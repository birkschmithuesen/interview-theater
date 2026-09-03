"""Sprachmodell-Client fuer Kimi K2.6 ueber Infomaniak (OpenAI-kompatibler
chat/completions-Endpunkt), Modus A (SPEC-kontext-architektur.md § 4, § 11.3).

Vorlage: kg.llm (chat_completions-Zweig), siehe
/home/birk/projekte/kollektivgedaechtnis/kg/llm.py und
.superpowers/sdd/task-5-brief.md. Uebernommen: die Form von
``response_format`` (json_schema, strict), die Reparatur der doppelten
Klammer, dass ``reasoning_effort`` nur gesendet wird, wenn ein Wert gesetzt
ist, und die Wiederholung bei 5xx.

Drei gemessene Fehlerbilder desselben Vorprojekts, alle bei
``moonshotai/Kimi-K2.6``, alle mit HTTP 200:

1. ``content`` beginnt mit ``{{`` statt ``{`` -- ohne ``reasoning_effort``
   nie ein valides JSON (0 von 5), mit ``"low"`` ebenfalls nicht (0 von 8),
   mit ``"none"`` immer (8 von 8). Die eine ueberzaehlige Klammer wird
   deshalb repariert statt eine bezahlte Antwort wegzuwerfen.
2. Bei aktivem Reasoning ist ``content`` ``null`` und der Text steht in
   ``message.reasoning``.
3. ``finish_reason == "length"``: das Reasoning verbraucht das
   Ausgabebudget, bevor der eigentliche Inhalt beginnt. Deshalb
   ``MAX_TOKENS = 9000`` und niemals ein leeres Ergebnis -- ein Fehler und
   ein Vorfall ``abgeschnitten``.
"""

import json
import logging
import random
import time

import httpx

from theatersoap import repo

log = logging.getLogger(__name__)

#: Grosszuegig bemessen, weil das Reasoning-Budget vor dem eigentlichen
#: Inhalt aufgebraucht sein kann (Fehlerbild 3 oben).
MAX_TOKENS = 9000

#: Wartezeiten zwischen Wiederholungen bei 5xx/Timeout; plus Jitter in
#: _sende_mit_wiederholung. Macht bis zu vier Versuche insgesamt.
WARTEZEITEN = (0.7, 1.5, 3.0)


class LLMFehler(Exception):
    """Fehler beim Zugriff auf das Sprachmodell.

    Der API-Schluessel steht ausschliesslich im Authorization-Header, nie in
    der URL -- anders als der Telegram-Token in theatersoap.telegram, der im
    URL-Pfad liegt und dort eigens bereinigt werden muss. Trotzdem gilt
    dieselbe Regel: Header und Anfragekoerper duerfen nie in eine
    Fehlermeldung wandern, die als Vorfall auf dem im Raum projizierten
    Dashboard landen kann.
    """


def erster_json_block(text: str) -> str:
    """Schneidet den ersten vollstaendigen ``{...}``-Block aus text.

    Zaehlt Klammern stringbewusst: Anfuehrungszeichen und
    Backslash-Maskierung werden erkannt, damit eine geschweifte Klammer
    innerhalb eines woertlichen Zitats (die Antworten enthalten Zitate aus
    Interviewtranskripten) den Block nicht vorzeitig beendet.
    """
    try:
        start = text.index("{")
    except ValueError as fehler:
        raise LLMFehler("keine oeffnende Klammer in der Antwort gefunden") from fehler

    tiefe = 0
    in_string = False
    maskiert = False
    for i in range(start, len(text)):
        zeichen = text[i]
        if in_string:
            if maskiert:
                maskiert = False
            elif zeichen == "\\":
                maskiert = True
            elif zeichen == '"':
                in_string = False
            continue
        if zeichen == '"':
            in_string = True
        elif zeichen == "{":
            tiefe += 1
        elif zeichen == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start : i + 1]

    raise LLMFehler("kein vollstaendiger JSON-Block in der Antwort gefunden")


def inhalt_aus(koerper: dict) -> str | None:
    """Liefert den Antworttext aus dem chat/completions-Koerper.

    Abweichung von der Vorlage (kg.llm._chat_completions_text): dort ist
    ``content: null`` bereits ein Fehler. Wir weichen stattdessen auf
    ``message.reasoning`` aus (SPEC-kontext-architektur.md § 4.4). Das ist
    sicher, weil im Anschluss ohnehin JSON geparst wird: steht dort kein
    JSON, schlaegt ``json.loads`` fehl und wir bekommen einen Fehler statt
    eines still durchgereichten leeren Ergebnisses.
    """
    nachricht = koerper["choices"][0].get("message") or {}
    return nachricht.get("content") or nachricht.get("reasoning")


class LLM:
    """Kapselt die chat/completions-Aufrufe fuer Modus A (Schema) und Prosa."""

    def __init__(self, e, klient: httpx.Client, conn):
        self._e = e
        self._klient = klient
        self._conn = conn

    def schema(self, chat_id: int | None, system: str, nutzer: str, schema: dict, art: str) -> dict:
        """Erzwingt ein JSON-Schema (``reasoning_effort: "none"``, Modus A)
        und liefert das geparste Ergebnis."""
        koerper = self._anfrage(
            chat_id=chat_id,
            system=system,
            nutzer=nutzer,
            art=art,
            modus="A",
            reasoning_effort="none",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": art, "strict": True, "schema": schema},
            },
        )
        text = self._text_aus(koerper)
        text = text.strip()
        if text.startswith("{{"):
            # Gemessenes Fehlerbild 1 (Moduldocstring): die eine
            # ueberzaehlige Klammer wegnehmen statt die Antwort zu verwerfen.
            text = text[1:]
            log.warning("llm-Antwort begann mit '{{'; doppelte Klammer repariert")
        block = erster_json_block(text)
        try:
            return json.loads(block)
        except json.JSONDecodeError as fehler:
            raise LLMFehler(f"Antwort ist kein gueltiges JSON: {fehler}") from fehler

    def prosa(self, chat_id: int | None, system: str, nutzer: str, art: str) -> str:
        """Freier Text (``reasoning_effort: "medium"``, Modus B)."""
        koerper = self._anfrage(
            chat_id=chat_id,
            system=system,
            nutzer=nutzer,
            art=art,
            modus="B",
            reasoning_effort="medium",
            response_format=None,
        )
        return self._text_aus(koerper).strip()

    def _text_aus(self, koerper: dict) -> str:
        text = inhalt_aus(koerper)
        if text is None:
            raise LLMFehler("weder content noch reasoning in der Antwort enthalten")
        return text

    def _anfrage(
        self,
        *,
        chat_id: int | None,
        system: str,
        nutzer: str,
        art: str,
        modus: str,
        reasoning_effort: str | None,
        response_format: dict | None,
    ) -> dict:
        """Baut den Request, schickt ihn (mit Wiederholung bei 5xx/Timeout)
        und protokolliert den Aufruf -- im ``finally``, damit auch
        Fehlschlaege in der Tabelle ``aufruf`` landen."""
        body: dict = {
            "model": self._e.llm_modell,
            "max_tokens": MAX_TOKENS,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": nutzer},
            ],
        }
        if response_format is not None:
            body["response_format"] = response_format
        if reasoning_effort:
            # Nur senden, wenn gesetzt: Modelle, die das Feld nicht kennen,
            # lehnen den Request sonst mit HTTP 400 ab (Vorlage).
            body["reasoning_effort"] = reasoning_effort

        geschaetzte_token = (len(system) + len(nutzer)) // 3
        tatsaechliche_token = antwort_token = finish_reason = None
        erfolg = 0
        start = time.monotonic()
        try:
            koerper = self._sende_mit_wiederholung(body, chat_id=chat_id, art=art)
            try:
                auswahl = koerper["choices"][0]
            except (KeyError, IndexError, TypeError) as fehler:
                raise LLMFehler(f"keine choices in der Antwort: {fehler}") from fehler

            finish_reason = auswahl.get("finish_reason")
            nutzung = koerper.get("usage") or {}
            tatsaechliche_token = nutzung.get("prompt_tokens")
            antwort_token = nutzung.get("completion_tokens")

            if finish_reason == "length":
                # Fehlerbild 3 (Moduldocstring): niemals ein leeres Ergebnis
                # durchreichen, sondern Fehler plus Vorfall.
                repo.merke_vorfall(
                    self._conn,
                    chat_id,
                    getattr(self._e, "bot_name", None),
                    "abgeschnitten",
                    f"Sprachmodell-Antwort bei max_tokens abgeschnitten (art={art})",
                )
                raise LLMFehler(
                    "Antwort wurde bei max_tokens abgeschnitten (finish_reason: length)"
                )

            erfolg = 1
            return koerper
        finally:
            dauer_ms = int((time.monotonic() - start) * 1000)
            repo.merke_aufruf(
                self._conn,
                chat_id,
                art,
                modus,
                geschaetzte_token,
                tatsaechliche_token,
                antwort_token,
                finish_reason,
                dauer_ms,
                erfolg,
            )

    def _sende_mit_wiederholung(self, body: dict, *, chat_id: int | None, art: str) -> dict:
        """Schickt den Request, wiederholt bei 5xx/Transportfehler mit den
        Wartezeiten aus WARTEZEITEN plus etwas Jitter -- bis zu vier
        Versuche insgesamt. Erfolgreiche Wiederholungen werden der Gruppe
        nicht gemeldet (SPEC § 11.3 Punkt 3), aber als Vorfall 'http_5xx'
        gezaehlt, damit sich Haeufungen im Dashboard zeigen.

        ``httpx.TransportError`` ist die gemeinsame Basisklasse von
        ``ConnectError``, ``ReadError`` und ``TimeoutException`` -- das
        Betriebsszenario "Infomaniak ist komplett weg" (SPEC § 11.1) aeussert
        sich in der Praxis fast immer als ConnectError/DNS-Fehler, nicht als
        HTTP 500 oder Timeout, und muss deshalb genauso wiederholt und in
        einen LLMFehler verpackt werden."""
        letzter_fehler: Exception | None = None
        gesamtversuche = len(WARTEZEITEN) + 1
        for versuch in range(gesamtversuche):
            try:
                antwort = self._klient.post(
                    self._e.llm_url, headers=self._headers(), json=body
                )
                antwort.raise_for_status()
                return antwort.json()
            except httpx.HTTPStatusError as fehler:
                if fehler.response.status_code < 500:
                    raise LLMFehler(
                        f"Sprachmodell lehnte den Aufruf ab: HTTP {fehler.response.status_code}"
                    ) from fehler
                letzter_fehler = fehler
            except httpx.TransportError as fehler:
                letzter_fehler = fehler

            if versuch < len(WARTEZEITEN):
                # Fehlertyp und Versuchsnummer, bewusst ohne str(fehler):
                # weder Header noch Anfragekoerper duerfen in den Vorfall
                # wandern (siehe LLMFehler-Docstring).
                repo.merke_vorfall(
                    self._conn,
                    chat_id,
                    getattr(self._e, "bot_name", None),
                    "http_5xx",
                    f"Sprachmodell-Aufruf fehlgeschlagen ({type(letzter_fehler).__name__}), "
                    f"Versuch {versuch + 1}/{gesamtversuche}, Wiederholung folgt (art={art})",
                )
                time.sleep(WARTEZEITEN[versuch] + random.uniform(0, 0.3))

        raise LLMFehler(
            f"Sprachmodell nach {gesamtversuche} Versuchen nicht erreichbar "
            f"(zuletzt: {type(letzter_fehler).__name__})"
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._e.llm_key}",
            "Content-Type": "application/json",
        }

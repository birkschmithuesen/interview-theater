"""Sprachmodell-Client fuer Kimi K2.6 ueber Infomaniak (OpenAI-kompatibler
chat/completions-Endpunkt), Modus A (SPEC-kontext-architektur.md § 4, § 11.3).

Vorlage: kg.llm (chat_completions-Zweig), siehe
/home/birk/projekte/kollektivgedaechtnis/kg/llm.py und
.superpowers/sdd/task-5-brief.md. Uebernommen: die Form von
``response_format`` (json_schema, strict) und die Wiederholung bei 5xx.
**Nicht** uebernommen: dass ``reasoning_effort`` nur bei gesetztem Wert
gesendet wurde -- siehe Fehlerbild 4 unten, das ist genau umgekehrt worden.

Vier gemessene Fehlerbilder, alle bei ``moonshotai/Kimi-K2.6``, alle mit
HTTP 200:

1. ``content`` beginnt mit ueberzaehligen Klammern statt nur ``{`` -- ohne
   ``reasoning_effort`` nie ein valides JSON (0 von 5), mit ``"low"``
   ebenfalls nicht (0 von 8), mit ``"none"`` immer (8 von 8). Gemessen
   wurden dabei unterschiedlich lange Praefixe (ein Zeichen ``{{``, aber
   auch zwei Zeichen ``' {{'`` -- ein Leerzeichen plus eine ueberzaehlige
   Klammer) -- deshalb sucht ``lies_json`` die passende Position, statt
   blind eine feste Anzahl Zeichen abzuschneiden.
2. Bei aktivem Reasoning ist ``content`` ``null`` und der Text steht in
   ``message.reasoning``.
3. ``finish_reason == "length"``: das Reasoning verbraucht das
   Ausgabebudget, bevor der eigentliche Inhalt beginnt. Deshalb
   ``MAX_TOKENS = 9000`` und niemals ein leeres Ergebnis -- ein Fehler und
   ein Vorfall ``abgeschnitten``, im Text ausdruecklich als Budgetproblem
   benannt (``max_tokens`` zu klein), nicht als Formatproblem.
4. **`reasoning_effort` ist bei Infomaniak binaer** (SPEC § 4.4): ``"none"``
   schaltet Reasoning aus, jeder andere Wert -- auch das Fehlen des Feldes!
   -- schaltet es an. Es gibt keine stille Voreinstellung "aus". Das Feld
   wird deshalb **immer** gesendet, mit Vorgabewert ``"none"``.
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


#: Obergrenze fuer die Praefix-Suche in lies_json: die gemessenen
#: Artefakte sind ein bis zwei Zeichen lang, nie Zeilen. ``raw_decode(text,
#: i)`` arbeitet ueber einen Index in den unveraenderten String, nicht ueber
#: ``text[i:]`` -- es wird also bei jedem Versuch nicht neu geslict, das
#: waere hier gar nicht die Kostenquelle. Der eigentliche Grund fuer den
#: Deckel: ohne ihn wuerde reiner Fliesstext ohne jedes JSON an jeder
#: einzelnen Position im ganzen Text einen (meist sofort scheiternden)
#: Parse-Versuch ausloesen. 200 Zeichen geben dem gemessenen Praefix
#: grosszuegigen Sicherheitsabstand und begrenzen die Anzahl dieser
#: Versuche auf einen kleinen, konstanten Wert.
LIES_JSON_SUCHFENSTER = 200


def lies_json(text: str) -> dict:
    """Liest ein JSON-Objekt robust aus einer Modellantwort.

    Erst wird ``json.loads`` auf den ganzen, getrimmten Text versucht --
    der Normalfall bei ``reasoning_effort: "none"``. Schlaegt das fehl
    (Praefix-Artefakt, siehe Moduldocstring Fehlerbild 1), wird die erste
    Position gesucht, ab der der Rest **vollstaendig als JSON-Wert
    parst** -- nicht blind eine feste Zeichenzahl abgeschnitten, weil das
    gemessene Praefix mal ein, mal zwei Zeichen lang war.

    ``json.JSONDecoder.raw_decode`` statt ``json.loads`` fuer die Suche:
    das erlaubt zusaetzlich Text *nach* dem JSON-Objekt (Kimi haengt
    gelegentlich noch einen Satz an), waehrend json.loads das als
    "Extra data" ablehnen wuerde. Anfuehrungszeichen und
    Backslash-Maskierung sind dabei automatisch beruecksichtigt -- eine
    geschweifte Klammer innerhalb eines woertlichen Zitats (die Antworten
    enthalten Zitate aus Interviewtranskripten) beendet den Block deshalb
    nicht vorzeitig.

    **Mehrdeutigkeit nach dem gefundenen Block ist ein Fehler, kein
    stillschweigend verworfener Rest.** ``raw_decode`` liest nur den ersten
    JSON-Wert und ignoriert von sich aus alles danach -- das ist bei reiner
    Prosa erwuenscht, aber gefaehrlich, wenn dort ein *zweiter* JSON-Wert
    folgt: der haeufigste gueltige Absichtserkenner-Fall ist die leere
    Liste ``{"aenderungen": []}``, und ein zweiter, inhaltstragender Block
    dahinter wuerde sonst lautlos verschluckt (Review-Befund 2026-09-04).
    Deshalb wird der Rest nach dem gefundenen Block auf ein weiteres
    ``{``/``[`` geprueft und im Trefferfall ein Fehler geworfen; reiner
    Fliesstext danach bleibt erlaubt.
    """
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    dekoder = json.JSONDecoder()
    grenze = min(len(text), LIES_JSON_SUCHFENSTER)
    for i in range(grenze):
        try:
            ergebnis, ende = dekoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue

        rest = text[ende:].lstrip()
        if rest and rest[0] in "{[":
            log.warning(
                "llm-Antwort enthaelt mehr als einen JSON-Wert; als "
                "mehrdeutig verworfen statt den ersten (moeglicherweise "
                "leeren) Block stillschweigend zu nehmen"
            )
            raise LLMFehler(
                "Antwort ist mehrdeutig: mehr als ein JSON-Wert gefunden "
                f"(erster Block endet bei Zeichen {ende}, danach folgt ein "
                "weiterer JSON-Wert statt reinem Fliesstext)"
            )
        return ergebnis

    raise LLMFehler(
        "kein Text gefunden, dessen Rest vollstaendig als JSON parst "
        f"(erste {grenze} Zeichen durchsucht)"
    )


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

    def schema(
        self,
        chat_id: int | None,
        system: str,
        nutzer: str,
        schema: dict,
        art: str,
        modell: str | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Erzwingt ein JSON-Schema (Modus A) und liefert das geparste
        Ergebnis.

        ``reasoning_effort`` wird hier bewusst **nicht** an ``_anfrage``
        uebergeben, sondern deren Vorgabewert ``"none"`` ueberlassen --
        das ist der Beleg dafuer, dass ein Aufrufer, der das Feld nicht
        anfasst, "aus" bekommt und nicht "an" (SPEC § 4.4).

        ``modell`` und ``temperature`` sind optional: ohne Angabe gilt
        ``e.llm_modell`` und der Anfragekoerper bekommt gar kein
        ``temperature``-Feld. Grundlage dafuer, dass unterschiedliche
        Aufrufe (Gespraech, Absichtserkenner) unterschiedliche Modelle und
        Temperaturen waehlen koennen (SPEC § 4.3a).
        """
        koerper = self._anfrage(
            chat_id=chat_id,
            system=system,
            nutzer=nutzer,
            art=art,
            modus="A",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": art, "strict": True, "schema": schema},
            },
            modell=modell,
            temperature=temperature,
        )
        text = self._text_aus(koerper)
        return lies_json(text)

    def prosa(
        self,
        chat_id: int | None,
        system: str,
        nutzer: str,
        art: str,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        """Freier Text mit aktivem Reasoning (Modus B).

        ``reasoning_effort: "medium"`` heisst hier schlicht "an": bei
        Infomaniak ist der Parameter binaer, low/medium/high sind
        untereinander nicht unterscheidbar (gemessen 04.09.2026, siehe
        Moduldocstring Fehlerbild 4). Der Wert steht fest verdrahtet, weil es
        nichts zu waehlen gibt.

        ``max_tokens`` und ``timeout`` sind additiv und optional: ohne
        Angabe gilt MAX_TOKENS bzw. der Timeout des uebergebenen
        httpx.Client, der Aufruf verhaelt sich also unveraendert. Der
        Szenen-Aufruf (theatersoap/szene.py) setzt beide hoch, weil aktives
        Reasoning das Ausgabebudget vor dem eigentlichen Inhalt verbraucht
        (``max_tokens >= 12.000``) und die Latenz um Faktor 7-23 steigt (der
        30-Sekunden-Client-Timeout aus bot.main reicht dafuer nicht)."""
        koerper = self._anfrage(
            chat_id=chat_id,
            system=system,
            nutzer=nutzer,
            art=art,
            modus="B",
            reasoning_effort="medium",
            response_format=None,
            max_tokens=max_tokens,
            timeout=timeout,
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
        response_format: dict | None,
        reasoning_effort: str | None = "none",
        modell: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Baut den Request, schickt ihn (mit Wiederholung bei 5xx/Timeout)
        und protokolliert den Aufruf -- im ``finally``, damit auch
        Fehlschlaege in der Tabelle ``aufruf`` landen.

        ``modell`` faellt ohne Angabe auf ``e.llm_modell`` zurueck;
        ``temperature`` wird nur gesendet, wenn gesetzt (manche Modelle
        kennen das Feld nicht und lehnen es sonst ab). ``max_tokens`` faellt
        ohne Angabe auf MAX_TOKENS zurueck, ``timeout`` auf den des
        httpx.Client -- beide werden nur von Aufrufen mit aktivem Reasoning
        heraufgesetzt (siehe ``prosa``)."""
        body: dict = {
            "model": modell or self._e.llm_modell,
            "max_tokens": max_tokens or MAX_TOKENS,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": nutzer},
            ],
        }
        if response_format is not None:
            body["response_format"] = response_format
        if temperature is not None:
            body["temperature"] = temperature
        # reasoning_effort ist bei Infomaniak BINAER: "none" schaltet
        # Reasoning aus, jeder andere Wert -- und auch das Fehlen des
        # Feldes! -- schaltet es an. Es gibt keine stille Voreinstellung
        # "aus". Deshalb wird das Feld IMMER gesendet, mit Vorgabewert
        # "none" oben in der Signatur (SPEC-kontext-architektur.md § 4.4).
        # Eine fruehere Fassung hatte hier ein ``if reasoning_effort:`` --
        # das liess das Feld bei einem leeren Wert weg und schaltete
        # Reasoning damit ungewollt ein: still zwanzigfache Latenz plus,
        # bei Klassifikationsaufgaben, eingebrochene Trefferquote.
        #
        # Die Typannotation "str" auf dem Parameter erzwingt zur Laufzeit
        # nichts -- ein interner Aufrufer, der explizit ``None`` uebergibt,
        # wuerde sonst "reasoning_effort": null in den Koerper schreiben.
        # Das ist dieselbe binaere Falle eine Ebene tiefer, deshalb hier
        # nochmal auf den Vorgabewert normalisiert statt sich auf den
        # Funktions-Default zu verlassen (der bei explizitem ``None`` nicht
        # greift).
        if reasoning_effort is None:
            reasoning_effort = "none"
        body["reasoning_effort"] = reasoning_effort

        geschaetzte_token = (len(system) + len(nutzer)) // 3
        tatsaechliche_token = antwort_token = finish_reason = None
        erfolg = 0
        start = time.monotonic()
        try:
            koerper = self._sende_mit_wiederholung(
                body, chat_id=chat_id, art=art, timeout=timeout
            )
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
                # durchreichen, sondern Fehler plus Vorfall. Ausdruecklich
                # als Budgetproblem benannt (max_tokens zu klein), nicht als
                # Formatproblem -- wer das im Log liest, soll nicht nach
                # einem Parserfehler suchen.
                repo.merke_vorfall(
                    self._conn,
                    chat_id,
                    getattr(self._e, "bot_name", None),
                    "abgeschnitten",
                    f"Sprachmodell-Antwort abgeschnitten, max_tokens zu klein (art={art})",
                )
                raise LLMFehler(
                    "Sprachmodell-Antwort abgeschnitten: max_tokens zu klein fuer diese "
                    "Aufgabe (finish_reason: length) -- kein Formatfehler, ein Budgetproblem."
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

    def _sende_mit_wiederholung(
        self, body: dict, *, chat_id: int | None, art: str, timeout: float | None = None
    ) -> dict:
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
        # Ohne eigenen Wert bleibt es beim Timeout des Klienten -- httpx
        # unterscheidet "nicht gesetzt" nicht an None, deshalb wird das
        # Argument nur im Ausnahmefall ueberhaupt mitgegeben.
        zusatz = {} if timeout is None else {"timeout": timeout}
        for versuch in range(gesamtversuche):
            try:
                antwort = self._klient.post(
                    self._e.llm_url, headers=self._headers(), json=body, **zusatz
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

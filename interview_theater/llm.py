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

from interview_theater import repo

log = logging.getLogger(__name__)

#: Grosszuegig bemessen, weil das Reasoning-Budget vor dem eigentlichen
#: Inhalt aufgebraucht sein kann (Fehlerbild 3 oben).
MAX_TOKENS = 32_000
#: 05.09. 04:20: war 9.000. Simulation --set birk: Kimi lief im Gespraech
#: (reasoning none!) in finish_reason=length, weil es sein Selbstgespraech ins
#: Antwortfeld schrieb (~4.000 Zeichen) und dann das JSON nicht mehr schloss.
#: Deckel = Obergrenze gegen ein durchdrehendes Modell, nie Zielwert knapp
#: ueber der Messung (Birk 04.09.). Bezahlt werden nur erzeugte Token.

#: Wartezeiten zwischen Wiederholungen bei 5xx/Timeout; plus Jitter in
#: _sende_mit_wiederholung. Macht bis zu vier Versuche insgesamt.
WARTEZEITEN = (0.7, 1.5, 3.0)

#: Ist Streaming bei diesem Anbieter ueberhaupt moeglich? Eine
#: PROZESSflagge, kein Dauerversuch (Plan Karte W, Abweichung 2): hat der
#: Anbieter ``stream: true`` einmal abgelehnt oder keine ``usage`` geliefert,
#: geht jeder weitere Aufruf dieses Prozesses sofort blockierend -- sonst
#: zahlte jede Antwort den Fehlversuch mit, und E7 (Kostendeckel) stuende
#: dauerhaft auf geschaetzten Zahlen.
_STROM_AUS = False


def strom_moeglich() -> bool:
    return not _STROM_AUS


def vergiss_strom() -> None:
    """Nur fuer Tests: die Prozessflagge zuruecknehmen."""
    global _STROM_AUS
    _STROM_AUS = False


class _StromNichtVerfuegbar(Exception):
    """Der Anbieter hat den Stream DAUERHAFT abgelehnt (unbekannter
    Parameter, kaputte Antwort) -- BEVOR ein Stueck kam. Setzt die
    Prozessflagge ``_STROM_AUS``: dieser Anbieter kann kein Streaming."""


class _StromVoruebergehend(Exception):
    """Ein VORUEBERGEHENDER Fehler (429, 5xx, Transport-/Dekodierfehler) --
    BEVOR ein Stueck kam (Fix Runde 1, Punkt 3). Infomaniak drosselt mit
    429/5xx statt mit einer sauberen Warteschlange (AGENTS.md Falle 8); ein
    einzelner Drosselimpuls darf nicht jede weitere Antwort dieses Prozesses
    auf Nichtstreaming umschalten. Setzt die Prozessflagge NICHT -- nur
    dieser eine Zug laeuft blockierend weiter."""


class _StromAbbruch(Exception):
    """Der Stream ist mitten drin abgerissen -- NACH dem ersten Stueck. Setzt
    die Prozessflagge nie: ein Abbruch sagt nichts darueber, ob der naechste
    Stream gelingt."""


class LLMFehler(Exception):
    """Fehler beim Zugriff auf das Sprachmodell.

    Der API-Schluessel steht ausschliesslich im Authorization-Header, nie in
    der URL -- anders als der Telegram-Token in interview_theater.telegram, der im
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
        bei_teil=None,
        teil_feld: str = "antwort",
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

        ``bei_teil`` (30.09.2026, Karte W): eine Senke, die den bisherigen
        Text bekommt, waehrend er entsteht. **Sie bekommt nicht das rohe
        JSON**, sondern den mit ``strom.wert_aus_praefix`` dekodierten Wert von
        ``teil_feld`` -- der Gespraechszug laeuft ueber dieses Schema, und was
        die Gruppe sehen soll, ist der Satz und nicht die Verpackung.
        Ohne ``bei_teil`` ist der Anfragekoerper zeichengleich wie vorher.
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
            bei_teil=bei_teil,
            teil_feld=teil_feld,
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
        bei_teil=None,
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
        Szenen-Aufruf (interview_theater/szene.py) setzt beide hoch, weil aktives
        Reasoning das Ausgabebudget vor dem eigentlichen Inhalt verbraucht
        (``max_tokens >= 12.000``) und die Latenz um Faktor 7-23 steigt (der
        30-Sekunden-Client-Timeout aus bot.main reicht dafuer nicht).

        ``bei_teil`` bekommt hier den rohen, bisherigen Text -- anders als bei
        ``schema`` gibt es kein Feld, das dekodiert werden muesste."""
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
            bei_teil=bei_teil,
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
        bei_teil=None,
        teil_feld: str | None = None,
    ) -> dict:
        """Baut den Request, schickt ihn (mit Wiederholung bei 5xx/Timeout)
        und protokolliert den Aufruf -- im ``finally``, damit auch
        Fehlschlaege in der Tabelle ``aufruf`` landen.

        ``modell`` faellt ohne Angabe auf ``e.llm_modell`` zurueck;
        ``temperature`` wird nur gesendet, wenn gesetzt (manche Modelle
        kennen das Feld nicht und lehnen es sonst ab). ``max_tokens`` faellt
        ohne Angabe auf MAX_TOKENS zurueck, ``timeout`` auf den des
        httpx.Client -- beide werden nur von Aufrufen mit aktivem Reasoning
        heraufgesetzt (siehe ``prosa``).

        ``bei_teil``/``teil_feld`` (30.09.2026, Karte W): ohne ``bei_teil``
        bleibt der Anfragekoerper zeichengleich wie vor dieser Karte (E1)."""
        body = self._baue_body(
            system=system, nutzer=nutzer, response_format=response_format,
            reasoning_effort=reasoning_effort, modell=modell,
            temperature=temperature, max_tokens=max_tokens,
        )

        # Dieselbe Schaetzung wie beim Promptbau (Zeichen / 3, kein
        # Tokenizer) -- und ausdruecklich dieselbe FUNKTION: die Spalte
        # ``aufruf.geschaetzte_token`` ist die Messreihe, an der der Divisor
        # nachjustiert wird (HANDOFF (g)). Stuende die 3 hier ein zweites Mal,
        # wuerde eine Korrektur an ``kontext.schaetze`` die Messreihe nicht
        # mit korrigieren.
        from interview_theater import kontext

        geschaetzte_token = kontext.schaetze(system + nutzer)
        tatsaechliche_token = antwort_token = finish_reason = None
        erfolg = 0
        start = time.monotonic()
        try:
            koerper = self._hole(
                body, chat_id=chat_id, art=art, timeout=timeout,
                bei_teil=bei_teil, teil_feld=teil_feld,
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
                self._melde_abgeschnitten(chat_id, art)

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

    def _hole(self, body: dict, *, chat_id, art, timeout, bei_teil, teil_feld) -> dict:
        """Ein Anbieteraufruf -- streamend, wenn eine Senke da ist, sonst wie
        immer. Liefert in **beiden** Faellen denselben Koerper, damit alles
        danach (``_text_aus``, ``lies_json``, die Buchung im ``finally`` von
        ``_anfrage``) unveraendert weiterlaeuft."""
        if bei_teil is None or not strom_moeglich():
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        strom_body = dict(body)
        strom_body["stream"] = True
        strom_body["stream_options"] = {"include_usage": True}
        try:
            koerper = self._sende_strom(strom_body, timeout=timeout,
                                        bei_teil=bei_teil, teil_feld=teil_feld,
                                        art=art)
        except _StromVoruebergehend as fehler:
            # Fix Runde 1, Punkt 3: ein einzelner Drosselimpuls (429/5xx,
            # Transport-/Dekodierfehler vor dem ersten Stueck) schaltet das
            # Streaming NICHT fuer den Prozess ab -- nur dieser eine Zug
            # laeuft blockierend weiter, die Flagge bleibt unberuehrt.
            log.info("Stream voruebergehend nicht verfuegbar (art=%s): %s -- "
                     "dieser Zug laeuft blockierend, Flagge bleibt an",
                     art, fehler)
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        except _StromNichtVerfuegbar as fehler:
            self._melde_strom_aus(chat_id, art, f"abgelehnt: {fehler}")
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        except _StromAbbruch as fehler:
            # Entscheidung E: KEIN halber Text wird zur Nachricht. Die
            # vorlaeufige Blase verschwindet, und genau EIN blockierender
            # Versuch holt die vollstaendige Antwort. Fix Runde 1, Punkt 6:
            # der abgerissene Stream selbst wird NICHT gebucht -- nur dieser
            # Nachversuch hinterlaesst die eine ``aufruf``-Zeile, geschrieben
            # im ``finally`` von ``_anfrage`` nach dessen Rueckgabe.
            abbruch = getattr(bei_teil, "abbruch", None)
            if callable(abbruch):
                abbruch()
            log.warning("Stream abgerissen (art=%s): %s -- ein Versuch ohne Stream",
                        art, type(fehler).__name__)
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        if not (koerper.get("usage") or {}).get("prompt_tokens"):
            self._melde_strom_aus(chat_id, art, "keine usage im Stream")
        return koerper

    def _melde_strom_aus(self, chat_id: int | None, art: str, grund: str) -> None:
        """Einmal je Prozess: Vorfall und Flagge."""
        global _STROM_AUS
        if _STROM_AUS:
            return
        _STROM_AUS = True
        try:
            repo.merke_vorfall(
                self._conn, chat_id, getattr(self._e, "bot_name", None),
                "strom_nicht_verfuegbar",
                f"Streaming abgeschaltet fuer diesen Prozess ({grund}, art={art})",
            )
        except Exception:  # noqa: BLE001 -- ein Vorfall reisst keinen Zug mit
            log.exception("Vorfall strom_nicht_verfuegbar nicht geschrieben")

    def _sende_strom(self, body: dict, *, timeout, bei_teil, teil_feld, art: str) -> dict:
        """Ein Aufruf mit ``stream: true``; baut aus den Stuecken denselben
        Koerper, den der blockierende Weg liefert.

        Keine Wiederholung hier: ein abgerissener Stream wird EINMAL ohne
        Stream wiederholt (``_hole``), und den Anbieter mehrfach streamen zu
        lassen hiesse, denselben Text mehrfach zu bezahlen.

        ``jemals_stueck`` ist wahr, sobald irgendein Delta ankam -- Inhalt
        ODER Denkspur (Fix Runde 1, Punkt 4: eine reine Denkspur-Antwort ist
        kein leerer Stream). ``fertig_gesehen`` ist wahr, sobald ein
        ``finish_reason`` oder ``[DONE]`` ankam. Ein sauberes Verbindungsende
        OHNE ``fertig_gesehen`` ist ein Abbruch (Fix Runde 1, Punkt 1,
        KRITISCH): sonst kaeme ein abgeschnittener Satz als vollstaendige
        Antwort durch."""
        from interview_theater import strom as strom_modul

        zusatz = {} if timeout is None else {"timeout": timeout}
        roh: list[str] = []
        denkspur_roh: list[str] = []
        finish = None
        nutzung: dict = {}
        jemals_stueck = False
        fertig_gesehen = False
        sende_an_senke = True
        try:
            with self._klient.stream(
                "POST", self._e.llm_url, headers=self._headers(), json=body, **zusatz
            ) as antwort:
                if antwort.status_code >= 400:
                    if antwort.status_code == 429 or antwort.status_code >= 500:
                        raise _StromVoruebergehend(f"HTTP {antwort.status_code}")
                    raise _StromNichtVerfuegbar(f"HTTP {antwort.status_code}")
                for zeile in antwort.iter_lines():
                    zeile = zeile.strip()
                    if not zeile.startswith("data:"):
                        continue
                    nutzlast = zeile[len("data:"):].strip()
                    if nutzlast == "[DONE]":
                        fertig_gesehen = True
                        break
                    try:
                        stueck = json.loads(nutzlast)
                    except json.JSONDecodeError as fehler:
                        if jemals_stueck:
                            raise _StromAbbruch("unlesbares Stueck") from fehler
                        raise _StromNichtVerfuegbar("unlesbare Antwort") from fehler
                    if stueck.get("usage"):
                        nutzung = stueck["usage"]
                    for wahl in stueck.get("choices") or []:
                        if wahl.get("finish_reason"):
                            finish = wahl["finish_reason"]
                            fertig_gesehen = True
                        delta = wahl.get("delta") or {}
                        teil = delta.get("content")
                        # ``reasoning_content`` geht NIEMALS an ``bei_teil``:
                        # die Denkspur ist nie fuer die Gruppe (Entscheidung
                        # C). Gesammelt wird sie trotzdem (Fix Runde 1,
                        # Punkt 4) -- siehe Rueckgabe unten.
                        denkspur = delta.get("reasoning_content")
                        if denkspur:
                            jemals_stueck = True
                            denkspur_roh.append(denkspur)
                        if not teil:
                            continue
                        jemals_stueck = True
                        roh.append(teil)
                        if not sende_an_senke:
                            continue
                        ganz = "".join(roh)
                        wert = (strom_modul.wert_aus_praefix(ganz, teil_feld)
                                if teil_feld else ganz)
                        try:
                            bei_teil(wert)
                        except Exception:  # noqa: BLE001 -- Fix Runde 1, Punkt 2:
                            # eine werfende Anzeige (z. B. gesperrte DB) darf
                            # die Antwort nicht kosten. Nur die Anzeige
                            # stoppt, das Sammeln laeuft weiter.
                            log.exception(
                                "bei_teil-Senke fehlgeschlagen (art=%s) -- "
                                "Anzeige gestoppt, der Text wird trotzdem "
                                "weiter gesammelt", art,
                            )
                            sende_an_senke = False
        except (_StromNichtVerfuegbar, _StromVoruebergehend, _StromAbbruch):
            raise
        except httpx.HTTPStatusError as fehler:
            status = fehler.response.status_code
            if status == 429 or status >= 500:
                raise _StromVoruebergehend(f"HTTP {status}") from fehler
            raise _StromNichtVerfuegbar(f"HTTP {status}") from fehler
        except (httpx.TransportError, httpx.DecodingError, httpx.StreamError) as fehler:
            # Fix Runde 1, Punkt 5 (MINOR): ``httpx.DecodingError`` und
            # ``httpx.StreamError`` sind KEINE ``httpx.TransportError`` (eigene
            # Hierarchien), muessen aber genauso behandelt werden -- vor dem
            # ersten Stueck ein (voruebergehender) Rueckfall, danach ein
            # Abbruch.
            if jemals_stueck:
                raise _StromAbbruch(type(fehler).__name__) from fehler
            raise _StromVoruebergehend(type(fehler).__name__) from fehler

        if jemals_stueck and not fertig_gesehen:
            # Fix Runde 1, Punkt 1 (KRITISCH): die Verbindung endete sauber,
            # aber ohne Abschlusssignal -- das ist ein Abbruch, kein Erfolg.
            raise _StromAbbruch("Verbindung endete ohne finish_reason/[DONE]")
        if not jemals_stueck:
            raise _StromNichtVerfuegbar("kein einziges Stueck")

        # Fix Runde 1, Punkt 4: kam die Antwort nur als Denkspur
        # (Fehlerbild 2 im Moduldocstring), baut der Stream-Pfad dieselbe
        # Form wie der blockierende Weg -- ``inhalt_aus`` kennt den Rueckfall
        # auf ``message.reasoning`` bereits und braucht keinen zweiten,
        # bezahlten Versuch.
        geroh = "".join(roh)
        nachricht = ({"content": geroh} if geroh
                     else {"reasoning": "".join(denkspur_roh)})
        return {
            "choices": [{"message": nachricht, "finish_reason": finish}],
            "usage": nutzung,
        }

    def _baue_body(
        self,
        *,
        system: str,
        nutzer: str,
        response_format: dict | None,
        reasoning_effort: str | None,
        modell: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict:
        """Der Request-Koerper. Enthaelt die eine Falle, die diesem Modul den
        Moduldocstring wert war -- siehe ``reasoning_effort`` unten."""
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
        return body

    def _melde_abgeschnitten(self, chat_id: int | None, art: str) -> None:
        """Fehlerbild 3 (Moduldocstring): niemals ein leeres Ergebnis
        durchreichen, sondern Fehler plus Vorfall. Ausdruecklich als
        Budgetproblem benannt (max_tokens zu klein), nicht als Formatproblem --
        wer das im Log liest, soll nicht nach einem Parserfehler suchen."""
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

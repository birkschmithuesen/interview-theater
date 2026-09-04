"""Absichtserkenner (SPEC-kontext-architektur.md § 4.3, § 4.3a).

Schliesst die Luecke, die Teil A offen liess: ``kontext.py`` liest
``arbeitsstand``, ``figur`` und ``journal`` in den Prompt, aber vor Teil B
schrieb sie niemand. ``erkenne()`` erkennt Aenderungsabsichten im Gespraech,
``wende_an()`` schreibt sie in Arbeitsstand, Figuren, Journal und Schalter
(Aufgabe 3), ``baue_meldung()`` fasst die tatsaechlich wirksamen Aenderungen
zu hoechstens einer Nachricht je Lauf zusammen (Aufgabe 4), und ``laufe()``
kapselt alle drei Schritte fuer den Aufrufer aus dem Hintergrund-Pool.

Laeuft nachgelagert, nachdem die Bot-Antwort in der Gruppe steht. Niemand
wartet darauf (SPEC § 4.3): Modell ``google/gemma-4-31B-it``, erzwungenes
Schema, ``reasoning_effort: "none"`` (Vorgabe von ``LLM.schema``, hier nicht
extra gesetzt), ``temperature: 0.2``. Gemessen: 0 Falsch-Positive bei 25
Negativfaellen, 30/30 Treffer, 0,75 s -- Kimi (das Gespraechsmodell) verpasste
``interview_beenden`` in 3 von 3 Faellen, Nemotron-Nano fiel mit 6/27
Falsch-Positiven durch und darf deshalb nirgends als Vorgabewert auftauchen.

**Kontext:** aktueller Arbeitsstand + die neuen Nachrichten seit
``gruppe.letzte_extrahierte_message_id`` (``repo.unextrahierte``). Nicht das
Journal, nicht die Transkripte -- das Journal wird hier nur GESCHRIEBEN
(spaeter, in ``wende_an``), nie mitgelesen, und Transkripte gehoeren zum
Gespraechs-, nicht zum Erkenner-Kontext.

**Schema, bewusst flach** (global-constraints.md 'Schema'): ein Array aus
Objekten mit zwei Feldern, keine Verschachtelung tiefer als
``array > object > string``. Kein Objekt mit elf meist leeren Feldern --
strikte Modi kennen keine optionalen Felder, das Modell muesste jedes Mal
alle ausfuellen, und ein Feld, das befuellt werden *will*, ist ein
Halluzinationsanreiz. Die leere Liste ist die natuerliche Form von "nichts
gefunden". Kein ``maxItems`` im Schema (von strikten Modi oft nicht
unterstuetzt) -- die Fuenf-Obergrenze steht im Prompttext UND wird unten in
``erkenne()`` hart durchgesetzt.

**Fehlerhaltung** (global-constraints.md, SPEC § 4.3): Bei Erfolg rueckt das
Wasserzeichen vor, erkannte Aenderungen werden zurueckgegeben. Bei Fehlschlag
bleibt das Wasserzeichen STEHEN (kostenloser Wiederholungsversuch beim
naechsten Lauf), ein ``vorfall`` wird geschrieben, der Gruppe wird nichts
gemeldet, leere Liste zurueck. Ueber dem Token-Deckel FENSTER_DECKEL wird das
Wasserzeichen dagegen TROTZDEM vorgerueckt (sonst wuerde ein einmal zu
grosses Fenster den Erkenner dauerhaft lahmlegen) und ein ``vorfall``
``fenster_verworfen`` geschrieben.
"""

import logging
from pathlib import Path

from theatersoap import kontext, repo

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: theatersoap/prompts/erkenner.md fuer die vollstaendige Anweisung samt
#: der fuenf Few-Shot-Beispiele).
PROMPT = (Path(__file__).parent / "prompts" / "erkenner.md").read_text(encoding="utf-8")

#: Alle erkennbaren Aenderungsarten, in derselben Reihenfolge wie im Prompt
#: aufgelistet (SPEC § 4.3, teil-b.md Aufgabe 2). Auch die Schema-Enum unten
#: verwendet diese Liste, damit beide Stellen nie auseinanderlaufen.
ARTEN = (
    "interview_starten",
    "interview_beenden",
    "interview_benennen",
    "begriffe_setzen",
    "kernthema_setzen",
    "hauptkonflikt_setzen",
    "figur_setzen",
    "wortlaut_an",
    "wortlaut_aus",
    "verworfen",
    "entschieden",
)

#: Obergrenze fuer Aenderungen je Lauf -- im Prompttext UND hier im Code
#: durchgesetzt (global-constraints.md 'Schema': kein maxItems im Schema
#: selbst, weil strikte Modi das oft nicht unterstuetzen).
MAX_AENDERUNGEN = 5

#: Sampling-Temperatur des Erkenneraufrufs (SPEC § 4.3, § 4.3a) -- niedrig,
#: gegen Formulierungsvarianz und (bei mehrsprachigen Modellen)
#: Sprachdrift. Bewusst ein eigener Wert, nicht die des Gespraechsaufrufs.
TEMPERATURE = 0.2

#: Ab dieser geschaetzten Tokenzahl (kontext.schaetze -- Zeichen // 3, kein
#: Tokenizer) wird das Fenster verworfen statt gesendet (SPEC § 4.3
#: 'Deckel'): das Wasserzeichen rueckt trotzdem vor, ein vorfall
#: 'fenster_verworfen' wird geschrieben. Verhindert, dass ein einmal
#: aussergewoehnlich grosses Fenster (z. B. ein sehr langer Gespraechsstau)
#: den Erkenner auf Dauer blockiert.
FENSTER_DECKEL = 12000

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md § 4). Absichtlich flach: array > object > string,
#: keine tiefere Verschachtelung (die bricht bei kleineren Modellen wie
#: gemma/Apertus).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["aenderungen"],
    "properties": {
        "aenderungen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["art", "wert"],
                "properties": {
                    "art": {"type": "string", "enum": list(ARTEN)},
                    "wert": {"type": "string"},
                },
            },
        },
    },
}


def _arbeitsstand_text(conn, chat_id: int) -> str:
    """Formatiert den aktuellen Arbeitsstand (Begriffe, Kernthema,
    Hauptkonflikt, Figuren) fuer den Erkenner-Kontext -- eine eigene,
    schlanke Formatierung statt der privaten ``kontext._baue_arbeitsstand``,
    weil der Erkenner den Stand nur als Eingabe braucht, nicht in der vollen
    Anzeigeform des Gespraechs-Prompts (dort zusaetzlich mit
    Kernthema-Begruendung)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)

    zeilen = []
    if stand:
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
        if stand["kernthema"]:
            zeilen.append(f"Kernthema: {stand['kernthema']}")
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(f"Figur {figur['name']}{beschreibung}")

    if not zeilen:
        return ""
    return "Arbeitsstand:\n" + "\n".join(zeilen)


def _nachrichten_text(nachrichten) -> str:
    zeilen = [kontext.sprecherzeile(n) for n in nachrichten]
    return "Neue Nachrichten:\n" + "\n".join(zeilen)


def _baue_nutzertext(conn, chat_id: int, nachrichten) -> str:
    """Baut den Nutzertext des Erkenneraufrufs: aktueller Arbeitsstand plus
    die neuen Nachrichten seit dem Wasserzeichen -- nicht das Journal, nicht
    die Transkripte (SPEC § 4.3)."""
    bloecke = [b for b in (_arbeitsstand_text(conn, chat_id), _nachrichten_text(nachrichten)) if b]
    return "\n\n".join(bloecke)


def erkenne(klm, conn, e, chat_id: int) -> list[dict]:
    """Erkennt Aenderungsabsichten im Gespraech seit der letzten Erkennung.

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art, modell=None, temperature=None) -> dict``-Methode (in
    Produktion ``theatersoap.llm.LLM``, in Tests eine Attrappe).

    Liefert eine Liste von ``{"art": ..., "wert": ...}``-Dicts, hoechstens
    ``MAX_AENDERUNGEN`` lang, nur mit bekannten ``art``-Werten. Wendet
    NICHTS auf die Datenbank an -- das ist eine spaetere Aufgabe
    (``wende_an``)."""
    neue = repo.unextrahierte(conn, chat_id)
    if not neue:
        # Kein Aufruf ins Leere: ohne neue Nachrichten gibt es nichts zu
        # erkennen, und ein Aufruf waere reine Latenz- und Kostenlast ohne
        # jeden Nutzen.
        return []

    letzte_message_id = max(n["message_id"] for n in neue)
    nutzer = _baue_nutzertext(conn, chat_id, neue)

    if kontext.schaetze(nutzer) > FENSTER_DECKEL:
        # Deckel (SPEC § 4.3): das Wasserzeichen rueckt TROTZDEM vor, sonst
        # bliebe der Erkenner an einem einmal zu grossen Fenster haengen und
        # wuerde bei jedem weiteren Lauf erneut daran scheitern.
        repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "fenster_verworfen",
            f"Absichtserkenner-Fenster ueber {FENSTER_DECKEL} geschaetzten Token "
            "verworfen, ohne Sprachmodell-Aufruf",
        )
        return []

    try:
        ergebnis = klm.schema(
            chat_id, PROMPT, nutzer, SCHEMA, "erkenner",
            modell=e.erkenner_modell, temperature=TEMPERATURE,
        )
    except Exception:
        # Fehlschlag: das Wasserzeichen bleibt STEHEN -- ein kostenloser
        # Wiederholungsversuch beim naechsten Lauf, ohne eigene
        # Retry-Logik hier (SPEC § 4.3). Der Gruppe wird nichts gemeldet,
        # sie kann den Fehler weder beheben noch wartet sie darauf
        # (global-constraints.md 'Fehlerhaltung').
        log.exception("Absichtserkennung fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "extraktor_fehler",
            "Absichtserkenner-Aufruf fehlgeschlagen",
        )
        return []

    aenderungen = []
    for eintrag in ergebnis.get("aenderungen", []):
        art = eintrag.get("art")
        if art not in ARTEN:
            # Unbekannte art wird verworfen statt zu krachen -- ein
            # strikt erzwungenes Schema garantiert zwar den Enum-Wert,
            # aber die Attrappe in Tests (und ein kuenftiger Anbieterwechsel)
            # koennen trotzdem einen unbekannten Wert liefern.
            continue
        aenderungen.append({"art": art, "wert": eintrag.get("wert", "")})
        if len(aenderungen) >= MAX_AENDERUNGEN:
            break

    repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
    return aenderungen


#: art -> Arbeitsstand-Feld fuer die drei Aenderungsarten, die ein einzelnes
#: Feld ueberschreiben (SPEC § 4.3 'Ueberschreiben ist der Normalfall').
_ARBEITSSTAND_ARTEN = {
    "begriffe_setzen": "begriffe",
    "kernthema_setzen": "kernthema",
    "hauptkonflikt_setzen": "hauptkonflikt",
}


def _wende_arbeitsstand_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Ueberschreibt ein Arbeitsstand-Feld -- aber nur, wenn sich der Wert
    tatsaechlich aendert (die wichtigste Regel aus Aufgabe 3: derselbe Wert
    ist keine Aenderung, sonst meldete Aufgabe 4 bei jedem Zug dasselbe
    Kernthema erneut)."""
    wert = wert.strip()
    if not wert:
        return None
    feld = _ARBEITSSTAND_ARTEN[art]
    stand = repo.hole_arbeitsstand(conn, chat_id)
    aktuell = stand[feld] if stand else None
    if aktuell == wert:
        return None
    repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    return {"art": art, "wert": wert}


def _wende_figur_an(conn, chat_id: int, wert: str) -> dict | None:
    """Trennt ``wert`` am ersten Doppelpunkt in Name und Beschreibung (SPEC
    § 4.3: 'ein String, den der Code am ersten Doppelpunkt trennt'). Ohne
    Doppelpunkt liefert ``str.partition`` eine leere Beschreibung statt zu
    krachen. Existiert der Name schon (getrimmt, Kleinschreibung -- siehe
    repo.setze_figur), wird nur bei tatsaechlich geaenderter Beschreibung
    geschrieben.

    Korrektur (2026-09-04): nennt das Modell beilaeufig einen schon
    bekannten Namen ohne Doppelpunkt (z. B. nur "Peter"), ist ``beschreibung``
    leer -- das darf die vorhandene Beschreibung NICHT loeschen. Ohne diese
    Pruefung ueberschrieb ein blosser Namenstreffer die vorhandene
    Beschreibung mit einem leeren String und die Meldung bestaetigte das
    sogar noch als 'Notiert', ohne dass jemand merkt, dass die Beschreibung
    weg ist -- echter, stiller Datenverlust. Bei einem NEUEN Namen bleibt das
    Verhalten unveraendert: eine leere Beschreibung ist dort kein Fehler,
    sondern der Normalfall (der Name allein ist schon eine Aenderung)."""
    wert = wert.strip()
    if not wert:
        return None
    name, _, beschreibung = wert.partition(":")
    name = name.strip()
    beschreibung = beschreibung.strip()
    if not name:
        return None

    vorhandene = repo.figuren(conn, chat_id)
    treffer = next(
        (f for f in vorhandene if f["name"].strip().lower() == name.lower()), None
    )
    if treffer is not None and not beschreibung:
        # Name bekannt, aber kein neuer Beschreibungsteil mitgeliefert --
        # die vorhandene Beschreibung bleibt unangetastet und gilt nicht als
        # Aenderung.
        return None
    if treffer is not None and (treffer["beschreibung"] or "").strip() == beschreibung:
        return None

    repo.setze_figur(conn, chat_id, name, beschreibung)
    return {"art": "figur_setzen", "wert": name}


def _wende_journal_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """``verworfen``/``entschieden`` haengen eine Journalzeile an -- nie in
    den Arbeitsstand (SPEC § 4.3: 'Journaleintraege fallen hier mit ab').
    Das Journal ist nur-anhaengend, ein Dubletten-Check waere hier sachfremd:
    zwei getrennte Aeusserungen mit demselben Wortlaut sind zwei Ereignisse."""
    wert = wert.strip()
    if not wert:
        return None
    repo.schreibe_journal(conn, chat_id, art, wert, quelle="erkenner")
    return {"art": art, "wert": wert}


def _wende_wortlaut_an(conn, chat_id: int, wert: str) -> dict | None:
    """``wortlaut_an``: Name im ``wert``, leer bedeutet 'alle' (``'*'``)."""
    name = wert.strip() or "*"
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["wortlaut_modus"] == name:
        return None
    repo.setze_wortlaut_modus(conn, chat_id, name)
    return {"art": "wortlaut_an", "wert": name}


def _wende_wortlaut_aus_an(conn, chat_id: int) -> dict | None:
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["wortlaut_modus"] is None:
        return None
    repo.setze_wortlaut_modus(conn, chat_id, None)
    return {"art": "wortlaut_aus", "wert": ""}


def _wende_interview_starten_an(conn, chat_id: int) -> dict | None:
    """Schaltet den Interviewmodus an (teil-b.md Aufgabe 5, SPEC § 10.1) --
    setzt gruppe.interviewmodus_seit auf jetzt. War der Modus schon an, ist
    das keine Aenderung (dieselbe Regel wie ueberall sonst: derselbe Zustand
    zaehlt nicht als Aenderung, sonst bestaetigte laufe() bei jedem
    Erkennerlauf erneut)."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["interviewmodus_seit"] is not None:
        return None
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    return {"art": "interview_starten", "wert": ""}


def _wende_interview_beenden_an(conn, chat_id: int) -> dict | None:
    """Schaltet den Interviewmodus aus -- spiegelbildlich zu
    _wende_interview_starten_an."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None or gruppe["interviewmodus_seit"] is None:
        return None
    repo.setze_interviewmodus(conn, chat_id, None)
    return {"art": "interview_beenden", "wert": ""}


def _wende_interview_benennen_an(conn, chat_id: int, wert: str) -> dict | None:
    """Benennt die letzte (juengste) Aufnahme dieser Gruppe um. Ohne
    vorhandene Aufnahme gibt es nichts umzubenennen -- ein stilles No-Op,
    kein Fehler."""
    wert = wert.strip()
    if not wert:
        return None
    aufnahmen = repo.transkripte(conn, chat_id)
    if not aufnahmen:
        return None
    letzte = aufnahmen[-1]
    if letzte["name"] == wert:
        return None
    repo.setze_aufnahme_name(conn, letzte["id"], wert)
    return {"art": "interview_benennen", "wert": wert}


def _wende_eine_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Wendet genau eine Aenderung an und liefert das angewendete
    ``{"art": ..., "wert": ...}`` zurueck, oder ``None`` wenn nichts
    geschrieben wurde (leerer Wert oder Wert bereits so in der Datenbank)."""
    if art == "interview_starten":
        return _wende_interview_starten_an(conn, chat_id)
    if art == "interview_beenden":
        return _wende_interview_beenden_an(conn, chat_id)
    if art in _ARBEITSSTAND_ARTEN:
        return _wende_arbeitsstand_an(conn, chat_id, art, wert)
    if art == "figur_setzen":
        return _wende_figur_an(conn, chat_id, wert)
    if art in ("verworfen", "entschieden"):
        return _wende_journal_an(conn, chat_id, art, wert)
    if art == "wortlaut_an":
        return _wende_wortlaut_an(conn, chat_id, wert)
    if art == "wortlaut_aus":
        return _wende_wortlaut_aus_an(conn, chat_id)
    if art == "interview_benennen":
        return _wende_interview_benennen_an(conn, chat_id, wert)
    # Unbekannte art sollte erkenne() bereits herausgefiltert haben; bei
    # direktem Aufruf von wende_an() (z. B. in Tests) einfach ignorieren
    # statt zu krachen.
    return None


def wende_an(conn, e, chat_id: int, aenderungen: list[dict]) -> list[dict]:
    """Schreibt erkannte Aenderungen in Arbeitsstand, Figuren, Journal und
    Schalter (SPEC § 4.3, teil-b.md Aufgabe 3).

    Liefert nur die Aenderungen zurueck, die tatsaechlich etwas verschoben
    haben -- Grundlage fuer die Meldung in Aufgabe 4 (``baue_meldung``).

    Robustheit: jede Aenderung laeuft in ihrem eigenen try/except. Eine
    fehlerhafte Aenderung (z. B. ein unerwarteter Werttyp) darf die anderen
    im selben Lauf nicht mitreissen -- sie wird geloggt und als ``vorfall``
    vermerkt, der Lauf macht mit der naechsten Aenderung weiter."""
    wirkliche = []
    for aenderung in aenderungen:
        art = None
        try:
            art = aenderung.get("art")
            wert = aenderung.get("wert") or ""
            ergebnis = _wende_eine_an(conn, chat_id, art, wert)
        except Exception:
            log.exception(
                "Anwenden einer Erkenner-Aenderung fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, art,
            )
            repo.merke_vorfall(
                conn,
                chat_id,
                getattr(e, "bot_name", None),
                "erkenner_anwenden_fehler",
                f"Aenderung art={art!r} konnte nicht angewendet werden",
            )
            continue
        if ergebnis is not None:
            wirkliche.append(ergebnis)
    return wirkliche


#: Zahlwoerter fuer die zusammenfassende Figuren-Zeile der Meldung (Aufgabe
#: 4) -- reicht bis MAX_AENDERUNGEN, weil in einem einzelnen Erkennerlauf nie
#: mehr als fuenf Aenderungen (und damit hoechstens fuenf figur_setzen)
#: vorkommen koennen.
_FIGUREN_ZAHLWORT = {2: "zwei", 3: "drei", 4: "vier", 5: "fuenf"}


def _figuren_zeile(namen: list[str]) -> str:
    liste = ", ".join(namen)
    if len(namen) == 1:
        return f"eine Figur: {liste}"
    zahlwort = _FIGUREN_ZAHLWORT.get(len(namen), str(len(namen)))
    return f"{zahlwort} Figuren: {liste}"


def baue_meldung(wirkliche_aenderungen: list[dict]) -> str | None:
    """Baut die eine Meldung je Erkennerlauf (SPEC § 4.3, teil-b.md Aufgabe
    4) -- nicht eine je Aenderung.

    Kernthema und Hauptkonflikt bekommen je eine eigene Zeile im Wortlaut,
    Figuren eine zusammenfassende Zeile mit Namen, Begriffe eine Zeile.
    Journaleintraege (``verworfen``/``entschieden``) sowie Schalter,
    Interviewmodus und Umbenennungen bleiben still -- sonst waere der Chat
    zugespammt und die Meldungen wuerden ueberlesen. Gab es keine Aenderung
    am Arbeitsstand, gibt es keine Meldung: ``None``."""
    kernthema = None
    hauptkonflikt = None
    begriffe = None
    figuren_namen = []
    for aenderung in wirkliche_aenderungen:
        art = aenderung.get("art")
        wert = aenderung.get("wert", "")
        if art == "kernthema_setzen":
            kernthema = wert
        elif art == "hauptkonflikt_setzen":
            hauptkonflikt = wert
        elif art == "begriffe_setzen":
            begriffe = wert
        elif art == "figur_setzen":
            figuren_namen.append(wert)
        # verworfen/entschieden/wortlaut_an/wortlaut_aus/interview_benennen:
        # bewusst ignoriert, bleiben still (Aufgabe 4).

    zeilen = []
    if kernthema:
        zeilen.append(f"Kernthema: {kernthema}")
    if hauptkonflikt:
        zeilen.append(f"Hauptkonflikt: {hauptkonflikt}")
    if figuren_namen:
        zeilen.append(_figuren_zeile(figuren_namen))
    if begriffe:
        zeilen.append(f"Begriffe: {begriffe}")

    if not zeilen:
        return None

    zeilen.append("Falls das nicht stimmt, sagt es mir.")
    return "Notiert:\n" + "\n".join(zeilen)


#: Wortlaut der Interviewmodus-Bestaetigung (teil-b.md Aufgabe 5, § 10.1) --
#: die EINE Ausnahme von "nur Arbeitsstandaenderungen werden gemeldet": der
#: Modus muss sichtbar sein, sonst weiss die Gruppe nicht, ob sie gerade
#: aufnimmt. Bewusst getrennt von baue_meldung()/der Aenderungsmeldung, nicht
#: mit ihr vermischt -- zwei kurze Nachrichten sind hier klarer als eine.
_TEXT_INTERVIEW_STARTEN = "Ich zeichne jetzt auf."
_TEXT_INTERVIEW_BEENDEN = "Aufnahme beendet."
_INTERVIEWMODUS_TEXTE = {
    "interview_starten": _TEXT_INTERVIEW_STARTEN,
    "interview_beenden": _TEXT_INTERVIEW_BEENDEN,
}


def _melde_interviewmodus(tg, conn, e, chat_id: int, wirkliche: list[dict]) -> None:
    """Bestaetigt jeden tatsaechlich wirksamen Moduswechsel einzeln und
    sofort (Aufgabe 5) -- unabhaengig von und vor baue_meldung(), das diese
    beiden Arten weiterhin bewusst still haelt."""
    for aenderung in wirkliche:
        text = _INTERVIEWMODUS_TEXTE.get(aenderung.get("art"))
        if text is None:
            continue
        try:
            message_id = tg.sende(chat_id, text)
            repo.merke_nachricht(
                conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
                text, repo._jetzt(),
            )
        except Exception:
            log.exception(
                "Interviewmodus-Bestaetigung fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, aenderung.get("art"),
            )


def laufe(klm, tg, conn, e, chat_id: int) -> None:
    """Kapselt den ganzen Absichtserkenner-Nachlauf: erkennen, anwenden,
    melden (teil-b.md Aufgabe 4), Interviewmodus bestaetigen (Aufgabe 5).
    Laeuft nachgelagert, nachdem die Bot-Antwort in der Gruppe steht (SPEC
    § 4.3) -- niemand wartet darauf, und ein Fehlschlag bleibt fuer die
    Gruppe unsichtbar, genau wie ``ablauf.antworte`` es fuer den
    Gespraechszug haelt: geloggt und als ``vorfall`` vermerkt, nie eine
    zusaetzliche Fehlermeldung im Chat."""
    try:
        aenderungen = erkenne(klm, conn, e, chat_id)
        if not aenderungen:
            return
        wirkliche = wende_an(conn, e, chat_id, aenderungen)
        _melde_interviewmodus(tg, conn, e, chat_id, wirkliche)
        text = baue_meldung(wirkliche)
        if text is None:
            return
        message_id = tg.sende(chat_id, text)
        # Wie ablauf.antworte: die gesendete Meldung wird als Bot-Nachricht
        # mitgeschrieben, damit sie im naechsten Verlaufsfenster steht.
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Erkenner-Nachlauf fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "erkenner_nachlauf_fehler",
            "Erkenner-Nachlauf (anwenden/melden) fehlgeschlagen",
        )

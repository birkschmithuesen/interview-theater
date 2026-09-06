"""Journal-Extraktor (gedaechtnis-extraktion-agenten.md § 6, § 8;
SPEC-kontext-architektur.md § 4.3).

Ergaenzt den Absichtserkenner (``interview_theater/erkenner.py``) um die eine
Kategorie, die ihm bewusst fehlt: ``vorgeschlagen``. Der Erkenner laeuft
zeitnah nach jedem Gespraechszug ueber die letzten paar Nachrichten -- gut
genug, um eine ausdrueckliche Ablehnung oder Festlegung zu erkennen, aber zu
knapp, um zu beurteilen, ob etwas ein ernstgemeinter Vorschlag war oder nur
eine beilaeufige Bemerkung. Das sieht man erst ueber mehrere Redebeitraege
hinweg. Der Journal-Extraktor bekommt deshalb einen ganzen zusammenhaengenden
Gespraechsabschnitt zu sehen -- dafuer darf er gemaechlich sein: er laeuft
nicht bei jedem Zug, sondern nur bei VERDRAENGUNG (siehe
``berechne_verdraengten_abschnitt`` unten).

**Arbeitsteilung gegen Doppeleintraege (die heikelste Stelle hier):** der
Absichtserkenner schreibt weiterhin ``verworfen`` und ``entschieden`` --
daran aendert sich nichts. Der Journal-Extraktor schreibt AUSSCHLIESSLICH
``vorgeschlagen``. Beide schreiben in dieselbe ``journal``-Tabelle
(``repo.schreibe_journal``), aber nie dieselbe Kategorie -- es gibt also
keine Situation, in der beide denselben Sachverhalt in derselben Kategorie
doppelt eintragen koennten. Als zweite Absicherung (Verteidigung in der
Tiefe, falls das Modell oder eine kuenftige Anbieteraenderung trotzdem eine
andere Kategorie liefert) verwirft ``extrahiere()`` unten jede Kategorie
ausser ``vorgeschlagen`` -- genau wie der Erkenner unbekannte ``art``-Werte
verwirft.

**Verdraengung statt Dauerschwelle** (analog Absichtserkenner-Wasserzeichen,
aber mit eigenem Auslaeser): das kurze Fenster, das ``kontext.baue()`` in den
Gespraechs-Prompt gibt, ist ueber ``kontext.fenster_grenzen()`` bemessen.
Waechst der Verlauf weiter, faellt irgendwann ein Abschnitt aus diesem
Fenster -- das ist der Moment, in dem der Extraktor etwas zu tun bekommt.
``berechne_verdraengten_abschnitt()`` fragt dafuer **dieselbe** Funktion, die
den Fensterblock baut (``kontext.waehle_fenster``), statt eine eigene Zahl
danebenzustellen: genau daran ist die Kopplung bis zum 06.09.2026
auseinandergelaufen (Audit-Befund C.3). Sie ist bewusst eine eigenstaendige,
ungebundene Funktion (nicht in ``extrahiere()`` verschachtelt), damit sie
ohne Datenbank und ohne Sprachmodell-Attrappe fuer sich alleine getestet
werden kann.

**Fehlerhaltung wie beim Absichtserkenner** (global-constraints.md
'Fehlerhaltung'): laeuft nachgelagert, niemand wartet darauf. Bei Erfolg
rueckt das Wasserzeichen ``letzte_journalisierte_message_id`` vor -- aber nur
bis zum Ende des tatsaechlich verarbeiteten verdraengten Abschnitts, nicht
bis zum Ende aller unjournalisierten Nachrichten (der Rest steht noch im
Fenster und ist noch nicht verdraengt). Bei Fehlschlag bleibt das
Wasserzeichen stehen, ein ``vorfall`` wird geschrieben, der Gruppe wird
nichts gemeldet. Journaleintraege werden GRUNDSAETZLICH nie in der Gruppe
gemeldet -- ``laufe()`` nimmt deshalb, anders als ``erkenner.laufe()``, gar
kein Telegram-Objekt entgegen: es gibt architektonisch keine Stelle, an der
dieser Code ueberhaupt etwas senden koennte.
"""

import logging

from interview_theater import kontext, repo

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: interview_theater/prompts/journal.md fuer die vollstaendige Anweisung samt der
#: fuenf Few-Shot-Beispiele, davon zwei leer).
from interview_theater import anweisungen


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("journal")

#: Die einzige Kategorie, die dieser Extraktor je schreibt (Arbeitsteilung,
#: siehe Moduldocstring). Als Tupel, nicht als nackter String, damit Schema
#: und Filterlogik unten dieselbe Quelle verwenden und nie auseinanderlaufen
#: koennten -- auch wenn es aktuell nur ein Element ist (vgl. erkenner.ARTEN).
KATEGORIEN = ("vorgeschlagen",)

#: Obergrenze fuer Eintraege je Lauf -- im Prompttext (Regel 8) UND hier im
#: Code durchgesetzt (kein maxItems im Schema, das strikte Modi oft nicht
#: unterstuetzen -- gedaechtnis-extraktion-agenten.md § 4.3).
MAX_EINTRAEGE = 5

#: Sampling-Temperatur, identisch zum Absichtserkenner (SPEC § 4.3a) --
#: niedrig, gegen Formulierungsvarianz und Sprachdrift bei einem
#: mehrsprachigen Modell (gedaechtnis-extraktion-agenten.md § 5.2, § 8).
TEMPERATURE = 0.2

#: Ab dieser geschaetzten Groesse (kontext.schaetze) eines verdraengten
#: Abschnitts lohnt sich ein eigener Modellaufruf. Ohne diese Schwelle
#: wuerde jeder einzelne, winzige Verdraengungsschritt (ein paar Worte) einen
#: eigenen Aufruf ausloesen -- Latenz- und Kostenlast ohne Ertrag, weil ein
#: derart kurzer Ausschnitt so gut wie nie etwas Journalwuerdiges enthaelt.
#:
#: **2.000 -> 600 am 06.09.2026** (Audit, Befund C.3, Auftrag 2). Die 2.000
#: waren gegen ein 8.000-Token-Fenster gesetzt, also gegen ein Viertel davon.
#: Das reale Fenster ist seit dem Umbau rund 4.000 Token gross
#: (``kontext.FENSTER_ZEICHEN`` = 12.000 Zeichen) -- 2.000 waeren die Haelfte
#: des Fensters, und gemessen sprang der Extraktor an Tag 1 in **allen drei**
#: echten Betriebsgruppen **kein einziges Mal** an (Wasserzeichen bei allen
#: auf 0, kein einziger ``extraktor``-Eintrag im Betriebsjournal). 600 Token
#: halten dasselbe Verhaeltnis zum neuen Fenster, das 2.000 zum alten hatten.
SCHWELLE_VERDRAENGUNG = 600

#: Wie viele der zuletzt geschriebenen Journaleintraege dem Prompt als
#: Dedup-Referenz beigelegt werden (gedaechtnis-extraktion-agenten.md § 2.6:
#: "die letzten 10-15", nicht das ganze Journal -- Tokenkosten UND
#: Kontaminationsrisiko, siehe § 2.2c "No Detail Contamination"). Ein Wert
#: aus dieser Spanne, nicht das gemessene Maximum.
LETZTE_JOURNALEINTRAEGE = 12

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften (global-constraints.md § 4). Absichtlich flach:
#: array > object > string, kein eigenes begruendung-/reasoning-Feld (der
#: Grund fuer "vorgeschlagen" gibt es ohnehin nicht, siehe § 2.5 in der
#: Recherche -- ein Feld, das befuellt werden will, ist ein
#: Halluzinationsanreiz).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eintraege"],
    "properties": {
        "eintraege": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kategorie", "text"],
                "properties": {
                    "kategorie": {"type": "string", "enum": list(KATEGORIEN)},
                    "text": {"type": "string"},
                },
            },
        },
    },
}


def berechne_verdraengten_abschnitt(nachrichten: list) -> list:
    """Liefert genau den Abschnitt, der aus dem kurzen Fenster gefallen ist
    -- oder eine leere Liste, wenn entweder noch nichts verdraengt wurde oder
    der verdraengte Teil kleiner als ``SCHWELLE_VERDRAENGUNG`` ist.

    **Die Fenstergrenze kommt aus ``kontext.waehle_fenster()``** -- derselben
    Funktion, die den Fensterblock des Gespraechs-Prompts baut (Audit
    06.09.2026, Befund C.3, Auftrag 2). Vorher rechnete diese Funktion gegen
    ``kontext.BUDGETS["fenster"] = 8000`` Token, waehrend das reale Fenster
    seit dem Fensterumbau ganz anders bemessen war: gemessen hielt sie
    **31 Nachrichten fuer "noch im Fenster"**, waehrend der Prompt nur 20
    sah. Die Nachrichten 21-31 waren aus dem Prompt verschwunden, galten hier
    aber als anwesend -- sie wurden nie journalisiert und standen danach
    nirgends mehr. Ein Loch von elf Nachrichten Breite, das mit jedem Zug
    mitwanderte.

    Zwei Zahlen nebeneinander laufen auseinander, sobald eine davon geaendert
    wird; eine Funktion, die beide lesen, kann das nicht. ``tests/
    test_journal.py`` haelt die Kopplung als Regressionstest fest.

    ``nachrichten`` ist chronologisch aufsteigend (aeltester zuerst) und
    ungefiltert (wie ``repo.unjournalisierte`` sie liefert) -- typischerweise
    alles seit dem Journal-Wasserzeichen. Diese Funktion beruehrt weder die
    Datenbank noch ein Sprachmodell und laesst sich deshalb ohne beides
    testen."""
    if not nachrichten:
        return []

    im_fenster = kontext.waehle_fenster(nachrichten)
    # Identitaet, nicht Gleichheit: zwei Nachrichten koennen denselben Text
    # tragen (ein "ja" ist haeufig), und ``sqlite3.Row`` ist nicht hashbar.
    im_fenster_ids = {id(n) for n in im_fenster}
    verdraengt = [n for n in nachrichten if id(n) not in im_fenster_ids]
    if not verdraengt:
        return []

    text = "\n".join(kontext.sprecherzeile(n) for n in verdraengt)
    if kontext.schaetze(text) <= SCHWELLE_VERDRAENGUNG:
        return []
    return verdraengt


def _bisheriges_journal_text(conn, chat_id: int) -> str:
    """Formatiert die letzten LETZTE_JOURNALEINTRAEGE Eintraege -- nicht das
    ganze Journal (Tokenkosten und Kontaminationsrisiko, siehe
    Moduldocstring). Nur zur Dedup-Erkennung gedacht: der Prompt (Regel 7)
    verbietet ausdruecklich, etwas von hier in einen neuen Eintrag zu
    uebernehmen."""
    eintraege = repo.journal(conn, chat_id)[-LETZTE_JOURNALEINTRAEGE:]
    if not eintraege:
        return ""
    zeilen = [f"- [{e['art']}] {e['text']}" for e in eintraege]
    return "Bisheriges Journal:\n" + "\n".join(zeilen)


def _ausschnitt_text(verdraengt) -> str:
    zeilen = [kontext.sprecherzeile(n) for n in verdraengt]
    return "Ausschnitt:\n" + "\n".join(zeilen)


def _baue_nutzertext(conn, chat_id: int, verdraengt) -> str:
    """Baut den Nutzertext des Extraktoraufrufs: die letzten Journaleintraege
    (Dedup-Referenz) plus GENAU der verdraengte Abschnitt -- nie das ganze
    Gespraech, nie das ganze Journal."""
    bloecke = [b for b in (_bisheriges_journal_text(conn, chat_id), _ausschnitt_text(verdraengt)) if b]
    return "\n\n".join(bloecke)


def extrahiere(klm, conn, e, chat_id: int) -> list[dict]:
    """Erkennt Vorschlaege im gerade verdraengten Gespraechsabschnitt und
    schreibt sie sofort ins Journal (anders als beim Absichtserkenner gibt es
    hier keinen getrennten ``wende_an``-Schritt: jeder erkannte Vorschlag ist
    schlicht ein neuer, angehaengter Journaleintrag, keine Ueberschreib- oder
    Dublettenpruefung noetig).

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art, modell=None, temperature=None) -> dict``-Methode (in
    Produktion ``interview_theater.llm.LLM``, in Tests eine Attrappe).

    Liefert die geschriebenen Eintraege als ``{"kategorie": "vorgeschlagen",
    "text": ...}``-Dicts, hoechstens ``MAX_EINTRAEGE`` lang. Leere Liste ist
    der Normalfall (kein Vorschlag im Abschnitt, oder noch nichts
    verdraengt) -- kein Fehler."""
    nachrichten = repo.unjournalisierte(conn, chat_id)
    if not nachrichten:
        return []

    verdraengt = berechne_verdraengten_abschnitt(nachrichten)
    if not verdraengt:
        # Noch nichts (Genuegendes) aus dem Fenster gefallen -- das
        # Wasserzeichen bleibt stehen, der naechste Zug prueft erneut mit
        # dann mehr angesammeltem Material.
        return []

    letzte_message_id = max(n["message_id"] for n in verdraengt)
    nutzer = _baue_nutzertext(conn, chat_id, verdraengt)

    try:
        ergebnis = klm.schema(
            chat_id, prompt(), nutzer, SCHEMA, "journal",
            modell=e.erkenner_modell, temperature=TEMPERATURE,
        )
    except Exception:
        # Fehlschlag: das Wasserzeichen bleibt STEHEN -- ein kostenloser
        # Wiederholungsversuch beim naechsten Verdraengungslauf. Der Gruppe
        # wird nichts gemeldet (global-constraints.md 'Fehlerhaltung';
        # Journaleintraege werden ohnehin nie gemeldet, siehe Moduldocstring).
        log.exception("Journal-Extraktion fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "journal_extraktor_fehler",
            "Journal-Extraktor-Aufruf fehlgeschlagen",
        )
        return []

    eintraege = []
    for eintrag in ergebnis.get("eintraege", []):
        kategorie = eintrag.get("kategorie")
        if kategorie not in KATEGORIEN:
            # Arbeitsteilung, verteidigt in der Tiefe: verworfen/entschieden
            # sind Sache des Absichtserkenners. Kaeme trotzdem eine solche
            # Kategorie zurueck (Testattrappe oder ein kuenftiger
            # Anbieterwechsel), landet sie hier NICHT im Journal.
            continue
        text = (eintrag.get("text") or "").strip()
        if not text:
            continue
        eintraege.append({"kategorie": kategorie, "text": text})
        if len(eintraege) >= MAX_EINTRAEGE:
            break

    for eintrag in eintraege:
        repo.schreibe_journal(
            conn, chat_id, eintrag["kategorie"], eintrag["text"],
            quelle="extraktor", bis_message_id=letzte_message_id,
        )

    repo.setze_journalisiert_bis(conn, chat_id, letzte_message_id)
    return eintraege


def laufe(klm, conn, e, chat_id: int) -> None:
    """Kapselt den ganzen Journal-Extraktor-Nachlauf fuer den Aufrufer aus
    dem Hintergrund-Pool -- analog ``erkenner.laufe()``, aber ohne
    Telegram-Parameter: Journaleintraege werden nie in der Gruppe gemeldet,
    also gibt es hier architektonisch nichts zu senden.

    ``extrahiere()`` faengt Sprachmodell-Fehlschlaege bereits selbst ab; der
    try/except hier ist die zweite Sicherheitsnetz-Ebene (analog
    ``erkenner.laufe``), falls z. B. das Schreiben ins Journal selbst
    scheitert -- auch das darf den Hintergrund-Pool nie mitreissen."""
    try:
        extrahiere(klm, conn, e, chat_id)
    except Exception:
        log.exception("Journal-Extraktor-Nachlauf fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "journal_nachlauf_fehler",
            "Journal-Extraktor-Nachlauf fehlgeschlagen",
        )

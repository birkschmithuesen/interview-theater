"""Findet deutsche Saetze in allem, was ein Profil erzeugt (Karte A1, D10).

Die Abnahme (3) der Karte: mit ``padua-2026`` enthaelt **kein** Chat-,
Knopf- oder Prompttext mehr einen deutschen Satz -- mechanisch geprueft,
nicht gelesen. Positivkontrolle: gegen ``dortmund-2026`` muss der Pruefer
anschlagen, sonst prueft er nichts.

Zwei Signale, casefold, an Wortgrenzen:

* ``STOPPWOERTER`` -- deutsche Funktionswoerter, die weder englisch noch
  italienisch sind,
* ``UI_WOERTER`` -- deutsche Inhaltswoerter aus Knopf- und Systemzeilen
  ("Ja, speichern", "Notiert:"), die kein Funktionswort tragen (W2),

dazu Umlaute/ß und die grossgeschriebenen deutschen Formnamen
(``FORMANZEIGE_DE``) als eigene Signale. Ausgenommen: Protokoll-Token
(Woerter nur aus Grossbuchstaben, snake_case, ``{…}``/``{{…}}``-Platzhalter,
Slash-Befehlssyntax, Feldnamen in Backticks aus ``FELDNAMEN_IN_BACKTICKS``)
und ``ERLAUBT`` (Formnamen als Datenbankwerte, Stil-Slugs, erfundene Namen).

Der Profilmodus (Aufgabe 30, W3, W11) rendert unter dem Profil fuenf
Quellen: (a) ``prompts`` -- jeder Prompt-Abschnitt wie
``scripts/prompt_schnappschuss``; (b) ``texte`` -- jeder Schluessel der
englischen Tabelle ueber ``sprache.text``; (c) ``durchlauf`` -- ein
skriptierter Workshop gegen Telegram- und LLM-Attrappe (gesendete Texte,
Knopfbeschriftungen, Einblendungen, Befehlsmenue); (c2) ``modellprompts``
-- System UND Nutzer jedes Aufrufs, den die LLM-Attrappe dabei bekam; (d)
``web`` -- Gruppenseite, Probenansicht, Leitfaden als lesbarer Text. Kein
Netz, keine Betriebsdatenbank.

Aufruf::

    python -m scripts.pruefe_sprache --dateien <pfad> [<pfad> ...]
    python -m scripts.pruefe_sprache --schluessel <modul>[,<modul> ...]
    python -m scripts.pruefe_sprache <profil> [--quelle prompts,texte,durchlauf,modellprompts,web]

Exit 0 nur ohne Treffer.
"""

import argparse
import contextlib
import os
import re
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from interview_theater.dramaturgie.fanout import A10_FELDER, A11_FELDER
from interview_theater.repo import FESTLEGUNG_BEREICHE

#: Deutsche Funktionswoerter (Brief D10) plus einige, die in Knopftexten
#: tragen. Keins davon ist ein englisches oder italienisches Wort.
STOPPWOERTER = frozenset({
    "und", "nicht", "ist", "ihr", "euch", "wir", "ich", "mit", "fuer", "für",
    "auf", "eine", "einen", "noch", "schon", "auch", "oder", "wenn", "dass",
    "sich", "werden", "bitte", "jetzt", "hier", "sind", "habt", "eure",
    "euer", "uns", "kein", "keine", "nichts", "dann", "weil", "aber", "zum",
    "zur", "beim", "ueber", "über", "wird", "seid", "wollt", "koennt",
    "könnt", "sagt", "mir", "dir", "du", "dein", "deine",
    # Aufgabe 30 (offener Punkt aus dem Review zu Aufgabe 17): gemessen
    # rutschte "Der Weg dahin" durch. Bewusst NICHT "die" (englisch "to
    # die"), "den" (englisch "den"), "was", "so", "im" (aus "I'm").
    "der", "das", "dem", "ein", "einem", "einer", "eines", "dahin", "dort",
    "nur", "sehr", "wie", "nach", "bei", "vom", "diese", "dieser", "dieses",
})

#: Deutsche Inhaltswoerter aus Knopf- und Systemzeilen, die ohne
#: Funktionswort stehen (W2). Kuratiert aus knoepfe/texte.py, befehle.py,
#: aufnahme.py, erkenner.baue_meldung und web.py; keins ist ein englisches
#: Wort.
UI_WOERTER = frozenset({
    "ja", "nein", "speichern", "gespeichert", "notiert", "weiter", "zurueck",
    "zurück", "fertig", "aufnahme", "aufnahmen", "auswerten", "ausgewertet",
    "begriffe", "fragen", "figur", "figuren", "szene", "szenen", "geschichte",
    "kurzgeschichte", "textbuch", "fassung", "fassungen", "leitfaden",
    "eroeffnung", "eröffnung", "abschluss", "einleitung", "einleitungen",
    "verdichtung", "kernthema", "stueck", "stück", "passt", "anders", "neu",
    "schreiben", "zeigen", "ansehen", "kuerzer", "kürzer", "hinweis",
    "schweiz", "bereit", "laeuft", "läuft", "beendet", "gruppe",
    "feinschliff", "schaerfung", "schärfung", "sprechanteile",
    "probenansicht", "arbeitsstand", "festlegung", "festlegungen", "stand",
    "hilfe", "starten", "beenden", "interviewpartnerin", "sprachnachricht",
    "sprachnachrichten", "zusammenfassung", "transkript", "knopf", "knoepfe",
    "knöpfe", "vorschlag", "runde", "entfernt", "zurueckgenommen",
    "zurückgenommen", "uebernommen", "übernommen", "abgeschlossen",
    # Aufgabe 30: Einzelwoerter aus Ueberschriften und Beschriftungen, die
    # gemessen durchrutschten ("struktur", "sonstiges"), und ihre Verwandten.
    "struktur", "sonstiges", "sonstige", "ueberblick", "überblick",
    "beschreibung", "einstellungen", "verlauf", "vorspann", "besetzung",
    "handlung", "sprachstil", "sprachprofil", "kernfrage",
})

#: Feldnamen, die ein Programm aus einer Judge-Antwort liest
#: (``VORSCHLAG: <feld>: <neuer Wert>``) und die ein englischer Prompt deshalb
#: woertlich nennen muss -- aber nur in Backticks (Aufgabe 30, offener Punkt
#: aus Aufgabe 21). Importiert statt kopiert wie ``FESTLEGUNG_BEREICHE``,
#: damit ein neues Feld den Pruefer nicht stillschweigend uebergeht.
#: Ausgenommen ist nur der Name direkt hinter einem Backtick und direkt vor
#: einem Backtick oder Doppelpunkt: `` `geschichte` `` und die Protokollform
#: `` `anlass: <Wert>` `` -- der Wert dahinter wird weiter geprueft. Im
#: Fliesstext bleibt "geschichte" ein Treffer.
FELDNAMEN_IN_BACKTICKS = frozenset(A10_FELDER) | frozenset(A11_FELDER)

#: Woerter, die in englischen Texten legitim stehen: Formnamen als
#: Datenbankwerte (``szene.form``), Stil-Slugs, Profil-Beispielorte (Padua,
#: italienisch), und die Namen der Phasen, soweit sie Protokoll sind.
ERLAUBT = frozenset({
    "dialog", "monolog", "chor", "lied", "rap", "prosa",
    "herkules", "schlagabtausch", "litanei",
    "fermata", "piazza", "bar", "stazione",
    # Formberater (Karte t_256ec777): die drei Schema-Felder des
    # Modellaufrufs (interview_theater/formberater.py, SCHEMA) heissen
    # bewusst wie Birks Brief, nicht uebersetzt -- Protokoll wie
    # "dialog"/"chor" oben, keine Prosa.
    "passt", "vorschlag", "gegenpol",
})

#: Die deutschen ANZEIGE-Namen der Formen, gross geschrieben -- anders als
#: der kleingeschriebene Datenbankwert (``"chor"``, Protokoll, in
#: ``ERLAUBT``) ist "Chor" auf einem Knopf deutscher Text (Aufgabe 30:
#: gemessen standen im Padua-Durchlauf die Formknoepfe "Monolog", "Chor",
#: "Lied"). Gross/klein zaehlt hier, anders als in den Listen oben.
#: "Dialog" und "Rap" fehlen bewusst: beide sind auch englische Woerter.
FORMANZEIGE_DE = frozenset({"Monolog", "Chor", "Lied"})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")
_UMLAUT = re.compile(r"[äöüÄÖÜß]")

#: Formwerte einer Szene (szene.FORMEN, Review Aufgabe 14: "die Formwerte
#: dialog/monolog/chor/lied/rap"). Hier als eigene, statische Kopie und
#: nicht ueber ``szene.FORMEN`` importiert: dieser Wert haengt am aktiven
#: Workshop-Profil (PEP 562, Modul-``__getattr__``), der Pruefer laeuft aber
#: profil-unabhaengig und baut die Regex einmal beim Import.
_FORMWERTE = frozenset({"dialog", "monolog", "chor", "lied", "rap"})

#: Argumentwoerter, die im Text direkt hinter einem Slash-Befehl als Teil
#: der Befehlssyntax gelten (Annahme A4: Befehlsnamen und Argumentwoerter
#: bleiben deutsch, ``/hilfe`` darf sie nennen) und deshalb NICHT als
#: deutscher Flusstext gezaehlt werden. Bewusst eine GESCHLOSSENE Menge
#: (Review zu Aufgabe 14): das fruehere Muster liess JEDES kleingeschriebene
#: Wort hinter einem Befehl als Argument durchgehen und verschluckte damit
#: ganze Saetze -- gemessen: "Tippt /aufnahme und dann sprecht ihr los."
#: und "/hilfe zeigt dir alles, was geht" ergaben 0 Treffer statt "ihr"
#: bzw. "dir". Jedes Wort unten ist am Code von ``befehle.py`` ermittelt,
#: nicht geraten:
#:   "aus"                    -- ``rest.lower() == "aus"`` in
#:                                _befehl_stueck/_befehl_kernthema/
#:                                _befehl_wortlaut
#:   "rahmen", "format"       -- Schluessel von ``befehle._STUECK_FELDER``
#:   "entfernen", "entferne",
#:   "loeschen", "löschen",
#:   "weg", "raus"            -- ``befehle._ENTFERNEN_WOERTER``
#:                                (``/figur <name> entfernen``,
#:                                ``/festlegung weg <suchwort>``)
#:   "ort", "zeit", "anlass",
#:   "figuren", "form"        -- Szenenfelder aus ``szene.FELD_ALIASE``, ueber
#:                                ``befehle._setze_szenenfeld`` geparst
#:                                (``/szene <n> ort|zeit|anlass|figuren
#:                                <text>``, ``/szene <n> form <...>``)
#:   "usa", "ja", "j", "yes",
#:   "nein", "n", "no"        -- ``befehle._SZENE_USA``/``_SZENE_USA_LEER``
#:                                (``/szene usa ja|nein``)
#:   "auto"                   -- ``befehle._SPRACHWERT`` (``/sprache auto``)
#:   "off", "setting",
#:   "remove", "delete",
#:   "drop", "out"            -- die englischen Argumentwoerter aus Aufgabe 22
#:                                (``befehle._AUS``, ``_STUECK_SYNONYME_EN``,
#:                                ``_ENTFERNEN_WOERTER_EN``, ``_FESTLEGUNG_WEG_EN``);
#:                                geschlossen mitgefuehrt, damit ein englischer
#:                                Text sie als Befehlssyntax nennen darf
#: Dazu die fuenf Formwerte (oben) und die Festlegungsbereiche aus
#: ``repo.FESTLEGUNG_BEREICHE`` -- importiert statt dupliziert, damit ein
#: neuer Bereich den Pruefer nicht stillschweigend uebergeht.
ARGUMENTWOERTER = frozenset({
    "aus", "rahmen", "format",
    "entfernen", "entferne", "loeschen", "löschen", "weg", "raus",
    "ort", "zeit", "anlass", "figuren", "form",
    "usa", "ja", "j", "yes", "nein", "n", "no",
    "auto",
    "off", "setting", "remove", "delete", "drop", "out",
}) | _FORMWERTE | frozenset(FESTLEGUNG_BEREICHE)

#: Laengstes Wort zuerst, damit z. B. "figuren" vor "figur" probiert wird
#: (nur fuer Lesbarkeit/Effizienz -- die Regex-Engine backtrackt ohnehin
#: ueber die Alternation, siehe Wortgrenzen-Lookahead unten).
_ARGWORT = "|".join(re.escape(w) for w in sorted(ARGUMENTWOERTER, key=len, reverse=True))
_FELDNAME_BT = "|".join(re.escape(w) for w in sorted(FELDNAMEN_IN_BACKTICKS, key=len, reverse=True))

#: Was vor dem Pruefen herausgenommen wird: Platzhalter, snake_case-Namen
#: (Erkenner-Arten, JSON-Schluessel, Feldnamen), Woerter nur aus
#: Grossbuchstaben (Protokoll-Marker wie VORSCHLAG FRAGENAUSWAHL:, BEFUND:),
#: URLs und Dateipfade. Dazu die Syntax eines Slash-Befehls (Annahme A4:
#: Befehlsnamen und Argumentwoerter bleiben deutsch, ``/hilfe`` darf sie
#: nennen): der Name samt direkt folgender Argumente aus ``ARGUMENTWOERTER``,
#: ``a|b``-Alternativen daraus und ``<…>``/``[…]``-Platzhalter (deren Inhalt
#: bleibt ungeprueft -- er ist per Definition Beispieltext, kein Flusstext).
#: Grenze, bewusst: nur ein Wort aus der geschlossenen Menge direkt hinter
#: einem Befehl gilt als Argument, kein beliebiges kleingeschriebenes Wort
#: (Review Aufgabe 14) -- sonst verschluckt die Regex den ganzen Satz danach.
_AUSSEN_VOR = re.compile(
    r"(?<![\w/])/[a-z]+(?:[ ]+(?:<[^<>\n]*>|\[[^\[\]\n]*\]|"
    rf"(?:{_ARGWORT})(?:\|(?:{_ARGWORT}))*)(?![\w]))*"
    rf"|(?<=`)(?:{_FELDNAME_BT})(?=`|:)"
    r"|\{\{[a-z0-9_]+\}\}|\{[A-Za-z0-9_!:>< .]*\}"
    r"|\b[a-z]+(?:_[a-z0-9]+)+\b"
    r"|\b[A-ZÄÖÜ]{2,}(?:[ _][A-ZÄÖÜ]{2,})*\b"
    r"|https?://\S+|\b[\w./-]+\.(?:md|toml|py|txt|json|jsonl)\b"
)


@dataclass(frozen=True)
class Treffer:
    quelle: str
    wort: str
    ausschnitt: str


def deutsche_treffer(quelle: str, text: str) -> list[Treffer]:
    """Jedes deutsche Signal in ``text``, mit Ausschnitt."""
    gesaeubert = _AUSSEN_VOR.sub(lambda t: " " * len(t.group(0)), text or "")
    treffer = []
    for wort in _WORT.finditer(gesaeubert):
        roh = wort.group(0)
        klein = roh.casefold()
        if roh in FORMANZEIGE_DE:
            zeichen = roh
        elif klein in ERLAUBT:
            continue
        elif klein in STOPPWOERTER or klein in UI_WOERTER:
            zeichen = klein
        elif _UMLAUT.search(roh):
            zeichen = _UMLAUT.search(roh).group(0)
        else:
            continue
        anfang = max(0, wort.start() - 30)
        ausschnitt = " ".join(text[anfang:wort.end() + 30].split())
        treffer.append(Treffer(quelle, zeichen, ausschnitt))
    return treffer


_SKRIPT_STIL = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def nur_text(html: str) -> str:
    """Der lesbare Text einer HTML-Seite: ohne ``<script>``/``<style>``, ohne
    Tags, Entitaeten dekodiert -- geprueft wird, was man liest, nicht CSS
    und JavaScript (Aufgabe 17)."""
    import html as html_modul

    ohne = _SKRIPT_STIL.sub(" ", html or "")
    return html_modul.unescape(_TAG.sub(" ", ohne))


def pruefe_dateien(pfade: list[Path]) -> list[Treffer]:
    treffer = []
    for pfad in pfade:
        treffer += deutsche_treffer(str(pfad), Path(pfad).read_text(encoding="utf-8"))
    return treffer


def _blaetter(wert, pfad: str):
    if isinstance(wert, str):
        yield pfad, wert
    elif isinstance(wert, dict):
        for k, v in wert.items():
            if k in ("slug", "command"):
                continue
            yield from _blaetter(v, f"{pfad}.{k}")
    elif isinstance(wert, (list, tuple)):
        for i, v in enumerate(wert):
            yield from _blaetter(v, f"{pfad}[{i}]")


def pruefe_schluessel(module: list[str], sprachcode: str = "en") -> list[Treffer]:
    """Die Werte der Tabelle fuer ``module`` (leer = alle) -- genau das, was
    ``sprache.text`` zur Laufzeit liefert. Schluessel werden nicht geprueft:
    Beschriftungstabellen (K4) haben deutsche Schluessel."""
    from interview_theater import sprache

    sprache.vergiss()
    tabelle = sprache.tabelle(sprachcode)
    treffer = []
    for modul in module or sorted(tabelle):
        for name, wert in tabelle.get(modul, {}).items():
            for pfad, text in _blaetter(wert, f"{modul}.{name}"):
                treffer += deutsche_treffer(pfad, text)
    return treffer


# -- Aufgabe 30: der Render-Pruefer (Abnahme 3, D10, W3, W11) ----------------


@contextlib.contextmanager
def _profil(name: str):
    """Haengt ein Profil ein wie scripts/pruefe_profil.pruefe_namen und
    stellt die Umgebung danach wieder her."""
    from interview_theater import anweisungen, sprache, workshop

    vorher = os.environ.get(workshop.VARIABLE)
    os.environ[workshop.VARIABLE] = name
    workshop.vergiss(); sprache.vergiss(); anweisungen._CACHE.clear()
    try:
        yield
    finally:
        if vorher is None:
            os.environ.pop(workshop.VARIABLE, None)
        else:
            os.environ[workshop.VARIABLE] = vorher
        workshop.vergiss(); sprache.vergiss(); anweisungen._CACHE.clear()


def _quelle_prompts() -> list[tuple[str, str]]:
    """(a) Jeder Prompt-Abschnitt, wie ``scripts/prompt_schnappschuss`` ihn
    unter dem aktiven Profil rendert."""
    from scripts import prompt_schnappschuss

    return [(f"prompt {name}", text) for name, text in prompt_schnappschuss.teile()]


def _quelle_texte() -> list[tuple[str, str]]:
    """(b) Jeder Schluessel der englischen Tabelle, geliefert ueber
    sprache.text -- also genau das, was der Code unter DIESEM Profil sieht
    (Dortmund: die deutsche Konstante)."""
    import importlib

    from interview_theater import sprache

    fertig = []
    for modul, eintraege in sprache.tabelle("en").items():
        importlib.import_module(f"interview_theater.{modul}")
        for name in eintraege:
            wert = sprache.text(f"interview_theater.{modul}", name)
            for pfad, text in _blaetter(wert, f"{modul}.{name}"):
                fertig.append((pfad, text))
    return fertig


ANTWORT_EN = "Here is a short answer in plain English for the group."


def _minimal(schema: dict):
    """Eine gueltige Minimalantwort zu einem JSON-Schema -- die Attrappe
    braucht keine Fachlogik, nur Form."""
    if "enum" in schema:
        return schema["enum"][0]
    typ = schema.get("type")
    if isinstance(typ, list):
        typ = next((t for t in typ if t != "null"), None)
    if typ == "object":
        pflicht = schema.get("required", [])
        return {k: _minimal(v) for k, v in schema.get("properties", {}).items() if k in pflicht}
    if typ == "array":
        return []
    if typ in ("integer", "number"):
        return 1
    if typ == "boolean":
        return False
    return ANTWORT_EN


class LLMAttrappe:
    """Zeichnet jeden Prompt auf (Quelle c2, W3: System UND Nutzer) und
    antwortet in Minimalform."""

    def __init__(self):
        self.aufgezeichnet: list[tuple[str, str, str]] = []
        self._sperre = threading.Lock()

    def _merke(self, art, system, nutzer):
        with self._sperre:
            self.aufgezeichnet.append((art, system, nutzer))

    def schema(self, chat_id, system, nutzer, schema, art, **_kw):
        self._merke(art, system, nutzer)
        if art == "gespraech":
            # Mit einem Vorschlagsblock, damit die Grundleiste
            # ("Ja, speichern" / "Nein, nochmal aendern") im Durchlauf steht.
            return {"antwort": ANTWORT_EN + "\n\nVORSCHLAG RAHMEN:\nA bus stop at night, in the rain."}
        return _minimal(schema)

    def prosa(self, chat_id, system, nutzer, art, **_kw):
        self._merke(art, system, nutzer)
        if art == "geschichte":
            return ("Three directions for the play.\n\nVORSCHLAG GESCHICHTE:\n"
                    "The last bus — Nadia leaves on the last bus.\n"
                    "One more night — She stays one more night.\n"
                    "Until dawn — They argue until the sun comes up.")
        if art == "szenenfolge":
            return ("A scene sequence.\n\nVORSCHLAG SZENENFOLGE:\n"
                    "Last bus — Nadia says she is leaving — Nadia, Tomas — dialog — they talk\n"
                    "One more night — She stays — Nadia, Tomas — dialog — they talk")
        if art == "szenenfelder":
            return ("A proposal for this scene.\n\nVORSCHLAG SZENE:\n"
                    "ort: the bus stop\nwas_passiert: Nadia says she is leaving.")
        if art == "kurzgeschichte":
            return ("SECTION 1: Last bus\nNadia waits. Tomas does not.\nSummary: They wait.\n\n"
                    "SECTION 2: One more night\nThe bus comes. She stays.\nSummary: She stays.")
        return ("TITLE: Night\nSHORT: Two wait.\nSUMMARY: They wait.\n"
                "DONE DIFFERENTLY: nothing\n\nNADIA: The bus is late.\nTOMAS: It always is.")


def _warte_auf_threads(vorher: set, sekunden: float = 10.0) -> None:
    """Wartet auf jeden Thread, der seit ``vorher`` entstanden ist -- auch
    auf Daemon-Threads: die Laeufe des Bots (Verdichtung, Schaerfung,
    Kurzgeschichte) sind Daemons und schreiben ueber dieselbe Verbindung,
    die der Durchlauf am Ende schliesst (sonst gemessen: Segfault in
    sqlite3, weil ein Lauf nach ``conn.close()`` noch schrieb)."""
    for t in threading.enumerate():
        if t in vorher or t is threading.current_thread():
            continue
        t.join(sekunden)


def _durchlauf() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(c) und (c2): ein skriptierter Workshop gegen Attrappen --
    Begruessung, Befehle, Aufnahme per Textimport samt Verdichtung,
    Phaseneintritte 1-7, jeder angebotene Knopf einmal. Kein Netz, keine
    Betriebsdatenbank."""
    from interview_theater import (aufnahme, befehle, bot, db, einstellungen, knoepfe,
                                   repo, sprachprofil, szene, szene_claude, szenenfolge)
    from simulation.attrappe import TelegramAttrappe
    from tests.fixture_sprache import ABSENDER as ABSENDER_EN
    from tests.fixture_sprache import _zeit as _zeitpunkt
    from tests.fixture_sprache import baue_englische_gruppe

    with tempfile.TemporaryDirectory(prefix="a1-sprache-") as verz:
        e = einstellungen.Einstellungen(
            bot_token="T", bot_name="gruppe1", db_pfad=f"{verz}/t.db",
            audio_verz=f"{verz}/audio", llm_url="https://llm.invalid/v1/chat/completions",
            llm_key="K", llm_modell="kimi", stt_basis="https://stt.invalid",
            stt_produkt="P", web_url="https://web.invalid/theater", erkenner_modell="gemma",
        )
        conn = db.verbinde(e.db_pfad)
        db.initialisiere(conn)
        baue_englische_gruppe(conn)
        tg, klm = TelegramAttrappe(), LLMAttrappe()
        original = szene_claude.ist_aktiv
        szene_claude.ist_aktiv = lambda *a, **k: False   # kein Weg ins Netz
        vorher = set(threading.enumerate())
        try:
            bot.erstkontakt(conn, tg, e, 1)
            for befehl in ("/hilfe", "/stand", "/sprache", "/leitfaden", "/phase"):
                befehle.behandle(conn, tg, e, 1, befehl, None, klm=klm)
            befehle.behandle(conn, tg, e, 1, "/aufnahme", None, klm=klm)
            aufnahme_id = aufnahme.importiere_text(
                conn, e, 1, 900, "Allora, home is the smell of bread. " * 20)
            aufnahme.verarbeite(conn, tg, klm, e, None, aufnahme_id)
            _warte_auf_threads(vorher)
            befehle.behandle(conn, tg, e, 1, "/aufnahme", None, klm=klm)
            _warte_auf_threads(vorher)
            # Ein Gespraechszug samt Erkenner und Journal-Extraktor (W3: deren
            # Nutzertexte haben eigene Koepfe). Genug Verlauf, dass das
            # Fenster (kontext.FENSTER_ZEICHEN) Nachrichten verdraengt --
            # sonst liefe der Journal-Extraktor gar nicht.
            for i in range(50):
                repo.merke_nachricht(
                    conn, 1, 500 + i, ABSENDER_EN[i % len(ABSENDER_EN)], 0, "text",
                    f"Round {i}: " + "the bus stop is cold and the light keeps flickering. " * 6,
                    _zeitpunkt(300 + i))
            bot._zug_und_erkenner(conn, tg, klm, e, 1)
            _warte_auf_threads(vorher)
            for phase in range(1, 8):
                repo.setze_phase(conn, 1, phase)
                knoepfe.eintritt_in_phase(conn, tg, klm, e, 1, phase)
                _warte_auf_threads(vorher)
                if phase == 4:
                    szenenfolge.starte_geschichte(conn, tg, klm, e, 1)
                    _warte_auf_threads(vorher)
            # Sprachprofil und ein Szenenlauf (Feinschliff): Figuren an das
            # Interview gebunden, Szene 1 vollstaendig geplant -- sonst
            # sperrt szene.sperrtext vor dem Aufruf, und der Szenen-Prompt
            # (CONTINUITY_KOPF u. a.) bliebe ungeprueft.
            figuren = repo.figuren(conn, 1)
            for figur in figuren:
                repo.setze_figur_quelle(conn, figur["id"], aufnahme_id)
            sprachprofil.starte(conn, tg, klm, e, 1, [f["id"] for f in figuren])
            _warte_auf_threads(vorher)
            erste = next(s for s in repo.hole_szenen(conn, 1) if s["nummer"] == 1)
            for feld, wert in (("form", "dialog"), ("ort", "the bus stop"),
                               ("was_passiert", "Nadia says she is leaving.")):
                repo.setze_szenenfeld(conn, erste["id"], feld, wert)
            repo.setze_szene_figuren(conn, 1, erste["id"], [f["id"] for f in figuren])
            szene.starte(conn, tg, klm, e, 1, "Write scene 1.")
            _warte_auf_threads(vorher)
            gedrueckt: set[str] = set()
            je_beschriftung: dict[str, int] = {}
            for _ in range(200):
                offen = [k for k in tg.offene_knoepfe() if k["daten"] not in gedrueckt
                         and je_beschriftung.get(k["beschriftung"], 0) < 3]
                if not offen:
                    break
                knopf = offen[0]
                gedrueckt.add(knopf["daten"])
                je_beschriftung[knopf["beschriftung"]] = je_beschriftung.get(knopf["beschriftung"], 0) + 1
                knoepfe.behandle(conn, tg, klm, e, {
                    "callback_query_id": "q", "data": knopf["daten"],
                    "chat_id": 1, "message_id": knopf["message_id"]})
                _warte_auf_threads(vorher)
        finally:
            _warte_auf_threads(vorher, 60.0)
            szene_claude.ist_aktiv = original
            conn.close()
    gesendet = [("chat", n["text"]) for n in tg.gesendet]
    gesendet += [("knopf", b) for leiste in tg.knoepfe for b, _ in leiste["knoepfe"]]
    gesendet += [("knopf", b) for _, _, leiste in tg.knoepfe_aktualisiert for b, _ in leiste]
    gesendet += [("einblendung", text) for _, text in tg.beantwortet if text]
    gesendet += [("menue", b["description"]) for b in befehle.T.BEFEHLE_LISTE]
    modell = [(f"{art} system", s) for art, s, _ in klm.aufgezeichnet]
    modell += [(f"{art} nutzer", n) for art, _, n in klm.aufgezeichnet]
    return gesendet, modell


def _quelle_web() -> list[tuple[str, str]]:
    """(d) Gruppenseite, Probenansicht und Leitfaden der Fixture-Gruppe, als
    lesbarer Text (``nur_text``)."""
    from interview_theater import db, web, web_daten
    from tests.fixture_sprache import baue_englische_gruppe

    with tempfile.TemporaryDirectory(prefix="a1-web-") as verz:
        pfad = f"{verz}/web.db"
        conn = db.verbinde(pfad)
        db.initialisiere(conn)
        token = baue_englische_gruppe(conn)
        conn.close()
        lesend = web_daten.oeffne_lesend(pfad)
        try:
            daten = web_daten.gruppe_nach_token(lesend, token)
            leitfaden = web_daten.leitfaden_nach_token(lesend, token)
        finally:
            lesend.close()
    return [
        ("web gruppe", nur_text(web.gruppe_html(daten, web.nonce(b"k", token), token))),
        ("web textbuch", nur_text(web.textbuch_html(daten, token))),
        ("web leitfaden", nur_text(web.leitfaden_html(leitfaden | {"token": token}))),
    ]


#: Die Quellen in der Reihenfolge der Karte: (a) Prompts, (b) Tabelle,
#: (c) Probedurchlauf, (c2) Modellprompts, (d) Gruppenseite.
QUELLEN = ("prompts", "texte", "durchlauf", "modellprompts", "web")


def quellen(profil: str) -> dict[str, list[tuple[str, str]]]:
    with _profil(profil):
        durchlauf, modell = _durchlauf()
        return {
            "prompts": _quelle_prompts(),
            "texte": _quelle_texte(),
            "durchlauf": durchlauf,
            "modellprompts": modell,
            "web": _quelle_web(),
        }


def pruefe_profil(profil: str, nur: set[str] | None = None) -> list[Treffer]:
    treffer = []
    for name, liste in quellen(profil).items():
        if nur and name not in nur:
            continue
        for quelle, text in liste:
            treffer += deutsche_treffer(f"{name} | {quelle}", text)
    return treffer


def _ausgabe(treffer: list[Treffer]) -> int:
    for t in treffer:
        print(f"{t.quelle}: {t.wort!r} in: {t.ausschnitt}")
    print(f"{len(treffer)} Treffer")
    return 1 if treffer else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.pruefe_sprache")
    p.add_argument("profil", nargs="?")
    p.add_argument("--dateien", nargs="+", type=Path)
    p.add_argument("--schluessel")
    p.add_argument("--quelle", help="Kommaliste aus " + ",".join(QUELLEN))
    args = p.parse_args(argv)
    if args.dateien:
        return _ausgabe(pruefe_dateien(args.dateien))
    if args.schluessel is not None:
        module = [m.strip() for m in args.schluessel.split(",") if m.strip()]
        return _ausgabe(pruefe_schluessel(module))
    if args.profil:
        nur = None
        if args.quelle:
            nur = {q.strip() for q in args.quelle.split(",") if q.strip()}
            unbekannt = nur - set(QUELLEN)
            if unbekannt:
                p.error(f"unbekannte Quelle(n): {', '.join(sorted(unbekannt))}")
        return _ausgabe(pruefe_profil(args.profil, nur))
    p.error("--dateien, --schluessel oder ein Profilname")
    return 2


if __name__ == "__main__":
    sys.exit(main())

"""Welcher Modellaufruf in Padua live vorkommt -- und wo sein Dump liegt.

**Warum es diese Liste gibt** (Architekt D2): der Prompt-Check soll nicht
veralten. Ein Test liest den Quelltext aller Modellaufrufe und vergleicht sie
mit dieser Liste; ein neuer Aufruf macht die Suite rot, bis er hier steht oder
mit Grund in ``NICHT_LIVE_IN_PADUA``. Dieselbe Bauart wie
``tests/test_knoepfe_struktur.py``, und aus demselben Grund: eine Tabelle laesst
sich auslesen, eine Kaskade nicht.

``art`` wird im Repo fast immer **positionell** uebergeben. Die Positionen
stehen in ``AUFRUFE`` und sind an den Signaturen gemessen
(``llm.LLM.schema``/``prosa``, ``modellwahl.aufruf_schema``,
``szene_claude.schema``/``prosa``).

**Die Messung** (Task 3, Schritt 1 -- ein Scan von ``interview_theater/**/*.py``
nach ``klm.schema``/``klm.prosa``/``modellwahl.aufruf_schema``/
``szene_claude.schema``/``szene_claude.prosa``/``richter_klm.prosa``) fand 35
Aufrufstellen, die sich zu 22 unterschiedlichen ``(modul, art_quelle)``-Paaren
buendeln -- mehrere Stellen teilen sich oft denselben Prompt (z. B. die sieben
Phasen des Gespraechszugs, oder ein Kimi- und ein Claude-Pfad fuer dieselbe
Sache). ``INVENTAR`` und ``NICHT_LIVE_IN_PADUA`` zusammen decken alle 22 Paare
ab -- das ist die Abschrift dieser Messung, nicht eine Planung davor."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

WURZEL = Path("interview_theater")

#: Aufrufname -> Position des ``art``-Arguments. ``szene_claude`` hat drei
#: Parameter mehr vorn (conn, e, klient) und steht deshalb getrennt.
AUFRUFE = {
    ("klm", "schema"): 4,
    ("klm", "prosa"): 3,
    ("richter_klm", "prosa"): 3,
    ("modellwahl", "aufruf_schema"): 7,
    ("szene_claude", "schema"): 7,
    ("szene_claude", "prosa"): 6,
}


@dataclasses.dataclass(frozen=True)
class Stelle:
    modul: str
    zeile: int
    aufruf: str
    art_quelle: str


@dataclasses.dataclass(frozen=True)
class Eintrag:
    datei: str
    art: str
    phase: int
    modul: str
    art_quelle: str
    weg: str = "abgefangen"
    grund: str = ""


def aufrufstellen(wurzel: Path | None = None) -> list[Stelle]:
    gefunden: list[Stelle] = []
    for datei in sorted((wurzel or WURZEL).rglob("*.py")):
        modul = ".".join(datei.with_suffix("").parts)
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            if not isinstance(knoten.func, ast.Attribute):
                continue
            schluessel = (ast.unparse(knoten.func.value), knoten.func.attr)
            if schluessel not in AUFRUFE:
                continue
            stelle = AUFRUFE[schluessel]
            schluesselwort = next(
                (k.value for k in knoten.keywords if k.arg == "art"), None)
            if schluesselwort is not None:
                quelle = ast.unparse(schluesselwort)
            elif len(knoten.args) > stelle:
                quelle = ast.unparse(knoten.args[stelle])
            else:
                quelle = "?"
            gefunden.append(Stelle(modul, knoten.lineno,
                                   ".".join(schluessel), quelle))
    return gefunden


def abgedeckt() -> set[tuple[str, str]]:
    return ({(e.modul, e.art_quelle) for e in INVENTAR}
            | set(NICHT_LIVE_IN_PADUA))


def offen() -> list[Stelle]:
    bekannt = abgedeckt()
    return [s for s in aufrufstellen() if (s.modul, s.art_quelle) not in bekannt]


def eintrag_fuer(datei: str) -> Eintrag:
    for eintrag in INVENTAR:
        if eintrag.datei == datei:
            return eintrag
    raise KeyError(datei)


#: ------------------------------------------------------------------------
#: Was in Padua live ist. Ein Dump je Zeile. Die vier Namen 01-04 sind die
#: des Vorgaengers (docs/prompt-audit/2026-10-02-padua-p2) und bleiben, damit
#: die Groessen vergleichbar sind (D1).
INVENTAR = (
    # --- Gespraechszug je Phase. EINE Aufrufstelle (ablauf.py:1331 -- plus
    # vier weitere modellwahl.aufruf_schema-Stellen in ablauf.py fuer
    # dieselbe Sache, siehe Messung), sieben Dumps: der Prompt unterscheidet
    # sich nur durch Phase und Datenlage.
    Eintrag("01-gespraech-phase1", "gespraech", 1,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("05-gespraech-phase2", "gespraech", 2,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("06-gespraech-phase3", "gespraech", 3,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("07-gespraech-phase4", "gespraech", 4,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("08-gespraech-phase5", "gespraech", 5,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("02-gespraech-phase6", "gespraech", 6,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("09-gespraech-phase7", "gespraech", 7,
            "interview_theater.ablauf", "'gespraech'"),
    # --- Hintergrundwege
    Eintrag("10-erkenner-verlauf", "erkenner", 4,
            "interview_theater.erkenner", "'erkenner'"),
    Eintrag("11-erkenner-aufnahme", "erkenner", 3,
            "interview_theater.erkenner", "'erkenner'"),
    Eintrag("12-journal", "journal", 4,
            "interview_theater.journal", "'journal'"),
    Eintrag("13-begriffsboard", "begriffsboard", 1,
            "interview_theater.begriffsboard", "ART"),
    Eintrag("14-diskussion-verdichtung", "diskussion_verdichtung", 1,
            "interview_theater.diskussion", "ART"),
    Eintrag("15-fragen-ki", "fragen_ki_vorschlag", 2,
            "interview_theater.fragen_ki", "ART"),
    Eintrag("16-verdichter", "verdichter", 3,
            "interview_theater.verdichter", "'verdichter'"),
    Eintrag("17-buehnenkarte", "brainstorm_karte", 4,
            "interview_theater.buehnenkarte", "'brainstorm_karte'"),
    # --- Phase 4: Szenenfolge, Geschichte, Felder
    Eintrag("18-szenenfolge", "szenenfolge", 4,
            "interview_theater.szenenfolge", "art"),
    Eintrag("19-geschichte", "geschichte", 4,
            "interview_theater.szenenfolge", "art",
            weg="abgefangen", grund=""),
    Eintrag("20-szenenfelder", "szenenfelder", 4,
            "interview_theater.szenenfolge", "art",
            weg="abgefangen", grund=""),
    # --- Phase 5
    Eintrag("21-schaerfung", "schaerfung", 5,
            "interview_theater.schaerfung", "ART"),
    Eintrag("22-entwurf-uebersicht", "entwurf_uebersicht", 5,
            "interview_theater.entwurf", "ART_UEBERSICHT"),
    Eintrag("23-sprachprofil", "sprachprofil", 5,
            "interview_theater.sprachprofil", "ART"),
    Eintrag("24-kernzitate", "kernzitate", 5,
            "interview_theater.kernzitate", "ART"),
    # --- Phase 6
    Eintrag("25-kurzgeschichte", "kurzgeschichte", 6,
            "interview_theater.kurzgeschichte", "art"),
    Eintrag("03-kurzgeschichte-phase6", "kurzgeschichte", 6,
            "interview_theater.kurzgeschichte", "art",
            weg="gebaut",
            grund="Der Kuerzungslauf derselben Stelle (vorlage=True, "
                  "kuerzung.notiz_fuer_prosa) -- Name aus dem Vorgaengerdump."),
    Eintrag("04-szene-prosa-phase6", "szene", 6,
            "interview_theater.szene", "art",
            weg="gebaut",
            grund="szene._lauf baut system=systemanweisung(form, stil) und "
                  "nutzer=baue_nutzertext(...) und uebergibt sie unveraendert "
                  "-- der gebaute Prompt ist zeichengleich (szene.py:2361)."),
    # --- Phase 7: Formen, Sprechweise, Stueckpruefung
    Eintrag("27-sprechweise", "sprechweise", 7,
            "interview_theater.sprechweise", "ART"),
    Eintrag("28-szene-dialog", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 04: der Treiber ruft systemanweisung('dialog') und "
                  "baue_nutzertext; eine Form je Dump."),
    Eintrag("29-szene-monolog", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, derselbe Treiberweg, nur mit Form monolog."),
    Eintrag("30-szene-chor", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, derselbe Treiberweg, nur mit Form chor."),
    Eintrag("31-szene-lied", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, derselbe Treiberweg, nur mit Form lied."),
    Eintrag("32-szene-rap", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, derselbe Treiberweg, nur mit Form rap."),
    # 33-sprachstil entfaellt: kein Live-Eintrag -- siehe NICHT_LIVE_IN_PADUA.
    Eintrag("34-stueckpruefung", "stueckpruefung", 7,
            "interview_theater.stueckpruefung", "ART"),
    # --- Die Richterfragen des Prueflaufs (prueflauf.FRAGEN_*).
    Eintrag("35-dramaturgie-b1", "dramaturgie_b1", 6,
            "interview_theater.dramaturgie.fanout", "art"),
    Eintrag("36-dramaturgie-a2", "dramaturgie_a2", 6,
            "interview_theater.dramaturgie.fanout", "art",
            weg="abgefangen", grund=""),
    # 37-dramaturgie-a6 entfaellt (Task 7, Praezisierung von Task 3): kein
    # Fixture-Inhalt kann einen Aufruf erzeugen. mechanik.tschechow_kandidaten
    # liefert nur im Deutschen je ueberhaupt Kandidaten
    # (mechanik.py: "if sprache.code() != sprache.DEUTSCH: return []"), und
    # Padua laeuft fest auf Englisch (workshop/padua-2026/profil.toml:32,
    # "sprache.code = \"en\""). fanout.pruefe ruft frage_a6 ausschliesslich
    # mit genau diesem (immer leeren) Ergebnis (fanout.py:1328); ohne
    # Kandidaten liefert frage_a6 sofort None, vor jeder Belegpflicht und vor
    # jedem Modellaufruf (fanout.py:1019-1020). Die Aufrufstelle selbst
    # (dramaturgie.fanout, art) bleibt ueber die anderen sechs Fragen
    # abgedeckt -- kein eigener NICHT_LIVE_IN_PADUA-Eintrag noetig.
    Eintrag("38-dramaturgie-a9", "dramaturgie_a9", 6,
            "interview_theater.dramaturgie.fanout", "art",
            weg="abgefangen", grund=""),
    Eintrag("39-dramaturgie-a10", "dramaturgie_a10", 7,
            "interview_theater.dramaturgie.fanout", "art",
            weg="abgefangen", grund=""),
    Eintrag("40-dramaturgie-a11", "dramaturgie_a11", 6,
            "interview_theater.dramaturgie.fanout", "art",
            weg="abgefangen", grund=""),
    Eintrag("41-dramaturgie-c1", "dramaturgie_c1", 7,
            "interview_theater.dramaturgie.fanout", "art",
            weg="abgefangen", grund=""),
)

#: Aufrufstellen, die in Padua NICHT live sind -- mit Grund, nicht nur mit
#: Haken. Schluessel ist ``(modul, art_quelle)``, genau wie der Scanner sie
#: ausgibt.
NICHT_LIVE_IN_PADUA = {
    ("interview_theater.begriffsboard_analyse", "art_fuer(teile)"):
        "Kein Live-Aufrufer -- einziger Aufrufer ist "
        "scripts/rauchtest_begriffsboard_resonanz.py, festgehalten in "
        "tests/test_begriffsboard_analyse.py::test_kein_live_aufrufer. Ob ein "
        "zweiter Live-Aufruf kommt, entscheidet Birk.",
    ("interview_theater.bot", "'erkenner'"):
        "Warmlauf beim Prozessstart (bot.warmlaufen) mit dem festen Text "
        "'Testaufruf.' -- kein Prompt der Gruppe, nichts zu pruefen.",
    ("interview_theater.modellwahl", "art"):
        "Die Rumpfimplementierung von aufruf_schema selbst (modellwahl.py "
        "Zeilen 97 und 117): sie reicht ihr eigenes art-Parameter nur an "
        "szene_claude.schema bzw. klm.schema weiter. Der AST sieht hier den "
        "Parameternamen der eigenen Signatur, nicht den tatsaechlichen Wert "
        "-- der ist an den sieben Aufrufstellen von aufruf_schema bereits "
        "im Inventar (ablauf, begriffsboard, diskussion, entwurf, "
        "fragen_ki, schaerfung, sprechweise). Ein eigener Dump waere "
        "derselbe Prompt noch einmal.",
    ("interview_theater.sprachstil", "ART"):
        "Zirkulaer und ohne Bootstrap live unerreichbar: stelle_stil_vor "
        "(knoepfe/figuren.py, ruft sprachstil.starte) hat im ganzen Repo "
        "genau einen Aufrufer -- _wirkung_figur_stil (knoepfe/wirkung.py), "
        "der Handler des Knopfs ART_FIGUR_STIL. Dieser Knopf wird "
        "ausschliesslich von sende_stil erzeugt, und sende_stil wird "
        "ausschliesslich aus sprachstil.starte selbst heraus gerufen, nach "
        "einem schon erfolgreichen Lauf. Es gibt keine Stelle, die den "
        "allerersten Lauf ohne einen schon gedrueckten Knopf anstoesst "
        "(grep bestaetigt je genau einen Aufrufer). Die Phase-7-Sprechweise "
        "(sprechweise.py, Dump 27) hat die Aufgabe inzwischen uebernommen.",
}

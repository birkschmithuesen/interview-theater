"""Wirkungstest Sprachstil (Padua M1, 30.09.2026): aendert ``figur.sprachstil``
den erzeugten Szenentext?

Messkarte, kein Feature -- `interview_theater/` wird hier nur gelesen und
aufgerufen, nie geaendert. Aufbau angelehnt an ``scripts/szenen_vergleich.py``.

**Der Aufbau.** Je Variante eine eigene Wegwerf-Datenbank (tempfile,
``db.verbinde`` + ``db.initialisiere``) mit demselben erfundenen Arbeitsstand:
Begriffe, Fragen, Setting, Geschichte, drei Figuren (Namen aus
``simulation/interviews/set1/``), eine Szenenfolge aus drei Szenen. Die fuenf
Interviews aus set1 werden per ``aufnahme.importiere_text`` importiert --
das legt die Aufnahme nur bis 'transkribiert' an und ruft den Verdichter
NICHT (siehe Docstring dort), also kein Modellaufruf. Der Prosa-Weg sieht
das Material ohnehin nicht (``szenenfolge._erfundenes``). Sprachprofil und
Zitate der Figuren sind feste Konstanten (Zitate aus den ``zitate_soll`` der
set1-Interviews), in allen Varianten identisch -- kein gemma-Aufruf.

Die Varianten unterscheiden sich allein in ``figur.sprachstil``, gesetzt ueber
``repo.setze_figur_sprachstil``, im Format, das
``knoepfe/wirkung._wirkung_figur_stil`` wirklich speichert: der Knopfwert
aus ``knoepfe/figuren.sende_stil`` ist ``f"{titel}: {beispiel or zitat}"``
-- Titel, Doppelpunkt, Beispielsatz. Drei erfundene Stile (KNAPP, SCHACHTEL,
FUELL), passend zu ``sprachstil_masse.MARKER``:

  A = Figur1 KNAPP, Figur2 SCHACHTEL, Figur3 FUELL
  B = kein Stil
  C = rotiert: Figur1 SCHACHTEL, Figur2 FUELL, Figur3 KNAPP

**Die zwei Wege**, jeweils mit den ECHTEN Prompt-Bauern:

  prosa  Phase 6, ``kurzgeschichte.systemanweisung()`` +
         ``kurzgeschichte.baue_nutzertext(conn, CHAT_ID)`` -- genau der
         Aufruf aus ``kurzgeschichte.starte._lauf`` (ohne Regie-Notiz).
  szene  Phase 7 (Feinschliff), Szene 1 mit Form "Dialog" und fester
         Prosafassung: ``ziel = szene.ziel_fuer(conn, CHAT_ID, auftrag)``,
         ``szene.systemanweisung(ziel["form"], ziel["stil"])`` +
         ``szene.baue_nutzertext(conn, CHAT_ID, auftrag, ziel, e)`` -- genau
         der Weg aus ``szene.schreibe``. ``vorlage`` ergibt sich dort aus
         ``not schreibt_prosa(...)``, in Phase 7 also True: die Prosa steht
         als bindende Vorlage im Prompt.

Unterbefehle: ``pfad`` (Prompts erzeugen, Diffs schreiben, kein Netz).
``lauf`` und ``auswertung`` kommen in Task 3/4 dazu.

Aufruf:
    python -m scripts.sprachstil_wirkung pfad [--ausgabe DIR]
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from interview_theater import aufnahme, db, kurzgeschichte, repo, szene

WURZEL = Path(__file__).resolve().parent.parent
INTERVIEWS = WURZEL / "simulation" / "interviews" / "set1"
AUSGABE = WURZEL / "docs" / "sprachstil-wirkung-2026-09-30"
CHAT_ID = -1000000031
BOT_NAME = "sprachstil-wirkung"

#: Szenenmodell fuer Task 3 (Padua E9): lokaler Anthropic-Proxy, Abo, kein
#: Authorization-Header. Hier nur fuer den Prompt-Bau relevant: mit
#: ``szene_anbieter="claude"`` und Einwilligung "ja" rechnet
#: ``szene.token_budget`` mit dem Claude-Fenster -- wie im echten Lauf.
SZENE_URL = "http://127.0.0.1:28764/v1/messages"
SZENE_MODELL = "claude-opus-5-5"

AUFTRAG_SZENE = "Schreib Szene 1."

# ---------------------------------------------------------------------------
# Der erfundene Arbeitsstand (identisch in allen Varianten)
# ---------------------------------------------------------------------------

BEGRIFFE = "Ankommen, Koffer, Heimweh, Kaelte, Freundschaft"
FRAGEN = "\n".join([
    "Womit bist du gekommen?",
    "Was hast du am ersten Abend gedacht?",
    "Wann hast du gemerkt, dass du bleibst?",
])
RAHMEN = (
    "Die Gemeinschaftskueche eines Frauenwohnheims am Hauptbahnhof, "
    "Winter 1971, die erste Woche nach der Ankunft."
)
GESCHICHTE = (
    "Drei Frauen teilen sich eine Kueche und wissen nicht, ob sie bleiben. "
    "Meryem laesst ihren Koffer gepackt unter dem Bett, Ferzan will sofort "
    "zurueck, Aynur friert und sagt es niemandem. Am Ende pflanzen sie "
    "gemeinsam Tomatensamen in einen Blumenkasten -- keine entscheidet, "
    "ob sie bleibt, aber alle drei giessen."
)

#: (Name, Beschreibung, Sprachprofil, Zitate) -- Zitate woertlich aus den
#: ``zitate_soll`` der set1-Interviews, Profile erfunden.
FIGUREN = [
    (
        "Meryem",
        "haelt den Koffer gepackt, weil sie zurueck will, und raeumt heimlich ein",
        "Mittellange Saetze, viele Neuansaetze, einzelne tuerkische Woerter.",
        [
            "Der Koffer war braun, so ein Braun wie Milchkaffee.",
            "Drei Jahre stand der Koffer unter dem Bett, gepackt.",
        ],
    ),
    (
        "Ferzan",
        "will sofort zurueck und zaehlt die Tage bis zum naechsten Zug",
        "Kurze Saetze mit Selbstkorrekturen, kurdische Einsprengsel.",
        [
            "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
            "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
        ],
    ),
    (
        "Aynur",
        "friert in duennen Stoffschuhen und sagt es niemandem",
        "Abbrueche, kurze Nachschuebe, tuerkische Einsprengsel.",
        [
            "Ich hab gedacht, die Sonne ist kaputt hier.",
            "Die Waesche ist steif geworden auf dem Balkon, wie Bretter.",
        ],
    ),
]

#: (Titel, was_passiert, Besetzung als Namen) je Szene.
SZENEN = [
    (
        "Der Koffer",
        "Meryem schiebt ihren Koffer unters Bett, Ferzan will wissen, warum sie "
        "nicht auspackt. Aynur steht am kalten Herd.",
        ["Meryem", "Ferzan", "Aynur"],
    ),
    (
        "Der Zug",
        "Ferzan zaehlt am Fahrplan die Tage, Meryem haelt sie nicht auf.",
        ["Meryem", "Ferzan"],
    ),
    (
        "Die Samen",
        "Aynur findet Meryems Tomatensamen, die drei pflanzen sie in einen Kasten.",
        ["Meryem", "Ferzan", "Aynur"],
    ),
]

#: Fester Ort/Zeit/Anlass fuer Szene 1 (Pflichtfeld ``ort`` fuer die Sperre).
SZENE_1_FELDER = {
    "ort": "Gemeinschaftskueche des Wohnheims",
    "zeit": "Abend, dritter Tag nach der Ankunft",
    "anlass": "Meryem kommt mit dem Koffer aus dem Keller zurueck",
}

#: Die feste Prosafassung je Szene, wie Phase 6 sie in ``szene.prosa``
#: hinterlaesst -- in allen Varianten identisch. Szene 1 ist die Vorlage des
#: Feinschliffs; Task 3 ersetzt sie durch die Prosa aus einem echten Lauf
#: (``setze_vorlage``).
PROSA = {
    1: (
        "Die Kueche roch nach Gas und nassem Mantel. Meryem schob den braunen "
        "Koffer mit dem Fuss unter das Bett im Nebenraum und kam zurueck, als "
        "haette sie nur die Tuer zugemacht. Ferzan sass am Tisch, den Fahrplan "
        "vor sich, und sah nicht auf. „Du packst nicht aus“, sagte sie. Meryem "
        "zuckte die Schultern. Aynur stand am Herd, die Haende ueber einer "
        "Flamme, die nicht warm machte, und sagte nichts. Draussen fuhr ein Zug "
        "ab, und alle drei hoerten hin."
    ),
    2: (
        "Ferzan strich im Fahrplan die Tage durch. Meryem sah ihr dabei zu und "
        "sagte kein Wort, und das war schlimmer als jedes Wort."
    ),
    3: (
        "Im Taschentuch lagen die Samen, trocken wie Sand. Aynur hielt sie ins "
        "Licht, und zum ersten Mal lachten alle drei."
    ),
}

# ---------------------------------------------------------------------------
# Die drei Stile -- im Format von knoepfe/wirkung._wirkung_figur_stil
# ---------------------------------------------------------------------------

#: ``f"{titel}: {beispiel}"`` -- genau der Wert, den ``sende_stil`` in den
#: Knopf legt und ``_wirkung_figur_stil`` nach dem zweiten TRENNER in
#: ``figur.sprachstil`` schreibt. Titel unter 25 Zeichen (Knopfregel aus
#: ``sprachstil.ANWEISUNG``), Beispielsatz ueber den Kernkonflikt der
#: Geschichte (bleiben oder zurueck). Alles erfunden; die Marker stehen
#: wortgleich in ``sprachstil_masse.MARKER``.
STILE = {
    "KNAPP": "Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter.",
    "SCHACHTEL": (
        "Verschachtelt, gelehrt: Wobei man insofern, als das Zurueckgehen "
        "de facto gar keine Option ist, prinzipiell sagen muesste, dass der "
        "Koffer per se gewissermassen quasi schon ausgepackt ist."
    ),
    "FUELL": (
        "Mit Fuellwoertern: Also, weisst du, der Koffer ist halt irgendwie, "
        "also sozusagen, der Koffer ist halt noch zu, weisst du."
    ),
}

#: Variante -> Stil je Figur (in der Reihenfolge von FIGUREN), None = kein Stil.
VARIANTEN = {
    "A": ["KNAPP", "SCHACHTEL", "FUELL"],
    "B": [None, None, None],
    "C": ["SCHACHTEL", "FUELL", "KNAPP"],
}


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


def einstellungen_szene(url: str = SZENE_URL, modell: str = SZENE_MODELL) -> SimpleNamespace:
    """Das minimale ``e`` fuer den Szenenweg -- ohne ``einstellungen.laden()``,
    das Infomaniak-Variablen verlangen wuerde. Genau die Attribute, die
    ``szene_claude.ist_aktiv``/``prosa`` und ``szene.baue_nutzertext`` lesen."""
    return SimpleNamespace(
        szene_anbieter="claude", szene_url=url, szene_modell=modell,
        bot_name=BOT_NAME,
    )


def _interviewtext(pfad: Path) -> tuple[str, str]:
    """(Name, Transkript) aus einer set1-Datei -- Kopf abgetrennt."""
    roh = pfad.read_text()
    teile = roh.split("\n---\n", 1)
    kopf, koerper = (teile[0], teile[1]) if len(teile) == 2 else ("", roh)
    treffer = re.search(r"^name:\s*(.+)$", kopf, re.M)
    return (treffer.group(1).strip() if treffer else pfad.stem), koerper.strip()


def baue_db(pfad, variante: str, phase: int = 6, e=None):
    """Legt die Wegwerf-DB einer Variante an und liefert die Verbindung.

    ``phase`` 6 ist der Prosa-Weg (Kurzgeschichte), 7 der Feinschliff: dann
    bekommt Szene 1 zusaetzlich die bestaetigte Form "Dialog", und die Gruppe
    hat dem US-Modell zugestimmt (wie im echten Claude-Lauf). Die Prosa je
    Szene steht in beiden Faellen -- in Phase 6 geht sie in keinen Prompt
    (``_erfundenes`` liest nur Titel und was_passiert)."""
    if variante not in VARIANTEN:
        raise ValueError(f"unbekannte Variante: {variante!r}")
    e = e or einstellungen_szene()
    conn = db.verbinde(str(pfad))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT_ID, BOT_NAME, "Sprachstil-Wirkung")
    repo.setze_arbeitsstand(conn, CHAT_ID, "begriffe", BEGRIFFE)
    repo.setze_arbeitsstand(conn, CHAT_ID, "fragen", FRAGEN)
    repo.setze_arbeitsstand(conn, CHAT_ID, "rahmen", RAHMEN)
    repo.setze_arbeitsstand(conn, CHAT_ID, "geschichte", GESCHICHTE)

    for nr, datei in enumerate(sorted(INTERVIEWS.glob("*.md")), start=1):
        name, text = _interviewtext(datei)
        aufnahme.importiere_text(conn, e, CHAT_ID, nr, text, name=f"Interview {nr}")

    for name, beschreibung, profil, zitate in FIGUREN:
        repo.setze_figur(conn, CHAT_ID, name, beschreibung)
        figur = repo.hole_figur(conn, CHAT_ID, name)
        repo.setze_sprachprofil(conn, figur["id"], profil, zitate)
    repo.setze_arbeitsstand(conn, CHAT_ID, "figuren_fixiert_am", "2026-09-30T10:00:00+00:00")

    for (name, *_), stil in zip(FIGUREN, VARIANTEN[variante]):
        if stil:
            figur = repo.hole_figur(conn, CHAT_ID, name)
            repo.setze_figur_sprachstil(conn, figur["id"], STILE[stil])

    ids = {f["name"]: f["id"] for f in repo.figuren(conn, CHAT_ID)}
    for nummer, (titel, was, besetzung) in enumerate(SZENEN, start=1):
        sz_id = repo.lege_szene_an(conn, CHAT_ID, nummer, titel, None, None)
        repo.setze_szenenfeld(conn, sz_id, "was_passiert", was)
        if nummer == 1:
            for feld, wert in SZENE_1_FELDER.items():
                repo.setze_szenenfeld(conn, sz_id, feld, wert)
            if phase >= 7:
                repo.setze_szenenfeld(conn, sz_id, "form", "Dialog")
        repo.setze_szene_figuren(conn, CHAT_ID, sz_id, [ids[n] for n in besetzung])
        repo.aktualisiere_szene(conn, sz_id, titel, None, None, None, prosa=PROSA[nummer])

    if phase >= 7:
        repo.setze_szene_usa(conn, CHAT_ID, True)
    repo.setze_phase(conn, CHAT_ID, phase)
    return conn


def setze_vorlage(conn, prosa: str, nummer: int = 1) -> None:
    """Ersetzt die Prosafassung einer Szene (fuer Task 3: die Vorlage aus
    einem echten Prosa-Lauf). Titel bleibt, Volltext wird nicht angefasst."""
    ziel = next(z for z in repo.hole_szenen(conn, CHAT_ID) if z["nummer"] == nummer)
    repo.aktualisiere_szene(conn, ziel["id"], ziel["titel"], ziel["kurzbeschreibung"],
                            None, ziel["zusammenfassung"], prosa=prosa)


# ---------------------------------------------------------------------------
# Die echten Prompts
# ---------------------------------------------------------------------------


def prosa_prompt(conn) -> tuple[str, str]:
    """(System, Nutzer) des Prosa-Laufs -- wie ``kurzgeschichte.starte._lauf``."""
    return kurzgeschichte.systemanweisung(), kurzgeschichte.baue_nutzertext(conn, CHAT_ID)


def szene_prompt(conn, e=None, auftrag: str = AUFTRAG_SZENE) -> tuple[str, str]:
    """(System, Nutzer) des Feinschliff-Laufs -- wie ``szene.schreibe``.

    Verweigert den Bau, wenn die Sperre aus ``szene.starte`` griffe: ein Prompt,
    den der Bot nie abschicken wuerde, misst nichts."""
    e = e or einstellungen_szene()
    ziel = szene.ziel_fuer(conn, CHAT_ID, auftrag)
    sperre = szene.sperrtext(conn, ziel)
    if sperre:
        raise RuntimeError(f"Sperre griffe: {sperre}")
    if szene.schreibt_prosa(conn, CHAT_ID):
        raise RuntimeError("Phase ist nicht Feinschliff -- szene.schreibe schriebe Prosa")
    form = ziel["form"]
    stil = ziel["stil"] if "stil" in ziel.keys() else None
    return (szene.systemanweisung(form, stil),
            szene.baue_nutzertext(conn, CHAT_ID, auftrag, ziel, e))


def als_datei(system: str, nutzer: str) -> str:
    return f"=== SYSTEM ===\n{system}\n\n=== NUTZER ===\n{nutzer}\n"


def _diff(a: str, b: str, name_a: str, name_b: str) -> tuple[str, int, int]:
    zeilen = list(difflib.unified_diff(
        a.splitlines(keepends=True), b.splitlines(keepends=True),
        fromfile=name_a, tofile=name_b,
    ))
    plus = sum(1 for z in zeilen if z.startswith("+") and not z.startswith("+++"))
    minus = sum(1 for z in zeilen if z.startswith("-") and not z.startswith("---"))
    return "".join(zeilen), plus, minus


# ---------------------------------------------------------------------------
# Unterbefehle
# ---------------------------------------------------------------------------


def befehl_pfad(a) -> int:
    ziel_dir = Path(a.ausgabe) / "prompts"
    ziel_dir.mkdir(parents=True, exist_ok=True)
    texte: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as ordner:
        for variante in VARIANTEN:
            for weg, phase in (("prosa", 6), ("szene", 7)):
                conn = baue_db(Path(ordner) / f"{weg}-{variante}.db", variante, phase)
                system, nutzer = prosa_prompt(conn) if weg == "prosa" else szene_prompt(conn)
                conn.close()
                name = f"{weg}-{variante}.txt"
                texte[name] = als_datei(system, nutzer)
                (ziel_dir / name).write_text(texte[name])

    for weg, x, y in (("prosa", "A", "B"), ("prosa", "A", "C"), ("szene", "A", "B"),
                      ("szene", "A", "C")):
        name_a, name_b = f"{weg}-{x}.txt", f"{weg}-{y}.txt"
        text, plus, minus = _diff(texte[name_a], texte[name_b], name_a, name_b)
        (ziel_dir / f"diff-{weg}-{x}-{y}.diff").write_text(text)
        urteil = "identisch" if not text else f"{max(plus, minus)} Zeilen geaendert (+{plus}/-{minus})"
        print(f"{weg} {x}-{y}: {urteil}")
    print(f"Ausgabe: {ziel_dir.relative_to(WURZEL) if ziel_dir.is_relative_to(WURZEL) else ziel_dir}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    unter = ap.add_subparsers(dest="befehl", required=True)
    p = unter.add_parser("pfad", help="echte Prompts je Variante erzeugen und diffen (kein Netz)")
    p.add_argument("--ausgabe", default=str(AUSGABE))
    p.set_defaults(fn=befehl_pfad)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

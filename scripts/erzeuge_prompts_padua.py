"""Die vollstaendig arrangierten Prompts zweier Phasen unter dem Padua-Profil.

Aufruf (Karte P, 01.10.2026)::

    IT_WORKSHOP=padua-2026 python -m scripts.erzeuge_prompts_padua \\
        docs/prompt-audit/2026-09-30-padua

Anders als ``scripts/erzeuge_prompts.py`` liest dieses Skript **keine**
bestehende Datenbank: es baut sich eine Wegwerf-Datenbank in einem
Temp-Verzeichnis und fuellt sie mit zwei erfundenen Gruppen -- eine in
Phase 1 (Terms), eine in Phase 6 (Scenes as Story). Das Interviewmaterial
der zweiten ist ``simulation/interviews/set1/2-ferzan-bahnhof.md``, frei
erfunden; die echte Betriebsdatenbank wird nie geoeffnet.

``IT_DB`` wird dabei auf die Wegwerf-Datenbank gesetzt, weil
``anweisungen.system`` den Regie-Zettel (``zusatz.md``) neben ``IT_DB``
sucht -- ein Zettel aus ``betrieb/`` stuende sonst im Dump.

Je Pfad eine Datei mit ``=== SYSTEM ===`` und ``=== NUTZER ===`` (dasselbe
Format wie ``erzeuge_prompts``), plus ``uebersicht.tsv``. Steht die
Profil-Anweisung (``workshop/<name>/prompts/anweisung.md``) im
Systemtext, wird im **Dump** -- und nur dort -- die Zeile ``MARKE``
davorgesetzt: der Bot bekommt sie nie.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_theater import (
    anweisungen, db, kontext, kurzgeschichte, repo, szene, workshop,
)
from scripts.erzeuge_prompts import _E, _schreibe

#: Die Markierung vor der Profil-Anweisung, nur im Dump. Bis zum 01.10.2026
#: war sie ein Vorschlag ("<!-- VORSCHLAG zur Abnahme -->"); Birk hat ihn an
#: diesem Tag abgenommen (Karte P-Fix).
MARKE = "<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->"

#: Das erfundene Interview, aus dem die Phase-6-Gruppe ihr Material hat.
INTERVIEW = Path("simulation/interviews/set1/2-ferzan-bahnhof.md")

BASIS = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)


def _iso(minuten: int) -> str:
    return (BASIS + timedelta(minutes=minuten)).isoformat(timespec="seconds")


def _markiere(system: str) -> str:
    """Setzt die Abnahme-Markierung vor die Profil-Anweisung -- nur im Dump."""
    anweisung = (anweisungen.hole_optional(anweisungen.PROFIL_ANWEISUNG) or "").strip()
    if anweisung and anweisung in system:
        return system.replace(anweisung, f"{MARKE}\n{anweisung}", 1)
    return system


def _verlauf(conn, chat_id: int, zeilen, start: int) -> None:
    for i, (absender, text) in enumerate(zeilen):
        repo.merke_nachricht(
            conn, chat_id, start + i, absender, int(absender == "InScribe"),
            "text", text, _iso(start + i),
        )


def baue_phase1(conn) -> int:
    """Gruppe 1: gerade angekommen, die Begriffsliste aus dem Plenum kommt."""
    chat_id = 1
    repo.sichere_gruppe(conn, chat_id, "padua1", "Padua group 1")
    repo.setze_phase(conn, chat_id, 1)
    _verlauf(conn, chat_id, [
        ("InScribe", "Hello! This is where your list of terms from the plenary "
                     "comes to me. Send it typed or as a voice message."),
        ("Giulia", "hi! ok here is our wall"),
        ("Giulia", "arrival, waiting, strangers, home, noise, trust, "
                   "belonging, the city at night, family"),
        ("Marco", "we also had 'language' but we weren't sure"),
        ("Giulia", "is that too many? what do we do with them now?"),
    ], start=10)
    return chat_id


def baue_phase6(conn) -> int:
    """Gruppe 2: Setting, Figuren, Geschichte und drei Abschnitte stehen,
    ein Interview ist verdichtet -- der Stand mitten in Phase 6."""
    chat_id = 2
    repo.sichere_gruppe(conn, chat_id, "padua2", "Padua group 2")
    for feld, wert in (
        ("begriffe", "arrival, waiting, strangers, noise, belonging"),
        ("fragen", "1. What do you remember about your first day here?\n"
                   "2. Where did you wait the longest in your life?\n"
                   "3. When did a strange place start to feel like yours?"),
        ("interview_eroeffnung", "Hi, we are acting students from the theatre "
                                 "academy. Do you have ten minutes for three questions?"),
        ("interview_abschluss", "Thank you. Your answers stay anonymous and "
                                "become material for a fictional play."),
        ("rahmen", "A railway station in a northern Italian city, one wet "
                   "November evening. A young man has just arrived and waits "
                   "for a cousin who does not come."),
        ("geschichte", "Samir waits on a bench with two bags, one of them broken. "
                       "He rehearses how to order a coffee and never goes. The "
                       "woman at the station café notices him. When his cousin "
                       "finally arrives, the broken bag opens in the middle of the "
                       "hall - and for the first time Samir laughs here."),
        ("figuren_fixiert_am", _iso(0)),
    ):
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    repo.setze_phase(conn, chat_id, 6)

    # Das Interview: Transkript aus dem erfundenen Simulationsmaterial, eine
    # Verdichtung mit Zitaten, die woertlich darin stehen.
    roh = INTERVIEW.read_text(encoding="utf-8")
    transkript = roh.split("---", 2)[2].strip()
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, 5, "lang", "text", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, transkript)
    zitate = (
        "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
        "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
    )
    assert all(z in transkript for z in zitate)
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id,
        "The interviewee remembers his first day: three hours on a station "
        "bench with a broken bag, waiting for a cousin, too unsure to buy "
        "food, unable to understand the announcements.",
        [
            {"thema": "waiting", "beleg_zitat": zitate[0], "zitat_geprueft": 1,
             "kurz": "three hours on the bench"},
            {"thema": "noise", "beleg_zitat": zitate[1], "zitat_geprueft": 1,
             "kurz": "the loudspeaker"},
        ],
    )

    figuren = {}
    for name, beschreibung, stil in (
        ("Samir", "just arrived, wants to arrive without asking anyone",
         "Short sentences, corrects himself, drops into his first language."),
        ("Elena", "runs the station café, sees everyone and says little",
         "Dry, practical, questions instead of statements."),
        ("Tommaso", "the cousin, late, embarrassed, overly cheerful",
         "Talks fast, apologises twice, jokes to cover it."),
    ):
        repo.setze_figur(conn, chat_id, name, beschreibung)
        figur_id = repo.hole_figur(conn, chat_id, name)["id"]
        repo.setze_figur_sprachstil(conn, figur_id, stil)
        figuren[name] = figur_id

    for nummer, titel, kurz, besetzung, prosa in (
        (1, "The bench", "Samir waits and rehearses his order.",
         ("Samir",),
         "The hall smelled of wet coats. Samir held the broken bag shut with "
         "his foot and counted the trains he did not understand."),
        (2, "The café", "Elena watches him not coming in.",
         ("Samir", "Elena"),
         "Elena had wiped the same spot on the counter three times. The boy on "
         "the bench had looked at her menu for an hour."),
        (3, "Socks on the floor", "Tommaso arrives, the bag opens.",
         ("Samir", "Tommaso", "Elena"),
         "Tommaso came in running, said sorry twice and took the wrong bag. It "
         "opened. Socks everywhere. Samir laughed before he could stop himself."),
    ):
        szene_id = repo.lege_szene_an(conn, chat_id, nummer, titel, kurz, None)
        repo.aktualisiere_szene(conn, szene_id, titel, kurz, None, prosa=prosa)
        repo.setze_szenenfeld(conn, szene_id, "ort", "the railway station")
        repo.setze_szenenfeld(conn, szene_id, "was_passiert", kurz)
        repo.setze_szene_figuren(
            conn, chat_id, szene_id, [figuren[n] for n in besetzung])

    repo.schreibe_journal(conn, chat_id, "entschieden",
                          "Story as short story: 3 sections", quelle="szene")
    _verlauf(conn, chat_id, [
        ("InScribe", "Here is your story in three sections. Tell me what should "
                     "change."),
        ("Giulia", "we like it. but Elena is too quiet in part 2"),
        ("Luca", "yes she should say something to him, not just watch"),
        ("Giulia", "can she be a bit rude at first? like annoyed"),
    ], start=100)
    return chat_id


def main() -> None:
    # Das Skript ist Padua-spezifisch: ohne Variable haengt es das Profil
    # selbst ein, eine andere Variable weist es ab.
    os.environ.setdefault(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    if workshop.name() != "padua-2026":
        sys.exit("IT_WORKSHOP=padua-2026 setzen -- sonst entsteht der Dortmunder Prompt.")
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/prompt-audit/2026-09-30-padua")
    ziel.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "padua-prompts.db")
        os.environ["IT_DB"] = pfad
        conn = db.verbinde(pfad)
        db.initialisiere(conn)
        e = _E()
        e.bot_name = "padua1"
        eins = baue_phase1(conn)
        sechs = baue_phase6(conn)

        zeilen = []
        ausloeser = [repo.letzte_nachrichten(conn, eins, anzahl=1)[-1]]
        zeilen.append(_schreibe(
            ziel, "01-gespraech-phase1",
            _markiere(kontext.system(e.bot_name, 1)),
            kontext.baue(conn, eins, ausloeser, e),
            "Phase 1 (Terms): anweisungen.system(bot, 1) + kontext.baue",
        ))
        ausloeser = [repo.letzte_nachrichten(conn, sechs, anzahl=1)[-1]]
        zeilen.append(_schreibe(
            ziel, "02-gespraech-phase6",
            _markiere(kontext.system(e.bot_name, 6)),
            kontext.baue(conn, sechs, ausloeser, e),
            "Phase 6 (Scenes as Story): anweisungen.system(bot, 6) + kontext.baue",
        ))
        zeilen.append(_schreibe(
            ziel, "03-kurzgeschichte-phase6",
            kurzgeschichte.systemanweisung(),
            kurzgeschichte.baue_nutzertext(
                conn, sechs, "Elena should say something to him, a bit rude at first."),
            "Phase 6 Prosalauf: kurzgeschichte.systemanweisung + baue_nutzertext (Regie-Notiz)",
        ))
        ziel_szene = repo.hole_szenen(conn, sechs)[1]
        zeilen.append(_schreibe(
            ziel, "04-szene-prosa-phase6",
            szene.systemanweisung("prosa"),
            szene.baue_nutzertext(conn, sechs, "Rewrite scene 2.", ziel_szene),
            "Phase 6 Einzelszene: szene.systemanweisung('prosa') + baue_nutzertext",
        ))
        conn.close()

    tsv = ["pfad\tsystem_zeichen\tnutzer_zeichen\ttoken_gesamt"]
    for name, s, n, t in zeilen:
        tsv.append(f"{name}\t{s}\t{n}\t{t}")
    (ziel / "uebersicht.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    print("\n".join(tsv))


if __name__ == "__main__":
    main()

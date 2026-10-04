"""Abnahme gegen die echte Padua-Live-Datenbank (Task 7, Karte t_8f1adaa4).

Dieser Test spielt die Fixes aus den Tasks 1, 2, 3 und 5 gegen eine
VACUUM-Kopie der echten, laufenden Padua-Produktionsdatenbank
(chat_id 7000000000000) ab -- kein erfundenes Fixture, kein Modell, kein
Netz. Er validiert das ZUSAMMENSPIEL der vorherigen Tasks an einem realen
Datensatz, nicht einen einzelnen Codepfad.

Sicherheitsregel: ``padua_replay.db`` im Worktree-Root ist eine manuell
bereitgestellte Kopie der echten Live-DB und darf NIE direkt geoeffnet
werden -- dieser Test kopiert sie zuerst in ``tmp_path`` und arbeitet nur
auf dieser Kopie. ``padua_replay.db`` selbst bleibt dadurch byte-identisch
vor und nach jedem Testlauf (vom Controller separat per Checksumme
verifiziert).

Mutationstest: nicht sinnvoll als einzelner Code-Mutant -- dieser Test
validiert das Zusammenspiel aller vorherigen Fixes (Tasks 1/2/3/5) an
echten Daten, nicht einen einzelnen Fix. Ohne Task 1 (Schema) wuerde
``repo.stelle_erkenner_lauf_wieder_her`` und die Spalte
``aufnahme.zu_kurz_uebersprungen`` gar nicht existieren, ohne Task 5 nicht
``aufnahme.migriere_zu_kurz_altdaten`` -- das ist implizit durch die
Abhaengigkeitskette abgedeckt (ein `git stash` der frueheren Tasks wuerde
diesen Test nicht rot, sondern mit einem Importfehler abbrechen lassen).
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from interview_theater import aufnahme, db, phasen, repo, ruecknahme

CHAT_ID = 7000000000000

_REPLAY_DB = Path(__file__).resolve().parent.parent / "padua_replay.db"


def _oeffne_kopie(tmp_path) -> sqlite3.Connection:
    """Kopiert padua_replay.db nach tmp_path und oeffnet NUR die Kopie."""
    ziel = tmp_path / "padua_replay_kopie.db"
    shutil.copyfile(_REPLAY_DB, ziel)
    conn = db.verbinde(str(ziel))
    db.initialisiere(conn)
    return conn


@pytest.mark.skipif(
    not _REPLAY_DB.exists(),
    reason=(
        "padua_replay.db liegt nicht im Worktree-Root -- das ist eine "
        "manuell bereitgestellte VACUUM-Kopie der echten Padua-Live-DB "
        "(gitignored, kein Wegwerfartefakt). Ohne sie ueberspringt dieser "
        "Abnahmetest, er laeuft nur dort, wo die Datei von Hand abgelegt "
        "wurde."
    ),
)
def test_replay_padua_live_redo_plus_phase4_sperre(tmp_path):
    conn = _oeffne_kopie(tmp_path)
    try:
        # --- Schritt 1: die drei dokumentierten Annahmen verifizieren,
        # BEVOR irgendetwas angewendet wird. Weicht die Kopie vom
        # beschriebenen Stand ab, soll der Test laut abbrechen statt die
        # Zahlen stillschweigend anzupassen (Brief, Task 7).
        aufnahme_32 = conn.execute(
            "SELECT klasse, status, zu_kurz_uebersprungen FROM aufnahme "
            "WHERE id = 32 AND chat_id = ?",
            (CHAT_ID,),
        ).fetchone()
        assert aufnahme_32 is not None, (
            "aufnahme id 32 (chat_id 7000000000000) fehlt in der Kopie -- "
            "die Annahmen aus dem Task-7-Brief passen nicht auf diese DB."
        )
        assert (aufnahme_32["klasse"], aufnahme_32["status"], aufnahme_32["zu_kurz_uebersprungen"]) == (
            "lang",
            "fertig",
            0,
        ), f"aufnahme id 32 weicht vom dokumentierten Vorzustand ab: {dict(aufnahme_32)}"
        assert repo.verdichtung_zu_aufnahme(conn, 32) is None, (
            "aufnahme id 32 hat entgegen der Dokumentation bereits eine "
            "Verdichtung -- Annahme aus dem Brief stimmt nicht."
        )

        aufnahme_37 = conn.execute(
            "SELECT klasse, status FROM aufnahme WHERE id = 37 AND chat_id = ?",
            (CHAT_ID,),
        ).fetchone()
        assert aufnahme_37 is not None, "aufnahme id 37 fehlt in der Kopie."
        assert (aufnahme_37["klasse"], aufnahme_37["status"]) == ("lang", "fertig"), (
            f"aufnahme id 37 weicht vom dokumentierten Vorzustand ab: {dict(aufnahme_37)}"
        )
        assert repo.verdichtung_zu_aufnahme(conn, 37) is not None, (
            "aufnahme id 37 hat entgegen der Dokumentation KEINE Verdichtung."
        )

        lauf_3 = conn.execute(
            "SELECT chat_id, zurueckgenommen_am, wiederhergestellt_am "
            "FROM erkenner_lauf WHERE id = 3",
        ).fetchone()
        assert lauf_3 is not None, "erkenner_lauf id 3 fehlt in der Kopie."
        assert lauf_3["chat_id"] == CHAT_ID
        assert lauf_3["zurueckgenommen_am"] == "2026-10-03T20:48:47+00:00", (
            f"erkenner_lauf id 3 'zurueckgenommen_am' weicht ab: {dict(lauf_3)}"
        )
        assert lauf_3["wiederhergestellt_am"] is None, (
            f"erkenner_lauf id 3 ist entgegen der Dokumentation schon wiederhergestellt: {dict(lauf_3)}"
        )

        # --- Schritt 2: Legacy-Backfill (Task 5). Die additive
        # Spaltenmigration (db.initialisiere oben) setzt eine neu
        # ergaenzte Spalte nur auf ihren DEFAULT-Wert (0) -- sie weiss
        # nicht, dass die bestehende zu-kurz-Aufnahme (id 32, 38 Woerter,
        # status='fertig', keine Verdichtung) genau der Fall ist, den das
        # neue Flag beschreibt. Das ist derselbe Nachtrag, den ein
        # Operator nach dem Deployment dieses Fixes gegen die ECHTE
        # betrieb/padua.db fahren muesste, um die dort laengst blockierte
        # Gruppe zu entsperren -- hier simulieren wir genau das.
        migriert = aufnahme.migriere_zu_kurz_altdaten(conn, chat_id=CHAT_ID)
        assert migriert == 1, f"erwartet genau 1 migrierte Zeile (id 32), bekommen: {migriert}"

        nach_migration = conn.execute(
            "SELECT zu_kurz_uebersprungen FROM aufnahme WHERE id = 32",
        ).fetchone()
        assert nach_migration["zu_kurz_uebersprungen"] == 1

        # --- Schritt 3: Redo auf dem echten, live zurueckgenommenen Lauf
        # (Task 1/2). Repo-Level-Replay, kein Knopfdruck noetig.
        ergebnis = repo.stelle_erkenner_lauf_wieder_her(
            conn,
            3,
            ruecknahme.verweise(),
            ruecknahme.WEICH,
            ruecknahme.HART,
            ruecknahme.GELEERT,
        )
        assert ergebnis == repo.ZURUECK_OK, f"Redo lieferte {ergebnis!r}, erwartet ZURUECK_OK"

        # --- Assertions ---

        # 1. arbeitsstand.fragen traegt wieder die 11 Fragen -- die
        # 10. Frage ("Verdrängung: Is there something you avoid ...")
        # ist ein eindeutiges Stichwort fuer den wiederhergestellten
        # Stand (vorher stand dort nur die einzelne Apfel-Frage).
        fragen_zeile = conn.execute(
            "SELECT fragen FROM arbeitsstand WHERE chat_id = ?", (CHAT_ID,)
        ).fetchone()
        assert fragen_zeile is not None
        assert "Verdrängung" in fragen_zeile["fragen"], (
            f"arbeitsstand.fragen nach dem Redo ohne die erwartete 11. Frage: "
            f"{fragen_zeile['fragen']!r}"
        )

        # 2. die 38-Woerter-Aufnahme (id 32) ist nicht mehr unausgewertet --
        # die Phase-4-Sperre haelt sie nicht mehr auf.
        offene_ids = [z["id"] for z in aufnahme.unausgewertete_interviews(conn, CHAT_ID)]
        assert 32 not in offene_ids, (
            f"aufnahme id 32 steht trotz migriere_zu_kurz_altdaten noch in "
            f"unausgewertete_interviews: {offene_ids}"
        )

        # 3. Phase 4 ist jetzt erreichbar -- aufnahme_id 37 liefert die
        # schon vorher vorhandene Verdichtung (bool(repo.verdichtungen(..)));
        # erst der Fix aus Task 5 macht unausgewertete_interviews() leer.
        voraussetzungen = phasen.voraussetzungen(conn, CHAT_ID)
        assert voraussetzungen[4] is True, (
            f"phasen.voraussetzungen(..)[4] ist nicht True: {voraussetzungen}"
        )
    finally:
        conn.close()

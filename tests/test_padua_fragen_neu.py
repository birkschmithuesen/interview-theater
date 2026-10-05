"""scripts/padua_fragen_neu.py -- die Fragen-Sortierung einer Padua-Gruppe
(Phase 2) neu oeffnen: Entscheidungen zuruecksetzen, optional die isolierten
KI-Fragen neu erzeugen und die Auswahl neu zusammenstellen. Siehe
docs/superpowers/plans/2026-10-05-auswahlliste-cothinker.md, Task 4.

Alles gegen eine Wegwerf-DB in tmp_path (kein ``betrieb/`` wird je
angefasst), ohne Netz -- der Modellaufruf (``neu.ki_fragen_erzeugen``) ist
in jedem Test entweder monkeypatched oder per Fixture verboten.
"""

from pathlib import Path

import pytest

from interview_theater import db, repo
from scripts import padua_fragen_neu as neu

CHAT = 1
BEGRIFFE = "Heimat, Streit"
EIGENE = "Heimat: Wann warst du zuletzt dort?\nStreit: Worum ging's?"
KI_NEU_TEXT = "Heimat: Was bedeutet das Wort fuer dich?\nStreit: Wie hat es angefangen?"
ENTSCHIEDEN = "ja,nein"
HERKUNFT = "eigen,eigen"
FELDER = ("fragen_auswahl", "fragen_herkunft", "fragen_entschieden",
          "fragen_aktuell", "fragen_warte_auf")


def _baue_db(tmp_path: Path) -> Path:
    pfad = tmp_path / "betrieb" / "padua.db"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(str(pfad))
    try:
        db.initialisiere(conn)
        repo.sichere_gruppe(conn, CHAT, "padua1", "Testgruppe")
        repo.setze_phase(conn, CHAT, 2)
        repo.setze_arbeitsstand(conn, CHAT, "begriffe", BEGRIFFE)
        repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", EIGENE)
        repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", EIGENE)
        repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", HERKUNFT)
        repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", ENTSCHIEDEN)
        repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")
        repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", "schaerfen")
    finally:
        conn.close()
    return pfad


def _felder(pfad: Path, chat_id: int = CHAT) -> dict:
    conn = db.verbinde(str(pfad))
    try:
        zeile = repo.hole_arbeitsstand(conn, chat_id)
        if zeile is None:
            return dict.fromkeys(FELDER)
        return {f: zeile[f] for f in FELDER}
    finally:
        conn.close()


@pytest.fixture
def kein_modellaufruf(monkeypatch):
    """``ki_fragen_erzeugen`` darf in keinem Test, der diese Fixture nutzt,
    aufgerufen werden -- auch nicht im Trockenlauf mit ``--ki-neu``. Ein
    Aufruf waere ein echtes Modell (Geld, Netz) und damit ein Fehler im
    Skript, kein akzeptabler Testausgang."""
    def _verboten(*a, **k):
        raise AssertionError("ki_fragen_erzeugen wurde aufgerufen -- verboten in diesem Test")

    monkeypatch.setattr(neu, "ki_fragen_erzeugen", _verboten)


# --------------------------------------------------------------------------
# Trockenlauf (Vorgabe)
# --------------------------------------------------------------------------


def test_trockenlauf_schreibt_nichts(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    vorher = _felder(pfad)
    assert neu.main([str(CHAT), "--db", str(pfad)]) == 0
    assert _felder(pfad) == vorher
    aus = capsys.readouterr().out
    assert "Trockenlauf" in aus
    assert "Nichts geschrieben" in aus or "--apply" in aus


def test_trockenlauf_zeigt_anzahl_und_entscheidungen(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad)]) == 0
    aus = capsys.readouterr().out
    assert "ja=1" in aus
    assert "nein=1" in aus
    assert "offen=2" in aus  # Vorhersage: nach --apply waeren beide wieder offen


def test_trockenlauf_mit_ki_neu_ruft_kein_modell_und_sagt_es_an(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad), "--ki-neu"]) == 0
    aus = capsys.readouterr().out
    assert "ki" in aus.lower()
    assert "Nichts geschrieben" in aus or "--apply" in aus


def test_unbekannte_gruppe_verweigert_im_trockenlauf(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main(["987654321", "--db", str(pfad)]) == 1
    assert "Verweigert" in capsys.readouterr().out


def test_fehlende_datenbank_verweigert(tmp_path, capsys, kein_modellaufruf):
    pfad = tmp_path / "betrieb" / "padua.db"
    assert neu.main([str(CHAT), "--db", str(pfad)]) == 1
    assert "Verweigert" in capsys.readouterr().out


# --------------------------------------------------------------------------
# --apply (ohne --ki-neu): Entscheidungen zuruecksetzen, Text behalten
# --------------------------------------------------------------------------


def test_apply_setzt_entscheidungen_zurueck_behaelt_text(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad), "--apply"]) == 0
    nach = _felder(pfad)
    assert nach["fragen_entschieden"] is None
    assert nach["fragen_aktuell"] is None
    assert nach["fragen_warte_auf"] is None
    assert nach["fragen_auswahl"] == EIGENE
    assert nach["fragen_herkunft"] == HERKUNFT
    aus = capsys.readouterr().out
    assert "Ausgefuehrt" in aus or "Sicherung" in aus


def test_apply_legt_sicherung_mit_altem_stand_an(tmp_path, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad), "--apply"]) == 0
    sicherungen = list((pfad.parent / "backup").glob(f"padua-{CHAT}-*.db"))
    assert len(sicherungen) == 1
    gesichert = db.verbinde(str(sicherungen[0]))
    try:
        zeile = repo.hole_arbeitsstand(gesichert, CHAT)
        assert zeile["fragen_entschieden"] == ENTSCHIEDEN
    finally:
        gesichert.close()
    # die lebende Datenbank ist inzwischen zurueckgesetzt -- die Sicherung
    # hat den Stand VOR dem Reset eingefangen, nicht danach.
    assert _felder(pfad)["fragen_entschieden"] is None


def test_apply_unbekannte_gruppe_verweigert_ohne_sicherung(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main(["987654321", "--db", str(pfad), "--apply"]) == 1
    assert "Verweigert" in capsys.readouterr().out
    assert not (pfad.parent / "backup").exists() or \
        not list((pfad.parent / "backup").glob("*.db"))


# --------------------------------------------------------------------------
# --apply --ki-neu: Modell (gemockt) regeneriert, Auswahl neu zusammengestellt
# --------------------------------------------------------------------------


def test_ki_neu_apply_baut_auswahl_und_herkunft_neu(tmp_path, monkeypatch, capsys):
    pfad = _baue_db(tmp_path)
    aufrufe = []

    def _fake(conn, chat_id, stand):
        aufrufe.append(chat_id)
        return KI_NEU_TEXT

    monkeypatch.setattr(neu, "ki_fragen_erzeugen", _fake)
    assert neu.main([str(CHAT), "--db", str(pfad), "--ki-neu", "--apply"]) == 0
    assert aufrufe == [CHAT]

    nach = _felder(pfad)
    zeilen = nach["fragen_auswahl"].splitlines()
    herkunft = nach["fragen_herkunft"].split(",")
    assert len(zeilen) == len(herkunft) == 4
    # je Begriff zuerst die eigene Frage, dann die KI-Frage (dieselbe
    # Reihenfolge wie knoepfe.fragen.versuche_gegenueberstellung)
    assert herkunft == ["eigen", "ki", "eigen", "ki"]
    assert zeilen[0].startswith("Heimat:")
    assert zeilen[1] == "Heimat: Was bedeutet das Wort fuer dich?"
    assert zeilen[2].startswith("Streit:")
    assert zeilen[3] == "Streit: Wie hat es angefangen?"
    assert nach["fragen_entschieden"] is None
    assert nach["fragen_aktuell"] is None
    assert nach["fragen_warte_auf"] is None


def test_ki_neu_ohne_apply_ruft_modell_nicht_auf(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad), "--ki-neu"]) == 0


def test_apply_ohne_ki_neu_ruft_modell_nicht_auf(tmp_path, capsys, kein_modellaufruf):
    pfad = _baue_db(tmp_path)
    assert neu.main([str(CHAT), "--db", str(pfad), "--apply"]) == 0


# --------------------------------------------------------------------------
# Vorgabe-Pfad
# --------------------------------------------------------------------------


def test_vorgabe_db_ist_betrieb_padua(monkeypatch, tmp_path, kein_modellaufruf):
    """Ohne ``--db`` zeigt das Skript auf ``betrieb/padua.db`` relativ zum
    Arbeitsverzeichnis -- der Operator startet es aus dem Hauptcheckout."""
    monkeypatch.chdir(tmp_path)
    _baue_db(tmp_path)
    assert neu.main([str(CHAT)]) == 0

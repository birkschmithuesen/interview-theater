"""Weiche Fassungen in Phase 2 per Profil abschaltbar (Birk, 03.10.2026 live:
„Die ganze Softwaregeschichte beim Fragen entwickeln kannst du fuer Padua
deaktivieren [...] Es hat nicht gut funktioniert, aber deaktivier das
einfach.“).

Abgeschaltet heisst, an jeder Stelle, an der die weiche Fassung sonst
auftaucht:
* kein Auftrag im Prompt (``ANWEISUNG_FRAGEN_ANDERE``/``_SCHAERFEN``),
* nichts gespeichert, auch wenn das Modell den Block doch liefert,
* kein Angebot nach der letzten Entscheidung -- die Eroeffnung startet direkt,
* der Leitfaden zeigt die Frage selbst (auch bei Altbestand in der DB),
* Phase 3 wartet nicht auf eine Pruefung, die es nicht mehr gibt
  (``phasen``-Gate, Roadmap-Gate, Fehlstellen), und die Roadmap zeigt die
  Aufgabe \"Einleitungen\" nicht.

Dortmund (Vorgabe an) bleibt unberuehrt -- das decken die bestehenden Tests
in ``test_phase2_einzeln.py`` ab.
"""
import pytest

from interview_theater import fehlstellen, leitfaden, phasen, repo, roadmap, workshop
from interview_theater import knoepfe
from interview_theater.knoepfe import fragen as fragen_modul

from test_roadmap import _lage
from test_phase2_einzeln import (  # noqa: F401  (Fixtures)
    VORSCHLAG, _druecke, _vorschlag_zeigen, auftraege, tg,
)


@pytest.fixture
def aus(monkeypatch):
    monkeypatch.setattr(workshop, "fragen_weich_aktiv", lambda profil=None: False)


def test_padua_profil_schaltet_weiche_fassungen_ab():
    assert workshop.fragen_weich_aktiv(workshop.lade("padua-2026")) is False


def test_dortmund_und_vorgabe_behalten_weiche_fassungen():
    assert workshop.fragen_weich_aktiv(workshop.lade("dortmund-2026")) is True
    assert workshop.fragen_weich_aktiv(workshop.VORGABE) is True


def test_aus_der_weiche_block_wird_nicht_gespeichert(conn, tg, aus):
    _vorschlag_zeigen(conn, tg)  # VORSCHLAG enthaelt einen WEICH-Block
    assert (repo.hole_arbeitsstand(conn, 1)["fragen_weich"] or "") == ""


def test_aus_kein_angebot_die_eroeffnung_startet_direkt(conn, tg, einst, auftraege, aus):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    _druecke(conn, tg, einst, "Annehmen")
    _druecke(conn, tg, einst, "Annehmen")
    _druecke(conn, tg, einst, "Annehmen")

    for _, text, _ in tg.knoepfe:
        assert not text.startswith(knoepfe.T._TEXT_FRAGEN_WEICH_ANGEBOT)
    assert len(auftraege) == 1  # die Eroeffnung ist angelaufen


def test_aus_der_prompt_bittet_nicht_um_weiche_fassungen(conn, tg, aus):
    _vorschlag_zeigen(conn, tg)
    anweisung = fragen_modul.frage_fuer_andere_richtung(conn, 1, "mehr Streit")
    assert knoepfe.T._ANWEISUNG_FRAGEN_SENSIBEL not in anweisung
    assert "FRAGEN WEICH" not in anweisung
    assert "mehr Streit" in anweisung  # der Rest der Anweisung bleibt


def test_aus_die_schaerfung_bittet_nicht_um_weiche_fassungen(
    conn, tg, einst, auftraege, aus,
):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    fragen_modul._starte_schaerfung(conn, tg, None, einst, 1, 1, "kuerzer")
    anweisung = auftraege[-1]
    assert "FRAGEN WEICH" not in anweisung
    assert "kuerzer" in anweisung


def test_an_der_prompt_bittet_weiter_um_weiche_fassungen(conn, tg):
    _vorschlag_zeigen(conn, tg)
    anweisung = fragen_modul.frage_fuer_andere_richtung(conn, 1)
    assert knoepfe.T._ANWEISUNG_FRAGEN_SENSIBEL in anweisung


def test_aus_der_leitfaden_ignoriert_altbestand(aus):
    felder = {
        "fragen": "Heimat: Was nimmst du mit?",
        "fragen_weich": "1 — Ganz weich: was nimmst du mit?",
        "interview_eroeffnung": "Hallo.", "interview_abschluss": "Danke.",
    }
    teile = leitfaden.bausteine(felder)
    assert teile["fragen"][0]["text"] == "Heimat: Was nimmst du mit?"
    assert "Ganz weich" not in leitfaden.aus_feldern(felder)


def _stand_ohne_pruefung(conn):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Heimat: Was nimmst du mit?")
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", None)
    repo.setze_arbeitsstand(conn, 1, "frage_einleitungen", None)
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo.")
    repo.setze_arbeitsstand(conn, 1, "interview_abschluss", "Danke.")


def test_aus_phase_3_wartet_nicht_auf_die_pruefung(conn, aus):
    _stand_ohne_pruefung(conn)
    assert phasen.voraussetzungen(conn, 1)[3]


def test_an_phase_3_wartet_auf_die_pruefung(conn):
    """Gegenprobe: mit Vorgabe (Dortmund) haelt die fehlende Pruefung auf."""
    _stand_ohne_pruefung(conn)
    assert not phasen.voraussetzungen(conn, 1)[3]


def test_aus_keine_fehlstelle_ungeprueft(conn, aus):
    _stand_ohne_pruefung(conn)
    texte = [e["text"] for e in fehlstellen.register(conn, 1)]
    assert fehlstellen.T._SATZ_FRAGEN_UNGEPRUEFT not in texte


def test_an_fehlstelle_ungeprueft_bleibt(conn):
    _stand_ohne_pruefung(conn)
    texte = [e["text"] for e in fehlstellen.register(conn, 1)]
    assert fehlstellen.T._SATZ_FRAGEN_UNGEPRUEFT in texte


def test_aus_roadmap_ohne_einleitungen(aus):
    lage = _lage(phase=2, stand={
        "begriffe": "Heimat", "fragen": "Heimat: x?",
        "interview_eroeffnung": "Hallo.", "interview_abschluss": "Danke.",
    })
    phase2 = [p for p in roadmap.aus_daten(lage) if p["nummer"] == 2][0]
    assert "einleitungen" not in [a["kennung"] for a in phase2["aufgaben"]]
    assert "Einleitungen" not in roadmap.fehlt(3, lage)


def test_an_roadmap_mit_einleitungen():
    """Gegenprobe Dortmund: die Aufgabe bleibt und haelt Phase 3 auf."""
    lage = _lage(phase=2, stand={
        "begriffe": "Heimat", "fragen": "Heimat: x?",
        "interview_eroeffnung": "Hallo.", "interview_abschluss": "Danke.",
    })
    phase2 = [p for p in roadmap.aus_daten(lage) if p["nummer"] == 2][0]
    assert "einleitungen" in [a["kennung"] for a in phase2["aufgaben"]]
    assert "Einleitungen" in roadmap.fehlt(3, lage)


def test_aus_altbestand_in_der_db_loest_kein_angebot_aus(conn, tg, einst, auftraege, monkeypatch):
    """Der Live-Fall: eine Gruppe hat schon weiche Fassungen in der DB (vor dem
    Abschalten gespeichert). Nach dem Abschalten darf am Ende trotzdem kein
    Angebot kommen."""
    _vorschlag_zeigen(conn, tg)  # an: speichert die weiche Fassung
    assert repo.hole_arbeitsstand(conn, 1)["fragen_weich"]
    monkeypatch.setattr(workshop, "fragen_weich_aktiv", lambda profil=None: False)
    knoepfe.starte_durchgehen(conn, tg, 1)
    for _ in range(3):
        _druecke(conn, tg, einst, "Annehmen")
    for _, text, _ in tg.knoepfe:
        assert not text.startswith(knoepfe.T._TEXT_FRAGEN_WEICH_ANGEBOT)
    assert len(auftraege) == 1

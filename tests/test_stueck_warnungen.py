from interview_theater import befehle, phasen, repo, stagescript, szenenkarte
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def test_abgenommene_karte_in_phase_7_aenderbar(conn):
    phasen.setze(conn, 1, 7, "test")
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2)
    tg = TG()
    antwort = szenenkarte.starte_dialog(conn, tg, E(), 1, 1)
    assert antwort == szenenkarte._T(1)._ANTWORT_DIALOG_GESTARTET
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1
    assert szenenkarte._T(1)._WARNUNG_ANDERE_KARTE.format(nummer=1, aktuell=2) in tg.gesendet


def test_unbekannte_karte_wird_abgelehnt(conn):
    lege_karte_an(conn, 1, 1)
    antwort = szenenkarte.starte_dialog(conn, TG(), E(), 1, 9)
    assert antwort == szenenkarte._T(1)._TEXT_UNBEKANNTE_KARTE.format(nummer=9)


def test_speichern_szene_2_vor_szene_1_mit_warnung(conn):
    for n in (1, 2):
        sid = lege_karte_an(conn, 1, n, bestaetigt=True)
        repo.setze_stagescript(conn, sid, f"SCENE {n}", None)
    tg = TG()
    stagescript.bestaetige(conn, tg, None, E(), 1, 2)
    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 2))["fertig_am"]
    assert stagescript._T(1)._WARNUNG_VORHERIGE_OFFEN.format(nummer=2, offen=1) in tg.gesendet


def test_offene_fragen_sperren_weiterhin(conn):
    lege_karte_an(conn, 1, 1, fragen=["Wo?"])
    antwort = szenenkarte.bestaetige(conn, TG(), None, E(), 1, 1)
    assert antwort == szenenkarte._T(1)._TEXT_FRAGEN_OFFEN_ABGELEHNT


def test_phasenwarnung_ohne_sperre(conn, monkeypatch):
    monkeypatch.setattr(befehle, "p5_gate", lambda *a, **k: False)
    monkeypatch.setattr(befehle.knoepfe, "eintritt_in_phase", lambda *a, **k: None)
    tg = TG()
    assert phasen.warnungen(conn, 1, 5)
    befehle.wechsle_phase(conn, tg, None, E(), 1, 5)
    assert phasen.aktuelle(conn, 1) == 5
    assert any(t.startswith(phasen.T._WARNUNG_PHASE_KOPF.format(phase=5)) for t in tg.gesendet)


def test_keine_warnung_wenn_voraussetzung_erfuellt(conn, monkeypatch):
    monkeypatch.setattr(phasen, "voraussetzungen", lambda c, i: {5: True})
    assert phasen.warnungen(conn, 1, 5) == []

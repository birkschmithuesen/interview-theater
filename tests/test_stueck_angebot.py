from interview_theater import knoepfe, repo, stagescript, stueck
from interview_theater.knoepfe import szenen as ks, wirkung
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def _druck(tg, klm, wert):
    return wirkung.Druck(tg=tg, klm=klm, e=E(), knopf={"wert": wert}, chat_id=1)


def _veraltet(conn):
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 in the Bar.", None)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    return sid


def test_angebot_einmal_mit_ja_nein(conn):
    _veraltet(conn)
    tg = TG()
    assert ks.biete_veraltete(conn, tg, E(), 1) == 1
    assert "Piazza" in tg.gesendet[-1] and "1" in tg.gesendet[-1]
    assert ks.biete_veraltete(conn, tg, E(), 1) == 0


def test_nein_laesst_text_stehen(conn):
    sid = _veraltet(conn)
    [v] = repo.offene_veraltet(conn, 1)
    wirkung._wirkung_veraltet_lassen(conn, _druck(TG(), None, str(v["id"])))
    assert repo.offene_veraltet(conn, 1) == []
    assert repo.hole_szene(conn, sid)["volltext"] == "SCENE 1 in the Bar."


def test_ja_startet_den_schreiblauf(conn, monkeypatch):
    _veraltet(conn)
    aufrufe = []
    monkeypatch.setattr(stagescript, "starte", lambda *a, **k: aufrufe.append((a[5], k.get("notiz"))))
    [v] = repo.offene_veraltet(conn, 1)
    wirkung._wirkung_veraltet_neu(conn, _druck(TG(), object(), str(v["id"])))
    assert aufrufe and aufrufe[0][0] == 1 and "Piazza" in aufrufe[0][1]
    assert repo.offene_veraltet(conn, 1) == []


def test_ja_beim_kopf_leert_den_kopf(conn, monkeypatch):
    _veraltet(conn)
    repo.setze_arbeitsstand(conn, 1, "stage_kopf", "Kopf")
    vid = repo.merke_veraltet(conn, 1, None, "kopf", "neuer Rahmen", None)
    aufrufe = []
    monkeypatch.setattr(stagescript, "starte", lambda *a, **k: aufrufe.append(a[5]))
    wirkung._wirkung_veraltet_neu(conn, _druck(TG(), object(), str(vid)))
    assert aufrufe == [1]
    assert not repo.hole_arbeitsstand(conn, 1)["stage_kopf"]


def test_neu_geschriebener_text_erledigt_den_vermerk(conn, einst):
    sid = _veraltet(conn)
    stagescript._speichere_text(conn, None, einst, 1, repo.hole_szene(conn, sid),
                                "SCENE 1 on the Piazza.", False)
    assert repo.offene_veraltet(conn, 1) == []


def test_knopfarten_registriert():
    assert knoepfe.ART_VERALTET_NEU in knoepfe._WIRKUNGEN
    assert knoepfe.ART_VERALTET_LASSEN in knoepfe._WIRKUNGEN

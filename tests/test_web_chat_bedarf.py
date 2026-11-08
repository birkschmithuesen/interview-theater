"""Server-Seite der Bedarfsliste (Birk 08.10.2026 ~13:45, Padua): der eine
schmale POST-Weg, der ein Abhaken auch bei read-only Werkbank
(``workbench_bearbeitbar = false``) zulaesst -- ueber ``/g/<token>/chat/bedarf``
statt des alten, gesperrten ``/g/<token>``-Weges (``web_schreiben.py``)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 7_000_000_000_001
ANDERE_CHAT = 7_000_000_000_002
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    punkt_id = repo.ersetze_unerledigte_bedarf_punkte(
        conn, CHAT, [("Props", ["Chair"])]
    )
    # Die id des angelegten Punktes lesen, statt sie zu raten.
    punkt_id = repo.bedarf(conn, CHAT)[0]["id"]
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad, punkt_id
    dienst.shutdown()


def _post(basis, token, koerper, nonce=None):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/bedarf",
        data=json.dumps({"nonce": nonce if nonce is not None else web.nonce(SCHLUESSEL, token),
                          **koerper}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return urllib.request.urlopen(anfrage, timeout=5)


def test_abhaken_setzt_erledigt_am(aufbau):
    basis, token, pfad, punkt_id = aufbau
    antwort = _post(basis, token, {"punkt_id": punkt_id, "erledigt": True})
    assert antwort.status == 200
    assert json.loads(antwort.read().decode("utf-8")) == {"ok": True}

    conn = db.verbinde(pfad)
    punkte = repo.bedarf(conn, CHAT)
    assert punkte[0]["erledigt_am"] is not None


def test_abhaken_zurueck_loescht_erledigt_am(aufbau):
    basis, token, pfad, punkt_id = aufbau
    _post(basis, token, {"punkt_id": punkt_id, "erledigt": True})

    antwort = _post(basis, token, {"punkt_id": punkt_id, "erledigt": False})

    assert antwort.status == 200
    conn = db.verbinde(pfad)
    punkte = repo.bedarf(conn, CHAT)
    assert punkte[0]["erledigt_am"] is None


def test_falscher_nonce_liefert_403(aufbau):
    basis, token, pfad, punkt_id = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, {"punkt_id": punkt_id, "erledigt": True}, nonce="falsch")
    assert fehler.value.code == 403

    conn = db.verbinde(pfad)
    assert repo.bedarf(conn, CHAT)[0]["erledigt_am"] is None


def test_fremder_punkt_id_liefert_404(aufbau):
    basis, token, pfad, punkt_id = aufbau
    repo.sichere_gruppe(db.verbinde(pfad), ANDERE_CHAT, "gruppe2", "Andere Gruppe")
    conn = db.verbinde(pfad)
    fremder_id = repo.ersetze_unerledigte_bedarf_punkte(
        conn, ANDERE_CHAT, [("Props", ["Foreign chair"])]
    )
    fremder_id = repo.bedarf(conn, ANDERE_CHAT)[0]["id"]
    conn.commit()

    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, {"punkt_id": fremder_id, "erledigt": True})
    assert fehler.value.code == 404

    assert repo.bedarf(conn, ANDERE_CHAT)[0]["erledigt_am"] is None


def test_unbekannte_punkt_id_liefert_404(aufbau):
    basis, token, pfad, punkt_id = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, {"punkt_id": 999999, "erledigt": True})
    assert fehler.value.code == 404


def test_ungueltiger_erledigt_wert_liefert_400(aufbau):
    basis, token, pfad, punkt_id = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, {"punkt_id": punkt_id, "erledigt": "ja"})
    assert fehler.value.code == 400


def test_funktioniert_trotz_read_only_werkbank(aufbau, monkeypatch):
    """Die Kernzusage: ``workbench_bearbeitbar = false`` blockt den alten
    ``/g/<token>``-Weg (403), der neue ``/g/<token>/chat/bedarf``-Weg bleibt
    trotzdem offen -- er laeuft nie durch ``web_schreiben.beantworte_post``."""
    from interview_theater import workshop

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    try:
        assert workshop.workbench_bearbeitbar() is False
        basis, token, pfad, punkt_id = aufbau
        antwort = _post(basis, token, {"punkt_id": punkt_id, "erledigt": True})
        assert antwort.status == 200
    finally:
        workshop.vergiss()

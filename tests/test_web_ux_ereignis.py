"""``POST /g/<token>/chat/ereignis`` -- die Charge UX-Ereignisse aus dem
Browser (Karte t_10a31406). Fire-and-forget vom Client: kein Modellaufruf,
kein Knopf, nur Validierung (Groesse, Rate, kein Freitextfeld) und ein
INSERT je gueltigem Ereignis. Nur mit dem Profilschalter
``[ux] ereignisse`` -- ohne ihn ist der Weg 404 (Dortmund unberuehrt)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_grenze, workshop

CHAT = 7_000_000_000_061
SCHLUESSEL = b"y" * 32


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token


@pytest.fixture
def server(datenbank):
    pfad, token = datenbank
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


@pytest.fixture(autouse=True)
def profil_an_und_grenze_leer(monkeypatch):
    monkeypatch.setattr(workshop, "ux_ereignisse_aktiv", lambda *a, **k: True)
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


def _post(url, nutzlast):
    anfrage = urllib.request.Request(
        url, data=json.dumps(nutzlast).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _gespeicherte_ereignisse(pfad):
    conn = db.verbinde(pfad)
    try:
        return repo.hole_ux_ereignisse(conn, CHAT)
    finally:
        conn.close()


def _charge(n=1, **override):
    basis = {"typ": "klick", "ziel": "knopf:stift", "t": 1000}
    basis.update(override)
    return {"geraet": "g-abc123", "ereignisse": [dict(basis) for _ in range(n)]}


# -- Normalfall ---------------------------------------------------------------


def test_ereignis_post_speichert_eine_gueltige_charge(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis",
                      dict(_charge(), nonce=web.nonce(SCHLUESSEL, token)))
    assert status == 200
    assert len(_gespeicherte_ereignisse(pfad)) == 1


def test_ereignis_post_speichert_mehrere_ereignisse_in_einer_charge(server):
    basis, token, pfad = server
    nutzlast = dict(_charge(n=3), nonce=web.nonce(SCHLUESSEL, token))
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    assert status == 200
    assert len(_gespeicherte_ereignisse(pfad)) == 3


# -- Profilschalter: aus heisst 404, Dortmund unberuehrt ---------------------


def test_ereignis_post_ohne_profilschalter_ist_404(server, monkeypatch):
    monkeypatch.setattr(workshop, "ux_ereignisse_aktiv", lambda *a, **k: False)
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis",
                      dict(_charge(), nonce=web.nonce(SCHLUESSEL, token)))
    assert status == 404
    assert _gespeicherte_ereignisse(pfad) == []


# -- Nonce --------------------------------------------------------------------


def test_ereignis_post_ohne_nonce_ist_403(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", _charge())
    assert status == 403
    assert _gespeicherte_ereignisse(pfad) == []


# -- Groessen-/Zahlgrenzen: <= 50 Ereignisse, <= 2 KB -------------------------


def test_ereignis_post_ueber_der_hoechstzahl_ist_400_und_speichert_nichts(server):
    basis, token, pfad = server
    nutzlast = dict(_charge(n=repo.MAX_UX_EVENTS_JE_BATCH + 1),
                    nonce=web.nonce(SCHLUESSEL, token))
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    assert status == 400
    assert _gespeicherte_ereignisse(pfad) == []


def test_ereignis_post_genau_an_der_hoechstzahl_geht_durch(server):
    basis, token, pfad = server
    # Minimale Ereignisse, damit die 2-KB-Grenze bei 50 Stueck nicht
    # VOR der Zaehlgrenze greift -- beide Grenzen werden unabhaengig
    # geprueft (siehe test_ereignis_post_ueber_2kb_ist_400...).
    nutzlast = dict(_charge(n=repo.MAX_UX_EVENTS_JE_BATCH, ziel="k", t=1),
                    nonce=web.nonce(SCHLUESSEL, token))
    assert len(json.dumps(nutzlast["ereignisse"]).encode("utf-8")) <= repo.MAX_UX_BATCH_BYTES
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    assert status == 200
    assert len(_gespeicherte_ereignisse(pfad)) == repo.MAX_UX_EVENTS_JE_BATCH


def test_ereignis_post_ueber_2kb_ist_400_und_speichert_nichts(server):
    basis, token, pfad = server
    # Ein einzelnes Ereignis mit einer langen (aber fuer sich erlaubten)
    # msg-Diagnosezeile mehrfach wiederholt sprengt die 2-KB-Grenze, ohne
    # die 50er-Zaehlgrenze zu beruehren.
    gross = {"typ": "js_fehler", "ziel": "fenster", "t": 1,
             "extra": {"msg": "x" * 160}}
    nutzlast = {"geraet": "g-abc123", "ereignisse": [dict(gross) for _ in range(20)],
                "nonce": web.nonce(SCHLUESSEL, token)}
    assert len(json.dumps(nutzlast["ereignisse"]).encode("utf-8")) > 2048
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    assert status == 400
    assert _gespeicherte_ereignisse(pfad) == []


# -- kein Freitext-/Transkriptinhalt, auch nicht an der HTTP-Grenze ----------


@pytest.mark.parametrize("schmuggel", [
    {"text": "Freitext aus dem Chat"},
    {"transkript": "woertliches Interviewmaterial"},
])
def test_ereignis_post_speichert_kein_freitextfeld_aus_extra(server, schmuggel):
    basis, token, pfad = server
    nutzlast = dict(_charge(extra=schmuggel), nonce=web.nonce(SCHLUESSEL, token))
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    assert status == 200
    ereignisse = _gespeicherte_ereignisse(pfad)
    assert len(ereignisse) == 1
    assert ereignisse[0]["extra"] == {}


def test_ereignis_post_mit_unbekanntem_typ_speichert_dieses_ereignis_nicht(server):
    basis, token, pfad = server
    nutzlast = dict(_charge(typ="irgendwas_freies"), nonce=web.nonce(SCHLUESSEL, token))
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis", nutzlast)
    # fire-and-forget: die Antwort ist trotzdem 200, nur ohne Zeile.
    assert status == 200
    assert _gespeicherte_ereignisse(pfad) == []


# -- Rate-Limit: eigener Topf, zaehlt nicht gegen das Sende-Limit ------------


def test_ereignis_post_eigener_rate_limit_topf(server):
    basis, token, pfad = server
    url = f"{basis}/g/{token}/chat/ereignis"
    for _ in range(web_grenze.GRENZEN[web_grenze.TOPF_UX][0]):
        status, _antwort = _post(url, dict(_charge(), nonce=web.nonce(SCHLUESSEL, token)))
        assert status == 200
    status, _ = _post(url, dict(_charge(), nonce=web.nonce(SCHLUESSEL, token)))
    assert status == 429


def test_ereignis_post_laesst_das_sende_limit_unberuehrt(server):
    basis, token, pfad = server
    url = f"{basis}/g/{token}/chat/ereignis"
    for _ in range(web_grenze.GRENZEN[web_grenze.TOPF_UX][0]):
        _post(url, dict(_charge(), nonce=web.nonce(SCHLUESSEL, token)))
    # Das ux-Limit ist jetzt voll -- der Senden-Topf derselben Gruppe nicht.
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, CHAT) == 0


# -- Grundformat der Nutzlast -------------------------------------------------


@pytest.mark.parametrize("nutzlast", [
    {"geraet": "g-abc123"},
    {"ereignisse": [{"typ": "klick", "ziel": "knopf:stift", "t": 1}]},
    {"geraet": "g-abc123", "ereignisse": "kein array"},
    {"geraet": 123, "ereignisse": [{"typ": "klick", "ziel": "knopf:stift", "t": 1}]},
])
def test_ereignis_post_lehnt_falsches_grundformat_ab(server, nutzlast):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/ereignis",
                      dict(nutzlast, nonce=web.nonce(SCHLUESSEL, token)))
    assert status == 400
    assert _gespeicherte_ereignisse(pfad) == []

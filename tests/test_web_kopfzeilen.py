"""Angriff: was verraet der Server, und was fehlt an Kopfzeilen?

Vier Angriffe in einer Datei, weil sie dieselbe Antwort haerten:
  1. Es gibt keine Sicherheitskopfzeilen -- eine fremde Seite darf uns in
     einen iframe stellen, ein Crawler darf uns indizieren, der Browser darf
     den Content-Type raten.
  2. Der Server-Header nennt die Python-Version.
  3. Eine Ausnahme im Handler erzeugt heute gar keine Antwort
     (RemoteDisconnected); der Traceback geht nach stderr. Verlangt ist eine
     500 mit festem Kurztext.
  4. Die 404-Seite und die Download-Routen fallen heute aus jeder
     Kopfzeilen-Regel heraus, weil sie an _antworte vorbei oder durch
     send_error laufen.

Gemessen gegen einen echten lokalen ThreadingHTTPServer auf Port 0, wie
tests/test_web_edit.py -- kein Netz nach draussen.
"""

import http.client
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 1
SCHLUESSEL = b"x" * 32

#: Die sechs Kopfzeilen, die auf JEDER Antwort stehen muessen.
PFLICHT = {
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=(self)",
}


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url: str):
    """Statuscode und Kopfzeilen -- auch fuer 4xx/5xx, die urllib wirft."""
    try:
        with urllib.request.urlopen(url, timeout=10) as antwort:
            return antwort.status, dict(antwort.headers), antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, dict(fehler.headers), fehler.read().decode("utf-8")


def _rohanfrage(basis: str, zeile: bytes) -> tuple[int, dict]:
    """Eine Anfrage, die urllib gar nicht erst stellen wuerde -- fuer den
    send_error-Weg der Standardbibliothek (unbekannte Methode -> 501)."""
    wirt, port = basis.removeprefix("http://").split(":")
    verbindung = http.client.HTTPConnection(wirt, int(port), timeout=10)
    verbindung.request("BREW", "/")
    antwort = verbindung.getresponse()
    kopf = dict(antwort.getheaders())
    antwort.read()
    verbindung.close()
    return antwort.status, kopf


# -- 1. Die Kopfzeilen auf jeder Route ------------------------------------


def test_jede_route_traegt_die_pflichtkopfzeilen(aufbau):
    basis, token, _pfad = aufbau
    wege = [
        "/gesund", "/", f"/g/{token}", f"/g/{token}/textbuch",
        f"/g/{token}/leitfaden", f"/g/{token}/textbuch.md",
        f"/g/{token}/textbuch.txt",
        "/g/gibtsnicht", "/nixda", f"/theatersoap/g/{token}",
    ]
    for weg in wege:
        _status, kopf, _text = _hole(basis + weg)
        for name, wert in PFLICHT.items():
            assert kopf.get(name) == wert, (weg, name, kopf.get(name))


def test_auch_die_fehlerseiten_tragen_sie(aufbau):
    """404 laeuft ueber _antworte, 501 ueber send_error der
    Standardbibliothek -- beide muessen dieselben Kopfzeilen tragen, sonst
    ist die Einhaengung an der falschen Stelle."""
    basis, _token, _pfad = aufbau
    status, kopf, _text = _hole(basis + "/nixda")
    assert status == 404
    assert kopf.get("X-Frame-Options") == "DENY"

    status, kopf = _rohanfrage(basis, b"BREW / HTTP/1.1\r\n\r\n")
    assert status == 501
    for name, wert in PFLICHT.items():
        assert kopf.get(name) == wert, (name, kopf.get(name))


# -- 2. Die Richtlinie ohne Fremdquellen ----------------------------------


def test_csp_ohne_fremdquelle_und_mit_den_vier_sperren(aufbau):
    basis, token, _pfad = aufbau
    _status, kopf, _text = _hole(f"{basis}/g/{token}")
    csp = kopf.get("Content-Security-Policy") or ""
    for stueck in ("default-src 'none'", "frame-ancestors 'none'",
                   "base-uri 'none'", "form-action 'self'",
                   "connect-src 'self'", "media-src 'self' blob:"):
        assert stueck in csp, (stueck, csp)
    assert "http://" not in csp and "https://" not in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_der_csp_nonce_steht_an_jedem_inline_tag(aufbau):
    basis, token, _pfad = aufbau
    _status, kopf, text = _hole(f"{basis}/g/{token}")
    csp = kopf.get("Content-Security-Policy") or ""
    marke = csp.split("'nonce-", 1)[1].split("'", 1)[0]
    assert len(marke) >= 16
    assert text.count("<script") == text.count(f'nonce="{marke}"') - text.count("<style")
    assert f'<style nonce="{marke}">' in text
    assert f'<script nonce="{marke}">' in text


def test_der_nonce_bleibt_innerhalb_der_stunde_gleich(aufbau):
    """Der Kern: ein je Antwort gewuerfelter Nonce stuende im <body> und
    liesse das sanfte Nachladen die Seite alle zehn Sekunden austauschen
    (web._SCROLL_JS vergleicht document.body.innerHTML)."""
    basis, token, _pfad = aufbau
    _s1, _k1, erste = _hole(f"{basis}/g/{token}")
    _s2, _k2, zweite = _hole(f"{basis}/g/{token}")
    assert erste == zweite


def test_der_nonce_wechselt_mit_dem_fenster():
    a = web.csp_nonce(SCHLUESSEL, "tok", jetzt=0.0)
    b = web.csp_nonce(SCHLUESSEL, "tok", jetzt=web.NONCE_FENSTER + 1.0)
    assert a != b


def test_csp_nonce_ist_nicht_der_formular_nonce():
    """Zwei Geheimnisse, zwei Ableitungen: ein Leck des einen (der
    Formular-Nonce stand bei A2 in der Query und damit in der Logzeile) darf
    den anderen nicht mitnehmen."""
    assert web.csp_nonce(SCHLUESSEL, "tok", 0.0) != web.nonce(SCHLUESSEL, "tok", 0.0)


def test_mit_nonce_ruehrt_escapten_text_nicht_an():
    """Eine Gruppennachricht mit dem Wort <script> ist beim Rendern
    escaped -- die Ersetzung darf sie nicht treffen."""
    roh = "<style>a{}</style><p>&lt;script&gt;boese&lt;/script&gt;</p><script>x</script>"
    ergebnis = web.mit_nonce(roh, "abc")
    assert ergebnis.count('nonce="abc"') == 2
    assert "&lt;script&gt;boese&lt;/script&gt;" in ergebnis


# -- 3. Der Server verraet seine Version nicht ----------------------------


def test_server_header_ohne_versionsnummer(aufbau):
    basis, _token, _pfad = aufbau
    _status, kopf, _text = _hole(basis + "/gesund")
    assert kopf.get("Server") == "interview-theater"
    assert "Python" not in (kopf.get("Server") or "")
    assert "." not in (kopf.get("Server") or "")


# -- 4. Die Fehlerseite verraet nichts ------------------------------------


def test_ausnahme_im_handler_wird_500_ohne_traceback(aufbau, monkeypatch):
    """Heute: gar keine Antwort (RemoteDisconnected), Traceback nach stderr.
    Verlangt: 500 mit festem Kurztext -- kein 'Traceback', kein '/mnt/',
    kein '.py'."""
    basis, _token, _pfad = aufbau

    def kaputt(*args, **kwargs):
        raise RuntimeError("geheim /mnt/HC_Volume/pfad.py Zeile 7")

    monkeypatch.setattr(web, "dashboard_html", kaputt)
    status, kopf, text = _hole(basis + "/")
    assert status == 500
    assert web.TEXT_500 in text
    for verbotenes in ("Traceback", "/mnt/", ".py", "RuntimeError", "geheim"):
        assert verbotenes not in text, verbotenes
    assert kopf.get("X-Frame-Options") == "DENY"


def test_ausnahme_im_post_wird_ebenfalls_500(aufbau, monkeypatch):
    basis, token, _pfad = aufbau

    def kaputt(*args, **kwargs):
        raise RuntimeError("geheim /mnt/x.py")

    monkeypatch.setattr(web, "_beantworte_post", kaputt)
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            status, text = antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        status, text = fehler.code, fehler.read().decode("utf-8")
    assert status == 500
    assert "Traceback" not in text and "/mnt/" not in text


def test_send_error_gibt_keine_erklaerung_preis(aufbau):
    """Die Vorlage der Standardbibliothek setzt Message und Explain in den
    Koerper (DEFAULT_ERROR_MESSAGE). Beides raus."""
    basis, _token, _pfad = aufbau
    status, _kopf = _rohanfrage(basis, b"BREW / HTTP/1.1\r\n\r\n")
    assert status == 501
    verbindung = http.client.HTTPConnection(
        basis.removeprefix("http://").split(":")[0],
        int(basis.rsplit(":", 1)[1]), timeout=10,
    )
    verbindung.request("BREW", "/")
    antwort = verbindung.getresponse()
    koerper = antwort.read().decode("utf-8", "replace")
    verbindung.close()
    assert "Error code explanation" not in koerper
    assert "Unsupported method" not in koerper
    assert web.TEXT_500 in koerper or koerper.strip() == ""

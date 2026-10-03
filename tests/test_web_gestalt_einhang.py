"""Der CSP-Vertrag am AUSGELIEFERTEN HTML -- nicht an einer Konstante.

Das ist der Unterschied zu ``test_web_gestalt_css.py``: dort wird der
Quelltext des Moduls gemessen, hier die Seite, die wirklich ueber die
Leitung geht. Ein ``style="…"``-Attribut, das erst beim Zusammenbau
entsteht, faellt nur hier auf -- und in Padua waere es eine Seite ohne
Gestaltung, weil die Richtlinie aus Karte S es blockt.
"""

import inspect
import re
import threading
import urllib.request

import pytest

from interview_theater import db, repo, web, web_gestalt

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32

STIL_ATTRIBUT = re.compile(r"<[^>]*\sstyle\s*=")
EREIGNIS_ATTRIBUT = re.compile(r"<[^>]*\son[a-z]+\s*=")


@pytest.fixture
def dienst(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "We are from the theatre.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam mit einem Koffer")
    nummer = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis", None, None)
    repo.aktualisiere_szene(conn, nummer, "Ankunft am Gleis", None,
                            volltext="MERYEM: Ich bin da.\nERHAN: Endlich.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    server = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap",
                             schluessel=SCHLUESSEL)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", token
    server.shutdown()


def _hole(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.read().decode("utf-8")


@pytest.fixture(params=[
    "",
    pytest.param("/textbuch", marks=pytest.mark.xfail(
        reason="Gestaltung haengt dort erst in Aufgabe 10 ein", strict=False)),
    pytest.param("/leitfaden", marks=pytest.mark.xfail(
        reason="Gestaltung haengt dort erst in Aufgabe 10 ein", strict=False)),
])
def seite(request, dienst):
    basis, token = dienst
    return _hole(f"{basis}/g/{token}{request.param}")


# -- Der CSP-Vertrag ---------------------------------------------------------


def test_kein_style_attribut_im_ausgelieferten_html(seite):
    """``style-src 'nonce-…'`` ohne ``'unsafe-inline'``: ein
    ``style="…"``-Attribut waere im Browser wirkungslos."""
    assert not STIL_ATTRIBUT.search(seite)


def test_kein_ereignisattribut_im_ausgelieferten_html(seite):
    """``onclick=`` waere aus demselben Grund tot -- und ein offenes Tor,
    wenn jemals ``'unsafe-inline'`` dazukaeme."""
    assert not EREIGNIS_ATTRIBUT.search(seite)


def test_keine_fremdquelle_im_ausgelieferten_html(seite):
    for verboten in ("http://", "https://", "@font-face", "@import"):
        assert verboten not in seite, verboten


def test_das_skript_setzt_dynamische_werte_ueber_cssom(seite):
    """``el.style.setProperty`` ist unter der Richtlinie erlaubt,
    ``setAttribute('style', …)`` nicht. Der Unterschied ist eine Zeile und
    faellt sonst erst im Browser auf."""
    assert "setProperty(" in seite
    assert "setAttribute('style'" not in seite
    assert 'setAttribute("style"' not in seite


# -- Die Reihenfolge ---------------------------------------------------------


def test_die_gestaltung_steht_zuletzt_im_style(dienst):
    """Sonst gewinnt bei gleicher Spezifitaet das CSS aus A2/W."""
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    stil = re.search(r"<style[^>]*>(.*?)</style>", html, flags=re.S).group(1)
    assert stil.index("--rec-hoehe") > stil.index(".panel-chat")


def test_die_tokens_des_aktiven_entwurfs_stehen_drin(dienst):
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    tokens = web_gestalt.TOKENS[web_gestalt.entwurf()]
    assert f"--grund: {tokens['grund']};" in html
    assert f"--signal: {tokens['signal']};" in html


@pytest.mark.xfail(
    reason="web_gestalt.css_chat() ist bis Aufgabe 5/8 leer (_CHAT_A/_CHAT_B) "
    "und traegt noch keine eigene #interview-Regel; bis dahin geht die "
    "Reihenfolge zugunsten von test_die_gestaltung_steht_zuletzt_im_style "
    "(der allgemeinen 'Gestaltung zuletzt'-Pflicht)",
    strict=False,
)
def test_das_chat_css_der_gestaltung_ist_gescopt(dienst):
    """Ungescopt waere ``#interview`` (0,1,0,0) schwaecher als das schon
    gescopte ``.panel-chat #interview`` (0,1,1,0) aus ``_CSS_CHAT``."""
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    stil = re.search(r"<style[^>]*>(.*?)</style>", html, flags=re.S).group(1)
    nach = stil[stil.index("--rec-hoehe"):]
    assert ".panel-chat #interview" in nach


# -- Was die Gestaltung NICHT tut -------------------------------------------


def test_die_gestaltung_fasst_keine_daten_an():
    """Sie ist Gestaltung: kein SQL, kein Material, kein Zitat."""
    quelle = inspect.getsource(web_gestalt)
    for verboten in ("SELECT", "INSERT", "UPDATE", "DELETE", "sqlite3",
                     "import repo", "import web_daten", "import db"):
        assert verboten not in quelle, verboten


def test_kein_modellaufruf_in_der_gestaltung():
    quelle = inspect.getsource(web_gestalt)
    for verboten in ("import llm", "import httpx", "import stt", "anthropic"):
        assert verboten not in quelle, verboten

"""Der Webserver, ueber echtes HTTP.

Startet ihn auf 127.0.0.1:0 in einem Thread und ruft ihn mit urllib ab --
kein Netzzugriff nach draussen. Ueber HTTP statt ueber die Renderfunktionen
allein, weil hier die Verdrahtung geprueft wird: Routing, Statuscodes, das
Praefix und die read-only geoeffnete Datenbank.
"""

import threading
import urllib.error
import urllib.request

import pytest
from theatersoap import db, repo, web


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Maria", "kam 1998")
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema ist Ankommen", "extraktor")
    # Die Verbindung bleibt absichtlich offen: sie haelt die WAL-Dateien am
    # Leben, so wie im Betrieb der Bot-Prozess.
    conn.commit()
    return pfad


@pytest.fixture
def token(db_pfad):
    conn = db.verbinde(db_pfad)
    return repo.stelle_web_token_sicher(conn, 1)


@pytest.fixture
def basis(db_pfad):
    """Ein laufender Server auf einem freien Port; liefert seine Basis-URL."""
    server = web.baue_server(db_pfad, bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def hole(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_gesund_antwortet_ok(basis):
    status, koerper = hole(f"{basis}/gesund")
    assert status == 200
    assert koerper.strip() == "ok"


def test_dashboard_zeigt_die_gruppentitel(basis):
    status, koerper = hole(f"{basis}/")
    assert status == 200
    assert "Die Ankommenden" in koerper
    assert "Bot-Zuordnung" in koerper
    assert 'http-equiv="refresh"' in koerper


def test_gruppenseite_zeigt_das_kernthema(basis, token):
    status, koerper = hole(f"{basis}/g/{token}")
    assert status == 200
    assert "Ankommen" in koerper
    assert "Maria" in koerper
    assert "Kernthema ist Ankommen" in koerper


def test_unbekanntes_token_gibt_404_ohne_hinweis(basis):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g/falsch")
    assert fehler.value.code == 404
    koerper = fehler.value.read().decode("utf-8")
    assert "Die Ankommenden" not in koerper, "verraet nicht, dass es Gruppen gibt"


def test_unbekannter_pfad_gibt_404(basis):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/admin")
    assert fehler.value.code == 404


def test_routen_gehen_auch_mit_nginx_praefix(basis, token):
    """Ob nginx /theatersoap weiterreicht oder abschneidet, steht in der
    nginx-Konfiguration -- der Server nimmt deshalb beide Formen."""
    assert hole(f"{basis}/theatersoap/")[0] == 200
    assert hole(f"{basis}/theatersoap/gesund")[1].strip() == "ok"
    assert "Ankommen" in hole(f"{basis}/theatersoap/g/{token}")[1]


def test_alles_aus_der_datenbank_wird_maskiert(basis, db_pfad, token):
    """Gruppentitel und Kernthema kommen aus Telegram bzw. aus einem
    Sprachmodell. Was da an spitzen Klammern ankommt, darf im Browser kein
    Skript werden."""
    conn = db.verbinde(db_pfad)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "<script>alert(1)</script>")
    repo.sichere_gruppe(conn, 1, "gruppe1", "<img src=x onerror=alert(2)>")

    for url in (f"{basis}/", f"{basis}/g/{token}"):
        koerper = hole(url)[1]
        assert "<script>alert(1)</script>" not in koerper
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in koerper
        # Der Text darf dastehen, das Tag nicht: entscheidend ist die spitze
        # Klammer, nicht das Wort onerror.
        assert "<img" not in koerper
        assert "&lt;img src=x onerror=alert(2)&gt;" in koerper


def test_dashboard_zeigt_keinen_nachrichtentext(basis, db_pfad):
    conn = db.verbinde(db_pfad)
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "Meine Mutter starb 1998",
                         "2026-09-05T10:00:00+00:00")
    assert "Meine Mutter" not in hole(f"{basis}/")[1]


def test_der_server_schreibt_nicht_in_die_datenbank(basis, db_pfad, token):
    """Der einzige Schreibweg bleibt der Chat. Geprueft an der Datei selbst:
    nach Abrufen beider Seiten steht in der Datenbank nichts Neues."""
    conn = db.verbinde(db_pfad)
    vorher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    hole(f"{basis}/")
    hole(f"{basis}/g/{token}")
    nachher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    assert vorher == nachher


def test_leere_datenbank_ergibt_trotzdem_eine_seite(tmp_path):
    """Am Workshopmorgen hat noch keine Gruppe geschrieben -- das Dashboard
    muss trotzdem stehen, sonst sieht das Team einen Fehler statt einer
    leeren Seite."""
    pfad = str(tmp_path / "leer.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    server = web.baue_server(pfad, bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, koerper = hole(f"http://127.0.0.1:{server.server_address[1]}/")
        assert status == 200
        assert "Noch keine Gruppe" in koerper
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_fehlende_datenbank_gibt_500_statt_abzustuerzen(tmp_path):
    server = web.baue_server(str(tmp_path / "gibtsnicht.db"), bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        basis = f"http://127.0.0.1:{server.server_address[1]}"
        assert hole(f"{basis}/gesund")[1].strip() == "ok", "Health-Check ohne DB"
        with pytest.raises(urllib.error.HTTPError) as fehler:
            hole(f"{basis}/")
        assert fehler.value.code == 500
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("bind", ["0.0.0.0:8010", ":::8010", "8010", "127.0.0.1:abc"])
def test_unbrauchbare_bindadressen_werden_abgelehnt(bind, tmp_path):
    """0.0.0.0 waere ein Tippfehler mit Folgen: die Gruppenseiten haben kein
    Login, und in den Interviews stehen Lebensgeschichten."""
    with pytest.raises(RuntimeError):
        web.baue_server(str(tmp_path / "t.db"), bind=bind)


def test_bind_wird_zerlegt():
    assert web.lies_bind("100.75.24.33:8010") == ("100.75.24.33", 8010)
    assert web.lies_bind("127.0.0.1:0") == ("127.0.0.1", 0)


def test_praefix_wird_nur_am_anfang_abgeschnitten():
    assert web._pfad_ohne_praefix("/theatersoap/g/abc", "/theatersoap") == "/g/abc"
    assert web._pfad_ohne_praefix("/theatersoap", "/theatersoap") == "/"
    assert web._pfad_ohne_praefix("/g/abc", "/theatersoap") == "/g/abc"
    assert web._pfad_ohne_praefix("/g/theatersoap", "/theatersoap") == "/g/theatersoap"

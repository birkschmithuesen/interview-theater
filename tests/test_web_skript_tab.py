"""Der Textbuch-/Script-Tab zeigt frühere Fassungen und die Erstfassung vor
der Prüfung (Padua Phasen TEIL 2, Aufgabe 12) -- read-only, CSP-sauber."""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, sprache, web, web_daten, workshop

CHAT = 7_000_000_000_001

ERSTFASSUNG = "Mira steht am Steg und wartet, bis das Boot nicht kommt."
ZWISCHEN = "Mira steht am Steg. Das Boot kommt doch, aber leer."
AKTUELL = "Mira steht am Steg. Sie dreht sich um und geht."


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _baue(tmp_path, erstentwurf=True):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Am Steg", None, None)
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, None, prosa=AKTUELL)
    for text in (ERSTFASSUNG, ZWISCHEN, AKTUELL):
        repo.haenge_szenenfassung_an(conn, CHAT, szene_id, text)
    if erstentwurf:
        repo.setze_szene_erstentwurf(conn, szene_id, 1)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token, szene_id


def _daten(pfad, token):
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()


def _hole(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _vereint(pfad, token):
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        status, text = _hole(f"http://127.0.0.1:{dienst.server_address[1]}/g/{token}")
    finally:
        dienst.shutdown()
    assert status == 200
    return text


def _panel_textbuch(text):
    anfang = text.index('id="tab-textbuch"')
    ende = text.find('id="tab-', anfang + 1)
    return text[anfang: ende if ende != -1 else len(text)]


def test_prosa_it_zeigt_en_und_it_block_getrennt(tmp_path, padua):
    """Birk, Live-Workshop 07.10.2026 ~17:20: Script-Tab zweisprachig statt
    gemischt. Mit ``prosa_it`` gesetzt (Spiegelpass gelaufen) stehen EN- und
    IT-Fassung als zwei eigene, beschriftete Bloecke -- die Kernsaetze
    (italienisches Zitat) wandern aus der sonst englischen Planungsliste
    in den IT-Block."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Al binario", None, None)
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Maria arrives")
    repo.setze_szenenfeld(conn, szene_id, "kernsaetze", "Non sono mai tornata")
    repo.aktualisiere_szene(
        conn, szene_id, "Al binario", None, None,
        prosa="Maria stands at the station.",
    )
    repo.setze_szene_uebersetzung(
        conn, szene_id, "Maria stands at the station.", "Maria sta alla stazione.",
    )
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    html = web.textbuch_html(_daten(pfad, token), token)

    assert "Maria stands at the station." in html
    assert "Maria sta alla stazione." in html
    assert "Non sono mai tornata" in html
    assert "As a story (English):" in html
    assert "As a story (Italiano):" in html
    assert "Key lines (Italiano, original):" in html
    # Die Kernsaetze stehen nicht mehr ein zweites Mal in der Planungsliste.
    assert html.count("Non sono mai tornata") == 1
    assert "Not written yet." not in html
    assert ' style="' not in html
    assert "onclick=" not in html


def test_ohne_prosa_it_bleibt_einsprachig(tmp_path, padua):
    """Ohne Spiegelpass (``prosa_it`` leer) bleibt die Ansicht wie bisher --
    eine Fassung, die alte Beschriftung."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Al binario", None, None)
    repo.setze_szenenfeld(conn, szene_id, "kernsaetze", "Non sono mai tornata")
    repo.aktualisiere_szene(
        conn, szene_id, "Al binario", None, None,
        prosa="Maria stands at the station.",
    )
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    html = web.textbuch_html(_daten(pfad, token), token)

    assert "As a story:" in html
    assert "As a story (English):" not in html
    assert "As a story (Italiano):" not in html
    assert "Key lines (Italiano, original):" not in html
    assert "Non sono mai tornata" in html  # weiter in der normalen Planungsliste


def test_erstentwuerfe_nur_wenn_gesetzt_und_verschieden(tmp_path):
    pfad, token, szene_id = _baue(tmp_path)
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        assert web_daten.erstentwuerfe(lesend, CHAT) == {szene_id: ERSTFASSUNG}
    finally:
        lesend.close()
    assert _daten(pfad, token)["erstentwuerfe"] == {szene_id: ERSTFASSUNG}


def test_erstentwurf_gleich_aktuellem_text_faellt_weg(tmp_path):
    pfad, token, szene_id = _baue(tmp_path, erstentwurf=False)
    conn = db.verbinde(pfad)
    repo.setze_szene_erstentwurf(conn, szene_id, 3)  # = AKTUELL
    conn.close()
    assert _daten(pfad, token)["erstentwuerfe"] == {}


def test_erstfassung_steht_im_textbuch_panel(tmp_path):
    pfad, token, _ = _baue(tmp_path)
    panel = _panel_textbuch(_vereint(pfad, token))
    assert 'class="erstentwurf"' in panel
    assert ERSTFASSUNG in panel
    assert web._TEXT_ERSTE_FASSUNG in panel
    assert 'class="fruehere"' in panel
    assert web._TEXT_FRUEHERE.format(anzahl=2) in panel
    assert ZWISCHEN in panel


def test_padua_englisch_und_csp_sauber(tmp_path, padua):
    pfad, token, _ = _baue(tmp_path)
    for html in (_vereint(pfad, token), web.textbuch_html(_daten(pfad, token), token)):
        assert "Earlier versions (2)" in html
        assert "First draft (before the check)" in html
        assert ' style="' not in html
        assert "onclick=" not in html


def test_probenansicht_traegt_beides(tmp_path):
    pfad, token, _ = _baue(tmp_path)
    html = web.textbuch_html(_daten(pfad, token), token)
    assert ERSTFASSUNG in html
    assert ZWISCHEN in html
    assert ' style="' not in html
    assert "onclick=" not in html


def test_ohne_erstentwurf_kein_block(tmp_path):
    pfad, token, _ = _baue(tmp_path, erstentwurf=False)
    daten = _daten(pfad, token)
    assert daten["erstentwuerfe"] == {}
    html = web.textbuch_html(daten, token)
    assert 'class="erstentwurf"' not in html
    assert 'class="erstentwurf"' not in _panel_textbuch(_vereint(pfad, token))


def test_eine_fassung_kein_fruehere_block(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Am Steg", None, AKTUELL)
    repo.haenge_szenenfassung_an(conn, CHAT, szene_id, AKTUELL)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    html = web.textbuch_html(_daten(pfad, token), token)
    assert 'class="fruehere"' not in html
    assert html.count(AKTUELL) == 1


def test_fruehere_texte_werden_maskiert(tmp_path):
    pfad, token, szene_id = _baue(tmp_path)
    conn = db.verbinde(pfad)
    repo.haenge_szenenfassung_an(conn, CHAT, szene_id, "<script>alert(1)</script>")
    repo.haenge_szenenfassung_an(conn, CHAT, szene_id, AKTUELL + " ")
    conn.close()
    html = web.textbuch_html(_daten(pfad, token), token)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html

"""Gruppenseite, Probenansicht, Leitfaden-Seite ohne deutsches Wort (D10d)."""

import pytest

from interview_theater import db, sprache, web, web_daten, workshop
from scripts import pruefe_sprache
from tests.fixture_sprache import baue_englische_gruppe


#: Die Phasennamen kommen aus dem Profil (``workshop/padua-2026/phasen.toml``),
#: und die schreibt erst Aufgabe 29 -- bis dahin traegt Padua die sieben
#: deutschen Stationen der Vorgabe, und die Gruppenseite zeigt "6 · Szenen als
#: Geschichte". Solange das so ist, stellt der Test die Namen, die Aufgabe 29
#: vorsieht; danach greift die Weiche nicht mehr und das Profil gilt selbst.
PHASEN_AUFGABE_29 = (
    (1, "Terms", ""), (2, "Questions", ""), (3, "Interviews", ""),
    (4, "Setting, Characters & Story", ""), (5, "Sharpening", ""),
    (6, "Scenes as Story", ""), (7, "Polish", ""),
)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    if workshop.phasenliste()[0][1] == "Begriffe":
        monkeypatch.setattr(workshop, "phasenliste", lambda profil=None: PHASEN_AUFGABE_29)
    yield
    workshop.vergiss()
    sprache.vergiss()


def _seiten(tmp_path):
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    lesend = web_daten.oeffne_lesend(pfad)       # web_daten.py:40, wie web.py:2653
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)          # web_daten.py:1066
        leitfaden = web_daten.leitfaden_nach_token(lesend, token)   # web_daten.py:1206
    finally:
        lesend.close()
    return {
        "gruppe": web.gruppe_html(daten, web.nonce(b"k", token), token),
        "textbuch": web.textbuch_html(daten, token),
        "leitfaden": web.leitfaden_html(leitfaden | {"token": token}),
    }


def test_padua_seiten_ohne_deutsch(tmp_path, padua):
    treffer = []
    for name, html in _seiten(tmp_path).items():
        treffer += pruefe_sprache.deutsche_treffer(f"web {name}", pruefe_sprache.nur_text(html))
    assert [f"{t.quelle}: {t.wort} | {t.ausschnitt}" for t in treffer] == []


def test_dortmund_seiten_schlagen_an(tmp_path):
    """Positivkontrolle: ohne sie prueft der erste Test womoeglich nichts."""
    treffer = []
    for name, html in _seiten(tmp_path).items():
        treffer += pruefe_sprache.deutsche_treffer(f"web {name}", pruefe_sprache.nur_text(html))
    assert treffer


def test_lang_attribut(tmp_path, padua):
    assert '<html lang="en">' in _seiten(tmp_path)["gruppe"]


# --- Ueber den Brief hinaus: was die drei Seiten nicht erfassen -------------


def test_padua_leseansicht_und_fehlerseite_ohne_deutsch(tmp_path, padua):
    """Die Gruppenseite ohne Nonce (Leseansicht, ``_arbeitsstand_html``) und
    die 404-Seite -- beide gehen an die Gruppe."""
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    treffer = []
    for name, html in (("lesen", web.gruppe_html(daten)), ("404", web.nicht_gefunden_html())):
        treffer += pruefe_sprache.deutsche_treffer(name, pruefe_sprache.nur_text(html))
    assert [f"{t.quelle}: {t.wort} | {t.ausschnitt}" for t in treffer] == []


def test_dashboard_bleibt_deutsch(padua):
    """Das Team-Dashboard wird nicht umgestellt (Brief Aufgabe 17)."""
    html = web.dashboard_html({"gruppen": [], "bot_zuordnung": [], "stand": None})
    assert '<html lang="de">' in html
    assert "Noch keine Gruppe hat geschrieben." in html


def test_speichermeldungen_kommen_aus_data_attributen(tmp_path, padua):
    """Das Skript traegt keinen Nutzertext mehr; die Meldungen stehen im
    <body> in der Sprache des Profils."""
    for deutsch in (web._JS_SICHER, web._JS_SPEICHERT, web._JS_FEHLER):
        assert deutsch not in web._BEARBEITEN_JS
    assert "melde(feld, 'gespeichert'" not in web._BEARBEITEN_JS
    html = _seiten(tmp_path)["gruppe"]
    assert 'data-sicher="Really remove?"' in html
    assert 'data-fehler="didn&#x27;t work"' in html


def test_web_fehler_auf_englisch(conn, padua):
    from interview_theater import web_schreiben

    with pytest.raises(web_schreiben.Fehler, match="^Unknown parameter: quatsch$"):
        web_schreiben.wende_an(conn, 1, "quatsch", "x", None)


def test_web_fehler_in_dortmund_unveraendert(conn):
    from interview_theater import web_schreiben

    with pytest.raises(web_schreiben.Fehler, match="^Unbekannter Parameter: quatsch$"):
        web_schreiben.wende_an(conn, 1, "quatsch", "x", None)


def test_jede_szenenfeld_beschriftung_hat_einen_eintrag():
    """``web_daten.SZENENFELDER`` beschriftet deutsch (web_daten hat keinen
    Sprachzugriff); ``web.SZENENFELD_BESCHRIFTUNG`` muss jedes Wort kennen,
    sonst bliebe es in Padua stumm deutsch."""
    assert {label for _, label in web_daten.SZENENFELDER} <= set(web.SZENENFELD_BESCHRIFTUNG)


def test_formwerte_englisch_beschriftet_datenbankwert_bleibt(padua):
    paare = [(f, web._form_anzeige(f).capitalize()) for f in ("dialog", "monolog", "lied")]
    html = web._dropdown("szene_form", paare, "lied")
    assert '<option value="lied" selected>Song</option>' in html
    assert '<option value="monolog">Monologue</option>' in html


def test_formwerte_in_dortmund_wie_bisher():
    assert web._form_anzeige("monolog") == "monolog"
    assert web._form_anzeige("monolog").capitalize() == "Monolog"

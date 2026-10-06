"""Gruppenseite, Probenansicht, Leitfaden-Seite ohne deutsches Wort (D10d)."""

import pytest

from interview_theater import db, sprache, web, web_daten, workshop
from scripts import pruefe_sprache
from tests.fixture_sprache import baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
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


def test_dashboard_folgt_dem_profil(padua):
    """Bis Aufgabe 17 blieb das Team-Dashboard deutsch; seit Padua
    (02.10.2026) spricht es die Sprache des Profils -- ausfuehrlich in
    ``tests/test_web_dashboard_en.py``."""
    html = web.dashboard_html({"gruppen": [], "bot_zuordnung": [], "stand": None})
    assert '<html lang="en">' in html
    assert "No group has written yet." in html


def test_speichermeldungen_kommen_aus_data_attributen(tmp_path, padua, monkeypatch):
    """Das Skript traegt keinen Nutzertext mehr; die Meldungen stehen im
    <body> in der Sprache des Profils."""
    # Seit der read-only Werkbank (03.10.2026) gibt es die Formulare nur noch
    # mit ``[web] workbench_bearbeitbar = true``; Padua setzt false. Geprueft
    # wird hier die SPRACHE der Meldungen, deshalb der Schalter erzwungen.
    monkeypatch.setattr(workshop, "workbench_bearbeitbar", lambda profil=None: True)
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


def test_web_formnamen_passen_zum_profil(padua):
    """Review A1 (d): ``web.FORM_BESCHRIFTUNG`` ist eine zweite Formnamen-Liste
    neben ``workshop.form_anzeige``. Fuer Padua muessen beide dasselbe sagen --
    die Seite schreibt klein im Fliesstext, gross im Dropdown."""
    formen = workshop.formen()
    anzeige = workshop.form_anzeige()
    assert [web._form_anzeige(f).capitalize() for f in formen] == list(anzeige)
    assert [web._form_anzeige(f) for f in formen] == [a.lower() for a in anzeige]


def test_formwerte_in_dortmund_wie_bisher():
    assert web._form_anzeige("monolog") == "monolog"
    assert web._form_anzeige("monolog").capitalize() == "Monolog"


# --- Nachbesserung Aufgabe 17: Festlegungsbereiche, Pruefkennungen, Zitat ---

from interview_theater import repo  # noqa: E402
from interview_theater.dramaturgie import fanout  # noqa: E402


def _festlegungen():
    return {"festlegungen": [
        {"id": i, "bereich": b, "bezug": "Nadia" if b == "figur" else None,
         "text": "x"}
        for i, b in enumerate(repo.FESTLEGUNG_BEREICHE, 1)
    ]}


def _befunde():
    return {"runde": 1, "befunde": [
        {"pruefung": p, "szene": None, "schwere": "hinweis", "text": "x"}
        for p in fanout.EBENEN
    ]}


def test_festlegungsbereiche_decken_das_protokoll():
    # "rahmen" ist kein Bereich aus repo.FESTLEGUNG_BEREICHE (repo.py:3441-
    # 3449 nennt ihn absichtlich nicht -- das Setting hat mit
    # arbeitsstand.rahmen schon ein Zuhause). Er leckt trotzdem als Bereich
    # in die Festlegung: das Wort steht GROSSBUCHSTABEN in derselben
    # Prompt-Protokollliste wie die sieben kanonischen Bereiche, nur fuer
    # art=entfernen statt festlegung_setzen (sprachen/en/prompts/
    # erkenner.md Punkt 20), und ein Modell loest "If none fits, use a
    # short word of your own" bei festlegung_setzen manchmal wortgleich
    # damit ein (Abnahme-Befund A13/laptop-A1, 06.10.2026, gemessen in
    # festlegung.bereich='RAHMEN'). Er braucht trotzdem eine Beschriftung,
    # sonst bleibt er deutsch/GROSSBUCHSTABEN in einer englischen Gruppe
    # stehen.
    assert set(web.FESTLEGUNG_BEREICH_BESCHRIFTUNG) == set(repo.FESTLEGUNG_BEREICHE) | {"rahmen"}
    assert all(k == v for k, v in web.FESTLEGUNG_BEREICH_BESCHRIFTUNG.items())


def test_festlegung_bereich_rahmen_bekommt_einen_titel_englisch(padua):
    """Reproduziert den Befund A13/laptop-A1 wortgleich: der Erkenner
    speichert den Bereich roh, oft in GROSSBUCHSTABEN wie vom Protokoll
    verlangt (``repo.normiere_bereich`` laesst einen unbekannten Bereich
    unveraendert stehen) -- der Nachschlag muss GROSS-/Kleinschreibung
    tolerieren."""
    html = web._festlegungen_html(
        {"festlegungen": [{"id": 1, "bereich": "RAHMEN", "bezug": None, "text": "x"}]},
        None,
    )
    assert '<span class="marke">frame</span>' in html
    assert "rahmen" not in html.lower()


def test_pruefkennungen_decken_alle_pruefungen():
    """``fanout.EBENEN`` kennt jede Kennung, die in ``dramaturgie_befund``
    landen kann (Judge-Fragen und mechanische Pruefungen)."""
    assert set(fanout.PROMPTS) <= set(fanout.EBENEN)
    assert set(web.PRUEFUNG_BESCHRIFTUNG) == set(fanout.EBENEN)
    assert all(k == v for k, v in web.PRUEFUNG_BESCHRIFTUNG.items())


def test_festlegungen_in_padua_englisch(padua):
    html = web._festlegungen_html(_festlegungen(), None)
    assert '<span class="marke">character · Nadia</span>' in html
    assert '<span class="marke">structure</span>' in html
    assert '<span class="marke">other</span>' in html
    treffer = pruefe_sprache.deutsche_treffer("festlegungen", pruefe_sprache.nur_text(html))
    assert treffer == []


def test_festlegungen_in_dortmund_roh():
    html = web._festlegungen_html(_festlegungen(), None)
    for bereich in repo.FESTLEGUNG_BEREICHE:
        marke = "figur · Nadia" if bereich == "figur" else bereich
        assert f'<span class="marke">{marke}</span>' in html


def test_pruefkennungen_in_padua_englisch(padua):
    html = web._dramaturgie_html(_befunde())
    assert '<span class="marke">consistent names</span>' in html
    assert '<span class="marke">focus</span>' in html
    assert "namensstabilitaet" not in html and "sprechanteil" not in html
    treffer = pruefe_sprache.deutsche_treffer("dramaturgie", pruefe_sprache.nur_text(html))
    assert treffer == []


def test_pruefkennungen_in_dortmund_roh():
    html = web._dramaturgie_html(_befunde())
    for p in fanout.EBENEN:
        assert f'<span class="marke">{p}</span>' in html


def test_leeres_zitat_zeigt_strich():
    assert web._zitat("") == "„—“"
    assert web._zitat(None) == "„—“"


def test_textzugriff_heisst_wie_das_modul():
    """Auch unter ``python -m interview_theater.web`` (``__main__``) muss
    ``T`` in der Tabelle ``["web"]`` nachschlagen."""
    assert web.T._modul == "interview_theater.web"

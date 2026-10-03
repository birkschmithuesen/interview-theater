"""Das gestaltete Team-Dashboard (P2, Aufgabe 3) -- nur mit
``[web] dashboard_gestaltet`` im Profil (Padua).

Zweck (Birk): dauerhaft im Plenum projiziert, zeigt den Stand aller Gruppen,
fuer Dramaturgie und Workshopleitung. Inhalt und Fortschritt zuerst, Technik
nur bei einem Problem -- dann als klarer Hinweis, sonst eingeklappt im Log.

Dortmund und die Vorgabe bleiben byte-gleich
(``tests/test_web_dashboard_en.py::test_deutsch_byte_gleich_wie_vorher``).
"""

import copy
import re
from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import db, repo, sprache, web, web_daten, web_gestalt, workshop
from test_web_dashboard_en import DATEN, LEER, _lage, _lagen, _profil, _sichtbar


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def padua(monkeypatch):
    _profil(monkeypatch, "padua-2026")


def _daten(**je_gruppe) -> dict:
    """DATEN, erste Gruppe um ``je_gruppe`` ergaenzt."""
    daten = copy.deepcopy(DATEN)
    daten["gruppen"][0].update(je_gruppe)
    return daten


def _karten(html: str) -> list[str]:
    return re.findall(r'<section class="karte[^"]*">.*?</section>', html, flags=re.S)


# -- Der Schalter --------------------------------------------------------------


def test_gestaltet_nur_im_profil_gesetzt(monkeypatch):
    for profil, erwartet in ((None, False), ("dortmund-2026", False),
                             ("padua-2026", True)):
        _profil(monkeypatch, profil)
        assert workshop.aktiv().wert("web.dashboard_gestaltet") is erwartet


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_deutsch_ohne_gestaltung(monkeypatch, profil):
    _profil(monkeypatch, profil)
    html = web.dashboard_html(DATEN)
    assert "--grund:" not in html
    assert 'class="ux-achtung"' not in html


def test_padua_traegt_die_tokens_des_entwurfs(padua):
    html = web.dashboard_html(DATEN)
    tokens = web_gestalt.TOKENS[web_gestalt.entwurf()]
    assert f"--grund: {tokens['grund']};" in html
    assert web_gestalt.css_dashboard() in html


def test_das_dashboard_css_haelt_die_regeln_der_gestaltung():
    for name in web_gestalt.ENTWUERFE:
        css = web_gestalt.css_dashboard(name)
        ohne_kommentare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", ohne_kommentare)
        for verboten in ("@keyframes", "@media", "@import", "@font-face",
                         "url(", "animation", "transition"):
            assert verboten not in ohne_kommentare, verboten


# -- Fortschritt auf einen Blick -----------------------------------------------


def test_jede_karte_zeigt_ihre_phase_als_fortschritt(padua):
    html = web.dashboard_html(DATEN)
    erste, zweite = _karten(html)
    assert "Act 3/7" in _sichtbar(erste)
    assert "Act 1/7" in _sichtbar(zweite)      # ungesetzte Phase gilt wie 1
    # Sieben Segmente, die ersten drei als erreicht markiert.
    segmente = re.findall(r'<i class="(fertig|jetzt|offen)"></i>', erste)
    assert segmente == ["fertig", "fertig", "jetzt"] + ["offen"] * 4


def test_der_fortschritt_steht_nicht_im_log(padua):
    p = _lage(web.dashboard_html(DATEN))
    assert _lagen(p, "div.ux-fortschritt") == [None, None]


# -- Inhalt statt Technik ------------------------------------------------------


def test_leere_felder_stehen_nicht_da(padua):
    """Ein Strich je leeres Feld ist am Beamer Rauschen."""
    zweite = _karten(web.dashboard_html(DATEN))[1]
    assert "<dd>—</dd>" not in zweite
    assert "Nothing decided yet." in _sichtbar(zweite)


def test_der_inhalt_steht_ohne_doppelte_phase_und_ohne_leitfaden(padua):
    erste = _karten(web.dashboard_html(DATEN))[0]
    text = _sichtbar(erste)
    for inhalt in ("a bridge at night", "two friends meet on the bridge",
                   "bridge, market, rain", "Mira", "Luca", "fishing at dawn"):
        assert inhalt in text, inhalt
    # Der Leitfaden ist aus den Fragen gebaut -- die Fragen stehen schon da.
    assert "Hello, we are making a play." not in text
    # Die Phase steht oben im Fortschritt, nicht noch einmal im Inhalt.
    assert "<dt>Phase</dt>" not in erste


def test_der_botname_steht_nur_noch_in_der_zuordnung(padua):
    html = web.dashboard_html(DATEN)
    erste = _karten(html)[0]
    assert "padua_bot1" not in erste
    assert "padua_bot1" in html          # in der eingeklappten Bot-Zuordnung


def test_keine_rohdaten_ueber_die_grenzen(padua):
    """Die drei Grenzen aus AGENTS.md: kein Nachrichtentext, kein Transkript,
    kein Belegzitat -- das Dashboard bekommt sie gar nicht erst."""
    html = web.dashboard_html(DATEN)
    assert "<blockquote" not in html


# -- Technik nur bei einem Problem -----------------------------------------------


def test_ein_problem_steht_als_hinweis_ausserhalb_des_logs(padua):
    html = web.dashboard_html(DATEN)
    p = _lage(html)
    assert _lagen(p, "div.ux-achtung") == [None]       # nur Karte 1
    erste, zweite = _karten(html)
    text = _sichtbar(erste)
    assert "Needs attention" in text
    assert "1 failed model call today" in text
    assert "3 incidents in the last 2 hours" in text
    assert 'class="ux-achtung"' not in zweite


def test_ohne_problem_kein_hinweis(padua):
    daten = _daten(vorfaelle=[], aufrufe=[
        {"art": "gespraech", "anzahl": 5, "fehlschlaege": 0, "median_ms": 900}])
    assert 'class="ux-achtung"' not in web.dashboard_html(daten)


def test_kostendeckel_nah_ist_ein_problem(padua):
    daten = _daten(vorfaelle=[], aufrufe=[], kosten_heute_chf=4.3,
                   kosten_deckel_chf=5.0)
    text = _sichtbar(_karten(web.dashboard_html(daten))[0])
    assert "Daily cost cap almost reached (86 %)" in text


def test_kosten_unter_der_schwelle_sind_kein_problem(padua):
    daten = _daten(vorfaelle=[], aufrufe=[], kosten_heute_chf=1.0,
                   kosten_deckel_chf=5.0)
    assert 'class="ux-achtung"' not in web.dashboard_html(daten)


def test_ein_stiller_bot_ist_ein_problem(padua):
    daten = _daten(vorfaelle=[], aufrufe=[],
                   unbeantwortet={"anzahl": 2, "minuten": 9})
    text = _sichtbar(_karten(web.dashboard_html(daten))[0])
    assert "The bot hasn't picked up 2 messages for 9 min" in text


def test_der_hinweis_nennt_die_letzte_vorfallart(padua):
    text = _sichtbar(_karten(web.dashboard_html(DATEN))[0])
    assert "latest: repetition_discarded" in text


def test_padua_gestaltet_ohne_deutsche_woerter(padua):
    from test_web_dashboard_en import _deutsche_treffer

    daten = _daten(kosten_heute_chf=4.9, kosten_deckel_chf=5.0,
                   unbeantwortet={"anzahl": 1, "minuten": 4})
    assert _deutsche_treffer(web.dashboard_html(daten)) == []


# -- Die neuen Lesewerte (web_daten, read-only) ---------------------------------


JETZT = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
CHAT = 7_000_000_000_201


@pytest.fixture
def lesend(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "bot_x", "Gruppe X")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    conn.commit()
    yield conn, pfad
    conn.close()


def _iso(minuten_vorher: int) -> str:
    return (JETZT - timedelta(minutes=minuten_vorher)).isoformat(timespec="seconds")


def test_kosten_heute_und_deckel(lesend, monkeypatch):
    conn, pfad = lesend
    monkeypatch.setenv("IT_KOSTEN_DECKEL_CHF", "4.0")
    monkeypatch.setenv("IT_ZEITZONE", "Europe/Rome")
    repo.merke_aufruf(conn, CHAT, "gespraech", erfolg=1, kosten_chf=1.5)
    repo.merke_aufruf(conn, CHAT, "gespraech", erfolg=0, kosten_chf=1.0)
    conn.execute("UPDATE aufruf SET erstellt_am = ?", (_iso(30),))
    repo.merke_aufruf(conn, CHAT, "gespraech", erfolg=1, kosten_chf=9.0)
    conn.execute("UPDATE aufruf SET erstellt_am = ? WHERE kosten_chf = 9.0",
                 ((JETZT - timedelta(days=2)).isoformat(timespec="seconds"),))
    conn.commit()
    gruppe = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)["gruppen"][0]
    assert gruppe["kosten_heute_chf"] == pytest.approx(2.5)
    assert gruppe["kosten_deckel_chf"] == pytest.approx(4.0)


def test_unbeantwortet_zaehlt_alte_ungelesene_eingaenge(lesend):
    conn, pfad = lesend
    repo.setze_update_id(conn, "bot_x", 0)
    for minuten in (9, 5, 1):
        pid = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                    text="x")
        conn.execute("UPDATE web_post SET erstellt_am = ? WHERE id = ?",
                     (_iso(minuten), pid))
    conn.commit()
    gruppe = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)["gruppen"][0]
    # Nur, was laenger als STILLE_AB liegt; das Alter ist das des aeltesten.
    assert gruppe["unbeantwortet"] == {"anzahl": 2, "minuten": 9}


def test_gelesenes_ist_nicht_unbeantwortet(lesend):
    conn, pfad = lesend
    pid = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="x")
    conn.execute("UPDATE web_post SET erstellt_am = ? WHERE id = ?", (_iso(20), pid))
    repo.setze_update_id(conn, "bot_x", pid)
    conn.commit()
    gruppe = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)["gruppen"][0]
    assert gruppe["unbeantwortet"] is None


def test_unbeantwortet_ohne_web_post_tabelle_ist_none(tmp_path):
    """Eine Datenbank aus der Zeit vor dem Web-Kanal: kein Fehler."""
    pfad = str(tmp_path / "alt.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "bot_x", "Gruppe X")
    conn.execute("DROP TABLE web_post")
    conn.commit()
    gruppe = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)["gruppen"][0]
    assert gruppe["unbeantwortet"] is None

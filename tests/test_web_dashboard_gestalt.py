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


def test_der_figurenblock_nennt_nur_namen(padua):
    """Am Beamer muss eine Karte im Spaetstand (zehn Figuren und mehr) in
    1080 px passen -- die Beschreibungen stehen auf der Gruppenseite."""
    erste = _karten(web.dashboard_html(DATEN))[0]
    assert "a student" not in _sichtbar(erste)
    assert "Mira" in _sichtbar(erste) and "Luca" in _sichtbar(erste)


def test_lange_felder_werden_gekappt(padua):
    """Geschichte, Setting, Fragen, Interviewergebnisse tragen die Klasse,
    an der das CSS sie auf wenige Zeilen kappt (``line-clamp``)."""
    erste = _karten(web.dashboard_html(DATEN))[0]
    assert len(re.findall(r'<dd class="kurz">', erste)) >= 4
    css = web_gestalt.css_dashboard()
    assert "-webkit-line-clamp" in css and "dd.kurz" in css


# -- Technik nur bei einem Problem -----------------------------------------------


def test_ein_problem_steht_als_hinweis_ausserhalb_des_logs(padua):
    html = web.dashboard_html(_daten(fehlschlaege_fenster=1))
    p = _lage(html)
    assert _lagen(p, "div.ux-achtung") == [None]       # nur Karte 1
    erste, zweite = _karten(html)
    text = _sichtbar(erste)
    assert "Needs attention" in text
    assert "1 failed model call in the last 2 hours" in text
    # Von den drei Vorfaellen in DATEN ist nur die gescheiterte Transkription
    # ein Problem; Buchhaltung und eine unbekannte Art zaehlen nicht.
    assert "1 incident in the last 2 hours" in text
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


def test_der_hinweis_nennt_die_letzte_problemart(padua):
    """Die juengste Art unter den PROBLEMEN, nicht die juengste ueberhaupt
    (in DATEN ist das ``wiederholung_verworfen`` -- Buchhaltung)."""
    text = _sichtbar(_karten(web.dashboard_html(DATEN))[0])
    assert "latest: transcription_failed" in text
    assert "repetition_discarded" not in _sichtbar(
        re.sub(r"<details.*?</details>", "", _karten(web.dashboard_html(DATEN))[0],
               flags=re.S))


#: Vorfaelle, die im Betrieb laufend entstehen und nichts Kaputtes melden.
ROUTINE = ("wiederholung_verworfen", "kontext_gekuerzt", "strom_nicht_verfuegbar",
           "web_rate_limit", "http_5xx", "echo_verworfen", "zitat_ungeprueft",
           "interview_ohne_knopf_offen", "nachpass_gelaufen", "szene_prompt_gekuerzt")


@pytest.mark.parametrize("art", ROUTINE)
def test_routinevorfaelle_loesen_keinen_hinweis_aus(padua, art):
    daten = _daten(vorfaelle=[{"art": art, "stufe": None, "detail": "x",
                               "erstellt_am": "2026-10-02T10:01:00+00:00",
                               "bot_weit": False}],
                   fehlschlaege_fenster=0)
    html = web.dashboard_html(daten)
    assert 'class="ux-achtung"' not in html
    # Im Log steht er weiterhin.
    assert "<details" in _karten(html)[0]


def test_ein_fehlschlag_von_heute_frueh_loest_keinen_hinweis_aus(padua):
    """Fehlschlaege gelten im selben Zwei-Stunden-Fenster wie Vorfaelle --
    ein gescheiterter Aufruf um 9 Uhr haelt den Kasten nicht bis 2 Uhr nachts.
    Die Tagestabelle im Log (``aufrufe``) bleibt dabei unberuehrt."""
    daten = _daten(vorfaelle=[], fehlschlaege_fenster=0)   # aufrufe: 1 Fehlschlag heute
    assert 'class="ux-achtung"' not in web.dashboard_html(daten)


def test_die_problemliste_nennt_nur_arten_die_der_code_schreibt():
    """Eine Art in der Liste, die niemand schreibt, waere ein Tippfehler,
    der still nie anschlaegt."""
    import pathlib

    quelle = "".join(p.read_text(encoding="utf-8") for p in
                     pathlib.Path(web.__file__).parent.rglob("*.py")
                     if p.name != "web.py")
    for art in web.ACHTUNG_VORFAELLE:
        assert f'"{art}"' in quelle, art
    assert not set(ROUTINE) & web.ACHTUNG_VORFAELLE


def test_padua_gestaltet_ohne_deutsche_woerter(padua):
    from test_web_dashboard_en import _deutsche_treffer

    daten = _daten(kosten_heute_chf=4.9, kosten_deckel_chf=5.0,
                   unbeantwortet={"anzahl": 1, "minuten": 4}, fehlschlaege_fenster=2)
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


def test_fehlschlaege_im_fenster(lesend):
    """Nur Fehlschlaege der letzten zwei Stunden (``VORFALL_FENSTER``)."""
    conn, pfad = lesend
    for minuten, erfolg in ((30, 0), (90, 0), (150, 0), (10, 1)):
        repo.merke_aufruf(conn, CHAT, "gespraech", erfolg=erfolg)
        conn.execute("UPDATE aufruf SET erstellt_am = ? WHERE id = "
                     "(SELECT MAX(id) FROM aufruf)", (_iso(minuten),))
    conn.commit()
    gruppe = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)["gruppen"][0]
    assert gruppe["fehlschlaege_fenster"] == 2


#: Erfundene Rohdaten, die NIE auf das Dashboard duerfen (docs/agents/weboberflaeche.md).
GEHEIM_NACHRICHT = "SECRET message text from the group chat"
GEHEIM_TRANSKRIPT = "SECRET transcript: my grandmother crossed the bridge"
GEHEIM_ZITAT_UNGEPRUEFT = "SECRET unchecked quote about the bridge"
GEHEIM_ZITAT_GEPRUEFT = "SECRET checked quote about the market"
GEHEIM_ZUSAMMENFASSUNG = "SECRET summary of the whole interview"
GEHEIM_WEB = "SECRET browser message"


def test_keine_rohdaten_ueber_die_grenzen(lesend, padua):
    """Die drei Grenzen aus docs/agents/weboberflaeche.md: kein Nachrichtentext, kein Transkript,
    kein Belegzitat (ungeprueft sowieso nicht, und das Dashboard zeigt
    ueberhaupt keine Zitate) -- weder in den Daten noch im HTML."""
    conn, pfad = lesend
    repo.merke_nachricht(conn, CHAT, 5, "Gruppe", 0, "text", GEHEIM_NACHRICHT,
                         _iso(5))
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text=GEHEIM_WEB)
    aid = repo.lege_aufnahme_an(conn, CHAT, 6, "lang", "sprache", None, 300,
                                status="fertig")
    repo.setze_transkript(conn, aid, GEHEIM_TRANSKRIPT)
    repo.speichere_verdichtung(
        conn, CHAT, aid, GEHEIM_ZUSAMMENFASSUNG,
        [{"thema": "Crossing", "kurz": "the bridge crossing",
          "beleg_zitat": GEHEIM_ZITAT_UNGEPRUEFT, "zitat_geprueft": 0},
         {"thema": "Market", "kurz": "the market noise",
          "beleg_zitat": GEHEIM_ZITAT_GEPRUEFT, "zitat_geprueft": 1}],
    )
    conn.commit()
    daten = web_daten.dashboard(web_daten.oeffne_lesend(pfad), jetzt=JETZT)
    html = web.dashboard_html(daten)
    # Die Kurzformen kommen an -- die Fixture ist also wirklich gelesen worden.
    assert "the bridge crossing" in html
    for geheim in (GEHEIM_NACHRICHT, GEHEIM_TRANSKRIPT, GEHEIM_ZITAT_UNGEPRUEFT,
                   GEHEIM_ZITAT_GEPRUEFT, GEHEIM_ZUSAMMENFASSUNG, GEHEIM_WEB):
        assert geheim not in repr(daten), geheim
        assert geheim not in html, geheim
    assert "<blockquote" not in html

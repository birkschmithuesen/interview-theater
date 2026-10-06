"""Die read-only Werkbank auf der Gruppenseite (Padua, 03.10.2026).

Birk, 03.10.: "Unter Workbench alle Dropdowns und Textfelder gegen reine
Read-only-Darstellung ersetzen. Aenderungen passieren ueber Chat. Workbench
reiner Status-Ausspieler." Nur erfundenes Material (``fixture_sprache``)."""

import html as html_modul
import re

import pytest

from interview_theater import db, repo, roadmap, sprache, web, web_chat, web_daten, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FORMULAR = re.compile(r"<(select|textarea|input|button)\b|contenteditable", re.I)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _padua_daten(tmp_path):
    """Die volle englische Gruppe (Phase 6), gelesen UNTER dem Padua-Profil --
    nur dann traegt ``gruppe_nach_token`` den Schluessel ``werkbank``."""
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_volle_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token), token
    finally:
        lesend.close()


_STANDFELDER = (
    "phase", "begriffe", "fragen", "frage_einleitungen", "fragen_weich",
    "fragen_herkunft_final", "interview_eroeffnung", "interview_abschluss",
    "kernthema", "kernthema_begruendung", "format", "rahmen", "kernthema_richtung",
    "kernfrage", "geschichte", "figuren_fixiert_am", "hauptkonflikt", "geaendert_am",
)


def _lage(**abweichung) -> dict:
    grund = {"stand": {}, "figuren": [], "szenen": [], "interviews": [],
             "zuordnungen": 0, "pruefrunde": None, "phase": 1,
             "interviewmodus": False, "tippt": False, "strom": None}
    grund.update(abweichung)
    return grund


def _mini(phasen_liste=None, **mehr) -> dict:
    """Ein minimales ``daten``-Dict fuer ``werkbank_koerper`` ohne Datenbank."""
    daten = {
        "titel": "Test group", "chat_id": 1, "web_token": None, "kanal": "web",
        "arbeitsstand": dict.fromkeys(_STANDFELDER), "journal": [], "interviews": [],
        "figuren": [], "szenen": [], "festlegungen": [], "fragen_auswertung": None,
        "sprechanteile": None, "dramaturgie": None,
        "werkbank": {"phasen": phasen_liste or [], "begriffe_detail": [], "szenen_anzahl": None},
    }
    daten.update(mehr)
    return daten


def test_padua_werkbank_ohne_formular(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    for nonce in (None, "nonce-x"):
        seite = web.gruppe_koerper(daten, nonce, token)
        assert not FORMULAR.search(seite), FORMULAR.search(seite)
        assert "data-feld" not in seite
        assert 'id="meldungen"' not in seite


def test_padua_gruppenseite_ohne_bearbeiten_js(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    assert web._BEARBEITEN_JS not in web.gruppe_html(daten, "nonce-x", token)


def test_der_hinweis_steht_genau_einmal_ganz_oben(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, "nonce-x", token)
    assert web.T._TEXT_WERKBANK_HINWEIS == "To change something, just tell the bot in the chat."
    hinweis = html_modul.escape(web.T._TEXT_WERKBANK_HINWEIS)
    assert seite.count(hinweis) == 1
    assert seite.index(hinweis) < seite.index('class="wb-phase"')


def test_keine_phasenanzeige_keine_links_keine_alten_abschnitte(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, "nonce-x", token)
    assert f"<dt>{web.T.ARBEITSSTAND_BESCHRIFTUNG['phase']}</dt>" not in seite
    for weg in ('class="probenansicht"', '/textbuch"', f'/{web_chat.CHAT_PFAD}"',
                'class="fehlstellen"', 'class="stueckkarte"', 'class="uebersicht"'):
        assert weg not in seite, weg


def test_sieben_phasen_in_reihenfolge(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    stellen = [seite.index(f'data-wb-phase="{n}"') for n in range(1, 8)]
    assert stellen == sorted(stellen)
    assert seite.count('<details class="wb-phase"') == 7


def test_nur_die_aktuelle_phase_ist_aufgeklappt(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)          # die Gruppe steht in Phase 6
    seite = web.gruppe_koerper(daten, None, token)
    assert re.findall(r'<details class="wb-phase" data-wb-phase="(\d)" open>', seite) == ["6"]


def test_drei_zustaende_mit_form_und_beschriftung(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert 'class="wb-punkt wb-erledigt" role="img" aria-label="done"' in seite
    assert 'class="wb-punkt wb-offen" role="img" aria-label="open"' in seite
    assert 'class="wb-punkt wb-spaeter" role="img" aria-label="later"' in seite


def test_nach_der_aktuellen_phase_steht_nichts_offen(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    sieben = seite[seite.index('data-wb-phase="7"'):seite.index('class="wb-journal"')]
    assert "wb-offen" not in sieben


def test_keine_ampel_emoji(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    for zeichen in ("🟢", "🔴", "⚪", "🟡", "✅", "⬜", "⏳"):
        assert zeichen not in seite


def test_laeuft_ist_ein_wort_am_offenen_punkt(padua):
    phasen_liste = roadmap.werkbank(_lage(phase=3, interviewmodus=True), 3)
    seite = web.werkbank_koerper(_mini(phasen_liste))
    zeile = re.search(
        r'<li class="wb-zeile wb-offen" data-kennung="interviews">.*?</li>', seite).group(0)
    assert web.T._TEXT_WERKBANK_LAEUFT == "running"
    assert "running" in zeile


def test_der_zaehler_und_der_haken(padua):
    """Padua schaltet die weiche Fassung ab ([fragen_weich] aktiv = false)
    -- "Einleitungen" zaehlt dort nicht mit, Phase 2 hat drei Aufgaben, nicht
    vier (Feedbackloop P1-2, P2-H4: sonst wurde der Kreis nie voll)."""
    phasen_liste = roadmap.werkbank(_lage(phase=2, stand={"begriffe": "x"}), 2)
    seite = web.werkbank_koerper(_mini(phasen_liste))
    eins = seite[seite.index('data-wb-phase="1"'):seite.index('data-wb-phase="2"')]
    zwei = seite[seite.index('data-wb-phase="2"'):seite.index('data-wb-phase="3"')]
    assert "1 of 1" in eins and 'class="wb-fertig"' in eins
    assert "0 of 3" in zwei and 'class="wb-fertig"' not in zwei


def test_das_journal_steht_unten_und_zu(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert '<details class="wb-journal">' in seite
    assert seite.index('class="wb-journal"') > seite.index('data-wb-phase="7"')


def test_recherche_abschnitt_steht_unter_dem_journal_und_ist_klar_beschriftet(padua):
    """Karte t_c5117c91: ein eigener, von den sieben Phasen unabhaengiger
    Abschnitt -- klar als Internet-Recherche beschriftet, kein
    Interviewmaterial. Mutant: der Abschnitt fehlt ganz oder zeigt kein
    eigenes Label."""
    seite = web.werkbank_koerper(_mini())
    assert web.T._UEBERSCHRIFT_RECHERCHE == "Research - from the internet (not interview material)"
    assert '<details class="wb-recherche">' in seite
    assert web.T._UEBERSCHRIFT_RECHERCHE in seite
    assert seite.index('class="wb-recherche"') > seite.index('class="wb-journal"')


def test_recherche_abschnitt_zeigt_frage_text_und_quellen(padua):
    daten = _mini()
    daten["werkbank"]["recherche"] = [{
        "frage": "When was the bridge built?",
        "ergebnis_text": "The bridge was built in 1900 (Example, https://x.test).",
        "quellen": ["Example"],
    }]
    block = web.werkbank_koerper(daten)[
        web.werkbank_koerper(daten).index('class="wb-recherche"'):
    ]
    assert "When was the bridge built?" in block
    assert "The bridge was built in 1900" in block
    assert "Example" in block


def test_recherche_abschnitt_leer_ohne_recherche(padua):
    seite = web.werkbank_koerper(_mini())
    assert web.T._TEXT_RECHERCHE_LEER in seite


def test_ohne_werkbankdaten_kein_absturz(padua):
    seite = web.werkbank_koerper(_mini(werkbank=None))
    assert 'class="wb-phase"' not in seite
    assert html_modul.escape(web.T._TEXT_WERKBANK_HINWEIS) in seite


def _block(seite: str, nummer: int) -> str:
    anfang = seite.index(f'data-wb-phase="{nummer}"')
    ende = (seite.index('<details class="wb-phase"', anfang + 1) if nummer < 7
            else seite.index('class="wb-journal"'))
    return seite[anfang:ende]


def test_phase_1_zeigt_die_begriffe(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    assert "belonging, family, noise, courage" in _block(web.gruppe_koerper(daten, None, token), 1)


def test_begriffe_detail_mit_daten(padua):
    """Der Haken fuer Karte t_4517d4ad -- mit Inhalt."""
    phasen_liste = roadmap.werkbank(_lage(stand={"begriffe": "Heimat"}), 1)
    daten = _mini(phasen_liste)
    daten["arbeitsstand"]["begriffe"] = "Heimat"
    daten["werkbank"]["begriffe_detail"] = [
        {"begriff": "Heimat", "begruendung": "came up three times",
         "doppelbedeutung": "place and feeling"}]
    block = _block(web.werkbank_koerper(daten), 1)
    assert 'class="wb-begriffe"' in block
    assert "came up three times" in block and "place and feeling" in block


def test_begriffe_detail_ohne_daten(padua):
    phasen_liste = roadmap.werkbank(_lage(), 1)
    assert 'class="wb-begriffe"' not in web.werkbank_koerper(_mini(phasen_liste))


def test_phase_2_fragen_leitfaden_und_ab_zeile(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    block = _block(web.gruppe_koerper(daten, None, token), 2)
    assert 'class="fragen"' in block
    assert '<pre class="leitfaden">' in block       # _JS_INTERVIEW liest ihn hier
    daten["fragen_auswertung"] = {"gesamt": {"eigen": 2, "ki": 1}}
    block = _block(web.gruppe_koerper(daten, None, token), 2)
    assert web.T._TEXT_FRAGEN_AUSWERTUNG.format(eigen=2, ki=1) in block


def test_phase_3_verdichtung_wie_bisher_ohne_transkript(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    block = _block(seite, 3)
    assert "She talks about home and the bakery." in block
    assert "Home is the smell of bread." in block              # zitat_geprueft = 1
    assert "Allora, I grew up above a bakery" not in seite     # nur im Transkript


def test_phase_4_setting_figuren_und_auch_vereinbart(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    block = _block(web.gruppe_koerper(daten, None, token), 4)
    assert "A bus stop at night" in block
    assert "<b>Nadia</b>" in block and "the older sister, restless" in block
    assert html_modul.escape(web.T._TEXT_WB_AUCH_VEREINBART) in block
    assert "At most one song." in block                        # eine Festlegung
    assert "<button" not in block


def test_keine_szenen_volltexte(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert "You always say that." not in seite
    assert "TOMAS: Stay." not in seite


def test_phase_6_dramaturgie_und_phase_7_sprechanteile(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert "Scene 1 does not turn." in _block(seite, 6)
    assert 'class="anteile"' in _block(seite, 7)

"""Die Telefon-Organisationskarten (UX-Knoepfe-Karte, Abschnitt 5).

Drei Dinge werden hier geprueft, die am Quelltext gemessen werden koennen,
ohne Chromium neu laufen zu lassen: der Lookup (``interview_theater.
handykarten``) stimmt mit der EINEN Tabelle in ``scripts/handy_karten.py``
ueberein, die sieben PNGs liegen committet unter
``interview_theater/static/handys/``, und die Tab-Namen auf den Karten sind
wortgleich mit ``web_vereint._TEXT_TAB`` -- eine Karte, die einen Tab zeigt,
den es auf der echten Seite nicht gibt, verwirrt mehr, als sie hilft."""

from pathlib import Path

from interview_theater import handykarten, phasen, web_vereint
from scripts.handy_karten import PHASEN, TAB


def test_jede_phase_hat_dateiname_und_satz():
    for nummer, _name, satz, _phones in PHASEN:
        assert handykarten.dateiname(nummer) == f"phase-{nummer}.png"
        assert handykarten.satz(nummer) == satz


def test_unbekannte_phase_liefert_none():
    assert handykarten.dateiname(99) is None
    assert handykarten.satz(99) is None
    assert handykarten.pfad(99) is None


def test_sieben_pngs_liegen_committet():
    """Eine Karte je Phase, erzeugt und committet -- kein Platzhalter."""
    for nummer, *_ in PHASEN:
        datei = handykarten.pfad(nummer)
        assert datei is not None, f"Phase {nummer}: keine generierte Karte"
        assert datei.is_file()
        assert datei.stat().st_size > 1000


def test_alle_sieben_phasen_haben_eine_karte():
    """Die Tabelle in ``scripts/handy_karten.py`` deckt jede Phase aus
    ``phasen.PHASEN`` ab -- sonst stuende ein Phaseneintritt ohne Karte da."""
    nummern_karten = {nr for nr, *_ in PHASEN}
    nummern_phasen = {nr for nr, _, _ in phasen.PHASEN}
    assert nummern_karten == nummern_phasen


def test_tab_namen_stimmen_mit_der_echten_tableiste_ueberein():
    """``scripts/handy_karten.TAB`` nennt die Tabs, die eine Karte zeigen
    darf -- jeder davon muss es auch in ``web_vereint._TEXT_TAB`` geben,
    sonst zeigt eine Karte auf einen Tab, der auf der echten Seite nicht
    existiert."""
    echte_tabs = set(web_vereint._TEXT_TAB.values())
    for tab_name in TAB:
        assert tab_name in echte_tabs, tab_name


def test_jede_in_einer_karte_genannte_phase_benutzt_nur_bekannte_tabs():
    for _nummer, _name, _satz, phones in PHASEN:
        for tab_name, _rolle, _notiz in phones:
            assert tab_name in TAB


# --- Englische Karten (Padua, 02.10.2026: "Bilder zum Handy aufstellen sind
# auf deutsch") -----------------------------------------------------------

from scripts.handy_karten import PHASEN_EN, SPRACHEN, TAB_EN


def test_englische_tabelle_deckt_dieselben_phasen_ab():
    assert [nr for nr, *_ in PHASEN_EN] == [nr for nr, *_ in PHASEN]


def test_englische_tabs_sind_die_englischen_tabnamen_der_seite():
    """Wortgleich mit sprachen/en/texte.toml [web_vereint._TEXT_TAB]."""
    import tomllib
    pfad = Path(web_vereint.__file__).parent / "sprachen" / "en" / "texte.toml"
    en = tomllib.loads(pfad.read_text(encoding="utf-8"))["web_vereint"]["_TEXT_TAB"]
    echte = set(en.values())
    for tab_name in TAB_EN:
        assert tab_name in echte, tab_name
    for _nr, _name, _satz, phones in PHASEN_EN:
        for tab_name, _r, _n in phones:
            assert tab_name in TAB_EN


def test_englische_pngs_liegen_committet():
    from scripts.handy_karten import OUT
    for nr, *_ in PHASEN_EN:
        datei = OUT / SPRACHEN["en"][3].format(nr=nr)
        assert datei.is_file() and datei.stat().st_size > 1000, datei


def test_lookup_folgt_der_profilsprache(monkeypatch):
    from interview_theater import sprache
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert handykarten.dateiname(4) == "phase-4-en.png"
    assert handykarten.satz(4) == PHASEN_EN[3][2]
    assert handykarten.pfad(4) is not None
    monkeypatch.setattr(sprache, "code", lambda: "it")
    assert handykarten.dateiname(4) == "phase-4.png", "unbekannte Sprache -> deutsch"


def test_englischer_dateiname_passt_durch_die_static_positivliste():
    from interview_theater import web
    assert web._STATIC_NAME.fullmatch("phase-4-en.png")

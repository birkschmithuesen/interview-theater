"""Birk 08.10.2026 ~11:00 (Quickfix): IT-PDF mit italienischen Ueberschriften,
G1-Karten ohne Zitate. Mutanten: erzwinge ohne Wirkung -> rot;
ohne_zitate nicht an _karte_html -> rot."""
from interview_theater import sprache, web, web_skript


def test_erzwinge_it_macht_ueberschriften_italienisch(monkeypatch):
    with sprache.erzwinge("it"):
        assert web.T._TEXT_SZENE_NR.format(nummer=2) == "Scena 2"
        assert web_skript.T._TEXT_WO == "Dove"
    assert web.T._TEXT_SZENE_NR.format(nummer=2) != "Scena 2"


def test_karte_ohne_zitate():
    karte = {"typ": "description", "worum": "w", "zitate": [{"zitat": "ZITAT-X", "interview": "Interview 3"}]}
    assert "ZITAT-X" in web._karte_html(karte, True)
    assert "ZITAT-X" not in web._karte_html(karte, True, ohne_zitate=True)


def test_script_tab_status_und_sprachwahl():
    """Birk 08.10.2026 ~11:50: Status je Szene (Konzept rot / ausformuliert) und
    nur EINE Sprache mit Umschalter. Mutanten: Badge weg -> rot; CSS-Regel weg -> rot."""
    import inspect
    quelle = inspect.getsource(web)
    assert "status-badge konzept" in quelle and "status-badge fertig" in quelle
    assert "body.nur-en .stueck [lang=it]" in quelle and 'class="sprachwahl"' in quelle

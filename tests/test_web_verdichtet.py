"""Script vs. Workbench unter ``[skript] verdichtet`` (Birk 07.10.2026
~17:45, docs/superpowers/specs/2026-10-07-script-vs-workbench.md)."""

import pytest

from interview_theater import repo, schaerfung, web, web_daten, workshop

ZITAT_A = "Ich habe zwanzig Jahre genaeht und keiner hat gefragt."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt."


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _szene(**felder):
    s = {"nummer": 2, "titel": "Le voci", "ort": "Probenraum", "figuren": ["Emma"],
         "volltext": None, "prosa": None, "prosa_it": None,
         "verdichtet": {"kern": ["Die Stimmen werden geteilt", "Musik hoert nie auf"],
                        "kernsaetze_kurz": ['"Casa non sono le mura" (Interview 19)'],
                        "beschreibung": "Brei", "kernsaetze_eigen": [], "zitate": []}}
    s.update(felder)
    return s


def test_script_ohne_text_zeigt_worum_es_geht(padua):
    html, _ = web._probe_szene_html(_szene(), set())
    assert "Die Stimmen werden geteilt" in html
    assert "Casa non sono le mura" in html
    assert 'class="worum"' in html


def test_script_mit_text_ohne_kurzform_und_ohne_key_lines(padua):
    html, _ = web._probe_szene_html(
        _szene(prosa="Emma steht auf.\n\nGiada sitzt.", prosa_it="Emma si alza."), set())
    assert "Emma steht auf." in html and "Emma si alza." in html
    assert "Die Stimmen" not in html and "Casa non sono" not in html
    assert html.count('<div class="text"') == 2


def test_script_rueckfall_auf_bereinigte_beschreibung(padua):
    s = _szene()
    s["verdichtet"]["kern"] = []
    html, _ = web._probe_szene_html(s, set())
    assert "Brei" in html


def test_workbench_zeigt_kurzform_und_aufklappbar_alle_zitate(padua):
    s = _szene()
    s["verdichtet"]["zitate"] = [{"zitat": ZITAT_A, "interview": "Interview 1"}]
    html = web._wb_szenen_verdichtet_html([s])
    assert "Die Stimmen werden geteilt" in html
    assert '<details class="wb-alle">' in html and ZITAT_A in html


def test_css_nur_mit_schalter():
    assert web.css_textbuch_lesbar() == "" and web.css_werkbank_kurz() == ""


def _lage(conn, geprueft_b=1):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, ZITAT_A + " " + ZITAT_B)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": "Arbeit", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1},
        {"thema": "Stillstand", "beleg_zitat": ZITAT_B, "zitat_geprueft": geprueft_b},
    ])
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Mira naeht allein.")
    themen = conn.execute("SELECT id FROM verdichtung_thema ORDER BY id").fetchall()
    repo.lege_schaerfung_an(conn, 1, [
        {"verdichtung_thema_id": t["id"], "szene_id": szene_id, "begruendung": b}
        for t, b in zip(themen, ("gibt den Grundton", "zeigt den Stillstand"))
    ])
    return szene_id


def test_web_daten_ohne_schalter_unveraendert(conn):
    _lage(conn)
    assert "verdichtet" not in web_daten._szenen(conn, 1)[0]


def test_web_daten_bereinigt_und_zeigt_nur_gepruefte_zitate(conn, padua):
    szene_id = _lage(conn, geprueft_b=0)
    # Altbestand: vor dem Schalter angehaengt.
    repo.setze_szenenfeld(conn, szene_id, "was_passiert",
                          "Mira naeht allein. gibt den Grundton; zeigt den Stillstand")
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    v = web_daten._szenen(conn, 1)[0]["verdichtet"]
    assert v["beschreibung"] == "Mira naeht allein."
    assert [z["zitat"] for z in v["zitate"]] == [ZITAT_A]

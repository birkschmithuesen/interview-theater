"""Das abgenommene Stage-Script-Design (Birk 08.10.2026 ~00:05: "Das
PDF-Design gefaellt mir, das kann so bleiben") im Script-Tab und im PDF --
nur unter ``[skript] verdichtet`` / ``[karten]`` (Padua). Vorlage:
var/padua-nacht/stagescript-design-draft.py."""

import pytest

from interview_theater import web, web_pdf, web_skript, workshop


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


# --- Merkmal 4: Interview quotes -------------------------------------------

def test_zitatzeile_wird_block_mit_kopf_und_nummer(padua):
    html = web_skript.text_html("> “Tendenzialmente sì, meno se è nuovo.” (Interview 7)")
    assert '<blockquote class="interviewzitat">' in html
    assert '<span class="zitat-kopf">Interview quote · 7</span>' in html
    assert '<span class="zitat-text">“Tendenzialmente sì, meno se è nuovo.”</span>' in html
    assert "(Interview 7)" not in html


def test_zitat_im_prompt_format_mit_kopf(padua):
    html = web_skript.text_html('> *Interview quote (6):* "A me viene in mente casa"')
    assert '<span class="zitat-kopf">Interview quote · 6</span>' in html
    assert "“A me viene in mente casa”" in html


def test_zitat_im_absatz_wird_block_und_der_rest_ein_neuer_absatz(padua):
    text = ('3. Giada speaks quicker: "è tipo un po\' il rumore di sottofondo" '
            "(Interview 25). Mid-flow, all music stops.")
    html = web_skript.text_html(text)
    assert html.index("Giada speaks quicker:") < html.index("zitat-kopf")
    assert "Interview quote · 25" in html
    assert "<p>Mid-flow, all music stops.</p>" in html
    assert ". Mid-flow" not in html


def test_zitat_auf_italienisch_intervista(padua):
    html = web_skript.text_html('Emma dice: "di tornare a casa e dirmi" (Intervista 13). Poi torna.')
    assert "Interview quote · 13" in html and "<p>Poi torna.</p>" in html


# --- Merkmal 1: Markdown bleibt Markdown -----------------------------------

def test_markdown_tabelle_wird_tabelle():
    html = web_skript.text_html("| # | Moment |\n|---|---|\n| 1 | The **First** Press |")
    assert '<table class="skript-tabelle">' in html
    assert "<th>#</th><th>Moment</th>" in html
    assert "<td>1</td><td>The <strong>First</strong> Press</td>" in html


def test_listen_labels_ort_und_personen():
    text = ("THEME\nUnease before any group.\n\nPlace: empty bar table\nWho: Francesca\n\n"
            "INSTRUCTIONS (WHO DOES WHAT)\n\nFrancesca\n- Sits alone.\n- Waits.")
    html = web_skript.text_html(text)
    assert "<h4>THEME</h4>" in html and "<h4>INSTRUCTIONS (WHO DOES WHAT)</h4>" in html
    assert '<p class="meta">Place: empty bar table</p>' in html
    assert '<p class="person"><strong>Francesca</strong></p><ul><li>Sits alone.</li><li>Waits.</li></ul>' in html


def test_nummerierter_absatz_behaelt_seine_nummer():
    html = web_skript.text_html("2. Once everyone is seated.\n\n3. Giada turns.")
    assert '<ol start="2"><li>Once everyone is seated.</li></ol>' in html
    assert '<ol start="3"><li>Giada turns.</li></ol>' in html


def test_szenenzeile_am_anfang_faellt_weg_der_rest_bleibt():
    html = web_skript.text_html("SCENE 1 — BEGINNING\nPlace: bar\n\nText.")
    assert "BEGINNING" not in html and "Text." in html
    assert "SCENA 2" not in web_skript.text_html("SCENA 2 — INIZIO\n\nTesto.")


# --- Merkmal 7: Sprecher fett, Regie grau-kursiv ----------------------------

def test_sprecher_fett_und_regie_eigene_klasse():
    html = web_skript.text_html("ARLECCHINO: Excuse me (smiles), is this free?\n(Pause.)")
    assert "<strong>ARLECCHINO:</strong> Excuse me <span class=\"regie\">(smiles)</span>" in html
    assert '<p class="regie">(Pause.)</p>' in html


def test_klammer_in_beschreibung_bleibt_text():
    html = web_skript.text_html("Over music built on the home chord (tonic).")
    assert "regie" not in html


# --- Merkmal 5: G2 Setup als Label+Text, Rollen als Tabelle, details --------

KOPF_G2 = (
    "SETUP\nGoal: a short documentary film.\nPlace: a bar table.\nRules:\n- Only one real participant.\n"
    "- Nobody looks into the camera.\n\nROLES\n"
    "Francesca — the lonely one, the starting image. Character: quiet, a little uneasy, sincere, "
    "patient. What she does: sits alone at the empty table. What never: speaks first. "
    "When she steps in: only when someone sits at her table.\n\n"
    "Arlecchino (Anna) — the recruiter. Character: warm, quick. What she does: brings people."
)


def test_kopf_setup_als_label_und_text(padua):
    html = web_skript.kopf_html(KOPF_G2)
    assert '<h2 class="szenenkopf">Setup &amp; roles</h2>' in html
    assert "<h3>SETUP</h3>" in html and "<h3>ROLES</h3>" in html
    assert '<p class="feld"><strong>Goal</strong><br>a short documentary film.</p>' in html
    assert '<p class="feld"><strong>Rules</strong></p><ul><li>Only one real participant.</li>' in html


def test_kopf_label_mit_klammerzusatz(padua):
    html = web_skript.kopf_html("SETUP\nAbort (whole film): the moment the babbano shows distress.")
    assert '<p class="feld"><strong>Abort (whole film)</strong><br>the moment' in html


def test_kopf_rollen_tabelle_mit_hoechstens_drei_stichworten(padua):
    html = web_skript.kopf_html(KOPF_G2)
    assert "<th>Who</th><th>Role</th><th>Character</th>" in html
    assert "<td><strong>Francesca</strong></td><td>the lonely one, the starting image</td>" \
           "<td>quiet, a little uneasy, sincere</td>" in html
    assert "patient" not in html.split("</table>")[0]


def test_kopf_was_nie_wann_je_person_aufklappbar(padua):
    html = web_skript.kopf_html(KOPF_G2)
    assert html.count('<details class="rolle-mehr">') == 2
    assert "<summary>Francesca — what, never, when</summary>" in html
    teil = html.split("<summary>Francesca")[1].split("</details>")[0]
    assert "<strong>What she does:</strong> sits alone at the empty table." in teil
    assert "<strong>What never:</strong> speaks first." in teil
    assert "<strong>When she steps in:</strong>" in teil


def test_kopf_rollen_im_format_mit_klammer(padua):
    kopf = ("ROLES\nSamuele - the keeper of the harmony (calm, steady, few words). "
            "He plays the guitar.")
    html = web_skript.kopf_html(kopf)
    assert "<td><strong>Samuele</strong></td><td>the keeper of the harmony</td>" \
           "<td>calm, steady, few words</td>" in html
    assert "He plays the guitar." in html.split("<details")[1]


def test_kopf_rolle_ohne_character_klammer_im_rest_ist_kein_charakter(padua):
    kopf = ("ROLES\nCamera / crew — invisible observers. What they do: film from a distance. "
            "When they step in: only at the reveal (to show the footage).")
    html = web_skript.kopf_html(kopf)
    assert "<td><strong>Camera / crew</strong></td><td>invisible observers</td><td></td>" in html
    assert "<strong>What they do:</strong> film from a distance." in html


# --- Merkmal 5/6: Uebersicht ------------------------------------------------

def _s(n, typ, modus=None, volltext=None):
    return {"nummer": n, "titel": f"M{n}", "volltext": volltext,
            "karte": {"typ": typ, "modus": modus, "worum": f"Worum {n} " + "x" * 90}}


def test_partitur_als_tabelle_ohne_drei_spalten(padua):
    html = web_skript.uebersicht_html([_s(1, "moment", "collective"), _s(2, "moment", "microphone"),
                                       _s(3, "moment", "one_to_one"), _s(4, "moment", "none")])
    assert '<section class="probe-szene uebersicht">' in html
    assert "Score at a glance" in html
    assert "<th>#</th><th>Moment</th><th>Where</th>" in html
    assert "<td>1</td><td>M1</td><td>👥 All</td>" in html
    assert "<td>2</td><td>M2</td><td>🎤 Mic</td>" in html
    assert "<td>3</td><td>M3</td><td>👂 1:1</td>" in html
    assert "<td>4</td><td>M4</td><td>—</td>" in html
    assert "colspan" not in html


def test_uebersicht_fuer_anweisungen(padua):
    html = web_skript.uebersicht_html([_s(1, "instructions", volltext="T"), _s(2, "instructions")])
    assert "<h2 class=\"szenenkopf\">Overview</h2>" in html
    assert "<th>#</th><th>Moment</th><th>Theme</th><th>Script</th>" in html
    assert "<td>✓</td>" in html and "<td>—</td>" in html


def test_uebersicht_zaehlt_nur_szenen_mit_karte(padua):
    """G2 auf der DB-Kopie: 2 von 5 Szenen haben schon eine Karte."""
    ohne = {"nummer": 3, "titel": "M3", "volltext": None, "karte": None}
    html = web_skript.uebersicht_html([_s(1, "instructions"), _s(2, "instructions"),
                                       ohne, dict(ohne, nummer=4), dict(ohne, nummer=5)])
    assert "Overview" in html and "<td>5</td><td>M3</td><td></td><td>—</td>" in html


def test_keine_uebersicht_fuer_beschreibung_und_gesprochenes(padua):
    assert web_skript.uebersicht_html([_s(1, "description"), _s(2, "spoken")]) == ""


# --- Verdrahtung in web.py --------------------------------------------------

def _szene(**felder):
    s = {"nummer": 1, "titel": "The First Press", "figuren": [], "prosa": None, "prosa_it": None,
         "verdichtet": {"kern": [], "kernsaetze_kurz": [], "beschreibung": "", "kernsaetze_eigen": [],
                        "zitate": []},
         "volltext": "SCENE 1 — X\n\n> “casa” (Interview 4)",
         "karte": {"typ": "moment", "modus": "collective", "ort": "Empty room", "wer": "Audience"}}
    s.update(felder)
    return s


def test_script_tab_nimmt_den_neuen_renderer_und_badge(padua):
    html, _ = web._probe_szene_html(_szene(), set())
    assert "Interview quote · 4" in html
    assert '<span class="badge">👥 All</span>' in html.split("</h2>")[0]
    assert '<p class="meta">Empty room · Audience</p>' in html


def test_beschreibung_traegt_typ_und_ort_als_meta(padua):
    s = _szene(karte={"typ": "description", "ort": "Rehearsal room"})
    html, _ = web._probe_szene_html(s, set())
    assert '<p class="meta">description · Rehearsal room</p>' in html
    assert "badge" not in html


def test_textbuch_ohne_md_und_txt_aber_mit_pdf(padua):
    daten = {"titel": "G", "chat_id": 1, "figuren": [], "szenen": [_szene()],
             "stage_kopf": KOPF_G2}
    koerper = web.textbuch_koerper(daten, "tok", "/padua")
    assert "textbuch.md" not in koerper and "textbuch.txt" not in koerper
    assert "textbuch.pdf" in koerper
    assert "<th>Who</th>" in koerper and "Score at a glance" in koerper
    assert koerper.index("Setup &amp; roles") < koerper.index("Score at a glance") \
        < koerper.index("Interview quote · 4")


def test_css_design_nur_mit_schalter(padua):
    css = web.css_textbuch_lesbar()
    assert "#e3a440" in css and ".zitat-kopf" in css and "65ch" in css


def test_ohne_schalter_kein_design():
    assert web.css_textbuch_lesbar() == ""
    daten = {"titel": "G", "chat_id": 1, "figuren": [], "szenen": [], "stage_kopf": None}
    assert "textbuch.md" in web.textbuch_koerper(daten, "tok", "/x")


# --- Merkmal 3/5/6: Druck ---------------------------------------------------

def test_druck_css_a4_raender_und_umbrueche():
    css = web_pdf.DRUCK_CSS
    assert "margin: 18mm 18mm 20mm" in css
    # Das alte Druck-CSS der Probenansicht bricht NACH jeder Szene um --
    # sonst stuende die Uebersicht (G3) allein auf Seite 1.
    assert ".stueck > .probe-szene { break-before: page; break-after: auto; page-break-after: auto; }" in css
    assert ".stueck > .uebersicht + .probe-szene" in css
    assert "break-after: avoid" in css
    assert "break-inside: avoid" in css


def test_druck_klappt_die_rollen_auf():
    html = web_pdf.mit_druck_css('<html><head></head><body><details class="rolle-mehr"><summary>x'
                                 "</summary>y</details></body></html>")
    assert '<details class="rolle-mehr" open>' in html

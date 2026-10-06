"""Birk 06.10.2026 14:20: das Dashboard zeigte von 37 Interviews nur 1-3, weil die Liste in
``dd.kurz`` (line-clamp: 3) stand. Mutant: Klasse zurueck auf ``kurz`` -> beide Tests rot."""
from interview_theater import web, web_gestalt


def _g(n):
    return {"arbeitsstand": {}, "figuren": [],
            "interview_kurzformen": [{"name": f"Interview {i}", "kurzformen": [f"k{i}"]} for i in range(1, n + 1)]}


def test_interviewliste_nicht_in_gekapptem_dd():
    html = web._dashboard_inhalt_html(_g(30)) if web._dashboard_inhalt_html.__code__.co_argcount == 1 else web._dashboard_inhalt_html(_g(30), {}, False)
    assert '<dd class="interviews-voll">' in html
    i = html.index('<dd class="interviews-voll">')
    assert "Interview 30" in html[i:]
    assert '<dd class="kurz"><ul class="ergebnisse">' not in html


def test_css_kappt_interviewliste_nicht():
    css = web_gestalt.css_dashboard()
    assert "dd.interviews-voll" in css
    block = css[css.index("dd.interviews-voll"):].split("}")[0]
    assert "line-clamp" not in block

"""Die Browser-Haelfte der sicheren Markdown-Teilmenge (``buehneMarkdown``/
``buehneInline`` in ``web_vereint._VEREINT_JS``), node-geprueft -- dieselbe
Teilmenge wie ``web._buehne_markdown``/``test_buehne_markdown.py``, nur fuer
den Verlauf (``buehneVerlauf``), den der Browser ohne weiteren Serverlauf
anzeigt (``buehneZeige``).

Extraktion per Klammertiefe wie ``test_buehne_nav_js.py`` -- ``buehneMarkdown``
braucht ``buehneEscape`` UND ``buehneInline``, beide werden mitgeschnitten."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_vereint

NODE = shutil.which("node")

_FUNKTIONEN = ("buehneEscape", "buehneInline", "buehneMarkdown")


def _extrahiere(skript: str, name: str) -> str:
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _VEREINT_JS gefunden"
    i = treffer.end()
    tiefe = 1
    while tiefe:
        if skript[i] == "{":
            tiefe += 1
        elif skript[i] == "}":
            tiefe -= 1
        i += 1
    return skript[treffer.start():i]


def _baue_harness() -> str:
    teile = [_extrahiere(web_vereint._VEREINT_JS, name) for name in _FUNKTIONEN]
    return "\n".join(teile)


@pytest.fixture
def harness():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    return _baue_harness()


def _fuehre_aus(tmp_path, harness: str, anhang: str) -> dict:
    pfad = tmp_path / "buehne-markdown.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


def test_fett_wird_strong(tmp_path, harness):
    """Mutant: die Fett-Ersetzung in ``buehneInline`` entfernt."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ html: buehneMarkdown('Das ist **wichtig**.') }));
    """)
    assert ergebnis["html"] == "<p>Das ist <strong>wichtig</strong>.</p>"


def test_kursiv_wird_em(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ html: buehneMarkdown('Das ist *betont*.') }));
    """)
    assert ergebnis["html"] == "<p>Das ist <em>betont</em>.</p>"


def test_aufzaehlung_wird_eine_liste(tmp_path, harness):
    """Mutant: ``schliesseListe()`` wird bei jeder Zeile aufgerufen statt nur
    bei Nicht-Aufzaehlungszeilen -- drei ``<ul>`` statt einer."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ html: buehneMarkdown('- eins\\n- zwei\\n- drei') }));
    """)
    assert ergebnis["html"] == "<ul><li>eins</li><li>zwei</li><li>drei</li></ul>"


def test_zeile_aus_nur_einem_fett_label_wird_ueberschrift(tmp_path, harness):
    """Mutant: die Ueberschrift-Erkennung (``/^\\*\\*([^*]+)\\*\\*$/``)
    entfernt -- die Zeile bliebe ein gewoehnliches ``<p>``."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ html: buehneMarkdown('**What has emerged:**') }));
    """)
    assert ergebnis["html"] == '<p class="buehne-ueberschrift"><strong>What has emerged:</strong></p>'


def test_script_tag_bleibt_reiner_text(tmp_path, harness):
    """XSS-Schutz: ``buehneEscape`` MUSS vor den Markdown-Regeln laufen --
    Mutant: ``buehneEscape(text || '')`` durch ``text || ''`` ersetzt."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ html: buehneMarkdown('<script>alert(1)</script> **fett**') }));
    """)
    assert "<script>" not in ergebnis["html"]
    assert "&lt;script&gt;" in ergebnis["html"]
    assert "<strong>fett</strong>" in ergebnis["html"]

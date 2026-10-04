"""Die reinen Navigationsfunktionen der CoThinker-Tafel, node-geprueft.

Portiert aus ``cothinker/stage/stage.py``s ``blaettern``/
``verlaufUebernehmen``/``male`` (Task 1, Padua CoThinker-Tab clean,
03.10.2026) -- der Zeiger (``pos``) lebt NUR im Browser, nie auf dem
Server, siehe ``web._buehne_html`` und den Report.

Extrahiert die einzelnen Funktionen aus ``web_vereint._VEREINT_JS`` per
Klammertiefe (wie ``test_web_vereint_js_syntax.py`` den ganzen
``<script>``-Block extrahiert, nur hier gezielt je Funktion) und ruft sie
unter Node auf -- diese Funktionen haben keine Abhaengigkeit zum
umschliessenden IIFE/DOM, sie lassen sich also wortwoertlich herausloesen
und direkt aufrufen."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_vereint

NODE = shutil.which("node")

_FUNKTIONEN = (
    "buehneEscape",
    "buehneVorschau",
    "buehneBlaettern",
    "buehneUebernehmen",
    "buehneNavHtml",
)


def _extrahiere(skript: str, name: str) -> str:
    """Schneidet ``function <name>(...) { ... }`` per Klammertiefe aus --
    ein Regex mit einem ``.*?``-Rumpf bricht an der ersten inneren
    schliessenden Klammer ab, das hier nicht."""
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
    pfad = tmp_path / "buehne-nav.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# -- buehneBlaettern (blaettern-Aequivalent) ---------------------------------


def test_blaettern_von_aktuell_einen_schritt_zurueck(tmp_path, harness):
    """pos=null (aktuell), ein Schritt zurueck -> length-2."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      console.log(JSON.stringify({ wert: buehneBlaettern(v, null, -1) }));
    """)
    assert ergebnis["wert"] == 3  # length(5) - 2


def test_blaettern_zum_letzten_index_ist_wieder_aktuell(tmp_path, harness):
    """Vom vorletzten Index einen Schritt vor -> "aktuell" (null), nicht
    der letzte Index selbst -- CoThinkers Regel: der letzte Index UND
    pos===null meinen dieselbe Ansicht."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      console.log(JSON.stringify({ wert: buehneBlaettern(v, 3, 1) }));
    """)
    assert ergebnis["wert"] is None


def test_blaettern_klemmt_unten_bei_null(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      console.log(JSON.stringify({ wert: buehneBlaettern(v, 0, -1) }));
    """)
    assert ergebnis["wert"] == 0


def test_blaettern_klemmt_oben_bei_aktuell(tmp_path, harness):
    """Von "aktuell" (null) einen Schritt vor -> bleibt "aktuell", springt
    nicht ueber das Ende hinaus."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      console.log(JSON.stringify({ wert: buehneBlaettern(v, null, 1) }));
    """)
    assert ergebnis["wert"] is None


# -- buehneUebernehmen (verlaufUebernehmen-Aequivalent) ----------------------


def test_uebernehmen_folgt_der_id_auch_bei_verschobenem_index(tmp_path, harness):
    """Die alte Position zeigte auf id=3 (Index 2). Die neue Liste hat id=1
    verloren (Deckel) und id=6 angehaengt -- id=3 steht jetzt auf Index 1.
    Der Leser soll der ID folgen, nicht dem alten Index."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var alt = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      var neu = [{id:2},{id:3},{id:4},{id:5},{id:6}];
      var r = buehneUebernehmen(alt, 2, neu);
      console.log(JSON.stringify({ pos: r.pos, laenge: r.verlauf.length }));
    """)
    assert ergebnis["pos"] == 1
    assert ergebnis["laenge"] == 5


def test_uebernehmen_faellt_auf_die_aelteste_verbliebene_zurueck(tmp_path, harness):
    """Die alte Position zeigte auf id=1 (Index 0), und genau die ist aus
    der gedeckelten Liste gefallen. Gewaehlter Fallback (wie CoThinker):
    die AELTESTE noch vorhandene Karte halten, nicht ans Ende springen --
    ein Sprung ans Ende waere derselbe unerwartete Ortswechsel, den die
    ganze Portierung vermeiden soll."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var alt = [{id:1},{id:2},{id:3},{id:4},{id:5}];
      var neu = [{id:2},{id:3},{id:4},{id:5},{id:6}];
      var r = buehneUebernehmen(alt, 0, neu);
      console.log(JSON.stringify({ pos: r.pos }));
    """)
    assert ergebnis["pos"] == 0


def test_uebernehmen_laesst_aktuell_aktuell(tmp_path, harness):
    """pos===null bleibt null -- ein frischer Server-Stand darf die
    aktuelle Ansicht nie verschieben, das ist ja gerade "aktuell"."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var alt = [{id:1},{id:2}];
      var neu = [{id:1},{id:2},{id:3}];
      var r = buehneUebernehmen(alt, null, neu);
      console.log(JSON.stringify({ pos: r.pos }));
    """)
    assert ergebnis["pos"] is None


# -- buehneNavHtml (male()-Aequivalent, nur der Text) ------------------------


def test_nav_text_bei_aktuell_zeigt_zaehler_ohne_hinweise(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1,text:'eins'},{id:2,text:'zwei'},{id:3,text:'drei'}];
      var html = buehneNavHtml(v, null, '', ' - back', 'new: ');
      console.log(JSON.stringify({ html: html }));
    """)
    assert "3/3" in ergebnis["html"]
    assert "back" not in ergebnis["html"]
    assert "new:" not in ergebnis["html"]


def test_nav_text_paged_back_ohne_neue_karte_zeigt_keinen_hinweis(tmp_path, harness):
    """Zurueckgeblaettert, aber die neueste id ist seit ``basis``
    unveraendert -- kein "neu:"-Hinweis."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1,text:'eins'},{id:2,text:'zwei'},{id:3,text:'drei'}];
      var html = buehneNavHtml(v, 0, 3, ' - back', 'new: ');
      console.log(JSON.stringify({ html: html }));
    """)
    assert "back" in ergebnis["html"]
    assert "new:" not in ergebnis["html"]
    assert "1/3" in ergebnis["html"]


def test_nav_text_paged_back_mit_neuer_karte_zeigt_den_hinweis(tmp_path, harness):
    """Zurueckgeblaettert, UND die neueste id hat sich seit ``basis``
    geaendert -- der "neu:"-Hinweis erscheint, der Leser wird aber nicht
    dorthin verschoben (das ist Sache von ``buehneZeige``, nicht dieser
    Funktion)."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1,text:'eins'},{id:2,text:'zwei'},{id:3,text:'drei'}];
      var html = buehneNavHtml(v, 0, 2, ' - back', 'new: ');
      console.log(JSON.stringify({ html: html }));
    """)
    assert "new:" in ergebnis["html"]


def test_nav_text_ohne_zweite_karte_ist_leer(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var v = [{id:1,text:'eins'}];
      var html = buehneNavHtml(v, null, '', ' - back', 'new: ');
      console.log(JSON.stringify({ html: html }));
    """)
    assert ergebnis["html"] == ""

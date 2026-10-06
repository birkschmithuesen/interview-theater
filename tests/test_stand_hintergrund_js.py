"""Das Stand-Panel soll auch im Hintergrund weiterpollen -- nur seltener,
nicht gar nicht -- und einen "Neu"-Marker am Tab-Knopf zeigen, wenn sich der
Inhalt waehrend verborgenem Zustand geaendert hat (Birk 06.10.2026, woertlich:
"Ja, Auto-Poll und neuer Marker fuer Werkbank"; Live-Test G3: "Four
characters saved" kam im Chat an, die Werkbank zeigte es nicht, weil Tab/
Browser-Fenster verborgen waren).

Wie ``tests/test_buehne_nav_js.py`` fuer die CoThinker-Navigation: die beiden
reinen Entscheidungsfunktionen (``standTaktErlaubt``/``standEntscheide``) sind
absichtlich frei von DOM/Fetch-Abhaengigkeiten, damit sie sich woertlich aus
``web_vereint._VEREINT_JS`` herausloesen und unter Node einzeln aufrufen
lassen -- und ``ladeStand()`` ruft sie als einzige Entscheidungsstelle, es
gibt also keine zweite, nur-fuer-den-Test nachgebaute Fassung der Logik."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_vereint

NODE = shutil.which("node")

_FUNKTIONEN = (
    "standTaktErlaubt",
    "standEntscheide",
)


def _extrahiere(skript: str, name: str) -> str:
    """Schneidet ``function <name>(...) { ... }`` per Klammertiefe aus --
    wie ``test_buehne_nav_js.py._extrahiere``."""
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
    pfad = tmp_path / "stand-hintergrund.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# -- standTaktErlaubt (Takt-Drosselung im Hintergrund) -----------------------


def test_im_vordergrund_ist_jeder_takt_erlaubt(tmp_path, harness):
    """Sichtbar (``versteckt=false``): keine Drosselung, unabhaengig davon,
    wie kurz der letzte Lauf zurueckliegt."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({
        wert: standTaktErlaubt(false, 1000, 1001, 5000, 4)
      }));
    """)
    assert ergebnis["wert"] is True


def test_im_hintergrund_wird_vor_dem_groesseren_abstand_blockiert(tmp_path, harness):
    """Verborgen (``versteckt=true``), aber der normale Takt (5000ms) ist erst
    einmal vorbei -- noch keine 4x5000ms seit dem letzten Lauf: kein neuer
    Durchlauf, das Intervall ist im Hintergrund groesser, nicht gleich."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({
        wert: standTaktErlaubt(true, 0, 6000, 5000, 4)
      }));
    """)
    assert ergebnis["wert"] is False


def test_im_hintergrund_laeuft_es_nach_dem_groesseren_abstand_wieder(tmp_path, harness):
    """Nach dem vierfachen Takt darf der Hintergrund-Poll wieder laufen --
    komplettes Abschalten (Birks Vorgabe) ist damit ausgeschlossen."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({
        wert: standTaktErlaubt(true, 0, 20000, 5000, 4)
      }));
    """)
    assert ergebnis["wert"] is True


# -- standEntscheide (Tauschen vs. nur Markieren) ----------------------------


def test_unveraenderter_inhalt_tauscht_nicht_und_markiert_nicht(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(standEntscheide('<p>a</p>', '<p>a</p>', false)));
    """)
    assert ergebnis == {"aendern": False, "markieren": False}


def test_leere_antwort_tauscht_nicht_und_markiert_nicht(tmp_path, harness):
    """Ein ``null``/leerer Serverstand (Netzfehler, 404) darf nie den
    bisherigen Inhalt loeschen oder faelschlich einen Marker setzen."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(standEntscheide(null, '<p>a</p>', true)));
    """)
    assert ergebnis == {"aendern": False, "markieren": False}


def test_geaendert_und_sichtbar_tauscht_sofort(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(standEntscheide('<p>b</p>', '<p>a</p>', false)));
    """)
    assert ergebnis == {"aendern": True, "markieren": False}


def test_geaendert_und_verborgen_markiert_nur(tmp_path, harness):
    """Das ist der Kern der Karte: waehrend Tab/Fenster verborgen sind,
    schreibt ein geaenderter Stand NICHT ins Panel (kein unsichtbarer
    Teilzustand), sondern setzt nur den "Neu"-Marker -- der naechste
    sichtbare Takt holt dann frisch, genauso wie ``ladeBuehne()`` es fuer die
    CoThinker-Tafel schon tut."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(standEntscheide('<p>b</p>', '<p>a</p>', true)));
    """)
    assert ergebnis == {"aendern": False, "markieren": True}


# -- Verdrahtung: ladeStand(), der Tab-Marker, zeige()'s "stand"-Zweig ------


def test_ladestand_ist_eine_benannte_funktion():
    """Benannt, damit ``zeige()`` sie beim Oeffnen des Tabs sofort aufrufen
    kann -- wie ``ladeBuehne`` beim ``buehne``-Zweig."""
    assert "function ladeStand" in web_vereint._VEREINT_JS


def test_der_takt_ruft_ladestand_auf():
    js = web_vereint._VEREINT_JS
    treffer = re.search(r"setInterval\(function \(\) \{.*?\}, __NACHLADEN_MS__\);", js, re.DOTALL)
    assert treffer is not None
    assert "ladeStand();" in treffer.group(0)


def test_das_hintergrund_intervall_ist_groesser_als_das_normale():
    """Kein kompletter Stopp im Hintergrund -- nur ein selteneres Intervall
    (Birks Vorgabe, Punkt 1)."""
    js = web_vereint._VEREINT_JS
    treffer = re.search(r"STAND_HINTERGRUND_FAKTOR\s*=\s*(\d+)", js)
    assert treffer is not None
    assert int(treffer.group(1)) > 1


def test_zeige_stand_zweig_raeumt_den_marker_und_laedt_sofort():
    """Analog zum ``buehne``-Zweig (Zeile ~761): Oeffnen des Stand-Tabs
    loescht ``data-neu`` am Tab-Knopf und holt sofort frisch, statt bis zum
    naechsten Takt zu warten."""
    js = web_vereint._VEREINT_JS
    treffer = re.search(r"var zeige = function[\s\S]*?\n  \};", js)
    assert treffer is not None, "zeige() nicht gefunden"
    zweig = treffer.group(0)
    stand_zweig = re.search(r"if \(name === 'stand'\) \{[\s\S]*?\n    \}", zweig)
    assert stand_zweig is not None, "kein eigener 'stand'-Zweig in zeige()"
    text = stand_zweig.group(0)
    assert "dataset.neu" in text
    assert "ladeStand" in text



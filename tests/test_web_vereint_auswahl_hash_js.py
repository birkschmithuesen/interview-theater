"""Stift ✎ in der CoThinker-Klickliste wechselt sofort in den Chat-Tab
(Karte t_269062e2, 06.10.2026): derselbe ``location.hash = '#chat'``-
Mechanismus wie "Fertig sortiert" (``auswahl_fertig_post``), ausgeloest aus
dem VERBATIM-Klick-Handler in ``web_vereint._AUSWAHL_JS``, hier per Node
gegen eine minimale DOM-Attrappe ausgefuehrt (kein Playwright noetig).

✓/✗ aendern den Hash nicht; ein zweiter Tipp auf ✎ (Rueckgaengig, ``wert``
wird "") ebenfalls nicht; ohne Chat-Tab-Knopf auch nicht (wie bei "Fertig
sortiert")."""

import json
import shutil
import subprocess

import pytest

from interview_theater import web_vereint

NODE = shutil.which("node")

_PLATZHALTER = {
    "__BASIS__": "x/",
    "__BASIS_TEIL__": "x/chat/",
}
_TEXT_PLATZHALTER = {
    "__AUSWAHL_ZAEHLER__": "{ja} / {nein} / {schaerfen} / {offen}",
    "__AUSWAHL_FEHLER_NETZ__": "Netzfehler",
    "__AUSWAHL_FEHLER_UNGUELTIG__": "Ungueltig",
}


def _skript() -> str:
    js = web_vereint._AUSWAHL_JS
    for platzhalter, wert in _PLATZHALTER.items():
        js = js.replace(platzhalter, wert)
    for platzhalter, text in _TEXT_PLATZHALTER.items():
        js = js.replace(platzhalter, web_vereint._js_text(text))
    assert "__" not in js  # alle Platzhalter ersetzt
    return js


#: Eine winzige, auf die im Klick-Handler gebrauchten Selektoren
#: zugeschnittene DOM-Attrappe -- kein jsdom, nur Element/closest/
#: querySelector(All) fuer #id, .klasse, [attr]/[attr="wert"] und
#: Nachfahren-Ketten ("A B").
_DOM_STUB = r"""
function Elem(tag, attrs) {
  this.tag = tag;
  this.attrs = Object.assign({}, attrs || {});
  this.children = [];
  this.parent = null;
}
Elem.prototype.appendChild = function (kind) {
  kind.parent = this;
  this.children.push(kind);
  return kind;
};
Elem.prototype.getAttribute = function (name) {
  return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
};
Elem.prototype.setAttribute = function (name, value) {
  this.attrs[name] = String(value);
};
function nachfahren(wurzel) {
  var raus = [];
  (function lauf(knoten) {
    knoten.children.forEach(function (k) { raus.push(k); lauf(k); });
  })(wurzel);
  return raus;
}
function passtEinfach(el, sel) {
  var tagTreffer = sel.match(/^[a-zA-Z0-9_-]+/);
  var rest = sel;
  if (tagTreffer) {
    if (el.tag !== tagTreffer[0]) { return false; }
    rest = rest.slice(tagTreffer[0].length);
  }
  var re = /#([a-zA-Z0-9_-]+)|\.([a-zA-Z0-9_-]+)|\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\]/g;
  var mm;
  while ((mm = re.exec(rest))) {
    if (mm[1] !== undefined) {
      if (el.getAttribute('id') !== mm[1]) { return false; }
    } else if (mm[2] !== undefined) {
      var klassen = ' ' + (el.getAttribute('class') || '') + ' ';
      if (klassen.indexOf(' ' + mm[2] + ' ') === -1) { return false; }
    } else if (mm[3] !== undefined) {
      var wert = el.getAttribute(mm[3]);
      if (wert === null) { return false; }
      if (mm[4] !== undefined && wert !== mm[4]) { return false; }
    }
  }
  return true;
}
function passtKette(el, teile, idx) {
  if (!el || !passtEinfach(el, teile[idx])) { return false; }
  if (idx === 0) { return true; }
  var vorfahr = el.parent;
  while (vorfahr) {
    if (passtKette(vorfahr, teile, idx - 1)) { return true; }
    vorfahr = vorfahr.parent;
  }
  return false;
}
function passtSelektor(el, selektor) {
  var teile = selektor.trim().split(/\s+/);
  return passtKette(el, teile, teile.length - 1);
}
Elem.prototype.closest = function (selektor) {
  var knoten = this;
  while (knoten) {
    if (passtSelektor(knoten, selektor)) { return knoten; }
    knoten = knoten.parent;
  }
  return null;
};
Elem.prototype.querySelectorAll = function (selektor) {
  return nachfahren(this).filter(function (el) { return passtSelektor(el, selektor); });
};
Elem.prototype.querySelector = function (selektor) {
  var alle = this.querySelectorAll(selektor);
  return alle.length ? alle[0] : null;
};

var documentRoot = new Elem('root', {});
var clickListeners = [];
var document = {
  getElementById: function (id) {
    return nachfahren(documentRoot).filter(function (el) {
      return el.getAttribute('id') === id;
    })[0] || null;
  },
  querySelector: function (sel) { return documentRoot.querySelector(sel); },
  querySelectorAll: function (sel) { return documentRoot.querySelectorAll(sel); },
  addEventListener: function (typ, fn) { if (typ === 'click') { clickListeners.push(fn); } },
};
var location = { hash: '' };
var window = {};
var FETCH_LOG = [];
function fetch(url) {
  FETCH_LOG.push(url);
  if (url.indexOf('chat/auswahl') !== -1 && url.indexOf('auswahl_fertig') === -1) {
    return Promise.resolve({ ok: true, status: 200, text: function () { return Promise.resolve(''); } });
  }
  return Promise.resolve({ ok: false, status: 404, text: function () { return Promise.resolve(''); } });
}
"""


def _baue_panel(mit_chat_tab: bool, aktueller_zustand: str):
    panel = (
        "var panel = new Elem('div', "
        "{ id: 'buehne-panel', 'data-ansicht': 'auswahl', 'data-liste': 'fragen' });\n"
        "documentRoot.appendChild(panel);\n"
    )
    if mit_chat_tab:
        panel += (
            "var tabs = new Elem('div', { 'class': 'tabs' });\n"
            "var chatKnopf = new Elem('button', { 'data-tab': 'chat' });\n"
            "tabs.appendChild(chatKnopf);\n"
            "documentRoot.appendChild(tabs);\n"
        )
    panel += (
        f"var li = new Elem('li', {{ 'data-nummer': '4', "
        f"'data-zustand': {json.dumps(aktueller_zustand)} }});\n"
        "panel.appendChild(li);\n"
        "var knoepfeSpan = new Elem('span', { 'class': 'auswahl-knoepfe' });\n"
        "li.appendChild(knoepfeSpan);\n"
        "['ja', 'nein', 'schaerfen'].forEach(function (w) {\n"
        "  var gedrueckt = w === li.getAttribute('data-zustand');\n"
        "  var b = new Elem('button', { 'class': 'auswahl-knopf', 'data-wert': w,\n"
        "    'aria-pressed': gedrueckt ? 'true' : 'false' });\n"
        "  knoepfeSpan.appendChild(b);\n"
        "});\n"
    )
    return panel


@pytest.fixture
def harness():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    return _DOM_STUB + "\n" + _skript() + "\n"


def _klicke(tmp_path, harness: str, geklickter_wert: str, mit_chat_tab: bool = True,
            aktueller_zustand: str = "") -> dict:
    """Baut die Auswahlliste (eine Zeile, drei Knoepfe), simuliert einen
    Klick auf den Knopf mit ``data-wert == geklickter_wert`` -- genau der
    DOM-Pfad, den der VERBATIM extrahierte Klick-Handler durchlaeuft -- und
    liefert ``{"hash": ...}`` zurueck, nachdem alle Promise-Ketten
    (POST + Buchhaltung) abgelaufen sind."""
    aufbau = _baue_panel(mit_chat_tab, aktueller_zustand)
    skript = f"""
{harness}
{aufbau}
var ziel = knoepfeSpan.children.filter(function (b) {{
  return b.getAttribute('data-wert') === {json.dumps(geklickter_wert)};
}})[0];
clickListeners[0]({{ target: ziel, preventDefault: function () {{}} }});
setTimeout(function () {{
  console.log(JSON.stringify({{ hash: location.hash }}));
}}, 0);
"""
    pfad = tmp_path / "auswahl-klick.js"
    pfad.write_text(skript, encoding="utf-8")
    lauf = subprocess.run(["node", str(pfad)], capture_output=True, text=True, timeout=30)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout.strip().splitlines()[-1])


def test_stift_tipp_wechselt_in_den_chat_tab(tmp_path, harness):
    ergebnis = _klicke(tmp_path, harness, "schaerfen")
    assert ergebnis["hash"] == "#chat"


def test_haken_tipp_aendert_den_hash_nicht(tmp_path, harness):
    ergebnis = _klicke(tmp_path, harness, "ja")
    assert ergebnis["hash"] == ""


def test_kreuz_tipp_aendert_den_hash_nicht(tmp_path, harness):
    ergebnis = _klicke(tmp_path, harness, "nein")
    assert ergebnis["hash"] == ""


def test_zweiter_stift_tipp_loescht_und_aendert_den_hash_nicht(tmp_path, harness):
    # aktueller_zustand="schaerfen": der Knopf ist schon gedrueckt
    # (aria-pressed=true) -- der Klick-Handler toggelt auf wert="" (Rueckgaengig).
    ergebnis = _klicke(tmp_path, harness, "schaerfen", aktueller_zustand="schaerfen")
    assert ergebnis["hash"] == ""


def test_stift_tipp_ohne_chat_tab_aendert_den_hash_nicht(tmp_path, harness):
    ergebnis = _klicke(tmp_path, harness, "schaerfen", mit_chat_tab=False)
    assert ergebnis["hash"] == ""

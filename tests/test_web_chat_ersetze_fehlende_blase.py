"""Kanban-Karte t_9dd91550: die wachsende Transkriptblase (Padua, EINE
Blase je Interview, ``web_kanal.WebKanal.sende(transkript=True)`` +
``aendere_text``) blieb G1 im Interview 4 auf dem ersten Teil stehen,
obwohl die Datenbank das volle Transkript trug.

Befund (Code-Nachweis statt Vermutung, Annahme A2 der Karte): der
Poll-Client haelt die Zeile fuer eine Gruppe, deren Stand ueber
``zustand.letzte``/``zustand.aenderung`` getrennt fortschreitet
(``web_chat._CHAT_JS``, ``nimmZustand``/``hole``). Jede Aenderung einer
schon gelieferten Zeile kommt ueber ``geaendert`` und landet in
``ersetze(n)``; **existiert der DOM-Knoten dieser Zeile nicht** (etwa weil
diese Seite ihn nie als ``neu`` bekam -- zweites Geraet jenseits von
``web_daten.CHAT_GRENZE``, oder jeder andere Grund, aus dem die Blase
fehlt), gab ``ersetze`` die Aenderung bisher STILLSCHWEIGEND auf: kein
Fehler, keine neue Blase, und der Server-Zaehler ``aenderung``/``stand``
wandert trotzdem weiter -- ein spaeterer Poll liefert dieselbe Zeile nie
wieder (``web_daten.web_chataenderungen``, ``stand = max(seit, ...)``).

Dieser Test fuehrt ``ersetze``/``blase``/``blaseZu`` VERBATIM (derselbe
Node-Auszug wie ``tests/test_web_vereint_auswahl_hash_js.py``, kein
Playwright) gegen eine winzige DOM-Attrappe aus und belegt den Fehler, dann
die Behebung: eine fehlende Blase wird jetzt angelegt (``blase(n)``) statt
die Aenderung zu verwerfen."""

import json
import shutil
import subprocess

import pytest

from interview_theater import web_chat

NODE = shutil.which("node")

#: Von ``function entferne(element) {`` bis zum Ende von ``ersetze(n)`` --
#: derselbe zusammenhaengende Block aus ``web_chat._CHAT_JS``, der
#: ``blaseZu``, ``blase`` und ``ersetze`` samt ihrer Helfer (``escape``,
#: ``bildVon``, ``textVon``, ``klasseVon``, ``baueLabel``/``baueLeiste``,
#: ``undoInBlase``) traegt -- unveraendert, nur ausgeschnitten.
_START = "  function entferne(element) {"
_ENDE = "\n\n  function nachUnten() {"


def _auszug() -> str:
    js = web_chat._CHAT_JS
    start = js.index(_START)
    ende = js.index(_ENDE, start)
    return js[start:ende]


#: Winzige DOM-Attrappe -- kein jsdom, nur so viel Element/``dataset``/
#: ``classList``/``querySelector(All)`` (``#id``, ``.klasse``,
#: ``[attr]``/``[attr="wert"]``, Nachfahren-Ketten), wie der ausgeschnittene
#: Block braucht. ``dataset`` spiegelt ueber einen ``Proxy`` nach
#: ``data-*``-Attribute, genau wie im echten Browser -- ``blaseZu`` sucht
#: ueber ``[data-id="..."]``.
_DOM_STUB = r"""
function kebab(name) { return name.replace(/[A-Z]/g, function (c) { return '-' + c.toLowerCase(); }); }
function Elem(tag, attrs) {
  this.tag = tag;
  this.attrs = Object.assign({}, attrs || {});
  var self = this;
  this.dataset = new Proxy({}, {
    set: function (obj, key, value) { self.attrs['data-' + kebab(key)] = String(value); obj[key] = value; return true; },
    get: function (obj, key) { return obj[key]; },
  });
  this.children = [];
  this.parentNode = null;
  this._html = '';
  this._text = '';
  this.hidden = false;
  this.disabled = false;
  this.value = '';
  this.style = {};
  this._classes = [];
}
Object.defineProperty(Elem.prototype, 'innerHTML', {
  get: function () { return this._html; },
  set: function (v) { this._html = v; },
});
Object.defineProperty(Elem.prototype, 'textContent', {
  get: function () { return this._text; },
  set: function (v) { this._text = String(v); this._html = this._text; },
});
Object.defineProperty(Elem.prototype, 'className', {
  get: function () { return this._classes.join(' '); },
  set: function (v) { this._classes = String(v).split(/\s+/).filter(Boolean); },
});
function attachClassList(el) {
  el.classList = {
    add: function (c) { if (el._classes.indexOf(c) === -1) { el._classes.push(c); } },
    remove: function (c) { el._classes = el._classes.filter(function (x) { return x !== c; }); },
    toggle: function (c, force) {
      var has = el._classes.indexOf(c) !== -1;
      var on = force === undefined ? !has : !!force;
      if (on && !has) { el._classes.push(c); }
      if (!on && has) { el._classes = el._classes.filter(function (x) { return x !== c; }); }
    },
    contains: function (c) { return el._classes.indexOf(c) !== -1; },
  };
}
Elem.prototype.appendChild = function (kind) {
  kind.parentNode = this;
  this.children.push(kind);
  return kind;
};
Elem.prototype.insertBefore = function (kind, ref) {
  kind.parentNode = this;
  var idx = ref ? this.children.indexOf(ref) : -1;
  if (idx === -1) { this.children.push(kind); } else { this.children.splice(idx, 0, kind); }
  return kind;
};
Elem.prototype.removeChild = function (kind) {
  var idx = this.children.indexOf(kind);
  if (idx !== -1) { this.children.splice(idx, 1); kind.parentNode = null; }
  return kind;
};
Elem.prototype.replaceChild = function (neu, alt) {
  var idx = this.children.indexOf(alt);
  if (idx !== -1) { neu.parentNode = this; alt.parentNode = null; this.children[idx] = neu; }
  return alt;
};
Object.defineProperty(Elem.prototype, 'nextSibling', {
  get: function () {
    if (!this.parentNode) { return null; }
    var idx = this.parentNode.children.indexOf(this);
    return this.parentNode.children[idx + 1] || null;
  },
});
Object.defineProperty(Elem.prototype, 'previousElementSibling', {
  get: function () {
    if (!this.parentNode) { return null; }
    var idx = this.parentNode.children.indexOf(this);
    return this.parentNode.children[idx - 1] || null;
  },
});
Elem.prototype.getAttribute = function (name) {
  if (name === 'id') { return this.attrs.id || null; }
  if (name === 'class') { return this._classes.join(' '); }
  return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
};
Elem.prototype.setAttribute = function (name, value) {
  if (name === 'class') { this.className = value; return; }
  this.attrs[name] = String(value);
};
Elem.prototype.scrollIntoView = function () {};
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
      if (el._classes.indexOf(mm[2]) === -1) { return false; }
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
  var vorfahr = el.parentNode;
  while (vorfahr) {
    if (passtKette(vorfahr, teile, idx - 1)) { return true; }
    vorfahr = vorfahr.parentNode;
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
    knoten = knoten.parentNode;
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
var document = {
  createElement: function (tag) { var e = new Elem(tag, {}); attachClassList(e); return e; },
  getElementById: function (id) {
    return nachfahren(documentRoot).filter(function (el) {
      return el.getAttribute('id') === id;
    })[0] || null;
  },
  querySelector: function (sel) { return documentRoot.querySelector(sel); },
  querySelectorAll: function (sel) { return documentRoot.querySelectorAll(sel); },
  addEventListener: function () {},
};
function neuesElement(tag, attrs) {
  var e = new Elem(tag, attrs);
  attachClassList(e);
  return e;
}

var history = { pushState: function () {}, back: function () {} };
var window = {};
var navigator = {};
var bildOverlay = null;
var bildOverlayImg = null;
var bildOverlaySchliessen = null;
var fehlerFeld = null;
var BASIS = 'x/';
function weg(pfad) { return BASIS + pfad; }
var TEXT = {
  sprache_text: '{dauer} {text}', sprache_laeuft: 'laeuft {dauer}', sprache: '{dauer}',
  datei: '{name}', abkuerzung: 'Abkuerzung:', undo: 'Rueckgaengig', fehler_netz: 'Netzfehler',
};
"""


def _nachricht(id_: int, text: str) -> dict:
    """Dieselbe Form wie ein ``web_post``-Eintrag der Transkriptblase, wie
    ``web_chat._sende_zustand`` sie ausliefert (``typ='transkript'``,
    ``html`` schon serverseitig gefiltert -- hier identisch mit ``text``,
    das Filtern selbst ist nicht Gegenstand dieses Tests)."""
    return {
        "id": id_, "von": "bot", "typ": "transkript", "text": text, "html": text,
        "knoepfe": [], "dauer": None, "dateiname": None, "bild": None,
        "abgetippt": True, "geloescht": False,
    }


def _lauf(tmp_path, anweisungen: list) -> dict:
    if NODE is None:
        pytest.skip("kein node auf PATH")
    skript = (
        _DOM_STUB
        + "\nvar verlauf = neuesElement('div', { id: 'verlauf' });\n"
        + _auszug()
        + "\n"
        + "\n".join(anweisungen)
        + "\nconsole.log(JSON.stringify(__ERGEBNIS__));\n"
    )
    pfad = tmp_path / "ersetze-lauf.js"
    pfad.write_text(skript, encoding="utf-8")
    lauf = subprocess.run(["node", str(pfad)], capture_output=True, text=True, timeout=30)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout.strip().splitlines()[-1])


def test_auszug_enthaelt_blase_ersetze_blasezu():
    auszug = _auszug()
    for name in ("function blase(n)", "function ersetze(n)", "function blaseZu(id)"):
        assert name in auszug


def test_wachsende_blase_mit_vorhandenem_knoten_zeigt_vollen_text(tmp_path):
    """Gegenprobe: existiert die Blase schon (``blase()`` lief fuer diese
    id), schreibt ``ersetze()`` den vollen, gewachsenen Text -- das
    normale Verhalten bleibt unveraendert."""
    anweisungen = [
        f"blase({json.dumps(_nachricht(1030, 'Teil 1'))});",
        f"ersetze({json.dumps(_nachricht(1030, 'Teil 1\n\nTeil 2\n\nTeil 3'))});",
        "var h = blaseZu(1030);",
        "var __ERGEBNIS__ = { html: h ? h.innerHTML : null, anzahl: verlauf.querySelectorAll('.blase').length };",
    ]
    ergebnis = _lauf(tmp_path, anweisungen)
    assert ergebnis["html"] == "Teil 1\n\nTeil 2\n\nTeil 3"
    assert ergebnis["anzahl"] == 1


def test_aenderung_ohne_vorhandene_blase_legt_sie_jetzt_an(tmp_path):
    """Der Befund der Karte: eine ``geaendert``-Zeile, fuer die diese Seite
    nie ein ``blase()`` sah (zweites Geraet, Blase jenseits von
    ``CHAT_GRENZE`` o.ae.), muss trotzdem sichtbar werden -- ``ersetze()``
    legt die Blase jetzt an, statt die Aenderung wortlos zu verwerfen."""
    anweisungen = [
        f"ersetze({json.dumps(_nachricht(2040, 'Teil 1 (nie gesehen)\n\nTeil 2\n\nTeil 3'))});",
        "var h = blaseZu(2040);",
        "var __ERGEBNIS__ = { html: h ? h.innerHTML : null, anzahl: verlauf.querySelectorAll('.blase').length };",
    ]
    ergebnis = _lauf(tmp_path, anweisungen)
    assert ergebnis["html"] == "Teil 1 (nie gesehen)\n\nTeil 2\n\nTeil 3"
    assert ergebnis["anzahl"] == 1


def test_geloeschte_nachricht_ohne_vorhandene_blase_legt_keine_an(tmp_path):
    """``n.geloescht`` bleibt Vorrang: eine geloeschte Zeile, die diese
    Seite nie hatte, bekommt keine Blase nachtraeglich angelegt."""
    geloescht = _nachricht(3050, "irrelevant")
    geloescht["geloescht"] = True
    anweisungen = [
        f"ersetze({json.dumps(geloescht)});",
        "var __ERGEBNIS__ = { anzahl: verlauf.querySelectorAll('.blase').length };",
    ]
    ergebnis = _lauf(tmp_path, anweisungen)
    assert ergebnis["anzahl"] == 0

"""``AudioWarteschlangenSpeicher`` (``web_chat._PERSISTENZ_JS``) WOERTLICH in
Node, gegen einen minimalen IndexedDB-Fake -- kein Browser, kein echtes
``fake-indexeddb``-Paket (das Repo hat kein npm, Karte t_e2b0e489 verlangt
ausdruecklich einen selbst geschriebenen Shim).

Was hier NICHT geprueft wird: dass ``web_chat._CHAT_JS`` dieses Modul an den
richtigen Stellen aufruft (Wake Lock, ``reiheEin``, ``erledigt``) -- das
steht in ``tests/test_web_chat_js.py`` (am gerenderten HTML/JS) und, wo
Playwright zur Verfuegung steht, in ``tests/e2e``. Hier steht nur, dass das
Speichermodul selbst tut, was die Karte verlangt: VOR dem Eintritt in die
Warteschlange schreiben, nach einer Antwort loeschen, bei nichts (Netzfehler)
behalten, in Reihenfolge wiederherstellen, den Speicherdeckel nur gegen
bestaetigte Eintraege durchsetzen.
"""

import json
import shutil
import subprocess
import textwrap

import pytest

from interview_theater import web_chat

#: Ein IndexedDB-Fake, gerade genug fuer das, was
#: ``AudioWarteschlangenSpeicher`` tatsaechlich benutzt: ``open`` (mit
#: ``onupgradeneeded``/``createObjectStore``), eine Transaktion mit
#: ``oncomplete``/``onerror``, und an ihrem Store ``put``/``delete``/``get``/
#: ``getAll``. Jede Anfrage feuert ihr ``onsuccess`` einen Mikrotask spaeter
#: (wie eine echte IndexedDB-Implementierung asynchron ist), die Transaktion
#: "committet" zwei Mikrotasks nach ihrer Erzeugung -- das reicht fuer jede
#: Abfolge, die das Modul tatsaechlich macht (ein get/put/delete je
#: Transaktion, nie zwei nacheinander auf derselben).
_FAKE_INDEXEDDB_JS = """
var __ERZWINGE_DELETE_FEHLER__ = false;
function erzwingeDeleteFehler(wert) { __ERZWINGE_DELETE_FEHLER__ = wert; }

function baueFakeIndexedDB() {
  var datenbanken = {};

  function neuesRequest() {
    return { onsuccess: null, onerror: null, result: undefined, error: null };
  }
  function erfolgSpaeter(req, ergebnis) {
    Promise.resolve().then(function () {
      req.result = ergebnis;
      if (req.onsuccess) { req.onsuccess({ target: req }); }
    });
  }

  // ``meldeFehler`` traegt einen fehlgeschlagenen Request an seine
  // Transaktion weiter -- echtes IndexedDB laesst eine Transaktion mit
  // einem fehlgeschlagenen Request ebenfalls scheitern (``onerror`` statt
  // ``oncomplete``), nicht nur den einzelnen Request.
  function baueStore(map, meldeFehler) {
    return {
      put: function (wert) {
        var req = neuesRequest();
        map.set(wert.id, wert);
        erfolgSpaeter(req, wert.id);
        return req;
      },
      delete: function (key) {
        var req = neuesRequest();
        if (__ERZWINGE_DELETE_FEHLER__) {
          Promise.resolve().then(function () {
            req.error = new Error('fake Speicherfehler beim Loeschen');
            if (meldeFehler) { meldeFehler(req.error); }
            if (req.onerror) { req.onerror({ target: req }); }
          });
        } else {
          map.delete(key);
          erfolgSpaeter(req, undefined);
        }
        return req;
      },
      get: function (key) {
        var req = neuesRequest();
        erfolgSpaeter(req, map.get(key));
        return req;
      },
      getAll: function () {
        var req = neuesRequest();
        erfolgSpaeter(req, Array.from(map.values()));
        return req;
      }
    };
  }

  function baueTransaktion(stores) {
    var tx = { oncomplete: null, onerror: null, error: null };
    var fehlgeschlagen = false;
    tx.objectStore = function (name) {
      return baueStore(stores[name], function (fehler) {
        fehlgeschlagen = true;
        tx.error = fehler;
      });
    };
    Promise.resolve().then(function () {
      Promise.resolve().then(function () {
        if (fehlgeschlagen) { if (tx.onerror) { tx.onerror(); } }
        else if (tx.oncomplete) { tx.oncomplete(); }
      });
    });
    return tx;
  }

  function baueDb(eintrag) {
    return {
      objectStoreNames: {
        contains: function (n) {
          return Object.prototype.hasOwnProperty.call(eintrag.stores, n);
        }
      },
      createObjectStore: function (name) {
        eintrag.stores[name] = new Map();
        return baueStore(eintrag.stores[name]);
      },
      transaction: function () { return baueTransaktion(eintrag.stores); }
    };
  }

  return {
    open: function (name, _version) {
      var req = neuesRequest();
      var neu = !datenbanken[name];
      if (neu) { datenbanken[name] = { stores: {} }; }
      var db = baueDb(datenbanken[name]);
      Promise.resolve().then(function () {
        req.result = db;
        if (neu && req.onupgradeneeded) { req.onupgradeneeded({ target: req }); }
        Promise.resolve().then(function () {
          if (req.onsuccess) { req.onsuccess({ target: req }); }
        });
      });
      return req;
    }
  };
}
var indexedDB = baueFakeIndexedDB();
"""


def _persistenz_lauf(tmp_path, js_schnipsel: str, *, mit_indexeddb: bool = True) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node nicht installiert")
    bausteine = [web_chat._PERSISTENZ_JS]
    if mit_indexeddb:
        bausteine.insert(0, _FAKE_INDEXEDDB_JS)
    quelltext = "\n".join(bausteine) + """
var r = {};
Promise.resolve().then(function () {
%s
}).then(function () {
  console.log(JSON.stringify(r));
}, function (fehler) {
  console.log(JSON.stringify({ _fehler: String((fehler && fehler.stack) || fehler) }));
});
""" % textwrap.indent(js_schnipsel.strip(), "  ")
    datei = tmp_path / "persistenz.js"
    datei.write_text(quelltext, encoding="utf-8")
    ergebnis = subprocess.run([node, str(datei)], capture_output=True, text=True, timeout=30)
    assert ergebnis.returncode == 0, ergebnis.stderr
    zeilen = [z for z in ergebnis.stdout.strip().splitlines() if z]
    ausgabe = json.loads(zeilen[-1])
    assert "_fehler" not in ausgabe, ausgabe.get("_fehler")
    return ausgabe


# -- Feature-Detect ------------------------------------------------------


def test_unterstuetzt_ist_falsch_ohne_indexeddb(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    return Promise.resolve().then(function () {
      r.unterstuetzt = AudioWarteschlangenSpeicher.unterstuetzt();
    });
    """, mit_indexeddb=False)
    assert r["unterstuetzt"] is False


def test_unterstuetzt_ist_wahr_mit_indexeddb(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    return Promise.resolve().then(function () {
      r.unterstuetzt = AudioWarteschlangenSpeicher.unterstuetzt();
    });
    """)
    assert r["unterstuetzt"] is True


# -- Job wird VOR dem Einreihen persistiert ------------------------------


def test_job_ist_nach_dem_speichern_in_der_wiederherstellung_da(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-1', blob: { size: 1234 }, dauer: 5,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-a', 100)
      .then(function () {
        return AudioWarteschlangenSpeicher.wiederherstellen('tok-a');
      })
      .then(function (liste) {
        r.n = liste.length;
        r.dauer = liste[0] && liste[0].dauer;
        r.id = liste[0] && liste[0].clientJobId;
      });
    """)
    assert r["n"] == 1
    assert r["dauer"] == 5
    assert r["id"] == "job-1"


def test_speichern_schliesst_vor_der_fortsetzung_ab(tmp_path):
    """Die Karte verlangt: VOR dem Eintritt in die In-Memory-Queue
    geschrieben. Hier heisst das: der Aufrufer darf erst nach dem
    aufgeloesten Versprechen weitermachen -- und genau dann steht der
    Eintrag schon vollstaendig in der Wiederherstellung."""
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-2', blob: { size: 10 }, dauer: 9,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: null };
    var geschriebenVorFortsetzung = false;
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-b', 1)
      .then(function () {
        geschriebenVorFortsetzung = true;
        return AudioWarteschlangenSpeicher.wiederherstellen('tok-b');
      })
      .then(function (liste) {
        r.geschriebenVorFortsetzung = geschriebenVorFortsetzung;
        r.n = liste.length;
      });
    """)
    assert r["geschriebenVorFortsetzung"] is True
    assert r["n"] == 1


# -- geloescht bei 2xx -----------------------------------------------------


def test_entferne_nach_antwort_loescht_den_eintrag(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-3', blob: { size: 10 }, dauer: 3,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-c', 1)
      .then(function () { return AudioWarteschlangenSpeicher.entferneNachAntwort(auftrag); })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-c'); })
      .then(function (liste) { r.n = liste.length; });
    """)
    assert r["n"] == 0


# -- behalten bei Netzwerkfehler -------------------------------------------


def test_ohne_entferne_nach_antwort_bleibt_der_eintrag(tmp_path):
    """Ein Netzfehler ruft serverseitig nie ``entferneNachAntwort`` --
    exakt das simuliert dieser Test, indem er es einfach auslaesst."""
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-4', blob: { size: 10 }, dauer: 4,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-d', 1)
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-d'); })
      .then(function (liste) { r.n = liste.length; });
    """)
    assert r["n"] == 1


# -- in Reihenfolge wiederhergestellt --------------------------------------


def test_wiederherstellen_sortiert_nach_seq_nicht_nach_schreibreihenfolge(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var a = { clientJobId: 'job-spaeter', blob: { size: 1 }, dauer: 1,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    var b = { clientJobId: 'job-frueher', blob: { size: 1 }, dauer: 2,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    var c = { clientJobId: 'job-mitte', blob: { size: 1 }, dauer: 3,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    // Absichtlich in der "falschen" Reihenfolge geschrieben (hoher seq
    // zuerst) -- die Wiederherstellung muss trotzdem nach seq sortieren.
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(a, 'tok-e', 30)
      .then(function () { return AudioWarteschlangenSpeicher.speichereVorEinreihung(b, 'tok-e', 10); })
      .then(function () { return AudioWarteschlangenSpeicher.speichereVorEinreihung(c, 'tok-e', 20); })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-e'); })
      .then(function (liste) { r.reihenfolge = liste.map(function (e) { return e.clientJobId; }); });
    """)
    assert r["reihenfolge"] == ["job-frueher", "job-mitte", "job-spaeter"]


def test_wiederherstellen_ist_je_gruppen_schluessel_getrennt(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var a = { clientJobId: 'job-g1', blob: { size: 1 }, dauer: 1,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    var b = { clientJobId: 'job-g2', blob: { size: 1 }, dauer: 1,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(a, 'gruppe-1', 1)
      .then(function () { return AudioWarteschlangenSpeicher.speichereVorEinreihung(b, 'gruppe-2', 1); })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('gruppe-1'); })
      .then(function (liste) { r.n = liste.length; r.id = liste[0] && liste[0].clientJobId; });
    """)
    assert r["n"] == 1
    assert r["id"] == "job-g1"


def test_wiederherstellen_rekonstruiert_die_diskussions_sitzung(tmp_path):
    """Ein Segment des Hintergrund-Mithoerens (Phase 1/4) muss nach einem
    Neuladen wieder mit demselben Ziel ('diskussion'/'brainstorm') hochgehen
    -- postAudio() liest das aus auftrag.sitzung.ziel."""
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-disk', blob: { size: 1 }, dauer: 1,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: { art: 'diskussion', ziel: 'brainstorm' } };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-f', 1)
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-f'); })
      .then(function (liste) {
        r.sitzungArt = liste[0].sitzung && liste[0].sitzung.art;
        r.ziel = liste[0].sitzung && liste[0].sitzung.ziel;
        r.wiederhergestellt = liste[0]._wiederhergestellt;
      });
    """)
    assert r["sitzungArt"] == "diskussion"
    assert r["ziel"] == "brainstorm"
    assert r["wiederhergestellt"] is True


def test_wiederherstellen_ohne_diskussion_hat_keine_sitzung(tmp_path):
    """Ein Interview-Segment oder ein PTT-Klotz hat live keine Sitzung, die
    der Server fuer die Zuordnung braucht (die entscheidet serverseitig
    allein der offene Interviewmodus, nicht ein Client-Flag) -- die
    Wiederherstellung darf hier keine erfinden."""
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-interview', blob: { size: 1 }, dauer: 1,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: { art: 'interview' } };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-g', 1)
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-g'); })
      .then(function (liste) { r.sitzung = liste[0].sitzung; });
    """)
    assert r["sitzung"] is None


# -- Speichergrenze: aelteste BESTAETIGTE zuerst, unbestaetigte nie --------


def test_raeumeauf_laesst_unbestaetigte_jobs_unberuehrt_ueber_dem_deckel(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var gross = AudioWarteschlangenSpeicher.SPEICHER_DECKEL_BYTES;
    var a = { clientJobId: 'job-a', blob: { size: gross }, dauer: 1,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    var b = { clientJobId: 'job-b', blob: { size: gross }, dauer: 1,
              grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    // Beide unbestaetigt (kein entferneNachAntwort, keine Markierung) --
    // selbst weit ueber dem Deckel darf raeumeAuf hier nichts loeschen.
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(a, 'tok-h', 1)
      .then(function () { return AudioWarteschlangenSpeicher.speichereVorEinreihung(b, 'tok-h', 2); })
      .then(function () { return AudioWarteschlangenSpeicher.raeumeAuf(); })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-h'); })
      .then(function (liste) { r.n = liste.length; });
    """)
    assert r["n"] == 2


def test_raeumeauf_entfernt_die_aelteste_bestaetigte_zuerst(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var gross = Math.ceil(AudioWarteschlangenSpeicher.SPEICHER_DECKEL_BYTES / 2) + 1024;
    var alt = { clientJobId: 'job-alt', blob: { size: gross }, dauer: 1,
                grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    var neu = { clientJobId: 'job-neu', blob: { size: gross }, dauer: 1,
                grund: null, redeMs: null, weichMs: null, kalibrierung: false, sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(alt, 'tok-i', 1)
      .then(function () { return AudioWarteschlangenSpeicher.speichereVorEinreihung(neu, 'tok-i', 2); })
      .then(function () { return AudioWarteschlangenSpeicher.markiereBestaetigt('job-alt'); })
      .then(function () { return AudioWarteschlangenSpeicher.markiereBestaetigt('job-neu'); })
      .then(function () { return AudioWarteschlangenSpeicher.raeumeAuf(); })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-i'); })
      .then(function (liste) { r.verbleibend = liste.map(function (e) { return e.clientJobId; }); });
    """)
    assert r["verbleibend"] == ["job-neu"]


# -- entferneNachAntwort markiert bei einem Loeschfehler statt zu raten ---


def test_entferne_nach_antwort_markiert_bestaetigt_wenn_loeschen_scheitert(tmp_path):
    r = _persistenz_lauf(tmp_path, """
    var auftrag = { clientJobId: 'job-5', blob: { size: 10 }, dauer: 1,
                     grund: null, redeMs: null, weichMs: null, kalibrierung: false,
                     sitzung: null };
    return AudioWarteschlangenSpeicher.speichereVorEinreihung(auftrag, 'tok-j', 1)
      .then(function () {
        // Den Fake so stellen, dass loesche() scheitert (z.B. Safari
        // privat/voller Speicher) -- entferneNachAntwort() faengt das ab.
        erzwingeDeleteFehler(true);
        return AudioWarteschlangenSpeicher.entferneNachAntwort(auftrag);
      })
      .then(function () {
        erzwingeDeleteFehler(false);
        return AudioWarteschlangenSpeicher.raeumeAuf();
      })
      .then(function () { return AudioWarteschlangenSpeicher.wiederherstellen('tok-j'); })
      .then(function (liste) { r.n = liste.length; });
    """)
    # Der Loeschversuch ist gescheitert: der Eintrag bleibt da (nicht
    # stillschweigend verloren) -- ohne Deckeldruck raeumt raeumeAuf() ihn
    # nicht weg, auch wenn er inzwischen als bestaetigt markiert ist.
    assert r["n"] == 1

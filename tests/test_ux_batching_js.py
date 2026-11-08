"""Das UX-Ereignis-Batching im Browser (Karte t_10a31406), node-geprueft.

Extrahiert die reinen Funktionen aus ``web_vereint._UX_JS`` per
Klammertiefe (wie ``tests/test_buehne_nav_js.py`` es fuer die
CoThinker-Navigation tut) und ruft sie woertlich unter Node auf -- das ist
der echte Client-Code, keine Python-Nachbildung der JS-Logik."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_vereint

NODE = shutil.which("node")

_FUNKTIONEN = (
    "uxZufallsId",
    "uxGeraeteId",
    "uxExtraFiltern",
    "uxNeuesEreignis",
    "uxWarteschlangeHinzufuegen",
    "uxStapelAbschneiden",
    "uxRageZiel",
)


def _extrahiere(skript: str, name: str) -> str:
    """Schneidet ``function <name>(...) { ... }`` per Klammertiefe aus."""
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _UX_JS gefunden"
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
    return "\n".join(_extrahiere(web_vereint._UX_JS, name) for name in _FUNKTIONEN)


@pytest.fixture
def harness():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    return _baue_harness()


def _fuehre_aus(tmp_path, harness: str, anhang: str) -> dict:
    pfad = tmp_path / "ux-batching.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# -- uxExtraFiltern: kein Freitext, keine Transkript-/Chatinhalte -----------


def test_extra_filtern_behaelt_erlaubte_zahlenfelder(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxExtraFiltern({ von: 1, nach: 4, n: 3 })));
    """)
    assert ergebnis == {"von": 1, "nach": 4, "n": 3}


@pytest.mark.parametrize("schmuggel", [
    {"text": "Freitext aus dem Chat"},
    {"transkript": "woertliches Interviewmaterial"},
    {"nachricht": "frei formuliert"},
    {"zitat": "ein Belegzitat"},
])
def test_extra_filtern_streicht_jeden_freitextfeldversuch(tmp_path, harness, schmuggel):
    ergebnis = _fuehre_aus(tmp_path, harness, f"""
      console.log(JSON.stringify(uxExtraFiltern({json.dumps(schmuggel)})));
    """)
    assert ergebnis == {}


def test_extra_filtern_streicht_string_unter_zahlenfeld(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxExtraFiltern({ von: 'ein ganzer Satz' })));
    """)
    assert ergebnis == {}


def test_extra_filtern_erlaubt_eine_kurze_msg_fuer_js_fehler(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxExtraFiltern({ msg: 'TypeError: x', zeile: 12 })));
    """)
    assert ergebnis == {"msg": "TypeError: x", "zeile": 12}


def test_extra_filtern_begrenzt_msg_auf_160_zeichen(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify({ laenge: uxExtraFiltern({ msg: 'x'.repeat(500) }).msg.length }));
    """)
    assert ergebnis["laenge"] == 160


def test_extra_filtern_ohne_dict_liefert_leeres_objekt(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxExtraFiltern('kein objekt')));
    """)
    assert ergebnis == {}


def test_extra_filtern_nan_und_infinity_werden_gestrichen(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxExtraFiltern({ von: NaN, nach: Infinity })));
    """)
    assert ergebnis == {}


# -- uxNeuesEreignis: baut nur, was wirklich da ist --------------------------


def test_neues_ereignis_laesst_optionale_felder_weg_wenn_nicht_gesetzt(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxNeuesEreignis('klick', 'knopf:stift', null, 1000)));
    """)
    assert ergebnis == {"typ": "klick", "ziel": "knopf:stift", "t": 1000}


def test_neues_ereignis_traegt_phase_und_dauer_wenn_gesetzt(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxNeuesEreignis('tab_wechsel', 'tab:buehne', 4, 1000, 2500)));
    """)
    assert ergebnis == {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1000,
                        "phase": 4, "dauer_ms": 2500}


def test_neues_ereignis_haengt_gefiltertes_extra_nur_an_wenn_nicht_leer(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(
        uxNeuesEreignis('klick', 'knopf:stift', null, 1000, null, { text: 'frei' })
      ));
    """)
    assert "extra" not in ergebnis


# -- uxWarteschlangeHinzufuegen: FIFO-Deckel ---------------------------------


def test_warteschlange_haengt_an_bis_zur_grenze(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var q = [];
      uxWarteschlangeHinzufuegen(q, 3, { n: 1 });
      uxWarteschlangeHinzufuegen(q, 3, { n: 2 });
      uxWarteschlangeHinzufuegen(q, 3, { n: 3 });
      console.log(JSON.stringify(q));
    """)
    assert ergebnis == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_warteschlange_verwirft_das_aelteste_ueber_der_grenze(tmp_path, harness):
    """Ohne Netz waechst die Warteschlange nicht unbegrenzt -- das AELTESTE
    Ereignis faellt weg, nicht das juengste (FIFO, nicht LIFO)."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var q = [{ n: 1 }, { n: 2 }, { n: 3 }];
      uxWarteschlangeHinzufuegen(q, 3, { n: 4 });
      console.log(JSON.stringify(q));
    """)
    assert ergebnis == [{"n": 2}, {"n": 3}, {"n": 4}]


# -- uxStapelAbschneiden: <= 50 Ereignisse, <= 2 KB, Rest bleibt erhalten ----


def test_stapel_abschneiden_unter_beiden_grenzen_nimmt_alles(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var e = [{ t: 1 }, { t: 2 }, { t: 3 }];
      var r = uxStapelAbschneiden(e, 50, 2048);
      console.log(JSON.stringify({ stapel: r.stapel.length, rest: r.rest.length }));
    """)
    assert ergebnis == {"stapel": 3, "rest": 0}


def test_stapel_abschneiden_kappt_bei_der_zaehlgrenze(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var e = [];
      for (var i = 0; i < 80; i++) { e.push({ t: i }); }
      var r = uxStapelAbschneiden(e, 50, 100000);
      console.log(JSON.stringify({ stapel: r.stapel.length, rest: r.rest.length,
                                    ersterRest: r.rest[0].t }));
    """)
    assert ergebnis == {"stapel": 50, "rest": 30, "ersterRest": 50}


def test_stapel_abschneiden_kappt_bei_der_byte_grenze(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var e = [];
      for (var i = 0; i < 50; i++) { e.push({ typ: 'klick', ziel: 'knopf:stift', t: 1000 }); }
      var r = uxStapelAbschneiden(e, 50, 500);
      console.log(JSON.stringify({
        stapelBytes: JSON.stringify(r.stapel).length,
        stapel: r.stapel.length,
        rest: r.rest.length
      }));
    """)
    assert ergebnis["stapel"] > 0
    assert ergebnis["stapelBytes"] <= 500
    assert ergebnis["stapel"] + ergebnis["rest"] == 50


def test_stapel_abschneiden_verwirft_ein_einzeln_zu_grosses_ereignis(tmp_path, harness):
    """Ein Ereignis, das allein schon ueber der Byte-Grenze liegt, darf die
    Warteschlange nicht fuer immer blockieren -- es wird verworfen, der
    naechste gueltige Nachbar geht trotzdem raus."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var riesig = { typ: 'klick', ziel: 'x'.repeat(2000), t: 1 };
      var klein = { typ: 'klick', ziel: 'knopf:stift', t: 2 };
      var r = uxStapelAbschneiden([riesig, klein], 50, 500);
      console.log(JSON.stringify({ stapel: r.stapel, rest: r.rest }));
    """)
    assert ergebnis["stapel"] == [{"typ": "klick", "ziel": "knopf:stift", "t": 2}]
    assert ergebnis["rest"] == []


def test_stapel_abschneiden_leere_liste(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var r = uxStapelAbschneiden([], 50, 2048);
      console.log(JSON.stringify({ stapel: r.stapel.length, rest: r.rest.length }));
    """)
    assert ergebnis == {"stapel": 0, "rest": 0}


# -- uxRageZiel: derselbe Tipp binnen 1 s gilt als Rage-Tap ------------------


def test_rage_ziel_erster_tipp_ist_kein_rage_tap(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxRageZiel({}, 'knopf:stift', 1000, 1000)));
    """)
    assert ergebnis is False


def test_rage_ziel_zweiter_tipp_innerhalb_der_schwelle_ist_rage_tap(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var karte = {};
      uxRageZiel(karte, 'knopf:stift', 1000, 1000);
      console.log(JSON.stringify(uxRageZiel(karte, 'knopf:stift', 1500, 1000)));
    """)
    assert ergebnis is True


def test_rage_ziel_nach_der_schwelle_ist_wieder_kein_rage_tap(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var karte = {};
      uxRageZiel(karte, 'knopf:stift', 1000, 1000);
      console.log(JSON.stringify(uxRageZiel(karte, 'knopf:stift', 3000, 1000)));
    """)
    assert ergebnis is False


def test_rage_ziel_verschiedene_ziele_stoeren_sich_nicht(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      var karte = {};
      uxRageZiel(karte, 'knopf:stift', 1000, 1000);
      console.log(JSON.stringify(uxRageZiel(karte, 'knopf:groesse', 1050, 1000)));
    """)
    assert ergebnis is False


# -- uxGeraeteId: stabil je Schluessel, kein Fingerprint ---------------------


def _speicher_js() -> str:
    return """
    function neuerSpeicher(start) {
      var daten = Object.assign({}, start || {});
      return {
        daten: daten,
        getItem: function (k) { return Object.prototype.hasOwnProperty.call(daten, k) ? daten[k] : null; },
        setItem: function (k, v) { daten[k] = String(v); }
      };
    }
    """


def test_geraet_id_wird_beim_ersten_mal_erzeugt_und_gespeichert(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness + _speicher_js(), """
      var s = neuerSpeicher();
      var zaehler = 0;
      var id = uxGeraeteId(s, 'ux_geraet:tok', function () { zaehler++; return 'ERZEUGT'; });
      console.log(JSON.stringify({ id: id, gespeichert: s.daten['ux_geraet:tok'], zaehler: zaehler }));
    """)
    assert ergebnis == {"id": "ERZEUGT", "gespeichert": "ERZEUGT", "zaehler": 1}


def test_geraet_id_liest_eine_vorhandene_id_statt_neu_zu_wuerfeln(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness + _speicher_js(), """
      var s = neuerSpeicher({ 'ux_geraet:tok': 'ALT' });
      var id = uxGeraeteId(s, 'ux_geraet:tok', function () { return 'NEU'; });
      console.log(JSON.stringify({ id: id }));
    """)
    assert ergebnis == {"id": "ALT"}


def test_geraet_id_ist_je_token_getrennt(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness + _speicher_js(), """
      var s = neuerSpeicher();
      var a = uxGeraeteId(s, 'ux_geraet:tokenA', function () { return 'A'; });
      var b = uxGeraeteId(s, 'ux_geraet:tokenB', function () { return 'B'; });
      console.log(JSON.stringify({ a: a, b: b }));
    """)
    assert ergebnis == {"a": "A", "b": "B"}


def test_geraet_id_ohne_speicher_faellt_auf_den_zufall_zurueck(tmp_path, harness):
    """Privater Modus/alter Browser: ``localStorage`` fehlt -- dann gibt es
    kein stabiles Geraet, aber immer noch eine ID fuer diese eine Charge."""
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify(uxGeraeteId(null, 'ux_geraet:tok', function () { return 'X'; })));
    """)
    assert ergebnis == "X"


def test_zufalls_id_ist_kein_leerer_string_und_variiert(tmp_path, harness):
    ergebnis = _fuehre_aus(tmp_path, harness, """
      console.log(JSON.stringify([uxZufallsId(), uxZufallsId()]));
    """)
    assert ergebnis[0] and ergebnis[1]
    assert ergebnis[0] != ergebnis[1]


# -- die ganze IIFE bleibt syntaktisch gueltiges JS --------------------------


def test_ux_js_ist_gueltiges_javascript():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    skript = (
        web_vereint._UX_JS.replace("__BASIS__", "tok/")
        .replace("__MAX_EVENTS__", "50").replace("__MAX_BYTES__", "2048")
    )
    lauf = subprocess.run([NODE, "--check", "-"], input=skript,
                          capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr

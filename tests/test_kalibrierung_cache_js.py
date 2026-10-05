"""Der Raumcheck-Cache gilt je Gruppe und Tag (Birk, Live-Test 05.10.2026).

Vorher lag das Kalibrierungsergebnis unter festen ``localStorage``-
Schluesseln (``vad_boden_mess`` usw.) und galt fuer die ganze Domain: eine
Messung in Gruppe 1 uebersprang den Raumcheck in Gruppe 2 und in der
Testgruppe. Jetzt tragen die Schluessel die Gruppenkennung aus dem Pfad
(``/g/<token>``) und das lokale Datum -- je Gruppe und Tag einmal
automatisch messen; alte, ungekeyte Schluessel werden nicht mehr gelesen.

Die reinen Funktionen werden per Klammertiefe aus ``web_chat._CHAT_JS``
geschnitten (wie ``tests/test_buehne_nav_js.py``) und in einem echten
Chromium ausgefuehrt -- nicht in Node: unter dem Test-Aufruf mit
``env -i PATH=/usr/bin:/bin`` liegt kein ``node`` im PATH, ein Node-Test
liefe dort nur als "skipped"."""

import re

import pytest

from interview_theater import web_chat

sync_api = pytest.importorskip("playwright.sync_api")

_FUNKTIONEN = (
    "kalGruppeAus",
    "kalDatum",
    "kalSchluessel",
    "kalibrierungCacheLesen",
    "kalibrierungCacheSchreiben",
)


def _extrahiere(skript: str, name: str) -> str:
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _CHAT_JS gefunden"
    i, tiefe = treffer.end(), 1
    while tiefe:
        if skript[i] == "{":
            tiefe += 1
        elif skript[i] == "}":
            tiefe -= 1
        i += 1
    return skript[treffer.start():i]


def _konstanten(skript: str) -> str:
    return "\n".join(re.findall(r"var KAL_LS_[A-Z]+ = '[a-z_]+';", skript))


#: Ein Speicher mit der Flaeche von ``localStorage`` (getItem/setItem) -- so
#: laeuft der Test auf ``about:blank``, das kein eigenes localStorage hat.
_SPEICHER = """
function neuerSpeicher(start) {
  var daten = Object.assign({}, start || {});
  return {
    daten: daten,
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(daten, k) ? daten[k] : null; },
    setItem: function (k, v) { daten[k] = String(v); }
  };
}
"""


@pytest.fixture(scope="module")
def seite():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        blatt = browser.new_page()
        skript = web_chat._CHAT_JS
        harness = "\n".join(
            [_konstanten(skript), _SPEICHER]
            + [_extrahiere(skript, n) for n in _FUNKTIONEN]
        )
        blatt.add_script_tag(content=harness + "\nwindow.__bereit = true;")
        yield blatt
        browser.close()


def _js(seite, rumpf: str):
    return seite.evaluate("() => {" + rumpf + "}")


def test_gruppe_kommt_aus_dem_pfad(seite):
    assert _js(seite, "return kalGruppeAus('/theatersoap/g/AbC_12-x/chat');") == "AbC_12-x"
    assert _js(seite, "return kalGruppeAus('/g/AbC_12-x');") == "AbC_12-x"
    assert _js(seite, "return kalGruppeAus('/g/AbC_12-x/');") == "AbC_12-x"


def test_datum_ist_lokal_im_format_jjjj_mm_tt(seite):
    # 5. Oktober 2026, 00:30 Ortszeit -- Monat ist in JS nullbasiert.
    assert _js(seite, "return kalDatum(new Date(2026, 9, 5, 0, 30));") == "2026-10-05"
    assert _js(seite, "return kalDatum(new Date(2026, 0, 9, 23, 59));") == "2026-01-09"


def test_gleiche_gruppe_gleicher_tag_liest_die_messung(seite):
    ergebnis = _js(seite, """
      var s = neuerSpeicher();
      kalibrierungCacheSchreiben(s, 'gruppeA', '2026-10-05', 0.01, 0.2, 0.03);
      return kalibrierungCacheLesen(s, 'gruppeA', '2026-10-05');
    """)
    assert ergebnis == {"boden": 0.01, "rede": 0.2, "schwelle": 0.03}


def test_andere_gruppe_hat_einen_leeren_cache(seite):
    assert _js(seite, """
      var s = neuerSpeicher();
      kalibrierungCacheSchreiben(s, 'gruppeA', '2026-10-05', 0.01, 0.2, 0.03);
      return kalibrierungCacheLesen(s, 'gruppeB', '2026-10-05');
    """) is None


def test_anderer_tag_hat_einen_leeren_cache(seite):
    assert _js(seite, """
      var s = neuerSpeicher();
      kalibrierungCacheSchreiben(s, 'gruppeA', '2026-10-04', 0.01, 0.2, 0.03);
      return kalibrierungCacheLesen(s, 'gruppeA', '2026-10-05');
    """) is None


def test_alte_ungekeyte_schluessel_werden_ignoriert(seite):
    assert _js(seite, """
      var s = neuerSpeicher({vad_boden_mess: '0.01', vad_rede_mess: '0.2', vad_schwelle: '0.03'});
      return kalibrierungCacheLesen(s, 'gruppeA', '2026-10-05');
    """) is None


def test_die_schluessel_tragen_gruppe_und_datum(seite):
    schluessel = _js(seite, """
      var s = neuerSpeicher();
      kalibrierungCacheSchreiben(s, 'gruppeA', '2026-10-05', 0.01, 0.2, 0.03);
      return Object.keys(s.daten).sort();
    """)
    assert schluessel == [
        "vad_boden_mess:gruppeA:2026-10-05",
        "vad_rede_mess:gruppeA:2026-10-05",
        "vad_schwelle:gruppeA:2026-10-05",
    ]


def test_ohne_speicher_kein_fehler(seite):
    """Privater Modus/alter Browser: ``localStorage`` fehlt oder wirft --
    dann gibt es eben keinen Cache, der Raumcheck laeuft."""
    assert _js(seite, "return kalibrierungCacheLesen(null, 'gruppeA', '2026-10-05');") is None
    assert _js(seite, """
      kalibrierungCacheSchreiben(null, 'gruppeA', '2026-10-05', 0.01, 0.2, 0.03);
      return 'ok';
    """) == "ok"


def test_die_aufrufer_reichen_gruppe_und_heutiges_datum_durch():
    skript = web_chat._CHAT_JS
    assert "kalibrierungCacheLesen(kalSpeicher(), kalGruppeAus(location.pathname), kalDatum(new Date()))" in skript
    assert re.search(
        r"kalibrierungCacheSchreiben\(kalSpeicher\(\), kalGruppeAus\(location\.pathname\),\s*"
        r"kalDatum\(new Date\(\)\), k\.bodenMess, k\.redeMess, schwelle\)", skript)

"""Der Serververtrag des Chat-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_chat_e2e.py``: der
Recorder, die Segmente, PTT, die Warteschlange. Hier steht, was man am HTML
messen kann -- und das ist mehr, als es klingt: jede Zahl, die das JS braucht,
und jeder Endpunkt, den es ruft.
"""

import json
import re
import threading
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web, web_chat, web_vereint

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def seite(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", "1200")

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        html = antwort.read().decode("utf-8")
    dienst.shutdown()
    return html


def test_die_bedienelemente_stehen_da(seite):
    for kennung in ("verlauf", "eingabe", "senden", "ptt", "interview",
                    "uhr", "pegel", "warteschlange", "nonce", "tippt", "fuss"):
        assert f'id="{kennung}"' in seite, kennung


def test_die_segmentlaenge_kommt_aus_der_umgebung(seite):
    """Der Browsertest verkuerzt sie per Parameter -- 45 Sekunden je Segment
    wuerden einen Testlauf nutzlos lang machen."""
    assert 'data-segment-ms="1200"' in seite


def test_die_vad_werte_haben_vorgaben_ohne_umgebung(monkeypatch):
    for name in ("IT_WEB_VAD_PAUSE_MS", "IT_WEB_VAD_MAX_MS",
                 "IT_WEB_VAD_MIN_SPEECH_MS", "IT_WEB_VAD_RMS",
                 "IT_WEB_VAD_FLOOR_FACTOR"):
        monkeypatch.delenv(name, raising=False)
    assert web_chat._vad_werte() == {
        "pause_ms": 2500, "max_ms": 90_000, "min_speech_ms": 500,
        "rms": 0.01, "floor_faktor": 2.5,
    }


def test_die_vad_werte_kommen_einzeln_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_WEB_VAD_PAUSE_MS", "3000")
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", "60000")
    monkeypatch.setenv("IT_WEB_VAD_MIN_SPEECH_MS", "400")
    monkeypatch.setenv("IT_WEB_VAD_RMS", "0.02")
    monkeypatch.setenv("IT_WEB_VAD_FLOOR_FACTOR", "3.0")
    assert web_chat._vad_werte() == {
        "pause_ms": 3000, "max_ms": 60000, "min_speech_ms": 400,
        "rms": 0.02, "floor_faktor": 3.0,
    }


def test_eine_leere_oder_ungueltige_vad_umgebungszahl_faellt_auf_die_vorgabe_zurueck(monkeypatch):
    monkeypatch.setenv("IT_WEB_VAD_PAUSE_MS", "")
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", "nicht-numerisch")
    monkeypatch.setenv("IT_WEB_VAD_RMS", "-1")
    werte = web_chat._vad_werte()
    assert werte["pause_ms"] == 2500
    assert werte["max_ms"] == 90_000
    assert werte["rms"] == 0.01


def test_die_vad_attribute_stehen_am_fuss(seite):
    assert 'data-vad-pause-ms="2500"' in seite
    assert 'data-vad-max-ms="90000"' in seite
    assert 'data-vad-min-speech-ms="500"' in seite
    assert 'data-vad-rms="0.01"' in seite
    assert 'data-vad-floor-faktor="2.5"' in seite


def test_vad_ersetzt_den_festen_takt_mit_rueckfall():
    js = web_chat._CHAT_JS
    assert "sitzung.segmentTakt = setInterval" in js   # Rueckfall bleibt
    assert "if (!sitzung.vadAktiv)" in js              # ... aber nur ohne VAD
    assert "function schneideSegment" in js
    assert "getFloatTimeDomainData" in js


def test_vad_liest_alle_fuenf_werte_aus_dem_fuss():
    js = web_chat._CHAT_JS
    for attribut in ("vadPauseMs", "vadMaxMs", "vadMinSpeechMs", "vadRms",
                     "vadFloorFaktor"):
        assert f"fuss.dataset.{attribut}" in js, attribut


def test_kappe_schneidet_immer_pause_nur_mit_genug_rede():
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval"):]
    takt = takt[:takt.index("}, 120)")]
    assert "schneideSegment(sitzung, 'cap')" in takt
    assert "schneideSegment(sitzung, 'pause')" in takt
    assert "sitzung.vadSpeechMs >= MIN_SPEECH_MS" in takt


def test_manuelle_schnitte_tragen_den_grund_ende():
    js = web_chat._CHAT_JS
    # pausiereInterview + beendeInterview + pausiereBrainstorm + beendeBrainstorm
    assert js.count("_grund = 'ende'") == 4


def test_der_grund_ende_wird_nur_mit_aktivem_vad_gesetzt():
    """Ohne AnalyserNode (Rueckfall auf den festen Takt) bleibt vadSpeechMs
    bei 0 -- ohne diese Wache wuerde Pause/Beenden das letzte Stueck NIE mehr
    hochladen, weil 'ende' ohne VAD faelschlich redeMs=0 saehe statt null."""
    js = web_chat._CHAT_JS
    assert "letzter && sitzung.vadAktiv) { letzter._grund = 'ende'" in js
    assert "alt && sitzung.vadAktiv) { alt._grund = 'ende'" in js


def test_onstop_laesst_zu_kurze_kappen_schnitte_weg():
    js = web_chat._CHAT_JS
    onstop = js[js.index("r.onstop = function"):js.index("r.start();")]
    assert "genug" in onstop
    assert "redeMs > 0" in onstop


def test_postaudio_haengt_den_grund_an():
    js = web_chat._CHAT_JS
    ausschnitt = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "auftrag.grund" in ausschnitt


def test_schneidesegment_legt_sofort_einen_nachfolger_an():
    """Zwischen zwei Segmenten darf keine Luecke entstehen -- der neue
    Recorder steht schon, bevor der alte onstop gefeuert hat."""
    js = web_chat._CHAT_JS
    fn = js[js.index("function schneideSegment"):js.index("function pegelAn")]
    vor_stop = fn.index("alt.stop()")
    nach_stop = fn.index("sitzung.recorder = neuesSegment(sitzung)")
    assert vor_stop < nach_stop


def test_das_js_startet_weiterhin_einen_eigenen_recorder_je_segment():
    """VAD darf den Aufbau aus Re-Review B nicht aufbrechen: KEINE
    Zeitscheibe, jedes Segment bleibt eine eigenstaendige, komplette Datei."""
    js = web_chat._CHAT_JS
    assert re.search(r"\.start\(\s*\)", js)
    assert not re.search(r"\.start\([a-zA-Z0-9_.]+\)", js)


def test_der_nonce_steht_im_body_und_nicht_daran(seite):
    """Dieselbe Entscheidung wie auf der Gruppenseite (``web.nonce``):
    abgeleitet, nicht gewuerfelt, und IM body -- sonst reisst ein
    Fensterwechsel jedes offene Eingabefeld mit."""
    assert re.search(r'<input type="hidden" id="nonce" value="\d+\.[0-9a-f]{32}">', seite)


def test_das_js_ruft_nur_endpunkte_die_es_gibt(seite):
    """Jeder ``fetch``-Pfad im JS muss in ``_POSTWEGE`` oder unter den
    GET-Wegen stehen. Ein Tippfehler waere im Browser ein stilles 404."""
    pfade = set(re.findall(r"chat/([a-z]+)", web_chat._CHAT_JS))
    erlaubt = set(web_chat._POSTWEGE) | {"zustand", "datei", web_vereint.STROM_PFAD}
    assert pfade <= erlaubt, pfade - erlaubt


def test_das_js_nennt_jeden_postweg(seite):
    """Die andere Richtung: ein Endpunkt ohne Aufrufer im JS ist entweder
    toter Code oder ein vergessener Knopf.

    ``phase`` ist die eine Ausnahme (Karte W, 30.09.2026): die Roadmap mit
    ihren Phasenknoepfen gibt es nur auf der vereinten Seite, nicht im
    Chat-Alleingang (``/g/<token>/chat``) -- ihr Aufrufer steht deshalb in
    ``web_vereint._VEREINT_JS``, nicht in ``web_chat._CHAT_JS``."""
    for weg in web_chat._POSTWEGE:
        if weg == "phase":
            assert f"chat/{weg}" in web_vereint._VEREINT_JS, weg
            continue
        assert f"chat/{weg}" in web_chat._CHAT_JS, weg


def test_die_ptt_mindestdauer_kommt_aus_einer_konstante(seite):
    assert web_chat.PTT_MIN_MS == 500
    assert f"var PTT_MIN_MS = {web_chat.PTT_MIN_MS};" in seite
    # Kein zweiter Ort: im JS-Rohtext steht der Platzhalter, nicht die Zahl.
    assert "__PTT_MIN_MS__" in web_chat._CHAT_JS


def test_pointercancel_und_setpointercapture_stehen_im_js():
    """Birks Vorgabe woertlich: Pointer Events + setPointerCapture, Abbruch
    bei Wegziehen/pointercancel sendet NICHTS."""
    for baustein in ("setPointerCapture", "pointercancel", "pointerdown",
                     "pointerup", "releasePointerCapture"):
        assert baustein in web_chat._CHAT_JS, baustein


def test_kein_schieben_zum_sperren(seite):
    """Birk, verbindlich: ZWEI getrennte Knoepfe, KEIN Schieben-zum-Sperren.
    Ein Test, der eine Entscheidung festhaelt, die sonst niemand mehr kennt."""
    # Auf Wortgrenzen: ein Teilstring "lock" traefe auch "block" und "clock"
    # (Review-Befund 13).
    for muster in (r"\bslide\w*", r"\bswipe\w*", r"\block\w*", r"\w*Lock\b",
                   r"\bsperren\b"):
        assert not re.search(muster, web_chat._CHAT_JS, re.IGNORECASE), muster


def test_der_schieben_test_trifft_keine_harmlosen_woerter():
    """Gegenprobe zum Test darueber: "block", "clock" und "Blockade" sind
    keine Sperr-Geste."""
    harmlos = "display: block; var clock = 1; // Blockade"
    for muster in (r"\bslide\w*", r"\bswipe\w*", r"\block\w*", r"\bsperren\b"):
        assert not re.search(muster, harmlos, re.IGNORECASE), muster
    assert re.search(r"\block\w*", "slideToLock lockScreen", re.IGNORECASE)


def test_das_js_startet_einen_eigenen_recorder_je_segment():
    """MediaRecorder-Zeitscheiben sind einzeln nicht dekodierbar: nur das
    erste Stueck traegt den Container-Kopf. Also stop() + start() je Segment,
    NICHT start(timeslice)."""
    assert "new MediaRecorder" in web_chat._CHAT_JS
    assert re.search(r"\.start\(\s*\)", web_chat._CHAT_JS)
    assert not re.search(r"\.start\(\s*[A-Za-z0-9_]+\s*\)", web_chat._CHAT_JS)


def test_das_js_wartet_auf_den_interviewmodus_vor_dem_ersten_upload():
    """Der Wettlauf: die Aufnahme startet sofort, der Upload wartet bis
    ``interviewmodus: true``. Sonst kaeme das erste Segment vor dem
    ``/interview`` an, und ``aufnahme.klasse_fuer`` machte daraus eine
    kurz-Aufnahme statt eines Interview-Teils."""
    assert "interviewmodus" in web_chat._CHAT_JS


def test_das_js_laedt_ohne_nachladen_der_ganzen_seite(seite):
    """``web._seite(..., nachladen=False)``: das sanfte Nachladen tauscht den
    ``<body>`` aus, und mitten in einer Aufnahme riss das Recorder, Timer und
    Warteschlange mit."""
    assert "__NEULADEN_MS__" not in seite
    assert "location.reload" not in seite


def test_die_polltakte_stehen_als_konstanten():
    assert web_chat.POLL_MS == 2000
    assert web_chat.POLL_MS_HINTERGRUND == 10000
    fertig = web_chat._js()
    assert f"var POLL_MS = {web_chat.POLL_MS};" in fertig
    assert f"var POLL_MS_HINTERGRUND = {web_chat.POLL_MS_HINTERGRUND};" in fertig


def test_ui_texte_stehen_nicht_als_literal_im_js():
    """Review-Befund 9: jeder Satz, den das JS setzt, kommt aus einer
    ``_TEXT_*``-Konstante -- als JSON-Objekt ueber den Platzhalter."""
    for name, wert in web_chat._JS_TEXTE.items():
        assert wert not in web_chat._CHAT_JS, name
    for wort in ("Interview aufnehmen", "Aufnahme beenden", "schreibt …",
                 "Sprachnachricht", "hochgeladen", "Keine Verbindung"):
        assert wort not in web_chat._CHAT_JS, wort
    fertig = web_chat._js()
    assert "__TEXTE__" not in fertig
    texte = re.search(r"var TEXT = (\{.*?\});\n", fertig).group(1)
    import json
    assert json.loads(texte) == web_chat._JS_TEXTE


def test_im_fertigen_js_bleibt_kein_platzhalter_stehen():
    assert not re.search(r"__[A-Z_]+__", web_chat._js())


def test_uploads_haben_keine_hoechstzahl_an_versuchen():
    """Review-Befund 3: ein Segment wird bei Netzfehler oder 5xx nie
    verworfen. Es gibt keine Versuchsgrenze mehr, nur einen gedeckelten
    Abstand -- und das ``online``-Ereignis loest sofort einen Versuch aus."""
    assert not hasattr(web_chat, "UPLOAD_VERSUCHE")
    assert "UPLOAD_VERSUCHE" not in web_chat._CHAT_JS
    assert "'online'" in web_chat._CHAT_JS
    assert f"var UPLOAD_WARTEN_MS = [{', '.join(map(str, web_chat.UPLOAD_WARTEN_MS))}];" \
        in web_chat._js()


def test_fertig_wartet_auf_das_stop_ereignis():
    """Review-Befund 1: das letzte Segment kommt im ``onstop`` -- ``/fertig``
    wird erst dort (``pruefeEnde``) eingereiht, nie direkt nach ``stop()``."""
    js = web_chat._CHAT_JS
    assert "r.onstop" in js
    assert "pruefeEnde(sitzung)" in js
    beende = js[js.index("function beendeInterview"):js.index("interviewKnopf.addEventListener")]
    assert "an: false" in beende   # nur der Weg ohne eigene Aufnahme
    assert "fetch(" not in beende


def test_der_poll_setzt_den_nonce_und_wiederholt_bei_403():
    js = web_chat._CHAT_JS
    assert "daten.nonce" in js
    assert "r.status === 403" in js


# -- Scrollen bei einer wachsenden Blase (Padua Brainstorm, 03.10.2026) -----
#
# Befund: eine Blase, die nur per ``geaendert`` waechst (das laufende
# Transkript eines Brainstorm-Segments -- bis zum Stop-Klick legt der Server
# nie eine NEUE Nachricht an), loeste bisher kein ``nachUnten()`` aus:
# ``nimmZustand`` rief es nur bei ``neu.length``. Die Blase wuchs unterhalb
# des sichtbaren Bereichs, ohne dass der Bildschirm mitscrollte.


def test_amunterenrand_wird_vor_jeder_dom_aenderung_gelesen():
    """Der Lesezeitpunkt ist das Kritische: nach dem Einfuegen einer neuen
    Blase waere ``document.body.scrollHeight`` schon die NEUE Hoehe, und
    ``amUnterenRand()`` saehe immer "unten", auch wenn die Gruppe gerade
    weiter oben nachliest."""
    js = web_chat._CHAT_JS
    nimm = js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]
    # Erste Zeile im Funktionskoerper -- vor dem Nonce, vor ``neu.forEach``,
    # vor ``geaendert.forEach``.
    erste_zeile = nimm.split("\n")[1].strip()
    assert erste_zeile == "var warUnten = amUnterenRand();"
    assert nimm.index("var warUnten = amUnterenRand();") < nimm.index("neu.forEach(blase)")
    assert nimm.index("var warUnten = amUnterenRand();") < nimm.index("geaendert.forEach(ersetze)")


def test_nachunten_laeuft_bei_neu_oder_bei_geaenderter_letzter_blase():
    js = web_chat._CHAT_JS
    nimm = js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]
    assert "if (neu.length) {\n      nachUnten();\n    } else if " in nimm
    nach_else_if = nimm[nimm.index("} else if ") + len("} else if "):]
    bedingung = nach_else_if[:nach_else_if.index(") {")]
    assert "warUnten" in bedingung
    assert "geaendert.length" in bedingung
    assert "letzteBlaseWurdeGeaendert(geaendert)" in bedingung


def _node_oder_skip():
    import shutil

    node = shutil.which("node")
    if node is None:
        pytest.skip("node nicht installiert")
    return node


def _fuehre_js_aus(node: str, quelltext: str, tmp_path) -> str:
    """Schreibt ``quelltext`` als Datei und laesst ``node`` sie ausfuehren --
    wie ``test_das_js_ist_syntaktisch_gueltig``, nur mit Ausgabe statt nur dem
    Exit-Code."""
    import subprocess

    datei = tmp_path / "harness.js"
    datei.write_text(quelltext, encoding="utf-8")
    ergebnis = subprocess.run(
        [node, str(datei)], capture_output=True, text=True, timeout=30,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    return ergebnis.stdout


def _extrahiere(js: str, start_marke: str, end_marke: str) -> str:
    return js[js.index(start_marke):js.index(end_marke)]


def test_amunterenrand_entscheidet_live_in_node(tmp_path):
    """Fuehrt ``amUnterenRand()`` WOERTLICH aus dem ausgelieferten Skript aus
    (nicht nachgebaut) gegen vier Positionen: am Rand, knapp innerhalb der
    Toleranz, knapp ausserhalb, und weit hochgescrollt."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(js, "function amUnterenRand", "function letzteBlaseWurdeGeaendert")

    quelltext = f"""
    var UNTEN_TOLERANZ_PX = 48;
    var window, document;
    {funktion}

    function pruefe(innerHeight, scrollY, scrollHeight) {{
      window = {{ innerHeight: innerHeight, scrollY: scrollY }};
      document = {{ body: {{ scrollHeight: scrollHeight }} }};
      return amUnterenRand();
    }}

    var ergebnisse = {{
      genau_am_rand: pruefe(800, 1200, 2000),       // 800+1200 == 2000
      innerhalb_der_toleranz: pruefe(800, 1160, 2000),  // 40px Rest, < 48
      knapp_ausserhalb: pruefe(800, 1100, 2000),    // 100px Rest, > 48
      weit_hochgescrollt: pruefe(800, 100, 2000)
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse == {
        "genau_am_rand": True,
        "innerhalb_der_toleranz": True,
        "knapp_ausserhalb": False,
        "weit_hochgescrollt": False,
    }


def test_letzteblasewurdegeaendert_entscheidet_live_in_node(tmp_path):
    """Dieselbe Herangehensweise fuer die zweite Weiche: nur ein Treffer auf
    die zurzeit LETZTE Blase im Verlauf zaehlt -- eine Aenderung an einer
    aelteren Blase (z. B. eine entfernte Knopfleiste) scrollt nicht mit."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(js, "function letzteBlaseWurdeGeaendert", "function nimmZustand")

    quelltext = f"""
    var verlauf;
    {funktion}

    function blasen(ids) {{
      return {{
        querySelectorAll: function (sel) {{
          return ids.map(function (id) {{ return {{ dataset: {{ id: String(id) }} }}; }});
        }}
      }};
    }}

    verlauf = blasen(["10", "11", "12"]);
    var ergebnisse = {{
      letzte_blase_betroffen: letzteBlaseWurdeGeaendert([{{ id: 12 }}]),
      aeltere_blase_betroffen: letzteBlaseWurdeGeaendert([{{ id: 11 }}]),
      mehrere_eine_davon_die_letzte: letzteBlaseWurdeGeaendert([{{ id: 5 }}, {{ id: 12 }}]),
      keine_blase_vorhanden: (function () {{
        verlauf = blasen([]);
        return letzteBlaseWurdeGeaendert([{{ id: 12 }}]);
      }})()
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse == {
        "letzte_blase_betroffen": True,
        "aeltere_blase_betroffen": False,
        "mehrere_eine_davon_die_letzte": True,
        "keine_blase_vorhanden": False,
    }


def test_beforeunload_warnt_waehrend_aufnahme_und_upload():
    assert "beforeunload" in web_chat._CHAT_JS


def test_ptt_hat_die_beruehrungsregeln_im_css(seite):
    for regel in ("touch-action: none", "user-select: none",
                  "-webkit-user-select: none", "-webkit-touch-callout: none",
                  '#ptt[data-haelt="1"]'):
        assert regel in seite, regel


def test_die_wege_sind_absolut_zum_gruppenverzeichnis():
    """Review-Befund 12: kein relativer ``fetch('chat/...')`` mehr."""
    assert not re.search(r"fetch\(\s*'chat/", web_chat._CHAT_JS)
    assert "location.pathname" in web_chat._CHAT_JS


def test_die_seite_traegt_den_modus_schon_beim_laden(tmp_path, monkeypatch):
    """Review-Befund 11: im Interviewmodus steht der Stopp-Knopf schon im
    HTML da, und PTT ist ausgeblendet -- nicht erst nach dem ersten Poll.

    Erweitert (Drei-Zustands-Regler, 02.10.2026): ``data-pausiert`` steht
    ebenfalls schon beim ersten Rendern da -- ein frisch geladenes Dokument
    hat nie eine lokale Sitzung, also ist ein ``modus=true`` beim Laden
    immer die Pause-Darstellung (Punkt 5 des Reglers)."""
    daten = {"nachrichten": [], "letzte": 0, "aenderung": 0,
             "interviewmodus": True, "titel": None}
    seite = web_chat.chat_html(daten, "1.x", "tok", "", 45000)
    assert (f'data-laeuft="1" data-pausiert="1">{web_chat._TEXT_INTERVIEW_AUS}'
            f'</button>') in seite
    assert '<button type="button" id="ptt" hidden' in seite
    assert 'id="interview-aktionen"' in seite and 'id="interview-aktionen" hidden' not in seite
    assert f'id="interview-pause">{web_chat._TEXT_INTERVIEW_WEITER}</button>' in seite
    assert f'id="interview-beenden">{web_chat._TEXT_INTERVIEW_ENDEN}</button>' in seite
    aus = web_chat.chat_html(dict(daten, interviewmodus=False), "1.x", "tok", "", 45000)
    assert '<button type="button" id="ptt" title=' in aus
    assert 'data-laeuft="0" data-pausiert="0">' in aus
    assert 'id="interview-aktionen" hidden' in aus
    assert f'id="interview-pause">{web_chat._TEXT_INTERVIEW_PAUSE}</button>' in aus


def test_das_js_ist_syntaktisch_gueltig(tmp_path):
    """Wenn ``node`` da ist: ``node --check`` ueber das fertige Skript."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node nicht installiert")
    datei = tmp_path / "chat.js"
    datei.write_text(web_chat._js(), encoding="utf-8")
    ergebnis = subprocess.run([node, "--check", str(datei)],
                              capture_output=True, text=True, timeout=30)
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_kein_segment_geht_ohne_modus_raus():
    """Re-Review H: ohne Modus waere ein Segment (45 s, unter
    ``aufnahme.HINWEIS_AB_S``) fuer den Bot ein Gespraechsbeitrag
    (``aufnahme.klasse_fuer`` -> 'kurz'). Also prueft ``bereit`` den Modus
    bei JEDEM Segment -- und ein ueberholtes /fertig wird nicht gesendet."""
    js = web_chat._CHAT_JS
    bereit = js[js.index("function bereit"):js.index("function ueberholt")]
    assert "sitzung.bestaetigt = true" in bereit
    assert "return zustand.servermodus;" in bereit
    assert "sitzung.angehalten" in bereit
    ab = js[js.index("function arbeiteAb"):js.index("function erledigt")]
    assert "ueberholt(auftrag)" in ab
    assert "zustand.wechsel = null" in ab


def test_modusende_haelt_die_aufnahme_an_statt_still_weiterzuschicken():
    """Re-Review H: endet der Modus bei einer bestaetigten Aufnahme, stoppt
    das Telefon selbst, parkt den Rest und fragt -- nachreichen oder
    verwerfen. Kein /fertig fuer eine angehaltene Aufnahme."""
    js = web_chat._CHAT_JS
    nimm = js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]
    assert "pruefeModusende()" in nimm
    halte = js[js.index("function halteAn"):js.index("function geparkteZahl")]
    assert "letzter.stop()" in halte
    assert "sitzung.geparkt.push(a)" in halte
    assert "zustand.wechsel = null" in halte
    ende = js[js.index("function pruefeEnde"):js.index("function pruefeModusende")]
    assert ende.index("sitzung.angehalten") < ende.index("reiheEin(")
    nach = js[js.index("function reicheNach"):js.index("function verwirfRest")]
    # derselbe Weg wie der Umschalter: /interview, Segmente, /fertig
    assert nach.index("an: true") < nach.index("rest.forEach") < nach.index("an: false")
    assert "geparkteZahl()" in js[js.index("beforeunload"):]


def test_der_hinweis_mit_zwei_knoepfen_steht_in_der_seite(seite):
    for kennung in ("angehalten", "angehalten-text", "nachreichen", "verwerfen"):
        assert f'id="{kennung}"' in seite, kennung
    assert web_chat._TEXT_REST_NACHREICHEN in seite
    assert web_chat._TEXT_REST_VERWERFEN in seite
    assert web_chat._JS_TEXTE["modus_weg"] == web_chat._TEXT_MODUS_WEG


def test_ein_gescheiterter_upload_einer_angehaltenen_aufnahme_wird_geparkt():
    """Re-Review zu a615327: war ein Segment beim Modusende schon unterwegs,
    laesst ``halteAn`` es stehen. Scheitert der Upload, steht es vorn mit
    ``laeuft = false`` -- ``bereit`` sagt fuer immer nein, und ``halteAn``
    bricht am ``angehalten`` ab. ``arbeiteAb`` parkt es deshalb VOR
    ``bereit``, vorn in ``geparkt`` (es ist aelter als alles dort), und
    zeigt den Hinweis wieder."""
    js = web_chat._CHAT_JS
    ab = js[js.index("function arbeiteAb"):js.index("function erledigt")]
    assert "parkeKopf(auftrag)" in ab
    assert ab.index("parkeKopf(auftrag)") < ab.index("bereit(auftrag)")
    parke = js[js.index("function parkeKopf"):js.index("function arbeiteAb")]
    assert "zustand.warteschlange.shift()" in parke
    assert "sitzung.geparkt.unshift(auftrag)" in parke
    assert "zustand.angehalten.push(sitzung)" in parke
    assert "zeigeAngehalten()" in parke
    assert "restVerworfen" in parke   # verworfen bleibt verworfen
    # Solange es unterwegs ist, gilt die Aufnahme als noch offen: kein
    # Nachreichen, das sich vor das unterwegs befindliche Segment draengt.
    assert "unterwegs(s)" in js[js.index("function zeigeAngehalten"):
                                js.index("function reicheNach")]
    nach = js[js.index("function reicheNach"):js.index("function verwirfRest")]
    assert "unterwegs(s)" in nach
    assert "zeigeAngehalten()" in js[js.index("function erledigt"):
                                     js.index("function entferneAuftraege")]


def test_nachreichen_nur_ohne_laufenden_servermodus():
    """Re-Review: hat ein anderes Telefon den Modus wieder angeschaltet,
    schloesse das abschliessende /fertig dessen Interview."""
    js = web_chat._CHAT_JS
    nach = js[js.index("function reicheNach"):js.index("function verwirfRest")]
    assert "zustand.servermodus" in nach
    assert nach.index("zustand.servermodus") < nach.index("an: true")
    zeige = js[js.index("function zeigeAngehalten"):js.index("function reicheNach")]
    assert "zustand.servermodus" in zeige
    assert "TEXT.nachreichen_spaeter" in zeige
    assert web_chat._JS_TEXTE["nachreichen_spaeter"] == web_chat._TEXT_NACHREICHEN_SPAETER
    nimm = js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]
    assert "zeigeAngehalten()" in nimm


def test_die_sperrklinke_rastet_im_poll_ein():
    """Re-Review I: auch ohne Segment vorn in der Schlange."""
    js = web_chat._CHAT_JS
    nimm = js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]
    assert "zustand.aufnahme.bestaetigt = true" in nimm
    assert nimm.index("bestaetigt = true") < nimm.index("pruefeModusende()")


def test_segmente_werden_nach_ihrer_nummer_eingereiht():
    """Re-Review B: zwei onstop koennen sich ueberholen."""
    js = web_chat._CHAT_JS
    assert "sitzung.naechsteNr" in js
    assert "sitzung.einzureihen" in js


def test_403_in_der_schlange_wird_nachgeholt_nicht_verworfen():
    """Re-Review C."""
    ab = web_chat._CHAT_JS[web_chat._CHAT_JS.index("function arbeiteAb"):]
    assert "r.status === 403" in ab.split("throw new Error('nochmal')")[0]


def test_interviewstart_verwirft_einen_gehaltenen_ptt_druck():
    """Re-Review F: zwei Finger, zwei Recorder."""
    js = web_chat._CHAT_JS
    start = js[js.index("function starteInterview"):js.index("function brichAb")]
    assert "verwirfPtt()" in start


def test_der_aenderungsstand_wird_vor_dem_verlauf_gelesen():
    """Re-Review G: sonst faellt eine Aenderung zwischen beiden Abfragen
    durch -- sie stuende weder im Verlauf noch ueber dem Stand."""
    import inspect

    from interview_theater import web_daten

    quelle = inspect.getsource(web_daten.web_chatzustand)
    assert quelle.index("web_chataenderungen(") < quelle.index("web_chatverlauf(")


# -- Drei-Zustands-Regler: Laeuft/Pause/Beenden (02.10.2026, Padua) --------

def test_die_drei_knoepfe_stehen_im_markup(seite):
    for kennung in ("interview-aktionen", "interview-pause", "interview-beenden"):
        assert f'id="{kennung}"' in seite, kennung


def test_der_grosse_knopf_ist_waehrend_laeuft_pause_nur_eine_anzeige():
    """Punkt 2/3: ein Druck auf #interview waehrend Laeuft oder Pause tut
    NICHTS mehr -- Beenden laeuft nur noch ueber #interview-beenden."""
    js = web_chat._CHAT_JS
    start = js.index("interviewKnopf.addEventListener")
    ende = js.index("});", start) + 3
    klick = js[start:ende]
    assert "modusAn()" in klick
    assert "beendeInterview" not in klick
    assert "starteInterview()" in klick


def test_pausieren_sendet_kein_fertig_und_keinen_befehl():
    """Punkt 4: Pause stoppt nur den lokalen Recorder -- der Interviewmodus
    bleibt serverseitig an, es geht kein ``/fertig`` (und ueberhaupt kein
    Befehl) heraus."""
    js = web_chat._CHAT_JS
    pause = js[js.index("function pausiereInterview"):
                js.index("function fortsetzeInterview")]
    assert "an: false" not in pause
    assert "reiheEin(" not in pause
    assert "art: 'befehl'" not in pause
    assert "alt.stop()" in pause          # das letzte Stueck geht trotzdem raus
    assert "gibFrei(sitzung)" in pause    # Mikrofon los waehrend der Pause


def test_fortsetzen_haengt_an_dieselbe_sitzung_ohne_neues_interview():
    """Punkt 4/5: Weiter haengt an dieselbe (oder, nach einem Neuladen, eine
    frisch angelegte, aber schon ``angemeldet``e) Sitzung an -- nie ein
    zweites ``{art:'befehl', an:true}``.

    Seit dem Race-Fix (Re-Review, Befund 1/2) teilen sich starteInterview()
    und fortsetzeInterview() das tatsaechliche Aufnahme-Beginnen in der
    Funktion ``beginneAufnahme`` -- hier wird deshalb BEIDES geprueft: dass
    fortsetzeInterview() dorthin delegiert (statt es zu duplizieren), und
    dass der gemeinsame Helfer die bisherigen Invarianten weiterhin traegt.
    """
    js = web_chat._CHAT_JS
    fortsetzen = js[js.index("function fortsetzeInterview"):
                     js.index("if (nachreichenKnopf)")]
    assert "angemeldet: true" in fortsetzen
    assert "bestaetigt: true" in fortsetzen
    assert "art: 'befehl'" not in fortsetzen   # kein /interview, nirgends
    assert "beginneAufnahme(sitzung)" in fortsetzen
    assert "neuesSegment(sitzung)" not in fortsetzen   # keine Dopplung mehr

    beginn = js[js.index("function beginneAufnahme"):
                js.index("function starteInterview")]
    assert "neuesSegment(sitzung)" in beginn
    assert "sitzung.legStart = Date.now()" in beginn


def test_ptt_bleibt_waehrend_pause_versteckt():
    """Punkt 6: ``zeigeModus`` blendet PTT bei JEDEM 'Modus an' aus, Pause
    eingeschlossen -- keine zweite Bedingung dafuer."""
    js = web_chat._CHAT_JS
    zeige = js[js.index("function zeigeModus"):js.index("function verwirfPtt")]
    assert "pttKnopf.hidden = an" in zeige
    assert "var pausiert = an &&" in zeige


def test_beenden_hat_keinen_bestaetigungsdialog():
    """Punkt 7: kein ``confirm()``/Modal vor dem Beenden."""
    assert "confirm(" not in web_chat._CHAT_JS


def test_interview_beenden_knopf_ruft_dieselbe_funktion_wie_bisher():
    """Beenden dupliziert die Stop-Logik nicht neu -- Druck auf
    #interview-beenden ruft exakt ``beendeInterview`` (dieselbe Funktion wie
    beim alten Umschalter), die ``pruefeEnde``/``onstop`` unveraendert
    weiterverwendet."""
    js = web_chat._CHAT_JS
    assert "interviewBeendenKnopf.addEventListener('click', beendeInterview);" in js


def test_pause_weiter_knopf_wechselt_auf_die_richtige_funktion():
    js = web_chat._CHAT_JS
    wiring = js[js.index("if (interviewPauseKnopf)"):
                js.index("if (interviewBeendenKnopf)")]
    assert "pausiereInterview(sitzung)" in wiring
    assert "fortsetzeInterview(sitzung)" in wiring
    assert "fortsetzeInterview(null)" in wiring
    assert "zustand.servermodus" in wiring


def test_formatiereuhr_zaehlt_erfasstems_plus_laufende_spanne():
    js = web_chat._CHAT_JS
    formel = js[js.index("function formatiereUhr"):js.index("function uhrAn")]
    assert "sitzung.erfassteMs" in formel
    assert "sitzung.legStart" in formel
    assert "sitzung.pausiert" in formel


def test_keine_zweite_parallele_merkvariable_fuer_pause():
    """Design-Vorgabe: 'pausiert' haengt an der Sitzung, nicht an einem
    zweiten Feld von ``zustand`` -- ``zustand.pausiert`` darf es nicht
    geben."""
    assert "zustand.pausiert" not in web_chat._CHAT_JS


def test_pause_vor_dem_mikrofon_verschluckt_den_tipp_nicht():
    """Fix-Review, Befund 1: Pause, waehrend starteInterview() noch auf
    holeStrom() wartet (eine vom Menschen beantwortete Berechtigungsfrage --
    das Fenster kann Sekunden dauern), durfte bisher gegen
    ``sitzung.legStart === null`` falten (eine Muellzahl in die Uhr) UND den
    Tipp verschlucken, weil nichts sonst ihn vermerkte. Jetzt gibt es dafuer
    eine eigene, fruehe Verzweigung -- VOR dem Falten gegen Date.now()."""
    js = web_chat._CHAT_JS
    pause = js[js.index("function pausiereInterview"):
                js.index("function fortsetzeInterview")]
    vor_falten = pause[:pause.index("sitzung.erfassteMs +=")]
    assert "sitzung.mikroUnterwegs" in vor_falten
    assert "sitzung.pausiert = true" in vor_falten
    assert "zeigeModus()" in vor_falten
    assert "return" in vor_falten


def test_starteinterview_faengt_nicht_an_wenn_zwischenzeitlich_pausiert():
    """Fix-Review, Befund 1 (Kehrseite): wird waehrend der Mikrofon-Wartezeit
    pausiert, darf starteInterview()'s eigener .then() nicht trotzdem
    aufnehmen -- sonst laeuft ein Recorder, waehrend die Anzeige 'Pause'
    zeigt, und ein folgendes 'Weiter' haette einen zweiten gestartet
    (Fix-Review, Befund 1, letzter Absatz).

    Zweites Re-Review, Befund: dieser Schutz stand bis dahin als eigene
    Verzweigung HIER, in starteInterview()'s eigenem .then() -- eine Kopie,
    die fortsetzeInterview() nicht mitbekam. Jetzt ruft starteInterview()
    nach der reiheEin()-Anmeldung unbedingt beginneAufnahme() auf und
    ueberlaesst DIESER die Pruefung (siehe
    test_pausiert_schutz_lebt_nur_noch_in_beginneaufnahme); hier wird nur
    noch die Reihenfolge und die Abwesenheit der alten Kopie gehalten."""
    js = web_chat._CHAT_JS
    start = js[js.index("function starteInterview"):js.index("function brichAb")]
    then = start[start.index("holeStrom().then"):start.index(").catch(")]
    assert "if (sitzung.pausiert)" not in then   # keine eigene Kopie mehr
    assert then.index("reiheEin(") < then.index("beginneAufnahme(sitzung)")


def test_fortsetzen_haengt_sich_nicht_vor_das_laufende_holestrom():
    """Fix-Review, Befund 1 (Kehrseite): wird 'Weiter' getippt, waehrend
    starteInterview()'s EIGENE Mikrofonanfrage noch unterwegs ist (z.B. nach
    einem schnellen Pause-dann-Weiter), darf fortsetzeInterview() keinen
    ZWEITEN holeStrom()-Aufruf absetzen -- das waeren zwei Recorder auf
    derselben Sitzung. Es nimmt die Pause nur zurueck und ueberlaesst die
    Aufnahme dem schon laufenden Aufruf."""
    js = web_chat._CHAT_JS
    fortsetzen = js[js.index("function fortsetzeInterview"):
                     js.index("if (nachreichenKnopf)")]
    wenn_echt = fortsetzen[fortsetzen.index("if (sitzung) {"):
                           fortsetzen.index("} else {")]
    assert "sitzung.mikroUnterwegs" in wenn_echt
    assert "sitzung.pausiert = false" in wenn_echt
    assert "return" in wenn_echt
    # Der eigentliche holeStrom().then(...)-Aufruf kommt NACH diesem
    # fruehen Ausstieg, und es gibt nur diesen einen in der ganzen Funktion
    # -- nie einen zweiten, waehrend der erste noch laeuft.
    assert fortsetzen.index("sitzung.mikroUnterwegs") < \
        fortsetzen.index("holeStrom().then")
    assert fortsetzen.count("holeStrom().then") == 1


def test_beginneaufnahme_ist_der_einzige_ort_der_die_aufnahme_beginnt():
    """Fix-Review, Befund 2: die Dopplung, in der ein Schutz (Befund 1) nur
    in einer der beiden Kopien stand, darf nicht wiederkommen -- es gibt
    GENAU einen Ort, der legStart/Recorder/Segment-Takt/Uhr/Pegel setzt,
    und beide Aufrufer delegieren dorthin."""
    js = web_chat._CHAT_JS
    assert js.count("function beginneAufnahme") == 1
    # starteInterview + fortsetzeInterview + starteBrainstorm + fortsetzeBrainstorm
    assert js.count("beginneAufnahme(sitzung);") == 4
    # Der Segment-Takt wird nur noch EINMAL im ganzen Skript aufgebaut --
    # vorher stand dieselbe setInterval(...)-Konstruktion in beiden
    # Funktionen, und ein Schutz in der einen (Befund 1) galt nicht
    # automatisch fuer die andere.
    assert js.count("sitzung.segmentTakt = setInterval(") == 1


def test_pausiert_schutz_lebt_nur_noch_in_beginneaufnahme():
    """Zweites Re-Review (nach dem Fix fuer Befund 2 oben): der durch
    Befund 1 eingefuehrte Schutz -- eine waehrend des Mikrofon-Wartens
    zwischenzeitlich gesetzte Pause darf danach nicht doch noch aufnehmen --
    stand trotz ``beginneAufnahme`` als gemeinsamer Stelle nur in
    starteInterview()'s eigenem ``.then()``, VOR dem Aufruf von
    ``beginneAufnahme()`` statt darin. fortsetzeInterview()'s eigener
    ``.then()``-Rueckgang hatte ueberhaupt keine Kopie davon -- heute
    unschaedlich, weil ``sitzung.pausiert`` beim Eintritt in diesen Zweig
    schon lange true ist und nichts es waehrenddessen aendern kann, aber
    eine stillliegende Luecke, die ein kuenftiger UI-Pfad wieder oeffnen
    koennte, ohne dass irgendetwas sie faengt.

    Jetzt gibt es GENAU eine Stelle, die prueft: ``beginneAufnahme()``
    selbst. Beide Aufrufer liefern ihr dasselbe Signal, indem sie
    ``sitzung.pausiert`` auf false setzen, BEVOR ihr jeweils eigenes
    ``holeStrom()`` beginnt -- starteInterview() im frischen
    Sitzungs-Objekt, fortsetzeInterview() mit einer eigenen Zeile kurz vor
    seinem eigenen ``holeStrom().then(`` --, statt es nur in der einen
    Kopie zu tun."""
    js = web_chat._CHAT_JS

    beginn = js[js.index("function beginneAufnahme"):
                js.index("function starteInterview")]
    assert beginn.index("if (sitzung.pausiert)") < beginn.index("gibFrei(sitzung)")
    assert beginn.index("gibFrei(sitzung)") < beginn.index("neuesSegment(sitzung)")

    start = js[js.index("function starteInterview"):js.index("function brichAb")]
    start_then = start[start.index("holeStrom().then"):start.index(").catch(")]
    assert "if (sitzung.pausiert)" not in start_then   # keine Kopie hier
    assert "pausiert: false" in start   # Startzustand im frischen Sitzungs-Objekt

    fortsetzen = js[js.index("function fortsetzeInterview"):
                     js.index("if (nachreichenKnopf)")]
    # Der EIGENE holeStrom().then()-Rueckgang dieser Funktion -- nicht die
    # fruehe "Kehrseite"-Verzweigung weiter oben im ``if (sitzung) {...}``,
    # die das Mikrofon eines FREMDEN (starteInterview-)Aufrufs betrifft und
    # von test_fortsetzen_haengt_sich_nicht_vor_das_laufende_holestrom
    # geprueft wird.
    eigener_then = fortsetzen[fortsetzen.index("holeStrom().then"):
                              fortsetzen.index(").catch(")]
    assert "if (sitzung.pausiert)" not in eigener_then   # keine Kopie hier

    # Symmetrisch zu starteInterview(): pausiert wird explizit auf false
    # gesetzt, bevor DIESES holeStrom() lostritt -- nicht erst von
    # beginneAufnahme() selbst (sonst koennte der Aufrufer nie "schon
    # wieder pausiert" melden).
    vor_dem_eigenen_holestrom = fortsetzen[
        fortsetzen.index("Re-Review F, auch beim Wiederaufnehmen"):
        fortsetzen.index("holeStrom().then")]
    assert "sitzung.pausiert = false;" in vor_dem_eigenen_holestrom
    assert vor_dem_eigenen_holestrom.index("sitzung.pausiert = false;") < \
        vor_dem_eigenen_holestrom.index("sitzung.fortsetzend = true;")


def test_das_js_setzt_kein_cookie_und_nichts_in_den_speicher():
    """E6: der Zustand steht im DOM und in der URL, nirgends sonst -- damit
    ein Link teilbar bleibt und ein zweites Telefon dieselbe Gruppe sieht."""
    for verboten in ("document.cookie", "localStorage", "sessionStorage",
                     "WebSocket", "EventSource"):
        assert verboten not in web_chat._CHAT_JS, verboten


# -- Brainstorm mithoeren (Phase 4, nur Web, 02.10.2026) ---------------------


def test_der_brainstorm_knopf_steht_nur_in_phase_4_im_markup():
    """Ausserhalb Phase 4 rendert ``chat_html`` die vier Brainstorm-Elemente
    gar nicht -- das JS liest ``document.getElementById('brainstorm')`` als
    ``null`` und jede Brainstorm-Funktion bleibt ein No-Op (siehe
    ``zeigeBrainstormModus``)."""
    daten = {"nachrichten": [], "letzte": 0, "aenderung": 0,
             "interviewmodus": False, "titel": None, "phase": 4}
    seite = web_chat.chat_html(daten, "1.x", "tok", "", 45000)
    for kennung in ("brainstorm", "brainstorm-aktionen", "brainstorm-pause",
                    "brainstorm-beenden"):
        assert f'id="{kennung}"' in seite, kennung
    assert web_chat._TEXT_BRAINSTORM_AN in seite
    # Das Interview bleibt erreichbar, aber als Nebenknopf (brief: "stays
    # reachable, e.g. smaller/secondary").
    assert 'id="interview" data-laeuft="0" data-pausiert="0" class="nebenknopf">' in seite

    ohne = web_chat.chat_html(dict(daten, phase=1), "1.x", "tok", "", 45000)
    for kennung in ("brainstorm", "brainstorm-aktionen", "brainstorm-pause",
                    "brainstorm-beenden"):
        assert f'id="{kennung}"' not in ohne, kennung
    assert 'class="nebenknopf"' not in ohne
    assert 'id="interview" data-laeuft="0" data-pausiert="0">' in ohne

    fehlt = web_chat.chat_html(dict(daten, phase=None), "1.x", "tok", "", 45000)
    assert 'id="brainstorm"' not in fehlt


def test_zeigebrainstormmodus_ist_ein_no_op_ohne_knopf():
    """Ausserhalb Phase 4 ist ``brainstormKnopf`` ``null`` -- die Funktion
    darf dann nichts anfassen, sonst wirft sie auf jeder Nicht-Phase-4-Seite."""
    js = web_chat._CHAT_JS
    fn = js[js.index("function zeigeBrainstormModus"):
            js.index("function starteBrainstorm")]
    assert "if (!brainstormKnopf) { return; }" in fn


def test_brainstorm_segment_geht_immer_sofort_raus():
    """Brainstorm kennt keinen Modus-Befehl -- ``bereit()`` schickt ein
    Segment dieser Sitzung immer, ohne auf ``zustand.servermodus`` zu warten
    (anders als eine Interview-Aufnahme, siehe
    ``test_kein_segment_geht_ohne_modus_raus``)."""
    js = web_chat._CHAT_JS
    bereit = js[js.index("function bereit"):js.index("function ueberholt")]
    assert "if (sitzung.art === 'brainstorm') { return true; }" in bereit


def test_postaudio_haengt_das_brainstorm_flag_an():
    js = web_chat._CHAT_JS
    ausschnitt = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "sitzung.art === 'brainstorm'" in ausschnitt
    assert "&brainstorm=1" in ausschnitt


def test_brainstorm_und_interview_schliessen_sich_gegenseitig_aus():
    """Zwei Mikrofone gleichzeitig sind keine Bedienung: ``starteBrainstorm``
    lehnt waehrend eines Interviews (oder eines laufenden Wechsels) ab,
    ``starteInterview`` ebenso waehrend eines laufenden Brainstorms, und
    beide Knoepfe sowie PTT werden entsprechend deaktiviert/versteckt."""
    js = web_chat._CHAT_JS
    start_bs = js[js.index("function starteBrainstorm"):
                  js.index("function pausiereBrainstorm")]
    assert "if (zustand.brainstorm || modusAn() || zustand.wechsel) { return; }" in start_bs

    start_iv = js[js.index("function starteInterview"):
                  js.index("function brichAb")]
    assert "if (zustand.aufnahme || zustand.wechsel || zustand.brainstorm) { return; }" in start_iv

    zeige_bs = js[js.index("function zeigeBrainstormModus"):
                  js.index("function starteBrainstorm")]
    assert "interviewKnopf.disabled = an ||" in zeige_bs
    assert "brainstormKnopf.disabled = modusAn() || !!zustand.wechsel;" in js

    zeige_iv = js[js.index("function zeigeModus"):js.index("function verwirfPtt")]
    assert "!!zustand.brainstorm" in zeige_iv
    assert "pttKnopf.hidden = an || !!zustand.wechsel || !!zustand.brainstorm;" in zeige_iv
    assert "pttKnopf.hidden = an || modusAn() || !!zustand.wechsel;" in zeige_bs


def test_fortsetzebrainstorm_hat_dieselbe_sperrklinke_wie_interview():
    """Re-Review-Befund (dieselbe Klasse wie bei ``fortsetzeInterview``,
    Befund 1): ``mikroUnterwegs`` muss schon VOR ``holeStrom()`` gesetzt
    werden, sonst erkennt ein waehrenddessen gedrueckter Pause-Knopf das
    unterwegs befindliche Mikrofon nicht und rechnet ``erfassteMs`` gegen ein
    ``legStart`` von ``null`` (NaN). Dazu eine Sperrklinke gegen einen
    hastigen Doppeldruck auf "Weiter"."""
    js = web_chat._CHAT_JS
    fortsetzen = js[js.index("function fortsetzeBrainstorm"):
                    js.index("function beendeBrainstorm")]
    assert "sitzung.fortsetzend" in fortsetzen
    vor_holestrom = fortsetzen[:fortsetzen.index("holeStrom().then")]
    assert "sitzung.mikroUnterwegs = true;" in vor_holestrom
    assert "sitzung.fortsetzend = true;" in vor_holestrom


def test_brainstorm_pruefeende_tut_nie_etwas():
    """``fertigEingereiht`` steht von Anfang an auf ``true`` -- die
    gemeinsame ``pruefeEnde()``-Funktion (Interview-Pfad) reiht fuer eine
    Brainstorm-Sitzung deshalb nie ein ``'befehl'``-Auftrag ein."""
    js = web_chat._CHAT_JS
    start = js[js.index("function starteBrainstorm"):
               js.index("function pausiereBrainstorm")]
    assert "fertigEingereiht: true" in start


def test_beendebrainstorm_gibt_das_mikrofon_sofort_frei():
    """Anders als beim Interview (wo ``pruefeEnde()`` im ``onstop`` das
    Mikrofon freigibt) tut ``pruefeEnde()`` bei Brainstorm nie etwas -- also
    muss ``beendeBrainstorm`` selbst ``gibFrei`` rufen, nicht erst ueber den
    Umweg eines Auftrags."""
    js = web_chat._CHAT_JS
    beenden = js[js.index("function beendeBrainstorm"):
                 js.index("function starteInterview")]
    assert "gibFrei(sitzung);" in beenden


def test_brainstorm_knoepfe_sind_verdrahtet():
    js = web_chat._CHAT_JS
    assert "brainstormPauseKnopf.addEventListener('click'" in js
    assert "brainstormBeendenKnopf.addEventListener('click', beendeBrainstorm);" in js
    assert "brainstormKnopf.addEventListener('click'" in js
    wiring = js[js.index("if (brainstormPauseKnopf)"):js.index("-- Push-to-Talk")]
    assert "fortsetzeBrainstorm()" in wiring
    assert "pausiereBrainstorm()" in wiring
    assert "starteBrainstorm()" in wiring


# -- UX-Knoepfe-Karte, Abschnitt 1: Knoepfe als Abkuerzungen ---------------


def test_freies_schreiben_veraltet_die_letzte_leiste():
    """Wer stattdessen tippt, sieht die zuletzt gezeigte Chip-Leiste
    weiterhin -- nur gedaempft (Klasse 'ueberholt'), nie entfernt."""
    js = web_chat._CHAT_JS
    assert "function veralteLetzteLeiste" in js
    senden = js[js.index("function sendeText"):js.index("document.getElementById('senden')")]
    assert "veralteLetzteLeiste()" in senden
    funktion = js[js.index("function veralteLetzteLeiste"):
                  js.index("function blaseZu")]
    assert "classList.add('ueberholt')" in funktion


def test_freies_sprechen_per_ptt_veraltet_ebenfalls_die_leiste():
    """Dieselbe Regel gilt fuer Push-to-Talk, nicht nur fuer Text."""
    js = web_chat._CHAT_JS
    start = js.index("if (druck.abgebrochen || druck.dauerMs < PTT_MIN_MS")
    ausschnitt = js[start:start + 400]
    assert "veralteLetzteLeiste()" in ausschnitt


def test_die_chip_leiste_traegt_ein_abkuerzungs_label(seite):
    """Server und Client bauen dieselbe Reihenfolge: Label, dann Leiste."""
    js = web_chat._CHAT_JS
    assert "function baueLabel" in js
    assert "TEXT.abkuerzung" in js
    blase = js[js.index("function blase(n)"):js.index("function ersetze(n)")]
    assert blase.index("baueLabel(n)") < blase.index("appendChild(leiste)")


def test_die_chip_leiste_ist_keine_vollbreite_pflichtleiste(seite):
    """UX-Knoepfe-Karte: kleine Abkuerzungs-Chips nebeneinander, nicht
    vollbreite Primaerknoepfe untereinander."""
    assert "flex-direction: row" in seite
    assert "border-radius: 999px" in seite


def test_manuelle_schnitte_tragen_den_grund_ende_fuer_brainstorm_auch():
    """``pausiereBrainstorm``/``beendeBrainstorm`` flushen wie beim Interview
    ueber ``_grund = 'ende'`` -- ein manueller Stopp haelt sich nicht an
    ``MIN_SPEECH_MS``."""
    js = web_chat._CHAT_JS
    pause = js[js.index("function pausiereBrainstorm"):
               js.index("function fortsetzeBrainstorm")]
    beenden = js[js.index("function beendeBrainstorm"):
                 js.index("function starteInterview")]
    assert "_grund = 'ende'" in pause
    assert "_grund = 'ende'" in beenden

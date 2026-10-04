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
                 "IT_WEB_VAD_FLOOR_FACTOR", "IT_WEB_VAD_KALIBRIERUNG"):
        monkeypatch.delenv(name, raising=False)
    assert web_chat._vad_werte() == {
        "pause_ms": 2500, "max_ms": 90_000, "min_speech_ms": 500,
        "rms": 0.01, "floor_faktor": 2.5, "kalibrierung": True,
    }


def test_die_vad_werte_kommen_einzeln_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_WEB_VAD_PAUSE_MS", "3000")
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", "60000")
    monkeypatch.setenv("IT_WEB_VAD_MIN_SPEECH_MS", "400")
    monkeypatch.setenv("IT_WEB_VAD_RMS", "0.02")
    monkeypatch.setenv("IT_WEB_VAD_FLOOR_FACTOR", "3.0")
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    assert web_chat._vad_werte() == {
        "pause_ms": 3000, "max_ms": 60000, "min_speech_ms": 400,
        "rms": 0.02, "floor_faktor": 3.0, "kalibrierung": False,
    }


def test_die_vad_kalibrierung_ist_per_vorgabe_an(monkeypatch):
    monkeypatch.delenv("IT_WEB_VAD_KALIBRIERUNG", raising=False)
    assert web_chat._vad_werte()["kalibrierung"] is True


def test_die_vad_kalibrierung_laesst_sich_abschalten(monkeypatch):
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    assert web_chat._vad_werte()["kalibrierung"] is False


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
    assert 'data-vad-kalibrierung="1"' in seite


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
    # pausiereInterview + beendeInterview + pausiereBrainstorm +
    # beendeBrainstorm + pausiereDiskussion + beendeDiskussion
    assert js.count("_grund = 'ende'") == 6


def test_der_grund_ende_wird_nur_mit_aktivem_vad_gesetzt():
    """Ohne AnalyserNode (Rueckfall auf den festen Takt) bleibt vadSpeechMs
    bei 0 -- ohne diese Wache wuerde Pause/Beenden das letzte Stueck NIE mehr
    hochladen, weil 'ende' ohne VAD faelschlich redeMs=0 saehe statt null."""
    js = web_chat._CHAT_JS
    assert "letzter && sitzung.vadAktiv) { letzter._grund = 'ende'" in js
    assert "alt && sitzung.vadAktiv) { alt._grund = 'ende'" in js


def test_onstop_laedt_jedes_segment_mit_bytes_hoch_ohne_redems_gate():
    """Kanban-Karte Mithoeren SICHER, Birks Szenario A: eine zu hoch
    eingestellte VAD-Schwelle liess leise, aber echte Rede als 'nicht genug'
    durchfallen, und das ganze Segment -- samt Woertern -- ging nie hoch.
    Seit dieser Karte gibt es dieses Gate nicht mehr: jedes Segment mit
    Bytes aus einer nicht verworfenen Sitzung wird hochgeladen, ``redeMs``
    faehrt nur noch als Metadatum mit.

    Wer das alte ``genug``-Gate wiederherstellt, macht diesen Test ROT --
    das ist der Zweck dieses Tests, kein Unfall.

    Seit Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026)
    traegt dieselbe Zeile zusaetzlich ``!r._kalVerworfen`` -- ein
    ANDERSARTIGES, bewusstes Verwerfen (der 30s-Stille-Rueckfall der
    Kalibrierung, der nichts zu testen hat), keine Rueckkehr des alten,
    lautstaerkebasierten Gates. Geprueft wird deshalb weiterhin, dass
    ``redeMs``/``grund`` dort nicht stehen -- nur das neue, orthogonale Flag
    ist erlaubt."""
    js = web_chat._CHAT_JS
    onstop = js[js.index("r.onstop = function"):js.index("r.start();")]
    # Kommentarzeilen koennen das Wort "genug" in Prosa erklaeren (siehe
    # Docstring oben) -- geprueft wird nur der tatsaechliche Code, nie ein
    # Erklaertext.
    code_ohne_kommentare = "\n".join(
        zeile for zeile in onstop.splitlines() if not zeile.strip().startswith("//")
    )
    assert "genug" not in code_ohne_kommentare, (
        "das alte Verwerfen-Gate darf nicht zurueckkommen"
    )

    gate_zeile = next(
        zeile for zeile in onstop.splitlines()
        if zeile.strip().startswith("if (teile.length")
    )
    assert gate_zeile.strip().startswith(
        "if (teile.length && !sitzung.verworfen && !r._kalVerworfen)"
    )
    assert "redeMs" not in gate_zeile
    assert "grund" not in gate_zeile


def test_auftrag_traegt_redems_und_postaudio_haengt_rede_an():
    """``redeMs`` ist seit der Karte 'Mithoeren SICHER' reines
    Diagnose-Metadatum: es haengt am ``auftrag`` und geht als ``&rede=``
    mit, wird aber nirgends mehr als Upload-Gate gelesen (siehe Test oben)."""
    js = web_chat._CHAT_JS
    onstop = js[js.index("r.onstop = function"):js.index("r.start();")]
    assert "redeMs: redeMs" in onstop

    ausschnitt = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "auftrag.redeMs != null" in ausschnitt
    assert "&rede=" in ausschnitt


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


def test_ptt_ist_ein_klick_umschalter_ohne_pointer_capture():
    """Von Halten-zum-Sprechen auf Tippen-zum-Umschalten umgebaut (Kanban-
    Karte Buehne/PTT, Punkt 3): ein Tipp startet, ein zweiter beendet und
    sendet -- kein Pointer-Capture-Geschehen mehr."""
    js = web_chat._CHAT_JS
    block = js[js.index("-- Push-to-Talk"):]
    assert "pttKnopf.addEventListener('click'" in block
    for veraltet in ("setPointerCapture", "pointercancel", "pointerdown",
                     "pointerup", "pointermove", "lostpointercapture",
                     "releasePointerCapture"):
        assert veraltet not in block, veraltet


def test_die_ptt_hoechstdauer_kommt_aus_einer_konstante(seite):
    assert web_chat.PTT_MAX_MS == 90_000
    assert f"var PTT_MAX_MS = {web_chat.PTT_MAX_MS};" in seite
    assert "__PTT_MAX_MS__" in web_chat._CHAT_JS


def test_ptt_stoppt_und_sendet_automatisch_nach_der_hoechstdauer():
    js = web_chat._CHAT_JS
    block = js[js.index("-- Push-to-Talk"):]
    assert "setTimeout(" in block
    assert "PTT_MAX_MS" in block
    assert "beendePtt()" in block


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
    immer die Pause-Darstellung (Punkt 5 des Reglers).

    ``brainstorm_knopf: False`` haelt den Interview-Knopf hier ohne
    ``nebenknopf``-Klasse (Task 2, Kanban-Karte Buehne/PTT) -- dieser Test
    prueft den Interviewmodus, nicht die Brainstorm-Phase."""
    daten = {"nachrichten": [], "letzte": 0, "aenderung": 0,
             "interviewmodus": True, "titel": None, "brainstorm_knopf": False}
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
    """Re-Review F: zwei Mikrofone gleichzeitig sind keine Bedienung -- auch
    nicht im Tippen-zum-Umschalten-Modell (Kanban-Karte Buehne/PTT)."""
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
    # starteInterview + fortsetzeInterview + starteBrainstorm +
    # fortsetzeBrainstorm + starteDiskussion + fortsetzeDiskussion
    assert js.count("beginneAufnahme(sitzung);") == 6
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
    ein Link teilbar bleibt und ein zweites Telefon dieselbe Gruppe sieht.

    Die EINE genannte Ausnahme (Task 2, Kanban-Karte Mithoeren SICHER/
    Kalibrierung, 03.10.2026): genau drei ``localStorage``-Schluessel fuer
    das gemessene Kalibrierungsergebnis dieses GERAETS (nicht der Gruppe) --
    ``vad_boden_mess``/``vad_rede_mess``/``vad_schwelle``. Das ist bewusst
    eng: kein Link haengt daran, ein zweites Telefon sieht dieselbe Gruppe
    weiterhin unveraendert, es misst nur sein eigenes Mikrofon noch einmal."""
    assert "document.cookie" not in web_chat._CHAT_JS
    assert "sessionStorage" not in web_chat._CHAT_JS
    assert "WebSocket" not in web_chat._CHAT_JS
    assert "EventSource" not in web_chat._CHAT_JS
    for schluessel in ("getItem", "setItem"):
        assert f"localStorage.{schluessel}" in web_chat._CHAT_JS, schluessel
    erlaubte_schluessel = {"vad_boden_mess", "vad_rede_mess", "vad_schwelle"}
    gefundene = set(re.findall(r"localStorage\.(?:get|set)Item\(([A-Za-z_]+)", web_chat._CHAT_JS))
    # Die Aufrufe nennen die Konstante, nicht den Schluessel woertlich --
    # die Konstanten selbst muessen auf genau die drei Namen zeigen.
    konstanten = dict(re.findall(
        r"var (KAL_LS_[A-Z]+) = '([a-z_]+)';", web_chat._CHAT_JS,
    ))
    assert gefundene, "kein localStorage-Zugriff ueber eine Konstante gefunden"
    assert gefundene <= set(konstanten), gefundene
    assert {konstanten[k] for k in gefundene} <= erlaubte_schluessel
    assert set(konstanten.values()) == erlaubte_schluessel


# -- Brainstorm mithoeren (Phase 4, nur Web, 02.10.2026) ---------------------


def test_der_brainstorm_knopf_steht_immer_im_markup_aber_hidden_ausserhalb_phase_4():
    """Seit Task 2 (Kanban-Karte Buehne/PTT, wie zuvor beim CoThinker-Tab)
    rendert ``chat_html`` die vier Brainstorm-Elemente IMMER -- nur das
    ``hidden``-Attribut am ``#brainstorm``-Knopf und die ``nebenknopf``-
    Klasse am Interview-Knopf folgen ``daten["brainstorm_knopf"]``, nicht
    mehr ihre Existenz im Markup."""
    daten = {"nachrichten": [], "letzte": 0, "aenderung": 0,
             "interviewmodus": False, "titel": None, "phase": 4,
             "brainstorm_knopf": True}
    seite = web_chat.chat_html(daten, "1.x", "tok", "", 45000)
    for kennung in ("brainstorm", "brainstorm-aktionen", "brainstorm-pause",
                    "brainstorm-beenden"):
        assert f'id="{kennung}"' in seite, kennung
    assert web_chat._TEXT_BRAINSTORM_AN in seite
    assert 'id="brainstorm" data-laeuft="0" data-pausiert="0">' in seite
    # Das Interview bleibt erreichbar, aber als Nebenknopf (brief: "stays
    # reachable, e.g. smaller/secondary").
    assert 'id="interview" data-laeuft="0" data-pausiert="0" class="nebenknopf">' in seite

    ohne = web_chat.chat_html(
        dict(daten, phase=1, brainstorm_knopf=False), "1.x", "tok", "", 45000)
    for kennung in ("brainstorm", "brainstorm-aktionen", "brainstorm-pause",
                    "brainstorm-beenden"):
        assert f'id="{kennung}"' in ohne, kennung
    assert 'id="brainstorm" data-laeuft="0" data-pausiert="0" hidden>' in ohne
    assert 'class="nebenknopf"' not in ohne
    assert 'id="interview" data-laeuft="0" data-pausiert="0">' in ohne

    fehlt = web_chat.chat_html(
        dict(daten, phase=None, brainstorm_knopf=False), "1.x", "tok", "", 45000)
    assert 'id="brainstorm" data-laeuft="0" data-pausiert="0" hidden>' in fehlt


def test_zeigebrainstormmodus_behaelt_die_schutzzeile_fuer_fehlende_elemente():
    """Seit Task 2 existiert ``brainstormKnopf`` immer (``chat_html``
    rendert das Element jetzt auch ausserhalb Phase 4, nur ``hidden``) --
    die fruehere Praemisse dieses Tests ("ausserhalb Phase 4 ist
    brainstormKnopf null") gilt also nicht mehr. Die Schutzzeile bleibt
    trotzdem im Quelltext stehen (Brief, Abschnitt 3d) und wird hier als
    das geprueft, was sie jetzt ist: ein defensiver Schutz fuer ein
    hypothetisch fehlendes Element, kein aktiv genutzter Zweig."""
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
    beide Knoepfe sowie PTT werden entsprechend deaktiviert/versteckt.

    Abschluss-Review (Finding 2): ``starteBrainstorm``/``brainstormKnopf.
    disabled`` sperren seitdem auch gegen ``zustand.diskussion`` -- symmetrisch
    zur bestehenden Sperre von ``starteDiskussion()`` gegen
    ``zustand.brainstorm`` (095e6e9). Vorher konnte eine Gruppe, die eine
    Diskussion-Sitzung (Phase 1) nie beendet und spaeter in Phase 4
    "Brainstorm mithoeren" drueckt, einen zweiten Recorder auf demselben
    Mikrofon starten (siehe ``test_startebrainstorm_und_starteptt_lehnen_waehrend_diskussion_ab``)."""
    js = web_chat._CHAT_JS
    start_bs = js[js.index("function starteBrainstorm"):
                  js.index("function pausiereBrainstorm")]
    assert ("if (zustand.brainstorm || modusAn() || zustand.wechsel || "
            "zustand.diskussion) { return; }") in start_bs

    start_iv = js[js.index("function starteInterview"):
                  js.index("function brichAb")]
    assert "if (zustand.aufnahme || zustand.wechsel || zustand.brainstorm) { return; }" in start_iv

    zeige_bs = js[js.index("function zeigeBrainstormModus"):
                  js.index("function starteBrainstorm")]
    assert ("brainstormKnopf.disabled = modusAn() || !!zustand.wechsel || "
            "!!zustand.diskussion;") in js

    # Re-Review (Task 6, Fund 1): interviewKnopf.disabled/pttKnopf.hidden
    # werden seitdem NICHT mehr in zeigeBrainstormModus() gesetzt -- sonst
    # ueberschreibt die zuletzt gerufene Anzeigefunktion (zeigeDiskussionModus)
    # unbedingt, was diese hier zuvor gesetzt hat (siehe
    # test_zeigemodus_fuehrt_brainstorm_und_diskussion_zusammen).
    assert "interviewKnopf.disabled =" not in zeige_bs
    assert "pttKnopf.hidden =" not in zeige_bs

    zeige_iv = js[js.index("function zeigeModus"):js.index("function verwirfPtt")]
    assert "!!zustand.brainstorm" in zeige_iv
    assert "var nebenAn = !!zustand.brainstorm || !!zustand.diskussion;" in zeige_iv
    assert "interviewKnopf.disabled = !!(zustand.wechsel && !zustand.wechsel.ziel) || nebenAn;" in zeige_iv
    assert "if (pttKnopf) { pttKnopf.hidden = an || !!zustand.wechsel || nebenAn; }" in zeige_iv


def test_starteptt_lehnt_waehrend_diskussion_ab():
    """Abschluss-Review (Finding 2): ``startePtt()`` sperrte bereits gegen
    ``zustand.brainstorm`` -- ``zustand.diskussion`` fehlte in derselben
    Waeche, obwohl PTT ein drittes Mikrofon auf demselben Geraet waere."""
    js = web_chat._CHAT_JS
    # "function beendePtt" allein traefe zuerst auf "function beendePttAnzeige"
    # (das Praefix passt) -- die Klammer dahinter macht die Endmarke eindeutig.
    start_ptt = js[js.index("function startePtt"):js.index("function beendePtt() {")]
    assert ("if (modusAn() || zustand.wechsel || zustand.brainstorm || "
            "zustand.diskussion ||\n        zustand.ptt) { return; }") in start_ptt


def test_startebrainstorm_und_starteptt_lehnen_waehrend_diskussion_tatsaechlich_ab_in_node(
    tmp_path,
):
    """Verhaltensnachweis in Node (nicht nur String-Match): das realistischere
    Szenario aus dem Abschluss-Review ist die normale Ablaufrichtung --
    "Zuhoeren starten" in Phase 1 bleibt ueber den Fortschritt in Phase 4
    offen (niemand drueckt ``beendeDiskussion()``), und die Gruppe drueckt
    dort "Brainstorm mithoeren" (jetzt serverseitig sichtbar, ``phase == 4``).
    Ohne den Fix startet ``starteBrainstorm()`` trotzdem einen zweiten
    ``MediaRecorder`` auf demselben Mikrofon -- ebenso ``startePtt()`` fuer
    die Sprachnavigation. Dieser Test fuehrt ``starteBrainstorm``/
    ``startePtt`` WOERTLICH aus dem ausgelieferten Skript aus und bestaetigt,
    dass beide bei laufender ``zustand.diskussion`` synchron (vor jedem
    ``holeStrom()``-Promise) abbrechen, ohne eine eigene Sitzung bzw. einen
    eigenen PTT-Druck anzulegen."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    modus_an = _extrahiere(js, "function modusAn", "function zeigeModus")
    start_bs = _extrahiere(js, "function starteBrainstorm", "function pausiereBrainstorm")
    # "function beendePtt" allein traefe zuerst auf "function beendePttAnzeige"
    # (das Praefix passt) -- die Klammer dahinter macht die Endmarke eindeutig.
    start_ptt = _extrahiere(js, "function startePtt", "function beendePtt() {")

    quelltext = f"""
    var zustand, pttKnopf, verwirfAufgerufen;
    var PTT_MAX_MS = {web_chat.PTT_MAX_MS};

    {modus_an}

    function verwirfPtt() {{ verwirfAufgerufen = true; }}
    function zeigeBrainstormModus() {{}}
    function holeStrom() {{ return new Promise(function () {{}}); }}
    function setTimeout() {{ return {{}}; }}
    function clearTimeout() {{}}
    function setInterval() {{ return {{}}; }}
    function clearInterval() {{}}

    {start_bs}
    {start_ptt}

    function lauf(mitDiskussion) {{
      zustand = {{
        brainstorm: null, aufnahme: null, servermodus: false, wechsel: null,
        ptt: null, diskussion: mitDiskussion ? {{ pausiert: false }} : null
      }};
      pttKnopf = {{ dataset: {{}} }};
      verwirfAufgerufen = false;
      starteBrainstorm();
      var brainstormGestartet = !!zustand.brainstorm;
      zustand.brainstorm = null;   // unabhaengig von der Brainstorm-Probe testen
      startePtt();
      var pttGestartet = !!zustand.ptt;
      return {{ brainstormGestartet: brainstormGestartet, pttGestartet: pttGestartet }};
    }}

    var ergebnisse = {{
      waehrendDiskussion: lauf(true),
      ohneDiskussion: lauf(false)
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    # Der eigentliche Fix: waehrend zustand.diskussion laeuft, startet KEINE
    # der beiden Funktionen eine eigene Sitzung bzw. einen eigenen Druck.
    assert ergebnisse["waehrendDiskussion"] == {
        "brainstormGestartet": False, "pttGestartet": False,
    }
    # Gegenprobe: ohne zustand.diskussion funktionieren beide wie zuvor --
    # der Fix darf den Normalfall nicht mitsperren.
    assert ergebnisse["ohneDiskussion"] == {
        "brainstormGestartet": True, "pttGestartet": True,
    }


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


# -- Hintergrund-Mithoeren Phase 1 (Padua Phase 1+2 Umbau, 03.10.2026,
#    Task 6) -----------------------------------------------------------------
#
# Derselbe Aufbau wie der Brainstorm-Block oben (eigener Zustandsslot
# ``zustand.diskussion``, eigene DOM-Elemente ``#diskussion``/
# ``#diskussion-pause``/``#diskussion-beenden``) -- die Tests hier sind der
# strukturelle Zwilling der Brainstorm-Tests, nur auf die neuen Namen
# umgelegt.


def test_der_diskussion_knopf_steht_immer_im_markup_aber_hidden_ausserhalb_phase_1():
    """Wie beim Brainstorm-Knopf (Task 2) rendert ``chat_html`` die vier
    Diskussion-Elemente IMMER -- nur das ``hidden``-Attribut am
    ``#diskussion``-Knopf folgt ``daten["diskussion_knopf"]`` (server-
    seitige Vorgabe ``False``, anders als Brainstorms ``True`` -- das
    Hintergrund-Mithoeren ist ausgeschaltet, wenn der Server den Schluessel
    gar nicht mitschickt)."""
    daten = {"nachrichten": [], "letzte": 0, "aenderung": 0,
             "interviewmodus": False, "titel": None, "phase": 1,
             "diskussion_knopf": True}
    seite = web_chat.chat_html(daten, "1.x", "tok", "", 45000)
    for kennung in ("diskussion", "diskussion-aktionen", "diskussion-pause",
                    "diskussion-beenden"):
        assert f'id="{kennung}"' in seite, kennung
    assert web_chat._TEXT_DISKUSSION_AN in seite
    assert web_chat._TEXT_DISKUSSION_FERTIG_KNOPF in seite
    assert 'id="diskussion" data-laeuft="0" data-pausiert="0">' in seite
    # Der Beenden-Knopf traegt die UX-Markierung fuer die parallele Karte
    # (Global Constraints, data-discussion-done="1") -- das landete schon in
    # Task 5, hier nur mitgeprueft, weil die Markup-Form zusammengehoert.
    assert 'id="diskussion-beenden" data-discussion-done="1">' in seite

    ohne = web_chat.chat_html(
        dict(daten, diskussion_knopf=False), "1.x", "tok", "", 45000)
    for kennung in ("diskussion", "diskussion-aktionen", "diskussion-pause",
                    "diskussion-beenden"):
        assert f'id="{kennung}"' in ohne, kennung
    assert 'id="diskussion" data-laeuft="0" data-pausiert="0" hidden>' in ohne

    fehlt = web_chat.chat_html(
        dict(daten, phase=None, diskussion_knopf=False), "1.x", "tok", "", 45000)
    assert 'id="diskussion" data-laeuft="0" data-pausiert="0" hidden>' in fehlt


def test_zeigediskussionmodus_behaelt_die_schutzzeile_fuer_fehlende_elemente():
    """Dieselbe defensive Schutzzeile wie ``zeigeBrainstormModus`` (die
    Elemente stehen zwar immer im Markup, die Funktion bleibt trotzdem
    robust gegen ein hypothetisch fehlendes Element)."""
    js = web_chat._CHAT_JS
    fn = js[js.index("function zeigeDiskussionModus"):
            js.index("function starteDiskussion")]
    assert "if (!diskussionKnopf) { return; }" in fn


def test_diskussion_segment_geht_immer_sofort_raus():
    """Diskussion kennt keinen Modus-Befehl -- ``bereit()`` schickt ein
    Segment dieser Sitzung immer, ohne auf ``zustand.servermodus`` zu
    warten (dieselbe Regel wie bei Brainstorm)."""
    js = web_chat._CHAT_JS
    bereit = js[js.index("function bereit"):js.index("function ueberholt")]
    assert "if (sitzung.art === 'diskussion') { return true; }" in bereit


def test_postaudio_haengt_das_diskussion_flag_an():
    js = web_chat._CHAT_JS
    ausschnitt = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "sitzung.art === 'diskussion'" in ausschnitt
    assert "&diskussion=1" in ausschnitt


def test_starte_diskussion_lehnt_waehrend_interview_oder_wechsel_ab():
    """Eigene Sitzung, Interviewmodus (``modusAn()``), ein laufender Wechsel
    UND ein laufender Brainstorm schliessen einen Start aus.

    Re-Review (Task 6, Fund 2): ``zustand.brainstorm`` fehlte in der Waeche
    urspruenglich -- anders als bei ``starteInterview``/``startePtt``, die
    beide separat dagegen sperren. Ohne diese Zeile koennte ein
    Phase-4-zu-1-Wechsel mit noch laufendem Brainstorm auf einem anderen Tab
    einen zweiten Recorder auf demselben Mikrofon starten."""
    js = web_chat._CHAT_JS
    start = js[js.index("function starteDiskussion"):
               js.index("function pausiereDiskussion")]
    assert ("if (zustand.diskussion || modusAn() || zustand.wechsel || "
            "zustand.brainstorm) { return; }") in start


def test_zeigediskussionmodus_ueberschreibt_interview_und_ptt_nicht_mehr():
    """Re-Review (Task 6, Fund 1, Kritisch): ``zeigeDiskussionModus`` darf
    ``interviewKnopf.disabled``/``classList``/``pttKnopf.hidden`` nicht mehr
    selbst setzen -- sie liefen VOR dem Fix unbedingt und mit nur dem
    eigenen Sitzungsflag, und weil ``zeigeModus()`` ``zeigeDiskussionModus()``
    IMMER nach ``zeigeBrainstormModus()`` ruft, gewann am Ende immer die
    Diskussions-Formel und loeschte die Brainstorm-Sperre, sobald
    ``zustand.diskussion`` leer war (der Normalfall). Die Zusammenfuehrung
    sitzt seitdem einmal in ``zeigeModus()`` (siehe
    ``test_zeigemodus_fuehrt_brainstorm_und_diskussion_zusammen``)."""
    js = web_chat._CHAT_JS
    zeige_ds = js[js.index("function zeigeDiskussionModus"):
                  js.index("function starteDiskussion")]
    assert "diskussionKnopf.disabled = modusAn() || !!zustand.wechsel;" in zeige_ds
    assert "interviewKnopf.disabled =" not in zeige_ds
    assert "interviewKnopf.classList" not in zeige_ds
    assert "pttKnopf.hidden =" not in zeige_ds
    # zeigeModus() ruft beide Anzeigen am Ende auf, damit sie im selben Takt
    # synchron bleiben -- wie es schon fuer Brainstorm galt -- und fuehrt
    # DANACH die gemeinsame Formel einmal zusammen.
    zeige_iv = js[js.index("function zeigeModus"):js.index("function verwirfPtt")]
    assert "zeigeBrainstormModus();" in zeige_iv
    assert "zeigeDiskussionModus();" in zeige_iv
    assert zeige_iv.index("zeigeBrainstormModus();") < zeige_iv.index("zeigeDiskussionModus();")
    assert zeige_iv.index("zeigeDiskussionModus();") < zeige_iv.index("nebenSichtbar")


def test_zeigebrainstormmodus_ueberschreibt_interview_und_ptt_auch_nicht_mehr():
    """Dieselbe Entfernung auf der Brainstorm-Seite -- symmetrisch zum Fund
    oben, sonst waere das naechste Feature auf derselben Flaeche wieder
    anfaellig fuer dieselbe Art Ueberschreiben."""
    js = web_chat._CHAT_JS
    zeige_bs = js[js.index("function zeigeBrainstormModus"):
                  js.index("function starteBrainstorm")]
    assert "interviewKnopf.disabled =" not in zeige_bs
    assert "interviewKnopf.classList" not in zeige_bs
    assert "pttKnopf.hidden =" not in zeige_bs


def test_zeigemodus_fuehrt_brainstorm_und_diskussion_zusammen_in_node(tmp_path):
    """Verhaltensnachweis fuer den Kritisch-Fund in Node: ``zeigeModus()``
    ruft woertlich (nicht nachgebaut) ``zeigeBrainstormModus()`` und
    ``zeigeDiskussionModus()`` und muss am Ende ``interviewKnopf.disabled``/
    ``pttKnopf.hidden``/die ``nebenknopf``-Klasse aus BEIDEN Sitzungsflaggen
    kombinieren -- fuer alle vier Kombinationen, auch "beide gleichzeitig"
    (sollte normal nicht vorkommen, darf aber nicht crashen oder falsch
    rechnen)."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    modus_an = _extrahiere(js, "function modusAn", "function zeigeModus")
    zeige_modus = _extrahiere(js, "function zeigeModus", "function verwirfPtt")
    zeige_bs = _extrahiere(js, "function zeigeBrainstormModus", "function starteBrainstorm")
    zeige_ds = _extrahiere(js, "function zeigeDiskussionModus", "function starteDiskussion")

    quelltext = f"""
    var zustand, TEXT, interviewKnopf, pttKnopf, fuss,
        interviewAktionenFeld, interviewPauseKnopf,
        brainstormKnopf, brainstormAktionenFeld, brainstormPauseKnopf,
        diskussionKnopf, diskussionAktionenFeld, diskussionPauseKnopf;

    TEXT = {{
      interview_an: 'an', interview_pausiert: '{{zeit}}', interview_laeuft: '{{zeit}}',
      interview_weiter: 'weiter', interview_pause: 'pause',
      brainstorm_an: 'an', brainstorm_laeuft: '{{zeit}}',
      diskussion_an: 'an', diskussion_laeuft: '{{zeit}}'
    }};
    function formatiereUhr() {{ return '0:00'; }}

    {modus_an}
    {zeige_modus}
    {zeige_bs}
    {zeige_ds}

    function neuerKnopf() {{
      return {{
        dataset: {{}}, textContent: '', disabled: false, hidden: false,
        classList: {{ werte: {{}}, toggle: function (cls, an) {{ this.werte[cls] = !!an; }} }}
      }};
    }}

    function lauf(werte, mitDiskussionKnopf) {{
      zustand = Object.assign({{
        aufnahme: null, servermodus: false, wechsel: null, warteschlange: [],
        knopfErlaubt: false, brainstorm: null, diskussion: null,
        brainstormErlaubt: false, diskussionErlaubt: false
      }}, werte);
      interviewKnopf = neuerKnopf();
      pttKnopf = neuerKnopf();
      fuss = {{ dataset: {{}} }};
      interviewAktionenFeld = {{ hidden: false }};
      interviewPauseKnopf = {{ textContent: '' }};
      brainstormKnopf = neuerKnopf();
      brainstormAktionenFeld = {{ hidden: false }};
      brainstormPauseKnopf = {{ textContent: '' }};
      diskussionKnopf = mitDiskussionKnopf ? neuerKnopf() : null;
      diskussionAktionenFeld = {{ hidden: false }};
      diskussionPauseKnopf = {{ textContent: '' }};
      zeigeModus();
      return {{
        disabled: interviewKnopf.disabled,
        nebenknopf: !!interviewKnopf.classList.werte.nebenknopf,
        pttHidden: pttKnopf.hidden
      }};
    }}

    var ergebnisse = {{
      nur_brainstorm: lauf({{ brainstorm: {{ pausiert: false }} }}, true),
      nur_diskussion: lauf({{ diskussion: {{ pausiert: false }} }}, true),
      keines: lauf({{}}, true),
      beides: lauf({{ brainstorm: {{ pausiert: false }}, diskussion: {{ pausiert: false }} }}, true)
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    # Fund 1 (Kritisch): ein laufender Brainstorm ohne jemals beruehrtes
    # zustand.diskussion darf interviewKnopf/pttKnopf NICHT wieder freigeben
    # -- das war der Regressionsfall, reproduzierbar bei jeder Phase-4-
    # Brainstormsitzung.
    assert ergebnisse["nur_brainstorm"] == {
        "disabled": True, "nebenknopf": True, "pttHidden": True,
    }
    assert ergebnisse["nur_diskussion"] == {
        "disabled": True, "nebenknopf": True, "pttHidden": True,
    }
    assert ergebnisse["keines"] == {
        "disabled": False, "nebenknopf": False, "pttHidden": False,
    }
    assert ergebnisse["beides"] == {
        "disabled": True, "nebenknopf": True, "pttHidden": True,
    }


def test_zeigemodus_brainstorm_nur_szenario_bleibt_byte_identisch_zu_vor_task6_in_node(tmp_path):
    """Regressionsnachweis: in einem Szenario, in dem ``zustand.diskussion``
    nie beruehrt wird (der Normalfall jeder Nicht-Padua-Gruppe -- dort
    rendert der ``#diskussion``-Knopf gar nicht erst), muss
    ``interviewKnopf.disabled``/``pttKnopf.hidden``/die ``nebenknopf``-Klasse
    GENAU der Formel entsprechen, die vor dem gesamten Task-6-Commit galt:
    ``an(brainstorm) || (wechsel && !wechsel.ziel)`` fuer ``disabled``,
    ``modusAn() || wechsel || an(brainstorm)`` fuer ``pttKnopf.hidden`` und
    ``brainstormErlaubt || an(brainstorm) || wechsel`` fuer die Klasse --
    unabhaengig davon, in welcher Reihenfolge ``zeigeBrainstormModus()`` und
    ``zeigeDiskussionModus()`` laufen."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    modus_an = _extrahiere(js, "function modusAn", "function zeigeModus")
    zeige_modus = _extrahiere(js, "function zeigeModus", "function verwirfPtt")
    zeige_bs = _extrahiere(js, "function zeigeBrainstormModus", "function starteBrainstorm")
    zeige_ds = _extrahiere(js, "function zeigeDiskussionModus", "function starteDiskussion")

    quelltext = f"""
    var zustand, TEXT, interviewKnopf, pttKnopf, fuss,
        interviewAktionenFeld, interviewPauseKnopf,
        brainstormKnopf, brainstormAktionenFeld, brainstormPauseKnopf,
        diskussionKnopf, diskussionAktionenFeld, diskussionPauseKnopf;

    TEXT = {{
      interview_an: 'an', interview_pausiert: '{{zeit}}', interview_laeuft: '{{zeit}}',
      interview_weiter: 'weiter', interview_pause: 'pause',
      brainstorm_an: 'an', brainstorm_laeuft: '{{zeit}}',
      diskussion_an: 'an', diskussion_laeuft: '{{zeit}}'
    }};
    function formatiereUhr() {{ return '0:00'; }}

    {modus_an}
    {zeige_modus}
    {zeige_bs}
    {zeige_ds}

    function neuerKnopf() {{
      return {{
        dataset: {{}}, textContent: '', disabled: false, hidden: false,
        classList: {{ werte: {{}}, toggle: function (cls, an) {{ this.werte[cls] = !!an; }} }}
      }};
    }}

    // Die Formel, wie sie VOR Task 6 (ohne jede Diskussions-Variable) in
    // zeigeModus()/zeigeBrainstormModus() stand.
    function altesDisabled(z) {{
      return !!(z.wechsel && !z.wechsel.ziel) || !!z.brainstorm;
    }}
    function altesPttHidden(z) {{
      var an = !!z.aufnahme || !!z.servermodus;
      return an || !!z.wechsel || !!z.brainstorm;
    }}
    function altesNebenknopf(z) {{
      return !!z.brainstormErlaubt || !!z.brainstorm || !!z.wechsel;
    }}

    function lauf(werte) {{
      // Kein #diskussion-Knopf im Markup (Nicht-Padua-Profil) UND
      // zustand.diskussion nie gesetzt -- der tatsaechliche Normalfall.
      zustand = Object.assign({{
        aufnahme: null, servermodus: false, wechsel: null, warteschlange: [],
        knopfErlaubt: false, brainstorm: null, brainstormErlaubt: false
      }}, werte);
      interviewKnopf = neuerKnopf();
      pttKnopf = neuerKnopf();
      fuss = {{ dataset: {{}} }};
      interviewAktionenFeld = {{ hidden: false }};
      interviewPauseKnopf = {{ textContent: '' }};
      brainstormKnopf = neuerKnopf();
      brainstormAktionenFeld = {{ hidden: false }};
      brainstormPauseKnopf = {{ textContent: '' }};
      diskussionKnopf = null;
      zeigeModus();
      return {{
        disabled: interviewKnopf.disabled,
        nebenknopf: !!interviewKnopf.classList.werte.nebenknopf,
        pttHidden: pttKnopf.hidden,
        erwartetDisabled: altesDisabled(zustand),
        erwartetPttHidden: altesPttHidden(zustand),
        erwartetNebenknopf: altesNebenknopf(zustand)
      }};
    }}

    var faelle = [
      {{}},
      {{ brainstorm: {{ pausiert: false }} }},
      {{ brainstorm: {{ pausiert: true }} }},
      {{ wechsel: {{ ziel: true }} }},
      {{ wechsel: {{ ziel: false }} }},
      {{ brainstormErlaubt: true }},
      {{ brainstorm: {{ pausiert: false }}, wechsel: {{ ziel: false }} }},
      {{ aufnahme: {{ pausiert: false }} }}
    ];
    var ergebnisse = faelle.map(lauf);
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert len(ergebnisse) == 8
    for fall in ergebnisse:
        assert fall["disabled"] == fall["erwartetDisabled"], fall
        assert fall["pttHidden"] == fall["erwartetPttHidden"], fall
        assert fall["nebenknopf"] == fall["erwartetNebenknopf"], fall


def test_fortsetzediskussion_hat_dieselbe_sperrklinke_wie_brainstorm():
    """Dieselbe Sperrklinke (``fortsetzend``) und dasselbe Timing von
    ``mikroUnterwegs`` wie ``fortsetzeBrainstorm``/``fortsetzeInterview``."""
    js = web_chat._CHAT_JS
    fortsetzen = js[js.index("function fortsetzeDiskussion"):
                    js.index("function beendeDiskussion")]
    assert "sitzung.fortsetzend" in fortsetzen
    vor_holestrom = fortsetzen[:fortsetzen.index("holeStrom().then")]
    assert "sitzung.mikroUnterwegs = true;" in vor_holestrom
    assert "sitzung.fortsetzend = true;" in vor_holestrom


def test_diskussion_pruefeende_tut_nie_etwas():
    """``fertigEingereiht`` steht von Anfang an auf ``true`` -- die
    gemeinsame ``pruefeEnde()``-Funktion (Interview-Pfad) reiht fuer eine
    Diskussion-Sitzung deshalb nie ein ``'befehl'``-Auftrag ein."""
    js = web_chat._CHAT_JS
    start = js[js.index("function starteDiskussion"):
               js.index("function pausiereDiskussion")]
    assert "fertigEingereiht: true" in start


def test_beendediskussion_gibt_das_mikrofon_sofort_frei():
    """Wie ``beendeBrainstorm``: ``pruefeEnde()`` tut bei Diskussion nie
    etwas, also gibt ``beendeDiskussion`` das Mikrofon selbst frei, statt
    ueber den Umweg eines Auftrags."""
    js = web_chat._CHAT_JS
    beenden = js[js.index("function beendeDiskussion"):
                 js.index("function starteInterview")]
    assert "gibFrei(sitzung);" in beenden


def test_diskussion_knoepfe_sind_verdrahtet():
    js = web_chat._CHAT_JS
    assert "diskussionPauseKnopf.addEventListener('click'" in js
    assert "diskussionBeendenKnopf.addEventListener('click', beendeDiskussion);" in js
    assert "diskussionKnopf.addEventListener('click'" in js
    wiring = js[js.index("if (diskussionPauseKnopf)"):js.index("-- Push-to-Talk")]
    assert "fortsetzeDiskussion()" in wiring
    assert "pausiereDiskussion()" in wiring
    assert "starteDiskussion()" in wiring


def test_manuelle_schnitte_tragen_den_grund_ende_fuer_diskussion_auch():
    """``pausiereDiskussion``/``beendeDiskussion`` flushen wie beim
    Interview/Brainstorm ueber ``_grund = 'ende'``."""
    js = web_chat._CHAT_JS
    pause = js[js.index("function pausiereDiskussion"):
               js.index("function fortsetzeDiskussion")]
    beenden = js[js.index("function beendeDiskussion"):
                 js.index("function starteInterview")]
    assert "_grund = 'ende'" in pause
    assert "_grund = 'ende'" in beenden


def test_diskussion_hat_einen_eigenen_zustandsslot():
    """Global Constraints / Brief: ``zustand.diskussion`` ist ein eigener
    Slot, keine Wiederverwendung von ``zustand.brainstorm``."""
    js = web_chat._CHAT_JS
    assert "zustand.diskussion" in js
    assert "diskussionErlaubt: !diskussionKnopf.hidden" in js
    assert "if (typeof daten.diskussion_knopf === 'boolean') " \
           "{ zustand.diskussionErlaubt = daten.diskussion_knopf; }" in js


def test_diskussion_texte_kommen_aus_dem_text_objekt():
    """``_TEXT_DISKUSSION_AN``/``_TEXT_DISKUSSION_LAEUFT`` muessen denselben
    Weg wie die Brainstorm-Texte nehmen: hot-reload-faehig ueber ``T`` in
    ``_js()``, nicht als Literal im Skript."""
    js = web_chat._js()
    texte = json.loads(js[js.index("var TEXT = ") + len("var TEXT = "):
                          js.index(";\n", js.index("var TEXT = "))])
    assert texte["diskussion_an"] == web_chat._TEXT_DISKUSSION_AN
    assert texte["diskussion_laeuft"] == web_chat._TEXT_DISKUSSION_LAEUFT
    assert "TEXT.diskussion_an" in web_chat._CHAT_JS
    assert "TEXT.diskussion_laeuft" in web_chat._CHAT_JS


# -- Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/             --
# -- Kalibrierung, 03.10.2026): die reinen Rechenfunktionen, woertlich aus  --
# -- dem ausgelieferten Skript ausgefuehrt. --------------------------------


def test_kalzuleise_entscheidet_live_in_node(tmp_path):
    """Item (d): ``rede_mess / boden_mess < 3`` ODER unter 2000ms Stimmzeit.
    Mutant: Faktor 3 -> 1 liesse einen Fall, der 'zu leise' sein soll,
    unerkannt -- das deckt die zweite Assertion unten ab."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(js, "function kalZuLeise", "function kalSchwelle")
    quelltext = f"""
    {funktion}
    var ergebnisse = {{
      genau_am_faktor: kalZuLeise(0.03, 0.01, 4000),      // 3x genau, genug Stimmzeit
      knapp_darunter: kalZuLeise(0.0299, 0.01, 4000),      // < 3x -> zu leise
      genug_laut_aber_zu_kurz: kalZuLeise(0.1, 0.01, 1500),// laut genug, aber < 2000ms
      laut_und_lang_genug: kalZuLeise(0.1, 0.01, 4000)
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse == {
        "genau_am_faktor": False,
        "knapp_darunter": True,
        "genug_laut_aber_zu_kurz": True,
        "laut_und_lang_genug": False,
    }


def test_kalschwelle_ist_das_geklemmte_geometrische_mittel_live_in_node(tmp_path):
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(js, "function kalSchwelle", "function kalBerechneBodenUndSchwelle")
    quelltext = f"""
    var KAL_SCHWELLE_ABS_MIN = 0.004;
    var KAL_SCHWELLE_ABS_MAX = 0.08;
    {funktion}
    var ergebnisse = {{
      mittelwert: kalSchwelle(0.01, 0.09),      // sqrt(0.0009) = 0.03
      unterer_deckel: kalSchwelle(0.0001, 0.0002), // sqrt(2e-8) ~ 0.00014 < 0.004
      oberer_deckel: kalSchwelle(1, 1)             // sqrt(1) = 1 > 0.08
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert abs(ergebnisse["mittelwert"] - 0.03) < 1e-9
    assert ergebnisse["unterer_deckel"] == pytest.approx(0.004)
    assert ergebnisse["oberer_deckel"] == pytest.approx(0.08)


def test_kalmedian_und_kalperzentil_live_in_node(tmp_path):
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(js, "function kalMedian", "function kalibrierungCacheLesen")
    quelltext = f"""
    {funktion}
    var ergebnisse = {{
      median_ungerade: kalMedian([0.3, 0.1, 0.2]),
      median_gerade: kalMedian([0.1, 0.2, 0.3, 0.4]),
      median_leer: kalMedian([]),
      perzentil_80: kalPerzentil([1, 2, 3, 4, 5], 0.8)
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse["median_ungerade"] == pytest.approx(0.2)
    assert ergebnisse["median_gerade"] == pytest.approx(0.25)
    assert ergebnisse["median_leer"] == 0
    assert ergebnisse["perzentil_80"] == 5


def test_kalberechnebodenundschwelle_lebt_calibrated_ceiling_live_in_node(tmp_path):
    """2d: ist ``sitzung.vadSchwelleFix`` gesetzt, ist er die Decke, und der
    Boden-Deckel ist ``vadBodenMess * 2`` statt ``RMS_SCHWELLE * 10`` -- der
    rollende Boden darf die Schwelle nur nach UNTEN ziehen (bis zum
    absoluten Minimum 0.004), nie darueber."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(
        js, "function kalBerechneBodenUndSchwelle", "function pegelAn",
    )
    quelltext = f"""
    var KAL_SCHWELLE_ABS_MIN = 0.004;
    {funktion}
    var sortiert = [0.001, 0.002, 0.2];   // 10%-Perzentil: sortiert[0] = 0.001
    var kalibriert = {{ vadSchwelleFix: 0.05, vadBodenMess: 0.01 }};
    var unkalibriert = {{}};
    var ergebnisse = {{
      kalibriert: kalBerechneBodenUndSchwelle(sortiert, kalibriert, 0.01, 2.5, 10),
      unkalibriert: kalBerechneBodenUndSchwelle(sortiert, unkalibriert, 0.01, 2.5, 10),
      deckel_bindet: kalBerechneBodenUndSchwelle(
        [0.05, 0.06, 0.07], {{ vadSchwelleFix: 0.05, vadBodenMess: 0.01 }}, 0.01, 2.5, 10
      )
    }};
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    # unkalibriert: exakt die alte Formel (RMS_SCHWELLE=0.01, BODEN_FAKTOR=2.5,
    # BODEN_DECKEL_FAKTOR=10): boden = min(0.001, 0.1) = 0.001,
    # schwelle = max(0.01, 0.001*2.5) = 0.01.
    assert ergebnisse["unkalibriert"]["boden"] == pytest.approx(0.001)
    assert ergebnisse["unkalibriert"]["schwelle"] == pytest.approx(0.01)
    # kalibriert: bodenDeckel = 0.01*2 = 0.02, boden = min(0.001, 0.02) = 0.001,
    # schwelle = min(0.05, max(0.004, 0.001*2.5)) = min(0.05, 0.004) = 0.004.
    assert ergebnisse["kalibriert"]["boden"] == pytest.approx(0.001)
    assert ergebnisse["kalibriert"]["schwelle"] == pytest.approx(0.004)
    # deckel_bindet: der rollende Boden (10%-Perzentil 0.05) liegt UEBER dem
    # Kalibrierungs-Deckel (0.01*2=0.02) -- der Deckel zieht ihn nach unten
    # auf 0.02, schwelle = min(0.05, max(0.004, 0.02*2.5=0.05)) = 0.05.
    assert ergebnisse["deckel_bindet"]["boden"] == pytest.approx(0.02)
    assert ergebnisse["deckel_bindet"]["schwelle"] == pytest.approx(0.05)


def test_pegelan_ruft_die_kalibrierte_formel_auf():
    js = web_chat._CHAT_JS
    pegel_an = js[js.index("function pegelAn"):js.index("function formatiereUhr")]
    assert "kalBerechneBodenUndSchwelle(" in pegel_an


def test_herumreichen_erinnerung_zeigt_sich_nur_beim_ersten_mal_live_in_node(tmp_path):
    """Item (f): der Hinweis erscheint genau einmal je JS-Sitzungsobjekt --
    ein zweiter Aufruf derselben Funktion auf DERSELBEN Sitzung (Pause/
    Weiter ruft kalEntscheideOderStarte erneut auf) darf ihn nicht
    wiederholen."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(
        js, "function kalZeigeHerumreichenErinnerungWennNeu",
        "function kalEntscheideOderStarte",
    )
    quelltext = f"""
    var TEXT = {{ kal_herumreichen_erinnerung: 'Hinweis-Text' }};
    function baueFeld() {{
      return {{ hidden: true, textContent: '', _versteckAufrufe: 0,
        set hiddenGesetzt(w) {{ this.hidden = w; }} }};
    }}
    var kalErinnerungFeld = baueFeld();
    var zustand = {{ kalibrierungModus: 'herumreichen' }};
    var zeitueberschreitungen = [];
    function setTimeout(fn, ms) {{ zeitueberschreitungen.push(ms); }}
    {funktion}

    var sitzungA = {{}};
    kalZeigeHerumreichenErinnerungWennNeu(sitzungA);
    var ergebnis1 = {{
      sichtbar_erstes_mal: kalErinnerungFeld.hidden === false,
      text_erstes_mal: kalErinnerungFeld.textContent
    }};
    // Zweiter Aufruf auf DERSELBEN Sitzung (z. B. Pause/Weiter): nichts
    // Neues soll passieren -- also einfach wieder verstecken und pruefen,
    // dass der Aufruf es NICHT wieder sichtbar macht.
    kalErinnerungFeld.hidden = true;
    kalZeigeHerumreichenErinnerungWennNeu(sitzungA);
    var ergebnis2 = {{ sichtbar_zweites_mal: kalErinnerungFeld.hidden === false }};

    // Eine ANDERE Sitzung (neuer Start) zeigt ihn wieder.
    kalErinnerungFeld.hidden = true;
    var sitzungB = {{}};
    kalZeigeHerumreichenErinnerungWennNeu(sitzungB);
    var ergebnis3 = {{ sichtbar_neue_sitzung: kalErinnerungFeld.hidden === false }};

    console.log(JSON.stringify({{ a: ergebnis1, b: ergebnis2, c: ergebnis3 }}));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse["a"]["sichtbar_erstes_mal"] is True
    assert ergebnisse["a"]["text_erstes_mal"] == "Hinweis-Text"
    assert ergebnisse["b"]["sichtbar_zweites_mal"] is False
    assert ergebnisse["c"]["sichtbar_neue_sitzung"] is True


def test_herumreichen_erinnerung_bleibt_ohne_herumreichen_modus_versteckt_live_in_node(tmp_path):
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    funktion = _extrahiere(
        js, "function kalZeigeHerumreichenErinnerungWennNeu",
        "function kalEntscheideOderStarte",
    )
    quelltext = f"""
    var TEXT = {{ kal_herumreichen_erinnerung: 'Hinweis-Text' }};
    var kalErinnerungFeld = {{ hidden: true, textContent: '' }};
    var zustand = {{ kalibrierungModus: null }};
    function setTimeout(fn, ms) {{}}
    {funktion}
    var sitzung = {{}};
    kalZeigeHerumreichenErinnerungWennNeu(sitzung);
    console.log(JSON.stringify({{ versteckt_geblieben: kalErinnerungFeld.hidden === true }}));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnis = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnis["versteckt_geblieben"] is True


def test_kalibrierungsknoepfe_wirken_auch_auf_eine_laufende_diskussion_live_in_node(tmp_path):
    """Regression (03.10.2026 abends, Commit 35dc28f): die neun
    Kalibrierungs-Klick-Handler suchten die aktive Sitzung nur ueber
    ``zustand.aufnahme || zustand.brainstorm`` -- die am selben Tag VORMITTAGS
    eingefuehrte Diskussions-Sitzung (``zustand.diskussion``, Commits 3f4d511/
    f7aaf4e/095e6e9) fehlte in jedem der neun Ausdruecke. Waehrend einer
    laufenden Diskussion war ``zustand.aufnahme`` UND ``zustand.brainstorm``
    beide null/undefined, also rief z. B. der Start-Knopf
    ``kalStarteStille(undefined)`` auf -- die kal*-Funktionen haben ein
    fruehes ``if (!sitzung) return;``-Wächter-Muster und taten nichts, das
    Kalibrierungs-Panel blieb fuer immer offen haengen.

    Dieser Test fuehrt die neun Klick-Handler-Registrierungen WOERTLICH aus
    dem ausgelieferten Skript aus (Zeilen 2323-2367 vor der Behebung) und
    prueft, dass ein Klick bei einer laufenden Diskussion (kein ``aufnahme``,
    kein ``brainstorm``) die zugehoerige kal*-Funktion mit der
    Diskussions-Sitzung aufruft -- nicht mit ``undefined``."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    registrierung = _extrahiere(js, "if (kalStartKnopf) {", "function beginneAufnahme")

    def baue_knopf(name):
        return (
            f"var {name} = {{ _handler: null, "
            f"addEventListener: function (ev, fn) {{ this._handler = fn; }} }};"
        )

    knopf_namen = [
        "kalStartKnopf", "kalSprechenKnopf", "kalNochmalHoerenKnopf",
        "kalVersuchKnopf", "kalWeiterTrotzdemKnopf", "kalJaKnopf",
        "kalNeinKnopf", "kalSkipKnopf", "kalNeuKnopf",
    ]
    aufrufe = {
        "kalStartKnopf": "kalStarteStille",
        "kalSprechenKnopf": "kalStarteSprechen",
        "kalNochmalHoerenKnopf": "kalNochmalHoeren",
        "kalVersuchKnopf": "kalVersuchErneut",
        "kalWeiterTrotzdemKnopf": "kalWeiterTrotzdem",
        "kalJaKnopf": "kalAntwortJa",
        "kalNeinKnopf": "kalAntwortNein",
        "kalSkipKnopf": "kalibrierungSkip",
        "kalNeuKnopf": "kalibrierungNeu",
    }
    knopf_deklarationen = "\n    ".join(baue_knopf(n) for n in knopf_namen)
    stub_deklarationen = "\n    ".join(
        f"var {fn}_aufgerufen_mit = 'UNBERUEHRT';\n"
        f"    function {fn}(sitzung) {{ {fn}_aufgerufen_mit = sitzung; }}"
        for fn in set(aufrufe.values())
    )

    quelltext = f"""
    var diskussionsSitzung = {{ istDiskussion: true }};
    var zustand = {{ aufnahme: null, brainstorm: null, diskussion: diskussionsSitzung }};
    {knopf_deklarationen}
    {stub_deklarationen}
    {registrierung}

    {knopf_namen[0]}._handler();
    {knopf_namen[1]}._handler();
    {knopf_namen[2]}._handler();
    {knopf_namen[3]}._handler();
    {knopf_namen[4]}._handler();
    {knopf_namen[5]}._handler();
    {knopf_namen[6]}._handler();
    {knopf_namen[7]}._handler();
    {knopf_namen[8]}._handler();

    var ergebnisse = {{}};
    ergebnisse.kalStarteStille = kalStarteStille_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalStarteSprechen = kalStarteSprechen_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalNochmalHoeren = kalNochmalHoeren_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalVersuchErneut = kalVersuchErneut_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalWeiterTrotzdem = kalWeiterTrotzdem_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalAntwortJa = kalAntwortJa_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalAntwortNein = kalAntwortNein_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalibrierungSkip = kalibrierungSkip_aufgerufen_mit === diskussionsSitzung;
    ergebnisse.kalibrierungNeu = kalibrierungNeu_aufgerufen_mit === diskussionsSitzung;
    console.log(JSON.stringify(ergebnisse));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse == {name: True for name in aufrufe.values()}


# -- Schwellenmarke auf dem Pegelbalken (Task 3, Kanban-Karte Mithoeren      --
# -- SICHER/Kalibrierung, 03.10.2026): der Balken zeigt seitdem dieselbe     --
# -- RMS-Messung wie der VAD-Schnitt selbst, mit einer duennen Marke an der  --
# -- aktuellen Schwelle. ------------------------------------------------------

def test_pegel_schwelle_marker_steht_im_html(seite):
    assert '<i class="pegel-schwelle">' in seite


def test_pegel_css_zeigt_zwei_farben_getrennt_an_der_marke():
    """Grau unterhalb, eine andere Farbe sobald ``#pegel`` die Klasse
    ``ueber-schwelle`` traegt -- dieselbe von ``pegelAn`` gesetzte Klasse,
    die ``rms > schwelle`` im Takt widerspiegelt."""
    css = web_chat._CSS_CHAT
    assert ".pegel-schwelle" in css
    assert ".pegel.ueber-schwelle span" in css
    balken = re.search(r"\.pegel span\s*\{([^}]*)\}", css)
    ueber = re.search(r"\.pegel\.ueber-schwelle span\s*\{([^}]*)\}", css)
    assert balken and ueber
    assert balken.group(1) != ueber.group(1)


def test_pegeltakt_verwendet_keine_frequenzdaten_mehr():
    """Vorher zeigte der Balken ein Frequenzmittel (``getByteFrequencyData``
    ``* 2.2``) -- eine andere Zahl als die RMS-Schwelle, die den Schnitt
    steuert. Mutant: eine Rueckkehr zu ``getByteFrequencyData`` im Takt soll
    diesen Test ROT machen."""
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval"):]
    takt = takt[:takt.index("}, 120)")]
    assert "getByteFrequencyData" not in takt
    assert "frequenzWerte" not in takt
    assert "getFloatTimeDomainData" in takt


def test_pegeltakt_setzt_breite_marke_und_farbzustand_aus_derselben_rms():
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval"):]
    takt = takt[:takt.index("}, 120)")]
    assert "pegelBalken.style.width" in takt
    assert "(rms / PEGEL_MAX_RMS) * 100" in takt
    assert "pegelSchwelle.style.left" in takt
    assert "(schwelle / PEGEL_MAX_RMS) * 100" in takt
    assert "classList.toggle('ueber-schwelle', rms > schwelle)" in takt
    # Breite UND Marke stehen erst, nachdem ``schwelle`` aus der kalibrierten
    # Formel berechnet wurde -- sonst zeigte die Marke die Schwelle des
    # VORIGEN Takts.
    assert takt.index("berechnet.schwelle") < takt.index("pegelSchwelle.style.left")


def test_pegeltakt_zeichnet_breite_marke_und_farbzustand_live_in_node(tmp_path):
    """Laeuft den tatsaechlichen Rumpf des Pegeltakts (woertlich aus
    ``_CHAT_JS`` extrahiert, nicht nachgebaut) mit einer gefaelschten
    Zeitdomaenen-Messung und einer gefaelschten, festen Schwelle -- und
    prueft, dass Breite, Markenposition und Farbzustand auf derselben
    ``PEGEL_MAX_RMS``-Skala herauskommen."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval(function () {"):]
    takt = takt[:takt.index("}, 120)")]
    rumpf = takt[takt.index("{") + 1:]
    quelltext = f"""
    var PEGEL_MAX_RMS = 0.3;
    var BODEN_FENSTER = 10;
    var RMS_SCHWELLE = 0.01, BODEN_FAKTOR = 2.5, BODEN_DECKEL_FAKTOR = 10;
    var MAX_MS = 90000, PAUSE_MS = 2500, MIN_SPEECH_MS = 500;
    var __schwelleWert = 0;
    function kalBerechneBodenUndSchwelle() {{
      return {{ boden: 0, schwelle: __schwelleWert }};
    }}
    function schneideSegment() {{}}
    var __rmsWert = 0;
    var zeitWerte = {{ length: 1 }};
    var messer = {{ getFloatTimeDomainData: function (arr) {{ arr[0] = __rmsWert; }} }};
    var pegelBalken = {{ style: {{}} }};
    var pegelSchwelle = {{ style: {{}} }};
    var __ueberSchwelle = null;
    var pegelFeld = {{
      classList: {{ toggle: function (name, wert) {{ __ueberSchwelle = wert; }} }}
    }};
    var sitzung = {{ vadBoden: [], recorder: null }};

    function taktFn() {{
    {rumpf}
    }}

    function pruefe(rmsWert, schwelleWert) {{
      __rmsWert = rmsWert;
      __schwelleWert = schwelleWert;
      __ueberSchwelle = null;
      taktFn();
      return {{
        breite: parseFloat(pegelBalken.style.width),
        links: parseFloat(pegelSchwelle.style.left),
        ueber: __ueberSchwelle
      }};
    }}
    console.log(JSON.stringify({{
      halb: pruefe(0.15, 0.1),
      leise: pruefe(0.03, 0.1),
      gedeckelt: pruefe(0.5, 0.1)
    }}));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    # halb: rms=0.15 -> 50% Breite; schwelle=0.1 -> 33.33% Markenposition;
    # 0.15 > 0.1 -> ueber-schwelle.
    assert ergebnisse["halb"]["breite"] == pytest.approx(50.0)
    assert ergebnisse["halb"]["links"] == pytest.approx(100 / 3)
    assert ergebnisse["halb"]["ueber"] is True
    # leise: rms=0.03 -> 10% Breite, noch unter derselben Schwelle.
    assert ergebnisse["leise"]["breite"] == pytest.approx(10.0)
    assert ergebnisse["leise"]["links"] == pytest.approx(100 / 3)
    assert ergebnisse["leise"]["ueber"] is False
    # gedeckelt: rms=0.5 -> ueber 100% der Skala, auf 100 geklemmt.
    assert ergebnisse["gedeckelt"]["breite"] == pytest.approx(100.0)
    assert ergebnisse["gedeckelt"]["ueber"] is True


# -- Einmaliger Mitschnitt-Hinweis nach dem ersten Segment (Task 4, Kanban- --
# -- Karte Mithoeren SICHER, 03.10.2026): "Check the transcript in the chat --
# -- -- if words are missing, move the phone closer." Einmal je Sitzung,    --
# -- nicht je Segment, nicht fuer immer auf dem Geraet -- deshalb ein       --
# -- reines sitzung-Feld (sitzung.hinweisGezeigt), kein localStorage. Nicht --
# -- zu verwechseln mit Task 2s "Handy herumreichen"-Erinnerung             --
# -- (kalErinnerungFeld/zustand.kalibrierungModus): zwei unabhaengige       --
# -- Mechanismen mit unterschiedlichem Ausloeser. ----------------------------

def test_mitlauf_hinweis_element_steht_in_der_seite(seite):
    assert 'class="mitlauf-hinweis"' in seite
    assert 'id="mitlauf-hinweis"' in seite
    assert 'role="status"' in seite
    # Direkt neben #fehler im Markup, wie der Auftrag es verlangt.
    ausschnitt = seite[seite.index('id="fehler"') - 40:seite.index('id="fehler"') + 400]
    assert "mitlauf-hinweis" in ausschnitt


def test_mitlauf_hinweis_text_steht_in_js_texte_und_ist_eigenstaendig():
    assert web_chat._JS_TEXTE["mitlauf_hinweis"] == web_chat._TEXT_MITLAUF_HINWEIS
    # Eigenstaendig: kein Wiederverwenden von Task 2s Herumreichen-Text.
    assert web_chat._TEXT_MITLAUF_HINWEIS != web_chat._TEXT_KALIBRIERUNG_HERUMREICHEN_ERINNERUNG


def test_onstop_zeigt_den_mitlauf_hinweis_einmal_je_sitzung_nach_dem_ersten_segment():
    """Die Bewachung steht NACH dem ``if (teile.length && ...)``-Block (das
    erste fertige Segment dieser Sitzung), schaltet den Merkposten auf
    ``true`` und zeigt den Hinweistext -- unabhaengig davon, ob genau DIESES
    Segment hochgeladen wird."""
    js = web_chat._CHAT_JS
    onstop = js[js.index("r.onstop = function"):js.index("r.start();")]
    gate_index = onstop.index("if (teile.length")
    guard_index = onstop.index("if (!sitzung.hinweisGezeigt)")
    fertige_index = onstop.index("sitzung.fertige[nr] = auftrag;")
    assert gate_index < guard_index < fertige_index
    guard = onstop[guard_index:fertige_index]
    assert "sitzung.hinweisGezeigt = true;" in guard
    assert "mitlaufHinweisFeld.textContent = TEXT.mitlauf_hinweis;" in guard
    assert "mitlaufHinweisFeld.hidden = false;" in guard


def test_anzeigeaus_versteckt_den_mitlauf_hinweis():
    js = web_chat._CHAT_JS
    anzeige_aus = js[js.index("function anzeigeAus"):js.index("function modusAn")]
    assert "mitlaufHinweisFeld.hidden = true;" in anzeige_aus


def test_frische_sitzungen_bekommen_einen_eigenen_hinweisgezeigt_merkposten():
    """Ein neuer Interview- oder Brainstorm-Start (und das Wiederanmelden
    nach einem Reload waehrend ein anderes Telefon schon aufnimmt) legt ein
    FRISCHES Sitzungsobjekt an -- jedes bekommt ``hinweisGezeigt: false``,
    kein Uebertrag von einer frueheren Sitzung."""
    js = web_chat._CHAT_JS
    start_interview = js[js.index("function starteInterview"):js.index("var wechsel = { ziel: true")]
    assert "hinweisGezeigt: false" in start_interview
    start_brainstorm = js[js.index("function starteBrainstorm"):js.index("zustand.brainstorm = sitzung;")]
    assert "hinweisGezeigt: false" in start_brainstorm
    fortsetzen = js[js.index("sitzung = {\n        strom: null"):]
    fortsetzen = fortsetzen[:fortsetzen.index("zustand.aufnahme = sitzung;   // synchron")]
    assert "hinweisGezeigt: false" in fortsetzen


def test_mitlauf_hinweis_guard_zeigt_sich_nur_beim_ersten_segment_live_in_node(tmp_path):
    """Fuehrt die woertlich extrahierte Bewachung aus ``onstop`` aus: erster
    Aufruf auf einer frischen Sitzung zeigt den Hinweis, ein zweiter Aufruf
    auf DERSELBEN Sitzung (zweites Segment) zeigt ihn nicht erneut, und eine
    ANDERE (neue) Sitzung bekommt ihn wieder."""
    node = _node_oder_skip()
    js = web_chat._CHAT_JS
    guard = _extrahiere(
        js, "if (!sitzung.hinweisGezeigt)", "sitzung.fertige[nr] = auftrag;",
    )
    quelltext = f"""
    var TEXT = {{ mitlauf_hinweis: 'Hinweis-Text' }};
    function baueFeld() {{ return {{ hidden: true, textContent: '' }}; }}
    var mitlaufHinweisFeld = baueFeld();
    function pruefeHinweis(sitzung) {{
      {guard}
    }}

    var sitzungA = {{ hinweisGezeigt: false }};
    pruefeHinweis(sitzungA);
    var ergebnis1 = {{
      sichtbar_erstes_mal: mitlaufHinweisFeld.hidden === false,
      text_erstes_mal: mitlaufHinweisFeld.textContent,
      merkposten_erstes_mal: sitzungA.hinweisGezeigt
    }};

    mitlaufHinweisFeld.hidden = true;
    mitlaufHinweisFeld.textContent = '';
    pruefeHinweis(sitzungA);
    var ergebnis2 = {{ sichtbar_zweites_mal: mitlaufHinweisFeld.hidden === false }};

    var sitzungB = {{ hinweisGezeigt: false }};
    pruefeHinweis(sitzungB);
    var ergebnis3 = {{ sichtbar_neue_sitzung: mitlaufHinweisFeld.hidden === false }};

    console.log(JSON.stringify({{ a: ergebnis1, b: ergebnis2, c: ergebnis3 }}));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnisse = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnisse["a"]["sichtbar_erstes_mal"] is True
    assert ergebnisse["a"]["text_erstes_mal"] == "Hinweis-Text"
    assert ergebnisse["a"]["merkposten_erstes_mal"] is True
    assert ergebnisse["b"]["sichtbar_zweites_mal"] is False
    assert ergebnisse["c"]["sichtbar_neue_sitzung"] is True

"""Der Serververtrag des Chat-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_chat_e2e.py``: der
Recorder, die Segmente, PTT, die Warteschlange. Hier steht, was man am HTML
messen kann -- und das ist mehr, als es klingt: jede Zahl, die das JS braucht,
und jeder Endpunkt, den es ruft.
"""

import re
import threading
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web, web_chat

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


def test_der_nonce_steht_im_body_und_nicht_daran(seite):
    """Dieselbe Entscheidung wie auf der Gruppenseite (``web.nonce``):
    abgeleitet, nicht gewuerfelt, und IM body -- sonst reisst ein
    Fensterwechsel jedes offene Eingabefeld mit."""
    assert re.search(r'<input type="hidden" id="nonce" value="\d+\.[0-9a-f]{32}">', seite)


def test_das_js_ruft_nur_endpunkte_die_es_gibt(seite):
    """Jeder ``fetch``-Pfad im JS muss in ``_POSTWEGE`` oder unter den
    GET-Wegen stehen. Ein Tippfehler waere im Browser ein stilles 404."""
    pfade = set(re.findall(r"chat/([a-z]+)", web_chat._CHAT_JS))
    erlaubt = set(web_chat._POSTWEGE) | {"zustand", "datei"}
    assert pfade <= erlaubt, pfade - erlaubt


def test_das_js_nennt_jeden_postweg(seite):
    """Die andere Richtung: ein Endpunkt ohne Aufrufer im JS ist entweder
    toter Code oder ein vergessener Knopf."""
    for weg in web_chat._POSTWEGE:
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
    assert js.count("beginneAufnahme(sitzung);") == 2   # starteInterview + fortsetzeInterview
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

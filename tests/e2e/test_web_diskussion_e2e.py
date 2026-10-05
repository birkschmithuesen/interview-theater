"""Phase 1, Hintergrund-Diskussion -- der volle Ablauf im echten Browser,
gegen den echten Bot (Task 10, Padua Phase 1+2 Umbau).

Zwei Haerten, die keiner der bestehenden e2e-Laeufe allein abdeckt, werden
hier zusammengefuehrt:

* ``tests/e2e/test_web_chat_e2e.py`` faehrt einen echten Browser (Chromium,
  ``--use-fake-device-for-media-stream``, echter ``MediaRecorder``) gegen
  einen echten Webserver -- aber OHNE echten Bot: die dortige
  ``BotAttrappe`` liest nur ``/interview``/``/fertig`` aus ``web_post`` und
  schaltet ``repo.setze_interviewmodus``. Fuer die Diskussion reicht das
  nicht: die Begruessung (``kontext.ERSTKONTAKT_DISKUSSION``), das
  Abschlusswort (``aufnahme._TEXT_DISKUSSION_KEINE_BEGRIFFE``) und der
  Verdichtungslauf (``diskussion.starte``) entstehen erst im echten
  ``aufnahme``-/``ablauf``-Code.
* ``tests/test_web_e2e_http.py`` faehrt genau diesen echten Code --
  ``bot.schleife`` und ``web.baue_server`` je in einem Thread desselben
  Prozesses, mit einer ``LLMAttrappe`` (keyed auf ``art``) und einer
  gefaelschten Whisper-Gegenstelle (``httpx.MockTransport``, zweistufiges
  Protokoll wie beim echten Anbieter, Falle 2 aus AGENTS.md) -- aber nur
  ueber ``urllib``, kein Browser, kein ``MediaRecorder``.

Dieser Lauf kombiniert beides: die Browser-Fixtures des ersten Laufs
(``browser``, ``_MESSUNG``, das Handy-Setup) mit dem Thread-Aufbau des
zweiten (``web.baue_server`` + ``bot.schleife`` im selben Prozess). Weil
beide Server-Threads statt eines Subprozesses laufen, reicht
``monkeypatch.setenv("IT_WORKSHOP", "padua-2026")`` VOR dem Start: ``workshop.aktiv()``
liest ``IT_WORKSHOP`` bei jedem Aufruf frisch aus ``os.environ`` (siehe
``interview_theater/workshop.py``, ``aktiv()``), und beide Threads teilen
sich das ``os.environ`` des Testprozesses -- anders als beim
Subprozess-Webserver in ``test_web_chat_e2e.py``, der eine eigene
Umgebung braucht.

Geprueft wird NICHT, ob das echte Sprachmodell etwas Sinnvolles begruesst --
das uebernimmt ``scripts/pruefe_prompts.py``/die Simulation. Geprueft wird
die PLOMBIERUNG: dass bei aktivem Profil ``padua-2026``
(``workshop.diskussion_aktiv()``) der "Start listening"-Knopf erscheint,
ein Diskussionssegment als blosse Echo-Blase der GRUPPE landet (keine
Gespraechsantwort, keine CoThinker-Karte), und erst der Klick auf
"Discussion done" die deterministische Fuenf-Begriffe-Aufforderung
ausloest.

**Wichtiger, per Probelauf gefundener Befund (siehe Taskreport):** ``padua-2026``
laeuft auf ENGLISCH (``workshop/padua-2026/profil.toml``, ``[sprache] code =
"en"``) -- Birk, 29.09.2026: "Padua laeuft auf Englisch". Jeder sichtbare
Text (Knopfbeschriftung, die deterministische Fuenf-Begriffe-Zeile, der
Erstkontakt-Prompt-Baustein) kommt deshalb aus
``interview_theater/sprachen/en/texte.toml`` statt aus der deutschen
Python-Konstante -- zur Aufrufzeit ueber ``sprache.Texte``
(``aufnahme.T._TEXT_X`` statt ``aufnahme._TEXT_X``, siehe
``interview_theater/sprache.py::Texte.__getattr__``). Dieser Lauf liest die
erwarteten Texte deshalb ausschliesslich ueber ``aufnahme.T``/``web_chat.T``
und niemals als eigenes hartkodiertes Deutsch -- sonst pruefen wir gegen
Text, der im aktiven Profil nie gesendet wird (am eigenen Leib erlebt: ein
erster Entwurf dieser Datei pruefte auf "Zuhoeren starten"/"Diskussion
fertig" und schlug mit der tatsaechlichen Antwort "Start listening"/
"Discussion done" fehl, siehe Taskreport).

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_diskussion_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

import httpx  # noqa: E402

from interview_theater import (  # noqa: E402
    aufnahme, begriffsboard, bot, db, einstellungen, knoepfe, repo, web, web_chat,
    web_kanal, workshop,
)

CHAT = 7_000_000_000_002  # eigene chat_id -- nie dieselbe wie test_web_e2e_http.py
SCHLUESSEL = b"y" * 32
GEDULD_S = 30.0
SCHRITT_S = 0.1

#: Hart gedeckelt, kurz: Chromiums synthetischer Ton
#: (--use-fake-device-for-media-stream) ist ein DAUERTON -- der Pausen-Schnitt
#: (VAD) sieht also nie eine Pause (siehe _MESSUNG unten, T.rms = 0.6, "deutlich
#: ueber jeder Schwelle"). Segmente entstehen hier ausschliesslich ueber den
#: harten Zeitdeckel IT_WEB_VAD_MAX_MS -- derselbe Kniff wie in
#: tests/e2e/test_web_chat_e2e.py's ``server``-Fixture.
VAD_MAX_MS = 1200

#: Der von der gefaelschten Whisper-Gegenstelle gelieferte Text -- erfunden,
#: eindeutig genug, um ihn in der Blase wiederzuerkennen.
TRANSKRIPT = "Wir erzaehlen uns gerade, wie es war, als wir hier ankamen."

#: Die Begruessung, die unsere LLM-Attrappe liefert, SOBALD der Nutzertext
#: (``koerper`` aus ``kontext.baue``) das Diskussions-Erstkontaktprompt
#: traegt (``kontext.ERSTKONTAKT_DISKUSSION``). Der Marker "Discussion done"
#: steht wortgleich NUR in diesem Prompt-Block (gegen die echte, laufende
#: ``padua-2026``-Sprache gemessen -- siehe Dateikopf: das Profil laeuft auf
#: ENGLISCH, ``interview_theater/sprachen/en/texte.toml``, nicht auf der
#: deutschen Python-Konstante) -- kein Treffer durch Zufall. Die kanonische
#: Formulierung nennt den Knopf "Start listening"
#: (``web_chat.T._TEXT_DISKUSSION_AN``) und NICHT die fuenf Begriffe --
#: genau das pruefen die Tests unten.
GRUSS_DISKUSSION = (
    "Hello! Great to have you here. I'm the bot for your theatre project: "
    "your terms become questions, the questions become interviews, and the "
    "interviews become the play. I read everything here and answer it. Now "
    "put your phone in the middle and talk freely about which terms matter "
    "to you -- I will just listen and say nothing until you are done. Press "
    "\"Start listening\" below when you are ready, and \"Discussion done\" "
    "once you are finished."
)

#: Fuer jeden anderen Nutzertext -- es sollte hier keinen geben, denn
#: zwischen dem Erstkontakt und dem Klick auf "Discussion done" loest kein
#: Diskussionssegment einen Gespraechszug aus (aufnahme._diskussion_
#: abschliessen ruft weder ``zug`` noch den Erkenner). Taucht dieser Text
#: trotzdem auf, ist das ein Befund: irgendwo lief doch ein Gespraechszug.
_UNERWARTET = "UNERWARTETER GESPRAECHSZUG"


class LLMAttrappe:
    """Wie ``tests/test_web_e2e_http.py::LLMAttrappe`` -- nach ``art``
    verzweigt, der Gespraechszug nach einem Teilstring im Nutzertext. Hier um
    eine Regel fuer die Diskussions-Begruessung ergaenzt und um den
    Verdichtungslauf der Diskussion (``art='diskussion_verdichtung'``,
    ``interview_theater.diskussion.SCHEMA``)."""

    def __init__(self):
        self.nutzertexte = []
        self.diskussion_verdichtet = 0
        self.board = []
        self._sperre = threading.Lock()

    def _gespraech(self, nutzer: str) -> str:
        if "Discussion done" in nutzer:
            return GRUSS_DISKUSSION
        return _UNERWARTET

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            # Diskussionssegmente rufen den Erkenner gar nicht erst auf
            # (aufnahme._diskussion_abschliessen) -- diese Regel greift also
            # hoechstens fuer die allererste Textnachricht ("Hallo ...").
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        if art == "begriffsboard":
            # Karte t_4517d4ad: der Boardlauf -- ``self.board`` setzt der
            # jeweilige Test; leer heisst: der heutige Satz bleibt.
            return {"board": list(self.board)}
        if art == "diskussion_verdichtung":
            with self._sperre:
                self.diskussion_verdichtet += 1
            # "NICHTS" ist der vorgesehene Sentinel fuer "nichts Brauchbares"
            # (interview_theater.diskussion._LEER) -- kein Zitat zu pruefen,
            # kein Fehlerpfad.
            return {"antwort": "NICHTS"}
        with self._sperre:
            self.nutzertexte.append(nutzer)
        return {"antwort": self._gespraech(nutzer)}


def stt_attrappe(text: str) -> httpx.Client:
    """Wie ``tests/test_web_e2e_http.py::stt_attrappe``: Upload liefert eine
    batch_id, die erste Abfrage ist fertig. ``data`` ist ein JSON-STRING
    (Falle 2), genau wie beim echten Anbieter."""

    def handler(anfrage):
        if "audio/transcriptions" in anfrage.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


class _Halt(Exception):
    """Beendet ``bot.schleife`` von aussen (wie in ``test_web_e2e_http.py``)."""


class _HaltbarerKanal(web_kanal.WebKanal):
    """``WebKanal`` mit Ausschalter -- der Long-Poll wartet hoechstens eine
    halbe Sekunde je Runde, damit das Testende nicht auf einen laufenden
    Poll wartet."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.halt = threading.Event()

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        if self.halt.is_set():
            raise _Halt()
        return super().hole_updates(offset, timeout=min(timeout, 0.5))


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Webserver und Bot-Schleife, beide im Thread, auf einer Wegwerf-DB --
    UND ``IT_WORKSHOP=padua-2026``, damit ``workshop.diskussion_aktiv()``
    ueber den ganzen Lauf ``True`` bleibt (beide Threads laufen im selben
    Prozess wie dieser Test und teilen sich ``os.environ``, siehe Dateikopf).

    ``workshop.vergiss()`` vor UND nach dem Lauf: reine Vorsicht, falls ein
    anderer Test im selben Prozess schon ein Profil geladen und
    zwischengespeichert hat (``workshop._GELADEN`` ist nach Profilnamen
    geschluesselt, aber ein frischer Zwischenspeicher ist billiger als eine
    Vermutung)."""
    vorher = set(threading.enumerate())
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", str(VAD_MAX_MS))
    # Fallback fuer den Fall, dass pegelAn() im Browser doch einmal fehlschlaegt
    # (kein AudioContext) -- dann greift die feste Segmentlaenge statt der VAD.
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", str(VAD_MAX_MS))
    # Seit "Mithoeren SICHER" (35dc28f, nach dieser Datei gemerged) haengt vor
    # dem ersten echten Schnitt ein Kalibrierungs-Dialog (kalEntscheideOderStarte()
    # faehrt sonst auf #kalibrierung-* statt auf kalStarteEchteSchnitte()) --
    # diese Datei prueft die Diskussion/das Begriffsboard, nicht die
    # Kalibrierung (die hat tests/e2e/test_web_chat_kalibrierung_e2e.py), genau
    # wie test_web_chat_e2e.py::server es fuer seinen Lauf abschaltet.
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")

    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-diskussion", "Die Zuhoerenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    # web_daten.web_chatzustand's diskussion_knopf gate is a STRICT
    # ``phase == 1`` check (no ERSTE-fallback like interview_knopf has) --
    # a fresh group's arbeitsstand.phase is NULL until explicitly set, so
    # without this the button stays hidden for the whole test
    # (tests/test_web_daten_diskussion_knopf.py::test_ohne_arbeitsstand_ergibt_falsch,
    # review finding on this task).
    repo.setze_phase(aufbau, CHAT, 1)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe-diskussion", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test",
        stt_produkt="PRODUKT-ID", web_url="", kanal=einstellungen.KANAL_WEB,
        web_chat_id=CHAT,
    )
    klm = LLMAttrappe()
    kanal = _HaltbarerKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=bot.POOL_GROESSE)
    stt = stt_attrappe(TRANSKRIPT)

    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, stt, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token, pfad, klm

    kanal.halt.set()
    bot_faden.join(timeout=GEDULD_S)
    pool.shutdown(wait=True, cancel_futures=True)
    dienst.shutdown()
    dienst.server_close()
    web_faden.join(timeout=GEDULD_S)
    frist = time.monotonic() + GEDULD_S
    for faden in set(threading.enumerate()) - vorher:
        if faden is not threading.current_thread():
            faden.join(timeout=max(0.0, frist - time.monotonic()))
    stt.close()
    bot_conn.close()
    workshop.vergiss()
    assert not bot_faden.is_alive(), "bot.schleife ist nicht beendet"


# -- Browser-Fixtures, aus tests/e2e/test_web_chat_e2e.py uebernommen -------
#
# _MESSUNG unveraendert kopiert (nicht importiert -- test_web_chat_e2e.py
# bleibt read-only): die RMS-Ueberschreibung auf einen konstanten, lauten Pegel
# (T.rms = 0.6) ist genau das, was den Pausen-Schnitt (VAD) hier ausschaltet
# und damit IT_WEB_VAD_MAX_MS zum einzigen Schnittgrund macht.

_MESSUNG = r"""
(function () {
  var T = window.__t = {
    starts: 0, groessen: {}, stroeme: [], kontexte: [],
    stopVerzoegerung: {}, stopVerzoegerungAlle: 0,
    gumVerzoegerung: 0, halteAudio: false, gehalten: [], posts: []
  };

  var EchterRecorder = window.MediaRecorder;
  if (EchterRecorder) {
    var Attrappe = function (strom, optionen) {
      var r = optionen ? new EchterRecorder(strom, optionen) : new EchterRecorder(strom);
      var selbst = this;
      var index = null;
      this.ondataavailable = null;
      this.onstop = null;
      r.addEventListener('dataavailable', function (ev) {
        if (index !== null) {
          T.groessen[index] = (T.groessen[index] || 0) + (ev.data ? ev.data.size : 0);
        }
        if (selbst.ondataavailable) { selbst.ondataavailable(ev); }
      });
      r.addEventListener('stop', function (ev) {
        var ms = T.stopVerzoegerung[index] || T.stopVerzoegerungAlle || 0;
        var feuere = function () { if (selbst.onstop) { selbst.onstop(ev); } };
        if (ms) { setTimeout(feuere, ms); } else { feuere(); }
      });
      this.start = function () { index = T.starts; T.starts += 1; return r.start(); };
      this.stop = function () { return r.stop(); };
      Object.defineProperty(this, 'state', { get: function () { return r.state; } });
      Object.defineProperty(this, 'mimeType', { get: function () { return r.mimeType; } });
    };
    window.MediaRecorder = Attrappe;
  }

  var geraete = navigator.mediaDevices;
  if (geraete && geraete.getUserMedia) {
    var echtGum = geraete.getUserMedia.bind(geraete);
    geraete.getUserMedia = function (vorgabe) {
      return echtGum(vorgabe).then(function (strom) {
        T.stroeme.push(strom);
        var ms = T.gumVerzoegerung;
        if (!ms) { return strom; }
        return new Promise(function (ja) { setTimeout(function () { ja(strom); }, ms); });
      });
    };
  }

  T.rms = 0.6;
  T.setzeRms = function (wert) { T.rms = wert; };
  var EchterKontext = window.AudioContext;
  if (EchterKontext) {
    window.AudioContext = function () {
      var k = new EchterKontext();
      T.kontexte.push(k);
      var echtesCreateAnalyser = k.createAnalyser.bind(k);
      k.createAnalyser = function () {
        var messer = echtesCreateAnalyser();
        messer.getByteFrequencyData = function (werte) {
          var wert = Math.max(0, Math.min(255, Math.round(T.rms * 255)));
          for (var i = 0; i < werte.length; i++) { werte[i] = wert; }
        };
        messer.getFloatTimeDomainData = function (werte) {
          for (var i = 0; i < werte.length; i++) { werte[i] = T.rms; }
        };
        return messer;
      };
      return k;
    };
  }

  var echtFetch = window.fetch.bind(window);
  window.fetch = function (url, optionen) {
    var u = String(url);
    if (optionen && optionen.method === 'POST') {
      var pfad = u.split('?')[0];
      var eintrag = { pfad: pfad.slice(pfad.lastIndexOf('/chat/') + 6) };
      if (typeof optionen.body === 'string') {
        try { eintrag.an = JSON.parse(optionen.body).an; } catch (e) { /* egal */ }
      } else if (optionen.body && optionen.body.size !== undefined) {
        eintrag.groesse = optionen.body.size;
      }
      T.posts.push(eintrag);
      if (eintrag.pfad === 'audio' && T.halteAudio) {
        return new Promise(function (ja) {
          T.gehalten.push(function (status) {
            ja(new Response('festgehalten', { status: status }));
          });
        });
      }
    }
    return echtFetch(url, optionen);
  };
})();
"""

HANDY = {"width": 390, "height": 844}
GEDULD_MS = 20000


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


@pytest.fixture
def seite(lauf, browser):
    basis, token, _pfad, _klm = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"],
        base_url=basis, is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD_MS)
    blatt.goto(f"{basis}/g/{token}/chat")
    yield blatt
    kontext.close()


# -- der volle Ablauf -------------------------------------------------------


def test_diskussion_voller_ablauf_im_browser(lauf, seite):
    """Padua Phase 1+2, Task 10: Begruessung nennt die Diskussion (nicht die
    fuenf Begriffe) -> "Start listening" -> ein Segment landet als blosse
    Echo-Blase der GRUPPE (keine Bot-Antwort dazwischen) -> "Discussion
    done" -> die deterministische Fuenf-Begriffe-Aufforderung erscheint.

    Alle sichtbaren Texte werden ERST HIER, innerhalb der Testfunktion (nach
    dem ``monkeypatch.setenv`` der ``lauf``-Fixture), ueber ``aufnahme.T``/
    ``web_chat.T`` gelesen -- NICHT als Modul-Konstante
    (``aufnahme._TEXT_X``): ``padua-2026`` laeuft auf Englisch (siehe
    Dateikopf), und nur der ``T``-Weg liest zur Aufrufzeit aus der aktiven
    Sprache (``sprache.Texte.__getattr__``)."""
    _basis, _token, _pfad, klm = lauf
    text_diskussion_an = web_chat.T._TEXT_DISKUSSION_AN
    text_fuenf_begriffe = aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE

    # (1) Die erste Nachricht der Gruppe loest den Erstkontakt aus
    # (ablauf._erfrage_antwort: erstkontakt = not repo.hat_bot_nachricht(...)).
    # Unter Padua traegt der Nutzertext dafuer kontext.ERSTKONTAKT_DISKUSSION
    # statt des klassischen kontext.ERSTKONTAKT -- unsere Attrappe erkennt
    # das am Marker "Discussion done" und antwortet mit GRUSS_DISKUSSION.
    seite.fill("#eingabe", "Hallo, wir sind da!")
    seite.click("#senden")
    expect(seite.locator(".blase.bot").first).to_contain_text(text_diskussion_an)
    # Die Antwort auf "Hallo" abwarten, bevor gezaehlt wird: seit dem
    # versteckten /start (P1-2) steht die feste Begruessung schon beim
    # Seitenaufruf da, die Modellantwort kommt danach.
    expect(seite.locator(".blase.bot").filter(has_text="Great to have you here").first
           ).to_be_visible(timeout=GEDULD_MS)

    # Seit 05.10.2026 (Birk, Live-Test) erklaert die Begruessung die zwei
    # Handys selbst -- der Einstiegssatz aus Karte t_4517d4ad (D10) steht
    # nicht mehr dahinter.
    expect(
        seite.locator(".blase.bot").filter(has_text=begriffsboard.T._TEXT_EINSTIEG)
    ).to_have_count(0)

    # Die Begruessung fragt (noch) nicht nach den fuenf Begriffen -- das ist
    # erst die Aufforderung NACH "Discussion done".
    expect(seite.locator(".verlauf")).not_to_contain_text(text_fuenf_begriffe)

    bot_blasen_vor_start = seite.locator(".blase.bot").count()

    # (2) Der Knopf steht da (Phase 1 + workshop.diskussion_aktiv()).
    expect(seite.locator("#diskussion")).to_be_visible()
    expect(seite.locator("#diskussion")).to_have_text(text_diskussion_an)

    # (3) Start -- Mikrofon wird gewaehrt (fake), der Knopf zeigt "laeuft".
    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")

    # Birk 04.10.2026: nur Start und Fertig -- kein Pause-Knopf mehr.
    expect(seite.locator("#diskussion-aktionen button")).to_have_count(1)
    assert seite.locator("#diskussion-pause").count() == 0

    # (4) Mindestens ein Segment ueberschreitet IT_WEB_VAD_MAX_MS und wird
    # hochgeladen, transkribiert (gefaelschtes Whisper) und als Echo-Blase
    # der Gruppe gespiegelt (aufnahme._diskussion_abschliessen,
    # _web_sprachblase) -- OHNE Gespraechszug, OHNE Erkennerlauf.
    segment_blase = seite.locator(".blase.gruppe.sprache").filter(has_text=TRANSKRIPT)
    expect(segment_blase.first).to_be_visible(timeout=GEDULD_MS)
    # Dieselbe Nachricht darf NICHT zugleich als Bot-Blase auftauchen --
    # ".blase.gruppe" und ".blase.bot" schliessen sich aus (n.von ist genau
    # einer von beiden, siehe web_chat._CHAT_JS::blase()).
    assert seite.locator(".blase.bot").filter(has_text=TRANSKRIPT).count() == 0

    # Waehrenddessen ist KEIN neues Bot-/CoThinker-Message aufgetaucht: ein
    # Diskussionssegment loest weder Gespraechszug noch Absichtserkenner aus
    # (die Zahl der Bot-Blasen bleibt exakt die der Begruessung).
    assert seite.locator(".blase.bot").count() == bot_blasen_vor_start
    assert seite.locator(".blase.bot", has_text=_UNERWARTET).count() == 0

    # (5) "Discussion done": das letzte Segment traegt schnittgrund='ende'
    # (vadAktiv -> _grund = 'ende' in beendeDiskussion()), der Server schickt
    # synchron die Fuenf-Begriffe-Aufforderung und stoesst im Hintergrund den
    # EINEN Verdichtungslauf an (interview_theater.diskussion.starte).
    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")

    # Seit 05.10.2026 laeuft das Board am Ende-Schnitt immer; die Attrappe
    # liefert hier ein leeres Board -> der Rueckfallsatz, nicht mehr
    # "send me your five terms".
    keine_begriffe = seite.locator(".blase.bot").filter(
        has_text=aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE)
    expect(keine_begriffe.first).to_be_visible(timeout=GEDULD_MS)
    assert seite.locator(".blase.bot").filter(has_text=text_fuenf_begriffe).count() == 0

    # Genau EINE neue Bot-Blase ist dazugekommen -- der Rueckfallsatz,
    # keine zweite (kein CoThinker-Vorschlag, keine Rueckfrage).
    assert seite.locator(".blase.bot").count() == bot_blasen_vor_start + 1

    # Der Hintergrund-Verdichtungslauf (interview_theater.diskussion.starte)
    # liegt NICHT auf dem kritischen Pfad dieses Tests -- die Fuenf-Begriffe-
    # Zeile ging schon vorher SYNCHRON raus (aufnahme._diskussion_
    # abschliessen sendet sie, BEVOR diskussion.starte ueberhaupt gerufen
    # wird). Er braucht nur ein nicht-leeres Transkript (kein Woerter-
    # Mindestmass wie beim Interview-Verdichter, siehe diskussion.starte),
    # das haben wir mit TRANSKRIPT sicher. Hier nur gewartet, damit ein
    # etwaiger Fehlschlag (geloggt, nie dem Chat gezeigt) Zeit hat
    # aufzutreten, BEVOR der Lauf endet und die Verbindung schliesst.
    frist = time.monotonic() + 5.0
    while time.monotonic() < frist and klm.diskussion_verdichtet == 0:
        time.sleep(SCHRITT_S)
    # Entscheidend ist nur, dass kein zweiter, unerwarteter Gespraechszug lief:
    assert seite.locator(".blase.bot", has_text=_UNERWARTET).count() == 0


def test_begriffsboard_im_cothinker_und_top5_vorschlag(lauf, seite, monkeypatch):
    """Karte t_4517d4ad: Start -> Segment -> "Discussion done" ->
    regulärer Lauf auf dem Ende-Schnitt
    -> Board-Eintrag im CoThinker-Panel -> Top-5-Vorschlag mit EINEM Knopf
    "Take these". Der Zwischenlauf nach einem Pausenschnitt ist im Browser
    nicht herstellbar (Dauerton, nur ``cap``-Schnitte, siehe Dateikopf) und
    in ``tests/test_begriffsboard_mithoeren.py`` am echten ``aufnahme``-Pfad
    getestet."""
    _basis, _token, _pfad, klm = lauf
    # Seit 05.10.2026 laeuft der Ende-Schnitt bei jedem ungelesenen Rest,
    # unabhaengig von dieser Schwelle (sie bleibt fuer Zwischenlaeufe).
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1")
    klm.board = [{
        "begriff": "ankamen", "nennungen": 2, "zustimmung": 2,
        "begruendung": "Das Ankommen hier verbindet uns.",
        "zitat": "als wir hier ankamen", "doppelbedeutung": "", "status": "favorit",
    }]
    knopf_text = knoepfe.T._TEXT_BOARD_UEBERNEHMEN_KNOPF

    seite.fill("#eingabe", "Hallo, wir sind da!")
    seite.click("#senden")
    expect(seite.locator(".blase.bot").first).to_contain_text(web_chat.T._TEXT_DISKUSSION_AN)
    expect(seite.locator(".blase.bot").filter(has_text="Great to have you here").first
           ).to_be_visible(timeout=GEDULD_MS)

    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")
    segment_blase = seite.locator(".blase.gruppe.sprache").filter(has_text=TRANSKRIPT)
    expect(segment_blase.first).to_be_visible(timeout=GEDULD_MS)

    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")

    # Der Top-5-Vorschlag ersetzt den heutigen Satz und traegt genau einen Knopf.
    vorschlag = seite.locator(".blase.bot").filter(has_text="1. ankamen")
    expect(vorschlag.first).to_be_visible(timeout=GEDULD_MS)
    expect(seite.get_by_role("button", name=knopf_text)).to_have_count(1)
    for satz in (aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE,
                 aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE):
        assert seite.locator(".blase.bot").filter(has_text=satz).count() == 0

    # Der CoThinker-Tab ist in Phase 1 da und zeigt den Board-Eintrag als Top.
    tab = seite.locator('.tabs button[data-tab="buehne"]')
    expect(tab).to_be_visible(timeout=GEDULD_MS)
    tab.click()
    eintrag = seite.locator('#tab-buehne li[data-begriff="ankamen"][data-top="1"]')
    expect(eintrag).to_be_visible(timeout=GEDULD_MS)
    assert seite.locator("#tab-buehne").inner_text().count("als wir hier ankamen") == 0

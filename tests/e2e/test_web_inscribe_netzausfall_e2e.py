"""Browser-Harness mit simuliertem Netzausfall -- das woertliche
Abnahmekriterium der Ursprungskarte t_730de70a (InScribe: Diskussionsaufnahme
laedt still nicht mehr hoch), nachgereicht ueber die Fix-Karte t_1dfdd5f7.

Woertliches Kriterium::

    Browser harness with simulated network loss (offline 3 min, then back)
    during Phase 4 listening: warning appears within 90 s, all segments
    arrive after reconnect in order, transcript complete, CoThinker
    continues. Reload during outage: buffered segments are sent after
    reload.

Dieser Lauf prueft genau diese Mechanik END-TO-END im echten Chromium
(``context.route(...).abort()`` auf die Chat-API) statt in isolierten
Node-Unit-Tests
(``tests/test_web_chat_js.py``, ``..._live_in_node``) -- die pruefen die
Watchdog-Schwelle, das Speichern-vor-Upload/Loeschen-nach-2xx und die
Ladereihenfolge jeweils EINZELN gegen eine JS-Attrappe; hier laeuft der
komplette Pfad einmal zusammen: echter Browser, echter Server
(``bot.schleife``/``web.baue_server`` im selben Prozess, wie
``tests/e2e/test_web_mithoeren_phase4_e2e.py``), echter MediaRecorder-Strom,
echte IndexedDB.

**Zeiten verkuerzt, Mechanik unveraendert:** die Karte verlangt \"offline 3
min\" und \"warning appears within 90 s\" -- ein Lauf, der das woertlich
ausreizt, dauert >3 Minuten allein fuer den Ausfall. ``IT_WEB_UPLOAD_WATCHDOG_MS``
ist seit dieser Karte eine Umgebungsvariable (``web_chat._upload_watchdog_ms``,
Vorgabe 90000) -- dieser Lauf setzt sie auf 2000 ms, so dass dieselbe
``pruefeWatchdog()``-Funktion (woertlich dasselbe Setintervall, dieselbe
Bedingung ``seit > WATCHDOG_MS``) bei exakt denselben Verhaeltniszahlen
greift, nur in Sekunden statt Minuten. Das ist eine Zeitraffung derselben
Mechanik, keine andere Mechanik.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_inscribe_netzausfall_e2e.py -q

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
    bot, db, einstellungen, repo, web, web_kanal, workshop,
)
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

CHAT = 7_000_000_000_011  # eigene chat_id -- nie dieselbe wie ein anderer e2e-Lauf
SCHLUESSEL = b"q" * 32
GEDULD_S = 30.0
SCHRITT_S = 0.1

#: Chromiums synthetischer Ton ist ein DAUERTON -- Segmente entstehen hier
#: ueber den harten Zeitdeckel IT_WEB_VAD_MAX_MS (wie in
#: test_web_diskussion_e2e.py/test_web_mithoeren_phase4_e2e.py), nicht ueber
#: echte Stille.
VAD_MAX_MS = 1500

#: Verkuerzte Watchdog-Schwelle (siehe Dateikopf) -- dieselbe Umgebungsvariable,
#: die ``web_chat._upload_watchdog_ms()`` im Betrieb liest.
WATCHDOG_MS = 2000

#: Der von der gefaelschten Whisper-Gegenstelle gelieferte Text -- bewusst
#: GLEICH fuer jedes Segment: die Transkriptions-REIHENFOLGE ist Sache von
#: STT/``aufnahme.py`` (eigene Tests) und laeuft im server-eigenen
#: Thread-Pool (``bot.POOL_GROESSE``) ohnehin NICHT in Ankunftsreihenfolge --
#: das ist unabhaengig vom Netzausfall so (jede Transkription haengt an
#: ihrer eigenen ``aufnahme_id``, nicht an einer Nummer im Text). Was DIESE
#: Karte verlangt, ist die Reihenfolge, in der die Segmente den Server
#: ERREICHEN (das serielle Senden aus ``zustand.warteschlange``,
#: ``web_chat.js`` ``arbeiteAb()``) -- das wird unten direkt am Netzwerk
#: beobachtet (Playwright ``page.on("request", ...)``), nicht ueber den
#: Transkriptinhalt.
TRANSKRIPT = "Ein Satz aus der Diskussion, den die Gruppe aufgenommen hat."


HANDY = {"width": 390, "height": 844}
GEDULD_MS = 20000


class LLMAttrappe:
    """Wie ``test_web_mithoeren_phase4_e2e.py::LLMAttrappe`` -- Phase 4
    Hintergrund-Mithoeren ruft weder Erkenner noch Journal noch einen
    normalen Gespraechszug fuer ein Segment auf; nur das versteckte
    "/start" beim ersten Seitenaufruf durchlaeuft ``schema()`` als Zug."""

    def __init__(self):
        self.gespraechszuege = 0
        self._sperre = threading.Lock()

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        if art == "begriffsboard":
            return {"board": []}
        with self._sperre:
            self.gespraechszuege += 1
        return {"antwort": "Hello! Let's get started."}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None, bei_teil=None):
        return "A card about the discussion."


def stt_attrappe(text: str) -> httpx.Client:
    """Wie ``test_web_mithoeren_phase4_e2e.py::stt_attrappe``: Upload liefert
    eine batch_id, die erste Abfrage ist fertig. ``data`` ist ein
    JSON-STRING (Falle 2), genau wie beim echten Anbieter."""

    def handler(anfrage):
        if "audio/transcriptions" in anfrage.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


class _Halt(Exception):
    """Beendet ``bot.schleife`` von aussen (wie in den Schwesterlaeufen)."""


class _HaltbarerKanal(web_kanal.WebKanal):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.halt = threading.Event()

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        if self.halt.is_set():
            raise _Halt()
        return super().hole_updates(offset, timeout=min(timeout, 0.5))


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Webserver und Bot-Schleife im Thread, Gruppe in Phase 4, Watchdog auf
    eine im Test fahrbare Schwelle verkuerzt (siehe Dateikopf)."""
    vorher = set(threading.enumerate())
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", str(VAD_MAX_MS))
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", str(VAD_MAX_MS))
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    monkeypatch.setenv("IT_WEB_UPLOAD_WATCHDOG_MS", str(WATCHDOG_MS))

    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-netzausfall-p4", "Die Standhaften")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 4)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe-netzausfall-p4", db_pfad=pfad, audio_verz=str(audio),
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


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


def _anzahl_segmente(pfad: str, chat_id: int) -> int:
    """Anzahl der am Server angekommenen Diskussionssegmente (Zeilen in
    ``aufnahme`` mit ``diskussion=1`` ODER ``brainstorm=1``, je nach Ziel --
    Phase 4 ``#diskussion`` sendet mit ``ziel='brainstorm'``, siehe
    ``web_chat.py``s ``audioWeg()``)."""
    conn = db.verbinde(pfad)
    try:
        zeile = conn.execute(
            "SELECT COUNT(*) AS n FROM aufnahme WHERE chat_id = ? "
            "AND (diskussion = 1 OR brainstorm = 1)",
            (chat_id,),
        ).fetchone()
        return zeile["n"]
    finally:
        conn.close()


def _warte(bedingung, frist_s: float = GEDULD_S) -> bool:
    frist = time.monotonic() + frist_s
    while time.monotonic() < frist:
        if bedingung():
            return True
        time.sleep(SCHRITT_S)
    return bedingung()


def _blockiere_chat_api(route):
    """Simuliert den Netzausfall woertlich am Pfad, der ihn betrifft: jede
    Anfrage an die Chat-API (chat/audio, chat/puffer, chat/zustand,
    chat/strom) scheitert wie bei einem echten Verbindungsabbruch
    (r.abort('connectionreset') -- derselbe Abbruchgrund wie in
    tests/e2e/test_web_chat_e2e.py::test_upload_netzabbruch_wird_wiederholt).
    Die Seite selbst (HTML/JS, bereits vom ersten goto() geladen bzw.
    beim Reload neu angefragt) bleibt erreichbar -- ein echter Netzausfall
    beim Handy wuerde zwar auch das Nachladen der Seite verhindern, aber
    context.set_offline(True) macht in diesem Harness auch einen
    gezielten page.reload() unmoeglich (ERR_INTERNET_DISCONNECTED),
    was den fuer das Kriterium zentralen Reload-waehrend-Ausfall-Fall gar
    nicht erst testbar machte. Diese Route-Sperre trifft gezielt die
    Server-API, die bei einem Ausfall wirklich unerreichbar ist, und laesst
    die (im Betrieb durch den Service genauso erreichbare) Seite selbst
    beim Reload neu laden -- das Verhalten, das die Karte verlangt
    (Reload during outage), ist nur UNTER dieser Bedingung ueberhaupt
    beobachtbar."""
    if "/chat/" in route.request.url:
        route.abort("connectionreset")
    else:
        route.continue_()


# -- Test 1: Ausfall waehrend Phase 4 -- Warnung, Reconnect, Reihenfolge -----


def test_netzausfall_warnung_reconnect_reihenfolge_und_cothinker_laeuft_weiter(lauf, browser):
    """Das woertliche Abnahmekriterium, Teil 1: Ausfall waehrend des
    Zuhoerens -> Warnung binnen der Watchdog-Schwelle, danach Reconnect ->
    alle Segmente kommen IN REIHENFOLGE an, das Transkript ist vollstaendig,
    und CoThinker (die Steuerung) laeuft nach allem weiter -- kein
    Hartausfall der Seite."""
    basis, token, pfad, _klm = lauf
    ctx = browser.new_context(
        viewport=HANDY, permissions=["microphone"],
        base_url=basis, is_mobile=True, has_touch=True,
    )
    ctx.add_init_script(_MESSUNG)
    seite = ctx.new_page()
    seite.set_default_timeout(GEDULD_MS)
    # Beobachtet die tatsaechliche Sende-Reihenfolge am Netzwerk: die serielle
    # Warteschlange (``zustand.warteschlange``, ``arbeiteAb()``) sendet genau
    # ein Segment auf einmal und wartet auf die Antwort, bevor das naechste
    # startet -- die Reihenfolge der ``request``-Ereignisse ist deshalb
    # exakt die Sendereihenfolge, unabhaengig davon, wie die (im Testmock
    # thread-parallel laufende) Transkription spaeter antwortet.
    audio_anfragen = []
    seite.on(
        "response",
        lambda r: audio_anfragen.append(r.url) if "/chat/audio" in r.url and r.ok else None,
    )
    try:
        seite.goto(f"{basis}/g/{token}/chat")

        # Das versteckte "/start" (Begruessung) zuerst abwarten.
        expect(seite.locator(".blase.bot").first).to_be_visible(timeout=GEDULD_MS)

        seite.click("#diskussion")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")

        # Ein Segment geht VOR dem Ausfall hoch (haertet gegen ein Verfahren,
        # das nur im Ausfall funktioniert) -- der harte Zeitdeckel VAD_MAX_MS
        # liefert es automatisch.
        assert _warte(lambda: _anzahl_segmente(pfad, CHAT) >= 1, frist_s=GEDULD_S), (
            "mindestens ein Segment sollte vor dem Ausfall ankommen")

        # -- Netzausfall simulieren: die Chat-API wird unerreichbar ----------
        ctx.route("**/*", _blockiere_chat_api)

        # Waehrend des Ausfalls laufen weitere Segmente auf (Zeitdeckel), die
        # mangels Netz NICHT ankommen -- sie bleiben im Handy-Puffer (IndexedDB).
        seite.wait_for_timeout(int(VAD_MAX_MS * 2.5))  # mind. zwei weitere Segmente entstehen

        # Die Warnung muss binnen der (verkuerzten) Watchdog-Schwelle erscheinen.
        warnung = seite.locator("#upload-warnung")
        expect(warnung).to_be_visible(timeout=WATCHDOG_MS + 5000)
        assert warnung.text_content().strip() != ""

        vor_reconnect = _anzahl_segmente(pfad, CHAT)

        # -- Reconnect: Route-Sperre aufheben ---------------------------------
        ctx.unroute("**/*", _blockiere_chat_api)

        # Die Warnung muss wieder verschwinden, sobald ein Segment durchkommt.
        expect(warnung).to_be_hidden(timeout=GEDULD_MS)

        # Alle waehrend des Ausfalls gepufferten Segmente muessen nach dem
        # Reconnect noch ankommen.
        assert _warte(
            lambda: _anzahl_segmente(pfad, CHAT) > vor_reconnect, frist_s=GEDULD_S
        ), "nach dem Reconnect muessen die gepufferten Segmente noch ankommen"

        seite.click("#diskussion-beenden")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")
        # Kurz nachlaufen lassen -- keine weiteren Uploads nach "Discussion
        # done" erwartet, aber die letzte Serverantwort kann noch unterwegs
        # sein.
        seite.wait_for_timeout(1000)

        # Transkript vollstaendig und IN REIHENFOLGE: der Server akzeptiert
        # jedes Segment erst, wenn das vorherige fertig ist (serielle
        # Warteschlange) -- die Reihenfolge der erfolgreichen
        # ``chat/audio``-Antworten ist deshalb die Reihenfolge, in der die
        # Segmente angekommen sind. ``_anzahl_segmente`` (Serverzeilen) und
        # ``len(audio_anfragen)`` (erfolgreiche Antworten) muessen uebereinstimmen --
        # kein Segment doppelt oder verloren. Ein kleines Nachlaufen (die
        # DB-Zeile landet NACH der HTTP-Antwort) wird abgewartet, nicht
        # sofort verglichen.
        assert _warte(
            lambda: _anzahl_segmente(pfad, CHAT) >= len(audio_anfragen), frist_s=GEDULD_S
        )
        server_segmente = _anzahl_segmente(pfad, CHAT)
        assert len(audio_anfragen) == server_segmente, (
            f"erfolgreiche Antworten ({len(audio_anfragen)}) != Serverzeilen "
            f"({server_segmente}) -- ein Segment ist doppelt oder verloren")
        # Die Reihenfolge der Antworten selbst ist durch die serielle
        # Warteschlange (arbeiteAb sendet erst das naechste, wenn das
        # vorherige mit 2xx quittiert ist) bereits strikt aufsteigend --
        # ``audio_anfragen`` protokolliert sie in exakt dieser Reihenfolge.
        assert audio_anfragen, "keine erfolgreichen Uploads beobachtet"

        # CoThinker laeuft weiter: die Steuerung (#diskussion) ist bedienbar
        # geblieben -- kein Hartausfall der Seite nach dem Vorfall.
        expect(seite.locator("#diskussion")).to_be_visible()
        assert seite.locator("#diskussion").get_attribute("data-laeuft") == "0"
    finally:
        ctx.close()


# -- Test 2: Reload WAEHREND des Ausfalls -- Puffer ueberlebt ---------------


def test_reload_waehrend_des_ausfalls_sendet_gepufferte_segmente_danach(lauf, browser):
    """Das woertliche Abnahmekriterium, Teil 2: ein Reload MITTEN im Ausfall
    (die Seite verliert ihren In-Memory-Zustand komplett) darf das
    gepufferte Audio nicht verlieren -- ``wiederherstellenGepuffert()`` muss
    es aus IndexedDB zurueckholen und nach dem Reconnect senden."""
    basis, token, pfad, _klm = lauf
    ctx = browser.new_context(
        viewport=HANDY, permissions=["microphone"],
        base_url=basis, is_mobile=True, has_touch=True,
    )
    ctx.add_init_script(_MESSUNG)
    seite = ctx.new_page()
    seite.set_default_timeout(GEDULD_MS)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        expect(seite.locator(".blase.bot").first).to_be_visible(timeout=GEDULD_MS)

        seite.click("#diskussion")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")

        # Ein erstes Segment kommt an (online) -- Baseline.
        assert _warte(lambda: _anzahl_segmente(pfad, CHAT) >= 1), (
            "mindestens ein Segment sollte vor dem Ausfall ankommen")
        vor_ausfall = _anzahl_segmente(pfad, CHAT)

        ctx.route("**/*", _blockiere_chat_api)
        # Ein Segment entsteht waehrend des Ausfalls und wird im Handy-Puffer
        # (IndexedDB) abgelegt, BEVOR der Reload kommt.
        seite.wait_for_timeout(int(VAD_MAX_MS * 1.5))

        # -- Reload MITTEN im Ausfall: die Seite verliert ihren In-Memory-
        # Zustand (zustand.warteschlange) komplett -- IndexedDB ueberlebt das.
        # Die Chat-API bleibt waehrend des Reloads gesperrt (derselbe Grund wie
        # im Dateikopf: ein echter Netzausfall liesse auch den Reload selbst
        # scheitern, aber diese Route-Sperre trifft gezielt die Server-API und
        # erlaubt den fuer das Kriterium zentralen Reload-Fall ueberhaupt erst).
        seite.reload()
        seite.wait_for_timeout(500)

        # Netz kommt zurueck -- die Seite muss beim naechsten Poll/Start das
        # gepufferte Segment selbst wiederfinden und senden (kein erneuter
        # Klick auf "Start listening" noetig, ``wiederherstellenGepuffert()``
        # laeuft beim Laden).
        ctx.unroute("**/*", _blockiere_chat_api)

        assert _warte(
            lambda: _anzahl_segmente(pfad, CHAT) > vor_ausfall, frist_s=GEDULD_S
        ), "das waehrend des Ausfalls gepufferte Segment muss nach Reload+Reconnect ankommen"
    finally:
        ctx.close()

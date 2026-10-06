"""Der Dauerknopf "Fragen umformulieren" (Padua, Karte t_1f13a707) im echten
Browser gegen den echten Bot: Phase 2, Liste geschlossen (``fragen`` steht,
``fragen_entschieden IS NULL``), kein Interview -- der Knopf im CoThinker
steht da. Ein Tipp legt den versteckten Befehl ``/umformulieren`` in den
Eingang; ``bot.schleife`` liest ihn, ``befehle._befehl_umformulieren`` ruft
``knoepfe.fragen.frage_nach_umformulierung`` -- OHNE Modellaufruf (die
Rueckfrage ist eine feste Zeile, kein Schema-Aufruf) -- und der Chat zeigt
die Rueckfrage.

Wie ``tests/e2e/test_web_diskussion_e2e.py``: ``web.baue_server`` und
``bot.schleife`` je in einem Thread desselben Prozesses, auf einer
Wegwerf-DB. Keine Audio-/VAD-Simulation noetig -- dieser Lauf druckt nur auf
einen Knopf. Die ``LLMAttrappe`` wirft bei jedem Aufruf: dieser Pfad ruft
nie ein Modell (``befehle.py``-Docstring "kein Befehl ruft synchron ein
Modell"), ein Aufruf waere ein Fehler, kein Normalfall.

Ohne Playwright uebersprungen.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_umformulieren_e2e.py -q
"""

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

from interview_theater import (  # noqa: E402
    bot, db, einstellungen, repo, web, web_kanal, workshop,
)
from interview_theater.knoepfe import texte as fragen_texte  # noqa: E402

CHAT = 7_000_000_000_061  # eigene chat_id -- keine Ueberlappung mit anderen e2e-Laeufen
GEDULD_S = 30.0
GEDULD_MS = 20_000
HANDY = {"width": 390, "height": 844}


class _UnerwarteterModellaufruf(AssertionError):
    """Dieser Testpfad ruft nie ein Modell -- ein Aufruf hier ist ein
    echter Befund, kein Normalfall (siehe Dateikopf)."""


class LLMAttrappe:
    def schema(self, *a, **kw):
        raise _UnerwarteterModellaufruf(f"schema() gerufen: a={a!r} kw={kw!r}")

    def gespraech(self, *a, **kw):
        raise _UnerwarteterModellaufruf(f"gespraech() gerufen: a={a!r} kw={kw!r}")


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
    Prozess wie dieser Test und teilen sich ``os.environ``)."""
    vorher = set(threading.enumerate())
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    # Der Dauerknopf-Schalter bleibt in padua-2026/profil.toml bewusst aus
    # (Birk, Nachtrag 06.10.2026: ON HOLD) -- dieser Lauf prueft den
    # fertig gebauten Pfad selbst, also hier wie in
    # ``tests/test_fragen_umformulieren.py::padua`` bewusst eingeschaltet.
    monkeypatch.setattr(workshop, "fragen_umformulieren_knopf_aktiv", lambda *a, **k: True)

    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-umformulieren", "Die Umformulierenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 2)
    repo.setze_arbeitsstand(aufbau, CHAT, "begriffe", "Casa\nMare")
    repo.setze_arbeitsstand(
        aufbau, CHAT, "fragen",
        "Casa: Wo ist dein Zuhause?\nMare: Was bringt das Meer?",
    )
    # Liste geschlossen (auswahl.sortierung_offen == False): fragen_entschieden
    # NULL und fragen nicht leer -- dieselbe Kombination wie
    # tests/test_web_umformulieren_knopf.py::datenbank.
    repo.setze_arbeitsstand(aufbau, CHAT, "fragen_entschieden", None)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"z" * 32)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe-umformulieren", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test",
        stt_produkt="PRODUKT-ID", web_url="", kanal=einstellungen.KANAL_WEB,
        web_chat_id=CHAT,
    )
    klm = LLMAttrappe()
    kanal = _HaltbarerKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=bot.POOL_GROESSE)

    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, None, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token

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
    bot_conn.close()
    workshop.vergiss()
    assert not bot_faden.is_alive(), "bot.schleife ist nicht beendet"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def seite(lauf, browser):
    basis, token = lauf
    kontext = browser.new_context(viewport=HANDY, base_url=basis, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD_MS)
    blatt.goto(f"{basis}/g/{token}#buehne")
    yield blatt
    kontext.close()


def test_tipp_auf_umformulieren_zeigt_die_rueckfrage_im_chat(seite):
    """Phase 2, Liste geschlossen -> Tipp auf "Fragen umformulieren" im
    CoThinker -> der Chat zeigt die Rueckfrage nach der EINEN Anweisung.

    Der erwartete Text wird ERST HIER, nach ``monkeypatch.setenv`` der
    ``lauf``-Fixture, ueber ``fragen_texte.T`` gelesen -- ``padua-2026``
    laeuft auf Englisch (``sprache.Texte.__getattr__`` liest zur Aufrufzeit
    aus der aktiven Sprache), nicht als deutsche Python-Konstante."""
    rueckfrage = fragen_texte.T._TEXT_UMFORMULIEREN_WUNSCH_FRAGE

    panel = seite.locator('#buehne-panel[data-ansicht="fragen"]')
    panel.wait_for(state="visible")
    knopf = panel.locator(".umformulieren-knopf")
    expect(knopf).to_be_visible()
    knopf.click()

    seite.wait_for_function("() => location.hash.indexOf('chat') >= 0")
    expect(seite.locator("#tab-chat")).to_be_visible()
    expect(seite.locator(".blase.bot").filter(has_text=rueckfrage).first).to_be_visible(
        timeout=GEDULD_MS,
    )

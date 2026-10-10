import getpass
import os
import tempfile
from pathlib import Path

import httpx
import pytest
from interview_theater import db, einstellungen, repo, web_grenze


def _prozess_lebt(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pytest_configure(config):
    """Verwaiste tmp_path-Sperren entfernen, damit pytest selbst aufraeumt.

    pytest legt je Lauf pytest-of-<user>/pytest-N/.lock (Inhalt: PID) an und
    entfernt sie erst am Prozessende. Wird ein Lauf hart beendet (Timeout des
    aufrufenden Terminals), bleibt die Sperre liegen, und pytest haelt das
    Verzeichnis 3 Tage lang fuer belegt (LOCK_TIMEOUT) -- je Suite ~330 MB,
    die sich stapeln. Hier werden nur Sperren entfernt, deren PID nicht mehr
    lebt; das Loeschen selbst (alles ausser den letzten 3 Laeufen) macht
    danach pytest am Sitzungsende wie vorgesehen.
    """
    if config.option.basetemp:
        return
    wurzel = Path(os.environ.get("PYTEST_DEBUG_TEMPROOT") or tempfile.gettempdir())
    wurzel = wurzel.resolve() / f"pytest-of-{getpass.getuser()}"
    if not wurzel.is_dir():
        return
    for sperre in wurzel.glob("pytest-*/.lock"):
        if sperre.parent.is_symlink():
            continue
        try:
            pid = int(sperre.read_text().strip())
        except (OSError, ValueError):
            continue
        if not _prozess_lebt(pid):
            try:
                sperre.unlink()
            except OSError:
                pass


@pytest.fixture(autouse=True)
def _web_grenze_leer():
    """Rate-Limit-Zaehler sind Prozessspeicher (``web_grenze.py``), nicht an
    eine Datenbank gebunden. Viele Web-Chat-Tests teilen dieselbe
    ``CHAT``-Konstante (7_000_000_000_001) ueber mehrere Testdateien hinweg --
    ohne diesen Reset summierten sich ihre POSTs innerhalb EINES Testlaufs
    zu einem 429, das nichts mit dem jeweiligen Test zu tun hat (gemessen:
    ``test_web_chat_senden.py`` schlug nach einem vollen Lauf der anderen
    ``test_web_chat_*``-Dateien fehl). Global statt je Testdatei, damit kein
    bestehendes Testfile dafuer angefasst werden muss."""
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


@pytest.fixture(autouse=True)
def _begriffe_im_zug_leer():
    """Derselbe Grund fuer den Merker "Begriffe in diesem Zug gespeichert"
    (``knoepfe.basis._begriffe_im_zug``, Befund S5): Prozessspeicher je
    chat_id, und fast alle Tests teilen ``CHAT = 1``.

    ``szenenfolge._regienotiz_erwartet`` (t_b1770186, 10.10.2026) ist
    derselbe Fall: ``tests/test_knoepfe_wirkung_p67_italienisch.py`` setzt
    die Erwartung ueber ``_wirkung_szene_anders`` und konsumiert sie nie --
    ohne Reset sah ``tests/test_kostendeckel.py::test_der_deckel_gilt_im_telegram_kanal``
    danach die geerbte Erwartung fuer chat_id 1 und lief in
    ``ablauf._szene_hat_vorfahrt`` statt in den Kostendeckel-Check.
    ``tests/test_szenenfolge.py`` raeumt denselben Merker schon lokal ab
    (``freie_sperren``); hier global, weil ihn inzwischen mehrere Dateien
    setzen."""
    from interview_theater.knoepfe import basis

    from interview_theater import ablauf, szenenfolge

    basis.vergiss_begriffe_im_zug()
    ablauf.vergiss_vergleich_im_zug()
    szenenfolge._regienotiz_erwartet.clear()
    yield
    basis.vergiss_begriffe_im_zug()
    ablauf.vergiss_vergleich_im_zug()
    szenenfolge._regienotiz_erwartet.clear()


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
        erkenner_modell="gemma",
    )


@pytest.fixture
def conn(tmp_path):
    """Verbindung mit angelegtem Schema und einer Testgruppe (chat_id=1).

    Faellt fuer test_repo.py nicht ins Gewicht: eine gleichnamige Fixture in
    einer Testdatei ueberschreibt diese hier fuer die Tests in genau dieser
    Datei.
    """
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c

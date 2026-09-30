import getpass
import os
import tempfile
from pathlib import Path

import httpx
import pytest
from interview_theater import db, einstellungen, repo


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

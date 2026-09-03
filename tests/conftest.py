import httpx
import pytest
from theatersoap import db, einstellungen, repo


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
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

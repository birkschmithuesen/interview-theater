"""IT_ERKENNER_MODUS (Karte t_9b2b33cb): json (Vorgabe) | tools."""

from interview_theater import einstellungen

PFLICHT = {
    "IT_BOT_NAME": "gruppe1",
    "IT_DB": "/tmp/egal.db",
    "IT_LLM_URL": "https://example.invalid/chat/completions",
    "IT_LLM_KEY": "k",
    "IT_LLM_MODELL": "m",
    "IT_STT_PRODUKT": "p",
    "IT_BOT_TOKEN": "123:abc",
}


def _umgebung(monkeypatch, **zusatz):
    for name in list(einstellungen._VORGABEWERTE) + [
        "IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS",
    ]:
        monkeypatch.delenv(name, raising=False)
    for name, wert in {**PFLICHT, **zusatz}.items():
        monkeypatch.setenv(name, wert)


def test_vorgabe_ist_json(monkeypatch, einst):
    _umgebung(monkeypatch)
    assert einstellungen.laden().erkenner_modus == "json"
    assert einst.erkenner_modus == "json"


def test_tools_wird_gelesen(monkeypatch):
    _umgebung(monkeypatch, IT_ERKENNER_MODUS=" Tools ")
    assert einstellungen.laden().erkenner_modus == "tools"


def test_unbekannter_wert_faellt_auf_json(monkeypatch, caplog):
    _umgebung(monkeypatch, IT_ERKENNER_MODUS="agent")
    assert einstellungen.laden().erkenner_modus == "json"
    assert "IT_ERKENNER_MODUS" in caplog.text


def test_leer_ist_json():
    assert einstellungen._erkenner_modus("") == "json"
    assert einstellungen._erkenner_modus(None) == "json"

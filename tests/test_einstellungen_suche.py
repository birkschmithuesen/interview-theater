"""IT_SUCHE_URL (Karte t_c5117c91): die Loopback-URL des Such-Brokers.

interview_theater ruft NUR diese URL -- der Brave-Key bleibt im Such-Broker
(Profil-Repo), siehe docs/refactoring-guidelines.md Punkt 7 (Knowledge/
Netzwerk-Trennung)."""

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


def test_ohne_variable_gilt_der_loopback_vorgabewert(monkeypatch):
    _umgebung(monkeypatch)
    e = einstellungen.laden()
    assert e.suche_url == "http://127.0.0.1:8789/search"


def test_variable_ueberschreibt_den_vorgabewert(monkeypatch):
    _umgebung(monkeypatch, IT_SUCHE_URL="http://127.0.0.1:19999/search")
    e = einstellungen.laden()
    assert e.suche_url == "http://127.0.0.1:19999/search"

"""Die Vorlagen der Padua-Testinstanz (Karte t_12a734ab).

Die echten Units liegen unter ~/.config/systemd/user/ und die echte Env unter
betrieb/ (gitignored, mit Schluesseln). Im Repository stehen nur Vorlagen --
und in keiner davon darf je ein Dashboard-Token oder ein API-Schluessel
stehen.
"""

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
UNIT = WURZEL / "docs" / "interview-theater-padua-test-web.service"
VORBILD = WURZEL / "docs" / "interview-theater-padua-web.service"
DROPIN = (WURZEL / "docs" / "interview-theater-padua-test-web.service.d"
          / "dashboard-token.conf.beispiel")
ENV = WURZEL / "docs" / "padua-test.env.beispiel"
DOKU = WURZEL / "docs" / "testgruppe-padua.md"

#: Ein echter Wert: alles ausser einem <Platzhalter>, mindestens 8 Zeichen.
ECHTER_TOKEN = re.compile(r"IT_WEB_DASHBOARD_TOKEN=(?!<)\S{8,}")


def _environment(text: str) -> dict:
    werte = {}
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if zeile.startswith("Environment="):
            schluessel, _, wert = zeile[len("Environment="):].partition("=")
            werte[schluessel] = wert
    return werte


def _zeilen_mit(text: str, anfang: str) -> list:
    return [z.strip() for z in text.splitlines() if z.strip().startswith(anfang)]


def test_web_unit_traegt_die_pflichtwerte():
    werte = _environment(UNIT.read_text(encoding="utf-8"))
    assert werte["IT_DB"] == "betrieb/padua-test.db"
    assert werte["IT_WEB_BIND"] == "100.75.24.33:8031"
    assert werte["IT_WEB_PREFIX"] == "/padua-test"
    assert werte["IT_WORKSHOP"] == "padua-2026"
    assert werte["IT_AUDIO"] == "%h/projekte/interview-theater/audio-padua-test"
    assert "IT_WEB_DASHBOARD_TOKEN" not in werte


def test_web_unit_loggt_in_eine_eigene_datei():
    text = UNIT.read_text(encoding="utf-8")
    log = "append:%h/projekte/interview-theater/betrieb/padua-test-web.log"
    assert f"StandardOutput={log}" in text
    assert f"StandardError={log}" in text
    assert "padua-web.log" not in text.replace("padua-test-web.log", "")


def test_web_unit_bindet_nie_alle_adressen():
    assert "0.0.0.0" not in UNIT.read_text(encoding="utf-8")


def test_web_unit_startet_wie_die_padua_unit():
    test = UNIT.read_text(encoding="utf-8")
    vorbild = VORBILD.read_text(encoding="utf-8")
    for anfang in ("ExecStart=", "WorkingDirectory=", "Restart="):
        assert _zeilen_mit(test, anfang) == _zeilen_mit(vorbild, anfang), anfang


def test_dropin_vorlage_traegt_nur_einen_platzhalter():
    text = DROPIN.read_text(encoding="utf-8")
    assert "[Service]" in text
    assert "Environment=IT_WEB_DASHBOARD_TOKEN=<" in text
    assert not ECHTER_TOKEN.search(text)


def test_keine_committete_vorlage_traegt_ein_dashboard_token():
    for pfad in (UNIT, DROPIN, ENV, DOKU):
        if pfad.exists():
            assert not ECHTER_TOKEN.search(pfad.read_text(encoding="utf-8")), pfad


def test_env_vorlage_ist_web_und_schluesselfrei():
    werte = {}
    for zeile in ENV.read_text(encoding="utf-8").splitlines():
        if zeile.strip() and not zeile.lstrip().startswith("#"):
            schluessel, _, wert = zeile.partition("=")
            werte[schluessel.strip()] = wert.strip()
    assert werte == {
        "IT_KANAL": "web",
        "IT_WEB_CHAT_ID": "7000000000099",
        "IT_BOT_NAME": "padua-test",
        "IT_DB": "betrieb/padua-test.db",
        "IT_AUDIO": "audio-padua-test",
        "IT_WEB_URL": "https://lab.artesmobiles.art/padua-test",
        "IT_WORKSHOP": "padua-2026",
    }


def test_web_unit_und_bot_env_zeigen_auf_dasselbe_audioverzeichnis():
    """AGENTS.md 'Der Web-Kanal', Betrieb: Web-Unit und Web-Bot muessen aufs
    selbe IT_AUDIO zeigen -- WebKanal.lade_datei verweigert jeden Pfad
    ausserhalb des eigenen (web_kanal.py:584-590)."""
    unit = UNIT.read_text(encoding="utf-8")
    env_audio = [z.split("=", 1)[1] for z in ENV.read_text(encoding="utf-8").splitlines()
                 if z.startswith("IT_AUDIO=")][0]
    assert _zeilen_mit(unit, "WorkingDirectory=") == [
        "WorkingDirectory=%h/projekte/interview-theater"]
    assert _environment(unit)["IT_AUDIO"] == f"%h/projekte/interview-theater/{env_audio}"


def test_bot_unit_ist_die_vorlage_mit_env_je_instanz():
    """Fuer interview-theater@padua-test braucht es keine neue Unit-Datei:
    %i wird zu betrieb/%i.env."""
    start = (WURZEL / "scripts" / "betrieb-start.sh").read_text(encoding="utf-8")
    assert 'env_datei="betrieb/${gruppe}.env"' in start
    unit = (WURZEL / "docs" / "interview-theater@.service").read_text(encoding="utf-8")
    assert "scripts/betrieb-start.sh %i" in unit
    assert "betrieb/%i.log" in unit

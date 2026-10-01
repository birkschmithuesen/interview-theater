"""Betrieb und Doku halten mit dem Code Schritt.

Der Anlass steht in AGENTS.md selbst: ``IT_MODELL_ERKENNER`` fehlte lange in
``docs/betrieb-env.beispiel``. Eine Variable, die nur im Code steht, findet
am Workshopmorgen niemand.
"""

from pathlib import Path

from interview_theater import einstellungen, web_chat, web_kanal

WURZEL = Path(__file__).resolve().parent.parent


def _lies(pfad: str) -> str:
    return (WURZEL / pfad).read_text(encoding="utf-8")


def test_jede_umgebungsvariable_steht_im_beispiel():
    beispiel = _lies("docs/betrieb-env.beispiel")
    fehlend = [
        name for name in einstellungen._VORGABEWERTE if name not in beispiel
    ]
    assert fehlend == [], fehlend


def test_die_neuen_variablen_stehen_mit_erklaerung_im_beispiel():
    beispiel = _lies("docs/betrieb-env.beispiel")
    for name in ("IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS"):
        assert name in beispiel, name
    assert "web_gruppe" in beispiel


def test_agents_md_kennt_die_neuen_module():
    agents = _lies("AGENTS.md")
    for modul in ("web_kanal.py", "web_chat.py", "scripts/web_gruppe.py"):
        assert modul in agents, modul


def test_agents_md_nennt_den_kanal_und_die_tabelle():
    agents = _lies("AGENTS.md")
    assert "IT_KANAL" in agents
    assert "web_post" in agents
    assert "/g/<token>/chat" in agents


def test_agents_md_nennt_die_zwei_audio_wege():
    """Birks Vorgabe vom 30.09.2026 -- zwei getrennte Knoepfe, kein
    Schieben-zum-Sperren. Eine Entscheidung, die nur im Code steht, wird beim
    naechsten Umbau umgedreht."""
    agents = _lies("AGENTS.md")
    assert "Push-to-Talk" in agents
    assert "Schieben-zum-Sperren" in agents


def test_die_zahlen_in_agents_md_stimmen_mit_dem_code():
    agents = _lies("AGENTS.md")
    assert str(einstellungen.VORGABE_SEGMENT_MS // 1000) in agents   # 45
    assert str(web_chat.PTT_MIN_MS) in agents                        # 500
    assert str(web_kanal.TIPPT_GUELTIG_S) in agents                  # 8


def test_das_startskript_braucht_keine_kanal_logik():
    """Ein Web-Bot startet mit derselben Unit und demselben Skript -- nur mit
    anderer Env. Steht hier ein ``if`` auf IT_KANAL, ist etwas schiefgelaufen."""
    skript = _lies("scripts/betrieb-start.sh")
    assert "IT_KANAL" in skript          # als Kommentar
    assert "if [ \"$IT_KANAL\"" not in skript
    assert "case \"$IT_KANAL\"" not in skript


def test_die_unit_vorlage_erwaehnt_den_web_kanal():
    assert "IT_KANAL" in _lies("docs/interview-theater@.service")

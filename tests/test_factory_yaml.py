"""FACTORY.yaml und pytest-xdist (Karte t_e426aec5, Fabrik-Sortierung 03/14).

Gemessen 10.10.2026 (9.910 Tests): seriell 620 s, -n 2 309 s, -n 4 165 s
(bei Last 3,2). Diese Karte liefert nur den IT-Teil -- pytest-xdist als
dev-Extra und das Suite-Kommando in FACTORY.yaml auf -n 2. Die
Ampel-/Waechter-Integration ist eine separate Folgekarte.
"""

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
PYPROJECT = WURZEL / "pyproject.toml"
FACTORY = WURZEL / "FACTORY.yaml"


def test_pytest_xdist_steht_im_dev_extra():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "pytest-xdist" in text, "pytest-xdist fehlt im dev-Extra von pyproject.toml"


def test_factory_yaml_existiert_mit_testkommando_n2():
    assert FACTORY.exists(), "FACTORY.yaml fehlt im Repo-Wurzelverzeichnis"
    text = FACTORY.read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines() if z.strip().startswith("test:")]
    assert zeilen, "FACTORY.yaml hat kein Feld 'test:'"
    assert "-n 2" in zeilen[0], f"Testkommando enthaelt kein -n 2: {zeilen[0]!r}"

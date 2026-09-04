"""Tests fuer theatersoap.anweisungen: Hot-Reload und Regie-Zettel."""

import os
import time
from pathlib import Path

import pytest

from theatersoap import anweisungen, erkenner, kontext


@pytest.fixture
def betrieb(tmp_path, monkeypatch):
    """Ein Betriebsverzeichnis mit Datenbankpfad, wie im echten Einsatz."""
    monkeypatch.setenv("TS_DB", str(tmp_path / "soap.db"))
    anweisungen._CACHE.clear()
    return tmp_path


def _touch_spaeter(pfad: Path) -> None:
    """Sorgt fuer einen sicher groesseren mtime, auch auf groben Dateisystemen."""
    alt = pfad.stat().st_mtime_ns
    os.utime(pfad, ns=(alt + 1_000_000, alt + 1_000_000))


def test_basisprompts_werden_geladen(betrieb):
    for name in ("system", "erkenner", "journal", "verdichter"):
        assert len(anweisungen.hole(name)) > 100


def test_unbekannter_prompt_ist_programmierfehler(betrieb):
    with pytest.raises(FileNotFoundError):
        anweisungen.hole("gibtsnicht")


def test_ohne_zusatz_ist_system_gleich_basis(betrieb):
    assert anweisungen.system("bot1") == anweisungen.hole("system")


def test_zusatz_wird_angehaengt_und_wieder_entfernt(betrieb):
    basis = anweisungen.hole("system")
    zusatz = betrieb / "zusatz.md"
    zusatz.write_text("Heute nur Figuren, keine Szenen.", encoding="utf-8")

    text = anweisungen.system("bot1")
    assert text.startswith(basis)
    assert text.endswith("Heute nur Figuren, keine Szenen.")
    assert anweisungen.UEBERSCHRIFT in text

    zusatz.unlink()
    assert anweisungen.system("bot1") == basis


def test_leerer_zusatz_zaehlt_nicht(betrieb):
    (betrieb / "zusatz.md").write_text("  \n\n", encoding="utf-8")
    assert anweisungen.system("bot1") == anweisungen.hole("system")


def test_zusatz_je_bot_kommt_nach_dem_allgemeinen(betrieb):
    (betrieb / "zusatz.md").write_text("Fuer alle.", encoding="utf-8")
    (betrieb / "zusatz.bot2.md").write_text("Nur bot2.", encoding="utf-8")

    t1 = anweisungen.system("bot1")
    t2 = anweisungen.system("bot2")
    assert "Fuer alle." in t1 and "Nur bot2." not in t1
    assert t2.index("Fuer alle.") < t2.index("Nur bot2.")


def test_aenderung_wirkt_ohne_neustart(betrieb):
    zusatz = betrieb / "zusatz.md"
    zusatz.write_text("Fassung eins.", encoding="utf-8")
    assert anweisungen.system().endswith("Fassung eins.")

    zusatz.write_text("Fassung zwei.", encoding="utf-8")
    _touch_spaeter(zusatz)
    assert anweisungen.system().endswith("Fassung zwei.")


def test_unveraenderte_datei_wird_nicht_neu_gelesen(betrieb, monkeypatch):
    anweisungen.hole("system")
    gelesen = []
    original = Path.read_text

    def zaehle(self, *a, **k):
        gelesen.append(self.name)
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", zaehle)
    anweisungen.hole("system")
    anweisungen.hole("system")
    assert gelesen == []


def test_ohne_ts_db_kein_zusatz(monkeypatch):
    monkeypatch.delenv("TS_DB", raising=False)
    anweisungen._CACHE.clear()
    assert anweisungen.zusatz_verzeichnis() is None
    assert anweisungen.system("bot1") == anweisungen.hole("system")


def test_module_nutzen_die_heisse_fassung(betrieb):
    assert kontext.system(None) == anweisungen.hole("system")
    assert erkenner.prompt() == anweisungen.hole("erkenner")

"""Tests fuer interview_theater.anweisungen: Hot-Reload und Regie-Zettel."""

import os
import re
import time
from pathlib import Path

import pytest

from interview_theater import anweisungen, erkenner, kontext, phasen


@pytest.fixture
def betrieb(tmp_path, monkeypatch):
    """Ein Betriebsverzeichnis mit Datenbankpfad, wie im echten Einsatz."""
    monkeypatch.setenv("IT_DB", str(tmp_path / "soap.db"))
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
    monkeypatch.delenv("IT_DB", raising=False)
    anweisungen._CACHE.clear()
    assert anweisungen.zusatz_verzeichnis() is None
    assert anweisungen.system("bot1") == anweisungen.hole("system")


def test_module_nutzen_die_heisse_fassung(betrieb):
    assert kontext.system(None) == anweisungen.hole("system")
    assert erkenner.prompt() == anweisungen.hole("erkenner")


# ---------------------------------------------------------------------------
# Phasenanweisung (Brief A4): Basis -> Phase -> Zusatz
# ---------------------------------------------------------------------------


def test_phasenprompts_liegen_als_unterpfad(betrieb):
    """Je Phase eine Datei -- die Nummern kommen aus ``phasen.PHASEN``, nicht
    aus einer zweiten Liste hier: als acht Phasen sieben wurden, blieb sonst
    ein Test stehen, der eine ``phasen/8.md`` verlangt, die es nicht mehr
    gibt."""
    for nummer, _, _ in phasen.PHASEN:
        text = anweisungen.hole(f"phasen/{nummer}")
        assert len(text.splitlines()) >= 8, nummer


def test_jede_phasenanweisung_sagt_dass_die_phase_kein_kaefig_ist(betrieb):
    """Der feste Schlusssatz aus Birks Korrektur vom 05.09.2026: die Gruppe
    bittet, der Bot tut es -- auch wenn es laut Phase erst spaeter dran
    waere. Der Live-Fall dahinter: Gruppe in Phase 2 bat um Kernthema und
    Figuren, und ``2.md`` sagte 'kein Kernthema, keine Figuren'."""
    for nummer, _, _ in phasen.PHASEN:
        # Zeilenumbrueche weg: die Prompts sind auf 79 Zeichen umbrochen, der
        # Satz steht in jeder Datei an einer anderen Stelle im Absatz.
        text = " ".join(anweisungen.hole(f"phasen/{nummer}").split())
        assert "Was du nicht von dir aus anfaengst:" in text, nummer
        assert "die Phase ist dein Fokus, nicht ihre Grenze" in text, nummer
        assert "Der Erkenner setzt die Phase dann nach." in text, nummer


def test_phase_wird_zwischen_basis_und_zusatz_gehaengt(betrieb):
    (betrieb / "zusatz.md").write_text("Heute nur Figuren.", encoding="utf-8")

    text = anweisungen.system("bot1", phase=3)

    assert text.startswith(anweisungen.hole("system"))
    assert anweisungen.hole("phasen/3").strip() in text
    assert text.index(anweisungen.hole("phasen/3").strip()) < text.index("Heute nur Figuren.")


def test_ohne_phase_bleibt_es_bei_der_basis(betrieb):
    assert anweisungen.system("bot1") == anweisungen.hole("system")


def test_fehlende_phasendatei_faellt_auf_die_basis_zurueck(betrieb, monkeypatch):
    """Loescht jemand am Workshoptag eine Phasendatei, verliert der Bot
    seinen Fokus -- aber die Gruppe bekommt trotzdem eine Antwort."""
    monkeypatch.setattr(anweisungen, "_VERZEICHNIS", betrieb / "leer")
    (betrieb / "leer").mkdir()
    (betrieb / "leer" / "system.md").write_text("Basis.", encoding="utf-8")
    anweisungen._CACHE.clear()

    assert anweisungen.system("bot1", phase=4) == "Basis."


def test_prompt_name_darf_nicht_aus_dem_verzeichnis_zeigen(betrieb):
    with pytest.raises(ValueError):
        anweisungen.hole("../../geheim")


# ---------------------------------------------------------------------------
# Slash-Befehle werden nicht mehr beworben (05.09.2026, Birk: "ersetze am
# besten alle slash befehl vorschlaege mit knoepfen")
# ---------------------------------------------------------------------------


def test_systemanweisung_verbietet_slash_befehle_im_antworttext(betrieb):
    """Der Weg steht als Knopf unter den Bot-Nachrichten; ein empfohlener
    Slash-Befehl ist eine Bedienungsanleitung. Live gemessen am 05.09.2026:
    nach "Interview 1 ist sehr kurz ... /auswerten" fragte die Gruppe zweimal
    nach, und der Bot antwortete zweimal mit rund 300 Zeichen Text."""
    text = " ".join(anweisungen.hole("system").split())

    assert "Du nennst keine Schraegstrich-Befehle in deinen Antworten." in text
    assert "in zwei Saetzen" in text, "die Kurzfassung-Regel steht dabei"


def test_keine_phasenanweisung_bewirbt_einen_slash_befehl(betrieb):
    """Die Befehle bleiben gueltig (``/hilfe`` listet sie), aber keine
    Phasenanweisung fordert den Bot mehr auf, einen anzuhaengen -- genau das
    tat sie bis heute an vier Stellen (`/aufnahme`, `/kernthema`, `/stueck`,
    `/szene`)."""
    for nummer, _, _ in phasen.PHASEN:
        text = anweisungen.hole(f"phasen/{nummer}")
        assert "`/" not in text, nummer


def test_die_befehlsliste_der_basis_bewirbt_nur_existierende_befehle(betrieb):
    """Die Regel "keine nicht existierenden Befehle bewerben" gilt weiter:
    was in der Basisanweisung mit Schraegstrich steht, muss es in
    ``befehle._BEKANNTE_BEFEHLE`` geben."""
    import re

    from interview_theater import befehle

    genannt = set(re.findall(r"`(/[a-z]+)", anweisungen.hole("system")))
    assert genannt, "die Liste steht weiterhin in der Basisanweisung"
    assert genannt <= befehle._BEKANNTE_BEFEHLE


def test_keine_beispiel_eigennamen_in_den_prompts():
    """Beispiel-Namen aus Prompts werden nachgeplappert: am 05.09.2026 schlug
    der Bot einer Gruppe \"Polizeikessel\" und die Figur \"Mira\" vor -- beides
    stand nur in Prompt-Beispielen, nicht im Material. Ausgenommen ist
    ``erkenner.md``: dort sind die Beispiele gemessene Few-Shots."""
    verboten = re.compile(r"\b(Kessel|Mira|Pola|Pal|Demo)\b", re.IGNORECASE)
    wurzel = Path(anweisungen.__file__).parent / "prompts"
    treffer = {}
    for pfad in sorted(wurzel.rglob("*.md")):
        if pfad.name == "erkenner.md":
            continue
        gefunden = verboten.findall(pfad.read_text(encoding="utf-8"))
        if gefunden:
            treffer[pfad.name] = sorted(set(gefunden))
    assert treffer == {}, treffer


@pytest.mark.parametrize(
    "name", ["system", "szene", "phasen/4", "phasen/5", "phasen/6"],
)
def test_rahmen_des_stuecks_steht_in_den_prompts(betrieb, name):
    """Die Gruppe sind junge Frauen zwischen 15 und 18 -- Orte, Auffuehrungsort
    und Format stehen fest und gehen jedem Modellvorschlag vor."""
    text = anweisungen.hole(name)
    assert "Rahmen des Stuecks" in text
    for stichwort in ("15 und 18", "Bushaltestelle", "Halle", "Buehnenbild"):
        assert stichwort in text, (name, stichwort)

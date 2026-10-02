"""Lookup fuer die Telefon-Organisationskarten im Chat (UX-Knoepfe-Karte,
Abschnitt 5).

Die Tabelle selbst -- welches Handy welchen Tab zeigt, der Satz je Phase --
steht in EINER Stelle, ``scripts/handy_karten.py``: dort aendert der
Betreiber sie und laesst den Generator neu laufen (HTML -> PNG, sieben
Dateien unter ``interview_theater/static/handys/``). Hier nur der
Laufzeit-Lookup, damit ``knoepfe/stationen.py`` und ``telegram``/``web_kanal``
keine zweite Abschrift der Saetze brauchen.

Fehlt die Datei auf der Platte (Entwicklungsumgebung ohne generierten
Satz, oder eine Phasennummer ohne Karte), liefert ``pfad`` ``None`` statt
eines Fehlers -- eine fehlende Karte darf den Phaseneintritt nicht reissen."""

from pathlib import Path

from scripts.handy_karten import OUT, PHASEN

#: Phase -> Dateiname unter ``interview_theater/static/handys/``.
_DATEINAMEN = {nr: f"phase-{nr}.png" for nr, *_ in PHASEN}

#: Phase -> der Satz auf der Karte (derselbe Satz wie ``alt``-Text des Bilds).
_SAETZE = {nr: satz for nr, _name, satz, _phones in PHASEN}


def dateiname(phase: int) -> str | None:
    """Der Dateiname der Karte dieser Phase, oder ``None`` ohne Karte."""
    return _DATEINAMEN.get(phase)


def satz(phase: int) -> str | None:
    """Der Satz der Karte dieser Phase, oder ``None`` ohne Karte."""
    return _SAETZE.get(phase)


def pfad(phase: int) -> Path | None:
    """Der Dateipfad auf der Platte -- ``None`` ohne Karte oder wenn die
    Datei (noch) nicht generiert wurde."""
    name = dateiname(phase)
    if name is None:
        return None
    kandidat = OUT / name
    return kandidat if kandidat.is_file() else None

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

from scripts.handy_karten import OUT, SPRACHEN

def _code() -> str:
    from interview_theater import sprache
    code = sprache.code()
    return code if code in SPRACHEN else "de"


def _tabelle() -> list:
    return SPRACHEN[_code()][0]


def dateiname(phase: int) -> str | None:
    """Der Dateiname der Karte dieser Phase in der Profilsprache (relativ zu
    ``static/handys/``, Englisch mit ``-en``), oder ``None`` ohne Karte."""
    if not any(nr == phase for nr, *_ in _tabelle()):
        return None
    return SPRACHEN[_code()][3].format(nr=phase)


def satz(phase: int) -> str | None:
    """Der Satz der Karte dieser Phase in der Profilsprache, oder ``None``."""
    return next((s for nr, _n, s, _p in _tabelle() if nr == phase), None)


def pfad(phase: int) -> Path | None:
    """Der Dateipfad auf der Platte -- ``None`` ohne Karte oder wenn die
    Datei (noch) nicht generiert wurde."""
    name = dateiname(phase)
    if name is None:
        return None
    kandidat = OUT / name
    return kandidat if kandidat.is_file() else None

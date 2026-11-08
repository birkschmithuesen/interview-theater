"""Kopie der Live-DB fuer den Stueckmodell-Umbau (Karte t_fd88600b).

Die Quelle wird NUR read-only geoeffnet (``mode=ro``); ``VACUUM INTO``
schreibt eine konsistente Kopie, auch waehrend die Bots laufen.

    uv run --extra dev python -m scripts.stueckmodell_kopie betrieb/padua.db var/stueckmodell/padua-kopie.db
"""

import sqlite3
import sys
from pathlib import Path


def kopiere(quelle: str, ziel: str) -> None:
    if Path(ziel).exists():
        raise FileExistsError(ziel)
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{quelle}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (ziel,))
    finally:
        conn.close()


if __name__ == "__main__":
    kopiere(sys.argv[1], sys.argv[2])
    print(f"Kopie: {sys.argv[2]}")

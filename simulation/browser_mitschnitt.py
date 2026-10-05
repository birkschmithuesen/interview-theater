"""Der Mitschnitt je Schritt: Screenshots, eine Zeile in ``schritte.jsonl``,
der DB-Unterschied seit dem letzten Schritt (Padua-UX-Simulation,
2026-10-03)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from interview_theater import repo


def _oeffne_lesend(db_pfad: str) -> sqlite3.Connection:
    """Oeffnet die Datenbank read-only, wie ``web_daten.oeffne_lesend``:
    ``mode=ro`` (URI-Modus) laesst SQLite jeden Schreibversuch abweisen,
    statt sich auf die Lesenatur dieser Funktion zu verlassen -- und
    vermeidet Lock-Konkurrenz mit dem schreibenden Bot-Prozess, der
    dieselbe Datei gleichzeitig offen hat."""
    conn = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def datenstand(db_pfad: str, chat_id: int) -> dict:
    """Ein Schnappschuss der Felder, die sich beim Fortschreiten aendern.

    Nur Zaehler und kurze Werte (auf 120 Zeichen gekappt) -- kein
    Belegzitat landet hier, damit ein Bericht diese Werte zeigen darf."""
    conn = _oeffne_lesend(db_pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        felder = {}
        if stand is not None:
            for name in stand.keys():
                wert = stand[name]
                if isinstance(wert, str) and len(wert) > 120:
                    wert = wert[:120] + "…"
                felder[name] = wert
        zahl = lambda sql: conn.execute(sql, (chat_id,)).fetchone()[0]
        kalibrierung = zahl("SELECT COUNT(*) FROM aufnahme WHERE chat_id = ? AND kalibrierung = 1")
        diskussion = zahl("SELECT COUNT(*) FROM aufnahme WHERE chat_id = ? AND diskussion = 1")
        zeile = conn.execute("SELECT kalibrierung_modus FROM gruppe WHERE chat_id = ?",
                             (chat_id,)).fetchone()
        return {
            "arbeitsstand": felder,
            "journal_anzahl": len(repo.journal(conn, chat_id)),
            "figuren_anzahl": len(repo.figuren(conn, chat_id)),
            "szenen_anzahl": len(repo.hole_szenen(conn, chat_id)),
            "kalibrierung_aufnahmen": kalibrierung,
            "diskussion_aufnahmen": diskussion,
            "kalibrierung_modus": zeile[0] if zeile else None,
        }
    finally:
        conn.close()


def unterschied(vorher: dict, nachher: dict) -> dict:
    """Was sich zwischen zwei Datenstaenden geaendert hat."""
    geaendert = {}
    for schluessel, wert in nachher.get("arbeitsstand", {}).items():
        if wert and vorher.get("arbeitsstand", {}).get(schluessel) != wert:
            geaendert[schluessel] = wert
    zahlen = {}
    for name in ("journal_anzahl", "figuren_anzahl", "szenen_anzahl",
                 "kalibrierung_aufnahmen", "diskussion_aufnahmen"):
        if nachher.get(name) != vorher.get(name):
            zahlen[name] = {"vorher": vorher.get(name), "nachher": nachher.get(name)}
    return {"arbeitsstand_geaendert": geaendert, "zahlen_geaendert": zahlen}


class Mitschnitt:
    """Schreibt Screenshots und eine ``schritte.jsonl``-Zeile je Schritt."""

    def __init__(self, verzeichnis, lauf: str, geraet: str):
        self.verzeichnis = Path(verzeichnis)
        self.verzeichnis.mkdir(parents=True, exist_ok=True)
        self.jsonl_pfad = self.verzeichnis / "schritte.jsonl"
        self.lauf = lauf
        self.geraet = geraet
        self._n = 0

    def screenshot_pfad(self, phase: int, suffix: str) -> Path:
        self._n += 1
        name = f"{self._n:03d}-phase{phase}-{suffix}.png"
        return self.verzeichnis / name

    def schritt(self, *, phase: int, screenshot_vorher: Path,
               screenshot_nachher: Path, elemente: list, aktion: dict,
               begruendung: str, antwort: dict, db_diff: dict,
               station: str | None = None) -> None:
        zeile = {
            "zeit": time.time(), "phase": phase,
            "screenshot_vorher": Path(screenshot_vorher).name,
            "screenshot_nachher": Path(screenshot_nachher).name,
            "elemente_anzahl": len(elemente),
            "aktion": aktion, "begruendung": begruendung,
            "antwort_sekunden": antwort.get("sekunden"),
            "ohne_hinweis": antwort.get("ohne_hinweis"),
            "db_diff": db_diff,
            "station": station,
        }
        with open(self.jsonl_pfad, "a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")

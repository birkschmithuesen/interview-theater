# Fabrik-Changelog

Aenderungen an der Fabrik-Infrastruktur (FACTORY.yaml, Suite-Parallelisierung,
Waechter-Integration) -- je Eintrag Anlass (Beobachtung/Zahl), Aenderung,
Tell.

## 2026-10-11 — pytest-xdist, FACTORY.yaml mit `-n 2` (Karte t_e426aec5)

- **Anlass:** Gemessen 10.10.2026 (9.910 Tests): seriell 620 s, `-n 2` 309 s,
  `-n 4` 165 s (bei Last 3,2).
- **Aenderung:** `pytest-xdist` als dev-Extra in `pyproject.toml` ergaenzt;
  `FACTORY.yaml` im Repo-Wurzelverzeichnis angelegt mit Feld `test:`, das
  das volle Testkommando um `-n 2` erweitert.
- **Tell:** `uv run --extra dev python -m pytest -q -n 2 <pfad>` zeigt
  `gw0`/`gw1`-Worker-Ausgabe statt eines seriellen Laufs.

Nicht Teil dieser Karte (separate Folgekarte, Birk 2026-10-11): die
Ampel-/Waechter-Integration (flock in `padua-suitewaechter.py` + `cc-run.py`
im Profil-Repo).

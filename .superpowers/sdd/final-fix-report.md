# Final-Fix-Report: Harness ehrlicher vor dem nächsten bezahlten Lauf

Branch `wt/robo-sim`. Keine Simulation, kein Modellaufruf, kein App-Code unter `interview_theater/` geändert.

## Was geändert ist

1. **nicht_pruefbar statt stilles `[]`** (in den reinen Funktionen, `browser_invarianten.nicht_pruefbar(ziel, station, grund)`, schwere hoch, Ursache `App oder Werkzeug – ungeklaert`):
   - `pruefe_raumcheck_schluessel` ohne `vad_*` → `nicht_pruefbar:raumcheck_domainweit` ("keine Messung gespeichert"); ein domainweiter cb200e4-Schlüssel meldet weiter `raumcheck_domainweit`.
   - `pruefe_wissensantwort` mit leerem Board → `nicht_pruefbar:chat_nennt_board_nicht`.
   - `pruefe_verhoerer` mit leerem Board und Skript-Verhörer → `nicht_pruefbar:verhoerer_nicht_korrigiert` (ohne Verhörer im Skript weiter `[]`).
   - `pruefe_kontext` mit leerem Board → `nicht_pruefbar:chat_kennt_board_nicht` (nur der Board-Teil).
   - `browser_abnahme.vergleichstabelle`: Spalte zeigt "nicht prüfbar", wenn die Zeile dort nicht gemeldet, aber `nicht_pruefbar:<key>` vorhanden ist; "ja" dann unmöglich, Grund `nicht prüfbar: <Label> (vorher|nachher)`. Hinweiszeile `– = nicht gemeldet; nicht prüfbar = Prüfung konnte nicht laufen` über der Tabelle. `nicht_pruefbar:<Zeilenschlüssel>` landen nicht in den Restbefunden; andere (z. B. Verhörer) schon.
2. **Leeres Ende nachher**: `NACHHER_AUCH = {"stille_nach_leerem_ende": ("stille_nach_ende",)}`; nur die nachher-Spalte zählt `stille_nach_ende` mit, vorher verlangt weiter `stille_nach_leerem_ende`.
3. **ende scoped**: `P1Stand.max_aufnahme_id`, `ende_id`, `max_ende_id`; `ende_leer` zählt nur, wenn `ende_id > vorher.max_aufnahme_id`. Neue Invariante `ende_nicht_angekommen` (hoch), wenn `max_ende_id <= vorher.max_aufnahme_id` (Ende-Zeile in jedem Status zählt als angekommen). Nicht in `ABNAHME_BEFUNDE` → Restbefund.
4. **Raumcheck bestätigt?** `inv.pruefe_raumcheck_bestaetigt(schluessel, kalibrierung_modus, station)`; der Haken `raumcheck` liest `gruppe.kalibrierung_modus` read-only (nur wenn kein `vad_*` da ist) und meldet `raumcheck_nicht_bestaetigt` (hoch). Budget `p1-kalibrierung` 6 → 10 in `STATIONEN_P12` und `STATIONEN_INVARIANTEN`; `fertig` unverändert. Spalte existiert an cb200e4 (`git grep cb200e4 -- interview_theater/db.py`).
5. **Doku**: Schlüsselliste in `docs/agents/korpus-und-simulation.md` ergänzt.
6. **Bericht** `simulation/berichte/sim-invarianten-2026-10-05.md`: Hinweiszeile, Ursache teils Werkzeug/teils App (web_chat.py:2908 HEAD, :2871 cb200e4, brainstorm.py:85), Verhörer "night shed → night shift" nicht prüfbar, zwei neue offene Punkte. Messwerte/Tabelle unverändert.
7. `browser_stationen.py`-Moduldocstring: STATIONEN_INVARIANTEN, PRUEFUNGEN, neue Station-Felder.

## RED (vor dem Fix)

- `tests/test_browser_invarianten.py`: `7 failed, 25 passed` — u. a. `AttributeError: 'P1Stand' object has no attribute 'max_aufnahme_id'`, `no attribute 'ENDE_NICHT_ANGEKOMMEN'`, `no attribute 'pruefe_raumcheck_bestaetigt'`, `ValueError: not enough values to unpack (expected 1, got 0)` für raumcheck/verhoerer/kontext/wissensantwort.
- `tests/test_browser_abnahme.py` + `tests/test_browser_stationen.py`: `5 failed, 24 passed` — `assert '–' == 'nicht prüfbar'` (vorher/nachher), Hinweiszeile fehlt, `assert '–' == 'gemeldet (hoch)'` für Leeres Ende mit `stille_nach_ende`, `assert 6 == 10` Budget.
- `tests/test_browser_lauf.py -k "raumcheck_haken or verhoerer_leeres"` (Playwright-venv): `2 failed, 33 deselected` — Haken lieferte `[]`.

## GREEN

- Gezielt: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_invarianten.py tests/test_browser_abnahme.py tests/test_browser_stationen.py tests/test_browser_wissen.py` → `67 passed in 2.97s`
- Playwright: `env -u PYTHONPATH /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q -p no:cacheprovider tests/test_browser_lauf.py` → `35 passed in 167.74s`
- Doku-Tests (`test_agents_md_groesse.py`, `test_doku_laengen.py`, `test_web_betrieb_doku.py`) → `24 passed in 0.15s`
- Volle Suite: `7955 passed, 38 skipped, 4 deselected, 22 warnings in 694.25s (0:11:34)`

## Geänderte Dateien

- simulation/browser_invarianten.py
- simulation/browser_pruefhaken.py
- simulation/browser_abnahme.py
- simulation/browser_stationen.py
- tests/test_browser_invarianten.py
- tests/test_browser_abnahme.py
- tests/test_browser_stationen.py
- tests/test_browser_lauf.py
- docs/agents/korpus-und-simulation.md
- simulation/berichte/sim-invarianten-2026-10-05.md
- .superpowers/sdd/final-fix-report.md (dieser Bericht)

## Anmerkungen

- Bei leerem Board meldet die Station `wissen` zwei nicht_pruefbar-Befunde (`chat_kennt_board_nicht` aus dem Prompt-Abgleich, `chat_nennt_board_nicht` aus der Antwort); beide gehören zur Zeile "Chat kennt Board nicht".
- `nicht_pruefbar` greift auch im Haken `zweite_gruppe`, wenn auf dem Gerät gar kein `vad_*` liegt (dieselbe reine Funktion).
- `test_kontext_ohne_werkbank` und `test_kontext_transkript_mehrheit_…` bekamen ein nicht-leeres Board, damit sie weiter genau ihren Teil prüfen.
- uv.lock tauchte auf und wurde gelöscht (nicht committet).

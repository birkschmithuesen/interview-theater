# Padua-Simulation: Birks Live-Befunde automatisch finden — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Browser-Simulation (`simulation/browser_*`) meldet die Fehlerklasse aus Birks Live-Test vom 05.10.2026 selbst als Befund „hoch“: Board-Schwelle, leeres Ende-Segment, Werkbank leer/Phase 2 gesperrt, Chat kennt Board/Transkript nicht, Raumcheck domainweit — gegen `cb200e4` gemeldet, gegen diesen Branch nicht mehr.

**Architecture:** Ein neues Modul `simulation/browser_invarianten.py` enthält deterministische Prüfungen (eigenes Lese-SQL, kein `repo`, damit auch ältere App-Stände prüfbar sind) und erzeugt `Befund`-Objekte mit Ursache „App oder Werkzeug – ungeklaert“. Der Harness bekommt `--app-wurzel` (App aus einem anderen Checkout starten, Harness bleibt dieser Branch), knappe/realistische Diskussionsskripte, Stationen mit Zielen statt Rezepten, eine Station-Liste `invarianten` mit Prüf-Haken (`pruefung`) und zwei Gruppen im selben Browser-Kontext. Ein Prompt-Abzug (`simulation/prompt_abzug.py`, läuft im App-Checkout gegen eine DB-Kopie) liefert den nächsten Gesprächsprompt für den mechanischen Abgleich „Der Chat weiß, was der Bildschirm zeigt“. `browser_abnahme` schreibt Invarianten-Abschnitt und Vorher/Nachher-Tabelle.

**Tech Stack:** Python 3.11, sqlite3 (read-only URI), Playwright (Chromium, Fake-Mic), espeak-ng, pytest.

**Spec:** `.cc-card.md` (Karte t_fc2c1bfa), Birks Befunde `/mnt/HC_Volume_106183673/hermes/profiles/birk/cache/scratch/birk-test-p12-0510.md` + `brief-p1-nachtrag1.md`.

## Global Constraints

- Arbeitsverzeichnis nur dieser Worktree (`.worktrees/robo-sim`, Branch `wt/robo-sim`). Commit nach jeder Task. Kein Merge, kein Push, `main` und andere Worktrees nicht anfassen.
- Live-Dienste (`interview-theater@*`, `interview-theater-*-web`, `padua-web`) nie starten/stoppen/neu starten. `betrieb/*.env` nie lesen außer über den bestehenden `--env-datei`/`IT_SIM_ENV`-Mechanismus.
- **Nicht ändern** (parallele Session `robo/p1-bleiben`): `interview_theater/erkenner.py`, `interview_theater/knoepfe/basis.py`, `interview_theater/knoepfe/texte.py`, `sprachen/en/texte.toml`. Dieser Plan ändert **keinen App-Code** unter `interview_theater/` — nur `simulation/`, `tests/`, `docs/`.
- EN = Padua-Sprache; Dortmund eingefroren, keine neuen Profilschalter.
- Bash: ein Kommando je Aufruf, kein `cd`, kein `&&`/`;`, kein `$VAR`, keine Schleifen, keine Pfade außerhalb des Worktrees (Ausnahme: die zwei Scratch-Dateien lesen).
- Testkommando exakt: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider <dateien>`. In Tasks nur gezielte Dateien. Browser-Tests mit `/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q -p no:cacheprovider <dateien>`.
- Eigene Skripte immer `uv run --extra dev python -m <modul>`.
- Vorbestehend rot auf 9780250, nicht unseres: `tests/test_flow_audit_dynamisch.py::test_station_01_eintritt_ohne_jargon_mit_cothinker_hinweis`.
- Echte Modellaufrufe (Persona/Richter über Opus-Proxy, Bot über Infomaniak inkl. Whisper) kosten Geld: nur in Task 8, kleinstes Stationsset, kein Wiederholungslauf ohne Codeänderung dazwischen.
- Befund-Ursache wörtlich: `App oder Werkzeug – ungeklaert` (Gedankenstrich U+2013).
- Frist nach „Discussion done“: 60 s (Karte).

## File Structure

| Datei | Verantwortung |
|---|---|
| `simulation/browser_invarianten.py` (neu) | `Befund`, DB-Lesestand Phase 1/2, alle deterministischen Prüfungen inkl. Kontext-Abgleich und Raumcheck-Schlüssel. Kein Playwright, kein Modell. |
| `simulation/prompt_abzug.py` (neu) | Kleines Skript, das **im App-Checkout** läuft (`PYTHONPATH=<app-wurzel>`) und den Gesprächsprompt für einen Zug als JSON auf stdout schreibt. |
| `simulation/browser_wissen.py` (neu) | Harness-Seite des Abzugs: DB-Kopie anlegen, `prompt_abzug` als Unterprozess starten, Ergebnis lesen. |
| `simulation/diskussionen.py` (neu) | `Diskussion`-Datensatz: Skriptdatei, erwartete Begriffe, Verhörer, Endpause; Registry `DISKUSSIONEN`. |
| `simulation/diskussion/p1-knapp.txt`, `p1-verhoerer.txt`, `p1-nachtrag.txt` (neu) | Die gesprochenen Skripte. |
| `simulation/erzeuge_diskussion_audio.py` | + `ende_pause_s`, + `dauer_s(wav)`. |
| `simulation/browser_umgebung.py` | + `app_wurzel`, + Code-Vorgaben (Board-Env entfernen), + zweite Gruppe. |
| `simulation/browser_stationen.py` | Ziele statt Rezepte; neue Felder `diskussion`, `pruefung`, `sage`, `gruppe`; Liste `STATIONEN_INVARIANTEN`. |
| `simulation/browser_lauf.py` | CLI `--app-wurzel`, `--stationen invarianten`, eindeutiger Laufordner; Prüf-Haken in `fuehre_stationen`; `ergebnis.json["invarianten"]`. |
| `simulation/browser_beobachter.py` | + `begriffe()` (sichtbare Board-Begriffe als Text). |
| `simulation/ux_rubrik.md` | Onboarding-Checkliste für den Richter. |
| `simulation/browser_abnahme.py` | Invarianten-Abschnitt, `urteil` berücksichtigt Invarianten, Unterbefehl `vergleich`. |
| `simulation/berichte/sim-invarianten-2026-10-05.md` (neu, Task 8) | Abnahmebericht mit Vorher/Nachher-Tabelle. |
| `docs/agents/korpus-und-simulation.md` | Kurzer Abschnitt „Invarianten“ (Task 8). |

---

### Task 1: App aus anderem Checkout starten, frischer Laufordner, Code-Vorgaben

Heute startet `browser_umgebung.starte_stack` Web und Bot immer aus `WURZEL` (dem Harness-Checkout). Für die Abnahme muss der **neue Harness** die **alte App** (`cb200e4`) starten.

**Files:**
- Modify: `simulation/browser_umgebung.py` (Konstante `WURZEL` ~Z.30, Bot-Wrapper ~Z.57–70, `baue_gruppe` ~Z.40–54, Web-/Bot-Start ~Z.96–138, `starte_stack` ~Z.169)
- Modify: `simulation/browser_lauf.py` (`main` ~Z.660–700: Argumente, Laufordner)
- Test: `tests/test_browser_umgebung.py`

**Interfaces:**
- Produces:
  - `starte_stack(env_datei, lauf_verzeichnis, *, app_wurzel: Path = WURZEL, gruppen: int = 1)` → das bisherige Stack-Objekt, zusätzlich Attribut `gruppen: list[Gruppe]` mit `Gruppe(token: str, chat_id: int)` (dataclass in `browser_umgebung`); bisherige Attribute `token`/`chat_id` bleiben = `gruppen[0]`.
  - `bot_skript(env_datei, *, modul_oder_datei: str, app_wurzel: Path) -> str` — der bash-Text, der die Env-Datei sourct, danach `unset` für `CODE_VORGABEN_ENTFERNEN`, dann `exec python …` ausführt. (Wenn es heute schon eine Funktion für den Wrapper gibt, diese erweitern statt neu bauen.)
  - `CODE_VORGABEN_ENTFERNEN = ("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "IT_BEGRIFFSBOARD_MIN_ABSTAND_S")` — Begründung im Kommentar: die Padua-Env enthält seit 05.10. 08:33 eine Sofortmaßnahme (`IT_BEGRIFFSBOARD_MIN_ZEICHEN=100`); die Simulation prüft die Code-Vorgaben, sonst sähe sie die Board-Schwelle nie.
  - `lauf_verzeichnis_fuer(basis: Path, datum: str, geraet: str, persona: str, stationen: str, jetzt: str) -> Path` in `browser_lauf` — hängt `-HHMMSS` an und ist damit je Lauf eindeutig (heute wird `sim.db` bei gleichem Tag/Argumenten wiederverwendet).

- [ ] **Step 1: Bestand lesen.** `simulation/browser_umgebung.py` ganz lesen; `tests/test_browser_umgebung.py` lesen. Notieren, wie der Bot-Wrapper heute gebaut wird und welche Funktion `baue_gruppe` heißt/zurückgibt.

- [ ] **Step 2: Failing tests schreiben** (in `tests/test_browser_umgebung.py` anhängen; an vorhandene Hilfsfunktionen anpassen, Namen wie unten):

```python
from pathlib import Path
from simulation import browser_umgebung as bu
from simulation import browser_lauf as bl


def test_bot_skript_entfernt_board_vorgaben_nach_dem_sourcen(tmp_path):
    env = tmp_path / "x.env"
    env.write_text("IT_BEGRIFFSBOARD_MIN_ZEICHEN=100\n")
    text = bu.bot_skript(env, modul_oder_datei="-m interview_theater.bot", app_wurzel=tmp_path)
    pos_source = text.index(str(env))
    for name in bu.CODE_VORGABEN_ENTFERNEN:
        assert text.index(f"unset {name}") > pos_source or f"unset {' '.join(bu.CODE_VORGABEN_ENTFERNEN)}" in text
    assert "exec " in text and "interview_theater.bot" in text


def test_bot_skript_nutzt_app_wurzel(tmp_path):
    app = tmp_path / "alt"
    app.mkdir()
    text = bu.bot_skript(tmp_path / "x.env", modul_oder_datei="-m interview_theater.bot", app_wurzel=app)
    assert str(app) in text


def test_lauf_verzeichnis_ist_je_lauf_eindeutig(tmp_path):
    a = bl.lauf_verzeichnis_fuer(tmp_path, "2026-10-05", "handy", "student", "invarianten", "101500")
    b = bl.lauf_verzeichnis_fuer(tmp_path, "2026-10-05", "handy", "student", "invarianten", "101501")
    assert a != b
    assert a.name.startswith("2026-10-05-handy-student-invarianten")
```

Zusätzlich einen Test, dass `starte_stack(..., gruppen=2)` zwei verschiedene Gruppen anlegt — **nur wenn** es in `tests/test_browser_umgebung.py` schon einen Test gibt, der `baue_gruppe` ohne Netz gegen eine tmp-DB aufruft; dann analog `baue_gruppe` zweimal aufrufen und `token`/`chat_id` verschieden prüfen. Sonst diesen Teil über Task 6 abdecken.

- [ ] **Step 3: Test laufen lassen, muss rot sein.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_umgebung.py`
Expected: FAIL (`bot_skript`/`CODE_VORGABEN_ENTFERNEN`/`lauf_verzeichnis_fuer` fehlen).

- [ ] **Step 4: Implementieren.**
  - `starte_stack` bekommt `app_wurzel` und reicht es an Web-Start (`cwd=app_wurzel`, `PYTHONPATH=str(app_wurzel)`) und Bot-Wrapper (`cd`-frei: `cwd=app_wurzel` im `Popen`, `PYTHONPATH` im Wrapper bzw. env) weiter. `baue_gruppe` darf weiter in-process mit dem Harness-`repo` gegen `sim.db` laufen (Schema wird nur additiv migriert; die alte App verträgt zusätzliche Spalten). Wenn die alte App beim Start das Schema anlegt und der Harness vorher schreibt: Reihenfolge so lassen wie heute.
  - `gruppen=n`: `baue_gruppe` n-mal; Liste `gruppen`.
  - Wrapper: nach `source`/`set -a … set +a` eine Zeile `unset IT_BEGRIFFSBOARD_MIN_ZEICHEN IT_BEGRIFFSBOARD_MIN_ABSTAND_S` (aus `CODE_VORGABEN_ENTFERNEN` gebaut), auch für den Web-Prozess, falls der die Env-Datei ebenfalls lädt.
  - `browser_lauf.main`: neues Argument `--app-wurzel` (Pfad, Vorgabe `browser_umgebung.WURZEL`), muss `interview_theater/` enthalten, sonst `SystemExit` mit Meldung. Laufordner über `lauf_verzeichnis_fuer(..., jetzt=datetime.now().strftime("%H%M%S"))`.
  - In `ergebnis.json` zusätzlich `"app_wurzel"` und `"app_commit"` (Ausgabe von `git -C <app_wurzel> rev-parse --short HEAD` per `subprocess.run`, bei Fehler `None`) speichern — dort, wo `ergebnis.json` heute geschrieben wird (`fuehre_stationen` ~Z.541–549), über einen neuen Parameter `meta: dict | None = None`.

- [ ] **Step 5: Tests grün.** Gleiches Kommando wie Step 3, dazu `tests/test_browser_lauf.py`. Expected: PASS.

- [ ] **Step 6: Commit.**
```bash
git add simulation/browser_umgebung.py simulation/browser_lauf.py tests/test_browser_umgebung.py
git commit -m "Simulation: App aus anderem Checkout starten (--app-wurzel), Code-Vorgaben fuer Board, Laufordner je Lauf"
```

---

### Task 2: Deterministische Invarianten (Phase 1/2, Symptomregel, Raumcheck, Verhörer)

**Files:**
- Create: `simulation/browser_invarianten.py`
- Test: `tests/test_browser_invarianten.py`

**Interfaces:**
- Produces (exakt diese Namen; spätere Tasks verlassen sich darauf):
  - `URSACHE_UNGEKLAERT: str`, `FRIST_NACH_ENDE_S = 60.0`, `GRUPPENSCHLUESSEL_PRAEFIXE = ("vad_",)`
  - `@dataclass(frozen=True) Befund(schluessel: str, station: str, text: str, schwere: str = "hoch", ursache: str = URSACHE_UNGEKLAERT)` mit `als_dict() -> dict`
  - `@dataclass(frozen=True) P1Stand(board_begriffe: tuple[str,...], board_zeilen: int, transkript_zeichen: int, ende_leer: bool, arbeitsstand_begriffe: str, max_bot_id: int, bot_ids: tuple[int,...])`
  - `oeffne_lesend(db_pfad) -> sqlite3.Connection`
  - `board_begriffe_aus_json(roh: str | None) -> tuple[str, ...]`
  - `lese_p1_stand(conn, chat_id: int) -> P1Stand`
  - `pruefe_nach_diskussion(vorher: P1Stand, nachher: P1Stand, station: str) -> list[Befund]`
  - `warte_nach_diskussion(db_pfad, chat_id, vorher: P1Stand, station, *, frist_s=FRIST_NACH_ENDE_S, takt_s=2.0, schlafe=time.sleep, uhr=time.monotonic) -> tuple[list[Befund], P1Stand]`
  - `pruefe_station_erreicht(station: str, fertig: bool) -> list[Befund]`
  - `pruefe_beobachter(verlauf: list[int], station: str) -> list[Befund]`
  - `pruefe_raumcheck_schluessel(schluessel: list[str], token: str, station: str) -> list[Befund]`
  - `pruefe_verhoerer(board_begriffe, verhoerer: dict[str, str], station: str) -> list[Befund]`
  - `zaehle_fragen(text: str | None) -> int`, `pruefe_p2_werkbank(fragen_text: str | None, sichtbare_fragen: int | None, station: str) -> list[Befund]`
  - Befund-Schlüssel (Konstanten): `BOARD_LEER = "board_leer_nach_ende"`, `STILLE_LEERES_ENDE = "stille_nach_leerem_ende"`, `STILLE_NACH_ENDE = "stille_nach_ende"`, `WERKBANK_LEER = "werkbank_leer_phase2_gesperrt"`, `RAUMCHECK_DOMAINWEIT = "raumcheck_domainweit"`, `VERHOERER = "verhoerer_nicht_korrigiert"`, `P2_FRAGEN_FEHLEN = "p2_fragen_fehlen"`, `P2_ZAEHLER = "p2_zaehler_inkonsistent"`, `BOARD_BEOBACHTER_LEER = "board_beobachter_leer"`, Präfix `STATION_NICHT_ERREICHT = "station_nicht_erreicht"` (Schlüssel `f"{STATION_NICHT_ERREICHT}:{station}"`).

- [ ] **Step 1: Schema an beiden Ständen prüfen.** Die Prüfungen sollen gegen `cb200e4` **und** HEAD laufen. Lesen:
  - `git show cb200e4:interview_theater/db.py` und `interview_theater/db.py`: Spalten von `aufnahme` (Name der Transkript-Spalte, Status-Spalte, `diskussion`, `schnittgrund`), `begriffsboard` (`id, chat_id, json`), `arbeitsstand.begriffe`, `nachricht` (`ist_bot`).
  - Wo die Web-Chatansicht **Bot-Blasen** herliest (Tabelle `web_post` vs. `nachricht` mit `ist_bot=1`) — in `interview_theater/web_kanal.py`/`web_chat.py` an beiden Ständen. Die Bot-IDs in `P1Stand.bot_ids` kommen aus **der** Tabelle, die der Browser anzeigt (Ziel: „eine Bot-Nachricht kam“). Spalten-/Tabellennamen in Code und Test-Fixture unten entsprechend einsetzen, wenn sie abweichen.
  - JSON-Form von `begriffsboard.json` an beiden Ständen (`git show cb200e4:interview_theater/begriffsboard.py`): Liste von Einträgen oder Objekt mit Liste.
  - `phasen.voraussetzungen` an beiden Ständen: Phase 2 hängt nur an `arbeitsstand.begriffe` (HEAD ~Z.394). Falls `cb200e4` anders entscheidet, im Docstring vermerken.

- [ ] **Step 2: Failing tests schreiben** `tests/test_browser_invarianten.py` (Fixture-Schema minimal, Spaltennamen nach Step 1 angleichen):

```python
import json
import sqlite3

import pytest

from simulation import browser_invarianten as inv


@pytest.fixture
def db(tmp_path):
    pfad = tmp_path / "sim.db"
    conn = sqlite3.connect(pfad)
    conn.executescript(
        """
        CREATE TABLE begriffsboard (id INTEGER PRIMARY KEY, chat_id INTEGER, json TEXT);
        CREATE TABLE aufnahme (id INTEGER PRIMARY KEY, chat_id INTEGER, diskussion INTEGER,
                               schnittgrund TEXT, transkript TEXT, status TEXT);
        CREATE TABLE arbeitsstand (chat_id INTEGER PRIMARY KEY, begriffe TEXT);
        CREATE TABLE nachricht (id INTEGER PRIMARY KEY, chat_id INTEGER, ist_bot INTEGER, text TEXT);
        """
    )
    conn.commit()
    conn.close()
    return pfad


def _schreibe(pfad, sql, *werte):
    conn = sqlite3.connect(pfad)
    conn.execute(sql, werte)
    conn.commit()
    conn.close()


def _stand(pfad, chat_id=7):
    with inv.oeffne_lesend(pfad) as conn:
        return inv.lese_p1_stand(conn, chat_id)


def test_board_json_ohne_verworfene():
    roh = json.dumps([
        {"begriff": "home", "status": "favorit"},
        {"begriff": "noise", "status": "verworfen"},
        {"begriff": "border", "status": "kandidat"},
    ])
    assert inv.board_begriffe_aus_json(roh) == ("home", "border")
    assert inv.board_begriffe_aus_json(json.dumps({"begriffe": [{"begriff": "x"}]})) == ("x",)
    assert inv.board_begriffe_aus_json(None) == ()
    assert inv.board_begriffe_aus_json("kaputt") == ()


def test_knappe_diskussion_ohne_board_ist_befund_board_leer(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because we miss it', 'fertig')")
    nachher = _stand(db)
    befunde = inv.pruefe_nach_diskussion(vorher, nachher, "p1-zuhoeren")
    schluessel = {b.schluessel for b in befunde}
    assert inv.BOARD_LEER in schluessel
    assert inv.WERKBANK_LEER in schluessel
    assert inv.STILLE_NACH_ENDE in schluessel
    assert all(b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT for b in befunde)
    board = next(b for b in befunde if b.schluessel == inv.BOARD_LEER)
    assert "23 Zeichen" in board.text  # Zeichenzahl des Transkripts steht im Text


def test_leeres_ende_segment_ohne_bot_nachricht(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because', 'fertig')")
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'ende', '', 'fertig')")
    nachher = _stand(db)
    assert nachher.ende_leer is True
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert inv.STILLE_LEERES_ENDE in schluessel
    assert inv.STILLE_NACH_ENDE not in schluessel


def test_gesunder_abschluss_ohne_befund(db):
    _schreibe(db, "INSERT INTO nachricht VALUES (1, 7, 1, 'welcome')")
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'home because we miss it', 'fertig')")
    _schreibe(db, "INSERT INTO begriffsboard VALUES (1, 7, ?)", json.dumps([{"begriff": "home", "status": "kandidat"}]))
    _schreibe(db, "INSERT INTO arbeitsstand VALUES (7, 'home')")
    _schreibe(db, "INSERT INTO nachricht VALUES (2, 7, 1, 'These are your five terms')")
    nachher = _stand(db)
    assert inv.pruefe_nach_diskussion(vorher, nachher, "s") == []


def test_bot_nachricht_vor_dem_ende_zaehlt_nicht(db):
    _schreibe(db, "INSERT INTO nachricht VALUES (1, 7, 1, 'old')")
    vorher = _stand(db)
    nachher = _stand(db)
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}


def test_andere_gruppe_zaehlt_nicht(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO nachricht VALUES (1, 8, 1, 'other group')")
    _schreibe(db, "INSERT INTO arbeitsstand VALUES (8, 'home')")
    nachher = _stand(db)
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert {inv.STILLE_NACH_ENDE, inv.WERKBANK_LEER} <= schluessel


def test_warten_bricht_ab_sobald_alles_gut(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'home', 'fertig')")
    zeit = [0.0]
    aufrufe = []

    def schlafe(s):
        aufrufe.append(s)
        zeit[0] += s
        _schreibe(db, "INSERT INTO begriffsboard VALUES (NULL, 7, ?)", json.dumps([{"begriff": "home"}]))
        _schreibe(db, "INSERT OR REPLACE INTO arbeitsstand VALUES (7, 'home')")
        _schreibe(db, "INSERT INTO nachricht VALUES (NULL, 7, 1, 'saved')")

    befunde, stand = inv.warte_nach_diskussion(db, 7, vorher, "s", schlafe=schlafe, uhr=lambda: zeit[0])
    assert befunde == []
    assert len(aufrufe) == 1
    assert stand.board_begriffe == ("home",)


def test_warten_meldet_nach_frist(db):
    vorher = _stand(db)
    zeit = [0.0]

    def schlafe(s):
        zeit[0] += s

    befunde, _ = inv.warte_nach_diskussion(db, 7, vorher, "s", frist_s=6, takt_s=2, schlafe=schlafe, uhr=lambda: zeit[0])
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in befunde}
    assert zeit[0] >= 6


def test_symptomregel_station_nicht_erreicht():
    (b,) = inv.pruefe_station_erreicht("p1-begriffe", False)
    assert b.schluessel == "station_nicht_erreicht:p1-begriffe"
    assert b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT
    assert inv.pruefe_station_erreicht("p1-begriffe", True) == []


def test_symptomregel_beobachter_sah_nie_einen_begriff():
    assert inv.pruefe_beobachter([0, 0, 0], "p1-zuhoeren")[0].schluessel == inv.BOARD_BEOBACHTER_LEER
    assert inv.pruefe_beobachter([], "p1-zuhoeren")[0].schluessel == inv.BOARD_BEOBACHTER_LEER
    assert inv.pruefe_beobachter([0, 3], "p1-zuhoeren") == []


def test_raumcheck_ohne_gruppenschluessel_ist_domainweit():
    alt = ["vad_boden_mess", "vad_rede_mess", "vad_schwelle", "theme"]
    (b,) = inv.pruefe_raumcheck_schluessel(alt, "tok123", "p1-kalibrierung")
    assert b.schluessel == inv.RAUMCHECK_DOMAINWEIT
    assert "vad_schwelle" in b.text
    neu = ["vad_schwelle:tok123:2026-10-05", "vad_boden_mess:tok123:2026-10-05"]
    assert inv.pruefe_raumcheck_schluessel(neu, "tok123", "s") == []


def test_raumcheck_ohne_messung_meldet_nichts():
    assert inv.pruefe_raumcheck_schluessel(["theme"], "tok", "s") == []


def test_verhoerer_nicht_korrigiert():
    (b,) = inv.pruefe_verhoerer(("Night shed", "home"), {"night shed": "night shift"}, "s")
    assert b.schluessel == inv.VERHOERER
    assert b.schwere == "mittel"
    assert inv.pruefe_verhoerer(("night shift",), {"night shed": "night shift"}, "s") == []
    assert inv.pruefe_verhoerer((), {"night shed": "night shift"}, "s") == []


def test_p2_werkbank():
    assert inv.zaehle_fragen("1. Why?\n2. How?\n\n") == 2
    assert inv.zaehle_fragen(None) == 0
    assert inv.pruefe_p2_werkbank("", None, "s")[0].schluessel == inv.P2_FRAGEN_FEHLEN
    assert inv.pruefe_p2_werkbank("1. Why?\n2. How?", 3, "s")[0].schluessel == inv.P2_ZAEHLER
    assert inv.pruefe_p2_werkbank("1. Why?\n2. How?", 2, "s") == []
    assert inv.pruefe_p2_werkbank("1. Why?", None, "s") == []
```

Hinweis zu `zaehle_fragen`: vorher in Step 1 nachsehen, in welcher Form `arbeitsstand.fragen` gespeichert ist (Zeilen? JSON?). Ist es JSON, `zaehle_fragen` so bauen, dass es JSON-Listen zählt und sonst nicht-leere Zeilen; den Test um einen JSON-Fall ergänzen.

- [ ] **Step 3: Rot prüfen.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_invarianten.py`
Expected: FAIL (`ModuleNotFoundError: simulation.browser_invarianten`).

- [ ] **Step 4: Implementieren** `simulation/browser_invarianten.py`:

```python
"""Deterministische Invarianten der Browser-Simulation — kein Richter, kein Modell.

Karte t_fc2c1bfa (05.10.2026): ein Symptom ist ein App-Fehler bis zum
Gegenbeweis. Jede verletzte Invariante wird ein Befund "hoch" mit der Ursache
"App oder Werkzeug – ungeklaert" und wird nie still als Werkzeugmangel
abgehakt (der Abnahmebericht vom 04.10. zeigte 165-mal "0 Begriffe" und
erklaerte es weg).

Liest die Simulations-DB nur lesend und mit eigenem SQL statt ueber `repo`:
die Simulation prueft auch aeltere App-Staende (Abnahme gegen cb200e4), deren
Funktionen vom Harness-Stand abweichen. "Phase 2 moeglich" ist hier
gleichbedeutend mit "arbeitsstand.begriffe gesetzt" (phasen.voraussetzungen).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

URSACHE_UNGEKLAERT = "App oder Werkzeug – ungeklaert"
FRIST_NACH_ENDE_S = 60.0
GRUPPENSCHLUESSEL_PRAEFIXE = ("vad_",)

BOARD_LEER = "board_leer_nach_ende"
STILLE_LEERES_ENDE = "stille_nach_leerem_ende"
STILLE_NACH_ENDE = "stille_nach_ende"
WERKBANK_LEER = "werkbank_leer_phase2_gesperrt"
RAUMCHECK_DOMAINWEIT = "raumcheck_domainweit"
VERHOERER = "verhoerer_nicht_korrigiert"
P2_FRAGEN_FEHLEN = "p2_fragen_fehlen"
P2_ZAEHLER = "p2_zaehler_inkonsistent"
BOARD_BEOBACHTER_LEER = "board_beobachter_leer"
STATION_NICHT_ERREICHT = "station_nicht_erreicht"


@dataclass(frozen=True)
class Befund:
    schluessel: str
    station: str
    text: str
    schwere: str = "hoch"
    ursache: str = URSACHE_UNGEKLAERT

    def als_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class P1Stand:
    board_begriffe: tuple[str, ...]
    board_zeilen: int
    transkript_zeichen: int
    ende_leer: bool
    arbeitsstand_begriffe: str
    max_bot_id: int
    bot_ids: tuple[int, ...]


def oeffne_lesend(db_pfad) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_pfad)}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def board_begriffe_aus_json(roh: str | None) -> tuple[str, ...]:
    try:
        daten = json.loads(roh or "[]")
    except ValueError:
        return ()
    if isinstance(daten, dict):
        daten = daten.get("begriffe", [])
    if not isinstance(daten, list):
        return ()
    return tuple(
        str(e["begriff"]).strip()
        for e in daten
        if isinstance(e, dict)
        and e.get("status") != "verworfen"
        and str(e.get("begriff") or "").strip()
    )


def lese_p1_stand(conn: sqlite3.Connection, chat_id: int) -> P1Stand:
    letzte = conn.execute(
        "SELECT json FROM begriffsboard WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,)
    ).fetchone()
    board_zeilen = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    aufnahmen = conn.execute(
        "SELECT transkript, schnittgrund FROM aufnahme WHERE chat_id = ? AND diskussion = 1 ORDER BY id",
        (chat_id,),
    ).fetchall()
    stand = conn.execute("SELECT begriffe FROM arbeitsstand WHERE chat_id = ?", (chat_id,)).fetchone()
    bot_ids = tuple(
        z[0]
        for z in conn.execute(
            "SELECT id FROM nachricht WHERE chat_id = ? AND ist_bot = 1 ORDER BY id", (chat_id,)
        )
    )
    ende = [a for a in aufnahmen if a["schnittgrund"] == "ende"]
    return P1Stand(
        board_begriffe=board_begriffe_aus_json(letzte["json"] if letzte else None),
        board_zeilen=board_zeilen,
        transkript_zeichen=sum(len((a["transkript"] or "").strip()) for a in aufnahmen),
        ende_leer=bool(ende) and not (ende[-1]["transkript"] or "").strip(),
        arbeitsstand_begriffe=(stand["begriffe"] or "") if stand else "",
        max_bot_id=max(bot_ids, default=0),
        bot_ids=bot_ids,
    )


def pruefe_nach_diskussion(vorher: P1Stand, nachher: P1Stand, station: str) -> list[Befund]:
    befunde: list[Befund] = []
    if nachher.transkript_zeichen > 0 and not nachher.board_begriffe:
        befunde.append(Befund(
            BOARD_LEER, station,
            f"Nach 'Discussion done' ist das Board leer, obwohl {nachher.transkript_zeichen} Zeichen "
            f"transkribiert sind ({nachher.board_zeilen} Board-Laeufe).",
        ))
    if not any(i > vorher.max_bot_id for i in nachher.bot_ids):
        if nachher.ende_leer:
            befunde.append(Befund(
                STILLE_LEERES_ENDE, station,
                "Nach 'Discussion done' kam keine Bot-Nachricht; das Ende-Segment war leer.",
            ))
        else:
            befunde.append(Befund(STILLE_NACH_ENDE, station, "Nach 'Discussion done' kam keine Bot-Nachricht."))
    if not nachher.arbeitsstand_begriffe.strip():
        befunde.append(Befund(
            WERKBANK_LEER, station,
            "arbeitsstand.begriffe ist leer: die Werkbank zeigt keine Begriffe, Phase 2 ist gesperrt.",
        ))
    return befunde


def warte_nach_diskussion(
    db_pfad, chat_id: int, vorher: P1Stand, station: str, *,
    frist_s: float = FRIST_NACH_ENDE_S, takt_s: float = 2.0,
    schlafe: Callable[[float], None] = time.sleep, uhr: Callable[[], float] = time.monotonic,
) -> tuple[list[Befund], P1Stand]:
    ende = uhr() + frist_s
    while True:
        with oeffne_lesend(db_pfad) as conn:
            stand = lese_p1_stand(conn, chat_id)
        befunde = pruefe_nach_diskussion(vorher, stand, station)
        if not befunde or uhr() >= ende:
            return befunde, stand
        schlafe(takt_s)


def pruefe_station_erreicht(station: str, fertig: bool) -> list[Befund]:
    if fertig:
        return []
    return [Befund(f"{STATION_NICHT_ERREICHT}:{station}", station,
                   f"Station {station} nicht erreicht (Ziel nicht erfuellt).")]


def pruefe_beobachter(verlauf: list[int], station: str) -> list[Befund]:
    if verlauf and max(verlauf) > 0:
        return []
    return [Befund(BOARD_BEOBACHTER_LEER, station,
                   f"Das zweite Geraet sah nie einen Begriff im CoThinker (Verlauf {verlauf or '[]'}).")]


def pruefe_raumcheck_schluessel(schluessel: list[str], token: str, station: str) -> list[Befund]:
    offen = sorted(
        k for k in schluessel
        if k.startswith(GRUPPENSCHLUESSEL_PRAEFIXE) and token not in k
    )
    if not offen:
        return []
    return [Befund(RAUMCHECK_DOMAINWEIT, station,
                   "Raumcheck-Messung liegt ohne Gruppenbezug im localStorage (gilt fuer die ganze Domain, "
                   f"also auch fuer andere Gruppen): {', '.join(offen)}.")]


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def pruefe_verhoerer(board_begriffe, verhoerer: dict[str, str], station: str) -> list[Befund]:
    board = [_norm(b) for b in board_begriffe]
    befunde = []
    for falsch, richtig in verhoerer.items():
        hat_falsch = any(_norm(falsch) in b for b in board)
        hat_richtig = any(_norm(richtig) in b for b in board)
        if hat_falsch and not hat_richtig:
            befunde.append(Befund(VERHOERER, station,
                                  f"Verhoerer '{falsch}' steht im Board, '{richtig}' nicht (Kontextsatz nicht genutzt).",
                                  schwere="mittel"))
    return befunde


def zaehle_fragen(text: str | None) -> int:
    if not text or not text.strip():
        return 0
    try:
        daten = json.loads(text)
    except ValueError:
        daten = None
    if isinstance(daten, list):
        return len(daten)
    return sum(1 for z in text.splitlines() if z.strip())


def pruefe_p2_werkbank(fragen_text: str | None, sichtbare_fragen: int | None, station: str) -> list[Befund]:
    zahl = zaehle_fragen(fragen_text)
    if zahl == 0:
        return [Befund(P2_FRAGEN_FEHLEN, station, "arbeitsstand.fragen ist leer: keine Fragen in der Werkbank.")]
    if sichtbare_fragen is not None and sichtbare_fragen != zahl:
        return [Befund(P2_ZAEHLER, station,
                       f"Werkbank zeigt {sichtbare_fragen} Fragen, gespeichert sind {zahl}.")]
    return []
```

Spalten-/Tabellennamen aus Step 1 einsetzen. Wenn Bot-Blasen aus `web_post` kommen, `bot_ids` aus `web_post` (eigene `chat_id`-Spalte) lesen und Fixture/Tests (Tabelle `nachricht` → `web_post`) gleich mitändern.

- [ ] **Step 5: Grün.** Kommando aus Step 3. Expected: PASS.

- [ ] **Step 6: Commit.**
```bash
git add simulation/browser_invarianten.py tests/test_browser_invarianten.py
git commit -m "Simulation: deterministische Invarianten (Board, Abschluss, Werkbank, Raumcheck, Verhoerer, P2) mit Symptomregel"
```

---

### Task 3: „Der Chat weiß, was der Bildschirm zeigt“ — Prompt-Abzug und Abgleich

Es gibt keinen Laufzeit-Prompt-Dump in der App. Der Harness rekonstruiert den Prompt des nächsten Gesprächszugs mit dem `kontext` **des App-Checkouts** gegen eine **Kopie** der Sim-DB (die App-Funktion könnte schreiben).

**Files:**
- Create: `simulation/prompt_abzug.py`, `simulation/browser_wissen.py`
- Modify: `simulation/browser_invarianten.py` (Abgleich-Funktionen)
- Modify: `simulation/browser_beobachter.py` (+ `begriffe()`)
- Test: `tests/test_browser_wissen.py`, `tests/test_browser_invarianten.py`

**Interfaces:**
- Consumes: `Befund`, `URSACHE_UNGEKLAERT`, `_norm` aus Task 2; `bot_skript`/Env-Mechanik aus Task 1 (Env-Datei sourcen + `CODE_VORGABEN_ENTFERNEN`).
- Produces:
  - In `browser_invarianten`: `@dataclass(frozen=True) Sichtbar(board: tuple[str,...] = (), transkripte: tuple[str,...] = (), werkbank: tuple[str,...] = ())`; `pruefe_kontext(prompt: str, sichtbar: Sichtbar, station: str) -> list[Befund]`; `pruefe_wissensantwort(antwort: str, board: tuple[str,...], station: str) -> list[Befund]`; Schlüssel `CHAT_KENNT_BOARD_NICHT = "chat_kennt_board_nicht"`, `CHAT_KENNT_TRANSKRIPT_NICHT = "chat_kennt_transkript_nicht"`, `CHAT_KENNT_WERKBANK_NICHT = "chat_kennt_werkbank_nicht"`, `CHAT_NENNT_BOARD_NICHT = "chat_nennt_board_nicht"`; `WISSENSFRAGE = "Which terms are on the CoThinker right now?"`.
  - `simulation/prompt_abzug.py`: `main(argv: list[str] | None = None) -> int`; Argumente `--db PFAD --chat-id N --text TEXT`; schreibt `{"prompt": "<system>\n\n<nutzer>"}` als eine JSON-Zeile auf stdout.
  - `simulation/browser_wissen.py`: `kopiere_db(quelle: Path, ziel: Path) -> Path` (sqlite3-Backup-API, sicher bei WAL); `hole_prompt(*, app_wurzel: Path, env_datei: Path, db: Path, chat_id: int, text: str, arbeitsordner: Path, ausfuehren=subprocess.run) -> str`.
  - `Beobachter.begriffe() -> tuple[str, ...]` (Text der sichtbaren `li[data-begriff]`, Attributwert bevorzugt, sonst `inner_text`).

- [ ] **Step 1: `kontext.baue` an beiden Ständen lesen.** `git show cb200e4:interview_theater/kontext.py` und `interview_theater/kontext.py`: Signatur von `baue` und Rückgabeform (Nachrichtenliste? Tupel system/nutzer?), welche Verbindung/Setup sie braucht (`db.verbinde`? `einstellungen`?), ob sie schreibt. `prompt_abzug.py` muss mit **beiden** Signaturen funktionieren — wenn sie sich unterscheiden, über `inspect.signature` die passenden Argumente wählen. Außerdem nachsehen, wie `scripts/erzeuge_prompts.py` (`schreibe_dump` ~Z.171) `kontext.baue` aufruft — das ist die Vorlage.

- [ ] **Step 2: Failing tests** in `tests/test_browser_invarianten.py` anhängen:

```python
def test_kontext_kennt_alles():
    prompt = "Board: home, border\nThe group said: we miss home because of the border\nWorkbench terms: home"
    s = inv.Sichtbar(board=("home", "border"), transkripte=("We miss home because of the border.",), werkbank=("home",))
    assert inv.pruefe_kontext(prompt, s, "p1-wissen") == []


def test_kontext_ohne_board_und_transkript():
    prompt = "You are a helpful workshop bot. [voice message]"
    s = inv.Sichtbar(board=("home", "border"), transkripte=("We miss home because of the border.", "Noise at night"))
    schluessel = {b.schluessel for b in inv.pruefe_kontext(prompt, s, "p1-wissen")}
    assert schluessel == {inv.CHAT_KENNT_BOARD_NICHT, inv.CHAT_KENNT_TRANSKRIPT_NICHT}


def test_kontext_transkript_mehrheit_reicht_und_normalisiert():
    prompt = "we  MISS home because of the border"
    s = inv.Sichtbar(transkripte=("We miss home because of the border.", "Noise at night keeps us awake"))
    assert inv.pruefe_kontext(prompt, s, "s") == []  # 1 von 2 = Hälfte reicht
    s3 = inv.Sichtbar(transkripte=("We miss home because of the border.", "Noise at night", "Waiting rooms"))
    assert inv.pruefe_kontext(prompt, s3, "s")[0].schluessel == inv.CHAT_KENNT_TRANSKRIPT_NICHT


def test_kontext_leer_sichtbar_kein_befund():
    assert inv.pruefe_kontext("", inv.Sichtbar(), "s") == []


def test_wissensantwort():
    board = ("home", "border", "noise", "night shift")
    assert inv.pruefe_wissensantwort("On the CoThinker: home, border and noise.", board, "s") == []
    (b,) = inv.pruefe_wissensantwort("I can't see the cothinker page from here.", board, "s")
    assert b.schluessel == inv.CHAT_NENNT_BOARD_NICHT
    assert inv.pruefe_wissensantwort("home", ("home",), "s") == []
```

`tests/test_browser_wissen.py`:

```python
import json
import sqlite3
import subprocess

from simulation import browser_wissen as bw


def test_kopiere_db_ist_eigenstaendig(tmp_path):
    quelle = tmp_path / "a.db"
    conn = sqlite3.connect(quelle)
    conn.execute("CREATE TABLE t (x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    ziel = bw.kopiere_db(quelle, tmp_path / "b.db")
    assert sqlite3.connect(ziel).execute("SELECT x FROM t").fetchone() == (1,)
    assert ziel != quelle


def test_hole_prompt_ruft_abzug_im_app_checkout(tmp_path):
    aufrufe = []

    def ausfuehren(args, **kw):
        aufrufe.append((args, kw))
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"prompt": "SYSTEM\n\nNUTZER"}) + "\n", stderr="")

    db = tmp_path / "sim.db"
    sqlite3.connect(db).close()
    app = tmp_path / "app"
    app.mkdir()
    prompt = bw.hole_prompt(app_wurzel=app, env_datei=tmp_path / "x.env", db=db, chat_id=7,
                            text="Which terms?", arbeitsordner=tmp_path, ausfuehren=ausfuehren)
    assert prompt == "SYSTEM\n\nNUTZER"
    (args, kw), = aufrufe
    befehl = " ".join(args)
    assert "prompt_abzug" in befehl and "--chat-id" in befehl and "7" in befehl
    assert str(db) not in befehl  # gegen die Kopie, nie gegen die laufende DB
    assert kw.get("cwd") == app or str(app) in befehl


def test_hole_prompt_fehler_wird_laut(tmp_path):
    def ausfuehren(args, **kw):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="Traceback ...")

    db = tmp_path / "sim.db"
    sqlite3.connect(db).close()
    try:
        bw.hole_prompt(app_wurzel=tmp_path, env_datei=tmp_path / "x.env", db=db, chat_id=7,
                       text="x", arbeitsordner=tmp_path, ausfuehren=ausfuehren)
    except RuntimeError as e:
        assert "Traceback" in str(e)
    else:
        raise AssertionError("Fehler muss laut sein")
```

Plus ein echter Integrationstest ohne Netz und ohne Modell (in `tests/test_browser_wissen.py`): Sim-DB über `interview_theater.db` (aktueller Stand) anlegen, Gruppe wie `browser_umgebung.baue_gruppe` anlegen, `IT_WORKSHOP=padua-2026` setzen, `prompt_abzug.main(["--db", ..., "--chat-id", ..., "--text", "hello"])` in-process mit `capsys` aufrufen und prüfen, dass JSON mit nicht-leerem `"prompt"` kommt. Env-Variablen über `monkeypatch.setenv`; Sprachwahl so, wie `scripts/erzeuge_prompts_padua_voll.py` sie setzt.

- [ ] **Step 3: Rot prüfen.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_invarianten.py tests/test_browser_wissen.py`
Expected: FAIL.

- [ ] **Step 4: Implementieren.**

In `browser_invarianten.py` anhängen:

```python
CHAT_KENNT_BOARD_NICHT = "chat_kennt_board_nicht"
CHAT_KENNT_TRANSKRIPT_NICHT = "chat_kennt_transkript_nicht"
CHAT_KENNT_WERKBANK_NICHT = "chat_kennt_werkbank_nicht"
CHAT_NENNT_BOARD_NICHT = "chat_nennt_board_nicht"
WISSENSFRAGE = "Which terms are on the CoThinker right now?"
TRANSKRIPT_PROBE_ZEICHEN = 30


@dataclass(frozen=True)
class Sichtbar:
    board: tuple[str, ...] = ()
    transkripte: tuple[str, ...] = ()
    werkbank: tuple[str, ...] = ()


def _norm_satz(text: str) -> str:
    erlaubt = "".join(c if c.isalnum() or c.isspace() else " " for c in text.casefold())
    return " ".join(erlaubt.split())


def _fehlend(begriffe, prompt_n: str) -> list[str]:
    return [b for b in begriffe if _norm_satz(b) and _norm_satz(b) not in prompt_n]


def pruefe_kontext(prompt: str, sichtbar: Sichtbar, station: str) -> list[Befund]:
    p = _norm_satz(prompt)
    befunde = []
    fehlt = _fehlend(sichtbar.board, p)
    if fehlt:
        befunde.append(Befund(CHAT_KENNT_BOARD_NICHT, station,
                              f"CoThinker zeigt {len(sichtbar.board)} Begriffe, im Gespraechsprompt fehlen: {', '.join(fehlt)}."))
    proben = [_norm_satz(t)[:TRANSKRIPT_PROBE_ZEICHEN] for t in sichtbar.transkripte if _norm_satz(t)]
    if proben:
        gefunden = sum(1 for pr in proben if pr in p)
        if gefunden * 2 < len(proben):
            befunde.append(Befund(CHAT_KENNT_TRANSKRIPT_NICHT, station,
                                  f"Von {len(proben)} sichtbaren Transkript-Blasen stehen nur {gefunden} im Gespraechsprompt."))
    fehlt = _fehlend(sichtbar.werkbank, p)
    if fehlt:
        befunde.append(Befund(CHAT_KENNT_WERKBANK_NICHT, station,
                              f"Werkbank zeigt Begriffe, die im Gespraechsprompt fehlen: {', '.join(fehlt)}."))
    return befunde


def pruefe_wissensantwort(antwort: str, board: tuple[str, ...], station: str) -> list[Befund]:
    if not board:
        return []
    a = _norm_satz(antwort)
    genannt = [b for b in board if _norm_satz(b) in a]
    noetig = min(3, len(board))
    if len(genannt) >= noetig:
        return []
    return [Befund(CHAT_NENNT_BOARD_NICHT, station,
                   f"Auf '{WISSENSFRAGE}' nennt der Bot {len(genannt)} von {len(board)} Board-Begriffen "
                   f"(noetig {noetig}): {antwort[:160]!r}")]
```

`simulation/prompt_abzug.py` (läuft im App-Checkout, importiert nur `interview_theater` und die Standardbibliothek, **kein** `simulation`-Import):

```python
"""Gespraechsprompt eines Zugs als JSON auf stdout — fuer den Abgleich der Simulation.

Laeuft als Unterprozess mit PYTHONPATH=<app-wurzel>, damit `interview_theater`
aus dem geprueften App-Stand kommt (auch cb200e4), und immer gegen eine KOPIE
der Simulations-DB. Importiert nichts aus `simulation`.
"""
```

Inhalt nach Step 1: DB öffnen wie `scripts/erzeuge_prompts.py`, `kontext.baue(...)` mit den an diesem Stand gültigen Argumenten aufrufen (Text des Zugs = `--text`), Ergebnis zu einem String „system + Leerzeile + nutzer“ (bei Nachrichtenliste: alle `content` mit `\n\n` verbinden) machen und `print(json.dumps({"prompt": ...}))`. Rückgabe 0.

`simulation/browser_wissen.py`:

```python
"""Harness-Seite des Prompt-Abzugs: DB kopieren, Abzug im App-Checkout starten."""

from __future__ import annotations

import json
import shlex
import sqlite3
import subprocess
from pathlib import Path

from simulation import browser_umgebung

ABZUG = Path(__file__).resolve().parent / "prompt_abzug.py"


def kopiere_db(quelle: Path, ziel: Path) -> Path:
    with sqlite3.connect(f"file:{quelle}?mode=ro", uri=True) as alt, sqlite3.connect(ziel) as neu:
        alt.backup(neu)
    return ziel


def hole_prompt(*, app_wurzel: Path, env_datei: Path, db: Path, chat_id: int, text: str,
                arbeitsordner: Path, ausfuehren=subprocess.run) -> str:
    kopie = kopiere_db(db, Path(arbeitsordner) / f"abzug-{chat_id}.db")
    aufruf = f"{shlex.quote(str(ABZUG))} --db {shlex.quote(str(kopie))} --chat-id {chat_id} --text {shlex.quote(text)}"
    skript = browser_umgebung.bot_skript(env_datei, modul_oder_datei=aufruf, app_wurzel=app_wurzel)
    ergebnis = ausfuehren(["bash", "-c", skript], cwd=app_wurzel, capture_output=True, text=True, timeout=120)
    if ergebnis.returncode != 0:
        raise RuntimeError(f"prompt_abzug fehlgeschlagen: {ergebnis.stderr[-2000:]}")
    return json.loads(ergebnis.stdout.strip().splitlines()[-1])["prompt"]
```

Anpassen, falls `bot_skript` in Task 1 eine andere Aufrufform bekam (der Kern: Env sourcen, Board-Vorgaben entfernen, `exec python <abzug> …` mit `PYTHONPATH=<app_wurzel>`). Wenn `prompt_abzug` selbst Modelle anstoßen würde (z. B. Kürzung über Modell), das im Abzug abschalten bzw. gegen Attrappe laufen lassen — der Abzug darf **kein Geld** kosten; in Step 1 klären.

`Beobachter.begriffe()` in `browser_beobachter.py`: die Selektorlogik aus `messe()` wiederverwenden.

- [ ] **Step 5: Grün.** Kommando aus Step 3, dazu `tests/test_browser_beobachter.py` mit dem Playwright-Python (`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q -p no:cacheprovider tests/test_browser_beobachter.py`). Expected: PASS.

- [ ] **Step 6: Abzug gegen cb200e4 einmal trocken prüfen (kein Modell, kein Geld).** Nur wenn in Task 8 ohnehin gebraucht — hier lediglich: `git show cb200e4:interview_theater/kontext.py` wurde in Step 1 gelesen und `prompt_abzug` deckt die Signatur ab (im Commit-Text vermerken).

- [ ] **Step 7: Commit.**
```bash
git add simulation/browser_invarianten.py simulation/prompt_abzug.py simulation/browser_wissen.py simulation/browser_beobachter.py tests/test_browser_invarianten.py tests/test_browser_wissen.py
git commit -m "Simulation: Chat-Wissen mechanisch pruefen (Prompt-Abzug im App-Checkout, Board/Transkript/Werkbank, Wissensfrage)"
```

---

### Task 4: Realistisches Sprechen — knappe Skripte, leeres Ende-Segment, Verhörer, mehrere Diskussionen

**Files:**
- Create: `simulation/diskussionen.py`, `simulation/diskussion/p1-knapp.txt`, `simulation/diskussion/p1-verhoerer.txt`, `simulation/diskussion/p1-nachtrag.txt`
- Modify: `simulation/erzeuge_diskussion_audio.py`
- Test: `tests/test_diskussionen.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Diskussion(name: str, datei: Path, erwartete_begriffe: tuple[str,...], verhoerer: dict[str,str] = field(default_factory=dict), ende_pause_s: float = 0.0)` mit `text() -> str` (Skript ohne Sprecherpräfixe, so wie gesprochen) und `zeichen() -> int`.
  - `DISKUSSIONEN: dict[str, Diskussion]` mit Schlüsseln `"lang"` (bestehendes `p1-diskussion.txt`), `"knapp"`, `"verhoerer"`, `"nachtrag"`.
  - `erzeuge(skript: Path, wav: Path, *, ende_pause_s: float = 0.0) -> Path` (bestehende Funktion erweitern, Default ändert nichts), `dauer_s(wav: Path) -> float`.

- [ ] **Step 1: Bestand lesen:** `simulation/erzeuge_diskussion_audio.py` (Format der Skriptzeilen „A: …“, Pausenlogik ~Z.14–37), `simulation/diskussion/p1-diskussion.txt`.

- [ ] **Step 2: Skripte schreiben** (Format wie `p1-diskussion.txt`, Sprecher A–D):

`simulation/diskussion/p1-knapp.txt` — Birks Live-Fall: knappe Begriffsnennung, jeder Begriff mit kurzem Grund, **gesamt < 300 Zeichen gesprochener Text**:
```
A: Home. Because we all left one.
B: Border. We crossed many.
C: Waiting. Papers take months.
D: Noise. The camp is never quiet.
A: Language. Italian is hard.
```

`simulation/diskussion/p1-verhoerer.txt` — lang (> 600 Zeichen, damit das Board auch an `cb200e4` läuft und „Chat kennt Board“ prüfbar wird), mit eingebautem Verhörer samt Kontextsatz:
```
A: I want night shed as a term. I mean the night shift, my mother works nights at the hospital and sleeps all day.
B: Yes, the night shift. Nobody sees those people, but the city runs on them.
C: For me it is belonging. You can live somewhere ten years and still not belong there.
D: Belonging, yes. And language, because without the language you never really belong.
A: Language is good. When I speak Italian people answer me in English, and that hurts a bit.
B: Then I add waiting. We waited for papers, for the doctor, for the bus, always waiting.
C: Waiting is strong. And it fits the night shift too, waiting for the morning.
D: So our terms are night shift, belonging, language and waiting. I think that is our list.
```
(`verhoerer = {"night shed": "night shift"}`, erwartete Begriffe night shift, belonging, language, waiting.) Liegt `zeichen()` knapp unter 600, eine weitere Zeile im selben Ton anhängen, bis der Test `> 600` grün ist.

`simulation/diskussion/p1-nachtrag.txt` — dritte, kurze Runde in derselben Gruppe:
```
B: One more term. Noise. The camp is never quiet at night.
C: Yes, add noise.
```

- [ ] **Step 3: Failing tests** `tests/test_diskussionen.py`:

```python
import wave

import pytest

from simulation import diskussionen as d
from simulation import erzeuge_diskussion_audio as audio


def test_registry_und_dateien():
    assert {"lang", "knapp", "verhoerer", "nachtrag"} <= set(d.DISKUSSIONEN)
    for disk in d.DISKUSSIONEN.values():
        assert disk.datei.is_file(), disk.datei


def test_knapp_liegt_unter_der_alten_schwelle():
    assert d.DISKUSSIONEN["knapp"].zeichen() < 300
    assert d.DISKUSSIONEN["knapp"].ende_pause_s >= 6.0  # leeres Ende-Segment provozieren


def test_verhoerer_skript_ist_lang_und_traegt_kontext():
    disk = d.DISKUSSIONEN["verhoerer"]
    assert disk.zeichen() > 600
    assert disk.verhoerer == {"night shed": "night shift"}
    assert "night shed" in disk.text().casefold() and "night shift" in disk.text().casefold()


def test_text_ohne_sprecherpraefix():
    assert not d.DISKUSSIONEN["knapp"].text().startswith("A:")


@pytest.mark.skipif(not audio.verfuegbar(), reason="espeak-ng fehlt")
def test_endpause_verlaengert_die_datei(tmp_path):
    ohne = audio.erzeuge(d.DISKUSSIONEN["nachtrag"].datei, tmp_path / "a.wav")
    mit = audio.erzeuge(d.DISKUSSIONEN["nachtrag"].datei, tmp_path / "b.wav", ende_pause_s=6.0)
    assert audio.dauer_s(mit) - audio.dauer_s(ohne) == pytest.approx(6.0, abs=0.2)
```

Wenn `erzeuge_diskussion_audio` keine Funktion `verfuegbar()` hat: eine kleine hinzufügen (`try: import espeakng_loader … return True except Exception: return False`) — oder die Prüfung nehmen, die vorhandene Tests (`tests/test_browser_probe.py` o. ä.) schon nutzen.

- [ ] **Step 4: Rot prüfen.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_diskussionen.py`
Expected: FAIL.

- [ ] **Step 5: Implementieren.** `simulation/diskussionen.py`:

```python
"""Gesprochene Diskussionsskripte der Simulation (Karte t_fc2c1bfa, Punkt 4).

Neben dem langen Skript sprechen Gruppen live knapp: "Home. Because …" —
zusammen weniger Zeichen als die alte Board-Schwelle (600). `knapp` endet mit
einer Pause laenger als der VAD-Schnitt (2,5 s), sodass das Ende-Segment beim
Druck auf "Discussion done" leer ist (Birks Nachtrag D). `verhoerer` traegt
einen absichtlich falschen Begriff mit Kontextsatz; das Board soll ihn
korrigieren.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "diskussion"
_SPRECHER = re.compile(r"^\s*[A-Z]:\s*")


@dataclass(frozen=True)
class Diskussion:
    name: str
    datei: Path
    erwartete_begriffe: tuple[str, ...]
    verhoerer: dict[str, str] = field(default_factory=dict)
    ende_pause_s: float = 0.0

    def text(self) -> str:
        zeilen = [_SPRECHER.sub("", z).strip() for z in self.datei.read_text(encoding="utf-8").splitlines()]
        return " ".join(z for z in zeilen if z)

    def zeichen(self) -> int:
        return len(self.text())


DISKUSSIONEN: dict[str, Diskussion] = {
    "lang": Diskussion("lang", ORDNER / "p1-diskussion.txt",
                       ("home", "border", "waiting", "noise", "night shift", "belonging", "language")),
    "knapp": Diskussion("knapp", ORDNER / "p1-knapp.txt",
                        ("home", "border", "waiting", "noise", "language"), ende_pause_s=8.0),
    "verhoerer": Diskussion("verhoerer", ORDNER / "p1-verhoerer.txt",
                            ("night shift", "belonging", "language", "waiting"),
                            verhoerer={"night shed": "night shift"}),
    "nachtrag": Diskussion("nachtrag", ORDNER / "p1-nachtrag.txt", ("noise",), ende_pause_s=8.0),
}
```

`erzeuge(..., ende_pause_s=0.0)`: am Ende Stille der Länge `ende_pause_s` in derselben Abtastrate anhängen. `dauer_s(wav)`: `with wave.open(str(wav)) as w: return w.getnframes() / w.getframerate()`.

- [ ] **Step 6: Grün.** Kommando aus Step 4, dazu bestehende Tests, die `erzeuge_diskussion_audio` nutzen (mit `grep -l erzeuge_diskussion_audio tests` finden). Expected: PASS.

- [ ] **Step 7: Commit.**
```bash
git add simulation/diskussionen.py simulation/diskussion/p1-knapp.txt simulation/diskussion/p1-verhoerer.txt simulation/diskussion/p1-nachtrag.txt simulation/erzeuge_diskussion_audio.py tests/test_diskussionen.py
git commit -m "Simulation: knappe Begriffsnennung, leeres Ende-Segment, Verhoerer mit Kontext, Nachtrag-Diskussion"
```

---

### Task 5: Stationen mit Zielen statt Rezepten, Station-Liste `invarianten`, Onboarding-Rubrik

**Files:**
- Modify: `simulation/browser_stationen.py` (`Station` ~Z.28–43, `STATIONEN_P12` ~Z.78–134)
- Modify: `simulation/ux_rubrik.md`
- Test: `tests/test_browser_stationen.py`, `tests/test_browser_judge.py`

**Interfaces:**
- Consumes: `diskussionen.DISKUSSIONEN` (Task 4), `browser_invarianten.WISSENSFRAGE` (Task 3).
- Produces:
  - Neue `Station`-Felder (alle mit Vorgabe, bestehende Stationen bleiben gültig): `diskussion: str | None = None` (Schlüssel in `DISKUSSIONEN`), `pruefung: tuple[str, ...] = ()` (Werte aus `PRUEFUNGEN`), `sage: str | None = None` (Text, den der Harness selbst schickt; Station ohne Persona), `gruppe: int = 1`.
  - `PRUEFUNGEN = ("nach_ende", "wissen", "raumcheck", "zweite_gruppe", "verhoerer", "p2_werkbank")`.
  - `STATIONEN_INVARIANTEN: tuple[Station, ...]` und `STATIONSLISTEN = {"p12": STATIONEN_P12, "invarianten": STATIONEN_INVARIANTEN}` (falls es schon eine Auswahl-Map gibt: dort eintragen).

- [ ] **Step 1: Bestand lesen:** `simulation/browser_stationen.py`, `tests/test_browser_stationen.py`, `simulation/ux_rubrik.md`, `tests/test_browser_judge.py`.

- [ ] **Step 2: Failing tests** in `tests/test_browser_stationen.py` anhängen:

```python
import re

from simulation import browser_stationen as bs
from simulation import browser_invarianten as inv
from simulation.diskussionen import DISKUSSIONEN

REZEPT = re.compile(r"\b(with the button|undo button|press the|click the|tap the|save them)\b", re.I)


def test_ziele_statt_rezepte_in_beiden_listen():
    for liste in (bs.STATIONEN_P12, bs.STATIONEN_INVARIANTEN):
        for st in liste:
            if st.schluessel in {"p1-zuhoeren", "p1-zuhoeren-2", "p1-zuhoeren-3"}:
                continue  # 'Start listening' ist hier die Aufgabe selbst
            assert not REZEPT.search(st.ziel), (st.schluessel, st.ziel)


def test_p1_begriffe_ist_ein_ziel():
    st = next(s for s in bs.STATIONEN_P12 if s.schluessel == "p1-begriffe")
    assert "workbench" in st.ziel.casefold()
    assert "button" not in st.ziel.casefold()


def test_invarianten_liste_deckt_die_abnahme():
    liste = bs.STATIONEN_INVARIANTEN
    pruefungen = {p for st in liste for p in st.pruefung}
    assert {"nach_ende", "wissen", "raumcheck", "zweite_gruppe", "verhoerer"} <= pruefungen
    diskussionen = [st.diskussion for st in liste if st.diskussion]
    assert diskussionen[0] == "knapp"
    assert len(diskussionen) >= 3  # erste, zweite, dritte Diskussion in derselben Gruppe
    assert all(d in DISKUSSIONEN for d in diskussionen)
    assert any(st.gruppe == 2 for st in liste)
    wissen = next(st for st in liste if "wissen" in st.pruefung)
    assert wissen.sage == inv.WISSENSFRAGE
    assert all(p in bs.PRUEFUNGEN for p in pruefungen)


def test_p12_prueft_nach_ende_und_p2_werkbank():
    p12 = {st.schluessel: st for st in bs.STATIONEN_P12}
    assert "nach_ende" in p12["p1-zuhoeren"].pruefung
    assert "p2_werkbank" in p12["p2-einzeldurchgang"].pruefung
```

In `tests/test_browser_judge.py` anhängen (Rubrik-Pfad wie in vorhandenen Tests):

```python
def test_rubrik_hat_onboarding_checkliste():
    text = RUBRIK_PFAD.read_text(encoding="utf-8")  # Namen an vorhandenen Test angleichen
    for stichwort in ("two phones", "CoThinker", "room check", "first step", "phone card", "web app", "Telegram"):
        assert stichwort.casefold() in text.casefold(), stichwort
```

Bestehende Tests, die alte Zieltexte wörtlich prüfen, an die neuen Texte anpassen (nicht löschen).

- [ ] **Step 3: Rot prüfen.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_stationen.py tests/test_browser_judge.py`
Expected: FAIL.

- [ ] **Step 4: Implementieren.**

Zieltexte in `STATIONEN_P12` ersetzen:
- `p1-begriffe`: `"Get the terms from your discussion into the workbench and move on to the next phase."` — `fertig` bleibt (`arbeitsstand.begriffe and begriffe_detail`), `pruefung=()`.
- `p1-uebergang`: `"Move on to the next phase once your terms are in place."`
- `p1-zuhoeren`: Ziel unverändert, `pruefung=("nach_ende",)`.
- `p2-einzeldurchgang`: Ziel `"Make sure the question list for your interviews is the one your group wants, then check it in the workbench."`, `pruefung=("p2_werkbank",)`.
- `p1-kalibrierung`: `"The app wants to check the room before you start. Get through the room check; if it fails twice, skip it."`

`STATIONEN_INVARIANTEN` (kleinstes Set, das die Abnahme trägt — Reihenfolge ist Programm):

| schluessel | phase | gruppe | ziel | diskussion | pruefung | sage | sonst |
|---|---|---|---|---|---|---|---|
| `p1-eintritt` | 1 | 1 | wie in P12 | – | – | – | budget 3 (Richter sieht Begrüßung → Onboarding-Checkliste) |
| `p1-kalibrierung` | 1 | 1 | neuer Text oben | – | `("raumcheck",)` | – | `fertig` wie P12, budget 6 |
| `p1-zweite-gruppe` | 1 | 2 | `"Observe the app of the second group for 20 seconds."` | – | `("zweite_gruppe",)` | – | `ohne_persona=True`, `warte_s=20` |
| `p1-zuhoeren` | 1 | 1 | P12-Text | `"knapp"` | `("nach_ende",)` | – | `zuhoeren_s=None` (aus WAV-Dauer, Task 6), `fertig` wie P12 |
| `p1-zuhoeren-2` | 1 | 1 | `"Your group discusses a second time. Start listening again, put the phone down; when told, end the discussion."` | `"verhoerer"` | `("nach_ende", "verhoerer")` | – | wie oben |
| `p1-wissen` | 1 | 1 | `"Ask the bot what is on the CoThinker."` | – | `("wissen",)` | `inv.WISSENSFRAGE` | `ohne_persona=True` |
| `p1-zuhoeren-3` | 1 | 1 | `"One more short round: start listening, add one term, end the discussion."` | `"nachtrag"` | `("nach_ende",)` | – | wie oben |
| `p1-begriffe` | 1 | 1 | neuer P12-Text | – | – | – | `endet_bei_phasenwechsel=True`, budget 6, `fertig = phase>=2` |

`zuhoeren_s`: wenn `diskussion` gesetzt ist, darf `zuhoeren_s` `None` sein — die Engine (Task 6) nimmt dann `dauer_s(wav) + 5`.

`ux_rubrik.md`: neuer Abschnitt am Ende (Englisch, wie die Rubrik — falls die Rubrik deutsch ist, deutsch mit den englischen Stichwörtern):

```markdown
## Onboarding checklist (first contact, phase 1)

Rate as "hoch" if any of these is missing in the first screens:

1. **Two phones:** the welcome explains that phone A lies in the middle (chat, "Start listening") and phone B shows the CoThinker tab.
2. **Room check:** before the first discussion the group learns that the app first measures the room noise, and what to press for it.
3. **First step:** the welcome ends with one clear first step, not a row of shortcut buttons.
4. **Phone card:** the phone card ("How to set up your phones") matches the tabs that really exist in the web app.
5. **Web app, not Telegram:** the bot explains only controls that exist in the web app (no Telegram commands, no "/start", no "send a voice message" when listening is the way).
6. **Reasons, not just words:** the group is asked to say each term with one sentence why it matters.
```

- [ ] **Step 5: Grün.** Kommando aus Step 3. Expected: PASS.

- [ ] **Step 6: Commit.**
```bash
git add simulation/browser_stationen.py simulation/ux_rubrik.md tests/test_browser_stationen.py tests/test_browser_judge.py
git commit -m "Simulation: Ziele statt Rezepte, Stationsliste invarianten, Onboarding-Checkliste fuer den Richter"
```

---

### Task 6: Engine — Prüf-Haken, zweite Gruppe, Diskussion je Station, `ergebnis.json["invarianten"]`

**Files:**
- Modify: `simulation/browser_lauf.py` (`fuehre_stationen` ~Z.437–550, `_beende_diskussion_deterministisch` ~Z.112–125/369–397, `main` ~Z.660–791)
- Modify: `simulation/browser_probe.py` nur falls für Audiowechsel nötig (`chromium_argumente`)
- Test: `tests/test_browser_lauf.py`

**Interfaces:**
- Consumes: Task 1 `starte_stack(..., app_wurzel, gruppen)` / `Gruppe`; Task 2 alle `pruefe_*`, `lese_p1_stand`, `warte_nach_diskussion`, `P1Stand`; Task 3 `Sichtbar`, `pruefe_kontext`, `pruefe_wissensantwort`, `browser_wissen.hole_prompt`, `Beobachter.begriffe()`; Task 4 `DISKUSSIONEN`, `erzeuge`, `dauer_s`; Task 5 Station-Felder, `STATIONSLISTEN`.
- Produces:
  - `ergebnis.json` bekommt `"invarianten": [Befund.als_dict(), …]` (Reihenfolge des Auftretens) und `"app_commit"`/`"app_wurzel"` (Task 1).
  - CLI: `--stationen {p12,invarianten}`.
  - Hilfsfunktionen in `browser_lauf` (testbar ohne Browser, Abhängigkeiten als Parameter): `sichtbares(page, beobachter) -> Sichtbar`, `speicher_schluessel(page) -> list[str]` (`page.evaluate("Object.keys(localStorage)")`), `fuehre_pruefungen(station, kontext: PruefKontext) -> list[Befund]` mit `PruefKontext` (dataclass: `db_pfad`, `gruppen`, `page`, `beobachter`, `vorher: P1Stand | None`, `antwort: str | None`, `hole_prompt: Callable[[int, str], str]`, `warte: Callable` = `warte_nach_diskussion`).

Verhalten je Prüfung:
- **Symptomregel (immer, jede Station):** nach der Station `pruefe_station_erreicht(st.schluessel, fertig)`; nach der Station mit `nach_ende` zusätzlich `pruefe_beobachter(beobachter_verlauf_der_station, st.schluessel)`. Nichts davon wird wegen eines Harness-Fehlers unterdrückt — auch bei Ausnahme in der Station wird `station_nicht_erreicht` gemeldet (Ausnahmetext in den Befundtext).
- **`nach_ende`:** `vorher = lese_p1_stand(...)` direkt **vor** dem Klick auf „Discussion done“ (in `_beende_diskussion_deterministisch` bzw. unmittelbar davor), danach `warte_nach_diskussion(db, chat_id, vorher, station)` (60 s).
- **`verhoerer`:** `pruefe_verhoerer(stand.board_begriffe, DISKUSSIONEN[st.diskussion].verhoerer, …)` mit dem Stand aus `nach_ende`.
- **`wissen`:** Harness schickt `st.sage` als Gruppen-Nachricht (wie die Persona tippt: dieselbe Aktion aus `browser_aktionen`), **vorher** `prompt = hole_prompt(chat_id, st.sage)` (Prompt des Zugs, den der Bot gleich baut), `sichtbar = sichtbares(page, beobachter)`, dann `pruefe_kontext(prompt, sichtbar, …)`; nach `warte_auf_antwort` die Bot-Antwort → `pruefe_wissensantwort(antwort, sichtbar.board, …)`. Prompt in den Laufordner schreiben (`prompt-<station>.txt`) als Beleg. `sichtbar.transkripte` = Text der Gruppen-Transkript-Blasen im Chat (Selektor in `interview_theater/web_chat.py`/`web_vereint.py` nachsehen, an `cb200e4` gegenprüfen mit `git show`); `sichtbar.werkbank` = Begriffe im Werkbank-Tab (Selektor ebenso; Tab-Wechsel nur im Beobachter-Kontext, damit die Persona-Seite nicht springt — wenn das nicht geht, Werkbank aus `arbeitsstand.begriffe` nehmen und im Befundtext „(aus DB)“ vermerken).
- **`raumcheck`:** nach der Station `pruefe_raumcheck_schluessel(speicher_schluessel(page), gruppen[0].token, …)`.
- **`zweite_gruppe`:** **dieselbe** `page` (derselbe Browser-Kontext) `goto` auf `/g/<gruppen[1].token>`, `warte_s` beobachten, `pruefe_raumcheck_schluessel(speicher_schluessel(page), gruppen[1].token, …)` (meldet Schlüssel, die die zweite Gruppe von der ersten erbt), Screenshot, dann zurück auf Gruppe 1. Zusätzlich DOM-Hinweis notieren (Text „Measure again“ sichtbar ohne Messung in Gruppe 2 → in den Befundtext).
- **`p2_werkbank`:** `pruefe_p2_werkbank(datenstand["arbeitsstand"]["fragen"], sichtbare_fragen, …)`; `sichtbare_fragen` aus dem Werkbank-Tab des Beobachters zählen, wenn ein Selektor existiert, sonst `None`.
- **Diskussion je Station:** WAV je `st.diskussion` erzeugen (`erzeuge(..., ende_pause_s=disk.ende_pause_s)`), Zuhördauer = `st.zuhoeren_s or dauer_s(wav) + 5`. Chromium nimmt die Fake-Audio-Datei nur beim **Browserstart** (`--use-file-for-fake-audio-capture`). Vorgehen: zuerst prüfen (einmal, kurz, ohne Modell — z. B. mit dem bestehenden Playwright-Testserver in `tests/test_browser_lauf_*`), ob ein erneutes `getUserMedia` dieselbe Datei von vorn abspielt. Wenn ja: alle Skripte einer Station-Liste vorab zu **einer** Datei verketten ist nicht nötig — stattdessen je Diskussion eine eigene Datei nur, wenn ein Browser-Neustart erfolgt. Robust und ausreichend: **bei jeder Station mit `diskussion` den Persona-Browser neu starten** mit der passenden WAV, `storage_state` des alten Kontexts übernehmen (`context.storage_state()` → `browser.new_context(storage_state=…)`), dieselbe URL öffnen. Der Beobachter-Kontext bleibt. Die Raumcheck-Prüfungen laufen vor dem ersten Neustart, Storage geht über `storage_state` mit.

- [ ] **Step 1: Bestand lesen:** `simulation/browser_lauf.py` ganz, `tests/test_browser_lauf.py` (Attrappen `_LLMAttrappe`, `_ScriptedClient`, `_FakeJudge`, In-Process-Server).

- [ ] **Step 2: Failing tests** in `tests/test_browser_lauf.py` (Muster der vorhandenen Tests übernehmen, mit In-Process-Server und Attrappen; Playwright-Tests laufen mit dem Playwright-Python):
  1. `test_invarianten_landen_in_ergebnis_json`: eine Station `p1-zuhoeren`-artig mit `pruefung=("nach_ende",)` und einer Attrappe für `warte` (gibt `[Befund(BOARD_LEER, …)]` zurück) → `ergebnis.json["invarianten"][0]["schluessel"] == "board_leer_nach_ende"` und `schwere == "hoch"`, `ursache == "App oder Werkzeug – ungeklaert"`.
  2. `test_station_nicht_erreicht_wird_befund_hoch`: Station mit `fertig=lambda s: False`, budget 1 → Befund `station_nicht_erreicht:<schluessel>`.
  3. `test_ausnahme_in_station_wird_befund_nicht_verschluckt`: Persona-Attrappe wirft → Befund `station_nicht_erreicht:…`, Text enthält den Ausnahmetext.
  4. `test_zweite_gruppe_selber_kontext`: zwei Gruppen im In-Process-Server, Station `gruppe=2` mit `pruefung=("zweite_gruppe",)`; vor der Station per `page.evaluate("localStorage.setItem('vad_schwelle','0.1')")` einen alten Schlüssel setzen → Befund `raumcheck_domainweit`; mit Schlüssel `vad_schwelle:<token2>:2026-10-05` kein Befund.
  5. `test_wissen_vergleicht_prompt_und_antwort`: `hole_prompt`-Attrappe gibt `"no board here"` zurück, Beobachter-Attrappe zeigt `("home","border")`, Bot-Attrappe antwortet `"I can't see it"` → Befunde `chat_kennt_board_nicht` und `chat_nennt_board_nicht`; mit Prompt `"home border"` und Antwort `"home and border"` keine.
  6. `test_fuehre_pruefungen_ohne_browser`: reine Einheit für `fuehre_pruefungen` mit `PruefKontext`-Attrappen für `raumcheck` und `verhoerer`.

  Die genauen Fixture-Namen aus der Datei übernehmen; wo eine Prüfung echtes Audio bräuchte, `warte`/`hole_prompt` als Attrappe einsetzen.

- [ ] **Step 3: Rot prüfen.**
Run: `/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q -p no:cacheprovider tests/test_browser_lauf.py`
Expected: die neuen Tests FAIL, die alten PASS.

- [ ] **Step 4: Implementieren** wie unter „Verhalten je Prüfung“. `main`: `--stationen` wählt aus `STATIONSLISTEN`; `gruppen = max(st.gruppe for st in liste)` an `starte_stack`; `--app-wurzel` durchreichen; `hole_prompt` als `functools.partial(browser_wissen.hole_prompt, app_wurzel=…, env_datei=…, db=…, arbeitsordner=lauf_verzeichnis)`. `ergebnis.json["top_befunde"]` bleibt (Richter), `invarianten` kommt daneben.

- [ ] **Step 5: Grün.** Kommando aus Step 3 und
`uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_stationen.py tests/test_browser_invarianten.py tests/test_browser_wissen.py tests/test_browser_umgebung.py`
Expected: PASS.

- [ ] **Step 6: Commit.**
```bash
git add simulation/browser_lauf.py simulation/browser_probe.py tests/test_browser_lauf.py
git commit -m "Simulation: Pruef-Haken je Station, zweite Gruppe im selben Kontext, Diskussion je Station, invarianten in ergebnis.json"
```
(`browser_probe.py` nur, wenn geändert.)

---

### Task 7: Bericht — Invarianten-Abschnitt, Urteil, Vorher/Nachher-Tabelle

**Files:**
- Modify: `simulation/browser_abnahme.py` (`urteil` ~Z.30, `baue_abnahme` ~Z.213, CLI)
- Test: `tests/test_browser_abnahme.py`

**Interfaces:**
- Consumes: `ergebnis.json["invarianten"]` (Liste von `Befund.als_dict()`), `"app_commit"`.
- Produces:
  - `ABNAHME_BEFUNDE: tuple[tuple[str, tuple[str, ...]], ...]` — Zeilen der Abnahmetabelle, je (Label, Schlüssel, die die Zeile erfüllen):
    ```python
    ABNAHME_BEFUNDE = (
        ("Board-Schwelle (Board leer trotz Transkript)", ("board_leer_nach_ende", "board_beobachter_leer")),
        ("Leeres Ende-Segment (Stille nach Discussion done)", ("stille_nach_leerem_ende",)),
        ("Werkbank leer / Phase 2 gesperrt", ("werkbank_leer_phase2_gesperrt",)),
        ("Chat kennt Board nicht", ("chat_kennt_board_nicht", "chat_nennt_board_nicht")),
        ("Chat kennt Transkript nicht", ("chat_kennt_transkript_nicht",)),
        ("Raumcheck domainweit", ("raumcheck_domainweit",)),
    )
    ```
  - `invarianten_abschnitt(laeufe: list[dict]) -> str` (Markdown; „hoch“ zuerst, je Befund: Schwere, Gerät/Lauf, Station, Text, Ursache).
  - `urteil(...)` liefert „nein“, sobald ein Lauf eine Invariante mit `schwere == "hoch"` hat (Grund nennt den ersten Schlüssel).
  - `vergleichstabelle(vorher: dict, nachher: dict) -> str` — Kopf `| Befund | vorher (<commit>) | nachher (<commit>) | erwartet |`, je Zeile aus `ABNAHME_BEFUNDE` „gemeldet (hoch)“ / „–“, Spalte erwartet „vorher gemeldet, nachher weg“, plus Zeile „Abnahme erfüllt: ja/nein“; danach weitere Schlüssel, die nachher noch auftreten, als „Restbefunde nachher“.
  - CLI-Unterbefehl: `python -m simulation.browser_abnahme vergleich --vorher <laufordner> --nachher <laufordner> --ausgabe <md>`; `bericht` bekommt den Invarianten-Abschnitt automatisch.

- [ ] **Step 1: Bestand lesen:** `simulation/browser_abnahme.py`, `tests/test_browser_abnahme.py`.

- [ ] **Step 2: Failing tests** in `tests/test_browser_abnahme.py`:

```python
from simulation import browser_abnahme as ba


def _lauf(commit, *schluessel):
    return {"app_commit": commit, "invarianten": [
        {"schluessel": s, "station": "p1-zuhoeren", "text": f"t {s}", "schwere": "hoch",
         "ursache": "App oder Werkzeug – ungeklaert"} for s in schluessel]}


def test_vergleich_abnahme_erfuellt():
    vorher = _lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende", "werkbank_leer_phase2_gesperrt",
                   "chat_kennt_board_nicht", "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    nachher = _lauf("abc1234")
    md = ba.vergleichstabelle(vorher, nachher)
    assert "| Befund | vorher (cb200e4) | nachher (abc1234) |" in md
    assert md.count("gemeldet (hoch)") == 6
    assert "Abnahme erfüllt: ja" in md


def test_vergleich_abnahme_nicht_erfuellt_wenn_nachher_noch_da():
    vorher = _lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende", "werkbank_leer_phase2_gesperrt",
                   "chat_kennt_board_nicht", "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    nachher = _lauf("abc1234", "raumcheck_domainweit", "station_nicht_erreicht:p1-begriffe")
    md = ba.vergleichstabelle(vorher, nachher)
    assert "Abnahme erfüllt: nein" in md
    assert "station_nicht_erreicht:p1-begriffe" in md  # Restbefunde nachher


def test_invarianten_abschnitt_und_urteil():
    lauf = _lauf("cb200e4", "werkbank_leer_phase2_gesperrt")
    md = ba.invarianten_abschnitt([lauf])
    assert "werkbank_leer_phase2_gesperrt" in md and "App oder Werkzeug – ungeklaert" in md and "hoch" in md
```

Plus ein Test, dass `urteil` bei einem Lauf mit Invariante „hoch“ „nein“ liefert — Aufruf an die vorhandene `urteil`-Signatur anpassen (Bestand in Step 1).

- [ ] **Step 3: Rot prüfen.**
Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_browser_abnahme.py`
Expected: FAIL.

- [ ] **Step 4: Implementieren** wie unter Interfaces. `vergleich` liest `ergebnis.json` aus beiden Laufordnern.

- [ ] **Step 5: Grün.** Kommando aus Step 3. Expected: PASS.

- [ ] **Step 6: Commit.**
```bash
git add simulation/browser_abnahme.py tests/test_browser_abnahme.py
git commit -m "Simulation-Bericht: Invarianten-Abschnitt, Urteil nein bei Invariante hoch, Vorher/Nachher-Tabelle"
```

---

### Task 8: Abnahmeläufe cb200e4 vs. Branch, Bericht, Doku, Aufräumen

Kostet Geld (Persona/Richter über Opus-Proxy, Bot-Modelle + Whisper über Infomaniak). **Je ein Lauf vorher, ein Lauf nachher**, Gerät `handy`, Persona `student`, `--stationen invarianten`. Kein Wiederholungslauf ohne Codeänderung dazwischen.

**Files:**
- Create: `simulation/berichte/sim-invarianten-2026-10-05.md`
- Modify: `docs/agents/korpus-und-simulation.md` (Abschnitt „Invarianten der Browser-Simulation“, ≤ 25 Zeilen: Zweck, Befund-Schlüssel, `--app-wurzel`, `--stationen invarianten`, `vergleich`, Symptomregel)
- Ggf. `.gitignore`, falls `simulation/berichte/` den neuen Bericht ausschließt (nur diese eine Datei freigeben).

- [ ] **Step 1: Volle Suite einmal** (Vordergrund, Timeout 900000 ms):
`uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider`
Expected: grün bis auf das bekannte rote `test_flow_audit_dynamisch.py::test_station_01_eintritt_ohne_jargon_mit_cothinker_hinweis`. Neue Rote erst beheben.

- [ ] **Step 2: Env-Datei ermitteln:** `printenv IT_SIM_ENV` — leer → beim Controller nachfragen (nicht raten, keine `betrieb/*.env` lesen).

- [ ] **Step 3: Alten Stand bereitstellen:**
`git worktree add --detach .worktrees/sim-cb200e4 cb200e4`

- [ ] **Step 4: Lauf vorher** (Harness = dieser Branch, App = cb200e4):
`uv run --extra dev python -m simulation.browser_lauf --env-datei <pfad> --geraet handy --persona student --stationen invarianten --app-wurzel .worktrees/sim-cb200e4 --bericht`
Laufordner notieren. Expected in `ergebnis.json["invarianten"]`: mindestens die sechs Abnahme-Schlüssel (Tabelle Task 7). Fehlt einer: Ursache klären (Harness vs. App), **nicht** wegdefinieren; Harness fixen, gezielte Tests, Commit, erst dann neuer Lauf.

- [ ] **Step 5: Lauf nachher** (App = dieser Branch = gefixter main 9780250):
`uv run --extra dev python -m simulation.browser_lauf --env-datei <pfad> --geraet handy --persona student --stationen invarianten --bericht`
Expected: keiner der sechs Abnahme-Schlüssel. Bleibt einer: prüfen, ob App-Fehler (→ offener Punkt, kein App-Fix in diesem Auftrag, besonders nicht in den vier gesperrten Dateien) oder Harness-Fehler (→ fixen, Commit, neuer Lauf).

- [ ] **Step 6: Vergleich schreiben:**
`uv run --extra dev python -m simulation.browser_abnahme vergleich --vorher <lauf-vorher> --nachher <lauf-nachher> --ausgabe simulation/berichte/sim-invarianten-2026-10-05.md`
Danach von Hand im Bericht ergänzen: Kopf (Datum, Commits Harness/App, Env ohne Pfadgeheimnisse, Code-Vorgaben entfernt: `IT_BEGRIFFSBOARD_MIN_ZEICHEN`, `IT_BEGRIFFSBOARD_MIN_ABSTAND_S`), Kosten (Bot: `aufruf.kosten_chf` beider `sim.db`, z. B. über `uv run --extra dev python -m simulation.browser_abnahme kosten --lauf …`; Opus-Proxy-Aufrufe zählen aus `schritte.jsonl`), Richterbefunde zur Onboarding-Checkliste (vorher/nachher), Verhörer-Ergebnis, zweite/dritte Diskussion (kam jedes Mal eine Bot-Nachricht?), offene Punkte.

- [ ] **Step 7: Doku** `docs/agents/korpus-und-simulation.md` ergänzen. Doku-Tests laufen lassen:
`uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider tests/test_agents_md_groesse.py tests/test_doku_laengen.py tests/test_web_betrieb_doku.py`
Expected: PASS.

- [ ] **Step 8: Aufräumen:** `git worktree remove .worktrees/sim-cb200e4` (bei Restdateien `--force`, vorher `git -C .worktrees/sim-cb200e4 status --short` ansehen). Laufordner unter `simulation/browser_laeufe/` bleiben ungetrackt.

- [ ] **Step 9: Commit.**
```bash
git add simulation/berichte/sim-invarianten-2026-10-05.md docs/agents/korpus-und-simulation.md
git commit -m "Simulation-Abnahme: Invarianten finden Birks Live-Befunde an cb200e4, am gefixten Stand weg"
```

# Padua Testgruppe: eigene Instanz + Skript „Gruppe auf Test spielen" (Karte t_a9ef536f → t_12a734ab)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Geschrieben von der Planungskarte t_a9ef536f, ausgeführt von der
Umsetzungskarte t_12a734ab. Die Entscheidungen E1–E11 hat der Architekt
gesetzt; sie stehen unten wörtlich verdichtet und werden **nicht neu
verhandelt**. Wo dieser Plan sie am Code präzisiert, steht das als
Planentscheidung P1–P9 mit Beleg `datei:zeile`. Wer beim Umsetzen merkt,
dass eine Entscheidung oder ANNAHME am Code scheitert, hält das im Bericht
unter „ANNAHME widerlegt" mit `datei:zeile` fest, statt still abzuweichen.

**Goal:** Es gibt eine vierte, vom Betrieb getrennte Padua-Instanz (eigene
DB `betrieb/padua-test.db`, eigener Webdienst auf 8031 unter `/padua-test`,
eigener Bot `padua-test`). Ein Skript spielt jederzeit den aktuellen Stand
einer echten Gruppe dorthin oder setzt die Testgruppe auf eine frische
Phase 1 zurück.

**Architecture:** Neues Betreiberskript `scripts/test_uebernehmen.py` (SQL
im Skript, wie `scripts/interviews_uebernehmen.py`). Die Quelle wird per
`VACUUM INTO` aus einer `mode=ro`-Verbindung in eine Temp-DB kopiert; dort
bleibt nur die Quellgruppe, ihre `chat_id` wird zu `7000000000099`, Pfade und
flüchtige Felder werden umgeschrieben. Danach werden in **einer** Transaktion
auf der Live-Datei `betrieb/padua-test.db` die alte Testgruppe gelöscht und
alle Zeilen aus der Temp-DB per `ATTACH` eingefügt (ids unverändert), die
`web_post`-Folge gehoben und der Offset des Bots `padua-test` auf die höchste
`web_post`-id gesetzt. Audio wird in ein Staging-Verzeichnis kopiert und nach
dem Commit an seinen Platz getauscht. Units und Env sind schlüsselfreie
Vorlagen unter `docs/`.

**Tech Stack:** Python 3.11, SQLite (WAL), Standardbibliothek, pytest.

## Global Constraints (für jede Aufgabe bindend)

- Branch `padua-workshop/t_12a734ab-padua-testgruppe-eigene-instanz-db-web-8`.
  Kein Merge, kein Push. **Ein Commit je Task.**
- `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
  — jeder Befehl unten setzt `$PY` voraus (`export PY=…` einmal je Shell).
  (Derselbe Interpreter wie in `docs/superpowers/plans/2026-10-04-padua-interview-fliesstext.md:51`;
  `scripts/betrieb-start.sh:17-21` wählt im Betrieb `.venv/bin/python` oder
  dieselbe uv-Installation.)
- Suite: `$PY -m pytest -q -m "not dortmund"` (Marker registriert in
  `pyproject.toml:22-35`). Dortmund ist eingefroren (AGENTS.md ganz oben):
  **keine** Dortmund-Abnahme, kein `pruefe_profil dortmund-2026`.
- Testbefehle **im Vordergrund** laufen lassen und auf ihr Ende warten. Die
  volle Suite einmal am Ende (Task 9) — mit Ausgabe in eine Datei, siehe dort.
- **Nichts unter `betrieb/`, `audio-padua/` oder `audio-padua-test/` des
  Hauptbaums anfassen, lesen oder ausgeben** — weder Env-Dateien (Schlüssel)
  noch Datenbanken (PII). Kein `systemctl` gegen echte Units. Alle Tests
  laufen gegen Wegwerf-DBs in `tmp_path` und ohne Netz.
- Kein Inhalt in Ausgaben (E10): das Skript gibt nur Zählungen, chat_ids,
  Pfade und Dateigrößen aus, nie Nachrichtentexte, Transkripte, Titel oder
  Namen.
- **pytest sammelt `scripts/test_uebernehmen.py` ein** (Dateiname beginnt mit
  `test_`, pytest-Vorgabe `python_files = test_*.py`, kein `testpaths` in
  `pyproject.toml`). Deshalb: **keine Funktion und keine Klasse im Skript
  darf mit `test` bzw. `Test` beginnen** (sonst liefe sie als Test). Konstanten
  wie `TEST_CHAT_ID` sind unschädlich (keine Funktion, keine Klasse). Ein Test
  in Task 2 hält das fest.
- Die Testdatei heißt `tests/test_testgruppe_uebernehmen.py` (nicht
  `test_test_uebernehmen.py`, damit kein Basisname mit dem Skript kollidiert).
- Commit-Nachrichten deutsch, enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Ausdrücklich NICHT in dieser Karte

- nginx auf herkules (`/padua-test/` → `100.75.24.33:8031`). Die Doku nennt
  nur, dass der Block fehlt (sonst identisch mit `/padua/`,
  `X-Forwarded-Prefix /padua-test`). Robo/Birk nach dem Merge.
- Enable/Start der Units, Umstellen von `betrieb/padua-test.env`, Aufräumen
  der heutigen `betrieb/padua-test.db`. Robo nach dem Merge, nach
  `docs/testgruppe-padua.md`.
- Jede Änderung an `interview_theater/` (kein Produktivcode-Eingriff; E11:
  die Trennung vom Dashboard entsteht allein durch die eigene DB).

## Entscheidungen des Architekten (E1–E11, gesetzt)

- **E1** ids werden unverändert übernommen. `padua-test.db` darf außer der
  Testgruppe keine anderen chat_ids enthalten; sonst Verweigern mit Liste
  (chat_id + Zeilenzahl) und Aufräumbefehl `scripts/loeschen.py <chat_id>`
  mit Env der Testinstanz — das Skript löscht fremde Gruppen **nicht** selbst.
  Nach dem Einfügen `sqlite_sequence` je AUTOINCREMENT-Tabelle auf ≥ MAX(id).
- **E2** Geschrieben wird transaktional in die Live-Datei über `db.verbinde`,
  kein Dateitausch. Backup der Test-DB per `VACUUM INTO`; Quelle per
  `VACUUM INTO` aus `mode=ro` in eine Temp-DB; dort alles außer der
  Quell-chat_id löschen und umschreiben; dann in EINER Transaktion
  Testgruppe löschen und alles aus der Temp-DB einfügen (ATTACH). Migration
  auf Temp-DB und Ziel, nur gemeinsame Spalten. Nach `--ja` Hinweis auf den
  Testbot — das Skript startet nichts selbst.
- **E3** Das Web-Token der Testgruppe wird gemerkt und wieder gesetzt; fehlt
  es, wird eines erzeugt (gleicher Ausdruck wie `repo`). Das Quell-Token
  überlebt nie in der Test-DB.
- **E4** Nicht übernommen: `aufruf`, `web_strom`. Geleert:
  `gruppe.web_tippt_bis`, `gruppe.kostenpause_gemeldet_am`.
- **E5** Web-Wasserzeichen: (a) kein übernommener Eingang wird erneut
  verarbeitet, (b) ein neuer Eingang wird verarbeitet, (c) Erkenner/Journal-
  Wasserzeichen weder Historie neu noch neue Nachricht übersprungen.
  `web_post` wird übernommen.
- **E6** Audio der Quellgruppe nach `audio-padua-test/7000000000099/…`
  kopieren (Quelle unverändert), DB-Pfade umschreiben, relativ bleibt
  relativ, absolut bleibt absolut. Vorher nur `audio-padua-test/7000000000099/`
  leeren. Verzeichnisse sind Parameter.
- **E7** „Aufnahme läuft" = `scripts/interviews_uebernehmen.laufende_aufnahme`
  (`scripts/interviews_uebernehmen.py:111-129`), wiederverwendet.
- **E8** `--leer`: Testgruppe löschen, Audio leeren, frisch als Web-Gruppe
  wie `scripts/web_gruppe.py anlegen` (Phase 1), festes Token, Offset
  konsistent, Trockenlauf ohne `--ja`.
- **E9** Parameter mit Vorgaben `--quelle betrieb/padua.db`,
  `--ziel betrieb/padua-test.db`, `--audio-quelle audio-padua`,
  `--audio-ziel audio-padua-test`; `TEST_CHAT_ID = 7000000000099`, Bot-Name
  `padua-test`. Verweigern bei Quelle == Ziel oder Ziel == `betrieb/padua.db`.
- **E10** Keine Inhalte in Ausgaben.
- **E11** Kein Code-Eingriff fürs Dashboard; Nachweis, dass `padua.db` nicht
  beschrieben wird (Hash).

## Befund am Code (Belege für die Entscheidungen)

**Schema.** Alle Tabellen mit `chat_id` stehen in `db.TABELLEN_MIT_CHAT_ID`
(`interview_theater/db.py:1239-1271`, 29 Tabellen) — gegengeprüft gegen
jedes `CREATE TABLE` in `db.SCHEMA` (`db.py:34-1236`): die einzige Tabelle
ohne `chat_id` ist `bot_zustand` (`db.py:36-41`). Die **einzige**
AUTOINCREMENT-Tabelle ist `web_post` (`db.py:1111`). Spalten, die auf
Dateien zeigen: `aufnahme.audio_pfad` (`db.py:139`) und `web_post.datei`
(`db.py:1124`); `web_post.dateiname` ist nur ein Anzeigename
(`db.py:1126`), `web_post.bild` ein Dateiname unter
`interview_theater/static/handys/`, nicht je Gruppe (`db.py:1147-1152`).

**Pfadformen.** `aufnahme.audio_pfad` entsteht aus dem `IT_AUDIO` des Bots
(`aufnahme.py:515-518`, im Padua-Betrieb relativ: `IT_AUDIO=audio-padua`).
`web_post.datei` für Eingänge schreibt der Webdienst **absolut und
aufgelöst** (`web_chat.py:4412-4421`, `.resolve()`); für Ausgänge
(Textbuch-Datei) schreibt der Bot über `WebKanal.sende_datei` mit seinem
`IT_AUDIO`, also **relativ** (`web_kanal.py:476-479`). Der Bot prüft beim
Laden `quelle.is_relative_to(wurzel)` nach `resolve()` beider Seiten
(`web_kanal.py:584-590`); der Webdienst liefert Ausgangsdateien ohne
Wurzelprüfung relativ zu seinem `WorkingDirectory` aus (`web_chat.py:4659`).

**Commits in Repo-Funktionen.** `db.loesche_gruppe` committet
(`db.py:1466-1471`), ebenso `repo.setze_update_id` (`repo.py:461-474`) und
`repo.stelle_web_token_sicher` (`repo.py:128-151`). Keine davon darf
deshalb **innerhalb** der einen Transaktion laufen — sie würden sie mitten
im Ablauf festschreiben.

**Web-Wasserzeichen (E5).** Die Bot-Schleife liest den Offset bei **jedem**
Durchlauf aus der DB: `offset = repo.hole_update_id(conn, e.bot_name) + 1`
(`bot.py:447`), rückt ihn je Update vor (`bot.py:507`). Der Web-Kanal liefert
`web_post`-Zeilen `richtung='ein'` mit `id >= offset` (`repo.py:4471-4483`,
`web_kanal.py:214-239`). `web_post.id` **ist** `message_id` und `update_id`
(`db.py:1090-1097`, `repo.py:4452-4467`). `bot.baue_kanal` setzt den Offset
beim Start auf 0 zurück, wenn er **über** `repo.hoechste_web_post_id` liegt
(`bot.py:540-548`); `hoechste_web_post_id` = max(MAX(id), `sqlite_sequence`)
(`repo.py:4521-4538`). Die Wasserzeichen `gruppe.letzte_beantwortete/
extrahierte/journalisierte_message_id` (`db.py:49-52`) vergleichen
`nachricht.message_id` (`repo.py:289`, `repo.py:323`, `repo.py:3696`).
`gruppe.bot_name` filtert den Nachhol-Arbeiter (`repo.py:1739-1751`,
`repo.py:1774`, `repo.py:3607`).

**Telegram-Variante der Falle gilt im Web nicht.** In Dortmund bekam der
Testbot eine *neue* Telegram-Gruppe, deren `message_id`s klein neu begannen
— alte ids mussten negativ werden, damit neue darüber liegen. Im Web
vergibt die Test-DB selbst die nächste `message_id` als
`sqlite_sequence('web_post') + 1` (`db.py:1103-1111`, `repo.py:4452-4467`).
Hebt das Skript die Folge auf ≥ MAX(übernommene id), liegt jede neue
Nachricht automatisch über allen übernommenen ids und über den
übernommenen Wasserzeichen. Negative ids braucht es nicht.

**`aufruf` (E4).** Gelesen wird `aufruf` fachlich nur für Kosten und
Diagnose: `repo.kostensumme_seit` (`repo.py:3491-3507`, Tagesdeckel),
`web_daten.py:273` (Aufrufe heute, Dashboard), `web_daten.py:397`
(Kostenwarnung), `web_daten.py:415` (Fehlschläge), `szene.py:2259`
(Budgetwarnung im Log), sonst nur Prüfskripte unter `scripts/`. ANNAHME aus
der Karte damit **belegt**: kein Pfad liest `aufruf` als Arbeitsstand.

**Bausteine, die das Skript wiederverwendet:**
`scripts/interviews_uebernehmen.laufende_aufnahme` (`:111-129`, E7),
`web_daten.oeffne_lesend` (`interview_theater/web_daten.py:41-55`,
`mode=ro`), `db.verbinde`/`db.initialisiere` (`db.py:1274-1281`,
`db.py:1449-1463`), `db.TABELLEN_MIT_CHAT_ID`, `repo.WEB_TOKEN_BYTES`
(`repo.py:114`), `repo.hoechste_web_post_id` (`repo.py:4522`, liest nur,
committet nicht). Bewusst **nicht** wiederverwendet (mit Grund in P-Liste):
`interviews_uebernehmen._backup` (`:395-406`, `shutil.copy2` auf eine
WAL-Datei — genau die `cp`-Falle), `db.loesche_gruppe`/`repo.setze_update_id`/
`repo.stelle_web_token_sicher` (committen), `web_gruppe.lege_an`
(`scripts/web_gruppe.py:36-60`, vergibt die chat_id über
`repo.naechste_web_chat_id` statt der festen 099 und committet in vier
Schritten).

**Bot-Unit.** `interview-theater@.service` ist eine Template-Unit
(`docs/interview-theater@.service:10`, `ExecStart=…/scripts/betrieb-start.sh %i`);
`scripts/betrieb-start.sh:8-11` bildet `%i` auf `betrieb/%i.env` ab
(`env_datei="betrieb/${gruppe}.env"`). Für `interview-theater@padua-test`
braucht es also **keine** neue Unit-Datei, nur `betrieb/padua-test.env`; das
Log landet in `betrieb/padua-test.log`.

## Planentscheidungen (Präzisierungen am Code)

- **P1 Testbot muss bei `--ja` gestoppt sein (verschärft E2).**
  `WebKanal.hole_updates` wartet bis 25 s mit dem Offset, den die Schleife
  *vorher* gelesen hat (`bot.py:447-449`, `web_kanal.py:230-239`). Läuft der
  Testbot während der Übernahme, liefert ihm dieser laufende Poll bis zu 50
  übernommene Eingänge (`repo.py:4471`, `grenze=50`) als neu — er
  beantwortete die Historie. Deshalb prüft `main` vor jedem `--ja`
  `systemctl --user is-active interview-theater@padua-test` und verweigert,
  wenn er läuft. Danach druckt das Skript den **Start**befehl. Die
  Prozess-Sperren und Merkplätze aus E2 sind damit ebenfalls frisch.
- **P2 `vorfall` bekommt neue ids.** In der Test-DB können bot-weite
  Vorfälle mit `chat_id IS NULL` stehen (`db.py:1199`), die E1 nicht als
  fremd zählt — deren ids kollidierten mit den übernommenen. Keine Spalte
  irgendeiner Tabelle zeigt auf `vorfall.id` (Spaltenliste im Befund oben;
  Leser nur `web_daten.py:238`, `repo.py:4512`, `repo.py:4730`, alle über
  `chat_id`/`art`). Deshalb wird `vorfall` ohne `id` eingefügt. Alle anderen
  Tabellen behalten ihre ids (E1).
- **P3 Audio über ein Staging-Verzeichnis.** Kopiert wird nach
  `<audio-ziel>/.neu-7000000000099/`, **nach** dem Commit wird
  `<audio-ziel>/7000000000099/` gelöscht und das Staging umbenannt. Scheitert
  die Transaktion, bleibt das alte Audio der Testgruppe stehen und passt zur
  alten DB. Das ist E6 („vorher leeren") in sicherer Reihenfolge.
- **P4 Token und Offset entstehen in der Transaktion.** Das Token wird in
  der Temp-DB gesetzt (gemerkt oder
  `secrets.token_urlsafe(repo.WEB_TOKEN_BYTES)`, derselbe Ausdruck wie
  `repo.py:146`), der Offset per eigenem Upsert auf `bot_zustand` (dieselbe
  SQL-Form wie `repo.py:464-473`) — weil die Repo-Funktionen committen
  (Befund). Ein Abbruch zwischen zwei Commits hinterließe sonst eine
  Testgruppe mit fremdem Link oder mit einem Offset unter der Historie.
- **P5 Backup per `VACUUM INTO`**, als `<ziel>.bak-YYYYmmdd-HHMMSS-ffffff`
  neben der Test-DB (Benennung wie `interviews_uebernehmen.py:402-404`,
  plus Mikrosekunden, weil `VACUUM INTO` nie überschreibt und die
  Idempotenz-Tests zweimal in derselben Sekunde laufen).
- **P6 Nur Web-Gruppen als Quelle.** Die Quellgruppe muss
  `gruppe.kanal = 'web'` tragen (`db.py:72`), sonst Verweigern. Die
  Wasserzeichen-Argumentation oben gilt nur, wenn `message_id = web_post.id`.
- **P7 SQL im Skript.** Wie `scripts/interviews_uebernehmen.py` (dort
  durchgehend `conn.execute`) — ein Betreiberskript, das zwei Datenbanken
  über `ATTACH` verbindet, gehört nicht in `repo.py`.
- **P8 `--leer` schreibt die Gruppenzeile selbst**, mit denselben Feldern,
  die `web_gruppe.lege_an` erzeugt (`scripts/web_gruppe.py:42-51`:
  `chat_id`, `bot_name`, `titel`, `erste_nachricht_am`, `kanal='web'`,
  `web_token`, Offset) — aber in einer Transaktion mit dem festen Token.
  Ein Test vergleicht die Spaltenlage mit `web_gruppe.lege_an`.
- **P9 Der Schnappschuss wird noch einmal geprüft.** Zwischen Trockenlauf-
  Prüfung und `VACUUM INTO` kann die Quellgruppe eine Aufnahme starten.
  `laufende_aufnahme` läuft deshalb zusätzlich auf der Temp-DB; schlägt sie
  dort an, wird verweigert, bevor die Test-DB angefasst wird.

## ANNAHMEN (nicht am Code belegbar — nachzuprüfen)

1. **ANNAHME:** `VACUUM INTO` funktioniert aus einer `mode=ro`-Verbindung auf
   eine WAL-Datenbank, während andere Prozesse schreiben. Der erste Test in
   Task 3 übt genau diesen Weg (ohne parallele Schreiber); scheitert er mit
   `attempt to write a readonly database`, ist der Ersatz
   `src.backup(sqlite3.connect(kopie))` (Backup-API, liest nur) und das
   gehört in den Bericht.
2. **ANNAHME:** Eine `mode=ro`-Verbindung kann neben einer WAL-Datei leere
   `-wal`/`-shm` anlegen, ohne Inhalt zu ändern (so arbeitet der Webdienst
   seit Karte W, `web_daten.py:41-55`). Die Hash-Tests werten deshalb die
   Hauptdatei und `-wal` aus (fehlend == leer) und lassen `-shm` aus — `-shm`
   ist ein Shared-Memory-Index, in den auch Leser ihre Lesemarken schreiben.
   Nachzuprüfen im Betrieb nur, falls `padua.db` je ohne `-wal` liegt.
3. **ANNAHME:** Alle Gruppen in `betrieb/padua.db` sind Web-Gruppen (P6).
   Nachprüfen (nur Aggregat): `sqlite3 'file:betrieb/padua.db?mode=ro'
   "SELECT kanal, COUNT(*) FROM gruppe GROUP BY kanal"` → nur `web|3`.
4. **ANNAHME:** Die heutige `betrieb/padua-test.db` (Karte T, Telegram)
   enthält eine Gruppe mit fremder chat_id; der erste Lauf verweigert dann
   (E1). Nachprüfen mit dem Trockenlauf aus `docs/testgruppe-padua.md`.
5. **ANNAHME:** `betrieb/padua-test.env` enthält `IT_WORKSHOP=padua-2026`
   (die Vergleichsliste der Karte nennt es nicht). Nachprüfen ohne Inhalt:
   `grep -c '^IT_WORKSHOP=padua-2026$' betrieb/padua-test.env` → `1`.
6. **ANNAHME (gewollt):** Aufnahmen der Quelle im Status `empfangen` oder
   `transkribiert` (nicht „laufend" im Sinne von E7) greift nach dem Start
   der Nachhol-Arbeiter des Testbots auf (`repo.py:1739-1751`) — das kostet
   Whisper/Verdichtung auf dem Testdeckel. Birk entscheidet, ob das
   erwünscht ist.
7. **ANNAHME (gewollt):** Eingänge, die der Quell-Bot im Moment des
   Schnappschusses noch nicht abgeholt hatte, beantwortet der Testbot nicht
   (der Offset steht auf der höchsten id, E5a).
8. **ANNAHME:** Ein Hintergrund-Mithören (Phase 1) oder Brainstorm
   (Phase 4) hat außer `arbeitsstand.brainstorm_lauf_seit` (`db.py:519`)
   keinen Serverzustand, der nach der Kopie weiterliefe — die Aufnahme lebt
   im Browser (`web_chat.py`, Recorder). Kopiert wird, was bis zum
   Schnappschuss angekommen ist.

---

## Dateien

| Datei | Neu/Ändern | Zuständigkeit |
|---|---|---|
| `docs/interview-theater-padua-test-web.service` | neu | Web-Unit der Testinstanz (Vorlage, ohne Token) |
| `docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel` | neu | Drop-in-Vorlage mit Platzhalter |
| `docs/padua-test.env.beispiel` | neu | schlüsselfreie Zielzeilen für `betrieb/padua-test.env` |
| `scripts/test_uebernehmen.py` | neu | das Skript (Trockenlauf, `--ja`, `--leer`) |
| `tests/test_padua_test_vorlagen.py` | neu | Unit-/Env-Vorlagen |
| `tests/test_testgruppe_uebernehmen.py` | neu | alle Skripttests, Wegwerf-DBs |
| `docs/testgruppe-padua.md` | neu | skill-taugliche Kurzanleitung |
| `AGENTS.md` | ändern | eine Zeile im Skriptabschnitt (`AGENTS.md:126-128`) |

---

### Task 0: Grundlinie messen (kein Commit)

- [ ] **Step 1: Interpreter und Bestandstests**

Run: `export PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3; $PY -m pytest -q tests/test_interviews_uebernehmen.py tests/test_web_gruppe_skript.py tests/test_web_kanal.py`
Expected: letzte Zeile `N passed` ohne `failed`. Die Zahl N im Bericht
festhalten (der Planer konnte sie in seiner Session nicht messen).

---

### Task 1: Unit- und Env-Vorlagen

**Files:**
- Create: `docs/interview-theater-padua-test-web.service`
- Create: `docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel`
- Create: `docs/padua-test.env.beispiel`
- Test: `tests/test_padua_test_vorlagen.py`

**Interfaces:**
- Consumes: Vorbild `docs/interview-theater-padua-web.service` (ExecStart,
  WorkingDirectory), `docs/interview-theater@.service:10`,
  `scripts/betrieb-start.sh:9`.
- Produces: drei Dateien, die Task 8 (Doku) mit genau diesen Pfaden nennt.

- [ ] **Step 1: Den roten Test schreiben**

`tests/test_padua_test_vorlagen.py`:

```python
"""Die Vorlagen der Padua-Testinstanz (Karte t_12a734ab).

Die echten Units liegen unter ~/.config/systemd/user/ und die echte Env unter
betrieb/ (gitignored, mit Schluesseln). Im Repository stehen nur Vorlagen --
und in keiner davon darf je ein Dashboard-Token oder ein API-Schluessel
stehen.
"""

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
UNIT = WURZEL / "docs" / "interview-theater-padua-test-web.service"
VORBILD = WURZEL / "docs" / "interview-theater-padua-web.service"
DROPIN = (WURZEL / "docs" / "interview-theater-padua-test-web.service.d"
          / "dashboard-token.conf.beispiel")
ENV = WURZEL / "docs" / "padua-test.env.beispiel"
DOKU = WURZEL / "docs" / "testgruppe-padua.md"

#: Ein echter Wert: alles ausser einem <Platzhalter>, mindestens 8 Zeichen.
ECHTER_TOKEN = re.compile(r"IT_WEB_DASHBOARD_TOKEN=(?!<)\S{8,}")


def _environment(text: str) -> dict:
    werte = {}
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if zeile.startswith("Environment="):
            schluessel, _, wert = zeile[len("Environment="):].partition("=")
            werte[schluessel] = wert
    return werte


def _zeilen_mit(text: str, anfang: str) -> list:
    return [z.strip() for z in text.splitlines() if z.strip().startswith(anfang)]


def test_web_unit_traegt_die_pflichtwerte():
    werte = _environment(UNIT.read_text(encoding="utf-8"))
    assert werte["IT_DB"] == "betrieb/padua-test.db"
    assert werte["IT_WEB_BIND"] == "100.75.24.33:8031"
    assert werte["IT_WEB_PREFIX"] == "/padua-test"
    assert werte["IT_WORKSHOP"] == "padua-2026"
    assert werte["IT_AUDIO"] == "%h/projekte/interview-theater/audio-padua-test"
    assert "IT_WEB_DASHBOARD_TOKEN" not in werte


def test_web_unit_loggt_in_eine_eigene_datei():
    text = UNIT.read_text(encoding="utf-8")
    log = "append:%h/projekte/interview-theater/betrieb/padua-test-web.log"
    assert f"StandardOutput={log}" in text
    assert f"StandardError={log}" in text
    assert "padua-web.log" not in text.replace("padua-test-web.log", "")


def test_web_unit_bindet_nie_alle_adressen():
    assert "0.0.0.0" not in UNIT.read_text(encoding="utf-8")


def test_web_unit_startet_wie_die_padua_unit():
    test = UNIT.read_text(encoding="utf-8")
    vorbild = VORBILD.read_text(encoding="utf-8")
    for anfang in ("ExecStart=", "WorkingDirectory=", "Restart="):
        assert _zeilen_mit(test, anfang) == _zeilen_mit(vorbild, anfang), anfang


def test_dropin_vorlage_traegt_nur_einen_platzhalter():
    text = DROPIN.read_text(encoding="utf-8")
    assert "[Service]" in text
    assert "Environment=IT_WEB_DASHBOARD_TOKEN=<" in text
    assert not ECHTER_TOKEN.search(text)


def test_keine_committete_vorlage_traegt_ein_dashboard_token():
    for pfad in (UNIT, DROPIN, ENV, DOKU):
        if pfad.exists():
            assert not ECHTER_TOKEN.search(pfad.read_text(encoding="utf-8")), pfad


def test_env_vorlage_ist_web_und_schluesselfrei():
    werte = {}
    for zeile in ENV.read_text(encoding="utf-8").splitlines():
        if zeile.strip() and not zeile.lstrip().startswith("#"):
            schluessel, _, wert = zeile.partition("=")
            werte[schluessel.strip()] = wert.strip()
    assert werte == {
        "IT_KANAL": "web",
        "IT_WEB_CHAT_ID": "7000000000099",
        "IT_BOT_NAME": "padua-test",
        "IT_DB": "betrieb/padua-test.db",
        "IT_AUDIO": "audio-padua-test",
        "IT_WEB_URL": "https://lab.artesmobiles.art/padua-test",
        "IT_WORKSHOP": "padua-2026",
    }


def test_web_unit_und_bot_env_zeigen_auf_dasselbe_audioverzeichnis():
    """AGENTS.md 'Der Web-Kanal', Betrieb: Web-Unit und Web-Bot muessen aufs
    selbe IT_AUDIO zeigen -- WebKanal.lade_datei verweigert jeden Pfad
    ausserhalb des eigenen (web_kanal.py:584-590)."""
    unit = UNIT.read_text(encoding="utf-8")
    env_audio = [z.split("=", 1)[1] for z in ENV.read_text(encoding="utf-8").splitlines()
                 if z.startswith("IT_AUDIO=")][0]
    assert _zeilen_mit(unit, "WorkingDirectory=") == [
        "WorkingDirectory=%h/projekte/interview-theater"]
    assert _environment(unit)["IT_AUDIO"] == f"%h/projekte/interview-theater/{env_audio}"


def test_bot_unit_ist_die_vorlage_mit_env_je_instanz():
    """Fuer interview-theater@padua-test braucht es keine neue Unit-Datei:
    %i wird zu betrieb/%i.env."""
    start = (WURZEL / "scripts" / "betrieb-start.sh").read_text(encoding="utf-8")
    assert 'env_datei="betrieb/${gruppe}.env"' in start
    unit = (WURZEL / "docs" / "interview-theater@.service").read_text(encoding="utf-8")
    assert "scripts/betrieb-start.sh %i" in unit
    assert "betrieb/%i.log" in unit
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_padua_test_vorlagen.py`
Expected: FAIL — `FileNotFoundError` für
`interview-theater-padua-test-web.service` in sieben Tests; die zwei Tests
`test_keine_committete_vorlage_traegt_ein_dashboard_token` und
`test_bot_unit_ist_die_vorlage_mit_env_je_instanz` dürfen schon grün sein.

- [ ] **Step 3: Die drei Vorlagen anlegen**

`docs/interview-theater-padua-test-web.service`:

```ini
[Unit]
Description=InScribe Weboberflaeche Padua TESTINSTANZ (Karte t_12a734ab)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/projekte/interview-theater
# Eigene Datenbank, eigener Port, eigenes Praefix -- getrennt vom Betrieb
# (padua.db, 8030, /padua). Die Testgruppe erscheint deshalb nie auf der
# Padua-Uebersicht. Gefuellt wird sie mit scripts/test_uebernehmen.py.
Environment=IT_DB=betrieb/padua-test.db
Environment=IT_AUDIO=%h/projekte/interview-theater/audio-padua-test
# Tailnet-Adresse, nie 0.0.0.0: Gruppenseiten haben kein Login.
Environment=IT_WEB_BIND=100.75.24.33:8031
Environment=IT_WEB_PREFIX=/padua-test
Environment=IT_WORKSHOP=padua-2026
# IT_WEB_DASHBOARD_TOKEN steht NICHT hier, sondern im Drop-in
# interview-theater-padua-test-web.service.d/dashboard-token.conf
# (Vorlage daneben, Erzeugung in docs/testgruppe-padua.md).
ExecStart=%h/.local/bin/python3.11 -u -m interview_theater.web
Restart=always
RestartSec=5
StandardOutput=append:%h/projekte/interview-theater/betrieb/padua-test-web.log
StandardError=append:%h/projekte/interview-theater/betrieb/padua-test-web.log

[Install]
WantedBy=default.target
```

`docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel`:

```ini
# Vorlage -- NICHT mit echtem Wert committen.
# Ziel: ~/.config/systemd/user/interview-theater-padua-test-web.service.d/dashboard-token.conf
# Erzeugung des Werts: docs/testgruppe-padua.md, "Einmalig einrichten".
[Service]
Environment=IT_WEB_DASHBOARD_TOKEN=<TOKEN-HIER>
```

`docs/padua-test.env.beispiel`:

```sh
# Zielzeilen fuer betrieb/padua-test.env (Testinstanz Padua, Karte t_12a734ab).
# Schluesselfreie Vorlage: diese Zeilen ersetzen die gleichnamigen in
# betrieb/padua-test.env. IT_BOT_TOKEN dort ENTFERNEN (im Web-Kanal nicht
# Pflicht, einstellungen._NUR_TELEGRAM). Die Modell-, STT- und
# Schluesselzeilen (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL, IT_STT_PRODUKT, ...)
# bleiben wie in betrieb/padua-gruppe1.env -- sie stehen hier bewusst nicht.
IT_KANAL=web
IT_WEB_CHAT_ID=7000000000099
IT_BOT_NAME=padua-test
IT_DB=betrieb/padua-test.db
IT_AUDIO=audio-padua-test
IT_WEB_URL=https://lab.artesmobiles.art/padua-test
IT_WORKSHOP=padua-2026
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_padua_test_vorlagen.py`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add docs/interview-theater-padua-test-web.service docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel docs/padua-test.env.beispiel tests/test_padua_test_vorlagen.py
git commit -m "Testinstanz Padua: Vorlagen fuer Web-Unit (8031, /padua-test), Token-Drop-in und Bot-Env

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Skriptgerüst, Prüfungen und Trockenlauf (`plane`)

**Files:**
- Create: `scripts/test_uebernehmen.py`
- Create: `tests/test_testgruppe_uebernehmen.py`

**Interfaces:**
- Consumes: `scripts.interviews_uebernehmen.laufende_aufnahme(conn, chat_id) -> bool`,
  `interview_theater.web_daten.oeffne_lesend(pfad) -> sqlite3.Connection`,
  `db.TABELLEN_MIT_CHAT_ID`.
- Produces (spätere Tasks benutzen genau diese Namen):
  - Konstanten `TEST_CHAT_ID = 7_000_000_000_099`, `TEST_BOT_NAME = "padua-test"`,
    `VORGABE_QUELLE`, `VORGABE_ZIEL`, `VORGABE_AUDIO_QUELLE`, `VORGABE_AUDIO_ZIEL`,
    `VORGABE_URL`, `NICHT_UEBERNOMMEN: tuple[str, ...]`, `UEBERNOMMEN: tuple[str, ...]`,
    `NEUE_IDS: tuple[str, ...]`, `TITEL_LEER: str`, `TITEL_KOPIE: str` (Format mit `{bot_name}`)
  - `class Verweigert(Exception)`
  - `pruefe_ziel(ziel: str, audio_ziel: str) -> None` (raises `Verweigert`)
  - `pruefe_pfade(quelle: str, ziel: str, audio_quelle: str, audio_ziel: str) -> None`
  - `tabellen(conn) -> set[str]`
  - `zaehle(conn, chat_id: int) -> dict[str, int]`
  - `fremde_chat_ids(conn) -> dict[int, int]`
  - `fremde_text(fremde: dict[int, int]) -> str`
  - `audio_bestand(verz: Path) -> tuple[int, int]`
  - `lies_ziel(ziel: str) -> dict` mit Schlüsseln `existiert: bool`, `zeilen: dict[str,int]`, `token_vorhanden: bool`
  - `plane(quell_chat_id: int, *, quelle, ziel, audio_quelle, audio_ziel) -> dict`
    mit Schlüsseln `quell_chat_id`, `ziel`, `zeilen`, `audio_dateien`, `audio_bytes`, `ziel_lage`
  - `berichtstext(bericht: dict, trocken: bool) -> str`
  - Testdatei: Fixtures `umgebung`, `umgebung_ohne_ziel`, `kein_echter_dienst`
    (autouse), Helfer `fuelle_zeile`, `baue_gruppe`, `baue_quelle`, `baue_ziel`,
    `basis_id`, `fingerabdruck_db`, `fingerabdruck_baum`, `lies`, Konstanten
    `QUELLE_CHAT`, `ANDERE_CHAT`, `TEST`, `GEHEIM`, `ZEIT`.

- [ ] **Step 1: Testdatei mit Fixtures und den roten Tests schreiben**

`tests/test_testgruppe_uebernehmen.py`:

```python
"""scripts/test_uebernehmen.py -- eine echte Gruppe auf die Testinstanz spielen.

Alles gegen Wegwerf-DBs in tmp_path (monkeypatch.chdir), ohne Netz, ohne
systemctl. Die Quelle wird mit einer schreibenden Verbindung GEFUELLT und
danach geschlossen; das Skript selbst liest sie nur mode=ro.

Die Pfade sind die Vorgaben des Skripts (betrieb/padua.db, audio-padua, ...),
relativ zu tmp_path -- so wird nebenbei die Vorgabe selbst geprueft.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from interview_theater import db, repo
from scripts import test_uebernehmen as tu

QUELLE_CHAT = 7_000_000_000_001
ANDERE_CHAT = 7_000_000_000_002
TEST = tu.TEST_CHAT_ID
#: Steht in jedem Textfeld der Quelle -- darf in keiner Ausgabe auftauchen (E10).
GEHEIM = "GEHEIM-INHALT-7c1f"
ZEIT = "2026-10-04T10:00:00+00:00"
#: Diese Tabellen fuellt baue_gruppe von Hand (zusammenhaengende ids, Dateien).
VON_HAND = ("gruppe", "nachricht", "aufnahme", "web_post")


@dataclass
class Umgebung:
    quelle: str = "betrieb/padua.db"
    ziel: str = "betrieb/padua-test.db"
    audio_quelle: str = "audio-padua"
    audio_ziel: str = "audio-padua-test"

    def pfade(self) -> dict:
        return {"quelle": self.quelle, "ziel": self.ziel,
                "audio_quelle": self.audio_quelle, "audio_ziel": self.audio_ziel}


def basis_id(tabelle: str, basis: int) -> int:
    """Die id der generisch gefuellten Zeile einer Tabelle (basis+10 ...)."""
    return basis + 10 + db.TABELLEN_MIT_CHAT_ID.index(tabelle)


def fuelle_zeile(conn, tabelle: str, chat_id, nummer: int, **fest) -> None:
    """Eine Zeile mit allen Pflichtspalten -- aus PRAGMA table_info, damit
    eine spaeter hinzukommende Pflichtspalte den Test nicht bricht."""
    werte = {}
    for s in conn.execute(f"PRAGMA table_info({tabelle})").fetchall():
        name, typ = s["name"], (s["type"] or "").upper()
        if name == "chat_id":
            werte[name] = chat_id
        elif s["pk"] or (s["notnull"] and s["dflt_value"] is None):
            werte[name] = nummer if ("INT" in typ or "REAL" in typ) else f"x{nummer}"
    werte.update(fest)
    namen = ", ".join(werte)
    fragen = ", ".join("?" for _ in werte)
    conn.execute(f"INSERT INTO {tabelle} ({namen}) VALUES ({fragen})",
                 list(werte.values()))


def schreibe_datei(pfad: Path, inhalt: bytes) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(inhalt)


def baue_gruppe(conn, chat_id: int, basis: int, bot_name: str, audio: str) -> None:
    """Je Tabelle aus db.TABELLEN_MIT_CHAT_ID mindestens eine Zeile; dazu
    drei Nachrichten, vier web_post-Zeilen (Eingang Text, Eingang Sprache mit
    ABSOLUTEM Pfad wie der Webdienst, Ausgang Text, Ausgang Datei mit
    RELATIVEM Pfad wie der Bot) und eine Aufnahme mit relativem Pfad."""
    for tabelle in db.TABELLEN_MIT_CHAT_ID:
        if tabelle not in VON_HAND:
            fuelle_zeile(conn, tabelle, chat_id, basis_id(tabelle, basis))
    conn.execute("UPDATE vorfall SET bot_name = ? WHERE chat_id = ?", (bot_name, chat_id))
    fuelle_zeile(
        conn, "gruppe", chat_id, basis, bot_name=bot_name, kanal="web",
        titel=GEHEIM, web_token=f"quelltoken-{chat_id}", erste_nachricht_am=ZEIT,
        letzte_beantwortete_message_id=basis + 3,
        letzte_extrahierte_message_id=basis + 3,
        letzte_journalisierte_message_id=basis + 1,
        web_tippt_bis=ZEIT, kostenpause_gemeldet_am=ZEIT,
    )
    for nr, ist_bot, typ, unterdrueckt in (
        (basis + 1, 0, "text", 0),
        (basis + 2, 0, "sprache", 1),
        (basis + 3, 1, "text", 0),
    ):
        fuelle_zeile(conn, "nachricht", chat_id, nr, message_id=nr, ist_bot=ist_bot,
                     typ=typ, text=GEHEIM, gesendet_am=ZEIT,
                     unterdrueckt=unterdrueckt, absender="Gruppe")
    eingang = (Path(audio) / str(chat_id) / "web-eingang" / f"{basis + 2}.webm").resolve()
    ausgang = Path(audio) / str(chat_id) / "web-ausgang" / f"{basis + 4}-textbuch.md"
    aufnahme = Path(audio) / str(chat_id) / f"{basis + 2}.webm"
    schreibe_datei(eingang, b"webm-" + str(chat_id).encode())
    schreibe_datei(ausgang, GEHEIM.encode())
    schreibe_datei(aufnahme, b"aufnahme-" + str(chat_id).encode())
    fuelle_zeile(conn, "web_post", chat_id, basis + 1, richtung="ein", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 2, richtung="ein", typ="sprache",
                 datei=str(eingang), mime="audio/webm", erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 3, richtung="aus", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 4, richtung="aus", typ="datei",
                 datei=str(ausgang), dateiname="textbuch.md", erstellt_am=ZEIT)
    fuelle_zeile(conn, "aufnahme", chat_id, basis + 1, message_id=basis + 2,
                 klasse="kurz", quelle="sprache", audio_pfad=str(aufnahme),
                 transkript=GEHEIM, status="fertig", empfangen_am=ZEIT)


def baue_quelle(u: Umgebung) -> None:
    Path(u.quelle).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(u.quelle)
    db.initialisiere(conn)
    baue_gruppe(conn, QUELLE_CHAT, 100, "padua-gruppe1", u.audio_quelle)
    baue_gruppe(conn, ANDERE_CHAT, 500, "padua-gruppe2", u.audio_quelle)
    conn.commit()
    repo.setze_update_id(conn, "padua-gruppe1", 103)
    conn.close()


def baue_ziel(u: Umgebung) -> None:
    """Eine Test-DB mit einer ALTEN Testgruppe (festes Token, web_post-id 900
    -- hoeher als alles in der Quelle) und einem bot-weiten Vorfall ohne
    chat_id, dessen id mit einem Quellvorfall kollidiert (P2)."""
    Path(u.ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(u.ziel)
    db.initialisiere(conn)
    fuelle_zeile(conn, "gruppe", TEST, 900, bot_name=tu.TEST_BOT_NAME, kanal="web",
                 web_token="fester-testtoken", titel=GEHEIM)
    fuelle_zeile(conn, "nachricht", TEST, 900, message_id=900, typ="text",
                 text=GEHEIM, gesendet_am=ZEIT)
    fuelle_zeile(conn, "web_post", TEST, 900, richtung="ein", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "vorfall", None, basis_id("vorfall", 100), art="bot_weit",
                 erstellt_am=ZEIT)
    conn.commit()
    repo.setze_update_id(conn, tu.TEST_BOT_NAME, 900)
    conn.close()
    schreibe_datei(Path(u.audio_ziel) / str(TEST) / "alt.webm", b"alt")


def fingerabdruck_db(pfad) -> tuple:
    """Hauptdatei und -wal (fehlend == leer). -shm bewusst nicht: auch Leser
    schreiben dort ihre Lesemarken (ANNAHME 2 im Plan)."""
    def h(p: Path) -> str:
        return hashlib.sha256(p.read_bytes() if p.exists() else b"").hexdigest()
    return h(Path(pfad)), h(Path(f"{pfad}-wal"))


def fingerabdruck_baum(verz) -> dict:
    verz = Path(verz)
    return {str(p.relative_to(verz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(verz.rglob("*")) if p.is_file()}


def lies(pfad) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture(autouse=True)
def kein_echter_dienst(monkeypatch):
    """Auf dem Server laeuft womoeglich die echte Unit -- kein Test darf
    davon abhaengen (Task 7 fuehrt dienst_laeuft ein)."""
    monkeypatch.setattr(tu, "dienst_laeuft", lambda bot_name: False, raising=False)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    u = Umgebung()
    baue_quelle(u)
    baue_ziel(u)
    return u


@pytest.fixture
def umgebung_ohne_ziel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    u = Umgebung()
    baue_quelle(u)
    return u


# --------------------------------------------------------------------------
# Task 2: Pruefungen und Trockenlauf
# --------------------------------------------------------------------------


def test_skript_hat_keine_funktion_die_pytest_als_test_saehe():
    """scripts/test_uebernehmen.py heisst test_*, pytest sammelt es ein."""
    namen = [n for n, o in vars(tu).items()
             if callable(o) and (n.startswith("test") or n.startswith("Test"))]
    assert namen == []


def test_trockenlauf_zaehlt_und_veraendert_nichts(umgebung):
    q_vorher = fingerabdruck_db(umgebung.quelle)
    z_vorher = fingerabdruck_db(umgebung.ziel)
    bericht = tu.plane(QUELLE_CHAT, **umgebung.pfade())
    assert bericht["zeilen"]["nachricht"] == 3
    assert bericht["zeilen"]["web_post"] == 4
    assert bericht["zeilen"]["gruppe"] == 1
    assert "aufruf" not in bericht["zeilen"]
    assert bericht["audio_dateien"] == 3
    assert bericht["ziel_lage"]["existiert"] is True
    assert bericht["ziel_lage"]["token_vorhanden"] is True
    assert fingerabdruck_db(umgebung.quelle) == q_vorher
    assert fingerabdruck_db(umgebung.ziel) == z_vorher


def test_bericht_zeigt_zahlen_und_keine_inhalte(umgebung):
    text = tu.berichtstext(tu.plane(QUELLE_CHAT, **umgebung.pfade()), trocken=True)
    assert "nachricht: 3" in text
    assert GEHEIM not in text
    assert "quelltoken" not in text
    assert "fester-testtoken" not in text


def test_trockenlauf_ohne_test_db_sagt_es_wird_angelegt(umgebung_ohne_ziel):
    bericht = tu.plane(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    assert bericht["ziel_lage"] == {"existiert": False, "zeilen": {}, "token_vorhanden": False}
    assert not Path(umgebung_ohne_ziel.ziel).exists()


def test_verweigert_quelle_gleich_ziel(umgebung):
    pfade = umgebung.pfade() | {"ziel": umgebung.quelle}
    with pytest.raises(tu.Verweigert, match="dieselbe"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_die_betriebsdatenbank_als_ziel(umgebung, tmp_path):
    pfade = umgebung.pfade() | {"quelle": umgebung.ziel, "ziel": "betrieb/padua.db"}
    with pytest.raises(tu.Verweigert, match="Betrieb"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_das_betriebsaudio_als_ziel(umgebung):
    pfade = umgebung.pfade() | {"audio_ziel": "audio-padua"}
    with pytest.raises(tu.Verweigert, match="Audio"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_die_testgruppe_als_quelle(umgebung):
    with pytest.raises(tu.Verweigert):
        tu.plane(TEST, **umgebung.pfade())


def test_verweigert_unbekannte_quellgruppe(umgebung):
    with pytest.raises(tu.Verweigert, match="gibt es"):
        tu.plane(7_000_000_000_077, **umgebung.pfade())


def test_verweigert_eine_telegram_gruppe_als_quelle(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE gruppe SET kanal = 'telegram' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Web"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_bei_laufender_aufnahme(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE aufnahme SET status = 'laeuft' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Aufnahme"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_bei_interviewmodus(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = ?",
                 (ZEIT, QUELLE_CHAT))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Aufnahme"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_fremde_gruppen_im_ziel_mit_liste_ohne_inhalt(umgebung):
    conn = db.verbinde(umgebung.ziel)
    fuelle_zeile(conn, "gruppe", ANDERE_CHAT, 1, bot_name="alt", titel=GEHEIM)
    fuelle_zeile(conn, "nachricht", ANDERE_CHAT, 1, message_id=1, text=GEHEIM)
    conn.commit()
    conn.close()
    vorher = fingerabdruck_db(umgebung.ziel)
    with pytest.raises(tu.Verweigert) as fehler:
        tu.plane(QUELLE_CHAT, **umgebung.pfade())
    meldung = str(fehler.value)
    assert f"{ANDERE_CHAT} (2 Zeilen)" in meldung
    assert "scripts/loeschen.py" in meldung
    assert GEHEIM not in meldung
    assert fingerabdruck_db(umgebung.ziel) == vorher


def test_bot_weite_vorfaelle_ohne_chat_id_sind_nicht_fremd(umgebung):
    conn = lies(umgebung.ziel)
    assert tu.fremde_chat_ids(conn) == {}
    conn.close()
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: FAIL beim Sammeln — `ImportError: cannot import name 'test_uebernehmen' from 'scripts'`.

- [ ] **Step 3: Das Skriptgerüst schreiben**

`scripts/test_uebernehmen.py`:

```python
"""Eine echte Padua-Gruppe auf die Testinstanz spielen (Karte t_12a734ab).

Birk, 04.10.2026: "Wir werden ueber die Woche hinweg immer wieder 'ne
Testgruppe brauchen, wo wir wahlweise die Datenbank von einer Gruppe
draufspielen koennen."

Die Testinstanz ist eine eigene Datenbank (betrieb/padua-test.db), ein
eigener Webdienst (Port 8031, /padua-test) und ein eigener Bot (padua-test)
mit genau EINER Gruppe: ``TEST_CHAT_ID``. Dieses Skript kopiert den Stand
einer echten Gruppe dorthin. Die Quelle wird nur gelesen (mode=ro). Die ids
bleiben unveraendert -- Knoepfe tragen ids im Freitext (``knopf.wert``), eine
Neuvergabe braeche sie still --, umgeschrieben werden nur chat_id, bot_name,
Token, fluechtige Felder und Audiopfade.

Aufruf (aus dem Repo-Verzeichnis, Testbot VORHER stoppen):

    python -m scripts.test_uebernehmen <quell_chat_id>          # Trockenlauf
    python -m scripts.test_uebernehmen <quell_chat_id> --ja     # wirklich
    python -m scripts.test_uebernehmen --leer [--ja]            # frische Phase 1

Anleitung: docs/testgruppe-padua.md. Ausgegeben werden nur Zaehlungen, nie
Inhalte (Nachrichten, Transkripte, Titel, Namen).

ACHTUNG beim Erweitern: der Dateiname beginnt mit ``test_`` (Vorgabe der
Karte), pytest sammelt das Modul also ein. Keine Funktion und keine Klasse
darf mit ``test``/``Test`` anfangen -- sonst liefe sie als Test
(tests/test_testgruppe_uebernehmen.py haelt das fest).
"""

from pathlib import Path

from interview_theater import db
from interview_theater.web_daten import oeffne_lesend
from scripts.interviews_uebernehmen import laufende_aufnahme

#: Die eine Gruppe der Testinstanz. Fest, damit ein Lauf den vorigen ersetzt
#: und die Env des Testbots (IT_WEB_CHAT_ID) sich nie aendert.
TEST_CHAT_ID = 7_000_000_000_099
TEST_BOT_NAME = "padua-test"

VORGABE_QUELLE = "betrieb/padua.db"
VORGABE_ZIEL = "betrieb/padua-test.db"
VORGABE_AUDIO_QUELLE = "audio-padua"
VORGABE_AUDIO_ZIEL = "audio-padua-test"
VORGABE_URL = "https://lab.artesmobiles.art/padua-test"

#: Was nie Ziel sein darf: die Betriebsdatenbank und ihr Audio (E9).
GESCHUETZT_DB = (VORGABE_QUELLE,)
GESCHUETZT_AUDIO = (VORGABE_AUDIO_QUELLE,)

#: E4: Kostenbuchungen (sonst erbte die Testgruppe die heutigen Ausgaben der
#: Quelle gegen den Tagesdeckel, repo.kostensumme_seit) und fluechtige Stroeme
#: (sonst hinge im Browser ein "laeuft").
NICHT_UEBERNOMMEN = ("aufruf", "web_strom")
UEBERNOMMEN = tuple(t for t in db.TABELLEN_MIT_CHAT_ID if t not in NICHT_UEBERNOMMEN)

#: P2: bot-weite Vorfaelle (chat_id NULL) der Test-DB koennten dieselben ids
#: tragen. Auf vorfall.id zeigt keine Spalte -- also neue ids.
NEUE_IDS = ("vorfall",)

TITEL_LEER = "Testgruppe"
TITEL_KOPIE = "Testgruppe (Kopie von {bot_name})"

TEXT_AUFNAHME_LAEUFT = (
    "In Gruppe {chat_id} laeuft gerade eine Aufnahme oder der Interviewmodus "
    "ist an. Erst beenden lassen, dann uebernehmen."
)


class Verweigert(Exception):
    """Ein Grund, nichts zu tun. Der Text geht unveraendert an die Konsole --
    also nie Inhalte hineinschreiben (E10)."""


# --------------------------------------------------------------------------
# Pruefungen
# --------------------------------------------------------------------------


def _gleich(a: str, b: str) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def pruefe_ziel(ziel: str, audio_ziel: str) -> None:
    """Das Ziel ist nie die Betriebsdatenbank und nie das Betriebsaudio --
    weder als Pfad noch als gleichnamige Datei an anderem Ort."""
    for geschuetzt in GESCHUETZT_DB:
        if _gleich(ziel, geschuetzt) or Path(ziel).name == Path(geschuetzt).name:
            raise Verweigert(f"Ziel {ziel} ist die Betriebsdatenbank -- nie.")
    for geschuetzt in GESCHUETZT_AUDIO:
        if _gleich(audio_ziel, geschuetzt) or Path(audio_ziel).name == Path(geschuetzt).name:
            raise Verweigert(f"Audio-Ziel {audio_ziel} ist das Betriebsaudio -- nie.")


def pruefe_pfade(quelle: str, ziel: str, audio_quelle: str, audio_ziel: str) -> None:
    if _gleich(quelle, ziel):
        raise Verweigert("Quelle und Ziel sind dieselbe Datei.")
    if _gleich(audio_quelle, audio_ziel):
        raise Verweigert("Audio-Quelle und Audio-Ziel sind dasselbe Verzeichnis.")
    pruefe_ziel(ziel, audio_ziel)
    if not Path(quelle).exists():
        raise Verweigert(f"Quelle {quelle} gibt es nicht.")


# --------------------------------------------------------------------------
# Lesen (auch im Trockenlauf -- nur mode=ro)
# --------------------------------------------------------------------------


def tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}


def zaehle(conn, chat_id: int) -> dict[str, int]:
    """Zeilen je uebernommener Tabelle fuer eine Gruppe -- nur Zahlen."""
    vorhanden = tabellen(conn)
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                        (chat_id,)).fetchone()[0]
        for t in UEBERNOMMEN if t in vorhanden
    }


def fremde_chat_ids(conn) -> dict[int, int]:
    """Jede chat_id ausser der Testgruppe, mit ihrer Zeilenzahl ueber alle
    Tabellen. ``chat_id IS NULL`` (bot-weite Vorfaelle) ist nicht fremd."""
    vorhanden = tabellen(conn)
    fremde: dict[int, int] = {}
    for t in db.TABELLEN_MIT_CHAT_ID:
        if t not in vorhanden:
            continue
        for chat_id, anzahl in conn.execute(
            f"SELECT chat_id, COUNT(*) FROM {t} WHERE chat_id IS NOT NULL "
            "AND chat_id != ? GROUP BY chat_id", (TEST_CHAT_ID,)
        ):
            fremde[int(chat_id)] = fremde.get(int(chat_id), 0) + int(anzahl)
    return fremde


def fremde_text(fremde: dict[int, int]) -> str:
    liste = ", ".join(f"{c} ({n} Zeilen)" for c, n in sorted(fremde.items()))
    return (
        f"Die Test-DB enthaelt fremde Gruppen: {liste}. Das Skript loescht sie "
        "nicht selbst (E1). Aufraeumen je Gruppe, mit der Env der Testinstanz: "
        "set -a; . ./betrieb/padua-test.env; set +a; "
        "python scripts/loeschen.py <chat_id>"
    )


def audio_bestand(verz: Path) -> tuple[int, int]:
    """(Anzahl Dateien, Bytes) unter einem Verzeichnis, 0/0 wenn es fehlt."""
    verz = Path(verz)
    if not verz.exists():
        return 0, 0
    dateien = [p for p in verz.rglob("*") if p.is_file()]
    return len(dateien), sum(p.stat().st_size for p in dateien)


def lies_ziel(ziel: str) -> dict:
    """Die Lage der Test-DB, read-only. Verweigert bei fremden Gruppen."""
    if not Path(ziel).exists():
        return {"existiert": False, "zeilen": {}, "token_vorhanden": False}
    conn = oeffne_lesend(ziel)
    try:
        fremde = fremde_chat_ids(conn)
        if fremde:
            raise Verweigert(fremde_text(fremde))
        zeilen = zaehle(conn, TEST_CHAT_ID)
        token = None
        if "gruppe" in tabellen(conn):
            zeile = conn.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                                 (TEST_CHAT_ID,)).fetchone()
            token = zeile["web_token"] if zeile else None
    finally:
        conn.close()
    return {"existiert": True, "zeilen": zeilen, "token_vorhanden": bool(token)}


def _pruefe_quellgruppe(conn, quell_chat_id: int) -> None:
    zeile = conn.execute("SELECT kanal FROM gruppe WHERE chat_id = ?",
                         (quell_chat_id,)).fetchone()
    if zeile is None:
        raise Verweigert(f"Gruppe {quell_chat_id} gibt es in der Quelle nicht.")
    if zeile["kanal"] != "web":
        raise Verweigert(f"Gruppe {quell_chat_id} ist keine Web-Gruppe (P6).")
    if laufende_aufnahme(conn, quell_chat_id):
        raise Verweigert(TEXT_AUFNAHME_LAEUFT.format(chat_id=quell_chat_id))


def plane(quell_chat_id: int, *, quelle: str, ziel: str, audio_quelle: str,
          audio_ziel: str) -> dict:
    """Was ein Lauf taete -- reine Leseabfrage, Grundlage von Trockenlauf und
    Ernstfall. Verweigert mit ``Verweigert``."""
    if quell_chat_id == TEST_CHAT_ID:
        raise Verweigert("Die Testgruppe kann nicht ihre eigene Quelle sein.")
    pruefe_pfade(quelle, ziel, audio_quelle, audio_ziel)
    src = oeffne_lesend(quelle)
    try:
        _pruefe_quellgruppe(src, quell_chat_id)
        zeilen = zaehle(src, quell_chat_id)
    finally:
        src.close()
    anzahl, groesse = audio_bestand(Path(audio_quelle) / str(quell_chat_id))
    return {
        "quell_chat_id": quell_chat_id,
        "ziel": ziel,
        "zeilen": zeilen,
        "audio_dateien": anzahl,
        "audio_bytes": groesse,
        "ziel_lage": lies_ziel(ziel),
    }


# --------------------------------------------------------------------------
# Texte (nur Zahlen, E10)
# --------------------------------------------------------------------------


def berichtstext(bericht: dict, trocken: bool) -> str:
    kopf = "Trockenlauf" if trocken else "Uebernommen"
    z = [f"{kopf}: Gruppe {bericht['quell_chat_id']} -> Testgruppe "
         f"{TEST_CHAT_ID} ({bericht['ziel']})",
         "  Zeilen je Tabelle:"]
    z += [f"    {t}: {n}" for t, n in bericht["zeilen"].items() if n]
    z.append(f"  Nicht uebernommen: {', '.join(NICHT_UEBERNOMMEN)}")
    z.append(f"  Audio: {bericht['audio_dateien']} Datei(en), "
             f"{bericht['audio_bytes']} Bytes")
    lage = bericht["ziel_lage"]
    if lage["existiert"]:
        z.append(f"  Bisherige Testgruppe: {sum(lage['zeilen'].values())} "
                 "Zeile(n) -- wird ersetzt")
    else:
        z.append("  Test-DB gibt es noch nicht -- wird angelegt")
    z.append("  Link der Testgruppe: "
             + ("bleibt gleich" if lage["token_vorhanden"] else "wird neu erzeugt"))
    if not trocken:
        if bericht.get("backup"):
            z.append(f"  Backup: {bericht['backup']}")
        if "offset" in bericht:
            z.append(f"  Offset von {TEST_BOT_NAME}: {bericht['offset']}")
        for warnung in bericht.get("warnungen", []):
            z.append(f"  WARNUNG: {warnung}")
    return "\n".join(z)
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: Skriptgeruest mit Pruefungen und Trockenlauf (nur Zaehlungen)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Übernahme der Datenbank (`uebernimm`, ohne Audio, ohne Offset)

**Files:**
- Modify: `scripts/test_uebernehmen.py` (Funktionen anhängen, Importe ergänzen)
- Modify: `tests/test_testgruppe_uebernehmen.py` (Tests anhängen)

**Interfaces:**
- Consumes: alles aus Task 2.
- Produces:
  - `neues_token() -> str`
  - `sichere_ziel(conn, ziel: str, jetzt: datetime) -> str`
  - `uebernimm(quell_chat_id: int, *, quelle, ziel, audio_quelle, audio_ziel, jetzt: datetime | None = None) -> dict`
    — Bericht von `plane` plus `backup: str | None`, `warnungen: list[str]`,
    `nachher: dict[str,int]`, `token_neu: bool`
  - private, von Task 4/5 ersetzt: `_schnappschuss(quelle, kopie)`,
    `_bereite_kopie_vor(kopie, quell_chat_id, token) -> list[str]`,
    `_gemeinsame_spalten(conn, tabelle) -> list[str]`,
    `_hebe_folgen(conn) -> None`, `_schreibe_in_ziel(conn, kopie) -> None`,
    `_token_der_testgruppe(conn) -> str | None`

- [ ] **Step 1: Die roten Tests anhängen**

An `tests/test_testgruppe_uebernehmen.py` anhängen:

```python
# --------------------------------------------------------------------------
# Task 3: Uebernahme der Datenbank
# --------------------------------------------------------------------------


def test_uebernahme_ist_vollstaendig(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    src, ziel = lies(umgebung.quelle), lies(umgebung.ziel)
    for t in db.TABELLEN_MIT_CHAT_ID:
        im_ziel = ziel.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                               (TEST,)).fetchone()[0]
        if t in tu.NICHT_UEBERNOMMEN:
            assert im_ziel == 0, t
            continue
        in_quelle = src.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                                (QUELLE_CHAT,)).fetchone()[0]
        assert in_quelle >= 1, t
        assert im_ziel == in_quelle, t
        assert ziel.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id IN (?, ?)",
                            (QUELLE_CHAT, ANDERE_CHAT)).fetchone()[0] == 0, t
    src.close()
    ziel.close()


def test_ids_bleiben_unveraendert_ausser_bei_vorfall(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert {z[0] for z in ziel.execute(
        "SELECT id FROM web_post WHERE chat_id = ?", (TEST,))} == {101, 102, 103, 104}
    assert ziel.execute("SELECT id FROM aufnahme WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == 101
    assert ziel.execute("SELECT id FROM knopf WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == basis_id("knopf", 100)
    ziel.close()


def test_bot_weite_vorfaelle_im_ziel_bleiben_stehen(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert ziel.execute("SELECT COUNT(*) FROM vorfall WHERE chat_id IS NULL "
                        "AND art = 'bot_weit'").fetchone()[0] == 1
    assert ziel.execute("SELECT COUNT(*) FROM vorfall WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == 1
    ziel.close()


def test_quelle_bleibt_unveraendert(umgebung):
    db_vorher = fingerabdruck_db(umgebung.quelle)
    audio_vorher = fingerabdruck_baum(umgebung.audio_quelle)
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert fingerabdruck_db(umgebung.quelle) == db_vorher
    assert fingerabdruck_baum(umgebung.audio_quelle) == audio_vorher


def test_link_bleibt_gleich_und_ist_nie_der_quelllink(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    tokens = [z[0] for z in ziel.execute("SELECT web_token FROM gruppe")]
    ziel.close()
    assert tokens == ["fester-testtoken"]


def test_zweimal_uebernehmen_ist_idempotent(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    erste_verbindung = lies(umgebung.ziel)
    erstes = tu.zaehle(erste_verbindung, TEST)
    erste_verbindung.close()
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert tu.zaehle(ziel, TEST) == erstes
    assert ziel.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == "fester-testtoken"
    ziel.close()


def test_ohne_bisherige_testgruppe_entsteht_ein_eigener_link(umgebung_ohne_ziel):
    tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    ziel = lies(umgebung_ohne_ziel.ziel)
    token = ziel.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                         (TEST,)).fetchone()[0]
    ziel.close()
    assert token and len(token) >= 32
    assert token != f"quelltoken-{QUELLE_CHAT}"


def test_gruppenfelder_der_testgruppe(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    g = ziel.execute("SELECT * FROM gruppe WHERE chat_id = ?", (TEST,)).fetchone()
    assert g["bot_name"] == tu.TEST_BOT_NAME
    assert g["kanal"] == "web"
    assert g["titel"] == "Testgruppe (Kopie von padua-gruppe1)"
    assert g["web_tippt_bis"] is None
    assert g["kostenpause_gemeldet_am"] is None
    assert g["letzte_beantwortete_message_id"] == 103
    assert g["letzte_extrahierte_message_id"] == 103
    assert g["letzte_journalisierte_message_id"] == 101
    assert [z[0] for z in ziel.execute(
        "SELECT bot_name FROM vorfall WHERE chat_id = ?", (TEST,))] == [tu.TEST_BOT_NAME]
    ziel.close()


def test_kein_bot_zustand_der_quelle_im_ziel(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert ziel.execute("SELECT COUNT(*) FROM bot_zustand WHERE bot_name = "
                        "'padua-gruppe1'").fetchone()[0] == 0
    ziel.close()


def test_folge_von_web_post_steht_nie_unter_der_hoechsten_id(umgebung_ohne_ziel):
    tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    ziel = lies(umgebung_ohne_ziel.ziel)
    seq = ziel.execute("SELECT seq FROM sqlite_sequence WHERE name = 'web_post'").fetchone()[0]
    hoechste = ziel.execute("SELECT MAX(id) FROM web_post").fetchone()[0]
    ziel.close()
    assert seq >= hoechste == 104


def test_backup_enthaelt_die_alte_testgruppe(umgebung):
    bericht = tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert bericht["backup"] and Path(bericht["backup"]).exists()
    alt = lies(bericht["backup"])
    assert alt.execute("SELECT COUNT(*) FROM nachricht WHERE chat_id = ? "
                       "AND message_id = 900", (TEST,)).fetchone()[0] == 1
    alt.close()


def test_kein_backup_wenn_es_noch_keine_test_db_gab(umgebung_ohne_ziel):
    bericht = tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    assert bericht["backup"] is None


def test_keine_temp_kopie_bleibt_liegen(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    reste = [p.name for p in Path(umgebung.ziel).parent.iterdir()
             if p.name.startswith(".testuebernahme-")]
    assert reste == []


def test_verweigert_ohne_die_test_db_anzufassen(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE aufnahme SET status = 'laeuft' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    vorher = fingerabdruck_db(umgebung.ziel)
    with pytest.raises(tu.Verweigert):
        tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert fingerabdruck_db(umgebung.ziel) == vorher
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `14 failed, 14 passed` — die 14 Task-2-Tests grün, die 14 neuen
rot mit `AttributeError: module 'scripts.test_uebernehmen' has no attribute 'uebernimm'`.

- [ ] **Step 3: Implementieren**

In `scripts/test_uebernehmen.py` die Importzeilen ersetzen durch:

```python
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from interview_theater import db, repo
from interview_theater.web_daten import oeffne_lesend
from scripts.interviews_uebernehmen import laufende_aufnahme
```

und vor dem Abschnitt `# Texte (nur Zahlen, E10)` diesen Abschnitt einfügen:

```python
# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------


def neues_token() -> str:
    """Derselbe Ausdruck wie repo.stelle_web_token_sicher (repo.py:146) --
    hier ohne dessen commit, weil es in der Transaktion entsteht (P4)."""
    return secrets.token_urlsafe(repo.WEB_TOKEN_BYTES)


def sichere_ziel(conn, ziel: str, jetzt: datetime) -> str:
    """Backup der Test-DB per VACUUM INTO (P5) -- NIE shutil.copy auf eine
    WAL-Datei: was noch im -wal steht, fehlte der Kopie."""
    pfad = Path(ziel)
    sicherung = pfad.with_name(f"{pfad.name}.bak-{jetzt:%Y%m%d-%H%M%S-%f}")
    conn.execute("VACUUM INTO ?", (str(sicherung),))
    return str(sicherung)


def _token_der_testgruppe(conn) -> str | None:
    zeile = conn.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                         (TEST_CHAT_ID,)).fetchone()
    return zeile["web_token"] if zeile and zeile["web_token"] else None


def _schnappschuss(quelle: str, kopie: Path) -> None:
    """Die Quelle als Ganzes in eine Temp-DB -- aus einer mode=ro-Verbindung
    (E2). Die Quelle sieht dabei keinen einzigen Schreibzugriff."""
    src = oeffne_lesend(quelle)
    try:
        src.execute("VACUUM INTO ?", (str(kopie),))
    finally:
        src.close()


def _bereite_kopie_vor(kopie: Path, quell_chat_id: int, token: str) -> list[str]:
    """Macht aus der Temp-DB genau die kuenftige Testgruppe: nur die
    Quellgruppe, chat_id umgeschrieben, Token der Testinstanz, fluechtige
    Felder leer, kein bot_zustand. Liefert Warnungen (ohne Inhalte)."""
    warnungen: list[str] = []
    k = db.verbinde(str(kopie))
    try:
        db.initialisiere(k)
        _pruefe_quellgruppe(k, quell_chat_id)  # P9: der Schnappschuss zaehlt
        quell_bot = k.execute("SELECT bot_name FROM gruppe WHERE chat_id = ?",
                              (quell_chat_id,)).fetchone()["bot_name"]
        for t in db.TABELLEN_MIT_CHAT_ID:
            if t in NICHT_UEBERNOMMEN:
                k.execute(f"DELETE FROM {t}")
                continue
            k.execute(f"DELETE FROM {t} WHERE chat_id IS NOT ?", (quell_chat_id,))
            k.execute(f"UPDATE {t} SET chat_id = ? WHERE chat_id = ?",
                      (TEST_CHAT_ID, quell_chat_id))
        k.execute(
            "UPDATE gruppe SET bot_name = ?, titel = ?, web_token = ?, "
            "web_tippt_bis = NULL, kostenpause_gemeldet_am = NULL "
            "WHERE chat_id = ?",
            (TEST_BOT_NAME, TITEL_KOPIE.format(bot_name=quell_bot), token,
             TEST_CHAT_ID),
        )
        k.execute("UPDATE vorfall SET bot_name = ? WHERE bot_name IS NOT NULL",
                  (TEST_BOT_NAME,))
        k.execute("DELETE FROM bot_zustand")
        k.commit()
    finally:
        k.close()
    return warnungen


def _gemeinsame_spalten(conn, tabelle: str) -> list[str]:
    """Spalten, die Ziel UND Kopie kennen (E2), in der Reihenfolge des Ziels;
    bei NEUE_IDS ohne ``id`` (P2)."""
    im_ziel = [z[1] for z in conn.execute(f"PRAGMA main.table_info({tabelle})")]
    in_kopie = {z[1] for z in conn.execute(f"PRAGMA kopie.table_info({tabelle})")}
    return [s for s in im_ziel
            if s in in_kopie and not (tabelle in NEUE_IDS and s == "id")]


def _hebe_folgen(conn) -> None:
    """E1: sqlite_sequence je AUTOINCREMENT-Tabelle auf >= MAX(id). SQLite tut
    das beim Einfuegen mit expliziter id selbst -- hier steht es trotzdem,
    weil eine niedrigere Folge genau die Dortmund-Falle waere (neue
    message_ids unter der Historie)."""
    for (name,) in conn.execute(
        "SELECT name FROM main.sqlite_master WHERE type = 'table' "
        "AND sql LIKE '%AUTOINCREMENT%'"
    ).fetchall():
        hoechste = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM main.{name}").fetchone()[0]
        zeile = conn.execute("SELECT seq FROM main.sqlite_sequence WHERE name = ?",
                             (name,)).fetchone()
        if zeile is None:
            conn.execute("INSERT INTO main.sqlite_sequence (name, seq) VALUES (?, ?)",
                         (name, hoechste))
        elif zeile[0] < hoechste:
            conn.execute("UPDATE main.sqlite_sequence SET seq = ? WHERE name = ?",
                         (hoechste, name))


def _schreibe_in_ziel(conn, kopie: Path) -> None:
    """E2: in EINER Transaktion die alte Testgruppe loeschen und die Kopie
    einfuegen. Kein db.loesche_gruppe -- das committet (db.py:1471)."""
    conn.execute("ATTACH DATABASE ? AS kopie", (str(kopie),))
    try:
        spalten = {t: _gemeinsame_spalten(conn, t) for t in UEBERNOMMEN}
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t in db.TABELLEN_MIT_CHAT_ID:
                conn.execute(f"DELETE FROM main.{t} WHERE chat_id = ?", (TEST_CHAT_ID,))
            for t, namen in spalten.items():
                liste = ", ".join(namen)
                conn.execute(f"INSERT INTO main.{t} ({liste}) SELECT {liste} FROM kopie.{t}")
            _hebe_folgen(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.execute("DETACH DATABASE kopie")


def uebernimm(quell_chat_id: int, *, quelle: str, ziel: str, audio_quelle: str,
              audio_ziel: str, jetzt: datetime | None = None) -> dict:
    """Der Ernstfall. Verweigert (``Verweigert``) VOR jedem Schreibzugriff."""
    jetzt = jetzt or datetime.now(timezone.utc)
    bericht = plane(quell_chat_id, quelle=quelle, ziel=ziel,
                    audio_quelle=audio_quelle, audio_ziel=audio_ziel)
    existierte = Path(ziel).exists()
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".testuebernahme-",
                                     dir=Path(ziel).resolve().parent) as tmp:
        kopie = Path(tmp) / "kopie.db"
        _schnappschuss(quelle, kopie)
        conn = db.verbinde(ziel)
        try:
            db.initialisiere(conn)
            token = _token_der_testgruppe(conn)
            bericht["warnungen"] = _bereite_kopie_vor(
                kopie, quell_chat_id, token or neues_token())
            bericht["backup"] = sichere_ziel(conn, ziel, jetzt) if existierte else None
            _schreibe_in_ziel(conn, kopie)
            bericht["nachher"] = zaehle(conn, TEST_CHAT_ID)
            bericht["token_neu"] = token is None
        finally:
            conn.close()
    return bericht
```

Hinweis zur Reihenfolge: `_bereite_kopie_vor` (mit der P9-Prüfung) läuft
**vor** dem Backup und vor jedem Schreiben ins Ziel. Ein `Verweigert` dort
lässt die Test-DB unberührt. Die Ausnahme: `db.initialisiere` hat schon
migriert, aber das ändert keine Zeile der Testgruppe. Im Test
`test_verweigert_ohne_die_test_db_anzufassen` verweigert bereits `plane`.

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `28 passed`. Scheitert `test_quelle_bleibt_unveraendert` oder
irgendein Test an `VACUUM INTO` aus der `mode=ro`-Verbindung mit
„readonly database", gilt ANNAHME 1 als widerlegt: `_schnappschuss` auf
`dst = sqlite3.connect(str(kopie)); src.backup(dst); dst.close()` umstellen
und das im Bericht vermerken.

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: Uebernahme in einer Transaktion (ids unveraendert, Token fest, aufruf/web_strom nicht)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Bot-Wasserzeichen (Offset des Testbots, E5)

**Files:**
- Modify: `scripts/test_uebernehmen.py` (`_setze_offset` neu, `_schreibe_in_ziel` ersetzt, eine Zeile in `uebernimm`)
- Modify: `tests/test_testgruppe_uebernehmen.py`

**Interfaces:**
- Consumes: `repo.hoechste_web_post_id(conn) -> int` (`repo.py:4522`, liest nur),
  `interview_theater.web_kanal.WebKanal(conn, chat_id, audio_verz)` und
  `.hole_updates(offset, timeout=0) -> list[dict]` (Updates tragen `update_id`,
  `web_kanal.py:334-339`), `bot.baue_kanal(conn, e, klient)`.
- Produces: `_setze_offset(conn, jetzt: datetime) -> int`;
  `_schreibe_in_ziel(conn, kopie: Path, jetzt: datetime) -> int` (gibt den
  Offset zurück); `uebernimm(...)`-Bericht hat zusätzlich `offset: int`.

- [ ] **Step 1: Die roten Tests anhängen**

An `tests/test_testgruppe_uebernehmen.py` anhängen:

```python
# --------------------------------------------------------------------------
# Task 4: Bot-Wasserzeichen (E5)
# --------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from interview_theater import bot  # noqa: E402
from interview_theater.web_kanal import WebKanal  # noqa: E402


def _offset(pfad) -> int:
    conn = db.verbinde(pfad)
    try:
        return repo.hole_update_id(conn, tu.TEST_BOT_NAME)
    finally:
        conn.close()


@pytest.mark.parametrize("mit_altem_ziel", [True, False])
def test_kein_uebernommener_eingang_wird_erneut_geliefert(request, mit_altem_ziel):
    u = request.getfixturevalue("umgebung" if mit_altem_ziel else "umgebung_ohne_ziel")
    bericht = tu.uebernimm(QUELLE_CHAT, **u.pfade())
    conn = db.verbinde(u.ziel)
    offset = repo.hole_update_id(conn, tu.TEST_BOT_NAME)
    assert offset == bericht["offset"] == repo.hoechste_web_post_id(conn)
    # mit altem Ziel liegt die Folge bei 900 (alte Testgruppe), sonst bei 104
    assert offset == (900 if mit_altem_ziel else 104)
    kanal = WebKanal(conn, TEST, u.audio_ziel)
    assert kanal.hole_updates(offset + 1, timeout=0) == []          # (a)
    neu = repo.lege_web_post_an(conn, TEST, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="hallo")
    assert neu == offset + 1
    assert [x["update_id"] for x in kanal.hole_updates(offset + 1, timeout=0)] == [neu]  # (b)
    conn.close()


def test_baue_kanal_setzt_den_offset_nicht_zurueck(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    vorher = _offset(umgebung.ziel)
    conn = db.verbinde(umgebung.ziel)
    e = SimpleNamespace(kanal="web", web_chat_id=TEST, bot_name=tu.TEST_BOT_NAME,
                        audio_verz=umgebung.audio_ziel, bot_token="")
    bot.baue_kanal(conn, e, None)
    assert repo.hole_update_id(conn, tu.TEST_BOT_NAME) == vorher
    conn.close()


def test_erkenner_und_journal_stehen_wie_in_der_quelle(umgebung):
    """(c): weder die Historie neu noch eine neue Nachricht uebersprungen --
    die Wasserzeichen sagen im Ziel dasselbe wie in der Quelle."""
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    src = db.verbinde(umgebung.quelle)
    ziel = db.verbinde(umgebung.ziel)
    for funktion in (repo.unbeantwortete, repo.unextrahierte, repo.unjournalisierte):
        quell_ids = [z["message_id"] for z in funktion(src, QUELLE_CHAT)]
        ziel_ids = [z["message_id"] for z in funktion(ziel, TEST)]
        assert ziel_ids == quell_ids, funktion.__name__
    assert [z["message_id"] for z in repo.unbeantwortete(ziel, TEST)] == []
    neu = repo.lege_web_post_an(ziel, TEST, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="neu")
    repo.merke_nachricht(ziel, TEST, neu, "Gruppe", 0, "text", "neu", ZEIT)
    assert [z["message_id"] for z in repo.unbeantwortete(ziel, TEST)] == [neu]
    assert neu in [z["message_id"] for z in repo.unextrahierte(ziel, TEST)]
    src.close()
    ziel.close()
```

**Achtung, Quelle im Test:** `db.verbinde(umgebung.quelle)` öffnet hier die
Wegwerf-Quelle schreibend — nach der Übernahme, nur zum Lesen über die
`repo`-Funktionen. Das ist erlaubt (tmp_path), betrifft nicht den
Hash-Test (der läuft in einem eigenen Test).

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py -k "eingang or baue_kanal or erkenner_und_journal"`
Expected: `2 failed, 2 passed` — beide Fälle von
`test_kein_uebernommener_eingang_wird_erneut_geliefert` rot mit
`KeyError: 'offset'`. Grün dürfen schon sein:
`test_baue_kanal_setzt_den_offset_nicht_zurueck` (die Fixture hat den
Offset 900 der alten Testgruppe gesetzt, der zufällig passt) und
`test_erkenner_und_journal_stehen_wie_in_der_quelle` (die Wasserzeichen
kamen in Task 3 mit, das belegt (c)). Den eigentlichen Fehler zeigt der
Fall ohne altes Ziel: dort steht der Offset ohne Task 4 auf 0, und
`hole_updates(1)` lieferte die übernommenen Eingänge 101 und 102 — **genau
die Falle**.

- [ ] **Step 3: Implementieren**

In `scripts/test_uebernehmen.py` direkt vor `def _schreibe_in_ziel` einfügen:

```python
def _setze_offset(conn, jetzt: datetime) -> int:
    """E5: der Offset des Testbots auf die hoechste je vergebene web_post-id.

    bot.schleife liest ``hole_update_id + 1`` (bot.py:447) und der Web-Kanal
    liefert ``id >= offset`` (repo.py:4471-4483) -- nichts Uebernommenes kommt
    also noch einmal. Die naechste neue Zeile bekommt ``sqlite_sequence + 1``
    und liegt damit darueber. ``bot.baue_kanal`` setzt nur zurueck, wenn der
    Offset UEBER ``hoechste_web_post_id`` liegt (bot.py:540-548) -- er ist hier
    genau gleich. Upsert wie repo.setze_update_id (repo.py:464-473), aber ohne
    dessen commit (P4)."""
    offset = repo.hoechste_web_post_id(conn)
    jetzt_iso = jetzt.isoformat()
    conn.execute(
        "INSERT INTO main.bot_zustand (bot_name, letzte_update_id, gestartet_am, "
        "letzte_aktivitaet_am) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(bot_name) DO UPDATE SET "
        "letzte_update_id = excluded.letzte_update_id, "
        "letzte_aktivitaet_am = excluded.letzte_aktivitaet_am",
        (TEST_BOT_NAME, offset, jetzt_iso, jetzt_iso),
    )
    return offset
```

`_schreibe_in_ziel` vollständig ersetzen durch:

```python
def _schreibe_in_ziel(conn, kopie: Path, jetzt: datetime) -> int:
    """E2: in EINER Transaktion die alte Testgruppe loeschen, die Kopie
    einfuegen, die Folge heben und den Offset setzen. Kein db.loesche_gruppe
    und kein repo.setze_update_id -- beide committen (db.py:1471,
    repo.py:474). Liefert den Offset."""
    conn.execute("ATTACH DATABASE ? AS kopie", (str(kopie),))
    try:
        spalten = {t: _gemeinsame_spalten(conn, t) for t in UEBERNOMMEN}
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t in db.TABELLEN_MIT_CHAT_ID:
                conn.execute(f"DELETE FROM main.{t} WHERE chat_id = ?", (TEST_CHAT_ID,))
            for t, namen in spalten.items():
                liste = ", ".join(namen)
                conn.execute(f"INSERT INTO main.{t} ({liste}) SELECT {liste} FROM kopie.{t}")
            _hebe_folgen(conn)
            offset = _setze_offset(conn, jetzt)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.execute("DETACH DATABASE kopie")
    return offset
```

In `uebernimm` die Zeile

```python
            _schreibe_in_ziel(conn, kopie)
```

ersetzen durch

```python
            bericht["offset"] = _schreibe_in_ziel(conn, kopie, jetzt)
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `32 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: Offset des Testbots auf die hoechste web_post-id (keine Historie doppelt, neue Eingaenge kommen an)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Audio kopieren und Pfade umschreiben (E6)

**Files:**
- Modify: `scripts/test_uebernehmen.py` (`PFADSPALTEN`, `setze_pfad_um`,
  `kopiere_audio`, `tausche_audio` neu; `_bereite_kopie_vor` und `uebernimm`
  vollständig ersetzt; `import shutil`)
- Modify: `tests/test_testgruppe_uebernehmen.py`

**Interfaces:**
- Consumes: Task 2–4.
- Produces:
  - `PFADSPALTEN = (("aufnahme", "audio_pfad"), ("web_post", "datei"))`
  - `setze_pfad_um(wert: str, quell_chat_id: int, audio_quelle: str, audio_ziel: str) -> str | None`
  - `kopiere_audio(audio_quelle: str, audio_ziel: str, quell_chat_id: int) -> Path` (Staging)
  - `tausche_audio(staging: Path, audio_ziel: str) -> None`
  - `_bereite_kopie_vor(kopie, quell_chat_id, token, *, audio_quelle: str, audio_ziel: str) -> list[str]`

- [ ] **Step 1: Die roten Tests anhängen**

An `tests/test_testgruppe_uebernehmen.py` anhängen:

```python
# --------------------------------------------------------------------------
# Task 5: Audio (E6)
# --------------------------------------------------------------------------


def test_pfadspalten_sind_vollstaendig():
    """Jede Spalte im Schema, die auf eine Datei zeigt, steht in PFADSPALTEN
    -- eine neue (z. B. 'x_pfad') faellt hier auf, nicht im Testbot."""
    gefunden = set()
    for tabelle, spalten in db._tabellenspalten_aus_schema().items():
        for name, _ in spalten:
            if name.endswith("pfad") or name == "datei":
                gefunden.add((tabelle, name))
    assert gefunden == set(tu.PFADSPALTEN)


def test_setze_pfad_um_relativ_bleibt_relativ(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    neu = tu.setze_pfad_um(f"audio-padua/{QUELLE_CHAT}/102.webm", QUELLE_CHAT,
                           "audio-padua", "audio-padua-test")
    assert neu == f"audio-padua-test/{TEST}/102.webm"


def test_setze_pfad_um_absolut_bleibt_absolut(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    alt = str((tmp_path / "audio-padua" / str(QUELLE_CHAT) / "web-eingang" / "102.webm"))
    neu = tu.setze_pfad_um(alt, QUELLE_CHAT, "audio-padua", "audio-padua-test")
    assert neu == str((tmp_path / "audio-padua-test").resolve() / str(TEST)
                      / "web-eingang" / "102.webm")


def test_setze_pfad_um_laesst_fremdes_stehen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert tu.setze_pfad_um("/etc/passwd", QUELLE_CHAT, "audio-padua", "audio-padua-test") is None
    assert tu.setze_pfad_um(f"audio-padua/{ANDERE_CHAT}/1.webm", QUELLE_CHAT,
                            "audio-padua", "audio-padua-test") is None


def test_audio_ist_kopiert_und_die_pfade_zeigen_darauf(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel_verz = Path(umgebung.audio_ziel) / str(TEST)
    assert fingerabdruck_baum(ziel_verz) == fingerabdruck_baum(
        Path(umgebung.audio_quelle) / str(QUELLE_CHAT))
    ziel = lies(umgebung.ziel)
    pfade = [z[0] for z in ziel.execute(
        "SELECT audio_pfad FROM aufnahme WHERE chat_id = ? AND audio_pfad IS NOT NULL "
        "UNION ALL SELECT datei FROM web_post WHERE chat_id = ? AND datei IS NOT NULL",
        (TEST, TEST))]
    ziel.close()
    assert len(pfade) == 3
    wurzel = ziel_verz.resolve()
    for pfad in pfade:
        assert Path(pfad).exists(), pfad
        assert Path(pfad).resolve().is_relative_to(wurzel), pfad


def test_relative_und_absolute_pfade_behalten_ihre_form(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    aufnahme = ziel.execute("SELECT audio_pfad FROM aufnahme WHERE chat_id = ?",
                            (TEST,)).fetchone()[0]
    eingang = ziel.execute("SELECT datei FROM web_post WHERE id = 102").fetchone()[0]
    ausgang = ziel.execute("SELECT datei FROM web_post WHERE id = 104").fetchone()[0]
    ziel.close()
    assert not Path(aufnahme).is_absolute()
    assert Path(eingang).is_absolute()
    assert not Path(ausgang).is_absolute()


def test_altes_testaudio_ist_weg_und_fremdes_nie_kopiert(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel_verz = Path(umgebung.audio_ziel) / str(TEST)
    assert not (ziel_verz / "alt.webm").exists()
    assert not (Path(umgebung.audio_ziel) / str(ANDERE_CHAT)).exists()
    assert [p.name for p in Path(umgebung.audio_ziel).iterdir()] == [str(TEST)]


def test_der_webkanal_des_testbots_kann_das_segment_laden(umgebung, tmp_path):
    """WebKanal.lade_datei prueft die Wurzel (web_kanal.py:584-590) -- der
    umgeschriebene absolute Pfad muss unter dem IT_AUDIO des Testbots liegen."""
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    conn = db.verbinde(umgebung.ziel)
    kanal = WebKanal(conn, TEST, umgebung.audio_ziel)
    ziel = tmp_path / "geladen.webm"
    kanal.lade_datei("web:102.webm", ziel)
    assert ziel.read_bytes() == b"webm-" + str(QUELLE_CHAT).encode()
    conn.close()


def test_fehlende_audiodatei_gibt_eine_warnung_ohne_inhalt(umgebung):
    (Path(umgebung.audio_quelle) / str(QUELLE_CHAT) / "102.webm").unlink()
    bericht = tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert any("fehlt" in w for w in bericht["warnungen"])
    assert all(GEHEIM not in w for w in bericht["warnungen"])
```

Hinweis: `WebKanal` ist seit Task 4 oben in der Testdatei importiert.
`lade_datei(file_id, ziel)` steht in `web_kanal.py:563`.

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py -k "pfad or audio or webkanal_des_testbots"`
Expected: FAIL — `AttributeError: … has no attribute 'PFADSPALTEN'` /
`'setze_pfad_um'`, und `test_audio_ist_kopiert…`, weil `audio-padua-test/7000000000099/`
noch die alte `alt.webm` trägt und die Pfade auf `audio-padua/…` zeigen.

- [ ] **Step 3: Implementieren**

In `scripts/test_uebernehmen.py`: `import shutil` zu den Importen (nach
`import secrets`). Unter `NEUE_IDS` einfügen:

```python
#: Die Spalten, die auf Dateien zeigen (Schema-grep: db.py:139, db.py:1124;
#: web_post.dateiname ist nur ein Anzeigename, web_post.bild ein Name unter
#: interview_theater/static/handys/). Ein Test haelt die Liste am Schema fest.
PFADSPALTEN = (("aufnahme", "audio_pfad"), ("web_post", "datei"))
```

Vor `def _bereite_kopie_vor` einfügen:

```python
def setze_pfad_um(wert: str, quell_chat_id: int, audio_quelle: str,
                  audio_ziel: str) -> str | None:
    """``<audio_quelle>/<quell_chat_id>/REST`` -> ``<audio_ziel>/<TEST>/REST``.

    Relativ bleibt relativ (der Bot schreibt mit seinem relativen IT_AUDIO,
    aufnahme.py:515-518, web_kanal.py:476), absolut bleibt absolut und
    aufgeloest (der Webdienst schreibt so, web_chat.py:4412-4421). None, wenn
    der Pfad nicht unter dem Verzeichnis der Quellgruppe liegt -- dann bleibt
    er stehen und es gibt eine Warnung."""
    alt = Path(wert)
    try:
        rel = alt.resolve().relative_to(Path(audio_quelle).resolve())
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] != str(quell_chat_id):
        return None
    basis = Path(audio_ziel).resolve() if alt.is_absolute() else Path(audio_ziel)
    return str(basis / str(TEST_CHAT_ID) / Path(*rel.parts[1:]))


def kopiere_audio(audio_quelle: str, audio_ziel: str, quell_chat_id: int) -> Path:
    """Kopiert das Audioverzeichnis der Quellgruppe in ein Staging-Verzeichnis
    neben dem Ziel (P3). Die Quelle wird nur gelesen."""
    quelle = Path(audio_quelle) / str(quell_chat_id)
    staging = Path(audio_ziel) / f".neu-{TEST_CHAT_ID}"
    if staging.exists():
        shutil.rmtree(staging)
    if quelle.exists():
        shutil.copytree(quelle, staging)
    else:
        staging.mkdir(parents=True)
    return staging


def tausche_audio(staging: Path, audio_ziel: str) -> None:
    """Nach dem Commit: das alte Audio der Testgruppe weg, Staging an seinen
    Platz. Nur dieses eine Verzeichnis wird geleert (E6)."""
    ziel = Path(audio_ziel) / str(TEST_CHAT_ID)
    if ziel.exists():
        shutil.rmtree(ziel)
    staging.rename(ziel)
```

`_bereite_kopie_vor` vollständig ersetzen durch:

```python
def _bereite_kopie_vor(kopie: Path, quell_chat_id: int, token: str, *,
                       audio_quelle: str, audio_ziel: str) -> list[str]:
    """Macht aus der Temp-DB genau die kuenftige Testgruppe: nur die
    Quellgruppe, chat_id umgeschrieben, Token der Testinstanz, fluechtige
    Felder leer, kein bot_zustand, Audiopfade aufs Testverzeichnis. Liefert
    Warnungen (nur Tabelle, Spalte, rowid, Pfad -- keine Inhalte)."""
    warnungen: list[str] = []
    k = db.verbinde(str(kopie))
    try:
        db.initialisiere(k)
        _pruefe_quellgruppe(k, quell_chat_id)  # P9: der Schnappschuss zaehlt
        quell_bot = k.execute("SELECT bot_name FROM gruppe WHERE chat_id = ?",
                              (quell_chat_id,)).fetchone()["bot_name"]
        for t in db.TABELLEN_MIT_CHAT_ID:
            if t in NICHT_UEBERNOMMEN:
                k.execute(f"DELETE FROM {t}")
                continue
            k.execute(f"DELETE FROM {t} WHERE chat_id IS NOT ?", (quell_chat_id,))
        for tabelle, spalte in PFADSPALTEN:
            for zeile in k.execute(
                f"SELECT rowid AS r, {spalte} AS p FROM {tabelle} "
                f"WHERE {spalte} IS NOT NULL"
            ).fetchall():
                if not Path(zeile["p"]).exists():
                    warnungen.append(f"{tabelle}.{spalte} rowid {zeile['r']}: "
                                     f"Datei fehlt ({zeile['p']})")
                neu = setze_pfad_um(zeile["p"], quell_chat_id, audio_quelle, audio_ziel)
                if neu is None:
                    warnungen.append(f"{tabelle}.{spalte} rowid {zeile['r']}: liegt "
                                     f"nicht unter {audio_quelle}/{quell_chat_id} "
                                     "-- unveraendert")
                    continue
                k.execute(f"UPDATE {tabelle} SET {spalte} = ? WHERE rowid = ?",
                          (neu, zeile["r"]))
        for t in UEBERNOMMEN:
            k.execute(f"UPDATE {t} SET chat_id = ? WHERE chat_id = ?",
                      (TEST_CHAT_ID, quell_chat_id))
        k.execute(
            "UPDATE gruppe SET bot_name = ?, titel = ?, web_token = ?, "
            "web_tippt_bis = NULL, kostenpause_gemeldet_am = NULL "
            "WHERE chat_id = ?",
            (TEST_BOT_NAME, TITEL_KOPIE.format(bot_name=quell_bot), token,
             TEST_CHAT_ID),
        )
        k.execute("UPDATE vorfall SET bot_name = ? WHERE bot_name IS NOT NULL",
                  (TEST_BOT_NAME,))
        k.execute("DELETE FROM bot_zustand")
        k.commit()
    finally:
        k.close()
    return warnungen
```

`uebernimm` vollständig ersetzen durch:

```python
def uebernimm(quell_chat_id: int, *, quelle: str, ziel: str, audio_quelle: str,
              audio_ziel: str, jetzt: datetime | None = None) -> dict:
    """Der Ernstfall. Verweigert (``Verweigert``) VOR jedem Schreibzugriff.

    Reihenfolge: Schnappschuss -> Kopie vorbereiten (P9-Pruefung) -> Audio
    ins Staging -> Backup -> EINE Transaktion -> Audio tauschen (P3)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    bericht = plane(quell_chat_id, quelle=quelle, ziel=ziel,
                    audio_quelle=audio_quelle, audio_ziel=audio_ziel)
    existierte = Path(ziel).exists()
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    staging = None
    with tempfile.TemporaryDirectory(prefix=".testuebernahme-",
                                     dir=Path(ziel).resolve().parent) as tmp:
        kopie = Path(tmp) / "kopie.db"
        _schnappschuss(quelle, kopie)
        conn = db.verbinde(ziel)
        try:
            db.initialisiere(conn)
            token = _token_der_testgruppe(conn)
            bericht["warnungen"] = _bereite_kopie_vor(
                kopie, quell_chat_id, token or neues_token(),
                audio_quelle=audio_quelle, audio_ziel=audio_ziel)
            staging = kopiere_audio(audio_quelle, audio_ziel, quell_chat_id)
            bericht["backup"] = sichere_ziel(conn, ziel, jetzt) if existierte else None
            bericht["offset"] = _schreibe_in_ziel(conn, kopie, jetzt)
            tausche_audio(staging, audio_ziel)
            staging = None
            bericht["nachher"] = zaehle(conn, TEST_CHAT_ID)
            bericht["token_neu"] = token is None
        finally:
            conn.close()
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
    return bericht
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `41 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: Audio ueber Staging kopieren, Pfade relativ/absolut wie in der Quelle umschreiben

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `--leer` — frische Phase 1 mit festem Link (E8)

**Files:**
- Modify: `scripts/test_uebernehmen.py` (`plane_leer`, `leere`, `leer_berichtstext`)
- Modify: `tests/test_testgruppe_uebernehmen.py`

**Interfaces:**
- Consumes: `pruefe_ziel`, `lies_ziel`, `audio_bestand`, `sichere_ziel`,
  `neues_token`, `_token_der_testgruppe`, `_setze_offset` (Task 2–4).
- Produces:
  - `plane_leer(*, ziel: str, audio_ziel: str) -> dict` mit `ziel`, `ziel_lage`, `audio_dateien`, `audio_bytes`
  - `leere(*, ziel: str, audio_ziel: str, jetzt: datetime | None = None) -> dict` — zusätzlich `backup`, `offset`, `token_neu`
  - `leer_berichtstext(bericht: dict, trocken: bool) -> str`

- [ ] **Step 1: Die roten Tests anhängen**

An `tests/test_testgruppe_uebernehmen.py` anhängen:

```python
# --------------------------------------------------------------------------
# Task 6: --leer (E8)
# --------------------------------------------------------------------------

from interview_theater import phasen  # noqa: E402
from scripts import web_gruppe  # noqa: E402


def test_leer_nach_uebernahme_ist_frische_phase_1_mit_gleichem_link(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    tu.leere(ziel=umgebung.ziel, audio_ziel=umgebung.audio_ziel)
    conn = db.verbinde(umgebung.ziel)
    zeilen = tu.zaehle(conn, TEST)
    assert zeilen.pop("gruppe") == 1
    assert set(zeilen.values()) == {0}
    assert phasen.aktuelle(conn, TEST) == 1
    g = repo.hole_gruppe(conn, TEST)
    assert g["web_token"] == "fester-testtoken"
    assert g["bot_name"] == tu.TEST_BOT_NAME and g["kanal"] == "web"
    offset = repo.hole_update_id(conn, tu.TEST_BOT_NAME)
    assert offset == repo.hoechste_web_post_id(conn)
    kanal = WebKanal(conn, TEST, umgebung.audio_ziel)
    assert kanal.hole_updates(offset + 1, timeout=0) == []
    neu = repo.lege_web_post_an(conn, TEST, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a")
    assert [x["update_id"] for x in kanal.hole_updates(offset + 1, timeout=0)] == [neu]
    conn.close()
    assert not (Path(umgebung.audio_ziel) / str(TEST)).exists()


def test_leer_ohne_test_db_legt_sie_an(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bericht = tu.leere(ziel="betrieb/padua-test.db", audio_ziel="audio-padua-test")
    assert bericht["token_neu"] is True and bericht["backup"] is None
    conn = db.verbinde("betrieb/padua-test.db")
    assert repo.hole_gruppe(conn, TEST)["web_token"]
    conn.close()


def test_leer_legt_dieselben_felder_an_wie_web_gruppe_anlegen(tmp_path, monkeypatch):
    """P8: dieselbe Lage wie scripts/web_gruppe.py anlegen, nur mit fester
    chat_id und festem Token."""
    monkeypatch.chdir(tmp_path)
    tu.leere(ziel="betrieb/padua-test.db", audio_ziel="audio-padua-test")
    vergleich = db.verbinde(str(tmp_path / "vergleich.db"))
    db.initialisiere(vergleich)
    daten = web_gruppe.lege_an(vergleich, tu.TEST_BOT_NAME, tu.TITEL_LEER, "")
    conn = db.verbinde("betrieb/padua-test.db")
    unsere = dict(repo.hole_gruppe(conn, TEST))
    ihre = dict(repo.hole_gruppe(vergleich, daten["chat_id"]))
    for feld in ("chat_id", "web_token", "erste_nachricht_am"):
        unsere.pop(feld)
        ihre.pop(feld)
    assert unsere == ihre
    assert repo.hole_update_id(conn, tu.TEST_BOT_NAME) == repo.hoechste_web_post_id(conn)
    conn.close()
    vergleich.close()


def test_leer_trockenlauf_veraendert_nichts(umgebung):
    vorher = fingerabdruck_db(umgebung.ziel)
    audio_vorher = fingerabdruck_baum(umgebung.audio_ziel)
    bericht = tu.plane_leer(ziel=umgebung.ziel, audio_ziel=umgebung.audio_ziel)
    text = tu.leer_berichtstext(bericht, trocken=True)
    assert "nachricht: 1" in text
    assert GEHEIM not in text and "fester-testtoken" not in text
    assert fingerabdruck_db(umgebung.ziel) == vorher
    assert fingerabdruck_baum(umgebung.audio_ziel) == audio_vorher


def test_leer_verweigert_bei_fremden_gruppen(umgebung):
    conn = db.verbinde(umgebung.ziel)
    fuelle_zeile(conn, "gruppe", ANDERE_CHAT, 1, bot_name="alt")
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="fremde"):
        tu.leere(ziel=umgebung.ziel, audio_ziel=umgebung.audio_ziel)


def test_leer_verweigert_die_betriebsdatenbank(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(tu.Verweigert):
        tu.leere(ziel="betrieb/padua.db", audio_ziel="audio-padua-test")
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py -k leer`
Expected: FAIL — `AttributeError: … has no attribute 'leere'` bzw. `'plane_leer'`.

- [ ] **Step 3: Implementieren**

In `scripts/test_uebernehmen.py` nach `uebernimm` einfügen:

```python
def plane_leer(*, ziel: str, audio_ziel: str) -> dict:
    """Was --leer taete -- reine Leseabfrage."""
    pruefe_ziel(ziel, audio_ziel)
    anzahl, groesse = audio_bestand(Path(audio_ziel) / str(TEST_CHAT_ID))
    return {"ziel": ziel, "ziel_lage": lies_ziel(ziel),
            "audio_dateien": anzahl, "audio_bytes": groesse}


def leere(*, ziel: str, audio_ziel: str, jetzt: datetime | None = None) -> dict:
    """E8: die Testgruppe auf eine frische Phase 1 -- dieselben Felder wie
    scripts/web_gruppe.py anlegen (web_gruppe.py:42-51), aber in EINER
    Transaktion mit fester chat_id und festem Token (P8). Phase 1 heisst:
    keine arbeitsstand-Zeile, phasen.aktuelle liefert dann die erste Phase
    (phasen.py:274-281)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    bericht = plane_leer(ziel=ziel, audio_ziel=audio_ziel)
    existierte = Path(ziel).exists()
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(ziel)
    try:
        db.initialisiere(conn)
        token = _token_der_testgruppe(conn)
        bericht["backup"] = sichere_ziel(conn, ziel, jetzt) if existierte else None
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t in db.TABELLEN_MIT_CHAT_ID:
                conn.execute(f"DELETE FROM main.{t} WHERE chat_id = ?", (TEST_CHAT_ID,))
            conn.execute(
                "INSERT INTO main.gruppe (chat_id, bot_name, titel, "
                "erste_nachricht_am, kanal, web_token) VALUES (?, ?, ?, ?, 'web', ?)",
                (TEST_CHAT_ID, TEST_BOT_NAME, TITEL_LEER, jetzt.isoformat(),
                 token or neues_token()),
            )
            bericht["offset"] = _setze_offset(conn, jetzt)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        bericht["token_neu"] = token is None
    finally:
        conn.close()
    verz = Path(audio_ziel) / str(TEST_CHAT_ID)
    if verz.exists():
        shutil.rmtree(verz)
    return bericht
```

Und nach `berichtstext` einfügen:

```python
def leer_berichtstext(bericht: dict, trocken: bool) -> str:
    kopf = "Trockenlauf --leer" if trocken else "Geleert"
    lage = bericht["ziel_lage"]
    z = [f"{kopf}: Testgruppe {TEST_CHAT_ID} ({bericht['ziel']}) -> frische Phase 1"]
    if lage["existiert"]:
        z.append("  Zeilen der Testgruppe, die wegfallen:")
        z += [f"    {t}: {n}" for t, n in lage["zeilen"].items() if n]
    else:
        z.append("  Test-DB gibt es noch nicht -- wird angelegt")
    z.append(f"  Audio der Testgruppe, das wegfaellt: {bericht['audio_dateien']} "
             f"Datei(en), {bericht['audio_bytes']} Bytes")
    z.append("  Link der Testgruppe: "
             + ("bleibt gleich" if lage["token_vorhanden"] else "wird neu erzeugt"))
    if not trocken:
        if bericht.get("backup"):
            z.append(f"  Backup: {bericht['backup']}")
        z.append(f"  Offset von {TEST_BOT_NAME}: {bericht['offset']}")
    return "\n".join(z)
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `47 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: --leer setzt auf frische Phase 1 zurueck (fester Link, Offset konsistent)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Kommandozeile (`main`), Dienstprüfung (P1), Hinweise

**Files:**
- Modify: `scripts/test_uebernehmen.py` (`dienst_laeuft`, Texte, `main`, `__main__`)
- Modify: `tests/test_testgruppe_uebernehmen.py`

**Interfaces:**
- Consumes: `plane`, `uebernimm`, `plane_leer`, `leere`, `berichtstext`,
  `leer_berichtstext`, `Verweigert`.
- Produces: `dienst_laeuft(bot_name: str) -> bool`; `main(argv: list | None = None) -> int`
  (0 = erledigt/Trockenlauf, 1 = verweigert/falscher Aufruf; argparse-Fehler 2).

- [ ] **Step 1: Die roten Tests anhängen**

An `tests/test_testgruppe_uebernehmen.py` anhängen:

```python
# --------------------------------------------------------------------------
# Task 7: Kommandozeile
# --------------------------------------------------------------------------


def _argv(u: Umgebung) -> list:
    return ["--quelle", u.quelle, "--ziel", u.ziel,
            "--audio-quelle", u.audio_quelle, "--audio-ziel", u.audio_ziel]


def test_main_trockenlauf_schreibt_nichts_und_zeigt_keine_inhalte(umgebung, capsys):
    vorher = fingerabdruck_db(umgebung.ziel)
    assert tu.main([str(QUELLE_CHAT), *_argv(umgebung)]) == 0
    aus = capsys.readouterr().out
    assert "Trockenlauf" in aus and "Nichts geschrieben" in aus
    assert GEHEIM not in aus and "fester-testtoken" not in aus
    assert fingerabdruck_db(umgebung.ziel) == vorher


def test_main_ja_uebernimmt_und_nennt_den_startbefehl(umgebung, capsys):
    assert tu.main([str(QUELLE_CHAT), "--ja", *_argv(umgebung)]) == 0
    aus = capsys.readouterr().out
    assert "systemctl --user start interview-theater@padua-test" in aus
    assert "Backup:" in aus
    assert GEHEIM not in aus
    conn = lies(umgebung.ziel)
    assert conn.execute("SELECT COUNT(*) FROM web_post WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == 4
    conn.close()


def test_main_verweigert_bei_laufendem_testbot(umgebung, monkeypatch, capsys):
    monkeypatch.setattr(tu, "dienst_laeuft", lambda bot_name: True)
    vorher = fingerabdruck_db(umgebung.ziel)
    assert tu.main([str(QUELLE_CHAT), "--ja", *_argv(umgebung)]) == 1
    assert "systemctl --user stop interview-theater@padua-test" in capsys.readouterr().out
    assert fingerabdruck_db(umgebung.ziel) == vorher
    assert tu.main(["--leer", "--ja", "--ziel", umgebung.ziel,
                    "--audio-ziel", umgebung.audio_ziel]) == 1
    assert fingerabdruck_db(umgebung.ziel) == vorher


def test_main_trockenlauf_braucht_keinen_gestoppten_bot(umgebung, monkeypatch):
    monkeypatch.setattr(tu, "dienst_laeuft", lambda bot_name: True)
    assert tu.main([str(QUELLE_CHAT), *_argv(umgebung)]) == 0


def test_main_verweigert_quelle_gleich_ziel_mit_exitcode_1(umgebung, capsys):
    argv = ["--quelle", umgebung.quelle, "--ziel", umgebung.quelle,
            "--audio-quelle", umgebung.audio_quelle, "--audio-ziel", umgebung.audio_ziel]
    assert tu.main([str(QUELLE_CHAT), "--ja", *argv]) == 1
    assert "Verweigert" in capsys.readouterr().out


def test_main_verweigert_laufende_aufnahme_und_ziel_bleibt(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = ?",
                 (ZEIT, QUELLE_CHAT))
    conn.commit()
    conn.close()
    vorher = fingerabdruck_db(umgebung.ziel)
    assert tu.main([str(QUELLE_CHAT), "--ja", *_argv(umgebung)]) == 1
    assert fingerabdruck_db(umgebung.ziel) == vorher


def test_main_leer_ja(umgebung, capsys):
    assert tu.main(["--leer", "--ja", "--ziel", umgebung.ziel,
                    "--audio-ziel", umgebung.audio_ziel]) == 0
    assert "Geleert" in capsys.readouterr().out


def test_main_braucht_genau_eins_von_chat_id_und_leer(umgebung, capsys):
    assert tu.main([*_argv(umgebung)]) == 1
    assert tu.main([str(QUELLE_CHAT), "--leer", *_argv(umgebung)]) == 1


def test_dienst_laeuft_ohne_systemctl_ist_falsch(monkeypatch):
    monkeypatch.undo()  # die autouse-Attrappe zuruecknehmen: echte Funktion

    def kein_systemctl(*a, **k):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(tu.subprocess, "run", kein_systemctl)
    assert tu.dienst_laeuft("padua-test") is False
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py -k "main or dienst"`
Expected: FAIL — `AttributeError: … has no attribute 'main'` (bzw.
`'subprocess'`/`'dienst_laeuft'`).

- [ ] **Step 3: Implementieren**

In `scripts/test_uebernehmen.py`: `import argparse` und `import subprocess`
zu den Importen (alphabetisch: `argparse`, `secrets`, `shutil`,
`subprocess`, `tempfile`). Nach `TEXT_AUFNAHME_LAEUFT` einfügen:

```python
TEXT_DIENST_LAEUFT = (
    "Der Testbot laeuft (interview-theater@{bot}). Erst stoppen: "
    "systemctl --user stop interview-theater@{bot} -- sonst liefert ihm sein "
    "laufender Poll die uebernommene Historie als neuen Eingang (P1)."
)
TEXT_DANACH = (
    "\nJetzt den Testbot starten: systemctl --user start interview-theater@{bot}\n"
    "Link der Testgruppe: IT_DB={ziel} IT_WEB_URL={url} python scripts/web_links.py"
)
TEXT_NICHTS = "\nNichts geschrieben. Mit --ja ausfuehren (Testbot vorher stoppen)."
TEXT_AUFRUF = (
    "Aufruf: python -m scripts.test_uebernehmen <quell_chat_id> [--ja]\n"
    "    oder python -m scripts.test_uebernehmen --leer [--ja]"
)
```

Am Ende der Datei anfügen:

```python
# --------------------------------------------------------------------------
# Einstieg
# --------------------------------------------------------------------------


def dienst_laeuft(bot_name: str) -> bool:
    """Laeuft die Unit des Testbots? (P1) Ohne systemctl (Entwicklungsrechner)
    gilt sie als gestoppt."""
    try:
        ergebnis = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet",
             f"interview-theater@{bot_name}"],
            check=False, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return ergebnis.returncode == 0


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.test_uebernehmen",
        description="Spielt eine Padua-Gruppe auf die Testinstanz "
                    f"(chat_id {TEST_CHAT_ID}) oder setzt sie zurueck.",
    )
    zerleger.add_argument("quell_chat_id", nargs="?", type=int)
    zerleger.add_argument("--ja", action="store_true", help="wirklich schreiben")
    zerleger.add_argument("--leer", action="store_true", help="frische Phase 1")
    zerleger.add_argument("--quelle", default=VORGABE_QUELLE)
    zerleger.add_argument("--ziel", default=VORGABE_ZIEL)
    zerleger.add_argument("--audio-quelle", default=VORGABE_AUDIO_QUELLE)
    zerleger.add_argument("--audio-ziel", default=VORGABE_AUDIO_ZIEL)
    a = zerleger.parse_args(argv)
    if a.leer == (a.quell_chat_id is not None):
        print(TEXT_AUFRUF)
        return 1
    try:
        if a.ja and dienst_laeuft(TEST_BOT_NAME):
            raise Verweigert(TEXT_DIENST_LAEUFT.format(bot=TEST_BOT_NAME))
        if a.leer:
            if a.ja:
                bericht = leere(ziel=a.ziel, audio_ziel=a.audio_ziel)
            else:
                bericht = plane_leer(ziel=a.ziel, audio_ziel=a.audio_ziel)
            print(leer_berichtstext(bericht, trocken=not a.ja))
        else:
            pfade = {"quelle": a.quelle, "ziel": a.ziel,
                     "audio_quelle": a.audio_quelle, "audio_ziel": a.audio_ziel}
            if a.ja:
                bericht = uebernimm(a.quell_chat_id, **pfade)
            else:
                bericht = plane(a.quell_chat_id, **pfade)
            print(berichtstext(bericht, trocken=not a.ja))
    except Verweigert as fehler:
        print(f"Verweigert: {fehler}")
        return 1
    if a.ja:
        print(TEXT_DANACH.format(bot=TEST_BOT_NAME, ziel=a.ziel, url=VORGABE_URL))
    else:
        print(TEXT_NICHTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Grün sehen**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py`
Expected: `56 passed`

Run: `$PY -m scripts.test_uebernehmen --help`
Expected: Exitcode 0, Ausgabe beginnt mit `usage: python -m scripts.test_uebernehmen`
und nennt `--ja`, `--leer`, `--quelle`, `--ziel`, `--audio-quelle`, `--audio-ziel`.

- [ ] **Step 5: Commit**

```bash
git add scripts/test_uebernehmen.py tests/test_testgruppe_uebernehmen.py
git commit -m "Testgruppe Padua: Kommandozeile, verweigert --ja bei laufendem Testbot, nennt Start und Link

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Kurzanleitung und AGENTS.md

**Files:**
- Create: `docs/testgruppe-padua.md`
- Modify: `AGENTS.md:126-128`

**Interfaces:**
- Consumes: Pfade aus Task 1, Befehle aus Task 7.
- Produces: nichts für Code. `tests/test_padua_test_vorlagen.py::test_keine_committete_vorlage_traegt_ein_dashboard_token`
  prüft die neue Doku mit (Datei existiert jetzt).

- [ ] **Step 1: Prüfen, dass der Wächter die Doku erfasst (rot, wenn ein Token drinstünde)**

Kein neuer Test nötig: der Wächter aus Task 1 liest `docs/testgruppe-padua.md`,
sobald die Datei existiert. Nach Step 2 läuft er gegen sie.

- [ ] **Step 2: `docs/testgruppe-padua.md` schreiben**

````markdown
# Testgruppe Padua — Kurzanleitung

Eine vierte, vom Betrieb getrennte Padua-Instanz für Tests während des
Workshops (05.–09.10.2026): eigene DB `betrieb/padua-test.db`, eigener
Webdienst (Port 8031, `/padua-test`), eigener Bot `padua-test`, genau **eine**
Gruppe mit der festen chat_id `7000000000099`. Sie erscheint nie auf der
Padua-Übersicht (8030), weil sie eine eigene Datenbank hat. Auf sie lässt sich
jederzeit der Stand einer echten Gruppe spielen. Der Link der Testgruppe
ändert sich dabei nie.

Alle Befehle aus dem Repo-Verzeichnis `~/projekte/interview-theater`.
`PY=~/.local/bin/python3.11` (derselbe wie in der Web-Unit).

## Einmalig einrichten (Robo, nach dem Merge)

1. **Env umstellen.** `betrieb/padua-test.env` auf die Zeilen aus
   `docs/padua-test.env.beispiel` bringen: `IT_KANAL=web`,
   `IT_WEB_CHAT_ID=7000000000099`, `IT_BOT_NAME=padua-test`,
   `IT_WEB_URL=https://lab.artesmobiles.art/padua-test`,
   `IT_DB=betrieb/padua-test.db`, `IT_AUDIO=audio-padua-test`,
   `IT_WORKSHOP=padua-2026`; die Zeile `IT_BOT_TOKEN` **entfernen**. Die
   Modell-/STT-Schlüssel bleiben. Den Inhalt der Datei nie ausgeben; prüfen
   nur so: `grep -c '^IT_KANAL=web$' betrieb/padua-test.env` → `1`,
   `grep -c '^IT_BOT_TOKEN=' betrieb/padua-test.env` → `0`,
   `grep -c '^IT_WORKSHOP=padua-2026$' betrieb/padua-test.env` → `1`.
2. **Alte Testdaten prüfen.** `$PY -m scripts.test_uebernehmen --leer`
   (Trockenlauf). Meldet er „fremde Gruppen" (Reste aus der Telegram-Zeit),
   je Gruppe löschen — das Skript tut das bewusst nicht selbst:
   `set -a; . ./betrieb/padua-test.env; set +a; $PY scripts/loeschen.py <chat_id>`
   (fragt nach, `ja` eintippen).
3. **Testgruppe anlegen.** `$PY -m scripts.test_uebernehmen --leer --ja`.
4. **Dashboard-Token als Drop-in** (nie in eine Datei im Repo):
   ```
   mkdir -p ~/.config/systemd/user/interview-theater-padua-test-web.service.d
   TOKEN=$($PY -c 'import secrets; print(secrets.token_urlsafe(24))')
   printf '[Service]\nEnvironment=IT_WEB_DASHBOARD_TOKEN=%s\n' "$TOKEN" \
     > ~/.config/systemd/user/interview-theater-padua-test-web.service.d/dashboard-token.conf
   chmod 600 ~/.config/systemd/user/interview-theater-padua-test-web.service.d/dashboard-token.conf
   echo "Uebersicht: https://lab.artesmobiles.art/padua-test/dashboard/$TOKEN"
   ```
   Vorlage: `docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel`.
5. **Units.**
   ```
   cp docs/interview-theater-padua-test-web.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now interview-theater-padua-test-web.service
   systemctl --user enable --now interview-theater@padua-test.service
   ```
   Der Bot braucht **keine** eigene Unit-Datei: `interview-theater@.service`
   ist eine Vorlage, `%i` = `padua-test` → `betrieb/padua-test.env`
   (`scripts/betrieb-start.sh`), Log `betrieb/padua-test.log`. Web-Log:
   `betrieb/padua-test-web.log`.
6. **nginx (Birk, fehlt noch):** auf herkules einen Block `/padua-test/` →
   `http://100.75.24.33:8031/padua-test/`, sonst identisch mit `/padua/`
   (dieselben `proxy_set_header`, `proxy_buffering off;`,
   `X-Forwarded-Prefix /padua-test`). Ohne ihn ist die Testinstanz nur im
   Tailnet erreichbar.

## Benutzen

```
# 1. Was wuerde passieren? (nur Zaehlungen, schreibt nichts)
$PY -m scripts.test_uebernehmen <quell_chat_id>

# 2. Testbot stoppen -- sonst verweigert das Skript
systemctl --user stop interview-theater@padua-test

# 3. Wirklich uebernehmen (legt vorher selbst ein Backup an)
$PY -m scripts.test_uebernehmen <quell_chat_id> --ja

# 4. Testbot starten
systemctl --user start interview-theater@padua-test

# 5. Link der Testgruppe (aendert sich nie)
IT_DB=betrieb/padua-test.db IT_WEB_URL=https://lab.artesmobiles.art/padua-test $PY scripts/web_links.py
```

chat_ids der echten Gruppen: `padua-gruppe1` = `7000000000000`, die anderen
in ihren Env-Dateien (`IT_WEB_CHAT_ID`), ohne die Datei auszugeben:
`grep '^IT_WEB_CHAT_ID=' betrieb/padua-gruppe2.env`.

Zurück auf frische Phase 1: Testbot stoppen,
`$PY -m scripts.test_uebernehmen --leer --ja`, Testbot starten.

Backups liegen als `betrieb/padua-test.db.bak-<zeit>` daneben. Aufräumen von
Hand, wenn die Woche vorbei ist.

## Was übernommen wird

Alles, was in der Quelle an der Gruppe hängt (`db.TABELLEN_MIT_CHAT_ID`),
mit **unveränderten ids**, außer `aufruf` (Kosten — die Testgruppe beginnt
den Tag mit leerem Deckel) und `web_strom` (flüchtig). Die Quelle wird nur
gelesen. Audio wird kopiert, nie verschoben.

## Fallen

- **Nie `cp` auf eine `.db`.** WAL: was im `-wal` steht, fehlte der Kopie.
  Das Skript kopiert per `VACUUM INTO` aus einer read-only-Verbindung.
- **Wasserzeichen.** Der Bot liest im Web-Kanal ab `bot_zustand.letzte_update_id + 1`.
  Das Skript setzt den Offset des Testbots auf die höchste `web_post`-id,
  sonst beantwortete er die ganze Historie noch einmal. Deshalb muss er bei
  `--ja` **gestoppt** sein: sein laufender Poll hält den alten Offset bis zu
  25 s fest. Das Tell, falls es doch passiert: der Testbot antwortet auf
  alte Nachrichten. Das Gegenteil (Bot schweigt, 200 OK, kein Traceback)
  hieße, der Offset steht über neuen Eingängen. Dann `--ja` erneut laufen
  lassen.
- **Fremde chat_ids.** Die Test-DB darf nur die Testgruppe enthalten (die
  ids werden 1:1 übernommen und kollidierten sonst). Das Skript verweigert
  und nennt den Löschbefehl.
- **Laufende Aufnahme in der Quelle.** Verweigert. Später noch einmal.
- **Unfertige Aufnahmen** (Status `empfangen`/`transkribiert`) holt der
  Nachhol-Arbeiter des Testbots nach dem Start nach. Das kostet Whisper auf
  dem Deckel der Testgruppe.
````

- [ ] **Step 3: AGENTS.md ergänzen**

In `AGENTS.md` (Zeilen 126–128) den Satz

```
einer Gruppe). `scripts/web_gruppe.py anlegen <bot_name>` legt eine Gruppe
für den Web-Kanal an und gibt Link, chat_id und die zwei Env-Zeilen aus
(siehe „Der Web-Kanal").
```

ersetzen durch

```
einer Gruppe). `scripts/web_gruppe.py anlegen <bot_name>` legt eine Gruppe
für den Web-Kanal an und gibt Link, chat_id und die zwei Env-Zeilen aus
(siehe „Der Web-Kanal"). `scripts/test_uebernehmen.py <quell_chat_id> [--ja]`
spielt den Stand einer Padua-Gruppe auf die getrennte Testinstanz
(`betrieb/padua-test.db`, Web 8031 `/padua-test`, Bot `padua-test`, feste
chat_id `7000000000099`, fester Link), `--leer` setzt sie auf Phase 1 zurück
— Quelle nur `mode=ro`, Testbot vorher stoppen, Anleitung
`docs/testgruppe-padua.md`.
```

- [ ] **Step 4: Wächter laufen lassen**

Run: `$PY -m pytest -q tests/test_padua_test_vorlagen.py`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add docs/testgruppe-padua.md AGENTS.md
git commit -m "Testgruppe Padua: Kurzanleitung (einrichten, benutzen, Fallen) und Zeile in AGENTS.md

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Abnahme

**Files:** keine Änderung (außer einer etwaigen `.suite.log`, die **nicht**
committet wird).

- [ ] **Step 1: Gezielte Tests**

Run: `$PY -m pytest -q tests/test_padua_test_vorlagen.py tests/test_testgruppe_uebernehmen.py tests/test_interviews_uebernehmen.py tests/test_web_gruppe_skript.py tests/test_web_kanal.py`
Expected: `65 passed` plus die Zahl N aus Task 0, kein `failed`.

- [ ] **Step 2: Profilprüfung Padua**

Run: `$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?`
Expected: letzte Zeile `EXIT 0`.

- [ ] **Step 3: Volle Suite, auf das Ende warten**

Ein Vordergrund-Aufruf ist auf 600 s begrenzt, die Suite brauchte zuletzt
rund 300 s. Deshalb in eine Datei schreiben und das Ende abwarten (Claude
Code `timeout: 600000`), nicht abbrechen.

Run: `$PY -m pytest -q -m "not dortmund" > .suite.log 2>&1; echo EXIT $?`
Expected: `EXIT 0`; die Zusammenfassungszeile aus `.suite.log`
(`tail -1 .suite.log`) im Bericht zitieren. Ist etwas rot, das mit dieser
Karte nichts zu tun hat, mit Testname im Bericht nennen und gegen `main`
gegenprüfen (`git stash` NICHT benutzen — stattdessen
`git worktree add /tmp/<name> main` und dort denselben Test laufen lassen).

- [ ] **Step 4: Nachweis E11 und Quelle unverändert (für den Bericht)**

Run: `$PY -m pytest -q tests/test_testgruppe_uebernehmen.py -k "quelle_bleibt_unveraendert or trockenlauf_zaehlt or verweigert_ohne"`
Expected: `3 passed`. Das ist der Hash-Nachweis, dass die Übernahme die
Quell-DB (`padua.db`) und ihr Audio nicht beschreibt. Am echten Betrieb
wird nichts ausgeführt.

- [ ] **Step 5: Bericht**

Im Kartenbericht festhalten: die Commit-SHAs je Task, die Zahlen aus
Step 1–3, jede „ANNAHME widerlegt" mit `datei:zeile`, und die Liste der
Schritte für Robo (= `docs/testgruppe-padua.md`, „Einmalig einrichten").
`.suite.log` nicht committen.

---

## Selbstprüfung des Plans (Abdeckung der Karte)

| Auftrag/Pflichttest | Task |
|---|---|
| Web-Unit 8031/`/padua-test`/IT_DB/IT_AUDIO/IT_WORKSHOP/Drop-in-Token, Bot-Unit ohne neue Datei | 1 |
| Skript Trockenlauf mit Zählungen | 2 |
| `--ja`: Backup, VACUUM INTO aus `mode=ro`, nur chat_id, Umschreiben auf 099, Ersetzen in einer Transaktion | 3 |
| festes Token / Link bleibt gleich / Quell-Token überlebt nicht | 3 (Tests), 6 (`--leer`) |
| Wasserzeichen/IDs, Bot arbeitet weiter | 4 |
| Audio kopieren, Pfade umschreiben, Testverzeichnis leeren | 5 |
| Verweigern bei laufender Aufnahme / fremden chat_ids / Quelle == Ziel / Ziel == padua.db | 2, 3, 7 |
| `--leer` | 6 |
| Unit-Vorlagen-Test (kein Token, kein 0.0.0.0, Log eigener Name) | 1 |
| Quelle unverändert (Hash DB + Audio), Trockenlauf verändert nichts (Hash Ziel) | 2, 3, 7, 9 |
| Doku + AGENTS.md-Zeile | 8 |
| Neustart-Hinweis (hier: Stopp vorher, Start danach, P1) | 7 |

# Padua: Interview-Transkript als EINE Fliesstext-Blase + Statuszeilen (Karte t_ea994c7f)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Geschrieben von der Planungskarte t_ea994c7f, ausgefuehrt von Karte
t_778eb4fc. Die Kartenbeschreibung ist die Spezifikation; die
Architekturentscheidungen A–J unten sind vom Orchestrator/Architekten
gesetzt und **nicht neu zu verhandeln**. Wer beim Umsetzen merkt, dass eine
davon am Code scheitert, haelt das unter „ANNAHME widerlegt" mit
`datei:zeile` fest, statt still davon abzuweichen.

**Goal:** Im Web-Kanal (nur mit `[interview] fliesstext = true`, also Padua)
wird aus „Interview N, part K:" je Sprachnachricht EINE kursive Blase mit
Mikrofon, die mit jedem Teil waechst; „Recording stopped.", die
Abschlusszeile und „… was very short …" gehen als Systemzeilen raus; die
Abschlusszeile spricht endlich die Sprache des Workshops.

**Architecture:** Neuer Profilschalter `workshop.interview_fliesstext()`;
`aufnahme.fliesstext_aktiv(conn, chat_id)` = Schalter **und** Web-Gruppe. Der
Interview-Kopf merkt sich die `web_post`-id seiner Blase in der additiven
Spalte `aufnahme.echo_message_id`; jeder fertige Teil baut den Blasentext
aus `repo.hole_teile` neu und legt die Blase an (`tg.sende(...,
transkript=True)` → `web_post.typ='transkript'`) oder aendert sie
(`tg.aendere_text`), serialisiert durch eine Sperre je Kopf. Die Chatansicht
rendert `typ='transkript'` als `blase bot transkript` (kursiv, Theme-Tokens).

**Tech Stack:** Python 3.11, SQLite, Standardbibliothek-HTTP, Vanilla-JS,
pytest (+ optional Playwright unter `tests/e2e/`).

## Ausdruecklich NICHT in dieser Karte (nicht planen, nicht bauen)

- **Einen einzelnen Teil loeschen und die Blase neu aufbauen.** Die
  Abnahme von t_778eb4fc nennt das noch — der Orchestrator hat es
  gestrichen. Es gibt keinen Loeschweg fuer Teile, und es wird keiner
  gebaut. (Hinweis: weil die Blase bei jedem Teil aus `repo.hole_teile`
  NEU gebaut wird, waere ein spaeterer Loeschweg trivial — er bestuende
  nur aus „Teil raus, `_sende_transkript_blase(..., nur_aendern=True)`".)
- Telegram-Folgeblasen ueber 4096 Zeichen, `editMessageText` auf Telegram.
- Die „…"-Zeile, waehrend ein Teil noch transkribiert wird.
- Alles zur STT-Sprache (bleibt `auto`; Teile in verschiedenen Sprachen
  stehen einfach nebeneinander).
- PTT- und andere STT-Echos (die stehen seit B7 schon kursiv in der
  eingehenden Sprachblase, `aufnahme._web_sprachblase`).
- `_TEXT_LEER_VERWORFEN` / `_TEXT_OHNE_AUFNAHME` (`aufnahme.py:1745`) bleiben
  gewoehnliche Textzeilen — die Karte nennt nur „Recording stopped.", die
  Abschlusszeile und „very short".

## Global Constraints (fuer jede Aufgabe bindend)

- Branch `wt/t_778eb4fc`. Kein Merge, kein Push. Ein Commit je Aufgabe.
- `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
  — jeder Befehl unten setzt `$PY` voraus (`export PY=…` einmal je Shell).
- Testbefehle **im Vordergrund** laufen lassen und abwarten, nie im
  Hintergrund.
- Profilschalter `[interview] fliesstext`, Vorgabe **False**. Eingebautes
  Vorgabeprofil und `dortmund-2026` bleiben **bitgleich**
  (`tests/test_profil_bitgleich.py`, `tests/test_sprache_bitgleich.py`).
- Nur Web-Kanal: `aufnahme.ist_web_gruppe(conn, chat_id)`. Eine
  Telegram-Gruppe behaelt auch mit Schalter das alte Echo je Teil samt
  Leiste (`knoepfe.biete_nach_teil`).
- Deutscher Wortlaut bestehender Texte aendert sich nirgends. Neue
  Nutzertexte: deutsche Modulkonstante `_TEXT_*` + englischer Eintrag in
  `interview_theater/sprachen/en/texte.toml` unter `["aufnahme"]`, gelesen
  ueber `T.` (Waechter: `tests/test_sprache_texte.py` — gleiche
  Platzhalter, kein deutscher Inline-Text).
- Keine `style="…"`-Attribute, keine `on…=`-Handler (CSP, AGENTS.md „Die
  Gestaltung"). Das Mikrofon steht im **Text**, nicht im CSS.
- Kein Modellaufruf in neuen Pfaden, kein SQL ausserhalb `repo.py`/`db.py`.
- Baseline vor dem Start (gemessen 04.10.2026):
  `$PY -m pytest -q tests/test_web_kanal_naht.py tests/test_web_chat_system_zeile.py tests/test_workshop.py tests/test_db.py tests/test_sprache_texte.py`
  → `1291 passed`.

## Entwurfsentscheidungen (vom Architekten gesetzt, hier nur umgesetzt)

- **A Zustand:** additive Spalte `aufnahme.echo_message_id INTEGER` am
  Interview-Kopf (NULL = noch keine Blase), migriert ueber
  `db._migriere_fehlende_spalten` (generisch, `db.py:1261`). Zwei
  Repo-Funktionen unter `_gesperrt`: `echo_message_id(conn, kopf_id)` und
  `setze_echo_message_id(conn, kopf_id, message_id)`. Ueberlebt einen
  Neustart. `scripts/interviews_uebernehmen.py` kopiert mit fester
  Spaltenliste (`_AUFNAHME_SPALTEN`, Zeile 205) — die Spalte wandert also
  **nicht** in eine fremde Gruppe (gewollt: die id zeigte auf eine fremde
  `web_post`-Zeile).
- **B Text:** bei JEDEM Teil neu gebaut aus `repo.hole_teile(conn,
  kopf_id)`: alle Teile mit nicht-leerem `transkript` in dieser Reihenfolge
  (`id ASC`), mit `"\n\n"` verbunden, davor die Zeile
  `_TEXT_TRANSKRIPT_KOPF = "🎙 {name}"` (`name = anzeigename(conn, kopf,
  "Interview")`) und eine Leerzeile. Ausgewaehlt wird nach `transkript`,
  **nicht** nach `status`: in `_teil_abschliessen` steht der aktuelle Teil
  beim Echo noch auf `'transkribiert'` (Status `'fertig'` kommt danach,
  `aufnahme.py:1353`); sein Transkript liegt aber schon in der Datenbank
  (`_verarbeite`, `aufnahme.py:604-606`). Per `an_den_bot` abgezweigte
  Teile fallen heraus: `repo.loese_aus_interview` setzt `teil_von = NULL`
  (`repo.py:717-735`), `hole_teile` filtert `WHERE teil_von = ?`
  (`repo.py:611-626`) — **verifiziert**.
- **C Nebenlaeufigkeit:** Teile laufen im Pool (`bot.POOL_GROESSE`).
  „Teile lesen + Blase anlegen oder aendern + `echo_message_id` merken"
  laeuft unter einer `threading.Lock` je Kopf (Register wie
  `ablauf._sperre_fuer`, `ablauf.py:495`). Ein Test mit zwei Threads zeigt
  genau EINE Blase mit beiden Teilen.
- **D Kanalflaeche:** `transkript: bool = False` an `telegram.Telegram.sende`
  **und** `web_kanal.WebKanal.sende`, direkt hinter `system` (Vorbild
  `system`, in beiden Docstrings dokumentiert). Telegram: No-Op. Web:
  `web_post.typ = repo.WEB_TYP_TRANSKRIPT = "transkript"`.
  `tests/test_web_kanal_naht.py::test_signaturen_stimmen_mit_telegram_ueberein`
  vergleicht die **Parameterlisten** beider Klassen — deshalb an beiden in
  derselben Position. `simulation/attrappe.py` (`sende(self, chat_id, text,
  **_kw)`, Zeile 77) und die Test-Attrappen nehmen `**kw` — keine Anpassung
  noetig. `aendere_text` behaelt den `typ` (aendert nur `text` und zaehlt
  `aenderung` hoch, `repo.py:4220`). Die Poll-Abfragen in `web_daten.py`
  arbeiten mit einer **Sperrliste** (`_CHAT_VERBORGEN = ("befehl",)` plus
  `typ != 'knopf'`, `web_daten.py:1614-1709`) — `'transkript'` wird also
  ausgeliefert und ueber `aenderung` neu ausgeliefert, ohne Codeaenderung
  dort (Test in Aufgabe 3 haelt es fest).
- **E Darstellung:** `web_chat._blase_html` (Zweig neben `typ == "system"`,
  `web_chat.py:3265`) und JS `klasseVon` (`web_chat.py:766`) kennen
  `'transkript'` → Klasse `transkript` (`blase bot transkript`). CSS
  `.blase.transkript { font-style: italic; … }` in `web_chat._CSS_CHAT`
  (`web_chat.py:242ff.`) **und** in `web_gestalt._CHAT_A`/`_CHAT_B`
  (neben `.blase.sprache`, `web_gestalt.py:973` und `:1075`) mit
  `color: var(--text)`. Das Paar `text`/`grund-2` steht schon in
  `web_gestalt.KONTRAST` (Blase auf `--grund-2`) — **kein neues Paar**.
- **F Mitschrift:** beim ersten Anlegen geht die Blase wie heute als
  `nachricht`-Zeile `typ='transkript'`, versteckt (`repo.merke_nachricht(...,
  TYP_TRANSKRIPT, …, 1)`). Spaetere Aenderungen schreiben `nachricht`
  **nicht** nach: die Zeile steht in keinem Prompt-Fenster, die Wahrheit ist
  `aufnahme.transkript`.
- **G** `_web_sprachblase(conn, chat_id, row["message_id"], None)` (B7) bleibt
  in `_teil_abschliessen` unveraendert stehen.
- **H Sprachschicht:** `_text_interview_gespeichert_web` (`aufnahme.py:1220-1244`)
  bekommt drei Konstanten mit dem **genauen** heutigen deutschen Wortlaut
  und englische Eintraege. **Nicht** hinter dem Schalter (fuer Deutsch
  aendert sich nichts).
- **I Systemzeilen:** hinter dem Schalter **und** nur fuer Web-Gruppen
  (`fliesstext_aktiv`). `knoepfe.biete_nach_aufnahme` und
  `knoepfe.biete_aufnahme` bekommen `system: bool = False` und reichen es an
  `_sende_knoepfe(..., system=…)` bzw. `tg.sende` weiter.
- **J** Schalter aus oder Telegram-Gruppe: `_teil_abschliessen` verhaelt sich
  exakt wie heute (gleicher Text, gleiche Leiste, gleicher `typ`).

## Dateikarte

| Datei | Was sich aendert |
|---|---|
| `interview_theater/workshop.py` | `interview_fliesstext()` |
| `workshop/padua-2026/profil.toml` | `[interview] fliesstext = true` |
| `interview_theater/db.py` | Spalte `aufnahme.echo_message_id` |
| `interview_theater/repo.py` | `WEB_TYP_TRANSKRIPT`, `echo_message_id`, `setze_echo_message_id` |
| `interview_theater/telegram.py` · `web_kanal.py` | `sende(..., transkript=False)` |
| `interview_theater/aufnahme.py` | `fliesstext_aktiv`, `transkript_blasentext`, `_sende_transkript_blase`, Sperren-Register, Verdrahtung in `_teil_abschliessen`, drei Texte der Abschlusszeile, `system` an `_sende_und_merke`/`_sende_nach_interview` |
| `interview_theater/knoepfe/interviews.py` | `system` an `biete_aufnahme`, `biete_nach_aufnahme` |
| `interview_theater/befehle.py` · `erkenner.py` | „Aufnahme beendet." als Systemzeile |
| `interview_theater/sprachen/en/texte.toml` | vier neue Eintraege unter `["aufnahme"]` |
| `interview_theater/web_chat.py` · `web_gestalt.py` | Klasse `transkript` (Server, JS, CSS ×3) |
| `tests/test_interview_fliesstext.py` (neu) | Verhalten, Nebenlaeufigkeit, Systemzeilen, Sprache |
| `tests/test_workshop.py` · `tests/test_db.py` · `tests/test_web_chat_system_zeile.py` · `tests/test_web_e2e_http.py` · `tests/e2e/test_web_chat_e2e.py` | erweitert |
| `AGENTS.md` | ein Absatz unter „Der Web-Kanal" |

---

### Task 1: Profilschalter `[interview] fliesstext`

**Files:**
- Modify: `interview_theater/workshop.py` (neue Funktion direkt nach `ueberarbeitung_aktiv`, ~Zeile 997)
- Modify: `workshop/padua-2026/profil.toml` (neuer Abschnitt am Dateiende, nach `[ueberarbeitung]`)
- Test: `tests/test_workshop.py` (anhaengen)

**Interfaces:**
- Produces: `workshop.interview_fliesstext(profil: Profil | None = None) -> bool` (Vorgabe False). Spaetere Aufgaben rufen sie **ueber das Modul** (`workshop.interview_fliesstext()`), damit Tests sie mit `monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)` umschalten koennen.

- [ ] **Step 1: Failing test schreiben** — an `tests/test_workshop.py` anhaengen:

```python
def test_interview_fliesstext_nur_in_padua():
    """Karte t_ea994c7f: wie [prueflauf] -- aus in der Vorgabe und in
    Dortmund, an nur in Padua."""
    assert workshop.interview_fliesstext(None) is False
    assert workshop.interview_fliesstext(workshop.lade("dortmund-2026")) is False
    assert workshop.interview_fliesstext(workshop.lade("padua-2026")) is True


def test_interview_fliesstext_liest_den_baum():
    profil = workshop.Profil("test", None, {"interview": {"fliesstext": True}})
    assert workshop.interview_fliesstext(profil) is True
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_workshop.py -k interview_fliesstext`
Expected: `2 failed` mit `AttributeError: module 'interview_theater.workshop' has no attribute 'interview_fliesstext'`.

- [ ] **Step 3: Implementieren** — in `interview_theater/workshop.py` nach `ueberarbeitung_aktiv`:

```python
def interview_fliesstext(profil: Profil | None = None) -> bool:
    """Ein Interview = EINE Transkriptblase im Web-Chat (Padua, 04.10.2026,
    Karte t_ea994c7f): jeder fertige Teil schreibt dieselbe Blase als
    Fliesstext weiter, statt eine eigene "Interview N, Teil K:"-Nachricht
    zu schicken; dazu gehen "Aufnahme beendet.", die Abschlusszeile und
    "war sehr kurz" als Systemzeilen raus.

    Vorgabe false -- Dortmund und das eingebaute Profil bleiben bitgleich.
    Gilt nur fuer Web-Gruppen (``aufnahme.fliesstext_aktiv``): Telegram
    behaelt auch mit dem Schalter das Echo je Teil samt Leiste."""
    profil = profil or aktiv()
    return bool(profil.wert("interview.fliesstext", False))
```

Am Ende von `workshop/padua-2026/profil.toml` anhaengen:

```toml

# Ein Interview = EINE Transkriptblase im Web-Chat (04.10.2026, Karte
# t_ea994c7f): Fliesstext mit Mikrofon statt "part K:" je Sprachnachricht,
# und die Statuszeilen rund ums Interview als Systemzeilen. Nur Web --
# Telegram bleibt beim Echo je Teil.
[interview]
fliesstext = true
```

ANNAHME: `workshop.lade` kennt keine Liste erlaubter Abschnitte (gelesen:
nur `[mehrdeutig]` wird inhaltlich geprueft, `workshop.py:690`), und
`scripts/pruefe_profil.py` prueft keine Abschnittsnamen. Step 4 belegt das
mit `pruefe_profil`; meldet es einen Fehler zu `[interview]`, dort den
Abschnitt bekannt machen und das hier unter „ANNAHME widerlegt" vermerken.

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_workshop.py && $PY -m scripts.pruefe_profil padua-2026 && $PY -m scripts.pruefe_profil dortmund-2026`
Expected: alle Tests `passed`; zwei Zeilen `padua-2026: in Ordnung…` und `dortmund-2026: in Ordnung…`, Exit-Code 0.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/workshop.py workshop/padua-2026/profil.toml tests/test_workshop.py
git commit -m "Add profile switch [interview] fliesstext (Padua only)"
```

---

### Task 2: Spalte `aufnahme.echo_message_id` + Repo-Zugriff

**Files:**
- Modify: `interview_theater/db.py:132-206` (`CREATE TABLE IF NOT EXISTS aufnahme`, letzte Spalte)
- Modify: `interview_theater/repo.py` (zwei Funktionen direkt nach `teil_nummer`, ~Zeile 640)
- Test: `tests/test_db.py` (anhaengen; nutzt die vorhandene Konstante `_ALTE_AUFNAHME_UND_WEB_POST`, Zeile 479)

**Interfaces:**
- Produces: `repo.echo_message_id(conn, kopf_id: int) -> int | None`, `repo.setze_echo_message_id(conn, kopf_id: int, message_id: int) -> None`.

- [ ] **Step 1: Failing tests** — an `tests/test_db.py` anhaengen:

```python
def test_echo_message_id_spalte_existiert_frisch_und_wird_nachgeruestet(tmp_path):
    """Karte t_ea994c7f: die web_post-id der EINEN Transkriptblase steht am
    Interview-Kopf -- additiv, ueber die generische Migration."""
    frisch = db.verbinde(str(tmp_path / "frisch.db"))
    db.initialisiere(frisch)
    assert "echo_message_id" in [r[1] for r in frisch.execute("PRAGMA table_info(aufnahme)")]

    alt = db.verbinde(str(tmp_path / "alt.db"))
    alt.executescript(_ALTE_AUFNAHME_UND_WEB_POST)
    alt.execute(
        "INSERT INTO aufnahme (chat_id, message_id, klasse, quelle, status, empfangen_am) "
        "VALUES (1, 10, 'lang', 'sprache', 'laeuft', '2026-10-04T10:00:00+00:00')"
    )
    alt.commit()
    assert "echo_message_id" not in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]

    db.initialisiere(alt)

    assert "echo_message_id" in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]
    zeile = alt.execute("SELECT * FROM aufnahme WHERE chat_id = 1").fetchone()
    assert zeile["klasse"] == "lang", "Migration darf keine Daten verlieren"
    assert zeile["echo_message_id"] is None


def test_echo_message_id_lesen_und_setzen(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    kopf = repo.lege_interview_an(c, 1)

    assert repo.echo_message_id(c, kopf) is None
    repo.setze_echo_message_id(c, kopf, 4711)
    assert repo.echo_message_id(c, kopf) == 4711
    assert repo.echo_message_id(c, 99999) is None
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_db.py -k echo_message_id`
Expected: `2 failed` (`assert 'echo_message_id' in [...]` bzw. `AttributeError: … 'echo_message_id'`).

- [ ] **Step 3: Implementieren**

In `db.py` die letzte Spalte der `aufnahme`-Tabelle von
`  kalibrierung    INTEGER NOT NULL DEFAULT 0` auf ein Komma umstellen und
dahinter einfuegen (vor `);`):

```sql
  kalibrierung    INTEGER NOT NULL DEFAULT 0,
  -- Nur am Interview-KOPF (klasse='lang'): die web_post-id der EINEN
  -- Transkriptblase dieses Interviews im Web-Chat (Padua, 04.10.2026,
  -- Karte t_ea994c7f, [interview] fliesstext). NULL = noch keine Blase.
  -- In der Datenbank statt im Prozess, weil der Nachhol-Arbeiter einen
  -- Teil auch nach einem Neustart fertig machen kann -- dann schreibt er
  -- dieselbe Blase weiter. Additiv nachgeruestet ueber
  -- _migriere_fehlende_spalten.
  echo_message_id INTEGER
);
```

In `repo.py` nach `teil_nummer`:

```python
@_gesperrt
def echo_message_id(conn: sqlite3.Connection, kopf_id: int) -> int | None:
    """Die web_post-id der Transkriptblase eines Interviews (Karte
    t_ea994c7f), oder None -- noch keine Blase oder kein solcher Kopf."""
    zeile = conn.execute(
        "SELECT echo_message_id FROM aufnahme WHERE id = ?", (kopf_id,)
    ).fetchone()
    return None if zeile is None else zeile["echo_message_id"]


@_gesperrt
def setze_echo_message_id(conn: sqlite3.Connection, kopf_id: int, message_id: int) -> None:
    """Merkt die Transkriptblase am Interview-Kopf (``aufnahme._sende_transkript_blase``)."""
    conn.execute(
        "UPDATE aufnahme SET echo_message_id = ? WHERE id = ?", (message_id, kopf_id)
    )
    conn.commit()
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_db.py tests/test_interviews_uebernehmen.py`
Expected: alle `passed`.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/db.py interview_theater/repo.py tests/test_db.py
git commit -m "Add aufnahme.echo_message_id for the single transcript bubble"
```

---

### Task 3: Kanalflaeche `sende(..., transkript=False)` + `WEB_TYP_TRANSKRIPT`

**Files:**
- Modify: `interview_theater/repo.py` (Konstante direkt nach `WEB_TYP_SYSTEM`, ~Zeile 4065)
- Modify: `interview_theater/telegram.py:166-198` (`Telegram.sende`)
- Modify: `interview_theater/web_kanal.py:399-421` (`WebKanal.sende`)
- Create: `tests/test_interview_fliesstext.py` (Gerüst + erste Tests; die weiteren Aufgaben haengen hier an)

**Interfaces:**
- Produces: `repo.WEB_TYP_TRANSKRIPT = "transkript"`; `Telegram.sende(self, chat_id, text, parse_mode=None, klartext=None, system=False, transkript=False) -> int`; `WebKanal.sende(self, chat_id, text, parse_mode=None, klartext=None, system=False, transkript=False) -> int`.
- Produces (Testgerüst, von Aufgaben 4–9 benutzt): Fixtures `conn`, `klm`, `web`, `fliesstext`, `padua`; Klasse `_Kanal`; Helfer `_interview`, `_posts`; Konstante `TEILE`.

- [ ] **Step 1: Testgerüst + failing tests** — `tests/test_interview_fliesstext.py` neu anlegen:

```python
"""Padua: ein Interview = EINE Transkriptblase im Web-Chat (Karte
t_ea994c7f, ``[interview] fliesstext``). Telegram und das Vorgabeprofil
bleiben beim Echo je Teil."""

import inspect
import re
import threading
import time

import pytest

from interview_theater import (
    aufnahme, db, phasen, repo, sprache, telegram, web_daten, web_kanal, workshop,
)
from tests.test_aufnahme import (
    LLMAttrappe, TEIL_A, TEIL_B, TelegramAttrappe, interview_an, sprachnachricht,
    stt_attrappe,
)

#: Vier Teile ohne die Woerter "Teil"/"part" -- der Test sucht genau die.
TEILE = [
    "Ich kam im Winter an.",
    "Der Bahnhof war leer.",
    "Niemand hat gewartet.",
    "Dann kam meine Tante.",
]


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    # Phase 3: in Padua liefe eine Sprachnachricht in Phase 1 sonst in die
    # Hintergrund-Diskussion ([diskussion] aktiv).
    phasen.setze(c, 1, 3, "befehl")
    return c


@pytest.fixture
def klm():
    return LLMAttrappe()


class _Kanal(web_kanal.WebKanal):
    """Der echte WebKanal (schreibt ``web_post``), nur ohne Upload-Verzeichnis:
    ``lade_datei`` legt eine fingierte Audiodatei hin wie die
    TelegramAttrappe aus ``tests/test_aufnahme.py``."""

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


@pytest.fixture
def web(conn, tmp_path):
    repo.setze_gruppe_kanal(conn, 1, "web")
    return _Kanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)


@pytest.fixture
def fliesstext(monkeypatch):
    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _interview(conn, kanal, einst, klm, texte, message_id=600):
    """Modus an, je Text eine Sprachnachricht durch den echten Weg
    (``empfange`` + ``verarbeite``). Liefert die id des Kopfes."""
    kopf_id = interview_an(conn)
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(
            conn, kanal, einst, sprachnachricht(dauer=20, message_id=message_id + i)
        )
        aufnahme.verarbeite(conn, kanal, klm, einst, stt_attrappe(text), aid)
    return kopf_id


def _posts(conn, typ):
    return conn.execute(
        "SELECT * FROM web_post WHERE chat_id = 1 AND richtung = 'aus' AND typ = ? "
        "ORDER BY id", (typ,),
    ).fetchall()


# -- Aufgabe 3: die Kanalflaeche ---------------------------------------------


def test_webkanal_legt_eine_transkriptzeile_an_und_aendert_sie(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    zeile = conn.execute("SELECT typ FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == repo.WEB_TYP_TRANSKRIPT == "transkript"

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    zeile = conn.execute("SELECT typ, text, aenderung FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == "transkript", "aendere_text laesst den typ stehen"
    assert zeile["text"].endswith("Welt")
    assert zeile["aenderung"] is not None


def test_der_poll_liefert_die_transkriptzeile_und_ihre_aenderung(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    assert [z["typ"] for z in web_daten.web_chatverlauf(conn, 1) if z["id"] == mid] == ["transkript"]

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    geaendert, _stand = web_daten.web_chataenderungen(conn, 1, 0)
    assert mid in [z["id"] for z in geaendert]


def test_telegram_kennt_transkript_als_no_op():
    parameter = inspect.signature(telegram.Telegram.sende).parameters
    assert parameter["transkript"].default is False
    assert list(parameter)[-2:] == ["system", "transkript"]
```

ANNAHME: `web_daten.web_chatverlauf` liefert Zeilen mit Schluesseln `id`
und `typ` (die Chatansicht liest `n.typ`, `web_chat.py:767`), und
`web_chataenderungen(conn, chat_id, seit)` liefert `(zeilen, stand)` mit
`id` je Zeile (`web_daten.py:1678-1714`). Falls die Schluessel anders
heissen, im Test anpassen — nicht in `web_daten.py`.

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py`
Expected: `3 failed` — `TypeError: … unexpected keyword argument 'transkript'` (zweimal) und `KeyError: 'transkript'`.

- [ ] **Step 3: Implementieren**

`repo.py`, direkt nach `WEB_TYP_SYSTEM = "system"`:

```python
#: Die EINE Transkriptblase eines Interviews (Padua, 04.10.2026, Karte
#: t_ea994c7f, ``[interview] fliesstext``): waechst mit jedem Teil ueber
#: ``aendere_web_text``. Die Chatansicht setzt sie kursiv
#: (``web_chat.py``, ``klasseVon``). Wie ``WEB_TYP_SYSTEM`` nur eine
#: Anzeige-Unterscheidung -- die Mitschrift in ``nachricht`` traegt
#: ``typ='transkript'`` (versteckt) wie jedes Teil-Echo.
WEB_TYP_TRANSKRIPT = "transkript"
```

`telegram.py`, Signatur und Docstring von `Telegram.sende`:

```python
    def sende(self, chat_id: int, text: str, parse_mode: str | None = None,
              klartext: str | None = None, system: bool = False,
              transkript: bool = False) -> int:
```

und im Docstring nach dem `system`-Absatz:

```
        ``transkript`` ist ebenfalls ein No-Op (Karte t_ea994c7f): nur die
        Chatansicht des Web-Kanals kennt die EINE kursive Transkriptblase
        eines Interviews (``web_kanal.WebKanal.sende``). Telegram bekommt sie
        nie -- dort bleibt das Echo je Teil (``aufnahme.fliesstext_aktiv``).
```

`web_kanal.py`, `WebKanal.sende`:

```python
    def sende(self, chat_id: int, text: str, parse_mode=None, klartext=None,
              system: bool = False, transkript: bool = False) -> int:
        """…(bestehender Docstring bleibt)…

        ``transkript`` (Karte t_ea994c7f): die EINE Transkriptblase eines
        Interviews -- ``web_post.typ = WEB_TYP_TRANSKRIPT``, danach nur noch
        ueber ``aendere_text`` weitergeschrieben (der ``typ`` bleibt)."""
        if transkript:
            typ = repo.WEB_TYP_TRANSKRIPT
        elif system:
            typ = repo.WEB_TYP_SYSTEM
        else:
            typ = repo.WEB_TYP_TEXT
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, typ, text=text,
        )
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_web_kanal_naht.py tests/test_web_kanal.py`
Expected: alle `passed` (die Naht-Tests insbesondere `test_signaturen_stimmen_mit_telegram_ueberein`).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/repo.py interview_theater/telegram.py interview_theater/web_kanal.py tests/test_interview_fliesstext.py
git commit -m "Add transkript flag to the channel send surface (web_post typ transkript)"
```

---

### Task 4: EINE Blase je Interview (Kern, noch ohne Sperre)

**Files:**
- Modify: `interview_theater/aufnahme.py` — Import-Zeile 66 (`workshop` ergaenzen); neue Konstante nach `_TEXT_TEIL_ECHO` (Zeile 167); neue Funktionen direkt vor `_teil_abschliessen` (~Zeile 1297); Verdrahtung in `_teil_abschliessen` (Zeilen 1346-1352)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["aufnahme"]`, nach `_TEXT_TEIL_ECHO`, Zeile 971)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Consumes: `workshop.interview_fliesstext()` (T1), `repo.echo_message_id`/`setze_echo_message_id` (T2), `tg.sende(..., transkript=True)` (T3).
- Produces: `aufnahme.fliesstext_aktiv(conn, chat_id: int) -> bool`; `aufnahme.transkript_blasentext(conn, kopf) -> str`; `aufnahme._sende_transkript_blase(conn, tg, e, chat_id: int, kopf_id: int) -> None`; `aufnahme._TEXT_TRANSKRIPT_KOPF`.

- [ ] **Step 1: Failing tests anhaengen**

```python
# -- Aufgabe 4: eine Blase je Interview --------------------------------------


def test_vier_teile_sind_genau_eine_transkriptblase(conn, web, einst, klm, fliesstext):
    _interview(conn, web, einst, klm, TEILE)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1, "eine Blase je Interview, nicht eine je Teil"
    text = blasen[0]["text"]
    assert text == "🎙 Interview 1\n\n" + "\n\n".join(TEILE)
    assert not re.search(r"\b(Teil|part)\b", text)
    assert not any(", Teil " in (p["text"] or "") for p in _posts(conn, repo.WEB_TYP_TEXT))


def test_die_blase_wird_einmal_mitgeschrieben(conn, web, einst, klm, fliesstext):
    """Entscheidung F: die nachricht-Zeile entsteht beim Anlegen, spaetere
    Aenderungen schreiben sie nicht nach (sie steht in keinem Fenster)."""
    kopf_id = _interview(conn, web, einst, klm, TEILE[:3])
    mitschrift = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND typ = 'transkript'"
    ).fetchall()
    assert len(mitschrift) == 1
    assert mitschrift[0]["text"] == "🎙 Interview 1\n\n" + TEILE[0]
    assert repo.echo_message_id(conn, kopf_id) == _posts(conn, repo.WEB_TYP_TRANSKRIPT)[0]["id"]


def test_ohne_schalter_bleibt_es_im_web_ein_echo_je_teil(conn, web, einst, klm):
    _interview(conn, web, einst, klm, TEILE[:2])

    assert _posts(conn, repo.WEB_TYP_TRANSKRIPT) == []
    echos = [p["text"] for p in _posts(conn, repo.WEB_TYP_TEXT) if ", Teil " in (p["text"] or "")]
    assert echos == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]


def test_telegram_bleibt_auch_mit_schalter_beim_echo_je_teil(conn, einst, klm, fliesstext):
    tg = TelegramAttrappe()  # hat kein aendere_text -- ein Aufruf waere ein Fehler
    _interview(conn, tg, einst, klm, TEILE[:2])

    assert [t for _, t, _ in tg.mit_knoepfen] == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]
    assert all(leiste for _, _, leiste in tg.mit_knoepfen), "die Leiste aus biete_nach_teil bleibt"
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k "blase or echo_je_teil"`
Expected: `test_vier_teile_…` und `test_die_blase_…` FAIL (`assert 0 == 1` — vier `text`-Echos statt einer Transkriptzeile); die beiden „bleibt"-Tests sind schon GRUEN (Regressionsanker, Entscheidung J).

- [ ] **Step 3: Implementieren**

Import (Zeile 66):

```python
from interview_theater import brainstorm, buehnenkarte, phasen, repo, sprache, stt, verdichter, workshop
```

Konstante nach `_TEXT_TEIL_ECHO`:

```python
#: Padua (04.10.2026, Karte t_ea994c7f, ``[interview] fliesstext``): die
#: erste Zeile der EINEN Transkriptblase eines Interviews im Web-Chat.
#: Darunter, je durch eine Leerzeile getrennt, alle Teil-Transkripte als
#: Fliesstext -- ohne "Teil K:" (``transkript_blasentext``).
_TEXT_TRANSKRIPT_KOPF = "🎙 {name}"
```

`sprachen/en/texte.toml`, unter `["aufnahme"]` nach `_TEXT_TEIL_ECHO`:

```toml
_TEXT_TRANSKRIPT_KOPF = "🎙 {name}"
```

Neue Funktionen direkt vor `_teil_abschliessen`:

```python
def fliesstext_aktiv(conn, chat_id: int) -> bool:
    """Gilt fuer diese Gruppe die EINE Transkriptblase je Interview samt der
    Systemzeilen rund ums Interview (Karte t_ea994c7f)? Nur mit
    ``[interview] fliesstext`` UND nur im Web-Kanal -- Telegram behaelt das
    Echo je Teil mit seiner Leiste, auch mit dem Schalter."""
    return workshop.interview_fliesstext() and ist_web_gruppe(conn, chat_id)


def transkript_blasentext(conn, kopf) -> str:
    """Der ganze Text der Transkriptblase, bei JEDEM Teil neu gebaut statt
    angehaengt (Entscheidung B): Kopfzeile, Leerzeile, alle Teile mit
    Transkript in Eingangsreihenfolge, je durch eine Leerzeile getrennt.

    Ausgewaehlt wird nach ``transkript``, nicht nach ``status``: der Teil,
    der gerade abgeschlossen wird, steht noch auf 'transkribiert'. Ein per
    ``an_den_bot`` abgezweigter Teil faellt heraus, weil
    ``repo.loese_aus_interview`` sein ``teil_von`` leert."""
    teile = [
        (teil["transkript"] or "").strip()
        for teil in repo.hole_teile(conn, kopf["id"])
        if (teil["transkript"] or "").strip()
    ]
    kopfzeile = T._TEXT_TRANSKRIPT_KOPF.format(name=anzeigename(conn, kopf, "Interview"))
    return "\n\n".join([kopfzeile, *teile])


def _sende_transkript_blase(conn, tg, e, chat_id: int, kopf_id: int) -> None:
    """Legt die EINE Transkriptblase eines Interviews an oder schreibt sie
    weiter (Karte t_ea994c7f).

    Gibt es noch keine (``aufnahme.echo_message_id`` leer), geht sie mit
    ``transkript=True`` raus, wird am Kopf gemerkt und -- wie jedes
    Teil-Echo -- einmal versteckt in ``nachricht`` mitgeschrieben.
    Spaetere Teile tauschen nur ihren Text (``tg.aendere_text``); die
    Mitschrift wird dabei NICHT nachgezogen: sie steht in keinem Fenster,
    die Wahrheit ist ``aufnahme.transkript`` (Entscheidung F).

    Ein Fehlschlag kostet nur die Anzeige, nie das Transkript."""
    kopf = repo.hole_aufnahme(conn, kopf_id)
    if kopf is None:
        return
    text = transkript_blasentext(conn, kopf)
    message_id = repo.echo_message_id(conn, kopf_id)
    if message_id is not None:
        try:
            tg.aendere_text(chat_id, message_id, text)
        except Exception:
            log.exception("Transkriptblase nicht aktualisiert, kopf_id=%s", kopf_id)
        return
    try:
        message_id = tg.sende(chat_id, text, transkript=True)
    except Exception:
        log.exception("Transkriptblase nicht gesendet, kopf_id=%s", kopf_id)
        return
    repo.setze_echo_message_id(conn, kopf_id, message_id)
    try:
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1,
            repo.TYP_TRANSKRIPT, text, repo._jetzt(), 1,
        )
    except Exception:
        log.exception("Transkriptblase mitzuschreiben fehlgeschlagen, chat_id=%s", chat_id)
```

In `_teil_abschliessen` die Zeilen 1346-1352 ersetzen durch:

```python
    if fliesstext_aktiv(conn, chat_id):
        # Padua (04.10.2026, Karte t_ea994c7f): EINE Blase je Interview, aus
        # allen Teilen mit Transkript neu gebaut -- ohne Leiste, die deckt
        # im Web der eigene Aufnahme-Regler ab.
        _sende_transkript_blase(conn, tg, e, chat_id, row["teil_von"])
    else:
        kopf = repo.hole_aufnahme(conn, row["teil_von"])
        text = T._TEXT_TEIL_ECHO.format(
            name=anzeigename(conn, kopf, "Interview") if kopf else "Interview",
            nummer=repo.teil_nummer(conn, row["id"]),
            transkript=row["transkript"],
        )
        _sende_teil_echo(conn, tg, e, chat_id, text)
```

Die folgenden Zeilen (`repo.setze_status(...)`, `_web_sprachblase(...)` —
Entscheidung G —, `_wende_aus_aufnahme_an`, die Race-Nachpruefung mit dem
frisch gelesenen `kopf`) bleiben **unveraendert**. Im Docstring von
`_teil_abschliessen` einen Satz ergaenzen: „Mit `fliesstext_aktiv` (Padua,
Web) geht statt des Echos je Teil die EINE Transkriptblase raus
(`_sende_transkript_blase`)."

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_aufnahme.py tests/test_sprache_texte.py`
Expected: alle `passed`.

- [ ] **Step 5: Mutationsprobe M1 (nicht committen)**

In `_sende_transkript_blase` die Zeile
`message_id = repo.echo_message_id(conn, kopf_id)` durch
`message_id = None` ersetzen.
Run: `$PY -m pytest -q tests/test_interview_fliesstext.py::test_vier_teile_sind_genau_eine_transkriptblase`
Expected: FAIL mit `assert 4 == 1` („eine Blase je Interview …").
Die Zeile **von Hand** zuruecksetzen (kein `git checkout` — die Datei
traegt die noch ungecommittete Aufgabe) und Step 4 wiederholen: wieder
alles `passed`.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/aufnahme.py interview_theater/sprachen/en/texte.toml tests/test_interview_fliesstext.py
git commit -m "Web interview transcript as one growing bubble (behind [interview] fliesstext)"
```

---

### Task 5: Sperre je Interview-Kopf (zwei Teile gleichzeitig → eine Blase)

**Files:**
- Modify: `interview_theater/aufnahme.py` (Register direkt vor `fliesstext_aktiv`; `_sende_transkript_blase` umschliessen)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Consumes: `_sende_transkript_blase` (T4).
- Produces: `aufnahme._blasen_sperre(kopf_id: int) -> threading.Lock`.

- [ ] **Step 1: Failing test anhaengen**

```python
# -- Aufgabe 5: Nebenlaeufigkeit ---------------------------------------------


class _LangsamerKanal(_Kanal):
    """Haelt ``sende`` 0,2 s auf -- genug, damit zwei Threads ohne Sperre
    beide "noch keine Blase" lesen und beide eine anlegen."""

    def sende(self, *args, **kw):
        time.sleep(0.2)
        return super().sende(*args, **kw)


def test_zwei_gleichzeitige_teile_ergeben_eine_blase(conn, einst, tmp_path, fliesstext):
    repo.setze_gruppe_kanal(conn, 1, "web")
    kanal = _LangsamerKanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)
    kopf_id = interview_an(conn)
    for i, text in enumerate(TEILE[:2]):
        aid = repo.lege_aufnahme_an(
            conn, 1, 700 + i, "teil", "sprache", dauer=5, teil_von=kopf_id,
            status="transkribiert",
        )
        repo.setze_transkript(conn, aid, text)

    start = threading.Barrier(2)

    def lauf():
        start.wait()
        aufnahme._sende_transkript_blase(conn, kanal, einst, 1, kopf_id)

    faeden = [threading.Thread(target=lauf) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(timeout=10)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1
    assert TEILE[0] in blasen[0]["text"] and TEILE[1] in blasen[0]["text"]
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py::test_zwei_gleichzeitige_teile_ergeben_eine_blase`
Expected: FAIL mit `assert 2 == 1`.

- [ ] **Step 3: Implementieren** — vor `fliesstext_aktiv`:

```python
#: Eine Sperre je Interview-Kopf fuer "Teile lesen + Blase anlegen oder
#: aendern + echo_message_id merken" (Karte t_ea994c7f, Entscheidung C).
#: Teile laufen im Pool (``bot.POOL_GROESSE``): ohne die Sperre laegen zwei
#: gleichzeitig fertige Teile beide "noch keine Blase" und legten zwei an,
#: oder der spaetere Text ueberschriebe den vollstaendigeren. Je Kopf statt
#: je Gruppe, wie die Register in ``ablauf``/``szene`` -- gemeinsam haette
#: es nichts zu schuetzen.
_blasen_sperren: dict[int, threading.Lock] = {}
_blasen_sperren_schutz = threading.Lock()


def _blasen_sperre(kopf_id: int) -> threading.Lock:
    """Liefert die (ggf. neu angelegte) Sperre fuer einen Interview-Kopf."""
    with _blasen_sperren_schutz:
        sperre = _blasen_sperren.get(kopf_id)
        if sperre is None:
            sperre = threading.Lock()
            _blasen_sperren[kopf_id] = sperre
        return sperre
```

`_sende_transkript_blase`: den Rumpf (ab `kopf = repo.hole_aufnahme(...)`)
in `with _blasen_sperre(kopf_id):` einruecken — Lesen von Teilen und
`echo_message_id`, Senden/Aendern und `setze_echo_message_id` liegen damit
alle unter der Sperre. Docstring-Satz: „Unter `_blasen_sperre(kopf_id)`."

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py`
Expected: alle `passed`.

- [ ] **Step 5: Mutationsprobe M2 (nicht committen)**

`with _blasen_sperre(kopf_id):` durch `with contextlib.nullcontext():`
ersetzen (`import contextlib` voruebergehend oben einfuegen).
Run: `$PY -m pytest -q tests/test_interview_fliesstext.py::test_zwei_gleichzeitige_teile_ergeben_eine_blase`
Expected: FAIL `assert 2 == 1`. Mutation von Hand zuruecknehmen, Step 4
erneut: `passed`.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/aufnahme.py tests/test_interview_fliesstext.py
git commit -m "Serialize the transcript bubble per interview head"
```

---

### Task 6: Ein abgezweigter Teil verschwindet aus der Blase

Grund: zwei Teile laufen parallel; Teil 3 baut die Blase neu, waehrend
Teil 2 noch beim Erkenner ist — Teil 2s Transkript steht schon in der
Datenbank und damit in der Blase. Erkennt der Erkenner danach `an_den_bot`,
loest `repo.loese_aus_interview` ihn aus dem Interview, aber die Blase
zeigte ihn bis zum naechsten Teil weiter. Deshalb nach dem Abzweigen ein
reines Neuschreiben (nie ein Anlegen).

**Files:**
- Modify: `interview_theater/aufnahme.py` (`_sende_transkript_blase` bekommt `nur_aendern`; `an_den_bot`-Zweig in `_teil_abschliessen`, Zeilen 1337-1344)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Produces: `aufnahme._sende_transkript_blase(conn, tg, e, chat_id: int, kopf_id: int, nur_aendern: bool = False) -> None`.

- [ ] **Step 1: Failing test anhaengen**

```python
# -- Aufgabe 6: an_den_bot ----------------------------------------------------


def test_ein_abgezweigter_teil_verschwindet_aus_der_blase(conn, web, einst, klm, fliesstext, monkeypatch):
    from interview_theater import erkenner

    kopf_id = interview_an(conn)
    erster = repo.lege_aufnahme_an(conn, 1, 710, "teil", "sprache", dauer=5,
                                   teil_von=kopf_id, status="fertig")
    repo.setze_transkript(conn, erster, TEILE[0])
    frage = repo.lege_aufnahme_an(conn, 1, 711, "teil", "sprache", dauer=5,
                                  teil_von=kopf_id, status="transkribiert")
    repo.setze_transkript(conn, frage, "Zeig mir die Verdichtungen.")
    # Ein paralleler Teil hat die Blase schon gebaut -- mit der Frage darin.
    aufnahme._sende_transkript_blase(conn, web, einst, 1, kopf_id)
    assert "Zeig mir" in _posts(conn, repo.WEB_TYP_TRANSKRIPT)[0]["text"]

    monkeypatch.setattr(
        erkenner, "erkenne_in_aufnahme",
        lambda *a, **k: [{"art": "an_den_bot", "wert": ""}],
    )
    aufnahme._teil_abschliessen(conn, web, klm, einst, repo.hole_aufnahme(conn, frage))

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1
    assert blasen[0]["text"] == "🎙 Interview 1\n\n" + TEILE[0]


def test_nur_aendern_legt_nie_eine_blase_an(conn, web, einst, fliesstext):
    kopf_id = interview_an(conn)
    aufnahme._sende_transkript_blase(conn, web, einst, 1, kopf_id, nur_aendern=True)
    assert _posts(conn, repo.WEB_TYP_TRANSKRIPT) == []
```

ANNAHME: `_an_den_bot_abzweigen` → `_kurz_abschliessen(..., zug=_kein_zug)`
laeuft mit `LLMAttrappe` ohne Ausnahme durch (der Erkenner ist per
`monkeypatch` ersetzt, `_wende_aus_aufnahme_an` faengt jeden Fehler,
`aufnahme.py:1439ff.`). Wirft `_kurz_abschliessen` hier doch, den Test mit
`zug=lambda *a, **k: None` als sechstes Argument an `_teil_abschliessen`
fahren und das vermerken.

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k "abgezweigt or nur_aendern"`
Expected: `test_ein_abgezweigter_…` FAIL (Text enthaelt noch „Zeig mir");
`test_nur_aendern_…` FAIL mit `TypeError: … unexpected keyword argument 'nur_aendern'`.

- [ ] **Step 3: Implementieren**

Signatur: `def _sende_transkript_blase(conn, tg, e, chat_id: int, kopf_id: int, nur_aendern: bool = False) -> None:`
und direkt nach dem `if message_id is not None: … return`-Block, noch unter
der Sperre:

```python
        if nur_aendern:
            return
```

Docstring-Satz: „`nur_aendern=True` schreibt nur eine schon vorhandene
Blase neu und legt nie eine an (Nachlauf nach `an_den_bot`)."

Im `an_den_bot`-Zweig von `_teil_abschliessen`:

```python
    if any(a.get("art") == "an_den_bot" for a in aenderungen):
        kopf_id = row["teil_von"]
        _an_den_bot_abzweigen(conn, tg, klm, e, row, zug, nachgeholt)
        # Karte t_ea994c7f: ein paralleler Teil kann die Blase schon MIT
        # diesem Transkript gebaut haben -- jetzt, wo es aus dem Interview
        # geloest ist, einmal ohne es neu schreiben. Nie neu anlegen.
        if kopf_id is not None and fliesstext_aktiv(conn, chat_id):
            _sende_transkript_blase(conn, tg, e, chat_id, kopf_id, nur_aendern=True)
        # (bestehender Kommentar und Aufruf bleiben)
        _wende_aus_aufnahme_an(conn, tg, klm, e, chat_id, row, aenderungen)
        return
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_aufnahme.py`
Expected: alle `passed`.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/aufnahme.py tests/test_interview_fliesstext.py
git commit -m "Rewrite the transcript bubble after an an_den_bot detach"
```

---

### Task 7: Abschlusszeile ueber die Sprachschicht (nicht hinter dem Schalter)

**Files:**
- Modify: `interview_theater/aufnahme.py` (drei Konstanten nach `_TEXT_AUSGEWERTET`, Zeile 191; `_text_interview_gespeichert_web`, Zeilen 1235-1243)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["aufnahme"]`, nach `_TEXT_AUSGEWERTET`)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Produces: `aufnahme._TEXT_GESPEICHERT_WEB`, `_TEXT_THEMEN_WEB`, `_TEXT_AUSWERTUNG_IM_TAB`.

- [ ] **Step 1: Failing test anhaengen**

```python
# -- Aufgabe 7: die Abschlusszeile spricht die Workshop-Sprache ----------------


def _verdichtetes_interview(conn):
    kopf_id = repo.lege_interview_an(conn, 1)
    teil = repo.lege_aufnahme_an(conn, 1, 720, "teil", "sprache", dauer=120,
                                 teil_von=kopf_id, status="fertig")
    repo.setze_transkript(conn, teil, "egal")
    vid = repo.speichere_verdichtung(conn, 1, kopf_id, "Zusammenfassung", [
        {"thema": "Ankommen", "kurz": "Ankommen", "beleg_zitat": "egal", "zitat_geprueft": 1},
    ])
    return repo.hole_aufnahme(conn, kopf_id), vid


def test_abschlusszeile_deutsch_ohne_profil(conn, einst):
    row, vid = _verdichtetes_interview(conn)
    zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    assert re.fullmatch(r"Interview 1 gespeichert · \d\d:\d\d Uhr · 2 Min", zeilen[0])
    assert zeilen[1:] == ["Themen: Ankommen", "Ganze Auswertung im Tab Arbeitsstand."]


def test_abschlusszeile_deutsch_in_dortmund(conn, einst, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        row, vid = _verdichtetes_interview(conn)
        zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    finally:
        workshop.vergiss()
        sprache.vergiss()
    assert re.fullmatch(r"Interview 1 gespeichert · \d\d:\d\d Uhr · 2 Min", zeilen[0])
    assert zeilen[1:] == ["Themen: Ankommen", "Ganze Auswertung im Tab Arbeitsstand."]


def test_abschlusszeile_englisch_in_padua(conn, einst, padua):
    row, vid = _verdichtetes_interview(conn)
    zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    assert re.fullmatch(r"Interview 1 saved · \d\d:\d\d · 2 min", zeilen[0])
    assert zeilen[1:] == ["Topics: Ankommen", "Full analysis in the Workbench tab."]
```

ANNAHME: `repo.themen_zu` liefert das Thema mit `zitat_geprueft = 1`
(gelesen wird `t["kurz"]`, `aufnahme.py:1236-1240`). Der englische
Tabname „Workbench" ist verifiziert: `texte.toml`
`["web_vereint"._TEXT_TAB] stand = "Workbench"` (Zeile 1887-1889).

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k abschlusszeile`
Expected: die beiden deutschen Tests `passed` (Regressionsanker), der
englische FAIL (`re.fullmatch(...)` ist `None` — die Zeile ist deutsch).

- [ ] **Step 3: Implementieren**

Konstanten nach `_TEXT_AUSGEWERTET`:

```python
#: Die Zeile nach einem Interview im Web-Kanal (02.10.2026), Bausteine fuer
#: ``_text_interview_gespeichert_web``. Bis 04.10.2026 standen sie als
#: Literale in der Funktion und gingen an der Sprachschicht vorbei -- Padua
#: (englisch) sah deutschen Text. Wortlaut unveraendert.
_TEXT_GESPEICHERT_WEB = "{name} gespeichert · {uhrzeit} Uhr · {minuten} Min"
_TEXT_THEMEN_WEB = "Themen: "
_TEXT_AUSWERTUNG_IM_TAB = "Ganze Auswertung im Tab Arbeitsstand."
```

`texte.toml`, `["aufnahme"]`, nach `_TEXT_AUSGEWERTET`:

```toml
_TEXT_GESPEICHERT_WEB = "{name} saved · {uhrzeit} · {minuten} min"
_TEXT_THEMEN_WEB = "Topics: "
_TEXT_AUSWERTUNG_IM_TAB = "Full analysis in the Workbench tab."
```

In `_text_interview_gespeichert_web`:

```python
    zeilen = [T._TEXT_GESPEICHERT_WEB.format(name=name, uhrzeit=uhrzeit, minuten=minuten)]
    themen = [
        (t["kurz"] or "").strip()
        for t in repo.themen_zu(conn, verdichtung_id)
        if (t["kurz"] or "").strip()
    ][:3]
    if themen:
        zeilen.append(T._TEXT_THEMEN_WEB + " · ".join(themen))
    zeilen.append(T._TEXT_AUSWERTUNG_IM_TAB)
    return "\n".join(zeilen)
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_aufnahme.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py`
Expected: alle `passed` (`test_normaler_abschluss_auf_web_sendet_die_neue_zeile` in `test_aufnahme.py` haelt den deutschen Wortlaut fest).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/aufnahme.py interview_theater/sprachen/en/texte.toml tests/test_interview_fliesstext.py
git commit -m "Route the web interview closing line through the language layer"
```

---

### Task 8: Abschlusszeile und „sehr kurz" als Systemzeilen

**Files:**
- Modify: `interview_theater/knoepfe/interviews.py:273-382` (`biete_nach_aufnahme`)
- Modify: `interview_theater/aufnahme.py` — `_sende_und_merke` (1201), `_sende_nach_interview` (1247), `_zu_kurz_gemeldet` (1522), `_interview_abschliessen` (1653)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Consumes: `aufnahme.fliesstext_aktiv` (T4).
- Produces: `knoepfe.biete_nach_aufnahme(conn, tg, chat_id, text, kopf_id, system: bool = False) -> int`; `aufnahme._sende_und_merke(conn, tg, e, chat_id, text, typ="text", system=False)`; `aufnahme._sende_nach_interview(conn, tg, e, chat_id, text, kopf_id, system=False)`.

- [ ] **Step 1: Failing tests anhaengen**

```python
# -- Aufgabe 8: Abschluss und "sehr kurz" als Systemzeilen ---------------------


def _texte(conn, typ):
    return [p["text"] or "" for p in _posts(conn, typ)]


def test_abschlusszeile_ist_im_web_mit_schalter_eine_systemzeile(conn, web, einst, klm, fliesstext):
    kopf_id = _interview(conn, web, einst, klm, [TEIL_A, TEIL_B])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any(t.startswith("Interview 1 gespeichert · ") for t in _texte(conn, repo.WEB_TYP_SYSTEM))
    assert not any("gespeichert · " in t for t in _texte(conn, repo.WEB_TYP_TEXT))


def test_zu_kurz_ist_im_web_mit_schalter_eine_systemzeile(conn, web, einst, klm, fliesstext):
    kopf_id = _interview(conn, web, einst, klm, ["nur ein kurzer Satz"])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_SYSTEM))
    assert not any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_TEXT))


def test_ohne_schalter_bleibt_zu_kurz_eine_textzeile(conn, web, einst, klm):
    kopf_id = _interview(conn, web, einst, klm, ["nur ein kurzer Satz"])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_TEXT))
    assert not any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_SYSTEM))
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k "systemzeile or textzeile"`
Expected: die beiden `…_eine_systemzeile`-Tests FAIL (Zeile steht unter `text`), `test_ohne_schalter_…` `passed`.

- [ ] **Step 3: Implementieren**

`knoepfe/interviews.py`, `biete_nach_aufnahme`:

```python
def biete_nach_aufnahme(conn, tg, chat_id: int, text: str, kopf_id: int | None,
                        system: bool = False) -> int:
```

Docstring-Satz am Ende: „`system=True` (Karte t_ea994c7f, nur mit
`aufnahme.fliesstext_aktiv`): die Zeile geht als Systemzeile raus, die
Leiste haengt unveraendert darunter." Alle drei `_sende_knoepfe(...)`-Aufrufe
der Funktion (Zeilen 374, 378, 382) bekommen `system=system` als letztes
Argument, z. B.:

```python
            return _sende_knoepfe(
                conn, tg, chat_id, text,
                [(T._TEXT_INTERVIEWS_FERTIG_KNOPF, _daten(knopf_id))],
                system=system,
            )
        return _sende_knoepfe(conn, tg, chat_id, text, [], system=system)
    ...
    return _sende_knoepfe(conn, tg, chat_id, text, knoepfe, system=system)
```

(`_sende_knoepfe(..., **kw)` reicht `system` an `tg.sende_mit_knoepfen`
weiter, `knoepfe/basis.py:151-160`; beide Kanaele und alle Attrappen
nehmen es.)

`aufnahme._sende_und_merke` — Signatur und Sendezeile:

```python
def _sende_und_merke(conn, tg, e, chat_id: int, text: str, typ: str = "text",
                     system: bool = False) -> None:
    ...
        message_id = tg.sende(chat_id, text, system=True) if system else tg.sende(chat_id, text)
```

(bedingt, damit jeder bestehende Aufruf **zeichengleich** `tg.sende(chat_id,
text)` bleibt — es gibt Test-Attrappen ohne `**kw`, z. B.
`tests/test_stt_sprache.py:62`). Docstring-Satz: „`system=True` nur aus
`_sende_nach_interview` (Karte t_ea994c7f)."

`aufnahme._sende_nach_interview`:

```python
def _sende_nach_interview(conn, tg, e, chat_id: int, text: str, kopf_id: int | None,
                          system: bool = False) -> None:
    ...
    try:
        message_id = knoepfe.biete_nach_aufnahme(conn, tg, chat_id, text, kopf_id, system=system)
    except Exception:
        log.exception("Knopfleiste nach Interview fehlgeschlagen, chat_id=%s", chat_id)
        _sende_und_merke(conn, tg, e, chat_id, text, system=system)
        return
```

`_zu_kurz_gemeldet`:

```python
    _sende_nach_interview(
        conn, tg, e, row["chat_id"],
        T._TEXT_ZU_KURZ.format(
            name=anzeigename(conn, row, T._TEXT_DAS_INTERVIEW),
            woerter=woerter,
        ),
        row["id"],
        system=fliesstext_aktiv(conn, row["chat_id"]),
    )
```

`_interview_abschliessen`, Zeile 1653:

```python
        _sende_nach_interview(
            conn, tg, e, chat_id, text, aufnahme_id,
            system=fliesstext_aktiv(conn, chat_id),
        )
```

Der Aufruf bei `_TEXT_LEER_VERWORFEN`/`_TEXT_OHNE_AUFNAHME` (Zeile 1745)
bleibt **unveraendert** (ausserhalb der Karte).

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_aufnahme.py tests/test_nach_interview.py tests/test_knoepfe.py`
Expected: alle `passed`.

- [ ] **Step 5: Mutationsprobe M3 (nicht committen)**

In `_sende_nach_interview` `system=system` im Aufruf von
`knoepfe.biete_nach_aufnahme` entfernen.
Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k systemzeile`
Expected: beide `…_eine_systemzeile`-Tests FAIL. Mutation zuruecknehmen,
Step 4 erneut: `passed`.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/knoepfe/interviews.py interview_theater/aufnahme.py tests/test_interview_fliesstext.py
git commit -m "Send interview closing and too-short lines as system lines on web (Padua)"
```

---

### Task 9: „Aufnahme beendet." als Systemzeile (Befehl, Umschalter, Erkenner)

**Files:**
- Modify: `interview_theater/knoepfe/interviews.py:51-79` (`biete_aufnahme`)
- Modify: `interview_theater/befehle.py:325-327` (`_befehl_aufnahme`) und `:366-376` (`_befehl_fertig`)
- Modify: `interview_theater/erkenner.py:2224-2262` (`_melde_interviewmodus`)
- Test: `tests/test_interview_fliesstext.py` (anhaengen)

**Interfaces:**
- Produces: `knoepfe.biete_aufnahme(conn, tg, chat_id, text, knopf=True, system=False) -> int`.

- [ ] **Step 1: Failing tests anhaengen**

```python
# -- Aufgabe 9: "Aufnahme beendet." als Systemzeile ---------------------------


def test_fertig_befehl_meldet_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/interview", "Ada")
    befehle.behandle(conn, web, einst, 1, "/fertig", "Ada")

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)
    assert "Aufnahme beendet." not in _texte(conn, repo.WEB_TYP_TEXT)


def test_aufnahme_umschalter_meldet_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/aufnahme", "Ada")
    befehle.behandle(conn, web, einst, 1, "/aufnahme", "Ada")

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)


def test_erkenner_meldet_das_ende_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import erkenner

    erkenner._melde_interviewmodus(web, conn, einst, 1, [{"art": "interview_beenden"}])

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)


def test_ohne_schalter_bleibt_aufnahme_beendet_text(conn, web, einst):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/interview", "Ada")
    befehle.behandle(conn, web, einst, 1, "/fertig", "Ada")

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_TEXT)
    assert "Aufnahme beendet." not in _texte(conn, repo.WEB_TYP_SYSTEM)
```

ANNAHME: `befehle.behandle(conn, tg, e, chat_id, text, absender)` ist die
Signatur (so in `tests/test_aufnahme.py::test_aufnahmestart_setzt_phase_3_mit_journalnotiz`);
`klm` ist optional, ohne `klm` startet `/fertig` keinen Abschluss-Thread.

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py -k "aufnahme_beendet or meldet"`
Expected: die drei `…systemzeile`-Tests FAIL, `test_ohne_schalter_…` `passed`.

- [ ] **Step 3: Implementieren**

`knoepfe/interviews.py`:

```python
def biete_aufnahme(conn, tg, chat_id: int, text: str, knopf: bool = True,
                   system: bool = False) -> int:
    """…(bestehend)…

    ``system=True`` (Karte t_ea994c7f, nur mit ``aufnahme.fliesstext_aktiv``):
    "Aufnahme beendet." geht als Systemzeile raus, der Umschalter haengt
    unveraendert darunter."""
    if not knopf:
        return tg.sende(chat_id, text, system=True) if system else tg.sende(chat_id, text)
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = T._TEXT_AUFNAHME_BEENDEN if laeuft else T._TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    return _sende_knoepfe(conn, tg, chat_id, text, [(beschriftung, _daten(knopf_id))], system=system)
```

`befehle._befehl_aufnahme` (Zeile 327):

```python
        knoepfe.biete_aufnahme(
            conn, tg, chat_id, T._TEXT_INTERVIEW_AUS,
            system=aufnahme.fliesstext_aktiv(conn, chat_id),
        )
```

`befehle._befehl_fertig` (Zeile 374):

```python
    if aufnahme.fliesstext_aktiv(conn, chat_id):
        # Karte t_ea994c7f: im Padua-Web eine Systemzeile, keine Sprechblase.
        tg.sende(chat_id, T._TEXT_INTERVIEW_AUS, system=True)
    else:
        tg.sende(chat_id, T._TEXT_INTERVIEW_AUS)
```

`erkenner._melde_interviewmodus`:

```python
    from interview_theater import aufnahme, knoepfe  # spaeter Import, haelt den Modulkopf frei
    ...
        try:
            system = art == "interview_beenden" and aufnahme.fliesstext_aktiv(conn, chat_id)
            message_id = knoepfe.biete_aufnahme(conn, tg, chat_id, text, system=system)
            repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_interview_fliesstext.py tests/test_befehle.py tests/test_erkenner.py tests/test_knoepfe.py`
Expected: alle `passed`.

- [ ] **Step 5: Mutationsprobe M4 (nicht committen)**

In `_befehl_fertig` den `if`-Zweig auf `tg.sende(chat_id, T._TEXT_INTERVIEW_AUS)`
(ohne `system=True`) setzen.
Run: `$PY -m pytest -q tests/test_interview_fliesstext.py::test_fertig_befehl_meldet_als_systemzeile`
Expected: FAIL. Zuruecknehmen, Step 4 erneut: `passed`.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/knoepfe/interviews.py interview_theater/befehle.py interview_theater/erkenner.py tests/test_interview_fliesstext.py
git commit -m "Send 'recording stopped' as a system line on web (Padua)"
```

---

### Task 10: Darstellung — Klasse `transkript` (Server, JS, CSS ×3)

**Files:**
- Modify: `interview_theater/web_chat.py` — `_CSS_CHAT` (nach `.blase.sprache`, Zeile 252), `klasseVon` (Zeile 766-771), `_blase_html` (neuer Zweig vor `elif n["typ"] == "system":`, Zeile 3265)
- Modify: `interview_theater/web_gestalt.py` — `_CHAT_A` (nach `.blase.sprache`, Zeile 973) und `_CHAT_B` (nach `.blase.sprache`, Zeile 1075)
- Test: `tests/test_web_chat_system_zeile.py` (anhaengen)

- [ ] **Step 1: Failing tests anhaengen** (`tests/test_web_chat_system_zeile.py`;
  die drei Imports gehoeren an den Dateikopf neben
  `from interview_theater import web_chat`, der Rest ans Dateiende):

```python
import re

import pytest

from interview_theater import web_gestalt

_KURSIV = re.compile(r"\.blase\.transkript\s*\{[^}]*font-style:\s*italic")


def test_eine_transkriptblase_bekommt_die_klasse_transkript():
    """Karte t_ea994c7f: die EINE Transkriptblase eines Interviews bleibt
    eine Bot-Blase, nur mit der Klasse ``transkript``."""
    html = web_chat._blase_html(
        _nachricht("transkript", text="🎙 Interview 1\n\nIch kam im Winter an.")
    )
    assert 'class="blase bot transkript"' in html
    assert "🎙 Interview 1<br><br>Ich kam im Winter an." in html
    assert 'style="' not in html


def test_die_js_kennt_die_transkriptblase():
    assert "n.typ === 'transkript'" in web_chat._js()


def test_das_chat_css_setzt_die_transkriptblase_kursiv():
    assert _KURSIV.search(web_chat._CSS_CHAT)


@pytest.mark.parametrize("entwurf", ["a", "b"])
def test_beide_entwuerfe_setzen_die_transkriptblase_kursiv(entwurf):
    css = web_gestalt.css_chat(entwurf)
    assert _KURSIV.search(css)
    regel = re.search(r"\.blase\.transkript\s*\{([^}]*)\}", css).group(1)
    assert "var(--text)" in regel, "Theme-Token, keine feste Farbe (KONTRAST text/grund-2)"
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_web_chat_system_zeile.py`
Expected: 5 neue Tests FAIL (Klasse `text` statt `transkript`; Muster nicht gefunden), die 3 alten `passed`.

- [ ] **Step 3: Implementieren**

`web_chat._CSS_CHAT`, nach `.blase.sprache { … }`:

```css
/* Karte t_ea994c7f: die EINE Transkriptblase eines Interviews -- kursiv
   wie eine Sprachnachricht, aber eine Bot-Blase (Rahmen, Seite). */
.blase.transkript { font-style: italic; }
```

`klasseVon`:

```javascript
  function klasseVon(n) {
    if (n.typ === 'sprache' || n.typ === 'datei' || n.typ === 'system' ||
        n.typ === 'transkript') {
      return n.typ;
    }
    return 'text';
  }
```

`_blase_html`, vor `elif n["typ"] == "system":`:

```python
    elif n["typ"] == "transkript":
        # Karte t_ea994c7f: die EINE Transkriptblase eines Interviews
        # (Padua, ``[interview] fliesstext``). Inhalt wie jede Bot-Zeile;
        # das Mikrofon steht im Text, kursiv macht das CSS.
        inhalt = sichere_html(n["text"])
        klasse = "transkript"
```

`web_gestalt._CHAT_A` und `_CHAT_B`, je direkt nach der Zeile
`.blase.sprache { color: var(--text); font-style: italic; }`:

```css
/* Karte t_ea994c7f: die Transkriptblase eines Interviews -- Bot-Blase
   (--grund-2), Text in --text: das Paar text/grund-2 steht in KONTRAST. */
.blase.transkript { color: var(--text); font-style: italic; }
```

- [ ] **Step 4: Gruen sehen**

Run: `$PY -m pytest -q tests/test_web_chat_system_zeile.py tests/test_web_gestalt_tokens.py tests/test_web_gestalt_einhang.py tests/test_web_chat_sprache.py`
Expected: alle `passed` (die bestehenden CSP-/Kontrast-Tests bleiben gruen).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_chat.py interview_theater/web_gestalt.py tests/test_web_chat_system_zeile.py
git commit -m "Render the transcript bubble italic in the web chat (both designs)"
```

---

### Task 11: Abnahme ueber HTTP — drei Segmente, eine Blase

**Files:**
- Test: `tests/test_web_e2e_http.py` (anhaengen; nutzt Fixture `lauf` und die Helfer `_post`, `_warte_auf`, `_lade_segment`, `_zustand`, Konstanten `CHAT`, `INTERVIEWTEXT`)

- [ ] **Step 1: Test anhaengen**

```python
def test_drei_segmente_ergeben_eine_transkriptblase(lauf, monkeypatch):
    """Karte t_ea994c7f, ueber den echten Weg (bot.schleife mit WebKanal,
    echter Webserver): mit ``[interview] fliesstext`` werden drei Segmente
    EINE Transkriptblase, und "Aufnahme beendet." ist eine Systemzeile."""
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)
    basis, token, pfad, klm = lauf
    _post(basis, token, "interview", {"an": True})
    _warte_auf(pfad, lambda c: repo.ist_interviewmodus_an(c, CHAT), "Modus an")

    for nummer in (1, 2, 3):
        _lade_segment(basis, token, nummer)

    def drei_teile_in_einer_blase(conn):
        zeilen = conn.execute(
            "SELECT text FROM web_post WHERE chat_id = ? AND typ = 'transkript'", (CHAT,)
        ).fetchall()
        return len(zeilen) == 1 and zeilen[0]["text"].count(INTERVIEWTEXT) == 3

    _warte_auf(pfad, drei_teile_in_einer_blase, "eine Blase mit drei Teilen")

    blasen = [n for n in _zustand(basis, token)["nachrichten"] if n["typ"] == "transkript"]
    assert len(blasen) == 1, "der Poll liefert genau eine Transkriptblase"
    assert blasen[0]["von"] == "bot"

    _post(basis, token, "interview", {"an": False})
    _warte_auf(
        pfad,
        lambda c: c.execute(
            "SELECT 1 FROM web_post WHERE chat_id = ? AND typ = 'system' "
            "AND text = 'Aufnahme beendet.'", (CHAT,),
        ).fetchone(),
        "Aufnahme beendet. als Systemzeile",
    )
    _warte_auf(pfad, lambda c: klm.verdichtet >= 1, "Verdichtung")
```

ANNAHME: der Poll (`chat/zustand`) liefert je Nachricht `typ` und `von`
(die Chatansicht liest beides: `klasseVon(n)`, `'blase ' + n.von`,
`web_chat.py:767,826`). Das Warten auf die Verdichtung am Ende sorgt dafuer,
dass der Abschluss-Thread vor dem Fixture-Ende durch ist (Muster
`test_fertig_direkt_hinter_zwei_segmenten_verliert_keines`).

- [ ] **Step 2: Laufen lassen** (die Implementierung steht seit Aufgabe 4–9;
  dieser Test ist die Abnahme, er muss ohne weitere Codeaenderung gruen sein)

Run: `$PY -m pytest -q tests/test_web_e2e_http.py`
Expected: alle `passed`.

- [ ] **Step 3: Gegenprobe (nicht committen)** — in
`aufnahme.fliesstext_aktiv` voruebergehend `return False` setzen.
Run: `$PY -m pytest -q tests/test_web_e2e_http.py::test_drei_segmente_ergeben_eine_transkriptblase`
Expected: FAIL `AssertionError: eine Blase mit drei Teilen trat nicht ein`.
Zuruecknehmen, Step 2 erneut: `passed`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_web_e2e_http.py
git commit -m "Add HTTP acceptance test: three segments, one transcript bubble"
```

---

### Task 12: Browser-Darstellung (Playwright, uebersprungen ohne Playwright)

**Files:**
- Test: `tests/e2e/test_web_chat_e2e.py` (anhaengen; nutzt `seite`, `DB_PFAD`, `CHAT`, `AUDIO`, `db`, `web_kanal`, `expect` aus der Datei)

- [ ] **Step 1: Test anhaengen**

```python
def test_transkriptblase_ist_kursiv_und_waechst_ohne_neuladen(seite):
    """Karte t_ea994c7f: die EINE Transkriptblase kommt als
    ``blase bot transkript`` an, ist kursiv und tauscht ihren Text per Poll."""
    conn = db.verbinde(DB_PFAD)
    try:
        kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
        mid = kanal.sende(CHAT, "🎙 Interview 1\n\nIch kam im Winter an.", transkript=True)
        blase = seite.locator(f'.blase[data-id="{mid}"]')
        expect(blase).to_have_class(re.compile(r"\bblase bot transkript\b"))
        assert blase.evaluate("b => getComputedStyle(b).fontStyle") == "italic"
        kanal.aendere_text(CHAT, mid, "🎙 Interview 1\n\nIch kam im Winter an.\n\nDer Bahnhof war leer.")
    finally:
        conn.close()
    expect(seite.locator(f'.blase[data-id="{mid}"]')).to_contain_text("Der Bahnhof war leer.")
```

ANNAHME: Playwright liegt im venv aus dem Dateikopf
(`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python`); aus der
Planungssitzung war das Verzeichnis nicht lesbar. `re` ist in der Datei
schon importiert (Zeile 33).

- [ ] **Step 2: Laufen lassen**

Run: `/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q tests/e2e/test_web_chat_e2e.py -k transkriptblase`
Expected: `1 passed`. Fehlt das venv/Playwright: mit `$PY -m pytest -q tests/e2e/test_web_chat_e2e.py` → `1 skipped` (importorskip) und das im Bericht der Karte so sagen.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_web_chat_e2e.py
git commit -m "Add browser check: transcript bubble italic, updated by poll"
```

---

### Task 13: AGENTS.md — ein Absatz unter „Der Web-Kanal"

**Files:**
- Modify: `AGENTS.md` — direkt nach dem Absatz, der mit `**Keine Nachzügler im Web** (Abschlussreview I4)` beginnt (~Zeile 2778).

- [ ] **Step 1: Absatz einfuegen**

```markdown
**Ein Interview ist im Web EINE Blase** (04.10.2026, Karte t_ea994c7f,
nur mit `[interview] fliesstext = true` — gesetzt allein in
`workshop/padua-2026/profil.toml`, Zugriff `workshop.interview_fliesstext()`).
Statt „Interview N, Teil K:" je Sprachnachricht schreibt jeder fertige Teil
dieselbe Blase weiter: `aufnahme._sende_transkript_blase` baut den Text
bei **jedem** Teil neu aus `repo.hole_teile` (Kopfzeile `🎙 Interview N`,
dann alle Teile mit Transkript, je durch eine Leerzeile), legt die Blase
beim ersten Teil mit `tg.sende(..., transkript=True)` an
(`web_post.typ = 'transkript'`, kursiv in der Chatansicht) und merkt ihre
id am Kopf (`aufnahme.echo_message_id`, ueberlebt einen Neustart); danach
nur noch `tg.aendere_text`. Eine Sperre je Kopf
(`aufnahme._blasen_sperre`) verhindert zwei Blasen, wenn zwei Teile im Pool
gleichzeitig fertig werden. In `nachricht` steht die Blase einmal, beim
Anlegen — spaetere Aenderungen ziehen dort nichts nach (die Wahrheit ist
`aufnahme.transkript`). Mit demselben Schalter gehen „Aufnahme beendet.",
die Abschlusszeile und „… war sehr kurz …" als Systemzeilen raus
(`system=True` an `knoepfe.biete_aufnahme`/`biete_nach_aufnahme`).
**Telegram bleibt beim Echo je Teil samt Leiste, auch mit Schalter**
(`aufnahme.fliesstext_aktiv` = Schalter **und** `ist_web_gruppe`). Nicht
gebaut: einen Teil loeschen und die Blase neu aufbauen (es gibt keinen
Loeschweg; der Neuaufbau aus `hole_teile` machte ihn spaeter einfach),
Telegram-Folgeblasen ueber 4096 Zeichen, eine „…"-Zeile waehrend der
Transkription. Unabhaengig vom Schalter laeuft die Abschlusszeile im Web
seither ueber die Sprachschicht (`_TEXT_GESPEICHERT_WEB` & Co.) — Padua
liest sie englisch, Deutsch ist zeichengleich.
```

- [ ] **Step 2: Pruefen**

Run: `grep -n "Ein Interview ist im Web EINE Blase" AGENTS.md`
Expected: genau eine Zeile.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "Document the single web interview transcript bubble in AGENTS.md"
```

---

### Task 14: Gesamtpruefung

**Files:** keine Aenderung (nur bei Befund: Fix in der Aufgabe, zu der er gehoert, eigener Commit).

- [ ] **Step 1: Bitgleichheit ausdruecklich**

Run: `$PY -m pytest -q tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py tests/test_sprache_texte.py tests/test_web_kanal_naht.py`
Expected: alle `passed`.

- [ ] **Step 2: Profile**

Run: `$PY -m scripts.pruefe_profil padua-2026; $PY -m scripts.pruefe_profil dortmund-2026; $PY -m scripts.pruefe_profil --vorgabe`
Expected: je eine Zeile `…: in Ordnung…`, jeder Exit-Code 0.

- [ ] **Step 3: Volle Suite, auf das Ende warten** (Architekt-Korrektur: ein Werkzeugaufruf im Vordergrund ist bei Claude Code wie bei Hermes auf 600 s begrenzt, die Suite brauchte zuletzt rund 300 s und waechst. Deshalb in eine Datei schreiben und auf das Ende warten, NICHT abbrechen und nicht ohne Ergebnis weitermachen: Claude Code `timeout: 600000`; reicht das nicht, `$PY -m pytest -q > .suite.log 2>&1; echo EXIT $?` im Hintergrund starten und das Ende abwarten, dann die Zusammenfassungszeile aus `.suite.log` zitieren. `.suite.log` nicht committen.)

Run: `$PY -m pytest -q > .suite.log 2>&1; echo EXIT $?`
Expected: `… passed …`, `0 failed`, keine Errors. Die Playwright-Dateien unter `tests/e2e/` erscheinen ohne Playwright als `skipped`.

- [ ] **Step 4: Nur Planumfang geaendert**

Run: `git diff --stat main...HEAD`
Expected: genau die Dateien aus der Dateikarte oben (plus diese Plandatei aus dem Planungscommit), nichts unter `korpus/`, `prompts/` oder `docs/prompt-audit/`.

---

## Mutationsproben (Uebersicht)

| Mutant | Aufgabe | Wird rot |
|---|---|---|
| M1: `message_id = None` statt `repo.echo_message_id(...)` in `_sende_transkript_blase` (neue Nachricht je Teil) | 4 | `test_vier_teile_sind_genau_eine_transkriptblase` (`assert 4 == 1`) |
| M2: `with contextlib.nullcontext():` statt `with _blasen_sperre(kopf_id):` | 5 | `test_zwei_gleichzeitige_teile_ergeben_eine_blase` (`assert 2 == 1`) |
| M3: `system=system` beim Aufruf von `biete_nach_aufnahme` weggelassen | 8 | `test_abschlusszeile_ist_im_web_mit_schalter_eine_systemzeile`, `test_zu_kurz_ist_im_web_mit_schalter_eine_systemzeile` |
| M4: `_befehl_fertig` ohne `system=True` | 9 | `test_fertig_befehl_meldet_als_systemzeile` |
| Gegenprobe: `fliesstext_aktiv` liefert immer False | 11 | `test_drei_segmente_ergeben_eine_transkriptblase` |

Jede Mutation wird von Hand eingesetzt, rot gesehen und von Hand
zurueckgenommen — **nie committet**, und nie per `git checkout` auf eine
Datei mit ungecommitteter Aufgabe zurueckgesetzt.

## Selbstpruefung des Plans

- Spezifikation MUST 1 → Aufgabe 1 (+ `pruefe_profil` in 1 und 14). MUST 2 →
  4, 5, 6. MUST 3 → 4 (Mikrofon im Text), 10 (Klasse, kursiv, Tokens).
  MUST 4 → 7 (Englisch), 8, 9 (Systemzeilen). MUST 5 → 4
  (`test_telegram_bleibt_auch_mit_schalter_beim_echo_je_teil`).
- Abnahmetests der Karte: 4 Teile/1 Blase + Mutant (4/M1), zwei Threads (5),
  Telegram mit Schalter (4), Schalter aus im Web (4), Abschlusszeile EN/DE
  exakt (7), Systemzeilen + Mutant + Schalter-aus (8, 9), Darstellung
  Server/JS/CSS beide Entwuerfe/kein `style="` (10), HTTP-e2e (11),
  Playwright (12), Gesamtsuite + Bitgleichheit + Profile (14), AGENTS.md (13).
- Signaturen ueber die Aufgaben hinweg: `fliesstext_aktiv(conn, chat_id)`,
  `_sende_transkript_blase(conn, tg, e, chat_id, kopf_id, nur_aendern=False)`,
  `repo.echo_message_id`/`setze_echo_message_id`,
  `biete_nach_aufnahme(..., kopf_id, system=False)`,
  `biete_aufnahme(..., knopf=True, system=False)` — einheitlich verwendet.

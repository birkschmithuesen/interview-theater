# Padua Workbench read-only — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Plan-Karte t_59001131, Ausführung auf Karte t_49e7354c, Branch `wt/t_49e7354c`, **in diesem Worktree**.

**Goal:** Der Arbeitsstand-Tab („Workbench") der vereinten Gruppenseite wird in Padua eine reine Statusansicht — EINE Achse, Phasen 1–7 in Reihenfolge, je Phase eine aufklappbare Zeile mit Zähler, darunter ihre Attribute mit Statuspunkt; Änderungen gehen nur über den Chat. Dortmund (Vorgabeprofil und `dortmund-2026`) bleibt byte-gleich.

**Architecture:** Ein Profilschalter `[web] workbench_bearbeitbar` (Vorgabe `true`, Padua `false`). Die Statusdaten kommen aus EINER reinen Funktion `roadmap.werkbank(lage, aktuelle_phase)` (erweitert `roadmap.py`, keine neue Regelwelt), geladen read-only über `web_daten.werkbank`. `web.gruppe_koerper` verzweigt beim Schalter `false` auf `web.werkbank_koerper`; `web_vereint.seite` hängt dann weder `_BEARBEITEN_JS` noch ein Nonce-Feld ins Stand-Panel (der Nonce wandert ins Chat-Panel), dafür `web_gestalt.css_werkbank()`. Der Werkbank-POST (`web._beantworte_post`, leerer Unterpfad) antwortet 403; die Chat-POSTs bleiben.

**Tech Stack:** Python 3.11, nur Standardbibliothek im Webdienst (`http.server`, `sqlite3`), pytest, Playwright (nur `tests/e2e`, eigenes venv).

## Global Constraints

Bindende Entscheidungen von Birk / aus der Karte — **nicht neu verhandeln**:

- **D1 Profilschalter:** `[web] workbench_bearbeitbar` im Workshop-Profil, Vorgabe in `workshop.VORGABE_WERTE["web"]` = `true`; `workshop/dortmund-2026/profil.toml` bekommt KEINE Zeile (fehlt → Vorgabe `true`); `workshop/padua-2026/profil.toml` = `false`. Mit `true` rendert alles **byte-gleich** wie heute — bewiesen durch Vergleichsdateien, die in Aufgabe 1 mit dem unveränderten Code erzeugt werden (Muster: `tests/test_web_dashboard_en.py`).
- **D2 Read-only in Padua:** im Workbench-Panel kein `<select>`, `<textarea>`, `<input>`, `<button>`, `contenteditable`, kein Löschknopf, kein `_BEARBEITEN_JS` auf der Seite. Der Werkbank-POST (`POST /g/<token>`, dispatcht an `web_schreiben.wende_an`) antwortet **403**, wenn `workbench_bearbeitbar` falsch ist. **Nur dieser Weg** — `chat/senden`, `chat/knopf`, `chat/audio`, `chat/interview`, `chat/phase` funktionieren weiter (Test). `web_schreiben.py` bleibt unverändert. Oben **einmal** ein ruhiger Hinweis, EN: „To change something, just tell the bot in the chat." (über `sprache.T` / `sprachen/en/texte.toml`, Tabelle `["web"]`).
- **D3 Eine Datenquelle = `roadmap.py`, erweitert.** `AUFGABEN` (Namen + Reihenfolge, per Test an `phasentexte.PARAMETER` genagelt) wird **nicht** angefasst. Neu: reine Funktion `roadmap.werkbank(lage, aktuelle_phase)` auf demselben `lage`-Dict; sie ist auch die Quelle für das Stepper-Bottom-Sheet der Parallelkarte t_cc4306db (Rückgabeform siehe unten). `fehlstellen.py` bleibt, wie es ist (`/stand`, Dortmund-Seite); in der Padua-Werkbank entfällt sein Abschnitt — die offenen Punkte SIND die Liste.
- **D4 Drei Zustände je Attribut, mechanisch:** `erledigt` (roadmap-`zustand == erledigt` bzw. Detail-Prädikat wahr) · `offen` (nicht erledigt UND Phasennummer ≤ aktuelle Phase) · `spaeter` (nicht erledigt UND Phasennummer > aktuelle Phase). Roadmap-`laeuft` erscheint als `offen` plus das Wort „running" (keine eigene Farbe). Phasenzeile: Zähler „4 of 5" in `var(--text-leise)` plus ✓, wenn alle Attribute erledigt sind. Aktuelle Phase `<details open>`, alle anderen zu; erledigte bleiben aufklappbar.
- **D5 Attribute je Phase** ([R] = Roadmap-`AUFGABEN`, [D] = neue Detailzeile, berechnet in `roadmap.py` aus `lage`):
  1 Terms: [R] begriffe (Begriffe anzeigen); [D] „Discussion summarised" aus `diskussion_verdichtung` (nur wenn `[diskussion] aktiv`). HOOK `arbeitsstand.begriffe_detail` (Spalte gibt es NOCH NICHT, Karte t_4517d4ad; JSON-Liste `[{begriff, begruendung, zitat, doppelbedeutung}]`): defensiv lesen, je Begriff Begründung/Doppelbedeutung zeigen; fehlt die Spalte → nichts.
  2 Questions: [R] fragen, einleitungen, eroeffnung, abschluss; dazu die vorhandene A/B-Zeile über `_fragen_auswertung_html` (keine zweite Berechnung).
  3 Interviews: [R] interviews, auswertungen; [D] je Interview eine Zeile (aufgenommen; ausgewertet ja/nein); darunter Zusammenfassung + Kernthemen genau wie heute (`_interview_html`) — kein Transkript, kein Zitat ohne `zitat_geprueft = 1`.
  4 Frame: [R] setting, figuren, geschichte, szenenfolge; Inhalt: Setting, Geschichte, Kernthema/Hauptkonflikt wenn gesetzt (`_altbestand_html`/`NUR_ANZEIGE`), Figuren als Name + eine Zeile (`vorspann.erster_satz`), Szenenköpfe, „Also agreed" = Festlegungen + Stückkarte in EINER read-only Liste.
  5 Prose Draft: [R] zuordnungen; [D] je Szene „prose ja/nein". Nur Kopf + Status, KEINE Volltexte.
  6 Rewrite: [R] szenentexte; [D] Gesamt-Rückmeldung (`arbeitsstand.gesamttext_fixiert_am`), je Szene überarbeitet (`szene.ueberarbeitung_bestaetigt_am`); der heutige Dramaturgie-Abschnitt hängt hier.
  7 Stage Version: [R] stueckpruefung; [D] Form je Szene (`szene.form`), Sprechweise je Figur (`figur.sprachstil`); die heutigen Sprechanteile hängen hier.
  Unten, zugeklappt, kleiner: Journal „How we got here".
  ENTFÄLLT in Padua: Phasenanzeige im Arbeitsstand, Probenansicht-Link, Chat-Link, eigenständiges „What's still missing", eigenständige Stückkarte / Other agreements / Dramaturgie / Sprechanteile / From the interviews, Szenen-Volltexte.
  SPÄTER (nicht in diesem Plan): der Inhalt von `begriffe_detail` selbst (t_4517d4ad) — nur der Haken.
- **D6 Statuspunkte, kein Emoji** („Dezenter, aber trotzdem klar"): kleine CSS-Punkte aus den Theme-Variablen von `web_gestalt.py`, beide Entwürfe (`TOKENS["a"]`, `["b"]`): erledigt = gefüllter Punkt `var(--signal)` + kleiner Haken; offen = hohler Ring `var(--warn)`, normaler Text; später = gestrichelter Ring `var(--text-leise)`, gedämpfter Text. Form unterscheidet sich, nicht nur die Farbe; `aria-label` „done"/„open"/„later". Paare in `web_gestalt.KONTRAST` eintragen, damit `tests/test_web_gestalt_tokens.py` ≥ 3:1 (WCAG 1.4.11) für beide Entwürfe rechnet. Aufklappen über natives `<details>/<summary>`, kein JS.
- CSS-Regeln aus AGENTS.md „Die Gestaltung": kein `style="…"`, kein `on…=`, kein Webfont/`@import`/`@font-face`, `@keyframes`/`@media` nur in `css_rahmen()`; Panel-CSS läuft durch `web_vereint.scope_css`.
- Code-Bezeichner deutsch wie im Repo; Kommentar-Dichte wie im umgebenden Code. Nur erfundenes Material in Tests/Screenshots, nie `betrieb/`.
- Branch `wt/t_49e7354c`, **kein Merge nach main, kein Push**. Ein Commit je Aufgabe, nur die genannten Dateien `git add`-en (nie `git add -A`; `.superpowers-brief-*.md` und `.cc-*` bleiben ungetrackt). Commit-Nachrichten enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testbefehle immer abwarten (nicht in den Hintergrund schicken).

**Abkürzungen in diesem Plan:**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python   # Playwright-venv (tests/e2e/README.md)
```

Suite: `$PY -m pytest -q -x --ignore=tests/e2e`. Profilprüfung: `$PY -m scripts.pruefe_profil padua-2026`, `$PY -m scripts.pruefe_profil dortmund-2026`, `$PY -m scripts.pruefe_profil --vorgabe` (CLI verifiziert in `scripts/pruefe_profil.py:389-407`; Rückgabe 0 = „<name>: in Ordnung").

### Rückgabeform von `roadmap.werkbank` (Vertrag für t_cc4306db)

```python
roadmap.werkbank(lage: dict, aktuelle_phase: int) -> list[dict]   # genau 7 Einträge, Reihenfolge phasen.PHASEN
{
  "nummer": int,            # 1..7
  "name": str,              # phasen.PHASEN-Kurzname (Profil-Sprache)
  "bezeichnung": str,       # phasen.bezeichnung(nummer)
  "aktiv": bool,            # nummer == aktuelle_phase
  "erledigt": int,          # Anzahl Zeilen mit status == "erledigt"
  "gesamt": int,            # Anzahl Zeilen (Aufgaben + Details)
  "fertig": bool,           # gesamt > 0 and erledigt == gesamt
  "zeilen": [{
      "kennung": str,       # Aufgaben: roadmap.AUFGABEN-Kennung; Details: "diskussion" | "interview" |
                            #   "prosa" | "gesamttext" | "ueberarbeitet" | "form" | "sprechweise"
      "art": "aufgabe" | "detail",
      "text": str | None,   # nur Aufgaben: phasentexte.beschriftung(parameter); Details: None (web.py beschriftet)
      "bezug": str | int | None,   # Interview-Bezeichnung, Szenennummer oder Figurenname
      "titel": str | None,  # Szenentitel bei Szenen-Details
      "status": "erledigt" | "offen" | "spaeter",   # roadmap.ERLEDIGT / OFFEN / SPAETER
      "laeuft": bool,       # nur Aufgaben mit roadmap-zustand "laeuft" (dann status == "offen")
  }],
}
```

`lage` ist das Dict von `roadmap.aus_daten` (Schlüssel siehe dessen Docstring) plus optional: `stand["gesamttext_fixiert_am"]`, `stand["begriffe_detail"]`, je Szene `ueberarbeitung_bestaetigt_am`/`form`/`titel`/`nummer`/`prosa`, je Figur `name`/`sprachstil`, je Interview `bezeichnung`, und `diskussion` (`True`/`False`, oder `None` = Zeile entfällt). Fehlende Schlüssel gelten als „nicht erledigt" bzw. „keine Zeile". Für das Web liefert `web_daten.werkbank(conn, chat_id)` → `{"phasen": <obige Liste>, "begriffe_detail": list[dict], "szenen_anzahl": str | None}`.

### Dateien

| Datei | Änderung |
|---|---|
| `interview_theater/workshop.py` | Vorgabe `web.workbench_bearbeitbar = True`, Funktion `workbench_bearbeitbar()` |
| `workshop/padua-2026/profil.toml` | `[web] workbench_bearbeitbar = false` |
| `interview_theater/roadmap.py` | `ERLEDIGT/OFFEN/SPAETER`, `status()`, `werkbank()`, `begriffe_detail()` |
| `interview_theater/web_daten.py` | `_roadmap_lage()` herausgelöst, `werkbank()`, Schlüssel `werkbank` in `gruppe_nach_token` |
| `interview_theater/web_gestalt.py` | `_WERKBANK`-CSS, `css_werkbank()`, Kontrastpaare |
| `interview_theater/web.py` | Texte, `_journal_html`, `werkbank_koerper` + Helfer, Weiche in `gruppe_koerper`/`gruppe_html`, 403 in `_beantworte_post` |
| `interview_theater/web_vereint.py` | Schalter in `seite()`: `bearbeitbar`, Nonce im Chat, `css_werkbank` |
| `interview_theater/sprachen/en/texte.toml` | englische Texte (`["web"]`) |
| `tests/test_werkbank_bitgleich.py` + `tests/fixtures/werkbank_vorher_*.html` | Byte-Gleichheit Dortmund |
| `tests/test_werkbank_schalter.py`, `tests/test_roadmap_werkbank.py`, `tests/test_web_daten_werkbank.py`, `tests/test_werkbank_gestalt.py`, `tests/test_werkbank_web.py`, `tests/test_werkbank_vereint.py`, `tests/test_werkbank_post.py` | neue Tests |
| `tests/test_sprache_texte.py` | `BLEIBT_DEUTSCH["web_gestalt._WERKBANK"]` |
| `tests/test_web_sprache.py` | ein Padua-Test erzwingt den Schalter `true` |
| `tests/e2e/test_web_werkbank_e2e.py` (neu), `tests/e2e/test_web_uebersicht_e2e.py` | Browser + Screenshots, ein Padua-Test umgeschrieben |
| `docs/ux-padua/workbench/*.png` | Screenshots (nur mit `IT_SCHUSS_AKTUALISIEREN=1`) |
| `AGENTS.md` | Doku |

---

### Task 1: Dortmund-Ausgabe als Vergleichsdateien festhalten (vor jeder Änderung)

**Files:**
- Create: `tests/test_werkbank_bitgleich.py`
- Create: `tests/fixtures/werkbank_vorher_{gruppe,koerper,vereint}_{vorgabe,dortmund-2026}.html` (6 Dateien, generiert)

**Interfaces:**
- Consumes: nichts Neues (nur bestehender Code).
- Produces: `tests/test_werkbank_bitgleich.py::seiten(tmp_path) -> dict[str, str]` und die sechs Vergleichsdateien; alle späteren Aufgaben müssen diesen Test grün halten.

- [ ] **Step 1: Baseline der Suite festhalten** (damit später klar ist, was schon vorher rot war)

Run: `$PY -m pytest -q --ignore=tests/e2e > /tmp/werkbank-baseline.log 2>&1; tail -5 /tmp/werkbank-baseline.log` (timeout 600000 ms)
Expected: Summenzeile `N passed …`. Steht dort `failed`, die Testnamen notieren — sie sind vorbestehend und nicht Teil dieser Karte.

- [ ] **Step 2: Test schreiben**

```python
"""Die Werkbank (Arbeitsstand-Tab) bleibt ohne Profilschalter byte-gleich.

Die Vergleichsdateien ``tests/fixtures/werkbank_vorher_*.html`` sind mit dem
Code VOR dem Umbau zur read-only Werkbank erzeugt (Plan
``docs/superpowers/plans/2026-10-03-padua-workbench-readonly.md``,
Aufgabe 1) -- ohne Profil und mit ``IT_WORKSHOP=dortmund-2026``. Sie sind die
Beweisgrundlage dafuer, dass Dortmund kein Zeichen anders sieht
(dasselbe Muster wie ``tests/test_web_dashboard_en.py``).

Neu geschrieben werden sie NUR mit ``IT_WERKBANK_VORHER_SCHREIBEN=1`` -- und
nur auf einem Stand, von dem man weiss, dass er Dortmund nicht veraendert.

Zeitstempel und Token sind festgenagelt (``_fest``): die Gruppe kommt aus
``tests/fixture_sprache.py`` und damit aus ``repo``-Funktionen, die "jetzt"
stempeln. Nur erfundenes Material.
"""

import os
import pathlib
import re
import sqlite3

import pytest

from interview_theater import db, repo, sprache, web, web_chat, web_daten, web_vereint, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SEITEN = ("gruppe", "koerper", "vereint")
TOKEN = "tok-werkbank"
NONCE = "nonce-werkbank"
FEST = "2026-10-03T10:00:00+00:00"
_ISO = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")
SCHREIBEN = os.environ.get("IT_WERKBANK_VORHER_SCHREIBEN") == "1"


def _datei(name: str, profil: str | None) -> pathlib.Path:
    return FIXTURES / f"werkbank_vorher_{name}_{profil or 'vorgabe'}.html"


def _fest(wert):
    """Jeder ISO-Zeitstempel wird FEST, ``sqlite3.Row`` wird ein Dict."""
    if isinstance(wert, sqlite3.Row):
        return {k: _fest(wert[k]) for k in wert.keys()}
    if isinstance(wert, dict):
        return {k: _fest(v) for k, v in wert.items()}
    if isinstance(wert, list):
        return [_fest(v) for v in wert]
    if isinstance(wert, tuple):
        return tuple(_fest(v) for v in wert)
    if isinstance(wert, str) and _ISO.match(wert):
        return FEST
    return wert


def _profil(monkeypatch, name: str | None) -> None:
    monkeypatch.delenv("IT_UX_ENTWURF", raising=False)
    if name is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


def seiten(tmp_path) -> dict[str, str]:
    """Die drei Ausgaben, die der Schalter ``[web] workbench_bearbeitbar``
    nicht beruehren darf: die Einzelseite mit Formularen, der Rumpf ohne
    Nonce (Leseansicht) und die vereinte Seite mit Chat."""
    pfad = str(tmp_path / "werkbank.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    echtes_token = baue_volle_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, echtes_token)
        chat = web_daten.web_chatzustand(lesend, echtes_token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    daten = _fest(daten)
    daten["web_token"] = TOKEN
    chat = _fest(chat)
    for nachricht in chat["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return {
        "gruppe": web.gruppe_html(daten, NONCE, TOKEN),
        "koerper": web.gruppe_koerper(daten, None, TOKEN),
        "vereint": web_vereint.seite(
            daten, chat, _fest(roadmapdaten), NONCE, TOKEN, "/theatersoap", 45000),
    }


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_ohne_schalter_bleibt_die_werkbank_byte_gleich(tmp_path, monkeypatch, profil):
    _profil(monkeypatch, profil)
    erzeugt = seiten(tmp_path)
    for name in SEITEN:
        datei = _datei(name, profil)
        if SCHREIBEN:
            datei.write_text(erzeugt[name], encoding="utf-8")
        assert erzeugt[name] == datei.read_text(encoding="utf-8"), name


def test_die_vergleichsdateien_tragen_die_formulare():
    """Gegenprobe: eine leere oder schon umgebaute Vergleichsdatei bewiese
    nichts. Vorher stehen Formulare, Nonce und Speicher-Skript drin."""
    gruppe = _datei("gruppe", None).read_text(encoding="utf-8")
    vereint = _datei("vereint", None).read_text(encoding="utf-8")
    assert "<textarea" in gruppe
    assert 'id="nonce"' in gruppe
    assert web._BEARBEITEN_JS in vereint
```

- [ ] **Step 3: Vergleichsdateien mit dem UNVERÄNDERTEN Code erzeugen**

Run: `IT_WERKBANK_VORHER_SCHREIBEN=1 $PY -m pytest -q tests/test_werkbank_bitgleich.py`
Expected: `3 passed`; `ls tests/fixtures/werkbank_vorher_*` zeigt 6 Dateien.

- [ ] **Step 4: Determinismus prüfen (zweimal ohne Schreiben)**

Run: `$PY -m pytest -q tests/test_werkbank_bitgleich.py && $PY -m pytest -q tests/test_werkbank_bitgleich.py`
Expected: beide Male `3 passed`. ANNAHME: außer ISO-Zeitstempeln und Token ist die Ausgabe deterministisch. Schlägt der zweite Lauf fehl, `diff` zwischen Datei und Ausgabe ansehen und die abweichende Stelle in `_fest` (oder als feste Zuweisung nach `_fest`) festnageln, dann Step 3 wiederholen. Sind `vorgabe`- und `dortmund-2026`-Dateien identisch (`cmp`), ist das erwartet, aber nicht verlangt.

- [ ] **Step 5: Commit**

```bash
git add tests/test_werkbank_bitgleich.py tests/fixtures/werkbank_vorher_*.html
git commit -m "Werkbank: Dortmund-Ausgabe als Vergleichsdateien festhalten

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Profilschalter `[web] workbench_bearbeitbar`

**Files:**
- Modify: `interview_theater/workshop.py` (`VORGABE_WERTE["web"]` ~Zeile 228-238; neue Funktion nach `fragen_ab_aktiv` ~Zeile 955-963)
- Modify: `workshop/padua-2026/profil.toml` (Abschnitt `[web]`, ~Zeile 155-163)
- Test: `tests/test_werkbank_schalter.py`

**Interfaces:**
- Produces: `workshop.workbench_bearbeitbar(profil: Profil | None = None) -> bool` — liest `web.workbench_bearbeitbar`, Vorgabe `True`. Alle späteren Aufgaben rufen sie als `workshop.workbench_bearbeitbar()` über einen **lokalen** Import (`from interview_theater import workshop`), damit Tests sie per `monkeypatch.setattr(workshop, "workbench_bearbeitbar", ...)` ersetzen können.

- [ ] **Step 1: Failing test**

```python
"""Der Profilschalter der read-only Werkbank (Padua, 03.10.2026)."""

import pytest

from interview_theater import sprache, workshop


@pytest.fixture
def profil(monkeypatch):
    def setze(name):
        if name is None:
            monkeypatch.delenv(workshop.VARIABLE, raising=False)
        else:
            monkeypatch.setenv(workshop.VARIABLE, name)
        workshop.vergiss()
        sprache.vergiss()
    yield setze
    workshop.vergiss()
    sprache.vergiss()


def test_die_vorgabe_traegt_den_schluessel():
    assert workshop.VORGABE_WERTE["web"]["workbench_bearbeitbar"] is True


@pytest.mark.parametrize("name, erwartet", [
    (None, True), ("dortmund-2026", True), ("padua-2026", False),
])
def test_der_schalter_je_profil(profil, name, erwartet):
    profil(name)
    assert workshop.workbench_bearbeitbar() is erwartet
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_schalter.py`
Expected: FAIL (`KeyError: 'workbench_bearbeitbar'` bzw. `AttributeError: … has no attribute 'workbench_bearbeitbar'`).

- [ ] **Step 3: Implementieren**

In `interview_theater/workshop.py`, im Kommentar über `"web": {` den Satz anhängen und den Schlüssel ergänzen:

```python
    # ``workbench_bearbeitbar`` (Padua, 03.10.2026): der Arbeitsstand-Tab
    # ("Workbench") mit Formularen. ``false`` macht ihn zur reinen
    # Statusansicht (``web.werkbank_koerper``), Aenderungen gehen dann nur
    # ueber den Chat, und der Werkbank-POST antwortet 403. An ist die Zusage
    # an Dortmund: Seite und Endpunkt bleiben byte-gleich.
    "web": {
        "dashboard_log_einklappen": False,
        "dashboard_gestaltet": False,
        "workbench_bearbeitbar": True,
    },
```

Nach `fragen_ab_aktiv`:

```python
def workbench_bearbeitbar(profil: Profil | None = None) -> bool:
    """Ob der Arbeitsstand-Tab ("Workbench") Formulare traegt und der
    Werkbank-POST schreibt (Padua, 03.10.2026, Karte t_49e7354c).

    Vorgabe true -- Dortmund setzt die Zeile nicht und bleibt byte-gleich.
    Padua setzt false: dort ist die Werkbank reine Anzeige, geaendert wird
    im Chat (Birk: "Workbench reiner Status-Ausspieler")."""
    profil = profil or aktiv()
    return bool(profil.wert("web.workbench_bearbeitbar", True))
```

In `workshop/padua-2026/profil.toml` unter `dashboard_gestaltet = true`:

```toml
# Die read-only Werkbank (03.10.2026): der Arbeitsstand-Tab zeigt nur noch
# den Stand je Phase mit Statuspunkten; geaendert wird im Chat. Ohne diese
# Zeile (Dortmund) bleiben Formulare und Schreibweg wie gehabt.
workbench_bearbeitbar = false
```

- [ ] **Step 4: Grün + Profile**

Run: `$PY -m pytest -q tests/test_werkbank_schalter.py tests/test_werkbank_bitgleich.py tests/test_workshop.py tests/profile tests/test_profil_bitgleich.py && $PY -m scripts.pruefe_profil padua-2026 && $PY -m scripts.pruefe_profil dortmund-2026 && $PY -m scripts.pruefe_profil --vorgabe`
Expected: alle Tests PASS; drei Zeilen `…: in Ordnung` (ggf. mit Hinweisen, keine `FEHLER`). ANNAHME: `workshop.lade` und `pruefe_profil` lehnen unbekannte Schlüssel nicht ab — da der Schlüssel jetzt in `VORGABE_WERTE` steht, ist er ohnehin bekannt.

**Mutationsprobe:** `workbench_bearbeitbar = true` in Padua → `test_der_schalter_je_profil[padua-2026-False]` wird rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/workshop.py workshop/padua-2026/profil.toml tests/test_werkbank_schalter.py
git commit -m "Workshop-Profil: Schalter [web] workbench_bearbeitbar (Padua false)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `roadmap.werkbank` — drei Zustände und Detailzeilen

**Files:**
- Modify: `interview_theater/roadmap.py` (Import `json`; Neues nach `aus_daten`, vor `register`)
- Test: `tests/test_roadmap_werkbank.py`

**Interfaces:**
- Consumes: `roadmap.AUFGABEN`, `roadmap._zustand`, `roadmap._text`, `phasen.PHASEN`, `phasen.bezeichnung`, `phasentexte.beschriftung`.
- Produces: `roadmap.ERLEDIGT = "erledigt"`, `roadmap.OFFEN = "offen"`, `roadmap.SPAETER = "spaeter"`; `roadmap.status(erledigt: bool, nummer: int, aktuelle_phase: int) -> str`; `roadmap.werkbank(lage: dict, aktuelle_phase: int) -> list[dict]` (Form siehe Kopf); `roadmap.begriffe_detail(stand) -> list[dict]` mit Schlüsseln `begriff`, `begruendung`, `doppelbedeutung` (das `zitat` geht bewusst NICHT mit).

**Wichtig:** `tests/test_roadmap.py::test_kein_sql_und_kein_repo_in_roadmap` verbietet die Wörter `SELECT`, `INSERT`, `UPDATE`, `DELETE` irgendwo in `roadmap.py` — auch in Docstrings und Kommentaren.

- [ ] **Step 1: Failing tests**

```python
"""Die Werkbank-Sicht der Roadmap (Padua, 03.10.2026): je Phase ihre
Attribute mit drei Zustaenden -- erledigt, offen, spaeter.

Dieselbe ``lage`` wie ``roadmap.aus_daten``; keine zweite Wunschliste: die
Aufgabenzeilen SIND ``roadmap.AUFGABEN``, die Detailzeilen lesen nur, was in
``lage`` steht."""

import json

import pytest

from interview_theater import phasen, roadmap


def _lage(**abweichung) -> dict:
    grund = {
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 1,
        "interviewmodus": False, "tippt": False, "strom": None,
    }
    grund.update(abweichung)
    return grund


def _phase(liste, nummer):
    return next(p for p in liste if p["nummer"] == nummer)


def _zeile(liste, nummer, kennung, bezug=None):
    for z in _phase(liste, nummer)["zeilen"]:
        if z["kennung"] == kennung and (bezug is None or z["bezug"] == bezug):
            return z
    raise AssertionError(f"{nummer}/{kennung}/{bezug} nicht gefunden")


# -- Grundform ---------------------------------------------------------------


def test_sieben_phasen_in_reihenfolge():
    assert [p["nummer"] for p in roadmap.werkbank(_lage(), 1)] == \
        [n for n, _, _ in phasen.PHASEN]


def test_die_aufgabenzeilen_sind_die_aufgaben_der_roadmap():
    """Keine zweite Liste: Kennung und Text kommen aus ``aus_daten``."""
    werkbank = roadmap.werkbank(_lage(), 1)
    for p in roadmap.aus_daten(_lage()):
        aufgaben = [z for z in _phase(werkbank, p["nummer"])["zeilen"]
                    if z["art"] == "aufgabe"]
        assert [(z["kennung"], z["text"]) for z in aufgaben] == \
            [(a["kennung"], a["text"]) for a in p["aufgaben"]]


def test_nur_die_aktuelle_phase_ist_aktiv():
    assert [p["nummer"] for p in roadmap.werkbank(_lage(phase=5), 5) if p["aktiv"]] == [5]


# -- die drei Zustaende ------------------------------------------------------


def test_erledigt():
    liste = roadmap.werkbank(_lage(stand={"begriffe": "Heimat, Arbeit"}), 1)
    assert _zeile(liste, 1, "begriffe")["status"] == roadmap.ERLEDIGT


def test_offen_in_der_aktuellen_und_in_frueheren_phasen():
    liste = roadmap.werkbank(_lage(phase=3), 3)
    assert _zeile(liste, 2, "fragen")["status"] == roadmap.OFFEN
    assert _zeile(liste, 3, "interviews")["status"] == roadmap.OFFEN


def test_nach_der_aktuellen_phase_ist_nichts_offen_sondern_spaeter():
    """Mutationsprobe: wer den Zweig ``nummer > aktuelle_phase`` entfernt,
    macht diesen Test rot."""
    liste = roadmap.werkbank(_lage(phase=3), 3)
    for p in liste:
        if p["nummer"] > 3:
            assert {z["status"] for z in p["zeilen"]} == {roadmap.SPAETER}, p["nummer"]


def test_erledigt_gilt_auch_in_einer_spaeteren_phase():
    liste = roadmap.werkbank(_lage(stand={"rahmen": "Bahnhof, nachts"}), 1)
    assert _zeile(liste, 4, "setting")["status"] == roadmap.ERLEDIGT


def test_laeuft_ist_offen_mit_vermerk():
    liste = roadmap.werkbank(_lage(phase=3, interviewmodus=True), 3)
    zeile = _zeile(liste, 3, "interviews")
    assert zeile["status"] == roadmap.OFFEN
    assert zeile["laeuft"] is True
    assert _zeile(liste, 2, "fragen")["laeuft"] is False


def test_zaehler_und_fertig():
    liste = roadmap.werkbank(_lage(phase=2, stand={"begriffe": "x"}), 2)
    eins, zwei = _phase(liste, 1), _phase(liste, 2)
    assert (eins["erledigt"], eins["gesamt"], eins["fertig"]) == (1, 1, True)
    assert (zwei["erledigt"], zwei["gesamt"], zwei["fertig"]) == (0, 4, False)


# -- Detailzeilen ------------------------------------------------------------


def test_ohne_diskussionsangabe_keine_zeile():
    zeilen = _phase(roadmap.werkbank(_lage(), 1), 1)["zeilen"]
    assert [z["kennung"] for z in zeilen] == ["begriffe"]


@pytest.mark.parametrize("da, erwartet", [(True, "erledigt"), (False, "offen")])
def test_diskussion(da, erwartet):
    liste = roadmap.werkbank(_lage(diskussion=da), 1)
    zeile = _zeile(liste, 1, "diskussion")
    assert (zeile["art"], zeile["status"]) == ("detail", erwartet)


def test_je_interview_eine_zeile():
    lage = _lage(phase=3, interviews=[
        {"bezeichnung": "Interview 1", "zusammenfassung": "Sie erzaehlt."},
        {"bezeichnung": "Interview 2", "zusammenfassung": None},
    ])
    liste = roadmap.werkbank(lage, 3)
    assert _zeile(liste, 3, "interview", "Interview 1")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 3, "interview", "Interview 2")["status"] == roadmap.OFFEN


def test_phase_5_je_szene_prosa():
    lage = _lage(phase=5, szenen=[
        {"nummer": 1, "titel": "Ankunft", "prosa": "Sie kommt an."},
        {"nummer": 2, "titel": "Abschied", "prosa": None},
    ])
    liste = roadmap.werkbank(lage, 5)
    eins = _zeile(liste, 5, "prosa", 1)
    assert (eins["status"], eins["titel"]) == (roadmap.ERLEDIGT, "Ankunft")
    assert _zeile(liste, 5, "prosa", 2)["status"] == roadmap.OFFEN


def test_phase_6_gesamttext_und_ueberarbeitung():
    lage = _lage(phase=6, stand={"gesamttext_fixiert_am": "2026-10-03T10:00:00+00:00"},
                 szenen=[{"nummer": 1, "ueberarbeitung_bestaetigt_am": "2026-10-03T10:00:00+00:00"},
                         {"nummer": 2}])
    liste = roadmap.werkbank(lage, 6)
    assert _zeile(liste, 6, "gesamttext")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 6, "ueberarbeitet", 1)["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 6, "ueberarbeitet", 2)["status"] == roadmap.OFFEN


def test_phase_7_form_und_sprechweise():
    lage = _lage(phase=7,
                 szenen=[{"nummer": 1, "form": "dialog"}, {"nummer": 2, "form": None}],
                 figuren=[{"name": "Nadia", "sprachstil": "Knapp: Ja."}, {"name": "Tomas"}])
    liste = roadmap.werkbank(lage, 7)
    assert _zeile(liste, 7, "form", 1)["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 7, "form", 2)["status"] == roadmap.OFFEN
    assert _zeile(liste, 7, "sprechweise", "Nadia")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 7, "sprechweise", "Tomas")["status"] == roadmap.OFFEN


# -- der Haken fuer begriffe_detail (Karte t_4517d4ad) ------------------------


@pytest.mark.parametrize("stand", [None, {}, {"begriffe_detail": None},
                                   {"begriffe_detail": "{kaputt"},
                                   {"begriffe_detail": '{"a": 1}'}])
def test_begriffe_detail_fehlt_oder_kaputt(stand):
    assert roadmap.begriffe_detail(stand) == []


def test_begriffe_detail_liest_die_liste_ohne_zitat():
    roh = json.dumps([
        {"begriff": "Heimat", "begruendung": "kam dreimal", "zitat": "z",
         "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": ""},
        "quatsch",
    ])
    assert roadmap.begriffe_detail({"begriffe_detail": roh}) == [
        {"begriff": "Heimat", "begruendung": "kam dreimal",
         "doppelbedeutung": "Ort und Gefuehl"},
    ]
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_roadmap_werkbank.py`
Expected: FAIL mit `AttributeError: module 'interview_theater.roadmap' has no attribute 'werkbank'` (bzw. `ERLEDIGT`).

- [ ] **Step 3: Implementieren**

Oben in `interview_theater/roadmap.py` `import json` vor `from collections.abc import Callable`. Nach `aus_daten` (vor `def register`):

```python
# --- Die Werkbank (Padua, 03.10.2026) ---------------------------------------
#
# Der Arbeitsstand-Tab in Padua ist eine reine Statusansicht: je Phase ihre
# Attribute mit einem von drei Zustaenden. Dieselbe ``lage`` wie
# ``aus_daten``, dieselben ``AUFGABEN`` -- dazu Detailzeilen, die nur lesen,
# was in ``lage`` steht. Die Beschriftung der Details macht ``web.py``; hier
# stehen nur Kennungen. Auch das Stepper-Bottom-Sheet (Karte t_cc4306db)
# liest diese Funktion.

ERLEDIGT = "erledigt"
OFFEN = "offen"
SPAETER = "spaeter"


def status(erledigt: bool, nummer: int, aktuelle_phase: int) -> str:
    """Erledigt, sonst offen bis zur aktuellen Phase, danach spaeter.

    Eine noch nicht erreichte Phase hat nichts "Offenes" -- dort steht
    niemand im Verzug (Birk: dezent, aber klar)."""
    if erledigt:
        return ERLEDIGT
    return OFFEN if nummer <= aktuelle_phase else SPAETER


def _roh(quelle, name: str):
    """Ein Feld als Rohwert -- ``None``, wenn es fehlt (Dict, Row, ``None``)."""
    if quelle is None:
        return None
    try:
        return quelle[name]
    except (IndexError, KeyError, TypeError):
        return None


def _szenenzeilen(kennung: str, szenen, feld: str) -> list[tuple]:
    return [
        (kennung, bool(_text(s, feld)), _roh(s, "nummer"), _text(s, "titel") or None)
        for s in szenen
    ]


def _details(nummer: int, lage: dict) -> list[tuple]:
    """Die Detailzeilen einer Phase als ``(kennung, erledigt, bezug, titel)``."""
    stand = lage["stand"]
    if nummer == 1:
        diskussion = lage.get("diskussion")
        return [] if diskussion is None else [("diskussion", bool(diskussion), None, None)]
    if nummer == 3:
        return [
            ("interview", bool(_roh(i, "zusammenfassung")), _roh(i, "bezeichnung"), None)
            for i in lage["interviews"]
        ]
    if nummer == 5:
        return _szenenzeilen("prosa", lage["szenen"], "prosa")
    if nummer == 6:
        return (
            [("gesamttext", bool(_text(stand, "gesamttext_fixiert_am")), None, None)]
            + _szenenzeilen("ueberarbeitet", lage["szenen"], "ueberarbeitung_bestaetigt_am")
        )
    if nummer == 7:
        return _szenenzeilen("form", lage["szenen"], "form") + [
            ("sprechweise", bool(_text(f, "sprachstil")), _text(f, "name") or None, None)
            for f in lage["figuren"]
        ]
    return []


def werkbank(lage: dict, aktuelle_phase: int) -> list[dict]:
    """Die sieben Phasen mit ihren Attributen und je einem Zustand -- rein.

    Rueckgabeform siehe ``docs/superpowers/plans/2026-10-03-padua-workbench-
    readonly.md`` (Kopf): je Phase ``nummer``, ``name``, ``bezeichnung``,
    ``aktiv``, ``erledigt``, ``gesamt``, ``fertig`` und ``zeilen``; je Zeile
    ``kennung``, ``art`` ("aufgabe"/"detail"), ``text``, ``bezug``, ``titel``,
    ``status`` und ``laeuft``. 'laeuft' ist ein Vermerk an einer offenen
    Aufgabe, kein vierter Zustand."""
    ergebnis = []
    for nummer, name, _satz in phasen.PHASEN:
        zeilen = []
        for aufgabe in AUFGABEN.get(nummer, ()):
            stand = status(aufgabe.erledigt(lage), nummer, aktuelle_phase)
            zeilen.append({
                "kennung": aufgabe.kennung, "art": "aufgabe",
                "text": phasentexte.beschriftung(aufgabe.parameter),
                "bezug": None, "titel": None, "status": stand,
                "laeuft": stand != ERLEDIGT and _zustand(aufgabe, lage) == "laeuft",
            })
        for kennung, erledigt, bezug, titel in _details(nummer, lage):
            zeilen.append({
                "kennung": kennung, "art": "detail", "text": None,
                "bezug": bezug, "titel": titel,
                "status": status(erledigt, nummer, aktuelle_phase), "laeuft": False,
            })
        erledigt = sum(1 for z in zeilen if z["status"] == ERLEDIGT)
        ergebnis.append({
            "nummer": nummer,
            "name": name,
            "bezeichnung": phasen.bezeichnung(nummer),
            "aktiv": nummer == aktuelle_phase,
            "erledigt": erledigt,
            "gesamt": len(zeilen),
            "fertig": bool(zeilen) and erledigt == len(zeilen),
            "zeilen": zeilen,
        })
    return ergebnis


def begriffe_detail(stand) -> list[dict]:
    """Der Haken fuer ``arbeitsstand.begriffe_detail`` (Karte t_4517d4ad):
    eine JSON-Liste ``[{begriff, begruendung, zitat, doppelbedeutung}]``.

    Defensiv: fehlt die Spalte, ist sie leer oder kaputt, kommt eine leere
    Liste -- nie ein Fehler (der Webserver migriert nichts). Das ``zitat``
    geht bewusst NICHT mit: es hat keine ``zitat_geprueft``-Pruefung, und auf
    der Seite steht kein ungeprueftes Zitat (AGENTS.md, "Drei Grenzen")."""
    roh = _text(stand, "begriffe_detail")
    if not roh:
        return []
    try:
        eintraege = json.loads(roh)
    except (ValueError, TypeError):
        return []
    if not isinstance(eintraege, list):
        return []
    ergebnis = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        begriff = str(eintrag.get("begriff") or "").strip()
        if not begriff:
            continue
        ergebnis.append({
            "begriff": begriff,
            "begruendung": str(eintrag.get("begruendung") or "").strip(),
            "doppelbedeutung": str(eintrag.get("doppelbedeutung") or "").strip(),
        })
    return ergebnis
```

- [ ] **Step 4: Grün**

Run: `$PY -m pytest -q tests/test_roadmap_werkbank.py tests/test_roadmap.py`
Expected: PASS (inkl. `test_kein_sql_und_kein_repo_in_roadmap`).

**Mutationsprobe:** in `status()` `return OFFEN if nummer <= aktuelle_phase else SPAETER` durch `return OFFEN` ersetzen → `test_nach_der_aktuellen_phase_ist_nichts_offen_sondern_spaeter` rot. Zurücknehmen.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/roadmap.py tests/test_roadmap_werkbank.py
git commit -m "Roadmap: Werkbank-Sicht mit drei Zustaenden und Detailzeilen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `web_daten.werkbank` — read-only laden

**Files:**
- Modify: `interview_theater/web_daten.py` (`roadmap()` ~Zeile 1886-1926 zerlegen; neue Funktionen danach; `gruppe_nach_token` ~Zeile 1270-1332 um einen Schlüssel erweitern)
- Test: `tests/test_web_daten_werkbank.py`

**Interfaces:**
- Consumes: `roadmap.werkbank`, `roadmap.begriffe_detail` (Task 3), `workshop.workbench_bearbeitbar` (Task 2), `workshop.diskussion_aktiv`.
- Produces: `web_daten._roadmap_lage(conn, chat_id) -> dict`; `web_daten.werkbank(conn, chat_id) -> {"phasen": list[dict], "begriffe_detail": list[dict], "szenen_anzahl": str | None}`; `gruppe_nach_token(...)["werkbank"]` = dieses Dict, wenn `workbench_bearbeitbar()` falsch ist, sonst `None`.

- [ ] **Step 1: Failing tests**

```python
"""Die Werkbank aus der read-only Verbindung (Padua, 03.10.2026)."""

import json

import pytest

from interview_theater import db, repo, sprache, web_daten, workshop

CHAT = 7_000_000_000_001


@pytest.fixture
def profil(monkeypatch):
    def setze(name):
        if name is None:
            monkeypatch.delenv(workshop.VARIABLE, raising=False)
        else:
            monkeypatch.setenv(workshop.VARIABLE, name)
        workshop.vergiss()
        sprache.vergiss()
    yield setze
    workshop.vergiss()
    sprache.vergiss()


def _db(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    conn.commit()
    return pfad, conn


def _werkbank(pfad):
    lesend = web_daten.oeffne_lesend(pfad)   # mode=ro: jeder Schreibversuch wirft
    try:
        return web_daten.werkbank(lesend, CHAT)
    finally:
        lesend.close()


def _zeile(werkbank, nummer, kennung, bezug=None):
    phase = next(p for p in werkbank["phasen"] if p["nummer"] == nummer)
    for z in phase["zeilen"]:
        if z["kennung"] == kennung and (bezug is None or z["bezug"] == bezug):
            return z
    raise AssertionError(f"{nummer}/{kennung}/{bezug} nicht gefunden")


def test_liest_ueber_die_read_only_verbindung(tmp_path, profil):
    profil("padua-2026")
    pfad, _ = _db(tmp_path)
    ergebnis = _werkbank(pfad)
    assert [p["nummer"] for p in ergebnis["phasen"]] == [1, 2, 3, 4, 5, 6, 7]
    assert ergebnis["begriffe_detail"] == []
    assert ergebnis["szenen_anzahl"] is None


def test_die_roadmap_bleibt_dieselbe(tmp_path, profil):
    """Herausloesen von ``_roadmap_lage`` darf ``roadmap()`` nicht aendern."""
    profil(None)
    pfad, conn = _db(tmp_path)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        from interview_theater import roadmap
        assert web_daten.roadmap(lesend, CHAT) == roadmap.aus_daten(
            web_daten._roadmap_lage(lesend, CHAT))
    finally:
        lesend.close()


def test_diskussion_nur_mit_profilschalter(tmp_path, profil):
    pfad, conn = _db(tmp_path)
    profil(None)
    assert all(z["kennung"] != "diskussion" for z in _werkbank(pfad)["phasen"][0]["zeilen"])
    profil("padua-2026")
    assert _zeile(_werkbank(pfad), 1, "diskussion")["status"] == "offen"
    repo.merke_diskussion_verdichtung(conn, CHAT, "Sie redeten ueber Heimat.", None)
    conn.commit()
    assert _zeile(_werkbank(pfad), 1, "diskussion")["status"] == "erledigt"


def test_ueberarbeitung_gesamttext_form_und_sprechweise(tmp_path, profil):
    profil("padua-2026")
    pfad, conn = _db(tmp_path)
    repo.setze_phase(conn, CHAT, 7)
    eins = repo.lege_szene_an(conn, CHAT, 1, "Ankunft", None, "A: Hallo.")
    repo.lege_szene_an(conn, CHAT, 2, "Abschied", None, "A: Tschuess.")
    repo.setze_szene_ueberarbeitung_bestaetigt(conn, eins)
    repo.setze_szenenfeld(conn, eins, "form", "dialog")
    repo.setze_arbeitsstand(conn, CHAT, "gesamttext_fixiert_am", "2026-10-03T10:00:00+00:00")
    repo.setze_figur(conn, CHAT, "Nadia", "die Aeltere")
    repo.setze_figur(conn, CHAT, "Tomas", "der Juengere")
    nadia = next(f for f in repo.figuren(conn, CHAT) if f["name"] == "Nadia")
    repo.setze_figur_sprachstil(conn, nadia["id"], "Knapp: Ja. Nein.")
    conn.commit()
    w = _werkbank(pfad)
    assert _zeile(w, 6, "gesamttext")["status"] == "erledigt"
    assert _zeile(w, 6, "ueberarbeitet", 1)["status"] == "erledigt"
    assert _zeile(w, 6, "ueberarbeitet", 2)["status"] == "offen"
    assert _zeile(w, 7, "form", 1)["status"] == "erledigt"
    assert _zeile(w, 7, "form", 2)["status"] == "offen"
    assert _zeile(w, 7, "sprechweise", "Nadia")["status"] == "erledigt"
    assert _zeile(w, 7, "sprechweise", "Tomas")["status"] == "offen"


def test_begriffe_detail_mit_spalte(tmp_path, profil):
    """Simuliert Karte t_4517d4ad: die Spalte wird hier von Hand angelegt."""
    profil("padua-2026")
    pfad, conn = _db(tmp_path)
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    if "begriffe_detail" not in spalten:
        conn.execute("ALTER TABLE arbeitsstand ADD COLUMN begriffe_detail TEXT")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    conn.execute(
        "UPDATE arbeitsstand SET begriffe_detail = ? WHERE chat_id = ?",
        (json.dumps([{"begriff": "Heimat", "begruendung": "kam dreimal",
                      "zitat": "z", "doppelbedeutung": "Ort und Gefuehl"}]), CHAT),
    )
    conn.commit()
    assert _werkbank(pfad)["begriffe_detail"] == [
        {"begriff": "Heimat", "begruendung": "kam dreimal", "doppelbedeutung": "Ort und Gefuehl"},
    ]


def test_gruppe_nach_token_traegt_die_werkbank_nur_ohne_bearbeitung(tmp_path, profil):
    pfad, conn = _db(tmp_path)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    for name, erwartet_liste in ((None, False), ("padua-2026", True)):
        profil(name)
        lesend = web_daten.oeffne_lesend(pfad)
        try:
            daten = web_daten.gruppe_nach_token(lesend, token)
        finally:
            lesend.close()
        if erwartet_liste:
            assert isinstance(daten["werkbank"]["phasen"], list)
        else:
            assert daten["werkbank"] is None
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_web_daten_werkbank.py`
Expected: FAIL (`AttributeError: … has no attribute 'werkbank'` / `_roadmap_lage`).

- [ ] **Step 3: Implementieren**

In `interview_theater/web_daten.py` den Rumpf von `roadmap()` in eine neue Funktion verschieben — **das Dict-Literal samt Kommentaren wortgleich**:

```python
def _roadmap_lage(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die ``lage`` der Roadmap aus der read-only Verbindung -- herausgeloest
    (Werkbank, 03.10.2026), damit ``roadmap`` und ``werkbank`` dieselben
    Daten lesen."""
    from interview_theater import phasen

    stand = _arbeitsstand(conn, chat_id)
    gruppe = conn.execute(
        "SELECT interviewmodus_seit, web_tippt_bis FROM gruppe WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    interviews = _interviews(conn, chat_id)
    return {
        # ... das bisherige Dict aus roadmap() unveraendert, mit allen Kommentaren ...
    }


def roadmap(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """(bisheriger Docstring unveraendert)"""
    from interview_theater import roadmap as modul

    return modul.aus_daten(_roadmap_lage(conn, chat_id))
```

Danach neu:

```python
# --- Die Werkbank (Padua, 03.10.2026) ---------------------------------------

#: Arbeitsstandfelder, die nur die Werkbank braucht -- ueber ``_feld``, weil
#: der Webserver read-only liest und eine Spalte noch fehlen kann
#: (``begriffe_detail`` kommt erst mit Karte t_4517d4ad).
_WERKBANK_STANDFELDER = (
    "gesamttext_fixiert_am", "sprechweisen_fixiert_am", "szenen_anzahl", "begriffe_detail",
)


def _werkbank_stand(conn: sqlite3.Connection, chat_id: int) -> dict:
    zeile = conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return {feld: _feld(zeile, feld) for feld in _WERKBANK_STANDFELDER}


def _diskussion_verdichtet(conn: sqlite3.Connection, chat_id: int) -> bool:
    try:
        return conn.execute(
            "SELECT 1 FROM diskussion_verdichtung WHERE chat_id = ?", (chat_id,)
        ).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def _spalte_je_id(conn: sqlite3.Connection, tabelle: str, spalte: str,
                  chat_id: int) -> dict:
    """``{id: wert}`` einer Spalte -- leer, wenn sie (noch) fehlt. ``tabelle``
    und ``spalte`` kommen nur aus dem Code, nie von aussen."""
    try:
        zeilen = conn.execute(
            f"SELECT id, {spalte} FROM {tabelle} WHERE chat_id = ? AND {_NICHT_ENTFERNT}",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {z["id"]: z[spalte] for z in zeilen}


def werkbank(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die read-only Werkbank (``roadmap.werkbank``) -- dieselbe ``lage`` wie
    ``roadmap``, ergaenzt um das, was nur die Detailzeilen brauchen. Kein
    Schreibvorgang, kein Modellaufruf."""
    from interview_theater import roadmap as modul, workshop

    lage = _roadmap_lage(conn, chat_id)
    zusatz = _werkbank_stand(conn, chat_id)
    lage["stand"] = {**lage["stand"], **zusatz}
    abnahme = _spalte_je_id(conn, "szene", "ueberarbeitung_bestaetigt_am", chat_id)
    lage["szenen"] = [
        {**s, "ueberarbeitung_bestaetigt_am": abnahme.get(s["id"])} for s in lage["szenen"]
    ]
    stil = _spalte_je_id(conn, "figur", "sprachstil", chat_id)
    lage["figuren"] = [{**f, "sprachstil": stil.get(f["id"])} for f in lage["figuren"]]
    # Die Diskussionszeile gibt es nur, wo Phase 1 mitschneidet -- sonst
    # stuende dort fuer immer ein offener Punkt, den niemand schliessen kann.
    lage["diskussion"] = (
        _diskussion_verdichtet(conn, chat_id) if workshop.diskussion_aktiv() else None
    )
    anzahl = zusatz.get("szenen_anzahl")
    return {
        "phasen": modul.werkbank(lage, lage["phase"]),
        "begriffe_detail": modul.begriffe_detail(lage["stand"]),
        "szenen_anzahl": (str(anzahl).strip() or None) if anzahl is not None else None,
    }
```

In `gruppe_nach_token` direkt nach `from interview_theater import fragen_auswertung as _fragen_auswertung_modul` ergänzen `from interview_theater import workshop as _workshop`, und im Rückgabe-Dict nach `"stueckkarte_felder": …,`:

```python
        # Die read-only Werkbank (Padua, 03.10.2026) -- nur, wenn das Profil
        # den Arbeitsstand nicht bearbeiten laesst. Dortmund liest sie nie.
        "werkbank": (
            werkbank(conn, chat_id) if not _workshop.workbench_bearbeitbar() else None
        ),
```

- [ ] **Step 4: Grün**

Run: `$PY -m pytest -q tests/test_web_daten_werkbank.py tests/test_roadmap.py tests/test_web_daten.py tests/test_werkbank_bitgleich.py`
Expected: PASS.

**Mutationsprobe:** in `werkbank()` die Zeile `lage["figuren"] = …` streichen → `test_ueberarbeitung_gesamttext_form_und_sprechweise` rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_daten.py tests/test_web_daten_werkbank.py
git commit -m "web_daten: Werkbank read-only laden (Diskussion, Abnahmen, Sprechweisen)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Statuspunkte gestalten (`web_gestalt.css_werkbank` + Kontrast)

**Files:**
- Modify: `interview_theater/web_gestalt.py` (`KONTRAST` ~Zeile 173-193; neue Funktion nach `css_dashboard` ~Zeile 441; neue Konstante `_WERKBANK` nach `_STAND` ~Zeile 1272)
- Modify: `tests/test_sprache_texte.py` (`BLEIBT_DEUTSCH`, Block „Karte Padua UX")
- Test: `tests/test_werkbank_gestalt.py`

**Interfaces:**
- Produces: `web_gestalt.css_werkbank(name: str | None = None) -> str` (für beide Entwürfe gleich, ungescopt geliefert, der Aufrufer scopt auf `.panel-stand`). CSS-Klassen, die Task 6/7 rendern: `.werkbank`, `.wb-hinweis`, `details.wb-phase`, `.wb-name`, `.wb-fertig`, `.wb-zahl`, `ul.wb-zeilen`, `.wb-zeile` (+ `.wb-erledigt|.wb-offen|.wb-spaeter`), `.wb-punkt` (+ dieselben drei), `.wb-laeuft`, `.wb-inhalt`, `dl.wb-begriffe`, `details.wb-journal`.

ANNAHME (geprüft, Geschmack offen): `--warn` existiert in beiden Token-Blöcken — in A `#ffc857` (Gelb), in B `#7fd6a0` (Mint). D6 verlangt `var(--warn)`; wirkt der Mint-Ring in B neben dem Amber-Haken unruhig, ist es ein Einzeiler auf `var(--text)` — Birk entscheidet am Screenshot (Task 10).

- [ ] **Step 1: Failing test**

```python
"""Die Statuspunkte der read-only Werkbank (Padua, 03.10.2026): Form und Farbe
tragen den Zustand, jede Farbe haelt 3:1 (WCAG 1.4.11), kein Emoji."""

import re

import pytest

from interview_theater import web_gestalt

PUNKTE = {
    ("signal", "grund"), ("warn", "grund"), ("text-leise", "grund"),
    ("signal", "grund-2"), ("warn", "grund-2"), ("text-leise", "grund-2"),
    ("auf-signal", "signal"),
}


def _regel(css: str, selektor: str) -> str:
    treffer = re.search(re.escape(selektor) + r"\s*\{([^}]*)\}", css)
    assert treffer, selektor
    return treffer.group(1)


def test_die_statuspunkte_stehen_in_der_kontrasttabelle():
    paare = {(p.vorn, p.hinten) for p in web_gestalt.KONTRAST
             if p.zweck.startswith("Werkbank") and p.mindest >= 3.0}
    assert PUNKTE <= paare


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jeder_statuspunkt_haelt_drei_zu_eins(name):
    tokens = web_gestalt.TOKENS[name]
    for vorn, hinten in PUNKTE:
        assert web_gestalt.kontrastverhaeltnis(tokens[vorn], tokens[hinten]) >= 3.0, (vorn, hinten)


def test_die_form_traegt_den_zustand_nicht_nur_die_farbe():
    css = web_gestalt.css_werkbank()
    erledigt = _regel(css, ".wb-punkt.wb-erledigt")
    offen = _regel(css, ".wb-punkt.wb-offen")
    spaeter = _regel(css, ".wb-punkt.wb-spaeter")
    assert "background: var(--signal)" in erledigt
    assert "transparent" in offen and "solid var(--warn)" in offen
    assert "transparent" in spaeter and "dashed var(--text-leise)" in spaeter
    assert '"✓"' in _regel(css, ".wb-punkt.wb-erledigt::after")


def test_der_zaehler_ist_leise():
    assert "var(--text-leise)" in _regel(web_gestalt.css_werkbank(), ".wb-zahl")


def test_ohne_media_keyframes_und_fremdquelle():
    css = web_gestalt.css_werkbank()
    for verboten in ("@media", "@keyframes", "@import", "@font-face", "url("):
        assert verboten not in css


def test_ohne_ampel_emoji():
    css = web_gestalt.css_werkbank()
    for zeichen in ("🟢", "🔴", "⚪", "🟡"):
        assert zeichen not in css


def test_fuer_beide_entwuerfe_gleich():
    assert web_gestalt.css_werkbank("a") == web_gestalt.css_werkbank("b")
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_gestalt.py`
Expected: FAIL (`AttributeError: … has no attribute 'css_werkbank'`).

- [ ] **Step 3: Implementieren**

`KONTRAST` — vor der schließenden `)` anhängen:

```python
    # Die Statuspunkte der read-only Werkbank (Padua, 03.10.2026): gefuellt /
    # Ring / gestrichelt -- die Form traegt den Zustand, die Farbe muss als
    # Grenze eines grafischen Objekts 3:1 halten (WCAG 1.4.11).
    Paar("signal", "grund", "Werkbank: Punkt erledigt", 3.0),
    Paar("warn", "grund", "Werkbank: Ring offen", 3.0),
    Paar("text-leise", "grund", "Werkbank: gestrichelter Ring spaeter", 3.0),
    Paar("signal", "grund-2", "Werkbank: Punkt erledigt auf gehobener Flaeche", 3.0),
    Paar("warn", "grund-2", "Werkbank: Ring offen auf gehobener Flaeche", 3.0),
    Paar("text-leise", "grund-2", "Werkbank: Ring spaeter auf gehobener Flaeche", 3.0),
    Paar("auf-signal", "signal", "Werkbank: Haken im erledigt-Punkt", 3.0),
```

Nach `css_dashboard`:

```python
def css_werkbank(name: str | None = None) -> str:
    """Die read-only Werkbank (Padua, 03.10.2026) -- nur mit
    ``[web] workbench_bearbeitbar = false``, eingehaengt an EINER Stelle in
    ``web_vereint.seite`` und dort auf ``.panel-stand`` gescopt. Ohne
    ``@keyframes``/``@media``. Fuer beide Entwuerfe gleich, die Tokens tragen
    den Unterschied."""
    return _WERKBANK
```

Nach `_STAND`:

```python
#: Die read-only Werkbank (Padua, 03.10.2026, Birk: "Anstatt roter und gruener
#: LEDs passendere Farben im Design. Dezenter, aber trotzdem klar."). Drei
#: Punkte, die sich in der FORM unterscheiden: gefuellt mit Haken (erledigt),
#: Ring (offen), gestrichelter Ring (spaeter). Kein Emoji.
_WERKBANK = """
.wb-hinweis { color: var(--text-leise); margin: .2rem 0 1rem; }
details.wb-phase { border-top: 1px solid var(--linie); padding: .1rem 0; }
details.wb-phase > summary { display: flex; align-items: center; gap: .6rem;
                             min-height: var(--tippflaeche); list-style: none;
                             cursor: pointer; }
details.wb-phase > summary::-webkit-details-marker { display: none; }
.wb-name { font-family: var(--schrift-skript); font-weight: 700; color: var(--text); }
.wb-fertig { color: var(--signal); }
.wb-zahl { margin-left: auto; color: var(--text-leise);
           font-family: var(--schrift-tech); font-size: .8rem; }
ul.wb-zeilen { list-style: none; padding-left: 0; margin: .1rem 0 .6rem; }
.wb-zeile { display: flex; align-items: baseline; gap: .55rem; padding: .15rem 0; }
.wb-zeile.wb-spaeter { color: var(--text-leise); }
.wb-punkt { flex: 0 0 auto; position: relative; top: .1rem; width: .85rem;
            height: .85rem; border-radius: 50%; box-sizing: border-box; }
.wb-punkt.wb-erledigt { background: var(--signal); border: 2px solid var(--signal); }
.wb-punkt.wb-erledigt::after { content: "✓"; position: absolute; inset: 0;
                               display: flex; align-items: center; justify-content: center;
                               font-size: .55rem; line-height: 1; color: var(--auf-signal); }
.wb-punkt.wb-offen { background: transparent; border: 2px solid var(--warn); }
.wb-punkt.wb-spaeter { background: transparent; border: 2px dashed var(--text-leise); }
.wb-laeuft { color: var(--text-leise); font-size: .85em; }
.wb-inhalt { padding: 0 0 .8rem 1.4rem; }
dl.wb-begriffe dd { margin: 0 0 .3rem; }
details.wb-journal { margin-top: 1.5rem; font-size: .9em; color: var(--text-leise); }
"""
```

In `tests/test_sprache_texte.py`, im Block mit `"web_gestalt._STAND": "CSS, nur Kommentare deutsch",` eine Zeile darunter:

```python
    "web_gestalt._WERKBANK": "CSS, nur Kommentare deutsch",
```

- [ ] **Step 4: Grün**

Run: `$PY -m pytest -q tests/test_werkbank_gestalt.py tests/test_web_gestalt_tokens.py tests/test_web_gestalt_css.py tests/test_sprache_texte.py tests/test_werkbank_bitgleich.py`
Expected: PASS. ANNAHME: `test_sprache_texte` (Regel 5) verlangt für jede neue String-Konstante in `web_gestalt` einen `BLEIBT_DEUTSCH`-Eintrag; meldet er weitere, mit Grund dort eintragen.

**Mutationsprobe:** `dashed` → `solid` in `.wb-punkt.wb-spaeter` → `test_die_form_traegt_den_zustand_nicht_nur_die_farbe` rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_werkbank_gestalt.py tests/test_sprache_texte.py
git commit -m "Gestaltung: Statuspunkte der Werkbank, Kontrast fuer beide Entwuerfe

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `web.werkbank_koerper` — Gerüst, Punkte, Hinweis, Journal; Weiche

**Files:**
- Modify: `interview_theater/web.py` (Texte nach `_TEXT_JOURNAL = "Journal ({anzahl})"` ~Zeile 929; `_journal_html` + Werkbank-Funktionen vor `def gruppe_koerper` ~Zeile 2797; Weiche in `gruppe_koerper` und `gruppe_html`)
- Modify: `interview_theater/sprachen/en/texte.toml` (Tabelle `["web"]`, direkt nach `_TEXT_JOURNAL = "Journal ({anzahl})"` ~Zeile 1534)
- Modify: `tests/test_web_sprache.py` (`test_speichermeldungen_kommen_aus_data_attributen`)
- Test: `tests/test_werkbank_web.py`

**Interfaces:**
- Consumes: `roadmap.werkbank`, `roadmap.ERLEDIGT/OFFEN/SPAETER` (Task 3); `daten["werkbank"]` (Task 4); `workshop.workbench_bearbeitbar` (Task 2).
- Produces: `web.werkbank_koerper(daten: dict) -> str`; `web._journal_html(eintraege: list[dict]) -> str`; `web._wb_inhalt_html(nummer: int, daten: dict, werkbank: dict) -> str` (hier noch leer, Task 7 füllt sie); Markup-Vertrag: `<details class="wb-phase" data-wb-phase="N"[ open]>`, `<li class="wb-zeile wb-<status>" data-kennung="…">`, `<span class="wb-punkt wb-<status>" role="img" aria-label="done|open|later">`, `<details class="wb-journal">`.

- [ ] **Step 1: Failing tests**

```python
"""Die read-only Werkbank auf der Gruppenseite (Padua, 03.10.2026).

Birk, 03.10.: "Unter Workbench alle Dropdowns und Textfelder gegen reine
Read-only-Darstellung ersetzen. Aenderungen passieren ueber Chat. Workbench
reiner Status-Ausspieler." Nur erfundenes Material (``fixture_sprache``)."""

import html as html_modul
import re

import pytest

from interview_theater import db, repo, roadmap, sprache, web, web_chat, web_daten, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FORMULAR = re.compile(r"<(select|textarea|input|button)\b|contenteditable", re.I)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _padua_daten(tmp_path):
    """Die volle englische Gruppe (Phase 6), gelesen UNTER dem Padua-Profil --
    nur dann traegt ``gruppe_nach_token`` den Schluessel ``werkbank``."""
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_volle_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token), token
    finally:
        lesend.close()


_STANDFELDER = (
    "phase", "begriffe", "fragen", "frage_einleitungen", "fragen_weich",
    "fragen_herkunft_final", "interview_eroeffnung", "interview_abschluss",
    "kernthema", "kernthema_begruendung", "format", "rahmen", "kernthema_richtung",
    "kernfrage", "geschichte", "figuren_fixiert_am", "hauptkonflikt", "geaendert_am",
)


def _lage(**abweichung) -> dict:
    grund = {"stand": {}, "figuren": [], "szenen": [], "interviews": [],
             "zuordnungen": 0, "pruefrunde": None, "phase": 1,
             "interviewmodus": False, "tippt": False, "strom": None}
    grund.update(abweichung)
    return grund


def _mini(phasen_liste=None, **mehr) -> dict:
    """Ein minimales ``daten``-Dict fuer ``werkbank_koerper`` ohne Datenbank."""
    daten = {
        "titel": "Test group", "chat_id": 1, "web_token": None, "kanal": "web",
        "arbeitsstand": dict.fromkeys(_STANDFELDER), "journal": [], "interviews": [],
        "figuren": [], "szenen": [], "festlegungen": [], "fragen_auswertung": None,
        "sprechanteile": None, "dramaturgie": None,
        "werkbank": {"phasen": phasen_liste or [], "begriffe_detail": [], "szenen_anzahl": None},
    }
    daten.update(mehr)
    return daten


def test_padua_werkbank_ohne_formular(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    for nonce in (None, "nonce-x"):
        seite = web.gruppe_koerper(daten, nonce, token)
        assert not FORMULAR.search(seite), FORMULAR.search(seite)
        assert "data-feld" not in seite
        assert 'id="meldungen"' not in seite


def test_padua_gruppenseite_ohne_bearbeiten_js(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    assert web._BEARBEITEN_JS not in web.gruppe_html(daten, "nonce-x", token)


def test_der_hinweis_steht_genau_einmal_ganz_oben(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, "nonce-x", token)
    assert web.T._TEXT_WERKBANK_HINWEIS == "To change something, just tell the bot in the chat."
    hinweis = html_modul.escape(web.T._TEXT_WERKBANK_HINWEIS)
    assert seite.count(hinweis) == 1
    assert seite.index(hinweis) < seite.index('class="wb-phase"')


def test_keine_phasenanzeige_keine_links_keine_alten_abschnitte(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, "nonce-x", token)
    assert f"<dt>{web.T.ARBEITSSTAND_BESCHRIFTUNG['phase']}</dt>" not in seite
    for weg in ('class="probenansicht"', '/textbuch"', f'/{web_chat.CHAT_PFAD}"',
                'class="fehlstellen"', 'class="stueckkarte"', 'class="uebersicht"'):
        assert weg not in seite, weg


def test_sieben_phasen_in_reihenfolge(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    stellen = [seite.index(f'data-wb-phase="{n}"') for n in range(1, 8)]
    assert stellen == sorted(stellen)
    assert seite.count('<details class="wb-phase"') == 7


def test_nur_die_aktuelle_phase_ist_aufgeklappt(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)          # die Gruppe steht in Phase 6
    seite = web.gruppe_koerper(daten, None, token)
    assert re.findall(r'<details class="wb-phase" data-wb-phase="(\d)" open>', seite) == ["6"]


def test_drei_zustaende_mit_form_und_beschriftung(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert 'class="wb-punkt wb-erledigt" role="img" aria-label="done"' in seite
    assert 'class="wb-punkt wb-offen" role="img" aria-label="open"' in seite
    assert 'class="wb-punkt wb-spaeter" role="img" aria-label="later"' in seite


def test_nach_der_aktuellen_phase_steht_nichts_offen(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    sieben = seite[seite.index('data-wb-phase="7"'):seite.index('class="wb-journal"')]
    assert "wb-offen" not in sieben


def test_keine_ampel_emoji(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    for zeichen in ("🟢", "🔴", "⚪", "🟡", "✅", "⬜", "⏳"):
        assert zeichen not in seite


def test_laeuft_ist_ein_wort_am_offenen_punkt(padua):
    phasen_liste = roadmap.werkbank(_lage(phase=3, interviewmodus=True), 3)
    seite = web.werkbank_koerper(_mini(phasen_liste))
    zeile = re.search(
        r'<li class="wb-zeile wb-offen" data-kennung="interviews">.*?</li>', seite).group(0)
    assert web.T._TEXT_WERKBANK_LAEUFT == "running"
    assert "running" in zeile


def test_der_zaehler_und_der_haken(padua):
    phasen_liste = roadmap.werkbank(_lage(phase=2, stand={"begriffe": "x"}), 2)
    seite = web.werkbank_koerper(_mini(phasen_liste))
    eins = seite[seite.index('data-wb-phase="1"'):seite.index('data-wb-phase="2"')]
    zwei = seite[seite.index('data-wb-phase="2"'):seite.index('data-wb-phase="3"')]
    assert "1 of 1" in eins and 'class="wb-fertig"' in eins
    assert "0 of 4" in zwei and 'class="wb-fertig"' not in zwei


def test_das_journal_steht_unten_und_zu(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert '<details class="wb-journal">' in seite
    assert seite.index('class="wb-journal"') > seite.index('data-wb-phase="7"')


def test_ohne_werkbankdaten_kein_absturz(padua):
    seite = web.werkbank_koerper(_mini(werkbank=None))
    assert 'class="wb-phase"' not in seite
    assert html_modul.escape(web.T._TEXT_WERKBANK_HINWEIS) in seite
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_web.py`
Expected: FAIL (`AttributeError: … has no attribute 'werkbank_koerper'` bzw. Formulare gefunden).

- [ ] **Step 3: Texte**

`interview_theater/web.py`, nach `_TEXT_JOURNAL = "Journal ({anzahl})"`:

```python
# --- Die read-only Werkbank (Padua, 03.10.2026) ----------------------------
_TEXT_WERKBANK_HINWEIS = "Etwas ändern? Sagt es einfach dem Bot im Chat."
_TEXT_WERKBANK_ZAHL = "{erledigt} von {gesamt}"
_TEXT_STATUS_ERLEDIGT = "erledigt"
_TEXT_STATUS_OFFEN = "offen"
_TEXT_STATUS_SPAETER = "später"
_TEXT_WERKBANK_LAEUFT = "läuft"
_TEXT_WB_DISKUSSION = "Diskussion zusammengefasst"
_TEXT_WB_INTERVIEW_FERTIG = "{bezug}: aufgenommen, ausgewertet"
_TEXT_WB_INTERVIEW_OFFEN = "{bezug}: aufgenommen, noch nicht ausgewertet"
_TEXT_WB_PROSA = "Szene {bezug}: Prosa"
_TEXT_WB_GESAMTTEXT = "Rückmeldung zum ganzen Text"
_TEXT_WB_UEBERARBEITET = "Szene {bezug}: überarbeitet"
_TEXT_WB_FORM = "Szene {bezug}: Form"
_TEXT_WB_SPRECHWEISE = "{bezug}: Sprechweise"
```

`interview_theater/sprachen/en/texte.toml`, in `["web"]` direkt nach `_TEXT_JOURNAL = "Journal ({anzahl})"`:

```toml
_TEXT_WERKBANK_HINWEIS = "To change something, just tell the bot in the chat."
_TEXT_WERKBANK_ZAHL = "{erledigt} of {gesamt}"
_TEXT_STATUS_ERLEDIGT = "done"
_TEXT_STATUS_OFFEN = "open"
_TEXT_STATUS_SPAETER = "later"
_TEXT_WERKBANK_LAEUFT = "running"
_TEXT_WB_DISKUSSION = "Discussion summarised"
_TEXT_WB_INTERVIEW_FERTIG = "{bezug}: recorded, summarised"
_TEXT_WB_INTERVIEW_OFFEN = "{bezug}: recorded, not yet summarised"
_TEXT_WB_PROSA = "Scene {bezug}: prose"
_TEXT_WB_GESAMTTEXT = "Feedback on the whole text"
_TEXT_WB_UEBERARBEITET = "Scene {bezug}: revised"
_TEXT_WB_FORM = "Scene {bezug}: form"
_TEXT_WB_SPRECHWEISE = "{bezug}: way of speaking"
```

- [ ] **Step 4: Rendering + Weiche**

Vor `def gruppe_koerper(`:

```python
def _journal_html(eintraege: list[dict]) -> str:
    """Die Journalzeilen -- herausgeloest aus ``gruppe_koerper`` (Werkbank,
    03.10.2026), Zeichen fuer Zeichen dieselben."""
    return "".join(
        '<div class="eintrag"><span class="art">{art}</span>{text} '
        '<span class="zeit">{zeit}</span></div>'.format(
            art=_t(T.JOURNALART_BESCHRIFTUNG.get(e["art"], e["art"])),
            text=_t(e["text"]),
            zeit=_zeitpunkt(e["erstellt_am"]),
        )
        for e in eintraege
    ) or f'<p class="leer">{_t(T._TEXT_NICHTS_NOTIERT)}</p>'


def _wb_status_text(status: str) -> str:
    from interview_theater import roadmap

    return {
        roadmap.ERLEDIGT: T._TEXT_STATUS_ERLEDIGT,
        roadmap.OFFEN: T._TEXT_STATUS_OFFEN,
        roadmap.SPAETER: T._TEXT_STATUS_SPAETER,
    }[status]


def _wb_zeilentext(z: dict) -> str:
    """Aufgaben tragen ihren Text schon (``phasentexte.beschriftung``),
    Detailzeilen werden hier beschriftet -- ``roadmap`` bleibt textfrei."""
    from interview_theater import roadmap

    if z["art"] == "aufgabe":
        return z["text"] or ""
    vorlage = {
        "diskussion": T._TEXT_WB_DISKUSSION,
        "interview": (T._TEXT_WB_INTERVIEW_FERTIG if z["status"] == roadmap.ERLEDIGT
                      else T._TEXT_WB_INTERVIEW_OFFEN),
        "prosa": T._TEXT_WB_PROSA,
        "gesamttext": T._TEXT_WB_GESAMTTEXT,
        "ueberarbeitet": T._TEXT_WB_UEBERARBEITET,
        "form": T._TEXT_WB_FORM,
        "sprechweise": T._TEXT_WB_SPRECHWEISE,
    }[z["kennung"]]
    text = vorlage.format(bezug="" if z.get("bezug") is None else z["bezug"])
    if z.get("titel"):
        text += SUMMARY_TRENNER + z["titel"]
    return text


def _wb_zeile_html(z: dict) -> str:
    """Eine Attributzeile: Punkt (Form + Farbe + aria-label), Text, und bei
    einer laufenden Aufgabe das Wort 'running' -- keine eigene Farbe."""
    status = z["status"]
    laeuft = (
        f' <span class="wb-laeuft">{_t(T._TEXT_WERKBANK_LAEUFT)}</span>'
        if z.get("laeuft") else ""
    )
    return (
        f'<li class="wb-zeile wb-{status}" data-kennung="{_t(z["kennung"])}">'
        f'<span class="wb-punkt wb-{status}" role="img" '
        f'aria-label="{_t(_wb_status_text(status))}"></span>'
        f"<span>{_t(_wb_zeilentext(z))}</span>{laeuft}</li>"
    )


def _wb_inhalt_html(nummer: int, daten: dict, werkbank: dict) -> str:
    """Was unter den Punkten einer Phase steht. Aufgabe 7 fuellt das."""
    return ""


def werkbank_koerper(daten: dict) -> str:
    """Der Arbeitsstand als reine Statusansicht (Padua, 03.10.2026, Karte
    t_49e7354c) -- statt ``gruppe_koerper``, wenn das Profil
    ``[web] workbench_bearbeitbar = false`` setzt.

    EINE Achse: die sieben Phasen in Reihenfolge, je ein ``<details>`` mit
    Zaehler, darunter die Attribute mit einem Punkt aus drei Formen
    (``roadmap.werkbank``). Aufgeklappt ist allein die aktuelle Phase. Kein
    Formular, kein Knopf, kein Nonce: geaendert wird im Chat. Keine
    Phasenanzeige, kein Probenansicht- und kein Chat-Link -- die Kopfleiste
    der Seite zeigt die Phase (Birk: "die Anzeige der aktuellen Phase ist
    doppelt")."""
    werkbank = daten.get("werkbank") or {}
    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    bloecke = []
    for phase in werkbank.get("phasen") or []:
        zahl = T._TEXT_WERKBANK_ZAHL.format(erledigt=phase["erledigt"], gesamt=phase["gesamt"])
        haken = (
            ' <span class="wb-fertig" aria-hidden="true">✓</span>' if phase["fertig"] else ""
        )
        offen = " open" if phase["aktiv"] else ""
        zeilen = "".join(_wb_zeile_html(z) for z in phase["zeilen"])
        bloecke.append(
            f'<details class="wb-phase" data-wb-phase="{phase["nummer"]}"{offen}>'
            f'<summary><span class="wb-name">{_t(phase["bezeichnung"])}</span>{haken}'
            f'<span class="wb-zahl">{_t(zahl)}</span></summary>'
            f'<ul class="wb-zeilen">{zeilen}</ul>'
            f"{_wb_inhalt_html(phase['nummer'], daten, werkbank)}"
            "</details>"
        )
    journal = (
        '<details class="wb-journal"><summary>'
        f"{_t(T._UEBERSCHRIFT_WEG)}{SUMMARY_TRENNER}"
        f"{_t(T._TEXT_JOURNAL.format(anzahl=len(daten['journal'])))}</summary>"
        f"{_journal_html(daten['journal'])}</details>"
    )
    return (
        f"<h1>{_t(titel)}</h1>\n"
        '<div id="stand-inhalt" class="werkbank">\n'
        f'<p class="wb-hinweis">{_t(T._TEXT_WERKBANK_HINWEIS)}</p>\n'
        + "\n".join(bloecke)
        + f"\n{journal}\n</div>\n"
    )
```

In `gruppe_koerper`, als erste Anweisung nach dem Docstring:

```python
    from interview_theater import workshop

    if not workshop.workbench_bearbeitbar():
        # Padua (03.10.2026): reine Statusansicht. Der Nonce wird hier nicht
        # gebraucht -- auf der vereinten Seite steht er im Chat-Panel.
        return werkbank_koerper(daten)
```

und dort die Journal-Zusammensetzung ersetzen durch `journal = _journal_html(daten["journal"])` (Ausgabe identisch; der Byte-Test aus Aufgabe 1 hält es fest).

In `gruppe_html` das letzte Argument von `_seite(...)` ändern:

```python
    from interview_theater import workshop

    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    return _seite(
        T._TITEL_GRUPPENSEITE.format(titel=titel),
        _CSS_GRUPPE,
        gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        # Padua: die Werkbank ist reine Anzeige, das Speicher-Skript faellt weg.
        bearbeitbar=bool(nonce_wert) and workshop.workbench_bearbeitbar(),
    )
```

Hinweis: `gruppe_html` als Einzelseite wird von keiner Route mehr ausgeliefert (`/g/<token>` geht an `web_vereint`) und bindet `web_gestalt` nicht ein — dort bleiben die Punkte ungestaltet. Bewusst nicht behoben (YAGNI).

- [ ] **Step 5: Bestehenden Padua-Test anpassen**

`tests/test_web_sprache.py::test_speichermeldungen_kommen_aus_data_attributen` prüft die Speichermeldungen der Formulare unter Padua — die gibt es dort jetzt nicht mehr. Signatur um `monkeypatch` erweitern und als erste Zeile nach dem Docstring:

```python
    # Seit der read-only Werkbank (03.10.2026) gibt es die Formulare nur noch
    # mit ``[web] workbench_bearbeitbar = true``; Padua setzt false. Geprueft
    # wird hier die SPRACHE der Meldungen, deshalb der Schalter erzwungen.
    monkeypatch.setattr(workshop, "workbench_bearbeitbar", lambda profil=None: True)
```

- [ ] **Step 6: Grün**

Run: `$PY -m pytest -q tests/test_werkbank_web.py tests/test_werkbank_bitgleich.py tests/test_web_sprache.py tests/test_sprache_texte.py tests/test_web_koerper.py tests/test_web.py tests/test_web_edit.py tests/test_fehlstellen.py`
Expected: PASS. Insbesondere `test_padua_seiten_ohne_deutsch` (kein deutsches Wort in der Padua-Werkbank) und `test_jeder_zugriff_hat_einen_englischen_eintrag`.

**Mutationsproben:** (a) `workbench_bearbeitbar = true` in Padua → `test_padua_werkbank_ohne_formular` und `test_padua_gruppenseite_ohne_bearbeiten_js` rot. (b) in `_wb_zeile_html` die Klasse `wb-{status}` am Punkt durch `wb-erledigt` ersetzen → `test_drei_zustaende_mit_form_und_beschriftung` rot. (c) ein „🟢" in `_wb_zeile_html` → `test_keine_ampel_emoji` rot.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/web.py interview_theater/sprachen/en/texte.toml tests/test_werkbank_web.py tests/test_web_sprache.py
git commit -m "Werkbank: read-only Statusansicht je Phase mit Statuspunkten (Padua)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Inhalt je Phase

**Files:**
- Modify: `interview_theater/web.py` (`_wb_inhalt_html` ausfüllen, `_auch_vereinbart_html` neu; Text `_TEXT_WB_AUCH_VEREINBART`)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["web"]`, nach `_TEXT_WB_SPRECHWEISE`)
- Test: `tests/test_werkbank_web.py` (anhängen)

**Interfaces:**
- Consumes: `_fragen_html`, `_fragen_auswertung_html`, `_leitfaden_html`, `_interview_html`, `_altbestand_html`, `_festlegungen_html(daten, None)`, `_dramaturgie_html`, `_sprechanteile_html`, `vorspann.erster_satz` — alle unverändert.
- Produces: der Inhalt unter Phase 1, 2, 3, 4, 6, 7 (Phase 5: nur Punkte). **`pre.leitfaden` muss in Phase 2 stehen**: `web_gestalt._JS_INTERVIEW` liest den Leitfaden des Interview-Modus per `document.querySelector('pre.leitfaden')` (web_gestalt.py ~Zeile 1806) aus dem Stand-Panel.

- [ ] **Step 1: Failing tests (an `tests/test_werkbank_web.py` anhängen)**

```python
def _block(seite: str, nummer: int) -> str:
    anfang = seite.index(f'data-wb-phase="{nummer}"')
    ende = (seite.index('<details class="wb-phase"', anfang + 1) if nummer < 7
            else seite.index('class="wb-journal"'))
    return seite[anfang:ende]


def test_phase_1_zeigt_die_begriffe(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    assert "belonging, family, noise, courage" in _block(web.gruppe_koerper(daten, None, token), 1)


def test_begriffe_detail_mit_daten(padua):
    """Der Haken fuer Karte t_4517d4ad -- mit Inhalt."""
    phasen_liste = roadmap.werkbank(_lage(stand={"begriffe": "Heimat"}), 1)
    daten = _mini(phasen_liste)
    daten["arbeitsstand"]["begriffe"] = "Heimat"
    daten["werkbank"]["begriffe_detail"] = [
        {"begriff": "Heimat", "begruendung": "came up three times",
         "doppelbedeutung": "place and feeling"}]
    block = _block(web.werkbank_koerper(daten), 1)
    assert 'class="wb-begriffe"' in block
    assert "came up three times" in block and "place and feeling" in block


def test_begriffe_detail_ohne_daten(padua):
    phasen_liste = roadmap.werkbank(_lage(), 1)
    assert 'class="wb-begriffe"' not in web.werkbank_koerper(_mini(phasen_liste))


def test_phase_2_fragen_leitfaden_und_ab_zeile(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    block = _block(web.gruppe_koerper(daten, None, token), 2)
    assert 'class="fragen"' in block
    assert '<pre class="leitfaden">' in block       # _JS_INTERVIEW liest ihn hier
    daten["fragen_auswertung"] = {"gesamt": {"eigen": 2, "ki": 1}}
    block = _block(web.gruppe_koerper(daten, None, token), 2)
    assert web.T._TEXT_FRAGEN_AUSWERTUNG.format(eigen=2, ki=1) in block


def test_phase_3_verdichtung_wie_bisher_ohne_transkript(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    block = _block(seite, 3)
    assert "She talks about home and the bakery." in block
    assert "Home is the smell of bread." in block              # zitat_geprueft = 1
    assert "Allora, I grew up above a bakery" not in seite     # nur im Transkript


def test_phase_4_setting_figuren_und_auch_vereinbart(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    block = _block(web.gruppe_koerper(daten, None, token), 4)
    assert "A bus stop at night" in block
    assert "<b>Nadia</b>" in block and "the older sister, restless" in block
    assert html_modul.escape(web.T._TEXT_WB_AUCH_VEREINBART) in block
    assert "At most one song." in block                        # eine Festlegung
    assert "<button" not in block


def test_keine_szenen_volltexte(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert "You always say that." not in seite
    assert "TOMAS: Stay." not in seite


def test_phase_6_dramaturgie_und_phase_7_sprechanteile(tmp_path, padua):
    daten, token = _padua_daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, token)
    assert "Scene 1 does not turn." in _block(seite, 6)
    assert 'class="anteile"' in _block(seite, 7)
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_web.py`
Expected: die neuen Tests FAIL (`_wb_inhalt_html` liefert noch `""`; `_TEXT_WB_AUCH_VEREINBART` fehlt).

- [ ] **Step 3: Implementieren**

Text in `web.py` nach `_TEXT_WB_SPRECHWEISE`: `_TEXT_WB_AUCH_VEREINBART = "Auch vereinbart"`; in `texte.toml` nach `_TEXT_WB_SPRECHWEISE`: `_TEXT_WB_AUCH_VEREINBART = "Also agreed"`.

`_wb_inhalt_html` ersetzen, `_auch_vereinbart_html` davor:

```python
def _auch_vereinbart_html(daten: dict, szenen_anzahl: str | None) -> str:
    """Stueckkarte und Festlegungen als EINE read-only Liste (Werkbank).
    Setting, Figuren und Geschichte der Stueckkarte stehen schon darueber --
    hier bleibt von ihr nur die Szenenzahl. Ohne Loeschknopf (kein Nonce)."""
    zeilen = []
    if szenen_anzahl:
        zeilen.append(
            '<div class="festlegung"><span class="marke">{marke}</span>'
            "<span>{wert}</span></div>".format(
                marke=_t(T._STUECKKARTE_SZENENANZAHL), wert=_t(szenen_anzahl))
        )
    if daten.get("festlegungen"):
        zeilen.append(_festlegungen_html(daten, None))
    if not zeilen:
        return ""
    return f"<h3>{_t(T._TEXT_WB_AUCH_VEREINBART)}</h3>" + "".join(zeilen)


def _wb_inhalt_html(nummer: int, daten: dict, werkbank: dict) -> str:
    """Was unter den Punkten einer Phase steht -- read-only, aus denselben
    Bausteinen wie die bisherige Gruppenseite (keine zweite Formatierung):
    1 die Begriffe (und ``begriffe_detail``, wenn es sie gibt), 2 Fragen,
    A/B-Zeile und Leitfaden (``pre.leitfaden`` liest der Interview-Modus),
    3 die Verdichtungen wie bisher, 4 Setting, Geschichte, Figuren,
    Szenenkoepfe und "Also agreed", 6 die Dramaturgie-Pruefung, 7 die
    Sprechanteile. Keine Szenen-Volltexte -- die stehen im Script-Tab."""
    stand = daten["arbeitsstand"]
    dt = T.ARBEITSSTAND_BESCHRIFTUNG
    teile: list[str] = []
    if nummer == 1:
        if (stand.get("begriffe") or "").strip():
            teile.append(f"<p>{_t(stand['begriffe'])}</p>")
        detail = werkbank.get("begriffe_detail") or []
        if detail:
            teile.append('<dl class="wb-begriffe">' + "".join(
                f"<dt>{_t(b['begriff'])}</dt>"
                + (f"<dd>{_t(b['begruendung'])}</dd>" if b["begruendung"] else "")
                + (f'<dd class="zeit">{_t(b["doppelbedeutung"])}</dd>'
                   if b["doppelbedeutung"] else "")
                for b in detail
            ) + "</dl>")
    elif nummer == 2:
        if (stand.get("fragen") or "").strip():
            teile.append(_fragen_html(stand["fragen"]))
        teile.append(_fragen_auswertung_html(daten.get("fragen_auswertung")))
        leitfaden = _leitfaden_html(stand, daten.get("web_token"))
        if leitfaden:
            teile.append(f"<dl>{leitfaden}</dl>")
    elif nummer == 3:
        teile.append("".join(_interview_html(v) for v in daten["interviews"]))
    elif nummer == 4:
        zeilen = [
            f"<dt>{_t(dt[feld])}</dt><dd>{_t(stand[feld])}</dd>"
            for feld in ("rahmen", "geschichte")
            if (stand.get(feld) or "").strip()
        ]
        zeilen.append(_altbestand_html(stand))
        if daten["figuren"]:
            figuren = "".join(
                "<li><b>{name}</b>{rest}</li>".format(
                    name=_t(f["name"]),
                    rest=(f" — {_t(vorspann.erster_satz(f.get('beschreibung')))}"
                          if (f.get("beschreibung") or "").strip() else ""),
                )
                for f in daten["figuren"]
            )
            zeilen.append(f'<dt>{_t(dt["figuren"])}</dt><dd><ul class="figuren">{figuren}</ul></dd>')
        if daten["szenen"]:
            szenen = "".join(
                "<li>{nr}. {titel}</li>".format(
                    nr=_t("—" if s["nummer"] is None else str(s["nummer"])),
                    titel=_t(s.get("titel"), T._TEXT_OHNE_TITEL),
                )
                for s in daten["szenen"]
            )
            zeilen.append(f"<dt>{_t(T._UEBERSCHRIFT_SZENEN)}</dt><dd><ul>{szenen}</ul></dd>")
        if any(zeilen):
            teile.append(f"<dl>{''.join(zeilen)}</dl>")
        teile.append(_auch_vereinbart_html(daten, werkbank.get("szenen_anzahl")))
    elif nummer == 6:
        teile.append(_dramaturgie_html(daten.get("dramaturgie")))
    elif nummer == 7:
        teile.append(_sprechanteile_html(daten.get("sprechanteile")))
    inhalt = "".join(t for t in teile if t)
    return f'<div class="wb-inhalt">{inhalt}</div>' if inhalt else ""
```

- [ ] **Step 4: Grün**

Run: `$PY -m pytest -q tests/test_werkbank_web.py tests/test_web_sprache.py tests/test_sprache_texte.py tests/test_werkbank_bitgleich.py tests/test_web.py`
Expected: PASS (inkl. `test_padua_seiten_ohne_deutsch`).

**Mutationsprobe:** `if nummer == 3` auf `if nummer == 99` → `test_phase_3_verdichtung_wie_bisher_ohne_transkript` rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web.py interview_theater/sprachen/en/texte.toml tests/test_werkbank_web.py
git commit -m "Werkbank: Inhalt je Phase (Begriffe, Fragen, Interviews, Rahmen, Pruefung)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Vereinte Seite verdrahten (kein Speicher-Skript, Nonce im Chat, Werkbank-CSS)

**Files:**
- Modify: `interview_theater/web_vereint.py` (`seite()` ~Zeile 1224-1362)
- Test: `tests/test_werkbank_vereint.py`

**Interfaces:**
- Consumes: `workshop.workbench_bearbeitbar` (Task 2), `web_gestalt.css_werkbank` (Task 5), `web.gruppe_koerper`-Weiche (Task 6).
- Produces: In Padua trägt die vereinte Seite genau ein `id="nonce"` — im Chat-Panel (`web_chat.chat_koerper(..., mit_nonce=True)`); bei einer Telegram-Gruppe (kein Chat-Panel) gar keins. `teil/stand` liefert in Padua den Werkbank-Rumpf ohne Nonce; `friskeNonce()` in `_VEREINT_JS` findet dort keinen und gibt `null` zurück (vorhandener Pfad) — der Chat-Poll hält `#nonce` ohnehin alle 2–10 s frisch (`web_chat.py`, Poll setzt `daten["nonce"]`, JS ~Zeile 531/732). ANNAHME: das reicht für den Phasenklick; im Browser-Test (Task 10) nicht gesondert geprüft.

- [ ] **Step 1: Failing test**

```python
"""Die vereinte Seite mit read-only Werkbank (Padua, 03.10.2026)."""

import re

import pytest

from interview_theater import db, repo, sprache, web, web_chat, web_daten, web_vereint, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FORMULAR = re.compile(r"<(select|textarea|input|button)\b|contenteditable", re.I)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _vereint(tmp_path, chat: bool = True) -> str:
    pfad = str(tmp_path / "v.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_volle_englische_gruppe(conn)
    if chat:
        repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    if chatdaten is None:
        chatdaten = {"titel": daten["titel"], "nachrichten": [], "letzte": 0,
                     "interviewmodus": False, "tippt": False, "antworten": {}}
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return web_vereint.seite(daten, chatdaten, roadmapdaten, "nonce-x", token,
                             "/theatersoap", 45000, chat_vorhanden=chat)


def _panel(seite: str, tab: str) -> str:
    anfang = seite.index(f'id="tab-{tab}"')
    return seite[anfang:seite.index("</section>", anfang)]


def test_padua_ohne_speicher_skript_und_ohne_formular(tmp_path, padua):
    seite = _vereint(tmp_path)
    assert web._BEARBEITEN_JS not in seite
    assert not FORMULAR.search(_panel(seite, "stand"))


def test_padua_genau_ein_nonce_und_der_steht_im_chat(tmp_path, padua):
    seite = _vereint(tmp_path)
    assert seite.count('id="nonce"') == 1
    assert 'id="nonce"' in _panel(seite, "chat")


def test_padua_telegram_gruppe_ohne_nonce(tmp_path, padua):
    seite = _vereint(tmp_path, chat=False)
    assert 'id="nonce"' not in seite
    assert web._BEARBEITEN_JS not in seite


def test_padua_traegt_das_werkbank_css_gescopt(tmp_path, padua):
    assert ".panel-stand .wb-punkt.wb-erledigt" in _vereint(tmp_path)


def test_padua_der_leitfaden_steht_fuer_den_interview_modus_bereit(tmp_path, padua):
    assert '<pre class="leitfaden">' in _panel(_vereint(tmp_path), "stand")
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_vereint.py`
Expected: FAIL (`_BEARBEITEN_JS` steht noch drin; `id="nonce"` fehlt im Chat; CSS fehlt).

- [ ] **Step 3: Implementieren** (`interview_theater/web_vereint.py`, in `seite()`)

Nach `from interview_theater import web, web_chat, web_gestalt`:

```python
    from interview_theater import workshop

    # Padua (03.10.2026, read-only Werkbank): ohne Formulare traegt das
    # Stand-Panel auch kein ``id="nonce"``-Feld mehr -- dann steht es im Chat.
    werkbank_bearbeitbar = workshop.workbench_bearbeitbar()
```

Im Aufruf von `web_chat.chat_koerper(...)`: `mit_nonce=False` → `mit_nonce=not werkbank_bearbeitbar`, und den Kommentar darüber um einen Satz ergänzen: „In Padua (read-only Werkbank) steht es nur hier."

Nach `css += scope_css(web_gestalt.css_stand(), ".panel-stand")`:

```python
    if not werkbank_bearbeitbar:
        css += scope_css(web_gestalt.css_werkbank(), ".panel-stand")
```

Im `return web._seite(...)`: `bearbeitbar=True` → `bearbeitbar=werkbank_bearbeitbar`.

- [ ] **Step 4: Grün (inkl. Byte-Gleichheit und bestehende Seiten-Tests)**

Run: `$PY -m pytest -q tests/test_werkbank_vereint.py tests/test_werkbank_bitgleich.py tests/test_web_vereint.py tests/test_web_vereint_js_syntax.py tests/test_web_vereint_nachladen.py tests/test_web_skript_tab.py tests/test_web_gestalt_einhang.py tests/test_web_kopfzeilen.py`
Expected: PASS. Meldet `tests/test_web_gestalt_einhang.py` eine feste Zahl von Einhängezeilen, die zehnte Zeile (`css_werkbank`) dort mit Begründung nachtragen.

**Mutationsprobe:** `bearbeitbar=werkbank_bearbeitbar` zurück auf `bearbeitbar=True` → `test_padua_ohne_speicher_skript_und_ohne_formular` rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_vereint.py tests/test_werkbank_vereint.py
git commit -m "Vereinte Seite: read-only Werkbank ohne Speicher-Skript, Nonce im Chat

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Werkbank-POST in Padua → 403, Chat-POSTs unberührt

**Files:**
- Modify: `interview_theater/web.py` (`_beantworte_post` ~Zeile 3816-3888; Text nach `_TEXT_WB_AUCH_VEREINBART`)
- Modify: `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_werkbank_post.py`

**Interfaces:**
- Consumes: `workshop.workbench_bearbeitbar`.
- Produces: `POST /g/<token>` (leerer Unterpfad) → 403 mit `T._TEXT_WERKBANK_NUR_LESEN` als Klartext, wenn der Schalter falsch ist — geprüft NACH Pfad/Herkunft und NACH dem Chat-Dispatch, VOR dem Lesen des Rumpfes und vor der Token-Suche.

- [ ] **Step 1: Failing test**

```python
"""Der Werkbank-POST in Padua: 403. Die Chat-Wege laufen weiter."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, sprache, web, workshop

CHAT = 7_000_000_000_001
SCHLUESSEL = b"w" * 32


def _profil(monkeypatch, name):
    monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def dienst(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    server = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", token, pfad
    server.shutdown()
    workshop.vergiss()
    sprache.vergiss()


def _post(url: str, koerper: dict) -> tuple[int, str]:
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _rahmen(pfad: str) -> str:
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT rahmen FROM arbeitsstand WHERE chat_id = ?", (CHAT,)).fetchone()[0]
    finally:
        conn.close()


def _werkbank_post(basis, token):
    return _post(f"{basis}/g/{token}", {
        "nonce": web.nonce(SCHLUESSEL, token), "feld": "rahmen", "wert": "Markt, mittags"})


def test_werkbank_post_in_padua_ist_403(dienst, monkeypatch):
    basis, token, pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, text = _werkbank_post(basis, token)
    assert status == 403
    assert text == web.T._TEXT_WERKBANK_NUR_LESEN
    assert _rahmen(pfad) == "Bahnhof, nachts"


def test_werkbank_post_in_dortmund_wirkt_wie_bisher(dienst, monkeypatch):
    basis, token, pfad = dienst
    _profil(monkeypatch, "dortmund-2026")
    status, _text = _werkbank_post(basis, token)
    assert status == 200
    assert _rahmen(pfad) == "Markt, mittags"


def test_chat_senden_in_padua_wird_angenommen(dienst, monkeypatch):
    basis, token, _pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, _text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": web.nonce(SCHLUESSEL, token), "text": "hello bot"})
    assert status == 202


def test_phasenklick_in_padua_wird_angenommen(dienst, monkeypatch):
    basis, token, _pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 2, "bestaetigt": 1})
    assert status == 202
```

- [ ] **Step 2: Rot sehen**

Run: `$PY -m pytest -q tests/test_werkbank_post.py`
Expected: `test_werkbank_post_in_padua_ist_403` FAIL (200 statt 403); die anderen drei PASS. ANNAHME: `chat/phase` antwortet mit 202 über `web_chat._angenommen` (web_chat.py ~Zeile 2693, „202, nicht 200").

- [ ] **Step 3: Implementieren**

Text in `web.py` nach `_TEXT_WB_AUCH_VEREINBART`: `_TEXT_WERKBANK_NUR_LESEN = "Hier wird nur angezeigt – Änderungen bitte im Chat."`; in `texte.toml` nach `_TEXT_WB_AUCH_VEREINBART`: `_TEXT_WERKBANK_NUR_LESEN = "The workbench only shows things — please make changes in the chat."`

In `_beantworte_post`, direkt nach dem Block `if unterpfad: … return` und vor `try: daten = handler._koerper()`:

```python
    from interview_theater import workshop

    if not workshop.workbench_bearbeitbar():
        # Padua (03.10.2026): die Werkbank ist reine Anzeige, geaendert wird
        # im Chat. NUR dieser Weg -- die Chat-POSTs oben laufen weiter. Vor
        # dem Lesen des Rumpfes und vor der Token-Suche: es gibt nichts, was
        # hier je wirken duerfte, also auch nichts zu verraten.
        schliesse_nach_antwort(handler)
        handler._fehler(403, T._TEXT_WERKBANK_NUR_LESEN)
        return
```

Docstring von `_beantworte_post` um einen Satz ergänzen: „Mit ``[web] workbench_bearbeitbar = false`` (Padua) antwortet dieser Weg immer 403 — nach Pfad und Herkunft, vor Token und Nonce."

- [ ] **Step 4: Grün**

Run: `$PY -m pytest -q tests/test_werkbank_post.py tests/test_web_edit.py tests/test_web_herkunft.py tests/test_web_chat_senden.py tests/test_sprache_texte.py tests/test_werkbank_bitgleich.py`
Expected: PASS.

**Mutationsprobe:** den neuen `if`-Block entfernen → `test_werkbank_post_in_padua_ist_403` rot; den Block vor den Chat-Dispatch ziehen → `test_chat_senden_in_padua_wird_angenommen` rot.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web.py interview_theater/sprachen/en/texte.toml tests/test_werkbank_post.py
git commit -m "Werkbank-POST: 403 in Padua, Chat-Wege unberuehrt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Browser — Werkbank im Chromium, Screenshots, Übersichts-Test angepasst

**Files:**
- Create: `tests/e2e/test_web_werkbank_e2e.py`
- Modify: `tests/e2e/test_web_uebersicht_e2e.py` (`test_der_arbeitsstand_ohne_doppelten_chatlink_und_mit_lesbarer_festlegung`, ~Zeile 246-269)
- Create (nur mit `IT_SCHUSS_AKTUALISIEREN=1`): `docs/ux-padua/workbench/werkbank-phase{1,3,5}-{handy,laptop}.png`

**Interfaces:**
- Consumes: die Markup-Klassen aus Task 5–7; `_ALLE_TEXTE`, `_HELLIGKEIT` aus `tests/e2e/test_web_gestalt_e2e.py` (Import wie in `test_web_uebersicht_e2e.py`).

ANNAHME: `$E2E` (`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python`) existiert mit Playwright + Chromium (tests/e2e/README.md, „Einmalig: das Wegwerf-venv"). Fehlt es, nach der README einrichten.

- [ ] **Step 1: Test schreiben**

```python
"""Die read-only Werkbank im echten Chromium (Padua, 03.10.2026).

Drei erfundene Web-Gruppen in Phase 1, 3 und 5 unter ``IT_WORKSHOP=padua-2026``:
kein Eingabeelement im Arbeitsstand, die aktuelle Phase aufgeklappt, die
sieben Phasen in Reihenfolge, jeder sichtbare Text mit Kontrast -- und die
Screenshots fuer Birk (Telefon 390x844 und Laptop).

**Nur erfundenes Material**, nie ``betrieb/``. Die Screenshots landen bei
jedem Lauf unter ``/tmp/it-werkbank-shots/``, ins Repository
(``docs/ux-padua/workbench/``) nur mit ``IT_SCHUSS_AKTUALISIEREN=1``.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_werkbank_e2e.py -q
"""

import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-werkbank.db"
SCHUSS = pathlib.Path("/tmp/it-werkbank-shots")
SCHUSS_REPO = WURZEL / "docs" / "ux-padua" / "workbench"
HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}
GRUPPEN = {1: 7_000_000_000_201, 3: 7_000_000_000_203, 5: 7_000_000_000_205}

from test_web_gestalt_e2e import _ALLE_TEXTE, _HELLIGKEIT  # noqa: E402


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"


def _baue_datenbank() -> dict[int, str]:
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    tokens = {}
    for phase, chat in GRUPPEN.items():
        repo.sichere_gruppe(conn, chat, f"padua_bot{phase}", f"Workbench {phase}")
        repo.setze_gruppe_kanal(conn, chat, "web")
        repo.setze_arbeitsstand(conn, chat, "begriffe", "bridge, market, rain, courage")
        if phase >= 3:
            for feld, wert in (
                ("fragen", "1. Where do you feel at home?\n2. Who do you argue with?\n"
                           "3. What gives you courage?"),
                ("fragen_weich", ""),
                ("interview_eroeffnung", "Hi, we are a youth theatre group."),
                ("interview_abschluss", "Thank you very much."),
            ):
                repo.setze_arbeitsstand(conn, chat, feld, wert)
            for nummer, verdichtet in ((1, True), (2, False)):
                aid = repo.lege_aufnahme_an(conn, chat, 10 + nummer, "lang", "sprache",
                                            status="fertig")
                repo.setze_transkript(conn, aid, f"Invented talk {nummer}. Home is the bridge.")
                if verdichtet:
                    repo.speichere_verdichtung(conn, chat, aid, "She talks about the bridge.", [
                        {"thema": "home", "beleg_zitat": "Home is the bridge.",
                         "zitat_geprueft": 1, "kurz": "home"}])
        if phase >= 5:
            repo.setze_arbeitsstand(conn, chat, "rahmen", "A bus stop at night.")
            repo.setze_arbeitsstand(conn, chat, "geschichte",
                                    "Nadia wants to leave; Tomas wants her to stay.")
            repo.setze_figur(conn, chat, "Nadia", "the older sister, restless")
            repo.setze_figur(conn, chat, "Tomas", "the younger brother, stubborn")
            repo.schreibe_festlegung(conn, chat, "sonstiges", "Nobody dies.", quelle="befehl")
            for nummer, titel, prosa in ((1, "Last bus", "Nadia waits at the stop."),
                                         (2, "One more night", None)):
                sid = repo.lege_szene_an(conn, chat, nummer, titel, None, None)
                if prosa:
                    repo.aktualisiere_szene(conn, sid, titel, None, None, prosa=prosa)
        repo.setze_phase(conn, chat, phase)
        tokens[phase] = repo.stelle_web_token_sicher(conn, chat)
    conn.commit()
    conn.close()
    return tokens


@pytest.fixture(scope="module")
def dienst():
    tokens = _baue_datenbank()
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="",
                    IT_WORKSHOP="padua-2026")
    umgebung.pop("IT_UX_ENTWURF", None)
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://{BIND}", tokens
    prozess.terminate()
    prozess.wait(timeout=10)


def _oeffne(browser, basis, token, viewport=HANDY):
    seite = browser.new_page(viewport=viewport)
    seite.goto(f"{basis}/g/{token}#stand")
    seite.wait_for_selector("#tab-stand:not([hidden])")
    return seite


@pytest.mark.parametrize("phase", sorted(GRUPPEN))
def test_die_werkbank_ist_reine_anzeige(dienst, phase):
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = _oeffne(browser, basis, tokens[phase])
        elemente = "#tab-stand :is(input, select, textarea, button, [contenteditable])"
        assert seite.locator(elemente).count() == 0
        offen = seite.locator("#tab-stand details.wb-phase[open]")
        assert offen.count() == 1
        assert offen.first.get_attribute("data-wb-phase") == str(phase)
        reihenfolge = seite.eval_on_selector_all(
            "#tab-stand details.wb-phase", "els => els.map(e => e.dataset.wbPhase)")
        assert reihenfolge == [str(n) for n in range(1, 8)]
        browser.close()


@pytest.mark.parametrize("viewport", [HANDY, LAPTOP], ids=["handy", "laptop"])
def test_jeder_sichtbare_text_hat_kontrast(dienst, viewport):
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for token in tokens.values():
            seite = _oeffne(browser, basis, token, viewport)
            seite.wait_for_timeout(500)
            schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
            assert not schlecht, schlecht
            seite.close()
        browser.close()


def test_screenshots(dienst):
    """Telefon und Laptop je Phase 1, 3, 5 -- fuer Birk."""
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for phase, token in sorted(tokens.items()):
            for geraet, viewport in (("handy", HANDY), ("laptop", LAPTOP)):
                seite = _oeffne(browser, basis, token, viewport)
                seite.wait_for_timeout(400)
                seite.screenshot(path=str(SCHUSS / f"werkbank-phase{phase}-{geraet}.png"))
                seite.close()
        browser.close()
    dateien = sorted(SCHUSS.glob("werkbank-phase*.png"))
    assert len(dateien) == 6
    for datei in dateien:
        assert datei.stat().st_size > 5_000, datei
    if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
        SCHUSS_REPO.mkdir(parents=True, exist_ok=True)
        for datei in dateien:
            shutil.copyfile(datei, SCHUSS_REPO / datei.name)
```

- [ ] **Step 2: Den Padua-Übersichtstest auf die Werkbank umstellen**

`tests/e2e/test_web_uebersicht_e2e.py`: den ganzen Test `test_der_arbeitsstand_ohne_doppelten_chatlink_und_mit_lesbarer_festlegung` ersetzen durch

```python
def test_der_arbeitsstand_ohne_doppelten_chatlink_und_mit_lesbarer_festlegung(dienst):
    """Seit der read-only Werkbank (Padua, 03.10.2026): kein Chat-Link, keine
    Formulare; die Festlegungen stehen unter Phase 4 ("Also agreed") und
    bleiben lesbar (Marke und Text kleben nicht aneinander); die Phasennamen
    sind nicht leiser als der Text darunter."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}#stand")
        seite.wait_for_selector("#tab-stand:not([hidden])")
        assert seite.locator('#tab-stand a[href$="/chat"]').count() == 0
        assert seite.locator("#tab-stand [data-feld]").count() == 0
        seite.locator('#tab-stand details.wb-phase[data-wb-phase="4"] > summary').click()
        marke = seite.locator("#tab-stand .festlegung .marke").first.bounding_box()
        text = seite.locator("#tab-stand .festlegung .marke + span").first.bounding_box()
        assert text["x"] >= marke["x"] + marke["width"] + 4
        name, absatz = seite.evaluate(
            """() => [getComputedStyle(document.querySelector('#tab-stand .wb-name')),
                      getComputedStyle(document.querySelector('#tab-stand'))]
                     .map(s => [s.color, s.fontWeight])""")
        assert name[0] == absatz[0], (name, absatz)
        assert int(name[1]) >= 600, name
        browser.close()
```

- [ ] **Step 3: Laufen lassen**

Run: `$E2E -m pytest -q tests/e2e/test_web_werkbank_e2e.py tests/e2e/test_web_uebersicht_e2e.py tests/e2e/test_web_vereint_e2e.py tests/e2e/test_web_gestalt_e2e.py`
Expected: PASS. (`test_web_uebersicht_e2e.py::test_review_screenshots` schreibt Review-Bilder nur nach `/tmp`; die committeten `review-stand-*-nachher.png` bleiben unberührt, solange `IT_SCHUSS_AKTUALISIEREN` nicht gesetzt ist.) Scheitert der Kontrast-Rundgang an einem Werkbank-Element, die Farbe in `_WERKBANK` korrigieren (nur Token-Variablen) und das Paar in `KONTRAST` nachtragen.

- [ ] **Step 4: Screenshots ins Repository**

Run: `IT_SCHUSS_AKTUALISIEREN=1 $E2E -m pytest -q tests/e2e/test_web_werkbank_e2e.py -k screenshots`
Expected: `1 passed`; `ls docs/ux-padua/workbench/` zeigt sechs `werkbank-phase*.png`. Ein Bild ansehen (Read-Tool) und prüfen: Punkte sichtbar, drei Formen unterscheidbar, kein Formular.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_web_werkbank_e2e.py tests/e2e/test_web_uebersicht_e2e.py docs/ux-padua/workbench/
git commit -m "Werkbank im Browser: reine Anzeige, Kontrast, Screenshots Phase 1/3/5

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Modultabelle** — in der Zeile `| \`roadmap.py\` | …` vor dem abschließenden ` |` anhängen:

```
. Seit 03.10.2026 auch `werkbank(lage, aktuelle_phase)`: je Phase ihre Attribute mit `erledigt`/`offen`/`spaeter` (die Quelle der read-only Werkbank in Padua und des Steppers), plus `begriffe_detail` als defensiver Haken
```

- [ ] **Step 2: Einstiegstabelle** — nach der Zeile `| Wo steht Phase 6/7 gerade? | …` einfügen:

```
| Was zeigt die Werkbank in Padua? | `roadmap.werkbank` → `web_daten.werkbank` → `web.werkbank_koerper` |
```

- [ ] **Step 3: Abschnitt „Die Gestaltung"** — direkt nach dem Absatz, der mit „Element: `docs/ux-padua/DESIGN-REVIEW.md`." endet (vor `### Eine Oberfläche je Gruppe`), einfügen:

```markdown
**Die Werkbank ist in Padua reine Anzeige** (03.10.2026, Karte
t_49e7354c, Birk: „Workbench reiner Status-Ausspieler. Änderungen passieren
über Chat."). Profilschalter `[web] workbench_bearbeitbar` (Vorgabe `true`,
`false` nur in `workshop/padua-2026/profil.toml`). Mit `false` ersetzt
`web.werkbank_koerper` den Rumpf von `gruppe_koerper`: EINE Achse, die
sieben Phasen in Reihenfolge, je ein `<details>` mit Zähler („4 of 5", ✓
wenn alles erledigt), aufgeklappt nur die aktuelle Phase, darunter je
Attribut ein Punkt in drei **Formen** — gefüllt mit Haken `--signal`
(erledigt), Ring `--warn` (offen, bis zur aktuellen Phase), gestrichelter
Ring `--text-leise` (später) — und ein `aria-label`; Roadmap-„läuft"
erscheint als offen plus Wort. **Eine Quelle:** `roadmap.werkbank` auf
derselben `lage` wie `roadmap.aus_daten`, `AUFGABEN` unverändert; die
Detailzeilen (Diskussion, je Interview, je Szene Prosa/Überarbeitung/Form,
je Figur Sprechweise) lesen nur, was `web_daten.werkbank` read-only lädt.
`fehlstellen.py` bleibt für `/stand` und Dortmund; in Padua sind die
offenen Punkte die Liste. Kein Formular, kein `_BEARBEITEN_JS`, kein
Probenansicht-/Chat-Link, keine Phasenanzeige im Panel; der Inhalt je
Phase kommt aus denselben Bausteinen wie vorher (`_interview_html`,
`_festlegungen_html` ohne Löschknopf, `_dramaturgie_html`,
`_sprechanteile_html`, `_leitfaden_html` — `pre.leitfaden` muss bleiben,
der Interview-Modus liest ihn). Der Werkbank-POST (`POST /g/<token>`)
antwortet dann **403**; die Chat-POSTs laufen weiter. Der Nonce steht in
Padua im Chat-Panel (`chat_koerper(mit_nonce=True)`); `friskeNonce()` findet
in `teil/stand` keinen mehr, der Chat-Poll hält ihn frisch. Das CSS
(`web_gestalt.css_werkbank`) ist die zehnte Einhängezeile, nur mit dem
Schalter `false`. Ohne Profil und mit `dortmund-2026` bleibt alles
byte-gleich — `tests/test_werkbank_bitgleich.py` gegen
`tests/fixtures/werkbank_vorher_*.html`. Grenze: die Einzelseite
`gruppe_html` (von keiner Route mehr ausgeliefert) zeigt die Punkte
ungestaltet. Screenshots: `docs/ux-padua/workbench/`.
```

- [ ] **Step 4: Zahl der Einhängezeilen** — im Satz „an neun Zeilen eingehaengt (gezaehlt am 03.10.2026)" hinter der schließenden Klammer des Satzes, der mit „…nur mit `[web] dashboard_gestaltet`)." endet, ergänzen: „Dazu seit der read-only Werkbank eine zehnte in `web_vereint.seite` (`css_werkbank()`, nur mit `[web] workbench_bearbeitbar = false`)."

- [ ] **Step 5: Prüfen + Commit**

Run: `$PY -m pytest -q tests/test_web_betrieb_doku.py tests/test_werkbank_bitgleich.py`
Expected: PASS.

```bash
git add AGENTS.md
git commit -m "AGENTS.md: read-only Werkbank in Padua, roadmap.werkbank als Quelle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Volle Suite + Profilprüfung

- [ ] **Step 1: Suite** (in eine Logdatei, aber abwarten)

Run: `$PY -m pytest -q -x --ignore=tests/e2e > /tmp/werkbank-suite.log 2>&1; tail -5 /tmp/werkbank-suite.log` (timeout 600000 ms)
Expected: Summenzeile `N passed …`, kein `failed`/`error` außer den in Task 1 Step 1 notierten vorbestehenden. Bei einem neuen Fehler: Ursache beheben (systematic-debugging), eigenen Commit „Werkbank: <Befund>" machen, Suite neu.

- [ ] **Step 2: Gezielte e2e-Dateien**

Run: `$E2E -m pytest -q tests/e2e/test_web_werkbank_e2e.py tests/e2e/test_web_uebersicht_e2e.py tests/e2e/test_web_vereint_e2e.py tests/e2e/test_web_app_shell_e2e.py`
Expected: PASS.

- [ ] **Step 3: Profile**

Run: `$PY -m scripts.pruefe_profil padua-2026; $PY -m scripts.pruefe_profil dortmund-2026; $PY -m scripts.pruefe_profil --vorgabe`
Expected: drei Zeilen `padua-2026: in Ordnung…`, `dortmund-2026: in Ordnung…`, `<vorgabe-name>: in Ordnung…` (Hinweise erlaubt, keine `FEHLER`).

- [ ] **Step 4:** Die Summenzeile der Suite und die drei Profilzeilen wörtlich in den Abschlussbericht übernehmen. Kein Commit nötig, wenn nichts geändert wurde.

---

### Task 13: Merge `origin/main` und erneut prüfen (kein Push)

- [ ] **Step 1: Holen und mergen**

Run: `git fetch origin && git merge origin/main`
Expected: Merge-Commit oder „Already up to date". Bei Konflikten:
- `interview_theater/web.py` (`gruppe_koerper`, `gruppe_html`) und `interview_theater/web_vereint.py` (`seite`): **die Struktur dieses Plans gewinnt** — die Weiche `if not workshop.workbench_bearbeitbar(): return werkbank_koerper(daten)` am Anfang von `gruppe_koerper`, `bearbeitbar=werkbank_bearbeitbar`, `mit_nonce=not werkbank_bearbeitbar`, das `css_werkbank`-`if`. Änderungen der Parallelkarte t_cc4306db (Kopfleiste/Stepper, z. B. entfernter Probenansicht-Link in `gruppe_html`) **außerhalb** des Werkbank-Panels übernehmen.
- Ändert t_cc4306db den Dortmund-Rumpf (z. B. Probenansicht-Link weg), wird `tests/test_werkbank_bitgleich.py` rot, obwohl Dortmund damit gewollt anders ist: die Vergleichsdateien auf dem gemergten Stand **mit Schalter `true`** neu schreiben (`IT_WERKBANK_VORHER_SCHREIBEN=1 $PY -m pytest -q tests/test_werkbank_bitgleich.py`), vorher per `git diff` der Fixtures prüfen, dass der Unterschied genau die Änderung von t_cc4306db ist, und das im Merge-Commit nennen.
- Liefert t_cc4306db einen eigenen Statuspunkt oder Stepper: dessen Datenquelle auf `roadmap.werkbank` lenken, keine zweite Zustandsregel.

- [ ] **Step 2: Erneut prüfen**

Run: Task 12 Step 1–3 wiederholen.
Expected: wie dort.

- [ ] **Step 3:** Merge-Konfliktlösungen (falls nötig) committen: `git commit` (Merge-Commit-Nachricht nennt die gelösten Dateien und endet mit der Co-Authored-By-Zeile). **Kein `git push`, kein Merge nach `main`.**

---

## ANNAHMEN (gesammelt)

1. `$PY` hat pytest; `$E2E` existiert mit Playwright + Chromium (tests/e2e/README.md). — prüfen: `$PY -m pytest --version`, `$E2E -c "import playwright"`.
2. Die Ausgabe von `seiten()` (Task 1) ist bis auf ISO-Zeitstempel und Token deterministisch. — Task 1 Step 4 (zweimal laufen).
3. `workshop.lade`/`pruefe_profil` lehnen den neuen Schlüssel nicht ab (er steht in `VORGABE_WERTE`). — Task 2 Step 4.
4. `tests/test_sprache_texte.py` Regel 5 verlangt `BLEIBT_DEUTSCH` für `web_gestalt._WERKBANK` und meldet keine weiteren neuen Konstanten. — Task 5 Step 4.
5. `--warn` in Entwurf B ist Mint (`#7fd6a0`) — D6 verlangt `var(--warn)`; ob der Ring neben Amber passt, entscheidet Birk am Screenshot. — Task 10 Step 4.
6. `repo.merke_diskussion_verdichtung` committet nicht selbst; der Test ruft `conn.commit()`. — Task 4.
7. `chat/phase` antwortet 202 (`web_chat._angenommen`). — Task 9 Step 2.
8. Der Chat-Poll hält `#nonce` in Padua frisch; `friskeNonce()` mit leerem `teil/stand` ist harmlos. — nur Code-Lesung (`web_chat.py` ~531/732, `web_vereint.py` ~700-718), nicht im Browser getestet.
9. `tests/test_web_gestalt_einhang.py` zählt Einhängezeilen evtl. fest. — Task 8 Step 4.
10. Weitere Padua-Tests, die Formulare im Arbeitsstand voraussetzen, gibt es außer `test_web_sprache::test_speichermeldungen_kommen_aus_data_attributen` und `test_web_uebersicht_e2e::test_der_arbeitsstand_ohne_doppelten_chatlink_…` nicht (gesucht: `grep -ln padua tests/*.py`). — Task 12 Step 1.
11. `arbeitsstand.szenen_anzahl` wird in Padua befüllt; `web_daten._arbeitsstand` liest die Spalte heute nicht (die bisherige Stückkarte zeigt deshalb immer „offen"). Die Werkbank liest sie über `_werkbank_stand`. — nur Code-Lesung.
12. Ob t_cc4306db beim Merge schon auf `origin/main` liegt, ist offen. — Task 13.

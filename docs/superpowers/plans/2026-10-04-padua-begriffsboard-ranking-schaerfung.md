# Padua Phase 1: Begriffsboard mit Live-Ranking und Schärfungs-Historie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Plan-Karte t_5e484a08, Ausführung auf Karte t_cb2c4678, Branch `wt/t_cb2c4678`, **in diesem Worktree**
(`/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_cb2c4678`). Ziel ist `main` über eine spätere [Merge]-Karte.

**Goal:** Der CoThinker-Tab der Phase 1 (Begriffsboard, nur Padua, Profilschalter `diskussion.aktiv`) sortiert seine Begriffe live um, ohne dass die Liste springt; schärft das Modell einen Begriff („Roboter" → „KI-Roboter"), zeigt dieselbe Zeile den alten Wortlaut durchgestrichen neben dem neuen, während die Begründung die Entwicklung weiter in Prosa erzählt.

**Architecture:** Hybrid (Architekt D1): das Modell liefert je Eintrag ein neues Pflichtfeld `vorheriger_begriff`, der **Code** prüft es gegen das bisherige Board (`begriffsboard.validiere(roh, transkript, bisher)`) und führt daraus die Kette `vorgaenger` (älteste zuerst), die nie im Schema steht. `web._begriffsboard_html` zeigt die Kette als `<del>` und trägt `data-vorgaenger`; ein **eigenes**, nur mit `workshop.diskussion_aktiv()` ausgeliefertes Skript (`web_vereint._BEGRIFFSBOARD_JS`) hängt sich per `MutationObserver` an den unveränderten Panel-Tausch von `ladeBuehne()` und spielt FLIP, samt Erhalt der aufgeklappten „Warum"-Zeilen. Dortmund sieht kein Byte davon.

**Tech Stack:** Python 3.11, Standardbibliothek, SQLite, pytest, Node (nur für die extrahierten JS-Helfer), Playwright (nur `tests/e2e`, eigenes venv).

## Global Constraints

Bindende Entscheidungen (Architekt, Abschnitt D der Karte) — **nicht neu verhandeln**:

- **D1 Datenquelle hybrid.** Neues Pflicht-String-Feld `vorheriger_begriff` im Schema (`""`, wenn keins). Gehalten wird ein Link **nur**, wenn `schluessel(link)` der Schlüssel eines Eintrags in `bisher` ist **und** dieser Schlüssel im neuen Board nicht mehr als eigene Zeile steht **und** er sich vom eigenen Schlüssel des Eintrags unterscheidet. Sonst gilt er als `""`. **Keine** Levenshtein-/Teilstring-Heuristik im Code (Begründung unten). Historie = `vorgaenger: list[str]`, älteste zuerst, **nur vom Code** geführt: ein geprüfter Link ergibt `bisher_eintrag.vorgaenger + [bisher_eintrag.begriff]`; ein Eintrag mit gleichem Schlüssel erbt `vorgaenger` des bisherigen. `lies`/`_eintrag` lesen `vorgaenger` defensiv (fehlt/kaputt → keine Kette). `vorgaenger` steht **nicht** im Schema. Prompt DE + EN: Feldbeschreibung `vorheriger_begriff` und der Satz, dass ein Begriff aus `vorgaenger` nicht wieder als eigene Zeile kommt, obwohl er im (wachsenden) Transkript stehen bleibt; der Board-JSON im Nutzertext trägt `vorgaenger`. **Keine** anderen Verbraucher ändern sich (`detail_fuer`, `detail_zeilen`, `sende_vorschlag`, `arbeitsstand.begriffe_detail`).
- **D2 Darstellung** in `web._begriffsboard_html`: je `<li>` mit Kette `<span class="begriff">NEU</span>` gefolgt von den Vorgängern durchgestrichen, der jüngste direkt neben dem neuen Begriff (`<span class="vorgaenger"><del>KI-Roboter</del> <del>Roboter</del></span>`); Pfeil als CSS, kein `style=`, alles `html.escape`; `data-vorgaenger="<jüngster Vorgänger>"` am `<li>`. `web_daten.begriffsboard` reicht `vorgaenger` durch und lässt `zitat` weiter weg.
- **D3 Live-Ranking:** klassisches FLIP in reinem JS, ohne Bibliothek. Zuordnung alt↔neu über `data-begriff`, ersatzweise `data-vorgaenger`; Neue blenden ein, Entfernte verschwinden. `prefers-reduced-motion: reduce` → keine Bewegung. Auf-/Zu-Zustand jedes `<details>` übersteht den Panel-Tausch (gleiche Zuordnung). Transform nur über `el.style.*` (CSSOM, CSP). Reine Helfer node-getestet wie `tests/test_buehne_nav_js.py`.
- **D4 Dortmund byte-gleich OHNE Fixture-Neuerzeugung:** `tests/test_web_vereint_bitgleich.py` grün gegen die **unveränderte** `tests/fixtures/web_vereint_dortmund_vorher.html`. Neues JS und CSS nur hinter `workshop.diskussion_aktiv()` (Muster `css_stepper()`), **keine** Änderung an `_VEREINT_JS` oder `web._CSS_BUEHNE`. Eine Aufgabe, die die Dortmund-Fixture neu erzeugt, ist ein Planfehler.
- **D5** Phase-4-CoThinker (Bühnenkarten, Nicht-Board-Zweig von `_buehne_html`) bleibt unberührt.
- Karten-Leitplanken: `tests/test_profil_bitgleich.py` grün; bestehende `tests/test_begriffsboard_*.py` grün, besonders `test_html_ist_funktional_mit_data_attributen` und `test_roadmap_traegt_das_board_merkmal_nur_mit_profil`; **kein Zitat im CoThinker** — `vorgaenger` trägt nur Begriffswortlaut, nie einen Transkriptausschnitt (AGENTS.md „Drei Grenzen"); Suite (ohne e2e) Pflicht, Baseline- **und** Schlusszahlen im Abschlussbericht.
- AGENTS.md-Zusagen: SQL nur in `repo.py`/`db.py` (hier kommt keins dazu); Prompts nur Negativbeispiele; kein `style="…"`, kein `on…=` im ausgelieferten HTML; `@keyframes`/`@media` nur in `web_gestalt.css_rahmen()` (deshalb steht die Bewegung im JS, nicht im CSS).
- Code-Bezeichner deutsch wie im Repo, Kommentare in ae/oe/ue wie im umgebenden Code. Nur erfundenes Material in Tests und Screenshots. Nie `.env`/`betrieb/` lesen.
- Branch `wt/t_cb2c4678`, **kein Merge nach main, kein Push** (ein Push auf origin/main ist ≤ 5 min später LIVE). Nie den Haupt-Arbeitsbaum anfassen und **nie** dessen uncommittete Änderungen von Hand herüberkopieren. Ein Commit je Aufgabe, nur die genannten Dateien `git add`-en (nie `git add -A`; `.suite.log`, `.cc-*`, `.superpowers-*` bleiben ungetrackt). Commit-Nachrichten enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testbefehle immer abwarten. Einzige Ausnahme sind die beiden Suite-Läufe (Aufgaben 1 und 7): im Hintergrund in `.suite.log`, **abwarten bis zum Ende, nicht abbrechen**.
- Kein bezahlter Modelllauf (Korpus, Simulation, `pruefe_prompts`) — Geld entscheidet Birk; der Prompt-Zusatz bleibt „ungemessen" (AGENTS.md, Aufgabe 7).

**Abkürzungen in diesem Plan:**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python   # Playwright-venv (tests/e2e/README.md)
```

**Warum keine Ähnlichkeits-Heuristik im Code (D1, für die Akte):** Ein Levenshtein- oder Teilstring-Abgleich („Roboter" steckt in „KI-Roboter") würde auch zwei echte, neue Begriffe verketten („Rolle" / „Rollenbild", „Heim" / „Heimat") — ein solcher Fehler steht durchgestrichen auf einem projizierten Board und behauptet eine Entwicklung, die die Gruppe nie hatte. Das geprüfte Modellfeld kann das per Konstruktion nicht: es zählt nur, wenn es auf einen Begriff zeigt, der wirklich auf dem alten Board stand **und** jetzt verschwunden ist. Der verbleibende Fehlerfall — das Modell vergisst das Feld — ist der harmlose: kein Durchstreichen, die Begründung erzählt die Entwicklung trotzdem (Zusammenführ-Regel im Prompt). Ein fehlender Strich kostet eine Gelegenheit, ein falscher kostet Vertrauen.

## Abweichung von den Architekt-Entscheidungen (mit Beleg)

Keine Entscheidung wird ersetzt; drei Präzisierungen und eine unvermeidliche Testanpassung, je mit Fundstelle:

1. **`vorheriger_begriff` wird nicht gespeichert.** D1 sagt „otherwise it is set to `""`" — das Feld wird in `validiere` gelesen und verbraucht; sein geprüfter Wert lebt als **letztes Element von `vorgaenger`** weiter (genau der Wert, den die Darstellung braucht). Beleg: `tests/test_begriffsboard.py:100-104` (`test_fehlende_felder_werden_aufgefuellt`) und `:136-143` (`test_lies_ist_defensiv`) vergleichen die Eintragsform **wortgleich** mit sieben Schlüsseln; ein gespeichertes `vorheriger_begriff` (und ein immer vorhandenes `vorgaenger: []`) bräche beide. Getestet wird die Prüfung deshalb über das beobachtbare Ergebnis (`vorgaenger` ja/nein).
2. **`vorgaenger` steht nur am Eintrag, wenn die Kette nicht leer ist** (dünn statt `[]`). Gleicher Beleg wie 1.; Nebeneffekt: Boards ohne Schärfung bleiben im gespeicherten JSON, im Nutzertext und im HTML byte-gleich zu heute. Leser nehmen `eintrag.get("vorgaenger") or []`.
3. **Geerbte Ketten werden gegen eigene Zeilen gefiltert.** Steht ein Vorgänger (trotz Prompt) wieder als eigene Zeile auf dem neuen Board, fällt er aus jeder Kette dieses Laufs. Sonst zeigte das Board „KI-Roboter ← ~~Roboter~~" **und** eine Zeile „Roboter" — ein falscher Strich, genau der Fehler, den D1 per Konstruktion ausschließen will. Das ist dieselbe Bedingung wie D1s „key no longer appears as its own entry", angewandt auch auf die geerbte Kette.
4. **Eine bestehende Testerwartung ändert sich:** `tests/test_begriffsboard_lauf.py::test_schema_ist_streng` (`:86-93`) prüft die Feldmenge des Schemas wortgleich auf sieben Namen; D1 verlangt ein achtes Pflichtfeld. Die Erwartung bekommt `"vorheriger_begriff"` dazu — sonst nichts.

Außerdem, ehrlich benannt: „1–3 Wörter" ist **keine Code-Regel**. `_eintrag` (`interview_theater/begriffsboard.py:80-99`) erzwingt nur „genau EIN Begriff nach `begriffe.zerlege`, Whitespace zusammengezogen"; die Wortzahl steht im Prompt. Was ein `vorgaenger`-Element tragen kann, ist per Konstruktion trotzdem eng begrenzt (Aufgabe 2, Schritt „Konstruktion"), aber nicht auf drei Wörter.

## Entscheidungen dieser Planung (D4-Mechanismus)

- **MutationObserver statt Haken in `ladeBuehne()`.** Jeder Haken in `_VEREINT_JS` steht in Dortmunds Seite (die Fixture enthält das ganze Skript) und bräche D4. `ladeBuehne()` (`interview_theater/web_vereint.py:1276-1321`) tauscht im Board-Fall `panel.innerHTML = neu` am `#tab-buehne` — ein `MutationObserver(childList)` auf genau diesem Element sieht genau diesen Tausch und sonst nichts (Nav-Updates liegen eine Ebene tiefer). Die alten Knoten stehen in `removedNodes` und sind noch lesbar (`details.open`), haben aber kein Layout mehr — deshalb hält das Skript die **Lagen** (`offsetTop` je Schlüssel, ignoriert `transform`) aus dem letzten Stand im Speicher und frischt sie bei `toggle` (Capture), `resize`, `hashchange` und nach jedem Tausch auf. Ist das Panel beim Messen verborgen (`offsetParent === null`), gibt es keine Lagen: der nächste Tausch stellt dann nur den Auf-/Zu-Zustand wieder her, ohne Bewegung.
- **Bewegung nur im JS, nicht im CSS.** Eine `transition` im CSS bräuchte ihren Selektor im reduced-motion-Block, und `@media` darf nur in `css_rahmen()` stehen (`web_gestalt.py`, Modulkopf Regel 3) — `css_rahmen()` ist Dortmunds CSS. Also setzt das Skript `style.transition`/`style.transform`/`style.opacity` per CSSOM und fragt vorher `matchMedia('(prefers-reduced-motion: reduce)')`. Das neue CSS (`web_gestalt.css_begriffsboard()`) trägt nur Ruhendes: Pfeil, Farbe, `position: relative` fürs Messen.
- **„Identität" heißt hier „zugeordnet".** Der Panel-Tausch erzeugt neue Knoten; D3 erlaubt „survives or is matched". Bewiesen wird die Zuordnung im Browser an zwei Wirkungen: das geöffnete „Warum" ist nach dem Tausch an der verschobenen bzw. geschärften Zeile offen, und genau diese Zeilen bekamen ein `translateY(…)`.

---

## Dateiübersicht

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/begriffsboard.py` | 0 (Merge), 2, 3 | `_ein_begriff`, `_vorgaenger`, `_verkette`, `validiere(…, bisher)`, `_eintrag`, `_FELDER`/`SCHEMA`, `_lauf_einmal` |
| `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md` | 3 | Feld `vorheriger_begriff`, Satz zu `vorgaenger`, ein Negativpunkt |
| `interview_theater/web.py` | 4 | `_begriffsboard_html`: `<del>`-Kette, `data-vorgaenger` |
| `interview_theater/web_daten.py` | 4 | nur Docstring von `begriffsboard` (Durchreichen ist per `lies` schon gegeben, Test belegt es) |
| `interview_theater/web_gestalt.py` | 5 | `css_begriffsboard()` (neu) |
| `interview_theater/web_vereint.py` | 5 | `_BEGRIFFSBOARD_JS` (neu), bedingte Einhängung in `seite()` |
| `tests/test_begriffsboard_lauf.py` | 3 | eine Erwartung in `test_schema_ist_streng` |
| `tests/test_begriffsboard_schaerfung.py` (neu) | 2, 3 | Kern + Lauf + Prompt |
| `tests/test_begriffsboard_schaerfung_web.py` (neu) | 4 | Darstellung, `web_daten` |
| `tests/test_begriffsboard_flip.py` (neu) | 5 | Node-Tests der Helfer, Skriptregeln, Gating |
| `tests/e2e/test_web_begriffsboard_ranking_e2e.py` (neu) | 6 | Browser + Handy-Screenshot |
| `docs/web-begriffsboard/ranking-2026-10-04.png` (neu) | 6 | der Screenshot für Birk (nur erfundenes Material) |
| `AGENTS.md` | 7 | Modultabelle, „Wo man anfängt", Gestaltung, Übergaben |

**Nicht** angefasst: `_VEREINT_JS`, `web._CSS_BUEHNE`, `web_gestalt.css_rahmen()`, `tests/fixtures/*`, `detail_fuer`/`detail_zeilen`/`sende_vorschlag`/`schreibe_detail`, der Phase-4-Zweig von `_buehne_html`, `db.py`/`repo.py`.

---

### Task 0: Vorbedingung — Schwelle 600 und Zusammenführ-Regel müssen auf `main` committet sein, dann `main` mergen

Die Karte nennt beides „schon in main". Am 04.10.2026 14:33 (Architekt) und beim Schreiben dieses Plans (`git grep … main` ohne Treffer) standen beide **nur uncommittet im Haupt-Arbeitsbaum**. Alle späteren Aufgaben, die `begriffsboard.py` oder die Prompts ändern, sind gegen den Stand **nach** diesem Merge geschrieben (Funktionsnamen statt Zeilennummern).

**Files:** keine eigenen Änderungen (nur der Merge-Commit).

**Interfaces:**
- Produces: `begriffsboard.min_zeichen()`, `begriffsboard.VORGABE_MIN_ZEICHEN = 600`, der Absatz „Zusammenfuehren statt verdoppeln" (DE) / „Merge instead of duplicating" (EN) in den beiden Prompt-Dateien — die Basis, an die Aufgabe 3 anhängt.

- [ ] **Step 1: Prüfen, ob beides auf `main` steht**

```bash
git -C /mnt/HC_Volume_106183673/projekte/interview-theater grep -n "IT_BEGRIFFSBOARD_MIN_ZEICHEN" main -- interview_theater/begriffsboard.py
git -C /mnt/HC_Volume_106183673/projekte/interview-theater grep -n "Zusammenfuehren statt verdoppeln" main -- interview_theater/prompts/begriffsboard.md
git -C /mnt/HC_Volume_106183673/projekte/interview-theater grep -n "Merge instead of duplicating" main -- interview_theater/sprachen/en/prompts/begriffsboard.md
```

Expected: je mindestens eine Trefferzeile, z. B. `main:interview_theater/begriffsboard.py:<n>:    roh = (os.environ.get("IT_BEGRIFFSBOARD_MIN_ZEICHEN") or "").strip()`.

- [ ] **Step 2: Bei einem Fehltreffer: STOPP**

Fehlt auch nur eine Zeile: **nichts** weiter tun, nichts kopieren. Die Karte t_cb2c4678 wird blockiert, `kind=dependency`, Text: „Schwelle/Prompt-Regel noch nicht auf main committet". Ende der Ausführung.

- [ ] **Step 3: `main` in den Branch mergen**

```bash
git status --short            # Expected: leer (sauberer Baum)
git merge --no-edit main
git log --oneline -1          # Expected: ein Merge-Commit "Merge branch 'main' into wt/t_cb2c4678" (oder Fast-forward)
git rev-parse HEAD            # diese SHA als BASIS im Abschlussbericht notieren
```

Expected: kein Konflikt (der Branch trägt bis hierher nur diese Plandatei). Bei einem Konflikt: abbrechen (`git merge --abort`) und die Karte mit dem Konflikt-Output blockieren.

- [ ] **Step 4: Stand nach dem Merge belegen**

```bash
grep -n "def min_zeichen\|VORGABE_MIN_ZEICHEN = 600" interview_theater/begriffsboard.py
grep -n "Zusammenfuehren statt verdoppeln" interview_theater/prompts/begriffsboard.md
grep -n "Merge instead of duplicating" interview_theater/sprachen/en/prompts/begriffsboard.md
$PY -m pytest tests/test_begriffsboard_lauf.py tests/test_begriffsboard_web.py tests/test_brainstorm.py -q -p no:cacheprovider
```

Expected: drei Trefferzeilen, danach `… passed` ohne `failed`.

Kein eigener Commit (der Merge ist der Commit).

---

### Task 1: Baseline der Suite

**Files:** keine (`.suite.log` wird **nicht** committet).

- [ ] **Step 1: Suite im Hintergrund starten und bis zum Ende abwarten**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e > .suite.log 2>&1; echo EXIT $?
```

Der Lauf dauert 5–15 Minuten. Im Hintergrund starten (Shell-Werkzeug mit Hintergrund-Option), auf die Fertigmeldung warten, **nicht abbrechen**, währenddessen keine Codeänderung.

- [ ] **Step 2: Zusammenfassung festhalten**

```bash
tail -n 3 .suite.log
cp .suite.log .suite-baseline.log
```

Expected: eine Zeile der Form `NNNN passed, NN skipped[, N failed] in …s` und `EXIT 0` (oder `EXIT 1`, falls schon vorher Tests rot sind). Diese Zeile wörtlich für den Abschlussbericht notieren. Sind schon in der Baseline Tests rot: ihre Namen (`grep -E "^FAILED|^ERROR" .suite.log`) notieren — sie sind dann **nicht** Folge dieser Karte und werden im Bericht so benannt.

Kein Commit.

---

### Task 2: Kern — `vorgaenger` lesen, `vorheriger_begriff` prüfen, Kette führen

**Files:**
- Modify: `interview_theater/begriffsboard.py` (`_eintrag` und `validiere`; neue Helfer `_ein_begriff`, `_vorgaenger`, `_verkette` direkt über `_eintrag` bzw. über `validiere`; Moduldocstring um einen Absatz)
- Test: `tests/test_begriffsboard_schaerfung.py` (neu)

**Interfaces:**
- Consumes: `begriffsboard.schluessel(text) -> str`, `begriffe.zerlege(text) -> list[str]`, `zitat.pruefe`.
- Produces:
  - `begriffsboard._ein_begriff(roh) -> str | None` — dieselbe Einzelbegriff-Regel für `begriff` **und** jedes Kettenelement.
  - `begriffsboard._vorgaenger(roh, eigener: str) -> list[str]` — defensives Lesen einer Kette.
  - `begriffsboard.validiere(roh, transkript: str, bisher: list[dict] | None = None) -> list[dict]` — ohne `bisher` exakt das heutige Verhalten.
  - Eintragsform: die sieben bisherigen Schlüssel, **plus** `"vorgaenger": list[str]` nur wenn nicht leer (älteste zuerst). `vorheriger_begriff` steht nie im Ergebnis.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_begriffsboard_schaerfung.py`:

```python
"""Karte t_cb2c4678, Aufgabe 2: Schaerfung eines Begriffs -- der Code prueft
``vorheriger_begriff`` gegen das bisherige Board und fuehrt ``vorgaenger``
(D1). Nur erfundenes Material."""

import json

import pytest

from interview_theater import begriffsboard

TRANSKRIPT = (
    "Wir wollen einen Roboter. Nein, einen KI-Roboter, der redet. "
    "Einen sozialen KI-Roboter eigentlich. Und Heimat, Heimat ist wichtig."
)


def _z(begriff, vorher="", **kw):
    zeile = {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": "",
             "zitat": "", "doppelbedeutung": "", "status": "kandidat",
             "vorheriger_begriff": vorher}
    zeile.update(kw)
    return zeile


def _bisher(*zeilen):
    """Ein bisheriges Board, wie ``aktuelles`` es liefert (ueber ``lies``)."""
    return begriffsboard.lies(json.dumps(list(zeilen)))


def _ketten(ergebnis):
    return {e["begriff"]: e.get("vorgaenger") for e in ergebnis}


# -- Pruefung des Links (D1) ---------------------------------------------------

def test_gueltiger_link_wird_zur_kette():
    neu = begriffsboard.validiere([_z("KI-Roboter", "Roboter")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": ["Roboter"]}


def test_erfundener_link_wird_verworfen():
    neu = begriffsboard.validiere([_z("KI-Roboter", "Maschine")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": None}


def test_link_auf_einen_noch_stehenden_begriff_wird_verworfen():
    neu = begriffsboard.validiere(
        [_z("KI-Roboter", "Heimat"), _z("Heimat")], TRANSKRIPT,
        bisher=_bisher(_z("Roboter"), _z("Heimat")),
    )
    assert _ketten(neu) == {"KI-Roboter": None, "Heimat": None}


def test_link_auf_sich_selbst_wird_verworfen():
    neu = begriffsboard.validiere([_z("Roboter", "roboter")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"Roboter": None}


@pytest.mark.parametrize("link", [None, 5, ["Roboter"], {"x": 1}, "", "   "])
def test_kaputter_link_ist_kein_link_und_kein_absturz(link):
    neu = begriffsboard.validiere([_z("KI-Roboter", link)], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": None}


def test_ohne_feld_und_ohne_bisher_wie_bisher():
    """Abwaertskompatibel: alte Aufrufer und alte Modellantworten."""
    zeile = _z("Heimat")
    del zeile["vorheriger_begriff"]
    assert begriffsboard.validiere([zeile], TRANSKRIPT) == [
        {"begriff": "Heimat", "nennungen": 1, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
    ]


# -- Kette ueber mehrere Laeufe ----------------------------------------------

def test_kette_ueber_zwei_laeufe_aelteste_zuerst():
    lauf1 = begriffsboard.validiere([_z("Roboter")], TRANSKRIPT)
    lauf2 = begriffsboard.validiere([_z("KI-Roboter", "Roboter")], TRANSKRIPT, bisher=lauf1)
    lauf3 = begriffsboard.validiere([_z("sozialen KI-Roboter", "KI-Roboter")], TRANSKRIPT,
                                    bisher=lauf2)
    assert _ketten(lauf3) == {"sozialen KI-Roboter": ["Roboter", "KI-Roboter"]}


def test_gleicher_schluessel_erbt_die_kette_ohne_dass_das_modell_sie_wiederholt():
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]))
    neu = begriffsboard.validiere([_z("ki-roboter")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"ki-roboter": ["Roboter"]}


def test_zusammenfuehren_zweier_alter_zeilen_haengt_die_aufgenommene_an():
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]), _z("Heimat"))
    neu = begriffsboard.validiere([_z("KI-Roboter", "Heimat")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"KI-Roboter": ["Roboter", "Heimat"]}


def test_kein_strich_ueber_etwas_das_wieder_als_eigene_zeile_steht():
    """Praezisierung 3 im Plankopf: ein Vorgaenger, der als eigene Zeile
    zurueckkommt, faellt aus jeder Kette -- sonst stuende er zweimal da."""
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]))
    neu = begriffsboard.validiere([_z("KI-Roboter"), _z("Roboter")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"KI-Roboter": None, "Roboter": None}


# -- Konstruktion: eine Kette traegt nie mehr als einen Begriff ----------------

def test_kette_traegt_den_wortlaut_des_bisherigen_boards_nicht_den_des_modells():
    neu = begriffsboard.validiere([_z("KI-Roboter", "  ROBOTER ")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": ["Roboter"]}


def test_ein_zitat_als_link_kommt_nie_in_die_kette():
    neu = begriffsboard.validiere(
        [_z("KI-Roboter", "Roboter, und dann sagte sie: ich will nach Hause")],
        TRANSKRIPT, bisher=_bisher(_z("Roboter")),
    )
    assert _ketten(neu) == {"KI-Roboter": None}


def test_eine_vom_modell_mitgeschickte_kette_wird_ignoriert():
    """``vorgaenger`` steht nicht im Schema; kommt es trotzdem (anderer
    Anbieterweg), schreibt die Kette allein der Code."""
    neu = begriffsboard.validiere([_z("Heimat", vorgaenger=["Erfunden", "Auch erfunden"])],
                                  TRANSKRIPT)
    assert _ketten(neu) == {"Heimat": None}


def test_jedes_kettenelement_ist_ein_frueherer_begriff_des_boards():
    """Die Zusage als Eigenschaft: nach beliebig vielen Laeufen ist jedes
    Kettenelement wortgleich ein ``begriff``, der in einem frueheren Lauf
    auf dem Board stand -- nie ein Modelltext."""
    gesehen = set()
    board = []
    laeufe = [
        [_z("Roboter"), _z("Heimat")],
        [_z("KI-Roboter", "Roboter"), _z("Heimat", "Roboter, und mehr")],
        [_z("sozialen KI-Roboter", "KI-Roboter"), _z("Heimat", "Heimat")],
    ]
    for roh in laeufe:
        board = begriffsboard.validiere(roh, TRANSKRIPT, bisher=board)
        for eintrag in board:
            for v in eintrag.get("vorgaenger", []):
                assert v in gesehen, v
                assert begriffsboard._ein_begriff(v) == v
        gesehen |= {e["begriff"] for e in board}


# -- Defensives Lesen (lies / _eintrag) ----------------------------------------

def test_lies_eines_alten_boards_ohne_feld():
    assert begriffsboard.lies('[{"begriff": "Mut"}]') == [
        {"begriff": "Mut", "nennungen": 0, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
    ]


@pytest.mark.parametrize("roh, erwartet", [
    ('"Roboter"', None),                              # keine Liste
    ('null', None),
    ('[5, null, {"a": 1}, "Roboter"]', ["Roboter"]),  # nur Zeichenketten
    ('["Heimat, Grenze", "Roboter"]', ["Roboter"]),   # Listentrenner fliegt
    ('["Roboter", "roboter", "KI-Roboter"]', ["Roboter", "KI-Roboter"]),  # doppelt
    ('["Mut", "Roboter"]', ["Roboter"]),              # der eigene Begriff fliegt
    ('["  Roboter  "]', ["Roboter"]),                 # Whitespace zusammengezogen
])
def test_lies_liest_vorgaenger_defensiv(roh, erwartet):
    eintrag = begriffsboard.lies(f'[{{"begriff": "Mut", "vorgaenger": {roh}}}]')[0]
    assert eintrag.get("vorgaenger") == erwartet
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_schaerfung.py -q -p no:cacheprovider`
Expected: FAIL — u. a. `TypeError: validiere() got an unexpected keyword argument 'bisher'` und `AttributeError: … has no attribute '_ein_begriff'`; `test_lies_eines_alten_boards_ohne_feld` und `test_ohne_feld_und_ohne_bisher_wie_bisher` sind schon grün (Abwärtskompatibilität), der Rest rot.

- [ ] **Step 3: Helfer und `_eintrag`** — in `interview_theater/begriffsboard.py` `_eintrag` ersetzen durch:

```python
def _ein_begriff(roh) -> str | None:
    """EIN Begriff in fester Form (Whitespace zusammengezogen), oder None,
    wenn ``roh`` leer ist oder einen Listentrenner traegt -- er zerfiele beim
    Speichern (``begriffe.zerlege``) in zwei. Dieselbe Regel fuer ``begriff``
    und fuer jedes Element von ``vorgaenger``."""
    teile = begriffe_modul.zerlege(" ".join(str(roh or "").split()))
    return teile[0] if len(teile) == 1 else None


def _vorgaenger(roh, eigener: str) -> list[str]:
    """Eine Vorgaengerkette defensiv gelesen (Karte t_cb2c4678, D1): nur
    Zeichenketten, die als EIN Begriff durchgehen, ohne den eigenen Begriff,
    ohne Doppelte (erste Nennung gilt), aelteste zuerst. Fehlt sie oder ist
    sie keine Liste: keine Kette."""
    if not isinstance(roh, list):
        return []
    kette: list[str] = []
    gesehen = {schluessel(eigener)}
    for element in roh:
        begriff = _ein_begriff(element) if isinstance(element, str) else None
        if begriff is None or schluessel(begriff) in gesehen:
            continue
        gesehen.add(schluessel(begriff))
        kette.append(begriff)
    return kette


def _eintrag(zeile) -> dict | None:
    """Eine Zeile in die feste Form -- ohne Transkriptpruefung (die macht
    ``validiere``). None, wenn sie keinen brauchbaren Begriff traegt.
    ``vorgaenger`` steht nur da, wenn die Kette nicht leer ist: ein Board
    ohne Schaerfung bleibt Zeichen fuer Zeichen, wie es war."""
    if not isinstance(zeile, dict):
        return None
    begriff = _ein_begriff(zeile.get("begriff"))
    if begriff is None:
        return None
    status = str(zeile.get("status") or "").strip().casefold()
    eintrag = {
        "begriff": begriff,
        "nennungen": max(0, _ganzzahl(zeile.get("nennungen"))),
        "zustimmung": min(ZUSTIMMUNG_MAX, max(ZUSTIMMUNG_MIN, _ganzzahl(zeile.get("zustimmung")))),
        "begruendung": str(zeile.get("begruendung") or "").strip(),
        "zitat": str(zeile.get("zitat") or "").strip(),
        "doppelbedeutung": str(zeile.get("doppelbedeutung") or "").strip(),
        "status": status if status in STATUS else "kandidat",
    }
    kette = _vorgaenger(zeile.get("vorgaenger"), begriff)
    if kette:
        eintrag["vorgaenger"] = kette
    return eintrag
```

- [ ] **Step 4: `_verkette` und `validiere`** — `validiere` ersetzen durch:

```python
def _verkette(neu: list[dict], links: list, bisher: list[dict]) -> None:
    """Fuehrt ``vorgaenger`` (D1, Karte t_cb2c4678) -- allein der Code.

    Ein Eintrag mit einem Schluessel aus ``bisher`` erbt dessen Kette. Ein
    ``vorheriger_begriff`` des Modells zaehlt NUR, wenn er auf einen Eintrag
    aus ``bisher`` zeigt, der im neuen Board nicht mehr als eigene Zeile
    steht und nicht der Eintrag selbst ist; dann wird dessen Kette plus
    dessen Begriff angehaengt -- im Wortlaut des BISHERIGEN Boards, nie im
    Wortlaut des Modells. Alles andere ist kein Link: ein vergessenes Feld
    heisst "kein Strich", nie "ein falscher". Zuletzt faellt aus jeder Kette,
    was als eigene Zeile im neuen Board steht (sonst stuende es zweimal da)."""
    alt = {schluessel(e["begriff"]): e for e in bisher}
    eigene = {schluessel(e["begriff"]) for e in neu}
    for eintrag, link in zip(neu, links):
        k = schluessel(eintrag["begriff"])
        kette = list(alt[k].get("vorgaenger") or []) if k in alt else []
        lk = schluessel(link) if isinstance(link, str) else ""
        if lk and lk != k and lk in alt and lk not in eigene:
            kette += list(alt[lk].get("vorgaenger") or []) + [alt[lk]["begriff"]]
        kette = [v for v in _vorgaenger(kette, eintrag["begriff"]) if schluessel(v) not in eigene]
        if kette:
            eintrag["vorgaenger"] = kette


def validiere(roh, transkript: str, bisher: list[dict] | None = None) -> list[dict]:
    """Die Modellantwort gegen das Transkript (D3). Nichts erfinden: nur
    Begriffe, die im Transkript stehen; Zitate nur woertlich. Mit ``bisher``
    (dem geltenden Board vor diesem Lauf) zusaetzlich die Schaerfungskette
    (``_verkette``); ohne ``bisher`` genau das Verhalten von vorher."""
    if not isinstance(roh, list):
        return []
    ergebnis: list[dict] = []
    links: list = []
    gesehen: set[str] = set()
    for zeile in roh:
        eintrag = _eintrag(zeile)
        if eintrag is None or not _steht_im_transkript(eintrag["begriff"], transkript):
            continue
        k = schluessel(eintrag["begriff"])
        if k in gesehen:
            continue
        gesehen.add(k)
        if eintrag["zitat"] and not zitat.pruefe(eintrag["zitat"], transkript):
            eintrag["zitat"] = ""
        # Die Kette schreibt allein der Code -- eine mitgeschickte faellt weg.
        eintrag.pop("vorgaenger", None)
        links.append(zeile.get("vorheriger_begriff"))
        ergebnis.append(eintrag)
        if len(ergebnis) >= HOECHSTENS:
            break
    _verkette(ergebnis, links, bisher or [])
    return ergebnis
```

Im Moduldocstring hinter dem Absatz „**Validiert wird im Code, nicht im Prompt**" ergänzen:

```text
**Schaerfung (Karte t_cb2c4678):** das Modell nennt je Eintrag
``vorheriger_begriff`` (den ersetzten Begriff oder ""), der Code prueft es
gegen das bisherige Board und fuehrt daraus ``vorgaenger`` (aelteste
zuerst, nur am Eintrag, wenn nicht leer). Die Kette ist nie Modelltext:
jedes Element ist der Wortlaut eines frueheren ``begriff`` dieses Boards.
```

- [ ] **Step 5: Konstruktion — warum eine Kette nie mehr als einen Begriff trägt** (nur prüfen, kein Code)

Jedes Kettenelement entsteht an genau einer Stelle: `_verkette` hängt `alt[lk]["begriff"]` an, und `alt` ist `bisher` = `aktuelles()` = `lies()` → jeder `begriff` dort hat `_ein_begriff` (ein Begriff, kein Listentrenner) und beim Schreiben `_steht_im_transkript` passiert und stand selbst schon auf dem Board. Der Modellwert `vorheriger_begriff` **wählt** nur einen Schlüssel aus `alt` aus; gespeichert wird nie er selbst. Beim Zurücklesen filtert `_vorgaenger` jedes Element erneut mit `_ein_begriff`. `vorgaenger` steht nicht im Schema, und eine mitgeschickte Kette wirft `validiere` weg. Die Tests `test_kette_traegt_den_wortlaut_des_bisherigen_boards_nicht_den_des_modells`, `test_ein_zitat_als_link_kommt_nie_in_die_kette`, `test_eine_vom_modell_mitgeschickte_kette_wird_ignoriert` und `test_jedes_kettenelement_ist_ein_frueherer_begriff_des_boards` halten das fest. Grenze (Plankopf): die Wortzahl ist nicht im Code begrenzt.

- [ ] **Step 6: Grün laufen lassen, Nachbarn mit**

Run: `$PY -m pytest tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_vorschlag.py tests/test_begriffe_detail_wege.py -q -p no:cacheprovider`
Expected: `… passed`, kein `failed`. (Insbesondere `test_fehlende_felder_werden_aufgefuellt` und `test_lies_ist_defensiv` unverändert grün.)

- [ ] **Step 7: Commit**

```bash
git add interview_theater/begriffsboard.py tests/test_begriffsboard_schaerfung.py
git commit -m "Begriffsboard: vorheriger_begriff pruefen, vorgaenger-Kette im Code fuehren (t_cb2c4678, Aufgabe 2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Schema, Lauf und Prompt (DE + EN)

**Files:**
- Modify: `interview_theater/begriffsboard.py` (`_FELDER`, `SCHEMA`, `_lauf_einmal`, Kommentar über `SCHEMA`)
- Modify: `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md`
- Modify: `tests/test_begriffsboard_lauf.py` (nur `test_schema_ist_streng`, Plankopf Punkt 4)
- Test: `tests/test_begriffsboard_schaerfung.py` (erweitern)

**Interfaces:**
- Consumes: `validiere(roh, transkript, bisher=…)` aus Aufgabe 2; `_nutzertext(transkript, board)` (unverändert — es dumpt `sortiert(board)` mit allen Feldern, also auch `vorgaenger`).
- Produces: `SCHEMA["properties"]["board"]["items"]["required"]` enthält `"vorheriger_begriff"` (Typ `string`); `_lauf_einmal` speichert Boards mit Kette.

- [ ] **Step 1: Prüfer-Baseline des englischen Prompts** (vor jeder Änderung)

Run: `$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/begriffsboard.md`
Expected: letzte Zeile `0 Treffer`. ANNAHME: so ist es nach dem Merge aus Aufgabe 0; steht dort schon ein Treffer, ist er nicht Folge dieser Karte — notieren und im Bericht nennen.

- [ ] **Step 2: Failing tests anhängen** — an `tests/test_begriffsboard_schaerfung.py`:

```python
# -- Aufgabe 3: Schema, Nutzertext, Lauf, Prompt -------------------------------

from pathlib import Path  # noqa: E402

from interview_theater import db, einstellungen, repo, workshop  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
CHAT = 1


def test_schema_verlangt_vorheriger_begriff_als_string():
    zeile = begriffsboard.SCHEMA["properties"]["board"]["items"]
    assert "vorheriger_begriff" in zeile["required"]
    assert zeile["properties"]["vorheriger_begriff"] == {"type": "string"}
    assert "vorgaenger" not in zeile["properties"]


def test_nutzertext_zeigt_dem_modell_die_kette():
    """Sofort gruen (der Dump traegt alle Felder) -- ein Waechter: ohne die
    Kette im Nutzertext spaltete das Modell "Roboter" im naechsten Lauf
    wieder ab, weil das Wort weiter im Transkript steht."""
    board = begriffsboard.lies(json.dumps([_z("KI-Roboter", vorgaenger=["Roboter"])]))
    text = begriffsboard._nutzertext("Roboter. KI-Roboter.", board)
    assert '"vorgaenger": ["Roboter"]' in text
    assert "vorheriger_begriff" not in text


class _KLM:
    def __init__(self):
        self.boards = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        return {"board": self.boards.pop(0)}


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Testgruppe")
    aid = repo.lege_aufnahme_an(conn, CHAT, 10, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund="pause")
    repo.setze_transkript(conn, aid, TRANSKRIPT)
    repo.setze_status(conn, aid, "fertig")
    einst = einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )
    return conn, einst, aid


def test_lauf_fuehrt_die_kette_ueber_drei_laeufe(lauf):
    conn, einst, aid = lauf
    klm = _KLM()
    klm.boards = [
        [_z("Roboter")],
        [_z("KI-Roboter", "Roboter")],
        [_z("sozialen KI-Roboter", "KI-Roboter")],
    ]
    for _ in range(3):
        begriffsboard._lauf_einmal(conn, klm, einst, CHAT, aid)
    assert _ketten(begriffsboard.aktuelles(conn, CHAT)) == {
        "sozialen KI-Roboter": ["Roboter", "KI-Roboter"],
    }


@pytest.mark.parametrize("pfad", [
    "interview_theater/prompts/begriffsboard.md",
    "interview_theater/sprachen/en/prompts/begriffsboard.md",
])
def test_prompt_nennt_feld_und_kettenregel(pfad):
    text = (WURZEL / pfad).read_text(encoding="utf-8")
    assert "vorheriger_begriff" in text
    assert "``vorgaenger``" in text
```

- [ ] **Step 3: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_schaerfung.py -q -p no:cacheprovider`
Expected: FAIL in `test_schema_verlangt_vorheriger_begriff_als_string` (`AssertionError`), `test_lauf_fuehrt_die_kette_ueber_drei_laeufe` (Kette `None`, weil `_lauf_einmal` kein `bisher` reicht) und beiden `test_prompt_nennt_feld_und_kettenregel`; `test_nutzertext_zeigt_dem_modell_die_kette` grün (Wächter, siehe Docstring).

- [ ] **Step 4: Schema** — in `begriffsboard.py`:

```python
_FELDER = ("begriff", "nennungen", "zustimmung", "begruendung", "zitat",
           "doppelbedeutung", "status", "vorheriger_begriff")
```

In `SCHEMA[...]["properties"]` hinter `"status": {"type": "string"},` einfügen:

```python
                    "vorheriger_begriff": {"type": "string"},
```

Den Kommentar über `SCHEMA` um einen Satz ergänzen:

```python
#: ``vorheriger_begriff`` (Karte t_cb2c4678) ist Pflicht und darf "" sein;
#: ``validiere`` prueft es gegen das bisherige Board. ``vorgaenger`` steht
#: bewusst NICHT hier: die Kette fuehrt allein der Code. Beide Namen sind
#: fuer ``scripts/pruefe_sprache.py`` unkritisch (snake_case faellt dort
#: heraus, "vorgaenger" steht in keiner Liste).
```

- [ ] **Step 5: Lauf** — in `_lauf_einmal` die Zeile mit `validiere(` ersetzen durch:

```python
    neu = validiere(ergebnis.get("board") if isinstance(ergebnis, dict) else None, transkript,
                    bisher=bisher)
```

(`bisher = aktuelles(conn, chat_id)` steht dort schon, vor dem Modellaufruf.)

- [ ] **Step 6: Bestehende Schema-Erwartung nachziehen** — in `tests/test_begriffsboard_lauf.py::test_schema_ist_streng` die Menge ersetzen:

```python
    assert set(zeile["required"]) == set(zeile["properties"]) == {
        "begriff", "nennungen", "zustimmung", "begruendung", "zitat", "doppelbedeutung", "status",
        "vorheriger_begriff",
    }
```

- [ ] **Step 7: Prompt DE** — `interview_theater/prompts/begriffsboard.md`:

(a) In der Feldliste hinter dem `- status: …`-Punkt (vor der Leerzeile) einfügen:

```text
- vorheriger_begriff: wenn dieser Eintrag einen Eintrag des bisherigen
  Boards ersetzt (Zusammenfuehren, siehe unten), genau dessen ``begriff``
  aus dem bisherigen Board; sonst "".
```

(b) Direkt hinter dem Absatz „Zusammenfuehren statt verdoppeln: …" (aus Aufgabe 0) als eigenen Absatz:

```text
Wer ersetzt, nennt den ersetzten Eintrag in ``vorheriger_begriff`` -- im
Wortlaut des bisherigen Boards. Ein Begriff, der im bisherigen Board in der
Liste ``vorgaenger`` eines Eintrags steht, ist schon zusammengefuehrt: nimm
ihn nicht wieder als eigenen Eintrag auf, auch wenn er weiter im Transkript
steht -- das Transkript waechst, das alte Wort bleibt darin stehen.
``vorgaenger`` schreibst du nie selbst; diese Liste fuehrt das Programm.
```

(c) In „Nicht so:" vor `- Kein Text ausserhalb des JSON.`:

```text
- Kein ``vorheriger_begriff``, der nicht wortgleich als ``begriff`` im
  bisherigen Board steht.
```

- [ ] **Step 8: Prompt EN** — `interview_theater/sprachen/en/prompts/begriffsboard.md`, an denselben drei Stellen:

(a)

```text
- vorheriger_begriff: when this entry replaces an entry of the board so far
  (merge, see below), exactly that entry's ``begriff`` from the board so
  far; otherwise "".
```

(b) hinter „Merge instead of duplicating: …":

```text
When you replace an entry, name the replaced one in ``vorheriger_begriff``
-- worded as on the board so far. A term that the board so far lists under
an entry's ``vorgaenger`` has already been merged: do not add it back as an
entry of its own, even if it still appears in the transcript -- the
transcript keeps growing and the old word stays in it. You never write
``vorgaenger`` yourself; the program keeps that list.
```

(c) vor `- No text outside the JSON.`:

```text
- No ``vorheriger_begriff`` that is not worded exactly like a ``begriff``
  on the board so far.
```

- [ ] **Step 9: Grün laufen lassen + Sprachprüfer**

```bash
$PY -m pytest tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard.py tests/test_begriffsboard_mithoeren.py -q -p no:cacheprovider
$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/begriffsboard.md
grep -n "begriffsboard" scripts/prompt_schnappschuss.py
```

Expected: `… passed` ohne `failed`; Prüfer `0 Treffer`; `grep` ohne Ausgabe (ANNAHME: der Begriffsboard-Prompt steht nicht im Dortmund-Schnappschuss — gibt es doch einen Treffer, muss in Aufgabe 7 `tests/test_profil_bitgleich.py` trotzdem grün sein, weil der Prompt nur unter `padua-2026` gelesen wird; ist er rot, STOPP und berichten statt den Schnappschuss neu zu erzeugen).

- [ ] **Step 10: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/prompts/begriffsboard.md interview_theater/sprachen/en/prompts/begriffsboard.md tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard_lauf.py
git commit -m "Begriffsboard: Schema-Feld vorheriger_begriff, Lauf reicht bisher, Prompt DE/EN (t_cb2c4678, Aufgabe 3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Darstellung — `<del>`-Kette und `data-vorgaenger`

**Files:**
- Modify: `interview_theater/web.py` (`_begriffsboard_html`, Docstring)
- Modify: `interview_theater/web_daten.py` (nur Docstring von `begriffsboard`: „reicht `vorgaenger` durch")
- Test: `tests/test_begriffsboard_schaerfung_web.py` (neu)

**Interfaces:**
- Consumes: Eintragsform aus Aufgabe 2 (`vorgaenger` optional, älteste zuerst).
- Produces (Markup-Vertrag für Aufgabe 5/6): `<li data-begriff="…" data-status="…" data-zustimmung="…" data-nennungen="…"[ data-vorgaenger="<jüngster>"][ data-top="1"]><span class="begriff">…</span>[<span class="vorgaenger"><del>jüngster</del> … <del>ältester</del></span>][<details>…</details>]</li>` in `<ol class="begriffsboard">`.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_begriffsboard_schaerfung_web.py`:

```python
"""Karte t_cb2c4678, Aufgabe 4: die Schaerfung im CoThinker (D2). Nur
erfundenes Material."""

import json
import re
import sqlite3

import pytest

from interview_theater import db, repo, web, web_daten

CHAT = 1


def _e(begriff, **kw):
    eintrag = {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": "",
               "doppelbedeutung": "", "status": "kandidat"}
    eintrag.update(kw)
    return eintrag


def test_kette_steht_durchgestrichen_der_juengste_neben_dem_neuen():
    html_ = web._begriffsboard_html([_e("sozialer KI-Roboter",
                                        vorgaenger=["Roboter", "KI-Roboter"])])
    assert ('<span class="begriff">sozialer KI-Roboter</span>'
            '<span class="vorgaenger"><del>KI-Roboter</del> <del>Roboter</del></span>') in html_
    assert re.search(r'<li data-begriff="sozialer KI-Roboter"[^>]*'
                     r' data-vorgaenger="KI-Roboter"[^>]*>', html_)


def test_kette_wird_maskiert():
    html_ = web._begriffsboard_html([_e("Mut", vorgaenger=['<b>"A&B"</b>'])])
    assert "<del>&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;</del>" in html_
    assert 'data-vorgaenger="&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;"' in html_
    assert "<b>" not in html_


def test_ohne_kette_bleibt_die_zeile_zeichengleich():
    """Regression: ein Board ohne Schaerfung rendert wie vor dieser Karte."""
    assert web._begriffsboard_html([_e("Mut")]) == (
        '<div id="buehne-panel" data-ansicht="begriffsboard"><ol class="begriffsboard">'
        '<li data-begriff="Mut" data-status="kandidat" data-zustimmung="0" '
        'data-nennungen="1" data-top="1"><span class="begriff">Mut</span></li></ol></div>'
    )


def test_kein_style_kein_handler():
    html_ = web._begriffsboard_html([_e("KI-Roboter", vorgaenger=["Roboter"],
                                        begruendung="Erst Roboter, dann KI-Roboter.")])
    assert "style=" not in html_
    assert re.search(r"\son\w+=", html_) is None


@pytest.fixture
def pfad(tmp_path):
    p = str(tmp_path / "t.db")
    c = db.verbinde(p)
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    repo.lege_begriffsboard_an(c, CHAT, json.dumps([
        {"begriff": "KI-Roboter", "nennungen": 2, "zustimmung": 1,
         "begruendung": "Zuerst als Roboter genannt, dann geschaerft.",
         "zitat": "ZITAT-NIE-IM-WEB", "doppelbedeutung": "", "status": "favorit",
         "vorgaenger": ["Roboter"]},
    ]), "sovereign", 0)
    c.close()
    return p


def _ro(pfad):
    c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_web_daten_reicht_die_kette_durch_ohne_zitat(pfad):
    eintraege = web_daten.begriffsboard(_ro(pfad), CHAT)
    assert eintraege[0]["vorgaenger"] == ["Roboter"]
    assert "zitat" not in eintraege[0]
    html_ = web._begriffsboard_html(eintraege)
    assert "<del>Roboter</del>" in html_
    assert "ZITAT-NIE-IM-WEB" not in html_
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_schaerfung_web.py -q -p no:cacheprovider`
Expected: FAIL in `test_kette_steht_durchgestrichen…`, `test_kette_wird_maskiert`, `test_web_daten_reicht…` (kein `<del>`); `test_ohne_kette_bleibt…`, `test_kein_style_kein_handler` grün; `web_daten.begriffsboard(...)[0]["vorgaenger"] == ["Roboter"]` hält bereits (Durchreichen über `lies`).

- [ ] **Step 3: Implementierung** — in `web._begriffsboard_html` im Schleifenrumpf, nach `top_merkmal = …`, einfügen:

```python
        kette = eintrag.get("vorgaenger") or []
        vorgaenger_merkmal = (
            f' data-vorgaenger="{html.escape(kette[-1], quote=True)}"' if kette else ""
        )
        # Der juengste Vorgaenger steht direkt neben dem neuen Begriff (D2,
        # Karte t_cb2c4678); der Pfeil kommt aus dem CSS
        # (``web_gestalt.css_begriffsboard``), nie aus einem style-Attribut.
        vorgaenger_html = (
            '<span class="vorgaenger">'
            + " ".join(f"<del>{html.escape(v)}</del>" for v in reversed(kette))
            + "</span>"
            if kette else ""
        )
```

und das `zeilen.append(...)` ersetzen durch:

```python
        zeilen.append(
            f'<li data-begriff="{begriff}" data-status="{html.escape(eintrag["status"])}" '
            f'data-zustimmung="{int(eintrag["zustimmung"])}" '
            f'data-nennungen="{int(eintrag["nennungen"])}"{vorgaenger_merkmal}{top_merkmal}>'
            f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>'
            f'{vorgaenger_html}{mehr}</li>'
        )
```

Docstring von `_begriffsboard_html` um einen Satz ergänzen: „Eine Schärfungskette (`vorgaenger`, Karte t_cb2c4678) steht durchgestrichen hinter dem Begriff, der jüngste zuerst, und als `data-vorgaenger` am `<li>` — für die FLIP-Zuordnung im Browser (`web_vereint._BEGRIFFSBOARD_JS`)." Docstring von `web_daten.begriffsboard`: „… OHNE `zitat` … `vorgaenger` (nur Begriffswortlaut, Karte t_cb2c4678) geht mit."

- [ ] **Step 4: Grün laufen lassen, bestehende Board-Tests mit**

Run: `$PY -m pytest tests/test_begriffsboard_schaerfung_web.py tests/test_begriffsboard_web.py -q -p no:cacheprovider`
Expected: `… passed`, kein `failed` — insbesondere `test_html_ist_funktional_mit_data_attributen` und `test_roadmap_traegt_das_board_merkmal_nur_mit_profil` unverändert grün (die neuen Attribute stehen **hinter** `data-status`, die Regexe `<li data-begriff="Heimat" data-status="favorit"[^>]*data-top="1"` greifen weiter).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web.py interview_theater/web_daten.py tests/test_begriffsboard_schaerfung_web.py
git commit -m "Begriffsboard: Schaerfungskette als <del> mit data-vorgaenger im CoThinker (t_cb2c4678, Aufgabe 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Live-Ranking — FLIP-Skript und CSS, nur mit `diskussion.aktiv`

**Files:**
- Modify: `interview_theater/web_gestalt.py` (neu: `_BEGRIFFSBOARD` + `css_begriffsboard()` direkt hinter `css_stepper()`)
- Modify: `interview_theater/web_vereint.py` (neu: `_BEGRIFFSBOARD_JS` direkt hinter `_STEPPER_JS`; in `seite()` zwei bedingte Blöcke)
- Test: `tests/test_begriffsboard_flip.py` (neu)

**Interfaces:**
- Consumes: Markup-Vertrag aus Aufgabe 4; `ladeBuehne()` tauscht unverändert `#tab-buehne.innerHTML`.
- Produces:
  - `web_gestalt.css_begriffsboard(name: str | None = None) -> str` — ruhendes CSS, ohne `@media`/`@keyframes`/`transition`/`animation`, ohne rohe Hexfarbe.
  - `web_vereint._BEGRIFFSBOARD_JS: str` — IIFE mit den reinen Helfern `bbSchluessel(text) -> string`, `bbZuordnung(alt: string[], neu: {begriff, vorgaenger}[]) -> (string|null)[]`, `bbVersatz(altLagen: {schluessel: number}|null, quellen: (string|null)[], neuLagen: number[]) -> (number|null)[]`.
  - `seite()` hängt beides **nur** an, wenn `workshop.diskussion_aktiv()`.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_begriffsboard_flip.py`:

```python
"""Karte t_cb2c4678, Aufgabe 5: Live-Ranking ohne Springen (D3) und das
Gating (D4). Die reinen Helfer werden wie in ``tests/test_buehne_nav_js.py``
per Klammertiefe aus dem Skript geschnitten und unter Node gerufen."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import (db, repo, sprache, web_daten, web_gestalt, web_vereint,
                               workshop)

NODE = shutil.which("node")
_HELFER = ("bbSchluessel", "bbZuordnung", "bbVersatz")


def _extrahiere(skript: str, name: str) -> str:
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _BEGRIFFSBOARD_JS gefunden"
    i = treffer.end()
    tiefe = 1
    while tiefe:
        if skript[i] == "{":
            tiefe += 1
        elif skript[i] == "}":
            tiefe -= 1
        i += 1
    return skript[treffer.start():i]


@pytest.fixture
def harness():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    return "\n".join(_extrahiere(web_vereint._BEGRIFFSBOARD_JS, n) for n in _HELFER)


def _node(tmp_path, harness, anhang):
    pfad = tmp_path / "bb.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# -- Node: reine Helfer ------------------------------------------------------

def test_zuordnung_ueber_begriff_dann_ueber_vorgaenger(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify(bbZuordnung(['Heimat', 'Grenze', 'Roboter'], [
        {begriff: 'KI-Roboter', vorgaenger: 'Roboter'},
        {begriff: 'Heimat', vorgaenger: null},
        {begriff: 'Grenze', vorgaenger: ''}
      ])));
    """)
    assert wert == ["roboter", "heimat", "grenze"]


def test_zuordnung_vorgaenger_nur_wenn_die_alte_zeile_frei_ist(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([
        bbZuordnung(['Roboter'], [{begriff: 'Roboter'}, {begriff: 'KI-Roboter', vorgaenger: 'Roboter'}]),
        bbZuordnung(['Roboter'], [{begriff: 'KI-Roboter', vorgaenger: 'Roboter'},
                                  {begriff: 'Haushaltsroboter', vorgaenger: 'Roboter'}]),
        bbZuordnung([], [{begriff: 'Neu'}])
      ]));
    """)
    assert wert == [["roboter", None], ["roboter", None], [None]]


def test_schluessel_gleicht_gross_klein_und_leerraum_an(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([bbSchluessel('  KI-Roboter \\n'), bbSchluessel(null),
                                  bbZuordnung(['heimat '], [{begriff: 'Heimat'}])]));
    """)
    assert wert == ["ki-roboter", "", ["heimat"]]


def test_versatz_ist_alt_minus_neu_und_null_ohne_alte_lage(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([
        bbVersatz({heimat: 0, roboter: 80}, ['roboter', 'heimat', null], [0, 40, 80]),
        bbVersatz(null, ['roboter'], [0]),
        bbVersatz({heimat: 0}, ['roboter'], [0])
      ]));
    """)
    assert wert == [[80, -40, None], [None], [None]]


# -- Skriptregeln (CSP, reduced motion, kein Eingriff in _VEREINT_JS) --------

def test_skript_haelt_die_csp_und_die_ruhe():
    js = web_vereint._BEGRIFFSBOARD_JS
    assert "style=" not in js and "setAttribute('style'" not in js
    assert re.search(r"\son\w+=", js) is None
    assert "prefers-reduced-motion: reduce" in js
    assert "MutationObserver" in js and "'tab-buehne'" in js
    assert ".style.transform" in js
    assert "innerHTML" not in js            # der Tausch bleibt allein ladeBuehne()s
    assert "bbZuordnung" not in web_vereint._VEREINT_JS


def test_css_ist_ruhend_und_ohne_hexfarbe():
    css = web_gestalt.css_begriffsboard()
    for verboten in ("@media", "@keyframes", "transition", "animation", "url("):
        assert verboten not in css, verboten
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    assert ".vorgaenger" in css and "var(--text-leise)" in css


# -- Gating (D4): nur mit diskussion.aktiv ----------------------------------

CHAT = 7_000_000_000_779
TOKEN = "deterministischer-flip-test-token"


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "flip.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([
        {"begriff": "KI-Roboter", "nennungen": 2, "zustimmung": 1, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "favorit", "vorgaenger": ["Roboter"]},
    ]), "sovereign", 0)
    conn.execute("UPDATE gruppe SET web_token = ? WHERE chat_id = ?", (TOKEN, CHAT))
    conn.commit()
    conn.close()
    return pfad


def _rendere(pfad) -> str:
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, TOKEN)
        chatdaten = web_daten.web_chatzustand(lesend, TOKEN)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    return web_vereint.seite(
        daten, chatdaten, roadmapdaten, nonce_wert="n", token=TOKEN, praefix="/theatersoap",
        segment_ms=45_000, fassungswahl={}, chat_vorhanden=chatdaten is not None,
    )


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.mark.parametrize("profil, erwartet", [
    (None, False), ("dortmund-2026", False), ("padua-2026", True),
])
def test_skript_und_css_nur_mit_diskussion_aktiv(monkeypatch, db_pfad, profil, erwartet):
    if profil is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, profil)
    workshop.vergiss()
    sprache.vergiss()
    assert workshop.diskussion_aktiv() is erwartet
    html_ = _rendere(db_pfad)
    css = web_vereint.scope_css(web_gestalt.css_begriffsboard(), ".panel-buehne")
    assert ("function bbZuordnung(" in html_) is erwartet
    assert (css in html_) is erwartet
    # Mit Profil steht das Board samt Kette im CoThinker-Panel.
    assert ("<del>Roboter</del>" in html_) is erwartet
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_flip.py -q -p no:cacheprovider`
Expected: FAIL / ERROR mit `AttributeError: module 'interview_theater.web_vereint' has no attribute '_BEGRIFFSBOARD_JS'` bzw. `… web_gestalt … 'css_begriffsboard'`; die Gating-Fälle `None`/`dortmund-2026` scheitern ebenfalls am fehlenden `css_begriffsboard`. ANNAHME: die minimale Fixture-Gruppe rendert unter `padua-2026` ohne weitere Arbeitsstandzeilen (die Bitgleich-DB ist reicher); wirft `seite()` dort einen `KeyError`, die fehlende Zeile mit `repo.setze_arbeitsstand` in `db_pfad` ergänzen — nicht `seite()` ändern.

- [ ] **Step 3: CSS** — in `interview_theater/web_gestalt.py` direkt hinter `css_stepper()`:

```python
#: Das Begriffsboard (Karte t_cb2c4678): nur Ruhendes. Die Bewegung (FLIP)
#: setzt ``web_vereint._BEGRIFFSBOARD_JS`` per CSSOM und fragt dort selbst
#: nach ``prefers-reduced-motion`` -- eine ``transition`` hier braeuchte
#: einen Selektor im reduced-motion-Block, und der steht in ``css_rahmen()``
#: (Dortmund, byte-gleich). ``position: relative`` macht die Zeile zum
#: Bezug von ``offsetTop`` (das Skript misst damit, ``transform`` zaehlt
#: dort nicht mit).
_BEGRIFFSBOARD = """
.begriffsboard { position: relative; }
.begriffsboard .vorgaenger { color: var(--text-leise); margin-left: 0.4em; }
.begriffsboard .vorgaenger::before { content: "\\2190\\00a0"; }
.begriffsboard .vorgaenger del { text-decoration-thickness: 1px; }
"""


def css_begriffsboard(name: str | None = None) -> str:
    """Das Begriffsboard im CoThinker (Phase 1, Karte t_cb2c4678) -- nur
    angehaengt, wenn ``workshop.diskussion_aktiv()`` (siehe
    ``web_vereint.seite()``), wie ``css_stepper()``: Dortmund rendert das
    Board nie und bekommt dieses CSS deshalb auch nicht. Der Aufrufer scopt
    es auf ``.panel-buehne`` -- deshalb kein ``@media``/``@keyframes``. Fuer
    beide Entwuerfe gleich, die Tokens tragen den Unterschied."""
    return _BEGRIFFSBOARD
```

(`--text-leise` auf `--grund` steht schon in `KONTRAST`, 4.5.)

- [ ] **Step 4: Skript** — in `interview_theater/web_vereint.py` direkt hinter dem Ende von `_STEPPER_JS`:

```python
#: Live-Ranking des Begriffsboards (Karte t_cb2c4678, D3/D4). Eine eigene
#: IIFE, nur mit ``workshop.diskussion_aktiv()`` angehaengt (``seite()``) --
#: ``_VEREINT_JS`` steht Zeichen fuer Zeichen in Dortmunds Seite
#: (``tests/fixtures/web_vereint_dortmund_vorher.html``) und wird deshalb
#: NICHT angefasst. Stattdessen sieht ein MutationObserver den Tausch, den
#: ``ladeBuehne()`` ohnehin macht (``panel.innerHTML = neu``): die alten
#: Knoten stehen in ``removedNodes`` (ihr ``details.open`` ist lesbar), ihr
#: Layout nicht mehr -- deshalb merkt sich das Skript die Lagen (``offsetTop``,
#: ohne ``transform``) des letzten Stands. Bewegung nur per CSSOM (CSP) und
#: nie bei ``prefers-reduced-motion: reduce``. Roh-String: die Regex ``\s``
#: bleibt unveraendert.
_BEGRIFFSBOARD_JS = r"""
(function () {
  var panel = document.getElementById('tab-buehne');
  if (!panel || typeof MutationObserver === 'undefined') { return; }
  var DAUER_MS = 320;
  var lagen = null;

  function bbSchluessel(text) {
    return String(text || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  // Je neuem Eintrag der Schluessel der alten Zeile, von der er kommt, oder
  // null (neu). Erst ueber den eigenen Begriff, dann -- fuer einen
  // geschaerften Begriff -- ueber seinen juengsten Vorgaenger, und das nur,
  // wenn die alte Zeile nicht schon vergeben ist.
  function bbZuordnung(alt, neu) {
    var frei = {};
    alt.forEach(function (b) { frei[bbSchluessel(b)] = true; });
    var erst = neu.map(function (n) {
      var k = bbSchluessel(n.begriff);
      if (frei[k]) { frei[k] = false; return k; }
      return null;
    });
    return erst.map(function (k, i) {
      if (k !== null) { return k; }
      var v = bbSchluessel(neu[i].vorgaenger);
      if (v && frei[v]) { frei[v] = false; return v; }
      return null;
    });
  }

  // FLIP "Invert": alte Lage minus neue, je neuem Eintrag; null ohne alte Lage.
  function bbVersatz(altLagen, quellen, neuLagen) {
    return quellen.map(function (q, i) {
      if (q === null || !altLagen || typeof altLagen[q] !== 'number') { return null; }
      return altLagen[q] - neuLagen[i];
    });
  }

  function liste(wurzel) {
    if (!wurzel || !wurzel.querySelector) { return null; }
    if (wurzel.matches && wurzel.matches('ol.begriffsboard')) { return wurzel; }
    return wurzel.querySelector('ol.begriffsboard');
  }

  function miss(ol) {
    if (!ol || ol.offsetParent === null) { return null; }
    var ergebnis = {};
    Array.prototype.forEach.call(ol.children, function (li) {
      ergebnis[bbSchluessel(li.getAttribute('data-begriff'))] = li.offsetTop;
    });
    return ergebnis;
  }

  function merke() { lagen = miss(liste(panel)); }

  function ruhig() {
    return !!(window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function nachTausch(aenderungen) {
    var altOl = null;
    aenderungen.forEach(function (m) {
      Array.prototype.forEach.call(m.removedNodes, function (n) {
        if (!altOl) { altOl = liste(n); }
      });
    });
    var neuOl = liste(panel);
    if (!neuOl || !altOl) { merke(); return; }
    var altLagen = lagen;
    var alt = [];
    var offen = {};
    Array.prototype.forEach.call(altOl.children, function (li) {
      var b = li.getAttribute('data-begriff');
      var d = li.querySelector('details');
      alt.push(b);
      if (d && d.open) { offen[bbSchluessel(b)] = true; }
    });
    var lis = Array.prototype.slice.call(neuOl.children);
    var quellen = bbZuordnung(alt, lis.map(function (li) {
      return { begriff: li.getAttribute('data-begriff'),
               vorgaenger: li.getAttribute('data-vorgaenger') };
    }));
    // Erst den Auf-/Zu-Zustand zurueck, DANN messen: ein offenes "Warum"
    // verschiebt alle Zeilen darunter.
    quellen.forEach(function (q, i) {
      var d = lis[i].querySelector('details');
      if (d && q !== null && offen[q]) { d.open = true; }
    });
    var neuLagen = lis.map(function (li) { return li.offsetTop; });
    lagen = miss(neuOl);
    if (ruhig()) { return; }
    var versatz = bbVersatz(altLagen, quellen, neuLagen);
    lis.forEach(function (li, i) {
      if (quellen[i] === null) { li.style.opacity = '0'; }
      else if (versatz[i]) { li.style.transform = 'translateY(' + versatz[i] + 'px)'; }
    });
    neuOl.getBoundingClientRect();   // Startlage festschreiben (Reflow)
    requestAnimationFrame(function () {
      lis.forEach(function (li) {
        li.style.transition = 'transform ' + DAUER_MS + 'ms ease, opacity '
          + DAUER_MS + 'ms ease';
        li.style.transform = '';
        li.style.opacity = '';
      });
      setTimeout(function () {
        lis.forEach(function (li) { li.style.transition = ''; });
      }, DAUER_MS + 50);
    });
  }

  new MutationObserver(nachTausch).observe(panel, { childList: true });
  // ``toggle`` blubbert nicht -- im Capture kommt es trotzdem an.
  panel.addEventListener('toggle', merke, true);
  window.addEventListener('resize', merke);
  window.addEventListener('hashchange', function () { setTimeout(merke, 0); });
  merke();
})();
"""
```

- [ ] **Step 5: Bedingte Einhängung in `seite()`** — in `web_vereint.seite()`:

(a) direkt hinter dem Block `if stepper_aktiv: css += web_gestalt.css_stepper()`:

```python
    # Begriffsboard (Karte t_cb2c4678): wie der Stepper NUR bedingt -- mit
    # ``diskussion.aktiv`` kann Phase 1 das Board zeigen, ohne bekommt
    # Dortmund kein Zeichen davon (tests/test_web_vereint_bitgleich.py).
    board_aktiv = workshop.diskussion_aktiv()
    if board_aktiv:
        css += scope_css(web_gestalt.css_begriffsboard(), ".panel-buehne")
```

(b) direkt hinter dem Block `if stepper_aktiv: skript += (_STEPPER_JS …)` und **vor** `skript += web_gestalt.skript(...)`:

```python
    if board_aktiv:
        skript += _BEGRIFFSBOARD_JS
```

(`workshop` ist in `seite()` schon importiert — es liest `workshop.workbench_bearbeitbar()` und `workshop.diskussion_aktiv()`. ANNAHME: Import steht modulweit oder lokal oben in `seite()`; falls lokal unterhalb der Einhängestelle, `from interview_theater import workshop` an den Funktionsanfang ziehen.)

- [ ] **Step 6: Grün laufen lassen + Bitgleich + Syntax**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py tests/test_web_vereint_bitgleich.py tests/test_web_vereint_js_syntax.py tests/test_buehne_nav_js.py tests/test_web_gestalt_css.py tests/test_begriffsboard_web.py -q -p no:cacheprovider
git status --short tests/fixtures/
```

Expected: `… passed` ohne `failed` (die Node-Tests `skipped`, falls kein `node` auf PATH — dann im Bericht „Node-Tests nicht gelaufen", **nicht** „grün"); `git status` für `tests/fixtures/` ohne Ausgabe. `test_vereinte_seite_bleibt_byte_gleich[None]` und `[dortmund-2026]` grün gegen die **unveränderte** Fixture. Ist sie rot: der Fehler liegt in dieser Aufgabe (etwas wurde unbedingt angehängt) — Fixture **nicht** neu erzeugen.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/web_gestalt.py interview_theater/web_vereint.py tests/test_begriffsboard_flip.py
git commit -m "Begriffsboard: FLIP-Live-Ranking und Schaerfungs-CSS, nur mit diskussion.aktiv (t_cb2c4678, Aufgabe 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Browserlauf — Umsortieren, Schärfung, offenes „Warum", Handy-Screenshot

**Files:**
- Create: `tests/e2e/test_web_begriffsboard_ranking_e2e.py`
- Create: `docs/web-begriffsboard/ranking-2026-10-04.png` (nur mit `IT_SCHUSS_AKTUALISIEREN=1`, erfundenes Material)

**Interfaces:**
- Consumes: Markup aus Aufgabe 4, Skript aus Aufgabe 5, `repo.lege_begriffsboard_an` (nur anhängen, letzter Stand gilt), Nachladetakt `web_vereint.NACHLADEN_MS` (= 10 000 ms).

- [ ] **Step 1: Test schreiben** — `tests/e2e/test_web_begriffsboard_ranking_e2e.py`:

```python
"""Karte t_cb2c4678, Aufgabe 6: das Begriffsboard sortiert im echten Browser
um, ohne zu springen (D3). Ein echter Webserver-Prozess unter
``IT_WORKSHOP=padua-2026`` (sonst gibt es kein Board), eine Gruppe in
Phase 1, ein Board A; der Test legt ein umsortiertes Board B mit einer
Schaerfung ("Roboter" -> "KI-Roboter") in die Datenbank und wartet auf den
naechsten ``ladeBuehne()``-Takt. Nachgewiesen werden die Wirkungen der
Zuordnung: das geoeffnete "Warum" bleibt an der verschobenen und an der
geschaerften Zeile offen, genau diese Zeilen bekommen ein ``translateY``
(mit reduzierter Bewegung: keins), und die alte Fassung steht als ``<del>``.

Ohne Playwright wird die Datei uebersprungen (``importorskip``). Der
Handy-Schuss landet immer unter /tmp und nur mit
``IT_SCHUSS_AKTUALISIEREN=1`` im Repository (Muster
``test_web_cothinker_status_screenshot_e2e.py``). Nur erfundenes Material."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-bb-ranking.db"
AUDIO = "/tmp/it-bb-ranking-audio"
SERVERLOG = "/tmp/it-bb-ranking-server.log"
CHAT = 7_000_000_000_101
HANDY = {"width": 390, "height": 844}
SCHUSS = WURZEL / "docs" / "web-begriffsboard" / "ranking-2026-10-04.png"
SCHUSS_TMP = Path("/tmp/it-bb-ranking/ranking-2026-10-04.png")
GEDULD_MS = 30_000


def _e(begriff, status, zustimmung, nennungen, begruendung, vorgaenger=None):
    eintrag = {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
               "begruendung": begruendung, "zitat": "", "doppelbedeutung": "",
               "status": status}
    if vorgaenger:
        eintrag["vorgaenger"] = vorgaenger
    return eintrag


BOARD_A = [
    _e("Heimat", "favorit", 2, 3, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "kandidat", 1, 2, "Eine Grenze kann auch im Kopf sein."),
    _e("Roboter", "kandidat", 0, 1, "Einer will eine Maschine auf der Buehne."),
]
BOARD_B = [
    _e("KI-Roboter", "favorit", 2, 4,
       "Zuerst als 'Roboter' genannt, spaeter geschaerft auf 'KI-Roboter'.", ["Roboter"]),
    _e("Heimat", "kandidat", 1, 3, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "kandidat", 1, 2, "Eine Grenze kann auch im Kopf sein."),
]

#: Zeichnet jedes inline gesetzte ``transform`` einer Boardzeile auf -- im
#: Test, nicht im Produktivcode.
_BEOBACHTER = """() => {
  window.__bbTransforms = {};
  new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      var t = m.target;
      if (t.matches && t.matches('li[data-begriff]') && t.style.transform) {
        window.__bbTransforms[t.getAttribute('data-begriff')] = t.style.transform;
      }
    });
  }).observe(document.getElementById('tab-buehne'),
             { subtree: true, attributes: true, attributeFilter: ['style'] });
}"""


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        Path(DB_PFAD + endung).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "rankingbot", "Rankinggruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD_A), "sovereign", 0)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    return token


def _lege_board_b() -> None:
    conn = db.verbinde(DB_PFAD)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD_B), "sovereign", 0)
    conn.close()


def _warte_auf_server(prozess, basis: str, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Der Webserver ist abgestuerzt, siehe {SERVERLOG}.")
        try:
            with urllib.request.urlopen(f"{basis}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture
def server():
    token = _baue_datenbank()
    bind = f"127.0.0.1:{_freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "", "IT_AUDIO": AUDIO,
        "IT_WORKSHOP": "padua-2026", "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        basis = f"http://{bind}"
        _warte_auf_server(prozess, basis)
        yield basis, token
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


def _lauf(basis, token, *, ruhig: bool, schuss: bool):
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(
                viewport=HANDY, is_mobile=True,
                reduced_motion="reduce" if ruhig else "no-preference",
            )
            seite = kontext.new_page()
            seite.set_default_timeout(GEDULD_MS)
            seite.goto(f"{basis}/g/{token}#buehne")
            seite.wait_for_selector('#tab-buehne li[data-begriff="Roboter"]', state="visible")
            # Zwei "Warum" oeffnen: eine Zeile, die nach unten rutscht
            # (Heimat), und die, die gleich geschaerft wird (Roboter).
            seite.click('#tab-buehne li[data-begriff="Heimat"] summary')
            seite.click('#tab-buehne li[data-begriff="Roboter"] summary')
            seite.evaluate(_BEOBACHTER)
            _lege_board_b()
            seite.wait_for_selector('#tab-buehne li[data-begriff="KI-Roboter"]', state="visible")
            seite.wait_for_timeout(600)   # FLIP-Dauer (320 ms) plus Luft

            neu = seite.locator('#tab-buehne li[data-begriff="KI-Roboter"]')
            assert neu.get_attribute("data-vorgaenger") == "Roboter"
            assert neu.locator(".vorgaenger del").inner_text() == "Roboter"
            assert seite.locator('#tab-buehne li[data-begriff="Roboter"]').count() == 0
            reihenfolge = seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li", "els => els.map(e => e.dataset.begriff)")
            assert reihenfolge == ["KI-Roboter", "Heimat", "Grenze"]
            # Zuordnung belegt: beide "Warum" sind an ihren (neuen) Zeilen offen.
            assert neu.locator("details").evaluate("d => d.open") is True
            assert seite.locator(
                '#tab-buehne li[data-begriff="Heimat"] details').evaluate("d => d.open") is True
            assert seite.locator(
                '#tab-buehne li[data-begriff="Grenze"] details').evaluate("d => d.open") is False

            transforms = seite.evaluate("() => window.__bbTransforms")
            if ruhig:
                assert transforms == {}
            else:
                assert transforms.get("KI-Roboter", "").startswith("translateY(")
                assert transforms.get("Heimat", "").startswith("translateY(")
            # Die Bewegung ist vorbei: keine Zeile bleibt verschoben stehen.
            assert seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li",
                "els => els.every(e => !e.style.transform)") is True

            if schuss:
                SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
                seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
                assert SCHUSS_TMP.stat().st_size > 1000
                if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
                    SCHUSS.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(SCHUSS_TMP, SCHUSS)
            kontext.close()
        finally:
            chromium.close()


def test_board_sortiert_um_ohne_zu_springen_und_zeigt_die_schaerfung(server):
    basis, token = server
    _lauf(basis, token, ruhig=False, schuss=True)


def test_reduzierte_bewegung_ohne_animation_aber_mit_offenem_warum(server):
    basis, token = server
    _lauf(basis, token, ruhig=True, schuss=False)
```

- [ ] **Step 2: Laufen lassen (Playwright-venv), Screenshot ins Repo**

```bash
ls $E2E && IT_SCHUSS_AKTUALISIEREN=1 $E2E -m pytest tests/e2e/test_web_begriffsboard_ranking_e2e.py -q -p no:cacheprovider
ls -l docs/web-begriffsboard/ranking-2026-10-04.png
```

Expected: `2 passed`; die PNG-Datei existiert (> 1 kB). Fehlt `$E2E` oder Playwright (`1 skipped` bzw. `No such file`), heißt das im Bericht wörtlich „e2e nicht gelaufen" — **nie** „grün". Den Screenshot einmal mit dem Read-Werkzeug ansehen (Handybreite 390, Board mit `KI-Roboter ← ~~Roboter~~` oben, zwei offene „Warum") und im Bericht beschreiben; Birk urteilt über die Gestaltung nur am Bild.

ANNAHME (im Lauf prüfen): Mit `#buehne` in der URL ist der CoThinker-Tab beim Laden sichtbar und `ladeBuehne()` holt alle 10 s frisch. Wartet der Test vergeblich auf `KI-Roboter`, zuerst `SERVERLOG` und `seite.content()` ansehen, ob `#roadmap` `data-begriffsboard="1"` trägt (Padua-Stepper); erst danach am Test drehen.

ANNAHME (im Lauf prüfen): die Bewegung der Zeile „Grenze" kann 0 sein (gleiche Lage); deshalb prüft der Test sie nicht.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_web_begriffsboard_ranking_e2e.py docs/web-begriffsboard/ranking-2026-10-04.png
git commit -m "Begriffsboard: Browserlauf Umsortieren + Schaerfung + offenes Warum, Handy-Screenshot (t_cb2c4678, Aufgabe 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Ist e2e nicht gelaufen: nur die Testdatei committen, im Bericht „e2e nicht gelaufen, kein Screenshot".)

---

### Task 7: AGENTS.md, Abschluss-Suite, Bericht

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: AGENTS.md nachziehen** — vier Stellen, Wortlaut sinngemäß, im Stil des Dokuments:

(a) Modultabelle, Zeile `begriffsboard.py`: an das Ende der Zelle anhängen:
„Seit 04.10.2026 (Karte t_cb2c4678) die **Schärfung**: Pflichtfeld `vorheriger_begriff` im Schema, im Code gegen das bisherige Board geprüft (`validiere(…, bisher)`, `_verkette` — nur ein Begriff, der wirklich verschwand, keine Ähnlichkeitsheuristik); daraus die Kette `vorgaenger` (älteste zuerst, nur am Eintrag, wenn nicht leer, nie im Schema, nie Modelltext). Im CoThinker durchgestrichen (`web._begriffsboard_html`, `data-vorgaenger`), Live-Ranking per FLIP (`web_vereint._BEGRIFFSBOARD_JS`, MutationObserver auf den unveränderten Tausch von `ladeBuehne()`, nur mit `diskussion.aktiv`)."

(b) „Wo man anfängt": neue Zeile
`| Warum ist ein Begriff durchgestrichen (oder nicht)? | begriffsboard.validiere → _verkette → web._begriffsboard_html → web_vereint._BEGRIFFSBOARD_JS |`

(c) Abschnitt „Die Gestaltung": „neun Zeilen … zehnte" um eine **elfte** Einhängezeile ergänzen: `css_begriffsboard()` in `web_vereint.seite`, nur mit `diskussion.aktiv`, gescopt auf `.panel-buehne`, ohne Bewegung im CSS (die setzt das Skript per CSSOM und nur ohne `prefers-reduced-motion`).

(d) „Die Übergaben der Karte t_4517d4ad (Begriffsboard …)": drei Punkte anhängen:
- „**Ungemessen (t_cb2c4678):** kein bezahlter Lauf für `vorheriger_begriff` — ob Kimi/Opus das Feld zuverlässig füllen, weiß niemand. Vergisst das Modell es, fehlt nur der Strich; die Begründung erzählt die Entwicklung trotzdem."
- „Die Wortzahl „1–3" eines Begriffs (und damit eines Vorgängers) steht im Prompt, nicht im Code; der Code garantiert „ein Begriff, früher schon auf dem Board"."
- „Ist der CoThinker beim letzten Messen verborgen, sortiert der nächste Tausch ohne Bewegung um (nur das offene „Warum" bleibt)."

- [ ] **Step 2: Gezielte Pflichttests einzeln, mit Namen**

```bash
$PY -m pytest tests/test_web_vereint_bitgleich.py tests/test_profil_bitgleich.py tests/test_pruefe_sprache.py -q -p no:cacheprovider
$PY -m pytest tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_web.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_einstieg.py tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard_schaerfung_web.py tests/test_begriffsboard_flip.py -q -p no:cacheprovider
BASIS=<SHA aus Aufgabe 0, Step 3>
git diff --stat "$BASIS" HEAD -- tests/fixtures/
```

Expected: beide Läufe `… passed`, kein `failed`; `git diff --stat` ohne Ausgabe (keine Fixture neu erzeugt).

- [ ] **Step 3: Abschluss-Suite im Hintergrund, abwarten**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e > .suite.log 2>&1; echo EXIT $?
```

Im Hintergrund starten, bis zum Ende abwarten, nicht abbrechen. Danach `tail -n 3 .suite.log` und `tail -n 3 .suite-baseline.log`.

Expected: `EXIT 0`; Zahl `passed` = Baseline + die neuen Tests (Aufgabe 2: 27, Aufgabe 3: 5, Aufgabe 4: 5, Aufgabe 5: 9 — zusammen +46, Node-Tests ggf. als `skipped`); keine neuen `failed`. Ein Test, der in der Baseline grün und jetzt rot ist, ist Folge dieser Karte und wird behoben, bevor committet wird.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "Begriffsboard: AGENTS.md -- Schaerfung, FLIP, elfte Einhaengezeile, Uebergaben (t_cb2c4678, Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Abschlussbericht** (als Kartenkommentar, nicht als Datei) — Pflichtinhalt:
  1. BASIS-SHA aus Aufgabe 0 und die Commit-SHAs der Aufgaben 2–7.
  2. **Beide** Suite-Zeilen wörtlich: Baseline (`.suite-baseline.log`) und Schluss (`.suite.log`), jeweils mit `EXIT`.
  3. Die drei Pflichttests mit Ergebnis: `tests/test_web_vereint_bitgleich.py`, `tests/test_profil_bitgleich.py`, `tests/test_pruefe_sprache.py`.
  4. Node-Tests gelaufen ja/nein; e2e gelaufen ja/nein (sonst wörtlich „e2e nicht gelaufen"); Pfad und Beschreibung des Screenshots.
  5. Jede ANNAHME dieses Plans mit dem, was sich im Lauf gezeigt hat.
  6. Ausdrücklich: kein Merge, kein Push, kein bezahlter Lauf.

---

## Selbstprüfung des Plans (gegen Abschnitt A–F der Karte)

| Anforderung | Aufgabe |
|---|---|
| Vorbedingung prüfen, sonst blockieren, nie kopieren | 0 |
| Baseline-Suite im Hintergrund, `.suite.log` nicht committet | 1 |
| D1 Feld + Prüfung in `validiere(…, bisher)` (gültig / erfunden / noch stehend / selbst) | 2 |
| D1 Kette über zwei Läufe, Erben, altes Board ohne Feld | 2, 3 |
| D1 keine Heuristik, Begründung | Plankopf |
| D1 Schema `required`, Prompt DE/EN, Nutzertext mit `vorgaenger` | 3 |
| „nie mehr als ein Begriff", per Konstruktion begründet | 2 (Step 5 + vier Tests) |
| D2 `<del>`, maskiert, `data-vorgaenger`, kein `style=`/`on…=`/Zitat, alte Regexe grün | 4 |
| D3 FLIP, Zuordnung über Vorgänger, Einblenden, reduced motion, `<details>`-Zustand, CSSOM, Node-Test | 5, 6 |
| D4 Gating-Test, Bitgleich gegen unveränderte Fixture | 5, 7 |
| D5 Phase 4 unberührt | Dateiübersicht („Nicht angefasst") |
| e2e + Handy-Screenshot, „e2e nicht gelaufen" statt „grün" | 6 |
| Schluss-Suite, beide Zeilen im Bericht, AGENTS.md | 7 |

**ANNAHME-Marker in diesem Plan:**
1. Aufgabe 3, Step 1: der englische Prompt hat nach dem Merge `0 Treffer` im Sprachprüfer.
2. Aufgabe 3, Step 9: `scripts/prompt_schnappschuss.py` enthält den Begriffsboard-Prompt nicht (Dortmund-Bitgleich unberührt).
3. Aufgabe 5, Step 2: die minimale Fixture-Gruppe rendert unter `padua-2026` ohne weitere Arbeitsstandzeilen, und `web._seite` setzt das CSS unverändert ein (der Gating-Test sucht die gescopte CSS-Zeichenkette wörtlich im HTML).
4. Aufgabe 5, Step 5: `workshop` ist an der Einhängestelle in `seite()` schon importiert.
5. Aufgabe 6, Step 2: mit `#buehne` ist der CoThinker beim Laden sichtbar und lädt alle 10 s nach.
6. Aufgabe 6, Step 2: die Lage von „Grenze" kann unverändert bleiben (nicht geprüft).

# Padua Phase 1: Begriffsboard mit Live-Ranking und Schärfungs-Historie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Plan-Karte t_5e484a08, Ausführung auf Karte t_cb2c4678, Branch `wt/t_cb2c4678`, **in diesem Worktree**
(`/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_cb2c4678`). Ziel ist `main` über eine spätere [Merge]-Karte.

**Zwei Teile, eine Ausführung in Reihenfolge 0 → 11.** Teil 1 (Aufgaben 0–7): Live-Ranking und Schärfungs-Historie. Teil 2 (Aufgaben 8–11, Birks Nachtrag vom 04.10.2026 14:50, eigener Abschnitt weiter unten): Pause-Knopf des Mithörens weg, Endstand = Zwischenstand. Die Abschluss-Suite und der Bericht stehen für beide Teile in Aufgabe 11.

**Revision 04.10.2026 (Birk, `main` 4fe89de): Dortmund ist eingefroren.** AGENTS.md auf `main`, Abschnitt „🔴 Dortmund eingefroren seit 04.10.2026 — Abnahme nur noch an Padua": „Dortmund byte-gleich/bitgleich" und `pruefe_profil dortmund-2026` sind **keine** Abnahmekriterien mehr. Abgenommen wird: Suite grün mit `-m "not dortmund"`, `pruefe_profil padua-2026` grün, Prompt-Snapshot nur für Padua. Ein Test, der **nur** wegen Dortmund-Verhalten rot wird, bekommt `@pytest.mark.dortmund` (registriert in `pyproject.toml`) statt angepasst zu werden; Dortmund-/Vorgabe-Fixtures (`tests/fixtures/*dortmund*`, `*vorgabe*`) werden **nicht** mehr neu erzeugt; neue Funktionen nur für Padua, **keine neuen Profilschalter**, bestehende bleiben, Dortmund-Code und -Daten werden nicht gelöscht. Die frühere Entscheidung D4 (Dortmund byte-gleich, gegatetes Skript per MutationObserver, Fixture-Neuerzeugung in Teil 2) ist damit **gestrichen**.

**Goal:** Der CoThinker-Tab der Phase 1 (Begriffsboard, nur Padua, Profilschalter `diskussion.aktiv`) sortiert seine Begriffe live um, ohne dass die Liste springt; schärft das Modell einen Begriff („Roboter" → „KI-Roboter"), zeigt dieselbe Zeile den alten Wortlaut durchgestrichen neben dem neuen, während die Begründung die Entwicklung weiter in Prosa erzählt.

**Architecture:** Hybrid (Architekt D1): das Modell liefert je Eintrag ein neues Pflichtfeld `vorheriger_begriff`, der **Code** prüft es gegen das bisherige Board (`begriffsboard.validiere(roh, transkript, bisher)`) und führt daraus die Kette `vorgaenger` (älteste zuerst), die nie im Schema steht. `web._begriffsboard_html` zeigt die Kette als `<del>` und trägt `data-vorgaenger`. Das Live-Ranking sitzt **direkt in `ladeBuehne()`** (`_VEREINT_JS`): unmittelbar vor `panel.innerHTML = neu` werden Lagen und `<details>`-Zustand gemerkt, unmittelbar danach wird FLIP gespielt; das ruhende CSS steht im regulären CoThinker-CSS (`web_gestalt.css_buehne()`). Kein neuer Schalter — das Board rendert ohnehin nur unter `diskussion.aktiv`, und ohne `ol.begriffsboard` im Panel tun die neuen Funktionen nichts.

**Tech Stack:** Python 3.11, Standardbibliothek, SQLite, pytest, Node (nur für die extrahierten JS-Helfer), Playwright (nur `tests/e2e`, eigenes venv).

## Global Constraints

Bindende Entscheidungen (Architekt, Abschnitt D der Karte, mit der Revision vom 04.10.2026) — **nicht neu verhandeln**:

- **D1 Datenquelle hybrid.** Neues Pflicht-String-Feld `vorheriger_begriff` im Schema (`""`, wenn keins). Gehalten wird ein Link **nur**, wenn `schluessel(link)` der Schlüssel eines Eintrags in `bisher` ist **und** dieser Schlüssel im neuen Board nicht mehr als eigene Zeile steht **und** er sich vom eigenen Schlüssel des Eintrags unterscheidet. Sonst gilt er als `""`. **Keine** Levenshtein-/Teilstring-Heuristik im Code (Begründung unten). Historie = `vorgaenger: list[str]`, älteste zuerst, **nur vom Code** geführt: ein geprüfter Link ergibt `bisher_eintrag.vorgaenger + [bisher_eintrag.begriff]`; ein Eintrag mit gleichem Schlüssel erbt `vorgaenger` des bisherigen. `lies`/`_eintrag` lesen `vorgaenger` defensiv (fehlt/kaputt → keine Kette). `vorgaenger` steht **nicht** im Schema. Prompt DE + EN: Feldbeschreibung `vorheriger_begriff` und der Satz, dass ein Begriff aus `vorgaenger` nicht wieder als eigene Zeile kommt, obwohl er im (wachsenden) Transkript stehen bleibt; der Board-JSON im Nutzertext trägt `vorgaenger`. **Keine** anderen Verbraucher ändern sich (`detail_fuer`, `detail_zeilen`, `sende_vorschlag`, `arbeitsstand.begriffe_detail`).
- **D2 Darstellung** in `web._begriffsboard_html`: je `<li>` mit Kette `<span class="begriff">NEU</span>` gefolgt von den Vorgängern durchgestrichen, der jüngste direkt neben dem neuen Begriff (`<span class="vorgaenger"><del>KI-Roboter</del> <del>Roboter</del></span>`); Pfeil als CSS, kein `style=`, alles `html.escape`; `data-vorgaenger="<jüngster Vorgänger>"` am `<li>`. `web_daten.begriffsboard` reicht `vorgaenger` durch und lässt `zitat` weiter weg.
- **D3 Live-Ranking:** klassisches FLIP in reinem JS, ohne Bibliothek, **in `ladeBuehne()`**. Zuordnung alt↔neu über `data-begriff`, ersatzweise `data-vorgaenger`; Neue blenden ein, Entfernte verschwinden. `prefers-reduced-motion: reduce` → keine Bewegung. Auf-/Zu-Zustand jedes `<details>` übersteht den Panel-Tausch (gleiche Zuordnung). Transform nur über `el.style.*` (CSSOM, CSP). Reine Helfer node-getestet wie `tests/test_buehne_nav_js.py`.
- **~~D4~~ gestrichen (Revision).** Statt Byte-Gleichheit gilt AGENTS.md „Dortmund eingefroren": wird ein `*bitgleich*`-Test **nur** wegen einer Dortmund-/Vorgabe-Fixture rot, bekommt er `@pytest.mark.dortmund` (Vorgehen in Aufgabe 5 und 9), **keine** Fixture wird neu erzeugt, kein neuer Schalter, kein Gating-Test.
- **D5** Phase-4-CoThinker (Bühnenkarten, Nicht-Board-Zweig von `_buehne_html`) bleibt im Verhalten unberührt: `bbMerke` liefert ohne `ol.begriffsboard` `null`, `bbSpiele(panel, null)` tut nichts.
- Karten-Leitplanken: bestehende `tests/test_begriffsboard_*.py` grün, besonders `test_html_ist_funktional_mit_data_attributen` und `test_roadmap_traegt_das_board_merkmal_nur_mit_profil`; **kein Zitat im CoThinker** — `vorgaenger` trägt nur Begriffswortlaut, nie einen Transkriptausschnitt (AGENTS.md „Drei Grenzen"); Suite (ohne e2e, `-m "not dortmund"`) Pflicht, Baseline- **und** Schlusszahlen im Abschlussbericht; `pruefe_profil padua-2026` grün.
- AGENTS.md-Zusagen: SQL nur in `repo.py`/`db.py` (hier kommt keins dazu); Prompts nur Negativbeispiele; kein `style="…"`, kein `on…=` im ausgelieferten HTML; `@keyframes`/`@media` nur in `web_gestalt.css_rahmen()` — `css_buehne()` wird von `web_vereint.seite` durch `scope_css` geschickt, also steht dort **kein** `@media`/`@keyframes`/`transition`; die Bewegung setzt das JS per CSSOM.
- Code-Bezeichner deutsch wie im Repo, Kommentare in ae/oe/ue wie im umgebenden Code. Nur erfundenes Material in Tests und Screenshots. Nie `.env`/`betrieb/` lesen. Dortmund-Code und -Fixtures nicht löschen, nicht neu erzeugen.
- Branch `wt/t_cb2c4678`, **kein Merge nach main, kein Push** (ein Push auf origin/main ist ≤ 5 min später LIVE). Nie den Haupt-Arbeitsbaum anfassen und **nie** dessen uncommittete Änderungen von Hand herüberkopieren. Ein Commit je Aufgabe, nur die genannten Dateien `git add`-en (nie `git add -A`; `.suite.log`, `.suite-baseline.log`, `.cc-*`, `.superpowers-*` bleiben ungetrackt). Commit-Nachrichten enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testbefehle immer abwarten. Einzige Ausnahme sind die beiden Suite-Läufe (Aufgaben 1 und 11): im Hintergrund in `.suite.log`, **abwarten bis zum Ende, nicht abbrechen**. Der Suite-Befehl lautet **immer**:
  `$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?`
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
2. **`vorgaenger` steht nur am Eintrag, wenn die Kette nicht leer ist** (dünn statt `[]`). Gleicher Beleg wie 1.; Nebeneffekt: Boards ohne Schärfung bleiben im gespeicherten JSON, im Nutzertext und im HTML zeichengleich zu heute. Leser nehmen `eintrag.get("vorgaenger") or []`.
3. **Geerbte Ketten werden gegen eigene Zeilen gefiltert.** Steht ein Vorgänger (trotz Prompt) wieder als eigene Zeile auf dem neuen Board, fällt er aus jeder Kette dieses Laufs. Sonst zeigte das Board „KI-Roboter ← ~~Roboter~~" **und** eine Zeile „Roboter" — ein falscher Strich, genau der Fehler, den D1 per Konstruktion ausschließen will. Das ist dieselbe Bedingung wie D1s „key no longer appears as its own entry", angewandt auch auf die geerbte Kette.
4. **Eine bestehende Testerwartung ändert sich:** `tests/test_begriffsboard_lauf.py::test_schema_ist_streng` (`:86-93`) prüft die Feldmenge des Schemas wortgleich auf sieben Namen; D1 verlangt ein achtes Pflichtfeld. Die Erwartung bekommt `"vorheriger_begriff"` dazu — sonst nichts.

Außerdem, ehrlich benannt: „1–3 Wörter" ist **keine Code-Regel**. `_eintrag` (`interview_theater/begriffsboard.py:80-99`) erzwingt nur „genau EIN Begriff nach `begriffe.zerlege`, Whitespace zusammengezogen"; die Wortzahl steht im Prompt. Was ein `vorgaenger`-Element tragen kann, ist per Konstruktion trotzdem eng begrenzt (Aufgabe 2, Schritt „Konstruktion"), aber nicht auf drei Wörter.

## Entscheidungen dieser Planung (FLIP in `ladeBuehne()`)

- **Messen vor dem Tausch, spielen nach dem Tausch — beides in `ladeBuehne()`.** `ladeBuehne()` (`interview_theater/web_vereint.py:1276-1321`) tauscht im Board-Fall `panel.innerHTML = neu` (Zweig `buehnePos === null`). Unmittelbar davor liest `bbMerke(panel)` die alten Zeilen live aus (Schlüssel, `getBoundingClientRect().top`, `details.open`); unmittelbar danach stellt `bbSpiele(panel, vorher)` den Auf-/Zu-Zustand her, misst die neuen Lagen und spielt FLIP. Weil beide Messungen am lebenden Layout erfolgen, braucht es **keinen Lagen-Speicher**, keinen `toggle`/`resize`/`hashchange`-Listener und keinen MutationObserver (der frühere Entwurf brauchte sie nur, weil `_VEREINT_JS` für Dortmund unberührt bleiben musste). `getBoundingClientRect` schließt eine laufende Bewegung ein — ein Tausch mitten in einer Bewegung startet also an der Stelle, an der die Zeile gerade *sichtbar* steht, genau wie FLIP es will.
- **Ohne Board kein Effekt.** Ohne `ol.begriffsboard` im Panel liefert `bbMerke` `null`, und `bbSpiele(panel, null)` kehrt sofort zurück — der Phase-4-Bühnenkarten-Weg (D5) läuft unverändert.
- **Bewegung nur im JS, nicht im CSS.** `css_buehne()` läuft durch `scope_css`; dort darf weder `@media` noch `@keyframes` stehen (`web_gestalt.py`, Modulkopf Regel 3), und eine `transition` im CSS bräuchte einen Selektor im reduced-motion-Block von `css_rahmen()` (Test `tests/test_web_gestalt_css.py::test_reduzierte_bewegung_legt_jeden_bewegten_selektor_stumm` liest nur `css_rahmen`/`css_chat`/`css_stand`/`css_textbuch`, prüfte eine `transition` in `css_buehne` also nicht einmal — umso mehr bleibt sie draußen). Das Skript setzt `style.transition`/`style.transform`/`style.opacity` per CSSOM und fragt vorher `matchMedia('(prefers-reduced-motion: reduce)')`. Das CSS trägt nur Ruhendes: Pfeil und Farbe.
- **„Identität" heißt hier „zugeordnet".** Der Panel-Tausch erzeugt neue Knoten; D3 erlaubt „survives or is matched". Bewiesen wird die Zuordnung im Browser an zwei Wirkungen: das geöffnete „Warum" ist nach dem Tausch an der verschobenen bzw. geschärften Zeile offen, und genau diese Zeilen bekamen ein `translateY(…)`.

---

## Dateiübersicht

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/begriffsboard.py` | 0 (Merge), 2, 3 | `_ein_begriff`, `_vorgaenger`, `_verkette`, `validiere(…, bisher)`, `_eintrag`, `_FELDER`/`SCHEMA`, `_lauf_einmal` |
| `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md` | 3 | Feld `vorheriger_begriff`, Satz zu `vorgaenger`, ein Negativpunkt |
| `interview_theater/web.py` | 4 | `_begriffsboard_html`: `<del>`-Kette, `data-vorgaenger` |
| `interview_theater/web_daten.py` | 4 | nur Docstring von `begriffsboard` (Durchreichen ist per `lies` schon gegeben, Test belegt es) |
| `interview_theater/web_gestalt.py` | 5 | `_BUEHNE` (das CSS hinter `css_buehne()`): drei ruhende Regeln für `.begriffsboard .vorgaenger` |
| `interview_theater/web_vereint.py` | 5 | `_VEREINT_JS`: Helfer `bbSchluessel`/`bbZuordnung`/`bbVersatz`, DOM-Teil `bbMerke`/`bbSpiele`, zwei Zeilen in `ladeBuehne()` |
| `tests/test_begriffsboard_lauf.py` | 3 | eine Erwartung in `test_schema_ist_streng` |
| `tests/test_begriffsboard_schaerfung.py` (neu) | 2, 3 | Kern + Lauf + Prompt |
| `tests/test_begriffsboard_schaerfung_web.py` (neu) | 4 | Darstellung, `web_daten` |
| `tests/test_begriffsboard_flip.py` (neu) | 5 | Node-Tests der Helfer, Skript- und CSS-Regeln |
| `tests/test_web_vereint_bitgleich.py`, `tests/test_werkbank_bitgleich.py` (und jeder weitere `*bitgleich*`-Test, der **nur** an einer Dortmund-/Vorgabe-Fixture rot wird) | 5 | `@pytest.mark.dortmund`, sonst nichts |
| `tests/e2e/test_web_begriffsboard_ranking_e2e.py` (neu) | 6 | Browser + Handy-Screenshot |
| `docs/web-begriffsboard/ranking-2026-10-04.png` (neu) | 6 | der Screenshot für Birk (nur erfundenes Material) |
| `AGENTS.md` | 7 | Modultabelle, „Wo man anfängt", Gestaltung, Übergaben |

**Nicht** angefasst: `web._CSS_BUEHNE`, `web_gestalt.css_rahmen()`, `tests/fixtures/*` (keine Neuerzeugung), `detail_fuer`/`detail_zeilen`/`sende_vorschlag`/`schreibe_detail`, der Phase-4-Zweig von `_buehne_html`, `db.py`/`repo.py`, `web_vereint.seite()` (kein neuer Schalter).

---

### Task 0: Vorbedingung — Schwelle 600 und Zusammenführ-Regel müssen auf `main` committet sein, dann `main` mergen

Die Karte nennt beides „schon in main". Am 04.10.2026 14:33 (Architekt) standen beide nur uncommittet im Haupt-Arbeitsbaum; **seit der Revision ist die Vorbedingung erfüllt**: `main` trägt `07cbd80` (600-Zeichen-Schwelle `IT_BEGRIFFSBOARD_MIN_ZEICHEN` + Zusammenführ-Regel in beiden Prompts) und `4fe89de` (Dortmund eingefroren, Marker `dortmund` in `pyproject.toml`). Beim Schreiben der Revision geprüft: alle drei `git grep`-Befehle aus Step 1 treffen (`main:interview_theater/begriffsboard.py:235`, `main:interview_theater/prompts/begriffsboard.md:26`, `main:interview_theater/sprachen/en/prompts/begriffsboard.md:26`). Die Prüfung bleibt trotzdem als Step 1 stehen — sie kostet nichts. Alle späteren Aufgaben, die `begriffsboard.py` oder die Prompts ändern, sind gegen den Stand **nach** diesem Merge geschrieben (Funktionsnamen statt Zeilennummern).

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
grep -n '"dortmund:' pyproject.toml
git grep -n "mark.dortmund" -- tests
$PY -m pytest tests/test_begriffsboard_lauf.py tests/test_begriffsboard_web.py tests/test_brainstorm.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_vorschlag.py -q -p no:cacheprovider -m "not dortmund"
```

Expected: drei Trefferzeilen; der Marker `"dortmund: Test prueft Dortmund-spezifisches Verhalten, eingefroren seit 04.10.2026"` steht in `pyproject.toml`; `git grep … mark.dortmund` listet, welche Tests eine Parallelkarte schon markiert hat (beim Schreiben der Revision: keine — die Ausgabe für Aufgabe 5/9 notieren); danach `… passed` ohne `failed`. (`tests/test_begriffsboard_mithoeren.py` setzt auf `main` bereits `IT_BEGRIFFSBOARD_MIN_ZEICHEN = "10"`, beim Schreiben der Revision geprüft.)

Kein eigener Commit (der Merge ist der Commit).

---

### Task 1: Baseline der Suite

**Files:** keine (`.suite.log` wird **nicht** committet).

- [ ] **Step 1: Suite im Hintergrund starten und bis zum Ende abwarten**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
```

Der Lauf dauert 5–15 Minuten. Im Hintergrund starten (Shell-Werkzeug mit Hintergrund-Option), auf die Fertigmeldung warten, **nicht abbrechen**, währenddessen keine Codeänderung.

- [ ] **Step 2: Zusammenfassung festhalten**

```bash
tail -n 3 .suite.log
cp .suite.log .suite-baseline.log
IT_WORKSHOP=padua-2026 $PY -m scripts.prompt_schnappschuss /tmp/t_cb2c4678-padua-prompts-vorher.txt
```

Der letzte Befehl legt den Padua-Prompt-Fingerabdruck **vor** jeder Codeänderung ab (Expected: `<N> Zeichen nach /tmp/t_cb2c4678-padua-prompts-vorher.txt (Profil: padua-2026)`); Aufgabe 11 vergleicht dagegen.

Expected (Suite): eine Zeile der Form `NNNN passed, NN skipped, NN deselected[, N failed] in …s` und `EXIT 0` (oder `EXIT 1`, falls schon vorher Tests rot sind). Diese Zeile wörtlich für den Abschlussbericht notieren. Sind schon in der Baseline Tests rot: ihre Namen (`grep -E "^FAILED|^ERROR" .suite.log`) notieren — sie sind dann **nicht** Folge dieser Karte und werden im Bericht so benannt.

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
$PY -m pytest tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard.py tests/test_begriffsboard_mithoeren.py -q -p no:cacheprovider -m "not dortmund"
$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/begriffsboard.md
$PY -m pytest tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py -q -p no:cacheprovider -m "not dortmund"
```

Expected: `… passed` ohne `failed`; Prüfer `0 Treffer`; die beiden Prompt-Bitgleich-Tests grün oder — falls einer **nur** wegen des Dortmund-/Vorgabe-Massstabs am geänderten Begriffsboard-Prompt rot wird — mit `@pytest.mark.dortmund` auf genau diesem Test (Vorgehen wie Aufgabe 5, Step 6), **nicht** angepasst und **kein** Schnappschuss neu erzeugt. ANNAHME: erwartet ist grün — der Begriffsboard-Prompt ist erst nach beiden Massstäben entstanden, und `test_sprache_bitgleich.py` erlaubt ausdrücklich neue Abschnitte (Docstring); für `test_profil_bitgleich.py` beim Lauf prüfen.

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
        # (``web_gestalt.css_buehne``), nie aus einem style-Attribut.
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

Docstring von `_begriffsboard_html` um einen Satz ergänzen: „Eine Schärfungskette (`vorgaenger`, Karte t_cb2c4678) steht durchgestrichen hinter dem Begriff, der jüngste zuerst, und als `data-vorgaenger` am `<li>` — für die FLIP-Zuordnung im Browser (`ladeBuehne()` in `web_vereint._VEREINT_JS`)." Docstring von `web_daten.begriffsboard`: „… OHNE `zitat` … `vorgaenger` (nur Begriffswortlaut, Karte t_cb2c4678) geht mit."

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

### Task 5: Live-Ranking — FLIP direkt in `ladeBuehne()`, CSS im CoThinker-CSS

**Files:**
- Modify: `interview_theater/web_vereint.py` (`_VEREINT_JS`: fünf neue Funktionen direkt **vor** `function ladeBuehne()`; zwei Zeilen im Zweig `if (buehnePos === null)` von `ladeBuehne()`)
- Modify: `interview_theater/web_gestalt.py` (`_BUEHNE`, das CSS hinter `css_buehne()`: drei Regeln ans Ende)
- Test: `tests/test_begriffsboard_flip.py` (neu)
- Modify (nur Marker): `tests/test_web_vereint_bitgleich.py`, `tests/test_werkbank_bitgleich.py` — und jeder weitere `*bitgleich*`-Test, der **nur** an einer Dortmund-/Vorgabe-Fixture rot wird (Step 6)

**Interfaces:**
- Consumes: Markup-Vertrag aus Aufgabe 4 (`ol.begriffsboard > li[data-begriff][data-vorgaenger]`, `<details>` je Zeile); `ladeBuehne()` mit `panel` (= `#tab-buehne`), `neu`, `buehnePos`.
- Produces (alle in `_VEREINT_JS`, im IIFE-Rumpf):
  - reine Helfer: `bbSchluessel(text) -> string`, `bbZuordnung(alt: string[], neu: {begriff, vorgaenger}[]) -> (string|null)[]`, `bbVersatz(altLagen: {schluessel: number}|null, quellen: (string|null)[], neuLagen: number[]) -> (number|null)[]`;
  - DOM-Teil: `bbMerke(panel) -> {alt: string[], lagen: {schluessel: number}, offen: {schluessel: true}} | null` und `bbSpiele(panel, vorher) -> void`;
  - `ladeBuehne()` ruft `var bbVorher = bbMerke(panel);` unmittelbar vor und `bbSpiele(panel, bbVorher);` unmittelbar nach `panel.innerHTML = neu;`.
  - `css_buehne()` enthält zusätzlich `.begriffsboard .vorgaenger { … }`, `…::before { content: "\2190\00a0"; }`, `… del { … }` — ohne `@media`, `@keyframes`, `transition`, `animation`, Hexfarbe.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_begriffsboard_flip.py`:

```python
"""Karte t_cb2c4678, Aufgabe 5: Live-Ranking ohne Springen (D3), direkt in
``ladeBuehne()``. Die reinen Helfer werden wie in
``tests/test_buehne_nav_js.py`` per Klammertiefe aus ``_VEREINT_JS``
geschnitten und unter Node gerufen."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_gestalt, web_vereint

NODE = shutil.which("node")
_HELFER = ("bbSchluessel", "bbZuordnung", "bbVersatz")


def _extrahiere(skript: str, name: str) -> str:
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _VEREINT_JS gefunden"
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
    return "\n".join(_extrahiere(web_vereint._VEREINT_JS, n) for n in _HELFER)


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


# -- Einhaengung in ladeBuehne(), CSP, reduced motion -------------------------

def test_ladebuehne_merkt_vor_dem_tausch_und_spielt_danach():
    js = web_vereint._VEREINT_JS
    lade = _extrahiere(js, "ladeBuehne")
    merke = lade.index("var bbVorher = bbMerke(panel);")
    tausch = lade.index("panel.innerHTML = neu;")
    spiele = lade.index("bbSpiele(panel, bbVorher);")
    assert merke < tausch < spiele
    # Der Phase-4-Weg (zurueckgeblaettert) bleibt unangetastet: nur im
    # Zweig "aktuell" wird getauscht und damit gespielt.
    zweig = lade[lade.index("if (buehnePos === null) {"):spiele]
    assert "panel.innerHTML = neu;" in zweig


def test_ohne_board_tun_die_funktionen_nichts():
    js = web_vereint._VEREINT_JS
    merke = _extrahiere(js, "bbMerke")
    spiele = _extrahiere(js, "bbSpiele")
    assert "ol.begriffsboard" in merke and "return null" in merke
    assert spiele.index("if (!vorher") < spiele.index("querySelector")


def test_skript_haelt_die_csp_und_die_ruhe():
    js = web_vereint._VEREINT_JS
    teil = "\n".join(_extrahiere(js, n) for n in _HELFER + ("bbMerke", "bbSpiele"))
    assert "style=" not in teil and "setAttribute('style'" not in teil
    assert re.search(r"\son\w+=", teil) is None
    assert "prefers-reduced-motion: reduce" in teil
    assert ".style.transform" in teil and ".style.transition" in teil
    assert "innerHTML" not in teil            # der Tausch bleibt allein ladeBuehne()s
    assert "MutationObserver" not in teil     # kein Beobachter-Umweg


def test_css_ist_ruhend_ohne_media_und_ohne_hexfarbe():
    css = web_gestalt.css_buehne()
    teil = css[css.index(".begriffsboard .vorgaenger"):]
    for verboten in ("@media", "@keyframes", "transition", "animation", "url("):
        assert verboten not in teil, verboten
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", teil) is None
    assert "var(--text-leise)" in teil
    # Ueberlebt das Scoping wie der Rest von css_buehne():
    assert ".panel-buehne .begriffsboard .vorgaenger" in web_vereint.scope_css(css, ".panel-buehne")
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_flip.py -q -p no:cacheprovider`
Expected: FAIL — `AssertionError: bbSchluessel nicht in _VEREINT_JS gefunden` (bzw. `ladeBuehne` ohne `bbMerke`) und `ValueError: substring not found` in `test_css_ist_ruhend_…`. ANNAHME: `scope_css` setzt den Scope mit einem Leerzeichen davor (`.panel-buehne .begriffsboard …`); wenn nicht, die letzte Assertion an die tatsächliche Form von `web_vereint._ein_selektor` angleichen (Ausgabe ansehen), nicht weglassen.

- [ ] **Step 3: CSS** — in `interview_theater/web_gestalt.py` ans Ende des Strings `_BUEHNE` (vor dem schließenden `"""`, ~Z. 1325 ff.) anhängen:

```css
/* Begriffsboard (Karte t_cb2c4678): die Schaerfungskette steht leise und
   durchgestrichen hinter dem Begriff, der Pfeil zeigt vom alten Wortlaut
   zum neuen. Nur Ruhendes: die Bewegung (FLIP) setzt ladeBuehne() per
   CSSOM und nur ohne prefers-reduced-motion -- hier steht weder
   transition noch @media (dieser Block laeuft durch scope_css). */
.begriffsboard .vorgaenger { color: var(--text-leise); margin-left: 0.4em; }
.begriffsboard .vorgaenger::before { content: "\2190\00a0"; }
.begriffsboard .vorgaenger del { text-decoration-thickness: 1px; }
```

Im Python-Quelltext: `_BUEHNE` ist ein gewöhnlicher (nicht roher) String — die Backslashes deshalb verdoppeln: `content: "\\2190\\00a0";`. Kontrolle: `$PY -c "from interview_theater import web_gestalt; print([z for z in web_gestalt.css_buehne().splitlines() if 'before' in z and 'vorgaenger' in z])"` → `['.begriffsboard .vorgaenger::before { content: "\\2190\\00a0"; }']` (in der `repr`-Ausgabe erscheinen die Backslashes verdoppelt; im CSS steht einer). `--text-leise` auf `--grund` steht schon in `web_gestalt.KONTRAST` (4.5).

- [ ] **Step 4: Skript** — in `interview_theater/web_vereint.py`, `_VEREINT_JS`, direkt **vor** `  function ladeBuehne() {` einfügen (Einrückung zwei Leerzeichen wie die Nachbarn; `_VEREINT_JS` ist kein Roh-String — in der Regex `\\s` schreiben, damit im JS `\s` ankommt):

```js
  // -- Begriffsboard: Live-Ranking ohne Springen (Karte t_cb2c4678) -------
  //
  // ladeBuehne() tauscht das ganze Panel (panel.innerHTML = neu). Damit die
  // Liste dabei nicht springt, misst bbMerke() die alten Zeilen UNMITTELBAR
  // davor und bbSpiele() spielt UNMITTELBAR danach FLIP: jede Zeile startet
  // optisch an ihrer alten Stelle und gleitet an die neue. Zuordnung ueber
  // data-begriff, fuer einen geschaerften Begriff ueber data-vorgaenger.
  // Ein offenes "Warum" (<details>) bleibt offen. Ohne ol.begriffsboard
  // (Phase 4, Buehnenkarten) tun beide nichts. Bewegung nur per CSSOM (CSP)
  // und nie bei prefers-reduced-motion: reduce.
  var BB_DAUER_MS = 320;

  function bbSchluessel(text) {
    return String(text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  }

  // Je neuem Eintrag der Schluessel der alten Zeile, von der er kommt, oder
  // null (neu). Erst ueber den eigenen Begriff, dann ueber den juengsten
  // Vorgaenger -- nur, wenn diese alte Zeile nicht schon vergeben ist.
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

  function bbMerke(panel) {
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return null; }
    var vorher = { alt: [], lagen: {}, offen: {} };
    Array.prototype.forEach.call(ol.children, function (li) {
      var b = li.getAttribute('data-begriff');
      var k = bbSchluessel(b);
      var d = li.querySelector('details');
      vorher.alt.push(b);
      vorher.lagen[k] = li.getBoundingClientRect().top;
      if (d && d.open) { vorher.offen[k] = true; }
    });
    return vorher;
  }

  function bbSpiele(panel, vorher) {
    if (!vorher) { return; }
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return; }
    var lis = Array.prototype.slice.call(ol.children);
    var quellen = bbZuordnung(vorher.alt, lis.map(function (li) {
      return { begriff: li.getAttribute('data-begriff'),
               vorgaenger: li.getAttribute('data-vorgaenger') };
    }));
    // Erst den Auf-/Zu-Zustand zurueck, DANN messen: ein offenes "Warum"
    // verschiebt alle Zeilen darunter.
    quellen.forEach(function (q, i) {
      var d = lis[i].querySelector('details');
      if (d && q !== null && vorher.offen[q]) { d.open = true; }
    });
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    var versatz = bbVersatz(vorher.lagen, quellen, lis.map(function (li) {
      return li.getBoundingClientRect().top;
    }));
    lis.forEach(function (li, i) {
      if (quellen[i] === null) { li.style.opacity = '0'; }
      else if (versatz[i]) { li.style.transform = 'translateY(' + versatz[i] + 'px)'; }
    });
    ol.getBoundingClientRect();   // Startlage festschreiben (Reflow)
    requestAnimationFrame(function () {
      lis.forEach(function (li) {
        li.style.transition = 'transform ' + BB_DAUER_MS + 'ms ease, opacity '
          + BB_DAUER_MS + 'ms ease';
        li.style.transform = '';
        li.style.opacity = '';
      });
      setTimeout(function () {
        lis.forEach(function (li) { li.style.transition = ''; });
      }, BB_DAUER_MS + 50);
    });
  }

```

und in `ladeBuehne()` den Zweig

```js
          if (buehnePos === null) {
            // "Aktuell": komplett ersetzen -- sicher, weil
            // buehneNavRender() den (absichtlich leeren) Nav-Platzhalter
            // sofort danach selbst fuellt (siehe web._buehne_html).
            panel.innerHTML = neu;
          }
```

ersetzen durch

```js
          if (buehnePos === null) {
            // "Aktuell": komplett ersetzen -- sicher, weil
            // buehneNavRender() den (absichtlich leeren) Nav-Platzhalter
            // sofort danach selbst fuellt (siehe web._buehne_html). Das
            // Begriffsboard (Phase 1) gleitet dabei per FLIP an seine neue
            // Ordnung, statt zu springen (bbMerke/bbSpiele, oben).
            var bbVorher = bbMerke(panel);
            panel.innerHTML = neu;
            bbSpiele(panel, bbVorher);
          }
```

- [ ] **Step 5: Grün laufen lassen + Syntax + Nachbarn**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py tests/test_buehne_nav_js.py tests/test_web_vereint_js_syntax.py tests/test_web_gestalt_css.py tests/test_begriffsboard_web.py tests/test_web_vereint.py -q -p no:cacheprovider -m "not dortmund"
```

Expected: `… passed`, kein `failed` (die Node-Tests `skipped`, falls kein `node` auf PATH — dann im Bericht „Node-Tests nicht gelaufen", **nicht** „grün").

- [ ] **Step 6: Bitgleich-Tests — Rot nur wegen Dortmund? Dann Marker, sonst Fehler suchen**

```bash
git grep -n "mark.dortmund" -- tests
$PY -m pytest tests/ -q -p no:cacheprovider -k "bitgleich" -rf
```

Expected: `tests/test_web_vereint_bitgleich.py::test_vereinte_seite_bleibt_byte_gleich[None|dortmund-2026]` und `tests/test_werkbank_bitgleich.py::test_ohne_schalter_bleibt_die_werkbank_byte_gleich[None|dortmund-2026]` sind rot — sie vergleichen die ganze vereinte Seite (samt `_VEREINT_JS` und `css_buehne()`) mit `tests/fixtures/web_vereint_dortmund_vorher.html` bzw. `werkbank_vorher_vereint_*`. Jeder andere `*bitgleich*`-Test bleibt grün; ist einer rot, der **nicht** an einer `*dortmund*`/`*vorgabe*`-Fixture vergleicht, ist das ein Fehler dieser Aufgabe.

Nachweis, dass das Rot **nur** Dortmund ist (Blick, kein formales Tor):

```bash
env -u IT_WORKSHOP $PY - <<'EOF'
import difflib, sys
sys.path.insert(0, ".")
from interview_theater import sprache, workshop
from tests import test_web_vereint_bitgleich as t
workshop.vergiss(); sprache.vergiss()
t._baue_datenbank()
alt = t.VORHER.read_text(encoding="utf-8").splitlines()
neu = t._rendere().splitlines()
for z in difflib.unified_diff(alt, neu, lineterm="", n=0):
    if z[:1] in "+-" and z[:3] not in ("+++", "---"):
        print(z[:110])
EOF
```

Expected: jede Zeile gehört zu `bbSchluessel`/`bbZuordnung`/`bbVersatz`/`bbMerke`/`bbSpiele`, zu den zwei neuen Zeilen in `ladeBuehne()` (plus deren Kommentar) oder zu den drei `.begriffsboard .vorgaenger`-CSS-Regeln — sonst nichts. Die Ausgabe (oder ihre ersten ~60 Zeilen) geht in den Bericht.

Dann — **nur** für Tests, die `git grep` oben noch nicht als markiert zeigt — den Marker direkt über die Testfunktion setzen, sonst nichts ändern (keine Fixture neu erzeugen, keine Erwartung anpassen):

```python
@pytest.mark.dortmund  # Dortmund eingefroren (AGENTS.md, 04.10.2026): vergleicht gegen eine Dortmund-/Vorgabe-Fixture
@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_vereinte_seite_bleibt_byte_gleich(monkeypatch, profil):
```

(dasselbe über `test_ohne_schalter_bleibt_die_werkbank_byte_gleich` in `tests/test_werkbank_bitgleich.py`). Danach:

```bash
$PY -m pytest tests/ -q -p no:cacheprovider -k "bitgleich" -m "not dortmund"
```

Expected: `… passed, … deselected`, kein `failed`. Trägt `main` den Marker inzwischen schon (`git grep -n "mark.dortmund" main -- tests`), trotzdem hier setzen — dieselbe Decorator-Zeile auf beiden Seiten löst die spätere [Merge]-Karte trivial.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/web_vereint.py interview_theater/web_gestalt.py tests/test_begriffsboard_flip.py tests/test_web_vereint_bitgleich.py tests/test_werkbank_bitgleich.py
git commit -m "Begriffsboard: FLIP-Live-Ranking in ladeBuehne(), Schaerfungs-CSS im CoThinker; Dortmund-Bitgleich markiert (t_cb2c4678, Aufgabe 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Nur die Testdateien `git add`-en, an denen Step 6 wirklich einen Marker gesetzt hat.)

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

### Task 7: AGENTS.md (Teil 1)

Die Abschluss-Suite und der Bericht stehen für beide Teile in **Aufgabe 11**. Hier wird nur die Doku für Teil 1 nachgezogen.

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: AGENTS.md nachziehen** — vier Stellen, Wortlaut sinngemäß, im Stil des Dokuments:

(a) Modultabelle, Zeile `begriffsboard.py`: an das Ende der Zelle anhängen:
„Seit 04.10.2026 (Karte t_cb2c4678) die **Schärfung**: Pflichtfeld `vorheriger_begriff` im Schema, im Code gegen das bisherige Board geprüft (`validiere(…, bisher)`, `_verkette` — nur ein Begriff, der wirklich verschwand, keine Ähnlichkeitsheuristik); daraus die Kette `vorgaenger` (älteste zuerst, nur am Eintrag, wenn nicht leer, nie im Schema, nie Modelltext). Im CoThinker durchgestrichen (`web._begriffsboard_html`, `data-vorgaenger`), Live-Ranking per FLIP direkt in `ladeBuehne()` (`_VEREINT_JS`: `bbMerke` vor, `bbSpiele` nach dem Panel-Tausch; ohne `ol.begriffsboard` wirkungslos)."

(b) „Wo man anfängt": neue Zeile
`| Warum ist ein Begriff durchgestrichen (oder nicht)? | begriffsboard.validiere → _verkette → web._begriffsboard_html → web_vereint._VEREINT_JS (ladeBuehne → bbMerke/bbSpiele) |`

(c) Abschnitt „Die Gestaltung": ein Satz, dass `css_buehne()` (`_BUEHNE`) seit dem 04.10.2026 auch die ruhende Darstellung der Schärfungskette trägt (`.begriffsboard .vorgaenger`, Pfeil per `::before`) — **ohne** Bewegung im CSS; die setzt `ladeBuehne()` per CSSOM und nur ohne `prefers-reduced-motion`. Keine neue Einhängezeile, kein neuer Schalter.

(d) „Die Übergaben der Karte t_4517d4ad (Begriffsboard …)": zwei Punkte anhängen:
- „**Ungemessen (t_cb2c4678):** kein bezahlter Lauf für `vorheriger_begriff` — ob Kimi/Opus das Feld zuverlässig füllen, weiß niemand. Vergisst das Modell es, fehlt nur der Strich; die Begründung erzählt die Entwicklung trotzdem."
- „Die Wortzahl „1–3" eines Begriffs (und damit eines Vorgängers) steht im Prompt, nicht im Code; der Code garantiert „ein Begriff, früher schon auf dem Board"."

- [ ] **Step 1b: Nachweis (Architekt-Ergänzung)**

```bash
grep -c "vorheriger_begriff" AGENTS.md          # Expected: >= 2 (Modultabelle + Uebergabe)
grep -n "bbMerke/bbSpiele" AGENTS.md             # Expected: genau 1 Trefferzeile ("Wo man anfaengt")
grep -n "Ungemessen (t_cb2c4678)" AGENTS.md      # Expected: genau 1 Trefferzeile
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "Begriffsboard: AGENTS.md -- Schaerfung, FLIP in ladeBuehne, Uebergaben (t_cb2c4678, Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

# Teil 2: Pause weg, Endstand = Zwischenstand (Birk, 04.10.2026 14:50)

**Birks Entscheidung, wörtlich (Kartennachtrag):**
1. Den Pause-Knopf des Mithörens in Phase 1 vollständig entfernen. Es bleiben nur Start („Start listening") und Fertig („Discussion done"). Interview-Pause (`#interview-pause`, `pausiereInterview`) und Brainstorm-Pause (Phase 4) bleiben unberührt; `_TEXT_INTERVIEW_PAUSE` bleibt (das Interview braucht ihn).
2. „Bei Abschluss kann Ergebnis als Zwischenstand direkt kommen. Wenn es weitergeht aendert sich der Stand. Zwischenstand und Endstand muessen nicht anders behandelt werden."

**Goal (Teil 2):** Phase 1 hat nur noch Start und Fertig; das Begriffsboard kennt keinen eigenen Abschlusspfad mehr — der Ende-Schnitt ist ein gewöhnlicher Schnitt unter derselben Regel (600 Zeichen), und „Discussion done" zeigt den Top-5-Vorschlag mit dem Board, wie es ist.

**Architecture (Teil 2):** `begriffsboard.soll_laufen(conn, chat_id)` verliert `ist_abschluss` und behandelt `'ende'` wie `'pause'` (ohne Mindestabstand, Begründung unten); `nach_segment` entscheidet bei Fertig neu, sobald ein laufender Lauf endet (`merke_falls_laeuft`). `brainstorm.soll_reagieren` und der Phase-4-Pfad bleiben Zeichen für Zeichen. In `web_chat.py` fallen `#diskussion-pause`, `pausiereDiskussion`/`fortsetzeDiskussion`, `diskussionPauseKnopf`, `data-pausiert` an `#diskussion` und die nur der Diskussions-Pause dienenden Zweige weg. Dass dieser Code auch in Dortmunds (eingefrorener) Seite steht, ändert daran nichts: die Dortmund-Bitgleich-Tests tragen seit Aufgabe 5 `@pytest.mark.dortmund`, keine Fixture wird neu erzeugt (Revision 04.10.2026).

## Global Constraints (Teil 2, zusätzlich zu oben)

- **Dortmund eingefroren (Revision):** `tests/fixtures/web_vereint_dortmund_vorher.html` und `tests/fixtures/werkbank_vorher_vereint_vorgabe.html`/`…_dortmund-2026.html` enthalten den Diskussions-Pause-Code (versteckter Knopf, unbedingt ausgeliefertes `_CHAT_JS`; z. B. `web_vereint_dortmund_vorher.html:903, 905, 1905, 3981, 4034, 4056, 4401`). Er wird trotzdem **vollständig entfernt** (kein profilgeschalteter toter Code). Die Fixtures werden **nicht** neu erzeugt; die Tests, die gegen sie vergleichen, sind seit Aufgabe 5 mit `@pytest.mark.dortmund` markiert — Aufgabe 9 prüft nur, dass das so bleibt und dass kein weiterer Test aus anderem Grund rot wird.
- `tests/test_profil_bitgleich.py` (Prompt-Fingerabdruck, Dortmund-Massstab) ist kein Abnahmekriterium mehr; Teil 2 ändert keinen Prompt, er bleibt also ohnehin grün. Würde er **nur** aus Dortmund-Gründen rot: Marker, keine Anpassung.
- Unberührt: `brainstorm.soll_reagieren` (Signatur und Verhalten, inkl. des mit Aufgabe 0 gemergten `min_zeichen_override`), `aufnahme._brainstorm_abschliessen`, `#interview-pause`/`pausiereInterview`/`fortsetzeInterview`, `#brainstorm-pause`/`pausiereBrainstorm`/`fortsetzeBrainstorm`, `_TEXT_INTERVIEW_PAUSE`/`_WEITER`/`_PAUSIERT`, `beginneAufnahme` (sein `if (sitzung.pausiert)` dient Interview und Brainstorm), `formatiereUhr`.
- `diskussion.starte` (Verdichtung) startet weiter auf `schnittgrund == 'ende'` in `aufnahme._diskussion_abschliessen` — unverändert.

## Abwägung Abschlusspfad

**Belegte Fakten (gegen den Stand nach Aufgabe 0 geprüft, Zeilen aus dem Worktree vor dem Merge):**

- `brainstorm.soll_reagieren` ohne `ist_abschluss` löst nur aus, wenn `letzter_schnittgrund == "pause"` **und** `unreagierte_zeichen >= min_zeichen` **und** `sekunden_seit_letzter_reaktion >= min_abstand_s()` (`interview_theater/brainstorm.py:68-74`; nach dem Merge mit `min_zeichen_override`, siehe Diff in Aufgabe 0). `min_abstand_s()` ist 90 s (`brainstorm.py:22`).
- `repo.begriffsboard_stand` zählt die Zeichen aller Diskussionssegmente **seit `bis_aufnahme_id` des letzten Boards** und liefert den Schnittgrund des **jüngsten** davon (`repo.py`, `begriffsboard_stand`; Test `tests/test_repo_begriffsboard.py::test_stand_zaehlt_nur_diskussionssegmente_nach_der_markierung`).
- Das letzte Segment trägt `'ende'` nur aus `beendeDiskussion()` — **und bis heute auch aus `pausiereDiskussion()`** (`interview_theater/web_chat.py:2861` und `:2915`, je `if (… && sitzung.vadAktiv) { …_grund = 'ende' … }`). Server: `aufnahme._diskussion_abschliessen` macht aus jedem `'ende'` den Vorschlag **und** einen Verdichtungslauf (`interview_theater/aufnahme.py:980-988`). Heute löst also **jede Pause** einen Top-5-Vorschlag und eine Verdichtung aus — mit dem Wegfall der Pause gibt es `'ende'` nur noch einmal, bei „Discussion done".
- Ohne Pausenschnitt (Dauerrede, harte Schnitte `'cap'` nach `IT_WEB_VAD_MAX_MS`) läuft das Board laufend **nie** (`tests/e2e/test_web_diskussion_e2e.py:97-102`: mit dem Chromium-Dauerton tragen alle Segmente `'cap'`).
- Daten zum Sprechtempo: ~16 Zeichen/s, ein Gedanke median 614 Zeichen (`interview_theater/brainstorm.py:9-11`, gemessen an **Erwachsenen**-Meetings).

**Wird der Sonderpfad einfach gelöscht**, kann das `'ende'`-Segment nie einen Lauf auslösen (es ist kein `'pause'`), und alles seit dem letzten Pausen-Lauf erreicht das Board nie — auch über 600 Zeichen, auch die ganze Diskussion, wenn alle Schnitte `'cap'` waren.

| Option | Was bei „Discussion done" passiert | Was verloren geht | Eigene Regel? |
|---|---|---|---|
| **A** kein Lauf bei Fertig | nur der Vorschlag mit dem Board von zuletzt | alles seit dem letzten Pausen-Lauf, **unbegrenzt** (bei nur `'cap'`-Schnitten: alles) | nein |
| **B** `'ende'` zählt als gewöhnlicher Schnitt, gleiche Schwelle 600 | Lauf, wenn ≥ 600 unreagierte Zeichen; danach der Vorschlag | ein Rest **unter** 600 Zeichen ≈ **unter ~37 s Rede** (600 ÷ 16 Zeichen/s) | nein — eine Regel, eine Schwelle |
| **C** jeder Rest > 0 löst aus | Lauf schon bei wenigen Wörtern | nichts | **ja** — eine eigene Schwelle (> 0) nur für Fertig, genau der Sonderpfad, den Birk streicht |

**Gewählt: B.** Es ist wörtlich „Endstand = Zwischenstand": der Ende-Schnitt durchläuft dieselbe Regel mit derselben Schwelle wie jeder Pausenschnitt, und ein großer Rest wird nicht weggeworfen. Was B verliert — ein Rest unter 600 Zeichen, nach den Erwachsenen-Daten unter rund 37 Sekunden Rede (ANNAHME: Schülerinnen und Schüler sprechen nicht wesentlich langsamer; ungemessen) — ist nach Birks Satz hingenommen: der Zwischenstand ist der Endstand. A verliert bis zur ganzen letzten Strecke, C führt den gestrichenen Sonderpfad unter anderem Namen wieder ein.

**Mindestabstand bei `'ende'`: gilt nicht.** `min_abstand_s` (90 s) drosselt Läufe, *während* weitergeredet wird; ein abgewiesener Lauf verliert dort nichts, „die Zeichen laufen weiter auf" (`begriffsboard.py`, `_lauf_einmal`-Kommentar; `brainstorm.py` Kopf). Beim Ende-Schnitt kommt kein weiterer Schnitt mehr, der das Aufgeschobene nachholt — Aufschieben hieße dort Verwerfen, im schlimmsten Fall von weit mehr als 600 Zeichen (Lauf vor 80 s, danach 70 s Rede ≈ 1 100 Zeichen). Schwelle und Schnittbedingung bleiben dieselben; nur die Wartezeit, deren Zweck am Ende entfällt, fällt weg. Umgesetzt **in `begriffsboard.soll_laufen`** (`'ende'` → wie `'pause'`, Sekunden → ∞), `brainstorm.soll_reagieren` bleibt unverändert.

**Ein laufender Lauf bei „Discussion done".** Heute (`nach_segment`) kommt der Vorschlag sofort, wenn kein Schlusslauf nötig ist — auch wenn gerade ein regulärer Lauf läuft, also mit dem Board **vor** diesem Lauf; und ist ein Schlusslauf nötig, aber einer läuft schon, merkt `nimm_oder_merke` nur den Vorschlag, der Rest seit dessen Markierung (`bis_id` wird **vor** dem Lauf gelesen) bliebe ungelesen. Birk: „with the board AS IT IS (if a regular run is in flight, after it)". Deshalb merkt `nach_segment` bei Fertig, wenn ein Lauf unterwegs ist, **sich selbst** (`merke_falls_laeuft`) und entscheidet nach dessen Ende neu — dieselbe Regel B auf den dann aktuellen Zahlen. Kein eigener Pfad: es ist derselbe Aufruf, nur später.

**Bestätigt: der Ende-Schnitt kommt weiter aus `beendeDiskussion()`** (`web_chat.py:2915`) — der Test `test_fertig_setzt_weiter_den_grund_ende` (Aufgabe 9) hält es fest. Er gilt, wie bisher, **nur mit aktivem VAD** (`sitzung.vadAktiv`); siehe Befund 1 unten.

**Befunde, außerhalb dieser Karte (nicht behoben, in AGENTS.md als Übergabe):**
1. Ohne VAD (Rückfall auf den festen Takt, `web_chat.py:2413`) trägt kein Segment einen Schnittgrund — Phase 1 macht dann weder Board-Läufe noch Vorschlag noch Verdichtung. Das war vor dieser Karte genauso (Test `tests/test_web_chat_js.py::test_der_grund_ende_wird_nur_mit_aktivem_vad_gesetzt` hält die Wache absichtlich fest).
2. Hat das letzte Teilstück bei „Discussion done" keine Bytes, wird es nicht hochgeladen (`web_chat.py` `r.onstop`: `if (teile.length && …)`) — dann kommt kein `'ende'` beim Server an. Ebenfalls vorher schon so.

## Dateiübersicht (Teil 2)

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/begriffsboard.py` | 8 | `soll_laufen(conn, chat_id)`, `merke_falls_laeuft`, `nach_segment`, Moduldocstring |
| `interview_theater/aufnahme.py` | 8 | nur Docstring von `_diskussion_abschliessen` |
| `tests/test_begriffsboard_abschluss.py` (neu) | 8 | B, Mindestabstand, laufender Lauf, Mutant |
| `tests/test_begriffsboard_lauf.py`, `tests/test_begriffsboard_vorschlag.py`, `tests/test_begriffsboard_mithoeren.py` | 8 | anpassen bzw. löschen (Liste unten) |
| `interview_theater/web_chat.py` | 9 | Pause des Mithörens weg (Markup, JS, Kommentare) |
| `tests/test_web_chat_diskussion_ohne_pause.py` (neu) | 9 | Markup/JS ohne Pause, Ende-Schnitt, Interview/Brainstorm-Pause bleiben |
| `tests/test_web_chat_js.py`, `tests/test_web_chat_diskussion_knopf.py` | 9 | anpassen bzw. löschen (Liste unten) |
| `tests/fixtures/*` | — | **nicht** angefasst (Dortmund eingefroren) |
| weitere `*bitgleich*`-Tests, falls **nur** an einer Dortmund-/Vorgabe-Fixture rot | 9 | `@pytest.mark.dortmund` |
| `tests/e2e/test_web_diskussion_e2e.py` | 10 | Schlusslauf-Annahme raus, Start+Fertig belegt |
| `AGENTS.md` | 11 | Diskussionsknöpfe, Auslöser (D1/D6), Übergaben |

## Vollständige Testliste Teil 2 (die Autorität, neu gegrept)

Gegrept mit `grep -rn "ist_abschluss\|diskussion-pause\|pausiereDiskussion\|fortsetzeDiskussion\|diskussionPauseKnopf\|data-pausiert\|MIN_ZEICHEN_BEI_ABSCHLUSS\|min_zeichen_bei_abschluss\|_grund = 'ende'\|beginneAufnahme(sitzung);" tests` plus Lesen jeder Fundstelle. ANNAHME: Zeilennummern sind die des Worktrees **vor** dem Merge aus Aufgabe 0; der Merge ändert in `tests/test_begriffsboard_lauf.py` die Umgebungsvariablen und die erwarteten kwargs (Diff in Aufgabe 0), nicht die Testnamen.

| Datei::Test | Änderung | Aufgabe |
|---|---|---|
| `tests/test_begriffsboard_lauf.py::test_unter_der_zeichenschwelle_kein_lauf` | anpassen: `soll_laufen(conn, CHAT)` statt `…, ist_abschluss=False)` | 8 |
| `tests/test_begriffsboard_lauf.py::test_ueber_der_schwelle_nach_pause_laeuft` | anpassen: dito | 8 |
| `tests/test_begriffsboard_lauf.py::test_cap_schnitt_loest_nicht_aus` | anpassen: dito | 8 |
| `tests/test_begriffsboard_lauf.py::test_mindestabstand_nach_einem_lauf` | anpassen: dito | 8 |
| `tests/test_begriffsboard_lauf.py::test_abschluss_mit_niedriger_schwelle` | **löschen** (prüft genau den gestrichenen Pfad; ersetzt durch `test_keine_eigene_abschlussschwelle` + Mutant) | 8 |
| `tests/test_begriffsboard_lauf.py::test_soll_laufen_ruft_brainstorm_soll_reagieren_unveraendert` | anpassen: Aufruf ohne `ist_abschluss`; erwartete kwargs bleiben (`ist_abschluss: False`, `min_zeichen_override: begriffsboard.min_zeichen()`) | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_leeres_board_heutiger_text` | anpassen: `IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS` → `IT_BEGRIFFSBOARD_MIN_ZEICHEN` (Wert 100000) | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_ohne_schlusslauf_sofort_die_top_fuenf_mit_einem_knopf` | anpassen: dito (100000) | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_mit_schlusslauf_kommt_der_vorschlag_erst_danach` | anpassen: dito (Wert 10) — der „Schlusslauf" ist jetzt der reguläre Lauf auf dem Ende-Schnitt; Docstring/Kommentar entsprechend | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_gescheiterter_schlusslauf_nimmt_das_aktuelle_board` | anpassen: dito (10) | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_gesamtverdichtung_startet_unabhaengig` | anpassen: dito (100000) | 8 |
| `tests/test_begriffsboard_vorschlag.py::test_take_these_speichert_begriffe_und_detail_einmal` | anpassen: dito (100000) | 8 |
| `tests/test_begriffsboard_mithoeren.py` (autouse-Fixture `aktiv`, alle 7 Tests der Datei) | anpassen: Zeile `IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS = "10"` → `IT_BEGRIFFSBOARD_MIN_ZEICHEN = "10"` (steht die Zeile nach dem Merge schon da: nur die Abschluss-Zeile löschen) | 8 |
| `tests/test_begriffsboard_abschluss.py` (8 Tests) | **neu** | 8 |
| `tests/test_web_chat_js.py::test_manuelle_schnitte_tragen_den_grund_ende` | anpassen: `== 6` → `== 5`, Kommentar ohne `pausiereDiskussion` | 9 |
| `tests/test_web_chat_js.py::test_beginneaufnahme_ist_der_einzige_ort_der_die_aufnahme_beginnt` | anpassen: `beginneAufnahme(sitzung);`-Zählung `== 6` → `== 5`, Kommentar ohne `fortsetzeDiskussion` | 9 |
| `tests/test_web_chat_js.py::test_der_diskussion_knopf_steht_immer_im_markup_aber_hidden_ausserhalb_phase_1` | anpassen: Kennungen ohne `diskussion-pause` („drei" statt „vier" Elemente); erwartete Tags `id="diskussion" data-laeuft="0">` bzw. `… data-laeuft="0" hidden>` (zweimal); Blockkommentar darüber ohne `#diskussion-pause` | 9 |
| `tests/test_web_chat_js.py::test_starte_diskussion_lehnt_waehrend_interview_oder_wechsel_ab` | anpassen: Schnittende `"function pausiereDiskussion"` → `"function beendeDiskussion"` | 9 |
| `tests/test_web_chat_js.py::test_fortsetzediskussion_hat_dieselbe_sperrklinke_wie_brainstorm` | **löschen** (Funktion entfällt) | 9 |
| `tests/test_web_chat_js.py::test_diskussion_pruefeende_tut_nie_etwas` | anpassen: Schnittende → `"function beendeDiskussion"` | 9 |
| `tests/test_web_chat_js.py::test_diskussion_knoepfe_sind_verdrahtet` | anpassen: Pause-Asserts raus, `wiring` ab `"if (diskussionBeendenKnopf)"`, neu `assert "diskussionPauseKnopf" not in js` | 9 |
| `tests/test_web_chat_js.py::test_manuelle_schnitte_tragen_den_grund_ende_fuer_diskussion_auch` | anpassen: nur noch `beendeDiskussion` prüfen | 9 |
| `tests/test_web_chat_diskussion_knopf.py::test_der_knopf_ist_standardmaessig_verborgen` | anpassen: Kennungen ohne `diskussion-pause`, Docstring „drei Elemente" | 9 |
| `tests/test_web_chat_diskussion_ohne_pause.py` (4 Tests) | **neu** | 9 |
| `tests/test_web_vereint_bitgleich.py::test_vereinte_seite_bleibt_byte_gleich[None]`, `[dortmund-2026]` | nichts zu tun: seit Aufgabe 5 `@pytest.mark.dortmund` (vergleicht gegen die Dortmund-Fixture, die den Pause-Code noch trägt); **keine** Fixture-Neuerzeugung | 9 (nur prüfen) |
| `tests/test_werkbank_bitgleich.py::test_ohne_schalter_bleibt_die_werkbank_byte_gleich[None]`, `[dortmund-2026]` | dito, seit Aufgabe 5 markiert | 9 (nur prüfen) |
| jeder weitere `*bitgleich*`-Test, der nach der Pausen-Entfernung **nur** an einer `*dortmund*`/`*vorgabe*`-Fixture rot wird | `@pytest.mark.dortmund` (beim Schreiben keiner erwartet) | 9 |
| `tests/e2e/test_web_diskussion_e2e.py::test_begriffsboard_im_cothinker_und_top5_vorschlag` | anpassen: `IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS=1` → `IT_BEGRIFFSBOARD_MIN_ZEICHEN=1`; Docstring „Schlusslauf" → „regulärer Lauf auf dem Ende-Schnitt" | 10 |
| `tests/e2e/test_web_diskussion_e2e.py::test_diskussion_voller_ablauf_im_browser` | anpassen (Ergänzung): nach dem Start genau **ein** Knopf in `#diskussion-aktionen`, kein `#diskussion-pause` | 10 |

**Geprüft und unberührt** (Fundstellen betreffen nur Interview/Brainstorm/Phase 4 oder nennen Pause nur im Kommentar):
`tests/test_brainstorm.py` (alle, inkl. der beiden `min_zeichen_override`-Tests aus dem Merge — der Override überlebt, `soll_laufen` nutzt ihn weiter), `tests/test_aufnahme.py::test_abschluss_schnitt_feuert_schon_ab_150_zeichen` (Phase-4-Brainstorm), `tests/test_aufnahme_diskussion.py` (Ende-Segment ohne `klm` → kein Lauf, Vorschlag sofort = heutiges Verhalten), `tests/test_web_chat_js.py` Interview-/Brainstorm-Pause-Tests (z. B. `test_pause_weiter_knopf_wechselt_auf_die_richtige_funktion`, `test_formatiereuhr_zaehlt_erfasstems_plus_laufende_spanne`, `test_keine_zweite_parallele_merkvariable_fuer_pause`, `test_pausiert_schutz_lebt_nur_noch_in_beginneaufnahme`, `test_die_seite_traegt_den_modus_schon_beim_laden`, `test_der_brainstorm_knopf_steht_immer_im_markup_aber_hidden_ausserhalb_phase_4`), die zwei Node-Tests `test_zeigemodus_fuehrt_brainstorm_und_diskussion_zusammen_in_node` / `test_zeigemodus_brainstorm_nur_szenario_bleibt_byte_identisch_zu_vor_task6_in_node` (deklarieren `diskussionPauseKnopf` nur noch als ungenutzte Variable — harmlos, bleibt), `test_startebrainstorm_und_pttpointerdown_lehnen_waehrend_diskussion_tatsaechlich_ab_in_node` (`{ pausiert: false }` als Attrappe, harmlos), `tests/test_web_chat_sprache.py` (prüft „Pause" bewusst nicht, `:104-107`), `tests/e2e/test_web_chat_e2e.py` und `tests/e2e/test_web_gestalt_e2e.py` (nur `#interview[data-pausiert]`), `tests/test_sprache_bitgleich.py` (keine Textkonstante fällt weg), `tests/test_profil_bitgleich.py`.

---

### Task 8: Endstand = Zwischenstand im Begriffsboard

**Files:**
- Modify: `interview_theater/begriffsboard.py` (`soll_laufen`, neu `merke_falls_laeuft` direkt hinter `laeuft`, `nach_segment`, Moduldocstring)
- Modify: `interview_theater/aufnahme.py` (nur Docstring `_diskussion_abschliessen`)
- Create: `tests/test_begriffsboard_abschluss.py`
- Modify: `tests/test_begriffsboard_lauf.py`, `tests/test_begriffsboard_vorschlag.py`, `tests/test_begriffsboard_mithoeren.py` (Liste oben)

**Interfaces:**
- Consumes: `begriffsboard.min_zeichen()` (Aufgabe 0), `brainstorm.soll_reagieren(*, unreagierte_zeichen, sekunden_seit_letzter_reaktion, letzter_schnittgrund, ist_abschluss, min_zeichen_override=None)` (unverändert), `repo.begriffsboard_stand`, `nimm_oder_merke`/`beende`/`_rufe`.
- Produces:
  - `begriffsboard.soll_laufen(conn, chat_id: int) -> bool` — **ohne** `ist_abschluss`.
  - `begriffsboard.merke_falls_laeuft(chat_id: int, danach) -> bool` — True: ein Lauf ist unterwegs, `danach` läuft nach ihm; False: nichts gemerkt.
  - `begriffsboard.nach_segment(conn, tg, klm, e, chat_id, *, ist_abschluss: bool, rueckfall_text=None) -> None` — Signatur unverändert (Aufrufer `aufnahme._diskussion_abschliessen` bleibt), `ist_abschluss` heißt nur noch „Sitzung zu Ende, danach der Vorschlag".

- [ ] **Step 1: Failing tests schreiben** — `tests/test_begriffsboard_abschluss.py`:

```python
"""Karte t_cb2c4678, Teil 2 (Birk 04.10.2026 14:50): "Zwischenstand und
Endstand muessen nicht anders behandelt werden." Der Ende-Schnitt
("Discussion done") ist ein gewoehnlicher Schnitt unter derselben Regel wie
ein Pausenschnitt (600 Zeichen, ``begriffsboard.min_zeichen``) -- ohne eigene
Schwelle, ohne Mindestabstand (danach kommt kein Schnitt mehr). Laeuft gerade
ein Lauf, wird nach ihm neu entschieden. Nur erfundenes Material."""

import inspect
import threading
import time

import pytest

from interview_theater import (aufnahme, begriffsboard, brainstorm, db, diskussion,
                               einstellungen, repo, workshop)

CHAT = 1
KURZ = "Heimat und Grenze."
LANG = "Heimat und Grenze und Mut. " * 12   # 324 Zeichen
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Weil Heimat.",
          "zitat": "", "doppelbedeutung": "", "status": "favorit"}
GRENZE = dict(HEIMAT, begriff="Grenze", begruendung="Weil Grenze.", status="kandidat")


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "1")


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet, self.mit_knoepfen, self._id = [], [], 900

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid

    # Wie ``tests/test_begriffsboard_vorschlag.py::_TG`` -- falls der
    # Vorschlagsweg sie beruehrt.
    def beantworte_knopf(self, callback_query_id, text=""):
        pass

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _KLM:
    """Liefert der Reihe nach ``boards``; der erste Aufruf wartet auf ``halt``."""

    def __init__(self, *boards, halt=None):
        self.boards, self.halt, self.aufrufe = list(boards), halt, 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        if self.halt is not None and self.aufrufe == 1:
            self.halt.wait(5)
        return {"board": self.boards.pop(0) if self.boards else []}


def _zeile(conn, message_id, schnittgrund, text=KURZ):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund=schnittgrund)
    repo.setze_transkript(conn, aid, text)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_soll_laufen_kennt_keinen_abschluss_mehr():
    assert list(inspect.signature(begriffsboard.soll_laufen).parameters) == ["conn", "chat_id"]


def test_ende_schnitt_zaehlt_wie_ein_pausenschnitt(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    _zeile(conn, 10, "ende")
    assert begriffsboard.soll_laufen(conn, CHAT) is True


def _pruefe_keine_eigene_abschlussschwelle(conn, einst):
    """Ende-Schnitt mit 18 Zeichen: unter der Board-Schwelle (1000), ueber
    der alten Abschluss-Schwelle (10) -- es darf KEIN Lauf starten, und der
    Vorschlag kommt sofort (leeres Board -> der heutige Satz)."""
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 20, "ende"),
                                aufnahme._kein_zug, False)
    time.sleep(0.1)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert klm.aufrufe == 0
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE)]


def test_keine_eigene_abschlussschwelle(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    _pruefe_keine_eigene_abschlussschwelle(conn, einst)


def test_mutant_mit_dem_alten_abschlusszweig_faellt_durch(conn, einst, monkeypatch):
    """Mutant: wer den alten Zweig (``ist_abschluss=True`` mit
    ``min_zeichen_bei_abschluss``, Vorgabe 150) zurueckbringt, muss den Test
    oben rot machen."""
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    echt = begriffsboard.soll_laufen

    def alter_zweig(conn_, chat_id):
        stand = repo.begriffsboard_stand(conn_, chat_id)
        if stand["letzter_schnittgrund"] == "ende":
            return brainstorm.soll_reagieren(
                unreagierte_zeichen=stand["unreagierte_zeichen"],
                sekunden_seit_letzter_reaktion=0.0,
                letzter_schnittgrund="ende", ist_abschluss=True,
            )
        return echt(conn_, chat_id)

    monkeypatch.setattr(begriffsboard, "soll_laufen", alter_zweig)
    with pytest.raises(AssertionError):
        _pruefe_keine_eigene_abschlussschwelle(conn, einst)


def test_ende_ignoriert_den_mindestabstand_ein_pausenschnitt_nicht(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "3600")
    a = _zeile(conn, 30, "pause")
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a["id"])
    _zeile(conn, 31, "pause")
    assert begriffsboard.soll_laufen(conn, CHAT) is False   # gleich nach einem Lauf
    _zeile(conn, 32, "ende")
    assert begriffsboard.soll_laufen(conn, CHAT) is True    # am Ende: nichts mehr aufschieben


def test_vorschlag_wartet_auf_den_laufenden_lauf_und_zeigt_dessen_board(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")   # der Rest reicht nicht
    _zeile(conn, 40, "pause")
    halt = threading.Event()
    klm, tg = _KLM([HEIMAT], halt=halt), _TG()
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 41, "ende"),
                                aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert tg.gesendet == [] and tg.mit_knoepfen == []       # noch nicht: es laeuft einer
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Heimat" in tg.mit_knoepfen[0][1]
    assert klm.aufrufe == 1


def test_rest_ueber_der_schwelle_wird_nach_dem_laufenden_lauf_gelesen(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100")
    _zeile(conn, 50, "pause", LANG)
    halt = threading.Event()
    klm, tg = _KLM([HEIMAT], [HEIMAT, GRENZE], halt=halt), _TG()
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 51, "ende", LANG),
                                aufnahme._kein_zug, False)
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert klm.aufrufe == 2
    assert "Grenze" in tg.mit_knoepfen[0][1]


def test_merke_falls_laeuft():
    gerufen = []
    assert begriffsboard.merke_falls_laeuft(99, lambda: gerufen.append(1)) is False
    assert begriffsboard.nimm_oder_merke(99, None) is True
    assert begriffsboard.merke_falls_laeuft(99, lambda: gerufen.append(2)) is True
    begriffsboard._rufe(begriffsboard.beende(99))
    assert gerufen == [2]
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_begriffsboard_abschluss.py -q -p no:cacheprovider`
Expected: FAIL — u. a. `test_soll_laufen_kennt_keinen_abschluss_mehr` (`['conn', 'chat_id', 'ist_abschluss']`), `TypeError: soll_laufen() missing 1 required keyword-only argument: 'ist_abschluss'`, `AttributeError: … 'merke_falls_laeuft'`, `test_keine_eigene_abschlussschwelle` (`klm.aufrufe == 1`: der alte Zweig startet bei 18 ≥ 10 Zeichen). `test_mutant_…` ist schon grün (er erwartet das Rot des alten Verhaltens).

- [ ] **Step 3: `soll_laufen`** — in `begriffsboard.py` ersetzen durch:

```python
def soll_laufen(conn, chat_id: int) -> bool:
    """D1 und Birk 04.10.2026 14:50 ("Zwischenstand und Endstand muessen
    nicht anders behandelt werden"): EINE Regel fuer jeden Lauf --
    ``brainstorm.soll_reagieren`` unveraendert, mit den eigenen Zahlen der
    Phase 1 (``repo.begriffsboard_stand``) und der eigenen Schwelle
    (``min_zeichen``). Der Schnitt "Discussion done" (``'ende'``) zaehlt wie
    ein Pausenschnitt; nur der Mindestabstand gilt dort nicht -- er schiebt
    auf, und nach dem Ende kommt kein Schnitt mehr, der das Aufgeschobene
    nachholt. Kein eigener Abschlusspfad, keine eigene Schwelle (Abwaegung
    im Plan 2026-10-04-padua-begriffsboard-ranking-schaerfung, Teil 2).
    Kein Modellaufruf."""
    stand = repo.begriffsboard_stand(conn, chat_id)
    grund = stand["letzter_schnittgrund"]
    sekunden = stand["sekunden_seit_letztem_lauf"]
    ende = grund == "ende"
    return brainstorm.soll_reagieren(
        unreagierte_zeichen=stand["unreagierte_zeichen"],
        sekunden_seit_letzter_reaktion=(
            float("inf") if ende or sekunden is None else sekunden),
        letzter_schnittgrund="pause" if ende else grund,
        ist_abschluss=False,
        min_zeichen_override=min_zeichen(),
    )
```

(Der Pausenfall ruft damit **wortgleich** dieselben kwargs wie vorher — `test_soll_laufen_ruft_brainstorm_soll_reagieren_unveraendert` hält das fest.)

- [ ] **Step 4: `merke_falls_laeuft`** — direkt hinter `laeuft()`:

```python
def merke_falls_laeuft(chat_id: int, danach) -> bool:
    """True, wenn gerade ein Boardlauf dieser Gruppe laeuft -- dann laeuft
    ``danach`` nach seinem Ende (``beende`` liefert es). False: es laeuft
    keiner, nichts gemerkt. Unter derselben Sperre wie ``nimm_oder_merke``:
    zwischen "laeuft" und "gemerkt" kann kein ``beende`` den Merkplatz leeren."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            _DANACH.setdefault(chat_id, []).append(danach)
            return True
        return False
```

- [ ] **Step 5: `nach_segment`** — ersetzen durch:

```python
def nach_segment(conn, tg, klm, e, chat_id: int, *, ist_abschluss: bool,
                 rueckfall_text: str | None = None) -> None:
    """Der Einhaengepunkt in ``aufnahme._diskussion_abschliessen``, je
    Segment. Entscheidet per Code (``soll_laufen``, EINE Regel fuer jeden
    Schnitt), ob ein Boardlauf faellig ist, und stoesst ihn im Thread an.

    ``ist_abschluss`` heisst seit Birks Entscheidung vom 04.10.2026 nur
    noch "die Sitzung ist zu Ende": es aendert KEINE Schwelle, es haengt
    nur den Vorschlag (``sende_vorschlag``) an -- nach dem Lauf, den dieser
    Schnitt ausloest, sonst sofort, mit dem Board, wie es ist. Laeuft beim
    Ende gerade ein Lauf, wird nach ihm NEU entschieden (derselbe Aufruf,
    nur spaeter): sonst bliebe der Rest seit seiner Markierung ungelesen,
    und der Vorschlag zeigte den Stand davor. Ohne Profil, ohne Modell: nur
    der Satz, wie bisher."""
    if ist_abschluss and merke_falls_laeuft(chat_id, lambda: nach_segment(
            conn, tg, klm, e, chat_id, ist_abschluss=True, rueckfall_text=rueckfall_text)):
        return
    danach = None
    if ist_abschluss:
        def danach() -> None:
            sende_vorschlag(conn, tg, chat_id, rueckfall_text)

    if klm is not None and workshop.diskussion_aktiv() and soll_laufen(conn, chat_id):
        starte(conn, klm, e, chat_id, danach=danach)
        return
    if danach is not None:
        danach()
```

Im Moduldocstring den Satz „bei "Discussion done" schlaegt der Bot seine Top 5 vor" ergänzen um: „— nach Birks Entscheidung vom 04.10.2026 ohne eigenen Schlusslauf: der Ende-Schnitt ist ein gewöhnlicher Schnitt (`soll_laufen`), der Vorschlag zeigt das Board, wie es ist."

In `aufnahme._diskussion_abschliessen` den letzten Docstring-Absatz ersetzen durch: „Beim Abschluss-Segment (`schnittgrund == 'ende'`, allein aus „Discussion done" — Phase 1 hat seit 04.10.2026 keinen Pause-Knopf mehr) kommt danach der Vorschlag der Top 5 (oder, bei leerem Board, die bisherige Aufforderung) — nach einem Lauf, den dieser Schnitt unter der gewöhnlichen Regel auslöst, oder nach einem gerade laufenden — und, unabhängig davon, der EINE Verdichtungslauf (`diskussion.starte`)." Code dort unverändert.

- [ ] **Step 6: Bestehende Tests nachziehen** (Liste „Vollständige Testliste Teil 2", Aufgabe 8):

```bash
sed -i 's/begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False)/begriffsboard.soll_laufen(conn, CHAT)/' tests/test_begriffsboard_lauf.py
sed -i 's/"IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS"/"IT_BEGRIFFSBOARD_MIN_ZEICHEN"/' tests/test_begriffsboard_vorschlag.py
grep -n "ist_abschluss=True\|MIN_ZEICHEN_BEI_ABSCHLUSS" tests/test_begriffsboard_lauf.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_mithoeren.py
```

Danach von Hand: in `tests/test_begriffsboard_lauf.py` die Funktion `test_abschluss_mit_niedriger_schwelle` **löschen**; in `tests/test_begriffsboard_mithoeren.py` (Fixture `aktiv`) die Zeile `monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")` ersetzen durch `monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")` (steht diese Zeile dort nach dem Merge schon: nur die Abschluss-Zeile löschen); in `tests/test_begriffsboard_vorschlag.py` die Docstrings/Kommentare, die „Schlusslauf" sagen, auf „Lauf auf dem Ende-Schnitt" umschreiben (Testnamen bleiben). Expected nach dem `grep`: keine Ausgabe mehr außer gegebenenfalls Kommentarzeilen.

- [ ] **Step 7: Grün laufen lassen + Phase-4-Nachweis**

```bash
$PY -m pytest tests/test_begriffsboard_abschluss.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_mithoeren.py tests/test_aufnahme_diskussion.py tests/test_brainstorm.py tests/test_aufnahme.py -q -p no:cacheprovider -m "not dortmund"
git diff --stat HEAD -- interview_theater/brainstorm.py tests/test_brainstorm.py
```

Expected: `… passed`, kein `failed`; `git diff --stat` ohne Ausgabe (Phase 4 unberührt).

- [ ] **Step 8: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/aufnahme.py tests/test_begriffsboard_abschluss.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_mithoeren.py
git commit -m "Begriffsboard: Endstand = Zwischenstand -- Ende-Schnitt unter derselben Regel, kein Abschlusspfad (t_cb2c4678, Aufgabe 8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Pause-Knopf des Mithörens entfernen (Markup + JS)

**Files:**
- Modify: `interview_theater/web_chat.py`
- Create: `tests/test_web_chat_diskussion_ohne_pause.py`
- Modify: `tests/test_web_chat_js.py`, `tests/test_web_chat_diskussion_knopf.py` (Liste oben)

**Interfaces:**
- Produces (Markup-Vertrag): `<button type="button" id="diskussion" data-laeuft="0"[ hidden]>…</button>` und `<div class="interview-aktionen" id="diskussion-aktionen" hidden>` mit **genau einem** Knopf `#diskussion-beenden` (`data-discussion-done="1"`). Im JS gibt es `starteDiskussion`, `zeigeDiskussionModus`, `beendeDiskussion` — kein `pausiereDiskussion`, `fortsetzeDiskussion`, `diskussionPauseKnopf`.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_web_chat_diskussion_ohne_pause.py`:

```python
"""Karte t_cb2c4678, Teil 2 (Birk 04.10.2026 14:50): das Mithoeren der
Phase 1 hat nur noch Start und Fertig. Interview- und Brainstorm-Pause
bleiben unberuehrt."""

import re

from interview_theater import web_chat

DATEN = {"nachrichten": [], "letzte": 0, "aenderung": 0, "interviewmodus": False,
         "titel": None, "phase": 1, "diskussion_knopf": True}


def _seite(**kw):
    return web_chat.chat_html(dict(DATEN, **kw), "1.x", "tok", "", 45000)


def _fn(js, name, bis):
    return js[js.index(f"function {name}"):js.index(f"function {bis}")]


def test_markup_hat_nur_start_und_fertig():
    seite = _seite()
    assert "diskussion-pause" not in seite
    assert 'id="diskussion" data-laeuft="0">' in seite
    assert 'id="diskussion" data-laeuft="0" hidden>' in _seite(diskussion_knopf=False)
    aktionen = re.search(r'id="diskussion-aktionen" hidden>(.*?)</div>', seite, re.S).group(1)
    assert aktionen.count("<button") == 1
    assert 'id="diskussion-beenden" data-discussion-done="1"' in aktionen


def test_js_kennt_keine_diskussionspause():
    js = web_chat._CHAT_JS
    for name in ("pausiereDiskussion", "fortsetzeDiskussion", "diskussionPauseKnopf",
                 "diskussion-pause"):
        assert name not in js, name
    assert "pausiert" not in _fn(js, "zeigeDiskussionModus", "starteDiskussion")
    assert "fortsetzend" not in _fn(js, "starteDiskussion", "beendeDiskussion")


def test_fertig_setzt_weiter_den_grund_ende():
    """Der Ende-Schnitt markiert das Sitzungsende fuer ``diskussion.starte``
    und den Vorschlag -- er kommt allein aus ``beendeDiskussion``."""
    beenden = _fn(web_chat._CHAT_JS, "beendeDiskussion", "starteInterview")
    assert "letzter && sitzung.vadAktiv) { letzter._grund = 'ende'" in beenden


def test_interview_und_brainstorm_pause_bleiben():
    js, seite = web_chat._CHAT_JS, _seite()
    for name in ("function pausiereInterview", "function fortsetzeInterview",
                 "function pausiereBrainstorm", "function fortsetzeBrainstorm",
                 "interviewPauseKnopf", "brainstormPauseKnopf"):
        assert name in js, name
    assert 'id="interview-pause"' in seite and 'id="brainstorm-pause"' in seite
    assert web_chat._TEXT_INTERVIEW_PAUSE in seite
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_web_chat_diskussion_ohne_pause.py -q -p no:cacheprovider`
Expected: `test_markup_hat_nur_start_und_fertig` und `test_js_kennt_keine_diskussionspause` FAIL; `test_fertig_setzt_weiter_den_grund_ende` und `test_interview_und_brainstorm_pause_bleiben` grün (Wächter für das, was bleiben muss).

- [ ] **Step 3: Markup** — in `web_chat.chat_html` (Block `id="diskussion"`, ~Z. 3847–3858):

```python
        + (
            f'  <button type="button" id="diskussion" data-laeuft="0"'
            + ('' if diskussion_erlaubt else ' hidden')
            + f'>{html.escape(T._TEXT_DISKUSSION_AN)}</button>\n'
            f'  <div class="interview-aktionen" id="diskussion-aktionen" hidden>\n'
            f'    <button type="button" id="diskussion-beenden" '
            f'data-discussion-done="1">'
            f'{html.escape(T._TEXT_DISKUSSION_FERTIG_KNOPF)}</button>\n'
            f'  </div>\n'
        )
```

(Gelöscht: die Zeile `f'data-pausiert="0"'`, die zwei Zeilen des `#diskussion-pause`-Knopfs, und das Leerzeichen am Ende von `data-laeuft="0" '` — sonst stünde ohne `hidden` `data-laeuft="0" >`. Gerendert ist das für Dortmund genau das Löschen des Tokens ` data-pausiert="0"` und der Knopfzeile.)

- [ ] **Step 4: JS (`_CHAT_JS`)** — nur löschen:
  1. `var diskussionPauseKnopf = document.getElementById('diskussion-pause');` (~Z. 718) — Zeile weg.
  2. Kommentar über `zeigeDiskussionModus` (~Z. 2765): aus `(#diskussion, #diskussion-pause, #diskussion-beenden), aber dieselbe` nur das Teilstück `#diskussion-pause, ` löschen.
  3. In `zeigeDiskussionModus` die Zeilen löschen:
     ```
         var pausiert = an && sitzung.pausiert;
         diskussionKnopf.dataset.pausiert = pausiert ? '1' : '0';
         } else if (pausiert) {
           diskussionKnopf.textContent = TEXT.interview_pausiert.replace('{zeit}', formatiereUhr(sitzung));
         if (diskussionPauseKnopf) {
           diskussionPauseKnopf.textContent = pausiert ? TEXT.interview_weiter : TEXT.interview_pause;
         }
     ```
     (Übrig bleibt `if (!an) { … } else { …diskussion_laeuft… }`.)
  4. In `starteDiskussion` im Sitzungsobjekt die Zeile `      fortsetzend: false` löschen (das Komma am Ende von `mikroUnterwegs: true,` bleibt — ein abschließendes Komma im Objektliteral ist gültiges JS). `pausiert: false, erfassteMs: 0, legStart: null` **bleiben**: `beginneAufnahme` und `formatiereUhr` lesen sie für jede Sitzungsart.
  5. Die ganzen Funktionen `pausiereDiskussion()` und `fortsetzeDiskussion()` samt der Leerzeile danach löschen.
  6. Die Verdrahtung `if (diskussionPauseKnopf) { … }` (7 Zeilen, ~Z. 3214–3220) löschen.

Python-Kommentar über `_TEXT_DISKUSSION_AN` (~Z. 214–218, **nicht** in `_CHAT_JS`) neu fassen: „Hintergrund-Mithören Phase 1 (…): nur Start und Fertig — seit Birks Entscheidung vom 04.10.2026 ohne Pause/Weiter; eigene Beschriftungen für den großen Knopf, die Läuft-Zeile und den Fertig-Knopf."

Danach belegen:

```bash
grep -n "diskussion-pause\|pausiereDiskussion\|fortsetzeDiskussion\|diskussionPauseKnopf" interview_theater/web_chat.py
```

Expected: keine Ausgabe.

- [ ] **Step 5: Bestehende Tests nachziehen** — die Aufgabe-9-Zeilen der Liste oben, je wörtlich:
  - `test_manuelle_schnitte_tragen_den_grund_ende`: `assert js.count("_grund = 'ende'") == 5`, Kommentar `# pausiereInterview + beendeInterview + pausiereBrainstorm + beendeBrainstorm + beendeDiskussion`.
  - `test_beginneaufnahme_ist_der_einzige_ort_der_die_aufnahme_beginnt`: `assert js.count("beginneAufnahme(sitzung);") == 5`, Kommentar ohne `fortsetzeDiskussion`.
  - `test_der_diskussion_knopf_steht_immer_im_markup_aber_hidden_ausserhalb_phase_1`: beide Tupel → `("diskussion", "diskussion-aktionen", "diskussion-beenden")`; `'id="diskussion" data-laeuft="0">'`; zweimal `'id="diskussion" data-laeuft="0" hidden>'`; Docstring „die drei Diskussion-Elemente"; Blockkommentar darüber `#diskussion`/`#diskussion-beenden`.
  - `test_starte_diskussion_lehnt_waehrend_interview_oder_wechsel_ab` und `test_diskussion_pruefeende_tut_nie_etwas`: `js.index("function beendeDiskussion")` als Schnittende.
  - `test_fortsetzediskussion_hat_dieselbe_sperrklinke_wie_brainstorm`: Funktion löschen.
  - `test_diskussion_knoepfe_sind_verdrahtet`:
    ```python
    def test_diskussion_knoepfe_sind_verdrahtet():
        js = web_chat._CHAT_JS
        assert "diskussionPauseKnopf" not in js
        assert "diskussionBeendenKnopf.addEventListener('click', beendeDiskussion);" in js
        assert "diskussionKnopf.addEventListener('click'" in js
        wiring = js[js.index("if (diskussionBeendenKnopf)"):js.index("-- Push-to-Talk")]
        assert "starteDiskussion()" in wiring
    ```
  - `test_manuelle_schnitte_tragen_den_grund_ende_fuer_diskussion_auch`:
    ```python
    def test_manuelle_schnitte_tragen_den_grund_ende_fuer_diskussion_auch():
        """``beendeDiskussion`` flusht wie beim Interview/Brainstorm ueber
        ``_grund = 'ende'`` -- seit 04.10.2026 der einzige Ende-Schnitt."""
        js = web_chat._CHAT_JS
        beenden = js[js.index("function beendeDiskussion"):
                     js.index("function starteInterview")]
        assert "_grund = 'ende'" in beenden
    ```
  - `tests/test_web_chat_diskussion_knopf.py::test_der_knopf_ist_standardmaessig_verborgen`: Tupel `("diskussion", "diskussion-aktionen", "diskussion-beenden")`, Docstring „die drei Elemente".

- [ ] **Step 6: Grün laufen lassen; Bitgleich-Tests: Rot nur wegen Dortmund?**

```bash
$PY -m pytest tests/test_web_chat_diskussion_ohne_pause.py tests/test_web_chat_js.py tests/test_web_chat_diskussion_knopf.py tests/test_web_chat_sprache.py tests/test_web_vereint_js_syntax.py -q -p no:cacheprovider -m "not dortmund"
git grep -n "mark.dortmund" -- tests
$PY -m pytest tests/ -q -p no:cacheprovider -k "bitgleich" -rf
$PY -m pytest tests/ -q -p no:cacheprovider -k "bitgleich" -m "not dortmund"
```

Expected: erster Lauf `… passed`, kein `failed` (Node-Tests ggf. `skipped`). `git grep` zeigt die Marker aus Aufgabe 5 an `test_vereinte_seite_bleibt_byte_gleich` und `test_ohne_schalter_bleibt_die_werkbank_byte_gleich`. Der dritte Lauf (ohne Markerfilter) zeigt genau diese beiden Funktionen rot (je `[None]` und `[dortmund-2026]`) — jetzt zusätzlich wegen des entfernten Pause-Codes in der Dortmund-Fixture; der vierte (`-m "not dortmund"`) ist `… passed, … deselected` ohne `failed`.

Ist im dritten Lauf ein **weiterer** `*bitgleich*`-Test rot: Blick auf den Unterschied, wie in Aufgabe 5 Step 6 (dort das `difflib`-Snippet). Bestehen die Unterschiede nur aus Pause-Code (`diskussion-pause`, `pausiereDiskussion`, `fortsetzeDiskussion`, `diskussionPauseKnopf`, `data-pausiert` an `#diskussion`, `fortsetzend`) und den Teil-1-Zeilen (`bb…`, `.begriffsboard .vorgaenger`), und vergleicht der Test gegen eine `*dortmund*`/`*vorgabe*`-Fixture: `@pytest.mark.dortmund` über die Testfunktion, Datei mit `git add`-en. Sonst ist es ein Fehler dieser Aufgabe. Für den Bericht genügt derselbe Blick auf `tests/fixtures/web_vereint_dortmund_vorher.html` (Snippet aus Aufgabe 5) — kein formales Tor.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_diskussion_ohne_pause.py tests/test_web_chat_js.py tests/test_web_chat_diskussion_knopf.py
git commit -m "Phase 1: Pause-Knopf des Mithoerens entfernt, nur Start und Fertig (t_cb2c4678, Aufgabe 9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Browserlauf Phase 1 nachziehen

**Files:**
- Modify: `tests/e2e/test_web_diskussion_e2e.py`

- [ ] **Step 1: Anpassen**
  - `test_begriffsboard_im_cothinker_und_top5_vorschlag`: die Zeile `monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "1")` ersetzen durch
    ```python
    # Endstand = Zwischenstand (Birk 04.10.2026): der Ende-Schnitt laeuft
    # unter derselben Regel wie ein Pausenschnitt -- die Schwelle dafuer ist
    # die des Boards, hier auf ein Zeichen gesenkt.
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1")
    ```
    und im Docstring „Schlusslauf" → „regulärer Lauf auf dem Ende-Schnitt".
  - `test_diskussion_voller_ablauf_im_browser`: direkt hinter `expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")` (Schritt 3) einfügen:
    ```python
    # Birk 04.10.2026: nur Start und Fertig -- kein Pause-Knopf mehr.
    expect(seite.locator("#diskussion-aktionen button")).to_have_count(1)
    assert seite.locator("#diskussion-pause").count() == 0
    ```

- [ ] **Step 2: Laufen lassen (Playwright-venv)**

```bash
$E2E -m pytest tests/e2e/test_web_diskussion_e2e.py tests/e2e/test_web_begriffsboard_ranking_e2e.py -q -p no:cacheprovider
```

Expected: `4 passed` (zwei Diskussions-, zwei Ranking-Tests). Ohne Playwright: im Bericht wörtlich „e2e nicht gelaufen".

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_web_diskussion_e2e.py
git commit -m "e2e Phase 1: Ende-Schnitt unter der Board-Schwelle, nur Start und Fertig (t_cb2c4678, Aufgabe 10)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: AGENTS.md (Teil 2), Padua-Abnahme, Abschluss-Suite, Bericht

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: AGENTS.md nachziehen** — drei Stellen:

(a) Modultabelle, Zeile `begriffsboard.py`: „Bei „Discussion done" der Top-5-Vorschlag mit EINEM Knopf „Take these"" ersetzen durch: „Bei „Discussion done" der Top-5-Vorschlag mit EINEM Knopf „Take these" — **ohne eigenen Schlusslauf** (Birk 04.10.2026 14:50: „Zwischenstand und Endstand müssen nicht anders behandelt werden"): der Ende-Schnitt zählt in `soll_laufen` wie ein Pausenschnitt (dieselbe Schwelle `min_zeichen`, 600; nur ohne Mindestabstand), der Vorschlag zeigt das Board, wie es ist — läuft gerade ein Lauf, wird nach ihm neu entschieden (`merke_falls_laeuft`)."

(b) Absatz „**Phase 1 hört seit 04.10.2026 laufend mit, wie Phase 4**": den Satz „Bei „Discussion done" schlägt der Bot die Top 5 mit EINEM Knopf „Take these" vor" um denselben Halbsatz ergänzen und davor einfügen: „**Das Mithören hat nur Start und Fertig** — der Pause-Knopf (`#diskussion-pause`, `pausiereDiskussion`/`fortsetzeDiskussion`) ist seit dem 04.10.2026 entfernt; er setzte bis dahin ebenfalls den Ende-Schnitt und löste damit bei jeder Pause Vorschlag und Verdichtung aus. Interview- und Brainstorm-Pause bleiben."

(c) „Die Übergaben der Karte t_4517d4ad": den Punkt „ein Neustart zwischen „Discussion done" und Ende des Schlusslaufs verliert den Vorschlag" auf „… und Ende des laufenden Laufs …" umstellen und zwei Punkte anhängen:
- „**Endstand = Zwischenstand (t_cb2c4678):** ein Rest unter `min_zeichen` (600 Zeichen ≈ 37 s Rede nach den Erwachsenen-Daten in `brainstorm.py`) nach dem letzten Lauf erreicht das Board nicht — so entschieden (Birk). Ungemessen für Schülerinnen und Schüler."
- „Ohne VAD trägt kein Diskussionssegment einen Schnittgrund: dann gibt es weder Board-Lauf noch Vorschlag noch Verdichtung (vor dieser Karte genauso). Und hat das letzte Teilstück bei „Discussion done" keine Bytes, kommt kein Ende-Schnitt an (`r.onstop`)."

- [ ] **Step 2: Pflichttests einzeln, mit Namen**

```bash
$PY -m pytest tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_web.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_einstieg.py tests/test_begriffsboard_schaerfung.py tests/test_begriffsboard_schaerfung_web.py tests/test_begriffsboard_flip.py tests/test_begriffsboard_abschluss.py tests/test_web_chat_diskussion_ohne_pause.py tests/test_brainstorm.py tests/test_pruefe_sprache.py -q -p no:cacheprovider -m "not dortmund"
git grep -n "mark.dortmund" -- tests
BASIS=<SHA aus Aufgabe 0, Step 3>
git diff --stat "$BASIS" HEAD -- tests/fixtures/
```

Expected: `… passed`, kein `failed`; `git grep` listet die in Aufgabe 5/9 (und Aufgabe 3, falls nötig) gesetzten Marker — diese Liste geht in den Bericht; `git diff --stat` für `tests/fixtures/` **ohne Ausgabe** (keine Fixture neu erzeugt).

- [ ] **Step 3: Padua-Abnahme — Profil und Prompt-Snapshot**

```bash
$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?
IT_WORKSHOP=padua-2026 $PY -m scripts.prompt_schnappschuss /tmp/t_cb2c4678-padua-prompts-nachher.txt
diff /tmp/t_cb2c4678-padua-prompts-vorher.txt /tmp/t_cb2c4678-padua-prompts-nachher.txt
```

Expected:
- `pruefe_profil` (Aufruf laut `scripts/pruefe_profil.py`: `python -m scripts.pruefe_profil <name>|--alle|--vorgabe`): erste Zeile `Workshop-Profil padua-2026`, gegebenenfalls `  Hinweis: …`-Zeilen, letzte Zeile `padua-2026: in Ordnung` (oder `padua-2026: in Ordnung, N Hinweis(e)`), `EXIT 0`. Eine Zeile `  FEHLER:  …` / `padua-2026: N Fehler` ist ein Fehler dieser Karte, wenn sie in einem Lauf am Stand `BASIS` nicht auftritt (Gegencheck am Stand `BASIS`, z. B. in einem Wegwerf-Worktree `git worktree add /tmp/t_cb2c4678-basis "$BASIS"`, danach `git worktree remove /tmp/t_cb2c4678-basis`).
- `prompt_schnappschuss`: `<N> Zeichen nach /tmp/t_cb2c4678-padua-prompts-nachher.txt (Profil: padua-2026)`.
- `diff`: nur Zeilen, deren Abschnittsname den Begriffsboard-Prompt betrifft (Aufgabe 3) — oder gar keine, wenn der Fingerabdruck diesen Prompt nicht abdeckt. Jede andere geänderte Zeile ist ein Befund und wird vor dem Commit erklärt.

ANNAHME (beim Lauf prüfen): „Prompt-Snapshot nur für Padua" (AGENTS.md auf `main`, Abschnitt „Dortmund eingefroren") hat auf `main` **noch keinen eigenen Befehl oder Test** — beim Schreiben der Revision gibt es nur Dortmund-bezogene Massstäbe (`tests/test_profil_bitgleich.py`, `tests/test_sprache_bitgleich.py`, beide gegen Dortmund/Vorgabe) und das Werkzeug `scripts/prompt_schnappschuss.py`. Der Vorher/Nachher-Vergleich oben ist deshalb die Padua-Abnahme dieser Karte. Der Coder prüft vor dem Lauf mit `git grep -n "padua" main -- tests/test_*bitgleich*.py scripts/prompt_schnappschuss.py docs/prompt-audit`, ob inzwischen ein Padua-Snapshot (Datei oder Test) auf `main` liegt; wenn ja, **den** benutzen und hier im Bericht nennen.

`tests/test_profil_bitgleich.py`: läuft in Step 4 mit; wird er **nur** wegen des Dortmund-/Vorgabe-Massstabs rot, bekommt der betroffene Test `@pytest.mark.dortmund` (wie Aufgabe 5, Step 6), keine Anpassung, kein neuer Schnappschuss. `pruefe_profil dortmund-2026` ist **kein** Abnahmekriterium und wird nicht gefahren.

- [ ] **Step 4: Abschluss-Suite im Hintergrund, abwarten**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
```

Im Hintergrund starten, bis zum Ende abwarten, nicht abbrechen. Danach `tail -n 3 .suite.log` und `tail -n 3 .suite-baseline.log`.

Expected: `EXIT 0`. Rechnung für `passed`: Baseline + 45 (Teil 1: Aufgabe 2: 27, 3: 5, 4: 5, 5: 8) + 12 (Teil 2: Aufgabe 8: 8, Aufgabe 9: 4) − 2 gelöschte (`test_abschluss_mit_niedriger_schwelle`, `test_fortsetzediskussion_hat_dieselbe_sperrklinke_wie_brainstorm`) − M neu markierte Testfälle (mindestens 4: je zwei Parametrisierungen von `test_vereinte_seite_bleibt_byte_gleich` und `test_ohne_schalter_bleibt_die_werkbank_byte_gleich`; sie wandern von `passed` nach `deselected`) = **Baseline + 55 − M**. Node-Tests zählen ggf. als `skipped`. Keine neuen `failed`: ein Test, der in der Baseline grün und jetzt rot ist, ist Folge dieser Karte und wird vor dem Commit behoben — oder, wenn er **nur** an Dortmund-Verhalten scheitert, markiert (und im Bericht genannt).

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "AGENTS.md: Phase 1 nur Start/Fertig, Endstand = Zwischenstand, Uebergaben (t_cb2c4678, Aufgabe 11)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Hat Step 3 einen Marker an `tests/test_profil_bitgleich.py` gesetzt, die Datei mit `git add`-en.)

- [ ] **Step 6: Abschlussbericht** (als Kartenkommentar, nicht als Datei) — Pflichtinhalt:
  1. BASIS-SHA aus Aufgabe 0 und die Commit-SHAs der Aufgaben 2–11.
  2. **Beide** Suite-Zeilen wörtlich: Baseline (`.suite-baseline.log`) und Schluss (`.suite.log`), jeweils mit `EXIT`, und die Rechnung „Baseline + 55 − M" mit dem tatsächlichen M.
  3. Die Padua-Abnahme: Ausgabe von `pruefe_profil padua-2026` (letzte Zeile + `EXIT`) und das Ergebnis des Prompt-Snapshot-Vergleichs (bzw. des Padua-Snapshots, falls auf `main` inzwischen vorhanden).
  4. Die Liste der gesetzten `@pytest.mark.dortmund` (Datei::Test) samt dem Blick auf den Fixture-Diff aus Aufgabe 5 Step 6 und Aufgabe 9 Step 6 (die ersten ~60 Zeilen), als Beleg „rot nur wegen Dortmund".
  5. Die gewählte Option der Abwägung (B) in einem Satz, mit dem hingenommenen Verlust.
  6. Node-Tests gelaufen ja/nein; e2e gelaufen ja/nein (sonst wörtlich „e2e nicht gelaufen"); Pfad und Beschreibung des Screenshots.
  7. Jede ANNAHME dieses Plans mit dem, was sich im Lauf gezeigt hat.
  8. Ausdrücklich: kein Merge, kein Push, kein bezahlter Lauf, keine Fixture neu erzeugt, kein Dortmund-Code gelöscht.

---

## Selbstprüfung des Plans (gegen Abschnitt A–F der Karte, den Nachtrag und die Revision)

| Anforderung | Aufgabe |
|---|---|
| Vorbedingung prüfen (jetzt erfüllt), sonst blockieren, nie kopieren | 0 |
| Baseline-Suite mit `-m "not dortmund"` im Hintergrund, `.suite.log` nicht committet; Padua-Prompt-Fingerabdruck vorher | 1 |
| D1 Feld + Prüfung in `validiere(…, bisher)` (gültig / erfunden / noch stehend / selbst) | 2 |
| D1 Kette über zwei Läufe, Erben, altes Board ohne Feld | 2, 3 |
| D1 keine Heuristik, Begründung | Plankopf |
| D1 Schema `required`, Prompt DE/EN, Nutzertext mit `vorgaenger` | 3 |
| „nie mehr als ein Begriff", per Konstruktion begründet | 2 (Step 5 + vier Tests) |
| D2 `<del>`, maskiert, `data-vorgaenger`, kein `style=`/`on…=`/Zitat, alte Regexe grün | 4 |
| D3 FLIP **in `ladeBuehne()`**, Zuordnung über Vorgänger, Einblenden, reduced motion, `<details>`-Zustand, CSSOM, Node-Test | 5, 6 |
| Revision: kein Gating, kein neuer Schalter, kein MutationObserver; CSS im regulären CoThinker-CSS ohne `@media`/`transition` | 5 |
| Revision: `*bitgleich*` rot nur wegen Dortmund → `@pytest.mark.dortmund`, keine Fixture neu erzeugt | 3 (falls nötig), 5, 9, 11 |
| D5 Phase 4 unberührt | Dateiübersicht, 5 (`bbMerke` → `null`), 8 (Step 7) |
| e2e + Handy-Screenshot, „e2e nicht gelaufen" statt „grün" | 6, 10 |
| Nachtrag 1: Pause weg (Markup, JS, `data-pausiert`, Zweige), Interview/Brainstorm-Pause bleiben | 9 |
| Nachtrag 2: kein eigener Abschlusspfad, Vorschlag mit dem Board, wie es ist, nach laufendem Lauf | 8 |
| Abwägung A/B/C mit Belegen, Verlust von B beziffert, Mindestabstand entschieden | „Abwägung Abschlusspfad" |
| `'ende'` kommt weiter aus `beendeDiskussion()` | 9 (`test_fertig_setzt_weiter_den_grund_ende`) |
| Vollständige Testliste Teil 2, Mutant gegen den alten 150er-Zweig | „Vollständige Testliste", 8 |
| Abnahme: Suite `-m "not dortmund"`, `pruefe_profil padua-2026`, Prompt-Snapshot Padua | 11 |
| AGENTS.md (Teil 1 + Teil 2), Schluss-Suite, beide Zeilen im Bericht | 7, 11 |

**ANNAHME-Marker in diesem Plan:**
1. Aufgabe 3, Step 1: der englische Prompt hat nach dem Merge `0 Treffer` im Sprachprüfer.
2. Aufgabe 3, Step 9: `tests/test_profil_bitgleich.py` und `tests/test_sprache_bitgleich.py` bleiben mit dem geänderten Begriffsboard-Prompt grün (der Prompt ist erst nach beiden Massstäben entstanden); sonst Marker statt Anpassung.
3. Aufgabe 5, Step 2: `scope_css` schreibt `.panel-buehne .begriffsboard .vorgaenger` (Scope mit Leerzeichen davor).
4. Aufgabe 6, Step 2: mit `#buehne` ist der CoThinker beim Laden sichtbar und lädt alle 10 s nach.
5. Aufgabe 6, Step 2: die Lage von „Grenze" kann unverändert bleiben (nicht geprüft).
6. Abwägung (Teil 2): 600 Zeichen ≈ 37 s Rede gilt nach Erwachsenen-Daten (`brainstorm.py:9-11`); für Schülerinnen und Schüler ungemessen.
7. Testliste Teil 2: Zeilennummern sind die des Worktrees vor dem Merge aus Aufgabe 0; die Testnamen ändert der Merge nicht.
8. Aufgabe 11, Step 3: für „Prompt-Snapshot nur für Padua" gibt es auf `main` noch keinen eigenen Befehl/Test; der Vorher/Nachher-Fingerabdruck mit `scripts/prompt_schnappschuss.py` unter `IT_WORKSHOP=padua-2026` ist die Abnahme, bis ein Padua-Snapshot auf `main` liegt.

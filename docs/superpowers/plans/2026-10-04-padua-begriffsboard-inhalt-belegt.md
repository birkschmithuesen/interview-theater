# Padua Phase 1: Begriffsboard-Inhalt belegt -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Karte:** t_2b9d2cbe (Plan), ausgeführt auf Branch
`padua-workshop/t_90f7ec48-padua-phase-1-begriffsboard-inhalt-sinnh`. Nicht
mergen, nicht pushen.

**Goal:** Eine `begruendung` auf dem Begriffsboard der Phase 1 steht nur noch,
wenn sie durch ein geprüftes Zitat mit eigenem Inhalt belegt ist (im Code
erzwungen), Meta-Begriffe („Begriff“, „Gepäck“, „Test“) fallen im Code weg, und
der Prompt (DE + EN) erkennt Ansage-Formeln, Testgerede und STT-Verhörer --
vorher/nachher gegen Kimi gemessen, Opus nur als Entscheidungsvorlage.

**Architecture:** Reine Hilfsfunktionen in `interview_theater/begriffsboard.py`
(`inhaltswoerter`, `traegt_beleg`, `ist_fuellsatz`, `ist_metabegriff`) werden
zuerst **ungebunden** gebaut, damit die Messung sie als Zähler benutzen kann;
dann wird **vorher** gemessen, dann werden sie mit zwei Zeilen in `validiere`
eingehängt (`_belege`, Meta-Check), dann der Prompt geändert und **nachher**
gemessen. Das Messskript `scripts/rauchtest_begriffsboard_inhalt.py` liest den
„vorher“-Stand (Prompt, `SCHEMA`, `validiere`, `_nutzertext`) per `git show`
aus einem festen Commit, so dass „vorher“ auch nach dem Umbau reproduzierbar
bleibt -- ohne Schalter im Produktivcode.

**Tech Stack:** Python 3.11, Standardbibliothek (`re`, `tomllib`, `sqlite3`,
`subprocess`), pytest, httpx (vorhanden), Infomaniak/Kimi über `llm.LLM`,
Opus über `simulation/claude.py`.

## Global Constraints

- Python: **`python3.11`** (liegt unter `/home/birk/.local/bin/python3.11`).
  `uv run pytest` findet `interview_theater` in diesem Worktree **nicht**
  (vom Architekten am 04.10.2026 geprüft: `ModuleNotFoundError`), das
  System-Python 3.9 kann den Code nicht importieren. Im ganzen Plan steht
  deshalb `python3.11 -m …`.
- Suite (Abnahme, Dortmund eingefroren seit 04.10.2026):
  `python3.11 -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund"`
  plus `python3.11 -m scripts.pruefe_profil padua-2026` und
  `python3.11 -m scripts.pruefe_sprache padua-2026`. Die volle Suite dauert
  über 10 Minuten: **als Hintergrundlauf mit Log-Datei** (siehe Aufgabe 9).
- Dortmund ist eingefroren: Abnahme nur Padua. Ein Test, der **nur** wegen
  Dortmund rot wird, bekommt `@pytest.mark.dortmund`, statt angepasst zu
  werden. `tests/fixtures/*dortmund*`, `*vorgabe*` werden nicht neu erzeugt.
- **Keine Live-Daten ins Repo:** kein Transkript, kein Zitat, keine
  Begründung, keine Rohantwort aus `betrieb/padua.db`. Für den Fall „live“
  stehen im Repo nur die Soll-Begriffsliste (Begriffe wie „Cappuccino“ sind
  keine PII) und Zahlen.
- **Live-Transkript nie an ein US-Modell:** der Fall „live“ läuft nur über
  `llm.LLM` (Infomaniak, `IT_LLM_URL`), das Skript verweigert
  `--modell opus` für „live“ hart.
- **Live-DB nur lesend:** `file:<pfad>?mode=ro`, nie `db.verbinde` auf
  `betrieb/*.db`. `aufruf`-/`vorfall`-Zeilen der Messung gehen in eine
  Wegwerf-DB (`tempfile`).
- Kein Modellaufruf in der Belegprüfung; **keine zweite Normalisierung**
  neben `zitat.normalisiere` / `begriffsboard.schluessel`.
- Hotspot: `begriffsboard.py` und beide `begriffsboard.md` werden auch von
  der ungemergten Karte t_cb2c4678 (`wt/t_cb2c4678`) geändert. Eingriffe in
  `validiere` sind deshalb **zwei einzelne Zeilen**; alles andere sind neue
  Funktionen/Konstanten. `wt/t_9258d2e9` nicht anfassen.
- Jeder Commit endet mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Entscheidungen (vom Architekten getroffen, nicht neu verhandeln)

- **D1 Belegpflicht in `validiere`:** `begruendung` bleibt nur, wenn (a) das
  Zitat `zitat.pruefe` besteht **und** (b) nach Abzug der Wörter des
  Begriffs, der Ansage-Formel-Wörter (DE + EN inkl. STT-Varianten
  „Gepäck“/„Betreff“), der Meta-Wörter, der Stoppwörter und reiner Ziffern
  noch mindestens `BELEG_MIN_INHALTSWOERTER = 2` Inhaltswörter übrig bleiben.
  Sonst `begruendung = ""`. Zusätzlich wird eine Füll-Begründung per Muster
  geleert, auch wenn ein Zitat da ist. Leere Begründung ist gültig
  (`detail_zeilen` lässt solche Einträge schon heute weg).
  - **Warum N = 2:** Ein einzelnes übrig bleibendes Wort ist in den
    beobachteten Fehlbildern ein Adjektiv oder ein STT-Rest aus der Ansage
    („… als besten Gepäck vor“ → „besten“; „my turn is harbour“ → „turn“).
    Ein Grund braucht mindestens Gegenstand und Aussage („wo meine Oma
    kocht“ → „oma“, „kocht“). N = 3 würde kurze echte Gründe („Oma kocht
    sonntags“ geht, „weil Oma kocht“ wäre bei 3 schon tot) wegschneiden.
  - **Füll-Muster als gemeinsame DE+EN-Liste, nicht über
    `sprache.je_sprache`:** gemessen (Live-Board vom 04.10.2026) schrieb Kimi
    unter dem EN-Profil deutsche Begründungen. Eine Liste nur der
    Profilsprache ließe genau diesen Fall durch. Gleiches gilt für Stopp-,
    Ansage- und Meta-Wörter.
  - Eine Füll-Begründung mit einem Grund-Marker (`weil`, `denn`, `damit`,
    `deshalb`, `darum`, `because`, `since`, `so that`, `therefore`) gilt
    **nicht** als Füllsatz („wird genannt, weil …“) -- über ihr Bestehen
    entscheidet dann allein (a)+(b).
- **D2 Meta-Begriffe im Code verwerfen:** ein Eintrag, dessen Begriff nur aus
  Meta-/Stopp-Wörtern und Ziffern besteht und mindestens ein Meta-Wort
  enthält („Begriff“, „Term“, „Gepäck“, „Betreff“, „Test“, „Mikrofon“, „Test
  1 2 3“, „Mikrofon Test“), fällt in `validiere` weg. Kleine, geschlossene
  Liste (`_METAWOERTER`).
- **D3 Merge-/STT-Spuren nicht in `begruendung`:** beide Prompt-Abschnitte,
  die heute „extend begruendung with the development“ bzw. „note the
  correction briefly in begruendung“ verlangen, werden umgeschrieben;
  gemergte/verhörte Varianten erscheinen gar nicht, auch nicht als
  `status = verworfen`. „verworfen“ nur für inhaltlich fallen gelassene
  Begriffe. Kein Code dafür (die Messung zählt es als `dubletten`).
- **D4 Profilsprache:** der EN-Prompt verlangt `begruendung` und
  `doppelbedeutung` auf Englisch, auch bei deutschem Transkript; `begriff`
  bleibt im Wortlaut. Kein Code-Übersetzer; der Sprach-Zähler misst es.
- **D5 Messung:** `scripts/rauchtest_begriffsboard_inhalt.py` (kein Test,
  läuft nie automatisch, kostet Geld). Fälle: `live` + 3 erfundene unter
  `simulation/begriffsboard_faelle/*.toml`. Je Fall 3 Läufe, Arme
  `vorher`/`nachher`, Kimi. **Ein Lauf = zwei Aufrufe** (erst die erste
  Hälfte der Segmente mit leerem Board, dann das ganze Transkript mit dem
  validierten Board aus Schritt 1): so entstehen Zusammenführungen und
  Merge-Spuren wie im Live-Betrieb, der fortlaufend schreibt. Gezählt wird
  am Board nach Schritt 2, zweimal: roh (Prompt-Wirkung) und validiert
  (Code-Wirkung).
- **„vorher“ reproduzierbar:** `VORHER_REF` (fester Commit-SHA, in Aufgabe 0
  bestimmt) -- das Skript liest `interview_theater/begriffsboard.py` und
  `interview_theater/sprachen/en/prompts/begriffsboard.md` per `git show`
  aus diesem Commit und führt das alte Modul in einem eigenen Modulobjekt
  aus. Kein Schalter im Produktivcode.
- **Budget:** je Aufruf geschätzt ≤ 0,015 CHF (≈ 5 000 Token rein × 0,60 +
  ≈ 4 000 Token raus × 3,00 CHF/Mio, `kosten.PREISE_CHF_JE_MIO_TOKEN` für
  `moonshotai/Kimi-K2.6`). Eine Skript-Ausführung = 4 Fälle × 3 Läufe × 2
  Aufrufe = 24 Aufrufe ≈ 0,36 CHF. Deckel je Ausführung: `MAX_AUFRUFE = 30`
  (24 + Luft für einen Wiederholungslauf eines Falls) und `BUDGET_CHF = 0,75`.
  Höchstens 4 Kimi-Ausführungen (vorher, nachher, 2 Iterationen) → ≤ 3 CHF
  gesamt. Opus läuft über das Abonnement (0 CHF), 3 Fälle × 3 × 2 = 18
  Aufrufe.
- **D6 Bericht:** `docs/begriffsboard-inhalt/BERICHT.md`; Zahlen-JSON je
  Ausführung unter `docs/begriffsboard-inhalt/messung/` (committet, nur
  Zahlen); Rohantworten der erfundenen Fälle unter
  `docs/begriffsboard-inhalt/roh/` (gitignoriert). Für `live` wird **keine**
  Rohantwort geschrieben, auch nicht ins gitignorierte Verzeichnis.
- **D7 Zugangsdaten:** Messkommandos laufen in einer Shell mit
  `set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a`
  (absoluter Hauptbaum-Pfad; `betrieb/` ist gitignoriert und im Worktree
  leer). Vorher nur `ja/nein` prüfen, ob `IT_LLM_KEY`/`IT_LLM_URL` gesetzt
  sind -- **Wert nie ausgeben**. Fehlen sie: Messung als „ausstehend“ mit
  Nachfahr-Kommando berichten; den Einbau dann **nicht** als gemessen
  ausgeben.
- **D8 Iteration:** ist ein Zähler nachher (validiert) nicht 0, höchstens
  zwei weitere Prompt-Runden mit je 3 Läufen; danach ehrlich berichten. Die
  Soll-Listen werden **nie** nachträglich an ein Ergebnis angepasst (sie
  sind vor dem ersten Vorher-Lauf committet).

## ANNAHMEN (nicht selbst im Code gesehen -- jeweils nachprüfen)

- ANNAHME: `betrieb/padua-gruppe1.env` im Hauptbaum enthält `IT_LLM_URL`,
  `IT_LLM_KEY`, `IT_LLM_MODELL=moonshotai/Kimi-K2.6`, `IT_WORKSHOP=padua-2026`
  (Befund des Architekten). Nachprüfen in Aufgabe 0 Schritt 3 (nur ja/nein).
  Der Sandkasten des Plan-Autors durfte `betrieb/` des Hauptbaums nicht
  einmal listen -- schlägt das beim Coder genauso fehl, gilt D7 „ausstehend“.
- ANNAHME: `einstellungen.laden()` läuft mit dieser Env durch (Web-Kanal,
  kein `IT_BOT_TOKEN`). Nachprüfen mit `--trocken` in Aufgabe 3 Schritt 9.
- ANNAHME: Die Live-Diskussion der Gruppe `7000000000000` steht in
  `/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua.db`
  (16 `aufnahme`-Zeilen mit `diskussion = 1`, zusammen 1 395 Zeichen, deutsch
  gesprochen). Nachprüfen mit `--trocken` (gibt nur Segmentzahl und
  Zeichenzahl aus).
- ANNAHME: Die Start-Soll-Liste für `live` (Aufgabe 3 Schritt 5) stammt aus
  dem Board-Auszug des Architekten, nicht aus dem Transkript. Der Coder prüft
  sie **vor** dem ersten Vorher-Lauf gegen das Transkript (lokal, stdout) und
  korrigiert sie nach der Regel in Aufgabe 3 Schritt 5.
- ANNAHME: Der Opus-Proxy läuft unter `IT_SIM_URL` (Vorgabe
  `http://127.0.0.1:28764/v1/messages`), Modell `IT_SIM_MODELL` (Vorgabe
  `claude-opus-5`). Nachprüfen in Aufgabe 7 Schritt 7 mit einem Einzelaufruf.
- ANNAHME: Der Opus-Arm über `simulation/claude.py` (kein erzwungenes Schema,
  JSON per Anweisung) ist **nicht** der Produktionspfad -- der wäre
  `modellwahl.aufruf_schema(..., ueber_claude=True)` → `szene_claude.schema`.
  Für die Entscheidungsvorlage reicht das; im Bericht so benennen.
- ANNAHME: Kein Prompt-Schnappschuss/keine Bitgleich-Fixture hasht
  `begriffsboard.md` oder das Board-JSON. Geprüft vom Plan-Autor:
  `grep -rln begriffsboard docs/prompt-audit scripts/prompt_schnappschuss.py tests/fixtures`
  trifft nur drei HTML-Fixtures (Werkbank/vereinte Seite, Dortmund/Vorgabe),
  die von Prompt und `validiere` nicht abhängen. Wird in Aufgabe 9 trotzdem
  ein Snapshot-Test rot, gilt Aufgabe 9 Schritt 4.

---

## Dateistruktur

| Datei | Aufgabe | Zuständigkeit |
|---|---|---|
| `interview_theater/begriffsboard.py` | 1, 5 | Wortlisten, `inhaltswoerter`, `traegt_beleg`, `ist_fuellsatz`, `ist_metabegriff` (1); `_belege` + zwei Zeilen in `validiere` (5) |
| `tests/test_begriffsboard_beleg.py` | 1, 5 | Helfer (1), Einhängung mit Mutanten (5) |
| `tests/test_begriffsboard.py` | 5 | ein Test absichtlich geändert |
| `simulation/begriffsboard_faelle/{ansage_en,deutsch_stt,schaerfung_stt_en}.toml` | 2 | erfundene Fälle mit Soll-Liste |
| `scripts/begriffsboard_inhalt_zaehler.py` | 2 | `Fall`, `lade_fall`, Zähler, `sprache_von`, `tabelle` -- rein |
| `tests/test_begriffsboard_inhalt_zaehler.py` | 2 | Zähler und Falldaten offline |
| `scripts/rauchtest_begriffsboard_inhalt.py` | 3 | Messlauf, `LIVE`-Soll, Stände vorher/nachher, Budget |
| `tests/test_rauchtest_begriffsboard_inhalt.py` | 3 | Skript offline (Attrappe, Verweigerung, ro) |
| `.gitignore` | 3 | `docs/begriffsboard-inhalt/roh/` |
| `docs/begriffsboard-inhalt/messung/*.json` | 4, 7 | Zahlen je Ausführung |
| `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md` | 6 (+7) | Prompt |
| `docs/begriffsboard-inhalt/BERICHT.md` | 8 | Messtabelle, Board-Beispiel |
| `AGENTS.md` | 9 | Belegpflicht im Modulabschnitt |

---

### Task 0: Vorbereitung (kein Code)

**Files:** keine.

- [ ] **Schritt 1: Ist t_cb2c4678 inzwischen in main?**

```bash
git fetch --all --quiet 2>/dev/null; git merge-base --is-ancestor wt/t_cb2c4678 main && echo GEMERGT || echo OFFEN
```

Erwartet zum Planstand: `OFFEN`. Bei `GEMERGT`:

```bash
git rebase main
```

Konflikte dürfen nur in Dateien entstehen, die dieser Plan noch nicht
angefasst hat (es gibt bis hier nur die Plandatei) -- also keine.

- [ ] **Schritt 2: VORHER_REF festhalten**

```bash
git rev-parse HEAD
```

Ohne Rebase: `55f34b58fc50de41114676222ce55e8cd1278b2e` (der Commit, auf dem
dieser Plan steht, Plan-Commit selbst ausgenommen -- der Plan ändert keinen
Code, also ist auch der Plan-Commit gleichwertig; nimm den **Elter des
Plan-Commits**, `git rev-parse HEAD~1`, wenn HEAD der Plan-Commit ist). Nach
einem Rebase: der neue `main`-SHA (`git rev-parse main`). Diesen SHA in
Aufgabe 3 als `VORHER_REF` eintragen. Er muss den **alten** `validiere` und
den **alten** Prompt tragen -- Probe:

```bash
git show <SHA>:interview_theater/sprachen/en/prompts/begriffsboard.md | grep -c "extend"
```

Erwartet: `1` (der zu streichende Merge-Satz steht noch drin).

- [ ] **Schritt 3: Zugangsdaten nur ja/nein (D7)**

```bash
bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; for v in IT_LLM_URL IT_LLM_KEY IT_LLM_MODELL IT_WORKSHOP; do [ -n "${!v}" ] && echo "$v: ja" || echo "$v: nein"; done; echo "IT_LLM_MODELL=$IT_LLM_MODELL"; echo "IT_WORKSHOP=$IT_WORKSHOP"'
```

Erwartet: vier `ja`, `IT_LLM_MODELL=moonshotai/Kimi-K2.6`,
`IT_WORKSHOP=padua-2026`. (Modell und Profil sind keine Geheimnisse, Schlüssel
und URL werden nie ausgegeben.) Bei `nein` oder „Permission denied“: weiter
mit dem Plan, Aufgaben 4 und 7 werden „ausstehend“ (siehe dort).

- [ ] **Schritt 4: Grundlinie der betroffenen Tests**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_web.py tests/test_begriffsboard_einstieg.py tests/test_begriffe_detail_wege.py tests/test_flow_audit_dynamisch.py
```

Erwartet: alles grün (`passed`, keine `failed`). Zahl notieren.

Kein Commit.

---

### Task 1: Reine Beleg-Helfer (noch NICHT in `validiere` eingehängt)

Sie kommen zuerst, weil die Zähler der Vorher-Messung sie benutzen. Solange
sie nicht eingehängt sind, ändert sich am Verhalten nichts.

**Files:**
- Modify: `interview_theater/begriffsboard.py` (neuer Block direkt **nach**
  `_steht_im_transkript`, Zeile ~71; `import re` oben ergänzen)
- Create: `tests/test_begriffsboard_beleg.py`

**Interfaces:**
- Produces:
  - `BELEG_MIN_INHALTSWOERTER: int = 2`
  - `_STOPPWOERTER`, `_ANSAGEWOERTER`, `_METAWOERTER: frozenset[str]` (alle
    Einträge in casefold-Form)
  - `_FUELL_MUSTER: tuple[re.Pattern, ...]`, `_GRUND_MARKER: re.Pattern`
  - `_woerter(text: str | None) -> list[str]`
  - `inhaltswoerter(text: str | None, begriff: str | None) -> list[str]`
  - `traegt_beleg(eintrag: dict, transkript: str) -> bool`
  - `ist_fuellsatz(text: str | None) -> bool`
  - `ist_metabegriff(begriff: str | None) -> bool`

- [ ] **Schritt 1: Den roten Test schreiben**

`tests/test_begriffsboard_beleg.py`:

```python
"""Karte t_2b9d2cbe: Belegpflicht der Begruendung im Begriffsboard (D1, D2).

Alle Beispiele sind frei erfunden -- keine Zeile aus betrieb/padua.db."""

import pytest

from interview_theater import begriffsboard as bb

TRANSKRIPT = (
    "okay test test eins zwei drei. also der erste Gepäck ist Heimat. "
    "Heimat, weil meine Oma jeden Sonntag für zwanzig Leute kocht. "
    "the first term is lighthouse. I'd suggest silence."
)


# -- Wortlisten ----------------------------------------------------------------

@pytest.mark.parametrize("liste", ["_STOPPWOERTER", "_ANSAGEWOERTER", "_METAWOERTER"])
def test_wortlisten_stehen_in_casefold_form(liste):
    """_woerter vergleicht casefold -- ein Eintrag mit Grossbuchstaben oder
    'ß' wuerde nie treffen."""
    for wort in getattr(bb, liste):
        assert wort == wort.casefold(), wort


def test_beleg_min_ist_zwei():
    assert bb.BELEG_MIN_INHALTSWOERTER == 2


# -- inhaltswoerter -----------------------------------------------------------

@pytest.mark.parametrize("text, begriff, erwartet", [
    ("the first term is lighthouse", "lighthouse", []),
    ("I'd suggest silence", "silence", []),
    ("also der erste Gepäck ist Heimat", "Heimat", []),
    ("Mikrofon Test eins zwei drei 1 2 3", "Heimat", []),
    ("weil meine Oma jeden Sonntag für zwanzig Leute kocht", "Heimat",
     ["oma", "jeden", "sonntag", "zwanzig", "leute", "kocht"]),
    ("wo meine Oma kocht", "Heimat", ["oma", "kocht"]),
    ("KI-Roboter, der alles mitschreibt", "KI-Roboter", ["mitschreibt"]),  # "alles" ist Stoppwort
])
def test_inhaltswoerter(text, begriff, erwartet):
    assert bb.inhaltswoerter(text, begriff) == erwartet


# -- traegt_beleg -------------------------------------------------------------

def _e(zitat, begriff="Heimat", begruendung="egal"):
    return {"begriff": begriff, "zitat": zitat, "begruendung": begruendung}


def test_beleg_mit_inhalt_traegt():
    assert bb.traegt_beleg(_e("weil meine Oma jeden Sonntag für zwanzig Leute kocht"), TRANSKRIPT)


def test_leeres_zitat_traegt_nicht():
    assert not bb.traegt_beleg(_e(""), TRANSKRIPT)


def test_nicht_woertliches_zitat_traegt_nicht():
    assert not bb.traegt_beleg(_e("weil die Oma immer kocht und backt"), TRANSKRIPT)


def test_nur_ansage_traegt_nicht():
    assert not bb.traegt_beleg(_e("also der erste Gepäck ist Heimat"), TRANSKRIPT)
    assert not bb.traegt_beleg(_e("the first term is lighthouse", "lighthouse"), TRANSKRIPT)


def test_ein_restwort_traegt_nicht():
    transkript = "die Sprecherin nennt Heimat als besten Begriff"
    assert not bb.traegt_beleg(_e("Heimat als besten Begriff"), transkript)


# -- ist_fuellsatz ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Wird als Begriff gesammelt.",
    "Wird als dritter Begriff gesammelt.",
    "Wird als etwas Erwähntes aufgeführt.",
    "Wurde im Gespräch genannt.",
    "Kam zweimal vor.",
    "Die Sprecherin schlägt es als ersten Gepäck vor.",
    "Die Gruppe nennt es als Begriff.",
    "Is mentioned as a term.",
    "Was suggested by the group.",
    "Came up twice.",
    "The speaker proposes it as the first term.",
])
def test_fuellsatz_wird_erkannt(text):
    assert bb.ist_fuellsatz(text)


@pytest.mark.parametrize("text", [
    "",
    "Wo die Oma kocht.",
    "Heimat ist für sie der Ort, an dem die Oma sonntags kocht.",
    "Wird genannt, weil die Oma dort jeden Sonntag kocht.",
    "It was named because the grandfather kept the light on every night.",
    "The pier is where the old men tell their stories.",
])
def test_echter_grund_ist_kein_fuellsatz(text):
    assert not bb.ist_fuellsatz(text)


# -- ist_metabegriff ----------------------------------------------------------

@pytest.mark.parametrize("begriff", [
    "Begriff", "Term", "Gepäck", "GEPÄCK", "Gepaeck", "Betreff", "Test",
    "Test 1 2 3", "Mikrofon Test", "microphone", "Wort",
])
def test_metabegriff(begriff):
    assert bb.ist_metabegriff(begriff)


@pytest.mark.parametrize("begriff", [
    "Heimat", "KI", "KI-Roboter", "Alice Hotel", "Cappuccino", "eins", "", None,
])
def test_kein_metabegriff(begriff):
    assert not bb.ist_metabegriff(begriff)
```

- [ ] **Schritt 2: Rot sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py`
Expected: FAIL / ERROR mit `AttributeError: module 'interview_theater.begriffsboard' has no attribute '_STOPPWOERTER'` (bzw. `inhaltswoerter` …).

- [ ] **Schritt 3: Implementieren**

In `interview_theater/begriffsboard.py` oben bei den Importen `import re`
ergänzen (alphabetisch zwischen `os` und `threading`). Dann direkt **nach**
`_steht_im_transkript` einfügen:

```python
# -- Belegpflicht (Karte t_2b9d2cbe, D1/D2) -----------------------------------
#
# Eine Begruendung gilt nur, wenn ein woertlich geprueftes Zitat sie traegt,
# das mehr enthaelt als den Begriff und die Ansage ("der erste Begriff ist
# X"). Die Woerter werden ueber ``schluessel`` (zitat.normalisiere +
# casefold) gewonnen -- keine zweite Normalisierung. Alle Listen gelten fuer
# DE und EN zugleich: gemessen schrieb Kimi unter dem EN-Profil deutsche
# Begruendungen (Live-Board 04.10.2026), eine Liste nur der Profilsprache
# liesse genau diesen Fall durch. Eintraege in casefold-Form (Test).

#: Mindestzahl Inhaltswoerter im Zitat. Ein einzelnes Restwort ist in den
#: beobachteten Fehlbildern ein Adjektiv oder ein STT-Rest aus der Ansage
#: ("als besten Gepaeck vor" -> "besten"); ein Grund braucht Gegenstand und
#: Aussage ("wo meine Oma kocht" -> "oma", "kocht").
BELEG_MIN_INHALTSWOERTER = 2

_STOPPWOERTER = frozenset("""
aber alle alles als also am an auch auf aus bei bin bis bist da dann das dass
dem den der des dich die dir doch dort du ein eine einem einen einer eines er
es etwa euch für fuer gar hab habe haben hat hier ich ihm ihn ihr ihre im in
ist ja jetzt kann kein keine man mal mein meine meinem meinen meiner mich mir
mit muss nach nee nein nicht nichts noch nur ob oder schon sehr sein seine
sich sie sind so soll sollte uns und unser vom von war waren was weil wenn wer
wie wir wird wo zu zum zur äh ähm hm genau eben halt einfach eigentlich
a about all also am an and any are as at be because been but by can could d
did do does for from had has have he her here him his how i if in into is it
its just ll like m me my no not now of oh ok okay on or our re s she so some
that the their them then there they this to too uh um us ve very we well were
what when where which who will with would yeah yes you your
eins zwei drei vier fünf fuenf one two three four five
""".split())

#: Woerter einer Ansage-Formel ("der erste Begriff ist X", "I'd suggest X")
#: samt der beobachteten STT-Varianten von "Begriff".
_ANSAGEWOERTER = frozenset("""
begriff begriffe term terms wort wörter woerter word words gepäck gepaeck
betreff vorschlag vorschlagen schlage schlägt schlaegt schlagen vor suggest
suggests suggestion propose proposes pick nehmen nehme take nenne nennen name
erste erster ersten erstes zweite zweiter zweiten dritte dritter dritten
vierte fünfte fuenfte nächste naechste nächster naechster letzte letzter
weitere weiterer first second third fourth fifth next last another nummer
number
""".split())

#: Woerter, die nie ein Begriff der Gruppe sind (D2) -- Ansage- und
#: Mikrofon-Gerede. Klein und geschlossen.
_METAWOERTER = frozenset("""
begriff begriffe term terms wort word gepäck gepaeck betreff test tests
testing mikrofon mikro microphone mic aufnahme recording hallo hello check
""".split())

#: Fuell-Begruendungen: sagen nur, DASS der Begriff fiel. Gesucht im
#: casefold-Text (``schluessel``).
_FUELL_MUSTER = (
    re.compile(r"\b(wird|wurde|werden|wurden|ist|sind)\b.{0,80}?\b(genannt|erwähnt|erwaehnt"
               r"|aufgeführt|aufgefuehrt|gesammelt|vorgeschlagen|aufgelistet|notiert"
               r"|festgehalten)\b"),
    re.compile(r"\bkam(en)?\b.{0,40}?\bvor\b"),
    re.compile(r"\bschl(ä|ae)gt\b.{0,80}?\bvor\b"),
    re.compile(r"\b(nennt|nennen)\b"),
    re.compile(r"\b(is|was|are|were|gets|got)\b.{0,80}?\b(named|mentioned|listed|collected"
               r"|suggested|proposed|noted|brought up|put forward)\b"),
    re.compile(r"\bcame up\b"),
    re.compile(r"\b(suggests|proposes|names|mentions)\b"),
)

#: Ein Grund-Marker macht aus einem Fuellsatz-Treffer einen Satz mit Grund
#: ("wird genannt, weil ...") -- ob er bleibt, entscheidet dann der Beleg.
_GRUND_MARKER = re.compile(r"\b(weil|denn|damit|deshalb|darum|because|since|so that|therefore)\b")


def _woerter(text: str | None) -> list[str]:
    return re.findall(r"\w+", schluessel(text))


def inhaltswoerter(text: str | None, begriff: str | None) -> list[str]:
    """Die Woerter von ``text`` ohne Begriff, Ansage-, Meta- und
    Stoppwoerter und ohne reine Ziffern -- in Reihenfolge, mit Doppelten."""
    weg = set(_woerter(begriff)) | _STOPPWOERTER | _ANSAGEWOERTER | _METAWOERTER
    return [w for w in _woerter(text) if w not in weg and not w.isdigit()]


def traegt_beleg(eintrag: dict, transkript: str) -> bool:
    """D1: das Zitat steht woertlich im Transkript (``zitat.pruefe``) UND
    traegt mindestens ``BELEG_MIN_INHALTSWOERTER`` Inhaltswoerter."""
    z = str(eintrag.get("zitat") or "").strip()
    return (bool(z) and zitat.pruefe(z, transkript)
            and len(inhaltswoerter(z, eintrag.get("begriff"))) >= BELEG_MIN_INHALTSWOERTER)


def ist_fuellsatz(text: str | None) -> bool:
    """D1: eine Begruendung, die nur sagt, dass der Begriff genannt/
    gesammelt/vorgeschlagen wurde -- ohne Grund-Marker."""
    k = schluessel(text)
    return (bool(k) and any(m.search(k) for m in _FUELL_MUSTER)
            and not _GRUND_MARKER.search(k))


def ist_metabegriff(begriff: str | None) -> bool:
    """D2: der Begriff besteht nur aus Meta-, Stoppwoertern und Ziffern und
    traegt mindestens ein Meta-Wort ("Test 1 2 3", "Gepaeck")."""
    woerter = _woerter(begriff)
    return (any(w in _METAWOERTER for w in woerter)
            and all(w in _METAWOERTER or w in _STOPPWOERTER or w.isdigit() for w in woerter))
```

Hinweis: `ist_metabegriff(None)` → `_woerter(None)` → `schluessel(None)` ist
`""` → `[]` → `any([])` ist `False`. Richtig.

- [ ] **Schritt 4: Grün sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py`
Expected: alle `passed`.

Schlägt ein einzelner Parameter fehl, zuerst prüfen, ob das Wort in einer
Liste fehlt (z. B. `inhaltswoerter` für „KI-Roboter, der alles
mitschreibt“: `der` ist Stoppwort, `ki`/`roboter` sind Begriffswörter). Die
**Testerwartung** nur ändern, wenn sie offensichtlich falsch abgeschrieben
ist, nie um die Liste zu schonen.

- [ ] **Schritt 5: Bestehende Board-Tests unverändert grün**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py`
Expected: gleiche Zahl `passed` wie in Aufgabe 0 Schritt 4 für diese zwei Dateien (die Helfer sind noch nicht eingehängt).

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/begriffsboard.py tests/test_begriffsboard_beleg.py
git commit -m "$(cat <<'EOF'
Begriffsboard: Beleg-Helfer (Inhaltswoerter, Fuellsatz, Metabegriff), noch nicht eingehaengt (t_2b9d2cbe, Aufgabe 1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Erfundene Fälle und Zähler

**Files:**
- Create: `simulation/begriffsboard_faelle/ansage_en.toml`
- Create: `simulation/begriffsboard_faelle/deutsch_stt.toml`
- Create: `simulation/begriffsboard_faelle/schaerfung_stt_en.toml`
- Create: `scripts/begriffsboard_inhalt_zaehler.py`
- Create: `tests/test_begriffsboard_inhalt_zaehler.py`

**Interfaces:**
- Consumes: `begriffsboard.schluessel`, `ist_fuellsatz`, `traegt_beleg`,
  `ist_metabegriff` (Aufgabe 1); `zitat.pruefe`.
- Produces (`scripts/begriffsboard_inhalt_zaehler.py`):
  - `@dataclass(frozen=True) class Fall: name: str; beschreibung: str;
    sprache_gesprochen: str; segmente: tuple[str, ...];
    soll: tuple[tuple[str, ...], ...]; varianten: tuple[str, ...];
    meta: tuple[str, ...]; mit_grund: tuple[str, ...]`
  - `FAELLE_VERZ: Path`, `ERFUNDEN: tuple[str, ...] = ("ansage_en", "deutsch_stt", "schaerfung_stt_en")`
  - `lade_fall(pfad: Path) -> Fall`, `lade_erfundene() -> list[Fall]`
  - `ZAEHLER: tuple[str, ...]` (die sechs Ziel-0-Zähler),
    `INFO: tuple[str, ...] = ("eintraege", "begruendungen_belegt")`
  - `sprache_von(text: str | None) -> str` (`"de"`, `"en"` oder `""`)
  - `zaehle(board: list[dict], transkript: str, fall: Fall, profilsprache: str) -> dict[str, int]`
  - `summe(zaehlungen: list[dict[str, int]]) -> dict[str, int]`
  - `tabelle(messungen: list[dict]) -> str` (Markdown)

**Zählerdefinitionen** (alle am Board nach Schritt 2 eines Laufs, über alle
Einträge **inklusive** `status = verworfen`):

| Zähler | Zählt +1 je … |
|---|---|
| `fuell_begruendungen` | Eintrag mit nicht leerer `begruendung` und `ist_fuellsatz(begruendung)` |
| `begruendung_ohne_beleg` | Eintrag mit nicht leerer `begruendung` und `not traegt_beleg(eintrag, transkript)` |
| `meta_begriffe` | Eintrag mit `ist_metabegriff(begriff)` **oder** `schluessel(begriff)` in den `meta` des Falls |
| `dubletten` | (a) jeder **weitere** Eintrag einer Soll-Gruppe (Gruppe mit k Treffern → k−1), (b) jeder Eintrag, dessen Begriff eine `variante` des Falls ist, (c) jeder Eintrag mit Merge-/STT-Spur in der `begruendung` (`aufgegangen`, `zusammengeführt`, `verhört`, `merged`, `misheard`, `stt` …) |
| `sprache_ungleich_profil` | je nicht leeres Feld `begruendung`/`doppelbedeutung`, dessen `sprache_von` weder `""` noch die Profilsprache ist |
| `begriffe_fehlend` | Soll-Gruppe ohne Treffer |
| `eintraege` (Info) | Einträge gesamt |
| `begruendungen_belegt` (Info) | nicht leere `begruendung` mit `traegt_beleg` -- macht sichtbar, ob der Code am Ende **alles** leer macht |

Treffer einer Soll-Gruppe / Variante: `schluessel(begriff)` gleich
`schluessel(alternative)` -- nur Gleichheit, Schreibweisen stehen explizit als
Alternativen in den Falldaten. Die Validierungs-Spalte von
`fuell_begruendungen`, `begruendung_ohne_beleg` und (zum Teil)
`meta_begriffe` ist nach Aufgabe 5 **per Konstruktion** 0 (gleiche
Funktionen); aussagekräftig sind dort die Roh-Spalte, `dubletten`,
`sprache_ungleich_profil`, `begriffe_fehlend` und `begruendungen_belegt`. So
im Bericht benennen.

- [ ] **Schritt 1: Die drei Fälle anlegen** (frei erfunden, vor jeder Messung
  festgelegt; die Soll-Listen werden danach **nicht** mehr geändert)

`simulation/begriffsboard_faelle/ansage_en.toml`:

```toml
# Frei erfunden (Karte t_2b9d2cbe). Ansage-Formeln, Testgerede, ein STT-Verhoerer
# von "term" ("germ", "turn"), zwei echte Gruende (lighthouse, silence), zwei
# Begriffe ohne Grund (ferry, harbour) -- deren begruendung muss leer bleiben.
name = "ansage_en"
beschreibung = "EN gesprochen: Ansage-Formeln, Testgerede, STT 'germ'/'turn' fuer 'term'"
sprache_gesprochen = "en"
segmente = [
  "okay test test one two three can you hear me is this recording yes it's recording. okay so the first term is lighthouse. I'd suggest lighthouse because my grandfather kept the light on the island every night and we always waited for the beam.",
  "another term would be ferry. the next germ is ferry ticket no sorry just ferry. and I'd suggest silence",
  "silence because nobody on the boat ever said what they were afraid of, they just looked at the water. okay my turn is harbour. harbour",
  "yes harbour, and lighthouse again, lighthouse for sure, everyone agrees on lighthouse. test is the mic still on okay good",
]
varianten = ["ferry ticket"]
meta = ["term", "germ", "turn", "test", "mic", "recording"]
mit_grund = ["lighthouse", "silence"]

[[soll]]
alternativen = ["lighthouse"]
[[soll]]
alternativen = ["ferry"]
[[soll]]
alternativen = ["silence"]
[[soll]]
alternativen = ["harbour", "harbor"]
```

`simulation/begriffsboard_faelle/deutsch_stt.toml`:

```toml
# Frei erfunden (Karte t_2b9d2cbe). DEUTSCH gesprochen bei EN-Profil:
# Begruendungen muessen trotzdem englisch sein (D4). STT "Gepäck"/"Betreff"
# fuer "Begriff", Mikrofontest, Schaerfung Roboter -> KI-Roboter, echte
# Gruende an Heimat und Grenze, Tauben ohne Grund.
name = "deutsch_stt"
beschreibung = "DE gesprochen, EN-Profil: STT Gepäck/Betreff, Mikrofontest, Roboter -> KI-Roboter"
sprache_gesprochen = "de"
segmente = [
  "Ja hallo, Mikrofon Test eins zwei drei, hört man uns? Okay. Also der erste Gepäck ist Heimat. Heimat, weil meine Oma in Izmir jeden Sonntag für zwanzig Leute kocht und keiner nach Hause geht, bevor alle satt sind.",
  "Der zweite Betreff ist Roboter. Ein Roboter, der im Laden an der Kasse steht.",
  "Nee, nicht einfach Roboter, ein KI-Roboter, der alles mitschreibt, was wir sagen. KI-Roboter. Und noch ein Begriff ist Grenze.",
  "Grenze, weil man im Bus nach Padua plötzlich nicht mehr verstanden hat, was der Fahrer sagt, und alle still wurden. Und ich schlage Tauben vor. Tauben.",
  "Tauben, ja, und noch mal KI-Roboter, da sind wir uns einig. Test, ist das noch an?",
]
varianten = ["Roboter"]
meta = ["Gepäck", "Betreff", "Begriff", "Mikrofon", "Test"]
mit_grund = ["Heimat", "Grenze"]

[[soll]]
alternativen = ["Heimat"]
[[soll]]
alternativen = ["KI-Roboter", "KI Roboter"]
[[soll]]
alternativen = ["Grenze"]
[[soll]]
alternativen = ["Tauben"]
```

`simulation/begriffsboard_faelle/schaerfung_stt_en.toml`:

```toml
# Frei erfunden (Karte t_2b9d2cbe). Phonetischer Verhoerer "peer" fuer "pier"
# (1:4), Schaerfung boat -> fishing boat, ein echter Grund (pier), ein
# Begriff mit ausdruecklich keinem Grund (storm).
name = "schaerfung_stt_en"
beschreibung = "EN gesprochen: STT peer/pier, Schaerfung boat -> fishing boat, storm ohne Grund"
sprache_gesprochen = "en"
segmente = [
  "so for me the word is pier, the old pier where the fishermen sit. the pier is falling apart but people still go there every evening to talk.",
  "yeah pier. I'd suggest boat. a boat. actually not just a boat, a fishing boat, the small fishing boats that come in at five",
  "fishing boat yes. and the peer should be where the scene starts because that's where the old men tell their stories on the pier",
  "and storm, I'd suggest storm. storm. no reason, just storm. okay is it still recording",
]
varianten = ["peer", "boat"]
meta = ["word", "recording"]
mit_grund = ["pier"]

[[soll]]
alternativen = ["pier", "old pier"]
[[soll]]
alternativen = ["fishing boat"]
[[soll]]
alternativen = ["storm"]
```

- [ ] **Schritt 2: Den roten Test schreiben**

`tests/test_begriffsboard_inhalt_zaehler.py`:

```python
"""Karte t_2b9d2cbe: Zaehler und Falldaten der Begriffsboard-Messung -- offline."""

import pytest

from interview_theater import begriffsboard
from scripts import begriffsboard_inhalt_zaehler as z


def _fall(**kw):
    basis = dict(name="t", beschreibung="", sprache_gesprochen="de",
                 segmente=("a", "b"), soll=(("Heimat",), ("KI-Roboter", "KI Roboter")),
                 varianten=("Roboter",), meta=("Gepäck",), mit_grund=("Heimat",))
    basis.update(kw)
    return z.Fall(**basis)


TRANSKRIPT = ("der erste Gepäck ist Heimat. Heimat, weil meine Oma jeden Sonntag kocht. "
              "Roboter. nicht einfach Roboter, ein KI-Roboter.")


def _e(begriff, begruendung="", zitat="", doppelbedeutung="", status="kandidat"):
    return {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": begruendung,
            "zitat": zitat, "doppelbedeutung": doppelbedeutung, "status": status}


# -- Falldaten ----------------------------------------------------------------

def test_drei_erfundene_faelle_laden():
    faelle = z.lade_erfundene()
    assert [f.name for f in faelle] == list(z.ERFUNDEN)
    assert any(f.sprache_gesprochen != "en" for f in faelle)  # D5: deutsch bei EN-Profil


@pytest.mark.parametrize("fall", z.lade_erfundene(), ids=lambda f: f.name)
def test_falldaten_sind_im_transkript_belegt(fall):
    transkript = begriffsboard.schluessel("\n\n".join(fall.segmente))
    assert len(fall.segmente) >= 2                      # Lauf hat zwei Schritte
    for gruppe in fall.soll:
        assert any(begriffsboard.schluessel(a) in transkript for a in gruppe), gruppe
    for wort in fall.varianten + fall.meta + fall.mit_grund:
        assert begriffsboard.schluessel(wort) in transkript, wort


# -- sprache_von --------------------------------------------------------------

@pytest.mark.parametrize("text, erwartet", [
    ("Die Gruppe will den Ort, an dem die Oma kocht.", "de"),
    ("The group wants the place where the grandmother cooks.", "en"),
    ("Heimat", ""),
    ("", ""),
    ("Größe", "de"),
])
def test_sprache_von(text, erwartet):
    assert z.sprache_von(text) == erwartet


# -- zaehle -------------------------------------------------------------------

def test_sauberes_board_zaehlt_null():
    board = [
        _e("Heimat", "The grandmother cooks there every Sunday.",
           "weil meine Oma jeden Sonntag kocht"),
        _e("KI-Roboter"),
    ]
    zahl = z.zaehle(board, TRANSKRIPT, _fall(), "en")
    assert {k: zahl[k] for k in z.ZAEHLER} == dict.fromkeys(z.ZAEHLER, 0)
    assert zahl["eintraege"] == 2
    assert zahl["begruendungen_belegt"] == 1


def test_fehlerbilder_werden_gezaehlt():
    board = [
        _e("Heimat", "Wird als Begriff gesammelt.", "der erste Gepäck ist Heimat"),
        _e("Gepäck"),
        _e("Roboter", "Ist in KI-Roboter aufgegangen.", status="verworfen"),
        _e("heimat"),
    ]
    zahl = z.zaehle(board, TRANSKRIPT, _fall(), "en")
    assert zahl["fuell_begruendungen"] == 1        # "Wird als Begriff gesammelt."
    assert zahl["begruendung_ohne_beleg"] == 2     # Ansage-Zitat + Roboter ohne Zitat
    assert zahl["meta_begriffe"] == 1              # Gepäck
    assert zahl["dubletten"] == 3                  # 2. Heimat + Variante Roboter + Merge-Spur
    assert zahl["sprache_ungleich_profil"] == 2    # zwei deutsche Begruendungen ("wird"/"als", "ist")
    assert zahl["begriffe_fehlend"] == 1           # KI-Roboter fehlt
    assert zahl["begruendungen_belegt"] == 0


def test_summe_addiert_je_schluessel():
    assert z.summe([{"a": 1, "b": 0}, {"a": 2, "b": 3}]) == {"a": 3, "b": 3}


def test_tabelle_enthaelt_jeden_zaehler_und_arm():
    messung = {"arm": "vorher", "modell": "kimi", "runde": 0,
               "faelle": {"t": {"laeufe": 3, "fehler": 0,
                                "roh": dict.fromkeys(z.ZAEHLER + z.INFO, 1),
                                "validiert": dict.fromkeys(z.ZAEHLER + z.INFO, 0)}}}
    text = z.tabelle([messung])
    for name in z.ZAEHLER:
        assert name in text
    assert "vorher" in text and "kimi" in text
```

- [ ] **Schritt 3: Rot sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_inhalt_zaehler.py`
Expected: ERROR `ModuleNotFoundError: No module named 'scripts.begriffsboard_inhalt_zaehler'`.

- [ ] **Schritt 4: Implementieren**

`scripts/begriffsboard_inhalt_zaehler.py`:

```python
"""Die Zaehler der Begriffsboard-Inhaltsmessung (Karte t_2b9d2cbe) -- rein,
offline getestet (``tests/test_begriffsboard_inhalt_zaehler.py``). Kein Netz,
keine Datenbank, kein Modell. Der Messlauf steht in
``scripts/rauchtest_begriffsboard_inhalt.py``."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from interview_theater import begriffsboard

FAELLE_VERZ = Path(__file__).resolve().parent.parent / "simulation" / "begriffsboard_faelle"
ERFUNDEN = ("ansage_en", "deutsch_stt", "schaerfung_stt_en")

ZAEHLER = ("fuell_begruendungen", "begruendung_ohne_beleg", "meta_begriffe",
           "dubletten", "sprache_ungleich_profil", "begriffe_fehlend")
INFO = ("eintraege", "begruendungen_belegt")

#: Merge-/STT-Spuren in einer Begruendung (D3) -- casefold.
_SPUR = re.compile(r"\b(aufgegangen|zusammengeführt|zusammengefuehrt|verhört|verhoert"
                   r"|verhörer|verhoerer|merged|misheard|mishearing|stt)\b")

#: Deterministische Sprachheuristik: Funktionswoerter, die nur in einer der
#: beiden Sprachen vorkommen ("was", "die", "an" stehen deshalb in keiner).
_DE = frozenset("der das und ist nicht wird mit für fuer ein eine sich auch als von zu "
                "den dem sie er es im auf weil dass wie wo oder aber noch nur sehr hat "
                "haben werden wurde ihr ihre gruppe will".split())
_EN = frozenset("the and is of to it with for as that this are be by not they their "
                "because when what where or but only very has have group wants".split())
_UMLAUT = re.compile(r"[äöüß]")


@dataclass(frozen=True)
class Fall:
    name: str
    beschreibung: str
    sprache_gesprochen: str
    segmente: tuple[str, ...]
    soll: tuple[tuple[str, ...], ...]
    varianten: tuple[str, ...]
    meta: tuple[str, ...]
    mit_grund: tuple[str, ...]


def lade_fall(pfad: Path) -> Fall:
    with open(pfad, "rb") as f:
        d = tomllib.load(f)
    return Fall(
        name=d["name"], beschreibung=d["beschreibung"],
        sprache_gesprochen=d["sprache_gesprochen"],
        segmente=tuple(d["segmente"]),
        soll=tuple(tuple(g["alternativen"]) for g in d["soll"]),
        varianten=tuple(d.get("varianten", ())), meta=tuple(d.get("meta", ())),
        mit_grund=tuple(d.get("mit_grund", ())),
    )


def lade_erfundene() -> list[Fall]:
    return [lade_fall(FAELLE_VERZ / f"{name}.toml") for name in ERFUNDEN]


def sprache_von(text: str | None) -> str:
    k = begriffsboard.schluessel(text)
    woerter = re.findall(r"\w+", k)
    de = sum(w in _DE for w in woerter) + 2 * len(_UMLAUT.findall(k))
    en = sum(w in _EN for w in woerter)
    if de > en:
        return "de"
    if en > de:
        return "en"
    return ""


def _trifft(begriff: str, alternativen) -> bool:
    k = begriffsboard.schluessel(begriff)
    return any(k == begriffsboard.schluessel(a) for a in alternativen)


def zaehle(board: list[dict], transkript: str, fall: Fall, profilsprache: str) -> dict[str, int]:
    meta = {begriffsboard.schluessel(m) for m in fall.meta}
    zahl = dict.fromkeys(ZAEHLER + INFO, 0)
    zahl["eintraege"] = len(board)
    for e in board:
        grund = (e.get("begruendung") or "").strip()
        if grund and begriffsboard.ist_fuellsatz(grund):
            zahl["fuell_begruendungen"] += 1
        if grund and not begriffsboard.traegt_beleg(e, transkript):
            zahl["begruendung_ohne_beleg"] += 1
        if grund and begriffsboard.traegt_beleg(e, transkript):
            zahl["begruendungen_belegt"] += 1
        if (begriffsboard.ist_metabegriff(e.get("begriff"))
                or begriffsboard.schluessel(e.get("begriff")) in meta):
            zahl["meta_begriffe"] += 1
        if _trifft(e.get("begriff", ""), fall.varianten):
            zahl["dubletten"] += 1
        if _SPUR.search(begriffsboard.schluessel(grund)):
            zahl["dubletten"] += 1
        for feld in ("begruendung", "doppelbedeutung"):
            s = sprache_von(e.get(feld))
            if (e.get(feld) or "").strip() and s and s != profilsprache:
                zahl["sprache_ungleich_profil"] += 1
    for gruppe in fall.soll:
        treffer = sum(_trifft(e.get("begriff", ""), gruppe) for e in board)
        if treffer == 0:
            zahl["begriffe_fehlend"] += 1
        else:
            zahl["dubletten"] += treffer - 1
    return zahl


def summe(zaehlungen: list[dict[str, int]]) -> dict[str, int]:
    gesamt: dict[str, int] = {}
    for z in zaehlungen:
        for k, v in z.items():
            gesamt[k] = gesamt.get(k, 0) + v
    return gesamt


def tabelle(messungen: list[dict]) -> str:
    """Eine Markdown-Tabelle: je Fall eine Zeile je (Arm, Modell, Runde,
    Stufe), Spalten = Zaehler + Info. Summen ueber die Laeufe."""
    spalten = ZAEHLER + INFO
    zeilen = ["| Fall | Arm | Modell | Runde | Stufe | Läufe/Fehler | " + " | ".join(spalten) + " |",
              "|" + "---|" * (6 + len(spalten))]
    for m in messungen:
        for fall, d in m["faelle"].items():
            for stufe in ("roh", "validiert"):
                werte = " | ".join(str(d[stufe].get(s, 0)) for s in spalten)
                zeilen.append(f"| {fall} | {m['arm']} | {m['modell']} | {m['runde']} | {stufe} | "
                              f"{d['laeufe']}/{d['fehler']} | {werte} |")
    return "\n".join(zeilen)
```

- [ ] **Schritt 5: Grün sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_inhalt_zaehler.py`
Expected: alle `passed`.

Prüfe besonders `test_fehlerbilder_werden_gezaehlt`: rechnet ein Zähler
anders, ist **zuerst** die Rechnung im Test nachzuvollziehen (Kommentar je
Zeile); die Zählerdefinition in der Tabelle oben ist bindend.

- [ ] **Schritt 6: Commit**

```bash
git add simulation/begriffsboard_faelle scripts/begriffsboard_inhalt_zaehler.py tests/test_begriffsboard_inhalt_zaehler.py
git commit -m "$(cat <<'EOF'
Begriffsboard-Messung: drei erfundene Faelle mit Soll-Liste, Zaehler offline (t_2b9d2cbe, Aufgabe 2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Das Messskript (offline getestet) und die Live-Soll-Liste

**Files:**
- Create: `scripts/rauchtest_begriffsboard_inhalt.py`
- Create: `tests/test_rauchtest_begriffsboard_inhalt.py`
- Modify: `.gitignore` (eine Zeile)

**Interfaces:**
- Consumes: `scripts.begriffsboard_inhalt_zaehler` (Aufgabe 2),
  `begriffsboard.lies`, `begriffsboard.validiere`, `begriffsboard.SCHEMA`,
  `begriffsboard._nutzertext`, `anweisungen.hole`/`fuelle`, `llm.LLM.schema`,
  `repo.diskussion_transkript`, `simulation.claude.Claude.json_objekt`.
- Produces:
  - `VORHER_REF: str`, `LIVE: zaehler.Fall`, `LIVE_DB_VORGABE: str`,
    `LIVE_CHAT_ID = 7_000_000_000_000`, `MAX_AUFRUFE = 30`,
    `BUDGET_CHF = 0.75`
  - `@dataclass(frozen=True) class Stand: name, system, schema, validiere, nutzertext`
  - `stand_vorher(ref: str = VORHER_REF) -> Stand`, `stand_nachher() -> Stand`
  - `pruefe_auswahl(faelle: list[str], modell: str) -> None` (SystemExit bei opus+live)
  - `lies_live_segmente(pfad: str, chat_id: int) -> list[str]`
  - `ein_lauf(rufe, stand: Stand, fall, profil: str) -> tuple[dict, list, list]`
    mit `rufe(stand: Stand, nutzer: str) -> list` (Roh-Board)
  - `roh_pfad(fall_name: str, arm: str, modell: str, runde: int, lauf: int) -> Path | None`
    (`None` für `live`)

- [ ] **Schritt 1: `.gitignore` ergänzen**

Am Ende von `.gitignore` anhängen:

```
# Begriffsboard-Inhaltsmessung (t_2b9d2cbe): Rohantworten der erfundenen Faelle
docs/begriffsboard-inhalt/roh/
```

- [ ] **Schritt 2: Den roten Test schreiben**

`tests/test_rauchtest_begriffsboard_inhalt.py`:

```python
"""Karte t_2b9d2cbe: das Messskript offline -- keine Netz-, keine Live-DB-Zugriffe."""

import sqlite3

import pytest

from interview_theater import sprache, workshop
from scripts import begriffsboard_inhalt_zaehler as zaehler
from scripts import rauchtest_begriffsboard_inhalt as skript


@pytest.fixture
def padua(monkeypatch):
    """Muster aus tests/test_chat_sprache.py: Profil-Cache vor UND nach dem
    Test leeren, sonst erbt der naechste Test padua-2026."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_live_mit_opus_wird_verweigert():
    with pytest.raises(SystemExit):
        skript.pruefe_auswahl(["ansage_en", "live"], "opus")


def test_opus_mit_erfundenen_ist_erlaubt():
    skript.pruefe_auswahl(list(zaehler.ERFUNDEN), "opus")


def test_live_fall_traegt_kein_transkript():
    assert skript.LIVE.segmente == ()
    assert skript.LIVE.soll  # Soll-Liste steht im Skript


def test_live_rohantworten_werden_nie_geschrieben():
    assert skript.roh_pfad("live", "nachher", "kimi", 0, 1) is None
    assert skript.roh_pfad("ansage_en", "nachher", "kimi", 0, 1).parent == skript.ROH_VERZ


def test_live_db_wird_nur_lesend_geoeffnet(tmp_path, monkeypatch):
    gesehen = []
    echt = sqlite3.connect

    def merke(ziel, *a, **kw):
        gesehen.append((ziel, kw.get("uri")))
        return echt(ziel, *a, **kw)

    monkeypatch.setattr(skript.sqlite3, "connect", merke)
    with pytest.raises(sqlite3.OperationalError):
        skript.lies_live_segmente(str(tmp_path / "gibtsnicht.db"), skript.LIVE_CHAT_ID)
    assert gesehen and gesehen[0][0].endswith("?mode=ro") and gesehen[0][1] is True
    assert not (tmp_path / "gibtsnicht.db").exists()


def test_vorher_stand_kommt_aus_git():
    stand = skript.stand_vorher()
    assert stand.name == "vorher"
    assert stand.schema["required"] == ["board"]
    assert callable(stand.validiere) and callable(stand.nutzertext)
    assert "term board" in stand.system  # der EN-Prompt


def test_ein_lauf_mit_attrappe_zaehlt_beide_stufen(padua):
    fall = zaehler.lade_erfundene()[1]  # deutsch_stt
    antworten = iter([
        [{"begriff": "Heimat", "nennungen": 1, "zustimmung": 1,
          "begruendung": "Wird als Begriff gesammelt.", "zitat": "der erste Gepäck ist Heimat",
          "doppelbedeutung": "", "status": "kandidat"}],
        [{"begriff": "Heimat", "nennungen": 2, "zustimmung": 1,
          "begruendung": "Wird als Begriff gesammelt.", "zitat": "der erste Gepäck ist Heimat",
          "doppelbedeutung": "", "status": "kandidat"},
         {"begriff": "Test", "nennungen": 2, "zustimmung": 0, "begruendung": "",
          "zitat": "", "doppelbedeutung": "", "status": "kandidat"}],
    ])
    nutzertexte = []

    def rufe(stand, nutzer):
        nutzertexte.append(nutzer)
        return next(antworten)

    zahlen, roh, validiert = skript.ein_lauf(rufe, skript.stand_nachher(), fall, "en")
    assert len(nutzertexte) == 2                     # Haelfte, dann ganz
    assert set(zahlen) == {"roh", "validiert"}
    assert zahlen["roh"]["meta_begriffe"] == 1       # "Test"
    assert zahlen["roh"]["fuell_begruendungen"] == 1
    assert len(roh) == 2
```

- [ ] **Schritt 3: Rot sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_rauchtest_begriffsboard_inhalt.py`
Expected: ERROR `ModuleNotFoundError: No module named 'scripts.rauchtest_begriffsboard_inhalt'`.

- [ ] **Schritt 4: Das Skript schreiben**

`scripts/rauchtest_begriffsboard_inhalt.py` (`VORHER_REF` = SHA aus
Aufgabe 0 Schritt 2 eintragen; ohne Rebase
`55f34b58fc50de41114676222ce55e8cd1278b2e`):

```python
"""Messung: Begriffsboard-Inhalt vorher/nachher (Karte t_2b9d2cbe).

**Kein Test, laeuft nie automatisch, kostet Geld** (Kimi ueber Infomaniak).
Braucht die Padua-Env (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL):

    set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --trocken
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm vorher --modell kimi
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell kimi --runde 0
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell opus --faelle ansage_en,deutsch_stt,schaerfung_stt_en
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --tabelle

Grenzen, die im Code stehen und nicht im Kommentar:
- Der Fall ``live`` liest das Transkript zur Laufzeit read-only
  (``file:...?mode=ro``) und schreibt es NIE in eine Datei; seine
  Rohantworten werden nicht gespeichert (``roh_pfad`` -> None).
- ``live`` geht nie an Opus (``pruefe_auswahl``): kein US-Modell fuer
  Live-Material.
- ``aufruf``-Zeilen gehen in eine Wegwerf-DB (tempfile), nie in betrieb/.
- ``vorher`` ist der Stand aus ``VORHER_REF`` (Prompt, SCHEMA, validiere,
  _nutzertext per ``git show``) -- reproduzierbar ohne Schalter im
  Produktivcode.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import types
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import anweisungen, begriffsboard, db, einstellungen, llm, repo, sprache, workshop  # noqa: E402
from scripts import begriffsboard_inhalt_zaehler as zaehler  # noqa: E402

VORHER_REF = "55f34b58fc50de41114676222ce55e8cd1278b2e"
LIVE_DB_VORGABE = "/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua.db"
LIVE_CHAT_ID = 7_000_000_000_000
LAEUFE_VORGABE = 3
#: 4 Faelle x 3 Laeufe x 2 Aufrufe = 24, plus Luft fuer Wiederholungen.
MAX_AUFRUFE = 30
#: ~0,015 CHF je Kimi-Aufruf geschaetzt (kosten.PREISE_CHF_JE_MIO_TOKEN) x 24
#: = 0,36 CHF; der Deckel liegt beim Doppelten.
BUDGET_CHF = 0.75
EN_PROMPT = "interview_theater/sprachen/en/prompts/begriffsboard.md"
MESS_VERZ = WURZEL / "docs" / "begriffsboard-inhalt" / "messung"
ROH_VERZ = WURZEL / "docs" / "begriffsboard-inhalt" / "roh"
ART = "messung_begriffsboard_inhalt"

#: Soll-Liste des Live-Falls (nur Begriffe, kein Transkript). Vor dem ersten
#: Vorher-Lauf gegen das Transkript geprueft und danach NICHT mehr geaendert.
LIVE = zaehler.Fall(
    name="live",
    beschreibung="Live-Diskussion Padua Gruppe 1 (DE gesprochen, EN-Profil), read-only",
    sprache_gesprochen="de",
    segmente=(),
    soll=(
        ("Cappuccino",),
        ("Alice Hotel",),
        ("Rolle",),
        ("Strasse", "Straße"),
        ("Tuch",),
        ("Biennale",),
        ("KI",),
    ),
    varianten=(),
    meta=("Begriff", "Gepäck", "Gepaeck", "Betreff", "Test", "Mikrofon"),
    mit_grund=(),
)

OPUS_ZUSATZ = ("\n\nReply with a single JSON object that matches this JSON schema, "
               "and nothing else:\n{schema}")


@dataclasses.dataclass(frozen=True)
class Stand:
    name: str
    system: str
    schema: dict
    validiere: object
    nutzertext: object


def _git_show(ref: str, pfad: str) -> str:
    return subprocess.run(["git", "-C", str(WURZEL), "show", f"{ref}:{pfad}"],
                          check=True, capture_output=True, text=True).stdout


def stand_vorher(ref: str = VORHER_REF) -> Stand:
    # Eigenes Modulobjekt unter dem echten Namen: sprache.Texte(__name__)
    # findet so dieselben Texte. NICHT in sys.modules eingetragen.
    mod = types.ModuleType("interview_theater.begriffsboard")
    quelle = _git_show(ref, "interview_theater/begriffsboard.py")
    exec(compile(quelle, f"begriffsboard@{ref[:7]}", "exec"), mod.__dict__)
    return Stand("vorher", anweisungen.fuelle(_git_show(ref, EN_PROMPT)), mod.SCHEMA,
                 mod.validiere, mod._nutzertext)


def stand_nachher() -> Stand:
    return Stand("nachher", anweisungen.hole("begriffsboard"), begriffsboard.SCHEMA,
                 begriffsboard.validiere, begriffsboard._nutzertext)


def pruefe_auswahl(faelle: list[str], modell: str) -> None:
    if modell == "opus" and "live" in faelle:
        raise SystemExit("Der Fall 'live' geht nie an Opus (US-Modell) -- nur Kimi.")
    unbekannt = set(faelle) - set(zaehler.ERFUNDEN) - {"live"}
    if unbekannt:
        raise SystemExit(f"Unbekannte Faelle: {sorted(unbekannt)}")


def lies_live_segmente(pfad: str, chat_id: int) -> list[str]:
    conn = sqlite3.connect(f"file:{Path(pfad).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [s for s in repo.diskussion_transkript(conn, chat_id).split("\n\n") if s.strip()]
    finally:
        conn.close()


def roh_pfad(fall_name: str, arm: str, modell: str, runde: int, lauf: int) -> Path | None:
    if fall_name == "live":
        return None
    return ROH_VERZ / f"{fall_name}-{arm}-{modell}-r{runde}-l{lauf}.json"


def _validiere(stand: Stand, roh: list, transkript: str, bisher: list) -> list:
    if "bisher" in inspect.signature(stand.validiere).parameters:  # nach t_cb2c4678
        return stand.validiere(roh, transkript, bisher=bisher)
    return stand.validiere(roh, transkript)


def ein_lauf(rufe, stand: Stand, fall: zaehler.Fall, profil: str):
    """Zwei Aufrufe wie im fortlaufenden Betrieb: erst die erste Haelfte der
    Segmente mit leerem Board, dann alles mit dem validierten Board."""
    haelfte = math.ceil(len(fall.segmente) / 2)
    erst = "\n\n".join(fall.segmente[:haelfte])
    ganz = "\n\n".join(fall.segmente)
    bisher = _validiere(stand, rufe(stand, stand.nutzertext(erst, [])), erst, [])
    roh = rufe(stand, stand.nutzertext(ganz, bisher))
    validiert = _validiere(stand, roh, ganz, bisher)
    roh_board = begriffsboard.lies(json.dumps(roh, ensure_ascii=False))
    zahlen = {"roh": zaehler.zaehle(roh_board, ganz, fall, profil),
              "validiert": zaehler.zaehle(validiert, ganz, fall, profil)}
    return zahlen, roh, validiert


def _board_aus(ergebnis) -> list:
    board = ergebnis.get("board") if isinstance(ergebnis, dict) else None
    return board if isinstance(board, list) else []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=("vorher", "nachher"), default="nachher")
    p.add_argument("--modell", choices=("kimi", "opus"), default="kimi")
    p.add_argument("--faelle", default=",".join(("live",) + zaehler.ERFUNDEN))
    p.add_argument("--laeufe", type=int, default=LAEUFE_VORGABE)
    p.add_argument("--runde", type=int, default=0)
    p.add_argument("--live-db", default=LIVE_DB_VORGABE)
    p.add_argument("--trocken", action="store_true")
    p.add_argument("--tabelle", action="store_true")
    a = p.parse_args(argv)

    if a.tabelle:
        messungen = [json.loads(f.read_text()) for f in sorted(MESS_VERZ.glob("*.json"))]
        print(zaehler.tabelle(messungen))
        return 0

    faelle_namen = [f for f in a.faelle.split(",") if f]
    pruefe_auswahl(faelle_namen, a.modell)
    os.environ["IT_WORKSHOP"] = "padua-2026"
    workshop.vergiss()
    sprache.vergiss()
    profil = sprache.code()

    faelle: list[zaehler.Fall] = []
    for name in faelle_namen:
        if name == "live":
            faelle.append(dataclasses.replace(
                LIVE, segmente=tuple(lies_live_segmente(a.live_db, LIVE_CHAT_ID))))
        else:
            faelle.append(zaehler.lade_fall(zaehler.FAELLE_VERZ / f"{name}.toml"))

    stand = stand_vorher() if a.arm == "vorher" else stand_nachher()
    if a.arm == "nachher":
        datei = anweisungen.fuelle((WURZEL / EN_PROMPT).read_text(encoding="utf-8")).strip()
        if datei != stand.system.strip():
            raise SystemExit("anweisungen.hole('begriffsboard') liefert unter padua-2026 nicht "
                             f"{EN_PROMPT} -- Profil pruefen, Messung abgebrochen.")

    aufrufe_geplant = len(faelle) * a.laeufe * 2
    print(f"Profil {profil}, Arm {a.arm}, Modell {a.modell}, Runde {a.runde}, "
          f"VORHER_REF {VORHER_REF[:12]}, Aufrufe geplant {aufrufe_geplant}")
    for f in faelle:
        print(f"  Fall {f.name}: {len(f.segmente)} Segmente, "
              f"{len(''.join(f.segmente))} Zeichen, {len(f.soll)} Soll-Gruppen")
    if a.trocken:
        for v in ("IT_LLM_URL", "IT_LLM_KEY", "IT_LLM_MODELL"):
            print(f"  {v}: {'ja' if os.environ.get(v) else 'nein'}")
        return 0
    if a.modell == "kimi" and aufrufe_geplant > MAX_AUFRUFE:
        raise SystemExit(f"{aufrufe_geplant} Aufrufe > MAX_AUFRUFE={MAX_AUFRUFE}")

    import httpx

    tmp = tempfile.mkdtemp(prefix="begriffsboard-messung-")
    tmp_db = str(Path(tmp) / "wegwerf.db")
    os.environ["IT_DB"] = tmp_db
    einst = dataclasses.replace(einstellungen.laden(), db_pfad=tmp_db)
    if a.modell == "kimi" and "kimi" not in (einst.llm_modell or "").casefold():
        raise SystemExit(f"IT_LLM_MODELL={einst.llm_modell} ist nicht Kimi -- Padua-Env laden.")
    conn = db.verbinde(tmp_db)
    db.initialisiere(conn)
    zaehl = {"aufrufe": 0}

    def kosten() -> float:
        return float(conn.execute("SELECT COALESCE(SUM(kosten_chf), 0) FROM aufruf").fetchone()[0])

    with httpx.Client(timeout=180.0) as klient:
        klm = llm.LLM(einst, klient, conn)
        claude = None
        if a.modell == "opus":
            from simulation.claude import Claude
            claude = Claude(klient)

        def rufe(st: Stand, nutzer: str) -> list:
            if a.modell == "kimi" and (zaehl["aufrufe"] >= MAX_AUFRUFE or kosten() >= BUDGET_CHF):
                raise SystemExit(f"Budget erreicht: {zaehl['aufrufe']} Aufrufe, {kosten():.3f} CHF")
            zaehl["aufrufe"] += 1
            if a.modell == "kimi":
                return _board_aus(klm.schema(None, st.system, nutzer, st.schema, ART))
            return _board_aus(claude.json_objekt(
                st.system, nutzer + OPUS_ZUSATZ.format(schema=json.dumps(st.schema)), art=ART))

        ergebnis = {"arm": a.arm, "modell": a.modell if a.modell == "opus" else einst.llm_modell,
                    "runde": a.runde, "vorher_ref": VORHER_REF,
                    "datum": datetime.now().isoformat(timespec="seconds"), "faelle": {}}
        for fall in faelle:
            roh_z, val_z, fehler = [], [], 0
            for lauf in range(1, a.laeufe + 1):
                try:
                    zahlen, roh, validiert = ein_lauf(rufe, stand, fall, profil)
                except SystemExit:
                    raise
                except Exception as fehler_obj:  # ein gescheiterter Lauf reisst die Messung nicht mit
                    print(f"  {fall.name} Lauf {lauf}: FEHLER {type(fehler_obj).__name__}")
                    fehler += 1
                    continue
                roh_z.append(zahlen["roh"])
                val_z.append(zahlen["validiert"])
                pfad = roh_pfad(fall.name, a.arm, a.modell, a.runde, lauf)
                if pfad is not None:
                    pfad.parent.mkdir(parents=True, exist_ok=True)
                    pfad.write_text(json.dumps({"roh": roh, "validiert": validiert},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  {fall.name} Lauf {lauf}: roh {zahlen['roh']} | validiert {zahlen['validiert']}")
            ergebnis["faelle"][fall.name] = {"laeufe": len(roh_z), "fehler": fehler,
                                             "roh": zaehler.summe(roh_z),
                                             "validiert": zaehler.summe(val_z)}
        ergebnis["aufrufe"] = zaehl["aufrufe"]
        ergebnis["kosten_chf"] = round(kosten(), 4)

    MESS_VERZ.mkdir(parents=True, exist_ok=True)
    ziel = MESS_VERZ / (f"{datetime.now():%Y-%m-%d}-{a.arm}-{a.modell}-r{a.runde}.json")
    ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Geschrieben: {ziel.relative_to(WURZEL)} ({ergebnis['aufrufe']} Aufrufe, "
          f"{ergebnis['kosten_chf']} CHF)")
    print(zaehler.tabelle([ergebnis]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Zwei Hinweise für den Coder:
- `einstellungen.Einstellungen` ist `frozen=True` -- deshalb
  `dataclasses.replace`.
- Der Opus-Arm bekommt den `klient` mit `timeout=180.0`; `Claude` nimmt
  einen fremden Klienten und schließt ihn nicht.

- [ ] **Schritt 5: Live-Soll-Liste prüfen** (vor jedem bezahlten Lauf; die
  Liste oben ist eine ANNAHME aus dem Board-Auszug des Architekten)

Das Transkript **nur auf stdout** lesen, nie in eine Datei:

```bash
python3.11 -c "from scripts.rauchtest_begriffsboard_inhalt import *; print('\n---\n'.join(lies_live_segmente(LIVE_DB_VORGABE, LIVE_CHAT_ID)))"
```

Regel für die Soll-Liste (in den Kommentar über `LIVE` übernehmen):
- **Soll** ist jeder Begriff, den die Gruppe ausdrücklich als Begriff
  vorschlägt (Ansage-Formel oder klare Diskussion darüber) -- in der
  Schreibweise, die im Transkript steht (`begriffsboard.validiere` verlangt
  das ohnehin). Schreibvarianten derselben Sache als Alternativen derselben
  Gruppe.
- **Variante** ist ein Wort, das ein STT-Verhörer eines Soll-Begriffs ist
  oder eine Vorstufe, die die Gruppe selbst geschärft hat.
- Nicht Soll: Füllwörter, Mikrofon-/Testgerede, Ansagewörter.
- Jeder Eintrag muss im Transkript stehen (`schluessel(...) in
  schluessel(transkript)`).

Die Liste in `LIVE` entsprechend korrigieren. **Keine Zeile des
Transkripts, kein Zitat in den Kommentar oder die Commit-Nachricht.**
Läuft Schritt 5 wegen fehlender Rechte nicht (Live-DB nicht lesbar): Liste
so lassen, im Bericht als „Soll-Liste ungeprüft (ANNAHME)“ führen, und
`live` aus allen bezahlten Läufen weglassen (`--faelle ansage_en,deutsch_stt,schaerfung_stt_en`).

- [ ] **Schritt 6: Grün sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_rauchtest_begriffsboard_inhalt.py tests/test_begriffsboard_inhalt_zaehler.py`
Expected: alle `passed`.

`test_ein_lauf_mit_attrappe_zaehlt_beide_stufen` braucht `anweisungen.hole`
unter `padua-2026` -- dafür die Fixture `padua` (leert den Profil-Cache vor
und nach dem Test). Achtung: `skript.main()` setzt `IT_WORKSHOP` selbst und
wird deshalb in keinem Test aufgerufen.

- [ ] **Schritt 7: Prüfen, dass nichts Live-artiges im Diff steht**

```bash
git diff --cached --stat; git status --short
```

Expected: nur `.gitignore`, `scripts/rauchtest_begriffsboard_inhalt.py`,
`tests/test_rauchtest_begriffsboard_inhalt.py`. Kein `docs/begriffsboard-inhalt/roh/`.

- [ ] **Schritt 8: Commit** (Soll-Listen sind damit **vor** der ersten Messung festgelegt)

```bash
git add .gitignore scripts/rauchtest_begriffsboard_inhalt.py tests/test_rauchtest_begriffsboard_inhalt.py
git commit -m "$(cat <<'EOF'
Begriffsboard-Messung: Messskript vorher/nachher, Live-Soll-Liste, ro-Live-Lesen, Opus-Sperre fuer live (t_2b9d2cbe, Aufgabe 3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Schritt 9: Trockenlauf mit Env** (kostet nichts)

```bash
bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; python3.11 -m scripts.rauchtest_begriffsboard_inhalt --trocken'
```

Expected (ungefähr):

```
Profil en, Arm nachher, Modell kimi, Runde 0, VORHER_REF 55f34b58fc50, Aufrufe geplant 24
  Fall live: 16 Segmente, 13xx Zeichen, 7 Soll-Gruppen
  Fall ansage_en: 4 Segmente, ... Zeichen, 4 Soll-Gruppen
  Fall deutsch_stt: 5 Segmente, ...
  Fall schaerfung_stt_en: 4 Segmente, ...
  IT_LLM_URL: ja
  IT_LLM_KEY: ja
  IT_LLM_MODELL: ja
```

Steht dort `nein` oder bricht die Env-Datei mit „Permission denied“ ab:
D7 -- Aufgaben 4 und 7 als „ausstehend“ führen (siehe dort), Aufgaben 5, 6,
8, 9 trotzdem ausführen.

---

### Task 4: Vorher-Messung (Kimi, bezahlt)

**Files:**
- Create: `docs/begriffsboard-inhalt/messung/<datum>-vorher-kimi-r0.json` (vom Skript)

Läuft **bevor** Aufgabe 5 und 6 irgendetwas am Verhalten ändern. Der
`vorher`-Arm liest ohnehin aus `VORHER_REF`; die Reihenfolge ist trotzdem
bindend, damit „vorher“ auch dann ehrlich ist, wenn `stand_vorher` einen
Fehler hätte.

- [ ] **Schritt 1: Messen**

```bash
bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm vorher --modell kimi'
```

Expected: je Fall drei Zeilen `Lauf n: roh {...} | validiert {...}`, dann
`Geschrieben: docs/begriffsboard-inhalt/messung/2026-10-..-vorher-kimi-r0.json (24 Aufrufe, 0.xx CHF)`
und die Tabelle. Erwartet ist, dass im Vorher-Stand mehrere Zähler **nicht**
0 sind (sonst zeigt der Fall die Fehlerbilder nicht -- im Bericht benennen,
die Fälle trotzdem **nicht** nachträglich ändern).

Fällt ein Lauf mit `FEHLER` aus, steht `fehler` > 0 in der Zeile -- nicht
wiederholen, um die Zahl zu schönen; im Bericht so stehen lassen.

- [ ] **Schritt 2: Prüfen, dass nur Zahlen committet werden**

```bash
python3.11 -c "import json,glob; d=json.load(open(sorted(glob.glob('docs/begriffsboard-inhalt/messung/*vorher-kimi*.json'))[-1])); print(sorted(d['faelle']['live'])); print(sorted(d))"
git status --short
```

Expected: `['fehler', 'laeufe', 'roh', 'validiert']` und die Schlüssel
`arm, aufrufe, datum, faelle, kosten_chf, modell, runde, vorher_ref`;
`git status` zeigt nur die neue JSON-Datei (das `roh/`-Verzeichnis ist
gitignoriert).

- [ ] **Schritt 3: Commit**

```bash
git add docs/begriffsboard-inhalt/messung
git commit -m "$(cat <<'EOF'
Begriffsboard-Messung: vorher, Kimi, 4 Faelle x 3 Laeufe (nur Zahlen) (t_2b9d2cbe, Aufgabe 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

**Wenn D7 greift (keine Zugangsdaten):** keine JSON-Datei, kein Commit. In
Aufgabe 8 steht „Vorher-Messung ausstehend“ mit genau dem Kommando aus
Schritt 1. Aufgabe 5 und 6 werden trotzdem gebaut, im Bericht aber **nicht**
als „gemessen“ ausgegeben.

---

### Task 5: Belegpflicht und Meta-Verwurf in `validiere` einhängen

**Files:**
- Modify: `interview_theater/begriffsboard.py` -- Modul-Docstring (Absatz
  „Validiert wird im Code“), neue Funktion `_belege` direkt nach
  `ist_metabegriff`, **zwei** Zeilen in `validiere`
- Modify: `tests/test_begriffsboard_beleg.py` (neue Tests unten anhängen)
- Modify: `tests/test_begriffsboard.py` -- **ein** Test absichtlich geändert

**Interfaces:**
- Consumes: `traegt_beleg`, `ist_fuellsatz`, `ist_metabegriff` (Aufgabe 1)
- Produces: `_belege(eintrag: dict, transkript: str) -> None` (setzt
  `eintrag["begruendung"] = ""`, wenn sie Füllsatz oder unbelegt ist);
  `validiere` verwirft Metabegriffe und ruft `_belege` nach der Zitatprüfung.

- [ ] **Schritt 1: Die roten Tests anhängen** (an `tests/test_begriffsboard_beleg.py`)

```python
# -- Einhaengung in validiere (Aufgabe 5) -------------------------------------

def _z(**kw):
    basis = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1,
             "begruendung": "The grandmother cooks there every Sunday.",
             "zitat": "weil meine Oma jeden Sonntag für zwanzig Leute kocht",
             "doppelbedeutung": "", "status": "kandidat"}
    basis.update(kw)
    return basis


def _pruefe_begruendung_ohne_zitat_wird_leer():
    ergebnis = bb.validiere([_z(zitat="")], TRANSKRIPT)
    assert [e["begriff"] for e in ergebnis] == ["Heimat"]   # Eintrag bleibt
    assert ergebnis[0]["begruendung"] == ""


def test_begruendung_ohne_zitat_wird_leer():
    _pruefe_begruendung_ohne_zitat_wird_leer()


def test_mutant_ohne_belegpruefung_faellt_durch(monkeypatch):
    """Wer ``_belege`` aus ``validiere`` nimmt, muss den Test oben rot machen."""
    monkeypatch.setattr(bb, "_belege", lambda eintrag, transkript: None)
    with pytest.raises(AssertionError):
        _pruefe_begruendung_ohne_zitat_wird_leer()


def test_belegte_begruendung_bleibt():
    ergebnis = bb.validiere([_z()], TRANSKRIPT)
    assert ergebnis[0]["begruendung"] == "The grandmother cooks there every Sunday."


def test_ansage_als_zitat_leert_die_begruendung():
    ergebnis = bb.validiere([_z(zitat="also der erste Gepäck ist Heimat")], TRANSKRIPT)
    assert ergebnis[0]["zitat"] == "also der erste Gepäck ist Heimat"  # Zitat ist woertlich, bleibt
    assert ergebnis[0]["begruendung"] == ""


def test_fuellsatz_mit_gutem_zitat_wird_leer():
    ergebnis = bb.validiere([_z(begruendung="Wird als Begriff gesammelt.")], TRANSKRIPT)
    assert ergebnis[0]["begruendung"] == ""


def test_leere_begruendung_ist_gueltig():
    ergebnis = bb.validiere([_z(begruendung="", zitat="")], TRANSKRIPT)
    assert ergebnis[0]["begruendung"] == "" and ergebnis[0]["begriff"] == "Heimat"


def _pruefe_metabegriff_faellt_weg():
    roh = [_z(), _z(begriff="Test"), _z(begriff="Gepäck"), _z(begriff="test eins zwei drei")]
    assert [e["begriff"] for e in bb.validiere(roh, TRANSKRIPT)] == ["Heimat"]


def test_metabegriff_faellt_weg():
    _pruefe_metabegriff_faellt_weg()


def test_mutant_ohne_metapruefung_faellt_durch(monkeypatch):
    monkeypatch.setattr(bb, "ist_metabegriff", lambda begriff: False)
    with pytest.raises(AssertionError):
        _pruefe_metabegriff_faellt_weg()


def test_detail_zeilen_lassen_geleerte_begruendung_weg():
    board = bb.validiere([_z(begruendung="Wird als Begriff gesammelt.")], TRANSKRIPT)
    assert bb.detail_zeilen(bb.detail_fuer(board, "Heimat")) == []
```

- [ ] **Schritt 2: Rot sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py`
Expected: FAIL in `test_begruendung_ohne_zitat_wird_leer`, `test_ansage_als_zitat_leert_die_begruendung`,
`test_fuellsatz_mit_gutem_zitat_wird_leer`, `test_metabegriff_faellt_weg`,
`test_detail_zeilen_lassen_geleerte_begruendung_weg`; die beiden Mutanten-Tests
schlagen fehl (bzw. `AttributeError: … has no attribute '_belege'`).

- [ ] **Schritt 3: Implementieren**

(a) Direkt nach `ist_metabegriff` einfügen:

```python
def _belege(eintrag: dict, transkript: str) -> None:
    """D1: eine Begruendung, die ein Fuellsatz ist oder kein tragendes Zitat
    hat, wird leer. Leere Begruendung ist ein gueltiger Zustand --
    ``detail_zeilen`` laesst solche Eintraege ohnehin weg. Der Eintrag
    selbst bleibt."""
    if eintrag["begruendung"] and (ist_fuellsatz(eintrag["begruendung"])
                                   or not traegt_beleg(eintrag, transkript)):
        eintrag["begruendung"] = ""
```

(b) In `validiere` genau zwei Zeilen -- **nach** der bestehenden Zeile
`if eintrag is None or not _steht_im_transkript(...): continue`:

```python
        if ist_metabegriff(eintrag["begriff"]):
            continue
```

und **direkt nach** dem Block
`if eintrag["zitat"] and not zitat.pruefe(...): eintrag["zitat"] = ""`:

```python
        _belege(eintrag, transkript)
```

(Auf dem t_cb2c4678-Stand stehen danach `eintrag.pop("vorgaenger", None)` und
`links.append(...)` -- `_belege` gehört **vor** sie, unmittelbar hinter die
Zitatprüfung.)

(c) Im Modul-Docstring den Satz

```
der nicht im Transkript steht, fliegt raus; ein Zitat, das ``zitat.pruefe``
nicht besteht, wird leer, die Begruendung bleibt.
```

ersetzen durch

```
der nicht im Transkript steht oder nur ein Ansage-/Mikrofonwort ist
(``ist_metabegriff``), fliegt raus; ein Zitat, das ``zitat.pruefe`` nicht
besteht, wird leer. **Belegpflicht (Karte t_2b9d2cbe):** eine Begruendung
bleibt nur, wenn ein geprueftes Zitat sie traegt, das mehr enthaelt als
Begriff und Ansage (``traegt_beleg``), und wenn sie kein Fuellsatz ist
("wird genannt/gesammelt", ``ist_fuellsatz``); sonst wird sie leer.
```

- [ ] **Schritt 4: Grün sehen**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py`
Expected: alle `passed`.

- [ ] **Schritt 5: Den einen bestehenden Test absichtlich ändern**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard.py`
Expected: genau **ein** Fehlschlag, `test_unbelegtes_zitat_wird_leer_begruendung_bleibt`
(`assert '' == 'Kam zweimal vor.'`).

Begründung für die Änderung: der Test hält genau das Verhalten fest, das D1
abschafft -- eine Begründung ohne geprüftes Zitat ist unbelegt (und „Kam
zweimal vor.“ ist zudem ein Füllsatz). Ersetzen in `tests/test_begriffsboard.py`:

```python
def test_unbelegtes_zitat_leert_zitat_und_begruendung():
    """Karte t_2b9d2cbe, D1: ohne geprueftes Zitat ist die Begruendung
    unbelegt -- vorher blieb sie stehen (Test hiess
    test_unbelegtes_zitat_wird_leer_begruendung_bleibt)."""
    ergebnis = begriffsboard.validiere(
        [_zeile(zitat="Heimat ist alles fuer uns")], TRANSKRIPT,
    )
    assert ergebnis[0]["zitat"] == ""
    assert ergebnis[0]["begruendung"] == ""
```

Alle anderen Tests in dieser Datei schicken `_zeile()` zwar durch
`validiere`, prüfen aber nicht die Begründung (Zustimmung, Nennungen, Status,
Dubletten, Deckel, Listentrenner) bzw. gehen nicht durch `validiere`
(`test_detail_fuer_…` arbeitet direkt auf `_zeile`) -- sie bleiben
unverändert. Ändert sich trotzdem ein weiterer, ist das ein Befund: stoppen
und nachsehen, nicht anpassen.

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard.py`
Expected: alle `passed`.

- [ ] **Schritt 6: Die übrigen Board-Tests**

Run:

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_lauf.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_web.py tests/test_begriffsboard_einstieg.py tests/test_begriffe_detail_wege.py tests/test_flow_audit_dynamisch.py tests/test_repo_begriffsboard.py tests/test_aufnahme_diskussion.py
```

Expected: alle `passed`. Vom Plan-Autor geprüft: `test_begriffsboard_lauf`
und `_mithoeren` schicken `HEIMAT` (`begruendung "Oma."`, Zitat „wo meine Oma
kocht“ steht im Transkript, Inhaltswörter `oma`, `kocht` = 2) -- die
Begründung bleibt. `_vorschlag`, `_web`, `test_begriffe_detail_wege` und
`simulation/flow_audit_dynamisch.py` legen Boards über
`repo.lege_begriffsboard_an` direkt an, nicht über `validiere`. Wird einer
davon trotzdem rot: Ursache je Test benennen, Test nur ändern, wenn er ein
durch D1 abgeschafftes Verhalten festhält, und die Begründung in den
Commit schreiben.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/begriffsboard.py tests/test_begriffsboard_beleg.py tests/test_begriffsboard.py
git commit -m "$(cat <<'EOF'
Begriffsboard: Belegpflicht der Begruendung und Meta-Verwurf in validiere (t_2b9d2cbe, Aufgabe 5)

Eine Begruendung bleibt nur mit gepruefetem Zitat, das mehr traegt als
Begriff und Ansage, und nur, wenn sie kein Fuellsatz ist. Begriffe wie
"Test", "Gepaeck", "Begriff" fallen weg. Absichtlich geaendert:
test_unbelegtes_zitat_wird_leer_begruendung_bleibt -> ..._leert_zitat_und_begruendung
(hielt das abgeschaffte Verhalten fest).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Prompt DE + EN

**Files:**
- Modify: `interview_theater/prompts/begriffsboard.md`
- Modify: `interview_theater/sprachen/en/prompts/begriffsboard.md`
- Test: `tests/test_begriffsboard_beleg.py` (Prompt-Inhaltstest anhängen)

Alle `old`-Blöcke unten sind wörtlich aus dem Stand `55f34b5`. Auf dem
t_cb2c4678-Stand (nach Rebase) stehen sie unverändert (t_cb2c4678 fügt nur
Zeilen dazwischen ein: `vorheriger_begriff`-Feld, -Absatz, -Verbot) -- diese
eingefügten Zeilen bleiben stehen.

- [ ] **Schritt 1: Den roten Test anhängen**

```python
# -- Prompt (Aufgabe 6) -------------------------------------------------------

from pathlib import Path

_PROMPTS = Path(bb.__file__).parent
_DE = _PROMPTS / "prompts" / "begriffsboard.md"
_EN = _PROMPTS / "sprachen" / "en" / "prompts" / "begriffsboard.md"


@pytest.mark.parametrize("pfad, verboten", [
    (_DE, ("ergaenze die\n``begruendung`` um die Entwicklung", "vermerke\ndie Korrektur kurz in ``begruendung``")),
    (_EN, ("extend\n``begruendung`` with the development", "note the correction\nbriefly in ``begruendung``")),
])
def test_prompt_verlangt_keine_merge_spur_in_der_begruendung(pfad, verboten):
    text = pfad.read_text(encoding="utf-8")
    for satz in verboten:
        assert satz not in text


def test_en_prompt_verlangt_englische_begruendung_und_kennt_ansagen():
    text = _EN.read_text(encoding="utf-8")
    assert "written in English" in text
    assert "the first term is" in text
    assert "test, one two three" in text


def test_de_prompt_kennt_ansagen_und_stt():
    text = _DE.read_text(encoding="utf-8")
    assert "der erste Begriff ist" in text
    assert "Gepaeck" in text and "Betreff" in text
```

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py -k prompt`
Expected: FAIL (alle drei).

- [ ] **Schritt 2: DE-Prompt ändern** (`interview_theater/prompts/begriffsboard.md`)

(a) Feld `begruendung` und `zitat` -- ersetze

```
- begruendung: ein oder zwei Saetze, warum die Gruppe diesen Begriff will --
  in ihrer eigenen Argumentation.
- zitat: eine kurze Stelle, buchstabengetreu aus dem Transkript kopiert,
  oder "" wenn es keine gibt.
```

durch

```
- begruendung: ein oder zwei Saetze, warum die Gruppe diesen Begriff will --
  nur, wenn die Gruppe selbst einen Grund nennt, und in ihrer eigenen
  Argumentation. Nennt sie keinen, ist begruendung "" -- das ist richtig,
  keine Luecke. Dass ein Begriff genannt, gesammelt, aufgefuehrt oder
  vorgeschlagen wurde, ist KEIN Grund.
- zitat: die kurze Stelle, buchstabengetreu aus dem Transkript kopiert, die
  den Grund traegt -- nicht die Ansage des Begriffs. Ohne Grund "".
```

(b) Merge-Absatz -- ersetze

```
Wortlaut als ``begriff``, addiere die Nennungen, und ergaenze die
``begruendung`` um die Entwicklung in einem Halbsatz, zum Beispiel "Zuerst
als 'Roboter' genannt, spaeter praezisiert auf 'KI-Roboter'." Die
Entwicklung bleibt damit in der Begruendung lesbar, erscheint aber nicht als
eigene Zeile. Zwei Begriffe, die inhaltlich eigenstaendig sind (z. B.
```

durch

```
Wortlaut als ``begriff`` und addiere die Nennungen. Die Entwicklung schreibst
du NICHT in die ``begruendung`` -- die sagt nur, warum die Gruppe den
Begriff will. Die alte Fassung erscheint auch nicht als eigene Zeile, auch
nicht mit status "verworfen". Zwei Begriffe, die inhaltlich eigenstaendig sind (z. B.
```

(c) STT-Schluss -- ersetze

```
Verrechne beide Nennungszahlen in den verbliebenen Eintrag und vermerke
die Korrektur kurz in ``begruendung``, zum Beispiel "Einmal als 'Saite'
verstanden (STT-Verhoerer), gemeint war 'Seite', dreimal richtig
gehoert."
```

durch

```
Verrechne beide Nennungszahlen in den verbliebenen Eintrag. Die Korrektur
vermerkst du nirgends -- nicht in ``begruendung``, nicht als eigene Zeile,
auch nicht mit status "verworfen". "verworfen" heisst nur: die Gruppe laesst
einen Begriff inhaltlich fallen.

Ansagen, Testgerede, Verhoerer der Ansage:

- Ansage-Formeln ("der erste Begriff ist X", "ein Begriff ist X", "noch ein
  Begriff waere X", "ich schlage X vor", "mein Wort ist X") liefern NUR den
  Begriff X. Aus ihnen entsteht keine begruendung und kein zitat.
- Mikrofon- und Testgerede ("Test, eins zwei drei", "hoert man uns?", "laeuft
  die Aufnahme?") ignorierst du ganz: kein Begriff, keine Nennung.
- "Begriff", "Wort", "Test", "Mikrofon" selbst sind nie ein Begriff.
- Ein Wort, das an der Stelle einer Ansage keinen Sinn ergibt ("der erste
  Gepaeck ist X", "der zweite Betreff ist X"), ist ein Verhoerer fuer
  "Begriff". Lies es so und uebernimm es nie in begriff oder begruendung.
- begruendung und doppelbedeutung schreibst du auf Deutsch, auch wenn das
  Transkript in einer anderen Sprache ist; begriff bleibt im Wortlaut des
  Transkripts.
```

(d) In der Liste „Nicht so:“ nach `- Keine Begruendung, die die Gruppe nicht gegeben hat.` einfügen:

```
- Keine Begruendung, die nur sagt, dass der Begriff genannt, gesammelt oder
  vorgeschlagen wurde.
- Keine Zeile fuer eine zusammengefuehrte oder verhoerte Fassung.
```

(Hinweis: Der DE-Prompt schreibt Umlaute als `ae`/`oe` wie die übrige Datei --
deshalb „Gepaeck“ im Prompt und im Test.)

- [ ] **Schritt 3: EN-Prompt ändern** (`interview_theater/sprachen/en/prompts/begriffsboard.md`)

(a) ersetze

```
- begruendung: one or two sentences on why the group wants this term -- in
  the group's own line of argument.
- zitat: a short passage copied letter for letter from the transcript, or
  "" if there is none.
```

durch

```
- begruendung: one or two sentences on why the group wants this term --
  only when the group itself gives a reason, and in the group's own line of
  argument. If it gives none, begruendung is "" -- that is correct, not a
  gap. That a term was named, collected, listed or suggested is NOT a
  reason.
- zitat: the short passage, copied letter for letter from the transcript,
  that carries the reason -- not the announcement of the term. "" when
  there is no reason.
```

(b) ersetze

```
wording as ``begriff``, add the mention counts together, and extend
``begruendung`` with the development in one clause, for example "First
named 'robot', later sharpened to 'AI robot'." That keeps the development
readable in the reasoning without it showing up as its own line. Two terms
```

durch

```
wording as ``begriff`` and add the mention counts together. Do NOT write the
development into ``begruendung`` -- it only says why the group wants the
term. The old wording does not show up as its own line either, not even
with status "verworfen". Two terms
```

(c) ersetze

```
Add both mention counts into the remaining entry and note the correction
briefly in ``begruendung``, for example "Misheard once as 'whether' (STT
slip), meant 'weather', heard correctly three times."
```

durch

```
Add both mention counts into the remaining entry. Do not note the
correction anywhere -- not in ``begruendung``, not as its own line, not
with status "verworfen". "verworfen" only means: the group drops a term on
its merits.

Announcements, test talk, misheard announcements:

- Announcement formulas ("the first term is X", "a term is X", "another
  term would be X", "I'd suggest X", "my word is X") give ONLY the term X.
  They never yield a begruendung or a zitat.
- Ignore microphone and test talk entirely ("test, one two three", "can you
  hear us?", "is this recording?"): no term, no mention.
- The words "term", "word", "test", "microphone" themselves are never a
  term.
- A word that makes no sense in the slot of an announcement ("the first
  germ is X", "my turn is X") is a mishearing of "term". Read it that way
  and never copy it into begriff or begruendung. The same holds when the
  group speaks another language: an odd word in the place of that
  language's word for "term" is a mishearing of it.
- begruendung and doppelbedeutung are always written in English, even when
  the transcript is in another language; begriff stays worded exactly as in
  the transcript.
```

(d) in „Not like this:“ nach `- No reason the group did not give.` einfügen:

```
- No begruendung that only says the term was named, collected or suggested.
- No line for a merged or misheard wording.
```

- [ ] **Schritt 4: Grün sehen und Sprachprüfung**

Run: `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py`
Expected: alle `passed`.

Run: `python3.11 -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/begriffsboard.md`
Expected: `0 Treffer` (Grundlinie des Plan-Autors am 04.10.2026: `0 Treffer`). Gibt es Treffer, das
deutsche Wort im EN-Prompt umformulieren -- **keine** Ausnahme in
`scripts/pruefe_sprache.py` eintragen.

Run: `python3.11 -m scripts.pruefe_profil padua-2026`
Expected: letzte Zeile `padua-2026: in Ordnung`.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/prompts/begriffsboard.md interview_theater/sprachen/en/prompts/begriffsboard.md tests/test_begriffsboard_beleg.py
git commit -m "$(cat <<'EOF'
Begriffsboard-Prompt DE/EN: Begruendung nur mit eigenem Grund, Ansagen/Testgerede/STT der Ansage, keine Merge-Spur, Profilsprache (t_2b9d2cbe, Aufgabe 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Nachher-Messung, Iteration, Opus-Arm

**Files:**
- Create: `docs/begriffsboard-inhalt/messung/<datum>-nachher-kimi-r{0,1,2}.json`, `<datum>-nachher-opus-r0.json`
- Modify (nur bei Iteration): beide `begriffsboard.md`

- [ ] **Schritt 1: Nachher messen (Kimi, Runde 0)**

```bash
bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell kimi --runde 0'
```

Expected: `Geschrieben: …-nachher-kimi-r0.json (24 Aufrufe, …)` und die Tabelle.

- [ ] **Schritt 2: Ist das Ziel erreicht?**

```bash
python3.11 -c "
import json,glob
from scripts.begriffsboard_inhalt_zaehler import ZAEHLER
d=json.load(open(sorted(glob.glob('docs/begriffsboard-inhalt/messung/*nachher-kimi-r0.json'))[-1]))
rest={f:{k:v['validiert'][k] for k in ZAEHLER if v['validiert'][k]} for f,v in d['faelle'].items()}
print(rest or 'ALLE NULL')"
```

Expected (Ziel): `{'live': {}, 'ansage_en': {}, …}` bzw. alle Fälle mit leerem
Dict. Steht dort ein Zähler > 0: Schritt 3, sonst weiter mit Schritt 5.

- [ ] **Schritt 3: Iteration (höchstens zwei Runden, D8)**

Je Runde:
1. In den gitignorierten Rohantworten der erfundenen Fälle
   (`docs/begriffsboard-inhalt/roh/*-nachher-kimi-r<runde>-*.json`)
   nachsehen, welche Einträge den Zähler auslösen. Für `live` gibt es keine
   Rohantworten -- dort nur die Zahl.
2. Den Prompt **DE und EN gleich** an genau dieser Stelle schärfen (ein
   Satz oder ein Beispiel; EN ohne deutsche Wörter, danach
   `python3.11 -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/begriffsboard.md`
   → `0 Treffer`). **Nicht** die Soll-Listen, **nicht** die Fälle, **nicht**
   die Zähler ändern.
3. `python3.11 -m pytest -q -p no:cacheprovider tests/test_begriffsboard_beleg.py` → `passed`.
4. Commit des Prompts:
   ```bash
   git add interview_theater/prompts/begriffsboard.md interview_theater/sprachen/en/prompts/begriffsboard.md
   git commit -m "$(cat <<'EOF'
   Begriffsboard-Prompt: Iteration <n> nach Nachher-Messung (<Zaehler>) (t_2b9d2cbe, Aufgabe 7)

   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   EOF
   )"
   ```
5. Messen mit `--runde <n>` (1 bzw. 2), dann Schritt 2 mit `r<n>`.

Nach Runde 2 wird **nicht** weiter iteriert, egal wie die Zahlen stehen.
Was nicht 0 wurde, steht im Bericht mit Fall und Zähler.

Ein Zähler, der nur über den Code (validiert) zu drücken wäre -- z. B.
`dubletten` durch verworfene Merge-Spuren, `sprache_ungleich_profil` --,
bekommt in dieser Karte **keinen** neuen Code (D3/D4 entschieden: nur
Prompt). Im Bericht als offener Punkt für Birk benennen.

- [ ] **Schritt 4: Commit der Messungen**

```bash
git add docs/begriffsboard-inhalt/messung
git commit -m "$(cat <<'EOF'
Begriffsboard-Messung: nachher, Kimi (nur Zahlen) (t_2b9d2cbe, Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Schritt 5: Opus-Proxy erreichbar?** (Einzelaufruf, Abonnement, 0 CHF)

```bash
python3.11 -c "from simulation.claude import Claude; c=Claude(); print(c.modell, c.text('Reply with OK.', 'OK?', art='probe')[:20]); c.schliesse()"
```

Expected: `claude-opus-5 OK` (oder ähnlich). Bei `ClaudeFehler`: Opus-Spalte
im Bericht „ausstehend“ mit dem Kommando aus Schritt 6.

- [ ] **Schritt 6: Opus-Arm, nur erfundene Fälle, letzter Prompt-Stand**

```bash
python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell opus --faelle ansage_en,deutsch_stt,schaerfung_stt_en
```

(Für den Opus-Arm ist die Padua-Env nicht nötig, `einstellungen.laden()`
braucht aber die Pflichtvariablen -- deshalb ebenfalls mit
`set -a; . …/padua-gruppe1.env; set +a` davor. Das Live-Transkript wird bei
dieser Fallauswahl nicht gelesen.)

Gegenprobe, dass die Sperre hält (kostet nichts, bricht vor jedem Aufruf ab):

```bash
python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell opus --faelle live --trocken; echo "exit $?"
```

Expected: `Der Fall 'live' geht nie an Opus (US-Modell) -- nur Kimi.` und `exit 1`.

- [ ] **Schritt 7: Commit**

```bash
git add docs/begriffsboard-inhalt/messung
git commit -m "$(cat <<'EOF'
Begriffsboard-Messung: Opus ueber Proxy, nur erfundenes Material (Entscheidungsvorlage) (t_2b9d2cbe, Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Bericht

**Files:**
- Create: `docs/begriffsboard-inhalt/BERICHT.md`

- [ ] **Schritt 1: Tabelle erzeugen**

```bash
python3.11 -m scripts.rauchtest_begriffsboard_inhalt --tabelle > /tmp/t_2b9d2cbe-tabelle.md; wc -l /tmp/t_2b9d2cbe-tabelle.md
```

Expected: Kopfzeile + Trennzeile + je Messdatei × Fall × 2 Stufen eine Zeile.

- [ ] **Schritt 2: Board-Beispiel auswählen** (nur erfundenes Material)

Aus `docs/begriffsboard-inhalt/roh/deutsch_stt-nachher-kimi-r<letzte>-l1.json`
das Feld `validiert` nehmen (deutsch gesprochen, EN-Profil -- zeigt
Sprache und STT zugleich).

- [ ] **Schritt 3: `BERICHT.md` schreiben** -- Gliederung (alle Abschnitte füllen,
  keiner bleibt leer; „ausstehend“ ist ein gültiger Inhalt nach D7):

```markdown
# Begriffsboard-Inhalt: Belegpflicht und Prompt -- Messung (Karte t_2b9d2cbe)

Stand <Datum>, Branch padua-workshop/t_90f7ec48-…, VORHER_REF <sha>.

## Was geändert wurde
- Code (`begriffsboard.validiere`): Belegpflicht (N = 2 Inhaltswörter),
  Füllsatz-Muster, Meta-Begriffe -- je ein Satz.
- Prompt DE/EN: Ansagen, Testgerede, STT der Ansage, keine Merge-Spur,
  Profilsprache.

## Wie gemessen wurde
- Fälle (live + 3 erfundene, `simulation/begriffsboard_faelle/`), je 3 Läufe,
  ein Lauf = 2 Aufrufe (Hälfte, dann ganz mit Board).
- Zähler und was „roh“/„validiert“ heißt; dass `fuell_begruendungen`,
  `begruendung_ohne_beleg`, `meta_begriffe` validiert per Konstruktion 0
  sind (gleiche Funktionen) und deshalb die Roh-Spalte die Prompt-Wirkung zeigt.
- Kosten (aus den JSON-Dateien, Summe `kosten_chf`), Aufrufe.

## Messtabelle
<Inhalt von /tmp/t_2b9d2cbe-tabelle.md>

## Ergebnis je Zähler (vorher → nachher, validiert, Summe über 3 Läufe)
Eine kurze Tabelle: Zähler | vorher Kimi | nachher Kimi (letzte Runde) | Opus.
Dazu `begruendungen_belegt` vorher/nachher: wie viele echte Gründe übrig blieben.

## Was nicht 0 wurde
Fall, Zähler, Zahl, vermutete Ursache (aus den Rohantworten der erfundenen
Fälle), und ob Code oder Prompt der Ort wäre -- als offener Punkt für Birk.

## Live-Fall
NUR Zahlen. Kein Board, kein Begriff außer der Soll-Liste, kein Zitat.
Ob die Soll-Liste gegen das Transkript geprüft wurde (Aufgabe 3 Schritt 5).

## Board-Beispiel nachher (erfundener Fall `deutsch_stt`)
Das validierte Board als JSON-Block.

## Opus (Entscheidungsvorlage, nicht geschaltet)
Zahlen gegen Kimi nachher; Hinweis, dass der Opus-Arm über
`simulation/claude.py` ohne erzwungenes Schema lief und nicht über den
Produktionspfad `szene_claude.schema`. Kein Live-Material an Opus.

## Ausstehend
Was nicht gelaufen ist (D7), mit dem genauen Nachfahr-Kommando.
```

- [ ] **Schritt 4: Kein Live-Material im Bericht**

```bash
python3.11 -c "
from scripts.rauchtest_begriffsboard_inhalt import *
segs=lies_live_segmente(LIVE_DB_VORGABE, LIVE_CHAT_ID)
text=open('docs/begriffsboard-inhalt/BERICHT.md',encoding='utf-8').read()
import re
treffer=sum(1 for s in segs for satz in re.split(r'[.!?]', s) if len(satz.strip())>25 and satz.strip() in text)
print('LIVE-SAETZE IM BERICHT:', treffer)"
```

Expected: `LIVE-SAETZE IM BERICHT: 0` (gibt nur eine Zahl aus, nie den
Satz). Ist die Live-DB nicht lesbar (D7), Schritt überspringen und im
Bericht vermerken.

- [ ] **Schritt 5: Commit**

```bash
git add docs/begriffsboard-inhalt/BERICHT.md
git commit -m "$(cat <<'EOF'
Begriffsboard-Inhalt: Bericht mit Messtabelle vorher/nachher, Opus-Spalte, Board-Beispiel (t_2b9d2cbe, Aufgabe 8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: AGENTS.md und Abnahme

**Files:**
- Modify: `AGENTS.md` (Modultabelle, Zeile `begriffsboard.py`; Absatz „Phase 1 hört seit 04.10.2026 laufend mit“; Übergaben der Karte t_4517d4ad)

- [ ] **Schritt 1: AGENTS.md ergänzen**

(a) In der Modultabelle, Zeile `begriffsboard.py`, den Satz

```
Validiert **im Code**: Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`.
```

ersetzen durch

```
Validiert **im Code**: Begriff muss im Transkript stehen und darf kein Ansage-/Mikrofonwort sein (`ist_metabegriff`), Zitat über `zitat.pruefe`, und eine `begruendung` bleibt nur mit Beleg (`traegt_beleg`: geprüftes Zitat mit ≥ `BELEG_MIN_INHALTSWOERTER` = 2 Inhaltswörtern jenseits von Begriff/Ansage) und ohne Füllsatz (`ist_fuellsatz`) -- sonst `""` (Karte t_2b9d2cbe).
```

(b) Im Absatz „**Phase 1 hört seit 04.10.2026 laufend mit, wie Phase 4**“
nach dem Satz „Validiert wird im Code (Begriff muss im Transkript stehen,
Zitat über `zitat.pruefe`), die Tabelle `begriffsboard` nur anhängend.“
einfügen:

```
**Belegpflicht der Begründung** (Karte t_2b9d2cbe, 04.10.2026): eine
`begruendung` gilt nur, wenn ein geprüftes Zitat sie trägt, das nach Abzug
von Begriff, Ansage-Formel (DE+EN samt STT-Varianten „Gepäck“/„Betreff“),
Meta- und Stoppwörtern noch mindestens zwei Inhaltswörter hat, und wenn sie
kein Füllsatz ist („wird genannt/gesammelt“, „came up“); sonst wird sie
leer. Die Wortlisten gelten für DE und EN zugleich, weil Kimi unter dem
EN-Profil deutsch begründete. Leer ist gültig -- `detail_zeilen` lässt solche
Einträge weg, in die Phase-2-Prompts geht nur Belegtes. Merge- und
STT-Spuren gehören nicht in die Begründung (Prompt). Gemessen:
`docs/begriffsboard-inhalt/BERICHT.md`, Messskript
`scripts/rauchtest_begriffsboard_inhalt.py` (kein Test, kostet Geld; `live`
nur read-only und nie an Opus).
```

(c) In „Die Übergaben der Karte t_4517d4ad“ den Punkt „**Ungemessen:** kein
bezahlter Lauf des neuen Prompts `begriffsboard.md` …“ um den Satz
ergänzen: „Seit Karte t_2b9d2cbe gemessen für die Inhaltsqualität der
Begründung (vorher/nachher, Kimi), siehe `docs/begriffsboard-inhalt/BERICHT.md`;
Korpusfälle gibt es weiterhin nicht.“ (Wenn Aufgabe 4/7 „ausstehend“ sind:
statt „gemessen“ „Messung ausstehend, Kommando im Bericht“.)

- [ ] **Schritt 2: Die volle Suite im Hintergrund**

Mit dem Bash-Werkzeug **im Hintergrund** starten (`run_in_background`), Log in
eine Datei:

```bash
python3.11 -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > /tmp/t_2b9d2cbe-suite.log 2>&1; echo "exit $?" >> /tmp/t_2b9d2cbe-suite.log
```

Währenddessen Schritt 3.

- [ ] **Schritt 3: Profil- und Sprachprüfung**

```bash
python3.11 -m scripts.pruefe_profil padua-2026
python3.11 -m scripts.pruefe_sprache padua-2026
```

Expected: `padua-2026: in Ordnung` bzw. `0 Treffer` (Grundlinie des
Plan-Autors am 04.10.2026: beides so).

- [ ] **Schritt 4: Suite auswerten**

```bash
tail -5 /tmp/t_2b9d2cbe-suite.log
```

Expected: `… passed …` ohne `failed`/`error`, letzte Zeile `exit 0`.

Ist etwas rot:
- nur wegen Dortmund-Verhalten → `@pytest.mark.dortmund` am Test, nicht anpassen;
- ein Snapshot-/Bitgleich-Test, der den Padua-Prompt `begriffsboard.md`
  hasht (laut ANNAHME gibt es keinen) → nur für Padua absichtlich erneuern,
  mit dem Kommando aus dem Kopf des jeweiligen Tests, und den Grund in den
  Commit schreiben;
- sonst: Ursache finden (superpowers:systematic-debugging), nicht den Test
  biegen.

Danach Schritt 2 wiederholen, bis `exit 0`.

- [ ] **Schritt 5: Commit**

```bash
git add AGENTS.md
git commit -m "$(cat <<'EOF'
AGENTS.md: Belegpflicht der Begruendung im Begriffsboard, Messung (t_2b9d2cbe, Aufgabe 9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Schritt 6: Handoff** (an den Architekten, als Text, nicht als Datei)

- Messtabelle vorher/nachher (Kimi roh + validiert, Opus-Spalte) aus dem Bericht.
- Board-Beispiel nachher (erfundener Fall).
- Suite: Zahl `passed` und `exit 0` aus `/tmp/t_2b9d2cbe-suite.log`.
- Was nicht 0 wurde, was ausstehend ist (mit Kommando), Kosten gesamt.
- Hinweis auf den Hotspot: war t_cb2c4678 beim Ausführen noch ungemergt, sind
  die Konfliktstellen in `validiere` genau die zwei Zeilen aus Aufgabe 5
  (`ist_metabegriff`-`continue` und `_belege`), in den Prompts die Blöcke
  aus Aufgabe 6.
```

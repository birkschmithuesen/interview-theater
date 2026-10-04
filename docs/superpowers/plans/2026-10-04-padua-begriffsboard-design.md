# Padua Begriffsboard: visuelle Gestaltung (Design-Erweiterung) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Scope-Erweiterung von Karte t_cb2c4678, Branch `wt/t_cb2c4678`, **in diesem Worktree**
(`/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_cb2c4678`). HEAD bei Planbeginn: `05bfe5e`
(„Begriffsboard: web_gestalt._BUEHNE in BLEIBT_DEUTSCH aufnehmen", Aufgabe 11 Nachtrag). Ziel ist `main` über eine
spätere [Merge]-Karte — **kein Merge, kein Push** aus diesem Plan heraus.

**Anlass** (Birk, live, 04.10.2026 17:10, wörtlich siehe `.superpowers-brief-t_cb2c4678-design.md` im Worktree):
das CoThinker-Board in Phase 1 ist fertig *funktional* (Live-Ranking ohne Springen, Schärfungs-Historie — beide
Aufgabe 2–7 dieser Karte, Suite grün: 7383 passed, 1 skipped, 4 deselected, EXIT 0), sieht aber „noch sehr unschön"
aus. Diese Erweiterung macht aus der funktionalen Liste ein kuratiertes, bewusst gestaltetes Bild — ohne die
FLIP-Mechanik, die Datenzusagen (kein Zitat im CoThinker) oder die Dortmund-Invarianten anzurühren.

**Goal:** Drei sichtbare Änderungen am Begriffsboard im CoThinker-Tab (Phase 1, nur Padua): (1) kein aufklappbares
„Warum" mehr — pro Zeile steht nur der Begriff; (2) eine kuratierte Rang-Darstellung (Scheinwerfer-Marke 1–5,
stille Trennlinie zum Rest, gedämpfter/kursiver Status `verworfen`); (3) ein eigenes, bewusstes Design für die
Schärfungskette (ein abgetrenntes „Fach" statt bloßem Anhängetext). Die Live-Umsortierung (FLIP) bleibt exakt die
bestehende Mechanik, nur ohne die jetzt wegfallende Auf-/Zu-Zustandsverfolgung des „Warum".

**Architecture:** Reines CSS- und Markup-Downsizing auf vorhandenen Daten — **keine neue HTML-Struktur, kein neues
`data-*`-Attribut**. `web._begriffsboard_html` trägt schon `data-status`, `data-top`, `data-vorgaenger` an jedem
`<li>`; die gesamte neue Optik (Rang-Marke, Trennlinie, Status-Kursivschrift, Schärfungs-Steg) entsteht allein
über CSS-Selektoren auf diesen Attributen in `web_gestalt._BUEHNE` (`css_buehne()`). Entfernt wird nur die
`<details>`/`<summary>`-Erzeugung in `web._begriffsboard_html` und die dazu gehörige Auf-/Zu-Zustandsverfolgung in
`bbMerke`/`bbSpiele` (`web_vereint._VEREINT_JS`). Der Poll-Takt (`NACHLADEN_MS`) bleibt unverändert — siehe
„Geprüfte, nicht umgesetzte Entscheidung" unten.

**Tech Stack:** Python 3.11 Standardbibliothek, SQLite, pytest, Node (nur für die extrahierten JS-Helfer),
Playwright (nur `tests/e2e`, eigenes venv).

## Global Constraints

Bindend, nicht neu verhandeln:

- **Keine neue HTML-Struktur.** Jede neue Optik hängt an `data-top`, `data-status`, `data-vorgaenger` — Attribute,
  die `web._begriffsboard_html` schon heute schreibt. Kein neues `data-*`, kein neuer Wrapper, keine neue Klasse
  außer den CSS-Selektoren selbst (Klassennamen wie `.begriffsboard`, `.begriff`, `.vorgaenger` bleiben, wie sie
  sind — nur ihre Deklarationen in `web_gestalt._BUEHNE` ändern sich).
- **Kein `style="…"`-Attribut, kein `on…=`-Handler** im ausgelieferten HTML (CSP, `web_gestalt.py` Modulkopf
  Regel 2). Dynamische Werte bleiben CSSOM (`el.style.setProperty`/`el.style.transform` im JS), nie ein
  `setAttribute('style', …)`.
- **Kein `@keyframes`, kein `@media` außerhalb von `css_rahmen()`.** `css_buehne()` läuft durch
  `web_vereint.scope_css`; dessen Regex zerlegt den Rumpf eines `@keyframes`/`@media`-Blocks falsch (Modulkopf
  Regel 3). Die neue CSS trägt **keine** `transition`/`animation`/`@media`/`@keyframes`/`url(` — auch nicht in
  Kommentaren als blankes Wort (Falle siehe Aufgabe 2, Schritt 1 unten).
- **Nur Design-Tokens, keine rohen Hexfarben.** Jede Farbe über `var(--…)` aus `web_gestalt.TOKENS`. Wird eine
  Token-Kombination neu verwendet, die noch nicht in `web_gestalt.KONTRAST` steht, muss sie dort ergänzt werden
  (WCAG ≥ 4.5 für Fließtext, ≥ 3 für Bedienelement-Ränder). **Diese Erweiterung braucht keine neue Kombination** —
  siehe Begründung in Aufgabe 2 (jede verwendete Kombination steht schon in `KONTRAST`).
- **`--text-leise` nie zusätzlich über `opacity` abdunkeln** — das drückt den Kontrast unter 4.5:1 (bestehende
  Regel, siehe `web_gestalt.py` Kommentar bei `_SKRIPT_FLAECHEN`). Ein „älter/leiser"-Eindruck in der
  Schärfungskette entsteht über **Schriftgröße**, nicht über Opazität.
- **Status `verworfen` ist stumm, nicht durchgestrichen.** Durchstreichen (`<del>`) bleibt exklusiv der
  Schärfungskette (`vorgaenger`) vorbehalten — zwei verschiedene Bedeutungen brauchen zwei verschiedene Zeichen.
  `verworfen` bekommt `font-style: italic` plus die ohnehin für „Rest" geltende gedämpfte Größe/Farbe.
- **Datenzusagen unverändert:** kein Zitat im CoThinker (`web_daten.begriffsboard` lässt `zitat` weiter weg), keine
  Behauptung ohne Beleg. Begründung/Zitat/Doppelbedeutung bleiben in der Datenbank — nur das **Rendering** ändert
  sich (`web._begriffsboard_html` zeigt sie nicht mehr an).
- **Dortmund-Code/-Fixtures nicht löschen, nicht neu erzeugen.** Wird ein `*bitgleich*`-Test NUR wegen einer
  Dortmund-/Vorgabe-Fixture rot, bekommt er `@pytest.mark.dortmund` (registriert in `pyproject.toml`) — diese
  Erweiterung berührt nach aktueller Prüfung aber keine `*bitgleich*`-Fixture (CoThinker/Begriffsboard ist ein
  Padua-exklusives Profilmerkmal, in keiner Dortmund-Fixture aktiv).
- **Keine neuen Profilschalter.** Das Begriffsboard rendert weiterhin nur, wenn `workshop.diskussion_aktiv()`
  (Padua) — diese Erweiterung ändert nichts an der Sichtbarkeitslogik.
- Code-Bezeichner deutsch wie im Repo, Kommentare in ae/oe/ue wie im umgebenden Code. Nur erfundenes Material in
  Tests und Screenshots. Nie `.env`/`betrieb/` lesen.
- Branch `wt/t_cb2c4678`, **kein Merge nach main, kein Push**. Ein Commit je Aufgabe, nur die genannten Dateien
  `git add`-en (nie `git add -A`). Commit-Nachrichten enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Suite-Kommando (**immer identisch**, blockierender Vordergrund-Aufruf):
  ```bash
  PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
  $PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
  ```
- E2E-Playwright-venv: `E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python`.
- Kein bezahlter Modelllauf.

**Geprüfte, nicht umgesetzte Entscheidung (Birks Punkt 4, Taktung):** Birk fragte, ob ein kürzerer Poll-Takt nur
für den CoThinker-Tab sinnvoll ist (Vorbild: 3 s Fingerprint-Poll in `cothinker/stage/stage.py`). Geprüft:
`ladeBuehne()` hängt am selben `setInterval(ladeBuehne, __NACHLADEN_MS__)` wie der Stand-Panel-Poll
(`web_vereint.NACHLADEN_MS = web.NEULADEN_SEKUNDEN * 1000` = 10000, eine einzige in `_VEREINT_JS` zweifach
eingesetzte Konstante). Ein eigener, kürzerer Takt nur für `ladeBuehne()` wäre technisch machbar (zweite
`__NACHLADEN_BUEHNE_MS__`-Platzhalter-Konstante, zweiter `setInterval`), aber: (a) erhöht die Serverlast beim
Mehrgruppenbetrieb (jede Gruppe pollt `/g/<token>/teil/buehne` häufiger), (b) vergrößert die Diff-Fläche in einer
Datei, die mehrere Karten parallel berühren (AGENTS.md „Modulkarte", `web_vereint.py` als Hotspot), (c) ist von
Birk selbst als „Inspiration, kein hartes Muss" eingeordnet, während die drei Design-Punkte der Kern sind. Diese
Planung **ändert `NACHLADEN_MS` nicht** und hält das als Übergabe in AGENTS.md fest (Aufgabe 6) statt es stillos
wegzulassen.

---

## Dateiübersicht

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/web.py` | 1 | `_begriffsboard_html`: `<details>`/`<summary>` „Warum" entfernen; `_TEXT_BOARD_WARUM`/`_TEXT_BOARD_DOPPEL` entfernen |
| `interview_theater/sprachen/en/texte.toml` | 1 | dieselben zwei Schlüssel entfernen |
| `tests/test_begriffsboard_web.py` | 1 | eine Testerwartung (kein `<details>` mehr) |
| `interview_theater/web_gestalt.py` | 2 | `_BUEHNE`: Rang-Marke, Trennlinie, gedämpfter Rest, kursives `verworfen`, Schärfungs-Steg |
| `tests/test_begriffsboard_flip.py` | 2, 3 | neue CSS-Assertions; neue Assertion „kein `details`/`offen` mehr in `bbMerke`/`bbSpiele`" |
| `interview_theater/web_vereint.py` | 3 | `_VEREINT_JS`: `bbMerke`/`bbSpiele` ohne Auf-/Zu-Zustandsverfolgung, Kommentar über dem Block |
| `tests/e2e/test_web_begriffsboard_ranking_e2e.py` | 4 | kein Klick auf „Warum" mehr, keine `details.open`-Assertions |
| `tests/e2e/test_web_begriffsboard_design_e2e.py` (neu) | 5 | der „Nachher"-Screenshot, Datenlage mit 5 Top + 1 Rest + 1 verworfen + 1 Schärfungskette |
| `docs/web-begriffsboard/design-2026-10-04.png` (neu) | 5 | der Screenshot für Birk |
| `AGENTS.md` | 6 | Modultabelle (`begriffsboard.py`-Zeile), Übergaben (vanishende Begriffe, Taktung) |

**Nicht** angefasst: `begriffsboard.py` (keine Datenlogik ändert sich), `web_daten.py`, `db.py`/`repo.py`, der
Phase-4-Bühnenkarten-Zweig von `web._buehne_html`, `web._CSS_BUEHNE` (alte, separate Konstante — siehe Hinweis
unten), `tests/test_begriffsboard_schaerfung_web.py` (bleibt wortgleich grün, siehe Aufgabe 2 Begründung),
`web_vereint.NACHLADEN_MS`, jede `*bitgleich*`-Fixture.

**Wichtiger Unterschied, nicht verwechseln:** `web_gestalt._BUEHNE` (über `css_buehne()`, das CoThinker-Panel in
der vereinten Seite — **diese** Konstante ändert sich) ist **nicht** dieselbe wie `web._CSS_BUEHNE` (eine ältere,
separate Konstante für die nicht mehr ausgelieferte Einzelseite `gruppe_html`, geprüft von
`tests/test_web_cothinker_status_html.py::test_css_buehne_enthaelt_kein_keyframes` und
`tests/e2e/test_web_gestalt_buehne_e2e.py`). Diese Erweiterung fasst `web._CSS_BUEHNE` **nicht** an.

---

### Task 1: Kein aufklappbares „Warum" mehr — nur der Begriff

**Files:**
- Modify: `interview_theater/web.py:1029-1032` (Textkonstanten), `interview_theater/web.py:2906-2966`
  (`_begriffsboard_html`)
- Modify: `interview_theater/sprachen/en/texte.toml:1593-1594`
- Modify: `tests/test_begriffsboard_web.py:61-66` (`test_html_ist_funktional_mit_data_attributen`)

**Interfaces:**
- Consumes: nichts Neues — `eintrag["begruendung"]`, `eintrag["doppelbedeutung"]` bleiben im Dict (aus
  `web_daten.begriffsboard`), werden nur nicht mehr gerendert.
- Produces: `_begriffsboard_html(eintraege)` liefert pro `<li>` nur noch `<span class="begriff">…</span>` plus
  optional `<span class="vorgaenger">…</span>` — keine `<details>` mehr. Nachfolgende Aufgaben (2, 5) bauen
  darauf auf.

- [ ] **Step 1: Test zuerst anpassen (failing)**

In `tests/test_begriffsboard_web.py`, Funktion `test_html_ist_funktional_mit_data_attributen` (aktuell Zeilen
61–66):

```python
def test_html_ist_funktional_mit_data_attributen(pfad):
    html_ = web._begriffsboard_html(web_daten.begriffsboard(_ro(pfad), CHAT))
    assert 'data-ansicht="begriffsboard"' in html_
    assert re.search(r'<li data-begriff="Heimat" data-status="favorit"[^>]*data-top="1"', html_)
    assert re.search(r'<li data-begriff="Musik" data-status="verworfen"(?![^>]*data-top)[^>]*>', html_)
    assert "<details>" in html_ and "Ort und Gefuehl" in html_
    assert "&lt;Oma&gt;" in html_ and "<Oma>" not in html_
    assert "ZITAT-NIE-IM-WEB" not in html_
    assert "style=" not in html_
    assert re.search(r"\son\w+=", html_) is None
```

ersetzen durch:

```python
def test_html_ist_funktional_mit_data_attributen(pfad):
    """Seit der Design-Erweiterung (Karte t_cb2c4678, 04.10.2026) zeigt eine
    Zeile NUR noch den Begriff -- Begruendung und Doppelbedeutung bleiben in
    der Datenbank (``web_daten.begriffsboard`` liest sie weiter), aber ohne
    ``<details>`` in der Anzeige."""
    html_ = web._begriffsboard_html(web_daten.begriffsboard(_ro(pfad), CHAT))
    assert 'data-ansicht="begriffsboard"' in html_
    assert re.search(r'<li data-begriff="Heimat" data-status="favorit"[^>]*data-top="1"', html_)
    assert re.search(r'<li data-begriff="Musik" data-status="verworfen"(?![^>]*data-top)[^>]*>', html_)
    assert "<details>" not in html_ and "<summary>" not in html_
    assert "Ort und Gefuehl" not in html_ and "&lt;Oma&gt;" not in html_ and "<Oma>" not in html_
    assert "ZITAT-NIE-IM-WEB" not in html_
    assert "style=" not in html_
    assert re.search(r"\son\w+=", html_) is None
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
$PY -m pytest tests/test_begriffsboard_web.py::test_html_ist_funktional_mit_data_attributen -q
```

Expected: FAIL — `assert "<details>" not in html_ and "<summary>" not in html_` schlägt fehl, weil `_begriffsboard_html`
noch ein `<details>` erzeugt.

- [ ] **Step 3: `_begriffsboard_html` ändern**

In `interview_theater/web.py`, Funktion `_begriffsboard_html` (aktuell Zeilen 2906–2966), den Docstring und den
Zeilen-Baukörper ändern. Aktuell (Zeilen 2906–2917, Docstring):

```python
def _begriffsboard_html(eintraege: list[dict]) -> str:
    """Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad, D9):
    eine Liste in ``begriffsboard.sortiert``-Ordnung, die Top 5 mit
    ``data-top="1"``, Begruendung und Doppelbedeutung aufklappbar. Nur
    funktionales Markup mit ``data-*`` -- die Gestaltung macht die UX-Karte.
    Kein Zitat (``web_daten.begriffsboard`` laesst es weg), kein
    ``style=``, kein ``on…=`` (CSP).

    Eine Schärfungskette (``vorgaenger``, Karte t_cb2c4678) steht
    durchgestrichen hinter dem Begriff, der jüngste zuerst, und als
    ``data-vorgaenger`` am ``<li>`` -- für die FLIP-Zuordnung im Browser
    (``ladeBuehne()`` in ``web_vereint._VEREINT_JS``)."""
```

wird zu:

```python
def _begriffsboard_html(eintraege: list[dict]) -> str:
    """Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad, D9):
    eine Liste in ``begriffsboard.sortiert``-Ordnung, die Top 5 mit
    ``data-top="1"``. Seit der Design-Erweiterung (Karte t_cb2c4678,
    04.10.2026, Birk: "nicht bloss funktional") zeigt eine Zeile NUR noch
    den Begriff -- Begruendung, Zitat und Doppelbedeutung bleiben in der
    Datenbank, stehen aber ohne ``<details>``/``<summary>`` in der Anzeige.
    Rang, Trennlinie zum Rest und die stille Kursivschrift fuer
    ``status="verworfen"`` haengen allein an den vorhandenen ``data-*``
    Attributen -- ``web_gestalt.css_buehne()`` macht daraus das Bild. Kein
    Zitat (``web_daten.begriffsboard`` laesst es weg), kein ``style=``,
    kein ``on…=`` (CSP).

    Eine Schärfungskette (``vorgaenger``, Karte t_cb2c4678) steht
    durchgestrichen hinter dem Begriff, der jüngste zuerst, und als
    ``data-vorgaenger`` am ``<li>`` -- für die FLIP-Zuordnung im Browser
    (``ladeBuehne()`` in ``web_vereint._VEREINT_JS``)."""
```

Weiter unten in derselben Funktion, aktuell (Zeilen 2944–2962):

```python
        teile = []
        if eintrag.get("begruendung"):
            teile.append(
                f'<p data-feld="begruendung">{html.escape(eintrag["begruendung"])}</p>'
            )
        if eintrag.get("doppelbedeutung"):
            teile.append(
                '<p data-feld="doppelbedeutung">'
                f'{_t(T._TEXT_BOARD_DOPPEL.format(doppelbedeutung=eintrag["doppelbedeutung"]))}</p>'
            )
        mehr = (f'<details><summary>{_t(T._TEXT_BOARD_WARUM)}</summary>{"".join(teile)}</details>'
                if teile else "")
        zeilen.append(
            f'<li data-begriff="{begriff}" data-status="{html.escape(eintrag["status"])}" '
            f'data-zustimmung="{int(eintrag["zustimmung"])}" '
            f'data-nennungen="{int(eintrag["nennungen"])}"{vorgaenger_merkmal}{top_merkmal}>'
            f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>'
            f'{vorgaenger_html}{mehr}</li>'
        )
```

wird zu:

```python
        zeilen.append(
            f'<li data-begriff="{begriff}" data-status="{html.escape(eintrag["status"])}" '
            f'data-zustimmung="{int(eintrag["zustimmung"])}" '
            f'data-nennungen="{int(eintrag["nennungen"])}"{vorgaenger_merkmal}{top_merkmal}>'
            f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>'
            f'{vorgaenger_html}</li>'
        )
```

Dann die beiden jetzt ungenutzten Textkonstanten entfernen. Aktuell (Zeilen 1029–1032):

```python
#: Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad).
_TEXT_BOARD_LEER = "Hier erscheinen die Begriffe, die ihr in der Diskussion nennt."
_TEXT_BOARD_WARUM = "Warum"
_TEXT_BOARD_DOPPEL = "Doppelbedeutung: {doppelbedeutung}"
```

wird zu:

```python
#: Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad).
_TEXT_BOARD_LEER = "Hier erscheinen die Begriffe, die ihr in der Diskussion nennt."
```

(`_TEXT_BOARD_WARUM`/`_TEXT_BOARD_DOPPEL` haben nach dieser Aufgabe keinen Aufrufer mehr — vorher per
`grep -rn "_TEXT_BOARD_WARUM\|_TEXT_BOARD_DOPPEL"` im ganzen Repo bestätigt: nur `web.py` und die englische
Tabelle.)

- [ ] **Step 4: Dieselben zwei Schlüssel aus der englischen Tabelle entfernen**

In `interview_theater/sprachen/en/texte.toml`, aktuell (Zeilen 1592–1594):

```toml
_TEXT_BOARD_LEER = "The terms you mention in the discussion will appear here."
_TEXT_BOARD_WARUM = "Why"
_TEXT_BOARD_DOPPEL = "Double meaning: {doppelbedeutung}"
```

wird zu:

```toml
_TEXT_BOARD_LEER = "The terms you mention in the discussion will appear here."
```

- [ ] **Step 5: Test laufen lassen, Erfolg bestätigen**

```bash
$PY -m pytest tests/test_begriffsboard_web.py -q
```

Expected: alle Tests in dieser Datei PASS (`test_html_ist_funktional_mit_data_attributen` jetzt grün, die
anderen unverändert grün).

- [ ] **Step 6: Nachbarliche Tests mitlaufen lassen (keine Regression)**

```bash
$PY -m pytest tests/test_begriffsboard_schaerfung_web.py tests/test_sprache.py tests/test_sprache_texte.py -q
```

Expected: alle PASS. `test_begriffsboard_schaerfung_web.py` bleibt wortgleich grün, weil keiner seiner Tests
`<details>` erwartet (die Schärfungskette selbst — `<span class="vorgaenger">…</span>` — wird in dieser Aufgabe
nicht verändert); `test_sprache_texte.py` bleibt grün, weil `web_gestalt._BUEHNE`/`web._CSS_BUEHNE` schon in der
Ausnahmeliste stehen und keine neue, unübersetzte Nutzertext-Konstante entsteht.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/web.py interview_theater/sprachen/en/texte.toml tests/test_begriffsboard_web.py
git commit -m "$(cat <<'EOF'
Begriffsboard: kein aufklappbares Warum mehr -- nur der Begriff (t_cb2c4678, Design-Erweiterung Aufgabe 1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Kuratierte Rang-Darstellung und eigenes Schärfungs-Design im CSS

**Files:**
- Modify: `interview_theater/web_gestalt.py:1331-1348` (`_BUEHNE`)
- Modify: `tests/test_begriffsboard_flip.py` (zwei neue Testfunktionen am Dateiende)

**Interfaces:**
- Consumes: `data-top="1"` (nur an den ersten bis zu 5 nicht-verworfenen Zeilen, aus
  `begriffsboard.top()`/`web._begriffsboard_html`), `data-status="verworfen"`, die bestehende Markup-Struktur
  `<span class="begriff">…</span><span class="vorgaenger"><del>…</del> …</span>` (unverändert seit vorheriger
  Aufgabe dieser Karte).
- Produces: `web_gestalt.css_buehne()` liefert die neuen Regeln; keine neue Python-Funktion, keine neue
  Exportfläche — nur der String-Inhalt von `_BUEHNE` ändert sich.

**Warum keine neue `KONTRAST`-Zeile nötig ist:** die Rang-Marke setzt `color: var(--auf-signal)` auf
`background: var(--signal)` — das Paar `Paar("auf-signal", "signal", "Text auf gefuellter Signalflaeche", 4.5)`
steht schon in `web_gestalt.KONTRAST`. Begriff-Text in `--text`/`--text-leise` auf dem Seitengrund (`--grund`,
da das Begriffsboard in keiner `.karte`-Fläche liegt) — `Paar("text", "grund", …, 4.5)` und
`Paar("text-leise", "grund", …, 4.5)` stehen ebenfalls schon dort. Die Trennlinie (`--linie`) ist laut
`KONTRAST`-Kommentar bewusst **nicht** geprüft (Haarlinie, keine Bedienelement-Grenze).

- [ ] **Step 1: Zwei Tests zuerst schreiben (failing)**

An das Ende von `tests/test_begriffsboard_flip.py` anfügen (nach der letzten bestehenden Funktion
`test_css_ist_ruhend_ohne_media_und_ohne_hexfarbe`):

```python
def test_css_hat_rang_marke_trennlinie_und_verworfen_kursiv():
    """Design-Erweiterung (Karte t_cb2c4678, 04.10.2026): Rang 1-5 bekommt
    eine Scheinwerfer-Marke (CSS-Counter auf data-top), der Rest eine
    Trennlinie direkt danach, ``status="verworfen"`` eine stille
    Kursivschrift -- durchgestrichen bleibt allein der Schaerfungskette
    vorbehalten."""
    css = web_gestalt.css_buehne()
    assert 'li[data-top="1"]::before' in css
    assert "counter-increment: bbrang" in css
    assert 'li[data-top="1"] + li:not([data-top="1"])' in css
    assert 'li[data-status="verworfen"] .begriff { font-style: italic; }' in css
    # Durchstreichen bleibt exklusiv der Schaerfungskette: keine neue
    # text-decoration-Regel fuer verworfen.
    verworfen_regel = css[css.index('li[data-status="verworfen"]'):]
    verworfen_regel = verworfen_regel[:verworfen_regel.index("}") + 1]
    assert "text-decoration" not in verworfen_regel
    # Ueberlebt das Scoping wie der Rest von css_buehne().
    gescoped = web_vereint.scope_css(css, ".panel-buehne")
    assert '.panel-buehne .begriffsboard li[data-top="1"]::before' in gescoped
    assert '.panel-buehne .begriffsboard li[data-status="verworfen"] .begriff' in gescoped


def test_css_ohne_hexfarbe_bleibt_auch_mit_dem_neuen_design_wahr():
    """Regression auf der bestehenden Zusage: die ganze ``_BUEHNE``-Konstante
    bleibt frei von rohen Hexfarben, nicht nur der Teil ab ``.vorgaenger``."""
    css = web_gestalt.css_buehne()
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    for verboten in ("@media", "@keyframes", "transition", "animation", "url("):
        assert verboten not in css, verboten
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py::test_css_hat_rang_marke_trennlinie_und_verworfen_kursiv tests/test_begriffsboard_flip.py::test_css_ohne_hexfarbe_bleibt_auch_mit_dem_neuen_design_wahr -q
```

Expected: FAIL — `'li[data-top="1"]::before' in css` schlägt fehl, die Regeln existieren noch nicht. Die zweite
Testfunktion (Hexfarben/verbotene Wörter) PASSt bereits (die bestehende `_BUEHNE` hat keine Hexfarben) — das ist
in Ordnung, sie ist eine Regressionssicherung für den nächsten Schritt.

- [ ] **Step 3: `_BUEHNE` ersetzen**

In `interview_theater/web_gestalt.py`, die gesamte Konstante `_BUEHNE` (aktuell Zeilen 1331–1348):

```python
_BUEHNE = """
#buehne-panel .karte { background: var(--grund-2); color: var(--text);
                       border-color: var(--linie); }
#buehne-panel .karte.alt { color: var(--text-leise); opacity: 1; }
#buehne-panel .hoert-zu { color: var(--text-leise); opacity: 1; }
#buehne-panel .leer { color: var(--text-leise); opacity: 1; }
.stueckkarte { background: var(--grund-3); }
.sk-haken { color: var(--text-leise); opacity: 1; }
.sk-frei { color: var(--text-leise); opacity: 1; }
/* Begriffsboard (Karte t_cb2c4678): die Schaerfungskette steht leise und
   durchgestrichen hinter dem Begriff, der Pfeil zeigt vom alten Wortlaut
   zum neuen. Nur Ruhendes: die Bewegung (FLIP) setzt ladeBuehne() per
   CSSOM und nur ohne prefers-reduced-motion -- hier steht weder
   transition noch @media (dieser Block laeuft durch scope_css). */
.begriffsboard .vorgaenger { color: var(--text-leise); margin-left: 0.4em; }
.begriffsboard .vorgaenger::before { content: "\\2190\\00a0"; }
.begriffsboard .vorgaenger del { text-decoration-thickness: 1px; }
"""
```

wird vollständig ersetzt durch:

```python
_BUEHNE = """
#buehne-panel .karte { background: var(--grund-2); color: var(--text);
                       border-color: var(--linie); }
#buehne-panel .karte.alt { color: var(--text-leise); opacity: 1; }
#buehne-panel .hoert-zu { color: var(--text-leise); opacity: 1; }
#buehne-panel .leer { color: var(--text-leise); opacity: 1; }
.stueckkarte { background: var(--grund-3); }
.sk-haken { color: var(--text-leise); opacity: 1; }
.sk-frei { color: var(--text-leise); opacity: 1; }
/* Begriffsboard -- Design-Erweiterung (Karte t_cb2c4678, 04.10.2026,
   Birk: "richtig gut designt, nicht bloss funktional"). Kein
   aufklappbares "Warum" mehr (web._begriffsboard_html): eine Zeile zeigt
   nur noch den Begriff, Rang und Status tragen allein die vorhandenen
   data-*-Attribute. Nur Ruhendes hier -- die Bewegung (FLIP) setzt
   ladeBuehne() per CSSOM und nur ohne prefers-reduced-motion; dieser
   Block laeuft durch scope_css und bleibt deshalb ohne Medienabfrage,
   Keyframe-Animation oder eine im CSS gesetzte Uebergangsdauer. */
.begriffsboard { list-style: none; counter-reset: bbrang; margin: 0; padding: 0; }
.begriffsboard li { display: flex; align-items: baseline; flex-wrap: wrap;
                     gap: .15rem .6rem; padding: .4rem 0; }
/* Rang 1-5 (data-top="1", begriffsboard.top()): die Zeilen, die
   "Take these" tatsaechlich vorschlaegt -- eine Scheinwerfer-Marke mit
   Nummer, der Begriff groesser und in der Buehnenschrift gesetzt. */
.begriffsboard li[data-top="1"] { counter-increment: bbrang; }
.begriffsboard li[data-top="1"]::before {
  content: counter(bbrang); flex: 0 0 auto; width: 1.5rem; height: 1.5rem;
  border-radius: 50%; background: var(--signal); color: var(--auf-signal);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--schrift-tech); font-size: .78rem; font-weight: 700;
}
.begriffsboard li[data-top="1"] .begriff {
  font-family: var(--schrift-skript); font-weight: 700; font-size: 1.1em;
  color: var(--text);
}
/* Alles unter der Scheinwerfer-Marke ist die Kandidatenliste, nicht mehr
   der Vorschlag -- kleiner und stiller, keine eigene Marke. */
.begriffsboard li:not([data-top="1"]) .begriff {
  font-size: .92em; color: var(--text-leise);
}
/* Der Schnitt zwischen Vorschlag und Rest: eine duenne Linie, einmal, am
   ersten Nicht-Rang-Eintrag direkt NACH dem letzten Rang-Eintrag -- ohne
   feste Positionszahl, falls das Board (noch) weniger als 5 Vorschlaege
   hat. */
.begriffsboard li[data-top="1"] + li:not([data-top="1"]) {
  border-top: 1px solid var(--linie); margin-top: .3rem; padding-top: .75rem;
}
/* Verworfen (begriffsboard.STATUS) bleibt auf dem Board sichtbar --
   "Take these" liest nur top() --, aber kursiv wie eine leise
   Randnotiz. Durchgestrichen bleibt allein der Schaerfungskette
   vorbehalten (naechste Regel), damit beide Zeichen Verschiedenes
   bedeuten. */
.begriffsboard li[data-status="verworfen"] .begriff { font-style: italic; }
/* Schaerfungskette (vorgaenger, Karte t_cb2c4678): ein eigenes Fach
   rechts vom lebenden Begriff, durch einen stillen Steg abgetrennt --
   "zur Seite geschoben" statt nur angehaengtem Text. Der juengste
   Vorgaenger steht direkt im Steg, jeder aeltere eine Stufe kleiner --
   das Alter traegt die Groesse, nicht die Opazitaet (die wuerde
   --text-leise unter 4.5:1 druecken, siehe Modulkopf). */
.begriffsboard .vorgaenger { display: inline-flex; align-items: baseline;
                             gap: .35em; margin-left: .5em; padding-left: .5em;
                             border-left: 1px solid var(--linie); }
.begriffsboard .vorgaenger del { color: var(--text-leise); font-size: .85em;
                                 text-decoration-thickness: 1px; }
.begriffsboard .vorgaenger del:not(:first-child) { font-size: .75em; }
"""
```

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py -q
```

Expected: alle Tests in dieser Datei PASS, inklusive der schon bestehenden
`test_css_ist_ruhend_ohne_media_und_ohne_hexfarbe` (die Slice-Prüfung ab `.begriffsboard .vorgaenger` bleibt
gültig: die Zeichenkette `.begriffsboard .vorgaenger` steht weiterhin wortgleich als Selektor da, und alles ab
dort — die zwei `.vorgaenger`/`.vorgaenger del`-Regeln — enthält kein `@media`/`@keyframes`/`transition`/
`animation`/`url(`/Hexfarbe).

- [ ] **Step 5: Auch die Schärfungs-Web-Tests gegenprüfen**

```bash
$PY -m pytest tests/test_begriffsboard_schaerfung_web.py tests/test_begriffsboard_web.py tests/test_web_gestalt_tokens.py tests/test_sprache_texte.py -q
```

Expected: alle PASS. `test_begriffsboard_schaerfung_web.py` und `test_begriffsboard_web.py` prüfen ausschließlich
den von `web._begriffsboard_html` erzeugten **HTML**-String (unverändert durch diese Aufgabe — nur das CSS ändert
sich); `test_web_gestalt_tokens.py` bleibt grün, weil keine neue Token-Kombination eingeführt wurde.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_begriffsboard_flip.py
git commit -m "$(cat <<'EOF'
Begriffsboard: Rang-Marke, Trennlinie, kursives verworfen, eigenes Schaerfungs-Design im CSS (t_cb2c4678, Design-Erweiterung Aufgabe 2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: FLIP-Helfer vereinfachen — kein Auf-/Zu-Zustand mehr zu verfolgen

**Files:**
- Modify: `interview_theater/web_vereint.py:1276-1371` (Kommentarblock + `bbMerke`/`bbSpiele` in `_VEREINT_JS`)
- Modify: `tests/test_begriffsboard_flip.py` (eine neue Testfunktion)

**Interfaces:**
- Consumes: nichts Neues — dieselbe Zuordnung über `data-begriff`/`data-vorgaenger` (`bbSchluessel`,
  `bbZuordnung`, `bbVersatz`, unverändert).
- Produces: `bbMerke(panel)` liefert `{ alt: [...], lagen: {...} }` (ohne `offen`-Feld); `bbSpiele(panel, vorher)`
  liest `vorher.alt`/`vorher.lagen` (ohne `vorher.offen`). Kein Aufrufer außerhalb von `ladeBuehne()` — die beiden
  Aufrufstellen in `ladeBuehne()` selbst (`var bbVorher = bbMerke(panel);` / `bbSpiele(panel, bbVorher);`) bleiben
  zeichengleich.

- [ ] **Step 1: Test zuerst schreiben (failing)**

An das Ende von `tests/test_begriffsboard_flip.py` anfügen:

```python
def test_bbmerke_und_bbspiele_verfolgen_kein_warum_mehr():
    """Design-Erweiterung (Karte t_cb2c4678, 04.10.2026): ohne
    aufklappbares "Warum" (Aufgabe 1) gibt es keinen Auf-/Zu-Zustand mehr,
    den die FLIP-Helfer ueber den Panel-Tausch retten muessten."""
    js = web_vereint._VEREINT_JS
    merke = _extrahiere(js, "bbMerke")
    spiele = _extrahiere(js, "bbSpiele")
    assert "details" not in merke and "details" not in spiele
    assert "offen" not in merke and "offen" not in spiele
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py::test_bbmerke_und_bbspiele_verfolgen_kein_warum_mehr -q
```

Expected: FAIL — `bbMerke`/`bbSpiele` enthalten noch `details`/`offen`.

- [ ] **Step 3: `bbMerke`/`bbSpiele` und den Kommentar darüber ändern**

In `interview_theater/web_vereint.py`, im String `_VEREINT_JS`. Aktueller Kommentarblock (Zeilen 1276–1286):

```javascript
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
```

wird zu:

```javascript
  // -- Begriffsboard: Live-Ranking ohne Springen (Karte t_cb2c4678) -------
  //
  // ladeBuehne() tauscht das ganze Panel (panel.innerHTML = neu). Damit die
  // Liste dabei nicht springt, misst bbMerke() die alten Zeilen UNMITTELBAR
  // davor und bbSpiele() spielt UNMITTELBAR danach FLIP: jede Zeile startet
  // optisch an ihrer alten Stelle und gleitet an die neue. Zuordnung ueber
  // data-begriff, fuer einen geschaerften Begriff ueber data-vorgaenger.
  // Seit der Design-Erweiterung gibt es kein aufklappbares "Warum" mehr --
  // bbMerke/bbSpiele muessen keinen Auf-/Zu-Zustand mehr tragen. Ohne
  // ol.begriffsboard (Phase 4, Buehnenkarten) tun beide nichts. Bewegung
  // nur per CSSOM (CSP) und nie bei prefers-reduced-motion: reduce.
  var BB_DAUER_MS = 320;
```

Aktuelle `bbMerke` (Zeilen 1319–1332):

```javascript
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
```

wird zu:

```javascript
  function bbMerke(panel) {
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return null; }
    var vorher = { alt: [], lagen: {} };
    Array.prototype.forEach.call(ol.children, function (li) {
      var b = li.getAttribute('data-begriff');
      var k = bbSchluessel(b);
      vorher.alt.push(b);
      vorher.lagen[k] = li.getBoundingClientRect().top;
    });
    return vorher;
  }
```

Aktuelle `bbSpiele` (Zeilen 1334–1371):

```javascript
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

wird zu:

```javascript
  function bbSpiele(panel, vorher) {
    if (!vorher) { return; }
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return; }
    var lis = Array.prototype.slice.call(ol.children);
    var quellen = bbZuordnung(vorher.alt, lis.map(function (li) {
      return { begriff: li.getAttribute('data-begriff'),
               vorgaenger: li.getAttribute('data-vorgaenger') };
    }));
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

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

```bash
$PY -m pytest tests/test_begriffsboard_flip.py -q
```

Expected: alle Tests PASS — insbesondere auch die drei unveränderten Bestandstests
(`test_ladebuehne_merkt_vor_dem_tausch_und_spielt_danach`, `test_ohne_board_tun_die_funktionen_nichts`,
`test_skript_haelt_die_csp_und_die_ruhe`), weil `ladeBuehne()` selbst nicht verändert wird und `bbSpiele`
weiterhin mit `if (!vorher` vor dem ersten `querySelector`-Aufruf beginnt.

- [ ] **Step 5: Node-Helfer isoliert gegenprüfen**

```bash
node -e "
$($PY -c "
import re
from interview_theater import web_vereint
js = web_vereint._VEREINT_JS
for name in ('bbSchluessel', 'bbZuordnung', 'bbVersatz', 'bbMerke', 'bbSpiele'):
    m = re.search(r'function\s+' + name + r'\s*\([^)]*\)\s*\{', js)
    i = m.end(); tiefe = 1
    while tiefe:
        if js[i] == '{': tiefe += 1
        elif js[i] == '}': tiefe -= 1
        i += 1
    print(js[m.start():i])
")
console.log('ok, keine Syntaxfehler');
"
```

Expected: `ok, keine Syntaxfehler` (reiner Syntax-Sanity-Check — die eigentlichen Verhaltensprüfungen laufen
bereits über `tests/test_begriffsboard_flip.py`, dessen Node-Harness identisch extrahiert).

- [ ] **Step 6: Commit**

```bash
git add interview_theater/web_vereint.py tests/test_begriffsboard_flip.py
git commit -m "$(cat <<'EOF'
Begriffsboard: bbMerke/bbSpiele ohne Auf-/Zu-Zustand -- kein Warum mehr zu verfolgen (t_cb2c4678, Design-Erweiterung Aufgabe 3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Bestehenden Browserlauf anpassen — kein Klick auf „Warum" mehr

**Files:**
- Modify: `tests/e2e/test_web_begriffsboard_ranking_e2e.py` (Docstring, Funktion `_lauf`)

**Interfaces:**
- Consumes: Task 1–3 (kein `<details>` im gerenderten HTML, `bbMerke`/`bbSpiele` ohne `offen`-Feld).
- Produces: nichts Neues — derselbe Testname, dieselbe Baugruppe (`server`-Fixture, `_lauf`), nur ohne die jetzt
  sinnlosen Interaktionen.

- [ ] **Step 1: Datei-Docstring anpassen**

Aktuell (Zeilen 1–13):

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
```

wird zu:

```python
"""Karte t_cb2c4678, Aufgabe 6 (angepasst in der Design-Erweiterung,
04.10.2026): das Begriffsboard sortiert im echten Browser um, ohne zu
springen (D3). Ein echter Webserver-Prozess unter
``IT_WORKSHOP=padua-2026`` (sonst gibt es kein Board), eine Gruppe in
Phase 1, ein Board A; der Test legt ein umsortiertes Board B mit einer
Schaerfung ("Roboter" -> "KI-Roboter") in die Datenbank und wartet auf den
naechsten ``ladeBuehne()``-Takt. Nachgewiesen werden die Wirkungen der
Zuordnung: die verschobene und die geschaerfte Zeile bekommen ein
``translateY`` (mit reduzierter Bewegung: keins), und die alte Fassung
steht als ``<del>``. Seit der Design-Erweiterung gibt es kein
aufklappbares "Warum" mehr -- dieser Lauf klickt keins mehr an.

Ohne Playwright wird die Datei uebersprungen (``importorskip``). Der
Handy-Schuss landet immer unter /tmp und nur mit
``IT_SCHUSS_AKTUALISIEREN=1`` im Repository (Muster
``test_web_cothinker_status_screenshot_e2e.py``). Nur erfundenes Material.

**Vorher-Referenz der Design-Erweiterung:** der Screenshot, den dieser
Test erzeugt (mit ``IT_SCHUSS_AKTUALISIEREN=1``, zuletzt am 04.10.2026 VOR
der Design-Erweiterung gelaufen), liegt unter
``docs/web-begriffsboard/ranking-2026-10-04.png`` -- NICHT erneut mit
``IT_SCHUSS_AKTUALISIEREN=1`` laufen lassen, solange diese Datei als
"Vorher"-Beleg gilt (siehe ``docs/superpowers/plans/2026-10-04-padua-begriffsboard-design.md``,
Aufgabe 5)."""
```

- [ ] **Step 2: `_lauf` ändern — keine Klicks auf „Warum", keine `details`-Assertions**

Aktuell (ganze Funktion `_lauf`, der betroffene Ausschnitt):

```python
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
```

wird zu:

```python
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
            assert seite.locator("#tab-buehne details").count() == 0

            transforms = seite.evaluate("() => window.__bbTransforms")
```

Der restliche Funktionskörper (ab `if ruhig: assert transforms == {}` bis zum Ende der Funktion, inklusive
Screenshot-Logik) bleibt **unverändert**.

- [ ] **Step 3: Test laufen lassen (E2E-venv)**

```bash
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python
$E2E -m pytest tests/e2e/test_web_begriffsboard_ranking_e2e.py -q
```

Expected: beide Tests (`test_board_sortiert_um_ohne_zu_springen_und_zeigt_die_schaerfung`,
`test_reduzierte_bewegung_ohne_animation_aber_mit_offenem_warum`) PASS. **`IT_SCHUSS_AKTUALISIEREN` bleibt dabei
ungesetzt** — der Testlauf schreibt nur nach `/tmp/it-bb-ranking/ranking-2026-10-04.png`, nicht in `docs/`; die
bestehende, committete `docs/web-begriffsboard/ranking-2026-10-04.png` bleibt dadurch als „Vorher"-Beleg
unverändert.

Hinweis: der zweite Testname (`test_reduzierte_bewegung_ohne_animation_aber_mit_offenem_warum`) trägt noch den
alten Namen aus Aufgabe 6 dieser Karte — er wird in dieser Aufgabe **nicht** umbenannt (reine Verhaltensänderung,
kein Namens-Aufräumen; der Name beschreibt weiterhin korrekt den `ruhig=True`-Fall, auch ohne „Warum").

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_web_begriffsboard_ranking_e2e.py
git commit -m "$(cat <<'EOF'
e2e Begriffsboard: kein Klick mehr auf das entfernte Warum (t_cb2c4678, Design-Erweiterung Aufgabe 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Neuer Browserlauf — der „Nachher"-Screenshot mit allen Zuständen

**Files:**
- Create: `tests/e2e/test_web_begriffsboard_design_e2e.py`
- Create: `docs/web-begriffsboard/design-2026-10-04.png` (per Testlauf mit `IT_SCHUSS_AKTUALISIEREN=1`, nicht von
  Hand)

**Interfaces:**
- Consumes: Task 1–3 (das fertige neue Markup/CSS/JS); `repo.lege_begriffsboard_an`, `repo.sichere_gruppe`,
  `repo.setze_gruppe_kanal`, `repo.setze_phase`, `repo.stelle_web_token_sicher` (unverändert aus `repo.py`, wie in
  `tests/e2e/test_web_begriffsboard_ranking_e2e.py` verwendet).
- Produces: eine eigenständige Datei, kein Aufrufer in anderen Tasks.

**Datenlage** (begründet die erwartete Reihenfolge über `begriffsboard.sortiert`, Schlüssel
`(rang, -zustimmung, -nennungen, schluessel(begriff))`, `rang`: favorit=0, kandidat=1, verworfen=2):

| Begriff | Status | Zustimmung | Nennungen | Vorgänger | Position |
|---|---|---|---|---|---|
| Heimat | favorit | 2 | 5 | — | 1 (Top) |
| Grenze | favorit | 2 | 3 | — | 2 (Top) |
| Familie | kandidat | 1 | 4 | — | 3 (Top) |
| Streit | kandidat | 1 | 2 | — | 4 (Top) |
| Musik | kandidat | 0 | 3 | Lieder | 5 (Top, letzte Rang-Zeile, trägt die Schärfungskette) |
| Zukunft | kandidat | 0 | 1 | — | 6 (Rest, erste Zeile nach der Trennlinie) |
| Partyszene | verworfen | -1 | 1 | — | 7 (Rest, kursiv) |

- [ ] **Step 1: Datei anlegen**

```python
"""Karte t_cb2c4678, Design-Erweiterung (04.10.2026): der "Nachher"-Beleg
der visuellen Gestaltung -- ein Board mit allen drei neuen Zustaenden auf
einmal (Scheinwerfer-Marke 1-5, Trennlinie zum Rest, kursives
``verworfen``, Schaerfungs-Steg). Gegenstueck zum "Vorher"-Beleg
``docs/web-begriffsboard/ranking-2026-10-04.png`` (aus Aufgabe 6 der
Karte, VOR dieser Design-Erweiterung erzeugt -- siehe
``docs/superpowers/plans/2026-10-04-padua-begriffsboard-design.md``).

Ohne Playwright wird die Datei uebersprungen (``importorskip``). Der
Handy-Schuss landet immer unter /tmp und nur mit
``IT_SCHUSS_AKTUALISIEREN=1`` im Repository (Muster wie
``tests/e2e/test_web_begriffsboard_ranking_e2e.py``). Nur erfundenes
Material."""

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

DB_PFAD = "/tmp/it-bb-design.db"
AUDIO = "/tmp/it-bb-design-audio"
SERVERLOG = "/tmp/it-bb-design-server.log"
CHAT = 7_000_000_000_102
HANDY = {"width": 390, "height": 844}
SCHUSS = WURZEL / "docs" / "web-begriffsboard" / "design-2026-10-04.png"
SCHUSS_TMP = Path("/tmp/it-bb-design/design-2026-10-04.png")
GEDULD_MS = 30_000


def _e(begriff, status, zustimmung, nennungen, begruendung, vorgaenger=None):
    eintrag = {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
               "begruendung": begruendung, "zitat": "", "doppelbedeutung": "",
               "status": status}
    if vorgaenger:
        eintrag["vorgaenger"] = vorgaenger
    return eintrag


BOARD = [
    _e("Heimat", "favorit", 2, 5, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "favorit", 2, 3, "Eine Grenze kann auch im Kopf sein."),
    _e("Familie", "kandidat", 1, 4, "Wer gehoert dazu, wer nicht."),
    _e("Streit", "kandidat", 1, 2, "Ein Streit, der nie ausgesprochen wurde."),
    _e("Musik", "kandidat", 0, 3,
       "Zuerst als 'Lieder' genannt, spaeter geschaerft auf 'Musik'.", ["Lieder"]),
    _e("Zukunft", "kandidat", 0, 1, "Noch unklar, ob das traegt."),
    _e("Partyszene", "verworfen", -1, 1, "Kam nur einmal vor, dann nie wieder."),
]


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        Path(DB_PFAD + endung).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "designbot", "Designgruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 0)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    return token


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


def test_kuratiertes_board_zeigt_rang_trennlinie_verworfen_und_schaerfung(server):
    basis, token = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
            seite = kontext.new_page()
            seite.set_default_timeout(GEDULD_MS)
            seite.goto(f"{basis}/g/{token}#buehne")
            seite.wait_for_selector('#tab-buehne li[data-begriff="Partyszene"]', state="visible")

            reihenfolge = seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li", "els => els.map(e => e.dataset.begriff)")
            assert reihenfolge == [
                "Heimat", "Grenze", "Familie", "Streit", "Musik", "Zukunft", "Partyszene",
            ]
            assert seite.locator('#tab-buehne li[data-top="1"]').count() == 5
            assert seite.locator('#tab-buehne li[data-status="verworfen"]').count() == 1
            assert seite.locator("#tab-buehne details").count() == 0
            assert seite.locator(
                '#tab-buehne li[data-begriff="Musik"] .vorgaenger del').inner_text() == "Lieder"

            # Die Trennlinie liegt an der Scheinwerfer-Grenze, nicht an
            # einer festen Position: Rang-Zeile ohne oberen Rand, erste
            # Rest-Zeile mit einem.
            musik_rand = seite.locator('#tab-buehne li[data-begriff="Musik"]').evaluate(
                "el => getComputedStyle(el).borderTopWidth")
            zukunft_rand = seite.locator('#tab-buehne li[data-begriff="Zukunft"]').evaluate(
                "el => getComputedStyle(el).borderTopWidth")
            assert musik_rand == "0px"
            assert zukunft_rand != "0px"

            # Verworfen ist kursiv, nicht durchgestrichen -- das Zeichen
            # bleibt der Schaerfungskette vorbehalten.
            verworfen_stil = seite.locator(
                '#tab-buehne li[data-status="verworfen"] .begriff').evaluate(
                "el => getComputedStyle(el).fontStyle")
            assert verworfen_stil == "italic"

            SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
            seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
            assert SCHUSS_TMP.stat().st_size > 1000
            if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
                SCHUSS.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SCHUSS_TMP, SCHUSS)
            kontext.close()
        finally:
            chromium.close()
```

- [ ] **Step 2: Test laufen lassen (ohne Repository-Schuss)**

```bash
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python
$E2E -m pytest tests/e2e/test_web_begriffsboard_design_e2e.py -q
```

Expected: PASS. Prüft Reihenfolge, Rang-Zahl, Verworfen-Zahl, Abwesenheit von `<details>`, die Schärfungskette,
die Trennlinie (per berechnetem `borderTopWidth`) und den kursiven Stil — alles ohne den Screenshot ins
Repository zu schreiben.

- [ ] **Step 3: Den „Nachher"-Screenshot erzeugen**

```bash
IT_SCHUSS_AKTUALISIEREN=1 $E2E -m pytest tests/e2e/test_web_begriffsboard_design_e2e.py -q
ls -la docs/web-begriffsboard/design-2026-10-04.png
```

Expected: PASS, und die Datei `docs/web-begriffsboard/design-2026-10-04.png` existiert mit Größe > 1000 Bytes.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_web_begriffsboard_design_e2e.py docs/web-begriffsboard/design-2026-10-04.png
git commit -m "$(cat <<'EOF'
Begriffsboard: Nachher-Screenshot der Design-Erweiterung, neuer Browserlauf mit allen drei Zustaenden (t_cb2c4678, Design-Erweiterung Aufgabe 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: AGENTS.md nachziehen

**Files:**
- Modify: `AGENTS.md`

**Interfaces:** keine (reine Dokumentation).

- [ ] **Step 1: Die `begriffsboard.py`-Zeile der Modultabelle ergänzen**

In `AGENTS.md`, im Abschnitt „Module unter `interview_theater/`", die Zeile für `begriffsboard.py` endet aktuell
mit (Satzende des bestehenden Eintrags):

```
...Im CoThinker durchgestrichen (`web._begriffsboard_html`, `data-vorgaenger`), Live-Ranking per FLIP direkt in `ladeBuehne()` (`_VEREINT_JS`: `bbMerke` vor, `bbSpiele` nach dem Panel-Tausch; ohne `ol.begriffsboard` wirkungslos). |
```

Danach (im selben Tabellenfeld, als neuer Satz vor dem schließenden `|`) ergänzen:

```
 Design-Erweiterung (04.10.2026, Birk: „richtig gut designt, nicht bloss funktional"): kein aufklappbares „Warum" mehr in der Anzeige (Begründung/Zitat/Doppelbedeutung bleiben in der Datenbank, nur das Rendering in `web._begriffsboard_html` zeigt sie nicht mehr) — Rang 1–5 (`data-top="1"`) bekommt eine Scheinwerfer-Marke, der Rest eine Trennlinie direkt danach (`css_buehne()`, CSS-Selektor `li[data-top="1"] + li:not([data-top="1"])`, keine feste Positionszahl), `status="verworfen"` bleibt sichtbar, aber kursiv — durchgestrichen bleibt allein der Schärfungskette vorbehalten. Die Kette selbst bekommt ein eigenes Fach (`border-left`-Steg), der jüngste Vorgänger im Steg, jeder ältere eine Stufe kleiner (Größe trägt das Alter, nicht Opazität — die würde `--text-leise` unter 4,5:1 drücken). `bbMerke`/`bbSpiele` verfolgen seitdem keinen Auf-/Zu-Zustand mehr.
```

- [ ] **Step 2: Übergabe „silently vanishende Begriffe" ergänzen**

Im Abschnitt „Was bewusst fehlt", bei den „Übergaben der Karte t_4517d4ad (Begriffsboard, 04.10.2026)" (die
Liste, die mit „Ungemessen: kein bezahlter Lauf…" beginnt), als neuen Punkt am Ende der Liste ergänzen:

```
- **Design-Erweiterung (04.10.2026): ein Begriff, der ganz vom Board faellt, bleibt unsichtbar.** Nennt die
  Gruppe einen Begriff danach nicht mehr, und das Modell fuehrt ihn im naechsten Lauf nicht mehr, ersetzt
  `begriffsboard._lauf_einmal` das gespeicherte Board vollstaendig durch das neue Ergebnis (`repo.lege_begriffsboard_an`)
  -- der Begriff verschwindet ohne jede Spur, kein Ereignis, kein Zeitstempel. Birk hat das am 04.10.2026 17:10
  als moegliche eigene Visualisierung angefragt ("ein Begriff, der ganz aus dem Board faellt, weil er nie wieder
  genannt wurde"); eine Pruefung ergab: dafuer existiert heute **keine Datengrundlage** -- nichts haelt fest,
  *dass* ein Begriff verschwunden ist, nur *was* zuletzt gespeichert wurde. Nicht gebaut, um nichts zu erfinden.
  Zu unterscheiden vom bestehenden `status="verworfen"` (ein Begriff, den das Modell ausdruecklich als erledigt
  markiert -- der bleibt sichtbar und bekommt seit der Design-Erweiterung eine eigene, gedaempft-kursive
  Darstellung, siehe die `begriffsboard.py`-Zeile oben). Ein kuenftiger Bau bräuchte einen Vorher/Nachher-Abgleich
  der beiden Boardstaende in `_lauf_einmal` und eine neue, dauerhaft gespeicherte Markierung -- beides nicht Teil
  dieser Karte.
- **Design-Erweiterung (04.10.2026): der Poll-Takt des CoThinker-Tabs bleibt bei den 10 s aller Panels.** Birk
  nannte als Vorbild den 3-s-Fingerprint-Poll von `cothinker/stage/stage.py`. `ladeBuehne()` haengt heute am selben
  `setInterval(ladeBuehne, __NACHLADEN_MS__)` wie der Stand-Panel-Poll (`web_vereint.NACHLADEN_MS`, eine Konstante,
  zweifach in `_VEREINT_JS` eingesetzt). Ein eigener, kuerzerer Takt nur fuer die Buehne ist technisch machbar
  (eine zweite Platzhalter-Konstante, ein zweiter `setInterval`), wurde aber **gepruft und bewusst nicht
  umgesetzt**: hoehere Serverlast im Mehrgruppenbetrieb gegen einen von Birk selbst als „Inspiration, kein hartes
  Muss" eingeordneten Punkt. Offen fuer eine eigene, kleine Karte, falls Birk den schnelleren Takt tatsaechlich
  will.
```

- [ ] **Step 3: Prüfen, dass die Markdown-Tabelle nicht zerbricht**

```bash
$PY -c "
import re
text = open('AGENTS.md', encoding='utf-8').read()
zeile = [l for l in text.splitlines() if l.startswith('| `begriffsboard.py`')]
assert len(zeile) == 1, zeile
assert zeile[0].count('|') >= 2, 'Tabellenzeile verloren ihre Spaltentrenner'
print('ok')
"
```

Expected: `ok` (die Modultabellenzeile bleibt eine einzige Zeile mit intakten `|`-Spaltentrennern — der neue Text
wird **innerhalb** der bestehenden Zelle angehängt, kein Zeilenumbruch in der Tabelle).

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "$(cat <<'EOF'
AGENTS.md: Design-Erweiterung Begriffsboard dokumentiert, zwei neue Uebergaben (t_cb2c4678, Design-Erweiterung Aufgabe 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Abschluss — volle Suite, beide e2e-Dateien, Bericht

**Files:** keine eigenen Änderungen (nur Prüfung + Bericht).

**Interfaces:** keine.

- [ ] **Step 1: Baseline-Zahl notieren (vor dieser Erweiterung, zum Vergleich)**

Bereits bekannt aus dem Brief: **7383 passed, 1 skipped, 4 deselected, EXIT 0** (Stand `05bfe5e`, vor Aufgabe 1
dieser Erweiterung). Diese Zahl geht unverändert in den Abschlussbericht als „vorher".

- [ ] **Step 2: Volle Suite laufen lassen (ohne e2e)**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
tail -5 .suite.log
```

Expected: `EXIT 0`, Zahl der `passed` mindestens `7383 + 9` (sechs neue/geänderte Testfunktionen aus Aufgabe 1–3:
1 geänderte Erwartung, 2 neue in Aufgabe 2, 1 neue in Aufgabe 3 — das Delta kann durch Testumbenennungen/-
Löschungen geringfügig abweichen; entscheidend ist `EXIT 0` und keine neuen `FAILED`-Zeilen gegenüber der
Baseline).

- [ ] **Step 3: Bei einem Fehlschlag: systematisch debuggen, nicht pauschal anpassen**

Tritt ein `FAILED` auf, das nicht in den Aufgaben 1–6 vorhergesehen ist: den genauen Testnamen und die
Fehlermeldung lesen, die betroffene Datei erneut mit dem passenden Task dieser Planung abgleichen (Diffs oben
sind wortgleich mit dem Ist-Stand bei Planbeginn — ein Konflikt deutet auf eine zwischenzeitliche Änderung an
derselben Stelle hin, nicht auf einen Fehler in diesem Plan). Erst danach gezielt nachbessern und erneut die
volle Suite laufen lassen. **Kein** `@pytest.mark.dortmund` auf einen Test setzen, der nicht nachweislich NUR an
einer Dortmund-/Vorgabe-Fixture scheitert.

- [ ] **Step 4: Beide Begriffsboard-e2e-Dateien gezielt laufen lassen**

```bash
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python
$E2E -m pytest tests/e2e/test_web_begriffsboard_ranking_e2e.py tests/e2e/test_web_begriffsboard_design_e2e.py -q
```

Expected: beide Dateien vollständig PASS (3 Tests insgesamt: 2 aus der angepassten Ranking-Datei, 1 aus der
neuen Design-Datei). `IT_SCHUSS_AKTUALISIEREN` bleibt bei diesem Lauf **ungesetzt** (beide Repository-Screenshots
stehen bereits fest — der „Vorher"-Screenshot aus Aufgabe 6 der ursprünglichen Karte, der „Nachher"-Screenshot
aus Aufgabe 5 dieser Erweiterung).

- [ ] **Step 5: Zwei Dortmund-Stichproben (kein Gate, nur Beleg für den Bericht)**

```bash
$PY -m scripts.pruefe_profil padua-2026
```

Expected: Exit 0 (Profilprüfung grün — diese Erweiterung führt keinen neuen Profilschalter ein und ändert keine
`profil.toml`).

- [ ] **Step 6: Abschlussbericht als letzte Textausgabe verfassen**

Enthält (siehe Vorgabe im Brief): Commit-SHAs aller sieben Aufgaben-Commits (`git log --oneline -8`), beide
Suite-Zeilen (`EXIT`-Zeile aus Baseline 05bfe5e und aus Schritt 2 dieser Aufgabe), die Pfade der zwei Screenshots
(`docs/web-begriffsboard/ranking-2026-10-04.png` als Vorher, `docs/web-begriffsboard/design-2026-10-04.png` als
Nachher), eine kurze Beschreibung der visuellen Änderung (kein Warum mehr, Rang-Marke + Trennlinie, kursives
Verworfen, Schärfungs-Steg) und jede Abweichung von diesem Plan (falls keine: das explizit so benennen). Kein
neuer Git-Commit für den Bericht selbst — er ist die letzte Textausgabe des Laufs, keine Datei.

---

## Self-Review (bereits durchgeführt beim Schreiben dieses Plans)

- **Spec-Abdeckung:** Birks drei Design-Punkte → Aufgabe 1 (kein Warum), Aufgabe 2+3 (Rang/Trennlinie/Schärfungs-
  Design + FLIP-Vereinfachung); Birks Punkt 4 (Taktung) → explizit geprüft und als Übergabe dokumentiert
  (Aufgabe 6, Global Constraints); Abnahme-Screenshots → Aufgabe 5 + 7; AGENTS.md → Aufgabe 6; Suite grün → Aufgabe
  7; Dortmund nicht löschen/neu erzeugen → Global Constraints, in keiner Aufgabe verletzt.
- **Platzhalter-Scan:** keine `TBD`/`TODO` in diesem Plan; jeder Code-Schritt zeigt vollständigen Vorher- UND
  Nachher-Code, keine „ähnlich wie Aufgabe N"-Verweise ohne Wiederholung des Codes.
- **Typkonsistenz:** `bbMerke`/`bbSpiele`-Signaturen (`bbMerke(panel)` → `{alt, lagen}`, `bbSpiele(panel, vorher)`)
  bleiben über Aufgabe 3 und die Bestandstests aus Aufgabe 2 der vorherigen Karte identisch; `_begriffsboard_html`
  behält Signatur und Rückgabetyp (`list[dict] -> str`); keine neue Funktion wird in einer Aufgabe mit einem Namen
  eingeführt und in einer späteren mit einem anderen erwartet.

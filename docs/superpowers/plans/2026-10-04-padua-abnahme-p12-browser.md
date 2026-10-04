# Padua-Abnahmelauf Phase 1–2 im Browser — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aus dem vorhandenen Browserlauf (`simulation/browser_lauf.py`) wird ein Abnahmelauf fuer Padua Phase 1–2 (inkl. Angebot von Phase 3) auf Handy (390×844) und Laptop (1440×900), mit den Personas Giulia und Priya, Mehrfachantworten, echtem Diskussionsaudio und einem zweiten, beobachtenden Geraet fuer das Begriffsboard im CoThinker-Tab. Am Ende stehen ein Bericht mit Urteil „Phase 1-2 abnahmebereit: ja|nein“, hoechstens 5 B-Befunde und Leitbilder fuer Birks Deck.

**Architecture:** Der bisherige Phasenmodus bleibt unveraendert. Daneben kommt ein Stationsmodus (`--stationen p12`). Er laeuft ueber eine Datenliste `simulation/browser_stationen.py` mit reinen Hilfsfunktionen (`muss_antworten`, `notweg_ziel`) und einen zweiten Browser-Kontext `simulation/browser_beobachter.py`. Das Audio wird offline erzeugt (`simulation/erzeuge_diskussion_audio.py`, espeak-ng ueber `espeakng_loader`) und per Chromium-Fake-Mikrofon eingespielt. Leitbilder (`simulation/browser_leitbilder.py`) entstehen nur im Schlusslauf, hinter einem getesteten Bildwaechter. Den Abnahmebericht baut `simulation/browser_abnahme.py` aus den `ergebnis.json` zweier Laeufe.

**Tech Stack:** Python 3.11, Playwright (sync, headless Chromium), SQLite read-only, `espeakng_loader` (nur Simulation, nie `interview_theater/`), pytest.

**Kanban:** Planungskarte t_b76ee5e2 → Umsetzungskarte t_0b702d1d. Branch: `padua-workshop/t_0b702d1d-padua-abnahmelauf-phase-1-2-im-browser-s`.

## Global Constraints

- Branch bleibt `padua-workshop/t_0b702d1d-…`. **Kein Merge nach main, kein Push.** Nach jedem Task ein Commit (nur die Dateien des Tasks, `git add <pfad>`).
- **Dortmund eingefroren seit 04.10.2026.** Abnahme nur: Suite gruen mit `-m "not dortmund"`, `pruefe_profil padua-2026` gruen. Rot nur wegen Dortmund → `@pytest.mark.dortmund`.
- Nur **erfundenes** Material (Persona-Texte, Diskussionsskript). Keine Tokens, URLs oder echten Namen, weder in Texten noch in Bildern.
- **Nie** `.env`-Dateien und nie etwas unter `betrieb/` lesen. Die Env-Datei geht nur als Pfad an ein Bash-Kindskript (Muster `browser_umgebung.bau_bot_skript`).
- `espeakng_loader` ist eine reine Dev-/Simulationsabhaengigkeit. Installiert wird sie nur ins venv `/mnt/HC_Volume_106183673/venvs/it-webtest`, die Tests nutzen `pytest.importorskip`. Kein Import in `interview_theater/`.
- Kein Pillow und keine andere Bildbibliothek hinzufuegen.
- Parallele Karten t_cb2c4678 (CoThinker-Design) und t_2b9d2cbe beruehren `web_vereint.py` und `begriffsboard.py`. Aenderungen dort nur, wenn winzig, sonst wird es ein B-Befund.
- Bezahlte Laeufe sind **controller-executed** (nie ein Subagent): hoechstens 4 echte Laeufe, harter Stopp bei Σ `aufruf.kosten_chf` > **1.50 CHF**. Handy und Laptop laufen **nacheinander** (AGENTS.md, Falle 8).
- Kommandos:
  - `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3` fuer Suite und reine Unit-Tests
  - `W=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python` fuer Playwright- und espeak-Tests sowie fuer die Laeufe
- Suite (auf das Ergebnis warten, nie im Hintergrund vergessen):
  `$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?` → `EXIT 0`, plus `$PY -m scripts.pruefe_profil padua-2026` → Exit 0.
- Alles, was beim Planen nicht selbst verifiziert wurde, traegt `ANNAHME:` plus die Pruefung.

## Dateikarte

| Datei | Aenderung | Verantwortung |
|---|---|---|
| `.gitignore` | Modify | Negation fuer `simulation/berichte/abnahme-p12-*.md` |
| `simulation/browser_persona.py` | Modify | Personas `giulia`, `priya`; `done_station`; `offene_fragen`; `hinweis=` |
| `simulation/browser_elemente.py` | Modify | `#diskussion*`, `#kalibrierung-*` sichtbar fuer die Persona |
| `simulation/browser_aktionen.py` | Modify | Tab per Anzeigetext → `data-tab` |
| `simulation/browser_zaehler.py` | Modify | neue Selektoren verdrahtet; `entwickler_meta` |
| `simulation/browser_stationen.py` | Create | `Station`, `STATIONEN_P12`, `muss_antworten`, `notweg_ziel` |
| `simulation/browser_mitschnitt.py` | Modify | `datenstand` + Kalibrier-/Diskussionszaehler; `schritt(station=)` |
| `simulation/browser_beobachter.py` | Create | zweites Geraet, Board-Zaehlung, Reload-Erkennung |
| `simulation/diskussion/p1-diskussion.txt` | Create | erfundene Diskussion (~3 min) |
| `simulation/erzeuge_diskussion_audio.py` | Create | Text → WAV (espeak-ng, deterministisch) |
| `simulation/browser_probe.py` | Create | billige Probe: Fake-Mikro, Whisper-Ausschnitt |
| `simulation/browser_lauf.py` | Modify | `fuehre_stationen`, CLI `--stationen`, Notweg-Waechter |
| `simulation/browser_leitbilder.py` | Create | Bildwaechter, Aufnahme, `index.json` |
| `simulation/browser_abnahme.py` | Create | Abnahmebericht, Urteil, Modellbeleg, Kostensumme |
| `simulation/ux_rubrik.md` | Modify | Hintergrund-Zuhoeren: Begriffsboard ist gewollt |
| `workshop/padua-2026/prompts/phasen/2.md` | Modify | Regel: nie ueber Code reden |
| `simulation/README.md` | Modify | Abschnitt „Der Abnahmelauf Phase 1–2“ |
| Tests | Create/Modify | je Task benannt |

---

### Task 0: Ausgangsbefund committen, Bericht freigeben

**Files:**
- Modify: `.gitignore:53-55`
- Add: `simulation/browser_berichte/2026-10-04-handy.md`, `simulation/browser_berichte/2026-10-04-laptop.md` (heute erzeugt, untracked)

**Interfaces:** keine.

- [ ] **Step 1: Pruefen, dass der Bericht heute ignoriert wuerde**

Run: `git check-ignore -q simulation/berichte/abnahme-p12-2026-10-04.md; echo $?`
Expected: `0` (ignoriert)

- [ ] **Step 2: Negation eintragen**, direkt unter `!simulation/berichte/verlauf.jsonl`:

```gitignore
!simulation/berichte/abnahme-p12-*.md
```

- [ ] **Step 3: Erneut pruefen**

Run: `git check-ignore -q simulation/berichte/abnahme-p12-2026-10-04.md; echo $?`
Expected: `1` (nicht mehr ignoriert)

- [ ] **Step 4: Commit**

```bash
git add .gitignore simulation/browser_berichte/2026-10-04-handy.md simulation/browser_berichte/2026-10-04-laptop.md
git commit -m "Abnahme P1-2: Ausgangslaeufe 04.10. als Startbefund, Abnahmebericht nicht mehr gitignored"
```

---

### Task 1: Personas Giulia und Priya, `offene_fragen`, Nachfrage-Hinweis (D1)

**Files:**
- Modify: `simulation/browser_persona.py`
- Modify: `simulation/browser_lauf.py` (nur `--persona choices`)
- Test: `tests/test_browser_persona.py`

**Interfaces:**
- Produces: `browser_persona.PERSONEN` mit Schluesseln `student`, `clicker`, `giulia`, `priya`.
- Produces: `naechste_aktion(client, persona_name, bild_png, elemente, phasenziel, verlaufszeilen, hinweis: str | None = None) -> dict`. Ist `hinweis` gesetzt, wird er als eigene Zeile an den Nutzertext angehaengt.
- Produces: `offene_fragen(aktion: dict) -> list[str]`, hoechstens 5 nicht-leere Strings, gekappt auf 200 Zeichen.
- Neuer Aktionstyp `done_station` (gleichwertig zu `done_phase`).

- [ ] **Step 1: Failing tests schreiben.** In `tests/test_browser_persona.py` die alte Mengenpruefung ersetzen und Neues anhaengen:

```python
def test_alle_vier_personas_existieren_und_unterscheiden_sich():
    assert set(p.PERSONEN) == {"student", "clicker", "giulia", "priya"}
    assert len(set(p.PERSONEN.values())) == 4


def test_priya_ist_erstnutzerin_ohne_push_to_talk():
    text = p.PERSONEN["priya"].lower()
    assert "never used push-to-talk" in text
    assert "ask" in text


def test_giulia_antwortet_auf_rueckfragen():
    assert "answer it in character" in p.PERSONEN["giulia"]


def test_hinweis_landet_im_nutzertext():
    client = _FakeClient({"type": "wait", "begruendung": "x"})
    p.naechste_aktion(client, "giulia", b"x", [], "ziel", [],
                      hinweis="The bot just asked you something. Answer it in character.")
    assert client.aufrufe[0]["nutzer"].rstrip().endswith(
        "The bot just asked you something. Answer it in character.")


def test_schema_nennt_done_station_und_offene_fragen():
    client = _FakeClient({"type": "wait", "begruendung": "x"})
    p.naechste_aktion(client, "priya", b"x", [], "ziel", [])
    system = client.aufrufe[0]["system"]
    assert "done_station" in system and "offene_fragen" in system


def test_offene_fragen_werden_bereinigt():
    aktion = {"offene_fragen": ["What is CoThinker?", "", 7, "x" * 300] + ["q"] * 9}
    fragen = p.offene_fragen(aktion)
    assert fragen[0] == "What is CoThinker?"
    assert all(isinstance(f, str) and f for f in fragen)
    assert len(fragen) == 5 and len(fragen[1]) == 200


def test_offene_fragen_fehlen_ergibt_leere_liste():
    assert p.offene_fragen({"type": "wait"}) == []
```

- [ ] **Step 2: Laufen lassen**

Run: `$PY -m pytest tests/test_browser_persona.py -q -p no:cacheprovider`
Expected: FAIL (`KeyError: 'priya'` / `AttributeError: offene_fragen`)

- [ ] **Step 3: Implementieren.** In `simulation/browser_persona.py`:

```python
PERSONEN["giulia"] = (
    "You are Giulia, a 23-year-old acting student in Padua taking part in an "
    "English-language theatre workshop (your English is B2). You are creative "
    "and impatient with forms, you bring your own ideas, you sometimes "
    "contradict a suggestion and then change your mind. You prefer typing "
    "full sentences over tapping buttons, but you tap a button when it is "
    "clearly the fastest way forward. When the bot asks your group a "
    "question, you answer it in character instead of walking away."
)
PERSONEN["priya"] = (
    "You are Priya, taking part in a theatre workshop. You have never used a "
    "chatbot for group work and you have never used push-to-talk. Your "
    "English is hesitant: short, simple sentences, now and then a small "
    "mistake. You read everything on the screen before you act. When you "
    "are not sure what a button does, you do not guess -- you ask the bot in "
    "a short message. When the bot asks you something, you answer it."
)
```

(Als Dict-Literal-Eintraege in `PERSONEN` einfuegen, nicht als Zuweisung danach.) In `_SYSTEM_RAHMEN` den Typ und ein Feld ergaenzen:

```
{{"type": "click" | "type_send" | "tab" | "phase" | "ptt" | "wait" | "done_phase" | "done_station",
 ...
 "offene_fragen": <optional list of short strings: what a first-time user would still wonder about on this screen; [] if nothing>,
 "begruendung": ...}}

Use "done_station" (or "done_phase") once you believe the current goal is complete.
```

Neue Funktion und Parameter:

```python
def offene_fragen(aktion: dict) -> list[str]:
    roh = aktion.get("offene_fragen") if isinstance(aktion, dict) else None
    if not isinstance(roh, list):
        return []
    return [f.strip()[:200] for f in roh if isinstance(f, str) and f.strip()][:5]


def naechste_aktion(client, persona_name, bild_png, elemente, phasenziel,
                    verlaufszeilen, hinweis: str | None = None) -> dict:
    system = _SYSTEM_RAHMEN.format(persona=PERSONEN[persona_name])
    nutzer = baue_nutzertext(elemente, phasenziel, verlaufszeilen)
    if hinweis:
        nutzer += f"\n\n{hinweis}"
    ...  # Rest unveraendert
```

In `browser_lauf.main`: `choices=sorted(browser_persona.PERSONEN)`.

- [ ] **Step 4: Gruen**

Run: `$PY -m pytest tests/test_browser_persona.py -q -p no:cacheprovider`
Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_persona.py simulation/browser_lauf.py tests/test_browser_persona.py
git commit -m "Browserlauf: Personas Giulia und Priya, offene_fragen, Nachfrage-Hinweis"
```

---

### Task 2: Die Persona sieht Zuhoeren und Kalibrierung; Tab per Anzeigetext (D6 Klasse A)

Befund beim Planen (verifiziert): `browser_elemente._ARTEN` kennt weder `#diskussion`/`#diskussion-pause`/`#diskussion-beenden` noch die `#kalibrierung-*`-Knoepfe (IDs in `interview_theater/web_chat.py`). „Start listening“ fehlte also in der Elementliste der Persona. Das erklaert, warum sie in den Baselines die Begriffe tippte. Laptop-Baseline: `tab` mit Anzeigetext lief in einen Timeout.

**Files:**
- Modify: `simulation/browser_elemente.py` (`_ARTEN`)
- Modify: `simulation/browser_zaehler.py` (`VERDRAHTETE_SELEKTOREN`)
- Modify: `simulation/browser_aktionen.py` (`fuehre_aus`, Zweig `tab`)
- Test: `tests/test_browser_elemente.py`, `tests/test_browser_aktionen.py`

**Interfaces:**
- Produces: neue Elementarten `diskussion`, `diskussion_pause`, `diskussion_beenden`, `kalibrierung_start`, `kalibrierung_sprechen`, `kalibrierung_ja`, `kalibrierung_nein`, `kalibrierung_versuch`, `kalibrierung_weiter`, `kalibrierung_nochmal`, `kalibrierung_skip`.
- Produces: `browser_aktionen._tab_wert(page, name: str) -> str`: `data-tab`-Wert zu einem Wert **oder** einem Anzeigetext (casefold, getrimmt, auch Praefix). Ohne Treffer bleibt `name` unveraendert.

- [ ] **Step 1: Failing tests.** In `tests/test_browser_elemente.py`:

```python
_FIXTURE_ZUHOEREN = """
<button id="diskussion" data-laeuft="0">Start listening</button>
<button id="diskussion-beenden">Discussion done</button>
<div id="kalibrierung"><button id="kalibrierung-start">Start check</button>
<button id="kalibrierung-skip">Skip</button></div>
"""


def test_zuhoeren_und_kalibrierung_stehen_in_der_elementliste():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(_FIXTURE_ZUHOEREN)
        arten = {e["art"] for e in browser_elemente.extrahiere(page)}
        b.close()
    assert {"diskussion", "diskussion_beenden", "kalibrierung_start",
            "kalibrierung_skip"} <= arten
```

In `tests/test_browser_aktionen.py` (die Fixture enthaelt schon `<button data-tab="stand">Status</button>`):

```python
def test_tab_per_anzeigetext_trifft_den_data_tab(seite):
    protokoll = a.fuehre_aus(seite, {"type": "tab", "name": "Status"})
    assert protokoll == {"art": "tab", "ziel": "stand"}


def test_tab_per_data_tab_bleibt_unveraendert(seite):
    assert a.fuehre_aus(seite, {"type": "tab", "name": "stand"})["ziel"] == "stand"
```

- [ ] **Step 2: Rot**

Run: `$W -m pytest tests/test_browser_elemente.py tests/test_browser_aktionen.py -q -p no:cacheprovider`
Expected: FAIL (fehlende Arten; Timeout bzw. `ziel == "Status"`)

- [ ] **Step 3: Implementieren.** `_ARTEN` vor `("link", "a[href]")` ergaenzen:

```python
    ("diskussion", "#diskussion"),
    ("diskussion_pause", "#diskussion-pause"),
    ("diskussion_beenden", "#diskussion-beenden"),
    ("kalibrierung_start", "#kalibrierung-start"),
    ("kalibrierung_sprechen", "#kalibrierung-sprechen"),
    ("kalibrierung_ja", "#kalibrierung-ja"),
    ("kalibrierung_nein", "#kalibrierung-nein"),
    ("kalibrierung_versuch", "#kalibrierung-versuch"),
    ("kalibrierung_weiter", "#kalibrierung-weiter-trotzdem"),
    ("kalibrierung_nochmal", "#kalibrierung-nochmal-hoeren"),
    ("kalibrierung_skip", "#kalibrierung-skip"),
```

Dieselben Selektoren in `browser_zaehler.VERDRAHTETE_SELEKTOREN` aufnehmen. In `browser_aktionen`:

```python
def _tab_wert(page, name: str) -> str:
    tabs = page.eval_on_selector_all(
        ".tabs button",
        "els => els.map(e => ({tab: e.dataset.tab || '', text: (e.innerText || '').trim()}))",
    )
    gesucht = (name or "").strip().casefold()
    for t in tabs:
        if t["tab"] == name:
            return name
    for t in tabs:
        text = t["text"].casefold()
        if t["tab"] and (text == gesucht or text.startswith(gesucht)):
            return t["tab"]
    return name
```

Zweig `tab`: `wert = _tab_wert(page, aktion["name"])`, dann `page.click(f'.tabs button[data-tab="{wert}"]')`, Rueckgabe `{"art": "tab", "ziel": wert}`.

- [ ] **Step 4: Gruen**

Run: `$W -m pytest tests/test_browser_elemente.py tests/test_browser_aktionen.py tests/test_browser_lauf_zaehler.py -q -p no:cacheprovider`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_elemente.py simulation/browser_zaehler.py simulation/browser_aktionen.py tests/test_browser_elemente.py tests/test_browser_aktionen.py
git commit -m "Browserlauf: Start listening und Kalibrierung fuer die Persona sichtbar, Tab per Anzeigetext"
```

---

### Task 3: Stationen als Daten, Mehrfachantwort, Notweg-Waechter (D2, D3, D6)

**Files:**
- Create: `simulation/browser_stationen.py`
- Modify: `simulation/browser_mitschnitt.py` (`datenstand`, `Mitschnitt.schritt`)
- Test: `tests/test_browser_stationen.py`, `tests/test_browser_mitschnitt.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class Station:
    schluessel: str
    phase: int
    ziel: str                                   # englischer Zieltext fuer die Persona
    fertig: Callable[[dict], bool] | None = None   # ueber browser_mitschnitt.datenstand
    budget: int = 8
    zuhoeren_s: int = 0                         # >0: Harness wartet, solange #diskussion laeuft
    endet_bei_phasenwechsel: bool = False
    leitbild_anfang: str | None = None
    leitbild_mitte: str | None = None           # erster Bildschirm mit .leiste-Knopf bzw. waehrend des Zuhoerens
    leitbild_ende: str | None = None
    leitbild_tab: str | None = None             # Tab fuer leitbild_ende (z. B. "stand"), danach zurueck auf "chat"
    leitbild_beobachter: str | None = None      # Bild vom zweiten Geraet am Stationsende

STATIONEN_P12: tuple[Station, ...]
STATIONEN: dict[str, tuple[Station, ...]]        # {"p12": STATIONEN_P12}
MAX_NACHFRAGEN = 3
HINWEIS_NACHFRAGE = "The bot just asked you something. Answer it in character."
HINWEIS_DISKUSSION_ENDE = "Your group has finished discussing. Press 'Discussion done' now."
def muss_antworten(blasen: list[dict], beantwortet: int) -> bool
def notweg_ziel(station_phase: int, aktive_phase: int | None) -> int | None
```

- `blasen`: Dicts `{"von": "bot"|"gruppe"|…, "typ": "text"|"system"|"transkript"|…, "text": str}` (Klassen `blase <von> <typ>`, `web_chat.py:972/3720`).
- Produces: `datenstand` bekommt zusaetzlich `kalibrierung_aufnahmen` und `diskussion_aufnahmen` (int), `kalibrierung_modus` (str|None). `Mitschnitt.schritt(..., station: str | None = None)` schreibt `"station"` in die JSONL-Zeile.

- [ ] **Step 1: Failing tests** `tests/test_browser_stationen.py`:

```python
from simulation import browser_stationen as s


def _b(von, text, typ="text"):
    return {"von": von, "typ": typ, "text": text}


def test_bot_fragt_zuletzt_also_antworten():
    assert s.muss_antworten([_b("gruppe", "hi"), _b("bot", "Which terms matter most?")], 0)


def test_systemzeilen_zaehlen_nicht():
    blasen = [_b("bot", "Which one?"), _b("bot", "📌 Saved.", "system"),
              _b("bot", "Interview 1", "transkript")]
    assert s.muss_antworten(blasen, 0)


def test_ohne_fragezeichen_oder_gruppe_zuletzt_nicht():
    assert not s.muss_antworten([_b("bot", "Saved your terms.")], 0)
    assert not s.muss_antworten([_b("bot", "Which?"), _b("gruppe", "home")], 0)
    assert not s.muss_antworten([], 0)


def test_hoechstens_drei_nachfragen():
    assert s.muss_antworten([_b("bot", "And?")], 2)
    assert not s.muss_antworten([_b("bot", "And?")], 3)


def test_notweg_nie_rueckwaerts_nie_doppelt():
    assert s.notweg_ziel(1, 1) == 2
    assert s.notweg_ziel(1, 2) is None      # schon da: kein zweiter Phasentext
    assert s.notweg_ziel(1, 3) is None      # nie zurueck
    assert s.notweg_ziel(1, None) is None   # unbekannt: nichts anfassen


def test_stationen_p12_vollstaendig_und_geordnet():
    schluessel = [st.schluessel for st in s.STATIONEN["p12"]]
    assert schluessel == [
        "p1-eintritt", "p1-kalibrierung", "p1-zuhoeren", "p1-begriffe",
        "p1-uebergang", "p2-eigene-fragen", "p2-ab-vergleich",
        "p2-einzeldurchgang", "p2-eroeffnung", "p2-uebergang"]
    phasen = [st.phase for st in s.STATIONEN_P12]
    assert phasen == sorted(phasen) and set(phasen) == {1, 2}
    zuhoeren = next(st for st in s.STATIONEN_P12 if st.schluessel == "p1-zuhoeren")
    assert zuhoeren.zuhoeren_s >= 120          # brainstorm: 1200 Zeichen / 90 s
    assert "Start listening" in zuhoeren.ziel and "do not type" in zuhoeren.ziel


def test_praedikate_ueber_datenstand():
    st = {x.schluessel: x for x in s.STATIONEN_P12}
    leer = {"arbeitsstand": {}, "kalibrierung_aufnahmen": 0, "diskussion_aufnahmen": 0}
    voll = {"arbeitsstand": {"begriffe": "home, border", "begriffe_detail": "[...]",
                             "phase": 2, "phase_angeboten": 3, "fragen": "x",
                             "fragen_eigene_vorschlag": "x", "fragen_ki_vorschlag": "x",
                             "interview_eroeffnung": "x", "interview_abschluss": "x"},
            "kalibrierung_aufnahmen": 1, "diskussion_aufnahmen": 4}
    for x in s.STATIONEN_P12:
        if x.fertig:
            assert not x.fertig(leer), x.schluessel
            assert x.fertig(voll), x.schluessel
```

In `tests/test_browser_mitschnitt.py` (vorhandene Fixture-Art nutzen: DB mit `db.initialisiere`, eine Gruppe):

```python
def test_datenstand_zaehlt_kalibrierung_und_diskussion(tmp_path):
    from interview_theater import db, repo
    from simulation import browser_mitschnitt as m
    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad); db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_777, "g", "G"); conn.commit(); conn.close()
    stand = m.datenstand(pfad, 7_000_000_000_777)
    assert stand["kalibrierung_aufnahmen"] == 0
    assert stand["diskussion_aufnahmen"] == 0
    assert "kalibrierung_modus" in stand


def test_schritt_schreibt_die_station(tmp_path):
    import json
    from simulation import browser_mitschnitt as m
    ms = m.Mitschnitt(tmp_path, "l", "handy")
    ms.schritt(phase=1, screenshot_vorher=tmp_path / "a.png",
               screenshot_nachher=tmp_path / "b.png", elemente=[], aktion={},
               begruendung="", antwort={}, db_diff={}, station="p1-eintritt")
    assert json.loads(ms.jsonl_pfad.read_text())["station"] == "p1-eintritt"
```

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_browser_stationen.py tests/test_browser_mitschnitt.py -q -p no:cacheprovider`
Expected: FAIL (`ModuleNotFoundError: simulation.browser_stationen`)

- [ ] **Step 3: Implementieren.** `simulation/browser_stationen.py`, Modulkopf im Stil der anderen `browser_*`-Module, dann:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

MAX_NACHFRAGEN = 3
HINWEIS_NACHFRAGE = "The bot just asked you something. Answer it in character."
HINWEIS_DISKUSSION_ENDE = "Your group has finished discussing. Press 'Discussion done' now."
_NICHT_GESPRAECH = ("system", "transkript")


@dataclass(frozen=True)
class Station:
    schluessel: str
    phase: int
    ziel: str
    fertig: Callable[[dict], bool] | None = None
    budget: int = 8
    zuhoeren_s: int = 0
    endet_bei_phasenwechsel: bool = False
    leitbild_anfang: str | None = None
    leitbild_mitte: str | None = None
    leitbild_ende: str | None = None
    leitbild_tab: str | None = None
    leitbild_beobachter: str | None = None


def _feld(stand: dict, name: str):
    return (stand.get("arbeitsstand") or {}).get(name)


def muss_antworten(blasen: list[dict], beantwortet: int) -> bool:
    if beantwortet >= MAX_NACHFRAGEN:
        return False
    for blase in reversed(blasen):
        if blase.get("typ") in _NICHT_GESPRAECH:
            continue
        if blase.get("von") != "bot":
            return False
        return (blase.get("text") or "").rstrip().endswith("?")
    return False


def notweg_ziel(station_phase: int, aktive_phase: int | None) -> int | None:
    ziel = station_phase + 1
    if aktive_phase is None or aktive_phase >= ziel:
        return None
    return ziel


STATIONEN_P12: tuple[Station, ...] = (
    Station("p1-eintritt", 1,
            "You just opened the app with your group for the first time. Read "
            "the screen, say hello, and find out what this first phase is about.",
            budget=4, leitbild_ende="eintritt"),
    Station("p1-kalibrierung", 1,
            "The app wants to check the microphone before you start. Follow the "
            "microphone check on screen: start it, let it listen, confirm. If it "
            "fails twice, skip it.",
            fertig=lambda s: s.get("kalibrierung_aufnahmen", 0) > 0
            or bool(s.get("kalibrierung_modus")),
            budget=6, leitbild_mitte="kalibrierung"),
    Station("p1-zuhoeren", 1,
            "Your group now discusses which terms matter for your play. Press "
            "'Start listening' and put the phone down in the middle of the table "
            "-- do not type the terms. When you are told the discussion is over, "
            "press 'Discussion done'.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            budget=6, zuhoeren_s=180, leitbild_mitte="zuhoeren"),
    Station("p1-begriffe", 1,
            "The bot proposes terms from your discussion. Save them with the "
            "button, then undo that once with the Undo button, then save them again.",
            fertig=lambda s: bool(_feld(s, "begriffe")) and bool(_feld(s, "begriffe_detail")),
            budget=10, leitbild_beobachter="cothinker"),
    Station("p1-uebergang", 1,
            "Your terms are saved. Move on to the next phase the way the app offers it.",
            fertig=lambda s: (_feld(s, "phase") or 1) >= 2,
            budget=4, endet_bei_phasenwechsel=True, leitbild_ende="uebergang"),
    Station("p2-eigene-fragen", 2,
            "Write your own interview questions for your terms as a group, at "
            "least four, in the chat.",
            fertig=lambda s: bool(_feld(s, "fragen_eigene_vorschlag")),
            budget=10, leitbild_anfang="eintritt"),
    Station("p2-ab-vergleich", 2,
            "The app compares your questions with the AI's questions. Look at "
            "the comparison and react to it.",
            fertig=lambda s: bool(_feld(s, "fragen_ki_vorschlag")), budget=6),
    Station("p2-einzeldurchgang", 2,
            "Go through the questions one by one: accept some, drop one, rework one.",
            fertig=lambda s: bool(_feld(s, "fragen")),
            budget=14, leitbild_mitte="arbeit"),
    Station("p2-eroeffnung", 2,
            "Agree on how you open and how you close your interviews.",
            fertig=lambda s: bool(_feld(s, "interview_eroeffnung"))
            and bool(_feld(s, "interview_abschluss")),
            budget=8, leitbild_ende="ergebnis", leitbild_tab="stand"),
    Station("p2-uebergang", 2,
            "Check whether the app now offers you the next phase (interviews). "
            "Do not start an interview yet.",
            fertig=lambda s: (_feld(s, "phase_angeboten") or 0) >= 3
            or (_feld(s, "phase") or 2) >= 3,
            budget=3, leitbild_ende="uebergang"),
)

STATIONEN: dict[str, tuple[Station, ...]] = {"p12": STATIONEN_P12}
```

Hinweis: `p1-eintritt` hat kein Praedikat (Absicht) und gilt damit als erreicht.

`browser_mitschnitt.datenstand` im `try` vor dem `return` ergaenzen (read-only Verbindung, wie `_modell_lesen` in `browser_lauf`):

```python
        zahl = lambda sql: conn.execute(sql, (chat_id,)).fetchone()[0]
        kalibrierung = zahl("SELECT COUNT(*) FROM aufnahme WHERE chat_id = ? AND kalibrierung = 1")
        diskussion = zahl("SELECT COUNT(*) FROM aufnahme WHERE chat_id = ? AND diskussion = 1")
        zeile = conn.execute("SELECT kalibrierung_modus FROM gruppe WHERE chat_id = ?",
                             (chat_id,)).fetchone()
```

Danach `"kalibrierung_aufnahmen": kalibrierung, "diskussion_aufnahmen": diskussion, "kalibrierung_modus": zeile[0] if zeile else None` ins Rueckgabe-Dict. `unterschied` bekommt beide Zaehler zusaetzlich in die Namensschleife. `Mitschnitt.schritt` nimmt `station: str | None = None` und schreibt `"station": station`.

`ANNAHME:` `aufnahme.diskussion` und `aufnahme.kalibrierung` sind INTEGER-Spalten (`interview_theater/db.py:205/1163`, `begriffsboard.py`-Kopf). Pruefen mit `grep -n "  diskussion \|  kalibrierung " interview_theater/db.py`.

- [ ] **Step 4: Gruen**

Run: `$PY -m pytest tests/test_browser_stationen.py tests/test_browser_mitschnitt.py -q -p no:cacheprovider`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_stationen.py simulation/browser_mitschnitt.py tests/test_browser_stationen.py tests/test_browser_mitschnitt.py
git commit -m "Browserlauf: Stationen P1-2 als Daten, Nachfrageregel, Notweg nie rueckwaerts"
```

---

### Task 4: Das zweite Geraet — Beobachter im CoThinker-Tab (D4)

**Files:**
- Create: `simulation/browser_beobachter.py`
- Test: `tests/test_browser_beobachter.py`

**Interfaces:**
- Produces:

```python
HANDY_PROFIL = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
class Beobachter:
    page: Page
    verlauf: list[int]
    @classmethod
    def oeffne(cls, browser, url: str) -> "Beobachter"   # eigener Context, Tab buehne, Marke setzen
    def messe(self) -> int                                 # li[data-begriff] zaehlen, an verlauf haengen
    @property
    def neu_geladen(self) -> bool
    def ergebnis(self) -> dict  # {"board_verlauf", "beobachter_neu_geladen", "board_bestanden"}
    def schliesse(self) -> None
```

Abweichung von D4, mit Grund: `framenavigated` feuert auch bei Hash-Navigation, und der Tabwechsel setzt `#buehne`. Erkannt wird ein Neuladen deshalb ueber eine Fenster-Marke (`window.__beobachterMarke`), die ein Reload loescht. Gezaehlt werden zusaetzlich die Hauptframe-Navigationen mit **anderem Pfad oder gleicher URL** (`navigationen`, nur fuers Protokoll). `board_bestanden = max(verlauf) > 0 and not neu_geladen`.

- [ ] **Step 1: Failing test** (`page.route` liefert die Seite, kein Server noetig):

```python
import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_beobachter as bb  # noqa: E402

_SEITE = """<!doctype html><nav class="tabs">
<button data-tab="chat">Chat</button><button data-tab="buehne">CoThinker</button></nav>
<ol class="begriffsboard"></ol>
<script>
document.querySelector('[data-tab=buehne]').onclick = () => { location.hash = 'buehne'; };
setTimeout(() => { document.querySelector('.begriffsboard').innerHTML =
  '<li data-begriff="home">home</li><li data-begriff="border">border</li>'; }, 400);
</script>"""


@pytest.fixture()
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _route(context):
    context.route("http://sim.test/**", lambda r: r.fulfill(
        status=200, content_type="text/html", body=_SEITE))


def test_board_waechst_ohne_reload(browser, monkeypatch):
    monkeypatch.setattr(bb, "_vor_goto", _route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    beob.messe()  # je nach Timing 0 oder 2
    beob.page.wait_for_timeout(700)
    assert beob.messe() == 2
    ergebnis = beob.ergebnis()
    assert ergebnis["board_bestanden"] is True
    assert ergebnis["beobachter_neu_geladen"] is False
    beob.schliesse()


def test_reload_wird_erkannt(browser, monkeypatch):
    monkeypatch.setattr(bb, "_vor_goto", _route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    beob.page.reload()
    assert beob.neu_geladen is True
    assert beob.ergebnis()["board_bestanden"] is False
    beob.schliesse()
```

- [ ] **Step 2: Rot**

Run: `$W -m pytest tests/test_browser_beobachter.py -q -p no:cacheprovider`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren**

```python
"""Das zweite Geraet im Abnahmelauf P1-2 (04.10.2026): ein Handy, das nur
zuschaut. Es oeffnet dieselbe Gruppen-URL, wechselt einmal in den
CoThinker-Tab und wird nie neu geladen -- gemessen wird, ob das
Begriffsboard dort von selbst waechst (Karte t_4517d4ad). Kein Modell, keine
Persona."""

from __future__ import annotations

HANDY_PROFIL = {"viewport": {"width": 390, "height": 844},
                "is_mobile": True, "has_touch": True}
BOARD_SELEKTOR = "li[data-begriff]"
_TAB = '.tabs button[data-tab="buehne"]'


def _vor_goto(context) -> None:
    """Einhaengepunkt fuer Tests (``page.route``); im Lauf leer."""


class Beobachter:
    def __init__(self, context, page):
        self.context = context
        self.page = page
        self.verlauf: list[int] = []

    @classmethod
    def oeffne(cls, browser, url: str) -> "Beobachter":
        context = browser.new_context(**HANDY_PROFIL)
        _vor_goto(context)
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector(".tabs")
        page.click(_TAB)
        page.wait_for_timeout(300)
        page.evaluate("window.__beobachterMarke = 1")
        return cls(context, page)

    def messe(self) -> int:
        anzahl = self.page.locator(BOARD_SELEKTOR).count()
        self.verlauf.append(anzahl)
        return anzahl

    @property
    def neu_geladen(self) -> bool:
        return not self.page.evaluate("window.__beobachterMarke === 1")

    def ergebnis(self) -> dict:
        neu = self.neu_geladen
        return {"board_verlauf": list(self.verlauf),
                "beobachter_neu_geladen": neu,
                "board_bestanden": bool(self.verlauf) and max(self.verlauf) > 0 and not neu}

    def schliesse(self) -> None:
        self.context.close()
```

`ANNAHME:` `li[data-begriff]` ueberlebt die Designkarte t_cb2c4678. Pruefen in Task 6 Step 1.

- [ ] **Step 4: Gruen**

Run: `$W -m pytest tests/test_browser_beobachter.py -q -p no:cacheprovider`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_beobachter.py tests/test_browser_beobachter.py
git commit -m "Browserlauf: zweites Geraet beobachtet das Begriffsboard ohne Reload"
```

---

### Task 5: Erfundene Diskussion und Offline-Audio (D5)

**Files:**
- Create: `simulation/diskussion/p1-diskussion.txt`
- Create: `simulation/erzeuge_diskussion_audio.py`
- Test: `tests/test_diskussion_audio.py`

**Interfaces:**
- Produces: `lies_skript(pfad: Path) -> list[tuple[str, str]]` (Sprecher, Text). Zeilen `A: …`, Leerzeilen und `#`-Kommentare werden ignoriert.
- Produces: `plane(zeilen) -> list[tuple[str, str, float]]` (Stimme, Text, Pause danach in s). Deterministisch, Pausen 1.5–3.0 s.
- Produces: `erzeuge(skript: Path, ziel: Path) -> float` (Sekunden Audio). Schreibt eine WAV-Datei, 16 bit mono, Rate von espeak.
- Produces: `STIMMEN = {"A": "en-gb+m3", "B": "en-us+f2", "C": "en-gb+f4", "D": "en-us+m5"}`.
- Produces: CLI `python -m simulation.erzeuge_diskussion_audio <ziel.wav>`.

- [ ] **Step 1: Skript anlegen** `simulation/diskussion/p1-diskussion.txt` (frei erfunden, keine Namen):

```text
# Erfundene Begriffsdiskussion fuer den Abnahmelauf P1-2 (04.10.2026).
# Vier Stimmen A-D, keine Namen. Begriffe wiederholen sich absichtlich:
# home, border, waiting, noise, night shift, belonging, language.
A: Okay, so what is our play about? I keep thinking about home. Not a house, but the feeling of home.
B: Home, yes. But for a lot of people in this city home is on the other side of a border.
C: Border is a strong word. A border can be a line on a map or a line between two people at the same table.
D: I would add waiting. Everybody I know is waiting for something. A paper, a call, a train, a reply.
A: Waiting is good. Waiting and home together. Waiting for home.
B: What about noise? When I think of the station at night there is so much noise, and still nobody talks.
C: Noise, okay. And the night shift. My cousin works the night shift in a bakery, and she says the night shift is its own country.
D: The night shift as a country, I love that. A country with its own language.
A: Language is important. Half of us speak two languages at home and another one outside.
B: So: home, border, waiting, noise, night shift, language. Is belonging something different from home?
C: Belonging is when other people say you are part of it. Home is when you say it yourself.
D: Then belonging is the harder one. You can have a home and still no belonging.
A: I want belonging on the list. And home. Those two fight with each other.
B: Border too. The border is where home and belonging stop agreeing.
C: I am not sure about noise. Is noise a term or just a picture?
D: For me noise is a term. Noise is what you hear when nobody listens to you.
A: Okay, noise stays. Waiting stays as well, I think waiting is the engine of every scene.
B: The night shift could be our place. Everything happens during one night shift.
C: Then language is how the characters talk across the border, or how they fail to.
D: So the strongest ones are home, belonging, border, waiting and the night shift.
A: And language and noise as the background.
B: Home first. Then belonging. Then border. Then waiting. Then the night shift.
C: Agreed. Home, belonging, border, waiting, night shift.
D: Good. I think that is our list for now.
```

- [ ] **Step 2: Failing tests** `tests/test_diskussion_audio.py`:

```python
import wave
from pathlib import Path

import pytest

from simulation import erzeuge_diskussion_audio as e

SKRIPT = Path("simulation/diskussion/p1-diskussion.txt")


def test_skript_hat_vier_sprecher_und_genug_text():
    zeilen = e.lies_skript(SKRIPT)
    assert {s for s, _ in zeilen} == {"A", "B", "C", "D"}
    text = " ".join(t for _, t in zeilen)
    assert len(text) >= 1200                       # brainstorm.VORGABE_MIN_ZEICHEN
    for begriff in ("home", "border", "waiting", "belonging", "night shift"):
        assert text.lower().count(begriff) >= 3


def test_plan_ist_deterministisch_mit_pausen():
    zeilen = e.lies_skript(SKRIPT)
    plan1, plan2 = e.plane(zeilen), e.plane(zeilen)
    assert plan1 == plan2
    assert all(1.5 <= pause <= 3.0 for _, _, pause in plan1)
    assert {stimme for stimme, _, _ in plan1} == set(e.STIMMEN.values())


def test_erzeugt_eine_wav_von_mindestens_zwei_minuten(tmp_path):
    pytest.importorskip("espeakng_loader")
    ziel = tmp_path / "d.wav"
    sekunden = e.erzeuge(SKRIPT, ziel)
    assert sekunden >= 120
    with wave.open(str(ziel)) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert abs(w.getnframes() / w.getframerate() - sekunden) < 0.5
```

- [ ] **Step 3: Rot**

Run: `$PY -m pytest tests/test_diskussion_audio.py -q -p no:cacheprovider`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: Implementieren.** `simulation/erzeuge_diskussion_audio.py`:

```python
"""Erzeugt die Diskussions-WAV fuer den Abnahmelauf P1-2 offline mit
espeak-ng (PyPI ``espeakng_loader``, bringt libespeak-ng und Daten mit).
Kein Netz-TTS: von diesem Rechner ist keins erreichbar (edge-tts lief am
04.10.2026 in den Timeout). Nur Simulation -- nie aus ``interview_theater/``
importieren. Ausgabe gehoert ins gitignorte Laufverzeichnis."""

from __future__ import annotations

import ctypes
import sys
import wave
from pathlib import Path

STIMMEN = {"A": "en-gb+m3", "B": "en-us+f2", "C": "en-gb+f4", "D": "en-us+m5"}
_AUDIO_OUTPUT_SYNCHRONOUS = 0x02
_POS_CHARACTER = 1
_ESPEAK_CHARS_UTF8 = 1
_ESPEAK_RATE = 1
_WOERTER_JE_MINUTE = 150
_PAUSEN = (1.5, 2.25, 3.0, 1.8, 2.6)


def lies_skript(pfad: Path) -> list[tuple[str, str]]:
    zeilen = []
    for roh in Path(pfad).read_text(encoding="utf-8").splitlines():
        roh = roh.strip()
        if not roh or roh.startswith("#") or ":" not in roh:
            continue
        sprecher, text = roh.split(":", 1)
        zeilen.append((sprecher.strip(), text.strip()))
    return zeilen


def plane(zeilen: list[tuple[str, str]]) -> list[tuple[str, str, float]]:
    return [(STIMMEN[s], t, _PAUSEN[i % len(_PAUSEN)]) for i, (s, t) in enumerate(zeilen)]


def _espeak():
    import espeakng_loader

    lib = ctypes.cdll.LoadLibrary(str(espeakng_loader.get_library_path()))
    rate = lib.espeak_Initialize(_AUDIO_OUTPUT_SYNCHRONOUS, 0,
                                 str(espeakng_loader.get_data_path()).encode(), 0)
    if rate <= 0:
        raise RuntimeError("espeak_Initialize fehlgeschlagen")
    return lib, rate


def erzeuge(skript: Path, ziel: Path) -> float:
    lib, rate = _espeak()
    puffer: list[bytes] = []
    callback_typ = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                    ctypes.c_int, ctypes.c_void_p)

    def _sammle(wav, anzahl, _ereignisse):
        if wav and anzahl > 0:
            puffer.append(ctypes.string_at(wav, anzahl * 2))
        return 0

    rueckruf = callback_typ(_sammle)       # Referenz halten, sonst GC
    lib.espeak_SetSynthCallback(rueckruf)
    lib.espeak_SetParameter(_ESPEAK_RATE, _WOERTER_JE_MINUTE, 0)
    frames = bytearray()
    for stimme, text, pause in plane(lies_skript(skript)):
        lib.espeak_SetVoiceByName(stimme.encode())
        puffer.clear()
        roh = text.encode("utf-8") + b"\0"
        lib.espeak_Synth(roh, len(roh), 0, _POS_CHARACTER, 0, _ESPEAK_CHARS_UTF8, None, None)
        frames += b"".join(puffer) + b"\0\0" * int(rate * pause)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ziel), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return len(frames) / 2 / rate


if __name__ == "__main__":
    ziel = Path(sys.argv[1])
    sekunden = erzeuge(Path(__file__).parent / "diskussion" / "p1-diskussion.txt", ziel)
    print(f"{ziel}: {sekunden:.1f} s")
```

`ANNAHME:` `espeakng_loader` stellt `get_library_path()` und `get_data_path()` bereit (Architekt-Probe nannte nur „lib + data path“). Pruefen: `$W -c "import espeakng_loader as l; print(l.get_library_path(), l.get_data_path())"`. Fehlt das Paket: `$W -m pip install espeakng_loader`. Liegt die Sprechdauer bei 150 wpm unter 120 s, `_WOERTER_JE_MINUTE` auf 130 senken (der Test sagt es).

- [ ] **Step 5: Gruen** (beide venvs: ohne espeak wird uebersprungen, mit espeak erzeugt)

Run: `$PY -m pytest tests/test_diskussion_audio.py -q -p no:cacheprovider && $W -m pytest tests/test_diskussion_audio.py -q -p no:cacheprovider`
Expected: `2 passed, 1 skipped`, dann `3 passed`

- [ ] **Step 6: Commit**

```bash
git add simulation/diskussion/p1-diskussion.txt simulation/erzeuge_diskussion_audio.py tests/test_diskussion_audio.py
git commit -m "Browserlauf: erfundene Begriffsdiskussion als Offline-Audio (espeak-ng)"
```

---

### Task 6: Billige Probe — Fake-Mikrofon, Whisper, Selektor, Leerzustand (controller-executed, ≤ 1 Whisper-Minute ≈ 0.006 CHF, kein LLM)

Prueft die ANNAHMEN aus D4/D5/D6, bevor der Stationsmodus gebaut wird. Was hier scheitert, wird dokumentiert, nicht vorgetaeuscht.

**Files:**
- Create: `simulation/browser_probe.py`
- Test: `tests/test_browser_probe.py`

**Interfaces:**
- Produces: `schneide(quelle: Path, ziel: Path, sekunden: float) -> float` (rein, `wave`).
- Produces: `begriffe_gefunden(transkript: str, begriffe: Iterable[str]) -> list[str]` (rein, casefold).
- Produces: `chromium_argumente(wav: Path, schleife: bool = False) -> list[str]`. Liefert die drei Fake-Flags. `--use-file-for-fake-audio-capture=<wav>`, mit `%noloop`, solange `schleife` falsch ist.
- CLI: `python -m simulation.browser_probe mikro` startet nur den Webserver (`browser_umgebung.baue_gruppe` + `starte_web`, **kein Bot, keine Env**), oeffnet die Gruppenseite mit Fake-Audio, klickt `#diskussion`, wartet 50 s, klickt `#diskussion-beenden` und gibt die Zahl der `web_post`-Zeilen mit Audio sowie ihre Dateigroessen aus.
- CLI: `python -m simulation.browser_probe whisper <env-datei> <wav>` schneidet 60 s und uebergibt an ein Bash-Kindskript (`source "<env>"`, dann `python -m simulation.browser_probe _whisper_kind <ausschnitt>`). Im Kind laufen `einstellungen.laden()` und `stt.transkribiere(e, httpx.Client(), pfad, 120.0)`. Ausgabe: gefundene Begriffe + Laenge des Transkripts, **kein Transkripttext**.

- [ ] **Step 1: Failing tests**

```python
import wave
from pathlib import Path

from simulation import browser_probe as bp


def _wav(pfad: Path, sekunden: float, rate=8000):
    with wave.open(str(pfad), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * sekunden))


def test_schneide_kappt_auf_sekunden(tmp_path):
    _wav(tmp_path / "a.wav", 5.0)
    assert bp.schneide(tmp_path / "a.wav", tmp_path / "b.wav", 2.0) == 2.0
    with wave.open(str(tmp_path / "b.wav")) as w:
        assert w.getnframes() == 16000


def test_begriffe_gefunden():
    assert bp.begriffe_gefunden("We said Home and the night shift.",
                                ["home", "border", "night shift"]) == ["home", "night shift"]


def test_chromium_argumente_ohne_schleife(tmp_path):
    args = bp.chromium_argumente(tmp_path / "d.wav")
    assert "--use-fake-ui-for-media-stream" in args
    assert "--use-fake-device-for-media-stream" in args
    assert args[-1] == f"--use-file-for-fake-audio-capture={tmp_path / 'd.wav'}%noloop"
    assert bp.chromium_argumente(tmp_path / "d.wav", schleife=True)[-1].endswith("d.wav")
```

- [ ] **Step 2: Rot.** Run: `$PY -m pytest tests/test_browser_probe.py -q -p no:cacheprovider`. Expected: FAIL.

- [ ] **Step 3: Implementieren** (die reinen Funktionen wie in den Interfaces; CLI-Zweige nach dem Muster von `browser_umgebung`, Env nur als Pfad im Bash-Text). Gruen: `3 passed`. Commit:

```bash
git add simulation/browser_probe.py tests/test_browser_probe.py
git commit -m "Browserlauf: billige Probe fuer Fake-Mikrofon und Whisper-Ausschnitt"
```

- [ ] **Step 4 (controller): ANNAHMEN pruefen und Ergebnisse festhalten** in `simulation/browser_laeufe/probe-2026-10-04.txt` (gitignored). Spaeter gehoeren sie in den Bericht, Abschnitt „Harness-Notizen“.
  1. Selektor: `git log --oneline main -- interview_theater/web.py | head -5` und `git show main:interview_theater/web.py | grep -c 'data-begriff='`. Erwartet `≥ 1`. Bei 0: Selektor in `browser_beobachter.BOARD_SELEKTOR` anpassen und Task-4-Test nachziehen.
  2. Leerzustand (D6): `grep -n "sende\|tg\." scripts/web_gruppe.py` und `sed -n 45,56p scripts/begruessen.py`. Beim Planen gesehen: `scripts/begruessen.py` ist seit 02.10.2026 **stillgelegt** („die Gruppe schreibt zuerst“, Begruessung im ersten Gespraechszug). Bestaetigt sich, dass `web_gruppe.py` nichts sendet, sehen echte Gruppen ebenfalls „Nothing here yet…“. Das ist dann **kein** Harness-Fix, sondern Kandidat fuer einen B-Befund (mehr als eine Loesung: Phaseneintrittsnachricht beim Anlegen oder ein besserer Leertext, Birks Entscheidung vom 02.10.).
  3. Audio: `$W -m simulation.erzeuge_diskussion_audio simulation/browser_laeufe/probe/d.wav`, dann `$W -m simulation.browser_probe mikro --wav simulation/browser_laeufe/probe/d.wav`. Erwartet ≥ 1 Audio-Post mit Groesse > 0 (Annahme a). Ob die Datei schleift (Annahme d): Mit `%noloop` und einer 10-s-Schnittdatei 50 s aufnehmen. Die Segmente nach Sekunde 10 sind dann still bzw. klein. Ergebnis notieren und fuer den Lauf `schleife=False` behalten, wenn `%noloop` greift.
  4. Kalibrierung (Annahme c): im selben Probelauf `#kalibrierung-start` → `#kalibrierung-sprechen` klicken und 12 s warten. Notieren, ob `#kalibrierung-ja` erscheint. **Ohne Bot transkribiert niemand.** Erscheint es nicht, wird in Task 11 mit Bot erneut geprueft. Scheitert es dort auch, gilt die Kalibrierstation als „vom Harness nicht abgedeckt“ (Harness-Notiz im Bericht, nicht vortaeuschen).
  5. Whisper (Annahme b, ≈ 0.006 CHF): `$W -m simulation.browser_probe whisper /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env simulation/browser_laeufe/probe/d.wav`. Erwartet: mindestens 3 von `home, border, waiting, belonging, night shift` gefunden. Weniger → `_WOERTER_JE_MINUTE` auf 130 senken, neu erzeugen, einmal wiederholen. Danach ist Schluss, mit Notiz.

  Kein Commit in Step 4 (nur gitignorte Notizen), ausser Step 4.1 erzwingt eine Selektoraenderung. Die geht dann als eigener Commit `Browserlauf: Board-Selektor an Designkarte angepasst`.

---

### Task 7: Stationsmodus in der Engine und CLI (D2, D3, D4, D5, D6)

**Files:**
- Modify: `simulation/browser_lauf.py`
- Modify: `simulation/README.md` (Abschnitt „Der Abnahmelauf Phase 1–2“)
- Test: `tests/test_browser_lauf.py` (anhaengen; nutzt die vorhandene `stack`-Fixture)

**Interfaces:**
- Consumes: `browser_stationen.Station/STATIONEN/muss_antworten/notweg_ziel/HINWEIS_*` (Task 3), `browser_persona.naechste_aktion(..., hinweis=)`/`offene_fragen` (Task 1), `browser_beobachter.Beobachter` (Task 4), `browser_probe.chromium_argumente` (Task 6), `erzeuge_diskussion_audio.erzeuge` (Task 5), `browser_zaehler.entwickler_meta` (Task 8; bis dahin per `getattr`-Rueckfall leer, siehe unten).
- Produces:

```python
def _verlaufsblasen(page) -> list[dict]   # [{"von","typ","text"}]
def _aktion_ausfuehren(page, aktion: dict) -> dict   # die try/except-Logik aus _fuehre_phase_aus, herausgezogen
def fuehre_stationen(page, context, *, basis_url, token, db_pfad, chat_id,
                     persona_client, judge_client, geraet, persona_name,
                     stationen, lauf_verzeichnis, beobachter=None,
                     leitbilder=None) -> dict
```

Rueckgabe von `fuehre_stationen`:

```python
{"stationen_ergebnisse": [{"schluessel", "phase", "schritte", "nachfragen_beantwortet",
   "offene_fragen": list[str], "fertig": bool, "fallback_benutzt": bool,
   "note", "befunde", "zaehler_summe", "screenshots_fuer_bericht"}],
 "board_verlauf": list[int], "beobachter_neu_geladen": bool, "board_bestanden": bool,
 "entwickler_meta": list[str], "modelle": dict, "top_befunde": list,
 "fehlgeschlagen_bei": str | None}
```

Zusaetzlich schreibt die Engine `lauf_verzeichnis / "ergebnis.json"` (Grundlage fuer Task 10).

- Notweg-Waechter auch im **alten** Phasenmodus: In `_fuehre_phase_aus` wird `if aktuelle_phase < phasen.LETZTE:` zu `ziel = browser_stationen.notweg_ziel(aktuelle_phase, _aktive_phase_nummer(page)); if ziel is not None and ziel <= phasen.LETZTE:`.

- [ ] **Step 1: Failing tests** (an `tests/test_browser_lauf.py` anhaengen):

```python
def test_notweg_springt_nicht_in_eine_schon_aktive_phase(stack, tmp_path):
    """Baseline 04.10.: /phaseklick hin und her erzeugte doppelte
    Phasentexte. Ist Phase 2 schon aktiv, darf der Notweg aus Phase 1 nichts
    ausloesen -- eine nicht aufloesende Basis-URL machte jeden Versuch sichtbar."""
    basis, token, pfad = stack
    conn = db.verbinde(pfad); repo.setze_phase(conn, CHAT, 2); conn.commit(); conn.close()
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page(); seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")
        ergebnis = browser_lauf._fuehre_phase_aus(
            seite, _ScriptedClient([{"type": "wait", "duration_ms": 50,
                                     "begruendung": "w"}] * 5),
            browser_lauf.browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy"),
            aktuelle_phase=1, basis_url="http://127.0.0.1:1", token=token,
            db_pfad=pfad, chat_id=CHAT, persona_name="student",
            max_schritte=3, fallback_nach_schritten=1)
        browser.close()
    assert ergebnis["fallback_benutzt"] is False


def test_station_beantwortet_eine_rueckfrage_bevor_sie_endet(stack, tmp_path, monkeypatch):
    from simulation import browser_stationen
    basis, token, pfad = stack
    monkeypatch.setattr(browser_lauf, "_verlaufsblasen",
                        lambda page: [{"von": "bot", "typ": "text", "text": "Which terms?"}])
    station = browser_stationen.Station("t-eins", 1, "Say hello.", budget=4)
    persona = _ScriptedClient([
        {"type": "done_station", "begruendung": "fertig", "offene_fragen": ["What is this?"]},
        {"type": "type_send", "text": "home and border", "begruendung": "antworte"},
        {"type": "done_station", "begruendung": "jetzt fertig"},
    ])
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        ergebnis = browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=persona, judge_client=_FakeJudge(), geraet="handy",
            persona_name="priya", stationen=(station,), lauf_verzeichnis=tmp_path / "l")
        browser.close()
    st = ergebnis["stationen_ergebnisse"][0]
    assert st["nachfragen_beantwortet"] >= 1
    assert st["offene_fragen"] == ["What is this?"]
    assert persona.aufrufe >= 3
    assert (tmp_path / "l" / "ergebnis.json").exists()
    zeilen = (tmp_path / "l" / "schritte.jsonl").read_text().splitlines()
    assert json.loads(zeilen[0])["station"] == "t-eins"
```

(`_ScriptedClient` endet nach der Folge mit `done_phase`. Da `_verlaufsblasen` gepatcht immer eine Frage meldet, endet die Station spaetestens nach `MAX_NACHFRAGEN` bzw. dem Budget. Der Test prueft genau das.)

- [ ] **Step 2: Rot**

Run: `$W -m pytest tests/test_browser_lauf.py -q -p no:cacheprovider`
Expected: 2 neue FAIL (`fallback_benutzt is True` bzw. `AttributeError: fuehre_stationen`), die 4 alten passed

- [ ] **Step 3: Implementieren.** In `simulation/browser_lauf.py` (zusaetzlich `import time`, `from simulation import browser_stationen`):

```python
def _verlaufsblasen(page) -> list[dict]:
    return page.eval_on_selector_all(
        ".blase",
        "els => els.map(el => ({von: el.classList[1] || '?', "
        "typ: el.classList[2] || 'text', text: (el.innerText || '').trim()}))",
    )


def _aktion_ausfuehren(page, aktion: dict) -> dict:
    try:
        return browser_aktionen.fuehre_aus(page, aktion)
    except browser_aktionen.UnbekannteAktion as fehler:
        log.warning("unbekannte Persona-Aktion: %s", fehler)
        return {"art": "unbekannt", "fehler": str(fehler)}
    except PlaywrightError as fehler:
        log.warning("Aktion schlug fehl (%s): %s", aktion, fehler)
        return {"art": "fehlgeschlagen", "fehler": str(fehler)}


def _diskussion_laeuft(page) -> bool:
    return page.locator('#diskussion[data-laeuft="1"]').count() > 0


def _entwickler_meta(page) -> list[str]:
    zaehler = getattr(browser_zaehler, "entwickler_meta_seite", None)
    return zaehler(page) if zaehler else []


def _fuehre_station_aus(page, persona_client, mitschnitt, station, *, basis_url,
                        token, db_pfad, chat_id, persona_name, beobachter,
                        leitbilder) -> dict:
    zaehler_summe: dict[str, int] = {}
    screenshots: list[Path] = []
    offene: list[str] = []
    beantwortet = 0
    hinweis = None
    gewartet = mitte_genommen = fallback = False
    vorher = browser_mitschnitt.datenstand(db_pfad, chat_id)
    if leitbilder and station.leitbild_anfang:
        leitbilder.nimm(page, station.phase, station.leitbild_anfang)

    schritte = 0
    while schritte < station.budget:
        schritte += 1
        vor = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-vor")
        vor.write_bytes(browser_elemente.bildschirmfoto(page))
        elemente = browser_elemente.extrahiere(page)
        aktion = browser_persona.naechste_aktion(
            persona_client, persona_name, vor.read_bytes(), elemente,
            station.ziel, _verlaufszeilen(page), hinweis=hinweis)
        hinweis = None
        offene.extend(browser_persona.offene_fragen(aktion))
        if aktion.get("type") in ("done_phase", "done_station"):
            if browser_stationen.muss_antworten(_verlaufsblasen(page), beantwortet):
                beantwortet += 1
                hinweis = browser_stationen.HINWEIS_NACHFRAGE
                continue
            break

        protokoll = _aktion_ausfuehren(page, aktion)
        warte = browser_aktionen.warte_auf_antwort(page)

        if station.zuhoeren_s and not gewartet and _diskussion_laeuft(page):
            gewartet = True
            ende = time.monotonic() + station.zuhoeren_s
            while time.monotonic() < ende:
                page.wait_for_timeout(10_000)
                if beobachter:
                    beobachter.messe()
                if leitbilder and station.leitbild_mitte and not mitte_genommen:
                    mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))
            hinweis = browser_stationen.HINWEIS_DISKUSSION_ENDE

        if (leitbilder and station.leitbild_mitte and not mitte_genommen
                and not station.zuhoeren_s
                and page.locator(".leiste button:visible, #kalibrierung-start:visible").count()):
            mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))

        nach = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-nach")
        nach.write_bytes(browser_elemente.bildschirmfoto(page))
        screenshots.append(nach)
        nachher = browser_mitschnitt.datenstand(db_pfad, chat_id)
        db_diff = browser_mitschnitt.unterschied(vorher, nachher)
        vorher = nachher
        _zaehler_addieren(zaehler_summe, browser_zaehler.alle(page))
        if beobachter:
            beobachter.messe()
        mitschnitt.schritt(
            phase=station.phase, screenshot_vorher=vor, screenshot_nachher=nach,
            elemente=elemente, aktion=protokoll, begruendung=aktion.get("begruendung", ""),
            antwort=warte, db_diff=db_diff, station=station.schluessel)

        aktiv = _aktive_phase_nummer(page)
        if station.endet_bei_phasenwechsel and aktiv is not None and aktiv > station.phase:
            break

    stand = browser_mitschnitt.datenstand(db_pfad, chat_id)
    fertig = station.fertig(stand) if station.fertig else True
    if not fertig and station.endet_bei_phasenwechsel:
        ziel = browser_stationen.notweg_ziel(station.phase, _aktive_phase_nummer(page))
        if ziel is not None and ziel <= phasen.LETZTE:
            _loese_phasenwechsel_aus(basis_url, token, ziel)
            fallback = True
    if leitbilder and station.leitbild_ende:
        if station.leitbild_tab:
            browser_aktionen.fuehre_aus(page, {"type": "tab", "name": station.leitbild_tab})
        leitbilder.nimm(page, station.phase, station.leitbild_ende)
        if station.leitbild_tab:
            browser_aktionen.fuehre_aus(page, {"type": "tab", "name": "chat"})
    if leitbilder and beobachter and station.leitbild_beobachter:
        leitbilder.nimm(beobachter.page, station.phase, station.leitbild_beobachter,
                        geraet="handy")
    return {"schritte": schritte, "nachfragen_beantwortet": beantwortet,
            "offene_fragen": offene, "fertig": fertig, "fallback_benutzt": fallback,
            "zaehler_summe": zaehler_summe, "screenshots_nach": screenshots}


def fuehre_stationen(page, context, *, basis_url, token, db_pfad, chat_id,
                     persona_client, judge_client, geraet, persona_name,
                     stationen, lauf_verzeichnis, beobachter=None,
                     leitbilder=None) -> dict:
    lauf_verzeichnis = Path(lauf_verzeichnis)
    mitschnitt = browser_mitschnitt.Mitschnitt(
        lauf_verzeichnis, f"{geraet}-{persona_name}", geraet)
    browser_zaehler.installiere_messung(context)
    page.goto(f"{basis_url}/g/{token}")
    page.wait_for_selector("#verlauf")
    ergebnisse: list[dict] = []
    fehlgeschlagen_bei = None
    meta: set[str] = set()
    for station in stationen:
        try:
            lauf = _fuehre_station_aus(
                page, persona_client, mitschnitt, station, basis_url=basis_url,
                token=token, db_pfad=db_pfad, chat_id=chat_id,
                persona_name=persona_name, beobachter=beobachter,
                leitbilder=leitbilder)
        except Exception:
            log.exception("Station %s ist gescheitert", station.schluessel)
            fehlgeschlagen_bei = fehlgeschlagen_bei or station.schluessel
            ergebnisse.append({"schluessel": station.schluessel, "phase": station.phase,
                               "schritte": 0, "nachfragen_beantwortet": 0,
                               "offene_fragen": [], "fertig": False,
                               "fallback_benutzt": False, "note": None, "befunde": [],
                               "zaehler_summe": {}, "screenshots_fuer_bericht": []})
            continue
        meta.update(_entwickler_meta(page))
        repraesentativ = _repraesentativ(lauf["screenshots_nach"])
        bewertung = browser_judge.bewerte_phase(
            judge_client, station.phase, f"{phasen.kurzname(station.phase)} / {station.schluessel}",
            [p.read_bytes() for p in repraesentativ], [p.name for p in repraesentativ],
            lauf["zaehler_summe"])
        ergebnisse.append({
            "schluessel": station.schluessel, "phase": station.phase,
            **{k: lauf[k] for k in ("schritte", "nachfragen_beantwortet", "offene_fragen",
                                    "fertig", "fallback_benutzt", "zaehler_summe")},
            "note": bewertung.get("note"), "befunde": bewertung.get("befunde") or [],
            "screenshots_fuer_bericht": [p.name for p in repraesentativ]})

    beob = beobachter.ergebnis() if beobachter else {
        "board_verlauf": [], "beobachter_neu_geladen": False, "board_bestanden": False}
    modelle = _modell_lesen(db_pfad)
    modelle["persona"] = getattr(persona_client, "modell", "?")
    modelle["judge"] = getattr(judge_client, "modell", "?")
    top = [{**b, "station": e["schluessel"]} for e in ergebnisse
           for b in e["befunde"] if b.get("schwere") == "hoch"]
    ergebnis = {"geraet": geraet, "persona": persona_name,
                "stationen_ergebnisse": ergebnisse, **beob,
                "entwickler_meta": sorted(meta), "modelle": modelle,
                "top_befunde": top, "fehlgeschlagen_bei": fehlgeschlagen_bei,
                "db_pfad": db_pfad}
    (lauf_verzeichnis / "ergebnis.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    return ergebnis
```

`_fuehre_phase_aus` nutzt jetzt `_aktion_ausfuehren` statt des inline `try/except`. Verhalten unveraendert, alte Tests gruen.

CLI in `main()`:

```python
    zerleger.add_argument("--stationen", choices=sorted(browser_stationen.STATIONEN))
    zerleger.add_argument("--leitbilder", action="store_true",
                          help="nur Schlusslauf: Leitbilder nach docs/guide/bilder")
```

Mit `--stationen`:
- `lauf_name = f"{datum}-{geraet}-{persona}-{stationen}"`
- WAV erzeugen: `erzeuge_diskussion_audio.erzeuge(<skript>, lauf_verzeichnis / "diskussion.wav")`
- `browser = p.chromium.launch(args=browser_probe.chromium_argumente(wav))`
- Laptop-Profil `{"viewport": {"width": 1440, "height": 900}}`, Handy `{**p.devices["iPhone 13"]}`
- `beobachter = Beobachter.oeffne(browser, f"{stack.web_basis}/g/{stack.token}")`, **bevor** die Persona-Seite startet
- `leitbilder = browser_leitbilder.Sammler(token=stack.token, geraet=..., ziel=Path("docs/guide/bilder")) if --leitbilder else None` (Task 9; bis dahin `None`)
- `fuehre_stationen(...)` mit `stationen=browser_stationen.STATIONEN[argumente.stationen]`
- `beobachter.schliesse()` vor `browser.close()`
- mit `--bericht`: `print(f"Ergebnis: {lauf_verzeichnis / 'ergebnis.json'}")`. Den Markdown baut erst Task 10. Der alte Phasenmodus bleibt Zeile fuer Zeile wie gehabt.

README: Abschnitt „Der Abnahmelauf Phase 1–2“ (ca. 15 Zeilen) mit beiden Kommandos aus Task 11, dem Hinweis auf das zweite Geraet, Fake-Audio und `espeakng_loader` nur im it-webtest-venv sowie „kostet Geld, controller-executed“.

- [ ] **Step 4: Gruen**

Run: `$W -m pytest tests/test_browser_lauf.py tests/test_browser_stationen.py tests/test_browser_persona.py -q -p no:cacheprovider`
Expected: alle passed (6 + Task-3- + Task-1-Tests)

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_lauf.py simulation/README.md tests/test_browser_lauf.py
git commit -m "Browserlauf: Stationsmodus P1-2 mit Nachfragen, Zuhoeren, zweitem Geraet; Notweg nie doppelt"
```

---

### Task 8: Rubrik, Phase-2-Regel und Zaehler `entwickler_meta` (D7, D8 Klasse A)

**Files:**
- Modify: `simulation/ux_rubrik.md:85-92`
- Modify: `workshop/padua-2026/prompts/phasen/2.md`
- Modify: `simulation/browser_zaehler.py`
- Test: `tests/test_browser_judge.py`, `tests/test_padua_phase2_prompt.py` (neu), `tests/test_browser_lauf_zaehler.py`

**Interfaces:**
- Produces: `browser_zaehler.entwickler_meta(texte: list[str]) -> list[str]` (rein; Treffer von `re.compile(r"\bcode\b|\bthe code\b|implement|bug", re.I)`, Reihenfolge erhalten, ohne Doppel).
- Produces: `browser_zaehler.entwickler_meta_seite(page) -> list[str]` (liest `.blase.bot`, Text auf 200 Zeichen gekappt).

- [ ] **Step 1: Failing tests**

`tests/test_browser_judge.py`:

```python
def test_rubrik_erlaubt_das_begriffsboard_beim_zuhoeren():
    from simulation import browser_judge
    text = " ".join(browser_judge.lies_rubrik().split())
    assert ("Tell: a CoThinker-style card or a bot line appears during a pure "
            "context recording.") not in text
    assert "term board" in text
    assert "no bot line in the chat" in text.lower()
```

`tests/test_padua_phase2_prompt.py`:

```python
from pathlib import Path

DATEI = Path("workshop/padua-2026/prompts/phasen/2.md")


def test_phase2_verbietet_entwickler_meta_gegenueber_der_gruppe():
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "Never talk to the group about code." in text
    assert "what the code reads" in text
    assert "say plainly that it does not exist yet" in text
```

`tests/test_browser_lauf_zaehler.py`:

```python
def test_entwickler_meta_findet_code_gerede():
    from simulation import browser_zaehler as z
    texte = ["keep tapping Accept -- or say 'accept all mine' and see if the code reads that",
             "Saved your questions.", "That is a bug on my side."]
    assert z.entwickler_meta(texte) == [texte[0], texte[2]]
    assert z.entwickler_meta(["Your opening is warm."]) == []
```

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_browser_judge.py tests/test_padua_phase2_prompt.py tests/test_browser_lauf_zaehler.py -q -p no:cacheprovider -k "rubrik or entwickler or phase2"`
Expected: 3 FAIL

- [ ] **Step 3: Implementieren**

Rubrik, den Spiegelpunkt ab Zeile 85 ersetzen durch:

```markdown
- **Background listening is a mode of its own: record, no chat feedback.** When the
  recording only serves as context for later phases (Phase 1 term discussion),
  the phone lies in the middle and runs the whole time: no arc buttons, no
  comments, only pause/stop/resume; one condensation at the very end
  („es gibt überhaupt gar kein Feedback. Das ist einfach nur ein
  Mitschneiden, damit die KI das Hintergrundwissen aus der Diskussion hat“,
  03.10.2026). Since 04.10.2026 (Birk, card t_4517d4ad) Phase 1 listening
  fills the term board in the CoThinker tab, meant for a second phone: that
  growing term board is intended, not a violation. Still no bot line in the
  chat while listening. Tell: a bot line appears in the chat during a pure
  context recording, or a CoThinker card with comments (other than the term
  board) appears.
```

`2.md`: einen eigenen Absatz direkt nach dem Abschnitt „Don't suggest questions yourself…“ einfuegen:

```markdown
**Never talk to the group about code.** The group sees a theatre workshop,
not software. Never mention code, what the code reads, buttons as code,
implementing something or bugs. If the group wants to accept all their
questions at once: if there is a button for it on screen, point to that
button; otherwise say plainly that it does not exist yet and that they
decide question by question. Never suggest trying a phrase "to see if
something reacts".
```

`ANNAHME:` Kein Padua-Prompt-Schnappschuss hasht `phasen/2.md`. Pruefen: `grep -rln "padua-2026/prompts/phasen\|schnappschuss-padua" tests/`. Gibt es einen, den Schnappschuss mit dem dort genannten Skript neu erzeugen und mitcommitten. Rot nur wegen Dortmund → `@pytest.mark.dortmund`.

`browser_zaehler.py`:

```python
import re

_ENTWICKLER_META = re.compile(r"\bcode\b|\bthe code\b|implement|bug", re.I)


def entwickler_meta(texte: list[str]) -> list[str]:
    """Bot-Blasen mit Entwickler-Meta (Baseline 04.10.: "see if the code
    reads that"). Ziel im bezahlten Lauf: 0."""
    gesehen, treffer = set(), []
    for text in texte:
        if text and _ENTWICKLER_META.search(text) and text not in gesehen:
            gesehen.add(text)
            treffer.append(text)
    return treffer


def entwickler_meta_seite(page, selektor: str = ".blase.bot") -> list[str]:
    return entwickler_meta([(el.text_content() or "").strip()[:200]
                            for el in page.query_selector_all(selektor)])
```

- [ ] **Step 4: Gruen + Profil**

Run: `$PY -m pytest tests/test_browser_judge.py tests/test_padua_phase2_prompt.py tests/test_browser_lauf_zaehler.py tests/test_anweisungen.py -q -p no:cacheprovider && $PY -m scripts.pruefe_profil padua-2026; echo EXIT $?`
Expected: alle passed, `EXIT 0`

- [ ] **Step 5: Commit**

```bash
git add simulation/ux_rubrik.md workshop/padua-2026/prompts/phasen/2.md simulation/browser_zaehler.py tests/test_browser_judge.py tests/test_padua_phase2_prompt.py tests/test_browser_lauf_zaehler.py
git commit -m "Padua Phase 2: kein Entwickler-Meta gegenueber der Gruppe; Rubrik kennt das Begriffsboard; Zaehler entwickler_meta"
```

---

### Task 9: Leitbilder mit Bildwaechter (D9)

**Files:**
- Create: `simulation/browser_leitbilder.py`
- Test: `tests/test_browser_leitbilder.py`, `tests/test_guide_bilder.py`

**Interfaces:**
- Produces:

```python
UNTERSCHRIFTEN: dict[tuple[int, str], str]   # englische Bildunterschriften je (phase, station)
MAX_BYTES = 400_000
def pruefe_bild(seitentext: str, token: str, fehler_sichtbar: bool) -> str | None   # Grund oder None
class Sammler:
    def __init__(self, *, token: str, geraet: str, ziel: Path)
    def nimm(self, page, phase: int, station: str, geraet: str | None = None) -> dict | None
    def schreibe_index(self) -> Path   # fuehrt mit vorhandenem index.json zusammen (Schluessel: datei)
```

- Dateiname `phase-<N>-<station>-<geraet>.png`, `page.screenshot(path=…, scale="css")`. Jede Station wird je Geraet hoechstens einmal genommen (zweiter Aufruf → `None`).
- `index.json`: Liste `{datei, phase, station, geraet, unterschrift_en}`, sortiert nach (phase, Reihenfolge in `UNTERSCHRIFTEN`, geraet).

- [ ] **Step 1: Failing tests**

`tests/test_browser_leitbilder.py`:

```python
from simulation import browser_leitbilder as lb

TOKEN = "AbC123tokenXYZ"


def test_sauberer_text_ist_erlaubt():
    assert lb.pruefe_bild("Phase 1 of 7 · Terms. Start listening.", TOKEN, False) is None


def test_token_link_fehler_und_deutschreste_werden_abgelehnt():
    assert lb.pruefe_bild(f"open /g/{TOKEN}", TOKEN, False) == "token"
    assert lb.pruefe_bild("see http://x", TOKEN, False) == "http"
    assert lb.pruefe_bild("ok", TOKEN, True) == "fehler"
    for rest in ("Begriffe für", "Straße", "Haus und Hof", "das ist nicht gut",
                 "der Plan", "die Gruppe"):
        assert lb.pruefe_bild(rest, TOKEN, False) == "deutsch", rest


def test_unterschriften_decken_die_leitstationen_ab():
    assert set(lb.UNTERSCHRIFTEN) == {
        (1, "eintritt"), (1, "kalibrierung"), (1, "zuhoeren"), (1, "cothinker"),
        (1, "uebergang"), (2, "eintritt"), (2, "arbeit"), (2, "ergebnis"),
        (2, "uebergang")}
    assert all(lb.pruefe_bild(t, TOKEN, False) is None for t in lb.UNTERSCHRIFTEN.values())
```

`tests/test_guide_bilder.py` (laeuft immer mit, greift ab dem Schlusslauf):

```python
import json
from collections import Counter
from pathlib import Path

import pytest

INDEX = Path("docs/guide/bilder/index.json")


def test_leitbilder_klein_vollstaendig_und_hoechstens_fuenf_je_phase_und_geraet():
    if not INDEX.exists():
        pytest.skip("noch kein Schlusslauf")
    eintraege = json.loads(INDEX.read_text(encoding="utf-8"))
    assert eintraege
    for e in eintraege:
        datei = INDEX.parent / e["datei"]
        assert datei.exists(), e["datei"]
        assert datei.stat().st_size <= 400_000, e["datei"]
        assert e["geraet"] in {"handy", "laptop"} and e["unterschrift_en"]
    zahl = Counter((e["phase"], e["geraet"]) for e in eintraege)
    assert max(zahl.values()) <= 5
```

- [ ] **Step 2: Rot.** Run: `$PY -m pytest tests/test_browser_leitbilder.py tests/test_guide_bilder.py -q -p no:cacheprovider`. Expected: FAIL (Modul fehlt) bzw. 1 skipped.

- [ ] **Step 3: Implementieren**

```python
"""Leitbilder fuer Birks Deck (04.10.2026, 18:40): je Phase und Geraet
hoechstens fuenf Screenshots nach docs/guide/bilder/, nur im Schlusslauf.
Ein Waechter lehnt jedes Bild ab, auf dem das Gruppentoken, ein Link, ein
sichtbarer Fehler oder ein deutscher Rest steht. Kein PDF, keine
Bildbibliothek -- kleine PNGs ueber Playwrights scale="css"."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

MAX_BYTES = 400_000
_DEUTSCH = re.compile(r"[äöüß]| und | nicht | der | die ")

UNTERSCHRIFTEN: dict[tuple[int, str], str] = {
    (1, "eintritt"): "Phase 1 starts: the app explains what this phase is for.",
    (1, "kalibrierung"): "A short microphone check before the group starts talking.",
    (1, "zuhoeren"): "Listening: the phone lies in the middle while the group discusses.",
    (1, "cothinker"): "A second phone shows the term board growing in the CoThinker tab.",
    (1, "uebergang"): "Terms saved, the app offers the next phase.",
    (2, "eintritt"): "Phase 2 starts: the group writes its own questions first.",
    (2, "arbeit"): "Going through the questions one at a time with buttons.",
    (2, "ergebnis"): "Where we are: questions, opening and closing at a glance.",
    (2, "uebergang"): "Questions ready, the app offers the interview phase.",
}
_REIHENFOLGE = list(UNTERSCHRIFTEN)


def pruefe_bild(seitentext: str, token: str, fehler_sichtbar: bool) -> str | None:
    if token and token in seitentext:
        return "token"
    if "http" in seitentext:
        return "http"
    if fehler_sichtbar:
        return "fehler"
    if _DEUTSCH.search(seitentext):
        return "deutsch"
    return None


class Sammler:
    def __init__(self, *, token: str, geraet: str, ziel: Path):
        self.token, self.geraet, self.ziel = token, geraet, Path(ziel)
        self.eintraege: list[dict] = []
        self._genommen: set[tuple[int, str, str]] = set()

    def nimm(self, page, phase: int, station: str, geraet: str | None = None) -> dict | None:
        geraet = geraet or self.geraet
        schluessel = (phase, station, geraet)
        if schluessel in self._genommen or (phase, station) not in UNTERSCHRIFTEN:
            return None
        text = page.inner_text("body")
        fehler = page.locator("#fehler:visible").count() > 0
        grund = pruefe_bild(text, self.token, fehler)
        if grund:
            log.warning("Leitbild %s abgelehnt: %s", schluessel, grund)
            return None
        self.ziel.mkdir(parents=True, exist_ok=True)
        datei = f"phase-{phase}-{station}-{geraet}.png"
        page.screenshot(path=str(self.ziel / datei), scale="css")
        if (self.ziel / datei).stat().st_size > MAX_BYTES:
            (self.ziel / datei).unlink()
            log.warning("Leitbild %s zu gross", datei)
            return None
        eintrag = {"datei": datei, "phase": phase, "station": station,
                   "geraet": geraet, "unterschrift_en": UNTERSCHRIFTEN[(phase, station)]}
        self._genommen.add(schluessel)
        self.eintraege.append(eintrag)
        return eintrag

    def schreibe_index(self) -> Path:
        pfad = self.ziel / "index.json"
        alt = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else []
        alle = {e["datei"]: e for e in alt}
        alle.update({e["datei"]: e for e in self.eintraege})
        sortiert = sorted(alle.values(), key=lambda e: (
            e["phase"], _REIHENFOLGE.index((e["phase"], e["station"])), e["geraet"]))
        self.ziel.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(sortiert, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return pfad
```

In `browser_lauf.main()` (Stationsmodus, `--leitbilder`): `Sammler` bauen und nach `fuehre_stationen` `leitbilder.schreibe_index()` aufrufen.

`ANNAHME:` „http“ steht nirgends im normalen Seitentext (z. B. nicht in einem Leitfaden-Link-Text). Faellt in Task 11 ein Bild nur deshalb raus, ist das ein ehrlicher Befund und keine Lockerung des Waechters.

- [ ] **Step 4: Gruen.** Run: `$PY -m pytest tests/test_browser_leitbilder.py tests/test_guide_bilder.py -q -p no:cacheprovider`. Expected: `3 passed, 1 skipped`.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_leitbilder.py simulation/browser_lauf.py tests/test_browser_leitbilder.py tests/test_guide_bilder.py
git commit -m "Browserlauf: Leitbilder mit Waechter gegen Token, Links, Fehler und deutsche Reste"
```

---

### Task 10: Abnahmebericht, Urteil, Modellbeleg, Kosten (D13)

**Files:**
- Create: `simulation/browser_abnahme.py`
- Test: `tests/test_browser_abnahme.py`

**Interfaces:**
- Consumes: `ergebnis.json` aus Task 7 (Schluessel siehe dort).
- Produces:

```python
def urteil(laeufe: list[dict]) -> tuple[bool, str]
def modellbeleg(db_pfad: str) -> list[tuple[str, str, int, float]]   # art, modell, anzahl, chf
def kosten_summe(db_pfade: list[str]) -> float
def baue_abnahme(laeufe: list[dict], *, belege: dict[str, list[tuple]],
                 b_befunde: list[dict], leitbilder: list[dict],
                 harness_notizen: list[str], modellwahl_satz: str) -> str
```

- `urteil`: ja genau dann, wenn in jedem Lauf jede Station `fertig` ist, `board_bestanden` gilt und `entwickler_meta` leer ist. Der Grund nennt bei „nein“ die erste Verfehlung (`"<geraet>: Station p2-eroeffnung nicht erreicht"`), bei „ja“ `"alle 10 Stationen auf beiden Geraeten erreicht, Board ohne Reload gewachsen"`.
- `b_befunde`: `[{"titel","text","vorschlag"}]`, hoechstens 5 (mehr → `ValueError`). Format wie `docs/flow-audit/vorlagen.md`: nummeriert, fetter Titel, Text, „Vorschlag: …“, „Frage: Soll ich?“.
- CLI: `python -m simulation.browser_abnahme bericht --lauf <dir> --lauf <dir> [--b-befunde <json>] [--notizen <txt>] [--modellwahl "<satz>"] --ausgabe simulation/berichte/abnahme-p12-2026-10-04.md`
- CLI: `python -m simulation.browser_abnahme kosten <db> [<db> …]` gibt `Summe CHF: 0.1234` aus.

- [ ] **Step 1: Failing tests**

```python
import sqlite3

import pytest

from simulation import browser_abnahme as ab


def _lauf(geraet, fertig=True, board=True, meta=()):
    return {"geraet": geraet, "persona": "giulia" if geraet == "handy" else "priya",
            "stationen_ergebnisse": [
                {"schluessel": "p1-eintritt", "phase": 1, "schritte": 2,
                 "nachfragen_beantwortet": 1, "offene_fragen": ["What is CoThinker?"],
                 "fertig": True, "fallback_benutzt": False, "note": 4, "befunde": [],
                 "screenshots_fuer_bericht": ["001.png"]},
                {"schluessel": "p2-eroeffnung", "phase": 2, "schritte": 5,
                 "nachfragen_beantwortet": 0, "offene_fragen": [], "fertig": fertig,
                 "fallback_benutzt": False, "note": 3, "befunde": [],
                 "screenshots_fuer_bericht": []}],
            "board_verlauf": [0, 2, 5] if board else [0, 0], "board_bestanden": board,
            "beobachter_neu_geladen": False, "entwickler_meta": list(meta)}


def test_urteil_ja_und_nein():
    assert ab.urteil([_lauf("handy"), _lauf("laptop")])[0] is True
    ok, grund = ab.urteil([_lauf("handy"), _lauf("laptop", fertig=False)])
    assert ok is False and "laptop" in grund and "p2-eroeffnung" in grund
    assert ab.urteil([_lauf("handy", board=False), _lauf("laptop")])[0] is False
    assert ab.urteil([_lauf("handy", meta=["the code reads"]), _lauf("laptop")])[0] is False


def test_bericht_beginnt_mit_dem_urteil_und_enthaelt_alle_teile():
    md = ab.baue_abnahme(
        [_lauf("handy"), _lauf("laptop")],
        belege={"handy": [("gespraech", "moonshotai/Kimi-K2.6", 12, 0.04)]},
        b_befunde=[{"titel": "Phase 2 · Alle annehmen", "text": "24 Taps.",
                    "vorschlag": "Knopf 'Accept all mine'."}],
        leitbilder=[{"datei": "phase-1-eintritt-handy.png", "unterschrift_en": "x"}],
        harness_notizen=["Kalibrierung mit Fake-Audio: bestanden"],
        modellwahl_satz="Kimi, Modellwahl noch nicht gemergt")
    erste = md.splitlines()[0]
    assert erste.startswith("Phase 1-2 abnahmebereit: ja")
    for teil in ("## Testanleitung fuer Birk", "## Stationen", "What is CoThinker?",
                 "## Begriffsboard", "0 → 2 → 5", "## Modellbeleg", "Kimi-K2.6",
                 "## B-Befunde", "Frage: Soll ich?", "docs/guide/bilder/phase-1-eintritt-handy.png",
                 "Kimi, Modellwahl noch nicht gemergt", "## Harness-Notizen"):
        assert teil in md, teil


def test_mehr_als_fuenf_b_befunde_sind_ein_fehler():
    with pytest.raises(ValueError):
        ab.baue_abnahme([_lauf("handy")], belege={}, leitbilder=[], harness_notizen=[],
                        modellwahl_satz="", b_befunde=[{"titel": "t", "text": "x",
                                                        "vorschlag": "v"}] * 6)


def test_modellbeleg_und_kosten(tmp_path):
    pfad = str(tmp_path / "s.db")
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE aufruf (art TEXT, modell TEXT, kosten_chf REAL)")
    conn.executemany("INSERT INTO aufruf VALUES (?,?,?)",
                     [("gespraech", "kimi", 0.01), ("gespraech", "kimi", 0.02),
                      ("stt", "whisper", None)])
    conn.commit(); conn.close()
    assert ab.modellbeleg(pfad) == [("gespraech", "kimi", 2, 0.03), ("stt", "whisper", 1, 0.0)]
    assert ab.kosten_summe([pfad, pfad]) == pytest.approx(0.06)
```

- [ ] **Step 2: Rot.** Run: `$PY -m pytest tests/test_browser_abnahme.py -q -p no:cacheprovider`. Expected: FAIL (Modul fehlt).

- [ ] **Step 3: Implementieren.** `modellbeleg`: read-only (`file:…?mode=ro`), `SELECT art, modell, COUNT(*), COALESCE(SUM(kosten_chf), 0) FROM aufruf GROUP BY 1, 2 ORDER BY 1, 2`, Summen auf 4 Stellen gerundet. Fehlende Tabelle → `[]`. `kosten_summe` = Summe der vierten Spalte ueber alle Pfade.

`baue_abnahme` in dieser Reihenfolge (Ueberschriften genau so, die Tests pruefen sie):
1. `Phase 1-2 abnahmebereit: ja|nein — <grund>` (aus `urteil`)
2. `## Testanleitung fuer Birk`: feste Klickfolge auf zwei Geraeten. (1) Handy A oeffnet den Gruppenlink. (2) Handy B oeffnet denselben Link und tippt auf „CoThinker“, danach nicht neu laden. (3) A: Mikrofon-Check, „Start listening“, Handy in die Mitte, 3 Minuten diskutieren. (4) **Auf B achten: das Board waechst ohne Neuladen.** (5) A: „Discussion done“ → Vorschlag → „Take these“ → 📌 gespeichert → „Undo“ → erneut „Take these“. (6) Weiter zu Phase 2, eigene Fragen tippen, **auf einen Warte-Hinweis waehrend des A/B-Vergleichs achten**, Fragen einzeln durchgehen, Eroeffnung/Abschluss. (7) **Am Ende muss das Angebot fuer Phase 3 dastehen.**
3. `## Stationen`: je Lauf eine Tabelle `| Station | Persona | Schritte | Nachfragen | fertig | Note | offene Fragen |`. Offene Fragen mit `; ` verbunden, leer = `—`.
4. `## Begriffsboard (zweites Geraet)`: je Lauf `board_verlauf` als `0 → 2 → 5`, „neu geladen: ja/nein“, „bestanden: ja/nein“.
5. `## Richter`: Befunde je Station (Schwere, Text).
6. `## Modellbeleg`: je Geraet die Tabelle aus `belege`, darunter `modellwahl_satz`, dazu die Kostenzeile `Summe: x.xxxx CHF`.
7. `## Entwickler-Meta im Chat`: Treffer oder „0 (Ziel 0)“.
8. `## B-Befunde (hoechstens 5)`: im vorlagen.md-Format.
9. `## Leitbilder`: `- docs/guide/bilder/<datei> — <unterschrift_en>`.
10. `## Harness-Notizen`: Zeilen aus `harness_notizen`.

CLI-Zweig `bericht` liest `<dir>/ergebnis.json`, `belege[geraet] = modellbeleg(ergebnis["db_pfad"])`, Leitbilder aus `docs/guide/bilder/index.json` (falls vorhanden), B-Befunde aus JSON, Notizen zeilenweise aus Text.

- [ ] **Step 4: Gruen.** Run: `$PY -m pytest tests/test_browser_abnahme.py -q -p no:cacheprovider`. Expected: `4 passed`.

- [ ] **Step 5: Suite vor dem bezahlten Teil**

Run: `$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?` (warten), dann `tail -3 .suite.log` und `$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?`
Expected: `EXIT 0`, `… passed …`, `EXIT 0`. Dazu `$W -m pytest tests/test_browser_*.py tests/test_diskussion_audio.py -q -p no:cacheprovider` → alle passed.

- [ ] **Step 6: Commit**

```bash
git add simulation/browser_abnahme.py tests/test_browser_abnahme.py
git commit -m "Browserlauf: Abnahmebericht P1-2 mit Urteil, Modellbeleg und Kostensumme"
```

---

### Task 11: Befundlauf, zwei echte Laeufe (controller-executed, kostet Geld)

Rahmen wie Task 13 im Plan vom 03.10.2026: Den Lauf faehrt der **Controller selbst** in der laufenden Session, kein Subagent. Es gibt kein Code-Review-Gate, nur „echte Artefakte, korrekt“. Budget: dieser Task ≤ 2 Laeufe. Gemessen am 04.10.: Handy-Baseline 30 Aufrufe = 0.097 CHF, Laptop 11 = 0.027 CHF, Whisper 0.006 CHF/min. Mit 3 Minuten Audio je Lauf erwartet: ≤ 0.35 CHF fuer beide. Harter Stopp bei Σ > 1.50 CHF ueber alle Laeufe (inkl. Task 6).

**Voraussetzungen:**
- Tasks 0–10 committed, Suite gruen (Task 10 Step 5).
- Claude-Code-Settings des Controllers erlauben `Bash(/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python*)` und `Bash(env -u IT_WORKSHOP*)`.
- `test -f /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env` (nur Existenz, **nie lesen**; `dangerouslyDisableSandbox: true` nur fuer diese eine Pruefung wie am 03.10.).
- Proxy-Rauchprobe fuer Opus (klein, `max_tokens` niedrig) wie am 03.10.

- [ ] **Step 1: Modellwahl-Karte pruefen (D10)**

Run: `git log --oneline main | head -15`
Liegen die Commits der Karte t_fde12c23 („Padua Modellwahl: Opus ueberall ausser Interviews“) auf main, dann `git merge main` in **diesen** Branch (kein Push) und die Suite wie in Task 10 Step 5 erneut laufen lassen (warten, `EXIT 0`). Sonst auf dem jetzigen Stand fahren und als Notiz festhalten: `modellwahl_satz = "Kimi, Modellwahl noch nicht gemergt"`.

- [ ] **Step 2: Handy, Giulia**

```bash
env -u IT_WORKSHOP /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m simulation.browser_lauf \
  --env-datei /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env \
  --geraet handy --persona giulia --stationen p12 --bericht
```

Nicht blind in den Hintergrund. Bei Stillstand `simulation/browser_laeufe/<lauf>/schritte.jsonl` und `bot.log` lesen, bevor abgebrochen wird. Expected: `Ergebnis: simulation/browser_laeufe/2026-10-04-handy-giulia-p12/ergebnis.json`.

- [ ] **Step 3: Kosten pruefen**

Run: `$PY -m simulation.browser_abnahme kosten simulation/browser_laeufe/2026-10-04-handy-giulia-p12/sim.db`
Expected: `Summe CHF: <0.25`. Liegt der Wert inkl. Task 6 schon > 1.50: Stopp, committen, was da ist, berichten.

- [ ] **Step 4: Laptop, Priya** (erst nach Step 3, nie parallel)

```bash
env -u IT_WORKSHOP /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m simulation.browser_lauf \
  --env-datei /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env \
  --geraet laptop --persona priya --stationen p12 --bericht
```

- [ ] **Step 5: Befunde auswerten und einordnen.** Je Lauf `ergebnis.json` lesen: Stationen `fertig`, `board_verlauf`, `beobachter_neu_geladen`, `entwickler_meta`, Richterbefunde, Priyas `offene_fragen`. Zusaetzlich `SELECT COUNT(*) FROM aufnahme WHERE diskussion = 1` (read-only) fuer Annahme a.
  - **Klasse A** (genau eine sinnvolle Loesung): direkt fixen, je Fix ein Test zuerst (rot → gruen), eigener Commit `Abnahme P1-2: <Fix>`. Harness-Artefakte (Persona traf falsches Element, Wartezeit zu kurz) zaehlen als Harness-Fix, nicht als Produktbefund.
  - **Klasse B** (mehr als eine Loesung, Wortlaut = Birks Entscheidung): Liste in `simulation/browser_laeufe/abnahme-b.json` fuehren, hoechstens 5. Vorbesetzt nach D8: (1) Einzeldurchgang mit vielen eigenen Fragen = viele Accept-Taps → „Accept all mine“ als Knopf/Intent. (2) „Please suggest the rest“ → Bot lehnt dreimal ab; die **erste** Antwort muss sagen, warum und wann die KI-Fragen kommen. Dazu gegen den Browser erneut pruefen und nur bei Bestaetigung uebernehmen: vorlagen.md 1 („yes“ nimmt keine Frage an), 2 (kein Warte-Hinweis waehrend A/B), 3 (dreifache Begriffsantwort). Sowie der Leerzustand aus Task 6 Step 4.2, falls bestaetigt. Mehr als 5 Kandidaten → nach Schwere die 5 obersten, der Rest als eine Zeile in die Harness-Notizen.
  - Ein Test, der **nur** wegen Dortmund rot wird → `@pytest.mark.dortmund`.

- [ ] **Step 6: Suite nach den A-Fixes** wie Task 10 Step 5 → `EXIT 0`; danach Commit der Fixes (je Fix eigener Commit, siehe oben).

---

### Task 12: Schlusslauf mit Leitbildern, Bericht, Abschluss (controller-executed, kostet Geld)

Budget: ≤ 2 Laeufe (insgesamt damit 4), Stopp bei Σ > 1.50 CHF.

- [ ] **Step 1: Handy, Giulia, mit Leitbildern**

```bash
env -u IT_WORKSHOP /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m simulation.browser_lauf \
  --env-datei /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env \
  --geraet handy --persona giulia --stationen p12 --bericht --leitbilder
```

(Das Laufverzeichnis des Befundlaufs vom selben Tag vorher nach `…-befund` umbenennen: `mv simulation/browser_laeufe/2026-10-04-handy-giulia-p12 simulation/browser_laeufe/2026-10-04-handy-giulia-p12-befund`, ebenso Laptop. Sonst ueberschreibt der Schlusslauf es.)

- [ ] **Step 2: Kosten** wie Task 11 Step 3, ueber alle bisherigen `sim.db`. Weiter nur bei Σ ≤ 1.50 CHF.

- [ ] **Step 3: Laptop, Priya, mit Leitbildern** (Kommando wie Step 1 mit `--geraet laptop --persona priya`)

- [ ] **Step 4: Leitbilder pruefen**

Run: `$PY -m pytest tests/test_guide_bilder.py -q -p no:cacheprovider` und `ls -la docs/guide/bilder/`
Expected: `1 passed` (nicht mehr skipped). Hoechstens 5 Bilder je Phase und Geraet, keines > 400 KB. Jedes Bild einmal mit dem Read-Werkzeug ansehen: kein Token, kein Link, keine deutsche Zeile. Fehlt eine Station (Waechter hat abgelehnt), steht das als Harness-Notiz im Bericht.

- [ ] **Step 5: Bericht bauen**

```bash
$PY -m simulation.browser_abnahme bericht \
  --lauf simulation/browser_laeufe/2026-10-04-handy-giulia-p12 \
  --lauf simulation/browser_laeufe/2026-10-04-laptop-priya-p12 \
  --b-befunde simulation/browser_laeufe/abnahme-b.json \
  --notizen simulation/browser_laeufe/probe-2026-10-04.txt \
  --modellwahl "<Satz aus Task 11 Step 1>" \
  --ausgabe simulation/berichte/abnahme-p12-2026-10-04.md
```

Expected: Die erste Zeile ist `Phase 1-2 abnahmebereit: ja — …` oder `… nein — …`. Den Bericht einmal ganz lesen und auf Tokens, URLs und echte Namen pruefen (`grep -n "http\|/g/" simulation/berichte/abnahme-p12-2026-10-04.md` → keine Treffer).

- [ ] **Step 6: Abschluss-Gates**

Run: `$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?` (warten), `$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?`, `$W -m pytest tests/test_browser_*.py tests/test_diskussion_audio.py tests/test_guide_bilder.py -q -p no:cacheprovider`
Expected: `EXIT 0`, `EXIT 0`, alle passed.

- [ ] **Step 7: Commit** (nur diese Artefakte; Laufverzeichnisse bleiben gitignored)

```bash
git add simulation/berichte/abnahme-p12-2026-10-04.md docs/guide/bilder/
git commit -m "Abnahme P1-2: Bericht mit Urteil, Leitbilder fuer das Deck"
```

- [ ] **Step 8: Rueckmeldung an Birk** (Text, kein Merge, kein Push): Urteil in einem Satz, Pfad des Berichts, Zahl der A-Fixes mit Commit-SHAs, die B-Befunde (je Titel + „Soll ich?“), Kosten gesamt, Hinweis auf `docs/guide/bilder/index.json` fuers Deck.

---

## Selbstpruefung (gegen den Auftrag)

| Auftrag | Task |
|---|---|
| D1 Personas, `offene_fragen`, CLI | 1 |
| D2 Stationsliste, `--stationen p12`, alter Modus unveraendert | 3, 7 |
| D3 Mehrfachantwort, `muss_antworten`, Limit 3 | 3, 7 |
| D4 zweites Geraet, `board_verlauf`, kein Reload; Selektor-ANNAHME | 4, 6.4.1, 7 |
| D5 Fake-Audio, espeak offline, Annahmen a–d, ≥ 2 min | 5, 6, 7 |
| D6 Tab-Label, Notweg nie rueckwaerts/doppelt, Zuhoeren statt Tippen, Leerzustand pruefen | 2, 3, 7, 6.4.2 |
| D6 zusaetzlich beim Planen gefunden: Diskussions-/Kalibrierknoepfe fehlten in der Elementliste | 2 |
| D7 Rubrik | 8 |
| D8 A-Fix Entwickler-Meta + Zaehler; B-Kandidaten | 8, 11.5 |
| D9 Leitbilder, Waechter, ≤ 400 KB, index.json | 9, 12 |
| D10 Modellwahl-Karte | 11.1 |
| D11 bezahlte Laeufe, Budget, Reihenfolge | 6, 11, 12 |
| D12 Suite/Gates | 8.4, 10.5, 11.6, 12.6 |
| D13 Bericht, Baseline-Berichte committen, gitignore-Negation | 0, 10, 12 |

**Bekannte Grenzen** (gehoeren in die Harness-Notizen des Berichts):
- espeak-Englisch ist kein Studierendenenglisch; Whisper-Treffer zeigen die Kette, nicht die Erkennungsqualitaet im Raum.
- Beide Browser-Kontexte haengen am selben Fake-Mikrofon. Der Beobachter nimmt nie auf.
- Die Kalibrierung mit einer Dauerschleife ist nur so gut wie Annahme c.
- Der Richter bewertet je Station drei Screenshots, nicht den ganzen Verlauf.

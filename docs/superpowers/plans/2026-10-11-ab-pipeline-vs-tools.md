# InScribe Messung 2: A/B Pipeline gegen Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Karten:** Plan `t_c0056676` → Umsetzung `t_9b2b33cb` (Branch/Worktree
`wt/t_9b2b33cb`) → Review → Merge. Spec:
`docs/superpowers/specs/2026-10-11-ab-pipeline-vs-tools-design.md`.

**Goal:** Zahlen für Birks Grundsatzfrage „Pipeline gegen Agent mit Werkzeugen“
auf denselben Daten: Erkenner `json` gegen `tools` (Opus, Stückwerkzeuge) und —
falls der Gold-Korpus vorliegt — Zitatsuche Pipeline gegen Agent, als Bericht
`docs/messung/2026-10-ab-pipeline-vs-tools.md`.

**Architecture:** Ein neuer Schalter `IT_ERKENNER_MODUS` (Default `json`)
schaltet im Opus-Pfad des Erkenners auf eine Werkzeugschleife
(`szene_claude.werkzeug_schleife`) um, die `stueck.WERKZEUGE` plus ein
generisches `aenderung_melden` an Opus bindet (`erkenner_werkzeuge.py`). Ein
Messskript (`scripts/ab_pipeline_vs_tools.py`) fährt beide Modi über
denselben Korpus, übersetzt Werkzeugaufrufe in die Korpus-Sprache
(`art`/`wert`) zurück und zählt mit dem unveränderten
`pruefe_prompts.vergleiche_erkenner`. Achsen B (Padua-Testsatz) und C
(Zitatsuche) sind bedingte Spätphasen.

**Tech Stack:** Python 3.11, `httpx` (`MockTransport` in Tests), SQLite,
pytest (`-n 2`), Anthropic-Messages-Format über
`hermes-anthropic-proxy.service` (127.0.0.1:28764).

## Global Constraints

- Default `IT_ERKENNER_MODUS=json`; ohne die Variable ändert sich **kein**
  Verhalten und kein Prompt-Snapshot.
- `tools` wirkt nur, wenn `erkenner.ueber_claude(e, conn, chat_id)` wahr ist.
- Phase 3 (Interviews), `erkenne_in_aufnahme` und `verdichter.py` bleiben in
  **beiden** Modi hart auf Infomaniak (Kimi/gemma).
- `prompts/erkenner.md` und `sprachen/en/prompts/erkenner.md` werden **nicht**
  geändert (FP=0-Invariante des Erkenner-Prompts).
- `interview_theater/stueck.py` und `tests/test_stueck_*.py` bleiben unverändert.
- Kein neuer Profilschalter, kein Dortmund-Pfad, keine neue Tabelle/Spalte.
- SQL nur in `repo.py`/`db.py`; Messskripte lesen die Padua-Kopie nur über
  `sqlite3` read-only bzw. über `repo`.
- `betrieb/padua.db` nur `mode=ro`, Messung auf `VACUUM INTO`-Kopie
  (`scripts.stueckmodell_kopie.kopiere`); nie `betrieb/padua-test*.db` als
  Messgrundlage.
- Live-Dienste nie starten/stoppen/neu starten. Kein Bot-Neustart.
- Skripte, die Geld kosten (Kimi/gemma über Infomaniak), laufen nie
  automatisch und nur nach Birks Freigabe (Task 10). Opus über den Proxy ist
  Abo (0 CHF, `kosten.CLAUDE_CHF_JE_AUFRUF`).
- Eigene Skripte als Modul starten: `uv run --extra dev python -m scripts.<name>`.
- Testkommando (gezielt): `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 <testpfad>`
- Keine Empfehlung „umstellen“ ohne Zahlen; die Entscheidung trifft Birk.

## Dateien

| Datei | Aufgabe | Task |
|---|---|---|
| `docs/messung/2026-10-ab-vorbedingungen.md` (neu) | Befund Task 0: Proxy, Messung-1-Format, Gold-Korpus | 0 |
| `interview_theater/einstellungen.py` | `erkenner_modus`, `_erkenner_modus` | 1 |
| `interview_theater/erkenner_werkzeuge.py` (neu) | Werkzeugdefinitionen, Ausführung, Rückübersetzung | 2 |
| `interview_theater/szene_claude.py` | `werkzeug_schleife`, `Schleifenergebnis` | 3 |
| `interview_theater/erkenner.py` | `aktive_arten`, `erkenne_mit_werkzeugschritten`, `_werkzeuglauf`, `laufe` | 4 |
| `interview_theater/prompts/erkenner_werkzeuge.md`, `interview_theater/sprachen/en/prompts/erkenner_werkzeuge.md` (neu) | Werkzeug-Absatz | 4 |
| `tests/test_erkenner_tools_datenschutz.py` (neu) | Datenschutz in beiden Modi | 5 |
| `scripts/ab_pipeline_vs_tools.py` (neu) | Messskript, Achse A + `bericht` | 6, 9 |
| `scripts/ab_padua.py` (neu, bedingt) | Achse B | 7 |
| `scripts/ab_zitate.py` (neu, bedingt) | Achse C | 8 |
| `docs/messung/2026-10-ab-pipeline-vs-tools.md` (neu, erzeugt) | Bericht | 9, 10 |
| `AGENTS.md`, `docs/agents/aufbau.md`, `docs/agents/korpus-und-simulation.md` | Doku | 11 |

---

### Task 0: Vorbedingungen prüfen und festhalten (kein Produktivcode)

🔴 **ANNAHME: Testsatz-Format aus Messung 1** — prüfen bei Start der Umsetzung,
ob `docs/messung/` oder ein eigenes `tests/padua_testsatz_*` Format existiert;
ggf. Task 0 der Umsetzung um einen Format-Abgleich ergänzen. Stand
11.10.2026: Messung 1 (`t_dd94e894`/`t_7321edc8`/`t_0fedafe0`) **nicht**
gemergt; Branch `wt/t_dd94e894` ändert nur `scripts/pruefe_prompts.py` und
`tests/test_pruefe_prompts.py`; `docs/messung/` fehlt auf `main`.

🔴 **ANNAHME: Gold-Korpus Zitatauswahl** (`t_2349e9a8` → `t_2f905d2c` →
`t_20f9dc6b` → `t_e906dce3`) existiert am 11.10.2026 **nicht**. Kein Pfad wird
angenommen; er wird hier aus dem dann gemergten Repo-Stand gelesen.

**Files:**
- Create: `docs/messung/2026-10-ab-vorbedingungen.md`

**Interfaces:**
- Produces: drei Entscheidungen, die Task 7, 8 und 9 lesen:
  `ACHSE_B = ja|nein` (+ Pfad und Format des Testsatzes),
  `ACHSE_C = ja|nein` (+ Pfad und Format des Gold-Korpus),
  `PROXY_TOOLS = ja|nein`.

- [ ] **Step 1: Prüfen, dass Messung 1 gemergt ist**

Run: `git log --oneline --grep=t_0fedafe0 main`
Expected: mindestens ein Merge-Commit. Fehlt er: Umsetzung stoppen,
`kanban_block` mit „Messung 1 nicht gemergt“ (die Karte dürfte dann gar
nicht `ready` sein).

- [ ] **Step 2: Format des Padua-Testsatzes aus Messung 1 suchen**

Run: `git log --oneline --name-status --grep=t_dd94e894 main`
Run: `ls docs/messung tests`
Run: `grep -rln -i "testsatz" docs scripts tests korpus`
Expected: Pfad(e) des Testsatzes und seines Lesers (vermutlich in
`scripts/pruefe_prompts.py`). Notieren: Pfad, Dateiformat (JSONL/JSON/DB),
Feldnamen je Fall, ob Erwartungen (`erwartet`) enthalten sind, wie Messung 1
ihn aufruft (Kommando aus ihrem Bericht). Nichts gefunden → `ACHSE_B = nein`.

- [ ] **Step 3: Gold-Korpus der Zitat-Kette suchen**

Run: `git log --oneline --grep=t_2f905d2c main`
Run: `git log --oneline --name-status --grep=t_2f905d2c main`
Expected: Merge vorhanden **und** eine Datei mit dem Gold-Korpus (positiv:
verwendete Stellen, negativ: vorgeschlagen/verworfen) und ihre Doku. Notieren:
Pfad, Format, Feld für Gruppe (G1/G2/G3), Feld für Stellen-Text oder
-Kennung, Feld für Szene/Figur, wie Recall@10 dort definiert ist. Fehlt der
Merge → `ACHSE_C = nein`.

- [ ] **Step 4: Proxy-Probe `tools` (Abo, 0 CHF)**

Run:
```
curl -s -m 120 http://127.0.0.1:28764/v1/messages -H "content-type: application/json" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-opus-5-5","max_tokens":300,"tools":[{"name":"setze_ort","description":"Setzt den Ort einer Szene.","input_schema":{"type":"object","properties":{"szene":{"type":"integer"},"ort":{"type":"string"}},"required":["szene","ort"]}}],"tool_choice":{"type":"auto"},"messages":[{"role":"user","content":"Szene 2 spielt in der Kueche. Trag das ein."}]}'
```
Expected (wie am 11.10.2026 gemessen): `"stop_reason":"tool_use"` und ein
`content`-Block `{"type":"tool_use","name":"setze_ort","input":{"szene":2,...}}`.
Sonst `PROXY_TOOLS = nein` → Umsetzung stoppen, `kanban_block`.

- [ ] **Step 5: Befund schreiben**

`docs/messung/2026-10-ab-vorbedingungen.md` mit den drei Entscheidungen, den
Kommandos aus Step 1–4 und ihrer Ausgabe (gekürzt). Bei `ACHSE_B = ja`
oder `ACHSE_C = ja`: Format-Abgleich hier festhalten (Feldnamen, Beispielzeile),
Task 7 bzw. 8 liest ihn.

- [ ] **Step 6: Commit**

```bash
git add docs/messung/2026-10-ab-vorbedingungen.md
git commit -m "docs(messung): Vorbedingungen Messung 2 (t_9b2b33cb)"
```

---

### Task 1: Schalter `IT_ERKENNER_MODUS`

**Files:**
- Modify: `interview_theater/einstellungen.py` (`_VORGABEWERTE` Zeile 22ff, Dataclass `Einstellungen` Ende, `laden()` Zeile 161ff)
- Test: `tests/test_erkenner_modus.py` (neu)

**Interfaces:**
- Produces: `einstellungen.ERKENNER_MODI = ("json", "tools")`,
  `einstellungen._erkenner_modus(roh: str | None) -> str`,
  Feld `Einstellungen.erkenner_modus: str = "json"`.

- [ ] **Step 1: Failing test**

```python
"""IT_ERKENNER_MODUS (Karte t_9b2b33cb): json (Vorgabe) | tools."""

from interview_theater import einstellungen

PFLICHT = {
    "IT_BOT_NAME": "gruppe1",
    "IT_DB": "/tmp/egal.db",
    "IT_LLM_URL": "https://example.invalid/chat/completions",
    "IT_LLM_KEY": "k",
    "IT_LLM_MODELL": "m",
    "IT_STT_PRODUKT": "p",
    "IT_BOT_TOKEN": "123:abc",
}


def _umgebung(monkeypatch, **zusatz):
    for name in list(einstellungen._VORGABEWERTE) + [
        "IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS",
    ]:
        monkeypatch.delenv(name, raising=False)
    for name, wert in {**PFLICHT, **zusatz}.items():
        monkeypatch.setenv(name, wert)


def test_vorgabe_ist_json(monkeypatch, einst):
    _umgebung(monkeypatch)
    assert einstellungen.laden().erkenner_modus == "json"
    assert einst.erkenner_modus == "json"


def test_tools_wird_gelesen(monkeypatch):
    _umgebung(monkeypatch, IT_ERKENNER_MODUS=" Tools ")
    assert einstellungen.laden().erkenner_modus == "tools"


def test_unbekannter_wert_faellt_auf_json(monkeypatch, caplog):
    _umgebung(monkeypatch, IT_ERKENNER_MODUS="agent")
    assert einstellungen.laden().erkenner_modus == "json"
    assert "IT_ERKENNER_MODUS" in caplog.text


def test_leer_ist_json():
    assert einstellungen._erkenner_modus("") == "json"
    assert einstellungen._erkenner_modus(None) == "json"
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: ... erkenner_modus`)

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_erkenner_modus.py`

- [ ] **Step 3: Implementierung**

In `einstellungen.py`: oben `import logging` und `log = logging.getLogger(__name__)`;
in `_VORGABEWERTE` `"IT_ERKENNER_MODUS": "json",`; am **Ende** der Dataclass
(Vorgabewert, damit direkte Konstruktionen weiter gelten):

```python
    # Karte t_9b2b33cb (Messung 2): "tools" laesst den Opus-Erkenner die
    # Stueckwerkzeuge selbst rufen statt das JSON-Schema zu fuellen. Wirkt
    # nur, wenn der Erkenner ohnehin ueber Claude laeuft
    # (erkenner.ueber_claude); Vorgabe bleibt "json".
    erkenner_modus: str = "json"
```

Funktion unter `_zahl`:

```python
ERKENNER_MODI = ("json", "tools")


def _erkenner_modus(roh) -> str:
    """``IT_ERKENNER_MODUS``. Ein Tippfehler faellt auf ``json`` zurueck --
    der heutige, gemessene Weg -- und wird geloggt."""
    wert = (roh or "").strip().lower() or "json"
    if wert not in ERKENNER_MODI:
        log.warning("IT_ERKENNER_MODUS=%r unbekannt -- es gilt 'json'", roh)
        return "json"
    return wert
```

In `laden()` im `Einstellungen(...)`-Aufruf: `erkenner_modus=_erkenner_modus(werte["IT_ERKENNER_MODUS"]),`.

- [ ] **Step 4: Run, expect PASS** (4 passed)
- [ ] **Step 5: Commit**

```bash
git add interview_theater/einstellungen.py tests/test_erkenner_modus.py
git commit -m "feat(einstellungen): IT_ERKENNER_MODUS json|tools, Vorgabe json (t_9b2b33cb)"
```

---

### Task 2: `erkenner_werkzeuge.py` — Definitionen, Ausführung, Rückübersetzung

**Files:**
- Create: `interview_theater/erkenner_werkzeuge.py`
- Test: `tests/test_erkenner_werkzeuge.py`

**Interfaces:**
- Consumes: `stueck.WERKZEUGE`, `stueck.QUELLE_AGENT`, `stueck.Ergebnis.als_dict()`.
- Produces:
  - `GENERISCH = "aenderung_melden"`
  - `ART_FUER_WERKZEUG: dict[str, str]`
  - `@dataclass(frozen=True) class Ausfuehrung: name: str; eingabe: dict; ok: bool; ergebnis: dict | None; fehler: str | None; generisch: dict | None`
  - `definitionen(arten: tuple[str, ...]) -> list[dict]`
  - `fuehre_aus(conn, chat_id: int, name: str, eingabe: dict) -> Ausfuehrung`
  - `als_tool_result(a: Ausfuehrung) -> tuple[str, bool]` (Text, `is_error`)
  - `als_aenderung(a: Ausfuehrung) -> dict | None`

- [ ] **Step 1: Failing tests**

```python
import json

import pytest

from interview_theater import erkenner_werkzeuge as ew, repo, stueck

CHAT = 1


def _namen(defs):
    return [d["name"] for d in defs]


def test_definitionen_haben_alle_stueckwerkzeuge_und_generisch():
    defs = ew.definitionen(("interview_starten", "szene_planen"))
    assert _namen(defs) == list(stueck.WERKZEUGE) + [ew.GENERISCH]


def test_schema_aus_signatur_ohne_quelle_und_szene_id():
    defs = {d["name"]: d for d in ew.definitionen(("szene_planen",))}
    ort = defs["setze_ort"]["input_schema"]
    assert ort["type"] == "object"
    assert set(ort["properties"]) == {"szene", "ort"}
    assert ort["properties"]["szene"] == {"type": "integer"}
    assert ort["required"] == []
    karte = defs["karte_aendern"]["input_schema"]
    assert karte["required"] == ["szene"]
    assert karte["properties"]["punkte"] == {"type": "array", "items": {"type": "string"}}
    assert karte["properties"]["zitate"] == {"type": "array", "items": {"type": "integer"}}
    for d in defs.values():
        assert "quelle" not in d["input_schema"]["properties"]
        assert "szene_id" not in d["input_schema"]["properties"]


def test_generisch_enum_ist_die_uebergebene_artenliste():
    defs = {d["name"]: d for d in ew.definitionen(("a", "b"))}
    schema = defs[ew.GENERISCH]["input_schema"]
    assert schema["properties"]["art"]["enum"] == ["a", "b"]
    assert schema["required"] == ["art", "wert"]


def test_fuehre_aus_setze_rahmen_schreibt_mit_quelle_agent(conn):
    a = ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"rahmen": "Ein Bahnhof bei Nacht"})
    assert a.ok is True and a.fehler is None
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Ein Bahnhof bei Nacht"
    text, ist_fehler = ew.als_tool_result(a)
    assert ist_fehler is False
    assert json.loads(text)["ok"] is True


def test_fuehre_aus_unbekanntes_werkzeug_ist_fehler_keine_ausnahme(conn):
    a = ew.fuehre_aus(conn, CHAT, "loesche_alles", {})
    assert a.ok is False and "unbekannt" in a.fehler
    assert ew.als_tool_result(a)[1] is True


def test_fuehre_aus_falsche_argumente_ist_fehler(conn):
    a = ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"falsch": 1})
    assert a.ok is False and a.fehler


def test_fuehre_aus_quelle_aus_dem_modell_wird_ignoriert(conn, monkeypatch):
    gesehen = {}

    def attrappe(conn_, chat_id, **kw):
        gesehen.update(kw)
        return stueck.Ergebnis(ok=True)

    monkeypatch.setattr(stueck, "setze_rahmen", attrappe)
    ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"rahmen": "x", "quelle": "script"})
    assert gesehen["quelle"] == stueck.QUELLE_AGENT


def test_generisch_fuehrt_nichts_aus(conn):
    a = ew.fuehre_aus(conn, CHAT, ew.GENERISCH, {"art": "interview_starten", "wert": ""})
    assert a.ok is True and a.generisch == {"art": "interview_starten", "wert": ""}
    assert ew.als_aenderung(a) == {"art": "interview_starten", "wert": ""}


@pytest.mark.parametrize("name, eingabe, art, teil", [
    ("setze_rahmen", {"rahmen": "Bahnhof"}, "rahmen_setzen", "Bahnhof"),
    ("setze_ort", {"szene": 2, "ort": "Küche"}, "szene_planen", "Küche"),
    ("karte_aendern", {"szene": 1, "worum": "Streit"}, "szene_planen", "Streit"),
    ("figur_hinzu", {"name": "Meryem", "beschreibung": "Mutter"}, "figur_setzen", "Meryem"),
])
def test_als_aenderung_uebersetzt_erfolgreiche_stueckaufrufe(name, eingabe, art, teil):
    a = ew.Ausfuehrung(name=name, eingabe=eingabe, ok=True,
                       ergebnis={"ok": True}, fehler=None, generisch=None)
    aenderung = ew.als_aenderung(a)
    assert aenderung["art"] == art and teil in aenderung["wert"]


def test_als_aenderung_none_bei_ablehnung_und_ohne_korpusart():
    abgelehnt = ew.Ausfuehrung("setze_ort", {"szene": 9, "ort": "x"}, False,
                               {"ok": False}, "keine_szene", None)
    assert ew.als_aenderung(abgelehnt) is None
    frage = ew.Ausfuehrung("frage_stellen", {"frage": "Wer?"}, True, {"ok": True}, None, None)
    assert ew.als_aenderung(frage) is None
```

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError`)

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_erkenner_werkzeuge.py`

- [ ] **Step 3: Implementierung**

```python
"""Die Stueckwerkzeuge als Werkzeuge eines Tool-Calling-Modells (Karte
t_9b2b33cb, Messung 2: Pipeline gegen Agent).

Fachlogik ohne SQL, ohne Modellaufruf, ohne ``tg``. Bindet
``stueck.WERKZEUGE`` (deren Zuschnitt ``(conn, chat_id, *, <JSON-Werte>)``
genau dafuer gebaut ist, ``stueck``-Docstring) plus EIN generisches
Werkzeug ``aenderung_melden`` fuer alle Erkenner-Arten ohne Stueckwerkzeug
(Interview, Phase, Szene schreiben, ...). Das generische fuehrt NICHTS aus:
es sammelt ``{"art", "wert"}`` fuer den heutigen ``erkenner.wende_an``-Weg
mit seinen Waechtern. ``szene_planen`` bleibt dort im Enum, weil kein
Stueckwerkzeug eine NEUE Szene anlegt.

``als_aenderung`` uebersetzt einen Aufruf in die Korpus-Sprache zurueck --
eine Messgrenze, siehe Spec § 2.3."""

from __future__ import annotations

import inspect
import json
import types
import typing
from dataclasses import dataclass

from interview_theater import stueck

GENERISCH = "aenderung_melden"

#: Rueckuebersetzung fuer Korpusvergleich und "Notiert:"-Meldung. Werkzeuge
#: ohne Eintrag (frage_*, szene_wieder_oeffnen, reihenfolge_aendern,
#: pruefe_szene) haben keine Korpus-Art.
ART_FUER_WERKZEUG = {
    "setze_rahmen": "rahmen_setzen",
    "setze_ort": "szene_planen",
    "setze_besetzung": "szene_planen",
    "figur_aus_szene": "szene_planen",
    "karte_aendern": "szene_planen",
    "figur_hinzu": "figur_setzen",
}

_AUSGEBLENDET = ("conn", "chat_id", "quelle", "szene_id")

_BESCHREIBUNG_GENERISCH = (
    "Meldet eine Aenderungsabsicht der Gruppe, fuer die es kein eigenes "
    "Werkzeug gibt (art wie im Erkenner-Prompt, wert als Text)."
)


@dataclass(frozen=True)
class Ausfuehrung:
    name: str
    eingabe: dict
    ok: bool
    ergebnis: dict | None
    fehler: str | None
    generisch: dict | None


def _json_typ(annotation) -> dict:
    herkunft = typing.get_origin(annotation)
    if herkunft in (typing.Union, types.UnionType):
        echte = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _json_typ(echte[0])
    if herkunft is list:
        (inneres,) = typing.get_args(annotation)
        return {"type": "array", "items": _json_typ(inneres)}
    return {int: {"type": "integer"}, str: {"type": "string"},
            bool: {"type": "boolean"}}[annotation]


def _input_schema(funktion) -> dict:
    hinweise = typing.get_type_hints(funktion)
    eigenschaften, pflicht = {}, []
    for name, parameter in inspect.signature(funktion).parameters.items():
        if name in _AUSGEBLENDET or parameter.kind is not parameter.KEYWORD_ONLY:
            continue
        eigenschaften[name] = _json_typ(hinweise[name])
        if parameter.default is parameter.empty:
            pflicht.append(name)
    return {"type": "object", "properties": eigenschaften, "required": pflicht}


def _beschreibung(funktion) -> str:
    text = inspect.getdoc(funktion) or funktion.__name__.replace("_", " ")
    return text.split("\n\n")[0]


def definitionen(arten: tuple[str, ...]) -> list[dict]:
    """Anthropic-``tools``-Liste: je Stueckwerkzeug eine Definition aus der
    Signatur, zuletzt ``aenderung_melden`` mit ``arten`` als Enum."""
    defs = []
    for name in stueck.WERKZEUGE:
        funktion = getattr(stueck, name)
        defs.append({"name": name, "description": _beschreibung(funktion),
                     "input_schema": _input_schema(funktion)})
    defs.append({
        "name": GENERISCH,
        "description": _BESCHREIBUNG_GENERISCH,
        "input_schema": {
            "type": "object",
            "properties": {"art": {"type": "string", "enum": list(arten)},
                           "wert": {"type": "string"}},
            "required": ["art", "wert"],
        },
    })
    return defs


def fuehre_aus(conn, chat_id: int, name: str, eingabe: dict) -> Ausfuehrung:
    """Fuehrt EINEN Werkzeugaufruf aus. Nie eine Ausnahme nach aussen: ein
    falscher Name oder falsche Argumente werden ein ``Ausfuehrung(ok=False)``,
    das das Modell im ``tool_result`` sieht."""
    eingabe = dict(eingabe or {})
    if name == GENERISCH:
        generisch = {"art": str(eingabe.get("art", "")), "wert": str(eingabe.get("wert", ""))}
        return Ausfuehrung(name, eingabe, True, {"ok": True, "vorgemerkt": True}, None, generisch)
    if name not in stueck.WERKZEUGE:
        return Ausfuehrung(name, eingabe, False, None, f"Werkzeug {name!r} unbekannt", None)
    argumente = {k: v for k, v in eingabe.items() if k not in _AUSGEBLENDET}
    try:
        ergebnis = getattr(stueck, name)(conn, chat_id, **argumente,
                                         quelle=stueck.QUELLE_AGENT)
    except TypeError as fehler:
        return Ausfuehrung(name, eingabe, False, None, f"Argumente: {fehler}", None)
    daten = ergebnis.als_dict()
    return Ausfuehrung(name, eingabe, bool(ergebnis.ok), daten, ergebnis.fehler, None)


def als_tool_result(a: Ausfuehrung) -> tuple[str, bool]:
    """Text und ``is_error`` des ``tool_result``-Blocks."""
    if a.ergebnis is None:
        return json.dumps({"ok": False, "fehler": a.fehler}, ensure_ascii=False), True
    return json.dumps(a.ergebnis, ensure_ascii=False), not a.ok


def als_aenderung(a: Ausfuehrung) -> dict | None:
    """``{"art", "wert"}`` in der Korpus-Sprache, oder ``None`` (abgelehnt
    oder Werkzeug ohne Korpus-Art)."""
    if a.generisch is not None:
        return dict(a.generisch)
    if not a.ok or a.name not in ART_FUER_WERKZEUG:
        return None
    teile = [str(v) for v in a.eingabe.values() if isinstance(v, (str, int))]
    teile += [str(x) for v in a.eingabe.values() if isinstance(v, list) for x in v]
    return {"art": ART_FUER_WERKZEUG[a.name], "wert": " ".join(teile)}
```

Hinweis: Wirft ein Stückwerkzeug eine andere Ausnahme als `TypeError`, ist
das ein Fehler in `stueck` und soll laut werden (keine breite `except`).
Falls `typing.get_type_hints` an einer Annotation scheitert, die hier nicht
vorkommt (`dict`), den Test `test_schema_aus_signatur…` erweitern und
`_json_typ` um genau diesen Typ ergänzen — nicht raten.

- [ ] **Step 4: Run, expect PASS** (alle Tests der Datei)
- [ ] **Step 5: `stueck`-Tests unverändert grün**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_stueck_schnittstelle.py`
Expected: PASS, `git diff --stat main -- interview_theater/stueck.py tests/test_stueck_*` leer.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/erkenner_werkzeuge.py tests/test_erkenner_werkzeuge.py
git commit -m "feat(erkenner_werkzeuge): Stueckwerkzeuge als Tool-Definitionen (t_9b2b33cb)"
```

---

### Task 3: `szene_claude.werkzeug_schleife` — die deterministische Tool-Schleife

**Files:**
- Modify: `interview_theater/szene_claude.py` (neu unter `schema`, vor `_json_nach_schluessel`; `prosa`/`schema` unverändert)
- Test: `tests/test_szene_claude_werkzeuge.py`

**Interfaces:**
- Consumes: `szene_claude._buche`, `URL_VORGABE`, `MODELL_VORGABE`, `API_VERSION`, `ClaudeFehler`, `kosten.pruefe`.
- Produces:
  - `MAX_RUNDEN = 6`, `GESAMT_TIMEOUT_S = 120.0`, `WERKZEUG_MAX_TOKENS = 4_000`
  - `@dataclass(frozen=True) class Schleifenergebnis: aufrufe: tuple[dict, ...]; runden: int; abbruch: str | None; eingabe_token: int; ausgabe_token: int; dauer_ms: int; text: str`
    (`aufrufe`-Einträge: `{"name", "eingabe", "is_error"}`; `abbruch` ∈ `None | "runden" | "aufrufe" | "zeit" | "fehler"`)
  - `werkzeug_schleife(conn, e, klient, chat_id, system: str, nutzer: str, werkzeuge: list[dict], ausfuehren: Callable[[str, dict], tuple[str, bool]], *, art: str, modell: str | None = None, max_runden: int = MAX_RUNDEN, max_aufrufe: int = 5, gesamt_timeout: float = GESAMT_TIMEOUT_S, uhr: Callable[[], float] = time.monotonic) -> Schleifenergebnis`
  - Wirft `ClaudeFehler` **nur**, wenn der **erste** Modellaufruf scheitert (dann ist nichts ausgeführt → Aufrufer darf auf JSON zurückfallen).

- [ ] **Step 1: Failing tests**

```python
import json

import dataclasses
import httpx
import pytest

from interview_theater import szene_claude

CHAT = 1


@pytest.fixture
def opus_e(einst):
    return dataclasses.replace(einst, szene_anbieter="claude")


def _antwort(content, stop, ein=10, aus=5):
    return httpx.Response(200, json={
        "content": content, "stop_reason": stop,
        "usage": {"input_tokens": ein, "output_tokens": aus},
    })


def _tool(i, name="setze_ort", eingabe=None):
    return {"type": "tool_use", "id": f"t{i}", "name": name,
            "input": eingabe or {"szene": 1, "ort": "Küche"}}


def _klient(antworten, koerper):
    folge = iter(antworten)

    def handler(anfrage):
        koerper.append(json.loads(anfrage.content))
        antwort = next(folge)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ausfuehren(protokoll):
    def f(name, eingabe):
        protokoll.append((name, eingabe))
        return json.dumps({"ok": True}), False
    return f


def test_eine_runde_werkzeug_dann_fertig(conn, opus_e):
    koerper, protokoll = [], []
    klient = _klient([_antwort([_tool(1)], "tool_use"),
                      _antwort([{"type": "text", "text": "erledigt"}], "end_turn")], koerper)
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, klient, CHAT, "sys", "nutz", [{"name": "setze_ort"}],
        _ausfuehren(protokoll), art="erkenner")
    assert r.abbruch is None and r.runden == 2 and r.text == "erledigt"
    assert protokoll == [("setze_ort", {"szene": 1, "ort": "Küche"})]
    assert r.eingabe_token == 20 and r.ausgabe_token == 10
    assert koerper[0]["tools"] == [{"name": "setze_ort"}]
    assert koerper[0]["tool_choice"] == {"type": "auto"}
    letzte = koerper[1]["messages"][-1]
    assert letzte["role"] == "user"
    assert letzte["content"][0] == {"type": "tool_result", "tool_use_id": "t1",
                                    "content": '{"ok": true}', "is_error": False}
    zeilen = conn.execute("SELECT modus FROM aufruf WHERE art='erkenner'").fetchall()
    assert [z["modus"] for z in zeilen] == ["C", "C"]


def test_rundendeckel(conn, opus_e):
    antworten = [_antwort([_tool(i)], "tool_use") for i in range(10)]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren([]),
        art="erkenner", max_runden=3, max_aufrufe=99)
    assert r.abbruch == "runden" and r.runden == 3


def test_aufrufdeckel_fuehrt_nicht_mehr_aus(conn, opus_e):
    protokoll = []
    antworten = [_antwort([_tool(1), _tool(2), _tool(3)], "tool_use")]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren(protokoll),
        art="erkenner", max_aufrufe=2)
    assert r.abbruch == "aufrufe" and len(protokoll) == 2
    assert [a["is_error"] for a in r.aufrufe] == [False, False]


def test_zeitdeckel(conn, opus_e):
    zeiten = iter([0.0, 0.0, 500.0, 500.0, 500.0])
    antworten = [_antwort([_tool(1)], "tool_use"), _antwort([_tool(2)], "tool_use")]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren([]),
        art="erkenner", gesamt_timeout=120.0, uhr=lambda: next(zeiten))
    assert r.abbruch == "zeit" and r.runden == 1


def test_erster_aufruf_scheitert_wirft_claudefehler(conn, opus_e):
    klient = _klient([httpx.Response(400, json={})], [])
    with pytest.raises(szene_claude.ClaudeFehler):
        szene_claude.werkzeug_schleife(conn, opus_e, klient, CHAT, "s", "n", [],
                                       _ausfuehren([]), art="erkenner")


def test_spaeterer_fehler_ist_abbruch_kein_wurf(conn, opus_e):
    protokoll = []
    klient = _klient([_antwort([_tool(1)], "tool_use"), httpx.Response(400, json={})], [])
    r = szene_claude.werkzeug_schleife(conn, opus_e, klient, CHAT, "s", "n", [],
                                       _ausfuehren(protokoll), art="erkenner")
    assert r.abbruch == "fehler" and len(protokoll) == 1


def test_prosa_koerper_bleibt_ohne_tools(conn, opus_e):
    koerper = []
    klient = _klient([_antwort([{"type": "text", "text": "x"}], "end_turn")], koerper)
    szene_claude.prosa(conn, opus_e, klient, CHAT, "s", "n", "szene", timeout=5)
    assert "tools" not in koerper[0] and "tool_choice" not in koerper[0]
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: werkzeug_schleife`)

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_szene_claude_werkzeuge.py`

- [ ] **Step 3: Implementierung** (in `szene_claude.py`; `from dataclasses import dataclass` und `from typing import Callable` oben ergänzen)

```python
#: Werkzeugschleife (Karte t_9b2b33cb, Messung 2): Deckel, damit ein
#: Messlauf nie endlos laeuft. Spec § 2.2.
MAX_RUNDEN = 6
GESAMT_TIMEOUT_S = 120.0
WERKZEUG_MAX_TOKENS = 4_000
_TEXT_GRENZE = '{"ok": false, "fehler": "Grenze der Werkzeugaufrufe erreicht"}'


@dataclass(frozen=True)
class Schleifenergebnis:
    aufrufe: tuple[dict, ...]
    runden: int
    abbruch: str | None
    eingabe_token: int
    ausgabe_token: int
    dauer_ms: int
    text: str


def werkzeug_schleife(conn, e, klient: httpx.Client, chat_id: int | None, system: str,
                      nutzer: str, werkzeuge: list[dict],
                      ausfuehren: Callable[[str, dict], tuple[str, bool]], *,
                      art: str, modell: str | None = None, max_runden: int = MAX_RUNDEN,
                      max_aufrufe: int = 5, gesamt_timeout: float = GESAMT_TIMEOUT_S,
                      uhr: Callable[[], float] = time.monotonic) -> Schleifenergebnis:
    """Der dritte Aufrufmodus neben ``prosa`` und ``schema``: Modell ->
    ``tool_use`` -> ``ausfuehren`` -> ``tool_result`` -> Modell, bis das
    Modell fertig ist oder ein Deckel greift. Blockierend, je Runde eine
    ``aufruf``-Zeile (modus 'C', 0 CHF). Kein Wiederholungsversuch: eine
    wiederholte Runde koennte Werkzeuge doppelt ausfuehren.

    Wirft ``ClaudeFehler`` nur, wenn die ERSTE Runde scheitert -- dann ist
    noch nichts ausgefuehrt und der Aufrufer darf auf den JSON-Weg
    zurueckfallen. Spaeter ist schon geschrieben: ``abbruch="fehler"``."""
    kosten.pruefe(conn, chat_id, e)
    url = getattr(e, "szene_url", None) or URL_VORGABE
    modell = modell or getattr(e, "szene_modell", None) or MODELL_VORGABE
    headers = {"content-type": "application/json", "anthropic-version": API_VERSION}
    nachrichten: list[dict] = [{"role": "user", "content": nutzer}]
    aufrufe: list[dict] = []
    ein = aus = runden = 0
    abbruch, text = None, ""
    start = uhr()
    while True:
        if runden >= max_runden:
            abbruch = "runden"
            break
        if uhr() - start > gesamt_timeout:
            abbruch = "zeit"
            break
        koerper = {
            "model": modell, "max_tokens": WERKZEUG_MAX_TOKENS,
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],
            "tools": werkzeuge, "tool_choice": {"type": "auto"},
            "messages": nachrichten,
        }
        runde_start = time.monotonic()
        try:
            restzeit = max(1.0, gesamt_timeout - (uhr() - start))
            daten = _blockierend(klient, url, headers, koerper, restzeit)
        except (httpx.HTTPError, ValueError) as fehler:
            _buche(conn, chat_id, e, art, modell, {}, "werkzeug_fehler",
                   time.monotonic() - runde_start, erfolg=False)
            if runden == 0:
                raise ClaudeFehler(f"Werkzeugschleife, erste Runde: {fehler}") from fehler
            abbruch = "fehler"
            break
        runden += 1
        nutzung = daten.get("usage") or {}
        ein += int(nutzung.get("input_tokens") or 0)
        aus += int(nutzung.get("output_tokens") or 0)
        stop = daten.get("stop_reason")
        _buche(conn, chat_id, e, art, modell, nutzung, stop,
               time.monotonic() - runde_start, erfolg=True)
        inhalt = daten.get("content") or []
        text = "".join(b.get("text", "") for b in inhalt if b.get("type") == "text")
        werkzeug_bloecke = [b for b in inhalt if b.get("type") == "tool_use"]
        if stop != "tool_use" or not werkzeug_bloecke:
            break
        nachrichten.append({"role": "assistant", "content": inhalt})
        ergebnisse = []
        for block in werkzeug_bloecke:
            if len(aufrufe) >= max_aufrufe:
                abbruch = "aufrufe"
                ergebnisse.append({"type": "tool_result", "tool_use_id": block["id"],
                                   "content": _TEXT_GRENZE, "is_error": True})
                continue
            ergebnis_text, ist_fehler = ausfuehren(block["name"], block.get("input") or {})
            aufrufe.append({"name": block["name"], "eingabe": block.get("input") or {},
                            "is_error": ist_fehler})
            ergebnisse.append({"type": "tool_result", "tool_use_id": block["id"],
                               "content": ergebnis_text, "is_error": ist_fehler})
        nachrichten.append({"role": "user", "content": ergebnisse})
        if abbruch == "aufrufe":
            break
    return Schleifenergebnis(tuple(aufrufe), runden, abbruch, ein, aus,
                             int((uhr() - start) * 1000), text)
```

- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Bestehende Claude-Tests unverändert grün**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_modellwahl.py tests/test_szene_claude_strom.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/szene_claude.py tests/test_szene_claude_werkzeuge.py
git commit -m "feat(szene_claude): werkzeug_schleife mit Runden-, Aufruf- und Zeitdeckel (t_9b2b33cb)"
```

---

### Task 4: Erkenner im Tools-Modus

**Files:**
- Modify: `interview_theater/erkenner.py` (`erkenne` Zeile 487–565, neue Funktionen darunter; `laufe` Zeile 3764 und 3872)
- Create: `interview_theater/prompts/erkenner_werkzeuge.md`, `interview_theater/sprachen/en/prompts/erkenner_werkzeuge.md`
- Test: `tests/test_erkenner_tools_modus.py`

**Interfaces:**
- Consumes: `erkenner_werkzeuge.definitionen/fuehre_aus/als_tool_result/als_aenderung/GENERISCH`, `szene_claude.werkzeug_schleife/ClaudeFehler`, `einstellungen.Einstellungen.erkenner_modus`.
- Produces:
  - `erkenner.aktive_arten() -> tuple[str, ...]` (Enum aus `schema()`)
  - `erkenner.werkzeug_modus(e, conn, chat_id) -> bool` = `getattr(e, "erkenner_modus", "json") == "tools" and ueber_claude(e, conn, chat_id)`
  - `erkenner.erkenne_mit_werkzeugschritten(klm, conn, e, chat_id) -> tuple[list[dict], list[dict]]`
  - `erkenner._werkzeuglauf(conn, e, chat_id, nutzer) -> tuple[list[dict], list[dict], "szene_claude.Schleifenergebnis", list["erkenner_werkzeuge.Ausfuehrung"]]` (generische Änderungen, Stück-Schritte, Schleifenergebnis, alle Ausführungen — die letzten beiden braucht das Messskript)
  - `erkenne(...)` unverändert in Signatur und Rückgabe.

- [ ] **Step 1: Prompt-Absätze anlegen**

`interview_theater/prompts/erkenner_werkzeuge.md`:

```markdown
## Werkzeuge statt Liste

Du lieferst keine JSON-Liste. Du rufst Werkzeuge.

- Ort, Besetzung, Karte einer BESTEHENDEN Szene, Rahmen, Figuren, offene
  Fragen: das passende Stueckwerkzeug (setze_ort, setze_besetzung,
  karte_aendern, setze_rahmen, figur_hinzu, frage_stellen, ...).
- Alles andere aus der Liste der Arten oben -- und eine NEUE Szene
  (szene_planen) -- meldest du mit aenderung_melden(art, wert).
- Lehnt ein Werkzeug ab (ok: false), lies den Fehler. Versuche es hoechstens
  einmal anders; sonst lass es.
- Dieselben Regeln wie oben: im Zweifel KEIN Aufruf. Hoechstens fuenf
  Aufrufe. Gibt es nichts zu tun, antworte mit einem Wort: nichts.
```

`interview_theater/sprachen/en/prompts/erkenner_werkzeuge.md`: dieselben vier
Punkte auf Englisch („## Tools instead of a list“ …, „When in doubt, NO call.
At most five calls. If there is nothing to do, answer with one word: nothing.“).

- [ ] **Step 2: Failing tests**

```python
import dataclasses

import httpx
import pytest

from interview_theater import erkenner, modellwahl, repo, szene_claude, workshop
from interview_theater.szene_claude import Schleifenergebnis

CHAT = 1


@pytest.fixture
def tools_e(einst):
    return dataclasses.replace(einst, szene_anbieter="claude", erkenner_modus="tools")


@pytest.fixture
def ueber_claude_an(monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: True)
    monkeypatch.setattr(modellwahl, "konversation_ueber_claude", lambda e, c, ch: True)


def _nachricht(conn, text, mid=10):
    repo.speichere_nachricht(conn, CHAT, mid, "Sara", text)


class KlmVerboten:
    def schema(self, *a, **k):
        raise AssertionError("JSON-Pfad darf im Tools-Modus nicht laufen")


def _schleife(aufrufe_und_ergebnisse):
    """Attrappe fuer szene_claude.werkzeug_schleife: ruft ``ausfuehren`` mit
    den vorgegebenen Aufrufen, wie es das Modell taete."""
    def schleife(conn, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        protokoll = []
        for name, eingabe in aufrufe_und_ergebnisse:
            text, fehler = ausfuehren(name, eingabe)
            protokoll.append({"name": name, "eingabe": eingabe, "is_error": fehler})
        return Schleifenergebnis(tuple(protokoll), 2, None, 10, 5, 1, "")
    return schleife


def test_json_ist_vorgabe_und_nutzt_schema_aufruf(conn, einst, ueber_claude_an, monkeypatch):
    assert erkenner.werkzeug_modus(einst, conn, CHAT) is False


def test_tools_ohne_ueber_claude_bleibt_json(conn, tools_e, monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: False)
    assert erkenner.werkzeug_modus(tools_e, conn, CHAT) is False


def test_tools_modus_schreibt_ueber_stueck_und_sammelt_generisches(
        conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "der Rahmen ist ein Bahnhof bei Nacht, und wir machen jetzt ein Interview")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("setze_rahmen", {"rahmen": "Bahnhof bei Nacht"}),
        ("aenderung_melden", {"art": "interview_starten", "wert": ""}),
    ]))
    aenderungen, schritte = erkenner.erkenne_mit_werkzeugschritten(
        KlmVerboten(), conn, tools_e, CHAT)
    assert aenderungen == [{"art": "interview_starten", "wert": ""}]
    assert schritte == [{"art": "rahmen_setzen", "wert": "Bahnhof bei Nacht"}]
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Bahnhof bei Nacht"
    assert repo.unextrahierte(conn, CHAT) == []


def test_unbekannte_art_aus_generisch_wird_verworfen(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "egal")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("aenderung_melden", {"art": "gibt_es_nicht", "wert": "x"}),
    ]))
    assert erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT) == []


def test_erste_runde_scheitert_faellt_auf_json_zurueck(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "wir machen jetzt ein Interview")

    def kaputt(*a, **k):
        raise szene_claude.ClaudeFehler("proxy weg")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", kaputt)
    gesehen = {}

    def schema_aufruf(klm, conn_, e, chat_id, system, nutzer, schema_, art):
        gesehen["ja"] = True
        return {"aenderungen": [{"art": "interview_starten", "wert": ""}]}

    monkeypatch.setattr(erkenner, "_schema_aufruf", schema_aufruf)
    aenderungen, schritte = erkenner.erkenne_mit_werkzeugschritten(
        KlmVerboten(), conn, tools_e, CHAT)
    assert gesehen["ja"] and aenderungen == [{"art": "interview_starten", "wert": ""}]
    assert schritte == []
    vorfaelle = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "erkenner_werkzeug_fallback" in vorfaelle


def test_abbruch_wird_als_vorfall_gemeldet(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "x")

    def schleife(*a, **k):
        return Schleifenergebnis((), 6, "runden", 1, 1, 1, "")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT)
    vorfaelle = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "erkenner_werkzeug_abbruch" in vorfaelle


def test_werkzeug_prompt_haengt_am_erkenner_prompt(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "x")
    gesehen = {}

    def schleife(conn_, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        gesehen["system"], gesehen["werkzeuge"] = system, werkzeuge
        return Schleifenergebnis((), 1, None, 1, 1, 1, "nichts")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT)
    assert gesehen["system"].startswith(erkenner.prompt())
    assert "aenderung_melden" in gesehen["system"]
    assert gesehen["werkzeuge"][-1]["input_schema"]["properties"]["art"]["enum"] == list(
        erkenner.aktive_arten())
```

Hinweis für die Umsetzung: `repo.speichere_nachricht` und die Spalte
`vorfall.art` sind vor dem Lauf mit
`grep -n "^def speichere_nachricht\|^def merke_vorfall" interview_theater/repo.py`
und `grep -n "CREATE TABLE IF NOT EXISTS vorfall" -A8 interview_theater/db.py`
zu prüfen; heißen sie anders, die Tests an die echten Namen anpassen (die
Bedeutung bleibt).

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_erkenner_tools_modus.py`

- [ ] **Step 4: Implementierung in `erkenner.py`**

Unter `schema()`:

```python
def aktive_arten() -> tuple[str, ...]:
    """Das Arten-Enum des aktiven Profils -- dieselbe Liste fuer den
    JSON-Weg und fuer ``aenderung_melden`` im Tools-Modus."""
    return tuple(schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"])
```

`erkenne` wird zur Hülle, der bisherige Rumpf wandert nach
`erkenne_mit_werkzeugschritten`; einzige Änderung im Rumpf ist die
Verzweigung vor `_schema_aufruf`:

```python
def erkenne(klm, conn, e, chat_id: int) -> list[dict]:
    """<bisheriger Docstring unveraendert>"""
    return erkenne_mit_werkzeugschritten(klm, conn, e, chat_id)[0]


def erkenne_mit_werkzeugschritten(klm, conn, e, chat_id: int) -> tuple[list[dict], list[dict]]:
    """Wie ``erkenne``, zusaetzlich die im Tools-Modus (``IT_ERKENNER_MODUS=
    tools``) schon ueber ``stueck`` geschriebenen Schritte, rueckuebersetzt
    (``erkenner_werkzeuge.als_aenderung``) -- fuer die "Notiert:"-Meldung.
    Im JSON-Modus ist die zweite Liste immer leer."""
    # ... bisheriger Rumpf bis einschliesslich Fenster-Deckel, dort
    #     "return []" -> "return [], []" ...
    schritte: list[dict] = []
    ergebnis = None
    if werkzeug_modus(e, conn, chat_id):
        try:
            generisch, schritte, _, _ = _werkzeuglauf(conn, e, chat_id, nutzer)
            ergebnis = {"aenderungen": generisch}
        except szene_claude_fehler() as fehler:
            log.warning("Werkzeugschleife, erste Runde gescheitert -- JSON-Weg: %s", fehler)
            repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                               "erkenner_werkzeug_fallback", str(fehler)[:200])
    if ergebnis is None:
        try:
            ergebnis = _schema_aufruf(klm, conn, e, chat_id, prompt(), nutzer, schema(), "erkenner")
        except Exception:
            # ... bisheriger except-Block, "return []" -> "return [], []" ...
    # ... bisherige Schleife ueber ergebnis["aenderungen"] (ARTEN-Filter,
    #     MAX_AENDERUNGEN), setze_extrahiert_bis ...
    return aenderungen, schritte
```

Darunter:

```python
def szene_claude_fehler():
    from interview_theater import szene_claude
    return szene_claude.ClaudeFehler


def werkzeug_modus(e, conn, chat_id) -> bool:
    """Tools-Modus nur mit ``IT_ERKENNER_MODUS=tools`` UND wenn der Erkenner
    ohnehin ueber Claude laeuft (``ueber_claude``: Profilschalter,
    Einwilligung, NICHT Phase 3)."""
    if getattr(e, "erkenner_modus", "json") != "tools":
        return False
    return ueber_claude(e, conn, chat_id)


def _werkzeuglauf(conn, e, chat_id, nutzer):
    """Eine Werkzeugschleife ueber den Claude-Proxy. Liefert
    ``(generische, stueck_schritte, schleifenergebnis, ausfuehrungen)``.
    ``ClaudeFehler`` (erste Runde) geht an den Aufrufer."""
    import httpx

    from interview_theater import anweisungen, erkenner_werkzeuge, szene_claude

    ausfuehrungen: list = []

    def ausfuehren(name, eingabe):
        a = erkenner_werkzeuge.fuehre_aus(conn, chat_id, name, eingabe)
        ausfuehrungen.append(a)
        return erkenner_werkzeuge.als_tool_result(a)

    system = prompt() + "\n\n" + anweisungen.hole("erkenner_werkzeuge")
    with httpx.Client(timeout=szene_claude.GESAMT_TIMEOUT_S) as klient:
        lauf = szene_claude.werkzeug_schleife(
            conn, e, klient, chat_id, system, nutzer,
            erkenner_werkzeuge.definitionen(aktive_arten()), ausfuehren,
            art="erkenner",
            modell=getattr(e, "szene_modell", None) or "claude-opus-5-5",
            max_aufrufe=MAX_AENDERUNGEN,
        )
    if lauf.abbruch is not None:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                           "erkenner_werkzeug_abbruch",
                           f"abbruch={lauf.abbruch}, runden={lauf.runden}, "
                           f"aufrufe={len(lauf.aufrufe)}")
    generisch = [a.generisch for a in ausfuehrungen if a.generisch is not None]
    schritte = [x for x in (erkenner_werkzeuge.als_aenderung(a) for a in ausfuehrungen
                            if a.generisch is None) if x is not None]
    return generisch, schritte, lauf, ausfuehrungen
```

In `laufe` (Zeile 3764): `aenderungen = erkenne(klm, conn, e, chat_id)` →
`aenderungen, werkzeugschritte = erkenne_mit_werkzeugschritten(klm, conn, e, chat_id)`.
Die Bedingung `if not aenderungen: return` (Zeile 3781) wird zu
`if not aenderungen and not werkzeugschritte: return`. Vor
`text = baue_meldung(wirkliche, conn, chat_id)` (Zeile 3872):
`wirkliche = wirkliche + werkzeugschritte` — **nach** allen `_starte_*`,
damit kein Startweg die Stück-Schritte als neue Aufträge liest, aber vor
`baue_meldung`. Kommentar dazu: „Undo deckt die Werkzeugschritte nicht ab
(Spec § 3.4) — sie stehen im `stueck`-Änderungsprotokoll.“

- [ ] **Step 5: Test `laufe` meldet Werkzeugschritte** (an `tests/test_erkenner_tools_modus.py` anhängen)

```python
def test_laufe_nennt_werkzeugschritt_in_der_notiert_meldung(
        conn, tools_e, ueber_claude_an, monkeypatch):
    from tests.test_erkenner import TgAttrappe  # vorhandene Attrappe; Name vorab per grep pruefen

    _nachricht(conn, "der Rahmen ist ein Bahnhof bei Nacht")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("setze_rahmen", {"rahmen": "Bahnhof bei Nacht"}),
    ]))
    tg = TgAttrappe()
    erkenner.laufe(KlmVerboten(), tg, conn, tools_e, CHAT)
    assert any("Bahnhof bei Nacht" in t for t in tg.texte())
```

Vor dem Schreiben: `grep -n "^class .*Tg\|def texte\|gesendet" tests/test_erkenner.py`
— die vorhandene Telegram-Attrappe und ihr Lese-Attribut verwenden.

- [ ] **Step 6: Run, expect PASS**; danach Bestand:

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_erkenner_tools_modus.py tests/test_erkenner.py tests/test_erkenner_teil2.py tests/test_pruefe_prompts.py`
Expected: PASS (JSON-Modus unverändert).

- [ ] **Step 7: Prompt-Snapshot Padua unverändert**

Run: `grep -rln "schnappschuss\|snapshot" tests | head -5` → den Padua-Prompt-Snapshot-Test gezielt laufen lassen.
Expected: PASS ohne neue Fixture.

- [ ] **Step 8: Commit**

```bash
git add interview_theater/erkenner.py interview_theater/prompts/erkenner_werkzeuge.md interview_theater/sprachen/en/prompts/erkenner_werkzeuge.md tests/test_erkenner_tools_modus.py
git commit -m "feat(erkenner): IT_ERKENNER_MODUS=tools -- Opus ruft Stueckwerkzeuge (t_9b2b33cb)"
```

---

### Task 5: Datenschutz-Tests in beiden Modi

**Files:**
- Test: `tests/test_erkenner_tools_datenschutz.py`

**Interfaces:**
- Consumes: `erkenner.werkzeug_modus`, `erkenner.erkenne_in_aufnahme`, `modellwahl.konversation_ueber_claude`, `verdichter`.

- [ ] **Step 1: Tests**

```python
"""Interviews bleiben hart auf Infomaniak -- in BEIDEN Erkenner-Modi
(Spec § 4; modellwahl.konversation_ueber_claude, PHASE_INTERVIEWS)."""

import ast
import dataclasses
from pathlib import Path

import pytest

from interview_theater import erkenner, repo, szene_claude, workshop

CHAT = 1
WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture(params=["json", "tools"])
def e_modus(request, einst):
    return dataclasses.replace(einst, szene_anbieter="claude", erkenner_modus=request.param)


@pytest.fixture
def schalter_an(monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: True)


def test_phase_3_nie_ueber_claude_in_beiden_modi(conn, e_modus, schalter_an):
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_szene_usa(conn, CHAT, True)
    assert erkenner.ueber_claude(e_modus, conn, CHAT) is False
    assert erkenner.werkzeug_modus(e_modus, conn, CHAT) is False


def test_phase_3_erkenne_ruft_keinen_proxy(conn, e_modus, schalter_an, monkeypatch):
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_szene_usa(conn, CHAT, True)
    repo.speichere_nachricht(conn, CHAT, 10, "Sara", "wir machen jetzt ein Interview")

    def verboten(*a, **k):
        raise AssertionError("Proxy in Phase 3")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", verboten)
    monkeypatch.setattr(szene_claude, "schema", verboten)

    class Klm:
        def schema(self, *a, **k):
            return {"aenderungen": [{"art": "interview_starten", "wert": ""}]}

    assert erkenner.erkenne(Klm(), conn, e_modus, CHAT) == [
        {"art": "interview_starten", "wert": ""}]


def test_aufnahme_erkenner_nie_ueber_claude(conn, e_modus, schalter_an, monkeypatch):
    repo.setze_phase(conn, CHAT, 5)

    def verboten(*a, **k):
        raise AssertionError("Transkript ueber den Proxy")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", verboten)
    monkeypatch.setattr(szene_claude, "schema", verboten)

    class Klm:
        def schema(self, *a, **k):
            return {"aenderungen": []}

    assert erkenner.erkenne_in_aufnahme(Klm(), conn, e_modus, CHAT, "so das wars") == []


def test_verdichter_kennt_weder_werkzeuge_noch_proxy():
    baum = ast.parse((WURZEL / "interview_theater" / "verdichter.py").read_text(encoding="utf-8"))
    namen = {n.id for n in ast.walk(baum) if isinstance(n, ast.Name)}
    namen |= {n.attr for n in ast.walk(baum) if isinstance(n, ast.Attribute)}
    assert not {"erkenner_werkzeuge", "werkzeug_schleife", "szene_claude"} & namen
```

- [ ] **Step 2: Run, expect PASS** (8 Tests: 3×2 parametrisiert + 1; schlägt einer fehl, ist Task 4 falsch — dort beheben, nicht hier)

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_erkenner_tools_datenschutz.py`

- [ ] **Step 3: Commit**

```bash
git add tests/test_erkenner_tools_datenschutz.py
git commit -m "test(datenschutz): Phase 3, Aufnahme, Verdichter hart auf Infomaniak in json und tools (t_9b2b33cb)"
```

---

### Task 6: Messskript Achse A — Erkenner-Korpus, json gegen tools

**Files:**
- Create: `scripts/ab_pipeline_vs_tools.py`
- Test: `tests/test_ab_pipeline_vs_tools.py`

**Interfaces:**
- Consumes: `scripts.pruefe_prompts.lade_korpus/_fuelle_arbeitsstand/_nachrichtenzeilen/vergleiche_erkenner`, `erkenner._baue_nutzertext/baue_aufnahme_nutzertext/prompt/schema/aktive_arten/waechter_filter/MAX_AENDERUNGEN/ARTEN_IN_AUFNAHME/_werkzeuglauf`, `szene_claude.schema`.
  (Nach Merge von Messung 1 kann `pruefe_prompts` umgebaut sein — in Task 0 festgestellt; Namen hier dann angleichen.)
- Produces:
  - `ROH_VERZ = Path("korpus/berichte/ab")`
  - `nutzertext_fuer(conn, chat_id, fall) -> str`
  - `laufe_json(conn, e, klient, chat_id, fall) -> dict`
  - `laufe_tools(conn, e, chat_id, fall) -> dict`
  - Zeilenformat (eine JSONL-Zeile je Fall und Modus):
    `{"achse": "A", "sprache", "modus": "json"|"tools", "id", "treffer", "fp", "fn", "still_fp", "ohne_korpusart", "abgelehnt", "abbruch", "runden", "eingabe_token", "ausgabe_token", "dauer_ms", "fehler", "geliefert", "aufrufe"}`
  - CLI: `python -m scripts.ab_pipeline_vs_tools erkenner --sprache de|en --modus json|tools|beide [--nur ID ...] [--db PFAD] [--aus DATEI.jsonl]`

- [ ] **Step 1: Failing tests** (Attrappen statt Proxy; kein Netz)

```python
import json

import pytest

from interview_theater import erkenner, erkenner_werkzeuge as ew, szene_claude
from interview_theater.szene_claude import Schleifenergebnis
from scripts import ab_pipeline_vs_tools as ab

FALL = {"id": "x1", "arbeitsstand": {}, "nachrichten": [
    {"absender": "Sara", "text": "wir machen jetzt ein Interview"}],
    "erwartet": [{"art": "interview_starten", "wert": ""}]}


def test_json_zaehlt_wie_der_korpus(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": [
        {"art": "interview_starten", "wert": ""}, {"art": "verworfen", "wert": "x"}]})
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert (z["modus"], z["treffer"], z["fp"], z["fn"]) == ("json", 1, 1, 0)
    assert z["still_fp"] == 1 and z["abgelehnt"] == 0


def test_tools_uebersetzt_und_trennt_still_und_laut(conn, einst, monkeypatch):
    ausf = [
        ew.Ausfuehrung(ew.GENERISCH, {"art": "interview_starten", "wert": ""}, True,
                       {"ok": True}, None, {"art": "interview_starten", "wert": ""}),
        ew.Ausfuehrung("setze_ort", {"szene": 9, "ort": "x"}, False, {"ok": False},
                       "keine_szene", None),
        ew.Ausfuehrung("frage_stellen", {"frage": "Wer?"}, True, {"ok": True}, None, None),
    ]
    lauf = Schleifenergebnis((), 2, None, 100, 20, 900, "")
    monkeypatch.setattr(erkenner, "_werkzeuglauf",
                        lambda conn_, e, ch, n: ([ausf[0].generisch], [], lauf, ausf))
    z = ab.laufe_tools(conn, einst, 1, FALL)
    assert (z["modus"], z["treffer"], z["fp"], z["fn"]) == ("tools", 1, 0, 0)
    assert z["abgelehnt"] == 1 and z["ohne_korpusart"] == 1
    assert z["still_fp"] == 1          # fp 0 + ohne_korpusart 1
    assert (z["runden"], z["eingabe_token"], z["dauer_ms"]) == (2, 100, 900)


def test_zeile_ist_jsonl_tauglich(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": []})
    json.dumps(ab.laufe_json(conn, einst, None, 1, FALL))


def test_fehler_im_fall_bricht_den_lauf_nicht(conn, einst, monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(szene_claude, "schema", kaputt)
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert "boom" in z["fehler"] and z["treffer"] == 0


def test_cli_kennt_keinen_automatiklauf():
    with pytest.raises(SystemExit):
        ab.main([])
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_ab_pipeline_vs_tools.py`

- [ ] **Step 3: Implementierung**

```python
"""Messung 2 (Karte t_9b2b33cb): Pipeline gegen Agent auf denselben Daten.

Achse A: der Erkenner-Korpus (korpus/erkenner.jsonl, korpus/en/erkenner.jsonl)
einmal ueber den heutigen JSON-Weg (Opus fuellt das Schema), einmal im
Tools-Modus (Opus ruft die Stueckwerkzeuge). Beide ueber den Abo-Proxy
(0 CHF). Gezaehlt wird mit dem unveraenderten
``pruefe_prompts.vergleiche_erkenner`` -- die Tools-Seite wird dafuer in die
Korpus-Sprache zurueckuebersetzt (``erkenner_werkzeuge.als_aenderung``,
Spec § 2.3).

Laeuft NIE automatisch. Start (als Modul):
  uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx

from interview_theater import db, einstellungen, erkenner, erkenner_werkzeuge, repo, szene_claude
from scripts import pruefe_prompts as pp

ROH_VERZ = Path("korpus/berichte/ab")
OPUS = "claude-opus-5-5"


def nutzertext_fuer(conn, chat_id: int, fall: dict) -> str:
    """Derselbe Nutzertext wie ``pruefe_prompts._laufe_erkenner``."""
    if fall.get("aufnahme"):
        return erkenner.baue_aufnahme_nutzertext(fall["aufnahme"])
    pp._fuelle_arbeitsstand(conn, chat_id, fall.get("arbeitsstand"))
    zeilen = pp._nachrichtenzeilen(fall["nachrichten"])
    vorlauf = None
    if fall.get("vorlauf"):
        vorlauf = pp._nachrichtenzeilen([{"absender": "Bot", "text": fall["vorlauf"]}])[0]
    elif len(zeilen) > 1 and zeilen[0]["ist_bot"]:
        vorlauf, zeilen = zeilen[0], zeilen[1:]
    return erkenner._baue_nutzertext(conn, chat_id, zeilen, vorlauf)


def _filter(fall: dict, geliefert: list[dict]) -> list[dict]:
    geliefert = geliefert[: erkenner.MAX_AENDERUNGEN]
    if fall.get("aufnahme"):
        geliefert = [a for a in geliefert if a.get("art") in erkenner.ARTEN_IN_AUFNAHME]
    return erkenner.waechter_filter(geliefert)


def _leer(modus: str, fall: dict) -> dict:
    return {"achse": "A", "modus": modus, "id": fall["id"], "treffer": 0, "fp": 0,
            "fn": len(fall.get("erwartet", [])), "still_fp": 0, "ohne_korpusart": 0,
            "abgelehnt": 0, "abbruch": None, "runden": 0, "eingabe_token": 0,
            "ausgabe_token": 0, "dauer_ms": 0, "fehler": None, "geliefert": [],
            "aufrufe": []}


def _zaehle(zeile: dict, fall: dict, geliefert: list[dict]) -> dict:
    bewertung = pp.vergleiche_erkenner(fall["erwartet"], geliefert)
    zeile.update(treffer=len(bewertung["treffer"]), fp=len(bewertung["ueberzaehlig"]),
                 fn=len(bewertung["fehlend"]), geliefert=geliefert)
    return zeile


def laufe_json(conn, e, klient, chat_id: int, fall: dict) -> dict:
    zeile = _leer("json", fall)
    start = time.monotonic()
    vorher = pp._hoechste_aufruf_id(conn)
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall)
        roh = szene_claude.schema(conn, e, klient, chat_id, erkenner.prompt(), nutzer,
                                  erkenner.schema(), "erkenner", timeout=60.0, modell=OPUS)
        _zaehle(zeile, fall, _filter(fall, roh.get("aenderungen", [])))
    except Exception as fehler:  # noqa: BLE001 -- ein Fall bricht den Lauf nie ab
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
    gemessen = pp._aufruf_nach(conn, vorher)
    zeile.update(still_fp=zeile["fp"], runden=1,
                 eingabe_token=gemessen["eingabe_token"],
                 ausgabe_token=gemessen["ausgabe_token"],
                 dauer_ms=int((time.monotonic() - start) * 1000))
    return zeile


def laufe_tools(conn, e, chat_id: int, fall: dict) -> dict:
    zeile = _leer("tools", fall)
    start = time.monotonic()
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall)
        generisch, _, lauf, ausfuehrungen = erkenner._werkzeuglauf(conn, e, chat_id, nutzer)
        uebersetzt = [x for x in (erkenner_werkzeuge.als_aenderung(a) for a in ausfuehrungen)
                      if x is not None]
        _zaehle(zeile, fall, _filter(fall, uebersetzt))
        ohne = sum(1 for a in ausfuehrungen if a.generisch is None and a.ok
                   and a.name not in erkenner_werkzeuge.ART_FUER_WERKZEUG)
        zeile.update(
            ohne_korpusart=ohne,
            abgelehnt=sum(1 for a in ausfuehrungen if not a.ok),
            abbruch=lauf.abbruch, runden=lauf.runden,
            eingabe_token=lauf.eingabe_token, ausgabe_token=lauf.ausgabe_token,
            aufrufe=[{"name": a.name, "eingabe": a.eingabe, "ok": a.ok, "fehler": a.fehler}
                     for a in ausfuehrungen],
        )
        zeile["still_fp"] = zeile["fp"] + ohne
        zeile["dauer_ms"] = lauf.dauer_ms
    except Exception as fehler:  # noqa: BLE001
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
        zeile["dauer_ms"] = int((time.monotonic() - start) * 1000)
    return zeile


def _messkopie_db(pfad: str | None):
    pfad = pfad or str(Path(tempfile.mkdtemp(prefix="ab_")) / "korpus.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    return conn


def _erkenner(args) -> int:
    e = dataclasses.replace(einstellungen.laden(), szene_anbieter="claude",
                            erkenner_modus="tools", szene_modell=OPUS)
    conn = _messkopie_db(args.db)
    faelle = pp.lade_korpus("erkenner", args.nur, sprache=args.sprache)
    modi = ("json", "tools") if args.modus == "beide" else (args.modus,)
    ROH_VERZ.mkdir(parents=True, exist_ok=True)
    aus = Path(args.aus or ROH_VERZ / f"A-{args.sprache}-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    klient = httpx.Client(timeout=120.0)
    with aus.open("a", encoding="utf-8") as datei:
        for nummer, fall in enumerate(faelle, start=1):
            for modus in modi:
                chat_id = nummer * 10 + (1 if modus == "json" else 2)
                repo.sichere_gruppe(conn, chat_id, "ab", fall["id"])
                zeile = (laufe_json(conn, e, klient, chat_id, fall) if modus == "json"
                         else laufe_tools(conn, e, chat_id, fall))
                zeile["sprache"] = args.sprache
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                datei.flush()
                print(f"[{nummer}/{len(faelle)}] {modus} {fall['id']}: "
                      f"T{zeile['treffer']} FP{zeile['fp']} FN{zeile['fn']}"
                      + (f" FEHLER {zeile['fehler']}" if zeile["fehler"] else ""), flush=True)
    print(f"Rohdaten: {aus}")
    return 0


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m scripts.ab_pipeline_vs_tools")
    unter = p.add_subparsers(dest="befehl", required=True)
    a = unter.add_parser("erkenner", help="Achse A: Korpus, json gegen tools")
    a.add_argument("--sprache", choices=("de", "en"), default="de")
    a.add_argument("--modus", choices=("json", "tools", "beide"), default="beide")
    a.add_argument("--nur", nargs="*")
    a.add_argument("--db")
    a.add_argument("--aus")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    if args.befehl == "erkenner":
        return _erkenner(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

Hinweis: `laufe_tools` liest die Werkzeug-Ausführungen, nicht `generisch`, damit
generische und Stück-Aufrufe in **einer** Menge gezählt werden.
Im Tools-Lauf schreibt `stueck` in die Korpus-DB — gewollt, das ist die
Agent-Semantik; jede `chat_id` ist frisch.

- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Trockenlauf an EINEM Fall** (Abo, 0 CHF, manuell)

Run: `uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide --nur e01-interview-starten-fatma --aus korpus/berichte/ab/trocken.jsonl`
Expected: zwei Zeilen `json`/`tools`, je `T1 FP0 FN0` oder ein erklärbarer
Fehler; `trocken.jsonl` danach löschen (nicht committen).
Benötigt `IT_*`-Pflichtvariablen in der Shell-Umgebung (aus `betrieb/padua-test.env`
lesen, **nicht** aus einer Live-Env schreiben).

- [ ] **Step 6: Commit**

```bash
git add scripts/ab_pipeline_vs_tools.py tests/test_ab_pipeline_vs_tools.py
git commit -m "feat(messung): Achse A -- Erkenner-Korpus json gegen tools (t_9b2b33cb)"
```

---

### Task 7: Achse B — Padua-Testsatz (BEDINGT: nur wenn Task 0 `ACHSE_B = ja`)

🔴 ANNAHME: Testsatz-Format aus Messung 1 ist zum Planungszeitpunkt
unbekannt. Diese Task wird **nach** Task 0 gegen das dort festgehaltene
Format konkretisiert. Bei `ACHSE_B = nein`: Task überspringen, im Bericht
„Achse B: 0 — Padua-Testsatz fehlte“.

**Files:**
- Create: `scripts/ab_padua.py`
- Test: `tests/test_ab_padua.py`

**Interfaces:**
- Consumes: `ab_pipeline_vs_tools.laufe_json/laufe_tools` (Zeilenformat Task 6, `achse` = `"B"`), `scripts.stueckmodell_kopie.kopiere(quelle, ziel)`, Leser des Testsatzes aus Messung 1 (Name aus Task 0).
- Produces: `lade_testsatz(pfad) -> list[dict]` im Korpus-Fallformat
  (`id`, `nachrichten`, `arbeitsstand`, `erwartet`) — oder, falls der
  Testsatz **keine** Erwartungen trägt, `erwartet = None`; dann zählt Achse B
  nur Übereinstimmung json↔tools (`gleich`, `nur_json`, `nur_tools`) und
  kein Treffer/FP.
- CLI: `python -m scripts.ab_padua --testsatz <pfad aus Task 0> --kopie /tmp/padua-ab.db`

- [ ] **Step 1: Kopie erzeugen und prüfen, dass die Quelle nur gelesen wird**

Test:

```python
from scripts import ab_padua


def test_kopie_oeffnet_quelle_nur_lesend(tmp_path, monkeypatch):
    gesehen = []
    monkeypatch.setattr(ab_padua.stueckmodell_kopie, "kopiere",
                        lambda q, z: gesehen.append((q, z)))
    ab_padua.bereite_kopie_vor("betrieb/padua.db", str(tmp_path / "k.db"))
    assert gesehen == [("betrieb/padua.db", str(tmp_path / "k.db"))]


def test_padua_test_db_wird_abgelehnt(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        ab_padua.bereite_kopie_vor("betrieb/padua-test.db", str(tmp_path / "k.db"))
```

Implementierung `bereite_kopie_vor(quelle: str, ziel: str) -> None`:
`if "padua-test" in Path(quelle).name: raise SystemExit("Messung nur auf betrieb/padua.db")`,
sonst `stueckmodell_kopie.kopiere(quelle, ziel)`.

- [ ] **Step 2: `lade_testsatz` gegen eine Beispielzeile aus Task 0** — Test
mit genau der in `docs/messung/2026-10-ab-vorbedingungen.md` festgehaltenen
Beispielzeile als Fixture-String; Erwartung: ein Fall im Korpus-Fallformat.
- [ ] **Step 3: Lauf je Fall beide Modi auf der Kopie** (je Fall eigene
`chat_id` wie in Task 6), Zeilen nach `korpus/berichte/ab/B-*.jsonl`. Test
mit Attrappen wie in Task 6 (`szene_claude.schema`, `erkenner._werkzeuglauf`
gepatcht): je Fall zwei Zeilen, `achse == "B"`.
- [ ] **Step 4: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_ab_padua.py`

- [ ] **Step 5: Commit**

```bash
git add scripts/ab_padua.py tests/test_ab_padua.py
git commit -m "feat(messung): Achse B -- Padua-Testsatz json gegen tools (t_9b2b33cb)"
```

---

### Task 8: Achse C — Zitatsuche Pipeline gegen Agent (BEDINGT: nur wenn Task 0 `ACHSE_C = ja`)

🔴 ANNAHME: Der Gold-Korpus aus `t_2349e9a8`/`t_2f905d2c` existiert zum
Planungszeitpunkt nicht. **Nur wenn er zum Start der Umsetzung im Repo-Stand
von `main` vorliegt** (Pfad und Format aus Task 0, gelesen aus der gemergten
Doku von `t_2f905d2c`), sonst diese Achse auslassen und im Bericht als
„Achse C: 0 — Gold-Korpus fehlte“ vermerken. Kein Pfad wird hier angenommen.

Kosten: Die Agent-Seite und die Kontrollzeile laufen auf **Kimi
(Infomaniak) und kosten CHF**. Der echte Lauf erst in Task 10 nach Birks
Freigabe; hier nur Code mit Attrappen.

**Files:**
- Create: `scripts/ab_zitate.py`
- Test: `tests/test_ab_zitate.py`

**Interfaces:**
- Consumes: `schaerfung._eintraege(conn, chat_id)`, `schaerfung._ziele(conn, chat_id)`,
  `schaerfung._mappe_ziel(klm, conn, e, chat_id, ziel, eintraege, nach_nummer)`,
  `zitat.pruefe(zitat, quelle)`, `llm.LLM` (Kimi), Gold-Korpus-Leser (Task 0).
- Produces:
  - `MAX_RUNDEN = 6`, `TOP_K = 10`, `SUCH_TREFFER = 8`, `FENSTER_ZEICHEN = 400`
  - `pipeline_top10(klm, conn, e, chat_id, ziel, *, ueber_claude: bool) -> list[dict]`
    — Kandidaten `{"text", "aufnahme_id", "verdichtung_thema_id", "staerke"}`, nach
    `staerke` absteigend, höchstens 10. `ueber_claude=False` = Kontrollzeile Kimi
    (über `monkeypatch`-freien Weg: `dataclasses.replace(e, szene_anbieter="infomaniak")`).
  - `suche(conn, chat_id, anfrage: str) -> list[dict]` — lokale Volltextsuche
    über `aufnahme.transkript` (nicht entfernt, `klasse in ('lang','teil','kurz')`
    mit Transkript), Wörter der Anfrage normalisiert (`zitat.normalisiere`),
    Treffer = Fenster ±`FENSTER_ZEICHEN // 2` um das erste Vorkommen, sortiert
    nach Anzahl getroffener Wörter, höchstens `SUCH_TREFFER`
    `{"aufnahme_id", "text"}`. Liest über `repo` (neue Lesefunktion
    `repo.transkripte(conn, chat_id) -> list[sqlite3.Row]` mit `id, transkript`,
    in `repo.py`, mit eigenem Test in `tests/test_ab_zitate.py`).
  - `AGENT_SCHEMA` = `{"type":"object","additionalProperties":False,"required":["aktion","anfrage","stellen"],"properties":{"aktion":{"type":"string","enum":["suche","fertig"]},"anfrage":{"type":"string"},"stellen":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["aufnahme_id","zitat"],"properties":{"aufnahme_id":{"type":"integer"},"zitat":{"type":"string"}}}}}}`
  - `agent_top10(klm, conn, e, chat_id, ziel) -> tuple[list[dict], dict]` —
    Schema-Schleife auf Kimi (`klm.schema(..., modell=e.llm_modell)`), je
    Runde: `suche` → Treffer an den nächsten Nutzertext; `fertig` → `stellen`.
    Jede Stelle wird mit `zitat.pruefe(stelle["zitat"], transkript der
    aufnahme_id)` geprüft; ungeprüfte fallen weg (zählen als `verworfen_zitat`).
    Zweite Rückgabe: `{"runden", "abbruch", "verworfen_zitat"}`.
  - `recall_at_10(kandidaten, gold_positiv, trifft) -> float`
  - `trifft(kandidat: dict, gold: dict) -> bool` — Vorgabe: gleiche
    `verdichtung_thema_id`, falls beide sie tragen; sonst
    `zitat.pruefe(gold_text, kandidat["text"]) or zitat.pruefe(kandidat["text"], gold_text)`.
    In Task 0 gegen das Gold-Format abgleichen; weicht die Gold-Definition ab
    (z. B. Kennungen statt Text), **dessen** Definition übernehmen.
  - Zeilenformat: `{"achse": "C", "gruppe", "ziel", "variante": "pipeline_opus"|"pipeline_kimi"|"agent_kimi", "recall_at_10", "kandidaten", "runden", "abbruch", "eingabe_token", "ausgabe_token", "dauer_ms", "kosten_chf", "fehler"}`
  - CLI: `python -m scripts.ab_zitate --gold <pfad aus Task 0> --kopie /tmp/padua-ab.db --gruppe G1 G2 G3`

- [ ] **Step 1: Failing tests (Attrappen)**

```python
import pytest

from interview_theater import repo
from scripts import ab_zitate as az


def test_recall_at_10_zaehlt_nur_die_ersten_zehn():
    kand = [{"text": f"stelle {i}"} for i in range(12)]
    gold = [{"text": "stelle 11"}, {"text": "stelle 1"}]
    gleich = lambda k, g: k["text"] == g["text"]
    assert az.recall_at_10(kand, gold, gleich) == 0.5


def test_recall_ohne_gold_ist_none():
    assert az.recall_at_10([{"text": "x"}], [], lambda k, g: True) is None


def test_trifft_ueber_thema_id_oder_wortlaut():
    assert az.trifft({"verdichtung_thema_id": 3, "text": "a"},
                     {"verdichtung_thema_id": 3, "text": "b"})
    assert az.trifft({"text": "ich bin damals allein gegangen"},
                     {"text": "allein gegangen"})


def _aufnahme(conn, text, chat_id=1):
    # Name/Signatur der Anlegefunktion vorab per
    # grep -n "^def lege_aufnahme\|^def neue_aufnahme" interview_theater/repo.py pruefen
    return repo.lege_aufnahme_an(conn, chat_id, 1, "lang", "text", transkript=text)


def test_suche_findet_fenster(conn):
    _aufnahme(conn, "Am Bahnhof hat meine Mutter geweint. Dann sind wir gegangen.")
    treffer = az.suche(conn, 1, "Mutter weint Bahnhof")
    assert treffer and "Mutter" in treffer[0]["text"]


class KlmFolge:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.nutzer = []

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        self.nutzer.append(nutzer)
        return self.antworten.pop(0)


def test_agent_sucht_dann_liefert_nur_gepruefte_stellen(conn, einst):
    aid = _aufnahme(conn, "Am Bahnhof hat meine Mutter geweint.")
    klm = KlmFolge([
        {"aktion": "suche", "anfrage": "Mutter Bahnhof", "stellen": []},
        {"aktion": "fertig", "anfrage": "", "stellen": [
            {"aufnahme_id": aid, "zitat": "meine Mutter geweint"},
            {"aufnahme_id": aid, "zitat": "erfunden"}]},
    ])
    stellen, info = az.agent_top10(klm, conn, einst, 1, {"art": "szene", "id": 1,
                                                          "beschreibung_text": "Abschied"})
    assert [s["text"] for s in stellen] == ["meine Mutter geweint"]
    assert info["verworfen_zitat"] == 1 and info["runden"] == 2
    assert "Mutter" in klm.nutzer[1]


def test_agent_rundendeckel(conn, einst):
    klm = KlmFolge([{"aktion": "suche", "anfrage": "x", "stellen": []}] * 10)
    stellen, info = az.agent_top10(klm, conn, einst, 1, {"art": "szene", "id": 1,
                                                          "beschreibung_text": "x"})
    assert stellen == [] and info["abbruch"] == "runden" and info["runden"] == az.MAX_RUNDEN
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_ab_zitate.py`

- [ ] **Step 3: Implementierung** — `repo.transkripte` (SQL nur in `repo.py`):

```python
def transkripte(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle nicht entfernten Transkripte einer Gruppe -- Lesequelle der
    Zitatsuche-Messung (scripts/ab_zitate.py, Karte t_9b2b33cb)."""
    with _LOCK:
        return conn.execute(
            "SELECT id, transkript FROM aufnahme WHERE chat_id = ? "
            "AND entfernt_am IS NULL AND transkript IS NOT NULL AND transkript != '' "
            "ORDER BY id", (chat_id,)).fetchall()
```

`scripts/ab_zitate.py`: die Funktionen aus „Interfaces“; die Schleife von
`agent_top10`:

```python
SYSTEM = (
    "Du suchst in Interview-Transkripten woertliche Stellen, die zu EINEM Ziel "
    "(Szene oder Figur) passen -- nach Ausdruckskraft, nicht nur nach Thema. "
    "Je Runde: aktion='suche' mit einer Suchanfrage (Stichwoerter), oder "
    "aktion='fertig' mit hoechstens 10 Stellen, wortgleich aus den gezeigten "
    "Treffern zitiert, beste zuerst."
)


def agent_top10(klm, conn, e, chat_id, ziel):
    texte = {z["id"]: z["transkript"] for z in repo.transkripte(conn, chat_id)}
    verlauf = [f"Ziel: {ziel.get('beschreibung_text') or ziel}"]
    info = {"runden": 0, "abbruch": None, "verworfen_zitat": 0}
    while True:
        if info["runden"] >= MAX_RUNDEN:
            info["abbruch"] = "runden"
            return [], info
        antwort = klm.schema(chat_id, SYSTEM, "\n\n".join(verlauf), AGENT_SCHEMA,
                             "ab_zitatsuche", modell=e.llm_modell)
        info["runden"] += 1
        if antwort.get("aktion") == "suche":
            treffer = suche(conn, chat_id, antwort.get("anfrage", ""))
            verlauf.append(f"Suche: {antwort.get('anfrage', '')}\n" + "\n".join(
                f"[aufnahme {t['aufnahme_id']}] {t['text']}" for t in treffer)
                or "keine Treffer")
            continue
        stellen = []
        for s in antwort.get("stellen", [])[:TOP_K]:
            quelle = texte.get(int(s.get("aufnahme_id") or 0), "")
            if quelle and zitat.pruefe(s.get("zitat", ""), quelle):
                stellen.append({"text": s["zitat"], "aufnahme_id": s["aufnahme_id"]})
            else:
                info["verworfen_zitat"] += 1
        return stellen, info
```

`pipeline_top10` ruft `schaerfung._mappe_ziel` mit `e` bzw.
`dataclasses.replace(e, szene_anbieter="infomaniak")` und mappt
`verdichtung_thema_id` über `schaerfung._eintraege` auf `zitat`-Text.
Hinweis Datenschutz (Spec § 4): `agent_top10` und `suche` dürfen
**nie** `szene_claude` importieren — Test:

```python
def test_agent_zitatsuche_geht_nie_ueber_den_proxy():
    import ast, pathlib
    baum = ast.parse(pathlib.Path("scripts/ab_zitate.py").read_text(encoding="utf-8"))
    importe = {a.name for n in ast.walk(baum) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in n.names}
    assert "szene_claude" not in importe
```

- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit**

```bash
git add interview_theater/repo.py scripts/ab_zitate.py tests/test_ab_zitate.py
git commit -m "feat(messung): Achse C -- Zitatsuche Pipeline gegen Agent, Recall@10 (t_9b2b33cb)"
```

---

### Task 9: Bericht bauen (`bericht`-Unterbefehl)

**Files:**
- Modify: `scripts/ab_pipeline_vs_tools.py` (Unterbefehl `bericht`)
- Test: `tests/test_ab_bericht.py`

**Interfaces:**
- Consumes: JSONL-Zeilen aus Task 6/7/8 (`achse` A/B/C).
- Produces: `baue_bericht(zeilen: list[dict], vorbedingungen: dict, kommandos: list[str]) -> str`;
  CLI `python -m scripts.ab_pipeline_vs_tools bericht --roh korpus/berichte/ab/*.jsonl --aus docs/messung/2026-10-ab-pipeline-vs-tools.md`
  (`--roh` nimmt mehrere Pfade, `nargs="+"`; die Shell expandiert den Stern).

- [ ] **Step 1: Failing tests**

```python
from scripts import ab_pipeline_vs_tools as ab


def _z(modus, **kw):
    basis = {"achse": "A", "sprache": "de", "modus": modus, "id": "x", "treffer": 1,
             "fp": 0, "fn": 0, "still_fp": 0, "ohne_korpusart": 0, "abgelehnt": 0,
             "abbruch": None, "runden": 1, "eingabe_token": 100, "ausgabe_token": 10,
             "dauer_ms": 1000, "fehler": None}
    basis.update(kw)
    return basis


VOR = {"ACHSE_B": "nein", "ACHSE_C": "nein", "PROXY_TOOLS": "ja"}


def test_bericht_hat_tabelle_je_kennzahl_und_beide_modi():
    text = ab.baue_bericht([_z("json"), _z("tools", runden=3, dauer_ms=3000)], VOR, ["cmd"])
    for kennzahl in ("Treffer", "stille Fehler", "abgelehnt (laut)", "Abbrüche",
                     "Latenz", "Token", "Kosten"):
        assert kennzahl in text
    assert "| json |" in text and "| tools |" in text


def test_opus_kosten_sind_abo_keine_erfundene_chf_zahl():
    text = ab.baue_bericht([_z("json"), _z("tools")], VOR, [])
    assert "0 CHF (Abo)" in text


def test_fehlende_achsen_stehen_als_null_mit_grund():
    text = ab.baue_bericht([_z("json")], VOR, [])
    assert "Achse B: 0 — Padua-Testsatz fehlte" in text
    assert "Achse C: 0 — Gold-Korpus fehlte" in text


def test_was_die_messung_nicht_zeigt():
    text = ab.baue_bericht([_z("json")], VOR, [])
    abschnitt = text[text.index("## Was die Messung NICHT zeigt"):]
    assert "Laien" in abschnitt and "Gruppenerlebnis" in abschnitt


def test_keine_empfehlung_umstellen():
    text = ab.baue_bericht([_z("json"), _z("tools")], VOR, [])
    assert "Die Entscheidung trifft Birk" in text
    assert "empfehlen umzustellen" not in text.lower()


def test_kommandos_zum_nachrechnen_stehen_drin():
    text = ab.baue_bericht([_z("json")], VOR, ["uv run ... erkenner --sprache de"])
    assert "uv run ... erkenner --sprache de" in text
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_ab_bericht.py`

- [ ] **Step 3: Implementierung** — `baue_bericht` erzeugt:

1. Kopf (Karte, Datum, Modell `claude-opus-5-5`, Proxy, Korpusgrößen, Verweis
   auf Spec und `docs/messung/2026-10-ab-vorbedingungen.md`).
2. Je Achse und Sprache eine Tabelle `| Kennzahl | json | tools |` mit den
   Zeilen: Treffer (Summe / erwartet gesamt), FN, FP, stille Fehler
   (`still_fp`, bei tools zusätzlich „davon ohne Korpus-Art: n“), abgelehnt
   (laut), Abbrüche (je `abbruch`-Wert), Runden (Median), Latenz Median/p90
   (ms, aus `dauer_ms`, `statistics.median` und
   `statistics.quantiles(n=10)[-1]`, bei < 2 Werten nur Median), Token
   ein/aus (Summe), Kosten (`0 CHF (Abo)` für Opus-Zeilen; echte CHF nur aus
   `kosten_chf` der Achse-C-Kimi-Zeilen), Fehler (Anzahl).
3. Achse C: `| Gruppe | pipeline_opus | pipeline_kimi | agent_kimi |` mit
   Recall@10, darunter Kosten CHF der Kimi-Zeilen.
4. Fehlende Achsen: genau „Achse B: 0 — Padua-Testsatz fehlte“ /
   „Achse C: 0 — Gold-Korpus fehlte“.
5. „## Messgrenzen“: Abbildungstabelle `ART_FUER_WERKZEUG` (aus dem Modul
   gerendert), Undo-Unterschied (Spec § 3.4), Modell-Störfaktor Achse C.
6. „## Kommandos zum Nachrechnen“: die übergebenen `kommandos` als Codeblock.
7. „## Was die Messung NICHT zeigt“: Live mit Laien; Gruppenerlebnis
   (Tempo, Vertrauen, ob die Gruppe Notiert-Meldungen versteht);
   Gesprächsführung durch einen Agenten (nur der Erkenner wurde getauscht);
   Langzeitstabilität über einen ganzen Workshoptag; Wirkung fehlender
   Undo-Knöpfe für Werkzeugschritte.
8. Schlusszeile: „Keine Empfehlung. Die Entscheidung trifft Birk.“

- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit**

```bash
git add scripts/ab_pipeline_vs_tools.py tests/test_ab_bericht.py
git commit -m "feat(messung): Bericht Pipeline gegen Agent aus den Rohdaten (t_9b2b33cb)"
```

---

### Task 10: Messlauf und Bericht (manuell, nie automatisch)

**Files:**
- Create: `korpus/berichte/ab/A-de-*.jsonl`, `A-en-*.jsonl` (und B/C, falls aktiv)
- Create: `docs/messung/2026-10-ab-pipeline-vs-tools.md`

- [ ] **Step 1: Achse A deutsch** (Abo, 0 CHF; ~157 Fälle × 2 Modi, seriell)

Run: `uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide`
(Bash-Timeout 900000 ms; reicht er nicht, mit `--nur` in Blöcken fahren und
`--aus` auf dieselbe Datei setzen — Zeilen werden angehängt.)
Expected: je Fall zwei Zeilen; Fehlerquote < 5 % (sonst Proxy prüfen, nicht
umdeuten).

- [ ] **Step 2: Achse A englisch** (`--sprache en`, 103 Fälle × 2), sonst wie Step 1.

- [ ] **Step 3: Achse B** — nur bei `ACHSE_B = ja`:
`uv run --extra dev python -m scripts.ab_padua --testsatz <pfad> --kopie /tmp/padua-ab.db`
(Opus, Abo). Kopie danach löschen; sie enthält Workshopdaten und gehört nicht
ins Repo.

- [ ] **Step 4: Achse C — nur bei `ACHSE_C = ja` und nach Freigabe**

Kimi kostet CHF. Vorher Schätzung aus Achse-A-Tokenzahlen ×
`kosten.PREISE_CHF_JE_MIO_TOKEN[<llm_modell>]` × Ziele × Runden ×
2 Kimi-Varianten, dann `kanban_block` an Birk mit der Schätzung
(Geldfrage). Erst nach Freigabe:
`uv run --extra dev python -m scripts.ab_zitate --gold <pfad> --kopie /tmp/padua-ab.db --gruppe G1 G2 G3`.
Ohne Freigabe: Achse C im Bericht als „0 — nicht freigegeben (Kosten)“.

- [ ] **Step 5: Bericht bauen**

Run: `uv run --extra dev python -m scripts.ab_pipeline_vs_tools bericht --roh korpus/berichte/ab/A-de-<stempel>.jsonl korpus/berichte/ab/A-en-<stempel>.jsonl --aus docs/messung/2026-10-ab-pipeline-vs-tools.md`
Expected: Datei mit allen Abschnitten aus Task 9; Zahlen stichprobenartig
gegen drei JSONL-Zeilen nachrechnen (Summe Treffer einer Spalte von Hand).

- [ ] **Step 6: Commit**

```bash
git add korpus/berichte/ab docs/messung/2026-10-ab-pipeline-vs-tools.md
git commit -m "docs(messung): Bericht A/B Pipeline gegen Agent (t_9b2b33cb)"
```

---

### Task 11: Doku und Abnahme

**Files:**
- Modify: `AGENTS.md` (Modulkarte, Zeile „Fachlogik“: `erkenner_werkzeuge.py` ergänzen; Modulliste: eine Zeile)
- Modify: `docs/agents/aufbau.md` (Modultabelle: `erkenner_werkzeuge.py` mit Begründung)
- Modify: `docs/agents/korpus-und-simulation.md` (Abschnitt „Messung 2: Pipeline gegen Agent“ mit den CLI-Kommandos und „kostet Geld: Kimi-Teil von Achse C“)
- Modify: `docs/agents/fallen.md` (eine Falle: „`IT_ERKENNER_MODUS=tools` wirkt nur mit `[erkenner] ueber_claude`; Werkzeugschritte haben keinen Undo-Knopf“)

- [ ] **Step 1: AGENTS.md-Zeile** (unter `erkenner.py`):

```markdown
- `erkenner_werkzeuge.py` — `stueck.WERKZEUGE` + `aenderung_melden` als Tool-Definitionen für den Opus-Erkenner unter `IT_ERKENNER_MODUS=tools` (Vorgabe `json`); kein SQL, kein Modellaufruf; Messung `docs/messung/2026-10-ab-pipeline-vs-tools.md`.
```

- [ ] **Step 2: Größe und Doku-Tests**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_agents_md_groesse.py tests/test_doku_laengen.py tests/test_web_betrieb_doku.py`
Expected: PASS (AGENTS.md < 25.000 Bytes; heute 22.075).

- [ ] **Step 3: Profilprüfung Padua**

Run: `uv run --extra dev python -m scripts.pruefe_profil padua-2026`
Expected: grün.

- [ ] **Step 4: Default-Nachweis**

Run: `grep -rn "IT_ERKENNER_MODUS" betrieb/*.env docs/interview-theater@.service`
Expected: kein Treffer (keine Live-Env gesetzt, kein Neustart nötig).

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/agents/aufbau.md docs/agents/korpus-und-simulation.md docs/agents/fallen.md
git commit -m "docs(agents): erkenner_werkzeuge, IT_ERKENNER_MODUS, Messung 2 (t_9b2b33cb)"
```

Die volle Suite läuft einmal am Ende durch `cc-run.py`
(`uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`,
Stand 10.10.: 9.910 Tests, ≈ 309 s). Kein Merge, kein Push in der
Umsetzungskarte.

---

## Abnahme (aus der Karte)

| Kriterium | Nachweis |
|---|---|
| Bericht `docs/messung/2026-10-ab-pipeline-vs-tools.md` mit Tabelle je Kennzahl, Kommandos, „Was die Messung NICHT zeigt“ | Task 9 (Tests), Task 10 (Datei) |
| Volle Suite grün | cc-run.py nach dem Lauf |
| Default `IT_ERKENNER_MODUS=json` unverändert | Task 1 `test_vorgabe_ist_json`, Task 11 Step 4 |
| Kein Bot-Neustart | Global Constraints; keine Env/Unit geändert |
| Keine Empfehlung „umstellen“ ohne Zahlen | Task 9 `test_keine_empfehlung_umstellen` |
| Datenschutz: Interviews hart auf Kimi in json **und** tools | Task 5 |
| Zitatsuche-Achse abhängig vom Gold-Korpus | Task 0 Step 3, Task 8 (bedingt), Task 9 `test_fehlende_achsen…` |
| Testsatz-Format aus Messung 1 als ANNAHME | Task 0 Step 2, Task 7 (bedingt) |

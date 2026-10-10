# Stückmodell: jede Tatsache an genau einer Stelle (unter der Pipeline) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Leitsatz (wörtlich, Review `grundsatz-architektur-review.md` Abschnitt 4):**
„Stückmodell heißt: Jede Tatsache über das Stück — wer spielt, wo eine Szene spielt, was die Gruppe beschlossen hat — steht an genau einer Stelle; Werkbank, Karte, Script-Kopf und PDF lesen von dort ab und tragen nichts Eigenes, und wenn die Gruppe den Ort ändert, ändert sie ihn einmal und sieht überall sofort den neuen Ort oder die Meldung ‚Szene 3 passt nicht mehr — neu schreiben? Ja/Nein‘."

**Goal:** Ort, Besetzung, Kartenfelder, Reihenfolge und offene Fragen einer Szene stehen je an genau einer Stelle. Karte, Script-Kopf, PDF, Werkbank und Prompt-Blöcke werden aus diesen Stellen abgeleitet. Geändert wird über eine Mutations-Schnittstelle (`interview_theater/stueck.py`), die in jeder Phase gilt, Prosa nur als veraltet markiert und die Gruppe mit Ja/Nein fragt.

**Architecture:** Gebaut wird unter der heutigen Phasen-Pipeline (B); Gesprächsmodell, Erkenner, Knöpfe und Phasen werden nicht umgebaut. Neu sind drei Teile:
- `stueck_sicht.py`: reine Ableitungsfunktionen ohne Projektimport. Bot und Webserver rufen dieselbe Funktion.
- `stueck.py`: die Mutations-Schnittstelle. Nur Keyword-Argumente mit JSON-Typen, Rückgabe `Ergebnis`, keine `tg`/`klm`/`e`-Parameter, damit sie später 1:1 als Agenten-Werkzeug taugt.
- Eine idempotente Daten-Migration in `db.py`.

Der Opus-Nachzug `karten_nachzug.ziehe_nach` wird kein Zweit-Schreiber mehr, sondern ein Aufrufer der Schnittstelle (`repo.aktualisiere_karte_und_werkbank` fällt weg).

**Tech Stack:** Python 3.11, SQLite (WAL, additive Migration), pytest, `uv run --extra dev`.

**Spec-Quellen (von Birk am 10.10.2026 entschieden, hier nicht neu verhandelt):**
- Entscheidungsvorlage v2 `~/hermes-shared/hermes-entities/entities/artesmobiles/projekte/inscribe/grundsatz-architektur-und-kollektiver-prozess.md` (Folien 2, 3, 7)
- Review `…/inscribe/grundsatz-architektur-review.md` (Abschnitt 4 = Leitsatz oben)
- Kernkarte `t_5a439d0d` (Board hermes-dev): Kommentar 1404 (10.10. 06:31 UTC+2, „EIN Weg zum Ergebnis … das Script ist die einzige Quelle, der Chat zeigt nur Änderungen daran (Diff + Yes/No)."), Kommentar 1374 (Vorfälle 1–13), Kommentar 1431 (Freigabe, Kette `t_85747bb9` Plan → `t_fd88600b` Code → `t_e4b074e5` Review → `t_5526e2fc` Merge)
- Umsetzungskarte `t_fd88600b` (Board interview-theater): Probleme 1–5, Nicht-in-Scope, Abnahme gesamt (unten wörtlich unter „Global Constraints")

## Global Constraints

- Branch für die Umsetzung: `wt/t_fd88600b` in einem eigenen Worktree. Commit nach jedem Task, kein Merge, kein Push.
- Suite (einmal am Ende; während der Arbeit nur gezielte Tests): `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider`.
- Gezielte Tests: `uv run --extra dev python -m pytest -q -p no:cacheprovider <testpfad>` (ein Befehl je Bash-Aufruf, kein `cd`, kein `&&`).
- Live-DB `betrieb/padua.db` **nur read-only** (`file:…?mode=ro`). Die Migration läuft nur gegen eine `VACUUM INTO`-Kopie unter `var/stueckmodell/`, die nicht eingecheckt wird.
- Live-Dienste (`interview-theater*`) werden nie gestartet, gestoppt oder neu gestartet. Die Migration läuft live erst beim nächsten Bot-Start, und den macht Birk.
- Dortmund ist eingefroren (AGENTS.md):
  - Ein Test, der nur wegen Dortmund-Verhalten rot wird, bekommt `@pytest.mark.dortmund`.
  - Keine neuen Profilschalter. Wo ein Schalter Dortmund und Padua trennt, wird direkt das Padua-Verhalten gebaut.
- Schema nur additiv (`db._migriere_fehlende_spalten`), tote Spalten bleiben stehen. Jede neue Tabelle hat `chat_id` und steht in `db.TABELLEN_MIT_CHAT_ID`.
- SQL nur in `repo.py`/`db.py` (Ausnahme `web_daten.py`, read-only). Neue `repo`-Funktionen tragen `@_gesperrt`.
- Kein Modellaufruf in Knopf-Handlern oder Slash-Befehlen; was ein Modell braucht, geht an einen Thread (`tests/test_knoepfe_struktur.py`).
- Nutzertexte über `sprache.Texte` (`T`/`_T(chat_id)`). Neue `_TEXT_*`-Konstanten bekommen Einträge in `interview_theater/sprachen/en/texte.toml` **und** `…/it/texte.toml`; Knopf-Beschriftungen bleiben EN (Morgen-Auftrag 4).
- Prompt-Schnappschüsse werden nur bewusst geändert. Erwartet ist **keine** Änderung am SYSTEM-Teil (Task 0 und Task 18 vergleichen).
- **Abnahme gesamt (wörtlich, Karte `t_fd88600b`):**
  - „Migration: bestehende Padua-Daten (Kopie) lassen sich ins Stueckmodell ueberfuehren; danach liefern alle Ansichten denselben Inhalt wie vorher, wo er konsistent war, und EINEN Wert, wo er widerspruechlich war (Konfliktliste als Bericht)."
  - „Wiedergabe: Die 69 Wuensche aus `p7audit.json`, soweit sie Struktur betreffen (Ort, Figuren, Karten, offene Fragen), landen gegen die Kopie korrekt; Zahl vorher/nachher nennen."
  - „Mutationstest je Problem 1-4: der Test wird rot, wenn die Ableitung durch eine zweite Spalte ersetzt wird."
  - „Volle Suite gruen, Prompt-Schnappschuesse nur bewusst geaendert."
- **Nicht in Scope:**
  - Kein Umbau von Gesprächsmodell, Erkenner-Prompt oder Phasensteuerung; kein Hermes-Agent.
  - Keine neue UI (drei Handys, Timer — wartet auf `t_287c2928`).
  - Kein Konsistenzwächter (Opus-Hintergrundlauf aus Vorschlag A). Er gehört zum Prüfweg, nicht zu dieser Karte.

---

## Die eine Stelle je Tatsache (Zielbild)

| Tatsache | einzige Stelle (danach) | heute zusätzlich | abgeleitete Ansichten |
|---|---|---|---|
| Rahmen des Stücks | `arbeitsstand.rahmen` | — | Werkbank P4, Vorspann, Prompt |
| Figur (Stück) | `figur` | `stage_kopf` ROLES (Prosa) | Werkbank P4, Kopf-Prompt |
| Ort je Szene | `szene.ort` | `karte.ort` (JSON) | Karte, Script-Kopf (`meta_html`), PDF, Werkbank, Prompt |
| Wer je Szene | `szene_figur` (+ neue Spalten `rolle`, `position`) + neue Spalte `szene.wer_zusatz` | `karte.wer` (JSON) | Karte, `meta_html`, Besetzungszeile, PDF, Werkbank, Prompt |
| Typ/Modus/Worum/Punkte/Zitate | `szene.karte` JSON **ohne** `ort`/`wer`/`fragen` | — | Karte, Badge, Partitur, Prompt |
| Reihenfolge | `szene.nummer` | — | alle |
| Offene Frage | neue Tabelle `offene_frage` | `karte.fragen`, `[OPEN]`-Punkte in `karte.punkte` | Karte (Fragen + `[OPEN]`-Punkte), Speichersperre, Klärweg |
| Script-Text EN/IT | `szene.volltext`/`volltext_it` (Prosa) | — | Script-Tab, PDF |
| Kopf des Skripts | `arbeitsstand.stage_kopf(_it)` (Prosa) | — | Script-Tab, PDF |
| „passt nicht mehr" | neue Tabelle `veraltet` (nur für Prosa) | — | Ja/Nein-Angebot im Chat |
| Was wann geändert wurde | neue Tabelle `stueck_aenderung` (nur anhängen) | `karte_verlauf` (bleibt als Kartenhistorie) | Konfliktbericht, Wiedergabe, Audit |

`szene.karte_klaerung` bleibt Ablaufzustand (Cursor der Frage-für-Frage-Runde). Ab Task 11 trägt sie Frage-ids statt Fragetexten.

## Heutige Gate-Semantik (gelesen vor dem Umbau, Pflicht laut Karte)

- `phasen.voraussetzungen(conn, chat_id) -> dict[int, bool]` (`interview_theater/phasen.py:351-458`) liest nur Daten. Laut Docstring (`phasen.py:375-376`): „was hier True ergibt, wird der Gruppe angeboten …, nie geschaltet". Es ist **kein Verbot**. Aufrufer: `kontext._baue_phasenhinweis` (`kontext.py:1245`) sowie intern `moegliche_naechste` (`phasen.py:481-494`), `naechste_moegliche` (`phasen.py:497-507`) und `offenes_angebot` (`phasen.py:510-547`). Alle bauen daraus nur ein Angebot (Knopf `knoepfe/basis.py:137 _phasenknopf`, Prompt-Hinweis, `/stand`).
- `erneuere_nach_aenderung` (`phasen.py:586-597`) räumt nur einen negativen Merkposten ab (Angebot nach „Noch etwas ändern" erneuern). Aufrufer: `erkenner.py:3802`.
- `befehle.wechsle_phase` (`befehle.py:897-962`) prüft `voraussetzungen` **nicht**. Jeder Sprung per `/phase`, Klick oder Knopf geht durch. Einzige harte Sperre ist `p5_gate` (`befehle.py:866`, Padua-Bestätigung der Übersicht).
- Die **tatsächlichen Verbote**, die Problem 2 meint, sitzen auf Szenenebene:
  - `szenenkarte.starte_dialog`/`aktualisiere_mit_dialog`/`behalte_karte`/`bestaetige`/`starte_fragenklaerung`/`ueberspringe_fragen` lehnen mit `_TEXT_NICHT_DRAN` ab, wenn `nummer != aktuelle_nummer` (`szenenkarte.py:373, 453, 472, 658, 779, 806`). Eine abgenommene Karte ist dadurch nach P6 nicht mehr änderbar.
  - `stagescript.bestaetige` lehnt mit `_TEXT_ERST_VORHERIGE` ab (`stagescript.py:795-814`, Vorfall 6 „Speicher-Sperre").
  - `erkenner.py:3332` verwirft `text_ueberarbeiten` in P6 bewusst (Entscheidung ~09:35, keine heimlichen Umbauten). Das bleibt so (Nicht-in-Scope Erkenner).

**Daraus folgt für diesen Plan:**
- `voraussetzungen`/`moegliche_naechste`/`naechste_moegliche`/`erneuere_nach_aenderung` bleiben **unverändert**: Fokus und Vorschlag bleiben phasenabhängig, wie die Karte es verlangt.
- **Neu** ist `phasen.warnungen(conn, chat_id, ziel)`. `wechsle_phase` nennt damit bei einem expliziten Sprung, was laut Materiallage fehlt, und schaltet trotzdem (Task 15).
- Die Szenen-Verbote werden Warnungen (Task 15).
- `p5_gate` und `erkenner._ohne_phasensprung_vor_fixierten_figuren` (`erkenner.py:2233`) bleiben: Das erste ist ein Bestätigungsschritt, das zweite ein Schutz vor fehlgelesenem Chat. Der Klick- und `/phase`-Weg ist dort schon frei. Siehe „Offene Entscheidungen für Birk".

## Dateistruktur

| Datei | Rolle | Task |
|---|---|---|
| `interview_theater/db.py` (ändern) | neue Spalten, drei Tabellen, `_migriere_stueckmodell` | 1, 8 |
| `interview_theater/repo.py` (ändern) | Schreib- und Lesefunktionen der neuen Stellen, Sperre `NUR_UEBER_STUECK`, Wegfall `aktualisiere_karte_und_werkbank` | 2, 12, 13 |
| `interview_theater/stueck_sicht.py` (neu) | reine Ableitung: `karte_ansicht`, `wer_text`, `ordne_besetzung`, `OFFEN_PUNKT` | 3 |
| `interview_theater/stueck.py` (neu) | Mutations-Schnittstelle + `karte(conn, szene)` + `karte_aus_modell` + `pruefe_szene` | 4, 5, 6 |
| `interview_theater/sprachen/{en,it}/texte.toml` (ändern) | Texte von `stueck`, neue Warnungen | 4, 14, 15 |
| `interview_theater/szenenkarte.py` (ändern) | Leser auf `stueck.karte`, `erzeuge` → `stueck.karte_aus_modell`, Klärweg auf `offene_frage`, „nicht dran" → Warnung | 9, 11, 15 |
| `interview_theater/stagescript.py`, `prueflauf.py`, `ueberarbeitung.py`, `ablauf.py`, `erkenner.py` (ändern) | Leser auf `stueck.karte`; Schreiber auf `stueck` | 9, 13, 14, 15 |
| `interview_theater/web_daten.py`, `web.py` (ändern) | abgeleitete Karte im Web; Wo/Wer in der Padua-Werkbank | 10 |
| `interview_theater/karten_nachzug.py` (ändern) | Modelllesung bleibt, Schreiben nur über `stueck` | 12 |
| `interview_theater/web_schreiben.py`, `befehle.py`, `knoepfe/szenen.py`, `entwurf.py`, `szene.py`, `szenenfolge.py`, `kurzgeschichte.py` (ändern) | Ort/Besetzung über `stueck` | 13 |
| `interview_theater/knoepfe/texte.py`, `knoepfe/__init__.py`, `knoepfe/wirkung.py`, `knoepfe/szenen.py` (ändern) | Knöpfe „Ja, neu schreiben" / „Nein, so lassen" | 14 |
| `interview_theater/phasen.py`, `befehle.py` (ändern) | `phasen.warnungen`, Warnung beim Phasensprung | 15 |
| `tests/stueck_hilfe.py` (neu) | Testhilfe: Karte anlegen, Telegram-Attrappe | 4 |
| `tests/test_stueck_*.py` (neu) | Tests je Task | 1–16 |
| `scripts/stueckmodell_kopie.py`, `scripts/stueckmodell_ansichten.py`, `scripts/stueckmodell_vergleich.py`, `scripts/stueckmodell_migration.py`, `scripts/stueckmodell_wiedergabe.py` (neu) | Messbasis, Migration gegen Kopie, Vergleich, Wiedergabe | 0, 17 |
| `AGENTS.md`, `docs/agents/aufbau.md`, `docs/agents/entscheidungen.md`, `docs/handoffs/2026-10-xx-stueckmodell.md` (ändern/neu) | Doku, Nachweise | 18 |

---

### Task 0: Messbasis vorher (Kopie, Ansichten, Prompt-Schnappschuss) — VOR jeder Codeänderung

Ohne diesen Stand ist „dieselben Inhalte wie vorher" nicht nachweisbar. Er muss mit dem **unveränderten** Code entstehen.

**Files:**
- Create: `scripts/stueckmodell_kopie.py`
- Create: `scripts/stueckmodell_ansichten.py`
- Test: `tests/test_stueckmodell_skripte.py`

**Interfaces:**
- Produces:
  - `scripts.stueckmodell_kopie.kopiere(quelle: str, ziel: str) -> None` (VACUUM INTO, Quelle nur `mode=ro`; bricht ab, wenn `ziel` existiert).
  - `scripts.stueckmodell_ansichten.fakten(conn, chat_id: int) -> dict[str, dict]`. Je Szenennummer (als String) die Schlüssel `pdf_meta`, `pdf_besetzung`, `karte_wo`, `karte_wer`, `werkbank_ort`, `werkbank_figuren`, `prompt_wo`, `prompt_wer`, `fragen`, `punkte_offen`.
  - CLI: `python -m scripts.stueckmodell_ansichten --db <pfad> --aus <json>`.

- [ ] **Step 1: Failing test schreiben**

```python
# tests/test_stueckmodell_skripte.py
"""Messbasis des Stueckmodells (Karte t_fd88600b, Task 0): Kopie read-only,
Ansichten-Fakten je Szene."""

import json
import sqlite3

import pytest

from interview_theater import db, repo, workshop
from scripts import stueckmodell_ansichten, stueckmodell_kopie


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_kopie_entsteht_und_quelle_bleibt_unberuehrt(tmp_path):
    quelle = tmp_path / "q.db"
    c = db.verbinde(str(quelle))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "g1", "G")
    c.close()
    vorher = quelle.read_bytes()
    ziel = tmp_path / "k.db"

    stueckmodell_kopie.kopiere(str(quelle), str(ziel))

    assert quelle.read_bytes() == vorher
    k = sqlite3.connect(ziel)
    assert k.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 1


def test_kopie_ueberschreibt_nie(tmp_path):
    quelle = tmp_path / "q.db"
    db.initialisiere(db.verbinde(str(quelle)))
    ziel = tmp_path / "k.db"
    ziel.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        stueckmodell_kopie.kopiere(str(quelle), str(ziel))


def test_fakten_lesen_ort_aus_allen_ansichten(conn, padua):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, sid, "ort", "Bar")
    repo.setze_szenenkarte(conn, sid, json.dumps({
        "typ": "spoken", "modus": "none", "worum": "w", "ort": "Bar",
        "wer": "", "punkte": ["p"], "zitate": [], "fragen": []}))

    f = stueckmodell_ansichten.fakten(conn, 1)

    assert f["1"]["werkbank_ort"] == "Bar"
    assert f["1"]["karte_wo"] == "Bar"
    assert "Bar" in f["1"]["pdf_meta"]
```

(Der dritte Test schreibt absichtlich noch auf dem **alten** Weg. Nach Task 13 ist `setze_szenenfeld(..., "ort", …)` gesperrt, und in Task 13 Step 6 wird dieser Test auf `tests.stueck_hilfe.lege_karte_an` umgestellt.)

- [ ] **Step 2: Test laufen lassen**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_skripte.py`
Expected: FAIL mit `ModuleNotFoundError: No module named 'scripts.stueckmodell_ansichten'`.

- [ ] **Step 3: Skripte schreiben**

```python
# scripts/stueckmodell_kopie.py
"""Kopie der Live-DB fuer den Stueckmodell-Umbau (Karte t_fd88600b).

Die Quelle wird NUR read-only geoeffnet (``mode=ro``); ``VACUUM INTO``
schreibt eine konsistente Kopie, auch waehrend die Bots laufen.

    uv run --extra dev python -m scripts.stueckmodell_kopie betrieb/padua.db var/stueckmodell/padua-kopie.db
"""

import sqlite3
import sys
from pathlib import Path


def kopiere(quelle: str, ziel: str) -> None:
    if Path(ziel).exists():
        raise FileExistsError(ziel)
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{quelle}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (ziel,))
    finally:
        conn.close()


if __name__ == "__main__":
    kopiere(sys.argv[1], sys.argv[2])
    print(f"Kopie: {sys.argv[2]}")
```

```python
# scripts/stueckmodell_ansichten.py
"""Was jede Ansicht je Szene ueber Ort, Besetzung und offene Fragen zeigt
(Karte t_fd88600b) -- gelesen ueber die Ansichten selbst, nicht ueber die
Spalten: Script-Tab/PDF (``web.textbuch_html``), CoThinker-Karte
(``web._szenenkarten_html``), Werkbank-Daten (``web_daten``), Szenen-Prompt
(``stagescript.baue_nutzertext``).

Laeuft VOR (Task 0) und NACH (Task 17) dem Umbau gegen dieselbe Kopie;
``scripts.stueckmodell_vergleich`` legt beide nebeneinander.

    uv run --extra dev python -m scripts.stueckmodell_ansichten --db var/stueckmodell/padua-kopie.db --aus var/stueckmodell/ansichten-vorher.json
"""

import argparse
import html as htmllib
import json
import os
import re

_TAG = re.compile(r"<[^>]+>")
_NUMMER = re.compile(r"(?:Scene|Scena|Szene)\s+(\d+)", re.I)


def _text(fragment: str | None) -> str:
    return " ".join(htmllib.unescape(_TAG.sub(" ", fragment or "")).split())


def _erstes(muster: str, text: str) -> str:
    treffer = re.search(muster, text, re.S)
    return _text(treffer.group(1)) if treffer else ""


def _nach_label(zeile: str, label: str) -> str:
    teile = [t.strip() for t in re.split(r"<br\s*/?>", zeile)]
    for t in teile:
        t = _text(t)
        if t.lower().startswith(label.lower()):
            return t[len(label):].strip(" :")
    return ""


def _prompt_zeile(prompt: str, label: str) -> str:
    for zeile in prompt.splitlines():
        z = zeile.replace("**", "").strip()
        if z.lower().startswith(label.lower()):
            return z[len(label):].strip(" :")
    return ""


def fakten(conn, chat_id: int) -> dict[str, dict]:
    from interview_theater import repo, stagescript, szenenkarte, web, web_daten

    token = repo.stelle_web_token_sicher(conn, chat_id)
    daten = web_daten.gruppe_nach_token(conn, token)
    t = szenenkarte._T(chat_id)
    ergebnis: dict[str, dict] = {}
    pdf = web.textbuch_html(daten, token)
    for stueck in pdf.split('<h2 class="szenenkopf">')[1:]:
        nr = _NUMMER.search(stueck[:200])
        if not nr:
            continue
        e = ergebnis.setdefault(nr.group(1), {})
        e["pdf_meta"] = _erstes(r'<p class="meta">(.*?)</p>', stueck)
        e["pdf_besetzung"] = _erstes(r'<p class="besetzung">(.*?)</p>', stueck)
    karten = web._szenenkarten_html(web_daten.szenenkarten(conn, chat_id), chat_id)
    for stueck in re.split(r'<li class="karte-eintrag', karten)[1:]:
        nr = re.search(r'data-nummer="(\d+)"', stueck)
        if not nr:
            continue
        e = ergebnis.setdefault(nr.group(1), {})
        angaben = re.search(r'<p class="karte-angaben">(.*?)</p>', stueck, re.S)
        e["karte_wo"] = _nach_label(angaben.group(1), t._ZEILE_ORT) if angaben else ""
        e["karte_wer"] = _nach_label(angaben.group(1), t._ZEILE_WER) if angaben else ""
    for s in daten["szenen"]:
        if s.get("nummer") is None:
            continue
        e = ergebnis.setdefault(str(s["nummer"]), {})
        e["werkbank_ort"] = (s.get("ort") or "").strip()
        e["werkbank_figuren"] = list(s.get("figuren") or [])
        karte = s.get("karte") or {}
        e["fragen"] = list(karte.get("fragen") or [])
        e["punkte_offen"] = [p for p in karte.get("punkte") or [] if "[OPEN" in p.upper()]
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None or s["entfernt_am"]:
            continue
        prompt = stagescript.baue_nutzertext(conn, chat_id, s)
        e = ergebnis.setdefault(str(s["nummer"]), {})
        e["prompt_wo"] = _prompt_zeile(prompt, t._ZEILE_ORT)
        e["prompt_wer"] = _prompt_zeile(prompt, t._ZEILE_WER)
    return ergebnis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--aus", required=True)
    p.add_argument("--profil", default="padua-2026")
    a = p.parse_args()
    os.environ.setdefault("IT_WORKSHOP", a.profil)
    from interview_theater import db

    conn = db.verbinde(a.db)
    gruppen = [z[0] for z in conn.execute("SELECT chat_id FROM gruppe ORDER BY chat_id")]
    alles = {str(c): fakten(conn, c) for c in gruppen}
    with open(a.aus, "w", encoding="utf-8") as f:
        json.dump(alles, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{sum(len(v) for v in alles.values())} Szenen aus {len(alles)} Gruppen -> {a.aus}")


if __name__ == "__main__":
    main()
```

Hinweise für die Umsetzung:
- `db.verbinde` öffnet die **Kopie** schreibbar. `stelle_web_token_sicher` darf dort ein Token setzen; die Live-DB wird nie geöffnet.
- `_ZEILE_ORT`/`_ZEILE_WER` existieren in `szenenkarte` (`szenenkarte.py:306-309`).
- Weicht ein Label im Prompt von `karte_text` ab, ist das gemessene Label maßgeblich. Dann den Test aus Step 1 auf das tatsächliche Label anpassen, nicht raten.

- [ ] **Step 4: Tests grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_skripte.py`
Expected: `3 passed`

- [ ] **Step 5: Messbasis gegen die Live-Kopie erzeugen (alter Code!)**

Run: `uv run --extra dev python -m scripts.stueckmodell_kopie betrieb/padua.db var/stueckmodell/padua-kopie.db`
Expected: `Kopie: var/stueckmodell/padua-kopie.db`

Run: `uv run --extra dev python -m scripts.stueckmodell_ansichten --db var/stueckmodell/padua-kopie.db --aus var/stueckmodell/ansichten-vorher.json`
Expected: `14 Szenen aus 3 Gruppen -> var/stueckmodell/ansichten-vorher.json` (Stand 10.10.2026: G1 3, G2 5, G3 6 Szenen). Eine andere Zahl ist kein Fehler, muss aber in der Übergabe stehen.

Run: `IT_WORKSHOP=padua-2026 uv run --extra dev python -m scripts.prompt_schnappschuss var/stueckmodell/schnappschuss-vorher.txt`
Expected: `… Zeichen nach var/stueckmodell/schnappschuss-vorher.txt (Profil: padua-2026)`

- [ ] **Step 6: Commit** (nur die Skripte und den Test; `var/` ist nicht eingecheckt)

```bash
git add scripts/stueckmodell_kopie.py scripts/stueckmodell_ansichten.py tests/test_stueckmodell_skripte.py
git commit -m "stueckmodell: Messbasis (Kopie read-only, Ansichten-Fakten je Szene)"
```

---

### Task 1: Schema — neue Spalten und Tabellen

**Files:**
- Modify: `interview_theater/db.py` (Tabelle `szene` um `wer_zusatz`; `szene_figur` um `rolle`, `position`; neue Tabellen `offene_frage`, `veraltet`, `stueck_aenderung` am Ende von `SCHEMA` vor Zeile 1506; `TABELLEN_MIT_CHAT_ID` ab Zeile 1509)
- Modify: `tests/test_ruecknahme.py:126-138` (Verweis-Menge)
- Test: `tests/test_stueck_schema.py`

**Interfaces:**
- Produces: Spalten `szene.wer_zusatz TEXT`, `szene_figur.rolle TEXT`, `szene_figur.position INTEGER` sowie die Tabellen

```sql
offene_frage(id, chat_id, szene_id, text, status, antwort, quelle, erstellt_am, geschlossen_am)
veraltet(id, chat_id, szene_id, ansicht, grund, aenderung_id, erstellt_am, angeboten_am, erledigt_am, entscheidung)
stueck_aenderung(id, chat_id, art, ziel, vorher, nachher, quelle, erstellt_am)
```

- [ ] **Step 1: Failing test**

```python
# tests/test_stueck_schema.py
from interview_theater import db


def _spalten(conn, tabelle):
    return {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}


def test_neue_stellen_existieren(conn):
    assert "wer_zusatz" in _spalten(conn, "szene")
    assert {"rolle", "position"} <= _spalten(conn, "szene_figur")
    assert {"szene_id", "text", "status", "antwort", "quelle"} <= _spalten(conn, "offene_frage")
    assert {"szene_id", "ansicht", "grund", "angeboten_am", "erledigt_am", "entscheidung"} <= _spalten(conn, "veraltet")
    assert {"art", "ziel", "vorher", "nachher", "quelle"} <= _spalten(conn, "stueck_aenderung")


def test_neue_tabellen_stehen_in_der_loeschzusage():
    for t in ("offene_frage", "veraltet", "stueck_aenderung"):
        assert t in db.TABELLEN_MIT_CHAT_ID


def test_alte_datenbank_bekommt_die_spalten_additiv(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.executescript(
        "CREATE TABLE szene_figur (chat_id INTEGER NOT NULL, szene_id INTEGER NOT NULL,"
        " figur_id INTEGER NOT NULL, PRIMARY KEY (szene_id, figur_id));"
        "INSERT INTO szene_figur VALUES (1, 2, 3);"
    )
    db.initialisiere(c)
    assert c.execute("SELECT rolle, position FROM szene_figur").fetchone() == (None, None)
```

- [ ] **Step 2: Rot prüfen**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_schema.py`
Expected: FAIL (`no such table: offene_frage` bzw. AssertionError)

- [ ] **Step 3: Schema ergänzen**

In `szene` nach `volltext_it TEXT,` (db.py:752):

```sql
  -- Stueckmodell (Karte t_fd88600b, 10.10.2026): wer in der Szene ist,
  -- ohne eine Figur zu sein ("tutto il pubblico", "uno di noi alla camera").
  -- Zusammen mit szene_figur die EINE Stelle fuer "wer" -- karte.wer
  -- entfaellt. Additiv ueber _migriere_fehlende_spalten.
  wer_zusatz        TEXT,
```

`szene_figur` (db.py:1050) ersetzen durch:

```sql
CREATE TABLE IF NOT EXISTS szene_figur (
  chat_id    INTEGER NOT NULL,
  szene_id   INTEGER NOT NULL,
  figur_id   INTEGER NOT NULL,
  -- Stueckmodell (t_fd88600b): die Rolle der Figur in DIESER Szene
  -- ("(Arlecchino)", "fuori campo") und ihre Reihenfolge in der Besetzung.
  -- NULL = keine Rolle / Reihenfolge nach figur.id wie bisher.
  rolle      TEXT,
  position   INTEGER,
  PRIMARY KEY (szene_id, figur_id)
);
```

Vor dem schließenden `"""` von `SCHEMA` (nach `idx_bedarf_punkt_gruppe`, db.py:1505):

```sql
-- Stueckmodell (Karte t_fd88600b, Birk 10.10.2026): die EINE Stelle fuer
-- offene Fragen -- karte.fragen und "[OPEN] ..."-Punkte entfallen. status:
-- offen (blockiert "Yes, save" der Karte) | vertagt ("I don't know", steht
-- als [OPEN]-Punkt auf der Karte) | beantwortet | uebersprungen.
CREATE TABLE IF NOT EXISTS offene_frage (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  szene_id        INTEGER,
  text            TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'offen',
  antwort         TEXT,
  quelle          TEXT NOT NULL,
  erstellt_am     TEXT NOT NULL,
  geschlossen_am  TEXT
);
CREATE INDEX IF NOT EXISTS idx_offene_frage_szene ON offene_frage(chat_id, szene_id, status);

-- Stueckmodell: Prosa, die nach einer Aenderung nicht mehr passt. Prosa wird
-- nie still umgeschrieben -- die Gruppe bekommt "Szene N passt nicht mehr zu
-- ... -- neu schreiben?" (angeboten_am) und entscheidet (entscheidung:
-- neu | lassen | neu_geschrieben). ansicht: script | kopf.
CREATE TABLE IF NOT EXISTS veraltet (
  id            INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL,
  szene_id      INTEGER,
  ansicht       TEXT NOT NULL,
  grund         TEXT NOT NULL,
  aenderung_id  INTEGER,
  erstellt_am   TEXT NOT NULL,
  angeboten_am  TEXT,
  erledigt_am   TEXT,
  entscheidung  TEXT
);
CREATE INDEX IF NOT EXISTS idx_veraltet_offen ON veraltet(chat_id, erledigt_am);

-- Stueckmodell: jede Mutation (stueck.py) und jede Migrationsentscheidung,
-- nur anhaengend. art = Funktionsname oder konflikt_* (Migration); ziel,
-- vorher, nachher = JSON.
CREATE TABLE IF NOT EXISTS stueck_aenderung (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  art          TEXT NOT NULL,
  ziel         TEXT NOT NULL,
  vorher       TEXT,
  nachher      TEXT,
  quelle       TEXT NOT NULL,
  erstellt_am  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stueck_aenderung_gruppe ON stueck_aenderung(chat_id, id);
```

In `TABELLEN_MIT_CHAT_ID` nach `"bedarf_punkt",`:

```python
    # Stueckmodell (Karte t_fd88600b, 10.10.2026).
    "offene_frage",
    "veraltet",
    "stueck_aenderung",
```

In `tests/test_ruecknahme.py` die erwartete Menge um zwei Einträge ergänzen (Spalte `szene_id`):

```python
        # Stueckmodell (t_fd88600b): offene Fragen und Veraltet-Vermerke je Szene.
        ("offene_frage", "szene_id", "szene"),
        ("veraltet", "szene_id", "szene"),
```

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_schema.py tests/test_db.py tests/test_ruecknahme.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/db.py tests/test_stueck_schema.py tests/test_ruecknahme.py
git commit -m "stueckmodell: Schema (wer_zusatz, szene_figur.rolle/position, offene_frage, veraltet, stueck_aenderung)"
```

---

### Task 2: repo — Schreib- und Lesefunktionen der neuen Stellen

**Files:**
- Modify: `interview_theater/repo.py` (neue Funktionen nach `szene_figuren`, repo.py:~3346; `szene_figuren` ORDER BY anpassen)
- Test: `tests/test_stueck_repo.py`

**Interfaces (Produces, alle `@_gesperrt`, `commit()` je Schreibfunktion):**

```python
def setze_szenenort(conn, szene_id: int, ort: str | None) -> None
def besetzung(conn, szene_id: int) -> list[sqlite3.Row]          # figur_id, name, rolle, position
def setze_besetzung(conn, chat_id: int, szene_id: int,
                    eintraege: list[tuple[int, str | None]], zusatz: str | None) -> None
def aktualisiere_szenenkarte(conn, chat_id: int, szene_id: int, karte_json: str,
                             ausloeser: str, notiz_text: str | None = None) -> None   # Abnahme bleibt
def setze_szenenkarte_offen(conn, szene_id: int) -> None         # karte_bestaetigt_am = NULL
def nummeriere_szenen(conn, chat_id: int, szene_ids: list[int]) -> None
def lege_offene_frage_an(conn, chat_id: int, szene_id: int | None, text: str,
                         quelle: str, status: str = "offen") -> int
def offene_fragen(conn, chat_id: int, szene_id: int | None,
                  status: tuple[str, ...] = ("offen", "vertagt")) -> list[sqlite3.Row]
def fragen_der_szene(conn, chat_id: int, szene_id: int | None) -> list[sqlite3.Row]   # alle Status
def hole_offene_frage(conn, frage_id: int) -> sqlite3.Row | None
def setze_frage_status(conn, frage_id: int, status: str, antwort: str | None = None) -> None
def merke_veraltet(conn, chat_id: int, szene_id: int | None, ansicht: str,
                   grund: str, aenderung_id: int | None) -> int
def offene_veraltet(conn, chat_id: int, nur_unangeboten: bool = False) -> list[sqlite3.Row]
def hole_veraltet(conn, veraltet_id: int) -> sqlite3.Row | None
def markiere_veraltet_angeboten(conn, veraltet_id: int) -> None
def erledige_veraltet(conn, veraltet_id: int, entscheidung: str) -> None
def erledige_veraltet_fuer(conn, chat_id: int, szene_id: int | None, ansicht: str,
                           entscheidung: str) -> int
def merke_stueck_aenderung(conn, chat_id: int, art: str, ziel: dict,
                           vorher, nachher, quelle: str) -> int
def stueck_aenderungen(conn, chat_id: int, quelle: str | None = None) -> list[sqlite3.Row]
```

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_repo.py
import json

from interview_theater import repo


def _szene(conn, nummer=1):
    return repo.stelle_szene_sicher(conn, 1, nummer)


def test_besetzung_mit_rolle_und_reihenfolge(conn):
    for n in ("Anna", "Pietro"):
        repo.setze_figur(conn, 1, n, "")
    anna, pietro = (repo.hole_figur(conn, 1, n)["id"] for n in ("Anna", "Pietro"))
    sid = _szene(conn)
    repo.setze_besetzung(conn, 1, sid, [(pietro, None), (anna, "(Arlecchino)")], "tutto il pubblico")
    reihen = repo.besetzung(conn, sid)
    assert [(r["name"], r["rolle"]) for r in reihen] == [("Pietro", None), ("Anna", "(Arlecchino)")]
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "tutto il pubblico"
    # szene_figuren folgt derselben Reihenfolge
    assert [f["name"] for f in repo.szene_figuren(conn, sid)] == ["Pietro", "Anna"]


def test_aktualisiere_szenenkarte_laesst_abnahme_stehen(conn):
    sid = _szene(conn)
    repo.setze_szenenkarte(conn, sid, json.dumps({"worum": "a"}))
    repo.setze_szenenkarte_bestaetigt(conn, sid)
    repo.aktualisiere_szenenkarte(conn, 1, sid, json.dumps({"worum": "b"}), "aenderung", "n")
    s = repo.hole_szene(conn, sid)
    assert json.loads(s["karte"])["worum"] == "b"
    assert s["karte_bestaetigt_am"]
    assert repo.karte_verlauf(conn, 1, sid)[-1]["notiz_text"] == "n"


def test_offene_frage_lebenslauf(conn):
    sid = _szene(conn)
    fid = repo.lege_offene_frage_an(conn, 1, sid, "Wo steht Giona?", "test")
    assert [f["id"] for f in repo.offene_fragen(conn, 1, sid)] == [fid]
    repo.setze_frage_status(conn, fid, "beantwortet", "im Loch")
    assert repo.offene_fragen(conn, 1, sid) == []
    f = repo.hole_offene_frage(conn, fid)
    assert (f["status"], f["antwort"]) == ("beantwortet", "im Loch") and f["geschlossen_am"]


def test_veraltet_eine_offene_zeile_je_szene_und_ansicht(conn):
    sid = _szene(conn)
    a = repo.merke_veraltet(conn, 1, sid, "script", "neuer Ort", None)
    b = repo.merke_veraltet(conn, 1, sid, "script", "neue Figur Anna", None)
    assert a == b
    [zeile] = repo.offene_veraltet(conn, 1)
    assert zeile["grund"] == "neuer Ort; neue Figur Anna"
    repo.erledige_veraltet(conn, a, "lassen")
    assert repo.offene_veraltet(conn, 1) == []


def test_nummeriere_szenen(conn):
    a, b, c = (_szene(conn, n) for n in (1, 2, 3))
    repo.nummeriere_szenen(conn, 1, [c, a, b])
    assert [repo.hole_szene(conn, i)["nummer"] for i in (a, b, c)] == [2, 3, 1]


def test_stueck_aenderung_nur_anhaengend(conn):
    i = repo.merke_stueck_aenderung(conn, 1, "setze_ort", {"szene": 1}, "Bar", "Piazza", "test")
    [z] = repo.stueck_aenderungen(conn, 1)
    assert z["id"] == i and json.loads(z["nachher"]) == "Piazza"
```

- [ ] **Step 2: Rot**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_repo.py`
Expected: FAIL `AttributeError: module 'interview_theater.repo' has no attribute 'setze_besetzung'`

- [ ] **Step 3: Implementieren** (in `repo.py` nach `szene_figuren`; das `ORDER BY` in `szene_figuren` wird `ORDER BY sf.position IS NULL, sf.position ASC, f.id ASC`, für Altbestand ohne `position` byte-gleich)

```python
# --- Stueckmodell (Karte t_fd88600b, 10.10.2026) ---------------------------
# Die Schreibfunktionen hier ruft NUR stueck.py (tests/test_stueck_einzige_
# schreibstelle.py) -- sonst gaebe es wieder einen zweiten Weg zu derselben
# Tatsache.


@_gesperrt
def setze_szenenort(conn: sqlite3.Connection, szene_id: int, ort: str | None) -> None:
    conn.execute("UPDATE szene SET ort = ?, geaendert_am = ? WHERE id = ?",
                 (ort, _jetzt_genau(), szene_id))
    conn.commit()


@_gesperrt
def besetzung(conn: sqlite3.Connection, szene_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT f.id AS figur_id, f.name AS name, sf.rolle AS rolle, sf.position AS position "
        "FROM szene_figur sf JOIN figur f ON f.id = sf.figur_id "
        "WHERE sf.szene_id = ? AND f.entfernt_am IS NULL "
        "ORDER BY sf.position IS NULL, sf.position ASC, f.id ASC",
        (szene_id,),
    ).fetchall()


@_gesperrt
def setze_besetzung(conn: sqlite3.Connection, chat_id: int, szene_id: int,
                    eintraege: list[tuple[int, str | None]], zusatz: str | None) -> None:
    conn.execute("DELETE FROM szene_figur WHERE szene_id = ?", (szene_id,))
    for position, (figur_id, rolle) in enumerate(eintraege, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO szene_figur (chat_id, szene_id, figur_id, rolle, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, szene_id, figur_id, rolle, position),
        )
    conn.execute("UPDATE szene SET wer_zusatz = ?, geaendert_am = ? WHERE id = ?",
                 (zusatz, _jetzt_genau(), szene_id))
    conn.commit()


@_gesperrt
def aktualisiere_szenenkarte(conn: sqlite3.Connection, chat_id: int, szene_id: int,
                             karte_json: str, ausloeser: str,
                             notiz_text: str | None = None) -> None:
    """Karte + neue ``karte_verlauf``-Fassung in EINER Transaktion, OHNE die
    Abnahme zurueckzunehmen -- eine ausdrueckliche Aenderung der Gruppe
    (``stueck.karte_aendern``) ist keine neue Karte."""
    conn.execute("UPDATE szene SET karte = ? WHERE id = ?", (karte_json, szene_id))
    naechste = conn.execute(
        "SELECT COALESCE(MAX(fassung_nr), 0) + 1 FROM karte_verlauf WHERE szene_id = ?",
        (szene_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO karte_verlauf (chat_id, szene_id, fassung_nr, karte_json, ausloeser, "
        "notiz_text, erstellt_am) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chat_id, szene_id, naechste, karte_json, ausloeser, notiz_text, _jetzt()),
    )
    conn.commit()


@_gesperrt
def setze_szenenkarte_offen(conn: sqlite3.Connection, szene_id: int) -> None:
    conn.execute("UPDATE szene SET karte_bestaetigt_am = NULL WHERE id = ?", (szene_id,))
    conn.commit()


@_gesperrt
def nummeriere_szenen(conn: sqlite3.Connection, chat_id: int, szene_ids: list[int]) -> None:
    for nummer, szene_id in enumerate(szene_ids, start=1):
        conn.execute("UPDATE szene SET nummer = ? WHERE id = ? AND chat_id = ?",
                     (nummer, szene_id, chat_id))
    conn.commit()


@_gesperrt
def lege_offene_frage_an(conn: sqlite3.Connection, chat_id: int, szene_id: int | None,
                         text: str, quelle: str, status: str = "offen") -> int:
    cur = conn.execute(
        "INSERT INTO offene_frage (chat_id, szene_id, text, status, quelle, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, szene_id, text, status, quelle, _jetzt_genau()),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
def offene_fragen(conn: sqlite3.Connection, chat_id: int, szene_id: int | None,
                  status: tuple[str, ...] = ("offen", "vertagt")) -> list[sqlite3.Row]:
    platz = ",".join("?" * len(status))
    return conn.execute(
        f"SELECT * FROM offene_frage WHERE chat_id = ? AND szene_id IS ? "
        f"AND status IN ({platz}) ORDER BY id ASC",
        (chat_id, szene_id, *status),
    ).fetchall()


@_gesperrt
def fragen_der_szene(conn: sqlite3.Connection, chat_id: int,
                     szene_id: int | None) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM offene_frage WHERE chat_id = ? AND szene_id IS ? ORDER BY id ASC",
        (chat_id, szene_id),
    ).fetchall()


@_gesperrt
def hole_offene_frage(conn: sqlite3.Connection, frage_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM offene_frage WHERE id = ?", (frage_id,)).fetchone()


@_gesperrt
def setze_frage_status(conn: sqlite3.Connection, frage_id: int, status: str,
                       antwort: str | None = None) -> None:
    geschlossen = _jetzt_genau() if status in ("beantwortet", "uebersprungen") else None
    conn.execute(
        "UPDATE offene_frage SET status = ?, antwort = COALESCE(?, antwort), "
        "geschlossen_am = ? WHERE id = ?",
        (status, antwort, geschlossen, frage_id),
    )
    conn.commit()


@_gesperrt
def merke_veraltet(conn: sqlite3.Connection, chat_id: int, szene_id: int | None,
                   ansicht: str, grund: str, aenderung_id: int | None) -> int:
    """EINE offene Zeile je (Szene, Ansicht): ein weiterer Grund wird
    angehaengt und die Zeile neu angeboten (``angeboten_am`` = NULL)."""
    offen = conn.execute(
        "SELECT id, grund FROM veraltet WHERE chat_id = ? AND szene_id IS ? AND ansicht = ? "
        "AND erledigt_am IS NULL",
        (chat_id, szene_id, ansicht),
    ).fetchone()
    if offen is not None:
        if grund not in offen["grund"].split("; "):
            conn.execute("UPDATE veraltet SET grund = ?, angeboten_am = NULL WHERE id = ?",
                         (f"{offen['grund']}; {grund}", offen["id"]))
            conn.commit()
        return offen["id"]
    cur = conn.execute(
        "INSERT INTO veraltet (chat_id, szene_id, ansicht, grund, aenderung_id, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, szene_id, ansicht, grund, aenderung_id, _jetzt_genau()),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
def offene_veraltet(conn: sqlite3.Connection, chat_id: int,
                    nur_unangeboten: bool = False) -> list[sqlite3.Row]:
    zusatz = " AND angeboten_am IS NULL" if nur_unangeboten else ""
    return conn.execute(
        "SELECT * FROM veraltet WHERE chat_id = ? AND erledigt_am IS NULL" + zusatz
        + " ORDER BY id ASC", (chat_id,),
    ).fetchall()


@_gesperrt
def hole_veraltet(conn: sqlite3.Connection, veraltet_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM veraltet WHERE id = ?", (veraltet_id,)).fetchone()


@_gesperrt
def markiere_veraltet_angeboten(conn: sqlite3.Connection, veraltet_id: int) -> None:
    conn.execute("UPDATE veraltet SET angeboten_am = ? WHERE id = ?", (_jetzt_genau(), veraltet_id))
    conn.commit()


@_gesperrt
def erledige_veraltet(conn: sqlite3.Connection, veraltet_id: int, entscheidung: str) -> None:
    conn.execute("UPDATE veraltet SET erledigt_am = ?, entscheidung = ? WHERE id = ?",
                 (_jetzt_genau(), entscheidung, veraltet_id))
    conn.commit()


@_gesperrt
def erledige_veraltet_fuer(conn: sqlite3.Connection, chat_id: int, szene_id: int | None,
                           ansicht: str, entscheidung: str) -> int:
    cur = conn.execute(
        "UPDATE veraltet SET erledigt_am = ?, entscheidung = ? WHERE chat_id = ? "
        "AND szene_id IS ? AND ansicht = ? AND erledigt_am IS NULL",
        (_jetzt_genau(), entscheidung, chat_id, szene_id, ansicht),
    )
    conn.commit()
    return cur.rowcount


@_gesperrt
def merke_stueck_aenderung(conn: sqlite3.Connection, chat_id: int, art: str, ziel: dict,
                           vorher, nachher, quelle: str) -> int:
    cur = conn.execute(
        "INSERT INTO stueck_aenderung (chat_id, art, ziel, vorher, nachher, quelle, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chat_id, art, json.dumps(ziel, ensure_ascii=False),
         json.dumps(vorher, ensure_ascii=False), json.dumps(nachher, ensure_ascii=False),
         quelle, _jetzt_genau()),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
def stueck_aenderungen(conn: sqlite3.Connection, chat_id: int,
                       quelle: str | None = None) -> list[sqlite3.Row]:
    if quelle is None:
        return conn.execute("SELECT * FROM stueck_aenderung WHERE chat_id = ? ORDER BY id",
                            (chat_id,)).fetchall()
    return conn.execute(
        "SELECT * FROM stueck_aenderung WHERE chat_id = ? AND quelle = ? ORDER BY id",
        (chat_id, quelle)).fetchall()
```

(`json` ist in `repo.py` schon importiert; falls nicht, oben ergänzen.)

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_repo.py tests/test_repo.py tests/test_ruecknahme_rundreise.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/repo.py tests/test_stueck_repo.py
git commit -m "stueckmodell: repo-Funktionen fuer Ort, Besetzung, offene Fragen, Veraltet, Aenderungsprotokoll"
```

---

### Task 3: `stueck_sicht.py` — die eine Ableitung

**Files:**
- Create: `interview_theater/stueck_sicht.py`
- Test: `tests/test_stueck_sicht.py`

**Interfaces (Produces, reine Funktionen, kein Projektimport):**

```python
STRUKTUR_SCHLUESSEL: tuple[str, ...] = ("ort", "wer", "fragen")
OFFEN_PUNKT: re.Pattern            # "[OPEN] text" / "[APERTO] text" / "[OFFEN] text" -> group(1) = text
def normalisiert(text) -> str
def roh_ohne_struktur(karte: dict) -> dict
def teile_wer(text: str | None) -> list[str]
def ordne_besetzung(text: str | None, figuren: dict[str, int]
                    ) -> tuple[list[tuple[int, str | None]], list[str]]
def wer_text(besetzung: list[tuple[str, str | None]], zusatz: str | None) -> str
def karte_ansicht(roh: dict | None, *, ort: str | None,
                  besetzung: list[tuple[str, str | None]], zusatz: str | None,
                  fragen_offen: list[str], fragen_vertagt: list[str],
                  punkt_offen: str = "[OPEN] {frage}") -> dict | None
```

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_sicht.py
from interview_theater import stueck_sicht as sicht


def test_karte_ansicht_ignoriert_struktur_aus_dem_json():
    roh = {"typ": "spoken", "worum": "w", "ort": "GIFT", "wer": "GIFT", "fragen": ["GIFT?"],
           "punkte": ["p"], "zitate": []}
    k = sicht.karte_ansicht(roh, ort="Piazza", besetzung=[("Anna", "(Arlecchino)")],
                            zusatz="tutto il pubblico", fragen_offen=["Wo?"],
                            fragen_vertagt=["Wann?"])
    assert k["ort"] == "Piazza"
    assert k["wer"] == "Anna (Arlecchino), tutto il pubblico"
    assert k["fragen"] == ["Wo?"]
    assert k["punkte"] == ["p", "[OPEN] Wann?"]
    assert "GIFT" not in repr(k)


def test_ohne_karte_keine_ansicht():
    assert sicht.karte_ansicht(None, ort="x", besetzung=[], zusatz=None,
                               fragen_offen=[], fragen_vertagt=[]) is None


def test_ordne_besetzung_rolle_und_rest():
    figuren = {"anna": 1, "pietro": 2, "francesco": 3}
    eintraege, rest = sicht.ordne_besetzung(
        "Anna (Arlecchino), Pietro; Francesco fuori campo e tutto il pubblico", figuren)
    assert eintraege == [(1, "(Arlecchino)"), (2, None), (3, "fuori campo")]
    assert rest == ["tutto il pubblico"]


def test_ordne_besetzung_kein_teiltreffer():
    eintraege, rest = sicht.ordne_besetzung("Annabella", {"anna": 1})
    assert eintraege == [] and rest == ["Annabella"]


def test_offen_punkt():
    assert sicht.OFFEN_PUNKT.match("[OPEN] Wer spielt?").group(1) == "Wer spielt?"
    assert sicht.OFFEN_PUNKT.match("[APERTO]: Chi?").group(1) == "Chi?"
    assert sicht.OFFEN_PUNKT.match("Kein [OPEN] hier") is None
```

- [ ] **Step 2: Rot**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_sicht.py`
Expected: FAIL `ModuleNotFoundError: interview_theater.stueck_sicht`

- [ ] **Step 3: Implementieren**

```python
# interview_theater/stueck_sicht.py
"""Die abgeleiteten Ansichten des Stueckmodells (Karte t_fd88600b, Birk
10.10.2026) -- reine Funktionen, kein Projektimport, kein SQL.

Jede Tatsache steht an genau einer Stelle (Ort: ``szene.ort``; wer:
``szene_figur`` + ``szene.wer_zusatz``; offene Fragen: ``offene_frage``).
Hier wird daraus die Karte, wie Script-Kopf, PDF, Werkbank und Prompt sie
zeigen. Bot (``stueck.karte``) und Webserver (``web_daten``) rufen DIESELBE
Funktion -- eine zweite Formatierung waere eine zweite Wahrheit."""

from __future__ import annotations

import re

#: Kartenschluessel, die in ``szene.karte`` NICHT mehr gelesen werden -- sie
#: haben ihre eine Stelle woanders.
STRUKTUR_SCHLUESSEL = ("ort", "wer", "fragen")

#: Ein Kartenpunkt, der in Wahrheit eine offene Frage ist.
OFFEN_PUNKT = re.compile(r"^\s*[\[(]\s*(?:OPEN|APERTO|OFFEN)\s*[\])]\s*:?\s*(.+?)\s*$", re.I)

_TRENNER = re.compile(r"\s*[;,]\s*|\s+(?:e|and|und)\s+", re.I)


def normalisiert(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def roh_ohne_struktur(karte: dict) -> dict:
    return {k: v for k, v in karte.items() if k not in STRUKTUR_SCHLUESSEL}


def teile_wer(text: str | None) -> list[str]:
    return [t.strip(" .") for t in _TRENNER.split(text or "") if t and t.strip(" .")]


def ordne_besetzung(text: str | None, figuren: dict[str, int]
                    ) -> tuple[list[tuple[int, str | None]], list[str]]:
    """``figuren``: normalisierter Name -> figur_id. Ein Stueck von ``text``,
    das mit einem bekannten Namen als ganzem Wort BEGINNT, wird diese Figur;
    der Rest des Stuecks ist ihre Rolle in der Szene. Alles andere bleibt
    woertlich als Zusatz -- nichts wird geraten, nichts geht verloren."""
    namen = sorted(figuren, key=len, reverse=True)
    eintraege: list[tuple[int, str | None]] = []
    rest: list[str] = []
    gesehen: set[int] = set()
    for stueck in teile_wer(text):
        klein = normalisiert(stueck)
        treffer = next((n for n in namen if klein == n or klein.startswith(n + " ")
                        or klein.startswith(n + "(")), None)
        if treffer is None:
            rest.append(stueck)
            continue
        figur_id = figuren[treffer]
        if figur_id in gesehen:
            continue
        gesehen.add(figur_id)
        rolle = stueck.strip()[len(treffer):].strip() or None
        eintraege.append((figur_id, rolle))
    return eintraege, rest


def wer_text(besetzung: list[tuple[str, str | None]], zusatz: str | None) -> str:
    teile = [f"{name} {rolle}".strip() if rolle else name for name, rolle in besetzung]
    if (zusatz or "").strip():
        teile.append(zusatz.strip())
    return ", ".join(teile)


def karte_ansicht(roh: dict | None, *, ort: str | None,
                  besetzung: list[tuple[str, str | None]], zusatz: str | None,
                  fragen_offen: list[str], fragen_vertagt: list[str],
                  punkt_offen: str = "[OPEN] {frage}") -> dict | None:
    if roh is None:
        return None
    karte = roh_ohne_struktur(roh)
    karte["ort"] = (ort or "").strip()
    karte["wer"] = wer_text(besetzung, zusatz)
    karte["punkte"] = list(karte.get("punkte") or []) + [
        punkt_offen.format(frage=f) for f in fragen_vertagt]
    karte["fragen"] = list(fragen_offen)
    return karte
```

Hinweis: `ordne_besetzung` schneidet die Rolle aus dem Originaltext (`stueck.strip()[len(treffer):]`). Der normalisierte Name hat dieselbe Länge wie der getrimmte Originalname, solange darin keine Mehrfach-Leerzeichen stehen. Für Namen mit inneren Mehrfach-Leerzeichen gilt die Rolle als `None` (ein Testfall genügt nicht, hier nicht weiter ausbauen).

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_sicht.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add interview_theater/stueck_sicht.py tests/test_stueck_sicht.py
git commit -m "stueckmodell: stueck_sicht -- die eine Ableitung der Karte (Ort/Wer/Fragen)"
```

---

### Task 4: `stueck.py` Teil A — Ergebnis, Protokoll, Veraltet, `setze_ort`, `setze_rahmen`, Besetzung

**Files:**
- Create: `interview_theater/stueck.py`
- Create: `tests/stueck_hilfe.py`
- Modify: `interview_theater/sprachen/en/texte.toml`, `interview_theater/sprachen/it/texte.toml` (Abschnitt `[stueck]`)
- Test: `tests/test_stueck_ort_besetzung.py`

**Interfaces:**
- Consumes: Task 2 (`repo.*`), Task 3 (`stueck_sicht.*`)
- Produces:

```python
@dataclass(frozen=True)
class Ergebnis:
    ok: bool
    aenderung_id: int | None = None
    diff: tuple[str, ...] = ()
    warnungen: tuple[str, ...] = ()
    veraltet: tuple[int, ...] = ()
    fehler: str | None = None          # "beschaeftigt" | "unbekannte_szene" | "unbekannte_figur"
                                       # | "keine_karte" | "ungueltig" | "unbekannte_frage"
    frage_id: int | None = None
    def als_dict(self) -> dict

QUELLE_GRUPPE = "gruppe"; QUELLE_SCRIPT = "script"; QUELLE_KARTE_MODELL = "karte_modell"
QUELLE_PLANUNG = "planung"; QUELLE_AGENT = "agent"
INTERNE_QUELLEN: frozenset[str]   # {script, karte_modell, planung}: kein Busy-Gate

def karte(conn, szene) -> dict | None
def setze_rahmen(conn, chat_id: int, *, rahmen: str, quelle: str = QUELLE_GRUPPE) -> Ergebnis
def setze_ort(conn, chat_id: int, *, szene: int, ort: str | None,
              quelle: str = QUELLE_GRUPPE) -> Ergebnis
def setze_besetzung(conn, chat_id: int, *, szene: int, namen: list[str],
                    zusatz: str | None = None, quelle: str = QUELLE_GRUPPE) -> Ergebnis
def figur_hinzu(conn, chat_id: int, *, name: str, szene: int | None = None,
                rolle: str | None = None, beschreibung: str | None = None,
                quelle: str = QUELLE_GRUPPE) -> Ergebnis
def figur_aus_szene(conn, chat_id: int, *, name: str, szene: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis
```

Regeln, die die Tests festnageln:
- **Busy-Gate (Problem 5):** Läuft für die Gruppe ein Schreiblauf (`ueberarbeitung.laeuft(chat_id)`, die ODER-Verknüpfung der Sperren von szene, kurzgeschichte, szenenkarte und stagescript), lehnt jede Mutation mit `fehler="beschaeftigt"` ab. Ausgenommen sind `INTERNE_QUELLEN`; das ist der Schreiber selbst.
- **Veraltet (Problem 3):**
  - Hat die Zielszene `volltext`, entsteht `veraltet(script)`.
  - Andere Szenen mit `volltext` werden nur markiert, wenn ihr Text den **alten** Wert wörtlich enthält (normalisiert, mindestens 4 Zeichen).
  - `stage_kopf` (falls gesetzt) wird markiert, wenn er den alten Wert enthält (Ort) oder wenn sich die Figurenmenge des Stücks ändert.
  - Quelle `script` markiert die eigene Szene nicht, denn der Text ist dort die Quelle.
  - Prosa wird **nie** geschrieben.
- **Protokoll:** jede wirksame Mutation schreibt genau eine `stueck_aenderung`. Eine Mutation ohne Änderung ist ein No-op mit `ok=True` ohne Protokoll.
- Unbekannte Szenennummer → `fehler="unbekannte_szene"`.
- `setze_besetzung`: Namen, zu denen keine Figur existiert, ergeben `fehler="unbekannte_figur"`. Anlegen geht nur über `figur_hinzu`, Birks Regel aus `erkenner._figuren_aus_namen`.

- [ ] **Step 1: Testhilfe und failing tests**

```python
# tests/stueck_hilfe.py
"""Testhilfe Stueckmodell (Karte t_fd88600b): Karten und Szenen nur ueber
die Mutations-Schnittstelle anlegen -- nie Ort/Wer/Fragen ins Karten-JSON."""

from interview_theater import repo, stueck

KARTE = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}


class TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def entferne_knoepfe(self, *a, **k):
        pass


def lege_karte_an(conn, chat_id=1, nummer=1, *, ort=None, wer=None, fragen=(),
                  bestaetigt=False, **felder) -> int:
    sid = repo.stelle_szene_sicher(conn, chat_id, nummer)
    karte = dict(KARTE, **felder)
    if ort is not None:
        karte["ort"] = ort
    if wer is not None:
        karte["wer"] = wer
    karte["fragen"] = list(fragen)
    stueck.karte_aus_modell(conn, chat_id, szene=nummer, karte=karte,
                            ausloeser="erstentwurf")
    if bestaetigt:
        repo.setze_szenenkarte_bestaetigt(conn, sid)
    return sid
```

(`karte_aus_modell` kommt in Task 6. Bis dahin importieren die Tests dieses Tasks die Hilfe nur für `TG`.)

```python
# tests/test_stueck_ort_besetzung.py
import json

import pytest

from interview_theater import repo, stueck


def _szene(conn, nummer=1, volltext=None, karte=True):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    if karte:
        repo.setze_szenenkarte(conn, sid, json.dumps(
            {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}))
    if volltext:
        repo.setze_stagescript(conn, sid, volltext, None)
    return sid


def test_setze_ort_eine_stelle_und_protokoll(conn):
    sid = _szene(conn)
    e = stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert e.ok and e.aenderung_id
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza"
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["ort"] == "Piazza"
    [a] = repo.stueck_aenderungen(conn, 1)
    assert a["art"] == "setze_ort"


def test_gleicher_ort_ist_kein_ereignis(conn):
    _szene(conn)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    e = stueck.setze_ort(conn, 1, szene=1, ort="  piazza ")
    assert e.ok and e.aenderung_id is None
    assert len(repo.stueck_aenderungen(conn, 1)) == 1


def test_ort_markiert_eigene_und_erwaehnende_szene_nie_umschreiben(conn):
    s1 = _szene(conn, 1, volltext="Sala prove. ANNA: Ciao.")
    s2 = _szene(conn, 2, volltext="Wieder in der Sala prove.")
    s3 = _szene(conn, 3, volltext="Draussen.")
    stueck.setze_ort(conn, 1, szene=1, ort="Sala prove")
    e = stueck.setze_ort(conn, 1, szene=1, ort="Sala riunioni")
    markiert = {v["szene_id"] for v in repo.offene_veraltet(conn, 1)}
    assert markiert == {s1, s2}
    assert len(e.veraltet) == 2
    assert repo.hole_szene(conn, s1)["volltext"] == "Sala prove. ANNA: Ciao."  # nie still umgeschrieben
    assert s3 not in markiert


def test_quelle_script_markiert_die_eigene_szene_nicht(conn):
    s1 = _szene(conn, 1, volltext="Piazza")
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza", quelle=stueck.QUELLE_SCRIPT)
    assert repo.offene_veraltet(conn, 1) == []


def test_busy_gate(conn, monkeypatch):
    from interview_theater import ueberarbeitung

    _szene(conn)
    monkeypatch.setattr(ueberarbeitung, "laeuft", lambda chat_id: True)
    e = stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert not e.ok and e.fehler == "beschaeftigt"
    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 1))["ort"] is None
    assert stueck.setze_ort(conn, 1, szene=1, ort="Piazza", quelle=stueck.QUELLE_SCRIPT).ok


def test_unbekannte_szene(conn):
    assert stueck.setze_ort(conn, 1, szene=9, ort="x").fehler == "unbekannte_szene"


def test_figur_hinzu_legt_an_und_besetzt_mit_rolle(conn):
    sid = _szene(conn, volltext="ANNA: Ciao.")
    e = stueck.figur_hinzu(conn, 1, name="Chicca", szene=1, rolle="(Cover)")
    assert e.ok
    assert repo.hole_figur(conn, 1, "Chicca") is not None
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["wer"] == "Chicca (Cover)"
    assert {v["szene_id"] for v in repo.offene_veraltet(conn, 1)} == {sid}


def test_figur_hinzu_ueberschreibt_keine_beschreibung(conn):
    repo.setze_figur(conn, 1, "Anna", "Studentin")
    _szene(conn)
    stueck.figur_hinzu(conn, 1, name="anna", szene=1)
    assert repo.hole_figur(conn, 1, "Anna")["beschreibung"] == "Studentin"


def test_figur_aus_szene(conn):
    sid = _szene(conn)
    stueck.figur_hinzu(conn, 1, name="Anna", szene=1)
    stueck.figur_aus_szene(conn, 1, name="Anna", szene=1)
    assert repo.besetzung(conn, sid) == []


def test_setze_besetzung_nur_bekannte_figuren(conn):
    _szene(conn)
    repo.setze_figur(conn, 1, "Anna", "")
    assert stueck.setze_besetzung(conn, 1, szene=1, namen=["Anna", "Niemand"]).fehler == "unbekannte_figur"
    assert stueck.setze_besetzung(conn, 1, szene=1, namen=["Anna"], zusatz="il pubblico").ok


def test_setze_rahmen_markiert_kopf(conn):
    repo.setze_arbeitsstand(conn, 1, "stage_kopf", "SETUP: Sala prove")
    stueck.setze_rahmen(conn, 1, rahmen="Sala prove")
    stueck.setze_rahmen(conn, 1, rahmen="Sala riunioni")
    assert [v["ansicht"] for v in repo.offene_veraltet(conn, 1)] == ["kopf"]


def test_ergebnis_ist_json_tauglich(conn):
    _szene(conn)
    json.dumps(stueck.setze_ort(conn, 1, szene=1, ort="x").als_dict())
```

- [ ] **Step 2: Rot**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_ort_besetzung.py`
Expected: FAIL `ModuleNotFoundError: interview_theater.stueck`

- [ ] **Step 3: Implementieren** (`interview_theater/stueck.py`, Teil A; Teil B/C folgen in Task 5/6 im selben Modul)

```python
"""Das Stueckmodell: die EINE Mutations-Schnittstelle (Karte t_fd88600b,
Birk 10.10.2026, Kernkarte t_5a439d0d).

Jede Tatsache ueber ein Stueck steht an genau einer Stelle; Karte,
Script-Kopf, PDF, Werkbank und Prompt sind Ansichten
(``stueck_sicht.karte_ansicht``). Geaendert wird NUR hier:

* in jeder Phase -- Phasen bestimmen Fokus und Vorschlag, nie ein Verbot;
* Strukturfelder ziehen deterministisch nach (es gibt nur eine Stelle);
* Prosa (Stage Script, Kopf) wird NIE still umgeschrieben -- sie wird als
  ``veraltet`` vermerkt, und die Gruppe bekommt "Szene N passt nicht mehr
  zu ... -- neu schreiben? Ja/Nein" (``knoepfe.szenen.biete_veraltete``);
* die deterministischen Pruefungen (Busy-Gate, Kartentreue, [OPEN]-
  Reinigung, Zitat nur aus geprueftem Bestand, Diff) laufen HIER.

**Werkzeug-Zuschnitt** (B-vs-C bleibt offen, Folie 7): jede oeffentliche
Funktion nimmt ``(conn, chat_id, *, <JSON-Werte>)`` und gibt ``Ergebnis``
zurueck -- kein ``tg``/``klm``/``e``, kein Senden, kein Modellaufruf. Damit
ist sie 1:1 als Werkzeug eines spaeteren Agenten aufrufbar
(``tests/test_stueck_schnittstelle.py``)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from interview_theater import repo, stueck_sicht

QUELLE_GRUPPE = "gruppe"
QUELLE_SCRIPT = "script"
QUELLE_KARTE_MODELL = "karte_modell"
QUELLE_PLANUNG = "planung"
QUELLE_AGENT = "agent"
#: Der Schreiber selbst -- fuer ihn gilt das Busy-Gate nicht.
INTERNE_QUELLEN = frozenset({QUELLE_SCRIPT, QUELLE_KARTE_MODELL, QUELLE_PLANUNG})

#: Die oeffentlichen Werkzeuge (Reihenfolge = Tool-Liste eines spaeteren Agenten).
WERKZEUGE = (
    "setze_rahmen", "setze_ort", "setze_besetzung", "figur_hinzu", "figur_aus_szene",
    "karte_aendern", "szene_wieder_oeffnen", "reihenfolge_aendern",
    "frage_stellen", "frage_beantworten", "frage_zurueckstellen", "frage_verwerfen",
    "pruefe_szene",
)

_MIN_ERWAEHNUNG = 4


@dataclass(frozen=True)
class Ergebnis:
    ok: bool
    aenderung_id: int | None = None
    diff: tuple[str, ...] = ()
    warnungen: tuple[str, ...] = ()
    veraltet: tuple[int, ...] = ()
    fehler: str | None = None
    frage_id: int | None = None

    def als_dict(self) -> dict:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}


def _nein(fehler: str, *warnungen: str) -> Ergebnis:
    return Ergebnis(ok=False, fehler=fehler, warnungen=tuple(warnungen))


def _beschaeftigt(chat_id: int, quelle: str) -> bool:
    if quelle in INTERNE_QUELLEN:
        return False
    from interview_theater import ueberarbeitung

    return ueberarbeitung.laeuft(chat_id)


def _szene(conn, chat_id: int, nummer: int):
    return next((s for s in repo.hole_szenen(conn, chat_id)
                 if s["nummer"] == nummer and not s["entfernt_am"]), None)


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _erwaehnt(text, wert) -> bool:
    w = stueck_sicht.normalisiert(wert)
    return len(w) >= _MIN_ERWAEHNUNG and w in stueck_sicht.normalisiert(text)


def _punkt_offen(chat_id: int) -> str:
    from interview_theater import szenenkarte

    return szenenkarte._T(chat_id)._PUNKT_OFFEN


def karte(conn, szene) -> dict | None:
    """Die Karte, wie JEDE Ansicht sie zeigt -- aus den einen Stellen
    abgeleitet. ``szene`` ist eine ``szene``-Zeile."""
    from interview_theater import szenenkarte

    roh = szenenkarte.roh_karte_von(szene)
    if roh is None:
        return None
    fragen = repo.offene_fragen(conn, szene["chat_id"], szene["id"])
    return stueck_sicht.karte_ansicht(
        roh, ort=szene["ort"],
        besetzung=[(b["name"], b["rolle"]) for b in repo.besetzung(conn, szene["id"])],
        zusatz=szene["wer_zusatz"] if "wer_zusatz" in szene.keys() else None,
        fragen_offen=[f["text"] for f in fragen if f["status"] == "offen"],
        fragen_vertagt=[f["text"] for f in fragen if f["status"] == "vertagt"],
        punkt_offen=_punkt_offen(szene["chat_id"]),
    )


def _protokoll(conn, chat_id: int, art: str, ziel: dict, vorher, nachher, quelle: str) -> int:
    return repo.merke_stueck_aenderung(conn, chat_id, art, ziel, vorher, nachher, quelle)


def _markiere_script(conn, chat_id: int, szene, grund: str, aenderung_id: int) -> int | None:
    if szene is None or not _gesetzt(szene["volltext"]):
        return None
    return repo.merke_veraltet(conn, chat_id, szene["id"], "script", grund, aenderung_id)


def _markiere_kopf(conn, chat_id: int, grund: str, aenderung_id: int,
                   nur_wenn_erwaehnt: str | None = None) -> int | None:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kopf = (stand["stage_kopf"] if stand is not None else None) or ""
    if not kopf.strip():
        return None
    if nur_wenn_erwaehnt is not None and not _erwaehnt(kopf, nur_wenn_erwaehnt):
        return None
    return repo.merke_veraltet(conn, chat_id, None, "kopf", grund, aenderung_id)


def _ergebnis(aenderung_id, diff=(), veraltet=(), warnungen=(), frage_id=None) -> Ergebnis:
    return Ergebnis(ok=True, aenderung_id=aenderung_id, diff=tuple(diff),
                    veraltet=tuple(v for v in veraltet if v is not None),
                    warnungen=tuple(warnungen), frage_id=frage_id)


def setze_rahmen(conn, chat_id: int, *, rahmen: str, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    stand = repo.hole_arbeitsstand(conn, chat_id)
    alt = (stand["rahmen"] if stand is not None else None) or ""
    neu = " ".join((rahmen or "").split())
    if stueck_sicht.normalisiert(alt) == stueck_sicht.normalisiert(neu):
        return Ergebnis(ok=True)
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", neu or None)
    aid = _protokoll(conn, chat_id, "setze_rahmen", {}, alt, neu, quelle)
    v = _markiere_kopf(conn, chat_id, T._GRUND_RAHMEN, aid)
    return _ergebnis(aid, [f"rahmen: {alt or '(none)'} -> {neu or '(none)'}"], [v])


def setze_ort(conn, chat_id: int, *, szene: int, ort: str | None,
              quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    alt = zeile["ort"] or ""
    neu = " ".join((ort or "").split())
    if stueck_sicht.normalisiert(alt) == stueck_sicht.normalisiert(neu):
        return Ergebnis(ok=True)
    repo.setze_szenenort(conn, zeile["id"], neu or None)
    aid = _protokoll(conn, chat_id, "setze_ort", {"szene": szene}, alt, neu, quelle)
    grund = T._GRUND_ORT.format(neu=neu or "—")
    veraltet = []
    for s in repo.hole_szenen(conn, chat_id):
        if s["entfernt_am"] or s["nummer"] is None:
            continue
        if s["id"] == zeile["id"]:
            if quelle != QUELLE_SCRIPT:
                veraltet.append(_markiere_script(conn, chat_id, s, grund, aid))
        elif alt and _erwaehnt(s["volltext"], alt):
            veraltet.append(_markiere_script(conn, chat_id, s, grund, aid))
    if alt:
        veraltet.append(_markiere_kopf(conn, chat_id, grund, aid, nur_wenn_erwaehnt=alt))
    return _ergebnis(aid, [f"ort: {alt or '(none)'} -> {neu or '(none)'}"], veraltet)


def _figuren_index(conn, chat_id: int) -> dict[str, int]:
    return {stueck_sicht.normalisiert(f["name"]): f["id"] for f in repo.figuren(conn, chat_id)}


def _schreibe_besetzung(conn, chat_id: int, zeile, eintraege, zusatz, art: str,
                        ziel: dict, quelle: str, grund: str,
                        kopf_auch: bool = False) -> Ergebnis:
    alt = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    alt_zusatz = zeile["wer_zusatz"]
    if alt == list(eintraege) and (alt_zusatz or None) == (zusatz or None):
        return Ergebnis(ok=True)
    alt_text = stueck_sicht.wer_text(
        [(b["name"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])], alt_zusatz)
    repo.setze_besetzung(conn, chat_id, zeile["id"], list(eintraege), zusatz or None)
    neu_text = stueck_sicht.wer_text(
        [(b["name"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])], zusatz)
    aid = _protokoll(conn, chat_id, art, ziel, alt_text, neu_text, quelle)
    veraltet = []
    if quelle != QUELLE_SCRIPT:
        veraltet.append(_markiere_script(conn, chat_id, zeile, grund, aid))
    if kopf_auch:
        veraltet.append(_markiere_kopf(conn, chat_id, grund, aid))
    return _ergebnis(aid, [f"wer: {alt_text or '(none)'} -> {neu_text or '(none)'}"], veraltet)


def setze_besetzung(conn, chat_id: int, *, szene: int, namen: list[str],
                    zusatz: str | None = None, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    index = _figuren_index(conn, chat_id)
    rollen = {b["figur_id"]: b["rolle"] for b in repo.besetzung(conn, zeile["id"])}
    eintraege = []
    for name in namen:
        figur_id = index.get(stueck_sicht.normalisiert(name))
        if figur_id is None:
            return _nein("unbekannte_figur", T._WARNUNG_UNBEKANNTE_FIGUR.format(name=name))
        if figur_id not in dict(eintraege):
            eintraege.append((figur_id, rollen.get(figur_id)))
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zusatz, "setze_besetzung",
                               {"szene": szene}, quelle,
                               T._GRUND_BESETZUNG.format(wer=", ".join(namen)))


def figur_hinzu(conn, chat_id: int, *, name: str, szene: int | None = None,
                rolle: str | None = None, beschreibung: str | None = None,
                quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    name = " ".join((name or "").split())
    if not name:
        return _nein("ungueltig")
    zeile = None
    if szene is not None:
        zeile = _szene(conn, chat_id, szene)
        if zeile is None:
            return _nein("unbekannte_szene")
    figur = repo.hole_figur(conn, chat_id, name)
    neu_angelegt = figur is None
    if neu_angelegt:
        repo.setze_figur(conn, chat_id, name, beschreibung or "")
        figur = repo.hole_figur(conn, chat_id, name)
    elif beschreibung and not _gesetzt(figur["beschreibung"]):
        repo.setze_figur_feld(conn, figur["id"], "beschreibung", beschreibung)
    grund = T._GRUND_FIGUR_NEU.format(name=figur["name"])
    if zeile is None:
        if not neu_angelegt:
            return Ergebnis(ok=True)
        aid = _protokoll(conn, chat_id, "figur_hinzu", {"name": name}, None, figur["name"], quelle)
        return _ergebnis(aid, [f"figur: + {figur['name']}"], [_markiere_kopf(conn, chat_id, grund, aid)])
    eintraege = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    vorhanden = dict(eintraege)
    if figur["id"] in vorhanden:
        if rolle is None or vorhanden[figur["id"]] == rolle:
            return Ergebnis(ok=True)
        eintraege = [(f, rolle if f == figur["id"] else r) for f, r in eintraege]
    else:
        eintraege.append((figur["id"], rolle))
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zeile["wer_zusatz"],
                               "figur_hinzu", {"name": name, "szene": szene}, quelle, grund,
                               kopf_auch=neu_angelegt)


def figur_aus_szene(conn, chat_id: int, *, name: str, szene: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    figur = repo.hole_figur(conn, chat_id, name)
    if figur is None:
        return _nein("unbekannte_figur", T._WARNUNG_UNBEKANNTE_FIGUR.format(name=name))
    eintraege = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    if figur["id"] not in dict(eintraege):
        return Ergebnis(ok=True)
    eintraege = [(f, r) for f, r in eintraege if f != figur["id"]]
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zeile["wer_zusatz"],
                               "figur_aus_szene", {"name": name, "szene": szene}, quelle,
                               T._GRUND_FIGUR_WEG.format(name=figur["name"]))


# --- Texte -----------------------------------------------------------------

_WARNUNG_BESCHAEFTIGT = "Gerade wird noch geschrieben -- gleich nochmal."
_WARNUNG_UNBEKANNTE_FIGUR = "{name} ist noch keine Figur des Stücks."
_GRUND_RAHMEN = "neuer Rahmen"
_GRUND_ORT = "neuer Ort ({neu})"
_GRUND_BESETZUNG = "neue Besetzung ({wer})"
_GRUND_FIGUR_NEU = "neue Figur {name}"
_GRUND_FIGUR_WEG = "{name} spielt nicht mehr mit"

from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
```

Eine Übergangsregel bis Task 9: `szenenkarte.roh_karte_von` gibt es noch nicht. In diesem Task bekommt `szenenkarte.py` deshalb den Alias `roh_karte_von = karte_von` (eine Zeile unter `karte_von`). Task 9 benennt um.

`sprachen/en/texte.toml`, neuer Abschnitt:

```toml
[stueck]
_WARNUNG_BESCHAEFTIGT = "Still writing -- try again in a moment."
_WARNUNG_UNBEKANNTE_FIGUR = "{name} is not a character of the piece yet."
_GRUND_RAHMEN = "new setting"
_GRUND_ORT = "new place ({neu})"
_GRUND_BESETZUNG = "new cast ({wer})"
_GRUND_FIGUR_NEU = "new character {name}"
_GRUND_FIGUR_WEG = "{name} is no longer in it"
```

`sprachen/it/texte.toml`:

```toml
[stueck]
_WARNUNG_BESCHAEFTIGT = "Sto ancora scrivendo -- riprovate tra un attimo."
_WARNUNG_UNBEKANNTE_FIGUR = "{name} non è ancora un personaggio dello spettacolo."
_GRUND_RAHMEN = "nuova cornice"
_GRUND_ORT = "nuovo luogo ({neu})"
_GRUND_BESETZUNG = "nuovo cast ({wer})"
_GRUND_FIGUR_NEU = "nuovo personaggio {name}"
_GRUND_FIGUR_WEG = "{name} non è più in scena"
```

**Achtung Sprache:** `T` ist hier die profilweite Sprache. Für die `_GRUND_*`-Texte, die die Gruppe im Angebot sieht, nimmt Task 14 `_T(chat_id)` (IT ab Phase 6 für gelistete Chats), nach demselben Muster wie `szenenkarte._T`. In Task 4 reicht `T`.

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_ort_besetzung.py tests/test_sprache_texte.py`
Expected: alle passed (`test_keine_unuebersetzte_konstante[stueck]` grün dank der TOML-Einträge)

- [ ] **Step 5: Commit**

```bash
git add interview_theater/stueck.py interview_theater/szenenkarte.py interview_theater/sprachen tests/stueck_hilfe.py tests/test_stueck_ort_besetzung.py
git commit -m "stueckmodell: Mutations-Schnittstelle Teil A (Ort, Rahmen, Besetzung, Veraltet, Busy-Gate)"
```

---

### Task 5: `stueck.py` Teil B — `karte_aendern` (mit Kartentreue, [OPEN]-Reinigung, Zitat aus Bestand), `szene_wieder_oeffnen`, `reihenfolge_aendern`

**Files:**
- Modify: `interview_theater/stueck.py`, `interview_theater/sprachen/{en,it}/texte.toml`
- Test: `tests/test_stueck_karte.py`

**Interfaces (Produces):**

```python
def karte_aendern(conn, chat_id: int, *, szene: int, worum: str | None = None,
                  typ: str | None = None, modus: str | None = None,
                  punkte: list[str] | None = None, punkte_hinzu: list[str] | None = None,
                  punkte_weg: list[str] | None = None, zitate: list[int] | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis
def szene_wieder_oeffnen(conn, chat_id: int, *, szene: int, ebene: str = "karte",
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis   # ebene: "karte" | "script"
def reihenfolge_aendern(conn, chat_id: int, *, folge: list[int],
                        quelle: str = QUELLE_GRUPPE) -> Ergebnis   # folge = heutige Nummern in neuer Reihenfolge
```

Validierung (Problem 5):
- `typ` muss in `szenenkarte.TYPEN` liegen, `modus` in `MODI`; `modus` gilt nur bei `typ == "moment"`, sonst `"none"`. Andernfalls `fehler="ungueltig"`.
- `punkte` werden gekappt (`szenenkarte._kappe`, höchstens `PUNKTE_MAX`).
- Ein Punkt, der `stueck_sicht.OFFEN_PUNKT` trifft, wird **kein** Kartenpunkt, sondern eine offene Frage mit Status `vertagt`. Das ist die Endfassungs-Reinigung an der Schnittstelle.
- `zitate` sind 1-basierte Nummern in `szenenkern._kandidaten(conn, chat_id, szene)`. Gespeichert wird der Wortlaut aus der DB; eine Nummer außerhalb ergibt `fehler="ungueltig"`. Das ist die Zitatverifikation: nur geprüfter Bestand, nie freier Text.
- **Kartentreue:** Hat die Szene `volltext`, laufen `kartentreue.widersprueche(neue_karte, volltext)` und `kartentreue.fehlende_stichworte(neue_karte, volltext)`. Jeder Befund geht in den Veraltet-Grund und in `warnungen`.
- `diff` = `szenenkarte.diff_karten(alt_ansicht, neu_ansicht)`.
- Die Abnahme bleibt (`repo.aktualisiere_szenenkarte`). Der Verlauf bekommt `ausloeser="aenderung"`, die Notiz ist die Diff-Zeile.
- `reihenfolge_aendern`: `folge` muss eine Permutation der aktuellen Nummern sein, sonst `fehler="ungueltig"`. Jede Szene mit `volltext`, deren Nummer sich ändert, wird veraltet (der Kopf „SCENE N" stimmt nicht mehr).
- `szene_wieder_oeffnen("karte")` setzt `karte_bestaetigt_am` auf NULL, `("script")` setzt `fertig_am` auf NULL (`repo.setze_szene_fertig(..., False)`). Beides läuft in jeder Phase und ohne Veraltet-Vermerk.

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_karte.py
import json

from interview_theater import phasen, repo, stueck


def _szene(conn, nummer=1, volltext=None, **karte):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    k = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}
    k.update(karte)
    repo.setze_szenenkarte(conn, sid, json.dumps(k))
    repo.setze_szenenkarte_bestaetigt(conn, sid)
    if volltext:
        repo.setze_stagescript(conn, sid, volltext, None)
    return sid


def test_karte_aendern_in_phase_7_laesst_abnahme_stehen(conn):
    phasen.setze(conn, 1, 7, "test")
    sid = _szene(conn)
    e = stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=["Tutti si alzano"])
    assert e.ok and "punkte" in " ".join(e.diff)
    s = repo.hole_szene(conn, sid)
    assert s["karte_bestaetigt_am"]
    assert stueck.karte(conn, s)["punkte"] == ["p", "Tutti si alzano"]


def test_open_punkt_wird_offene_frage(conn):
    sid = _szene(conn)
    stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=["[OPEN] Wo steht Giona?"])
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert k["punkte"] == ["p", "[OPEN] Wo steht Giona?"]   # Ansicht
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert roh["punkte"] == ["p"]                            # nicht im JSON
    [f] = repo.offene_fragen(conn, 1, sid)
    assert (f["text"], f["status"]) == ("Wo steht Giona?", "vertagt")


def test_kartentreue_markiert_mit_befund(conn):
    sid = _szene(conn, volltext="ANNA: Saresti l'ultimo.")
    e = stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=[
        "✔ No: Arlecchino gli dice solo di sedersi, senza dire \"saresti l'ultimo\""])
    [v] = repo.offene_veraltet(conn, 1)
    assert v["szene_id"] == sid and "saresti l'ultimo" in v["grund"].lower()
    assert e.warnungen


def test_ungueltiger_typ(conn):
    _szene(conn)
    assert stueck.karte_aendern(conn, 1, szene=1, typ="oper").fehler == "ungueltig"


def test_zitat_nur_aus_bestand(conn):
    _szene(conn)
    assert stueck.karte_aendern(conn, 1, szene=1, zitate=[99]).fehler == "ungueltig"


def test_keine_karte(conn):
    repo.stelle_szene_sicher(conn, 1, 1)
    assert stueck.karte_aendern(conn, 1, szene=1, worum="x").fehler == "keine_karte"


def test_wieder_oeffnen(conn):
    sid = _szene(conn, volltext="T")
    repo.setze_szene_fertig(conn, sid, True)
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="script").ok
    assert not repo.hole_szene(conn, sid)["fertig_am"]
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="karte").ok
    assert not repo.hole_szene(conn, sid)["karte_bestaetigt_am"]
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="x").fehler == "ungueltig"


def test_reihenfolge(conn):
    a, b, c = (_szene(conn, n, volltext=f"SCENE {n}") for n in (1, 2, 3))
    e = stueck.reihenfolge_aendern(conn, 1, folge=[3, 1, 2])
    assert e.ok
    assert [repo.hole_szene(conn, i)["nummer"] for i in (a, b, c)] == [2, 3, 1]
    assert {v["szene_id"] for v in repo.offene_veraltet(conn, 1)} == {a, b, c}
    assert stueck.reihenfolge_aendern(conn, 1, folge=[1, 1, 2]).fehler == "ungueltig"
```

- [ ] **Step 2: Rot**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_karte.py`
Expected: FAIL `AttributeError: module 'interview_theater.stueck' has no attribute 'karte_aendern'`

- [ ] **Step 3: Implementieren** (in `stueck.py` vor dem Textblock)

```python
def _ansicht_von(conn, chat_id: int, nummer: int) -> dict | None:
    zeile = _szene(conn, chat_id, nummer)
    return karte(conn, zeile) if zeile is not None else None


def karte_aendern(conn, chat_id: int, *, szene: int, worum: str | None = None,
                  typ: str | None = None, modus: str | None = None,
                  punkte: list[str] | None = None, punkte_hinzu: list[str] | None = None,
                  punkte_weg: list[str] | None = None, zitate: list[int] | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    from interview_theater import kartentreue, szenenkarte, szenenkern

    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    roh = szenenkarte.roh_karte_von(zeile)
    if roh is None:
        return _nein("keine_karte")
    neu = stueck_sicht.roh_ohne_struktur(roh)
    if typ is not None:
        if typ not in szenenkarte.TYPEN:
            return _nein("ungueltig")
        neu["typ"] = typ
    if modus is not None:
        if modus not in szenenkarte.MODI:
            return _nein("ungueltig")
        neu["modus"] = modus
    if neu.get("typ") != "moment":
        neu["modus"] = "none"
    if worum is not None:
        neu["worum"] = szenenkarte._kappe(worum)
    liste = list(neu.get("punkte") or []) if punkte is None else list(punkte)
    liste = [p for p in liste if p not in set(punkte_weg or [])] + list(punkte_hinzu or [])
    fragen_neu = []
    sauber = []
    for p in liste:
        treffer = stueck_sicht.OFFEN_PUNKT.match(p or "")
        if treffer:
            fragen_neu.append(treffer.group(1))
        elif str(p).strip():
            sauber.append(szenenkarte._kappe(p))
    neu["punkte"] = sauber[:szenenkarte.PUNKTE_MAX]
    if zitate is not None:
        kandidaten = szenenkern._kandidaten(conn, chat_id, zeile)
        if any(not (1 <= int(n) <= len(kandidaten)) for n in zitate):
            return _nein("ungueltig")
        neu["zitate"] = [{"zitat": kandidaten[int(n) - 1][0], "interview": kandidaten[int(n) - 1][1]}
                         for n in zitate][:szenenkarte.ZITATE_MAX]
    alt_ansicht = karte(conn, zeile)
    if neu == stueck_sicht.roh_ohne_struktur(roh) and not fragen_neu:
        return Ergebnis(ok=True)
    diff = None
    if neu != stueck_sicht.roh_ohne_struktur(roh):
        repo.aktualisiere_szenenkarte(conn, chat_id, zeile["id"],
                                      json.dumps(neu, ensure_ascii=False),
                                      szenenkarte.AUSLOESER_AENDERUNG, None)
    for text in fragen_neu:
        if not _frage_bekannt(conn, chat_id, zeile["id"], text):
            repo.lege_offene_frage_an(conn, chat_id, zeile["id"], text, quelle, status="vertagt")
    neu_ansicht = karte(conn, repo.hole_szene(conn, zeile["id"]))
    diff = szenenkarte.diff_karten(alt_ansicht or {}, neu_ansicht or {})
    aid = _protokoll(conn, chat_id, "karte_aendern", {"szene": szene},
                     alt_ansicht, neu_ansicht, quelle)
    befunde: list[str] = []
    if _gesetzt(zeile["volltext"]):
        befunde = (kartentreue.widersprueche(neu_ansicht, zeile["volltext"])
                   + [T._BEFUND_FEHLT.format(stichwort=s)
                      for s in kartentreue.fehlende_stichworte(neu_ansicht, zeile["volltext"])])
    grund = T._GRUND_KARTE.format(felder=", ".join(d.split(":")[0] for d in diff) or "punkte")
    if befunde:
        grund += " -- " + "; ".join(befunde)
    v = _markiere_script(conn, chat_id, zeile, grund, aid) if quelle != QUELLE_SCRIPT else None
    return _ergebnis(aid, diff, [v], warnungen=befunde)


def szene_wieder_oeffnen(conn, chat_id: int, *, szene: int, ebene: str = "karte",
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if ebene not in ("karte", "script"):
        return _nein("ungueltig")
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    if ebene == "karte":
        if not _gesetzt(zeile["karte_bestaetigt_am"]):
            return Ergebnis(ok=True)
        repo.setze_szenenkarte_offen(conn, zeile["id"])
    else:
        if not _gesetzt(zeile["fertig_am"]):
            return Ergebnis(ok=True)
        repo.setze_szene_fertig(conn, zeile["id"], False)
    aid = _protokoll(conn, chat_id, "szene_wieder_oeffnen", {"szene": szene, "ebene": ebene},
                     "abgenommen", "offen", quelle)
    return _ergebnis(aid, [f"{ebene}: abgenommen -> offen"])


def reihenfolge_aendern(conn, chat_id: int, *, folge: list[int],
                        quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    szenen = sorted((s for s in repo.hole_szenen(conn, chat_id)
                     if s["nummer"] is not None and not s["entfernt_am"]),
                    key=lambda s: s["nummer"])
    je_nummer = {s["nummer"]: s for s in szenen}
    if sorted(folge) != sorted(je_nummer) or len(set(folge)) != len(folge):
        return _nein("ungueltig")
    if list(folge) == [s["nummer"] for s in szenen]:
        return Ergebnis(ok=True)
    repo.nummeriere_szenen(conn, chat_id, [je_nummer[n]["id"] for n in folge])
    aid = _protokoll(conn, chat_id, "reihenfolge_aendern", {"folge": list(folge)},
                     [s["nummer"] for s in szenen], list(folge), quelle)
    veraltet = []
    for neue_nummer, alte_nummer in enumerate(folge, start=1):
        if neue_nummer != alte_nummer:
            veraltet.append(_markiere_script(conn, chat_id, je_nummer[alte_nummer],
                                             T._GRUND_REIHENFOLGE.format(nummer=neue_nummer), aid))
    return _ergebnis(aid, [f"reihenfolge: {[s['nummer'] for s in szenen]} -> {list(folge)}"], veraltet)
```

`_frage_bekannt` kommt in Task 6; bis dahin als Hilfsfunktion in diesem Task:

```python
def _frage_bekannt(conn, chat_id: int, szene_id: int | None, text: str) -> int | None:
    """id einer Frage derselben Szene mit demselben (normalisierten) Text --
    egal welcher Status: eine beantwortete Frage wird nie wieder geoeffnet
    (Beleg 6, Kernkarte: 21 im Chat beantwortete Fragen blieben [OPEN])."""
    ziel = stueck_sicht.normalisiert(text)
    return next((f["id"] for f in repo.fragen_der_szene(conn, chat_id, szene_id)
                 if stueck_sicht.normalisiert(f["text"]) == ziel), None)
```

Texte (Python-Konstante deutsch, plus TOML en/it im Abschnitt `[stueck]`):

```python
_GRUND_KARTE = "geänderte Karte ({felder})"
_GRUND_REIHENFOLGE = "neue Reihenfolge (jetzt Szene {nummer})"
_BEFUND_FEHLT = "Pflichtpunkt fehlt im Text: {stichwort}"
```

```toml
# en
_GRUND_KARTE = "changed card ({felder})"
_GRUND_REIHENFOLGE = "new order (now scene {nummer})"
_BEFUND_FEHLT = "mandatory point missing in the text: {stichwort}"
# it
_GRUND_KARTE = "scheda modificata ({felder})"
_GRUND_REIHENFOLGE = "nuovo ordine (ora scena {nummer})"
_BEFUND_FEHLT = "punto obbligatorio assente nel testo: {stichwort}"
```

Der Kartentreue-Test erwartet, dass `kartentreue.widersprueche` die Negation „senza dire" erkennt (`kartentreue.py:47` `_VERNEINUNG_MARKER`) und den Text in Anführungszeichen als ausgeschlossene Wendung liest. Erkennt die heutige Funktion diese Schreibweise nicht, wird der **Testtext** an ein Muster angepasst, das `tests/test_kartentreue.py` schon nachweist; die Kartentreue selbst bleibt unverändert.

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_karte.py tests/test_stueck_ort_besetzung.py tests/test_sprache_texte.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/stueck.py interview_theater/sprachen tests/test_stueck_karte.py
git commit -m "stueckmodell: karte_aendern (Kartentreue, [OPEN]-Reinigung, Zitat aus Bestand), wieder oeffnen, Reihenfolge"
```

---

### Task 6: `stueck.py` Teil C — offene Fragen, `karte_aus_modell`, `pruefe_szene`, Schnittstellen-Test

**Files:**
- Modify: `interview_theater/stueck.py`, `interview_theater/sprachen/{en,it}/texte.toml`
- Test: `tests/test_stueck_fragen.py`, `tests/test_stueck_schnittstelle.py`

**Interfaces (Produces):**

```python
def frage_stellen(conn, chat_id: int, *, frage: str, szene: int | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis           # frage_id gesetzt
def frage_beantworten(conn, chat_id: int, *, frage_id: int, antwort: str,
                      quelle: str = QUELLE_GRUPPE) -> Ergebnis
def frage_zurueckstellen(conn, chat_id: int, *, frage_id: int,
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis     # -> vertagt ([OPEN]-Punkt)
def frage_verwerfen(conn, chat_id: int, *, frage_id: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis          # -> uebersprungen
def pruefe_szene(conn, chat_id: int, *, szene: int,
                 quelle: str = QUELLE_GRUPPE) -> Ergebnis            # nur Kartentreue, keine Mutation an Fakten
def karte_aus_modell(conn, chat_id: int, *, szene: int, karte: dict, ausloeser: str,
                     notiz: str | None = None) -> Ergebnis           # intern (szenenkarte.erzeuge)
```

Regeln:
- **`frage_stellen` dedupliziert** gegen alle Fragen derselben Szene, auch beantwortete. Eine schon beantwortete Frage wird nicht wieder geöffnet: `ok=True`, `frage_id` = alte id, Warnung `_WARNUNG_SCHON_BEANTWORTET`.
- **`frage_beantworten` schließt sofort** (Problem 4). Unbekannte id oder eine id eines anderen Chats ergibt `fehler="unbekannte_frage"`. Hat die Szene `volltext` und war die Frage `vertagt` oder `offen`, wird das Script veraltet („beantwortete Frage …").
- **`karte_aus_modell`** zerlegt die Modellkarte:
  - `ort` → `setze_ort(quelle=karte_modell)`, nur wenn nicht leer.
  - `wer` → `ordne_besetzung`. Bekannte Figuren werden **hinzugefügt oder bekommen ihre Rolle**, nie still entfernt. Unbekannte Stücke werden `wer_zusatz`.
  - `fragen` → `frage_stellen` je Frage.
  - `[OPEN]`-Punkte → vertagte Fragen.
  - Das JSON wird ohne Struktur geschrieben: `repo.setze_szenenkarte` (nimmt die Abnahme zurück, wie heute) + `repo.merke_karte_verlauf` mit der **abgeleiteten** Ansicht als Schnappschuss. So bleibt `verfeinerungs_zeilen` (Diff über ort/wer) lesbar.
- **`pruefe_szene`** prüft Kartentreue gegen den gespeicherten Text und vermerkt einen Befund als veraltet. Das ist die Validierung ohne Faktenänderung, für den WIDERSPRUCH-Fall aus `p7audit.json`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_fragen.py
import json

from interview_theater import repo, stueck
from tests.stueck_hilfe import lege_karte_an


def test_frage_beantworten_schliesst_im_modell(conn):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == ["Wo steht Giona?"]
    e = stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="im Loch")
    assert e.ok
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == []


def test_beantwortete_frage_kommt_nie_wieder(conn):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="im Loch")
    e = stueck.frage_stellen(conn, 1, szene=1, frage="wo steht giona?")
    assert e.ok and e.frage_id == f["id"] and e.warnungen
    assert repo.offene_fragen(conn, 1, sid) == []


def test_zurueckstellen_wird_open_punkt_und_sperrt_nicht(conn):
    sid = lege_karte_an(conn, fragen=["Musik?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_zurueckstellen(conn, 1, frage_id=f["id"])
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert k["fragen"] == [] and "[OPEN] Musik?" in k["punkte"]


def test_verwerfen(conn):
    sid = lege_karte_an(conn, fragen=["Unpassend?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_verwerfen(conn, 1, frage_id=f["id"])
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["punkte"] == ["p"]


def test_fremde_frage(conn):
    assert stueck.frage_beantworten(conn, 1, frage_id=999, antwort="x").fehler == "unbekannte_frage"


def test_karte_aus_modell_trennt_struktur_vom_json(conn):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, ort="Bar", wer="Anna (Arlecchino), tutto il pubblico",
                        fragen=["Wann?"], punkte=["p", "[OPEN] Licht?"])
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert not {"ort", "wer", "fragen"} & set(roh) and roh["punkte"] == ["p"]
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert (k["ort"], k["wer"], k["fragen"]) == ("Bar", "Anna (Arlecchino), tutto il pubblico", ["Wann?"])
    assert "[OPEN] Licht?" in k["punkte"]
    assert json.loads(repo.karte_verlauf(conn, 1, sid)[-1]["karte_json"])["ort"] == "Bar"


def test_karte_aus_modell_entfernt_nie_still(conn):
    for n in ("Anna", "Pietro"):
        repo.setze_figur(conn, 1, n, "")
    sid = lege_karte_an(conn, wer="Anna, Pietro")
    lege_karte_an(conn, wer="Anna")
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Anna", "Pietro"]


def test_pruefe_szene_vermerkt_widerspruch(conn):
    sid = lege_karte_an(conn, punkte=["✔ No: senza dire \"saresti l'ultimo\""])
    repo.setze_stagescript(conn, sid, "ANNA: Saresti l'ultimo.", None)
    e = stueck.pruefe_szene(conn, 1, szene=1)
    assert e.ok and e.veraltet and e.warnungen
```

```python
# tests/test_stueck_schnittstelle.py
"""Werkzeug-Zuschnitt (Karte t_fd88600b): jede Mutation ist 1:1 als Werkzeug
eines spaeteren Agenten aufrufbar -- (conn, chat_id, *, JSON-Werte) ->
Ergebnis, ohne tg/klm/e. Rot, sobald jemand eine Oberflaechen-Abhaengigkeit
in die Schnittstelle zieht."""

import inspect
import typing

from interview_theater import stueck

_JSON = {int, str, bool, type(None), list, dict, float}


def _json_typ(annot) -> bool:
    if annot in _JSON:
        return True
    herkunft = typing.get_origin(annot)
    if herkunft in (list, dict):
        return all(_json_typ(a) for a in typing.get_args(annot))
    if herkunft in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        return all(_json_typ(a) for a in typing.get_args(annot))
    return False


def test_werkzeuge_sind_schlank():
    for name in stueck.WERKZEUGE:
        f = getattr(stueck, name)
        sig = inspect.signature(f, eval_str=True)
        params = list(sig.parameters.values())
        assert [p.name for p in params[:2]] == ["conn", "chat_id"], name
        for p in params[2:]:
            assert p.kind is inspect.Parameter.KEYWORD_ONLY, (name, p.name)
            assert p.name not in {"tg", "klm", "e"}, (name, p.name)
            assert _json_typ(p.annotation), (name, p.name, p.annotation)
        assert sig.return_annotation is stueck.Ergebnis, name
```

- [ ] **Step 2: Rot**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_fragen.py tests/test_stueck_schnittstelle.py`
Expected: FAIL (`karte_aus_modell` bzw. `frage_stellen` fehlen)

- [ ] **Step 3: Implementieren** (in `stueck.py`)

```python
def _frage_der_gruppe(conn, chat_id: int, frage_id: int):
    f = repo.hole_offene_frage(conn, frage_id)
    return f if f is not None and f["chat_id"] == chat_id else None


def _szene_nach_id(conn, szene_id: int | None):
    return repo.hole_szene(conn, szene_id) if szene_id is not None else None


def frage_stellen(conn, chat_id: int, *, frage: str, szene: int | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    text = " ".join((frage or "").split())
    if not text:
        return _nein("ungueltig")
    szene_id = None
    if szene is not None:
        zeile = _szene(conn, chat_id, szene)
        if zeile is None:
            return _nein("unbekannte_szene")
        szene_id = zeile["id"]
    bekannt = _frage_bekannt(conn, chat_id, szene_id, text)
    if bekannt is not None:
        f = repo.hole_offene_frage(conn, bekannt)
        warn = (T._WARNUNG_SCHON_BEANTWORTET,) if f["status"] in ("beantwortet", "uebersprungen") else ()
        return Ergebnis(ok=True, frage_id=bekannt, warnungen=warn)
    fid = repo.lege_offene_frage_an(conn, chat_id, szene_id, text, quelle)
    aid = _protokoll(conn, chat_id, "frage_stellen", {"szene": szene}, None, text, quelle)
    return _ergebnis(aid, [f"fragen: + {text}"], frage_id=fid)


def _schliesse(conn, chat_id: int, frage_id: int, status: str, antwort: str | None,
               art: str, quelle: str) -> Ergebnis:
    f = _frage_der_gruppe(conn, chat_id, frage_id)
    if f is None:
        return _nein("unbekannte_frage")
    if f["status"] == status and (antwort is None or f["antwort"] == antwort):
        return Ergebnis(ok=True, frage_id=frage_id)
    repo.setze_frage_status(conn, frage_id, status, antwort)
    aid = _protokoll(conn, chat_id, art, {"frage_id": frage_id}, f["status"], status, quelle)
    v = None
    if status == "beantwortet":
        v = _markiere_script(conn, chat_id, _szene_nach_id(conn, f["szene_id"]),
                             T._GRUND_FRAGE.format(frage=f["text"]), aid)
    return _ergebnis(aid, [f"frage: {f['text']} -> {status}"], [v], frage_id=frage_id)


def frage_beantworten(conn, chat_id: int, *, frage_id: int, antwort: str,
                      quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "beantwortet", (antwort or "").strip() or None,
                      "frage_beantworten", quelle)


def frage_zurueckstellen(conn, chat_id: int, *, frage_id: int,
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "vertagt", None, "frage_zurueckstellen", quelle)


def frage_verwerfen(conn, chat_id: int, *, frage_id: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "uebersprungen", None, "frage_verwerfen", quelle)


def pruefe_szene(conn, chat_id: int, *, szene: int, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    from interview_theater import kartentreue

    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    k = karte(conn, zeile)
    if k is None or not _gesetzt(zeile["volltext"]):
        return Ergebnis(ok=True)
    befunde = (kartentreue.widersprueche(k, zeile["volltext"])
               + [T._BEFUND_FEHLT.format(stichwort=s)
                  for s in kartentreue.fehlende_stichworte(k, zeile["volltext"])])
    if not befunde:
        return Ergebnis(ok=True)
    aid = _protokoll(conn, chat_id, "pruefe_szene", {"szene": szene}, None, befunde, quelle)
    v = repo.merke_veraltet(conn, chat_id, zeile["id"], "script", "; ".join(befunde), aid)
    return _ergebnis(aid, veraltet=[v], warnungen=befunde)


def karte_aus_modell(conn, chat_id: int, *, szene: int, karte: dict, ausloeser: str,
                     notiz: str | None = None) -> Ergebnis:
    """Der EINE Weg, auf dem eine vom Modell gebaute Karte (``szenenkarte.
    erzeuge``) ins Stueckmodell kommt: Struktur an ihre Stellen, nur der Rest
    ins JSON. Das Modell darf Figuren hinzufuegen, nie still entfernen."""
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    q = QUELLE_KARTE_MODELL
    if str(karte.get("ort") or "").strip():
        setze_ort(conn, chat_id, szene=szene, ort=karte["ort"], quelle=q)
    if str(karte.get("wer") or "").strip():
        eintraege, rest = stueck_sicht.ordne_besetzung(karte["wer"], _figuren_index(conn, chat_id))
        zeile = _szene(conn, chat_id, szene)
        bisher = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
        rollen = dict(eintraege)
        zusammen = [(f, rollen.get(f) or r) for f, r in bisher] + [
            (f, r) for f, r in eintraege if f not in dict(bisher)]
        _schreibe_besetzung(conn, chat_id, zeile, zusammen, ", ".join(rest) or None,
                            "karte_aus_modell", {"szene": szene}, q,
                            T._GRUND_BESETZUNG.format(wer=karte["wer"]))
    zeile = _szene(conn, chat_id, szene)
    roh = stueck_sicht.roh_ohne_struktur(karte)
    punkte = []
    for p in roh.get("punkte") or []:
        treffer = stueck_sicht.OFFEN_PUNKT.match(p or "")
        if treffer:
            if not _frage_bekannt(conn, chat_id, zeile["id"], treffer.group(1)):
                repo.lege_offene_frage_an(conn, chat_id, zeile["id"], treffer.group(1), q,
                                          status="vertagt")
        else:
            punkte.append(p)
    roh["punkte"] = punkte
    for frage in karte.get("fragen") or []:
        frage_stellen(conn, chat_id, szene=szene, frage=frage, quelle=q)
    repo.setze_szenenkarte(conn, zeile["id"], json.dumps(roh, ensure_ascii=False))
    ansicht = karte_ansicht_von_id(conn, zeile["id"])
    repo.merke_karte_verlauf(conn, chat_id, zeile["id"],
                             json.dumps(ansicht, ensure_ascii=False), ausloeser, notiz)
    aid = _protokoll(conn, chat_id, "karte_aus_modell", {"szene": szene}, None, ansicht, q)
    return _ergebnis(aid)


def karte_ansicht_von_id(conn, szene_id: int) -> dict | None:
    zeile = repo.hole_szene(conn, szene_id)
    return karte(conn, zeile) if zeile is not None else None
```

Texte:

```python
_WARNUNG_SCHON_BEANTWORTET = "Diese Frage ist schon geklärt."
_GRUND_FRAGE = "beantwortete Frage ({frage})"
```

```toml
# en
_WARNUNG_SCHON_BEANTWORTET = "This question is already settled."
_GRUND_FRAGE = "answered question ({frage})"
# it
_WARNUNG_SCHON_BEANTWORTET = "Questa domanda è già chiarita."
_GRUND_FRAGE = "domanda chiarita ({frage})"
```

Die Funktion `karte_ansicht_von_id` steht nicht in `WERKZEUGE`. Sie ist ein Lesehelfer, kein Werkzeug.

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_fragen.py tests/test_stueck_schnittstelle.py tests/test_stueck_karte.py tests/test_stueck_ort_besetzung.py tests/test_sprache_texte.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/stueck.py interview_theater/sprachen tests/test_stueck_fragen.py tests/test_stueck_schnittstelle.py
git commit -m "stueckmodell: offene Fragen schliessen im Modell, karte_aus_modell, pruefe_szene, Werkzeug-Zuschnitt-Test"
```

---

### Task 7: Konfliktbericht-Format (Vorbereitung Migration)

Der Bericht entsteht aus `stueck_aenderung` (Quelle `migration`). Dieser Task legt nur den Leser fest, damit Task 8 und Task 17 ein gemeinsames Format haben.

**Files:**
- Create: `scripts/stueckmodell_migration.py` (zunächst nur `bericht`)
- Test: `tests/test_stueckmodell_skripte.py` (ergänzen)

**Interfaces (Produces):**
- `scripts.stueckmodell_migration.bericht(conn) -> dict`, Form: `{"konflikte": [{"chat_id", "szene", "art", "vorher", "nachher"}], "zaehler": {art: anzahl}}`
- `scripts.stueckmodell_migration.als_markdown(b: dict) -> str`

- [ ] **Step 1: Failing test** (in `tests/test_stueckmodell_skripte.py` anhängen)

```python
def test_bericht_liest_nur_migrationszeilen(conn):
    from scripts import stueckmodell_migration as m
    from interview_theater import repo

    repo.merke_stueck_aenderung(conn, 1, "konflikt_ort", {"szene": 1}, "a", "b", "migration")
    repo.merke_stueck_aenderung(conn, 1, "setze_ort", {"szene": 1}, "b", "c", "gruppe")
    b = m.bericht(conn)
    assert b["zaehler"] == {"konflikt_ort": 1}
    assert b["konflikte"][0]["szene"] == 1
    assert "konflikt_ort" in m.als_markdown(b)
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_skripte.py::test_bericht_liest_nur_migrationszeilen` — Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implementieren**

```python
# scripts/stueckmodell_migration.py
"""Stueckmodell-Migration gegen eine KOPIE (Karte t_fd88600b).

    uv run --extra dev python -m scripts.stueckmodell_migration var/stueckmodell/padua-kopie.db var/stueckmodell/padua-migriert.db

Kopiert die Quelle (``VACUUM INTO``, Quelle read-only), migriert NUR die
Kopie (``db.initialisiere`` -> ``db._migriere_stueckmodell``) und schreibt
den Konfliktbericht nach ``<ziel>.konflikte.md`` / ``.json``."""

import collections
import json
import sys


def bericht(conn) -> dict:
    zeilen = conn.execute(
        "SELECT chat_id, art, ziel, vorher, nachher FROM stueck_aenderung "
        "WHERE quelle = 'migration' ORDER BY chat_id, id").fetchall()
    konflikte = [{"chat_id": z[0], "szene": json.loads(z[2]).get("szene"), "art": z[1],
                  "vorher": json.loads(z[3]) if z[3] else None,
                  "nachher": json.loads(z[4]) if z[4] else None} for z in zeilen]
    return {"konflikte": konflikte,
            "zaehler": dict(collections.Counter(k["art"] for k in konflikte))}


def als_markdown(b: dict) -> str:
    zeilen = ["# Stueckmodell-Migration: Konfliktbericht", "",
              "| art | anzahl |", "|---|---|"]
    zeilen += [f"| {a} | {n} |" for a, n in sorted(b["zaehler"].items())]
    zeilen += ["", "| chat_id | szene | art | vorher | nachher |", "|---|---|---|---|---|"]
    zeilen += [f"| {k['chat_id']} | {k['szene']} | {k['art']} | {k['vorher']} | {k['nachher']} |"
               for k in b["konflikte"]]
    return "\n".join(zeilen) + "\n"


def main() -> None:
    from interview_theater import db
    from scripts import stueckmodell_kopie

    quelle, ziel = sys.argv[1], sys.argv[2]
    stueckmodell_kopie.kopiere(quelle, ziel)
    conn = db.verbinde(ziel)
    db.initialisiere(conn)
    b = bericht(conn)
    with open(ziel + ".konflikte.json", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    with open(ziel + ".konflikte.md", "w", encoding="utf-8") as f:
        f.write(als_markdown(b))
    print(json.dumps(b["zaehler"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
```

(Die SQL-Abfrage steht im Skript, nicht im Paket, wie in `scripts/fuelle_pruef_db.py`. Das Skript öffnet nur die Kopie.)

- [ ] **Step 4: Grün** — gleiches Kommando wie Step 2 — Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/stueckmodell_migration.py tests/test_stueckmodell_skripte.py
git commit -m "stueckmodell: Konfliktbericht-Format der Migration"
```

---

### Task 8: Daten-Migration `db._migriere_stueckmodell` (idempotent, ein Wert je Widerspruch)

**Files:**
- Modify: `interview_theater/db.py` (neue Funktion nach `_migriere_erste_szenenfassung`, Aufruf in `initialisiere` als letzte Zeile)
- Test: `tests/test_stueck_migration.py`

**Interfaces:**
- Consumes: `stueck_sicht.ordne_besetzung`, `stueck_sicht.OFFEN_PUNKT`, `stueck_sicht.normalisiert`, `stueck_sicht.roh_ohne_struktur` (reiner Import; `db` darf ein projektimportfreies Modul laden)
- Produces: `db._migriere_stueckmodell(conn) -> dict[str, int]` (Zähler je `art`)

Regeln (je nicht entfernte Szene mit `karte`, deren JSON einen der Schlüssel `ort`/`wer`/`fragen` oder einen `[OPEN]`-Punkt trägt):
- **Ort:**
  - Ist `karte.ort` gesetzt und `szene.ort` leer → `szene.ort = karte.ort`, art `ort_uebernommen`.
  - Sind beide gesetzt und verschieden (normalisiert) → **`karte.ort` gewinnt**: die Karte ist jünger (P6) und von der Gruppe abgenommen. Art `konflikt_ort`, vorher = `szene.ort`, nachher = `karte.ort`.
- **Wer:**
  - `ordne_besetzung(karte.wer, figuren)` liefert die Einträge aus der Karte.
  - Die neue Besetzung ist die **Vereinigung**: zuerst die Kartenfiguren in Kartenreihenfolge mit Rolle, dann die Werkbank-Figuren, die die Karte nicht nennt. Keine Figur geht verloren.
  - Der Rest der Karte wird `wer_zusatz`.
  - Art `konflikt_wer`, wenn sich die Figurenmengen von Karte und Werkbank unterscheiden.
  - Art `name_ohne_figur` je Reststück, das wie ein einzelner Name aussieht (ein Wort, Großbuchstabe am Anfang). Es wird **keine** Figur angelegt.
- **Fragen:** `karte.fragen` → `offene_frage` Status `offen`, `[OPEN]`-Punkte → Status `vertagt`, beide mit `quelle='migration'`. Art `frage_uebernommen`.
- Das JSON wird ohne `ort`/`wer`/`fragen` und ohne `[OPEN]`-Punkte zurückgeschrieben (`karte_bestaetigt_am` bleibt). `karte_verlauf` bleibt unberührt, es ist Historie.
- Alles läuft in **einer** Transaktion `BEGIN IMMEDIATE`. Drei Bot-Prozesse starten parallel; der zweite wartet (`busy_timeout`) und findet nichts mehr zu tun.

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_migration.py
import json

from interview_theater import db, repo, stueck


def _alt(conn, nummer, karte, ort=None, figuren=()):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    if ort is not None:
        conn.execute("UPDATE szene SET ort = ? WHERE id = ?", (ort, sid))
    conn.execute("UPDATE szene SET karte = ?, karte_bestaetigt_am = 'x' WHERE id = ?",
                 (json.dumps(karte), sid))
    for f in figuren:
        repo.setze_figur(conn, 1, f, "")
        conn.execute("INSERT INTO szene_figur (chat_id, szene_id, figur_id) VALUES (1, ?, ?)",
                     (sid, repo.hole_figur(conn, 1, f)["id"]))
    conn.commit()
    return sid


K = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}


def test_konsistent_bleibt_gleich(conn):
    sid = _alt(conn, 1, dict(K, ort="Bar", wer="Anna", fragen=[]), ort="Bar", figuren=["Anna"])
    db._migriere_stueckmodell(conn)
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert (k["ort"], k["wer"]) == ("Bar", "Anna")
    assert repo.stueck_aenderungen(conn, 1, quelle="migration") == []


def test_widerspruch_ein_wert_und_bericht(conn):
    sid = _alt(conn, 1, dict(K, ort="Sala riunioni", wer="Emma, Giada e tutto il pubblico", fragen=[]),
               ort="meeting room", figuren=["Emma", "Giona"])
    repo.setze_figur(conn, 1, "Giada", "")
    z = db._migriere_stueckmodell(conn)
    s = repo.hole_szene(conn, sid)
    assert s["ort"] == "Sala riunioni"
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Emma", "Giada", "Giona"]
    assert s["wer_zusatz"] == "tutto il pubblico"
    assert z["konflikt_ort"] == 1 and z["konflikt_wer"] == 1
    assert s["karte_bestaetigt_am"] == "x"


def test_name_ohne_figur_wird_berichtet_nicht_angelegt(conn):
    sid = _alt(conn, 1, dict(K, wer="Anna, Chicca", fragen=[]), figuren=["Anna"])
    z = db._migriere_stueckmodell(conn)
    assert z["name_ohne_figur"] == 1
    assert repo.hole_figur(conn, 1, "Chicca") is None
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "Chicca"


def test_fragen_und_open_punkte(conn):
    sid = _alt(conn, 1, dict(K, punkte=["p", "[OPEN] Licht?"], fragen=["Wann?"]))
    db._migriere_stueckmodell(conn)
    assert [(f["text"], f["status"]) for f in repo.offene_fragen(conn, 1, sid)] == [
        ("Wann?", "offen"), ("Licht?", "vertagt")]
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert roh["punkte"] == ["p"] and not {"ort", "wer", "fragen"} & set(roh)


def test_idempotent(conn):
    _alt(conn, 1, dict(K, ort="Bar", wer="", fragen=["Wann?"]))
    db._migriere_stueckmodell(conn)
    vorher = conn.execute("SELECT count(*) FROM offene_frage").fetchone()[0]
    assert db._migriere_stueckmodell(conn) == {}
    assert conn.execute("SELECT count(*) FROM offene_frage").fetchone()[0] == vorher


def test_initialisiere_ruft_die_migration(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "g", "G")
    sid = repo.stelle_szene_sicher(c, 1, 1)
    c.execute("UPDATE szene SET karte = ? WHERE id = ?", (json.dumps(dict(K, ort="Bar")), sid))
    c.commit()
    db.initialisiere(c)
    assert repo.hole_szene(c, sid)["ort"] == "Bar"
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_migration.py` — Expected: FAIL `AttributeError: … _migriere_stueckmodell`

- [ ] **Step 3: Implementieren**

```python
def _migriere_stueckmodell(conn: sqlite3.Connection) -> dict[str, int]:
    """Stueckmodell (Karte t_fd88600b, 10.10.2026): Ort, Wer und offene
    Fragen aus ``szene.karte`` an ihre EINE Stelle (``szene.ort``,
    ``szene_figur``/``szene.wer_zusatz``, ``offene_frage``). Liefert die
    Zaehler je Art; jede Entscheidung steht als ``stueck_aenderung``
    (quelle ``migration``) -- das IST der Konfliktbericht.

    Idempotent ueber die Datenlage (wie ``_migriere_erste_szenenfassung``):
    eine Karte ohne die drei Schluessel und ohne [OPEN]-Punkt ist fertig.
    ``BEGIN IMMEDIATE``: die Bots starten parallel auf derselben Datei.

    Widerspruch -> EIN Wert: beim Ort gewinnt die Karte (juenger, P6,
    abgenommen); bei der Besetzung die Vereinigung (keine Figur geht
    verloren); ein Name ohne Figur wird berichtet, nie angelegt (Birk
    05.09.2026, ``erkenner._figuren_aus_namen``)."""
    from interview_theater import stueck_sicht as sicht

    zaehler: dict[str, int] = {}
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def merke(chat_id, art, szene, vorher, nachher):
        zaehler[art] = zaehler.get(art, 0) + 1
        conn.execute(
            "INSERT INTO stueck_aenderung (chat_id, art, ziel, vorher, nachher, quelle, erstellt_am) "
            "VALUES (?, ?, ?, ?, ?, 'migration', ?)",
            (chat_id, art, json.dumps({"szene": szene}), json.dumps(vorher, ensure_ascii=False),
             json.dumps(nachher, ensure_ascii=False), jetzt))

    conn.execute("BEGIN IMMEDIATE")
    try:
        zeilen = conn.execute(
            "SELECT * FROM szene WHERE entfernt_am IS NULL AND karte IS NOT NULL AND ("
            "karte LIKE '%\"ort\"%' OR karte LIKE '%\"wer\"%' OR karte LIKE '%\"fragen\"%' "
            "OR karte LIKE '%[OPEN%' OR karte LIKE '%[APERTO%' OR karte LIKE '%[OFFEN%')"
        ).fetchall()
        for s in zeilen:
            try:
                karte = json.loads(s["karte"])
            except ValueError:
                continue
            if not isinstance(karte, dict):
                continue
            offene_punkte = [p for p in karte.get("punkte") or [] if sicht.OFFEN_PUNKT.match(str(p))]
            if not (set(sicht.STRUKTUR_SCHLUESSEL) & set(karte)) and not offene_punkte:
                continue
            chat_id, nr = s["chat_id"], s["nummer"]
            k_ort = " ".join(str(karte.get("ort") or "").split())
            s_ort = (s["ort"] or "").strip()
            if k_ort and not s_ort:
                conn.execute("UPDATE szene SET ort = ? WHERE id = ?", (k_ort, s["id"]))
                merke(chat_id, "ort_uebernommen", nr, None, k_ort)
            elif k_ort and sicht.normalisiert(k_ort) != sicht.normalisiert(s_ort):
                conn.execute("UPDATE szene SET ort = ? WHERE id = ?", (k_ort, s["id"]))
                merke(chat_id, "konflikt_ort", nr, s_ort, k_ort)
            wer = str(karte.get("wer") or "").strip()
            if wer:
                figuren = {sicht.normalisiert(f["name"]): f["id"] for f in conn.execute(
                    "SELECT id, name FROM figur WHERE chat_id = ? AND entfernt_am IS NULL", (chat_id,))}
                aus_karte, rest = sicht.ordne_besetzung(wer, figuren)
                bisher = [z["figur_id"] for z in conn.execute(
                    "SELECT figur_id FROM szene_figur WHERE szene_id = ? "
                    "ORDER BY position IS NULL, position, figur_id", (s["id"],))]
                neu = list(aus_karte) + [(f, None) for f in bisher if f not in dict(aus_karte)]
                if set(dict(aus_karte)) != set(bisher):
                    merke(chat_id, "konflikt_wer", nr, sorted(bisher), sorted(dict(neu)))
                for r in rest:
                    if len(r.split()) == 1 and r[:1].isupper():
                        merke(chat_id, "name_ohne_figur", nr, None, r)
                conn.execute("DELETE FROM szene_figur WHERE szene_id = ?", (s["id"],))
                for pos, (fid, rolle) in enumerate(neu, start=1):
                    conn.execute("INSERT OR IGNORE INTO szene_figur "
                                 "(chat_id, szene_id, figur_id, rolle, position) VALUES (?,?,?,?,?)",
                                 (chat_id, s["id"], fid, rolle, pos))
                conn.execute("UPDATE szene SET wer_zusatz = ? WHERE id = ?",
                             (", ".join(rest) or None, s["id"]))
            for text, status in ([(f, "offen") for f in karte.get("fragen") or []]
                                 + [(sicht.OFFEN_PUNKT.match(p).group(1), "vertagt") for p in offene_punkte]):
                conn.execute("INSERT INTO offene_frage (chat_id, szene_id, text, status, quelle, erstellt_am) "
                             "VALUES (?, ?, ?, ?, 'migration', ?)", (chat_id, s["id"], text, status, jetzt))
                merke(chat_id, "frage_uebernommen", nr, None, {"text": text, "status": status})
            roh = sicht.roh_ohne_struktur(karte)
            roh["punkte"] = [p for p in karte.get("punkte") or [] if p not in offene_punkte]
            conn.execute("UPDATE szene SET karte = ? WHERE id = ?",
                         (json.dumps(roh, ensure_ascii=False), s["id"]))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return zaehler
```

In `initialisiere` als letzte Zeile: `_migriere_stueckmodell(conn)`; den Docstring um einen Satz ergänzen. `db.py` importiert heute `re`, `sqlite3` und `datetime, timedelta, timezone` (`db.py:3-5`). `import json` muss dazu.

`test_konsistent_bleibt_gleich` erwartet **keine** Berichtszeile, wenn Karte und Werkbank übereinstimmen. `ort_uebernommen`/`frage_uebernommen` gelten als Überführung, nicht als Konflikt. In diesem Test gibt es keine, weil `fragen=[]` ist und beide Orte gleich sind.

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_migration.py tests/test_db.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/db.py tests/test_stueck_migration.py
git commit -m "stueckmodell: idempotente Datenmigration (Karte gewinnt beim Ort, Vereinigung bei der Besetzung, Bericht in stueck_aenderung)"
```

---

### Task 9: Alle Bot-Leser auf die abgeleitete Karte (`karte_von` → `roh_karte_von` + `stueck.karte`)

**Files:**
- Modify: `interview_theater/szenenkarte.py:110` (`karte_von` → `roh_karte_von`; Alias aus Task 4 entfernen). Leser bei `szenenkarte.py:173, 394, 461, 516, 632, 662, 698, 783, 810, 923, 989`
- Modify: `interview_theater/stagescript.py:87, 132, 151`; `interview_theater/prueflauf.py:390`; `interview_theater/ueberarbeitung.py:675`; `interview_theater/ablauf.py:1633`; `interview_theater/erkenner.py:1331`; `interview_theater/karten_nachzug.py:152`
- Modify: Tests, die `szenenkarte.karte_von` aufrufen (`tests/test_karten_nachzug.py`, `tests/test_szenenkarte.py`, `tests/test_szenenkarte_dialog.py`, `tests/test_figur_festlegung_nachzug.py`, `tests/test_karten_cothinker.py`, `tests/test_stagescript.py`): `szenenkarte.karte_von(x)` → `stueck.karte(conn, x)`
- Test: `tests/test_stueck_einzige_lesestelle.py`

**Interfaces:**
- Consumes: `stueck.karte(conn, szene) -> dict | None`
- Produces: `szenenkarte.roh_karte_von(szene) -> dict | None` (nur `stueck.py`, `web_daten.py` und `db.py`-freie Skripte dürfen es lesen)

Ersetzungsregel je Fundstelle: `szenenkarte.karte_von(X)` bzw. innerhalb von `szenenkarte.py` `karte_von(X)` wird `stueck.karte(conn, X)`, mit lokalem Import `from interview_theater import stueck` in der Funktion (Zyklen-Bauart des Repos). Wo nur der Typ gebraucht wird (`stagescript.py:87`, `ueberarbeitung.py:675`), genügt `roh_karte_von`, denn `typ` ist kein Strukturfeld.

- [ ] **Step 1: Failing test**

```python
# tests/test_stueck_einzige_lesestelle.py
"""Problem 1 (Karte t_fd88600b): das Karten-JSON liest NUR das Stueckmodell
(``stueck.karte`` / ``web_daten`` ueber ``stueck_sicht``). Ein Leser, der
``roh_karte_von`` direkt nimmt, saehe wieder eine zweite Wahrheit."""

import pathlib
import re

ERLAUBT = {"stueck.py", "szenenkarte.py", "web_daten.py", "stagescript.py", "ueberarbeitung.py"}
# stagescript/ueberarbeitung: nur fuer ``typ`` (kein Strukturfeld), siehe Plan Task 9.


def test_niemand_liest_das_rohe_karten_json():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    treffer = []
    for datei in wurzel.rglob("*.py"):
        text = datei.read_text(encoding="utf-8")
        if re.search(r"\bkarte_von\(", text):
            treffer.append(f"{datei.name}: karte_von")
        if "roh_karte_von(" in text and datei.name not in ERLAUBT:
            treffer.append(f"{datei.name}: roh_karte_von")
    assert treffer == []


def test_typ_leser_nutzen_kein_strukturfeld():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    for name in ("stagescript.py", "ueberarbeitung.py"):
        for zeile in (wurzel / name).read_text(encoding="utf-8").splitlines():
            if "roh_karte_von(" in zeile:
                assert not re.search(r"\b(ort|wer|fragen)\b", zeile), zeile
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_einzige_lesestelle.py` — Expected: FAIL mit Liste aller `karte_von`-Fundstellen

- [ ] **Step 3: Umstellen** (je Fundstelle; Beispiele)

`szenenkarte.py:110`:

```python
def roh_karte_von(szene) -> dict | None:
    """Das gespeicherte Karten-JSON OHNE Ableitung -- nur fuer
    ``stueck.karte``/``web_daten`` (Stueckmodell, t_fd88600b). Jede Ansicht
    liest ``stueck.karte(conn, szene)``."""
```

`stagescript.py:151-152`:

```python
    from interview_theater import stueck

    karte = stueck.karte(conn, szene) or {}
    teile.append(T._KOPF_KARTE + "\n" + szenenkarte.karte_text(karte, szene, chat_id))
```

`stagescript.py:132`: `karte = stueck.karte(conn, s)`. `stagescript.py:87` und `ueberarbeitung.py:675`: `szenenkarte.roh_karte_von(s)`. `prueflauf.py:390`, `ablauf.py:1633`, `erkenner.py:1331`, `karten_nachzug.py:152`: `stueck.karte(conn, …)`.

In `szenenkarte.py` ersetzt jede `karte_von(szene)`-Stelle `stueck.karte(conn, szene)`. Die Funktionen haben alle `conn` im Scope; Ausnahme ist `karte_von` selbst.

- [ ] **Step 4: Grün — gezielte Tests der berührten Module**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_einzige_lesestelle.py tests/test_szenenkarte.py tests/test_szenenkarte_dialog.py tests/test_stagescript.py tests/test_prueflauf.py tests/test_karten_cothinker.py tests/test_kontext_stagescript_stand.py tests/test_figur_festlegung_nachzug.py`
Expected: alle passed.

Rot ist hier zulässig, wenn ein Test Ort, Wer oder Fragen **nur** ins Karten-JSON schreibt (`repo.setze_szenenkarte(..., json.dumps({... "ort": ...}))`) und danach eine Ansicht prüft. Solche Tests auf `tests.stueck_hilfe.lege_karte_an(...)` umstellen; die Zusicherungen bleiben unverändert. Weiter geht es erst, wenn alle grün sind. `tests/test_karten_nachzug.py` wird in Task 12 neu gefasst und bleibt bis dahin außen vor.

- [ ] **Step 5: Commit**

```bash
git add interview_theater tests
git commit -m "stueckmodell: alle Bot-Leser auf die abgeleitete Karte (stueck.karte)"
```

---

### Task 10: Web-Leser — abgeleitete Karte in `web_daten`, Wo/Wer in der Padua-Werkbank

**Files:**
- Modify: `interview_theater/web_daten.py:580-611` (`_szene_figuren`/`_szene_figur_ids` `ORDER BY sf.position IS NULL, sf.position, f.id`), `:746-819` (`_szenen`), `:1831-1850` (`szenenkarten`); neue Helfer `_besetzung`, `_fragen`, `_karte_sicht`
- Modify: `interview_theater/web.py:5146-5173` (`_wb_szenen_verdichtet_html`: Zeile „Wo · Wer" je Szene)
- Modify: `interview_theater/sprachen/en/texte.toml`, `…/it/texte.toml` (`[web]` `_TEXT_WB_WO_WER`)
- Test: `tests/test_stueck_web.py`

**Interfaces:**
- Consumes: `stueck_sicht.karte_ansicht`, `szenenkarte.roh_karte_von`, `szenenkarte._T(chat_id)._PUNKT_OFFEN`
- Produces: `web_daten._karte_sicht(conn, zeile) -> dict | None` (dieselbe Ableitung wie `stueck.karte`, über eigenes read-only-SQL); `eintrag["karte"]` und `szenenkarten()[i]["karte"]` sind abgeleitet.

- [ ] **Step 1: Failing test**

```python
# tests/test_stueck_web.py
import pytest

from interview_theater import repo, stueck, web, web_daten, workshop
from tests.stueck_hilfe import lege_karte_an


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_web_und_bot_zeigen_dieselbe_karte(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, ort="Bar", wer="Anna (Arlecchino), il pubblico", fragen=["Wann?"])
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    [s] = daten["szenen"]
    assert s["karte"] == stueck.karte(conn, repo.hole_szene(conn, sid))
    [k] = web_daten.szenenkarten(conn, 1)
    assert k["karte"] == s["karte"]


def test_padua_werkbank_zeigt_wo_und_wer(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    lege_karte_an(conn, ort="Sala riunioni", wer="Anna")
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    html = web._wb_szenen_verdichtet_html(
        [dict(s, verdichtet=s.get("verdichtet") or {}) for s in daten["szenen"]])
    assert "Sala riunioni" in html and "Anna" in html
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_web.py` — Expected: FAIL (Karte im Web ohne `ort`; Werkbank ohne „Sala riunioni")

- [ ] **Step 3: Implementieren**

`web_daten.py` (neue Helfer bei `_szene_figur_ids`):

```python
def _besetzung(conn: sqlite3.Connection, szene_id: int) -> list[tuple[str, str | None]]:
    try:
        return [(z["name"], _feld(z, "rolle")) for z in conn.execute(
            "SELECT f.name AS name, sf.rolle AS rolle FROM szene_figur sf "
            "JOIN figur f ON f.id = sf.figur_id "
            f"WHERE sf.szene_id = ? AND f.{_NICHT_ENTFERNT} "
            "ORDER BY sf.position IS NULL, sf.position ASC, f.id ASC", (szene_id,))]
    except sqlite3.OperationalError:
        return [(n, None) for n in _szene_figuren(conn, szene_id)]


def _fragen(conn: sqlite3.Connection, chat_id: int, szene_id: int) -> tuple[list[str], list[str]]:
    try:
        zeilen = conn.execute(
            "SELECT text, status FROM offene_frage WHERE chat_id = ? AND szene_id = ? "
            "AND status IN ('offen', 'vertagt') ORDER BY id", (chat_id, szene_id)).fetchall()
    except sqlite3.OperationalError:
        return [], []
    return ([z["text"] for z in zeilen if z["status"] == "offen"],
            [z["text"] for z in zeilen if z["status"] == "vertagt"])


def _karte_sicht(conn: sqlite3.Connection, z) -> dict | None:
    """Dieselbe Ableitung wie ``stueck.karte`` (``stueck_sicht.karte_ansicht``),
    nur ueber das read-only-SQL dieses Moduls -- keine zweite Formatierung."""
    from interview_theater import stueck_sicht, szenenkarte

    offen, vertagt = _fragen(conn, z["chat_id"], z["id"])
    return stueck_sicht.karte_ansicht(
        szenenkarte.roh_karte_von(z), ort=z["ort"], besetzung=_besetzung(conn, z["id"]),
        zusatz=_feld(z, "wer_zusatz"), fragen_offen=offen, fragen_vertagt=vertagt,
        punkt_offen=szenenkarte._T(z["chat_id"])._PUNKT_OFFEN)
```

`_szenen` Zeile 816: `eintrag["karte"] = _karte_sicht(conn, z)`. `szenenkarten` Zeile 1848: `"karte": _karte_sicht(conn, z)`.

`web.py` in `_wb_szenen_verdichtet_html` nach `kopf`:

```python
        karte = s.get("karte") or {}
        wo_wer = " · ".join(t for t in ((karte.get("ort") or s.get("ort") or "").strip(),
                                       (karte.get("wer") or ", ".join(s.get("figuren") or [])).strip()) if t)
        teile = [kopf]
        if wo_wer:
            teile.append(f'<p class="wb-wo-wer">{_t(T._TEXT_WB_WO_WER.format(wert=wo_wer))}</p>')
        teile += [_liste_html("wb-kern", _kurzform_punkte(v), PLANUNG_PUNKT_ZEICHEN),
                  _liste_html("wb-zitate", _staerkste_zitate(v), KERNSATZ_ZEICHEN)]
```

(Die bisherige Zeile `teile = [kopf, _liste_html(...), _liste_html(...)]` in `web.py:5156-5157` wird dadurch ersetzt.)

Text: `_TEXT_WB_WO_WER = "Wo · Wer: {wert}"` (Konstante in `web.py`), en `"Where · Who: {wert}"`, it `"Dove · Chi: {wert}"`.

**Bewusste Abweichung von „keine neue UI":** Diese eine Zeile in der Werkbank ist nötig, weil die Abnahme von Problem 1 wörtlich „Werkbank … zeigt den neuen Ort" verlangt und die Padua-Werkbank bisher keinen Szenenort zeigt (`web.py:3936-4035`). Sie steht in der Übergabe.

- [ ] **Step 4: Grün** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_web.py tests/test_web_skript.py tests/test_web_skript_tab.py tests/test_werkbank_web.py tests/test_werkbank_bitgleich.py tests/test_web_daten.py tests/test_karten_cothinker.py tests/test_sprache_texte.py`

Expected: alle passed. Wird `tests/test_werkbank_bitgleich.py` nur wegen der neuen Zeile „Wo · Wer" in einem **Padua**-Szenario rot, wird die Erwartung bewusst nachgezogen und im Commit genannt. Ein Dortmund-Szenario bekommt `@pytest.mark.dortmund`.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_daten.py interview_theater/web.py interview_theater/sprachen tests/test_stueck_web.py tests
git commit -m "stueckmodell: Web liest die abgeleitete Karte; Padua-Werkbank zeigt Wo/Wer je Szene"
```

---

### Task 11: `szenenkarte` — Modellkarte über `karte_aus_modell`, Klärweg über `offene_frage`

**Files:**
- Modify: `interview_theater/szenenkarte.py`:
  - `erzeuge` (Zeilen 285-290)
  - `_bewahre_fragen` (Zeilen 423-444) fällt weg, ebenso die Übergabe in `aktualisiere_mit_dialog`/`aendere` (Zeilen 461-465, 698-704)
  - `starte_fragenklaerung` (772-795), `ueberspringe_fragen` (798-826), `beantworte_frage` (907-978), `aktive_klaerung` (755-769)
- Test: `tests/test_stueck_klaerweg.py`; vorhandene Tests in `tests/test_szenenkarte.py`, `tests/test_szenenkarte_dialog.py` angleichen

**Interfaces:**
- Consumes: `stueck.karte_aus_modell`, `stueck.frage_beantworten`, `stueck.frage_zurueckstellen`, `stueck.frage_verwerfen`, `repo.offene_fragen`
- Produces: `szene.karte_klaerung` JSON `{"ids": [int], "index": int, "antworten": [str|None], "runde": int}`

Verhalten:
1. **`erzeuge`**: Statt `repo.setze_szenenkarte` + `merke_karte_verlauf` ruft es `stueck.karte_aus_modell(conn, chat_id, szene=nummer, karte=karte, ausloeser=…, notiz=notiz)` und gibt `stueck.karte(conn, repo.hole_szene(conn, szene["id"]))` zurück.
2. **`beantworte_frage`**: Jede Antwort schließt ihre Frage **sofort** (`frage_beantworten`; bei `ist_skip` → `frage_zurueckstellen`). Bricht die Gruppe nach Frage 1 von 3 ab, ist Frage 1 trotzdem geschlossen (Problem 4). Danach wie heute EIN Neubau mit `_klaerungsnotiz`. `_nachbereitung` hängt keine `[OPEN]`-Punkte mehr an, denn vertagte Fragen zeigt die Ansicht. Die zweite Runde läuft nur, wenn der Neubau wirklich **neue** offene Fragen hat (`stueck.karte(...)["fragen"]`).
3. **`ueberspringe_fragen`**: `frage_verwerfen` je offene Frage; das JSON bleibt unberührt. Der Verlauf bekommt die abgeleitete Ansicht.
4. **`aktive_klaerung`**: sucht über **alle** Szenen nach `karte_klaerung`, nicht nur über die aktuelle (Vorbereitung für Task 15).

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_klaerweg.py
import json

from interview_theater import repo, stueck, szenenkarte
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def test_antwort_schliesst_sofort_auch_bei_abbruch(conn):
    sid = lege_karte_an(conn, fragen=["Wo?", "Wann?", "Wer?"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    assert szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "Im Loch") is True
    status = {f["text"]: f["status"] for f in repo.fragen_der_szene(conn, 1, sid)}
    assert status == {"Wo?": "beantwortet", "Wann?": "offen", "Wer?": "offen"}
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == ["Wann?", "Wer?"]


def test_skip_wird_vertagt(conn):
    sid = lege_karte_an(conn, fragen=["Wo?"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "skip")
    [f] = repo.fragen_der_szene(conn, 1, sid)
    assert f["status"] == "vertagt"


def test_ueberspringen_verwirft_ohne_json_aenderung(conn):
    sid = lege_karte_an(conn, fragen=["Unpassend?"])
    roh = repo.hole_szene(conn, sid)["karte"]
    szenenkarte.ueberspringe_fragen(conn, TG(), E(), 1, 1)
    assert repo.hole_szene(conn, sid)["karte"] == roh
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == []


def test_erzeuge_schreibt_struktur_an_ihre_stelle(conn, monkeypatch):
    from interview_theater import modellwahl

    repo.stelle_szene_sicher(conn, 1, 1)
    monkeypatch.setattr(modellwahl, "aufruf_schema", lambda *a, **k: {
        "typ": "spoken", "modus": "none", "worum": "w", "ort": "Bar", "wer": "il pubblico",
        "punkte": ["p"], "zitate": [], "questions": ["Licht?"]})
    k = szenenkarte.erzeuge(conn, object(), E(), 1, 1)
    s = repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 1))
    assert s["ort"] == "Bar" and s["wer_zusatz"] == "il pubblico"
    assert not {"ort", "wer", "fragen"} & set(json.loads(s["karte"]))
    assert k["fragen"] == ["Licht?"]
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_klaerweg.py` — Expected: FAIL (Antwort schließt nicht sofort; `erzeuge` schreibt `ort` ins JSON)

- [ ] **Step 3: Implementieren** (Kernstellen)

`starte_fragenklaerung` (statt Zeilen 783-794):

```python
    from interview_theater import stueck

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    offen = repo.offene_fragen(conn, chat_id, szene["id"], status=("offen",)) if szene else []
    if not offen:
        zeige(conn, tg, e, chat_id, nummer)
        return _T(chat_id)._ANTWORT_GESPEICHERT.format(nummer=nummer)
    repo.setze_szenenkarte_dialog(conn, szene["id"], None)
    klaerung = {"ids": [f["id"] for f in offen], "index": 0, "antworten": [], "runde": runde}
    repo.setze_szenenkarte_klaerung(conn, szene["id"], json.dumps(klaerung))
    _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FRAGE_N_VON_M.format(
        n=1, gesamt=len(offen), frage=offen[0]["text"]))
    return _T(chat_id)._ANTWORT_FRAGEN_KLAEREN
```

`beantworte_frage` (Kern):

```python
    from interview_theater import stueck

    nummer, klaerung = gefunden
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    ids = list(klaerung.get("ids") or [])
    index = int(klaerung.get("index") or 0)
    if szene is None or index >= len(ids):
        if szene is not None:
            repo.setze_szenenkarte_klaerung(conn, szene["id"], None)
        return False
    frage = repo.hole_offene_frage(conn, ids[index])
    if ist_skip(text):
        stueck.frage_zurueckstellen(conn, chat_id, frage_id=ids[index], quelle="chat")
        antwort = None
    else:
        antwort = text.strip()
        stueck.frage_beantworten(conn, chat_id, frage_id=ids[index], antwort=antwort, quelle="chat")
    antworten = list(klaerung.get("antworten") or []) + [antwort]
    index += 1
    if index < len(ids):
        repo.setze_szenenkarte_klaerung(conn, szene["id"], json.dumps(
            {"ids": ids, "index": index, "antworten": antworten, "runde": klaerung.get("runde", 1)}))
        naechste = repo.hole_offene_frage(conn, ids[index])
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FRAGE_N_VON_M.format(
            n=index + 1, gesamt=len(ids), frage=naechste["text"]))
        return True
    fragen = [repo.hole_offene_frage(conn, i)["text"] for i in ids]
```

Danach geht es weiter wie bisher (Journal je Frage, `setze_szenenkarte_klaerung(None)`, Neubau). Die neue `_nachbereitung`:

```python
    def _nachbereitung(neue_karte: dict) -> bool | None:
        if (neue_karte.get("fragen") or []) and runde == 1:
            starte_fragenklaerung(conn, tg, e, chat_id, nummer, runde=2)
            return False
        return None
```

Klärungen, die beim Deploy mitten in einer Runde stehen, haben noch das alte Format `{"index", "antworten"}` ohne `ids`. Fehlt `ids`, setzt `beantworte_frage` die Klärung auf `None` zurück, gibt `False` zurück und erzeugt keinen Fehler. Die Gruppe startet „Clear the questions" einfach neu.

`ueberspringe_fragen` (statt Zeilen 814-821):

```python
    from interview_theater import stueck

    for f in repo.offene_fragen(conn, chat_id, szene["id"], status=("offen",)):
        stueck.frage_verwerfen(conn, chat_id, frage_id=f["id"], quelle="web")
    repo.setze_szenenkarte_klaerung(conn, szene["id"], None)
    repo.merke_karte_verlauf(
        conn, chat_id, szene["id"],
        json.dumps(stueck.karte(conn, repo.hole_szene(conn, szene["id"])), ensure_ascii=False),
        AUSLOESER_FRAGEN_UEBERSPRUNGEN, _NOTIZ_FRAGEN_UEBERSPRUNGEN,
    )
```

`erzeuge` (statt Zeilen 285-290):

```python
    from interview_theater import stueck

    stueck.karte_aus_modell(
        conn, chat_id, szene=nummer, karte=karte,
        ausloeser=ausloeser or (AUSLOESER_AENDERUNG if notiz else AUSLOESER_ERSTENTWURF),
        notiz=notiz)
    return stueck.karte(conn, repo.hole_szene(conn, szene["id"]))
```

`_bewahre_fragen` löschen. In `aktualisiere_mit_dialog` und `aendere` entfällt `nachbereitung=_bewahre_fragen(...)`; `alte_fragen` wird aus `stueck.karte(conn, szene)["fragen"]` gelesen.

`aktive_klaerung`:

```python
    for s in _szenen(conn, chat_id):
        klaerung = _klaerung_von(s)
        if klaerung is not None:
            return s["nummer"], klaerung
    return None
```

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_klaerweg.py tests/test_szenenkarte.py tests/test_szenenkarte_dialog.py tests/test_karten_cothinker.py tests/test_karte_verlauf.py`
Expected: alle passed. Prüft ein bestehender Test die alte Mechanik wörtlich (z. B. dass `_bewahre_fragen` Fragen ins JSON zurückschreibt oder dass `[OPEN]` als Kartenpunkt **im JSON** steht), wird die Zusicherung auf die Ansicht `stueck.karte(...)` umgestellt. Die beobachtbare Zusage bleibt: Fragen gehen nie still verloren, `[OPEN]` steht auf der Karte.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/szenenkarte.py tests
git commit -m "stueckmodell: Karten-Neubau ueber karte_aus_modell, Klaerweg schliesst jede Frage sofort im Modell"
```

---

### Task 12: `karten_nachzug` ersetzen — Schreiben nur über die Schnittstelle

**Files:**
- Modify: `interview_theater/karten_nachzug.py:144-186` (`ziehe_nach`)
- Modify: `interview_theater/repo.py:3126-3166` (`aktualisiere_karte_und_werkbank` **löschen**)
- Modify: `tests/test_karten_nachzug.py` (neu fassen, siehe unten)
- Modify: `scripts/erzeuge_prompts_padua_voll.py:481`, `scripts/prompt_inventar.py:259` (nur prüfen, ob sie `aktualisiere_karte_und_werkbank` aufrufen; sie rufen `ziehe_nach`, das bleibt)

**Interfaces:**
- Consumes: `stueck.setze_ort`, `stueck.karte_aendern(modus=…)`, `stueck.figur_hinzu`, `stueck.karte_aus_modell` (nicht genutzt), `stueck_sicht.ordne_besetzung`
- Produces: `karten_nachzug.ziehe_nach(conn, klm, e, chat_id, szene_id, text, *, ueber_claude) -> None` (Signatur unverändert)

Neues Verhalten:
- Ein Modellaufruf wie bisher.
- **Neu:** Vorher wird geprüft, ob `text` noch der aktuelle `volltext` ist (`_spiegel`-Regel, `stagescript.py:376`). Sonst passiert nichts, denn ein älterer Text darf keinen jüngeren überschreiben.
- Der Ort geht über `stueck.setze_ort(..., quelle=QUELLE_SCRIPT)`.
- Die Figuren sind die Vereinigung aus Modell-`wer` (bekannte Namen über `ordne_besetzung`) und `_figuren_aus_text`. Jede noch nicht besetzte bekannte Figur kommt über `stueck.figur_hinzu(..., quelle=QUELLE_SCRIPT)` dazu. Unbekannte Namen werden **nicht** zur Figur, wie bisher.
- Modus über `stueck.karte_aendern(modus=…, quelle=QUELLE_SCRIPT)`.
- Es gibt **keinen** direkten `repo`-Schreibaufruf mehr.

- [ ] **Step 1: Tests neu fassen** (`tests/test_karten_nachzug.py`, die bisherigen Zusagen bleiben, jetzt über das Stückmodell)

```python
"""Phase 7: Ort/Figuren aus dem neu geschriebenen Stage Script ins
Stueckmodell (Karte t_fd88600b ersetzt den Zweit-Schreiber
``repo.aktualisiere_karte_und_werkbank``). Der Modellaufruf ist ein
Testdouble; geschrieben wird NUR ueber ``stueck``."""

import pytest

from interview_theater import karten_nachzug, repo, stueck
from tests.stueck_hilfe import lege_karte_an


class LLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append(art)
        return self.antwort


def _mit_text(conn, text="TEXT", **karte):
    sid = lege_karte_an(conn, bestaetigt=True, **karte)
    repo.setze_stagescript(conn, sid, text, None)
    return sid


def _k(conn, sid):
    return stueck.karte(conn, repo.hole_szene(conn, sid))


def test_neuer_ort_eine_stelle_alle_ansichten(conn, einst):
    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza" and _k(conn, sid)["ort"] == "Piazza"


def test_veralteter_text_schreibt_nichts(conn, einst):
    sid = _mit_text(conn, text="NEU", ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "ALT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Bar"


def test_neue_figur_nur_wenn_figur_existiert(conn, einst):
    repo.setze_figur(conn, 1, "Anna", "")
    vorher = len(repo.figuren(conn, 1))
    sid = _mit_text(conn)
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "Anna, an audience member", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert len(repo.figuren(conn, 1)) == vorher
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Anna"]


def test_abnahme_bleibt_und_eigene_szene_nicht_veraltet(conn, einst):
    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["karte_bestaetigt_am"]
    assert repo.offene_veraltet(conn, 1) == []


def test_abschnittskoepfe_und_sprecherzeilen(conn, einst):
    for n in ("Anna", "Berta", "Clara", "Dario"):
        repo.setze_figur(conn, 1, n, "")
    text = "CLARA (moderator)\nArrives.\n\nBERTA, DARIO\nWait.\n\nANNA: Hi.\n"
    sid = _mit_text(conn, text=text, wer="Anna")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "Clara", "modus": "none"}),
                              einst, 1, sid, text, ueber_claude=False)
    assert {b["name"] for b in repo.besetzung(conn, sid)} == {"Anna", "Berta", "Clara", "Dario"}


def test_modus_nur_bei_moment(conn, einst):
    sid = _mit_text(conn, typ="moment", modus="microphone")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "", "modus": "collective"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert _k(conn, sid)["modus"] == "collective"


def test_fehler_laesst_alles_stehen(conn, einst):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("boom")

    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, Kaputt(), einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Bar"


def test_kein_zweitschreiber_mehr():
    assert not hasattr(repo, "aktualisiere_karte_und_werkbank")
```

(`test_kopfzeile_erkennt_keine_unbekannten_namen` und `test_ohne_karte_tut_nichts` aus der alten Datei bleiben inhaltlich erhalten; die Szene wird wie oben über `_mit_text` angelegt.)

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_karten_nachzug.py` — Expected: FAIL (`test_veralteter_text_schreibt_nichts`, `test_kein_zweitschreiber_mehr`)

- [ ] **Step 3: Implementieren** (`ziehe_nach` neu; `_figuren_aus_text`, `SCHEMA`, `baue_nutzertext` bleiben)

```python
def ziehe_nach(conn, klm, e, chat_id: int, szene_id: int, text: str, *,
               ueber_claude: bool) -> None:
    """EIN Modellaufruf liest Ort/Figuren/Modus aus dem neuen Skripttext;
    geschrieben wird NUR ueber die Mutations-Schnittstelle (``stueck``,
    Quelle ``script``: der Text ist hier die Quelle, die eigene Szene wird
    nicht als veraltet markiert). Ein aelterer Text als der gespeicherte
    schreibt nichts (gleiche Regel wie die IT-Spiegelung)."""
    from interview_theater import stueck, stueck_sicht

    try:
        szene = repo.hole_szene(conn, szene_id)
        if szene is None or (szene["volltext"] or "").strip() != (text or "").strip():
            return
        karte = stueck.karte(conn, szene)
        if karte is None or not (text or "").strip():
            return
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=_system_fuer(chat_id),
            nutzer=baue_nutzertext(karte, text), schema=SCHEMA, art=ART,
            ueber_claude=ueber_claude, claude_modell=CLAUDE_MODELL, timeout=60.0,
        )
        nummer = szene["nummer"]
        q = stueck.QUELLE_SCRIPT
        neuer_ort = str(ergebnis.get("ort") or "").strip()
        if neuer_ort:
            stueck.setze_ort(conn, chat_id, szene=nummer, ort=neuer_ort, quelle=q)
        index = {stueck_sicht.normalisiert(f["name"]): f["id"] for f in repo.figuren(conn, chat_id)}
        aus_modell, _ = stueck_sicht.ordne_besetzung(str(ergebnis.get("wer") or ""), index)
        namen = {f["id"]: f["name"] for f in repo.figuren(conn, chat_id)}
        ids = [f for f, _ in aus_modell] + [
            f for f in _figuren_aus_text(conn, chat_id, text) if f not in dict(aus_modell)]
        for figur_id in ids:
            stueck.figur_hinzu(conn, chat_id, name=namen[figur_id], szene=nummer, quelle=q)
        neuer_modus = str(ergebnis.get("modus") or "").strip().lower()
        if (karte.get("typ") == "moment" and neuer_modus in szenenkarte.MODI
                and neuer_modus not in ("none", karte.get("modus"))):
            stueck.karte_aendern(conn, chat_id, szene=nummer, modus=neuer_modus, quelle=q)
    except Exception:
        log.exception("P7-Meta-Nachzug fehlgeschlagen, chat_id=%s, szene_id=%s",
                      chat_id, szene_id)
```

(Modulkopf: `erkenner` aus dem Import streichen, falls nicht mehr gebraucht. Den Docstring des Moduls um einen Absatz ergänzen: „Seit dem Stückmodell (t_fd88600b) schreibt dieses Modul nichts selbst".)

`repo.aktualisiere_karte_und_werkbank` (repo.py:3126-3166) löschen.

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_karten_nachzug.py tests/test_stagescript.py tests/test_erzeuge_prompts_padua_voll.py tests/test_modellaufrufe_inventar.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater/karten_nachzug.py interview_theater/repo.py tests/test_karten_nachzug.py
git commit -m "stueckmodell: karten_nachzug schreibt nur noch ueber stueck; Zweit-Schreiber aktualisiere_karte_und_werkbank entfernt"
```

---

### Task 13: Alle übrigen Schreiber auf die Schnittstelle + Sperre gegen Zweitwege

**Files (je Fundstelle, Stand 10.10.2026):**
- `interview_theater/repo.py:3282-3301` (`setze_szenenfeld`): `if feld in NUR_UEBER_STUECK: raise ValueError(...)`, `NUR_UEBER_STUECK = ("ort",)`
- `interview_theater/repo.py:3416` (`ABGLEICHBARE_SZENENFELDER`): `"ort"` entfernen; die Aufrufer setzen den Ort danach selbst (s. u.)
- `interview_theater/erkenner.py:1119-1135` (`_wende_szene_planen_an`): `figuren` → `stueck.setze_besetzung(namen=…, quelle=QUELLE_PLANUNG)`, `ort` → `stueck.setze_ort(quelle=QUELLE_PLANUNG)`
- `interview_theater/erkenner.py:1328-1344` (`_ziehe_figur_festlegung_nach`): Kartenpunkt über `stueck.karte_aendern(szene=…, punkte=_ersetze_oder_haenge_an(...), quelle="erkenner")`. Das Erkennerverhalten (welche Szenen, welcher Text) bleibt gleich; nur der Schreibweg ändert sich, und die Abnahme bleibt jetzt stehen.
- `interview_theater/befehle.py:1365-1367` (`_setze_szenenfeld`): `figuren` → `stueck.setze_besetzung`, `ort` → `stueck.setze_ort`
- `interview_theater/knoepfe/szenen.py:1799-1802` (`_speichere_szenenfelder`): wie befehle
- `interview_theater/web_schreiben.py:471-480` (`_setze_szenenfeld` für `szene_ort`) und `:502` (`_setze_szene_figuren`): Ort → `stueck.setze_ort(quelle="web")`; Figuren-ids → Namen → `stueck.setze_besetzung(quelle="web")`
- `interview_theater/entwurf.py:327-328`: `stueck.setze_ort(..., quelle=QUELLE_PLANUNG)`
- `interview_theater/szene.py:672-673`: für `feld == "ort"` → `stueck.setze_ort(..., quelle=QUELLE_PLANUNG)`; `zeit`/`anlass` bleiben auf `setze_szenenfeld`
- `interview_theater/prueflauf.py:263-265`: `if feld in repo.NUR_UEBER_STUECK: stueck.setze_ort(..., quelle=QUELLE_PLANUNG); continue`
- `interview_theater/szenenfolge.py:338` und `interview_theater/kurzgeschichte.py:210` (Aufrufer von `gleiche_szenenfolge_ab`): danach je Zeile mit `ort` → `stueck.setze_ort(..., szene=<nummer>, quelle=QUELLE_PLANUNG)`
- `interview_theater/szenenfolge.py:349` (`repo.setze_szene_figuren` in `lege_an`) → `stueck.setze_besetzung(..., quelle=QUELLE_PLANUNG)`
- jede weitere Fundstelle, die `test_nur_stueck_ruft_die_tatsachen_schreiber` (Step 1) meldet, nach demselben Muster
- `tests/test_stueckmodell_skripte.py::test_fakten_lesen_ort_aus_allen_ansichten`: auf `lege_karte_an(conn, ort="Bar")` umstellen
- Test: `tests/test_stueck_einzige_schreibstelle.py`

**Interfaces:**
- Consumes: `stueck.setze_ort`, `stueck.setze_besetzung`, `stueck.karte_aendern`
- Produces: `repo.NUR_UEBER_STUECK: tuple[str, ...]`

- [ ] **Step 1: Failing test**

```python
# tests/test_stueck_einzige_schreibstelle.py
"""Problem 1/2 (Karte t_fd88600b): Ort, Besetzung und Karte schreibt NUR
``stueck.py``. Rot, sobald ein Modul wieder einen eigenen Weg zu derselben
Tatsache baut."""

import ast
import pathlib

import pytest

from interview_theater import repo

NUR_STUECK = {"setze_szenenort", "setze_besetzung", "setze_szene_figuren",
              "aktualisiere_szenenkarte", "setze_szenenkarte", "merke_karte_verlauf",
              "lege_offene_frage_an", "setze_frage_status", "nummeriere_szenen"}
#: Ausnahmen mit Grund: szenenkarte schreibt Dialog-/Klaerungsstand und den
#: Verlauf "uebersprungen" (Ablaufzustand, keine Tatsache).
AUSNAHMEN = {("szenenkarte.py", "merke_karte_verlauf")}


def test_nur_stueck_ruft_die_tatsachen_schreiber():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    funde = []
    for datei in wurzel.rglob("*.py"):
        if datei.name in {"stueck.py", "repo.py", "db.py"}:
            continue
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if (isinstance(knoten, ast.Attribute) and isinstance(knoten.value, ast.Name)
                    and knoten.value.id == "repo" and knoten.attr in NUR_STUECK
                    and (datei.name, knoten.attr) not in AUSNAHMEN):
                funde.append(f"{datei.relative_to(wurzel)}:{knoten.lineno} repo.{knoten.attr}")
    assert funde == []


def test_ort_ist_ueber_setze_szenenfeld_gesperrt(conn):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    with pytest.raises(ValueError):
        repo.setze_szenenfeld(conn, sid, "ort", "Bar")
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_einzige_schreibstelle.py` — Expected: FAIL mit der Fundliste (erkenner, befehle, knoepfe/szenen, web_schreiben, …)

- [ ] **Step 3: Umstellen** (Beispiele; jede Fundstelle aus der Testausgabe nach demselben Muster)

`erkenner._wende_szene_planen_an` (Zeilen 1119-1135):

```python
        if feld == "figuren":
            ids = _figuren_aus_namen(conn, chat_id, neuer_wert)
            if not ids:
                continue
            vorher = [f["id"] for f in repo.szene_figuren(conn, szene_id)]
            if vorher == ids:
                continue
            namen = {f["id"]: f["name"] for f in repo.figuren(conn, chat_id)}
            stueck.setze_besetzung(conn, chat_id, szene=nummer, namen=[namen[i] for i in ids],
                                   zusatz=repo.hole_szene(conn, szene_id)["wer_zusatz"],
                                   quelle=stueck.QUELLE_PLANUNG)
            geaendert.append("figuren")
            continue
        if (repo.hole_szene(conn, szene_id)[feld] or "") == neuer_wert:
            continue
        if feld in repo.NUR_UEBER_STUECK:
            stueck.setze_ort(conn, chat_id, szene=nummer, ort=neuer_wert, quelle=stueck.QUELLE_PLANUNG)
        else:
            repo.setze_szenenfeld(conn, szene_id, feld, neuer_wert)
        geaendert.append(feld)
```

`erkenner._ziehe_figur_festlegung_nach` (Zeilen 1328-1344):

```python
    from interview_theater import stueck

    for szene in repo.hole_szenen(conn, chat_id):
        if szene["entfernt_am"] or szene["fertig_am"]:
            continue
        karte = stueck.karte(conn, szene)
        if karte is None:
            continue
        if figur_id not in {f["id"] for f in repo.szene_figuren(conn, szene["id"])}:
            continue
        roh_punkte = [p for p in karte.get("punkte") or [] if not stueck_sicht.OFFEN_PUNKT.match(p)]
        stueck.karte_aendern(conn, chat_id, szene=szene["nummer"],
                             punkte=_ersetze_oder_haenge_an(roh_punkte, praefix, hakenpunkt),
                             quelle="erkenner")
```

(Das JSON enthält nie `[OPEN]`-Punkte, daher wird hier aus der Ansicht `roh_punkte` gebildet. Import `from interview_theater import stueck_sicht` lokal ergänzen. Der alte Verlauf-Notiztext `notiz` entfällt; den Verlauf schreibt `karte_aendern`.)

`web_schreiben._setze_szene_figuren` (Zeile ~502): Figuren-ids → Namen über `repo.figuren`, dann `stueck.setze_besetzung(conn, chat_id, szene=zeile["nummer"], namen=…, zusatz=zeile["wer_zusatz"], quelle="web")`. Bei `fehler` meldet die Seite den Warnungstext wie bei anderen Formularfehlern (gleicher Rückgabeweg wie `_setze_szenenfeld`).

Der dritte Test aus Task 0 schreibt den Ort über die Testhilfe:

```python
def test_fakten_lesen_ort_aus_allen_ansichten(conn, padua):
    from tests.stueck_hilfe import lege_karte_an

    lege_karte_an(conn, ort="Bar")
    f = stueckmodell_ansichten.fakten(conn, 1)
    assert f["1"]["werkbank_ort"] == "Bar"
    assert f["1"]["karte_wo"] == "Bar"
    assert "Bar" in f["1"]["pdf_meta"]
```

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_einzige_schreibstelle.py tests/test_stueckmodell_skripte.py tests/test_erkenner.py tests/test_figur_festlegung_nachzug.py tests/test_befehle.py tests/test_web_edit.py tests/test_entwurf.py tests/test_szene.py tests/test_szenenfolge.py tests/test_prueflauf.py tests/test_szenenabgleich.py tests/test_kurzgeschichte.py`

Expected: alle passed. Setzt ein Test in seiner Vorbereitung `repo.setze_szenenfeld(conn, sid, "ort", …)`, wird er auf `stueck.setze_ort(conn, 1, szene=<nr>, ort=…)` umgestellt. Ist der Test nur noch wegen Dortmund-Verhalten rot, bekommt er `@pytest.mark.dortmund`.

- [ ] **Step 5: Commit**

```bash
git add interview_theater tests
git commit -m "stueckmodell: alle Schreiber von Ort/Besetzung/Karte ueber stueck; Sperre gegen Zweitwege"
```

---

### Task 14: „Szene N passt nicht mehr zu … — neu schreiben? Ja/Nein"

**Files:**
- Modify: `interview_theater/knoepfe/texte.py` (bei Zeile ~288: `ART_VERALTET_NEU = "veraltet_neu"`, `ART_VERALTET_LASSEN = "veraltet_lassen"`)
- Modify: `interview_theater/knoepfe/__init__.py:56-90` (Export)
- Modify: `interview_theater/knoepfe/wirkung.py` (`_wirkung_veraltet_neu`, `_wirkung_veraltet_lassen`; Einträge in `_WIRKUNGEN` bei Zeile ~1915)
- Modify: `interview_theater/knoepfe/szenen.py` (`biete_veraltete(conn, tg, e, chat_id) -> int`)
- Modify: `interview_theater/stueck.py` (`_T(chat_id)` für die `_GRUND_*`-Texte, gleiches Muster wie `szenenkarte._T`; `_TEXT_VERALTET`, `_TEXT_KOPF_VERALTET`, `_TEXT_VERALTET_GELASSEN`; Knopfbeschriftungen `_TEXT_JA_NEU_KNOPF`, `_TEXT_NEIN_LASSEN_KNOPF`)
- Modify: `interview_theater/stagescript.py:334-349` (`_speichere_text`: nach `repo.setze_stagescript` → `repo.erledige_veraltet_fuer(conn, chat_id, szene["id"], "script", "neu_geschrieben")`; nach dem Setzen von `stage_kopf` (Zeile 328) → `repo.erledige_veraltet_fuer(conn, chat_id, None, "kopf", "neu_geschrieben")`)
- Modify: Aufrufpunkte für `biete_veraltete`:
  - `stagescript.weiter` (`stagescript.py:774`) am Anfang;
  - `stagescript.zeige_aenderung` am Ende;
  - `ablauf.antworte` nach dem Versand der Antwort (deckt Web-Änderungen ab);
  - `knoepfe/wirkung.py` nach `_wirkung_karte_update` (`:470`).
- Modify: `interview_theater/sprachen/{en,it}/texte.toml`
- Test: `tests/test_stueck_angebot.py`

**Interfaces:**
- Consumes: `repo.offene_veraltet(nur_unangeboten=True)`, `repo.markiere_veraltet_angeboten`, `repo.erledige_veraltet`, `stagescript.starte(conn, tg, klm, e, chat_id, nummer, notiz)`
- Produces: `knoepfe.szenen.biete_veraltete(conn, tg, e, chat_id) -> int` (Anzahl gesendeter Angebote); `ART_VERALTET_NEU`/`ART_VERALTET_LASSEN` (Wert = `str(veraltet_id)`)

Verhalten:
- Je offene, noch nicht angebotene `veraltet`-Zeile geht genau ein Text mit zwei Knöpfen raus. Beim Script: `_T(chat_id)._TEXT_VERALTET.format(nummer=…, grund=…)`. Beim Kopf: `_TEXT_KOPF_VERALTET`. Danach `markiere_veraltet_angeboten`.
- **Ja** (`_wirkung_veraltet_neu`):
  - Es gibt keinen Modellaufruf im Handler.
  - `erledige_veraltet(id, "neu")`.
  - Bei `script` folgt `stagescript.starte(conn, d.tg, d.klm, d.e, d.chat_id, nummer, notiz=grund)`; `starte` hat seinen eigenen Thread.
  - Bei `kopf` werden `stage_kopf`/`stage_kopf_it` auf `None` gesetzt, über `repo.setze_arbeitsstand` (der Kopf ist Prosa, keine Tatsache). Danach `stagescript.starte(..., nummer=<erste Szene>, notiz=grund)`, denn `mit_kopf` baut den Kopf mit, solange er leer ist (`stagescript.py:288-289`).
- **Nein** (`_wirkung_veraltet_lassen`): `erledige_veraltet(id, "lassen")` und `_T(chat_id)._TEXT_VERALTET_GELASSEN`.
- Knopf-Zusagen: `callback_data` über `_daten(repo.lege_knopf_an(...))`, idempotent über `beanspruche_knopf` (macht `behandle`).

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_angebot.py
from interview_theater import knoepfe, repo, stagescript, stueck
from interview_theater.knoepfe import szenen as ks, wirkung
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def _veraltet(conn):
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 in the Bar.", None)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    return sid


def test_angebot_einmal_mit_ja_nein(conn):
    _veraltet(conn)
    tg = TG()
    assert ks.biete_veraltete(conn, tg, E(), 1) == 1
    assert "Piazza" in tg.gesendet[-1] and "1" in tg.gesendet[-1]
    assert ks.biete_veraltete(conn, tg, E(), 1) == 0


def test_nein_laesst_text_stehen(conn):
    sid = _veraltet(conn)
    [v] = repo.offene_veraltet(conn, 1)
    d = wirkung.Druck(tg=TG(), klm=None, e=E(), knopf=None, chat_id=1, wert=str(v["id"]))
    wirkung._wirkung_veraltet_lassen(conn, d)
    assert repo.offene_veraltet(conn, 1) == []
    assert repo.hole_szene(conn, sid)["volltext"] == "SCENE 1 in the Bar."


def test_ja_startet_den_schreiblauf(conn, monkeypatch):
    _veraltet(conn)
    aufrufe = []
    monkeypatch.setattr(stagescript, "starte", lambda *a, **k: aufrufe.append((a[5], k.get("notiz"))))
    [v] = repo.offene_veraltet(conn, 1)
    d = wirkung.Druck(tg=TG(), klm=object(), e=E(), knopf=None, chat_id=1, wert=str(v["id"]))
    wirkung._wirkung_veraltet_neu(conn, d)
    assert aufrufe and aufrufe[0][0] == 1 and "Piazza" in aufrufe[0][1]


def test_neu_geschriebener_text_erledigt_den_vermerk(conn, einst):
    sid = _veraltet(conn)
    stagescript._speichere_text(conn, None, einst, 1, repo.hole_szene(conn, sid),
                                "SCENE 1 on the Piazza.", False)
    assert repo.offene_veraltet(conn, 1) == []


def test_knopfarten_registriert():
    assert knoepfe.ART_VERALTET_NEU in knoepfe._WIRKUNGEN
    assert knoepfe.ART_VERALTET_LASSEN in knoepfe._WIRKUNGEN
```

(Die Feldnamen von `wirkung.Druck` vor dem Schreiben in `knoepfe/wirkung.py:102` nachsehen; weichen sie ab, wird der Testaufbau angepasst, nicht der Druck.)

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_angebot.py tests/test_knoepfe_struktur.py` — Expected: FAIL (`biete_veraltete` fehlt)

- [ ] **Step 3: Implementieren**

`knoepfe/szenen.py`:

```python
def biete_veraltete(conn, tg, e, chat_id: int) -> int:
    """Stueckmodell (t_fd88600b): je Prosa, die nach einer Aenderung nicht
    mehr passt, EIN Angebot "Szene N passt nicht mehr zu ... -- neu
    schreiben?" mit Ja/Nein. Prosa wird nie still umgeschrieben. Kein
    Modellaufruf; ein Angebot je Vermerk (``angeboten_am``)."""
    from interview_theater import stueck

    gesendet = 0
    for v in repo.offene_veraltet(conn, chat_id, nur_unangeboten=True):
        if v["ansicht"] == "kopf":
            text = stueck._T(chat_id)._TEXT_KOPF_VERALTET.format(grund=v["grund"])
        else:
            szene = repo.hole_szene(conn, v["szene_id"])
            if szene is None or szene["entfernt_am"]:
                repo.erledige_veraltet(conn, v["id"], "lassen")
                continue
            text = stueck._T(chat_id)._TEXT_VERALTET.format(nummer=szene["nummer"], grund=v["grund"])
        leiste = [
            _knopf(conn, chat_id, stueck.T._TEXT_JA_NEU_KNOPF, ART_VERALTET_NEU, str(v["id"])),
            _knopf(conn, chat_id, stueck.T._TEXT_NEIN_LASSEN_KNOPF, ART_VERALTET_LASSEN, str(v["id"])),
        ]
        message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
        repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
        repo.markiere_veraltet_angeboten(conn, v["id"])
        gesendet += 1
    return gesendet
```

`knoepfe/wirkung.py`:

```python
def _wirkung_veraltet_neu(conn, d: Druck) -> str:
    """"Ja, neu schreiben": kein Modellaufruf hier -- ``stagescript.starte``
    gibt an einen eigenen Thread ab (Knopf-Zusage 2)."""
    from interview_theater import stagescript, stueck

    v = repo.hole_veraltet(conn, int(d.wert))
    if v is None or v["chat_id"] != d.chat_id or v["erledigt_am"]:
        return stueck._T(d.chat_id)._TEXT_VERALTET_ERLEDIGT
    repo.erledige_veraltet(conn, v["id"], "neu")
    if v["ansicht"] == "kopf":
        repo.setze_arbeitsstand(conn, d.chat_id, "stage_kopf", None)
        repo.setze_arbeitsstand(conn, d.chat_id, "stage_kopf_it", None)
        erste = min((s["nummer"] for s in repo.hole_szenen(conn, d.chat_id)
                     if s["nummer"] is not None and not s["entfernt_am"]), default=None)
        if erste is None:
            return stueck._T(d.chat_id)._TEXT_VERALTET_ERLEDIGT
        nummer = erste
    else:
        nummer = repo.hole_szene(conn, v["szene_id"])["nummer"]
    stagescript.starte(conn, d.tg, d.klm, d.e, d.chat_id, nummer, notiz=v["grund"])
    return stueck._T(d.chat_id)._TEXT_VERALTET_NEU.format(nummer=nummer)


def _wirkung_veraltet_lassen(conn, d: Druck) -> str:
    from interview_theater import stueck

    v = repo.hole_veraltet(conn, int(d.wert))
    if v is None or v["chat_id"] != d.chat_id or v["erledigt_am"]:
        return stueck._T(d.chat_id)._TEXT_VERALTET_ERLEDIGT
    repo.erledige_veraltet(conn, v["id"], "lassen")
    nummer = repo.hole_szene(conn, v["szene_id"])["nummer"] if v["szene_id"] else 0
    text = stueck._T(d.chat_id)._TEXT_VERALTET_GELASSEN.format(nummer=nummer)
    d.tg.sende(d.chat_id, text)
    return text
```

`stueck.py` (Texte und `_T`):

```python
_TEXT_VERALTET = "Szene {nummer} passt nicht mehr zu: {grund}. Neu schreiben?"
_TEXT_KOPF_VERALTET = "Der Kopf des Skripts passt nicht mehr zu: {grund}. Neu schreiben?"
_TEXT_VERALTET_GELASSEN = "Ok, Szene {nummer} bleibt, wie sie ist."
_TEXT_VERALTET_NEU = "Ich schreibe Szene {nummer} neu."
_TEXT_VERALTET_ERLEDIGT = "Das ist schon entschieden."
_TEXT_JA_NEU_KNOPF = "Ja, neu schreiben"
_TEXT_NEIN_LASSEN_KNOPF = "Nein, so lassen"

# am Modulende, nach T:
_T_IT = sprache.Texte(__name__, sprachcode="it")


def _T(chat_id: int) -> sprache.Texte:
    from interview_theater import workshop

    return _T_IT if chat_id in workshop.italienisch_ab_phase6_chats() else T
```

Die `_GRUND_*`-Aufrufe in `stueck.py` (Tasks 4–6) nutzen ab jetzt `_T(chat_id)` statt `T`, damit der Grund in der Sprache des Angebots steht.

TOML en (Knöpfe bleiben EN, deshalb tragen auch it-Gruppen die englischen Beschriftungen aus `T`):

```toml
_TEXT_VERALTET = "Scene {nummer} no longer fits: {grund}. Rewrite it?"
_TEXT_KOPF_VERALTET = "The script header no longer fits: {grund}. Rewrite it?"
_TEXT_VERALTET_GELASSEN = "Ok, scene {nummer} stays as it is."
_TEXT_VERALTET_NEU = "Rewriting scene {nummer}."
_TEXT_VERALTET_ERLEDIGT = "That is already decided."
_TEXT_JA_NEU_KNOPF = "Yes, rewrite"
_TEXT_NEIN_LASSEN_KNOPF = "No, keep it"
```

TOML it:

```toml
_TEXT_VERALTET = "La scena {nummer} non corrisponde più a: {grund}. La riscrivo?"
_TEXT_KOPF_VERALTET = "L'intestazione del copione non corrisponde più a: {grund}. La riscrivo?"
_TEXT_VERALTET_GELASSEN = "Ok, la scena {nummer} resta com'è."
_TEXT_VERALTET_NEU = "Riscrivo la scena {nummer}."
_TEXT_VERALTET_ERLEDIGT = "È già deciso."
```

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_angebot.py tests/test_knoepfe_struktur.py tests/test_stagescript.py tests/test_sprache_texte.py tests/test_ablauf.py`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add interview_theater tests/test_stueck_angebot.py
git commit -m "stueckmodell: Ja/Nein-Angebot 'Szene N passt nicht mehr zu ... -- neu schreiben?'"
```

---

### Task 15: Verbote → Warnungen (Szenen-Gates, Phasensprung)

**Files:**
- Modify: `interview_theater/szenenkarte.py:370-382` (`starte_dialog`), `:447-466` (`aktualisiere_mit_dialog`), `:469-481` (`behalte_karte`), `:647-676` (`bestaetige`), `:772-781` (`starte_fragenklaerung`), `:798-808` (`ueberspringe_fragen`). Gemeinsamer Helfer `_ziel_mit_warnung`.
- Modify: `interview_theater/stagescript.py:788-822` (`bestaetige`), `_TEXT_ERST_VORHERIGE` (Zeile ~967) → `_WARNUNG_VORHERIGE_OFFEN`
- Modify: `interview_theater/phasen.py` (neu `warnungen`, nach `naechste_moegliche`)
- Modify: `interview_theater/befehle.py:942` (`wechsle_phase`: Warnung nach `phasen.meldung`)
- Modify: `interview_theater/sprachen/{en,it}/texte.toml`
- Test: `tests/test_stueck_warnungen.py`; bestehende Tests, die `_TEXT_NICHT_DRAN`/`_TEXT_ERST_VORHERIGE` als Ablehnung prüfen (`tests/test_szenenkarte.py`, `tests/test_szenenkarte_dialog.py`, `tests/test_stagescript.py`, `tests/test_ueberarbeitung_phase7.py`)

**Interfaces:**
- Produces: `phasen.warnungen(conn, chat_id: int, ziel: int) -> list[str]` (leer, wenn `voraussetzungen()[ziel]` wahr ist; sonst höchstens drei Sätze aus `fehlstellen.register`, deren `phase < ziel`, oder ein Ersatzsatz `_WARNUNG_PHASE_ALLGEMEIN`)

Regeln:
- **Karten (P6/P7):**
  - Eine andere als die aktuelle Karte lässt sich öffnen, ändern, klären, überspringen und speichern.
  - Der Chat bekommt vorher EINE Warnzeile `_WARNUNG_ANDERE_KARTE` („Karte {nummer} wird geändert; Karte {aktuell} ist noch nicht gespeichert.").
  - Abgelehnt wird nur noch, wenn die Szene nicht existiert (`_TEXT_UNBEKANNTE_KARTE`) oder, bei `bestaetige`, wenn die Karte **offene** Fragen hat. Die Speichersperre bei offenen Fragen bleibt: Birk-Entscheid 08.10. ~09:20, kein Phasen-Gate.
- **Stage Script (P7):**
  - `bestaetige` auf Szene N mit Text speichert immer.
  - Ist eine frühere Szene offen, folgt die Warnzeile `_WARNUNG_VORHERIGE_OFFEN` („Szene {nummer} ist gespeichert. Szene {offen} ist noch nicht gespeichert.").
  - Ohne Text bleibt es bei `_TEXT_NICHT_DRAN`: es gibt nichts zu speichern, das ist kein Verbot.
- **Phasensprung:** `wechsle_phase` schaltet wie bisher. Liefert `phasen.warnungen(conn, chat_id, nummer)` etwas, folgt eine Nachricht `_WARNUNG_PHASE_KOPF` plus Zeilen. `p5_gate` bleibt vorgeschaltet (siehe Gate-Abschnitt oben).

- [ ] **Step 1: Failing tests**

```python
# tests/test_stueck_warnungen.py
from interview_theater import befehle, phasen, repo, stagescript, szenenkarte
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def test_abgenommene_karte_in_phase_7_aenderbar(conn):
    phasen.setze(conn, 1, 7, "test")
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2)
    tg = TG()
    antwort = szenenkarte.starte_dialog(conn, tg, E(), 1, 1)
    assert antwort == szenenkarte._T(1)._ANTWORT_DIALOG_GESTARTET
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1
    assert any("2" in t for t in tg.gesendet)  # Warnzeile nennt die offene Karte


def test_speichern_szene_2_vor_szene_1_mit_warnung(conn):
    for n in (1, 2):
        sid = lege_karte_an(conn, 1, n, bestaetigt=True)
        repo.setze_stagescript(conn, sid, f"SCENE {n}", None)
    tg = TG()
    stagescript.bestaetige(conn, tg, None, E(), 1, 2)
    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 2))["fertig_am"]
    assert stagescript._T(1)._WARNUNG_VORHERIGE_OFFEN.format(nummer=2, offen=1) in tg.gesendet


def test_offene_fragen_sperren_weiterhin(conn):
    lege_karte_an(conn, 1, 1, fragen=["Wo?"])
    antwort = szenenkarte.bestaetige(conn, TG(), None, E(), 1, 1)
    assert antwort == szenenkarte._T(1)._TEXT_FRAGEN_OFFEN_ABGELEHNT


def test_phasenwarnung_ohne_sperre(conn, monkeypatch):
    monkeypatch.setattr(befehle, "p5_gate", lambda *a, **k: False)
    monkeypatch.setattr(befehle.knoepfe, "eintritt_in_phase", lambda *a, **k: None)
    tg = TG()
    assert phasen.warnungen(conn, 1, 5)
    befehle.wechsle_phase(conn, tg, None, E(), 1, 5)
    assert phasen.aktuelle(conn, 1) == 5
    assert any(t.startswith(phasen.T._WARNUNG_PHASE_KOPF.format(phase=5)) for t in tg.gesendet)


def test_keine_warnung_wenn_voraussetzung_erfuellt(conn, monkeypatch):
    monkeypatch.setattr(phasen, "voraussetzungen", lambda c, i: {5: True})
    assert phasen.warnungen(conn, 1, 5) == []
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_warnungen.py` — Expected: FAIL (`_TEXT_NICHT_DRAN` statt Dialog; `phasen.warnungen` fehlt)

- [ ] **Step 3: Implementieren**

`szenenkarte.py`:

```python
def _ziel_mit_warnung(conn, tg, e, chat_id: int, nummer: int):
    """Stueckmodell (t_fd88600b, Problem 2): jede Karte ist in jeder Phase
    aenderbar. Statt "nicht dran" eine Warnzeile, wenn eine fruehere Karte
    noch offen ist. ``None`` nur, wenn es die Szene nicht gibt."""
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_UNBEKANNTE_KARTE.format(nummer=nummer))
        return None
    aktuell = aktuelle_nummer(conn, chat_id)
    if aktuell is not None and aktuell != nummer:
        _sende(conn, tg, e, chat_id, _T(chat_id)._WARNUNG_ANDERE_KARTE.format(
            nummer=nummer, aktuell=aktuell))
    return szene
```

In den sechs Funktionen ersetzt dieser Helfer den Block `if nummer != aktuelle_nummer(...)` samt nachfolgendem `szene is None`-Block, zum Beispiel in `starte_dialog`:

```python
    szene = _ziel_mit_warnung(conn, tg, e, chat_id, nummer)
    if szene is None:
        return _T(chat_id)._TEXT_UNBEKANNTE_KARTE.format(nummer=nummer)
    repo.setze_szenenkarte_dialog(conn, szene["id"], repo._jetzt())
```

In `bestaetige` bleibt das Busy-Gate (`laeuft`) davor stehen, ebenso die Sperre bei offenen Fragen danach.

`stagescript.bestaetige` (statt Zeilen 793-822):

```python
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None or not _gesetzt(szene["volltext"]):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    aktuell = aktuelle_nummer(conn, chat_id)
    repo.setze_szene_fertig(conn, szene["id"], True)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          _T(chat_id)._JOURNAL_GESPEICHERT.format(nummer=nummer,
                                                        titel=szene["titel"] or "").strip(),
                          quelle="knopf")
    antwort = _T(chat_id)._ANTWORT_GESPEICHERT.format(nummer=nummer)
    if aktuell is not None and aktuell < nummer:
        # Stueckmodell (t_fd88600b, Vorfall 6 "Speicher-Sperre"): speichern
        # IMMER, die offene fruehere Szene ist eine Warnung, kein Verbot.
        _sende(conn, tg, e, chat_id, _T(chat_id)._WARNUNG_VORHERIGE_OFFEN.format(
            nummer=nummer, offen=aktuell))
    weiter(conn, tg, klm, e, chat_id)
    return antwort
```

`phasen.py`:

```python
def warnungen(conn, chat_id: int, ziel: int) -> list[str]:
    """Was fuer Phase ``ziel`` laut Materiallage noch fehlt -- als Saetze,
    NIE als Sperre (Stueckmodell, t_fd88600b, Problem 2). ``voraussetzungen``
    bleibt, was es ist: Fokus und Vorschlag. Leer, wenn die Lage reicht."""
    from interview_theater import fehlstellen

    if voraussetzungen(conn, chat_id).get(ziel, True):
        return []
    saetze = [e["text"] for e in fehlstellen.register(conn, chat_id, hoechstens=50)
              if e["phase"] < ziel][:3]
    return saetze or [T._WARNUNG_PHASE_ALLGEMEIN.format(phase=ziel)]
```

(`phasen.py` hat `T = sprache.Texte(__name__)`; falls nicht, nach dem Muster aus `fehlstellen.py:386-387` am Modulende ergänzen.)

`befehle.wechsle_phase` nach `tg.sende(chat_id, phasen.meldung(nummer))`:

```python
    fehlt = phasen.warnungen(conn, chat_id, nummer)
    if fehlt:
        tg.sende(chat_id, phasen.T._WARNUNG_PHASE_KOPF.format(phase=nummer) + "\n"
                 + "\n".join(f"- {s}" for s in fehlt))
```

Texte (deutsch als Konstante, plus en/it):

| Konstante | de | en | it |
|---|---|---|---|
| `szenenkarte._WARNUNG_ANDERE_KARTE` | „Karte {nummer} wird geändert; Karte {aktuell} ist noch nicht gespeichert." | "Changing card {nummer}; card {aktuell} is not saved yet." | "Modifico la scheda {nummer}; la scheda {aktuell} non è ancora salvata." |
| `szenenkarte._TEXT_UNBEKANNTE_KARTE` | „Eine Szene {nummer} gibt es nicht." | "There is no scene {nummer}." | "Non c'è una scena {nummer}." |
| `stagescript._WARNUNG_VORHERIGE_OFFEN` | „Szene {nummer} ist gespeichert. Szene {offen} ist noch nicht gespeichert." | "Scene {nummer} is saved. Scene {offen} is not saved yet." | "La scena {nummer} è salvata. La scena {offen} non è ancora salvata." |
| `phasen._WARNUNG_PHASE_KOPF` | „Phase {phase} ist offen -- laut Plan fehlt noch:" | "Phase {phase} is open -- according to the plan, still missing:" | "La fase {phase} è aperta -- secondo il piano manca ancora:" |
| `phasen._WARNUNG_PHASE_ALLGEMEIN` | „Für Phase {phase} fehlt laut Plan noch etwas." | "Something is still missing for phase {phase}." | "Per la fase {phase} manca ancora qualcosa." |

`_TEXT_ERST_VORHERIGE` wird aus `stagescript.py` und beiden TOML-Dateien entfernt (es ist kein Aufrufer mehr übrig).

- [ ] **Step 4: Grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueck_warnungen.py tests/test_szenenkarte.py tests/test_szenenkarte_dialog.py tests/test_stagescript.py tests/test_ueberarbeitung_phase6.py tests/test_ueberarbeitung_phase7.py tests/test_phasen.py tests/test_befehle.py tests/test_befehle_phasenwechsel_interview.py tests/test_sprache_texte.py tests/test_knoepfe_karte.py`

Expected: alle passed. Ein bestehender Test, der „nicht dran → abgelehnt" festschreibt, wird auf die neue Zusage umgestellt („andere Karte → Warnung + Wirkung"). Er wird nicht gelöscht, und der Commit nennt ihn.

- [ ] **Step 5: Commit**

```bash
git add interview_theater tests
git commit -m "stueckmodell: Szenen-Verbote werden Warnungen; phasen.warnungen beim Phasensprung"
```

---

### Task 16: Abnahme-Mutationstests je Problem 1–4

Diese Tests sind die Abnahme der Karte. Jeder legt einen **Giftwert** in die frühere Zweitstelle (Karten-JSON). Liest irgendeine Ansicht wieder aus einer zweiten Spalte statt aus der Ableitung, erscheint das Gift, und der Test wird rot.

**Files:**
- Test: `tests/test_stueckmodell_abnahme.py`

- [ ] **Step 1: Tests schreiben**

```python
# tests/test_stueckmodell_abnahme.py
"""Abnahme Karte t_fd88600b, Probleme 1-4. Jeder Test wird rot, wenn eine
Ansicht ihre Tatsache wieder aus einer ZWEITEN Stelle liest (Giftwert im
Karten-JSON) oder wenn Prosa still umgeschrieben wird."""

import json

import pytest

from interview_theater import phasen, repo, stagescript, stueck, szenenkarte, web, web_daten, workshop
from interview_theater.knoepfe import szenen as ks
from tests.stueck_hilfe import TG, lege_karte_an

GIFT = "GIFTWERT-ZWEITE-SPALTE"


class E:
    bot_name = "test"


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _vergifte(conn, sid, **felder):
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    roh.update(felder)
    conn.execute("UPDATE szene SET karte = ? WHERE id = ?", (json.dumps(roh), sid))
    conn.commit()


def _alle_ansichten(conn, sid) -> str:
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    szene = repo.hole_szene(conn, sid)
    k = stueck.karte(conn, szene)
    return "\n".join([
        szenenkarte.karte_text(k, szene, 1),                       # Karte im Chat
        web._szenenkarten_html(web_daten.szenenkarten(conn, 1), 1),  # Karte im CoThinker
        web.textbuch_html(daten, token),                           # Script-Kopf + PDF-Quelle
        web._wb_szenen_verdichtet_html(
            [dict(s, verdichtet=s.get("verdichtet") or {}) for s in daten["szenen"]]),  # Werkbank
        stagescript.baue_nutzertext(conn, 1, szene),               # Prompt-Block
    ])


def test_problem_1_ort_in_p7_aendern_alle_ansichten_ohne_nachzug(conn, padua):
    phasen.setze(conn, 1, 7, "test")
    sid = lege_karte_an(conn, ort="Sala prove", bestaetigt=True)
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Sala prove.", None)
    _vergifte(conn, sid, ort=GIFT)

    assert stueck.setze_ort(conn, 1, szene=1, ort="Sala riunioni").ok

    alles = _alle_ansichten(conn, sid)
    assert alles.count("Sala riunioni") >= 5
    assert GIFT not in alles


def test_problem_1_wer_eine_stelle(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, wer="Anna")
    _vergifte(conn, sid, wer=GIFT)
    stueck.figur_hinzu(conn, 1, name="Chicca", szene=1, rolle="(Cover)")
    alles = _alle_ansichten(conn, sid)
    assert "Chicca (Cover)" in alles and GIFT not in alles


def test_problem_2_jede_mutation_in_jeder_phase(conn):
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2, bestaetigt=True)
    repo.setze_figur(conn, 1, "Anna", "")
    for phase in range(1, 8):
        phasen.setze(conn, 1, phase, "test")
        assert stueck.setze_ort(conn, 1, szene=1, ort=f"Ort {phase}").ok, phase
        assert stueck.figur_hinzu(conn, 1, name=f"Figur {phase}", szene=2).ok, phase
        assert stueck.karte_aendern(conn, 1, szene=1, worum=f"w{phase}").ok, phase
        assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="karte").ok, phase
        assert stueck.reihenfolge_aendern(conn, 1, folge=[2, 1]).ok, phase
        f = stueck.frage_stellen(conn, 1, szene=1, frage=f"Frage {phase}?")
        assert stueck.frage_beantworten(conn, 1, frage_id=f.frage_id, antwort="ja").ok, phase


def test_problem_2_abgenommene_karte_nach_p6_ueber_den_chatweg(conn):
    phasen.setze(conn, 1, 7, "test")
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2)
    szenenkarte.starte_dialog(conn, TG(), E(), 1, 1)
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1


def test_problem_3_prosa_nie_still_umgeschrieben_aber_angeboten(conn):
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Bar.", None)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert repo.hole_szene(conn, sid)["volltext"] == "SCENE 1 -- Bar."
    [v] = repo.offene_veraltet(conn, 1)
    tg = TG()
    assert ks.biete_veraltete(conn, tg, E(), 1) == 1
    assert "1" in tg.gesendet[-1] and "Piazza" in tg.gesendet[-1]


def test_problem_3_veraltet_kommt_aus_der_tabelle_nicht_aus_einem_flag(conn):
    """Rot, wenn jemand statt ``veraltet`` wieder fertig_am/einen Zweitstatus
    als Wahrheit nimmt: das Angebot haengt allein an der veraltet-Zeile."""
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Bar.", None)
    repo.setze_szene_fertig(conn, sid, True)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert repo.hole_szene(conn, sid)["fertig_am"]  # Abnahme bleibt
    assert len(repo.offene_veraltet(conn, 1)) == 1


def test_problem_4_im_chat_beantwortet_ist_geschlossen(conn, padua):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    _vergifte(conn, sid, fragen=[GIFT], punkte=["p", f"[OPEN] {GIFT}"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "Im Loch")
    alles = _alle_ansichten(conn, sid)
    assert "Wo steht Giona?" not in alles
    assert "[OPEN]" not in stueck.karte(conn, repo.hole_szene(conn, sid))["punkte"]
    assert GIFT not in json.dumps(stueck.karte(conn, repo.hole_szene(conn, sid)))
```

Hinweis zu `test_problem_4`: Das Gift steht in `punkte` des **JSON**. `karte_ansicht` übernimmt `punkte` aus dem JSON, also müsste `[OPEN] GIFT…` erscheinen. Deshalb filtert `stueck_sicht.karte_ansicht` `punkte`, die `OFFEN_PUNKT` treffen, **heraus**: Offene Fragen kommen nur aus `offene_frage`. Ergänzung in Task 3 (`karte_ansicht`):

```python
    karte["punkte"] = [p for p in (karte.get("punkte") or [])
                       if not OFFEN_PUNKT.match(str(p))] + [
        punkt_offen.format(frage=f) for f in fragen_vertagt]
```

Falls Task 3 schon committet ist, zieht dieser Task die Zeile dort nach, samt einem Fall in `tests/test_stueck_sicht.py::test_karte_ansicht_ignoriert_struktur_aus_dem_json` (`"punkte": ["p", "[OPEN] GIFT"]` → `["p", "[OPEN] Wann?"]`).

- [ ] **Step 2: Laufen lassen**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_abnahme.py tests/test_stueck_sicht.py`
Expected: alle passed

- [ ] **Step 3: Gegenprobe „rot bei zweiter Spalte" (Nachweis, wird nicht committet)**

Kurz in `interview_theater/stueck_sicht.py` in `karte_ansicht` die Zeile `karte["ort"] = (ort or "").strip()` ersetzen durch `karte["ort"] = (roh.get("ort") or ort or "").strip()`.

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_abnahme.py::test_problem_1_ort_in_p7_aendern_alle_ansichten_ohne_nachzug`
Expected: FAIL (`assert GIFT not in alles`)

Run: `git checkout interview_theater/stueck_sicht.py`
Danach Step 2 erneut ausführen. Expected: grün.

Dieselbe Gegenprobe für `wer` (`karte["wer"] = roh.get("wer") or …`) und `fragen` (`karte["fragen"] = list(roh.get("fragen") or fragen_offen)`): jeweils FAIL, dann zurücksetzen. Die drei FAIL-Ausgaben kommen in die Übergabe (Task 18).

- [ ] **Step 4: Commit**

```bash
git add tests/test_stueckmodell_abnahme.py interview_theater/stueck_sicht.py tests/test_stueck_sicht.py
git commit -m "stueckmodell: Abnahme-Mutationstests Probleme 1-4 (Giftwert in der frueheren Zweitstelle)"
```

---

### Task 17: Migration gegen die Kopie, Ansichtenvergleich, Wiedergabe der Struktur-Wünsche

**Files:**
- Create: `scripts/stueckmodell_vergleich.py`
- Create: `scripts/stueckmodell_wiedergabe.py`
- Create (nicht eingecheckt): `var/stueckmodell/wiedergabe.json`
- Test: `tests/test_stueckmodell_skripte.py` (ergänzen)

**Interfaces:**
- Produces:
  - `scripts.stueckmodell_vergleich.vergleiche(vorher: dict, nachher: dict, konflikte: dict) -> dict`, Form `{"konsistent_gleich": int, "vereinheitlicht": int, "fehler": [str]}`.
  - `scripts.stueckmodell_wiedergabe.spiele(conn, audit: list[dict], plan: list[dict]) -> dict`, Form `{"struktur": int, "nicht_anwendbar": [post_id], "vorher_automatisch": int, "vorher_drin": int, "nachher_korrekt": int, "fehler": [str]}`.
  - `STRUKTUR`-Regel: `ziel` trifft `/karte|rahmen|figur|reihenfolge/i` **oder** `fehlerklasse` enthält `karte` (gemessen am 10.10.2026: 13 von 69).

**Vergleichsregeln (Abnahme „gleich, wo konsistent; EIN Wert, wo widersprüchlich"):**
- Ort je Szene: Die Ansichten `karte_wo`, `werkbank_ort`, `prompt_wo` und (Teilstring) `pdf_meta`.
  - **Vorher konsistent** heißt: alle nicht leeren Werte sind normalisiert gleich. Dann muss nachher derselbe Wert in allen vier stehen.
  - **Vorher widersprüchlich**: Nachher müssen alle vier denselben Wert zeigen, und die Szene muss im Konfliktbericht (`konflikt_ort`) stehen.
- Wer je Szene:
  - Konsistent, wenn die Namensmenge aus `pdf_besetzung` (Werkbank) gleich der Menge der bekannten Namen in `karte_wer` ist und `karte_wer` keinen Rest hat.
  - Nachher: `karte_wer` vorher ⊆ `karte_wer` nachher. Gemeint ist: jedes Stück aus `stueck_sicht.teile_wer` steht normalisiert im neuen Text (kein Textverlust). `werkbank_figuren` ⊇ vorher.
  - Bei Abweichung muss die Szene in `konflikt_wer` stehen.
- Offene Fragen: Die Vereinigung `fragen` + `punkte_offen` vorher ist gleich der Vereinigung nachher. Live-Stand am 10.10.: beide leer, weil das Regie-Audit alles geschlossen hat.

**Wiedergabe-Plan** `var/stueckmodell/wiedergabe.json`: eine Liste von Objekten

```json
{"post_id": 2424, "gruppe": "G1",
 "ausgang": [{"werkzeug": "karte_aendern", "argumente": {"szene": 3, "punkte_weg": ["…"]}}],
 "aufrufe": [{"werkzeug": "karte_aendern", "argumente": {"szene": 3, "punkte_hinzu": ["…"]}}],
 "erwartet": [{"ansicht": "karte", "szene": 3, "enthaelt": "…"},
              {"ansicht": "veraltet", "szene": 3}]}
```

- `ausgang` stellt den Stand **vor** dem Wunsch wieder her. Die Kopie trägt schon den Endstand nach den Robo-Patches.
- `aufrufe` ist der Wunsch als Werkzeugaufruf.
- `erwartet` prüft Ansichten: `karte`, `pdf`, `werkbank` (Teilstring), `veraltet` (offener Vermerk der Szene), `frage_offen`/`frage_zu`, `speichern_gesperrt`.
- `gruppe` → `chat_id` über `gruppe.bot_name` (`padua-gruppe1..3`).
- Verkettete Fragen (#5 → #6): Der Schritt in #5 trägt `"merke_frage": "giona"`. Der Schritt in #6 nennt in `argumente` `"frage_ref": "giona"` statt `frage_id`. Die Erwartung `frage_offen`/`frage_zu` nennt `"frage": "giona"`. `spiele` löst das auf.
- Falls `wechsle_phase` im Test weitere Abhängigkeiten anfasst (`schliesse_offenes_interview_vor_phasenwechsel`, `phasen_summary.starte_wenn_aktiv`), werden diese im Test per `monkeypatch` stillgelegt, wie in `tests/test_befehle_phasenwechsel_interview.py`.
- Konkrete Strings übernimmt die Umsetzung **wörtlich** aus `p7audit.json` (`beleg`/`nachzug_vorschlag`) bzw. aus der Kopie. Klarnamen bleiben in `var/`, nichts davon wird eingecheckt.

Die 13 Struktur-Einträge (gemessen 10.10.2026, `p7audit.json`) und ihr Werkzeugaufruf:

| # | post_id | Gruppe/Szene | Status vorher | Robo-Handarbeit laut `beleg` | Werkzeug(e) | erwartet |
|---|---|---|---|---|---|---|
| 1 | 2402 | G1 S1–3 | DRIN | ja („Robo-Patch 2523") | `setze_rahmen` (Rahmentext der Kopie), `setze_ort` S1–3 (Ort aus Karte S1 der Kopie); `ausgang`: `setze_ort` S1–3 = „Sala prove" | Ort in karte/pdf/werkbank S1–3; `veraltet` je Szene mit Text |
| 2 | 2412 | G1 S1–3 | DRIN | nein | dieselben Aufrufe wie #1 (Wiederholung) | wie #1, **keine** zweite Veraltet-Zeile je Szene |
| 3 | 2420 | G1 S3 | DRIN | nein | `karte_aendern` S3 `punkte_hinzu` (Kreis/Hände-Punkt aus `beleg`); `ausgang`: `punkte_weg` desselben | karte S3 enthält den Punkt |
| 4 | 2424 | G1 S3 | TEILWEISE | — | `karte_aendern` S3 `punkte_hinzu=[nachzug_vorschlag]` | karte S3 enthält; `veraltet` S3 |
| 5 | 2439 | G1 S3 | TEILWEISE | — | `frage_stellen` S3 (Position laut `nachzug_vorschlag` „da confermare") | `frage_offen` S3; `speichern_gesperrt` S3 |
| 6 | 2440 | G1 S3 | TEILWEISE | — | `frage_beantworten` (id aus #5, Antwort laut `beleg` „bleibt im Loch") | `frage_zu`; karte S3 ohne Frage; `veraltet` S3 |
| 7 | 2534 | G2 S1,2,3,5 | DRIN | ja („per Robo nachgezogen") | `figur_hinzu` je Szene mit Coverrolle als `rolle` | wer mit Rolle in karte/pdf S1,2,3,5; `veraltet` kopf (G2 hat `stage_kopf`) |
| 8 | 2563 | G2 S4 | DRIN | ja („Robo, journal 403") | `karte_aendern` S4 `punkte_hinzu` (Sicherheitswort-Punkt); `ausgang`: `punkte_weg` | karte S4 enthält |
| 9 | 2594 | G2 S3,4 | TEILWEISE | — | `karte_aendern` S3 und S4 `punkte_hinzu` („Ordine di arrivo: …" aus `beleg`) | karte S3/S4 enthält; `veraltet` S3, S4 |
| 10 | (null) | G2 S3,5 | WIDERSPRUCH | — | `pruefe_szene` S3 | `veraltet` S3 mit Grund „saresti l'ultimo" (Kartentreue) |
| 11 | 2314 | G3 | DRIN | — | **nicht anwendbar**: Phasenwechsel, `ziel` irreführend „Rahmen" | zählt in `nicht_anwendbar` |
| 12 | 2318 | G3 S5 | TEILWEISE | — | `karte_aendern` S5 `punkte_hinzu=["OBBLIGATORIO: Do you want to know how events will affect you?"]` | `veraltet` S5 mit „Pflichtpunkt fehlt" (Kartentreue) |
| 13 | 2572 | G3 S4 | TEILWEISE | — | `figur_hinzu` je fehlende „Voce N" in S4; `karte_aendern` S4 `punkte` laut `nachzug_vorschlag` | werkbank S4 = 5 Stimmen; karte S4 wer nennt alle 5 |

**Zahlen, die die Umsetzung nennen muss** (Formel im Skript, nicht von Hand):
- Struktur = 13, davon anwendbar 12.
- `vorher_drin` = DRIN unter den anwendbaren. Gemessen 10.10.: 5 (#1, #2, #3, #7, #8).
- `vorher_automatisch` = DRIN ohne „Robo" im `beleg`. Gemessen: 2 (#2, #3).
- `nachher_korrekt` = Einträge, deren `erwartet` vollständig erfüllt ist. Ziel: 12 von 12.

- [ ] **Step 1: Failing tests** (anhängen an `tests/test_stueckmodell_skripte.py`)

```python
def test_struktur_regel_und_zaehlung():
    from scripts import stueckmodell_wiedergabe as w

    audit = [
        {"post_id": 1, "ziel": "Karte", "fehlerklasse": None, "status": "DRIN", "beleg": "x"},
        {"post_id": 2, "ziel": "Script", "fehlerklasse": "Karte nicht nachgezogen", "status": "TEILWEISE", "beleg": ""},
        {"post_id": 3, "ziel": "nur Antwort", "fehlerklasse": None, "status": "DRIN", "beleg": ""},
        {"post_id": 4, "ziel": "Rahmen", "fehlerklasse": None, "status": "DRIN", "beleg": "Robo-Patch"},
    ]
    assert [a["post_id"] for a in w.struktur(audit)] == [1, 2, 4]


def test_vergleich_konsistent_und_vereinheitlicht():
    from scripts import stueckmodell_vergleich as v

    vorher = {"1": {"1": {"karte_wo": "Bar", "werkbank_ort": "Bar", "prompt_wo": "Bar", "pdf_meta": "x · Bar",
                          "karte_wer": "", "pdf_besetzung": "", "werkbank_figuren": [], "fragen": [], "punkte_offen": []},
                    "2": {"karte_wo": "Sala", "werkbank_ort": "room", "prompt_wo": "Sala", "pdf_meta": "Sala",
                          "karte_wer": "", "pdf_besetzung": "", "werkbank_figuren": [], "fragen": [], "punkte_offen": []}}}
    nachher = {"1": {"1": dict(vorher["1"]["1"]),
                     "2": dict(vorher["1"]["2"], werkbank_ort="Sala")}}
    konflikte = {"konflikte": [{"chat_id": 1, "szene": 2, "art": "konflikt_ort"}]}
    r = v.vergleiche(vorher, nachher, konflikte)
    assert (r["konsistent_gleich"], r["vereinheitlicht"], r["fehler"]) == (1, 1, [])
```

- [ ] **Step 2: Rot** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_skripte.py` — Expected: FAIL (Module fehlen)

- [ ] **Step 3: Skripte schreiben**

```python
# scripts/stueckmodell_vergleich.py
"""Ansichten vorher/nachher (Task 0 gegen Task 17), Karte t_fd88600b.

    uv run --extra dev python -m scripts.stueckmodell_vergleich var/stueckmodell/ansichten-vorher.json var/stueckmodell/ansichten-nachher.json var/stueckmodell/padua-migriert.db.konflikte.json
"""

import json
import sys

from interview_theater import stueck_sicht as sicht

_ORT = ("karte_wo", "werkbank_ort", "prompt_wo")


def _orte(f: dict) -> set[str]:
    return {sicht.normalisiert(f.get(k)) for k in _ORT if (f.get(k) or "").strip()}


def vergleiche(vorher: dict, nachher: dict, konflikte: dict) -> dict:
    im_bericht = {(str(k["chat_id"]), str(k["szene"]), k["art"]) for k in konflikte["konflikte"]}
    gleich, einheitlich, fehler = 0, 0, []
    for chat, szenen in vorher.items():
        for nr, f in szenen.items():
            n = nachher.get(chat, {}).get(nr)
            if n is None:
                fehler.append(f"{chat}/{nr}: Szene fehlt nachher")
                continue
            alt, neu = _orte(f), _orte(n)
            if len(neu) > 1:
                fehler.append(f"{chat}/{nr}: nachher mehrere Orte {sorted(neu)}")
                continue
            ort = next(iter(neu), "")
            if ort and ort not in sicht.normalisiert(n.get("pdf_meta")):
                fehler.append(f"{chat}/{nr}: PDF-Kopf zeigt den Ort nicht")
            if len(alt) <= 1:
                if alt != neu and alt:
                    fehler.append(f"{chat}/{nr}: konsistenter Ort veraendert {alt} -> {neu}")
                else:
                    gleich += 1
            elif (chat, nr, "konflikt_ort") in im_bericht:
                einheitlich += 1
            else:
                fehler.append(f"{chat}/{nr}: Widerspruch ohne Berichtszeile")
            neuer_wer = sicht.normalisiert(n.get("karte_wer"))
            for stueck in sicht.teile_wer(f.get("karte_wer")):
                if sicht.normalisiert(stueck) not in neuer_wer:
                    fehler.append(f"{chat}/{nr}: Text verloren in wer: {stueck!r}")
            if not set(f.get("werkbank_figuren") or []) <= set(n.get("werkbank_figuren") or []):
                fehler.append(f"{chat}/{nr}: Figur aus der Werkbank verloren")
            if (sorted(f.get("fragen") or []) + sorted(f.get("punkte_offen") or [])
                    != sorted(n.get("fragen") or []) + sorted(n.get("punkte_offen") or [])):
                fehler.append(f"{chat}/{nr}: offene Fragen veraendert")
    return {"konsistent_gleich": gleich, "vereinheitlicht": einheitlich, "fehler": fehler}


if __name__ == "__main__":
    lade = lambda p: json.load(open(p, encoding="utf-8"))  # noqa: E731
    r = vergleiche(lade(sys.argv[1]), lade(sys.argv[2]), lade(sys.argv[3]))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(1 if r["fehler"] else 0)
```

```python
# scripts/stueckmodell_wiedergabe.py
"""Wiedergabe der Struktur-Wuensche aus p7audit.json gegen die MIGRIERTE
Kopie (Karte t_fd88600b). Jeder Wunsch ist ein Werkzeugaufruf der
Mutations-Schnittstelle -- derselbe Aufruf, den ein spaeterer Agent machte.

    uv run --extra dev python -m scripts.stueckmodell_wiedergabe --db var/stueckmodell/padua-migriert.db --audit /mnt/HC_Volume_106183673/hermes/profiles/birk/var/padua-nacht/p7audit.json --plan var/stueckmodell/wiedergabe.json
"""

import argparse
import json
import os
import re

_STRUKTUR_ZIEL = re.compile(r"karte|rahmen|figur|reihenfolge", re.I)


def struktur(audit: list[dict]) -> list[dict]:
    return [a for a in audit if _STRUKTUR_ZIEL.search(a.get("ziel") or "")
            or "karte" in (a.get("fehlerklasse") or "").lower()]


def _chat_id(conn, gruppe: str) -> int:
    nr = gruppe.strip().upper().lstrip("G")
    return conn.execute("SELECT chat_id FROM gruppe WHERE bot_name = ?",
                        (f"padua-gruppe{nr}",)).fetchone()[0]


def _pruefe(conn, chat_id: int, e: dict, frage_ids: dict) -> str | None:
    from interview_theater import repo, stueck, szenenkarte, web, web_daten

    s = next((z for z in repo.hole_szenen(conn, chat_id)
              if z["nummer"] == e.get("szene") and not z["entfernt_am"]), None)
    art = e["ansicht"]
    if art == "veraltet":
        ok = any(v["szene_id"] == (s["id"] if s else None) and (e.get("grund") or "") in v["grund"]
                 for v in repo.offene_veraltet(conn, chat_id))
        if e.get("szene") is None:
            ok = any(v["ansicht"] == "kopf" for v in repo.offene_veraltet(conn, chat_id))
        return None if ok else f"kein Veraltet-Vermerk {e}"
    if art in ("frage_offen", "frage_zu"):
        f = repo.hole_offene_frage(conn, frage_ids[e["frage"]])
        offen = f["status"] in ("offen", "vertagt")
        return None if offen == (art == "frage_offen") else f"Frage-Status {f['status']}"
    if art == "speichern_gesperrt":
        return None if stueck.karte(conn, s)["fragen"] else "Karte ohne offene Frage"
    token = repo.stelle_web_token_sicher(conn, chat_id)
    daten = web_daten.gruppe_nach_token(conn, token)
    text = {"karte": lambda: szenenkarte.karte_text(stueck.karte(conn, s), s, chat_id),
            "pdf": lambda: web.textbuch_html(daten, token),
            "werkbank": lambda: json.dumps([z for z in daten["szenen"] if z["nummer"] == e.get("szene")],
                                           ensure_ascii=False)}[art]()
    return None if e["enthaelt"] in text else f"{art} S{e.get('szene')} ohne {e['enthaelt']!r}"


def spiele(conn, audit: list[dict], plan: list[dict]) -> dict:
    from interview_theater import stueck

    je_post = {p["post_id"]: p for p in plan}
    eintraege = struktur(audit)
    ergebnis = {"struktur": len(eintraege), "nicht_anwendbar": [], "vorher_drin": 0,
                "vorher_automatisch": 0, "nachher_korrekt": 0, "fehler": []}
    frage_ids: dict[str, int] = {}
    for a in eintraege:
        p = je_post.get(a["post_id"])
        if p is None or p.get("nicht_anwendbar"):
            ergebnis["nicht_anwendbar"].append(a["post_id"])
            continue
        if a["status"] == "DRIN":
            ergebnis["vorher_drin"] += 1
            if "robo" not in (a.get("beleg") or "").lower():
                ergebnis["vorher_automatisch"] += 1
        chat_id = _chat_id(conn, p["gruppe"])
        for schritt in p.get("ausgang", []) + p.get("aufrufe", []):
            argumente = dict(schritt["argumente"])
            if "frage_ref" in argumente:
                argumente["frage_id"] = frage_ids[argumente.pop("frage_ref")]
            r = getattr(stueck, schritt["werkzeug"])(conn, chat_id, quelle="wiedergabe", **argumente)
            if schritt.get("merke_frage"):
                frage_ids[schritt["merke_frage"]] = r.frage_id
            if not r.ok:
                ergebnis["fehler"].append(f"{a['post_id']}: {schritt['werkzeug']} -> {r.fehler}")
        fehler = [f for f in (_pruefe(conn, chat_id, e, frage_ids) for e in p["erwartet"]) if f]
        if fehler:
            ergebnis["fehler"] += [f"{a['post_id']}: {f}" for f in fehler]
        else:
            ergebnis["nachher_korrekt"] += 1
    return ergebnis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--audit", required=True)
    p.add_argument("--plan", required=True)
    a = p.parse_args()
    os.environ.setdefault("IT_WORKSHOP", "padua-2026")
    from interview_theater import db

    conn = db.verbinde(a.db)
    r = spiele(conn, json.load(open(a.audit, encoding="utf-8")),
               json.load(open(a.plan, encoding="utf-8")))
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
```

(Die SQL-Zeile in `_chat_id` steht im Skript, wie in Task 7.)

- [ ] **Step 4: Grün** — Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_stueckmodell_skripte.py` — Expected: alle passed

- [ ] **Step 5: Gegen die Kopie laufen lassen (Nachweis-Kommandos)**

Run: `uv run --extra dev python -m scripts.stueckmodell_migration var/stueckmodell/padua-kopie.db var/stueckmodell/padua-migriert.db`
Expected: eine JSON-Zeile mit Zählern. Nach den Live-Zahlen vom 10.10. heißt das mindestens `"konflikt_ort": 2` (G1 S1, G2 S1: EN gegen IT) und `konflikt_wer` > 0 (9 von 14 Karten weichen heuristisch ab). Die genauen Zahlen gehen in die Übergabe.

Run: `uv run --extra dev python -m scripts.stueckmodell_ansichten --db var/stueckmodell/padua-migriert.db --aus var/stueckmodell/ansichten-nachher.json`
Expected: `14 Szenen aus 3 Gruppen -> …` (dieselbe Zahl wie Task 0)

Run: `uv run --extra dev python -m scripts.stueckmodell_vergleich var/stueckmodell/ansichten-vorher.json var/stueckmodell/ansichten-nachher.json var/stueckmodell/padua-migriert.db.konflikte.json`
Expected: Exit 0, `"fehler": []`, `konsistent_gleich + vereinheitlicht == 14`

Danach `var/stueckmodell/wiedergabe.json` nach der Tabelle oben anlegen (Strings wörtlich aus `p7audit.json` und der Kopie). Die Wiedergabe läuft gegen eine **frische** Kopie der migrierten DB, damit der Vergleich oben unberührt bleibt:

Run: `uv run --extra dev python -m scripts.stueckmodell_kopie var/stueckmodell/padua-migriert.db var/stueckmodell/padua-wiedergabe.db`

Run: `uv run --extra dev python -m scripts.stueckmodell_wiedergabe --db var/stueckmodell/padua-wiedergabe.db --audit /mnt/HC_Volume_106183673/hermes/profiles/birk/var/padua-nacht/p7audit.json --plan var/stueckmodell/wiedergabe.json`
Expected: `"struktur": 13`, `"nicht_anwendbar": [2314]`, `"vorher_drin": 5`, `"vorher_automatisch": 2`, `"nachher_korrekt": 12`, `"fehler": []`. Jede Abweichung wird in der Übergabe mit dem Eintrag genannt, nicht weggerechnet.

- [ ] **Step 6: Commit** (nur Skripte und Tests)

```bash
git add scripts/stueckmodell_vergleich.py scripts/stueckmodell_wiedergabe.py tests/test_stueckmodell_skripte.py
git commit -m "stueckmodell: Ansichtenvergleich vorher/nachher und Wiedergabe der Struktur-Wuensche aus p7audit.json"
```

---

### Task 18: Doku, Prompt-Schnappschuss, volle Suite, Übergabe

**Files:**
- Modify: `AGENTS.md`:
  - Modulkarte, Zeile „Fachlogik" um `stueck.py` · `stueck_sicht.py` ergänzen.
  - Zwei Einzeiler unter „Je Modul ein Satz".
  - Neue Zeile in „Wo man anfängt": „Wo steht eine Tatsache, wer darf sie ändern? → `stueck.WERKZEUGE` → `stueck_sicht.karte_ansicht`".
  - Eine harte Invariante: „**Stückmodell:** Ort/Besetzung/Karte/offene Fragen schreibt nur `stueck.py`; Prosa nie still umschreiben (`veraltet`) → `entscheidungen.md`".
  - Die Zeile `karten_nachzug.py` in „Ohne eigene Zeile" um „(schreibt seit t_fd88600b nur über `stueck`)" ergänzen.
  - Grenze 25.000 Bytes; heute 21.428.
- Modify: `docs/agents/aufbau.md` (Modultabelle: `stueck.py`, `stueck_sicht.py`)
- Modify: `docs/agents/entscheidungen.md` (neuer Abschnitt „Stückmodell (Karte t_fd88600b, Birk 10.10.2026)": Zielbild-Tabelle, Gate-Semantik vorher/nachher, Migrationsregeln „Karte gewinnt beim Ort / Vereinigung bei der Besetzung / Name ohne Figur nur berichten", Werkzeug-Zuschnitt)
- Create: `docs/handoffs/2026-10-xx-stueckmodell.md` (Datum des Umsetzungstags)

Die Übergabe enthält die Zahlen aus Task 0/17, die drei Gegenproben aus Task 16 Step 3 und den Prompt-Diff. Dazu kommen die bewussten Abweichungen:
- die Werkbank-Zeile „Wo · Wer";
- die Ja-Antwort auf einen veralteten Kopf schreibt Szene 1 mit neu.

- [ ] **Step 1: Doku schreiben** (Inhalte wie oben; keine Übergabeprosa in AGENTS.md, Regel „Folgearbeit")

- [ ] **Step 2: Doku-Tests**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_agents_md_groesse.py tests/test_doku_laengen.py tests/test_pruefe_agents_umzug.py tests/test_web_betrieb_doku.py`
Expected: alle passed

- [ ] **Step 3: Prompt-Schnappschuss nachher**

Run: `IT_WORKSHOP=padua-2026 uv run --extra dev python -m scripts.prompt_schnappschuss var/stueckmodell/schnappschuss-nachher.txt`

Run: `diff var/stueckmodell/schnappschuss-vorher.txt var/stueckmodell/schnappschuss-nachher.txt`
Expected: keine Ausgabe (der SYSTEM-Teil bleibt unverändert, denn dieser Plan ändert keine Prompt-Datei). Jede Zeile Diff wird in der Übergabe begründet oder ist ein Fehler.

- [ ] **Step 4: Profilprüfung Padua**

Run: `uv run --extra dev python -m scripts.pruefe_profil padua-2026`
Expected: Exit 0

- [ ] **Step 5: Volle Suite (einmal)**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider`
Expected: `… passed …, 0 failed`. Die Zahl der Tests liegt um die neuen Tests über dem Ausgangsstand (10.032 am 10.10.2026 laut Review). Rote Tests werden einzeln behandelt: echter Fehler → beheben; nur Dortmund → `@pytest.mark.dortmund`. Hartcodierte Altmechanik, die dieser Plan bewusst ändert, wird umgestellt und im Commit genannt.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md docs/agents docs/handoffs tests
git commit -m "stueckmodell: Doku, Uebergabe mit Migrations-, Vergleichs- und Wiedergabezahlen"
```

---

## Offene Entscheidungen für Birk (nicht blockierend, im Plan bewusst konservativ gelöst)

1. **`p5_gate`** (`befehle.py:866`) bleibt eine Sperre. Begründung: Es ist ein Bestätigungsschritt der Übersicht, keine Datenvoraussetzung. Soll auch er zur Warnung werden?
2. **`erkenner._ohne_phasensprung_vor_fixierten_figuren`** (`erkenner.py:2233`) bleibt. Es ist ein Schutz vor fehlgelesenem Chat; der Klick- und `/phase`-Weg ist schon frei. Eine Änderung wäre ein Erkenner-Umbau (Nicht-in-Scope).
3. **Freier Chat beantwortet eine Kartenfrage ohne Klärweg** (Beleg 5/K24): Das bräuchte eine neue Erkenner-Art `frage_beantworten`, und eine Erkenner-Prompt-Änderung gilt nur mit FP = 0 im bezahlten Korpuslauf (AGENTS.md). Hier abgedeckt sind Klärweg, Dialog und Knöpfe. Die Erkenner-Art wäre eine Folgekarte und ist zugleich der natürliche erste Fall für den Prüfweg („Erkenner als Werkzeuge", `t_d99ab13c`).
4. **Ja auf „Kopf passt nicht mehr"** schreibt Szene 1 mit (der Kopf entsteht nur in diesem Lauf). Ein eigener Kopf-Lauf wäre ein neuer Modellaufruf; dafür wird eine eigene Karte vorgeschlagen.
5. **Rücknahme (Undo)** eines Erkennerlaufs stellt `szene.ort`/`szene_figur` her, räumt aber `veraltet`-Vermerke nicht weg. Folge: Es kann ein überflüssiges Ja/Nein-Angebot kommen, aber nie eine stille Änderung.

---

## Self-Review (gegen die Spec, beim Schreiben erledigt)

- **Problem 1** (eine Stelle je Tatsache, Test „Ort in P7 → Werkbank, Karte, Script-Kopf, PDF ohne Nachzug-Skript"): Tasks 3, 9, 10, 12, 13, Abnahme Task 16 `test_problem_1_*`.
- **Problem 2** (Mutations-Schnittstelle in jeder Phase, Gates → Warnungen): Tasks 4–6, Task 15, Abnahme `test_problem_2_*`. Die Gate-Semantik ist vor dem Umbau gelesen und oben referenziert.
- **Problem 3** (veraltet, Prosa nie still, Ja/Nein): Tasks 4–6 (Vermerk), Task 14 (Angebot), Abnahme `test_problem_3_*`.
- **Problem 4** (`frage_beantworten` schließt im Modell): Tasks 6, 11, Abnahme `test_problem_4_*`.
- **Problem 5** (deterministische Prüfungen an der Schnittstelle): Busy-Gate (Task 4), Kartentreue (Tasks 5/6), Endfassungs-Reinigung `[OPEN]` (Tasks 3/5), Zitat nur aus Bestand (Task 5), Diff (`Ergebnis.diff`, Task 5). EN/IT-Trennung und `stagescript.endfassung` bleiben unverändert im Schreibweg, den „Ja, neu schreiben" (Task 14) unverändert nutzt.
- **Abnahme gesamt:** Migration + Konfliktbericht + Ansichtenvergleich (Tasks 0, 7, 8, 17); Wiedergabe mit Zahlen vorher/nachher (Task 17); Mutationstests (Task 16); Suite + Schnappschuss (Task 18).
- **Werkzeug-Zuschnitt:** `tests/test_stueck_schnittstelle.py` (Task 6); `scripts/stueckmodell_wiedergabe.py` ruft die Werkzeuge per Namen auf (Task 17).
- **Typkonsistenz:** `Ergebnis`, `stueck.karte(conn, szene)`, `repo.besetzung` (Felder `figur_id`, `name`, `rolle`, `position`), `karte_klaerung.ids`, `QUELLE_*` sind in den Tasks 2/4/6/11/12/13 einheitlich benannt.

---

## Prämisse geprüft

Frage: Existieren die vier Datenstände aus Beleg 1 (Kernkarte `t_5a439d0d`, Beleg 4; Karte `t_fd88600b`, Problem 1) **im aktuellen Code** (Stand `main` = `e4e9824`, 10.10.2026) und in den Live-Daten, nicht nur in alten Kommentaren?

**Ort einer Szene, vier Stände: bestätigt, mit einer Präzisierung zu `stage_kopf`.**

| Stand | im Code (Datei:Zeile) | geschrieben von | gelesen von | Live (`betrieb/padua.db`, read-only, 10.10.) |
|---|---|---|---|---|
| `szene.ort` | `interview_theater/db.py:695` | `repo.setze_szenenfeld` (`repo.py:3282`, Aufrufer u. a. `entwurf.py:328`, `szene.py:673`, `erkenner.py:1134`), `repo.aktualisiere_karte_und_werkbank` (`repo.py:3145`) | `web_daten.py:570` (`SZENENFELDER`), `szenenkarte.py:165-166` (Kartenprompt), `web.py:2907`, `web.py:4996-5000` (Fallback) | 9 von 14 Szenen haben einen Ort |
| `karte.ort` (JSON in `szene.karte`) | Spalte `db.py:732`, Feld `szenenkarte.py:78` (Schema), `:267` (geschrieben) | `szenenkarte.erzeuge` (`:285`), `karten_nachzug.ziehe_nach` (`karten_nachzug.py:180`) | `szenenkarte.karte_text` (`:306-307`), `web_skript.meta_html` (`web_skript.py:391, 394`), `web._karte_html` (`web.py:4769`) | 14 von 14 Karten. Bei 2 von 9 Szenen mit beiden Werten weicht er ab (G1 S1, G2 S1: EN in `szene.ort`, IT in `karte.ort`) |
| Stage-Script-Text | `szene.volltext` `db.py:702`, `volltext_it` `db.py:752` | `stagescript.schreibe` → `_speichere_text` (`stagescript.py:330, 346-348`) | Script-Tab/PDF `web.py:5025-5048` | Ort steht als Fließtext im Skript (kein Feld) |
| `stage_kopf` | `arbeitsstand.stage_kopf` `db.py:530`, `stage_kopf_it` `db.py:534` | `stagescript.schreibe` (`stagescript.py:328-329`); Auftrag nennt ausdrücklich „Versuchsanordnung (Ziel, **Ort**, Regeln, Abbruch)" (`stagescript.py:909-915`) | `web_daten.py:684-693`, `web.py:5414-5419` → `web_skript.kopf_html` (`web_skript.py:277`); zurück in den Prompt `stagescript.py:128-129` | nur G2 gefüllt (`stage_kopf_it` 2.780 Zeichen) |

**Präzisierung:** `stage_kopf` ist **je Stück**, nicht je Szene. Er trägt den Ort der Versuchsanordnung als Prosa, kein Szenenfeld. Der Plan behandelt ihn deshalb als Prosa (`veraltet` ansicht `kopf`), nicht als Strukturfeld. Ein eigenes Feld `stage_kopf` an der Szene gibt es nicht (`grep stage_kopf`: nur `db.py:530/534` in `arbeitsstand`).

**Figuren, drei Stände: bestätigt.**
- `figur`-Tabelle: `db.py:624`; je Szene `szene_figur` `db.py:1050-1055`.
- `karte.wer`: Freitext im JSON, `szenenkarte.py:79` (Schema) und `:268` (geschrieben); gelesen in `szenenkarte.py:308-309`, `web_skript.py:391`, `web.py:4770`.
- Cast-Zeile, zwei Ausprägungen:
  - die Besetzungszeile im Script-Tab aus `szene_figur`, `web.py:5020-5023` (`_TEXT_BESETZUNG`);
  - die ROLES-Tabelle im Kopf aus `stage_kopf`, `web_skript.py:277-` (`kopf_html`).
- Live: Bei 9 von 14 Karten nennt `karte.wer` andere Namen als `szene_figur` (grobe Heuristik: Komma, „ e ", „ and "). Beispiel G1 S3: `szene_figur` = 3 Figuren, `karte.wer` nennt 4 plus „tutto il pubblico".
- Im **selben** Szenenkopf stehen beide Stände nebeneinander: `meta_html` aus `karte.wer` (`web.py:5016-5017`) und die Besetzung aus `szene_figur` (`web.py:5020-5023`).

**Offene Fragen, drei Orte: im Code bestätigt, live derzeit leer.**
- Die drei Orte: `karte.fragen` (`szenenkarte.py:274`), `[OPEN]`-Punkte in `karte.punkte` (`szenenkarte.py:962-970`, `_PUNKT_OFFEN` `:1132`) und der Klärstand `szene.karte_klaerung` (`db.py:742`).
- Live sind 0 offene Fragen in `karte.fragen`, 0 `[OPEN]`-Punkte und alle `karte_klaerung` leer. Die 21 Fälle aus Beleg 6 hat das Regie-Audit geschlossen.
- Spuren davon stehen nur noch in `karte_verlauf` (`ausloeser`: 19 × `fragen_geklaert`, 2 × `fragen_uebersprungen`, 38 × `aenderung`, 1 × `erstentwurf`).
- Folge für die Abnahme: Die Migration überführt live voraussichtlich **keine** offene Frage. Problem 4 wird über die Abnahmetests (Task 16) und die Wiedergabe (#5/#6, Task 17) nachgewiesen.

**Nachzug als Zweit-Schreiber: bestätigt.**
- `karten_nachzug.ziehe_nach` (`karten_nachzug.py:144-186`) schreibt Karte **und** Werkbank in einer Transaktion über `repo.aktualisiere_karte_und_werkbank` (`repo.py:3126-3166`).
- Aufgerufen wird es im Hintergrund-Thread nach jedem gespeicherten Skripttext (`stagescript.py:350-360`), Profilschalter `[karten] p7_meta_nachziehen` (`workshop/padua-2026/profil.toml:353`).
- Es prüft nicht, ob der gelesene Text noch der aktuelle ist. Anders `_spiegel`, `stagescript.py:376`.

**Gate-Prämisse der Karte (Problem 2), teilweise widerlegt.**
- Die Karte nennt `phasen.voraussetzungen`/`moegliche_naechste`/`naechste_moegliche`/`erneuere_nach_aenderung` als „Phasen-Gates".
- Sie sperren nichts: Ihr eigener Docstring sagt „angeboten …, nie geschaltet" (`phasen.py:375-376`), und `befehle.wechsle_phase` ruft sie nicht (`befehle.py:897-962`).
- Die tatsächlichen Verbote sitzen in `szenenkarte.py:373, 453, 472, 658, 779, 806` (`_TEXT_NICHT_DRAN`) und `stagescript.py:795-814` (`_TEXT_ERST_VORHERIGE`).
- Der Plan baut **diese** zu Warnungen um (Task 15) und lässt die vier `phasen`-Funktionen als Fokus/Vorschlag stehen, wie die Karte es für Fokus und Vorschlag verlangt.

**Padua-Werkbank zeigt keinen Szenenort: gefunden, nicht in der Prämisse.** Die read-only Werkbank (`web.py:3936-4035`, `_wb_szenen_verdichtet_html` `web.py:5146-5173`) zeigt je Szene Titel, Kurzform und Zitate, aber weder Ort noch Besetzung. „Werkbank zeigt den neuen Ort" ist deshalb erst mit Task 10 prüfbar.

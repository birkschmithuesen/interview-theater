# Messung 2 (t_9b2b33cb): Vorbedingungen, Stand 11.10.2026

`main` und `HEAD` stehen beide auf `02acf7dfd96e4f9608ae01eb4d29e2d53a499e74`.

## Entscheidungen

- `ACHSE_B = ja` -- Testsatz aus Messung 1 vorhanden (privat, siehe unten).
- `ACHSE_C = ja` -- Gold-Korpus und B0 gemergt (siehe unten).
- `PROXY_TOOLS = ja` -- Proxy liefert `stop_reason: tool_use`.

## Step 1: Messung 1 gemergt

`git log --oneline --grep=t_0fedafe0 main` (identisch auf HEAD):

```
eb5587d merge: InScribe Messung 1 Erkenner-Baseline (t_0fedafe0)
```

Die Commits zu `t_dd94e894` sind enthalten (70a5a25, e681598, b33d431).
`t_7321edc8` hat keinen eigenen Commit; irrelevant.

## Step 2: Format des Padua-Testsatzes (Achse B)

- Pfad: `betrieb/korpus/en/padua_testsatz.jsonl` (gitignored, E8). Liegt im
  Haupt-Checkout (`/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/korpus/en/`),
  **nicht** im Worktree. Zugriff ueber `IT_PRIVAT_KORPUS` (Vorgabe
  `<Repo>/betrieb/korpus`); im Worktree muss die Variable auf den
  Haupt-Checkout zeigen.
- Format: JSONL, 37 Faelle (ein Fall je Zeile).
- Felder je Fall: `id` (str, z. B. `p01-g1-...`), `arbeitsstand` (dict),
  `nachrichten` (list), `erwartet` (list von Absichten, kann leer sein),
  `notiz` (str), `herkunft` (dict mit `audit_status`, `erkenner_befund`,
  `fehlerklasse`, `gruppe`, `post_id`, `ziel`). Optional `vorlauf` (Text) laut
  `scripts/pruefe_prompts.py` Z. 582.
- Leser: `scripts.pruefe_prompts.lade_korpus(name, ...)`,
  `PRIVATE_KORPUS_DATEIEN = {"padua_testsatz"}`. Bewertung:
  `vergleiche_erkenner(erwartet, geliefert)` (FP/FN/Treffer).
- Aufruf aus Messung 1 (Opus-Pfad, Abo, 0 CHF):

```
set -a; . ./betrieb/padua-gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner --ueber-claude --sprache en \
    --korpus-datei padua_testsatz --bericht
```

- Baseline-Bericht: `docs/messung/2026-10-erkenner-baseline.md`. Beim
  Padua-Testsatz 3/27 Treffer, 29 FP, 24 FN, aber laut Bericht kein scharfes
  Pass/Fail-Gate (Muster A: `text_ueberarbeiten` vs. `stagescript_notiz`
  nicht aus dem Chatverlauf rekonstruierbar). Fuer A/B nur als Vergleich
  zwischen Varianten brauchbar, nicht als absolute Qualitaet.
  Daneben der EN-Korpus `korpus/en/erkenner.jsonl` (103 Faelle, oeffentlich;
  61/63 Treffer, 2 FP, 2 FN; 7 Aufnahmefaelle laufen nie ueber Claude).

## Step 3: Gold-Korpus Zitatauswahl (Achse C)

Merge: `02acf7d merge: InScribe Zitatauswahl Gold-Korpus Padua Fix (t_e906dce3)`;
Inhalt aus `t_4e8a59aa` (3704261, ebe6c8b, f45fcbd, 4d822ac).

- Gold-Korpus: `korpus/zitatauswahl_gold.jsonl` (im Repo, 85 Zeilen, JSONL).
  Traegt **keinen** Wortlaut (`wortlaut`/`fragmente` werden vor dem Schreiben
  entfernt). Die private Quelle `zitatauswahl_quelle.toml` liegt unter
  `IT_PRIVAT_KORPUS` (`betrieb/korpus/`) und wird nur zum Neubau des Golds
  gebraucht, nicht zum Messen.
- Felder je Zeile: `id` (z. B. `G1-1`), `gruppe` (`G1`/`G2`/`G3`),
  `ziel` (`{art: szene|figur, id, nummer, titel}`), `polaritaet`
  (`positiv`/`negativ`), `im_pool` (bool), `thema_ids` (list),
  `verdichtung_thema_id` (int), `aufnahme_id`, `chat_id`, `frage`, `quelle`
  (dict).
- Recall@10 (`scripts/zitatauswahl.py`, `K = 10`): je Ziel eine Rangliste
  von `verdichtung_thema_id` (Staerke absteigend, bei Gleichstand
  Listenposition, jedes Thema einmal). Je Gruppe und gesamt: nur
  `polaritaet == positiv` und `im_pool == True`; Treffer, wenn
  `set(thema_ids) & set(rangliste[:10])` nicht leer; Nenner ist die Zahl dieser
  Stellen mit Rangliste (ohne Rangliste: Zaehler `fehlt`). Dazu
  `negativ_at_k` (verworfene Paare in den Top-10) und `pool_recall`.
  Entscheidungsregel E7 (`entscheide`): Gewinn im Mittel >= 2 Stellen,
  schlechtester Variantenlauf nicht unter bestem Basislauf, keine Gruppe sinkt.
- B0-Baseline: `docs/messung/zitatauswahl/B0.jsonl` (3 Zeilen, je Gruppe;
  Felder `variante`, `lauf`, `gruppe`, `ranglisten`, `maskiert`, `fehler`,
  `dauer_ms`). Erzeugung (0 CHF, kein Modellaufruf, nur lesend):

```
uv run --extra dev python -m scripts.zitatauswahl kopie
uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
```

  (`kopie` macht `VACUUM INTO` von `betrieb/padua.db`; Messung auf der Live-DB
  oder `padua-test` wird abgelehnt.)
- Kosten: B0 und Gold-Pruefung kosten nichts. Ein Neu-Lauf einer
  Modellvariante (B1, Interventionen) ist **nicht** Teil des Skripts; er geht
  ueber den Claude-Proxy (Abo, 0 CHF je Aufruf laut `kosten.CLAUDE_CHF_JE_AUFRUF`)
  und laeuft laut AGENTS.md nie automatisch. Kimi/Infomaniak-Aufrufe fallen
  dabei nicht an, solange die Variante ueber `szene_claude` laeuft.
- Hinweis: Im Worktree fehlt `var/zitatauswahl/padua-kopie.db` und
  `betrieb/padua.db` (Live-DB liegt im Haupt-Checkout). Pfade fuer Task 8
  muessen darauf Ruecksicht nehmen.

## Step 4: Proxy-Probe tools

Kommando wie im Brief ausgefuehrt (`http://127.0.0.1:28764/v1/messages`,
`claude-opus-5-5`). Ausgabe gekuerzt:

```
"content":[{"type":"tool_use","name":"setze_ort","input":{"szene":2,"ort":"Küche"}}],
"stop_reason":"tool_use", "usage":{"input_tokens":438,"output_tokens":74}
```

Erwartung erfuellt: `PROXY_TOOLS = ja`.

# Messung Zitatauswahl InScribe (Padua, Oktober 2026)

Karte `t_2349e9a8` / Umsetzung `t_2f905d2c`. Erzeugt mit `python -m scripts.zitatauswahl bericht --db var/zitatauswahl/padua-kopie.db`; Spec: `docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.

## Kurzfassung

Recall@10 gesamt: B0 7,0/15 · B1 6,0/15 · I-a 9,0/15 · I-b nicht gemessen.

Fix: **keiner** -- keine Intervention erfuellt die Schwelle E7.

## Gold-Korpus

Positiv 16 (im Pool 15), negativ 69. G1: positiv 5, im Pool 5, negativ 27 · G2: positiv 5, im Pool 5, negativ 22 · G3: positiv 6, im Pool 5, negativ 20.

### Format

Datei: `korpus/zitatauswahl_gold.jsonl` -- eine JSON-Zeile je Stelle, UTF-8,
sortiert nach `id`. Leser: `scripts.zitatauswahl.lade_gold(pfad)`.
Treffer-Regel: `scripts.zitatauswahl.trifft(kandidat, gold)`.

Fuer Messung 2: Ranglisten sind `dict[str, list[int]]`, Schluessel
`<gruppe>:<art>:<ziel.id>` (`ziel_schluessel(zeile)`, z. B. `G1:szene:2`), Wert
die Thema-Kennungen in Rangfolge, jedes Thema einmal. Aufruf:
`recall_at_k(ranglisten: dict, gold: list[dict], k: int = 10) -> dict[str, dict]`
(je Gruppe und `gesamt`: `{"treffer", "n", "fehlt"}`) und
`negativ_at_k(ranglisten: dict, gold: list[dict], k: int = 10) -> dict[str, int]`
(verworfene Paare in den Top-k, je Gruppe und `gesamt`).

| Feld | Bedeutung |
|---|---|
| `id` | `G1-1` (positiv, Gruppe-Karte) bzw. `G1-n-0286` (negativ, kleinste `schaerfung.id`) |
| `gruppe` | `G1` / `G2` / `G3` |
| `chat_id` | 7000000000000 / …001 / …002 |
| `polaritaet` | `positiv` (im Stueck, Plakat) / `negativ` (`nein` an diesem Ziel, nie `ja`, nirgends positiv) |
| `ziel` | `{"art": "szene"|"figur", "nummer", "id", "titel"}` -- `id` = `szene.id`/`figur.id` in padua.db |
| `frage` | Interviewfrage laut Plakat (EN, nur positiv) |
| `wortlaut` | Plakatwortlaut, Auslassungen ` … ` (nur positiv) |
| `fragmente` | Teile zwischen den Auslassungen im Originalwortlaut des Transkripts; jedes besteht `zitat.pruefe` (nur positiv) |
| `aufnahme_id` | Interview (Kopf), in dem die Stelle steht |
| `verdichtung_thema_id` | das Thema im Pool (`repo.gepruefte_themen`), sonst `null` |
| `thema_ids` | alle Themen derselben Stelle (auch aus entfernten Verdichtungen) |
| `im_pool` | ob eines davon im Pool der Schaerfung steht |
| `schaerfung_ids` | nur negativ: die `nein`-Zeilen |
| `quelle` | positiv: entities-Commit, Datei, Karte, Label; negativ: Tabelle |

**Recall@10** (Spec E1) gilt **je Ziel**: eine positive Stelle im Pool ist
getroffen, wenn eines ihrer `thema_ids` unter den ersten 10 verschiedenen
Themen der Rangliste IHRES Ziels steht. Sortiert wird wie im Betrieb:
`(-staerke, runde, Reihenfolge des Modells)`. Gemittelt wird mikro, je Gruppe
und gesamt. Fuer Kandidaten ohne Thema-Kennung (Agent) gilt `trifft`: alle
`fragmente` stehen im Kandidatentext.

### Herkunft und Diskrepanzen

Positiv sind nur die Karten der drei Gruppenplakate (hermes-entities `3fa1f46`,
`### cards: quotes`, "Variante A: nur Zitate, die im Stueck landen"):
G1 5, G2 5, G3 6.

- Kommentar 1402 (hermes-dev, t_56f8d856) nennt "G2 8 Stellen". Plakat G2 hat
  5; die Notizzeile "Int. 9, 13, 29, 21, 38" stammt aus einer frueheren
  Fassung. Das Prozessplakat (`01_prozess.md`, "Nicht doppelt zu den
  Gruppenplakaten") illustriert nur und belegt keine Verwendung im Stueck --
  nicht im Korpus.
- Kommentar 1402 nennt "L'unione fa la forza" einen generischen
  Erstvorschlag; das Plakat G2 Karte 2 verwendet die Stelle. Massgeblich ist
  der Plakatstand; 1402 ist nur Quelle der Hypothesen.
- `entfernt_am` ist nicht "verworfen" (G1-4 ist positiv und hat nur
  entfernte Zeilen). Negativ ist nur `nein` ohne `ja` (Spec F7.3).
- Hypothese (d) "nachgeladenes Material nie im Pool" ist fuer den Pool
  widerlegt (Queer-Viertel, lingua del santo stehen geprueft im Pool); es
  stand in der Rangliste zu weit hinten.

Volle Begruendung: `docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.

## Ergebnisse je Gruppe

Recall@10: Mittel/n (min–max ueber Laeufe); Recall@5 = sichtbare Liste; Negativ@10 = verworfene Paare in den Top-10 (Mittel). Fehler = fehlgeschlagene Ziel-Versuche in den Rohzeilen, verworfen = Laeufe mit offenem Fehler (zaehlen nicht fuer E7).

| Gruppe | Variante | Recall@10 | Recall@5 | Negativ@10 | Laeufe | maskiert | Fehler | verworfen |
|---|---|---|---|---|---|---|---|---|
| G1 | B0 | 1/5 | 0,0 | 2,0 | 1 | 0 | 0 | – |
| G1 | B1 | 0,3/5 (0–1) | 0,0 | 2,0 | 3 | 24 | 3 | – |
| G1 | I-a | 3,0/5 (3–3) | 1,5 | 1,0 | 2 | 16 | 11 | – |
| G2 | B0 | 4/5 | 4,0 | 6,0 | 1 | 0 | 0 | – |
| G2 | B1 | 4,0/5 (3–5) | 4,0 | 2,7 | 3 | 24 | 0 | – |
| G2 | I-a | 4,5/5 (4–5) | 4,5 | 3,0 | 2 | 16 | 0 | – |
| G3 | B0 | 2/5 | 2,0 | 4,0 | 1 | 0 | 0 | – |
| G3 | B1 | 1,7/5 (1–2) | 1,7 | 2,0 | 3 | 24 | 0 | – |
| G3 | I-a | 1,5/5 (1–2) | 1,0 | 1,0 | 2 | 16 | 0 | – |
| gesamt | B0 | 7/15 | 6,0 | 12,0 | 1 | 0 | 0 | 0 |
| gesamt | B1 | 6,0/15 (5–7) | 5,7 | 6,7 | 3 | 24 | 3 | 0 |
| gesamt | I-a | 9,0/15 (9–9) | 7,0 | 5,0 | 2 | 16 | 11 | 1 |

Pool-Recall (Obergrenze, Hypothese c): G1 5/5 · G2 5/5 · G3 5/6 · gesamt 15/16.

## Rang jeder Gold-Stelle

Rang des ersten Gold-Themas in der Rangliste des Ziels, je Lauf (`–` = nicht in der Liste, `?` = Fehler).

| Stelle | Ziel | B0 | B1 | I-a | I-b |
|---|---|---|---|---|---|
| G1-1 | Szene 2 | 25 | 33/33/30 | 3/2 |  |
| G1-2 | Szene 2 | 31 | 40/40/33 | 4/6 |  |
| G1-3 | Szene 2 | 8 | 11/11/10 | 26/60 |  |
| G1-4 | Szene 2 | 109 | 27/27/24 | 36/65 |  |
| G1-5 | Szene 2 | 61 | 74/166/66 | 9/10 |  |
| G2-1 | Szene 1 | 1 | –/1/– | –/1 |  |
| G2-2 | Szene 2 | 3 | –/2/3 | 3/1 |  |
| G2-3 | Szene 2 | 1 | 1/4/1 | 1/2 |  |
| G2-4 | Szene 3 | 2 | 5/1/1 | 1/1 |  |
| G2-5 | Szene 4 | 38 | 1/1/1 | 1/1 |  |
| G3-1 | Szene 2 | 5 | 4/16/4 | 15/22 |  |
| G3-2 | Szene 2 | 19 | 15/18/16 | 9/20 |  |
| G3-3 (nicht im Pool) | Szene 3 | – | –/–/– | –/– |  |
| G3-4 | Szene 3 | 36 | 29/24/35 | 14/23 |  |
| G3-5 | Szene 3 | 51 | 42/41/56 | 24/15 |  |
| G3-6 | Szene 5 | 4 | 4/4/4 | 2/1 |  |

## Entscheidungen (E7)

- I-a gegen B1: **nicht uebernommen** -- G3 sinkt (1.67 -> 1.50).
- I-b: nicht gemessen (Datenschutz-Gate nicht freigegeben). Die Sperre `eintraege_mit_frage` bleibt stehen.

## Kommandos zum Nachrechnen

Die Kommandos laufen im Repo-Checkout (Worktree oder Haupt-Checkout). Die
Live-DB liegt im Haupt-Checkout unter `betrieb/padua.db` und wird nur mit
`kopie --quelle <pfad-zur-padua.db>` (read-only, VACUUM INTO) kopiert; alles
andere arbeitet auf `var/zitatauswahl/padua-kopie.db`. `_verbinde` lehnt jede
Datei `padua.db`, jeden Pfad mit Verzeichnis `betrieb` und `padua-test` ab.

```
uv run --extra dev python -m scripts.zitatauswahl kopie --quelle <pfad-zur-padua.db>
uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G1 --prompt docs/messung/zitatauswahl/prompt-I-a.md
uv run --extra dev python -m scripts.zitatauswahl bericht --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py
```

(`neu` je Variante fuer `--lauf 1 2 3` und `--gruppe G1 G2 G3`; Mutationstest:
`test_mutation_*` in `tests/test_zitatauswahl.py`. Rohergebnisse:
`docs/messung/zitatauswahl/*.jsonl`. Kopie und Proxy: Spec E5.)

## Grenzen

- n = 15 Stellen im Pool (G3-3 "Mara Venier" liegt ausserhalb, Hypothese c);
  eine Stelle sind 6,7 Prozentpunkte. Deshalb die Schwelle E7 (mindestens zwei
  Stellen, keine Ueberlappung der Laeufe, keine Gruppe schlechter).
- B0 ist verzerrt: die Gruppen haben aus den sichtbaren Top-5 gewaehlt.
  Verglichen wird nur Neu-Lauf gegen Neu-Lauf.
- Die Kopie zeigt den Stand vom 11.10.2026, nicht den zur Zeit der Schaerfung
  (07./08.10.); Gold-Fragmente im Nicht-Material-Teil sind maskiert (Spalte
  "maskiert", Spec E6).
- Der Pool selbst (ein Beleg je Thema, `verdichter.py`) ist nicht Gegenstand
  dieser Karte.
- Fehler: Die Spalte "Fehler" der Ergebnistabelle zaehlt die fehlgeschlagenen
  Ziel-Versuche in den Rohzeilen (auch spaeter wiederholte), "verworfen" die
  Laeufe, die deshalb nicht in E7 eingehen. Beides ist aus den Rohdaten
  berechnet; `lade_roh` hebt einen Fehler nur durch eine erfolgreiche
  Wiederholung desselben Ziels im selben Lauf auf.
- Timeout bei G1:szene:2 (rund 180 Themen): gueltige Ergebnisse kamen bei B1 aus 3 von 6 Versuchen, bei I-a aus 2 von 13 Versuchen. Die erfolgreichen I-a-Versuche dauerten 172–178 s, also knapp unter dem Betriebs-Timeout von 180 s je Versuch; die Fehlschlaege endeten nach rund 370 s (Versuch plus Wiederholung). Gerade dort liegt der Grossteil des I-a-Gewinns (G1 0,3 -> 3,0).
- Die I-a-Listen sind kuerzer (G1:szene:2: 155–165 Eintraege, B1 187–189), u. a. weil der Kandidat-Prompt den Halbsatz "name all of them, not just the three strongest" streicht (vom Plan vorgegeben) und Staerke 3 auf fuenf Stellen begrenzt. Folgerung: Der G1-Gewinn von I-a ist durch die Auswahl rechtzeitig fertiger Laeufe verzerrt, und I-a liefe im Betrieb an dieser Szene haeufig in den Timeout. Die Entscheidung "nicht uebernommen" bleibt.
- E7-Entscheidung I-a gegen B1, die drei Bedingungen mit Zahlen: (1) Gewinn
  mindestens zwei Stellen: erfuellt, 6,0 -> 9,0 von 15 (+3,0); (2) keine
  Ueberlappung der Laeufe: erfuellt, B1 5–7 gegen I-a 9–9, I-a-Minimum 9
  liegt ueber dem B1-Maximum 7; (3) keine Gruppe schlechter: **verletzt**,
  G3 sinkt von 1,67 auf 1,50 (G1 0,3 -> 3,0; G2 4,0 -> 4,5). I-a wird
  deshalb nicht uebernommen; die Betriebs-Prompts (EN und DE) bleiben
  unveraendert.
- Die Live-DB liegt im Haupt-Checkout unter `betrieb/padua.db`; die Kopie
  entsteht mit `kopie --quelle <pfad-zur-padua.db>` (Kommandos oben).
- I-b: nicht gemessen (Datenschutz-Gate nicht freigegeben).

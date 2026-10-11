# InScribe Zitatauswahl: Gold-Korpus Padua, Recall@10, Fix — Design

Karte `t_2349e9a8` (Plan) → Umsetzung `t_2f905d2c`, Branch `wt/t_2f905d2c`.
Stand der Befunde: 11.10.2026, `betrieb/padua.db` nur `mode=ro` gelesen.
Folgekarte, die den Gold-Korpus wiederverwendet: Messung 2 `t_c0056676` →
`docs/superpowers/plans/2026-10-11-ab-pipeline-vs-tools.md`, Task 0 Step 3 und
Task 8 (Achse C).

## 1. Ziel und Abnahme (wörtlich aus der Karte)

Ziel: Die Zitatauswahl von InScribe an einem Gold-Korpus aus Padua messen und
verbessern. Der Fix `t_56f8d856` (Fragmente < 4 Wörter raus, gemergt 5044e80,
`interview_theater/verdichter.py:120` `MIN_ZITAT_WOERTER = 4`) trifft den Kern
nicht: < 4 Wörter sind die Ausnahme, das Problem sind vollständige, aber
nichtssagende Sätze.

Abnahme:

- Bericht `docs/messung/2026-10-zitatauswahl.md`: Baseline und Nachher je
  Gruppe, Kommandos zum Nachrechnen.
- Fix nur, wenn Recall@10 messbar steigt; Mutationstest: Gold-Korpus
  verfälscht → Lauf rot.
- Der Gold-Korpus ist so abgelegt, dass Messung 2 (A/B Pipeline vs. Agent)
  ihn wiederverwenden kann.
- Volle Suite grün, kein Bot-Neustart, Interviews bleiben hart auf Kimi
  (Phase 3, `erkenne_in_aufnahme`, `verdichter.py` — nicht anfassen).

## 2. Beleg der Kartenprämisse

Fundstelle: hermes-dev `kanban.db`, `task_comments.id = 1402` (Karte
`t_56f8d856`), author `birk`, `created_at 1791606077`:

> „Zusätzliche Evidenz (Robo, 10.10., Plakat-Session 20261008_144309_81b1b295).
> Die Zitatauswahl für die Werkschau-Plakate war ein zweiter, unabhängiger
> Testlauf desselben Mappings. Er zeigt: Der Fix dieser Karte
> (MIN_ZITAT_WOERTER=4) erfasst den Kern des Problems nicht.
> 1. Fragmente unter 4 Wörtern sind die Ausnahme (Tabelle Gruppe/Themen/Median
>    Wörter/<4 Wörter/<8 Wörter: G1 303/22/3/22 · G2 132/25,5/2/12 ·
>    G3 217/19/0/22).
> 2. Erste Vorschläge waren generisch ("Casa non sono le mura...",
>    "L'unione fa la forza", "Erano cadute le torri"); Auswahlkriterien
>    "kurz, stark, PII-sicher" bevorzugen Allgemeinplätze.
> 3. Frage-Kontext fehlt: `verdichtung_thema` hat nur `thema`, `kurz`,
>    `beleg_zitat`, keine Interviewfrage.
> 4. Viele der im Stück verwendeten Zitate liegen außerhalb des Mappings
>    (G1 5/5 in Verdichtung, 1 nie übernommen; G2 2/8 Stellen gar nicht in
>    verdichtung_thema; G3 3/6 nicht in verdichtung_thema, plus P6/7
>    nachgeladenes Material — Queer-Viertel, Gefängnis — nie im Pool des
>    Mappings).
> 5. Die Menge erdrückt die Auswahl (vorgeschlagen/übernommen: G1 186/70,
>    G2 61/9, G3 157/25). Ordnung nach Themen-Passung, nicht Ausdruckskraft.
>
> Hypothesen: (a) Ranking misst Passung, nicht Prägnanz/Überraschung ·
> (b) beleg_zitat ohne Frage gespeichert · (c) ein Beleg pro Thema wird zum
> einzigen Pool, Rest geht verloren · (d) nachgeladenes Material landet nie im
> Pool. Messbar: Top-10 des Mappings gegen die vom Stück tatsächlich
> verwendeten Stellen (Recall)."

## 3. Geprüfte Fakten (11.10.2026, `betrieb/padua.db`, `mode=ro`)

Gruppen: G1 = `7000000000000` (`padua-gruppe1`), G2 = `7000000000001`,
G3 = `7000000000002`.

**F1 — < 4 Wörter sind die Ausnahme** (Auftraggeber nachgemessen, bestätigt
Kommentar 1402): G1 303 Themen, Median 21 Wörter, 3 unter 4, 22 unter 8 · G2
132, Median 25,5, 2 unter 4, 12 unter 8 · G3 217, Median 19, 0 unter 4, 22–25
unter 8. `MIN_ZITAT_WOERTER = 4` entfernt höchstens 0–3 Fälle je Gruppe.

**F2 — produktive Zitatauswahl ist `schaerfung.py`, nicht `kernzitate.py`.**
`kernzitat` hat 0 Zeilen; `aufruf` hat keine `art='kernzitate'`, aber
`schaerfung_szene_*`/`schaerfung_figur_*` (G1 9, G2 20, G3 11 Aufrufe, alle
`claude-opus-5`, 0 CHF über den Proxy). Alles Folgende richtet sich auf
`schaerfung.py`.

**F3 — `schaerfung` in Zahlen** (je Gruppe: distinct Themen vorgeschlagen /
übernommen · `ja` / `nein` / `NULL` · `entfernt_am` gesetzt · Zeilen ·
Ziele · höchste Runde):
G1 186/70 · 68/27/237 · 253 · 332 · 7 · 1 —
G2 61/9 · 9/25/200 · 225 · 234 · 10 · 1 —
G3 157/25 · 25/21/281 · 127 · 327 · 6 · 2.
Pool (`repo.gepruefte_themen`): G1 227, G2 106, G3 168.

**F4 — die Rangfolge hat drei Stufen und sonst nur die Reihenfolge des
Modells.** `staerke` ∈ {2,3} wird gespeichert (`STAERKE_MIN = 2`).
`offene_stellen` (`schaerfung.py:858`) und `web_daten.schaerfungsliste`
sortieren `(-staerke, runde, id)`. `lege_schaerfung_an` legt die Zuordnungen
eines Ziels in der Ausgabereihenfolge des Modells an, also ist `id` innerhalb
einer Stärke und Runde **die Reihenfolge des Modells**. Sichtbar sind je Ziel
höchstens `SCHAERFUNGSLISTE_JE_ZIEL = 5` offene Einträge
(`web_daten.py:1757`).

**F5 — der Prompt verlangt Menge.** `sprachen/en/prompts/schaerfung.md`,
Regel 2: „Name ALL numbers that contribute something concrete — even if there
are many, name all of them, not just the three strongest." Über die
Reihenfolge sagt er nichts.

**F6 — die Plakat-Stellen liegen fast alle im Pool, und die Schärfung hat sie
an der richtigen Szene vorgeschlagen.** Abgleich der 16 Zitate der
Gruppenplakate (§ 4.2) gegen `verdichtung_thema.beleg_zitat` und
`aufnahme.transkript` (lose Prüfung: Anteil getroffener 4-Wort-Fenster):

| Stelle | thema_id(s) | Aufnahme | an Gold-Szene vorgeschlagen | Rang in der Liste der Gold-Szene (letzte Runde) |
|---|---|---|---|---|
| G1-1 Mi manchi | 114 | 283 | ja (`ja`, übernommen) | 25 / 182 |
| G1-2 gran casino | 129 | 300 | ja (`ja`) | 31 / 182 |
| G1-3 filo rosso | 40 | 177 | ja (`ja`) | 8 / 182 |
| G1-4 persone, emozioni | 84 | 248 | ja (Stärke 2, nie entschieden) | 109 / 182 |
| G1-5 profumo di pane | 371 | 323 | ja (`ja`) | 61 / 182 |
| G2-1 Tendenzialmente sì | 186 | 391 | ja (`ja`) | 1 / 7 |
| G2-2 l'unione fa la forza | 188 | 391 | ja (`ja`) | 3 / 7 |
| G2-3 mi fa ansia | 178 | 368 | ja (`ja`) | 1 / 7 |
| G2-4 accettare un rifiuto | 181 | 384 | ja (`ja`) | 2 / 6 |
| G2-5 homosexuales (es) | 204 | 419 | ja (Stärke 2, nie entschieden) | 38 / 53 |
| G3-1 non ero ancora nato | 24, 403 | 139 | ja (`ja`) | 5 / 32 |
| G3-2 bella domanda | 405 | 139 | ja | 19 / 32 |
| G3-3 Mara Venier | — | 550 | **nicht im Pool** | — |
| G3-4 lingua del santo | 586 | 906 | ja (Runde 2) | 36 / 76 |
| G3-5 quartiere queer | 282, 439 | 578 | ja (Runde 2) | 51 / 76 |
| G3-6 piccolo amico | 29, 409 | 147 | ja (Szene 13) | 4 / 27 |

Rang = Position des ersten Gold-Themas in der Liste der Gold-Szene, sortiert
`(-staerke, id)`, Themen dedupliziert. Daraus ergibt sich ein historisches
Recall@10 von G1 1/5, G2 4/5 und G3 2/6. Das ist ein Richtwert aus der
Sondierung; die verbindlichen Zahlen erzeugt das Skript (§ 6, B0).

**Bewertung der Hypothesen aus Kommentar 1402:**

- **(a) Ranking misst Passung, nicht Prägnanz — bestätigt.** G1 Szene 2:
  182 Themen, 85 davon Stärke 3; vier von fünf Plakatstellen stehen auf den
  Rängen 25–109. Bei 85 Gleichständen entscheidet die Reihenfolge des
  Modells, und die verlangt der Prompt nicht (F5).
- **(b) Frage fehlt — teilweise.** In `verdichtung_thema.thema` steht bei G1/G2
  oft schon die Leitfadenfrage („casa: Se casa tua potesse parlare, cosa
  direbbe di…", „fuorisede: Cosa fai per sentirti più a casa…"), bei G3 meist
  eine englische Zusammenfassung („On 11 September 2001 the interviewee had
  not been born yet."). Im Transkript steht die Frage fast immer direkt vor
  der Antwort, manchmal aber mit Klarnamen der Interviewerin („Ciao, sono
  M… e volevo chiederti…", Aufnahme 139). Siehe I-b und das
  Datenschutz-Gate.
- **(c) ein Beleg je Thema — eine Grenze, aber nicht der Hebel.** Nur
  1 von 16 Stellen (G3-3 Venier, Aufnahme 550) liegt außerhalb des Pools. Den
  Pool zu erweitern hieße `verdichter.py` zu ändern, und das ist gesperrt. Gemessen
  wird es als Pool-Recall (Obergrenze), ein Fix entfällt.
- **(d) nachgeladenes Material nie im Pool — für `verdichtung_thema`
  widerlegt.** Queer-Viertel (thema 282, 439) und „lingua del santo"/Maniero
  (544, 586, 587, 588) stehen mit `zitat_geprueft = 1` im Pool, und die
  Schärfung hat sie in Runde 2 an Szene 11 vorgeschlagen (Rang 36 und 51 von
  76). Material fehlt also nicht; es steht in der Rangfolge zu weit hinten.
  Das ist wieder (a).

**F7 — Diskrepanzen und wie der Gold-Korpus sie auflöst**

1. *Kommentar 1402 nennt „G2 8 Stellen".* Das G2-Plakat
   (`03_g2.md`, `### cards: quotes`) hat 5. Die Notizzeile „Zitate neu …
   Int. 9, 13, 29, 21, 38" nennt fünf andere Interviews und passt nicht zu den
   Karten (nur HPV/Spanisch deckt sich), stammt also aus einer früheren
   Fassung. Das Prozessplakat (`01_prozess.md`) führt die IDs „G2 216, 533/631,
   174" ausdrücklich als „Nicht doppelt zu den Gruppenplakaten", also als
   Illustration und nicht als Beleg, dass die Stellen im Stück stehen.
   Zusammengezählt kämen 5 + 3 = 8 heraus; das wäre plausibel, belegt aber keine
   Verwendung im Stück. **Entscheidung:** positiv sind nur die Karten der
   Gruppenplakate (Notiz „Variante A: nur Zitate, die im Stück landen").
   Prozessplakat-IDs gehören nicht in den Korpus.
2. *Kommentar 1402 nennt „L'unione fa la forza" als generischen ersten
   Vorschlag*, das Plakat G2 Karte 2 verwendet die Stelle (Interview 391,
   thema 188, `ja`, übernommen in Szene 2). **Entscheidung:** Der
   Gold-Korpus richtet sich nach dem Plakatstand (entities `3fa1f46`,
   09.10.2026). Kommentar 1402 ist nur Quelle der Hypothesen, keine
   Spezifikation dessen, was positiv oder negativ ist.
3. *Der Auftrag nennt als negativ `entscheidung='nein'` ODER
   `entfernt_am IS NOT NULL`.* `entfernt_am` heißt aber nicht „verworfen": G1-4
   (positiv) hat nur entfernte Zeilen ohne Entscheidung, und G2-1 (thema
   186) hat an Szene 1 erst `nein` (Zeile 83) und dann `ja` (Zeile 629).
   **Entscheidung:** negativ ist ein Paar (Thema, Ziel) mit mindestens einem
   `nein`, ohne `ja` an diesem Ziel, und das Thema ist an keinem Ziel positiv.

## 4. Entscheidungen

### E1 — Recall@10 gilt JE ZIEL, gemittelt je Gruppe (Entscheidung)

`Recall@10(Gruppe) = |{g ∈ Gold⁺(Gruppe), im Pool : Thema(g) ∈ Top10(Ziel(g))}| / |{g ∈ Gold⁺(Gruppe), im Pool}|`

- `Top10(Ziel)` = die ersten 10 **verschiedenen** `verdichtung_thema_id` der
  Liste dieses einen Ziels, sortiert wie im Betrieb: `(-staerke, runde,
  Ausgabereihenfolge des Modells)`.
- Gemittelt wird mikro, also über die Stellen. Ausgewiesen werden G1, G2, G3
  und gesamt. Zusätzlich stehen im Bericht **Recall@5** (was die Gruppe
  sieht, `SCHAERFUNGSLISTE_JE_ZIEL = 5`), **Pool-Recall** (Anteil der
  Gold-Stellen im Pool überhaupt, Obergrenze, Hypothese c) und
  **Negativ@10** (verworfene Paare in den Top-10).

Begründung: Das Mapping läuft je Ziel (`schaerfung._ziele`, ein Aufruf je
Szene oder Figur), und die Gruppe sieht Stellen immer in der Liste einer
Szene oder Figur. Eine Rangfolge über die ganze Gruppe gibt es im Produkt
nicht; bei 85 Gleichständen der Stärke 3 wäre sie in G1 außerdem reiner
Zufall der Einfügereihenfolge. Messung 2 rechnet ohnehin je Ziel
(`pipeline_top10(…, ziel)` im A/B-Plan, Task 8).

### E2 — Positiv: die Karten der drei Gruppenplakate

Quelle: entities-Repo
`entities/artesmobiles/projekte/padua-workshop/deliverables/2026-10-09-plakat-a3/en/content/{02_g1,03_g2,04_g3}.md`,
Abschnitt `### cards: quotes`, Commit `3fa1f46` (09.10.2026 13:26). Das ergibt
16 Stellen (G1 5, G2 5, G3 6), davon 15 im Pool. Das Ziel ist die erste in der
Spalte `label` genannte Szene (`scene N` → `szene.nummer` N der Gruppe). Weil
das entities-Repo nicht in diesem Repo liegt, schreibt der Plan die 16 Karten
als Quelldatei **ins Repo** (`korpus/zitatauswahl_quelle.toml`, Wortlaut, Frage,
Szene, Fundstelle). Der Bau des Korpus liest nur diese Datei und die DB-Kopie.

### E3 — Negativ: Paare mit `nein`, nur als Kennungen

Nach F7.3. Negative tragen **keinen Zitattext**, nur Kennungen
(`verdichtung_thema_id`, `aufnahme_id`, `schaerfung_ids`, Ziel). Der Text wird
bei Bedarf aus der DB-Kopie gelesen. Positive Zitate stehen schon auf den
veröffentlichten Plakaten; die verworfenen nicht. Die vorsichtige Wahl ist
deshalb: kein neuer Interviewtext im Repo. Birk kann das lockern.

### E4 — Ablage und Format (die Schnittstelle zu Messung 2)

- Gold-Korpus: **`korpus/zitatauswahl_gold.jsonl`**, eine Zeile je Stelle,
  UTF-8, `ensure_ascii=False`, sortiert nach `id`.
- Format-Doku: Abschnitt „Gold-Korpus" in
  `docs/messung/2026-10-zitatauswahl.md` (dieser Abschnitt ist die Quelle für
  Task 0 Step 3 des A/B-Plans).
- Leser: `scripts.zitatauswahl.lade_gold(pfad) -> list[dict]` und
  `scripts.zitatauswahl.trifft(kandidat, gold) -> bool`.

Zeile **positiv** (Felder fest):

```json
{"id": "G1-1", "gruppe": "G1", "chat_id": 7000000000000, "polaritaet": "positiv",
 "ziel": {"art": "szene", "nummer": 2, "id": 2, "titel": "Le voci"},
 "frage": "If your home could talk, what would it say about you?",
 "wortlaut": "Mi manchi! Spero che dica questa.",
 "fragmente": ["Mi manchi! Spero che dica questa"],
 "aufnahme_id": 283, "verdichtung_thema_id": 114, "thema_ids": [114], "im_pool": true,
 "quelle": {"repo": "hermes-entities", "commit": "3fa1f46",
            "datei": "…/en/content/02_g1.md", "karte": 1}}
```

Zeile **negativ**:

```json
{"id": "G1-n-0286", "gruppe": "G1", "chat_id": 7000000000000, "polaritaet": "negativ",
 "ziel": {"art": "szene", "nummer": 2, "id": 2, "titel": "Le voci"},
 "aufnahme_id": 70, "verdichtung_thema_id": 3, "thema_ids": [3], "im_pool": true,
 "schaerfung_ids": [286], "quelle": {"tabelle": "schaerfung", "entscheidung": "nein"}}
```

Das Beispiel ist echt: `schaerfung.id = 286`, `nein` an Szene 2, thema 3 an
keinem Ziel positiv. Die `id` eines Negativs ist `<Gruppe>-n-<kleinste
schaerfung_id, 4-stellig>`. Negative gibt es auch an Figuren
(`ziel.art = "figur"`, `nummer` = `null`, `titel` = Name). Negativ@10 zählt
nur an den Gold-Zielen. Für die Felder gilt:

- `gruppe`: `G1`/`G2`/`G3`.
- `ziel.id`: `szene.id` in `padua.db` (stabil, weil jede Kopie aus derselben DB stammt).
- `wortlaut`: Text des Plakats, Auslassungen als ` … `.
- `fragmente`: Teile zwischen den Auslassungen, jedes **wörtlich** im
  Transkript der `aufnahme_id` (`zitat.pruefe`, sonst ist der Korpus ungültig, § 6).
- `verdichtung_thema_id`: das Thema einer **nicht entfernten** Verdichtung;
  `thema_ids` nennt alle (auch Dubletten aus entfernten Verdichtungen).
- `im_pool`: ob eines der `thema_ids` in `repo.gepruefte_themen` steht.

**Treffer-Definition** (für Messung 2 verbindlich, ersetzt die Vorgabe
`trifft` im A/B-Plan, Task 8):
`trifft(k, g)` ist wahr, wenn `k["verdichtung_thema_id"] in g["thema_ids"]`.
Trägt `k` keine Thema-Kennung (Agent-Seite), gilt stattdessen: alle
`g["fragmente"]` stehen in `k["text"]` (`zitat.pruefe`). Recall@10 wie E1.

### E5 — zwei Baselines

- **B0 historisch**: aus den Live-Zeilen von `schaerfung` in der DB-Kopie,
  deterministisch, ohne Modellaufruf, 0 CHF. Je Gold-Ziel zählt die letzte
  Runde, in der dieses Ziel Zeilen hat; entfernte Zeilen zählen mit, weil sie
  zum Zeitpunkt der Runde sichtbar waren. B0 ist verzerrt, weil die Gruppe aus
  den sichtbaren Top-5 gewählt hat. B0 dient zur Einordnung und als Daten für
  den Mutationstest.
- **B1 Neu-Lauf**: der heutige `main`-Code (`_baue_nutzertext_ziel` + Prompt +
  Auswertung `_mappe_ziel`) läuft auf der DB-Kopie für **jedes Gold-Ziel**
  (G1: Szene 2; G2: Szenen 1–4; G3: Szenen 2, 3, 5 → 8 Ziele) direkt über
  `szene_claude.schema` mit `claude-opus-5` (Proxy, Abo, 0 CHF), **ohne
  Rückfall auf gemma/Kimi** (`klm = None`; ein Fehler wird als `fehler`
  notiert, nicht ersetzt). Drei Läufe je Variante, je Lauf und Gruppe ein
  eigener Aufruf des Skripts, Ergebnisse als JSONL angehängt (fortsetzbar).
  Vorher/Nachher wird nur zwischen Neu-Läufen verglichen.

### E6 — Leck-Maskierung im Neu-Lauf

Die Kopie zeigt den Stand vom 11.10.: übernommene Stellen können schon in
Szenenbeschreibung, Festlegungen oder P5-Gespräch stehen und dem Modell die
Antwort verraten. Das Skript setzt den Nutzertext aus denselben Bausteinen
zusammen wie `_baue_nutzertext_ziel` (ein Test zeigt: ohne Maske bitgleich)
und ersetzt im **Nicht-Material-Teil** (Erfundenes, Hintergrund, Ziel) jedes
Gold-Fragment (positiv, alle Gruppen) durch `[…]`. Die Materialliste bleibt
unverändert. Die Zahl der maskierten Stellen steht je Ziel im Bericht.
Basis und Varianten maskieren gleich, deshalb bleibt der Vergleich fair.

### E7 — „messbar steigt" (Entscheidung)

Eine Variante gilt als Fix, wenn **alle** drei Bedingungen gelten (Neu-Läufe,
15 Gold-Stellen im Pool):

1. Mittleres Recall@10 gesamt steigt gegenüber B1 um **mindestens 2 Stellen**
   (≥ 0,133);
2. der schlechteste Lauf der Variante ist ≥ dem besten Lauf von B1;
3. keine Gruppe sinkt im Mittel.

Sonst wird die Variante nicht übernommen. Bei 15 Stellen ist eine einzelne
Stelle (6,7 Prozentpunkte) nicht von der Streuung zwischen Läufen zu trennen.
Die Mindestzahl verhindert, dass Rauschen als Fix durchgeht.

### E8 — Interventionen nacheinander, je eine Hypothese

Kandidat-Prompts liegen zunächst **neben** dem Betrieb
(`docs/messung/zitatauswahl/prompt-<variante>.md`) und werden dem Skript per
`--prompt` übergeben. Der Prompt des Betriebs ändert sich erst, wenn eine
Variante E7 erfüllt.

- **I-a (Hypothese a, nur Prompt):** Die Regel „alle nennen" bleibt (der Pool
  soll vollständig bleiben). Neu sind zwei Regeln: (1) **Reihenfolge**: die
  Stellen nach Bühnenwirkung ordnen, stärkste zuerst; eine eigene, konkrete,
  überraschende Stimme schlägt einen Allgemeinplatz oder ein Sprichwort, auch
  wenn beide passen; (2) **Stärke 3 knapp**: höchstens fünf Stellen je Ziel.
  Am Code ändert sich nichts, weil die Betriebssortierung die Reihenfolge des
  Modells schon als Tiebreak nutzt (F4). Gilt nur für den EN-Prompt (Padua);
  der DE-Prompt bleibt wegen Dortmund unverändert.
- **I-b (Hypothese b, Frage-Kontext):** Die Materialzeile bekommt die
  Interviewfrage, und zwar den letzten Satz mit `?` vor dem Belegzitat im
  Transkript. Er wird deterministisch zur Lesezeit abgeleitet; kein neues
  Feld, kein Eingriff in `verdichter.py`. **Datenschutz-Gate (Birk):** I-b
  schickt erstmals Transkripttext außerhalb des Belegzitats an Opus (USA),
  und Interviewfragen enthalten nachweislich Vornamen (F6, Aufnahme 139).
  I-b wird erst gebaut und gemessen, wenn Birk dem Datenfluss zustimmt.
  Ohne Zustimmung entfällt I-b, und der Bericht vermerkt „I-b: nicht
  gemessen — Datenschutz-Gate".
- I-b setzt auf I-a auf, wenn I-a übernommen wurde, sonst auf B1. Nach jeder
  Variante wird gemessen, bevor die nächste dazukommt.
- **Kein Fix für (c)/(d):** (c) braucht `verdichter.py` (gesperrt), (d) ist
  widerlegt.

### E9 — was unangetastet bleibt

`verdichter.py`, `erkenner.py` (`erkenne_in_aufnahme`), die Phase-3-
Interviewstrecke und ihr Modell (Kimi/Infomaniak), `kernzitate.py`, das
Modell der Schärfung (Opus über den Proxy), die Sortierung in `offene_stellen`
und `schaerfungsliste`, `SCHAERFUNGSLISTE_JE_ZIEL`. Ebenso: kein neuer
Profilschalter, kein Dortmund-Pfad, kein Neustart eines Dienstes.

## 5. Bausteine

| Einheit | Zweck | Abhängigkeiten |
|---|---|---|
| `korpus/zitatauswahl_quelle.toml` (neu) | die 16 Plakatkarten im Wortlaut (Quelle E2) | — |
| `korpus/zitatauswahl_gold.jsonl` (neu, erzeugt, eingecheckt) | Gold-Korpus (E4) | Quelle + DB-Kopie |
| `repo.schaerfungen_historie(conn, chat_id)` (neu, `@_gesperrt`) | alle `schaerfung`-Zeilen samt entfernten, mit `runde`, `entscheidung` | `db` |
| `schaerfung.werte_aus(ergebnis, ziel, nach_nummer)` (neu, aus `_mappe_ziel` herausgelöst, reine Funktion) | Modellausgabe → Zuordnungen, gemeinsam für Betrieb und Messung | `zitat` |
| `scripts/zitatauswahl.py` (neu) | `kopie`, `gold`, `historisch`, `neu`, `bericht`; `lade_gold`, `trifft`, `recall_at_k` | `stueckmodell_kopie.kopiere`, `repo`, `schaerfung`, `szene_claude`, `zitat` |
| `docs/messung/zitatauswahl/*.jsonl` (erzeugt, eingecheckt) | Rohergebnisse je Lauf: nur Kennungen und Ränge, kein Zitattext | — |
| `docs/messung/2026-10-zitatauswahl.md` (erzeugt + Hand) | Bericht und Format-Doku | — |
| `tests/test_zitatauswahl.py` (neu) | Recall, Treffer, Gold-Prüfung, Mutationstest, Bitgleichheit Nutzertext, Datenschutz | conftest `conn`, `einst` |

`scripts/zitatauswahl.py` hat kein eigenes SQL. Kopien liegen unter
`var/zitatauswahl/` (nicht eingecheckt) und entstehen nur über
`stueckmodell_kopie.kopiere` (`VACUUM INTO`, Quelle `mode=ro`). Das Skript
lehnt `padua-test.db` als Quelle ab. Profil: das Skript setzt
`IT_WORKSHOP=padua-2026` per `os.environ.setdefault`, wie
`scripts/stueckmodell_wiedergabe.py:148`.

## 6. Fehlerfälle und „Lauf rot"

- **Gold-Prüfung** (`pruefe_gold(conn, gold) -> list[str]`) bei `gold`,
  `historisch`, `neu` und `bericht`: Jedes Fragment jeder positiven Zeile muss
  im Transkript seiner `aufnahme_id` stehen, `thema_ids` muss existieren und zur
  Gruppe gehören, `ziel.id` muss eine Szene der Gruppe mit dieser `nummer`
  sein. Ein Fehler → Meldung je Zeile, Exit-Code 1.
- **Mutationstest** (deterministisch, ohne Modell, auf einer synthetischen DB
  im Test): (1) Eine positive Stelle wird durch eine erfundene Stelle ersetzt
  (Thema-Kennung und Wortlaut, die es nicht gibt) → `pruefe_gold` meldet sie,
  `main([...])` gibt 1 zurück. (2) Dieselbe Mutation ohne Prüfung → Recall@10
  fällt sichtbar (im Test von 1,0 auf 0,5). (3) Ein Wort im Wortlaut geändert →
  Lauf rot.
- Neu-Lauf: Proxy-Fehler, Zeitüberschreitung oder unlesbares JSON → Zeile mit
  `fehler`, Recall dieses Ziels `None`. Der Bericht zählt Fehler und wertet einen
  Lauf mit Fehler nicht für E7.
- Kein Rückfall auf ein anderes Modell; `klm = None` ist erzwungen, und ein
  Test belegt, dass `llm.LLM` im Neu-Lauf nie aufgerufen wird.

## 7. Datenschutz

- Ins Repo kommen positive Zitate (schon auf den Plakaten veröffentlicht),
  Plakatfragen (von Birk paraphrasiert, englisch) und Kennungen. Nicht ins Repo
  kommen Text verworfener Stellen, Transkriptausschnitte und Klarnamen.
- Rohergebnisse (`docs/messung/zitatauswahl/*.jsonl`) enthalten nur Kennungen,
  Ränge, Zahlen und Fehlertexte.
- Neu-Läufe B1 und I-a schicken an Opus genau das, was der Betrieb am
  07./08.10. schon geschickt hat, nach Maskierung sogar weniger. I-b erweitert
  den Datenfluss → Gate (E8).
- Interviews (Phase 3, `erkenne_in_aufnahme`, `verdichter.py`) bleiben auf
  Kimi. Ein Test belegt, dass `scripts/zitatauswahl.py` keines dieser Module
  aufruft, und die Suite hält die bestehenden Datenschutztests der
  Interviewstrecke.

## 8. Bericht `docs/messung/2026-10-zitatauswahl.md`

1. Kurzfassung: Fix ja/nein, mit Zahlen.
2. Gold-Korpus: Format (E4), Herkunft (E2, E3), Diskrepanzen (F7), Anzahl je
   Gruppe positiv/negativ/im Pool.
3. Tabelle je Gruppe (G1, G2, G3, gesamt) × Variante (B0, B1, I-a, ggf. I-b):
   Recall@10 (Mittel, min–max über Läufe), Recall@5, Pool-Recall, Negativ@10,
   maskierte Stellen, Fehler.
4. Rang jeder Gold-Stelle je Variante (Tabelle wie F6).
5. Entscheidung nach E7 je Intervention.
6. Kommandos zum Nachrechnen (Kopie, Gold, Historisch, Neu-Läufe, Bericht,
   Mutationstest) wörtlich.
7. Grenzen: n = 15; Selektionsverzerrung von B0; Stand der Kopie ≠ Stand zur
   Zeit der Schärfung (gemildert durch E6); Pool-Grenze (c).

## 9. Nicht im Umfang

Agent mit Werkzeugen (Messung 2, `t_c0056676`), Änderungen am Pool
(`verdichter.py`), `kernzitate.py`, Dortmund, neue Chat-Texte (es entsteht
keine Nutzerzeile, daher keine `T`-Einträge), Anzeigegrenze je Ziel.

# Workshop-Profil `padua-2026` — Gerüst

**Stand 06.09.2026: die Struktur steht, die Inhalte fehlen.** Solange in
`profil.toml` die Zeile `geruest = true` steht, startet kein Bot mit diesem
Profil (`bot.main` bricht ab, `scripts/pruefe_profil.py padua-2026` meldet
es). Das ist Absicht: ein halb ausgefülltes Profil ist am Workshoptag
teurer als gar keins.

Angelegt hat es der Umbau vom 06.09.2026, damit man an einem zweiten
Einsatzort sieht, wo was hingehört — nicht als Vorwegnahme des Inhalts.
**Kein Satz hier drin ist von einem Agenten geschrieben worden, und das soll
so bleiben:** ein italienischer Prompt ist ein eigener Text, keine
Übersetzung der deutschen Fassung (Teil C der Analyse).

## Was dieses Profil eigenständig macht

Bisher nur zweierlei:

- `sprache.code = "it"` und `sprache.anrede = "voi"`
- `orte.beispiele` — die Beispielorte, die in Prompts als Beispiel stehen
  (`fermata`, `piazza`, `bar`, `stazione`). Sprache und Ort sind zwei
  getrennte Felder: ein italienisches Profil könnte auch deutsche
  Beispielorte haben, und umgekehrt.

Alles andere ist leer und fällt damit auf das eingebaute Vorgabeprofil
zurück — also auf Dortmund, auf Deutsch. Das ist der Grund, warum
`geruest = true` dasteht.

## Was noch fehlt, in der Reihenfolge des Aufwands

1. **`profil.toml` ausfüllen** — Zielgruppe, Orte, Auführungsort, Konflikt,
   Projektbeschreibung. Ein Nachmittag, wenn die Eckdaten des Workshops
   feststehen.
2. **Die Rahmenblöcke** — `prompts/rahmen.md`, `prompts/rahmen-kurz.md`,
   `prompts/rahmen-knapp.md`. Vorlage: die drei gleichnamigen Dateien unter
   `workshop/dortmund-2026/prompts/`. Neu schreiben, nicht übersetzen.
3. **`formen.toml`** und je Form ein Regelblock unter
   `prompts/formen/<name>.md`. Padua darf andere Formen haben als Dortmund
   (Commedia? Coro?); die Zahl ist nirgends festgeschrieben.
4. **`phasen.toml` und `phasentexte.toml`** — vermutlich nur die Namen und
   Stichwörter neu, nicht die Zahl der Stationen: der Ablauf ist die
   Methode, nicht der Einsatzort.
5. **Die Prompt-Sätze auf Italienisch** — `prompts/system.md`,
   `prompts/szene.md`, `prompts/phasen/*.md` als Dateiersatz. Schätzung aus
   Teil C der Analyse: 1–2 Personentage.
6. **Der Erkenner-Korpus** — `korpus/erkenner.jsonl` mit rund 70
   italienischen Fällen, davon mindestens 28 Negativfälle. Der teure
   Posten (2–3 Tage) und der einzige, der sich **nicht** übersetzen lässt:
   die gemessene Zusicherung „0 Falsch-Positive" gilt für diese Sätze in
   dieser Sprache. `scripts/pruefe_profil.py padua-2026` prüft die
   Mindestzahlen, sobald ein eigener Korpus da ist — vorher prüft es
   nichts, damit ein halbfertiges Padua den Dortmunder Betrieb nicht
   blockiert.

## Was das Profil **nicht** kann, weil es im Kern noch fehlt

Das ist der ehrliche Teil. Diese Dinge liegen am 06.09.2026 noch fest im
Code und wären für einen italienischen Workshop zu bauen:

- **Die Whisper-Sprache** (`stt.py`, `"language": "de"`) liest
  `sprache.code` noch nicht. Ein Parameter, eine halbe Stunde — aber sie
  ist noch nicht gemacht.
- **Die Chat-Texte**: rund 111 `_TEXT_*`-Konstanten in `knoepfe.py`, dazu
  `befehle.py`, `leitfaden.py`, `phasen.MELDUNG`. Sie sind deutsch und
  stehen im Code. Das ist Schritt 7 der Analyse (`texte.yaml`) und
  ausdrücklich noch nicht gebaut; `knoepfe.py` wurde zur selben Zeit
  anderweitig umgebaut, und ein gleichzeitiger Eingriff in dieselben
  Konstanten hätte einen Merge-Konflikt erzeugt, den niemand auflösen will.
- **Die Auftragsmuster** (`ablauf.py`) und die **Anti-Nachplapper-Wortlisten**
  in den Tests sind deutsche Regex bzw. deutsche Namen.
- **Die Simulations-Personas** (`simulation/stimmen/*.md`) schreiben
  deutsch.

Solange das offen ist, wäre ein italienischer Workshop halb deutsch. Deshalb
`geruest = true`.

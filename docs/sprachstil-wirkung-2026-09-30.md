# Wirkungstest Sprachstil (Padua M1, 30.09.2026)

**Frage:** Veraendert `figur.sprachstil` -- in Phase 4 per Knopf gesetzt
(`repo.setze_figur_sprachstil`) -- den Text, den das Szenenmodell schreibt?

**Kurzantwort, getrennt nach Weg:**

| Weg | Urteil | Tragende Zahl (A = mit Stil, B = ohne, n = 3 je Variante) |
|---|---|---|
| (1) Prosa, Phase 6 (Kurzgeschichte) | **wirkt** (ueberwiegend als Uebernahme des Beispiel-Wortschatzes in neue Saetze, selten als Zitat) | Gesamttext-Marker SCHACHTEL 0,36 [0,32-0,40] vs. 0,00 [0,00-0,00], FUELL 0,89 [0,69-1,20] vs. 0,01 [0,00-0,04] je 100 Woerter; in C wandert das Markerprofil mit dem Stil zur anderen Figur |
| (2) Einzelszene direkt, Phase 7 (Feinschliff) | **wirkt nicht** (per Konstruktion) | System- und Nutzertext A/B/C byte-identisch, `diff-szene-A-B.diff` und `diff-szene-A-C.diff` sind 0 Byte |
| (3) Einzelszene indirekt ueber die Prosa-Vorlage | **wirkt kaum** | nach dem Kriterium kommt allein Meryems KNAPP durch (1,02 [0,57-1,64] vs. 0,00 -- ein bis zwei "Egal" je Lauf); Aynur FUELL 5,31 [0,00-8,23] vs. 0,00 ueberlappt, 6 der 19 FUELL-Treffer in A sind eine aus der Vorlage kopierte Zeile; SCHACHTEL verschwindet ganz (0,00 in A und B), Satzlaengen je Figur unveraendert |

Diese Karte misst nur. **Kein Produktcode in `interview_theater/` wurde
geaendert** (E2: "misst nur, streicht nichts").

Zitierter Modelltext steht in seiner Originalschreibung (mit Umlauten und
"ß"); der Rest dieses Berichts ist in ASCII-Umschrift.

---

## 1. Pfadnachweis: wo der Stil ueberhaupt ankommt

Erzeugt mit `python -m scripts.sprachstil_wirkung pfad` aus den echten
Prompt-Bauern, abgelegt unter
[`sprachstil-wirkung-2026-09-30/prompts/`](sprachstil-wirkung-2026-09-30/prompts/).

- **Prosa (Phase 6): der Stil landet im Nutzertext.**
  `interview_theater/kurzgeschichte.py:210-222` (`baue_nutzertext`) haengt den
  Block "So sprechen die Figuren:" mit einer Zeile `- Name: <sprachstil>` je
  Figur mit nicht-leerem Stil an. Der Systemprompt
  (`kurzgeschichte.systemanweisung()`) ist in allen Varianten gleich.
  - [`diff-prosa-A-B.diff`](sprachstil-wirkung-2026-09-30/prompts/diff-prosa-A-B.diff):
    genau dieser Block (4 Zeilen + Leerzeile) faellt in B weg.
  - [`diff-prosa-A-C.diff`](sprachstil-wirkung-2026-09-30/prompts/diff-prosa-A-C.diff):
    die drei Stilzeilen tauschen die Figur, sonst nichts.
- **Einzelszene Feinschliff (Phase 7): der Stil landet nicht.**
  `interview_theater/szene.py` enthaelt das Wort `sprachstil` kein einziges
  Mal (grep: 0 Treffer). `_figuren_text` (`szene.py:979ff`) liest
  `beschreibung`, `sprachprofil` und `zitate` -- andere Felder.
  [`diff-szene-A-B.diff`](sprachstil-wirkung-2026-09-30/prompts/diff-szene-A-B.diff)
  und [`diff-szene-A-C.diff`](sprachstil-wirkung-2026-09-30/prompts/diff-szene-A-C.diff)
  sind leer.
- **Der einzige indirekte Weg:** `szene.baue_nutzertext` ruft
  `_diese_szene_text(..., vorlage=not schreibt_prosa(...))` (`szene.py:1728-1731`),
  in Phase 7 also mit `vorlage=True`; `_diese_szene_text` (`szene.py:1445ff`,
  Vorlage ab Zeile 1462) legt dann `szene.prosa` als bindende Vorlage in den
  Prompt. Was der Stil in der Prosa hinterlassen hat, kann so in den
  Theatertext durchsickern -- das misst Weg (3).
- Sonst liest nur `knoepfe/figuren.py` das Feld (Pruefung "Figur ohne Stil?"
  fuer die naechste Stilfrage) -- kein Prompt.

**Nebenwirkung, nicht gemessen:** `knoepfe/wirkung._wirkung_figur_stil`
(`knoepfe/wirkung.py:797ff`) setzt neben `figur.sprachstil` zusaetzlich
`quelle_aufnahme_id` (Zeile 810), wenn der gewaehlte Stil aus einem Interview
stammt. Daraus entsteht spaeter ein `sprachprofil` -- und das fliesst sehr wohl
in den Einzelszenen-Prompt. Die Stilwahl kann also ueber diesen Umweg den
Theatertext beeinflussen. Unsere erfundenen Stile tragen keine Interviewquelle
(wie der Weg "Eigener Stil"), das Sprachprofil ist in allen Varianten dieselbe
Konstante; dieser Effekt ist hier ausdruecklich **nicht** gemessen.

---

## 2. Methodik

**Aufbau** (`scripts/sprachstil_wirkung.py`, Funktion `baue_db`): je Lauf eine
frische Wegwerf-Datenbank mit demselben erfundenen Arbeitsstand -- Setting
(Gemeinschaftskueche eines Frauenwohnheims, Winter 1971), Geschichte, drei
Figuren (Meryem, Ferzan, Aynur; Namen aus `simulation/interviews/set1/`) mit
festem Sprachprofil und festen Zitaten, drei Szenen. Die fuenf set1-Interviews
sind per `aufnahme.importiere_text` importiert (ohne Verdichter-Aufruf); der
Prosa-Weg sieht dieses Material ohnehin nicht (`szenenfolge._erfundenes`).
Keine Echtdaten, kein `betrieb/`.

**Varianten** -- einziger Unterschied ist `figur.sprachstil`, im Format, das
der Knopf wirklich speichert (`"Titel: Beispielsatz"`):

| Variante | Meryem | Ferzan | Aynur |
|---|---|---|---|
| A | KNAPP | SCHACHTEL | FUELL |
| B | -- | -- | -- |
| C (rotiert) | SCHACHTEL | FUELL | KNAPP |

- KNAPP: `Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter.`
- SCHACHTEL: `Verschachtelt, gelehrt: Wobei man insofern, als das Zurueckgehen de facto gar keine Option ist, prinzipiell sagen muesste, dass der Koffer per se gewissermassen quasi schon ausgepackt ist.`
- FUELL: `Mit Fuellwoertern: Also, weisst du, der Koffer ist halt irgendwie, also sozusagen, der Koffer ist halt noch zu, weisst du.`

**Modell und Weg.** Alle Aufrufe gingen ueber den echten Anbieterweg
`interview_theater.szene_claude.prosa(...)` an den lokalen Anthropic-Proxy
(`http://127.0.0.1:28764/v1/messages`), Modell `claude-opus-5-5`. Das ist das
Padua-Szenenmodell (E9) -- gemessen wird also das Modell, das in Padua die
Kurzgeschichte und die Szenen tatsaechlich schreibt, nicht ein Ersatz. Kein
Infomaniak-Schluessel wurde benutzt; der Proxy laeuft ueber ein Abonnement,
die Laeufe kosten je Aufruf nichts. Seriell, nie parallel.

**Laeufe** (alle `status: ok`, `stop_reason: end_turn`, keine Wiederholung):

- Prosa: A, B, C je n = 3 (9 Laeufe, 81-116 s je Lauf, 12.459-14.758 Zeichen).
- Szene (indirekt): A und B je n = 3 (6 Laeufe, 76-86 s). Vorlage fuer
  `szene-<V>-<i>` ist der erste Abschnitt (`kurzgeschichte.zerlege`) aus
  `prosa-<V>-<i>` -- also eine Prosa, die selbst mit bzw. ohne Stil entstanden
  ist. C entfaellt im Szenenweg: der Prompt ist A/B/C byte-gleich (Weg 2),
  C haette nur die Prosa-Rotation wiederholt.
- Zusammen rund 22 Minuten Modellzeit. Rohtexte:
  [`sprachstil-wirkung-2026-09-30/laeufe/`](sprachstil-wirkung-2026-09-30/laeufe/).

**Masse** (`scripts/sprachstil_masse.py`, reine Funktionen; Auswertung:
`python -m scripts.sprachstil_wirkung auswertung`, Ergebnis
[`auswertung.json`](sprachstil-wirkung-2026-09-30/auswertung.json)):

- Rede je Figur: Prosa ueber `direkte_rede` (Zitat in Anfuehrungszeichen, dem
  naechststehenden Namen im Absatz zugeordnet), Szene ueber `sprecherzeilen`
  (Sprecherkopf `NAME:`, Regieklammern entfernt). Szenentext erst ab der Zeile
  `SZENE <n>`, Prosa ohne Ueberschrift und `Zusammenfassung:`-Zeile.
- Je Figur: Zahl der Reden, mittlere Satzlaenge (Woerter je Satz),
  Markeranteil je Stil (Treffer je 100 Woerter), Wortschatz-Jaccard je
  Figurenpaar; je Lauf die **Zuordnungsquote** (zugeordnete / alle Reden).
- Robuste Zweitmessung ohne Zuordnung: Markeranteil im **ganzen Text**, dazu
  getrennt ab Abschnitt 2 (haelt der Stil, oder steht nur der Beispielsatz in
  Abschnitt 1?).
- Dritte Messung, nur Prosa: jeder Markertreffer im ganzen Text wird dem
  **naechststehenden Figurennamen im Absatz** zugerechnet (absolute Zahl je
  Lauf). Grund: das Modell zeigt einen Stil oft in indirekter Rede ("Sie
  fragt lang, mit Nebensaetzen ... insofern ..."), die in keinem Zitat steht.
- Vor dem Zaehlen wird "ß" zu "ss" (`sprachstil_masse.normalisiere`, wirkt
  in jedem Mass) -- das Modell schreibt "weißt du", die Markerliste "weisst du".
- Im Theatertext zaehlen die Gesamttext-Masse ohne Regieklammern -- "(Sie
  schreibt weiter.)" ist keine Rede.
- Abschreib-Zaehlung (`sprachstil_masse.marker_in_kopie`): wie viele
  Markertreffer stehen in einem Satz, der mit dem Beispielsatz des Stils eine
  Folge von vier Woertern teilt? Summen je Variante in `auswertung.json`,
  Schluessel `summen`.

**Kriterium:** Ein Effekt zaehlt, wenn der Abstand A gegen B groesser ist als
die Spannweite innerhalb der Varianten (Bereiche ueberlappen nicht), und wenn
in C das Markerprofil mit dem **Stil** zur anderen Figur wandert statt bei der
Figur zu bleiben. Bei n = 3 gibt es keine p-Werte; angegeben ist durchgehend
Mittelwert [min-max], die Standardabweichung steht in `auswertung.json`.

---

## 3. Ergebnisse Prosa (Weg 1)

### 3.1 Gesamttext (ohne Zuordnung, je 100 Woerter)

| Mass | A (mit Stil) | B (ohne) | C (rotiert) |
|---|---|---|---|
| Marker KNAPP | 0,15 [0,10-0,18] | 0,05 [0,00-0,09] | 0,21 [0,15-0,29] |
| Marker SCHACHTEL | 0,36 [0,32-0,40] | 0,00 [0,00-0,00] | 0,43 [0,28-0,61] |
| Marker FUELL | 0,89 [0,69-1,20] | 0,01 [0,00-0,04] | 1,21 [0,79-1,52] |
| ... davon ab Abschnitt 2: SCHACHTEL | 0,34 [0,31-0,36] | 0,00 [0,00-0,00] | 0,30 [0,13-0,57] |
| ... davon ab Abschnitt 2: FUELL | 0,81 [0,57-1,21] | 0,02 [0,00-0,06] | 1,26 [0,79-1,72] |
| Satzlaenge Gesamttext | 12,8 [12,2-13,7] | 12,2 [11,6-12,8] | 14,0 [11,8-15,4] |

SCHACHTEL und FUELL: die Bereiche liegen weit auseinander -- in B kommen die
Woerter praktisch nie vor, in A und C in jedem Lauf. Der Effekt haelt auch
ab Abschnitt 2 an, sitzt also nicht nur im ersten Abschnitt. Ob er
Abschreiben ist, zaehlt Abschnitt 6 nach: ueberwiegend nicht -- wohl aber
Uebernahme des Beispiel-Wortschatzes. KNAPP ("egal", "weiter") ist schwach: zwei
Allerweltswoerter, die Bereiche beruehren sich fast (A min 0,10 / B max 0,09).
Die Satzlaenge des Gesamttexts bewegt sich nicht messbar -- sie ist
Erzaehlerprosa, die Figurenrede ist darin ein kleiner Anteil.

### 3.2 Folgt das Profil dem Stil oder der Figur?

Markeranteil des jeweils erwarteten Stils in der **zugeordneten direkten
Rede** der Figur (je 100 Woerter). "A-Stil" = der Stil, den die Figur in A
traegt, "C-Stil" = der in C.

| Figur | Rolle | Stil | A | B | C | folgt dem Stil? | zugeordnete Woerter je Lauf A / B / C |
|---|---|---|---|---|---|---|---|
| Meryem | A-Stil | KNAPP | **12,89** [10,00-16,67] | 0,00 | 0,00 | ja: nur in A | 10-25 / 0-44 / 0-17 |
| Meryem | C-Stil | SCHACHTEL | 0,00 | 0,00 | 0,00 | nicht messbar (s. u.) | 10-25 / 0-44 / 0-17 |
| Ferzan | A-Stil | SCHACHTEL | 1,54 [0,00-4,62] | 0,00 | 0,00 | schwach | 0-98 / 10-56 / 1-19 |
| Ferzan | C-Stil | FUELL | 0,68 [0,00-2,04] | 0,59 [0,00-1,79] | **12,28** [0,00-36,84] | ja, streut stark | 0-98 / 10-56 / 1-19 |
| Aynur | A-Stil | FUELL | **20,36** [0,00-35,00] | 0,00 | 0,00 | ja, streut stark | 0-23 / 3-10 / 2-7 |
| Aynur | C-Stil | KNAPP | 0,00 | 0,00 | **37,30** [28,57-50,00] | ja: nur in C | 0-23 / 3-10 / 2-7 |

Die Anteile beruhen auf sehr wenig Rede: Aynur in C hat je Lauf 2-7
zugeordnete Woerter (37,30 = 1-2 Treffer je Lauf), Ferzan in C 1-19 (die
0,00 in C-2 steht auf einem einzigen Wort). Die 0,00 bei Aynur/A
(prosa-A-1) ist ein Zuordnungsfehler -- Aynur hat dort 0 zugeordnete Woerter,
ihre Fuellwort-Saetze landen ohne Namen oder bei Meryem ("Sie schaut zu
Meryem" steht direkt nach dem Zitat; Meryem FUELL 20,00 in diesem Lauf). Die
Tabelle zeigt die Richtung, nicht die Groesse des Effekts.

Dasselbe ueber die **Markertreffer neben dem Namen** (inkl. indirekter
Rede, absolute Treffer je Lauf):

| Figur | Rolle | Stil | A | B | C |
|---|---|---|---|---|---|
| Meryem | A-Stil | KNAPP | **2,67** [1-4] | 0,33 [0-1] | 1,00 [0-2] |
| Meryem | C-Stil | SCHACHTEL | 1,33 [0-2] | 0,00 | **6,33** [2-12] |
| Ferzan | A-Stil | SCHACHTEL | **3,33** [0-5] | 0,00 | 2,00 [0-3] |
| Ferzan | C-Stil | FUELL | 0,67 [0-2] | 0,33 [0-1] | **5,67** [0-10] |
| Aynur | A-Stil | FUELL | **4,33** [0-7] | 0,00 | 1,00 [0-3] |
| Aynur | C-Stil | KNAPP | 0,33 [0-1] | 0,33 [0-1] | **2,00** [2-2] |

Alle sechs Zeilen haben ihr Maximum in der Variante, in der die Figur genau
diesen Stil traegt. In der Gegenvariante bleibt ein Rest (am deutlichsten
Ferzan SCHACHTEL in C: 2,00 -- Meryems verschachtelte Rede steht oft im
selben Absatz wie Ferzans Name; ebenso wandern FUELL-Treffer zu Meryem: 7 in
A, 11 in C, Summe ueber drei Laeufe). Ohne Namen im Absatz bleiben FUELL 35
von 57 (A) bzw. 43 von 74 (C), SCHACHTEL 9 von 23 (A) Treffern; die Tabelle
deckt also nur einen Teil der Treffer ab. Das Profil folgt dem **Stil**, nicht
der Figur.

**Der verschachtelte Stil erscheint kaum als direkte Rede.** Die Figur mit
SCHACHTEL verliert Zitate: Meryem hat in A im Mittel 6,0 zugeordnete Reden,
in C (SCHACHTEL) 0,33; Ferzan in A (SCHACHTEL) 4,0, in B 8,67. Das Modell
gibt lange, verschachtelte Rede als indirekte Rede im Konjunktiv wieder --
passend zur Prosa-Regel "Direkte Rede nur sparsam" (`prompts/formen/prosa.md`,
Regel 4). Deshalb ist die Zeile "Meryem C-Stil" in der Zitat-Tabelle 0 und in
der Namens-Tabelle 6,33.

**Satzlaenge und Wortschatz je Figur** tragen bei diesen Zitatmengen kein
Urteil: Satzlaenge Meryem 2,4 [1,7-3,6] (A) / 2,3 [0,0-4,0] (B) / 5,7
[0,0-17,0] (C); die Spannweiten ueberlappen sich fast vollstaendig, oft
beruht ein Wert auf einem einzigen Zitat. Jaccard zwischen Figurenpaaren liegt
ueberall zwischen 0,00 und 0,29 -- bei 0-11 Zitaten je Figur ist das Rauschen.
Zuordnungsquote: A 0,62 [0,52-0,78], B 0,66 [0,51-0,88], C 0,46 [0,27-0,68].

---

## 4. Ergebnisse Einzelszene (Wege 2 und 3)

**Weg 2 (direkt)** braucht keinen Lauf: der Prompt ist in A, B und C
byte-identisch, ein direkter Effekt ist ausgeschlossen.

**Weg 3 (indirekt ueber die Vorlage)**, Theatertext, Sprecherzeilen, je 100
Woerter; Zuordnungsquote in allen sechs Laeufen 1,00.

| Mass | A (Vorlage mit Stil) | B (Vorlage ohne) |
|---|---|---|
| Vorlage: Marker KNAPP / SCHACHTEL / FUELL | 0,12 / 0,41 / 1,09 | 0,00 / 0,00 / 0,00 |
| Meryem: KNAPP in ihrer Rede | 1,02 [0,57-1,64] | 0,00 [0,00-0,00] |
| Ferzan: SCHACHTEL in ihrer Rede | 0,00 [0,00-0,00] | 0,00 [0,00-0,00] |
| Aynur: FUELL in ihrer Rede | 5,31 [0,00-8,23] | 0,00 [0,00-0,00] |
| Gesamttext ohne Regieklammern: KNAPP | 0,47 [0,32-0,68] | 0,20 [0,00-0,30] |
| Gesamttext ohne Regieklammern: SCHACHTEL | 0,00 | 0,00 |
| Gesamttext ohne Regieklammern: FUELL | 1,03 [0,28-1,69] | 0,15 [0,00-0,30] |
| Treffer absolut, Summe ueber 3 Laeufe: KNAPP / FUELL | 9 / 19 | 4 / 3 |
| Satzlaenge Meryem | 4,3 [3,8-5,1] | 4,3 [4,2-4,5] |
| Satzlaenge Ferzan | 3,7 [3,1-4,2] | 3,5 [3,0-3,9] |
| Satzlaenge Aynur | 2,8 [2,2-3,1] | 2,4 [2,2-2,6] |
| Jaccard Meryem-Ferzan | 0,26 [0,24-0,30] | 0,22 [0,21-0,24] |

Was durchkommt, sind einzelne Woerter und Saetze aus der Vorlage -- in
szene-A-1 uebernimmt Aynur ihren Fuellwort-Satz aus der Prosa woertlich, in
szene-A-3 gar nicht (0,00). SCHACHTEL verschwindet ganz: die Fremdwoerter
("de facto", "prinzipiell") kommen in keinem der drei A-Laeufe an; Ferzans
lange Rede wird zu Selbstkorrekturen mit kurdischen Einsprengseln -- das ist
ihr **Sprachprofil**, das im Szenen-Prompt steht und offenbar staerker wiegt.
Satzlaenge und Wortschatz-Aehnlichkeit unterscheiden sich nicht ueber die
Streuung hinaus.

Nach dem Kriterium aus Abschnitt 2 kommt allein Meryems KNAPP durch -- ein
bis zwei "Egal" je Lauf (2 / 1 / 2); das ist das "kaum". Der Gesamttext-KNAPP
trennt ebenfalls (0,47 [0,32-0,68] gegen 0,20 [0,00-0,30]), aber aus
demselben Grund: Ferzans "egal" steht in A und B gleich oft (0,55 gegen 0,50
in ihrer Rede). Gesamttext-FUELL ueberlappt knapp (A min 0,28, B max 0,30),
und 6 der 19 FUELL-Treffer in A stehen in einer einzigen, aus der
Prosa-Vorlage kopierten Zeile in szene-A-1 (Satz mit einer Viererfolge aus dem
Beispielsatz). Die Zahlen gelten ohne Regieklammern; mit ihnen zaehlte
"(Sie schreibt weiter.)" als KNAPP-Treffer (in szene-A-3 standen 4 der
damals 7 Treffer in Regieklammern).
Daher: **wirkt kaum**.

---

## 5. Beispiele: derselbe Ausschnitt mit und ohne Stil

Die Laeufe sind unabhaengig (kein gemeinsamer Seed); verglichen wird dieselbe
Stelle der Handlung -- Abschnitt 1, "Der Koffer": Ferzan fragt, warum Meryem
nicht auspackt; Meryem antwortet; Aynur steht am kalten Herd. Originaltext
der Modelle, gekuerzt.

### Beispiel 1 -- Ferzan fragt (Prosa)

**MIT Stil (prosa-A-1, Ferzan = SCHACHTEL):**

> Sie fragt lang, mit Nebensätzen, in denen sie erst einmal klärt, dass sie
> selbstverständlich niemandem vorschreiben wolle, wie man mit seinem Gepäck
> umgeht, dass es aber insofern auffalle, als alle anderen Frauen im Haus ihre
> Sachen längst in den Spinden hätten, und ob es denn prinzipiell einen Grund
> gebe, weshalb man einen Koffer vier Tage lang geschlossen unter einem Bett
> aufbewahre [...]
>
> Meryem steht auf und klopft sich die Knie ab. „Koffer bleibt zu.“

**OHNE Stil (prosa-B-1):**

> „Machst du den nicht auf?“
>
> Meryem richtet die Bettdecke gerade, die schon gerade ist. Sie sagt, sie
> brauche nichts daraus.

**ROTIERT (prosa-C-1, Ferzan = FUELL, Meryem = SCHACHTEL):**

> „Also, weißt du, warum machst du den nicht auf, also, den Koffer, der ist ja
> halt noch zu, weißt du.“
>
> Meryem setzt sich auf die Bettkante und faltet die Hände im Schoß. Sie
> antwortet lange. Man müsse ja, sagt sie, insofern man noch gar nicht wisse,
> ob der Vertrag überhaupt verlängert werde, prinzipiell davon ausgehen, dass
> Auspacken gewissermaßen eine Entscheidung vorwegnehme, die de facto noch gar
> nicht gefallen sei.

Dieselbe Frage, dreimal: in A verschachtelt (Ferzan), in C mit Fuellwoertern
(Ferzan) -- und die Verschachtelung ist mit dem Stil zu Meryem gewandert.

### Beispiel 2 -- Aynur am Herd (Prosa)

| MIT Stil (prosa-A-1, Aynur = FUELL) | OHNE Stil (prosa-B-1) | ROTIERT (prosa-C-1, Aynur = KNAPP) |
|---|---|---|
| Sie sagt: „Also, weißt du, der ist halt, also sozusagen, der ist ja noch zu, weißt du.“ Dann schaut sie auf die Herdplatten. | Sie sagt: „Geht nicht.“ Dann bleibt sie stehen, die Hände über dem kalten Eisen, als würde es gleich doch warm. | (Ferzan:) „Warum stehst du dann da?“ Aynur zuckt mit den Schultern. „Egal.“ |

Die A-Fassung ist fast woertlich der Beispielsatz des Stils (siehe
Grenzen, 6.).

### Beispiel 3 -- dieselbe Stelle als Theatertext (Weg 3)

| MIT Stil in der Vorlage (szene-A-1) | OHNE Stil in der Vorlage (szene-B-1) |
|---|---|
| FERZAN: (sieht nicht vom Heft auf) Ich sag nicht, wie man – also, jede macht mit ihrem Koffer, was sie will. Belê. Das sag ich nicht. Aber oben, die anderen, die haben alles im Spind. [...] Also frag ich. Warum bleibt der zu? | FERZAN: Machst du den nicht auf? |
| MERYEM: Koffer bleibt zu. | MERYEM: (richtet die Bettdecke) Ich brauch nichts daraus. |

Direkt danach in szene-A-1: "AYNUR: Also, weißt du, der ist halt, also
sozusagen, der ist ja noch zu, weißt du." -- in szene-B-1 kommt Aynur an
dieser Stelle nicht zu Wort (ihre erste Replik ist spaeter "Ja. Gleich.").

In szene-A-1 ist der Umweg sichtbar: Meryems und Aynurs Satz stehen woertlich
wie in der Prosa-Vorlage. Ferzans Verschachtelung ueberlebt als Struktur (ein
langer Anlauf), aber ohne ein einziges Stilwort -- dafuer mit "Belê" aus ihrem
Sprachprofil.

---

## 6. Grenzen

- **n = 3 je Variante.** Aussagen nur als Effekt gegen Spannweite; keine
  Signifikanz. Wo Bereiche sich beruehren (KNAPP im Gesamttext, Szene FUELL
  im Gesamttext), ist das Urteil vorsichtig formuliert.
- **Die Prosa-Regel begrenzt die Messflaeche.** `prosa.md` Regel 4 ("Direkte
  Rede nur sparsam") laesst je Lauf nur 8-39 Zitate zu, 0-11 je Figur.
  Satzlaenge und Jaccard je Figur tragen deshalb kein Urteil; die robusten
  Masse sind Gesamttext-Marker und Treffer neben dem Namen.
- **Zuordnungsheuristik.** "Naechster Name im Absatz" irrt, wenn zwei Figuren
  in einem Absatz stehen (Zuordnungsquote Prosa 0,27-0,88). Die Treffer
  neben dem Namen sind dieselbe Heuristik fuer Erzaehlertext.
- **Marker messen Woerter, nicht Stil.** Die Markerlisten sind aus den
  erfundenen Stiltexten abgeleitet; ein Modell, das den Stil ohne diese Woerter
  trifft, wird unterschaetzt, ein Modell, das den Beispielsatz abschreibt,
  ueberschaetzt. Beides kommt vor (Beispiel 2: fast woertliche Uebernahme;
  Beispiel 3: Struktur ohne Wort). Nachgezaehlt (Treffer in einem Satz, der
  mit dem Beispielsatz des Stils eine Folge von vier Woertern teilt):
  SCHACHTEL 0 von 23 (A) bzw. 0 von 26 (C) Treffern, FUELL 6 von 57 bzw. 7
  von 74, KNAPP 0 von 10 bzw. 0 von 13; in der Szene (Weg 3) FUELL 6 von 19,
  alle aus einer Zeile in szene-A-1. "Koffer bleibt zu" steht in einem von
  neun Prosa-Laeufen. Der Effekt ist also ueberwiegend kein Abschreiben ganzer
  Saetze -- wohl aber die Uebernahme des **Wortschatzes** des Beispielsatzes
  (bei FUELL oft als Formel "Also, weisst du …"). Gemessen ist damit "das
  Modell uebernimmt die Stilwoerter in neue Saetze", nicht ein vom Beispiel
  unabhaengiger Sprechstil.
- **Die KNAPP-Markerliste ist duenn.** "egal" und "weiter" sind
  Alltagswoerter; "weiter" ist auch in Erzaehlprosa haeufig ("isst weiter")
  und blaeht KNAPP in allen Varianten gleich auf: alle drei KNAPP-Treffer der
  Prosa in B sind "weiter", in A und C sind es 14 von 23 Treffern. Im
  Theatertext sagt Ferzan auch ohne Stil "egal" (alle vier B-Treffer). Die Liste ist
  bewusst nicht nachtraeglich geaendert; KNAPP-Urteile sind entsprechend
  vorsichtig.
- **Ein fester Arbeitsstand**, drei extreme, erfundene Stile. Echte Stile aus
  Interviews sind leiser; der Effekt dort ist eher kleiner.
- **Interviews sind importiert, aber der Prosa-Weg sieht kein Material**
  (`szenenfolge._erfundenes`); im Szenenweg fehlt mangels Verdichtung der
  Kernpaket-Block -- fuer A und B gleich.
- **Nebenwirkung `quelle_aufnahme_id` -> `sprachprofil`** (Abschnitt 1) nicht
  gemessen.
- Ein Modell (`claude-opus-5-5`); andere Szenenmodelle nicht geprueft.

---

## 7. Was die Zahlen hergeben (Empfehlung)

Diese Karte aendert nichts. Was die Zahlen tragen:

- Die Stilwahl in Phase 4 **wirkt in der Kurzgeschichte (Phase 6)** -- und
  zwar figurengenau, das Profil wandert mit dem Stil.
- Im **Feinschliff (Phase 7)** kommt die Stilwahl nur als Rest ueber die
  Prosa-Vorlage an, einzelne Saetze statt eines Sprechstils; bestimmend ist
  dort das Sprachprofil. Wer will, dass der gewaehlte Stil den Theatertext
  praegt, muesste `figur.sprachstil` in den Szenen-Prompt (`szene._figuren_text`)
  nehmen -- das ist eine Produktentscheidung, keine Folgerung dieser Messung,
  und gehoert vorher gegen das Sprachprofil abgewogen (zwei Stimmangaben je
  Figur koennen sich widersprechen).
- Der Beispielsatz des Stils wird selten woertlich uebernommen (FUELL 6 von
  57 bzw. 7 von 74 Treffern, "Koffer bleibt zu" in einem von neun Laeufen),
  sein **Wortschatz** dagegen durchgehend -- und wo er woertlich kommt, samt
  seinem Inhalt (hier: dem Koffer). Stilbeispiele sollten deshalb inhaltlich
  neutral oder zur Geschichte passend sein, und ein Stil wirkt nur so breit
  wie die Woerter, die sein Beispiel vorgibt.

---

## 8. Wie reproduzieren

Aus dem Repository-Wurzelverzeichnis, mit Python 3.11:

```
python -m scripts.sprachstil_wirkung pfad            # Prompts + Diffs, kein Netz
python -m scripts.sprachstil_wirkung lauf --pfad prosa --n 3   # echte Aufrufe, seriell
python -m scripts.sprachstil_wirkung lauf --pfad szene --n 3   # braucht die Prosa-Laeufe
python -m scripts.sprachstil_wirkung auswertung      # auswertung.json + Tabellen, kein Netz
```

`lauf` braucht den Anthropic-Proxy unter `http://127.0.0.1:28764/v1/messages`
und ueberspringt vorhandene erfolgreiche Laeufe. **Kein Test, laeuft nie
automatisch.** Die Masse sind in `tests/test_sprachstil_masse.py` offline
getestet.

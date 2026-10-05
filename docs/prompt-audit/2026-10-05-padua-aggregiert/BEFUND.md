# Padua Prompt-Check B: aggregierte Session-Erkenntnisse

Karte t_97f605c7, 05.10.2026 ~03:00–04:00 Uhr. Prueft, was aus drei
Gespraechsstraengen — Phase 1 Hintergrund-Diskussion, Phase 3 Interviews,
Phase 4 Brainstorm — in Folgeprompts landet, wenn eine Gruppe den jeweiligen
Strang nicht nur einmal, sondern mehrfach durchlaeuft (5 Sessions je Strang).

**Werkzeuge dieser Karte** (neu angelegt, committet in diesem Branch):

- `scripts/fixture_padua_aggregiert.py` — fuenf Sessions je Strang auf je
  einem `chat_id`, inklusive einer "Honeypot-Fabrikation": in genau einer
  Session je Strang steckt ein erfundener Name (`"Dorotea"` / `"Mehmet"` /
  `"Rosaria"`), der in keinem Transkript vorkommt, aber in dem unverifizierten
  Freitextfeld (Verdichtungstext / `zusammenfassung` / Buehnenkarte) steht.
  Tests: `tests/test_fixture_padua_aggregiert.py` (16 gruen).
- `scripts/pruefe_padua_aggregiert.py` — misst Treue (mechanische
  Wortueberlappung + `zitat.pruefe`), Kumulation, Platz im Prompt
  (`kontext.baue(..., protokoll=...)`) und Nutzung (Grep gegen die Prompt-
  Dateien). Tests: `tests/test_pruefe_padua_aggregiert.py` (17 gruen).
  Voller Berichtslauf: `.superpowers/sdd/task-2-berichtsausgabe.txt`
  (nicht committet, `.superpowers/` ist `.gitignore`t — Zahlen unten sind
  woertlich daraus uebernommen).
- Ein Klasse-A-Fix ist bereits angewandt (Commit `1a1bb40`, siehe unten).

Mechanische Treue-Pruefung statt Live-Modellurteil (Zeitbox eingehalten):
die drei Honeypots wurden mit einer einfachen, getesteten
Wortueberlappungs-Heuristik gefunden, kein zusaetzlicher bezahlter
LLM-Judge-Lauf war noetig oder wurde durchgefuehrt.

---

## P1 — Hintergrund-Diskussion (Phase 1)

### Fundstelle

`interview_theater/repo.py:2182` (`merke_diskussion_verdichtung`):

> "Haelt die EINE Verdichtung der Hintergrund-Diskussion fest ... genau eine
> Zeile je Gruppe (`UNIQUE (chat_id)`, anders als `buehnenkarte`): ein
> zweiter Lauf ersetzt die Zeile, statt eine zweite anzuhaengen."

`interview_theater/begriffsboard.py:648` (`schreibe_detail`):

> "D7: je gespeichertem Begriff die Boardzeile nach
> `arbeitsstand.begriffe_detail`."

— liest dabei nur `repo.letztes_begriffsboard` (die juengste Zeile), obwohl
`repo.lege_begriffsboard_an` (`repo.py:2214`, "Haengt einen Stand des
Begriffsboards an") bei jedem Lauf eine NEUE Zeile anhaengt.

`interview_theater/kontext.py:835` (`_baue_diskussion_block`) vs. `:861`
(`_baue_begriffe_detail`): der Diskussionsblock hat **keinen** Phasenfilter
("Datengetrieben wie jeder Block ... die Gating-Entscheidung liegt damit
allein in den Daten"), der Begriffe-Detail-Block dagegen genau einen
(`if phase != 2 and phase < 4: return ""`, Kommentar: "Nicht in Phase 3: dort
wird interviewt").

### Treue-Befund

Mechanisch verifiziert (`treue_wortueberlappung`, drei von fuenf Sessions
sauber, eine mit absichtlicher Fabrikation, eine mit einem echten Grenzfund
— siehe unten):

> Session 3: `kandidaten=['Belonging', 'Dorotea'] verdaechtig=['Dorotea']`
> (Honeypot gefunden) — "Dorotea, who joined only for this part of the
> conversation, added that belonging starts with whoever opens the door for
> you — a detail nobody else recorded hearing." steht im Verdichtungstext,
> **"Dorotea" kommt in keinem der bis dahin gesammelten Diskussions-
> Transkripte vor.**

Die vier echten, woertlichen Zitate in den anderen vier Sessions bestehen
alle `zitat.pruefe` (`bestanden: True` in allen `quote_pruefungen`). Der
Mechanismus, der diese Zitate schuetzt, existiert also und funktioniert.
**Was er nicht schuetzt:** der Rest des Fliesstexts. `diskussion._gefiltert`
(`interview_theater/diskussion.py:73`) verwirft eine Zeile nur, wenn sie ein
`"..."`-Zitat **enthaelt**, das nicht besteht:

> "Eine Zeile ohne jedes Zitat bleibt unangetastet stehen — es gibt hier
> nichts zu verifizieren, und nichts, was dagegen spraeche." (Zeile 83–84)

Genau diese Luecke hat die Fixture ausgenutzt: der erfundene Nebensatz steht
**ohne** Anfuehrungszeichen neben einem echten Zitat in derselben Zeile und
ueberlebt deshalb den bestehenden Filter unverandert. Das ist keine
hypothetische Schwaeche — sie ist im Code selbst als bewusste
Nicht-Entscheidung dokumentiert ("nichts, was dagegen spraeche"), nur nie an
einem konkreten Fall durchgespielt worden.

### Kumulations-Tabelle

| Session | Verdichtungstext (Zeichen) | Dublette? | Begriffsboard-Zeilen (kumulativ) | `begriffe_detail` zeigt |
|---|---|---|---|---|
| 1 | 208 | nein | 1 | nur Stand nach Session 1 |
| 2 | 196 | nein | 2 | nur Stand nach Session 2 |
| 3 | 273 (inkl. Fabrikation) | nein | 3 | nur Stand nach Session 3 |
| 5 | 170 | nein | 5 | **nur** Stand nach Session 5 |

`diskussion_verdichtung`-Tabelle nach 5 Sessions: **1 Zeile** (ersetzt).
`repo.diskussion_verdichtung_text(conn, chat_id) == sessions[-1]["verdichtung_text"]`,
der Text von Session 1 ist nach Session 5 **unwiederbringlich weg** — nicht
nur aus dem Prompt, sondern aus der Datenbank: es gibt kein
`aktualisiere_diskussion_verdichtung`-Gegenstueck mit Historie, die
`UNIQUE(chat_id)`-Zeile ist die einzige Quelle.

`begriffsboard`-Tabelle: **5 Zeilen** (haengt an, volle Historie bleibt in
der Rohtabelle erhalten). Aber `arbeitsstand.begriffe_detail` — die einzige
Spalte, die `kontext.baue()` tatsaechlich liest — spiegelt nach jedem Lauf
nur den juengsten Stand: ein Begriff wie `"arrival"`, der ab Session 3 nicht
mehr vom Board gefuehrt wird (aber in `arbeitsstand.begriffe` additiv stehen
bleibt, weil die Gruppe ihn einmal genannt hat), hat am Ende **keine**
Begruendung/Doppelbedeutung mehr im Prompt, obwohl Session 1 und 2 dafuer
wortwoertlich belegte Eintraege hatten. Verifiziert:
`tests/test_fixture_padua_aggregiert.py::test_begriffsboard_haengt_an_aber_detail_spiegelt_nur_juengsten_stand`.

**Gegenueberstellung P1 vs. P3** (wie von der Karte verlangt): P1s
Diskussionsverdichtung **ersetzt** (SQL `ON CONFLICT ... DO UPDATE`), P3s
Interview-Verdichtungen **haengen an** (SQL `INSERT`, keine `UNIQUE`-Grenze
ausser der Primaerschluessel) — und dieser Unterschied ist nicht nur ein
Implementierungsdetail, er hat eine reale Konsequenz: eine P1-Gruppe, die
ihre Hintergrunddiskussion in mehreren Schueben fuehrt (Mikrofon aus/an ueber
den Tag), verliert bei jedem neuen Lauf das, was der vorherige Lauf
destilliert hatte, falls das Modell es nicht von selbst erneut aufgreift —
eine P3-Gruppe mit mehreren Interviews verliert nichts, jede Verdichtung
bleibt als eigene Zeile stehen.

### Platz-im-Prompt-Befund

`kontext._REIHENFOLGE` (`kontext.py:235`): `diskussion` steht hinter
`festlegungen`, `begriffe_detail` direkt danach — beide VOR
`phasenhinweis`/`figurenhinweis`/`szene`/`journal`/`fenster`.

Gemessen (`platz_im_prompt`, Diskussions-Gruppe, Phase 1, kein
Erstkontakt): Koerper gesamt **188 Token**, davon `diskussion`-Block
**67 Token (35,6 % des Koerpers)** — der mit Abstand groesste Einzelblock
dieses Prompts. `begriffe_detail` = 0 (Phase-Gating, siehe unten). Die
Systemanweisung allein: **9283 Token**, rund **49-mal** so viel wie der
ganze Koerper — der Diskussionsblock ist im Gesamtprompt winzig, aber im
KOERPER (dem Teil, der sich mit dem Gespraech aendert) dominant.

**Phasen-Gating-Asymmetrie, live verifiziert** (nicht nur gelesen):
derselbe `chat_id`, einmal auf Phase 1, einmal auf Phase 7 gesetzt:

```
{'phase_1': {'diskussion': 67, 'begriffe_detail': 0},
 'phase_7': {'diskussion': 67, 'begriffe_detail': 103}}
```

`diskussion` ist in **jeder** Phase sichtbar (1 bis 7), solange die Zeile in
der DB steht. `begriffe_detail` ist nur in Phase 2 und ab Phase 4 sichtbar —
in Phase 1 (wo die Diskussion gerade lief!) und in Phase 3 (Interviews)
zeigt der Bot **die eigene Begruendung der Gruppe fuer ihre Begriffe nicht**,
waehrend die freie Diskussions-Verdichtung die ganze Zeit durchlaeuft.

**Kuerzungsverhalten, live provoziert** (nicht nur aus dem Code zitiert):
mit genuegend zusaetzlichem Material (`provoziere_kuerzung`, 24 Wachstums-
Runden) wird `gekuerzt=True`, und die beobachtete Reihenfolge, in der
Bloecke zuerst auf 0 fielen:

```
fenster (Runde 21) -> festlegungen (23) -> diskussion (23) ->
begriffe_detail (23) -> verdichtungen (24)
```

Das bestaetigt empirisch, was `kontext._kuerze_auf_budget`
(`kontext.py:1704`) dokumentiert: **beide P1-Bloecke fallen VOR den
P3-Verdichtungen weg**, wenn der Platz nicht reicht. Die eigene
Begriffs-Diskussion der Gruppe hat im Prompt eine niedrigere Prioritaet als
das Interviewmaterial — eine bewusste, aber bisher nur im Code
dokumentierte, nie gemessene Entscheidung.

### Nutzungs-Befund

`nutzung_befund()` gegen `interview_theater/prompts/system.md` und
`interview_theater/prompts/phasen/1.md` … `7.md` (reiner String-Vergleich):

```
'Kernpaket':           ['5.md', '6.md']
'Verdichtung':         ['system.md', '3.md', '4.md', '6.md']
'Begriffs-Diskussion': []
'begriffe_detail':     []
'Begriffsboard':       []
```

Das **Kernpaket** wird dem Modell ausdruecklich als Arbeitsgrundlage
vorgestellt ("Woraus du arbeitest: dem Kernpaket." — `phasen/5.md:8`,
`phasen/6.md:15`), die **Verdichtungen** werden an mehreren Stellen erklaert
und eingeordnet (`system.md`, `phasen/3.md`). Fuer den Diskussionsblock und
den Begriffe-Detail-Block — die Phase 1 ueberhaupt erst produziert — gibt es
**keine einzige Zeile** in irgendeiner Phasenanweisung oder der
Systemanweisung, die dem Modell sagt, dass dieser Block existiert, was er
bedeutet, oder wie es ihn nutzen soll. Das Modell bekommt nur die rohe
Kopfzeile ("Aus eurer Begriffs-Diskussion:" / "Warum ihr diese Begriffe
gewaehlt habt:") ohne jede Rahmung — waehrend `phasen/1.md` und `phasen/2.md`
(gelesen fuer diese Karte) im Gegenteil ausdruecklich sagen, der Bot solle in
Phase 1 "nicht sortieren, nicht kommentieren, keine Assoziationen" machen und
in Phase 2 Fragen "aus ihren Kernbegriffen" statt frei erfunden stellen —
Anweisungen, die ein Modell, das weiss, dass eine Begruendung/Doppelbedeutung
im Kontext steht, praeziser befolgen koennte, als eines, das sie nur als
unbenannten Text im Prompt findet.

### Klasse

**Klasse B** (Entscheidung Birk) — siehe Entscheidungsfrage am Ende.

---

## P3 — Interviews (Phase 3)

### Fundstelle

`interview_theater/repo.py:871` (`speichere_verdichtung`):

> "Speichert eine Verdichtung mit ihren Kernthemen. Wird laut SPEC nie
> aktualisiert — es gibt bewusst kein `aktualisiere_verdichtung()`."

`interview_theater/verdichter.py:52` (`SCHEMA`) und `:114` (`verdichte`):
das Schema verlangt `zusammenfassung` UND `kernthemen[].beleg_zitat`, aber
nur `beleg_zitat` wird geprueft:

> "Faellt die Pruefung durch, faellt das ganze Thema weg" (Zeile 14, bezogen
> auf `beleg_zitat`) — keine aequivalente Zeile existiert fuer
> `zusammenfassung`. Der Aufruf `repo.speichere_verdichtung(conn, chat_id,
> aufnahme_id, ergebnis["zusammenfassung"], themen)` (Zeile 174–176)
> speichert `ergebnis["zusammenfassung"]` unverifiziert, so wie das Modell
> es geliefert hat.

### Treue-Befund

> Interview-Session 3 (Aynur, Honeypot): `kandidaten=['Aynur', 'Mehmet']
> verdaechtig=['Mehmet']` — die Zusammenfassung behauptet "Her son Mehmet
> started school three weeks after they arrived", **"Mehmet" kommt in
> keinem Satz des echten Transkripts** (`simulation/interviews/set1/3-aynur-winter.md`)
> vor.

Zum Vergleich: alle `beleg_zitat`-Werte der uebrigen vier Interviews
bestehen `zitat.pruefe` (das ist Teil der Fixture-Konstruktion selbst, per
`assert` erzwungen — der Produktionscode wuerde ein unbelegtes Zitat ebenso
verwerfen, siehe `verdichter.py:151`). Der Unterschied zur Diskussion (P1):
hier gibt es **gar kein** Anfuehrungszeichen-basiertes Teilfilter fuer die
`zusammenfassung` — die Diskussion hat wenigstens die Chance, dass ein
erfundener Satz zufaellig ein Zitat enthaelt, das durchfaellt; die
Interview-`zusammenfassung` hat diese Chance nicht einmal, weil sie
strukturell nie gegen Zitate geprueft wird.

**Ein echter, von der Fixture nicht geplanter Zusatzbefund** (Task 2,
dokumentiert statt versteckt): Interview-Session 1s `zusammenfassung`
enthaelt das Wort `"Quran"` — die englische Zusammenfassung uebersetzt das
deutsche `"Koran"` aus dem Originaltranskript. Mechanisch ist das
ununterscheidbar von einer Fabrikation (das Wort steht wortwoertlich nicht
im Transkript), inhaltlich ist es eine korrekte Uebersetzung. Das zeigt eine
Grenze der mechanischen Pruefung selbst: **eine woertliche
Teilstring-Pruefung kann eine Uebersetzung nicht von einer Erfindung
unterscheiden** — bei einem zweisprachigen Workshop (Padua: italienische
Teilnehmerinnen, englische Zusammenfassungen) ist das kein Rand-, sondern ein
Kernfall.

### Kumulations-Tabelle

| Session | `zusammenfassung` (Zeichen) | Dublette? |
|---|---|---|
| 1 (Meryem) | 335 | nein |
| 2 (Ferzan) | 353 | nein |
| 3 (Aynur, Fabrikation) | 344 | nein |
| 4 (Ljiljana) | 326 | nein |
| 5 (Halina) | 381 | nein |

`verdichtung`-Tabelle nach 5 Interviews: **5 Zeilen** (haengt an, wie
erwartet und wie SPEC es verlangt). Keine Dublette (`ist_dublette` ueberall
`False`). Kein Wachstums- oder Schrumpfungsmuster ueber die Sessions — jede
Verdichtung ist unabhaengig von den anderen (das ist by design: der
Verdichter kennt den Chatverlauf nicht, SPEC § 4.2).

### Platz-im-Prompt-Befund

`kontext._baue_verdichtungen` (`kontext.py:471`) ist der **erste** Block in
`_REIHENFOLGE` — "stabil nach vorn, fluechtig nach hinten"
(`kontext.py:234`). In der Kuerzungsleiter ist er der **letzte** opferbare
Block vor der Szenen-Garantie (`_kuerze_auf_budget`, Stufe 7 von 8, direkt
VOR nur noch dem Szenenblock) — empirisch bestaetigt: in der provozierten
Kuerzung fiel `verdichtungen` erst in Runde 24, eine Runde NACH `diskussion`
und `begriffe_detail` (Runde 23). Die Verdichtungen sind also sowohl
rendering-seitig am prominentesten platziert als auch budget-seitig am
besten geschuetzt — genau umgekehrt zur Diskussion/begriffe_detail aus P1.

### Nutzungs-Befund

`"Verdichtung"` steht in `system.md`, `phasen/3.md`, `phasen/4.md`,
`phasen/6.md` — der Bot wird in mehreren Phasen ausdruecklich ueber den
Umgang mit Verdichtungen instruiert (`phasen/3.md:36-72`: was zu tun ist,
wenn die Gruppe einer Verdichtung widerspricht, dass sie "bis zum Schluss
zurueck" bleibt, etc.). Deutlich besser instrumentiert als P1.

### Klasse

**Klasse B** (Entscheidung Birk, Teil derselben Entscheidungsfrage wie P1 —
die unverifizierte `zusammenfassung` ist dasselbe Muster wie der
unverifizierte Diskussions-Fliesstext, nur an einer anderen Stelle im Code).

---

## P4 — Brainstorm (Phase 4)

### Fundstelle

`interview_theater/buehnenkarte.py:50` (`_kontext_phasen_1_bis_3`):

> "Begriffe und die (vom Modell formulierten) Interviewfragen — NIE
> Interviewmaterial, Phase 4 ist absichtlich interview-frei."

`interview_theater/kontext.py:673` (`material_erlaubt`) und `:694`
(`kernpaket_erlaubt`): `PHASEN_ERFINDEN = (4,)`,
`material_erlaubt` liefert `phasen.aktuelle(...) < 4`, `kernpaket_erlaubt`
liefert `phasen.aktuelle(...) >= 5`. In `_bloecke` (`kontext.py:1675-1676`):
`"verdichtungen": _baue_verdichtungen(...) if material else ""`,
`"transkripte": _baue_transkripte(...) if material else ""` — in Phase 4
ist `material` `False`, also sind beide Bloecke leer, und `kernpaket` ist
ebenfalls leer (Phase 4 < 5). **Das ist die vorab geklaerte Behauptung der
Karte, selbst nachgelesen und bestaetigt**: im Hauptgespraechs-Prompt sieht
Phase 4 weder P1- noch P3-Material.

Die Buehnenkarte ist strukturell ein ANDERER Prompt-Pfad:
`repo.brainstorm_transkript` (`repo.py:2152`) wird laut Grep **ausschliesslich**
von `buehnenkarte._nutzertext` (`buehnenkarte.py:75`) gelesen — niemals von
`kontext.py`. Bestaetigt: `grep -rn "brainstorm_transkript" interview_theater/`
findet nur die Definition in `repo.py` und den einen Aufruf in
`buehnenkarte.py`.

### Treue-Befund

> Brainstorm-Session 3 (Honeypot): `kandidaten=['Rosaria']
> verdaechtig=['Rosaria']` — die Buehnenkarte behauptet "Give the
> stationmaster a name - Rosaria - and let her mention she has worked this
> platform for eleven years", **"Rosaria" kommt in keinem
> Brainstorm-Transkript, Setting oder der Geschichte dieser Gruppe vor.**
> Genau wie die Interview-`zusammenfassung`: `buehnenkarte.erzeuge()`
> (`buehnenkarte.py:103`) prueft die Modellantwort gegen **gar nichts** —
> nicht einmal ein Zitat-Feld existiert hier, die ganze Karte ist freier
> Text.

**Ein echter, von der Fixture nicht geplanter Zusatzbefund:** Session 2s
Buehnenkarte erwaehnt `"Tommaso"` ("Tommaso's double apology already lands
in the interview material") — dieser Name kommt in **keinem** Feld des
Brainstorm-`chat_id` vor (nicht im Transkript, nicht in `rahmen`, nicht in
`geschichte`). Er stammt aus dem **anderen** Strang dieser Karte
(Interview-Fixture). Eine rein chat-lokale mechanische Pruefung kann das
nicht unterscheiden von einer Fabrikation — in der Produktion hat das aber
eine reale Entsprechung: Figuren wie "Tommaso" entstehen in Phase 4/5 durchs
freie Erfinden der Gruppe UND koennten durch das Modell "erinnert" werden,
obwohl sie in DIESER Gruppe nie genannt wurden, wenn die Buehnenkarte (anders
als hier in der Fixture) tatsaechlich einmal mit echtem Interviewmaterial in
Beruehrung kaeme. Da `buehnenkarte.py` laut Code-Lesung ausschliesslich
`begriffe`/`fragen`/`stueckkarte`/eigenes-Brainstorm-Transkript sieht
(niemals Interviewmaterial, siehe oben), ist das in der echten Produktion
kein Risiko — es zeigt aber, dass die Honeypot-Methode selbst strukturell
scharf unterscheidet zwischen "im Code unmoeglich" (Interviewmaterial in P4)
und "im Code nicht geprueft" (ein beliebiger erfundener Name in der Karte).

### Kumulations-Tabelle

| Session | `brainstorm_transkript` (Zeichen, kumulativ) | Wachstum | Dublette? |
|---|---|---|---|
| 1 | 66 | 0 | nein |
| 2 | 145 | +79 | nein |
| 3 (Fabrikation in Karte) | 212 | +67 | nein |
| 4 | 277 | +65 | nein |
| 5 | 352 | +75 | nein |

**Strikt monotones Wachstum** — anders als P1 (schwankt: 208/196/273/172/170)
und P3 (schwankt: 335/353/344/326/381). Das ist by design: der Brainstorm-
Transkript-Text wird nie destilliert, sondern roh angehaengt
(`repo.brainstorm_transkript`: "chronologisch aneinandergehaengt ... eine
Karte soll den ganzen bisherigen Bogen sehen"). `buehnenkarte`-Tabelle: **5
Zeilen** (haengt an, wie `journal`/`szenenfassung`). Keine Dublette.

Drei verschiedene Kumulationsmuster fuer drei Straenge: **P1 ersetzt** (ein
Lauf verdichtet jedes Mal alles neu, das Ergebnis schwankt), **P3 haengt an
und verdichtet unabhaengig** (jede Zeile ist endgueltig, das Ergebnis
schwankt mit dem Interviewinhalt), **P4 haengt roh an, ohne zu verdichten**
(monotones Wachstum, kein Modell-Destillationsschritt dazwischen — die Karte
selbst wird zwar separat angehaengt, aber der NUTZERTEXT fuer die naechste
Karte liest den akkumulierten ROH-Transkript, nicht die vorherigen Karten).

### Platz-im-Prompt-Befund

Nicht anwendbar fuer den Hauptprompt — P4-Material erscheint dort nicht (per
Design, siehe Fundstelle oben). Gemessen: Brainstorm-Gruppe in Phase 4,
Hauptprompt-Koerper gesamt **96 Token**, System **11155 Token**; keiner der
Bloecke `verdichtungen`/`transkripte`/`kernpaket`/`diskussion`/
`begriffe_detail` traegt etwas bei (alle 0). Die Buehnenkarte selbst lebt in
einem komplett getrennten Prompt mit eigenem Budget
(`buehnenkarte.transkript_zeichen_grenze()`, Vorgabe 200.000 Zeichen,
Kuerzung von VORNE bei Ueberschreitung, `buehnenkarte.py:38-47/75-91`) — eine
Kuerzung dieses Budgets wurde fuer diese Karte NICHT provoziert (haette einen
zusaetzlichen, vom Brief nicht verlangten Messlauf gebraucht; Zeitbox).

### Nutzungs-Befund

Nicht anwendbar im selben Sinn wie P1/P3 — die Buehnenkarte hat ihren
eigenen Prompt (`anweisungen.hole("buehnenkarte")`,
`interview_theater/prompts/buehnenkarte.md`), der fuer diese Karte nicht
geprueft wurde (ausserhalb des Scopes "Hauptgespraechs-Prompt"). Im
Hauptgespraechs-Prompt gibt es nichts zu nutzen, weil nichts dort landet —
konsistent mit der Design-Entscheidung "Erst erfinden, dann schaerfen".

### Klasse

**Klasse B**, aber niedrigere Prioritaet als P1/P3: die unverifizierte
Buehnenkarte ist laut AGENTS.md ausdruecklich eine "Zugabe" ("niemand wartet
auf eine Karte und niemand muss auf einen Fehler reagieren"), waehrend die
P1-Diskussion und die P3-Zusammenfassung in **jedem** Folgeprompt stehen und
vom Modell als Tatsachengrundlage gelesen werden.

---

## Was bewusst nicht gemessen wurde (Zeitbox)

- Kein Live-LLM-Judge-Lauf gegen die Fixture-Texte — die mechanische
  Wortueberlappung reichte, um alle drei Honeypots nachweisbar zu finden,
  ohne Geld auszugeben (Kartentext erlaubt das ausdruecklich).
- Kein Kuerzungstest fuer `buehnenkarte.transkript_zeichen_grenze()` (P4s
  eigenes 200.000-Zeichen-Budget) — andere Prioritaet, Hauptbefund fuer P4
  war die Trennung vom Hauptprompt und die unverifizierte Karte selbst.
- Kein Korpuslauf fuer `diskussion_verdichtung.md`/`buehnenkarte.md` (die
  Prompt-DATEIEN selbst wurden nicht geaendert, nur gelesen — kein
  Korpuslauf faellig).

## Klasse-A-Fix in dieser Karte umgesetzt

**Commit `1a1bb40`**: `kontext.baue()`s kurze Zusammenfassung der
Kuerzungsreihenfolge (Docstring) nannte nur "Transkripte -> Szenenblock ->
Fenster -> Journal -> Festlegungen -> Verdichtungen -> Szenenblock" — ohne
die beiden Padua-Stufen "Diskussion" und "begriffe_detail", die
`_kuerze_auf_budget` (die ausfuehrliche, massgebliche Version direkt daneben)
schon laengst kennt. Zwei Beschreibungen derselben Reihenfolge waren
auseinandergelaufen. Fix: Docstring ergaenzt, ein Test
(`tests/test_kontext.py::test_baue_docstring_nennt_diskussion_und_begriffe_detail_in_der_kuerzungsleiter`)
haelt die relative Reihenfolge der vier Namen in der Kurzfassung fest, damit
eine kuenftige Umsortierung der Leiter hier auffaellt, statt die Doku
stillschweigend veralten zu lassen.

## Weitere offene Punkte (keine Fragen, nur Liste — siehe Entscheidungsfrage fuer die wichtigste)

- Die Uebersetzungs-Falle ("Quran"/"Koran"): eine woertliche
  Teilstring-Pruefung kann bei einem mehrsprachigen Workshop eine korrekte
  Uebersetzung nicht von einer Erfindung unterscheiden. Betrifft jede
  bestehende `zitat.pruefe`-Stelle (Verdichter, Kernzitate, Schaerfung,
  Dramaturgie, Sprachpass), nicht nur diese Karte — hier nur erstmals an
  einem konkreten Fall sichtbar gemacht.
- P1s Diskussionsverdichtung hat keinen Historienpfad: ein zweiter Lauf
  loescht unwiderruflich, was der erste destilliert hatte (keine
  `UNIQUE`-Ausweichtabelle wie bei `szenenfassung`/`buehnenkarte`). Ob das
  gewollt ist (eine Gruppe soll nur EINE, finale Diskussionsverdichtung
  haben) oder ein Luecke ist (eine Gruppe, die ihre Diskussion ueber den Tag
  verteilt fuehrt, verdient Historie wie bei Interviews), ist nicht
  eindeutig aus dem Code ablesbar.
- Die Phasen-Gating-Asymmetrie zwischen `diskussion` (kein Filter) und
  `begriffe_detail` (Phase 2 und ≥4) wirkt wie zwei unabhaengig getroffene
  Entscheidungen zu zwei Bloecken, die inhaltlich zusammengehoeren (beide
  sind Phase-1-Artefakte). Ob das beabsichtigt ist, ist aus dem Code allein
  nicht zu beantworten.

## Die Entscheidungsfrage

**Befund:** Drei Freitextfelder — die P1-Diskussionsverdichtung
(`diskussion.py`), die P3-Interview-`zusammenfassung`
(`verdichter.py:52-176`) und die P4-Buehnenkarte (`buehnenkarte.py:103-142`)
— werden **nie** gegen ihr Ausgangstranskript verifiziert, bevor sie
gespeichert und (bei P1/P3) in jeden Folgeprompt geschrieben werden. Nur
explizit zitierter, in Anfuehrungszeichen stehender Text durchlaeuft
`zitat.pruefe`. Diese Karte hat das an drei konkreten, reproduzierbaren
Faellen demonstriert (ein erfundener Name je Strang, mechanisch gefunden,
ohne Live-Modellaufruf) — es ist kein theoretisches Risiko mehr.

**Frage an Birk:** Soll fuer diese drei Freitextfelder eine mechanische
Nachpruefung (dieselbe Wortueberlappungs-Heuristik wie in dieser Karte,
ggf. verfeinert gegen die Uebersetzungs-Falle) als **Vorfall** (nicht als
blockierender Fehler, analog zu `zitat_ungeprueft`/`kontext_gekuerzt`) in die
Produktion aufgenommen werden — oder bleibt die aktuelle Abdeckung (nur
Zitate, nie Fliesstext) bewusst so, weil ein falscher Nebensatz in einer
Zusammenfassung als geringeres Risiko gilt als der Aufwand einer weiteren
Pruefstufe?

**Empfehlung:** Einen Vorfall einbauen, kein blockierendes Verhalten. Die
Begruendung aus `verdichter.py:14-25` ("ein Thema ohne Beleg ist ... eine
Behauptung ueber einen Menschen") gilt fuer die `zusammenfassung` genauso
wie fuer `beleg_zitat` — nur dass die Zusammenfassung nie wegfallen darf
(sie ist das einzige Ergebnis, wenn kein Thema ein Zitat besteht, SPEC N2),
also passt hier kein "verwerfen", sondern nur ein "sichtbar machen". Ein
Vorfall `verdichtung_zusammenfassung_unbelegt` (bzw. `diskussion_.../
buehnenkarte_...`) mit den verdaechtigen Woertern kostet nichts an
Betriebszeit, blockiert nichts, und macht aus dem stillen Risiko dieser
Karte zumindest eine Dashboard-Zeile, die ein Mensch nachpruefen kann —
genau das Muster, das `kontext_kuerzung_erfolglos` fuer ein anderes stilles
Risiko schon etabliert hat.

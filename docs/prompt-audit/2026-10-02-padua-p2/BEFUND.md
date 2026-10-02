# Befund: Padua P2-Fix -- Abschnittszahl fest bei Szenenfolge + Restspannungen (02.10.2026)

Dieser Befund loest die sieben offenen Restspannungen aus
`docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md` (Abschnitt „Bekannte
Restspannungen") ab. Grundlage: **Birks Entscheidung vom 02.10.2026** zur
Abschnittszahl und die **Code-Wahrheit** fuer alles uebrige. Zeilennummern
sind auf diesem Zweig per `grep -n` nachgemessen, nicht aus dem Plan
uebernommen.

## Wie die Dumps entstehen

`python3.11 -m scripts.erzeuge_prompts_padua docs/prompt-audit/2026-10-02-padua-p2`
-- unveraendert wie am 01.10.2026: Wegwerf-Datenbank im Temp-Verzeichnis,
zwei erfundene Gruppen (Phase 1 und Phase 6), Interviewmaterial aus
`simulation/interviews/set1/2-ferzan-bahnhof.md` (frei erfunden), `IT_DB` auf
die Wegwerf-DB, damit kein Regie-Zettel aus `betrieb/` hineinrutscht. **Kein
Modellaufruf** -- der Dump ist reine Textmontage. Die Phase-6-Fixture legt
**drei** Szenen an (`scripts/erzeuge_prompts_padua.py:152-176`); deshalb ist
in Dump 03 die neue bindende Auftragszeile messbar.

| Dump | System alt (01.10.) | System neu | Nutzer alt | Nutzer neu | Token alt | Token neu |
|---|---|---|---|---|---|---|
| 01 Gespraech Phase 1 | 26 965 | 26 943 | 393 | 393 | 9 119 | 9 112 |
| 02 Gespraech Phase 6 | 31 584 | 31 396 | 2 416 | 2 416 | 11 333 | 11 270 |
| 03 Kurzgeschichte Phase 6 | 14 205 | 14 230 | 1 433 | 1 500 | 5 212 | 5 243 |
| 04 Einzelszene Prosa Phase 6 | 13 094 | 13 051 | 2 702 | 3 002 | 5 264 | 5 350 |

Je Zeile, woher die Differenz kommt:

- **01**: System kuerzer (26 965 -> 26 943) -- Restspannung 1 nimmt
  „(variants of the same idea, …)" aus `en/phasen/1.md` heraus. Nutzer
  unveraendert (393 = 393): Phase 1 liest keinen der geaenderten Bloecke.
- **02**: System kuerzer (31 584 -> 31 396) -- Restspannungen 1, 7 und 8
  nehmen Saetze aus `en/phasen/6.md` (alle vier Diff-Hunks dieses Dumps
  liegen dort, gemessen; `en/system.md` ist auf diesem Zweig unveraendert
  und hier nicht beteiligt). Nutzer unveraendert (2 416 = 2 416):
  `kontext.KERNPAKET_KOPF` (Restspannung 4)
  sagte englisch schon vorher „story" statt „core theme" (seit c8) -- die
  Aenderung dieser Karte betrifft dort nur die deutsche Fassung, die
  dieser Dump nicht liest.
- **03**: System laenger (14 205 -> 14 230) -- Task 5/6 ergaenzen
  `en/formen/prosa.md` um die bindende Abschnittszahl-Regel (Teil A). Nutzer
  laenger (1 433 -> 1 500, +67 Zeichen): die neue Auftragszeile
  `kurzgeschichte._ZEILE_ABSCHNITTE` erscheint, weil die Fixture drei Szenen
  anlegt. **Das ist nicht der Pfad des echten Padua-Laufs:**
  `scripts/erzeuge_prompts_padua.py:223` ruft `baue_nutzertext` OHNE
  `eintraege` -- der reale Lauf (mit aktivem Laengen-Profil) traegt die
  Bindung stattdessen ueber `laengen.SATZ_BINDUNG` im Laengen-Budget-Block
  (`laengen.block_prosa`). Die Zusicherung fuer den echten Pfad sind die
  Tests aus Task 7/8 (`tests/test_laengen_prosa.py`,
  `tests/test_nachpass_prosa.py`), nicht dieser Dump.
- **04**: System kuerzer (13 094 -> 13 051) -- der einzige System-Hunk
  dieses Dumps liegt in `en/formen/prosa.md` (Task 5, Commit `75846b6`,
  dieselbe neue Bindungsregel wie in Teil A); `kurzgeschichte.ANWEISUNG`
  ist am Einzelszenen-Prompt nicht beteiligt (der liest `szene.py`, nicht
  `kurzgeschichte.py`) und wird hier nicht zitiert.
  **Nutzer laenger, abweichend von der erwarteten Richtung** (2 702 -> 3 002,
  +300 Zeichen) -- und das ist **keine Wirkung dieser Karte**: der Diff
  zeigt, dass der Figuren-Block-Kopf von `szene.FIGUREN_KOPF_OHNE_STIMME`
  (`en/texte.toml:936`) auf `szene.FIGUREN_KOPF_MIT_STIL` (`:938`) wechselt
  und drei Zeilen `szene.ZEILE_SPRACHSTIL` (`:937`, „Speech style (chosen
  by the group): …") dazukommen. Alle drei Konstanten stammen aus Padua M1
  (Commits `20d5b0a`/`eb5949e`, „szene: sprachstil im Szenen-Prompt" / „drei
  Koepfe fuer Block 3") und sind bereits vor dieser Karte auf `main`
  gelandet -- aber **nach** dem alten Dump vom 01.10.2026 (`4280f51`). Der
  Altdump zeigt den Code-Stand vor M1, der Neudump den Stand danach; die
  Differenz gehoert zu M1, nicht zu P2-Fix.

## Teil A -- Birks Entscheidung vom 02.10.2026

> Die Abschnittszahl der Prosa (Phase 6) ist FEST, sobald eine Szenenfolge
> existiert. Ohne Szenenfolge waehlt das Modell frei.

| Wo | Was jetzt dasteht | Code-Beleg |
|---|---|---|
| `en/prompts/formen/prosa.md:24-33` | „If a scene sequence already exists, its number of scenes is binding … Without one, you choose the number of sections from the story" | `phasen.voraussetzungen[6]` verlangt >= 1 Szene (`phasen.py:374`); `kurzgeschichte.abschnittszahl` sagt es im Docstring (`kurzgeschichte.py:308-320`: „Dieselbe Menge, mit der `lege_szenen_an` abgleicht und die `budget_eintraege` bemisst") |
| `kurzgeschichte.ANWEISUNG` (DE `kurzgeschichte.py:81-96`, EN `en/texte.toml:1115-1124`) | „Nennt der Auftrag eine Abschnittszahl, ist sie verbindlich … Nennt er keine, waehlst du die Zahl der Abschnitte selbst" | eine Systemanweisung kennt die Datenlage nicht -- die Bedingung muss am Auftrag haengen |
| `kurzgeschichte.abschnittszahl` + `_ZEILE_ABSCHNITTE` (`kurzgeschichte.py:301-304`) | „Schreib genau N Abschnitte -- einen je geplanter Szene, in deren Reihenfolge." | `repo.hole_szenen` filtert `entfernt_am IS NULL` (`repo.py:2309-2318`) -- dieselbe Menge, mit der `lege_szenen_an` abgleicht und `budget_eintraege` rechnet |
| `laengen.SATZ_BINDUNG` (unveraendert, `laengen.py:368`) | „Genau N Abschnitte, in dieser Reihenfolge, mit diesen Laengen." | `laengen.block_prosa` (`laengen.py:401-415`); bei aktivem Laengen-Profil ist **sie** die eine Stelle, und `baue_nutzertext` laesst seine eigene Zeile dann weg |
| `en/prompts/phasen/6.md:42-43` | „its number and its order count" -- **unveraendert**, und seit dieser Karte wieder durchgehend wahr | das war der Widerspruch, den Restspannung 6 benannt hat |

**Ein Fakt, eine Stelle:** die Zahl steht in **genau einem** Block je Prompt
-- im Budget-Block, wenn es einen gibt, sonst im Auftrag. Test:
`tests/test_laengen_prosa.py::test_die_zahl_steht_genau_einmal_im_prompt`
(gemessen: `1 passed, 2 skipped, 5210 deselected`).

**Entfaellt gegenueber der Planvorlage:** die Zeile zu
`workshop/padua-2026/phasentexte.toml:49-56` ("One section per scene you
planned, in that order.") ist hier bewusst nicht aufgefuehrt -- diese
Aenderung existiert nicht. Task 11 (die englische Phase-6-Chat-Einleitung
nachzuziehen) wurde im Architekten-Review gestrichen (Auftrag Birk,
02.10.2026) und ist damit out of scope. Die Datei sagt nach wie vor „The story decides how
many sections it gets." (`workshop/padua-2026/phasentexte.toml:51-52`,
gemessen) -- siehe Teil F, Punkt 2.

## Teil B -- die sieben Restspannungen

| Nr. | Was war | Was jetzt gilt | Code-Beleg / Commit |
|---|---|---|---|
| 1 | `en/phasen/1..7.md` verlangten „(variants of the same idea, …)" -- gegen die Profil-Anweisung, die einen gegenlaeufigen Winkel erlaubt | „(title — description each)"; die Winkel-Regel steht **nur** in `anweisung.md` | `anweisungen.py:346-378` (`system()`, letzter Block vor dem Regie-Zettel, SPEC § 6.1). Commit `729146f` |
| 2 | `en/texte.toml:932` „filtered by the core theme" | „The passages from the interviews the group has taken on for this story" -- was in **beiden** Zweigen stimmt | `szene._kernpaket_text` (`szene.py:986-1023` je Szene/Figur, `:1026-1044` Rueckfall global, EIN Kopf fuer beide, `szene.py:979-984`). Commit `82f6d80` |
| 4 | Deutsch wich an drei Stellen vom korrigierten Englisch ab | `prompts/system.md:46` „Station 4"; `kontext.KERNPAKET_KOPF` „aus der Geschichte"; `szene.KERNPAKET_KOPF` ohne Kernthema. `prompts/formen/prosa.md:29` war nach Birks Entscheidung **schon richtig** und ist unangetastet | `workshop.py:331-344` (4 traegt `konflikt`/`hauptkonflikt`, 5 ist „Schaerfung"); `kontext.py:454-463` (Geschichte vorn, Kommentar: „Die Geschichte ist die Quelle, nicht das Kernthema"). Commits `82f6d80`, `71150f2`, `9919925` |
| 5 | „ein reiner Sprachpass-Lauf nennt die Abschnittszahl nicht" | **Praemisse korrigiert**: er nennt sie, nur nicht in der Regie-Notiz. `nach_geschichte` laeuft nur mit aktivem Laengen-Profil und uebergibt dann immer `eintraege` -> `laengen.SATZ_BINDUNG` steht im Nutzertext. Kein neuer Text; dafuer eine Zusicherung mit Docstring-Beleg | `nachpass.py:305-320` (Docstring „Wer die Abschnittszahl bindet"). `tests/test_nachpass_prosa.py::test_ein_reiner_sprachpass_lauf_traegt_die_abschnittszahl` (gemessen: `3 passed, 12 deselected`). Commit `051db88` |
| 6 | c5 war „vorlaeufig": prosa.md frei, phasen/6.md bindend | **entschieden** (Birk 02.10.2026): fest bei Szenenfolge. Siehe Teil A | Commits `75846b6` (en-prosa), `338a954` (kurzgeschichte.ANWEISUNG DE+EN), `f13201f` (Auftragszeile) |
| 7 | `en/phasen/6.md:9-13` „A script is created … Herkules measure" | „What is created is source material." -- Inszenierung in der Probe, kein Textbuch, kein Herkules-Mass | `en/phasen/6.md:9` (gemessen); `kurzgeschichte.ANWEISUNG` („keine Szenenliste, kein Theatertext"), `en/formen/prosa.md:27`. Commit `55f1ef7` |
| 8 | `en/phasen/6.md:96-104` beschrieb Ergebnis und Knopfleiste von Phase 7 | Phase 6 nennt „Write the story" / „Looks good" / „Change something" / „Shorter (25 %)" / „Rewrite from scratch" (`en/phasen/6.md:97-99`, gemessen); der Szene-fuer-Szene-Ablauf mit „Yes, write it" / „Plan it differently" / „Change form" / „Skip" steht in `en/phasen/7.md:97-99` | `knoepfe/szenen.py:1290` (`zeige_kurzgeschichte`, Geschichte) gegen `:747` (`biete_nach_szenentext`, Szenentext); Wortlaute aus `en/texte.toml`. Commit `8b9aa10` |

**Restspannung 3** war im Gesamtreview vom 02.10.2026 schon behoben.

## Teil C -- die Greptabelle (Positivkontrolle alt -> neu)

Gemessen mit `/tmp/abnahme_p2fix.py` (Wegwerf-Skript, nicht im Repo) ueber
beide Dump-Verzeichnisse; Treffer je Datei `01/02/03/04`. Exit-Code `0`,
keine Zeile mit „FEHLER".

| Muster | alt | neu | Art |
|---|---|---|---|
| `suggestion, not a requirement` | 0/0/1/0 | 0/0/0/0 | Positivkontrolle |
| `variants of the same idea` | 1/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `A script is created` | 0/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `Change form` | 0/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `a text for every scene` | 0/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `Herkules measure`, **nur Dump 02** | 1 | 0 | Positivkontrolle. Ueber alle vier Dateien steht es alt auf 0/1/1/1 -- in 03 und 04 aus `en/formen/prosa.md:27` („doesn't apply here either"), und dort **bleibt** es. Eine Kontrolle „ueberall 0" waere falsch |

Gegenprobe, der **neue** Stand ist da (Dump 03):

| Muster | neu | Warum dort |
|---|---|---|
| `its number of scenes is binding` | 1 | `formen/prosa.md`, im System-Teil des Prosalaufs |
| `If the job names a number of sections` | 1 | `kurzgeschichte.ANWEISUNG` |
| `Write exactly \d+ sections` | 1 | die neue Auftragszeile; die Fixture hat drei Szenen |

**Zwei Muster sind im Dump nicht messbar, und das ist kein Mangel des
Nachweises, sondern eine Eigenschaft der vier Dumps:**

1. **`szene.KERNPAKET_KOPF` („filtered by the core theme") kommt in keinem
   Dump vor** -- gemessen am Altstand: 0/0/0/0. Dump 04 ist der einzige
   Szenenlauf, und `szene._kernpaket_text` liefert dort nichts: die Fixture
   hat `verdichtung_thema`-Zeilen, aber keine `schaerfung` und kein
   `zum_kernthema_am`. Eine Positivkontrolle am Dump ist damit unmoeglich.
   **Stattdessen** zwei Nachweise: der Grep auf die Quelldateien
   (`en/texte.toml`, `szene.py` -> je 0) und der Test
   `tests/test_szene_sprache.py::test_der_kernpaket_kopf_nennt_das_kernthema_nicht_mehr`
   (gemessen: `1 passed, 13 deselected`), der **beide** Sprachfassungen zur
   Aufrufzeit rendert.
2. **„core theme" allein ist kein taugliches Muster.** Es steht in 01/02 je
   elf- bis zwölfmal voellig zu Recht: `system.md` nennt das Kernthema als
   Beispiel fuer einen Satz der Gruppe („we're still on the core theme",
   c8), und `phasen.toml` fuehrt es als Stichwort von Phase 4. Gemessen wird
   deshalb die **vollstaendige** Wendung.

| Quelldatei | Muster | alt | neu |
|---|---|---|---|
| `interview_theater/sprachen/en/texte.toml` | `filtered by the core theme` | 1 | 0 |
| `interview_theater/szene.py` | `am Kernthema gefiltert` | 2 | 0 |
| `interview_theater/kontext.py` | `Kernthema und dieser Auswahl` | 1 | 0 |
| `interview_theater/prompts/system.md` | `Station 5, keine Voraussetzung` | 1 | 0 |

(Die „alt"-Werte sind gegen Commit `04c31c3`, den Stand vor Task 1 dieser
Karte, gemessen: `git show 04c31c3:<pfad> | grep -c <muster>`.)

## Teil D -- Profil- und Sprachpruefung

```
$ python3.11 -m scripts.pruefe_profil padua-2026
Workshop-Profil padua-2026
padua-2026: in Ordnung
$ python3.11 -m scripts.pruefe_profil dortmund-2026
Workshop-Profil dortmund-2026
dortmund-2026: in Ordnung
$ python3.11 -m scripts.pruefe_sprache padua-2026 ; echo "exit=$?"
0 Treffer
exit=0
```

## Teil E -- die zwei Bitgleichheits-Massstaebe

Vier deutsche Stellen sind mitgezogen (Restspannung 4 und Birks
Entscheidung), also wandern Abschnitte in den Massstaeben. Beides ist
belegt, nichts ist weggedrueckt:

* **`tests/test_sprache_bitgleich.py`** hat den dafuer gebauten
  Ausnahmemechanismus (`GEAENDERT`, je Abschnitt ein Grund,
  `test_jede_ausnahme_hat_einen_grund`). Neue Eintraege (gemessen,
  `tests/test_sprache_bitgleich.py:97-124`): `szene.KERNPAKET_KOPF`,
  `kontext.KERNPAKET_KOPF`, `kurzgeschichte.ANWEISUNG` und die neun
  Abschnitte der Systemanweisung (`prompt system`,
  `anweisungen.system(phase=None|1..7)`), alle mit demselben Grund
  (`_GRUND_STATION_4`: die Systemanweisung geht in jede Phase ein, deshalb
  neun statt einem Abschnitt).
* **`tests/test_profil_bitgleich.py`** hat **keinen** solchen Mechanismus:
  `_vergleiche` kennt nur „unveraendert oder neu". Deshalb sind in
  `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` genau die **neun**
  betroffenen Zeilen gehoben worden, in Commit `9919925` dieser Karte
  (nach der Praezedenz aus Commit `8cc52fd`, 07.09.2026, demselben Vorgehen
  bei main-Drift). Nachweis:
  `git diff --numstat 04c31c3 HEAD -- docs/prompt-audit/schnappschuss-vor-profilumbau.txt`
  zeigt `9  9` (neun geaendert, keine dazu, keine weg).
* **Die Abnahmebedingung des Profilumbaus gilt weiter und ist
  massstabsfrei nachgemessen:** `ohne IT_WORKSHOP` == `IT_WORKSHOP=dortmund-2026`
  (`test_dortmund_und_keine_variable_sind_identisch`, Teil der 49 gruenen
  Tests unten).
* `tests/test_laengen_prosa.py` pinnt den SHA von
  `kurzgeschichte.systemanweisung()`; er ist begruendet nachgezogen
  (alt `704119e3dd886eef7ac619511b4ab70cc7c6fb6858a8618e4ee2da19ffddc729` /
  `12785`, neu `81d5b2384e332d77ad32e48938eb8e54603a46b3f7f098fb0ffdb57a08e1412d`
  / `12839`), und die Zusage „ohne Budget zeichengleich" bleibt (die
  Laenge hat sich nur erhoeht, weil `kurzgeschichte.ANWEISUNG` den neuen
  Bindungssatz traegt -- auch fuer Dortmund, das ist eine gewollte
  Verhaltensaenderung, siehe Docstring dort).

Lauf (gemessen):
```
$ python3.11 -m pytest -q -p no:cacheprovider tests/test_laengen_prosa.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py
.................................................                        [100%]
49 passed in 4.10s
```

## Teil F -- was offen bleibt (bewusst, mit Grund)

1. **Verfehlt das Modell die bindende Zahl, raeumt niemand auf.**
   `kurzgeschichte.lege_szenen_an` gleicht **ergaenzend** ab
   (`kurzgeschichte.py:176-180`, `repo.gleiche_szenenfolge_ab`,
   `repo.py:2355`): kommen bei sechs geplanten Szenen nur vier Abschnitte
   zurueck, bleiben zwei Szenen ohne Prosa stehen -- und
   `phasen.voraussetzungen` verlangt fuer Phase 7 Prosa fuer **jede**
   geplante Szene (`phasen.py:381-383`). Phase 7 ist dann blockiert, **ohne
   Vorfall und ohne Zeile im Chat**. Diese Karte macht die Zahl bindend,
   baut dafuer aber **keinen Code** (so beauftragt). Der Weg einer
   Folgekarte waere entweder ein Vorfall plus eine Zeile an die Gruppe,
   oder ein weiches Loeschen der ueberzaehligen prosalosen Szenen -- das
   zweite ist eine Entscheidung mit Datenwirkung und gehoert Birk.
2. **Die Phase-6-Einleitung im Chat sagt in beiden Sprachen weiter, dass
   die Geschichte die Abschnittszahl entscheidet** -- nicht nur Deutsch.
   Deutsch: `workshop.VORGABE_PHASENTEXTE["6"]`
   (`workshop.py:415-422`, gemessen: „Wie viele Abschnitte es werden,
   entscheidet die Geschichte."); Birk hat den Wortlaut am 06.09.2026
   ausdruecklich bestaetigt, und er haengt in beiden
   Bitgleichheits-Massstaeben (`phasentexte.EINLEITUNGEN[6]`) und in
   `tests/profile/test_dortmund.py:232-233` (gemessen, wortgleich).
   Englisch, Padua-Profil: `workshop/padua-2026/phasentexte.toml:51-52`
   (gemessen: „The story decides how many sections it gets."). Das ist die
   englische Entsprechung derselben Zeile -- **unveraendert**, weil Task 11
   dieser Karte (die englische Phase-6-Chat-Einleitung an Birks
   Entscheidung anzugleichen) im Architekten-Review gestrichen wurde
   (Auftrag Birk, 02.10.2026) und damit out of scope ist. Beide Fassungen sagen damit weiterhin das
   Gegenteil von Teil A dieses Befunds, solange niemand sie aendert.
   Folgekarte, fuer beide Sprachen gemeinsam.
3. **`interview_theater/prompts/phasen/6.md` (deutsch) bleibt unangetastet.**
   Die Datei traegt nicht nur die Restspannungen 7 und 8, sondern auch c2
   („Die Form je Szene steht schon", `prompts/phasen/6.md:34`, gemessen),
   c4 („Szene fuer Szene", `:4`, gemessen) und c9 -- alles, was die
   Vorgaengerkarte fuer Deutsch ausdruecklich ausgeschlossen hat; und sie
   heisst noch „Szenentexte" (`:1`, gemessen), waehrend
   `workshop.VORGABE_PHASEN` fuer 6 „Szenen als Geschichte" fuehrt
   (`workshop.py:348-352`). Nur 7 und 8 nachzuziehen hinterliesse eine
   Datei, die im selben Dokument „Szene fuer Szene" und „EINE
   Kurzgeschichte" sagt. Folgekarte „DE-Phasenprompts nachziehen".
4. **Der Erkenner-Korpuslauf gegen das echte Modell steht weiter aus**
   (kostet Geld, Birk entscheidet). Diese Karte legt **keine** neue
   Erkenner-Art an und aendert `prompts/erkenner.md` nicht -- es ist also
   kein neuer Lauf fällig.

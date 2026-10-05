# Padua Prompt-Check vollstaendig -- BEFUND

## 1. Kopf

- **Datum:** 05.10.2026
- **Karte:** t_1dcf3864 ("Padua Prompt-Check: Volltext-Dump aller
  Modellaufrufe je Phase + Pruefer gegen UX-Regeln")
- **Branch:** `padua-workshop/t_1dcf3864-padua-prompt-check-volltext-dump-aller-m`
- **Profil:** `padua-2026` (gesetzt vom Dump-Skript selbst,
  `os.environ.setdefault(workshop.VARIABLE, "padua-2026")`)
- **Umgebung des Laufs** (`scripts/erzeuge_prompts_padua_voll.umgebung()`):
  `szene_anbieter=claude`, `szene_modell=claude-opus-5`,
  `llm_modell=moonshotai/Kimi-K2.6`, `erkenner_modell=google/gemma-4-31B-it`.
- **Die drei Befehle dieses Laufs, und was sie kosten:**
  1. `python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-voll`
     -- **0 CHF**, kein Netz (faengt an der Transportgrenze ab,
     `scripts.mitschnitt`).
  2. `python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-voll --basis docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv`
     -- **0 CHF**, kein Modell (liest nur Dateien).
  3. `python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-voll`
     -- **0 CHF ueber das Abo** (lokaler Claude-Proxy, kein
     Infomaniak-Aufruf) -- **in diesem Lauf nicht zu Ende gekommen**, siehe
     Abschnitt 7.

## 2. Inventartabelle

38 Inventareintraege, alle 7 Phasen vertreten. `art -> Datei -> Phase ->
weg/Modell -> quelle` (erzeugt aus `uebersicht.tsv`):

| art | pfad | phase | weg | modell | quelle | system_zeichen | nutzer_zeichen |
|---|---|---|---|---|---|---|---|
| gespraech | 01-gespraech-phase1 | 1 | claude | claude-opus-5 | abgefangen | 28705 | 1657 |
| gespraech | 05-gespraech-phase2 | 2 | claude | claude-opus-5 | abgefangen | 33654 | 1802 |
| gespraech | 06-gespraech-phase3 | 3 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 29649 | 14199 |
| gespraech | 07-gespraech-phase4 | 4 | claude | claude-opus-5 | abgefangen | 34804 | 2609 |
| gespraech | 08-gespraech-phase5 | 5 | claude | claude-opus-5 | abgefangen | 30462 | 3108 |
| gespraech | 02-gespraech-phase6 | 6 | claude | claude-opus-5 | abgefangen | 32431 | 3066 |
| gespraech | 09-gespraech-phase7 | 7 | claude | claude-opus-5 | abgefangen | 31759 | 3253 |
| erkenner | 10-erkenner-verlauf | 4 | infomaniak | google/gemma-4-31B-it | abgefangen | 31460 | 2261 |
| erkenner | 11-erkenner-aufnahme | 3 | infomaniak | google/gemma-4-31B-it | abgefangen | 31460 | 2294 |
| journal | 12-journal | 4 | infomaniak | google/gemma-4-31B-it | abgefangen | 4892 | 9698 |
| begriffsboard | 13-begriffsboard | 1 | claude | claude-opus-5 | abgefangen | 4608 | 729 |
| diskussion_verdichtung | 14-diskussion-verdichtung | 1 | claude | claude-opus-5 | abgefangen | 1672 | 208 |
| fragen_ki_vorschlag | 15-fragen-ki | 2 | claude | claude-opus-5 | abgefangen | 2390 | 114 |
| verdichter | 16-verdichter | 3 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 3204 | 2436 |
| brainstorm_karte | 17-buehnenkarte | 4 | claude | claude-opus-5 | abgefangen | 2168 | 924 |
| szenenfolge | 18-szenenfolge | 4 | claude | claude-opus-5 | abgefangen | 7531 | 1857 |
| geschichte | 19-geschichte | 4 | claude | claude-opus-5 | abgefangen | 10234 | 1203 |
| szenenfelder | 20-szenenfelder | 4 | claude | claude-opus-5 | abgefangen | 484 | 2072 |
| schaerfung | 21-schaerfung | 5 | claude | claude-opus-5 | abgefangen | 2249 | 1341 |
| entwurf_uebersicht | 22-entwurf-uebersicht | 5 | claude | claude-opus-5 | abgefangen | 927 | 655 |
| sprachprofil | 23-sprachprofil | 5 | infomaniak | google/gemma-4-31B-it | abgefangen | 2517 | 2233 |
| kernzitate | 24-kernzitate | 5 | infomaniak | google/gemma-4-31B-it | abgefangen | 2658 | 587 |
| kurzgeschichte | 25-kurzgeschichte | 6 | claude | claude-opus-5 | abgefangen | 14226 | 1869 |
| kurzgeschichte | 03-kurzgeschichte-phase6 | 6 | claude | claude-opus-5 | gebaut | 14226 | 2478 |
| szene | 04-szene-prosa-phase6 | 6 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 13052 | 3570 |
| sprechweise | 27-sprechweise | 7 | claude | claude-opus-5 | abgefangen | 592 | 424 |
| szene | 28-szene-dialog | 7 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 32791 | 4052 |
| szene | 29-szene-monolog | 7 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 26229 | 4052 |
| szene | 30-szene-chor | 7 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 32791 | 4052 |
| szene | 31-szene-lied | 7 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 32791 | 4052 |
| szene | 32-szene-rap | 7 | infomaniak | moonshotai/Kimi-K2.6 | gebaut | 27399 | 4052 |
| stueckpruefung | 34-stueckpruefung | 7 | claude | claude-opus-5 | abgefangen | 2712 | 305 |
| dramaturgie_b1 | 35-dramaturgie-b1 | 6 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 2326 | 169 |
| dramaturgie_a2 | 36-dramaturgie-a2 | 6 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 2193 | 565 |
| dramaturgie_a9 | 38-dramaturgie-a9 | 6 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 4084 | 262 |
| dramaturgie_a10 | 39-dramaturgie-a10 | 7 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 4133 | 340 |
| dramaturgie_a11 | 40-dramaturgie-a11 | 6 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 4279 | 784 |
| dramaturgie_c1 | 41-dramaturgie-c1 | 7 | infomaniak | moonshotai/Kimi-K2.6 | abgefangen | 1899 | 328 |

**Nicht im Inventar -- mit Grund (`prompt_inventar.NICHT_LIVE_IN_PADUA`):**

- `interview_theater.begriffsboard_analyse` (`art_fuer(teile)`): kein
  Live-Aufrufer -- einziger Aufrufer ist
  `scripts/rauchtest_begriffsboard_resonanz.py`. Ob ein zweiter Live-Aufruf
  kommt, entscheidet Birk.
- `interview_theater.bot` (`'erkenner'`): Warmlauf beim Prozessstart
  (`bot.warmlaufen`) mit festem Text `'Testaufruf.'` -- kein Prompt der
  Gruppe.
- `interview_theater.modellwahl` (`art`): `aufruf_schema`s eigene
  Weiterleitung an `szene_claude.schema`/`klm.schema` -- derselbe Prompt wie
  an den sieben Aufrufstellen von `aufruf_schema`, die schon im Inventar
  stehen.
- `interview_theater.sprachstil` (`ART`): strukturell unerreichbar ohne
  Bootstrap (Task 3, bestaetigt in Task 7) -- `sprechweise.py` (Dump 27) hat
  die Aufgabe in Phase 7 uebernommen.

**Zusaetzlich aus `INVENTAR` entfernt (Task 7, neuer Fund):**
`37-dramaturgie-a6` -- `mechanik.tschechow_kandidaten` ist unconditional auf
Deutsch gesperrt (`if sprache.code() != sprache.DEUTSCH: return []`), Padua
laeuft auf Englisch. Siehe Abschnitt 10, Punkt 2.

## 3. Groessen gegen die Basis vom 02.10.2026

Die vier vergleichbaren Dumps (System-Teil ist unabhaengig vom gewaehlten
Fixture-Inhalt -- die Systemanweisung ist fuer jede Gruppe dieselbe; der
Nutzer-Teil ist es **nicht**, siehe Hinweis unten):

| Dump | System vorher | System jetzt | Delta System | Nutzer vorher | Nutzer jetzt | Delta Nutzer |
|---|---|---|---|---|---|---|
| 01-gespraech-phase1 | 26943 | 28705 | **+1762** | 393 | 1657 | +1264 |
| 02-gespraech-phase6 | 31396 | 32431 | +1035 | 2416 | 3066 | +650 |
| 03-kurzgeschichte-phase6 | 14230 | 14226 | -4 | 1500 | 2478 | +978 |
| 04-szene-prosa-phase6 | 13051 | 13052 | +1 | 3002 | 3570 | +568 |

**Die System-Spalte ist die, die echte Prompt-Drift zeigt**, weil die
Systemanweisung nicht vom Fixture-Inhalt abhaengt: Phase 1 ist seit dem
02.10.2026 um **+1762 Zeichen** gewachsen (genau der Wert, den
`scripts/erzeuge_prompts_padua.py` am 05.10.2026 bereits unabhaengig
gemessen hatte, bevor diese Karte existierte -- siehe AGENTS.md, Abschnitt
„Prompt geändert? → Korpus laufen lassen" ist dafuer nicht einschlaegig,
aber der Befund selbst stand schon in der Planung dieser Karte). Phase 6
ist um +1035 Zeichen gewachsen. Die Kurzgeschichte-/Szene-Formblöcke (03,
04) sind praktisch unveraendert (-4/+1) -- ihr Systemteil kommt aus den
Formen-Regelblock-Dateien, die seit dem 02.10. nicht angefasst wurden.

**Die Nutzer-Spalte ist zwischen den beiden Audits NICHT vergleichbar**:
Birk hat fuer diesen Lauf ausdruecklich **realistisches Volumen** verlangt
(>= 34 Zuege je Gruppe statt der viel kuerzeren Vorgaenger-Fixture), also
ist jede Zunahme im Nutzerteil hier **gewollt** und sagt nichts ueber eine
Drift im Produktivcode aus.

Alle anderen 34 Dumps sind `neu` (kein Vorgaenger in der Basis-TSV).

## 4. Token-Anteil je Blockgruppe (Gespraechs-Dumps)

| Dump | Phase | Token gesamt | System | Status | Verlauf | Zusammenfassung |
|---|---|---|---|---|---|---|
| 01-gespraech-phase1 | 1 | 10120 | 9550 | 191 | 319 | 37 |
| 05-gespraech-phase2 | 2 | 11818 | 11200 | 247 | 311 | 37 |
| 06-gespraech-phase3 | 3 | 14616 | 9865 | 246 | 4321 | 160 |
| 07-gespraech-phase4 | 4 | 12470 | 11583 | 518 | 311 | 37 |
| 08-gespraech-phase5 | 5 | 11190 | 10136 | 686 | 307 | 37 |
| 02-gespraech-phase6 | 6 | 11832 | 10792 | 685 | 294 | 37 |
| 09-gespraech-phase7 | 7 | 11670 | 10568 | 741 | 299 | 37 |

**Die Systemanweisung dominiert jeden Gespraechs-Prompt** -- zwischen 84 %
(Phase 3) und 95 % (Phase 2) des Gesamttokenbudgets, in sechs der sieben
Phasen ueber 90 %. Verlauf und Zusammenfassung zusammen liegen meist unter
400 Token, nur Phase 3 (Interviews) zeigt mit 4321 Verlauf-Token einen
deutlich groesseren Anteil -- erklaerbar durch die lange
Interview-Diskussion in der Fixture dieser Phase (siehe Abschnitt 5, Grund
„zeichen"). Das Verhaeltnis ist eine Eigenschaft der echten
Systemanweisung (Basis- + Phasen-Prompt + Profil + ggf. Regie-Zettel), nicht
der Fixture -- ein Datenpunkt fuer die Frage, ob die Systemanweisung
selbst zu lang geworden ist (siehe Abschnitt 10).

## 5. Gemessene Fenstergrenzen

Woertliche Ausgabe von `fixture_padua_voll.fensterbefund()` je Phase:

```
phase=1 gesamt=37 im_fenster=19 zeichen=760 grund=minuten
phase=2 gesamt=37 im_fenster=19 zeichen=736 grund=minuten
phase=3 gesamt=74 im_fenster=19 zeichen=11781 grund=zeichen
phase=4 gesamt=37 im_fenster=19 zeichen=734 grund=minuten
phase=5 gesamt=37 im_fenster=19 zeichen=722 grund=minuten
phase=6 gesamt=37 im_fenster=19 zeichen=686 grund=minuten
phase=7 gesamt=37 im_fenster=19 zeichen=700 grund=minuten
```

Alle sieben Gruppen schneiden messbar (`im_fenster < gesamt`). Sechs der
sieben Gruppen werden durch die **weiche Minutengrenze**
(`kontext.FENSTER_MINUTEN`) begrenzt, nicht durch die Nachrichtenzahl oder
das Zeichenbudget -- bei 37 Nachrichten und `FENSTER_NACHRICHTEN = 20`
waere ohne die Minutengrenze mehr im Fenster. Nur Phase 3 (74 Nachrichten,
wegen der eigens verlaengerten Interview-Diskussion in der Fixture)
schneidet am **Zeichenbudget** (`kontext.FENSTER_ZEICHEN = 12000`) -- genau
der Fall, fuer den Birk das realistische Volumen verlangt hat (00:40:
„gegen eine frische Datenbank zeigt sich keiner der Befunde").

## 6. Mechanische Treffer je Dump

Verdichtet aus `mechanik.md` (vollstaendig im selben Ordner):

- **Deutsche Reste:** 9 von 38 Dumps zeigen Treffer. Zwei Quellen, beide
  identifiziert:
  1. **Die erfundene Interview-Transkript-Fixture** (`Ferzan`/`Leyla`, aus
     `simulation/interviews/set1/2-ferzan-bahnhof.md`) ist selbst auf
     Deutsch verfasst (vermutlich urspruenglich fuer einen deutschsprachigen
     Workshop erfunden) und erzeugt Treffer in jedem Dump, der das
     Transkript lesen laesst oder zitiert: `06-gespraech-phase3`,
     `10-erkenner-verlauf`, `11-erkenner-aufnahme`, `16-verdichter`,
     `21-schaerfung`, `23-sprachprofil`, `24-kernzitate`. **Das ist eine
     Eigenschaft dieses Laufs' Fixture-Material, kein Befund ueber den
     Padua-Bot** -- eine echte englischsprachige Gruppe wuerde kein
     deutsches Interview liefern. Gehoert in Abschnitt 11 (Grenzen).
  2. **Zwei echte, vom Fixture-Inhalt unabhaengige Treffer** in
     `14-diskussion-verdichtung.txt` (Z41: „Das Transkript der Diskussion:")
     und `17-buehnenkarte.txt` (Z49: „Begriffe und Fragen (Phase 1-3):",
     plus die Feldnamen „Stueckkarte:"/„Figuren:"/„Geschichte:"/„Mitschnitt
     des Brainstormings bisher:"). Beide kommen aus **hartcodierten
     deutschen Python-f-Strings** in `interview_theater/diskussion.py`
     (Zeile mit `f"Das Transkript der Diskussion:\n{transkript}"`) und
     `interview_theater/buehnenkarte.py` (mehrere `teile.append(f"...")`) --
     **nicht** aus einer Prompt-Datei unter `sprachen/en/`. Das ist ein
     echter Befund (Kategorie d, Kontextstruktur: ein englischer
     Systemprompt trifft auf deutsche Feldnamen im Nutzerteil, genau die
     Falle aus AGENTS.md „W3"). **Nicht behebbar in dieser Karte**: der Fix
     braucht eine Aenderung an Python-Produktivcode, und diese Karte darf
     ausser an Prompt-Dateien (Task 10) keine Produktivaenderung vornehmen.
     Siehe Abschnitt 10, Punkt 1.
  3. (`NICHTS` in `17-buehnenkarte.txt` ist **kein** Befund -- es ist der
     dokumentierte, absichtlich untranslated Sentinel-Wert aus
     `sprachen/en/prompts/buehnenkarte.md:41`, denselben, den die UX-Regeln
     selbst zitieren: „The bot may say nothing (`NICHTS`)".)
- **UX-Muster:** 12 von 38 Dumps zeigen Treffer, drei Muster:
  - „Yes, save"/„No, change it again" (alle sieben Gespraechs-Dumps plus
    zwei Erkenner-Dumps): **echte Knopfbeschriftungen**
    (`_TEXT_SPEICHERN_KNOPF`/`TEXT_WEITER_KNOPF`/`_TEXT_ANDERS_KNOPF` in
    `sprachen/en/texte.toml:18-19,120`), vom System-Prompt an der Stelle
    zitiert, wo er dem Bot erklaert, welche Knoepfe es gibt -- kein
    Bestaetigungs-Zeremoniell im Fliesstext. Siehe Abschnitt 10, Punkt 3.
  - „ask whether" (mehrfach, z. B. `01-gespraech-phase1.txt` Z289/Z328):
    **Falsch-Positiv** -- jede gefundene Stelle steht in einem **negierten**
    Satz („... ask whether it arrived" nach „you neither have to wait for
    it nor", „Never ask whether an interim result ... should first be
    discussed"). Der Systemprompt verbietet dem Bot genau das, was das
    Muster zu finden vorgibt. Kein Fix noetig -- aber eine bekannte Grenze
    des mechanischen Pruefers (reine Teilstringsuche ohne Negationserkennung,
    siehe Abschnitt 11).
  - „how many scenes" (`07-gespraech-phase4.txt`, `10-/11-erkenner-*.txt`,
    `19-geschichte.txt`): ebenfalls ein **Falsch-Positiv** in gleicher Form
    -- die Stelle im Systemprompt sagt dem Bot, dass die Gruppe die Zahl
    entscheidet und der Bot selbst nie eine Anzahl vorschlaegt
    („the group must decide how many scenes"-aehnliche Formulierung), nicht
    dass der Bot danach fragen soll. Ebenfalls eine bekannte Grenze des
    Pruefers.
- **Frageregeln (nebeneinander lesen):** 14 von 38 Dumps -- alle aus
  derselben System-Prompt-Passage (`sprachen/en/prompts/system.md`, rund um
  „ends with an open question"/„BEFORE the suggestion block"/„that one at
  the end"). Diese drei Zeilen beschreiben dieselbe Regel aus drei
  Blickwinkeln (wo die Frage steht, wie viele es sein duerfen) und sind
  **kein Widerspruch bei genauem Lesen** -- geprueft: „ends with an open
  question" + „that one at the end" sagen dasselbe (am Ende), „BEFORE the
  suggestion block" bezieht sich auf die Position der Frage relativ zu
  einem Vorschlagsblock, nicht relativ zum Nachrichtenende. Keine Aenderung
  noetig; der Pruefer stellt die Zeilen bewusst nur nebeneinander, die
  Lesung sollte das normalerweise bestaetigen -- siehe Abschnitt 7.
- **Dubletten im Nutzertext:** 9 Dumps, ausschliesslich
  „2-4x Place: the railway station" in den Szenen-/Szenenfolge-Dumps --
  **erwartet und harmlos**: mehrere Szenen teilen sich denselben, fixen
  Schauplatz, und das Feld wird je Szene einmal genannt.
- **Verbotene Reste (`VERBOTEN`):** einzig „Mira" in
  `11-erkenner-aufnahme.txt` -- das ist ein alter Platzhaltername aus der
  Pruefer-eigenen `VERBOTEN`-Liste (vermutlich ein Klarname aus einem
  frueheren echten Lauf); die Fixture dieser Karte verwendet ihn nirgends
  als Namen, der Treffer kommt aus dem erfundenen Interviewtext selbst
  (`"Mira zeigt Härte."`-artige Beispielsaetze existieren in diesem
  Transkript nicht -- zu pruefen, ob die `VERBOTEN`-Liste ueberhaupt noch
  zu den Padua-Fixtures passt; auessert sich hier als Dateninkonsistenz der
  Pruefer-Konstante, keine echte Namensverletzung).

## 7. Opus-Befunde je Phase

**Ausstehend: die Opus-Lesung.**

Der Dump-Lauf und der mechanische Pruefer sind vollstaendig und oben
dokumentiert. Die Opus-Lesung (`scripts/pruefe_prompts_lesung.py`, ohne
`--trocken`) ist in dieser Session **nicht zu Ende gekommen** -- nicht,
weil der Proxy unerreichbar ist (eine kleine Testanfrage an
`http://127.0.0.1:28764/v1/messages` beantwortete der Proxy in unter drei
Sekunden korrekt), sondern weil die reale Phase-1-Anfrage (67.412 Zeichen
Nutzertext: UX-Regeln + Rubrik + drei nummerierte Dumps) **wiederholt mit
`ReadTimeout` scheiterte** -- sowohl mit dem Vorgabe-Timeout
(`simulation.claude.TIMEOUT_S = 120.0`, vier Versuche à 120 s) als auch mit
einem eigens verlaengerten Testlauf (900 s Client-Timeout, `wartezeiten`
auf einen Versuch reduziert): der Antwortversuch brach nach rund 245
Sekunden mit demselben Fehler ab. Eine kuenstlich erzeugte, gleich grosse
Fuellanfrage (68.054 Zeichen Lorem-Text, triviale Zusammenfassungsaufgabe)
beantwortete derselbe Proxy dagegen in 2,5 Sekunden -- die Antwortzeit
haengt also nicht an der blossen Zeichenzahl, sondern an der tatsaechlichen
Analyseaufgabe (Widersprueche in UX-Regeln, Rubrik und mehreren
nummerierten Dumps finden und mit woertlichem Zitat belegen), die
offenkundig deutlich laenger braucht, als der lokale Proxy in dieser
Session zulaesst.

**Befehl zum Nachholen** (unveraendert, keine Codeaenderung noetig -- sehr
wahrscheinlich reicht ein Lauf in einer Umgebung mit weniger
Netz-/Proxy-Latenz oder mit mehr Geduld):

```
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-voll
```

**Trockenlauf-Befund** (kein Netz, 0 CHF, lief erfolgreich):

```
phase=1 dumps=3 zeichen=67412 gekappt=nein
phase=2 dumps=2 zeichen=67588 gekappt=nein
phase=3 dumps=3 zeichen=116576 gekappt=nein
phase=4 dumps=7 zeichen=149762 gekappt=nein
phase=5 dumps=5 zeichen=77623 gekappt=nein
phase=6 dumps=8 zeichen=137404 gekappt=nein
phase=7 dumps=10 zeichen=264486 gekappt=ja
```

**Phase 7 wird gekappt**: bei `ZEICHEN_MAX = 240000` fallen einzelne Dumps
der zehn Phase-7-Dumps aus der Lesung heraus (welche genau, haengt von der
alphabetischen Sortierung in `nutzertext()` ab). Das ist im Code selbst
sichtbar gemacht (die Antwort enthaelt den Hinweis „some dumps ... were
truncated") und war laut Plan bereits als `ANNAHME: ungemessen` erwartet --
hiermit gemessen und bestaetigt: **Phase 7 braucht entweder eine hoehere
Kappgrenze oder zwei Teillaeufe**, wenn die Lesung je durchlaeuft. Siehe
Abschnitt 10, Punkt 5.

**Entscheidung nach dieser Karte's eigener Vorgabe:** keine erfundenen
Befunde, keine geschaetzte Lesung. Abschnitt 8 unten ist deshalb leer (kein
Fix ohne eine echte Opus-Lesung als Grundlage), und Abschnitt 9 bleibt ohne
Eintraege aus dieser Quelle. Die beiden echten, unabhaengig von der Lesung
gefundenen Befunde (Abschnitt 6, Punkt 2 der Mechanik) stehen in Abschnitt
10.

## 8. Behoben in diesem Lauf

Keine Fixes in Task 9 selbst (dieser Abschnitt ist fuer Task 10 reserviert,
die auf Basis der Opus-Lesung arbeitet -- ohne sie bleibt dieser Abschnitt
vorerst nur mit den mechanischen Befunden bestueckbar, siehe Abschnitt 6
und 10).

## 9. Liegt bei t_0b702d1d

Keine Eintraege aus dieser Karte (ohne Opus-Lesung keine Kategorie-a/b/c-
Befunde zum Zuordnen). Bekannt und unveraendert: `system.md` und die
Phase-1/2-Prompt-Dateien gehoeren der Parallelkarte und wurden in dieser
Karte nicht angefasst.

## 10. Fuer Birk, hoechstens fuenf

1. **Zwei echte deutsche Leftover-Strings in Python-Produktivcode**
   (`interview_theater/diskussion.py`: `f"Das Transkript der Diskussion:\n{transkript}"`;
   `interview_theater/buehnenkarte.py`: `"Begriffe und Fragen (Phase 1-3):"`,
   `"Stueckkarte:"`, `"Figuren:"`, `"Geschichte:"`,
   `"Mitschnitt des Brainstormings bisher:"`). Beide bauen den Nutzertext
   fuer einen sonst englischen System-Prompt (`diskussion_verdichtung` bzw.
   `brainstorm_karte`) mit hartcodierten deutschen Feldnamen -- genau die
   Falle aus AGENTS.md „W3" (ein englischer Systemprompt mit deutschem
   Nutzertext laesst das Modell leicht deutsch antworten). **Warum nicht
   eindeutig fuer diese Karte:** der Fix ist eine Aenderung an
   Python-Produktivcode (Feldnamen uebersetzen oder durch die
   `sprache.Texte`-Schicht fuehren), und diese Karte darf ausser an
   Prompt-Dateien (Task 10) keine Produktivaenderung vornehmen.
   **Empfehlung:** eine kleine Folgekarte, die beide Stellen auf Englisch
   umstellt (am saubersten ueber `sprachen/en/texte.toml`, analog zu den
   bestehenden `_TEXT_*`-Konstanten). **Kosten:** gering, keine
   Prompt-Verhaltensaenderung, kein neuer Korpuslauf (keine Erkenner-Art
   betroffen).
2. **`37-dramaturgie-a6` ist seit Task 7 komplett aus dem Inventar entfernt**,
   nicht nur als „nicht live" markiert: `mechanik.tschechow_kandidaten`
   liefert fuer jede nicht-deutsche Gruppe unconditional `[]`, bevor
   irgendein Modellaufruf stattfindet -- fuer Padua (Englisch) ist die ganze
   Richter-Frage A6 (Tschechow-Kandidaten) **dauerhaft unerreichbar**, nicht
   nur fuer diese Fixture. **Warum nicht eindeutig:** das ist eine
   inhaltliche Luecke in der Dramaturgie-Pruefung fuer jeden
   englischsprachigen Workshop, keine Kleinigkeit -- entweder braucht
   `mechanik.py` eine englische Fassung der Heuristik (Codeaenderung,
   ausserhalb dieser Karte), oder es ist eine bewusste Entscheidung, dass
   A6 fuer englische Workshops ausfaellt. Aktuell steht das nirgends
   ausserhalb eines Kommentars in `prompt_inventar.py`. **Empfehlung:**
   Birk entscheidet; wenn A6 ausfallen soll, gehoert das als Satz in
   AGENTS.md oder in `dramaturgie/mechanik.py`s Docstring, nicht nur in
   einen Audit-Kommentar. **Kosten:** 0 bis zu einer kleinen Codeänderung,
   je nach Entscheidung.
3. **„Yes, save"/„No, change it again" sind echte Knopfbeschriftungen, die
   im Systemprompt woertlich zitiert werden** -- der mechanische Pruefer
   markiert jeden Treffer als potenzielles UX-Regel-3-Problem
   („Bestaetigungs-Zeremonie"), aber bei genauem Lesen beschreibt der
   Systemprompt dort nur, **welche** Knoepfe existieren, nicht dass der Bot
   eine Ja/Nein-Zeremonie im Fliesstext durchfuehrt. **Warum nicht
   eindeutig:** eine Aenderung am Wortlaut muesste entweder die
   Knopfbeschriftung selbst aendern (`sprachen/en/texte.toml`, betrifft
   Code und UI) oder den Systemprompt so umformulieren, dass klar wird:
   das ist eine Erklaerung der UI, keine Chat-Zeremonie -- beides ist eine
   Entwurfsentscheidung mit mehr als einer sinnvollen Loesung.
   **Empfehlung:** wenn die Opus-Lesung nachgeholt wird (Abschnitt 7),
   zeigt sie vermutlich, ob ein menschlicher Leser diese Stelle tatsaechlich
   als Zeremonie missversteht -- das waere die Grundlage fuer eine
   Entscheidung. **Kosten:** 0 CHF (Lesung ueber das Abo), aber abhaengig von
   Abschnitt 7.
4. **Die Opus-Lesung ist in dieser Session nicht durchgelaufen** (siehe
   Abschnitt 7) -- der lokale Claude-Proxy antwortet auf kleine Anfragen
   sofort, aber auf die reale, komplexe Lesungs-Anfrage durchgaengig mit
   `ReadTimeout`, auch bei stark verlaengertem Client-Timeout (900 s,
   tatsaechlicher Abbruch nach ~245 s). **Warum das Birk betrifft:** ohne
   die Lesung hat diese Karte keine Kategorie-a/b/c/d-Befunde fuer Task 10,
   und der in AGENTS.md vorgesehene feste Abnahmeschritt
   (`docs/flow-audit/vorlagen.md`) kann in dieser Session nicht vollstaendig
   demonstriert werden. **Empfehlung:** den Lauf
   (`python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-voll`)
   in einer Umgebung mit kuerzerer Latenz zum lokalen Proxy nachholen,
   oder -- falls das Timing-Problem reproduzierbar ist -- die Phasen
   einzeln mit `--phase N` fahren (kleinere Einzelanfragen koennten
   schneller durchkommen als alle sieben in Folge). **Kosten:** 0 CHF.
5. **Die Systemanweisung dominiert jeden Gespraechs-Prompt mit 84-95 % des
   Tokenbudgets** (Abschnitt 4) -- Verlauf und Zusammenfassung sind
   durchgaengig klein dagegen. **Warum das Birk interessieren könnte:** das
   ist keine Fehlfunktion, aber ein Datenpunkt fuer die Frage, ob die
   Systemanweisung selbst (Basis- + Phasen-Prompt + Profil) inzwischen so
   gross ist, dass sie den eigentlichen Gruppeninhalt dominiert --
   insbesondere zusammen mit dem gemessenen Drift von +1762/+1035 Zeichen
   seit dem 02.10.2026 (Abschnitt 3). **Empfehlung:** keine konkrete, nur
   der Hinweis, dass dieser Lauf die Zahl zum ersten Mal mit einer
   realistischen Fixture gemessen hat statt sie nur anzunehmen.

## 11. Grenzen dieses Laufs

- Die Dumps entstehen gegen eine **erfundene Fixture**
  (`scripts/fixture_padua_voll.py`), nicht gegen eine echte Gruppe. Das
  Interviewmaterial (`simulation/interviews/set1/2-ferzan-bahnhof.md`) ist
  selbst auf Deutsch verfasst, was die „Deutsche Reste"-Zaehlung in sieben
  Dumps aufblaeht (Abschnitt 6) -- ein Artefakt der Materialwahl, kein
  Befund ueber den Padua-Bot.
- `weg="gebaut"` bei sieben Dumps (`03-kurzgeschichte-phase6`,
  `04-szene-prosa-phase6`, `28`-`32-szene-*`): der Prompt wird aus
  `systemanweisung()`/`baue_nutzertext()` direkt gebaut statt an der
  Transportgrenze abgefangen zu werden -- bei diesen sieben wird nicht
  zwischen Claude- und Infomaniak-Modellwahl unterschieden (die
  `szene_claude.ist_aktiv`-Weiche fehlt in der nachgebauten Fassung, siehe
  Task-7-Bericht).
- **Kein bezahlter Infomaniak-Lauf** -- alles laeuft gegen das
  mitschreibende Double (`scripts/mitschnitt.py`), kein Byte geht ins
  echte Netz.
- **Die Opus-Lesung (Abschnitt 7) ist in dieser Session nicht
  abgeschlossen** -- siehe dort fuer das genaue Fehlerbild und den Befehl
  zum Nachholen.
- `scripts.pruefe_prompts_lesung.ZEICHEN_MAX = 240000` ist, wie im Plan
  selbst vermerkt, ungemessen -- dieser Lauf hat gezeigt, dass Phase 7
  (264.486 Zeichen) tatsaechlich darueber liegt und gekappt wird
  (Abschnitt 7).
- `ANNAHME`: die Live-Envs setzen `IT_SZENE_ANBIETER=claude` und
  `IT_LLM_MODELL=moonshotai/Kimi-K2.6` -- nicht im Code dieser Karte
  gelesen, von Birk oder mit
  `grep -h "IT_SZENE_ANBIETER\|IT_LLM_MODELL" betrieb/padua-gruppe*.env`
  zu pruefen (nicht Teil dieses Laufs).
- Der mechanische Pruefer (`VERBOTENE_UX`, insbesondere „ask whether" und
  „how many scenes") erkennt keine Negation -- beide Treffer in diesem Lauf
  waren Falsch-Positive, weil die Stelle das Gegenteil des Musters anordnet
  (Abschnitt 6). Keine Codeaenderung in dieser Karte (der Pruefer ist ein
  Bericht, kein Gate, und seine Schwellen sind an den Vorgaenger-Dumps
  gemessen, nicht an diesem Fall).

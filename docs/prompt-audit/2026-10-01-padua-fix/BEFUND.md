# Befund: Padua P-Fix -- Profil-Abnahme und Widersprueche c1-c10 (01.10.2026)

Dieser Befund loest `docs/prompt-audit/2026-09-30-padua/BEFUND.md`
Abschnitt c ab. Grundlage: Birks Entscheidungen vom 01.10.2026 (Punkte 1-7,
`hermes/profiles/birk/docs/padua-fabrik/entscheidungen-p.md`) und die
**Code-Wahrheit** fuer c2-c9. Zeilennummern sind die des Stands nach
Commit `4280f51` (nachgemessen, nicht aus dem Plan uebernommen).

## Wie die Dumps entstehen

`python3.11 -m scripts.erzeuge_prompts_padua docs/prompt-audit/2026-10-01-padua-fix`
-- unveraendert wie am 30.09.2026: Wegwerf-Datenbank im Temp-Verzeichnis,
zwei erfundene Gruppen (Phase 1 und Phase 6), Interviewmaterial aus
`simulation/interviews/set1/2-ferzan-bahnhof.md` (frei erfunden), `IT_DB` auf
die Wegwerf-DB, damit kein Regie-Zettel aus `betrieb/` hineinrutscht. **Kein
Modellaufruf** -- der Dump ist reine Textmontage.

Die Zeile `<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->` setzt nur
das Dump-Skript (`MARKE`, `_markiere`); der Bot bekommt sie nie, und
`anweisung.md` traegt sie nicht. Gemessen: sie steht in 01 und 02 je einmal,
in 03/04 nicht (dort gibt es keine Profil-Anweisung); `VORSCHLAG zur Abnahme`
steht in keinem neuen Dump mehr (alt 1/1/0/0).

Zeichenzahlen aus `uebersicht.tsv` beider Verzeichnisse (dieselbe Messung,
`system_zeichen` / `nutzer_zeichen` / `token_gesamt`):

| Dump | System alt (30.09.) | System neu | Nutzer alt | Nutzer neu | Token alt | Token neu |
|---|---|---|---|---|---|---|
| 01 Gespraech Phase 1 | 26 467 | 26 965 | 393 | 393 | 8 953 | 9 119 |
| 02 Gespraech Phase 6 | 30 681 | 31 584 | 2 421 | 2 416 | 11 034 | 11 333 |
| 03 Kurzgeschichte Phase 6 | 12 145 | 14 205 | 1 433 | 1 433 | 4 525 | 5 212 |
| 04 Einzelszene Prosa Phase 6 | 11 034 | 13 094 | 2 535 | 2 702 | 4 523 | 5 264 |

(Der Plan nannte als Altwerte 26 594 / 30 819 / 12 300 / 11 174; das ist
eine andere Zaehlung als `uebersicht.tsv`. Verglichen wird hier tsv gegen
tsv.) Die Systemteile wachsen aus zwei Gruenden: c1-c7 **ergaenzen** Saetze
statt nur zu streichen (Zuordnung Ganz-Lauf/Einzelszene in `formen/prosa.md`,
die Ausnahme in `phasen/6.md`, die USA-Frage an beiden Stellen, der
Tells-Kopf); und in 03/04 stehen neu die Tells 31-34 (Gedankenstrich,
„not X but Y", …) aus Karte R, die erst nach dem Altdump gemergt wurde
(`f37e048`) -- keine Aenderung dieser Karte. Der
Nutzertext von 02 wird um 5 Zeichen kuerzer (`KERNPAKET_KOPF`, c8: „core
theme" -> „story"). Der von 04 wird um 167 Zeichen laenger: neu steht dort der
Block „How long this scene should be: About 250 words …" (Laengen-Budget aus
`[laengen]` des Padua-Profils, Karte R) -- keine Aenderung dieser Karte, der
Altdump vom 30.09. ist nur aelter als dieser Stand.

**Nachtrag Gesamtreview (02.10.2026):** die Dumps 01 und 02 wurden nach den
Korrekturen an `en/system.md:39-40` und `en/phasen/6.md:69` dieses Reviews
neu erzeugt (`python3.11 -m scripts.erzeuge_prompts_padua
docs/prompt-audit/2026-10-01-padua-fix`), 03 und 04 bleiben zeichengleich
(sie lesen weder `system.md` noch `phasen/6.md`). „System neu"/„Token neu"
oben sind bereits die Werte **nach** diesem Review (01: 26 891 -> 26 965
Zeichen, 02: 31 503 -> 31 584 Zeichen); die Akzeptanz-Greps aus Teil C wurden
gegen den neu erzeugten Stand erneut gefahren, Ergebnis unveraendert 0.

## Teil A -- Birks Punkte 1-7

| Punkt | Entscheidung | Wo umgesetzt |
|---|---|---|
| 1 Spielorte | offen, Orte waehlt die Gruppe aus den Interviews; „Venice" raus | `profil.toml` `[orte] beschreibung` |
| 2 Ausgeschlossene Orte | unveraendert, nur ANNAHME weg | `profil.toml` `[orte] ausgeschlossen` |
| 3 Werkschau | woertlich Birks Text; kein Teatro Verdi, keine KI-Projektion | `profil.toml` `[orte] auffuehrung`, dazu `zielgruppe.traeger` (D5) |
| 4 Beispielorte | raus, im Prompt `<place>` | `[orte] beispiele = []` + 8 Stellen in `sprachen/en/prompts/` (Commit `8ab5711`) |
| 5 Konfliktrahmen | leer; Teilsatz faellt weg | `[konflikt] erlaubt = ""`, `workshop.platzhalter` (`konflikt_erlaubt_strich`/`_klammer`), `en/prompts/rahmen.md`, `rahmen-kurz.md` |
| 6 Konflikt-Ausschluesse | nur „No interviewed person recognisable by name or address" | `[konflikt] ausgeschlossen` |
| 7 Profil-Anweisung | Schluss woertlich ersetzt | `workshop/padua-2026/prompts/anweisung.md` |

Alle sechs `# ANNAHME (unbelegt)`-Kommentare sind entfernt; `profil.toml`
nennt je Angabe „Birk 01.10.2026 (Punkt N)".

## Teil B -- die Widersprueche c1 bis c10

| Nr. | Satz, der **bleibt** | Satz, der **geht** | Code-Beleg |
|---|---|---|---|
| c1 | `en/system.md:74-76` „two to three options" (neutral: „grow out of their answer and out of their material"); `en/system.md:67` jetzt „One question, and two to three options to choose from"; die Winkel-Regel steht **nur** in `anweisung.md` | `en/system.md:67-68` „Suggest ONE thing, not three to choose from"; `:72-76` „variants of the **SAME** idea … not about yours" (D6) | entschieden durch Birks Punkt 7; `anweisungen.py:368-370` haengt `anweisung.md` als **letzten** Block vor dem Regie-Zettel an (SPEC § 6.1). Commit `80d5615` |
| c2 | `en/system.md:38` („already in the scene sequence **suggestion**"), `:17` „still without a form" | `en/phasen/6.md:34` „The form for each scene is **already settled** … decided with the story" -> „NOT settled yet … chosen scene by scene in the polish phase, by button". **Review-Nachtrag (Commit `3232ba9`):** im selben Sinn `en/phasen/6.md:45-46` „its number, its order **and its forms** count" -> „its number and its order count" und `:80-81` „Order, casting, place **and form** are decided" -> „…; the form is chosen in the polish phase" | `kurzgeschichte.py:174` („`form` bleibt leer: sie entscheidet die Gruppe im Feinschliff"), `szenenfolge.py:313-317` (`form_vorschlag`, „Die Form wird NICHT gesetzt"), `szene.py:2241-2246`. Commits `b713779`, `3232ba9` |
| c2 (Gesamtreview-Fund) | `en/system.md:39-40` jetzt „A scene without a form is not written **as a theatre text**; in phase 6 it is first told as a story, without a form" | `en/system.md:39-40` zuvor uneingeschraenkt „A scene without a form is not written" — falsch fuer Phase 6, wo eine Szene ohne Form als Geschichte entsteht | `szene.py:685-693` (`pflicht`: `form` wird aus `PFLICHTFELDER` genommen, solange `schreibt_prosa(conn, chat_id)` gilt). Minimal umformuliert, kein Widerspruch zu `:17`/`:37-39` oder `phasen/6.md:34` — die bleiben wie sie sind |
| c3 | `en/system.md:378` („when entering the scene phase, with two buttons") | `en/system.md:322` „asked by the scene run, not by you" als einzige Antwort -> jetzt beide Wege, Eintritt zuerst | `knoepfe/stationen.py:171-189` (Eintritt in `PHASE_SZENEN`), `szene.py:2488-2496` (nur noch Rueckfall, wenn die Frage noch offen ist). Commit `9bd4b86` |
| c4 | `en/phasen/6.md:4` jetzt „the story is written -- in ONE go, as one continuous short story" | `en/phasen/6.md:4` „the texts are written -- **scene by scene**" | `kurzgeschichte.py:72-82` (`ANWEISUNG`: EINE zusammenhaengende Kurzgeschichte), `szene.py:2241-2246`, `workshop/padua-2026/phasen.toml:47` („still without a form", unveraendert). Commit `b713779` |
| c5 (**entschieden am 02.10.2026** -- Birk: fest bei Szenenfolge; siehe `../2026-10-02-padua-p2/BEFUND.md`) | `texte.toml:1116-1119` (`kurzgeschichte.ANWEISUNG`: „You choose the number of sections yourself … a suggestion, not a requirement"); `en/formen/prosa.md:28-30` sagt jetzt dasselbe, mit „Where the number IS fixed, the job says so" | `en/formen/prosa.md:28` „**If a scene sequence already exists, it is binding**" | `kurzgeschichte.py:79-82`, `lege_szenen_an` gleicht **ergaenzend** ab (`kurzgeschichte.py:168-186`); wo die Zahl bindet, sagt es der Auftrag (`texte.toml:730` `kuerzung.TEXT_NOTIZ_PROSA`, `nachpass.py:350-356`). Commit `96a5df7`. **c5 wird durch diesen Review nicht zurueckgenommen** -- die Entscheidung bleibt die freie Abschnittszahl; „vorlaeufig" heisst nur, dass die Folgefragen in Restspannung 6 noch offen sind |
| c6 | `kurzgeschichte.ANWEISUNG` fuer den Ganz-Lauf; `en/formen/prosa.md` „Your output" (`:61-64`) fuer die **Einzelszene** -- beides jetzt ausdruecklich zugeordnet | der unbedingte Anspruch „Exactly in this form" fuer jeden Auftrag, und „only `Scene N — Title`" fuer den Ganz-Lauf. **Review-Nachtrag (Commit `92d6edd`):** `en/formen/prosa.md:13-14` „This file is the **whole** instruction for this step" -> „This file, together with the job around it, is the instruction for this step" | `kurzgeschichte.zerlege` liest nur Ueberschrift + `ZUSAMMENFASSUNG:` (`kurzgeschichte.py:137-165`), `szene.py` liest die vier Pflichtzeilen; `formen/prosa` steht nie allein: `kurzgeschichte.py:235-248` (ANWEISUNG + prosa + tells), `szene.py:351-354` (prosa + tells). Commits `96a5df7`, `92d6edd` |
| c7 | die Tells gelten als Sprachhygiene auch fuer Prosa (`en/theater-tells.md:8-12`), Eintrag 11 jetzt „(not in a prose job -- there it is the point)" (`:65`) | `en/theater-tells.md:7` „**not in prose**, not in an essay"; Eintrag 11 ohne Textsortenangabe | `szene.py:338-343` („Die Tells bleiben: sie sind Sprachhygiene und gelten fuer jeden Text"), `szene.py:351-354`, `kurzgeschichte.py:246-248`. Commit `420f945` |
| c8 | `en/system.md:50` („we're still on the core theme") -- das Wort loest auf Phase 4 auf | `texte.toml:848` `["kontext"] KERNPAKET_KOPF` „come from the **core theme** and this selection" -> „from the **story**"; `en/system.md:44` „station 5" -> „station 4" | `kontext.py:469-472` + `:549-551` (Block entsteht aus der Geschichte, Kernthema nur wenn gesetzt), `workshop/padua-2026/phasen.toml:35-36` (`core theme`/`conflict`/`story` = Phase 4; Phase 5 = Sharpening, Z. 38-42), `tests/test_profile_geruest.py` Fall `("core theme", 4)`. Commit `8138ed3` |
| c9 | der Figurenhinweis im Nutzertext (er ist richtig und gewollt) | `en/phasen/6.md:67` „**No** question about a character's way of speaking" (ohne Ausnahme) -> jetzt „You don't reopen …" plus genau eine Ausnahme fuer den Hinweis (`:69-73`) | `kontext.py:788-798` (`_baue_figurenhinweis` ab `kernpaket_erlaubt`, `kontext.py:565-566`/`:583-590`, also ab Phase 5), `texte.toml:851`, `knoepfe/figuren.py:357-368`. **Geteilt mit Karte M1-Fix:** `texte.toml:926`/`:934` (`["szene"] FIGUREN_KOPF_OHNE_STIMME`) und `szene.py` gehoeren dort hin und sind hier **nicht** angefasst. Commit `b713779` |
| c10 | — | **entfaellt durch Birks Punkt 3**: „AI-generated projected backgrounds" steht nicht mehr im Profil, der Widerspruch zu „The scenes need no set" ist weg. Die zweite Haelfte („Places: places from everyday life", Dopplung in `rahmen-kurz.md`) loest der neue `orte.beschreibung`-Wert mit auf: „Places: wherever the group decides, …" | `profil.toml` `[orte] auffuehrung`, `[orte] beschreibung`; Greptabelle unten (`projected backgrounds` alt 1/2/0/0, neu 0) |

### Bekannte Restspannungen, bewusst nicht in dieser Karte geloest

> **Geloest am 02.10.2026:** die Punkte 1, 2, 4, 5, 6, 7 und 8 sind
> entschieden und umgesetzt -- was blieb, was ging und mit welchem
> Code-Beleg, steht in `docs/prompt-audit/2026-10-02-padua-p2/BEFUND.md`.
> Punkt 3 war schon vorher behoben. Die Liste unten bleibt als Stand von
> vorher stehen.

1. **`en/phasen/1..7.md` „(variants of the same idea, title — description)"**
   (`1.md:20`, `2.md:31`, `3.md:57`, `4.md:94`, `5.md:33`, `6.md:56`,
   `7.md:31`). Die Karte nennt fuer c1 nur `system.md`. Aufgeloest wird es
   ueber die Position: `anweisung.md` steht hinter der Phasenanweisung
   (`anweisungen.py:368-370`) und gilt gegen die aelteren Formulierungen.
2. **`texte.toml:932` `["szene"] KERNPAKET_KOPF`** („filtered by the core
   theme") nennt weiter das Kernthema. Das ist der Szenen-Prompt, M1-Zone;
   D8 zieht die Grenze bei `:848`.
3. **Behoben im Gesamtreview (02.10.2026).** `en/phasen/6.md:69` sagte „The
   speech style was decided in phase 4" gegen `knoepfe/figuren.py:362-368`
   (`ebene2_erlaubt`: Sprechweise und Interviewzuordnung erst ab Phase 5, nicht
   Phase 4). Der Satz stand im Zusammenhang „nicht wieder aufmachen" und war im
   Ergebnis richtig (vor Phase 6 entschieden), nannte aber die falsche Phase --
   jetzt „decided before this phase".
4. **Deutsche Seite driftet** (deutsche Prompts sind fuer diese Karte tabu):
   `interview_theater/prompts/system.md:46` „Station 5" fuer den Konflikt
   (englisch jetzt Station 4); `kontext.py:452-456` deutscher
   `KERNPAKET_KOPF` „kommen aus dem Kernthema" samt Kommentar davor
   (englisch jetzt „story"); `interview_theater/prompts/formen/prosa.md:29`
   „Steht schon eine Szenenfolge, ist sie verbindlich" (englisch jetzt
   Anregung, c5). Dortmund bleibt dadurch bitgleich, aber die beiden
   Sprachfassungen sagen hier Verschiedenes.
5. **OFFENE FRAGE fuer Birk -- Nachpass ohne Abschnittszahl.**
   `nachpass.py:315-326` baut die Regie-Notiz des Prosa-Nachpasses: ist die
   Geschichte zu lang, steht `kuerzung.notiz_fuer_prosa(anzahl)` darin und
   bindet die Abschnittszahl; laeuft der Nachpass **nur wegen des
   Sprachpasses** (`sprachpass.notiz`), nennt die Notiz die Zahl **nicht**.
   `nachpass.py:350-356` verwirft aber jeden Lauf mit anderer Abschnittszahl.
   Vorher deckte die alte Regel „If a scene sequence already exists, it is
   binding" in `formen/prosa.md` diesen Fall mit ab; seit c5 sagt die Datei
   „Where the number IS fixed, the job says so" -- und dieser Auftrag sagt es
   nicht. Folge: ein reiner Sprachpass-Lauf kann die Abschnittszahl aendern
   und wird dann still verworfen (Vorfall `VORFALL_ABSCHNITTSZAHL`, die Gruppe
   merkt nichts, der Text bleibt wie vorher). Die Behebung laege in
   `texte.toml`/`sprachpass`-Notiz oder `nachpass.py` (die Zahl auch dort
   nennen) und ist nicht Teil dieser Karte.
6. **OFFENE FRAGE fuer Birk (zweite) -- c5 ist vorlaeufig, nicht entschieden.**
   `en/formen/prosa.md:28-33` sagt seit c5 „You decide the number of sections
   from the story" (frei, `kurzgeschichte.py:79-82`), aber `en/phasen/6.md:44-50`
   sagt im selben Atemzug weiter „its number and its order count" -- einmal
   frei, einmal bindend, fuer denselben Lauf. Dazu kommt ein Code-Befund, der
   c5 nicht widerlegt, aber verschaerft: `kurzgeschichte.lege_szenen_an`
   (`kurzgeschichte.py:176-180`) gleicht nur **ergaenzend** ab und laesst
   ueberzaehlige, bereits geplante Szenen unberuehrt stehen, waehrend
   `phasen.py:381-383` fuer Phase 7 Prosa fuer **jede** geplante Szene
   verlangt. Schreibt das Modell bei einer geplanten Szenenfolge von 6 nur 4
   Abschnitte, bleiben 2 Szenen ohne Prosa stehen und Phase 7 ist blockiert,
   ohne dass irgendwo ein Vorfall oder eine Zeile im Chat das sagt. Dazu
   driftet Deutsch/Englisch (Restspannung 4): `interview_theater/prompts/
   formen/prosa.md:29` sagt weiterhin „Steht schon eine Szenenfolge, ist sie
   verbindlich" -- DE und EN sagen hier Verschiedenes.
   **Vorschlag, nicht entschieden:** entweder gilt die Zahl als bindend,
   sobald eine Szenenfolge existiert (die alte Regel der Sache nach wieder
   einsetzen -- dann waere auch `phasen/6.md:44-50` wieder durchgehend wahr),
   oder, falls die Zahl frei bleiben soll, muss `lege_szenen_an` ueberzaehlige,
   prosalose Szenen weich loeschen statt sie stehen zu lassen (Code, eigene
   Karte). Die bestehende Nachpass-Offene-Frage (Punkt 5 oben) gehoert zur
   selben Entscheidung: beide drehen sich darum, was gilt, wenn die
   tatsaechliche Abschnittszahl von der geplanten Szenenfolge abweicht.
7. **Vorbestehend, nicht behoben: `en/phasen/6.md:9-13` widerspricht der
   eigenen Phasenzusammenfassung.** Der Absatz „**A script is created.** First
   a script is written (spoken-theatre form following the Herkules measure);
   how it is staged ... the team decides in rehearsal" beschreibt das Schreiben
   eines **Buehnentexts** nach dem Herkules-Mass -- im selben Dokument sagen
   aber `:3-5` und `en/formen/prosa.md:27` ausdruecklich das Gegenteil: Phase 6
   schreibt EINE zusammenhaengende Kurzgeschichte in **einem** Zug, als Prosa,
   und „The Herkules measure doesn't apply here either." Nicht Teil dieser
   Karte (die Karte nennt fuer `phasen/6.md` nur `:34`, `:45-46`, `:69`,
   `:80-81`); Folgekarte.
8. **Vorbestehend, nicht behoben: `en/phasen/6.md:96-104` beschreibt den
   Szene-fuer-Szene-Ablauf von Phase 7, nicht den von Phase 6.** „Result of the
   phase: a text for every scene ... Each scene is introduced individually --
   with 'Yes, write it', 'Plan it differently', **'Change form'** and 'Skip'.
   Under a finished scene text there are 'Looks good', 'No, change it again',
   'Rewrite' and 'Next scene'." Phase 6 schreibt laut c4/c2 EINE Kurzgeschichte
   in einem Lauf und kennt keine Form je Szene (die waehlt erst der
   Feinschliff) -- die Knopfliste mit „Change form" und der Einzelszenen-Flow
   gehoert zu Phase 7. Nicht Teil dieser Karte; Folgekarte.

## Teil C -- die Greptabelle (Positivkontrolle alt -> neu)

Gemessen mit einem Python-Skript ueber beide Verzeichnisse
(`docs/prompt-audit/2026-09-30-padua/` = alt, `2026-10-01-padua-fix/` = neu);
SYSTEM-Teil = alles vor `=== NUTZER`.

Im **SYSTEM**-Teil, Muster
`bus stop|piazza|café|station concourse|\bthe station\b|\(station,`
(ohne Gross/Klein-Unterscheidung):

| Dump | alt | welche Treffer (alt) | neu |
|---|---|---|---|
| 01 | 3 | `bus stop` (system.md:160), `the station` (:201), `bus stop` (:318) | 0 |
| 02 | 4 | dieselben drei plus `bus stop` (phasen/6.md:31) | 0 |
| 03 | 1 | `station concourse` (theater-tells.md:64) | 0 |
| 04 | 1 | `station concourse` (theater-tells.md:64) | 0 |

`szene.md:111-112` ist in keinem dieser vier Dumps messbar: Dump 04 ist ein
**Prosa**-Lauf, und `szene.systemanweisung(PROSA)` laesst `szene.md` weg
(`szene.py:351-354`). Die beiden Stellen sind trotzdem geaendert -- gesichert
wird sie durch `test_kein_englischer_prompt_nennt_einen_beispielort`.

Auf der **ganzen** Dump-Datei (Treffer je Datei 01/02/03/04):

| Muster | alt | neu | Art |
|---|---|---|---|
| `Teatro Verdi` | 2/3/0/0 | 0/0/0/0 | Positivkontrolle |
| `projected backgrounds` | 1/2/0/0 | 0/0/0/0 | Positivkontrolle |
| `glorification` | 1/2/0/0 | 0/0/0/0 | Positivkontrolle |
| `ONE thing` | 1/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `variants of the group's own idea` | 1/1/0/0 | 0/0/0/0 | Positivkontrolle |
| `Venice` | 1/2/0/0 | 0/0/0/0 | Positivkontrolle |
| `VORSCHLAG zur Abnahme` | 1/1/0/0 | 0/0/0/0 | Positivkontrolle (Dump-Marker) |
| `-- \.$` / `serious \(\)` | 0/0/0/0 | 0/0/0/0 | **keine** Positivkontrolle -- im Altstand war `konflikt.erlaubt` gefuellt, das Muster konnte nie anschlagen. Es sichert den **neuen** Stand |
| `{{` | 0/0/0/0 | 0/0/0/0 | wie oben: Dauerzusicherung |

**Praemisse der Karte korrigiert.** Der in der Karte genannte Grep
`bus stop|piazza|café|station` -> 0 kann so nicht gelten. Gemessen, ganze
Datei, ohne Gross/Klein, **Zeilen** mit Treffer: alt 12/17/5/7, neu
9/13/4/6 (Vorkommen: alt 12/19/7/9, neu 9/15/6/8):

1. „station" heisst in diesen Prompts auch **Arbeitsphase** -- `system.md:7`
   („seven stations"), `:29` („in station 4"), `:44`, `:53`. Das ist der
   grosse Teil der verbleibenden Treffer.
2. Das Fixture-Interview von `erzeuge_prompts_padua.py` spielt an einem
   Bahnhof („the railway station", „the station café") -- **Nutzertext**,
   erfundenes Material der Gruppe, und es bleibt legitim dort stehen.
3. „café" steht aus demselben Grund im Nutzertext von 02/03/04.

Deshalb die oben gefahrene Fassung: engeres Muster, und nur auf den
SYSTEM-Teil -- dort ist das Ergebnis 0/0/0/0.

## Teil D -- Profilpruefung

```
$ python3.11 -m scripts.pruefe_profil padua-2026
Workshop-Profil padua-2026
padua-2026: in Ordnung
$ python3.11 -m scripts.pruefe_profil dortmund-2026
Workshop-Profil dortmund-2026
dortmund-2026: in Ordnung
```

`scripts/pruefe_profil.py` prueft seit dieser Karte die **wirksame**
Prompt-Ebene (Profil > Sprache > Repo, Commit `d998db5`) -- vorher sah es die
englische Schicht nie an und pruefte dafuer deutsche Dateien, die unter
`sprache.code = "en"` niemand liest.

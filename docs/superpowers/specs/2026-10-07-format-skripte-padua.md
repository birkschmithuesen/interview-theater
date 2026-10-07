# Format-Skripte für die drei Padua-Gruppen — Design

Stand: 07.10.2026, ~17:15 (Fassung 2, mit Birks Nachtrag ~17:00) · Autor:
cc-formatspec (nach `brainstorming-to-spec`; Fragen nicht direkt gestellt,
sondern in Abschnitt 7 gesammelt) · Basis: Branch `spec-format-skripte` auf
`90e1d52` · Live-DB `betrieb/padua.db` nur `?mode=ro` gelesen (G1/G2 Stand
~16:17, G3-Format nach Robos Schärfung 16:45 neu gelesen).

**Ziel (Birk 07.10.2026 ~16:50):** Für G1, G2, G3 entsteht in Phase 7 ein
Skript **im Format, das die Gruppe gewählt hat**, kein Sprechtheater-Dialog.
Nur diese drei Gruppen, kein Generalumbau, heute Abend in ≤ 4 h baubar.

**Birks Nachtrag (~17:00), eingearbeitet:**
- **G1** braucht NUR einen Sprechtext für Szene 2 *Le voci*: nach
  Themen-Abschnitten (die „Silos" der Gruppe), Zitate wörtlich mit
  Interviewnummer, Übergänge Erzählung → Zeugnis, Englisch. Szene 1 und 3
  sind musikalisch/rituell und bekommen **kein Skript**. Kein Setlist- oder
  Partitur-Artefakt.
- **G2** Versuchsanordnung + Rollenanweisungen + Positionskarten + Drehplan:
  vermutlich richtig → in 2.2 bestätigt und präzisiert.
- **G3** Spurenpartitur nur „vielleicht“ → drei Varianten als **Frage F1**.

**Status:** Entwurf, wartet auf Birks Antworten. Phase 2 (`writing-plans`)
erst nach Freigabe.

---

## 1. Ist-Stand (am Code und an der Live-DB nachgeprüft)

### 1.1 Schreibweg

- **Phase 5** (Prosa-Entwurf, `entwurf.py`): je Szene `szene.starte(_AUFTRAG_PROSA)`
  → `szene.prosa`. Weiter geht es mit `entwurf.erste_offene_szene`, also mit
  der ersten Szene ohne `entwurf_bestaetigt_am` (`entwurf.py:333`).
- **Phase 6** (Rewrite, `ueberarbeitung.weiter_6`): erst das Ganze
  (`kurzgeschichte.starte(vorlage=True)`, bestätigt über `gesamttext_fixiert_am`),
  dann je Szene. „Aktuell“ ist die erste Szene ohne
  `ueberarbeitung_bestaetigt_am` (`ueberarbeitung.aktuelle_szene`, :160-188).
- **Phase 7** (`weiter_7`, :429): erst die Formwahl je Szene in EINER Antwort
  (`sende_formwahl` :379; Erkenner `formen_setzen` → `_wende_formen_an` :724),
  dann die Sprechweisen. Danach wird je Szene ohne `fertig_am`
  `szene.starte(_AUFTRAG_BUEHNE)` aufgerufen und schreibt nach `szene.volltext`.
  Die Prosa geht dabei als bindende Vorlage mit (`VORLAGE_KOPF`, „Translate it
  into the form …“).
- **Systemanweisung** im Theatertext (`szene.systemanweisung`, `szene.py:326-381`):
  - `szene.md` mit den Sprechtheater-Regeln (Repliken, „characters have to
    sound audibly different“);
  - `formen/<form>.md`;
  - Stil;
  - `theater-tells`.

  Im Prosalauf (Phase ≤ 6, `szene.schreibt_prosa`) gelten nur
  `formen/prosa` + `theater-tells`.
- **Die Formliste kommt aus dem Profil:** `workshop/padua-2026/formen.toml`
  (dialog, monolog, chor, lied, rap).
  - Die Regelblöcke lädt `anweisungen.hole_optional` in dieser Reihenfolge:
    `workshop/<p>/prompts/` → `sprachen/en/prompts/` → `prompts/`.
  - Eine unbekannte Form fällt still auf `dialog` zurück (`szene.formdatei`).
- `phasen.voraussetzungen[7]`: alle Szenen haben Prosa oder Volltext
  (`phasen.py:438`).
- `arbeitsstand.format` liest der Schreibweg **nicht** (`szene.py:909`). Es
  erscheint nur im Vorspann und Textbuch, auf der Workbench und bei Richter A11.
- Der Formberater wirkt nur im Chat-Prompt und auf der Workbench.
- **Textbuch** (`szenenfolge.textbuch`, :911): Vorspann, dann je Szene Kopf,
  Feldblock und `volltext`.
- **Prüflauf** (`prueflauf.py:50-55`):
  - Geschichte: a2/a6/a9/a11;
  - Prosaszene: b1/a10;
  - Bühnenszene: a10 (Materialtreue) + c1 (Stimme: Zeilen ohne Namen den
    Figuren zuordnen).

### 1.2 Hart kodierte Formlisten (müssen bei neuer Form mit)

1. `workshop/padua-2026/formen.toml` (+ `anzahl_wort`)
2. die Regelblock-Datei (`scripts/pruefe_profil.py:170-176` verlangt sie)
3. `sprachen/en/prompts/system.md:64` (die fünf Formen stehen wörtlich darin)
4. `szenenfolge.py:414` `_FORMEN`, `_FORM_AUS_EN` :432; der Test
   `tests/test_formabfolge.py:42` verlangt Gleichheit mit `szene.FORMEN`
5. `web.py:910-920` `FORM_BESCHRIFTUNG`, `texte.toml:1881`, `:2016`
   (Test `tests/test_web_sprache.py:130`)
6. `vorspann.py:244-250` (`texte.toml:918`)
7. `dramaturgie/mechanik.py:670` `_NICHT_DIALOG`, :1118 `_FORM_BESCHRIFTUNG`
   (`texte.toml:1595`)
8. `stile.py:83-96`: kein Eintrag heißt kein Stilvorschlag, das ist gewollt
9. `profil.toml [laengen.rahmen]`

### 1.3 Die drei Gruppen (Live-DB; alle in Phase 5, noch ohne Prosa und ohne Volltext)

**G1 (`7000000000000`)**
- **Format:** Konzertperformance mit Dokumentarmaterial, durchkomponiert. Vier
  Performer:innen spielen sich selbst, postdramatisch, „built on the home
  chord (tonic)“, Ritual am Schluss.
- **Übersicht/Logline:** fixiert um 14:11.
- **Szenen:** 3, nämlich *Tornare a casa* / *Le voci* / *Il rituale*.
  `kernsaetze` von Szene 2 ist voll mit italienischen Interviewzitaten, nach
  Silos geordnet: was ist Zuhause; Gerüche, Klänge, Farben; was tust du, um
  dich zuhause zu fühlen; was würde dein Zuhause sagen; Weggehen.
- **Gruppe 13:30:** „Szene 1 und 3 brauchen keine Interviews, nur die Mitte.“
- **Gruppe 13:47/13:49:** wünscht einen „sensorischen, nicht beschreibenden“
  Text mit den Interviews nach Themen, „in italiano … per la performance“.
  Dagegen steht Birks Nachtrag: Englisch (→ F2).

**G2 (`…001`)**
- **Format:** „Short documentary film / social experiment“, Titel „JAMM'IA“.
- **Rahmen:**
  - Bartisch nahe der Uni; die Moderatorin sitzt.
  - Arlecchino rekrutiert: zuerst die Mitspielenden „als wären sie Fremde“,
    dann eine echte Person („du wärst der/die Letzte“).
  - Ein Themen-Topf enthält Themen aus den Interviews.
  - Die Runde vertritt eine gemeinsame Meinung; beobachtet wird, ob die
    fremde Person bei ihrer eigenen bleibt.
- **14:40:** Das Schild fällt weg, nur Arlecchino zieht Leute an.
- **Szenen:** 5, nämlich *inizio / reclutamento / l'ultimo posto /
  discussione / rivelazione*, jeweils nur mit einzeiligem `was_passiert`.
- **Figuren:** Moderatorin, Arlecchino, Influencer 1–3.
- **Kamera:** Der Rahmen sagt „eine:r filmt als Passant:in“, aber alle fünf
  sind besetzt. Wer filmt, muss die Gruppe beantworten, nicht Birk.
- **Spielort** draußen, deshalb ist nach Birks Regel Italienisch erlaubt.

**G3 (`…002`)**
- **Format** (geschärft 16:45): „Live immersive performance among a standing
  audience, inside a video-and-sound environment: five performers … carry
  documentary/verbatim testimonies … as very short scenes, monologues and
  stories (whispered one-to-one, microphone moments, small happenings) while
  the projection and the sound carpet of questions run on the back wall“.
- **Szenen:** 6, als Welle: *The First Press / Slow Start / Fast Rise / The
  Dip / Second Rise / The Last Question*.
- **Festlegungen:**
  - Der Knopf startet, danach läuft alles autonom.
  - Ende: projizierte Frage im Wortlaut, zweiter Knopfdruck, alles aus,
    Dunkel.
  - Kurze Szenen überlappen; tiefere Zeugnisse unterbrechen sie.
  - Drei Modi, fließend gemischt.
- **Figuren:** Voce 1–5 als Funktionen.

---

## 2. Das Endprodukt je Gruppe

Gemeinsam ist allen drei: Niemand spielt eine erfundene Figur. `szene.md`
(Repliken, hörbar verschiedene Figuren) und Richter c1 passen deshalb auf
keine der drei Gruppen. Die Textteile kommen wörtlich aus den Interviews.

### 2.1 G1 — Sprechtext *Le voci* (Form `zeugnistext`, „Testimony text“)

**Nur Szene 2.** Begründung aus dem Katalog:
- *dokumentartheater*: „no invention, only re-arrangement“;
- *verbatim-theatre*: „exact recorded words“;
- *konzertperformance*: Musiker:innen „perform as themselves … not a plot“.

Die Musik schreibt die Gruppe selbst, also ist der einzige Text, den der Bot
liefern muss, das Gesprochene.

Aufbau:

```
ABSCHNITT 1 — What home is
[Performer 3, erzählend, eigene Worte, 1–3 Sätze, Englisch:
 Hinführung, warum diese Frage]
«<Zitat, wörtlich>» — Interview N
«<Zitat, wörtlich>» — Interview M
[Übergang: ein Satz Erzählung, der ins nächste Zeugnis führt]
...
ABSCHNITT 2 — Smells and sounds
(Hier geht der Kaffee durch den Halbkreis.)   ← nur Aktionen aus Festlegungen
...
```

Regeln für den Formblock:
- Die Abschnitte sind die Silos der Gruppe; die Reihenfolge folgt `was_passiert`.
- Jedes Zeugnis steht mit Interviewnummer da, nie mit einem Namen.
- Zwischen den Zeugnissen stehen kurze Erzählbrücken der Performer:innen in
  eigenen Worten, als Performer-Funktion und nicht als Figur.
- Keine Musikangaben außer einer Zeile „(music continues)“, wo die Gruppe es
  festgelegt hat.
- Nichts erfinden.
- Sprache Englisch; zur Form der Zitate → F2.

**Der bestehende Weg kann das fast:** Prosa (Phase 5/6) → Bühnentext einer
Szene (Phase 7). Es fehlen drei Dinge:
1. eine Form mit passendem Regelblock, ohne die Dialogregeln aus `szene.md`
   (5.2);
2. Szene 1 und 3 als „kein Text nötig“ markieren, damit Phase 5, 6 und 7
   nicht an ihnen hängen (5.3);
3. c1 abschalten.

Die Prosa von Szene 2 ist als Ablaufbeschreibung der Silos brauchbar und
dient A10 als Vorlage.

### 2.2 G2 — Versuchsanordnung (Form `versuchsanordnung`, „Experiment setup“)

**Bestätigt**, mit einer Präzisierung: Es braucht keinen eigenen
Gesamtlauf, das Artefakt verteilt sich auf die fünf Momente. Begründung aus
dem Katalog:
- *unsichtbares-theater*: „scripted but disguised as reality“;
- *soziales-experiment-als-kunst*: „no script, only a rule-set“, offener
  Ausgang.

Ein ausgeschriebener Dialog wäre falsch, denn die fremde Person spricht frei.

| Teil | Wo | Inhalt |
|---|---|---|
| Versuchsanordnung | Kopf von Moment 1 *inizio* | Ziel (Gruppenmeinung gegen Einzelmeinung), Ort, Ablauf in 5 Momenten, Abbruchregel (die Person zeigt Unwohlsein → sofort Auflösung) |
| Rollenanweisungen | Kopf von Moment 1, je Person 2–4 Zeilen | Moderatorin, Arlecchino (rekrutiert, seit 14:40 ohne Schild), Influencer 1–3: was sie tun, was nie, wann sie eingreifen |
| Positionskarten | Moment 4 *discussione* | je Influencer eine Karte: die Position + 1–2 Zitate «…» mit Interviewnummer, aus den Schärfungsstellen je Figur (G2 hat die Zuordnung zu Figuren, `profil.toml:291`); dazu die Zettel im Themen-Topf, jeder mit Interviewnummer |
| Drehplan | je Moment eine Zeile KAMERA | Position, Einstellung, Ton, Schnittmarke; die Kamera-Person als Platzhalter `[KAMERA: wer?]`, bis die Gruppe sie benennt |
| Auflösung + Einwilligung | Moment 5 *rivelazione* | ausformulierte Ansprache (wer wir sind, warum gefilmt, Material wird ohne Zustimmung gelöscht) → F4 |

Je Moment gilt die Blockform ZIEL / WER TUT WAS / SÄTZE (nur Einstiegssätze
der Eingeweihten, Italienisch erlaubt) / KAMERA / ABBRUCH.

### 2.3 G3 — drei Varianten (→ F1)

| Variante | Was die Performer:innen in der Hand haben | Pro | Contra | Bauaufwand heute |
|---|---|---|---|---|
| **A Spurenpartitur über Zeit** (`spurenpartitur`) | je Abschnitt Spuren WAND / KLANG / STIMMEN (Voce + Modus + Fragment) / PUBLIKUM, mit Zeitschätzung | bildet die Gleichzeitigkeit ab (Video läuft, während geflüstert wird); taugt direkt als Probenplan und für die Technik | das Modell muss Video und Klang erfinden oder Platzhalter setzen; Zeitangaben sind geraten; am schwersten gut zu prompten | eigener Formblock, ~45 min |
| **B Fragment-Sammlung je Modus** (`fragmente`) | je Szene die Fragmente nach Modus gruppiert (FLÜSTERN 1:1 / MIKROFON / HAPPENING), je Fragment Voce, erste/dritte Person, Interviewnummer, dazu EINE Zeile Wand/Klang | genau das, was die Performer:innen lernen und verteilen; Material ist der Kern (verbatim); robust zu prompten; die Abfolge im Raum entsteht in der Probe, wie es zur Installation passt | Gleichzeitigkeit und Timing stehen nicht drin; die Gruppe baut die Zeitachse selbst | eigener Formblock, ~35 min |
| **C Sprechtext je Szene wie G1** (`zeugnistext`) | je Szene Zeugnisse in Reihenfolge mit Erzählbrücken | null Zusatzbau (dieselbe Form wie G1); einheitlich | verliert die drei Modi, die die Gruppe ausdrücklich festgelegt hat (Festlegung 14:38); liest sich linear, die Installation ist es nicht | 0 min |

**Empfehlung: B.** Begründung:
- Die Festlegungen der Gruppe drehen sich um Modi und Zeugnisse; die
  Wand/Klang-Ebene stellt die Gruppe selbst zusammen (echte Bilder, „true
  and false“), und der Bot soll sie nicht erfinden.
- *performance-installation* sagt „improvised within a curated framework“:
  Das Fragment-Set ist dieses Framework.
- A ist der nächste Schritt, falls die Gruppe in der Probe eine Zeitachse
  vermisst.

---

## 3. Felder: was da ist, was fehlt

| Gruppe | Da | Fehlt | Heute |
|---|---|---|---|
| G1 | `format`, `rahmen`, Übersicht, Szene 2 mit `was_passiert` (Silos) und `kernsaetze`, Festlegungen (Aktionen, Sinneselemente) | Markierung „Szene 1/3 ohne Text“ | **kein neues Feld**, Markierung über vorhandene Zeitstempel (5.3) |
| G2 | `format`, `rahmen`, 5 Momente, Festlegungen, Figuren mit Rollenwort | Positionen je Influencer, Topf-Themen, Kamera-Person | **kein neues Feld**: Positionen und Topf aus den Schärfungsstellen; Kamera als Platzhalter + Frage an die Gruppe |
| G3 | `format`, `rahmen`, `geschichte`, 6 Szenen, Festlegungen (Modi, Knopf, Rhythmus), Voce 1–5 | Video-Inhalte, Dauer | **kein neues Feld**: Wand/Klang als eine Zeile bzw. Platzhalter `[VIDEO: …]` |

Neu sind nur Formwerte in der bestehenden Spalte `szene.form` und ein
Profil-Flag an der Form. Es gibt keine Migration.

---

## 4. Durchlauf Phase 5 → 6 → 7

- **Prosa bleibt** (selbst entschieden): Der Phase-6-Umbau von cc-p6test
  (Worktree `/tmp/nacht/wt-formberater`, Branch `testbot-voll`) wird nicht
  angefasst. Die Prosa beschreibt bei G2/G3 den Ablauf und bei G1 die Silos,
  und A10 prüft gegen sie. Birk hat im Nachtrag selbst den Weg „Prosa →
  Bühnentext“ genannt.
- **Szenen ohne Text** (G1 Szene 1 und 3) überspringen Phase 5, 6 und 7
  vollständig (5.3).
- **Phase 7:** Die Formwahl bietet zusätzlich `zeugnistext` und
  `versuchsanordnung` an, dazu je nach F1 die G3-Form. Die Gruppe antwortet
  wie bisher („2 testimony text“). Ob der Bot die passende Form vorschlägt,
  klärt F3.
- **Sprechweisen-Schritt** (`sprechweise.starte` in `weiter_7`): Für
  Funktionen ist er überflüssig, bleibt heute aber stehen, weil
  `ueberarbeitung.py` gerade bei cc-p6test liegt. Die Gruppe bestätigt ihn
  mit einem Klick.
- **Richter für die neuen Formen:** nur a10 (Materialtreue), c1 entfällt (F5).
  Die Prüfung der ganzen Geschichte (a2/a6/a9/a11) bleibt.
- **Sprache:** Rahmentexte Englisch (G1 laut Nachtrag; G3 nach Regel); G2
  darf Italienisch, weil draußen gespielt wird. Wie Zitate in einem
  englischen Text stehen, klärt F2.

---

## 5. Architektur

### 5.1 Ansätze

1. **Neue Szenenformen nur im Padua-Profil, mit Flag `eigenstaendig = true`.**
   *Empfohlen.*
   - Läuft über den vorhandenen Weg `szene.form` → `systemanweisung` →
     `volltext` → Textbuch.
   - Dortmund und Vorgabe bleiben byte-gleich.
   - Kosten: die Kopien aus 1.2.
   - Je nach F1 sind es 2 neue Formen (Variante C) oder 3 (A oder B).
2. **Format-Overlay je Gruppe** (neue Spalte, überschreibt jede Szenenform).
   Das braucht eine neue Spalte, einen Umbau von `weiter_7` und
   `PFLICHTFELDER`, und es kollidiert mit cc-p6test.
   Seit G1 nur noch eine Szene braucht, passt das Overlay-Konzept („ein
   Format fürs ganze Stück“) ohnehin nicht mehr.
3. **Eigener Generator außerhalb der Szenen.** Damit fallen Prüflauf,
   Kürzen, Fassungen und Abnahme je Szene weg; abgelehnt.

### 5.2 Bausteine

- **`workshop.py`:**
  - `[[form]]` darf optional `eigenstaendig = true` tragen;
  - neuer Accessor `workshop.form_eigenstaendig(name) -> bool`, Vorgabe False;
  - `_pruefe_formen` akzeptiert den Schlüssel.
- **`workshop/padua-2026/formen.toml`:** neue Einträge mit `anzeige` und
  Stichwörtern.
  - `zeugnistext`: testimony, testimony text, verbatim, spoken text,
    documentary text.
  - `versuchsanordnung`: experiment, social experiment, invisible theatre,
    film, shot list.
  - G3-Form nach F1. Für B (`fragmente`): fragments, whisper, one-to-one,
    installation, modes.
  - Nicht verwenden: „music“ und „song“ (bleiben bei `lied`) sowie „scene“.
  - `anzahl_wort` anpassen.
- **Regelblöcke** unter `workshop/padua-2026/prompts/formen/<name>.md`, im
  Profilordner, damit kein anderes Profil sie sieht. Inhalt jeweils:
  - Zweck in 3 Sätzen;
  - die Ausgabeform aus Abschnitt 2 mit Labels in Großbuchstaben;
  - Zitat nur wörtlich aus den mitgegebenen Stellen, mit Interviewnummer;
  - nichts erfinden, Platzhalter statt erfundener Fakten;
  - Performer als Funktion;
  - Sprache;
  - Länge.
- **`szene.systemanweisung`:** Ist `workshop.form_eigenstaendig(formdatei(form))`
  wahr, besteht die Anweisung nur aus `[formblock, theater-tells]`.
- **`prueflauf`:** Fragen für die Bühnenszene → `("a10",)`, wenn die Form
  eigenständig ist.
- **Kopien aus 1.2:**
  - `system.md` (en) bekommt einen Halbsatz zu den Formaten;
  - `szenenfolge._FORMEN`/`_FORM_AUS_EN` aus dem Profil lesen;
  - die EN-Beschriftungen in `sprachen/en/texte.toml` ergänzen; die deutschen
    Python-Konstanten bleiben unverändert;
  - `mechanik._NICHT_DIALOG` um die neuen Namen erweitern;
  - `[laengen.rahmen]` je Form: `zeugnistext` 400–900 Wörter (eine ganze
    Mittelszene), die anderen 250–500.

### 5.3 „Kein Text nötig“ ohne neue Spalte

Alle Schleifen in Phase 5, 6 und 7 fragen nur nach Zeitstempeln:
- `entwurf_bestaetigt_am`;
- `ueberarbeitung_bestaetigt_am`;
- `fertig_am`;
- `phasen.voraussetzungen[7]`: Prosa oder Volltext vorhanden.

Eine Funktion `repo.markiere_szene_ohne_text(conn, chat_id, nummer, grund)`
setzt in einem Schritt:
- alle drei Stempel;
- `form` = Profil-Vorgabe;
- `prosa` und `volltext` = eine feste Zeile `T._SZENE_OHNE_TEXT`, z. B. „(No
  script: musical/ritual section — staged by the group. <grund>)“.

Damit überspringt jede vorhandene Schleife die Szene, und das Textbuch zeigt
die Zeile statt einer Lücke. Gesetzt wird das heute Abend über ein kleines
Skript `scripts/szene_ohne_text.py <db> <chat_id> <nummer>` (Muster
`g3-korrektur.py`, mit Backup), das Robo auf der Live-DB ausführt; ein
Knopf kommt später.

Offen für Phase 2:
- Schreibt der Gesamt-Rewrite in Phase 6 (`kurzgeschichte.starte(vorlage=True)`)
  `prosa` aller Szenen neu und überschreibt damit die Zeile? Falls ja,
  schadet das nicht, weil `volltext` und die Stempel bleiben; trotzdem prüfen.
- Lesen `_szenen_zusammenfassung` und Kontext die Zeile sinnvoll?

### 5.4 Byte-Gleichheit

Dortmund und Vorgabe haben keine neuen Formen und kein Flag, und ihre
deutschen Texte bleiben unverändert. Ohne neu erzeugte Fixtures bleiben
deshalb grün:
- `tests/test_profil_bitgleich.py`;
- `tests/test_sprache_bitgleich.py`.

---

## 6. Plan für heute Abend (≤ 4 h)

| # | Schritt | Dateien | Zeit |
|---|---|---|---|
| 1 | Flag `eigenstaendig` + Accessor + Validierung, Test zuerst | `workshop.py`, `tests/test_formen_katalog.py` | 25 min |
| 2 | Neue Formen in Padua `formen.toml`, Längenrahmen | `workshop/padua-2026/formen.toml`, `profil.toml` | 15 min |
| 3 | Regelblöcke `zeugnistext.md`, `versuchsanordnung.md` (+ G3-Form nach F1) | `workshop/padua-2026/prompts/formen/` | 60–75 min |
| 4 | `systemanweisung` ohne `szene.md` bei eigenständiger Form; Prüflauf nur a10 | `szene.py`, `prueflauf.py`, Tests in `test_ueberarbeitung_phase7.py`, `test_prueflauf.py` | 30 min |
| 5 | „Kein Text nötig“: Repo-Funktion, Text-Konstante, Skript, Test (alle drei Schleifen überspringen, Voraussetzung 7 erfüllt) | `repo.py`, `sprache`/`texte.toml`, `scripts/szene_ohne_text.py`, neuer Test | 30 min |
| 6 | Kopien aus 1.2 nachziehen | s. 1.2 | 30 min |
| 7 | `pruefe_profil padua-2026`, gezielte Tests, dann einmal die volle Suite `-m "not dortmund"` | | 25 min |
| 8 | Testbot-Abnahme (F6) mit Ablauf 8a–8d unten | | 30 min |

Summe: etwa 4 h, mit Variante C für G3 etwa 3 h 45 min.

Ablauf von Schritt 8:
- **8a:** `scripts/test_uebernehmen.py` → `betrieb/padua-test.db` je Gruppe.
- **8b:** Auf der Kopie G1 Szene 1/3 „ohne Text“ setzen, Phase 7 setzen,
  Formen setzen.
- **8c:** Je Gruppe eine Szene schreiben: G1 *Le voci*, G2 *discussione*,
  G3 *Fast Rise*.
- **8d:** Das Textbuch lesen.

Abnahmekriterien:
- (a) Suite grün, `pruefe_profil padua-2026` grün.
- (b) Jede Testszene hat die Blöcke ihrer Form, keine Repliken im
  Dialogstil, jedes Zitat mit Interviewnummer und wörtlich in den
  mitgegebenen Stellen auffindbar (Stichprobe von Hand).
- (c) G1 Szene 1/3 erscheinen nicht als offene Szene in Phase 5, 6 oder 7,
  und das Textbuch zeigt sie mit der Zeile.
- (d) Die Formwahl zeigt die neuen Formen.
- (e) Der Dortmund-Snapshot ist unverändert.

Kein Deploy und kein Neustart der Live-Dienste: Die TOML-Profile wirken erst
nach einem Neustart, und den macht Birk.

---

## 7. Fragen an Birk (nach Wichtigkeit)

**F1 — G3: Welches Skript?** (Varianten in 2.3)
- *Empfehlung:* **B, Fragment-Sammlung je Modus.** Begründung: Die Modi sind
  die Festlegung der Gruppe; die Wand/Klang-Ebene bauen die
  Teilnehmer:innen selbst, und der Bot erfindet sie nicht.
- Optionen:
  - A: Spurenpartitur über Zeit (zeigt Gleichzeitigkeit, aber Video und
    Timing wären geraten, +10 min);
  - B: Fragmente je Modus;
  - C: Sprechtext je Szene wie G1 (null Zusatzbau, verliert die Modi).
- *Hängt ab:* Schritt 3, Anzahl neuer Formen, Abnahme 8c.

**F2 — G1 (und alle): Zitate in einem englischen Text — in welcher Sprache?**
Die Interviews sind italienisch, der Text soll Englisch sein und die Zitate
„wörtlich“.
- *Empfehlung:* (a) Gesprochen wird eine **nahe englische Übersetzung**,
  darunter steht klein das **italienische Original mit Interviewnummer**.
  Begründung: Wer probt, sieht die Quelle, und A10/`zitat.pruefe` können gegen
  das Original prüfen.
- Optionen:
  - (a) Übersetzung + Original;
  - (b) Zitate im italienischen Original sprechen, nur die Brücken Englisch;
  - (c) nur Übersetzung (Quelle nicht mehr prüfbar).
- *Hängt ab:* Sprachsatz in `zeugnistext.md`, ggf. auch in G3.

**F3 — Darf der Bot in Phase 7 die passende Form vorschlagen?**
Der Phase-7-Prompt sagt „You never suggest forms on your own“.
- *Empfehlung:* (a) Passt `arbeitsstand.format` per Stichwort zu einer neuen
  Form, zeigt die Formwahl EINEN Knopf „Alle offenen Szenen als <Form>“;
  die Gruppe klickt.
- Optionen:
  - (a) Knopf-Vorschlag (+20 min);
  - (b) nur in der Liste (Risiko: aus Gewohnheit „dialogue“);
  - (c) fest je `chat_id` im Profil wie `musik_chats` (schnell, aber gegen
    „die Gruppe entscheidet“).
- *Hängt ab:* Schritt 6, ein Satz in `7.md`.

**F4 — G2: Einwilligung beim Filmen von Fremden.** 15- bis 18-Jährige filmen
eine ahnungslose Person.
- *Empfehlung:* (a) *rivelazione* enthält die Auflösungs- und
  Einwilligungsansprache als Entwurf plus Abbruchregel; das Formular kommt
  von Birk bzw. der Schule, der Bot schreibt keins.
- Optionen:
  - (a);
  - (b) der Bot schreibt auch ein Formular-Muster;
  - (c) Einwilligung ganz aus dem Skript, das regelt die Leitung.
- *Hängt ab:* Inhalt von `versuchsanordnung.md`.

**F5 — Richter c1 (Stimme) für die neuen Formen abschalten?**
- *Empfehlung:* (a) c1 aus, a10 an.
- Optionen:
  - (a);
  - (b) c1 für G2 behalten (misst aber Improvisation, die nicht geschrieben
    wird);
  - (c) zusätzlich heute die deterministische Zitatprüfung (Interviewnummer +
    `zitat.pruefe`) bauen (+60 min, sprengt 4 h).
- *Hängt ab:* Schritt 4.

**F6 — Testbot-Abnahme mit echten Modellaufrufen heute Abend?** Skripte,
die Geld kosten, laufen nie automatisch.
- *Empfehlung:* (a) ja, drei Szenenläufe auf `padua-test.db`, geschätzt
  deutlich unter 1 CHF.
- Optionen:
  - (a);
  - (b) nur Prompt-Dump ansehen;
  - (c) morgen früh mit Birk.
- *Hängt ab:* Schritt 8.

**Selbst entschieden (mit Grund, zur Kenntnis):**
- **Prosa in Phase 5/6 bleibt.** Grund: keine Kollision mit cc-p6test,
  Vorlage für A10, Birk nannte den Weg „Prosa → Bühnentext“ selbst.
- **„Kein Text nötig“ über Stempel statt neuer Spalte.** Grund: Alle
  Schleifen lesen nur Stempel; null Änderung in `ueberarbeitung.py`/`entwurf.py`.
- **G2 ohne eigenen Gesamtlauf.** Grund: Anordnung und Rollen stehen im Kopf
  von Moment 1, Positionskarten in Moment 4, der Drehplan als Zeile je
  Moment; das spart einen Lauf und bleibt im Prüf-/Abnahmeweg.
- **Neue Formen nur im Padua-Profilordner.** Grund: Byte-Gleichheit,
  kein anderes englisches Profil sieht sie.

**An die Gruppe G2 (nicht an Birk):** Wer filmt?

---

## 8. Bewusst nicht heute (mit Grund)

- **Setlist/Partitur für G1:** Birk ~17:00, die Musik macht die Gruppe
  selbst.
- **Format-Overlay je Gruppe:** neue Spalte, Umbau von `weiter_7`, Kollision
  mit cc-p6test, und seit G1 nur eine Szene braucht, ohne Nutzen.
- **Deterministische Zitat-/Strukturprüfung:** modellfrei und richtig, aber
  ein eigener Baustein; erster Kandidat für morgen (F5c).
- **Sprechweisen-Schritt für Funktionen überspringen:** liegt in
  `ueberarbeitung.py`, das gerade bei cc-p6test ist.
- **Knopf „kein Text nötig“:** heute nur per Skript.
- **Ganzes-Stück-Artefakte** (G3-Cue-Liste für die Technik, G2-Gesamtdrehplan
  über einen eigenen Lauf).
- **Formberater im Schreibweg:** Er bleibt Gesprächshilfe.
- **Neue Felder** (Musik-Cues, Video-Inhalte, Positionen): erst, wenn die
  Gruppen sie auf der Workbench pflegen wollen.

## 9. Offene Punkte für Phase 2 (`writing-plans`)

- Kommen die Schärfungsstellen mit Interviewnummer im Nutzertext an
  (`baue_nutzertext`)? Bei G1/G3 werden sie nur Szenen zugeordnet,
  `profil.toml:291`. Die Formblöcke setzen das voraus.
- Passt `_AUFTRAG_BUEHNE`/`VORLAGE_KOPF` („Translate it into the form“) zu den
  neuen Formen, oder braucht jede eigenständige Form einen Zusatzsatz?
- 5.3: das Verhalten des Gesamt-Rewrites in Phase 6 gegenüber
  Ohne-Text-Szenen (mit cc-p6test abstimmen).

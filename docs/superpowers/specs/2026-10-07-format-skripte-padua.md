# Format-Skripte für die drei Padua-Gruppen — Design

Stand: 07.10.2026, ~17:30 · Autor: cc-formatspec (nach `brainstorming-to-spec`,
Fragen nicht direkt gestellt, sondern unten gesammelt) · Basis: Branch
`spec-format-skripte` auf `90e1d52` · Live-DB `betrieb/padua.db` nur `?mode=ro`
gelesen (Stand 16:17).

**Ziel (Birk 07.10.2026 ~16:50):** Für G1, G2, G3 entsteht in Phase 7 ein
Szenenskript **im Format, das die Gruppe gewählt hat** — nicht ein
Sprechtheater-Dialog. Nur diese drei Formate, kein Generalumbau, heute Abend
in ≤ 4 h baubar.

**Status:** Entwurf, wartet auf Birks Antworten (Abschnitt 7). Phase 2
(`writing-plans`) erst nach Freigabe.

---

## 1. Ist-Stand (am Code und an der Live-DB nachgeprüft)

### 1.1 Schreibweg

- Phase 5 (Prosa-Entwurf, `entwurf.py`) und Phase 6 (Rewrite,
  `ueberarbeitung.weiter_6`) schreiben **Prosa** nach `szene.prosa`
  (`szene.schreibt_prosa` = Phase ≤ 6, `szene.py:258`; Systemanweisung dann
  nur `formen/prosa` + `theater-tells`, `szene.py:358`).
- Phase 7 (`ueberarbeitung.weiter_7`, `ueberarbeitung.py:429`): Formwahl je
  Szene in EINER Antwort (`sende_formwahl` :379, Erkenner `formen_setzen` →
  `_wende_formen_an` :724) → Sprechweisen → je Szene
  `szene.starte(_AUFTRAG_BUEHNE)` → `szene.volltext`. Systemanweisung:
  `szene.md` (Sprechtheater-Regeln: Repliken, „Figuren müssen hörbar
  verschieden klingen") + `formen/<form>.md` + Stil + `theater-tells`
  (`szene.systemanweisung`, `szene.py:326-381`). Die Prosa geht als bindende
  Vorlage mit („Translate it into the form …", `VORLAGE_KOPF`).
- **Die Formliste kommt aus dem Profil:** `workshop/padua-2026/formen.toml`
  (dialog, monolog, chor, lied, rap), Regelblöcke über
  `anweisungen.hole_optional` mit Suchreihenfolge
  `workshop/<p>/prompts/` → `sprachen/en/prompts/` → `prompts/`.
  Unbekannte Form → stiller Rückfall auf `dialog` (`szene.formdatei`).
- `arbeitsstand.format` (Freitext) wird **im Schreibweg nicht gelesen**
  (`szene._format_rahmen_text` hat es bewusst entfernt, `szene.py:909`); nur
  Vorspann/Textbuch, Workbench, Richter A11.
- Formberater (Tabelle `formberater`, 67 Formen in `interview_theater/formen/`,
  für `musik_chats` auch `formen_musik/`) wirkt nur im Chat-Prompt und auf der
  Workbench, nie auf `szene.form`.
- Textbuch: `szenenfolge.textbuch` (`szenenfolge.py:911`) = Titel + Vorspann
  (Besetzung, Setting, Format) + je Szene Kopf, Feldblock, `volltext`.
- Prüflauf (`prueflauf.py:50-55`): Geschichte a2/a6/a9/a11, Prosaszene b1/a10,
  Bühnenszene a10 (Materialtreue) + c1 (Stimme: Zeilen ohne Namen den Figuren
  zuordnen). `dramaturgie/mechanik.py:670` `_NICHT_DIALOG` kennt nur die
  fünf Formen.

### 1.2 Hart kodierte Formlisten (müssen bei neuer Form mit)

1. `workshop/padua-2026/formen.toml` (+ `anzahl_wort = "five"`)
2. Regelblock-Datei; `scripts/pruefe_profil.py:170-176` verlangt sie
3. `sprachen/en/prompts/system.md:64` nennt die fünf Formen wörtlich
4. `szenenfolge.py:414` `_FORMEN`, `_FORM_AUS_EN` :432 (Test
   `tests/test_formabfolge.py:42` verlangt Gleichheit mit `szene.FORMEN`)
5. `web.py:910-920` `FORM_BESCHRIFTUNG` / `texte.toml:1881`, `:2016`
   (Test `tests/test_web_sprache.py:130`, Padua)
6. `vorspann.py:244-250` `FORM_BESCHRIFTUNG` (`texte.toml:918`)
7. `dramaturgie/mechanik.py:670` `_NICHT_DIALOG`, :673 `_ERSTE_VERBOTEN`,
   :1118 `_FORM_BESCHRIFTUNG` (`texte.toml:1595`)
8. `stile.py:83-96` `VORSCHLAG` (kein Eintrag = kein Stilvorschlag — gewollt)
9. `profil.toml [laengen.rahmen]` (ohne Eintrag: `vorgabe_min/max`)

### 1.3 Die drei Gruppen (Live-DB, alle in Phase 5, noch keine Prosa, kein Volltext)

**G1 (`7000000000000`)** — `format`: „Concert performance with documentary
material: one through-composed set where the music never stops; four
performer-musicians as themselves, post-dramatic …, built on the home chord
(tonic) and ending in a shared ritual". Übersicht/Logline **fixiert**
(14:11). 3 Szenen: *Tornare a casa* / *Le voci* / *Il rituale*;
`kernsaetze` je Szene voll mit italienischen Interviewzitaten (Szene 2 in
thematischen „Silos": was ist Zuhause, Gerüche/Klänge/Farben, was tust du,
was würde dein Zuhause sagen, Weggehen). Festlegungen: ein durchgehendes
Stück ohne Schnitte, Übergänge gehören zum Werk; Musik als fil rouge (Tonika
= Heimkehr); postdramatisch, keine vierte Wand; Kostüm Hauskleidung,
Dresscode Publikum Pyjama/Hausschuhe; sensorische Elemente (Kaffee, Brot,
Weihrauch). Figuren = die vier Performer:innen selbst (Gitarre, Klavier =
Ritualleiter, zwei Gesang/Instrument). Formberater: passt
dokumentartheater, postdramatisches-theater; Vorschlag konzertperformance,
kadenz-tonika (aus `formen_musik/`). **Gruppe 13:30:** Szene 1 und 3
brauchen keine Interviews, nur „Le voci". **13:47/13:49:** wollen einen
„sensorischen, nicht beschreibenden" Text mit den Interviews, nach Themen,
**„in italiano … per la performance"**.

**G2 (`…001`)** — `format`: „Short documentary film / social experiment";
Titel „JAMM'IA". `rahmen`: Bartisch nahe der Uni; Moderatorin sitzt, ein
Rekrutierer (Arlecchino) holt erst die Mitspielenden „als wären sie Fremde",
dann eine echte Passantin/einen echten Passanten („du wärst der/die
Letzte"); Themen-Topf mit Themen aus den Interviews; die Runde vertritt eine
gemeinsame Meinung, der Film beobachtet, ob die fremde Person bei ihrer
bleibt. 5 Szenen: *inizio / reclutamento / l'ultimo posto / discussione /
rivelazione*. Figuren: Moderatorin, Arlecchino, Influencer 1–3. **14:40:**
„kein Schild mehr, nur Arlecchino zieht Leute an". Lücke: der Rahmen sagt
„eine:r von euch filmt als Passant:in", aber alle fünf sind besetzt — die
Kamera ist unbesetzt (Frage an die Gruppe, nicht an Birk). Keine Übersicht.
Formberater: passt soziales-experiment-als-kunst, unsichtbares-theater;
Vorschlag commedia-dell-arte, happening. Spielort draußen → nach Birk-Regel
Italienisch erlaubt.

**G3 (`…002`)** — `format`: „Immersive performance installation (promenade,
audience standing) with video projection and sound carpet;
documentary/verbatim testimonies … very short scenes, monologues and stories
— first person, third person, small dialogues". `geschichte` „From Outside
In" (Welle: langsamer Start, schneller Anstieg, Senke, zweiter Anstieg).
6 Szenen: *The First Press / Slow Start / Fast Rise / The Dip / Second Rise
/ The Last Question*. Festlegungen: Knopf startet, Ablauf dann autonom
(kein Zapping); Ende = projizierte Frage, zweiter Knopfdruck, alles aus,
Dunkel; sehr kurze, sich überlappende Szenen, unterbrochen von tieferen
Zeugnissen und Musikmomenten; **drei Modi fließend gemischt:**
One-to-One-Flüstern, Mikrofon-Ruhepunkt (Projektion friert ein),
Kleinst-Happenings zu zweit/dritt. Figuren: Voce 1–5 als Funktionen.
Formberater: passt verbatim-theatre, performance-installation; Vorschlag
partizipative-performance, multimedia-performance.

---

## 2. Das richtige Endprodukt je Gruppe

Gemeinsam für alle drei: Die Performer:innen spielen **keine erfundenen
Figuren** (G1/G3 ausdrücklich, G2 als „semi personaggi"). Ein
Sprechtheater-Textbuch mit Repliken und „hörbar verschiedenen Figuren"
(`szene.md`, Richter c1) ist deshalb für alle drei das falsche Artefakt.
Das Skript ist jeweils eine **Partitur bzw. Spielanweisung**, deren
Textteile wörtlich aus den Interviews kommen.

### G1 — Setlist/Partitur (`setlist`)

Begründung aus dem Katalog: *konzertperformance* — „musicians perform as
themselves, as a song sequence, not a plot"; *dokumentartheater* — „no
invention, only re-arrangement" von Quellmaterial;
*postdramatisches-theater*; *kadenz-tonika* (Musik-Katalog) trägt die
Dramaturgie der Gruppe (weg von der Tonika, zurück im Ritual).

Je Szene eine Folge von **Nummern** (die Musik hört nie auf, also sind auch
Übergänge Nummern):

```
NUMMER 2.3 — "Gli odori" (Silo: Gerüche/Klänge)
MUSIK:    Klavier hält die Dominante, Gitarre Arpeggio; keine Auflösung.
WER:      Performer 3 spricht, Performer 4 summt.
AKTION:   Performer 1 geht mit Kaffeebohnen durch den Halbkreis.
TEXT:     «…» [Int. N]   (Beispielaufbau, Nummern nicht echt)
          «…» [Int. M] …
ÜBERGANG: Gitarre moduliert → Nummer 2.4 setzt auf dem Nachhall ein.
```

Felder je Nummer: Musik-Cue (Harmonik in Worten der Gruppe: Tonika /
weg von der Tonika / Rückkehr), Wer (Performer-Funktion, nicht Rolle),
Aktion/Sinneselement, Text (Zitate wörtlich mit Interviewnummer, gesprochen
oder gesungen markiert), Übergang. Szene 1 und 3 enthalten eigene
Performer-Texte (keine Interviews nötig, Gruppe 13:30); Szene 3 ist die
Ritualanweisung (Kreis, Hände, Augen zu, Track „Home", Bilder, die der
Ritualleiter beschreibt — diese Bilder aus `kernsaetze` Szene 3).

### G2 — Versuchsanordnung + Drehplan (`versuchsanordnung`)

Begründung: *unsichtbares-theater* — „scripted but disguised as reality",
Publikum = unwissende Beteiligte; *soziales-experiment-als-kunst* — „no
script, only a rule-set", offener Ausgang. Ein ausgeschriebener Dialog wäre
falsch: die fremde Person spricht frei, die Eingeweihten improvisieren
entlang von Positionen. Das Skript ist eine **Regelwerk-Partitur je
Moment**:

```
MOMENT 4 — discussione
ZIEL:        Die Runde vertritt geschlossen Position X; beobachtet wird,
             ob die fremde Person bei ihrer bleibt.
REGELN:      Influencer 1 eröffnet; niemand widerspricht der Runde;
             Arlecchino bricht ab, wenn die Person sich unwohl zeigt.
POSITIONEN:  Influencer 1 — «…» [Int. 4] / Influencer 2 — «…» [Int. 9] …
             (Karten zum Mitnehmen, je Person eine)
THEMA AUS DEM TOPF: <Thema> (aus Int. N)
KAMERA:      halbnah über die Schulter der Moderatorin, Ton vom Tisch;
             Schnittmarke, wenn die Person zum ersten Mal widerspricht.
ABBRUCH:     wenn … → sofort Moment 5 (Auflösung).
```

Moment 5 *rivelazione* enthält die **Auflösungs- und
Einwilligungsansprache** (wer wir sind, warum gefilmt, dass das Material
ohne Zustimmung gelöscht wird) als ausformulierten Text — siehe Frage 4.
Positionskarten aus den Interviews sind das Herz: jede Meinung am Tisch ist
belegt.

### G3 — Spurenpartitur (`spurenpartitur`)

Begründung: *performance-installation* — Publikum geht/steht in einer
Umgebung, „no fixed seating or fourth wall"; *verbatim-theatre* — „exact
recorded words of interviewees"; *multimedia-performance* — Video/Klang
„as structural elements … can behave like characters";
*one-to-one-performance* für den Flüstermodus. Ein linearer Text kann
gleichzeitige Spuren nicht abbilden. Das Skript ist eine **Partitur über
Zeit mit Spuren**:

```
ABSCHNITT 3 — Fast Rise (ca. 0:06–0:10)
WAND (Video):  Schnittfolge beschleunigt; [VIDEO: von der Gruppe gewähltes
               Ereignis] — nichts erfunden, nur Platzhalter.
KLANG:         Interviewfragen-Aufnahmen stapeln sich zum Teppich.
STIMMEN:
  V1 · FLÜSTERN 1:1  «…» [Int. 3]  (zu einer Person, nah)
  V2+V4 · HAPPENING  stummes Spiel: …, dann «…» [Int. 11]
  V5 · MIKROFON      — (erst in Abschnitt 4: Wand friert ein)
PUBLIKUM/KNOPF: —
DICHTE: 3 Fragmente überlappen.
```

Fragmente je Modus mit Interviewnummer, erste/dritte Person markiert;
Abschnitt 1 und 6 enthalten die Knopf-Mechanik (Start, projizierte
Schlussfrage im Wortlaut der Festlegung, Abbruch, Dunkel).

---

## 3. Felder: was da ist, was fehlt

| Gruppe | Schon da | Fehlt | Entscheidung für heute |
|---|---|---|---|
| G1 | `format`, `rahmen`, Übersicht, 3 Szenen mit `was_passiert` + `kernsaetze`, Festlegungen (struktur/stil/COSTUMES), Figuren als Funktionen | Musik-Cue je Nummer, Instrumentierung, Sinneselemente je Silo | **kein neues Feld**: Cues/Aktionen entstehen im Skript aus `was_passiert`, Festlegungen und Figurenbeschreibung (Instrument steht in `figur.beschreibung`) |
| G2 | `format`, `rahmen`, 5 Szenen (nur `was_passiert`, einzeilig), Festlegungen (struktur/ort/PROPS/figur) | Positionen je Influencer, Themen im Topf, Kamera-Besetzung, Einwilligungstext | **kein neues Feld**: Positionen kommen aus der Schärfung (Interviewstellen je Figur — G2 ist ausdrücklich NICHT in der Szenen-only-Zuordnung, `profil.toml:291`); Kamera ist eine Frage an die Gruppe im Chat |
| G3 | `format`, `rahmen`, `geschichte`, 6 Szenen, Festlegungen (Modi, Knopf, Rhythmus), Voce 1–5 | Video-Inhalte, Dauer je Abschnitt | **kein neues Feld**: Video als Platzhalter `[VIDEO: …]`, Dauer als Schätzung aus der Wellenform |

Das einzige neue Datum ist der Formwert in `szene.form` (bestehende Spalte)
und ein **Profil-Flag** an der Form (Abschnitt 5). Keine Migration.

---

## 4. Durchlauf Phase 5 → 6 → 7

- **Phase 5/6 bleiben unverändert** (Prosa-Entwurf, Rewrite). Gründe: (a)
  der laufende Lauf cc-p6test baut gerade Phase 6 um (Worktree
  `/tmp/nacht/wt-formberater`, Branch `testbot-voll`) — jeder Eingriff hier
  kollidiert; (b) die Prosa ist als „was in diesem Abschnitt passiert"
  auch für eine Partitur brauchbar und ist die Vorlage, gegen die A10
  Materialtreue prüft. Ob die Prosa für diese Formate gekürzt/übersprungen
  werden soll: Frage 3.
- **Phase 7:** Die Formwahl bietet zusätzlich drei Formen an —
  `setlist` („Setlist / score"), `versuchsanordnung` („Experiment setup"),
  `spurenpartitur` („Track score"). Die Gruppe wählt wie bisher je Szene in
  einer Antwort („all scenes setlist"). Ob der Bot die zum `format` passende
  Form vorschlägt: Frage 1.
- **Neue Formen statt Format-Overlay** (empfohlen, siehe 5.1): sie laufen
  durch denselben Weg (`szene.form` → `systemanweisung` → `volltext` →
  Textbuch), kosten keine neue Spalte und keinen neuen Zustand.
- **Systemanweisung für diese drei:** NUR der Formblock + `theater-tells`,
  **ohne `szene.md`** und ohne Stilblock — `szene.md` verlangt Repliken und
  hörbar verschiedene Figuren und widerspricht allen drei Formaten direkt.
- **Richter:** Bühnenszene in diesen Formen prüft nur **a10
  (Materialtreue)**; **c1 (Stimme) entfällt** — Zeilen ohne Namen
  Figuren zuordnen ist bei Funktionen/Performer:innen als sie selbst sinnlos
  und würde falsche Überarbeitungsaufträge erzeugen (Frage 5). Geschichte
  (a2/a6/a9/a11) bleibt. `mechanik._NICHT_DIALOG` bekommt die drei Namen.
- **Was fehlt (nicht heute):** eine deterministische Strukturprüfung
  („jede Nummer hat MUSIK/WER/TEXT", „jedes «…» hat [Int. N] und besteht
  `zitat.pruefe`"). Ohne Modellaufruf, aber ein eigener Baustein → Abschnitt 8.
- **Sprache:** Interviewfragmente stehen immer **wörtlich im Original
  (Italienisch) mit Interviewnummer** — das ist Verbatim-/Dokumentar-Logik,
  kein Sprachwechsel. Der übrige Skripttext (Cues, Regeln, Anweisungen)
  folgt der Birk-Regel (Englisch; G2 draußen → Italienisch erlaubt). Für G1
  liegt ein ausdrücklicher Wunsch nach Italienisch vor → Frage 2. Umsetzung
  ohne Code: der Formblock sagt „Sprache der Rahmentexte: wie in den
  Festlegungen (bereich `stil`/`sonstiges`, ‚language: …'), sonst Englisch".

---

## 5. Architektur

### 5.1 Ansätze

1. **Drei neue Szenenformen, nur im Padua-Profil, mit Flag
   `eigenstaendig = true`** — *empfohlen*. Nutzt den vorhandenen Weg,
   Dortmund/Vorgabe haben das Flag nicht und bleiben byte-gleich. Kosten:
   die neun Kopien aus 1.2 nachziehen.
2. **Format-Overlay je Gruppe** (neue Spalte `arbeitsstand.skriptformat`,
   überschreibt in Phase 7 jede Szenenform). Sauberer für „ein Format fürs
   ganze Stück", aber neue Spalte, neuer Zustand, `PFLICHTFELDER` (form)
   müsste umgangen werden, Formwahl-Schritt in `weiter_7` umbauen — zu viel
   für heute, und es kollidiert eher mit cc-p6test (`ueberarbeitung.py`).
3. **Eigener Generator außerhalb der Szenen** (ein Lauf, ganzes Skript als
   Datei). Passt zur „Partitur über das ganze Stück", verliert aber
   Prüflauf, Kürzen, Fassungen, Abnahme je Szene — nein.

### 5.2 Bausteine (Ansatz 1)

- **`workshop.py`**: `[[form]]` darf optional `eigenstaendig = true` tragen;
  Accessor `workshop.form_eigenstaendig(name) -> bool` (Vorgabe: False).
  `_pruefe_formen` akzeptiert den Schlüssel.
- **`workshop/padua-2026/formen.toml`**: drei Einträge mit `anzeige` und
  Stichwörtern (`setlist`: setlist, score, partitura, concert, set;
  `versuchsanordnung`: experiment, social experiment, invisible theatre,
  film, shot list; `spurenpartitur`: track score, installation, immersive,
  tracks, projection). Achtung Stichwort-Kollision: „score" nicht doppelt;
  „music"/„song" bleiben bei `lied`. `anzahl_wort = "eight"`.
- **Regelblöcke** unter `workshop/padua-2026/prompts/formen/`
  (`setlist.md`, `versuchsanordnung.md`, `spurenpartitur.md`) — im
  Profilordner, nicht in `sprachen/en/`, damit kein anderes englisches
  Profil sie je sieht. Inhalt je Datei: Zweck in 3 Sätzen, Ausgabeform
  (Blöcke wie in Abschnitt 2, Großbuchstaben-Labels), Regeln (Zitat nur
  wörtlich mit `[Int. N]` aus den mitgegebenen Stellen, nichts erfinden,
  Platzhalter statt erfundener Fakten, Performer als Funktion, Sprache
  s. o.), Länge (eine Szene = eine Seite Partitur).
- **`szene.systemanweisung`**: wenn `workshop.form_eigenstaendig(formdatei(form))`
  → `[formblock, theater-tells]`.
- **`prueflauf`**: Fragenwahl für Bühnenszene → `("a10",)`, wenn die Form
  eigenständig ist.
- **Kopien aus 1.2**: `system.md` (en) ergänzt „… or, for documentary/
  installation formats, a score form"; `szenenfolge._FORMEN`/`_FORM_AUS_EN`
  aus dem Profil lesen statt Literal (oder um die drei erweitern — der
  Test verlangt Gleichheit mit `szene.FORMEN` des aktiven Profils);
  Beschriftungen in `sprachen/en/texte.toml` (web, vorspann, mechanik) um
  drei Schlüssel ergänzen — **die deutschen Python-Konstanten bleiben
  unverändert**; `mechanik._NICHT_DIALOG` um die drei Namen erweitern
  (Namen, die in Dortmund nie vorkommen → keine Verhaltensänderung);
  `profil.toml [laengen.rahmen]` je Form ein Bereich (Partitur ≈ eine
  Seite, z. B. 250–450 Wörter).

### 5.3 Byte-Gleichheit

Dortmund und Vorgabe: kein Eintrag `eigenstaendig`, keine neuen Formen,
deutsche Texte unverändert → `tests/test_profil_bitgleich.py` und
`tests/test_sprache_bitgleich.py` müssen ohne Fixture-Neuerzeugung grün
bleiben (laut AGENTS.md kein Abnahmekriterium mehr, aber hier gratis).

---

## 6. Implementierungsplan heute Abend (≤ 4 h)

| # | Schritt | Dateien | Zeit |
|---|---|---|---|
| 1 | Flag `eigenstaendig` + Accessor + Validierung, Test zuerst | `workshop.py`, `tests/test_formen_katalog.py` | 25 min |
| 2 | Drei Formen in Padua `formen.toml`, Längenrahmen | `workshop/padua-2026/formen.toml`, `profil.toml` | 15 min |
| 3 | Drei Regelblöcke schreiben (Abschnitt 2 als Ausgabeform) | `workshop/padua-2026/prompts/formen/*.md` | 60 min |
| 4 | `systemanweisung` ohne `szene.md` bei eigenständiger Form; Prüflauf nur a10 | `szene.py`, `prueflauf.py`, Tests `test_ueberarbeitung_phase7.py`, `test_prueflauf.py` | 30 min |
| 5 | Kopien nachziehen (system.md en, szenenfolge, texte.toml en, mechanik) | s. 1.2 | 40 min |
| 6 | `pruefe_profil padua-2026`, gezielte Tests, dann einmal volle Suite `-m "not dortmund"` | — | 25 min |
| 7 | Testbot-Abnahme (Frage 6): `scripts/test_uebernehmen.py` → `betrieb/padua-test.db` je Gruppe, auf der **Kopie** Phase 7 setzen, Form setzen, je Gruppe EINE Szene schreiben (G1 *Le voci*, G2 *discussione*, G3 *Fast Rise*), Textbuch lesen | — | 30 min |

Abnahmekriterien: (a) Suite grün, `pruefe_profil padua-2026` grün; (b) je
Gruppe enthält die Testszene die Blöcke ihres Formats, keine
Replik-Dialogform, jedes Zitat mit `[Int. N]` und wörtlich in den
mitgegebenen Stellen auffindbar (Stichprobe von Hand); (c) Formwahl in
Phase 7 zeigt die drei neuen Formen; (d) Dortmund-Prompt-Snapshot
unverändert. Kein Deploy, kein Neustart der Live-Dienste (TOML-Profil wirkt
erst nach Neustart — den macht Birk).

---

## 7. Fragen an Birk (nach Wichtigkeit)

**F1 — Darf der Bot in Phase 7 die passende Format-Form vorschlagen?**
Der Phase-7-Prompt sagt „You never suggest forms on your own".
*Empfehlung:* (a) Wenn `arbeitsstand.format` per Stichwort zu einer der drei
Formen passt, zeigt die Formwahl EINEN Knopf „Alle Szenen als <Form>"
zusätzlich zur freien Antwort; die Gruppe entscheidet per Klick.
Optionen: (a) Knopf-Vorschlag · (b) nur in der Liste, Gruppe muss selbst
draufkommen (Risiko: wählt „dialogue" aus Gewohnheit) · (c) fest je
`chat_id` im Profil wie `musik_chats` (schnell, aber gegen „die Gruppe
entscheidet"). *Hängt ab:* Schritt 5 (+20 min für (a)), Prompt 7.md-Satz.

**F2 — Sprache des G1-Skripts.** G1 schrieb 13:49 „ci serve in italiano per
la performance"; Birk-Regel: Englisch, Italienisch nur draußen.
*Empfehlung:* (a) Zitate immer im italienischen Original mit `[Int. N]`
(Verbatim — damit ist *Le voci* ohnehin überwiegend Italienisch),
Cues/Anweisungen und eigene Performer-Texte Englisch. Optionen: (a) ·
(b) G1 ganz Italienisch (Ausnahme von der Regel) · (c) eigene Texte
zweisprachig. *Hängt ab:* Sprachsatz im Formblock `setlist.md`, ggf. eine
Festlegung „language: …" in G1.

**F3 — Prosa-Entwurf (Phase 5/6) für diese drei Formate behalten?**
*Empfehlung:* (a) Ja, unverändert — keine Kollision mit cc-p6test, die
Prosa ist Ablaufbeschreibung und Prüfgrundlage für A10. Optionen: (a) ·
(b) Prosa nur als knappe Ablaufbeschreibung (Padua-Overlay auf
`prosa.md` für eigenständige Formen; +30 min, berührt Phase 5) ·
(c) für diese Gruppen Phase 5/6 überspringen und direkt die Partitur
schreiben (bricht das Phasenmodell, morgen schneller). *Hängt ab:* ob
morgen Zeit für zwei Durchgänge (Prosa, dann Partitur) da ist.

**F4 — G2: Einwilligung und Filmen von Fremden im Skript.** 15–18-Jährige
filmen eine ahnungslose Person. *Empfehlung:* (a) Das Skript enthält die
Auflösungs-/Einwilligungsansprache in *rivelazione* als Entwurf; das
eigentliche Einwilligungsformular kommt von Birk/der Schule, der Bot
schreibt keines. Optionen: (a) · (b) Bot schreibt auch ein
Formular-Muster · (c) Einwilligung ganz aus dem Skript, regelt die
Leitung. *Hängt ab:* Inhalt `versuchsanordnung.md`, Abbruchregel.

**F5 — Richter für Partitur-Formen: c1 (Stimme) abschalten?**
*Empfehlung:* (a) c1 aus, a10 (Materialtreue) an, für alle drei. Optionen:
(a) · (b) c1 für G2 behalten (Influencer tragen Positionen) — misst aber
Improvisation, die nicht geschrieben wird · (c) zusätzlich heute die
deterministische Zitat-/Strukturprüfung bauen (+60 min, sprengt 4 h).
*Hängt ab:* Schritt 4, Umfang Abschnitt 8.

**F6 — Testbot-Abnahme mit echten Modellaufrufen heute Abend?**
Skripte, die Geld kosten, laufen nie automatisch. *Empfehlung:* (a) ja,
drei Szenenläufe auf `padua-test.db` (je Gruppe eine Szene, geschätzt
deutlich unter 1 CHF). Optionen: (a) · (b) nur Prompt-Dump ansehen, kein
Modellaufruf · (c) Abnahme morgen früh mit Birk. *Hängt ab:* Schritt 7 und
ob Birk morgen ein geprüftes Ergebnis sieht.

---

## 8. Bewusst nicht heute (mit Grund)

- **Format-Overlay je Gruppe** (Ansatz 2) — sauberer, aber neue Spalte und
  Umbau von `weiter_7`, kollidiert mit cc-p6test.
- **Deterministische Partitur-Prüfung** (Blockstruktur, `[Int. N]` +
  `zitat.pruefe` gegen das Transkript) — richtig und modellfrei, aber
  eigener Baustein; erster Kandidat für morgen.
- **Ganzes-Stück-Artefakte** (G1 Gesamt-Setlist mit Tonarten, G2 Drehplan
  über alle Momente, G3 Cue-Liste für die Technik) — heute steht der
  Gesamtblick im Textbuch durch die Aneinanderreihung der Szenen; ein
  zusammenfassender Kopf wäre ein zusätzlicher Lauf.
- **Formberater im Schreibweg** — er bleibt Gesprächshilfe; die Wahl
  trifft die Gruppe über `szene.form`.
- **Weitere Formate/Gruppen, Dortmund** — eingefroren bzw. nicht gefragt.
- **Neue Felder für Musik-Cues, Video-Inhalte, Positionen** — die Partitur
  leitet sie aus vorhandenen Feldern ab oder setzt Platzhalter; Felder erst,
  wenn die Gruppen sie auf der Workbench pflegen wollen.

## 9. Offene Punkte für Phase 2 (`writing-plans`)

- Prüfen, ob `_AUFTRAG_BUEHNE`/`VORLAGE_KOPF` („Translate it into the form")
  für Partituren passt oder je eigenständiger Form einen Zusatzsatz braucht.
- Prüfen, ob die Schärfungsstellen je Szene (G1/G3 nur Szenen-Zuordnung,
  `profil.toml:291`) mit Interviewnummer im Nutzertext ankommen — die
  Formblöcke setzen das voraus.
- `sprechweise.starte` in `weiter_7` ist für Funktionen/Performer als sie
  selbst überflüssig: überspringen, wenn alle Szenen eine eigenständige Form
  haben? (klein, in `ueberarbeitung.py` → mit cc-p6test abstimmen).
- An die Gruppe G2 (nicht Birk): wer filmt?

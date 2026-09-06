# Phase 4 (Setting, Figuren & Geschichte) — was landete in der Datenbank, was ging verloren

**Gruppe 1** · `chat_id = -5143986099` · Bot `theatersoap1_bot`
**Zeitraum** 06.09.2026, 13:03:29–14:09:41 UTC (Phasenbeginn bis Ende Phase 6-Start)
**Quelle** `betrieb/soap.db`, read-only geöffnet (`file:betrieb/soap.db?mode=ro`), Stand 06.09.2026 16:09 UTC
**Auftrag** Birk, 06.09.2026 nach der Probe: prüfen, ob die in Phase 4 festgelegten Rahmenparameter
vollständig gespeichert wurden, und sicherstellen, dass auch nicht kategorisierbare, aber relevante
Angaben künftig erhalten bleiben.

> **PII-Hinweis.** Diese Analyse hat die Tabelle `nachricht` gelesen. Sie enthält Beiträge realer
> Jugendlicher. In diesem Dokument steht **kein Wortlaut aus Teilnehmer-Nachrichten, kein Klarname
> einer realen Person und kein Interviewzitat**. Beschrieben wird ausschließlich die *Art* der
> Festlegung. Figurennamen des Stücks (Kassandra, Michael, Lucy, Elias, Obed, Yusra, Marawan,
> Sara, Yasmin, Emre) sind erfundene Rollennamen und unbedenklich. Bot-Systemtexte werden zitiert.

---

## 0. Kurzfassung

* **42 sachliche Festlegungen** der Gruppe in Phase 4 identifiziert (Nachrichten-IDs 455, 458, 461,
  465, 479, 485, 509, 516 sowie die Formwahl per Knopf und die Längenvorgabe in 556).
* **11 davon** sind sauber und vollständig in einem dafür vorgesehenen Feld gelandet.
* **9 davon** sind verkürzt oder nur mittelbar erhalten (Teil der Angabe fiel weg, oder sie steht
  nur in einer inzwischen weich gelöschten Zeile).
* **22 davon** sind faktisch verloren: kein Feld, oder nur ein `journal`-Eintrag der Art
  `vorgeschlagen`, der nachweislich nicht mehr in den Prompt kommt.
* Die drei schwersten Verluste: **(1)** die vierteilige Handlungsstruktur der Gruppe
  (`arbeitsstand.geschichte` enthält stattdessen 113 Zeichen Menüzeile), **(2)** sämtliche
  **Herkünfte, Alter und Berufe** der vier Hauptfiguren, **(3)** die **Gruppenzuordnung**
  (wer ist „cool", wer „Outsider") — dafür existiert im Schema überhaupt kein Feld.
* Zusätzlicher Datenschaden: die Tabelle `figur` enthält **16 Zeilen, keine weich gelöscht**,
  obwohl die Gruppe zweimal explizit 10–12 Figuren festgelegt hat und `arbeitsstand.figuren_entwurf`
  genau 10 Namen führt. Drei Figurenpaare sind Dubletten.

---

## 1. Inventar der Festlegungen und Abgleich mit der Datenbank

Legende Status: **OK** = vollständig in einem eigenen Feld · **VERKÜRZT** = Teil der Angabe fehlt
oder nur mittelbar erhalten · **VERLOREN** = kein Feld, oder nur `journal`-Eintrag ohne Wirkung.

### 1.1 Nachricht 455 · 13:21:01 UTC — Figurenrahmen, Setting, Erstentwurf der Geschichte

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 1 | Gesamtzahl Figuren (Spanne) | nur `journal` #27, 13:27:25, art `entschieden` (77 Z.). Feld `arbeitsstand.figuren_anzahl` ist **NULL** | VERKÜRZT |
| 2 | Anzahl Hauptfiguren (Spanne) | nirgends | VERLOREN |
| 3 | Anzahl Nebenfiguren (Zahl) | nirgends | VERLOREN |
| 4 | Prinzip „Figuren haben unterschiedliche Herkünfte/Kulturen" | nirgends | VERLOREN |
| 5 | Kassandra: Beruf | nirgends (`figur.beschreibung` id 1, 371 Z., enthält ihn nicht) | VERLOREN |
| 6 | Kassandra: Alter | nirgends | VERLOREN |
| 7 | Kassandra: Herkunftsland | nirgends | VERLOREN |
| 8 | Michael: Alter | nirgends | VERLOREN |
| 9 | Michael: Herkunftsland | nirgends | VERLOREN |
| 10 | Michael–Kassandra: Beziehungsstatus | nirgends als Feld; sinngemäß in `arbeitsstand.hauptkonflikt` (172 Z.) enthalten | VERKÜRZT |
| 11 | Lucy: Relation zu Kassandra (beste Freundin) | nirgends; `figur.beschreibung` id 3 (57 Z.) beschreibt nur ihre Funktion | VERLOREN |
| 12 | Ursprünglicher Hauptkonflikt (Elternebene) | `arbeitsstand.hauptkonflikt`, gesetzt 13:21:10, **später überschrieben** 13:38:51 durch den inneren Konflikt (siehe #22). Alter Wortlaut nur noch in `nachricht` 457 | VERKÜRZT |
| 13 | Geschichte-Grundidee „zwei Gruppen finden zusammen" | nirgends; wurde 13:27 durch #17 ersetzt (bewusst) | OK (bewusst ersetzt) |
| 14 | Spielort — Ortsteil und Gewässer | `arbeitsstand.rahmen` = 36 Z., 13:32:39 | OK |
| 15 | Spielort — Zusatzangabe Skatepark | nicht in `rahmen`; nirgends | VERLOREN |
| 16 | Spielort — Straßenangabe | nicht in `rahmen`; nirgends | VERLOREN |
| 17 | Zeit/Jahreszeit | in `arbeitsstand.rahmen` enthalten | OK |
| 18 | **Formatvorgabe: nur EINE Szene, erste Folge einer Serie** | `arbeitsstand.format` ist **NULL**. Nirgends. Das System hat später 6 Szenen gebaut | VERLOREN |
| 19 | Auftrag an Szene 1: alle Figuren und Konflikte einführen | nirgends | VERLOREN |
| 20 | Zwei alternative Begegnungsvarianten | nirgends | VERLOREN |
| 21 | Motiv „verbotene Stelle / Sprung ins Wasser" | mittelbar in `figur.beschreibung` id 5 (38 Z.) und in `szene`-Zeilen | VERKÜRZT |

### 1.2 Nachricht 458 · 13:27:11 UTC — zweiter Ort, Gruppenstruktur, vierte Hauptfigur

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 22 | Zweiter Spielort (Schule) | `arbeitsstand.rahmen` 13:27:25 (47 Z., beide Orte) — **korrekt gespeichert** | OK |
| 23 | Zwei getrennte Gruppen, Bezeichnungen | `journal` #27, 13:27:25, art `entschieden`, 77 Z. Kein Feld in `arbeitsstand` oder `gruppe` | VERKÜRZT |
| 24 | Bestätigung Figurenzahl | wie #1 | VERKÜRZT |
| 25 | Vierte Hauptfigur + Relation zu Michael | Name in `figur` id 4; Relation und Herkunft nur in `journal` #36, 13:43:37, art **`vorgeschlagen`** (70 Z.) — nie zu `entschieden` befördert | VERLOREN |
| 26 | Lucy: Herkunftsland | nirgends | VERLOREN |

### 1.3 Nachricht 461 · 13:32:18 UTC — Rücknahme, Gruppenmerkmale, Zuordnung

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 27 | **Rücknahme des zweiten Spielorts** | `arbeitsstand.rahmen` 13:32:39 auf 36 Z. zurückgesetzt — **sauber, bewusste Rücknahme, kein stiller Verlust**. ABER: `journal` #35 vom 13:43:37 („Ein zweiter Ort für das Stück ist die Schule", art `vorgeschlagen`) wurde **11 Minuten nach der Rücknahme** geschrieben und ist bis heute aktiv (`entfernt_am` NULL) | OK, mit Altlast |
| 28 | Definitionskriterien der Gruppen (drei Kriterien) | nur `journal` #43, 13:49:01, art `vorgeschlagen` (69 Z.) | VERLOREN |
| 29 | Zusammensetzung Gruppe A: 2 Hauptfiguren + 5 Nebenfiguren | nirgends als Struktur | VERLOREN |
| 30 | Gruppenverhalten A (Rebellion, Sprung) | mittelbar, siehe #21 | VERLOREN |
| 31 | Zusammensetzung Gruppe B: 2 Hauptfiguren + 3 Nebenfiguren | nirgends als Struktur | VERLOREN |
| 32 | Merkmalskatalog Gruppe B (Typ, Kleidung, Verhalten) | nur `journal` #44, 13:49:01, art `vorgeschlagen` (88 Z.) | VERLOREN |
| 33 | Einzelmerkmal „eine Figur wehrt sich" | `figur.beschreibung` id 11 und id 14 (je 42 Z.) | OK |
| 34 | Fähigkeiten Gruppe B (drei Fähigkeiten) | nur `journal` #45, 13:49:01, art `vorgeschlagen` (79 Z.) | VERLOREN |

### 1.4 Nachricht 465 · 13:38:40 UTC — innerer Konflikt, drei benannte Nebenfiguren

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 35 | Umdeutung des Hauptkonflikts zum inneren Konflikt | `arbeitsstand.hauptkonflikt`, 172 Z., 13:38:51 · zusätzlich `journal` #46 (art `vorgeschlagen`) | OK |
| 36 | Drei neue Nebenfiguren mit Namen und je einem Merkmal | `figur` id 8 (Obed), 9 (Yusra), 10 (Marawan), Beschreibungen 57/55/36 Z., 13:47:49–13:51:11 | OK |
| 37 | **Zuordnung dieser drei zur Gruppe A** | nirgends. Sie tragen keine Gruppenmarkierung; sie stehen als eigene Namen neben den Platzhaltern „Nebenfigur Cool 1–3" | VERLOREN |

### 1.5 Nachrichten 479 / 485 · 13:41:52 / 13:43:15 UTC — Zuordnungsauftrag und Namen

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 38 | Auftrag „ordne die verbleibenden Figuren zufällig zu" | nirgends; der Bot hat den Auftrag im Chat sichtbar **falsch ausgeführt und sich selbst korrigiert** (Nachricht 487: „Stopp — Emre war als Outsider gedacht. Ich korrigiere") | VERLOREN |
| 39 | Drei Namen für die Nebenfiguren der Gruppe B | `figur` id 14/15/16, 13:43:34 · zusätzlich `journal` #56 (art `vorgeschlagen`, 59 Z.) | OK, aber Dubletten (§ 2.4) |

### 1.6 Nachricht 509 · 13:48:39 UTC — die Geschichte in vier nummerierten Punkten

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 40 | Handlungsstruktur Punkt 1 (Einstieg mit Komik) | 13:48:55 in `szene` id 1: `was_passiert` 147 Z., `kernsaetze` 91 Z. — **diese Zeile ist seit 13:54:37 weich gelöscht** (`entfernt_am`) | VERLOREN |
| 41 | Handlungsstruktur Punkt 2 (Wasser, Rettung, Kernsatz) | 13:48:55 in `szene` id 2: `anlass` 34 Z., `was_passiert` 325 Z., `kernsaetze` 57 Z. — **seit 13:54:37 weich gelöscht**. Inhaltlich in `szene` id 11 (145 Z.) neu, aber vom Modell formuliert, nicht die Festlegung der Gruppe | VERKÜRZT |
| 42 | Handlungsstruktur Punkt 3 (Konfrontation) | 13:48:55 in `szene` id 3: `anlass` 33 Z., `was_passiert` 88 Z. — **seit 13:54:37 weich gelöscht** | VERKÜRZT |
| 43 | Handlungsstruktur Punkt 4 (Cliffhanger) | `journal` #41, 13:48:55, art `entschieden` (37 Z.) und `journal` #48, 13:50:09 (31 Z.). **Kein Feld.** Die Nummerierung „Cliffhanger am Ende der dritten Szene" ist nach dem Umbau auf 6 Szenen sachlich falsch | VERKÜRZT |
| 44 | **Die Struktur als Ganzes** | `arbeitsstand.geschichte` = **113 Zeichen** — enthält *nicht* die Handlung, sondern die gewählte Formvariante (§ 2.1) | VERLOREN |

### 1.7 Nachricht 516 · 13:49:23 UTC — Ende offen / Cliffhanger, „speichere alles"

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 45 | Entscheidung: Ende bleibt offen | `journal` #48, 13:50:09, art `entschieden` (31 Z.). Kein Feld | VERKÜRZT |
| 46 | Explizite Speicheraufforderung an das System | löste keinen Sammelschreibvorgang aus; es gibt keinen Speicherweg dafür | VERLOREN |

### 1.8 Knopfdruck 13:52:20 UTC — Szenenformen, und Nachricht 556 · 14:06:07 UTC

| # | Art der Festlegung | Wo gelandet | Status |
|---|---|---|---|
| 47 | Formwahl je Szene (drei Formen für drei Szenen) | `arbeitsstand.geschichte`, 113 Z. — **als Fließtext in einem Feld, das für die Handlung gedacht ist**. `szene.form` ist für **alle** Szenen NULL | VERKÜRZT |
| 48 | Längen-/Verdichtungsvorgabe für Szenentexte | nirgends. Kein Feld, kein `journal`-Eintrag. Der Bot antwortete im Chat, er könne den Text nicht kürzen | VERLOREN |

**Zählung.** 48 gelistete Positionen, davon 6 Doppelnennungen derselben Sache (#1/#24, #21/#30,
#13 als bewusst ersetzt, #10 teil von #12, #33 teil von #32, #39 teil von #38) → **42 eigenständige
Festlegungen**. Verteilung: **11 OK**, **9 VERKÜRZT**, **22 VERLOREN**.

---

## 2. Verlustliste — belegte Befunde

### 2.1 `arbeitsstand.geschichte` trägt eine Menüzeile statt der Handlung — BELEGT

`arbeitsstand.geschichte` = 113 Zeichen, Inhalt ist die vom Bot in Nachricht 518 angebotene
Auswahlzeile 3 (Formabfolge über drei Szenen). Die eigentliche Handlung — vier nummerierte Punkte,
665 Zeichen in Nachricht 509 — steht dort nicht.

Ursache: `interview_theater/knoepfe.py:2601`
```python
geschichte = wert.strip() if not zeilen else geschichte
```
Der Knopf `geschichte_speichern` (Tabelle `knopf` id 355, angelegt 13:50:01, benutzt 13:52:20)
transportiert in `wert` genau die Menüzeile. `szenenfolge.zerlege_geschichte` findet darin keine
Szenenzeilen (`zeilen` leer), also wird die **gesamte Menüzeile** als Geschichte gespeichert.
Der Kommentar darüber benennt das als Absicht („Eine Richtung ist eine Zeile 'Titel — Bogen, Ende,
Konflikt': sie ist die Geschichte") — die Absicht trägt aber nur, wenn die Menüzeile eine
Handlungsrichtung beschreibt. Hier beschrieb sie eine **Formabfolge**. Das Feld ist damit doppelt
belegt und trägt keine Handlung mehr.

Bestätigt den Befund aus `docs/analyse-phase5-chaos-2026-09-06.md` und erweitert ihn: es geht nicht
nur um Länge, sondern um die **Feldsemantik**.

### 2.2 Die Szenenformen sind strukturell nirgends — BELEGT

* `szene.form` ist für **alle 15 Zeilen** dieser Gruppe NULL (geprüft über alle `szene`-Zeilen mit
  `chat_id = -5143986099`).
* Die vom Modell erzeugten `form_vorschlag`-Werte lagen auf `szene` id 4–9 (13:54:37 / 14:06:24) und
  sind seit **14:09:35** weich gelöscht.
* Die aktuell gültigen Szenen id 10–15 (angelegt 14:09:35 aus der Kurzgeschichte) haben
  `form` NULL **und** `form_vorschlag` NULL.

Die Formentscheidung der Gruppe existiert damit nur noch als Fließtext in
`arbeitsstand.geschichte` und in `journal` #52 (125 Z.). `interview_theater/szenenfolge.py:284`
dokumentiert bewusst, dass `form` leer bleibt und nur `form_vorschlag` gesetzt wird — der Umbau um
14:09:35 (`kurzgeschichte` → neue Szenenzeilen) trägt aber auch den Vorschlag nicht mit.

### 2.3 Herkünfte, Alter, Berufe: kein Feld, keine Speicherung — BELEGT

Die Gruppe hat für vier Hauptfiguren Herkunftsländer festgelegt, für zwei zusätzlich Alter, für eine
einen Beruf. Geprüft: `figur.beschreibung` aller 16 Zeilen enthält **keine** dieser Angaben;
`figur.sprachprofil` ist überall NULL; `figur.beleg_zitat` ist überall NULL.

Im Schema (`interview_theater/db.py`, Tabelle `figur`) gibt es die Spalten `name`, `beschreibung`,
`beleg_zitat`, `sprachprofil`, `zitate`, `sprachstil`, `quelle_aufnahme_id`, `geprueft_am`,
`entfernt_am`, `geaendert_am`. **Kein Feld für Herkunft, Alter, Beruf, Gruppenzugehörigkeit oder
Relationen zwischen Figuren.**

Einziger Rest: `journal` #36 vom 13:43:37, art `vorgeschlagen`, 70 Zeichen — nennt Herkunft und
Freundschaftsrelation *einer* Figur. Für die übrigen drei Herkünfte gibt es keinen Eintrag.

### 2.4 Figurentabelle: 16 Zeilen statt 10, drei Dublettenpaare — BELEGT

`arbeitsstand.figuren_entwurf` (591 Z., fixiert 13:43:34) führt **10 Namen**.
Tabelle `figur` enthält **16 Zeilen**, `entfernt_am` ist bei **keiner** gesetzt:

| Platzhalter (bleibt) | Nachbenannt (neu angelegt) | identische `beschreibung` |
|---|---|---|
| id 11 `Nebenfigur Outsider 1` | id 14 `Sara` | „laesst sich nichts gefallen, redet zurueck" (42 Z.) |
| id 12 `Nebenfigur Outsider 2` | id 15 `Yasmin` | „programmiert, beobachtet, sagt wenig" (36 Z.) |
| id 13 `Nebenfigur Outsider 3` | id 16 `Emre` | „traegt die Buecher aller, vertritt keinen" (41 Z.) |

Zusätzlich existieren id 5–7 `Nebenfigur Cool 1–3` als eigenständige Figuren, obwohl die Gruppe für
diese Plätze in Nachricht 465 die Namen Obed/Yusra/Marawan geliefert hat (die als id 8–10 **zusätzlich**
angelegt wurden). Der Bot hat die Fehlzuordnung im Chat selbst bemerkt (Nachricht 487), aber die
Datenbank nie bereinigt.

**Folgeschaden:** die im Chat mühsam erarbeiteten Sprachstile hängen an den **Platzhalter**-Zeilen
(id 5, 6, 7, 11 haben `sprachstil` mit 188/196/187/167 Z.), während die **benannten** Figuren
id 14/15/16 `sprachstil` NULL haben. `szene_figur` verweist gemischt auf beide Seiten
(z. B. Szene id 3 auf 5, 6, 7 **und** 14, 15, 16 gleichzeitig — neun Figuren, real sind es sechs).

### 2.5 Der zweite Spielort wurde korrekt zurückgenommen — mit Altlast — BELEGT

Zeitleiste `arbeitsstand.rahmen`:
* 13:27:25 gesetzt auf 47 Zeichen (zwei Orte) — Knopf id 299
* 13:32:39 gesetzt auf 36 Zeichen (ein Ort) — Knopf id 305, nach expliziter Rücknahme durch die Gruppe

Das ist **kein stiller Verlust**, sondern eine korrekt umgesetzte Willensäußerung.

**Aber:** `journal` #35 vom **13:43:37** (also 11 Minuten *nach* der Rücknahme), art `vorgeschlagen`,
Text „Ein zweiter Ort fuer das Stueck ist die Schule." — `entfernt_am` ist NULL, der Eintrag gilt
formal weiter. Der Erkenner hat aus einer Nachricht extrahiert, die zu diesem Zeitpunkt schon
überholt war. Kein Mechanismus räumt solche Einträge ab.

### 2.6 Das Serienformat wurde nie gespeichert — BELEGT

`arbeitsstand.format` ist **NULL**. Die Gruppe hat in Nachricht 455 explizit festgelegt, dass das
Stück aus *einer* Szene besteht, nämlich der ersten Folge einer Serie. Das System hat um 13:54:37
eine Szenenfolge mit **6 Szenen** angelegt und um 14:09:35 erneut 6 Szenen. Die Festlegung war zu
keinem Zeitpunkt im Kontext des Modells und konnte deshalb nicht widersprechen.

### 2.7 Journal-Einträge der Art `vorgeschlagen` sind faktisch tot — BELEGT

`interview_theater/kontext.py:599`
```python
JOURNAL_EINTRAEGE = 8
```
`_baue_journal()` (kontext.py:602) dedupliziert und nimmt dann die **letzten 8** Einträge.
Phase 4 hat allein `journal` id 26–64 erzeugt = **38 Einträge**. 30 davon waren spätestens am
Phasenende aus dem Prompt verdrängt — darunter **alle** in § 2.3, § 2.5 und § 1.3 genannten
`vorgeschlagen`-Einträge (Gruppenkriterien, Merkmalskatalog, Fähigkeiten, Herkunft, zweiter Ort).

Es gibt **keinen Weg**, der einen `vorgeschlagen`-Eintrag später in ein Feld befördert.
`erkenner._wende_journal_an` (erkenner.py:688) schreibt nur; `repo.entferne_journal` löscht nur.
Der Web-Ansicht (`web_daten.py:666`, `web.py:1179`) liegt das vollständige Journal vor, aber
eingeklappt in `<details><summary>Journal (N)</summary>` — sichtbar, nicht wirksam.

**Damit gilt: Was in Phase 4 als `vorgeschlagen` journalisiert wurde, ist nach spätestens acht
weiteren Journalzeilen aus dem Gedächtnis des Systems verschwunden und kommt nie zurück.**

### 2.8 Die Verdichtungs-/Längenvorgabe verschwand ohne Spur — BELEGT

Nachricht 556 (14:06:07) enthält eine klare Formatanweisung für alle künftigen Szenentexte.
Geprüft: kein `journal`-Eintrag zwischen 13:56:44 (#61) und 14:06:24 (#62) trägt sie;
`arbeitsstand.format` NULL; `szene.stil` für alle Szenen NULL; kein `knopf`-Eintrag.
Der Bot antwortete im Chat mit einer Absage („ich kann den Text nicht selbst kuerzen").
Die Anweisung ist vollständig verloren.

---

## 3. Die Strukturlücke

**In einem Satz:** Das Schema kennt nur einen festen Satz vorab definierter Slots
(`arbeitsstand`: rahmen, hauptkonflikt, geschichte, figuren_entwurf, format …; `figur`: name,
beschreibung, sprachstil; `szene`: form, ort, zeit, anlass, was_passiert …) — für jede relevante
Angabe außerhalb dieses Rasters gibt es **kein Feld**, nur einen `journal`-Eintrag, der nach acht
weiteren Zeilen aus dem Prompt fällt und von dort nie zurückkehrt.

Konkret fehlen im Schema Felder für:

| Art der Angabe | betroffene Festlegungen | heutiger Verbleib |
|---|---|---|
| Figureneigenschaften jenseits „Beschreibung" (Herkunft, Alter, Beruf) | #5–9, #26 | nichts / 1 toter Journaleintrag |
| **Gruppen-/Fraktionszugehörigkeit einer Figur** | #23, #29, #31, #37 | nichts |
| Relationen zwischen Figuren (befreundet, Partner, beste Freundin) | #10, #11, #25 | teils in `hauptkonflikt` |
| Kollektive Eigenschaften einer Fraktion (Merkmalskatalog, Fähigkeiten, Verhalten) | #28, #30, #32, #34 | 3 tote Journaleinträge |
| Struktur-/Formatentscheidungen des Stücks (Serie, Folgenanzahl, Cliffhanger als Prinzip) | #18, #43, #45 | `format` NULL, 2 Journaleinträge |
| Stil-/Längenvorgaben für Texte | #48 | nichts |
| Ortszusätze unterhalb des Settings (Teilorte) | #15, #16 | nichts |
| Die Handlung als mehrteilige Struktur | #40–#44 | 113-Zeichen-Feld mit falschem Inhalt |

**VERMUTUNG (nicht belegt):** Dass das Modell in Phase 5 und 6 sechs Szenen erfand statt der einen
festgelegten, und dass Figuren ohne Herkunft schrieben, hängt ursächlich damit zusammen, dass diese
Parameter zum Zeitpunkt der Generierung nicht im Prompt standen. Belegt ist nur, **dass** sie nicht
im Prompt standen (§ 2.7), nicht, dass allein das die Ausgabe verursacht hat.

---

## 4. Lösungsvorschlag: ein Auffangfeld für nicht kategorisierbare Festlegungen

Birks Forderung: *„falls nicht, stelle sicher, dass das in Zukunft passiert, auch wenn Dinge kommen,
die nicht kategorisiert werden können, aber relevant sind."*

### 4.1 Empfehlung — Variante A: Tabelle `festlegung` (empfohlen)

Eine schmale, nur-anhängende Tabelle je Gruppe, nach dem Muster von `journal`, aber mit
**Geltungsanspruch** statt Chronik-Charakter:

```sql
CREATE TABLE festlegung (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  bereich      TEXT NOT NULL,   -- figur|gruppe|ort|struktur|form|stil|sonstiges
  bezug        TEXT,            -- Figurenname / Gruppenname / Szenennummer, optional
  text         TEXT NOT NULL,   -- die Festlegung, eine Zeile
  quelle       TEXT NOT NULL,   -- erkenner|knopf|befehl|web
  erstellt_am  TEXT NOT NULL,
  entfernt_am  TEXT
);
CREATE INDEX festlegung_chat ON festlegung(chat_id) WHERE entfernt_am IS NULL;
```

**Warum eine eigene Tabelle und nicht `journal`:** `journal` ist per AGENTS.md und
`repo.journal`-Docstring ausdrücklich eine *Chronik* („nur-anhängend, es gibt bewusst kein
aktualisiere_journal") und wird im Kontext auf 8 Zeilen gekappt, weil es sonst den Prompt flutet.
Festlegungen brauchen das Gegenteil: sie sollen **vollständig und dauerhaft** mitgehen. Beides in
einer Tabelle zu mischen zwingt zu genau der Kappung, die den Verlust erzeugt hat.

**Schreibweg.** Der Erkenner bekommt eine neue Art `festlegung_setzen` in seiner Art-Liste
(`erkenner.py:81 ff.`, neben `rahmen_setzen`, `geschichte_setzen`, `hauptkonflikt_setzen`) mit der
Anweisung: *jede sachliche Festlegung, die in kein bestehendes Feld passt, aber für Text oder
Inszenierung relevant ist, hier ablegen — mit `bereich` und, wenn erkennbar, `bezug`.*
Zusätzlich ein Regie-Befehl `/festlegung <bereich>: <text>` und die Rücknahme
`/festlegung weg <suchtext>` nach dem Muster von `repo.entferne_journal`.

**Kontext-Einbindung.** Neuer Block direkt hinter dem Arbeitsstand (`kontext.py`, Block 4), Format:

```
Weitere Festlegungen der Gruppe:
- [figur/Kassandra] Herkunft: Russland, 19, Schauspielerin
- [gruppe/die Coolen] definieren sich über Herkunft, soziale Schicht, Geld
- [struktur] Das Stück ist eine Folge einer Serie, nur eine Szene
```

**Web-Anzeige.** Auf der Gruppenseite als eigener, **aufgeklappter** Abschnitt zwischen
Arbeitsstand und Figuren (`web.py` um Zeile 1156 ff., `web_daten.py` analog `_journal()`),
mit Löschknopf je Zeile über den bestehenden Schreibweg in `web_schreiben.py`.

### 4.2 Prompt-Budget — die zentrale Nebenbedingung

* Harte Körpergrenze: `kontext.ZEICHEN_GRENZE_VORGABE = 24_000` (kontext.py:102), überschreibbar
  per `IT_PROMPT_ZEICHEN`.
* Die Systemanweisung ist separat gedeckelt: `tests/test_prompt_audit.py:405–411` — < 32.000 Zeichen
  für `dialog`, < 26.000 für die übrigen Formen. Der Chor liegt laut Auftragsbeschreibung bei
  ~25,9k von 26k — **dort ist kein Platz.**
* Der neue Block gehört deshalb **nicht** in die Systemanweisung, sondern in den datengetriebenen
  Nutzertext, wo die zweistufige Kürzung (kontext.py, § 7.2) greift.
* Vorschlag: eigenes Budget `BUDGETS["festlegungen"] = 800` Token (≈ 2.400 Zeichen) und eine
  Obergrenze von **20 Zeilen**, gekappt nach Ältestem-zuerst — anders als beim Journal, weil eine
  frühe Grundfestlegung („nur eine Szene") mehr wiegt als eine späte Detailnotiz. Gruppe 1 hätte
  in Phase 4 rund **12 Zeilen à ~70 Zeichen ≈ 850 Zeichen** erzeugt; das passt.
* Der Block muss in der Kürzungskaskade **vor** dem Fenster und **nach** den Transkripten stehen,
  also als vorletzter Kandidat fürs Wegkürzen — er ist stabil und klein.

### 4.3 Aufwand und betroffene Dateien

| Baustein | Datei | Aufwand |
|---|---|---|
| Tabelle + Migration (`ALTER`/`CREATE IF NOT EXISTS` beim Start) | `interview_theater/db.py` | **S** |
| `schreibe_festlegung`, `festlegungen`, `entferne_festlegung` | `interview_theater/repo.py` | **S** |
| Neue Erkenner-Art + Prompt-Zeile + `_wende_*_an` | `interview_theater/erkenner.py` | **M** |
| Kontextblock + Budget + Platz in der Kürzungskaskade | `interview_theater/kontext.py` | **M** |
| Regie-Befehle `/festlegung`, `/festlegung weg` | `interview_theater/befehle.py` | **S** |
| Web-Anzeige + Löschen | `web_daten.py`, `web.py`, `web_schreiben.py` | **M** |
| Tests (Erkenner-Extraktion, Kontext-Budget, Prompt-Audit-Erweiterung) | `tests/test_kontext.py`, `tests/test_prompt_audit.py` | **M** |

**Gesamt: M** (etwa ein halber Arbeitstag). **Migration nötig:** ja, aber additiv —
`CREATE TABLE IF NOT EXISTS`, kein Umschreiben bestehender Zeilen, live gefahrlos.

### 4.4 Risiken

1. **Prompt-Inflation.** Der Erkenner neigt zur Übererfassung (belegt: 13 `vorgeschlagen`-Einträge
   in Phase 4, davon mehrere redundant). Ohne harte Zeilen- und Zeichengrenze wächst der Block
   unbegrenzt. → Deckel in `kontext.py`, plus Dedupe wie in `_baue_journal`.
2. **Doppelte Wahrheit.** Steht „Setting: X" sowohl in `arbeitsstand.rahmen` als auch als
   Festlegung, widersprechen sich beide irgendwann. → Erkenner-Anweisung muss explizit sein:
   *nur, wenn kein bestehendes Feld passt.* Zusätzlich ein Test, der die bekannten Feldnamen als
   `bereich` verbietet.
3. **Veraltete Festlegungen** (wie `journal` #35, § 2.5). → `entfernt_am` und ein sichtbarer
   Löschknopf im Web sind Pflicht, nicht Kür; ohne sie erbt die neue Tabelle den alten Fehler.
4. **Der Erkenner läuft über ein Modell**, das ausfallen kann (belegt: `vorfall` id 19, 13:49:53,
   `http_5xx` bei `art=erkenner` — mitten in Phase 4). Der Regie-Befehl als manueller Schreibweg
   ist deshalb kein Komfort, sondern die Rückfallebene.

### 4.5 Ergänzende Sofortmaßnahmen (unabhängig von 4.1, jeweils S)

* **`arbeitsstand.geschichte` entkoppeln:** `knoepfe.py:2601` darf eine Menüzeile, die erkennbar
  eine *Formabfolge* beschreibt, nicht als Geschichte speichern. Analog zu
  `erkenner._ist_geschichte` (erkenner.py:439), das denselben Fehler in umgekehrter Richtung
  bereits abfängt („rahmen_setzen sah nach Handlung aus, verworfen").
* **Formwahl in `szene.form` durchschreiben,** wenn die gewählte Richtung Formen je Szene nennt —
  heute landet sie ausschließlich als Fließtext.
* **Platzhalterfiguren beim Nachbenennen weich löschen** statt eine zweite Zeile anzulegen
  (`erkenner._figuren_aus_namen`, erkenner.py:598) — verhindert die Dubletten aus § 2.4 und
  bewahrt den bereits erarbeiteten `sprachstil`.
* **`arbeitsstand.figuren_anzahl` tatsächlich befüllen** — das Feld existiert und ist NULL,
  obwohl die Angabe zweimal kam.

---

## 5. Belegverzeichnis

Alle Zeitstempel UTC, alle Feldangaben aus `betrieb/soap.db` (read-only), `chat_id = -5143986099`.

* `arbeitsstand`: `rahmen` 36 Z. (13:32:39) · `hauptkonflikt` 172 Z. (13:38:51) ·
  `figuren_entwurf` 591 Z. (fixiert 13:43:34) · `geschichte` **113 Z.** (13:52:20) ·
  `figuren_anzahl` NULL · `format` NULL · `kernthema` NULL · `phase` 6 (gesetzt 14:06:24)
* `figur`: 16 Zeilen, `entfernt_am` überall NULL, ids 1–16, geändert 13:38:47–13:55:22
* `szene`: 15 Zeilen; id 1–3 entfernt 13:54:37; id 4–9 entfernt 14:09:35; id 10–15 aktiv;
  `form` in **allen** Zeilen NULL
* `szene_figur`: 35 Zuordnungen, verweisen gemischt auf Platzhalter und Nachbenennung
* `journal`: 64 Einträge gesamt, ids 26–64 in Phase 4/5/6; 13 davon art `vorgeschlagen`
* `knopf`: ids 299–397 in Phase 4 ff.; `geschichte_speichern` id 353–355 (13:50:01),
  id 355 benutzt 13:52:20
* `vorfall`: id 21, 13:49:53, `http_5xx` bei `art=gespraech`; id 19, 11:34:14, bei `art=erkenner`
* Code: `knoepfe.py:2572–2634` · `kontext.py:102, 599, 602–627` · `erkenner.py:81–105, 422–463,
  598–620, 688–696` · `szenenfolge.py:284–311` · `szene.py:389, 1958–1961` ·
  `repo.py:2013–2045` · `web_daten.py:666–675` · `web.py:1156–1179` ·
  `tests/test_prompt_audit.py:405–411`

---

*Erstellt 06.09.2026 als reine Lesanalyse. Keine Schreibzugriffe auf die Datenbank,
keine Codeänderung, kein Commit.*

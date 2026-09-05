# Prompt-Audit, 06.09.2026

Anlass: Birk, 06.09. 00:40 — *„Alle System-Prompts, die während des
Chatverlaufs ans Modell rausgehen, ansehen — sie können dafür extra generiert
werden — analysieren und verbessern. Vor allem so gravierende Fehler wie
gerade gefunden."*

Grundlage: **echte Prompts**, erzeugt gegen eine Kopie der Test-DB
(`scripts/erzeuge_prompts.py`, `scripts/fuelle_pruef_db.py`). Die Dumps liegen
neben diesem Dokument. Kein Prompt wurde von Hand geschrieben; alles unten
Genannte ist aus einer erzeugten Datei gemessen.

Schweregrade:

* **gravierend** — das Modell bekommt eine falsche Weltlage, verliert die
  Aufgabe oder liest widersprüchliche Fakten.
* **mittel** — Dubletten, Länge, Reihenfolge.
* **leicht** — Stil, Formulierung.

---

## Die drei Fragen aus dem Auftrag

### Warum ging um 21:50 der Vormittag mit?

Zwei Ursachen, die zusammenwirkten — und **keine davon war ein Modellfehler**.

1. `kontext._baue_fenster_eintraege` lädt bis zu `_FENSTER_POOL = 1000`
   Nachrichten und hat **kein eigenes Budget**. Die einzige Bremse war
   `ZIEL = 20.000 Token`, gemessen als Zeichen ÷ 3.
2. Der gemessene Nutzertext hatte 52.361 Zeichen → nach dieser Schätzung
   17.453 Token, also **unter** ZIEL. Die Kürzung nach § 7.2 wurde deshalb
   **nie ausgelöst**. Der Verlauf ging vollständig raus, rund 700 Zeilen bis
   in den Vormittag der übernommenen Gruppe-1-Historie.

Das Modell hat den Prompt korrekt gelesen: Vormittag und Abend standen
gleichberechtigt darin, der Vormittag umfangreicher. „Das ist Tag 1, wir
stehen erst am Anfang" ist die richtige Antwort auf einen falschen Prompt.

*Die Reihenfolge des Fensters (neueste zuerst) sowie der Systemzeilen-Filter
gehören dem Interaktions-Agenten und sind hier nicht angefasst — siehe
„Abgrenzung" unten.*

### Warum 52 k statt 8 k?

§ 7.2 nennt für das Fenster 8.000 Token, aber **im Code stand nie eine
Fenstergrenze**. Die Kommentare in `kontext.py` sagten das sogar ausdrücklich:
`BUDGETS` sei „rein dokumentarisch, wie in keinem der Blöcke einzeln
durchgesetzt". Die einzige tatsächliche Begrenzung war `ZIEL` über den
*Gesamt*prompt — und die wurde in der gemessenen Lage nicht erreicht.

Dazu kamen 15.000 Zeichen reine Dubletten (siehe G1–G3), die das Budget
zusätzlich füllten, ohne einen einzigen neuen Fakt zu tragen.

### Warum Phase 7 im Arbeitsstand?

**Kein Bug — korrekte Migration.** `db.PHASEN_UMNUMMERIERUNG_2 = {6: 7, 7: 8}`
rechnet beim Start alte Phasennummern auf das achtstufige Modell um
(`PRAGMA user_version` 1 → 2). Die Testgruppe stand auf der alten 6
(„Szenen") und wurde korrekt zur neuen 7 („Szentexte") migriert.

Der Widerspruch entstand woanders: das **Journal wird bewusst nie
umgeschrieben** (AGENTS.md — es hält fest, was die Gruppe damals entschieden
hat). Dort stand also weiterhin „Phase 6 · Szenen", während der Arbeitsstand
schon 7 sagte. Beides zusammen im selben Prompt liest sich wie ein
Widerspruch.

**Nichts an der Migration zu fixen.** Was gefixt ist: der Arbeitsstand nennt
die Phase genau einmal, das Journal wird auf die letzten 8 Einträge gekürzt,
und ein Test hält `prompt.count("Aktuelle Phase:") == 1` fest.

---

## Befunde je Pfad

### 1. Gesprächszug (`kontext.baue` + `anweisungen.system` + `phasen/N.md` + `zusatz.md`)

Gemessen vorher: **System 23.291, Nutzer 49.872 Zeichen** (24.387 Token).

| Nr | Befund | Schwere | Fix |
|----|--------|---------|-----|
| **G1** | Dieselbe Interview-Zusammenfassung stand **11×** im Kernpaket (je markiertem Thema einmal) — 7.700 Zeichen Dublette. Die Zusammenfassung gehört der Verdichtung, nicht dem Thema; `repo.kernthemen_themen` liefert sie je Zeile mit. | **gravierend** | Dedupe in `_baue_kernpaket`: einmal je Interview. |
| **G2** | Kernthema, Kernfrage, Geschichte, Rahmen und die Figurenzeilen standen **doppelt** — einmal im Kernpaket, einmal im Arbeitsstand. Rahmen faktisch dreimal („Setting (Rahmen)" + „Rahmen:" + in der Geschichte). | **gravierend** | `_baue_arbeitsstand(ohne_kernpaket_felder=True)`, sobald das Kernpaket im Prompt steht. Eine Quelle je Fakt. |
| **G3** | Journal mit 15 Zeilen, darunter „Szene 1 geschrieben" **4×** und vier Figurenzeilen mit demselben „basierend auf Interview 1"-Anhang. Das Modell hielt die eine geschriebene Szene für vier. | **gravierend** | `_baue_journal`: Dedupe (jüngster gewinnt), dann letzte `JOURNAL_EINTRAEGE = 8`. DB unangetastet. |
| **G4** | § 7.2 griff faktisch nicht (siehe oben). | **gravierend** | Harte Zeichengrenze `ZEICHEN_GRENZE_VORGABE = 24.000`, über `IT_PROMPT_ZEICHEN` konfigurierbar, mit definierter Kürzungsreihenfolge und Vorfall `kontext_gekuerzt` samt Zahlen. |
| **G5** | Systemanweisung sagte „grob in **sieben** Stationen" und listete darunter **acht**. | mittel | `system.md`: „acht Stationen". |
| G6 | Verlauf rückwärts, „Bin wieder da"-Systemzeilen doppelt. | gravierend | **Gehört dem Interaktions-Agenten**, hier nur dokumentiert. |

Nachher: **System 23.289, Nutzer 24.000 Zeichen** (15.763 Token) —
**−52 % Nutzertext**, alle konstruktionsbedingten Dubletten weg.

### 2. Erstkontakt

Derselbe Körper plus `ERSTKONTAKT`-Block. Vorher 50.861, nachher 23.903
Zeichen Nutzertext. Keine eigenen Befunde; erbt alle Fixes von 1.

### 3. Auftragszüge (`ablauf.auftragszug`)

Geprüft mit „Schlag du vor.", Namen, Duktus, Richtungen. Ein Auftragszug ist
ein Gesprächszug ohne auslösende Nachricht — er erbt **alle** Befunde von 1
und war ebenso 49 k lang. Der Auftrag selbst steht korrekt ganz am Ende
(`_AUFTRAG_KOPF`), wo er am schwersten wiegt. Nachher je ~24.100 Zeichen.
Vier Tests halten fest, dass die Anweisung die Kürzung überlebt.

### 4. Feldvorschlag

Läuft über `ablauf.starte_auftrag`, also identisch mit 3. 49.709 → 24.108
Zeichen.

### 5. Erkenner (`prompts/erkenner.md` + Arbeitsstand + Fenster)

System **31.066 Zeichen** — der längste System-Prompt im ganzen System, weil
er 20+ ausformulierte Few-Shot-Fälle trägt. Nutzer nur 2.423.

| Nr | Befund | Schwere |
|----|--------|---------|
| **E1** | Zeile 122 f.: *„Die **sieben** Phasen sind: 1 Begriffe, 2 Fragen, 3 Interviews, 4 **Kernthema & Figuren**, 5 **Format & Rahmen**, 6 Szenen, 7 Durchlauf."* — das ist das **alte** Modell. Der Erkenner setzt `phase_setzen` also gegen eine Skala, die es seit dem Umbau vom 05.09. nicht mehr gibt: sagt die Gruppe „wir machen jetzt Szenentexte", trifft er 6 statt 7. | **gravierend** |
| E2 | Beispiel-Eigennamen Mira/Pola/Pal/Polizeikessel in den Few-Shots. Anders als im Gesprächs-Prompt sind sie hier **legitim** (Few-Shot-Material), aber sie sind erwiesenermaßen nachplapperanfällig (05.09.: der Bot sagte dreimal „Pola"). | mittel |

**Nicht gefixt, bewusst.** `prompts/erkenner.md` darf laut Auftrag nur
geändert werden, wenn danach der Korpus läuft (`scripts.pruefe_prompts
erkenner --bericht`, FP = 0 Pflicht, ~10 min). Der Commit
`2277514 „Restliche Tests und Erkenner auf die acht Stufen"` sagt selbst:
*„erkenner.md bewusst unangetastet — ein Korpuslauf war nachts nicht
möglich"*. **E1 ist damit ein bekannter, offener gravierender Befund und
gehört als erstes auf die Liste des nächsten Korpuslaufs.**

### 6. Verdichter

System 3.259, Nutzer 3.346 Zeichen. Fragenliste vorn, Transkript hinten,
sauber getrennt. **Keine Befunde.**

### 7. Journal-Extraktor

System 5.070, Nutzer 1.545. Bekommt bewusst nur den verdrängten Abschnitt
plus Dedup-Referenz, nicht das ganze Gespräch. **Keine Befunde.**

### 8. Sprachprofil

System 2.458, Nutzer 2.413 (nur das Transkript). Bewusst ohne Arbeitsstand
und ohne Figurennamen. **Keine Befunde.**

### 9. Kernzitate

Gemessen vorher: System 2.483, **Nutzer 8.941 Zeichen**.

| Nr | Befund | Schwere | Fix |
|----|--------|---------|-----|
| **M1** | Jede der 11 Materialzeilen trug die **vollständige Interview-Zusammenfassung** — derselbe 700-Zeichen-Absatz 11×, also 7.700 von 8.941 Zeichen reine Dublette. Dritte Codestelle desselben Fehlers (vgl. G1, S2). | **gravierend** | Zusammenfassung einmal je Interview, als eigene Zeile über den Materialzeilen. |

Nachher: **Nutzer 1.558 Zeichen** — **−83 %**. Die Nummerierung, über die das
Modell auf einen Eintrag zeigt, bleibt unverändert.

### 10. Schärfung

Gemessen vorher: System 2.103, **Nutzer 9.743 Zeichen**. Derselbe Befund M1,
vierte Codestelle — `schaerfung.baue_nutzertext` baut die Materialliste
wortgleich wie `kernzitate`. Gleicher Fix.

Nachher: **Nutzer 2.360 Zeichen** — **−76 %**.

### 11. Szenenfolge / Geschichte

System 5.864 bzw. 5.352. Die Geschichte stand im Nutzertext zweimal
(143 Zeichen) — mit dem Fix in `szene.py` mitbehoben, weil derselbe Baustein
greift. **mittel**, gefixt.

### 12. Szene (`szene.systemanweisung(form)` + `baue_nutzertext`)

Gemessen vorher: **System 31.530 (Dialog), Nutzer 10.618 Zeichen.**

| Nr | Befund | Schwere | Fix |
|----|--------|---------|-----|
| **S1** | Die Geschichte stand **zweimal** im Nutzertext: als „Bogen und Ende" in `_format_rahmen_text` und nochmal als „Geschichte:" in `_thema_text`. | mittel | Aus `_thema_text` entfernt. |
| **S2** | Dieselbe Interview-Zusammenfassung **11×** im Kernpaket-Rückfall — derselbe Fehler wie G1, zweite Codestelle. | **gravierend** | Dedupe. |
| **S3** | Blockreihenfolge: „Aufgabe dieser Szene" stand **hinter** Figuren, Continuity und Verworfenem, also nach ~8.000 Zeichen Material — hinter dem, was sie rahmen soll. | **gravierend** | Neue Reihenfolge: Rahmen/Bogen → **Aufgabe** → Thema → Kernpaket → Figuren → Continuity → Verworfen → Angaben → Auftrag. |
| **S4** | **Leeres Versprechen:** der Kopf „So spricht jede Figur (aus ihrem Interview, wörtlich — kopiere diese Sprechweise)" erschien schon, wenn eine Figur ein *Sprachprofil* hatte — auch wenn **kein einziges Zitat** darunter stand. Ein Prompt, der etwas ankündigt und nicht liefert, lässt das Modell das Fehlende ergänzen: es erfindet Zitate. | **gravierend** | `mit_zitat` statt `mit_stimme`: der wörtlich-Kopf nur bei echten Zitaten, sonst der ehrliche `FIGUREN_KOPF_OHNE_STIMME`. |
| S5 | Einleitung von `szene.md` beschrieb eine Blockreihenfolge, die es nach dem Umbau nicht mehr gab. | leicht | Nachgezogen. |
| S6 | `## Ausgabeform` in `szene.md` wiederholte wortgleich `## Grundform der Ausgabe` zwei Seiten darüber; der Formblock geht ohnehin vor. Dazu ein Absatz Herkunftserklärung der Regeln (Prosa über die Regeln, keine Regel). | mittel | Gestrichen — **keine Regel entfernt**. |

Nachher: **System 31.183 (Dialog) / 24.335–25.495 (übrige Formen), Nutzer
3.805 Zeichen** — **−64 % Nutzertext**.

Der Dialog-System-Prompt bleibt über dem 15-k-Ziel: er ist die Summe aus
`szene.md` (14,9 k) + `formen/dialog.md` (8,4 k) + `theater-tells.md` (7,8 k).
Das sind **Regeln**, und der Auftrag sagt ausdrücklich „ohne Regelverlust —
nur Dubletten/Erklärprosa streichen". Weiter zu kürzen hieße, Regeln zu
löschen. Der Test hält 32.000 (Dialog) bzw. 26.000 (übrige) als Deckel fest,
damit es nicht wieder wächst.

---

## Abgrenzung: was dem Interaktions-Agenten gehört

Analysiert und dokumentiert, **hier bewusst nicht angefasst**:

* **Reihenfolge des Fensters** — der Verlauf stand rückwärts (neueste zuerst).
* **Fenstergrenze** — `_FENSTER_POOL = 1000` ohne eigenes Budget.
* **Systemzeilen-Filter** — „Bin wieder da"-Zeilen doppelt im Verlauf.

Die harte Zeichengrenze aus G4 begrenzt das Fenster **indirekt** mit (sie
schneidet es von vorn ab), ersetzt aber keine der drei Maßnahmen. Beide
Änderungen vertragen sich: die Kürzung arbeitet auf der Liste, die
`_baue_fenster_eintraege` liefert, egal in welcher Reihenfolge sie kommt.

## Datenschutz der abgelegten Dumps

Die Test-DB enthält Kopien echter Gruppen. Vor dem Ablegen ersetzt
`scripts/erzeuge_prompts.py` deshalb **drei** Arten von Inhalt durch eine
Längenangabe: Volltranskripte (`[Transkript N, 2413 Zeichen]`), die wörtlichen
Belegzitate ab 25 Zeichen (`[Zitat N, ...]`) und die
Verdichtungs-Zusammenfassungen (`[Zusammenfassung N, ...]`). Die letzten beiden
kamen beim zweiten Durchgang dazu: der erste Lauf hatte nur den markierten
Transkriptblock erwischt, während Verdichter-, Sprachprofil- und
Kernzitate-Prompt den Wortlaut **nackt** im Nutzertext tragen. Geprüft ist das
mit einem `grep` auf charakteristische Sätze; die Dumps sind sauber.

## Zahlen vorher / nachher

Zwei Spalten „nachher", weil zwei Arbeiten zusammenwirken: dieser Audit
(Dedupe + harte Grenze) und der Fensterumbau des Interaktions-Agenten
(chronologisches, begrenztes Fenster), der nach dem Merge dazukam.

| Pfad | Nutzer vorher | nur Audit | nach Merge | Δ gesamt |
|------|--------------:|----------:|-----------:|---|
| Gespräch | 49.872 | 24.000 | **7.688** | **−85 %** |
| Auftragszüge (je) | ~49.700 | ~24.100 | **~4.630** | **−91 %** |
| Feldvorschlag | 49.709 | 24.108 | **4.655** | **−91 %** |
| Szene (alle Formen) | 10.618 | 3.805 | **3.175** | **−70 %** |
| Kernzitate | 8.941 | 1.558 | **928** | **−90 %** |
| Schärfung | 9.743 | 2.360 | **1.730** | **−82 %** |
| Szenenfolge | 2.480 | 2.337 | 2.337 | −6 % |

Der Gesprächs-Prompt liegt damit bei **7.688 Zeichen ≈ 2.500 Token** — die
Größenordnung, die § 7.2 immer gemeint hat. Die harte Grenze von 24.000
Zeichen greift im Normalfall gar nicht mehr; sie ist die zweite Bremse
hinter dem begrenzten Fenster und muss trotzdem funktionieren, sonst fällt
sie beim nächsten Wachstum unbemerkt aus — genau der Weg, auf dem § 7.2
wirkungslos wurde. Ein Test erzwingt sie deshalb mit einer engen Grenze.

System-Prompts: Szene/Dialog 31.530 → 31.183, Szene/übrige 24.682–25.842 →
24.335–25.495. Kein Regelsatz entfernt.

## Offene gravierende Befunde

1. **E1 — `prompts/erkenner.md` nennt sieben Phasen mit alten Namen.** Braucht
   einen Korpuslauf mit FP = 0. Nicht gefixt.

## Werkzeuge

* `scripts/erzeuge_prompts.py` — erzeugt je Pfad einen echten Prompt gegen
  `IT_DB` und legt ihn hier ab. Transkript-Inhalte werden durch
  `[Transkript, N Zeichen]` ersetzt.
* `scripts/fuelle_pruef_db.py` — bringt eine **Kopie** der Test-DB auf einen
  realistischen Spätstand. Ohne ihn zeigt keiner der Befunde sich.
* `scripts/pruefe_prompt_dumps.py` — misst Dubletten, Längen und verbotene
  Reste über die abgelegten Dumps.
* `tests/test_prompt_audit.py` — 39 Tests, ein Block je Pfad, gegen eine
  Fixture-DB im Spätstand.

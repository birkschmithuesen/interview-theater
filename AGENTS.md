# AGENTS.md

Technische Referenz für Agenten und Entwicklerinnen, die an diesem Code
arbeiten. Für die Perspektive der Theatergruppe siehe [README.md](README.md).

Primärquelle für Entwurfsentscheidungen ist `SPEC-kontext-architektur.md` —
dieses Dokument verdichtet daraus, was für die Arbeit am Code am wichtigsten
ist, und ergänzt es um das, was sich erst beim Betrieb gegen die echten
Dienste gezeigt hat. Bei Widerspruch zwischen SPEC und Code gilt der Code;
Abschnitt „Wo SPEC und Code auseinanderlaufen" unten hält die bekannten
Fälle fest.

## Aufbau

Ein Python-Prozess je Gruppe (gleicher Code, eigener Bot-Token,
eigene `chat_id`), alle Prozesse teilen sich eine SQLite-Datei (WAL-Modus,
`busy_timeout`). Der Zustand liegt vollständig in der Datenbank — ein
Neustart verliert nichts, siehe § 9 der SPEC.

Module unter `interview_theater/`:

| Modul | Zuständigkeit |
|---|---|
| `bot.py` | Startroutine, Long-Poll-Schleife, Begrüßung, Warmlaufen, Prozessaufsicht |
| `ablauf.py` | Gesprächszug: Sperre je `chat_id` fürs Sammeln, Kontextaufbau anstoßen, Antwort verschicken |
| `aufnahme.py` | Aufnahme-Pipeline: Download, Transkription, Verdichtung, Nachhol-Arbeiter, Interviewfluss (kurz/teil/lang) |
| `befehle.py` | Die neun Slash-Befehle, laufen vor jedem Kontextaufbau und vor jedem Gespraechsaufruf |
| `erkenner.py` | Absichtserkenner: erkennt Änderungsabsichten im Gesprächsverlauf, wendet sie an, baut die Sammelmeldung |
| `journal.py` | Journal-Extraktor: erkennt `vorgeschlagen`-Einträge im aus dem Fenster verdrängten Gesprächsabschnitt |
| `kontext.py` | Baut den Gesprächs-Prompt datengetrieben zusammen, inklusive zweistufiger Kürzung |
| `phasen.py` | Die sieben Arbeitsphasen: Liste, tolerantes Mapping, `moegliche_naechste()` aus der Materiallage (reine Leseabfrage, kein Modellaufruf) |
| `llm.py` | Sprachmodell-Client (chat/completions), robustes JSON-Auslesen, Retry bei 5xx/Timeout |
| `stt.py` | Whisper-Anbindung, zweistufig und asynchron |
| `szene.py` | Szenentexte: eigener Prompt (Struktur statt Transkript, ein Regelblock je Form), eigener Thread, als einziger Aufruf mit Reasoning AN, Sperre vor dem Aufruf gegen fehlende Pflichtfelder |
| `sprachprofil.py` | Sprachprofil je Figur: ein gemma-Aufruf (Reasoning aus, eigener Thread) aus dem zugeordneten Interview, Zitate geprüft wie beim Verdichter |
| `telegram.py` | Dünner HTTP-Wrapper um die Telegram-Bot-API, inkl. Inline-Tastatur und `answerCallbackQuery` |
| `knoepfe.py` | Inline-Knöpfe an den drei Auswahl-Momenten (Kernthema, Aufnahme-Umschalter, Phasenwechsel): Angebot, Idempotenz-Sperre, Wirkung |
| `phasentexte.py` | Der Phasenrahmen im Chat (06.09.2026): die acht Einleitungen als Daten, `PARAMETER` je Phase, daraus Eintrittsnachricht („▶️ Phase N von 8 · Name" + Checkliste ✅/⬜), Abschlussnachricht („✅ … abgeschlossen" + alle gesetzten Parameter) und die Zeilen für `/stand`. Bot-Text an die Gruppe, kein Prompt — kein Modellaufruf, nur repo-Lesezugriffe |
| `verdichter.py` | Verdichtet ein Transkript zu Zusammenfassung und Kernthemen mit Belegzitaten — an der Frageliste der Gruppe entlang, wenn es eine gibt (N3) |
| `zitat.py` | Belegzitat-Verifikation: Teilstring-Vergleich nach Normalisierung |
| `repo.py` | Einzige SQL-Zugriffsschicht außer `db.py`, komplett `RLock`-serialisiert |
| `db.py` | Schema, Verbindungsaufbau samt PRAGMAs, Migration fehlender Spalten, Löschweg (`loesche_gruppe`) |
| `einstellungen.py` | Konfiguration ausschließlich über Umgebungsvariablen |
| `anweisungen.py` | Prompt-Texte mit Hot-Reload (mtime) + optionaler Regie-Zettel `betrieb/zusatz*.md` |
| `prompts/` | Die Prompt-Texte als eigene `.md`-Dateien (`system`, `erkenner`, `journal`, `verdichter`, `szene`, `sprachprofil` + `theater-tells`) |
| `prompts/formen/` | Ein Regelblock je Szenenform — genau fünf: `dialog`, `monolog`, `chor`, `lied`, `rap` (05.09.2026 abends). `szene.formdatei(form)` ordnet das freie Feld `szene.form` zu, Dialog ist der Rückfall. `dialog.md` trägt den am Herkules.exe-Textbuch gemessenen Regelblock (Sprechszene, Ausgangsmaterial, keine Choreografie); `lied.md`/`rap.md` das Songwriting- bzw. Rap-Handwerk. Eine Figurenanzahl gibt kein Regelblock vor — die kommt aus der Planung (Feld `figuren`) |
| `prompts/phasen/` | Je Arbeitsphase eine Datei `1.md` … `8.md`: worauf der Bot dort den Fokus legt, was er *nicht* tut, woran die Phase fertig ist. Wird zwischen Basis-Systemanweisung und Regie-Zettel gehängt |
| `web.py` | Weboberfläche: Routing, HTML und CSS für Dashboard und Gruppenseiten, `http.server`, nur Standardbibliothek |
| `web_daten.py` | Die Lesezugriffe dazu — read-only geöffnete Verbindung, reine Funktionen, `conn` rein, Dicts raus |

`scripts/loeschen.py` erfüllt die Löschzusage (löscht eine Gruppe vollständig,
Datenbank und Audioverzeichnis), `scripts/rauchtest.py` prüft echte
Betriebsannahmen gegen die echten Dienste, `scripts/pruefe_prompts.py` lässt
den Regressionskorpus unter `korpus/` gegen das echte Modell laufen (siehe
„Prompt geändert? → Korpus laufen lassen"), `scripts/simulation.py` fährt einen
kompletten simulierten Workshop durch alle Phasen und bewertet ihn (siehe
„Simulation", Bausteine unter `simulation/`), `scripts/backup-robocloud.sh`
sichert Betriebsdaten außerhalb des Repositories, `scripts/web_links.py` gibt
je Gruppe die URL ihrer Gruppenseite aus.

`web_daten.py` ist die einzige Ausnahme von „SQL nur in `repo.py` und
`db.py`". Grund: die Weboberfläche liest mit einer eigenen, read-only
geöffneten Verbindung (`file:…?mode=ro`). Sie durch `repo.py` zu führen hieße,
den modulweiten Schreib-Lock des Bots für Anfragen zu nehmen, die den Bot
nichts angehen — ein projiziertes Dashboard, das sich alle zehn Sekunden neu
lädt, würde damit Gesprächszüge ausbremsen.

## Bindende Entwurfsentscheidungen

- **Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte
  Entscheidungen.** Jede Nachricht wird roh gespeichert, unabhängig davon, ob
  sie einen Zug auslöst oder je in den Prompt wandert — etwas nicht
  aufzunehmen ist unumkehrbar, es nicht in den Prompt zu legen kostet nur
  Kilobyte (SPEC § 1).
- **Der Prompt ist datengetrieben.** `kontext.baue()` lässt jeden Block weg,
  solange die zugrundeliegenden Daten leer sind. Biegt die Gruppe ab, ändert
  sich die Materiallage und der Prompt folgt automatisch (SPEC § 6.1).
- **Inline-Knöpfe an den Auswahl-Momenten** (05.09.2026, `knoepfe.py`).
  Gemessen an diesem Tag: der Erkenner trifft eine Kernthema-Festlegung
  zuverlässig, wenn er das ganze Gespräch sieht (3/3) — live sieht er aber nur
  ein Fenster von 1–3 Nachrichten, und im Fenster mit der Zustimmung schrieb er
  `entschieden` (Journalnotiz) statt `kernthema_setzen` (Arbeitsstand). Die
  Festlegung landete nicht in der DB und nicht auf der Weboberfläche. Ein Knopf
  trägt die Auswahl selbst — nichts zu raten. Knöpfe gibt es deshalb **nur**
  dort, wo aus wenigen benannten Möglichkeiten gewählt wird: Kernthema-Vorschlag,
  Aufnahme-Umschalter, „Weiter zu Phase N", **Form je Szene** (Phase 6:
  Dialog · Monolog · Chor · Lied · Rap) und die **USA-Einwilligung**. Freitext (Begriffe,
  Fragen, Figurenbeschreibungen) bleibt bewusst Sprache — dort gibt es keine
  Liste. Die letzten drei kamen am selben Tag dazu, nachdem die nummerierten
  Auswahllisten in `phasen/5.md` und `6.md` dieselbe Schwäche zeigten („das
  erste" ist für den Erkenner nicht auflösbar) und die USA-Frage in der
  Simulation eine Sackgasse erzeugte: die Gruppe bejahte siebenmal, der
  Erkenner las es als Zustimmung zu den Figuren.
  Drei bindende Zusagen: (1) `callback_data` bleibt unter **64 Bytes** — ein
  Knopf trägt nur `k:<id>`, der Wert steht in der Tabelle `knopf`, nie der
  Volltext im Knopf (auch die Szenennummer nicht: sie steht als `"<nr>:<form>"`
  im `wert` der Knopfzeile); (2) **kein Modellaufruf** in einem Knopf-Handler,
  wie bei
  den Slash-Befehlen — was ein Modell braucht, geht an einen eigenen Thread;
  (3) **idempotent** über `repo.beanspruche_knopf` (bedingtes
  `UPDATE … WHERE benutzt_am IS NULL`, SQLite entscheidet) — der zweite Druck
  wird beantwortet, wirkt aber nicht. Die Weiche sitzt in `bot.schleife` vor
  `verarbeite_update`: ein Knopfdruck ist keine Nachricht und geht nie in
  `nachricht`, sonst läse ihn der Erkenner wie einen Gruppenbeitrag.
  Der Aufnahme-Umschalter kommt seit dem 05.09.2026 **auch am Erkenner-Pfad**:
  bestätigt `erkenner._melde_interviewmodus` einen erkannten Moduswechsel, geht
  das über `knoepfe.biete_aufnahme` mit demselben Wortlaut wie `/aufnahme`
  (`befehle._TEXT_INTERVIEW_AN`/`_AUS`) — sagt die Gruppe „ich will noch eine
  Aufnahme machen", steht der Knopf da, ohne dass jemand den Slash-Befehl
  kennen muss.
  **Nach jedem beendeten Interview steht eine Knopfleiste** (05.09.2026,
  `knoepfe.biete_nach_aufnahme`, aufgerufen an genau einer Stelle:
  `aufnahme._sende_nach_interview` — beide Wege, `/aufnahme` und der
  Erkenner-Pfad, laufen über `schliesse_ab` dorthin): „Auswerten", „Nächste
  Aufnahme" und, wenn `phasen.naechste_moegliche` es hergibt, „Weiter zu
  Phase N". „Auswerten" spielt eine schon vorhandene Verdichtung direkt aus der
  Datenbank aus (`aufnahme.zeige_verdichtung`, kein zweiter Modellaufruf) und
  verdichtet nur dann im Thread nach, wenn es noch keine gibt (Interview unter
  `MINDEST_WOERTER`). Anlass: Live-Fall Gruppe 2, 13:59 — „Interview 1 ist
  sehr kurz … /auswerten" als Text, zwei Rückfragen der Gruppe, keine
  Auswertung. **Slash-Befehle werden nicht mehr beworben**, nirgends: nicht in
  `_TEXT_*`-Konstanten, nicht in `prompts/system.md`, nicht in
  `prompts/phasen/*.md` (Test: `test_keine_phasenanweisung_bewirbt_einen_slash_befehl`).
  Sie bleiben funktionsfähig, `/hilfe` listet sie weiter — beworben wird der
  Knopf. **Reihenfolge beim Link:** die Begrüßung nennt die Gruppenseite nur,
  wenn `gruppe.web_token` existiert (entsteht in `repo.sichere_gruppe`). Weil
  `bot.erstkontakt` auch als Rückfallweg aus `ablauf.antworte` gerufen wird,
  geht der Link über `bot.stelle_link_sicher`, das die Gruppenzeile notfalls
  selbst anlegt. **Aufnahme-Angebote sind phasenabhängig** (05.09.2026,
  `knoepfe._aufnahme_anbieten`, `PHASE_INTERVIEWS = 3`): „Aufnahme starten" im
  Einstieg und „Nächste Aufnahme" nach einem Interview erscheinen nur in
  Phase 3 — in Begriffe (1) und Fragen (2) gibt es nichts aufzunehmen, die
  Begrüßung sagt dort, dass die Begriffe aus dem Plenum kommen
  (`bot._TEXT_ERSTKONTAKT_BEGRIFFE`). Läuft eine Aufnahme, steht „Aufnahme
  beenden" immer da. Ausdrückliches Aufnehmen (`/aufnahme`, erkannte Absicht)
  bleibt in jeder Phase möglich — eingeschränkt ist nur das Angebot.
  **Fallstrick:** `repo.setze_szene_usa` nimmt einen **bool**, nicht `"ja"`/
  `"nein"` — ein nicht-leerer String ist wahr, ein „nein" würde als Zustimmung
  zur Datenübermittlung enden. Test: `test_usa_knopf_nein_setzt_false_und_nicht_wahr`.
- **Die Phase setzt allein die Gruppe** (seit 05.09.2026, `phasen.py`, SPEC
  § 0 Leitsatz 3 Nachtrag): `phase_setzen` oder `/phase`, nie still erraten
  und seit dieser Korrektur auch nicht mehr vom Bot selbst. Der automatische
  Sprung (`ART_ERMOEGLICHT`, `sprung_nach`) ist **ersatzlos gestrichen**, aus
  einem Satz heraus: **Datenstand ist nicht Absicht** — eine fertige
  Verdichtung sagt nicht, ob noch drei Interviews kommen. Geblieben ist die
  **Frage**: erlaubt die Materiallage eine höhere Stufe, bekommt der
  Gesprächs-Prompt einen Hinweisblock (`kontext._baue_phasenhinweis`) mit der
  Anweisung, im Fluss nachzufragen — einmal je Stufe
  (`arbeitsstand.phase_angeboten`). Dieselbe Frage hängt an der
  Verdichtungs-Nachricht am Ende eines Interviews (`aufnahme._phasenfrage`);
  beide Stellen teilen sich den Merkposten über `phasen.offenes_angebot()` /
  `merke_angebot()`, deshalb liest die eine Funktion nur und die andere
  schreibt.
- **Die acht Phasen sind: 1 Begriffe · 2 Fragen · 3 Interviews ·
  4 Setting & Figuren · 5 Geschichte · 6 Schärfung · 7 Szenentexte ·
  8 Durchlauf** (Umbau 05.09.2026 nachts; davor: 7 Phasen mit „4 Kernthema &
  Figuren · 5 Rahmen · 6 Szenen · 7 Durchlauf"). Der Grund ist **nicht**
  Feingliederung, sondern eine umgedrehte Arbeitsrichtung.
- **Erst erfinden, dann schärfen** (Birk, 05.09.2026 23:30 — die tragende
  Entscheidung des Ablaufs). Bis dahin entstanden Figuren und Szenen **aus**
  den Interviews; das Ergebnis war handwerklich richtig und dramaturgisch
  tot, weil die Gruppe ihren eigenen kreativen Anteil nicht wiedererkannte —
  sie sah eine Nacherzählung ihres Materials. Jetzt:
  - In **4 (Setting & Figuren)** und **5 (Geschichte)** erfindet die Gruppe
    frei. Der Bot fragt **offen** („Welche Personen soll es geben? In welchem
    Setting spielt es?" / „Was soll passieren? Wie soll es enden?") mit nur
    zwei Knöpfen — „Eigene Idee" und „Schlag du vor" —, und seine Vorschläge
    speisen sich **ausschließlich aus `arbeitsstand.begriffe`, `fragen` und
    dem schon Festgelegten**. Kein Material: `kontext.baue` liefert dort
    weder Verdichtungen noch Transkripte noch das Kernpaket
    (`kontext.material_erlaubt`), und `szenenfolge.baue_nutzertext_geschichte`
    baut den Nutzertext ohne Material. Das ist im Code durchgesetzt, nicht im
    Prompt gebeten — ein Prompt, der Material sieht, referiert es.
  - In **6 (Schärfung)** kommt das Material dazu und legt sich **neben** das
    Erfundene, statt es zu ersetzen. Beim Eintritt läuft automatisch ein
    Schema-Aufruf (`schaerfung.mappe`, gemma, Thread — kein Modellaufruf im
    Knopf-Handler): er bekommt Setting, Figuren, Geschichte, die Szenen mit
    Nummer und **alle geprüften `verdichtung_thema`-Einträge nummeriert** und
    ordnet jeden passenden Eintrag einer Szene und/oder einer Figur zu. Zeigen
    kann er nur auf Nummern, Zitate werden mit `zitat.pruefe` gegen das
    Original verifiziert, was nicht passt bleibt weg. Ergebnis: Tabelle
    `schaerfung` (additiv, mit `runde`), daraus je Szene und je Figur eine
    Vorschlagsnachricht mit Grundleiste; „Gefällt uns, weiter" schreibt die
    Felder (`schaerfung.uebernimm_szene` / `uebernimm_figur`), „Noch eine
    Runde" startet einen neuen Lauf mit dem geschärften Stand.
  - **Die Figuren-Ebene 2 ist dorthin gewandert.** „Aus welchem Interview
    spricht sie?" und der Sprachduktus laufen erst ab Phase 6
    (`knoepfe.ebene2_erlaubt`); in Phase 4 ist die Liste nach Ebene 1 fixiert.
    In 4 danach zu fragen wäre genau die Rücklenkung aufs Material, die der
    Umbau vermeidet.
  - **Das Kernthema ist keine eigene Station mehr.** `arbeitsstand.geschichte`
    (Bogen + Ende) übernimmt seine Rolle im Kernpaket. Kernthema, Kernfrage
    und Kernzitate bleiben im Code funktional und getestet
    (rückwärtskompatibel für bestehende Gruppen), werden aber nicht mehr
    angeboten; `kernzitate.py` bleibt als Basis, `schaerfung.py` nutzt
    dieselbe Prüf- und Speicherlogik.
  - Voraussetzungen (`phasen.voraussetzungen`): **5** braucht `rahmen` **und**
    `figuren_fixiert_am`; **6 und 7** brauchen `geschichte` **und** ≥ 1 Szene
    — die Schärfung ist ein Angebot, keine Pflicht, deshalb sperrt sie 7
    nicht; **8** braucht einen geschriebenen Szenentext.
- **Der Szenen-Prompt bekommt die Schärfungen JE SZENE, nicht global**
  (`szene._kernpaket_text(conn, chat_id, ziel)`). Eine Szene sieht die
  Interviewstellen, die zu ihr und zu ihren Figuren gehören — und keine
  fremden. Ohne Schärfungen fällt der Code auf die alte, globale
  Kernzitat-Auswahl zurück: eine Gruppe, die den Umbau nicht mitgemacht hat,
  verliert nichts.
- **Die Form je Szene ist ein Vorschlag, keine Vorentscheidung** (Birk,
  06.09.2026 00:30: „Die Form Monolog habe ich niemals eingegeben und aktiv
  bestätigt. Die Form muss mit mehr Bedacht gewählt werden und vom User
  bestätigt werden."). Die vierte Spalte der Szenenzeile landet in
  `szene.form_vorschlag`, die fünfte (Begründung, Pflicht) in
  `form_vorschlag_grund`; **`szene.form` bleibt leer**, bis die Gruppe sie
  Szene für Szene per Knopf bestätigt. In der Szenenvorstellung kommt deshalb
  **zuerst** „Welche Form soll Szene N haben?" mit fünf Knöpfen — der
  Vorschlag zuerst und mit „(Vorschlag)" markiert, darüber seine Begründung —
  und **erst nach dem Druck** die Schreibfrage. `form` ist Pflichtfeld
  (`szene.PFLICHTFELDER`), ohne bestätigte Form läuft kein Szenenlauf.
  Vorschlagsregeln im Prompt: **Dialog ist der Normalfall**, höchstens eine
  Nicht-Dialog-Szene je drei, Szene 1 nie Monolog oder Lied.
- **Phase 4 heißt „Setting & Figuren"** — das frühere Feld `rahmen` ist das
  Setting (Ort, Zeit, Anlass) und behält seinen Spaltennamen; nach außen
  (Knopftexte, Notiert-Zeile, Weboberfläche) heißt es „Setting". `format` und
  `hauptkonflikt` bleiben als Spalten stehen und tragen keine Entscheidung
  mehr. Stichwörter: „Rahmen", „Setting", „Format", „Konflikt" und
  „Kernthema" zeigen alle auf 4, „Geschichte" auf 5 — `prompts/erkenner.md`
  wurde dafür **nicht** angefasst, die Zuordnung Wort→Nummer liegt in
  `phasen.STICHWOERTER`.
- **`geschichte_setzen` ist im Code, aber nicht im Erkenner-Prompt.** Der
  Regelweg zur Geschichte ist der Vorschlagsblock mit seinen Knöpfen
  (`knoepfe._speichere_geschichte`); die Erkenner-Art ist der zweite, freie
  Weg. `prompts/erkenner.md` blieb unverändert, weil in derselben Nacht kein
  Korpuslauf gegen das echte Modell möglich war — `tests/test_korpus.py`
  hält das als `OHNE_KORPUSFAELLE` fest. **Wer den Prompt erweitert, nimmt
  die Art dort heraus und legt zwei Korpusfälle an.**
- **Der Phasen-Prompt ist Fokus, kein Käfig** (05.09.2026). Jede
  `prompts/phasen/N.md` hat den Abschnitt „Was du nicht von dir aus
  anfängst" mit dem festen Schlusssatz „Bittet die Gruppe ausdrücklich darum,
  tust du es trotzdem …"; `tests/test_anweisungen.py` prüft ihn in jeder
  Datei. Der Live-Fall dahinter: eine Gruppe in Phase 2 bat um Kernthema und
  Figuren, `2.md` sagte „kein Kernthema, keine Figuren", und getragen hat die
  Antwort nur, weil der Basis-Prompt sie trug.
- **Phasennummern werden migriert, nicht umgedeutet** (`db.SCHEMA_VERSION`,
  `db.PHASEN_UMNUMMERIERUNG`, `db.PHASEN_UMNUMMERIERUNG_2`). Zwei Schritte
  hintereinander, eine alte Datenbank läuft durch beide: acht → sieben
  (04.09.: Kernthema und Figuren wurden eine Phase) und sieben → acht
  (05.09. nachts: 4 und 5 bleiben, 6 → 7, 7 → 8; die neue 6 bekommt niemand
  zugewiesen, sie ist ein Angebot und keine übersprungene Station). Der Merkposten ist SQLites eingebautes
  `PRAGMA user_version` — keine eigene Tabelle, keine Zeile, kein Schema. Das
  Journal bleibt dabei unangetastet: dort steht „Phase 5 · Figuren", weil das
  am 04.09. wahr war, und ein Journal wird nur angehängt.
- **Ein Interview ist eine Einheit** (seit 05.09.2026, SPEC § 10.6). Das ist
  die Korrektur aus dem Probelauf: ein Interview aus fünf Sprachnachrichten
  wurde zu fünf Aufnahmen, fünf Verdichtungen (zwei leer) und fünfmal „Ich
  höre durch", gefolgt von nichts. Der Fluss jetzt, in einem Satz: **Modus an
  → ein Interview (Kopf), jede Sprachnachricht ein Teil mit sofortigem
  Transkript-Echo im Chat, „fertig" → zusammenfügen, einmal verdichten, die
  Verdichtung in den Chat.** Daran hängen vier Dinge, die nicht verhandelbar
  sind: **im Live-Pfad nur Whisper, der Erkenner und die eine Verdichtung**
  (der Erkenner-Lauf über jedes Teil-Transkript ist seit N1 dabei — gemma,
  unter einer Sekunde, und er ist der einzige Weg, ein „fertig" zu hören, das
  in die Aufnahme statt in den Chat gesagt wurde; kein Gesprächs- oder
  Verdichteraufruf je Teil); **keine Empfangsbestätigung** mehr (das
  Transkript ist sie); das **Echo steht in keinem Fenster**
  (`typ='transkript'`, sonst liest der Erkenner Interviewinhalt als
  Gruppenabsicht); und **ein offener Teil hält den Abschluss auf**, statt
  ohne ihn zu verdichten.
- **Aus einer Aufnahme darf der Erkenner fast nichts schreiben** (seit
  05.09.2026, N1). Der Lauf über ein Teil-Transkript
  (`erkenner.erkenne_in_aufnahme`) wird **im Code** auf
  `erkenner.ARTEN_IN_AUFNAHME` eingeschränkt, nicht nur im Prompt gebeten:
  was eine interviewte Person erzählt, ist Material und nie eine Absicht der
  Gruppe (Korpusfälle n12/n26, a03/a04). Er rückt außerdem kein Wasserzeichen
  vor — er hängt an einer Aufnahme, nicht am Gesprächsverlauf. Die eine
  Ausnahme ist `an_den_bot` (N4): eine Sprachnachricht im Interviewmodus muss
  nicht Material sein, die Gruppe fragt darin auch den Bot direkt an ("zeig
  mir die Verdichtungen"). Der Erkenner erkennt das, `aufnahme.py` zweigt die
  Nachricht daraufhin aus dem Interview ab (`repo.loese_aus_interview`) und
  der Bot antwortet — als Text, unabhängig davon, ob die Frage gesprochen war.
- **Korrekturen wirken, nicht nur im Journal** (05.09.2026, N5,
  `erkenner.transkript_korrigieren`). Ein Hörfehler von Whisper wird überall
  ersetzt, wo er steht — im Transkript selbst, in Zusammenfassung und
  Kernthemen der Verdichtung, in Zitaten von Figuren —, ohne neu zu
  verdichten: die Ergebnisse der Gruppe bleiben stehen, nur der falsche
  Wortlaut wird getauscht. Der Gesprächs-Bot behauptet dabei keine
  Schreibvorgänge mehr, die er nicht selbst ausführt. `entfernen` darf seit
  derselben Änderung auch ein ganzes Interview treffen.
- **Sprachprofil je Figur** (05.09.2026, T3, `sprachprofil.py`): drei Felder
  (`sprachprofil` — Satzlänge, Füllwörter, Abbrüche, Dialekt, Tempo, 3–5
  Zeilen; `zitate` — 3–5 wörtliche Sätze; `quelle_aufnahme_id`). Der Weg
  dahin ist ein Gespräch, kein Namensvergleich: hat eine Figur noch keine
  Quelle, bekommt der Gesprächs-Prompt einen Hinweisblock
  (`kontext._baue_figurenhinweis`), der Bot schlägt im Fluss eine Zuordnung
  vor — mit Belegzitat —, die Gruppe nickt oder ändert
  (`figur_quelle_setzen`), und erst danach läuft EIN Sprachprofil-Aufruf
  (gemma, Reasoning aus, Schema, eigener Thread). Zitate werden geprüft wie
  beim Verdichter (`zitat.pruefe`); ohne ein einziges belegtes Zitat wird gar
  nichts gespeichert — ein erfundenes Zitat würde als Few-Shot in jeden
  weiteren Szenenlauf eingehen.
- **Eine Szene wird geplant, bevor sie geschrieben wird** (05.09.2026, T2):
  neun Felder (`form`, `ort`, `zeit`, `anlass`, `figuren`, `was_passiert`,
  `was_anders`, `kernsaetze`, `ton`), additiv über mehrere Nachrichten
  gesetzt (`repo.setze_szenenfeld` rührt nie mehr als ein Feld an). Erkenner-
  art `szene_planen`, kompakter Text mit `|`-getrennten Feldern. Sechs Formen
  (`prompts/formen/`: Dialog, Lied, Rap, Monolog, Chor, stumm), Dialog ist
  der Rückfall. **Sperre vor dem Aufruf** (T5, `szene.sperrtext`): fehlt ein
  Pflichtfeld (`form`, `ort`, `figuren`, `was_passiert`) oder hat eine Figur
  dieser Szene kein Sprachprofil, gibt es keinen Modellaufruf, sondern eine
  Nachricht in einem Satz, was fehlt — gemessen gegen den Probelauf, in dem
  ein Modell ohne Ort und Besetzung eine Küche statt eines Polizeikessels
  erfand. **Keine Rückfragenkette vor einer Szene** (T7): sagt die Gruppe
  „schreib sie" nach einer Planung, ist das ein Auftrag mit Szenenbezug aus
  dem Verlauf, kein einzelnes Wort — die Sperre meldet in einer Nachricht,
  was fehlt, statt viermal hintereinander nachzufragen.
- **Kein Thema ohne wörtliches Belegzitat, keine Verdichtung ohne Material**
  (seit 05.09.2026, N2). Ein Kernthema, dessen Zitat die Prüfung aus
  `zitat.py` nicht besteht, wird **nicht gespeichert** — nicht mehr mit
  `zitat_geprueft = 0` behalten. Und unter `aufnahme.MINDEST_WOERTER` (40)
  Wörtern im ganzen Interview wird der Verdichter **gar nicht erst gerufen**;
  die Gruppe bekommt eine Zeile mit Dauer und Wortzahl und kann mit
  `/auswerten` widersprechen. Beides kommt aus einem gemessenen Fall: aus
  einer vier Sekunden langen Sprachnachricht entstand ein vollständig
  erfundenes Interview mit drei unbelegten Themen.
- **Verdichtungen stehen ab der ersten fertigen im Gesprächs-Prompt (Block 2)
  und auf der Gruppenseite** — Zusammenfassung und Kernthemen mit Belegzitat,
  im Web nur mit `zitat_geprueft = 1`. Datengetrieben, also unabhängig von der
  Phase (`tests/test_kontext.py`, `tests/test_web.py`).
- **Weiches Löschen statt Löschen** (NACHTRAG N3): `entfernt_am` in `figur`,
  `szene`, `journal`; Arbeitsstandfelder werden auf NULL gesetzt. Jeder Leser
  in `repo.py` und `web_daten.py` filtert `entfernt_am IS NULL`. **Material
  (Aufnahmen, Transkripte, Verdichtungen) hat keinen Entfernungspfad** — dafür
  gibt es allein `scripts/loeschen.py`.
- **Verdichtungen werden nie nachträglich geändert.** Es gibt bewusst kein
  `aktualisiere_verdichtung()` in `repo.py`. Was einmal aus einem Interview
  verdichtet wurde, bleibt stehen; neue Erkenntnis gehört in den
  Arbeitsstand, nicht in eine Korrektur der Verdichtung.
- **Das Journal wird nur angehängt.** Kein `aktualisiere_journal()`, kein
  `DELETE`. Auch das weiche Löschen ändert keinen Text: der zurückgenommene
  Eintrag bekommt `entfernt_am`, ein neuer („Zurückgenommen: …") hält den Weg
  sichtbar. Verworfenes, Entwürfe in der Schwebe und das Warum hinter
  Entscheidungen stehen sonst nirgends außerhalb des kurzen Fensters (SPEC
  § 2).
- **Jede Tabelle außer `bot_zustand` hat `chat_id`.** Kein Ableiten über
  Umwege. Das macht die Löschzusage zu einem `DELETE … WHERE chat_id = ?` je
  Tabelle (`db.TABELLEN_MIT_CHAT_ID`, `db.loesche_gruppe`) — die einzige
  Ausnahme ist die getUpdates-Position pro Bot-Token, die keiner Gruppe
  zugeordnet ist.
- **Eine Antwort, die nur die Frage zurückgibt, ist keine** (seit 05.09.2026,
  `ablauf.ist_echo`/`_ohne_echo`). Gemessener Fall: der Bot schickte eine
  Nachricht der Gruppe wortgleich zurück, mit „Birk:" davor — formal eine
  Antwort, für die Gruppe ein kaputter Bot. Ein Echo löst **genau einen**
  zweiten Aufruf aus, mit einer angehängten Zeile im Nutzertext; ist auch der
  zweite eines, geht er trotzdem raus (`echo_wiederholt`). Keine Schleife: die
  Gruppe wartet, und ein Modell, das zweimal zitiert, zitiert auch beim
  dritten Mal.
- **Die Gruppe erfährt von einem Fehler nur, wenn sie ihn beheben kann oder
  gerade darauf wartet.** Ein gescheiterter Absichtserkenner- oder
  Journal-Lauf ist für die Gruppe unsichtbar (Wasserzeichen bleibt stehen,
  `vorfall` fürs Dashboard); ein gescheiterter Gesprächszug oder eine
  gescheiterte Transkription bekommt eine kurze, ehrliche Zeile, weil die
  Gruppe gerade darauf wartet oder selbst reagieren muss (SPEC § 11.1/§ 11.2).

- **Haltung: speichern beim ersten Mal, proaktiv zur nächsten Phase, keine
  Wiederholung** (06.09.2026, nach dem gemessenen Testabend: Median 20
  Nachrichten je Festlegung, 64 % Fragen, 23 Auswahlknöpfe null Mal gedrückt).
  Nennt die Gruppe einen Wert, wird er sofort abgelegt und in einer Zeile
  bestätigt — keine Rückfrage davor, keine Zusammenfassung danach. Steht etwas
  im Arbeitsstand, fragt der Bot nie erneut danach. Sobald die Voraussetzungen
  einer höheren Phase gespeichert sind, schickt er **einmal** eine eigene kurze
  Nachricht „<Was steht>. Weiter zu <Phase>?" (`knoepfe.biete_phase_proaktiv`,
  Merkposten `arbeitsstand.phase_angeboten`), nicht als vierten Knopf unter
  einem langen Text. Antworten mit über 60 % Deckung zur vorigen Bot-Nachricht
  werden ersatzlos verworfen (`ablauf.ist_wiederholung`, Vorfall
  `wiederholung_verworfen`); löst eine Nachricht einen Auftrag aus, schweigt
  der Gesprächs-Bot ganz (`ablauf.ist_auftrag`). Die Grundleiste speichert nie
  über ein gesetztes Feld hinweg, solange keine Änderung offen ist
  (`knoepfe._ist_bestaetigung`, `_feld_ist_frei`). Das Kontextfenster ist kurz
  und chronologisch: höchstens `kontext.FENSTER_NACHRICHTEN` (20) oder
  `FENSTER_MINUTEN` (30), sortiert nach `gesendet_am` — **nicht** nach
  `message_id`, denn übernommene Historien tragen negative, absteigend
  vergebene ids. Belege: `docs/analyse-interaktion-testgruppe-2026-09-05.md`.

- **Die Fragen sind eine Auswahl, und danach kommt der Leitfaden** (06.09.2026,
  Birk). Phase 2 schlägt zehn Fragen als `VORSCHLAG FRAGENAUSWAHL:` vor, aus
  denen die Gruppe per Mehrfachauswahl genau drei antippt — ein Knopf je Frage,
  Toggle über `telegram.aktualisiere_knoepfe`, Zustand in
  `arbeitsstand.fragen_gewaehlt` und nie in der Tastatur, „Diese 3 nehmen" wirkt
  nur bei genau drei. Auf das Speichern folgt automatisch eine
  Sensibilitätsprüfung (Einleitungen je heikler Frage, `VORSCHLAG
  EINLEITUNGEN:`) und danach Eröffnung und Abschluss (`VORSCHLAG EROEFFNUNG:`),
  beide als Ping-Pong über die Grundleiste und beide als Auftragszug im eigenen
  Thread, nicht im Knopf-Handler. Daraus baut `leitfaden.baue()` deterministisch
  den Gesprächsleitfaden — Eröffnung, Fragen mit ihren Einleitungen, Abschluss —,
  den der Bot beim Schritt in die Interviews und beim Interviewstart genau
  einmal schickt und danach nur noch auf Knopf, `/leitfaden` (versteckt) oder
  auf der Gruppenseite zeigt. Deshalb hängt `phasen.voraussetzungen[3]` seitdem
  an Fragen **und** `interview_eroeffnung`: ohne Eröffnungstext geht keine
  Sechzehnjährige auf eine fremde Person zu, während leere Einleitungen ein
  Ergebnis der Prüfung sind und kein fehlender Wert.

- **„Neu schreiben" heißt neu, und der Bot zeigt, dass er arbeitet**
  (06.09.2026). Der Knopf „Neu schreiben" gibt die alte Fassung NICHT als
  Vorlage mit (`szene.NEU_MARKER` im Auftrag → `NEU_HINWEIS` statt Volltext);
  „Passt, aber anders" überarbeitet den bestehenden Text mit der Regie-Notiz.
  Der Szenen-Prompt trägt vor den Angaben die **Aufgabe der Szene** an ihrer
  Position (`szene._aufgabe_text`: erste = Exposition wer/zueinander/warum
  hier/worum; Mitte = verschärfen/wenden; letzte = einlösen) und ganz oben
  Rahmen/Geschichte als bindende Vorgabe. Solange Opus schreibt, laufen
  Tippanzeige und eine wechselnde Emoji-Zeile (`szene._arbeitet_sichtbar`),
  die am Ende wieder gelöscht wird.

- **Prompts werden nicht gelesen, sondern erzeugt und gemessen** (06.09.2026,
  Prompt-Audit `docs/prompt-audit/2026-09-06/`, `scripts/erzeuge_prompts.py`).
  Jeder Prompt-Pfad hat einen Test gegen eine Fixture-DB im *Spätstand*
  (`tests/test_prompt_audit.py`) — gegen eine frische Datenbank zeigt sich
  keiner der Befunde (52 k Zeichen Nutzertext, dieselbe Zusammenfassung 11×,
  Rahmen 3×), und genau deshalb hatten sie überlebt. Drei Regeln: kein Satz über
  80 Zeichen zweimal, Nutzertext unter der harten Grenze
  (`kontext.ZEICHEN_GRENZE_VORGABE` = 24 000, Env `IT_PROMPT_ZEICHEN`, Kürzungsreihenfolge
  Verlauf → Journal → Verdichtungen, Vorfall `kontext_gekuerzt`), keine
  veralteten Reste. Ein Fakt hat genau eine Stelle im Prompt; steht er an zweien,
  ist eine davon zu löschen, nicht beide zu behalten. Ein Prompt-Kopf, der etwas
  ankündigt, muss es auch liefern — sonst ergänzt das Modell das Fehlende selbst.

- **Jede Phase hat im Chat denselben Rahmen** (06.09.2026, Birk): Eintritt
  über EINEN Weg (`knoepfe.eintritt_in_phase` — Knopf, `/phase`, Erkenner,
  proaktive Meldung) mit deterministischer Nachricht aus `phasentexte`
  (Einleitung 2–4 Sätze, Checkliste der Parameter, Einstiegsknöpfe darunter);
  Abschluss über `biete_phase_proaktiv` mit allen gesetzten Parametern und
  „Weiter zu <Phase>" · „Noch etwas aendern", einmal (Merkposten
  `phase_angeboten`). `/stand` nutzt dieselben `standzeilen`. Jinja wie im
  Fundusbot wurde geprüft (`docs/prompt-audit/2026-09-06/jinja-inspiration.md`):
  nicht installiert, nicht jetzt — `kontext.baue` braucht Blöcke als Objekte
  (Kürzung, Protokoll); Kandidaten für später sind die unkritischen Pfade.

- **Das Eingabe-Budget des Szenenlaufs ist gemessen, nicht gesetzt**
  (06.09.2026). Deutscher Prosatext tokenisiert schlechter als die Faustregel:
  gegen `count_tokens` gemessen ergab der echte Szenen-Prompt 38 610 Zeichen =
  20 222 Token, also **1,9 Zeichen je Token** — `kontext._ZEICHEN_JE_TOKEN = 3`
  hätte um 36 % zu niedrig geschätzt, deshalb `szene.SZENE_ZEICHEN_JE_TOKEN`.
  Die beiden Anbieterpfade sind nicht vergleichbar: bei Claude (`max_tokens =
  32 000`, kein extended thinking) müssen Eingabe **plus** `max_tokens` unter
  das Kontextfenster passen → 126 000 Token; bei Infomaniak zählen beide gegen
  `max_total_tokens = 249 984`, und `llm.prosa` läuft mit 200 000 → 37 488
  Token. Env `IT_SZENE_TOKEN_MAX` überschreibt. Jede Szene liefert per
  Pflichtzeile `Zusammenfassung:` + `Anders gemacht:` (→ `szene.zusammenfassung`,
  Journal-Eintrag bei Abweichung); passt der Volltext aller Vorszenen nicht,
  greift die Kürzungsleiter älteste Szene → Zusammenfassung, dann Chat-Block auf
  10, dann Kernpaket-Begründungen, dann 3 Zitate/Figur — nie Rahmen, Aufgabe,
  Angaben, Auftrag; alles im Continuity-Kopf benannt, Vorfall
  `szene_prompt_gekuerzt`. Der Szenenlauf bekommt den Chat seit der letzten
  Fassung dieser Szene (mind. 20 Nachrichten) als Block „Was die Gruppe zuletzt
  dazu gesagt hat" — Chat schlägt gespeicherte Angaben. `stop_reason ≠ end_turn`
  ist ein Fehler (`szene_abgeschnitten`), kein Text; `_pruefe_budget` warnt ab
  90 % der tatsächlichen Token.

## Die Fallen

Jede hier gemessen, keine geraten. Wer das nicht liest, verliert denselben
Nachmittag noch einmal.

1. **`IT_LLM_URL` braucht die volle URL inklusive `/chat/completions`.**
   Der Code hängt nichts an. Mit `.../openai/v1` allein antwortet der Server
   **HTTP 404**.

2. **Whisper liegt unter `/1/ai/{produkt}/...`, nicht unter
   `/2/.../openai/v1/`** — dort ebenfalls HTTP 404. Der Aufruf ist außerdem
   **zweistufig**: Absenden liefert eine `batch_id`
   (`POST .../openai/audio/transcriptions`), das Ergebnis wird gepollt
   (`GET .../results/{batch_id}`). Das Feld `data` in der Ergebnisantwort ist
   ein **JSON-String**, kein Objekt, und muss ein zweites Mal geparst werden
   (siehe `interview_theater/stt.py`).

3. **Der MIME-Typ beim Upload muss zur Datei passen.** Ein fest verdrahtetes
   `audio/ogg` für eine WAV-Datei wird vom Anbieter mit einer `batch_id`
   quittiert — kein HTTP-Fehler, keine Ablehnung — der Auftrag bleibt danach
   aber dauerhaft auf `pending` und läuft ins Zeitbudget: 89,7 s statt 2,0 s.
   Im Betrieb ist das nur als „hängt" sichtbar. `stt.mime_typ()` leitet den
   Typ deshalb aus der Dateiendung ab, nicht aus einer festen Konstante —
   Telegram liefert Audio als `voice` (ogg/opus), `audio` (m4a, mp3) und als
   Dokument.

4. **`reasoning_effort` ist binär, und das Feld wegzulassen schaltet
   Reasoning AN.** `"none"` schaltet aus, jeder andere Wert — auch das Fehlen
   des Feldes — schaltet an. Es gibt keine stille Voreinstellung „aus"
   (`interview_theater/llm.py`, `LLM._anfrage`: das Feld wird deshalb **immer**
   gesendet). Reasoning ist überall aus; bei Klassifikation mit Ausnahmen
   (dem Absichtserkenner) senkt es die Trefferquote messbar. Eng verwandte
   Falle: Reasoning verbraucht das Ausgabebudget, bevor der eigentliche
   Inhalt beginnt — bei zu knappem `max_tokens` kommt HTTP 200 mit
   `content: null` und `finish_reason: "length"` zurück, ein stiller
   Durchfall statt eines Fehlers. Deshalb `MAX_TOKENS = 9000` und
   `finish_reason == "length"` wird explizit als Budget-, nicht als
   Formatfehler behandelt.

   **Die eine Ausnahme: `szene.py`.** Dort ist Reasoning AN, und zwar nach
   der Matrix in `reasoning-stufen-entscheidungshilfe.md` § 4.2, nicht weil
   Szenentext „wichtiger" wäre: entscheidend ist, ob ein Mensch wartet — und
   beim Szenenlauf wartet niemand, er hängt in einem eigenen Thread. Daran
   hängen zwei Werte, die dort eigens gesetzt sind und nicht aus `llm.py`
   kommen: `max_tokens = 200.000` und ein Zeitbudget von 600 s (der
   `httpx.Client` aus `bot.main` hat 30 s, das reicht für einen Reasoning-Lauf
   nicht). Wer einen weiteren Aufruf mit Reasoning baut, braucht beides
   wieder.

   **`max_tokens` ist bei Infomaniak eine Obergrenze, kein Zielwert — und sie
   zählt gegen Eingabe *und* Ausgabe zusammen.** Mit dem erweiterten
   Szenen-Prompt (dreizehn Dramaturgieregeln, Formen-Regelblock, Tells) lief
   ein Lauf bei 12.000 Token nur im Denken leer (`finish_reason: "length"`,
   kein Inhalt), der erste erfolgreiche brauchte 19.410 Antwort-Token.
   Zugleich rechnet Infomaniak `max_tokens + Eingabe` gegen
   `max_total_tokens = 249.984` — bei 250.000 kam HTTP 400 zurück, gemessen
   am 04.09.2026 abends. 200.000 lässt rund 50.000 Token Platz für die
   Eingabe und liegt trotzdem klar über dem gemessenen Antwortbudget: ein
   Deckel knapp über dem letzten Lauf programmiert nur den nächsten Abbruch
   vor.

5. **Modellwahl je Aufruf.** Kimi fürs Gespräch und den Verdichter,
   `google/gemma-4-31B-it` für Absichtserkennung und Journal (gemessen: 0
   Falsch-Positive bei 25 Negativfällen, 30/30 Treffer; Kimi verpasste
   `interview_beenden` 3 von 3 Mal). `gemma` hat rund 28 s Kaltstart, danach
   unter 1 s — deshalb läuft `bot.warmlaufen()` beim Prozessstart in einem
   eigenen Thread ins Leere. Nemotron-Nano ist bei der Absichtserkennung mit
   6/27 Falsch-Positiven durchgefallen und darf nirgends als Vorgabewert
   auftauchen.

6. **Eine SQLite-Verbindung über mehrere Threads ist nicht
   nebenläufigkeitssicher — auch nicht mit `check_same_thread=False`.** Das
   hebt nur die Thread-Zugehörigkeitsprüfung auf, synchronisiert aber nicht
   die interne Transaktionsbuchhaltung; beobachtet als sporadisches
   `sqlite3.OperationalError: cannot commit - no transaction is active`
   unter mehreren gleichzeitigen Schreibern. Deshalb ist jede Funktion in
   `repo.py` über einen modulweiten `threading.RLock` serialisiert
   (`repo._LOCK`, Dekorator `_gesperrt`). **`RLock`, nicht `Lock`:**
   `lege_aufnahme_an` ruft innerhalb desselben Threads `zaehle_aufnahmen`
   auf — mit einem einfachen `Lock` würde sich der Thread beim zweiten
   `acquire` selbst blockieren.

7. **Betrieb:** nie denselben Bot-Namen zweimal gleichzeitig starten
   (beide würden dieselbe `bot_zustand`-Zeile und dasselbe
   getUpdates-Offset verwenden), nie zwei Bots in dieselbe Telegram-Gruppe
   einladen (beide würden dort antworten — sofort sichtbar, aber
   vermeidbar).

8. **Infomaniak drosselt Parallelität mit 429/5xx, nicht mit einer sauberen
   Warteschlange.** Betrifft im Betrieb kaum den Bot selbst (Aufrufe je
   Gruppe laufen ohnehin nacheinander), aber jeden eigenen Skriptlauf, der
   mehrere Anfragen gleichzeitig schickt — `scripts/pruefe_prompts.py` ruft
   deshalb sequenziell auf, nicht parallel. Wer ein Werkzeug baut, das mehrere
   Aufrufe gleichzeitig absetzt, bekommt sporadische 429/5xx statt eines
   verlässlichen Fehlers und sollte seriell bleiben oder selbst drosseln.

## Wo SPEC und Code auseinanderlaufen

`SPEC-kontext-architektur.md` § 8 beschreibt ursprünglich vierzehn Befehle
und einen Modus B (`/gruendlich`, freier Prosatext mit
`reasoning_effort: "medium"`, via `LLM.prosa()`). Nach dem ersten
Workshoptag wurde das auf die sechs Befehle in `befehle.py` reduziert (siehe
Commit „Sechs Befehle als Notausgang"): `/merken`, `/verworfen`,
`/konflikt`, `/begriffe`, `/figur`, `/name`, `/material` und `/gruendlich`
existieren in der SPEC, aber nicht mehr im Code. Seit dem 05.09.2026 sind es
zehn: `/szene` ist dazugekommen, und mit ihm ist `LLM.prosa()` verdrahtet
(`szene.py`, SPEC § 4.5 Nachtrag), dann `/phase` (Arbeitsphase zeigen oder
umschalten), `/figur <Name> entfernen` (weiches Löschen, NACHTRAG N3) und
`/auswerten [N]` (ein Interview unter `aufnahme.MINDEST_WOERTER` doch noch
verdichten, N2) —
`/figur` legt bewusst **nichts** an, das macht weiterhin der Erkenner im
Gespräch. Wer an diesen Stellen weiterbaut, sollte sich auf `befehle.py`
verlassen, nicht auf die SPEC-Tabelle.

`befehle.behandle()` nimmt seit `/szene` ein optionales `klm` entgegen. Die
alte strukturelle Garantie („behandle bekommt kein LLM-Objekt, also kann ein
Befehl nicht am Modell scheitern") ist damit eine Zusage geworden, die der
Code weiterhin einhält: **kein Befehl ruft synchron ein Modell** — `/szene`,
`/fertig` und `/auswerten` geben sofort an einen eigenen Thread ab. Wer einen
elften Befehl anhängt, halte sich daran.

`einstellungen.py` liest zusätzlich `IT_MODELL_ERKENNER` (Vorgabewert
`google/gemma-4-31B-it`) — diese Variable fehlt noch in
`docs/betrieb-env.beispiel`.

## Starten und testen

**Regelweg: systemd-User-Units, nie Handstart.** Zwei Handstarts desselben
Bots = beide bekommen `409 Conflict` bei `getUpdates`, keiner empfaengt —
passiert am 04.09.2026 zweimal. Unit-Vorlage `docs/interview-theater@.service`
(nach `~/.config/systemd/user/`, `daemon-reload`), Start ueber
`scripts/betrieb-start.sh <gruppe>` (waehlt Python 3.11 aus `.venv`/uv —
das System-Python 3.9 kann `X | None` nicht importieren).

```
systemctl --user enable --now interview-theater@gruppe1.service   # je Gruppe
systemctl --user restart interview-theater@gruppe1.service        # Neustart
tail -f betrieb/gruppe1.log                                 # Log je Gruppe
```

**Verhalten aendern ohne Neustart** (`interview_theater/anweisungen.py`): alle
Prompts unter `interview_theater/prompts/` werden bei jedem Aufruf per mtime
geprueft und heiss nachgeladen -- auch `szene.md` und die Negativliste
`theater-tells.md`, die im Workshop waechst und beim naechsten Szenenauftrag
wirkt. Fuer spontane Regieanweisungen gibt es
`betrieb/zusatz.md` (alle Bots) und `betrieb/zusatz.<IT_BOT_NAME>.md` (ein
Bot); der Inhalt wird ans Ende der Gespraechs-Systemanweisung gehaengt,
Loeschen der Datei nimmt ihn zurueck. Erkenner/Journal/Verdichter bekommen
bewusst keinen Zusatz (gemessene Few-Shot-Prompts). Bedienung aus Hermes:
Skill `interview-theater-live-ops`.

Umgebungsvariablen: siehe `docs/betrieb-env.beispiel` zum Kopieren nach
`betrieb/<name>.env`. Handstart nur zum Debuggen, und nur wenn die Unit
gestoppt ist:

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m interview_theater.bot
```

- `pytest` — die Testsuite unter `tests/`, läuft ohne Netzzugriff (Attrappen
  statt echter Dienste). Enthält die Korpus-Validierung und die
  Bewertungsfunktionen aus `scripts/pruefe_prompts.py`, nicht den Lauf gegen
  das Modell.
- `python -m scripts.rauchtest [pfad-zu-audio.ogg]` — **kein Test, läuft nie
  automatisch, kostet Geld.** Ein echter Aufruf gegen Sprachmodell und
  optional Whisper, zur Kalibrierung der Token-Schätzung und als
  Erreichbarkeitsprüfung vor einem Einsatz.
- `python scripts/chat_leeren.py <chat_id> [--ja]` — setzt eine Gruppe auf
  null: löscht alle dem Bot bekannten Nachrichten aus dem Telegram-Chat
  (`deleteMessages`, Bot muss Admin sein; Nachrichten von vor seinem
  Eintritt und Telegram-Servicezeilen bleiben) und danach DB + Audio wie
  `loeschen.py`. Für den Workshop-Start nach einem Probelauf. Env der
  jeweiligen Gruppe laden — das Skript prüft, dass der Bot zur Gruppe passt.
- `python -m scripts.chat_leeren_blind <chat_id> [--zurueck 300]` — wenn die
  DB die Nachrichten nicht mehr kennt (nach `loeschen.py` oder nach einem
  Simulationslauf mit `--echte-db`): Marker senden, dann die letzten 300
  IDs rückwärts löschen. Telegram-Grenze: nur 48 h, nur als Admin.
- `python -m scripts.szenen_vergleich --nur opus,kimi,mistral,apertus` —
  eine Szene, gleicher Prompt, vier Modelle; Ausgabe als Markdown mit dem
  Prompt als Anhang. Grundlage der Entscheidung für Opus (05.09.).
- `python -m scripts.interviews_uebernehmen <ziel> <quelle> [<quelle> …] [--ja]`
  — hebt die Gruppengrenze für **Material** auf (06.09.2026, Ende Tag 2: nur
  noch eine Gruppe arbeitet weiter und soll alle Interviews sehen). Kopiert je
  Quellinterview Kopf, Teile, Transkripte, Verdichtung und
  `verdichtung_thema` (inkl. `zitat_geprueft`) sowie die Audiodateien in die
  Zielgruppe; **kein Modellaufruf**, die Quellen bleiben unverändert.
  Arbeitsstand, Figuren, Szenen, Knöpfe, Nachrichten, Journal und Kernzitate
  wandern bewusst **nicht** — das ist die Arbeit der Quellgruppe an ihrem
  Material, nicht das Material. `zum_kernthema_am` wird auf NULL gesetzt: was
  zur Kernfrage passt, entscheidet die Zielgruppe selbst. Die Nummerierung
  läuft weiter, weil `kontext.interviewbezeichnung` nach `id` zählt und neue
  Zeilen höhere ids bekommen; `name` wird beim Import auf „Interview N"
  gesetzt und nie aus der Quelle übernommen (dort kann ein Klarname stehen).
  Idempotent über `aufnahme.uebernommen_von` („`<quell_chat_id>:<alte_id>`",
  additiv migriert), alles in einer Transaktion, ohne `--ja` reiner
  Trockenlauf mit Zählung. Verweigert den Dienst, solange in Ziel oder Quelle
  eine Aufnahme läuft oder der Interviewmodus an ist. Mit `--ja` legt es
  selbst ein DB-Backup an, schreibt einen Journaleintrag in die Zielgruppe und
  eine Zeile in den Zielchat. Env der **Ziel**gruppe laden — die Quellen
  dürfen anderen Bots gehören, sie liegen in derselben Datenbank.
- `python scripts/loeschen.py <chat_id>` — der Löschweg: entfernt alle
  Datenbankzeilen einer Gruppe und ihr Audioverzeichnis, fragt vorher
  interaktiv nach Bestätigung. Es gibt bewusst keinen Löschbefehl im Chat.

**Simulation** (`simulation/`, `scripts/simulation.py`, Stand 06.09.2026 nachts):
simulierte Gruppen spielen den Bot durch alle **acht Phasen** — mit Inline-Knöpfen
(`attrappe` merkt die Leisten, die Stimme drückt per Knopftext oder schreibt
frei) und dem Schrittplan `skript.SCHRITTE_TAG2`. Stimmen: drei erfundene Sets
plus **PII-freie Personas aus Tag 1** (`simulation/tag1.py`,
`simulation/stimmen/tag1-gruppe{1,2,3}.md`, `regie.md`): nur Begriffe/Fragen der
echten Gruppen, Themen-Stichworte und Verhaltensaggregate, nie Transkripte oder
Klarnamen — `tests/test_simulation_tag1.py` prüft das gegen die echte DB, wenn
sie da ist. Der Richter (Claude Opus über den Proxy) bewertet zusätzlich:
Nachrichten bis zum Speichern, Fragen je Bot-Nachricht, Wiederholungsquote,
„Bot redet parallel zum Auftrag", Knöpfe angeboten→gedrückt, Phasenwechsel
proaktiv, Form je Szene bestätigt, Exposition der Szene 1. Berichte
`simulation/laeufe/2026-09-06-*.md` + Sammelbericht. Läuft gegen ein anderes
Modell als der Bot. **Kein Test, kein Ersatz für `pytest` oder
`pruefe_prompts.py`**; Doku `simulation/README.md`.

## Weboberfläche

Ein einziger Prozess für alle Gruppen, neben den Bots:

```
IT_DB=betrieb/soap.db python -m interview_theater.web
```

Unit-Vorlage `docs/interview-theater-web.service` (nach `~/.config/systemd/user/`,
`daemon-reload`, dann `systemctl --user enable --now interview-theater-web`), Log
nach `betrieb/web.log`.

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `IT_DB` | — (Pflicht) | dieselbe SQLite wie die Bots, **read-only** geöffnet |
| `IT_WEB_BIND` | `127.0.0.1:8010` | im Betrieb `100.75.24.33:8010` (Tailnet) |
| `IT_WEB_PREFIX` | `/theatersoap` | Präfix, unter dem nginx den Server durchreicht |
| `IT_WEB_URL` | `https://lab.artesmobiles.art/theatersoap` | nur für `scripts/web_links.py` |

Routen: `/` (Team-Dashboard, projiziert, alle Gruppen), `/g/<token>`
(Leseansicht einer Gruppe, Handy), `/gesund` (Health-Check, antwortet ohne
Datenbankzugriff). Jede Route greift auch mit vorangestelltem
`IT_WEB_PREFIX`, weil erst die nginx-Konfiguration entscheidet, ob das
Präfix beim Server ankommt.

`python scripts/web_links.py` gibt aus, welche Gruppe welchen Link bekommt.
Das Token steht in `gruppe.web_token`, erzeugt wird es beim ersten Kontakt
vom Bot (`repo.stelle_web_token_sicher`, aufgerufen aus `sichere_gruppe`) —
der Webserver kann es nicht anlegen, er liest read-only.

**Drei Grenzen, die nicht verhandelbar sind**, weil beide Seiten ohne Login
erreichbar sind und das Dashboard projiziert wird:

- kein Nachrichtentext und keine Transkripte auf dem Dashboard,
- kein Volltranskript auf der Gruppenseite (dafür gibt es `/wortlaut` im Chat),
- kein Belegzitat ohne `zitat_geprueft = 1`.

`IT_WEB_BIND` lehnt `0.0.0.0` mit einem Fehler ab: ein Tippfehler in einer
Env-Datei soll die Interviews nicht ins offene Netz stellen.

### Die Gruppenseite ändert Parameter (05.09.2026 abends)

Bis zu diesem Abend war beides read-only, mit der Begründung „sonst laufen
zwei Schreibwege gegeneinander" (N1). Die Begründung gilt weiter — deshalb
gibt es **keinen zweiten Schreibweg, sondern einen zweiten Auslöser für den
vorhandenen**: `web_schreiben.py` ruft ausschließlich `repo`-Funktionen,
dieselben wie `knoepfe._speichere` und `erkenner.wende_an`. In `web_daten.py`
kommt kein einziger Schreibpfad dazu; es bleibt read-only (`mode=ro`), und nur
der POST-Handler öffnet eine schreibende Verbindung (`db.verbinde` — WAL und
`busy_timeout`, wie `scripts/begruessen.py` aus einem fremden Prozess). Zwei
Tests halten das fest: kein `SELECT`/`INSERT`/`UPDATE` in `web_schreiben.py`,
kein Schreibpfad in `web_daten.py`. Änderbar ist **genau** `web_schreiben.FELDER`
und nichts sonst: Phase (1–8, Namen aus `phasen.PHASEN`), Begriffe, Fragen und
die drei Leitfaden-Felder (`frage_einleitungen`, `interview_eroeffnung`,
`interview_abschluss`), Setting (`rahmen`), Geschichte, je Figur
Name/Beschreibung/Interview/Entfernen/Hinzufügen und je Szene Titel, Form,
Ort, Zeit, Anlass, was passiert, was anders, Ton und die Besetzung — **nie
Material** (Aufnahmen, Transkripte, Verdichtungen, Belegzitate), nie der
Szenen-Volltext, nie das Journal, nie die USA-Einwilligung, nie der
Sprachprofil-Text, nie die Schärfungs-Zuordnungen. Auch **nicht der
Leitfaden**: er wird aus seinen Feldern gebaut (`leitfaden.aus_feldern`,
dieselbe Funktion wie im Chat) und steht read-only darunter — editierbar sind
die Quellen, nicht das Ergebnis. Seit dem Phasen-Umbau fehlen **Kernthema,
Kernthema-Richtung und Kernfrage**: sie sind keine Station mehr, `geschichte`
hat ihre Rolle übernommen; gesetzte Werte bleiben sichtbar
(`web_schreiben.NUR_ANZEIGE`, nur wenn gesetzt), änderbar sind sie nicht.
Ebenfalls nur Anzeige: der Formvorschlag je Szene (`szene.form_vorschlag` —
bestätigt ist allein `form`, und wer hier wählt, bestätigt gerade selbst) und
die Schärfungen aus Phase 6, als Zähler mit Kurzformen und **ohne Belegzitat**.
Die Dropdowns holen ihre Vorschläge aus der Tabelle `knopf`, zeigen also nur,
was im Chat ohnehin schon zur Auswahl stand. Jede Änderung hängt einen Journaleintrag an, `art
'entschieden'`, **`quelle 'web'`**, mit altem und neuem Wert (120 Zeichen je
Seite) — das ist der einzige Weg, auf dem der Gesprächs-Bot davon erfährt, denn
der Webserver spricht nicht mit Telegram: er liest das Journal bei jedem Zug
frisch (`kontext._baue_journal`). Wie in einem Knopf-Handler fällt hier **kein
Modellaufruf** an; wechselt eine Figur ihr Interview, wird deshalb das alte
Sprachprofil geleert und `geprueft_am` zurückgenommen, `knoepfe.stelle_figur_vor`
holt es im nächsten Zug im eigenen Thread nach. Das **Dashboard bleibt
vollständig read-only** und nimmt gar kein POST an — es hängt am Beamer. CSRF:
das Token in der URL ist das Geheimnis, dazu ein Formular-Nonce aus Token und
Stundenfenster (abgeleitet, nicht gewürfelt — ein zufälliger Nonce ließe das
sanfte Nachladen die Seite alle zehn Sekunden austauschen und risse jedes
offene Eingabefeld mit); aus demselben Grund lädt die Seite gar nicht erst
nach, solange der Fokus in einem Feld steht oder eines ungespeichert geändert
ist. Ein Neustart der Unit `interview-theater-web.service` ist nötig, die Bots
nicht.

### Prompt geändert? → Korpus laufen lassen

Die fünf Prompts werden heiß nachgeladen, also ändert sie jemand **während**
des Workshops. Der Regressionskorpus unter `korpus/` ist das Gegenmittel gegen
den Blindflug: 121 Absichtserkenner-Fälle (davon 45 Negativfälle; darunter
welche aus einer laufenden Aufnahme — `aufnahme` statt `nachrichten`, N1 —,
und 10 mit `zustimmung: true` markiert, N7; Stand 05.09.2026 nach dem
Szenen-Umbau, alle `art`-Werte mindestens zweimal, `szene_planen` mit
Szenenbezug), 22 Journal-Abschnitte (davon 11 leere), 7 erfundene
Interviewtranskripte — darunter einer, dessen Sollwert **null** Kernthemen
sind (der Live-Fall aus dem Probelauf, N2) — und 5 Sprachprofil-Fälle (T3,
eine je Sprechweise: kurze Sätze mit Selbstkorrektur, Code-Switching,
„man"-Distanz, Reihungen, Rückfragen), alle mit Sollwert.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner             # nach einer Änderung an erkenner.md
python -m scripts.pruefe_prompts alle --bericht       # vollständig, mit Markdown-Bericht
python -m scripts.pruefe_prompts erkenner --nur e18-verworfen-kindheitsfragen
python -m scripts.pruefe_prompts erkenner --modell <anderes>   # Modellvergleich
```

**Kein Test, läuft nie automatisch, kostet Rappen** — wie `rauchtest.py`. Rund
70 Aufrufe für `alle`, sequenziell (Infomaniak liefert bei Parallelität
429/5xx). Der Lauf schreibt seine `aufruf`- und `vorfall`-Zeilen in eine
Wegwerf-Datenbank, nie in `IT_DB`.

> **Die Regel: eine Änderung am Erkenner-Prompt gilt nur, wenn FP = 0 bleibt.**
> Null Falsch-Positive bei 25 Negativfällen ist die Zahl, die den Erkenner
> qualifiziert und die acht nicht gebauten Befehle begründet hat (SPEC § 4.3a,
> § 8.1). Genau das ist deshalb der Exit-Code: das Skript endet mit 1, sobald
> der Erkenner auch nur ein Falsch-Positiv liefert.
>
> **Was FP heißt, hat sich am 05.09.2026 gedreht (N7) — die Zahl nicht.** Ein
> Falsch-Positiv ist jetzt: ein Eintrag, dem im Abschnitt **kein konkreter
> Vorschlag und keine Zustimmung** vorausgeht. Ein Eintrag *nach* einer
> Zustimmung ist keiner mehr, auch wenn sie beiläufig war („passt", „nehmen
> wir", „das können wir so fix machen"). Grund: seit es weiches Löschen und
> `transkript_korrigieren` gibt, ist ein falscher Eintrag billig — ein Satz der
> Gruppe nimmt ihn zurück —, ein fehlender teuer: die Website bleibt leer, der
> Bot weiß nichts davon, und die Gruppe muss alles noch einmal sagen. Im
> Probelauf stimmte sie dreimal zu (Fragen, Kernthema, drei Figuren), und
> dreimal blieb der Arbeitsstand leer. **Das Prüfskript rechnet dafür nicht
> anders — es sind die Sollwerte im Korpus, die sich gedreht haben.** Daneben
> steht seither eine zweite Kennzahl (nicht im Exit-Code): **Falsch-Negative in
> Zustimmungsfällen**, Korpusfeld `zustimmung`, soll ebenfalls 0.
>
> Zwei Arten bleiben auf „im Zweifel kein Eintrag" kalibriert:
> `szene_schreiben` (kostet zwei Minuten Wartezeit und eine unbestellte
> Nachricht) und `entfernen` (nimmt etwas weg).

Berichte landen in `korpus/berichte/` und sind **gitignored**: sie enthalten
vollständige Modellantworten. Der Korpus selbst ist frei erfunden und gehört
ins Repository.

### Simulation: ein ganzer Workshop gegen die echten Modelle

Der Korpus misst einzelne Prompts an einzelnen Fällen. Was er **nicht** misst,
ist der Zusammenhang: ob eine Gruppe mit diesem Bot von einer Begriffsliste zu
einem Szenentext kommt, ob Zustimmungen ankommen, ob der Bot behauptet, etwas
notiert zu haben, das nirgends steht. Genau dafür gibt es
`scripts/simulation.py` (Details in [simulation/README.md](simulation/README.md)).

Drei simulierte Teilnehmerinnen arbeiten sich durch neun Schritte: Begriffe,
Fragen, fünf Interviews, Kernthema, Figuren, Phase 5, eine Szene, eine
Korrektur, `/stand`. Gefahren wird **derselbe Codepfad wie im Betrieb**
(`bot.verarbeite_update`, `bot._zug_und_erkenner`), nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`. Der
Umweg über Telegram ist gar nicht möglich: Telegram liefert Bot-Nachrichten
nie an andere Bots (Bot-FAQ). Interviews kommen als Text
(`aufnahme.importiere_text`, § 10.5), kein Whisper.

**Zwei Modelle, eine Trennlinie.** Alles, was der Bot tut, läuft über
Infomaniak — er ist der Prüfling. Alles, was Simulation ist (die Stimmen, der
Richter, die einmalige Erzeugung der fünfzehn Interviewdatensätze), läuft über
**Claude Opus** an einem lokalen Proxy (`simulation/claude.py`,
`IT_SIM_URL`/`IT_SIM_MODELL`, Anthropic-Messages-Format, kein
Authorization-Header). Ohne diese Trennung würde der Prüfling seine eigenen
Teilnehmerinnen spielen und sich anschließend selbst benoten. Die
Simulationsseite läuft über ein Abonnement und kostet je Aufruf nichts — die
Kostenzeile im Bericht ist deshalb genau das, was ein Workshoptag zahlen
würde.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.simulation --set 1 --seed 7 --bericht
python -m scripts.simulation --mix 1,2,3 --seed 3
python -m scripts.simulation --set 1 --seed 1 --ohne-szene   # ohne Reasoning-Lauf
python -m scripts.simulation --set birk --bericht            # echtes Material, ~10 min
python -m scripts.simulation --alle                          # Sets 1-3 und birk
```

**Die Stimmen sind Personen, keine Sprachstile** (Gülten 58, Dilan 24,
Halyna 41 — Steckbriefe in `simulation/stimmen/*.md`, je mit einem eigenen
Ziel im Workshop). Wer dem Computer am wenigsten traut, schreibt am
seltensten; der `--seed` variiert nur, wer wann spricht.

**`--set birk` ist die Messlatte:** das einzige Set auf echten Daten (Birks
Testinterview vom 04.09., eine Stimme, kalibriert auf seinen echten
Chatverlauf). Gemessen wird die **Navigation**, nicht der Text — der Bericht
stellt neben jede Zahl die aus dem echten Chat. Der Lauf schreibt drei Szenen
in drei Formen (Dialog, Lied, Rap) und verbietet deshalb `--ohne-szene`. Das
Material liegt außerhalb des Repositories (`IT_SIM_BIRK`).

**Was sie misst.** Mechanisch, ohne Modell: erreichte Phase, Vollständigkeit
des Arbeitsstands, Anteil der Zustimmungen, nach denen wirklich eine
Notiert-Zeile kam (die Kennzahl aus N7), Verdichtungen und geprüfte
Belegzitate, Echo (`ablauf.ist_echo`), Rückfragen vor dem Szenenauftrag,
**behauptete Schreibvorgänge** (Bot sagt „notiert", ohne dass der Erkenner
etwas geschrieben hat — Soll 0), Namensanrede, Medianlänge der Bot-Antworten
(Soll < 700 Zeichen), Kosten und Dauer. Dazu bewertet ein Richter (Opus)
jeden Abschnitt mit 0/1/2 auf vier Kriterien und jeden Szenentext auf drei
weitere.

**Und die zwei Hintergrundwege, die entscheiden, was der Bot weiß.** Das
**Journal**: Einträge je Art, wie viele davon der Richter im Chat
wiederfindet, welche Vorschläge fehlen, Doppeleinträge — und ob der Extraktor
überhaupt lief (er läuft nur bei Verdrängung; sonst steht „Journal nicht
ausgelöst" statt einer Null, `--fenster-klein` provoziert sie). Der
**Kontextaufbau**: `kontext.baue(..., protokoll=list)` schreibt je Prompt mit,
welcher Block mit wie vielen Token drin stand; der Bericht zeigt die
Verteilung, die Prompts über `ZIEL`, die mit Kürzung — und bei den fünf
schwächsten Antworten urteilt der Richter am Block-Umriss, ob dem Bot
Information gefehlt hat, die in der DB stand. Dazu ein Skript-Schritt
**Zitatabfragen** mit der mechanischen Kennzahl `zitat_erfunden` (Soll 0).

**Kein Test, läuft nie automatisch, kostet Geld** — wie `pruefe_prompts.py`
und `rauchtest.py`, nur eine Größenordnung mehr: ein voller Lauf sind einige
hundert Aufrufe, grob 0,20–0,60 CHF für den Bot (die Stimmen und der Richter
laufen über das Abonnement und kosten nichts), dazu ein Szenenlauf mit
Reasoning (2–4 Minuten, der teuerste Einzelposten — `--ohne-szene` spart
ihn). Sequenziell; bei 429 wartet das Skript und wiederholt, wie
`pruefe_prompts`.

> **Die Regel: nach jeder Prompt-Änderung ein Lauf mit `--set` und einer mit
> `--mix`.** Der erste hält den Themenkreis fest und macht zwei Läufe
> vergleichbar; der zweite mischt drei Themenkreise und zeigt, was nur an
> einem Set hing. Beide mit demselben Seed wie beim letzten Mal, sonst
> vergleicht man Besetzungen statt Prompts.

Transkript (`simulation/laeufe/`) und Bericht (`simulation/berichte/`) sind
**gitignored** — sie enthalten vollständige Modellantworten. Die eine
Ausnahme ist `simulation/berichte/verlauf.jsonl`: eine Zeile je Lauf mit allen
Kennzahlen und dem git-HEAD, der Vergleichsmaßstab zwischen zwei
Prompt-Ständen. Die fünfzehn Interviewtranskripte unter
`simulation/interviews/` sind frei erfunden und gehören ins Repository —
geschrieben hat sie einmal `simulation/erzeuge_interviews.py` mit Opus, das
**Ergebnis** ist das Artefakt, nicht das Skript.

Der Simulator ist **datengetrieben** gebaut: Phasen aus `phasen.PHASEN`,
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort „Notiert:"
aus `erkenner.baue_meldung`. Ein Umbau an Phasen oder Feldern soll ihn nicht
mitreißen — wer trotzdem etwas anpassen muss, findet die Stellen in
`simulation/skript.py`.

Beim Erweitern: `wert` im Erkenner-Korpus ist der **Kern** der Sache
(`"Meryem"`, `"Mutter gegen Tochter"`), nicht der erwartete Wortlaut —
verglichen wird als Teilstring in beide Richtungen, ein leerer `wert` prüft
allein die `art`. `erwartet[].text` im Journal-Korpus ist ein
**Muss-Stichwort-Set**, mit `|` getrennt (`"sechs|fragen"`), ebenfalls kein
Wortlaut. `tests/test_korpus.py` prüft Form und Mindestbesetzung mit, ohne
Netz.

## Was bewusst fehlt

- **Hartes Löschen im Chat.** Entfernt wird nur weich, und Material
  (Aufnahmen, Transkripte, Verdichtungen) gar nicht — der vollständige
  Löschweg bleibt `scripts/loeschen.py`, von Hand, mit Rückfrage.
- **Freies Schreiben über die Weboberfläche.** Die Gruppenseite ändert seit
  dem 05.09.2026 abends eine kleine, feste Liste von Parametern (siehe
  „Weboberfläche"); alles darüber hinaus — Material, Szenen-Volltext,
  Journal — bleibt Sache des Chats.
- **Der automatische Phasensprung.** Er hat einmal existiert
  (`ART_ERMOEGLICHT`, `sprung_nach`) und ist am 05.09.2026 **bewusst und
  ersatzlos** gestrichen worden, nicht aus Zeitmangel: **Datenstand ist nicht
  Absicht** — eine fertige Verdichtung sagt nicht, ob noch drei Interviews
  kommen, und ein gesetztes Kernthema sagt nicht, dass die Gruppe damit
  fertig ist. Geblieben ist die Frage (`phasen.moegliche_naechste` /
  `offenes_angebot`): erlaubt die Materiallage eine höhere Phase, bietet der
  Bot sie im Fluss an, gesetzt wird sie nur von der Gruppe.

Die **Weboberflächen sind gebaut** (`web.py`/`web_daten.py`, siehe
„Weboberfläche" unten) — und **Szenen werden geschrieben** (`szene.py`, seit
04.09.2026 abends): der Volltext liegt in `szene` und auf der Gruppenseite.

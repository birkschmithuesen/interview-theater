# Bindende Entwurfsentscheidungen

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 227–1121).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Bindende Entwurfsentscheidungen

- **Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte
  Entscheidungen.** Jede Nachricht wird roh gespeichert, unabhängig davon, ob
  sie einen Zug auslöst oder je in den Prompt wandert — etwas nicht
  aufzunehmen ist unumkehrbar, es nicht in den Prompt zu legen kostet nur
  Kilobyte (SPEC § 1).
- **Der Prompt ist datengetrieben.** `kontext.baue()` lässt jeden Block weg,
  solange die zugrundeliegenden Daten leer sind. Biegt die Gruppe ab, ändert
  sich die Materiallage und der Prompt folgt automatisch (SPEC § 6.1).
- **Inline-Knöpfe an den Auswahl-Momenten** (05.09.2026, `knoepfe/`).
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
- **Die Phase setzt allein die Gruppe — per Chat, Befehl oder Klick** (seit
  05.09.2026, `phasen.py`, SPEC § 0 Leitsatz 3 Nachtrag; erweitert am
  30.09.2026): `phase_setzen`, `/phase` **oder ein Klick auf eine Phase in der
  Web-Phasenübersicht**, nie still erraten und auch nicht vom Bot selbst. Der
  automatische Sprung (`ART_ERMOEGLICHT`, `sprung_nach`) bleibt **ersatzlos
  gestrichen** — **Datenstand ist nicht Absicht**; ein Klick dagegen *ist* die
  Gruppe.
  **Der Klick geht durch dieselbe Funktion wie der Befehl**
  (`befehle.wechsle_phase`, Parameter `quelle`), damit er nie in einer anderen
  Phase landet als `/phase` oder der Knopf: Bestätigung im Browser → POST
  `/g/<token>/chat/phase` mit Nonce → ein gewöhnlicher Eingang
  (`WEB_TYP_BEFEHL`, Text `/phaseklick N`) → der **Bot** setzt die Phase und
  schickt die Eintrittsnachricht. Der Webserver setzt sie **nicht** selbst: er
  hat kein `klm`, und `knoepfe.eintritt_in_phase` stößt Modellarbeit in
  Threads an. Im Journal steht `quelle 'web'` statt `'befehl'` — sonst ist die
  Zeile dieselbe (Test). `/phaseklick` ist ein **versteckter** Befehl: nicht im
  Menü, nirgends beworben, er ist der Weg des Knopfes durch die Naht.
  Geblieben ist die **Frage**: erlaubt die Materiallage eine höhere
  Stufe, bekommt der Gesprächs-Prompt einen Hinweisblock
  (`kontext._baue_phasenhinweis`) mit der Anweisung, im Fluss nachzufragen —
  einmal je Stufe (`arbeitsstand.phase_angeboten`). Dieselbe Frage hängt an der
  Verdichtungs-Nachricht am Ende eines Interviews (`aufnahme._phasenfrage`);
  beide Stellen teilen sich den Merkposten über `phasen.offenes_angebot()` /
  `merke_angebot()`, deshalb liest die eine Funktion nur und die andere
  schreibt.
- **Die sieben Phasen sind: 1 Begriffe · 2 Fragen · 3 Interviews ·
  4 Setting, Figuren & Geschichte · 5 Schärfung · 6 Szenen als Geschichte ·
  7 Feinschliff** (Stand 06.09.2026 abends, `phasen.PHASEN` — die Liste im
  Code ist die Wahrheit, nicht diese Zeile). Die Geschichte des Umbaus in
  zwei Schritten: 05.09. nachts wurden aus sieben Phasen acht („4 Setting &
  Figuren · 5 Geschichte · 6 Schärfung · 7 Szenentexte · 8 Durchlauf"),
  06.09. abends wurden daraus wieder sieben — **4 und 5 sind wieder eine
  Station** (die Gruppe erfindet Setting, Figuren und Geschichte in einem
  Zug), und aus „Szenentexte + Durchlauf" wurde „6 Szenen als Geschichte" +
  „7 Feinschliff". Der Grund ist in beiden Schritten **nicht**
  Feingliederung, sondern die Arbeitsrichtung: erst erfinden, dann schärfen,
  und die Form einer Szene erst wählen, wenn die Geschichte steht.
  Migriert wird zwischen den Ständen, nicht umgedeutet
  (`db.PHASEN_UMNUMMERIERUNG*`).
- **Erst erfinden, dann schärfen** (Birk, 05.09.2026 23:30 — die tragende
  Entscheidung des Ablaufs). Bis dahin entstanden Figuren und Szenen **aus**
  den Interviews; das Ergebnis war handwerklich richtig und dramaturgisch
  tot, weil die Gruppe ihren eigenen kreativen Anteil nicht wiedererkannte —
  sie sah eine Nacherzählung ihres Materials. Jetzt:
  - In **4 (Setting, Figuren & Geschichte)** erfindet die Gruppe frei. Der
    Bot fragt **offen** („Welche Personen soll es geben? In welchem
    Setting spielt es?" / „Was soll passieren? Wie soll es enden?") mit nur
    zwei Knöpfen — „Eigene Idee" und „Schlag du vor" —, und seine Vorschläge
    speisen sich **ausschließlich aus `arbeitsstand.begriffe`, `fragen` und
    dem schon Festgelegten**. Kein Material: `kontext.baue` liefert dort
    weder Verdichtungen noch Transkripte noch das Kernpaket
    (`kontext.PHASEN_ERFINDEN = (4,)`, `material_erlaubt`,
    `kernpaket_erlaubt` ab `PHASE_KERNPAKET = 5`), und
    `szenenfolge.baue_nutzertext_geschichte` baut den Nutzertext ohne
    Material. Das ist im Code durchgesetzt, nicht im Prompt gebeten — ein
    Prompt, der Material sieht, referiert es.
  - In **5 (Schärfung)** kommt das Material dazu und legt sich **neben** das
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
    spricht sie?" und der Sprachduktus laufen erst ab Phase 5
    (`knoepfe.ebene2_erlaubt`); in Phase 4 ist die Liste nach Ebene 1 fixiert.
    In 4 danach zu fragen wäre genau die Rücklenkung aufs Material, die der
    Umbau vermeidet.
  - **Das Kernthema ist keine eigene Station mehr.** `arbeitsstand.geschichte`
    (Bogen + Ende) übernimmt seine Rolle im Kernpaket. Kernthema, Kernfrage
    und Kernzitate bleiben im Code funktional und getestet
    (rückwärtskompatibel für bestehende Gruppen), werden aber nicht mehr
    angeboten; `kernzitate.py` bleibt als Basis, `schaerfung.py` nutzt
    dieselbe Prüf- und Speicherlogik.
  - Voraussetzungen (`phasen.voraussetzungen`, der Code ist die Wahrheit):
    **2** braucht Begriffe; **3** braucht Fragen, die geprüfte Sensibilität
    (`fragen_weich` **oder** `frage_einleitungen`, beide zählen auch leer),
    `interview_eroeffnung` **und** `interview_abschluss`; **4** braucht eine
    fertige Verdichtung **und** kein offenes, unausgewertetes Interview;
    **5** braucht `rahmen`, `figuren_fixiert_am`, mindestens eine Figur,
    `geschichte` und ≥ 1 Szene; **6** braucht `geschichte` **und** ≥ 1 Szene
    — die Schärfung ist ein Angebot, keine Pflicht, deshalb sperrt sie 6
    nicht; **7** braucht **alle** geplanten Szenen als Geschichte
    (`szene.prosa`, ersatzweise `volltext`) — ein Urteil über ein Stück, dem
    drei Szenen fehlen, ist keins.
- **Der Szenen-Prompt bekommt die Schärfungen JE SZENE, nicht global**
  (`szene._kernpaket_text(conn, chat_id, ziel)`). Eine Szene sieht die
  Interviewstellen, die zu ihr und zu ihren Figuren gehören — und keine
  fremden. Ohne Schärfungen fällt der Code auf die alte, globale
  Kernzitat-Auswahl zurück: eine Gruppe, die den Umbau nicht mitgemacht hat,
  verliert nichts.
- **Der Szenen-Prompt liest auch den gewählten Sprachstil** (02.10.2026,
  Padua M1): `szene._figuren_text` setzt `figur.sprachstil` als eigene Zeile
  (`ZEILE_SPRACHSTIL`, nie in Anführungszeichen — ein Stil ist kein
  Belegzitat) neben `sprachprofil` und die Zitate; den Kopf von Block 3
  wählen seitdem **drei** Lagen: ein echtes Zitat → `FIGUREN_KOPF`
  („wörtlich"), sonst ein nicht-leerer Stil → `FIGUREN_KOPF_MIT_STIL`
  (die Gruppe hat gewählt), sonst `FIGUREN_KOPF_OHNE_STIMME` (unverändert).
  Vorher war der Einzelszenen-Prompt mit und ohne Stil byte-identisch
  (`docs/sprachstil-wirkung-2026-09-30.md`, Weg 2).
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
- **Phase 4 heißt „Setting, Figuren & Geschichte"** — das frühere Feld
  `rahmen` ist das Setting (Ort, Zeit, Anlass) und behält seinen
  Spaltennamen; nach außen (Knopftexte, Notiert-Zeile, Weboberfläche) heißt
  es „Setting". `format` und `hauptkonflikt` bleiben als Spalten stehen und
  tragen keine Entscheidung mehr. Stichwörter: „Rahmen", „Setting", „Format",
  „Konflikt", „Kernthema" **und „Geschichte"** zeigen seit dem Zusammenlegen
  alle auf 4 — `prompts/erkenner.md` wurde dafür **nicht** angefasst, die
  Zuordnung Wort→Nummer liegt in `phasen.STICHWOERTER`.
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
- **Phasennummern werden migriert, nicht umgedeutet** (`db.SCHEMA_VERSION`
  = 3, `db.PHASEN_UMNUMMERIERUNG` bis `_3`). **Drei** Schritte hintereinander,
  eine alte Datenbank läuft durch alle drei: acht → sieben (04.09.: Kernthema
  und Figuren wurden eine Phase), sieben → acht (05.09. nachts: 4 und 5
  bleiben, 6 → 7, 7 → 8; die neue 6 bekommt niemand zugewiesen, sie ist ein
  Angebot und keine übersprungene Station) und acht → sieben (06.09. abends:
  4 und 5 werden wieder eine Station, 6 → 5, 7 → 6, 8 → 7). Der Merkposten
  ist SQLites eingebautes `PRAGMA user_version` — keine eigene Tabelle, keine
  Zeile, kein Schema. Das Journal bleibt dabei unangetastet: dort steht
  „Phase 5 · Figuren", weil das am 04.09. wahr war, und ein Journal wird nur
  angehängt.
- **Eine lange Sprachnachricht ohne Interviewmodus wird gefragt, nicht gedeutet** (06.09.2026, Live-Fall Gruppe 1, 13:32–13:37). Der gemessene Fall: 186 Sekunden Interview ohne vorherigen Druck auf „Interview starten". Das Transkript ging als **Gesprächsbeitrag** in den Kontext, das Gesprächsmodell antwortete mit einem Denkspur-Rest, der **Absichtserkenner** las die Aufzählung der interviewten Person als Begriffsliste der Gruppe und **überschrieb `arbeitsstand.begriffe`** (Rassismus, Liebe, Spaß, Streit → Rausgehen, Familie, Musik hören), und der Journal-Extraktor schrieb einen `vorgeschlagen`-Eintrag aus dem Interviewinhalt. Drei Modellläufe auf Material, das keine Absicht der Gruppe war — genau der Fall, gegen den `repo.TYP_TRANSKRIPT` seit § 10.6 schützt, nur hier ungeschützt, weil ohne Modus niemand ein Interview vermutete. Seitdem gilt in `aufnahme._kurz_abschliessen`: Dauer über `HINWEIS_AB_S` (60 s) **und** Interviewmodus aus → **kein Gesprächszug, kein Erkenner, kein Journal-Extraktor** auf dieser Nachricht. Das Transkript wird gespeichert (Empfangen und In-den-Prompt-legen sind zwei Entscheidungen), aber **versteckt**: `repo.aktualisiere_transkribierte_nachricht(..., versteckt=True)` legt es als `TYP_TRANSKRIPT` ab, und damit fällt es aus allen drei Fenstern zugleich (`letzte_nachrichten`, `unextrahierte`, `unjournalisierte`) — `unterdrueckt` allein leistet das **nicht**, es filtert nur `unbeantwortete`. Stattdessen die deterministische Frage „Das klingt nach einem Interview (M:SS). Soll ich es als Interview speichern?" mit zwei Knöpfen (`knoepfe.biete_interview_ohne_knopf`, `ART_OHNE_KNOPF_JA`/`_NEIN`, die `aufnahme.id` im `wert`). Die Knopfregel ist erfüllt: es gibt etwas Fixes zu speichern und genau zwei benannte Möglichkeiten. **Ja** → `aufnahme.nimm_als_interview`: Modus an, Kopf anlegen, **gezielt genau diese Aufnahme** einsammeln (`repo.ziehe_eine_in_interview` mit der id — das `NACHZUEGLER_FENSTER_S`-Zeitfenster darf darüber nicht entscheiden, zwischen Sprechen und Knopfdruck stehen Minuten), `stelle_phase_interviews_sicher`, dann die Folgefrage „Fertig, auswerten" · „Es kommt noch was" (`ART_OHNE_KNOPF_FERTIG`/`_WEITER`, Kopf-id im `wert`); „Fertig" ist wortgleich derselbe Weg wie „Interview beenden" (`beende_interview` + `starte_abschluss` im Thread). **Nein** → `aufnahme.nimm_als_beitrag`: `repo.zeige_transkript_nachricht` macht die Zeile sichtbar, und `bot._zug_und_erkenner` wird **genau einmal** in einem eigenen Thread nachgeholt. **Keine Antwort → gar nichts** (kein Auto-Ja, kein Zeitgeber); fürs Dashboard bleibt der Vorfall `interview_ohne_knopf_offen` stehen, und „Interview starten" sammelt das Material weiterhin als Nachzügler ein — der Weg, der am Live-Tag fünf Minuten später tatsächlich funktioniert hat. Zusage 2 gilt: kein Modellaufruf in den vier Handlern `knoepfe._wirkung_ohne_knopf_ja/_nein/_weiter/_fertig`. Unter 60 Sekunden ändert sich nichts, dort bleibt eine Sprachnachricht ohne Modus ein Gesprächsbeitrag. Der frühere beiläufige Materialhinweis (`aufnahme._TEXT_MATERIAL_HINWEIS`) ist damit tot: er hing an genau dem Zug, den es nicht geben durfte. Tests: `tests/test_interview_ohne_knopf.py`.
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
  art `szene_planen`, kompakter Text mit `|`-getrennten Feldern. **Fünf**
  Formen (`szene.FORMEN`: Dialog, Monolog, Chor, Lied, Rap), Dialog ist
  der Rückfall — eine „stumme Szene" gibt es nicht mehr, und `prosa.md` im
  selben Verzeichnis ist keine Form, sondern der Regelblock der Phase 6. **Sperre vor dem Aufruf** (T5, `szene.sperrtext`): fehlt ein
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
  einem langen Text. **Macht gerade dieses Speichern die Phase
  abschließbar, ersetzt die Abschlussnachricht die Notiert-/Speicherleiste**
  (02.10.2026, Padua Hotfix B5, `knoepfe.sende_abschluss_statt_meldung`, an
  beiden Wegen: `erkenner._sende_meldung` und `basis._speichere`): EINE
  Nachricht mit „Weiter zu Phase N · Titel", „<Feld> ändern"
  (`ART_NOCH_NICHT`) und — am Erkenner-Weg — dem Undo-Knopf. Antworten mit über 60 % Deckung zur vorigen Bot-Nachricht
  werden ersatzlos verworfen (`ablauf.ist_wiederholung`, Vorfall
  `wiederholung_verworfen`); löst eine Nachricht einen Auftrag aus, schweigt
  der Gesprächs-Bot ganz (`ablauf.ist_auftrag`). Die Grundleiste speichert nie
  über ein gesetztes Feld hinweg, solange keine Änderung offen ist
  (`knoepfe._ist_bestaetigung`, `_feld_ist_frei`). Das Kontextfenster ist kurz
  und chronologisch, sortiert nach `gesendet_am` — **nicht** nach
  `message_id`, denn übernommene Historien tragen negative, absteigend
  vergebene ids. Seine Grenzen stehen im nächsten Absatz
  (`kontext.fenster_grenzen()`). Belege:
  `docs/analyse-interaktion-testgruppe-2026-09-05.md`.

- **Das Gesprächsfenster ist in ZEICHEN bemessen, es ist nie leer, und der
  Journal-Extraktor liest dieselbe Grenze** (06.09.2026, Kontext-Audit
  Aufträge 1+2, `docs/kontext-audit-2026-09-06.md` C.2/C.3/C.4). Drei Sätze,
  die zusammengehören, weil sie eine Wurzel haben — *Grenzen, die nur einen
  Teil bemessen, und Schwellen, die nebeneinander statt voneinander abgeleitet
  gesetzt sind*:
  1. **`kontext.FENSTER_ZEICHEN` (12.000) ist das primäre Maß**, nicht mehr die
     Nachrichtenzahl (SPEC § 6.2 Block 7, und dieselbe Entscheidung, die
     hermes-agent in `context_compressor.py:13` getroffen hat: *„Token-budget
     tail protection instead of fixed message count"*).
     `FENSTER_NACHRICHTEN` (20) ist die Obergrenze darüber.
  2. **`FENSTER_MINUTEN` (30) ist weich**: mindestens die letzten
     `FENSTER_MIN_NACHRICHTEN` (6) bleiben immer im Fenster. Gemessen war das
     Fenster nach *jeder* Pause über 30 Minuten — Mittag, Nacht, Probe —
     **vollständig leer** (Befund C.2, an der Test-DB reproduziert). Damit
     funktioniert auch die Pausenzeile `[Pause: N Stunden]` aus § 6.2 zum
     ersten Mal: sie steht auch **vor dem Auslöser**, weil der häufigste Fall
     einer langen Pause der ist, in dem die erste Nachricht danach den Zug
     auslöst.
  3. **`kontext.fenster_grenzen()` / `kontext.waehle_fenster()` sind die eine
     Quelle**, die der Promptbau *und* `journal.berechne_verdraengten_abschnitt`
     lesen. Vorher rechnete der Extraktor gegen `BUDGETS["fenster"] = 8000`
     Token und hielt 31 Nachrichten für „noch im Fenster", während der Prompt
     20 sah — die Differenz wurde nie journalisiert und stand danach nirgends.
     `BUDGETS["fenster"]` ist seitdem **historisch und von keinem Codepfad mehr
     gelesen**. `journal.SCHWELLE_VERDRAENGUNG` ist von 2.000 auf **600** Token
     gesenkt (sie bezog sich auf das alte 8.000er Fenster; an Tag 1 sprang der
     Extraktor in **allen drei** Betriebsgruppen kein einziges Mal an).
     **Wer eine Fenstergrenze ändert, ändert sie in `fenster_grenzen()` — und
     der Regressionstest `test_verdraengung_rechnet_gegen_dasselbe_fenster_wie_
     der_prompt` prüft, dass Fenster und verdrängter Abschnitt die
     Nachrichtenliste lückenlos und überschneidungsfrei teilen.**

  Dazu die Sichtbarkeit, die vorher fehlte: **`kontext.baue` schreibt bei jedem
  Aufruf eine Umriss-Zeile ins Log** (`kontext.umrisszeile`, Token je Block,
  Gesamt, gekürzt ja/nein — **nur Zahlen, nie Prompt-Inhalt**). Sie steht in
  `baue()` selbst und nicht bei den Aufrufern, damit sie jeden Pfad erfasst;
  ein durchgereichter Parameter wäre genau der Weg, auf dem sie beim nächsten
  neuen Aufrufer wieder fehlt (`umriss()` gab es seit jeher, es rief nur
  niemand). Und ein **zweiter Vorfalltyp `kontext_kuerzung_erfolglos`**: ist
  der Körper nach allen vier Kürzungsstufen immer noch über der Grenze, wird
  das eigens vermerkt, mit dem Umriss der übrig gebliebenen Blöcke.
  `kontext_gekuerzt` bleibt daneben stehen — beides ist wahr, aber „gekürzt"
  und „reicht nicht" sind zwei verschiedene Meldungen (hermes-agent,
  `should_compress_info`: *„Without this signal an over-threshold session fails
  opaquely."*).

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
  Token. Beide Budgets gelten seit dem 30.09.2026 für die **ganze** Eingabe,
  Systemanweisung eingeschlossen: `szene.nutzer_budget` zieht die Anweisung
  des Laufs (Form + Stil, gemessen bis 37 043 Zeichen ≈ 19 496 Token) ab,
  bevor der Nutzertext gemessen wird — vorher hätte ein Nutzertext am Budget
  mit ihr den Infomaniak-Raum um 7 000 Token gerissen
  (`docs/kontext-3-5-kalibrierung.md`). Env `IT_SZENE_TOKEN_MAX` überschreibt
  und meint ebenfalls die ganze Eingabe. Jede Szene liefert per
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

- **Kürzen ist eine Überarbeitung, keine neue Szenenfolge** (30.09.2026,
  Maßnahmen C4/C7/C9/C10 aus `docs/analyse-phase5-chaos-2026-09-06.md`; der
  Plan dazu: `docs/superpowers/plans/2026-09-30-padua-a5-dortmund-reste.md`).
  Vier Dinge, die eine Wurzel haben — am 06.09. bat die Gruppe um eine
  Kürzung, und weil es dafür keinen Weg gab, wurde daraus ein Neuaufbau:
  aus drei Szenen wurden sechs und eine Stunde später noch einmal sechs.
  1. **Der Knopf „Kürzer (25 %)"** steht an genau zwei Orten — unter der
     fertigen Kurzgeschichte (`knoepfe.zeige_kurzgeschichte`, Phase 6) und
     unter einem frisch geschriebenen Szenentext
     (`knoepfe.biete_nach_szenentext`, Phase 7). **Nicht** unter „Szene N
     ansehen": dort liest man, dort gehört „Frühere Fassungen" hin. Er wirkt
     wie „Passt, aber anders", nur ohne Rückfrage: die Regie-Notiz steht fest
     (`kuerzung.notiz_fuer_szene`, `notiz_fuer_prosa`), der Prozentwert an
     **einer** Stelle (`kuerzung.PROZENT`). Mit Szenennummer läuft
     `szene.starte`, ohne läuft `kurzgeschichte.starte` — die Phase entscheidet
     sich dabei von selbst, weil `szene.schreibt_prosa` ohnehin nach `prosa`
     oder `volltext` verzweigt. **Die Prosa-Notiz nennt keine
     Abschnittszahl** (seit dem Abschlussreview der Karte P2-Fix,
     02.10.2026): gebunden ist die Zahl, weil der Abgleich ergänzend ist und
     sonst zwei Abschnitte mit ihrem alten, langen Text stehen blieben — aber
     genau einmal, im Auftrag (`kurzgeschichte._ZEILE_ABSCHNITTE`, die Zahl
     der geplanten Szenen) oder bei aktivem Längen-Profil im Budget-Block
     (`laengen.SATZ_BINDUNG`). Vorher zählte die Notiz die Szenen **mit**
     Prosa, und bei sechs geplanten und vier geschriebenen standen „genau 4"
     und „genau 6" im selben Prompt
     (`tests/test_kuerzung.py::test_kuerzen_bindet_die_abschnittszahl_genau_einmal*`).
     Die Notiz sagt nur noch, dass die Abschnitte mit Titeln und Reihenfolge
     bleiben und innerhalb gekürzt wird. Beim Kürzen der ganzen
     Geschichte geht die bisherige Prosa **als Vorlage** in den Prosalauf
     (`kurzgeschichte.starte(..., vorlage=True)`) — sonst schriebe das Modell
     „25 Prozent kürzer" über einen Text, den es nie sah; ohne `vorlage`
     bleibt der Nutzertext zeichengleich zum bisherigen Weg. Der Prosalauf
     hat dabei **keine eigene Eingabebudget-Prüfung** (wie schon vorher
     nicht). Beim Kürzen **einer Szene in Phase 6** ist `volltext` leer; der
     Auftrag trägt deshalb `szene.BISHER_MARKER`, und nur mit ihm steht die
     bestehende Prosa der Szene als „Bisheriger Text" im Nutzertext
     (`szene._diese_szene_text(..., bisher_prosa=True)`) — jeder Lauf ohne
     Marker bleibt zeichengleich. `kuerzung.starte` liefert
     `(quittung, gestartet)`, `gestartet` aus dem Rückgabewert des
     Schreibwegs (Thread oder `None`), nicht aus dem Wortlaut der Quittung;
     und `kuerzung.starte` setzt selbst den Prüf-Vermerk für spätere Szenen
     (`knoepfe._melde_spaetere`), nur mit Lauf — damit gilt er für Knopf und
     Erkenner gleich.
  2. **Die Erkenner-Art `szene_kuerzen`** macht „mach das kürzer" im Chat zum
     selben Weg. Sie hat **keinen Schreibpfad** (wie `szene_schreiben`) und
     wird erst in `laufe()` ausgewertet (`erkenner._starte_kuerzung`),
     höchstens **eine je Lauf**. Leerer `wert` heißt „die ganze
     Kurzgeschichte" — eine geratene Nummer schriebe die falsche Szene neu.
     **Aber nur, solange Geschichten entstehen:** ab der Phase der
     Theatertexte (`szene.schreibt_prosa` falsch, heute ab 7) startet der
     Erkenner-Weg ohne Nummer **keinen** Lauf über die ganze Geschichte,
     sondern fragt in einem Satz nach der Szene
     (`kuerzung.TEXT_WELCHE_SZENE`). Das ist eine **vorläufige
     Voreinstellung, die Entscheidung liegt bei Birk**; der Knopf „Kürzer"
     unter der Kurzgeschichte ist davon nicht betroffen, und
     `prompts/erkenner.md` (Punkt 23, „der ganze Text, der zuletzt entstanden
     ist") blieb unverändert, damit kein neuer Korpuslauf fällig wird.
     Auf **„im Zweifel kein Eintrag"** kalibriert, wie `szene_schreiben` und
     `entfernen`: Kritik an der Länge („zu lang, was meint ihr", Korpusfall
     n20) feuert nicht, eine dauerhafte Längenvorgabe („höchstens eine Seite
     ab jetzt", fl04) bleibt `festlegung_setzen`, und aus einer **Aufnahme**
     gilt sie nie (`ARTEN_IN_AUFNAHME` bleibt bei drei). Korpus: `sk01`/`sk02`
     positiv, `sk03`–`sk05` negativ, plus
     `tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle`, der
     n20/n27/fl04 auf ihrem Sollwert festhält. **Der Erkenner-Korpuslauf
     gegen das echte Modell steht aus** (Birk, kostet Geld) — wie beim
     bestehenden Hinweis zu `festlegung_setzen` oben.
  3. **Schärfung und Szenenfolge laufen nie gleichzeitig**
     (`vorschlagssperre.py`, `nimm_oder_merke`). Wer die Sperre nicht bekommt,
     wird **gemerkt** und läuft nach der Freigabe automatisch — nicht
     abgewiesen. Das ist der Unterschied zum alten `szenenfolge._TEXT_BESETZT`,
     das den Auftrag verlor; die Konstante bleibt als Nutzertext stehen, hat
     aber keinen Aufrufer mehr. **Nehmen und Merken sind EIN atomarer Schritt**
     (`nimm_oder_merke`, Race-Fund): ein `nimm` gefolgt von einem separaten
     `merke` hätte ein Fenster offen gelassen, in dem ein gleichzeitiges
     `gib_frei` einen noch leeren Merkplatz leert und den kurz danach
     gemerkten Auftrag nie nachholt — `gib_frei` poppt den Merkplatz und gibt
     die Sperre unter demselben Schutz frei, `nimm_oder_merke` nimmt die
     Sperre oder legt den Auftrag unter demselben Schutz ab. Alle fünf
     Aufrufer (`schaerfung.starte`, die vier `szenenfolge.starte*`) nutzen
     `nimm_oder_merke` und geben die Sperre bei einer Exception vor dem
     Thread-Start selbst wieder frei. `schaerfung.starte` liefert dafür
     `GEMERKT` statt `None` — `None` heißt „es gab nichts anzustoßen", und
     `knoepfe.starte_schaerfung` spielt darauf die vorhandene Lage aus; die
     Zeile „Schärfung läuft, einen Moment" schickt der Knopf-Handler nur,
     wenn `vorschlagssperre.laeuft` beim Anstoßen noch `False` war — sonst
     schickt `schaerfung.starte` selbst `TEXT_GEMERKT`, und ein vorab
     gesendetes „gleich" wäre eine zweite, widersprüchliche Zeile im selben
     Chatfenster.
  4. **Die Richtungswahl speichert ihre Szenen mit**
     (`szenenfolge.szenen_in_zeile`, `szenen_der_richtung`, `lege_inline_an`).
     Ein Richtungs-Knopf trägt immer genau **eine** Zeile, und
     `zerlege_geschichte` liest Szenen erst ab Zeile 3 — nennt die Richtung
     ihre Szenen also im Satz („… Szene 1: Ankunft am Steg. Szene 2: …"),
     gingen Titel und Form verloren, und der Folge-Lauf erfand sie eine
     Minute später neu. `szenen_in_zeile` erkennt eng (mindestens zwei
     Anker, Nummern zusammenhängend ab 1, Form nur am Stückende, Titel bis
     `TITEL_MAX` = 80 Zeichen); Lücken oder Doppelungen in der Nummerierung
     hinterlassen den Vorfall `richtung_szenen_unvollstaendig`, statt still
     zu verwerfen — aber nur, wenn die Zeile keine Formwahl ist: eine
     Formabfolge mit Lücke geht in `_uebernimm_formwahl` und hinterlässt
     allein `geschichte_war_formwahl`. **Review-Fix (`c9af872`):** der Inline-Weg gilt darüber
     hinaus nur, wenn kein Titel mit einem Formwort beginnt und jede Form,
     die `formabfolge` in der Zeile findet, genau als Anhang eines dieser
     Titel steht (`szenenfolge.szenen_der_richtung`) — sonst bleibt es beim
     bisherigen `_uebernimm_formwahl`, das eine reine Formabfolge ohne
     eigene Titel sichert. Trifft der Inline-Weg zu, geht die Form in
     `szene.form` und nicht in `form_vorschlag` — die Gruppe hat gedrückt —,
     und `lege_inline_an` setzt dabei **nur eine leere** `form` (eine per
     Knopf schon bestätigte Form einer bestehenden Szene bleibt stehen, da
     `repo.setze_szenenfeld` `GESCHUETZTE_SZENENFELDER` nicht von sich aus
     beachtet). **Danach läuft kein `starte_geschichte_szenen` mehr:**
     `titel` steht nicht in `repo.GESCHUETZTE_SZENENFELDER`, ein frischer
     Vorschlag würde die Titel der Gruppe überschreiben und kostet gemessene
     110 s.
     **Eine bekannte Grenze, gemessen:** `if not alter_block: zeilen = []` in
     `knoepfe._speichere_geschichte` verwirft heute **nichts** (auf dem
     Menü-Weg ist der `wert` immer einzeilig) und bleibt für den
     `alter_block`-Weg stehen.
- **Ein Erkennerlauf ist mit einem Tipp zuruecknehmbar** (01.10.2026, Karte U,
  Birk 30.09.: "Die Tests vor dem Workshop bilden die echte Chatrealitaet der
  Studierenden nur begrenzt ab. Ein falsch gespeicherter Wert darf deshalb
  nicht STILL bleiben"). Unter **jeder** "Notiert:"-Meldung steht ein ruhiger
  Knopf "Rueckgaengig" (Padua: "Undo") als letzte Zeile der Tastatur -- die
  bestehende Grundleiste bleibt darueber, mobil gilt ein Hauptknopf je
  Bildschirm. Sieben Saetze, die zusammengehoeren:
  1. **Erfasst wird per DIFF, nicht per Nachbau je Art.** `erkenner.laufe`
     nimmt vor und nach `wende_an` einen Schnappschuss der verfolgten Tabellen
     (`ruecknahme.plan`, `repo.schnappschuss`); die Differenz sind die
     Schritte. Jede `_wende_*_an`-Funktion nachzubilden waere eine zweite
     Wahrheit, die beim naechsten Umbau still ausschert --
     `repo.fuehre_figur_zusammen` beruehrt drei Tabellen auf einmal,
     `korrigiere_transkripte` vier. Ein parametrisierter Test faehrt jede
     undo-faehige Art gegen die Spaetstand-Fixture und vergleicht den Dump
     (`tests/test_ruecknahme_rundreise.py`); ein zweiter prueft, dass jede von
     `wende_an` geschriebene Spalte verfolgt ist oder mit Grund in
     `AUSSEN_VOR` steht.
  2. **Eine Meldung, eine Ruecknahme** -- keine Einzelauswahl. Der Knopf traegt
     die `erkenner_lauf.id` im `wert` der Knopfzeile, `callback_data` bleibt
     `k:<id>` (Zusage 1), kein Modellaufruf im Handler (Zusage 2), idempotent
     doppelt: `repo.beanspruche_knopf` **und** ein bedingtes
     `UPDATE erkenner_lauf ... WHERE zurueckgenommen_am IS NULL` in derselben
     Transaktion (Zusage 3).
  3. **Weich statt hart** (N3): eine im Lauf angelegte Figur, Szene oder
     Festlegung bekommt `entfernt_am`; eine reine Verknuepfungszeile
     (`szene_figur`) wird geloescht, eine im Lauf geloeschte wieder
     eingefuegt; eine im Lauf entstandene `arbeitsstand`-Zeile wird
     **geleert**, nicht geloescht (sie traegt die Phasen-Buchhaltung).
     "Figur weg" heisst: kein Leser in `repo`/`web_daten` sieht sie mehr.
  4. **Alles oder nichts.** Stimmt EIN betroffener Wert nicht mehr mit dem
     Stand nach dem Lauf ueberein, oder zeigt inzwischen etwas Fremdes auf
     eine neu angelegte Figur/Szene (`ruecknahme.verweise()`, aus `db.SCHEMA`
     hergeleitet), wird **nichts** geaendert und die Gruppe bekommt einen Satz
     ("Seitdem geaendert -- bitte im Arbeitsstand korrigieren."). Ein halber
     Rueckschritt waere schlimmer als keiner.
  5. **Das Journal bleibt stehen** (nur-anhaengend): die Zeilen des Laufs
     werden nicht angefasst, die Ruecknahme haengt eine neue an
     (`quelle 'undo'`). Die Antwortzeile geht ausserdem als Bot-Zeile in
     `nachricht`, damit der Gespraechs-Bot im naechsten Zug nicht behauptet,
     der Wert stehe.
  6. **Kein Undo fuer die Phase und fuer die USA-Einwilligung.** Beide fallen
     automatisch heraus, weil `gruppe` und die Phasenspalten nicht verfolgt
     werden; ihre Zeilen stehen in der Meldung, aber nicht in "Rueckgaengig
     gemacht:". Die Einwilligung ist eine Datenschutzentscheidung mit eigenen
     zwei Knoepfen -- **offener Punkt fuer Birk**, nicht fuer diese Karte.
  7. **Nur die Erkenner-Meldung bekommt Undo.** Die Notiert-Zeilen aus
     Knopfdruecken (`knoepfe.basis._speichere`) und die Gruppenseite sind
     bewusste Handlungen der Gruppe an einem fixen Wert; dort hat sich keine
     Schicht geirrt, die man zurueckdrehen muesste. Nach einem wirksamen Undo
     werden die Grundleisten-Knoepfe derselben Nachricht verfallen gelassen,
     sonst schriebe "Ja, speichern" den gerade zurueckgenommenen Wert wieder
     (der Wert steckt im Knopf). Und eine ueberholte Leisten-Nachricht wird auf
     ihren Undo-Knopf **reduziert** statt ganz abgenommen: er ist der einzige
     Weg, ihren Wert zurueckzunehmen.

- **Die Laenge einer Szene waehlt der Code, nicht das Modell -- und nach dem
  Schreiben wird genau EINMAL nachgearbeitet** (30.09.2026, Karte R,
  `laengen.py` + `sprachpass.py` + `nachpass.py`, Befund
  `docs/padua-r-laengen-2026-09-30/BEFUND.md`). Der Anlass ist gemessen: am
  06.09.2026 hat Birk den Gruppentext vor dem Versand von Hand nachbearbeitet,
  zweimal in Richtungen, die eine Maschine haette gehen koennen. Erstens die
  Laenge -- das Textbuch v2 dieses Tages hatte 825 / 802 / 603 Woerter in drei
  **verschiedenen** Formen, also praktisch eine Laenge, weil
  `kurzgeschichte.ANWEISUNG` eine Gesamtlaenge nennt und sonst nichts. Zweitens
  die Sprache: Gedankenstrich-Inflation, "nicht X, sondern Y",
  Adjektiv-Trippel, Fazitsatz -- Muster, die `prompts/theater-tells.md`
  praeventiv verbietet und die trotzdem dastanden.
  Seitdem, **nur bei aktivem Profil** (`[laengen] aktiv = false` im Vorgabeprofil
  und in Dortmund): der Code wuerfelt je Gruppe ein **Rhythmus-Muster**
  (`kurz-lang-kurz`, `lang-kurz-schlag`, ...) und liest es **zyklisch** ueber
  die Szenennummern -- zyklisch und nicht ueber die Gesamtzahl verteilt, weil
  eine spaeter eingefuegte Szene sonst das Budget einer frueheren verschiebt
  und das Nachzaehlen gegen eine andere Zahl rechnet als der Lauf. Der Seed
  **ist die `chat_id`**: kein `random`, kein gespeicherter Wert, und trotzdem
  bekommt dieselbe Gruppe immer dasselbe Muster. Eine Journalzeile
  (`laengen.journalzeile`) haelt Seed, Muster, Faktor und Budgets fest, damit
  ein Mensch es nachrechnen kann.
  Das Budget geht **je Szene** in den nie gekuerzten Teil des Szenen-Prompts
  (`szene._REIHENFOLGE`, `"laenge"` direkt hinter `"aufgabe"` -- eine Laenge,
  die die Kuerzungsleiter wegwerfen darf, ist keine) und **als Liste plus
  Summe** in den Prosa-Prompt; dort **ersetzt** die Summe die feste Zeile
  `kurzgeschichte.ZEILE_GESAMTLAENGE`, statt sie zu ergaenzen (ein Fakt hat
  genau eine Stelle im Prompt). **In Phase 6 greift ein Budget je Form
  sehr wohl**, obwohl `szene.form` dort meist NULL ist: die Szenenfolge steht
  beim Eintritt fest (`phasen.voraussetzungen`), `formen/prosa.md` erklaert sie
  fuer verbindlich, und `laengen.form_der_szene` liest **bestaetigt vor
  vorgeschlagen vor Profilvorgabe**. Gelesen, nicht geschrieben: `szene.form`
  bestaetigt weiter allein die Gruppe.
  **Die Gruppe uebersteuert auf zwei Wegen, beide vorhanden.** "Kuerzer (25 %)"
  unter der **ganzen** Geschichte merkt seinen Faktor dauerhaft
  (`arbeitsstand.laengen_faktor`, additiv ueber `db._migriere_fehlende_spalten`,
  gesetzt in `kuerzung.starte`) -- damit werden auch die Szenen, die es noch
  nicht gibt, kuerzer **geplant** statt erst geschrieben und dann gekuerzt.
  "Kuerzer" unter **einer** Szene tut das bewusst nicht: eine Entscheidung
  ueber eine Szene ist keine ueber alle. Und eine ausdrueckliche Laengenansage
  ("hoechstens eine Seite pro Szene ab jetzt") **deckelt** das Budget --
  gelesen aus `festlegung` im Bereich `stil` (`laengen.woerter_aus_festlegungen`),
  wohin `prompts/erkenner.md` Punkt 23 sie ausdruecklich weist (Korpusfall
  `fl04`). **Keine neue Erkenner-Art**, also kein weiterer bezahlter
  Korpuslauf.
  **Nachgearbeitet wird genau einmal, und das ist gebaut, nicht abgesprochen.**
  `nachpass.nach_szene` bzw. `nach_geschichte` laeuft am Ende von
  `szene._lauf` bzw. `kurzgeschichte._lauf` -- **im schon laufenden Thread und
  unter dessen Sperre**, deshalb `szene.schreibe`/`kurzgeschichte.hole_text`
  und nie `starte` (die Sperre liegt). Nachzaehlen (ab
  `nachzaehl_schwelle` = 130 % des Budgets) und Sprachpass ergeben **eine**
  Regie-Notiz und **einen** Lauf -- waeren es zwei Wege, waeren es bis zu zwei
  Laeufe je Szene. Bleibt das Ergebnis ueber dem Budget, gibt es einen
  **Vorfall** (`nachpass_reicht_nicht`) und **keinen zweiten Lauf**: ein
  Modell, das zweimal zu lang schreibt, schreibt es beim dritten Mal auch
  (dieselbe Begruendung wie bei `ablauf.echo_wiederholt`). In Phase 6 ist es
  **ein** Lauf fuer **alle** Abschnitte.
  **Der Zitatschutz ist die wichtigste einzelne Massnahme dieses Pfades.** Ein
  Ueberarbeitungslauf, der einen woertlichen Interviewsatz glattzieht, nimmt
  der Gruppe genau das, was sie selbst gesammelt hat (`theater-tells` Nr. 21,
  25, 28). Geprueft wird mit `zitat.pruefe` -- **keine zweite, strengere
  Normalisierung**, dieselbe Funktion wie bei Verdichter, Kernzitaten,
  Sprachprofil, Schaerfung und Dramaturgie. Geht ein Zitat verloren, wird das
  Ergebnis **verworfen**: in Phase 7 wird die alte Fassung zurueckgeschrieben
  (`repo.aktualisiere_szene`; die Fassungszeile des Laufs bleibt in
  `szenenfassung` stehen -- nur anhaengen, nie loeschen), in Phase 6 wird gar
  nichts gespeichert, weil `kurzgeschichte.hole_text` die Antwort vor dem
  Speichern liefert. Dort haengt an derselben Stelle die zweite Wache: eine
  **geaenderte Abschnittszahl** wird verworfen, weil `lege_szenen_an`
  ergaenzend abgleicht und zwei Abschnitte sonst ihren alten, langen Text
  behielten.
  **Die Gruppe erfaehrt von all dem nichts.** Der Nachpass ist eine Zugabe:
  sie hat ihren Text, sie wartet nicht darauf, sie kann nichts tun. Ein
  gescheiterter Nachpass ist deshalb unsichtbar und bekommt einen Vorfall
  (SPEC § 11.1). Kosten und Aufrufe landen in `aufruf` mit eigener `art`
  (`szene_nachpass`, `kurzgeschichte_nachpass`) -- wie bei `dramaturgie_b1`,
  damit Dashboard und Kostenzeile den Weg getrennt sehen.
  **Bekannte Grenzen:** die Rahmenwerte in `[laengen.rahmen]` sind
  **Vorschlaege und ungemessen** (Chor/Lied 80-200, Rap 120-250, Dialog
  200-450, Monolog 150-350) und liegen bereits bei etwa einem Viertel des
  Herkules-Masses -- ob sie der Normalfall oder schon die Instagram-Laenge
  sind, entscheidet Birk (Befund Abschnitt 1). `zitat.pruefe` glaettet
  Whitespace und typografische Anfuehrungszeichen, ein Zitat bleibt also
  woertlich und nicht byte-genau erhalten. Und `scripts/laengen_probe.py` ist
  der **kostenlose** Nachweis dieses Pfades: die Simulation erreicht Phase 7
  und den Kuerzungsweg nicht.

- **Fuenf Franken je Gruppe und Tag, dann pausiert der Bot** (30.09.2026,
  Karte Padua S, `kosten.py`). Der Deckel steht **im Bot-Prozess** und nicht
  im Webserver: beide Kanaele laufen durch denselben `ablauf`/`aufnahme`-Code,
  nur mit einem anderen `tg`-Objekt, und ein Deckel im Webserver saehe die
  Telegram-Gruppen nicht. Drei Durchsetzungsstellen, alle **vor** dem
  Netzaufruf: `llm.LLM._anfrage` (jeder Infomaniak-Aufruf geht durch sie),
  `szene_claude.prosa` und `aufnahme._verarbeite` (der einzige Weg zu
  `stt.transkribiere`). `chat_id is None` zaehlt nie mit — das Warmlaufen und
  die Pruefskripte laufen ohne Gruppe.
  **Gerechnet wird beim Buchen, nicht beim Lesen.** `aufruf` trug bis dahin
  weder Modell noch Kosten, und nachtraeglich ging es auch nicht: aus
  `aufruf.art` folgt das Modell nicht, `LLM.schema` waehlt es je Aufruf.
  Seitdem: `aufruf.modell` und `aufruf.kosten_chf`, additiv migriert (alte
  Zeilen NULL = 0). Whisper bucht mit (`art='stt'`, Kosten aus
  `aufnahme.dauer_sekunden` mal `kosten.WHISPER_CHF_JE_MINUTE`); der
  Claude-Proxy bucht **0 CHF, weil Abo** — der Wert steht an **einer** Stelle
  (`kosten.CLAUDE_CHF_JE_AUFRUF`), damit aus dem Abo eine Abrechnung werden
  kann, ohne dass jemand sucht. Ein Modell, das nicht in
  `kosten.PREISE_CHF_JE_MIO_TOKEN` steht, wird mit dem **teuersten** Preis
  gebucht plus Vorfall `kosten_modell_unbekannt`: mit 0 umginge der naechste
  Modellwechsel den Deckel, ohne dass es jemand merkt.
  **Pausieren heisst: Empfangen geht weiter** — dieselbe Trennung wie in
  § 1 der SPEC. Nachrichten und Audio werden gespeichert, Slash-Befehle und
  Knopf-Handler laufen (sie rufen ohnehin kein Modell), die Gruppenseite
  bleibt lesbar und beschreibbar. Nur Modellaufrufe fallen aus. Eine Aufnahme
  bleibt auf `status='empfangen'`, und der **vorhandene** Nachhol-Arbeiter
  greift sie nach Mitternacht auf (`repo.offene_aufnahmen_fuer_bot` liefert
  alles ausserhalb von fertig/fehlgeschlagen/laeuft, alle 60 s) — kein neuer
  Mechanismus. **Ausdruecklich nicht** ueber `_melde_transkriptionsfehler`:
  das zaehlt `repo.zaehle_versuch_hoch` hoch, und bei 60 s Nachholintervall
  waeren `MAX_VERSUCHE` in fuenf Minuten verbraucht — jedes Interview des
  Abends stuende am naechsten Morgen auf `fehlgeschlagen`.
  Die Gruppe bekommt **eine** Meldung, danach hoechstens alle 15 Minuten
  (Merkposten `gruppe.kostenpause_gemeldet_am` — in der Datenbank, weil ein
  Neustart sonst sofort wieder meldet), plus **einen** Vorfall je Tag.
  Erkenner und Journal fallen still aus, das Wasserzeichen bleibt stehen.
  Der Text nennt **keinen Betrag**: eine Zahl, die der Betreiber setzt, sagt
  einer Theatergruppe nichts darueber, was sie tun soll. Env:
  `IT_KOSTEN_DECKEL_CHF` (Vorgabe 5.0), `IT_ZEITZONE` (Vorgabe Europe/Rome).
  **Zwei bekannte Grenzen, gemessen:** Sprachprofil (`sprachprofil.py`) und
  Nachpass (`nachpass.py`) rufen ebenfalls ueber `klm.schema` und haengen
  damit hinter derselben `llm.LLM._anfrage` -- waehrend der Pause scheitert
  also auch ihr Aufruf, aber ohne eigene Pausenmeldung: ihr Fangnetz ist ein
  gewoehnliches `except Exception` mit `log.exception`, nicht
  `kosten.melde_pause_wenn_deckel`, und ein Fehlschlag sieht fuer die Gruppe
  aus wie jeder andere. Und der Erkenner laeuft waehrend der Pause
  unveraendert **je Nachricht** weiter und scheitert jedesmal an
  `kosten.pruefe` -- jeder Lauf schreibt einen eigenen Vorfall
  `extraktor_fehler` (`erkenner.py`), ungedrosselt im Unterschied zur
  Pausenmeldung selbst: bei einer aktiven Gruppe fuellt sich das Dashboard
  mit gleichlautenden Vorfaellen, statt der einen Zeile, die der Deckel
  eigentlich verspricht.

- **Prüflauf vor jeder Anzeige, Phasen 6/7 für Padua** (03.10.2026, Padua
  Phasen TEIL 2; nur mit `[prueflauf] aktiv`/`[ueberarbeitung] aktiv`, beide
  nur in `workshop/padua-2026/profil.toml`). Birks Entscheidungen: höchstens
  zwei Runden (`schleife.RUNDEN_MAX`); fällt ein Score, bricht der Lauf ab
  und die **bessere** Fassung bleibt (`behalte_bessere=True` über
  `schleife.schnappschuss`/`stelle_wieder_her`); wer ein geprüftes
  Interviewzitat verliert (`sprachpass.verlorene`), wird verworfen; danach
  der Sprachpass (`nachpass`); an die Gruppe **höchstens drei Zeilen**
  (`prueflauf.ZEILEN_MAX`), nie der Volltext (Web: Script-Tab, Telegram:
  Link, `knoepfe.skript_verweis`); „Show first draft" (`ART_ERSTENTWURF`)
  zeigt auf die Fassung vor der Prüfung (`szene.erstentwurf_fassung`).
  **`zeigen=False`**, weil `szene.schreibe`/`kurzgeschichte.schreibe` ihren
  Text posteten, bevor eine Prüfung laufen konnte: `_lauf` schreibt jetzt
  still, prüft **unter der eigenen Sperre**, zeigt danach
  (`zeige_geprueft_szene`/`_geschichte`) und streamt nicht — der Strom
  zeigte sonst den ungeprüften Entwurf. **Fragen je Objekt:** Geschichte
  A2/A6/A9/A11, Prosaszene B1/A10, Bühnenszene A10/C1 (`fanout.pruefe(...,
  fragen, szenen, mechanik=False)`); „Formregeln" = A10 ab Phase 7
  (`fanout.A10_FORM_AB_PHASE`). **A10 in beiden Richtungen:** bei
  `richtung=parameter` folgt die Planung dem Text (Journal + eine Zeile),
  die Ausnahme vom „Vorschlag" in `fanout.parameterkorrektur` — **nie** für
  `repo.GESCHUETZTE_SZENENFELDER`: Form und Stil setzt die Gruppe (Birk 7.1).
  **Ablauf** (`ueberarbeitung.weiter_6`/`weiter_7`): Phase 6 prüft die Prosa
  aus 5, statt sie neu zu schreiben — erst das Ganze, dann Szene für Szene,
  nach der letzten Abnahme automatisch Phase 7 (die Gruppe hat gedrückt, wie
  am Ende von 5). Phase 7: Formen per Nummer in **einer** Antwort,
  Sprechweisen (`sprechweise.py`), Szene für Szene, zuletzt `starte_schluss`
  (Prüflauf übers Textbuch, dann `stueckpruefung` — nicht mehr beim
  Eintritt; lief sie nie, holt der Wiedereintritt sie nach). **Chat wirkt,
  wo Knöpfe wirken** (Flow-Audit B1/B2): fünf Arten in
  `erkenner.PHASEN_SPEZIFISCHE_ARTEN` plus Spalte `PROFILSCHALTER_DER_ARTEN`,
  nur im **englischen** Prompt; `arten_fuer_schema()` lässt Dortmunds Enum
  bei 27. Während eines Laufs kommt die „still running"-Zeile wie beim Knopf;
  ein „Noted…" aus dem Gesprächszug wird in 6/7 verworfen
  (`ablauf.ist_erfundenes_notiert`). **Gemessen:** Tabelle `prueflauf`, eine
  Zeile je Lauf (`runden`, `auftraege_je_runde`, `zweite_runde_mit_auftraegen`,
  `dauer_ms`), Basis für `RUNDEN_MAX`. **Grenzen:** ohne gültigen Richter
  (gleiches Modell ohne `IT_JUDGE_MODELL`, USA verneint) keine Prüfung, und
  der Betreiberhinweis steht im Hinweis an die Gruppe; ein Rücksprung nach 5
  setzt die Abnahmen aus 6 nicht zurück (offen, Birk). Mehr: „Was bewusst fehlt".

- **Phase 1 hört seit 04.10.2026 laufend mit, wie Phase 4** (Karte
  t_4517d4ad, Birk 15:15: „Phase 1 und 4 laufen einheitlich automatisch").
  Die Hintergrund-Diskussion der Phase 1 speist über `begriffsboard.py` ein
  laufendes Begriffsboard: derselbe Auslöser wie beim Brainstorm der Phase 4
  (`brainstorm.soll_reagieren`, unverändert), eigene Zähler nur über
  `aufnahme`-Zeilen mit `diskussion = 1`, ein Schema-Aufruf je
  qualifizierendem Segment im eigenen Thread. **Kein `tg`** im Boardlauf —
  strukturell keine Chatzeile beim Mithören, wie beim Brainstorm kein
  Gesprächszug und kein Erkenner-Lauf auf dieser Nachricht. Validiert wird im
  Code (Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`), die
  Tabelle `begriffsboard` nur anhängend. **Das Mithören hat nur Start und
  Fertig** — der Pause-Knopf (`#diskussion-pause`,
  `pausiereDiskussion`/`fortsetzeDiskussion`) ist seit dem 04.10.2026
  entfernt; er setzte bis dahin ebenfalls den Ende-Schnitt und löste damit
  bei jeder Pause Vorschlag und Verdichtung aus. Die Interview-Pause bleibt;
  Brainstorm kennt seit dem Toggle-Umbau (t_cf87ee0a) keinen Pausenschnitt
  mehr, nur noch den 90-Sekunden-Deckel (`grund='cap'`) und das Ende über den
  Toggle-Stopp.

  **Belegpflicht der Begründung** (Karte t_2b9d2cbe, 04.10.2026): eine
  `begruendung` gilt nur, wenn ein geprüftes Zitat sie trägt, das nach Abzug
  von Begriff, Ansage-Formel (DE+EN samt STT-Varianten „Gepäck"/„Betreff"),
  Meta- und Stoppwörtern noch mindestens zwei Inhaltswörter hat, und wenn sie
  kein Füllsatz ist („wird genannt/gesammelt", „came up"); sonst wird sie
  leer. Die Wortlisten gelten für DE und EN zugleich, weil Kimi unter dem
  EN-Profil deutsch begründete. Leer ist gültig -- `detail_zeilen` lässt solche
  Einträge weg, in die Phase-2-Prompts geht nur Belegtes. Merge- und
  STT-Spuren gehören nicht in die Begründung (Prompt). Gemessen:
  `docs/begriffsboard-inhalt/BERICHT.md`, Messskript
  `scripts/rauchtest_begriffsboard_inhalt.py` (kein Test, kostet Geld; `live`
  nur read-only und nie an Opus).

  Bei „Discussion done" schlägt der
  Bot die Top 5 mit EINEM Knopf „Take these" vor. **Seit 05.10.2026 läuft
  am Ende-Schnitt immer ein Lauf, sobald ungelesenes Transkript da ist**
  (Birk nach dem Live-Test: 298 Zeichen, kein Lauf; ersetzt die Regel vom
  04.10.2026 14:50, unter der der Ende-Schnitt an `min_zeichen` hing) —
  Zwischenläufe behalten ihre (seit 05.10. eigenen) Schwellen; läuft gerade
  ein Lauf, wird nach ihm neu entschieden (`merke_falls_laeuft`); bleibt das
  Board leer, kommt `aufnahme._TEXT_DISKUSSION_KEINE_BEGRIFFE` statt
  „schickt mir fünf". **Was im CoThinker steht, ist gespeichert**
  (05.10.2026, Auto-Speichern der Top 5, siehe `begriffsboard.py`-Zeile oben).
  **Eine Begriffs-Korrektur wechselt nie die Phase** (Birk 05.10.2026 ~10:50,
  Padua, unter `workshop.autosave_phase1_2_aktiv`): jeder Speicherweg der
  Begriffe in Phase 1 — Vorschlagsblock im Gesprächszug
  (`knoepfe.basis._korrigiere_begriffe`; `offene_art` hält `begriffe` dafür in
  Phase 1 offen, auch wenn sie stehen), Erkenner `begriffe_setzen`
  (`erkenner._sende_meldung`), „Take these" (`basis._speichere`) — endet in
  `basis.biete_begriffe_aktualisiert`: „Updated – saved:" + nummerierte Liste
  + „Move on?" mit „Yes, on to the questions" · „Change something" · Undo der
  Korrektur, beliebig oft, die vorige Frage behält nur ihr Undo. Weiter geht
  es nur auf ausdrücklichen Wunsch: Knopf oder Freitext (Erkenner
  `phase_setzen`; in Phase 1 gilt auch eines ohne wirksame Nummer als
  „weiter", `erkenner._weiter_aus_phase_1`). Ersetzt für Padua den
  automatischen Sprung des Autosave (P1-2) und die B5-Abschlussnachricht am
  Erkenner-Weg. Test: `tests/test_begriffe_korrektur_bleibt.py`.
  und **der Chat weiß, was mitgehört wurde und auf dem Board steht**
  (`kontext`-Blöcke `board`/`mitgehoert`, EN-Systemanweisung);
  `begriffsboard.schreibe_detail`
  füllt `arbeitsstand.begriffe_detail` auf jedem Schreibweg von `begriffe`
  und geht von dort nach Phase 2 und ab Phase 4 in den Prompt
  (`kontext.baue`) sowie in den isolierten `fragen_ki`-Aufruf. **Der
  CoThinker-Tab zeigt seitdem auch Phase 1**: bisher nur in Phase 4 sichtbar
  (die Brainstorm-Karten), rendert `teil/buehne` dort jetzt das
  Begriffsboard, sobald `workshop.diskussion_aktiv()` gilt — im Markup am Attribut
  `#roadmap[data-begriffsboard]`, im Client an `istCoThinkerPhase()`, das den
  bisherigen Early-Return `if (!istPhase4())` in `ladeBuehne` (und die drei
  anderen Phase-4-Weichen) für Phase 1 passieren lässt. Nur funktionales
  Markup (`data-*`, `<details>` für Begründung/Doppelbedeutung), keine
  Gestaltung — wie beim Rest des Boards.

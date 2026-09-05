# Analyse Workshop-Tag 1 — 05.09.2026

Auswertung des ersten echten Workshoptags (Dortmund, Migrantinnenverein, drei
Kleingruppen junger Frauen 15–18, 13:30–18:00) plus Birks Testlauf ab 19:00 in
einer vierten Gruppe. Grundlage: `betrieb/soap.db`, `betrieb/test.db`,
`betrieb/gruppe1..4.log`, `betrieb/web.log`, Code auf `main` HEAD `6bc40aa`.

**Datenschutz:** Diese Analyse enthält keine Nachrichtentexte, keine
Transkripte und keine Belegzitate der Teilnehmerinnen. Alle Aussagen über
Inhalte stammen aus Aggregaten, aus Bot-Systemtexten (stehen ohnehin im Code)
oder aus der Testgruppe, in der nur Birk geschrieben hat. Figurennamen der
Testgruppe sind erfunden.

Alle Uhrzeiten lokal (CEST). Read-only ausgewertet, nichts verändert.

---

## 0. Der Tag in Zahlen

Ausgerollt wurden heute im laufenden Betrieb rund 70 Commits, davon ~15
während des Workshops selbst (Inline-Knöpfe 12:46, Aufnahme-Knopf 14:00,
Slash-Bewerbung raus 14:38, Speicher-Leiste 15:59, Phase-4-Sperre 15:59,
Nachrichtenteilung 17:11, Grundleiste/Figuren-Ebenen 18:15, Prompt-Eigennamen
raus 20:00).

Gesamt über alle vier Gruppen:

- 174 Nachrichten (65 Mensch, 109 Bot), Verhältnis Bot:Mensch 1,68
- 7 Sprachnachrichten, 20 angelegte Aufnahmen, davon **13 leer entfernt** (65 %)
- 4 Interviews mit Transkript, 4 Verdichtungen, 29 Kernthemen mit Belegzitat,
  **28 davon geprüft** (1 `zitat_ungeprueft`, Quote 96,6 %)
- 166 Knopfangebote, 61 gedrückt (37 %)
- 13 Journaleinträge, davon 12 in der Testgruppe
- 149 Modellaufrufe (86 Erkenner, 57 Gespräch, 5 Verdichter, 3 Sprachprofil,
  1 Szenenfolge), ein einziger Fehlschlag
- rund 1,05 Mio. Prompt-Token, 23 000 Antwort-Token

Die harte Zahl des Tages: **die drei echten Gruppen kamen bis Phase 3
(Interviews). Kernthema, Figuren, Format, Rahmen: nichts davon steht in der
Datenbank.** Die Testgruppe kam allein bis Phase 6 — mit einem Bot, der ab
18:15 andere Knöpfe hatte als der, mit dem die Mädchen gearbeitet haben.

---

## 1. Verlauf je Gruppe, mechanisch

### Gruppe 1 (`-5143986099`, `theatersoap1_bot`)

- Erste Nachricht 15:15, letzte inhaltliche 16:33; danach nur noch der
  Neustart-Anstoß um 18:39. Lücken > 15 min: 15:15→15:41 (26 min),
  16:33→18:39 (126 min).
- 44 Nachrichten: 17 Mensch (14 Text, 2 Sprache, 1 sonstiges), 27 Bot
  (25 Text, 2 Transkript-Echo). Verhältnis 1,59.
- Bot-Textlänge: Median **392 Zeichen**, Maximum 1108, vier Nachrichten
  über 700, keine über 4000. Soll (< 700 Median) eingehalten.
- Sprachnachrichten: 2, Gesamtdauer 267 s (ein Interview mit 4:26 min).
- Aufnahmen: 6 angelegt, **3 leere „lang"-Köpfe entfernt**, 1 Interview mit
  2413 Zeichen Transkript, 1 Verdichtung, 11 Kernthemen, alle 11 Zitate
  geprüft (100 %).
- Arbeitsstand: Begriffe (30 Zeichen), Fragen (883 Zeichen), **Phase NULL**,
  kein Kernthema, keine Figuren, kein Format, kein Rahmen. Letzte Änderung
  16:09.
- Journal: 1 Eintrag (`entschieden`, Quelle `knopf`).
- Knöpfe: 21 angeboten, 8 gedrückt. Nach Art: `aufnahme` 8/7, `speichern` 1/1,
  `anders` 1/0, `phase` **6/0**, `auswerten` 2/0, `auswerten_alle` 1/0,
  `stand` 1/0, `hilfe` 1/0.
- Vorfälle: keine.
- Aufrufe: Erkenner 16 (⌀ 1274 ms), Gespräch 14 (⌀ 2802 ms, max 9406 ms),
  Verdichter 2 (⌀ 5952 ms). Keine Fehlschläge. 260 k Prompt-Token.
- Log: 4 × HTTP 409 (Doppelprozess vor dem Workshop, morgens), 6 × HTTP 403
  bei `sendMessage` (Bot war noch nicht/nicht mehr in der Gruppe), 2 × 400,
  1 × 502, 20 Tracebacks — alle vor dem Workshop oder aus dem Testlauf.

### Gruppe 2 (`-5552492879`, `theatersoap2_bot`)

- 15:14 bis 17:08. Lücken: 15:14→15:43 (29 min), 16:18→16:34 (16 min).
- 61 Nachrichten: 25 Mensch (23 Text, 1 Sprache, 1 sonstiges), 36 Bot.
  Verhältnis 1,44 — die gesprächigste Gruppe.
- Bot-Textlänge Median **448**, Max 1588, sieben über 700.
- 1 Sprachnachricht, 685 s (11:25 min) — das längste Interview des Tages,
  7957 Zeichen Transkript. Genau daran ist um 17:11 der Fix
  „lange Nachrichten teilen" entstanden: das Teil-Transkript kam als
  HTTP 400 nie an (3 × `sendMessage` 400 im Log, dazu die Fehler
  „Leiste unter dem Teil-Echo fehlgeschlagen" und „Nachricht an die Gruppe
  fehlgeschlagen").
- Aufnahmen: 4 angelegt, 2 leer entfernt, 1 Interview, 1 Verdichtung,
  4 Kernthemen — **1 Zitat fiel durch** (der einzige `zitat_ungeprueft` des
  Tages, Quote 80 %).
- Arbeitsstand: Begriffe (42 Z.), Fragen (789 Z.), **Phase NULL**, sonst leer.
  Letzte Änderung 16:48.
- Journal: **0 Einträge**.
- Knöpfe: 14 angeboten, 7 gedrückt. `aufnahme` 6/5, `anders` 1/1,
  `speichern` 1/0, `phase` **3/0**, `auswerten` 1/0, `teil_weiter` 1/0,
  `teil_fertig` 1/0.
- Aufrufe: Erkenner 24 (⌀ 1351 ms), Gespräch 23 (⌀ 1896 ms), Verdichter 2
  (⌀ 9107 ms). Keine Fehlschläge. 434 k Prompt-Token — die teuerste Gruppe.

### Gruppe 3 (`-5339679310`, `theatersoap3_bot`)

- 15:15 bis 16:50. Lücken: 15:15→15:55 (41 min), 16:12→16:36 (24 min).
- 47 Nachrichten: 17 Mensch, 30 Bot. Verhältnis 1,76.
- Bot-Textlänge Median **259** (die kürzeste), Max 1006.
- 2 Sprachnachrichten, 334 s. 1 Interview, 3884 Zeichen Transkript,
  1 Verdichtung, 3 Kernthemen, alle geprüft.
- Aufnahmen: 10 angelegt, **7 leer entfernt**. Zwischen 16:39:32 und 16:41:05
  wurde der Aufnahme-Knopf **14-mal in 93 Sekunden** gedrückt, abwechselnd
  „starten"/„beenden", median 2,5 s Abstand. Das ist kein Interview, das ist
  Ausprobieren — und es erzeugte sieben leere Aufnahmen.
- Arbeitsstand: Begriffe (37 Z.), Fragen (240 Z. — die dünnste Frageliste),
  **Phase NULL**, sonst leer.
- Journal: **0 Einträge**.
- Knöpfe: 29 angeboten, 14 gedrückt. `aufnahme` 16/14, `phase` **8/0**,
  `auswerten` 1/0, `stand` 1/0, `hilfe` 1/0.
- Aufrufe: Erkenner 15 (⌀ 935 ms), Gespräch 13 (⌀ 2607 ms, **max 13 709 ms**
  — der Latenz-Ausreißer des Tages), Verdichter 1. Keine Fehlschläge.
- Log: sauberste Datei, 0 Tracebacks, 1 × 502 bei `getUpdates`.

### Testgruppe (`-5257292234`, `theatersoap_testbot`, Birk allein)

- 17:59 Begrüßung, dann 19:10–19:54 der eigentliche Durchgang. Lücke
  19:23→19:54 (30 min, der hängende Szenenfolge-Lauf).
- 22 Nachrichten: 6 Mensch, 16 Bot. Verhältnis 2,67.
- Bot-Textlänge Median **202**, Max 982. Bot-Antwortlatenz median 3 s, max 4 s.
- Keine eigenen Aufnahmen (die sechs Aufnahmezeilen sind die kopierten aus
  Gruppe 1); gearbeitet wurde auf einem übernommenen Interviewbestand.
- Erreichte Phase: **6 (Szenen)**. Arbeitsstand vollständig bis auf
  `kernthema_richtung` und `hauptkonflikt`: Kernthema (194 Z.), Format
  („Urban Dance Tanztheater"), Rahmen (64 Z.), Figuren-Entwurf (270 Z.,
  3 Zeilen), `figuren_fixiert_am` 19:15.
- 3 Figuren (Mira, Amir, Freundin), alle drei mit Sprachprofil (167/216/336
  Zeichen, 3–5 Zeilen) und Quell-Interview. 3 Sprachprofil-Aufrufe, je
  ~2,7 s, alle erfolgreich.
- 0 Szenen.
- Journal: 12 Einträge, alle `entschieden` — 8 aus `knopf`, 3 aus
  `sprachprofil`, 1 aus `erkenner`.
- Knöpfe: 46 angeboten, 25 gedrückt (54 %). Druck-Latenz median 81 s.
- Vorfälle: `abgeschnitten` und `szenenfolge_fehlgeschlagen`, beide 19:54.
- Aufrufe: Erkenner 6, Gespräch 7, Sprachprofil 3, **Szenenfolge 1
  fehlgeschlagen** (28 254 ms, `finish_reason: length`, 4000 Antwort-Token
  komplett im Reasoning verbraucht). Fix drei Minuten später als `960f12a`
  (60 000 Token, 300 s) — der Lauf selbst wurde nicht wiederholt.

---

## 2. Memory-Management

### Zahlen

- Zustimmungsverlust-Proxy (kurze Mensch-Nachricht ≤ 40 Zeichen, kein
  Journaleintrag ± 60 s): **G1 9 von 13, G2 15 von 15, G3 8 von 8,
  Test 1 von 5.** In den echten Gruppen also 32 von 36 kurzen Äußerungen
  ohne Spur im Journal.
- Bot-Nachrichten mit „Notiert:"-Zeile gegen tatsächliche Journaleinträge:
  G1 5 gegen 1, G2 10 gegen 0, G3 4 gegen 0, Test 3 gegen 12.
- Journalquellen: `knopf` 9, `sprachprofil` 3, `erkenner` 1, **`journal`
  (Extraktor) 0** — der Journal-Extraktor lief den ganzen Tag kein einziges
  Mal, weil kein Gespräch groß genug für eine Verdrängung wurde.
- Vorfälle `kuerzung` / `fenster_verworfen`: **0**. Das Kontextfenster war
  nie eng; die größte Gruppe kam auf 434 k Prompt-Token verteilt auf 49
  Aufrufe, also ~8,9 k je Aufruf.
- Gespeicherte Arbeitsstandfelder: in allen drei echten Gruppen genau zwei
  (`begriffe`, `fragen`). Beide über die Speicher-Leiste bzw. den Erkenner.
- Wiederholte identische „Notiert: Fragen: …"-Nachrichten: G2 **7-mal
  wortgleich**, G1 4-mal, G3 2-mal.

### Befund

**Das Speichern funktioniert genau dort, wo ein Knopf es trägt — und nirgends
sonst.** Von 13 Journaleinträgen kamen 9 aus einem Knopfdruck und genau einer
aus dem Erkenner. Die zentrale Beobachtung aus `AGENTS.md` („der Erkenner
sieht nur ein Fenster von 1–3 Nachrichten") ist heute im Feld bestätigt
worden, und zwar deutlicher als in der Simulation: in Gruppe 2 mit 25
Mensch-Nachrichten und 10 „Notiert:"-Zeilen des Bots steht **null** im
Journal.

Die Diskrepanz „Notiert:"-Zeile gegen Journaleintrag ist dabei kein Fehler im
strengen Sinn — die Notiert-Zeile meldet einen Arbeitsstand-Schreibvorgang,
das Journal ist ein anderer Kanal. Aber für die Gruppe sieht beides gleich
aus, und für die Auswertung ist ein Tag mit 65 Mensch-Nachrichten und 13
Journalzeilen praktisch blind. Die siebenfache Wiederholung derselben
„Notiert: Fragen: …"-Nachricht in Gruppe 2 zeigt zusätzlich, dass ein
`fragen_setzen` bei jeder Zustimmung neu geschrieben und neu gemeldet wird,
statt einmal — für die Gruppe liest sich das, als hätte der Bot vergessen,
was er zwei Minuten vorher schon notiert hat.

**Der Journal-Extraktor ist heute nicht gelaufen.** `SCHWELLE_VERDRAENGUNG =
2000` ist bei Gesprächen dieser Länge unerreichbar. Das heißt: der eine Pfad,
der Verworfenes und Vorschläge in der Schwebe festhalten sollte, existierte
den ganzen Tag über nur auf dem Papier. Kein `vorgeschlagen`-Eintrag im
ganzen Datenbestand.

**Die Phase wurde in keiner echten Gruppe je gesetzt** (`arbeitsstand.phase
IS NULL`), obwohl alle drei Interviews geführt haben — also faktisch in
Phase 3 waren, während der Code sie als Phase 1 behandelte. Damit lief den
ganzen Nachmittag `phasen/1.md` als Fokus-Prompt, in einer Situation, für die
`phasen/3.md` geschrieben war. Der Phasen-Knopf wurde 17-mal angeboten und
**0-mal gedrückt**.

Das Journal liest sich, wo es existiert (Testgruppe), gut: „Begriffe: …",
„Figuren: Mira, Amir, Freundin", „Format: Urban Dance Tanztheater
(festgelegt)", „Sprachprofil für Mira aus Interview 1" — selbsterklärend,
keine Pronomen, ohne Kontext verständlich. Das Entwurfsziel ist erreicht; es
gibt nur zu wenig davon. Ein Doppeleintrag ist zu sehen: „Rahmen: …" steht
zweimal wortgleich (19:22 und 19:53), weil derselbe Wert über zwei
verschiedene Knopfleisten gespeichert wurde.

### Vorschläge

1. **Phase mit dem ersten Interview mitschreiben — als Angebot mit Knopf, das
   stehen bleibt.** Nicht der verworfene automatische Sprung, sondern: sobald
   `aufnahme.lege_aufnahme_an` das erste Interview eines Chats anlegt und
   `arbeitsstand.phase IS NULL` ist, geht **eine** Nachricht raus: „Ihr seid
   bei den Interviews — soll ich das als Phase 3 festhalten?" mit einem
   einzigen Knopf. Heute wurde die Phase 17-mal beiläufig unter einer
   anderen Leiste angeboten und nie gedrückt; ein Angebot, das allein steht,
   wird gesehen. Ort: `knoepfe.biete_phase`, Auslöser in
   `aufnahme.schliesse_ab`.
2. **Idempotentes Schreiben plus stille Wiederholung.** In
   `erkenner.wende_an`: schreibt eine `art` denselben Wert wie beim letzten
   Mal, wird der Arbeitsstand aktualisiert, aber **keine neue
   Notiert-Zeile** erzeugt. Das nimmt Gruppe 2 sieben identische Nachrichten
   weg. Test: gleicher Wert zweimal → eine Meldung.
3. **`SCHWELLE_VERDRAENGUNG` von 2000 auf ~600 Token senken oder den
   Journal-Extraktor zeitgesteuert laufen lassen** (alle N Minuten über den
   noch nicht journalisierten Abschnitt, unabhängig von Verdrängung). Heute
   0 Läufe bei vier Gruppen — das ist kein Feintuning, das ist eine tote
   Komponente. `journal.py`, Auslöser in `ablauf.py`.
4. **Ein Knopf „Was steht bisher?" in jeder Grundleiste.** `/stand`
   existiert, wurde aber von keinem Menschen getippt (0 Slash-Befehle am
   ganzen Tag, siehe § 3); der `stand`-Knopf wurde 3-mal angeboten und
   0-mal gedrückt — weil er nur in der Einstiegsleiste stand. Als vierter
   Knopf neben „Eigene Idee · Passt, aber anders · Gefällt uns, weiter"
   wäre er dauernd sichtbar. `knoepfe.grundleiste`.
5. **Undo als Knopf unter der Notiert-Zeile.** Es gibt weiches Löschen im
   Code, aber keinen Weg dorthin außer Sprache. Ein „Doch nicht"-Knopf
   direkt unter jeder Notiert-Zeile, der den letzten Schreibvorgang
   zurücknimmt und einen „Zurückgenommen: …"-Journaleintrag schreibt, ist
   billig (kein Modellaufruf) und macht das Kalibrieren des Erkenners auf
   „im Zweifel eintragen" (N7) erst risikolos.
6. **Überflüssig:** `gruppe.gruendlich_naechster_zug` und
   `telegram.antwortet_auf_bot` sind weiterhin toter Code (HANDOFF (f) 6).
   `kernthema_richtung` wurde auch im Testlauf nicht benutzt — die
   zweistufige Kernthema-Wahl wurde übersprungen, der erste Vorschlag saß
   sofort. Vor Tag 2 nicht anfassen, aber danach prüfen, ob die Stufe 1
   überhaupt gebraucht wird.

---

## 3. Navigation in Telegram

### Zahlen

- **0 Slash-Befehle** von Menschen getippt, in allen vier Gruppen, den
  ganzen Tag. Auch **0 Slash-Erwähnungen** in Bot-Texten — die
  Entwerbung ab 14:38 hat gehalten, und zwar in beide Richtungen.
- Knopfangebote gesamt 166, gedrückt 61 (37 %). Nach Art über alle Gruppen:
  `aufnahme` 30/26 (87 %), `speichern` 7/6, `figur_*` 13/9, `eigene` 7/6,
  `anders` 6/5, `rahmen` 7/1, `phase` **20/2** (10 %, beide Drücke in der
  Testgruppe), `auswerten` 5/0, `auswerten_alle` 1/0, `stand` 4/0,
  `hilfe` 4/0, `teil_weiter` 1/0, `teil_fertig` 1/0, `wir_zuerst` 2/0,
  `schlag_vor` 2/2.
- Nie gedrückt, in keiner Gruppe: `auswerten`, `auswerten_alle`, `stand`,
  `hilfe`, `teil_weiter`, `teil_fertig`, `wir_zuerst`.
- Fehldrücke Start→Beenden unter 10 s: Gruppe 3 **elf Paare**, Gruppe 1
  drei, Gruppe 2 zwei.
- Nachrichten > 4000 Zeichen: keine mehr in der Datenbank — aber Gruppe 2
  hatte um 17:07 ein Teil-Transkript von 7957 Zeichen, das als HTTP 400
  verschwand. Genau dafür kam `bcbad3a` (17:11).
- HTTP 400 bei `answerCallbackQuery`: 2 (nur Testgruppe, gegen 19:53 —
  Knopfdruck-Latenz 1795 s, also weit über Telegrams 10-Sekunden-Fenster
  für `callback_query`).
- `editMessageReplyMarkup`-Fehler „Knöpfe entfernen fehlgeschlagen": **16 in
  der Testgruppe**, 0 in den echten Gruppen — 25 Aufrufe, 21 mit HTTP 400.
  Ursache: die Leiste war schon abgenommen oder die Nachricht ist unverändert.
- Neustarts während des Workshops: keiner sichtbar (keine 409 nach 13:00,
  kein Datenverlust). Die 4 × 409 in `gruppe1.log` liegen vor Workshopbeginn.

### Befund

**Der Aufnahme-Knopf ist der einzige Knopf, den die Gruppen wirklich
angenommen haben** (87 % Druckquote). Alles andere wurde übersehen — vor
allem der Phasen-Knopf mit 10 %, und darunter kein einziger Druck in einer
echten Gruppe. Der Grund ist sichtbar in der Reihenfolge: `phase` steht
regelmäßig als dritter Knopf unter einer Leiste, deren erster Knopf die
naheliegende Handlung ist („Nächste Aufnahme"). Es wird der erste gedrückt.

**Der Aufnahme-Knopf hat zugleich das gröbste Problem:** Gruppe 3 hat ihn
14-mal in 93 Sekunden gedrückt und dabei sieben leere Interviews erzeugt; über
alle Gruppen sind 13 von 20 Aufnahmen leer entfernt worden. Der Knopf ist ein
Umschalter ohne Rückmeldung darüber, in welchem Zustand man ist — und ein
Umschalter, der bei jedem Druck sofort wieder eine neue Leiste erzeugt, lädt
zum Weiterdrücken ein. Die Aufräumlogik (`10466e4`, leere Interviews
verwerfen) fängt den Schaden auf, aber nicht die Verwirrung.

**Die Begriffe „Aufnahme" und „Interview" laufen im selben Chat
nebeneinander**: der Knopf heißt „Aufnahme starten", die Meldung danach
spricht vom Interview, die Auswertung heißt „Auswerten". Drei Wörter für eine
Sache, bei Zielgruppe 15–18 in einem lauten Raum.

**Verwaiste Leisten:** in der Testgruppe wurden ab 19:16 drei
`rahmen`-Vorschlagsknöpfe angeboten, dann um 19:17 drei weitere, dann um 19:23
noch einmal — sieben Rahmen-Knöpfe insgesamt, einer gedrückt. Die alten
Leisten blieben im Chat stehen (die 16 fehlgeschlagenen
`editMessageReplyMarkup`-Aufrufe), also standen zeitweise drei Leisten
gleichzeitig da, die alle noch klickbar aussahen.

**Die 400er bei `answerCallbackQuery`** sind harmlos, aber diagnostisch: sie
belegen, dass ein Knopf nach 30 Minuten noch gedrückt wurde. In einer echten
Gruppe mit fünf Handys wird das häufiger passieren als in Birks Testlauf.

### Vorschläge

1. **Aufnahme-Knopf entprellen.** In `knoepfe` beim Beanspruchen: wurde die
   letzte Aufnahme desselben Chats vor weniger als ~15 s beendet, keine neue
   anlegen, sondern eine Zeile „Die letzte Aufnahme war leer — noch mal
   drücken, wenn ihr wirklich neu starten wollt." Das hätte heute 13 leere
   Aufnahmen verhindert. Ort: `knoepfe` beim Wirken von `ART_AUFNAHME`,
   Prüfung über `repo` gegen `aufnahme.beendet_am`.
2. **Zustand statt Umschalter.** Solange eine Aufnahme läuft, soll **nur**
   „⏹ Aufnahme beenden" stehen, mit laufender Dauer im Text
   („läuft seit 2:14"). Solange keine läuft, **nur** „🎙 Aufnahme starten".
   Nie beide, nie eine neue Leiste unter jedem Teil-Transkript zusätzlich.
3. **Ein Wort für die Sache.** Überall „Interview". Der Knopf heißt
   „Interview aufnehmen" / „Interview beenden", die Verdichtung heißt
   „Interview auswerten". `befehle._TEXT_INTERVIEW_AN`/`_AUS`,
   `knoepfe.biete_aufnahme`, `knoepfe.biete_nach_aufnahme`.
4. **Phasenwechsel als eigene Nachricht, nicht als dritter Knopf.** Wenn
   `phasen.moegliche_naechste` eine Stufe hergibt, geht eine eigene, kurze
   Nachricht mit genau zwei Knöpfen raus („Weiter zu Phase N" / „Noch
   nicht"). Einmal je Stufe, wie bisher über `phase_angeboten` gedeckelt.
5. **Alte Leisten hart abnehmen, bevor eine neue kommt.**
   `knoepfe._nimm_alte_leiste_ab` existiert; sie greift offenbar nicht für
   die Vorschlagsleisten (`rahmen`, `figur_*`). 400er bei
   `editMessageReplyMarkup` nicht nur loggen, sondern die Knopfzeilen der
   alten Leiste in der DB auf „verfallen" setzen, damit ein später Druck eine
   klare Antwort bekommt statt zu wirken.
6. **`answerCallbackQuery` in einen eigenen try/except**, der bei 400 nicht
   den ganzen Handler abbricht — heute erscheinen dadurch zwei
   `bot fehlgeschlagen`-Zeilen für Knopfdrücke, die sonst funktioniert
   hätten.
7. **Ein „Zurück"-Knopf fehlt vollständig.** In der Testgruppe ging es über
   die Figuren-Ebenen (Menü → Figur → Duktus) drei Ebenen tief ohne Rückweg.
   Ein „◀ Zurück" in jeder Untermenü-Leiste.

---

## 4. Kommunikation Bot ↔ User

### Zahlen

- Bot-Antwortlatenz nach einer Mensch-Nachricht: Median 2–3 s in allen
  Gruppen. Maxima 843 s (G1), 736 s (G2), 2439 s (G3) — das sind Fälle, in
  denen der Bot erst nach der nächsten Aktion wieder dran war, kein Hänger.
- Fragedichte in freien (nicht system-generierten) Bot-Texten: G1 3,93
  Fragezeichen je Nachricht, G2 3,22, G3 4,79 — **Testgruppe 0,75**.
- Bot-Blöcke am Stück ohne Mensch-Nachricht dazwischen: G3 einmal **9**,
  G1 einmal 4, Test einmal 6.
- Kurze Mensch-Nachrichten (< 30 Zeichen) als Rückfrage-Proxy: G1 3 von 14,
  G2 **12 von 23**, G3 5 von 13, Test 5 von 6.
- Klarnamen in Bot-Texten (Telegram-Vorname einer Teilnehmerin kommt im
  Bot-Text vor): **G1 11 von 27, G3 12 von 31, G2 2 von 37**, Test 0 von 16.
- Slash-Bewerbung in Bot-Texten: **0**, vor und nach 16:00. Soll erfüllt.
- Echo-Vorfälle (`ablauf.ist_echo`): 0.

### Befund

**Die Fragedichte ist das auffälligste Kommunikationsproblem des Tages.**
Knapp vier bis fünf Fragezeichen in einer einzigen Nachricht an eine Gruppe
von 15–18-Jährigen, die nebenher ein Interview führen — das ist eine
Fragebogenzeile, kein Gespräch. Der Systemprompt verlangt „EIN Vorschlag";
gegen die Fragen sagt er nichts. Die Testgruppe mit 0,75 zeigt, dass der Bot
es kann, wenn ihn eine Knopfleiste trägt: wo Auswahl in Knöpfen steckt,
braucht der Text keine Fragen mehr.

**Die 12 von 23 kurzen Nachrichten in Gruppe 2** (Median Mensch-Nachricht:
29 Zeichen) sind ein starkes Indiz, dass die Gruppe überwiegend zurückgefragt
oder knapp bestätigt hat, statt inhaltlich zu arbeiten. Das passt zur
Fragedichte: der Bot fragt viel, die Gruppe antwortet knapp, der Bot fragt
das Nächste.

**Klarnamen sind wieder da.** In Gruppe 1 und 3 nennt fast jede zweite
Bot-Nachricht einen Vornamen aus dem Chat. Das ist nicht der 05.09.
behobene Fall (Aufnahmename → „Interview N"), sondern die direkte Anrede aus
dem Gesprächsverlauf: der Bot spricht die Person an, die zuletzt geschrieben
hat. Für eine Chatgruppe ist das normal, für ein Werkzeug, das mit
Lebensgeschichten Minderjähriger arbeitet, ist es eine Entscheidung, die
bewusst getroffen werden sollte — insbesondere weil dieselben Bot-Texte auf
der Weboberfläche landen können und das Dashboard projiziert wird. (Geprüft
wurde nur mechanisch, ob ein Vorname vorkommt; die Nachrichten selbst wurden
nicht gelesen.)

**Neun Bot-Nachrichten am Stück** (Gruppe 3, im Aufnahme-Chaos um 16:40) sind
eine Folge der Umschalter-Logik: jeder Knopfdruck erzeugt eine Bestätigung
plus eine neue Leiste.

### Vorschläge (als Prompt-Sätze)

Für `interview_theater/prompts/system.md`:

- „Stelle höchstens **eine** Frage je Nachricht. Hast du mehrere, nimm die
  wichtigste und lass die anderen weg."
- „Steht unter deiner Nachricht eine Knopfleiste, stelle gar keine Frage —
  die Knöpfe sind die Frage."
- „Sprich die Gruppe an, nicht einzelne Personen. Benutze keine Vornamen aus
  dem Chat."
- „Was du gerade notiert hast, sagst du nicht noch einmal. Wiederhole keine
  Liste, die im Verlauf schon steht."

Für `prompts/phasen/3.md` (Interviews, die Phase des Nachmittags):

- „Während ein Interview läuft, schreibst du nichts außer dem, was der Code
  ohnehin schickt. Kein Zwischenkommentar, keine Nachfrage."
- „Nach einem Interview: ein Satz, was du gehört hast, und ein Satz, was als
  Nächstes möglich ist. Nicht mehr."

Für `prompts/phasen/1.md` und `2.md`:

- „Die Begriffe und die Fragen kommen aus dem Plenum. Du sammelst sie nicht
  ab, du schlägst sie nicht vor, du fragst nicht nach weiteren."

---

## 5. Kreative Gestaltung der Inhalte

### Zahlen (Testgruppe, Phasen 4–7)

- Kernthema: 194 Zeichen, ein Satz, drei Motive verschränkt (Wegsehen,
  verpasste Nähe, Geschwisterkonflikt). Über die Speicher-Leiste in einem
  Zug gesetzt, keine Richtungs-Stufe benutzt.
- Figuren: 3 (Mira, Amir, Freundin), Entwurfszeilen je ~90 Zeichen im Format
  „Name — ein Satz — Interview N", alle drei mit Quell-Interview und
  Sprachprofil. Sprachprofile 167/216/336 Zeichen (3–5 Zeilen), Zitate
  357–513 Zeichen je Figur. Alle drei Sprachprofil-Aufrufe erfolgreich, je
  ~2,7 s, zusammen 609 Antwort-Token.
- Format: „Urban Dance Tanztheater", per Knopf festgelegt 19:15.
- Rahmen: 7 Vorschläge in drei Wellen, 1 übernommen („Schulhof in der Pause,
  kurz vor Schluss, Rucksack als Brennpunkt", 64 Zeichen).
- Szenenfolge: **1 Versuch, gescheitert** (`finish_reason: length`,
  4000 Token vollständig im Reasoning verbraucht, 28,3 s). 0 Szenen,
  0 Szenentexte, 0 Zeilen Bewegungsanweisung. `prompts/formen/tanztheater.md`
  (95 Zeilen, 16 Regeln) ist damit **noch nie gegen ein Modell gelaufen**.

### Befund

**Der Weg Kernthema → Figuren → Sprachprofil → Format → Rahmen trägt.** In
45 Minuten und mit sechs Mensch-Nachrichten stand ein vollständiger
Arbeitsstand für Phase 6, mit drei belegten Sprachprofilen. Das ist das
Ergebnis der Knopf-Navigation vom Nachmittag, und es ist deutlich besser als
alles, was die Sprachnavigation heute geliefert hat.

**Die inhaltliche Qualität der Vorschläge ist brauchbar, aber schmal.** Die
sieben Rahmen-Vorschläge zerfallen in zwei Gruppen: drei aus dem
Interviewmaterial abgeleitete (Schulhof, Bahnsteig, pädagogischer Raum) und
drei generische, die aus den Prompt-Beispielen stammen („Kessel nach Demo",
„Warteschlange vor Club"). Der Kessel taucht um 19:17 auf — **vor** Commit
`505cf23` (20:00, „Prompts: Beispiel-Eigennamen raus"). Das
Nachplapper-Problem aus dem Skill („Pola") ist also live noch einmal
aufgetreten, diesmal mit dem Ort statt dem Namen. Der Figurenname „Mira" in
der Testgruppe ist derselbe Fall: „Mira" steht als Beispielname in
`erkenner.md`, `formen/chor.md`, `formen/lied.md`, `formen/stumm.md` und
stand bis 18:15 auch in `phasen/4.md` und `system.md`. Dass die erste Figur
der Testgruppe „Mira" heißt, ist mit hoher Wahrscheinlichkeit kein Zufall.
`505cf23` hat das für `system.md` und die Phasen-Prompts behoben — **in
`prompts/erkenner.md` stehen Pola, Mira, Pal und der Polizeikessel weiterhin
in über 20 Zeilen**, und `formen/*.md` ebenfalls.

**Der Szenenlauf ist ungetestet in den Tag 2 hinein.** Der einzige Versuch
scheiterte am Budget; der Fix (`960f12a`, 60 000 Token, 300 s) wurde nie
verifiziert. Damit steht morgen der eigentliche Kern des Tages — Szenen
schreiben — auf einer Codepfad-Kombination (`szenenfolge` über `klm.prosa`
mit Reasoning, dann `szene` über den Claude-Proxy), die heute nicht ein
einziges Mal durchgelaufen ist.

### Vorschläge für Tag 2

1. **Vor dem Workshop einen vollständigen Szenendurchlauf in der Testgruppe
   fahren** — Szenenfolge, Szenenfelder, ein Szenentext in Form
   „tanztheater". Das ist der wichtigste Punkt der ganzen Analyse. Wenn
   `szenenfolge` mit 60 000 Token immer noch in `length` endet, muss das um
   9:00 bekannt sein, nicht um 15:00.
2. **`prompts/formen/tanztheater.md` als Vorgabe-Form setzen**, wenn
   `arbeitsstand.format` „Tanztheater" oder „Urban Dance" enthält. Aktuell
   ist Dialog der Rückfall (`szene.formdatei`), und eine Szene, die als
   Dialog geschrieben wird, ist für morgen unbrauchbar.
3. **Eigennamen aus `prompts/erkenner.md` und `prompts/formen/*.md`
   entfernen** — Platzhalter `<Figurname>`, `<Ort>`. Danach zwingend
   `python -m scripts.pruefe_prompts erkenner --bericht`, weil die Few-Shots
   des Erkenners betroffen sind (Regel: gilt nur bei FP = 0).
4. **Rahmen-Vorschläge aus dem Material erzwingen.** In `phasen/5.md`:
   „Jeder Ortsvorschlag muss aus einem Interview stammen, das euch vorliegt.
   Nenne dazu, aus welchem. Erfinde keinen Ort, den niemand erzählt hat."
5. **Ablauf morgen** (Vorschlag): Szenenfolge früh und gemeinsam (eine
   Nachricht, Knopf „Gefällt uns, weiter"), dann je Kleingruppe zwei bis
   drei Szenen, danach Durchlauf. Der Rahmen der Testgruppe — öffentlicher
   Ort, Pausensituation, ein Gegenstand als Brennpunkt — ist für Urban Dance
   auf einem öffentlichen Platz gut gewählt und lässt sich als Muster für
   die drei Gruppen anbieten, ohne ihn vorzugeben.
6. **Regie-Zettel für morgen vorbereiten** (`betrieb/zusatz.md`), Inhalt
   sinngemäß: „Heute geht es nur um Szenen. Das Format steht fest: Urban
   Dance Tanztheater, mehr Bewegung als Text, höchstens zwölf gesprochene
   Zeilen je Szene. Schlage keine neuen Kernthemen und keine neuen Figuren
   vor." Damit greift die Fokussierung sofort, ohne Neustart.

---

## 6. Ergänzungen

### Robustheit

Sehr gut: **149 Modellaufrufe, ein Fehlschlag.** Kein Datenverlust, kein
409 während des Workshops, kein Neustart nötig, der Nachhol-Arbeiter musste
nie eingreifen (alle Aufnahmen `fertig`). Die Threads für Verdichter und
Sprachprofil haben gehalten. Die Kürzungs- und Fenster-Vorfälle blieben bei
null.

Weniger gut: das Teil-Transkript von 7957 Zeichen ist in Gruppe 2
verschwunden, und die Gruppe hat nur den Fehler gesehen, nicht das Ergebnis —
zwischen 17:07 (Fehler) und 17:11 (Fix) lag der Rest des Nachmittags. Der Fix
ist ausgerollt, aber nie gegen ein echtes langes Transkript gelaufen.

### Kosten

Prompt-Token 05.09.: Erkenner 589 k, Gespräch 440 k, Verdichter 15 k,
Sprachprofil 4 k, Szenenfolge 3 k. Antwort-Token zusammen ~23 k. Der
**Erkenner ist mit 57 % der Prompt-Token der teuerste Posten** — er läuft auf
gemma und ist damit billig, aber die Größenordnung sagt: 86 Aufrufe für
13 Journaleinträge und zwei Arbeitsstandfelder ist ein schlechtes
Verhältnis. Bei Kimi-Preisen für den Gesprächsanteil liegt der Tag im
niedrigen einstelligen CHF-Bereich; das ist kein Kostenproblem, sondern ein
Wirkungsproblem.

Token-Schätzung: `geschaetzte_token` gegen `tatsaechliche_token` liegt beim
Szenenfolge-Aufruf bei 2808 gegen 2824 — der Divisor in `kontext.schaetze`
stimmt (HANDOFF (g)).

### Latenz

Gespräch median 1,9 s, p90 3,5 s, **max 13,7 s** (Gruppe 3). Verdichter bis
9,2 s. Der Szenenfolge-Lauf brauchte 28 s bis zum Abbruch. Der 8,3-s-Fall aus
HANDOFF (f) 5 ist also kein Einzelfall, aber auch kein Muster — ein
Ausreißer je ~50 Aufrufe.

### Web/Dashboard

2563 Aufrufe der Gruppenseiten und 3299 des Dashboards — **alle von einer
einzigen Tailnet-IP** (100.91.71.17), also vom Projektionsrechner, im
10-Sekunden-Takt. Kein einziger Aufruf von einem Handy einer Teilnehmerin.
Elf verschiedene Tokens wurden abgerufen (mehr als die vier Gruppen — Reste
aus Simulationsläufen). Der Link wurde in Gruppe 2 zweimal in den Chat
geschrieben. Nutzen für die Gruppen heute: praktisch null; Nutzen als
Projektion: nicht messbar aus dem Log.

### Datenschutz

- Bot-Texte mit Teilnehmer-Vornamen: 25 von 111 (23 %), in Gruppe 1 und 3 je
  ~40 %. Siehe § 4.
- Belegzitate: 28 von 29 geprüft. Ein durchgefallenes Zitat wurde korrekt
  nicht gespeichert.
- Transkripte und Nachrichten liegen unverschlüsselt in `betrieb/soap.db`,
  dazu sechs Backup-Kopien der DB im selben Verzeichnis
  (`soap.db.vor-*`, `soap.db.bak-*`, bis zu 4,1 MB WAL). Für die
  Löschzusage heißt das: `scripts/loeschen.py` räumt die aktive DB, **nicht
  die Backups**. Vor der Löschzusage muss jemand die `.bak`-Dateien
  mitnehmen.
- Die Bot-Tokens stehen weiterhin in den Tracebacks der Logdateien
  (HANDOFF (f) 8, bewusst so). `betrieb/` ist gitignored, aber die Logs
  liegen unverschlüsselt neben der DB.

---

## Top 5 für morgen (priorisiert, mit Aufwand)

1. **Szenendurchlauf in der Testgruppe verifizieren, vor 12:00.**
   Szenenfolge → Szenenfelder → ein Szenentext in Form „tanztheater" über
   den Claude-Proxy. Ohne diesen Lauf geht Tag 2 blind in seinen Kern.
   *Aufwand: 30–45 min, überwiegend Wartezeit. Kein Code.*
2. **Format „Tanztheater" auf `prompts/formen/tanztheater.md` mappen.**
   `szene.formdatei` fällt sonst auf Dialog zurück. Zwei Zeilen Code plus
   Test.
   *Aufwand: 20 min.*
3. **Fragedichte senken.** Vier Sätze in `prompts/system.md` (§ 4), plus die
   zwei in `phasen/3.md`. Hot-Reload, kein Neustart, keine Erkenner-Änderung
   — also kein Korpuslauf nötig.
   *Aufwand: 20 min.*
4. **Aufnahme-Knopf entprellen und Zustand statt Umschalter zeigen.**
   13 von 20 Aufnahmen waren heute leer; morgen wird wieder aufgenommen.
   *Aufwand: 1–1,5 h inkl. Tests.*
5. **Phase beim ersten Interview aktiv anbieten, als eigene Nachricht mit
   zwei Knöpfen.** Ohne das läuft morgen wieder `phasen/1.md`, während die
   Gruppen an Szenen arbeiten.
   *Aufwand: 1 h inkl. Tests.*

Falls nur zwei Dinge passen: **1 und 2.**

## Danach (nicht morgen)

- Journal-Extraktor zeitgesteuert statt verdrängungsgesteuert
  (heute 0 Läufe).
- Idempotentes Schreiben, keine wiederholten Notiert-Zeilen.
- „Was steht bisher?" und „◀ Zurück" in die Grundleiste.
- Eigennamen aus `erkenner.md` und `formen/*.md` (mit Korpuslauf, FP = 0).
- Alte Knopfleisten hart verfallen lassen; `answerCallbackQuery`-400 isolieren.
- Backup-Kopien der DB in die Löschzusage aufnehmen.
- Toten Code entfernen: `gruendlich_naechster_zug`, `antwortet_auf_bot`,
  ggf. `kernthema_richtung`.

## Offene Fragen an Birk

1. **Klarnamen:** Soll der Bot Teilnehmerinnen mit Vornamen ansprechen? Heute
   tat er es in 23 % seiner Nachrichten, in zwei Gruppen in ~40 %. Verbot ist
   ein Prompt-Satz; die Entscheidung ist deine.
2. **Wie ist der Nachmittag im Raum gelaufen?** Die Zahlen zeigen: Bot ab
   15:15 aktiv, Interviews 16:20–17:08, danach Stille. Von 13:30 bis 15:15
   und ab 17:10 lief er leer. War das so geplant (Plenum, Analogarbeit), oder
   ist da etwas hängengeblieben?
3. **Warum wurde die Phase nie gesetzt?** Wusstet ihr, dass der Bot alle drei
   Gruppen als Phase 1 geführt hat? Und: hat jemand den Phasen-Knopf
   überhaupt gesehen?
4. **Was hat im Raum gestört?** Fragedichte, Doppelnachrichten, das
   Aufnahme-Chaos in Gruppe 3 — welches davon ist den Betreuerinnen
   aufgefallen, und was hat gestört, das hier nicht messbar ist?
5. **Sollen die drei Gruppen morgen mit demselben Material weiterarbeiten?**
   Sie haben je genau ein Interview und eine Verdichtung — dünn für ein
   Kernthema. Alternative: morgen früh noch eine Interviewrunde, oder die
   Gruppen speisen sich gegenseitig.
6. **Wird der Szenentext weiter über Opus geschrieben?** Die USA-Einwilligung
   ist in keiner der drei Gruppen je erfragt worden
   (`szene_usa_bestaetigt_am` überall NULL). Morgen kommt sie zum ersten Mal
   — vor drei Gruppen gleichzeitig, im laufenden Betrieb.

# Übergabe

Für jemanden — Mensch oder Agent —, der diese Arbeit beurteilen soll, ohne bei ihrer
Entstehung dabei gewesen zu sein.

**Stand:** ~~04.09.2026 · 575 Tests grün · 20 Module, 7.328 Zeilen · 86 Commits~~
**Nachtrag 05.09.2026 früh:** 746 Tests grün · 21 Module · 122 Commits — siehe
„Nacht 04./05.09.: was sich geändert hat" unten für den größten Umbau seit dem
Durchstich.
**Erster Einsatz:** Workshop Dortmund, 05.+06.09.2026, 13:00

Verwandte Dokumente: `README.md` (für Theaterleute) · `AGENTS.md` (für Entwicklung) ·
`SPEC-kontext-architektur.md` (die maßgebliche Spezifikation) ·
`docs/entwurfsgeschichte.md` (**wichtig** — die Vorgeschichte und die verworfenen
Alternativen).

---

## (a) Was das Werkzeug tut und für wen

Ein Telegram-Bot, mit dem **Laienschauspielerinnen in Kleingruppen aus eigenen Interviews
ein Theaterstück entwickeln**. Sie führen Interviews, schicken sie als Sprachnachricht in
einen Gruppenchat, und arbeiten von dort weiter: Das Material wird transkribiert und
verdichtet, aus den Kernthemen entstehen Figuren, aus den Figuren ein Konflikt, aus dem
Konflikt Szenentext.

Der Bot **moderiert und schlägt vor, entscheidet aber nichts**. Seine Vorschläge sind
Andockpunkte zum Reagieren, und sie sind mit wörtlichen Zitaten aus den Interviews belegt.

Ein Prozess je Kleingruppe, gemeinsame SQLite. Spracherkennung und Sprachmodell laufen über
Infomaniak in der Schweiz.

---

## (b) Was in dieser Phase gebaut wurde, in welcher Reihenfolge, und warum

Die Arbeit lief in drei Phasen, jede mit Umsetzung **und unabhängiger Durchsicht** je
Aufgabe. Die Durchsicht fand in **neun von zehn** Aufgaben des Durchstichs einen echten
Fehler — das ist die wichtigste Zahl dieses Dokuments, weil sie sagt, wie viel von der
Qualität aus dem Verfahren stammt und nicht aus dem ersten Wurf.

### Teil A — der Durchstich (10 Aufgaben)

Ziel war ein Weg, der von Anfang bis Ende trägt, bevor irgendetwas verfeinert wird:
Nachricht rein · Sprachnachricht transkribiert · Verdichtung · Antwort raus · Zustand
überlebt den Neustart.

Reihenfolge: Gerüst und Datenbank → Repository → Telegram-Wrapper → Polling-Schleife →
LLM-Client → Whisper → Zitatprüfung und Verdichter → Aufnahme-Pipeline → Kontext-Zusammenbau
→ Gesprächszug.

**Warum diese Reihenfolge:** Von unten nach oben, damit jede Aufgabe auf Getestetem steht.
Der Gesprächszug kam zuletzt, weil er alles andere benutzt.

Was die Durchsicht fand, in absteigender Schwere:

| Aufgabe | Fehler |
|---|---|
| Polling | Sprachnachricht im Nachtstau erreichte die Pipeline nicht — **ein abends geschicktes Interview wäre spurlos verschwunden** |
| Aufnahme-Pipeline | Download-Fehler verlor die Aufnahme endgültig; Verdichtung ohne Kostenobergrenze (1.440 bezahlte Aufrufe pro Tag pro hängender Aufnahme) |
| Gesprächszug | Geteilte SQLite-Verbindung ohne Serialisierung — Race unter genau der Last, die drei gleichzeitig sprechende Personen erzeugen |
| Whisper | Zeitbudget um das Vierfache gerissen (185 s statt 45 s); 5xx beim Pollen entkam der Fehlerbehandlung; **echte Produkt-ID im öffentlichen Repo** |
| Telegram | **Bot-Token in HTTP-Fehlermeldungen** — wäre über die Vorfall-Tabelle auf dem projizierten Dashboard gelandet |
| Kontext | `/wortlaut`-Schalter fehlte → 5.000 Token Dauerlast; kurze Zurufe wurden als Interview-Material ausgegeben |
| LLM-Client | `ConnectError` wurde nicht wiederholt — genau das Ausfallszenario „Anbieter weg" |
| Repository | Wasserzeichen konnte **rückwärts** springen → beantwortete Nachrichten erneut beantwortet |

### Teil B — das Gedächtnis (8 Aufgaben)

Teil A hinterließ eine Lücke, die erst beim Nachsehen auffiel: `kontext.py` **las**
`arbeitsstand`, `figur` und `journal` in den Prompt, aber **niemand schrieb sie**. Das
Gedächtnis bestand aus Interview-Verdichtungen plus Verlaufsfenster; alles andere war eine
leere Hülle, die korrekt gelesen wurde.

Reihenfolge: Reasoning-Falle und robustes Auslesen → Absichtserkenner → Schreibpfad →
Meldelogik → Interviewmodus → sechs Befehle und `setMyCommands` → Begrüßung → Warmlauf.

**Warum die Reasoning-Falle zuerst:** größte Reichweite, jeder spätere Aufruf hängt daran.

### Nach dem ersten Live-Test

Der Bot lief gegen eine echte Gruppe. Zwei Beobachtungen führten zu Korrekturen:

1. **Der Bot redete Teilnehmerinnen mit Vornamen an.** Der Name muss im Kontext bleiben —
   sonst weiß der Bot bei vier Sprecherinnen nicht mehr, wer was gesagt hat. Falsch war nur
   die Verwendung. Die Systemanweisung sagt jetzt: Namen sind zur **Zuordnung** da, nicht
   zur Anrede.
2. **Die Begrüßung war inhaltlich falsch** — und beim Nachsehen stellte sich heraus, dass
   nicht der Text das Problem war, sondern der Code: Der Bot antwortete tatsächlich nur auf
   Reply, Erwähnung, Befehl oder Sprachnachricht. Nur den Text zu ändern hätte einen Bot
   ergeben, der verspricht, auf alles zu antworten, und dann schweigt. Beides wurde
   geändert.

Danach: Journal-Extraktor, Fenster von 2.500 auf 8.000 Token, Dokumentation.

### Nach dem Probelauf am 04.09. abends: Aufnahmen

Ein Interview bestand aus **fünf Sprachnachrichten**. Der Code behandelte jede einzeln als
eigene lange Aufnahme: fünf Aufnahmen `Interview 6` bis `Interview 10`, fünf Verdichtungen,
zwei davon leer („Material extrem kurz", „Transkript nicht beigefügt"). Nach jeder Nachricht
kam „Ich höre durch", danach nichts — weder Transkript noch Inhalt. Die Entwurfsgeschichte
hatte von Anfang an gesagt, ein Interview bestehe aus mehreren Sprachnachrichten; umgesetzt
war es nie.

Seitdem (SPEC § 10.6): **Modus an → ein Interview.** Jede Sprachnachricht ist ein *Teil*,
ihr Transkript geht sofort und wörtlich in den Chat („Interview 3, Teil 2: …") — zur
Kontrolle, solange die interviewte Person noch im Raum sitzt, ohne Modellaufruf. „fertig"
fügt die Teile zusammen, verdichtet **einmal** und stellt die Verdichtung in den Chat:
Zusammenfassung, Kernthemen, geprüfte Belegzitate, „Stimmt das so?". Das war der eigentliche
Verlust im Probelauf — die Gruppe erfuhr nie, was in ihrem Material steckt.

Drei Dinge daran sind Entscheidungen, keine Details: „Ich höre durch" ist **gestrichen** (das
Transkript ist die Bestätigung); das Echo steht in **keinem Fenster**, sonst liest der
Absichtserkenner die Erzählung der interviewten Person als Absicht der Gruppe; und ein noch
offener Teil **hält den Abschluss auf**, statt ohne ihn zu verdichten — der Nachhol-Arbeiter
holt ihn und schließt danach ab.

---

## Nacht 04./05.09.: was sich geändert hat

Zwischen dem Probelauf am 04.09. abends und dem Workshopstart am 05.09. um 13:00 lag eine
zweite, größere Korrekturrunde als der Abschnitt oben — ausgelöst durch denselben Probelauf,
aber mit Wirkung bis in den Szenen-Prompt hinein. Neun Punkte, mit den Live-Belegen aus dem
Probelauf-Chat (Nachrichtennummern) und den Commit-Kürzeln (`T1`–`T9`, `N4`–`N7`), unter
denen die Details in Commit-Messages und Prompts stehen.

1. **Interview als Einheit, jetzt vollständig.** Ergänzend zum Abschnitt oben wirkt die
   Korrektur jetzt auch rückwärts: fehlt „fertig" im Chat, weil es in die Aufnahme
   hineingesagt wurde, hört der Erkenner es trotzdem — er läuft über jedes Teil-Transkript
   mit, gemma, unter einer Sekunde. Und unter `aufnahme.MINDEST_WOERTER` (40 Wörtern) wird gar
   nicht erst verdichtet, kein Thema ohne wörtliches Zitat (N2).
2. **Sieben Phasen, kein automatischer Sprung mehr.** Birk: „Datenstand ist nicht Absicht" —
   eine fertige Verdichtung sagt nichts darüber, ob die Gruppe fertig ist. Phase 4 ist jetzt
   Kernthema & Figuren zusammen, Phase 5 heißt „Format & Rahmen" statt „Hauptkonflikt": „nicht
   jede Szene braucht einen Konflikt, es wird vermutlich ein Musical" (Birk, T1).
3. **Im Zweifel eintragen (N7).** Zustimmung zu einem Vorschlag ist seitdem eine Festlegung,
   auch beiläufig („passt", „nehmen wir") — Belege aus dem Chat sind die Nachrichten 67 und
   69. Grund: seit weichem Löschen und `transkript_korrigieren` ist ein falscher Eintrag
   billig, ein fehlender teuer — dreimal blieb der Arbeitsstand im Probelauf leer, obwohl die
   Gruppe zugestimmt hatte.
4. **Szenen werden geplant, dann geschrieben.** Neun Felder je Szene (`form`, `ort`, `zeit`,
   `anlass`, `figuren`, `was_passiert`, `was_anders`, `kernsaetze`, `ton`), Beleg aus dem
   Probelauf ist Nachricht 86 („Alle drei sind auf der Demo, Palästina-Demo, Polizeikessel" →
   `rahmen_setzen`, davor war daraus eine Küche geworden). Dazu **Sprachprofil je Figur**: der
   Bot schlägt eine Zuordnung mit Zitat vor, die Gruppe nickt, ein gemma-Aufruf analysiert
   Satzlänge, Füllwörter, Dialekt.
5. **Szenen-Prompt: Struktur statt Transkript.** Birk nach dem Probelauf: „genau andersrum ist
   richtig — destillierte Begriffe, klare Strukturen, Zitate als Few-Shots für die Sprechweise,
   Continuity mechanisch." Sechs Formen (`prompts/formen/`), Lied und Rap aus einer eigenen
   Recherche zu Songwriting-Handwerk und deutschsprachigem queerfeministischem Rap (26 belegte
   Zeilen); eine **Sperre** verhindert den Aufruf ganz, solange Pflichtfelder oder ein
   Sprachprofil fehlen, statt wie im Probelauf viermal nachzufragen (Nachrichten 84, 98, 108,
   114) und trotzdem die falsche Szene zu schreiben (Nachricht 97 wäre die richtige Stelle
   gewesen).
6. **Im Interviewmodus reagiert der Bot auf Anfragen** (`an_den_bot`, N4). Eine Sprachnachricht
   im laufenden Interview muss nicht Material sein — die Gruppe fragt darin auch den Bot direkt
   an, und die Antwort geht immer als Text zurück, unabhängig von der Sprache der Frage.
7. **Korrekturen wirken jetzt tatsächlich** (`transkript_korrigieren`, N5). Ein Hörfehler von
   Whisper wird überall ersetzt, wo er steht — Transkript, Zusammenfassung, Zitate —, ohne neu
   zu verdichten; der Gesprächs-Bot behauptet dabei keine Schreibvorgänge mehr, die er nicht
   ausführt. `entfernen` darf seitdem auch ein ganzes Interview treffen.
8. **Weboberfläche zeigt Ergebnisse, nicht Fließtext.** Gruppenseite und Dashboard bekamen
   aufklappbare `<details>`-Blöcke je Szene und Interview — Kurzform in der Summary-Zeile,
   Details erst beim Aufklappen. Dazu: reiner Text ohne Markdown im Systemprompt, weil Telegram
   Sternchen roh anzeigt, und maximal ein Vorschlag je Antwort.
9. **`max_tokens` beim Szenen-Aufruf auf 200.000.** Infomaniak rechnet Eingabe und Ausgabe
   gegen ein gemeinsames `max_total_tokens = 249.984` (HTTP 400 bei 250.000, gemessen); mit dem
   erweiterten Prompt lief ein Lauf bei 12.000 Token nur im Denken leer, gemessen wurden 19.410
   Antwort-Token beim ersten erfolgreichen Versuch.

Dazu kommt der **Simulator** (`simulation/`, `scripts/simulation.py`, Stand im Worktree
`feat/simulation`, wird gerade nach `main` gemergt): drei simulierte Personen, 15 erfundene
Interviews in drei Sets, dazu `--set birk` mit Birks echtem Testinterview als Messlatte für die
Navigation, ein Richter, Kennzahlen, ein vollständiger Verlauf in `verlauf.jsonl`. Der Bot
läuft gegen Infomaniak, die Simulation gegen Claude Opus über einen Proxy — kein Modellvergleich,
sondern ein zweiter, günstigerer Weg zum Probelauf. Eigene Dokumentation in
`simulation/README.md`, hier nur erwähnt, weil er zeigt, wohin ein Probelauf gehört: vor den
Workshop, nicht in ihn hinein.

---

## (c) Entwurfsentscheidungen — mit den verworfenen Alternativen

**Die ausführliche Fassung steht in `docs/entwurfsgeschichte.md`.** Hier die
architektonischen Entscheidungen, die man kennen muss, um den Code zu beurteilen.

### Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte Entscheidungen

Beim Empfangen großzügig, beim Zusammenbauen streng. **Etwas nicht aufzunehmen ist
unumkehrbar; etwas aufzunehmen und nicht in den Prompt zu legen kostet Kilobyte.**
Deshalb ist der Privacy Mode bei BotFather aus, und deshalb wird alles roh gespeichert.

### Kein Rolling Summary — ein Journal

*Verworfen:* periodische Neuverdichtung des Verlaufs (der Lehrbuchansatz). Sie driftet über
zwei Tage, braucht einen Modellaufruf zu unvorhersehbaren Zeitpunkten und widerspricht der
Regel, dass Verdichtungen nicht angefasst werden.

Die Einsicht: Das Problem war nie „der Verlauf ist zu lang", sondern **„das Wichtige liegt
in der falschen Schicht"**.

### Ein datengetriebener Prompt-Zusammenbau, keine Phasen-Zustandsmaschine

*Verworfen:* je Workshop-Phase ein eigener Zusammenbau. Das hätte erfordert, dass der Code
weiß, welche Phase läuft — also eine Zustandsmaschine oder einen Klassifikationsaufruf im
kritischen Pfad.

*Gewählt:* Jeder Block entfällt, solange er leer ist. Der Fortschritt steht ohnehin in der
Datenbank. **Biegt die Gruppe ab, ändert sich die Materiallage und der Prompt folgt** — es
gibt keinen Zustand, der ihr widersprechen könnte.

### Keine Rückfragen, die auf eine Antwort warten

Ein Zustandsfeld, das ablaufen kann, falsch verbraucht werden kann und nur gegen die Uhr
testbar ist, wurde zweimal entworfen und **zweimal gestrichen** — beim zweiten Mal, als es
über den Interviewmodus zurückkommen wollte.

Der Ersatz ist billiger und robuster: Der Bot **weist beiläufig hin**, statt zu fragen. Der
Rettungsanker ist, dass Rohmaterial immer gespeichert wird — wird der Modus zu starten
vergessen, ist die Aufnahme trotzdem da.

### Die Zitatprüfung wurde bewusst wieder vereinfacht

*Zwischenstand:* Zerlegung an `[...]`, Reihenfolge- und Abstandsprüfung, ein Retry.

*Verworfen, weil:* Das schützte gegen **ein einziges Vorkommnis in neun Messläufen** und
konnte selbst falsch ablehnen. Ein fälschlich abgewiesenes Zitat ist am Workshoptag genauso
schlecht wie ein zusammengeklebtes. Geblieben ist ein Teilstring-Vergleich nach
Normalisierung — er fängt den Fall ab, den die Gruppe nicht selbst sehen kann: ein Zitat,
das **gar nicht** im Transkript steht.

### Zwei getrennte Modellaufrufe für das Gedächtnis

*Verworfen:* ein Extraktor für alles.

*Gewählt:* Der **Absichtserkenner** läuft nach jeder Antwort und muss zeitnah sein, weil
seine Änderungen sofort gemeldet werden. Der **Journal-Extraktor** läuft bei Verdrängung
und darf gemächlich sein, sieht dafür einen ganzen Gesprächsabschnitt im Zusammenhang.
Arbeitsteilung gegen Doppeleinträge: Erkenner schreibt `verworfen`/`entschieden`, Journal
schreibt `vorgeschlagen`.

### Sechs Befehle statt fünfzehn

*Verworfen:* je Absicht ein Slash-Befehl. **Fünfzehn Befehle zu bauen hieße, dem eigenen
Messergebnis nicht zu trauen** — der Erkenner hat 0 Falsch-Positive bei 25 Negativfällen.
Die Begründung je nicht gebautem Befehl steht in `SPEC` § 8.1.

---

## (d) Was gemessen wurde

Alle Zahlen gegen die echten Dienste, nicht gegen Attrappen. Die ausführlichen Recherchen
liegen unter `/home/birk/hermes-shared/hermes-knowledge/`:
`infomaniak-modelle.md` · `reasoning-stufen-entscheidungshilfe.md` ·
`gedaechtnis-extraktion-agenten.md` (22 Primärquellen, enthält den Prompt-Entwurf und das
Schema für den Journal-Extraktor).

### Modellwahl (04.09.2026)

| Aufruf | Modell | Beleg |
|---|---|---|
| Gespräch, Verdichter | `moonshotai/Kimi-K2.6` | 6/6 valide, 5,1 s, 8/8 Belegzitate wörtlich |
| Absichtserkenner, Journal | `google/gemma-4-31B-it` | **0 Falsch-Positive bei 25 Negativfällen, 30/30 Treffer, 0,75 s.** Kimi verpasste `interview_beenden` 3/3 |

**Ausgeschlossen:** `Nemotron-Nano` — 6/27 Falsch-Positive, las „Kindheitsfragen lassen wir
weg" als `kernthema_setzen`. `Apertus` scheitert an verschachtelten Schemata.

**Kosten sind kein Auswahlkriterium:** ein ganzes Wochenende kostet 1,20 statt 1,41 CHF.
Ausgewählt wird nach Trefferquote.

**`gemma` hat rund 28 s Kaltstart**, danach unter 1 s. Der Bot läuft beim Start selbst warm.

### Whisper-Latenz (03.09.2026, 76 Läufe über 52 Minuten, alle erfolgreich)

Median 2,9 s bei 7 s Audio · 2,8 s bei 30 s · 4,8 s bei 180 s. **Einziger Ausreißer 8,88 s,
kein Lauf über 10 s.** Kein Rate-Limiting bei zehn gleichzeitigen Uploads. **Chunking bringt
nichts** (6×30 s parallel 4,22 s gegen 4,84 s am Stück) — also wird nicht geschnitten außer
wegen der 25-MB-Grenze.

Daraus abgeleitet: Tippanzeige ab 5 s, Textmeldung ab 12 s (über dem Ausreißer),
Zeitbudget 45 s für Gesprächsbeiträge und 90 s für Interviews. Die Textmeldung gilt seit
§ 10.6 auch für einen Interview-Teil: die Empfangsbestätigung, die früher für Material
sprach, gibt es nicht mehr, und bei diesen Messwerten feuert sie ohnehin so gut wie nie.

Eine frühere Sorge aus dem Realbetrieb einer anderen Installation (Ausfälle, bis zu 30 s)
hat die Nachmessung **nicht bestätigt**. Die Architektur hängt trotzdem nicht an diesen
Zahlen: Datei zuerst sichern, nebenläufig transkribieren, Zeitbudget, Nachhol-Arbeiter.

### Reasoning

Hilft bei Mathematik und Symbolik (0/6 richtig ohne, 5/6 mit). Bringt bei **extraktiven und
sprachlichen** Aufgaben nichts außer Latenz (0,6 s gegen 14–16 s bei identischem Ergebnis).
Bei **Klassifikation mit Ausnahmen** — also dem Absichtserkenner — bricht die Trefferquote
laut Princeton-Studie um bis zu 36 Prozentpunkte **ein**.

**`reasoning_effort` ist bei Infomaniak binär**, und **das Feld wegzulassen schaltet
Reasoning AN**. Es gibt keine stille Voreinstellung „aus".

### Token-Schätzung

Zeichen ÷ 3, kein Tokenizer. Gemessen: 983 Zeichen ergaben 337 Prompt-Token, also **2,92**.
Der angenommene Wert 3 überschätzt leicht — die richtige Fehlerrichtung.

### Endprüfungen gegen die echten Dienste

**Absichtserkenner, 7 Fälle:** 7/7 richtig, **0 Falsch-Positive**, 0,3–3,0 s. Erkannte
`interview_starten`, `interview_beenden`, `kernthema_setzen: Ankommen`,
`verworfen: Kindheitsfragen – zu privat`. Blieb korrekt stumm bei einer
Beinahe-Entscheidung („find ich stark" / „mal sehen"), bei Geplauder und bei
Terminorganisation.

**Journal-Extraktor, 4 Abschnitte:** 4/4 richtig. Erzeugte selbsterklärende, pronomenfreie
Einträge; blieb bei „nur Zustimmung" leer **und** bei einem bereits entschiedenen Thema —
also keine Dopplung mit dem Absichtserkenner.

**Whisper nach dem MIME-Fix:** 1,8 s für 7 s Audio, 3,6 s für 30 s.

---

## (e) Was bewusst nicht gebaut wurde

| Nicht gebaut | Warum |
|---|---|
| **Die zwei Weboberflächen** | Team-Dashboard und Leseansicht je Gruppe. Der Weg von außen steht (`https://lab.artesmobiles.art/theatersoap/`, nginx auf *herkules*, Tailnet, Port 8010, Zertifikat geprüft) — nur die Anwendung fehlt. Siehe `NACHTRAG-weboberflaeche-und-sprache.md`. |
| ~~**Weiches Löschen**~~ (`entfernt_am`) | **Gebaut am 04.09.2026** (NACHTRAG N3): `entfernt_am` in `figur`, `szene`, `journal`, Arbeitsstandfelder auf NULL. Wege: Erkenner-art `entfernen`, `/figur … entfernen`, `/szene … entfernen`, `/kernthema aus`. Der ursprüngliche Grund („Überschreiben deckt den Alltagsfall ab") galt für Korrekturen, nicht fürs Zurücknehmen — eine Figur, die die Gruppe verwirft, lässt sich nicht überschreiben. **Material bleibt unentfernbar.** |
| ~~**Phasen als Zustand**~~ | **Gebaut am 04.09.2026** (`interview_theater/phasen.py`, `arbeitsstand.phase`): gesetzt nur hörbar — von der Gruppe (`phase_setzen`, `/phase`) oder vom Bot mit Meldung, nie still erraten. Je Phase ein Prompt (`prompts/phasen/N.md`), der den Fokus steuert, nicht den Informationszugang. **Am selben Abend inhaltlich korrigiert, am 05.09.2026 noch einmal** (SPEC § 0 Leitsatz 3, zweiter und dritter Nachtrag). Es sind jetzt **sieben** Phasen: 1 Begriffe · 2 Fragen · 3 Interviews · 4 Kernthema & Figuren · ~~5 Hauptkonflikt~~ · 6 Szenen · 7 Durchlauf — die Begriffe kommen aus dem Plenum, die Frageliste ist eine eigene Phase mit eigenem Feld, Kernthema und Figuren sind eine, und die Voraussetzung für 5 braucht beides. **Der automatische Sprung ist verworfen** (Datenstand ist nicht Absicht): der Bot fragt nach der nächsten Station, gesetzt wird sie nur von der Gruppe. Siehe auch `docs/entwurfsgeschichte.md` Korrektur 6 und 8.
> **Nachtrag 05.09.2026 früh.** Phase 5 heißt seit dem Probelauf „Format & Rahmen", nicht mehr „Hauptkonflikt" (Birk: „Es muss nicht immer einen Konflikt geben — es kann ein Lied sein oder eine harmonische Liebesszene. Das Ganze wird vermutlich ein Musical."). Details unten unter „Nacht 04./05.09." Punkt 2. |
| ~~**Szenen**~~ | **Gebaut am 04.09.2026** (`interview_theater/szene.py`): eigener Prompt, eigener Thread, Auslöser `szene_schreiben` und `/szene`, dazu die Blöcke 4/5 im Gesprächs-Kontext. Der ursprüngliche Grund („etwas zu schreiben, das niemand liest, ist Fläche ohne Nutzen") ist damit weggefallen — jetzt liest es der Gesprächs-Prompt. |
| **Sechs der vierzehn Befehle** | `SPEC` § 8.1 nennt je einen Grund. Zwei sind seit dem 04.09.2026 doch da: `/szene` mit den Szenentexten und `/figur` — letzterer aber **nur** als `/figur <Name> entfernen`; angelegt wird eine Figur weiterhin im Gespräch, und genau das war der ursprüngliche Grund gegen ihn. Dazu `/phase`, den die SPEC-Liste gar nicht kannte. |
| ~~**Modus B**~~ (`LLM.prosa`) | **Verdrahtet am 04.09.2026**, genau für den Anwendungsfall, dessen Fehlen ihn tot hielt: Szenentext. Das Latenzargument entfällt mit dem eigenen Thread — 34 s sind keine Gesprächspause, wenn niemand wartet. Einziger Aufruf mit Reasoning AN im ganzen System. |

**Nachgetragen: der Regressionskorpus ist gebaut.** Er stand hier bis zum
04.09.2026 als „nicht gebaut" — begründet damit, dass die Prompts an je 4–7
Fällen gemessen sind. Seit die Prompts heiß nachgeladen werden
(`interview_theater/anweisungen.py`), ändert sie jemand **während** des Workshops,
und damit wurde die Begründung hinfällig: gemessen war der Stand von gestern.

`korpus/` enthält jetzt 74 Absichtserkenner-Fälle (davon 29 Negativfälle, alle
fünfzehn `art`-Werte mindestens zweimal, `phase_setzen` und `entfernen` je
sieben-, `fragen_setzen` viermal), 22 Journal-Abschnitte (davon 11 leere) und
6 erfundene Interviewtranskripte. Die gemessenen Fälle aus (d) sind 1:1 darin,
einschließlich des Nemotron-Fehlers („Kindheitsfragen lassen wir weg" ist
`verworfen`, nicht `kernthema_setzen`). `scripts/pruefe_prompts.py` lässt ihn
gegen das echte Modell laufen, mit denselben Einstellungen wie der Bot;
`tests/test_korpus.py` und `tests/test_pruefe_prompts.py` prüfen Korpus und
Bewertung ohne Netz mit. **Die Regel steht in `AGENTS.md`: eine Änderung am
Erkenner-Prompt gilt nur, wenn FP = 0 bleibt** — der Exit-Code des Skripts
hängt genau daran.

Was der Korpus **nicht** ist: gemessen. Die Sollwerte sind gesetzt, nicht am
Modell erhoben — Ausnahme sind die Fälle, die aus (d) übernommen sind (sieben
Endprüfungen beim Erkenner, vier Abschnitte beim Journal). Der erste
vollständige Lauf gegen das echte Modell steht noch aus.

---

## (f) Offene Punkte und Risiken

**Ehrlich benannt, nach Schwere:**

1. **`bot.main()` ist als Ganzes nie getestet**, nur seine Bausteine. Der erste echte Start
   ist der erste Test der Verdrahtung.
2. **Die Schema-Migration ist nie an einer echten Altdatenbank gelaufen.** Sie ist gegen
   eine künstlich alte geprüft, aber es lag keine gewachsene vor. Beim ersten Start mit
   einer bestehenden `interview_theater.db` nachsehen, dass `interviewmodus_seit` und
   `letzte_journalisierte_message_id` ergänzt wurden **und die Nachrichten noch da sind**.
3. **Gesetzte, nicht gemessene Werte:** `HINWEIS_AB_S = 60` (wann der Bot beiläufig auf den
   Interviewmodus hinweist) · `SCHWELLE_VERDRAENGUNG = 2000` · `LETZTE_JOURNALEINTRAEGE = 12`
   · das kurze Fenster mit 8.000 Token · ~~`szene.DECKEL = 40.000` und
   `szene.TIMEOUT_S = 150`~~. Alle sind begründet, keiner ist gemessen. Bei den beiden
   Szenen-Werten ist die Fehlerrichtung bewusst gewählt: zu großzügig kostet Wartezeit,
   die niemand absitzt, zu knapp kostet den bezahlten Lauf.
   > **Nachtrag 05.09.2026 früh.** `szene.DECKEL` ist mit der Prompt-Umstellung auf
   > Struktur statt Transkript entfallen — alle Blöcke sind kurz, es gibt nichts mehr
   > zu kürzen. `szene.TIMEOUT_S` steht jetzt bei 600 s, `szene.MAX_TOKENS` bei
   > 200.000 (Infomaniak rechnet Eingabe und Ausgabe gegen ein gemeinsames
   > `max_total_tokens = 249.984`, HTTP 400 bei 250.000, gemessen). Beide Werte sind
   > damit auch nicht mehr „gesetzt, nicht gemessen": 12.000 Token liefen im Probelauf
   > zweimal im Denken leer, gemessen wurden 19.410 Antwort-Token beim ersten
   > erfolgreichen Lauf. Details in `AGENTS.md`, Falle 4.
4. **Zwei Aussetzer beim Anbieter beobachtet:** ein HTTP 502 (Wiederholung nach 0,7 s
   erfolgreich) und ein `ReadTimeout` (zweiter Versuch sofort erfolgreich). Die Wiederholung
   mit Backoff fängt beides ab — aber es zeigt, dass der Dienst nicht durchgehend stabil ist.
5. **Ein Modellaufruf lag bei 8,3 s** statt der üblichen unter 1 s. Vermutlich Warteschlange.
   Wenn das häufiger auftritt, ist es einen Blick wert.
6. **Toter Code — zum Teil erledigt (04.09.2026).** `LLM.prosa` und die Tabelle `szene` sind
   verdrahtet (`interview_theater/szene.py`, `SPEC` § 4.5 Nachtrag). Übrig bleiben
   `gruppe.gruendlich_naechster_zug` (gehörte zum gestrichenen `/gruendlich`, nicht zu den
   Szenen) und `telegram`s Feld `antwortet_auf_bot` (korrekt berechnet, aber seit der
   Auslöser-Änderung ungenutzt). Beides dokumentiert, keines schadet — aber es sollte
   entweder verdrahtet oder entfernt werden.
7. **Betriebsregeln, die nirgends erzwungen sind:** nie denselben Bot-Namen zweimal
   gleichzeitig starten (beide Nachhol-Arbeiter lüden dieselbe Datei hoch), nie zwei Bots in
   dieselbe Gruppe (`repo.sichere_gruppe` überschreibt `gruppe.bot_name` bei jeder
   Nachricht).
8. **`telegram.py` verkettet die Originalausnahme** (`raise ... from fehler`); deren
   Traceback enthält den Bot-Token weiterhin. Betrifft nur die lokale Logdatei, nicht die
   Vorfall-Tabelle und damit nicht das projizierte Dashboard — bewusst so belassen, weil die
   Kette beim Debuggen hilft.

---

## (g) Nach dem Workshop: wie man aus der Datenbank lernt

**Die Datenbank enthält vollständiges Auswertungsmaterial.** Nichts davon wurde für die
Auswertung gebaut — es fällt im Betrieb an, weil alles roh gespeichert wird.

### `aufruf` — was die Modelle gekostet und gebraucht haben

Je Aufruf: Art, Modell-Modus, geschätzte gegen **tatsächliche** Token, Antwort-Token,
`finish_reason`, Dauer, Erfolg.

- **Den Divisor nachjustieren:** `geschaetzte_token` gegen `tatsaechliche_token` über alle
  Aufrufe. Weicht das Verhältnis deutlich von 3 ab, gehört `kontext.schaetze` angepasst.
- **Latenzverteilung je Art** — insbesondere, ob die 8,3 s ein Einzelfall waren.
- **Fehlschläge:** `erfolg = 0` gruppiert nach `art` zeigt, welcher Aufruf am unzuverlässigsten
  war.

### `vorfall` — was schiefging, ohne dass es jemand merkte

Jede Art hat eine eigene Aussage: `kuerzung` (der Prompt wurde zu groß — wie oft, an welchem
Tag?) · `zitat_ungeprueft` (das Modell erfand Zitate — **die wichtigste Qualitätszahl**) ·
`fenster_verworfen` (Material fiel unbearbeitet raus) · `http_5xx`, `abgeschnitten`,
`transkription_fehlgeschlagen`, `extraktor_fehler`.

### `verdichtung_thema` — hielten die Belegzitate?

`zitat_geprueft = 0` gegen `= 1` ist die **direkte Messung der Halluzinationsrate** bei der
Verdichtung. Diese Zahl entscheidet, ob das Belegzitat-Prinzip trägt oder ob der Verdichter
einen besseren Prompt braucht.

### `journal` — arbeiteten die beiden Aufrufe sauber zusammen?

Nach `quelle` gruppieren (`erkenner` gegen `journal`) und nach `art`. Zu prüfen:
Gibt es **Doppeleinträge** — dieselbe Sache aus beiden Quellen? Wurden `vorgeschlagen`-Einträge
erzeugt, die nie zu einer Entscheidung führten? Und die entscheidende qualitative Frage:
**Liest sich ein Eintrag Wochen später noch verständlich, ohne den Ursprungskontext?** Das
war das erklärte Entwurfsziel (Pronomenverbot, selbsterklärende Sätze).

### `nachricht` — was für ein Gespräch war das?

Der vollständige Verlauf, mit Sprecher, Typ und Zeitstempel. Daraus:

- **Wie viel wurde gesprochen, wie viel getippt?** Die Entscheidung „Sprache ist auch
  Gesprächsbeitrag" steht und fällt damit.
- **Wie oft antwortete der Bot?** Seit er auf alles antwortet, ist die Frage, ob das im
  Betrieb als hilfreich oder als aufdringlich empfunden wurde. Falls Letzteres: `ist_ausloeser`
  in `ablauf.py` ist die eine Stelle, an der das zurückgedreht wird.
- **Wie lang waren die Sprachnachrichten wirklich?** `aufnahme.dauer_sekunden` gegen
  `klasse` zeigt, ob der mechanische Interviewmodus richtig geschaltet wurde — und ob
  `HINWEIS_AB_S = 60` ein brauchbarer Wert ist.

### Und das, was nicht in der Datenbank steht

Die eigentliche Frage lässt sich nur im Raum beantworten: **Hat das Werkzeug der Gruppe
geholfen, ein Stück zu entwickeln — oder hat es sie beschäftigt?** Die Zahlen oben können
das nur eingrenzen. Ein Bot mit tadelloser Trefferquote, der den Fluss der Probe stört, ist
gescheitert.

**Vor der Auswertung an die Löschzusage denken:** Wenn ausgewertet und dann gelöscht werden
soll, gehört die Reihenfolge vorher besprochen. `scripts/loeschen.py` entfernt eine Gruppe
vollständig — Datenbank und Audiodateien.

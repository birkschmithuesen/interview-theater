# Übergabe

Für jemanden — Mensch oder Agent —, der diese Arbeit beurteilen soll, ohne bei ihrer
Entstehung dabei gewesen zu sein.

**Stand:** 04.09.2026 · 336 Tests grün · 16 Module, 4.461 Zeilen · 47 Commits
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
Zeitbudget 45 s für Gesprächsbeiträge und 90 s für Interviews.

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
| **Weiches Löschen** (`entfernt_am`) | Überschreiben deckt den Alltagsfall ab; Entfernen ist seltener. Die Spalte fehlt noch. |
| **Szenen** | Sie entstehen erst in der letzten Workshop-Phase. Die Tabelle existiert, wird aber weder gelesen noch geschrieben — etwas zu schreiben, das niemand liest, ist Fläche ohne Nutzen. |
| **Acht der vierzehn Befehle** | `SPEC` § 8.1 nennt je einen Grund. |
| **Modus B** (`LLM.prosa`) | Vorhanden, aber von nirgendwo aufgerufen — **toter Code**, bewusst so benannt in `SPEC` § 4.5. Sein Anwendungsfall (Szenentext) existiert nicht, und 34 s Latenz sind unattraktiv, seit Sprache Gesprächsbeitrag ist. |

**Nachgetragen: der Regressionskorpus ist gebaut.** Er stand hier bis zum
04.09.2026 als „nicht gebaut" — begründet damit, dass die Prompts an je 4–7
Fällen gemessen sind. Seit die Prompts heiß nachgeladen werden
(`theatersoap/anweisungen.py`), ändert sie jemand **während** des Workshops,
und damit wurde die Begründung hinfällig: gemessen war der Stand von gestern.

`korpus/` enthält jetzt 42 Absichtserkenner-Fälle (davon 18 Negativfälle, alle
elf `art`-Werte mindestens zweimal), 22 Journal-Abschnitte (davon 11 leere) und
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
   einer bestehenden `theatersoap.db` nachsehen, dass `interviewmodus_seit` und
   `letzte_journalisierte_message_id` ergänzt wurden **und die Nachrichten noch da sind**.
3. **Gesetzte, nicht gemessene Werte:** `HINWEIS_AB_S = 60` (wann der Bot beiläufig auf den
   Interviewmodus hinweist) · `SCHWELLE_VERDRAENGUNG = 2000` · `LETZTE_JOURNALEINTRAEGE = 12`
   · das kurze Fenster mit 8.000 Token. Alle sind begründet, keiner ist gemessen.
4. **Zwei Aussetzer beim Anbieter beobachtet:** ein HTTP 502 (Wiederholung nach 0,7 s
   erfolgreich) und ein `ReadTimeout` (zweiter Versuch sofort erfolgreich). Die Wiederholung
   mit Backoff fängt beides ab — aber es zeigt, dass der Dienst nicht durchgehend stabil ist.
5. **Ein Modellaufruf lag bei 8,3 s** statt der üblichen unter 1 s. Vermutlich Warteschlange.
   Wenn das häufiger auftritt, ist es einen Blick wert.
6. **Toter Code:** `LLM.prosa`, `gruppe.gruendlich_naechster_zug`, die Tabelle `szene`,
   `telegram`s Feld `antwortet_auf_bot` (korrekt berechnet, aber seit der Auslöser-Änderung
   ungenutzt). Alles dokumentiert, nichts davon schadet — aber es sollte entweder verdrahtet
   oder entfernt werden.
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

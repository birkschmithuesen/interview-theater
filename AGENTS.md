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

Module unter `theatersoap/`:

| Modul | Zuständigkeit |
|---|---|
| `bot.py` | Startroutine, Long-Poll-Schleife, Begrüßung, Warmlaufen, Prozessaufsicht |
| `ablauf.py` | Gesprächszug: Sperre je `chat_id` fürs Sammeln, Kontextaufbau anstoßen, Antwort verschicken |
| `aufnahme.py` | Aufnahme-Pipeline: Download, Transkription, Verdichtung, Nachhol-Arbeiter, kurz/lang-Klassifizierung |
| `befehle.py` | Die sechs Slash-Befehle, laufen vor jedem Kontextaufbau und vor jedem Sprachmodell-Aufruf |
| `erkenner.py` | Absichtserkenner: erkennt Änderungsabsichten im Gesprächsverlauf, wendet sie an, baut die Sammelmeldung |
| `journal.py` | Journal-Extraktor: erkennt `vorgeschlagen`-Einträge im aus dem Fenster verdrängten Gesprächsabschnitt |
| `kontext.py` | Baut den Gesprächs-Prompt datengetrieben zusammen, inklusive zweistufiger Kürzung |
| `llm.py` | Sprachmodell-Client (chat/completions), robustes JSON-Auslesen, Retry bei 5xx/Timeout |
| `stt.py` | Whisper-Anbindung, zweistufig und asynchron |
| `telegram.py` | Dünner HTTP-Wrapper um die Telegram-Bot-API |
| `verdichter.py` | Verdichtet ein Transkript zu Zusammenfassung und Kernthemen mit Belegzitaten |
| `zitat.py` | Belegzitat-Verifikation: Teilstring-Vergleich nach Normalisierung |
| `repo.py` | Einzige SQL-Zugriffsschicht außer `db.py`, komplett `RLock`-serialisiert |
| `db.py` | Schema, Verbindungsaufbau samt PRAGMAs, Migration fehlender Spalten, Löschweg (`loesche_gruppe`) |
| `einstellungen.py` | Konfiguration ausschließlich über Umgebungsvariablen |
| `anweisungen.py` | Prompt-Texte mit Hot-Reload (mtime) + optionaler Regie-Zettel `betrieb/zusatz*.md` |
| `prompts/` | Die Prompt-Texte als eigene `.md`-Dateien (`system`, `erkenner`, `journal`, `verdichter`) |
| `web.py` | Weboberfläche: Routing, HTML und CSS für Dashboard und Gruppenseiten, `http.server`, nur Standardbibliothek |
| `web_daten.py` | Die Lesezugriffe dazu — read-only geöffnete Verbindung, reine Funktionen, `conn` rein, Dicts raus |

`scripts/loeschen.py` erfüllt die Löschzusage (löscht eine Gruppe vollständig,
Datenbank und Audioverzeichnis), `scripts/rauchtest.py` prüft echte
Betriebsannahmen gegen die echten Dienste, `scripts/backup-robocloud.sh`
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
- **Der Prompt ist datengetrieben, es gibt keine Phasen-Zustandsmaschine.**
  `kontext.baue()` lässt jeden Block weg, solange die zugrundeliegenden Daten
  leer sind. Biegt die Gruppe ab, ändert sich die Materiallage und der Prompt
  folgt automatisch — es gibt keinen gespeicherten Zustand, der ihr
  widersprechen könnte (SPEC § 6.1).
- **Verdichtungen werden nie nachträglich geändert.** Es gibt bewusst kein
  `aktualisiere_verdichtung()` in `repo.py`. Was einmal aus einem Interview
  verdichtet wurde, bleibt stehen; neue Erkenntnis gehört in den
  Arbeitsstand, nicht in eine Korrektur der Verdichtung.
- **Das Journal wird nur angehängt.** Kein `aktualisiere_journal()`, keine
  Löschfunktion. Verworfenes, Entwürfe in der Schwebe und das Warum hinter
  Entscheidungen stehen sonst nirgends außerhalb des kurzen Fensters (SPEC
  § 2).
- **Jede Tabelle außer `bot_zustand` hat `chat_id`.** Kein Ableiten über
  Umwege. Das macht die Löschzusage zu einem `DELETE … WHERE chat_id = ?` je
  Tabelle (`db.TABELLEN_MIT_CHAT_ID`, `db.loesche_gruppe`) — die einzige
  Ausnahme ist die getUpdates-Position pro Bot-Token, die keiner Gruppe
  zugeordnet ist.
- **Die Gruppe erfährt von einem Fehler nur, wenn sie ihn beheben kann oder
  gerade darauf wartet.** Ein gescheiterter Absichtserkenner- oder
  Journal-Lauf ist für die Gruppe unsichtbar (Wasserzeichen bleibt stehen,
  `vorfall` fürs Dashboard); ein gescheiterter Gesprächszug oder eine
  gescheiterte Transkription bekommt eine kurze, ehrliche Zeile, weil die
  Gruppe gerade darauf wartet oder selbst reagieren muss (SPEC § 11.1/§ 11.2).

## Die Fallen

Jede hier gemessen, keine geraten. Wer das nicht liest, verliert denselben
Nachmittag noch einmal.

1. **`TS_LLM_URL` braucht die volle URL inklusive `/chat/completions`.**
   Der Code hängt nichts an. Mit `.../openai/v1` allein antwortet der Server
   **HTTP 404**.

2. **Whisper liegt unter `/1/ai/{produkt}/...`, nicht unter
   `/2/.../openai/v1/`** — dort ebenfalls HTTP 404. Der Aufruf ist außerdem
   **zweistufig**: Absenden liefert eine `batch_id`
   (`POST .../openai/audio/transcriptions`), das Ergebnis wird gepollt
   (`GET .../results/{batch_id}`). Das Feld `data` in der Ergebnisantwort ist
   ein **JSON-String**, kein Objekt, und muss ein zweites Mal geparst werden
   (siehe `theatersoap/stt.py`).

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
   (`theatersoap/llm.py`, `LLM._anfrage`: das Feld wird deshalb **immer**
   gesendet). Reasoning ist überall aus; bei Klassifikation mit Ausnahmen
   (dem Absichtserkenner) senkt es die Trefferquote messbar. Eng verwandte
   Falle: Reasoning verbraucht das Ausgabebudget, bevor der eigentliche
   Inhalt beginnt — bei zu knappem `max_tokens` kommt HTTP 200 mit
   `content: null` und `finish_reason: "length"` zurück, ein stiller
   Durchfall statt eines Fehlers. Deshalb `MAX_TOKENS = 9000` und
   `finish_reason == "length"` wird explizit als Budget-, nicht als
   Formatfehler behandelt.

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

## Wo SPEC und Code auseinanderlaufen

`SPEC-kontext-architektur.md` § 8 beschreibt ursprünglich vierzehn Befehle
und einen Modus B (`/gruendlich`, freier Prosatext mit
`reasoning_effort: "medium"`, via `LLM.prosa()`). Nach dem ersten
Workshoptag wurde das auf die sechs Befehle in `befehle.py` reduziert (siehe
Commit „Sechs Befehle als Notausgang"): `/merken`, `/verworfen`,
`/konflikt`, `/begriffe`, `/figur`, `/name`, `/material` und `/gruendlich`
existieren in der SPEC, aber nicht mehr im Code. `LLM.prosa()` selbst ist
weiterhin vorhanden, wird aber aktuell nirgends aufgerufen. Wer an diesen
Stellen weiterbaut, sollte sich auf `befehle.py` verlassen, nicht auf die
SPEC-Tabelle.

`einstellungen.py` liest zusätzlich `TS_MODELL_ERKENNER` (Vorgabewert
`google/gemma-4-31B-it`) — diese Variable fehlt noch in
`docs/betrieb-env.beispiel`.

## Starten und testen

**Regelweg: systemd-User-Units, nie Handstart.** Zwei Handstarts desselben
Bots = beide bekommen `409 Conflict` bei `getUpdates`, keiner empfaengt —
passiert am 04.09.2026 zweimal. Unit-Vorlage `docs/theatersoap@.service`
(nach `~/.config/systemd/user/`, `daemon-reload`), Start ueber
`scripts/betrieb-start.sh <gruppe>` (waehlt Python 3.11 aus `.venv`/uv —
das System-Python 3.9 kann `X | None` nicht importieren).

```
systemctl --user enable --now theatersoap@gruppe1.service   # je Gruppe
systemctl --user restart theatersoap@gruppe1.service        # Neustart
tail -f betrieb/gruppe1.log                                 # Log je Gruppe
```

**Verhalten aendern ohne Neustart** (`theatersoap/anweisungen.py`): die vier
Prompts unter `theatersoap/prompts/` werden bei jedem Aufruf per mtime
geprueft und heiss nachgeladen. Fuer spontane Regieanweisungen gibt es
`betrieb/zusatz.md` (alle Bots) und `betrieb/zusatz.<TS_BOT_NAME>.md` (ein
Bot); der Inhalt wird ans Ende der Gespraechs-Systemanweisung gehaengt,
Loeschen der Datei nimmt ihn zurueck. Erkenner/Journal/Verdichter bekommen
bewusst keinen Zusatz (gemessene Few-Shot-Prompts). Bedienung aus Hermes:
Skill `interview-theater-live-ops`.

Umgebungsvariablen: siehe `docs/betrieb-env.beispiel` zum Kopieren nach
`betrieb/<name>.env`. Handstart nur zum Debuggen, und nur wenn die Unit
gestoppt ist:

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m theatersoap.bot
```

- `pytest` — die Testsuite unter `tests/`, läuft ohne Netzzugriff (Attrappen
  statt echter Dienste).
- `python -m scripts.rauchtest [pfad-zu-audio.ogg]` — **kein Test, läuft nie
  automatisch, kostet Geld.** Ein echter Aufruf gegen Sprachmodell und
  optional Whisper, zur Kalibrierung der Token-Schätzung und als
  Erreichbarkeitsprüfung vor einem Einsatz.
- `python scripts/loeschen.py <chat_id>` — der Löschweg: entfernt alle
  Datenbankzeilen einer Gruppe und ihr Audioverzeichnis, fragt vorher
  interaktiv nach Bestätigung. Es gibt bewusst keinen Löschbefehl im Chat.

## Weboberfläche

Ein einziger Prozess für alle Gruppen, neben den Bots:

```
TS_DB=betrieb/soap.db python -m theatersoap.web
```

Unit-Vorlage `docs/theatersoap-web.service` (nach `~/.config/systemd/user/`,
`daemon-reload`, dann `systemctl --user enable --now theatersoap-web`), Log
nach `betrieb/web.log`.

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `TS_DB` | — (Pflicht) | dieselbe SQLite wie die Bots, **read-only** geöffnet |
| `TS_WEB_BIND` | `127.0.0.1:8010` | im Betrieb `100.75.24.33:8010` (Tailnet) |
| `TS_WEB_PREFIX` | `/theatersoap` | Präfix, unter dem nginx den Server durchreicht |
| `TS_WEB_URL` | `https://lab.artesmobiles.art/theatersoap` | nur für `scripts/web_links.py` |

Routen: `/` (Team-Dashboard, projiziert, alle Gruppen), `/g/<token>`
(Leseansicht einer Gruppe, Handy), `/gesund` (Health-Check, antwortet ohne
Datenbankzugriff). Jede Route greift auch mit vorangestelltem
`TS_WEB_PREFIX`, weil erst die nginx-Konfiguration entscheidet, ob das
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

`TS_WEB_BIND` lehnt `0.0.0.0` mit einem Fehler ab: ein Tippfehler in einer
Env-Datei soll die Interviews nicht ins offene Netz stellen.

## Was bewusst fehlt

- **Weiches Löschen von Arbeitsstand-Einträgen.** Kein `entfernt_am`-Feld;
  Überschreiben ist der einzige Schreibpfad. Laut SPEC § 4.3 auf die Zeit
  nach dem ersten Workshoptag verschoben.
- **Das Schreiben von Szenen.** Die Tabelle `szene` wird bisher von niemandem
  gefüllt — `kontext.py` lässt den Block „aktuelle Szene im Volltext"
  ausdrücklich weg, er gehört zu einer späteren Workshop-Phase. Gelesen wird
  sie inzwischen: die Gruppenseite zeigt Szenen an, sobald welche dastehen.
- **Schreiben über die Weboberfläche.** Beide Seiten sind read-only, der
  einzige Schreibweg bleibt der Chat — sonst laufen zwei Schreibwege
  gegeneinander (`NACHTRAG-weboberflaeche-und-sprache.md` N1).

Die **Weboberflächen selbst sind gebaut** (`web.py`/`web_daten.py`, siehe
„Weboberfläche" unten).

# Die Fallen

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 2170–2277 und 1270–1365).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

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

   **Der Web-Kanal hängt an derselben Falle** (30.09.2026): `aufnahme.empfange`
   verdrahtete die Endung fest (`f"{message_id}.ogg"`), und ein WebM aus dem
   Browser hätte damit `audio/ogg` bekommen. Seitdem trägt
   `telegram.lies_nachricht` den optionalen Schlüssel `endung`, und
   `aufnahme.ENDUNG_VORGABE` ist nur noch der Rückfall. **Bekannte Grenze, nicht
   behoben:** auch im Telegram-Betrieb bekommt eine `audio`-Nachricht (m4a, mp3)
   oder ein Dokument heute einen `.ogg`-Pfad — derselbe Fehler eine Etage weiter,
   und er war schon vor dieser Karte da. `lies_nachricht` könnte die Endung aus
   `mime_type`/`file_name` ableiten; das ändert den Telegram-Pfad und wurde
   deshalb hier nicht angefasst.

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
   vermeidbar). Im Web-Kanal entsprechend: nie zwei Bot-Prozesse mit
   derselben `IT_WEB_CHAT_ID` — beide läsen dieselben `web_post`-Zeilen.

8. **Infomaniak drosselt Parallelität mit 429/5xx, nicht mit einer sauberen
   Warteschlange.** Betrifft im Betrieb kaum den Bot selbst (Aufrufe je
   Gruppe laufen ohnehin nacheinander), aber jeden eigenen Skriptlauf, der
   mehrere Anfragen gleichzeitig schickt — `scripts/pruefe_prompts.py` ruft
   deshalb sequenziell auf, nicht parallel. Wer ein Werkzeug baut, das mehrere
   Aufrufe gleichzeitig absetzt, bekommt sporadische 429/5xx statt eines
   verlässlichen Fehlers und sollte seriell bleiben oder selbst drosseln.

# Report Aufgabe 13: Browserlauf und Handy-Screenshot

Status: DONE

## Gebaut

- `tests/e2e/test_web_chat_e2e.py` (neu, 29 Tests): Chromium headless mit
  `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`, echter
  MediaRecorder, echter Webserver-Prozess (`python -m interview_theater.web`,
  Praefix `/theatersoap`, `IT_WEB_SEGMENT_MS=1200`), Wegwerf-DB
  `/tmp/it-webchat.db`, Handy-Kontext 390x844 (`is_mobile`, `has_touch`).
  Ueberspringt sich im normalen Lauf per `importorskip`.
- `tests/e2e/README.md`: Abschnitt zum Chat-Browserlauf (Flags, BotAttrappe,
  Messschicht, Segmentlaenge, Screenshot, Pfade).
- `docs/web-chat/handy-2026-09-30.png` (committet): Handy-Ansicht mit zwei
  Bot-Blasen, Knopfleiste "Stand zeigen", einer Gruppenblase, Interview-Knopf,
  PTT und Senden. Nur erfundene Fixture-Daten ("Die Ankommenden", Begriffe
  Ankommen/Arbeit/Nacht), kein Name (E8).

## Abgedeckte Faelle (alle im echten Browser)

Pflicht aus dem Brief: Verlauf, Text senden, Knopf (Druck angelegt, Leiste
aus), PTT < 0,5 s sendet nichts, PTT + pointercancel sendet nichts (mit
Nachweis, dass ein Recorder lief), PTT >= 0,5 s genau ein Upload,
Umschalter an/aus -> >= 2 Segmente, /interview zuerst, /fertig zuletzt,
PTT waehrend Aufnahme weg, Screenshot.

Aus der Liste des Task-11-Reports:
- B1+B8: Stopp mitten im Segment, stop-Ereignis des letzten Recorders
  1,5 s verzoegert -> POST-Folge exakt `an, audio x N, aus` mit N = Zahl der
  Recorder (das letzte Segment ist dabei); Knopf waehrend des Stopps
  disabled; danach alle Tracks `ended`, alle AudioContexts `closed`.
- Re-Review B: onstop von Segment 0 kommt nach dem von Segment 1 -> Uploads
  in Reihenfolge 0, 1 (per Blob-Groesse geprueft), dann /fertig.
- B7: Wegziehen (data-weg=1) + Loslassen aussen -> nichts; >= 500 ms innen ->
  genau ein Upload, kein /interview.
- B6: zwei schnelle Druecke -> zwei Uploads.
- B5: pointerup bevor getUserMedia aufloest -> kein Recorder-Start, Tracks
  gestoppt, nichts gesendet.
- B3: Upload 2x 503 -> #warteschlange zeigt "Keine Verbindung", dritter
  Versuch kommt an; Netzabbruch (route.abort) -> kommt an; 400 -> genau ein
  Versuch, Servertext in #fehler, nichts in der DB, Schlange leer.
- B2/C: Upload 3x 403 -> Zustands-Poll zwischen erstem und zweitem Versuch,
  vierter Versuch kommt an.
- A'/B4/Entscheidung I: Bot haengt -> Knopf bleibt "Aufnahme beenden",
  #warteschlange zeigt den Wartetext, nur `/interview` gesendet, kein
  Segment; Bot laeuft an -> Segmente kommen nach, Stopp schliesst sauber.
- F: gehaltener PTT, Interviewstart mit "zweitem Finger" -> kein PTT-Upload.
- B11: Seite im Interviewmodus geladen -> Stopp-Knopf, PTT unsichtbar; Stopp
  schickt nur /fertig.
- A/H + H2: Modusende durch "anderes Telefon" waehrend Aufnahme -> Recorder
  gestoppt, Uhr weg, Rest geparkt (Hinweis mit Zahl), Knopf bedienbar
  ("Interview aufnehmen"), PTT sichtbar, danach KEIN POST (kein stiller
  Upload, kein /fertig); "Rest als Interview nachreichen" -> exakt
  `an, audio x geparkt, aus`, Hinweis weg, Modus aus.
- H3: "Rest verwerfen" -> kein Upload.
- H1: Upload beim Modusende festgehalten, scheitert danach mit 503 -> wird
  geparkt (Zahl +1), Nachreichen-Knopf da, ein PTT danach kommt an
  (Schlange haengt nicht).
- H4: geparkt + fremdes Interview startet -> Nachreichen-Knopf weg, Hinweis
  nennt das andere Interview, kein POST; nach dessen Ende Knopf wieder da.
- B10: aendere_web_text / setze_web_knoepfe(None) / loesche_web_posts ->
  Blase geaendert, Leiste weg, Blase weg, ohne Neuladen.
- B12: Seite unter `/theatersoap/g/<t>/chat` pollt ausschliesslich auf
  `/theatersoap/g/<t>/chat/zustand?...` und sendet auf `.../chat/senden`;
  `/chat/` -> 404.
- data-segment-ms kommt beim Browser an.

Nicht gebaut: beforeunload-Dialog (B11 zweiter Teil) -- headless-Dialoge bei
`beforeunload` sind in Playwright nur ueber `page.close(run_before_unload=True)`
erreichbar und unzuverlaessig; der Fall bleibt beim Vertragstest.

## Abweichungen vom Brief (mit Grund)

1. **BotAttrappe** (Thread in der Testdatei): der Brief sagt "kein Bot laeuft
   mit", aber seit Aufgabe 11 geht ein Segment erst raus, wenn der Poll den
   Interviewmodus meldet (Entscheidung I). Ohne jemanden, der `/interview`
   verarbeitet, haette der Umschalter-Test nie ein Segment gesehen. Die
   Attrappe liest nur `typ='befehl'` aus `web_post` und ruft
   `repo.setze_interviewmodus`; mit `aktiv=False` spielt sie den haengenden
   Bot. Dieselbe Funktion `setze_modus` spielt das "zweite Telefon".
2. **Messschicht `_MESSUNG`** per `add_init_script` um MediaRecorder,
   getUserMedia, AudioContext und fetch (Zaehler, POST-Folge, optionale
   Verzoegerungen, Upload festhalten). Ohne Eingriff transparent. Noetig fuer
   die Reihenfolge- und Haenger-Faelle, die mit echtem Timing nicht
   zuverlaessig eintreten.
3. **Serverausgabe in eine Datei** (`/tmp/it-webchat-server.log`) statt
   `stdout=PIPE`: eine ungelesene Pipe ist nach 64 KiB voll, danach haengt
   der Server (jede Pollanfrage schreibt eine Logzeile).
4. Umschalter-Test: `/fertig` heisst im JS `POST chat/interview {an:false}`;
   geprueft ueber die DB (befehl +2) und die POST-Folge. Zusaetzlich wartet
   `test_waehrend_der_aufnahme_ist_ptt_weg` 2,5 s vor dem Stopp, damit der
   Stopp nicht in den noch offenen Start-Wechsel faellt.
5. Screenshot-Test steht frueh in der Datei (Verlauf noch sauber).
6. Plan Schritt 3 erwartete "2966 passed, 2 skipped" -- massgeblich ist der
   aktuelle Stand: 4513 passed, 2 skipped (die zweite uebersprungene Datei ist
   die neue).

## Gegenprobe (Mutation)

Vier absichtliche Fehler im JS (Wegziehen ignoriert, /fertig ohne Warten auf
offene Recorder, Loeschung ignoriert, parkeKopf aus) -> die zugehoerigen
Browsertests schlugen fehl (4 failed); Datei danach wiederhergestellt
(`git status` sauber). Kein echter Fehler im JS gefunden, `_CHAT_JS`
unveraendert.

## Befund nebenbei (nicht in dieser Aufgabe behoben)

`tests/e2e/test_web_edit_e2e.py::test_was_der_chat_fuehrt_steht_nur_da`
schlaegt fehl (auch allein): erwartet "4 · Setting & Figuren", die Phase
heisst seit dem Umbau "Setting, Figuren & Geschichte". Veralteter Test, nicht
durch diese Karte verursacht.

## Testlaeufe

- `python3 .superpowers/sdd/run.py WEBPY -m pytest tests/e2e/test_web_chat_e2e.py -q -p no:cacheprovider`
  -> `29 passed in 95.40s`; Wiederholung -> `29 passed in 100.67s`
- `python3 .superpowers/sdd/run.py WEBPY -m pytest tests/e2e -q -p no:cacheprovider`
  -> `1 failed, 47 passed` (der Altbefund oben)
- `python3 .superpowers/sdd/run.py PY -m pytest -q -p no:cacheprovider`
  -> `4513 passed, 2 skipped in 284.85s`

## Commits

- 4cc026e Browserlauf: Segmente, PTT-Abbruch, Warteschlange, Modusende und der Handy-Screenshot
- (folgt) Plan-Kaestchen Aufgabe 13 + Report

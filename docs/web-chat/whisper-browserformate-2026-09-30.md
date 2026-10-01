# Whisper und die Browserformate

**Gemessen am 01.10.2026** gegen den echten Infomaniak-Endpunkt, mit einer
Datei, die ein echter `MediaRecorder` erzeugt hat (nicht nachgebaut).

| Container/Codec | Browser | Endung | MIME (aus `stt.mime_typ`) | Ergebnis | Dauer |
|---|---|---|---|---|---|
| WebM/Opus | Chromium 149.0.7827.55 (headless, Playwright) | `.webm` | `audio/webm` | angenommen: Auftrag `success`, Text leer (siehe unten) | 6,1 s |
| mp4/AAC | Safari | `.m4a` | `audio/mp4` | ungeprueft, kein Safari erreichbar | — |

**Die Datei.** Ein Segment (19 616 Byte, EBML-Kopf `1A45DFA3`, DocType
`webm`) aus dem Browserlauf `tests/e2e/test_web_chat_e2e.py -k umschalter`
(Segmentlaenge im Test 1,2 s), abgelegt vom Web-Kanal unter
`web-eingang/` und vor der Pruefung nach `/tmp` kopiert — weder umbenannt
noch umgewandelt.

**Wie das Ergebnis zu lesen ist.** Chromium lief mit
`--use-fake-device-for-media-stream`: das Mikrofon liefert einen
synthetischen Ton, kein Sprechen. Der Auftrag kam deshalb nach 6,1 s mit
`status == 'success'` und **leerem** Text zurueck, und `stt.transkribiere`
meldete dafuer wie vorgesehen `STTFehler("leeres Transkript -- Stille ist
kein gueltiges Ergebnis")`. Das ist **kein** Fehlschlag des Formats: das
Fehlerbild „Format nicht unterstuetzt" waere ein Auftrag, der bis ins
Zeitbudget (rund 90 s) auf `pending` bleibt, oder ein Abbruchstatus bzw.
eine HTTP-Ablehnung — keines davon trat auf. Gemessen ist damit: der
Anbieter nimmt WebM/Opus aus dem Browser an und dekodiert es in Sekunden.
**Nicht** gemessen ist die Transkriptqualitaet gesprochener Sprache in
diesem Format; dafuer braucht es eine echte Aufnahme mit Stimme.

**Wie gemessen wurde.** Genau ein Whisper-Aufruf, ueber
`scripts.rauchtest.teste_whisper` (derselbe Weg wie
`python -m scripts.rauchtest <datei>`, Budget 90 s, Sprache `de`), aber ohne
den vorgeschalteten Sprachmodellaufruf von `rauchtest.main` — der haette
nichts zur Frage beigetragen und nur gekostet. `IT_DB` zeigte dabei auf eine
Wegwerf-Datei unter `/tmp`: `rauchtest.main` schreibt sonst in die
Datenbank aus `IT_DB`. `scripts/rauchtest.py` blieb unveraendert; es nimmt
jeden Pfad an, die Endung wertet erst `stt.mime_typ` aus.

**Warum das eigens gemessen wurde.** Falle 3: ein nicht unterstuetztes Format
wird nicht abgelehnt, sondern mit einer `batch_id` quittiert und bleibt
dauerhaft `pending` — 89,7 s statt 2,0 s, im Betrieb nur als „haengt"
sichtbar. Ein Format, das durch `stt._MIME_TYPEN` hindurchgeht, ist damit noch
nicht eines, das der Anbieter transkribiert.

**Folge fuer den Betrieb:** WebM geht; mp4 ist offen, weil kein Safari
erreichbar war. Fuer Chromium und Firefox ist der Web-Kanal fuer Interviews
einsatzbereit. Fuer iPhones gilt bis zu einer Messung mit einer echten
Safari-Aufnahme: Telegram (E1, Telegram bleibt Plan B). Faellt mp4 dann
durch, ist das **kein Workaround in dieser Karte:** ffmpeg liegt nicht im
PATH, und eine Konvertierung ist eine Entscheidung mit neuer Abhaengigkeit,
die Birk trifft.

**Was NICHT gemacht wurde und warum:** keine Konvertierung, kein
`ffmpeg`-Aufruf, kein Umbenennen einer Datei auf eine andere Endung. Das
Letztere waere genau Falle 3 noch einmal. Keine nachgebaute mp4-Datei: sie
haette den Container-Kopf von Safari nicht, und genau der ist die Frage.

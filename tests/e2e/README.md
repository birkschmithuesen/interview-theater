# tests/e2e — der Browserlauf

Ein echtes Chromium klickt auf der Gruppenseite. Was hier geprüft wird, prüft
`tests/test_web_edit.py` **nicht**: das Dropdown selbst, `_BEARBEITEN_JS`, der
fetch-Aufruf, der Nonce aus der Seite, das sanfte Nachladen — und ob nach
einem Neuladen wirklich der neue Wert dasteht.

Seit dem 06.09.2026 gehört die **Probenansicht** (`/g/<token>/textbuch`) dazu:
Rollenfilter, „Regieanweisungen ausblenden" und der geteilte Link
(`#figur=Pola&schrift=gross`) sind clientseitig — im Browser geklickt ist das
die einzige Stelle, an der sie wirklich laufen. `tests/test_web_textbuch.py`
prüft daneben, was der Server liefert.

Seit dem 30.09.2026 gehört der **Chat im Browser** dazu
(`/g/<token>/chat`, Karte Padua A2, `tests/e2e/test_web_chat_e2e.py`): der
MediaRecorder, die Segmente der Interview-Aufnahme, die Warteschlange für
Befehle und Segmente und Push-to-Talk mit `setPointerCapture` laufen **nur**
im echten Browser. `tests/test_web_chat_*.py` prüft daneben, was der Server
liefert (und `tests/test_web_chat_js.py` den Quelltext des Skripts);
`tests/test_web_e2e_http.py` fährt den ganzen Weg mit einem echten Bot, aber
ohne Browser.

Seit dem 30.09.2026 (Karte W) gehört die **vereinte Seite** (`/g/<token>`) dazu:
Tabwechsel während eines laufenden Streams und mit halb getipptem Text, die
Zurück-Taste, die Phasenleiste und der Phasenklick mit Rückfrage. Das ist die
einzige Stelle, an der sich messen lässt, dass der Wechsel wirklich nichts
verliert — im Server-Test sieht man nur, dass drei Panels ausgeliefert werden.
Screenshots gehen nach `docs/web-vereint/` und ins Repository: sie sind der
Beleg der Abnahme und zeigen deshalb ausschließlich erfundenes Material.

Chromium braucht dafür zwei Flags — sie stehen im Test:

    --use-fake-ui-for-media-stream      # Mikrofon ohne Rückfrage
    --use-fake-device-for-media-stream  # synthetischer Ton

Ein Bot läuft nicht mit, aber ein Interviewsegment geht erst raus, wenn der
Poll den Interviewmodus meldet. Den setzt im Lauf die `BotAttrappe` (ein
Thread, der `/interview` und `/fertig` aus `web_post` liest und
`repo.setze_interviewmodus` ruft — sonst nichts). Ein Init-Skript
(`_MESSUNG`) legt eine dünne Messschicht um MediaRecorder, `getUserMedia`,
AudioContext und `fetch`: es zählt Recorder-Starts und Blob-Größen, schreibt
die POST-Reihenfolge mit und kann ein `stop`-Ereignis verzögern,
`getUserMedia` bremsen oder einen Upload festhalten. Ohne Eingriff verhält
sich alles wie im echten Browser; Serverfehler (503, 403, 400, Netzabbruch)
kommen über `page.route`.

Die Segmentlänge ist im Lauf auf `SEGMENT_MS = 1200` verkürzt (im Betrieb
45 000, `einstellungen.VORGABE_SEGMENT_MS`) — sonst dauerte ein Test, der zwei
Segmente prüft, über eineinhalb Minuten. Der Server bekommt sie über
`IT_WEB_SEGMENT_MS`.

Der Handy-Screenshot (390×844) landet bei jedem Lauf in
`/tmp/it-webchat-shots/handy-2026-09-30.png`. Die committete Fassung in
`docs/web-chat/handy-2026-09-30.png` (nur erfundene Fixture-Daten, das
Artefakt, das Birk ansieht) wird nur mit `IT_SCHUSS_AKTUALISIEREN=1`
überschrieben — sonst wäre der Arbeitsbaum nach jedem Lauf schmutzig.

Die Druckversuche auf Push-to-Talk laufen als **Maus-Zeiger**
(`page.mouse`, `pointerId` 1); ein echter Touch-Zeiger selbst ist nicht
abgedeckt.

Wegwerf-Datenbank: `/tmp/it-webchat.db`, Audio unter `/tmp/it-webchat-audio`,
Serverlog `/tmp/it-webchat-server.log`, Adresse `127.0.0.1:<freier Port>` (vom
Betriebssystem vergeben, damit kein Altserver antwortet) — neben dem
Edit-Lauf, damit beide nebeneinander laufen können. Der Lauf dauert rund
100 Sekunden.

**Läuft nicht im normalen `pytest`-Lauf mit.** Dort gibt es kein Playwright,
und die Datei überspringt sich selbst (`pytest.importorskip`). Das ist
Absicht: die Testsuite soll ohne Browser und ohne Netz durchlaufen.

## Einmalig: das Wegwerf-venv

Playwright gehört nicht in die Projektabhängigkeiten — der Bot braucht es
nicht, der Webserver erst recht nicht (nur Standardbibliothek). Es liegt
deshalb in einem eigenen venv **auf dem Volume**, nicht im Repository:

```
python3.11 -m venv /mnt/HC_Volume_106183673/venvs/it-webtest
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/pip install \
    'playwright==1.61.0' pytest httpx
```

`playwright==1.61.0` ist kein Zufall: diese Fassung erwartet **chromium-1228**,
und genau das liegt im Cache unter `~/.cache/ms-playwright/`. Eine neuere
Playwright-Fassung will eine neuere Chromium-Revision und lädt sie herunter
(`playwright install chromium`) — was am Workshoptag niemand will. Wer die
Fassung anhebt, prüft vorher, was im Cache liegt:

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -c \
  "import json,pathlib,playwright; d=pathlib.Path(playwright.__file__).parent/'driver'/'package'/'browsers.json'; \
   print([(x['name'],x['revision']) for x in json.loads(d.read_text())['browsers']])"
```

`httpx` ist nur da, weil `tests/conftest.py` es importiert.

## Der Lauf

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e -q
```

Der Lauf startet sich seinen Server selbst (`python -m interview_theater.web`
als eigener Prozess) auf `127.0.0.1:8019`, gegen die **Wegwerf-Datenbank**
`/tmp/it-webtest.db` — nie gegen `IT_DB` aus dem Betrieb. Die Datenbank wird
zu Beginn neu aufgebaut, über `repo`, nicht über SQL.

Screenshots landen in `/tmp/it-webedit-shots/` (das Verzeichnis wird bei jedem
Lauf geleert).

## Von Hand nachsehen

Adresse und Datenbank stehen fest, damit man denselben Zustand ohne Playwright
anschauen kann:

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -c \
  "import sys; sys.path.insert(0,'.'); \
   from tests.e2e.test_web_edit_e2e import _baue_datenbank, DB_PFAD; \
   print(_baue_datenbank(DB_PFAD))"
IT_DB=/tmp/it-webtest.db IT_WEB_BIND=127.0.0.1:8019 python -m interview_theater.web
curl -s http://127.0.0.1:8019/g/<token>
```

# tests/e2e — der Browserlauf

Ein echtes Chromium klickt auf der Gruppenseite. Was hier geprüft wird, prüft
`tests/test_web_edit.py` **nicht**: das Dropdown selbst, `_BEARBEITEN_JS`, der
fetch-Aufruf, der Nonce aus der Seite, das sanfte Nachladen — und ob nach
einem Neuladen wirklich der neue Wert dasteht.

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

# Padua W: Web vereint — Tabs, Phasenuebersicht, Streaming

> **Fuer agentische Arbeiterinnen:** PFLICHT-UNTERSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Aufgabe fuer Aufgabe. Die Schritte tragen
> Kaestchen (`- [ ]`) zum Abhaken.

**Ziel:** Eine Gruppe arbeitet unter **einer** Adresse (`/g/<token>`) — Chat, Arbeitsstand und
Textbuch als Tabs im selben Dokument —, sieht oben eine schmale Phasenuebersicht mit Klick zum
Phasenwechsel, und liest die Antworten des Modells beim Entstehen (Streaming).

**Architektur:** Drei neue Module. `strom.py` (Dienste) dekodiert den wachsenden
JSON-Praefix eines Schema-Aufrufs und drosselt das Schreiben; `roadmap.py` (Fachlogik) macht
aus dem Datenstand die Phasenuebersicht — rein, wie `fehlstellen.aus_daten`; `web_vereint.py`
(Oberflaeche) baut die vereinte Seite und liefert den SSE-Kanal. Der Bot ruft das Modell und
schreibt Teiltexte in die neue Tabelle `web_strom`; der Webserver liest sie read-only und
schickt sie per Server-Sent Events an den Browser. Beide Prozesse teilen nur die SQLite-Datei
(WAL) — wie bei Karte A2.

**Technik:** Python 3.11, Standardbibliothek (`http.server`, `sqlite3`, `json`), `httpx`
0.28.1 fuer die Anbieterwege, Vanilla JS ohne Build, SQLite/WAL. Tests: `pytest` (ohne Netz,
ohne Browser) plus `tests/e2e` mit Playwright 1.61.0 aus dem Wegwerf-venv.

---

## Baseline (in diesem Worktree auf `d144715` selbst gemessen)

```
/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 \
  -m pytest -q -p no:cacheprovider
→ 2768 passed, 1 skipped in 205.06s
```

`PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
Die `.venv` im Hauptbaum wird **nicht** benutzt. Gemessen wurde auf dem Plan-Branch von A2 —
A1 und A2 sind darin noch **nicht** enthalten, ihre Tests kommen also oben drauf. Am Ende
dieser Karte gilt: die Zahl muss **≥ der Zahl sein, die der Umsetzungs-Branch beim ersten
Lauf in Aufgabe 1 zeigt** (dort gemessen und in die Abschlussaufgabe eingetragen), und
`1 skipped` bleibt (`tests/e2e` ueberspringt sich per `importorskip`).

---

## Praemissenkorrektur: der Chat-Zug IST ein Schema-Aufruf

Der Kartentext sagt „Nur Prosa streamt. Schema-/JSON-Aufrufe (Erkenner, Verdichtung) bleiben
blockierend." Am Code gemessen ist das so nicht haltbar:

```
interview_theater/ablauf.py:899   ergebnis = klm.schema(chat_id, system, koerper, SCHEMA, "gespraech")
interview_theater/ablauf.py:1025  ergebnis = klm.schema(chat_id, system, koerper, SCHEMA, "gespraech")
interview_theater/ablauf.py:364   SCHEMA = {"type": "object", ..., "properties": {"antwort": {"type": "string"}}}
```

Der Gespraechszug und der Auftragszug laufen ueber `LLM.schema` mit dem Schema
`{"antwort": string}`. Buchstabengetreu umgesetzt wuerde die Regel also **genau die
Antworten nicht streamen, die Birk streamen sehen will** — die Antwort des Bots im Chat.

**Entscheidung (gilt fuer diese Karte):**

| streamt | streamt nicht |
|---|---|
| Gespraechszug (`ablauf._erfrage_antwort`) | Erkenner |
| Auftragszug (`ablauf.auftragszug`) | Journal-Extraktor |
| Szenenlauf (`szene.schreibe` → `klm.prosa` / `szene_claude.prosa`) | Verdichter |
| Prosalauf (`kurzgeschichte._lauf`) | Sprachprofil, Schaerfung |
| | Szenenfolge-Vorschlag, Stueckpruefung, Dramaturgie |

Die Trennlinie ist nicht „Schema gegen Prosa", sondern **„liest ein Mensch das Ergebnis oder
eine Maschine"**. Alles, dessen Ergebnis maschinell weiterverarbeitet wird, bleibt
blockierend.

Damit ein Schema-Aufruf trotzdem streamen kann, braucht es genau eine neue reine Funktion:
`strom.wert_aus_praefix(praefix, feld)` dekodiert aus einem **unvollstaendigen** JSON-Text
den bisherigen Wert von `antwort` (Escapes `\n \" \\ \uXXXX`, halber Escape am Ende,
Surrogatpaare; kein Wert → `""`). **Kein Prompt und kein Response-Format aendert sich** —
der Korpus (`korpus/erkenner.jsonl`, `scripts/pruefe_prompts.py`) bleibt unberuehrt.

---

## Vorbedingung: A1 und A2 muessen in `main` sein

Diese Karte baut auf zwei Karten auf, die es beim Planen noch nicht gab:

* **A2** (`docs/superpowers/plans/2026-09-30-padua-a2-web-arbeitsplatz.md`, geplant, nicht
  umgesetzt): Tabelle `web_post`, `interview_theater/web_kanal.py` (`WebKanal` statt
  `telegram.Telegram`, Weiche `IT_KANAL=web`), `interview_theater/web_chat.py` (Chatansicht
  `/g/<token>/chat`, Polling per fetch, **kein SSE**), Spalte `gruppe.web_tippt_bis`,
  `scripts/web_gruppe.py`.
* **A1** (Branch `padua-workshop/t_28ed3dde-padua-a1-sprache-pro-workshop-profil-eng`,
  umgesetzt, nicht gemergt): `interview_theater/sprache.py`, `T = sprache.Texte(__name__)`,
  englische Tabelle `interview_theater/sprachen/en/texte.toml`,
  `tests/test_sprache_texte.py` mit den Mengen `UMGESTELLT` und `ALLE_MODULE`
  (`test_alle_module_sind_umgestellt` verlangt `UMGESTELLT == ALLE_MODULE`).

**Aufgabe 1 ist ein Vorbedingungs-Check.** Schlaegt er fehl, **bricht die Umsetzung ab** und
meldet genau das. A1 oder A2 nachzubauen ist ausdruecklich **verboten** — beide sind eigene
Karten mit eigener Abnahme, und zwei Fassungen von `web_kanal.py` waeren teurer als ein
Wartetag.

---

## Abweichungen von den Entscheidungen des Architekten (A–L), mit Beleg

Sieben Stellen, an denen dieser Plan von der Vorgabe abweicht. Jede mit Messung oder
Begruendung; alles Uebrige gilt wie vorgegeben.

1. **Zu B (Drosselung): nur ein Takt, kein Zeichen-Zweig.** Vorgabe war „hoechstens alle
   150 ms **oder** je 40 neue Zeichen"; zwei Regeln mit „oder" heben einander auf — bei
   einem schnellen Modell feuert die Zeichenregel alle paar Millisekunden und die 150 ms
   waeren wirkungslos. Es bleibt bei **einem** Wert: `strom.INTERVALL_S = 0.15` (hoechstens
   ~7 UPDATEs je Sekunde und laufendem Zug), dazu **immer** ein letzter Schreibvorgang beim
   Abschluss. Eine dreissig Sekunden lange Antwort sind damit ≤ 200 winzige UPDATEs auf
   einer WAL-Datenbank mit `busy_timeout = 5000` — gegen die Schreiblast des Bots (Nachricht,
   Aufruf, Journal je Zug) faellt das nicht ins Gewicht. Die Zahl steht an **einer** Stelle
   und ist ueber `Senke(intervall_s=…)` testbar.
2. **Zu E (fehlende `usage`): kein zweiter bezahlter Lauf.** Vorgabe war „keine usage im
   Stream → still auf Nicht-Stream zurueck". Das bemerkt man erst am **Ende** eines Streams;
   den Aufruf dann zu wiederholen kostet eine zweite vollstaendige Generierung **und** zeigt
   der Gruppe denselben Text zweimal. Stattdessen: die Zeile in `aufruf` wird gebucht wie
   sonst (mit `geschaetzte_token`, `tatsaechliche_token = NULL`), es gibt den Vorfall
   `strom_nicht_verfuegbar`, und eine **Prozessflagge** (`llm._STROM_AUS`) schaltet jeden
   **weiteren** Aufruf dieses Prozesses auf den Nicht-Stream-Weg. E7 steht damit ab dem
   zweiten Aufruf wieder auf exakten Zahlen, ohne dass ein einziger Lauf doppelt bezahlt
   wird. Fehler **vor** dem ersten Chunk und Abbruch **nach** dem ersten Chunk verhalten
   sich wie vorgegeben (stiller Rueckfall bzw. genau ein Wiederholungsversuch ohne Stream).
3. **Zu H (Weg des Klicks durch die A2-Naht): ein versteckter Befehl, kein neuer
   Eingangstyp.** Der Webserver legt den Klick als ganz gewoehnlichen A2-Eingang ab —
   `repo.lege_web_post_an(..., repo.WEB_TYP_BEFEHL, text=f"/phaseklick {n}")`. `WEB_TYP_BEFEHL`
   ist in A2 genau dafuer da („ein Umschalter-Druck, der als Slash-Text in den Bot geht und
   in der Chatansicht verborgen bleibt"), also aendert sich **nichts** an `web_post`,
   `web_kanal.hole_updates`, `bot.schleife` oder `telegram.py`. Im Bot fuehren `/phase` und
   `/phaseklick` durch **eine** Funktion `befehle.wechsle_phase(..., quelle)`; der einzige
   Unterschied ist `quelle="befehl"` gegen `quelle="web"` — genau das, was die Abnahme
   („gleiche Journalzeile bis auf Quelle") verlangt. `/phaseklick` steht **nicht** in
   `BEFEHLE_LISTE` (kein Menueeintrag) und wird nirgends beworben, wie `/leitfaden` und
   `/festlegung`.
4. **Zu F (CSS im gemeinsamen Dokument): Laufzeit-Scoping statt Umschreiben der
   Konstanten.** Gemessen am 30.09.2026 in diesem Worktree:

   ```
   $PY -c "…"  →  GRUPPE x TEXTBUCH: ['body', 'h1']
   ```

   dazu traegt `_CSS_TEXTBUCH` sechs Selektoren der Form `body[data-figur] …`,
   `body.ohne-regie …`, `body[data-schrift="…"] …` (der Zustand der Probenansicht haengt am
   `<body>`), und `_CSS_TEXTBUCH` **und** `_CSS_CHAT` (A2) definieren beide `.leiste` mit
   unvereinbarer Bedeutung (Rollenleiste gegen Knopfleiste). Deshalb bekommt `web_vereint`
   eine reine Funktion `scope_css(css, scope)`, die jeden Selektor einer Panel-CSS auf das
   Panel einschraenkt (`body` → der Scope selbst, alles andere → `<scope> …`).
   **Die bestehenden CSS-Konstanten bleiben Zeichen fuer Zeichen stehen**, die
   Einzelseiten (`/g/<token>/textbuch`, `/leitfaden`, Dashboard) aendern sich damit gar
   nicht — das ist billiger und sicherer, als drei CSS-Bloecke von Hand umzuschreiben.
5. **Zu G (Aufgabenliste der Roadmap): Namen genagelt, Pruefer eigen.** `phasentexte.PARAMETER`
   ist die eine Liste „welche Phase setzt was" — aber ihre Leser rufen `repo`
   (`phasentexte.parameterzeilen` → `repo.hole_arbeitsstand` …), und der Webserver bekommt
   keinen `repo`-Pfad (AGENTS.md, `fehlstellen`). `roadmap.AUFGABEN` traegt deshalb eigene
   **reine** Pruefer ueber Dicts, und ein Test nagelt Reihenfolge und Namen an
   `phasentexte.PARAMETER` fest:
   `[a.parameter for a in roadmap.AUFGABEN[p]] == [n for n, _, _ in phasentexte.PARAMETER[p]]`.
   Die Beschriftung kommt aus `phasentexte` (A1-Tabelle `PARAMETER_BESCHRIFTUNG`), es gibt
   also **keine** zweite Wunschliste und **keine** zweite Uebersetzung.
6. **Zu B/A2: SSE wird fuer genau einen Kanal erlaubt.** A2 schreibt „kein SSE" als globale
   Vorgabe. Diese Karte hebt das **ausschliesslich** fuer `GET /g/<token>/chat/strom` auf.
   Der Nachrichten-Poll aus A2 bleibt unveraendert der Weg fuer alles andere; faellt
   `EventSource` aus, zeigt der Poll die fertige Nachricht wie heute.
7. **Zu F (alte Adressen):** `/g/<token>/textbuch` (+ `.md`/`.txt`) und `/g/<token>/leitfaden`
   bleiben **eigenstaendige Seiten ohne Weiterleitung** (Druck, `@media print`, geteilte
   Rollenlinks mit Fragment). `/g/<token>/chat` aus A2 **leitet mit 302 auf
   `<praefix>/g/<token>#chat`** — die Chatansicht ist in der vereinten Seite aufgegangen,
   zwei Chats nebeneinander waeren zwei Zustaende. Das Team-Dashboard `/` bleibt
   unveraendert (Annahme der Karte, hier ausdruecklich festgehalten).

---

## Hotspots

Andere Karten (A1, A2, R, S, UX) arbeiten an denselben Dateien. Deshalb gilt:

| Datei | Regel in diesem Plan |
|---|---|
| `interview_theater/web.py` | **nur** Routing-Zeilen und die mechanische Extraktion `gruppe_koerper`/`textbuch_koerper` (Aufgaben 10, 11). Kein neues HTML, kein neues CSS. |
| `interview_theater/web_chat.py` (A2) | **nur** Weichen: `chat_koerper` herausloesen, `strom` im GET, `phase` in `_POSTWEGE`, `BASIS` im JS, `data-basis` im Rumpf (Aufgaben 8, 10, 11, 13). |
| `interview_theater/ablauf.py` | **nur** additive Parameter und die Senke-Aufrufe (Aufgabe 7). Keine Logikaenderung an `antworte`. |
| `interview_theater/szene.py`, `kurzgeschichte.py` | je **eine** Senke-Zeile am Aufruf und je eine am Abschluss (Aufgabe 7). |
| `interview_theater/llm.py`, `szene_claude.py` | additive Parameter `bei_teil`; ohne ihn ist der Anfragekoerper zeichengleich (Test). |
| `interview_theater/db.py` | eine `CREATE TABLE`, ein Eintrag in `TABELLEN_MIT_CHAT_ID`. **Keine** Erhoehung von `SCHEMA_VERSION` — rein additiv. |
| `interview_theater/repo.py`, `web_daten.py` | neue Funktionen am Dateiende, keine bestehende geaendert. |
| `interview_theater/befehle.py` | `wechsle_phase` herausloesen, `/phaseklick` anhaengen (Aufgabe 13). |
| `interview_theater/phasentexte.py` | **drei Zeilen**: `beschriftung()` als oeffentlicher Name (Aufgabe 9). |

Alles Neue geht in **neue Module**: `strom.py`, `roadmap.py`, `web_vereint.py`,
`scripts/strom_probe.py`.

---

## Globale Vorgaben

Gelten fuer **jede** Aufgabe, auch wenn dort nicht wiederholt:

- **Projektsprache Deutsch**, ASCII-Umschrift `ue/oe/ae/ss` in Code, Docstrings, Kommentaren
  und Commit-Zeilen. In Nutzertexten (HTML, Chat) sind echte Umlaute erlaubt, wie ueberall
  in `web.py`.
- **Neue Nutzertexte als modulweite `_TEXT_*`-Konstanten** und ueber `T = sprache.Texte(__name__)`
  gelesen (A1), mit englischem Eintrag in `interview_theater/sprachen/en/texte.toml`
  (Aufgabe 15). Ein neues Modul mit Nutzertext wird in `tests/test_sprache_texte.py`
  **beiden** Mengen hinzugefuegt (`UMGESTELLT` **und** `ALLE_MODULE`) — sie muessen gleich
  bleiben.
- **SQL nur in `repo.py` (schreibend) und `web_daten.py` (read-only).** `strom.py`,
  `roadmap.py` und `web_vereint.py` enthalten kein `SELECT`/`INSERT`/`UPDATE`/`DELETE`.
- **Kein Modellaufruf** in `web_vereint.py`, `roadmap.py` oder einem Knopf-/POST-Handler.
- **Kein Frontend-Build**, kein npm, kein WebSocket, kein Cookie, kein localStorage.
  Vanilla JS. Mobile zuerst (390×844).
- **E1: der Telegram-Weg bleibt unveraendert.** `telegram.Telegram` bekommt nichts dazu;
  ohne `bei_teil` ist jeder Anbieteraufruf zeichengleich wie heute (Test).
- **E6** Zugang allein ueber `/g/<token>`, kein Login. **E8** keine Vornamen.
- **Datenschutz:** Tests, Fixtures, Screenshots und Probelaeufe **nur** mit erfundenem
  Material (`simulation/interviews/`), **nie** `betrieb/**`.
- **Die drei Web-Grenzen gelten weiter:** kein Nachrichtentext/Transkript auf dem Dashboard,
  kein Volltranskript auf der Gruppenseite, kein Belegzitat ohne `zitat_geprueft = 1`.
- **Nie `git stash`** ohne `-m <tag>`; nie `checkout`/`switch`; committet wird ausschliesslich
  auf dem Branch der Umsetzungskarte (t_9c2921e2). Kein Merge, kein Push.
- Jede Aufgabe endet gruen: `$PY -m pytest -q -p no:cacheprovider` ≥ Baseline aus Aufgabe 1.

---

## Annahmen

Was beim Planen **nicht** geprueft werden konnte — je mit dem Kommando, das es klaert. Wer
eine Aufgabe anfaengt, in der eine Annahme steckt, fuehrt das Kommando **zuerst** aus.

**ANNAHME 1 (alle Aufgaben) — die A2-Flaeche heisst so, wie der A2-Plan sie nennt.**
Gelesen im Plan, nicht am Code: `web_kanal.WebKanal`, `web_chat.CHAT_PFAD`,
`web_chat._CHAT_JS`, `web_chat._POSTWEGE`, `web_chat.chat_html`, `web_chat._blase_html`,
`web_chat.beantworte_get/_post`, `web_chat._sende_zustand`, `repo.lege_web_post_an`,
`repo.RICHTUNG_EIN`, `repo.WEB_TYP_BEFEHL`, `web_daten.web_chatzustand`,
`web_daten.web_chatverlauf`, Spalte `gruppe.web_tippt_bis`.

```
$PY -c "
from interview_theater import repo, web_chat, web_daten, web_kanal
for n in ('lege_web_post_an','RICHTUNG_EIN','WEB_TYP_BEFEHL'): print('repo.'+n, hasattr(repo,n))
for n in ('CHAT_PFAD','_CHAT_JS','_POSTWEGE','chat_html','_blase_html','beantworte_get','beantworte_post','_sende_zustand'):
    print('web_chat.'+n, hasattr(web_chat,n))
for n in ('web_chatzustand','web_chatverlauf'): print('web_daten.'+n, hasattr(web_daten,n))
print('WebKanal', hasattr(web_kanal,'WebKanal'))"
```
Erwartet: ueberall `True`. Ein `False` → **Aufgabe 1 bricht ab**.

**ANNAHME 2 (Aufgaben 9, 15) — die A1-Flaeche.** `sprache.Texte`,
`phasentexte._beschriftung`, `phasentexte.PARAMETER_BESCHRIFTUNG`, und in
`tests/test_sprache_texte.py` die Mengen `UMGESTELLT`/`ALLE_MODULE`.

```
$PY -c "
from interview_theater import phasentexte, sprache
print('Texte', hasattr(sprache,'Texte'))
print('_beschriftung', hasattr(phasentexte,'_beschriftung'))
print('PARAMETER_BESCHRIFTUNG', hasattr(phasentexte,'PARAMETER_BESCHRIFTUNG'))"
grep -c "UMGESTELLT\|ALLE_MODULE" tests/test_sprache_texte.py
```

**ANNAHME 3 (Aufgabe 11) — `web_chat._CHAT_JS` baut seine URLs relativ** (`fetch('chat/zustand…')`),
weil die Chatansicht unter `/g/<token>/chat` liegt. Auf der vereinten Seite ist die Basis
`/g/<token>`, dieselbe relative URL loest dann auf `/g/chat/zustand` auf. Aufgabe 11 setzt
deshalb ein `BASIS`-Praefix vor jeden `chat/`-Pfad im JS. Traegt das JS die Pfade schon
absolut oder ueber eine eigene Konstante, ist der Schritt kuerzer — **dann im Commit
benennen, was stattdessen getan wurde**.

```
grep -n "chat/" interview_theater/web_chat.py | head -30
```

**ANNAHME 4 (Aufgabe 17, kostet Geld) — Infomaniak kann `stream: true` zusammen mit
`response_format: {"type":"json_schema"}` und liefert `usage` bei
`stream_options: {"include_usage": true}`.** Genau das misst Aufgabe 17. Kann es das
**nicht**, greift der Rueckfall aus Abweichung 2 automatisch: das Gespraech streamt dann
nicht, der Szenen-/Prosalauf (reine Prosa) weiterhin schon. **Das ist ein Befund fuer den
Abschlussbericht, keine Umgehung** — nichts am Prompt oder am Schema wird veraendert, um
Streaming zu erzwingen.

**ANNAHME 5 (Aufgabe 17, kostet Geld) — der lokale Proxy (127.0.0.1:28764) gibt
Anthropic-SSE weiter** (`message_start`, `content_block_delta`, `message_delta`,
`message_stop`). Pruefung ebenfalls in Aufgabe 17.

**ANNAHME 6 (Aufgabe 18) — nginx auf herkules puffert die SSE-Antwort nicht.** Die
nginx-Konfiguration liegt nicht im Repository. `X-Accel-Buffering: no` setzt der Server
selbst; ob es reicht, zeigt

```
curl -N -s https://lab.artesmobiles.art/theatersoap/g/<token>/chat/strom | head -5
```
(Teilstuecke muessen **einzeln** und nicht am Stueck erscheinen). Puffert es doch, ist das
ein Befund fuer Birk mit der Zeile `proxy_buffering off;` als Vorschlag — **keine
Repo-Aenderung**.

**ANNAHME 7 (Aufgaben 5, 6) — `httpx.Client.stream` steht zur Verfuegung.** Gemessen in
diesem Worktree: `httpx 0.28.1`, `hasattr(httpx.Client, "stream") → True`. Bleibt als
Nachweis stehen:

```
$PY -c "import httpx; print(httpx.__version__, hasattr(httpx.Client,'stream'))"
```
Erwartet: `0.28.1 True`.

**ANNAHME 8 (Aufgabe 16) — Playwright 1.61.0 + chromium-1228 im Wegwerf-venv**, wie in
`tests/e2e/README.md`.

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -c "import playwright; print(playwright.__version__)"
```

---

## Dateikarte

| Datei | Verantwortung | Aufgabe |
|---|---|---|
| `tests/test_w_vorbedingung.py` | **neu.** Haelt die A1/A2-Flaeche fest, auf der W steht | 1 |
| `interview_theater/strom.py` | **neu.** JSON-Praefix-Dekoder, `Senke` (Drosselung), `senke/schliesse/verwirf` | 2 |
| `interview_theater/db.py` | Tabelle `web_strom`, `TABELLEN_MIT_CHAT_ID` | 3 |
| `interview_theater/repo.py` | Schreib- und Bot-Lesezugriffe auf `web_strom` | 3 |
| `interview_theater/web_kanal.py` | `WebKanal.strom` / `.strom_abschluss` (die Senke, die schreibt) | 4 |
| `interview_theater/llm.py` | `bei_teil` in `schema`/`prosa`, Stream-Parser, Rueckfall | 5 |
| `interview_theater/szene_claude.py` | `bei_teil` in `prosa`, Anthropic-SSE | 6 |
| `interview_theater/ablauf.py`, `szene.py`, `kurzgeschichte.py` | die Senke an den vier Callsites | 7 |
| `interview_theater/web_daten.py` | `web_strom_lage`, `roadmap` (read-only) | 8, 9 |
| `interview_theater/web_vereint.py` | **neu.** SSE-Route, `scope_css`, die vereinte Seite, Phasenleiste, Phase-POST | 8, 11, 12, 13, 14 |
| `interview_theater/roadmap.py` | **neu.** Die Phasenuebersicht als Daten (rein) | 9 |
| `interview_theater/phasentexte.py` | `beschriftung()` als oeffentlicher Name | 9 |
| `interview_theater/web.py` | `gruppe_koerper`, `textbuch_koerper`, Routing | 10, 11 |
| `interview_theater/web_chat.py` | `chat_koerper`, `BASIS`, Weichen fuer `strom` und `phase` | 8, 10, 11, 13 |
| `interview_theater/befehle.py` | `wechsle_phase`, versteckter Befehl `/phaseklick` | 13 |
| `interview_theater/sprachen/en/texte.toml` | die englischen Texte der neuen Module | 15 |
| `tests/e2e/test_web_vereint_e2e.py` | **neu.** Browserlauf und Screenshots | 16 |
| `scripts/strom_probe.py` | **neu.** Der echte Lauf gegen Infomaniak und Proxy | 17 |
| `AGENTS.md`, `docs/betrieb-env.beispiel`, `docs/web-vereint/` | Betrieb und Doku | 18 |

---

## Aufgabenuebersicht

| # | Titel | kostet Geld |
|---|---|---|
| 1 | Vorbedingung A1/A2 und die Baseline dieses Branches | nein |
| 2 | `strom.py`: JSON-Praefix-Dekoder und die gedrosselte Senke | nein |
| 3 | Tabelle `web_strom` und ihre `repo`-Funktionen | nein |
| 4 | `WebKanal.strom` — die Senke, die schreibt | nein |
| 5 | `llm.py`: `bei_teil`, Stream-Parser, identische Buchung, Rueckfall | nein |
| 6 | `szene_claude.py`: Anthropic-SSE mit derselben Buchung | nein |
| 7 | Die vier Callsites: Gespraech, Auftrag, Szene, Kurzgeschichte | nein |
| 8 | Die SSE-Route `/g/<token>/chat/strom` | nein |
| 9 | `roadmap.py`: die Phasenuebersicht als Daten | nein |
| 10 | Die drei Koerper herausloesen (`gruppe_koerper`, `textbuch_koerper`, `chat_koerper`) | nein |
| 11 | `web_vereint.py`: `scope_css`, drei Panels, Hash-Tabs, Routing, alte URLs | nein |
| 12 | Das Stand-Panel laedt allein nach (`/g/<token>/teil/stand`) | nein |
| 13 | Phasenleiste und Phase per Klick (`/phaseklick`) | nein |
| 14 | Streaming in der Ansicht: die vorlaeufige Blase | nein |
| 15 | Englische Texte (A1) und `pruefe_profil dortmund-2026` | nein |
| 16 | Browserlauf und Screenshots (390×844 und 1366×900) | nein |
| 17 | **Echter Lauf: Stream gegen Infomaniak und Proxy** | **JA** |
| 18 | Betrieb, Doku, Abschluss | nein |

---

## Aufgabe 1: Vorbedingung A1/A2 und die Baseline dieses Branches

**Dateien:**
- Neu: `tests/test_w_vorbedingung.py`

**Schnittstellen — Konsumiert:** alles aus A1 und A2 (siehe ANNAHME 1 und 2).
**Schnittstellen — Produziert:** nichts. Diese Aufgabe stellt fest, ob weitergearbeitet
werden darf, und misst die Baseline dieses Branches.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_w_vorbedingung.py`:

```python
"""Worauf Karte W steht: die Flaeche der Karten A1 (Sprache) und A2 (Web-Kanal).

Kein Feature-Test -- ein **Abbruchkriterium**. Karte W wird headless
umgesetzt: faellt hier etwas aus, soll die Umsetzung stehenbleiben und das
melden, statt A1 oder A2 nachzubauen. Zwei Fassungen von ``web_kanal.py``
waeren teurer als ein Wartetag.

Der Test bleibt danach stehen: er ist die Liste der Namen, auf die W sich
stuetzt, und faellt auf, wenn eine spaetere Karte einen davon umbenennt.
"""

import pytest

from interview_theater import db, phasentexte, repo, sprache, web_chat, web_daten, web_kanal


@pytest.mark.parametrize("name", [
    "lege_web_post_an", "RICHTUNG_EIN", "WEB_TYP_BEFEHL", "hole_gruppe",
    "hole_arbeitsstand", "hole_szenen", "figuren", "verdichtungen",
])
def test_repo_traegt_was_w_braucht(name):
    assert hasattr(repo, name), f"repo.{name} fehlt -- Karte A2 nicht gemergt?"


@pytest.mark.parametrize("name", [
    "CHAT_PFAD", "_CHAT_JS", "_POSTWEGE", "chat_html", "_blase_html",
    "beantworte_get", "beantworte_post", "_sende_zustand",
])
def test_web_chat_traegt_was_w_braucht(name):
    assert hasattr(web_chat, name), f"web_chat.{name} fehlt -- Karte A2 nicht gemergt?"


@pytest.mark.parametrize("name", ["web_chatzustand", "web_chatverlauf", "oeffne_lesend",
                                  "chat_id_nach_token", "gruppe_nach_token"])
def test_web_daten_traegt_was_w_braucht(name):
    assert hasattr(web_daten, name)


def test_web_kanal_ist_die_kanalklasse():
    assert hasattr(web_kanal, "WebKanal")
    for name in ("sende", "sende_mit_knoepfen", "hole_updates", "tippt"):
        assert hasattr(web_kanal.WebKanal, name), name


def test_die_tippanzeige_hat_ihre_spalte(tmp_path):
    """``gruppe.web_tippt_bis`` (A2) -- die Roadmap liest sie fuer 'laeuft'."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_001, "gruppe1", "X")
    assert "web_tippt_bis" in repo.hole_gruppe(conn, 7_000_000_000_001).keys()


def test_die_sprachschicht_steht():
    """Karte A1: ``T = sprache.Texte(__name__)`` und die Beschriftungstabelle
    der Phasenparameter, aus der die Roadmap ihre Woerter nimmt."""
    assert hasattr(sprache, "Texte")
    assert hasattr(phasentexte, "PARAMETER_BESCHRIFTUNG")
    assert hasattr(phasentexte, "_beschriftung")
```

- [ ] **Schritt 2: Lauf**

```
$PY -m pytest tests/test_w_vorbedingung.py -q -p no:cacheprovider
```
Erwartet: alle passed.

**Faellt hier auch nur ein Test: ABBRECHEN.** Kein Nachbauen von A1 oder A2. Melden:
„Karte W kann nicht starten: `<name>` fehlt — A1/A2 sind nicht in main."

- [ ] **Schritt 3: Die Baseline dieses Branches messen**

```
$PY -m pytest -q -p no:cacheprovider
```
Die Zahl notieren (sie liegt ueber 2768, weil A1 und A2 eigene Tests mitbringen) und **hier
in den Plan eintragen**, hinter „Baseline dieses Branches:". Jede weitere Aufgabe misst
gegen diese Zahl.

Baseline dieses Branches: __________ passed, 1 skipped.

- [ ] **Schritt 4: Commit**

```bash
git add tests/test_w_vorbedingung.py docs/superpowers/plans/2026-09-30-padua-w-web-vereint.md
git commit -m "Web vereint: Vorbedingungstest fuer die A1/A2-Flaeche

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 2: `strom.py` — JSON-Praefix-Dekoder und die gedrosselte Senke

**Dateien:**
- Neu: `interview_theater/strom.py` (Schicht **Dienste**)
- Test: `tests/test_strom.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/strom.py
INTERVALL_S = 0.15

def wert_aus_praefix(praefix: str, feld: str = "antwort") -> str
def sichtbar(text: str) -> str

class Senke:
    def __init__(self, beginne, schreibe, beende, *,
                 intervall_s: float = INTERVALL_S, uhr=time.monotonic) -> None
    def __call__(self, text: str) -> None
    def neu(self) -> None
    def abbruch(self) -> None
    def fertig(self, post_id: int | None = None) -> None

def senke(tg, chat_id: int, art: str)                 # None ohne Strom-Kanal
def schliesse(tg, chat_id: int, post_id: int | None = None) -> None
def verwirf(tg, chat_id: int) -> None
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_strom.py`:

```python
"""Der Stromschicht-Kern: aus einem halben JSON den bisherigen Text lesen.

Warum das noetig ist (Praemissenkorrektur im Plan-Kopf): der Gespraechszug
laeuft ueber ``LLM.schema`` mit ``{"antwort": string}``. Was beim Streamen
ankommt, ist also nicht der Text, sondern ein waschsender JSON-Praefix --
und der endet mitten in einem Escape, mitten in einem ``\\uXXXX`` und
mitten in einem Surrogatpaar.

Nichts hier fasst eine Datenbank an: reine Funktionen, Tabellentests.
"""

import pytest

from interview_theater import strom


# -- der Dekoder ------------------------------------------------------------


@pytest.mark.parametrize("praefix,erwartet", [
    ("", ""),
    ("{", ""),
    ('{"antw', ""),
    ('{"antwort"', ""),
    ('{"antwort":', ""),
    ('{"antwort": ', ""),
    ('{"antwort": "', ""),
    ('{"antwort": "Hallo', "Hallo"),
    ('{"antwort": "Hallo"', "Hallo"),
    ('{"antwort": "Hallo"}', "Hallo"),
    ('{"antwort":"Hallo ihr"}', "Hallo ihr"),
    # Der Schluessel darf Leerraum um den Doppelpunkt haben.
    ('{"antwort"  :\n  "Hi', "Hi"),
])
def test_wachsender_praefix(praefix, erwartet):
    assert strom.wert_aus_praefix(praefix) == erwartet


@pytest.mark.parametrize("praefix,erwartet", [
    (r'{"antwort": "Zeile\n', "Zeile\n"),
    (r'{"antwort": "Zeile\\', "Zeile\\"),
    (r'{"antwort": "sie sagte \"ja\"', 'sie sagte "ja"'),
    (r'{"antwort": "Tab\there', "Tab\there"),
    # Halber Escape am Praefixende: der Backslash faellt weg, nicht der Satz.
    ('{"antwort": "Zeile\\', "Zeile"),
    (r'{"antwort": "Gruß', "Gruß"),
    # Halbe \u-Folge: weg, der Rest bleibt.
    (r'{"antwort": "Gru\u00', "Gru"),
    (r'{"antwort": "Gru\u', "Gru"),
])
def test_escapes(praefix, erwartet):
    assert strom.wert_aus_praefix(praefix) == erwartet


def test_surrogatpaar_wird_zusammengesetzt():
    assert strom.wert_aus_praefix(r'{"antwort": "ok 😀"}') == "ok \U0001F600"


def test_halbes_surrogatpaar_faellt_weg_statt_zu_sprengen():
    """Ein einzeln stehendes High-Surrogate laesst sich nicht nach UTF-8
    kodieren -- es wuerde den ``json.dumps`` der SSE-Nutzlast sprengen."""
    ergebnis = strom.wert_aus_praefix(r'{"antwort": "ok \ud83d')
    assert ergebnis == "ok "
    ergebnis.encode("utf-8")   # wirft nicht


def test_ein_anderes_feld_stoert_nicht():
    assert strom.wert_aus_praefix('{"denken": "egal", "antwort": "Text') == "Text"


def test_feldname_ist_waehlbar():
    assert strom.wert_aus_praefix('{"x": "abc', feld="x") == "abc"


# -- was sichtbar wird ------------------------------------------------------


def test_eine_fertige_markerzeile_erscheint_nie():
    """Entscheidung D: VORSCHLAG-Marker sieht die Gruppe nie -- auch nicht
    fuer einen Augenblick."""
    text = "Wie waere es damit?\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit"
    assert "VORSCHLAG" not in strom.sichtbar(text)
    assert "Heimat, Arbeit" in strom.sichtbar(text)


@pytest.mark.parametrize("angefangen", ["V", "VOR", "VORSCHLA", "VORSCHLAG",
                                        "VORSCHLAG BEGR"])
def test_eine_angefangene_markerzeile_erscheint_auch_nicht(angefangen):
    """Der Fall, den ``vorschlag.ohne_marker`` nicht kennt: die Markerzeile
    ist noch nicht fertig getippt."""
    assert strom.sichtbar(f"Wie waere es damit?\n{angefangen}") == "Wie waere es damit?"


def test_ein_gewoehnliches_wort_mit_v_bleibt_stehen():
    assert strom.sichtbar("Wir nehmen\nVier Figuren") == "Wir nehmen\nVier Figuren"


# -- die Drosselung ---------------------------------------------------------


class Uhr:
    """Eine Uhr, die nur weitergeht, wenn der Test es sagt."""

    def __init__(self) -> None:
        self.jetzt = 1000.0

    def __call__(self) -> float:
        return self.jetzt


@pytest.fixture
def aufbau():
    uhr = Uhr()
    geschrieben: list[tuple[int, str]] = []
    beendet: list[tuple[int, str, int | None]] = []
    zaehler = {"n": 0}

    def beginne() -> int:
        zaehler["n"] += 1
        return zaehler["n"]

    senke = strom.Senke(
        beginne,
        lambda sid, text: geschrieben.append((sid, text)),
        lambda sid, zustand, post_id: beendet.append((sid, zustand, post_id)),
        uhr=uhr,
    )
    return senke, uhr, geschrieben, beendet


def test_die_erste_zeile_geht_sofort_raus(aufbau):
    senke, _uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    assert geschrieben == [(1, "Hallo")]


def test_innerhalb_des_takts_wird_nichts_geschrieben(aufbau):
    senke, uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    uhr.jetzt += 0.05
    senke("Hallo ihr")
    assert geschrieben == [(1, "Hallo")]


def test_nach_dem_takt_wird_wieder_geschrieben(aufbau):
    senke, uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    uhr.jetzt += strom.INTERVALL_S
    senke("Hallo ihr")
    assert geschrieben == [(1, "Hallo"), (1, "Hallo ihr")]


def test_der_letzte_stand_geht_beim_abschluss_immer_raus(aufbau):
    """Sonst fehlte der Gruppe genau der Satz, auf den sie gewartet hat."""
    senke, _uhr, geschrieben, beendet = aufbau
    senke("Hallo")
    senke("Hallo ihr alle")          # innerhalb des Takts -- nicht geschrieben
    senke.fertig(post_id=42)
    assert geschrieben[-1] == (1, "Hallo ihr alle")
    assert beendet == [(1, "fertig", 42)]


def test_abbruch_beendet_ohne_nachricht(aufbau):
    senke, _uhr, _geschrieben, beendet = aufbau
    senke("halb")
    senke.abbruch()
    assert beendet == [(1, "abgebrochen", None)]


def test_neu_faengt_eine_zweite_zeile_an_statt_anzuhaengen(aufbau):
    """Entscheidung D: loest ``_ohne_echo`` einen zweiten Aufruf aus, beginnt
    der Strom neu -- sonst klebte die verworfene Antwort davor."""
    senke, uhr, geschrieben, beendet = aufbau
    senke("erster Versuch")
    senke.neu()
    uhr.jetzt += strom.INTERVALL_S
    senke("zweiter Versuch")
    assert beendet[0][1] == "abgebrochen"
    assert geschrieben[-1] == (2, "zweiter Versuch")


def test_zweimal_fertig_beendet_nur_einmal(aufbau):
    senke, _uhr, _geschrieben, beendet = aufbau
    senke("x")
    senke.fertig(1)
    senke.fertig(2)
    assert beendet == [(1, "fertig", 1)]


def test_ohne_ein_einziges_stueck_passiert_gar_nichts(aufbau):
    """Ein Aufruf, der sofort scheitert, soll keine leere Blase hinterlassen."""
    senke, _uhr, geschrieben, beendet = aufbau
    senke.abbruch()
    assert geschrieben == [] and beendet == []


# -- die drei Kanal-Helfer --------------------------------------------------


class OhneStrom:
    """So sieht ``telegram.Telegram`` aus: kein ``strom``."""


class MitStrom:
    def __init__(self) -> None:
        self.gerufen: list = []

    def strom(self, chat_id, art):
        self.gerufen.append(("strom", chat_id, art))
        return "senke"

    def strom_abschluss(self, chat_id, post_id=None, abgebrochen=False):
        self.gerufen.append(("ab", chat_id, post_id, abgebrochen))


def test_ein_kanal_ohne_strom_liefert_none_und_faellt_nicht_um():
    """E1: ``telegram.Telegram`` bekommt nichts dazu."""
    tg = OhneStrom()
    assert strom.senke(tg, 1, "gespraech") is None
    strom.schliesse(tg, 1, 5)     # wirft nicht
    strom.verwirf(tg, 1)          # wirft nicht


def test_ein_kanal_mit_strom_wird_gerufen():
    tg = MitStrom()
    assert strom.senke(tg, 7, "gespraech") == "senke"
    strom.schliesse(tg, 7, 5)
    strom.verwirf(tg, 7)
    assert tg.gerufen == [
        ("strom", 7, "gespraech"), ("ab", 7, 5, False), ("ab", 7, None, True),
    ]
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_strom.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.strom'`.

- [ ] **Schritt 3: `interview_theater/strom.py` schreiben**

```python
"""Der Strom: was ein Modell schreibt, waehrend es schreibt (30.09.2026, Karte W).

**Warum es dieses Modul gibt.** Der Gespraechszug laeuft ueber ``LLM.schema``
mit dem Schema ``{"antwort": string}`` (ablauf.SCHEMA) -- was beim Streamen
ankommt, ist also kein Text, sondern ein wachsender JSON-Praefix. ``json.loads``
scheitert daran bis zum letzten Zeichen. ``wert_aus_praefix`` liest den
bisherigen Wert heraus, mit allem, was ein abgeschnittener JSON-String an
Halbheiten mitbringt: ein Backslash ohne Folgezeichen, eine halbe
``\\uXXXX``-Folge, ein High-Surrogate ohne sein Low-Surrogate.

**Kein Prompt aendert sich dafuer.** Das Response-Format bleibt, wie es ist --
der Regressionskorpus (``korpus/``) gilt unveraendert weiter.

**Was sichtbar wird, ist schon gesaeubert** (Entscheidung D): ``sichtbar``
nimmt die VORSCHLAG-Markerzeilen heraus, und zwar auch die gerade erst halb
getippte -- sonst stuende fuer einen Augenblick ``VORSCHLAG BEGR`` im Chat.

**Die Drosselung liegt hier und nicht im Kanal**, damit sie einen Test hat,
der ohne Datenbank auskommt: ``Senke`` bekommt drei Rueckrufe (anlegen,
schreiben, beenden) und eine Uhr.

Schicht Dienste: nur ``vorschlag`` und Standardbibliothek, keine Datenbank,
kein ``repo``.
"""

import time

from interview_theater import vorschlag

#: Wie oft der laufende Text hoechstens in die Datenbank geschrieben wird.
#: **Ein** Wert und nicht zwei (Plan-Kopf, Abweichung 1): eine zweite Regel
#: "oder je N Zeichen" haette den Takt aufgehoben, weil ein schnelles Modell
#: N Zeichen in wenigen Millisekunden liefert. 0,15 s heisst hoechstens
#: ~7 winzige UPDATEs je Sekunde und laufendem Zug -- gegen die Schreiblast
#: eines Gespraechszugs (Nachricht, Aufruf, Journal) faellt das nicht ins
#: Gewicht, und die WAL-Datenbank hat ``busy_timeout = 5000``.
INTERVALL_S = 0.15

_EINFACH = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            "n": "\n", "r": "\r", "t": "\t"}
_HEX = "0123456789abcdefABCDEF"
_LEERRAUM = " \t\r\n"

#: Das erste Wort jeder Markerzeile (``vorschlag.py``). Hier steht es, um die
#: ANGEFANGENE Zeile zu erkennen -- ``vorschlag.ohne_marker`` kennt nur die
#: fertige.
_MARKERWORT = "VORSCHLAG"


def wert_aus_praefix(praefix: str, feld: str = "antwort") -> str:
    """Der bisherige Wert von ``feld`` aus einem unvollstaendigen JSON-Text.

    Leerer String, solange der Wert noch nicht angefangen hat -- nicht
    ``None``: der Aufrufer schreibt das Ergebnis in eine Blase, und "noch
    nichts" ist dort ein leerer Text."""
    marke = f'"{feld}"'
    i = praefix.find(marke)
    if i < 0:
        return ""
    j = i + len(marke)
    n = len(praefix)
    while j < n and praefix[j] in _LEERRAUM:
        j += 1
    if j >= n or praefix[j] != ":":
        return ""
    j += 1
    while j < n and praefix[j] in _LEERRAUM:
        j += 1
    if j >= n or praefix[j] != '"':
        return ""
    return _ohne_halbes_paar(_zeichen(praefix, j + 1))


def _zeichen(text: str, i: int) -> str:
    """Die Zeichen eines JSON-Strings ab ``i`` bis zum schliessenden
    Anfuehrungszeichen oder bis zum Ende des Praefix.

    Jede Halbheit am Ende faellt weg statt zu werfen: ein Backslash ohne
    Folgezeichen, eine halbe ``\\uXXXX``-Folge. Beim naechsten Stueck ist sie
    vollstaendig und kommt dann mit."""
    aus: list[str] = []
    n = len(text)
    while i < n:
        z = text[i]
        if z == '"':
            break
        if z != "\\":
            aus.append(z)
            i += 1
            continue
        if i + 1 >= n:
            break
        k = text[i + 1]
        if k in _EINFACH:
            aus.append(_EINFACH[k])
            i += 2
            continue
        if k == "u":
            roh = text[i + 2:i + 6]
            if len(roh) < 4 or any(c not in _HEX for c in roh):
                break
            aus.append(chr(int(roh, 16)))
            i += 6
            continue
        break
    return "".join(aus)


def _ohne_halbes_paar(text: str) -> str:
    """Surrogatpaare zusammensetzen, einzeln stehende wegwerfen.

    Ein einzelnes High-Surrogate laesst sich nicht nach UTF-8 kodieren -- es
    wuerde den ``json.dumps`` der SSE-Nutzlast sprengen, und ein Emoji, das
    eine Zehntelsekunde spaeter vollstaendig ankommt, ist den Absturz nicht
    wert."""
    aus: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        z = text[i]
        if "\ud800" <= z <= "\udbff":
            if i + 1 < n and "\udc00" <= text[i + 1] <= "\udfff":
                aus.append(chr(0x10000 + (ord(z) - 0xD800) * 0x400
                               + (ord(text[i + 1]) - 0xDC00)))
                i += 2
            else:
                i += 1
            continue
        if "\udc00" <= z <= "\udfff":
            i += 1
            continue
        aus.append(z)
        i += 1
    return "".join(aus)


def _faengt_marker_an(zeile: str) -> bool:
    """Koennte aus dieser Zeile noch eine Markerzeile werden?"""
    wort = zeile.strip().upper()
    if not wort:
        return False
    return _MARKERWORT.startswith(wort) or wort.startswith(_MARKERWORT)


def sichtbar(text: str) -> str:
    """Der Teiltext, wie die Gruppe ihn sehen darf: ohne Markerzeilen -- auch
    ohne die gerade erst angefangene."""
    kopf, trenner, letzte = text.rpartition("\n")
    if not trenner:
        return "" if _faengt_marker_an(text) else (vorschlag.ohne_marker(text) or "")
    if _faengt_marker_an(letzte):
        text = kopf
    return vorschlag.ohne_marker(text) or ""


class Senke:
    """Nimmt den bisherigen Text entgegen und schreibt ihn gedrosselt weg.

    Drei Rueckrufe statt einer Datenbank, damit dieses Modul in der
    Dienste-Schicht bleibt und der Test ohne SQLite auskommt:

    * ``beginne() -> int`` legt eine Stromzeile an und liefert ihre id,
    * ``schreibe(id, text)`` schreibt den bisherigen **sichtbaren** Text,
    * ``beende(id, zustand, post_id)`` schliesst sie ab.

    Angelegt wird erst beim ersten Stueck: ein Aufruf, der sofort scheitert,
    soll keine leere Blase hinterlassen."""

    def __init__(self, beginne, schreibe, beende, *,
                 intervall_s: float = INTERVALL_S, uhr=time.monotonic) -> None:
        self._beginne = beginne
        self._schreibe = schreibe
        self._beende = beende
        self._intervall_s = intervall_s
        self._uhr = uhr
        self._id: int | None = None
        self._zuletzt = 0.0
        self._offen = ""

    @property
    def strom_id(self) -> int | None:
        return self._id

    def __call__(self, text: str) -> None:
        text = sichtbar(text)
        if self._id is None:
            self._id = self._beginne()
            self._schreibe(self._id, text)
            self._zuletzt = self._uhr()
            self._offen = ""
            return
        if text == self._offen:
            return
        if self._uhr() - self._zuletzt < self._intervall_s:
            self._offen = text
            return
        self._schreibe(self._id, text)
        self._zuletzt = self._uhr()
        self._offen = ""

    def _spuele(self) -> None:
        if self._id is not None and self._offen:
            self._schreibe(self._id, self._offen)
            self._offen = ""

    def neu(self) -> None:
        """Ein zweiter Modellaufruf zum selben Zug (``_ohne_echo``,
        ``_ohne_denkspur``): die bisherige Zeile wird verworfen und eine neue
        begonnen -- angehaengt wuerde die verworfene Antwort sichtbar bleiben."""
        self.abbruch()

    def abbruch(self) -> None:
        if self._id is None:
            return
        self._beende(self._id, "abgebrochen", None)
        self._id = None
        self._offen = ""

    def fertig(self, post_id: int | None = None) -> None:
        if self._id is None:
            return
        self._spuele()
        self._beende(self._id, "fertig", post_id)
        self._id = None


def senke(tg, chat_id: int, art: str):
    """Die Senke des Kanals -- oder ``None``, wenn er keine hat.

    **Die eine Stelle**, an der ein Callsite nach Streaming fragt (Entscheidung
    C). ``telegram.Telegram`` bekommt nichts dazu und liefert deshalb ``None``;
    ``web_kanal.WebKanal`` liefert eine Senke, die in ``web_strom`` schreibt."""
    holen = getattr(tg, "strom", None)
    return holen(chat_id, art) if callable(holen) else None


def schliesse(tg, chat_id: int, post_id: int | None = None) -> None:
    """Der Strom dieses Zuges ist zu Ende und die Nachricht steht."""
    _abschluss(tg, chat_id, post_id=post_id, abgebrochen=False)


def verwirf(tg, chat_id: int) -> None:
    """Der Zug ist gescheitert oder die Antwort wurde verworfen -- die
    vorlaeufige Blase verschwindet, ohne dass eine Nachricht an ihre Stelle
    tritt."""
    _abschluss(tg, chat_id, post_id=None, abgebrochen=True)


def _abschluss(tg, chat_id: int, *, post_id: int | None, abgebrochen: bool) -> None:
    fertig = getattr(tg, "strom_abschluss", None)
    if callable(fertig):
        fertig(chat_id, post_id=post_id, abgebrochen=abgebrochen)
```

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_strom.py -q -p no:cacheprovider
```
Erwartet: alle passed (rund 45 Tests).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/strom.py tests/test_strom.py
git commit -m "Strom: JSON-Praefix-Dekoder und die gedrosselte Senke

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 3: Die Tabelle `web_strom` und ihre `repo`-Funktionen

**Dateien:**
- Aendern: `interview_theater/db.py` (`SCHEMA`, `TABELLEN_MIT_CHAT_ID`)
- Aendern: `interview_theater/repo.py` (neue Funktionen am Dateiende)
- Test: `tests/test_web_strom.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/repo.py
STROM_LAEUFT = "laeuft"
STROM_FERTIG = "fertig"
STROM_ABGEBROCHEN = "abgebrochen"

def beginne_strom(conn, chat_id: int, art: str) -> int
def schreibe_strom(conn, strom_id: int, text: str) -> None
def beende_strom(conn, strom_id: int, zustand: str, post_id: int | None = None) -> None
def hole_strom(conn, strom_id: int)
def laufende_stroeme(conn, chat_id: int) -> list
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_strom.py`:

```python
"""Die Tabelle web_strom: der laufende Text zwischen zwei Prozessen.

Der Bot ruft das Modell, der Webserver haengt am Browser -- sie teilen nur
die SQLite-Datei (WAL). Eine Zeile je laufendem Aufruf: der Bot schreibt
gedrosselt, der Webserver liest read-only und schickt die Deltas per SSE.
"""

import pytest

from interview_theater import db, repo

CHAT = 7_000_000_000_001
ANDERE = 7_000_000_000_002


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    return verbindung


def test_eine_zeile_entsteht_laufend(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_LAEUFT
    assert zeile["art"] == "gespraech"
    assert zeile["text"] == ""
    assert zeile["post_id"] is None


def test_text_waechst_und_die_zeit_rueckt_vor(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    vorher = repo.hole_strom(conn, sid)["aktualisiert_am"]
    repo.schreibe_strom(conn, sid, "Hallo")
    repo.schreibe_strom(conn, sid, "Hallo ihr")
    zeile = repo.hole_strom(conn, sid)
    assert zeile["text"] == "Hallo ihr"
    assert zeile["aktualisiert_am"] >= vorher


def test_abschluss_setzt_zustand_und_post_id(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=17)
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_FERTIG
    assert zeile["post_id"] == 17


def test_abbruch_laesst_keine_post_id_zurueck(conn):
    sid = repo.beginne_strom(conn, CHAT, "szene")
    repo.schreibe_strom(conn, sid, "halber Satz")
    repo.beende_strom(conn, sid, repo.STROM_ABGEBROCHEN)
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_ABGEBROCHEN
    assert zeile["post_id"] is None
    # Der Teiltext bleibt in der Zeile stehen -- er ist nie eine Nachricht
    # geworden, aber im Log der Gruppe nachvollziehbar, was zu sehen war.
    assert zeile["text"] == "halber Satz"


def test_laufende_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    meiner = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beginne_strom(conn, ANDERE, "gespraech")
    assert [z["id"] for z in repo.laufende_stroeme(conn, CHAT)] == [meiner]


def test_beendete_zaehlen_nicht_mehr_als_laufend(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=1)
    assert repo.laufende_stroeme(conn, CHAT) == []


def test_web_strom_steht_im_loeschweg():
    """Die Loeschzusage ist ein DELETE je Tabelle (db.loesche_gruppe) -- eine
    Tabelle mit chat_id, die dort fehlt, ueberlebt das Loeschen einer Gruppe."""
    assert "web_strom" in db.TABELLEN_MIT_CHAT_ID


def test_loesche_gruppe_nimmt_die_stroeme_mit(conn):
    repo.beginne_strom(conn, CHAT, "gespraech")
    db.loesche_gruppe(conn, CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_strom WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0


def test_migration_ruestet_die_tabelle_nach(tmp_path):
    """db.py migriert ausschliesslich additiv (AGENTS.md): eine Datenbank ohne
    die Tabelle bekommt sie beim naechsten Start, ohne user_version-Schritt."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    vorher = alt.execute("PRAGMA user_version").fetchone()[0]
    alt.execute("DROP TABLE web_strom")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)
    repo.sichere_gruppe(neu, CHAT, "gruppe1", "X")
    assert repo.beginne_strom(neu, CHAT, "gespraech") > 0
    assert neu.execute("PRAGMA user_version").fetchone()[0] == vorher
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_strom.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.repo' has no attribute 'beginne_strom'`.

- [ ] **Schritt 3: Schema in `db.py`**

In `SCHEMA`, **hinter** der Tabelle `web_post` (Karte A2), einfuegen. Die Form
(`CREATE TABLE IF NOT EXISTS <name> (` … `\n);`) ist Pflicht: `db._tabellenspalten_aus_schema`
liest sie per Regex, und daran haengt die additive Spaltenmigration.

```sql
-- Der laufende Text eines Modellaufrufs (30.09.2026, Karte W): eine Zeile je
-- laufendem Aufruf, deren ``text`` waechst, waehrend das Modell schreibt.
--
-- Warum ueber die Datenbank und nicht direkt: das Modell wird im BOT-Prozess
-- gerufen, der Browser haengt am WEB-Prozess (read-only, eigene Verbindung).
-- Die beiden teilen die SQLite-Datei und sonst nichts -- ein Kanal zwischen
-- ihnen ist eine Tabelle.
--
-- ``text`` ist der SICHTBARE Teiltext (strom.sichtbar): VORSCHLAG-Markerzeilen
-- stehen hier nie drin, auch nicht halb getippt.
--
-- Eine abgebrochene Zeile BLEIBT stehen, mit ihrem Teiltext: sie ist nie eine
-- Nachricht geworden (kein halber Text in ``nachricht``, ``web_post`` oder
-- ``journal``), aber der Betreiber soll nachlesen koennen, was im Chat kurz
-- zu sehen war.
CREATE TABLE IF NOT EXISTS web_strom (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  art             TEXT NOT NULL,            -- 'gespraech' | 'szene' | 'prosa'
  text            TEXT NOT NULL DEFAULT '',
  zustand         TEXT NOT NULL,            -- 'laeuft' | 'fertig' | 'abgebrochen'
  post_id         INTEGER,                  -- web_post.id der fertigen Nachricht
  begonnen_am     TEXT NOT NULL,
  aktualisiert_am TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_web_strom_lage
  ON web_strom(chat_id, id);
```

`TABELLEN_MIT_CHAT_ID` bekommt `"web_strom"` (hinter `"web_post"`).

**`SCHEMA_VERSION` bleibt unveraendert.** Die Migration ist rein additiv.

- [ ] **Schritt 4: Lauf, die beiden Schema-Tests muessen durch sein**

```
$PY -m pytest tests/test_web_strom.py -q -p no:cacheprovider -k "loeschweg or migration"
```
Erwartet: `2 passed` (`test_loesche_gruppe_nimmt_die_stroeme_mit` braucht noch `repo`).

- [ ] **Schritt 5: `repo.py` — die Funktionen**

Am Dateiende anhaengen, jede mit dem vorhandenen `@_gesperrt`-Dekorator (AGENTS.md, Falle 6).

```python
# --- Der laufende Text (30.09.2026, Karte W) -------------------------------

STROM_LAEUFT = "laeuft"
STROM_FERTIG = "fertig"
STROM_ABGEBROCHEN = "abgebrochen"


@_gesperrt
def beginne_strom(conn, chat_id: int, art: str) -> int:
    """Legt die Zeile fuer einen laufenden Aufruf an und liefert ihre id."""
    jetzt = _jetzt()
    zeiger = conn.execute(
        "INSERT INTO web_strom (chat_id, art, text, zustand, begonnen_am, "
        "aktualisiert_am) VALUES (?, ?, '', ?, ?, ?)",
        (chat_id, art, STROM_LAEUFT, jetzt, jetzt),
    )
    conn.commit()
    return zeiger.lastrowid


@_gesperrt
def schreibe_strom(conn, strom_id: int, text: str) -> None:
    """Der bisherige sichtbare Text. Wird gedrosselt gerufen
    (``strom.INTERVALL_S``), nicht je Zeichen."""
    conn.execute(
        "UPDATE web_strom SET text = ?, aktualisiert_am = ? WHERE id = ?",
        (text, _jetzt(), strom_id),
    )
    conn.commit()


@_gesperrt
def beende_strom(conn, strom_id: int, zustand: str,
                 post_id: int | None = None) -> None:
    """Schliesst die Zeile ab. ``post_id`` ist die ``web_post``-Zeile der
    fertigen Nachricht -- daran erkennt die Ansicht, welche vorlaeufige Blase
    sie durch welche Nachricht ersetzt."""
    conn.execute(
        "UPDATE web_strom SET zustand = ?, post_id = ?, aktualisiert_am = ? "
        "WHERE id = ?",
        (zustand, post_id, _jetzt(), strom_id),
    )
    conn.commit()


@_gesperrt
def hole_strom(conn, strom_id: int):
    return conn.execute(
        "SELECT * FROM web_strom WHERE id = ?", (strom_id,)
    ).fetchone()


@_gesperrt
def laufende_stroeme(conn, chat_id: int) -> list:
    """Die noch offenen Zeilen dieser Gruppe, aelteste zuerst.

    Die Roadmap liest sie fuer den Zustand 'laeuft' -- und nur sie: ein
    Szenenlauf-Lock lebt im Bot-Prozess und ist fuer den Webserver
    unsichtbar."""
    return conn.execute(
        "SELECT * FROM web_strom WHERE chat_id = ? AND zustand = ? ORDER BY id ASC",
        (chat_id, STROM_LAEUFT),
    ).fetchall()
```

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_strom.py -q -p no:cacheprovider
```
Erwartet: `9 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/db.py interview_theater/repo.py tests/test_web_strom.py
git commit -m "Web vereint: Tabelle web_strom als Kanal zwischen Bot und Webserver

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 4: `WebKanal.strom` — die Senke, die schreibt

**Dateien:**
- Aendern: `interview_theater/web_kanal.py` (zwei Methoden am Klassenende)
- Test: `tests/test_web_kanal_strom.py` (neu)

**Schnittstellen — Konsumiert:** `strom.Senke` (Aufgabe 2), `repo.beginne_strom` … (Aufgabe 3).
**Schnittstellen — Produziert:**

```python
# interview_theater/web_kanal.py, in WebKanal
def strom(self, chat_id: int, art: str) -> strom_modul.Senke
def strom_abschluss(self, chat_id: int, post_id: int | None = None,
                    abgebrochen: bool = False) -> None
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_kanal_strom.py`:

```python
"""Der Web-Kanal bekommt eine Senke, der Telegram-Kanal nicht (E1).

Die Senke ist der einzige Ort, an dem ein laufender Modelltext in die
Datenbank geht. Sie merkt sich ihre Zeile im Kanal, damit ``ablauf.antworte``
sie nach dem Versand abschliessen kann, ohne sie durch drei Funktionen
durchzureichen.
"""

import pytest

from interview_theater import db, repo, strom, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def kanal(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio")), conn


def test_telegram_bekommt_keine_senke():
    """E1: der Telegram-Weg bleibt Zeichen fuer Zeichen, wie er war."""
    assert not hasattr(telegram.Telegram, "strom")
    assert not hasattr(telegram.Telegram, "strom_abschluss")


def test_die_senke_legt_erst_beim_ersten_stueck_an(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    assert repo.laufende_stroeme(conn, CHAT) == []
    senke("Hallo")
    assert [z["text"] for z in repo.laufende_stroeme(conn, CHAT)] == ["Hallo"]


def test_der_abschluss_traegt_die_post_id_ein(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    senke("Hallo ihr")
    tg.strom_abschluss(CHAT, post_id=99)
    zeile = repo.hole_strom(conn, senke.strom_id)
    assert (zeile["zustand"], zeile["post_id"]) == (repo.STROM_FERTIG, 99)


def test_ein_abbruch_hinterlaesst_keine_nachricht(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    senke("halb")
    tg.strom_abschluss(CHAT, abgebrochen=True)
    assert repo.hole_strom(conn, senke.strom_id)["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.laufende_stroeme(conn, CHAT) == []


def test_ein_abschluss_ohne_laufenden_strom_tut_nichts(kanal):
    tg, _conn = kanal
    tg.strom_abschluss(CHAT, post_id=5)   # wirft nicht


def test_die_hilfsfunktionen_finden_den_kanal(kanal):
    """``strom.senke``/``schliesse``/``verwirf`` sind die EINE Stelle, an der
    ein Callsite nach Streaming fragt (Entscheidung C)."""
    tg, conn = kanal
    senke = strom.senke(tg, CHAT, "gespraech")
    senke("Text")
    strom.schliesse(tg, CHAT, 3)
    assert repo.hole_strom(conn, senke.strom_id)["post_id"] == 3


def test_ein_zweiter_strom_beendet_den_ersten_nicht_versehentlich(kanal):
    """Zwei Zuege hintereinander: der zweite bekommt eine eigene Zeile."""
    tg, conn = kanal
    erste = tg.strom(CHAT, "gespraech")
    erste("a")
    tg.strom_abschluss(CHAT, post_id=1)
    zweite = tg.strom(CHAT, "gespraech")
    zweite("b")
    tg.strom_abschluss(CHAT, post_id=2)
    assert erste.strom_id != zweite.strom_id
    assert repo.hole_strom(conn, erste.strom_id)["post_id"] == 1
    assert repo.hole_strom(conn, zweite.strom_id)["post_id"] == 2
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_kanal_strom.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: 'WebKanal' object has no attribute 'strom'`.

- [ ] **Schritt 3: `web_kanal.py` ergaenzen**

Im Modulkopf `from interview_theater import strom as strom_modul` ergaenzen, im
`__init__` eine Zeile `self._stroeme: dict[int, strom_modul.Senke] = {}`, und am Ende der
Klasse:

```python
    # --- Der laufende Text (30.09.2026, Karte W) ---------------------------

    def strom(self, chat_id: int, art: str):
        """Eine Senke fuer diesen Zug: was das Modell schreibt, geht gedrosselt
        in ``web_strom`` und von dort per SSE in den Browser.

        Der Kanal merkt sich die Senke je ``chat_id``, damit ``ablauf.antworte``
        sie nach dem Versand ueber ``strom.schliesse(tg, chat_id, message_id)``
        abschliessen kann -- ohne sie durch ``_erfrage_antwort`` und zwei
        Nachfassfunktionen durchzureichen (``ablauf.py`` ist Hotspot mehrerer
        Karten).

        ``telegram.Telegram`` hat diese Methode **nicht**: dort gibt es nichts
        zu streamen, und E1 sagt, dass der Telegram-Weg unveraendert bleibt."""
        vorher = self._stroeme.pop(chat_id, None)
        if vorher is not None:
            vorher.abbruch()
        senke = strom_modul.Senke(
            lambda: repo.beginne_strom(self._conn, chat_id, art),
            lambda sid, text: repo.schreibe_strom(self._conn, sid, text),
            lambda sid, zustand, post_id: repo.beende_strom(
                self._conn, sid, zustand, post_id),
        )
        self._stroeme[chat_id] = senke
        return senke

    def strom_abschluss(self, chat_id: int, post_id: int | None = None,
                        abgebrochen: bool = False) -> None:
        """Schliesst die Senke dieses Zuges ab. Ohne laufenden Strom passiert
        nichts -- der Aufrufer weiss nicht, ob es einen gab, und soll es auch
        nicht wissen muessen."""
        senke = self._stroeme.pop(chat_id, None)
        if senke is None:
            return
        if abgebrochen:
            senke.abbruch()
        else:
            senke.fertig(post_id)
```

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_kanal_strom.py tests/test_web_kanal_naht.py -q -p no:cacheprovider
```
Erwartet: alle passed. **Faellt der Naht-Test** (A2, prueft per AST, dass `WebKanal` jede
auf `tg` gerufene Methode hat): `strom`/`strom_abschluss` werden in `interview_theater/`
nur ueber `getattr` gerufen (`strom.senke`, `strom._abschluss`), tauchen also nicht als
`tg.strom(...)` auf — der Naht-Test darf davon nichts merken. Sieht er sie doch, ist
`strom.py` versehentlich mit `tg.strom(...)` geschrieben; das ist zu korrigieren, nicht der
Test.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/web_kanal.py tests/test_web_kanal_strom.py
git commit -m "Web-Kanal: die Senke, die den laufenden Text in web_strom schreibt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 5: `llm.py` — `bei_teil`, Stream-Parser, identische Buchung, Rueckfall

**Dateien:**
- Aendern: `interview_theater/llm.py`
- Test: `tests/test_llm_strom.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/llm.py
def schema(self, chat_id, system, nutzer, schema, art, modell=None,
           temperature=None, bei_teil=None, teil_feld="antwort") -> dict
def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
          bei_teil=None) -> str
def strom_moeglich() -> bool
def vergiss_strom() -> None      # nur fuer Tests
```

**Der Vertrag von `bei_teil`:** es bekommt **immer den bisherigen sichtbaren Gesamttext**
(nicht das Delta) — bei `schema` den mit `strom.wert_aus_praefix(…, teil_feld)` dekodierten
Feldwert, bei `prosa` den rohen Text. `reasoning_content`-Deltas gehen **nie** hinein.
Optional darf das Objekt `.abbruch()` und `.neu()` haben (`strom.Senke`); ein blankes
`lambda` genuegt.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_llm_strom.py`:

```python
"""Streaming bei Infomaniak: gleiche Rueckgabe, gleiche Buchung, sauberer Rueckfall.

Der Kern dieser Datei ist der Vergleich: derselbe Aufruf einmal mit und
einmal ohne ``bei_teil`` muss dieselbe ``aufruf``-Zeile hinterlassen
(prompt_tokens, completion_tokens, finish_reason, erfolg) -- sonst steht der
Kostendeckel (E7, Karte S) beim Streamen auf Sand.

Kein Netz: httpx.MockTransport spielt den Anbieter.
"""

import json

import httpx
import pytest

from interview_theater import db, llm, repo

CHAT = 7_000_000_000_001


class Einstellungen:
    llm_url = "https://example.invalid/v1/chat/completions"
    llm_key = "geheim"
    llm_modell = "moonshotai/Kimi-K2.6"
    bot_name = "gruppe1"


@pytest.fixture(autouse=True)
def frischer_prozesszustand():
    llm.vergiss_strom()
    yield
    llm.vergiss_strom()


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "X")
    return verbindung


def _sse(stuecke, usage=True, finish="stop"):
    """Baut eine OpenAI-Stream-Antwort aus Textstuecken."""
    zeilen = []
    for stueck in stuecke:
        zeilen.append("data: " + json.dumps(
            {"choices": [{"delta": {"content": stueck}, "finish_reason": None}]}
        ))
    zeilen.append("data: " + json.dumps(
        {"choices": [{"delta": {}, "finish_reason": finish}]}
    ))
    if usage:
        zeilen.append("data: " + json.dumps(
            {"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 34}}
        ))
    zeilen.append("data: [DONE]")
    return ("\n\n".join(zeilen) + "\n\n").encode("utf-8")


_FERTIG = {
    "choices": [{"message": {"content": '{"antwort": "Hallo ihr"}'},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 34},
}

#: Das JSON kommt in fuenf Stuecken -- der Dekoder sieht also jeden Zwischenstand.
_STUECKE = ['{"antw', 'ort": "Hal', "lo ", "ihr", '"}']


def _klient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _aufrufzeile(conn):
    return conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()


# -- ohne bei_teil bleibt alles, wie es war ---------------------------------


def test_ohne_bei_teil_steht_kein_stream_im_koerper(conn):
    """E1 im Kleinen: ein Aufrufer, der nichts von Streaming weiss, schickt
    denselben Anfragekoerper wie vor dieser Karte."""
    gesehen = {}

    def handler(anfrage):
        gesehen["body"] = json.loads(anfrage.content)
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech")
    assert "stream" not in gesehen["body"]
    assert "stream_options" not in gesehen["body"]


# -- mit bei_teil ------------------------------------------------------------


def test_stream_liefert_mehr_als_ein_teilstueck(conn):
    teile = []

    def handler(anfrage):
        assert json.loads(anfrage.content)["stream"] is True
        assert json.loads(anfrage.content)["stream_options"] == {"include_usage": True}
        return httpx.Response(200, content=_sse(_STUECKE))

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=teile.append)
    assert len(teile) > 1
    assert teile == [t for t in teile if isinstance(t, str)]
    # Der Dekoder liefert den bisherigen Wert, nie das rohe JSON.
    assert all("antwort" not in t for t in teile)
    assert teile[-1] == "Hallo ihr"
    assert ergebnis == {"antwort": "Hallo ihr"}


def test_der_endtext_ist_der_rueckgabewert(conn):
    teile = []
    klm = llm.LLM(Einstellungen(),
                  _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE))), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=teile.append)
    assert ergebnis["antwort"] == teile[-1]


def test_die_aufrufzeile_ist_dieselbe_wie_ohne_stream(conn):
    """Die Abnahme der Karte: ``aufruf``-Kosten wie ohne Stream."""
    klm_ohne = llm.LLM(Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)), conn)
    klm_ohne.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech")
    ohne = _aufrufzeile(conn)

    klm_mit = llm.LLM(Einstellungen(),
                      _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE))), conn)
    klm_mit.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                   bei_teil=lambda t: None)
    mit = _aufrufzeile(conn)

    for spalte in ("art", "modus", "geschaetzte_token", "tatsaechliche_token",
                   "antwort_token", "finish_reason", "erfolg"):
        assert mit[spalte] == ohne[spalte], spalte


def test_prosa_streamt_den_rohen_text(conn):
    teile = []
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        conn,
    )
    text = klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=teile.append)
    assert teile == ["Es war ", "Es war einmal"]
    assert text == "Es war einmal"


def test_reasoning_geht_nie_an_bei_teil(conn):
    """Die Denkspur ist nie fuer die Gruppe (Entscheidung C)."""
    inhalt = (
        'data: {"choices": [{"delta": {"reasoning_content": "ich ueberlege"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "Hallo"}}]}\n\n'
        'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'
        'data: {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}\n\n'
        "data: [DONE]\n\n"
    ).encode("utf-8")
    teile = []
    klm = llm.LLM(Einstellungen(),
                  _klient(lambda a: httpx.Response(200, content=inhalt)), conn)
    klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=teile.append)
    assert teile == ["Hallo"]


def test_finish_reason_length_bleibt_ein_budgetfehler(conn):
    """Fehlerbild 3 aus dem Moduldocstring gilt im Stream genauso."""
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["halb"], finish="length"))),
        conn,
    )
    with pytest.raises(llm.LLMFehler) as fehler:
        klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=lambda t: None)
    assert "abgeschnitten" in str(fehler.value)


# -- Rueckfall ---------------------------------------------------------------


def test_abbruch_nach_dem_ersten_stueck_wird_ohne_stream_wiederholt(conn):
    """Entscheidung E: kein halber Text wird zur Nachricht -- die Gruppe
    bekommt die vollstaendige Antwort aus einem zweiten, blockierenden Lauf."""
    versuche = []

    def handler(anfrage):
        body = json.loads(anfrage.content)
        versuche.append(bool(body.get("stream")))
        if body.get("stream"):
            # Zwei Stuecke, dann reisst die Verbindung.
            return httpx.Response(200, content=(
                'data: {"choices": [{"delta": {"content": "Hal"}}]}\n\n'
                'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n'
            ).encode("utf-8") + b"data: {kaputt")
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=Senke())
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert versuche == [True, False]
    assert abbrueche == [True]
    # Genau EINE Buchung, obwohl zwei HTTP-Aufrufe noetig waren: der Zug ist
    # einer, und ``_anfrage`` bucht im finally.
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1


def test_ein_4xx_auf_stream_faellt_still_zurueck(conn):
    """Kennt der Anbieter ``stream`` nicht, laeuft der Zug blockierend weiter --
    und der Vorfall sagt einmal, warum."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(400, json={"error": "unknown parameter"})
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    assert klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                      bei_teil=lambda t: None) == {"antwort": "Hallo ihr"}
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" in arten


def test_nach_einem_fehlschlag_streamt_der_prozess_nicht_mehr(conn):
    """Eine Prozessflagge, kein Dauerversuch: der zweite Aufruf geht sofort
    blockierend -- sonst zahlte jede Antwort den Fehlversuch mit."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(400, json={"error": "unknown parameter"})
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
               bei_teil=lambda t: None)
    assert llm.strom_moeglich() is False
    teile = []
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
               bei_teil=teile.append)
    assert teile == []


def test_ohne_usage_wird_nicht_zweimal_bezahlt(conn):
    """Abweichung 2 im Plan-Kopf: eine fehlende usage merkt man erst am ENDE.
    Den Aufruf zu wiederholen kostete eine zweite Generierung und zeigte der
    Gruppe denselben Text zweimal. Also: Vorfall, Prozessflagge, weiter."""
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE, usage=False))),
        conn,
    )
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=lambda t: None)
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1
    zeile = _aufrufzeile(conn)
    assert zeile["erfolg"] == 1 and zeile["tatsaechliche_token"] is None
    assert zeile["geschaetzte_token"] > 0     # E7 steht nie ganz ohne Zahl da
    assert llm.strom_moeglich() is False
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_llm_strom.py -q -p no:cacheprovider
```
Erwartet: FAIL — `TypeError: schema() got an unexpected keyword argument 'bei_teil'`.

- [ ] **Schritt 3: `llm.py` erweitern**

Am Modulkopf ergaenzen:

```python
#: Ist Streaming bei diesem Anbieter ueberhaupt moeglich? Eine
#: PROZESSflagge, kein Dauerversuch (Plan Karte W, Abweichung 2): hat der
#: Anbieter ``stream: true`` einmal abgelehnt oder keine ``usage`` geliefert,
#: geht jeder weitere Aufruf dieses Prozesses sofort blockierend -- sonst
#: zahlte jede Antwort den Fehlversuch mit, und E7 (Kostendeckel) stuende
#: dauerhaft auf geschaetzten Zahlen.
_STROM_AUS = False


def strom_moeglich() -> bool:
    return not _STROM_AUS


def vergiss_strom() -> None:
    """Nur fuer Tests: die Prozessflagge zuruecknehmen."""
    global _STROM_AUS
    _STROM_AUS = False


class _StromNichtVerfuegbar(Exception):
    """Der Anbieter hat den Stream abgelehnt -- BEVOR ein Stueck kam."""


class _StromAbbruch(Exception):
    """Der Stream ist mitten drin abgerissen -- NACH dem ersten Stueck."""
```

`schema` und `prosa` bekommen die Parameter und reichen sie durch:

```python
    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort") -> dict:
        """… (bestehender Docstring bleibt) …

        ``bei_teil`` (30.09.2026, Karte W): eine Senke, die den bisherigen
        Text bekommt, waehrend er entsteht. **Sie bekommt nicht das rohe
        JSON**, sondern den mit ``strom.wert_aus_praefix`` dekodierten Wert von
        ``teil_feld`` -- der Gespraechszug laeuft ueber dieses Schema, und was
        die Gruppe sehen soll, ist der Satz und nicht die Verpackung.
        Ohne ``bei_teil`` ist der Anfragekoerper zeichengleich wie vorher."""
        koerper = self._anfrage(
            chat_id=chat_id, system=system, nutzer=nutzer, art=art, modus="A",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": art, "strict": True, "schema": schema},
            },
            modell=modell, temperature=temperature,
            bei_teil=bei_teil, teil_feld=teil_feld,
        )
        text = self._text_aus(koerper)
        return lies_json(text)
```

`prosa` analog mit `bei_teil=bei_teil` (ohne `teil_feld`, also `None`).

`_anfrage` bekommt `bei_teil=None, teil_feld=None` und ersetzt den einen Aufruf von
`_sende_mit_wiederholung` durch:

```python
            koerper = self._hole(
                body, chat_id=chat_id, art=art, timeout=timeout,
                bei_teil=bei_teil, teil_feld=teil_feld,
            )
```

`_baue_body` bekommt `stream: bool = False` und haengt am Ende an:

```python
        if stream:
            # ``stream_options.include_usage`` ist der Grund, warum die
            # ``aufruf``-Zeile im Stream dieselbe sein kann wie ohne: ohne das
            # Feld liefert der OpenAI-Weg gar keine Tokenzahlen, und E7
            # (Kostendeckel) stuende auf Schaetzungen.
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
```

Neu, zwischen `_anfrage` und `_baue_body`:

```python
    def _hole(self, body: dict, *, chat_id, art, timeout, bei_teil, teil_feld) -> dict:
        """Ein Anbieteraufruf -- streamend, wenn eine Senke da ist, sonst wie
        immer. Liefert in **beiden** Faellen denselben Koerper, damit alles
        danach (``_text_aus``, ``lies_json``, die Buchung im ``finally`` von
        ``_anfrage``) unveraendert weiterlaeuft."""
        if bei_teil is None or not strom_moeglich():
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        strom_body = dict(body)
        strom_body["stream"] = True
        strom_body["stream_options"] = {"include_usage": True}
        try:
            koerper = self._sende_strom(strom_body, timeout=timeout,
                                        bei_teil=bei_teil, teil_feld=teil_feld)
        except _StromNichtVerfuegbar as fehler:
            self._melde_strom_aus(chat_id, art, f"abgelehnt: {fehler}")
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        except _StromAbbruch as fehler:
            # Entscheidung E: KEIN halber Text wird zur Nachricht. Die
            # vorlaeufige Blase verschwindet, und genau EIN blockierender
            # Versuch holt die vollstaendige Antwort.
            abbruch = getattr(bei_teil, "abbruch", None)
            if callable(abbruch):
                abbruch()
            log.warning("Stream abgerissen (art=%s): %s -- ein Versuch ohne Stream",
                        art, type(fehler).__name__)
            return self._sende_mit_wiederholung(body, chat_id=chat_id, art=art,
                                                timeout=timeout)
        if not (koerper.get("usage") or {}).get("prompt_tokens"):
            self._melde_strom_aus(chat_id, art, "keine usage im Stream")
        return koerper

    def _melde_strom_aus(self, chat_id, art: str, grund: str) -> None:
        """Einmal je Prozess: Vorfall und Flagge."""
        global _STROM_AUS
        if _STROM_AUS:
            return
        _STROM_AUS = True
        try:
            repo.merke_vorfall(
                self._conn, chat_id, getattr(self._e, "bot_name", None),
                "strom_nicht_verfuegbar",
                f"Streaming abgeschaltet fuer diesen Prozess ({grund}, art={art})",
            )
        except Exception:  # noqa: BLE001 -- ein Vorfall reisst keinen Zug mit
            log.exception("Vorfall strom_nicht_verfuegbar nicht geschrieben")

    def _sende_strom(self, body: dict, *, timeout, bei_teil, teil_feld) -> dict:
        """Ein Aufruf mit ``stream: true``; baut aus den Stuecken denselben
        Koerper, den der blockierende Weg liefert.

        Keine Wiederholung hier: ein abgerissener Stream wird EINMAL ohne
        Stream wiederholt (``_hole``), und den Anbieter mehrfach streamen zu
        lassen hiesse, denselben Text mehrfach zu bezahlen."""
        from interview_theater import strom as strom_modul

        zusatz = {} if timeout is None else {"timeout": timeout}
        roh: list[str] = []
        finish = None
        nutzung: dict = {}
        erstes_stueck = False
        try:
            with self._klient.stream(
                "POST", self._e.llm_url, headers=self._headers(), json=body, **zusatz
            ) as antwort:
                if antwort.status_code >= 400:
                    raise _StromNichtVerfuegbar(f"HTTP {antwort.status_code}")
                for zeile in antwort.iter_lines():
                    zeile = zeile.strip()
                    if not zeile.startswith("data:"):
                        continue
                    nutzlast = zeile[len("data:"):].strip()
                    if nutzlast == "[DONE]":
                        break
                    try:
                        stueck = json.loads(nutzlast)
                    except json.JSONDecodeError as fehler:
                        if erstes_stueck:
                            raise _StromAbbruch("unlesbares Stueck") from fehler
                        raise _StromNichtVerfuegbar("unlesbare Antwort") from fehler
                    if stueck.get("usage"):
                        nutzung = stueck["usage"]
                    for wahl in stueck.get("choices") or []:
                        if wahl.get("finish_reason"):
                            finish = wahl["finish_reason"]
                        # ``reasoning_content`` wird bewusst NICHT gelesen:
                        # die Denkspur ist nie fuer die Gruppe.
                        teil = (wahl.get("delta") or {}).get("content")
                        if not teil:
                            continue
                        erstes_stueck = True
                        roh.append(teil)
                        ganz = "".join(roh)
                        bei_teil(
                            strom_modul.wert_aus_praefix(ganz, teil_feld)
                            if teil_feld else ganz
                        )
        except (_StromNichtVerfuegbar, _StromAbbruch):
            raise
        except httpx.HTTPStatusError as fehler:
            raise _StromNichtVerfuegbar(
                f"HTTP {fehler.response.status_code}") from fehler
        except httpx.TransportError as fehler:
            if erstes_stueck:
                raise _StromAbbruch(type(fehler).__name__) from fehler
            raise _StromNichtVerfuegbar(type(fehler).__name__) from fehler
        if not erstes_stueck:
            raise _StromNichtVerfuegbar("kein einziges Stueck")
        return {
            "choices": [{"message": {"content": "".join(roh)},
                         "finish_reason": finish}],
            "usage": nutzung,
        }
```

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_llm_strom.py tests/test_llm.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/llm.py tests/test_llm_strom.py
git commit -m "LLM: optionaler Stream-Pfad mit identischer Buchung und stillem Rueckfall

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 6: `szene_claude.py` — Anthropic-SSE mit derselben Buchung

**Dateien:**
- Aendern: `interview_theater/szene_claude.py`
- Test: `tests/test_szene_claude_strom.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/szene_claude.py
def prosa(conn, e, klient, chat_id, system, nutzer, art, timeout,
          bei_teil=None) -> str
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_szene_claude_strom.py`:

```python
"""Der zweite Anbieterweg streamt ebenfalls -- im Anthropic-Format.

Die Ereignisse heissen anders (``message_start``, ``content_block_delta``,
``message_delta``), die Zusage ist dieselbe: gleiche Rueckgabe, gleiche
``aufruf``-Zeile, kein halber Text, keine Denkspur an die Gruppe.
"""

import json

import httpx
import pytest

from interview_theater import db, repo, szene_claude

CHAT = 7_000_000_000_001


class Einstellungen:
    szene_anbieter = "claude"
    szene_url = "http://127.0.0.1:28764/v1/messages"
    szene_modell = "claude-opus-5"
    bot_name = "gruppe1"


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "X")
    return verbindung


_FERTIG = {
    "content": [{"type": "text", "text": "Es war einmal"}],
    "usage": {"input_tokens": 700, "output_tokens": 12},
    "stop_reason": "end_turn",
}


def _sse(stuecke, stop="end_turn"):
    zeilen = [
        "event: message_start",
        "data: " + json.dumps({"type": "message_start",
                               "message": {"usage": {"input_tokens": 700}}}),
    ]
    for stueck in stuecke:
        zeilen += [
            "event: content_block_delta",
            "data: " + json.dumps({"type": "content_block_delta",
                                   "delta": {"type": "text_delta", "text": stueck}}),
        ]
    zeilen += [
        "event: message_delta",
        "data: " + json.dumps({"type": "message_delta",
                               "delta": {"stop_reason": stop},
                               "usage": {"output_tokens": 12}}),
        "event: message_stop",
        "data: " + json.dumps({"type": "message_stop"}),
    ]
    return ("\n".join(zeilen) + "\n\n").encode("utf-8")


def _klient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ohne_bei_teil_steht_kein_stream_im_koerper(conn):
    gesehen = {}

    def handler(anfrage):
        gesehen["body"] = json.loads(anfrage.content)
        return httpx.Response(200, json=_FERTIG)

    szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                       "sys", "nutz", "szene", timeout=5)
    assert "stream" not in gesehen["body"]


def test_stream_liefert_teilstuecke_und_denselben_text(conn):
    teile = []
    text = szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append,
    )
    assert teile == ["Es war ", "Es war einmal"]
    assert text == "Es war einmal"


def test_die_aufrufzeile_ist_dieselbe_wie_ohne_stream(conn):
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)),
                       CHAT, "sys", "nutz", "szene", timeout=5)
    ohne = conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()

    szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None,
    )
    mit = conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()
    for spalte in ("art", "modus", "geschaetzte_token", "tatsaechliche_token",
                   "antwort_token", "finish_reason", "erfolg"):
        assert mit[spalte] == ohne[spalte], spalte


def test_thinking_deltas_gehen_nie_an_bei_teil(conn):
    inhalt = (
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "delta": {"type": "thinking_delta", '
        '"thinking": "ich ueberlege"}}\n\n'
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", '
        '"text": "Text"}}\n\n'
        'event: message_delta\n'
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, '
        '"usage": {"output_tokens": 3}}\n\n'
    ).encode("utf-8")
    teile = []
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, content=inhalt)),
                       CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append)
    assert teile == ["Text"]


def test_ein_abgeschnittener_stream_bleibt_ein_fehler(conn):
    """Birk, 06.09.2026: 'Nichts darf stillschweigend abgeschnitten werden.'"""
    with pytest.raises(szene_claude.ClaudeFehler) as fehler:
        szene_claude.prosa(
            conn, Einstellungen(),
            _klient(lambda a: httpx.Response(200, content=_sse(["halb"], stop="max_tokens"))),
            CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None,
        )
    assert "abgeschnitten" in str(fehler.value)
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "szene_abgeschnitten" in arten


def test_ein_abriss_nach_dem_ersten_stueck_wird_ohne_stream_wiederholt(conn):
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, content=(
                b'event: content_block_delta\n'
                b'data: {"type": "content_block_delta", "delta": '
                b'{"type": "text_delta", "text": "Es war "}}\n\n'
                b'data: {kaputt'
            ))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"
    assert versuche == [True, False]
    assert abbrueche == [True]
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_szene_claude_strom.py -q -p no:cacheprovider
```
Erwartet: FAIL — `TypeError: prosa() got an unexpected keyword argument 'bei_teil'`.

- [ ] **Schritt 3: `szene_claude.py` erweitern**

`prosa` bekommt `bei_teil=None` am Ende der Signatur. Der bestehende Rumpf bleibt **genau
so**; nur der eine Sendevorgang innerhalb der Versuchsschleife wird ersetzt:

```python
        try:
            if bei_teil is not None and not _abgeschaltet():
                try:
                    daten = _stream(klient, url, headers, koerper, timeout, bei_teil)
                except _StromNichtVerfuegbar as fehler:
                    _melde_strom_aus(conn, e, chat_id, str(fehler))
                    daten = _blockierend(klient, url, headers, koerper, timeout)
                except _StromAbbruch:
                    abbruch = getattr(bei_teil, "abbruch", None)
                    if callable(abbruch):
                        abbruch()
                    daten = _blockierend(klient, url, headers, koerper, timeout)
            else:
                daten = _blockierend(klient, url, headers, koerper, timeout)
            teile = [...]   # unveraendert weiter wie bisher
```

wobei `_blockierend` genau das tut, was heute inline steht (`klient.post(...)`,
`raise_for_status()`, `antwort.json()`), und daneben:

```python
#: Wie in ``llm.py``: eine Prozessflagge, kein Dauerversuch.
_STROM_AUS = False


class _StromNichtVerfuegbar(Exception):
    """Der Proxy hat den Stream abgelehnt -- BEVOR ein Stueck kam."""


class _StromAbbruch(Exception):
    """Der Stream ist mitten drin abgerissen -- NACH dem ersten Stueck."""


def _abgeschaltet() -> bool:
    return _STROM_AUS


def vergiss_strom() -> None:
    """Nur fuer Tests."""
    global _STROM_AUS
    _STROM_AUS = False


def _melde_strom_aus(conn, e, chat_id, grund: str) -> None:
    global _STROM_AUS
    if _STROM_AUS:
        return
    _STROM_AUS = True
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "strom_nicht_verfuegbar",
            f"Claude-Proxy ohne Stream ({grund})",
        )
    except Exception:  # noqa: BLE001
        log.exception("Vorfall strom_nicht_verfuegbar nicht geschrieben")


def _blockierend(klient, url, headers, koerper, timeout) -> dict:
    antwort = klient.post(url, headers=headers, json=koerper, timeout=timeout)
    antwort.raise_for_status()
    return antwort.json()


def _stream(klient, url, headers, koerper, timeout, bei_teil) -> dict:
    """Ein Aufruf mit ``stream: true`` im Anthropic-Messages-Format; baut aus
    den Ereignissen denselben Koerper, den der blockierende Weg liefert.

    Gelesen werden genau drei Ereignisse: ``message_start`` (input_tokens),
    ``content_block_delta`` mit ``delta.type == "text_delta"`` und
    ``message_delta`` (stop_reason, output_tokens). Ein ``thinking_delta``
    wird **nicht** weitergegeben -- die Denkspur ist nie fuer die Gruppe."""
    import json as _json

    strom_koerper = dict(koerper)
    strom_koerper["stream"] = True
    roh: list[str] = []
    nutzung: dict = {}
    stop = None
    erstes_stueck = False
    try:
        with klient.stream("POST", url, headers=headers, json=strom_koerper,
                           timeout=timeout) as antwort:
            if antwort.status_code >= 400:
                raise _StromNichtVerfuegbar(f"HTTP {antwort.status_code}")
            for zeile in antwort.iter_lines():
                zeile = zeile.strip()
                if not zeile.startswith("data:"):
                    continue
                try:
                    ereignis = _json.loads(zeile[len("data:"):].strip())
                except ValueError as fehler:
                    if erstes_stueck:
                        raise _StromAbbruch("unlesbares Ereignis") from fehler
                    raise _StromNichtVerfuegbar("unlesbare Antwort") from fehler
                typ = ereignis.get("type")
                if typ == "message_start":
                    nutzung.update(
                        (ereignis.get("message") or {}).get("usage") or {})
                elif typ == "content_block_delta":
                    delta = ereignis.get("delta") or {}
                    if delta.get("type") != "text_delta":
                        continue
                    erstes_stueck = True
                    roh.append(delta.get("text") or "")
                    bei_teil("".join(roh))
                elif typ == "message_delta":
                    stop = (ereignis.get("delta") or {}).get("stop_reason") or stop
                    nutzung.update(ereignis.get("usage") or {})
    except (_StromNichtVerfuegbar, _StromAbbruch):
        raise
    except httpx.HTTPStatusError as fehler:
        raise _StromNichtVerfuegbar(f"HTTP {fehler.response.status_code}") from fehler
    except httpx.TransportError as fehler:
        if erstes_stueck:
            raise _StromAbbruch(type(fehler).__name__) from fehler
        raise _StromNichtVerfuegbar(type(fehler).__name__) from fehler
    if not erstes_stueck:
        raise _StromNichtVerfuegbar("kein einziges Stueck")
    return {
        "content": [{"type": "text", "text": "".join(roh)}],
        "usage": nutzung,
        "stop_reason": stop,
    }
```

Im Test-Fixture von `tests/test_szene_claude_strom.py` **fehlt** noch das Zuruecknehmen der
Flagge — beim Schreiben der Datei ein `autouse`-Fixture ergaenzen, das
`szene_claude.vergiss_strom()` vor und nach jedem Test ruft (wie in `tests/test_llm_strom.py`).

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_szene_claude_strom.py tests/test_szene_claude.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/szene_claude.py tests/test_szene_claude_strom.py
git commit -m "Claude-Weg: Anthropic-SSE mit derselben Buchung und demselben Rueckfall

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 7: Die vier Callsites — Gespraech, Auftrag, Szene, Kurzgeschichte

**Dateien:**
- Aendern: `interview_theater/ablauf.py` (`_erfrage_antwort`, `_ohne_denkspur`, `_ohne_echo`,
  `antworte`, `auftragszug`)
- Aendern: `interview_theater/szene.py` (`schreibe`, zwei Stellen)
- Aendern: `interview_theater/kurzgeschichte.py` (`_lauf`, zwei Stellen)
- Test: `tests/test_ablauf_strom.py` (neu)

**Schnittstellen — Konsumiert:** `strom.senke/schliesse/verwirf` (Aufgabe 2),
`LLM.schema(..., bei_teil=)` (Aufgabe 5), `szene_claude.prosa(..., bei_teil=)` (Aufgabe 6).
**Schnittstellen — Produziert:**

```python
# interview_theater/ablauf.py -- beide bekommen einen additiven Parameter
def _ohne_denkspur(conn, klm, e, chat_id, system, koerper, text, bei_teil=None) -> str
def _ohne_echo(conn, klm, e, chat_id, system, koerper, offen, antwort, bei_teil=None) -> str
```

**Die Regel in einem Satz:** die Senke holt sich jede Callsite ueber `strom.senke(tg, …)`;
ein Kanal ohne Strom liefert `None`, und dann ist alles wie heute (E1).

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_ablauf_strom.py`:

```python
"""Der Gespraechszug streamt -- und nichts Halbes wird je eine Nachricht.

Vier Faelle, die zusammengehoeren (Entscheidung D und E):
* der Regelfall -- Teiltexte fliessen, am Ende steht die fertige Nachricht
  und die Stromzeile traegt ihre ``post_id``;
* die verworfene Antwort (Wiederholung, erfundene Systemzeile) -- die
  vorlaeufige Blase verschwindet ersatzlos;
* der zweite Aufruf (Echo) -- der Strom beginnt NEU statt anzuhaengen;
* der gescheiterte Zug -- 'abgebrochen', keine halbe Nachricht.
"""

import pytest

from interview_theater import ablauf, db, repo, strom, web_kanal

CHAT = 7_000_000_000_001


class Einstellungen:
    bot_name = "gruppe1"
    llm_modell = "x"


class KlmMitStrom:
    """Ein Sprachmodell, das seine Antwort in Stuecken liefert."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort"):
        text = self._antworten[min(self.aufrufe, len(self._antworten) - 1)]
        self.aufrufe += 1
        if bei_teil is not None:
            gesehen = ""
            for zeichen in text:
                gesehen += zeichen
                bei_teil(gesehen)
        return {"antwort": text}


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    tg = web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"))
    # Der Takt der Drosselung stoert im Test nur.
    monkeypatch.setattr(strom, "INTERVALL_S", 0.0)
    return conn, tg


def _nachricht(conn, text="Womit fangen wir an?"):
    message_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN,
                                       repo.WEB_TYP_TEXT, text=text)
    return repo.unbeantwortete(conn, CHAT), message_id


def _stroeme(conn):
    return conn.execute(
        "SELECT * FROM web_strom WHERE chat_id = ? ORDER BY id", (CHAT,)
    ).fetchall()


def test_der_regelfall_endet_mit_fertig_und_post_id(aufbau):
    conn, tg = aufbau
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Fangen wir mit Begriffen an."]),
                    Einstellungen(), CHAT, offen)
    zeilen = _stroeme(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["zustand"] == repo.STROM_FERTIG
    assert zeilen[0]["post_id"] is not None
    # Die fertige Nachricht steht als web_post unter genau dieser id.
    assert repo.hole_web_post(conn, zeilen[0]["post_id"])["richtung"] == repo.RICHTUNG_AUS


def test_der_teiltext_wandert_waehrenddessen_in_die_zeile(aufbau):
    """Ohne diesen Test koennte der ganze Weg auch erst am Ende schreiben --
    und niemand saehe einen Unterschied zu vorher."""
    conn, tg = aufbau
    gesehen = []

    class Mitlesend(KlmMitStrom):
        def schema(self, *args, bei_teil=None, **kw):
            def merke(text):
                bei_teil(text)
                gesehen.append(_stroeme(conn)[0]["text"] if _stroeme(conn) else "")
            return super().schema(*args, bei_teil=merke, **kw)

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Mitlesend(["Hallo ihr"]), Einstellungen(), CHAT, offen)
    assert any(0 < len(t) < len("Hallo ihr") for t in gesehen), gesehen


def test_eine_verworfene_antwort_hinterlaesst_keine_blase(aufbau, monkeypatch):
    """Wiederholungsfilter: die Antwort geht NICHT raus -- dann darf auch die
    vorlaeufige Blase nicht stehenbleiben."""
    conn, tg = aufbau
    monkeypatch.setattr(ablauf, "ist_wiederholung", lambda *a, **k: True)
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Das habe ich schon gesagt.")
    repo.merke_nachricht(conn, CHAT, 1, "gruppe1", 1, "text",
                         "Das habe ich schon gesagt.", repo._jetzt())
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Das habe ich schon gesagt."]),
                    Einstellungen(), CHAT, offen)
    assert _stroeme(conn)[-1]["zustand"] == repo.STROM_ABGEBROCHEN
    assert _stroeme(conn)[-1]["post_id"] is None


def test_ein_gescheiterter_zug_bricht_den_strom_ab(aufbau):
    conn, tg = aufbau

    class Kaputt:
        def schema(self, *a, bei_teil=None, **kw):
            if bei_teil is not None:
                bei_teil("halber ")
            raise RuntimeError("Anbieter weg")

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Kaputt(), Einstellungen(), CHAT, offen)
    assert _stroeme(conn)[-1]["zustand"] == repo.STROM_ABGEBROCHEN


def test_ein_zweiter_anlauf_beginnt_eine_neue_zeile(aufbau, monkeypatch):
    """Entscheidung D: loest ``_ohne_echo`` einen zweiten Aufruf aus, beginnt
    der Strom neu -- die verworfene erste Antwort klebt nicht davor."""
    conn, tg = aufbau
    rufe = {"n": 0}

    def echo(antwort, ausloeser):
        rufe["n"] += 1
        return rufe["n"] == 1

    monkeypatch.setattr(ablauf, "ist_echo", echo)
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Womit fangen wir an?", "Mit den Begriffen."]),
                    Einstellungen(), CHAT, offen)
    zeilen = _stroeme(conn)
    assert len(zeilen) == 2
    assert zeilen[0]["zustand"] == repo.STROM_ABGEBROCHEN
    assert zeilen[1]["zustand"] == repo.STROM_FERTIG
    assert "Womit fangen wir an?" not in zeilen[1]["text"]


def test_ein_vorschlagsblock_erscheint_nie_im_strom(aufbau):
    """Entscheidung D: was sichtbar gestreamt wird, ist schon gesaeubert."""
    conn, tg = aufbau
    antwort = "Wie waere es damit?\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit"
    gesehen = []

    class Mitlesend(KlmMitStrom):
        def schema(self, *args, bei_teil=None, **kw):
            def merke(text):
                bei_teil(text)
                zeilen = _stroeme(conn)
                if zeilen:
                    gesehen.append(zeilen[-1]["text"])
            return super().schema(*args, bei_teil=merke, **kw)

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Mitlesend([antwort]), Einstellungen(), CHAT, offen)
    assert all("VORSCHLAG" not in t for t in gesehen), gesehen
    assert all("VORSCHLA" not in t for t in gesehen), gesehen


def test_ein_kanal_ohne_strom_verhaelt_sich_wie_vorher(tmp_path):
    """E1: dieselbe Antwort, kein Strom, keine Ausnahme."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Telegram-Gruppe")

    class TgOhneStrom:
        def __init__(self):
            self.gesendet = []

        def sende(self, chat_id, text, **kw):
            self.gesendet.append(text)
            return len(self.gesendet)

        def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
            return self.sende(chat_id, text)

        def tippt(self, chat_id):
            pass

    tg = TgOhneStrom()
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "Hallo", repo._jetzt())
    offen = repo.unbeantwortete(conn, 1)
    ablauf.antworte(conn, tg, KlmMitStrom(["Hallo zurueck"]), Einstellungen(), 1, offen)
    assert tg.gesendet
    assert conn.execute("SELECT COUNT(*) FROM web_strom").fetchone()[0] == 0
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_ablauf_strom.py -q -p no:cacheprovider
```
Erwartet: FAIL — es entsteht keine `web_strom`-Zeile.

- [ ] **Schritt 3: `ablauf.py` verdrahten**

Im Modulkopf `strom` ergaenzen (`from interview_theater import … strom …`).

In `_erfrage_antwort`, innerhalb von `with _tippanzeige(...)`, den Modellaufruf ersetzen:

```python
        # Der laufende Text (30.09.2026, Karte W): ``senke`` ist ``None``,
        # solange der Kanal keinen Strom kann -- der Telegram-Weg bleibt damit
        # Zeichen fuer Zeichen, wie er war (E1). Abgeschlossen wird sie NICHT
        # hier, sondern in ``antworte``: erst dort steht fest, ob die Antwort
        # wirklich verschickt wurde.
        senke = strom.senke(tg, chat_id, "gespraech")
        ergebnis = klm.schema(chat_id, system, koerper, SCHEMA, "gespraech",
                              bei_teil=senke)
        antwort = _antworttext(ergebnis)
        if not str(antwort).strip():
            raise LLMFehler(
                "Sprachmodell lieferte keine verwertbare Antwort "
                f"(Typ {type(ergebnis).__name__})"
            )
        text = _ohne_denkspur(conn, klm, e, chat_id, system, koerper, antwort,
                              bei_teil=senke)
        text = _ohne_echo(conn, klm, e, chat_id, system, koerper, offen, text,
                          bei_teil=senke)
```

In `_ohne_denkspur` und `_ohne_echo` je den Parameter `bei_teil=None` anhaengen und **vor**
dem zweiten Modellaufruf zwei Zeilen setzen:

```python
    # Der zweite Anlauf ersetzt den ersten -- der Strom beginnt NEU, sonst
    # klebte die verworfene Antwort sichtbar davor (Karte W, Entscheidung D).
    if bei_teil is not None:
        neu = getattr(bei_teil, "neu", None)
        if callable(neu):
            neu()
```

und den zweiten `klm.schema(...)`-Aufruf um `bei_teil=bei_teil` ergaenzen.

In `antworte` drei Stellen:

```python
        if _erfundene_systemzeile(conn, e, chat_id, text):
            strom.verwirf(tg, chat_id)          # die vorlaeufige Blase verschwindet
            versand_erfolgreich = True
            return

        if _wiederholt_die_vorige(conn, e, chat_id, text, letzte_message_id):
            strom.verwirf(tg, chat_id)
            versand_erfolgreich = True
            knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
            return

        message_id, text = _sende_mit_leiste(conn, tg, chat_id, text)
        # Ab hier steht die Antwort in der Gruppe: die vorlaeufige Blase wird
        # durch genau diese Nachricht ersetzt (Zuordnung ueber web_strom.post_id).
        strom.schliesse(tg, chat_id, message_id)
        versand_erfolgreich = True
```

und im `except Exception`-Zweig, **vor** `_melde_fehler`:

```python
        strom.verwirf(tg, chat_id)
```

In `auftragszug` dasselbe Muster: `senke = strom.senke(tg, chat_id, "gespraech")` vor dem
`klm.schema(...)` (mit `bei_teil=senke`), `strom.verwirf(tg, chat_id)` im `except`-Zweig und
`strom.schliesse(tg, chat_id, message_id)` direkt nach dem erfolgreichen
`sende_mit_speicherleiste`/`tg.sende`.

- [ ] **Schritt 4: `szene.py` und `kurzgeschichte.py` verdrahten**

In `szene.schreibe`, direkt vor dem Anbieteraufruf:

```python
    # Der laufende Text (Karte W). Der Szenenlauf haengt in einem eigenen
    # Thread, und niemand wartet vor dem Bildschirm -- aber im Browser ist
    # "es passiert etwas" der Unterschied zwischen zwei Minuten Stille und
    # zwei Minuten Lesen.
    senke = strom.senke(tg, chat_id, "szene")
```
und `bei_teil=senke` an beide Aufrufe (`szene_claude.prosa(...)` und `klm.prosa(...)`).
Direkt nach `titel, kurz, fassung, anders, volltext = zerlege(antwort)` **und** vor jedem
`raise` in dieser Funktion:

```python
    # Kein ``post_id``: der Szenentext geht nicht als eine Nachricht raus,
    # sondern als Vorschau mit Knopfleiste. 'fertig' ohne post_id heisst fuer
    # die Ansicht schlicht: die vorlaeufige Blase darf weg.
    strom.schliesse(tg, chat_id)
```

Im `except`-Zweig von `szene._lauf` (der Thread-Huelle, die `schreibe` ruft) sowie im
`except`-Zweig von `kurzgeschichte._lauf`: `strom.verwirf(tg, chat_id)`.

In `kurzgeschichte._lauf` analog `senke = strom.senke(tg, chat_id, "prosa")` vor den beiden
Anbieteraufrufen, `bei_teil=senke` daran, und `strom.schliesse(tg, chat_id)` nach
`lege_szenen_an`.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_ablauf_strom.py tests/test_ablauf.py tests/test_szene.py \
  tests/test_kurzgeschichte.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/ablauf.py interview_theater/szene.py \
        interview_theater/kurzgeschichte.py tests/test_ablauf_strom.py
git commit -m "Strom an den vier Callsites: Gespraech, Auftrag, Szene, Kurzgeschichte

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 8: Die SSE-Route `/g/<token>/chat/strom`

**Dateien:**
- Neu: `interview_theater/web_vereint.py` (erster Teil: nur der Strom-Kanal)
- Aendern: `interview_theater/web_daten.py` (eine Lesefunktion, read-only)
- Aendern: `interview_theater/web_chat.py` (**eine** Weiche in `beantworte_get`)
- Test: `tests/test_web_strom_route.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_daten.py
def web_stromlage(conn, chat_id: int, nach: int = 0) -> dict | None

# interview_theater/web_vereint.py
STROM_PFAD = "strom"
STROM_TAKT_S = 0.15
STROM_KEEPALIVE_S = 15.0
STROM_MAX_S = 300.0
def sende_strom(handler, db_pfad: str, token: str, query: str) -> None
```

`web_stromlage` liefert `{"id": …, "art": …, "text": …, "zustand": …, "post_id": …}` der
**juengsten** Zeile der Gruppe — oder `None`, wenn es keine gibt oder ihre id ≤ `nach` ist
und sie nicht mehr laeuft.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_strom_route.py`:

```python
"""Der SSE-Kanal: `GET /g/<token>/chat/strom`.

Das ist die EINE Stelle, an der diese Karte A2s Vorgabe "kein SSE" aufhebt
(Plan-Kopf, Abweichung 6) -- fuer alles andere bleibt der Poll.

Getestet wird ueber echtes HTTP gegen einen Server auf Port 0, wie der Rest
der Web-Tests. Kein Browser: gelesen wird der Bytestrom selbst.
"""

import http.client
import json
import threading
import time

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield dienst.server_address[1], token, conn
    dienst.shutdown()


def _oeffne(port: int, pfad: str):
    """Eine rohe HTTP-Verbindung -- ``urllib`` liest bis zum Ende, und ein
    SSE-Strom hat keines, solange er laeuft."""
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    verbindung.request("GET", pfad)
    return verbindung, verbindung.getresponse()


def _ereignisse(antwort, bis: int, frist_s: float = 8.0):
    """Liest, bis ``bis`` Datenzeilen da sind oder die Frist ablaeuft."""
    gefunden = []
    ende = time.monotonic() + frist_s
    puffer = b""
    while len(gefunden) < bis and time.monotonic() < ende:
        stueck = antwort.read(1)
        if not stueck:
            break
        puffer += stueck
        while b"\n" in puffer:
            zeile, _, puffer = puffer.partition(b"\n")
            text = zeile.decode("utf-8").strip()
            if text.startswith("data:"):
                gefunden.append(json.loads(text[len("data:"):].strip()))
    return gefunden


def test_die_kopfzeilen_stimmen(aufbau):
    port, token, conn = aufbau
    repo.beginne_strom(conn, CHAT, "gespraech")
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
        assert antwort.getheader("Content-Type").startswith("text/event-stream")
        assert antwort.getheader("Cache-Control") == "no-cache"
        # Fuer nginx: ohne das puffert der Reverse-Proxy den Strom zu einem
        # einzigen Block (ANNAHME 6 im Plan-Kopf).
        assert antwort.getheader("X-Accel-Buffering") == "no"
        # HTTP/1.1 ohne Content-Length: die Verbindung MUSS als schliessend
        # angekuendigt werden, sonst wartet der Browser auf den naechsten
        # Request auf derselben Verbindung.
        assert antwort.getheader("Connection") == "close"
    finally:
        verbindung.close()


def test_die_teilstuecke_kommen_einzeln(aufbau):
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "Hallo")

    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")

    def weiterschreiben():
        schreibend = db.verbinde(conn.execute("PRAGMA database_list").fetchone()[2])
        time.sleep(0.3)
        repo.schreibe_strom(schreibend, sid, "Hallo ihr")
        time.sleep(0.3)
        repo.beende_strom(schreibend, sid, repo.STROM_FERTIG, post_id=9)
        schreibend.close()

    threading.Thread(target=weiterschreiben, daemon=True).start()
    try:
        ereignisse = _ereignisse(antwort, bis=3)
    finally:
        verbindung.close()

    texte = [e.get("text") for e in ereignisse if "text" in e]
    assert "Hallo" in texte and "Hallo ihr" in texte
    assert ereignisse[-1]["zustand"] == repo.STROM_FERTIG
    assert ereignisse[-1]["post_id"] == 9


def test_eine_fertige_zeile_liefert_sofort_das_ende(aufbau):
    """Reconnect: wer sich neu verbindet, bekommt den Endstand und keine
    haengende Verbindung."""
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "fertiger Satz")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=4)

    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        ereignisse = _ereignisse(antwort, bis=2, frist_s=4.0)
    finally:
        verbindung.close()
    assert ereignisse[-1]["zustand"] == repo.STROM_FERTIG
    assert ereignisse[-1]["post_id"] == 4


def test_ohne_strom_endet_die_verbindung_ohne_daten(aufbau):
    """Keine Zeile, kein Ereignis -- und die Verbindung haengt nicht ewig."""
    port, token, _conn = aufbau
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
        assert _ereignisse(antwort, bis=1, frist_s=2.0) == []
    finally:
        verbindung.close()


def test_unbekanntes_token_ist_404(aufbau):
    port, _token, _conn = aufbau
    verbindung, antwort = _oeffne(port, f"/g/gibtsnicht/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 404
    finally:
        verbindung.close()


def test_die_route_greift_auch_unter_dem_praefix(aufbau):
    port, token, conn = aufbau
    repo.beginne_strom(conn, CHAT, "gespraech")
    verbindung, antwort = _oeffne(
        port, f"/theatersoap/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
    finally:
        verbindung.close()


def test_der_strom_traegt_keinen_dateipfad_und_kein_transkript(aufbau):
    """Dieselben drei Grenzen wie ueberall im Web."""
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "Text")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=1)
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        ereignisse = _ereignisse(antwort, bis=2, frist_s=4.0)
    finally:
        verbindung.close()
    for ereignis in ereignisse:
        assert set(ereignis) <= {"id", "art", "text", "zustand", "post_id"}
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_strom_route.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.web_vereint'`.

- [ ] **Schritt 3: `web_daten.py` — die Lesefunktion**

Am Dateiende anhaengen:

```python
def web_stromlage(conn: sqlite3.Connection, chat_id: int,
                  nach: int = 0) -> dict | None:
    """Die juengste Stromzeile dieser Gruppe -- read-only.

    ``nach`` ist die id, die der Browser schon kennt: eine **aeltere** Zeile
    interessiert ihn nicht mehr. Eine laufende Zeile kommt immer, auch wenn
    ihre id gleich ``nach`` ist -- sonst saehe niemand, wie ihr Text waechst.

    Fehlt die Tabelle noch (Datenbank aus der Zeit davor), ist das Ergebnis
    ``None`` statt ein Fehler: der Webserver migriert nichts."""
    try:
        zeile = conn.execute(
            "SELECT id, art, text, zustand, post_id FROM web_strom "
            "WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if zeile is None:
        return None
    if zeile["id"] < nach:
        return None
    return {
        "id": zeile["id"], "art": zeile["art"], "text": zeile["text"],
        "zustand": zeile["zustand"], "post_id": zeile["post_id"],
    }
```

- [ ] **Schritt 4: `web_vereint.py` anlegen — der Strom-Teil**

```python
"""Die vereinte Gruppenseite: drei Tabs, eine Phasenuebersicht, ein Strom
(30.09.2026, Karte W).

**Warum es dieses Modul gibt.** ``web.py`` traegt schon Dashboard,
Gruppenseite, Probenansicht und Leitfaden; ``web_chat.py`` (Karte A2) den
Chat. Was hier dazukommt -- die Klammer um alle drei, die Phasenleiste und
der SSE-Kanal -- gehoert in keins von beiden, und beide sind Hotspots
mehrerer Karten. Also ein eigenes Modul, das von ``web.py`` nur ueber
Routing-Zeilen erreicht wird.

**Der Strom ist die einzige Ausnahme von A2s "kein SSE".** Fuer alles andere
bleibt der Poll aus ``web_chat``; hier geht es um Teiltexte im
Zehntelsekunden-Takt, und dafuer ist ein Poll je Delta das falsche Werkzeug.
Faellt ``EventSource`` aus, zeigt der Poll die fertige Nachricht wie heute --
Streaming ist eine Zutat, keine Bedingung.

Kein Modellaufruf, kein ``repo``: read-only ueber ``web_daten``, wie der
Rest der Leseseite.
"""

import json
import time

from interview_theater import web_daten

#: Der Unterpfad unter ``/g/<token>/chat/``.
STROM_PFAD = "strom"

#: Wie oft der Server nach neuem Text sieht -- derselbe Takt, in dem der Bot
#: schreibt (``strom.INTERVALL_S``). Schneller zu pollen fände nichts,
#: langsamer machte den Strom ruckelig.
STROM_TAKT_S = 0.15

#: Ein Kommentarzeile alle 15 s haelt die Verbindung durch Proxys am Leben,
#: die stille Verbindungen nach 30-60 s schliessen.
STROM_KEEPALIVE_S = 15.0

#: Nach fuenf Minuten wird die Verbindung geschlossen, auch wenn noch etwas
#: laeuft. ``ThreadingHTTPServer`` bindet je Verbindung einen Thread; der
#: Browser verbindet sich von selbst neu (das ist EventSource eingebaut), und
#: ein Reconnect auf eine fertige Zeile liefert sofort das Ende.
STROM_MAX_S = 300.0


def _kopf(handler) -> None:
    """Die Kopfzeilen eines Ereignisstroms.

    ``protocol_version`` ist ``HTTP/1.1`` (``web._Basishandler``), und dieser
    Antwort fehlt die ``Content-Length``: ohne ``Connection: close`` wartete
    der Browser auf einen weiteren Request auf derselben Verbindung.
    ``X-Accel-Buffering: no`` ist fuer nginx -- ohne das puffert der
    Reverse-Proxy den ganzen Strom zu einem Block (ANNAHME 6)."""
    handler.close_connection = True
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Connection", "close")
    handler.end_headers()


def _schicke(handler, daten: dict) -> bool:
    """Ein Ereignis. ``False``, wenn der Browser weg ist -- dann endet der
    Strom still (kein Vorfall: ein zugeklappter Tab ist kein Fehler)."""
    try:
        handler.wfile.write(
            f"data: {json.dumps(daten, ensure_ascii=False)}\n\n".encode("utf-8")
        )
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _lebt(handler) -> bool:
    try:
        handler.wfile.write(b": ping\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _nach(query: str) -> int:
    import urllib.parse

    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def sende_strom(handler, db_pfad: str, token: str, query: str) -> None:
    """``GET /g/<token>/chat/strom`` -- die Teiltexte des laufenden Aufrufs.

    Der Server pollt die Zeile in ``web_strom`` im selben Takt, in dem der Bot
    sie schreibt, und schickt jede Aenderung weiter. Ende bei ``zustand !=
    'laeuft'``, wenn der Browser weg ist, oder nach ``STROM_MAX_S``.

    Jede Runde oeffnet ihre eigene read-only Verbindung: eine ueber Minuten
    offen gehaltene Leseverbindung saehe wegen der WAL-Momentaufnahme den
    Fortschritt des Bots gar nicht."""
    from interview_theater import web

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
    finally:
        conn.close()
    if chat_id is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return

    _kopf(handler)
    nach = _nach(query)
    zuletzt = ""
    letzte_id = None
    letztes_lebenszeichen = time.monotonic()
    ende = time.monotonic() + STROM_MAX_S
    while time.monotonic() < ende:
        conn = web_daten.oeffne_lesend(db_pfad)
        try:
            lage = web_daten.web_stromlage(conn, chat_id, nach)
        finally:
            conn.close()
        if lage is not None:
            if lage["id"] != letzte_id:
                letzte_id, zuletzt = lage["id"], ""
            if lage["text"] != zuletzt or lage["zustand"] != "laeuft":
                zuletzt = lage["text"]
                if not _schicke(handler, lage):
                    return
                letztes_lebenszeichen = time.monotonic()
            if lage["zustand"] != "laeuft":
                return
        if time.monotonic() - letztes_lebenszeichen >= STROM_KEEPALIVE_S:
            if not _lebt(handler):
                return
            letztes_lebenszeichen = time.monotonic()
        time.sleep(STROM_TAKT_S)
```

- [ ] **Schritt 5: `web_chat.py` — die eine Weiche**

In `web_chat.beantworte_get`, vor dem abschliessenden 404:

```python
    # Der laufende Text (30.09.2026, Karte W). Nur die Weiche steht hier;
    # der Strom selbst liegt in web_vereint.py. Lokaler Import, weil
    # web_vereint seinerseits web_chat braucht (die Panels der vereinten
    # Seite) -- im Modulkopf waere das ein Zyklus.
    from interview_theater import web_vereint

    if unterpfad == web_vereint.STROM_PFAD:
        web_vereint.sende_strom(handler, db_pfad, token, query)
        return
```

Dazu in A2s `tests/test_web_chat_js.py` die Menge der erlaubten GET-Wege ergaenzen:
`erlaubt = set(web_chat._POSTWEGE) | {"zustand", "datei", web_vereint.STROM_PFAD}`.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_strom_route.py tests/test_web_chat.py \
  tests/test_web_chat_js.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web_vereint.py interview_theater/web_daten.py \
        interview_theater/web_chat.py tests/test_web_strom_route.py \
        tests/test_web_chat_js.py
git commit -m "Web vereint: der SSE-Kanal fuer den laufenden Text

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 9: `roadmap.py` — die Phasenuebersicht als Daten

**Dateien:**
- Neu: `interview_theater/roadmap.py` (Schicht **Fachlogik**)
- Aendern: `interview_theater/phasentexte.py` (drei Zeilen: `beschriftung()`)
- Aendern: `interview_theater/web_daten.py` (eine Lesefunktion, read-only)
- Test: `tests/test_roadmap.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/roadmap.py
class Aufgabe(NamedTuple):
    kennung: str
    parameter: str                 # wortgleich zu phasentexte.PARAMETER
    erledigt: Callable[[dict], bool]
    ziel: dict                     # {"tab": "stand"|"textbuch"|"chat", "feld": …}

AUFGABEN: dict[int, tuple[Aufgabe, ...]]
def aus_daten(lage: dict) -> list[dict]
def register(conn, chat_id: int) -> list[dict]

# interview_theater/web_daten.py
def roadmap(conn, chat_id: int) -> list[dict]

# interview_theater/phasentexte.py
def beschriftung(wort: str) -> str
```

`aus_daten` liefert je Phase ein Dict:

```python
{"nummer": 4, "name": "Setting, Figuren & Geschichte", "bezeichnung": "4 · …",
 "aktiv": True, "erledigt": 2, "gesamt": 4,
 "aufgaben": [{"kennung": "setting", "text": "Setting",
               "zustand": "erledigt"|"offen"|"laeuft",
               "ziel": {"tab": "stand", "feld": "rahmen"}}, …]}
```

`lage` ist ein Dict mit genau diesen Schluesseln (beide Aufrufer bauen es):
`stand`, `figuren`, `szenen`, `interviews`, `zuordnungen` (int), `pruefrunde` (int|None),
`phase` (int), `interviewmodus` (bool), `tippt` (bool), `strom` (str|None — die `art` eines
laufenden Stroms).

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_roadmap.py`:

```python
"""Die Roadmap: welche Aufgabe der sieben Phasen steht, welche fehlt.

**Keine zweite Wunschliste** (AGENTS.md, ``fehlstellen``). Was eine Phase
setzt, steht in ``phasentexte.PARAMETER`` -- und ein Test nagelt Namen und
Reihenfolge daran fest. Eigen sind nur die **Pruefer**, und das aus einem
harten Grund: die Leser in ``PARAMETER`` rufen ``repo``, und der Webserver
bekommt keinen ``repo``-Pfad.

**Nichts hier setzt eine Phase.** Die Uebersicht zeigt den Datenstand; der
Datenstand schaltet nie (AGENTS.md, "Der automatische Phasensprung").
"""

import pytest

from interview_theater import db, fehlstellen, phasen, phasentexte, repo, roadmap, web_daten

CHAT = 7_000_000_000_001


def _lage(**abweichung) -> dict:
    grund = {
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 1,
        "interviewmodus": False, "tippt": False, "strom": None,
    }
    grund.update(abweichung)
    return grund


# -- die Liste ist genagelt --------------------------------------------------


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_jede_phase_nennt_dieselben_parameter_wie_phasentexte(nummer):
    """Eine Liste, zwei Leser. Wer eine Phase um ein Feld erweitert, aendert
    ``phasentexte.PARAMETER`` -- und merkt HIER, dass die Roadmap nachzieht."""
    aus_texten = [name for name, _, _ in phasentexte.PARAMETER.get(nummer, ())]
    aus_roadmap = [a.parameter for a in roadmap.AUFGABEN.get(nummer, ())]
    assert aus_roadmap == aus_texten


def test_jede_phase_kommt_vor():
    assert [p["nummer"] for p in roadmap.aus_daten(_lage())] == \
        [n for n, _, _ in phasen.PHASEN]


def test_die_namen_kommen_aus_dem_profil():
    erste = roadmap.aus_daten(_lage())[0]
    assert erste["bezeichnung"] == phasen.bezeichnung(erste["nummer"])
    assert erste["name"] == phasen.kurzname(erste["nummer"])


def test_die_aufgabentexte_laufen_ueber_die_beschriftungstabelle():
    """Damit Padua sie auf Englisch liest (Karte A1) und niemand eine zweite
    Uebersetzung pflegen muss."""
    erste = roadmap.aus_daten(_lage())[0]["aufgaben"][0]
    assert erste["text"] == phasentexte.beschriftung(
        roadmap.AUFGABEN[1][0].parameter)


# -- erledigt / offen --------------------------------------------------------


def _zustand(phasen_liste, nummer, kennung):
    for p in phasen_liste:
        if p["nummer"] != nummer:
            continue
        for a in p["aufgaben"]:
            if a["kennung"] == kennung:
                return a["zustand"]
    raise AssertionError(f"{nummer}/{kennung} nicht gefunden")


def test_am_anfang_ist_alles_offen():
    ergebnis = roadmap.aus_daten(_lage())
    assert all(a["zustand"] == "offen" for p in ergebnis for a in p["aufgaben"])
    assert ergebnis[0]["erledigt"] == 0


def test_begriffe_erledigt():
    ergebnis = roadmap.aus_daten(_lage(stand={"begriffe": "Heimat, Arbeit"}))
    assert _zustand(ergebnis, 1, "begriffe") == "erledigt"
    assert ergebnis[0]["erledigt"] == 1


def test_leere_einleitungen_zaehlen_als_geprueft():
    """"Keine noetig" ist ein Ergebnis der Sensibilitaetspruefung, kein
    fehlender Wert -- dieselbe Unterscheidung wie in
    ``phasen.voraussetzungen`` und ``fehlstellen``."""
    ergebnis = roadmap.aus_daten(_lage(stand={"fragen": "drei", "fragen_weich": ""}))
    assert _zustand(ergebnis, 2, "einleitungen") == "erledigt"


def test_szenentexte_erst_erledigt_wenn_alle_stehen():
    halb = [{"nummer": 1, "volltext": "Text"}, {"nummer": 2, "volltext": ""}]
    ganz = [{"nummer": 1, "volltext": "Text"}, {"nummer": 2, "volltext": "Auch"}]
    assert _zustand(roadmap.aus_daten(_lage(szenen=halb)), 6, "szenentexte") == "laeuft"
    assert _zustand(roadmap.aus_daten(_lage(szenen=ganz)), 6, "szenentexte") == "erledigt"


def test_prosa_zaehlt_wie_volltext():
    """Wie ``phasen._prosa_oder_volltext``: Phase 6 schreibt Geschichte, der
    Feinschliff Theatertext -- beides ist 'die Szene steht'."""
    szenen = [{"nummer": 1, "prosa": "Geschichte", "volltext": ""}]
    assert _zustand(roadmap.aus_daten(_lage(szenen=szenen)), 6, "szenentexte") == "erledigt"


def test_auswertungen_erledigt_erst_mit_einer_verdichtung():
    ohne = [{"zusammenfassung": None}]
    mit = [{"zusammenfassung": "Maria erzaehlt vom ersten Winter"}]
    assert _zustand(roadmap.aus_daten(_lage(interviews=ohne)), 3, "auswertungen") == "offen"
    assert _zustand(roadmap.aus_daten(_lage(interviews=mit)), 3, "auswertungen") == "erledigt"


# -- laeuft ------------------------------------------------------------------


def test_eine_laufende_aufnahme_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=3, interviewmodus=True))
    assert _zustand(ergebnis, 3, "interviews") == "laeuft"


def test_ein_laufender_szenenlauf_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=6, strom="szene"))
    assert _zustand(ergebnis, 6, "szenentexte") == "laeuft"


def test_ein_laufender_prosalauf_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=6, strom="prosa"))
    assert _zustand(ergebnis, 6, "szenentexte") == "laeuft"


def test_was_schon_steht_bleibt_erledigt_auch_wenn_etwas_laeuft():
    ergebnis = roadmap.aus_daten(
        _lage(phase=3, interviewmodus=True,
              interviews=[{"zusammenfassung": "steht"}]))
    assert _zustand(ergebnis, 3, "auswertungen") == "erledigt"


# -- die aktive Phase --------------------------------------------------------


def test_genau_eine_phase_ist_aktiv():
    ergebnis = roadmap.aus_daten(_lage(phase=4))
    assert [p["nummer"] for p in ergebnis if p["aktiv"]] == [4]


# -- die Sprungziele ---------------------------------------------------------


@pytest.mark.parametrize("nummer,kennung,tab", [
    (1, "begriffe", "stand"),
    (4, "setting", "stand"),
    (4, "szenenfolge", "stand"),
    (3, "interviews", "chat"),
    (6, "szenentexte", "textbuch"),
])
def test_jede_aufgabe_zeigt_auf_einen_tab(nummer, kennung, tab):
    for p in roadmap.aus_daten(_lage()):
        for a in p["aufgaben"]:
            if p["nummer"] == nummer and a["kennung"] == kennung:
                assert a["ziel"]["tab"] == tab
                return
    raise AssertionError("nicht gefunden")


def test_jedes_ziel_nennt_einen_bekannten_tab():
    erlaubt = {"chat", "stand", "textbuch"}
    for phase in roadmap.AUFGABEN.values():
        for aufgabe in phase:
            assert aufgabe.ziel["tab"] in erlaubt, aufgabe.kennung


# -- nichts setzt eine Phase -------------------------------------------------


def test_das_lesen_setzt_nie_eine_phase(tmp_path):
    """AGENTS.md: 'Datenstand ist nicht Absicht.' Die Uebersicht zeigt, sie
    schaltet nicht."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Drei Fragen")
    vorher = phasen.aktuelle(conn, CHAT)

    roadmap.register(conn, CHAT)
    conn.commit()
    assert phasen.aktuelle(conn, CHAT) == vorher
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_kein_sql_und_kein_repo_in_roadmap():
    """Dasselbe Muster wie ``fehlstellen``: ``aus_daten`` ist rein, ``register``
    holt ueber ``repo``, ``web_daten.roadmap`` read-only -- der Webserver
    bekommt dadurch keinen ``repo``-Pfad."""
    import pathlib

    quelle = pathlib.Path(roadmap.__file__).read_text(encoding="utf-8")
    for verboten in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert verboten not in quelle
    # ``repo`` nur im lokalen Import von ``register``, nie im Modulkopf.
    kopf = quelle.split("def aus_daten")[0]
    assert "import repo" not in kopf


# -- der Weg des Webservers --------------------------------------------------


def test_web_daten_liefert_dieselbe_liste_wie_der_bot(tmp_path):
    """Ein Zusammenbau, zwei Aufrufer -- wie beim Leitfaden und bei den
    Fehlstellen. Auf der Seite darf nichts anderes stehen als im Chat."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    repo.setze_phase(conn, CHAT, 4)
    conn.commit()

    vom_bot = roadmap.register(conn, CHAT)
    lesend = web_daten.oeffne_lesend(pfad)
    vom_web = web_daten.roadmap(lesend, CHAT)
    lesend.close()

    def kurz(liste):
        return [(p["nummer"], p["aktiv"],
                 [(a["kennung"], a["zustand"]) for a in p["aufgaben"]])
                for p in liste]

    assert kurz(vom_web) == kurz(vom_bot)


def test_web_daten_schreibt_nichts(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)      # mode=ro: jeder Schreibversuch wirft
    assert isinstance(web_daten.roadmap(lesend, CHAT), list)
    lesend.close()


# -- die Demo-Gruppe: erfundenes Material, drei Staende ----------------------


def _demo(conn, stand: str) -> None:
    """Baut eine Gruppe in einem von drei Staenden auf -- **nur erfundenes
    Material** (``simulation/interviews/``), nie ``betrieb/`` (Datenschutz)."""
    import pathlib

    from interview_theater import aufnahme

    class Einstellungen:
        bot_name = "gruppe1"
        audio_verz = "/tmp"

    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit, Streit")
    if stand == "begriffe":
        return
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war im Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    quelle = pathlib.Path("simulation/interviews/set1/1-meryem-koffer.md")
    aufnahme_id = aufnahme.importiere_text(
        conn, Einstellungen(), CHAT, 11,
        quelle.read_text(encoding="utf-8"), name="Interview 1",
    )
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Erzaehlt vom ersten Winter",
        [{"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
          "zitat_geprueft": 1}],
    )
    if stand == "interviews":
        return
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte", "Zwei treffen sich und bleiben.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    repo.lege_szene_an(conn, CHAT, 1, "Ankunft")


@pytest.fixture
def demo(tmp_path, request):
    pfad = str(tmp_path / "demo.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    _demo(conn, request.param)
    conn.commit()
    return conn


@pytest.mark.parametrize("demo,erwartet", [
    ("begriffe", {(1, "begriffe"): "erledigt", (2, "fragen"): "offen",
                  (3, "interviews"): "offen", (4, "setting"): "offen"}),
    ("interviews", {(1, "begriffe"): "erledigt", (2, "fragen"): "erledigt",
                    (2, "einleitungen"): "erledigt", (3, "interviews"): "erledigt",
                    (3, "auswertungen"): "erledigt", (4, "setting"): "offen"}),
    ("phase4", {(4, "setting"): "erledigt", (4, "figuren"): "erledigt",
                (4, "geschichte"): "erledigt", (4, "szenenfolge"): "erledigt",
                (5, "zuordnungen"): "offen", (6, "szenentexte"): "offen",
                (7, "stueckpruefung"): "offen"}),
], indirect=["demo"])
def test_die_demo_gruppe_zeigt_den_richtigen_stand(demo, erwartet):
    """Die Abnahme der Karte: erledigt/offen stimmt an einer echten Datenbank
    -- und das Lesen setzt keine Phase."""
    vorher = phasen.aktuelle(demo, CHAT)
    ergebnis = roadmap.register(demo, CHAT)
    for (nummer, kennung), soll in erwartet.items():
        assert _zustand(ergebnis, nummer, kennung) == soll, (nummer, kennung)
    assert phasen.aktuelle(demo, CHAT) == vorher
```

**Hinweis zum Fixture:** `repo.lege_szene_an` und `aufnahme.importiere_text` sind am Code
zu pruefen, bevor die Datei geschrieben wird — heisst eine Funktion anders, die Fixture
anpassen, **nicht** die Erwartungen. Einstiegspunkt:
`grep -n "def lege_szene_an\|def setze_figur\|def speichere_verdichtung" interview_theater/repo.py`.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_roadmap.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.roadmap'`.

- [ ] **Schritt 3: `phasentexte.beschriftung` oeffentlich machen**

Hinter `_beschriftung` in `interview_theater/phasentexte.py`:

```python
def beschriftung(wort: str) -> str:
    """``_beschriftung`` unter oeffentlichem Namen -- fuer ``roadmap.py``.

    Die Roadmap zeigt dieselben Woerter wie Checkliste, Abschluss und
    ``/stand``; sie sollen in einer Sprachtabelle stehen und nicht in zweien."""
    return _beschriftung(wort)
```

- [ ] **Schritt 4: `roadmap.py` schreiben**

```python
"""Die Roadmap zum Text: welche Aufgabe der sieben Phasen steht, welche fehlt
(30.09.2026, Karte W).

**Warum es das gibt** (Birk, 30.09.2026): "es soll eine uebersicht geben,
welche aufgaben der roadmap zur erstellung des textes schon erfuellt und noch
ausstehend sind." Im Chat sieht eine Gruppe die Checkliste einer Phase beim
Eintritt -- und danach nie wieder; auf der Gruppenseite steht, was gefuellt
ist, und daneben (seit dem 06.09.) was fehlt. Was keiner der beiden zeigt,
ist der **Weg**: sieben Stationen, wo stehen wir, was kommt noch.

**Keine zweite Wunschliste.** Welche Phase was setzt, steht in
``phasentexte.PARAMETER``; ``tests/test_roadmap.py`` nagelt Namen und
Reihenfolge daran fest. Eigen sind hier nur die **Pruefer** -- und das aus
einem harten Grund: die Leser in ``PARAMETER`` rufen ``repo``, und der
Webserver bekommt keinen ``repo``-Pfad (AGENTS.md, ``fehlstellen``). Die
Pruefer sind deshalb reine Funktionen ueber Dicts, und sie pruefen genau das,
woran ``phasen.voraussetzungen`` schon haengt.

**Ein Zusammenbau, zwei Aufrufer** -- dasselbe Muster wie
``leitfaden.aus_feldern`` und ``fehlstellen.aus_daten``: ``aus_daten`` ist
rein und kennt nur Dicts, ``register`` holt sie ueber ``repo`` (Bot),
``web_daten.roadmap`` ueber die read-only geoeffnete Verbindung (Web).

**Nichts hier setzt eine Phase.** Die Uebersicht zeigt den Datenstand; der
Datenstand schaltet nie (AGENTS.md, "Der automatische Phasensprung" --
Datenstand ist nicht Absicht). Umschalten tut allein die Gruppe, per Chat,
Befehl oder Klick (``befehle.wechsle_phase``).

**Kein Modellaufruf.**

**Eine Grenze, ausdruecklich:** 'laeuft' kann nur zeigen, was in der
Datenbank steht -- Interviewmodus, Tippanzeige (``gruppe.web_tippt_bis``) und
eine laufende Zeile in ``web_strom``. Ein Szenenlauf-Lock lebt im
Bot-Prozess und ist fuer den Webserver unsichtbar; laeuft ein Auftrag ohne
Strom (Schaerfung, Szenenfolge, Stueckpruefung), steht die Aufgabe hier
weiter auf 'offen'.
"""

from collections.abc import Callable
from typing import NamedTuple

from interview_theater import phasen, phasentexte


class Aufgabe(NamedTuple):
    """Eine Zeile der Uebersicht.

    ``parameter`` ist wortgleich der Name aus ``phasentexte.PARAMETER`` --
    daran haengt die Beschriftung (und damit die Uebersetzung) und der Test,
    der beide Listen zusammenhaelt."""

    kennung: str
    parameter: str
    erledigt: Callable[[dict], bool]
    ziel: dict


def _text(quelle, name: str) -> str:
    """Ein Feld als getrimmter String -- leer, wenn es fehlt oder NULL ist.
    Dieselbe Nachsicht wie in ``fehlstellen._text``: der Webserver sieht die
    Datenbank read-only und migriert nichts."""
    if quelle is None:
        return ""
    try:
        return (quelle[name] or "").strip()
    except (IndexError, KeyError, TypeError):
        return ""


def _gesetzt(quelle, name: str) -> bool:
    """Wie ``_text``, aber ein **leerer String zaehlt als gesetzt** -- der Fall
    der ``fragen_weich``/``frage_einleitungen``: "keine noetig" ist ein
    Ergebnis, kein fehlender Wert."""
    if quelle is None:
        return False
    try:
        return quelle[name] is not None
    except (IndexError, KeyError, TypeError):
        return False


def _szene_steht(szene) -> bool:
    """Wie ``phasen._prosa_oder_volltext``: Phase 6 schreibt die Geschichte,
    der Feinschliff den Theatertext -- beides ist "die Szene steht"."""
    return bool(_text(szene, "prosa") or _text(szene, "volltext"))


def _alle_szenen_stehen(lage: dict) -> bool:
    szenen = lage["szenen"]
    return bool(szenen) and all(_szene_steht(s) for s in szenen)


#: Je Phase, in der Reihenfolge der Arbeit: was sie setzt.
#: ``parameter`` **muss** wortgleich und in derselben Reihenfolge in
#: ``phasentexte.PARAMETER`` stehen (Test).
AUFGABEN: dict[int, tuple[Aufgabe, ...]] = {
    1: (
        Aufgabe("begriffe", "Begriffe",
                lambda l: bool(_text(l["stand"], "begriffe")),
                {"tab": "stand", "feld": "begriffe"}),
    ),
    2: (
        Aufgabe("fragen", "Fragen",
                lambda l: bool(_text(l["stand"], "fragen")),
                {"tab": "stand", "feld": "fragen"}),
        Aufgabe("einleitungen", "Einleitungen",
                lambda l: _gesetzt(l["stand"], "fragen_weich")
                or _gesetzt(l["stand"], "frage_einleitungen"),
                {"tab": "stand", "feld": "fragen"}),
        Aufgabe("eroeffnung", "Eroeffnung",
                lambda l: bool(_text(l["stand"], "interview_eroeffnung")),
                {"tab": "stand", "feld": "interview_eroeffnung"}),
        Aufgabe("abschluss", "Abschluss",
                lambda l: bool(_text(l["stand"], "interview_abschluss")),
                {"tab": "stand", "feld": "interview_abschluss"}),
    ),
    3: (
        Aufgabe("interviews", "Interviews",
                lambda l: bool(l["interviews"]),
                {"tab": "chat", "feld": None}),
        Aufgabe("auswertungen", "Auswertungen",
                lambda l: any(i.get("zusammenfassung") for i in l["interviews"]),
                {"tab": "stand", "feld": None}),
    ),
    4: (
        Aufgabe("setting", "Setting",
                lambda l: bool(_text(l["stand"], "rahmen")),
                {"tab": "stand", "feld": "rahmen"}),
        Aufgabe("figuren", "Figuren",
                lambda l: bool(l["figuren"]),
                {"tab": "stand", "feld": None}),
        Aufgabe("geschichte", "Geschichte",
                lambda l: bool(_text(l["stand"], "geschichte")),
                {"tab": "stand", "feld": "geschichte"}),
        Aufgabe("szenenfolge", "Szenenfolge",
                lambda l: bool(l["szenen"]),
                {"tab": "stand", "feld": None}),
    ),
    5: (
        Aufgabe("zuordnungen", "Zuordnungen",
                lambda l: l["zuordnungen"] > 0,
                {"tab": "stand", "feld": None}),
    ),
    6: (
        Aufgabe("szenentexte", "Szenentexte", _alle_szenen_stehen,
                {"tab": "textbuch", "feld": None}),
    ),
    7: (
        Aufgabe("stueckpruefung", "Stueckpruefung",
                lambda l: bool(l["pruefrunde"]),
                {"tab": "stand", "feld": None}),
    ),
}

#: Wann eine Aufgabe 'laeuft' statt 'offen' ist -- nur, wo der DATENSTAND es
#: zeigt. Siehe die Grenze im Moduldocstring.
_LAEUFT: dict[str, Callable[[dict], bool]] = {
    "interviews": lambda l: bool(l["interviewmodus"]),
    "auswertungen": lambda l: bool(l["interviewmodus"]),
    "szenentexte": lambda l: l["strom"] in ("szene", "prosa")
    or any(_szene_steht(s) for s in l["szenen"]),
}


def _zustand(aufgabe: Aufgabe, lage: dict) -> str:
    if aufgabe.erledigt(lage):
        return "erledigt"
    laeuft = _LAEUFT.get(aufgabe.kennung)
    return "laeuft" if laeuft is not None and laeuft(lage) else "offen"


def aus_daten(lage: dict) -> list[dict]:
    """Die sieben Phasen mit ihren Aufgaben -- rein, ohne Datenbank.

    ``lage`` traegt: ``stand`` (Arbeitsstand als Dict oder Row), ``figuren``,
    ``szenen``, ``interviews`` (je Dict mit ``zusammenfassung``),
    ``zuordnungen`` (Anzahl Schaerfungen), ``pruefrunde``, ``phase``,
    ``interviewmodus``, ``tippt`` und ``strom`` (die ``art`` einer laufenden
    ``web_strom``-Zeile oder ``None``)."""
    jetzige = lage["phase"]
    ergebnis = []
    for nummer, name, _satz in phasen.PHASEN:
        aufgaben = []
        for aufgabe in AUFGABEN.get(nummer, ()):
            zustand = _zustand(aufgabe, lage)
            aufgaben.append({
                "kennung": aufgabe.kennung,
                "text": phasentexte.beschriftung(aufgabe.parameter),
                "zustand": zustand,
                "ziel": dict(aufgabe.ziel),
            })
        ergebnis.append({
            "nummer": nummer,
            "name": name,
            "bezeichnung": phasen.bezeichnung(nummer),
            "aktiv": nummer == jetzige,
            "erledigt": sum(1 for a in aufgaben if a["zustand"] == "erledigt"),
            "gesamt": len(aufgaben),
            "aufgaben": aufgaben,
        })
    return ergebnis


def register(conn, chat_id: int) -> list[dict]:
    """Der Weg des Bots, ueber ``repo``. Kein Modellaufruf, kein
    Schreibvorgang."""
    from interview_theater import repo

    return aus_daten({
        "stand": repo.hole_arbeitsstand(conn, chat_id),
        "figuren": repo.figuren(conn, chat_id),
        "szenen": repo.hole_szenen(conn, chat_id),
        "interviews": [
            {"zusammenfassung": v["zusammenfassung"]}
            for v in repo.verdichtungen(conn, chat_id)
        ],
        "zuordnungen": len(repo.schaerfungen(conn, chat_id)),
        "pruefrunde": repo.letzte_pruefrunde(conn, chat_id),
        "phase": phasen.aktuelle(conn, chat_id),
        "interviewmodus": repo.ist_interviewmodus_an(conn, chat_id),
        "tippt": False,
        "strom": next(
            (z["art"] for z in repo.laufende_stroeme(conn, chat_id)), None),
    })
```

**Hinweis zu `register`:** die Namen `repo.verdichtungen`, `repo.schaerfungen`,
`repo.letzte_pruefrunde`, `repo.ist_interviewmodus_an` sind am Code geprueft
(`phasen.voraussetzungen`, `phasentexte._zuordnungen`, `phasentexte._stueckpruefung`).
Liefert `repo.verdichtungen` Zeilen ohne Spalte `zusammenfassung`, den Ausdruck auf
`dict(v)` umstellen — nicht die Datenstruktur von `aus_daten` aendern.

- [ ] **Schritt 5: `web_daten.roadmap`**

Am Dateiende von `web_daten.py`:

```python
def roadmap(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die Phasenuebersicht (``interview_theater/roadmap.py``) -- aus der
    read-only geoeffneten Verbindung.

    Ein Zusammenbau, zwei Aufrufer (wie beim Leitfaden und den Fehlstellen):
    die reine Funktion kennt nur Dicts, deshalb kommt der Webserver ohne
    ``repo`` aus."""
    from interview_theater import phasen, roadmap as modul

    stand = _arbeitsstand(conn, chat_id)
    gruppe = conn.execute(
        "SELECT interviewmodus_seit, web_tippt_bis FROM gruppe WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    lage = web_stromlage(conn, chat_id)
    return modul.aus_daten({
        "stand": stand,
        "figuren": _figuren(conn, chat_id),
        "szenen": _szenen(conn, chat_id),
        "interviews": _interviews(conn, chat_id),
        "zuordnungen": sum(
            len(v) for teil in schaerfungen(conn, chat_id).values()
            for v in teil.values()
        ),
        "pruefrunde": (stueckpruefung(conn, chat_id) or {}).get("runde"),
        "phase": stand.get("phase") or phasen.ERSTE,
        "interviewmodus": bool(gruppe and gruppe["interviewmodus_seit"]),
        "tippt": _tippt_noch(gruppe),
        "strom": lage["art"] if lage and lage["zustand"] == "laeuft" else None,
    })


def _tippt_noch(gruppe) -> bool:
    """``gruppe.web_tippt_bis`` (Karte A2) liegt in der Zukunft?"""
    from datetime import datetime, timezone

    if gruppe is None:
        return False
    try:
        bis = lies_zeitstempel(gruppe["web_tippt_bis"])
    except (IndexError, KeyError):
        return False
    return bool(bis and bis > datetime.now(timezone.utc))
```

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_roadmap.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/roadmap.py interview_theater/phasentexte.py \
        interview_theater/web_daten.py tests/test_roadmap.py
git commit -m "Roadmap: die sieben Phasen mit ihren Aufgaben als reine Funktion

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 10: Die drei Koerper herausloesen

**Dateien:**
- Aendern: `interview_theater/web.py` (`gruppe_html`, `textbuch_html`)
- Aendern: `interview_theater/web_chat.py` (`chat_html`)
- Test: `tests/test_web_koerper.py` (neu)

**Warum zuerst.** Die vereinte Seite traegt drei Panels **im selben Dokument** — sie
braucht also von jeder der drei Seiten den **Rumpf** ohne `<!doctype html>`, `<head>` und
`<script>`. Heute bauen alle drei ihre Seite in einem Zug. Diese Aufgabe zieht je eine reine
Funktion heraus und laesst die bestehende Funktion sie rufen; **die Ausgabe der drei Seiten
aendert sich um kein Zeichen** (Test).

**Schnittstellen — Produziert:**

```python
# interview_theater/web.py
def gruppe_koerper(daten, nonce_wert=None, token=None, praefix=VORGABE_PRAEFIX,
                   fassungswahl=None) -> str
def textbuch_koerper(daten, token=None, praefix=VORGABE_PRAEFIX) -> str

# interview_theater/web_chat.py
def chat_koerper(daten, nonce_wert, token, segment_ms, basis: str = "") -> str
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_koerper.py`:

```python
"""Der Rumpf einer Seite, ohne ihre Klammer.

Die vereinte Seite (Karte W) traegt Arbeitsstand, Textbuch und Chat als drei
Panels in EINEM Dokument. Sie braucht deshalb von jeder Seite den Koerper --
und die Einzelseiten muessen dabei Zeichen fuer Zeichen bleiben, was sie
waren. Genau das prueft diese Datei.
"""

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001


def _daten(tmp_path):
    from interview_theater import web_daten

    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    daten = web_daten.gruppe_nach_token(lesend, token)
    lesend.close()
    return daten, token


def test_die_gruppenseite_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten, token = _daten(tmp_path)
    seite = web.gruppe_html(daten, "nonce", token)
    koerper = web.gruppe_koerper(daten, "nonce", token)
    assert koerper in seite
    assert not koerper.startswith("<!doctype")


def test_die_probenansicht_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten, token = _daten(tmp_path)
    assert web.textbuch_koerper(daten, token) in web.textbuch_html(daten, token)


def test_die_chatansicht_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten = {"titel": "Die Ankommenden", "nachrichten": [], "letzte": 0,
             "interviewmodus": False, "tippt": False, "antworten": {}}
    seite = web_chat.chat_html(daten, "nonce", "tok", "/theatersoap", 45_000)
    assert web_chat.chat_koerper(daten, "nonce", "tok", 45_000) in seite


def test_die_basis_steht_im_chatkoerper(tmp_path):
    """Auf der vereinten Seite ist die Basis ``/g/<token>`` statt
    ``/g/<token>/chat`` -- jede relative URL des Chat-JS braucht deshalb ein
    Praefix, und es steht als ``data-basis`` in der Seite."""
    daten = {"titel": "x", "nachrichten": [], "letzte": 0,
             "interviewmodus": False, "tippt": False, "antworten": {}}
    ohne = web_chat.chat_koerper(daten, "n", "tok", 45_000)
    mit = web_chat.chat_koerper(daten, "n", "tok", 45_000, basis="tok/")
    assert 'data-basis=""' in ohne
    assert 'data-basis="tok/"' in mit


def test_das_chat_js_baut_seine_pfade_ueber_die_basis():
    """Ohne diese Regel zeigte jeder ``fetch`` der vereinten Seite auf
    ``/g/chat/zustand`` -- ein stilles 404 im Browser."""
    assert "data-basis" in web_chat._CHAT_JS or "dataset.basis" in web_chat._CHAT_JS
    # Kein nackter Pfad mehr: jedes 'chat/...' haengt an BASIS.
    for treffer in ("'chat/", '"chat/'):
        assert treffer not in web_chat._CHAT_JS, treffer
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_koerper.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.web' has no attribute 'gruppe_koerper'`.

- [ ] **Schritt 3: `web.py` — zwei Extraktionen**

Rein mechanisch. Aus `gruppe_html` wird:

```python
def gruppe_koerper(
    daten: dict,
    nonce_wert: str | None = None,
    token: str | None = None,
    praefix: str = VORGABE_PRAEFIX,
    fassungswahl: dict[int, int] | None = None,
) -> str:
    """Der Rumpf der Gruppenseite -- ohne die Klammer aus ``_seite``.

    Herausgeloest fuer die vereinte Seite (30.09.2026, Karte W): dort steht
    dieser Rumpf als eines von drei Panels in EINEM Dokument. ``gruppe_html``
    ruft ihn und haengt die Klammer davor -- die Einzelseite bleibt damit
    Zeichen fuer Zeichen, was sie war (``tests/test_web_koerper.py``)."""
    …   # der bisherige Rumpf von gruppe_html, unveraendert
    return (
        f"<h1>{_t(titel)}</h1>\n"
        …   # der bisherige f-String, der heute an _seite geht
    )


def gruppe_html(daten, nonce_wert=None, token=None, praefix=VORGABE_PRAEFIX,
                fassungswahl=None) -> str:
    """… (bestehender Docstring unveraendert) …"""
    titel = daten["titel"] or f"Gruppe {daten['chat_id']}"
    return _seite(
        f"{titel} — interview-theater",
        _CSS_GRUPPE,
        gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        bearbeitbar=bool(nonce_wert),
    )
```

Fuer `textbuch_html` genauso: `textbuch_koerper(daten, token, praefix)` traegt alles ab
`<h1>`, `textbuch_html` bleibt die Klammer (`_seite(..., nachladen=False,
skript=_TEXTBUCH_JS)`).

- [ ] **Schritt 4: `web_chat.py` — Extraktion und die Basis**

`chat_koerper(daten, nonce_wert, token, segment_ms, basis="")` traegt alles, was heute in
`chat_html` in der Variablen `koerper` steht; `chat_html` ruft sie und haengt `web._seite`
davor. Dazu drei Aenderungen:

1. `#fuss` bekommt `data-basis="{html.escape(basis, quote=True)}"`.
2. `_blase_html(n, basis="")` haengt die Basis vor den Dateilink
   (`f'<a href="{basis}{CHAT_PFAD}/datei/{n["id"]}">'`).
3. In `_CHAT_JS` ganz oben:

   ```js
     // Die Basis aller Endpunkte. Auf der Chat-Einzelseite (/g/<token>/chat)
     // ist sie leer -- dort loesen die relativen Pfade von selbst richtig auf.
     // Auf der vereinten Seite (/g/<token>) ist sie "<token>/", weil die
     // Basis eine Ebene hoeher liegt und 'chat/zustand' sonst auf
     // /g/chat/zustand zeigte.
     var BASIS = ((document.getElementById('fuss') || {}).dataset || {}).basis || '';
   ```
   und jeder Pfadliteral `'chat/…'` wird zu `BASIS + 'chat/…'`.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_koerper.py tests/test_web.py tests/test_web_textbuch.py \
  tests/test_web_chat.py tests/test_web_chat_js.py tests/test_web_edit.py \
  tests/test_web_fassungen.py -q -p no:cacheprovider
```
Erwartet: alle passed. **Faellt hier etwas**, ist die Extraktion nicht mechanisch geblieben —
die Ausgabe der Einzelseiten muss unveraendert sein.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web.py interview_theater/web_chat.py tests/test_web_koerper.py
git commit -m "Web: Gruppenseite, Probenansicht und Chat liefern ihren Koerper einzeln

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 11: `web_vereint.py` — `scope_css`, drei Panels, Hash-Tabs, Routing

**Dateien:**
- Aendern: `interview_theater/web_vereint.py` (die Seite selbst)
- Aendern: `interview_theater/web.py` (Routing in `_beantworte_gruppenseite`)
- Aendern: `interview_theater/web.py` (`_TEXTBUCH_JS`: Wurzel und bare Hash-Schluessel)
- Test: `tests/test_web_vereint.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_vereint.py
TABS = ("chat", "stand", "textbuch")
VORGABE_TAB = "chat"
def scope_css(css: str, scope: str) -> str
def seite(daten: dict, chatdaten: dict, roadmapdaten: list[dict],
          nonce_wert: str, token: str, praefix: str, segment_ms: int,
          fassungswahl: dict[int, int] | None = None) -> str
def beantworte_seite(handler, db_pfad: str, token: str, praefix: str,
                     schluessel: bytes, query: str) -> None
```

**Der Entwurf, und warum.**

* **Drei Panels im selben DOM, umgeschaltet nur ueber `hidden`.** Ein Seitenwechsel
  riesse Aufnahme, halb getippte Nachricht und laufenden Strom mit — genau das, was die
  Karte verbietet. Ein `hidden`-Panel rendert nicht, also verschwindet auch der `position:
  fixed`-Fuss des Chats, wenn ein anderer Tab vorn ist.
* **Chat ist der Start-Tab** (ohne Fragment). Dort passiert die Arbeit; Arbeitsstand und
  Textbuch sind Nachschlagewerke.
* **Hash-Routing** ueber `location.hash` und `hashchange`: die Zurueck-Taste des Handys
  wechselt damit den Tab, und ein Link laesst sich teilen. Der Tab steht als **blosses
  Wort** im Fragment (`#chat`, `#stand`, `#textbuch`), damit
  `/g/<token>#textbuch&figur=Leyla` dieselbe Form hat wie die gedruckten Rollenlinks der
  Probenansicht.
* **CSS wird zur Laufzeit eingeschraenkt** (`scope_css`), die Konstanten bleiben stehen —
  siehe Abweichung 4 im Plan-Kopf.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_vereint.py`:

```python
"""Die vereinte Seite: drei Panels, ein Dokument, alte Adressen leben weiter.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_vereint_e2e.py``:
das Umschalten selbst, die Zurueck-Taste, der Strom im Browser. Hier steht,
was man am ausgelieferten HTML messen kann.
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url, folge=True):
    class OhneUmleitung(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    oeffner = (urllib.request.build_opener()
               if folge else urllib.request.build_opener(OhneUmleitung))
    try:
        with oeffner.open(url, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8"), antwort.headers
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8"), fehler.headers


# -- scope_css --------------------------------------------------------------


@pytest.mark.parametrize("css,erwartet", [
    ("body { color: red; }", ".p { color: red; }"),
    ("h1 { font-size: 2rem; }", ".p h1 { font-size: 2rem; }"),
    (".leiste button { color: blue; }", ".p .leiste button { color: blue; }"),
    ("body[data-figur] .replik { opacity: .4; }",
     ".p[data-figur] .replik { opacity: .4; }"),
    ("body.ohne-regie .regie { display: none; }",
     ".p.ohne-regie .regie { display: none; }"),
    ("a, b { color: red; }", ".p a, .p b { color: red; }"),
])
def test_scope_schraenkt_jeden_selektor_ein(css, erwartet):
    assert web_vereint.scope_css(css, ".p").strip() == erwartet.strip()


def test_scope_laesst_media_bloecke_stehen_und_schraenkt_darin_ein():
    css = "@media (prefers-color-scheme: dark) { body { color: #fff; } }"
    ergebnis = web_vereint.scope_css(css, ".p")
    assert "@media (prefers-color-scheme: dark)" in ergebnis
    assert ".p { color: #fff; }" in ergebnis.replace("\n", " ")


def test_scope_laesst_kommentare_unangetastet():
    assert "/* ein Wort */" in web_vereint.scope_css("/* ein Wort */\nbody{a:b}", ".p")


def test_die_leiste_der_probenansicht_kollidiert_nicht_mehr():
    """Gemessen am 30.09.2026: ``.leiste`` heisst in ``_CSS_TEXTBUCH`` die
    Rollenleiste und in ``_CSS_CHAT`` die Knopfleiste."""
    textbuch = web_vereint.scope_css(web._CSS_TEXTBUCH, ".panel-textbuch")
    assert "\n.leiste" not in "\n" + textbuch
    assert ".panel-textbuch .leiste" in textbuch


# -- die Seite --------------------------------------------------------------


def test_die_drei_panels_stehen_in_einem_dokument(aufbau):
    basis, token, _pfad = aufbau
    status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert text.count("<!doctype html>") == 1
    for tab in web_vereint.TABS:
        assert f'id="tab-{tab}"' in text, tab


def test_der_chat_ist_der_starttab(aufbau):
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert f'id="tab-{web_vereint.VORGABE_TAB}"' in text
    # Die beiden anderen kommen versteckt aus dem Server: ohne JS sieht man
    # den Chat, und nicht drei Seiten untereinander.
    assert text.count("hidden") >= 2


def test_der_arbeitsstand_traegt_seine_formulare(aufbau):
    """Das Stand-Panel IST die Gruppenseite -- Nonce und Felder inklusive."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'id="nonce"' in text
    assert 'data-feld="rahmen"' in text


def test_das_textbuch_panel_traegt_seinen_zustand_am_panel(aufbau):
    """Die Probenansicht haengt ihren Zustand heute an ``document.body``. Im
    gemeinsamen Dokument geht das nicht -- sonst faerbte der Rollenfilter
    auch den Chat."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "data-textbuch" in text


def test_die_seite_laedt_sich_nicht_selbst_neu(aufbau):
    """``_SCROLL_JS`` tauscht ``document.body.innerHTML`` alle zehn Sekunden --
    das wuerde Chat, Aufnahme und Strom mitreissen."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "document.body.innerHTML = neu" not in text


def test_die_grenzen_gelten_auch_vereint(aufbau):
    """Die vereinte Seite darf nicht mehr ausliefern als ihre drei Quellen
    einzeln: kein Transkript, kein Dateipfad, kein ungeprueftes Zitat."""
    basis, token, pfad = aufbau
    schreibend = db.verbinde(pfad)
    aufnahme_id = repo.lege_aufnahme_an(schreibend, CHAT, 9, "lang", "sprache",
                                        "/tmp/geheim/zwirbelkiste.ogg", 200)
    repo.speichere_verdichtung(
        schreibend, CHAT, aufnahme_id, "Kurz erzaehlt",
        [{"thema": "Arbeit", "beleg_zitat": "so hat das niemand gesagt",
          "zitat_geprueft": 0}],
    )
    schreibend.commit()
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "zwirbelkiste" not in text.lower()
    assert "/tmp/" not in text
    assert "so hat das niemand gesagt" not in text


# -- alte Adressen ----------------------------------------------------------


def test_die_probenansicht_bleibt_eine_eigene_seite(aufbau):
    """Gedruckte QR-Codes und geteilte Rollenlinks duerfen nicht sterben --
    und ``@media print`` braucht eine Seite fuer sich."""
    basis, token, _pfad = aufbau
    for pfad in ("/textbuch", "/textbuch.md", "/textbuch.txt", "/leitfaden"):
        status, _text, _kopf = _hole(f"{basis}/g/{token}{pfad}")
        assert status == 200, pfad


def test_die_alte_chatadresse_leitet_auf_den_tab(aufbau):
    basis, token, _pfad = aufbau
    status, _text, kopf = _hole(f"{basis}/g/{token}/chat", folge=False)
    assert status == 302
    assert kopf["Location"].endswith(f"/g/{token}#chat")


def test_alles_greift_auch_unter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    for pfad in ("", "/textbuch", "/leitfaden"):
        assert _hole(f"{basis}/theatersoap/g/{token}{pfad}")[0] == 200
    status, _text, kopf = _hole(f"{basis}/theatersoap/g/{token}/chat", folge=False)
    assert status == 302 and kopf["Location"].startswith("/theatersoap/")


def test_unbekannter_unterpfad_bleibt_404(aufbau):
    basis, token, _pfad = aufbau
    assert _hole(f"{basis}/g/{token}/quatsch")[0] == 404


def test_unbekanntes_token_ist_404(aufbau):
    basis, _token, _pfad = aufbau
    assert _hole(f"{basis}/g/gibtsnicht")[0] == 404


def test_das_dashboard_bleibt_wie_es_war(aufbau):
    """Es haengt am Beamer, es ist nicht diese Karte."""
    basis, _token, _pfad = aufbau
    status, text, _kopf = _hole(f"{basis}/")
    assert status == 200 and "Arbeitsstand aller Gruppen" in text


# -- das JS der Tabs --------------------------------------------------------


def test_das_tab_js_haengt_an_hashchange():
    """Ohne ``hashchange`` wechselt die Zurueck-Taste des Handys den Tab nicht."""
    assert "hashchange" in web_vereint._VEREINT_JS


def test_das_tab_js_schaltet_nur_hidden_um():
    """Ein Seitenwechsel riesse Aufnahme, Eingabefeld und Strom mit."""
    assert "hidden" in web_vereint._VEREINT_JS
    assert "location.href =" not in web_vereint._VEREINT_JS
    assert "location.reload" not in web_vereint._VEREINT_JS
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_vereint.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.web_vereint' has no attribute 'scope_css'`.

- [ ] **Schritt 3: `scope_css` schreiben**

In `web_vereint.py`:

```python
import re

#: Die drei Panels. Reihenfolge = Reihenfolge der Tableiste.
TABS = ("chat", "stand", "textbuch")

#: Ohne Fragment steht der Chat vorn: dort wird gearbeitet, die anderen
#: beiden sind Nachschlagewerke.
VORGABE_TAB = "chat"

_REGEL = re.compile(r"([^{}]+)\{([^{}]*)\}")
_KOMMENTAR = re.compile(r"/\*.*?\*/", re.S)


def scope_css(css: str, scope: str) -> str:
    """Schraenkt jede Regel einer Panel-CSS auf das Panel ein.

    **Warum zur Laufzeit und nicht von Hand** (Plan-Kopf, Abweichung 4):
    gemessen am 30.09.2026 kollidieren ``_CSS_GRUPPE`` und ``_CSS_TEXTBUCH``
    in ``body`` und ``h1``, und ``.leiste`` heisst in ``_CSS_TEXTBUCH`` die
    Rollenleiste und in ``_CSS_CHAT`` die Knopfleiste. Die Konstanten
    umzuschreiben haette die drei Einzelseiten mit veraendert -- dieser Weg
    laesst sie Zeichen fuer Zeichen stehen.

    ``body`` wird zum Scope selbst (auch mit Anhang: ``body[data-figur] x``
    → ``<scope>[data-figur] x``), alles andere bekommt ihn als Vorfahren.
    ``@media``-Bloecke bleiben stehen, ihr Inhalt wird eingeschraenkt."""
    def eine(treffer: re.Match) -> str:
        selektoren = treffer.group(1).strip()
        koerper = treffer.group(2)
        neu = ", ".join(_ein_selektor(s.strip(), scope)
                        for s in selektoren.split(",") if s.strip())
        return f"{neu} {{{koerper}}}"

    ergebnis = []
    rest = css
    while True:
        block = re.search(r"@media[^{]*\{", rest)
        if block is None:
            ergebnis.append(_REGEL.sub(eine, rest))
            break
        ergebnis.append(_REGEL.sub(eine, rest[:block.start()]))
        tiefe, i = 1, block.end()
        while i < len(rest) and tiefe:
            tiefe += {"{": 1, "}": -1}.get(rest[i], 0)
            i += 1
        ergebnis.append(block.group(0))
        ergebnis.append(_REGEL.sub(eine, rest[block.end():i - 1]))
        ergebnis.append("}")
        rest = rest[i:]
    return "".join(ergebnis)


def _ein_selektor(selektor: str, scope: str) -> str:
    if selektor == "body" or selektor.startswith("body[") or \
            selektor.startswith("body."):
        return scope + selektor[len("body"):]
    if selektor.startswith("body "):
        return f"{scope} {selektor[len('body '):]}"
    if selektor == "*":
        return f"{scope} *"
    return f"{scope} {selektor}"
```

**Hinweis:** `_KOMMENTAR` wird bewusst **nicht** angewandt — Kommentare bleiben im
ausgelieferten CSS stehen (Test `test_scope_laesst_kommentare_unangetastet`); sie enthalten
keine geschweiften Klammern und stoeren den Regex-Lauf nicht. Enthaelt ein Kommentar doch
eine Klammer, ist er vorher zu entfernen — dann `_KOMMENTAR.sub("", css)` an den Anfang
setzen und den Test anpassen.

- [ ] **Schritt 4: Die Seite bauen**

Weiter in `web_vereint.py`:

```python
_TEXT_TAB = {"chat": "Chat", "stand": "Arbeitsstand", "textbuch": "Textbuch"}

#: Nur Struktur, keine Gestaltung -- die UX-Karte gestaltet (Kartentext).
_CSS_VEREINT = """
.tabs { position: sticky; top: 0; z-index: 5; display: flex; gap: .3rem;
        padding: .3rem 0; background: inherit; }
.tabs button { flex: 1; font: inherit; min-height: 2.8rem; border-radius: .6rem;
               border: 1px solid #c9c4b8; background: #fff; }
.tabs button[aria-selected="true"] { font-weight: 600; border-width: 2px; }
.panel[hidden] { display: none; }
"""

```

**Die Platzhalter in den Skripten** — alle werden in `seite()` mit `str.replace` gefuellt,
und **jedes IIFE deklariert sein eigenes `BASIS`** (es gibt keinen gemeinsamen
Gueltigkeitsbereich zwischen `_VEREINT_JS`, `_STROM_JS` und `web_chat._CHAT_JS`):

| Platzhalter | Wert in `seite()` | steht in |
|---|---|---|
| `__TABS__` | `json.dumps(list(TABS))` | `_VEREINT_JS` |
| `__VORGABE__` | `VORGABE_TAB` | `_VEREINT_JS` |
| `__BASIS__` | `f"{token}/"` | `_VEREINT_JS`, `_STROM_JS` |
| `__BASIS_TEIL__` | `f"{token}/{TEIL_PFAD}/"` | `_VEREINT_JS` (Aufgabe 12) |
| `__NACHLADEN_MS__` | `str(NACHLADEN_MS)` | `_VEREINT_JS` (Aufgabe 12) |
| `__SICHER__` | `T._TEXT_PHASE_SICHER` | `_VEREINT_JS` (Aufgabe 13) |
| `__STROM__` | `STROM_PFAD` | `_STROM_JS` (Aufgabe 14) |

`web_chat._CHAT_JS` braucht keine Ersetzung: es liest seine Basis aus
`#fuss[data-basis]` (Aufgabe 10).

```python
_VEREINT_JS = """
(function () {
  var TABS = __TABS__;
  var VORGABE = '__VORGABE__';
  // Die Basis aller Endpunkte dieser Seite: sie liegt unter /g/<token>, die
  // Endpunkte eine Ebene tiefer. Jedes IIFE deklariert sie selbst -- sie
  // teilen keinen Gueltigkeitsbereich.
  var BASIS = '__BASIS__';
  // Der Tab steht als BLOSSES Wort im Fragment (#chat, #stand, #textbuch) --
  // damit ein geteilter Rollenlink dieselbe Form hat wie auf der
  // Probenansicht: #textbuch&figur=Leyla.
  var lies = function () {
    var teile = location.hash.replace(/^#/, '').split('&');
    for (var i = 0; i < teile.length; i++) {
      if (TABS.indexOf(teile[i]) >= 0) { return teile[i]; }
    }
    return VORGABE;
  };
  var zeige = function (name) {
    TABS.forEach(function (tab) {
      var panel = document.getElementById('tab-' + tab);
      if (panel) { panel.hidden = tab !== name; }
      var knopf = document.querySelector('.tabs button[data-tab="' + tab + '"]');
      if (knopf) { knopf.setAttribute('aria-selected', tab === name ? 'true' : 'false'); }
    });
    document.body.dataset.tab = name;
  };
  var setze = function (name) {
    var teile = location.hash.replace(/^#/, '').split('&').filter(function (t) {
      return t && TABS.indexOf(t) < 0;
    });
    // Ueber location.hash, damit die Zurueck-Taste des Handys den vorigen
    // Tab wiederherstellt -- und damit ein kopierter Link der ist, den man
    // gerade sieht. Umgeschaltet wird NUR ueber hidden: ein Seitenwechsel
    // riesse Aufnahme, halb getippte Nachricht und laufenden Strom mit.
    location.hash = '#' + [name].concat(teile).join('&');
  };
  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('.tabs button') : null;
    if (knopf) { setze(knopf.dataset.tab); return; }
    // Ein Klick auf eine Aufgabe der Roadmap springt zu ihrer Stelle --
    // Tab wechseln und, wo es ein Feld gibt, dorthin scrollen. Er setzt
    // KEINE Phase (AGENTS.md: Datenstand ist nicht Absicht).
    var ziel = ev.target.closest ? ev.target.closest('[data-ziel-tab]') : null;
    if (!ziel) { return; }
    setze(ziel.dataset.zielTab);
    var feld = ziel.dataset.zielFeld;
    if (!feld) { return; }
    var stelle = document.querySelector('[data-feld="' + feld + '"]');
    if (stelle && stelle.scrollIntoView) { stelle.scrollIntoView({block: 'center'}); }
  });
  window.addEventListener('hashchange', function () { zeige(lies()); });
  zeige(lies());
})();
"""


def _tabs_html(aktiv: str) -> str:
    knoepfe = "".join(
        f'<button type="button" role="tab" data-tab="{tab}" '
        f'aria-selected="{"true" if tab == aktiv else "false"}">'
        f"{_TEXT_TAB[tab]}</button>"
        for tab in TABS
    )
    return f'<nav class="tabs" role="tablist">{knoepfe}</nav>'


def seite(daten, chatdaten, roadmapdaten, nonce_wert, token, praefix,
          segment_ms, fassungswahl=None) -> str:
    """Die vereinte Gruppenseite: Chat, Arbeitsstand und Textbuch als drei
    Panels in EINEM Dokument.

    **Ohne das sanfte Nachladen** (``web._seite(..., nachladen=False)``): es
    tauscht ``document.body.innerHTML`` alle zehn Sekunden aus, und mitten in
    einer Aufnahme, einer halb getippten Nachricht oder einem laufenden Strom
    waere das ein Datenverlust. Nachgeladen wird gezielt: der Chat per Poll
    (A2), das Stand-Panel ueber ``/g/<token>/teil/stand`` (Aufgabe 12)."""
    from interview_theater import web, web_chat

    titel = daten["titel"] or f"Gruppe {daten['chat_id']}"
    panels = {
        "chat": web_chat.chat_koerper(chatdaten, nonce_wert, token, segment_ms,
                                      basis=f"{token}/"),
        "stand": web.gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        "textbuch": web.textbuch_koerper(daten, token, praefix),
    }
    koerper = [_leiste_html(roadmapdaten, nonce_wert), _tabs_html(VORGABE_TAB)]
    for tab in TABS:
        # ``data-textbuch`` ist die Wurzel, an der ``_TEXTBUCH_JS`` seinen
        # Zustand ablegt: im gemeinsamen Dokument darf der Rollenfilter nicht
        # am ``<body>`` haengen, sonst faerbte er auch den Chat.
        zusatz = ' data-textbuch=""' if tab == "textbuch" else ""
        verborgen = "" if tab == VORGABE_TAB else " hidden"
        koerper.append(
            f'<section class="panel panel-{tab}" id="tab-{tab}" role="tabpanel"'
            f'{zusatz}{verborgen}>\n{panels[tab]}\n</section>'
        )
    css = (
        _CSS_VEREINT
        + scope_css(web._CSS_GRUPPE, ".panel-stand")
        + scope_css(web._CSS_TEXTBUCH, ".panel-textbuch")
        + scope_css(web_chat._CSS_CHAT, ".panel-chat")
    )
    skript = (
        _VEREINT_JS.replace("__TABS__", json.dumps(list(TABS)))
        .replace("__VORGABE__", VORGABE_TAB)
        + web._TEXTBUCH_JS + web_chat._CHAT_JS
    )
    return web._seite(
        f"{titel} — interview-theater", css, "\n".join(koerper),
        bearbeitbar=True, nachladen=False, skript=skript,
    )
```

`_leiste_html` (die Phasenleiste) kommt in Aufgabe 13; bis dahin ein Rumpf:

```python
def _leiste_html(roadmapdaten, nonce_wert: str) -> str:
    """Wird in Aufgabe 13 gefuellt."""
    return ""
```

Dazu der GET-Handler:

```python
def beantworte_seite(handler, db_pfad: str, token: str, praefix: str,
                     schluessel: bytes, query: str) -> None:
    from interview_theater import web, web_chat

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        daten = web_daten.gruppe_nach_token(conn, token)
        chatdaten = web_daten.web_chatzustand(conn, token)
        roadmapdaten = (
            web_daten.roadmap(conn, daten["chat_id"]) if daten else [])
    finally:
        conn.close()
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    if chatdaten is None:
        # Eine Gruppe ohne Web-Kanal hat keinen Chatzustand -- das Panel
        # bleibt leer, die beiden anderen tragen die Seite.
        chatdaten = {"titel": daten["titel"], "nachrichten": [], "letzte": 0,
                     "interviewmodus": False, "tippt": False, "antworten": {}}
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    handler._antworte(200, seite(
        daten, chatdaten, roadmapdaten, web.nonce(schluessel, token), token,
        praefix, web_chat._segment_ms(), web.fassungswahl(query),
    ))
```

Importe in `web_vereint.py` ergaenzen: `json`, `re`.

- [ ] **Schritt 5: `_TEXTBUCH_JS` auf eine Wurzel stellen**

In `interview_theater/web.py`, im Kopf von `_TEXTBUCH_JS`:

```js
  // Die Wurzel, an der der Zustand haengt. Auf der Probenansicht ist das
  // der <body> (er traegt selbst data-textbuch); auf der vereinten Seite
  // (Karte W) das Panel -- sonst faerbte der Rollenfilter auch den Chat.
  var wurzel = document.querySelector('[data-textbuch]') || document.body;
```

und `document.body` → `wurzel`, `document.querySelectorAll(` → `wurzel.querySelectorAll(`
in `wende_an`. Der `<body>` der Einzelseite bekommt das Attribut ueber einen additiven
Parameter an `_seite`:

```python
def _seite(titel, css, koerper, bearbeitbar=False, nachladen=True, skript="",
           koerper_attribute: str = "") -> str:
```
und `f"<body{koerper_attribute}>"`; `textbuch_html` ruft `_seite(..., koerper_attribute=' data-textbuch=""')`.

In `schreib` gilt neu: **ein leerer Wert schreibt den Schluessel ohne `=`** — so ueberlebt
das blosse Tab-Wort im Fragment einen Klick auf den Rollenfilter:

```js
    var text = Object.keys(s).map(function (k) {
      // Ein Schluessel ohne Wert bleibt ohne Gleichheitszeichen: so
      // ueberlebt '#textbuch' (der Tab der vereinten Seite) einen Klick auf
      // den Rollenfilter, statt zu '#textbuch=' zu werden.
      return s[k] === '' ? encodeURIComponent(k)
        : encodeURIComponent(k) + '=' + encodeURIComponent(s[k]);
    }).join('&');
```

- [ ] **Schritt 6: `web.py` — das Routing**

In `_beantworte_gruppenseite`, **anstelle** des heutigen `if unterpfad not in ("", "textbuch")`-Blocks
und des `else`-Zweigs am Ende:

```python
    from interview_theater import web_chat, web_vereint

    if unterpfad == web_chat.CHAT_PFAD:
        # Die Chatansicht ist in der vereinten Seite aufgegangen (Karte W) --
        # zwei Chats nebeneinander waeren zwei Zustaende. Gedruckte Links aus
        # der Zeit von Karte A2 landen im richtigen Tab.
        handler.send_response(302)
        handler.send_header("Location", f"{praefix}/g/{token}#{web_vereint.VORGABE_TAB}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    if unterpfad.startswith(web_chat.CHAT_PFAD + "/"):
        web_chat.beantworte_get(
            handler, db_pfad, token,
            unterpfad[len(web_chat.CHAT_PFAD):].strip("/"),
            praefix, schluessel, query,
        )
        return
    if unterpfad not in ("", "textbuch"):
        handler._antworte(404, nicht_gefunden_html())
        return
    if unterpfad == "textbuch":
        daten = handler._gruppe(token)
        if daten is None:
            handler._antworte(404, nicht_gefunden_html())
        else:
            handler._antworte(200, textbuch_html(daten, token, praefix))
        return
    web_vereint.beantworte_seite(handler, db_pfad, token, praefix, schluessel, query)
```

- [ ] **Schritt 7: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_vereint.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest tests/test_web.py tests/test_web_textbuch.py tests/test_web_edit.py \
  tests/test_web_chat.py tests/test_web_fassungen.py tests/test_festlegung_web.py \
  tests/test_vorspann_web.py tests/test_web_szenenuebersicht.py -q -p no:cacheprovider
```
Erwartet: alle passed. **Ein Test, der an `/g/<token>` eine Eigenschaft der alten
Einzelseite prueft** (z. B. genau ein `<h1>`), ist der einzige erlaubte Anpassungsfall —
und nur, wenn er wirklich die Seitenidentitaet und nicht den Inhalt prueft. **Kein Test
wird abgeschwaecht**: prueft einer einen Inhalt, der jetzt fehlt, fehlt der Inhalt.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 8: Commit**

```bash
git add interview_theater/web_vereint.py interview_theater/web.py \
        tests/test_web_vereint.py
git commit -m "Web vereint: drei Panels in einem Dokument, Hash-Tabs, alte Adressen leben

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 12: Das Stand-Panel laedt allein nach

**Dateien:**
- Aendern: `interview_theater/web_vereint.py` (`TEIL_PFAD`, `sende_teil`, JS)
- Aendern: `interview_theater/web.py` (eine Routing-Zeile)
- Test: `tests/test_web_vereint_nachladen.py` (neu)

**Das Problem, genau.** Heute ersetzt `web._SCROLL_JS` alle zehn Sekunden
`document.body.innerHTML`. Auf der vereinten Seite waere das ein Datenverlust: der laufende
`MediaRecorder`, das halb getippte Feld und die Strom-Blase haengen im DOM. Deshalb laeuft
das Nachladen jetzt **nur** ueber das Stand-Panel, **nur**, wenn es sichtbar ist, und mit
denselben zwei Sperren wie bisher (Fokus in einem Feld, ungespeicherte Aenderung).

**Schnittstellen — Produziert:**

```python
# interview_theater/web_vereint.py
TEIL_PFAD = "teil"
NACHLADEN_MS = web.NEULADEN_SEKUNDEN * 1000
def sende_teil(handler, db_pfad: str, token: str, name: str, praefix: str,
               schluessel: bytes, query: str) -> None
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_vereint_nachladen.py`:

```python
"""Nachgeladen wird nur das Stand-Panel -- und nur, wenn es vorn ist.

Der Grund steht im Plan: ``_SCROLL_JS`` tauscht ``document.body.innerHTML``
aus. Im gemeinsamen Dokument riesse das den laufenden MediaRecorder, das halb
getippte Feld und die Strom-Blase mit.
"""

import threading
import urllib.request

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_der_teil_liefert_nur_das_panel(aufbau):
    basis, token, _pfad = aufbau
    status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand")
    assert status == 200
    assert "<!doctype html>" not in text
    assert "Bahnhof, nachts" in text
    # Der frische Nonce kommt mit: sonst waere jedes Formular nach dem
    # ersten Stundenwechsel ungueltig.
    assert 'id="nonce"' in text


def test_der_teil_traegt_keinen_chat(aufbau):
    basis, token, _pfad = aufbau
    _status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand")
    assert 'id="tab-chat"' not in text
    assert 'id="verlauf"' not in text


def test_ein_unbekannter_teil_ist_404(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/chat")
    assert fehler.value.code == 404


def test_der_teil_greift_unter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    assert _hole(f"{basis}/theatersoap/g/{token}/{web_vereint.TEIL_PFAD}/stand")[0] == 200


def test_der_teil_nimmt_kein_post(aufbau):
    """Geschrieben wird ueber ``/g/<token>`` wie bisher -- ein zweiter
    Schreibweg waere genau das, was N1 verhindert hat."""
    import urllib.error

    anfrage = urllib.request.Request(
        f"{basis_und_token(aufbau)}/{web_vereint.TEIL_PFAD}/stand",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


def basis_und_token(aufbau) -> str:
    basis, token, _pfad = aufbau
    return f"{basis}/g/{token}"


def test_das_js_ersetzt_nur_das_panel():
    js = web_vereint._VEREINT_JS
    assert "document.body.innerHTML" not in js
    assert "tab-stand" in js
    assert web_vereint.TEIL_PFAD in js


def test_das_js_haelt_die_beiden_sperren_ein():
    """Wer gerade tippt, verliert nichts (Brief 05.09. abends) -- dieselben
    zwei Sperren wie in ``_SCROLL_JS``."""
    js = web_vereint._VEREINT_JS
    assert "activeElement" in js
    assert "data-schmutzig" in js or "schmutzig" in js


def test_das_js_laedt_nicht_nach_solange_das_panel_verborgen_ist():
    assert ".hidden" in web_vereint._VEREINT_JS
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_vereint_nachladen.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: … has no attribute 'TEIL_PFAD'`.

- [ ] **Schritt 3: `web_vereint.sende_teil`**

```python
#: Unter welchem Pfad ein einzelnes Panel frisch geholt wird.
TEIL_PFAD = "teil"

#: Derselbe Takt wie das sanfte Nachladen der Einzelseite.
NACHLADEN_MS = 10_000

#: Welche Panels sich nachladen lassen. Der Chat NICHT: er hat seinen eigenen
#: Poll (Karte A2), und das Textbuch aendert sich nicht, waehrend man es liest.
_TEILE = ("stand",)


def sende_teil(handler, db_pfad: str, token: str, name: str, praefix: str,
               schluessel: bytes, query: str) -> None:
    """``GET /g/<token>/teil/stand`` -- nur der Rumpf des Stand-Panels.

    Der Ersatz fuer das sanfte Nachladen der Einzelseite: dort tauscht
    ``web._SCROLL_JS`` den ganzen ``<body>``, hier nur dieses eine Panel.
    Alles andere -- Chat, Aufnahme, Strom, halb getipptes Feld -- bleibt
    stehen.

    Der frische Nonce kommt mit, wie beim sanften Nachladen: er steht IM
    Rumpf (``web.nonce``), nicht daran."""
    from interview_theater import web

    if name not in _TEILE:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    daten = handler._gruppe(token)
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(200, web.gruppe_koerper(
        daten, web.nonce(schluessel, token), token, praefix,
        web.fassungswahl(query),
    ))
```

- [ ] **Schritt 4: Routing in `web.py`**

In `_beantworte_gruppenseite`, vor der Chat-Weiche:

```python
    if unterpfad.startswith(web_vereint.TEIL_PFAD + "/"):
        web_vereint.sende_teil(
            handler, db_pfad, token,
            unterpfad[len(web_vereint.TEIL_PFAD) + 1:], praefix, schluessel, query,
        )
        return
```

- [ ] **Schritt 5: Das Nachladen ins `_VEREINT_JS`**

Am Ende des IIFE in `_VEREINT_JS`, vor `zeige(lies());`:

```js
  // Nachgeladen wird NUR das Stand-Panel, NUR wenn es vorn ist, und nur mit
  // denselben zwei Sperren wie bisher: Fokus in einem Feld oder eine
  // ungespeicherte Aenderung halten es an (Brief 05.09. abends). Der <body>
  // wird nie getauscht -- daran haengen Recorder, Eingabefeld und Strom.
  var wirdBearbeitet = function () {
    var aktiv = document.activeElement;
    if (aktiv && aktiv.closest && aktiv.closest('.feld')) { return true; }
    return !!document.querySelector('.feld[data-schmutzig="1"]');
  };
  var laeuft = false;
  var offene = function (panel) {
    var s = {};
    panel.querySelectorAll('details[open] > summary').forEach(function (el) {
      s[el.textContent.trim()] = true;
    });
    return s;
  };
  setInterval(function () {
    var panel = document.getElementById('tab-stand');
    if (!panel || panel.hidden || laeuft || document.hidden || wirdBearbeitet()) {
      return;
    }
    laeuft = true;
    fetch(BASIS_TEIL + 'stand', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html || html === panel.innerHTML) { return; }
        var zustand = offene(panel);
        var y = window.scrollY;
        panel.innerHTML = html;
        panel.querySelectorAll('details > summary').forEach(function (el) {
          if (zustand[el.textContent.trim()]) { el.parentElement.setAttribute('open', ''); }
        });
        window.scrollTo(0, y);
      })
      .catch(function () {})
      .finally(function () { laeuft = false; });
  }, __NACHLADEN_MS__);
```

und oben im IIFE `var BASIS_TEIL = '__BASIS_TEIL__';`. In `seite()` werden
`__NACHLADEN_MS__` → `str(NACHLADEN_MS)` und `__BASIS_TEIL__` → `f"{token}/{TEIL_PFAD}/"`
ersetzt.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_vereint_nachladen.py tests/test_web_vereint.py \
  -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web_vereint.py interview_theater/web.py \
        tests/test_web_vereint_nachladen.py
git commit -m "Web vereint: nur das Stand-Panel laedt nach, nie der ganze body

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 13: Phasenleiste und Phase per Klick

**Dateien:**
- Aendern: `interview_theater/befehle.py` (`wechsle_phase` herausloesen, `/phaseklick`)
- Aendern: `interview_theater/web_vereint.py` (`_leiste_html`, `phase_post`, JS)
- Aendern: `interview_theater/web_chat.py` (ein Eintrag in `_POSTWEGE`)
- Aendern: `interview_theater/web_schreiben.py` (der Kommentar bei „Die einzelnen Parameter")
- Test: `tests/test_phase_klick.py` (neu)

**Birks Nachtrag, woertlich:** „Die Phase soll per KLICK auf die Phase in der
Phasenuebersicht umschaltbar sein … weg von reiner chat navigation, deterministisch ist
vorzuziehen."

**Das ist kein Widerspruch zu „Die Phase setzt allein die Gruppe":** ein Klick **ist** die
Gruppe. Verworfen bleibt allein der automatische Sprung aus dem Datenstand.

**Der Weg, und warum er so laeuft** (Plan-Kopf, Abweichung 3):

```
Klick  →  POST /g/<token>/chat/phase  (Nonce + bestaetigt + Nummer)
       →  repo.lege_web_post_an(..., WEB_TYP_BEFEHL, text="/phaseklick 5")
       →  WebKanal.hole_updates  (A2, unveraendert)
       →  bot.verarbeite_update  (unveraendert)
       →  befehle.behandle       → befehle.wechsle_phase(..., quelle="web")
/phase 5                          → befehle.wechsle_phase(..., quelle="befehl")
```

Der Webserver setzt die Phase **nicht selbst**: er hat kein `klm`, und
`knoepfe.eintritt_in_phase` stoesst Modellarbeit in Threads an (Schaerfung, Stueckpruefung).
Beide Wege laufen durch **eine** Funktion — ein Klick landet damit nie in einer anderen
Phase als Befehl oder Knopf.

**Schnittstellen — Produziert:**

```python
# interview_theater/befehle.py
def wechsle_phase(conn, tg, klm, e, chat_id: int, nummer: int,
                  quelle: str = "befehl") -> None

# interview_theater/web_vereint.py
def phase_post(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None
```

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_phase_klick.py`:

```python
"""Ein Klick auf eine Phase ist dasselbe wie ``/phase N`` -- bis auf die Quelle.

Birk, 30.09.2026: "weg von reiner chat navigation, deterministisch ist
vorzuziehen." Der Klick geht durch dieselbe Funktion wie der Befehl
(``befehle.wechsle_phase``), damit er nie in einer anderen Phase landet.

Der Webserver setzt dabei nichts: er legt einen Eingang ab, der Bot fuehrt
ihn aus -- ``knoepfe.eintritt_in_phase`` stoesst Modellarbeit an, und der
Webserver hat kein ``klm``.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import befehle, db, phasen, repo, web, web_vereint

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


class Einstellungen:
    bot_name = "gruppe1"


class TgAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def _gruppe(tmp_path, name="t.db"):
    conn = db.verbinde(str(tmp_path / name))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    return conn


# -- ein Weg, zwei Quellen ---------------------------------------------------


def test_klick_und_befehl_landen_in_derselben_phase(tmp_path):
    """Die Abnahme aus Birks Nachtrag: Klick auf Phase 5 == /phase 5."""
    ergebnisse = {}
    for name, text in (("befehl", "/phase 5"), ("klick", "/phaseklick 5")):
        conn = _gruppe(tmp_path, f"{name}.db")
        tg = TgAttrappe()
        befehle.behandle(conn, tg, Einstellungen(), CHAT, text, None, klm=None)
        journal = conn.execute(
            "SELECT art, text, quelle FROM journal WHERE chat_id = ?", (CHAT,)
        ).fetchall()
        ergebnisse[name] = (phasen.aktuelle(conn, CHAT),
                            [(z["art"], z["text"]) for z in journal],
                            [z["quelle"] for z in journal],
                            tg.gesendet)

    assert ergebnisse["befehl"][0] == ergebnisse["klick"][0] == 5
    # Gleiche Journalzeile BIS AUF die Quelle.
    assert ergebnisse["befehl"][1] == ergebnisse["klick"][1]
    assert ergebnisse["befehl"][2] == ["befehl"]
    assert ergebnisse["klick"][2] == ["web"]
    # Gleiche Eintrittsnachricht(en) im Chat.
    assert ergebnisse["befehl"][3] == ergebnisse["klick"][3]


def test_rueckwaerts_geht_auch(tmp_path):
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 7)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 2",
                     None, klm=None)
    assert phasen.aktuelle(conn, CHAT) == 2


def test_dieselbe_phase_erzeugt_keinen_journaleintrag(tmp_path):
    """Wie ``phasen.setze``: derselbe Wert ist keine Aenderung."""
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 4)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 4",
                     None, klm=None)
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_der_klickbefehl_wird_nirgends_beworben():
    """Slash-Befehle werden nicht beworben (AGENTS.md) -- und dieser hier ist
    ueberhaupt nur der Weg des Knopfes durch die Naht."""
    assert "/phaseklick" in befehle._BEKANNTE_BEFEHLE
    assert "phaseklick" not in {b["command"] for b in befehle.BEFEHLE_LISTE}


def test_eine_unbekannte_nummer_aendert_nichts(tmp_path):
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 3)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 99",
                     None, klm=None)
    assert phasen.aktuelle(conn, CHAT) == 3


# -- der Weg durch den Webserver --------------------------------------------


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _post(url, nutzlast):
    anfrage = urllib.request.Request(
        url, data=json.dumps(nutzlast).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _eingaenge(pfad):
    conn = db.verbinde(pfad)
    try:
        return [dict(z) for z in repo.web_eingang(conn, CHAT, 0)]
    finally:
        conn.close()


def test_ein_klick_legt_den_befehl_in_den_eingang(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token),
                           "nummer": 5, "bestaetigt": 1})
    assert status == 202
    eingaenge = _eingaenge(pfad)
    assert [(z["typ"], z["text"]) for z in eingaenge] == [(repo.WEB_TYP_BEFEHL,
                                                          "/phaseklick 5")]


def test_der_webserver_setzt_die_phase_nicht_selbst(server):
    """Er hat kein ``klm``, und ``eintritt_in_phase`` stoesst Modellarbeit an.
    Gesetzt wird sie im Bot-Prozess."""
    basis, token, pfad = server
    _post(f"{basis}/g/{token}/chat/phase",
          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 5, "bestaetigt": 1})
    conn = db.verbinde(pfad)
    assert repo.hole_phase(conn, CHAT) is None
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_ohne_bestaetigung_passiert_nichts(server):
    """Fehlgriff-Schutz: erst die Rueckfrage, dann der Sprung."""
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 5})
    assert status == 400
    assert _eingaenge(pfad) == []


def test_ohne_nonce_passiert_nichts(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nummer": 5, "bestaetigt": 1})
    assert status == 403
    assert _eingaenge(pfad) == []


@pytest.mark.parametrize("nummer", [0, 99, -1, "fuenf", None])
def test_eine_unmoegliche_nummer_ist_400(server, nummer):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token),
                           "nummer": nummer, "bestaetigt": 1})
    assert status == 400
    assert _eingaenge(pfad) == []


def test_alle_sieben_phasen_sind_klickbar(server):
    basis, token, pfad = server
    for nummer, _name, _satz in phasen.PHASEN:
        status, _text = _post(f"{basis}/g/{token}/chat/phase",
                              {"nonce": web.nonce(SCHLUESSEL, token),
                               "nummer": nummer, "bestaetigt": 1})
        assert status == 202, nummer
    assert len(_eingaenge(pfad)) == len(phasen.PHASEN)


# -- die Leiste --------------------------------------------------------------


def test_die_leiste_steht_auf_der_seite_und_ist_knapp(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    # Zugeklappt eine Zeile: Phase, Fortschritt -- aufklappbar zur vollen Liste,
    # und das ohne JavaScript (<details>).
    assert "<details" in text and 'class="roadmap"' in text
    assert "1/7" in text or "1 / 7" in text


def test_jede_phase_traegt_ihren_knopf(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    for nummer, _name, _satz in phasen.PHASEN:
        assert f'data-phase="{nummer}"' in text, nummer


def test_jede_aufgabe_traegt_ihr_sprungziel(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    assert "data-ziel-tab=" in text


def test_das_js_fragt_vor_dem_sprung_nach():
    """Kein Sofortsprung: ein Fehlgriff auf dem Telefon soll keine Phase
    kosten -- dieselbe Inline-Rueckfrage wie beim Entfernen einer Figur."""
    assert "bestaetigt" in web_vereint._VEREINT_JS
    assert "data-sicher" in web_vereint._VEREINT_JS
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_phase_klick.py -q -p no:cacheprovider
```
Erwartet: FAIL — `/phaseklick` ist unbekannt, der POST-Weg fehlt.

- [ ] **Schritt 3: `befehle.py` — eine Funktion fuer beide Wege**

Aus dem Umschaltteil von `_befehl_phase` wird:

```python
def wechsle_phase(conn, tg, klm, e, chat_id: int, nummer: int,
                  quelle: str = "befehl") -> None:
    """Die Phase umschalten -- der EINE Weg fuer Befehl und Klick
    (30.09.2026, Karte W).

    Birk, 30.09.2026: die Phase soll per Klick in der Phasenuebersicht
    umschaltbar sein, "weg von reiner chat navigation". Das ist kein
    Widerspruch zu "Die Phase setzt allein die Gruppe" -- ein Klick IST die
    Gruppe; verworfen bleibt allein der automatische Sprung aus dem
    Datenstand.

    Damit ein Klick nie in einer anderen Phase landet als ein Befehl, laufen
    beide hier durch: ``quelle`` ist der einzige Unterschied ('befehl' gegen
    'web') und steht im Journal.

    Geantwortet wird immer, auch wenn die Phase schon stimmte; ins Journal
    geht der Eintrag nur bei einer echten Aenderung (``phasen.setze``)."""
    phasen.setze(conn, chat_id, nummer, quelle)
    tg.sende(chat_id, phasen.meldung(nummer))
    # Derselbe Rahmen wie ueber den Knopf (06.09.2026): Kopfzeile,
    # Einleitung, Checkliste und die Einstiegsknoepfe dieser Phase.
    try:
        knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, nummer)
    except Exception:
        log.exception("Phaseneintritt fehlgeschlagen, chat_id=%s", chat_id)
```

`_befehl_phase` endet damit auf:

```python
    nummer = phasen.nummer_fuer(rest, jetzige=phasen.aktuelle(conn, chat_id))
    if nummer is None:
        tg.sende(chat_id, f"{_TEXT_PHASE_UNBEKANNT}\n\n{phasen.liste()}")
        return
    wechsle_phase(conn, tg, klm, e, chat_id, nummer, quelle="befehl")
```

Dazu der versteckte Befehl:

```python
def _befehl_phaseklick(conn, tg, klm, e, chat_id: int, rest: str) -> None:
    """Der Klick auf eine Phase in der Web-Uebersicht (30.09.2026, Karte W).

    **Versteckt**: nirgends beworben, nicht im Menue -- er ist kein Befehl
    zum Tippen, sondern der Weg des Knopfes durch die Naht von Karte A2. Der
    Webserver kann die Phase nicht selbst setzen (kein ``klm``, und
    ``eintritt_in_phase`` stoesst Modellarbeit in Threads an); er legt
    stattdessen einen gewoehnlichen Eingang ab, und der Bot fuehrt ihn aus.

    Genau derselbe Weg wie ``/phase N`` -- nur die Journalquelle ist 'web'."""
    nummer = phasen.nummer_fuer(rest, jetzige=phasen.aktuelle(conn, chat_id))
    if nummer is None:
        log.warning("Phasenklick ohne gueltige Nummer: %r (chat_id=%s)", rest, chat_id)
        return
    wechsle_phase(conn, tg, klm, e, chat_id, nummer, quelle="web")
```

`_BEKANNTE_BEFEHLE` bekommt `"/phaseklick"` (mit einem Kommentar wie bei `/festlegung`),
`behandle` einen `elif`-Zweig. `BEFEHLE_LISTE` bleibt unveraendert.

- [ ] **Schritt 4: Der POST-Weg**

In `web_vereint.py`:

```python
_TEXT_PHASE_UNGUELTIG = "Diese Phase gibt es nicht."
_TEXT_PHASE_UNBESTAETIGT = "Bitte einmal bestätigen."


def phase_post(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None:
    """``POST /g/<token>/chat/phase`` -- ein Klick auf eine Phase.

    Der Webserver **setzt nichts**: er legt den Klick als gewoehnlichen
    Eingang ab (derselbe ``WEB_TYP_BEFEHL`` wie der Aufnahme-Umschalter aus
    Karte A2), und der Bot fuehrt ihn ueber ``befehle.wechsle_phase`` aus.
    Zwei Gruende: der Webserver hat kein ``klm``, und
    ``knoepfe.eintritt_in_phase`` stoesst Modellarbeit in Threads an.

    Reihenfolge der Pruefungen wie ueberall: Token (im Aufrufer), Nonce,
    Wert -- erst 403, dann 400. **Ohne ``bestaetigt`` passiert nichts**: ein
    Fehlgriff auf dem Telefon soll keine Phase kosten."""
    from interview_theater import db, phasen, repo, web_chat

    daten = web_chat._koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    if not daten.get("bestaetigt"):
        handler._fehler(400, _TEXT_PHASE_UNBESTAETIGT)
        return
    nummern = {n for n, _name, _satz in phasen.PHASEN}
    roh = daten.get("nummer")
    if not isinstance(roh, int) or isinstance(roh, bool) or roh not in nummern:
        handler._fehler(400, _TEXT_PHASE_UNGUELTIG)
        return
    conn = db.verbinde(db_pfad)
    try:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
            text=f"/phaseklick {roh}",
        )
    finally:
        conn.close()
    web_chat._angenommen(handler, {"message_id": message_id})
```

In `web_chat.py` die Weiche (lokaler Import, weil `web_vereint` seinerseits `web_chat`
braucht):

```python
def _phase(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Der Klick auf eine Phase (Karte W). Nur die Weiche steht hier."""
    from interview_theater import web_vereint

    web_vereint.phase_post(handler, db_pfad, token, chat_id, schluessel)
```
und `_POSTWEGE` bekommt `"phase": _phase`.

- [ ] **Schritt 5: Die Leiste**

`web_vereint._leiste_html` ersetzen:

```python
_TEXT_ROADMAP_KOPF = "Phase {nummer} von {gesamt} · {name} — {erledigt}/{gesamt_aufgaben}"
_TEXT_PHASE_WECHSELN = "Zu dieser Phase wechseln"
_TEXT_PHASE_SICHER = "Wirklich zu {bezeichnung}?"
_ZEICHEN = {"erledigt": "✅", "offen": "⬜", "laeuft": "⏳"}


def _leiste_html(roadmapdaten: list[dict], nonce_wert: str) -> str:
    """Die Phasenuebersicht: zugeklappt eine Zeile, aufgeklappt die volle Liste.

    **Platzierung** (Kartentext: "an geeigneter Stelle anbringen"): ganz oben,
    ueber der Tableiste, und zugeklappt genau **eine** Zeile hoch. Auf einem
    Telefon (390×844) ist der Chat die Arbeitsflaeche -- eine dauerhaft
    aufgeklappte Liste mit sieben Phasen und fuenfzehn Aufgaben naehme ein
    Drittel des Bildschirms fuer etwas, das man dreimal am Tag braucht.
    ``<details>`` statt eines Schalters, damit es **ohne JavaScript**
    funktioniert -- dasselbe Element, das die Gruppenseite schon benutzt.

    Ein Klick auf eine **Phase** schaltet um (ueber den Chat-Weg, Aufgabe 13);
    ein Klick auf eine **Aufgabe** springt nur zu ihrer Stelle (Tab + Feld)
    und setzt nichts."""
    if not roadmapdaten:
        return ""
    aktiv = next((p for p in roadmapdaten if p["aktiv"]), roadmapdaten[0])
    kopf = _TEXT_ROADMAP_KOPF.format(
        nummer=aktiv["nummer"], gesamt=len(roadmapdaten), name=aktiv["name"],
        erledigt=aktiv["erledigt"], gesamt_aufgaben=aktiv["gesamt"],
    )
    zeilen = []
    for phase in roadmapdaten:
        aufgaben = "".join(
            f'<li class="aufgabe {a["zustand"]}" '
            f'data-ziel-tab="{a["ziel"]["tab"]}"'
            + (f' data-ziel-feld="{html.escape(a["ziel"]["feld"], quote=True)}"'
               if a["ziel"].get("feld") else "")
            + f'>{_ZEICHEN[a["zustand"]]} {html.escape(a["text"])}</li>'
            for a in phase["aufgaben"]
        )
        zeilen.append(
            f'<li class="phase{" aktiv" if phase["aktiv"] else ""}">'
            f'<button type="button" class="phase-knopf" '
            f'data-phase="{phase["nummer"]}" '
            f'data-bezeichnung="{html.escape(phase["bezeichnung"], quote=True)}" '
            f'title="{html.escape(_TEXT_PHASE_WECHSELN, quote=True)}">'
            f'{html.escape(phase["bezeichnung"])}</button>'
            f'<ul class="aufgaben">{aufgaben}</ul></li>'
        )
    return (
        f'<details class="roadmap" id="roadmap">'
        f'<summary>{html.escape(kopf)}</summary>'
        f'<ol class="phasen">{"".join(zeilen)}</ol>'
        f'</details>\n'
        f'<input type="hidden" id="nonce-roadmap" '
        f'value="{html.escape(nonce_wert, quote=True)}">'
    )
```

Dazu im `_VEREINT_JS`, im bestehenden `click`-Zuhoerer **vor** der Tab-Weiche:

```js
    var phase = ev.target.closest ? ev.target.closest('.phase-knopf') : null;
    if (phase) {
      // Kein Sofortsprung: erst die Rueckfrage im Knopf selbst -- dieselbe
      // Inline-Bestaetigung wie beim Entfernen einer Figur, damit ein
      // Fehlgriff auf dem Telefon keine Phase kostet.
      if (phase.dataset.sicher !== '1') {
        phase.dataset.sicher = '1';
        phase.dataset.beschriftung = phase.textContent;
        phase.textContent = '__SICHER__'.replace(
          '{bezeichnung}', phase.dataset.bezeichnung);
        return;
      }
      phase.disabled = true;
      fetch(BASIS + 'chat/phase', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nonce: (document.getElementById('nonce-roadmap') || {}).value || '',
          nummer: parseInt(phase.dataset.phase, 10),
          bestaetigt: 1
        })
      }).then(function () {
        phase.disabled = false;
        phase.dataset.sicher = '0';
        phase.textContent = phase.dataset.beschriftung;
        setze('chat');   // die Eintrittsnachricht kommt im Chat an
      }).catch(function () {
        phase.disabled = false;
      });
      return;
    }
```

`__SICHER__` wird in `seite()` durch `_TEXT_PHASE_SICHER` ersetzt, `BASIS` ist
`f"{token}/"` (dieselbe Basis wie im Chat-JS; in `seite()` als `__BASIS__` einsetzen).

- [ ] **Schritt 6: Den Kommentar in `web_schreiben.py` nachtragen**

Im Abschnitt „Die einzelnen Parameter" den bestehenden Block ergaenzen:

```python
# Die Phase setzt allein die Gruppe -- per Chat, Befehl oder Klick (AGENTS.md,
# "Die Phase setzt allein die Gruppe"). Sie stand hier einmal als Dropdown und
# ist am 06.09.2026 wieder herausgenommen worden (Birk): der Bot bietet den
# Wechsel im Fluss an, und ein zweiter Weg daneben macht aus einem Angebot eine
# Einstellung.
#
# Nachtrag 30.09.2026 (Birk, Karte W): in der Phasenuebersicht der vereinten
# Seite ist jede Phase klickbar -- "weg von reiner chat navigation,
# deterministisch ist vorzuziehen". Das macht sie trotzdem NICHT zu einem Feld
# dieser Seite: der Klick geht ueber den Chat-Weg (``web_vereint.phase_post``
# legt einen Eingang ab, der Bot fuehrt ihn ueber ``befehle.wechsle_phase``
# aus, mit Eintrittsnachricht und Einstiegsknoepfen). Ein Eintrag in ``FELDER``
# waere der zweite Weg, den es hier weiterhin nicht gibt.
```

- [ ] **Schritt 7: Lauf, alles gruen**

```
$PY -m pytest tests/test_phase_klick.py tests/test_befehle.py tests/test_phasen.py \
  tests/test_web_edit.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 8: Commit**

```bash
git add interview_theater/befehle.py interview_theater/web_vereint.py \
        interview_theater/web_chat.py interview_theater/web_schreiben.py \
        tests/test_phase_klick.py
git commit -m "Phase per Klick: derselbe Weg wie /phase, Quelle 'web'

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 14: Streaming in der Ansicht — die vorlaeufige Blase

**Dateien:**
- Aendern: `interview_theater/web_vereint.py` (`_STROM_JS`, CSS-Zeile)
- Test: `tests/test_web_vereint_strom_js.py` (neu)

**Was der Browser tut, in vier Saetzen.** Beim Laden oeffnet er `EventSource` auf
`<token>/chat/strom`. Kommt ein `teil`-Ereignis, steht eine **vorlaeufige Blase** am Ende
des Verlaufs und traegt den Text. Kommt `zustand: "fertig"` mit `post_id`, bleibt sie
stehen, bis der A2-Poll die Nachricht mit dieser id liefert — dann verschwindet sie. Kommt
`abgebrochen`, verschwindet sie sofort und ersatzlos.

**`prefers-reduced-motion`:** der Text erscheint trotzdem stueckweise (das ist Information,
keine Animation), nur der blinkende Cursor faellt weg.

**Faellt `EventSource` aus** (altes Geraet, Proxy puffert), passiert gar nichts Sichtbares:
der Poll liefert die fertige Nachricht wie heute.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_vereint_strom_js.py`:

```python
"""Der Vertrag des Strom-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_vereint_e2e.py``:
dass die Blase im echten Chromium waechst. Hier steht, was man am
ausgelieferten Skript messen kann -- und das ist genug, um die vier
Entscheidungen festzuhalten, die leicht verloren gehen.
"""

from interview_theater import web_vereint


def test_der_strom_haengt_an_eventsource():
    assert "EventSource" in web_vereint._STROM_JS


def test_der_strom_zeigt_auf_die_route_die_es_gibt():
    assert f"chat/{web_vereint.STROM_PFAD}" in web_vereint._STROM_JS


def test_eine_abgebrochene_antwort_verschwindet_ersatzlos():
    """Entscheidung E: kein halber Text bleibt stehen."""
    assert "abgebrochen" in web_vereint._STROM_JS


def test_die_fertige_nachricht_ersetzt_die_blase_ueber_die_post_id():
    """Sonst stuende der Text zweimal da: einmal vorlaeufig, einmal echt."""
    assert "post_id" in web_vereint._STROM_JS


def test_ohne_eventsource_passiert_nichts():
    """Faellt EventSource aus, liefert der Poll die fertige Nachricht wie
    heute -- Streaming ist eine Zutat, keine Bedingung."""
    assert "window.EventSource" in web_vereint._STROM_JS


def test_reduzierte_bewegung_hat_ihre_regel():
    """Der Text erscheint trotzdem stueckweise -- das ist Information, keine
    Animation. Nur der Cursor blinkt nicht mehr."""
    assert "prefers-reduced-motion" in web_vereint._CSS_VEREINT


def test_die_blase_traegt_ihre_eigene_klasse():
    assert "vorlaeufig" in web_vereint._STROM_JS
    assert "vorlaeufig" in web_vereint._CSS_VEREINT
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_vereint_strom_js.py -q -p no:cacheprovider
```
Erwartet: FAIL — `_STROM_JS` gibt es nicht.

- [ ] **Schritt 3: `_STROM_JS` und die CSS-Zeilen**

In `web_vereint.py`:

```python
_STROM_JS = """
(function () {
  // Der laufende Text (Karte W). EventSource statt Poll: es geht um
  // Teiltexte im Zehntelsekunden-Takt, und dafuer waere ein Poll je Delta
  // das falsche Werkzeug. Faellt EventSource aus (altes Geraet, puffernder
  // Proxy), passiert hier gar nichts -- der Nachrichten-Poll aus Karte A2
  // liefert die fertige Antwort wie bisher.
  if (!window.EventSource) { return; }
  var verlauf = document.getElementById('verlauf');
  if (!verlauf) { return; }
  var blase = null;
  var wartetAuf = null;   // web_post-id, die die Blase abloesen soll

  var weg = function () {
    if (blase && blase.parentNode) { blase.parentNode.removeChild(blase); }
    blase = null;
    wartetAuf = null;
  };
  var zeige = function (text) {
    if (!blase) {
      blase = document.createElement('div');
      blase.className = 'blase bot text vorlaeufig';
      verlauf.appendChild(blase);
    }
    // textContent, nicht innerHTML: der Teiltext ist roher Modelltext, und
    // gefiltert wird serverseitig (web_chat.sichere_html) -- erst die
    // FERTIGE Nachricht geht durch den Filter.
    blase.textContent = text;
    blase.scrollIntoView({ block: 'end' });
  };

  var quelle = new EventSource(BASIS + 'chat/__STROM__');
  quelle.onmessage = function (ev) {
    var daten = JSON.parse(ev.data);
    if (daten.zustand === 'abgebrochen') { weg(); return; }
    if (daten.zustand === 'fertig') {
      // Die Blase bleibt stehen, bis der Poll die richtige Nachricht
      // gebracht hat -- sonst blitzt eine Luecke auf.
      wartetAuf = daten.post_id;
      if (daten.text) { zeige(daten.text); }
      if (!wartetAuf) { weg(); }
      return;
    }
    zeige(daten.text || '');
  };
  quelle.onerror = function () { /* EventSource verbindet sich selbst neu */ };

  // Der Poll aus Karte A2 haengt die fertige Nachricht an; sobald sie da
  // ist, faellt die vorlaeufige Blase weg.
  var beobachter = new MutationObserver(function () {
    if (wartetAuf && verlauf.querySelector('[data-id="' + wartetAuf + '"]')) {
      weg();
    }
  });
  beobachter.observe(verlauf, { childList: true, subtree: true });
})();
"""
```

`_CSS_VEREINT` bekommt:

```css
.blase.vorlaeufig { opacity: .85; }
.blase.vorlaeufig::after { content: '▍'; animation: blinken 1s steps(2) infinite; }
@keyframes blinken { 50% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  /* Der Text erscheint trotzdem stueckweise -- das ist Information, keine
     Animation. Nur der Cursor hoert auf zu blinken. */
  .blase.vorlaeufig::after { animation: none; }
}
```

In `seite()` wird `_STROM_JS` an das Skript gehaengt, mit `__STROM__` → `STROM_PFAD` und
`BASIS` aus derselben Ersetzung wie in Aufgabe 13.

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_vereint_strom_js.py tests/test_web_vereint.py \
  -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/web_vereint.py tests/test_web_vereint_strom_js.py
git commit -m "Web vereint: die vorlaeufige Blase waechst per SSE und weicht der Nachricht

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 15: Englische Texte (A1) und das Dortmunder Profil

**Dateien:**
- Aendern: `interview_theater/web_vereint.py`, `roadmap.py` (`T = sprache.Texte(__name__)`)
- Aendern: `interview_theater/sprachen/en/texte.toml`
- Aendern: `tests/test_sprache_texte.py` (`UMGESTELLT` und `ALLE_MODULE`)
- Test: `tests/test_web_vereint_sprache.py` (neu)

**Was zu tun ist.** Padua arbeitet auf Englisch (Karte A1), Dortmund bleibt deutsch. Die
neuen Nutzertexte stehen als deutsche `_TEXT_*`-Konstanten in ihren Modulen und werden ueber
`T` gelesen; die englische Fassung steht in `sprachen/en/texte.toml`. Der A1-Test
`test_alle_module_sind_umgestellt` verlangt `UMGESTELLT == ALLE_MODULE` — **beide** Mengen
bekommen die neuen Module.

Betroffen sind (Stand Aufgabe 14):

| Modul | Konstanten |
|---|---|
| `web_vereint` | `_TEXT_TAB`, `_TEXT_ROADMAP_KOPF`, `_TEXT_PHASE_WECHSELN`, `_TEXT_PHASE_SICHER`, `_TEXT_PHASE_UNGUELTIG`, `_TEXT_PHASE_UNBESTAETIGT` |
| `roadmap` | keine — die Aufgabentexte kommen aus `phasentexte.PARAMETER_BESCHRIFTUNG` (Aufgabe 9), es gibt also **keine zweite Tabelle** |

`_CSS_VEREINT`, `_VEREINT_JS` und `_STROM_JS` bleiben deutsch (nur Kommentare) und gehen in
`BLEIBT_DEUTSCH` — wie `web._SCROLL_JS` und `web._TEXTBUCH_JS` es dort schon tun.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_vereint_sprache.py`:

```python
"""Padua liest Englisch, Dortmund Deutsch -- aus derselben Seite.

Die Sprachschicht ist Karte A1; hier wird nur geprueft, dass die neuen Texte
dieser Karte wirklich durch sie laufen und dass das Dortmunder Profil dabei
Zeichen fuer Zeichen bleibt.
"""

import pytest

from interview_theater import roadmap, sprache, web_vereint


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    from interview_theater import workshop

    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_die_tabs_heissen_auf_englisch_anders(englisch):
    assert web_vereint.T._TEXT_TAB != web_vereint._TEXT_TAB
    assert set(web_vereint.T._TEXT_TAB) == set(web_vereint._TEXT_TAB)


def test_die_rueckfrage_traegt_ihren_platzhalter(englisch):
    assert "{bezeichnung}" in web_vereint.T._TEXT_PHASE_SICHER


def test_die_roadmap_hat_keine_zweite_texttabelle():
    """Die Aufgabentexte kommen aus ``phasentexte.PARAMETER_BESCHRIFTUNG`` --
    eine Uebersetzung, nicht zwei."""
    import pathlib

    quelle = pathlib.Path(roadmap.__file__).read_text(encoding="utf-8")
    assert "_TEXT_" not in quelle
```

**ANNAHME:** das Profil fuer Padua heisst `padua-2026` und steht nach Karte A1 unter
`workshop/`. Gibt es es noch nicht, nimmt der Test das englische Profil, das A1 angelegt hat
(`ls workshop/`) — **den Namen im Test anpassen, nicht die Pruefung**.

```
ls workshop/
$PY -c "from interview_theater import sprache; print(sprache.GEBAUT)"
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_vereint_sprache.py -q -p no:cacheprovider
```
Erwartet: FAIL — `web_vereint.T` gibt es nicht.

- [ ] **Schritt 3: `T` einhaengen und die Tabelle fuellen**

Am Ende von `web_vereint.py`:

```python
#: Die Nutzertexte in der Sprache des Profils (Karte A1). Nachgeschlagen wird
#: zur Aufrufzeit, nie beim Import: ein Web-Prozess bedient mehrere Gruppen.
T = sprache.Texte(__name__)
```
und jede Verwendung von `_TEXT_*` auf `T._TEXT_*` umstellen (`_TEXT_TAB[tab]` →
`T._TEXT_TAB[tab]` usw.).

In `interview_theater/sprachen/en/texte.toml` einen Abschnitt anlegen:

```toml
[web_vereint]
_TEXT_ROADMAP_KOPF = "Act {nummer} of {gesamt} · {name} — {erledigt}/{gesamt_aufgaben}"
_TEXT_PHASE_WECHSELN = "Switch to this act"
_TEXT_PHASE_SICHER = "Really switch to {bezeichnung}?"
_TEXT_PHASE_UNGUELTIG = "There is no such act."
_TEXT_PHASE_UNBESTAETIGT = "Please confirm first."

[web_vereint._TEXT_TAB]
chat = "Chat"
stand = "Workbench"
textbuch = "Script"
```

**Die Platzhalter muessen identisch sein** (A1-Test `test_platzhalter_und_form_gleich`):
`{nummer}`, `{gesamt}`, `{name}`, `{erledigt}`, `{gesamt_aufgaben}`, `{bezeichnung}`.

In `tests/test_sprache_texte.py`:
* `UMGESTELLT` **und** `ALLE_MODULE` bekommen `"web_vereint"` (beide, sonst faellt
  `test_alle_module_sind_umgestellt`);
* `BLEIBT_DEUTSCH` bekommt

  ```python
  "web_vereint._CSS_VEREINT": "CSS, nur Kommentare deutsch",
  "web_vereint._VEREINT_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
  "web_vereint._STROM_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
  ```

`roadmap` kommt **nicht** in die Mengen: es hat keinen eigenen Nutzertext (Test oben).

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_vereint_sprache.py tests/test_sprache_texte.py \
  tests/test_sprache_bitgleich.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: gruen, ohne Fehlerzeile.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/web_vereint.py interview_theater/sprachen/en/texte.toml \
        tests/test_sprache_texte.py tests/test_web_vereint_sprache.py
git commit -m "Web vereint: englische Texte fuer Padua ueber die Sprachschicht

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 16: Browserlauf und Screenshots

**Dateien:**
- Neu: `tests/e2e/test_web_vereint_e2e.py`
- Neu: `docs/web-vereint/*.png` (committet)
- Aendern: `tests/e2e/README.md` (ein Absatz)

**Laeuft nicht im normalen `pytest`-Lauf mit** (`pytest.importorskip`), wie
`tests/e2e/test_web_edit_e2e.py`. Gefahren wird mit dem Wegwerf-venv:
`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python`.

**Was hier geprueft wird und sonst nirgends:** dass der Tabwechsel **wirklich nichts
verliert** — und das laesst sich nur in einem echten Browser messen.

- [ ] **Schritt 1: Den Test schreiben**

`tests/e2e/test_web_vereint_e2e.py`:

```python
"""Die vereinte Seite im echten Chromium.

Was ``tests/test_web_vereint*.py`` NICHT pruefen kann: ob der Tabwechsel den
halb getippten Text und die laufende Strom-Blase wirklich stehen laesst, ob
die Zurueck-Taste den Tab wechselt, und wie das Ganze auf einem Telefon
aussieht.

**Nur erfundenes Material** (``simulation/interviews/``), nie ``betrieb/``.
Die Screenshots gehen ins Repository (``docs/web-vereint/``) -- sie sind der
Beleg der Abnahme und duerfen deshalb nichts Echtes zeigen.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-vereint.db"
BIND = "127.0.0.1:8021"
SCHUSS = WURZEL / "docs" / "web-vereint"
CHAT = 7_000_000_000_001


def _baue_datenbank(pfad: str) -> str:
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    if os.path.exists(pfad):
        os.remove(pfad)
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit, Streit")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte", "Zwei treffen sich und bleiben.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998 mit einem Koffer")
    repo.setze_phase(conn, CHAT, 4)
    nummer = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis")
    repo.aktualisiere_szene(conn, nummer, volltext="MERYEM: Ich bin da.\nALI: Endlich.")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Womit fangen wir an?")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Mit euren Begriffen. Was faellt euch ein?")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


@pytest.fixture(scope="module")
def dienst():
    token = _baue_datenbank(DB_PFAD)
    shutil.rmtree(SCHUSS, ignore_errors=True)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="")
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://{BIND}", token
    prozess.terminate()
    prozess.wait(timeout=10)


def _strom_schreiben(text: str, zustand: str = "laeuft", strom_id=None):
    """Schreibt eine Stromzeile, als haette es der Bot getan."""
    from interview_theater import db, repo

    conn = db.verbinde(DB_PFAD)
    try:
        if strom_id is None:
            strom_id = repo.beginne_strom(conn, CHAT, "gespraech")
        repo.schreibe_strom(conn, strom_id, text)
        if zustand != "laeuft":
            repo.beende_strom(conn, strom_id, zustand)
        return strom_id
    finally:
        conn.close()


def test_der_tabwechsel_verliert_nichts(dienst):
    """Der Kern der Karte: halb getippter Text und laufende Strom-Blase
    ueberstehen den Wechsel -- weil nur ``hidden`` umgeschaltet wird."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}")
        seite.fill("#eingabe", "Das tippe ich gerade")
        strom_id = _strom_schreiben("Der Bot schreibt ger")
        seite.wait_for_selector(".blase.vorlaeufig", timeout=10_000)

        seite.click('.tabs button[data-tab="stand"]')
        seite.wait_for_selector("#tab-stand:not([hidden])")
        seite.click('.tabs button[data-tab="chat"]')
        seite.wait_for_selector("#tab-chat:not([hidden])")

        assert seite.input_value("#eingabe") == "Das tippe ich gerade"
        assert seite.is_visible(".blase.vorlaeufig")
        _strom_schreiben("Der Bot schreibt gerade weiter.", "fertig", strom_id)
        browser.close()


def test_die_blase_waechst(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}")
        strom_id = _strom_schreiben("Erst ")
        seite.wait_for_selector(".blase.vorlaeufig", timeout=10_000)
        kurz = seite.text_content(".blase.vorlaeufig")
        _strom_schreiben("Erst kurz, dann laenger.", strom_id=strom_id)
        seite.wait_for_function(
            "document.querySelector('.blase.vorlaeufig')"
            ".textContent.length > %d" % len(kurz), timeout=10_000)
        _strom_schreiben("Erst kurz, dann laenger.", "abgebrochen", strom_id)
        seite.wait_for_selector(".blase.vorlaeufig", state="detached", timeout=10_000)
        browser.close()


def test_die_zurueck_taste_wechselt_den_tab(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}")
        seite.click('.tabs button[data-tab="textbuch"]')
        seite.wait_for_selector("#tab-textbuch:not([hidden])")
        seite.go_back()
        seite.wait_for_selector("#tab-chat:not([hidden])")
        browser.close()


def test_ein_geteilter_rollenlink_oeffnet_das_textbuch_mit_rolle(dienst):
    """``#textbuch&figur=Meryem`` -- dieselbe Form wie auf der Probenansicht."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}#textbuch&figur=Meryem")
        seite.wait_for_selector("#tab-textbuch:not([hidden])")
        assert seite.get_attribute("#tab-textbuch", "data-figur")
        browser.close()


def test_die_phasenleiste_klappt_auf_und_zu(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}")
        assert not seite.is_visible(".roadmap .phasen")
        seite.click(".roadmap summary")
        seite.wait_for_selector(".roadmap .phasen", state="visible")
        browser.close()


def test_ein_phasenklick_fragt_nach_und_legt_dann_den_eingang_ab(dienst):
    """Fehlgriff-Schutz und der Weg durch die Naht -- im Browser."""
    from interview_theater import db, repo

    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 390, "height": 844})
        seite.goto(f"{basis}/g/{token}")
        seite.click(".roadmap summary")
        knopf = seite.locator('.phase-knopf[data-phase="5"]')
        vorher = knopf.text_content()
        knopf.click()
        seite.wait_for_function(
            "document.querySelector('.phase-knopf[data-phase=\\"5\\"]')"
            ".dataset.sicher === '1'", timeout=5_000)
        assert knopf.text_content() != vorher

        conn = db.verbinde(DB_PFAD)
        vor = len(repo.web_eingang(conn, CHAT, 0))
        conn.close()
        knopf.click()
        seite.wait_for_timeout(1_000)
        conn = db.verbinde(DB_PFAD)
        eingaenge = repo.web_eingang(conn, CHAT, 0)
        conn.close()
        assert len(eingaenge) == vor + 1
        assert eingaenge[-1]["text"] == "/phaseklick 5"
        browser.close()


@pytest.mark.parametrize("breite,hoehe,name", [(390, 844, "handy"),
                                               (1366, 900, "laptop")])
def test_screenshots(dienst, breite, hoehe, name):
    """Die Abnahme der Karte: Chat mit laufendem Stream, Tab Arbeitsstand,
    Phasenuebersicht zu und auf."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": breite, "height": hoehe})
        seite.goto(f"{basis}/g/{token}")

        strom_id = _strom_schreiben("Mit euren Begriffen. Was faellt euch ")
        seite.wait_for_selector(".blase.vorlaeufig", timeout=10_000)
        seite.screenshot(path=str(SCHUSS / f"{name}-chat-stream.png"))

        seite.click(".roadmap summary")
        seite.wait_for_selector(".roadmap .phasen", state="visible")
        seite.screenshot(path=str(SCHUSS / f"{name}-phasen-auf.png"))
        seite.click(".roadmap summary")
        seite.screenshot(path=str(SCHUSS / f"{name}-phasen-zu.png"))

        seite.click('.tabs button[data-tab="stand"]')
        seite.wait_for_selector("#tab-stand:not([hidden])")
        seite.screenshot(path=str(SCHUSS / f"{name}-stand.png"), full_page=True)

        _strom_schreiben("fertig", "abgebrochen", strom_id)
        browser.close()
```

- [ ] **Schritt 2: Den Lauf machen**

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_vereint_e2e.py -q
```
Erwartet: alle passed, und in `docs/web-vereint/` liegen acht PNG.

```
ls docs/web-vereint/
```
Erwartet: `handy-chat-stream.png handy-phasen-auf.png handy-phasen-zu.png handy-stand.png
laptop-chat-stream.png laptop-phasen-auf.png laptop-phasen-zu.png laptop-stand.png`

- [ ] **Schritt 3: Die normale Suite ueberspringt sie weiterhin**

```
$PY -m pytest tests/e2e -q -p no:cacheprovider
```
Erwartet: `2 skipped` (oder mehr) — **kein** Fehler. Faellt es auf einen Importfehler, fehlt
das `pytest.importorskip` vor dem Playwright-Import.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1, `1 skipped` bleibt `1 skipped`.

- [ ] **Schritt 4: `tests/e2e/README.md` ergaenzen**

Ein Absatz hinter dem zur Probenansicht:

```markdown
Seit dem 30.09.2026 (Karte W) gehört die **vereinte Seite** (`/g/<token>`) dazu:
Tabwechsel während eines laufenden Streams und mit halb getipptem Text, die
Zurück-Taste, die Phasenleiste und der Phasenklick mit Rückfrage. Das ist die
einzige Stelle, an der sich messen lässt, dass der Wechsel wirklich nichts
verliert — im Server-Test sieht man nur, dass drei Panels ausgeliefert werden.
Screenshots gehen nach `docs/web-vereint/` und ins Repository: sie sind der
Beleg der Abnahme und zeigen deshalb ausschließlich erfundenes Material.
```

- [ ] **Schritt 5: Commit**

```bash
git add tests/e2e/test_web_vereint_e2e.py tests/e2e/README.md docs/web-vereint
git commit -m "Web vereint: Browserlauf und Screenshots fuer Handy und Laptop

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 17: Der echte Lauf — Stream gegen Infomaniak und Proxy · **KOSTET GELD**

**Dateien:**
- Neu: `scripts/strom_probe.py`
- Neu: `docs/web-vereint/strom-probe-<datum>.md` (committet — nur Zahlen)

**Diese Aufgabe kostet Geld und laeuft nach allen kostenlosen.** Sie misst **ANNAHME 4 und
5**: kann Infomaniak `stream: true` zusammen mit `response_format: json_schema` und liefert
es `usage`? Und gibt der Proxy Anthropic-SSE weiter?

**Kein Test, laeuft nie automatisch** — wie `scripts/rauchtest.py` und
`scripts/pruefe_prompts.py`. Zwei Aufrufe, beide klein.

- [ ] **Schritt 1: Das Skript schreiben**

`scripts/strom_probe.py`:

```python
"""Ein echter Stream-Aufruf gegen Infomaniak und gegen den Proxy.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/rauchtest.py``. Zwei Aufrufe mit kleinem ``max_tokens``, gegen eine
**Wegwerf-Datenbank**, mit **erfundenem** Material. Gemessen wird nur, was die
Karte wissen muss:

1. Kommt mehr als ein Teilstueck, und verteilt ueber mehr als eine Sekunde?
2. Steht am Ende eine ``usage`` (sonst greift der Rueckfall, und der
   Kostendeckel E7 stuende auf Schaetzungen)?
3. Ist die ``aufruf``-Zeile dieselbe wie ohne Stream?
4. Geht bei einem Reasoning-Modell wirklich nichts aus der Denkspur an die
   Gruppe?

Das Protokoll enthaelt **nur Zahlen** -- Zeitpunkte, Laengen, Anzahl, usage.
Kein Prompt, keine Antwort, keine Echtdaten.

    set -a; . ./betrieb/gruppe1.env; set +a
    python -m scripts.strom_probe --bericht
"""
```

Der Rumpf, in Stichpunkten (der Umsetzerin ueberlassen, weil es ein Messskript ist und
jede Zeile davon im Bericht landet):

1. `argparse`: `--bericht`, `--nur infomaniak|proxy`.
2. `einstellungen.laden()`; **verweigern**, wenn `IT_DB` gesetzt ist und auf die
   Betriebsdatenbank zeigt — geschrieben wird in eine `tempfile`-Datenbank
   (`db.verbinde` + `db.initialisiere`), wie `pruefe_prompts.py`.
3. **Infomaniak:** `LLM.schema(None, system, nutzer, ablauf.SCHEMA, "strom_probe",
   bei_teil=…)` mit einem erfundenen Nutzertext („Schreib drei Saetze ueber einen Bahnhof
   bei Nacht") und `ablauf.SCHEMA` — **genau dem Schema des Gespraechszugs**, denn genau das
   ist die offene Frage. Je Teilstueck `(time.monotonic() - start, len(text))` sammeln.
4. Denselben Aufruf **ohne** `bei_teil` wiederholen und die beiden `aufruf`-Zeilen
   vergleichen.
5. **Proxy:** `szene_claude.prosa(conn, e, httpx.Client(timeout=120), None, system, nutzer,
   "strom_probe_claude", timeout=120, bei_teil=…)` mit `MAX_TOKENS` voruebergehend auf 400
   (`monkeypatch`-frei: als Parameter oder durch Setzen des Modulwerts im Skript) und einem
   kurzen Auftrag.
6. Ausgabe auf stdout und, mit `--bericht`, nach
   `docs/web-vereint/strom-probe-<YYYY-MM-DD>.md`:

```markdown
# Strom-Probe <Datum>

| Weg | Teilstuecke | erstes bei | letztes bei | Zeichen | prompt_tokens | completion_tokens | finish |
|---|---|---|---|---|---|---|---|
| Infomaniak (schema + stream) | 37 | 0,41 s | 6,20 s | 612 | 421 | 158 | stop |
| Infomaniak (ohne stream) | — | — | 5,90 s | 612 | 421 | 158 | stop |
| Proxy (prosa + stream) | 22 | 0,80 s | 9,10 s | 498 | 512 | 140 | end_turn |

Befund: <ein Satz>
```

7. **Wenn Infomaniak `stream` mit `json_schema` ablehnt:** das Skript meldet es als Befund
   und endet mit Exit-Code 0 — es ist eine **Messung**, kein Test. Der Befund geht in den
   Abschlussbericht, der Rueckfall aus Entscheidung E greift im Betrieb von selbst, und der
   Gespraechszug streamt dann nicht. **Nichts am Prompt oder am Schema wird veraendert, um
   Streaming zu erzwingen** — das waere eine Aenderung an der gemessenen Grundlage des
   Korpus, und sie braucht Birks Entscheidung.

- [ ] **Schritt 2: Der Lauf**

```
set -a; . ./betrieb/gruppe1.env; set +a
$PY -m scripts.strom_probe --bericht
```
Erwartet (wenn ANNAHME 4 traegt):
* Infomaniak: **> 1** Teilstueck, erstes deutlich vor dem letzten (Abstand **> 1 s**),
  `prompt_tokens` und `completion_tokens` gesetzt, gleich der Zeile ohne Stream;
* Proxy: **> 1** Teilstueck, `input_tokens`/`output_tokens` gesetzt, `stop_reason=end_turn`;
* **kein** Teilstueck, das Denkspur-Text enthaelt.

- [ ] **Schritt 3: Der Befund**

Den Bericht durchlesen und **einen Satz** schreiben — er geht in den Abschlussbericht:

* traegt ANNAHME 4: „Infomaniak streamt `json_schema` mit `usage`; der Gespraechszug
  streamt im Betrieb."
* traegt sie nicht: „Infomaniak lehnt `stream` mit `json_schema` ab (HTTP `<code>`): der
  Gespraechszug streamt **nicht**, Szene und Kurzgeschichte schon. Entscheidung fuer Birk:
  Schema aufgeben und den Chat-Zug auf Prosa umstellen — oder so lassen."

- [ ] **Schritt 4: Commit**

```bash
git add scripts/strom_probe.py docs/web-vereint/strom-probe-*.md
git commit -m "Strom-Probe: echter Stream-Lauf gegen Infomaniak und Proxy, nur Zahlen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 18: Betrieb, Doku, Abschluss

**Dateien:**
- Aendern: `AGENTS.md` (Modultabelle, Weboberflaeche, Phasenregel, Modulkarte)
- Aendern: `docs/betrieb-env.beispiel` (falls Aufgabe 17 einen Schalter noetig macht)
- Test: kein neuer

- [ ] **Schritt 1: `AGENTS.md` — die Modultabelle**

Drei Zeilen ergaenzen (alphabetisch bei den Nachbarn eingeordnet):

```markdown
| `strom.py` | Der laufende Text (30.09.2026): dekodiert aus einem wachsenden JSON-Praefix den bisherigen Wert von `antwort` (der Gespraechszug ist ein **Schema**-Aufruf), saeubert ihn (`vorschlag.ohne_marker`, auch die halb getippte Markerzeile) und drosselt das Schreiben auf `INTERVALL_S` = 0,15 s. Reine Funktionen plus `Senke` mit drei Rueckrufen — **keine Datenbank**, kein `repo` |
| `roadmap.py` | Die Phasenuebersicht als Daten (30.09.2026): die sieben Phasen mit ihren Aufgaben, je `erledigt`/`offen`/`laeuft` und einem Sprungziel. Reine Leseabfrage wie `fehlstellen`; `aus_daten` ist rein, `register` liest ueber `repo`, `web_daten.roadmap` read-only. Die **Namen** der Aufgaben sind per Test an `phasentexte.PARAMETER` genagelt — keine zweite Wunschliste |
| `web_vereint.py` | Die vereinte Gruppenseite (30.09.2026): drei Panels (Chat · Arbeitsstand · Textbuch) in **einem** Dokument, Hash-Tabs, die Phasenleiste mit Klick, der SSE-Kanal `/g/<token>/chat/strom` und `scope_css`. `web.py` bekommt davon nur Routing-Zeilen |
```

In der **Modulkarte** (Abschnitt „Vier Schichten"): `strom.py` zu den **Diensten**,
`roadmap.py` zur **Fachlogik**, `web_vereint.py` zur **Oberflaeche**. In „Wo man anfaengt,
je nach Frage" zwei Zeilen:

```markdown
| Warum baut sich der Text im Browser auf? | `strom.Senke` → `web_kanal.WebKanal.strom` → `web_vereint.sende_strom` |
| Was passiert beim Klick auf eine Phase? | `web_vereint.phase_post` → `web_post` → `befehle.wechsle_phase` |
```

- [ ] **Schritt 2: `AGENTS.md` — die Phasenregel**

Im Abschnitt „Die Phase setzt allein die Gruppe" den ersten Satz aendern und einen Absatz
anhaengen:

```markdown
- **Die Phase setzt allein die Gruppe — per Chat, Befehl oder Klick** (seit
  05.09.2026, `phasen.py`, SPEC § 0 Leitsatz 3 Nachtrag; erweitert am
  30.09.2026): `phase_setzen`, `/phase` **oder ein Klick auf eine Phase in der
  Web-Phasenuebersicht**, nie still erraten und auch nicht vom Bot selbst. Der
  automatische Sprung (`ART_ERMOEGLICHT`, `sprung_nach`) bleibt **ersatzlos
  gestrichen** — **Datenstand ist nicht Absicht**; ein Klick dagegen *ist* die
  Gruppe.
  **Der Klick geht durch dieselbe Funktion wie der Befehl**
  (`befehle.wechsle_phase`, Parameter `quelle`), damit er nie in einer anderen
  Phase landet als `/phase` oder der Knopf: Bestaetigung im Browser → POST
  `/g/<token>/chat/phase` mit Nonce → ein gewoehnlicher Eingang
  (`WEB_TYP_BEFEHL`, Text `/phaseklick N`) → der **Bot** setzt die Phase und
  schickt die Eintrittsnachricht. Der Webserver setzt sie **nicht** selbst: er
  hat kein `klm`, und `knoepfe.eintritt_in_phase` stoesst Modellarbeit in
  Threads an. Im Journal steht `quelle 'web'` statt `'befehl'` — sonst ist die
  Zeile dieselbe (Test). `/phaseklick` ist ein **versteckter** Befehl: nicht im
  Menue, nirgends beworben, er ist der Weg des Knopfes durch die Naht.
```

- [ ] **Schritt 3: `AGENTS.md` — die Weboberflaeche**

Im Abschnitt „Weboberflaeche" die Routenliste ergaenzen und einen Unterabschnitt anhaengen:

```markdown
### Eine Oberflaeche je Gruppe (30.09.2026, Karte W)

`/g/<token>` ist seitdem **eine** Seite mit drei Tabs — **Chat** (der Ersatz
fuer Telegram, Karte A2), **Arbeitsstand** (die bisherige Gruppenseite, weiter
editierbar) und **Textbuch** (die Probenansicht). Alle drei liegen im
**selben Dokument**; umgeschaltet wird nur ueber `hidden`, nie ueber einen
Seitenwechsel — sonst riesse jeder Tabwechsel die laufende Aufnahme, die halb
getippte Nachricht und den laufenden Stream mit. Der Tab steht als blosses
Wort im Fragment (`#chat`, `#stand`, `#textbuch`), damit die Zurueck-Taste des
Handys funktioniert und ein Link teilbar bleibt; ein Rollenlink der
Probenansicht behaelt dabei seine Form (`#textbuch&figur=Leyla`).

**Die alten Adressen leben weiter**, und das ist keine Hoeflichkeit: die
Probenansicht (`/g/<token>/textbuch`, `.md`, `.txt`) und der Leitfaden
(`/g/<token>/leitfaden`) bleiben **eigene** Seiten mit ihrem `@media print`
und ohne Nachladen — gedruckte QR-Codes und geteilte Rollenlinks duerfen nicht
sterben. `/g/<token>/chat` (Karte A2) leitet mit **302** auf `/g/<token>#chat`.

**Nachgeladen wird nur noch das Stand-Panel** (`/g/<token>/teil/stand`,
`web_vereint.sende_teil`), mit denselben zwei Sperren wie bisher (Fokus in
einem Feld, ungespeicherte Aenderung) und **nur, wenn es sichtbar ist**.
`web._SCROLL_JS` steht weiter, aber die vereinte Seite laedt es nicht: es
tauscht `document.body.innerHTML`, und daran haengen Recorder, Eingabefeld und
Strom.

**Das CSS wird zur Laufzeit eingeschraenkt** (`web_vereint.scope_css`), die
bestehenden Konstanten bleiben Zeichen fuer Zeichen. Gemessen am 30.09.2026
kollidieren `_CSS_GRUPPE` und `_CSS_TEXTBUCH` in `body` und `h1`, und
`.leiste` heisst im Textbuch die Rollenleiste und im Chat die Knopfleiste; die
Probenansicht haengt ihren Zustand ausserdem an `<body>`, was im gemeinsamen
Dokument den Chat mitfaerben wuerde (deshalb `data-textbuch` als Wurzel).

**Das Team-Dashboard `/` bleibt unveraendert** — es haengt am Beamer, es zeigt
alle Gruppen, und es ist nicht diese Karte.

### Die Phasenuebersicht (30.09.2026, Karte W)

Oben auf der vereinten Seite, **eine Zeile hoch**: „Phase N von 7 · Name —
2/4". Per `<details>` aufklappbar zur vollen Liste aller sieben Phasen mit
ihren Aufgaben (✅ erledigt · ⏳ laeuft · ⬜ offen) — **ohne JavaScript
benutzbar**. Auf einem Telefon ist der Chat die Arbeitsflaeche; eine dauerhaft
aufgeklappte Liste naehme ein Drittel des Bildschirms fuer etwas, das man
dreimal am Tag braucht.

Die Daten kommen aus `roadmap.aus_daten` — **rein**, kein Modellaufruf, und
die Aufgabenliste ist per Test an `phasentexte.PARAMETER` genagelt: eine
zweite, frei erfundene Wunschliste waere der erste Stand, der ausschert
(dieselbe Regel wie bei `fehlstellen`). **'laeuft' zeigt nur, was in der
Datenbank steht** — Interviewmodus, `gruppe.web_tippt_bis`, eine laufende
Zeile in `web_strom`; ein Szenenlauf-Lock lebt im Bot-Prozess und ist fuer den
Webserver unsichtbar. Ein Klick auf eine **Aufgabe** springt zu ihrer Stelle
(Tab + Feld) und setzt **nichts**; ein Klick auf eine **Phase** schaltet um
(siehe Phasenregel oben).

### Der Strom (30.09.2026, Karte W)

Birk: „die website soll die llm antworten streamen koennen." Gestreamt werden
**Gespraechszug, Auftragszug, Szenenlauf und Prosalauf** — alles, dessen
Ergebnis ein Mensch liest. **Nicht** gestreamt werden Erkenner, Journal,
Verdichter, Sprachprofil, Schaerfung, Szenenfolge-Vorschlag und Dramaturgie:
ihr Ergebnis liest eine Maschine.

**Der Gespraechszug ist dabei ein Schema-Aufruf** (`ablauf.SCHEMA`,
`{"antwort": string}`) — was ankommt, ist ein wachsender JSON-Praefix, kein
Text. `strom.wert_aus_praefix` dekodiert daraus den bisherigen Wert, samt
halbem Escape, halber `\uXXXX`-Folge und halbem Surrogatpaar. **Kein Prompt
und kein Response-Format aendert sich dafuer** — der Korpus gilt unveraendert.

Der Weg: das Modell wird im **Bot**-Prozess gerufen, der Browser haengt am
**Web**-Prozess; dazwischen liegt die Tabelle `web_strom` (eine Zeile je
laufendem Aufruf, `zustand` laeuft/fertig/abgebrochen, `post_id` der fertigen
Nachricht). Der Bot schreibt gedrosselt (`strom.INTERVALL_S` = 0,15 s), der
Webserver liest read-only und schickt die Deltas per **SSE** ueber
`GET /g/<token>/chat/strom` (`text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, `Connection: close`, Keepalive alle 15 s, Ende nach
`STROM_MAX_S` = 300 s). **Karte A2 sagt „kein SSE" — diese eine Route ist die
Ausnahme**, fuer alles andere bleibt der Poll.

**Was sichtbar streamt, ist schon gesaeubert:** `strom.sichtbar` nimmt die
VORSCHLAG-Markerzeilen heraus, auch die halb getippte. **Kein halber Text wird
je eine Nachricht:** reisst der Anbieterstream nach dem ersten Stueck ab, geht
die Zeile auf `abgebrochen`, die vorlaeufige Blase verschwindet, und **genau
ein** Wiederholungsversuch ohne Stream holt die vollstaendige Antwort — eine
Buchung, nicht zwei. Lehnt der Anbieter `stream` ab oder liefert keine
`usage`, faellt der Prozess still auf den blockierenden Weg zurueck und
vermerkt das **einmal** (`strom_nicht_verfuegbar`), damit der Kostendeckel
nicht dauerhaft auf Schaetzungen steht. **Der Telegram-Weg bleibt unangetastet**:
`telegram.Telegram` hat kein `strom`, und ohne `bei_teil` ist jeder
Anbieteraufruf zeichengleich wie vorher (Test).

**Betriebshinweis nginx:** ohne `proxy_buffering off;` (oder mit einem Proxy,
der `X-Accel-Buffering` ignoriert) kommen die Teilstuecke am Stueck an. Die
nginx-Konfiguration liegt nicht im Repository; gemessen wird sie mit
`curl -N <URL>/g/<token>/chat/strom`.
```

- [ ] **Schritt 4: nginx pruefen (ANNAHME 6)**

```
curl -N -s -m 20 https://lab.artesmobiles.art/theatersoap/g/<token>/chat/strom | head -5
```
Erwartet: die Zeilen erscheinen **einzeln** und ueber die Zeit verteilt. Kommen sie am
Stueck, ist das ein **Befund fuer Birk** (mit der Zeile `proxy_buffering off;` als
Vorschlag) — **keine Repo-Aenderung**. In den Abschlussbericht.

- [ ] **Schritt 5: Der Abschluss**

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1, `1 skipped`.

```
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: gruen.

```
git status --short
```
Erwartet: **leer**. Die Arbeiterdateien (`.cc-settings.json`, `.superpowers-brief-*.md`,
`.cc-run-*`) gehoeren **nie** in einen Commit — stehen sie als `??` da, bleiben sie stehen
und werden nicht hinzugefuegt.

```
git log --oneline -20
```

- [ ] **Schritt 6: Commit**

```bash
git add AGENTS.md
git commit -m "Doku: vereinte Weboberflaeche, Phasenuebersicht, Strom und die Phasenregel

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Uebergaben

Was diese Karte bewusst **nicht** erledigt — jeweils mit dem Grund:

1. **Gestaltung** → die UX-Karte. Hier steht Struktur: Tabs, Panels, eine Phasenleiste,
   eine vorlaeufige Blase. Farben, Matrix-/Theater-Look, Typografie, die Frage, ob die
   Tableiste oben oder unten gehoert (auf einem Telefon spricht viel fuer unten) — alles
   dort. `_CSS_VEREINT` ist bewusst duenn gehalten, damit die UX-Karte nicht erst
   aufraeumen muss.
2. **Die Roadmap im Chat (`/stand`).** `roadmap.register` liegt fertig da und koennte
   `befehle._befehl_stand` um einen Block ergaenzen — diese Karte laesst es, weil `/stand`
   heute schon `phasentexte.standzeilen` **und** `fehlstellen.zeilen` zeigt und ein dritter
   Block aus derselben Datenlage die Nachricht zur Wand macht. Wer es baut, ersetzt damit
   besser einen der beiden, statt einen dritten danebenzustellen.
3. **Was im Stream kurz falsch stehen kann.** Die vorlaeufige Blase zeigt den **rohen**
   Modelltext (ohne Marker, aber sonst ungefiltert). Drei Dinge koennen darin einen Moment
   lang zu sehen sein und verschwinden dann:
   * ein **Denkspur-Rest** — `_ohne_denkspur` schneidet ihn erst, wenn die Antwort
     vollstaendig ist;
   * ein **Echo** der Gruppe — `_ohne_echo` erkennt es ebenfalls erst am Ende, und dann
     beginnt der Strom neu (die erste Fassung verschwindet sichtbar);
   * eine Antwort, die danach **verworfen** wird (Wiederholungsfilter, erfundene
     Systemzeile) — die Blase verschwindet ersatzlos.
   Das ist der Preis dafuer, dass man beim Schreiben zusieht. Fiele es im Betrieb auf,
   waere die Gegenmassnahme, die Blase erst ab N Zeichen zu zeigen oder die drei Filter
   praefix-faehig zu machen — beides ist mehr Arbeit, als der Befund heute wert ist.
4. **Kein Rate-Limit auf der SSE-Route.** Wer den Link hat, kann beliebig viele
   Stromverbindungen oeffnen; `ThreadingHTTPServer` bindet je Verbindung einen Thread.
   `STROM_MAX_S` deckelt die Lebensdauer, mehr nicht. Gehoert in dieselbe Karte wie das
   Rate-Limit aus A2 („Absicherung Web").
5. **Der Simulator kennt den Strom nicht.** `simulation/` faehrt ueber die
   Telegram-Attrappe, die kein `strom` hat — dort passiert also nichts, und die
   Kennzahlen bleiben vergleichbar. Ein Lauf ueber `WebKanal` waere der ehrlichere Test
   (schon A2s Uebergabe 5).
6. **Die Phase im Dashboard.** Das Team-Dashboard zeigt weiterhin nicht, welche Gruppe in
   welcher Phase steht und was ihr fehlt — `roadmap.aus_daten` koennte es in einer Zeile,
   aber das Dashboard ist projiziert und diese Karte fasst es nicht an.
7. **Fassungen und Leitfaden als vierter/fuenfter Tab.** Beide sind heute eigene Seiten und
   bleiben es: der Leitfaden, weil er ohne Nachladen und gross gesetzt in der Hand einer
   Sechzehnjaehrigen liegt; die Fassungsansicht, weil sie serverseitig ueber die Query
   laeuft (`?szene=…&fassung=…`) und im Stand-Panel unveraendert funktioniert.
8. **Ob der Gespraechszug wirklich streamt, entscheidet Aufgabe 17.** Lehnt Infomaniak
   `stream` mit `json_schema` ab, greift der Rueckfall, und die Frage „Schema aufgeben und
   den Chat-Zug auf Prosa umstellen?" geht an Birk — sie ruehrt an den Prompt und damit an
   den Regressionskorpus, und das entscheidet keine Umsetzungskarte nebenbei.

# Padua A2: Weboberflaeche als vollwertiger Arbeitsplatz der Gruppe

> **Fuer agentische Arbeiterinnen:** PFLICHT-UNTERSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Aufgabe fuer Aufgabe. Die Schritte tragen
> Kaestchen (`- [ ]`) zum Abhaken.

**Ziel:** Eine Gruppe macht den ganzen Workshop im Browser (Handy + Laptop) — Chat mit dem
Bot, Knoepfe als HTML-Knoepfe, Sprachaufnahme per MediaRecorder —, ohne dass `knoepfe/`
oder der Telegram-Weg angefasst werden.

**Architektur:** Der Webserver ist fuer den Bot das, was Telegrams Server heute ist. Er legt
Browser-Ereignisse als Telegram-foermige Updates in eine Tabelle `web_post`; ein normaler
Bot-Prozess (einer je Gruppe) liest sie mit einer neuen Kanal-Klasse `web_kanal.WebKanal`
statt mit `telegram.Telegram`. `bot.schleife` bleibt unveraendert, `bot.main` waehlt den Kanal
ueber `IT_KANAL`. Bot-Ausgaben (`sende`, `sende_mit_knoepfen`, …) schreiben in dieselbe
Tabelle; die Chatansicht liest sie read-only und pollt.

**Technik:** Python 3.11, Standardbibliothek (`http.server`, `sqlite3`, `json`, `hmac`),
Vanilla JS ohne Build, SQLite/WAL. Tests: `pytest` (ohne Netz, ohne Browser) plus
`tests/e2e` mit Playwright 1.61.0 aus dem Wegwerf-venv.

---

## Baseline (auf `d8deb6c` selbst gemessen)

```
/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 \
  -m pytest -q -p no:cacheprovider
→ 2768 passed, 1 skipped in 242.91s
```

`PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
Die `.venv` im Hauptbaum wird **nicht** benutzt. Am Ende muss die Zahl **≥ 2768** sein
(1 skipped bleibt: `tests/e2e` ueberspringt sich per `importorskip`).

---

## Nahtbefund: die Naht **traegt**

Gepruefte Frage: laesst sich `telegram.Telegram` durch eine andere Klasse ersetzen, ohne
`knoepfe/` (≈ 4.500 Zeilen) neu zu schreiben?

**Antwort: ja.** Der Beleg in vier Messungen am Quelltext von `d8deb6c`:

1. **Die ganze Kanalfläche sind zwölf Methoden**, und `interview_theater/` ruft sie
   ausnahmslos ueber das durchgereichte `tg`-Objekt:

   ```
   grep -rnoE '[a-zA-Z_]+\.(sende|sende_mit_knoepfen|sende_datei|beantworte_knopf|aendere_text|entferne_knoepfe|aktualisiere_knoepfe|loesche_nachrichten|setze_befehle|tippt|lade_datei|hole_updates)\(' interview_theater/
   ```

   | Methode | Aufrufe | belegte Stelle |
   |---|---|---|
   | `sende` | 194 + 2 | `interview_theater/knoepfe/basis.py:95`, `arbeitszeilen.py:135` |
   | `sende_mit_knoepfen` | 3 | `interview_theater/knoepfe/basis.py:161` |
   | `tippt` | 2 + 2 | `arbeitszeilen.py:131`, `arbeitszeilen.py:146` |
   | `hole_updates` | 1 | `bot.py:403` |
   | `beantworte_knopf` | 1 | `knoepfe/wirkung.py:1406` |
   | `entferne_knoepfe` | 1 | `knoepfe/basis.py:57` |
   | `aendere_text` | 1 | `arbeitszeilen.py:159` |
   | `loesche_nachrichten` | 1 + 1 | `arbeitszeilen.py:172`, `scripts/chat_leeren.py` |
   | `sende_datei` | 1 | `knoepfe/szenen.py` (Textbuch) |
   | `lade_datei` | 1 | `aufnahme.py:386` (via `_lade_mit_wiederholung`) |
   | `setze_befehle` | 1 | `bot.py:503` |
   | `aktualisiere_knoepfe` | **0** | nur `telegram.py:315` selbst, `simulation/attrappe.py:109` und drei Testattrappen |

   `aktualisiere_knoepfe` hat seit dem 06.09.2026 (Fragenauswahl per Nummer statt Toggle,
   `knoepfe/fragen.py:137-141`) **keinen Aufrufer in `interview_theater/`**. `WebKanal`
   implementiert sie trotzdem — gleiche Flaeche, damit der Naht-Test nicht lueckenhaft wird.

2. **Kein Weg geht an `tg` vorbei.** `grep -rn 'api.telegram.org' interview_theater/` ist
   leer (der einzige Treffer im Repo ist `scripts/chat_leeren_blind.py:33`, ein Handwerkzeug
   und kein Bot-Pfad). Kein Modul importiert `httpx`, um selbst mit Telegram zu sprechen.

3. **Die Attrappe beweist es empirisch.** `simulation/attrappe.py` ersetzt `Telegram` mit
   **neun** Methoden und faehrt damit `bot.verarbeite_update` + `bot._zug_und_erkenner`
   durch alle Phasen (`simulation/lauf.py:468-470`). Was `WebKanal` zusaetzlich leistet, ist
   genau eine Methode, die die Simulation nicht braucht: `hole_updates` (die Simulation
   ruft `verarbeite_update` direkt, `simulation/lauf.py:455-468`).

4. **Keine Telegram-Semantik sitzt ausserhalb von `telegram.py`.**
   - `from.first_name` steht an **einer** Stelle: `telegram.py:453`. E8 ist damit eine
     Eigenschaft des Adapters, keine Codeaenderung.
   - Negative `chat_id` wird nirgends angenommen:
     `grep -rnE 'chat_id\s*[<>]\s*0|abs\(chat_id|-100' interview_theater/` ist leer.
   - `parse_mode="HTML"` / `escape_html` gibt es an fuenf Stellen
     (`vorschlag.py:333-344`, `knoepfe/basis.py:297`, `knoepfe/szenen.py:300,418`,
     `knoepfe/figuren.py:459`) — Telegram-HTML, also eine **Darstellungs**aufgabe der
     Chatansicht (Aufgabe 7, Entscheidung F), kein Naht-Problem.

**Zwei Stellen, an denen die Naht doch einen Handgriff braucht** — beide einzeilig, beide
additiv, beide mit Bitgleich-Test:

- **`aufnahme.py:385` verdrahtet die Endung fest:**
  `ziel = Path(e.audio_verz) / str(chat_id) / f"{message_id}.ogg"`. `stt.mime_typ()` leitet
  den MIME-Typ aus der **Endung** ab (Falle 3). Ein `.webm` aus dem Browser, das als `.ogg`
  abgelegt wird, bekommt `audio/ogg` — und das quittiert Infomaniak mit einer `batch_id`
  und bleibt dauerhaft `pending` (89,7 s statt 2,0 s). Behoben in **Aufgabe 3**.
- **`telegram.lies_nachricht` liefert einen festen Schluesselsatz** ohne Endung. Additiver
  Schluessel `endung`, ebenfalls Aufgabe 3.

**Zwei Feinheiten, die die Architektur-Entscheidungen praeziser machen** (Abweichung mit
Beleg, nicht Widerspruch):

- **Zu G:** `knopf.message_id` ist **nicht** verlaesslich gesetzt.
  `repo.merke_knopf_nachricht` wird 22× gerufen, `_sende_knoepfe`/`_mit_leiste` aber 47× —
  `knoepfe.biete_einstieg` (`knoepfe/interviews.py:343-383`) setzt sie zum Beispiel nie.
  Eine Pruefung gegen `knopf.message_id` wuerde die Einstiegsknoepfe abweisen. Geprueft
  wird deshalb gegen die Leiste, die **`WebKanal` selbst** in `web_post.knoepfe` notiert
  hat — sie ist per Konstruktion "die aktuell haengende Leiste genau dieser message_id"
  und unabhaengig davon, ob ein Aufrufer `merke_knopf_nachricht` ruft.
- **Zu C:** `tippt` darf **keine** `web_post`-Zeile anlegen.
  `arbeitszeilen.TIPP_S = 4.0` heisst bei einem vierminuetigen Szenenlauf 60 Zeilen, die je
  eine `message_id` aus der gemeinsamen Folge verbrauchen. Die Tippanzeige ist keine
  Nachricht: sie landet in der additiven Spalte `gruppe.web_tippt_bis` (Aufgabe 2).

---

## Hotspots (parallel laufende Karten)

Karte **A1** (Branch `padua-workshop/t_28ed3dde…`, noch nicht in `main`) aendert
`web.py`, `aufnahme.py` und `db.py` gleichzeitig. Deshalb:

| Datei | Regel in diesem Plan |
|---|---|
| `interview_theater/web.py` | **nur Routing-Zeilen** (Aufgabe 6, ~14 Zeilen in zwei Funktionen). Alles HTML/CSS/JS/Handler liegt in `web_chat.py`. |
| `interview_theater/aufnahme.py` | **genau eine Zeile** (385), Aufgabe 3. |
| `interview_theater/telegram.py` | **genau eine Zeile** (im Rueckgabe-Dict von `lies_nachricht`), Aufgabe 3. |
| `interview_theater/bot.py` | **nur die Kanalweiche** in `main` (Aufgabe 4). `schleife` bleibt Zeichen fuer Zeichen. |
| `interview_theater/einstellungen.py` | zwei neue Variablen + ein `if` in `laden` (Aufgabe 4). |
| `interview_theater/db.py` | eine `CREATE TABLE`, zwei Spalten, ein Eintrag in `TABELLEN_MIT_CHAT_ID` (Aufgabe 1). **Keine** Erhoehung von `SCHEMA_VERSION` — die Migration ist rein additiv. |
| `interview_theater/repo.py` | neue Funktionen am Ende, keine bestehende geaendert. |
| `interview_theater/web_daten.py` | neue Lesefunktionen, read-only, keine bestehende geaendert. |

Neue Logik geht in **neue Module**: `web_kanal.py`, `web_chat.py`, `scripts/web_gruppe.py`.

---

## Globale Vorgaben

Gelten fuer **jede** Aufgabe, auch wenn dort nicht wiederholt:

- **Projektsprache Deutsch**, ASCII-Umschrift `ue/oe/ae/ss` in Code, Docstrings, Kommentaren
  und Commit-Zeilen. In Nutzertexten (HTML, Chat) sind echte Umlaute erlaubt, wie in
  `web.py` schon ueblich.
- **Neue UI-Texte als modulweite `_TEXT_*`-Konstanten** (Entscheidung K), damit Karte A1
  (`T = sprache.Texte(__name__)`) sie spaeter uebersetzen kann. Englische Eintraege sind
  **nicht** Teil dieser Karte.
- **SQL nur in `repo.py` (schreibend) und `web_daten.py` (read-only lesend).** `web_kanal.py`
  und `web_chat.py` enthalten kein einziges `SELECT`/`INSERT`/`UPDATE`/`DELETE`.
- **Kein Modellaufruf** in `web_chat.py`, `web_kanal.py` oder `scripts/web_gruppe.py` — sie
  importieren weder `llm` noch `stt`. Der Webserver bleibt Standardbibliothek.
- **Kein Frontend-Build**, kein npm, kein WebSocket, kein SSE, kein Cookie, kein
  localStorage. Vanilla JS, Polling per `fetch`.
- **Mobile zuerst.** 390×844 ist die Zielgroesse.
- **Der Telegram-Weg bleibt unveraendert funktionsfaehig (E1).** Ohne `IT_KANAL` verhaelt
  sich alles bitgleich wie heute.
- **Datenschutz:** Tests nur mit erfundenem Material (`simulation/interviews/`), **nie**
  `betrieb/**`. Keine Klarnamen, keine Echtdaten in Fixtures oder Screenshots.
- **E6:** Zugang allein ueber `/g/<token>`, kein Login. **E8:** Web-Nachrichten tragen
  keinen Vornamen.
- **Nie `git stash`** ohne `-m <tag>`; nie `checkout`/`switch`; committet wird
  ausschliesslich auf dem Branch/Worktree der ausfuehrenden Umsetzungskarte (t_d37deda1,
  `padua-workshop/t_d37deda1-…`), abgezweigt vom Plan-Branch
  `padua-workshop/t_fb48fb6c-plan-a2-web` oder von `main` mit diesem Plan. Kein Merge, kein
  Push — dafuer gibt es die [Merge]-Karte.
- Jede Aufgabe endet gruen: `$PY -m pytest -q -p no:cacheprovider` ≥ Baseline.

---

## Annahmen

Was beim Planen **nicht** geprueft werden konnte — je mit dem Kommando, das es klaert. Wer
eine Aufgabe anfaengt, in der eine Annahme steckt, fuehrt das Kommando **zuerst** aus.

**GEKLAERT durch den Architekten (30.09.2026, gemessen auf `d8deb6c` mit `hasattr`):**
`repo.hole_phase` (repo.py:1675) **existiert**, `repo.hole_aufnahme` **existiert**,
`phasen.aktuelle` **existiert**, `web_daten._phase` existiert **nicht**. Folge fuer die
Umsetzung: in Aufgabe 12 bleibt `repo.hole_phase(c, CHAT)` stehen (Hinweis 1 dort ist damit
erledigt); in Aufgabe 6 (`web_chatzustand`) wird die Phase **nicht** ueber `_phase` gelesen,
sondern wie die bestehende Leseseite ueber `_feld(zeile, "phase")` aus `arbeitsstand`
(web_daten.py:107) — keine neue Hilfsfunktion, kein `repo`-Import in `web_daten`.
ANNAHME 2 ist ebenfalls geklaert: `sqlite3.sqlite_version` = **3.53.1** (≥ 3.35, `DROP COLUMN`
geht). Die Pruefkommandos unten bleiben als Nachweis stehen.

**ANNAHME 1 (Aufgaben 6, 12, 13):** Die Namen der Lesefunktionen, die die Tests benutzen,
stimmen. Geprueft am Code sind `repo.hole_gruppe`, `repo.hole_arbeitsstand`,
`repo.ist_interviewmodus_an`, `repo.setze_interviewmodus`, `repo.setze_arbeitsstand`,
`repo.stelle_web_token_sicher`, `repo.lege_knopf_an`, `repo.transkripte`, `repo.setze_phase`
und `web_daten.chat_id_nach_token`. **Nicht** geprueft: `repo.hole_phase` (im Plan an einer
Stelle in Aufgabe 12 benutzt), `repo.hole_aufnahme` (Aufgabe 3) und `web_daten._phase`
(Aufgabe 6). Der Code nimmt fuer die Phase `phasen.aktuelle(conn, chat_id)` — im Zweifel
**das** benutzen, es ist laut AGENTS.md die eine Quelle.

```
$PY -c "from interview_theater import repo, phasen, web_daten; \
print('hole_phase', hasattr(repo,'hole_phase')); \
print('hole_aufnahme', hasattr(repo,'hole_aufnahme')); \
print('aktuelle', hasattr(phasen,'aktuelle')); \
print('_phase', hasattr(web_daten,'_phase'))"
```

**ANNAHME 2 (Aufgabe 1, Migrationstest):** SQLite kann `ALTER TABLE … DROP COLUMN` (seit
3.35). Kann es die gebundelte Fassung nicht, baut der Test die alte Datenbank stattdessen ohne
die Spalte auf (`CREATE TABLE gruppe (…)` von Hand) — der Sinn des Tests ist die Migration,
nicht das Loeschen.

```
$PY -c "import sqlite3; print(sqlite3.sqlite_version)"
```
Erwartet: ≥ `3.35.0`.

**ANNAHME 3 (Aufgabe 13):** Playwrights `page.mouse.down()` erzeugt Pointer-Events mit
`pointerId: 1`. Der Test `test_ptt_mit_pointercancel_sendet_nichts` schickt ein
`pointercancel` mit genau dieser id; stimmt sie nicht, greift `releasePointerCapture` nicht,
und der Test schlaegt aus dem falschen Grund an.

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -c \
 "import playwright; print(playwright.__version__)"
```
Und im Lauf notfalls die id aus dem Browser lesen:
`seite.evaluate("new Promise(r => document.addEventListener('pointerdown', e => r(e.pointerId), {once:true})))")`.

**ANNAHME 4 (Aufgabe 15, kostet Geld):** Infomaniak-Whisper transkribiert
`audio/webm;codecs=opus` (Chrome, Firefox) und `audio/mp4` (Safari). Beide stehen in
`stt._MIME_TYPEN`, also gehen sie durch den Code — ob der Anbieter sie annimmt, ist nicht
gemessen, und die Fehlerrichtung ist boese (Falle 3: `batch_id` statt Ablehnung, dann
dauerhaft `pending`). Pruefkommando und Befundvorlage stehen in Aufgabe 15.

**ANNAHME 5 (Aufgabe 12):** Der Weg Phase 1 → 3 laeuft so, wie er in der Tabelle in
Aufgabe 12 steht. Die Kette ist am Code nachgelesen (`knoepfe/basis.offene_art`,
`knoepfe/wirkung._wirkung_speichern`, `knoepfe/fragen._speichere_eroeffnung`,
`phasen.voraussetzungen`), aber nicht gefahren. Traegt sie nicht, erlaubt die Karte den
Text-Import-Weg (`aufnahme.importiere_text`) — dann **im Test-Docstring benennen, welcher Weg
gewaehlt wurde und warum**, und den Audio-Teil getrennt fahren.

---

## Dateikarte

| Datei | Verantwortung | Aufgabe |
|---|---|---|
| `interview_theater/db.py` | Tabelle `web_post`, Spalten `gruppe.kanal`, `gruppe.web_tippt_bis`, `TABELLEN_MIT_CHAT_ID` | 1 |
| `interview_theater/repo.py` | alle Schreib- und Bot-Lesezugriffe auf `web_post` | 1 |
| `interview_theater/web_kanal.py` | **neu.** `WebKanal` — die Kanal-Klasse (Schicht Dienste) | 2, 3 |
| `interview_theater/telegram.py` | additiver Schluessel `endung` in `lies_nachricht` | 3 |
| `interview_theater/aufnahme.py` | Endung des Zielpfads aus `n["endung"]` | 3 |
| `interview_theater/einstellungen.py` | `IT_KANAL`, `IT_WEB_CHAT_ID`, `IT_WEB_SEGMENT_MS` | 4 |
| `interview_theater/bot.py` | Kanalweiche in `main` | 4 |
| `scripts/web_gruppe.py` | **neu.** Web-Gruppe anlegen, Link und Env-Zeilen ausgeben | 5 |
| `interview_theater/web_daten.py` | `web_chatverlauf`, `web_chatzustand`, `web_ausgangsdatei` | 6 |
| `interview_theater/web_chat.py` | **neu.** HTML/CSS/JS und alle Handler der Chatansicht | 6–11 |
| `interview_theater/web.py` | Routing-Zeilen fuer `/g/<token>/chat…` | 6 |
| `docs/betrieb-env.beispiel`, `AGENTS.md`, `docs/interview-theater@.service` | Betrieb und Doku | 14 |

---

## Aufgabenuebersicht

| # | Titel | kostet Geld |
|---|---|---|
| 1 | Die Tabelle `web_post` und ihre `repo`-Funktionen | nein |
| 2 | `WebKanal`: die neun Ausgabemethoden + `hole_updates` + Naht-Test | nein |
| 3 | Audio durch die Naht: `sende_datei`, `lade_datei`, die Endung | nein |
| 4 | `IT_KANAL` und die Kanalweiche in `bot.main` | nein |
| 5 | `scripts/web_gruppe.py` | nein |
| 6 | Die Chatansicht: HTML-Filter, Verlauf, Routing | nein |
| 7 | Text senden und der Zustands-Poll | nein |
| 8 | Knopf druecken | nein |
| 9 | Audio-Upload | nein |
| 10 | Interview-Umschalter serverseitig | nein |
| 11 | Das Browser-JavaScript: Recorder, Segmente, PTT | nein |
| 12 | Abnahme-E2E per HTTP in der normalen Suite | nein |
| 13 | Browserlauf und Handy-Screenshot | nein |
| 14 | Betrieb, Doku, Abschluss | nein |
| 15 | **Vorbedingung Whisper: webm/mp4 aus dem Browser** | **JA** |

---

## Aufgabe 1: Die Tabelle `web_post` und ihre `repo`-Funktionen

**Dateien:**
- Aendern: `interview_theater/db.py` (`SCHEMA`, `TABELLEN_MIT_CHAT_ID`)
- Aendern: `interview_theater/repo.py` (neue Funktionen am Dateiende)
- Test: `tests/test_web_post.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/repo.py
RICHTUNG_EIN = "ein"
RICHTUNG_AUS = "aus"
WEB_TYP_TEXT = "text"        # beide Richtungen
WEB_TYP_SPRACHE = "sprache"  # nur 'ein'
WEB_TYP_KNOPF = "knopf"      # nur 'ein'
WEB_TYP_BEFEHL = "befehl"    # nur 'ein', in der Ansicht verborgen
WEB_TYP_DATEI = "datei"      # nur 'aus'
WEB_CHAT_ID_BASIS = 7_000_000_000_000

def web_knoepfe(zeile) -> list[list[str]]
def lege_web_post_an(conn, chat_id: int, richtung: str, typ: str, *,
                     text=None, knoepfe=None, daten=None, bezug_message_id=None,
                     dauer=None, datei=None, mime=None, dateiname=None) -> int
def web_eingang(conn, chat_id: int, ab_update_id: int, grenze: int = 50) -> list
def hole_web_post(conn, post_id: int)
def aendere_web_text(conn, chat_id: int, message_id: int, text: str) -> bool
def setze_web_knoepfe(conn, chat_id: int, message_id: int, knoepfe) -> bool
def loesche_web_posts(conn, chat_id: int, message_ids: list) -> int
def setze_web_antwort(conn, post_id: int, text: str) -> None
def setze_web_tippt(conn, chat_id: int, bis_iso) -> None
def setze_gruppe_kanal(conn, chat_id: int, kanal: str) -> None
def naechste_web_chat_id(conn) -> int
```

`knoepfe` wird als JSON-Liste von Zweierlisten gespeichert (`json.dumps`,
`ensure_ascii=False`); `None` heisst „keine Leiste". Die Serialisierung gehoert in die
Ablageschicht, damit kein Aufrufer die Form kennen muss.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_post.py`:

```python
"""Die Tabelle web_post: EINE message_id-Folge fuer Gruppe UND Bot.

Warum das der Kern ist (Lehre aus simulation/attrappe.py.naechste_message_id):
der Bot merkt sich seinen Stand als letzte_beantwortete_message_id und liest
danach nur, was GROESSER ist. Zaehlten Gruppe und Bot in getrennten Folgen,
laege jede Gruppennachricht ab dem zweiten Zug unter dem Wasserzeichen.
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


def test_eine_folge_fuer_beide_richtungen(conn):
    ein = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="Hallo")
    aus = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                               text="Auch hallo")
    zweite = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                   text="Und weiter")
    assert ein < aus < zweite


def test_eingang_liefert_nur_eingehende_ab_dem_offset(conn):
    erste = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="botantwort")
    zweite = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="b")

    assert [z["id"] for z in repo.web_eingang(conn, CHAT, 0)] == [erste, zweite]
    assert [z["id"] for z in repo.web_eingang(conn, CHAT, erste + 1)] == [zweite]


def test_eingang_ignoriert_fremde_gruppen(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    repo.lege_web_post_an(conn, ANDERE, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="nicht meine")
    assert repo.web_eingang(conn, CHAT, 0) == []


def test_knoepfe_kommen_als_liste_zurueck(conn):
    leiste = [("Ja, speichern", "k:12"), ("Nein, nochmal ändern", "k:13")]
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="Speichern?", knoepfe=leiste)
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [
        ["Ja, speichern", "k:12"], ["Nein, nochmal ändern", "k:13"],
    ]


def test_leiste_austauschen_und_entfernen(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="x", knoepfe=[("A", "k:1")])
    assert repo.setze_web_knoepfe(conn, CHAT, post_id, [("B", "k:2")]) is True
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [["B", "k:2"]]
    assert repo.setze_web_knoepfe(conn, CHAT, post_id, None) is True
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == []


def test_fremde_gruppe_darf_keine_leiste_aendern(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="x", knoepfe=[("A", "k:1")])
    assert repo.setze_web_knoepfe(conn, ANDERE, post_id, None) is False
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [["A", "k:1"]]


def test_text_aendern_und_loeschen(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="alt")
    assert repo.aendere_web_text(conn, CHAT, post_id, "neu") is True
    assert repo.hole_web_post(conn, post_id)["text"] == "neu"
    assert repo.loesche_web_posts(conn, CHAT, [post_id]) == 1
    assert repo.hole_web_post(conn, post_id)["geloescht_am"] is not None
    # Weiches Loeschen zweimal aendert nichts mehr.
    assert repo.loesche_web_posts(conn, CHAT, [post_id]) == 0


def test_antwort_auf_einen_knopfdruck(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF,
                                    daten="k:7", bezug_message_id=3)
    repo.setze_web_antwort(conn, post_id, "Begriffe uebernommen")
    assert repo.hole_web_post(conn, post_id)["antwort"] == "Begriffe uebernommen"


def test_tippt_steht_in_der_gruppe_und_nicht_als_nachricht(conn):
    vorher = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="x")
    repo.setze_web_tippt(conn, CHAT, "2026-09-30T10:00:08+00:00")
    assert repo.hole_gruppe(conn, CHAT)["web_tippt_bis"] == "2026-09-30T10:00:08+00:00"
    nachher = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="y")
    # Die Tippanzeige verbraucht keine message_id: arbeitszeilen.TIPP_S = 4,0 s
    # heisst bei einem vierminuetigen Szenenlauf 60 Anzeigen.
    assert nachher == vorher + 1


def test_kanal_ist_ohne_zutun_telegram(conn):
    assert repo.hole_gruppe(conn, CHAT)["kanal"] == "telegram"
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    assert repo.hole_gruppe(conn, CHAT)["kanal"] == "web"


def test_naechste_web_chat_id_liegt_ausserhalb_der_telegram_bereiche(conn):
    erste = repo.naechste_web_chat_id(conn)
    assert erste > CHAT >= repo.WEB_CHAT_ID_BASIS
    assert repo.hole_gruppe(conn, erste) is None
    repo.sichere_gruppe(conn, erste, "gruppeX", "X")
    assert repo.naechste_web_chat_id(conn) == erste + 1


def test_web_post_steht_im_loeschweg():
    # Die Loeschzusage ist ein DELETE je Tabelle (db.loesche_gruppe) -- eine
    # Tabelle mit chat_id, die dort fehlt, ueberlebt das Loeschen einer Gruppe.
    assert "web_post" in db.TABELLEN_MIT_CHAT_ID


def test_loesche_gruppe_nimmt_web_posts_mit(conn):
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a")
    db.loesche_gruppe(conn, CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0


def test_migration_ruestet_web_post_in_einer_alten_datenbank_nach(tmp_path):
    # db.py migriert ausschliesslich additiv (AGENTS.md): eine Datenbank ohne
    # die Tabelle und ohne die Spalte muss beides beim naechsten Start
    # bekommen, ohne einen user_version-Schritt.
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    alt.execute("DROP TABLE web_post")
    alt.execute("ALTER TABLE gruppe DROP COLUMN kanal")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)
    repo.sichere_gruppe(neu, CHAT, "gruppe1", "X")
    assert repo.lege_web_post_an(
        neu, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a"
    ) > 0
    assert repo.hole_gruppe(neu, CHAT)["kanal"] == "telegram"
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_post.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.repo' has no attribute 'RICHTUNG_EIN'`.

- [x] **Schritt 3: Schema in `db.py`**

In `SCHEMA` **nach** der `knopf`-Tabelle einfuegen. Die Form (`CREATE TABLE IF NOT EXISTS
<name> (` … `\n);`) ist Pflicht: `db._tabellenspalten_aus_schema` liest sie per Regex, und
daran haengt die additive Spaltenmigration.

```sql
-- Der Web-Kanal (30.09.2026, Karte Padua A2): der Webserver ist fuer den Bot
-- das, was Telegrams Server heute ist. Browser-Ereignisse liegen hier als
-- Eingang ('ein'), Bot-Ausgaben als Ausgang ('aus').
--
-- EINE Tabelle fuer beide Richtungen, und das ist der Kern: ``id`` ist
-- zugleich die ``message_id`` und die ``update_id``. Zaehlten Gruppe und Bot
-- in getrennten Folgen, laege jede Gruppennachricht ab dem zweiten Zug unter
-- dem Wasserzeichen ``gruppe.letzte_beantwortete_message_id``, und der Bot
-- beantwortete sie nie (gemessen in simulation/attrappe.naechste_message_id).
-- Telegram vergibt die ids ebenfalls fortlaufend je Chat, ueber alle Absender.
--
-- Die Tippanzeige steht NICHT hier, sondern in gruppe.web_tippt_bis:
-- arbeitszeilen.TIPP_S = 4,0 s heisst bei einem vierminuetigen Szenenlauf 60
-- Aufrufe, und eine Tippanzeige ist keine Nachricht.
CREATE TABLE IF NOT EXISTS web_post (
  id                INTEGER PRIMARY KEY,        -- = message_id = update_id
  chat_id           INTEGER NOT NULL,
  richtung          TEXT NOT NULL,              -- 'ein' (Browser) | 'aus' (Bot)
  -- 'ein': text|sprache|knopf|befehl -- 'aus': text|datei
  -- 'befehl' ist ein Umschalter-Druck, der als Slash-Text in den Bot geht und
  -- in der Chatansicht verborgen bleibt: Slash-Befehle werden nicht beworben.
  typ               TEXT NOT NULL,
  text              TEXT,
  knoepfe           TEXT,                       -- JSON [[beschriftung, daten], ...]
  daten             TEXT,                       -- 'knopf': die callback_data
  bezug_message_id  INTEGER,                    -- 'knopf': unter welcher Nachricht
  antwort           TEXT,                       -- 'knopf': answerCallbackQuery-Text
  dauer             INTEGER,                    -- 'sprache': Sekunden vom Client
  datei             TEXT,                       -- 'sprache'/'datei': Pfad
  mime              TEXT,
  dateiname         TEXT,                       -- 'datei': Name fuer den Download
  geloescht_am      TEXT,                       -- loesche_nachrichten, weich
  erstellt_am       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_web_post_eingang
  ON web_post(chat_id, richtung, id);
```

In der `gruppe`-Tabelle zwei Spalten anhaengen, hinter `web_token` (dort das fehlende
Komma setzen):

```sql
  -- Welcher Kanal diese Gruppe bedient (30.09.2026): 'telegram' (Vorgabe) oder
  -- 'web'. Additiv nachgeruestet ueber _migriere_fehlende_spalten.
  kanal                           TEXT NOT NULL DEFAULT 'telegram',
  -- Bis wann die Tippanzeige im Web gilt (ISO 8601). Eine Spalte statt einer
  -- Zeile je Aufruf, siehe den Kommentar an web_post.
  web_tippt_bis                   TEXT
```

`TABELLEN_MIT_CHAT_ID` bekommt `"web_post"` (hinter `"knopf"`).

**`SCHEMA_VERSION` bleibt bei 3.** Die Migration ist rein additiv und braucht keinen
`user_version`-Schritt — wie `_migriere_erste_szenenfassung`.

- [x] **Schritt 4: Lauf, der Loeschweg-Test muss durch sein**

```
$PY -m pytest tests/test_web_post.py -q -p no:cacheprovider -k loeschweg
```
Erwartet: `1 passed`.

- [x] **Schritt 5: `repo.py` — die Funktionen**

Am Dateiende anhaengen. `import json` im Modulkopf ergaenzen, falls noch nicht vorhanden.

```python
# --- Der Web-Kanal (30.09.2026, Karte Padua A2) ----------------------------

#: Die beiden Richtungen in ``web_post``.
RICHTUNG_EIN = "ein"
RICHTUNG_AUS = "aus"

#: Die Typen. ``befehl`` geht als Slash-Text in den Bot und bleibt in der
#: Chatansicht verborgen -- Slash-Befehle werden nicht beworben (AGENTS.md).
WEB_TYP_TEXT = "text"
WEB_TYP_SPRACHE = "sprache"
WEB_TYP_KNOPF = "knopf"
WEB_TYP_BEFEHL = "befehl"
WEB_TYP_DATEI = "datei"

#: Ab hier liegen die synthetischen chat_ids der Web-Gruppen. Positiv und weit
#: oberhalb aller Telegram-Bereiche (Gruppen sind dort negativ, Nutzer-ids
#: liegen unter 10^10): eine Web-chat_id kann so nie mit einer echten
#: kollidieren. Geprueft am 30.09.2026: im ganzen Repo leitet keine Stelle aus
#: dem Vorzeichen einer chat_id etwas ab.
WEB_CHAT_ID_BASIS = 7_000_000_000_000


def web_knoepfe(zeile) -> list[list[str]]:
    """Die Leiste einer ``web_post``-Zeile als Liste ``[beschriftung, daten]``.

    Reine Funktion ohne Datenbankzugriff, damit der Bot-Prozess und die
    read-only Leseseite dieselbe Deutung benutzen: die Form des JSON soll an
    genau einer Stelle stehen. Kaputtes JSON gibt eine leere Liste und keinen
    Fehler -- eine Nachricht ohne Knoepfe ist besser als eine Seite, die nicht
    laedt."""
    if zeile is None:
        return []
    roh = zeile["knoepfe"] if "knoepfe" in zeile.keys() else None
    if not roh:
        return []
    try:
        gelesen = json.loads(roh)
    except (TypeError, ValueError):
        return []
    return [list(eintrag) for eintrag in gelesen if len(eintrag) == 2]


@_gesperrt
def lege_web_post_an(conn, chat_id: int, richtung: str, typ: str, *,
                     text=None, knoepfe=None, daten=None,
                     bezug_message_id=None, dauer=None,
                     datei=None, mime=None, dateiname=None) -> int:
    """Legt eine Zeile in ``web_post`` an und liefert ihre id.

    Die id ist zugleich ``message_id`` und ``update_id`` -- eine Folge fuer
    beide Richtungen (siehe Tabellenkommentar in db.py)."""
    cur = conn.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, text, knoepfe, daten, "
        "bezug_message_id, dauer, datei, mime, dateiname, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chat_id, richtung, typ, text,
            json.dumps([list(k) for k in knoepfe], ensure_ascii=False)
            if knoepfe else None,
            daten, bezug_message_id, dauer, datei, mime, dateiname, _jetzt(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


@_gesperrt
def web_eingang(conn, chat_id: int, ab_update_id: int, grenze: int = 50) -> list:
    """Die eingehenden Posts ab ``ab_update_id``, aelteste zuerst.

    Das Gegenstueck zu ``telegram.Telegram.hole_updates``: ``bot.schleife``
    rechnet ``offset = hole_update_id() + 1`` und erwartet alles ab dort.
    ``grenze`` deckelt einen Stapel, damit ein Browser, der nach einer
    Netztrennung zehn Segmente nachschiebt, die Schleife nicht blockiert --
    der Rest kommt im naechsten Durchlauf."""
    return conn.execute(
        "SELECT * FROM web_post WHERE chat_id = ? AND richtung = ? AND id >= ? "
        "AND geloescht_am IS NULL ORDER BY id ASC LIMIT ?",
        (chat_id, RICHTUNG_EIN, ab_update_id, grenze),
    ).fetchall()


@_gesperrt
def hole_web_post(conn, post_id: int):
    """Eine Zeile, egal welcher Richtung und ob geloescht -- der Aufrufer muss
    den Unterschied kennen (wie bei ``hole_knopf``)."""
    return conn.execute("SELECT * FROM web_post WHERE id = ?", (post_id,)).fetchone()


@_gesperrt
def aendere_web_text(conn, chat_id: int, message_id: int, text: str) -> bool:
    """Tauscht den Text einer ausgehenden Nachricht (``aendere_text``).

    ``chat_id`` steht in der Bedingung und nicht nur in der Signatur:
    dieselbe Datenbank traegt alle Gruppen des Workshops."""
    cur = conn.execute(
        "UPDATE web_post SET text = ? WHERE id = ? AND chat_id = ? "
        "AND richtung = ? AND geloescht_am IS NULL",
        (text, message_id, chat_id, RICHTUNG_AUS),
    )
    conn.commit()
    return cur.rowcount > 0


@_gesperrt
def setze_web_knoepfe(conn, chat_id: int, message_id: int, knoepfe) -> bool:
    """Tauscht die Leiste unter einer ausgehenden Nachricht aus; ``None``
    nimmt sie weg (``entferne_knoepfe`` / ``aktualisiere_knoepfe``)."""
    cur = conn.execute(
        "UPDATE web_post SET knoepfe = ? WHERE id = ? AND chat_id = ? "
        "AND richtung = ? AND geloescht_am IS NULL",
        (
            json.dumps([list(k) for k in knoepfe], ensure_ascii=False)
            if knoepfe else None,
            message_id, chat_id, RICHTUNG_AUS,
        ),
    )
    conn.commit()
    return cur.rowcount > 0


@_gesperrt
def loesche_web_posts(conn, chat_id: int, message_ids: list) -> int:
    """Nimmt Nachrichten aus der Ansicht (``loesche_nachrichten``) -- weich,
    mit ``geloescht_am``, wie alles Entfernte in diesem Projekt. Liefert die
    Zahl der wirklich betroffenen Zeilen (hoechstens 100, wie Telegram)."""
    if not message_ids:
        return 0
    jetzt = _jetzt()
    getroffen = 0
    for message_id in message_ids[:100]:
        cur = conn.execute(
            "UPDATE web_post SET geloescht_am = ? WHERE id = ? AND chat_id = ? "
            "AND geloescht_am IS NULL",
            (jetzt, message_id, chat_id),
        )
        getroffen += cur.rowcount
    conn.commit()
    return getroffen


@_gesperrt
def setze_web_antwort(conn, post_id: int, text: str) -> None:
    """Der Text aus ``answerCallbackQuery`` zu einem Knopfdruck. Der Browser
    holt ihn beim naechsten Zustands-Poll ab -- in Telegram ist das die
    kleine Blase ueber dem Knopf."""
    conn.execute(
        "UPDATE web_post SET antwort = ? WHERE id = ? AND typ = ?",
        (text, post_id, WEB_TYP_KNOPF),
    )
    conn.commit()


@_gesperrt
def setze_web_tippt(conn, chat_id: int, bis_iso) -> None:
    """Bis wann die Tippanzeige gilt. Eine Spalte statt einer Zeile je
    Aufruf: ``arbeitszeilen`` ruft ``tippt`` alle vier Sekunden."""
    conn.execute(
        "UPDATE gruppe SET web_tippt_bis = ? WHERE chat_id = ?", (bis_iso, chat_id)
    )
    conn.commit()


@_gesperrt
def setze_gruppe_kanal(conn, chat_id: int, kanal: str) -> None:
    """'telegram' oder 'web'. Gesetzt von ``scripts/web_gruppe.py``."""
    conn.execute("UPDATE gruppe SET kanal = ? WHERE chat_id = ?", (kanal, chat_id))
    conn.commit()


@_gesperrt
def naechste_web_chat_id(conn) -> int:
    """Die naechste freie synthetische chat_id fuer eine Web-Gruppe."""
    hoechste = conn.execute(
        "SELECT MAX(chat_id) FROM gruppe WHERE chat_id >= ?", (WEB_CHAT_ID_BASIS,)
    ).fetchone()[0]
    return WEB_CHAT_ID_BASIS if hoechste is None else int(hoechste) + 1
```

- [x] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_post.py -q -p no:cacheprovider
```
Erwartet: `15 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `2783 passed, 1 skipped`.

- [x] **Schritt 7: Commit**

```bash
git add interview_theater/db.py interview_theater/repo.py tests/test_web_post.py
git commit -m "Web-Kanal: Tabelle web_post, eine message_id-Folge fuer Gruppe und Bot

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 2: `WebKanal` — die Ausgabemethoden, `hole_updates` und der Naht-Test

**Dateien:**
- Neu: `interview_theater/web_kanal.py` (Schicht **Dienste**)
- Test: `tests/test_web_kanal.py` (neu)
- Test: `tests/test_web_kanal_naht.py` (neu — die Nahtpruefung per AST, Entscheidung A)

**Schnittstellen — Konsumiert:** alles aus Aufgabe 1.
**Schnittstellen — Produziert:**

```python
# interview_theater/web_kanal.py
ABSENDER = "Gruppe"
TIPPT_GUELTIG_S = 8
POLL_SCHRITT_S = 0.25

class WebKanal:
    def __init__(self, conn, chat_id: int, audio_verz: str,
                 schritt_s: float = POLL_SCHRITT_S) -> None
    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]
    def sende(self, chat_id: int, text: str, parse_mode=None, klartext=None) -> int
    def sende_mit_knoepfen(self, chat_id: int, text: str, knoepfe,
                           parse_mode=None, klartext=None) -> int
    def sende_datei(self, chat_id: int, dateiname: str, inhalt, beschreibung: str = "") -> int
    def beantworte_knopf(self, callback_query_id: str, text: str = "") -> None
    def aendere_text(self, chat_id: int, message_id: int, text: str) -> None
    def entferne_knoepfe(self, chat_id: int, message_id: int) -> None
    def aktualisiere_knoepfe(self, chat_id: int, message_id: int, knoepfe) -> None
    def loesche_nachrichten(self, chat_id: int, message_ids: list[int]) -> int
    def setze_befehle(self, befehle: list[dict]) -> None
    def tippt(self, chat_id: int) -> None
    def lade_datei(self, file_id: str, ziel) -> None      # Aufgabe 3
def datei_verweis(post_id: int, endung: str) -> str        # Aufgabe 3
def lies_verweis(file_id: str) -> tuple[int, str] | None   # Aufgabe 3
```

`sende_datei` und `lade_datei` bekommen in **dieser** Aufgabe nur einen Rumpf, der
`NotImplementedError` wirft — ausgefuellt werden sie in Aufgabe 3. Der Naht-Test prueft die
Existenz und die Signatur, nicht die Wirkung; so bleibt Aufgabe 2 klein und der Naht-Test
steht schon da, wenn die Audio-Arbeit beginnt.

- [x] **Schritt 1: Den Naht-Test schreiben**

`tests/test_web_kanal_naht.py`:

```python
"""Die Nahtpruefung: traegt die Ersetzung von telegram.Telegram?

Der Test liest ``interview_theater/`` per AST und sammelt JEDEN Attributaufruf
auf einem Objekt, das ein Kanal ist (heisst ``tg`` oder ``_tg``). Jede so
gefundene Methode muss ``web_kanal.WebKanal`` mit derselben Signatur haben.

Warum per AST und nicht per grep: ein neuer Aufrufer, der eine
dreizehnte Methode benutzt, soll HIER auffallen und nicht im Betrieb, wenn
eine Gruppe im Browser vor einem AttributeError sitzt.

Dazu drei Sperren gegen Wege, die an ``tg`` VORBEI gehen -- gemessen am
30.09.2026, alle drei damals leer. Sie muessen leer bleiben.
"""

import ast
import inspect
from pathlib import Path

from interview_theater import telegram, web_kanal

WURZEL = Path(telegram.__file__).resolve().parent

#: Wie ein Kanal-Objekt in diesem Repo heisst. ``tg`` ueberall,
#: ``self._tg`` in ``arbeitszeilen.Lauf``.
KANALNAMEN = {"tg", "_tg"}

#: Dateien, die die Naht selbst sind und deshalb nicht dagegen gemessen werden.
AUSGENOMMEN = {"telegram.py", "web_kanal.py"}


def _kanalaufrufe() -> dict[str, set[str]]:
    """Methode -> {"datei:zeile", ...} fuer jeden Aufruf auf einem Kanal."""
    gefunden: dict[str, set[str]] = {}
    for pfad in sorted(WURZEL.rglob("*.py")):
        if pfad.name in AUSGENOMMEN:
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            ziel = knoten.func
            if not isinstance(ziel, ast.Attribute):
                continue
            basis = ziel.value
            name = None
            if isinstance(basis, ast.Name):
                name = basis.id
            elif isinstance(basis, ast.Attribute):
                name = basis.attr
            if name not in KANALNAMEN:
                continue
            gefunden.setdefault(ziel.attr, set()).add(
                f"{pfad.relative_to(WURZEL.parent)}:{ziel.lineno}"
            )
    return gefunden


def test_die_naht_ist_nicht_leer():
    """Ein Test, der nichts findet, prueft nichts."""
    aufrufe = _kanalaufrufe()
    assert "sende" in aufrufe
    assert "hole_updates" in aufrufe
    assert len(aufrufe) >= 10, aufrufe


def test_webkanal_kann_jede_benutzte_kanalmethode():
    fehlend = {
        name: sorted(stellen)
        for name, stellen in _kanalaufrufe().items()
        if not callable(getattr(web_kanal.WebKanal, name, None))
    }
    assert not fehlend, (
        "WebKanal fehlen Methoden, die interview_theater/ auf einem Kanal "
        f"ruft: {fehlend}"
    )


def test_signaturen_stimmen_mit_telegram_ueberein():
    """Gleiche Parameternamen in gleicher Reihenfolge.

    Nicht nur gleiche Namen der Methoden: ``sende(chat_id, text)`` und
    ``sende(text, chat_id)`` sind beide aufrufbar und genau einmal richtig.
    Vorgabewerte werden nicht verglichen -- ``hole_updates(offset,
    timeout=25)`` darf im Web einen anderen Vorgabewert haben."""
    for name in _kanalaufrufe():
        original = getattr(telegram.Telegram, name, None)
        if original is None:
            continue   # eine Methode, die es in Telegram nie gab
        erwartet = list(inspect.signature(original).parameters)
        gemessen = list(
            inspect.signature(getattr(web_kanal.WebKanal, name)).parameters
        )
        assert gemessen == erwartet, f"{name}: {gemessen} != {erwartet}"


def test_webkanal_deckt_die_ganze_telegram_flaeche_ab():
    """Auch die Methoden, die HEUTE keinen Aufrufer haben.

    ``aktualisiere_knoepfe`` hat seit dem 06.09.2026 keinen (die
    Fragenauswahl laeuft per Nummer im Text, knoepfe/fragen.py:137-141) --
    der naechste Toggle bringt sie zurueck, und dann soll sie im Web da
    sein."""
    oeffentlich = {
        name for name, _ in inspect.getmembers(
            telegram.Telegram, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    fehlend = {
        name for name in oeffentlich
        if not callable(getattr(web_kanal.WebKanal, name, None))
    }
    assert not fehlend, fehlend


def test_niemand_spricht_selbst_mit_telegram():
    """Kein Modul baut eine eigene HTTP-Verbindung zur Bot-API.

    Gemessen am 30.09.2026: der einzige Treffer im Repo steht in
    ``scripts/chat_leeren_blind.py`` -- ein Handwerkzeug, kein Bot-Pfad."""
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "api.telegram.org" in zeile and p.name != "telegram.py"
    ]
    assert treffer == [], treffer


def test_der_vorname_steht_an_genau_einer_stelle():
    """E8: Web-Nachrichten tragen keinen Absendernamen.

    Das ist eine Eigenschaft des Adapters, solange ``from.first_name`` nur in
    ``telegram.lies_nachricht`` gelesen wird. Kommt eine zweite Stelle dazu,
    muss E8 dort eigens gesichert werden."""
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "first_name" in zeile
    ]
    assert treffer == ["telegram.py:453"], treffer


def test_keine_stelle_leitet_aus_dem_vorzeichen_einer_chat_id_ab():
    """Web-Gruppen haben POSITIVE chat_ids (repo.WEB_CHAT_ID_BASIS), echte
    Telegram-Gruppen negative. Eine Stelle, die daraus etwas ableitet, waere
    fuer Web-Gruppen falsch."""
    import re

    muster = re.compile(r"chat_id\s*[<>]\s*0|abs\(\s*chat_id|-100\d")
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if muster.search(zeile)
    ]
    assert treffer == [], treffer
```

**Hinweis fuer die Ausfuehrung:** `test_der_vorname_steht_an_genau_einer_stelle` nennt die
Zeilennummer 453. Verschiebt sich `telegram.py` durch Aufgabe 3, ist die Erwartung dort
nachzuziehen — der Test soll die **Zahl der Stellen** festhalten, nicht die Zeile. Falls das
zu sproede wirkt: auf `len(treffer) == 1 and treffer[0].startswith("telegram.py:")` lockern.

- [x] **Schritt 2: Den Verhaltenstest schreiben**

`tests/test_web_kanal.py`:

```python
"""WebKanal gegen die Tabelle -- ohne Netz, ohne Browser, ohne Bot.

Gemessen wird, dass die zwoelf Methoden genau das in web_post schreiben, was
die Chatansicht spaeter liest, und dass hole_updates Telegram-foermige Updates
liefert, die telegram.lies_nachricht/lies_knopfdruck deuten koennen -- die
Bedingung dafuer, dass bot.schleife unveraendert bleibt.
"""

import threading
import time

import pytest

from interview_theater import db, repo, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    return verbindung


@pytest.fixture
def kanal(conn, tmp_path):
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)


def test_sende_legt_eine_ausgehende_zeile_an(conn, kanal):
    message_id = kanal.sende(CHAT, "Hallo, ich bin der Theaterbot.")
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["richtung"] == repo.RICHTUNG_AUS
    assert zeile["typ"] == repo.WEB_TYP_TEXT
    assert zeile["text"] == "Hallo, ich bin der Theaterbot."
    assert repo.web_knoepfe(zeile) == []


def test_sende_teilt_nicht_bei_4000_zeichen(conn, kanal):
    """Telegram teilt bei NACHRICHT_GRENZE -- der Browser braucht das nicht.

    Eine Nachricht bleibt eine Zeile: sonst haengt die Knopfleiste am letzten
    Stueck, und der Verlauf zerfaellt in Haeppchen, die niemand zuordnen kann."""
    lang = "A" * 9000
    message_id = kanal.sende(CHAT, lang)
    assert repo.hole_web_post(conn, message_id)["text"] == lang
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 1


def test_sende_nimmt_den_klartext_wenn_es_einen_gibt(conn, kanal):
    """``parse_mode='HTML'`` plus ``klartext`` gehoeren in Telegram zusammen:
    der zweite ist der Rueckfall bei HTTP 400. Im Web gibt es kein 400, aber
    die Chatansicht filtert HTML ohnehin (Entscheidung F) -- gespeichert wird
    die HTML-Fassung, weil sie mehr Information traegt."""
    message_id = kanal.sende(
        CHAT, "1. <b>Ankommen</b> — am Bahnhof", parse_mode="HTML",
        klartext="1. Ankommen — am Bahnhof",
    )
    assert repo.hole_web_post(conn, message_id)["text"] == (
        "1. <b>Ankommen</b> — am Bahnhof"
    )


def test_sende_mit_knoepfen_haelt_die_leiste_fest(conn, kanal):
    leiste = [("Ja, speichern", "k:1"), ("Nein, nochmal ändern", "k:2")]
    message_id = kanal.sende_mit_knoepfen(CHAT, "Speichern?", leiste)
    zeile = repo.hole_web_post(conn, message_id)
    assert repo.web_knoepfe(zeile) == [["Ja, speichern", "k:1"],
                                       ["Nein, nochmal ändern", "k:2"]]


def test_sende_mit_knoepfen_prueft_die_64_byte_grenze(kanal):
    """Dieselbe Pruefung wie in Telegram, und aus demselben Grund: Zusage 1
    sagt, dass ein Knopf nur ``k:<id>`` traegt. Im Web gibt es die
    Byte-Grenze technisch nicht -- sie faellt weg zu lassen hiesse, dass ein
    Fehler gegen Zusage 1 erst im Telegram-Betrieb auffaellt."""
    with pytest.raises(ValueError):
        kanal.sende_mit_knoepfen(CHAT, "x", [("A", "k:" + "9" * 70)])


def test_aendere_text_und_entferne_knoepfe(conn, kanal):
    message_id = kanal.sende_mit_knoepfen(CHAT, "alt", [("A", "k:1")])
    kanal.aendere_text(CHAT, message_id, "neu")
    kanal.entferne_knoepfe(CHAT, message_id)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["text"] == "neu"
    assert repo.web_knoepfe(zeile) == []


def test_aktualisiere_knoepfe_tauscht_die_leiste(conn, kanal):
    message_id = kanal.sende_mit_knoepfen(CHAT, "x", [("A", "k:1")])
    kanal.aktualisiere_knoepfe(CHAT, message_id, [("✓ A", "k:1"), ("B", "k:2")])
    assert repo.web_knoepfe(repo.hole_web_post(conn, message_id)) == [
        ["✓ A", "k:1"], ["B", "k:2"],
    ]


def test_loesche_nachrichten_liefert_die_zahl(conn, kanal):
    erste = kanal.sende(CHAT, "a")
    zweite = kanal.sende(CHAT, "b")
    assert kanal.loesche_nachrichten(CHAT, [erste, zweite]) == 2
    assert kanal.loesche_nachrichten(CHAT, []) == 0


def test_tippt_schreibt_keine_nachricht(conn, kanal):
    kanal.tippt(CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0
    assert repo.hole_gruppe(conn, CHAT)["web_tippt_bis"] is not None


def test_setze_befehle_tut_nichts_und_faellt_nicht_um(conn, kanal):
    """Im Web gibt es kein Slash-Menue -- und Slash-Befehle werden nicht
    beworben (AGENTS.md). Die Methode existiert, damit ``bot.main``
    unveraendert bleibt."""
    kanal.setze_befehle([{"command": "stand", "description": "Stand zeigen"}])
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_beantworte_knopf_schreibt_die_antwort_an_den_druck(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF, daten="k:9",
        bezug_message_id=5,
    )
    kanal.beantworte_knopf(f"w{post_id}", "Begriffe uebernommen")
    assert repo.hole_web_post(conn, post_id)["antwort"] == "Begriffe uebernommen"


def test_beantworte_knopf_vertraegt_eine_unbekannte_kennung(kanal):
    """``knoepfe.wirkung._beantworte`` schluckt Fehler, aber eine Attrappe
    soll gar keinen werfen: Telegram antwortet auf einen alten Druck mit 400,
    und das ist kein Fehler des Bots."""
    kanal.beantworte_knopf("voellig-anders", "x")
    kanal.beantworte_knopf("w999999", "x")


def test_hole_updates_liefert_eine_textnachricht_die_lies_nachricht_deutet(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
        text="Unsere Begriffe: Ankommen, Arbeit, Nacht",
    )
    updates = kanal.hole_updates(0, timeout=0)
    assert [u["update_id"] for u in updates] == [post_id]

    gedeutet = telegram.lies_nachricht(updates[0])
    assert gedeutet["chat_id"] == CHAT
    assert gedeutet["message_id"] == post_id
    assert gedeutet["typ"] == "text"
    assert gedeutet["text"] == "Unsere Begriffe: Ankommen, Arbeit, Nacht"
    # E8: kein Vorname. "Gruppe" ist ein Rollenwort, kein Name -- und
    # kontext.sprecherzeile braucht EIN Wort, sonst steht "None:" im Prompt.
    assert gedeutet["absender"] == web_kanal.ABSENDER


def test_hole_updates_traegt_den_gruppentitel_mit(conn, kanal):
    """``bot.verarbeite_update`` reicht ``chat_titel`` an
    ``repo.sichere_gruppe`` weiter, und das ``ON CONFLICT DO UPDATE SET titel``
    wuerde einen Titel, der nicht mitkommt, bei JEDER Nachricht auf NULL
    setzen. Der Titel der Web-Gruppe steht in der Datenbank -- also von dort."""
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="x")
    updates = kanal.hole_updates(0, timeout=0)
    assert telegram.lies_nachricht(updates[0])["chat_titel"] == "Web-Gruppe"


def test_hole_updates_liefert_einen_knopfdruck_den_lies_knopfdruck_deutet(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF, daten="k:42",
        bezug_message_id=7,
    )
    updates = kanal.hole_updates(0, timeout=0)
    assert telegram.lies_nachricht(updates[0]) is None

    druck = telegram.lies_knopfdruck(updates[0])
    assert druck == {
        "callback_query_id": f"w{post_id}",
        "data": "k:42",
        "chat_id": CHAT,
        "chat_titel": "Web-Gruppe",
        "message_id": 7,
    }


def test_hole_updates_liefert_eine_sprachnachricht(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        dauer=44, datei="7000000000001/web-eingang/1.webm", mime="audio/webm",
    )
    gedeutet = telegram.lies_nachricht(kanal.hole_updates(0, timeout=0)[0])
    assert gedeutet["typ"] == "sprache"
    assert gedeutet["dauer"] == 44
    assert gedeutet["file_id"] == web_kanal.datei_verweis(post_id, ".webm")


def test_hole_updates_uebergeht_ausgehende_posts(conn, kanal):
    kanal.sende(CHAT, "Bot spricht")
    assert kanal.hole_updates(0, timeout=0) == []


def test_hole_updates_wartet_bis_zum_timeout_und_kommt_dann_leer(kanal):
    """Der Long-Poll-Ersatz: ``bot.schleife`` ruft ``hole_updates(offset)``
    in einer engen Schleife. Ohne Wartezeit drehte sie mit hundert Prozent
    CPU-Last leer."""
    begonnen = time.monotonic()
    assert kanal.hole_updates(0, timeout=1) == []
    assert 0.5 <= time.monotonic() - begonnen < 3.0


def test_hole_updates_kommt_zurueck_sobald_etwas_eintrifft(conn, kanal):
    def spaeter():
        time.sleep(0.2)
        repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="da")

    threading.Thread(target=spaeter, daemon=True).start()
    begonnen = time.monotonic()
    updates = kanal.hole_updates(0, timeout=10)
    assert len(updates) == 1
    assert time.monotonic() - begonnen < 5.0
```

- [x] **Schritt 3: Beide Laeufe muessen scheitern**

```
$PY -m pytest tests/test_web_kanal.py tests/test_web_kanal_naht.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.web_kanal'` (Collection-Fehler in beiden Dateien).

- [x] **Schritt 4: `interview_theater/web_kanal.py` schreiben**

```python
"""Der Web-Kanal: derselbe Bot, nur ohne Telegram (30.09.2026, Karte Padua A2).

**Die Idee in einem Satz:** der Webserver ist fuer den Bot das, was Telegrams
Server heute ist -- er nimmt Browser-Ereignisse an und legt sie als
Telegram-foermige Updates in eine Tabelle; diese Klasse liest sie und schreibt
die Antworten dorthin zurueck.

Damit bleibt ``bot.schleife`` unveraendert, und ``knoepfe/`` (rund 4.500
Zeilen) wird nicht angefasst: der Weg vom Knopfdruck zur Wirkung ist derselbe
wie in Telegram, bis hinunter zu ``repo.beanspruche_knopf``.

**Warum das traegt, ist gemessen und nicht geraten.** ``simulation/attrappe.py``
ersetzt ``telegram.Telegram`` seit dem 06.09.2026 mit neun Methoden und faehrt
damit einen ganzen Workshop durch (``simulation/lauf.py``). Was hier
zusaetzlich dazukommt, ist genau eine Methode, die die Simulation nicht
braucht: ``hole_updates`` -- sie ruft ``bot.verarbeite_update`` direkt.
``tests/test_web_kanal_naht.py`` haelt die Flaeche am Quelltext fest.

**Kein SQL hier.** Alles geht ueber ``repo`` -- dieselbe Schicht, dieselbe
``RLock``-Serialisierung (Falle 6), derselbe Loeschweg. Und **kein Modell**:
diese Klasse importiert weder ``llm`` noch ``stt``.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_theater import repo
from interview_theater.telegram import CALLBACK_DATA_GRENZE

log = logging.getLogger(__name__)

#: Was in ``nachricht.absender`` steht, wenn eine Gruppe im Browser schreibt.
#:
#: E8 (Birk): Web-Nachrichten tragen **keinen Vornamen**. Sie tragen aber
#: irgendein Wort, denn ``kontext.sprecherzeile`` baut
#: ``f"{sprecher}: {text}"`` und schriebe bei ``None`` woertlich ``"None:"``
#: in jeden Gespraechs-Prompt. "Gruppe" ist ein Rollenwort und kein Name --
#: und es ist ehrlich: im Browser gibt es keine Absenderin, es gibt die
#: Gruppe an einem Telefon.
ABSENDER = "Gruppe"

#: Wie lange eine Tippanzeige gilt. ``arbeitszeilen.TIPP_S`` ist 4,0 s --
#: acht Sekunden ueberbruecken einen ausgefallenen Takt, ohne die Anzeige
#: nach dem Ende eines Laufs minutenlang stehen zu lassen.
TIPPT_GUELTIG_S = 8

#: In welchen Schritten ``hole_updates`` die Tabelle abfragt, solange sie
#: leer ist. 0,25 s ist unter der Wahrnehmungsschwelle und kostet bei drei
#: Gruppen zwoelf Abfragen je Sekunde auf eine WAL-Datei im Dateisystem --
#: das ist billiger als jede Signalisierung, die wir selbst bauen muessten.
POLL_SCHRITT_S = 0.25

#: Praefix der ``file_id`` einer im Browser aufgenommenen Datei.
_VERWEIS = "web:"


def datei_verweis(post_id: int, endung: str) -> str:
    """Die ``file_id`` einer hochgeladenen Aufnahme: ``"web:<id><endung>"``.

    Die **Endung wandert mit**, und das ist Falle 3: ``stt.mime_typ()``
    leitet den MIME-Typ aus der Dateiendung ab, und ein fest verdrahtetes
    ``audio/ogg`` fuer eine WebM-Datei wird von Infomaniak mit einer
    ``batch_id`` quittiert und bleibt dann dauerhaft ``pending`` -- im
    Betrieb nur als "haengt" sichtbar (89,7 s statt 2,0 s)."""
    return f"{_VERWEIS}{post_id}{endung}"


def lies_verweis(file_id: str) -> tuple[int, str] | None:
    """``"web:12.webm"`` -> ``(12, ".webm")``; None bei allem anderen.

    Tolerant wie ``knoepfe._id_aus_daten``: ein Verweis aus einer aelteren
    Fassung darf die Aufnahme-Pipeline nicht zum Absturz bringen."""
    if not isinstance(file_id, str) or not file_id.startswith(_VERWEIS):
        return None
    rest = file_id[len(_VERWEIS):]
    pfad = Path(rest)
    if not pfad.stem.isdigit():
        return None
    return int(pfad.stem), pfad.suffix


def _pruefe_daten(knoepfe) -> None:
    """Die 64-Byte-Grenze, obwohl sie im Web technisch nicht gilt.

    Zusage 1 (AGENTS.md) sagt, dass ein Knopf nur ``k:<id>`` traegt und der
    Wert in der Tabelle ``knopf`` steht. Die Pruefung hier weglassen hiesse,
    dass ein Verstoss dagegen erst im Telegram-Betrieb auffaellt -- also
    beim naechsten Workshop mit Telegram, nicht im Test."""
    for _, daten in knoepfe:
        if len(daten.encode("utf-8")) > CALLBACK_DATA_GRENZE:
            raise ValueError(f"callback_data zu lang: {len(daten)} Zeichen")


class WebKanal:
    """Ersetzt ``telegram.Telegram`` im Web-Kanal (``IT_KANAL=web``).

    Ein Prozess bedient genau EINE Gruppe -- ``chat_id`` im Konstruktor ist
    die, deren Eingang ``hole_updates`` liest. Die uebrigen Methoden nehmen
    ``chat_id`` als Parameter, damit die Signaturen denen von ``Telegram``
    gleichen; sie schreiben in die Gruppe, die ihnen genannt wird."""

    def __init__(self, conn, chat_id: int, audio_verz: str,
                 schritt_s: float = POLL_SCHRITT_S):
        self._conn = conn
        self._chat_id = int(chat_id)
        self._audio = Path(audio_verz)
        self._schritt = schritt_s

    # -- Eingang -----------------------------------------------------------

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        """Der Long-Poll-Ersatz: liest ``web_post`` ab ``offset``, wartet in
        Schritten von ``POLL_SCHRITT_S`` bis ``timeout``, und liefert
        Telegram-foermige Updates.

        ``timeout=0`` fragt genau einmal (die Form, die Tests brauchen).

        Gewartet wird **zwischen** den Abfragen und nie mit einer gehaltenen
        Sperre: jeder ``repo``-Aufruf nimmt den modulweiten ``RLock`` und
        gibt ihn wieder her, sonst haenge der Webserver an unserem Schlaf."""
        frist = time.monotonic() + max(0.0, float(timeout))
        while True:
            zeilen = repo.web_eingang(self._conn, self._chat_id, max(0, int(offset)))
            if zeilen:
                titel = self._titel()
                return [self._update(zeile, titel) for zeile in zeilen]
            if time.monotonic() >= frist:
                return []
            time.sleep(min(self._schritt, max(0.0, frist - time.monotonic())))

    def _titel(self) -> str | None:
        """Der Gruppentitel aus der Datenbank.

        Er MUSS mitkommen: ``bot.verarbeite_update`` reicht ``chat_titel`` an
        ``repo.sichere_gruppe`` weiter, und dessen
        ``ON CONFLICT DO UPDATE SET titel = excluded.titel`` setzte den Titel
        sonst bei jeder Nachricht auf NULL."""
        gruppe = repo.hole_gruppe(self._conn, self._chat_id)
        return gruppe["titel"] if gruppe is not None else None

    def _update(self, zeile, titel: str | None) -> dict:
        """Eine ``web_post``-Zeile als Telegram-Update.

        Zwei Formen, genau die zwei, die ``bot.schleife`` kennt: ein
        ``callback_query`` fuer einen Knopfdruck (``telegram.lies_knopfdruck``)
        und eine ``message`` fuer alles andere (``telegram.lies_nachricht``).
        Ein Knopfdruck ist keine Nachricht und darf nie in ``nachricht``
        landen -- sonst liest ihn der Erkenner als Gruppenbeitrag (AGENTS.md,
        die Weiche in ``bot.schleife``)."""
        post_id = int(zeile["id"])
        chat = {"id": int(zeile["chat_id"]), "type": "group"}
        if titel:
            chat["title"] = titel

        if zeile["typ"] == repo.WEB_TYP_KNOPF:
            knopf = {
                "id": f"w{post_id}",
                "data": zeile["daten"] or "",
                "message": {"message_id": zeile["bezug_message_id"], "chat": chat},
            }
            return {"update_id": post_id, "callback_query": knopf}

        nachricht = {
            "message_id": post_id,
            "chat": chat,
            "from": {"first_name": ABSENDER},
            "date": self._unix(zeile["erstellt_am"]),
        }
        if zeile["typ"] == repo.WEB_TYP_SPRACHE:
            endung = Path(zeile["datei"] or "").suffix or ".ogg"
            nachricht["voice"] = {
                "file_id": datei_verweis(post_id, endung),
                "duration": zeile["dauer"],
                "mime_type": zeile["mime"],
                # Additiver Schluessel, den telegram.lies_nachricht mitnimmt
                # (Aufgabe 3): aufnahme.empfange braucht die Endung fuer den
                # Zielpfad, weil stt.mime_typ() daraus den MIME-Typ ableitet.
                "endung": endung,
            }
        else:
            nachricht["text"] = zeile["text"] or ""
        return {"update_id": post_id, "message": nachricht}

    @staticmethod
    def _unix(iso: str | None) -> int:
        """ISO 8601 -> Unix-Sekunden. ``telegram.lies_nachricht`` rechnet mit
        ``_iso()`` zurueck; ueber diesen Umweg bleibt die Zeitzone erhalten,
        ohne dass das Update-Format von Telegram abweicht."""
        if not iso:
            return int(datetime.now(timezone.utc).timestamp())
        try:
            return int(datetime.fromisoformat(iso).timestamp())
        except ValueError:
            return int(datetime.now(timezone.utc).timestamp())

    # -- Ausgang -----------------------------------------------------------

    def sende(self, chat_id: int, text: str, parse_mode=None, klartext=None) -> int:
        """Eine Textnachricht. Liefert die ``message_id``.

        **Nicht geteilt**, anders als in Telegram (``teile_text``, 4000
        Zeichen): der Browser hat keine Laengengrenze, und ein Text, der in
        vier Zeilen zerfaellt, macht aus einer Bot-Antwort vier Blasen, unter
        deren letzter dann die Knoepfe haengen.

        ``klartext`` wird verworfen: er ist der Telegram-Rueckfall fuer
        HTTP 400, den es hier nicht gibt. Gespeichert wird die
        HTML-Fassung -- sie traegt mehr Information, und die Chatansicht
        filtert sie ohnehin serverseitig (Aufgabe 6)."""
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text=text,
        )

    def sende_mit_knoepfen(self, chat_id: int, text: str, knoepfe,
                           parse_mode=None, klartext=None) -> int:
        """Wie ``sende``, mit einer Leiste darunter -- je Eintrag
        ``(beschriftung, callback_data)``.

        Die Leiste steht in derselben Zeile wie der Text, und **hier** ist
        deshalb die Wahrheit darueber, was unter einer Nachricht gerade
        haengt. ``web_chat`` prueft einen Knopfdruck dagegen (Aufgabe 8) und
        nicht gegen ``knopf.message_id``: die ist nur gesetzt, wenn ein
        Aufrufer ``repo.merke_knopf_nachricht`` ruft, und das tun 22 von 47
        Sendestellen (``knoepfe.biete_einstieg`` zum Beispiel nicht)."""
        leiste = list(knoepfe)
        _pruefe_daten(leiste)
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
            text=text, knoepfe=leiste,
        )

    def sende_datei(self, chat_id: int, dateiname: str, inhalt, beschreibung: str = "") -> int:
        """Wird in Aufgabe 3 ausgefuellt."""
        raise NotImplementedError("Aufgabe 3")

    def beantworte_knopf(self, callback_query_id: str, text: str = "") -> None:
        """Das Gegenstueck zu ``answerCallbackQuery``: der Text wird an den
        Druck geschrieben, und der Browser holt ihn beim naechsten
        Zustands-Poll ab.

        Die Kennung ist ``"w<post_id>"`` (siehe ``_update``) -- es braucht
        keine eigene Spalte, um von ihr auf die Zeile zu kommen. Eine
        unbekannte Kennung ist kein Fehler: in Telegram antwortet die API auf
        einen alten Druck mit 400, und ``knoepfe.wirkung._beantworte``
        schluckt das."""
        if not isinstance(callback_query_id, str) or not callback_query_id.startswith("w"):
            return
        rest = callback_query_id[1:]
        if not rest.isdigit():
            return
        repo.setze_web_antwort(self._conn, int(rest), text)

    def aendere_text(self, chat_id: int, message_id: int, text: str) -> None:
        """``editMessageText`` -- die wechselnden Arbeitszeilen
        (``arbeitszeilen.py``). Ein Fehlschlag ist unkritisch und wird vom
        Aufrufer geschluckt, deshalb kein Rueckgabewert."""
        repo.aendere_web_text(self._conn, chat_id, message_id, text)

    def entferne_knoepfe(self, chat_id: int, message_id: int) -> None:
        """Nimmt die Leiste weg, nachdem ein Knopf gewirkt hat."""
        repo.setze_web_knoepfe(self._conn, chat_id, message_id, None)

    def aktualisiere_knoepfe(self, chat_id: int, message_id: int, knoepfe) -> None:
        """Tauscht die Leiste aus.

        Hat in ``interview_theater/`` seit dem 06.09.2026 keinen Aufrufer
        (die Fragenauswahl laeuft per Nummer im Text, ``knoepfe/fragen.py``)
        -- sie steht hier, weil die Flaeche vollstaendig sein soll und der
        naechste Toggle sie zurueckbringt."""
        leiste = list(knoepfe)
        _pruefe_daten(leiste)
        repo.setze_web_knoepfe(self._conn, chat_id, message_id, leiste)

    def loesche_nachrichten(self, chat_id: int, message_ids: list) -> int:
        """Nimmt bis zu 100 Nachrichten aus der Ansicht -- weich, mit
        ``geloescht_am``. Liefert die Zahl der uebergebenen ids, wie
        ``Telegram.loesche_nachrichten`` (der Aufrufer zaehlt keinen Erfolg
        je id)."""
        if not message_ids:
            return 0
        repo.loesche_web_posts(self._conn, chat_id, list(message_ids))
        return len(list(message_ids)[:100])

    def setze_befehle(self, befehle: list) -> None:
        """No-Op: im Browser gibt es kein Slash-Menue, und Slash-Befehle
        werden nicht beworben (AGENTS.md) -- beworben wird der Knopf. Die
        Methode existiert, damit ``bot.main`` unveraendert bleibt."""
        log.debug("setze_befehle im Web-Kanal ohne Wirkung (%s Befehle)", len(befehle))

    def tippt(self, chat_id: int) -> None:
        """Die Tippanzeige, als Zeitpunkt in ``gruppe.web_tippt_bis``.

        **Keine Zeile in ``web_post``:** ``arbeitszeilen.TIPP_S`` ist 4,0 s,
        ein vierminuetiger Szenenlauf gaebe 60 Zeilen, die je eine
        ``message_id`` aus der gemeinsamen Folge verbrauchen -- und eine
        Tippanzeige ist keine Nachricht."""
        bis = datetime.now(timezone.utc) + timedelta(seconds=TIPPT_GUELTIG_S)
        repo.setze_web_tippt(self._conn, chat_id, bis.isoformat(timespec="seconds"))

    def lade_datei(self, file_id: str, ziel) -> None:
        """Wird in Aufgabe 3 ausgefuellt."""
        raise NotImplementedError("Aufgabe 3")
```

`json` ist im Kopf aufgefuehrt, aber hier noch nicht gebraucht — entweder Zeile weglassen
oder (empfohlen) erst in Aufgabe 3 aufnehmen, damit `ruff`/Lint nicht meckert.

- [x] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_kanal.py tests/test_web_kanal_naht.py -q -p no:cacheprovider
```
Erwartet: `26 passed` (19 Verhalten + 7 Naht). Weicht die Zahl ab, zaehlen — nicht schaetzen.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2809 passed, 1 skipped`.

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/web_kanal.py tests/test_web_kanal.py tests/test_web_kanal_naht.py
git commit -m "Web-Kanal: WebKanal statt Telegram, Naht per AST festgehalten

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 3: Audio durch die Naht — `lade_datei`, `sende_datei`, die Endung

**Dateien:**
- Aendern: `interview_theater/telegram.py` (**eine** Zeile im Rueckgabe-Dict von `lies_nachricht`)
- Aendern: `interview_theater/aufnahme.py` (**eine** Zeile: 385, plus eine Konstante)
- Aendern: `interview_theater/web_kanal.py` (`sende_datei`, `lade_datei`, Verzeichniskonstanten)
- Test: `tests/test_web_kanal_audio.py` (neu)

**Warum das die kritische Stelle ist.** `aufnahme.py:385` verdrahtet die Endung fest:

```python
ziel = Path(e.audio_verz) / str(chat_id) / f"{message_id}.ogg"
```

`stt.mime_typ()` leitet den MIME-Typ aus **der Endung** ab (Falle 3), und ein WebM, das als
`.ogg` abgelegt wird, bekommt `audio/ogg` — was Infomaniak mit einer `batch_id` quittiert und
dann dauerhaft auf `pending` stehen laesst: 89,7 s statt 2,0 s, im Betrieb nur als „haengt"
sichtbar. `stt._MIME_TYPEN` kennt `.webm`, `.m4a`, `.mp4` und `.mp3` **schon** — es fehlt
allein der Weg, wie die Endung dorthin kommt.

**Schnittstellen — Produziert:**

```python
# interview_theater/telegram.py -- lies_nachricht liefert einen Schluessel mehr
{"...": ..., "endung": str | None}

# interview_theater/aufnahme.py
ENDUNG_VORGABE = ".ogg"

# interview_theater/web_kanal.py
EINGANG_VERZ = "web-eingang"
AUSGANG_VERZ = "web-ausgang"
def eingangspfad(audio_verz: str, chat_id: int, post_id: int, endung: str) -> Path
```

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_kanal_audio.py`:

```python
"""Audio durch die Naht -- und die Endung, an der Falle 3 haengt.

Der gemessene Fall (04.09.2026): ein fest verdrahtetes ``audio/ogg`` fuer eine
WAV-Datei wird vom Anbieter mit einer batch_id quittiert -- kein HTTP-Fehler,
keine Ablehnung -- und der Auftrag bleibt danach dauerhaft auf 'pending':
89,7 s statt 2,0 s, im Betrieb nur als "haengt" sichtbar.

Daraus folgt: die Endung der im Browser aufgenommenen Datei muss bis in
``aufnahme.empfange`` durchkommen, denn dort entsteht der Zielpfad, und
``stt.mime_typ()`` liest nur ihn.
"""

from pathlib import Path

import pytest

from interview_theater import aufnahme, db, repo, stt, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    return verbindung


@pytest.fixture
def kanal(conn, tmp_path):
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)


# -- die additive Erweiterung bleibt bitgleich fuer Telegram ----------------


def test_telegram_sprachnachricht_hat_keine_endung():
    """Bitgleich: ein echtes Telegram-Update traegt kein 'endung', also
    bleibt der Zielpfad ``.ogg`` wie bisher."""
    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": -100123, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "date": 1_790_000_000,
            "voice": {"file_id": "AwACAgI", "duration": 44},
        },
    }
    gedeutet = telegram.lies_nachricht(update)
    assert gedeutet["endung"] is None
    assert gedeutet["file_id"] == "AwACAgI"
    assert gedeutet["dauer"] == 44


def test_telegram_textnachricht_hat_auch_keine_endung():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 11,
            "chat": {"id": -100123},
            "date": 1_790_000_000,
            "text": "Hallo",
        },
    }
    assert telegram.lies_nachricht(update)["endung"] is None


def test_die_schluesselmenge_waechst_um_genau_einen_eintrag():
    """``lies_nachricht`` ist eine feste Schluesselmenge, mit der der ganze
    Bot arbeitet. Waechst sie, soll man es hier sehen."""
    update = {"update_id": 1, "message": {"message_id": 1,
                                          "chat": {"id": 1}, "date": 1, "text": "x"}}
    assert set(telegram.lies_nachricht(update)) == {
        "chat_id", "chat_titel", "message_id", "absender", "typ", "text",
        "file_id", "dauer", "gesendet_am", "endung",
    }


def test_empfange_legt_ohne_endung_weiter_eine_ogg_datei_ab(conn, tmp_path):
    """Der Telegram-Pfad, unveraendert."""

    class TgAttrappe:
        def lade_datei(self, file_id, ziel):
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"OggS")

        def sende(self, chat_id, text, **kw):
            return 1

    class E:
        audio_verz = str(tmp_path / "audio")
        bot_name = "gruppe1"

    nachricht = {
        "chat_id": CHAT, "message_id": 10, "absender": "Ada", "typ": "sprache",
        "text": None, "file_id": "F1", "dauer": 5,
        "gesendet_am": "2026-09-30T10:00:00+00:00", "endung": None,
    }
    aufnahme_id = aufnahme.empfange(conn, TgAttrappe(), E(), nachricht)
    pfad = Path(repo.hole_aufnahme(conn, aufnahme_id)["audio_pfad"])
    assert pfad.suffix == ".ogg"
    assert stt.mime_typ(pfad) == "audio/ogg"


def test_empfange_nimmt_die_endung_aus_der_nachricht(conn, tmp_path):
    """Der Web-Pfad: eine WebM-Datei bekommt einen WebM-Pfad -- und damit den
    richtigen MIME-Typ (Falle 3)."""

    class TgAttrappe:
        def lade_datei(self, file_id, ziel):
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"\x1a\x45\xdf\xa3")   # EBML-Kopf

        def sende(self, chat_id, text, **kw):
            return 1

    class E:
        audio_verz = str(tmp_path / "audio")
        bot_name = "gruppe1"

    nachricht = {
        "chat_id": CHAT, "message_id": 11, "absender": web_kanal.ABSENDER,
        "typ": "sprache", "text": None, "file_id": "web:11.webm", "dauer": 45,
        "gesendet_am": "2026-09-30T10:00:00+00:00", "endung": ".webm",
    }
    aufnahme_id = aufnahme.empfange(conn, TgAttrappe(), E(), nachricht)
    pfad = Path(repo.hole_aufnahme(conn, aufnahme_id)["audio_pfad"])
    assert pfad.suffix == ".webm"
    assert stt.mime_typ(pfad) == "audio/webm"


# -- die Verweise ----------------------------------------------------------


@pytest.mark.parametrize("endung", [".webm", ".ogg", ".m4a", ".mp3"])
def test_verweis_hin_und_zurueck(endung):
    verweis = web_kanal.datei_verweis(42, endung)
    assert web_kanal.lies_verweis(verweis) == (42, endung)


@pytest.mark.parametrize("kaputt", ["", "AwACAgI", "web:", "web:abc.webm", None, 7])
def test_lies_verweis_ist_tolerant(kaputt):
    assert web_kanal.lies_verweis(kaputt) is None


# -- lade_datei ------------------------------------------------------------


def test_lade_datei_kopiert_die_hochgeladene_aufnahme(conn, kanal, tmp_path):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        dauer=45, mime="audio/webm",
        datei=str(web_kanal.eingangspfad(str(tmp_path / "audio"), CHAT, 1, ".webm")),
    )
    quelle = Path(repo.hole_web_post(conn, post_id)["datei"])
    quelle.parent.mkdir(parents=True, exist_ok=True)
    quelle.write_bytes(b"\x1a\x45\xdf\xa3segment")

    ziel = tmp_path / "audio" / str(CHAT) / f"{post_id}.webm"
    kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"), ziel)
    assert ziel.read_bytes() == b"\x1a\x45\xdf\xa3segment"


def test_lade_datei_wirft_bei_unbekanntem_verweis(kanal, tmp_path):
    """``aufnahme._lade_mit_wiederholung`` faengt jede Ausnahme und wiederholt
    mit ``stt.WARTEZEITEN``; danach entsteht ein Vorfall und die Gruppe wird
    gebeten, es nochmal zu schicken. Eine Ausnahme ist hier also der richtige
    Ausgang -- stillschweigend eine leere Datei anzulegen waere der falsche:
    daraus wuerde ein Interview mit erfundenem Inhalt."""
    with pytest.raises(Exception):
        kanal.lade_datei("web:999999.webm", tmp_path / "x.webm")


def test_lade_datei_wirft_wenn_die_quelle_fehlt(conn, kanal, tmp_path):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        datei=str(tmp_path / "gibtsnicht.webm"), mime="audio/webm",
    )
    with pytest.raises(Exception):
        kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"),
                         tmp_path / "y.webm")


def test_lade_datei_verlaesst_das_audioverzeichnis_nicht(conn, kanal, tmp_path):
    """Die ``datei``-Spalte wird vom Webserver geschrieben. Ein Pfad, der aus
    dem Audioverzeichnis herausfuehrt, darf nicht kopiert werden -- sonst
    liesse sich ueber einen manipulierten Eintrag jede lesbare Datei des
    Servers in ein Transkript verwandeln."""
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        datei="/etc/passwd", mime="audio/webm",
    )
    with pytest.raises(Exception):
        kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"),
                         tmp_path / "z.webm")


# -- sende_datei -----------------------------------------------------------


def test_sende_datei_legt_die_datei_und_eine_zeile_an(conn, kanal, tmp_path):
    message_id = kanal.sende_datei(
        CHAT, "textbuch.md", "# Unser Stueck\n\nSZENE 1\n", "Das Textbuch",
    )
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["typ"] == repo.WEB_TYP_DATEI
    assert zeile["dateiname"] == "textbuch.md"
    assert zeile["text"] == "Das Textbuch"
    assert Path(zeile["datei"]).read_text(encoding="utf-8").startswith("# Unser Stueck")


def test_sende_datei_nimmt_auch_bytes(conn, kanal):
    message_id = kanal.sende_datei(CHAT, "t.md", b"roh", "")
    assert Path(repo.hole_web_post(conn, message_id)["datei"]).read_bytes() == b"roh"


def test_sende_datei_saeubert_den_dateinamen(conn, kanal):
    """Der Name kommt aus dem Code, aber der Pfad entsteht daraus -- ein
    ``../`` darin schriebe neben das Audioverzeichnis."""
    message_id = kanal.sende_datei(CHAT, "../../etc/passwd", "x", "")
    pfad = Path(repo.hole_web_post(conn, message_id)["datei"]).resolve()
    assert web_kanal.AUSGANG_VERZ in pfad.parts
    assert ".." not in pfad.parts
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_kanal_audio.py -q -p no:cacheprovider
```
Erwartet: FAIL — `KeyError: 'endung'` bzw. `NotImplementedError: Aufgabe 3`.

- [x] **Schritt 3: `telegram.py` — der additive Schluessel**

Im Rueckgabe-Dict von `lies_nachricht` (heute Zeile 449–459) hinter `"dauer"` einfuegen:

```python
        "dauer": _sprachquelle(nachricht).get("duration"),
        # Die Dateiendung, wenn die Quelle eine nennt (30.09.2026, Web-Kanal).
        # Telegram nennt keine -- dort bleibt der Wert None und
        # ``aufnahme.empfange`` legt wie bisher eine ``.ogg`` ab. Der
        # Web-Kanal setzt ihn, weil ``stt.mime_typ()`` den MIME-Typ aus der
        # ENDUNG ableitet (Falle 3): ein WebM als ``.ogg`` abgelegt laesst den
        # Whisper-Auftrag dauerhaft auf 'pending' stehen.
        "endung": _sprachquelle(nachricht).get("endung"),
```

Im Docstring von `lies_nachricht` einen Satz ergaenzen, dass `endung` optional ist und nur
der Web-Kanal sie setzt.

- [x] **Schritt 4: `aufnahme.py` — die Endung des Zielpfads**

Bei den Modulkonstanten (neben `HINWEIS_AB_S`) einfuegen:

```python
#: Endung des Zielpfads einer heruntergeladenen Aufnahme, wenn die Quelle
#: keine nennt. Telegram nennt keine -- der Web-Kanal nennt sie, weil
#: ``stt.mime_typ()`` den MIME-Typ aus der Endung ableitet (Falle 3).
ENDUNG_VORGABE = ".ogg"
```

Zeile 385 ersetzen:

```python
    ziel = (
        Path(e.audio_verz) / str(chat_id)
        / f"{message_id}{n.get('endung') or ENDUNG_VORGABE}"
    )
```

Im Docstring von `empfange` einen Satz ergaenzen:

```
    ``n["endung"]`` (optional) bestimmt die Endung des Zielpfads. Sie ist der
    einzige Weg, auf dem ``stt.mime_typ()`` den richtigen MIME-Typ bekommt
    (Falle 3); ohne sie bleibt es bei ``ENDUNG_VORGABE``, wie im
    Telegram-Betrieb.
```

**Bekannte Grenze, hier nicht behoben** (Uebergabe, siehe Aufgabe 14): auch im
Telegram-Betrieb bekommen `audio`-Nachrichten (m4a, mp3) und Dokumente heute einen
`.ogg`-Pfad. Das ist derselbe Fehler eine Etage weiter und war schon vor dieser Karte da —
`lies_nachricht` koennte die Endung aus `mime_type`/`file_name` ableiten. Nicht Teil dieser
Karte, weil es den Telegram-Pfad aendert (E1).

- [x] **Schritt 5: `web_kanal.py` — die beiden Methoden**

Bei den Modulkonstanten:

```python
#: Wo die im Browser aufgenommenen Segmente landen, bevor
#: ``aufnahme.empfange`` sie an ihren Platz kopiert -- ein Unterverzeichnis
#: je Gruppe unterhalb von ``IT_AUDIO``, damit der Loeschweg
#: (``scripts/loeschen.py`` entfernt das Audioverzeichnis einer Gruppe) sie
#: ohne Zutun mitnimmt.
EINGANG_VERZ = "web-eingang"

#: Wo Dateien liegen, die der Bot verschickt (Textbuch-Export).
AUSGANG_VERZ = "web-ausgang"


def eingangspfad(audio_verz: str, chat_id: int, post_id: int, endung: str) -> Path:
    """Wohin ein hochgeladenes Segment gehoert."""
    return Path(audio_verz) / str(chat_id) / EINGANG_VERZ / f"{post_id}{endung}"
```

Die beiden Methoden:

```python
    def sende_datei(self, chat_id: int, dateiname: str, inhalt, beschreibung: str = "") -> int:
        """Eine Datei (Telegram: ``sendDocument``) -- gebraucht fuer den
        Textbuch-Export in Phase 7.

        Im Browser wird daraus eine Zeile mit einem Herunterladen-Link; die
        Datei liegt unter ``IT_AUDIO/<chat_id>/web-ausgang/`` und wird von
        ``web_chat`` ausgeliefert (Aufgabe 6). Der Name wird gesaeubert: er
        kommt heute aus dem Code, aber aus ihm entsteht ein Pfad."""
        daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
        sauber = Path(str(dateiname)).name or "datei"
        post_id = repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, repo.WEB_TYP_DATEI,
            text=beschreibung or None, dateiname=sauber,
        )
        ziel = self._audio / str(chat_id) / AUSGANG_VERZ / f"{post_id}-{sauber}"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(daten)
        repo.setze_web_datei(self._conn, post_id, str(ziel))
        return post_id

    def lade_datei(self, file_id: str, ziel) -> None:
        """Kopiert ein hochgeladenes Segment an seinen Platz.

        Das Gegenstueck zu ``Telegram.lade_datei`` (getFile + Download). Jede
        Ausnahme ist hier der richtige Ausgang: ``aufnahme._lade_mit_wiederholung``
        faengt sie, wiederholt mit ``stt.WARTEZEITEN`` und meldet danach der
        Gruppe, sie moege es nochmal schicken. Stillschweigend eine leere
        Datei anzulegen waere der falsche -- daraus wuerde ein Interview mit
        erfundenem Inhalt (gemessen 05.09.2026, N2)."""
        gelesen = lies_verweis(file_id)
        if gelesen is None:
            raise ValueError(f"kein Web-Dateiverweis: {file_id!r}")
        post_id, _endung = gelesen
        zeile = repo.hole_web_post(self._conn, post_id)
        if zeile is None or not zeile["datei"]:
            raise FileNotFoundError(f"Web-Aufnahme {post_id} ist nicht hinterlegt")

        wurzel = self._audio.resolve()
        quelle = Path(zeile["datei"]).resolve()
        if not quelle.is_relative_to(wurzel):
            # Die Spalte wird vom Webserver geschrieben. Ein Pfad ausserhalb
            # von IT_AUDIO wuerde jede lesbare Datei des Servers in ein
            # Transkript verwandeln.
            raise ValueError(f"Web-Aufnahme {post_id} liegt ausserhalb von {wurzel}")

        ziel = Path(ziel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(quelle.read_bytes())
```

Dazu in `repo.py` (Aufgabe 1 erweitern, gleiche Stelle):

```python
@_gesperrt
def setze_web_datei(conn, post_id: int, pfad: str) -> None:
    """Haelt fest, wo die Datei zu einer ``web_post``-Zeile liegt. Getrennt
    vom Anlegen, weil der Pfad die id enthaelt: erst die Zeile, dann der
    Name, dann der Verweis."""
    conn.execute("UPDATE web_post SET datei = ? WHERE id = ?", (pfad, post_id))
    conn.commit()
```

`Path.is_relative_to` gibt es seit Python 3.9 — das Projekt laeuft auf 3.11.

- [x] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_kanal_audio.py -q -p no:cacheprovider
```
Erwartet: `19 passed`.

Der Bitgleich-Nachweis fuer Telegram — die bestehenden Audio- und Telegram-Tests:

```
$PY -m pytest tests/test_aufnahme.py tests/test_telegram.py tests/test_stt.py \
  tests/test_interview_ohne_knopf.py -q -p no:cacheprovider
```
Erwartet: alle passed, keine Aenderung gegenueber vorher.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2828 passed, 1 skipped`.

- [x] **Schritt 7: Commit**

```bash
git add interview_theater/telegram.py interview_theater/aufnahme.py \
        interview_theater/web_kanal.py interview_theater/repo.py \
        tests/test_web_kanal_audio.py
git commit -m "Web-Kanal: Audio durch die Naht, Endung bis in den Zielpfad (Falle 3)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 4: `IT_KANAL` und die Kanalweiche in `bot.main`

**Dateien:**
- Aendern: `interview_theater/einstellungen.py`
- Aendern: `interview_theater/bot.py` (**nur** `main`, nicht `schleife`)
- Test: `tests/test_kanal_wahl.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/einstellungen.py
KANAL_TELEGRAM = "telegram"
KANAL_WEB = "web"
# Einstellungen bekommt drei Felder mit Vorgabewerten (ans Ende, damit
# bestehende direkte Konstruktionsaufrufe in Tests weiter gelten):
#   kanal: str = "telegram"
#   web_chat_id: int | None = None
#   web_segment_ms: int = 45000

# interview_theater/bot.py
def baue_kanal(conn, e, klient)    # liefert Telegram oder WebKanal
```

- [x] **Schritt 1: Den Test schreiben**

`tests/test_kanal_wahl.py`:

```python
"""Ohne IT_KANAL bleibt alles, wie es war (E1: Telegram ist Plan B).

Die Weiche steht in bot.main und NICHT in bot.schleife: die Schleife kennt
nur ein Objekt mit hole_updates, und genau das ist die Naht.
"""

import pytest

from interview_theater import bot, einstellungen, db, repo, telegram, web_kanal

PFLICHT = {
    "IT_BOT_NAME": "gruppe1",
    "IT_DB": "/tmp/egal.db",
    "IT_LLM_URL": "https://example.invalid/chat/completions",
    "IT_LLM_KEY": "k",
    "IT_LLM_MODELL": "m",
    "IT_STT_PRODUKT": "p",
}


def _umgebung(monkeypatch, **zusatz):
    for name in list(einstellungen._VORGABEWERTE) + [
        "IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS",
    ]:
        monkeypatch.delenv(name, raising=False)
    for name, wert in {**PFLICHT, **zusatz}.items():
        monkeypatch.setenv(name, wert)


def test_ohne_variable_ist_der_kanal_telegram(monkeypatch):
    _umgebung(monkeypatch, IT_BOT_TOKEN="123:abc")
    e = einstellungen.laden()
    assert e.kanal == einstellungen.KANAL_TELEGRAM
    assert e.bot_token == "123:abc"
    assert e.web_chat_id is None


def test_ohne_variable_bleibt_der_bot_token_pflicht(monkeypatch):
    _umgebung(monkeypatch)   # kein IT_BOT_TOKEN
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_BOT_TOKEN" in str(fehler.value)


def test_im_web_kanal_ist_der_bot_token_keine_pflicht(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="web", IT_WEB_CHAT_ID="7000000000001")
    e = einstellungen.laden()
    assert e.kanal == einstellungen.KANAL_WEB
    assert e.web_chat_id == 7_000_000_000_001
    assert e.bot_token == ""


def test_kanal_wird_normalisiert(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="  WEB  ", IT_WEB_CHAT_ID="7000000000001")
    assert einstellungen.laden().kanal == einstellungen.KANAL_WEB


def test_unbekannter_kanal_bricht_ab(monkeypatch):
    """Ein Tippfehler in einer Env-Datei soll nicht still auf Telegram
    zurueckfallen: dann sucht jemand am Workshopmorgen, warum der Browser
    nichts sieht."""
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a", IT_KANAL="webb")
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_KANAL" in str(fehler.value)


def test_web_kanal_ohne_chat_id_bricht_ab(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="web")
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_WEB_CHAT_ID" in str(fehler.value)


def test_segmentlaenge_hat_einen_vorgabewert(monkeypatch):
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a")
    assert einstellungen.laden().web_segment_ms == 45_000
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a", IT_WEB_SEGMENT_MS="800")
    assert einstellungen.laden().web_segment_ms == 800


def test_baue_kanal_liefert_telegram_ohne_variable(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    e = einstellungen.Einstellungen(
        bot_token="1:a", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
    )
    assert isinstance(bot.baue_kanal(conn, e, klient=None), telegram.Telegram)


def test_baue_kanal_liefert_webkanal_im_web_modus(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_001, "gruppe1", "Web-Gruppe")
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=einstellungen.KANAL_WEB, web_chat_id=7_000_000_000_001,
    )
    kanal = bot.baue_kanal(conn, e, klient=None)
    assert isinstance(kanal, web_kanal.WebKanal)


def test_baue_kanal_verweigert_eine_unbekannte_gruppe(tmp_path):
    """Der Web-Bot-Prozess bedient genau seine IT_WEB_CHAT_ID. Gibt es die
    Gruppe nicht, hat niemand ``scripts/web_gruppe.py`` laufen lassen -- und
    ein Bot, der auf eine leere Gruppe hoert, sieht aus wie einer, der
    haengt."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=einstellungen.KANAL_WEB, web_chat_id=7_000_000_000_999,
    )
    with pytest.raises(RuntimeError) as fehler:
        bot.baue_kanal(conn, e, klient=None)
    assert "web_gruppe" in str(fehler.value)


def test_schleife_ist_nicht_angefasst_worden():
    """Die Naht traegt genau dann, wenn bot.schleife nichts vom Kanal weiss.

    Gemessen: im Quelltext von ``schleife`` steht kein 'telegram' und kein
    'web' -- sie ruft nur ``tg.hole_updates`` und ``telegram.lies_*``."""
    import inspect

    quelle = inspect.getsource(bot.schleife)
    assert "web_kanal" not in quelle
    assert "IT_KANAL" not in quelle
    assert "kanal" not in quelle
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_kanal_wahl.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.einstellungen' has no attribute 'KANAL_TELEGRAM'`.

- [x] **Schritt 3: `einstellungen.py`**

```python
#: Welcher Kanal den Bot bedient (30.09.2026, Karte Padua A2).
#: ``telegram`` ist die Vorgabe, und ohne die Variable ist alles wie vorher
#: (E1: Telegram bleibt Plan B).
KANAL_TELEGRAM = "telegram"
KANAL_WEB = "web"
KANAELE = (KANAL_TELEGRAM, KANAL_WEB)

#: Wie lang ein Aufnahmesegment im Browser ist (Millisekunden). Jedes Segment
#: ist ein eigener MediaRecorder-Lauf und damit eine vollstaendige Datei --
#: eine Zeitscheibe allein ist nicht dekodierbar. 45 s sind der Kompromiss:
#: Netz weg oder Tab zu verliert hoechstens 45 Sekunden, und ein Interview
#: von zehn Minuten kostet dreizehn Uploads statt einem grossen.
#: Der Browsertest setzt die Variable kurz (tests/e2e).
VORGABE_SEGMENT_MS = 45_000
```

Im `_VORGABEWERTE`-Dict:

```python
    "IT_KANAL": KANAL_TELEGRAM,
    # Die eine Gruppe, die ein Web-Bot-Prozess bedient. Pflicht, sobald
    # IT_KANAL=web -- geprueft in laden().
    "IT_WEB_CHAT_ID": "",
    "IT_WEB_SEGMENT_MS": str(VORGABE_SEGMENT_MS),
```

`Einstellungen` bekommt drei Felder **am Ende** (die bestehenden Konstruktionsaufrufe in
Tests kennen sie nicht):

```python
    kanal: str = KANAL_TELEGRAM
    web_chat_id: int | None = None
    web_segment_ms: int = VORGABE_SEGMENT_MS
```

`laden()`:

```python
#: Variablen, die nur der Telegram-Kanal braucht. Im Web-Kanal gibt es keinen
#: Bot-Token -- ihn dort zur Pflicht zu machen hiesse, einen Platzhalter in
#: jede Env-Datei zu schreiben, und ein Platzhalter-Token ist nicht von einem
#: falschen zu unterscheiden.
_NUR_TELEGRAM = ("IT_BOT_TOKEN",)


def laden() -> Einstellungen:
    """Liest die Umgebungsvariablen. Wirft RuntimeError bei fehlender
    Pflichtvariable und bei einem unbekannten ``IT_KANAL``.

    Ein Tippfehller in ``IT_KANAL`` faellt NICHT still auf Telegram zurueck:
    dann sucht am Workshopmorgen jemand, warum der Browser nichts sieht.
    Fehlerbild am Workshoptag ist die teuerste Waehrung (wie beim
    Workshop-Profil, ``bot.main``)."""
    kanal = (os.environ.get("IT_KANAL") or KANAL_TELEGRAM).strip().lower()
    if kanal not in KANAELE:
        raise RuntimeError(
            f"IT_KANAL muss {' oder '.join(KANAELE)} sein, ist: "
            f"{os.environ.get('IT_KANAL')!r}"
        )

    werte = {}
    fehlend = []
    for name, vorgabe in _VORGABEWERTE.items():
        if kanal != KANAL_TELEGRAM and name in _NUR_TELEGRAM:
            vorgabe = ""
        wert = os.environ.get(name, vorgabe)
        if wert is None:
            fehlend.append(name)
        werte[name] = wert
    if fehlend:
        raise RuntimeError(f"Fehlende Umgebungsvariable(n): {', '.join(fehlend)}")

    roh_chat = (werte["IT_WEB_CHAT_ID"] or "").strip()
    if kanal == KANAL_WEB and not roh_chat:
        raise RuntimeError(
            "IT_KANAL=web braucht IT_WEB_CHAT_ID -- die eine Gruppe, die "
            "dieser Prozess bedient. Anlegen mit: "
            "python -m scripts.web_gruppe anlegen <bot_name>"
        )
    try:
        web_chat_id = int(roh_chat) if roh_chat else None
    except ValueError:
        raise RuntimeError(f"IT_WEB_CHAT_ID muss eine Zahl sein, ist: {roh_chat!r}") from None
    try:
        segment_ms = int((werte["IT_WEB_SEGMENT_MS"] or VORGABE_SEGMENT_MS))
    except ValueError:
        raise RuntimeError(
            f"IT_WEB_SEGMENT_MS muss eine Zahl sein, ist: "
            f"{werte['IT_WEB_SEGMENT_MS']!r}"
        ) from None

    return Einstellungen(
        # ... alles Bestehende unveraendert ...
        kanal=kanal,
        web_chat_id=web_chat_id,
        web_segment_ms=segment_ms,
    )
```

- [x] **Schritt 4: `bot.py` — die Weiche in `main`, `schleife` unberuehrt**

Neue Funktion oberhalb von `main`:

```python
def baue_kanal(conn, e: Einstellungen, klient):
    """Der Kanal dieses Prozesses: Telegram (Vorgabe) oder der Web-Kanal.

    **Die eine Stelle, an der der Kanal gewaehlt wird.** ``schleife`` weiss
    nichts davon -- sie ruft ``tg.hole_updates`` und reicht das Objekt weiter,
    und genau das ist die Naht, an der der ganze Web-Arbeitsplatz haengt
    (``tests/test_web_kanal_naht.py``).

    Im Web-Kanal wird die Gruppe vorher geprueft: ein Prozess, der auf eine
    chat_id hoert, die es nicht gibt, laeuft ohne Fehlermeldung und antwortet
    nie -- das sieht aus wie ein haengender Bot, und die Ursache steht
    nirgends."""
    if e.kanal != einstellungen.KANAL_WEB:
        return Telegram(e.bot_token, klient)

    from interview_theater.web_kanal import WebKanal

    if repo.hole_gruppe(conn, e.web_chat_id) is None:
        raise RuntimeError(
            f"IT_WEB_CHAT_ID={e.web_chat_id} kennt die Datenbank nicht. "
            f"Anlegen mit: python -m scripts.web_gruppe anlegen {e.bot_name}"
        )
    log.info("Kanal: Web (chat_id=%s)", e.web_chat_id)
    return WebKanal(conn, e.web_chat_id, e.audio_verz)
```

In `main` die Zeile `tg = Telegram(e.bot_token, klient)` ersetzen durch:

```python
    tg = baue_kanal(conn, e, klient)
```

Sonst nichts. `setze_befehle`, `warmlaufen`, `sende_wiederkehr_begruessungen`, der
Nachhol-Thread und `schleife(conn, e, tg, klm, klient, pool)` bleiben Zeichen fuer Zeichen
stehen — `WebKanal.setze_befehle` ist ein No-Op, und `sende_wiederkehr_begruessungen`
ueberspringt eine Gruppe ohne Nachrichten von selbst (`repo.letzte_nachricht_zeit` gibt
`None`).

- [x] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_kanal_wahl.py -q -p no:cacheprovider
```
Erwartet: `12 passed`.

```
$PY -m pytest tests/test_einstellungen.py tests/test_bot.py -q -p no:cacheprovider
```
Erwartet: alle passed (Bitgleich-Nachweis).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2840 passed, 1 skipped`.

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/einstellungen.py interview_theater/bot.py tests/test_kanal_wahl.py
git commit -m "Web-Kanal: IT_KANAL waehlt den Kanal in bot.main, schleife bleibt unberuehrt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 5: `scripts/web_gruppe.py`

**Dateien:**
- Neu: `scripts/web_gruppe.py`
- Test: `tests/test_web_gruppe_skript.py` (neu)

**Schnittstellen — Produziert:**

```python
# scripts/web_gruppe.py
def lege_an(conn, bot_name: str, titel: str, basis_url: str) -> dict
    # -> {"chat_id": int, "token": str, "url": str | None, "env": list[str]}
def bericht(daten: dict) -> str
def main(argv: list[str] | None = None) -> int
```

Aufruf: `$PY -m scripts.web_gruppe anlegen <bot_name> [--titel "Gruppe A"]`. Liest `IT_DB`
(Pflicht) und `IT_WEB_URL` (optional, fuer den Link). **Liest keine Datei unter `betrieb/`**
und gibt keinen Bot-Token aus.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_gruppe_skript.py`:

```python
"""Eine Web-Gruppe anlegen -- ohne Telegram, ohne Modell, ohne Netz.

Der Web-Bot-Prozess bedient genau EINE Gruppe, und ihre chat_id ist
synthetisch (repo.WEB_CHAT_ID_BASIS). Sie muss also jemand anlegen: der
Webserver kann es nicht, er liest read-only.
"""

import pytest

from interview_theater import db, repo
from scripts import web_gruppe


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    return verbindung


def test_lege_an_erzeugt_gruppe_token_und_kanal(conn):
    daten = web_gruppe.lege_an(
        conn, "gruppe1", "Die Ankommenden", "https://lab.example/theatersoap"
    )
    assert daten["chat_id"] >= repo.WEB_CHAT_ID_BASIS
    gruppe = repo.hole_gruppe(conn, daten["chat_id"])
    assert gruppe["bot_name"] == "gruppe1"
    assert gruppe["titel"] == "Die Ankommenden"
    assert gruppe["kanal"] == "web"
    assert gruppe["web_token"] == daten["token"]
    assert daten["url"] == f"https://lab.example/theatersoap/g/{daten['token']}/chat"


def test_zwei_gruppen_bekommen_verschiedene_ids(conn):
    erste = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    zweite = web_gruppe.lege_an(conn, "gruppe2", "B", "")
    assert zweite["chat_id"] == erste["chat_id"] + 1
    assert zweite["token"] != erste["token"]


def test_ohne_basis_url_gibt_es_keinen_link(conn):
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    assert daten["url"] is None


def test_die_env_zeilen_nennen_kanal_und_chat_id(conn):
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    assert "IT_KANAL=web" in daten["env"]
    assert f"IT_WEB_CHAT_ID={daten['chat_id']}" in daten["env"]


def test_der_bericht_nennt_keinen_bot_token(conn):
    """Das Skript liest keine Env-Datei einer Gruppe und gibt nichts aus, was
    ein Geheimnis eines anderen Dienstes ist. Der Web-Token IST das Geheimnis
    des Links -- er steht bewusst da, das ist der Zweck."""
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "https://lab.example/theatersoap")
    text = web_gruppe.bericht(daten)
    assert "IT_BOT_TOKEN" not in text
    assert daten["token"] in text
    assert "IT_KANAL=web" in text


def test_das_skript_liest_niemals_betrieb(tmp_path):
    """Keine Zeile darf 'betrieb/' oeffnen: dort liegen echte Zugangsdaten,
    und ein Skript, das sie einmal liest, gibt sie irgendwann aus."""
    from pathlib import Path

    quelle = Path(web_gruppe.__file__).read_text(encoding="utf-8")
    assert "betrieb" not in quelle


def test_main_ohne_it_db_bricht_ab(monkeypatch, capsys):
    monkeypatch.delenv("IT_DB", raising=False)
    assert web_gruppe.main(["anlegen", "gruppe1"]) == 1
    assert "IT_DB" in capsys.readouterr().err


def test_main_legt_an_und_druckt(monkeypatch, tmp_path, capsys):
    pfad = str(tmp_path / "t.db")
    vorbereitung = db.verbinde(pfad)
    db.initialisiere(vorbereitung)
    vorbereitung.close()
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://lab.example/theatersoap")

    assert web_gruppe.main(["anlegen", "gruppe1", "--titel", "Die Ankommenden"]) == 0
    ausgabe = capsys.readouterr().out
    assert "IT_KANAL=web" in ausgabe
    assert "/chat" in ausgabe

    nachher = db.verbinde(pfad)
    assert repo.hole_gruppe(nachher, repo.WEB_CHAT_ID_BASIS)["kanal"] == "web"


def test_main_kennt_nur_anlegen(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("IT_DB", str(tmp_path / "t.db"))
    assert web_gruppe.main(["loeschen", "gruppe1"]) == 2
    assert "anlegen" in capsys.readouterr().err
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gruppe_skript.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'scripts.web_gruppe'`.

- [x] **Schritt 3: `scripts/web_gruppe.py` schreiben**

```python
"""Eine Web-Gruppe anlegen (30.09.2026, Karte Padua A2).

Eine Gruppe im Web-Kanal hat keine echte Telegram-``chat_id`` -- es gibt
keinen Chat, es gibt einen Link. Ihre chat_id ist deshalb synthetisch
(``repo.WEB_CHAT_ID_BASIS``), und **anlegen muss sie jemand von Hand**: der
Webserver kann es nicht, er oeffnet die Datenbank read-only, und der Bot
legt eine Gruppe nur beim ersten Update an -- das aber kommt erst, wenn
jemand den Link hat.

Kein Modellaufruf, kein Netz, kein Telegram. Und **keine Zeile liest eine
Env-Datei einer Gruppe**: dort stehen echte Zugangsdaten, und ein Skript, das
sie einmal liest, gibt sie irgendwann aus. Ausgegeben wird nur, was neu ist:
die chat_id, der Link und die zwei Zeilen fuer die Env-Datei.

Aufruf::

    IT_DB=betrieb/soap.db IT_WEB_URL=https://lab.artesmobiles.art/theatersoap \\
      python -m scripts.web_gruppe anlegen gruppe4 --titel "Gruppe D"

Danach die zwei ausgegebenen Zeilen nach ``betrieb/gruppe4.env`` und
``systemctl --user restart interview-theater@gruppe4``.
"""

import argparse
import os
import sys

from interview_theater import db, repo

#: Wo die Chatansicht liegt (``web_chat.CHAT_PFAD``). Als Literal, damit das
#: Skript den Webserver nicht importieren muss -- ein Test haelt beide
#: zusammen (tests/test_web_chat.py).
CHAT_PFAD = "chat"


def lege_an(conn, bot_name: str, titel: str, basis_url: str) -> dict:
    """Legt die Gruppe an und liefert alles, was jemand danach braucht.

    ``repo.sichere_gruppe`` erzeugt das Web-Token gleich mit
    (``stelle_web_token_sicher``) -- derselbe Weg wie beim ersten Kontakt
    eines Telegram-Bots, keine zweite Token-Quelle."""
    chat_id = repo.naechste_web_chat_id(conn)
    repo.sichere_gruppe(conn, chat_id, bot_name, titel)
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    token = repo.stelle_web_token_sicher(conn, chat_id)
    basis = (basis_url or "").rstrip("/")
    return {
        "chat_id": chat_id,
        "token": token,
        "url": f"{basis}/g/{token}/{CHAT_PFAD}" if basis and token else None,
        "env": ["IT_KANAL=web", f"IT_WEB_CHAT_ID={chat_id}"],
        "bot_name": bot_name,
        "titel": titel,
    }


def bericht(daten: dict) -> str:
    """Was auf die Konsole geht -- in der Reihenfolge, in der man es braucht:
    erst der Link (den bekommt die Gruppe), dann die Env-Zeilen (die braucht
    der Betrieb), dann der Neustart."""
    zeilen = [
        f"Web-Gruppe angelegt: {daten['titel'] or '(ohne Titel)'} "
        f"(chat_id {daten['chat_id']}, Bot {daten['bot_name']})",
        "",
        "Der Link fuer die Gruppe:",
        f"  {daten['url'] or '(IT_WEB_URL ist nicht gesetzt -- kein Link)'}",
        "",
        f"Diese zwei Zeilen nach betrieb/{daten['bot_name']}.env:",
    ]
    zeilen += [f"  {zeile}" for zeile in daten["env"]]
    zeilen += [
        "",
        f"Danach: systemctl --user restart interview-theater@{daten['bot_name']}",
        "",
        "Der Link IST das Geheimnis (kein Login) -- er geht nur an diese Gruppe.",
        "Ein QR-Code ist nicht Teil dieses Skripts (keine Abhaengigkeit dafuer).",
    ]
    return "\n".join(zeilen)


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.web_gruppe",
        description="Legt eine Gruppe im Web-Kanal an (IT_KANAL=web).",
    )
    zerleger.add_argument("befehl", choices=["anlegen"])
    zerleger.add_argument("bot_name", help="wie die Env-Datei: betrieb/<name>.env")
    zerleger.add_argument("--titel", default="", help="Anzeigename der Gruppe")
    argumente = zerleger.parse_args(argv)

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        return 1

    conn = db.verbinde(db_pfad)
    try:
        db.initialisiere(conn)
        daten = lege_an(
            conn, argumente.bot_name, argumente.titel,
            os.environ.get("IT_WEB_URL", ""),
        )
    finally:
        conn.close()
    print(bericht(daten))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`argparse` mit `choices=["anlegen"]` beendet den Prozess bei einem anderen Wort mit
Exitcode 2 und einer Meldung auf `stderr`, die `anlegen` nennt — genau das, was
`test_main_kennt_nur_anlegen` erwartet. Dafuer muss `main` den `SystemExit` durchlassen;
der Test faengt ihn nicht, also braucht er ein `pytest.raises(SystemExit)`. **Anpassung im
Test:**

```python
def test_main_kennt_nur_anlegen(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("IT_DB", str(tmp_path / "t.db"))
    with pytest.raises(SystemExit) as beendet:
        web_gruppe.main(["loeschen", "gruppe1"])
    assert beendet.value.code == 2
    assert "anlegen" in capsys.readouterr().err
```

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gruppe_skript.py -q -p no:cacheprovider
```
Erwartet: `10 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2850 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add scripts/web_gruppe.py tests/test_web_gruppe_skript.py
git commit -m "Web-Kanal: scripts/web_gruppe.py legt eine Gruppe mit Link und Env-Zeilen an

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 6: Die Chatansicht — HTML-Filter, Verlauf, Routing

**Dateien:**
- Neu: `interview_theater/web_chat.py`
- Aendern: `interview_theater/web_daten.py` (drei Lesefunktionen, read-only)
- Aendern: `interview_theater/web.py` (**nur** Routing, ~16 Zeilen in zwei Funktionen)
- Aendern: `interview_theater/web.py` — eine Zeile im Gruppenseiten-Kopf: der Link zum Chat
- Test: `tests/test_web_chat.py` (neu)

**Schnittstellen — Konsumiert:** `repo.web_knoepfe`, `repo.WEB_TYP_*` (Aufgabe 1).
**Schnittstellen — Produziert:**

```python
# interview_theater/web_daten.py
def web_chatverlauf(conn, chat_id: int, nach: int = 0, grenze: int = 200) -> list[dict]
def web_chatzustand(conn, token: str, nach: int = 0) -> dict | None
def web_ausgangsdatei(conn, chat_id: int, post_id: int) -> dict | None

# interview_theater/web_chat.py
CHAT_PFAD = "chat"
ERLAUBTE_TAGS = ("b", "i", "u", "s", "code", "pre", "blockquote")
def sichere_html(text: str | None) -> str
def chat_html(daten: dict, nonce_wert: str, token: str, praefix: str,
              segment_ms: int) -> str
def beantworte_get(handler, db_pfad: str, token: str, unterpfad: str,
                   praefix: str, schluessel: bytes, query: str) -> None
```

`praefix` wird in `chat_html` **nicht gelesen**: alle Verweise der Seite sind relativ
(`<token>/chat/…`), damit sie hinter nginx mit und ohne Praefix greifen — genau wie beim
Leitfaden-Link. Der Parameter steht trotzdem da, wortgleich zu `gruppe_html` und
`textbuch_html`: dieselbe Signatur fuer alle drei Seiten. Meckert ein Linter, `# noqa: ARG001`
daran schreiben, nicht den Parameter entfernen.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat.py`:

```python
"""Die Chatansicht: was der Server liefert -- ohne Browser.

Der HTML-Filter ist der Kern dieser Datei. Bot-Ausgaben tragen
Telegram-HTML (parse_mode="HTML", fuenf Stellen im Repo, u. a.
vorschlag.menuetext): die Chatansicht muss es DARSTELLEN und darf dabei
nichts anderes durchlassen.
"""

import json
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_daten

CHAT = 7_000_000_000_001


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token


# -- der HTML-Filter (Entscheidung F) --------------------------------------


@pytest.mark.parametrize("gefaehrlich", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<a href=\"javascript:alert(1)\">klick</a>",
    "<iframe src=\"https://example.invalid\"></iframe>",
    "<b onclick=\"alert(1)\">fett</b>",
    "<svg/onload=alert(1)>",
    "<a href=\"data:text/html,<script>alert(1)</script>\">x</a>",
    "<style>body{display:none}</style>",
])
def test_nichts_gefaehrliches_kommt_durch(gefaehrlich):
    ergebnis = web_chat.sichere_html(gefaehrlich)
    for verboten in ("<script", "<img", "<iframe", "<svg", "<style",
                     "onerror", "onclick", "onload", "javascript:", "data:text"):
        assert verboten not in ergebnis.lower(), ergebnis


@pytest.mark.parametrize("tag", list(web_chat.ERLAUBTE_TAGS))
def test_die_telegram_teilmenge_kommt_durch(tag):
    ergebnis = web_chat.sichere_html(f"<{tag}>Text</{tag}>")
    assert ergebnis == f"<{tag}>Text</{tag}>"


def test_ein_link_kommt_durch_und_bekommt_noopener():
    ergebnis = web_chat.sichere_html(
        '<a href="https://lab.example/theatersoap/g/x">Gruppenseite</a>'
    )
    assert 'href="https://lab.example/theatersoap/g/x"' in ergebnis
    assert "noopener" in ergebnis
    assert ">Gruppenseite</a>" in ergebnis


def test_ein_link_ohne_http_kommt_nicht_durch():
    ergebnis = web_chat.sichere_html('<a href="ftp://x/y">z</a>')
    assert "<a " not in ergebnis
    assert "&lt;a" in ergebnis


def test_der_ampersand_bleibt_ein_ampersand():
    """Telegram-HTML maskiert & als &amp; (telegram.escape_html). Die Ansicht
    darf daraus kein doppelt maskiertes &amp;amp; machen."""
    assert web_chat.sichere_html("Kaffee &amp; Kuchen") == "Kaffee &amp; Kuchen"
    assert web_chat.sichere_html("Kaffee & Kuchen") == "Kaffee &amp; Kuchen"


def test_zeilenumbrueche_werden_sichtbar():
    assert web_chat.sichere_html("eins\nzwei") == "eins<br>zwei"


def test_leerer_text_ist_leer():
    assert web_chat.sichere_html(None) == ""
    assert web_chat.sichere_html("") == ""


def test_ein_echter_vorschlagsblock_bleibt_lesbar():
    """Der gemessene Fall: vorschlag.menuetext baut genau diese Form."""
    roh = ("Drei Richtungen:\n"
           "1. <b>Ankunft am Steg</b> — sie warten auf ein Boot\n"
           "2. <b>Nacht im Treppenhaus</b> — niemand schlaeft")
    ergebnis = web_chat.sichere_html(roh)
    assert "<b>Ankunft am Steg</b>" in ergebnis
    assert ergebnis.count("<br>") == 2


# -- der Verlauf (web_daten, read-only) ------------------------------------


def test_verlauf_zeigt_beide_richtungen_in_der_reihenfolge(datenbank):
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    ein = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                repo.WEB_TYP_TEXT, text="Unsere Begriffe")
    aus = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                repo.WEB_TYP_TEXT, text="Notiert.",
                                knoepfe=[("Ja, speichern", "k:1")])
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    assert [z["id"] for z in verlauf] == [ein, aus]
    assert verlauf[0]["von"] == "gruppe"
    assert verlauf[1]["von"] == "bot"
    assert verlauf[1]["knoepfe"] == [["Ja, speichern", "k:1"]]


def test_verlauf_verbirgt_befehle_und_geloeschtes(datenbank):
    """'befehl' ist der Umschalter-Druck, der als Slash-Text in den Bot geht.
    Slash-Befehle werden nicht beworben (AGENTS.md) -- er steht nicht im Chat."""
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                          repo.WEB_TYP_BEFEHL, text="/interview")
    weg = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                repo.WEB_TYP_TEXT, text="Arbeitszeile")
    repo.loesche_web_posts(schreibend, CHAT, [weg])
    bleibt = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="Notiert.")
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()
    assert [z["id"] for z in verlauf] == [bleibt]


def test_verlauf_ab_nach(datenbank):
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    erste = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                  repo.WEB_TYP_TEXT, text="a")
    zweite = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="b")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    assert [z["id"] for z in web_daten.web_chatverlauf(lesend, CHAT, nach=erste)] == [zweite]
    lesend.close()


def test_eine_sprachnachricht_zeigt_die_dauer_und_keinen_pfad(datenbank):
    """Der Dateipfad gehoert nicht ins HTML: er ist eine Serverinnerei, und
    die Ansicht ist ohne Login erreichbar."""
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                          dauer=45, datei="/tmp/geheim/1.webm", mime="audio/webm")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    zeile = web_daten.web_chatverlauf(lesend, CHAT)[0]
    lesend.close()
    assert zeile["typ"] == repo.WEB_TYP_SPRACHE
    assert zeile["dauer"] == 45
    assert "datei" not in zeile


def test_zustand_nennt_phase_interviewmodus_und_tippt(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    repo.setze_phase(schreibend, CHAT, 3)
    repo.setze_interviewmodus(schreibend, CHAT, repo._jetzt())
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    zustand = web_daten.web_chatzustand(lesend, token)
    lesend.close()

    assert zustand["chat_id"] == CHAT
    assert zustand["phase"] == 3
    assert zustand["interviewmodus"] is True
    assert zustand["tippt"] is False
    assert zustand["nachrichten"] == []
    assert zustand["letzte"] == 0


def test_zustand_meldet_tippt_nur_solange_es_gilt(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    repo.setze_web_tippt(schreibend, CHAT, "2020-01-01T00:00:00+00:00")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, token)["tippt"] is False
    lesend.close()


def test_zustand_traegt_die_knopfantwort_mit(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    post_id = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                    repo.WEB_TYP_KNOPF, daten="k:1",
                                    bezug_message_id=1)
    repo.setze_web_antwort(schreibend, post_id, "Begriffe uebernommen")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    zustand = web_daten.web_chatzustand(lesend, token)
    lesend.close()
    assert zustand["antworten"] == {str(post_id): "Begriffe uebernommen"}


def test_zustand_bei_unbekanntem_token_ist_none(datenbank):
    pfad, _token = datenbank
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, "gibtsnicht") is None
    lesend.close()


# -- Routing --------------------------------------------------------------


@pytest.fixture
def server(datenbank):
    pfad, token = datenbank
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    import threading

    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _hole(url: str):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_die_chatansicht_ist_erreichbar(server):
    basis, token, _pfad = server
    for url in (f"{basis}/g/{token}/chat", f"{basis}/theatersoap/g/{token}/chat"):
        status, text = _hole(url)
        assert status == 200
        assert "<!doctype html>" in text


def test_der_zustand_kommt_als_json(server):
    basis, token, _pfad = server
    status, text = _hole(f"{basis}/g/{token}/chat/zustand?nach=0")
    assert status == 200
    zustand = json.loads(text)
    assert zustand["chat_id"] == CHAT
    assert "nachrichten" in zustand


def test_unbekanntes_token_ist_404(server):
    basis, _token, _pfad = server
    for pfad in ("/g/gibtsnicht/chat", "/g/gibtsnicht/chat/zustand"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _hole(basis + pfad)
        assert fehler.value.code == 404


def test_unbekannter_unterpfad_ist_404(server):
    basis, token, _pfad = server
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _hole(f"{basis}/g/{token}/chat/irgendwas")
    assert fehler.value.code == 404


def test_die_bestehenden_routen_leben_weiter(server):
    """E1 im Kleinen: die Gruppenseite, die Probenansicht und der Leitfaden
    duerfen durch das neue Routing nicht verschwinden."""
    basis, token, _pfad = server
    for pfad in ("", "/textbuch", "/leitfaden", "/textbuch.md"):
        status, _text = _hole(f"{basis}/g/{token}{pfad}")
        assert status == 200
    assert _hole(f"{basis}/gesund")[1].strip() == "ok"


def test_die_gruppenseite_verlinkt_den_chat(server):
    basis, token, _pfad = server
    _status, text = _hole(f"{basis}/g/{token}")
    assert f"{token}/{web_chat.CHAT_PFAD}" in text


def test_kein_transkript_und_kein_pfad_im_chat_html(server):
    """Dieselben drei Grenzen wie auf der Gruppenseite (AGENTS.md): kein
    Volltranskript, kein Dateipfad, kein unbelegtes Zitat -- die Ansicht ist
    ohne Login erreichbar."""
    basis, token, pfad = server
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                          dauer=45, datei="/tmp/geheim/zwirbelkiste.webm",
                          mime="audio/webm")
    schreibend.close()
    _status, text = _hole(f"{basis}/g/{token}/chat")
    assert "zwirbelkiste" not in text.lower()
    assert "/tmp/" not in text


def test_der_chat_pfad_ist_in_skript_und_modul_derselbe():
    from scripts import web_gruppe

    assert web_gruppe.CHAT_PFAD == web_chat.CHAT_PFAD
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.web_chat'`.

- [x] **Schritt 3: `web_daten.py` — die drei Lesefunktionen**

Am Dateiende anhaengen. Read-only, reine Funktionen, `conn` rein und Dicts raus — wie der
Rest des Moduls.

```python
# --- Der Web-Chat (30.09.2026, Karte Padua A2) -----------------------------

#: Wie viele Nachrichten die Chatansicht hoechstens auf einmal traegt. Ein
#: Workshoptag sind einige hundert; mehr als das braucht niemand auf einem
#: Telefon, und der Poll holt ohnehin nur das Neue (``nach``).
CHAT_GRENZE = 200

#: Was NICHT im Chat steht: der Umschalter-Druck, der als Slash-Text in den
#: Bot geht. Slash-Befehle werden nicht beworben (AGENTS.md) -- beworben wird
#: der Knopf, und der steht schon da.
_CHAT_VERBORGEN = ("befehl",)


def web_chatverlauf(conn, chat_id: int, nach: int = 0, grenze: int = CHAT_GRENZE) -> list:
    """Der Chatverlauf einer Web-Gruppe ab ``nach`` (exklusiv), aelteste zuerst.

    Geliefert wird genau das, was die Ansicht braucht -- **und der Dateipfad
    ist nicht dabei.** Er ist eine Serverinnerei, und die Seite ist ohne Login
    erreichbar (dieselbe Grenze wie 'kein Volltranskript auf der
    Gruppenseite')."""
    zeilen = conn.execute(
        "SELECT id, richtung, typ, text, knoepfe, dauer, dateiname, erstellt_am "
        "FROM web_post WHERE chat_id = ? AND id > ? AND geloescht_am IS NULL "
        f"AND typ NOT IN ({','.join('?' * len(_CHAT_VERBORGEN))}) "
        "AND typ != 'knopf' "
        "ORDER BY id ASC LIMIT ?",
        (chat_id, nach, *_CHAT_VERBORGEN, grenze),
    ).fetchall()
    return [
        {
            "id": int(z["id"]),
            "von": "bot" if z["richtung"] == "aus" else "gruppe",
            "typ": z["typ"],
            "text": z["text"],
            "knoepfe": _web_knoepfe(z["knoepfe"]),
            "dauer": z["dauer"],
            "dateiname": z["dateiname"],
            "zeit": z["erstellt_am"],
        }
        for z in zeilen
    ]


def _web_knoepfe(roh) -> list:
    """Dieselbe Deutung wie ``repo.web_knoepfe`` -- hier eigens, weil
    ``web_daten`` bewusst nicht von ``repo`` abhaengt (der Webserver soll
    keinen Schreibpfad importieren, siehe Moduldocstring)."""
    if not roh:
        return []
    try:
        gelesen = json.loads(roh)
    except (TypeError, ValueError):
        return []
    return [list(eintrag) for eintrag in gelesen if len(eintrag) == 2]


def web_chatzustand(conn, token: str, nach: int = 0) -> dict | None:
    """Alles, was der Browser bei einem Poll braucht -- oder None bei
    unbekanntem Token.

    Ein Aufruf statt vier: der Browser fragt alle zwei Sekunden, und vier
    Anfragen je Takt waeren bei drei Gruppen mit je zwei Telefonen
    sechsunddreissig Anfragen in der Minute fuer dieselbe Antwort."""
    chat_id = chat_id_nach_token(conn, token)
    if chat_id is None:
        return None
    gruppe = conn.execute(
        "SELECT titel, interviewmodus_seit, web_tippt_bis FROM gruppe WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    nachrichten = web_chatverlauf(conn, chat_id, nach)
    letzte = nachrichten[-1]["id"] if nachrichten else nach
    # Phase wie web_daten.py:107 -- repo-frei, fehlende Spalte = None.
    stand = conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return {
        "chat_id": chat_id,
        "titel": gruppe["titel"] if gruppe else None,
        "phase": _feld(stand, "phase"),
        "interviewmodus": bool(gruppe and gruppe["interviewmodus_seit"]),
        "tippt": _tippt_noch(gruppe["web_tippt_bis"] if gruppe else None),
        "nachrichten": nachrichten,
        "letzte": letzte,
        "antworten": _web_antworten(conn, chat_id),
        "segment_ms": None,   # setzt der HTML-Bau, nicht der Poll
    }


def _tippt_noch(bis_iso) -> bool:
    """Gilt die Tippanzeige noch? ``WebKanal.tippt`` setzt sie auf
    ``jetzt + TIPPT_GUELTIG_S``; ist der Zeitpunkt vorbei, schreibt gerade
    niemand mehr (und ein abgebrochener Lauf laesst sie nicht stehen)."""
    zeitpunkt = lies_zeitstempel(bis_iso)
    if zeitpunkt is None:
        return False
    return zeitpunkt > datetime.now(timezone.utc)


def _web_antworten(conn, chat_id: int) -> dict:
    """Die ``answerCallbackQuery``-Texte der letzten Knopfdruecke, nach
    Druck-id. In Telegram ist das die kleine Blase ueber dem Knopf; im
    Browser zeigt sie die Seite kurz unter der Leiste an."""
    zeilen = conn.execute(
        "SELECT id, antwort FROM web_post WHERE chat_id = ? AND typ = 'knopf' "
        "AND antwort IS NOT NULL ORDER BY id DESC LIMIT 5",
        (chat_id,),
    ).fetchall()
    return {str(int(z["id"])): z["antwort"] for z in zeilen}


def web_ausgangsdatei(conn, chat_id: int, post_id: int) -> dict | None:
    """Die Datei zu einer ``sende_datei``-Zeile (Textbuch-Export) -- Pfad und
    Name, oder None. Der Pfad bleibt serverseitig; die Route liefert den
    Inhalt aus, nicht den Ort."""
    zeile = conn.execute(
        "SELECT datei, dateiname FROM web_post WHERE id = ? AND chat_id = ? "
        "AND typ = 'datei' AND geloescht_am IS NULL",
        (post_id, chat_id),
    ).fetchone()
    if zeile is None or not zeile["datei"]:
        return None
    return {"pfad": zeile["datei"], "dateiname": zeile["dateiname"] or "datei"}
```

`_phase` gibt es in `web_daten` **nicht** (gemessen, siehe „Annahmen"): die Phase aus der
`arbeitsstand`-Zeile ueber `_feld(zeile, "phase")` lesen wie web_daten.py:107, `repo`-frei. `json`, `datetime`, `timezone` im Modulkopf pruefen
und ergaenzen.

- [x] **Schritt 4: `web_chat.py` — Filter, HTML, GET-Handler**

```python
"""Der Chat im Browser (30.09.2026, Karte Padua A2).

Die Gegenseite zu ``web_kanal.py``: dort schreibt der Bot in ``web_post``,
hier liest der Browser es. **Eigenes Modul und nicht in ``web.py``**, weil
``web.py`` ein Kollisions-Hotspot mit Karte A1 ist -- dort stehen nur die
Routing-Zeilen, alles andere (HTML, CSS, JS, Handler) liegt hier.

**Kein SQL, kein Modell.** Gelesen wird ueber ``web_daten`` (read-only),
geschrieben ueber ``repo`` (Aufgaben 7-10). Der Webserver hat keinen
Modellklienten und soll keinen bekommen.

**Der HTML-Filter ist der Kern.** Bot-Ausgaben tragen Telegram-HTML
(``parse_mode="HTML"``, fuenf Stellen im Repo, u. a. ``vorschlag.menuetext``):
die Ansicht muss es darstellen und darf nichts anderes durchlassen. Der Weg
ist bewusst der langweilige: **alles maskieren, dann eine geschlossene Liste
wieder zulassen** -- nicht "das Gefaehrliche entfernen".
"""

import html
import re
import urllib.parse

from interview_theater import web_daten

#: Der Unterpfad unter ``/g/<token>/``. Steht wortgleich in
#: ``scripts/web_gruppe.CHAT_PFAD`` (Test).
CHAT_PFAD = "chat"

#: Die Telegram-Teilmenge ohne Attribute. ``a`` steht nicht dabei, weil es
#: eins hat und eigens behandelt wird.
ERLAUBTE_TAGS = ("b", "i", "u", "s", "code", "pre", "blockquote")

_TAGS = re.compile(
    r"&lt;(/?)(" + "|".join(ERLAUBTE_TAGS) + r")&gt;", re.IGNORECASE
)
#: Nur http und https, nur ohne maskiertes Ampersand im Ziel. Eine URL mit
#: Query-Parametern (``&amp;``) bleibt deshalb Text statt Link -- die
#: Fehlerrichtung ist bewusst: ein nicht klickbarer Link ist ein
#: Schoenheitsfehler, ein durchgelassenes Attribut ist ein Loch.
_LINK = re.compile(
    r"&lt;a href=&quot;(https?://[^&quot;&lt;&gt;\s]+)&quot;&gt;", re.IGNORECASE
)
_LINK_ENDE = re.compile(r"&lt;/a&gt;", re.IGNORECASE)


def sichere_html(text) -> str:
    """Telegram-HTML als sicheres HTML fuer die Chatansicht.

    Drei Schritte in dieser Reihenfolge: (1) alles maskieren
    (``html.escape``, inklusive Anfuehrungszeichen), (2) die geschlossene
    Liste wieder zulassen, (3) Zeilenumbrueche sichtbar machen.

    Dass Schritt 1 zuerst kommt, ist die ganze Sicherheit: danach gibt es im
    Text kein einziges ``<`` mehr, und Schritt 2 kann nur das erzeugen, was er
    ausdruecklich erlaubt. Ein Filter, der stattdessen ``<script>`` entfernt,
    ist eine Liste von Dingen, an die jemand gedacht hat."""
    maskiert = html.escape(text or "", quote=True)
    mit_tags = _TAGS.sub(lambda t: f"<{t.group(1)}{t.group(2).lower()}>", maskiert)
    mit_links = _LINK.sub(
        lambda t: (
            f'<a href="{t.group(1)}" target="_blank" rel="noopener noreferrer">'
        ),
        mit_tags,
    )
    mit_links = _LINK_ENDE.sub("</a>", mit_links)
    return mit_links.replace("\n", "<br>")
```

Dazu die Textkonstanten und der Seitenbau (die JS-Konstante `_CHAT_JS` kommt erst in
Aufgabe 11 — hier ein leerer String, damit die Seite schon steht):

```python
_TEXT_TITEL = "Chat mit dem Theaterbot"
_TEXT_LEER = "Noch nichts da. Schreibt mir, womit ihr anfangen wollt."
_TEXT_EINGABE = "Schreiben …"
_TEXT_SENDEN = "Senden"
_TEXT_TIPPT = "schreibt …"
_TEXT_SPRACHE = "Sprachnachricht ({dauer})"
_TEXT_DATEI = "Datei: {name}"
_TEXT_ZUR_GRUPPENSEITE = "Zur Gruppenseite"
_TEXT_INTERVIEW_AN = "Interview aufnehmen"
_TEXT_INTERVIEW_AUS = "Aufnahme beenden"
_TEXT_PTT = "Halten und sprechen"
_TEXT_OHNE_JS = (
    "Fuer Chat und Aufnahme braucht diese Seite JavaScript. "
    "Die Gruppenseite und das Textbuch funktionieren auch ohne."
)

#: Die Seite ist gross gesetzt: sie liegt auf einem Telefon in einem
#: Probenraum, und die Gruppe liest im Stehen.
_CSS_CHAT = """
body { background: #fbfaf8; color: #17181b; padding: .6rem .7rem 9rem;
       max-width: 44rem; margin: 0 auto; }
.verlauf { display: flex; flex-direction: column; gap: .55rem; }
.blase { padding: .55rem .7rem; border-radius: .8rem; max-width: 88%;
         font-size: 1.02rem; overflow-wrap: anywhere; }
.blase.bot { background: #fff; border: 1px solid #e0ddd6; align-self: flex-start;
             border-bottom-left-radius: .2rem; }
.blase.gruppe { background: #1f6f5c; color: #fff; align-self: flex-end;
                border-bottom-right-radius: .2rem; }
.blase.sprache { font-style: italic; opacity: .85; }
.leiste { display: flex; flex-direction: column; gap: .35rem; margin: .1rem 0 .3rem;
          align-self: flex-start; width: 88%; }
.leiste button { font: inherit; text-align: left; padding: .65rem .8rem;
                 border-radius: .7rem; border: 1px solid #1f6f5c;
                 background: #fff; color: #17181b; min-height: 2.9rem; }
.leiste button:disabled { opacity: .45; }
.quittung { font-size: .82rem; opacity: .7; align-self: flex-start; }
.tippt { font-size: .85rem; opacity: .6; height: 1.2em; }
.fuss { position: fixed; left: 0; right: 0; bottom: 0; background: #fbfaf8;
        border-top: 1px solid #e0ddd6; padding: .5rem .7rem .8rem;
        display: flex; flex-direction: column; gap: .5rem; }
.zeile { display: flex; gap: .4rem; align-items: stretch; }
.zeile input { flex: 1; font: inherit; padding: .6rem .7rem; min-height: 2.9rem;
               border-radius: .7rem; border: 1px solid #c9c4b8; }
.zeile button { font: inherit; min-width: 3.4rem; min-height: 2.9rem;
                border-radius: .7rem; border: 0; background: #1f6f5c; color: #fff; }
#interview { font: inherit; font-weight: 600; min-height: 3.2rem; width: 100%;
             border-radius: .8rem; border: 1px solid #1f6f5c; background: #fff; }
#interview[data-laeuft="1"] { background: #a8201a; border-color: #a8201a;
                              color: #fff; min-height: 4rem; font-size: 1.15rem; }
#ptt[hidden], #interview[hidden] { display: none; }
.pegel { height: .45rem; border-radius: .3rem; background: #e0ddd6; overflow: hidden; }
.pegel span { display: block; height: 100%; width: 0; background: #a8201a; }
.uhr { font-variant-numeric: tabular-nums; font-size: 1.3rem; text-align: center; }
.warteschlange { font-size: .82rem; opacity: .7; text-align: center; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e7e9ec; }
  .blase.bot { background: #1d2026; border-color: #2c313a; }
  .fuss { background: #14161a; border-color: #2c313a; }
  .zeile input { background: #1d2026; color: #e7e9ec; border-color: #2c313a; }
  .leiste button { background: #1d2026; color: #e7e9ec; }
}
"""

#: Wird in Aufgabe 11 gefuellt.
_CHAT_JS = ""


def _blase_html(n: dict) -> str:
    """Eine Nachricht als Blase, gegebenenfalls mit ihrer Leiste darunter."""
    if n["typ"] == "sprache":
        minuten, sekunden = divmod(int(n["dauer"] or 0), 60)
        inhalt = html.escape(_TEXT_SPRACHE.format(dauer=f"{minuten}:{sekunden:02d}"))
        klasse = "sprache"
    elif n["typ"] == "datei":
        inhalt = (
            f'<a href="{CHAT_PFAD}/datei/{n["id"]}">'
            + html.escape(_TEXT_DATEI.format(name=n["dateiname"] or "datei"))
            + "</a>"
        )
        if n["text"]:
            inhalt = sichere_html(n["text"]) + "<br>" + inhalt
        klasse = "datei"
    else:
        inhalt = sichere_html(n["text"])
        klasse = "text"

    teile = [
        f'<div class="blase {n["von"]} {klasse}" data-id="{n["id"]}">{inhalt}</div>'
    ]
    if n["knoepfe"]:
        knoepfe = "".join(
            f'<button type="button" data-message="{n["id"]}" '
            f'data-daten="{html.escape(daten, quote=True)}">'
            f"{html.escape(beschriftung)}</button>"
            for beschriftung, daten in n["knoepfe"]
        )
        teile.append(f'<div class="leiste" data-message="{n["id"]}">{knoepfe}</div>')
    return "\n".join(teile)


def chat_html(daten: dict, nonce_wert: str, token: str, praefix: str,
              segment_ms: int) -> str:
    """Die Chatansicht.

    Sie haengt sich in ``web._seite`` ein (dieselbe Klammer, dasselbe
    Grund-CSS), aber **ohne** dessen sanftes Nachladen: das tauscht den
    ``<body>`` aus, und mitten in einer laufenden Aufnahme wuerde das
    Recorder, Timer und Warteschlange mitreissen. Nachgeladen wird hier
    gezielt, per Poll (``_CHAT_JS``), und nur der Verlauf."""
    from interview_theater import web   # spaeter Import: web importiert web_chat

    blasen = "\n".join(_blase_html(n) for n in daten["nachrichten"])
    if not blasen:
        blasen = f'<p class="leer">{html.escape(_TEXT_LEER)}</p>'

    koerper = (
        f"<h1>{html.escape(daten.get('titel') or _TEXT_TITEL)}</h1>\n"
        f'<p><a href="{html.escape(token)}">'
        f"{html.escape(_TEXT_ZUR_GRUPPENSEITE)}</a></p>\n"
        f'<noscript><p class="leer">{html.escape(_TEXT_OHNE_JS)}</p></noscript>\n'
        f'<div class="verlauf" id="verlauf" data-letzte="{daten["letzte"]}">\n'
        f"{blasen}\n</div>\n"
        f'<div class="tippt" id="tippt"></div>\n'
        f'<input type="hidden" id="nonce" value="{html.escape(nonce_wert, quote=True)}">\n'
        f'<div class="fuss" id="fuss" data-segment-ms="{int(segment_ms)}"\n'
        f'     data-interview="{1 if daten["interviewmodus"] else 0}">\n'
        f'  <div class="uhr" id="uhr" hidden></div>\n'
        f'  <div class="pegel" id="pegel" hidden><span></span></div>\n'
        f'  <div class="warteschlange" id="warteschlange"></div>\n'
        f'  <button type="button" id="interview">'
        f'{html.escape(_TEXT_INTERVIEW_AN)}</button>\n'
        f'  <div class="zeile">\n'
        f'    <input type="text" id="eingabe" autocomplete="off" '
        f'placeholder="{html.escape(_TEXT_EINGABE, quote=True)}">\n'
        f'    <button type="button" id="ptt" title="'
        f'{html.escape(_TEXT_PTT, quote=True)}">🎤</button>\n'
        f'    <button type="button" id="senden">'
        f'{html.escape(_TEXT_SENDEN)}</button>\n'
        f"  </div>\n"
        f"</div>\n"
    )
    return web._seite(
        daten.get("titel") or _TEXT_TITEL, _CSS_CHAT, koerper,
        nachladen=False, skript=_CHAT_JS,
    )
```

Und der GET-Handler:

```python
def beantworte_get(handler, db_pfad: str, token: str, unterpfad: str,
                   praefix: str, schluessel: bytes, query: str) -> None:
    """Alles unter ``/g/<token>/chat``: die Seite, der Zustands-Poll und die
    Dateien aus ``sende_datei``. Alles Unbekannte ist 404 -- wie bei
    ``web._beantworte_gruppenseite``."""
    from interview_theater import web

    if unterpfad == "":
        _sende_seite(handler, db_pfad, token, praefix, schluessel)
        return
    if unterpfad == "zustand":
        _sende_zustand(handler, db_pfad, token, query)
        return
    if unterpfad.startswith("datei/"):
        _sende_datei(handler, db_pfad, token, unterpfad[len("datei/"):])
        return
    handler._antworte(404, web.nicht_gefunden_html())


def _zustand(db_pfad: str, token: str, nach: int = 0) -> dict | None:
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return web_daten.web_chatzustand(conn, token, nach)
    finally:
        conn.close()


def _sende_seite(handler, db_pfad: str, token: str, praefix: str,
                 schluessel: bytes) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token)
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200,
        chat_html(daten, web.nonce(schluessel, token), token, praefix,
                  _segment_ms()),
    )


def _sende_zustand(handler, db_pfad: str, token: str, query: str) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token, _nach(query))
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    # Der Verlauf enthaelt HTML aus Bot-Ausgaben -- er wird HIER gefiltert,
    # nicht im Browser: ein Filter im JavaScript liegt auf der Seite, die er
    # schuetzen soll.
    for nachricht in daten["nachrichten"]:
        nachricht["html"] = sichere_html(nachricht["text"])
    daten["segment_ms"] = _segment_ms()
    handler._antworte(
        200, json.dumps(daten, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


def _sende_datei(handler, db_pfad: str, token: str, roh_id: str) -> None:
    from interview_theater import web

    if not roh_id.isdigit():
        handler._antworte(404, web.nicht_gefunden_html())
        return
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
        datei = (
            web_daten.web_ausgangsdatei(conn, chat_id, int(roh_id))
            if chat_id is not None else None
        )
    finally:
        conn.close()
    if datei is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    try:
        inhalt = Path(datei["pfad"]).read_text(encoding="utf-8")
    except OSError:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200, inhalt, "text/markdown; charset=utf-8",
        dateiname=datei["dateiname"],
    )


def _nach(query: str) -> int:
    """``?nach=<id>`` -- alles, was keine Zahl ist, gilt als 0. Ein
    Tippfehler in der Adresszeile soll keine 500 geben (wie
    ``web.fassungswahl``)."""
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def _segment_ms() -> int:
    """Die Segmentlaenge fuer den Browser. Aus der Umgebung, weil der
    Webserver keine ``Einstellungen`` laedt (er braucht weder LLM- noch
    STT-Variablen) -- derselbe Name wie dort
    (``einstellungen.VORGABE_SEGMENT_MS``)."""
    roh = (os.environ.get("IT_WEB_SEGMENT_MS") or "").strip()
    return int(roh) if roh.isdigit() and int(roh) > 0 else 45_000
```

Importe ergaenzen: `json`, `os`, `from pathlib import Path`.

- [x] **Schritt 5: `web.py` — die Routing-Zeilen**

In `_beantworte_gruppenseite`, **vor** `if unterpfad not in ("", "textbuch"):`:

```python
    # Der Chat im Browser (30.09.2026, Karte Padua A2). Nur die Weiche steht
    # hier -- HTML, CSS, JS und Handler liegen in web_chat.py, damit diese
    # Datei nicht weiter waechst. Der Import steht in der Funktion, wie bei
    # ``leitfaden`` und ``szenenfolge``: web_chat importiert seinerseits
    # ``web`` (fuer ``_seite``), und das waere im Modulkopf ein Zyklus.
    from interview_theater import web_chat

    if unterpfad == web_chat.CHAT_PFAD or unterpfad.startswith(web_chat.CHAT_PFAD + "/"):
        web_chat.beantworte_get(
            handler, db_pfad, token,
            unterpfad[len(web_chat.CHAT_PFAD):].strip("/"),
            praefix, schluessel, query,
        )
        return
```

In `_beantworte_post`, direkt nach der `startswith("/g/")`-Pruefung und **anstelle** von
`token = pfad[len("/g/"):].strip("/")`:

```python
    from interview_theater import web_chat

    rest = pfad[len("/g/"):].strip("/")
    token, _, unterpfad = rest.partition("/")
    if unterpfad == web_chat.CHAT_PFAD or unterpfad.startswith(web_chat.CHAT_PFAD + "/"):
        web_chat.beantworte_post(
            handler, db_pfad, token,
            unterpfad[len(web_chat.CHAT_PFAD):].strip("/"),
            schluessel,
        )
        return
    if unterpfad:
        # Vorher wurde daraus ein Token mit Schraegstrich darin und damit
        # ebenfalls 404 -- jetzt ausdruecklich.
        handler._antworte(404, nicht_gefunden_html())
        return
```

`web_chat.beantworte_post` gibt es erst ab Aufgabe 7. **Damit Aufgabe 6 fuer sich laeuft**,
in dieser Aufgabe einen Rumpf in `web_chat.py` anlegen:

```python
def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None:
    """Wird in den Aufgaben 7-10 gefuellt."""
    from interview_theater import web

    handler._antworte(404, web.nicht_gefunden_html())
```

Dazu der Link von der Gruppenseite. In `gruppe_html` (bei `_leitfaden_link`, derselbe
relative Stil — `<token>/chat`, damit es hinter nginx genauso geht) eine Zeile:

```python
#: Der Weg vom Lesen ins Arbeiten (30.09.2026): auf der Gruppenseite steht,
#: was entschieden ist -- im Chat entscheidet man. Relativ verlinkt, wie der
#: Leitfaden.
_TEXT_CHAT_LINK = "Chat mit dem Bot"


def _chat_link(token: str | None) -> str:
    if not token:
        return ""
    from interview_theater import web_chat

    return (
        f'<p><a href="{html.escape(token)}/{web_chat.CHAT_PFAD}">'
        f"{html.escape(_TEXT_CHAT_LINK)}</a></p>"
    )
```

und im Koerper von `gruppe_html` neben `_leitfaden_link(token)` einhaengen.

- [x] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat.py -q -p no:cacheprovider
```
Erwartet: `31 passed`.

```
$PY -m pytest tests/test_web.py tests/test_web_edit.py tests/test_web_textbuch.py \
  tests/test_web_daten.py tests/test_web_fassungen.py -q -p no:cacheprovider
```
Erwartet: alle passed. **Faellt hier einer**, ist es fast sicher
`test_die_bestehenden_routen_leben_weiter` im Kleinen: das neue explizite 404 in
`_beantworte_post`. Pruefen, ob ein bestehender Test ein POST auf `/g/<token>/irgendwas`
schickt und dort 404 erwartet — dann stimmt es weiterhin.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2881 passed, 1 skipped`.

- [x] **Schritt 7: Commit**

```bash
git add interview_theater/web_chat.py interview_theater/web_daten.py \
        interview_theater/web.py tests/test_web_chat.py
git commit -m "Web-Chat: Chatansicht mit serverseitigem HTML-Filter, Routing in web.py

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 7: Text senden

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`beantworte_post`, `_senden`)
- Test: `tests/test_web_chat_senden.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_chat.py
MAX_TEXT_ZEICHEN = 4000
def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None
def schreibend(db_pfad: str)   # Kontextmanager um db.verbinde
```

`POST /g/<token>/chat/senden`, JSON `{"nonce": …, "text": …}` → **202** mit
`{"message_id": N}`. 202 und nicht 200: der Bot hat noch nicht geantwortet, die Nachricht
liegt im Eingang.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat_senden.py`:

```python
"""Text aus dem Browser -- derselbe Weg wie eine Telegram-Nachricht.

Die Reihenfolge der Pruefungen ist dieselbe wie in web._beantworte_post:
Pfad, Token, Nonce, Wert -- erst 404, dann 403, dann 400. Ein unbekanntes
Token bekommt 404, weil der Nonce an das Token gebunden ist und fuer ein
Token, das es nicht gibt, gar nicht gueltig sein kann.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(url: str, koerper: dict, typ: str = "application/json"):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": typ}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def _nonce(token: str) -> str:
    return web.nonce(SCHLUESSEL, token)


def test_senden_legt_einen_eingang_an(aufbau):
    basis, token, pfad = aufbau
    status, text = _post(
        f"{basis}/g/{token}/chat/senden",
        {"nonce": _nonce(token), "text": "Unsere Begriffe: Ankommen, Arbeit, Nacht"},
    )
    assert status == 202
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["richtung"] == repo.RICHTUNG_EIN
    assert zeile["typ"] == repo.WEB_TYP_TEXT
    assert zeile["text"] == "Unsere Begriffe: Ankommen, Arbeit, Nacht"
    assert zeile["chat_id"] == CHAT


def test_senden_greift_auch_hinter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    status, _text = _post(
        f"{basis}/theatersoap/g/{token}/chat/senden",
        {"nonce": _nonce(token), "text": "hallo"},
    )
    assert status == 202


def test_ohne_nonce_gibt_es_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden", {"text": "hallo"})
    assert fehler.value.code == 403


def test_falscher_nonce_gibt_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden",
              {"nonce": "0.deadbeef", "text": "hallo"})
    assert fehler.value.code == 403


def test_unbekanntes_token_gibt_404_und_nicht_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/gibtsnicht/chat/senden",
              {"nonce": _nonce(token), "text": "hallo"})
    assert fehler.value.code == 404


def test_leerer_text_gibt_400_und_legt_nichts_an(aufbau):
    basis, token, pfad = aufbau
    for wert in ("", "   ", "\n\n"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _post(f"{basis}/g/{token}/chat/senden",
                  {"nonce": _nonce(token), "text": wert})
        assert fehler.value.code == 400
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_zu_langer_text_gibt_400(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden",
              {"nonce": _nonce(token), "text": "A" * (web_chat.MAX_TEXT_ZEICHEN + 1)})
    assert fehler.value.code == 400


def test_kaputtes_json_gibt_400(aufbau):
    basis, token, _pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/senden", data=b"{kaputt",
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 400


def test_unbekannter_unterpfad_gibt_404(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/irgendwas", {"nonce": _nonce(token)})
    assert fehler.value.code == 404


def test_das_dashboard_nimmt_weiter_kein_post_an(aufbau):
    """Es haengt am Beamer -- dort soll niemand im Vorbeigehen etwas
    umstellen (AGENTS.md)."""
    basis, _token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/", {"nonce": "x"})
    assert fehler.value.code == 404


def test_die_gesendete_nachricht_steht_im_verlauf(aufbau):
    basis, token, _pfad = aufbau
    _post(f"{basis}/g/{token}/chat/senden",
          {"nonce": _nonce(token), "text": "Unsere Begriffe"})
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert [n["text"] for n in zustand["nachrichten"]] == ["Unsere Begriffe"]
    assert zustand["nachrichten"][0]["von"] == "gruppe"


def test_der_text_wird_nicht_beim_schreiben_gefiltert(aufbau):
    """Gefiltert wird beim LESEN (sichere_html), nicht beim Schreiben: der Bot
    soll den Wortlaut der Gruppe sehen, und ``<`` in einer Nachricht ist keine
    Absicht, sondern ein Zeichen."""
    basis, token, pfad = aufbau
    _status, text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": _nonce(token), "text": "3 < 5 & <b>fett</b>"})
    message_id = json.loads(text)["message_id"]
    conn = db.verbinde(pfad)
    assert repo.hole_web_post(conn, message_id)["text"] == "3 < 5 & <b>fett</b>"


def test_kein_absendername_liegt_im_eingang(aufbau):
    """E8: Web-Nachrichten tragen keinen Vornamen. Es gibt nicht einmal eine
    Spalte dafuer -- ``web_kanal.ABSENDER`` setzt das Rollenwort erst beim
    Bauen des Updates."""
    basis, token, pfad = aufbau
    _status, text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": _nonce(token), "text": "hallo"})
    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, json.loads(text)["message_id"])
    assert "absender" not in zeile.keys()
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_senden.py -q -p no:cacheprovider
```
Erwartet: FAIL — die ersten Tests bekommen 404 vom Rumpf aus Aufgabe 6.

- [x] **Schritt 3: `web_chat.py` — der POST-Weg**

```python
#: Wie lang eine Nachricht aus dem Browser hoechstens ist. Dieselbe Zahl wie
#: ``telegram.NACHRICHT_GRENZE``: eine Gruppe, die im Browser arbeitet, soll
#: nicht mehr schreiben koennen, als der Telegram-Weg tragen wuerde -- sonst
#: laesst sich ein Workshop nicht von einem Kanal in den anderen retten.
MAX_TEXT_ZEICHEN = 4000

_TEXT_FEHLER_LEER = "Da steht nichts."
_TEXT_FEHLER_LANG = "Das ist zu lang für eine Nachricht."
_TEXT_FEHLER_VERALTET = "Die Seite ist veraltet — bitte einmal neu laden."
_TEXT_FEHLER_ANFRAGE = "Ungültige Anfrage."


@contextmanager
def schreibend(db_pfad: str):
    """Eine schreibende Verbindung je Anfrage -- ``db.verbinde`` und nicht
    ``web_daten.oeffne_lesend``, wie im POST-Handler der Gruppenseite. WAL und
    ``busy_timeout`` (5 s) tragen das Nebeneinander mit den Bot-Prozessen; der
    modulweite ``repo._LOCK`` ist prozesslokal und richtet dagegen nichts aus
    (dieselbe Annahme wie ``scripts/begruessen.py``)."""
    conn = db.verbinde(db_pfad)
    try:
        yield conn
    finally:
        conn.close()


def _gruppe_oder_404(handler, db_pfad: str, token: str) -> int | None:
    """Die chat_id zum Token, oder 404 und None."""
    from interview_theater import web

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
    finally:
        conn.close()
    if chat_id is None:
        handler._antworte(404, web.nicht_gefunden_html())
    return chat_id


def _koerper_oder_400(handler, token: str, schluessel: bytes) -> dict | None:
    """JSON-Rumpf und Nonce in einem Griff. Reihenfolge wie in
    ``web._beantworte_post``: der Nonce kommt nach dem Token."""
    from interview_theater import web

    try:
        daten = handler._koerper()
    except ValueError as fehler:
        handler._fehler(400, str(fehler))
        return None
    if not web.nonce_gueltig(schluessel, token, daten.get("nonce")):
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return None
    return daten


def _angenommen(handler, nutzlast: dict) -> None:
    """**202, nicht 200:** der Bot hat noch nicht geantwortet, die Nachricht
    liegt im Eingang. Der Browser schaltet daraufhin auf einen schnellen Poll,
    statt auf eine Antwort in dieser Anfrage zu warten -- ein Gespraechszug
    dauert Sekunden, und eine HTTP-Verbindung so lange offen zu halten waere
    ein Thread je Nachricht."""
    handler._antworte(
        202, json.dumps(nutzlast, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None:
    """Alles, was der Browser schickt. Reihenfolge der Pruefungen:
    **Pfad, Token, Nonce, Wert** -- erst 404, dann 403, dann 400."""
    from interview_theater import web

    if unterpfad not in _POSTWEGE:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    chat_id = _gruppe_oder_404(handler, db_pfad, token)
    if chat_id is None:
        return
    try:
        _POSTWEGE[unterpfad](handler, db_pfad, token, chat_id, schluessel)
    except sqlite3.Error as fehler:
        handler.log_error("Datenbankfehler im Web-Chat: %s", fehler)
        handler._fehler(500, "Die Datenbank ist gerade nicht beschreibbar.")


def _senden(handler, db_pfad: str, token: str, chat_id: int,
            schluessel: bytes) -> None:
    """Eine Textnachricht der Gruppe.

    Der Text wird **nicht** gefiltert: gefiltert wird beim Lesen
    (``sichere_html``). Der Bot soll den Wortlaut sehen -- ein ``<`` in einer
    Nachricht ist ein Zeichen, keine Absicht."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    text = str(daten.get("text") or "").strip()
    if not text:
        handler._fehler(400, _TEXT_FEHLER_LEER)
        return
    if len(text) > MAX_TEXT_ZEICHEN:
        handler._fehler(400, _TEXT_FEHLER_LANG)
        return
    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text=text,
        )
    _angenommen(handler, {"message_id": message_id})


#: Die Tabelle der POST-Wege. Eine Tabelle statt einer if-Kette: ein neuer Weg
#: ist eine Zeile, und ``beantworte_post`` prueft Pfad, Token und Nonce fuer
#: alle gleich.
_POSTWEGE = {
    "senden": _senden,
}
```

Importe ergaenzen: `sqlite3`, `from contextlib import contextmanager`,
`from interview_theater import db, repo, web_daten`.

**Achtung Import-Richtung:** `web_chat` darf `repo` und `db` im Modulkopf importieren (beide
liegen unter ihm in der Schichtung). `web` bleibt ein lokaler Import in den Funktionen —
`web` importiert `web_chat`.

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_senden.py -q -p no:cacheprovider
```
Erwartet: `14 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2895 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_senden.py
git commit -m "Web-Chat: Text senden ueber den Nonce-Weg, 202 statt 200

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 8: Knopf druecken

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`knopf_erlaubt`, `_knopf`)
- Aendern: `interview_theater/web_daten.py` (`web_leiste`)
- Test: `tests/test_web_chat_knopf.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_daten.py
def web_leiste(conn, chat_id: int, message_id: int) -> list | None
    # None = die Nachricht gibt es nicht (oder nicht in dieser Gruppe)

# interview_theater/web_chat.py
def knopf_erlaubt(leiste, daten: str) -> bool
```

`POST /g/<token>/chat/knopf`, JSON `{"nonce", "message_id", "data"}` → **202** mit
`{"post_id": N}`, oder **400**, wenn `data` nicht in der aktuell haengenden Leiste **genau
dieser** `message_id` in **genau dieser** `chat_id` steht.

**Warum gegen die Leiste aus `web_post` und nicht gegen `knopf.message_id`** (Abweichung von
G mit Beleg): `repo.merke_knopf_nachricht` wird 22× gerufen, `_sende_knoepfe`/`_mit_leiste`
aber 47× — `knoepfe.biete_einstieg` (`knoepfe/interviews.py:343-383`) setzt
`knopf.message_id` nie. Eine Pruefung dagegen wuerde die Einstiegsknoepfe abweisen. Die
Leiste in `web_post.knoepfe` schreibt `WebKanal.sende_mit_knoepfen` selbst — sie **ist** per
Konstruktion „was gerade haengt".

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat_knopf.py`:

```python
"""Knopfdruck im Browser -- dieselbe Wirkung wie in Telegram.

Der Server prueft nur EINES: dass ``data`` wirklich in der Leiste steht, die
gerade unter dieser Nachricht in dieser Gruppe haengt. Die Wirkung macht
danach ``knoepfe.behandle`` im Bot-Prozess, unveraendert -- samt Idempotenz
ueber ``repo.beanspruche_knopf`` (Zusage 3). Es gibt hier keinen zweiten
Knopf-Handler.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, telegram, web, web_chat, web_daten, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)

    # Eine Leiste, wie sie der Bot ueber WebKanal hinlegt.
    kanal = web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)
    knopf_id = repo.lege_knopf_an(conn, CHAT, "speichern", "begriffe|Ankommen")
    message_id = kanal.sende_mit_knoepfen(
        CHAT, "Speichern?",
        [("Ja, speichern", f"k:{knopf_id}"), ("Nein, nochmal ändern", "k:999")],
    )
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad, message_id, f"k:{knopf_id}"
    dienst.shutdown()


def _post(url: str, koerper: dict):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


# -- die reine Pruefung ----------------------------------------------------


def test_knopf_erlaubt_nur_was_in_der_leiste_steht():
    leiste = [["Ja, speichern", "k:1"], ["Nein", "k:2"]]
    assert web_chat.knopf_erlaubt(leiste, "k:1") is True
    assert web_chat.knopf_erlaubt(leiste, "k:2") is True
    assert web_chat.knopf_erlaubt(leiste, "k:3") is False
    assert web_chat.knopf_erlaubt(leiste, "") is False
    assert web_chat.knopf_erlaubt(leiste, None) is False


def test_keine_leiste_erlaubt_nichts():
    assert web_chat.knopf_erlaubt([], "k:1") is False
    assert web_chat.knopf_erlaubt(None, "k:1") is False


def test_leiste_einer_fremden_gruppe_ist_none(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "A")
    repo.sichere_gruppe(conn, 7_000_000_000_002, "gruppe2", "B")
    message_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS,
                                       repo.WEB_TYP_TEXT, text="x",
                                       knoepfe=[("A", "k:1")])
    conn.commit()
    pfad = str(tmp_path / "t.db")
    conn.close()

    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_leiste(lesend, CHAT, message_id) == [["A", "k:1"]]
    assert web_daten.web_leiste(lesend, 7_000_000_000_002, message_id) is None
    assert web_daten.web_leiste(lesend, CHAT, 999_999) is None
    lesend.close()


# -- der Weg ueber HTTP ----------------------------------------------------


def test_ein_gueltiger_druck_legt_ein_callback_update_an(aufbau):
    basis, token, pfad, message_id, daten = aufbau
    status, text = _post(
        f"{basis}/g/{token}/chat/knopf",
        {"nonce": web.nonce(SCHLUESSEL, token), "message_id": message_id, "data": daten},
    )
    assert status == 202
    post_id = json.loads(text)["post_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, post_id)
    assert zeile["typ"] == repo.WEB_TYP_KNOPF
    assert zeile["daten"] == daten
    assert zeile["bezug_message_id"] == message_id

    # Und der Bot liest daraus einen Knopfdruck, keine Nachricht: ein
    # callback_query darf nie in ``nachricht`` landen, sonst liest ihn der
    # Erkenner als Gruppenbeitrag (AGENTS.md, die Weiche in bot.schleife).
    kanal = web_kanal.WebKanal(conn, CHAT, "/tmp/audio", schritt_s=0.01)
    update = kanal.hole_updates(post_id, timeout=0)[0]
    assert telegram.lies_nachricht(update) is None
    assert telegram.lies_knopfdruck(update)["data"] == daten


def test_fremde_daten_geben_400_und_legen_nichts_an(aufbau):
    basis, token, pfad, message_id, _daten = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": "k:4711"})
    assert fehler.value.code == 400
    conn = db.verbinde(pfad)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE typ = 'knopf'"
    ).fetchone()[0] == 0


def test_daten_unter_einer_anderen_nachricht_geben_400(aufbau):
    """Genau diese message_id -- nicht 'irgendwo im Chat'."""
    basis, token, pfad, message_id, daten = aufbau
    conn = db.verbinde(pfad)
    andere = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="ohne Leiste")
    conn.close()
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": andere, "data": daten})
    assert fehler.value.code == 400


def test_eine_abgenommene_leiste_wirkt_nicht_mehr(aufbau):
    """``entferne_knoepfe`` nimmt die Leiste weg, nachdem ein Knopf gewirkt
    hat. Danach darf derselbe Druck keinen zweiten Eingang erzeugen -- der
    Doppelklick wird schon hier abgefangen, und die Idempotenz ueber
    ``beanspruche_knopf`` bleibt die zweite Sperre dahinter."""
    basis, token, pfad, message_id, daten = aufbau
    conn = db.verbinde(pfad)
    repo.setze_web_knoepfe(conn, CHAT, message_id, None)
    conn.close()
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": daten})
    assert fehler.value.code == 400


def test_der_zweite_druck_bei_stehender_leiste_wird_angenommen(aufbau):
    """Solange die Leiste haengt, ist ein zweiter Druck ein zweiter Druck --
    und ``repo.beanspruche_knopf`` im Bot-Prozess entscheidet, dass er nicht
    wirkt (Zusage 3, bedingtes UPDATE). Der Server raet das nicht vorweg."""
    basis, token, _pfad, message_id, daten = aufbau
    koerper = {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": daten}
    assert _post(f"{basis}/g/{token}/chat/knopf", koerper)[0] == 202
    assert _post(f"{basis}/g/{token}/chat/knopf", koerper)[0] == 202


def test_message_id_ohne_zahl_gibt_400(aufbau):
    basis, token, _pfad, _message_id, daten = aufbau
    for kaputt in ("abc", None, -1, 0):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _post(f"{basis}/g/{token}/chat/knopf",
                  {"nonce": web.nonce(SCHLUESSEL, token),
                   "message_id": kaputt, "data": daten})
        assert fehler.value.code == 400


def test_ohne_nonce_gibt_es_403(aufbau):
    basis, token, _pfad, message_id, daten = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"message_id": message_id, "data": daten})
    assert fehler.value.code == 403


def test_die_leiste_steht_im_html_als_knoepfe(aufbau):
    basis, token, _pfad, message_id, daten = aufbau
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    assert f'data-message="{message_id}"' in text
    assert f'data-daten="{daten}"' in text
    assert "Ja, speichern" in text


def test_kein_neuer_knopf_handler_im_web(aufbau):
    """Die Wirkung eines Knopfes steht an genau einer Stelle:
    ``knoepfe/wirkung.py``. ``web_chat`` legt nur ein Update an."""
    from pathlib import Path

    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert "beanspruche_knopf" not in quelle
    assert "_WIRKUNGEN" not in quelle
    assert "knoepfe" not in quelle.replace("knoepfe\"", "").replace(
        "knoepfe'", "").replace("web_knoepfe", "").replace(
        "setze_web_knoepfe", "").replace("_knoepfe", "")
```

Der letzte Test ist sproede formuliert. **Besser** so:

```python
def test_kein_neuer_knopf_handler_im_web():
    """Die Wirkung eines Knopfes steht an genau einer Stelle:
    ``knoepfe/wirkung.py``. ``web_chat`` legt nur ein Update an -- es
    importiert das Knopf-Paket nicht und beansprucht keinen Knopf."""
    from pathlib import Path

    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert "beanspruche_knopf" not in quelle
    assert "import knoepfe" not in quelle
    assert "from interview_theater.knoepfe" not in quelle
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_knopf.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.web_chat' has no attribute 'knopf_erlaubt'`.

- [x] **Schritt 3: `web_daten.web_leiste`**

```python
def web_leiste(conn, chat_id: int, message_id: int) -> list | None:
    """Die Leiste, die gerade unter dieser Nachricht in DIESER Gruppe haengt --
    oder None, wenn es die Nachricht nicht gibt.

    Unterschied zwischen ``None`` und ``[]``: die Nachricht gibt es nicht
    gegen die Nachricht hat keine Knoepfe (mehr). Der Aufrufer antwortet auf
    beides mit 400, aber im Log soll der Unterschied stehen.

    ``chat_id`` in der Bedingung: dieselbe Datenbank traegt alle Gruppen des
    Workshops, und ein weitergegebener Link darf nie in fremde Daten
    schreiben (dieselbe Regel wie ``knoepfe.behandle``)."""
    zeile = conn.execute(
        "SELECT knoepfe FROM web_post WHERE id = ? AND chat_id = ? "
        "AND richtung = 'aus' AND geloescht_am IS NULL",
        (message_id, chat_id),
    ).fetchone()
    if zeile is None:
        return None
    return _web_knoepfe(zeile["knoepfe"])
```

- [x] **Schritt 4: `web_chat.py` — Pruefung und Handler**

```python
_TEXT_FEHLER_KNOPF = "Diesen Knopf kenne ich hier nicht mehr — bitte neu laden."


def knopf_erlaubt(leiste, daten) -> bool:
    """Steht ``daten`` in dieser Leiste?

    **Die eine Pruefung des Knopfwegs.** Geprueft wird gegen die Leiste aus
    ``web_post`` und NICHT gegen ``knopf.message_id``: die ist nur gesetzt,
    wenn ein Aufrufer ``repo.merke_knopf_nachricht`` ruft, und das tun 22 von
    47 Sendestellen -- ``knoepfe.biete_einstieg`` zum Beispiel nicht. Eine
    Pruefung dagegen wuerde die Einstiegsknoepfe abweisen. Die Leiste in
    ``web_post`` schreibt ``WebKanal.sende_mit_knoepfen`` selbst; sie IST per
    Konstruktion, was gerade haengt.

    Ohne diese Pruefung waere jeder Knopf jeder Gruppe per ``curl``
    drueckbar, sobald jemand einen Link hat -- und die ``k:<id>`` sind
    fortlaufende Zahlen."""
    if not leiste or not isinstance(daten, str) or not daten:
        return False
    return any(daten == eintrag[1] for eintrag in leiste)


def _knopf(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Ein Knopfdruck der Gruppe.

    Der Server stellt **nur** fest, dass der Knopf hier steht, und legt dann
    ein ``callback_query``-Update an. Die Wirkung macht ``knoepfe.behandle``
    im Bot-Prozess -- unveraendert, samt Idempotenz ueber
    ``repo.beanspruche_knopf`` (Zusage 3: der zweite Druck wird beantwortet,
    wirkt aber nicht). Es gibt hier keinen zweiten Knopf-Handler und keinen
    Modellaufruf (Zusage 2)."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    roh_id = daten.get("message_id")
    if not isinstance(roh_id, int) or isinstance(roh_id, bool) or roh_id < 1:
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return
    wert = daten.get("data")

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        leiste = web_daten.web_leiste(conn, chat_id, roh_id)
    finally:
        conn.close()
    if not knopf_erlaubt(leiste, wert):
        handler.log_error(
            "Knopfdruck abgewiesen: chat_id=%s message_id=%s leiste=%s",
            chat_id, roh_id, "fehlt" if leiste is None else len(leiste),
        )
        handler._fehler(400, _TEXT_FEHLER_KNOPF)
        return

    with schreibend(db_pfad) as schreiber:
        post_id = repo.lege_web_post_an(
            schreiber, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF,
            daten=wert, bezug_message_id=roh_id,
        )
    _angenommen(handler, {"post_id": post_id})
```

`_POSTWEGE` um `"knopf": _knopf` ergaenzen.

- [x] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_knopf.py -q -p no:cacheprovider
```
Erwartet: `13 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2908 passed, 1 skipped`.

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/web_chat.py interview_theater/web_daten.py \
        tests/test_web_chat_knopf.py
git commit -m "Web-Chat: Knopfdruck gegen die haengende Leiste geprueft, Wirkung bleibt in knoepfe/

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 9: Audio-Upload

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`endung_fuer`, `_audio`)
- Test: `tests/test_web_chat_audio.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_chat.py
MIME_ERLAUBT = {"audio/webm": ".webm", "audio/ogg": ".ogg",
                "audio/mp4": ".m4a", "audio/mpeg": ".mp3"}
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_DAUER_S = 3600
def endung_fuer(content_type) -> str | None
```

`POST /g/<token>/chat/audio?nonce=…&dauer=<sekunden>` mit **rohem Koerper** und
`Content-Type: audio/…` → **202** mit `{"message_id": N}`.

**Warum roher Koerper und nicht multipart:** die Standardbibliothek hat keinen
Multipart-Parser, den man verantworten will (`cgi.FieldStorage` ist in 3.13 entfernt), und
MediaRecorder liefert genau einen Blob. Der Nonce steht deshalb in der Query. Er ist ein
CSRF-Merkmal und kein Geheimnis ueber die Seite hinaus; das Token steht ohnehin schon im Pfad
und damit auch schon in jeder Logzeile (`web._Basishandler.log_message`).

**Die Groessengrenze, begruendet:** Opus bei 32 kbit/s macht 45 s ≈ 180 KiB, Safaris
mp4/AAC bei 64 kbit/s ≈ 360 KiB. **8 MiB** sind gut zwanzigfache Luft fuer einen Browser,
der eine hohe Bitrate waehlt, und bleiben klar unter `stt.MAX_UPLOAD_BYTES` (25 MiB) — eine
Datei, die Whisper ohnehin ablehnen wuerde, soll gar nicht erst ankommen.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat_audio.py`:

```python
"""Audio-Upload aus dem Browser -- roher Koerper, Allowlist, Groessengrenze.

Die Endung entscheidet ueber den MIME-Typ, den Whisper sieht (Falle 3):
ein WebM als .ogg abgelegt laesst den Auftrag dauerhaft auf 'pending' stehen,
89,7 s statt 2,0 s, im Betrieb nur als "haengt" sichtbar. Deshalb ist die
Allowlist Content-Type -> Endung und nicht Content-Type -> "erlaubt ja/nein".
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, stt, telegram, web, web_chat, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
#: EBML-Kopf -- so faengt eine WebM-Datei aus MediaRecorder an.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad, tmp_path / "audio"
    dienst.shutdown()


def _lade(basis, token, koerper: bytes, typ="audio/webm", dauer=45, nonce=None):
    kennung = nonce if nonce is not None else web.nonce(SCHLUESSEL, token)
    url = f"{basis}/g/{token}/chat/audio?nonce={kennung}&dauer={dauer}"
    anfrage = urllib.request.Request(
        url, data=koerper, headers={"Content-Type": typ}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


# -- die Allowlist ---------------------------------------------------------


@pytest.mark.parametrize("typ,endung", [
    ("audio/webm", ".webm"),
    ("audio/webm;codecs=opus", ".webm"),
    ("audio/webm; codecs=\"opus\"", ".webm"),
    ("AUDIO/WEBM", ".webm"),
    ("audio/ogg", ".ogg"),
    ("audio/ogg;codecs=opus", ".ogg"),
    ("audio/mp4", ".m4a"),
    ("audio/mp4;codecs=mp4a.40.2", ".m4a"),
    ("audio/mpeg", ".mp3"),
])
def test_erlaubte_typen_geben_eine_endung(typ, endung):
    assert web_chat.endung_fuer(typ) == endung


@pytest.mark.parametrize("typ", [
    None, "", "text/html", "application/octet-stream", "video/mp4",
    "audio/x-wav", "audio/flac", "audio/webm/../../etc",
])
def test_alles_andere_gibt_none(typ):
    assert web_chat.endung_fuer(typ) is None


def test_jede_endung_der_allowlist_ist_stt_bekannt():
    """Die Allowlist waere nutzlos, wenn ``stt.mime_typ`` die Endung nicht
    kennt: dann raet ``mimetypes.guess_type``, und im schlechten Fall kommt
    ``application/octet-stream`` bei Whisper an."""
    for typ, endung in web_chat.MIME_ERLAUBT.items():
        gemessen = stt.mime_typ(Path(f"x{endung}"))
        assert gemessen == typ.split(";")[0], (endung, gemessen, typ)


# -- der Weg ueber HTTP ----------------------------------------------------


def test_ein_segment_landet_als_sprachnachricht(aufbau):
    basis, token, pfad, audio = aufbau
    status, text = _lade(basis, token, WEBM)
    assert status == 202
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["typ"] == repo.WEB_TYP_SPRACHE
    assert zeile["dauer"] == 45
    assert zeile["mime"] == "audio/webm"

    datei = Path(zeile["datei"])
    assert datei.read_bytes() == WEBM
    assert datei.suffix == ".webm"
    assert web_kanal.EINGANG_VERZ in datei.parts
    assert str(CHAT) in datei.parts


def test_der_bot_sieht_daraus_eine_sprachnachricht_mit_endung(aufbau):
    basis, token, pfad, audio = aufbau
    _status, text = _lade(basis, token, WEBM)
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    kanal = web_kanal.WebKanal(conn, CHAT, str(audio), schritt_s=0.01)
    gedeutet = telegram.lies_nachricht(kanal.hole_updates(message_id, timeout=0)[0])
    assert gedeutet["typ"] == "sprache"
    assert gedeutet["endung"] == ".webm"
    assert gedeutet["dauer"] == 45
    # Und der Weg zurueck: lade_datei findet die Datei wieder.
    ziel = audio / str(CHAT) / f"{message_id}.webm"
    kanal.lade_datei(gedeutet["file_id"], ziel)
    assert ziel.read_bytes() == WEBM


def test_fremder_typ_gibt_415(aufbau):
    basis, token, pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"<html>", typ="text/html")
    assert fehler.value.code == 415
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_zu_grosses_segment_gibt_413(aufbau):
    basis, token, pfad, audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"\x00" * (web_chat.MAX_AUDIO_BYTES + 1))
    assert fehler.value.code == 413
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    # Und keine halbe Datei bleibt liegen.
    assert list(audio.rglob("*.webm")) == []


def test_leerer_koerper_gibt_400(aufbau):
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"")
    assert fehler.value.code == 400


def test_ohne_nonce_gibt_403_und_speichert_nichts(aufbau):
    basis, token, pfad, audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, WEBM, nonce="0.deadbeef")
    assert fehler.value.code == 403
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    assert list(audio.rglob("*")) == [] or not any(
        p.is_file() for p in audio.rglob("*")
    )


def test_unbekanntes_token_gibt_404(aufbau):
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        anfrage = urllib.request.Request(
            f"{basis}/g/gibtsnicht/chat/audio?nonce={web.nonce(SCHLUESSEL, token)}&dauer=5",
            data=WEBM, headers={"Content-Type": "audio/webm"}, method="POST",
        )
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


@pytest.mark.parametrize("dauer", ["", "abc", "-3", "99999999"])
def test_kaputte_dauer_gibt_400(aufbau, dauer):
    """Die Dauer kommt vom Client und geht in ``aufnahme`` -- sie entscheidet
    unter anderem ueber ``HINWEIS_AB_S`` (60 s: eine lange Sprachnachricht
    ohne Interviewmodus wird gefragt, nicht gedeutet). Eine geratene Dauer
    waere dort eine geratene Entscheidung."""
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, WEBM, dauer=dauer)
    assert fehler.value.code == 400


def test_zwei_segmente_bekommen_zwei_dateien(aufbau):
    basis, token, pfad, audio = aufbau
    erste = json.loads(_lade(basis, token, WEBM)[1])["message_id"]
    zweite = json.loads(_lade(basis, token, WEBM + b"zwei")[1])["message_id"]
    assert erste != zweite

    conn = db.verbinde(pfad)
    pfade = {
        Path(repo.hole_web_post(conn, mid)["datei"]) for mid in (erste, zweite)
    }
    assert len(pfade) == 2
    assert all(p.exists() for p in pfade)


def test_eine_sprachnachricht_steht_im_verlauf_ohne_dateipfad(aufbau):
    basis, token, _pfad, _audio = aufbau
    _lade(basis, token, WEBM)
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert zustand["nachrichten"][0]["typ"] == "sprache"
    assert zustand["nachrichten"][0]["dauer"] == 45
    assert "datei" not in zustand["nachrichten"][0]


def test_das_json_post_limit_gilt_fuer_audio_nicht(aufbau):
    """``web.MAX_POST_BYTES`` (64 KiB) deckelt den JSON-Rumpf der
    Gruppenseite. Ein Audiosegment ist ein Vielfaches davon und laeuft
    deshalb NICHT durch ``handler._koerper``."""
    basis, token, _pfad, _audio = aufbau
    gross = b"\x1a\x45\xdf\xa3" + b"\x00" * (200 * 1024)
    assert len(gross) > web.MAX_POST_BYTES
    assert _lade(basis, token, gross)[0] == 202
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_audio.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: … has no attribute 'endung_fuer'`.

- [x] **Schritt 3: `web_chat.py` — Allowlist und Handler**

```python
#: Was der Browser liefern darf, und mit welcher Endung es abgelegt wird.
#:
#: **Content-Type -> ENDUNG und nicht Content-Type -> ja/nein**, und das ist
#: Falle 3: ``stt.mime_typ()`` leitet den MIME-Typ, den Whisper sieht, aus der
#: Dateiendung ab. Ein WebM als ``.ogg`` abgelegt wird von Infomaniak mit
#: einer ``batch_id`` quittiert -- kein HTTP-Fehler -- und bleibt danach
#: dauerhaft auf 'pending': 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
#: sichtbar.
#:
#: Chrome und Firefox liefern ``audio/webm;codecs=opus``, Safari
#: ``audio/mp4``. ``audio/ogg`` und ``audio/mpeg`` stehen daneben, weil ein
#: Browser sie waehlen darf und beide bei Whisper unstrittig sind.
MIME_ERLAUBT = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}

#: Wie gross ein einzelnes Segment sein darf.
#:
#: Gerechnet, nicht geraten: Opus bei 32 kbit/s ergibt fuer 45 s rund
#: 180 KiB, Safaris mp4/AAC bei 64 kbit/s rund 360 KiB. 8 MiB sind gut
#: zwanzigfache Luft fuer einen Browser, der eine hohe Bitrate waehlt -- und
#: sie liegen klar unter ``stt.MAX_UPLOAD_BYTES`` (25 MiB): eine Datei, die
#: Whisper ohnehin ablehnen wuerde, soll gar nicht erst ankommen.
MAX_AUDIO_BYTES = 8 * 1024 * 1024

#: Obergrenze der vom Client gemeldeten Dauer (eine Stunde). Die Dauer
#: entscheidet mit ueber ``aufnahme.HINWEIS_AB_S`` (60 s: eine lange
#: Sprachnachricht ohne Interviewmodus wird gefragt, nicht gedeutet) -- eine
#: geratene Dauer waere dort eine geratene Entscheidung.
MAX_DAUER_S = 3600

_TEXT_FEHLER_TYP = "Dieses Audioformat kann ich nicht annehmen."
_TEXT_FEHLER_GROSS = "Die Aufnahme ist zu groß — bitte in kürzeren Stücken."
_TEXT_FEHLER_LEER_AUDIO = "Die Aufnahme ist leer angekommen."
_TEXT_FEHLER_DAUER = "Ungültige Aufnahmedauer."


def endung_fuer(content_type) -> str | None:
    """Die Endung zu einem Content-Type, oder None.

    Parameter werden abgeschnitten (``audio/webm;codecs=opus``), gross und
    klein ist gleich. Eine **Allowlist** und keine Ablehnliste: was hier nicht
    steht, kommt nicht an."""
    if not isinstance(content_type, str) or not content_type.strip():
        return None
    haupt = content_type.split(";", 1)[0].strip().lower()
    return MIME_ERLAUBT.get(haupt)


def _audio(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Ein Aufnahmesegment aus dem Browser.

    **Roher Koerper, kein multipart:** die Standardbibliothek hat keinen
    Multipart-Parser, den man verantworten will (``cgi.FieldStorage`` ist in
    Python 3.13 entfernt), und MediaRecorder liefert genau einen Blob. Der
    Nonce steht deshalb in der Query -- er ist ein CSRF-Merkmal, kein
    Geheimnis ueber die Seite hinaus, und das Token steht ohnehin schon im
    Pfad und damit in jeder Logzeile.

    Reihenfolge der Pruefungen: **Typ, Groesse, Dauer, Nonce, dann lesen** --
    die Kopfzeilen kosten nichts, der Koerper kostet Speicher. Geschrieben
    wird erst die Zeile, dann die Datei (der Pfad enthaelt die id), und erst
    danach der Verweis; scheitert die Datei, bleibt eine Zeile ohne ``datei``
    stehen und ``lade_datei`` wirft -- ``aufnahme`` bittet die Gruppe dann,
    es nochmal zu schicken."""
    from interview_theater import web

    endung = endung_fuer(handler.headers.get("Content-Type"))
    if endung is None:
        handler._fehler(415, _TEXT_FEHLER_TYP)
        return
    try:
        laenge = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return
    if laenge <= 0:
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return
    if laenge > MAX_AUDIO_BYTES:
        handler._fehler(413, _TEXT_FEHLER_GROSS)
        return

    felder = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    if not web.nonce_gueltig(schluessel, token, (felder.get("nonce") or [""])[0]):
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return
    roh_dauer = (felder.get("dauer") or [""])[0]
    if not roh_dauer.isdigit() or not 0 < int(roh_dauer) <= MAX_DAUER_S:
        handler._fehler(400, _TEXT_FEHLER_DAUER)
        return

    koerper = handler.rfile.read(laenge)
    if len(koerper) != laenge:
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return

    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
            dauer=int(roh_dauer), mime=haupttyp(handler),
        )
        ziel = web_kanal.eingangspfad(_audio_verz(), chat_id, message_id, endung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(koerper)
        repo.setze_web_datei(conn, message_id, str(ziel))
    _angenommen(handler, {"message_id": message_id})


def haupttyp(handler) -> str:
    """Der Haupt-MIME-Typ der Anfrage, fuer die Spalte ``mime`` -- ohne
    Parameter (``audio/webm;codecs=opus`` -> ``audio/webm``)."""
    roh = handler.headers.get("Content-Type") or ""
    return roh.split(";", 1)[0].strip().lower()


def _audio_verz() -> str:
    """``IT_AUDIO`` wie ``einstellungen._VORGABEWERTE`` -- der Webserver laedt
    keine ``Einstellungen`` (er braucht weder LLM- noch STT-Variablen), liest
    aber dieselbe Variable mit demselben Vorgabewert."""
    return os.environ.get("IT_AUDIO") or "audio"
```

`_POSTWEGE` um `"audio": _audio` ergaenzen, `from interview_theater import web_kanal`
im Modulkopf.

**Hinweis zur Schichtung:** `web_chat` importiert `web_kanal` nur fuer `eingangspfad` und
`EINGANG_VERZ` — beides reine Pfadlogik ohne Datenbank. Das ist gewollt: der Ort einer Datei
soll an genau einer Stelle stehen, damit `lade_datei` und der Upload nie auseinanderlaufen.

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_audio.py -q -p no:cacheprovider
```
Erwartet: `31 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2939 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_audio.py
git commit -m "Web-Chat: Audio-Upload mit Allowlist und Endung fuer stt.mime_typ

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 10: Interview-Umschalter serverseitig

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`_interview`)
- Test: `tests/test_web_chat_interview.py` (neu)

`POST /g/<token>/chat/interview`, JSON `{"nonce", "an": true|false}` → **202** mit
`{"message_id": N}`.

**Entscheidung I, woertlich umgesetzt:** der Umschalter nutzt die vorhandenen Befehlswege
`/interview` bzw. `/fertig`. Beide sind deterministisch (`befehle._befehl_interview`,
`_befehl_fertig`, kein Modell im Handler), und beide schalten `gruppe.interviewmodus_seit` —
woran nach `aufnahme.klasse_fuer` (aufnahme.py:208) **allein** haengt, ob eine
Sprachnachricht `teil` eines Interviews oder `kurz` ist. **Keine zweite Moduslogik.**

Der Post landet als `typ='befehl'` in `web_post` — im Update ist es eine gewoehnliche
Textnachricht (`befehle.behandle` faengt sie ab wie einen getippten Befehl), in der
Chatansicht ist die Zeile verborgen: Slash-Befehle werden nicht beworben.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat_interview.py`:

```python
"""Der Interview-Umschalter -- ueber /interview und /fertig, nicht daneben.

Birk, 30.09.2026: "einmal tippen = Aufnahme laeuft, erneut tippen = Stopp."
Die Klasse einer Aufnahme haengt NUR am Modus (aufnahme.klasse_fuer,
aufnahme.py:208) -- also schaltet der Umschalter den Modus, und zwar auf dem
Weg, den es schon gibt. Eine zweite Moduslogik waere eine zweite Wahrheit.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import befehle, db, repo, telegram, web, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(basis, token, koerper):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/interview",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), **koerper}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, json.loads(antwort.read().decode("utf-8"))


def test_an_schickt_den_interview_befehl(aufbau):
    basis, token, pfad = aufbau
    status, antwort = _post(basis, token, {"an": True})
    assert status == 202

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, antwort["message_id"])
    assert zeile["typ"] == repo.WEB_TYP_BEFEHL
    assert zeile["text"] == "/interview"


def test_aus_schickt_fertig(aufbau):
    basis, token, pfad = aufbau
    _status, antwort = _post(basis, token, {"an": False})
    conn = db.verbinde(pfad)
    assert repo.hole_web_post(conn, antwort["message_id"])["text"] == "/fertig"


def test_beide_befehle_sind_dem_bot_bekannt():
    """Wenn einer umbenannt wird, soll es hier auffallen und nicht im
    Browser."""
    assert "/interview" in befehle._BEKANNTE_BEFEHLE
    assert "/fertig" in befehle._BEKANNTE_BEFEHLE


def test_der_bot_liest_daraus_eine_gewoehnliche_textnachricht(aufbau):
    """``befehle.behandle`` faengt Slash-Text ab, bevor ein Kontext gebaut
    wird. Der Weg ist damit derselbe wie bei einem getippten ``/interview``."""
    basis, token, pfad = aufbau
    _status, antwort = _post(basis, token, {"an": True})
    conn = db.verbinde(pfad)
    kanal = web_kanal.WebKanal(conn, CHAT, "/tmp/audio", schritt_s=0.01)
    gedeutet = telegram.lies_nachricht(
        kanal.hole_updates(antwort["message_id"], timeout=0)[0]
    )
    assert gedeutet["typ"] == "text"
    assert gedeutet["text"] == "/interview"


def test_der_umschalter_steht_nicht_im_chatverlauf(aufbau):
    """Slash-Befehle werden nicht beworben (AGENTS.md) -- der Knopf steht
    schon da, sein Slash-Text gehoert nicht in die Blase."""
    basis, token, _pfad = aufbau
    _post(basis, token, {"an": True})
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert zustand["nachrichten"] == []


def test_der_zustand_meldet_den_modus_aus_der_datenbank(aufbau):
    """Seitenwechsel oder Neuladen bei laufendem Interview: der Knopf muss
    danach den Modus aus der DB zeigen und nicht aus dem Arbeitsspeicher des
    Browsers (Birk, Punkt 1: "Zustand unmissverstaendlich")."""
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.setze_interviewmodus(conn, CHAT, repo._jetzt())
    conn.close()

    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        assert json.loads(antwort.read().decode("utf-8"))["interviewmodus"] is True
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        assert 'data-interview="1"' in antwort.read().decode("utf-8")


@pytest.mark.parametrize("kaputt", [{}, {"an": "ja"}, {"an": 1}, {"an": None}])
def test_an_muss_ein_boolescher_wert_sein(aufbau, kaputt):
    """``repo.setze_szene_usa`` nimmt einen bool, und ein nicht-leerer String
    ist wahr -- ein "nein" wuerde dort als Zustimmung enden (AGENTS.md,
    Fallstrick). Dieselbe Strenge hier: der Umschalter raet nicht."""
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, kaputt)
    assert fehler.value.code == 400


def test_ohne_nonce_gibt_403(aufbau):
    basis, token, _pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/interview",
        data=json.dumps({"an": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 403


def test_kein_modellaufruf_und_keine_zweite_moduslogik():
    """``web_chat`` schaltet den Modus nicht selbst: es schickt den Befehl.
    Damit gilt Zusage 2 (kein Modell im Handler) und es gibt nur einen Ort,
    an dem ``interviewmodus_seit`` gesetzt wird."""
    from pathlib import Path

    from interview_theater import web_chat

    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert "setze_interviewmodus" not in quelle
    assert "stelle_interview_sicher" not in quelle
    assert "beende_interview" not in quelle
    assert "import llm" not in quelle
    assert "import stt" not in quelle
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_interview.py -q -p no:cacheprovider
```
Erwartet: FAIL — 404 fuer den Unterpfad `interview`.

- [x] **Schritt 3: `web_chat.py` — der Umschalter**

```python
#: Die zwei Befehle, die der Umschalter schickt. Woertlich die aus
#: ``befehle._BEKANNTE_BEFEHLE``: der Weg in den Interviewmodus ist
#: deterministisch und existiert schon (``befehle._befehl_interview`` /
#: ``_befehl_fertig``), und die Klasse einer Aufnahme haengt NUR am Modus
#: (``aufnahme.klasse_fuer``). Eine zweite Moduslogik hier waere eine zweite
#: Wahrheit -- und die eine, die dann irgendwann falsch ist.
BEFEHL_INTERVIEW_AN = "/interview"
BEFEHL_INTERVIEW_AUS = "/fertig"


def _interview(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None:
    """Der Interview-Umschalter (Birk, 30.09.2026, Punkt 1).

    Schickt ``/interview`` bzw. ``/fertig`` als Eingang. Der Bot faengt den
    Slash-Text in ``befehle.behandle`` ab, **bevor** ein Kontext gebaut oder
    ein Modell gerufen wird -- derselbe Weg wie bei einem getippten Befehl.

    In der Chatansicht bleibt die Zeile verborgen (``typ='befehl'``):
    Slash-Befehle werden nicht beworben (AGENTS.md), der Knopf steht schon da.

    ``an`` muss ein echter boolescher Wert sein. Der Fallstrick daneben ist
    dokumentiert: ``repo.setze_szene_usa`` nimmt einen bool, und ein
    nicht-leerer String ist wahr -- ein ``"nein"`` endete dort als
    Zustimmung. Hier wird deshalb nicht geraten."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    an = daten.get("an")
    if not isinstance(an, bool):
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return
    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
            text=BEFEHL_INTERVIEW_AN if an else BEFEHL_INTERVIEW_AUS,
        )
    _angenommen(handler, {"message_id": message_id})
```

`_POSTWEGE` um `"interview": _interview` ergaenzen.

**Wichtig fuer `WebKanal._update`:** `WEB_TYP_BEFEHL` wird dort wie `WEB_TYP_TEXT`
behandelt — das `else` im bestehenden Code trifft ihn schon, weil nur `WEB_TYP_KNOPF` und
`WEB_TYP_SPRACHE` eigene Zweige haben. Im Test `test_der_bot_liest_daraus_eine_gewoehnliche_textnachricht`
wird das festgehalten.

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_interview.py -q -p no:cacheprovider
```
Erwartet: `12 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2951 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_interview.py
git commit -m "Web-Chat: Interview-Umschalter ueber /interview und /fertig, keine zweite Moduslogik

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 11: Das Browser-JavaScript — Poll, Recorder, Segmente, PTT

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`_CHAT_JS`)
- Test: `tests/test_web_chat_js.py` (neu — der Server**vertrag** des JS, ohne Browser)

Der Browserlauf selbst ist Aufgabe 13. Hier wird geprueft, was **ohne** Browser pruefbar
ist: dass die Seite die Werte traegt, die das JS braucht, dass die Zahlen an einer Stelle
stehen, und dass das JS auf genau die Endpunkte zielt, die es gibt.

**Die zwei Audio-Wege nebeneinander** (Birk, 30.09.2026 — verbindlich):

| | 1. Interview-Aufnahme | 2. Push-to-Talk |
|---|---|---|
| Bedienung | tippen = laeuft, erneut tippen = Stopp | halten = sprechen, loslassen = senden |
| Kein Schieben-zum-Sperren | — | — |
| Modus | schaltet `/interview` … `/fertig` | schaltet nichts, Klasse `kurz` |
| Segmente | alle `IT_WEB_SEGMENT_MS` (45 s) ein eigener Recorder-Lauf | genau einer |
| Abbruch | — | `pointercancel` / Wegziehen sendet **nichts**; unter 500 ms verworfen |
| Sichtbar | Timer, Pegel, grosser Stopp-Knopf | gedrueckter Knopf |
| Wann sichtbar | immer | **ausgeblendet**, solange eine Interview-Aufnahme laeuft |

**Warum jedes Segment ein eigener Recorder-Lauf ist** (Entscheidung I): MediaRecorder-
Zeitscheiben (`start(timeslice)`) sind einzeln **nicht dekodierbar** — nur das erste Stueck
traegt den Container-Kopf. Whisper bekaeme ab dem zweiten Segment Bytes ohne Kopf. Also
`stop()` + `start()` alle 45 s; jedes `ondataavailable` liefert damit eine vollstaendige
Datei.

**Der Wettlauf und seine Loesung** (Entscheidung I): die Aufnahme startet **sofort** (sonst
verliert man die ersten Worte), der Upload des ersten Segments wartet aber in der
Warteschlange, bis der Zustands-Poll `interviewmodus: true` meldet. Sonst kaeme das Segment
vor dem `/interview` an, und `aufnahme.klasse_fuer` machte daraus eine `kurz`-Aufnahme statt
eines Interview-Teils. Beim Stopp umgekehrt: erst alle Uploads bestaetigt, dann `/fertig` —
sonst verdichtet der Bot ein Interview, dem das letzte Segment fehlt.

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_chat_js.py`:

```python
"""Der Serververtrag des Chat-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_chat_e2e.py``: der
Recorder, die Segmente, PTT, die Warteschlange. Hier steht, was man am HTML
messen kann -- und das ist mehr, als es klingt: jede Zahl, die das JS braucht,
und jeder Endpunkt, den es ruft.
"""

import re
import threading
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def seite(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", "1200")

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        html = antwort.read().decode("utf-8")
    dienst.shutdown()
    return html


def test_die_bedienelemente_stehen_da(seite):
    for kennung in ("verlauf", "eingabe", "senden", "ptt", "interview",
                    "uhr", "pegel", "warteschlange", "nonce", "tippt", "fuss"):
        assert f'id="{kennung}"' in seite, kennung


def test_die_segmentlaenge_kommt_aus_der_umgebung(seite):
    """Der Browsertest verkuerzt sie per Parameter -- 45 Sekunden je Segment
    wuerden einen Testlauf nutzlos lang machen."""
    assert 'data-segment-ms="1200"' in seite


def test_der_nonce_steht_im_body_und_nicht_daran(seite):
    """Dieselbe Entscheidung wie auf der Gruppenseite (``web.nonce``):
    abgeleitet, nicht gewuerfelt, und IM body -- sonst reisst ein
    Fensterwechsel jedes offene Eingabefeld mit."""
    assert re.search(r'<input type="hidden" id="nonce" value="\d+\.[0-9a-f]{32}">', seite)


def test_das_js_ruft_nur_endpunkte_die_es_gibt(seite):
    """Jeder ``fetch``-Pfad im JS muss in ``_POSTWEGE`` oder unter den
    GET-Wegen stehen. Ein Tippfehler waere im Browser ein stilles 404."""
    pfade = set(re.findall(r"chat/([a-z]+)", web_chat._CHAT_JS))
    erlaubt = set(web_chat._POSTWEGE) | {"zustand", "datei"}
    assert pfade <= erlaubt, pfade - erlaubt


def test_das_js_nennt_jeden_postweg(seite):
    """Die andere Richtung: ein Endpunkt ohne Aufrufer im JS ist entweder
    toter Code oder ein vergessener Knopf."""
    for weg in web_chat._POSTWEGE:
        assert f"chat/{weg}" in web_chat._CHAT_JS, weg


def test_die_ptt_mindestdauer_steht_genau_einmal_im_code():
    """Birks Vorgabe: unter ~0,5 s wird verworfen. Eine Zahl, zwei Orte -- und
    beim naechsten Mal stimmt einer davon nicht."""
    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert quelle.count(str(web_chat.PTT_MIN_MS)) >= 1
    assert f"PTT_MIN_MS" in web_chat._CHAT_JS or (
        f"data-ptt-min=" in quelle
    )


def test_pointercancel_und_setpointercapture_stehen_im_js():
    """Birks Vorgabe woertlich: Pointer Events + setPointerCapture, Abbruch
    bei Wegziehen/pointercancel sendet NICHTS."""
    for baustein in ("setPointerCapture", "pointercancel", "pointerdown",
                     "pointerup", "releasePointerCapture"):
        assert baustein in web_chat._CHAT_JS, baustein


def test_kein_schieben_zum_sperren(seite):
    """Birk, verbindlich: ZWEI getrennte Knoepfe, KEIN Schieben-zum-Sperren.
    Ein Test, der eine Entscheidung festhaelt, die sonst niemand mehr kennt."""
    for verboten in ("slideToLock", "sperren", "lock", "swipe"):
        assert verboten.lower() not in web_chat._CHAT_JS.lower(), verboten


def test_das_js_startet_einen_eigenen_recorder_je_segment():
    """MediaRecorder-Zeitscheiben sind einzeln nicht dekodierbar: nur das
    erste Stueck traegt den Container-Kopf. Also stop() + start() je Segment,
    NICHT start(timeslice)."""
    assert "new MediaRecorder" in web_chat._CHAT_JS
    assert re.search(r"\.start\(\s*\)", web_chat._CHAT_JS)
    assert not re.search(r"\.start\(\s*[A-Za-z0-9_]+\s*\)", web_chat._CHAT_JS)


def test_das_js_wartet_auf_den_interviewmodus_vor_dem_ersten_upload():
    """Der Wettlauf: die Aufnahme startet sofort, der Upload wartet bis
    ``interviewmodus: true``. Sonst kaeme das erste Segment vor dem
    ``/interview`` an, und ``aufnahme.klasse_fuer`` machte daraus eine
    kurz-Aufnahme statt eines Interview-Teils."""
    assert "interviewmodus" in web_chat._CHAT_JS


def test_das_js_laedt_ohne_nachladen_der_ganzen_seite(seite):
    """``web._seite(..., nachladen=False)``: das sanfte Nachladen tauscht den
    ``<body>`` aus, und mitten in einer Aufnahme riss das Recorder, Timer und
    Warteschlange mit."""
    assert "__NEULADEN_MS__" not in seite
    assert "location.reload" not in seite


def test_die_polltakte_stehen_als_konstanten():
    assert web_chat.POLL_MS == 2000
    assert web_chat.POLL_MS_HINTERGRUND == 10000
    assert str(web_chat.POLL_MS) in web_chat._CHAT_JS
    assert str(web_chat.POLL_MS_HINTERGRUND) in web_chat._CHAT_JS


def test_das_js_setzt_kein_cookie_und_nichts_in_den_speicher():
    """E6: der Zustand steht im DOM und in der URL, nirgends sonst -- damit
    ein Link teilbar bleibt und ein zweites Telefon dieselbe Gruppe sieht."""
    for verboten in ("document.cookie", "localStorage", "sessionStorage",
                     "WebSocket", "EventSource"):
        assert verboten not in web_chat._CHAT_JS, verboten
```

Der Test `test_die_ptt_mindestdauer_steht_genau_einmal_im_code` ist zu unscharf. **Ersetzen
durch** den klaren Vertrag: die Zahl steht als Python-Konstante und wird per Platzhalter ins
JS gesetzt:

```python
def test_die_ptt_mindestdauer_kommt_aus_einer_konstante(seite):
    assert web_chat.PTT_MIN_MS == 500
    assert f"var PTT_MIN_MS = {web_chat.PTT_MIN_MS};" in seite
    # Kein zweiter Ort: im JS-Rohtext steht der Platzhalter, nicht die Zahl.
    assert "__PTT_MIN_MS__" in web_chat._CHAT_JS
```

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_js.py -q -p no:cacheprovider
```
Erwartet: FAIL — `_CHAT_JS` ist leer, `PTT_MIN_MS` fehlt.

- [x] **Schritt 3: `web_chat.py` — Konstanten und `_CHAT_JS`**

Konstanten:

```python
#: Polltakt der Chatansicht (Millisekunden). Zwei Sekunden, solange der Tab
#: sichtbar ist -- schnell genug, dass eine Antwort nicht "haengt" wirkt, und
#: langsam genug, dass drei Gruppen mit je zwei Telefonen den stdlib-Server
#: nicht beschaeftigen. Im Hintergrund seltener (ein Telefon in der Tasche
#: muss nichts abholen).
POLL_MS = 2000
POLL_MS_HINTERGRUND = 10000

#: Kuerzer gedrueckt = nichts gesendet (Birk, 30.09.2026, Punkt 2). Ein
#: versehentlicher Tipper auf das Mikrofon soll keine leere Aufnahme in den
#: Chat legen -- und keinen Gespraechszug ausloesen.
PTT_MIN_MS = 500

#: Wie oft ein fehlgeschlagener Upload wiederholt wird, und mit welchen
#: Wartezeiten (Sekunden). Dieselbe Haltung wie ``stt.WARTEZEITEN``: ein
#: Netzaussetzer im Probenraum darf ein Segment nicht kosten.
UPLOAD_VERSUCHE = 4
UPLOAD_WARTEN_MS = (1000, 3000, 8000)
```

Das Skript (bewusst ES5-nah, wie `_BEARBEITEN_JS` und `_SCROLL_JS`; Platzhalter in doppelten
Unterstrichen, gesetzt in `chat_html`):

```python
#: Das Chat-JavaScript. Vanilla, kein Build, kein Framework -- wie die
#: bestehende Seite (``_BEARBEITEN_JS``). Faellt es aus, bleibt der Verlauf
#: lesbar (serverseitig gerendert); nur Senden und Aufnehmen gehen nicht.
#:
#: Die Zahlen kommen als Platzhalter herein, damit sie an genau einer Stelle
#: stehen: in den Python-Konstanten darueber.
_CHAT_JS = """
(function () {
  var POLL_MS = __POLL_MS__;
  var POLL_MS_HINTERGRUND = __POLL_MS_HINTERGRUND__;
  var PTT_MIN_MS = __PTT_MIN_MS__;
  var UPLOAD_VERSUCHE = __UPLOAD_VERSUCHE__;
  var UPLOAD_WARTEN_MS = __UPLOAD_WARTEN_MS__;

  var verlauf = document.getElementById('verlauf');
  var fuss = document.getElementById('fuss');
  if (!verlauf || !fuss) { return; }
  var eingabe = document.getElementById('eingabe');
  var uhrFeld = document.getElementById('uhr');
  var pegelFeld = document.getElementById('pegel');
  var pegelBalken = pegelFeld ? pegelFeld.querySelector('span') : null;
  var warteFeld = document.getElementById('warteschlange');
  var tipptFeld = document.getElementById('tippt');
  var interviewKnopf = document.getElementById('interview');
  var pttKnopf = document.getElementById('ptt');
  var SEGMENT_MS = parseInt(fuss.dataset.segmentMs, 10) || 45000;

  var zustand = {
    letzte: parseInt(verlauf.dataset.letzte, 10) || 0,
    interview: fuss.dataset.interview === '1',
    warteschlange: [],
    laeuft: false,        // sendet gerade ein Upload?
    recorder: null,
    strom: null,
    beginn: 0,
    uhrTakt: null,
    pegelTakt: null,
    segmentTakt: null,
    pttVon: 0,
    pttAbgebrochen: false
  };

  function nonce() {
    var feld = document.getElementById('nonce');
    return feld ? feld.value : '';
  }

  // -- Verlauf -------------------------------------------------------------

  function escape(text) {
    var hilf = document.createElement('div');
    hilf.textContent = text == null ? '' : String(text);
    return hilf.innerHTML;
  }

  function blase(n) {
    var huelle = document.createElement('div');
    // Der Server hat schon gefiltert (sichere_html) -- ein Filter im Browser
    // laege auf der Seite, die er schuetzen soll.
    var inhalt = n.html;
    if (n.typ === 'sprache') {
      var s = n.dauer || 0;
      inhalt = escape('Sprachnachricht (' + Math.floor(s / 60) + ':' +
                      ('0' + (s % 60)).slice(-2) + ')');
    } else if (n.typ === 'datei') {
      inhalt = '<a href="chat/datei/' + n.id + '">' +
               escape(n.dateiname || 'Datei') + '</a>';
    }
    huelle.className = 'blase ' + n.von + ' ' + n.typ;
    huelle.dataset.id = n.id;
    huelle.innerHTML = inhalt;
    verlauf.appendChild(huelle);

    if (n.knoepfe && n.knoepfe.length) {
      var leiste = document.createElement('div');
      leiste.className = 'leiste';
      leiste.dataset.message = n.id;
      n.knoepfe.forEach(function (paar) {
        var knopf = document.createElement('button');
        knopf.type = 'button';
        knopf.textContent = paar[0];
        knopf.dataset.message = n.id;
        knopf.dataset.daten = paar[1];
        leiste.appendChild(knopf);
      });
      verlauf.appendChild(leiste);
    }
  }

  function nachUnten() {
    window.scrollTo(0, document.body.scrollHeight);
  }

  function nimmZustand(daten) {
    (daten.nachrichten || []).forEach(blase);
    if (daten.nachrichten && daten.nachrichten.length) {
      zustand.letzte = daten.letzte;
      verlauf.dataset.letzte = daten.letzte;
      // Eine Leiste, deren Nachricht ueberholt ist, nimmt der Server weg
      // (entferne_knoepfe) -- hier wird nur ergaenzt, nie geraten.
      nachUnten();
    }
    if (tipptFeld) { tipptFeld.textContent = daten.tippt ? 'schreibt …' : ''; }
    setzeInterview(!!daten.interviewmodus);
    zeigeAntworten(daten.antworten || {});
  }

  function zeigeAntworten(antworten) {
    Object.keys(antworten).forEach(function (id) {
      if (document.querySelector('.quittung[data-druck="' + id + '"]')) { return; }
      var zeile = document.createElement('div');
      zeile.className = 'quittung';
      zeile.dataset.druck = id;
      zeile.textContent = antworten[id];
      verlauf.appendChild(zeile);
    });
  }

  function hole() {
    return fetch('chat/zustand?nach=' + zustand.letzte, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { nimmZustand(d); } })
      .catch(function () { /* Netz weg: der naechste Takt versucht es wieder */ });
  }

  var pollTakt = null;
  function planePoll() {
    if (pollTakt) { clearInterval(pollTakt); }
    var takt = document.hidden ? POLL_MS_HINTERGRUND : POLL_MS;
    pollTakt = setInterval(hole, takt);
  }
  document.addEventListener('visibilitychange', function () {
    planePoll();
    if (!document.hidden) { hole(); }
  });
  planePoll();

  // -- Senden --------------------------------------------------------------

  function sendeText() {
    var text = (eingabe.value || '').trim();
    if (!text) { return; }
    eingabe.value = '';
    fetch('chat/senden', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nonce: nonce(), text: text })
    }).then(function () { hole(); })
      .catch(function () { eingabe.value = text; });
  }

  document.getElementById('senden').addEventListener('click', sendeText);
  eingabe.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); sendeText(); }
  });

  // -- Knoepfe -------------------------------------------------------------

  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('.leiste button') : null;
    if (!knopf) { return; }
    // Alle Knoepfe der Leiste aus: der zweite Druck ist idempotent
    // (repo.beanspruche_knopf), aber ein Knopf, der weiter klickbar
    // dasteht, laedt dazu ein.
    var leiste = knopf.closest('.leiste');
    if (leiste) {
      Array.prototype.forEach.call(leiste.querySelectorAll('button'),
        function (b) { b.disabled = true; });
    }
    fetch('chat/knopf', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: nonce(),
        message_id: parseInt(knopf.dataset.message, 10),
        data: knopf.dataset.daten
      })
    }).then(function (r) {
      if (!r.ok && leiste) {
        Array.prototype.forEach.call(leiste.querySelectorAll('button'),
          function (b) { b.disabled = false; });
      }
      hole();
    }).catch(function () {
      if (leiste) {
        Array.prototype.forEach.call(leiste.querySelectorAll('button'),
          function (b) { b.disabled = false; });
      }
    });
  });

  // -- Upload-Warteschlange ------------------------------------------------
  //
  // Sequentiell mit Wiederholung: ein Netzaussetzer im Probenraum darf ein
  // Segment nicht kosten. Und sequentiell, damit die Segmente in der
  // Reihenfolge ankommen, in der gesprochen wurde.

  function reiheEin(auftrag) {
    zustand.warteschlange.push(auftrag);
    zeigeWarteschlange();
    arbeiteAb();
  }

  function zeigeWarteschlange() {
    if (!warteFeld) { return; }
    var offen = zustand.warteschlange.length + (zustand.laeuft ? 1 : 0);
    warteFeld.textContent = offen
      ? (offen === 1 ? 'ein Stück wird hochgeladen …'
                     : offen + ' Stücke werden hochgeladen …')
      : '';
  }

  function arbeiteAb() {
    if (zustand.laeuft || !zustand.warteschlange.length) { return; }
    var auftrag = zustand.warteschlange[0];
    // Der Wettlauf: das erste Segment darf erst raus, wenn der Bot den
    // Interviewmodus wirklich an hat. Sonst macht aufnahme.klasse_fuer
    // daraus eine kurz-Aufnahme statt eines Interview-Teils.
    if (auftrag.brauchtInterview && !zustand.interview) {
      setTimeout(arbeiteAb, 500);
      return;
    }
    zustand.laeuft = true;
    zeigeWarteschlange();
    schicke(auftrag, 0);
  }

  function schicke(auftrag, versuch) {
    fetch('chat/audio?nonce=' + encodeURIComponent(nonce()) +
          '&dauer=' + auftrag.dauer, {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': auftrag.blob.type || 'audio/webm' },
      body: auftrag.blob
    }).then(function (r) {
      if (!r.ok && r.status >= 500 && versuch + 1 < UPLOAD_VERSUCHE) {
        throw new Error('nochmal');
      }
      fertig(auftrag);
    }).catch(function () {
      if (versuch + 1 >= UPLOAD_VERSUCHE) { fertig(auftrag); return; }
      setTimeout(function () { schicke(auftrag, versuch + 1); },
                 UPLOAD_WARTEN_MS[Math.min(versuch, UPLOAD_WARTEN_MS.length - 1)]);
    });
  }

  function fertig(auftrag) {
    zustand.warteschlange.shift();
    zustand.laeuft = false;
    zeigeWarteschlange();
    if (auftrag.danach) { auftrag.danach(); }
    hole();
    arbeiteAb();
  }

  function leer() {
    return !zustand.warteschlange.length && !zustand.laeuft;
  }

  // -- Aufnahme ------------------------------------------------------------

  function strom() {
    if (zustand.strom) { return Promise.resolve(zustand.strom); }
    return navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (s) { zustand.strom = s; return s; });
  }

  function neuerRecorder(s) {
    // Ein eigener Recorder je Segment -- KEINE Zeitscheibe
    // (start(timeslice)): deren Stuecke sind einzeln nicht dekodierbar, nur
    // das erste traegt den Container-Kopf. Whisper bekaeme ab dem zweiten
    // Segment Bytes ohne Kopf.
    var r = new MediaRecorder(s);
    var von = Date.now();
    r.ondataavailable = function (ev) {
      if (!ev.data || !ev.data.size) { return; }
      var dauer = Math.max(1, Math.round((Date.now() - von) / 1000));
      reiheEin({ blob: ev.data, dauer: dauer, brauchtInterview: true });
    };
    r.start();
    return r;
  }

  function pegelAn(s) {
    if (!pegelBalken || !window.AudioContext) { return; }
    var kontext = new AudioContext();
    var messer = kontext.createAnalyser();
    messer.fftSize = 256;
    kontext.createMediaStreamSource(s).connect(messer);
    var werte = new Uint8Array(messer.frequencyBinCount);
    zustand.pegelTakt = setInterval(function () {
      messer.getByteFrequencyData(werte);
      var summe = 0;
      for (var i = 0; i < werte.length; i++) { summe += werte[i]; }
      pegelBalken.style.width =
        Math.min(100, (summe / werte.length) * 2.2) + '%';
    }, 120);
  }

  function uhrAn() {
    zustand.beginn = Date.now();
    uhrFeld.hidden = false;
    pegelFeld.hidden = false;
    zustand.uhrTakt = setInterval(function () {
      var s = Math.floor((Date.now() - zustand.beginn) / 1000);
      uhrFeld.textContent = '● ' + Math.floor(s / 60) + ':' +
                            ('0' + (s % 60)).slice(-2);
    }, 500);
  }

  function anzeigeAus() {
    [zustand.uhrTakt, zustand.pegelTakt, zustand.segmentTakt]
      .forEach(function (t) { if (t) { clearInterval(t); } });
    zustand.uhrTakt = zustand.pegelTakt = zustand.segmentTakt = null;
    uhrFeld.hidden = true;
    pegelFeld.hidden = true;
    if (pegelBalken) { pegelBalken.style.width = '0'; }
  }

  function setzeInterview(an) {
    zustand.interview = an;
    fuss.dataset.interview = an ? '1' : '0';
    interviewKnopf.dataset.laeuft = an ? '1' : '0';
    interviewKnopf.textContent = an ? 'Aufnahme beenden' : 'Interview aufnehmen';
    // Waehrend eine Interview-Aufnahme laeuft, ist PTT ausgeblendet
    // (Birk, Punkt 2): zwei Mikrofone gleichzeitig sind keine Bedienung.
    if (pttKnopf) { pttKnopf.hidden = an; }
  }

  function starteInterview() {
    strom().then(function (s) {
      // Die Aufnahme laeuft SOFORT -- sonst verliert man die ersten Worte.
      // Der Upload wartet in der Warteschlange, bis der Modus wirklich an
      // ist (arbeiteAb).
      zustand.recorder = neuerRecorder(s);
      uhrAn();
      pegelAn(s);
      zustand.segmentTakt = setInterval(function () {
        if (!zustand.recorder) { return; }
        zustand.recorder.stop();            // liefert ondataavailable
        zustand.recorder = neuerRecorder(s);
      }, SEGMENT_MS);
      setzeInterview(true);
      return fetch('chat/interview', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nonce: nonce(), an: true })
      });
    }).then(hole).catch(function () {
      setzeInterview(false);
      anzeigeAus();
    });
  }

  function beendeInterview() {
    var laufend = zustand.recorder;
    zustand.recorder = null;
    anzeigeAus();
    if (laufend && laufend.state !== 'inactive') { laufend.stop(); }
    setzeInterview(false);
    // /fertig erst, wenn ALLE Uploads durch sind -- sonst verdichtet der Bot
    // ein Interview, dem das letzte Segment fehlt.
    (function warte(versuche) {
      if (!leer() && versuche > 0) {
        setTimeout(function () { warte(versuche - 1); }, 500);
        return;
      }
      fetch('chat/interview', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nonce: nonce(), an: false })
      }).then(hole);
    })(240);
  }

  interviewKnopf.addEventListener('click', function () {
    if (zustand.interview) { beendeInterview(); } else { starteInterview(); }
  });

  // -- Push-to-Talk --------------------------------------------------------
  //
  // Halten = sprechen, loslassen = senden, Klasse 'kurz' (der Modus wird
  // NICHT geschaltet). Pointer Events mit setPointerCapture, damit ein
  // Finger, der vom Knopf rutscht, weiter erkannt wird -- und pointercancel
  // sendet NICHTS.

  if (pttKnopf) {
    var pttRecorder = null;

    pttKnopf.addEventListener('pointerdown', function (ev) {
      if (zustand.interview) { return; }
      ev.preventDefault();
      pttKnopf.setPointerCapture(ev.pointerId);
      zustand.pttVon = Date.now();
      zustand.pttAbgebrochen = false;
      pttKnopf.dataset.haelt = '1';
      strom().then(function (s) {
        if (zustand.pttAbgebrochen) { return; }
        pttRecorder = new MediaRecorder(s);
        pttRecorder.ondataavailable = function (e) {
          var dauer = Math.round((Date.now() - zustand.pttVon) / 1000);
          // Zu kurz oder abgebrochen: NICHTS senden. Ein versehentlicher
          // Tipper soll keine leere Aufnahme in den Chat legen.
          if (zustand.pttAbgebrochen ||
              Date.now() - zustand.pttVon < PTT_MIN_MS ||
              !e.data || !e.data.size) { return; }
          reiheEin({ blob: e.data, dauer: Math.max(1, dauer),
                     brauchtInterview: false });
        };
        pttRecorder.start();
      }).catch(function () { zustand.pttAbgebrochen = true; });
    });

    function pttEnde(abbrechen) {
      return function (ev) {
        if (pttKnopf.dataset.haelt !== '1') { return; }
        pttKnopf.dataset.haelt = '0';
        if (abbrechen) { zustand.pttAbgebrochen = true; }
        try { pttKnopf.releasePointerCapture(ev.pointerId); } catch (e) {}
        if (pttRecorder && pttRecorder.state !== 'inactive') {
          pttRecorder.stop();
        }
        pttRecorder = null;
      };
    }

    pttKnopf.addEventListener('pointerup', pttEnde(false));
    pttKnopf.addEventListener('pointercancel', pttEnde(true));
    // Wegziehen: mit setPointerCapture bleibt der Knopf das Ziel, aber ein
    // Kontextmenue oder ein Systemdialog kann den Zeiger entfuehren.
    pttKnopf.addEventListener('lostpointercapture', function (ev) {
      if (pttKnopf.dataset.haelt === '1') { pttEnde(true)(ev); }
    });
  }

  nachUnten();
  hole();
})();
"""
```

In `chat_html` die Platzhalter setzen — das ist die eine Stelle, an der die Zahlen ins JS
kommen:

```python
def _js() -> str:
    """``_CHAT_JS`` mit den Zahlen aus den Modulkonstanten.

    Platzhalter und keine f-String-Interpolation: das Skript ist voll mit
    geschweiften Klammern."""
    return (
        _CHAT_JS
        .replace("__POLL_MS__", str(POLL_MS))
        .replace("__POLL_MS_HINTERGRUND__", str(POLL_MS_HINTERGRUND))
        .replace("__PTT_MIN_MS__", str(PTT_MIN_MS))
        .replace("__UPLOAD_VERSUCHE__", str(UPLOAD_VERSUCHE))
        .replace("__UPLOAD_WARTEN_MS__", json.dumps(list(UPLOAD_WARTEN_MS)))
    )
```

und in `chat_html` `skript=_js()` statt `skript=_CHAT_JS`.

**Zwei Dinge, die der Test aus Schritt 1 dann so nicht mehr trifft** (im Test anpassen):
`test_die_polltakte_stehen_als_konstanten` prueft `str(POLL_MS) in web_chat._CHAT_JS` — im
Rohtext steht der Platzhalter. Auf `_js()` umstellen:

```python
def test_die_polltakte_stehen_als_konstanten():
    assert web_chat.POLL_MS == 2000
    assert web_chat.POLL_MS_HINTERGRUND == 10000
    fertig = web_chat._js()
    assert f"var POLL_MS = {web_chat.POLL_MS};" in fertig
    assert f"var POLL_MS_HINTERGRUND = {web_chat.POLL_MS_HINTERGRUND};" in fertig
```

Und `test_das_js_ruft_nur_endpunkte_die_es_gibt` / `test_das_js_nennt_jeden_postweg` laufen
weiter gegen `_CHAT_JS` — die Pfade stehen dort woertlich.

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_js.py -q -p no:cacheprovider
```
Erwartet: `12 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2963 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_js.py
git commit -m "Web-Chat: Poll, Interview-Umschalter mit Segmenten, Push-to-Talk

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 12: Abnahme-E2E per HTTP in der normalen Suite

**Dateien:**
- Test: `tests/test_web_e2e_http.py` (neu) — **ohne Browser, ohne Netz, in `pytest`**

**Das ist die Abnahme der Karte.** Eine Gruppe wird **ausschliesslich per HTTP** von Phase 1
bis zum ersten Interview-Import gefuehrt: Text schreiben, angebotene Knoepfe druecken,
Interview an, zwei Segmente hochladen, Interview aus → **genau ein Interview mit ≥ 2 Teilen**
in der Datenbank.

**Aufbau:** Webserver im Thread auf Port 0 (wie `tests/test_web_chat_*.py`) **plus**
`bot.schleife` mit `WebKanal` in einem zweiten Thread, dazu eine LLM-Attrappe mit
geskripteten Antworten (Muster `tests/test_aufnahme.LLMAttrappe`) und ein STT-Klient per
`httpx.MockTransport` (Muster `tests/test_aufnahme.stt_attrappe`).

**Keine direkten `repo`-Schreibaufrufe als Abkuerzung.** Was die Gruppe tut, tut sie per
HTTP; was der Bot tut, tut er im Bot-Thread.

**Der Weg durch die Phasen, und welche Modellinhalte die Attrappe dafuer liefert.** Er ist am
Code nachgemessen (`knoepfe/basis.offene_art`, `knoepfe/wirkung._wirkung_speichern`,
`phasen.voraussetzungen`):

| Schritt | Gruppe per HTTP | Attrappe antwortet | Wirkung |
|---|---|---|---|
| 1 | Text „Unsere Begriffe: Ankommen, Arbeit, Nacht" | `VORSCHLAG BEGRIFFE:` | Grundleiste „Ja, speichern" |
| 2 | Knopf „Ja, speichern" | — | `arbeitsstand.begriffe`, danach `_phasenknopf` „Weiter zu Fragen" |
| 3 | Knopf „Weiter zu …" | — | Phase 2, Eintrittsnachricht |
| 4 | Text „Macht uns drei Fragen" | `VORSCHLAG FRAGEN:` | Grundleiste |
| 5 | Knopf „Ja, speichern" | — | `fragen` gesetzt; `starte_sensibilitaetspruefung` laeuft im Thread |
| 6 | (wartet) | auf `ANWEISUNG_EINLEITUNGEN` (Teilstring „Sieh dir diese Interviewfragen der Gruppe an") → `VORSCHLAG FRAGEN WEICH:` | Grundleiste |
| 7 | Knopf „Ja, speichern" | — | `fragen_weich`; `starte_eroeffnung` laeuft im Thread |
| 8 | (wartet) | auf `ANWEISUNG_EROEFFNUNG` (Teilstring „womit das Interview anfaengt und aufhoert") → `VORSCHLAG EROEFFNUNG:` mit einer `Abschluss:`-Zeile | Grundleiste |
| 9 | Knopf „Ja, speichern" | — | `interview_eroeffnung` **und** `interview_abschluss` (`_speichere_eroeffnung`); `phasen.voraussetzungen[3]` erfuellt |
| 10 | Knopf „Weiter zu …" | — | Phase 3 |
| 11 | POST `/chat/interview {an: true}` | — | `/interview` → Modus an, Interview-Kopf |
| 12 | POST `/chat/audio` ×2 | STT-Attrappe liefert erfundenen Text | zwei `aufnahme`-Zeilen mit `teil_von` = Kopf |
| 13 | POST `/chat/interview {an: false}` | Verdichter-Antwort | `/fertig` → ein Interview, ≥ 2 Teile |

**Alle Attrappen-Antworten sind frei erfunden** (Datenschutz). Der Interviewtext kommt aus
`simulation/interviews/` — erfundenes Material, das ins Repository gehoert.

**Falls der Weg 4–9 im Lauf nicht traegt** (etwa weil eine Phasenkette sich geaendert hat):
die Karte erlaubt ausdruecklich den Text-Import-Weg. Dann Schritt 4–10 durch
`aufnahme.importiere_text` ersetzen und **im Test-Docstring benennen, welcher Weg gewaehlt
wurde und warum** — und den Audio-Teil (11–13) als eigenen Test fahren, der die Phase per
Knopf „Weiter zu …" erreicht oder in Phase 1 startet (`/interview` ist in jeder Phase
erlaubt, `aufnahme.stelle_phase_interviews_sicher` zieht die Phase mit).

- [x] **Schritt 1: Den Test schreiben**

`tests/test_web_e2e_http.py`:

```python
"""Die Abnahme: ein Workshopanfang ohne Telegram, nur ueber HTTP.

Gefahren wird DERSELBE Codepfad wie im Betrieb -- ``bot.schleife`` in einem
Thread, mit ``WebKanal`` statt ``Telegram``, dazu ein echter Webserver auf
Port 0. Attrappen gibt es nur an den zwei Stellen, an denen Geld fliessen
wuerde: Sprachmodell und Whisper.

Was die Gruppe tut, tut sie per HTTP. Es gibt in diesem Test keinen einzigen
``repo``-Schreibaufruf als Abkuerzung -- sonst prueft er nicht den Weg, den
eine Gruppe im Browser geht.
"""

import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from interview_theater import bot, db, einstellungen, repo, web, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
GEDULD_S = 30.0

#: Erfundenes Material -- kein Wort davon kommt aus betrieb/.
INTERVIEWTEXT = (
    "Ich bin mit vierzehn hergekommen, im Winter. Am Bahnhof hat niemand "
    "gewartet. Ich hatte nur einen Koffer und einen Schal, der nicht warm "
    "war. Heute arbeite ich nachts, und am Morgen ist die Stadt leer und "
    "gehoert mir ein bisschen."
)

BEGRIFFE = (
    "Gut, ich habe eure drei Begriffe.\n\n"
    "VORSCHLAG BEGRIFFE:\nAnkommen\nArbeit\nNacht"
)
FRAGEN = (
    "Drei Fragen, die dazu passen:\n\n"
    "VORSCHLAG FRAGEN:\n"
    "Was war in deinem Koffer?\n"
    "Wer hat auf dich gewartet?\n"
    "Wann ist eine Stadt deine geworden?"
)
FRAGEN_WEICH = (
    "Eine Frage habe ich weicher formuliert.\n\n"
    "VORSCHLAG FRAGEN WEICH:\n"
    "2 — Du musst nichts sagen, was zu nah ist. Ich frage trotzdem: "
    "war jemand da, als du angekommen bist?"
)
EROEFFNUNG = (
    "So koenntet ihr anfangen und aufhoeren.\n\n"
    "VORSCHLAG EROEFFNUNG:\n"
    "Hallo, wir machen ein Theaterstueck und sammeln dafuer Geschichten. "
    "Was du erzaehlst, bleibt anonym, und du kannst jederzeit aufhoeren. "
    "Darf ich mitschneiden?\n"
    "Abschluss: Danke, dass du dir Zeit genommen hast. Wir spielen das im "
    "Fruehjahr, und du bist eingeladen."
)


class LLMAttrappe:
    """Antwortet nach Teilstrings im Nutzertext -- die erste passende Regel
    gewinnt.

    Keine Warteschlange: der Bot laeuft in mehreren Threads (Gespraechszug,
    Erkenner, Auftragszuege), und eine Warteschlange haenge von der
    Reihenfolge ab, die dabei nicht festgelegt ist. Die Teilstrings sind die
    Anweisungstexte aus ``knoepfe/texte.py``, woertlich."""

    REGELN = (
        # Die Auftragszuege der Fragenkette (knoepfe/texte.ANWEISUNG_*).
        ("Sieh dir diese Interviewfragen der Gruppe an", FRAGEN_WEICH),
        ("womit das Interview anfaengt und aufhoert", EROEFFNUNG),
        # Die Beitraege der Gruppe.
        ("Unsere Begriffe", BEGRIFFE),
        ("drei Fragen", FRAGEN),
    )

    def __init__(self):
        self.nutzertexte = []
        self._sperre = threading.Lock()

    def chat(self, chat_id, system, nutzer, art=None, **kw):
        with self._sperre:
            self.nutzertexte.append(nutzer)
        for merkmal, antwort in self.REGELN:
            if merkmal in nutzer:
                return antwort
        return "Erzaehlt weiter."

    # ``ablauf`` ruft ``chat``, ``szene`` ruft ``prosa`` -- hier derselbe Weg.
    prosa = chat

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            # Der Erkenner schreibt in diesem Lauf nichts: alles Speichern
            # laeuft ueber Knoepfe, und ein Erkenner, der daneben etwas
            # setzt, machte den Test von einem Modell abhaengig.
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        # Der Verdichter (nach /fertig).
        return {
            "zusammenfassung": "Eine Ankunft im Winter, ohne Empfang.",
            "kernthemen": [{
                "thema": "Ankommen ohne Empfang",
                "kurz": "Ankommen",
                "beleg_zitat": "Am Bahnhof hat niemand gewartet",
            }],
        }


def stt_attrappe(text: str) -> httpx.Client:
    """Wie ``tests/test_aufnahme.stt_attrappe``: Upload liefert eine
    batch_id, die erste Abfrage ist fertig. Das Feld ``data`` ist ein
    JSON-STRING (Falle 2) -- genau wie beim echten Anbieter."""

    def handler(anfrage):
        if "audio/transcriptions" in anfrage.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Webserver und Bot-Schleife, beide im Thread, auf einer Wegwerf-DB."""
    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"
    monkeypatch.setenv("IT_AUDIO", str(audio))
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", "1000")

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    # Genau wie scripts/web_gruppe.py -- der einzige Vorlauf, den eine echte
    # Web-Gruppe auch braucht.
    repo.sichere_gruppe(aufbau, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="b", stt_produkt="p",
        web_url="", kanal=einstellungen.KANAL_WEB, web_chat_id=CHAT,
    )
    klm = LLMAttrappe()
    kanal = web_kanal.WebKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=bot.POOL_GROESSE)
    threading.Thread(
        target=bot.schleife,
        args=(bot_conn, e, kanal, klm, stt_attrappe(INTERVIEWTEXT), pool),
        daemon=True,
    ).start()

    yield basis, token, pfad, klm
    dienst.shutdown()
    pool.shutdown(wait=False)


# -- Hilfsmittel: nur HTTP ------------------------------------------------


def _nonce(token):
    return web.nonce(SCHLUESSEL, token)


def _zustand(basis, token, nach=0):
    with urllib.request.urlopen(
        f"{basis}/g/{token}/chat/zustand?nach={nach}", timeout=5
    ) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def _post(basis, token, weg, koerper):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/{weg}",
        data=json.dumps({"nonce": _nonce(token), **koerper}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def _warte_auf_knopf(basis, token, teil: str) -> tuple[int, str]:
    """Wartet, bis im Chat ein Knopf steht, dessen Beschriftung ``teil``
    enthaelt -- und liefert ``(message_id, data)``.

    Immer den JUENGSTEN: was zuletzt im Chat stand, ist das, was eine Gruppe
    auf dem Handy sieht (dieselbe Regel wie
    ``simulation.attrappe.offene_knoepfe``)."""
    frist = time.monotonic() + GEDULD_S
    gesehen = []
    while time.monotonic() < frist:
        for n in reversed(_zustand(basis, token)["nachrichten"]):
            for beschriftung, daten in n["knoepfe"]:
                gesehen.append(beschriftung)
                if teil.lower() in beschriftung.lower():
                    return n["id"], daten
        time.sleep(0.3)
    raise AssertionError(f"Knopf {teil!r} kam nicht. Gesehen: {sorted(set(gesehen))}")


def _druecke(basis, token, teil: str) -> None:
    message_id, daten = _warte_auf_knopf(basis, token, teil)
    _post(basis, token, "knopf", {"message_id": message_id, "data": daten})


def _warte_auf(pfad: str, pruefung, was: str):
    """Wartet, bis eine Bedingung in der Datenbank gilt. Gelesen wird ueber
    eine eigene Verbindung -- der Bot-Thread hat seine."""
    frist = time.monotonic() + GEDULD_S
    conn = db.verbinde(pfad)
    try:
        while time.monotonic() < frist:
            ergebnis = pruefung(conn)
            if ergebnis:
                return ergebnis
            time.sleep(0.3)
    finally:
        conn.close()
    raise AssertionError(f"{was} trat nicht ein")


def _feld(pfad: str, name: str):
    return lambda conn: (
        (repo.hole_arbeitsstand(conn, CHAT) or {})[name]
        if repo.hole_arbeitsstand(conn, CHAT) is not None else None
    )


# -- die Abnahme ----------------------------------------------------------


def test_von_phase_eins_bis_zum_ersten_interview_nur_ueber_http(lauf):
    basis, token, pfad, _klm = lauf

    # (1) Phase 1: Begriffe
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen, Arbeit, Nacht"})
    _druecke(basis, token, "Ja, speichern")
    stand = _warte_auf(pfad, _feld(pfad, "begriffe"), "begriffe gesetzt")
    assert "Ankommen" in stand

    # (2) Phase 2: Fragen, weiche Fassungen, Eroeffnung -- drei Stufen,
    # jede mit derselben Grundleiste (knoepfe.offene_art).
    _druecke(basis, token, "Weiter zu")
    _warte_auf(pfad, lambda c: repo.hole_phase(c, CHAT) == 2, "Phase 2")

    _post(basis, token, "senden", {"text": "Macht uns drei Fragen dazu."})
    _druecke(basis, token, "Ja, speichern")
    _warte_auf(pfad, _feld(pfad, "fragen"), "fragen gesetzt")

    # Die Sensibilitaetspruefung laeuft von selbst an (im Thread).
    _druecke(basis, token, "Ja, speichern")
    _warte_auf(pfad, _feld(pfad, "fragen_weich"), "fragen_weich gesetzt")

    # Eroeffnung und Abschluss: EIN Block, ZWEI Felder
    # (knoepfe/fragen._speichere_eroeffnung).
    _druecke(basis, token, "Ja, speichern")
    _warte_auf(pfad, _feld(pfad, "interview_eroeffnung"), "Eroeffnung gesetzt")
    _warte_auf(pfad, _feld(pfad, "interview_abschluss"), "Abschluss gesetzt")

    # (3) Phase 3: Interviews
    _druecke(basis, token, "Weiter zu")
    _warte_auf(pfad, lambda c: repo.hole_phase(c, CHAT) == 3, "Phase 3")

    # (4) Interview an -- ueber /interview, nicht ueber eine zweite
    # Moduslogik (aufnahme.klasse_fuer haengt allein am Modus).
    _post(basis, token, "interview", {"an": True})
    _warte_auf(pfad, lambda c: repo.ist_interviewmodus_an(c, CHAT), "Modus an")

    # (5) Zwei Segmente
    for nummer in (1, 2):
        _lade_segment(basis, token, nummer)
    _warte_auf(
        pfad,
        lambda c: c.execute(
            "SELECT COUNT(*) FROM aufnahme WHERE chat_id = ? AND klasse = 'teil' "
            "AND teil_von IS NOT NULL", (CHAT,),
        ).fetchone()[0] >= 2,
        "zwei Interview-Teile",
    )

    # (6) Interview aus
    _post(basis, token, "interview", {"an": False})
    _warte_auf(pfad, lambda c: not repo.ist_interviewmodus_an(c, CHAT), "Modus aus")

    # GENAU EIN Interview mit mindestens zwei Teilen.
    conn = db.verbinde(pfad)
    koepfe = conn.execute(
        "SELECT id FROM aufnahme WHERE chat_id = ? AND klasse = 'lang'", (CHAT,)
    ).fetchall()
    assert len(koepfe) == 1
    teile = conn.execute(
        "SELECT COUNT(*) FROM aufnahme WHERE teil_von = ?", (koepfe[0]["id"],)
    ).fetchone()[0]
    assert teile >= 2

    # Und die Transkripte tragen den erfundenen Text -- der Weg durch
    # WebKanal.lade_datei, stt.mime_typ und Whisper hat gehalten.
    transkripte = [z["transkript"] for z in repo.transkripte(conn, CHAT)]
    assert any("Bahnhof" in (t or "") for t in transkripte), transkripte
    conn.close()


def _lade_segment(basis, token, nummer: int) -> None:
    """Ein WebM-Segment, wie MediaRecorder es liefert (EBML-Kopf + Rest)."""
    koerper = b"\x1a\x45\xdf\xa3" + bytes([nummer]) * 512
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?nonce={_nonce(token)}&dauer=30",
        data=koerper, headers={"Content-Type": "audio/webm;codecs=opus"},
        method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=15) as antwort:
        assert antwort.status == 202


def test_kein_telegram_im_ganzen_lauf(lauf):
    """E1 von der anderen Seite: dieser Lauf hat keinen Bot-Token und keine
    Netzverbindung zu Telegram -- und funktioniert trotzdem."""
    basis, token, pfad, _klm = lauf
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen"})
    _warte_auf(pfad, _feld(pfad, "begriffe"), "begriffe gesetzt") if False else None
    # Der Bot antwortet -- mehr braucht dieser Test nicht.
    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist:
        if any(n["von"] == "bot" for n in _zustand(basis, token)["nachrichten"]):
            return
        time.sleep(0.3)
    raise AssertionError("der Bot hat nicht geantwortet")


def test_kein_absendername_im_verlauf(lauf):
    """E8: nie Vornamen. Die Blase der Gruppe traegt keinen Namen, und im
    Gespraechs-Prompt steht das Rollenwort ``Gruppe``."""
    basis, token, _pfad, klm = lauf
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen"})
    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist and not klm.nutzertexte:
        time.sleep(0.3)
    assert klm.nutzertexte, "das Modell wurde nicht gerufen"
    assert f"{web_kanal.ABSENDER}:" in klm.nutzertexte[0]
    assert "None:" not in klm.nutzertexte[0]
```

Der zweite Test enthaelt eine unsinnige Zeile (`… if False else None`). **Bereinigen:** die
Zeile loeschen, der Test wartet nur auf eine Bot-Antwort.

**Hinweise fuer die Ausfuehrung (wichtig, hier wird es erfahrungsgemaess haken):**

1. `repo.hole_phase` — den echten Namen nachsehen (`phasen.aktuelle(conn, chat_id)` ist der
   Weg, den der Code nimmt). Im Test `phasen.aktuelle` benutzen.
2. `_feld` ist umstaendlich geschrieben; `repo.hole_arbeitsstand` liefert eine
   `sqlite3.Row`. Einfacher:
   ```python
   def _feld(name):
       def pruefung(conn):
           stand = repo.hole_arbeitsstand(conn, CHAT)
           return (stand[name] or "").strip() if stand is not None else ""
       return pruefung
   ```
   und im Test `_warte_auf(pfad, _feld("begriffe"), "begriffe gesetzt")`.
3. Die Knopfbeschriftungen stehen in `knoepfe/texte.py` (`_TEXT_SPEICHERN_KNOPF`,
   `phasen.knopfbezeichnung`). `_warte_auf_knopf` sucht per Teilstring — schlaegt es fehl,
   nennt die Fehlermeldung alle gesehenen Beschriftungen. **Dann die Konstante nehmen statt
   den Text zu raten**, zum Beispiel
   `from interview_theater.knoepfe.texte import _TEXT_SPEICHERN_KNOPF`.
4. `ablauf.ist_wiederholung` verwirft Antworten mit über 60 % Deckung zur vorigen
   Bot-Nachricht. Die Trigger-Texte der Gruppe sind deshalb bewusst verschieden und kurz.
5. `bot.schleife` laeuft endlos; der Thread ist `daemon=True` und stirbt mit dem Prozess.
   Zwei Tests in derselben Datei starten je einen eigenen — das ist in Ordnung, weil jeder
   seine eigene Datenbank und seinen eigenen `bot_zustand`-Stand hat.
6. Der Lauf ist **langsam** (Polling, Threads). `GEDULD_S = 30` ist grosszuegig; die drei
   Tests zusammen sollten unter zwei Minuten bleiben. Wird es deutlich mehr, ist etwas
   haengen geblieben — nicht die Geduld erhoehen, sondern nachsehen, welcher `_warte_auf`
   nicht durchkommt.

- [x] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_e2e_http.py -q -p no:cacheprovider
```
Erwartet: FAIL an der ersten Bedingung, die noch nicht traegt.

- [x] **Schritt 3: Zum Laufen bringen**

Hier wird **kein Produktionscode** neu geschrieben — alles steht aus den Aufgaben 1–11. Was
hier haengt, ist ein Fehler in einer der vorigen Aufgaben oder eine falsche Annahme im Test.
Die Reihenfolge beim Suchen:

1. Kommt ueberhaupt eine Bot-Antwort? Wenn nicht: `hole_updates`/`bot_zustand` pruefen
   (`repo.hole_update_id(conn, "gruppe1")` muss wachsen).
2. Kommt eine Antwort, aber kein Knopf? Dann trifft die Attrappe eine andere Regel — die
   `nutzertexte` der Attrappe ausgeben und den Teilstring nachziehen.
3. Kommen die Segmente nicht als `teil` an? Dann war der Modus beim Upload noch aus:
   `repo.ist_interviewmodus_an` **vor** dem ersten `_lade_segment` abwarten (der Test tut das
   schon — im JS macht es die Warteschlange, hier `_warte_auf`).
4. Bleibt ein Transkript leer? Dann greift `stt.mime_typ` daneben: die Endung der abgelegten
   Datei pruefen (muss `.webm` sein, Aufgabe 3).

- [x] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_e2e_http.py -q -p no:cacheprovider
```
Erwartet: `3 passed` in unter zwei Minuten.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2966 passed, 1 skipped`.

- [x] **Schritt 5: Commit**

```bash
git add tests/test_web_e2e_http.py
git commit -m "Abnahme: eine Gruppe per HTTP von Phase 1 bis zum ersten Interview

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 13: Browserlauf und Handy-Screenshot

**Dateien:**
- Neu: `tests/e2e/test_web_chat_e2e.py`
- Aendern: `tests/e2e/README.md` (ein Abschnitt)
- Neu (committet): `docs/web-chat/handy-2026-09-30.png`

**Laeuft nicht im normalen `pytest`.** Wie `tests/e2e/test_web_edit_e2e.py` ueberspringt die
Datei sich per `pytest.importorskip("playwright.sync_api")` — das bleibt so.

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_chat_e2e.py -q
```

Chromium mit `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`: damit gibt
es ein Mikrofon ohne Rueckfrage, und `getUserMedia` liefert einen synthetischen Ton.

- [x] **Schritt 1: Den Test schreiben**

`tests/e2e/test_web_chat_e2e.py`:

```python
"""Der Chat im echten Browser -- geklickt und gehalten, nicht simuliert.

Was dieser Lauf leistet, was ``tests/test_web_chat_*.py`` nicht leisten: den
MediaRecorder, die Segmente, die Warteschlange, ``setPointerCapture`` und die
Frage, ob ein zu kurzer Druck wirklich NICHTS sendet.

Kein Bot laeuft dabei mit: geprueft wird die Browserseite gegen den
Webserver. Was der Bot daraus macht, prueft ``tests/test_web_e2e_http.py``.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_chat_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web_kanal  # noqa: E402

DB_PFAD = "/tmp/it-webchat.db"
AUDIO = "/tmp/it-webchat-audio"
BIND = "127.0.0.1:8021"
BASIS = f"http://{BIND}"
CHAT = 7_000_000_000_001

#: Kurz, damit ein Lauf nicht Minuten dauert -- im Betrieb sind es 45 s
#: (``einstellungen.VORGABE_SEGMENT_MS``).
SEGMENT_MS = 1200

#: Wohin der Handy-Screenshot geht. Committet, weil Birk ihn ansieht -- und
#: er zeigt ausschliesslich erfundene Fixture-Daten.
SCHUSS = WURZEL / "docs" / "web-chat" / "handy-2026-09-30.png"

#: iPhone-13-Groesse. Mobile zuerst.
HANDY = {"width": 390, "height": 844}

GEDULD = 8000


def _baue_datenbank() -> str:
    """Eine Web-Gruppe in Phase 3 mit einer Leiste im Chat.

    Aufgebaut ueber ``repo`` und ``WebKanal`` -- so steht am Ende genau das
    da, was im Betrieb entsteht. Alles Material ist frei erfunden."""
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen",
        "Was war in deinem Koffer?\nWer hat auf dich gewartet?",
    )
    repo.setze_arbeitsstand(
        conn, CHAT, "interview_eroeffnung",
        "Hallo, wir machen ein Theaterstueck und sammeln Geschichten.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Danke fuer die Zeit.")

    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    kanal.sende(CHAT, "Eure Begriffe habe ich. Womit fangen wir an?")
    knopf_id = repo.lege_knopf_an(conn, CHAT, "stand", None)
    kanal.sende_mit_knoepfen(
        CHAT, "Der Leitfaden steht. Wollt ihr ihn sehen?",
        [("Stand zeigen", f"k:{knopf_id}")],
    )
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


def _warte_auf_server(sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        try:
            with urllib.request.urlopen(f"{BASIS}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(token):
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "/theatersoap",
        "IT_AUDIO": AUDIO, "IT_WEB_SEGMENT_MS": str(SEGMENT_MS),
        "PYTHONPATH": str(WURZEL),
    })
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server()
        yield prozess
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            # Ein Mikrofon ohne Rueckfrage, und ein synthetischer Ton darin.
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


@pytest.fixture
def seite(server, browser, token):
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"],
        base_url=BASIS, is_mobile=True, has_touch=True,
    )
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}/chat")
    yield blatt
    kontext.close()


def _zaehle_sprachnachrichten() -> int:
    conn = db.verbinde(DB_PFAD)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND typ = 'sprache'",
            (CHAT,),
        ).fetchone()[0]
    finally:
        conn.close()


def _zaehle(typ: str) -> int:
    conn = db.verbinde(DB_PFAD)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND typ = ?",
            (CHAT, typ),
        ).fetchone()[0]
    finally:
        conn.close()


def test_der_verlauf_steht_da(seite):
    expect(seite.locator(".blase.bot").first).to_contain_text("Eure Begriffe")
    expect(seite.locator(".leiste button")).to_have_count(1)


def test_text_senden_erscheint_im_verlauf(seite):
    seite.fill("#eingabe", "Wir fangen mit Ankommen an.")
    seite.click("#senden")
    expect(seite.locator(".blase.gruppe").last).to_contain_text("Ankommen")


def test_knopf_klicken_legt_einen_druck_an(seite):
    vorher = _zaehle("knopf")
    seite.click(".leiste button")
    for _ in range(40):
        if _zaehle("knopf") > vorher:
            break
        seite.wait_for_timeout(200)
    assert _zaehle("knopf") == vorher + 1
    # Der Knopf ist danach aus: ein benutzter Knopf, der weiter klickbar
    # dasteht, laedt zum zweiten Druck ein.
    expect(seite.locator(".leiste button").first).to_be_disabled()


def test_ptt_unter_einer_halben_sekunde_sendet_nichts(seite):
    vorher = _zaehle_sprachnachrichten()
    knopf = seite.locator("#ptt")
    knopf.hover()
    seite.mouse.down()
    seite.wait_for_timeout(150)
    seite.mouse.up()
    seite.wait_for_timeout(2500)
    assert _zaehle_sprachnachrichten() == vorher


def test_ptt_mit_pointercancel_sendet_nichts(seite):
    """Wegziehen oder ein Systemdialog: der Druck gilt als abgebrochen."""
    vorher = _zaehle_sprachnachrichten()
    seite.locator("#ptt").hover()
    seite.mouse.down()
    seite.wait_for_timeout(1200)
    seite.evaluate("""
      document.getElementById('ptt').dispatchEvent(
        new PointerEvent('pointercancel', { bubbles: true, pointerId: 1 }));
    """)
    seite.mouse.up()
    seite.wait_for_timeout(2500)
    assert _zaehle_sprachnachrichten() == vorher


def test_ptt_ueber_einer_halben_sekunde_sendet_genau_eines(seite):
    vorher = _zaehle_sprachnachrichten()
    seite.locator("#ptt").hover()
    seite.mouse.down()
    seite.wait_for_timeout(1500)
    seite.mouse.up()
    for _ in range(50):
        if _zaehle_sprachnachrichten() > vorher:
            break
        seite.wait_for_timeout(200)
    assert _zaehle_sprachnachrichten() == vorher + 1


def test_der_umschalter_erzeugt_mindestens_zwei_segmente(seite):
    """Birks Abnahme: Umschalter an/aus erzeugt ein Interview mit >= 2
    Segmenten. Die Segmentlaenge ist im Test auf SEGMENT_MS verkuerzt."""
    vorher = _zaehle_sprachnachrichten()
    seite.click("#interview")
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "1")
    expect(seite.locator("#uhr")).to_be_visible()
    # Zwei Segmentgrenzen ueberschreiten, plus Luft fuer den Upload.
    seite.wait_for_timeout(SEGMENT_MS * 2 + 1500)
    seite.click("#interview")
    for _ in range(80):
        if _zaehle_sprachnachrichten() >= vorher + 2:
            break
        seite.wait_for_timeout(200)
    assert _zaehle_sprachnachrichten() >= vorher + 2
    assert _zaehle("befehl") >= 2       # /interview und /fertig
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "0")


def test_waehrend_der_aufnahme_ist_ptt_weg(seite):
    """Zwei Mikrofone gleichzeitig sind keine Bedienung (Birk, Punkt 2)."""
    seite.click("#interview")
    expect(seite.locator("#ptt")).to_be_hidden()
    seite.click("#interview")
    expect(seite.locator("#ptt")).to_be_visible()


def test_handy_screenshot(seite):
    """Der Artefakt-Schuss: die Handy-Ansicht mit Knopfleiste und
    Aufnahme-Knopf. Nur erfundene Fixture-Daten."""
    seite.fill("#eingabe", "")
    expect(seite.locator(".leiste button").first).to_be_visible()
    SCHUSS.parent.mkdir(parents=True, exist_ok=True)
    seite.screenshot(path=str(SCHUSS), full_page=False)
    assert SCHUSS.stat().st_size > 5000
```

- [x] **Schritt 2: Lauf**

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \
  tests/e2e/test_web_chat_e2e.py -q
```
Erwartet: `9 passed`. **Wenn nicht:**
- „Recorder liefert nichts": pruefen, ob die beiden `--use-fake-*`-Flags ankamen
  (`seite.evaluate("navigator.mediaDevices ? 'da' : 'weg'")`).
- „nur ein Segment": `SEGMENT_MS` im Server-Env pruefen (`data-segment-ms` im HTML).
- „`pointercancel` wirkt nicht": Playwrights `mouse` erzeugt Pointer-Events mit
  `pointerId: 1` — steht der Wert im `dispatchEvent` anders, greift
  `releasePointerCapture` nicht.

- [x] **Schritt 3: Die normale Suite bleibt unberuehrt**

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ `2966 passed, **2 skipped**` — die zweite uebersprungene Datei ist die neue
e2e-Datei. **Das ist die einzige Stelle im ganzen Plan, an der die skipped-Zahl waechst.**

- [x] **Schritt 4: `tests/e2e/README.md` ergaenzen**

Einen Abschnitt hinter dem zur Probenansicht:

```markdown
Seit dem 30.09.2026 gehört der **Chat im Browser** dazu
(`/g/<token>/chat`, Karte Padua A2): der MediaRecorder, die Segmente der
Interview-Aufnahme, die Upload-Warteschlange und Push-to-Talk mit
`setPointerCapture` laufen **nur** im echten Browser. `tests/test_web_chat_*.py`
prüft daneben, was der Server liefert; `tests/test_web_e2e_http.py` fährt den
ganzen Weg mit einem echten Bot, aber ohne Browser.

Chromium braucht dafür zwei Flags — sie stehen im Test:

    --use-fake-ui-for-media-stream    # Mikrofon ohne Rückfrage
    --use-fake-device-for-media-stream  # synthetischer Ton

Die Segmentlänge ist im Lauf auf `SEGMENT_MS = 1200` verkürzt (im Betrieb
45 000, `einstellungen.VORGABE_SEGMENT_MS`) — sonst dauerte ein Test, der zwei
Segmente prüft, über eineinhalb Minuten. Der Server bekommt sie über
`IT_WEB_SEGMENT_MS`.

Der Handy-Screenshot landet in `docs/web-chat/handy-2026-09-30.png` und ist
**committet** (anders als die Schüsse in `/tmp`): er zeigt nur erfundene
Fixture-Daten und ist das Artefakt, das Birk ansieht.

Wegwerf-Datenbank: `/tmp/it-webchat.db`, Audio unter `/tmp/it-webchat-audio`,
Adresse `127.0.0.1:8021` — neben dem Edit-Lauf, damit beide nebeneinander
laufen können.
```

- [x] **Schritt 5: Commit**

```bash
git add tests/e2e/test_web_chat_e2e.py tests/e2e/README.md \
        docs/web-chat/handy-2026-09-30.png
git commit -m "Browserlauf: Segmente, PTT-Abbruch und der Handy-Screenshot

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 14: Betrieb, Doku, Abschluss

**Dateien:**
- Aendern: `docs/betrieb-env.beispiel`
- Aendern: `AGENTS.md` (Modultabelle, Modulkarte, Abschnitt „Weboberflaeche", Fallen)
- Aendern: `scripts/betrieb-start.sh` (ein Kommentar, **keine Logik**)
- Aendern: `docs/interview-theater@.service` (ein Kommentar)
- Test: `tests/test_web_betrieb_doku.py` (neu)

**Warum `betrieb-start.sh` keine Logik braucht:** es laedt `betrieb/<gruppe>.env`, prueft das
Workshop-Profil und startet `interview_theater.bot.main`. Ein Web-Bot unterscheidet sich
allein durch zwei Zeilen in der Env-Datei — dieselbe Unit, dasselbe Skript, derselbe
Profil-Check. Genau das ist Entscheidung M, und es ist ein Nachweis, kein Umbau.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_betrieb_doku.py`:

```python
"""Betrieb und Doku halten mit dem Code Schritt.

Der Anlass steht in AGENTS.md selbst: ``IT_MODELL_ERKENNER`` fehlt seit
Wochen in ``docs/betrieb-env.beispiel``. Eine Variable, die nur im Code
steht, findet am Workshopmorgen niemand.
"""

from pathlib import Path

from interview_theater import einstellungen, web_chat, web_kanal

WURZEL = Path(__file__).resolve().parent.parent


def _lies(pfad: str) -> str:
    return (WURZEL / pfad).read_text(encoding="utf-8")


def test_jede_umgebungsvariable_steht_im_beispiel():
    beispiel = _lies("docs/betrieb-env.beispiel")
    fehlend = [
        name for name in einstellungen._VORGABEWERTE if name not in beispiel
    ]
    assert fehlend == [], fehlend


def test_die_neuen_variablen_stehen_mit_erklaerung_im_beispiel():
    beispiel = _lies("docs/betrieb-env.beispiel")
    for name in ("IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS"):
        assert name in beispiel, name
    assert "web_gruppe" in beispiel


def test_agents_md_kennt_die_neuen_module():
    agents = _lies("AGENTS.md")
    for modul in ("web_kanal.py", "web_chat.py", "scripts/web_gruppe.py"):
        assert modul in agents, modul


def test_agents_md_nennt_den_kanal_und_die_tabelle():
    agents = _lies("AGENTS.md")
    assert "IT_KANAL" in agents
    assert "web_post" in agents
    assert "/g/<token>/chat" in agents


def test_agents_md_nennt_die_zwei_audio_wege():
    """Birks Vorgabe vom 30.09.2026 -- zwei getrennte Knoepfe, kein
    Schieben-zum-Sperren. Eine Entscheidung, die nur im Code steht, wird beim
    naechsten Umbau umgedreht."""
    agents = _lies("AGENTS.md")
    assert "Push-to-Talk" in agents
    assert "Schieben-zum-Sperren" in agents


def test_die_zahlen_in_agents_md_stimmen_mit_dem_code():
    agents = _lies("AGENTS.md")
    assert str(einstellungen.VORGABE_SEGMENT_MS // 1000) in agents   # 45
    assert str(web_chat.PTT_MIN_MS) in agents                        # 500
    assert str(web_kanal.TIPPT_GUELTIG_S) in agents                  # 8


def test_das_startskript_braucht_keine_kanal_logik():
    """Ein Web-Bot startet mit derselben Unit und demselben Skript -- nur mit
    anderer Env. Steht hier ein ``if`` auf IT_KANAL, ist etwas schiefgelaufen."""
    skript = _lies("scripts/betrieb-start.sh")
    assert "IT_KANAL" in skript          # als Kommentar
    assert "if [ \"$IT_KANAL\"" not in skript
    assert "case \"$IT_KANAL\"" not in skript


def test_die_unit_vorlage_erwaehnt_den_web_kanal():
    assert "IT_KANAL" in _lies("docs/interview-theater@.service")
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_betrieb_doku.py -q -p no:cacheprovider
```
Erwartet: FAIL — die Variablen fehlen im Beispiel, `AGENTS.md` kennt die Module nicht.
**Mit einem Nebeneffekt:** `test_jede_umgebungsvariable_steht_im_beispiel` faellt auch wegen
`IT_MODELL_ERKENNER` — das ist der in `AGENTS.md` dokumentierte Altstand. Mit aufnehmen, es
kostet eine Zeile und schliesst eine bekannte Luecke.

- [ ] **Schritt 3: `docs/betrieb-env.beispiel`**

Anhaengen:

```
# --- Der Kanal (30.09.2026, Karte Padua A2) --------------------------------
# Womit diese Gruppe arbeitet: 'telegram' (Vorgabe) oder 'web'.
# Ohne die Variable ist alles wie vorher -- Telegram bleibt Plan B.
IT_KANAL=telegram

# Nur im Web-Kanal: die eine Gruppe, die dieser Prozess bedient. Anlegen mit
#   IT_DB=... IT_WEB_URL=... python -m scripts.web_gruppe anlegen <bot_name>
# Das Skript gibt die chat_id, den Link fuer die Gruppe und diese zwei Zeilen
# aus. IT_BOT_TOKEN ist im Web-Kanal nicht noetig.
# IT_WEB_CHAT_ID=7000000000001

# Wie lang ein Aufnahmesegment im Browser ist (Millisekunden). Jedes Segment
# ist ein eigener MediaRecorder-Lauf und damit eine vollstaendige Datei --
# Netz weg oder Tab zu verliert hoechstens dieses eine Segment. Nur im Test
# verkuerzt (tests/e2e).
IT_WEB_SEGMENT_MS=45000

# Der Absichtserkenner laeuft nicht mit dem Gespraechsmodell (gemessen: 0
# Falsch-Positive bei 25 Negativfaellen). Stand hier bis zum 30.09.2026 nicht
# drin, obwohl einstellungen.py sie liest.
IT_MODELL_ERKENNER=google/gemma-4-31B-it
```

- [ ] **Schritt 4: `AGENTS.md`**

**(a)** Drei Zeilen in die Modultabelle (alphabetisch bei den Nachbarn einsortieren):

```markdown
| `web_kanal.py` | Der Web-Kanal (30.09.2026): `WebKanal` ersetzt `telegram.Telegram`, wenn `IT_KANAL=web`. Liest Browser-Ereignisse aus der Tabelle `web_post` als Telegram-foermige Updates und schreibt die Antworten dorthin zurueck — `bot.schleife` bleibt unveraendert, `knoepfe/` wird nicht angefasst. Kein SQL (alles ueber `repo`), kein Modell |
| `web_chat.py` | Die Chatansicht im Browser (30.09.2026): HTML, CSS, Vanilla-JS und alle Handler unter `/g/<token>/chat`. `web.py` bekommt nur die Routing-Zeilen. Traegt den serverseitigen HTML-Filter (`sichere_html`), die Knopfpruefung gegen die haengende Leiste, den Audio-Upload und die zwei Aufnahme-Wege. Kein SQL, kein Modell |
```

**(b)** In die Modulkarte, Schicht **Dienste**: `web_kanal.py` dazu; Schicht
**Oberflaeche**: `web_chat.py` dazu. In „Wo man anfaengt, je nach Frage":

```markdown
| Warum sieht der Browser nichts? | `web_kanal.hole_updates` → `repo.web_eingang` → `bot.schleife` |
| Was passiert bei einem Klick im Web-Chat? | `web_chat.beantworte_post` → `_POSTWEGE` → Eingang → `knoepfe.behandle` |
```

**(c)** Ein eigener Abschnitt hinter „Die Gruppenseite aendert Parameter":

```markdown
### Der Web-Kanal: derselbe Bot ohne Telegram (30.09.2026, Karte Padua A2)

**Die Idee in einem Satz:** der Webserver ist fuer den Bot das, was Telegrams
Server heute ist — er nimmt Browser-Ereignisse an und legt sie als
Telegram-foermige Updates in die Tabelle `web_post`; ein normaler Bot-Prozess
liest sie mit `web_kanal.WebKanal` statt mit `telegram.Telegram`.

**Was dadurch NICHT passiert ist:** `knoepfe/` (rund 4.500 Zeilen) wurde nicht
angefasst, `bot.schleife` nicht geaendert, und der Telegram-Weg ist
unveraendert funktionsfaehig (E1: Telegram bleibt Plan B). Ohne `IT_KANAL`
verhaelt sich alles wie vorher — `tests/test_kanal_wahl.py` haelt das fest.

**Warum die Naht traegt, ist gemessen und nicht geraten.** Die ganze
Kanalflaeche sind zwoelf Methoden, und `interview_theater/` ruft sie
ausnahmslos ueber das durchgereichte `tg`-Objekt (kein `httpx` gegen
`api.telegram.org`, `from.first_name` an genau einer Stelle,
`telegram.py:453`). `simulation/attrappe.py` beweist es seit dem 06.09.2026
empirisch: sie ersetzt `Telegram` mit neun Methoden und faehrt einen ganzen
Workshop durch. `tests/test_web_kanal_naht.py` liest das Paket per AST und
haelt es am Quelltext fest — **wer eine dreizehnte Kanalmethode benutzt, merkt
es dort**, nicht im Betrieb.

**EINE message_id-Folge fuer Gruppe UND Bot.** `web_post.id` ist zugleich
`message_id` und `update_id`. Das ist kein Detail: der Bot merkt sich seinen
Stand als `gruppe.letzte_beantwortete_message_id` und liest danach nur, was
groesser ist. Zaehlten Gruppe und Bot in getrennten Folgen, laege jede
Gruppennachricht ab dem zweiten Zug unter dem Wasserzeichen — der Bot
beantwortete sie nie (gemessen in `simulation.attrappe.naechste_message_id`).
Telegram vergibt seine ids ebenfalls fortlaufend je Chat, ueber alle Absender.

**Die Tippanzeige ist keine Nachricht** und steht deshalb in
`gruppe.web_tippt_bis`, acht Sekunden gueltig (`web_kanal.TIPPT_GUELTIG_S`):
`arbeitszeilen.TIPP_S` ist 4,0 s, und ein vierminuetiger Szenenlauf gaebe 60
Zeilen, die je eine `message_id` aus der gemeinsamen Folge verbrauchen.

**Web-Gruppen haben positive, synthetische chat_ids** ab
`repo.WEB_CHAT_ID_BASIS` (7 000 000 000 000) — weit oberhalb aller
Telegram-Bereiche, und im ganzen Repo leitet keine Stelle aus dem Vorzeichen
einer chat_id etwas ab (Test). Angelegt werden sie mit
`python -m scripts.web_gruppe anlegen <bot_name>`; das Skript gibt den Link,
die chat_id und die zwei Env-Zeilen aus und **liest nie `betrieb/`**. Der
Webserver koennte es nicht: er oeffnet die Datenbank read-only.
`gruppe.kanal` haelt fest, welcher Kanal eine Gruppe bedient.

**E8 im Web:** Nachrichten tragen keinen Vornamen. `nachricht.absender` traegt
das Rollenwort `web_kanal.ABSENDER` (`"Gruppe"`) — nicht `None`, weil
`kontext.sprecherzeile` sonst woertlich `"None:"` in jeden Gespraechs-Prompt
schriebe.

**Drei Dinge, die der Web-Kanal anders macht als Telegram** (alle drei
absichtlich):
1. **Kein Teilen bei 4.000 Zeichen.** Der Browser hat keine Laengengrenze, und
   ein Text, der in vier Stuecke zerfaellt, macht aus einer Bot-Antwort vier
   Blasen, unter deren letzter dann die Knoepfe haengen.
2. **`setze_befehle` ist ein No-Op.** Im Browser gibt es kein Slash-Menue, und
   Slash-Befehle werden nicht beworben — beworben wird der Knopf.
3. **`loesche_nachrichten` loescht weich** (`geloescht_am`), wie alles
   Entfernte in diesem Projekt.

**Die Chatansicht** (`/g/<token>/chat`, Modul `web_chat.py`, Handy zuerst) ist
rein Vanilla-JS, ohne Build, ohne WebSocket, ohne Cookie: sie pollt
`/chat/zustand?nach=<id>` alle zwei Sekunden (sichtbar) bzw. alle zehn
(Hintergrund). **Kein sanftes Nachladen** wie auf der Gruppenseite —
`web._seite(..., nachladen=False)`: das tauscht den `<body>` aus, und mitten in
einer laufenden Aufnahme riss das Recorder, Timer und Warteschlange mit.

**Bot-Ausgaben tragen Telegram-HTML** (`parse_mode="HTML"`, fuenf Stellen im
Repo, u. a. `vorschlag.menuetext`). `web_chat.sichere_html` maskiert deshalb
**alles** und laesst dann eine geschlossene Liste wieder zu — `b i u s code pre
blockquote` und `a` mit `http`/`https`. In dieser Richtung, nicht in der
anderen: ein Filter, der `<script>` entfernt, ist eine Liste von Dingen, an
die jemand gedacht hat. Gefiltert wird **serverseitig**; ein Filter im
JavaScript laege auf der Seite, die er schuetzen soll.

**Ein Knopfdruck wird gegen die haengende Leiste geprueft**, nicht gegen
`knopf.message_id`: die ist nur gesetzt, wenn ein Aufrufer
`repo.merke_knopf_nachricht` ruft, und das tun 22 von 47 Sendestellen —
`knoepfe.biete_einstieg` zum Beispiel nicht. Geprueft wird gegen
`web_post.knoepfe`, das `WebKanal.sende_mit_knoepfen` selbst schreibt; es
**ist** per Konstruktion, was gerade haengt. Steht `data` dort nicht, gibt es
400 und **keinen Eingang** — sonst waere jeder Knopf jeder Gruppe per `curl`
drueckbar, sobald jemand einen Link hat, und die `k:<id>` sind fortlaufende
Zahlen. Die Wirkung macht danach `knoepfe.behandle` im Bot-Prozess, unveraendert:
**kein zweiter Knopf-Handler**, und die Idempotenz bleibt
`repo.beanspruche_knopf` (Zusage 3).

**Audio im Browser sind ZWEI getrennte Knoepfe** (Birk, 30.09.2026,
verbindlich — **kein** Schieben-zum-Sperren):

1. **Interview-Aufnahme**, ein Umschalter: einmal tippen = laeuft, erneut
   tippen = Stopp, mit Timer, Pegel (`AnalyserNode`) und grossem Stopp-Knopf.
   Er schaltet den Interviewmodus ueber die vorhandenen Befehlswege
   `/interview` und `/fertig` — **keine zweite Moduslogik**, denn die Klasse
   einer Aufnahme haengt allein am Modus (`aufnahme.klasse_fuer`).
   Hochgeladen wird in **Segmenten von 45 Sekunden**
   (`IT_WEB_SEGMENT_MS`): Netz weg oder Tab zu verliert hoechstens das letzte
   Segment, nie das ganze Interview. **Jedes Segment ist ein eigener
   MediaRecorder-Lauf** (`stop()` + `start()`), nicht eine Zeitscheibe:
   `start(timeslice)`-Stuecke sind einzeln nicht dekodierbar, nur das erste
   traegt den Container-Kopf.
   Zwei Wettlaeufe sind im JS geloest: die Aufnahme startet **sofort** (sonst
   fehlen die ersten Worte), der Upload des ersten Segments wartet aber in der
   Warteschlange, bis der Zustands-Poll `interviewmodus: an` meldet — sonst
   machte `aufnahme.klasse_fuer` daraus eine `kurz`-Aufnahme. Und `/fertig`
   geht erst raus, wenn **alle** Uploads bestaetigt sind, sonst verdichtet der
   Bot ein Interview, dem das letzte Segment fehlt. Der Leer-Schutz ist der
   vorhandene (`aufnahme._TEXT_LEER_VERWORFEN`).
2. **Push-to-Talk** fuer Sprachnavigation, neben dem Textfeld: halten =
   sprechen, loslassen = senden, Klasse `kurz` (der Modus wird nicht
   geschaltet). Pointer Events mit `setPointerCapture`; **unter 500 ms
   (`web_chat.PTT_MIN_MS`) wird verworfen**, und `pointercancel` oder Wegziehen
   sendet **nichts**. Waehrend eine Interview-Aufnahme laeuft, ist PTT
   ausgeblendet — zwei Mikrofone gleichzeitig sind keine Bedienung.

**Die Endung entscheidet ueber den MIME-Typ** (Falle 3, und hier war die eine
Stelle, die dafuer angefasst werden musste): `web_chat.MIME_ERLAUBT` ist eine
Allowlist **Content-Type → Endung** (`audio/webm` → `.webm`, `audio/mp4` →
`.m4a` fuer Safari, dazu `audio/ogg` und `audio/mpeg`), die Datei landet mit
dieser Endung unter `IT_AUDIO/<chat_id>/web-eingang/`, und
`telegram.lies_nachricht` traegt sie als neuen, optionalen Schluessel `endung`
weiter, den `aufnahme.empfange` in den Zielpfad setzt. Ohne das bekaeme ein
WebM den Pfad `<message_id>.ogg` und damit `audio/ogg` — was Infomaniak mit
einer `batch_id` quittiert und dann dauerhaft auf `pending` stehen laesst
(89,7 s statt 2,0 s, im Betrieb nur als „haengt" sichtbar). Telegram nennt
keine Endung; dort bleibt es bei `aufnahme.ENDUNG_VORGABE` (`.ogg`), bitgleich
wie vorher. Groessengrenze je Segment: **8 MiB** (`MAX_AUDIO_BYTES`) —
gerechnet aus Opus 32 kbit/s ≈ 180 KiB je 45 s mit zwanzigfacher Luft, und klar
unter `stt.MAX_UPLOAD_BYTES` (25 MiB).

**Betrieb:** dieselbe Unit-Vorlage, dasselbe `scripts/betrieb-start.sh`,
derselbe Profil-Check — ein Web-Bot unterscheidet sich allein durch
`IT_KANAL=web` und `IT_WEB_CHAT_ID` in `betrieb/<gruppe>.env`.
`IT_BOT_TOKEN` ist dort nicht Pflicht.

**Was bewusst fehlt** (Uebergaben, siehe unten): ein QR-Code zum Link, die
englischen UI-Texte, und die Haertung (Rate-Limit) — die macht die Karte
„Absicherung Web".
```

**(d)** In „Was bewusst fehlt" drei Absaetze:

```markdown
- **Ein QR-Code zum Gruppenlink.** `scripts/web_gruppe.py` gibt die URL aus,
  keinen Code — dafuer braeuchte es eine Abhaengigkeit (`qrcode`, `segno`), und
  das Projekt hat auf der Webseite bewusst nur die Standardbibliothek. Wer ihn
  will, entscheidet vorher, welche Abhaengigkeit er sich leistet.
- **Englische UI-Texte der Chatansicht.** Die neuen Texte stehen als
  modulweite `_TEXT_*`-Konstanten in `web_chat.py` — genau die Form, die der
  Mechanismus aus Karte A1 (`T = sprache.Texte(__name__)`) spaeter uebersetzt.
  Uebersetzt sind sie noch nicht; das ist eine Uebergabe an A1, nicht eine
  Luecke dieser Karte.
- **Haertung der Weboberflaeche.** Es gibt kein Rate-Limit: wer den Link hat,
  kann so viele Nachrichten und Uploads schicken, wie er will, und jeder
  Upload kostet bis zu 8 MiB Speicher und einen Whisper-Aufruf. Das Token in
  der URL ist weiterhin das einzige Geheimnis (E6). Beides gehoert in die
  Karte „Absicherung Web".
- **Das Transkript-Echo ist im Web eine gewoehnliche Blase.** In Telegram
  steht es als `typ='transkript'` in `nachricht` und faellt damit aus allen
  drei Fenstern; im Chat sieht es aus wie jede andere Bot-Nachricht, weil es
  ueber `tg.sende` laeuft. Fachlich ist das richtig (es IST die Bestaetigung),
  optisch fehlt die Kennzeichnung „das ist dein abgetippter Text, keine
  Antwort des Bots". Uebergabe an „Absicherung Web".
```

**(e)** Bei den Fallen eine Ergaenzung zu Falle 3:

```markdown
   **Der Web-Kanal haengt an derselben Falle** (30.09.2026): `aufnahme.empfange`
   verdrahtete die Endung fest (`f"{message_id}.ogg"`), und ein WebM aus dem
   Browser haette damit `audio/ogg` bekommen. Seitdem traegt
   `telegram.lies_nachricht` den optionalen Schluessel `endung`, und
   `aufnahme.ENDUNG_VORGABE` ist nur noch der Rueckfall. **Bekannte Grenze, nicht
   behoben:** auch im Telegram-Betrieb bekommt eine `audio`-Nachricht (m4a, mp3)
   oder ein Dokument heute einen `.ogg`-Pfad — derselbe Fehler eine Etage weiter,
   und er war schon vor dieser Karte da. `lies_nachricht` koennte die Endung aus
   `mime_type`/`file_name` ableiten; das aendert den Telegram-Pfad und wurde
   deshalb hier nicht angefasst.
```

- [ ] **Schritt 5: `scripts/betrieb-start.sh` und die Unit-Vorlage**

In `betrieb-start.sh` hinter dem Laden der Env-Datei **nur einen Kommentar**:

```bash
# Ein Web-Bot (Karte Padua A2) startet mit DERSELBEN Unit und diesem Skript --
# er unterscheidet sich allein durch IT_KANAL=web und IT_WEB_CHAT_ID in der
# Env-Datei. IT_BOT_TOKEN ist dort nicht Pflicht. Also keine Weiche hier:
# die steht in bot.baue_kanal, an genau einer Stelle.
```

In `docs/interview-theater@.service` einen Kommentar im Kopf:

```
# Dieselbe Vorlage fuer Telegram- und Web-Bots (Karte Padua A2): der Kanal
# steht in betrieb/<gruppe>.env (IT_KANAL, IT_WEB_CHAT_ID), nicht hier.
```

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_betrieb_doku.py -q -p no:cacheprovider
```
Erwartet: `8 passed`.

- [ ] **Schritt 7: Der Abschluss-Nachweis**

Alle drei, und alle drei muessen stimmen:

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: **≥ 2974 passed, 2 skipped** — die Zahl muss **≥ Baseline (2768)** sein, und die
zweite uebersprungene Datei ist `tests/e2e/test_web_chat_e2e.py`.

```
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: gruen, Exitcode 0. **Das ist der Nachweis, dass das Workshop-Profil weiter laedt**
— `tests/test_profil_bitgleich.py` prueft 114 Abschnitte gegen
`docs/prompt-audit/schnappschuss-vor-profilumbau.txt`, und diese Karte hat keinen Prompt
angefasst.

```
git status --short
```
Erwartet: **leer** bis auf die Workerdateien, die nicht committet werden. Falls
`.cc-run-*`, `.cc-settings.json` oder `.superpowers-brief-*.md` als `??` auftauchen: **stehen
lassen, nicht committen, nicht loeschen.**

```
$PY -m scripts.pruefe_profil --vorgabe
```
Erwartet: ebenfalls gruen (das eingebaute Vorgabeprofil).

- [ ] **Schritt 8: Commit**

```bash
git add AGENTS.md docs/betrieb-env.beispiel scripts/betrieb-start.sh \
        docs/interview-theater@.service tests/test_web_betrieb_doku.py
git commit -m "Web-Kanal: AGENTS.md, Env-Beispiel und Betriebsvorlagen nachgezogen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 15: Vorbedingung Whisper — webm/mp4 aus dem Browser · **KOSTET GELD**

> **Diese Aufgabe kostet Geld** (Infomaniak-Whisper, ein Aufruf je Datei, Rappen). Sie steht
> ganz am Ende, nach allen kostenlosen Aufgaben. **Kein Test, laeuft nie automatisch** — wie
> `scripts/rauchtest.py` und `scripts/pruefe_prompts.py`.

**Dateien:**
- Aendern: `scripts/rauchtest.py` (nur, wenn es die Datei nicht schon annimmt — pruefen, es
  nimmt einen Pfad als Argument)
- Neu: `docs/web-chat/whisper-browserformate-2026-09-30.md` (der Befund)

**ANNAHME, die diese Aufgabe prueft:** Infomaniak-Whisper akzeptiert die Formate, die ein
Browser aus `MediaRecorder` liefert — **`audio/webm;codecs=opus`** (Chrome, Firefox) und
**`audio/mp4`** (Safari). Beides steht in `stt._MIME_TYPEN` und ist damit *technisch* durch
den Code hindurch; ob der Anbieter sie *transkribiert*, ist nicht gemessen. Die
Fehlerrichtung ist bekannt und boese: ein nicht unterstuetztes Format wird laut Falle 3 nicht
abgelehnt, sondern mit einer `batch_id` quittiert und bleibt dauerhaft `pending` — im Betrieb
nur als „haengt" sichtbar.

**ffmpeg liegt nicht im PATH.** Faellt ein Format durch, wird **nicht** konvertiert: das ist
eine Entscheidung mit einer neuen Abhaengigkeit, und die trifft Birk. Der Befund wird
geschrieben, die Karte endet.

- [ ] **Schritt 1: Die Beispieldateien im Browser aufnehmen**

Den Browserlauf aus Aufgabe 13 einmal von Hand fahren und die abgelegten Segmente
mitnehmen — sie liegen unter `/tmp/it-webchat-audio/<chat_id>/web-eingang/`. Das sind
**echte** MediaRecorder-Dateien mit dem echten Container-Kopf; eine selbst gebaute Datei
prueft nichts.

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \
  tests/e2e/test_web_chat_e2e.py -q -k umschalter
ls -l /tmp/it-webchat-audio/7000000000001/web-eingang/
```
Erwartet: mindestens zwei `.webm`-Dateien, jede einige KiB gross.

Fuer Safari/`audio/mp4` gibt es im Chromium-Lauf **keine** Datei. Zwei Wege, in dieser
Reihenfolge:
1. Auf einem Geraet mit Safari die Chatansicht oeffnen, eine Aufnahme machen, die Datei aus
   `web-eingang/` holen. Das ist der ehrliche Weg.
2. Ist kein Safari erreichbar: **die Annahme bleibt offen.** Dann steht im Befund
   ausdruecklich „mp4/AAC ungeprueft, kein Safari erreichbar" — und nicht ein Ergebnis aus
   einer nachgebauten Datei.

- [ ] **Schritt 2: Gegen den echten Dienst pruefen**

```
set -a; . ./betrieb/gruppe1.env; set +a
$PY -m scripts.rauchtest /tmp/it-webchat-audio/7000000000001/web-eingang/<datei>.webm
```

**Wichtig:** `betrieb/gruppe1.env` wird hier **gelesen, nicht ausgegeben** — die
Zugangsdaten stehen in der Umgebung, nicht im Bericht. `rauchtest.py` schreibt seine
`aufruf`-Zeilen in eine Wegwerf-Datenbank, nie in `IT_DB`.

Erwartet bei Erfolg: eine Transkriptzeile und eine Dauer in der Groessenordnung **2–5 s**.
Erwartet bei Misserfolg: entweder ein Fehler — oder, und das ist der gefaehrliche Fall, ein
Lauf, der ins Zeitbudget rennt (**rund 90 s**) und dann mit „war nach Ns noch pending"
abbricht. Genau dieses Bild ist der Befund „Format nicht unterstuetzt".

Falls `rauchtest.py` den Pfad nicht als Argument nimmt: es tut es
(`python -m scripts.rauchtest [pfad-zu-audio.ogg]`, AGENTS.md). Nimmt es nur `.ogg` an, die
Endungspruefung dort weiten — **nicht** die Datei umbenennen, das waere genau Falle 3.

- [ ] **Schritt 3: Den Befund schreiben**

`docs/web-chat/whisper-browserformate-2026-09-30.md`:

```markdown
# Whisper und die Browserformate

**Gemessen am <Datum>** gegen den echten Infomaniak-Endpunkt, mit Dateien, die
ein echter `MediaRecorder` erzeugt hat (nicht nachgebaut).

| Container/Codec | Browser | Endung | MIME (aus `stt.mime_typ`) | Ergebnis | Dauer |
|---|---|---|---|---|---|
| WebM/Opus | Chromium <Fassung> | `.webm` | `audio/webm` | <Text kam / pending / Fehler> | <s> |
| mp4/AAC | Safari <Fassung> | `.m4a` | `audio/mp4` | <… oder „ungeprueft, kein Safari erreichbar"> | — |

**Warum das eigens gemessen wurde.** Falle 3: ein nicht unterstuetztes Format
wird nicht abgelehnt, sondern mit einer `batch_id` quittiert und bleibt
dauerhaft `pending` — 89,7 s statt 2,0 s, im Betrieb nur als „haengt"
sichtbar. Ein Format, das durch `stt._MIME_TYPEN` hindurchgeht, ist damit noch
nicht eines, das der Anbieter transkribiert.

**Folge fuer den Betrieb:** <einer der drei Saetze>

- Beide Formate gehen → nichts zu tun, der Web-Kanal ist einsatzbereit.
- WebM geht, mp4 nicht → iPhones koennen im Browser keine Interviews
  aufnehmen. **Kein Workaround in dieser Karte:** ffmpeg liegt nicht im PATH,
  und eine Konvertierung ist eine Entscheidung mit neuer Abhaengigkeit, die
  Birk trifft. Bis dahin: Telegram fuer iPhones (E1, Telegram bleibt Plan B).
- WebM geht nicht → der Web-Kanal traegt heute keine Interviews. Text, Knoepfe
  und Push-to-Talk in der Transkription unabhaengige Teile funktionieren
  weiter; die Aufnahme braucht eine Entscheidung.

**Was NICHT gemacht wurde und warum:** keine Konvertierung, kein
`ffmpeg`-Aufruf, kein Umbenennen einer Datei auf eine andere Endung. Das
Letztere waere genau Falle 3 noch einmal.
```

- [ ] **Schritt 4: Commit**

```bash
git add docs/web-chat/whisper-browserformate-2026-09-30.md scripts/rauchtest.py
git commit -m "Web-Kanal: Whisper gegen die echten Browserformate gemessen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Uebergaben

Was diese Karte bewusst **nicht** erledigt — jeweils mit dem Grund:

1. **QR-Code zum Gruppenlink.** `scripts/web_gruppe.py` gibt die URL aus. Ein QR-Code
   braucht eine Abhaengigkeit (`qrcode`, `segno`); die Webseite hat heute **nur** die
   Standardbibliothek, und diese Entscheidung gehoert nicht in eine Karte, die sie nur
   beilaeufig braeuchte.
2. **Englische UI-Texte der Chatansicht** → Karte A1 / Merge. Die neuen Texte stehen als
   modulweite `_TEXT_*`-Konstanten in `web_chat.py`, also in genau der Form, die
   `T = sprache.Texte(__name__)` uebersetzt. Uebersetzt sind sie nicht.
3. **Haertung („Absicherung Web")**, drei Punkte:
   - **Rate-Limit.** Wer den Link hat, kann beliebig viele Nachrichten und Uploads schicken;
     jeder Upload kostet bis zu 8 MiB Speicher und einen bezahlten Whisper-Aufruf. Heute
     begrenzt nur `MAX_AUDIO_BYTES` und `MAX_TEXT_ZEICHEN` das **einzelne** Ereignis, nichts
     die Rate.
   - **Transkript-Echo sichtbar wie in Telegram.** Das Echo laeuft ueber `tg.sende` und ist
     im Web eine gewoehnliche Bot-Blase. Fachlich richtig (es IST die Bestaetigung), optisch
     fehlt die Kennzeichnung „das ist dein abgetippter Text, keine Antwort des Bots" — in
     Telegram steht es als `typ='transkript'` in `nachricht` und faellt aus allen drei
     Fenstern, was im Web genauso gilt (es geht ueber `web_post`, nicht ueber `nachricht`,
     wenn der Bot es schickt).
   - **Der Nonce steht bei Audio in der Query** und damit in der Serverlogzeile
     (`web._Basishandler.log_message`). Neu ist das nicht — das Token steht schon im Pfad und
     damit ebenfalls dort —, aber es gehoert in die Haertungs-Karte.
4. **Die Endung im Telegram-Pfad.** `audio`-Nachrichten (m4a, mp3) und Dokumente bekommen in
   Telegram weiterhin einen `.ogg`-Pfad — derselbe Fehler wie Falle 3, eine Etage weiter, und
   schon vor dieser Karte vorhanden. `telegram.lies_nachricht` koennte die Endung aus
   `mime_type`/`file_name` ableiten. Hier nicht angefasst, weil es den Telegram-Pfad aendert
   (E1).
5. **Der Simulator kennt den Web-Kanal nicht.** `simulation/` faehrt weiter ueber
   `TelegramAttrappe` und `bot.verarbeite_update` direkt. Das ist in Ordnung (sie misst
   Prompts und Navigation, nicht den Kanal), aber ein Lauf ueber `WebKanal` waere der
   ehrlichere Test des Web-Wegs — und `hole_updates` ist die eine Methode, die die Simulation
   heute nicht beruehrt.
6. **`aktualisiere_knoepfe` hat keinen Aufrufer.** Sie ist in `WebKanal` implementiert und
   getestet, aber `interview_theater/` ruft sie seit dem 06.09.2026 nicht (Fragenauswahl per
   Nummer im Text). Der naechste Toggle bringt sie zurueck; bis dahin ist sie Flaeche ohne
   Betriebspfad.
7. **Kein Web-Dashboard-Blick auf den Kanal.** Das Dashboard zeigt nicht, welche Gruppe im
   Web arbeitet — `gruppe.kanal` steht in der Datenbank, aber nicht in `web_daten.dashboard`.
   Eine Zeile, die niemand bestellt hat.

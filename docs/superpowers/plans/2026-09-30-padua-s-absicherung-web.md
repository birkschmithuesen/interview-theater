# Padua S: Absicherung der Weboberflaeche (Upload, Flut, Kosten, Token-Rotation)

> **Fuer agentische Umsetzer:** PFLICHT-UNTERSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Aufgabe fuer Aufgabe. Die Schritte tragen
> Checkboxen (`- [ ]`).

**Ziel:** Nach Karte A2 ist die Gruppenseite schreibend und nimmt Audio an. Dieser Plan
haertet sie: Upload-Grenzen mit Typpruefung an den Magic Bytes, ein Rate-Limit je Gruppe,
ein Tageskostendeckel von 5 CHF ueber **alle** Modellaufrufe (Web wie Telegram),
Token-Rotation, Sicherheits-Kopfzeilen an genau einer Stelle und Fehlerseiten, die nichts
verraten.

**Architektur:** Drei Ebenen, die sich nicht beruehren. (1) **Im Webserver-Prozess**:
Kopfzeilen, Herkunftspruefung, Rate-Limit, Upload-Pruefung — alles vor der ersten Wirkung,
alles Standardbibliothek. (2) **Im Bot-Prozess**: EINE Kostenpruefung vor jedem Netzaufruf
an ein bezahltes Modell (`llm`, `szene_claude`, Whisper). Weil beide Kanaele durch denselben
Bot-Code laufen, gilt der Deckel fuer Telegram und Web automatisch. (3) **Von Hand**: ein
Betreiberskript fuer die Token-Rotation, kein Chat-Befehl.

**Tech-Stack:** Python 3.11, nur Standardbibliothek (`http.server`, `hmac`, `zoneinfo`,
`sqlite3`, `threading`, `tomllib`) plus das schon vorhandene `httpx`. **Kein neues Paket.**

---

## Baseline (in diesem Worktree selbst gemessen)

```
$PY -m pytest -q -p no:cacheprovider
2768 passed, 1 skipped in 230.78s (0:03:50)
```

Stand `d144715` (= `origin/main` `d8deb6c` + Plan A2). **Diese Zahl ist nicht die Zahl, gegen
die du arbeitest:** A1 und A2 bringen eigene Tests mit. Aufgabe 0 misst die Baseline nach dem
Merge neu und traegt sie ein; jedes `Erwartet: >= …` unten meint diese neu gemessene Zahl.

**`$PY` ist gesetzt als**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
```

Das `.venv` im Hauptbaum wird **nicht** benutzt.

---

## Die Praemisse der Karte ist falsch — Beleg

Der Kartentext sagt: *„Kostendeckel E7: 5 CHF je Gruppe und Tag ueber alle Modellaufrufe
(**Kosten stehen im `aufruf`-Protokoll**)."* Sie stehen dort nicht. Selbst gemessen auf
`d8deb6c`:

| Befund | Beleg |
|---|---|
| `aufruf` hat **keine** Kostenspalte und **keine** Modellspalte — nur Token | `interview_theater/db.py:705-717` (`id, chat_id, art, modus, geschaetzte_token, tatsaechliche_token, antwort_token, finish_reason, dauer_ms, erfolg, erstellt_am`) |
| Ohne Modellspalte ist die Kostenrechnung im Nachhinein **unmoeglich**: `art` sagt nicht, welches Modell lief (`schema(..., modell=…)` waehlt je Aufruf) | `interview_theater/llm.py:169-192` (`schema` nimmt `modell`), `interview_theater/llm.py:316-328` (das `finally` bucht ohne `modell`) |
| Whisper bucht **gar nicht** in `aufruf` | `grep -c merke_aufruf interview_theater/stt.py` → `0` |
| Claude bucht mit `modus='C'` und laut Docstring „mit 0 CHF, weil Abo" — ein Wert, der nirgends steht | `interview_theater/szene_claude.py:91-92`, `:157-166` |
| Die Preise stehen **nur** im Pruefskript, nicht im Paket | `scripts/pruefe_prompts.py:97-106` (`PREISE_CHF_JE_MIO_TOKEN`), `:695-703` (`kosten_chf`) |

**Folge fuer den Plan:** Kosten werden beim **Buchen** berechnet und gespeichert, nicht beim
Lesen rekonstruiert (Entscheidung E-S1). Zwei additive Spalten, eine Preistabelle im Paket,
und Whisper bucht kuenftig mit.

---

## Vorbedingung: A1 und A2 muessen auf `main` sein

Dieser Plan baut auf Code, den es zum Zeitpunkt des Schreibens **nicht gibt**.

- **Karte A2** („Weboberflaeche als Arbeitsplatz": Chat, Knoepfe, Audio-Upload im Browser)
  ist geplant, nicht umgesetzt. Ihr Plan liegt in diesem Worktree:
  `docs/superpowers/plans/2026-09-30-padua-a2-web-arbeitsplatz.md` (7141 Zeilen). Punkt 3
  des Abschnitts „Uebergaben" (Z. 7112-7125) ist **genau diese Karte**.
- **Karte A1** („Sprache pro Workshop-Profil", `sprache.Texte`,
  `interview_theater/sprachen/en/texte.toml`) ist umgesetzt, aber noch nicht gemergt:
  Plan unter `git show padua-workshop/t_285cd5fb-plan-a1-sprache:docs/superpowers/plans/2026-09-30-padua-a1-sprache.md`,
  Code unter `git show padua-workshop/t_28ed3dde-padua-a1-sprache-pro-workshop-profil-eng:interview_theater/sprache.py`.

**Aufgabe 0 ist die Vorbedingungspruefung.** Fehlt auch nur ein Name aus ihrer Liste:
**stoppen und blockieren, nicht neu erfinden.** Ein zweites `MAX_AUDIO_BYTES` neben dem aus
A2 waere die schlimmste Sorte Fehler — zwei Grenzen, von denen eine nicht wirkt.

---

## Annahmen

Jede Zeile ist ein Name, den dieser Plan aus dem A2- oder A1-Plan uebernimmt, **ohne ihn im
Code gesehen zu haben**. Das Kommando prueft sie; alle stehen noch einmal gesammelt in
Aufgabe 0.

| # | ANNAHME | Quelle | Pruefkommando |
|---|---|---|---|
| A-1 | `web_chat.MAX_AUDIO_BYTES == 8 * 1024 * 1024` | A2-Plan Z. 4326, 4610 | `grep -n "MAX_AUDIO_BYTES" interview_theater/web_chat.py` |
| A-2 | `web_chat.MAX_DAUER_S == 3600` | A2-Plan Z. 4327, 4616 | `grep -n "MAX_DAUER_S" interview_theater/web_chat.py` |
| A-3 | `web_chat.MAX_TEXT_ZEICHEN == 4000` | A2-Plan Z. 3573, 3784 | `grep -n "MAX_TEXT_ZEICHEN" interview_theater/web_chat.py` |
| A-4 | `web_chat.MIME_ERLAUBT` und `web_chat.endung_fuer(content_type)` | A2-Plan Z. 4342, 4596-4634 | `grep -n "MIME_ERLAUBT\|def endung_fuer" interview_theater/web_chat.py` |
| A-5 | `web_chat._POSTWEGE` ist ein Dict `unterpfad -> handler` | A2-Plan Z. 3894-3897 | `grep -n "_POSTWEGE" interview_theater/web_chat.py` |
| A-6 | `web_chat.beantworte_post(handler, db_pfad, token, unterpfad, schluessel)` | A2-Plan Z. 3849-3865 | `grep -n "def beantworte_post" interview_theater/web_chat.py` |
| A-7 | `web_chat.beantworte_get(handler, db_pfad, token, unterpfad, praefix, schluessel, query)` | A2-Plan Z. 3464-3470 | `grep -n "def beantworte_get" interview_theater/web_chat.py` |
| A-8 | Routen `POST /g/<token>/chat/{senden,knopf,audio,interview}` | A2-Plan Z. 3579, 3947, 4331, 4969 | `grep -n "\"senden\"\|\"knopf\"\|\"audio\"\|\"interview\"" interview_theater/web_chat.py` |
| A-9 | `/chat/audio` nimmt einen **rohen** Koerper, Nonce und Dauer in der **Query** | A2-Plan Z. 4331, 4670-4678 | `grep -n "parse_qs\|roh_dauer" interview_theater/web_chat.py` |
| A-10 | `web_chat.schreibend(db_pfad)` — Kontextmanager um `db.verbinde` | A2-Plan Z. 3793-3802 | `grep -n "def schreibend" interview_theater/web_chat.py` |
| A-11 | `web_chat._angenommen(handler, nutzlast)` antwortet **202** | A2-Plan Z. 3836-3846 | `grep -n "def _angenommen" interview_theater/web_chat.py` |
| A-12 | `web_chat._gruppe_oder_404(handler, db_pfad, token) -> int \| None` | A2-Plan Z. 3806-3818 | `grep -n "def _gruppe_oder_404" interview_theater/web_chat.py` |
| A-13 | `web_chat.CHAT_PFAD == "chat"` | A2-Plan Z. 2642 | `grep -n "CHAT_PFAD" interview_theater/web_chat.py` |
| A-14 | Tabelle `web_post`, `repo.lege_web_post_an(...)`, `repo.RICHTUNG_EIN`, `repo.WEB_TYP_TEXT/_SPRACHE/_KNOPF` | A2-Plan Z. 291-311 | `grep -n "web_post\|RICHTUNG_EIN\|WEB_TYP_" interview_theater/repo.py` |
| A-15 | `web_kanal.WebKanal` mit `sende(chat_id, text, …)` und `hole_updates(…)` | A2-Plan Aufgabe 2, Z. 761-772 | `grep -n "class WebKanal\|def sende\|def hole_updates" interview_theater/web_kanal.py` |
| A-16 | `web_kanal.eingangspfad(verz, chat_id, message_id, endung)` | A2-Plan Z. 4692-4694 | `grep -n "def eingangspfad" interview_theater/web_kanal.py` |
| A-17 | `einstellungen.Einstellungen` traegt die A2-Felder `kanal`, `web_chat_id`, `web_segment_ms` | A2-Plan Z. 2006-2010 | `grep -n "kanal\|web_chat_id\|web_segment_ms" interview_theater/einstellungen.py` |
| A-18 | `sprache.Texte(__name__)` und `interview_theater/sprachen/en/texte.toml` | A1 | `grep -n "class Texte" interview_theater/sprache.py && ls interview_theater/sprachen/en/texte.toml` |
| A-19 | **Claude-Proxy-Aufrufe zaehlen nicht gegen den 5-CHF-Deckel** (Abo). *Birk bestaetigt, dass Claude-Proxy-Aufrufe nicht gegen den 5-CHF-Deckel zaehlen.* | Entscheidung E-S1 des Architekten | keine — steht als **eine** Konstante `kosten.CLAUDE_CHF_JE_AUFRUF = 0.0` (Aufgabe 6), damit sie umstellbar ist |
| A-20 | **Whisper kostet 0,006 CHF je Minute Audio.** Quelle: `~/hermes-shared/hermes-knowledge/infomaniak-modelle.md` § 1.2 (Tabelle „Weitere Modalitaeten\": `whisper` (V3) · 0,006 · CHF/Minute Audio) und § 6.4 („Grenze: 25 MB. Preis 0,006 CHF/Minute\"). **Architekt-Korrektur 30.09.2026:** der Planlauf konnte die Datei nicht lesen, der Architekt hat beide Stellen selbst gelesen — der Wert ist damit belegt abgeschrieben, aber weiterhin **Listenpreis, nicht Rechnung**; die Datei liegt ausserhalb des Repos (Stand der Datei: 05.09.2026). | Architekt, selbst gelesen | keine — steht als Konstante mit Datum (Aufgabe 7); ob die Rechnung dem Listenpreis folgt, misst nur Aufgabe 11 (kostet Geld) |
| A-21 | **Die Preistabelle hat Stand 04.09.2026** und ist seither nicht nachgezogen. | `scripts/pruefe_prompts.py:97` | `grep -n "04.09.2026" scripts/pruefe_prompts.py` |

**Keine Annahmen** (selbst gemessen auf `d8deb6c`, Datei:Zeile steht jeweils dabei):
`web.MAX_POST_BYTES = 64 * 1024` (`web.py:2343`), `stt.MAX_UPLOAD_BYTES = 25 MiB`
(`stt.py:44`), `stt.mime_typ` (`stt.py:73`), `web._Basishandler` (`web.py:2525`),
`web.nonce`/`nonce_gueltig` (`web.py:85`/`:107`), `web._seite` (`web.py:570`),
`repo.stelle_web_token_sicher` (`repo.py:124`), `repo.merke_aufruf` (`repo.py:2788`),
`repo.merke_vorfall` (`repo.py:373`), `db._migriere_fehlende_spalten` (`db.py:783`),
`aufnahme.nachholen` (`aufnahme.py:1389`), `aufnahme.MAX_VERSUCHE = 5` (`aufnahme.py:77`),
`aufnahme.NACHHOL_INTERVALL_S = 60` (`aufnahme.py:76`).

---

## Hotspots — Dateien, die A1/A2 ebenfalls anfassen

Wer hier arbeitet, rebased vor dem ersten Commit und liest den Konflikt, statt ihn
wegzudruecken.

| Datei | Wer noch | Was dieser Plan dort tut |
|---|---|---|
| `interview_theater/web.py` | A2 (Routing-Weiche in `_beantworte_gruppenseite`/`_beantworte_post`) | `_Basishandler`: `end_headers`, `send_error`, `sys_version`, `server_version`, Catch-all in `do_GET`/`do_POST`, `log_message`-Maskierung, CSP-Nonce |
| `interview_theater/db.py` | A2 (`SCHEMA`: Tabelle `web_post`, `TABELLEN_MIT_CHAT_ID`) | `SCHEMA`: zwei Spalten in `aufruf`, eine in `gruppe` — **rein additiv**, kein `user_version`-Schritt |
| `interview_theater/repo.py` | A2 (`lege_web_post_an` & Co. am Dateiende) | `merke_aufruf` um zwei Parameter, drei neue Funktionen am Dateiende |
| `interview_theater/llm.py` | — | Deckelpruefung vor dem Netzaufruf, `modell`/`kosten_chf` in die Buchung |
| `interview_theater/einstellungen.py` | A2 (drei Felder), A1 | zwei Felder am Ende (`kosten_deckel_chf`, `zeitzone`) |
| `interview_theater/web_chat.py` | A2 (das ganze Modul) | Rate-Limit-Aufruf, Magic-Bytes-Pruefung, Nonce aus dem Header |
| `AGENTS.md`, `docs/betrieb-env.beispiel` | A1, A2 | eigene Abschnitte, ans Ende der jeweiligen Kapitel |

---

## Dateikarte

**Neu:**

| Datei | Verantwortung |
|---|---|
| `interview_theater/kosten.py` | Preistabelle, Kostenrechnung je Aufruf, Tagesgrenze Europe/Rome, `KostendeckelErreicht`, die Pausenmeldung. **Kein SQL** — liest ueber `repo`. Dienste-Schicht. |
| `interview_theater/web_grenze.py` | Das Rate-Limit: gleitendes Fenster im Prozessspeicher, thread-sicher, Schluessel = `chat_id`. **Kein Projektimport** (wie `vorschlagssperre.py`), damit es von jeder Seite importierbar bleibt. |
| `scripts/web_token_neu.py` | Token-Rotation von Hand: Trockenlauf, Backup, Journaleintrag, neue URL. |
| `tests/test_web_kopfzeilen.py` | Angriff: Kopfzeilen ueber alle Routen und Fehlerstatus; Fehlerseite ohne Traceback/Pfad. |
| `tests/test_web_herkunft.py` | Angriff: fremder `Origin`, `Sec-Fetch-Site: cross-site`, POST ohne Nonce, Token in der Logzeile. |
| `tests/test_web_grenze.py` | Das gleitende Fenster als reine Einheit (ohne HTTP). |
| `tests/test_web_chat_flut.py` | Angriff: 50 Nachrichten in 10 s, 21 Uploads ueber der Stundengrenze. |
| `tests/test_web_chat_upload.py` | Angriff: Upload ueber der Grenze, falscher Typ, gefaelschte `Content-Length`. |
| `tests/test_web_token_rotation.py` | Angriff: altes Token, alter Nonce am neuen Token. |
| `tests/test_kosten.py` | Preistabelle, Mitternacht Europe/Rome, unbekanntes Modell. |
| `tests/test_kostendeckel.py` | Angriff: gemockte Kosten >= 5 CHF → kein Netzaufruf, Pausenmeldung, beide Kanaele. |

**Geaendert:** `interview_theater/web.py`, `web_chat.py`, `db.py`, `repo.py`, `llm.py`,
`szene_claude.py`, `aufnahme.py`, `ablauf.py`, `szene.py`, `kurzgeschichte.py`,
`szenenfolge.py`, `sprachstil.py`, `einstellungen.py`, `sprachen/en/texte.toml`,
`scripts/pruefe_prompts.py`, `AGENTS.md`, `docs/betrieb-env.beispiel`.

---

## Globale Vorgaben

Diese gelten fuer **jede** Aufgabe und werden nicht wiederholt.

1. **Projektsprache Deutsch**: Bezeichner, Docstrings, Kommentare, Commit-Messages. Im Code
   ASCII-Umschrift (`ue/oe/ae/ss`); in Nutzertexten und Markdown duerfen Umlaute stehen, wie
   im bestehenden Code.
2. **SQL nur in `repo.py`, `db.py`, `web_daten.py`** (AGENTS.md). `kosten.py` und
   `web_grenze.py` enthalten **kein** SQL.
3. **Kein neues Paket.** Standardbibliothek plus das schon vorhandene `httpx`.
4. **Kein Modellaufruf** in einem Knopf-Handler, einem Slash-Befehl oder irgendwo im
   Webserver-Prozess (AGENTS.md, Zusage 2).
5. **Migration nur additiv** (`ALTER TABLE ... ADD COLUMN` ueber `SCHEMA`), niemals ein
   Tabellenneubau. `db.SCHEMA_VERSION` bleibt **3** — die neuen Spalten brauchen keine
   Umrechnung, alte Zeilen bleiben NULL.
6. **Kein Prompt aendert sich.** `$PY -m pytest tests/test_profil_bitgleich.py -q` und
   `tests/test_sprache_bitgleich.py` (falls vorhanden) bleiben gruen; ebenso
   `$PY -m scripts.pruefe_profil dortmund-2026`.
7. **Kein bezahlter Aufruf** in einer Aufgabe ausser Aufgabe 11, und die faehrt der Umsetzer
   **nicht ohne Freigabe von Birk**.
8. **Keine Echtdaten.** `betrieb/**` wird nicht gelesen. Tokens erscheinen nie in einer
   Ausgabe, einem Test-Artefakt oder einem Commit.
9. **Tests laufen ohne Netz**, gegen einen echten lokalen `ThreadingHTTPServer` auf Port 0
   und eine Wegwerf-Datenbank unter `tmp_path` — wie `tests/test_web_edit.py:35-46`.
10. **Attribution**: jede Commit-Message endet mit
    `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

**Die Entscheidungen des Architekten (E-S1 bis E-S10) sind gesetzt.** Sie werden umgesetzt
und im Plan begruendet, nicht neu verhandelt. Wo dieser Plan eine Zahl waehlt, die der
Kartentext anders vorschlaegt, steht die Rechnung dabei (Aufgabe 4).

---

## Aufgabenuebersicht

| # | Aufgabe | Liefert |
|---|---|---|
| 0 | Vorbedingungspruefung | Gate: A1+A2 auf `main`, alle Namen da, Baseline gemessen |
| 1 | Kopfzeilen und Fehlerseiten (E-S7, E-S8) | jede Antwort traegt sechs Kopfzeilen; kein Traceback, kein Pfad, keine Version |
| 2 | Herkunft: Origin, Sec-Fetch-Site, Nonce im Header, Log-Maskierung (E-S9) | 403 vor jeder Wirkung; Token nicht mehr voll in der Logzeile |
| 3 | Rate-Limit je Gruppe (E-S4) | `web_grenze.py`, 429 mit `Retry-After` |
| 4 | Upload-Haertung: Groesse und Magic Bytes (E-S5) | 413/415, nichts auf Platte, nichts in der DB |
| 5 | Token-Rotation (E-S6) | `repo.erneuere_web_token`, `scripts/web_token_neu.py` |
| 6 | `kosten.py`: Preise, Spalten, Buchung bei LLM und Claude (E-S1, Teil 1) | `aufruf.modell`, `aufruf.kosten_chf` |
| 7 | Whisper bucht mit (E-S1, Teil 2) | `art='stt'`, Kosten aus der Audiodauer |
| 8 | Deckel, Durchsetzung, Pausenmeldung (E-S2, E-S3) | kein Netzaufruf ueber 5 CHF/Tag, eine klare Meldung, DE+EN |
| 9 | Reviewer-Drehbuch | `curl`-Kommandos mit erwarteter Statuszeile |
| 10 | Doku und nginx-Vorschlag | AGENTS.md, `docs/betrieb-env.beispiel`, Abschlussbericht |
| 11 | **KOSTET GELD — nur mit Freigabe** | Whisper-Preis und Dauerfeld nachmessen |

---

## Aufgabe 0: Vorbedingungspruefung

**Kein Code.** Ein Gate. Wenn es faellt, wird die Karte blockiert, nicht umgangen.

**Dateien:** keine.

**Schnittstellen — Konsumiert:** alles aus der Annahmentabelle oben.

- [ ] **Schritt 1: A2 und A1 sind auf `main`**

```bash
git fetch origin
git merge-base --is-ancestor 9391e8a origin/main && echo "A2-Plan-Commit: ancestor"
git log origin/main --oneline --grep="Padua A2" | head -5
git log origin/main --oneline --grep="Padua A1" | head -5
```

Erwartet: beide `grep`-Laeufe zeigen Umsetzungs-Commits (nicht nur den Plan-Commit `9391e8a`).
Der Plan-Commit allein reicht **nicht** — ein Plan ist kein Code.

Haerter, und das ist die eigentliche Pruefung:

```bash
test -f interview_theater/web_chat.py && echo "web_chat.py da"
test -f interview_theater/web_kanal.py && echo "web_kanal.py da"
test -f interview_theater/sprache.py && echo "sprache.py da"
test -f interview_theater/sprachen/en/texte.toml && echo "texte.toml da"
```

Erwartet: vier Zeilen. Fehlt eine: **stoppen.**

- [ ] **Schritt 2: Jeder uebernommene Name existiert**

Die Kommandos aus der Annahmentabelle, alle auf einmal:

```bash
grep -n "MAX_AUDIO_BYTES\|MAX_DAUER_S\|MAX_TEXT_ZEICHEN\|MIME_ERLAUBT\|CHAT_PFAD" interview_theater/web_chat.py
grep -n "def endung_fuer\|def beantworte_post\|def beantworte_get\|def schreibend\|def _angenommen\|def _gruppe_oder_404\|_POSTWEGE" interview_theater/web_chat.py
grep -n "\"senden\"\|\"knopf\"\|\"audio\"\|\"interview\"" interview_theater/web_chat.py
grep -n "web_post\|RICHTUNG_EIN\|WEB_TYP_TEXT\|WEB_TYP_SPRACHE\|WEB_TYP_KNOPF\|def lege_web_post_an" interview_theater/repo.py
grep -n "class WebKanal\|def eingangspfad" interview_theater/web_kanal.py
grep -n "class Texte" interview_theater/sprache.py
grep -n "MAX_POST_BYTES\|class _Basishandler\|def nonce\|def nonce_gueltig\|def _seite\|def log_message" interview_theater/web.py
grep -n "MAX_UPLOAD_BYTES\|def mime_typ" interview_theater/stt.py
```

Erwartet: **jede** Zeile der Annahmentabelle findet mindestens einen Treffer. Fehlt einer:
**stoppen und die Karte blockieren** mit dem fehlenden Namen im Kommentar. Nicht neu bauen —
ein zweites `MAX_AUDIO_BYTES` neben dem aus A2 waere zwei Grenzen, von denen eine nicht wirkt.

Und die drei Werte muessen stimmen, nicht nur existieren:

```bash
$PY -c "
from interview_theater import web_chat, web, stt
print('MAX_AUDIO_BYTES', web_chat.MAX_AUDIO_BYTES, web_chat.MAX_AUDIO_BYTES == 8*1024*1024)
print('MAX_DAUER_S', web_chat.MAX_DAUER_S, web_chat.MAX_DAUER_S == 3600)
print('MAX_TEXT_ZEICHEN', web_chat.MAX_TEXT_ZEICHEN, web_chat.MAX_TEXT_ZEICHEN == 4000)
print('MAX_POST_BYTES', web.MAX_POST_BYTES, web.MAX_POST_BYTES == 64*1024)
print('MAX_UPLOAD_BYTES', stt.MAX_UPLOAD_BYTES, stt.MAX_UPLOAD_BYTES == 25*1024*1024)
print('POSTWEGE', sorted(web_chat._POSTWEGE))
"
```

Erwartet: fuenfmal `True`, und `POSTWEGE` enthaelt mindestens `audio`, `knopf`, `senden`.
Weicht ein Wert ab, ist er **im Plan** falsch, nicht im Code: dann wird hier notiert, welcher,
und die betroffene Aufgabe rechnet mit dem echten Wert weiter (die Rechnung in Aufgabe 4
zeigt, wie).

- [ ] **Schritt 3: Baseline messen und hier eintragen**

```bash
$PY -m pytest -q -p no:cacheprovider
```

Erwartet: gruen. **Die Zahl hier eintragen** (in diese Datei, Zeile darunter) — jedes
`Erwartet: >= …` der folgenden Aufgaben meint sie:

```
BASELINE NACH A1+A2 (vom Umsetzer einzutragen): ____ passed, ____ skipped
```

Zum Vergleich: vor A1/A2, auf `d144715`, waren es `2768 passed, 1 skipped`.

- [ ] **Schritt 4: Commit**

```bash
git add docs/superpowers/plans/2026-09-30-padua-s-absicherung-web.md
git commit -m "Plan Padua S: Vorbedingung geprueft, Baseline nach A1+A2 eingetragen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 1: Kopfzeilen und Fehlerseiten (E-S7, E-S8)

**Dateien:**
- Aendern: `interview_theater/web.py` (`_Basishandler` ab `web.py:2525`, `mache_handler` ab
  `web.py:2601`)
- Test: `tests/test_web_kopfzeilen.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web.py
SICHERHEITSKOPFZEILEN: tuple[tuple[str, str], ...]   # ohne CSP -- die traegt den Nonce
CSP_VORLAGE: str                                      # mit {nonce}
TEXT_500 = "Da ist bei uns etwas schiefgegangen."
def csp_nonce(schluessel: bytes, token: str, jetzt: float | None = None) -> str
def mit_nonce(html_text: str, nonce_wert: str) -> str
class _Basishandler:
    sys_version = ""
    server_version = "interview-theater"
    schluessel: bytes | None = None      # von mache_handler gesetzt
    praefix: str = ""                    # von mache_handler gesetzt
    def end_headers(self) -> None        # haengt die Kopfzeilen an JEDE Antwort
    def send_error(self, code, message=None, explain=None) -> None
    def _csp_nonce(self) -> str
```

### Der gemessene Ausgangszustand

Selbst gemessen auf `d8deb6c` mit einem lokalen Server (Wegwerf-DB, Port 0):

```
/gesund                 -> 200 | Server: interview-theater Python/3.11.15 | Sicherheitsheader: []
/                       -> 200 | Server: interview-theater Python/3.11.15 | Sicherheitsheader: []
/g/<token>              -> 200 | Server: interview-theater Python/3.11.15 | Sicherheitsheader: []
/g/unbekannt            -> 404 | Server: interview-theater Python/3.11.15 | Sicherheitsheader: []
/nixda                  -> 404 | Server: interview-theater Python/3.11.15 | Sicherheitsheader: []
Ausnahme im Handler     -> RemoteDisconnected (gar keine Antwort), Traceback nach stderr
```

Drei Befunde, alle im Code belegt:

1. **Null Sicherheitskopfzeilen**, auf keiner Route. `_antworte` (`web.py:2567-2588`) sendet
   `Content-Type`, `Content-Length`, optional `Content-Disposition`, `Cache-Control` — mehr
   nicht.
2. **Die Python-Version steht im `Server`-Header.** `web._Basishandler.server_version` ist
   gesetzt (`web.py:2533`), `sys_version` nicht — und `BaseHTTPRequestHandler.sys_version` ist
   `'Python/3.11.15'`. `version_string()` haengt beides aneinander.
3. **Eine Ausnahme im Handler erzeugt gar keine Antwort.** `http.server`
   (`handle_one_request`) faengt sie nicht; `socketserver` schreibt den Traceback nach stderr
   und schliesst die Verbindung. Der Koerper leckt also heute nichts — aber die Seite bricht
   ohne Statuszeile ab, und das sanfte Nachladen
   (`web._SCROLL_JS`, `.catch(function () {})`) schluckt es stumm. Der Catch-all ist damit
   zugleich eine Verbesserung fuer die Gruppe, nicht nur eine Haertung.

### Warum `end_headers` und nicht `_antworte`

`_antworte` deckt nur die eigenen Antworten. `send_error` — von `BaseHTTPRequestHandler`
selbst gerufen bei unbekannter Methode (501), kaputter Anfragezeile (400), zu langer URI
(414) — geht daran vorbei. `end_headers()` laeuft in **beiden** Wegen genau einmal je
Antwort. Deshalb steht die Einhaengung dort: **eine Stelle, jede Antwort**, auch 404, 413,
429, 500, auch `/gesund` und die `.md`/`.txt`-Downloads.

### Warum der CSP-Nonce aus dem Stundenfenster kommt und nicht gewuerfelt wird

Das ist der eine Punkt, an dem eine Standardempfehlung hier falsch waere. Der Ablauf
(gemessen an `web._SCROLL_JS`, `web.py:164` und `web.py:173`):

```js
var letzter = document.body.innerHTML;          // web.py:164
...
if (!neu || neu === letzter) { return; }        // web.py:173
document.body.innerHTML = neu;
```

Die Seite vergleicht alle zehn Sekunden den **ganzen** `<body>` mit dem vorigen und tauscht
ihn nur bei Unterschied. Das `<script>`-Tag steht **im** `<body>` (`web._seite`,
`web.py:601-609`). Ein je Antwort neu gewuerfelter Nonce stuende als Attribut in genau
diesem Tag — der Vergleich schluege bei **jedem** Poll an, die Seite tauschte sich alle zehn
Sekunden aus und risse jedes offene Eingabefeld mit. Das ist wortwoertlich derselbe Fehler,
gegen den der Formular-Nonce schon abgeleitet statt gewuerfelt ist (`web.nonce`,
Docstring `web.py:96-105`).

Also: derselbe Weg, dieselbe Fensterbreite. `csp_nonce` ist ein zweiter HMAC mit **eigenem
Praefix** (`csp:`), damit ein Leck des einen nicht den anderen mitnimmt. Weil beide
Nonces dasselbe `NONCE_FENSTER` (3600 s, `web.py:74`) benutzen, wechseln sie zur selben
Sekunde — die Seite tauscht sich **nicht oefter** aus als heute (heute schon einmal je
Stunde, weil der Formular-Nonce im Body steht).

Ein stundenstabiler Nonce ist schwaecher als ein Einweg-Nonce, aber deutlich staerker als
`'unsafe-inline'`: ein Angreifer, der durch den HTML-Filter der Chatansicht (A2) rutscht,
muesste den HMAC-Wert **raten**, um sein `<script>` ausfuehren zu lassen. Mit
`'unsafe-inline'` muesste er gar nichts. Deshalb Nonce — und `'unsafe-inline'` steht
ausdruecklich **nicht** in der Richtlinie.

Zwei Dinge, die den Weg tragen, beide im Code geprueft:

- `web.py` erzeugt **kein** `style="…"`-Attribut und **kein** `onclick=` (gemessen:
  `grep -c 'style="' interview_theater/web.py` → `0`,
  `grep -c "onclick=\|<img\|<svg" interview_theater/web.py` → `0`). Ein Nonce auf
  `style-src` bricht also nichts. **Faellt dieser Zaehler nach A2 nicht mehr auf 0**, wird
  `style-src` um `'unsafe-inline'` ergaenzt — und `script-src` trotzdem **nicht**.
- Beim Austausch des `<body>` per `innerHTML` fuehrt der Browser eingefuegte `<script>`
  ohnehin nicht aus (HTML-Spezifikation). Das erste Skript laeuft weiter. Der Nonce der
  nachgeladenen Antwort spielt gar keine Rolle.

`mit_nonce` setzt das Attribut nachtraeglich in den fertigen HTML-Text, statt `_seite` eine
Signatur zu geben. Grund: `_seite` hat sechs Aufrufer, und einer davon (`web_chat.chat_html`)
gehoert Karte A2, die zum Zeitpunkt dieses Plans nicht gemergt ist. Eine Signaturaenderung
dort waere ein Eingriff in fremden, ungesehenen Code. Die Ersetzung ist sicher, weil
`_seite` der **einzige** Erzeuger eines literalen `<style>`/`<script>` ist: jeder Text aus
der Gruppe laeuft vorher durch `html.escape` bzw. den Filter aus A2 und kann kein `<`
enthalten. Der Test unten haelt genau das fest.

- [ ] **Schritt 1: Den Angriffstest schreiben (rot ohne Schutz)**

`tests/test_web_kopfzeilen.py`:

```python
"""Angriff: was verraet der Server, und was fehlt an Kopfzeilen?

Vier Angriffe in einer Datei, weil sie dieselbe Antwort haerten:
  1. Es gibt keine Sicherheitskopfzeilen -- eine fremde Seite darf uns in
     einen iframe stellen, ein Crawler darf uns indizieren, der Browser darf
     den Content-Type raten.
  2. Der Server-Header nennt die Python-Version.
  3. Eine Ausnahme im Handler erzeugt heute gar keine Antwort
     (RemoteDisconnected); der Traceback geht nach stderr. Verlangt ist eine
     500 mit festem Kurztext.
  4. Die 404-Seite und die Download-Routen fallen heute aus jeder
     Kopfzeilen-Regel heraus, weil sie an _antworte vorbei oder durch
     send_error laufen.

Gemessen gegen einen echten lokalen ThreadingHTTPServer auf Port 0, wie
tests/test_web_edit.py -- kein Netz nach draussen.
"""

import http.client
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 1
SCHLUESSEL = b"x" * 32

#: Die sechs Kopfzeilen, die auf JEDER Antwort stehen muessen.
PFLICHT = {
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=(self)",
}


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url: str):
    """Statuscode und Kopfzeilen -- auch fuer 4xx/5xx, die urllib wirft."""
    try:
        with urllib.request.urlopen(url, timeout=10) as antwort:
            return antwort.status, dict(antwort.headers), antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, dict(fehler.headers), fehler.read().decode("utf-8")


def _rohanfrage(basis: str, zeile: bytes) -> tuple[int, dict]:
    """Eine Anfrage, die urllib gar nicht erst stellen wuerde -- fuer den
    send_error-Weg der Standardbibliothek (unbekannte Methode -> 501)."""
    wirt, port = basis.removeprefix("http://").split(":")
    verbindung = http.client.HTTPConnection(wirt, int(port), timeout=10)
    verbindung.request("BREW", "/")
    antwort = verbindung.getresponse()
    kopf = dict(antwort.getheaders())
    antwort.read()
    verbindung.close()
    return antwort.status, kopf


# -- 1. Die Kopfzeilen auf jeder Route ------------------------------------


def test_jede_route_traegt_die_pflichtkopfzeilen(aufbau):
    basis, token, _pfad = aufbau
    wege = [
        "/gesund", "/", f"/g/{token}", f"/g/{token}/textbuch",
        f"/g/{token}/leitfaden", f"/g/{token}/textbuch.md",
        f"/g/{token}/textbuch.txt",
        "/g/gibtsnicht", "/nixda", f"/theatersoap/g/{token}",
    ]
    for weg in wege:
        _status, kopf, _text = _hole(basis + weg)
        for name, wert in PFLICHT.items():
            assert kopf.get(name) == wert, (weg, name, kopf.get(name))


def test_auch_die_fehlerseiten_tragen_sie(aufbau):
    """404 laeuft ueber _antworte, 501 ueber send_error der
    Standardbibliothek -- beide muessen dieselben Kopfzeilen tragen, sonst
    ist die Einhaengung an der falschen Stelle."""
    basis, _token, _pfad = aufbau
    status, kopf, _text = _hole(basis + "/nixda")
    assert status == 404
    assert kopf.get("X-Frame-Options") == "DENY"

    status, kopf = _rohanfrage(basis, b"BREW / HTTP/1.1\r\n\r\n")
    assert status == 501
    for name, wert in PFLICHT.items():
        assert kopf.get(name) == wert, (name, kopf.get(name))


# -- 2. Die Richtlinie ohne Fremdquellen ----------------------------------


def test_csp_ohne_fremdquelle_und_mit_den_vier_sperren(aufbau):
    basis, token, _pfad = aufbau
    _status, kopf, _text = _hole(f"{basis}/g/{token}")
    csp = kopf.get("Content-Security-Policy") or ""
    for stueck in ("default-src 'none'", "frame-ancestors 'none'",
                   "base-uri 'none'", "form-action 'self'",
                   "connect-src 'self'", "media-src 'self' blob:"):
        assert stueck in csp, (stueck, csp)
    assert "http://" not in csp and "https://" not in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_der_csp_nonce_steht_an_jedem_inline_tag(aufbau):
    basis, token, _pfad = aufbau
    _status, kopf, text = _hole(f"{basis}/g/{token}")
    csp = kopf.get("Content-Security-Policy") or ""
    marke = csp.split("'nonce-", 1)[1].split("'", 1)[0]
    assert len(marke) >= 16
    assert text.count("<script") == text.count(f'nonce="{marke}"') - text.count("<style")
    assert f'<style nonce="{marke}">' in text
    assert f'<script nonce="{marke}">' in text


def test_der_nonce_bleibt_innerhalb_der_stunde_gleich(aufbau):
    """Der Kern: ein je Antwort gewuerfelter Nonce stuende im <body> und
    liesse das sanfte Nachladen die Seite alle zehn Sekunden austauschen
    (web._SCROLL_JS vergleicht document.body.innerHTML)."""
    basis, token, _pfad = aufbau
    _s1, _k1, erste = _hole(f"{basis}/g/{token}")
    _s2, _k2, zweite = _hole(f"{basis}/g/{token}")
    assert erste == zweite


def test_der_nonce_wechselt_mit_dem_fenster():
    a = web.csp_nonce(SCHLUESSEL, "tok", jetzt=0.0)
    b = web.csp_nonce(SCHLUESSEL, "tok", jetzt=web.NONCE_FENSTER + 1.0)
    assert a != b


def test_csp_nonce_ist_nicht_der_formular_nonce():
    """Zwei Geheimnisse, zwei Ableitungen: ein Leck des einen (der
    Formular-Nonce stand bei A2 in der Query und damit in der Logzeile) darf
    den anderen nicht mitnehmen."""
    assert web.csp_nonce(SCHLUESSEL, "tok", 0.0) != web.nonce(SCHLUESSEL, "tok", 0.0)


def test_mit_nonce_ruehrt_escapten_text_nicht_an():
    """Eine Gruppennachricht mit dem Wort <script> ist beim Rendern
    escaped -- die Ersetzung darf sie nicht treffen."""
    roh = "<style>a{}</style><p>&lt;script&gt;boese&lt;/script&gt;</p><script>x</script>"
    ergebnis = web.mit_nonce(roh, "abc")
    assert ergebnis.count('nonce="abc"') == 2
    assert "&lt;script&gt;boese&lt;/script&gt;" in ergebnis


# -- 3. Der Server verraet seine Version nicht ----------------------------


def test_server_header_ohne_versionsnummer(aufbau):
    basis, _token, _pfad = aufbau
    _status, kopf, _text = _hole(basis + "/gesund")
    assert kopf.get("Server") == "interview-theater"
    assert "Python" not in (kopf.get("Server") or "")
    assert "." not in (kopf.get("Server") or "")


# -- 4. Die Fehlerseite verraet nichts ------------------------------------


def test_ausnahme_im_handler_wird_500_ohne_traceback(aufbau, monkeypatch):
    """Heute: gar keine Antwort (RemoteDisconnected), Traceback nach stderr.
    Verlangt: 500 mit festem Kurztext -- kein 'Traceback', kein '/mnt/',
    kein '.py'."""
    basis, _token, _pfad = aufbau

    def kaputt(*args, **kwargs):
        raise RuntimeError("geheim /mnt/HC_Volume/pfad.py Zeile 7")

    monkeypatch.setattr(web, "dashboard_html", kaputt)
    status, kopf, text = _hole(basis + "/")
    assert status == 500
    assert web.TEXT_500 in text
    for verbotenes in ("Traceback", "/mnt/", ".py", "RuntimeError", "geheim"):
        assert verbotenes not in text, verbotenes
    assert kopf.get("X-Frame-Options") == "DENY"


def test_ausnahme_im_post_wird_ebenfalls_500(aufbau, monkeypatch):
    basis, token, _pfad = aufbau

    def kaputt(*args, **kwargs):
        raise RuntimeError("geheim /mnt/x.py")

    monkeypatch.setattr(web, "_beantworte_post", kaputt)
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            status, text = antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        status, text = fehler.code, fehler.read().decode("utf-8")
    assert status == 500
    assert "Traceback" not in text and "/mnt/" not in text


def test_send_error_gibt_keine_erklaerung_preis(aufbau):
    """Die Vorlage der Standardbibliothek setzt Message und Explain in den
    Koerper (DEFAULT_ERROR_MESSAGE). Beides raus."""
    basis, _token, _pfad = aufbau
    status, _kopf = _rohanfrage(basis, b"BREW / HTTP/1.1\r\n\r\n")
    assert status == 501
    verbindung = http.client.HTTPConnection(
        basis.removeprefix("http://").split(":")[0],
        int(basis.rsplit(":", 1)[1]), timeout=10,
    )
    verbindung.request("BREW", "/")
    antwort = verbindung.getresponse()
    koerper = antwort.read().decode("utf-8", "replace")
    verbindung.close()
    assert "Error code explanation" not in koerper
    assert "Unsupported method" not in koerper
    assert web.TEXT_500 in koerper or koerper.strip() == ""
```

13 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_kopfzeilen.py -q -p no:cacheprovider
```

Erwartet: rot. Konkret zuerst
`AttributeError: module 'interview_theater.web' has no attribute 'csp_nonce'` beim Sammeln
der Datei (die Modulkonstante `PFLICHT` allein bricht noch nicht). Nach dem Entfernen dieser
Zeile blieben die inhaltlichen Fehlschlaege:
`assert kopf.get('Referrer-Policy') == 'no-referrer'` → `None`, und
`test_ausnahme_im_handler_wird_500_ohne_traceback` → `RemoteDisconnected`.

- [ ] **Schritt 3: `web.py` — die Kopfzeilen und der Nonce**

Nach `EIGENE` (`web.py:79`) einfuegen:

```python
#: Die Kopfzeilen, die auf JEDER Antwort stehen -- auch 404, 413, 429, 500,
#: auch /gesund und die .md/.txt-Downloads. Angehaengt in
#: ``_Basishandler.end_headers`` und damit an genau EINER Stelle: ``_antworte``
#: allein wuerde ``send_error`` der Standardbibliothek verfehlen (501 bei
#: unbekannter Methode, 400 bei kaputter Anfragezeile).
#:
#: ``microphone=(self)`` steht hier, weil die Chatansicht (Karte A2) im
#: Browser aufnimmt; alles andere ist nicht aufgezaehlt und damit aus.
SICHERHEITSKOPFZEILEN = (
    ("Referrer-Policy", "no-referrer"),
    ("X-Robots-Tag", "noindex, nofollow"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Permissions-Policy", "microphone=(self)"),
)

#: Die Inhaltsrichtlinie. **Keine Fremdquelle** -- der Workshopraum haengt an
#: einem Tailnet, und eine Seite ohne Login soll nichts nachladen, was
#: jemand anders liefert. ``'unsafe-inline'`` steht bewusst NICHT da: die
#: beiden Inline-Tags aus ``_seite`` bekommen einen Nonce (siehe
#: ``csp_nonce``).
#:
#: ``media-src 'self' blob:`` fuer die Wiedergabe der eigenen Aufnahme im
#: Browser (MediaRecorder liefert einen Blob), ``connect-src 'self'`` fuer
#: das sanfte Nachladen und den Poll.
CSP_VORLAGE = (
    "default-src 'none'; "
    "script-src 'nonce-{nonce}'; "
    "style-src 'nonce-{nonce}'; "
    "img-src 'self' data:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)

#: Was eine unerwartete Ausnahme nach aussen sagt. Ein Satz, kein Pfad, keine
#: Klasse, keine Zeile -- das steht im Log (siehe ``log_error``). Die Gruppe
#: kann daran nichts beheben, aber sie wartet gerade (AGENTS.md: "Die Gruppe
#: erfaehrt von einem Fehler nur, wenn sie ihn beheben kann oder gerade
#: darauf wartet").
TEXT_500 = "Da ist bei uns etwas schiefgegangen."

_HTML_500 = (
    '<!doctype html><html lang="de"><meta charset="utf-8">'
    f"<p>{TEXT_500}</p></html>"
)


def csp_nonce(schluessel: bytes, token: str, jetzt: float | None = None) -> str:
    """Der CSP-Nonce einer Antwort -- **aus dem Stundenfenster abgeleitet**,
    nicht gewuerfelt.

    Das ist die eine Stelle, an der die Standardempfehlung ("ein Nonce je
    Antwort") hier falsch waere. ``_SCROLL_JS`` vergleicht alle zehn Sekunden
    ``document.body.innerHTML`` mit dem vorigen Stand und tauscht den Koerper
    nur bei Unterschied. Das ``<script>``-Tag steht IM Koerper; ein je Antwort
    neuer Nonce stuende als Attribut darin, der Vergleich schluege bei jedem
    Poll an, und die Seite risse alle zehn Sekunden jedes offene Eingabefeld
    mit. Genau dafuer ist schon der Formular-Nonce abgeleitet (siehe
    ``nonce``); hier gilt derselbe Grund und dieselbe Fensterbreite, damit
    beide zur selben Sekunde wechseln.

    Eigenes Praefix ``csp:``: der Formular-Nonce steht beim Audio-Upload in
    einer Kopfzeile und frueher in der Query -- ein Leck des einen darf den
    anderen nicht mitnehmen."""
    jetzt = time.time() if jetzt is None else jetzt
    fenster = int(jetzt) // NONCE_FENSTER
    return hmac.new(
        schluessel, f"csp:{token}:{fenster}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def mit_nonce(html_text: str, nonce_wert: str) -> str:
    """Haengt den Nonce an die beiden Inline-Tags aus ``_seite``.

    **Warum nachtraeglich und nicht als Parameter von ``_seite``:** ``_seite``
    hat sechs Aufrufer, einer davon in ``web_chat`` (Karte A2). Eine
    Signaturaenderung dort waere ein Eingriff in ein Modul, das diese Karte
    sonst nicht anfasst.

    **Warum das sicher ist:** ``_seite`` ist der einzige Erzeuger eines
    literalen ``<style>``/``<script>``. Jeder Text aus der Gruppe laeuft
    vorher durch ``html.escape`` bzw. den Filter aus A2 und traegt ``&lt;``
    statt ``<`` -- ``test_mit_nonce_ruehrt_escapten_text_nicht_an`` haelt das
    fest."""
    return (
        html_text
        .replace("<style>", f'<style nonce="{nonce_wert}">')
        .replace("<script>", f'<script nonce="{nonce_wert}">')
    )
```

- [ ] **Schritt 4: `web.py` — `_Basishandler` haerten**

In `_Basishandler` (ab `web.py:2525`). `server_version` bleibt, `sys_version` kommt dazu:

```python
    server_version = "interview-theater"
    #: Leer, damit ``version_string()`` nicht "interview-theater
    #: Python/3.11.15" liefert. Gemessen: die Vorgabe der
    #: Standardbibliothek ist ``'Python/3.11.15'`` und stand bis heute im
    #: Server-Header jeder Antwort. Eine Versionsnummer ist der erste
    #: Baustein jedes gezielten Angriffs und der Gruppe voellig gleichgueltig.
    sys_version = ""

    #: Von ``mache_handler`` gesetzt. ``_Basishandler`` liest sie nur fuer
    #: den CSP-Nonce -- die Klasse bleibt sonst konfigurationsfrei.
    schluessel: bytes | None = None
    praefix: str = ""
```

Dann, in derselben Klasse:

```python
    def _csp_nonce(self) -> str:
        """Der Nonce dieser Antwort, an das Token der aufgerufenen Seite
        gebunden.

        An das Token, nicht bloss an das Stundenfenster: sonst lernte jeder,
        der das Dashboard im Tailnet oeffnen kann, den Nonce aller
        Gruppenseiten. Ohne Token (Dashboard, /gesund) gilt der leere String
        -- dort gibt es keine Gruppendaten, die eine Einschleusung lohnen."""
        if not self.schluessel:
            return ""
        try:
            pfad = _pfad_ohne_praefix(
                urllib.parse.unquote(urllib.parse.urlsplit(self.path).path),
                self.praefix,
            )
        except Exception:  # noqa: BLE001 -- eine kaputte URL darf hier nichts reissen
            pfad = ""
        token = pfad[len("/g/"):].strip("/").partition("/")[0] if pfad.startswith("/g/") else ""
        return csp_nonce(self.schluessel, token)

    def end_headers(self) -> None:
        """Die **eine** Stelle, an der jede Antwort ihre Kopfzeilen bekommt.

        Nicht in ``_antworte``: ``send_error`` der Standardbibliothek (501
        bei unbekannter Methode, 400 bei kaputter Anfragezeile, 414 bei zu
        langer URI) geht daran vorbei, und genau diese Antworten sind die,
        die niemand von Hand testet."""
        for name, wert in SICHERHEITSKOPFZEILEN:
            self.send_header(name, wert)
        self.send_header(
            "Content-Security-Policy", CSP_VORLAGE.format(nonce=self._csp_nonce())
        )
        super().end_headers()

    def send_error(self, code, message=None, explain=None) -> None:
        """Die Fehlerseite der Standardbibliothek setzt ``%(message)s`` und
        ``%(explain)s`` in den Koerper (``DEFAULT_ERROR_MESSAGE``). Beide
        kommen aus der Anfrage oder aus dem Innenleben des Servers -- also
        weder das eine noch das andere nach aussen."""
        self.send_response(code)
        roh = _HTML_500.encode("utf-8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(roh)

    def _fuenfhundert(self) -> None:
        """Eine unerwartete Ausnahme: 500 mit festem Kurztext.

        Ohne das bekommt der Browser heute gar keine Antwort -- ``http.server``
        faengt eine Ausnahme aus ``do_GET`` nicht ab, ``socketserver`` schreibt
        den Traceback nach stderr und schliesst die Verbindung
        (gemessen 30.09.2026). Der Traceback bleibt im Log, wo er hingehoert."""
        try:
            self._antworte(500, _HTML_500)
        except Exception:  # noqa: BLE001 -- die Verbindung ist schon hin
            self.close_connection = True
```

Und `_antworte` bekommt den Nonce in den HTML-Koerper. In `_antworte`, direkt vor
`roh = inhalt.encode("utf-8")`:

```python
        if typ.startswith("text/html"):
            inhalt = mit_nonce(inhalt, self._csp_nonce())
```

- [ ] **Schritt 5: `web.py` — Catch-all und die Konfiguration an die Klasse**

In `mache_handler` die beiden Methoden umbauen und die zwei Klassenattribute setzen:

```python
    class Handler(_Basishandler):
        #: Fuer ``_csp_nonce`` -- die Konfiguration steht in der Fabrik, die
        #: Basisklasse liest sie nur.
        schluessel = schluessel
        praefix = praefix

        def do_GET(self) -> None:  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
            try:
                _beantworte_get(self, db_pfad, praefix, schluessel)
            except Exception:  # noqa: BLE001 -- der Server darf an keiner Anfrage sterben
                self.log_error("Unbehandelte Ausnahme bei GET: %s", traceback.format_exc())
                self._fuenfhundert()

        def do_POST(self) -> None:  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
            try:
                _beantworte_post(self, db_pfad, praefix, schluessel)
            except Exception:  # noqa: BLE001
                self.log_error("Unbehandelte Ausnahme bei POST: %s", traceback.format_exc())
                self._fuenfhundert()
```

`import traceback` in den Modulkopf.

**Achtung, Namensschatten:** `schluessel = schluessel` im Klassenkoerper liest die
Fabrikvariable und legt sie als Klassenattribut ab — das geht, weil Klassenkoerper keinen
Closure-Scope fuer Zuweisungen bilden wie Funktionen. Dasselbe fuer `praefix`. Wer es
lesbarer mag, schreibt `schluessel = schluessel` vor `def do_GET` und faellt damit nicht
ueber die Reihenfolge.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_kopfzeilen.py -q -p no:cacheprovider
```
Erwartet: `13 passed`.

```
$PY -m pytest tests/test_web.py tests/test_web_edit.py tests/test_web_fassungen.py \
    tests/test_web_textbuch.py tests/test_web_szenenuebersicht.py -q -p no:cacheprovider
```
Erwartet: gruen — die Kopfzeilen aendern keinen Koerper, nur den Kopf.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline aus Aufgabe 0, plus 13.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web.py tests/test_web_kopfzeilen.py
git commit -m "Web: Sicherheitskopfzeilen an einer Stelle, Fehlerseite ohne Traceback

Kopfzeilen in end_headers statt in _antworte -- send_error der
Standardbibliothek (501, 400, 414) geht an _antworte vorbei.
CSP-Nonce aus dem Stundenfenster abgeleitet wie der Formular-Nonce: ein je
Antwort gewuerfelter Nonce stuende im <body> und liesse das sanfte
Nachladen die Seite alle zehn Sekunden austauschen.
sys_version leer -- der Server-Header nannte bis hier die Python-Version.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 2: Herkunft — Origin, Sec-Fetch-Site, Nonce im Header, Log-Maskierung (E-S9)

**Dateien:**
- Aendern: `interview_theater/web.py` (`_Basishandler.log_message` `web.py:2589`,
  `_beantworte_post` `web.py:2472`)
- Aendern: `interview_theater/web_chat.py` (`beantworte_post`, `_audio` — **ANNAHME A-6/A-9**)
- Test: `tests/test_web_herkunft.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web.py
TEXT_FREMDE_HERKUNFT = "Diese Anfrage kommt nicht von dieser Seite."
NONCE_KOPFZEILE = "X-Nonce"
def eigene_herkunft(handler) -> bool
def maskiere_token(pfad: str) -> str
```

**Schnittstellen — Konsumiert:** `web_chat.beantworte_post` (A-6), `web_chat._audio` (A-9),
`web.nonce_gueltig` (`web.py:107`).

### Was heute fehlt und warum der Nonce allein nicht reicht

Der Formular-Nonce (`web.nonce`, Docstring `web.py:87-105`) schuetzt gegen ein POST von einer
fremden Seite, **weil** die fremde Seite unser HTML nicht lesen kann. Das stimmt — solange
niemand den Nonce anderweitig in die Hand bekommt. Zwei Wege, auf denen genau das passiert,
beide im Code:

1. **Der Nonce steht beim Audio-Upload in der Query** (A2-Plan Z. 4331:
   `POST /g/<token>/chat/audio?nonce=…&dauer=…`) und damit in der Serverlogzeile
   (`web._Basishandler.log_message`, `web.py:2589-2598`, `format % args` enthaelt den vollen
   Pfad mit Query). Das ist Punkt 3 der Uebergabe aus A2 (Z. 7123-7125).
2. **Das Token steht ohnehin im Pfad** und damit ebenfalls in jeder Logzeile. Wer das Log
   sieht (Screenshot, `betrieb/web.log` in einem Ticket, ein Blick ueber die Schulter beim
   `tail -f` am Beamer), hat den Link **und** den Nonce.

Origin ist die zweite, unabhaengige Schicht: sie haengt nicht an einem Geheimnis, sondern
daran, **wo der Browser gerade steht**. Ein Angreifer, der Token und Nonce kennt, kommt
damit trotzdem nicht durch den Browser eines Gruppenmitglieds.

**Fehlt `Origin` ganz, entscheidet der Nonce wie bisher.** `curl` schickt keinen, und ein
alter Browser bei einem `application/json`-POST auch nicht — der Reviewer faehrt seine
Angriffe mit `curl` (Aufgabe 9), und ein 403 auf jede `curl`-Anfrage waere ein Werkzeug, das
sich selbst pruefunfaehig macht.

### `Sec-Fetch-Site`

Jeder Browser ab 2020 schickt ihn; `cross-site` heisst: die Seite, von der die Anfrage
ausgeht, liegt auf einer anderen Site. Das ist strenger als der Origin-Vergleich (es faellt
auch bei `Origin: null`, etwa aus einem sandboxed iframe) und kostet zwei Zeilen. Fehlt der
Header, aendert sich nichts.

- [ ] **Schritt 1: Den Angriffstest schreiben (rot ohne Schutz)**

`tests/test_web_herkunft.py`:

```python
"""Angriff: POST von einer fremden Seite -- mit gueltigem Nonce.

Der Nonce schuetzt, WEIL eine fremde Seite unser HTML nicht lesen kann. Er
schuetzt nicht mehr, sobald er anderswo auftaucht: beim Audio-Upload stand er
bis hier in der Query und damit in der Serverlogzeile (A2-Uebergabe Punkt 3),
und das Token steht ohnehin im Pfad. Wer das Log sieht, hat beides.

Deshalb Origin als zweite, unabhaengige Schicht -- sie haengt nicht an einem
Geheimnis, sondern daran, wo der Browser steht.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 1
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_phase(conn, CHAT, 4)
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Eine Nacht im Treppenhaus")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(url: str, koerper: dict, kopf: dict | None = None):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **(kopf or {})},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _gueltig(token: str) -> dict:
    return {"nonce": web.nonce(SCHLUESSEL, token), "feld": "rahmen",
            "wert": "Ein Hinterhof im Regen"}


def _rahmen(pfad: str) -> str | None:
    conn = db.verbinde(pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, CHAT)
        return stand["rahmen"] if stand else None
    finally:
        conn.close()


# -- Der Angriff: fremde Herkunft, gueltiger Nonce ------------------------


def test_fremder_origin_ist_403_trotz_gueltigem_nonce(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Origin": "https://boese.example"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_sec_fetch_site_cross_site_ist_403(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Sec-Fetch-Site": "cross-site"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_eigener_origin_geht_durch(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Origin": basis})
    assert status == 200
    assert _rahmen(pfad) == "Ein Hinterhof im Regen"


def test_ohne_origin_entscheidet_der_nonce_wie_bisher(aufbau):
    """curl und alte Browser schicken keinen Origin. Ein 403 darauf machte
    das Reviewer-Drehbuch (Aufgabe 9) unmoeglich."""
    basis, token, pfad = aufbau
    assert _post(f"{basis}/g/{token}", _gueltig(token))[0] == 200
    assert _rahmen(pfad) == "Ein Hinterhof im Regen"


def test_sec_fetch_site_same_origin_geht_durch(aufbau):
    basis, token, _pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Sec-Fetch-Site": "same-origin"})
    assert status == 200


def test_post_ohne_nonce_bleibt_403(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}",
                          {"feld": "rahmen", "wert": "Ein Hinterhof im Regen"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_die_herkunft_wird_vor_dem_nonce_geprueft(aufbau):
    """E-S9: 'vor jeder Wirkung, auch wenn der Nonce stimmt'. Umgekehrt
    heisst das: ein fremder Origin OHNE Nonce gibt ebenfalls 403 -- und
    zwar mit dem Herkunftstext, nicht mit dem Veraltet-Text."""
    basis, token, _pfad = aufbau
    status, text = _post(f"{basis}/g/{token}",
                         {"feld": "rahmen", "wert": "x"},
                         {"Origin": "https://boese.example"})
    assert status == 403
    assert web.TEXT_FREMDE_HERKUNFT in text


# -- Der Nonce steht nicht mehr in der Logzeile ---------------------------


def test_maskiere_token_kuerzt_auf_vier_zeichen():
    assert web.maskiere_token("/g/abcdefgh1234/chat") == "/g/abcd.../chat"
    assert web.maskiere_token("/theatersoap/g/abcdefgh1234") == "/theatersoap/g/abcd..."
    assert web.maskiere_token("/gesund") == "/gesund"
    assert web.maskiere_token("/") == "/"


def test_maskiere_token_wirft_die_query_weg():
    """Beim Audio-Upload stand der Nonce in der Query (A2). Er steht
    kuenftig in einer Kopfzeile -- und selbst wenn ihn jemand wieder in die
    Query legt, landet er nicht im Log."""
    assert "nonce" not in web.maskiere_token("/g/abcdefgh1234/chat/audio?nonce=xy&dauer=45")


def test_die_logzeile_traegt_weder_token_noch_nonce(aufbau, capsys):
    basis, token, _pfad = aufbau
    _post(f"{basis}/g/{token}", _gueltig(token))
    ausgabe = capsys.readouterr().out
    assert token not in ausgabe
    assert web.nonce(SCHLUESSEL, token) not in ausgabe
    assert token[:4] in ausgabe
```

11 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_herkunft.py -q -p no:cacheprovider
```

Erwartet: rot,
`AttributeError: module 'interview_theater.web' has no attribute 'TEXT_FREMDE_HERKUNFT'`
beim Sammeln; inhaltlich danach
`test_fremder_origin_ist_403_trotz_gueltigem_nonce` mit `assert 200 == 403` — der Angriff
**wirkt** heute: der Rahmen steht danach auf `"Ein Hinterhof im Regen"`.

- [ ] **Schritt 3: `web.py` — die Herkunftspruefung**

Nach `TEXT_500` einfuegen:

```python
#: 403-Text fuer eine Anfrage, die von woanders kommt. Ein Satz, kein
#: Hinweis darauf, WAS nicht gepasst hat -- wer das Formular vor sich hat,
#: sieht diesen Text nie.
TEXT_FREMDE_HERKUNFT = "Diese Anfrage kommt nicht von dieser Seite."

#: Wo der Formular-Nonce beim Audio-Upload steht (E-S9). In der Query stand
#: er in der Serverlogzeile -- und der ist die eine Stelle, an der ein
#: CSRF-Merkmal garantiert aufgeschrieben wird.
NONCE_KOPFZEILE = "X-Nonce"


def eigene_herkunft(handler) -> bool:
    """Kommt diese Anfrage von unserer eigenen Seite?

    **Zwei Merkmale, beide optional, beide streng, wenn sie da sind:**

    * ``Sec-Fetch-Site`` -- jeder Browser ab 2020 schickt ihn.
      ``cross-site`` heisst ausdruecklich "von woanders" und faellt auch bei
      ``Origin: null`` (sandboxed iframe), wo der Vergleich unten nichts
      sagen kann.
    * ``Origin`` -- verglichen gegen den ``Host``-Header. Nicht gegen
      ``IT_WEB_URL``: hinter nginx kommt beim Server der interne Host an, und
      eine Konfiguration, die im Betrieb nicht passt, waere ein 403 auf
      alles.

    **Fehlen beide, ist die Antwort True** und der Nonce entscheidet wie
    bisher. ``curl`` schickt keinen Origin, und das Reviewer-Drehbuch faehrt
    mit ``curl``; ein 403 darauf machte die Pruefung unmoeglich. Das kostet
    nichts: ein Angriff ueber einen Browser TRAEGT die Kopfzeilen, und ein
    Angreifer, der sie weglassen kann, hat ohnehin keinen fremden Browser
    dazwischen -- er braucht dann aber Token und Nonce, und das ist die
    Schicht, die es schon gab."""
    if (handler.headers.get("Sec-Fetch-Site") or "").strip().lower() == "cross-site":
        return False
    herkunft = (handler.headers.get("Origin") or "").strip()
    if not herkunft:
        return True
    wirt = (handler.headers.get("Host") or "").strip()
    if not wirt:
        return False
    eigene = urllib.parse.urlsplit(herkunft).netloc.lower()
    return bool(eigene) and eigene == wirt.lower()


def maskiere_token(pfad: str) -> str:
    """Der Anfragepfad fuer die Logzeile: Token auf vier Zeichen, Query weg.

    Vier Zeichen bleiben stehen, damit man zwei Gruppen im Log
    auseinanderhalten kann -- das ist der ganze Zweck, den das Token dort je
    hatte. Die Query faellt komplett: beim Audio-Upload stand der
    Formular-Nonce darin (A2-Uebergabe Punkt 3), und die Logzeile ist die
    eine Stelle, an der ein CSRF-Merkmal garantiert aufgeschrieben wird."""
    ohne_query = pfad.split("?", 1)[0]
    stelle = ohne_query.find("/g/")
    if stelle < 0:
        return ohne_query
    kopf = ohne_query[: stelle + len("/g/")]
    rest = ohne_query[stelle + len("/g/"):]
    token, trenner, schwanz = rest.partition("/")
    if len(token) <= 4:
        return ohne_query
    return f"{kopf}{token[:4]}...{trenner}{schwanz}"
```

- [ ] **Schritt 4: `web.py` — einhaengen**

In `_beantworte_post` (`web.py:2472`), **direkt nach** der `startswith("/g/")`-Pruefung und
**vor** allem anderen (E-S9: „vor jeder Wirkung, auch wenn der Nonce stimmt"):

```python
    if not eigene_herkunft(handler):
        handler._fehler(403, TEXT_FREMDE_HERKUNFT)
        return
```

**Vor** der Weiche nach `web_chat.beantworte_post` (A2 setzt sie ebenfalls an diese Stelle,
A2-Plan Z. 3468-3480) — dann gilt die Pruefung fuer die Gruppenseite **und** fuer alle
`/chat/*`-Wege, ohne dass `web_chat` sie kennt.

`log_message` (`web.py:2589`) bekommt die Maskierung:

```python
    def log_message(self, format: str, *args) -> None:
        """Eine Zeile je Anfrage nach stdout (systemd haengt das an
        betrieb/web.log). Ohne Uhrzeit-Klammern der Vorlage, dafuer mit
        ISO-Zeit -- damit die Zeilen zu denen des Bots passen.

        **Das Token wird maskiert und die Query weggeworfen** (30.09.2026):
        es ist das einzige Geheimnis der Gruppenseite, und beim Audio-Upload
        stand der Formular-Nonce in der Query. Ein Log ist das, was man
        weiterschickt, wenn etwas nicht geht."""
        zeile = format % args
        for stueck in zeile.split(" "):
            if "/g/" in stueck or "?" in stueck:
                zeile = zeile.replace(stueck, maskiere_token(stueck))
        print(
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} web "
            f"{self.address_string()} {zeile}",
            flush=True,
        )
```

- [ ] **Schritt 5: `web_chat.py` — der Nonce wandert in die Kopfzeile**

**ANNAHME A-9.** In `web_chat._audio` die Nonce-Auswertung umstellen: erst die Kopfzeile,
die Query nur als Rueckfall, damit ein Browser mit altem, gecachtem JavaScript nicht
stehenbleibt.

```python
    felder = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    # Der Nonce steht seit dem 30.09.2026 in einer Kopfzeile statt in der
    # Query (E-S9): eine Query landet in der Serverlogzeile, eine Kopfzeile
    # nicht. Die Query bleibt als Rueckfall, damit ein Telefon mit altem,
    # gecachtem JavaScript den Tag noch zu Ende bringt.
    kennung = handler.headers.get(web.NONCE_KOPFZEILE) or (felder.get("nonce") or [""])[0]
    if not web.nonce_gueltig(schluessel, token, kennung):
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return
```

Und im Browser-JavaScript (A2-Plan Z. 5456, `fetch('chat/audio?nonce=' + …)`) den Nonce in
den Kopf ziehen:

```js
    fetch('chat/audio?dauer=' + sekunden, {
      method: 'POST',
      headers: { 'Content-Type': blob.type, 'X-Nonce': nonce() },
      body: blob
    })
```

**Wenn A2 den `fetch`-Aufruf anders geschrieben hat**, gilt nur die Regel: `dauer` bleibt in
der Query, `nonce` geht in `X-Nonce`. Der Test
`tests/test_web_chat_js.py::test_jeder_fetch_pfad_ist_bekannt` aus A2 (Z. 5101-5111) darf
dabei nicht rot werden — er prueft den Pfad, nicht die Query.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_herkunft.py -q -p no:cacheprovider
```
Erwartet: `11 passed`.

```
$PY -m pytest tests/test_web_chat_audio.py tests/test_web_edit.py -q -p no:cacheprovider
```
Erwartet: gruen. Faellt hier ein A2-Test, weil er den Nonce in der Query erwartet, wird
**der Test** nachgezogen (der Nonce ist umgezogen, das ist die Aenderung), nicht die
Pruefung entfernt.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 24.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web.py interview_theater/web_chat.py tests/test_web_herkunft.py
git commit -m "Web: Herkunftspruefung vor jeder Wirkung, Nonce aus der Logzeile

Origin und Sec-Fetch-Site als zweite Schicht neben dem Nonce: der Nonce
schuetzt, WEIL eine fremde Seite ihn nicht lesen kann -- beim Audio-Upload
stand er in der Query und damit in der Serverlogzeile. Er zieht in X-Nonce
um, die Logzeile maskiert Token und wirft die Query weg.
Fehlt Origin ganz, entscheidet der Nonce wie bisher (curl).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 3: Rate-Limit je Gruppe (E-S4)

**Dateien:**
- Neu: `interview_theater/web_grenze.py`
- Aendern: `interview_theater/web_chat.py` (`beantworte_post` — **ANNAHME A-6**)
- Test: `tests/test_web_grenze.py` (neu), `tests/test_web_chat_flut.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_grenze.py
NACHRICHTEN_JE_MINUTE = 20
NACHRICHTEN_FENSTER_S = 60
UPLOADS_JE_STUNDE = 150
UPLOADS_FENSTER_S = 3600
TOPF_NACHRICHT = "nachricht"
TOPF_UPLOAD = "upload"
GRENZEN: dict[str, tuple[int, int]]        # topf -> (anzahl, fenster_s)
def pruefe(topf: str, schluessel: int, jetzt: float | None = None) -> int
def vergiss() -> None
```

`pruefe` liefert **0**, wenn die Anfrage durchdarf (und zaehlt sie), sonst die Zahl der
Sekunden bis zum naechsten freien Platz (`Retry-After`).

**Schnittstellen — Konsumiert:** `web_chat._POSTWEGE` (A-5), `web_chat.beantworte_post`
(A-6), `web_chat._gruppe_oder_404` (A-12).

### Die Entscheidungen, begruendet

**Schluessel ist `chat_id`, nicht das Token** (E-S4). Sonst setzte eine Token-Rotation
(Aufgabe 5) das Limit zurueck — ein Angreifer koennte den Rotationsweg gar nicht ausloesen,
aber die Gruppe selbst haette nach einer Rotation ein leeres Konto, und der Zaehler meint
die Gruppe, nicht die URL.

**Knopfdruecke kommen in denselben Topf wie Nachrichten.** Die Entscheidung, die E-S4
verlangt, mit ihrem Grund: beide loesen einen Bot-Zug aus, beide kosten einen bezahlten
Modellaufruf, und zwei getrennte Toepfe liessen jemanden abwechseln und die Rate
verdoppeln. Der Umschalter (`/chat/interview`) zaehlt ebenfalls dort — er ist ein Knopf.

**20 Nachrichten je Minute je Gruppe.** Eine Gruppe sind drei bis fuenf Leute an Telefonen;
zwanzig Nachrichten in einer Minute sind schon dicht getippt. Der Abnahmetest verlangt es
genau so: „50 in 10 s" → ab der 21. kommt 429.

**150 Uploads je Stunde je Gruppe**, eigener Topf. Rechnung: A2 schneidet in Segmente von
45 s (`IT_WEB_SEGMENT_MS`, A2-Plan Z. 3440-3446) — eine volle Stunde Interview sind
3600/45 = **80** Uploads. 150 laesst Platz fuer Push-to-talk-Nachrichten nebenher und liegt
trotzdem weit unter dem, was ein Skript in einer Stunde schafft. Eigener Topf, weil ein
Upload eine andere Ressource kostet (Platte und einen bezahlten Whisper-Aufruf) als eine
Textnachricht.

**Gleitendes Fenster, nicht feste Eimer.** Ein fester Minuteneimer laesst 40 Anfragen in zwei
Sekunden zu, wenn sie auf der Minutengrenze liegen. Ein `deque` mit Zeitstempeln kostet bei
diesen Zahlen nichts (hoechstens 150 Eintraege je Gruppe und Topf).

**Im Prozessspeicher.** Ein Neustart des Webdienstes vergisst die Zaehler — **das ist
benannt und akzeptiert**: nginx auf herkules ist die zweite Schicht (Aufgabe 10), und eine
Zaehltabelle in SQLite bedeutete einen Schreibvorgang je Anfrage in eine Datei, die vier
Bot-Prozesse gleichzeitig benutzen.

**Das Limit greift nach der Tokenaufloesung**, weil es die `chat_id` braucht. Eine Flut mit
erfundenen Tokens kostet also weiterhin eine read-only SQLite-Abfrage je Anfrage
(`web_daten.chat_id_nach_token`, `web_daten.py:1044`). Auch das ist nginx' Aufgabe; im Plan
steht es, damit niemand es fuer uebersehen haelt.

- [ ] **Schritt 1: Den Einheitentest schreiben**

`tests/test_web_grenze.py`:

```python
"""Das gleitende Fenster, ohne HTTP.

Ein fester Minuteneimer liesse 40 Anfragen in zwei Sekunden durch, wenn sie
auf der Minutengrenze liegen. Deshalb Zeitstempel und kein Zaehler.

Die Zeit kommt als Parameter herein -- kein sleep in einem Test, der sonst
eine Minute dauerte.
"""

import threading

import pytest

from interview_theater import web_grenze


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


def test_bis_zur_grenze_frei_danach_gesperrt():
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0) == 0, i
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0) > 0


def test_gesperrte_anfragen_zaehlen_nicht_mit():
    """Sonst schoebe eine Flut das Fenster vor sich her und die Gruppe kaeme
    auch nach einer Minute nicht wieder hinein."""
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    for _ in range(100):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1005.0)
    assert web_grenze.pruefe(
        web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0 + web_grenze.NACHRICHTEN_FENSTER_S + 1
    ) == 0


def test_das_fenster_gleitet():
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0 + i)
    # Der aelteste Eintrag (t=1000) faellt bei t=1061 heraus -> genau einer frei.
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1061.0) == 0
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1061.0) > 0


def test_retry_after_zeigt_auf_den_naechsten_freien_platz():
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    warte = web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1010.0)
    assert warte == web_grenze.NACHRICHTEN_FENSTER_S - 10


def test_zwei_gruppen_stoeren_sich_nicht():
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 2, jetzt=1000.0) == 0


def test_zwei_toepfe_stoeren_sich_nicht():
    """Uploads kosten Platte und einen Whisper-Aufruf, Nachrichten einen
    Modellaufruf -- zwei Ressourcen, zwei Zaehler."""
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0) == 0


def test_die_uploadgrenze_deckt_eine_volle_stunde_interview():
    """45-Sekunden-Segmente: 3600/45 = 80 Uploads je Stunde. Die Grenze muss
    darueber liegen, sonst schneidet sie ein Interview ab."""
    assert web_grenze.UPLOADS_JE_STUNDE > 3600 // 45
    for i in range(web_grenze.UPLOADS_JE_STUNDE):
        assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0 + i) == 0
    assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0) > 0


def test_unbekannter_topf_wirft():
    with pytest.raises(KeyError):
        web_grenze.pruefe("gibtsnicht", 1)


def test_nebenlaeufig_wird_nicht_ueberzaehlt():
    """ThreadingHTTPServer bindet je Verbindung einen Thread. Ohne Sperre
    liessen 40 gleichzeitige Anfragen mehr als 20 durch."""
    frei = []
    sperre = threading.Lock()

    def laufe():
        ergebnis = web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
        with sperre:
            frei.append(ergebnis)

    faeden = [threading.Thread(target=laufe) for _ in range(200)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    assert frei.count(0) == web_grenze.NACHRICHTEN_JE_MINUTE


def test_web_grenze_importiert_kein_projektmodul():
    """Wie vorschlagssperre.py: reine Standardbibliothek, damit es von jeder
    Seite importierbar bleibt und nie einen Zyklus baut."""
    import ast
    from pathlib import Path

    quelle = Path(web_grenze.__file__).read_text(encoding="utf-8")
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.ImportFrom):
            assert not (knoten.module or "").startswith("interview_theater"), knoten.module
            assert knoten.level == 0
        if isinstance(knoten, ast.Import):
            for name in knoten.names:
                assert not name.name.startswith("interview_theater"), name.name
```

10 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_grenze.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.web_grenze'`.

- [ ] **Schritt 3: `interview_theater/web_grenze.py` anlegen**

```python
"""Das Rate-Limit der Weboberflaeche: wie oft eine Gruppe etwas schicken darf.

**Warum es das braucht** (Uebergabe 3 der Karte A2): wer den Gruppenlink hat,
kann beliebig viele Nachrichten und Uploads schicken. Jede Nachricht loest
einen bezahlten Modellaufruf aus, jeder Upload bis zu 8 MiB Platte und einen
bezahlten Whisper-Aufruf. Bis hier begrenzte nur ``MAX_TEXT_ZEICHEN`` und
``MAX_AUDIO_BYTES`` das EINZELNE Ereignis, nichts die Rate.

**Schluessel ist die chat_id, nicht das Token.** Eine Token-Rotation
(``scripts/web_token_neu.py``) darf das Limit nicht zuruecksetzen -- gezaehlt
wird die Gruppe, nicht die URL.

**Gleitendes Fenster, keine festen Eimer.** Ein fester Minuteneimer liesse 40
Anfragen in zwei Sekunden durch, wenn sie auf der Minutengrenze liegen. Ein
``deque`` mit Zeitstempeln kostet bei diesen Zahlen nichts: hoechstens
UPLOADS_JE_STUNDE Eintraege je Gruppe und Topf.

**Im Prozessspeicher, und ein Neustart vergisst die Zaehler.** Benannt und
akzeptiert: nginx auf herkules ist die zweite Schicht (``limit_req``, siehe
AGENTS.md), und eine Zaehltabelle in SQLite waere ein Schreibvorgang je
Anfrage in eine Datei, an der vier Bot-Prozesse haengen.

**Kein Projektimport** -- reine Standardbibliothek, wie
``vorschlagssperre.py``. Damit ist das Modul von jeder Seite importierbar und
baut nie einen Zyklus. ``tests/test_web_grenze.py`` haelt das per AST fest.
"""

import threading
import time
from collections import deque

#: Nachrichten und Knopfdruecke je Minute und Gruppe.
#:
#: Ein Topf fuer beide (Entscheidung 30.09.2026): beide loesen einen Bot-Zug
#: mit einem bezahlten Modellaufruf aus, und zwei Toepfe liessen jemanden
#: abwechseln und die Rate verdoppeln. Zwanzig in einer Minute sind fuer
#: drei bis fuenf Leute an Telefonen schon dicht getippt.
NACHRICHTEN_JE_MINUTE = 20
NACHRICHTEN_FENSTER_S = 60

#: Aufnahmesegmente je Stunde und Gruppe. Gerechnet: A2 schneidet in
#: Segmente von 45 s, eine volle Stunde Interview sind also 3600/45 = 80
#: Uploads. 150 laesst Platz fuer Push-to-talk nebenher und liegt trotzdem
#: weit unter dem, was ein Skript in einer Stunde schafft.
UPLOADS_JE_STUNDE = 150
UPLOADS_FENSTER_S = 3600

TOPF_NACHRICHT = "nachricht"
TOPF_UPLOAD = "upload"

GRENZEN = {
    TOPF_NACHRICHT: (NACHRICHTEN_JE_MINUTE, NACHRICHTEN_FENSTER_S),
    TOPF_UPLOAD: (UPLOADS_JE_STUNDE, UPLOADS_FENSTER_S),
}

_SPERRE = threading.Lock()
_ZEITEN: dict[tuple[str, int], deque] = {}


def pruefe(topf: str, schluessel: int, jetzt: float | None = None) -> int:
    """Darf diese Anfrage durch? ``0`` heisst ja (und zaehlt sie mit), sonst
    die Sekunden bis zum naechsten freien Platz (fuer ``Retry-After``).

    **Eine abgewiesene Anfrage zaehlt nicht mit.** Sonst schoebe eine Flut
    das Fenster vor sich her, und die Gruppe kaeme auch nach einer Minute
    nicht wieder hinein -- aus einem Rate-Limit waere eine Dauersperre
    geworden.

    Die Sperre umfasst Lesen, Aufraeumen und Anhaengen: ``ThreadingHTTPServer``
    bindet je Verbindung einen Thread, und ohne sie liessen 40 gleichzeitige
    Anfragen mehr als ``NACHRICHTEN_JE_MINUTE`` durch."""
    anzahl, fenster = GRENZEN[topf]
    jetzt = time.monotonic() if jetzt is None else jetzt
    with _SPERRE:
        zeiten = _ZEITEN.setdefault((topf, schluessel), deque())
        while zeiten and zeiten[0] <= jetzt - fenster:
            zeiten.popleft()
        if len(zeiten) < anzahl:
            zeiten.append(jetzt)
            return 0
        return max(1, int(zeiten[0] + fenster - jetzt))


def vergiss() -> None:
    """Alle Zaehler leeren. Nur fuer Tests."""
    with _SPERRE:
        _ZEITEN.clear()
```

- [ ] **Schritt 4: Lauf, die Einheit ist gruen**

```
$PY -m pytest tests/test_web_grenze.py -q -p no:cacheprovider
```
Erwartet: `10 passed`.

- [ ] **Schritt 5: Den Angriffstest ueber HTTP schreiben**

`tests/test_web_chat_flut.py`:

```python
"""Angriff: 50 Nachrichten in 10 Sekunden.

Ohne Rate-Limit landen alle 50 in web_post, und der Bot arbeitet 50
bezahlte Modellaufrufe ab. Verlangt: hoechstens 20 mal 202, der Rest 429 --
und genau 20 Zeilen in der Eingangstabelle. Die zweite Zahl ist die
wichtigere: ein 429, nach dem die Zeile trotzdem steht, waere kein Schutz,
sondern eine Luege.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_grenze

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


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
    yield basis, token, pfad
    dienst.shutdown()


def _senden(basis, token, text):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/senden",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), "text": text}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status, dict(antwort.headers)
    except urllib.error.HTTPError as fehler:
        kopf = dict(fehler.headers)
        fehler.read()
        return fehler.code, kopf


def _laden(basis, token):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?dauer=45", data=WEBM, method="POST",
        headers={"Content-Type": "audio/webm", web.NONCE_KOPFZEILE: web.nonce(SCHLUESSEL, token)},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _eingang(pfad):
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = ? AND richtung = ?",
            (CHAT, repo.RICHTUNG_EIN),
        ).fetchone()["n"]
    finally:
        conn.close()


def test_fuenfzig_nachrichten_in_zehn_sekunden(aufbau):
    basis, token, pfad = aufbau
    ergebnisse = [_senden(basis, token, f"Nachricht {i}")[0] for i in range(50)]
    assert ergebnisse.count(202) == web_grenze.NACHRICHTEN_JE_MINUTE
    assert ergebnisse.count(429) == 50 - web_grenze.NACHRICHTEN_JE_MINUTE
    assert _eingang(pfad) == web_grenze.NACHRICHTEN_JE_MINUTE


def test_die_ersten_zwanzig_gehen_durch_die_einundzwanzigste_nicht(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        assert _senden(basis, token, f"x{i}")[0] == 202, i
    assert _senden(basis, token, "einundzwanzig")[0] == 429


def test_die_absage_traegt_retry_after(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    status, kopf = _senden(basis, token, "zuviel")
    assert status == 429
    assert kopf.get("Retry-After", "").isdigit()
    assert 0 < int(kopf["Retry-After"]) <= web_grenze.NACHRICHTEN_FENSTER_S


def test_knoepfe_zaehlen_in_denselben_topf(aufbau):
    """Sonst liesse sich abwechseln und die Rate verdoppeln."""
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/knopf",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token),
                         "message_id": 1, "data": "k:1"}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=10)
    assert fehler.value.code == 429


def test_uploads_haben_einen_eigenen_topf(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    assert _laden(basis, token) == 202


def test_ueber_der_uploadgrenze_kommt_429_und_nichts_auf_die_platte(aufbau, tmp_path):
    basis, token, pfad = aufbau
    for _ in range(web_grenze.UPLOADS_JE_STUNDE):
        assert _laden(basis, token) == 202
    assert _laden(basis, token) == 429
    dateien = list((tmp_path / "audio").rglob("*.webm"))
    assert len(dateien) == web_grenze.UPLOADS_JE_STUNDE


def test_eine_zweite_gruppe_ist_nicht_betroffen(aufbau):
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Die Zweiten")
    repo.setze_gruppe_kanal(conn, CHAT + 1, "web")
    zweites = repo.stelle_web_token_sicher(conn, CHAT + 1)
    conn.commit()
    conn.close()
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    assert _senden(basis, token, "zuviel")[0] == 429
    assert _senden(basis, zweites, "wir sind neu")[0] == 202


def test_lesen_wird_nicht_begrenzt(aufbau):
    """Das Limit haengt am POST. Ein GET auf die Chatansicht kostet nur eine
    read-only Abfrage -- und der Poll laeuft alle zwei Sekunden."""
    basis, token, _pfad = aufbau
    for _ in range(60):
        with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0", timeout=10) as a:
            assert a.status == 200


def test_ein_vorfall_je_fenster_und_nicht_je_anfrage(aufbau):
    basis, token, pfad = aufbau
    for i in range(50):
        _senden(basis, token, f"x{i}")
    conn = db.verbinde(pfad)
    try:
        anzahl = conn.execute(
            "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ? AND art = ?",
            (CHAT, "web_rate_limit"),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert anzahl == 1
```

9 Testfunktionen.

- [ ] **Schritt 6: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_flut.py -q -p no:cacheprovider
```
Erwartet: rot — `test_fuenfzig_nachrichten_in_zehn_sekunden` mit
`assert 50 == 20`: alle fuenfzig gehen heute durch, und `_eingang(pfad)` steht auf `50`.

- [ ] **Schritt 7: `web_chat.py` — das Limit einhaengen**

**ANNAHME A-5/A-6.** In `beantworte_post`, **nach** `_gruppe_oder_404` (die `chat_id` wird
gebraucht) und **vor** dem Aufruf des Handlers:

```python
#: Welcher POST-Weg in welchen Topf zaehlt. Senden, Knopf und Umschalter
#: teilen sich einen: alle drei loesen einen Bot-Zug mit einem bezahlten
#: Modellaufruf aus, und zwei Toepfe liessen jemanden abwechseln und die
#: Rate verdoppeln. Audio hat einen eigenen -- ein Upload kostet Platte und
#: einen bezahlten Whisper-Aufruf, eine andere Ressource.
_TOEPFE = {
    "senden": web_grenze.TOPF_NACHRICHT,
    "knopf": web_grenze.TOPF_NACHRICHT,
    "interview": web_grenze.TOPF_NACHRICHT,
    "audio": web_grenze.TOPF_UPLOAD,
}

_TEXT_ZU_SCHNELL = "Das war zu viel auf einmal — einen Moment, dann wieder."
```

und in `beantworte_post`:

```python
    chat_id = _gruppe_oder_404(handler, db_pfad, token)
    if chat_id is None:
        return
    # Das Rate-Limit steht VOR dem Handler und damit vor jeder Wirkung:
    # eine abgewiesene Nachricht darf weder in web_post landen noch eine
    # Datei auf die Platte legen.
    warte = web_grenze.pruefe(_TOEPFE[unterpfad], chat_id)
    if warte:
        _zu_schnell(handler, db_pfad, chat_id, warte)
        return
    try:
        _POSTWEGE[unterpfad](handler, db_pfad, token, chat_id, schluessel)
    ...
```

Dazu die Absage:

```python
def _zu_schnell(handler, db_pfad: str, chat_id: int, warte: int) -> None:
    """429 mit ``Retry-After`` und einem Satz.

    Der Vorfall geht **einmal je Fenster** in die Datenbank, nicht je
    Anfrage: eine Flut von fuenfzig schriebe sonst dreissig Zeilen und faerbte
    das Dashboard rot, ohne mehr zu sagen als eine. Gemerkt wird an der
    Sperre selbst (ein Zaehler-Topf mit Fenstergroesse 1), damit dafuer keine
    zweite Buchhaltung noetig ist."""
    handler.send_response(429)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    roh = _TEXT_ZU_SCHNELL.encode("utf-8")
    handler.send_header("Content-Length", str(len(roh)))
    handler.send_header("Retry-After", str(warte))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(roh)
    if web_grenze.pruefe(web_grenze.TOPF_VORFALL, chat_id) == 0:
        try:
            with schreibend(db_pfad) as conn:
                repo.merke_vorfall(
                    conn, chat_id, None, "web_rate_limit",
                    f"Rate-Limit gegriffen, {warte}s bis zum naechsten Platz",
                )
        except Exception:  # noqa: BLE001 -- ein Vorfall darf die Absage nie mitreissen
            log.exception("Vorfall zum Rate-Limit nicht geschrieben, chat_id=%s", chat_id)
```

Dafuer bekommt `web_grenze` einen dritten Topf:

```python
#: Nur fuer die Vorfall-Drosselung: ein Eintrag je Fenster. Steht hier und
#: nicht als zweite Buchhaltung in web_chat -- es ist genau dieselbe Frage
#: ("wie oft in einem Zeitraum"), und eine zweite Antwort darauf waere eine
#: zweite Wahrheit.
TOPF_VORFALL = "vorfall"
```

und in `GRENZEN`: `TOPF_VORFALL: (1, NACHRICHTEN_FENSTER_S)`.

Importe in `web_chat.py`: `from interview_theater import web_grenze`, `import logging`,
`log = logging.getLogger(__name__)` (falls A2 das nicht schon hat).

**`_TEXT_ZU_SCHNELL` ist eine `_TEXT_*`-Konstante** und kommt damit automatisch in die
Uebersetzungstabelle (Aufgabe 8, A1-Mechanik).

- [ ] **Schritt 8: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_grenze.py tests/test_web_chat_flut.py -q -p no:cacheprovider
```
Erwartet: `19 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 43.

- [ ] **Schritt 9: Commit**

```bash
git add interview_theater/web_grenze.py interview_theater/web_chat.py \
        tests/test_web_grenze.py tests/test_web_chat_flut.py
git commit -m "Web: Rate-Limit je Gruppe, gleitendes Fenster im Prozess

Schluessel ist die chat_id und nicht das Token -- eine Rotation darf das
Limit nicht zuruecksetzen. Senden, Knopf und Umschalter teilen einen Topf
(sonst laesst sich abwechseln und die Rate verdoppeln), Audio hat einen
eigenen: 150/h decken eine volle Stunde 45-Sekunden-Segmente (80) mit Luft.
Eine abgewiesene Anfrage zaehlt nicht mit, sonst wird aus dem Limit eine
Dauersperre. Ein Vorfall je Fenster, nicht je Anfrage.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 4: Upload — Groesse hart, Typ an den Magic Bytes (E-S5)

**Dateien:**
- Aendern: `interview_theater/web_chat.py` (`_audio`, neue Funktion `endung_aus_bytes`)
- Test: `tests/test_web_chat_upload.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/web_chat.py
MAGISCHE_ANFAENGE: tuple[tuple[str, callable], ...]   # Endung -> Pruefer
def endung_aus_bytes(kopf: bytes) -> str | None
```

**Schnittstellen — Konsumiert:** `web_chat.MAX_AUDIO_BYTES` (A-1), `MAX_DAUER_S` (A-2),
`endung_fuer` (A-4), `_audio` (A-9), `stt.mime_typ` (`stt.py:73`),
`web_kanal.eingangspfad` (A-16).

### Die Zahl, die dieser Plan nimmt — mit Rechnung

Der Kartentext schlaegt **25 MB / 15 min** vor. Dieser Plan nimmt **8 MiB je Segment** und
laesst **`MAX_DAUER_S = 3600`** stehen. Warum:

| Groesse | Rechnung |
|---|---|
| Opus 32 kbit/s, 45 s Segment | 45 × 32 000 / 8 = 180 000 B ≈ **176 KiB** |
| Safari mp4/AAC 64 kbit/s, 45 s | 45 × 64 000 / 8 = 360 000 B ≈ **352 KiB** |
| A2-Grenze **8 MiB** | rund **23-faches** des schlechteren Falls |
| `stt.MAX_UPLOAD_BYTES` = **25 MiB** (`stt.py:44`) | die Grenze, ab der **Whisper** ablehnt |

25 MB waere also nicht die App-Grenze, sondern die **Decke des Anbieters**. Eine Datei, die
Whisper ohnehin zurueckweist, soll gar nicht erst ankommen — deshalb liegt die App-Grenze
darunter, nicht darauf. 8 MiB laesst dem uebelsten Browser das Dreiundzwanzigfache und
kostet im schlechtesten Fall 8 MiB Speicher je gleichzeitigem Upload.

**Die Dauer bleibt bei 3600 s, und das ist kein Versehen.** Sie wird vom **Client** gemeldet
(A2-Plan Z. 4616-4620: *„Dauer vom Client gemeldet"*) und ist damit **kein Schutz** — wer
luegen will, luegt. Sie wird geprueft (`400` ausserhalb `0 < d <= MAX_DAUER_S`), weil ein
Unsinnswert weiter unten Entscheidungen traegt (`aufnahme.HINWEIS_AB_S = 60`,
`aufnahme.py:95`: eine lange Sprachnachricht ohne Interviewmodus wird gefragt statt
gedeutet). Sie von 3600 auf 900 zu senken haette also **keine** Schutzwirkung gekauft,
sondern nur eine zweite Zahl erzeugt, die jemand spaeter fuer eine Grenze haelt. Die Grenze,
die traegt, ist die Groesse: 8 MiB sind bei 32 kbit/s rund **35 Minuten** Audio — die
Groesse deckelt die reale Dauer schon unterhalb der Stunde.

**Sollte Aufgabe 0 gemessen haben, dass A2 andere Werte traegt**, gilt dieselbe Rechnung mit
den echten Zahlen; die Pruefungen unten benutzen ausschliesslich `web_chat.MAX_AUDIO_BYTES`
und `web_chat.MAX_DAUER_S`, nie ein Literal.

### Warum Magic Bytes und nicht der Content-Type

`endung_fuer` (A2) liest den `Content-Type`-**Header** — also das, was der Absender
behauptet. Daran haengt die Dateiendung, und an der Endung haengt der MIME-Typ, den Whisper
sieht (`stt.mime_typ`, `stt.py:73`). Das ist **Falle 3** aus AGENTS.md, woertlich:

> Ein fest verdrahtetes `audio/ogg` fuer eine WAV-Datei wird vom Anbieter mit einer
> `batch_id` quittiert — kein HTTP-Fehler, keine Ablehnung — der Auftrag bleibt danach aber
> dauerhaft auf `pending` und laeuft ins Zeitbudget: 89,7 s statt 2,0 s. Im Betrieb ist das
> nur als „haengt" sichtbar.

Ein Absender, der `Content-Type: audio/ogg` zu einer WebM-Datei schickt, erzeugt genau
diesen Zustand — **einmal je Upload, bezahlt**. Der Header ist dafuer die falsche Quelle.
Die Magic Bytes stehen in der Datei und luegen nicht.

Also: Header als **billiger Vorfilter** (415 ohne den Koerper zu lesen), Magic Bytes als
**Entscheidung** (415 nach dem Lesen), und die Endung, die weitergegeben wird, kommt aus den
Magic Bytes.

### Die Reihenfolge der Pruefungen

```
Herkunft (Aufgabe 2)  -> 403   Kopfzeile, kostet nichts
Nonce                 -> 403   Kopfzeile, kostet nichts
Rate-Limit (Aufg. 3)  -> 429   Speicher, kostet nichts
Content-Type (Header) -> 415   Kopfzeile, kostet nichts  <- billiger Vorfilter
Content-Length        -> 413   Kopfzeile, KEIN Lesen     <- die harte Groessengrenze
Koerper lesen (genau Content-Length Bytes, nie mehr)
gelesene Bytes == Content-Length -> 400
Magic Bytes           -> 415   jetzt erst, mit Daten     <- die Entscheidung
Dauer                 -> 400
schreiben
```

Bei 413 wird **nichts** gelesen und die Verbindung geschlossen (`Connection: close`): ein
ungelesener Rumpf in einer HTTP/1.1-Keep-alive-Verbindung brächte die naechste Anfrage
durcheinander.

- [ ] **Schritt 1: Den Angriffstest schreiben (rot ohne Schutz)**

`tests/test_web_chat_upload.py`:

```python
"""Angriff auf den Upload: zu gross, falscher Typ, gelogene Laenge.

Der gefaehrlichste der drei ist der falsche Typ, und zwar nicht wegen HTTP:
die Endung entscheidet ueber den MIME-Typ, den Whisper sieht (AGENTS.md,
Falle 3). Ein WebM als .ogg abgelegt laesst den Auftrag dauerhaft auf
'pending' stehen -- 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
sichtbar, und bezahlt. A2 liest dafuer den Content-Type-HEADER, also das,
was der Absender behauptet.

Jeder Test prueft zwei Dinge: den Statuscode UND dass nichts auf der Platte
und nichts in der Datenbank steht. Ein 413, nach dem die Datei trotzdem
liegt, waere kein Schutz.
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, stt, web, web_chat, web_grenze

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32

#: Echte Dateianfaenge. WEBM ist ein EBML-Kopf (MediaRecorder in
#: Chrome/Firefox), MP4 hat 'ftyp' ab Byte 4 (Safari), OGG faengt mit 'OggS'
#: an (Telegram-Sprachnachricht), WAV mit RIFF/WAVE, MP3 mit ID3 oder einem
#: Frame-Sync.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
OGG = b"OggS" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 200
WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 200
MP3_ID3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 200
MP3_SYNC = b"\xff\xfb\x90\x00" + b"\x00" * 200


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


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


def _lade(basis, token, koerper, typ="audio/webm", dauer=45, laenge=None):
    kopf = {"Content-Type": typ, web.NONCE_KOPFZEILE: web.nonce(SCHLUESSEL, token)}
    if laenge is not None:
        kopf["Content-Length"] = str(laenge)
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?dauer={dauer}", data=koerper,
        method="POST", headers=kopf,
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _zeilen(pfad):
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = ?", (CHAT,)
        ).fetchone()["n"]
    finally:
        conn.close()


# -- Die Erkennung an den Magic Bytes -------------------------------------


@pytest.mark.parametrize("kopf,endung", [
    (WEBM, ".webm"), (OGG, ".ogg"), (MP4, ".m4a"),
    (WAV, ".wav"), (MP3_ID3, ".mp3"), (MP3_SYNC, ".mp3"),
])
def test_echte_dateianfaenge_werden_erkannt(kopf, endung):
    assert web_chat.endung_aus_bytes(kopf) == endung


@pytest.mark.parametrize("kopf", [
    b"", b"\x00" * 64, b"<!doctype html><html>", b"%PDF-1.4",
    b"\x89PNG\r\n\x1a\n", b"PK\x03\x04", b"\x7fELF", b"#!/bin/sh\n",
    b"\x1a\x45\xdf",                      # EBML, aber ein Byte zu kurz
])
def test_alles_andere_gibt_none(kopf):
    assert web_chat.endung_aus_bytes(kopf) is None


def test_jede_erkannte_endung_ist_stt_bekannt():
    """Sonst raet ``mimetypes.guess_type``, und im schlechten Fall kommt
    ``application/octet-stream`` bei Whisper an (Falle 3)."""
    from pathlib import Path

    for kopf in (WEBM, OGG, MP4, WAV, MP3_ID3, MP3_SYNC):
        endung = web_chat.endung_aus_bytes(kopf)
        assert stt.mime_typ(Path(f"x{endung}")) != "application/octet-stream", endung


# -- Der Angriff: falscher Typ --------------------------------------------


def test_html_als_audio_deklariert_ist_415(aufbau):
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, b"<!doctype html>" + b"x" * 500,
                          typ="audio/webm")
    assert status == 415
    assert _zeilen(pfad) == 0
    assert not list(verzeichnis.rglob("*")) or not any(
        p.is_file() for p in verzeichnis.rglob("*")
    )


def test_webm_als_ogg_deklariert_bekommt_die_webm_endung(aufbau):
    """Der Kern von Falle 3: nicht 415, sondern die RICHTIGE Endung. Der
    Absender hat sich geirrt (oder gelogen), die Datei ist in Ordnung -- und
    Whisper bekommt, was wirklich drinsteht."""
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, WEBM, typ="audio/ogg")
    assert status == 202
    dateien = [p.name for p in verzeichnis.rglob("*") if p.is_file()]
    assert len(dateien) == 1 and dateien[0].endswith(".webm")


def test_unbekannter_content_type_wird_ohne_lesen_abgewiesen(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    for typ in ("text/html", "application/octet-stream", "video/mp4", ""):
        status, _text = _lade(basis, token, WEBM, typ=typ)
        assert status == 415, typ
    assert _zeilen(pfad) == 0


# -- Der Angriff: zu gross ------------------------------------------------


def test_upload_ueber_der_grenze_ist_413_und_nichts_bleibt(aufbau):
    basis, token, pfad, verzeichnis = aufbau
    zuviel = WEBM + b"\x00" * (web_chat.MAX_AUDIO_BYTES + 1 - len(WEBM))
    status, _text = _lade(basis, token, zuviel)
    assert status == 413
    assert _zeilen(pfad) == 0
    assert not any(p.is_file() for p in verzeichnis.rglob("*"))


def test_genau_auf_der_grenze_geht_noch(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    genau = WEBM + b"\x00" * (web_chat.MAX_AUDIO_BYTES - len(WEBM))
    assert _lade(basis, token, genau)[0] == 202
    assert _zeilen(pfad) == 1


def test_gelogene_content_length_legt_nichts_an(aufbau):
    """Content-Length sagt 'klein', der Koerper ist gross. Gelesen wird
    genau Content-Length Bytes und nie mehr -- der Rest bleibt im Socket und
    die Verbindung wird geschlossen."""
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, WEBM + b"\x00" * 5000, laenge=len(WEBM))
    # Entweder 202 mit genau len(WEBM) Bytes auf der Platte, oder 400 --
    # was nicht passieren darf, ist eine Datei mit 5000 Bytes mehr.
    assert status in (202, 400)
    for datei in verzeichnis.rglob("*"):
        if datei.is_file():
            assert datei.stat().st_size == len(WEBM)


def test_leerer_koerper_ist_400(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    assert _lade(basis, token, b"")[0] == 400
    assert _zeilen(pfad) == 0


# -- Der Angriff: Unsinnsdauer --------------------------------------------


@pytest.mark.parametrize("dauer", ["0", "-5", "abc", "", "99999999"])
def test_unsinnige_dauer_ist_400(aufbau, dauer):
    basis, token, pfad, _verzeichnis = aufbau
    assert _lade(basis, token, WEBM, dauer=dauer)[0] == 400
    assert _zeilen(pfad) == 0


def test_die_dauergrenze_kommt_aus_der_konstante(aufbau):
    basis, token, _pfad, _verzeichnis = aufbau
    assert _lade(basis, token, WEBM, dauer=web_chat.MAX_DAUER_S)[0] == 202
    assert _lade(basis, token, WEBM, dauer=web_chat.MAX_DAUER_S + 1)[0] == 400


def test_die_groessengrenze_liegt_unter_der_whisper_grenze():
    """Eine Datei, die Whisper ohnehin ablehnt, soll gar nicht erst
    ankommen."""
    assert web_chat.MAX_AUDIO_BYTES < stt.MAX_UPLOAD_BYTES
```

10 Testfunktionen plus drei parametrisierte Saetze (6 + 9 + 5 Faelle) = **30 Testlaeufe**.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_chat_upload.py -q -p no:cacheprovider
```
Erwartet: rot, `AttributeError: module 'interview_theater.web_chat' has no attribute
'endung_aus_bytes'`. Nach dem Ausklammern der reinen Erkennungstests bleibt der
inhaltliche Fehlschlag: `test_html_als_audio_deklariert_ist_415` mit `assert 202 == 415` —
und eine HTML-Datei liegt danach als `.webm` im Audioverzeichnis.

- [ ] **Schritt 3: `web_chat.py` — die Magic Bytes**

```python
#: Dateianfaenge, an denen sich ein Audioformat wirklich erkennen laesst --
#: Endung zuerst, dann der Pruefer.
#:
#: **Warum nicht der Content-Type-Header:** der sagt, was der Absender
#: behauptet. An der Endung haengt der MIME-Typ, den Whisper sieht
#: (``stt.mime_typ``), und ein falscher laesst den Auftrag dauerhaft auf
#: 'pending' stehen -- 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
#: sichtbar, und bezahlt (AGENTS.md, Falle 3). Der Header bleibt als
#: billiger Vorfilter (415, ohne den Koerper zu lesen); entscheiden tun die
#: Bytes.
#:
#: Die Reihenfolge ist Absicht: der MP3-Frame-Sync steht zuletzt, weil er
#: mit zwei Bytes die unschaerfste Regel ist.
MAGISCHE_ANFAENGE = (
    # EBML -- WebM/Matroska, das Format von MediaRecorder in Chrome/Firefox.
    (".webm", lambda k: k[:4] == b"\x1a\x45\xdf\xa3"),
    # OggS -- Opus/Vorbis, auch die Telegram-Sprachnachricht.
    (".ogg", lambda k: k[:4] == b"OggS"),
    # ISO-BMFF: 'ftyp' ab Byte 4, davor die Boxlaenge. mp4/m4a, Safari.
    (".m4a", lambda k: len(k) >= 12 and k[4:8] == b"ftyp"),
    # RIFF....WAVE
    (".wav", lambda k: len(k) >= 12 and k[:4] == b"RIFF" and k[8:12] == b"WAVE"),
    # ID3-Tag am Anfang.
    (".mp3", lambda k: k[:3] == b"ID3"),
    # MPEG-Frame-Sync: elf gesetzte Bits. Zuletzt, weil am unschaerfsten.
    (".mp3", lambda k: len(k) >= 2 and k[0] == 0xFF and (k[1] & 0xE0) == 0xE0),
)

#: Wie viele Bytes vom Anfang fuer die Erkennung reichen. Zwoelf genuegen
#: allen Regeln oben; gelesen wird trotzdem der ganze (begrenzte) Koerper --
#: haeppchenweise zu lesen brachte hier nichts und macht die Groessenpruefung
#: unuebersichtlich.
MAGISCHE_BYTES = 12

_TEXT_FEHLER_INHALT = "Diese Datei ist keine Audioaufnahme."


def endung_aus_bytes(kopf: bytes) -> str | None:
    """Die Endung aus dem Dateianfang, oder None.

    Eine **Allowlist**: was hier nicht steht, kommt nicht durch. Und die
    Endung, die hier herauskommt, ist die, unter der die Datei abgelegt wird
    -- ``stt.mime_typ`` leitet den MIME-Typ fuer Whisper daraus ab."""
    if not isinstance(kopf, (bytes, bytearray)) or not kopf:
        return None
    for endung, passt in MAGISCHE_ANFAENGE:
        try:
            if passt(bytes(kopf)):
                return endung
        except (IndexError, TypeError):
            continue
    return None
```

- [ ] **Schritt 4: `web_chat.py` — `_audio` umbauen**

**ANNAHME A-9.** Die Pruefungen in der Reihenfolge von oben. `_audio` wird dabei zu:

```python
def _audio(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Ein Aufnahmesegment aus dem Browser.

    Reihenfolge der Pruefungen: **Nonce, Content-Type, Content-Length, lesen,
    Magic Bytes, Dauer, schreiben.** Alles, was aus einer Kopfzeile zu
    entscheiden ist, steht vor dem Lesen -- der Koerper kostet bis zu
    MAX_AUDIO_BYTES Speicher. Herkunft und Rate-Limit sind schon vorbei
    (``web._beantworte_post`` und ``beantworte_post``).

    **Der Content-Type ist ein Vorfilter, keine Entscheidung** (30.09.2026).
    Er sagt, was der Absender behauptet; abgelegt wird unter der Endung aus
    den Magic Bytes. Ein WebM mit ``Content-Type: audio/ogg`` landet als
    ``.webm`` -- sonst sieht Whisper ``audio/ogg`` zu einer WebM-Datei und
    der Auftrag bleibt dauerhaft auf 'pending' (Falle 3)."""
    from interview_theater import web

    felder = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    kennung = handler.headers.get(web.NONCE_KOPFZEILE) or (felder.get("nonce") or [""])[0]
    if not web.nonce_gueltig(schluessel, token, kennung):
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return

    # Vorfilter: was schon im Kopf nicht nach Audio aussieht, kostet uns
    # nicht einmal das Lesen.
    if endung_fuer(handler.headers.get("Content-Type")) is None:
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
        # NICHTS lesen. Und die Verbindung schliessen: ein ungelesener
        # Rumpf in einer Keep-alive-Verbindung brächte die naechste Anfrage
        # durcheinander.
        handler.close_connection = True
        handler._fehler(413, _TEXT_FEHLER_GROSS)
        return

    # Genau ``laenge`` Bytes, nie mehr -- ``laenge`` ist oben gedeckelt.
    koerper = handler.rfile.read(laenge)
    if len(koerper) != laenge:
        handler.close_connection = True
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return

    # Jetzt erst die Entscheidung, mit Daten statt mit einer Behauptung.
    endung = endung_aus_bytes(koerper[:MAGISCHE_BYTES])
    if endung is None:
        handler._fehler(415, _TEXT_FEHLER_INHALT)
        return

    roh_dauer = (felder.get("dauer") or [""])[0]
    if not roh_dauer.isdigit() or not 0 < int(roh_dauer) <= MAX_DAUER_S:
        handler._fehler(400, _TEXT_FEHLER_DAUER)
        return

    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
            dauer=int(roh_dauer), mime=stt.mime_typ(Path(f"x{endung}")),
        )
        ziel = web_kanal.eingangspfad(_audio_verz(), chat_id, message_id, endung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(koerper)
        repo.setze_web_datei(conn, message_id, str(ziel))
    _angenommen(handler, {"message_id": message_id})
```

Zwei Aenderungen an dem, was A2 hier hatte, beide absichtlich:

1. Die **Dauer** wird nach den Magic Bytes geprueft statt davor. Grund: eine Datei, die gar
   keine Audiodatei ist, soll 415 bekommen und nicht 400 — der Absender soll die *erste*
   Wahrheit ueber seine Anfrage erfahren, und ein 400 auf eine HTML-Datei mit Dauer 0 waere
   die falsche.
2. Die Spalte `mime` kommt aus `stt.mime_typ(Path(f"x{endung}"))` statt aus dem Header
   (`haupttyp(handler)`). **Eine Wahrheit, nicht zwei:** die Datei liegt unter `endung`, und
   `mime` soll dasselbe sagen. `haupttyp` bleibt als Funktion stehen, falls A2 sie anderswo
   benutzt.

Importe in `web_chat.py`: `from pathlib import Path`, `from interview_theater import stt`.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_chat_upload.py -q -p no:cacheprovider
```
Erwartet: `30 passed`.

```
$PY -m pytest tests/test_web_chat_audio.py -q -p no:cacheprovider
```
Erwartet: gruen. Prueft ein A2-Test, dass eine Datei mit beliebigem Inhalt und richtigem
Header angenommen wird (`b"\x00" * 200`), wird **der Test** nachgezogen: er beschreibt das
Verhalten von vor dieser Karte. Der Fixture-Wert `WEBM` aus dem A2-Plan (Z. 4371:
`b"\x1a\x45\xdf\xa3" + b"\x00" * 200`) ist schon ein echter EBML-Kopf und laeuft durch.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 73.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_chat.py tests/test_web_chat_upload.py
git commit -m "Web-Upload: Groesse hart, Typ an den Magic Bytes statt am Header

Der Content-Type sagt, was der Absender behauptet -- und an der daraus
abgeleiteten Endung haengt der MIME-Typ, den Whisper sieht. Ein WebM als
.ogg abgelegt laesst den Auftrag dauerhaft auf 'pending' stehen (Falle 3),
bezahlt und im Betrieb nur als 'haengt' sichtbar. Header bleibt Vorfilter,
entschieden wird an den Bytes.
Ueber der Groessengrenze wird NICHTS gelesen (413, Verbindung zu); 8 MiB
liegen klar unter stt.MAX_UPLOAD_BYTES -- was Whisper ohnehin ablehnt, soll
gar nicht erst ankommen.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 5: Token-Rotation (E-S6)

**Dateien:**
- Aendern: `interview_theater/repo.py` (neue Funktion, bei `stelle_web_token_sicher`
  `repo.py:124`)
- Neu: `scripts/web_token_neu.py`
- Test: `tests/test_web_token_rotation.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/repo.py
def erneuere_web_token(conn: sqlite3.Connection, chat_id: int) -> str | None
```

**Schnittstellen — Konsumiert:** `repo.stelle_web_token_sicher` (`repo.py:124`),
`repo.WEB_TOKEN_BYTES`, `repo.merke_journal` (fuer den Journaleintrag),
`scripts/web_links.py` (Ausgabeform), `scripts/interviews_uebernehmen.py:395-406`
(`_backup`).

### Nachweis: der Webserver haelt kein Token im Speicher

Selbst gelesen, drei Stellen, alle ohne Zwischenspeicher:

| Stelle | Datei:Zeile | Was sie tut |
|---|---|---|
| `Handler._gruppe` | `web.py:2652-2657` | oeffnet je Anfrage `web_daten.oeffne_lesend`, fragt, schliesst |
| `web_daten.chat_id_nach_token` | `web_daten.py:1044-1063` | ein `SELECT ... WHERE web_token = ?` je Aufruf |
| `web_daten.gruppe_nach_token` | `web_daten.py:1066-1090` | dasselbe, mit `SELECT *` |

Es gibt **keinen** Cache und keine gehaltene Verbindung. Ein rotiertes Token ist mit der
naechsten Anfrage tot — **kein Neustart der Unit noetig**, und keine Cache-Invalidierung zu
planen. (Die Bot-Prozesse haben ihrerseits keinen Lesepfad auf `web_token` ausser
`stelle_web_token_sicher`, das ein vorhandenes Token unangetastet zurueckgibt.)

### Der alte Nonce stirbt mit

`web.nonce(schluessel, token)` (`web.py:85-105`) bindet den HMAC an den Token-String. Ein
Nonce, der zum alten Token gehoert, ist fuer das neue keiner — `nonce_gueltig` vergleicht
beide Stundenfenster gegen `_nonce_roh(schluessel, token, fenster)` mit dem **neuen** Token.
Kein zusaetzlicher Code, aber ein Test: das ist die Art Eigenschaft, die beim naechsten Umbau
lautlos verschwindet.

### Kein Chat-Befehl

Rotieren heisst: jedes Telefon im Raum verliert seinen Link. Das ist eine Betreiberhandlung
mit Ansage, keine, die aus einer Nachricht folgt — wie `scripts/loeschen.py` und
`scripts/interviews_uebernehmen.py`. Der **Grund**, es ueberhaupt zu haben: ein Link wandert
in der Probe von Hand zu Hand (AGENTS.md zur Probenansicht), landet in einem Chat, einem
Screenshot, einem Foto von der Leinwand. Bis heute gab es dagegen nichts.

- [ ] **Schritt 1: Den Angriffstest schreiben (rot ohne Schutz)**

`tests/test_web_token_rotation.py`:

```python
"""Angriff: der alte Link nach einer Rotation.

Ein Gruppenlink hat kein Login; das Token IST das Geheimnis. Es wandert in
der Probe von Hand zu Hand, landet in einem Screenshot, auf einem Foto von
der Leinwand. Bis hier gab es keinen Weg, es zu wechseln.

Geprueft wird die ganze Kette: altes Token -> 404 (GET und POST), neues
Token -> 200, und der Nonce des alten Tokens gilt am neuen nicht.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 1
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_phase(conn, CHAT, 4)
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Eine Nacht im Treppenhaus")
    alt = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, alt, pfad
    dienst.shutdown()


def _hole(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _post(url, koerper):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            antwort.read()
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _rotiere(pfad):
    conn = db.verbinde(pfad)
    try:
        return repo.erneuere_web_token(conn, CHAT)
    finally:
        conn.close()


# -- Die Funktion ---------------------------------------------------------


def test_erneuern_gibt_ein_neues_token(aufbau):
    _basis, alt, pfad = aufbau
    neu = _rotiere(pfad)
    assert neu and neu != alt
    assert len(neu) >= 32


def test_erneuern_ist_nicht_idempotent(aufbau):
    """Zweimal rotieren gibt zwei verschiedene Token -- anders als
    ``stelle_web_token_sicher``, das ein vorhandenes stehen laesst."""
    _basis, _alt, pfad = aufbau
    assert _rotiere(pfad) != _rotiere(pfad)


def test_erneuern_einer_unbekannten_gruppe_gibt_none(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    assert repo.erneuere_web_token(conn, 999) is None
    conn.close()


def test_andere_gruppen_bleiben_unberuehrt(aufbau):
    _basis, _alt, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    fremdes = repo.stelle_web_token_sicher(conn, 2)
    conn.commit()
    conn.close()
    _rotiere(pfad)
    conn = db.verbinde(pfad)
    try:
        assert repo.stelle_web_token_sicher(conn, 2) == fremdes
    finally:
        conn.close()


# -- Der Angriff: der alte Link -------------------------------------------


def test_der_alte_link_ist_sofort_404(aufbau):
    basis, alt, pfad = aufbau
    assert _hole(f"{basis}/g/{alt}") == 200
    neu = _rotiere(pfad)
    assert _hole(f"{basis}/g/{alt}") == 404
    assert _hole(f"{basis}/g/{neu}") == 200


def test_alle_unterseiten_des_alten_links_sind_404(aufbau):
    basis, alt, pfad = aufbau
    _rotiere(pfad)
    for weg in ("", "/textbuch", "/leitfaden", "/textbuch.md", "/textbuch.txt"):
        assert _hole(f"{basis}/g/{alt}{weg}") == 404, weg


def test_post_auf_den_alten_link_ist_404(aufbau):
    basis, alt, pfad = aufbau
    nonce_alt = web.nonce(SCHLUESSEL, alt)
    _rotiere(pfad)
    status = _post(f"{basis}/g/{alt}",
                   {"nonce": nonce_alt, "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 404
    conn = db.verbinde(pfad)
    try:
        assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Eine Nacht im Treppenhaus"
    finally:
        conn.close()


def test_der_alte_nonce_gilt_am_neuen_token_nicht(aufbau):
    """Der Nonce ist an den Token-String gebunden (web.nonce). Diese
    Eigenschaft traegt die Rotation -- und verschwindet beim naechsten Umbau
    lautlos, wenn sie kein Test festhaelt."""
    basis, alt, pfad = aufbau
    nonce_alt = web.nonce(SCHLUESSEL, alt)
    neu = _rotiere(pfad)
    status = _post(f"{basis}/g/{neu}",
                   {"nonce": nonce_alt, "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 403
    conn = db.verbinde(pfad)
    try:
        assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Eine Nacht im Treppenhaus"
    finally:
        conn.close()


def test_mit_dem_neuen_nonce_geht_es_wieder(aufbau):
    basis, _alt, pfad = aufbau
    neu = _rotiere(pfad)
    status = _post(f"{basis}/g/{neu}",
                   {"nonce": web.nonce(SCHLUESSEL, neu),
                    "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 200


def test_der_webserver_haelt_kein_token_im_speicher(aufbau):
    """Kein Neustart der Unit noetig: jede Anfrage oeffnet ihre eigene
    read-only Verbindung (web.py:2652, web_daten.py:1044). Der Test faehrt
    die Rotation gegen einen LAUFENDEN Server."""
    basis, alt, pfad = aufbau
    assert _hole(f"{basis}/g/{alt}") == 200
    neu = _rotiere(pfad)
    assert _hole(f"{basis}/g/{alt}") == 404
    assert _hole(f"{basis}/g/{neu}") == 200


# -- Das Skript -----------------------------------------------------------


def test_das_skript_ist_ohne_ja_ein_trockenlauf(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://beispiel.invalid/theatersoap")
    web_token_neu.main([str(CHAT)])
    ausgabe = capsys.readouterr().out
    assert "Trockenlauf" in ausgabe
    assert _hole(f"{basis}/g/{alt}") == 200


def test_das_skript_gibt_kein_altes_token_aus(aufbau, monkeypatch, capsys):
    """Das alte Token ist nach der Rotation wertlos, aber es steht in
    Screenshots von frueher -- es gehoert nicht noch einmal in eine
    Terminalausgabe, die jemand weiterschickt."""
    from scripts import web_token_neu

    _basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    web_token_neu.main([str(CHAT), "--ja"])
    ausgabe = capsys.readouterr().out
    assert alt not in ausgabe


def test_das_skript_rotiert_und_legt_ein_backup_an(aufbau, monkeypatch, capsys, tmp_path):
    from scripts import web_token_neu

    basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://beispiel.invalid/theatersoap")
    web_token_neu.main([str(CHAT), "--ja"])
    ausgabe = capsys.readouterr().out
    assert "https://beispiel.invalid/theatersoap/g/" in ausgabe
    assert _hole(f"{basis}/g/{alt}") == 404
    assert list(tmp_path.glob("t.db.bak-*"))


def test_das_skript_schreibt_einen_journaleintrag_ohne_token(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    _basis, _alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    web_token_neu.main([str(CHAT), "--ja"])
    capsys.readouterr()
    conn = db.verbinde(pfad)
    try:
        neu = repo.stelle_web_token_sicher(conn, CHAT)
        eintraege = [z["text"] for z in repo.hole_journal(conn, CHAT, 20)]
    finally:
        conn.close()
    assert any("Zugangslink" in t for t in eintraege)
    assert not any(neu in t for t in eintraege)


def test_das_skript_verweigert_eine_unbekannte_gruppe(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    _basis, _alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    with pytest.raises(SystemExit) as beendet:
        web_token_neu.main(["999999", "--ja"])
    assert beendet.value.code != 0
```

15 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_token_rotation.py -q -p no:cacheprovider
```
Erwartet: rot,
`AttributeError: module 'interview_theater.repo' has no attribute 'erneuere_web_token'` und
`ModuleNotFoundError: No module named 'scripts.web_token_neu'`.

- [ ] **Schritt 3: `repo.py` — `erneuere_web_token`**

Direkt hinter `stelle_web_token_sicher` (`repo.py:148`):

```python
@_gesperrt
def erneuere_web_token(conn: sqlite3.Connection, chat_id: int) -> str | None:
    """Gibt der Gruppe ein neues Web-Token -- der alte Link ist danach tot.

    Die Gegenstueck-Funktion zu ``stelle_web_token_sicher``: die legt an,
    wenn nichts da ist, und laesst ein vorhandenes stehen; diese hier
    ersetzt ein vorhandenes. Deshalb **ohne** ``WHERE web_token IS NULL`` --
    die Bedingung dort macht das Anlegen atomar, hier wuerde sie die
    Rotation verhindern.

    Der Aufrufer ist ``scripts/web_token_neu.py``, von Hand und mit Ansage:
    rotieren heisst, dass jedes Telefon im Raum seinen Link verliert. Es gibt
    bewusst keinen Chat-Befehl dafuer (wie bei ``loesche_gruppe``).

    Liefert None, wenn es die Gruppe nicht gibt."""
    zeile = conn.execute(
        "SELECT chat_id FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if zeile is None:
        return None
    neu = secrets.token_urlsafe(WEB_TOKEN_BYTES)
    conn.execute(
        "UPDATE gruppe SET web_token = ? WHERE chat_id = ?", (neu, chat_id)
    )
    conn.commit()
    return neu
```

- [ ] **Schritt 4: `scripts/web_token_neu.py` anlegen**

```python
"""Betreiberskript: gibt einer Gruppe ein neues Web-Token. Der alte Link ist
danach sofort tot.

**Wozu.** Der Gruppenlink hat kein Login -- das Token IST das Geheimnis. Es
wandert in der Probe von Hand zu Hand (siehe die Probenansicht in AGENTS.md),
landet in einem Screenshot, auf einem Foto von der Leinwand, in einem
weitergeleiteten Chat. Bis zum 30.09.2026 gab es dagegen nichts.

**Kein Chat-Befehl.** Rotieren heisst, dass jedes Telefon im Raum seinen Link
verliert; das ist eine Betreiberhandlung mit Ansage, keine, die aus einer
Nachricht folgt -- wie ``scripts/loeschen.py``.

**Kein Neustart noetig.** Der Webserver haelt kein Token im Speicher: jede
Anfrage oeffnet ihre eigene read-only Verbindung
(``web.py`` ``Handler._gruppe``, ``web_daten.chat_id_nach_token``). Die
naechste Anfrage mit dem alten Link bekommt 404.

Aufruf::

    IT_DB=betrieb/soap.db python -m scripts.web_token_neu <chat_id>          # Trockenlauf
    IT_DB=betrieb/soap.db python -m scripts.web_token_neu <chat_id> --ja     # wirklich

Umgebung: ``IT_DB`` (Pflicht), ``IT_WEB_URL`` (Vorgabe wie
``scripts/web_links.py``).
"""

import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo

#: Derselbe Vorgabewert wie in scripts/web_links.py -- eine zweite Zahl waere
#: eine zweite Wahrheit.
VORGABE_URL = "https://lab.artesmobiles.art/theatersoap"

#: Der Journaltext. **Ohne Token**, weder altes noch neues: das Journal geht
#: in den Gespraechs-Prompt (kontext._baue_journal) und steht auf der
#: Gruppenseite. Ein Geheimnis gehoert in keines von beidem.
TEXT_JOURNAL = "Zugangslink der Gruppenseite erneuert (Betreiber)."


def _backup(db_pfad: str) -> str | None:
    """Kopie der Datenbank neben das Original, wie
    ``scripts/interviews_uebernehmen.py``. Eine Rotation ist nicht
    umkehrbar: ohne Backup ist der alte Link weg, auch wenn er noch
    gebraucht wuerde."""
    quelle = Path(db_pfad)
    if not quelle.is_file():
        return None
    ziel = quelle.with_name(f"{quelle.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(quelle, ziel)
    return str(ziel)


def main(argumente: list[str] | None = None) -> None:
    argumente = sys.argv[1:] if argumente is None else argumente
    wirklich = "--ja" in argumente
    stellen = [a for a in argumente if not a.startswith("-")]
    if len(stellen) != 1 or not stellen[0].lstrip("-").isdigit():
        print("Aufruf: python -m scripts.web_token_neu <chat_id> [--ja]", file=sys.stderr)
        sys.exit(2)
    chat_id = int(stellen[0])

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)
    basis = os.environ.get("IT_WEB_URL", VORGABE_URL).rstrip("/")

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    try:
        gruppe = repo.hole_gruppe(conn, chat_id)
        if gruppe is None:
            print(f"Keine Gruppe mit chat_id {chat_id}.", file=sys.stderr)
            sys.exit(1)
        titel = gruppe["titel"] or f"Gruppe {chat_id}"

        if not wirklich:
            # Das ALTE Token wird nicht ausgegeben -- es ist noch gueltig.
            print(f"Trockenlauf. Mit --ja bekaeme '{titel}' ({gruppe['bot_name']}) "
                  f"einen neuen Zugangslink; der bisherige waere sofort tot.")
            print("Kein Backup, keine Aenderung.")
            return

        sicherung = _backup(db_pfad)
        if sicherung:
            print(f"Backup: {sicherung}")
        neu = repo.erneuere_web_token(conn, chat_id)
        repo.merke_journal(conn, chat_id, "entschieden", TEXT_JOURNAL, quelle="skript")
        print(f"{titel}  ({gruppe['bot_name']})")
        print(f"  {basis}/g/{neu}")
        print("Der bisherige Link ist ab sofort 404. Kein Neustart noetig.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

**Falls `repo.merke_journal` eine andere Signatur hat** (der Name steht in `repo.py`, die
Parameter sind hier aus dem Web-Schreibpfad uebernommen — `web_schreiben.py` haengt je
Aenderung einen Eintrag mit `art 'entschieden'` und `quelle 'web'` an, AGENTS.md): die echte
Signatur nehmen. Was nicht verhandelbar ist: **kein Token im Journaltext**.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_token_rotation.py -q -p no:cacheprovider
```
Erwartet: `15 passed`.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 88.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/repo.py scripts/web_token_neu.py tests/test_web_token_rotation.py
git commit -m "Token-Rotation: repo.erneuere_web_token und scripts/web_token_neu.py

Der Gruppenlink hat kein Login -- das Token IST das Geheimnis, und es wandert
in der Probe von Hand zu Hand. Bis hier gab es keinen Weg, es zu wechseln.
Kein Chat-Befehl (Betreiberhandlung mit Ansage, wie loeschen.py), kein
Neustart noetig (der Webserver haelt kein Token im Speicher), kein Token im
Journaleintrag oder in der Ausgabe.
Der alte Nonce ist an den alten Token-String gebunden und damit ebenfalls
tot -- mit Test, weil so eine Eigenschaft beim naechsten Umbau lautlos
verschwindet.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 6: `kosten.py` — Preise im Paket, zwei Spalten, Buchung bei LLM und Claude (E-S1)

**Dateien:**
- Neu: `interview_theater/kosten.py`
- Aendern: `interview_theater/db.py` (`SCHEMA`, Tabelle `aufruf` ab `db.py:705`)
- Aendern: `interview_theater/repo.py` (`merke_aufruf` `repo.py:2788`, eine neue Lesefunktion)
- Aendern: `interview_theater/llm.py` (`_anfrage` `llm.py:252`, das `finally` `llm.py:316`)
- Aendern: `interview_theater/szene_claude.py` (`_buche` `szene_claude.py:157`)
- Aendern: `scripts/pruefe_prompts.py` (`PREISE_CHF_JE_MIO_TOKEN` `:97`, `kosten_chf` `:695`)
- Test: `tests/test_kosten.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/kosten.py
PREISE_CHF_JE_MIO_TOKEN: dict[str, tuple[float, float]]
PREISE_STAND = "04.09.2026"
WHISPER_CHF_JE_MINUTE = 0.006
WHISPER_STAND = "30.09.2026"
CLAUDE_CHF_JE_AUFRUF = 0.0
def kosten_chf(modell: str, eingabe_token: int, ausgabe_token: int) -> float | None
def teuerster_preis() -> tuple[float, float]
def kosten_oder_teuerster(conn, chat_id, bot_name, modell, eingabe_token, ausgabe_token) -> float
def stt_kosten_chf(dauer_s: float | int | None) -> float

# interview_theater/repo.py
def merke_aufruf(..., modell: str | None = None, kosten_chf: float | None = None) -> None
def kostensumme_seit(conn, chat_id: int, ab_iso: str) -> float
```

**Schnittstellen — Konsumiert:** `repo.merke_vorfall` (`repo.py:373`), `repo._jetzt`
(`repo.py:57`).

### Warum beim Buchen und nicht beim Lesen

Die Karte nimmt an, die Kosten stuenden schon in `aufruf`. Sie stehen nicht dort (siehe
„Die Praemisse der Karte ist falsch"). Sie **nachtraeglich** auszurechnen ist nicht nur
Arbeit, sondern unmoeglich: `aufruf` traegt keine Modellspalte, und `LLM.schema` waehlt das
Modell je Aufruf (`llm.py:169-192`) — der Absichtserkenner laeuft mit gemma, das Gespraech
mit Kimi, beide mit `modus='A'`. Aus `art` allein folgt das Modell nicht.

Also zwei additive Spalten. `modell` **und** `kosten_chf`, nicht nur eine:

- `modell` allein hiesse, den Preis bei jeder Abfrage neu anzuwenden — und eine
  Preisaenderung ruecktdatierte alle alten Zeilen.
- `kosten_chf` allein hiesse, spaeter nicht mehr nachvollziehen zu koennen, **warum** eine
  Zeile so teuer war.

Zusammen sind sie die Buchhaltung: was gelaufen ist, und was es gekostet hat.

### Unbekanntes Modell → teuerster Preis, nicht 0

`scripts/pruefe_prompts.kosten_chf` liefert heute `None` fuer ein unbekanntes Modell
(`:700-701`, Docstring: *„lieber keine Zahl als eine erfundene"*). Fuer einen **Bericht** ist
das richtig. Fuer einen **Deckel** ist es die falsche Richtung: ein unbekanntes Modell mit
0 CHF zu buchen hiesse, dass jemand die Grenze umgeht, indem er ein Modell einsetzt, das
nicht in der Tabelle steht — und genau das passiert beim naechsten Modellwechsel, ohne dass
es jemand merkt. Deshalb im Betriebspfad: **teuerster Preis der Tabelle plus Vorfall.** Das
Verhalten von `kosten_chf` selbst bleibt unveraendert (`None`), damit `pruefe_prompts` seinen
Bericht wie bisher schreibt; die konservative Variante ist eine zweite Funktion.

### Claude = 0 CHF, an einer Stelle

**ANNAHME A-19.** *Birk bestaetigt, dass Claude-Proxy-Aufrufe nicht gegen den 5-CHF-Deckel
zaehlen.* Der Grund steht im Docstring von `szene_claude.prosa` (`szene_claude.py:91-92`):
der Proxy laeuft ueber ein Abonnement. Der Wert steht als **eine** Konstante
(`CLAUDE_CHF_JE_AUFRUF = 0.0`) — wird aus dem Abo eine Abrechnung, ist das eine Zeile, nicht
eine Suche.

### Der Umzug der Preistabelle

`scripts/pruefe_prompts.py` behaelt die Namen und importiert sie aus dem Paket. Ein Test
haelt fest, dass die Zahlen **zeichengleich** dieselben sind — sonst haette der Bericht bald
andere Preise als der Deckel.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_kosten.py`:

```python
"""Die Kostenrechnung: Preise, Tagesgrenze, unbekanntes Modell.

Der Ausgangspunkt ist ein Befund, kein Wunsch: die Tabelle ``aufruf`` trug
bis zum 30.09.2026 weder Modell noch Kosten (db.py:705-717), und Whisper
buchte gar nicht. Eine Kostenrechnung im Nachhinein war deshalb unmoeglich --
aus ``art`` folgt das Modell nicht, ``LLM.schema`` waehlt es je Aufruf.
"""

import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from interview_theater import db, kosten, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Die Ankommenden")
    yield verbindung
    verbindung.close()


# -- Die Preistabelle -----------------------------------------------------


def test_die_preise_stehen_im_paket_und_im_skript_gleich():
    """Zwei Tabellen waeren zwei Wahrheiten: der Bericht rechnete mit
    anderen Preisen als der Deckel."""
    from scripts import pruefe_prompts

    assert pruefe_prompts.PREISE_CHF_JE_MIO_TOKEN is kosten.PREISE_CHF_JE_MIO_TOKEN


def test_kosten_eines_bekannten_modells():
    # gemma: 0.20 Eingabe, 0.40 Ausgabe je Million.
    assert kosten.kosten_chf("google/gemma-4-31B-it", 1_000_000, 0) == pytest.approx(0.20)
    assert kosten.kosten_chf("google/gemma-4-31B-it", 0, 1_000_000) == pytest.approx(0.40)
    assert kosten.kosten_chf("google/gemma-4-31B-it", 0, 0) == 0.0


def test_unbekanntes_modell_gibt_none():
    """Unveraendert gegenueber scripts/pruefe_prompts -- fuer einen BERICHT
    ist 'lieber keine Zahl als eine erfundene' richtig."""
    assert kosten.kosten_chf("gibtsnicht/modell-9", 1000, 1000) is None


def test_teuerster_preis_ist_das_maximum_je_richtung():
    eingabe, ausgabe = kosten.teuerster_preis()
    assert eingabe == max(p[0] for p in kosten.PREISE_CHF_JE_MIO_TOKEN.values())
    assert ausgabe == max(p[1] for p in kosten.PREISE_CHF_JE_MIO_TOKEN.values())


def test_unbekanntes_modell_wird_teuerst_gerechnet_und_vermerkt(conn):
    """Fuer einen DECKEL ist None/0 die falsche Richtung: dann umgeht ein
    Modellwechsel die Grenze, ohne dass es jemand merkt."""
    eingabe, ausgabe = kosten.teuerster_preis()
    wert = kosten.kosten_oder_teuerster(
        conn, CHAT, "gruppe1", "gibtsnicht/modell-9", 1_000_000, 1_000_000
    )
    assert wert == pytest.approx(eingabe + ausgabe)
    zeilen = conn.execute(
        "SELECT art, detail FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchall()
    assert [z["art"] for z in zeilen] == ["kosten_modell_unbekannt"]
    assert "gibtsnicht/modell-9" in zeilen[0]["detail"]


def test_bekanntes_modell_erzeugt_keinen_vorfall(conn):
    kosten.kosten_oder_teuerster(conn, CHAT, "gruppe1", "google/gemma-4-31B-it", 10, 10)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchone()["n"] == 0


def test_whisper_kostet_je_minute():
    assert kosten.stt_kosten_chf(60) == pytest.approx(kosten.WHISPER_CHF_JE_MINUTE)
    assert kosten.stt_kosten_chf(90) == pytest.approx(kosten.WHISPER_CHF_JE_MINUTE * 1.5)
    assert kosten.stt_kosten_chf(0) == 0.0
    assert kosten.stt_kosten_chf(None) == 0.0


def test_claude_steht_an_einer_stelle():
    """Aus dem Abo kann eine Abrechnung werden -- dann ist das eine Zeile
    und keine Suche."""
    assert kosten.CLAUDE_CHF_JE_AUFRUF == 0.0


# -- Die Spalten ----------------------------------------------------------


def test_aufruf_hat_modell_und_kosten(conn):
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(aufruf)")}
    assert "modell" in spalten and "kosten_chf" in spalten


def test_alte_zeilen_bleiben_null_und_zaehlen_als_null(conn):
    """Additive Migration: eine Datenbank von gestern hat NULL in den neuen
    Spalten, und NULL ist keine Kostenangabe, sondern 'wissen wir nicht'."""
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, erstellt_am) VALUES (?, ?, ?)",
        (CHAT, "gespraech", repo._jetzt()),
    )
    conn.commit()
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == 0.0


def test_merke_aufruf_schreibt_modell_und_kosten(conn):
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", 100, 120, 30, "stop", 900, 1,
                      modell="moonshotai/Kimi-K2.6", kosten_chf=0.25)
    zeile = conn.execute("SELECT * FROM aufruf WHERE chat_id = ?", (CHAT,)).fetchone()
    assert zeile["modell"] == "moonshotai/Kimi-K2.6"
    assert zeile["kosten_chf"] == pytest.approx(0.25)


def test_merke_aufruf_ohne_die_neuen_werte_geht_weiter(conn):
    """Die zwei Parameter sind additiv und stehen am Ende -- jeder
    bestehende Aufruf funktioniert unveraendert."""
    repo.merke_aufruf(conn, CHAT, "extraktor", "A", 10, 12, 3, "stop", 80, 1)
    zeile = conn.execute("SELECT * FROM aufruf WHERE chat_id = ?", (CHAT,)).fetchone()
    assert zeile["modell"] is None and zeile["kosten_chf"] is None


def test_kostensumme_zaehlt_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", kosten_chf=1.0)
    repo.merke_aufruf(conn, 2, "gespraech", "A", kosten_chf=99.0)
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == pytest.approx(1.0)


def test_kostensumme_zaehlt_auch_gescheiterte_aufrufe(conn):
    """Ein 5xx nach dem Senden ist bezahlt -- llm._anfrage bucht im finally
    (llm.py:316), und der Deckel muss dasselbe sehen."""
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", erfolg=0, kosten_chf=0.4)
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == pytest.approx(0.4)


def test_kostensumme_ignoriert_was_vor_dem_stichtag_liegt(conn):
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", 3.0, "2026-09-29T21:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", 2.0, "2026-09-30T08:00:00+00:00"),
    )
    conn.commit()
    summe = repo.kostensumme_seit(conn, CHAT, "2026-09-29T22:00:00+00:00")
    assert summe == pytest.approx(2.0)
```

16 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_kosten.py -q -p no:cacheprovider
```
Erwartet: `ModuleNotFoundError: No module named 'interview_theater.kosten'`.

- [ ] **Schritt 3: `db.py` — zwei Spalten**

In `SCHEMA`, Tabelle `aufruf` (`db.py:705-717`), zwei Zeilen vor `erstellt_am`:

```sql
CREATE TABLE IF NOT EXISTS aufruf (
  id                     INTEGER PRIMARY KEY,
  chat_id                INTEGER,
  art                    TEXT NOT NULL,     -- gespraech|verdichter|extraktor|stt|dramaturgie_*
  modus                  TEXT,              -- A|B|C (C = Claude ueber den Proxy)
  geschaetzte_token      INTEGER,
  tatsaechliche_token    INTEGER,           -- usage.prompt_tokens
  antwort_token          INTEGER,
  finish_reason          TEXT,
  dauer_ms               INTEGER,
  erfolg                 INTEGER,
  -- Was wirklich lief. Aus ``art`` folgt das Modell nicht: LLM.schema
  -- waehlt es je Aufruf (Erkenner gemma, Gespraech Kimi, beide modus 'A').
  modell                 TEXT,
  -- Beim Buchen gerechnet, nicht beim Lesen (30.09.2026, Karte Padua S):
  -- eine Preisaenderung soll alte Zeilen nicht ruecktdatieren. NULL heisst
  -- "aus der Zeit davor" und zaehlt als 0.
  kosten_chf             REAL,
  erstellt_am            TEXT NOT NULL
);
```

**`db.SCHEMA_VERSION` bleibt 3.** Die Spalten kommen ueber
`_migriere_fehlende_spalten` (`db.py:783-797`, liest die Sollspalten direkt aus `SCHEMA`) und
brauchen keine Umrechnung — es gibt nichts umzurechnen, alte Zeilen bleiben NULL.

- [ ] **Schritt 4: `repo.py` — buchen und summieren**

`merke_aufruf` (`repo.py:2788`) bekommt zwei Parameter **am Ende** (damit jeder bestehende
Aufruf mit Stellungsargumenten unveraendert gilt):

```python
@_gesperrt
def merke_aufruf(
    conn: sqlite3.Connection,
    chat_id: int | None,
    art: str,
    modus: str | None = None,
    geschaetzte_token: int | None = None,
    tatsaechliche_token: int | None = None,
    antwort_token: int | None = None,
    finish_reason: str | None = None,
    dauer_ms: int | None = None,
    erfolg: int | None = None,
    modell: str | None = None,
    kosten_chf: float | None = None,
) -> None:
    """Protokolliert einen Sprachmodell-Aufruf zur Selbstkorrektur der
    Token-Schaetzung (global-constraints.md § 4) -- und seit dem 30.09.2026
    mit Modell und Kosten, als Grundlage des Tagesdeckels
    (``interview_theater/kosten.py``).

    ``modell`` und ``kosten_chf`` stehen am Ende und haben Vorgabewerte: die
    bestehenden Aufrufer reichen zehn Stellungsargumente herein, und die
    sollen unveraendert gelten."""
    conn.execute(
        """
        INSERT INTO aufruf
            (chat_id, art, modus, geschaetzte_token, tatsaechliche_token,
             antwort_token, finish_reason, dauer_ms, erfolg, modell,
             kosten_chf, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id, art, modus, geschaetzte_token, tatsaechliche_token,
            antwort_token, finish_reason, dauer_ms, erfolg, modell,
            kosten_chf, _jetzt(),
        ),
    )
    conn.commit()
```

Direkt dahinter:

```python
@_gesperrt
def kostensumme_seit(conn: sqlite3.Connection, chat_id: int, ab_iso: str) -> float:
    """Was diese Gruppe seit ``ab_iso`` an Modellaufrufen gekostet hat.

    ``ab_iso`` ist ein UTC-Zeitstempel in derselben Form wie ``_jetzt()`` --
    der Vergleich laeuft als Textvergleich, und ISO-8601 in UTC sortiert
    lexikographisch richtig. Die Umrechnung von Mitternacht Europe/Rome nach
    UTC macht ``kosten.tagesbeginn_utc``: die Zeitzone gehoert nicht in die
    Ablageschicht.

    ``COALESCE``, weil alte Zeilen NULL tragen -- NULL heisst 'aus der Zeit
    vor der Kostenbuchung', nicht 'kostenlos'. Gezaehlt werden **auch
    gescheiterte** Aufrufe (``erfolg = 0``): ein 5xx nach dem Senden ist
    bezahlt, und ``llm._anfrage`` bucht deshalb im ``finally``."""
    zeile = conn.execute(
        """
        SELECT COALESCE(SUM(COALESCE(kosten_chf, 0)), 0) AS summe
        FROM aufruf WHERE chat_id = ? AND erstellt_am >= ?
        """,
        (chat_id, ab_iso),
    ).fetchone()
    return float(zeile["summe"] or 0.0)
```

- [ ] **Schritt 5: `interview_theater/kosten.py` anlegen**

```python
"""Was ein Workshoptag kostet -- und ab wann der Bot pausiert.

**Der Anlass ist ein Befund.** Die Karte ging davon aus, die Kosten stuenden
schon im ``aufruf``-Protokoll. Sie standen nicht dort: die Tabelle trug bis
zum 30.09.2026 weder eine Modell- noch eine Kostenspalte (``db.py``), und
Whisper buchte gar nicht. Nachtraeglich rechnen ging auch nicht -- aus
``aufruf.art`` folgt das Modell nicht, ``LLM.schema`` waehlt es je Aufruf.

**Also wird beim Buchen gerechnet.** Jeder Aufruf schreibt sein Modell und
seine Kosten mit; der Deckel summiert nur noch. Eine Preisaenderung
ruecktdatiert damit keine alte Zeile.

**Unbekanntes Modell => teuerster Preis, nicht 0.** Fuer den Bericht von
``scripts/pruefe_prompts.py`` ist ``None`` richtig ("lieber keine Zahl als
eine erfundene"); fuer einen Deckel ist es die falsche Richtung -- sonst
umgeht der naechste Modellwechsel die Grenze, ohne dass es jemand merkt.
Deshalb zwei Funktionen: ``kosten_chf`` (unveraendert, ``None``) und
``kosten_oder_teuerster`` (Betriebspfad, Vorfall).

**Kein SQL hier.** Gelesen wird ueber ``repo.kostensumme_seit`` (AGENTS.md:
SQL nur in ``repo.py``, ``db.py``, ``web_daten.py``). Dieses Modul rechnet
und entscheidet, es speichert nicht.
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from interview_theater import repo

log = logging.getLogger(__name__)

#: Stand der Preise: **04.09.2026**, uebernommen aus
#: ``scripts/pruefe_prompts.py`` und seither nicht nachgezogen. Das Skript
#: importiert sie seit dem 30.09.2026 von hier -- zwei Tabellen waeren zwei
#: Wahrheiten, und der Bericht rechnete bald anders als der Deckel.
#: Eingabe- und Ausgabepreis je Million Token, in CHF.
PREISE_STAND = "04.09.2026"
PREISE_CHF_JE_MIO_TOKEN = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8": (0.05, 0.20),
    "google/gemma-4-31B-it": (0.20, 0.40),
    "mistralai/Mistral-Small-4-119B-2603": (0.20, 0.75),
    "mistralai/Ministral-3-14B-Instruct-2512": (0.30, 0.40),
    "Qwen/Qwen3.5-122B-A10B-FP8": (0.40, 3.20),
    "moonshotai/Kimi-K2.6": (0.60, 3.00),
    "swiss-ai/Apertus-v1.5-70B": (0.70, 2.50),
    "Qwen/Qwen3.5-397B-A17B-FP8": (0.80, 3.60),
}

#: Whisper rechnet nach Audiodauer, nicht nach Token. Quelle:
#: ``~/hermes-shared/hermes-knowledge/infomaniak-modelle.md`` § 6.4 --
#: **ausserhalb dieses Repositories**, Stand unten. Nachgemessen ist der Wert
#: nicht (das kostete einen bezahlten Aufruf); er steht hier als Konstante
#: mit Datum, damit klar ist, was zu pruefen waere.
WHISPER_CHF_JE_MINUTE = 0.006
WHISPER_STAND = "30.09.2026"

#: Der Claude-Weg ueber den lokalen Proxy laeuft ueber ein Abonnement und
#: zaehlt deshalb nicht gegen den Tagesdeckel (Birk bestaetigt, dass
#: Claude-Proxy-Aufrufe nicht gegen den 5-CHF-Deckel zaehlen; siehe auch den
#: Docstring von ``szene_claude.prosa``: "mit 0 CHF, weil Abo").
#:
#: **An genau einer Stelle**, damit aus dem Abo eine Abrechnung werden kann,
#: ohne dass jemand suchen muss.
CLAUDE_CHF_JE_AUFRUF = 0.0


def kosten_chf(modell: str, eingabe_token: int, ausgabe_token: int) -> float | None:
    """Kostenschaetzung nach der Preistabelle. ``None`` fuer ein Modell, das
    nicht in der Liste steht -- lieber keine Zahl als eine erfundene.

    Wortgleich das Verhalten von ``scripts/pruefe_prompts.kosten_chf``, das
    diese Funktion seit dem Umzug ist."""
    preise = PREISE_CHF_JE_MIO_TOKEN.get(modell)
    if preise is None:
        return None
    eingabe, ausgabe = preise
    return ((eingabe_token or 0) * eingabe + (ausgabe_token or 0) * ausgabe) / 1_000_000


def teuerster_preis() -> tuple[float, float]:
    """Das Maximum je Richtung ueber die ganze Tabelle. Die konservative
    Annahme fuer ein Modell, das wir nicht kennen."""
    return (
        max(p[0] for p in PREISE_CHF_JE_MIO_TOKEN.values()),
        max(p[1] for p in PREISE_CHF_JE_MIO_TOKEN.values()),
    )


def kosten_oder_teuerster(conn, chat_id, bot_name, modell,
                          eingabe_token, ausgabe_token) -> float:
    """Die Kosten fuer die Buchung -- konservativ.

    Kennt die Tabelle das Modell nicht, wird mit dem **teuersten** Preis
    gerechnet und ein Vorfall vermerkt. Mit 0 zu buchen hiesse, dass der
    naechste Modellwechsel den Deckel aushebelt, ohne dass es jemand merkt;
    zu teuer zu buchen kostet hoechstens eine fruehe Pause, und die faellt
    sofort auf."""
    wert = kosten_chf(modell or "", eingabe_token, ausgabe_token)
    if wert is not None:
        return wert
    eingabe, ausgabe = teuerster_preis()
    wert = ((eingabe_token or 0) * eingabe + (ausgabe_token or 0) * ausgabe) / 1_000_000
    try:
        repo.merke_vorfall(
            conn, chat_id, bot_name, "kosten_modell_unbekannt",
            f"Kein Preis fuer {modell!r} (Tabelle Stand {PREISE_STAND}) -- "
            f"konservativ mit {eingabe}/{ausgabe} CHF je Mio gerechnet, "
            f"{wert:.4f} CHF gebucht",
        )
    except Exception:  # noqa: BLE001 -- ein Vorfall darf keine Buchung mitreissen
        log.exception("Vorfall zum unbekannten Modell nicht geschrieben")
    return wert


def stt_kosten_chf(dauer_s) -> float:
    """Was eine Transkription kostet: Audiodauer mal Minutenpreis.

    ``None`` oder 0 gibt 0.0 -- eine Aufnahme ohne bekannte Dauer wird nicht
    geraten. Das ist die einzige Stelle, an der der Deckel etwas **nicht**
    sieht; im Betrieb traegt jede Telegram-Sprachnachricht ihre
    ``dauer_sekunden``, und der Web-Upload meldet sie (``MAX_DAUER_S``)."""
    try:
        sekunden = float(dauer_s or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, sekunden) / 60.0 * WHISPER_CHF_JE_MINUTE
```

(Die Deckel-Funktionen `tagesbeginn_utc`, `deckel_erreicht`, `KostendeckelErreicht`,
`melde_pause_wenn_deckel` kommen in Aufgabe 8 in dieselbe Datei — sie brauchen die
Einstellungen, und die Aufgabe waere sonst zu gross fuer einen Reviewer.)

- [ ] **Schritt 6: `scripts/pruefe_prompts.py` — Preise importieren**

`PREISE_CHF_JE_MIO_TOKEN` (`:97-106`) und `kosten_chf` (`:695-703`) ersetzen durch:

```python
from interview_theater import kosten as _kosten

#: Die Preise liegen seit dem 30.09.2026 im Paket
#: (``interview_theater/kosten.py``), weil der Tagesdeckel dieselbe Tabelle
#: braucht. Hier nur der Verweis: zwei Tabellen waeren zwei Wahrheiten, und
#: der Bericht rechnete bald anders als der Deckel
#: (``tests/test_kosten.py::test_die_preise_stehen_im_paket_und_im_skript_gleich``).
PREISE_CHF_JE_MIO_TOKEN = _kosten.PREISE_CHF_JE_MIO_TOKEN
kosten_chf = _kosten.kosten_chf
```

Der bestehende Aufrufer im Skript bleibt unveraendert — Name und Verhalten sind dieselben.
Wer `simulation/` mit einer eigenen Kopie findet, zieht sie auf denselben Import.

- [ ] **Schritt 7: `llm.py` — Modell und Kosten buchen**

`_anfrage` (`llm.py:252-328`). Das Modell steht im Koerper (`_baue_body` setzt es aus
`modell` oder `e.llm_modell`); gebucht wird derselbe Wert:

```python
        body = self._baue_body(...)
        # Das Modell, das wirklich lief -- ``_baue_body`` faellt ohne Angabe
        # auf ``e.llm_modell`` zurueck, und aus ``art`` folgt es nicht
        # (Erkenner gemma, Gespraech Kimi, beide modus 'A').
        gelaufenes_modell = body.get("model")
```

und im `finally` (`llm.py:316-328`):

```python
        finally:
            dauer_ms = int((time.monotonic() - start) * 1000)
            # Die Kosten beim Buchen, nicht beim Lesen (Karte Padua S): eine
            # Preisaenderung soll alte Zeilen nicht ruecktdatieren. Auch bei
            # erfolg=0 -- ein 5xx NACH dem Senden ist bezahlt.
            gekostet = kosten.kosten_oder_teuerster(
                self._conn, chat_id, getattr(self._e, "bot_name", None),
                gelaufenes_modell, tatsaechliche_token or geschaetzte_token or 0,
                antwort_token or 0,
            )
            repo.merke_aufruf(
                self._conn,
                chat_id,
                art,
                modus,
                geschaetzte_token,
                tatsaechliche_token,
                antwort_token,
                finish_reason,
                dauer_ms,
                erfolg,
                modell=gelaufenes_modell,
                kosten_chf=gekostet,
            )
```

`tatsaechliche_token or geschaetzte_token`: scheitert der Aufruf vor der Antwort, gibt es
keine `usage` — dann ist die Schaetzung das Beste, was wir haben, und sie ist besser als 0.

`from interview_theater import kosten` in den Modulkopf von `llm.py`. **Zyklus pruefen:**
`kosten` importiert `repo`, `llm` importiert `repo` und `kosten` — `kosten` importiert
`llm` nicht. Kein Zyklus.

- [ ] **Schritt 8: `szene_claude.py` — 0 CHF, aber ausdruecklich**

`_buche` (`szene_claude.py:157-166`):

```python
def _buche(conn, chat_id, e, art, modell, nutzung, finish, dauer_s, erfolg):
    try:
        ein = int(nutzung.get("input_tokens") or 0)
        repo.merke_aufruf(
            conn, chat_id, art, modus="C", geschaetzte_token=ein,
            tatsaechliche_token=ein, antwort_token=int(nutzung.get("output_tokens") or 0),
            finish_reason=finish, dauer_ms=int(dauer_s * 1000), erfolg=1 if erfolg else 0,
            modell=modell,
            # 0 CHF, weil Abonnement -- der Wert steht in kosten.py an genau
            # einer Stelle, damit aus dem Abo eine Abrechnung werden kann,
            # ohne dass jemand suchen muss. ``modell`` steht trotzdem in der
            # Zeile: das Dashboard soll den Weg sehen.
            kosten_chf=kosten.CLAUDE_CHF_JE_AUFRUF,
        )
    except Exception:  # noqa: BLE001 -- Buchung darf den Aufruf nie mitreissen
        log.exception("Aufruf-Buchung (Claude) fehlgeschlagen")
```

`from interview_theater import kosten` im Modulkopf.

- [ ] **Schritt 9: Lauf, alles gruen**

```
$PY -m pytest tests/test_kosten.py -q -p no:cacheprovider
```
Erwartet: `16 passed`.

```
$PY -m pytest tests/test_llm.py tests/test_szene_claude.py tests/test_db.py \
    tests/test_repo.py -q -p no:cacheprovider
```
Erwartet: gruen. Prueft ein Test die Spaltenliste von `aufruf` oder die
`INSERT`-Parameterzahl, wird er um die zwei Spalten ergaenzt.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 104.

- [ ] **Schritt 10: Commit**

```bash
git add interview_theater/kosten.py interview_theater/db.py interview_theater/repo.py \
        interview_theater/llm.py interview_theater/szene_claude.py \
        scripts/pruefe_prompts.py tests/test_kosten.py
git commit -m "Kosten: Preise im Paket, aufruf.modell und aufruf.kosten_chf

Die Karte nahm an, die Kosten stuenden schon im aufruf-Protokoll. Sie
standen nicht dort: keine Modell- und keine Kostenspalte (db.py:705-717),
Whisper buchte gar nicht. Nachtraeglich rechnen ging auch nicht -- aus art
folgt das Modell nicht, LLM.schema waehlt es je Aufruf.
Also beim Buchen rechnen: zwei additive Spalten, Preistabelle aus
scripts/pruefe_prompts.py ins Paket gezogen (ein Test haelt sie identisch).
Unbekanntes Modell wird mit dem teuersten Preis gebucht plus Vorfall -- mit
0 umginge der naechste Modellwechsel den Deckel.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 7: Whisper bucht mit (E-S1, Teil 2)

**Dateien:**
- Aendern: `interview_theater/aufnahme.py` (`_transkribiere_mit_meldung` `aufnahme.py:475`)
- Test: `tests/test_aufnahme_kosten.py` (neu)

**Schnittstellen — Konsumiert:** `kosten.stt_kosten_chf`, `repo.merke_aufruf`,
`stt.transkribiere` (`stt.py:223`).

### Wo gebucht wird und warum dort

`stt.transkribiere` kennt weder `conn` noch `chat_id` — es bekommt `e`, einen `httpx.Client`
und einen Pfad (`stt.py:223`). Es dort buchen zu lassen hiesse, dem Dienstemodul die
Ablageschicht mitzugeben; `llm.py` hat diese Kopplung schon (es nimmt `conn` im
Konstruktor), `stt.py` bewusst nicht.

Der eine Aufrufer ist `aufnahme._transkribiere_mit_meldung` (`aufnahme.py:510`) — gemessen:
`grep -n "stt.transkribiere" interview_theater/` findet genau diese Stelle. Dort liegen
`conn`, `row["chat_id"]` und `row["dauer_sekunden"]` bereit. Also dort.

### Woher die Dauer kommt

Aus `aufnahme.dauer_sekunden` — Telegram liefert sie bei `voice`/`audio` mit, und der
Web-Upload meldet sie (A2, `MAX_DAUER_S`). **Nicht** aus der Whisper-Antwort: `stt.abholen`
gibt nur den Text zurueck (`stt.py:219`), ein Dauerfeld ist dort weder gelesen noch
nachgewiesen. Ob die Antwort eines traegt, waere ein bezahlter Aufruf — das steht als
Aufgabe 11.

Fehlt die Dauer, wird **0.0 gebucht und nichts geraten**. Das ist die eine Stelle, an der
der Deckel weniger sieht, als tatsaechlich anfaellt; sie steht im Docstring und in AGENTS.md.

### Gebucht wird auch bei Misserfolg

Ein Whisper-Auftrag, der ins Zeitbudget laeuft, wurde abgesendet und ist bezahlt.
`erfolg=0`, Kosten trotzdem — dieselbe Regel wie beim `finally` in `llm._anfrage`.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_aufnahme_kosten.py`:

```python
"""Whisper bucht in `aufruf` -- vorher tat es das gar nicht.

Gemessen am 30.09.2026: `grep -c merke_aufruf interview_theater/stt.py` -> 0.
Eine Kostengrenze, die die Transkription nicht sieht, waere keine: ein
Workshoptag mit fuenf Interviews a 20 Minuten sind 100 Minuten Audio.

Gebucht wird in aufnahme._transkribiere_mit_meldung und nicht in stt.py:
stt bekommt weder conn noch chat_id (stt.py:223) und soll sie auch nicht
bekommen.
"""

import pytest

from interview_theater import aufnahme, db, kosten, repo, stt

CHAT = 1


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def tippt(self, chat_id):
        pass


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", str(datei))
    repo.setze_aufnahme_dauer(conn, aufnahme_id, 120)
    conn.commit()
    yield conn, aufnahme_id
    conn.close()


def _zeilen(conn):
    return conn.execute(
        "SELECT * FROM aufruf WHERE chat_id = ? AND art = 'stt'", (CHAT,)
    ).fetchall()


def test_eine_gelungene_transkription_bucht_nach_dauer(aufbau, monkeypatch):
    conn, aufnahme_id = aufbau
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "Hier steht Text.")
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["erfolg"] == 1
    assert zeilen[0]["kosten_chf"] == pytest.approx(kosten.stt_kosten_chf(120))
    assert zeilen[0]["modell"]


def test_eine_gescheiterte_transkription_bucht_trotzdem(aufbau, monkeypatch):
    """Ein Auftrag, der ins Zeitbudget laeuft, wurde abgesendet und ist
    bezahlt -- dieselbe Regel wie das finally in llm._anfrage."""
    conn, aufnahme_id = aufbau

    def kaputt(*a, **k):
        raise stt.STTFehler("Zeitbudget ausgeschoepft")

    monkeypatch.setattr(stt, "transkribiere", kaputt)
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["erfolg"] == 0
    assert zeilen[0]["kosten_chf"] == pytest.approx(kosten.stt_kosten_chf(120))


def test_ohne_dauer_wird_null_gebucht_und_nichts_geraten(aufbau, monkeypatch):
    conn, aufnahme_id = aufbau
    conn.execute("UPDATE aufnahme SET dauer_sekunden = NULL WHERE id = ?", (aufnahme_id,))
    conn.commit()
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "Text.")
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    assert _zeilen(conn)[0]["kosten_chf"] == pytest.approx(0.0)


def test_hundert_minuten_audio_bleiben_unter_dem_deckel():
    """Ein Workshoptag mit fuenf Interviews a 20 Minuten. Die Zahl steht
    hier, damit der Anteil von Whisper am Deckel sichtbar ist -- er ist
    klein, und das ist eine Aussage, keine Selbstverstaendlichkeit."""
    assert kosten.stt_kosten_chf(100 * 60) == pytest.approx(0.6)


def test_stt_py_bucht_weiterhin_nicht_selbst():
    """stt.py bekommt weder conn noch chat_id und soll sie nicht bekommen --
    die Kopplung gehoert in die Fachlogik."""
    from pathlib import Path

    quelle = Path(stt.__file__).read_text(encoding="utf-8")
    assert "merke_aufruf" not in quelle
    assert "import repo" not in quelle
```

5 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_aufnahme_kosten.py -q -p no:cacheprovider
```
Erwartet: rot — `assert len(zeilen) == 1` mit `0`: es wird heute nichts gebucht.

- [ ] **Schritt 3: `aufnahme.py` — buchen**

`_transkribiere_mit_meldung` (`aufnahme.py:475-517`), der `try`-Block am Ende:

```python
    start = time.monotonic()
    erfolg = 0
    try:
        text = stt.transkribiere(e, klient, pfad, budget)
        erfolg = 1
        return text
    except Exception as fehler:
        _melde_transkriptionsfehler(conn, tg, e, row, fehler)
        return None
    finally:
        timer_tipp.cancel()
        timer_meldung.cancel()
        _buche_stt(conn, e, row, time.monotonic() - start, erfolg)
```

und daneben:

```python
#: Was in ``aufruf.modell`` steht, wenn Whisper lief. Ein fester Name und
#: kein Modell-Bezeichner: der Aufruf geht ueber ``e.stt_produkt`` an einen
#: Produkt-Endpunkt, nicht an ein benanntes Modell.
STT_MODELL = "whisper-v3"


def _buche_stt(conn, e, row, dauer_s: float, erfolg: int) -> None:
    """Der Whisper-Aufruf in ``aufruf`` -- seit dem 30.09.2026 (Karte Padua S).

    **Warum hier und nicht in ``stt.py``:** ``stt.transkribiere`` bekommt
    weder ``conn`` noch ``chat_id`` (``stt.py``), und das soll so bleiben --
    ``llm.py`` traegt diese Kopplung schon, ``stt.py`` bewusst nicht. Der
    einzige Aufrufer steht hier.

    **Die Dauer kommt aus ``aufnahme.dauer_sekunden``**, nicht aus der
    Whisper-Antwort: ``stt.abholen`` liefert nur den Text, und ob die Antwort
    ein Dauerfeld traegt, waere ein bezahlter Aufruf. Fehlt die Dauer, werden
    **0 CHF gebucht und nichts geraten** -- die eine Stelle, an der der
    Tagesdeckel weniger sieht, als anfaellt.

    **Gebucht wird auch bei Misserfolg**: ein Auftrag, der ins Zeitbudget
    laeuft, wurde abgesendet und ist bezahlt (dieselbe Regel wie das
    ``finally`` in ``llm._anfrage``)."""
    from interview_theater import kosten

    try:
        repo.merke_aufruf(
            conn, row["chat_id"], "stt", modus=None,
            dauer_ms=int(dauer_s * 1000), erfolg=erfolg,
            modell=STT_MODELL,
            kosten_chf=kosten.stt_kosten_chf(row["dauer_sekunden"]),
        )
    except Exception:  # noqa: BLE001 -- die Buchung darf die Aufnahme nie mitreissen
        log.exception("Aufruf-Buchung (Whisper) fehlgeschlagen, aufnahme=%s", row["id"])
```

`import time` steht in `aufnahme.py` schon (fuer die Timer); falls nicht, ergaenzen.

**Achtung:** der Import von `kosten` steht **in** der Funktion, nicht im Modulkopf.
`aufnahme.py` wird aus `bot.py` und aus `ablauf.py` gezogen, und `kosten` importiert `repo`
— kein Zyklus, aber der lokale Import ist hier die Bauart des Repos (AGENTS.md,
„Modulkarte": *„die wenigen Aufrufe nach oben stehen als lokaler Import"*), und er haelt den
Modulkopf schlank.

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_aufnahme_kosten.py -q -p no:cacheprovider
```
Erwartet: `5 passed`.

```
$PY -m pytest tests/test_aufnahme.py -q -p no:cacheprovider
```
Erwartet: gruen. Zaehlt ein bestehender Test `aufruf`-Zeilen ohne Filter auf `art`, bekommt
er den Filter — es gibt jetzt eine Zeile mehr je transkribierter Aufnahme.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 109.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/aufnahme.py tests/test_aufnahme_kosten.py
git commit -m "Whisper bucht in aufruf (art 'stt'), Kosten aus der Audiodauer

Gemessen: stt.py enthielt kein merke_aufruf -- eine Kostengrenze, die die
Transkription nicht sieht, waere keine (ein Workshoptag sind leicht 100
Minuten Audio). Gebucht wird in aufnahme._transkribiere_mit_meldung, dem
einzigen Aufrufer: stt.transkribiere bekommt weder conn noch chat_id und
soll sie nicht bekommen.
Auch bei Misserfolg -- ein abgesendeter Auftrag ist bezahlt. Ohne bekannte
Dauer 0 CHF und nichts geraten.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 8: Der Tagesdeckel — Pruefung, Durchsetzung, Pausenmeldung (E-S2, E-S3)

**Dateien:**
- Aendern: `interview_theater/kosten.py` (Deckel, Ausnahme, Pausenmeldung)
- Aendern: `interview_theater/einstellungen.py` (zwei Variablen)
- Aendern: `interview_theater/db.py` (`SCHEMA`, Tabelle `gruppe`: ein Merkposten)
- Aendern: `interview_theater/repo.py` (zwei Funktionen)
- Aendern: `interview_theater/llm.py` (`_anfrage`), `szene_claude.py` (`prosa`),
  `aufnahme.py` (`_verarbeite`)
- Aendern: `interview_theater/ablauf.py` (`ablauf.py:743`, `ablauf.py:1038`),
  `szene.py:2215`, `kurzgeschichte.py:326`, `szenenfolge.py:1024`, `sprachstil.py:190`
- Aendern: `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_kostendeckel.py` (neu)

**Schnittstellen — Produziert:**

```python
# interview_theater/kosten.py
class KostendeckelErreicht(Exception): ...
VORGABE_DECKEL_CHF = 5.0
VORGABE_ZEITZONE = "Europe/Rome"
PAUSE_WIEDERHOLUNG_S = 15 * 60
_TEXT_PAUSE: str
def zeitzone(e=None) -> str
def deckel(e=None) -> float
def tagesbeginn_utc(zone: str, jetzt: datetime | None = None) -> str
def summe_heute(conn, chat_id: int, e=None, jetzt=None) -> float
def deckel_erreicht(conn, chat_id: int | None, e=None, jetzt=None) -> bool
def pruefe(conn, chat_id: int | None, e=None, jetzt=None) -> None   # wirft
def melde_pause_wenn_deckel(conn, tg, e, chat_id: int | None, jetzt=None) -> bool
T = sprache.Texte(__name__)

# interview_theater/repo.py
def merke_kostenpause(conn, chat_id: int, nicht_vor_iso: str) -> bool
def gab_es_vorfall_seit(conn, chat_id: int, art: str, ab_iso: str) -> bool

# interview_theater/einstellungen.py
kosten_deckel_chf: float = 5.0
zeitzone: str = "Europe/Rome"
```

### Die Entscheidungen, begruendet

**Eine Pruefung, drei Aufrufer (E-S2).** Nicht an jedem Aufrufer, sondern an den drei
Stellen, an denen Geld ausgegeben wird:

| Stelle | Datei:Zeile | Warum dort |
|---|---|---|
| `llm.LLM._anfrage` | `llm.py:252` | **jeder** Infomaniak-Aufruf geht durch sie — Gespraech, Erkenner, Journal, Verdichter, Sprachprofil, Schaerfung, Szenenfolge, Stueckpruefung, Dramaturgie |
| `szene_claude.prosa` | `szene_claude.py:89` | der zweite Anbieterweg; bucht 0 CHF, muss aber **pausieren**, wenn der Tag ueber ist — sonst schriebe die Gruppe weiter Szenen und der Bot antwortete nicht mehr im Chat |
| `aufnahme._verarbeite` | `aufnahme.py:456` | der einzige Weg zu `stt.transkribiere` |

**Weil das im Bot-Prozess sitzt, gilt es fuer Telegram UND Web automatisch.** Beide Kanaele
laufen durch denselben `ablauf`/`aufnahme`-Code, nur mit einem anderen `tg`-Objekt
(`WebKanal` statt `Telegram`, A2 Aufgabe 2/4). Ein Deckel im Webserver waere die falsche
Schicht gewesen: er saehe die Telegram-Gruppen nicht.

**Mitternacht Europe/Rome.** `zoneinfo` ist Standardbibliothek,
`/usr/share/zoneinfo/Europe/Rome` ist vorhanden (selbst geprueft: `ZoneInfo("Europe/Rome")`
laedt, und Mitternacht Rom am 30.09.2026 ist `2026-09-29T22:00:00+00:00` UTC). Gerechnet
wird **nach UTC um**, weil `aufruf.erstellt_am` in UTC steht (`repo._jetzt`, `repo.py:57`)
und ISO-8601-UTC lexikographisch richtig sortiert — ein Textvergleich im SQL genuegt.

**`chat_id is None` zaehlt nicht** (E-S2): das Warmlaufen (`bot.warmlaufen`) und
Pruefskripte laufen ohne Gruppe. Sie gegen den Deckel einer Gruppe zu rechnen waere falsch,
und gegen „alle" hiesse, dass ein Skriptlauf den Workshop anhaelt.

**Pausieren heisst: Empfangen geht weiter (E-S3).** Das ist die bindende Entscheidung aus
AGENTS.md — *„Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte
Entscheidungen. Jede Nachricht wird roh gespeichert … etwas nicht aufzunehmen ist
unumkehrbar."* Konkret:

| Was | Bei erreichtem Deckel |
|---|---|
| Nachricht empfangen und speichern | **laeuft** (`bot.verarbeite_update`, kein Modell) |
| Audio empfangen und ablegen | **laeuft** (`aufnahme` legt `status='empfangen'` an) |
| Slash-Befehle, Knopf-Handler | **laufen** (kein Modellaufruf, Zusage 2) |
| Weboberflaeche lesen und Parameter aendern | **laeuft** (`web_schreiben` ruft nur `repo`) |
| Gespraechszug, Verdichter, Szene, Schaerfung | **faellt aus**, eine Pausenmeldung |
| Erkenner, Journal | **fallen still aus**, Wasserzeichen bleibt stehen |
| Transkription | **faellt aus**, Aufnahme bleibt `status='empfangen'` |

**Der Nachhol-Arbeiter greift es nach Mitternacht auf — nachgemessen, nichts Neues noetig.**
`aufnahme.nachholen` (`aufnahme.py:1389`) laeuft alle `NACHHOL_INTERVALL_S` = 60 s
(`aufnahme.py:76`) ueber `repo.offene_aufnahmen_fuer_bot` (`repo.py:1527`), und das liefert
alles mit `status NOT IN ('fertig','fehlgeschlagen','laeuft')` (`repo._NICHTS_ZU_TUN`,
`repo.py:398`). Eine Aufnahme auf `'empfangen'` ist also am naechsten Morgen automatisch
dran. **Kein neuer Mechanismus.**

**Aber: der Deckel darf nicht durch `_melde_transkriptionsfehler` laufen.** Das ist die
Falle dieser Aufgabe, und sie ist im Code belegt (`aufnahme.py:570-607`): dort wird
`repo.zaehle_versuch_hoch` gerufen, und ab `MAX_VERSUCHE` = 5 (`aufnahme.py:77`) wird die
Aufnahme dauerhaft auf `'fehlgeschlagen'` gesetzt. Bei 60 Sekunden Nachholintervall waeren
fuenf Versuche in fuenf Minuten verbraucht — **jedes Interview des Abends waere am naechsten
Morgen endgueltig verloren.** Ausserdem schickte `melde_ausfall` eine Whisper-Ausfallmeldung,
die schlicht nicht stimmt.

Deshalb steht die Pruefung **vor** `_transkribiere_mit_meldung` in `_verarbeite`, mit einem
eigenen `return`: kein Versuch, kein Fehlertext, Status bleibt.

**Die Meldung: einmal, dann hoechstens alle 15 Minuten, Merkposten in der DB (E-S3).** In
der DB und nicht im Prozess, aus zwei Gruenden: ein Neustart (systemd, Deploy) wuerde sonst
sofort wieder melden, und `nachholen` laeuft im Minutentakt — ohne Drosselung stuenden
sechzig Pausenzeilen je Stunde im Chat. Der Merkposten ist eine Spalte auf `gruppe`, gesetzt
per bedingtem `UPDATE` (dieselbe Bauart wie `repo.beanspruche_knopf`): SQLite entscheidet,
wer meldet, auch wenn zwei Threads gleichzeitig ankommen.

**Der Vorfall einmal je Tag**, nicht je Meldung: das Dashboard soll sagen „diese Gruppe hat
ihr Tagesbudget erreicht", nicht sechsmal dasselbe.

**Der Text nennt keinen Betrag** (E-S3). „5 CHF" sagt einer Theatergruppe nichts ueber das,
was sie tun soll, und lenkt die Aufmerksamkeit auf eine Zahl, die der Betreiber setzt. Der
Text sagt: Budget erreicht, bis Mitternacht (italienische Zeit) pausiert der Bot, die Arbeit
ist gespeichert, aufnehmen und lesen geht weiter.

**Deutsch als Konstante, Englisch ueber A1** (ANNAHME A-18). `_TEXT_PAUSE` ist eine
modulweite `_TEXT_*`-Konstante, `T = sprache.Texte(__name__)` am Dateiende, gelesen wird
`T._TEXT_PAUSE` zur Aufrufzeit — die Mechanik aus A1.

- [ ] **Schritt 1: Den Angriffstest schreiben (rot ohne Schutz)**

`tests/test_kostendeckel.py`:

```python
"""Angriff: gemockte Kosten ueber dem Tagesdeckel -- und der Bot ruft weiter an.

Die Kennzahl ist nicht der Statuscode, sondern die Zahl der Netzaufrufe: die
LLM-Attrappe zaehlt mit, und sie muss auf 0 bleiben. Ein Deckel, der die
Anfrage erst nach dem Absenden abbricht, hat nichts gespart.

Dazu die drei Eigenschaften, an denen so ein Deckel sonst scheitert:
  * Er gilt fuer Telegram UND Web (beide Kanaele laufen durch denselben
    Bot-Code -- ein Test je Kanal zeigt das).
  * Er setzt um Mitternacht Europe/Rome zurueck, nicht UTC: eine Zeile von
    gestern 23:59 Rom darf heute nicht mitzaehlen.
  * Er laesst das Empfangen in Ruhe. Nachrichten und Audio werden weiter
    gespeichert -- nicht aufzunehmen ist unumkehrbar (AGENTS.md).

Zeit kommt ueberall als Parameter herein. Kein sleep, kein echter Kalender.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from interview_theater import (
    aufnahme, db, einstellungen, kosten, llm, repo, stt,
)

CHAT = 1
ROM = ZoneInfo("Europe/Rome")


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def tippt(self, chat_id):
        pass


def _e(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="t", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="http://kein.netz/chat/completions",
        llm_key="k", llm_modell="moonshotai/Kimi-K2.6",
        stt_basis="http://kein.netz", stt_produkt="p",
    )


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Die Ankommenden")
    yield verbindung
    verbindung.close()


def _buche(conn, chf, zeitpunkt_iso=None):
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", chf, zeitpunkt_iso or repo._jetzt()),
    )
    conn.commit()


class Zaehler:
    """Ein httpx.Client, der jeden Aufruf zaehlt und nie ins Netz geht."""

    def __init__(self):
        self.aufrufe = 0

    def post(self, *a, **k):
        self.aufrufe += 1
        raise AssertionError("Es haette gar kein Netzaufruf stattfinden duerfen")

    def get(self, *a, **k):
        self.aufrufe += 1
        raise AssertionError("Es haette gar kein Netzaufruf stattfinden duerfen")


# -- Die Grenze selbst ----------------------------------------------------


def test_unter_der_grenze_ist_alles_frei(conn, tmp_path):
    _buche(conn, 4.99)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is False


def test_genau_auf_der_grenze_ist_erreicht(conn, tmp_path):
    _buche(conn, 5.0)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is True


def test_viele_kleine_summieren_sich(conn, tmp_path):
    for _ in range(50):
        _buche(conn, 0.1)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is True


def test_eine_andere_gruppe_ist_nicht_betroffen(conn, tmp_path):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    _buche(conn, 9.0)
    assert kosten.deckel_erreicht(conn, 2, _e(tmp_path)) is False


def test_ohne_chat_id_greift_der_deckel_nie(conn, tmp_path):
    """Warmlaufen und Pruefskripte laufen ohne Gruppe -- sie gegen den
    Deckel einer Gruppe zu rechnen waere falsch."""
    _buche(conn, 99.0)
    assert kosten.deckel_erreicht(conn, None, _e(tmp_path)) is False


def test_der_deckel_kommt_aus_der_umgebung(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("IT_KOSTEN_DECKEL_CHF", "1.0")
    _buche(conn, 1.5)
    assert kosten.deckel(None) == pytest.approx(1.0)
    assert kosten.deckel_erreicht(conn, CHAT) is True


# -- Mitternacht Europe/Rome ----------------------------------------------


def test_tagesbeginn_rechnet_nach_utc_um():
    jetzt = datetime(2026, 9, 30, 16, 38, tzinfo=ROM)
    assert kosten.tagesbeginn_utc("Europe/Rome", jetzt) == "2026-09-29T22:00:00+00:00"


def test_gestern_dreiundzwanzig_neunundfuenfzig_zaehlt_heute_nicht(conn, tmp_path):
    """Sommerzeit: Mitternacht Rom ist 22:00 UTC. Eine Zeile von gestern
    23:59 Rom steht als 21:59 UTC in der Datenbank und liegt damit VOR dem
    Tagesbeginn -- mit einem UTC-Tag waere sie mitgezaehlt worden."""
    gestern = datetime(2026, 9, 29, 23, 59, tzinfo=ROM)
    _buche(conn, 9.0, gestern.astimezone(timezone.utc).isoformat(timespec="seconds"))
    jetzt = datetime(2026, 9, 30, 9, 0, tzinfo=ROM)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path), jetzt=jetzt) is False


def test_heute_null_uhr_eins_zaehlt(conn, tmp_path):
    frueh = datetime(2026, 9, 30, 0, 1, tzinfo=ROM)
    _buche(conn, 9.0, frueh.astimezone(timezone.utc).isoformat(timespec="seconds"))
    jetzt = datetime(2026, 9, 30, 9, 0, tzinfo=ROM)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path), jetzt=jetzt) is True


def test_die_zeitzone_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_ZEITZONE", "UTC")
    jetzt = datetime(2026, 9, 30, 16, 38, tzinfo=ROM)
    assert kosten.tagesbeginn_utc(kosten.zeitzone(None), jetzt) == "2026-09-30T00:00:00+00:00"


# -- Der Angriff: kein Netzaufruf -----------------------------------------


def test_ueber_dem_deckel_faellt_der_llm_aufruf_ohne_netz_aus(conn, tmp_path):
    _buche(conn, 5.0)
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)
    with pytest.raises(kosten.KostendeckelErreicht):
        klm.schema(CHAT, "system", "nutzer", {"type": "object"}, "gespraech")
    assert zaehler.aufrufe == 0


def test_ein_ausgefallener_aufruf_bucht_keine_zeile(conn, tmp_path):
    """Sonst schoebe jeder abgewiesene Versuch die Summe weiter hoch, und
    aus einer Pause bis Mitternacht wuerde eine bis uebermorgen."""
    _buche(conn, 5.0)
    vorher = conn.execute("SELECT COUNT(*) AS n FROM aufruf").fetchone()["n"]
    klm = llm.LLM(_e(tmp_path), Zaehler(), conn)
    for _ in range(5):
        with pytest.raises(kosten.KostendeckelErreicht):
            klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech")
    assert conn.execute("SELECT COUNT(*) AS n FROM aufruf").fetchone()["n"] == vorher


def test_ueber_dem_deckel_faellt_auch_der_claude_weg_aus(conn, tmp_path):
    from interview_theater import szene_claude

    _buche(conn, 5.0)
    zaehler = Zaehler()
    with pytest.raises(kosten.KostendeckelErreicht):
        szene_claude.prosa(conn, _e(tmp_path), zaehler, CHAT, "s", "n", "szene", 10.0)
    assert zaehler.aufrufe == 0


def test_ueber_dem_deckel_wird_nicht_transkribiert_aber_gespeichert(conn, tmp_path, monkeypatch):
    """Empfangen und Antworten sind zwei Entscheidungen: die Datei bleibt,
    der Status bleibt 'empfangen' -- der Nachhol-Arbeiter greift sie nach
    Mitternacht auf."""
    _buche(conn, 5.0)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", str(datei))
    repo.setze_aufnahme_dauer(conn, aufnahme_id, 120)
    conn.commit()

    def darf_nicht(*a, **k):
        raise AssertionError("Whisper haette gar nicht gerufen werden duerfen")

    monkeypatch.setattr(stt, "transkribiere", darf_nicht)
    tg = TelegramAttrappe()
    aufnahme.verarbeite(conn, tg, None, _e(tmp_path), Zaehler(), aufnahme_id)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    assert row["status"] == "empfangen"
    assert datei.is_file()


def test_der_versuchszaehler_bleibt_stehen(conn, tmp_path, monkeypatch):
    """Die Falle dieser Aufgabe: liefe der Deckel ueber
    _melde_transkriptionsfehler, verbraeuchte der Nachhol-Arbeiter (alle
    60 s) MAX_VERSUCHE in fuenf Minuten -- und jedes Interview des Abends
    waere am naechsten Morgen endgueltig 'fehlgeschlagen'."""
    _buche(conn, 5.0)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", str(datei))
    conn.commit()
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "darf nicht laufen")
    for _ in range(aufnahme.MAX_VERSUCHE + 2):
        aufnahme.verarbeite(conn, TelegramAttrappe(), None, _e(tmp_path),
                            Zaehler(), aufnahme_id)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    assert row["status"] == "empfangen"
    assert (row["versuche"] or 0) == 0


# -- Die Meldung ----------------------------------------------------------


def test_die_pausenmeldung_kommt_einmal(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    e = _e(tmp_path)
    assert kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT) is True
    assert kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT) is True
    assert len(tg.gesendet) == 1


def test_nach_fuenfzehn_minuten_kommt_sie_wieder(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    e = _e(tmp_path)
    jetzt = datetime(2026, 9, 30, 14, 0, tzinfo=ROM)
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT, jetzt=jetzt)
    spaeter = datetime(2026, 9, 30, 14, 16, tzinfo=ROM)
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT, jetzt=spaeter)
    assert len(tg.gesendet) == 2


def test_der_merkposten_ueberlebt_einen_neustart(conn, tmp_path):
    """Im Prozess gemerkt haette ein Neustart sofort wieder gemeldet -- und
    der Nachhol-Arbeiter laeuft im Minutentakt."""
    _buche(conn, 5.0)
    e = _e(tmp_path)
    tg = TelegramAttrappe()
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT)
    conn.close()
    zweite = db.verbinde(str(tmp_path / "t.db"))
    try:
        zweiter_tg = TelegramAttrappe()
        kosten.melde_pause_wenn_deckel(zweite, zweiter_tg, e, CHAT)
        assert zweiter_tg.gesendet == []
    finally:
        zweite.close()


def test_unter_dem_deckel_meldet_sie_nichts(conn, tmp_path):
    _buche(conn, 1.0)
    tg = TelegramAttrappe()
    assert kosten.melde_pause_wenn_deckel(conn, tg, _e(tmp_path), CHAT) is False
    assert tg.gesendet == []


def test_der_text_nennt_keinen_betrag(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    kosten.melde_pause_wenn_deckel(conn, tg, _e(tmp_path), CHAT)
    text = tg.gesendet[0]
    for verbotenes in ("CHF", "5.0", "5,0", "Fr.", "€", "Euro"):
        assert verbotenes not in text, verbotenes


def test_der_vorfall_kommt_einmal_je_tag(conn, tmp_path):
    _buche(conn, 5.0)
    e = _e(tmp_path)
    jetzt = datetime(2026, 9, 30, 14, 0, tzinfo=ROM)
    for minuten in (0, 20, 40, 120):
        spaeter = datetime(2026, 9, 30, 14 + minuten // 60, minuten % 60, tzinfo=ROM)
        kosten.melde_pause_wenn_deckel(conn, TelegramAttrappe(), e, CHAT, jetzt=spaeter)
    anzahl = conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ? AND art = ?",
        (CHAT, "kostendeckel_erreicht"),
    ).fetchone()["n"]
    assert anzahl == 1


def test_der_englische_text_existiert_und_nennt_die_lage(monkeypatch):
    """A1-Mechanik: die deutsche Konstante IST die deutsche Tabelle, jede
    weitere Sprache steht in sprachen/<code>/texte.toml."""
    from interview_theater import sprache, workshop

    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    sprache.vergiss()
    workshop.vergiss() if hasattr(workshop, "vergiss") else None
    englisch = sprache.tabelle("en").get("kosten", {}).get("_TEXT_PAUSE")
    assert englisch, "Kein englischer Pausentext in sprachen/en/texte.toml"
    gesenkt = englisch.lower()
    assert "budget" in gesenkt
    assert "midnight" in gesenkt
    assert "saved" in gesenkt or "kept" in gesenkt


# -- Beide Kanaele --------------------------------------------------------


def test_der_deckel_gilt_im_telegram_kanal(conn, tmp_path, monkeypatch):
    from interview_theater import ablauf

    _buche(conn, 5.0)
    repo.merke_nachricht(conn, CHAT, 5, "Guelten", 0, "text", "Wie geht es weiter?",
                         repo._jetzt())
    conn.commit()
    tg = TelegramAttrappe()
    zaehler = Zaehler()
    ablauf.bearbeite(conn, tg, llm.LLM(_e(tmp_path), zaehler, conn), _e(tmp_path), CHAT)
    assert zaehler.aufrufe == 0
    assert any("Budget" in t or "budget" in t.lower() or "pausier" in t.lower()
               for t in tg.gesendet), tg.gesendet


def test_der_deckel_gilt_im_web_kanal(conn, tmp_path, monkeypatch):
    """Derselbe Bot-Code, nur ein anderes tg-Objekt (Karte A2). Dass beide
    Kanaele denselben Weg nehmen, ist der Grund, warum der Deckel im
    Bot-Prozess sitzt und nicht im Webserver."""
    from interview_theater import ablauf, web_kanal

    _buche(conn, 5.0)
    repo.merke_nachricht(conn, CHAT, 5, "Guelten", 0, "text", "Wie geht es weiter?",
                         repo._jetzt())
    conn.commit()
    kanal = web_kanal.WebKanal(conn, CHAT)
    zaehler = Zaehler()
    ablauf.bearbeite(conn, kanal, llm.LLM(_e(tmp_path), zaehler, conn), _e(tmp_path), CHAT)
    assert zaehler.aufrufe == 0
    hinausgegangen = [
        z["text"] or "" for z in conn.execute(
            "SELECT text FROM web_post WHERE chat_id = ? AND richtung = ?",
            (CHAT, repo.RICHTUNG_AUS),
        )
    ]
    assert any("pausier" in t.lower() or "budget" in t.lower() for t in hinausgegangen)


# -- Was weiterlaeuft -----------------------------------------------------


def test_slash_befehle_laufen_weiter(conn, tmp_path):
    """Kein Befehl ruft synchron ein Modell (AGENTS.md) -- also darf keiner
    am Deckel scheitern."""
    from interview_theater import befehle

    _buche(conn, 5.0)
    antwort = befehle.behandle(conn, _e(tmp_path), CHAT, "/stand")
    assert antwort


def test_der_web_schreibpfad_laeuft_weiter(conn, tmp_path):
    """web_schreiben ruft ausschliesslich repo-Funktionen, kein Modell."""
    from interview_theater import web_schreiben

    _buche(conn, 5.0)
    web_schreiben.wende_an(conn, CHAT, "rahmen", "Ein Hinterhof im Regen", None)
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Ein Hinterhof im Regen"
```

27 Testfunktionen.

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_kostendeckel.py -q -p no:cacheprovider
```
Erwartet: rot,
`AttributeError: module 'interview_theater.kosten' has no attribute 'KostendeckelErreicht'`.
Inhaltlich zeigt `test_ueber_dem_deckel_faellt_der_llm_aufruf_ohne_netz_aus` den Angriff:
heute laeuft `Zaehler.post` los und wirft `AssertionError`, also **findet ein Netzaufruf
statt**.

- [ ] **Schritt 3: `einstellungen.py` — zwei Variablen**

In `_VORGABEWERTE`:

```python
    # Tagesdeckel je Gruppe ueber alle bezahlten Modellaufrufe (Karte Padua
    # S, 30.09.2026). Danach pausiert der Bot bis Mitternacht -- empfangen
    # und speichern laeuft weiter.
    "IT_KOSTEN_DECKEL_CHF": "5.0",
    # Wonach "heute" sich richtet. Padua liegt in Italien; der Workshoptag
    # soll nicht um 02:00 Ortszeit umschlagen, weil UTC es tut.
    "IT_ZEITZONE": "Europe/Rome",
```

In `Einstellungen`, **am Ende** (damit bestehende direkte Konstruktionsaufrufe in Tests
weiter gelten — dieselbe Begruendung wie bei `erkenner_modell`):

```python
    kosten_deckel_chf: float = 5.0
    zeitzone: str = "Europe/Rome"
```

In `laden()`:

```python
        kosten_deckel_chf=_zahl(werte["IT_KOSTEN_DECKEL_CHF"], 5.0),
        zeitzone=werte["IT_ZEITZONE"] or "Europe/Rome",
```

mit

```python
def _zahl(roh, vorgabe: float) -> float:
    """Eine Kommazahl aus der Umgebung, mit Vorgabewert bei Unsinn.

    Ein Tippfehler in einer Env-Datei soll den Bot nicht am Workshoptag
    stoppen -- aber er soll auch nicht den Deckel abschalten. Deshalb faellt
    ein unlesbarer Wert auf die Vorgabe zurueck und nicht auf 'unendlich'."""
    try:
        return float(str(roh).strip())
    except (TypeError, ValueError):
        return vorgabe
```

- [ ] **Schritt 4: `db.py` und `repo.py` — der Merkposten**

In `SCHEMA`, Tabelle `gruppe`, eine Spalte (additiv):

```sql
  -- Wann der Gruppe zuletzt gesagt wurde, dass der Tagesdeckel erreicht ist
  -- (Karte Padua S). In der DATENBANK und nicht im Prozess: ein Neustart
  -- meldete sonst sofort wieder, und der Nachhol-Arbeiter laeuft im
  -- Minutentakt.
  kostenpause_gemeldet_am  TEXT,
```

In `repo.py`, am Dateiende:

```python
@_gesperrt
def merke_kostenpause(conn: sqlite3.Connection, chat_id: int, nicht_vor_iso: str) -> bool:
    """Darf die Pausenmeldung jetzt raus? Setzt den Merkposten und liefert
    True, wenn ja.

    Bedingtes ``UPDATE`` wie ``beanspruche_knopf``: SQLite entscheidet, wer
    meldet. Ohne das schickten zwei Threads (Gespraechszug und
    Nachhol-Arbeiter) dieselbe Zeile zweimal.

    ``nicht_vor_iso`` ist der Zeitpunkt, vor dem die letzte Meldung gelegen
    haben muss -- der Aufrufer rechnet ihn aus (jetzt minus
    ``kosten.PAUSE_WIEDERHOLUNG_S``), damit die Zeitrechnung an einer Stelle
    steht."""
    cursor = conn.execute(
        """
        UPDATE gruppe SET kostenpause_gemeldet_am = ?
        WHERE chat_id = ?
          AND (kostenpause_gemeldet_am IS NULL OR kostenpause_gemeldet_am < ?)
        """,
        (_jetzt(), chat_id, nicht_vor_iso),
    )
    conn.commit()
    return cursor.rowcount > 0


@_gesperrt
def gab_es_vorfall_seit(conn: sqlite3.Connection, chat_id: int, art: str,
                        ab_iso: str) -> bool:
    """Steht seit ``ab_iso`` schon ein Vorfall dieser Art fuer diese Gruppe?

    Fuer den Tagesdeckel: das Dashboard soll einmal sagen 'diese Gruppe hat
    ihr Budget erreicht' und nicht sechsmal dasselbe."""
    zeile = conn.execute(
        "SELECT 1 FROM vorfall WHERE chat_id = ? AND art = ? AND erstellt_am >= ? LIMIT 1",
        (chat_id, art, ab_iso),
    ).fetchone()
    return zeile is not None
```

- [ ] **Schritt 5: `kosten.py` — Deckel, Ausnahme, Meldung**

Ans Ende von `interview_theater/kosten.py`:

```python
#: Der Tagesdeckel je Gruppe, in CHF. Ueber ``IT_KOSTEN_DECKEL_CHF``
#: umstellbar; 5 CHF ist die Vorgabe aus der Karte.
VORGABE_DECKEL_CHF = 5.0

#: Wonach sich "heute" richtet. Padua liegt in Italien -- ein Workshoptag
#: soll nicht um 02:00 Ortszeit umschlagen, weil UTC es tut.
VORGABE_ZEITZONE = "Europe/Rome"

#: Wie oft die Pausenmeldung hoechstens wiederholt wird. Der
#: Nachhol-Arbeiter laeuft alle 60 s (``aufnahme.NACHHOL_INTERVALL_S``) --
#: ohne Drosselung stuenden sechzig Zeilen je Stunde im Chat.
PAUSE_WIEDERHOLUNG_S = 15 * 60

VORFALL_ART = "kostendeckel_erreicht"

#: Die Nachricht an die Gruppe. **Kein Betrag** (Entscheidung 30.09.2026):
#: "5 CHF" sagt einer Theatergruppe nichts darueber, was sie tun soll, und
#: lenkt die Aufmerksamkeit auf eine Zahl, die der Betreiber setzt. Der Text
#: sagt vier Dinge: Budget erreicht, bis wann, was gesichert ist, was
#: weitergeht.
_TEXT_PAUSE = (
    "Das Tagesbudget für heute ist erreicht — ich mache bis Mitternacht "
    "(italienische Zeit) Pause und antworte solange nicht.\n\n"
    "Eure Arbeit ist gespeichert. Aufnehmen könnt ihr weiter (ich höre sie "
    "morgen ab), und eure Gruppenseite bleibt lesbar."
)


class KostendeckelErreicht(Exception):
    """Der Tagesdeckel dieser Gruppe ist erreicht -- **es fand kein
    Netzaufruf statt**.

    Eine eigene Ausnahme und kein ``LLMFehler``: die Aufrufer behandeln sie
    anders (eine Pausenmeldung statt "bei mir hakt gerade etwas"), und ein
    ``LLMFehler`` haette Wiederholungslogik ausgeloest, wo es nichts zu
    wiederholen gibt."""


def zeitzone(e=None) -> str:
    """Die Zeitzone: aus den Einstellungen, sonst aus der Umgebung, sonst
    Rom. Zwei Quellen, weil der Bot ``Einstellungen`` hat und Skripte und
    Tests nicht."""
    return (
        getattr(e, "zeitzone", None)
        or os.environ.get("IT_ZEITZONE")
        or VORGABE_ZEITZONE
    )


def deckel(e=None) -> float:
    """Der Tagesdeckel in CHF, aus denselben zwei Quellen."""
    aus_e = getattr(e, "kosten_deckel_chf", None)
    if aus_e is not None:
        return float(aus_e)
    roh = os.environ.get("IT_KOSTEN_DECKEL_CHF")
    try:
        return float(roh) if roh else VORGABE_DECKEL_CHF
    except ValueError:
        return VORGABE_DECKEL_CHF


def tagesbeginn_utc(zone: str, jetzt: datetime | None = None) -> str:
    """Mitternacht der Ortszeit, umgerechnet nach UTC, im Format von
    ``repo._jetzt()``.

    **Warum nach UTC und nicht andersherum:** ``aufruf.erstellt_am`` steht in
    UTC (``repo._jetzt``), und ISO-8601 in UTC sortiert lexikographisch
    richtig -- ein Textvergleich im SQL genuegt, und ``repo`` muss nichts von
    Zeitzonen wissen.

    Am 30.09.2026 (Sommerzeit) ist Mitternacht Rom ``2026-09-29T22:00:00+00:00``.
    Eine Zeile von gestern 23:59 Rom liegt damit VOR dem Tagesbeginn -- mit
    einem UTC-Tag waere sie mitgezaehlt worden."""
    try:
        ort = ZoneInfo(zone)
    except Exception:  # noqa: BLE001 -- eine unbekannte Zone darf nichts reissen
        log.warning("Unbekannte Zeitzone %r -- es gilt %s", zone, VORGABE_ZEITZONE)
        ort = ZoneInfo(VORGABE_ZEITZONE)
    jetzt = datetime.now(ort) if jetzt is None else jetzt.astimezone(ort)
    mitternacht = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    return mitternacht.astimezone(timezone.utc).isoformat(timespec="seconds")


def summe_heute(conn, chat_id: int, e=None, jetzt=None) -> float:
    """Was diese Gruppe seit Mitternacht Ortszeit ausgegeben hat."""
    return repo.kostensumme_seit(conn, chat_id, tagesbeginn_utc(zeitzone(e), jetzt))


def deckel_erreicht(conn, chat_id, e=None, jetzt=None) -> bool:
    """Ist der Tagesdeckel dieser Gruppe erreicht?

    ``chat_id is None`` gibt immer False: das Warmlaufen
    (``bot.warmlaufen``) und die Pruefskripte laufen ohne Gruppe. Sie gegen
    den Deckel einer Gruppe zu rechnen waere falsch, und gegen "alle" hiesse,
    dass ein Skriptlauf den Workshop anhaelt."""
    if chat_id is None:
        return False
    try:
        return summe_heute(conn, chat_id, e, jetzt) >= deckel(e)
    except Exception:  # noqa: BLE001
        # Eine Datenbank, die gerade nicht lesbar ist, darf den Bot nicht
        # anhalten: der Deckel ist eine Bremse, keine Sicherung.
        log.exception("Tagessumme nicht lesbar, chat_id=%s -- Deckel gilt als offen", chat_id)
        return False


def pruefe(conn, chat_id, e=None, jetzt=None) -> None:
    """Wirft ``KostendeckelErreicht``, wenn nichts mehr ausgegeben werden
    darf. **Vor** dem Netzaufruf zu rufen -- der Sinn ist, dass er nicht
    stattfindet."""
    if deckel_erreicht(conn, chat_id, e, jetzt):
        raise KostendeckelErreicht(
            f"Tagesdeckel {deckel(e)} CHF fuer chat_id={chat_id} erreicht"
        )


def melde_pause_wenn_deckel(conn, tg, e, chat_id, jetzt=None) -> bool:
    """Sagt der Gruppe, dass pausiert wird -- hoechstens alle
    ``PAUSE_WIEDERHOLUNG_S``. Liefert True, wenn der Deckel erreicht ist
    (unabhaengig davon, ob gerade gemeldet wurde).

    **Der Rueckgabewert ist die Weiche an den Fehlerstellen:** wer True
    bekommt, schickt **kein** "bei mir hakt gerade etwas" hinterher. Deshalb
    prueft die Funktion den Zustand neu, statt eine Ausnahme entgegen-
    zunehmen -- die ``except Exception``-Bloecke in ``ablauf`` und den
    Schreibwegen binden das Ausnahmeobjekt gar nicht, und der Zustand steht
    ohnehin in der Datenbank.

    **Der Merkposten liegt in der Datenbank** (``gruppe.kostenpause_gemeldet_am``):
    im Prozess gemerkt meldete ein Neustart sofort wieder, und der
    Nachhol-Arbeiter laeuft im Minutentakt."""
    if not deckel_erreicht(conn, chat_id, e, jetzt):
        return False
    grenze = (datetime.now(timezone.utc) if jetzt is None else jetzt.astimezone(timezone.utc))
    nicht_vor = (grenze - timedelta(seconds=PAUSE_WIEDERHOLUNG_S)).isoformat(timespec="seconds")
    try:
        darf = repo.merke_kostenpause(conn, chat_id, nicht_vor)
    except Exception:  # noqa: BLE001
        log.exception("Merkposten zur Kostenpause nicht gesetzt, chat_id=%s", chat_id)
        return True
    if not darf:
        return True
    try:
        tg.sende(chat_id, T._TEXT_PAUSE)
    except Exception:  # noqa: BLE001 -- die Meldung darf nichts mitreissen
        log.exception("Pausenmeldung nicht zugestellt, chat_id=%s", chat_id)
    try:
        tagesbeginn = tagesbeginn_utc(zeitzone(e), jetzt)
        if not repo.gab_es_vorfall_seit(conn, chat_id, VORFALL_ART, tagesbeginn):
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), VORFALL_ART,
                f"Tagesdeckel {deckel(e)} CHF erreicht "
                f"(Summe {summe_heute(conn, chat_id, e, jetzt):.2f} CHF seit {tagesbeginn})",
            )
    except Exception:  # noqa: BLE001
        log.exception("Vorfall zum Kostendeckel nicht geschrieben, chat_id=%s", chat_id)
    return True


#: A1-Mechanik: die deutschen Konstanten oben SIND die deutsche Tabelle,
#: jede weitere Sprache steht in ``sprachen/<code>/texte.toml``. Gelesen wird
#: zur Aufrufzeit ueber ``T._TEXT_PAUSE`` -- ein Web-Prozess bedient mehrere
#: Gruppen, und Tests schalten das Profil per monkeypatch um.
T = sprache.Texte(__name__)
```

Importe ergaenzen: `os`, `timedelta`, `from interview_theater import sprache`.

- [ ] **Schritt 6: `sprachen/en/texte.toml` — der englische Text**

**ANNAHME A-18.** Ans Dateiende, in Modulreihenfolge:

```toml
["kosten"]
# Der Tagesdeckel (Karte Padua S). Vier Aussagen, in dieser Reihenfolge:
# Budget erreicht, bis wann, was gesichert ist, was weitergeht. Kein Betrag
# -- eine Zahl, die der Betreiber setzt, gehoert nicht in eine Nachricht an
# die Gruppe.
_TEXT_PAUSE = """Today's budget is used up — I'm pausing until midnight (Italian time) and won't reply in the meantime.

Your work is saved. You can keep recording (I'll listen tomorrow), and your group page stays readable."""
```

- [ ] **Schritt 7: Die drei Durchsetzungsstellen**

**`llm.py`**, in `_anfrage` als **erste Anweisung**, vor `_baue_body`:

```python
        # Der Tagesdeckel (Karte Padua S): VOR dem Bauen des Koerpers und
        # damit lange vor dem Netzaufruf -- der Sinn der Grenze ist, dass er
        # nicht stattfindet. Auch vor dem ``try``, also wird KEINE
        # ``aufruf``-Zeile gebucht: jeder abgewiesene Versuch schoebe sonst
        # die Tagessumme weiter hoch, und aus einer Pause bis Mitternacht
        # wuerde eine bis uebermorgen.
        kosten.pruefe(self._conn, chat_id, self._e)
```

**`szene_claude.py`**, in `prosa` als erste Anweisung:

```python
    # Auch hier, obwohl der Claude-Weg 0 CHF bucht (Abo): ist das Tagesbudget
    # der Gruppe erreicht, antwortet der Bot im Chat nicht mehr -- eine Szene,
    # die trotzdem geschrieben wird, koennte sie gar nicht abnehmen.
    kosten.pruefe(conn, chat_id, e)
```

**`aufnahme.py`**, in `_verarbeite` (`aufnahme.py:456`), **vor**
`_transkribiere_mit_meldung`:

```python
    if row["status"] == "empfangen":
        # Der Tagesdeckel (Karte Padua S). Hier und NICHT als Ausnahme aus
        # stt.transkribiere: die liefe durch ``_melde_transkriptionsfehler``,
        # und das zaehlt ``repo.zaehle_versuch_hoch`` hoch. Der
        # Nachhol-Arbeiter laeuft alle 60 s -- MAX_VERSUCHE waeren in fuenf
        # Minuten verbraucht, und jedes Interview des Abends stuende am
        # naechsten Morgen auf 'fehlgeschlagen'.
        #
        # Stattdessen: nichts tun. Datei und Zeile bleiben, der Status bleibt
        # 'empfangen', und ``nachholen()`` greift sie nach Mitternacht von
        # selbst auf (repo.offene_aufnahmen_fuer_bot liefert alles ausserhalb
        # von fertig/fehlgeschlagen/laeuft). Kein neuer Mechanismus.
        if kosten.deckel_erreicht(conn, row["chat_id"], e):
            if not nachgeholt:
                # Nur im Live-Pfad melden: "Nachgeholtes loest nie eine
                # Antwort aus" (SPEC § 10.3), und der Nachhol-Arbeiter kaeme
                # sonst alle 60 s wieder.
                kosten.melde_pause_wenn_deckel(conn, tg, e, row["chat_id"])
            return
        text = _transkribiere_mit_meldung(conn, tg, e, klient, row)
```

`from interview_theater import kosten` lokal in der Funktion (Bauart des Repos).

- [ ] **Schritt 8: Die sechs Meldestellen**

An jeder Stelle, an der heute `_TEXT_FEHLER` hinausgeht, kommt die Weiche davor. Immer
dasselbe Muster, drei Zeilen:

```python
            if not kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id):
                tg.sende(chat_id, _TEXT_FEHLER)
```

Die sechs Stellen, mit ihrer heutigen Zeile:

| Datei:Zeile | heutiger Aufruf |
|---|---|
| `ablauf.py:743` | `tg.sende(chat_id, _TEXT_FEHLER)` in `_melde_fehler` |
| `ablauf.py:1038` | `tg.sende(chat_id, _TEXT_FEHLER)` im Auftragszug |
| `szene.py:2215` | `_sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)` |
| `kurzgeschichte.py:326` | `szene_modul._sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)` |
| `szenenfolge.py:1024` | `_sende(conn, tg, e, chat_id, _TEXT_FEHLER)` |
| `sprachstil.py:190` | `tg.sende(chat_id, _TEXT_FEHLER)` |

Bei den vier Stellen mit eigener Sendefunktion entsprechend:

```python
        if not kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id):
            _sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)
```

**Warum der Zustand neu geprueft wird statt die Ausnahme durchzureichen:** die
`except Exception:`-Bloecke an diesen Stellen binden das Ausnahmeobjekt gar nicht
(`ablauf.py:558`, `:1031`), und eine Signaturaenderung an sechs Fehlerpfaden waere die
Sorte Umbau, bei der genau einer vergessen wird. Der Zustand steht in der Datenbank; ihn zu
lesen kostet eine Abfrage an einer Stelle, an der ohnehin gerade etwas schiefgegangen ist.

**Erkenner und Journal bekommen nichts** — sie laufen im Hintergrund, ihr Wasserzeichen
bleibt stehen, und das ist die bestehende Regel fuer jeden gescheiterten Lauf (AGENTS.md:
*„Ein gescheiterter Absichtserkenner- oder Journal-Lauf ist fuer die Gruppe unsichtbar"*).

- [ ] **Schritt 9: Lauf, alles gruen**

```
$PY -m pytest tests/test_kostendeckel.py -q -p no:cacheprovider
```
Erwartet: `27 passed`.

```
$PY -m pytest tests/test_ablauf.py tests/test_szene.py tests/test_aufnahme.py \
    tests/test_einstellungen.py -q -p no:cacheprovider
```
Erwartet: gruen.

```
$PY -m pytest tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py \
    tests/test_sprache_texte.py -q -p no:cacheprovider
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: gruen — die neuen Spalten und der neue Text aendern keinen Prompt.
(`test_sprache_bitgleich.py` nur, falls A1 sie mitgebracht hat.)

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: `>=` Baseline + 136.

- [ ] **Schritt 10: Commit**

```bash
git add interview_theater/kosten.py interview_theater/einstellungen.py \
        interview_theater/db.py interview_theater/repo.py interview_theater/llm.py \
        interview_theater/szene_claude.py interview_theater/aufnahme.py \
        interview_theater/ablauf.py interview_theater/szene.py \
        interview_theater/kurzgeschichte.py interview_theater/szenenfolge.py \
        interview_theater/sprachstil.py interview_theater/sprachen/en/texte.toml \
        tests/test_kostendeckel.py
git commit -m "Tagesdeckel 5 CHF je Gruppe, Reset um Mitternacht Europe/Rome

Eine Pruefung vor dem Netzaufruf an drei Stellen (llm._anfrage,
szene_claude.prosa, aufnahme._verarbeite). Weil die im Bot-Prozess sitzen,
gilt der Deckel fuer Telegram UND Web automatisch -- ein Deckel im Webserver
saehe die Telegram-Gruppen nicht.
Pausieren heisst: Empfangen laeuft weiter. Audio wird gespeichert und nicht
transkribiert; der vorhandene Nachhol-Arbeiter greift es nach Mitternacht
auf (gemessen: repo.offene_aufnahmen_fuer_bot liefert 'empfangen', alle 60s).
Ausdruecklich NICHT ueber _melde_transkriptionsfehler -- das zaehlt
MAX_VERSUCHE hoch, und jedes Interview des Abends waere morgens verloren.
Meldung einmal, dann alle 15 min; Merkposten in der DB, weil ein Neustart
sonst sofort wieder meldet. Kein Betrag im Text, englische Fassung ueber A1.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
## Aufgabe 9: Reviewer-Drehbuch — jeden Angriff selbst fahren

**Dateien:** keine (die Kommandos stehen im Plan und spaeter im Abschlussbericht).

Der Reviewer dieser Karte liest nicht nur Code, er **faehrt die Angriffe**. Grund: alle
Pruefungen dieser Karte sind Verneinungen („darf nicht durchkommen"), und eine Verneinung
lernt man nicht durch Lesen. Eine Pruefung, die versehentlich hinter einem `return` steht,
sieht im Diff richtig aus.

**Kein Token aus `betrieb/`.** Alles laeuft gegen eine Wegwerf-Datenbank unter `$TMPDIR`.

- [ ] **Schritt 1: Den Server aufsetzen**

```bash
export PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
export WERK=$(mktemp -d)
export IT_DB=$WERK/probe.db
export IT_AUDIO=$WERK/audio
export IT_WEB_BIND=127.0.0.1:8099
export IT_WEB_PREFIX=/theatersoap

$PY - <<'ENDE'
import os
from interview_theater import db, repo
conn = db.verbinde(os.environ["IT_DB"])
db.initialisiere(conn)
repo.sichere_gruppe(conn, 7_000_000_000_001, "probe", "Probe-Gruppe")
repo.setze_gruppe_kanal(conn, 7_000_000_000_001, "web")
repo.setze_phase(conn, 7_000_000_000_001, 4)
repo.setze_arbeitsstand(conn, 7_000_000_000_001, "rahmen", "Eine Nacht im Treppenhaus")
print(repo.stelle_web_token_sicher(conn, 7_000_000_000_001))
conn.commit(); conn.close()
ENDE
```

Die ausgegebene Zeichenkette ist das Token:

```bash
export TOK=<die ausgegebene Zeile>
$PY -m interview_theater.web &
export WEB=$!
sleep 1
curl -s http://127.0.0.1:8099/gesund && echo
```
Erwartet: `ok`

Den Nonce holt man sich aus der Seite (er steht im Formular):

```bash
export NONCE=$(curl -s http://127.0.0.1:8099/g/$TOK | grep -o 'name="nonce" value="[^"]*"' | head -1 | cut -d'"' -f4)
echo "Nonce-Laenge: ${#NONCE}"
```
Erwartet: eine Laenge > 30. **Steht der Nonce in A2 anders im HTML**, das Muster anpassen —
er ist ein Feld der Form `<fenster>.<hex>`.

- [ ] **Schritt 2: Angriff — falsches Token**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/g/gibtsnicht
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/g/$TOK/gibtsnicht
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/nixda
```
Erwartet: `404`, `404`, `404`

- [ ] **Schritt 3: Angriff — Kopfzeilen fehlen**

```bash
curl -s -D - -o /dev/null http://127.0.0.1:8099/g/$TOK | grep -iE \
  'referrer-policy|x-robots-tag|x-content-type-options|x-frame-options|content-security-policy|permissions-policy|^server'
```
Erwartet, sechs Zeilen plus `Server`:
```
Server: interview-theater
Referrer-Policy: no-referrer
X-Robots-Tag: noindex, nofollow
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Permissions-Policy: microphone=(self)
Content-Security-Policy: default-src 'none'; script-src 'nonce-…
```
`Server` **ohne** `Python/3.11.15`. Dasselbe auf der 404 und auf einer unbekannten Methode:

```bash
curl -s -D - -o /dev/null http://127.0.0.1:8099/nixda | grep -i x-frame-options
curl -s -D - -o /dev/null -X BREW http://127.0.0.1:8099/ | grep -iE '^HTTP|x-frame-options'
```
Erwartet: `X-Frame-Options: DENY`, dann `HTTP/1.1 501 …` **mit** `X-Frame-Options: DENY`.

- [ ] **Schritt 4: Angriff — POST von fremdem Origin mit gueltigem Nonce**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8099/g/$TOK \
  -H 'Content-Type: application/json' -H 'Origin: https://boese.example' \
  -d "{\"nonce\":\"$NONCE\",\"feld\":\"rahmen\",\"wert\":\"GEKAPERT\"}"

curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8099/g/$TOK \
  -H 'Content-Type: application/json' -H 'Sec-Fetch-Site: cross-site' \
  -d "{\"nonce\":\"$NONCE\",\"feld\":\"rahmen\",\"wert\":\"GEKAPERT\"}"

curl -s http://127.0.0.1:8099/g/$TOK | grep -c GEKAPERT
```
Erwartet: `403`, `403`, `0`

- [ ] **Schritt 5: Angriff — POST ohne Nonce**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8099/g/$TOK \
  -H 'Content-Type: application/json' -d '{"feld":"rahmen","wert":"OHNE"}'
```
Erwartet: `403`

Und die Gegenprobe, damit das Werkzeug nicht einfach alles ablehnt:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8099/g/$TOK \
  -H 'Content-Type: application/json' \
  -d "{\"nonce\":\"$NONCE\",\"feld\":\"rahmen\",\"wert\":\"Ein Hinterhof im Regen\"}"
```
Erwartet: `200`

- [ ] **Schritt 6: Angriff — Upload ueber der Grenze**

```bash
head -c 9000000 /dev/zero > $WERK/zugross.webm
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://127.0.0.1:8099/g/$TOK/chat/audio?dauer=45" \
  -H 'Content-Type: audio/webm' -H "X-Nonce: $NONCE" \
  --data-binary @$WERK/zugross.webm
find $WERK/audio -type f 2>/dev/null | wc -l
```
Erwartet: `413`, dann `0`

- [ ] **Schritt 7: Angriff — falscher Typ**

```bash
printf '<!doctype html><html><body>kein audio</body></html>' > $WERK/tarnung.webm
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://127.0.0.1:8099/g/$TOK/chat/audio?dauer=45" \
  -H 'Content-Type: audio/webm' -H "X-Nonce: $NONCE" \
  --data-binary @$WERK/tarnung.webm

printf '\x1a\x45\xdf\xa3' > $WERK/echt.webm
head -c 2000 /dev/zero >> $WERK/echt.webm
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://127.0.0.1:8099/g/$TOK/chat/audio?dauer=45" \
  -H 'Content-Type: audio/ogg' -H "X-Nonce: $NONCE" \
  --data-binary @$WERK/echt.webm
find $WERK/audio -type f | sed 's/.*\.//' | sort -u
```
Erwartet: `415` (HTML als WebM deklariert), dann `202` (echtes WebM, falsch deklariert),
und die Endung ist **`webm`** — nicht `ogg`. Das ist Falle 3: entschieden haben die Bytes,
nicht der Header.

- [ ] **Schritt 8: Angriff — 50 Nachrichten in 10 Sekunden**

```bash
for i in $(seq 1 50); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST \
    http://127.0.0.1:8099/g/$TOK/chat/senden -H 'Content-Type: application/json' \
    -d "{\"nonce\":\"$NONCE\",\"text\":\"Flut $i\"}"
done | sort | uniq -c

$PY -c "
import os, sqlite3
c = sqlite3.connect(os.environ['IT_DB']); c.row_factory = sqlite3.Row
print('web_post ein:', c.execute(
  \"SELECT COUNT(*) n FROM web_post WHERE richtung='ein' AND typ='text'\").fetchone()['n'])
"
```
Erwartet:
```
     20 202
     30 429
web_post ein: 20
```
Und die Absage traegt `Retry-After`:

```bash
curl -s -D - -o /dev/null -X POST http://127.0.0.1:8099/g/$TOK/chat/senden \
  -H 'Content-Type: application/json' -d "{\"nonce\":\"$NONCE\",\"text\":\"noch eine\"}" \
  | grep -iE '^HTTP|retry-after'
```
Erwartet: `HTTP/1.1 429 …` und `Retry-After: <Zahl zwischen 1 und 60>`

- [ ] **Schritt 9: Angriff — rotiertes Token**

```bash
$PY -m scripts.web_token_neu 7000000000001            # Trockenlauf
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/g/$TOK

$PY -m scripts.web_token_neu 7000000000001 --ja
export NEU=$($PY -c "
import os, sqlite3
c = sqlite3.connect(os.environ['IT_DB']); c.row_factory = sqlite3.Row
print(c.execute('SELECT web_token FROM gruppe').fetchone()['web_token'])")

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/g/$TOK
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/g/$NEU
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8099/g/$NEU \
  -H 'Content-Type: application/json' \
  -d "{\"nonce\":\"$NONCE\",\"feld\":\"rahmen\",\"wert\":\"mit altem Nonce\"}"
```
Erwartet: `200` (nach dem Trockenlauf lebt der alte Link noch), dann `404`, `200`, `403`.
**Der Server wurde dabei nicht neu gestartet** — das ist der Punkt.

- [ ] **Schritt 10: Angriff — Fehlerseite**

```bash
$PY - <<'ENDE'
import threading, urllib.request, urllib.error, os
from interview_theater import web
dienst = web.baue_server(os.environ["IT_DB"], "127.0.0.1:8098", "/theatersoap")
threading.Thread(target=dienst.serve_forever, daemon=True).start()
def kaputt(*a, **k):
    raise RuntimeError("geheim /mnt/HC_Volume/pfad.py")
web.dashboard_html = kaputt
try:
    urllib.request.urlopen("http://127.0.0.1:8098/", timeout=5)
except urllib.error.HTTPError as f:
    koerper = f.read().decode()
    print("Status:", f.code)
    print("Traceback drin:", "Traceback" in koerper)
    print("Pfad drin:", "/mnt/" in koerper)
    print("Koerper:", koerper[:120])
dienst.shutdown()
ENDE
```
Erwartet:
```
Status: 500
Traceback drin: False
Pfad drin: False
Koerper: <!doctype html><html lang="de"><meta charset="utf-8"><p>Da ist bei uns etwas schiefgegangen.</p></html>
```

- [ ] **Schritt 11: Angriff — Kostendeckel**

```bash
$PY - <<'ENDE'
import os, sqlite3
from interview_theater import db, kosten, repo
conn = db.verbinde(os.environ["IT_DB"])
chat = 7_000_000_000_001
for _ in range(6):
    repo.merke_aufruf(conn, chat, "gespraech", "A", kosten_chf=1.0,
                      modell="moonshotai/Kimi-K2.6")
print("Summe heute:", round(kosten.summe_heute(conn, chat), 2))
print("Deckel erreicht:", kosten.deckel_erreicht(conn, chat))
conn.close()
ENDE
```
Erwartet: `Summe heute: 6.0`, `Deckel erreicht: True`

Und dass kein Netzaufruf mehr stattfindet — ohne echten Anbieter, weil die Attrappe zaehlt:

```bash
$PY - <<'ENDE'
import os
from interview_theater import db, einstellungen, kosten, llm

class Zaehler:
    aufrufe = 0
    def post(self, *a, **k):
        Zaehler.aufrufe += 1
        raise AssertionError("Netzaufruf!")

e = einstellungen.Einstellungen(
    bot_token="t", bot_name="probe", db_pfad=os.environ["IT_DB"],
    audio_verz=os.environ["IT_AUDIO"], llm_url="http://kein.netz/chat/completions",
    llm_key="k", llm_modell="moonshotai/Kimi-K2.6",
    stt_basis="http://kein.netz", stt_produkt="p")
conn = db.verbinde(os.environ["IT_DB"])
try:
    llm.LLM(e, Zaehler(), conn).schema(7_000_000_000_001, "s", "n", {"type": "object"}, "gespraech")
    print("FEHLER: der Aufruf ging durch")
except kosten.KostendeckelErreicht as f:
    print("Abgewiesen:", f)
print("Netzaufrufe:", Zaehler.aufrufe)
conn.close()
ENDE
```
Erwartet: `Abgewiesen: Tagesdeckel 5.0 CHF fuer chat_id=7000000000001 erreicht`,
`Netzaufrufe: 0`

- [ ] **Schritt 12: Aufraeumen**

```bash
kill $WEB 2>/dev/null
rm -rf $WERK
unset TOK NEU NONCE WERK WEB IT_DB IT_AUDIO IT_WEB_BIND IT_WEB_PREFIX
```

Das Verzeichnis liegt unter `$TMPDIR`, die Datenbank war ein Wegwerfstueck, und in
`betrieb/` wurde nichts angefasst.

- [ ] **Schritt 13: Commit (nur, falls das Drehbuch etwas gefunden hat)**

Findet der Reviewer einen Angriff, der durchkommt, wird er **zuerst als Test** in die
zugehoerige Datei geschrieben (rot), dann gefixt. Kein Fix ohne Test — sonst faellt dieselbe
Luecke beim naechsten Umbau wieder auf.

---

## Aufgabe 10: Doku, Env-Beispiel und der nginx-Vorschlag

**Dateien:**
- Aendern: `AGENTS.md`
- Aendern: `docs/betrieb-env.beispiel`
- Test: keiner (Doku), aber `tests/test_anweisungen.py` muss gruen bleiben

- [ ] **Schritt 1: `AGENTS.md` — die Modultabelle**

Drei Zeilen in die Tabelle unter „Aufbau", alphabetisch einsortiert:

```markdown
| `kosten.py` | Was ein Workshoptag kostet: Preistabelle (aus `scripts/pruefe_prompts.py` hierher gezogen), Kostenrechnung je Aufruf, der Tagesdeckel je Gruppe mit Reset um Mitternacht Europe/Rome, `KostendeckelErreicht` und die Pausenmeldung. **Kein SQL** — liest ueber `repo.kostensumme_seit` |
| `web_grenze.py` | Das Rate-Limit der Weboberflaeche: gleitendes Fenster im Prozessspeicher, Schluessel `chat_id`, thread-sicher. **Kein Projektimport** (wie `vorschlagssperre.py`) |
```

Und in der Schichtentabelle unter „Modulkarte": `kosten.py` und `web_grenze.py` in die Zeile
**Dienste**.

In „Wo man anfaengt, je nach Frage":

```markdown
| Warum antwortet der Bot heute gar nicht mehr? | `kosten.deckel_erreicht` → `repo.kostensumme_seit`, Vorfall `kostendeckel_erreicht` |
| Warum kommt eine Weboberflaechen-Anfrage nicht durch? | `web.eigene_herkunft` (403) → `web_grenze.pruefe` (429) → `web_chat._audio` (413/415) |
```

- [ ] **Schritt 2: `AGENTS.md` — der Kostendeckel bei den Bindenden Entwurfsentscheidungen**

Als neuer Punkt ans Ende des Abschnitts „Bindende Entwurfsentscheidungen":

```markdown
- **Fuenf Franken je Gruppe und Tag, dann pausiert der Bot** (30.09.2026,
  Karte Padua S, `kosten.py`). Der Deckel steht **im Bot-Prozess** und nicht
  im Webserver: beide Kanaele laufen durch denselben `ablauf`/`aufnahme`-Code,
  nur mit einem anderen `tg`-Objekt, und ein Deckel im Webserver saehe die
  Telegram-Gruppen nicht. Drei Durchsetzungsstellen, alle **vor** dem
  Netzaufruf: `llm.LLM._anfrage` (jeder Infomaniak-Aufruf geht durch sie),
  `szene_claude.prosa` und `aufnahme._verarbeite` (der einzige Weg zu
  `stt.transkribiere`). `chat_id is None` zaehlt nie mit — das Warmlaufen und
  die Pruefskripte laufen ohne Gruppe.
  **Gerechnet wird beim Buchen, nicht beim Lesen.** `aufruf` trug bis dahin
  weder Modell noch Kosten, und nachtraeglich ging es auch nicht: aus
  `aufruf.art` folgt das Modell nicht, `LLM.schema` waehlt es je Aufruf.
  Seitdem: `aufruf.modell` und `aufruf.kosten_chf`, additiv migriert (alte
  Zeilen NULL = 0). Whisper bucht mit (`art='stt'`, Kosten aus
  `aufnahme.dauer_sekunden` mal `kosten.WHISPER_CHF_JE_MINUTE`); der
  Claude-Proxy bucht **0 CHF, weil Abo** — der Wert steht an **einer** Stelle
  (`kosten.CLAUDE_CHF_JE_AUFRUF`), damit aus dem Abo eine Abrechnung werden
  kann, ohne dass jemand sucht. Ein Modell, das nicht in
  `kosten.PREISE_CHF_JE_MIO_TOKEN` steht, wird mit dem **teuersten** Preis
  gebucht plus Vorfall `kosten_modell_unbekannt`: mit 0 umginge der naechste
  Modellwechsel den Deckel, ohne dass es jemand merkt.
  **Pausieren heisst: Empfangen geht weiter** — dieselbe Trennung wie in
  § 1 der SPEC. Nachrichten und Audio werden gespeichert, Slash-Befehle und
  Knopf-Handler laufen (sie rufen ohnehin kein Modell), die Gruppenseite
  bleibt lesbar und beschreibbar. Nur Modellaufrufe fallen aus. Eine Aufnahme
  bleibt auf `status='empfangen'`, und der **vorhandene** Nachhol-Arbeiter
  greift sie nach Mitternacht auf (`repo.offene_aufnahmen_fuer_bot` liefert
  alles ausserhalb von fertig/fehlgeschlagen/laeuft, alle 60 s) — kein neuer
  Mechanismus. **Ausdruecklich nicht** ueber `_melde_transkriptionsfehler`:
  das zaehlt `repo.zaehle_versuch_hoch` hoch, und bei 60 s Nachholintervall
  waeren `MAX_VERSUCHE` in fuenf Minuten verbraucht — jedes Interview des
  Abends stuende am naechsten Morgen auf `fehlgeschlagen`.
  Die Gruppe bekommt **eine** Meldung, danach hoechstens alle 15 Minuten
  (Merkposten `gruppe.kostenpause_gemeldet_am` — in der Datenbank, weil ein
  Neustart sonst sofort wieder meldet), plus **einen** Vorfall je Tag.
  Erkenner und Journal fallen still aus, das Wasserzeichen bleibt stehen.
  Der Text nennt **keinen Betrag**: eine Zahl, die der Betreiber setzt, sagt
  einer Theatergruppe nichts darueber, was sie tun soll. Env:
  `IT_KOSTEN_DECKEL_CHF` (Vorgabe 5.0), `IT_ZEITZONE` (Vorgabe Europe/Rome).
```

- [ ] **Schritt 3: `AGENTS.md` — ein Abschnitt „Die Absicherung der Weboberflaeche"**

Hinter „Die Gruppenseite aendert Parameter":

```markdown
### Die Absicherung (30.09.2026, Karte Padua S)

Seit Karte A2 ist die Gruppenseite schreibend und nimmt Audio an. Damit ist
der Link nicht mehr nur eine Anzeige, und die Grenzen mussten mitwachsen.

**Sechs Kopfzeilen an genau einer Stelle** (`web._Basishandler.end_headers`):
`Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Permissions-Policy: microphone=(self)` und eine CSP ohne jede Fremdquelle
(`default-src 'none'`, `frame-ancestors 'none'`, `base-uri 'none'`,
`form-action 'self'`, `connect-src 'self'`, `media-src 'self' blob:`).
In `end_headers` und nicht in `_antworte`, weil `send_error` der
Standardbibliothek (501 bei unbekannter Methode, 400 bei kaputter
Anfragezeile) daran vorbeigeht — und genau diese Antworten testet niemand von
Hand. `sys_version` ist leer: bis dahin stand `Python/3.11.15` im
Server-Header jeder Antwort.

**Der CSP-Nonce ist abgeleitet, nicht gewuerfelt** (`web.csp_nonce`), aus
demselben Stundenfenster wie der Formular-Nonce. Der Grund ist derselbe:
`_SCROLL_JS` vergleicht alle zehn Sekunden `document.body.innerHTML`, und das
`<script>`-Tag steht im Koerper — ein je Antwort neuer Nonce liesse die Seite
alle zehn Sekunden austauschen und risse jedes offene Eingabefeld mit.
`'unsafe-inline'` steht bewusst nicht in der Richtlinie: ein stundenstabiler
HMAC muss geraten werden, `'unsafe-inline'` muss gar nichts. **Wer ein
`style="…"`-Attribut oder ein `onclick=` einbaut, bricht das** — heute ist
beides in `web.py` nicht vorhanden (gemessen).

**Origin und Sec-Fetch-Site vor jeder Wirkung** (`web.eigene_herkunft`, 403).
Der Nonce schuetzt, *weil* eine fremde Seite ihn nicht lesen kann — und beim
Audio-Upload stand er in der Query und damit in der Serverlogzeile. Er ist
nach `X-Nonce` umgezogen, `log_message` maskiert das Token auf vier Zeichen
und wirft die Query weg. **Fehlt `Origin` ganz, entscheidet der Nonce wie
bisher**: `curl` schickt keinen, und das Reviewer-Drehbuch faehrt mit `curl`.

**Rate-Limit je Gruppe** (`web_grenze.py`): 20 Nachrichten je Minute
(Senden, Knopf und Umschalter teilen den Topf — sonst laesst sich abwechseln
und die Rate verdoppeln) und 150 Uploads je Stunde (eigener Topf: 45-s-
Segmente sind 80 je voller Interviewstunde, dazu Push-to-talk). Schluessel ist
die **`chat_id`**, nicht das Token: eine Rotation darf das Limit nicht
zuruecksetzen. Eine abgewiesene Anfrage zaehlt **nicht** mit, sonst wuerde aus
dem Limit eine Dauersperre. 429 mit `Retry-After`, ein Vorfall
`web_rate_limit` je Fenster. **Ein Neustart vergisst die Zaehler** — benannt
und akzeptiert, nginx ist die zweite Schicht (unten).

**Der Upload wird an den Bytes geprueft, nicht am Header**
(`web_chat.endung_aus_bytes`). Der `Content-Type` bleibt billiger Vorfilter
(415 ohne Lesen); entschieden wird an den Magic Bytes (EBML, `OggS`, `ftyp`,
`RIFF/WAVE`, `ID3`/Frame-Sync), und **die Endung, unter der die Datei
abgelegt wird, kommt von dort**. Das ist Falle 3 eine Etage hoeher: ein WebM
als `.ogg` abgelegt laesst den Whisper-Auftrag dauerhaft auf `pending`
stehen. Groesse: `MAX_AUDIO_BYTES` = 8 MiB je Segment — gerechnet gegen Opus
32 kbit/s (45 s ≈ 176 KiB) und Safaris AAC 64 kbit/s (≈ 352 KiB), also rund
zwanzigfache Luft, und klar unter `stt.MAX_UPLOAD_BYTES` (25 MiB): was
Whisper ohnehin ablehnt, soll gar nicht erst ankommen. Ueber der Grenze wird
**nichts gelesen** (413, Verbindung zu). Die **Dauer meldet der Client** und
ist deshalb kein Schutz; sie wird trotzdem geprueft, weil weiter unten
`aufnahme.HINWEIS_AB_S` daran haengt.

**Token-Rotation von Hand** (`scripts/web_token_neu.py`, `repo.erneuere_web_token`):
ohne `--ja` Trockenlauf, mit `--ja` Backup, Journaleintrag (**ohne Token**)
und die neue URL auf stdout. Der alte Link ist **sofort** 404 — der Webserver
haelt kein Token im Speicher, jede Anfrage oeffnet ihre eigene read-only
Verbindung; ein Neustart ist nicht noetig. Der alte Nonce ist an den alten
Token-String gebunden und damit ebenfalls tot. **Kein Chat-Befehl**:
rotieren heisst, dass jedes Telefon im Raum seinen Link verliert, und das ist
eine Betreiberhandlung mit Ansage, wie `scripts/loeschen.py`.

**Fehlerseiten verraten nichts**: ein Catch-all um `do_GET`/`do_POST`
antwortet mit 500 und einem festen Satz, der Traceback geht ins Log.
`send_error` ist ueberschrieben — die Vorlage der Standardbibliothek setzt
`%(message)s` und `%(explain)s` in den Koerper. Vor dieser Karte gab eine
Ausnahme im Handler **gar keine Antwort** (`RemoteDisconnected`), was das
sanfte Nachladen stumm schluckte.

### nginx auf herkules (Admin, NICHT umgesetzt)

Die App-Grenzen sind die erste Schicht; sie leben im Prozess und sind nach
einem Neustart leer. Die zweite gehoert vor den Prozess. **Dieser Block ist
ein Vorschlag fuer den Admin und steht in keiner Datei dieses Repositories** —
er passt zu den Werten oben und muesste mitgezogen werden, wenn die sich
aendern.

```nginx
# http { } -- einmal, ausserhalb des server-Blocks
limit_req_zone  $binary_remote_addr  zone=theatersoap_post:10m  rate=30r/m;
limit_req_zone  $binary_remote_addr  zone=theatersoap_audio:10m rate=200r/h;
limit_conn_zone $binary_remote_addr  zone=theatersoap_conn:10m;

location /theatersoap/ {
    proxy_pass http://127.0.0.1:8010/theatersoap/;

    # Etwas ueber der App-Grenze (8 MiB je Segment): nginx soll die
    # Verbindung kappen, bevor die App liest -- aber nicht frueher als sie,
    # sonst diagnostiziert man einen Fehler an der falschen Stelle.
    client_max_body_size 10m;
    client_body_timeout  60s;

    limit_conn theatersoap_conn 20;
}

location ~ ^/theatersoap/g/[^/]+/chat/audio$ {
    proxy_pass http://127.0.0.1:8010;
    limit_req  zone=theatersoap_audio burst=20 nodelay;
    client_max_body_size 10m;
}

location ~ ^/theatersoap/g/[^/]+/chat/(senden|knopf|interview)$ {
    proxy_pass http://127.0.0.1:8010;
    limit_req  zone=theatersoap_post burst=10 nodelay;
}
```

Drei Hinweise dazu: die nginx-Zonen zaehlen je **IP**, die App je **Gruppe** —
das ist Absicht, zwei Achsen fangen zwei verschiedene Angriffe. Die
nginx-Raten liegen **ueber** den App-Grenzen, damit die App die Absage gibt
(mit `Retry-After` und einem Satz) und nicht nginx mit einer nackten 503. Und
die Gruppen sitzen im Workshop haeufig hinter **einer** IP (Raum-WLAN) —
deshalb die grosszuegigen `burst`-Werte.
```

- [ ] **Schritt 4: `docs/betrieb-env.beispiel`**

Ans Ende des Bot-Abschnitts:

```
# --- Kostendeckel (30.09.2026, Karte Padua S) -----------------------------
# Wieviel eine Gruppe an einem Tag hoechstens an Modellaufrufen kosten darf
# (CHF, alle Anbieter zusammen). Ist er erreicht, pausiert der Bot bis
# Mitternacht: empfangen und speichern laeuft weiter, nur Modellaufrufe
# fallen aus. Gilt fuer Telegram und Web gleichermassen.
# IT_KOSTEN_DECKEL_CHF=5.0
#
# Wonach sich "heute" richtet. Padua liegt in Italien -- ohne das schluege
# der Workshoptag um 02:00 Ortszeit um, weil UTC es tut.
# IT_ZEITZONE=Europe/Rome
```

- [ ] **Schritt 5: Die Doku gegen den Code pruefen**

```
$PY -m pytest tests/test_anweisungen.py -q -p no:cacheprovider
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: gruen, `>=` Baseline + 136.

Und die Zahlen in AGENTS.md gegen den Code:

```bash
$PY -c "
from interview_theater import kosten, web_grenze, web_chat
print('Deckel', kosten.VORGABE_DECKEL_CHF, '| Zone', kosten.VORGABE_ZEITZONE)
print('Nachrichten/min', web_grenze.NACHRICHTEN_JE_MINUTE,
      '| Uploads/h', web_grenze.UPLOADS_JE_STUNDE)
print('Audio', web_chat.MAX_AUDIO_BYTES // 1024 // 1024, 'MiB')
"
```
Erwartet: `Deckel 5.0 | Zone Europe/Rome`, `Nachrichten/min 20 | Uploads/h 150`,
`Audio 8 MiB` — und dieselben Zahlen im Text.

- [ ] **Schritt 6: Commit**

```bash
git add AGENTS.md docs/betrieb-env.beispiel
git commit -m "Doku: Absicherung der Weboberflaeche, Kostendeckel, nginx-Vorschlag

Der nginx-Block ist ein Vorschlag fuer den Admin und steht als Text in
AGENTS.md -- keine Datei ausserhalb des Repositories wird angefasst. Die
nginx-Raten liegen ueber den App-Grenzen, damit die App die Absage gibt
(Retry-After und ein Satz) und nicht nginx eine nackte 503.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 11: Whisper-Preis und Dauerfeld nachmessen · **KOSTET GELD — nicht ohne Freigabe**

> **Der Umsetzer faehrt diese Aufgabe NICHT.** Sie braucht Birks ausdrueckliche Freigabe.
> Alles darueber ist ohne einen einzigen bezahlten Aufruf fertig und gruen.

**Warum sie ueberhaupt im Plan steht:** zwei Werte tragen den Kostendeckel und sind **nicht
gemessen**.

1. **`kosten.WHISPER_CHF_JE_MINUTE = 0.006`** (ANNAHME A-20). Quelle:
   `~/hermes-shared/hermes-knowledge/infomaniak-modelle.md` § 6.4 — eine Datei **ausserhalb
   dieses Repositories**, die in diesem Planlauf nicht gelesen werden konnte. Stimmt der
   Wert nicht, stimmt der Whisper-Anteil des Deckels nicht: bei 100 Minuten Audio am Tag
   sind das nach heutigem Stand 0,60 CHF, also gut ein Zehntel des Budgets.
2. **Ob die Whisper-Antwort ein Dauerfeld traegt.** `stt.abholen` (`stt.py:164-219`) liest
   nur `data.text`. Traegt die Antwort eine `duration`, waere sie die bessere Quelle als
   `aufnahme.dauer_sekunden` — vor allem fuer Aufnahmen ohne gemeldete Dauer, die heute mit
   0 CHF gebucht werden.
3. **`kosten.PREISE_CHF_JE_MIO_TOKEN` hat Stand 04.09.2026** (ANNAHME A-21) und ist seither
   nicht nachgezogen. Ein Preis, der gestiegen ist, laesst den Deckel zu spaet greifen.

- [ ] **Schritt 1: Freigabe einholen**

Birk fragen. Kosten: ein Whisper-Aufruf auf eine kurze Datei (wenige Rappen), plus ein Blick
in die Preisliste des Anbieters (kostenlos).

- [ ] **Schritt 2: Eine kurze Aufnahme durchschicken und die Rohantwort ansehen**

```bash
set -a; . ./betrieb/gruppe1.env; set +a
$PY -m scripts.rauchtest <pfad-zu-audio.ogg>
```

Dazu ein einmaliger Blick in die Rohantwort von `stt.abholen`: laeuft
`$PY -m scripts.rauchtest` mit `IT_LOG=debug` (oder einem `print` in einer lokalen,
**nicht committeten** Kopie), zeigt sich, ob `data` neben `text` ein Dauerfeld traegt.

- [ ] **Schritt 3: Die Werte nachziehen und den Stand hochsetzen**

Aendern sich Zahlen, dann in `interview_theater/kosten.py`:
`WHISPER_CHF_JE_MINUTE`, `WHISPER_STAND`, `PREISE_CHF_JE_MIO_TOKEN`, `PREISE_STAND`.
Traegt die Antwort eine Dauer, bekommt `stt.abholen` einen zweiten Rueckgabewert und
`aufnahme._buche_stt` nimmt ihn — **mit `aufnahme.dauer_sekunden` als Rueckfall**, weil der
Textimport (`aufnahme.importiere_text`) gar keinen Whisper-Lauf hat.

- [ ] **Schritt 4: Commit**

```bash
git add interview_theater/kosten.py interview_theater/stt.py interview_theater/aufnahme.py
git commit -m "Kosten: Whisper-Preis und Preistabelle nachgemessen (Stand <datum>)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Abnahme der ganzen Karte

- [ ] `$PY -m pytest -q -p no:cacheprovider` → gruen, `>=` Baseline aus Aufgabe 0 **+ 136**
      (13 + 11 + 19 + 30 + 15 + 16 + 5 + 27)
- [ ] `$PY -m scripts.pruefe_profil dortmund-2026` → gruen
- [ ] `$PY -m pytest tests/test_profil_bitgleich.py -q -p no:cacheprovider` → gruen
      (kein Prompt hat sich geaendert)
- [ ] Jeder der neun Pflicht-Angriffstests ist benannt, liegt in seiner Datei und war
      **rot**, bevor sein Schutz gebaut wurde:

| Angriff | Test | Datei |
|---|---|---|
| falsches Token → 404 | `test_unbekanntes_token_ist_404` (aus A2, **eigene Datei der A2-Umsetzung**, nicht `test_web_token_rotation.py`) + `test_der_alte_link_ist_sofort_404` (`tests/test_web_token_rotation.py`) | siehe Spalte Test |
| rotiertes Token → alt 404, neu 200, alter Nonce 403 | `test_der_alte_link_ist_sofort_404`, `test_der_alte_nonce_gilt_am_neuen_token_nicht` | `tests/test_web_token_rotation.py` |
| Upload ueber Grenze → 413, nichts auf Platte/in DB | `test_upload_ueber_der_grenze_ist_413_und_nichts_bleibt` | `tests/test_web_chat_upload.py` |
| falscher Typ → 415 | `test_html_als_audio_deklariert_ist_415` | `tests/test_web_chat_upload.py` |
| 50 Nachrichten in 10 s → 20×202, Rest 429, 20 Zeilen | `test_fuenfzig_nachrichten_in_zehn_sekunden` | `tests/test_web_chat_flut.py` |
| POST von fremdem Origin mit gueltigem Nonce → 403 | `test_fremder_origin_ist_403_trotz_gueltigem_nonce` | `tests/test_web_herkunft.py` |
| POST ohne Nonce → 403 | `test_post_ohne_nonce_bleibt_403` | `tests/test_web_herkunft.py` |
| Kostendeckel (gemockt) → kein Netzaufruf, Meldung einmal, beide Kanaele | `test_ueber_dem_deckel_faellt_der_llm_aufruf_ohne_netz_aus`, `test_die_pausenmeldung_kommt_einmal`, `test_der_deckel_gilt_im_telegram_kanal`, `test_der_deckel_gilt_im_web_kanal` | `tests/test_kostendeckel.py` |
| Reset: gestern 23:59 Rom zaehlt heute nicht | `test_gestern_dreiundzwanzig_neunundfuenfzig_zaehlt_heute_nicht` | `tests/test_kostendeckel.py` |
| Kopfzeilen ueber alle Routen inkl. Fehlerstatus | `test_jede_route_traegt_die_pflichtkopfzeilen`, `test_auch_die_fehlerseiten_tragen_sie` | `tests/test_web_kopfzeilen.py` |
| Fehlerseite ohne Traceback/Pfad | `test_ausnahme_im_handler_wird_500_ohne_traceback` | `tests/test_web_kopfzeilen.py` |

- [ ] Das Reviewer-Drehbuch (Aufgabe 9) ist **gefahren**, nicht nur gelesen, und jede
      erwartete Statuszeile ist eingetreten.
- [ ] `betrieb/**` wurde nicht gelesen, kein echtes Token steht in einem Commit, einem
      Test-Artefakt oder einer Terminalausgabe.
- [ ] Aufgabe 11 ist **nicht** gefahren (oder Birk hat sie freigegeben).

---

## Fuer Birk

Punkte, die dieser Plan gesetzt hat, aber nicht entscheiden kann.

1. **Claude-Proxy zaehlt nicht gegen den Deckel.** Die Umsetzung bucht
   `kosten.CLAUDE_CHF_JE_AUFRUF = 0.0` fuer jeden Aufruf ueber den lokalen Proxy, weil er
   ueber ein Abonnement laeuft (so steht es im Docstring von `szene_claude.prosa`). Das
   heisst: eine Gruppe mit `IT_SZENE_ANBIETER=claude` kann beliebig viele Szenen schreiben,
   ohne dass der Deckel es sieht — **der Szenenlauf ist der teuerste Einzelposten des Tages,
   und er ist der einzige, den der Deckel nicht misst.** Der Wert steht an einer Stelle und
   ist eine Zeile weit umstellbar. **Frage: soll das so bleiben?**
2. **Die Preistabelle hat Stand 04.09.2026** und ist seither nicht nachgezogen worden
   (`scripts/pruefe_prompts.py:97`, jetzt `kosten.PREISE_CHF_JE_MIO_TOKEN`). Ein gestiegener
   Preis laesst den Deckel zu spaet greifen. Nachziehen kostet nichts (Preisliste ansehen),
   steht aber in keiner Aufgabe, weil dieser Lauf keine externe Quelle abrufen durfte.
3. **Der Whisper-Preis (0,006 CHF/min) ist uebernommen, nicht gemessen** — Quelle ist eine
   Datei ausserhalb des Repositories. Aufgabe 11 wuerde ihn nachmessen und kostet Geld.
4. **Fuenf Franken je Gruppe und Tag** ist die Zahl aus der Karte. Zur Einordnung, mit den
   Zahlen aus AGENTS.md: ein voller Simulationslauf kostet 0,20–0,60 CHF, ein Szenenlauf
   mit Reasoning ist der teuerste Einzelposten. Fuenf Franken sind damit grosszuegig fuer
   einen normalen Workshoptag und knapp fuer einen, an dem viel geschrieben wird. Umstellbar
   ueber `IT_KOSTEN_DECKEL_CHF`, je Gruppe verschieden setzbar.
5. **Das Rate-Limit vergisst sich beim Neustart des Webdienstes.** Akzeptiert, weil nginx die
   zweite Schicht ist — aber der nginx-Block in AGENTS.md ist ein **Vorschlag**, den jemand
   auf herkules eintragen muss. Bis dahin ist die App die einzige Schicht.
6. **Eine Aufnahme ohne gemeldete Dauer wird mit 0 CHF gebucht.** Die eine Stelle, an der
   der Deckel weniger sieht, als anfaellt. Im Betrieb traegt jede Telegram-Sprachnachricht
   ihre Dauer und der Web-Upload meldet sie — der Fall tritt nur bei einem Dokument-Upload
   ohne Metadaten auf.
7. **Nach einer Token-Rotation muss jemand den neuen Link verteilen.** Das Skript gibt ihn
   auf stdout aus; der Bot schickt ihn **nicht** von selbst in den Chat (ein Skript spricht
   nicht mit Telegram, und der Chat ist der Ort, an dem der alte Link schon steht). Ob eine
   Zeile in den Chat gehoert, ist eine Entscheidung mit Aussenwirkung.

---

## Selbstpruefung des Plans

**Abdeckung der Karte** — jeder der sechs Kartenpunkte hat eine Aufgabe:

| Kartenpunkt | Aufgabe |
|---|---|
| 1 Upload-Obergrenze, falsche Typen ablehnen | 4 |
| 2 Rate-Limit je Token in der App (+ nginx im Bericht) | 3, nginx in 10 |
| 3 Kostendeckel 5 CHF/Tag, Reset Mitternacht Rom, Web und Telegram | 6, 7, 8 |
| 4 Token-Rotation, alter Link sofort 404 | 5 |
| 5 Fuenf Kopfzeilen + CSP ohne Fremdquellen | 1 |
| 6 Fehlerseiten verraten nichts | 1 |
| Abnahme: je Punkt ein Angriffstest, der ohne Schutz rot ist | Tabelle „Abnahme der ganzen Karte" |
| Reviewer faehrt die Angriffe selbst mit curl | 9 |

**Abdeckung der Architektenentscheidungen E-S1 bis E-S10:**
E-S1 → Aufgabe 6+7 · E-S2 → 8 · E-S3 → 8 · E-S4 → 3 · E-S5 → 4 · E-S6 → 5 · E-S7 → 1 ·
E-S8 → 1 · E-S9 → 2 · E-S10 → Globale Vorgaben 3/6 und die Abnahme.

**Eine Abweichung, benannt:** Der Kartentext schlaegt „25 MB / 15 min" vor; der Plan nimmt
8 MiB und laesst `MAX_DAUER_S = 3600`. Rechnung und Grund stehen in Aufgabe 4 — E-S5
verlangt ausdruecklich, die Zahl gegen A2 und die Whisper-Grenze zu pruefen und die
gewaehlte mit Rechnung zu nennen.

**Eine Praemisse, widerlegt:** „Kosten stehen im `aufruf`-Protokoll" — sie stehen nicht dort
(Beleg im Kopf, `db.py:705-717`, `stt.py`, `scripts/pruefe_prompts.py:97`). Aufgabe 6 und 7
bauen sie.

**Nichts kostet Geld** ausser Aufgabe 11, und die ist als solche markiert und gesperrt.







# AGENTS.md

Technische Referenz für Agenten und Entwicklerinnen, die an diesem Code
arbeiten — **als Index**. Das Projekt ist ein Telegram- und Web-Bot für
partizipative Theater-Workshops: eine Gruppe sammelt Begriffe und Fragen,
führt Interviews, erfindet Setting, Figuren und Geschichte und kommt mit dem
Bot bis zum Textbuch. Ein Python-Prozess je Gruppe (gleicher Code, eigener
Bot-Token bzw. eigene `IT_WEB_CHAT_ID`, eigene `chat_id`), alle Prozesse
teilen sich eine SQLite-Datei (WAL-Modus, `busy_timeout`). Der Zustand liegt
vollständig in der Datenbank — ein Neustart verliert nichts. Primärquelle für
Entwurfsentscheidungen ist `SPEC-kontext-architektur.md`; **bei Widerspruch
zwischen SPEC und Code gilt der Code** (`docs/agents/spec-abweichungen.md`).
Für die Perspektive der Theatergruppe siehe [README.md](README.md).

Der Volltext dieser Datei (bis 05.10.2026 rund 258 kB) steht unverkürzt
unter `docs/agents/` — siehe „Index" unten.

## 🔴 Dortmund eingefroren seit 04.10.2026 — Abnahme nur noch an Padua

Birk, 04.10.2026: Dortmund wird nicht mehr gepflegt; kein Dortmund-Bot läuft
mehr, nur die drei Padua-Bots sind live. **„Dortmund byte-gleich/bitgleich"
und `pruefe_profil dortmund-2026` sind keine Abnahmekriterien mehr.**
Abgenommen wird nur noch:

- Suite grün mit `-m "not dortmund"` (siehe „Starten und testen"),
- `pruefe_profil padua-2026` grün,
- Prompt-Snapshot nur für Padua.

Der Dortmund-Stand ist reproduzierbar unter dem Tag `dortmund-2026-final`
(SHA `2e552399749311f3787b375fa4df7d1e30e4097d`). Ein Test, der **nur**
wegen Dortmund-Verhalten rot wird, bekommt `@pytest.mark.dortmund` (Marker
in `pyproject.toml`) statt angepasst zu werden. Die Fixtures
`tests/fixtures/*dortmund*` und `*vorgabe*` werden **nicht** neu erzeugt.
Neue Funktionen nur für Padua — wo ein Profilschalter Dortmund/Padua trennt,
direkt das Padua-Verhalten bauen, **keine neuen Schalter**; bestehende
bleiben stehen bis zum Aufräumen ab 10.10.2026 (Birks Entscheidung). **Nicht
anfassen:** `betrieb/gruppe1-4.env`, Dortmund-Daten in `betrieb/soap.db`,
Dortmund-Code — nichts löschen. Wo die Doku unter `docs/agents/` Dortmund als
bindende Invariante verlangt, gilt stattdessen dieser Absatz. Wortlaut:
`docs/agents/aufbau.md`.

## Modulkarte

Vier Schichten, von unten nach oben; jede liest nur nach unten. Die wenigen
Aufrufe nach oben stehen als **lokaler Import in der Funktion**, die sie
braucht — das ist im ganzen Repo die Bauart, mit der Zyklen aufgelöst werden
(`from interview_theater import befehle` mitten in einer Funktion ist kein
Versehen).

| Schicht | Module |
|---|---|
| **Ablage** | `db.py` · `repo.py` · `web_daten.py` |
| **Dienste** | `llm.py` · `strom.py` · `stt.py` · `telegram.py` · `einstellungen.py` · `workshop.py` · `sprache.py` · `anweisungen.py` · `zitat.py` · `vorschlag.py` · `stile.py` · `vorschlagssperre.py` · `web_kanal.py` · `kosten.py` · `web_grenze.py` |
| **Fachlogik** | `phasen.py` · `kontext.py` · `erkenner.py` · `journal.py` · `verdichter.py` · `begriffe.py` · `aufnahme.py` · `begriffsboard.py` · `begriffsboard_analyse.py` · `szene.py` · `szene_claude.py` · `szenenfolge.py` · `kurzgeschichte.py` · `kuerzung.py` · `roadmap.py` · `ruecknahme.py` · `schaerfung.py` · `stueckpruefung.py` · `kernzitate.py` · `sprachprofil.py` · `sprachstil.py` · `sprecher.py` · `fehlstellen.py` · `arbeitszeilen.py` · `leitfaden.py` · `laengen.py` · `sprachpass.py` · `nachpass.py` · `prueflauf.py` · `ueberarbeitung.py` · `sprechweise.py` |
| **Oberfläche** | `bot.py` · `ablauf.py` · `befehle.py` · `knoepfe/` · `phasentexte.py` · `web.py` · `web_schreiben.py` · `web_chat.py` · `web_vereint.py` · `web_gestalt.py` |

**SQL nur in `repo.py` und `db.py`.** Einzige Ausnahme: `web_daten.py`, die
read-only (`file:…?mode=ro`) geöffnete Leseseite der Weboberfläche — sie
durch `repo` zu führen nähme den Schreib-Lock des Bots für Dashboard-Abfragen.

Je Modul ein Satz (Volltext mit Begründungen: `docs/agents/aufbau.md`):

- `bot.py` — Startroutine, Long-Poll-Schleife (`bot.schleife`), Begrüßung, Warmlaufen, Kanalwahl (`baue_kanal`).
- `ablauf.py` — der Gesprächszug: Sperre je `chat_id`, Kontextaufbau anstoßen, Antwort (Echo-/Wiederholungsschutz) verschicken.
- `aufnahme.py` — Aufnahme-Pipeline: Download, Transkription, Verdichtung, Nachhol-Arbeiter, Interviewfluss (ein Interview = Kopf + Teile).
- `begriffsboard.py` — das laufende Begriffsboard der Phase 1 (Schema-Aufruf je Segment, im Code validiert, Tabelle `begriffsboard` nur anhängend, kein `tg`).
- `befehle.py` — die Slash-Befehle (`_BEKANNTE_BEFEHLE`); kein Befehl ruft synchron ein Modell.
- `erkenner.py` — Absichtserkenner: erkennt Änderungsabsichten, wendet sie an (`wende_an`), baut die „Notiert:"-Meldung.
- `journal.py` — Journal-Extraktor für den aus dem Fenster verdrängten Gesprächsabschnitt.
- `kontext.py` — baut den Gesprächs-Prompt datengetrieben (`baue`), mit Fenster in Zeichen und Kürzung.
- `phasen.py` — die sieben Arbeitsphasen (`PHASEN`) und `voraussetzungen` (die einzige Stelle, die sagt, wann es weitergeht).
- `phasentexte.py` — Eintritts-/Abschlussnachricht je Phase und `/stand`-Zeilen; kein Modellaufruf.
- `sprecher.py` — Sprechanteile je Figur, gezählt über `szene.volltext`.
- `fehlstellen.py` — was der Gruppe noch fehlt, als Sätze; reine Leseabfrage.
- `roadmap.py` — Phasenübersicht und Werkbank als Daten; Aufgabennamen an `phasentexte.PARAMETER` genagelt.
- `llm.py` — Sprachmodell-Client (chat/completions), JSON-Auslesen, Retry, Kostendeckel-Prüfung in `_anfrage`.
- `strom.py` — dekodiert den wachsenden JSON-Präfix eines Schema-Aufrufs für den laufenden Text; keine Datenbank.
- `stt.py` — Whisper-Anbindung, zweistufig und asynchron.
- `telegram.py` — dünner Wrapper um die Telegram-Bot-API.
- `web_kanal.py` — `WebKanal` ersetzt `telegram.Telegram` bei `IT_KANAL=web`, über die Tabelle `web_post`.
- `szene.py` — Szenentexte im eigenen Thread, einziger Aufruf mit Reasoning AN, Sperre bei fehlenden Pflichtfeldern.
- `szene_claude.py` — zweiter Anbieterpfad (Anthropic über lokalen Proxy), nur nach USA-Einwilligung.
- `szenenfolge.py` — Szenenfolge und Geschichte als Vorschlag, Textbuch als Datei.
- `kurzgeschichte.py` — Phase 6: ein Prosalauf über die ganze Geschichte, Abschnitte werden Szenen.
- `kuerzung.py` — „Kürzer (25 %)": feste Regie-Notiz, Zielwahl; kein eigener Modellaufruf, nie eine neue Szenenfolge.
- `schaerfung.py` — Phase 5: legt geprüfte Interviewstellen auf Szenen und Figuren (Tabelle `schaerfung`).
- `stueckpruefung.py` — der Stück-Judge über das ganze Textbuch.
- `kernzitate.py` — Auswahl der Belegzitate, rückwärtskompatible Basis der Schärfung.
- `sprachprofil.py` — Sprachprofil je Figur aus dem zugeordneten Interview, Zitate geprüft.
- `sprachstil.py` · `stile.py` — gewählter Sprachstil je Figur bzw. Stilvorlage je Szene.
- `sprechweise.py` — Sprechweise je Figur vor der Bühnenfassung, nur für Figuren ohne `figur.sprachstil`.
- `kosten.py` — Preistabelle, Kosten je Aufruf, Tagesdeckel je Gruppe; kein SQL.
- `ruecknahme.py` — Undo eines Erkennerlaufs per Schnappschuss-Diff; reine Funktionen.
- `laengen.py` — Längen-Rhythmus und Budget je Szene aus dem Profil; kein Modellaufruf.
- `sprachpass.py` — vier Regex-Zähler für Sprach-Tells plus Zitatschutz; kein Modellaufruf.
- `nachpass.py` — der EINE Überarbeitungslauf am Ende eines Schreibvorgangs, im Thread und unter der Sperre des Schreibwegs.
- `prueflauf.py` — Padua: Prüflauf vor jeder Anzeige (`schleife.schliesse`, höchstens zwei Runden), Tabelle `prueflauf`.
- `ueberarbeitung.py` — Padua: Phasen 6/7 als Zustandsmaschine (`weiter_6`/`weiter_7`); kein SQL, kein Modellaufruf.
- `leitfaden.py` — baut den Gesprächsleitfaden deterministisch.
- `vorschlag.py` — die `VORSCHLAG …:`-Markerzeilen im Antworttext lesen und entfernen.
- `vorschlagssperre.py` — die eine Sperre, die Schärfung und Szenenfolge trennt, mit Merkplatz; kein Projektimport.
- `vorspann.py` — der Vorspann vor dem Text (Wo/Wann, Figuren); deterministisch.
- `verdichter.py` — verdichtet ein Transkript zu Zusammenfassung und Kernthemen mit Belegzitaten.
- `zitat.py` — Belegzitat-Verifikation (`zitat.pruefe`), die eine Normalisierung für alle Prüfungen.
- `knoepfe/` — Inline-Knöpfe (Angebot, Idempotenz, Wirkung), acht Module; `knoepfe/wirkung.py` trägt `_WIRKUNGEN`.
- `dramaturgie/` — feinkörnige Prüfung: `mechanik`, `beleg`, `fanout`, `bilanz`, `schleife` (`docs/agents/dramaturgie-pruefung.md`).
- `repo.py` — die SQL-Schicht des Bots, `RLock`-serialisiert.
- `db.py` — Schema, PRAGMAs, additive Migration, Löschweg (`loesche_gruppe`).
- `einstellungen.py` — Konfiguration ausschließlich über Umgebungsvariablen.
- `anweisungen.py` — Prompt-Texte mit Hot-Reload, Regie-Zettel, Einhängepunkt des Workshop-Profils.
- `workshop.py` — lädt `workshop/<name>/*.toml` über `IT_WORKSHOP`.
- `sprache.py` · `sprachen/` — Sprachschicht `T` (`de`/`en`), Texte in `sprachen/<code>/texte.toml`.
- `web.py` — Routing, HTML und CSS der Weboberfläche, nur Standardbibliothek.
- `web_daten.py` — read-only Lesezugriffe für die Weboberfläche.
- `web_schreiben.py` — Schreibpfade der Gruppenseite, ausschließlich über `repo` (`FELDER`).
- `web_chat.py` — Chatansicht im Browser: HTML-Filter, Knopfprüfung, Audio-Upload.
- `web_vereint.py` — die vereinte Gruppenseite (Tabs, Phasenleiste, SSE `/chat/strom`, `scope_css`).
- `web_gestalt.py` — Design-Tokens, Komponenten-CSS, Effekt-JS (`IT_UX_ENTWURF`).
- `web_grenze.py` — Rate-Limit der Weboberfläche je `chat_id`; kein Projektimport.
- `prompts/` — Prompt-Texte als `.md` (`phasen/`, `formen/`, `dramaturgie/`, `stile/`).

Ohne eigene Zeile hier (siehe Docstring): `arbeitszeilen.py`,
`begriffe.py`, `begriffsboard_analyse.py`, `brainstorm.py`,
`buehnenkarte.py`, `cothinker_status.py`, `diskussion.py`, `entwurf.py`,
`fragen_auswertung.py`, `fragen_ki.py`, `handykarten.py`, `modellwahl.py`.

**Wo man anfängt** (vollständige Tabelle: `docs/agents/aufbau.md`):

| Frage | Einstieg |
|---|---|
| Warum antwortet der Bot (nicht)? | `ablauf.antworte` → `_zug_faellt_aus` |
| Was steht im Prompt? | `kontext.baue` → `_bloecke` → `_kuerze_auf_budget` |
| Was passiert bei einem Knopfdruck? | `knoepfe.behandle` → `knoepfe/wirkung.py`, `_WIRKUNGEN` |
| Was schreibt der Erkenner? | `erkenner.laufe` → `wende_an` → `baue_meldung` |
| Wie entsteht ein Szenentext? | `szene.starte` → `baue_nutzertext` → `schreibe` |
| Wann darf die Gruppe weiter? | `phasen.voraussetzungen` |
| Warum sieht der Browser nichts? | `web_kanal.hole_updates` → `repo.web_eingang` → `bot.schleife` |
| Warum antwortet der Bot heute gar nicht mehr? | `kosten.deckel_erreicht` → `repo.kostensumme_seit` |

## Harte Invarianten

Je eine Zeile; Begründung und Geschichte stehen in der genannten Datei.

- **Datenschutz/E8:** keine Klarnamen (Web: `nachricht.absender` = Rollenwort). Weboberfläche ohne Login: kein Nachrichtentext und kein Transkript aufs Dashboard, kein Volltranskript auf der Gruppenseite, kein Belegzitat ohne `zitat_geprueft = 1`; `IT_WEB_BIND` nie `0.0.0.0`. → `weboberflaeche.md`
- **Sprachschicht `T`:** Nutzertexte über `sprache.py` (`T._TEXT_X`), weitere Sprachen in `sprachen/<code>/texte.toml` und `sprachen/<code>/prompts/`; Deutsch bleibt die Python-Konstante selbst. → `aufbau.md`, `workshop-profil.md`
- **Bitgleich-Tests** (Prompt-Snapshot, Werkbank, Dashboard) binden nur noch für Padua; Dortmund-Abweichung → Marker. → oben
- **Die drei Knopf-Zusagen:** `callback_data` < 64 Bytes, nur `k:<id>` (Wert in Tabelle `knopf`); **kein Modellaufruf** in Knopf-Handlern und Slash-Befehlen — was ein Modell braucht, geht an einen Thread; idempotent über `repo.beanspruche_knopf`. Test: `tests/test_knoepfe_struktur.py`. → `entscheidungen.md`
- **Kostendeckel:** `kosten.py`, 5 CHF je Gruppe und Tag (`IT_KOSTEN_DECKEL_CHF`), Reset um Mitternacht Europe/Rome; Empfangen geht weiter, nur Modellaufrufe pausieren. → `entscheidungen.md`
- **Nur anhängen:** Journal, Verdichtungen, `szenenfassung`, `begriffsboard` werden nie geändert; entfernt wird **weich** (`entfernt_am`); Material (Aufnahmen, Transkripte, Verdichtungen) hat keinen Entfernungspfad außer `scripts/loeschen.py`. → `entscheidungen.md`
- **Jede Tabelle außer `bot_zustand` hat `chat_id`** (`db.TABELLEN_MIT_CHAT_ID`, Löschzusage). → `entscheidungen.md`
- **Schema nur additiv migrieren** (`db._migriere_fehlende_spalten`); tote Spalten bleiben stehen. → `spec-abweichungen.md`
- **Die Phase setzt allein die Gruppe** (Chat, `/phase`, Klick über `befehle.wechsle_phase`); kein automatischer Sprung — Datenstand ist nicht Absicht. → `entscheidungen.md`
- **`repo.setze_szene_usa` nimmt einen bool**, nie `"ja"`/`"nein"` (ein „nein" wäre wahr). → `entscheidungen.md`
- **Erkenner-Prompt-Änderung gilt nur mit FP = 0** im Korpuslauf; der Lauf kostet Geld und läuft nie automatisch. → `korpus-und-simulation.md`
- **Kein CSS-Kommentar direkt vor einer Regel** in `_BUEHNE` (`web_gestalt.css_buehne`): `web_vereint.scope_css` reißt sonst das Scope-Präfix ab. → `aufbau.md`
- **CSP:** kein `style="…"`-Attribut, kein `on…=`-Handler, kein Webfont; dynamische Werte über CSSOM. → `weboberflaeche.md`
- **Live-Dienste** (`interview-theater*`) **nie starten, stoppen oder neu starten aus einem Arbeitsauftrag.**

## Starten und testen

Die Suite (dauert ~10 min, ohne Netz, Attrappen statt echter Dienste):

```
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider
```

- Marker `dortmund` ist in `pyproject.toml` registriert (siehe oben).
- `tests/e2e/` läuft mit Playwright im Browser; ohne Playwright wird es übersprungen.
- **Betrieb über systemd-User-Units, nie Handstart** (zwei Handstarts = `409 Conflict`): Vorlage `docs/interview-theater@.service`, Start über `scripts/betrieb-start.sh <gruppe>` (Python 3.11, Profilprüfung vorab mit `scripts/pruefe_profil.py`). Web: `docs/interview-theater-web.service`.
- Web-Gruppe anlegen: `python -m scripts.web_gruppe anlegen <bot_name>` (Datei `scripts/web_gruppe.py`); `IT_KANAL=web` und `IT_WEB_CHAT_ID` in der Env.
- Testinstanz: `scripts/test_uebernehmen.py` spielt den Stand einer Padua-Gruppe auf `betrieb/padua-test.db` → Anleitung `docs/testgruppe-padua.md`.
- **Skripte, die Geld kosten, laufen nie automatisch:** `scripts.rauchtest`, `scripts.pruefe_prompts`, `scripts.simulation`, `scripts/dramaturgie_pruefen.py`.

Volltext: `docs/agents/starten-und-testen.md`, `docs/agents/korpus-und-simulation.md`.

## Die wichtigsten Fallen

Jede gemessen, keine geraten (Volltext: `docs/agents/fallen.md`).

1. **`IT_LLM_URL` braucht die volle URL inklusive `/chat/completions`** — sonst HTTP 404.
2. **Whisper liegt unter `/1/ai/{produkt}/…`** und ist zweistufig (`batch_id`, dann pollen); das Feld `data` ist ein JSON-String und wird doppelt geparst.
3. **Der MIME-Typ kommt aus der Dateiendung** (`stt.mime_typ()`); ein falscher Typ bleibt still auf `pending` hängen.
4. **`reasoning_effort` immer senden** — `"none"` ist aus, Weglassen schaltet Reasoning AN. Einzige Ausnahme mit Reasoning: `szene.py` (eigenes `max_tokens` und Zeitbudget).
5. **Modellwahl je Aufruf:** gemma für Erkenner und Journal, Kimi für Gespräch und Verdichter; Nemotron-Nano nie als Vorgabe.
6. **SQLite über Threads ist nicht sicher** — jede `repo`-Funktion läuft unter `repo._LOCK` (ein `RLock`, kein `Lock`).
7. **Nie denselben Bot zweimal starten**, nie zwei Bots in eine Telegram-Gruppe, nie zwei Prozesse mit derselben `IT_WEB_CHAT_ID`.
8. **Infomaniak drosselt Parallelität mit 429/5xx** — eigene Werkzeuge seriell.
9. **Prompts werden heiß nachgeladen** (mtime), **TOML-Profile nur beim Start** — Änderung an `workshop/<name>/*.toml` braucht einen Bot-Neustart (den macht nicht der Agent).
10. **Ein Test ist nur wegen Dortmund rot?** Marker `@pytest.mark.dortmund`, keine Anpassung, keine neue Fixture.
11. **Eigene Skripte immer als Modul starten:** `uv run --extra dev python -m scripts.<name>` — ein direkter Dateiaufruf (`python scripts/x.py`) endet in `ModuleNotFoundError: interview_theater` (Repo-Wurzel fehlt in `sys.path`).
12. **Während der Arbeit nur gezielte Tests**, die volle Suite (~10 min) einmal am Ende; nie im Hintergrund starten und dann pollen.

## Index: docs/agents/

| Datei | Lies das, wenn du … |
|---|---|
| `docs/agents/aufbau.md` | … ein Modul anfasst oder suchst: Modultabelle mit Begründungen, Modulkarte, `knoepfe/`-Paket, was bewusst mehrfach existiert, Dortmund-Wortlaut |
| `docs/agents/entscheidungen.md` | … Verhalten änderst, das eine bindende Entscheidung berührt (Knöpfe, Phasen, Interviews, Erkenner, Kürzen, Undo, Länge/Nachpass, Kosten, Prüflauf, Begriffsboard) |
| `docs/agents/dramaturgie-pruefung.md` | … `dramaturgie/`, `stueckpruefung.py` oder den Richter anfasst |
| `docs/agents/fallen.md` | … mit Infomaniak, Whisper, SQLite oder dem Betrieb zu tun hast |
| `docs/agents/spec-abweichungen.md` | … die SPEC zitierst oder einen Slash-Befehl anfasst |
| `docs/agents/starten-und-testen.md` | … startest, testest oder ein Betriebsskript brauchst |
| `docs/agents/weboberflaeche.md` | … `web*.py`, den Web-Kanal, die Absicherung, die Gestaltung oder den Strom anfasst |
| `docs/agents/korpus-und-simulation.md` | … einen Prompt änderst oder Korpus/Simulation laufen lassen willst |
| `docs/agents/was-bewusst-fehlt.md` | … etwas „nachbauen" willst, das fehlt — erst nachsehen, ob es bewusst fehlt, und die offenen Übergaben je Karte |
| `docs/agents/workshop-profil.md` | … `workshop.py`, `anweisungen.py` oder ein Profil unter `workshop/` anfasst |

`docs/agents/umzug-dubletten.txt` hält fest, welche doppelten Abschnitte der
alten Datei beim Umzug zusammengelegt wurden.

**Kapitel der alten AGENTS.md → jetzt** (damit Verweise „AGENTS.md,
Abschnitt X" in einem Schritt auflösbar bleiben):

| Altes Kapitel | Jetzt |
|---|---|
| 🔴 Dortmund eingefroren seit 04.10.2026 | oben (verdichtet), Wortlaut `aufbau.md` |
| Aufbau | `aufbau.md` |
| Modulkarte | oben (verdichtet), Volltext `aufbau.md` |
| Bindende Entwurfsentscheidungen | `entscheidungen.md` |
| Die Dramaturgie-Prüfung | `dramaturgie-pruefung.md` |
| Die Fallen | `fallen.md` |
| Wo SPEC und Code auseinanderlaufen | `spec-abweichungen.md` |
| Starten und testen | `starten-und-testen.md` |
| Weboberfläche | `weboberflaeche.md` |
| ↳ Die Probenansicht | `weboberflaeche.md` |
| ↳ Die Gruppenseite ändert Parameter | `weboberflaeche.md` |
| ↳ Die Absicherung | `weboberflaeche.md` |
| ↳ nginx auf herkules | `weboberflaeche.md` |
| ↳ Der Web-Kanal: derselbe Bot ohne Telegram | `weboberflaeche.md` |
| ↳ Fassungen umschalten | `weboberflaeche.md` |
| ↳ Die Gestaltung | `weboberflaeche.md` |
| ↳ Eine Oberfläche je Gruppe | `weboberflaeche.md` |
| ↳ Die Phasenübersicht | `weboberflaeche.md` |
| ↳ Der Strom | `weboberflaeche.md` |
| Prompt geändert? → Korpus laufen lassen | `korpus-und-simulation.md` |
| Simulation: ein ganzer Workshop gegen die echten Modelle | `korpus-und-simulation.md` |
| Was bewusst fehlt (beide Fassungen, samt Übergaben je Karte) | `was-bewusst-fehlt.md` |
| Workshop-Profil | `workshop-profil.md` |

## Regel für Folgearbeit

Übergaben, Nachweise und Entscheidungsgeschichte einer Karte gehören nach
`docs/agents/<thema>.md` oder `docs/handoffs/` — **nie an AGENTS.md
anhängen**. AGENTS.md trägt nur, was ein Agent in jeder Aufgabe braucht;
`tests/test_agents_md_groesse.py` wird bei mehr als 25.000 Bytes rot. Die
Doku-Tests (`tests/test_doku_laengen.py`, `tests/test_web_betrieb_doku.py`)
lesen AGENTS.md und `docs/agents/` zusammen über
`tests.agents_doku.agents_doku()` — ein Stichwort, das ein Test verlangt,
darf deshalb in der passenden Datei unter `docs/agents/` stehen.

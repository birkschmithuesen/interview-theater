# Aufbau, Modulkarte, Dortmund-Stand

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 1–226).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

# AGENTS.md

Technische Referenz für Agenten und Entwicklerinnen, die an diesem Code
arbeiten. Für die Perspektive der Theatergruppe siehe [README.md](README.md).

Primärquelle für Entwurfsentscheidungen ist `SPEC-kontext-architektur.md` —
dieses Dokument verdichtet daraus, was für die Arbeit am Code am wichtigsten
ist, und ergänzt es um das, was sich erst beim Betrieb gegen die echten
Dienste gezeigt hat. Bei Widerspruch zwischen SPEC und Code gilt der Code;
Abschnitt „Wo SPEC und Code auseinanderlaufen" unten hält die bekannten
Fälle fest.

## 🔴 Dortmund eingefroren seit 04.10.2026 — Abnahme nur noch an Padua

Birk, 04.10.2026: Dortmund wird nicht mehr gepflegt. Kein Dortmund-Bot läuft
mehr, nur die drei Padua-Bots sind live. **„Dortmund byte-gleich/bitgleich"
und `pruefe_profil dortmund-2026` sind keine Abnahmekriterien mehr.**
Abgenommen wird nur noch:
- Suite grün (mit `-m "not dortmund"`, siehe unten)
- `pruefe_profil padua-2026` grün
- Prompt-Snapshot nur für Padua

Der Dortmund-Workshop-Stand ist eingefroren und jederzeit reproduzierbar
unter dem Tag `dortmund-2026-final` (SHA `2e552399749311f3787b375fa4df7d1e30e4097d`,
letzter live-gelaufener Commit am 06.09.2026 08:42, laut `docs/NACHTBERICHT-2026-09-06.md`).

Ein Test, der NUR wegen Dortmund-Verhalten rot wird, bekommt den Marker
`@pytest.mark.dortmund` statt angepasst zu werden (registriert in
`pyproject.toml`). Die Dortmund-/Vorgabe-Fixtures (`tests/fixtures/*dortmund*`,
`*vorgabe*`) werden NICHT mehr neu erzeugt. Neue Funktionen werden nur für
Padua gebaut — wo bisher ein Profilschalter Dortmund/Padua trennt, wird
direkt das Padua-Verhalten umgesetzt, keine neuen Schalter. Bestehende
Schalter bleiben stehen, Abbau erst beim Aufräumen nach dem Workshop
(ab 10.10.2026, Birks Entscheidung). Nicht anfassen: `betrieb/gruppe1-4.env`,
Dortmund-Daten in `betrieb/soap.db`, Dortmund-Code — nichts löschen.

An jeder Stelle unten, wo Dortmund als bindende Invariante verlangt wird,
gilt stattdessen dieser Absatz.

## Aufbau

Ein Python-Prozess je Gruppe (gleicher Code, eigener Bot-Token,
eigene `chat_id`), alle Prozesse teilen sich eine SQLite-Datei (WAL-Modus,
`busy_timeout`). Der Zustand liegt vollständig in der Datenbank — ein
Neustart verliert nichts, siehe § 9 der SPEC.

Module unter `interview_theater/`:

| Modul | Zuständigkeit |
|---|---|
| `bot.py` | Startroutine, Long-Poll-Schleife, Begrüßung, Warmlaufen, Prozessaufsicht |
| `ablauf.py` | Gesprächszug: Sperre je `chat_id` fürs Sammeln, Kontextaufbau anstoßen, Antwort verschicken |
| `aufnahme.py` | Aufnahme-Pipeline: Download, Transkription, Verdichtung, Nachhol-Arbeiter, Interviewfluss (kurz/teil/lang) |
| `begriffsboard.py` | Das Begriffsboard der Phase 1 (04.10.2026, Karte t_4517d4ad): laufend mithören wie der Brainstorm in Phase 4 (`brainstorm.soll_reagieren` **unverändert**, eigene Zähler über `aufnahme.diskussion = 1`, eigene Sperre), ein Schema-Aufruf je qualifizierendem Segment im eigenen Thread (Opus nach Einwilligung, sonst Kimi), Tabelle `begriffsboard` (nur anhängen, letzter Stand gilt). Validiert **im Code**: Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`. **Der Lauf kennt kein `tg`** — keine Chatzeile beim Mithören. Bei „Discussion done" der Top-5-Vorschlag mit EINEM Knopf „Take these" — **ohne eigenen Schlusslauf** (Birk 04.10.2026 14:50: „Zwischenstand und Endstand müssen nicht anders behandelt werden"): der Ende-Schnitt zählt in `soll_laufen` wie ein Pausenschnitt (dieselbe Schwelle `min_zeichen`, 600; nur ohne Mindestabstand), der Vorschlag zeigt das Board, wie es ist — läuft gerade ein Lauf, wird nach ihm neu entschieden (`merke_falls_laeuft`); `schreibe_detail` füllt `arbeitsstand.begriffe_detail` auf jedem Schreibweg von `begriffe` (AST-Test `tests/test_begriffe_detail_wege.py`). `detail_zeilen` ist die eine Prompt-Form für `kontext` (Phase 2, ≥ 4) und `fragen_ki`. Seit 04.10.2026 (Karte t_cb2c4678) die **Schärfung**: Pflichtfeld `vorheriger_begriff` im Schema, im Code gegen das bisherige Board geprüft (`validiere(…, bisher)`, `_verkette` — nur ein Begriff, der wirklich verschwand, keine Ähnlichkeitsheuristik); daraus die Kette `vorgaenger` (älteste zuerst, nur am Eintrag, wenn nicht leer, nie im Schema, nie Modelltext). Im CoThinker durchgestrichen (`web._begriffsboard_html`, `data-vorgaenger`), Live-Ranking per FLIP direkt in `ladeBuehne()` (`_VEREINT_JS`: `bbMerke` vor, `bbSpiele` nach dem Panel-Tausch; ohne `ol.begriffsboard` wirkungslos). Design-Erweiterung (04.10.2026, Birk: „richtig gut designt, nicht bloss funktional"): kein aufklappbares „Warum" mehr in der Anzeige (Begründung/Zitat/Doppelbedeutung bleiben in der Datenbank, nur das Rendering in `web._begriffsboard_html` zeigt sie nicht mehr) — Rang 1–5 (`data-top="1"`) bekommt eine Scheinwerfer-Marke, der Rest eine Trennlinie direkt danach (`css_buehne()`, CSS-Selektor `li[data-top="1"] + li:not([data-top="1"])`, keine feste Positionszahl), `status="verworfen"` bleibt sichtbar, aber kursiv — durchgestrichen bleibt allein der Schärfungskette vorbehalten. Die Kette selbst bekommt ein eigenes Fach (`border-left`-Steg), der jüngste Vorgänger im Steg, jeder ältere eine Stufe kleiner (Größe trägt das Alter, nicht Opazität — die würde `--text-leise` unter 4,5:1 drücken). `bbMerke`/`bbSpiele` verfolgen seitdem keinen Auf-/Zu-Zustand mehr. Dabei ist ein Bestandsfehler in `web_vereint.scope_css` aufgefallen und behoben worden: die Funktion trennt den Text vor jeder Regel an jedem Komma, bevor sie das Scope-Praefix voranstellt, ohne Kommentare vorher zu entfernen — ein mehrkommahaltiger `/* ... */`-Kommentar direkt vor einer Regel reisst das Praefix von deren echtem Selektor ab, und genau das traf seit der ersten Fassung unbemerkt die `.vorgaenger`-Regel der Schärfungskette (ihr Test sah nur zufaellig richtig aus, weil eine kommentarfreie Nachbarregel dieselbe Teilzeichenkette traf). Behoben, indem alle erklaerenden Saetze aus CSS-Kommentaren in den `#:`-Doc-Kommentar oberhalb von `_BUEHNE = """` gewandert sind (den `scope_css` nie liest) — der CSS-Text selbst ist seitdem durchgehend kommentarfrei. Deshalb die Regel fuer diesen Block: **kein CSS-Kommentar direkt vor einer Regel**, sonst reisst `scope_css` erneut ihr Praefix ab. |
| `befehle.py` | Die Slash-Befehle (`_BEKANNTE_BEFEHLE`, zurzeit fünfzehn; acht davon stehen über `setMyCommands` im Menü, `BEFEHLE_LISTE`), laufen vor jedem Kontextaufbau und vor jedem Gespraechsaufruf |
| `erkenner.py` | Absichtserkenner: erkennt Änderungsabsichten im Gesprächsverlauf, wendet sie an, baut die Sammelmeldung |
| `journal.py` | Journal-Extraktor: erkennt `vorgeschlagen`-Einträge im aus dem Fenster verdrängten Gesprächsabschnitt |
| `kontext.py` | Baut den Gesprächs-Prompt datengetrieben zusammen, inklusive zweistufiger Kürzung |
| `phasen.py` | Die sieben Arbeitsphasen (`PHASEN`, seit dem Profil-Umbau aus `workshop.VORGABE_PHASEN`): Liste, tolerantes Mapping, `moegliche_naechste()` aus der Materiallage (reine Leseabfrage, kein Modellaufruf) |
| `sprecher.py` | Sprecherzeilen-Parsing und Sprechanteile je Figur (06.09.2026): reine Zählung über `szene.volltext`, kein Modellaufruf. Bekannte Grenze im Docstring benannt (`FRAU K.:`, `MIRA, LEISE:`) |
| `fehlstellen.py` | Das Fehlstellen-Register (06.09.2026): was der Gruppe noch fehlt, als Sätze. Reine Leseabfrage wie `phasen.voraussetzungen`, kein Modellaufruf; `aus_daten` ist rein, `register` liest über `repo`, `web_daten.fehlstellen` read-only |
| `llm.py` | Sprachmodell-Client (chat/completions), robustes JSON-Auslesen, Retry bei 5xx/Timeout |
| `strom.py` | Der laufende Text (30.09.2026): dekodiert aus einem wachsenden JSON-Praefix den bisherigen Wert von `antwort` (der Gespraechszug ist ein **Schema**-Aufruf), saeubert ihn (`vorschlag.ohne_marker`, auch die halb getippte Markerzeile) und drosselt das Schreiben auf `INTERVALL_S` = 0,15 s. Reine Funktionen plus `Senke` mit drei Rueckrufen — **keine Datenbank**, kein `repo` |
| `stt.py` | Whisper-Anbindung, zweistufig und asynchron |
| `szene.py` | Szenentexte: eigener Prompt (Struktur statt Transkript, ein Regelblock je Form), eigener Thread, als einziger Aufruf mit Reasoning AN, Sperre vor dem Aufruf gegen fehlende Pflichtfelder |
| `sprachprofil.py` | Sprachprofil je Figur: ein gemma-Aufruf (Reasoning aus, eigener Thread) aus dem zugeordneten Interview, Zitate geprüft wie beim Verdichter |
| `telegram.py` | Dünner HTTP-Wrapper um die Telegram-Bot-API, inkl. Inline-Tastatur und `answerCallbackQuery` |
| `knoepfe/` | Inline-Knöpfe an den Auswahl-Momenten: Angebot, Idempotenz-Sperre, Wirkung. Seit 06.09.2026 ein Paket aus acht Modulen (siehe „Modulkarte") statt einer Datei; `knoepfe/__init__.py` re-exportiert die vollständige bisherige Modulfläche |
| `phasentexte.py` | Der Phasenrahmen im Chat (06.09.2026): die sieben Einleitungen als Daten, `PARAMETER` je Phase, daraus Eintrittsnachricht („▶️ Phase N von 7 · Name" + Checkliste ✅/⬜), Abschlussnachricht („✅ … abgeschlossen" + alle gesetzten Parameter) und die Zeilen für `/stand`. Bot-Text an die Gruppe, kein Prompt — kein Modellaufruf, nur repo-Lesezugriffe |
| `szenenfolge.py` | Die Szenenfolge und die Geschichte als Vorschlag: ein Modellaufruf im eigenen Thread, feste Zeilenform, daraus Zeilen in der Tabelle `szene`. Dazu die Merkposten für Regie-Notiz und Prüf-Vermerk und das Textbuch als Datei |
| `schaerfung.py` | Phase 5: legt die geprüften `verdichtung_thema`-Einträge per Schema-Aufruf (gemma, Thread) auf Szenen und Figuren, prüft die Zitate mit `zitat.pruefe` und schreibt in die Tabelle `schaerfung` (additiv, mit `runde`) |
| `stueckpruefung.py` | Phase 7: der Stück-Judge über das ganze Textbuch — je Befund eine Frage mit Szenenbezug, Tabelle `stueckpruefung`, eigener Thread |
| `kernzitate.py` | Die Auswahl der Belegzitate zum Kernthema (`waehle`), rückwärtskompatible Basis der Schärfung — dieselbe Prüf- und Speicherlogik |
| `kosten.py` | Was ein Workshoptag kostet: Preistabelle (aus `scripts/pruefe_prompts.py` hierher gezogen), Kostenrechnung je Aufruf, der Tagesdeckel je Gruppe mit Reset um Mitternacht Europe/Rome, `KostendeckelErreicht` und die Pausenmeldung. **Kein SQL** — liest über `repo.kostensumme_seit` |
| `kuerzung.py` | Kürzen als eigener Weg (30.09.2026, C4/C10): die feste Regie-Notiz (25 %), die Zielwahl (Szenennummer → `szene.starte`, keine → `kurzgeschichte.starte`) und `nummer_aus_wert`. **Kein eigener Modellaufruf** — beide Wege geben an ihren vorhandenen Thread ab, und beide hängen ihre Fassung an (`szenenfassung`). Eine Kürzung erzeugt **nie** eine neue Szenenfolge |
| `roadmap.py` | Die Phasenuebersicht als Daten (30.09.2026): die sieben Phasen mit ihren Aufgaben, je `erledigt`/`offen`/`laeuft` und einem Sprungziel. Reine Leseabfrage wie `fehlstellen`; `aus_daten` ist rein, `register` liest ueber `repo`, `web_daten.roadmap` read-only. Die **Namen** der Aufgaben sind per Test an `phasentexte.PARAMETER` genagelt — keine zweite Wunschliste. Seit 03.10.2026 auch `werkbank(lage, aktuelle_phase)`: je Phase ihre Attribute mit `erledigt`/`offen`/`spaeter` (die Quelle der read-only Werkbank in Padua und des Steppers), plus `begriffe_detail` als defensiver Haken |
| `ruecknahme.py` | Die Ruecknahme eines Erkennerlaufs (01.10.2026, Karte U): welche Tabellen und Spalten verfolgt werden (`VERFOLGT`, `MATERIAL`, `AUSSEN`) und wie aus zwei Schnappschuessen um `wende_an` die Ruecknahme-Schritte werden (`schritte`). **Reine Funktionen, kein SQL, kein Nutzertext** -- alles SQL steht in `repo.py`, die Wortlaute in `knoepfe/texte.py`. `db` wird nur fuer die Spaltenliste gelesen (`_tabellenspalten_aus_schema`), damit eine neue Spalte automatisch mitverfolgt wird |
| `laengen.py` | Laengen-Rhythmus je Szene (30.09.2026, Karte R): der eine Wortzaehler (`zaehle_woerter`), der Rahmen je Form aus dem Profil, die Rhythmus-Muster, das Budget je Szene, der Faktor und die Prompt-Bausteine. **Kein Modellaufruf, keine Datenbank** (ausser `setze_faktor`, das ueber `repo` geht). Ohne `[laengen] aktiv = true` im Profil liest es niemand |
| `sprachpass.py` | Der letzte Sprachpass (30.09.2026, Karte R): vier Regex-Zaehler (Gedankenstriche, "not X but Y", Adjektiv-Dreierketten, Fazitsatz), Grenzwerte aus dem Profil, die Regie-Notiz und der **Zitatschutz** ueber `zitat.pruefe`. **Kein Modellaufruf**; `gepruefte_zitate` ist die einzige Funktion mit Datenbankzugriff |
| `nachpass.py` | Der EINE Ueberarbeitungslauf am Ende eines Schreibvorgangs (30.09.2026, Karte R): `nach_szene` (Phase 7) und `nach_geschichte` (Phase 6). Laeuft **im Thread und unter der Sperre** des Schreibwegs, deshalb `szene.schreibe`/`kurzgeschichte.hole_text` und nie `starte`. Eigene `art`-Werte (`szene_nachpass`, `kurzgeschichte_nachpass`) |
| `prueflauf.py` | Der Prüflauf vor jeder Anzeige (03.10.2026, Padua Phasen TEIL 2): eine Fragen-Teilmenge je Objekt (`FRAGEN_GESCHICHTE`, `FRAGEN_PROSASZENE`, `FRAGEN_BUEHNENSZENE`) über `schleife.schliesse`, Zitatwache, Nachpass, A10-Parameterkorrektur und **eine** Zeile in der Tabelle `prueflauf`. `pruefe_szene`/`pruefe_geschichte` sind synchron, **der Aufrufer hält die Sperre**, sie zeigen nie etwas und liefern immer einen `Bericht`; `starte_szene`/`starte_geschichte` sind die Thread-Wege, `danach(bericht)` läuft nach der Freigabe. Kein SQL. Ohne `[prueflauf] aktiv` ruft es niemand |
| `ueberarbeitung.py` | Phase 6 (Rewrite) und 7 (Stage Version) in Padua als Zustandsmaschine (03.10.2026): `weiter_6`/`weiter_7` (der eine Schrittweg je Phase, `aus_eintritt` ohne automatischen Sprung), `aktuelle_szene`, `laeuft`, die vier `bestaetige_*`, `ueberarbeite` und `nimm_ab` (Chat wirkt wie der Knopf), `sende_formwahl`/`_wende_formen_an`, `schluss_gelaufen`/`starte_schluss`. Kein SQL, kein Modellaufruf — die Läufe gehen an die Threads von `prueflauf`/`szene`/`kurzgeschichte`/`sprechweise`. Ohne `[ueberarbeitung] aktiv` ruft es niemand |
| `sprechweise.py` | Die Sprechweise je Figur vor der Bühnenfassung (03.10.2026, Phase 7 Schritt 2): **ein** Schema-Aufruf (eigener Thread, eigenes Sperren-Register) nur für Figuren **ohne** `figur.sprachstil` — ein von der Gruppe gewählter Stil wird nie von einem Modell überschrieben. `wende_an` ist der Chat-Weg (`sprechweise_setzen`) und überschreibt, weil dort die Gruppe spricht. Die Anweisung ist eine Modul-Konstante, keine neue deutsche Prompt-Datei |
| `leitfaden.py` | Baut aus Eröffnung, den gewählten Fragen mit ihren weichen Fassungen und dem Abschluss **deterministisch** den Gesprächsleitfaden (`baue`, `aus_feldern`) — kein Modellaufruf, dieselbe Funktion für Chat und Gruppenseite |
| `vorschlag.py` | Die Markerzeilen im Antworttext (`VORSCHLAG BEGRIFFE:` und Verwandte): lesen, in Blöcke zerlegen, aus dem Chattext entfernen. Die Schnittstelle zwischen Prompt und Knopfleiste |
| `vorschlagssperre.py` | Die EINE Sperre je `chat_id`, die Schärfung und die vier `szenenfolge.starte*` voneinander trennt (30.09.2026, C7), plus einen Merkplatz je Auftragsart: wer sie nicht bekommt, wird **gemerkt** und läuft nach der Freigabe automatisch. Reines `threading`, **kein** Projektimport — deshalb von beiden Seiten importierbar. Grenze: der Merkplatz lebt im Prozess, ein Neustart verliert ihn |
| `szene_claude.py` | Der zweite Anbieterpfad für den Szenenlauf: Anthropic-Messages-Format über den lokalen Proxy, nur nach Einwilligung der Gruppe (`ist_aktiv`) |
| `web_schreiben.py` | Die Schreibpfade der Gruppenseite — ruft **ausschließlich** `repo`-Funktionen, kein eigenes SQL. `FELDER` ist die vollständige Liste des Änderbaren, `FUEHRT_DER_CHAT` und `NUR_ANZEIGE` das Gegenteil |
| `verdichter.py` | Verdichtet ein Transkript zu Zusammenfassung und Kernthemen mit Belegzitaten — an der Frageliste der Gruppe entlang, wenn es eine gibt (N3) |
| `zitat.py` | Belegzitat-Verifikation: Teilstring-Vergleich nach Normalisierung |
| `dramaturgie/` | Die feinkörnige Prüfung neben `stueckpruefung.py` (06.09.2026): `mechanik.py` zählt ohne Modell (Namensdrift, Geisterfiguren, Besetzung, Tschechow-Kandidaten, Formverteilung, Sprechanteile), `beleg.py` verifiziert Judge-Zitate über `zitat.pruefe` (ein Retry, dann `unsicher`), `fanout.py` stellt sieben Fragen (B1, A2, A6, A9, A10, A11, C1) an ein **anderes** Modell als das schreibende, `bilanz.py` und `schleife.py` schließen die Rückkopplung (07.09.2026). Siehe „Die Dramaturgie-Prüfung" |
| `prompts/dramaturgie/` | Ein Prompt je Judge-Frage, mit `prompt_version` im Dateikopf |
| `repo.py` | Einzige SQL-Zugriffsschicht außer `db.py`, komplett `RLock`-serialisiert |
| `db.py` | Schema, Verbindungsaufbau samt PRAGMAs, Migration fehlender Spalten, Löschweg (`loesche_gruppe`) |
| `einstellungen.py` | Konfiguration ausschließlich über Umgebungsvariablen |
| `anweisungen.py` | Prompt-Texte mit Hot-Reload (mtime) + optionaler Regie-Zettel `betrieb/zusatz*.md`; **der Einhängepunkt des Workshop-Profils** (Platzhalter, Dateiersatz, Cache-Schlüssel mit Profil) |
| `workshop.py` | Das Workshop-Profil: liest `IT_WORKSHOP`, lädt `workshop/<name>/*.toml`, liefert ein eingefrorenes Objekt. Ohne Variable gilt das eingebaute Vorgabeprofil mit den heutigen Dortmunder Werten. Siehe „Workshop-Profil" |
| `sprache.py` | Die Sprache eines Workshops (Karte A1, 30.09.2026): `code()` (`de`/`en`), `whisper_vorgabe()`, `pseudonyme()` (E8), `je_sprache()` für Parser, und der Nachschlagezugriff `Texte`/`T` — `T._TEXT_X` liest zur Aufrufzeit aus der Tabelle der aktiven Sprache. Deutsch bleibt die Python-Konstante selbst (bitgleich), jede weitere Sprache steht in `sprachen/<code>/texte.toml`. Siehe „Workshop-Profil", Absatz „Sprache" |
| `sprachen/` | Die Sprachschicht zwischen Repo und Profil (Karte A1): `en/texte.toml` (eine Tabelle je definierendem Modul, Konstantenname als Schlüssel) und `en/prompts/**` (englische Fassung je Prompt-Datei, gleicher Pfad wie im Repo). Wird von `sprache.py` bzw. `anweisungen.py` gelesen, nie direkt importiert |
| `prompts/` | Die Prompt-Texte als eigene `.md`-Dateien (`system`, `erkenner`, `journal`, `verdichter`, `szene`, `sprachprofil` + `theater-tells`) |
| `prompts/formen/` | Ein Regelblock je Szenenform — genau fünf: `dialog`, `monolog`, `chor`, `lied`, `rap` (05.09.2026 abends). `szene.formdatei(form)` ordnet das freie Feld `szene.form` zu, Dialog ist der Rückfall. `dialog.md` trägt den am Herkules.exe-Textbuch gemessenen Regelblock (Sprechszene, Ausgangsmaterial, keine Choreografie); `lied.md`/`rap.md` das Songwriting- bzw. Rap-Handwerk. Eine Figurenanzahl gibt kein Regelblock vor — die kommt aus der Planung (Feld `figuren`) |
| `prompts/phasen/` | Je Arbeitsphase eine Datei `1.md` … `8.md`: worauf der Bot dort den Fokus legt, was er *nicht* tut, woran die Phase fertig ist. Wird zwischen Basis-Systemanweisung und Regie-Zettel gehängt |
| `vorspann.py` | Der Vorspann vor dem Text (07.09.2026): Wo und wann · Worum es geht · Form · die Szenen · Wer vorkommt. Deterministisch aus `arbeitsstand.*`, `szene.titel`/`form` und `figur.name`/`beschreibung` — **kein Modellaufruf**. `daten()` nimmt Dicts und kennt keine Datenbank (deshalb darf `web_daten` es importieren), `aus_datenbank()` ist die `repo`-Abkürzung, `als_markdown()`/`als_chattext()` die zwei Darstellungen |
| `web.py` | Weboberfläche: Routing, HTML und CSS für Dashboard und Gruppenseiten, `http.server`, nur Standardbibliothek |
| `web_daten.py` | Die Lesezugriffe dazu — read-only geöffnete Verbindung, reine Funktionen, `conn` rein, Dicts raus |
| `web_grenze.py` | Das Rate-Limit der Weboberfläche: gleitendes Fenster im Prozessspeicher, Schlüssel `chat_id`, thread-sicher. **Kein Projektimport** (wie `vorschlagssperre.py`) |
| `web_kanal.py` | Der Web-Kanal (30.09.2026): `WebKanal` ersetzt `telegram.Telegram`, wenn `IT_KANAL=web`. Liest Browser-Ereignisse aus der Tabelle `web_post` als Telegram-förmige Updates und schreibt die Antworten dorthin zurück — `bot.schleife` bleibt unverändert, `knoepfe/` wird nicht angefasst. Kein SQL (alles über `repo`), kein Modell |
| `web_chat.py` | Die Chatansicht im Browser (30.09.2026): HTML, CSS, Vanilla-JS und alle Handler unter `/g/<token>/chat`. `web.py` bekommt nur die Routing-Zeilen. Trägt den serverseitigen HTML-Filter (`sichere_html`), die Knopfprüfung gegen die hängende Leiste (`knopf_erlaubt`), den Audio-Upload, die zwei Aufnahme-Wege und die sequentielle Warteschlange im JS. Kein SQL, kein Modell |
| `web_vereint.py` | Die vereinte Gruppenseite (30.09.2026): drei Panels (Chat · Arbeitsstand · Textbuch) in **einem** Dokument, Hash-Tabs, die Phasenleiste mit Klick, der SSE-Kanal `/g/<token>/chat/strom` und `scope_css`. `web.py` bekommt davon nur Routing-Zeilen |
| `web_gestalt.py` | Die Gestaltung der Weboberflaeche (01.10.2026, Padua): ein Block Design-Tokens je Entwurf (A „Terminal zuerst", B „Buehne zuerst"), das Komponenten-CSS, das Effekt-JavaScript und die englischen Mikrotexte. Eingehaengt an **neun** Zeilen (sechs in `web_vereint.seite`, je eine in `web.textbuch_html`/`leitfaden_html`/`dashboard_html`; das Dashboard nur mit `[web] dashboard_gestaltet`) — **kein SQL, kein Modellaufruf, kein Endpunkt, kein neues Markup** (zwei Ausnahmen in `web.py`: die Umstellung in `web.gruppe_koerper` und das gestaltete Dashboard-Markup `_fortschritt_html`/`_achtung_html`/`_dashboard_inhalt_html`, nur mit `[web] dashboard_gestaltet`). Dazu seit der read-only Werkbank eine zehnte in `web_vereint.seite` (`css_werkbank()`, nur mit `[web] workbench_bearbeitbar = false`). Umschalten: `IT_UX_ENTWURF` |

`scripts/loeschen.py` erfüllt die Löschzusage (löscht eine Gruppe vollständig,
Datenbank und Audioverzeichnis), `scripts/rauchtest.py` prüft echte
Betriebsannahmen gegen die echten Dienste, `scripts/pruefe_prompts.py` lässt
den Regressionskorpus unter `korpus/` gegen das echte Modell laufen (siehe
„Prompt geändert? → Korpus laufen lassen"), `scripts/simulation.py` fährt einen
kompletten simulierten Workshop durch alle Phasen und bewertet ihn (siehe
„Simulation", Bausteine unter `simulation/`), `scripts/backup-robocloud.sh`
sichert Betriebsdaten außerhalb des Repositories, `scripts/web_links.py` gibt
je Gruppe die URL ihrer Gruppenseite aus,
`scripts/dramaturgie_pruefen.py` fährt die Dramaturgie-Prüfung gegen eine
Kopie-Datenbank (siehe „Die Dramaturgie-Prüfung").
je Gruppe die URL ihrer Gruppenseite aus, `scripts/figuren_aufraeumen.py`
führt in Bestandsdaten Platzhalterfiguren mit ihren Nachbenennungen zusammen
(`--trocken`, läuft **nie** automatisch — es verändert Arbeitsergebnisse
einer Gruppe). `scripts/web_gruppe.py anlegen <bot_name>` legt eine Gruppe
für den Web-Kanal an und gibt Link, chat_id und die zwei Env-Zeilen aus
(siehe „Der Web-Kanal"). `scripts/test_uebernehmen.py <quell_chat_id> [--ja]`
spielt den Stand einer Padua-Gruppe auf die getrennte Testinstanz
(`betrieb/padua-test.db`, Web 8031 `/padua-test`, Bot `padua-test`, feste
chat_id `7000000000099`, fester Link), `--leer` setzt sie auf Phase 1 zurück
— Quelle nur `mode=ro`, Testbot vorher stoppen, Anleitung
`docs/testgruppe-padua.md`.

`web_daten.py` ist die einzige Ausnahme von „SQL nur in `repo.py` und
`db.py`". Grund: die Weboberfläche liest mit einer eigenen, read-only
geöffneten Verbindung (`file:…?mode=ro`). Sie durch `repo.py` zu führen hieße,
den modulweiten Schreib-Lock des Bots für Anfragen zu nehmen, die den Bot
nichts angehen — ein projiziertes Dashboard, das sich alle zehn Sekunden neu
lädt, würde damit Gesprächszüge ausbremsen.

## Modulkarte

Stand 06.09.2026 nach dem konsolidierenden Refactoring. Die Tabelle oben sagt,
**was** ein Modul tut; dieser Abschnitt sagt, **wo man anfängt zu lesen** und
in welche Richtung die Abhängigkeiten zeigen.

**Vier Schichten, von unten nach oben.** Jede liest nur nach unten; die
wenigen Aufrufe nach oben stehen als lokaler Import in der Funktion, die sie
braucht (das ist im ganzen Repo die Bauart, mit der Zyklen aufgelöst werden —
`from interview_theater import befehle` mitten in einer Funktion ist kein
Versehen).

| Schicht | Module |
|---|---|
| **Ablage** | `db.py` (Schema, Migration, Löschweg) · `repo.py` (alles SQL des Bots, `RLock`-serialisiert) · `web_daten.py` (die read-only Leseseite) |
| **Dienste** | `llm.py` · `strom.py` · `stt.py` · `telegram.py` · `einstellungen.py` · `workshop.py` · `sprache.py` · `anweisungen.py` · `zitat.py` · `vorschlag.py` · `stile.py` · `vorschlagssperre.py` · `web_kanal.py` · `kosten.py` · `web_grenze.py` |
| **Fachlogik** | `phasen.py` · `kontext.py` · `erkenner.py` · `journal.py` · `verdichter.py` · `begriffe.py` · `aufnahme.py` · `begriffsboard.py` · `begriffsboard_analyse.py` · `szene.py` · `szene_claude.py` · `szenenfolge.py` · `kurzgeschichte.py` · `kuerzung.py` · `roadmap.py` · `ruecknahme.py` · `schaerfung.py` · `stueckpruefung.py` · `kernzitate.py` · `sprachprofil.py` · `sprachstil.py` · `sprecher.py` · `fehlstellen.py` · `arbeitszeilen.py` · `leitfaden.py` · `laengen.py` · `sprachpass.py` · `nachpass.py` · `prueflauf.py` · `ueberarbeitung.py` · `sprechweise.py` |
| **Oberfläche** | `bot.py` · `ablauf.py` · `befehle.py` · `knoepfe/` · `phasentexte.py` · `web.py` · `web_schreiben.py` · `web_chat.py` · `web_vereint.py` · `web_gestalt.py` |

**Wo man anfängt, je nach Frage:**

| Frage | Einstieg |
|---|---|
| Warum antwortet der Bot (nicht)? | `ablauf.antworte` → `_zug_faellt_aus` |
| Was steht im Prompt? | `kontext.baue` → `_bloecke` → `_kuerze_auf_budget` |
| Was passiert bei einem Knopfdruck? | `knoepfe.behandle` → `knoepfe/wirkung.py`, Tabelle `_WIRKUNGEN` |
| Was schreibt der Erkenner? | `erkenner.laufe` → `wende_an` → `baue_meldung` |
| Wie entsteht ein Szenentext? | `szene.starte` → `baue_nutzertext` → `schreibe` |
| Wann darf die Gruppe weiter? | `phasen.voraussetzungen` (die einzige Stelle) |
| Warum wartet ein Vorschlag? | `vorschlagssperre.nimm_oder_merke` → `merke` → `gib_frei` |
| Wie nehme ich einen Erkennerlauf zurueck? | `knoepfe.wirkung._wirkung_undo` → `repo.nimm_erkenner_lauf_zurueck`; was erfasst wird: `ruecknahme.VERFOLGT` |
| Warum ist die Szene so lang? | `laengen.budget_fuer` -> `muster_fuer` -> `stufe_fuer` |
| Warum lief die Szene zweimal? | `nachpass.nach_szene` -> `befund` -> `_notiz` |
| Warum sieht der Browser nichts? | `web_kanal.hole_updates` → `repo.web_eingang` → `bot.schleife` |
| Was passiert bei einem Klick im Web-Chat? | `web_chat.beantworte_post` → `_POSTWEGE` → Eingang (`web_post`) → `knoepfe.behandle` |
| Warum antwortet der Bot heute gar nicht mehr? | `kosten.deckel_erreicht` → `repo.kostensumme_seit`, Vorfall `kostendeckel_erreicht` |
| Warum kommt eine Weboberflächen-Anfrage nicht durch? | `web.eigene_herkunft` (403) → `web_grenze.pruefe` (429) → `web_chat._audio` (413/415) |
| Warum baut sich der Text im Browser auf? | `strom.Senke` → `web_kanal.WebKanal.strom` → `web_vereint.sende_strom` |
| Was passiert beim Klick auf eine Phase? | `web_vereint.phase_post` → `web_post` → `befehle.wechsle_phase` |
| Warum sieht die Weboberflaeche so aus? | `web_gestalt.TOKENS` → `css_rahmen` → `docs/ux-padua/BERICHT.md` |
| Warum hat sich der Text vor der Anzeige geändert? | `prueflauf.pruefe_szene` → `schleife.schliesse` → Tabelle `prueflauf` |
| Wo steht Phase 6/7 gerade? | `ueberarbeitung.weiter_6`/`weiter_7` → `aktuelle_szene` |
| Was zeigt die Werkbank in Padua? | `roadmap.werkbank` → `web_daten.werkbank` → `web.werkbank_koerper` |
| Was steht auf dem Begriffsboard (und warum nicht)? | `aufnahme._diskussion_abschliessen` → `begriffsboard.nach_segment` → `soll_laufen` → `_lauf_einmal` → `validiere` |
| Warum ist ein Begriff durchgestrichen (oder nicht)? | `begriffsboard.validiere` → `_verkette` → `web._begriffsboard_html` → `web_vereint._VEREINT_JS` (`ladeBuehne` → bbMerke/bbSpiele) |

**Das Paket `knoepfe/`** (06.09.2026 aus einer Datei von 5.516 Zeilen
entstanden, die entlang dieser Schichten von selbst zerfiel):

| Modul | Inhalt |
|---|---|
| `texte.py` | ART-Kennungen, Knopfbeschriftungen, Systemzeilen, Phasennummern, Auftragsvorlagen — alles, was ein Wert ist und keine Wirkung |
| `basis.py` | `callback_data` (Zusage 1), Grundleiste, Speicherweg, `_starte_auftrag` (Zusage 2) |
| `fragen.py` · `figuren.py` · `szenen.py` · `interviews.py` | die Angebote je Phase (2 · 4 · 5–7 · 3) — `szenen.py` trägt Schärfung, Geschichte, Szenentexte, Stückprüfung und Durchlauf zusammen |
| `stationen.py` | der Phasenrahmen im Chat: Eintritt, Abschluss, proaktives Angebot |
| `wirkung.py` | `Druck`, ein Handler je Knopfart, die Tabelle `_WIRKUNGEN`, `_wirke`, `behandle` |
| `__init__.py` | re-exportiert die vollständige bisherige Modulfläche — kein Aufrufer außerhalb musste angepasst werden |

`tests/test_knoepfe_struktur.py` liest dieses Paket per AST und hält die drei
Zusagen **am Quelltext** fest: jede `ART_*`-Konstante hat einen Handler,
`PRAEFIX` steht nur in `_daten`/`_id_aus_daten`, kein Handler fasst `klm` an,
und `_wirke` wird nur aus `behandle` gerufen — hinter der
`beanspruche_knopf`-Wache. Wer eine Knopfart hinzufügt, merkt es dort, bevor
es jemand im Chat merkt.

**Was bewusst mehrfach existiert** — damit niemand es „aufräumt":

- `repo.py` **und** `web_daten.py` haben ähnliche SELECTs. Das ist die
  Entscheidung von oben (zwei Verbindungen, eine davon read-only), keine
  Wiederholung.
- `kontext.schaetze` (Zeichen ÷ 3) **und** `szene.schaetze_token` (÷ 1,9).
  Der zweite Wert ist an einem echten Szenen-Prompt gemessen; deutscher
  Prosatext tokenisiert schlechter als die Faustregel.
- Ein Sperren-Register je Nebenläufigkeit (`ablauf`, `szene`,
  `kurzgeschichte`, `sprachstil`). Gleicher Code, verschiedene Sperren — eine
  gemeinsame Sperre würde den Gesprächszug am Szenenlauf hängen lassen. **Die
  eine Ausnahme** (30.09.2026, C7): `szenenfolge` und `schaerfung` teilen
  seither eine Sperre, und sie liegt deshalb in einem eigenen Modul
  (`vorschlagssperre.py`) statt in einem der beiden. Der Grund ist gemessen:
  am 06.09. lagen Schärfungsvorschlag und Szenenfolge-Vorschlag im selben
  Chatfenster, und die Gruppe wusste nicht, auf welche Frage sie antwortet.
  Ausgeweitet werden darf sie nicht — `szenenfolge._sperre_fuer` bleibt als
  Name bestehen und delegiert dorthin, damit Tests weiter über
  `acquire(timeout=…)` auf das Ende eines Laufs warten können.

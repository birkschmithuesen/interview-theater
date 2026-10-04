# AGENTS.md

Technische Referenz für Agenten und Entwicklerinnen, die an diesem Code
arbeiten. Für die Perspektive der Theatergruppe siehe [README.md](README.md).

Primärquelle für Entwurfsentscheidungen ist `SPEC-kontext-architektur.md` —
dieses Dokument verdichtet daraus, was für die Arbeit am Code am wichtigsten
ist, und ergänzt es um das, was sich erst beim Betrieb gegen die echten
Dienste gezeigt hat. Bei Widerspruch zwischen SPEC und Code gilt der Code;
Abschnitt „Wo SPEC und Code auseinanderlaufen" unten hält die bekannten
Fälle fest.

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
| `begriffsboard.py` | Das Begriffsboard der Phase 1 (04.10.2026, Karte t_4517d4ad): laufend mithören wie der Brainstorm in Phase 4 (`brainstorm.soll_reagieren` **unverändert**, eigene Zähler über `aufnahme.diskussion = 1`, eigene Sperre), ein Schema-Aufruf je qualifizierendem Segment im eigenen Thread (Opus nach Einwilligung, sonst Kimi), Tabelle `begriffsboard` (nur anhängen, letzter Stand gilt). Validiert **im Code**: Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`. **Der Lauf kennt kein `tg`** — keine Chatzeile beim Mithören. Bei „Discussion done" der Top-5-Vorschlag mit EINEM Knopf „Take these"; `schreibe_detail` füllt `arbeitsstand.begriffe_detail` auf jedem Schreibweg von `begriffe` (AST-Test `tests/test_begriffe_detail_wege.py`). `detail_zeilen` ist die eine Prompt-Form für `kontext` (Phase 2, ≥ 4) und `fragen_ki` |
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
(siehe „Der Web-Kanal").

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
| **Fachlogik** | `phasen.py` · `kontext.py` · `erkenner.py` · `journal.py` · `verdichter.py` · `begriffe.py` · `aufnahme.py` · `begriffsboard.py` · `szene.py` · `szene_claude.py` · `szenenfolge.py` · `kurzgeschichte.py` · `kuerzung.py` · `roadmap.py` · `ruecknahme.py` · `schaerfung.py` · `stueckpruefung.py` · `kernzitate.py` · `sprachprofil.py` · `sprachstil.py` · `sprecher.py` · `fehlstellen.py` · `arbeitszeilen.py` · `leitfaden.py` · `laengen.py` · `sprachpass.py` · `nachpass.py` · `prueflauf.py` · `ueberarbeitung.py` · `sprechweise.py` |
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

## Bindende Entwurfsentscheidungen

- **Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte
  Entscheidungen.** Jede Nachricht wird roh gespeichert, unabhängig davon, ob
  sie einen Zug auslöst oder je in den Prompt wandert — etwas nicht
  aufzunehmen ist unumkehrbar, es nicht in den Prompt zu legen kostet nur
  Kilobyte (SPEC § 1).
- **Der Prompt ist datengetrieben.** `kontext.baue()` lässt jeden Block weg,
  solange die zugrundeliegenden Daten leer sind. Biegt die Gruppe ab, ändert
  sich die Materiallage und der Prompt folgt automatisch (SPEC § 6.1).
- **Inline-Knöpfe an den Auswahl-Momenten** (05.09.2026, `knoepfe/`).
  Gemessen an diesem Tag: der Erkenner trifft eine Kernthema-Festlegung
  zuverlässig, wenn er das ganze Gespräch sieht (3/3) — live sieht er aber nur
  ein Fenster von 1–3 Nachrichten, und im Fenster mit der Zustimmung schrieb er
  `entschieden` (Journalnotiz) statt `kernthema_setzen` (Arbeitsstand). Die
  Festlegung landete nicht in der DB und nicht auf der Weboberfläche. Ein Knopf
  trägt die Auswahl selbst — nichts zu raten. Knöpfe gibt es deshalb **nur**
  dort, wo aus wenigen benannten Möglichkeiten gewählt wird: Kernthema-Vorschlag,
  Aufnahme-Umschalter, „Weiter zu Phase N", **Form je Szene** (Phase 6:
  Dialog · Monolog · Chor · Lied · Rap) und die **USA-Einwilligung**. Freitext (Begriffe,
  Fragen, Figurenbeschreibungen) bleibt bewusst Sprache — dort gibt es keine
  Liste. Die letzten drei kamen am selben Tag dazu, nachdem die nummerierten
  Auswahllisten in `phasen/5.md` und `6.md` dieselbe Schwäche zeigten („das
  erste" ist für den Erkenner nicht auflösbar) und die USA-Frage in der
  Simulation eine Sackgasse erzeugte: die Gruppe bejahte siebenmal, der
  Erkenner las es als Zustimmung zu den Figuren.
  Drei bindende Zusagen: (1) `callback_data` bleibt unter **64 Bytes** — ein
  Knopf trägt nur `k:<id>`, der Wert steht in der Tabelle `knopf`, nie der
  Volltext im Knopf (auch die Szenennummer nicht: sie steht als `"<nr>:<form>"`
  im `wert` der Knopfzeile); (2) **kein Modellaufruf** in einem Knopf-Handler,
  wie bei
  den Slash-Befehlen — was ein Modell braucht, geht an einen eigenen Thread;
  (3) **idempotent** über `repo.beanspruche_knopf` (bedingtes
  `UPDATE … WHERE benutzt_am IS NULL`, SQLite entscheidet) — der zweite Druck
  wird beantwortet, wirkt aber nicht. Die Weiche sitzt in `bot.schleife` vor
  `verarbeite_update`: ein Knopfdruck ist keine Nachricht und geht nie in
  `nachricht`, sonst läse ihn der Erkenner wie einen Gruppenbeitrag.
  Der Aufnahme-Umschalter kommt seit dem 05.09.2026 **auch am Erkenner-Pfad**:
  bestätigt `erkenner._melde_interviewmodus` einen erkannten Moduswechsel, geht
  das über `knoepfe.biete_aufnahme` mit demselben Wortlaut wie `/aufnahme`
  (`befehle._TEXT_INTERVIEW_AN`/`_AUS`) — sagt die Gruppe „ich will noch eine
  Aufnahme machen", steht der Knopf da, ohne dass jemand den Slash-Befehl
  kennen muss.
  **Nach jedem beendeten Interview steht eine Knopfleiste** (05.09.2026,
  `knoepfe.biete_nach_aufnahme`, aufgerufen an genau einer Stelle:
  `aufnahme._sende_nach_interview` — beide Wege, `/aufnahme` und der
  Erkenner-Pfad, laufen über `schliesse_ab` dorthin): „Auswerten", „Nächste
  Aufnahme" und, wenn `phasen.naechste_moegliche` es hergibt, „Weiter zu
  Phase N". „Auswerten" spielt eine schon vorhandene Verdichtung direkt aus der
  Datenbank aus (`aufnahme.zeige_verdichtung`, kein zweiter Modellaufruf) und
  verdichtet nur dann im Thread nach, wenn es noch keine gibt (Interview unter
  `MINDEST_WOERTER`). Anlass: Live-Fall Gruppe 2, 13:59 — „Interview 1 ist
  sehr kurz … /auswerten" als Text, zwei Rückfragen der Gruppe, keine
  Auswertung. **Slash-Befehle werden nicht mehr beworben**, nirgends: nicht in
  `_TEXT_*`-Konstanten, nicht in `prompts/system.md`, nicht in
  `prompts/phasen/*.md` (Test: `test_keine_phasenanweisung_bewirbt_einen_slash_befehl`).
  Sie bleiben funktionsfähig, `/hilfe` listet sie weiter — beworben wird der
  Knopf. **Reihenfolge beim Link:** die Begrüßung nennt die Gruppenseite nur,
  wenn `gruppe.web_token` existiert (entsteht in `repo.sichere_gruppe`). Weil
  `bot.erstkontakt` auch als Rückfallweg aus `ablauf.antworte` gerufen wird,
  geht der Link über `bot.stelle_link_sicher`, das die Gruppenzeile notfalls
  selbst anlegt. **Aufnahme-Angebote sind phasenabhängig** (05.09.2026,
  `knoepfe._aufnahme_anbieten`, `PHASE_INTERVIEWS = 3`): „Aufnahme starten" im
  Einstieg und „Nächste Aufnahme" nach einem Interview erscheinen nur in
  Phase 3 — in Begriffe (1) und Fragen (2) gibt es nichts aufzunehmen, die
  Begrüßung sagt dort, dass die Begriffe aus dem Plenum kommen
  (`bot._TEXT_ERSTKONTAKT_BEGRIFFE`). Läuft eine Aufnahme, steht „Aufnahme
  beenden" immer da. Ausdrückliches Aufnehmen (`/aufnahme`, erkannte Absicht)
  bleibt in jeder Phase möglich — eingeschränkt ist nur das Angebot.
  **Fallstrick:** `repo.setze_szene_usa` nimmt einen **bool**, nicht `"ja"`/
  `"nein"` — ein nicht-leerer String ist wahr, ein „nein" würde als Zustimmung
  zur Datenübermittlung enden. Test: `test_usa_knopf_nein_setzt_false_und_nicht_wahr`.
- **Die Phase setzt allein die Gruppe — per Chat, Befehl oder Klick** (seit
  05.09.2026, `phasen.py`, SPEC § 0 Leitsatz 3 Nachtrag; erweitert am
  30.09.2026): `phase_setzen`, `/phase` **oder ein Klick auf eine Phase in der
  Web-Phasenübersicht**, nie still erraten und auch nicht vom Bot selbst. Der
  automatische Sprung (`ART_ERMOEGLICHT`, `sprung_nach`) bleibt **ersatzlos
  gestrichen** — **Datenstand ist nicht Absicht**; ein Klick dagegen *ist* die
  Gruppe.
  **Der Klick geht durch dieselbe Funktion wie der Befehl**
  (`befehle.wechsle_phase`, Parameter `quelle`), damit er nie in einer anderen
  Phase landet als `/phase` oder der Knopf: Bestätigung im Browser → POST
  `/g/<token>/chat/phase` mit Nonce → ein gewöhnlicher Eingang
  (`WEB_TYP_BEFEHL`, Text `/phaseklick N`) → der **Bot** setzt die Phase und
  schickt die Eintrittsnachricht. Der Webserver setzt sie **nicht** selbst: er
  hat kein `klm`, und `knoepfe.eintritt_in_phase` stößt Modellarbeit in
  Threads an. Im Journal steht `quelle 'web'` statt `'befehl'` — sonst ist die
  Zeile dieselbe (Test). `/phaseklick` ist ein **versteckter** Befehl: nicht im
  Menü, nirgends beworben, er ist der Weg des Knopfes durch die Naht.
  Geblieben ist die **Frage**: erlaubt die Materiallage eine höhere
  Stufe, bekommt der Gesprächs-Prompt einen Hinweisblock
  (`kontext._baue_phasenhinweis`) mit der Anweisung, im Fluss nachzufragen —
  einmal je Stufe (`arbeitsstand.phase_angeboten`). Dieselbe Frage hängt an der
  Verdichtungs-Nachricht am Ende eines Interviews (`aufnahme._phasenfrage`);
  beide Stellen teilen sich den Merkposten über `phasen.offenes_angebot()` /
  `merke_angebot()`, deshalb liest die eine Funktion nur und die andere
  schreibt.
- **Die sieben Phasen sind: 1 Begriffe · 2 Fragen · 3 Interviews ·
  4 Setting, Figuren & Geschichte · 5 Schärfung · 6 Szenen als Geschichte ·
  7 Feinschliff** (Stand 06.09.2026 abends, `phasen.PHASEN` — die Liste im
  Code ist die Wahrheit, nicht diese Zeile). Die Geschichte des Umbaus in
  zwei Schritten: 05.09. nachts wurden aus sieben Phasen acht („4 Setting &
  Figuren · 5 Geschichte · 6 Schärfung · 7 Szenentexte · 8 Durchlauf"),
  06.09. abends wurden daraus wieder sieben — **4 und 5 sind wieder eine
  Station** (die Gruppe erfindet Setting, Figuren und Geschichte in einem
  Zug), und aus „Szenentexte + Durchlauf" wurde „6 Szenen als Geschichte" +
  „7 Feinschliff". Der Grund ist in beiden Schritten **nicht**
  Feingliederung, sondern die Arbeitsrichtung: erst erfinden, dann schärfen,
  und die Form einer Szene erst wählen, wenn die Geschichte steht.
  Migriert wird zwischen den Ständen, nicht umgedeutet
  (`db.PHASEN_UMNUMMERIERUNG*`).
- **Erst erfinden, dann schärfen** (Birk, 05.09.2026 23:30 — die tragende
  Entscheidung des Ablaufs). Bis dahin entstanden Figuren und Szenen **aus**
  den Interviews; das Ergebnis war handwerklich richtig und dramaturgisch
  tot, weil die Gruppe ihren eigenen kreativen Anteil nicht wiedererkannte —
  sie sah eine Nacherzählung ihres Materials. Jetzt:
  - In **4 (Setting, Figuren & Geschichte)** erfindet die Gruppe frei. Der
    Bot fragt **offen** („Welche Personen soll es geben? In welchem
    Setting spielt es?" / „Was soll passieren? Wie soll es enden?") mit nur
    zwei Knöpfen — „Eigene Idee" und „Schlag du vor" —, und seine Vorschläge
    speisen sich **ausschließlich aus `arbeitsstand.begriffe`, `fragen` und
    dem schon Festgelegten**. Kein Material: `kontext.baue` liefert dort
    weder Verdichtungen noch Transkripte noch das Kernpaket
    (`kontext.PHASEN_ERFINDEN = (4,)`, `material_erlaubt`,
    `kernpaket_erlaubt` ab `PHASE_KERNPAKET = 5`), und
    `szenenfolge.baue_nutzertext_geschichte` baut den Nutzertext ohne
    Material. Das ist im Code durchgesetzt, nicht im Prompt gebeten — ein
    Prompt, der Material sieht, referiert es.
  - In **5 (Schärfung)** kommt das Material dazu und legt sich **neben** das
    Erfundene, statt es zu ersetzen. Beim Eintritt läuft automatisch ein
    Schema-Aufruf (`schaerfung.mappe`, gemma, Thread — kein Modellaufruf im
    Knopf-Handler): er bekommt Setting, Figuren, Geschichte, die Szenen mit
    Nummer und **alle geprüften `verdichtung_thema`-Einträge nummeriert** und
    ordnet jeden passenden Eintrag einer Szene und/oder einer Figur zu. Zeigen
    kann er nur auf Nummern, Zitate werden mit `zitat.pruefe` gegen das
    Original verifiziert, was nicht passt bleibt weg. Ergebnis: Tabelle
    `schaerfung` (additiv, mit `runde`), daraus je Szene und je Figur eine
    Vorschlagsnachricht mit Grundleiste; „Gefällt uns, weiter" schreibt die
    Felder (`schaerfung.uebernimm_szene` / `uebernimm_figur`), „Noch eine
    Runde" startet einen neuen Lauf mit dem geschärften Stand.
  - **Die Figuren-Ebene 2 ist dorthin gewandert.** „Aus welchem Interview
    spricht sie?" und der Sprachduktus laufen erst ab Phase 5
    (`knoepfe.ebene2_erlaubt`); in Phase 4 ist die Liste nach Ebene 1 fixiert.
    In 4 danach zu fragen wäre genau die Rücklenkung aufs Material, die der
    Umbau vermeidet.
  - **Das Kernthema ist keine eigene Station mehr.** `arbeitsstand.geschichte`
    (Bogen + Ende) übernimmt seine Rolle im Kernpaket. Kernthema, Kernfrage
    und Kernzitate bleiben im Code funktional und getestet
    (rückwärtskompatibel für bestehende Gruppen), werden aber nicht mehr
    angeboten; `kernzitate.py` bleibt als Basis, `schaerfung.py` nutzt
    dieselbe Prüf- und Speicherlogik.
  - Voraussetzungen (`phasen.voraussetzungen`, der Code ist die Wahrheit):
    **2** braucht Begriffe; **3** braucht Fragen, die geprüfte Sensibilität
    (`fragen_weich` **oder** `frage_einleitungen`, beide zählen auch leer),
    `interview_eroeffnung` **und** `interview_abschluss`; **4** braucht eine
    fertige Verdichtung **und** kein offenes, unausgewertetes Interview;
    **5** braucht `rahmen`, `figuren_fixiert_am`, mindestens eine Figur,
    `geschichte` und ≥ 1 Szene; **6** braucht `geschichte` **und** ≥ 1 Szene
    — die Schärfung ist ein Angebot, keine Pflicht, deshalb sperrt sie 6
    nicht; **7** braucht **alle** geplanten Szenen als Geschichte
    (`szene.prosa`, ersatzweise `volltext`) — ein Urteil über ein Stück, dem
    drei Szenen fehlen, ist keins.
- **Der Szenen-Prompt bekommt die Schärfungen JE SZENE, nicht global**
  (`szene._kernpaket_text(conn, chat_id, ziel)`). Eine Szene sieht die
  Interviewstellen, die zu ihr und zu ihren Figuren gehören — und keine
  fremden. Ohne Schärfungen fällt der Code auf die alte, globale
  Kernzitat-Auswahl zurück: eine Gruppe, die den Umbau nicht mitgemacht hat,
  verliert nichts.
- **Der Szenen-Prompt liest auch den gewählten Sprachstil** (02.10.2026,
  Padua M1): `szene._figuren_text` setzt `figur.sprachstil` als eigene Zeile
  (`ZEILE_SPRACHSTIL`, nie in Anführungszeichen — ein Stil ist kein
  Belegzitat) neben `sprachprofil` und die Zitate; den Kopf von Block 3
  wählen seitdem **drei** Lagen: ein echtes Zitat → `FIGUREN_KOPF`
  („wörtlich"), sonst ein nicht-leerer Stil → `FIGUREN_KOPF_MIT_STIL`
  (die Gruppe hat gewählt), sonst `FIGUREN_KOPF_OHNE_STIMME` (unverändert).
  Vorher war der Einzelszenen-Prompt mit und ohne Stil byte-identisch
  (`docs/sprachstil-wirkung-2026-09-30.md`, Weg 2).
- **Die Form je Szene ist ein Vorschlag, keine Vorentscheidung** (Birk,
  06.09.2026 00:30: „Die Form Monolog habe ich niemals eingegeben und aktiv
  bestätigt. Die Form muss mit mehr Bedacht gewählt werden und vom User
  bestätigt werden."). Die vierte Spalte der Szenenzeile landet in
  `szene.form_vorschlag`, die fünfte (Begründung, Pflicht) in
  `form_vorschlag_grund`; **`szene.form` bleibt leer**, bis die Gruppe sie
  Szene für Szene per Knopf bestätigt. In der Szenenvorstellung kommt deshalb
  **zuerst** „Welche Form soll Szene N haben?" mit fünf Knöpfen — der
  Vorschlag zuerst und mit „(Vorschlag)" markiert, darüber seine Begründung —
  und **erst nach dem Druck** die Schreibfrage. `form` ist Pflichtfeld
  (`szene.PFLICHTFELDER`), ohne bestätigte Form läuft kein Szenenlauf.
  Vorschlagsregeln im Prompt: **Dialog ist der Normalfall**, höchstens eine
  Nicht-Dialog-Szene je drei, Szene 1 nie Monolog oder Lied.
- **Phase 4 heißt „Setting, Figuren & Geschichte"** — das frühere Feld
  `rahmen` ist das Setting (Ort, Zeit, Anlass) und behält seinen
  Spaltennamen; nach außen (Knopftexte, Notiert-Zeile, Weboberfläche) heißt
  es „Setting". `format` und `hauptkonflikt` bleiben als Spalten stehen und
  tragen keine Entscheidung mehr. Stichwörter: „Rahmen", „Setting", „Format",
  „Konflikt", „Kernthema" **und „Geschichte"** zeigen seit dem Zusammenlegen
  alle auf 4 — `prompts/erkenner.md` wurde dafür **nicht** angefasst, die
  Zuordnung Wort→Nummer liegt in `phasen.STICHWOERTER`.
- **`geschichte_setzen` ist im Code, aber nicht im Erkenner-Prompt.** Der
  Regelweg zur Geschichte ist der Vorschlagsblock mit seinen Knöpfen
  (`knoepfe._speichere_geschichte`); die Erkenner-Art ist der zweite, freie
  Weg. `prompts/erkenner.md` blieb unverändert, weil in derselben Nacht kein
  Korpuslauf gegen das echte Modell möglich war — `tests/test_korpus.py`
  hält das als `OHNE_KORPUSFAELLE` fest. **Wer den Prompt erweitert, nimmt
  die Art dort heraus und legt zwei Korpusfälle an.**
- **Der Phasen-Prompt ist Fokus, kein Käfig** (05.09.2026). Jede
  `prompts/phasen/N.md` hat den Abschnitt „Was du nicht von dir aus
  anfängst" mit dem festen Schlusssatz „Bittet die Gruppe ausdrücklich darum,
  tust du es trotzdem …"; `tests/test_anweisungen.py` prüft ihn in jeder
  Datei. Der Live-Fall dahinter: eine Gruppe in Phase 2 bat um Kernthema und
  Figuren, `2.md` sagte „kein Kernthema, keine Figuren", und getragen hat die
  Antwort nur, weil der Basis-Prompt sie trug.
- **Phasennummern werden migriert, nicht umgedeutet** (`db.SCHEMA_VERSION`
  = 3, `db.PHASEN_UMNUMMERIERUNG` bis `_3`). **Drei** Schritte hintereinander,
  eine alte Datenbank läuft durch alle drei: acht → sieben (04.09.: Kernthema
  und Figuren wurden eine Phase), sieben → acht (05.09. nachts: 4 und 5
  bleiben, 6 → 7, 7 → 8; die neue 6 bekommt niemand zugewiesen, sie ist ein
  Angebot und keine übersprungene Station) und acht → sieben (06.09. abends:
  4 und 5 werden wieder eine Station, 6 → 5, 7 → 6, 8 → 7). Der Merkposten
  ist SQLites eingebautes `PRAGMA user_version` — keine eigene Tabelle, keine
  Zeile, kein Schema. Das Journal bleibt dabei unangetastet: dort steht
  „Phase 5 · Figuren", weil das am 04.09. wahr war, und ein Journal wird nur
  angehängt.
- **Eine lange Sprachnachricht ohne Interviewmodus wird gefragt, nicht gedeutet** (06.09.2026, Live-Fall Gruppe 1, 13:32–13:37). Der gemessene Fall: 186 Sekunden Interview ohne vorherigen Druck auf „Interview starten". Das Transkript ging als **Gesprächsbeitrag** in den Kontext, das Gesprächsmodell antwortete mit einem Denkspur-Rest, der **Absichtserkenner** las die Aufzählung der interviewten Person als Begriffsliste der Gruppe und **überschrieb `arbeitsstand.begriffe`** (Rassismus, Liebe, Spaß, Streit → Rausgehen, Familie, Musik hören), und der Journal-Extraktor schrieb einen `vorgeschlagen`-Eintrag aus dem Interviewinhalt. Drei Modellläufe auf Material, das keine Absicht der Gruppe war — genau der Fall, gegen den `repo.TYP_TRANSKRIPT` seit § 10.6 schützt, nur hier ungeschützt, weil ohne Modus niemand ein Interview vermutete. Seitdem gilt in `aufnahme._kurz_abschliessen`: Dauer über `HINWEIS_AB_S` (60 s) **und** Interviewmodus aus → **kein Gesprächszug, kein Erkenner, kein Journal-Extraktor** auf dieser Nachricht. Das Transkript wird gespeichert (Empfangen und In-den-Prompt-legen sind zwei Entscheidungen), aber **versteckt**: `repo.aktualisiere_transkribierte_nachricht(..., versteckt=True)` legt es als `TYP_TRANSKRIPT` ab, und damit fällt es aus allen drei Fenstern zugleich (`letzte_nachrichten`, `unextrahierte`, `unjournalisierte`) — `unterdrueckt` allein leistet das **nicht**, es filtert nur `unbeantwortete`. Stattdessen die deterministische Frage „Das klingt nach einem Interview (M:SS). Soll ich es als Interview speichern?" mit zwei Knöpfen (`knoepfe.biete_interview_ohne_knopf`, `ART_OHNE_KNOPF_JA`/`_NEIN`, die `aufnahme.id` im `wert`). Die Knopfregel ist erfüllt: es gibt etwas Fixes zu speichern und genau zwei benannte Möglichkeiten. **Ja** → `aufnahme.nimm_als_interview`: Modus an, Kopf anlegen, **gezielt genau diese Aufnahme** einsammeln (`repo.ziehe_eine_in_interview` mit der id — das `NACHZUEGLER_FENSTER_S`-Zeitfenster darf darüber nicht entscheiden, zwischen Sprechen und Knopfdruck stehen Minuten), `stelle_phase_interviews_sicher`, dann die Folgefrage „Fertig, auswerten" · „Es kommt noch was" (`ART_OHNE_KNOPF_FERTIG`/`_WEITER`, Kopf-id im `wert`); „Fertig" ist wortgleich derselbe Weg wie „Interview beenden" (`beende_interview` + `starte_abschluss` im Thread). **Nein** → `aufnahme.nimm_als_beitrag`: `repo.zeige_transkript_nachricht` macht die Zeile sichtbar, und `bot._zug_und_erkenner` wird **genau einmal** in einem eigenen Thread nachgeholt. **Keine Antwort → gar nichts** (kein Auto-Ja, kein Zeitgeber); fürs Dashboard bleibt der Vorfall `interview_ohne_knopf_offen` stehen, und „Interview starten" sammelt das Material weiterhin als Nachzügler ein — der Weg, der am Live-Tag fünf Minuten später tatsächlich funktioniert hat. Zusage 2 gilt: kein Modellaufruf in den vier Handlern `knoepfe._wirkung_ohne_knopf_ja/_nein/_weiter/_fertig`. Unter 60 Sekunden ändert sich nichts, dort bleibt eine Sprachnachricht ohne Modus ein Gesprächsbeitrag. Der frühere beiläufige Materialhinweis (`aufnahme._TEXT_MATERIAL_HINWEIS`) ist damit tot: er hing an genau dem Zug, den es nicht geben durfte. Tests: `tests/test_interview_ohne_knopf.py`.
- **Ein Interview ist eine Einheit** (seit 05.09.2026, SPEC § 10.6). Das ist
  die Korrektur aus dem Probelauf: ein Interview aus fünf Sprachnachrichten
  wurde zu fünf Aufnahmen, fünf Verdichtungen (zwei leer) und fünfmal „Ich
  höre durch", gefolgt von nichts. Der Fluss jetzt, in einem Satz: **Modus an
  → ein Interview (Kopf), jede Sprachnachricht ein Teil mit sofortigem
  Transkript-Echo im Chat, „fertig" → zusammenfügen, einmal verdichten, die
  Verdichtung in den Chat.** Daran hängen vier Dinge, die nicht verhandelbar
  sind: **im Live-Pfad nur Whisper, der Erkenner und die eine Verdichtung**
  (der Erkenner-Lauf über jedes Teil-Transkript ist seit N1 dabei — gemma,
  unter einer Sekunde, und er ist der einzige Weg, ein „fertig" zu hören, das
  in die Aufnahme statt in den Chat gesagt wurde; kein Gesprächs- oder
  Verdichteraufruf je Teil); **keine Empfangsbestätigung** mehr (das
  Transkript ist sie); das **Echo steht in keinem Fenster**
  (`typ='transkript'`, sonst liest der Erkenner Interviewinhalt als
  Gruppenabsicht); und **ein offener Teil hält den Abschluss auf**, statt
  ohne ihn zu verdichten.
- **Aus einer Aufnahme darf der Erkenner fast nichts schreiben** (seit
  05.09.2026, N1). Der Lauf über ein Teil-Transkript
  (`erkenner.erkenne_in_aufnahme`) wird **im Code** auf
  `erkenner.ARTEN_IN_AUFNAHME` eingeschränkt, nicht nur im Prompt gebeten:
  was eine interviewte Person erzählt, ist Material und nie eine Absicht der
  Gruppe (Korpusfälle n12/n26, a03/a04). Er rückt außerdem kein Wasserzeichen
  vor — er hängt an einer Aufnahme, nicht am Gesprächsverlauf. Die eine
  Ausnahme ist `an_den_bot` (N4): eine Sprachnachricht im Interviewmodus muss
  nicht Material sein, die Gruppe fragt darin auch den Bot direkt an ("zeig
  mir die Verdichtungen"). Der Erkenner erkennt das, `aufnahme.py` zweigt die
  Nachricht daraufhin aus dem Interview ab (`repo.loese_aus_interview`) und
  der Bot antwortet — als Text, unabhängig davon, ob die Frage gesprochen war.
- **Korrekturen wirken, nicht nur im Journal** (05.09.2026, N5,
  `erkenner.transkript_korrigieren`). Ein Hörfehler von Whisper wird überall
  ersetzt, wo er steht — im Transkript selbst, in Zusammenfassung und
  Kernthemen der Verdichtung, in Zitaten von Figuren —, ohne neu zu
  verdichten: die Ergebnisse der Gruppe bleiben stehen, nur der falsche
  Wortlaut wird getauscht. Der Gesprächs-Bot behauptet dabei keine
  Schreibvorgänge mehr, die er nicht selbst ausführt. `entfernen` darf seit
  derselben Änderung auch ein ganzes Interview treffen.
- **Sprachprofil je Figur** (05.09.2026, T3, `sprachprofil.py`): drei Felder
  (`sprachprofil` — Satzlänge, Füllwörter, Abbrüche, Dialekt, Tempo, 3–5
  Zeilen; `zitate` — 3–5 wörtliche Sätze; `quelle_aufnahme_id`). Der Weg
  dahin ist ein Gespräch, kein Namensvergleich: hat eine Figur noch keine
  Quelle, bekommt der Gesprächs-Prompt einen Hinweisblock
  (`kontext._baue_figurenhinweis`), der Bot schlägt im Fluss eine Zuordnung
  vor — mit Belegzitat —, die Gruppe nickt oder ändert
  (`figur_quelle_setzen`), und erst danach läuft EIN Sprachprofil-Aufruf
  (gemma, Reasoning aus, Schema, eigener Thread). Zitate werden geprüft wie
  beim Verdichter (`zitat.pruefe`); ohne ein einziges belegtes Zitat wird gar
  nichts gespeichert — ein erfundenes Zitat würde als Few-Shot in jeden
  weiteren Szenenlauf eingehen.
- **Eine Szene wird geplant, bevor sie geschrieben wird** (05.09.2026, T2):
  neun Felder (`form`, `ort`, `zeit`, `anlass`, `figuren`, `was_passiert`,
  `was_anders`, `kernsaetze`, `ton`), additiv über mehrere Nachrichten
  gesetzt (`repo.setze_szenenfeld` rührt nie mehr als ein Feld an). Erkenner-
  art `szene_planen`, kompakter Text mit `|`-getrennten Feldern. **Fünf**
  Formen (`szene.FORMEN`: Dialog, Monolog, Chor, Lied, Rap), Dialog ist
  der Rückfall — eine „stumme Szene" gibt es nicht mehr, und `prosa.md` im
  selben Verzeichnis ist keine Form, sondern der Regelblock der Phase 6. **Sperre vor dem Aufruf** (T5, `szene.sperrtext`): fehlt ein
  Pflichtfeld (`form`, `ort`, `figuren`, `was_passiert`) oder hat eine Figur
  dieser Szene kein Sprachprofil, gibt es keinen Modellaufruf, sondern eine
  Nachricht in einem Satz, was fehlt — gemessen gegen den Probelauf, in dem
  ein Modell ohne Ort und Besetzung eine Küche statt eines Polizeikessels
  erfand. **Keine Rückfragenkette vor einer Szene** (T7): sagt die Gruppe
  „schreib sie" nach einer Planung, ist das ein Auftrag mit Szenenbezug aus
  dem Verlauf, kein einzelnes Wort — die Sperre meldet in einer Nachricht,
  was fehlt, statt viermal hintereinander nachzufragen.
- **Kein Thema ohne wörtliches Belegzitat, keine Verdichtung ohne Material**
  (seit 05.09.2026, N2). Ein Kernthema, dessen Zitat die Prüfung aus
  `zitat.py` nicht besteht, wird **nicht gespeichert** — nicht mehr mit
  `zitat_geprueft = 0` behalten. Und unter `aufnahme.MINDEST_WOERTER` (40)
  Wörtern im ganzen Interview wird der Verdichter **gar nicht erst gerufen**;
  die Gruppe bekommt eine Zeile mit Dauer und Wortzahl und kann mit
  `/auswerten` widersprechen. Beides kommt aus einem gemessenen Fall: aus
  einer vier Sekunden langen Sprachnachricht entstand ein vollständig
  erfundenes Interview mit drei unbelegten Themen.
- **Verdichtungen stehen ab der ersten fertigen im Gesprächs-Prompt (Block 2)
  und auf der Gruppenseite** — Zusammenfassung und Kernthemen mit Belegzitat,
  im Web nur mit `zitat_geprueft = 1`. Datengetrieben, also unabhängig von der
  Phase (`tests/test_kontext.py`, `tests/test_web.py`).
- **Weiches Löschen statt Löschen** (NACHTRAG N3): `entfernt_am` in `figur`,
  `szene`, `journal`; Arbeitsstandfelder werden auf NULL gesetzt. Jeder Leser
  in `repo.py` und `web_daten.py` filtert `entfernt_am IS NULL`. **Material
  (Aufnahmen, Transkripte, Verdichtungen) hat keinen Entfernungspfad** — dafür
  gibt es allein `scripts/loeschen.py`.
- **Verdichtungen werden nie nachträglich geändert.** Es gibt bewusst kein
  `aktualisiere_verdichtung()` in `repo.py`. Was einmal aus einem Interview
  verdichtet wurde, bleibt stehen; neue Erkenntnis gehört in den
  Arbeitsstand, nicht in eine Korrektur der Verdichtung.
- **Das Journal wird nur angehängt.** Kein `aktualisiere_journal()`, kein
  `DELETE`. Auch das weiche Löschen ändert keinen Text: der zurückgenommene
  Eintrag bekommt `entfernt_am`, ein neuer („Zurückgenommen: …") hält den Weg
  sichtbar. Verworfenes, Entwürfe in der Schwebe und das Warum hinter
  Entscheidungen stehen sonst nirgends außerhalb des kurzen Fensters (SPEC
  § 2).
- **Jede Tabelle außer `bot_zustand` hat `chat_id`.** Kein Ableiten über
  Umwege. Das macht die Löschzusage zu einem `DELETE … WHERE chat_id = ?` je
  Tabelle (`db.TABELLEN_MIT_CHAT_ID`, `db.loesche_gruppe`) — die einzige
  Ausnahme ist die getUpdates-Position pro Bot-Token, die keiner Gruppe
  zugeordnet ist.
- **Eine Antwort, die nur die Frage zurückgibt, ist keine** (seit 05.09.2026,
  `ablauf.ist_echo`/`_ohne_echo`). Gemessener Fall: der Bot schickte eine
  Nachricht der Gruppe wortgleich zurück, mit „Birk:" davor — formal eine
  Antwort, für die Gruppe ein kaputter Bot. Ein Echo löst **genau einen**
  zweiten Aufruf aus, mit einer angehängten Zeile im Nutzertext; ist auch der
  zweite eines, geht er trotzdem raus (`echo_wiederholt`). Keine Schleife: die
  Gruppe wartet, und ein Modell, das zweimal zitiert, zitiert auch beim
  dritten Mal.
- **Die Gruppe erfährt von einem Fehler nur, wenn sie ihn beheben kann oder
  gerade darauf wartet.** Ein gescheiterter Absichtserkenner- oder
  Journal-Lauf ist für die Gruppe unsichtbar (Wasserzeichen bleibt stehen,
  `vorfall` fürs Dashboard); ein gescheiterter Gesprächszug oder eine
  gescheiterte Transkription bekommt eine kurze, ehrliche Zeile, weil die
  Gruppe gerade darauf wartet oder selbst reagieren muss (SPEC § 11.1/§ 11.2).

- **Haltung: speichern beim ersten Mal, proaktiv zur nächsten Phase, keine
  Wiederholung** (06.09.2026, nach dem gemessenen Testabend: Median 20
  Nachrichten je Festlegung, 64 % Fragen, 23 Auswahlknöpfe null Mal gedrückt).
  Nennt die Gruppe einen Wert, wird er sofort abgelegt und in einer Zeile
  bestätigt — keine Rückfrage davor, keine Zusammenfassung danach. Steht etwas
  im Arbeitsstand, fragt der Bot nie erneut danach. Sobald die Voraussetzungen
  einer höheren Phase gespeichert sind, schickt er **einmal** eine eigene kurze
  Nachricht „<Was steht>. Weiter zu <Phase>?" (`knoepfe.biete_phase_proaktiv`,
  Merkposten `arbeitsstand.phase_angeboten`), nicht als vierten Knopf unter
  einem langen Text. **Macht gerade dieses Speichern die Phase
  abschließbar, ersetzt die Abschlussnachricht die Notiert-/Speicherleiste**
  (02.10.2026, Padua Hotfix B5, `knoepfe.sende_abschluss_statt_meldung`, an
  beiden Wegen: `erkenner._sende_meldung` und `basis._speichere`): EINE
  Nachricht mit „Weiter zu Phase N · Titel", „<Feld> ändern"
  (`ART_NOCH_NICHT`) und — am Erkenner-Weg — dem Undo-Knopf. Antworten mit über 60 % Deckung zur vorigen Bot-Nachricht
  werden ersatzlos verworfen (`ablauf.ist_wiederholung`, Vorfall
  `wiederholung_verworfen`); löst eine Nachricht einen Auftrag aus, schweigt
  der Gesprächs-Bot ganz (`ablauf.ist_auftrag`). Die Grundleiste speichert nie
  über ein gesetztes Feld hinweg, solange keine Änderung offen ist
  (`knoepfe._ist_bestaetigung`, `_feld_ist_frei`). Das Kontextfenster ist kurz
  und chronologisch, sortiert nach `gesendet_am` — **nicht** nach
  `message_id`, denn übernommene Historien tragen negative, absteigend
  vergebene ids. Seine Grenzen stehen im nächsten Absatz
  (`kontext.fenster_grenzen()`). Belege:
  `docs/analyse-interaktion-testgruppe-2026-09-05.md`.

- **Das Gesprächsfenster ist in ZEICHEN bemessen, es ist nie leer, und der
  Journal-Extraktor liest dieselbe Grenze** (06.09.2026, Kontext-Audit
  Aufträge 1+2, `docs/kontext-audit-2026-09-06.md` C.2/C.3/C.4). Drei Sätze,
  die zusammengehören, weil sie eine Wurzel haben — *Grenzen, die nur einen
  Teil bemessen, und Schwellen, die nebeneinander statt voneinander abgeleitet
  gesetzt sind*:
  1. **`kontext.FENSTER_ZEICHEN` (12.000) ist das primäre Maß**, nicht mehr die
     Nachrichtenzahl (SPEC § 6.2 Block 7, und dieselbe Entscheidung, die
     hermes-agent in `context_compressor.py:13` getroffen hat: *„Token-budget
     tail protection instead of fixed message count"*).
     `FENSTER_NACHRICHTEN` (20) ist die Obergrenze darüber.
  2. **`FENSTER_MINUTEN` (30) ist weich**: mindestens die letzten
     `FENSTER_MIN_NACHRICHTEN` (6) bleiben immer im Fenster. Gemessen war das
     Fenster nach *jeder* Pause über 30 Minuten — Mittag, Nacht, Probe —
     **vollständig leer** (Befund C.2, an der Test-DB reproduziert). Damit
     funktioniert auch die Pausenzeile `[Pause: N Stunden]` aus § 6.2 zum
     ersten Mal: sie steht auch **vor dem Auslöser**, weil der häufigste Fall
     einer langen Pause der ist, in dem die erste Nachricht danach den Zug
     auslöst.
  3. **`kontext.fenster_grenzen()` / `kontext.waehle_fenster()` sind die eine
     Quelle**, die der Promptbau *und* `journal.berechne_verdraengten_abschnitt`
     lesen. Vorher rechnete der Extraktor gegen `BUDGETS["fenster"] = 8000`
     Token und hielt 31 Nachrichten für „noch im Fenster", während der Prompt
     20 sah — die Differenz wurde nie journalisiert und stand danach nirgends.
     `BUDGETS["fenster"]` ist seitdem **historisch und von keinem Codepfad mehr
     gelesen**. `journal.SCHWELLE_VERDRAENGUNG` ist von 2.000 auf **600** Token
     gesenkt (sie bezog sich auf das alte 8.000er Fenster; an Tag 1 sprang der
     Extraktor in **allen drei** Betriebsgruppen kein einziges Mal an).
     **Wer eine Fenstergrenze ändert, ändert sie in `fenster_grenzen()` — und
     der Regressionstest `test_verdraengung_rechnet_gegen_dasselbe_fenster_wie_
     der_prompt` prüft, dass Fenster und verdrängter Abschnitt die
     Nachrichtenliste lückenlos und überschneidungsfrei teilen.**

  Dazu die Sichtbarkeit, die vorher fehlte: **`kontext.baue` schreibt bei jedem
  Aufruf eine Umriss-Zeile ins Log** (`kontext.umrisszeile`, Token je Block,
  Gesamt, gekürzt ja/nein — **nur Zahlen, nie Prompt-Inhalt**). Sie steht in
  `baue()` selbst und nicht bei den Aufrufern, damit sie jeden Pfad erfasst;
  ein durchgereichter Parameter wäre genau der Weg, auf dem sie beim nächsten
  neuen Aufrufer wieder fehlt (`umriss()` gab es seit jeher, es rief nur
  niemand). Und ein **zweiter Vorfalltyp `kontext_kuerzung_erfolglos`**: ist
  der Körper nach allen vier Kürzungsstufen immer noch über der Grenze, wird
  das eigens vermerkt, mit dem Umriss der übrig gebliebenen Blöcke.
  `kontext_gekuerzt` bleibt daneben stehen — beides ist wahr, aber „gekürzt"
  und „reicht nicht" sind zwei verschiedene Meldungen (hermes-agent,
  `should_compress_info`: *„Without this signal an over-threshold session fails
  opaquely."*).

- **Die Fragen sind eine Auswahl, und danach kommt der Leitfaden** (06.09.2026,
  Birk). Phase 2 schlägt zehn Fragen als `VORSCHLAG FRAGENAUSWAHL:` vor, aus
  denen die Gruppe per Mehrfachauswahl genau drei antippt — ein Knopf je Frage,
  Toggle über `telegram.aktualisiere_knoepfe`, Zustand in
  `arbeitsstand.fragen_gewaehlt` und nie in der Tastatur, „Diese 3 nehmen" wirkt
  nur bei genau drei. Auf das Speichern folgt automatisch eine
  Sensibilitätsprüfung (Einleitungen je heikler Frage, `VORSCHLAG
  EINLEITUNGEN:`) und danach Eröffnung und Abschluss (`VORSCHLAG EROEFFNUNG:`),
  beide als Ping-Pong über die Grundleiste und beide als Auftragszug im eigenen
  Thread, nicht im Knopf-Handler. Daraus baut `leitfaden.baue()` deterministisch
  den Gesprächsleitfaden — Eröffnung, Fragen mit ihren Einleitungen, Abschluss —,
  den der Bot beim Schritt in die Interviews und beim Interviewstart genau
  einmal schickt und danach nur noch auf Knopf, `/leitfaden` (versteckt) oder
  auf der Gruppenseite zeigt. Deshalb hängt `phasen.voraussetzungen[3]` seitdem
  an Fragen **und** `interview_eroeffnung`: ohne Eröffnungstext geht keine
  Sechzehnjährige auf eine fremde Person zu, während leere Einleitungen ein
  Ergebnis der Prüfung sind und kein fehlender Wert.

- **„Neu schreiben" heißt neu, und der Bot zeigt, dass er arbeitet**
  (06.09.2026). Der Knopf „Neu schreiben" gibt die alte Fassung NICHT als
  Vorlage mit (`szene.NEU_MARKER` im Auftrag → `NEU_HINWEIS` statt Volltext);
  „Passt, aber anders" überarbeitet den bestehenden Text mit der Regie-Notiz.
  Der Szenen-Prompt trägt vor den Angaben die **Aufgabe der Szene** an ihrer
  Position (`szene._aufgabe_text`: erste = Exposition wer/zueinander/warum
  hier/worum; Mitte = verschärfen/wenden; letzte = einlösen) und ganz oben
  Rahmen/Geschichte als bindende Vorgabe. Solange Opus schreibt, laufen
  Tippanzeige und eine wechselnde Emoji-Zeile (`szene._arbeitet_sichtbar`),
  die am Ende wieder gelöscht wird.

- **Prompts werden nicht gelesen, sondern erzeugt und gemessen** (06.09.2026,
  Prompt-Audit `docs/prompt-audit/2026-09-06/`, `scripts/erzeuge_prompts.py`).
  Jeder Prompt-Pfad hat einen Test gegen eine Fixture-DB im *Spätstand*
  (`tests/test_prompt_audit.py`) — gegen eine frische Datenbank zeigt sich
  keiner der Befunde (52 k Zeichen Nutzertext, dieselbe Zusammenfassung 11×,
  Rahmen 3×), und genau deshalb hatten sie überlebt. Drei Regeln: kein Satz über
  80 Zeichen zweimal, Nutzertext unter der harten Grenze
  (`kontext.ZEICHEN_GRENZE_VORGABE` = 24 000, Env `IT_PROMPT_ZEICHEN`, Kürzungsreihenfolge
  Verlauf → Journal → Verdichtungen, Vorfall `kontext_gekuerzt`), keine
  veralteten Reste. Ein Fakt hat genau eine Stelle im Prompt; steht er an zweien,
  ist eine davon zu löschen, nicht beide zu behalten. Ein Prompt-Kopf, der etwas
  ankündigt, muss es auch liefern — sonst ergänzt das Modell das Fehlende selbst.

- **Jede Phase hat im Chat denselben Rahmen** (06.09.2026, Birk): Eintritt
  über EINEN Weg (`knoepfe.eintritt_in_phase` — Knopf, `/phase`, Erkenner,
  proaktive Meldung) mit deterministischer Nachricht aus `phasentexte`
  (Einleitung 2–4 Sätze, Checkliste der Parameter, Einstiegsknöpfe darunter);
  Abschluss über `biete_phase_proaktiv` mit allen gesetzten Parametern und
  „Weiter zu <Phase>" · „Noch etwas aendern", einmal (Merkposten
  `phase_angeboten`). `/stand` nutzt dieselben `standzeilen`. Jinja wie im
  Fundusbot wurde geprüft (`docs/prompt-audit/2026-09-06/jinja-inspiration.md`):
  nicht installiert, nicht jetzt — `kontext.baue` braucht Blöcke als Objekte
  (Kürzung, Protokoll); Kandidaten für später sind die unkritischen Pfade.

- **Das Eingabe-Budget des Szenenlaufs ist gemessen, nicht gesetzt**
  (06.09.2026). Deutscher Prosatext tokenisiert schlechter als die Faustregel:
  gegen `count_tokens` gemessen ergab der echte Szenen-Prompt 38 610 Zeichen =
  20 222 Token, also **1,9 Zeichen je Token** — `kontext._ZEICHEN_JE_TOKEN = 3`
  hätte um 36 % zu niedrig geschätzt, deshalb `szene.SZENE_ZEICHEN_JE_TOKEN`.
  Die beiden Anbieterpfade sind nicht vergleichbar: bei Claude (`max_tokens =
  32 000`, kein extended thinking) müssen Eingabe **plus** `max_tokens` unter
  das Kontextfenster passen → 126 000 Token; bei Infomaniak zählen beide gegen
  `max_total_tokens = 249 984`, und `llm.prosa` läuft mit 200 000 → 37 488
  Token. Beide Budgets gelten seit dem 30.09.2026 für die **ganze** Eingabe,
  Systemanweisung eingeschlossen: `szene.nutzer_budget` zieht die Anweisung
  des Laufs (Form + Stil, gemessen bis 37 043 Zeichen ≈ 19 496 Token) ab,
  bevor der Nutzertext gemessen wird — vorher hätte ein Nutzertext am Budget
  mit ihr den Infomaniak-Raum um 7 000 Token gerissen
  (`docs/kontext-3-5-kalibrierung.md`). Env `IT_SZENE_TOKEN_MAX` überschreibt
  und meint ebenfalls die ganze Eingabe. Jede Szene liefert per
  Pflichtzeile `Zusammenfassung:` + `Anders gemacht:` (→ `szene.zusammenfassung`,
  Journal-Eintrag bei Abweichung); passt der Volltext aller Vorszenen nicht,
  greift die Kürzungsleiter älteste Szene → Zusammenfassung, dann Chat-Block auf
  10, dann Kernpaket-Begründungen, dann 3 Zitate/Figur — nie Rahmen, Aufgabe,
  Angaben, Auftrag; alles im Continuity-Kopf benannt, Vorfall
  `szene_prompt_gekuerzt`. Der Szenenlauf bekommt den Chat seit der letzten
  Fassung dieser Szene (mind. 20 Nachrichten) als Block „Was die Gruppe zuletzt
  dazu gesagt hat" — Chat schlägt gespeicherte Angaben. `stop_reason ≠ end_turn`
  ist ein Fehler (`szene_abgeschnitten`), kein Text; `_pruefe_budget` warnt ab
  90 % der tatsächlichen Token.

- **Kürzen ist eine Überarbeitung, keine neue Szenenfolge** (30.09.2026,
  Maßnahmen C4/C7/C9/C10 aus `docs/analyse-phase5-chaos-2026-09-06.md`; der
  Plan dazu: `docs/superpowers/plans/2026-09-30-padua-a5-dortmund-reste.md`).
  Vier Dinge, die eine Wurzel haben — am 06.09. bat die Gruppe um eine
  Kürzung, und weil es dafür keinen Weg gab, wurde daraus ein Neuaufbau:
  aus drei Szenen wurden sechs und eine Stunde später noch einmal sechs.
  1. **Der Knopf „Kürzer (25 %)"** steht an genau zwei Orten — unter der
     fertigen Kurzgeschichte (`knoepfe.zeige_kurzgeschichte`, Phase 6) und
     unter einem frisch geschriebenen Szenentext
     (`knoepfe.biete_nach_szenentext`, Phase 7). **Nicht** unter „Szene N
     ansehen": dort liest man, dort gehört „Frühere Fassungen" hin. Er wirkt
     wie „Passt, aber anders", nur ohne Rückfrage: die Regie-Notiz steht fest
     (`kuerzung.notiz_fuer_szene`, `notiz_fuer_prosa`), der Prozentwert an
     **einer** Stelle (`kuerzung.PROZENT`). Mit Szenennummer läuft
     `szene.starte`, ohne läuft `kurzgeschichte.starte` — die Phase entscheidet
     sich dabei von selbst, weil `szene.schreibt_prosa` ohnehin nach `prosa`
     oder `volltext` verzweigt. **Die Prosa-Notiz nennt keine
     Abschnittszahl** (seit dem Abschlussreview der Karte P2-Fix,
     02.10.2026): gebunden ist die Zahl, weil der Abgleich ergänzend ist und
     sonst zwei Abschnitte mit ihrem alten, langen Text stehen blieben — aber
     genau einmal, im Auftrag (`kurzgeschichte._ZEILE_ABSCHNITTE`, die Zahl
     der geplanten Szenen) oder bei aktivem Längen-Profil im Budget-Block
     (`laengen.SATZ_BINDUNG`). Vorher zählte die Notiz die Szenen **mit**
     Prosa, und bei sechs geplanten und vier geschriebenen standen „genau 4"
     und „genau 6" im selben Prompt
     (`tests/test_kuerzung.py::test_kuerzen_bindet_die_abschnittszahl_genau_einmal*`).
     Die Notiz sagt nur noch, dass die Abschnitte mit Titeln und Reihenfolge
     bleiben und innerhalb gekürzt wird. Beim Kürzen der ganzen
     Geschichte geht die bisherige Prosa **als Vorlage** in den Prosalauf
     (`kurzgeschichte.starte(..., vorlage=True)`) — sonst schriebe das Modell
     „25 Prozent kürzer" über einen Text, den es nie sah; ohne `vorlage`
     bleibt der Nutzertext zeichengleich zum bisherigen Weg. Der Prosalauf
     hat dabei **keine eigene Eingabebudget-Prüfung** (wie schon vorher
     nicht). Beim Kürzen **einer Szene in Phase 6** ist `volltext` leer; der
     Auftrag trägt deshalb `szene.BISHER_MARKER`, und nur mit ihm steht die
     bestehende Prosa der Szene als „Bisheriger Text" im Nutzertext
     (`szene._diese_szene_text(..., bisher_prosa=True)`) — jeder Lauf ohne
     Marker bleibt zeichengleich. `kuerzung.starte` liefert
     `(quittung, gestartet)`, `gestartet` aus dem Rückgabewert des
     Schreibwegs (Thread oder `None`), nicht aus dem Wortlaut der Quittung;
     und `kuerzung.starte` setzt selbst den Prüf-Vermerk für spätere Szenen
     (`knoepfe._melde_spaetere`), nur mit Lauf — damit gilt er für Knopf und
     Erkenner gleich.
  2. **Die Erkenner-Art `szene_kuerzen`** macht „mach das kürzer" im Chat zum
     selben Weg. Sie hat **keinen Schreibpfad** (wie `szene_schreiben`) und
     wird erst in `laufe()` ausgewertet (`erkenner._starte_kuerzung`),
     höchstens **eine je Lauf**. Leerer `wert` heißt „die ganze
     Kurzgeschichte" — eine geratene Nummer schriebe die falsche Szene neu.
     **Aber nur, solange Geschichten entstehen:** ab der Phase der
     Theatertexte (`szene.schreibt_prosa` falsch, heute ab 7) startet der
     Erkenner-Weg ohne Nummer **keinen** Lauf über die ganze Geschichte,
     sondern fragt in einem Satz nach der Szene
     (`kuerzung.TEXT_WELCHE_SZENE`). Das ist eine **vorläufige
     Voreinstellung, die Entscheidung liegt bei Birk**; der Knopf „Kürzer"
     unter der Kurzgeschichte ist davon nicht betroffen, und
     `prompts/erkenner.md` (Punkt 23, „der ganze Text, der zuletzt entstanden
     ist") blieb unverändert, damit kein neuer Korpuslauf fällig wird.
     Auf **„im Zweifel kein Eintrag"** kalibriert, wie `szene_schreiben` und
     `entfernen`: Kritik an der Länge („zu lang, was meint ihr", Korpusfall
     n20) feuert nicht, eine dauerhafte Längenvorgabe („höchstens eine Seite
     ab jetzt", fl04) bleibt `festlegung_setzen`, und aus einer **Aufnahme**
     gilt sie nie (`ARTEN_IN_AUFNAHME` bleibt bei drei). Korpus: `sk01`/`sk02`
     positiv, `sk03`–`sk05` negativ, plus
     `tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle`, der
     n20/n27/fl04 auf ihrem Sollwert festhält. **Der Erkenner-Korpuslauf
     gegen das echte Modell steht aus** (Birk, kostet Geld) — wie beim
     bestehenden Hinweis zu `festlegung_setzen` oben.
  3. **Schärfung und Szenenfolge laufen nie gleichzeitig**
     (`vorschlagssperre.py`, `nimm_oder_merke`). Wer die Sperre nicht bekommt,
     wird **gemerkt** und läuft nach der Freigabe automatisch — nicht
     abgewiesen. Das ist der Unterschied zum alten `szenenfolge._TEXT_BESETZT`,
     das den Auftrag verlor; die Konstante bleibt als Nutzertext stehen, hat
     aber keinen Aufrufer mehr. **Nehmen und Merken sind EIN atomarer Schritt**
     (`nimm_oder_merke`, Race-Fund): ein `nimm` gefolgt von einem separaten
     `merke` hätte ein Fenster offen gelassen, in dem ein gleichzeitiges
     `gib_frei` einen noch leeren Merkplatz leert und den kurz danach
     gemerkten Auftrag nie nachholt — `gib_frei` poppt den Merkplatz und gibt
     die Sperre unter demselben Schutz frei, `nimm_oder_merke` nimmt die
     Sperre oder legt den Auftrag unter demselben Schutz ab. Alle fünf
     Aufrufer (`schaerfung.starte`, die vier `szenenfolge.starte*`) nutzen
     `nimm_oder_merke` und geben die Sperre bei einer Exception vor dem
     Thread-Start selbst wieder frei. `schaerfung.starte` liefert dafür
     `GEMERKT` statt `None` — `None` heißt „es gab nichts anzustoßen", und
     `knoepfe.starte_schaerfung` spielt darauf die vorhandene Lage aus; die
     Zeile „Schärfung läuft, einen Moment" schickt der Knopf-Handler nur,
     wenn `vorschlagssperre.laeuft` beim Anstoßen noch `False` war — sonst
     schickt `schaerfung.starte` selbst `TEXT_GEMERKT`, und ein vorab
     gesendetes „gleich" wäre eine zweite, widersprüchliche Zeile im selben
     Chatfenster.
  4. **Die Richtungswahl speichert ihre Szenen mit**
     (`szenenfolge.szenen_in_zeile`, `szenen_der_richtung`, `lege_inline_an`).
     Ein Richtungs-Knopf trägt immer genau **eine** Zeile, und
     `zerlege_geschichte` liest Szenen erst ab Zeile 3 — nennt die Richtung
     ihre Szenen also im Satz („… Szene 1: Ankunft am Steg. Szene 2: …"),
     gingen Titel und Form verloren, und der Folge-Lauf erfand sie eine
     Minute später neu. `szenen_in_zeile` erkennt eng (mindestens zwei
     Anker, Nummern zusammenhängend ab 1, Form nur am Stückende, Titel bis
     `TITEL_MAX` = 80 Zeichen); Lücken oder Doppelungen in der Nummerierung
     hinterlassen den Vorfall `richtung_szenen_unvollstaendig`, statt still
     zu verwerfen — aber nur, wenn die Zeile keine Formwahl ist: eine
     Formabfolge mit Lücke geht in `_uebernimm_formwahl` und hinterlässt
     allein `geschichte_war_formwahl`. **Review-Fix (`c9af872`):** der Inline-Weg gilt darüber
     hinaus nur, wenn kein Titel mit einem Formwort beginnt und jede Form,
     die `formabfolge` in der Zeile findet, genau als Anhang eines dieser
     Titel steht (`szenenfolge.szenen_der_richtung`) — sonst bleibt es beim
     bisherigen `_uebernimm_formwahl`, das eine reine Formabfolge ohne
     eigene Titel sichert. Trifft der Inline-Weg zu, geht die Form in
     `szene.form` und nicht in `form_vorschlag` — die Gruppe hat gedrückt —,
     und `lege_inline_an` setzt dabei **nur eine leere** `form` (eine per
     Knopf schon bestätigte Form einer bestehenden Szene bleibt stehen, da
     `repo.setze_szenenfeld` `GESCHUETZTE_SZENENFELDER` nicht von sich aus
     beachtet). **Danach läuft kein `starte_geschichte_szenen` mehr:**
     `titel` steht nicht in `repo.GESCHUETZTE_SZENENFELDER`, ein frischer
     Vorschlag würde die Titel der Gruppe überschreiben und kostet gemessene
     110 s.
     **Eine bekannte Grenze, gemessen:** `if not alter_block: zeilen = []` in
     `knoepfe._speichere_geschichte` verwirft heute **nichts** (auf dem
     Menü-Weg ist der `wert` immer einzeilig) und bleibt für den
     `alter_block`-Weg stehen.
- **Ein Erkennerlauf ist mit einem Tipp zuruecknehmbar** (01.10.2026, Karte U,
  Birk 30.09.: "Die Tests vor dem Workshop bilden die echte Chatrealitaet der
  Studierenden nur begrenzt ab. Ein falsch gespeicherter Wert darf deshalb
  nicht STILL bleiben"). Unter **jeder** "Notiert:"-Meldung steht ein ruhiger
  Knopf "Rueckgaengig" (Padua: "Undo") als letzte Zeile der Tastatur -- die
  bestehende Grundleiste bleibt darueber, mobil gilt ein Hauptknopf je
  Bildschirm. Sieben Saetze, die zusammengehoeren:
  1. **Erfasst wird per DIFF, nicht per Nachbau je Art.** `erkenner.laufe`
     nimmt vor und nach `wende_an` einen Schnappschuss der verfolgten Tabellen
     (`ruecknahme.plan`, `repo.schnappschuss`); die Differenz sind die
     Schritte. Jede `_wende_*_an`-Funktion nachzubilden waere eine zweite
     Wahrheit, die beim naechsten Umbau still ausschert --
     `repo.fuehre_figur_zusammen` beruehrt drei Tabellen auf einmal,
     `korrigiere_transkripte` vier. Ein parametrisierter Test faehrt jede
     undo-faehige Art gegen die Spaetstand-Fixture und vergleicht den Dump
     (`tests/test_ruecknahme_rundreise.py`); ein zweiter prueft, dass jede von
     `wende_an` geschriebene Spalte verfolgt ist oder mit Grund in
     `AUSSEN_VOR` steht.
  2. **Eine Meldung, eine Ruecknahme** -- keine Einzelauswahl. Der Knopf traegt
     die `erkenner_lauf.id` im `wert` der Knopfzeile, `callback_data` bleibt
     `k:<id>` (Zusage 1), kein Modellaufruf im Handler (Zusage 2), idempotent
     doppelt: `repo.beanspruche_knopf` **und** ein bedingtes
     `UPDATE erkenner_lauf ... WHERE zurueckgenommen_am IS NULL` in derselben
     Transaktion (Zusage 3).
  3. **Weich statt hart** (N3): eine im Lauf angelegte Figur, Szene oder
     Festlegung bekommt `entfernt_am`; eine reine Verknuepfungszeile
     (`szene_figur`) wird geloescht, eine im Lauf geloeschte wieder
     eingefuegt; eine im Lauf entstandene `arbeitsstand`-Zeile wird
     **geleert**, nicht geloescht (sie traegt die Phasen-Buchhaltung).
     "Figur weg" heisst: kein Leser in `repo`/`web_daten` sieht sie mehr.
  4. **Alles oder nichts.** Stimmt EIN betroffener Wert nicht mehr mit dem
     Stand nach dem Lauf ueberein, oder zeigt inzwischen etwas Fremdes auf
     eine neu angelegte Figur/Szene (`ruecknahme.verweise()`, aus `db.SCHEMA`
     hergeleitet), wird **nichts** geaendert und die Gruppe bekommt einen Satz
     ("Seitdem geaendert -- bitte im Arbeitsstand korrigieren."). Ein halber
     Rueckschritt waere schlimmer als keiner.
  5. **Das Journal bleibt stehen** (nur-anhaengend): die Zeilen des Laufs
     werden nicht angefasst, die Ruecknahme haengt eine neue an
     (`quelle 'undo'`). Die Antwortzeile geht ausserdem als Bot-Zeile in
     `nachricht`, damit der Gespraechs-Bot im naechsten Zug nicht behauptet,
     der Wert stehe.
  6. **Kein Undo fuer die Phase und fuer die USA-Einwilligung.** Beide fallen
     automatisch heraus, weil `gruppe` und die Phasenspalten nicht verfolgt
     werden; ihre Zeilen stehen in der Meldung, aber nicht in "Rueckgaengig
     gemacht:". Die Einwilligung ist eine Datenschutzentscheidung mit eigenen
     zwei Knoepfen -- **offener Punkt fuer Birk**, nicht fuer diese Karte.
  7. **Nur die Erkenner-Meldung bekommt Undo.** Die Notiert-Zeilen aus
     Knopfdruecken (`knoepfe.basis._speichere`) und die Gruppenseite sind
     bewusste Handlungen der Gruppe an einem fixen Wert; dort hat sich keine
     Schicht geirrt, die man zurueckdrehen muesste. Nach einem wirksamen Undo
     werden die Grundleisten-Knoepfe derselben Nachricht verfallen gelassen,
     sonst schriebe "Ja, speichern" den gerade zurueckgenommenen Wert wieder
     (der Wert steckt im Knopf). Und eine ueberholte Leisten-Nachricht wird auf
     ihren Undo-Knopf **reduziert** statt ganz abgenommen: er ist der einzige
     Weg, ihren Wert zurueckzunehmen.

- **Die Laenge einer Szene waehlt der Code, nicht das Modell -- und nach dem
  Schreiben wird genau EINMAL nachgearbeitet** (30.09.2026, Karte R,
  `laengen.py` + `sprachpass.py` + `nachpass.py`, Befund
  `docs/padua-r-laengen-2026-09-30/BEFUND.md`). Der Anlass ist gemessen: am
  06.09.2026 hat Birk den Gruppentext vor dem Versand von Hand nachbearbeitet,
  zweimal in Richtungen, die eine Maschine haette gehen koennen. Erstens die
  Laenge -- das Textbuch v2 dieses Tages hatte 825 / 802 / 603 Woerter in drei
  **verschiedenen** Formen, also praktisch eine Laenge, weil
  `kurzgeschichte.ANWEISUNG` eine Gesamtlaenge nennt und sonst nichts. Zweitens
  die Sprache: Gedankenstrich-Inflation, "nicht X, sondern Y",
  Adjektiv-Trippel, Fazitsatz -- Muster, die `prompts/theater-tells.md`
  praeventiv verbietet und die trotzdem dastanden.
  Seitdem, **nur bei aktivem Profil** (`[laengen] aktiv = false` im Vorgabeprofil
  und in Dortmund): der Code wuerfelt je Gruppe ein **Rhythmus-Muster**
  (`kurz-lang-kurz`, `lang-kurz-schlag`, ...) und liest es **zyklisch** ueber
  die Szenennummern -- zyklisch und nicht ueber die Gesamtzahl verteilt, weil
  eine spaeter eingefuegte Szene sonst das Budget einer frueheren verschiebt
  und das Nachzaehlen gegen eine andere Zahl rechnet als der Lauf. Der Seed
  **ist die `chat_id`**: kein `random`, kein gespeicherter Wert, und trotzdem
  bekommt dieselbe Gruppe immer dasselbe Muster. Eine Journalzeile
  (`laengen.journalzeile`) haelt Seed, Muster, Faktor und Budgets fest, damit
  ein Mensch es nachrechnen kann.
  Das Budget geht **je Szene** in den nie gekuerzten Teil des Szenen-Prompts
  (`szene._REIHENFOLGE`, `"laenge"` direkt hinter `"aufgabe"` -- eine Laenge,
  die die Kuerzungsleiter wegwerfen darf, ist keine) und **als Liste plus
  Summe** in den Prosa-Prompt; dort **ersetzt** die Summe die feste Zeile
  `kurzgeschichte.ZEILE_GESAMTLAENGE`, statt sie zu ergaenzen (ein Fakt hat
  genau eine Stelle im Prompt). **In Phase 6 greift ein Budget je Form
  sehr wohl**, obwohl `szene.form` dort meist NULL ist: die Szenenfolge steht
  beim Eintritt fest (`phasen.voraussetzungen`), `formen/prosa.md` erklaert sie
  fuer verbindlich, und `laengen.form_der_szene` liest **bestaetigt vor
  vorgeschlagen vor Profilvorgabe**. Gelesen, nicht geschrieben: `szene.form`
  bestaetigt weiter allein die Gruppe.
  **Die Gruppe uebersteuert auf zwei Wegen, beide vorhanden.** "Kuerzer (25 %)"
  unter der **ganzen** Geschichte merkt seinen Faktor dauerhaft
  (`arbeitsstand.laengen_faktor`, additiv ueber `db._migriere_fehlende_spalten`,
  gesetzt in `kuerzung.starte`) -- damit werden auch die Szenen, die es noch
  nicht gibt, kuerzer **geplant** statt erst geschrieben und dann gekuerzt.
  "Kuerzer" unter **einer** Szene tut das bewusst nicht: eine Entscheidung
  ueber eine Szene ist keine ueber alle. Und eine ausdrueckliche Laengenansage
  ("hoechstens eine Seite pro Szene ab jetzt") **deckelt** das Budget --
  gelesen aus `festlegung` im Bereich `stil` (`laengen.woerter_aus_festlegungen`),
  wohin `prompts/erkenner.md` Punkt 23 sie ausdruecklich weist (Korpusfall
  `fl04`). **Keine neue Erkenner-Art**, also kein weiterer bezahlter
  Korpuslauf.
  **Nachgearbeitet wird genau einmal, und das ist gebaut, nicht abgesprochen.**
  `nachpass.nach_szene` bzw. `nach_geschichte` laeuft am Ende von
  `szene._lauf` bzw. `kurzgeschichte._lauf` -- **im schon laufenden Thread und
  unter dessen Sperre**, deshalb `szene.schreibe`/`kurzgeschichte.hole_text`
  und nie `starte` (die Sperre liegt). Nachzaehlen (ab
  `nachzaehl_schwelle` = 130 % des Budgets) und Sprachpass ergeben **eine**
  Regie-Notiz und **einen** Lauf -- waeren es zwei Wege, waeren es bis zu zwei
  Laeufe je Szene. Bleibt das Ergebnis ueber dem Budget, gibt es einen
  **Vorfall** (`nachpass_reicht_nicht`) und **keinen zweiten Lauf**: ein
  Modell, das zweimal zu lang schreibt, schreibt es beim dritten Mal auch
  (dieselbe Begruendung wie bei `ablauf.echo_wiederholt`). In Phase 6 ist es
  **ein** Lauf fuer **alle** Abschnitte.
  **Der Zitatschutz ist die wichtigste einzelne Massnahme dieses Pfades.** Ein
  Ueberarbeitungslauf, der einen woertlichen Interviewsatz glattzieht, nimmt
  der Gruppe genau das, was sie selbst gesammelt hat (`theater-tells` Nr. 21,
  25, 28). Geprueft wird mit `zitat.pruefe` -- **keine zweite, strengere
  Normalisierung**, dieselbe Funktion wie bei Verdichter, Kernzitaten,
  Sprachprofil, Schaerfung und Dramaturgie. Geht ein Zitat verloren, wird das
  Ergebnis **verworfen**: in Phase 7 wird die alte Fassung zurueckgeschrieben
  (`repo.aktualisiere_szene`; die Fassungszeile des Laufs bleibt in
  `szenenfassung` stehen -- nur anhaengen, nie loeschen), in Phase 6 wird gar
  nichts gespeichert, weil `kurzgeschichte.hole_text` die Antwort vor dem
  Speichern liefert. Dort haengt an derselben Stelle die zweite Wache: eine
  **geaenderte Abschnittszahl** wird verworfen, weil `lege_szenen_an`
  ergaenzend abgleicht und zwei Abschnitte sonst ihren alten, langen Text
  behielten.
  **Die Gruppe erfaehrt von all dem nichts.** Der Nachpass ist eine Zugabe:
  sie hat ihren Text, sie wartet nicht darauf, sie kann nichts tun. Ein
  gescheiterter Nachpass ist deshalb unsichtbar und bekommt einen Vorfall
  (SPEC § 11.1). Kosten und Aufrufe landen in `aufruf` mit eigener `art`
  (`szene_nachpass`, `kurzgeschichte_nachpass`) -- wie bei `dramaturgie_b1`,
  damit Dashboard und Kostenzeile den Weg getrennt sehen.
  **Bekannte Grenzen:** die Rahmenwerte in `[laengen.rahmen]` sind
  **Vorschlaege und ungemessen** (Chor/Lied 80-200, Rap 120-250, Dialog
  200-450, Monolog 150-350) und liegen bereits bei etwa einem Viertel des
  Herkules-Masses -- ob sie der Normalfall oder schon die Instagram-Laenge
  sind, entscheidet Birk (Befund Abschnitt 1). `zitat.pruefe` glaettet
  Whitespace und typografische Anfuehrungszeichen, ein Zitat bleibt also
  woertlich und nicht byte-genau erhalten. Und `scripts/laengen_probe.py` ist
  der **kostenlose** Nachweis dieses Pfades: die Simulation erreicht Phase 7
  und den Kuerzungsweg nicht.

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
  **Zwei bekannte Grenzen, gemessen:** Sprachprofil (`sprachprofil.py`) und
  Nachpass (`nachpass.py`) rufen ebenfalls ueber `klm.schema` und haengen
  damit hinter derselben `llm.LLM._anfrage` -- waehrend der Pause scheitert
  also auch ihr Aufruf, aber ohne eigene Pausenmeldung: ihr Fangnetz ist ein
  gewoehnliches `except Exception` mit `log.exception`, nicht
  `kosten.melde_pause_wenn_deckel`, und ein Fehlschlag sieht fuer die Gruppe
  aus wie jeder andere. Und der Erkenner laeuft waehrend der Pause
  unveraendert **je Nachricht** weiter und scheitert jedesmal an
  `kosten.pruefe` -- jeder Lauf schreibt einen eigenen Vorfall
  `extraktor_fehler` (`erkenner.py`), ungedrosselt im Unterschied zur
  Pausenmeldung selbst: bei einer aktiven Gruppe fuellt sich das Dashboard
  mit gleichlautenden Vorfaellen, statt der einen Zeile, die der Deckel
  eigentlich verspricht.

- **Prüflauf vor jeder Anzeige, Phasen 6/7 für Padua** (03.10.2026, Padua
  Phasen TEIL 2; nur mit `[prueflauf] aktiv`/`[ueberarbeitung] aktiv`, beide
  nur in `workshop/padua-2026/profil.toml`). Birks Entscheidungen: höchstens
  zwei Runden (`schleife.RUNDEN_MAX`); fällt ein Score, bricht der Lauf ab
  und die **bessere** Fassung bleibt (`behalte_bessere=True` über
  `schleife.schnappschuss`/`stelle_wieder_her`); wer ein geprüftes
  Interviewzitat verliert (`sprachpass.verlorene`), wird verworfen; danach
  der Sprachpass (`nachpass`); an die Gruppe **höchstens drei Zeilen**
  (`prueflauf.ZEILEN_MAX`), nie der Volltext (Web: Script-Tab, Telegram:
  Link, `knoepfe.skript_verweis`); „Show first draft" (`ART_ERSTENTWURF`)
  zeigt auf die Fassung vor der Prüfung (`szene.erstentwurf_fassung`).
  **`zeigen=False`**, weil `szene.schreibe`/`kurzgeschichte.schreibe` ihren
  Text posteten, bevor eine Prüfung laufen konnte: `_lauf` schreibt jetzt
  still, prüft **unter der eigenen Sperre**, zeigt danach
  (`zeige_geprueft_szene`/`_geschichte`) und streamt nicht — der Strom
  zeigte sonst den ungeprüften Entwurf. **Fragen je Objekt:** Geschichte
  A2/A6/A9/A11, Prosaszene B1/A10, Bühnenszene A10/C1 (`fanout.pruefe(...,
  fragen, szenen, mechanik=False)`); „Formregeln" = A10 ab Phase 7
  (`fanout.A10_FORM_AB_PHASE`). **A10 in beiden Richtungen:** bei
  `richtung=parameter` folgt die Planung dem Text (Journal + eine Zeile),
  die Ausnahme vom „Vorschlag" in `fanout.parameterkorrektur` — **nie** für
  `repo.GESCHUETZTE_SZENENFELDER`: Form und Stil setzt die Gruppe (Birk 7.1).
  **Ablauf** (`ueberarbeitung.weiter_6`/`weiter_7`): Phase 6 prüft die Prosa
  aus 5, statt sie neu zu schreiben — erst das Ganze, dann Szene für Szene,
  nach der letzten Abnahme automatisch Phase 7 (die Gruppe hat gedrückt, wie
  am Ende von 5). Phase 7: Formen per Nummer in **einer** Antwort,
  Sprechweisen (`sprechweise.py`), Szene für Szene, zuletzt `starte_schluss`
  (Prüflauf übers Textbuch, dann `stueckpruefung` — nicht mehr beim
  Eintritt; lief sie nie, holt der Wiedereintritt sie nach). **Chat wirkt,
  wo Knöpfe wirken** (Flow-Audit B1/B2): fünf Arten in
  `erkenner.PHASEN_SPEZIFISCHE_ARTEN` plus Spalte `PROFILSCHALTER_DER_ARTEN`,
  nur im **englischen** Prompt; `arten_fuer_schema()` lässt Dortmunds Enum
  bei 27. Während eines Laufs kommt die „still running"-Zeile wie beim Knopf;
  ein „Noted…" aus dem Gesprächszug wird in 6/7 verworfen
  (`ablauf.ist_erfundenes_notiert`). **Gemessen:** Tabelle `prueflauf`, eine
  Zeile je Lauf (`runden`, `auftraege_je_runde`, `zweite_runde_mit_auftraegen`,
  `dauer_ms`), Basis für `RUNDEN_MAX`. **Grenzen:** ohne gültigen Richter
  (gleiches Modell ohne `IT_JUDGE_MODELL`, USA verneint) keine Prüfung, und
  der Betreiberhinweis steht im Hinweis an die Gruppe; ein Rücksprung nach 5
  setzt die Abnahmen aus 6 nicht zurück (offen, Birk). Mehr: „Was bewusst fehlt".

- **Phase 1 hört seit 04.10.2026 laufend mit, wie Phase 4** (Karte
  t_4517d4ad, Birk 15:15: „Phase 1 und 4 laufen einheitlich automatisch").
  Die Hintergrund-Diskussion der Phase 1 speist über `begriffsboard.py` ein
  laufendes Begriffsboard: derselbe Auslöser wie beim Brainstorm der Phase 4
  (`brainstorm.soll_reagieren`, unverändert), eigene Zähler nur über
  `aufnahme`-Zeilen mit `diskussion = 1`, ein Schema-Aufruf je
  qualifizierendem Segment im eigenen Thread. **Kein `tg`** im Boardlauf —
  strukturell keine Chatzeile beim Mithören, wie beim Brainstorm kein
  Gesprächszug und kein Erkenner-Lauf auf dieser Nachricht. Validiert wird im
  Code (Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`), die
  Tabelle `begriffsboard` nur anhängend. Bei „Discussion done" schlägt der
  Bot die Top 5 mit EINEM Knopf „Take these" vor; `begriffsboard.schreibe_detail`
  füllt `arbeitsstand.begriffe_detail` auf jedem Schreibweg von `begriffe`
  und geht von dort nach Phase 2 und ab Phase 4 in den Prompt
  (`kontext.baue`) sowie in den isolierten `fragen_ki`-Aufruf. **Der
  CoThinker-Tab zeigt seitdem auch Phase 1**: bisher nur in Phase 4 sichtbar
  (die Brainstorm-Karten), rendert `teil/buehne` dort jetzt das
  Begriffsboard, sobald `workshop.diskussion_aktiv()` gilt — im Markup am Attribut
  `#roadmap[data-begriffsboard]`, im Client an `istCoThinkerPhase()`, das den
  bisherigen Early-Return `if (!istPhase4())` in `ladeBuehne` (und die drei
  anderen Phase-4-Weichen) für Phase 1 passieren lässt. Nur funktionales
  Markup (`data-*`, `<details>` für Begründung/Doppelbedeutung), keine
  Gestaltung — wie beim Rest des Boards.

## Die Dramaturgie-Prüfung

Seit dem 06.09.2026, `interview_theater/dramaturgie/`. Sie steht **neben**
`stueckpruefung.py` und ersetzt sie nicht: der Stück-Judge liest das ganze
Textbuch und gibt sechs Noten 1–5, diese Ebene hier gibt **keine Note**,
sondern einzelne Befunde mit Szenennummer, Figur und geprüftem Belegzitat.
Zwei Fragen, zwei Tabellen (`stueckpruefung`, `dramaturgie_befund`), zwei
Knöpfe unter der Abschlussleiste in Phase 7. Fachliche Grundlage:
`docs/recherche-story-qualitaet-2026-09-06.md`.

**Was mechanisch läuft und was das Modell macht.** `mechanik.py` zählt und
vergleicht — Namensstabilität (`difflib`, Standardbibliothek: „Leyla"/„Layla"),
Geisterfiguren, Besetzungsabgleich gegen `szene_figur`, Erstauftritt-Register,
Tschechow-Kandidaten, Formverteilung gegen die Regeln des Szenen-Prompts und
die Sprechanteile je Figur. Kein Modellaufruf, kein Netz, reine Funktionen.
Das Modell bekommt nur, was sich nicht zählen lässt: ob eine Szene ihre
Wertladung dreht (B1), ob eine Szene kausal an die vorige anschließt (A2), ob
ein Kandidat überhaupt „aufgeladen" war (A6), ob zwei Figuren
auseinanderzuhalten sind (C1). **Vier Fragen, nicht vierzehn** — die vier mit
dem höchsten Ertrag pro Aufruf, in der Reihenfolge aus § 6 der Recherche. Für
ein Stück mit 8 Szenen sind das 18 Aufrufe (8 × B1, 8 × C1, 1 × A2, 1 × A6),
plus höchstens einen Retry je Frage.

**Der Sprecherzeilen-Parser ist der kritische Punkt und deshalb defensiv.**
Er liest die vier Ausgabeformen aus `prompts/formen/` (Dialog mit Inline-Regie
ohne Leerzeichen, `CHOR:`, Rap mit dem Namen allein auf der Zeile, Lied mit
`STROPHE (NAME)`); erkennt er in einer Szene **keine** Sprecherzeile, liefern
alle sprecherabhängigen Checks für diese Szene **gar keinen** Befund. Ohne
diese Regel meldete jede Liedszene ihre ganze Besetzung als stumm — ein
falscher Befund kostet Vertrauen, ein fehlender nur eine Gelegenheit.

**Warum der Richter ein anderes Modell sein muss.** Judges bevorzugen
messbar Texte des eigenen Modells (Self-Enhancement Bias, MT-Bench Q17; G-Eval
zeigt denselben Effekt zugunsten LLM-generierter Texte allgemein, Q19). Also
`IT_JUDGE_MODELL`, Vorgabe ist der jeweils **andere** Anbieterweg: schreiben
die Szenen über Claude, richtet das Infomaniak-Modell — und umgekehrt. Sind
Schreiber und Richter dasselbe Modell, gibt es einen `RichterFehler` mit einem
Satz für die Gruppe und **keinen Lauf**. Keine stille Abwertung: ein Abzug,
den niemand nachrechnen kann, ist schlimmer als eine Fehlermeldung.

**Der Richter fällt unter dieselbe USA-Einwilligung wie der Szenenlauf.** Er
liest den Szenentext, und der Claude-Weg geht über eine amerikanische API —
also verweigert `waehle_richter` einen Claude-Richter, solange
`gruppe.szene_usa_bestaetigt_am` nicht auf „ja" steht. Sonst ginge auf dem
Umweg über die Prüfung in die USA, was die Gruppe fürs Schreiben abgelehnt
hat. Der Ausweg steht in der Meldung: zustimmen, oder `IT_JUDGE_MODELL` auf
ein Schweizer Modell setzen, das nicht die Szenen geschrieben hat.

**Warum der Beleg mechanisch verifiziert wird.** Ein Judge kann jede Note
begründen, auch eine falsche — die Begründung entsteht nach dem Urteil. Das
einzige mechanische Gegenmittel ist die Zitatpflicht: `beleg.py` prüft das
Zitat mit `zitat.pruefe` (dieselbe Funktion wie bei Verdichter, Kernzitaten,
Sprachprofil und Schärfung — **keine zweite, großzügigere Normalisierung**)
gegen genau den Text, der dem Judge vorlag, nicht gegen das ganze Stück. Kein
Treffer → **ein** Retry mit dem Hinweis „dein Zitat kam im Text nicht vor" →
danach `unsicher`, der Score wird **verworfen** (nicht abgewertet), und der
Befund geht ins Log statt an den Schreib-LLM. Das ist die wichtigste einzelne
Maßnahme des Designs.

**Bei C1 vergibt der Judge keinen Score.** Er bekommt die Repliken einer Szene
ohne Namen und ordnet sie zu; die Trefferquote und damit der Score rechnet der
Code aus der Ground Truth. Das Modell erfährt nie, wie gut es war, und kann
sich deshalb nicht selbst benoten. Der Umbauvorschlag wird ebenfalls im Code
gebaut, aus dem Figurenpaar, das am häufigsten verwechselt wurde.

**Warum seriell statt parallel.** Die Recherche empfiehlt Nebenläufigkeit
8–12. Das ist für unseren Betrieb falsch: Infomaniak drosselt Parallelität mit
429/5xx statt mit einer Warteschlange (Falle 8 unten), und
`scripts/pruefe_prompts.py` ruft aus demselben Grund sequenziell auf. Bei
18 Aufrufen je Lauf ist das auch kein Verlust. Backoff steckt in den beiden
vorhandenen Anbieterwegen (`llm.WARTEZEITEN`, `szene_claude.WARTEZEITEN`); ein
einzelner gescheiterter Aufruf bekommt einen Vorfall
(`dramaturgie_aufruf_fehlgeschlagen`) und reißt den Lauf nicht mit.

**Der Bot schlägt vor, er handelt nicht.** Nicht gemittelt (§ 3 der
Recherche): jeder harte mechanische Befund und jeder Judge-Score 0 mit
`schwere ∈ {blocker, hoch}` ergibt genau **einen** Überarbeitungsauftrag,
adressiert an eine Szene, höchstens drei je Szene und Runde, priorisiert nach
Schwere und dann Ebene (Geschichte vor Szene vor Stimme) — sonst überschreibt
der Schreib-LLM sich selbst. Ein Auftrag entsteht nur, wenn das Zitat geprüft
ist und der Vorschlag Szenennummer und Figurennamen nennt („mehr Spannung
erzeugen" ist keine Anweisung). Die Befunde gehen als eine Zeile je Befund in
den Chat, je Auftrag mit dem Knopf „Szene N so überarbeiten"; **erst der
Knopfdruck** löst einen Szenenlauf aus, über denselben Weg wie „Passt, aber
anders". Datenstand ist nicht Absicht.

**Die Rückkopplung: gemessen wird an den Scores, nicht an den Befunden**
(07.09.2026, `bilanz.py` + `schleife.py`). `pruefe()` → `auftraege()` →
umschreiben → `pruefe()` → vergleichen. Der Punkt, an dem das leicht falsch
wird, ist das Erfolgsmaß: **die Zahl der Befunde taugt nicht.** Sie fällt in
drei Fällen, und einer davon ist der gefährliche — wird ein Text schlechter,
findet der Judge für seinen Befund oft kein Belegzitat mehr, weil die Stelle
umgeschrieben wurde; der Befund entfällt, und der Schaden sähe aus wie ein
Erfolg. Verglichen werden deshalb die **Scores je Frage und Szene**
(Tabelle `dramaturgie_bewertung`, gefüllt in `fanout._merke`) — und dort
steht auch die **Zwei**, die als Befund bewusst nicht existiert. Die Adresse
ist die, unter der *gefragt* wurde: A2, A6 und A11 laufen als ein Aufruf über
das Stück und tragen deshalb `szene = NULL`, auch wenn ihre Antwort eine
Nummer nennt. Kein Score ohne bestätigtes Belegzitat — ein verworfener Score
ist keine schlechtere Note, sondern keine, und er fällt aus der Bilanz
heraus, statt als Verschlechterung zu erscheinen.

Drei Abbrüche: keine Aufträge mehr (Regelfall), ein gefallener Score (dann
**bricht die Schleife ab** und schreibt einen Vorfall
`dramaturgie_verschlechterung` — sichtbar heißt nicht „steht in einer Bilanz,
die jemand lesen müsste"), und `schleife.RUNDEN_MAX = 2`
Überarbeitungsrunden als Auffangfall. Der Schreibweg kommt aus der Phase:
Feinschliff = ein `szene.schreibe()` je Auftrag (mit `szene.sperrtext` davor
— `schreibe()` prüft die Sperre selbst nicht, das tut sonst `starte()`),
Prosa-Phase = **ein** Lauf über die ganze Geschichte mit allen Aufträgen als
einer Regie-Notiz. Fehlt der Weg für die Phase, gibt es **keinen
Modellaufruf**, sondern einen Satz, was fehlt: der phasenfremde Pfad läuft
ohne Fehler durch und liefert gemessen schwächere Texte. Und: **die Schleife
hängt an keinem Knopf.** Sie fährt der Betreiber gegen eine Kopie
(`scripts/dramaturgie_pruefen.py --schleife`, der teuerste Schalter des
Repos), was dabei herauskommt, ist ein Vorschlag samt Bilanz. Der Bot
schlägt vor, die Gruppe bestätigt — ein Test hält fest, dass weder
`knoepfe.py` noch `fanout.py` `schleife.schliesse` rufen. **Die eine
Ausnahme, nur in Padua** (03.10.2026): der Prüflauf (`prueflauf.py`) ruft
`schleife.schliesse` im Thread eines Schreiblaufs, bevor die Gruppe den Text
sieht — auch er nie aus einem Knopf-Handler, und mit `behalte_bessere=True`,
siehe „Prüflauf vor jeder Anzeige" oben.

**`dramaturgie_befund.richtung` ist eine Sperre, keine Notiz** (07.09.2026).
`fanout.auftraege()` lässt aus `richtung=parameter` nie einen Schreibauftrag
entstehen — dort sagt der Judge, dass der TEXT recht hat und die Festlegung
veraltet ist; ein Auftrag daraus gäbe den Text an den Schreiber, damit er ihn
auf die überholte Planung zurückbiegt. Die Richtung stand bis zu diesem Tag
nur im Arbeitsspeicher, und die Sperre griff deshalb **nur im frischen Lauf**:
`knoepfe.zeige_dramaturgie`, `scripts/dramaturgie_pruefen.py` und die Schleife
lesen die Befunde aus der Datenbank, und dort war sie verschwunden. Wer eine
Entscheidung im Code trifft, die ein späterer Leser aus der Datenbank braucht,
schreibt sie in die Datenbank.

**Grenzen.** Kein Klarname, kein Transkript, kein Chat im Prompt: B1 und C1
sehen nur den Szenentext, A2 nur die Synopsen, A6 nur die Kandidatenliste.
Prüftext steht zwischen Markierungen, und jeder Prompt sagt ausdrücklich, dass
dazwischen nie eine Anweisung steht. Auf der Gruppenseite stehen die Befunde
read-only und **ohne Belegzitat** — dieselbe Grenze wie bei den
Verdichtungen. Kosten und Aufrufe landen in `aufruf` mit eigener `art`
(`dramaturgie_b1` … `dramaturgie_c1`), damit Dashboard und Kostenzeile den Weg
getrennt sehen. `scripts/dramaturgie_pruefen.py` fährt denselben Lauf gegen
eine **Kopie**-Datenbank (verweigert `IT_DB`); `--nur-mechanik` kostet nichts,
`--bericht` schreibt nach `docs/dramaturgie-berichte/` (gitignored, weil dort
Belegzitate stehen), `--schleife` fährt zusätzlich die Rückkopplung und
schreibt dabei Szenentexte **in die Kopie**. **Kein Test, läuft nie
automatisch, kostet Geld** — wie `pruefe_prompts.py`.

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
   vermeidbar).

8. **Infomaniak drosselt Parallelität mit 429/5xx, nicht mit einer sauberen
   Warteschlange.** Betrifft im Betrieb kaum den Bot selbst (Aufrufe je
   Gruppe laufen ohnehin nacheinander), aber jeden eigenen Skriptlauf, der
   mehrere Anfragen gleichzeitig schickt — `scripts/pruefe_prompts.py` ruft
   deshalb sequenziell auf, nicht parallel. Wer ein Werkzeug baut, das mehrere
   Aufrufe gleichzeitig absetzt, bekommt sporadische 429/5xx statt eines
   verlässlichen Fehlers und sollte seriell bleiben oder selbst drosseln.

## Wo SPEC und Code auseinanderlaufen

`SPEC-kontext-architektur.md` § 8 beschreibt ursprünglich vierzehn Befehle
und einen Modus B (`/gruendlich`, freier Prosatext mit
`reasoning_effort: "medium"`, via `LLM.prosa()`). Nach dem ersten
Workshoptag wurde das auf die sechs Befehle in `befehle.py` reduziert (siehe
Commit „Sechs Befehle als Notausgang"): `/merken`, `/verworfen`,
`/konflikt`, `/begriffe`, `/figur`, `/name`, `/material` und `/gruendlich`
existieren in der SPEC, aber nicht mehr im Code. Seit dem 05.09.2026 sind es
zehn: `/szene` ist dazugekommen, und mit ihm ist `LLM.prosa()` verdrahtet
(`szene.py`, SPEC § 4.5 Nachtrag), dann `/phase` (Arbeitsphase zeigen oder
umschalten), `/figur <Name> entfernen` (weiches Löschen, NACHTRAG N3) und
`/auswerten [N]` (ein Interview unter `aufnahme.MINDEST_WOERTER` doch noch
verdichten, N2) —
`/figur` legt bewusst **nichts** an, das macht weiterhin der Erkenner im
Gespräch. Wer an diesen Stellen weiterbaut, sollte sich auf `befehle.py`
verlassen, nicht auf die SPEC-Tabelle.

`befehle.behandle()` nimmt seit `/szene` ein optionales `klm` entgegen. Die
alte strukturelle Garantie („behandle bekommt kein LLM-Objekt, also kann ein
Befehl nicht am Modell scheitern") ist damit eine Zusage geworden, die der
Code weiterhin einhält: **kein Befehl ruft synchron ein Modell** — `/szene`,
`/fertig` und `/auswerten` geben sofort an einen eigenen Thread ab. Wer einen
elften Befehl anhängt, halte sich daran.

`einstellungen.py` liest zusätzlich `IT_MODELL_ERKENNER` (Vorgabewert
`google/gemma-4-31B-it`) — diese Variable fehlt noch in
`docs/betrieb-env.beispiel`.

## Starten und testen

**Regelweg: systemd-User-Units, nie Handstart.** Zwei Handstarts desselben
Bots = beide bekommen `409 Conflict` bei `getUpdates`, keiner empfaengt —
passiert am 04.09.2026 zweimal. Unit-Vorlage `docs/interview-theater@.service`
(nach `~/.config/systemd/user/`, `daemon-reload`), Start ueber
`scripts/betrieb-start.sh <gruppe>` (waehlt Python 3.11 aus `.venv`/uv —
das System-Python 3.9 kann `X | None` nicht importieren).

```
systemctl --user enable --now interview-theater@gruppe1.service   # je Gruppe
systemctl --user restart interview-theater@gruppe1.service        # Neustart
tail -f betrieb/gruppe1.log                                 # Log je Gruppe
```

**Verhalten aendern ohne Neustart** (`interview_theater/anweisungen.py`): alle
Prompts unter `interview_theater/prompts/` werden bei jedem Aufruf per mtime
geprueft und heiss nachgeladen -- auch `szene.md` und die Negativliste
`theater-tells.md`, die im Workshop waechst und beim naechsten Szenenauftrag
wirkt. Fuer spontane Regieanweisungen gibt es
`betrieb/zusatz.md` (alle Bots) und `betrieb/zusatz.<IT_BOT_NAME>.md` (ein
Bot); der Inhalt wird ans Ende der Gespraechs-Systemanweisung gehaengt,
Loeschen der Datei nimmt ihn zurueck. Erkenner/Journal/Verdichter bekommen
bewusst keinen Zusatz (gemessene Few-Shot-Prompts). Bedienung aus Hermes:
Skill `interview-theater-live-ops`.

Umgebungsvariablen: siehe `docs/betrieb-env.beispiel` zum Kopieren nach
`betrieb/<name>.env`. Handstart nur zum Debuggen, und nur wenn die Unit
gestoppt ist:

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m interview_theater.bot
```

- `pytest` — die Testsuite unter `tests/`, läuft ohne Netzzugriff (Attrappen
  statt echter Dienste). Enthält die Korpus-Validierung und die
  Bewertungsfunktionen aus `scripts/pruefe_prompts.py`, nicht den Lauf gegen
  das Modell.
- `python -m scripts.rauchtest [pfad-zu-audio.ogg]` — **kein Test, läuft nie
  automatisch, kostet Geld.** Ein echter Aufruf gegen Sprachmodell und
  optional Whisper, zur Kalibrierung der Token-Schätzung und als
  Erreichbarkeitsprüfung vor einem Einsatz.
- `python scripts/chat_leeren.py <chat_id> [--ja]` — setzt eine Gruppe auf
  null: löscht alle dem Bot bekannten Nachrichten aus dem Telegram-Chat
  (`deleteMessages`, Bot muss Admin sein; Nachrichten von vor seinem
  Eintritt und Telegram-Servicezeilen bleiben) und danach DB + Audio wie
  `loeschen.py`. Für den Workshop-Start nach einem Probelauf. Env der
  jeweiligen Gruppe laden — das Skript prüft, dass der Bot zur Gruppe passt.
- `python -m scripts.chat_leeren_blind <chat_id> [--zurueck 300]` — wenn die
  DB die Nachrichten nicht mehr kennt (nach `loeschen.py` oder nach einem
  Simulationslauf mit `--echte-db`): Marker senden, dann die letzten 300
  IDs rückwärts löschen. Telegram-Grenze: nur 48 h, nur als Admin.
- `python -m scripts.szenen_vergleich --nur opus,kimi,mistral,apertus` —
  eine Szene, gleicher Prompt, vier Modelle; Ausgabe als Markdown mit dem
  Prompt als Anhang. Grundlage der Entscheidung für Opus (05.09.).
- `python -m scripts.interviews_uebernehmen <ziel> <quelle> [<quelle> …] [--ja]`
  — hebt die Gruppengrenze für **Material** auf (06.09.2026, Ende Tag 2: nur
  noch eine Gruppe arbeitet weiter und soll alle Interviews sehen). Kopiert je
  Quellinterview Kopf, Teile, Transkripte, Verdichtung und
  `verdichtung_thema` (inkl. `zitat_geprueft`) sowie die Audiodateien in die
  Zielgruppe; **kein Modellaufruf**, die Quellen bleiben unverändert.
  Arbeitsstand, Figuren, Szenen, Knöpfe, Nachrichten, Journal und Kernzitate
  wandern bewusst **nicht** — das ist die Arbeit der Quellgruppe an ihrem
  Material, nicht das Material. `zum_kernthema_am` wird auf NULL gesetzt: was
  zur Kernfrage passt, entscheidet die Zielgruppe selbst. Die Nummerierung
  läuft weiter, weil `kontext.interviewbezeichnung` nach `id` zählt und neue
  Zeilen höhere ids bekommen; `name` wird beim Import auf „Interview N"
  gesetzt und nie aus der Quelle übernommen (dort kann ein Klarname stehen).
  Idempotent über `aufnahme.uebernommen_von` („`<quell_chat_id>:<alte_id>`",
  additiv migriert), alles in einer Transaktion, ohne `--ja` reiner
  Trockenlauf mit Zählung. Verweigert den Dienst, solange in Ziel oder Quelle
  eine Aufnahme läuft oder der Interviewmodus an ist. Mit `--ja` legt es
  selbst ein DB-Backup an, schreibt einen Journaleintrag in die Zielgruppe und
  eine Zeile in den Zielchat. Env der **Ziel**gruppe laden — die Quellen
  dürfen anderen Bots gehören, sie liegen in derselben Datenbank.
- `python scripts/loeschen.py <chat_id>` — der Löschweg: entfernt alle
  Datenbankzeilen einer Gruppe und ihr Audioverzeichnis, fragt vorher
  interaktiv nach Bestätigung. Es gibt bewusst keinen Löschbefehl im Chat.

`scripts/simulation_abdeckung.py` erzeugt die Abdeckungstabelle der
Simulation aus dem Code (Phasen aus `phasen.PHASEN`, Schritte aus den drei
`skript`-Listen, Pruefung aus `schritt.fertig.__name__`) und prueft jede
Behauptung der Simulations-Doku dagegen — kein Modell, kein Netz, keine
Kosten.

**Simulation** (`simulation/`, `scripts/simulation.py`, Stand 06.09.2026 nachts):
simulierte Gruppen spielen den Bot durch alle **Phasen** — mit Inline-Knöpfen
(`attrappe` merkt die Leisten, die Stimme drückt per Knopftext oder schreibt
frei) und dem Schrittplan `skript.SCHRITTE_TAG2`. Stimmen: drei erfundene Sets
plus **PII-freie Personas aus Tag 1** (`simulation/tag1.py`,
`simulation/stimmen/tag1-gruppe{1,2,3}.md`, `regie.md`): nur Begriffe/Fragen der
echten Gruppen, Themen-Stichworte und Verhaltensaggregate, nie Transkripte oder
Klarnamen — `tests/test_simulation_tag1.py` prüft das gegen die echte DB, wenn
sie da ist. Der Richter (Claude Opus über den Proxy) bewertet zusätzlich:
Nachrichten bis zum Speichern, Fragen je Bot-Nachricht, Wiederholungsquote,
„Bot redet parallel zum Auftrag", Knöpfe angeboten→gedrückt, Phasenwechsel
proaktiv, Form je Szene bestätigt, Exposition der Szene 1. Berichte
`simulation/laeufe/2026-09-06-*.md` + Sammelbericht. Läuft gegen ein anderes
Modell als der Bot. **Kein Test, kein Ersatz für `pytest` oder
`pruefe_prompts.py`**; Doku `simulation/README.md`.

**`python -m simulation.browser_lauf`** (Padua-UX-Simulation, 03.10.2026)
ist ein anderer Weg: statt den Bot-Code direkt anzufahren, bedient eine
Opus-Persona die echte Webseite in einem echten, headless Chromium
(Playwright) und sammelt dabei Screenshots, mechanische UX-Zaehler und ein
Opus-Urteil je Phase gegen `simulation/ux_rubrik.md` — eigene Module
(`simulation/browser_*.py`), eigene Doku (`simulation/README.md`, Abschnitt
„Der Browserlauf").

## Weboberfläche

Ein einziger Prozess für alle Gruppen, neben den Bots:

```
IT_DB=betrieb/soap.db python -m interview_theater.web
```

Unit-Vorlage `docs/interview-theater-web.service` (nach `~/.config/systemd/user/`,
`daemon-reload`, dann `systemctl --user enable --now interview-theater-web`), Log
nach `betrieb/web.log`.

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `IT_DB` | — (Pflicht) | dieselbe SQLite wie die Bots, **read-only** geöffnet |
| `IT_WEB_BIND` | `127.0.0.1:8010` | im Betrieb `100.75.24.33:8010` (Tailnet) |
| `IT_WEB_PREFIX` | `/theatersoap` | Präfix, unter dem nginx den Server durchreicht |
| `IT_WEB_URL` | `https://lab.artesmobiles.art/theatersoap` | nur für `scripts/web_links.py` |

Routen: `/` (Team-Dashboard, projiziert, alle Gruppen), `/g/<token>`
(Leseansicht einer Gruppe, Handy), `/gesund` (Health-Check, antwortet ohne
Datenbankzugriff). Jede Route greift auch mit vorangestelltem
`IT_WEB_PREFIX`, weil erst die nginx-Konfiguration entscheidet, ob das
Präfix beim Server ankommt.

`python scripts/web_links.py` gibt aus, welche Gruppe welchen Link bekommt.
Das Token steht in `gruppe.web_token`, erzeugt wird es beim ersten Kontakt
vom Bot (`repo.stelle_web_token_sicher`, aufgerufen aus `sichere_gruppe`) —
der Webserver kann es nicht anlegen, er liest read-only.

**Drei Grenzen, die nicht verhandelbar sind**, weil beide Seiten ohne Login
erreichbar sind und das Dashboard projiziert wird:

- kein Nachrichtentext und keine Transkripte auf dem Dashboard,
- kein Volltranskript auf der Gruppenseite (dafür gibt es `/wortlaut` im Chat),
- kein Belegzitat ohne `zitat_geprueft = 1`.

`IT_WEB_BIND` lehnt `0.0.0.0` mit einem Fehler ab: ein Tippfehler in einer
Env-Datei soll die Interviews nicht ins offene Netz stellen.

### Die Gruppenseite ändert Parameter (05.09.2026 abends)

Bis zu diesem Abend war beides read-only, mit der Begründung „sonst laufen
zwei Schreibwege gegeneinander" (N1). Die Begründung gilt weiter — deshalb
gibt es **keinen zweiten Schreibweg, sondern einen zweiten Auslöser für den
vorhandenen**: `web_schreiben.py` ruft ausschließlich `repo`-Funktionen,
dieselben wie `knoepfe._speichere` und `erkenner.wende_an`. In `web_daten.py`
kommt kein einziger Schreibpfad dazu; es bleibt read-only (`mode=ro`), und nur
der POST-Handler öffnet eine schreibende Verbindung (`db.verbinde` — WAL und
`busy_timeout`, wie `scripts/begruessen.py` aus einem fremden Prozess). Zwei
Tests halten das fest: kein `SELECT`/`INSERT`/`UPDATE` in `web_schreiben.py`,
kein Schreibpfad in `web_daten.py`. Änderbar ist **genau** `web_schreiben.FELDER`
und nichts sonst: Setting (`rahmen`), Geschichte, je Figur
Name/Beschreibung/Interview/Entfernen/Hinzufügen und je Szene Titel, Form,
Ort, Zeit, Anlass, was passiert, was anders, Ton und die Besetzung — also
genau das, was die Gruppe hier **fertig entscheiden** kann. Setting und
Geschichte sind dabei **unabhängig voneinander**: ein neues Setting ändert die
Geschichte nicht und stößt auch nichts an, was sie später ändern würde (Birk,
06.09.2026 10:25 — kein Auftragsweg vom Web an den Bot, keine automatische
Geschichte). Nicht änderbar: **nie Material** (Aufnahmen, Transkripte,
Verdichtungen, Belegzitate), nie der Szenen-Volltext, nie das Journal, nie die
USA-Einwilligung, nie der Sprachprofil-Text, nie die Schärfungs-Zuordnungen.
**Was der Chat führt** (`web_schreiben.FUEHRT_DER_CHAT`): Phase, Begriffe,
Fragen und die drei Leitfaden-Felder. Sie stehen auf der Seite an ihrem Platz,
aber als Anzeige — sie entstehen im Gespräch über Knöpfe und Ping-Pong, oft mit
einem Modellaufruf dahinter, und der Webserver hat keinen Modellklienten; sie
hier umtippen zu lassen hieße, denselben Wert auf zwei Wegen zu pflegen, von
denen einer die halbe Kette auslässt. Von den drei Leitfaden-Feldern steht
nicht einmal das Rohfeld da, sondern der **gebaute Leitfaden**
(`leitfaden.aus_feldern`, dieselbe Funktion wie im Chat): das, was die Gruppe
im Interview in der Hand hält. Seit dem Phasen-Umbau fehlen außerdem
**Kernthema, Kernthema-Richtung und Kernfrage**: sie sind keine Station mehr,
`geschichte` hat ihre Rolle übernommen; gesetzte Werte bleiben sichtbar
(`web_schreiben.NUR_ANZEIGE`, nur wenn gesetzt), änderbar sind sie nicht.
Ebenfalls nur Anzeige: der Formvorschlag je Szene (`szene.form_vorschlag` —
bestätigt ist allein `form`, und wer hier wählt, bestätigt gerade selbst) und
die Schärfungen aus Phase 6, als Zähler mit Kurzformen und **ohne Belegzitat**.
Die Dropdowns holen ihre Vorschläge aus der Tabelle `knopf`, zeigen also nur,
was im Chat ohnehin schon zur Auswahl stand. Jede Änderung hängt einen Journaleintrag an, `art
'entschieden'`, **`quelle 'web'`**, mit altem und neuem Wert (120 Zeichen je
Seite) — das ist der einzige Weg, auf dem der Gesprächs-Bot davon erfährt, denn
der Webserver spricht nicht mit Telegram: er liest das Journal bei jedem Zug
frisch (`kontext._baue_journal`). Wie in einem Knopf-Handler fällt hier **kein
Modellaufruf** an; wechselt eine Figur ihr Interview, wird deshalb das alte
Sprachprofil geleert und `geprueft_am` zurückgenommen, `knoepfe.stelle_figur_vor`
holt es im nächsten Zug im eigenen Thread nach. Das **Dashboard bleibt
vollständig read-only** und nimmt gar kein POST an — es hängt am Beamer. CSRF:
das Token in der URL ist das Geheimnis, dazu ein Formular-Nonce aus Token und
Stundenfenster (abgeleitet, nicht gewürfelt — ein zufälliger Nonce ließe das
sanfte Nachladen die Seite alle zehn Sekunden austauschen und risse jedes
offene Eingabefeld mit); aus demselben Grund lädt die Seite gar nicht erst
nach, solange der Fokus in einem Feld steht oder eines ungespeichert geändert
ist. Ein Neustart der Unit `interview-theater-web.service` ist nötig, die Bots
nicht.

### Prompt geändert? → Korpus laufen lassen

Die fünf Prompts werden heiß nachgeladen, also ändert sie jemand **während**
des Workshops. Der Regressionskorpus unter `korpus/` ist das Gegenmittel gegen
den Blindflug: 150 Absichtserkenner-Fälle (davon 53 Negativfälle; darunter
11 aus einer laufenden Aufnahme — `aufnahme` statt `nachrichten`, N1 —, und
20 mit `zustimmung: true` markiert, N7; Stand 30.09.2026, alle `art`-Werte
mindestens zweimal, `szene_planen` mit Szenenbezug), 22 Journal-Abschnitte
(davon 11 leere), 7 erfundene Interviewtranskripte — darunter einer, dessen
Sollwert **null** Kernthemen sind (der Live-Fall aus dem Probelauf, N2) —
und 5 Sprachprofil-Fälle (T3, eine je Sprechweise: kurze Sätze mit
Selbstkorrektur, Code-Switching, „man"-Distanz, Reihungen, Rückfragen), alle
mit Sollwert.

(Stand 30.09.2026 nachgemessen — die Zahlen davor waren seit dem 05.09. nicht
mitgewachsen. Wer Fälle ergänzt, zählt mit
`python3.11 -c "import json; f=[json.loads(l) for l in open('korpus/erkenner.jsonl') if l.strip()]; print(len(f), sum(1 for x in f if not x['erwartet']))"`
nach, statt zu schätzen.)

Seit dem 30.09.2026 dazu `szene_kuerzen` mit `sk01`/`sk02` (positiv, beide
`zustimmung: true`) und `sk03`–`sk05` (negativ) — die Art liegt direkt neben
n20, n27 und fl04, und
`tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle` hält deren
Sollwerte fest.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner             # nach einer Änderung an erkenner.md
python -m scripts.pruefe_prompts alle --bericht       # vollständig, mit Markdown-Bericht
python -m scripts.pruefe_prompts erkenner --nur e18-verworfen-kindheitsfragen
python -m scripts.pruefe_prompts erkenner --modell <anderes>   # Modellvergleich
```

**Kein Test, läuft nie automatisch, kostet Rappen** — wie `rauchtest.py`. Rund
70 Aufrufe für `alle`, sequenziell (Infomaniak liefert bei Parallelität
429/5xx). Der Lauf schreibt seine `aufruf`- und `vorfall`-Zeilen in eine
Wegwerf-Datenbank, nie in `IT_DB`.

> **Die Regel: eine Änderung am Erkenner-Prompt gilt nur, wenn FP = 0 bleibt.**
> Null Falsch-Positive bei 25 Negativfällen ist die Zahl, die den Erkenner
> qualifiziert und die acht nicht gebauten Befehle begründet hat (SPEC § 4.3a,
> § 8.1). Genau das ist deshalb der Exit-Code: das Skript endet mit 1, sobald
> der Erkenner auch nur ein Falsch-Positiv liefert.
>
> **Was FP heißt, hat sich am 05.09.2026 gedreht (N7) — die Zahl nicht.** Ein
> Falsch-Positiv ist jetzt: ein Eintrag, dem im Abschnitt **kein konkreter
> Vorschlag und keine Zustimmung** vorausgeht. Ein Eintrag *nach* einer
> Zustimmung ist keiner mehr, auch wenn sie beiläufig war („passt", „nehmen
> wir", „das können wir so fix machen"). Grund: seit es weiches Löschen und
> `transkript_korrigieren` gibt, ist ein falscher Eintrag billig — ein Satz der
> Gruppe nimmt ihn zurück —, ein fehlender teuer: die Website bleibt leer, der
> Bot weiß nichts davon, und die Gruppe muss alles noch einmal sagen. Im
> Probelauf stimmte sie dreimal zu (Fragen, Kernthema, drei Figuren), und
> dreimal blieb der Arbeitsstand leer. **Das Prüfskript rechnet dafür nicht
> anders — es sind die Sollwerte im Korpus, die sich gedreht haben.** Daneben
> steht seither eine zweite Kennzahl (nicht im Exit-Code): **Falsch-Negative in
> Zustimmungsfällen**, Korpusfeld `zustimmung`, soll ebenfalls 0.
>
> Zwei Arten bleiben auf „im Zweifel kein Eintrag" kalibriert:
> `szene_schreiben` (kostet zwei Minuten Wartezeit und eine unbestellte
> Nachricht) und `entfernen` (nimmt etwas weg).

Berichte landen in `korpus/berichte/` und sind **gitignored**: sie enthalten
vollständige Modellantworten. Der Korpus selbst ist frei erfunden und gehört
ins Repository.

**Die Zahlen des Laengen-Rhythmus und des Sprachpasses sind kein Prompt.**
Sie stehen in `workshop/padua-2026/profil.toml` (`[laengen]`,
`[laengen.rahmen]`, `[sprachpass]`). Eine Aenderung dort braucht **keinen**
Korpuslauf und **keinen** Neustart des Webdienstes, aber einen Neustart des
Bots: die TOML wird nur beim Start gelesen (siehe "Workshop-Profil").

### Simulation: ein ganzer Workshop gegen die echten Modelle

Der Korpus misst einzelne Prompts an einzelnen Fällen. Was er **nicht** misst,
ist der Zusammenhang: ob eine Gruppe mit diesem Bot von einer Begriffsliste zu
einem Szenentext kommt, ob Zustimmungen ankommen, ob der Bot behauptet, etwas
notiert zu haben, das nirgends steht. Genau dafür gibt es
`scripts/simulation.py` (Details in [simulation/README.md](simulation/README.md)).

Simulierte Teilnehmerinnen arbeiten sich durch die Schritte einer
Skriptliste. `skript.SCHRITTE` ist der Ablauf vom 05.09.2026 und die
Messlatte der damaligen Verlaufszeilen (zehn Schritte, keine Phasenwechsel);
`skript.SCHRITTE_TAG2` faehrt die heutigen **sieben** Phasen, und seit dem
30.09.2026 waehlt der Schalter `--skript tag2` es auch fuer die erfundenen
Sets 1–3 — vorher war es an `--set tag1-*` gebunden, und damit fuhr kein
erfundenes Set die Phasen 4 bis 7 ueberhaupt an. Gefahren wird **derselbe Codepfad wie im Betrieb**
(`bot.verarbeite_update`, `bot._zug_und_erkenner`), nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`. Der
Umweg über Telegram ist gar nicht möglich: Telegram liefert Bot-Nachrichten
nie an andere Bots (Bot-FAQ). Interviews kommen als Text
(`aufnahme.importiere_text`, § 10.5), kein Whisper.

**Zwei Modelle, eine Trennlinie.** Alles, was der Bot tut, läuft über
Infomaniak — er ist der Prüfling. Alles, was Simulation ist (die Stimmen, der
Richter, die einmalige Erzeugung der fünfzehn Interviewdatensätze), läuft über
**Claude Opus** an einem lokalen Proxy (`simulation/claude.py`,
`IT_SIM_URL`/`IT_SIM_MODELL`, Anthropic-Messages-Format, kein
Authorization-Header). Ohne diese Trennung würde der Prüfling seine eigenen
Teilnehmerinnen spielen und sich anschließend selbst benoten. Die
Simulationsseite läuft über ein Abonnement und kostet je Aufruf nichts — die
Kostenzeile im Bericht ist deshalb genau das, was ein Workshoptag zahlen
würde.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.simulation --set 1 --seed 7 --bericht
python -m scripts.simulation --mix 1,2,3 --seed 3
python -m scripts.simulation --set 1 --seed 1 --ohne-szene   # ohne Reasoning-Lauf
python -m scripts.simulation --set birk --bericht            # echtes Material, ~10 min
python -m scripts.simulation --alle                          # Sets 1-3 und birk
```

**Die Stimmen sind Personen, keine Sprachstile** (Gülten 58, Dilan 24,
Halyna 41 — Steckbriefe in `simulation/stimmen/*.md`, je mit einem eigenen
Ziel im Workshop). Wer dem Computer am wenigsten traut, schreibt am
seltensten; der `--seed` variiert nur, wer wann spricht.

**`--set birk` ist die Messlatte:** das einzige Set auf echten Daten (Birks
Testinterview vom 04.09., eine Stimme, kalibriert auf seinen echten
Chatverlauf). Gemessen wird die **Navigation**, nicht der Text — der Bericht
stellt neben jede Zahl die aus dem echten Chat. Der Lauf schreibt drei Szenen
in drei Formen (Dialog, Lied, Rap) und verbietet deshalb `--ohne-szene`. Das
Material liegt außerhalb des Repositories (`IT_SIM_BIRK`).

**Was sie misst.** Mechanisch, ohne Modell: erreichte Phase, Vollständigkeit
des Arbeitsstands, Anteil der Zustimmungen, nach denen wirklich eine
Notiert-Zeile kam (die Kennzahl aus N7), Verdichtungen und geprüfte
Belegzitate, Echo (`ablauf.ist_echo`), Rückfragen vor dem Szenenauftrag,
**behauptete Schreibvorgänge** (Bot sagt „notiert", ohne dass der Erkenner
etwas geschrieben hat — Soll 0), Namensanrede, Medianlänge der Bot-Antworten
(Soll < 700 Zeichen), Kosten und Dauer. Dazu bewertet ein Richter (Opus)
jeden Abschnitt mit 0/1/2 auf vier Kriterien und jeden Szenentext auf drei
weitere.

**Und die zwei Hintergrundwege, die entscheiden, was der Bot weiß.** Das
**Journal**: Einträge je Art, wie viele davon der Richter im Chat
wiederfindet, welche Vorschläge fehlen, Doppeleinträge — und ob der Extraktor
überhaupt lief (er läuft nur bei Verdrängung; sonst steht „Journal nicht
ausgelöst" statt einer Null, `--fenster-klein` provoziert sie). Der
**Kontextaufbau**: `kontext.baue(..., protokoll=list)` schreibt je Prompt mit,
welcher Block mit wie vielen Token drin stand; der Bericht zeigt die
Verteilung, die Prompts über `ZIEL`, die mit Kürzung — und bei den fünf
schwächsten Antworten urteilt der Richter am Block-Umriss, ob dem Bot
Information gefehlt hat, die in der DB stand. Dazu ein Skript-Schritt
**Zitatabfragen** mit der mechanischen Kennzahl `zitat_erfunden` (Soll 0).

Dazu seit dem 30.09.2026 die zwei Kennzahlen der Gegenpruefung, beide
mechanisch: **`festlegungsproben_erhalten`** (Soll: alle — von drei
Pruefsaetzen, die in kein Arbeitsstandfeld passen, muss jeder dauerhaft
liegen; das Journal zaehlt dabei **nicht**, es wird auf acht Zeilen gekappt)
und **`szenenfolge_nach_richtung`** (Soll 0 — nach einer gedrueckten
Geschichte-Richtung darf kein frischer Szenenfolge-Vorschlag laufen, er
ueberschreibt die Titel der Gruppe und kostet 110 s; in den Laeufen vom
30.09.2026 konnte sie noch nie anschlagen, weil die Richtungswahl in keinem
Lauf erreicht wurde). Beide sind entstanden, weil die Simulation die zwei
belegten Dortmunder Fehler vom 06.09.2026 vorher nicht benennen konnte; was
sie heute findet und was nicht, steht in
`docs/simulation-gegenpruefung-2026-09-30.md`.
`simulation/mutation.py` baut sie auf Knopfdruck wieder ein
(`--mutation`) — per Monkey-Patch aus `simulation/` heraus, kein
Produktivcode und keine Weiche darin; `tests/test_simulation_mutation.py`
haelt fest, dass die Mutation den Fehler wirklich erzeugt, und muss vor jedem
bezahlten Lauf gruen sein.

**Kein Test, läuft nie automatisch, kostet Geld** — wie `pruefe_prompts.py`
und `rauchtest.py`, nur eine Größenordnung mehr: ein voller Lauf sind einige
hundert Aufrufe, grob 0,20–0,60 CHF für den Bot (die Stimmen und der Richter
laufen über das Abonnement und kosten nichts), dazu ein Szenenlauf mit
Reasoning (2–4 Minuten, der teuerste Einzelposten — `--ohne-szene` spart
ihn). Sequenziell; bei 429 wartet das Skript und wiederholt, wie
`pruefe_prompts`.

> **Die Regel: nach jeder Prompt-Änderung ein Lauf mit `--set` und einer mit
> `--mix`.** Der erste hält den Themenkreis fest und macht zwei Läufe
> vergleichbar; der zweite mischt drei Themenkreise und zeigt, was nur an
> einem Set hing. Beide mit demselben Seed wie beim letzten Mal, sonst
> vergleicht man Besetzungen statt Prompts.

Transkript (`simulation/laeufe/`) und Bericht (`simulation/berichte/`) sind
**gitignored** — sie enthalten vollständige Modellantworten. Die eine
Ausnahme ist `simulation/berichte/verlauf.jsonl`: eine Zeile je Lauf mit allen
Kennzahlen und dem git-HEAD, der Vergleichsmaßstab zwischen zwei
Prompt-Ständen. Die fünfzehn Interviewtranskripte unter
`simulation/interviews/` sind frei erfunden und gehören ins Repository —
geschrieben hat sie einmal `simulation/erzeuge_interviews.py` mit Opus, das
**Ergebnis** ist das Artefakt, nicht das Skript.

Der Simulator ist **datengetrieben** gebaut: Phasen aus `phasen.PHASEN`,
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort „Notiert:"
aus `erkenner.baue_meldung`. Ein Umbau an Phasen oder Feldern soll ihn nicht
mitreißen — wer trotzdem etwas anpassen muss, findet die Stellen in
`simulation/skript.py`.

Beim Erweitern: `wert` im Erkenner-Korpus ist der **Kern** der Sache
(`"Meryem"`, `"Mutter gegen Tochter"`), nicht der erwartete Wortlaut —
verglichen wird als Teilstring in beide Richtungen, ein leerer `wert` prüft
allein die `art`. `erwartet[].text` im Journal-Korpus ist ein
**Muss-Stichwort-Set**, mit `|` getrennt (`"sechs|fragen"`), ebenfalls kein
Wortlaut. `tests/test_korpus.py` prüft Form und Mindestbesetzung mit, ohne
Netz.

## Was bewusst fehlt

- **Phase 6 ist EINE Kurzgeschichte, nicht fünf Szenenläufe** (06.09.2026,
  Birk 11:50, `kurzgeschichte.py`). Ein Opus-Lauf schreibt aus Setting,
  Figuren (mit `figur.sprachstil`) und der gewählten Geschichte eine
  zusammenhängende Kurzgeschichte. Danach werden die Abschnitte zu Szenen —
  `nummer`, `titel` = Überschrift, `prosa` = Abschnittstext, `was_passiert`
  aus der Pflichtzeile `Zusammenfassung:`, `ort`/`zeit`/`anlass` aus dem
  Setting (`szene.rahmenfelder`), **`form` bleibt NULL** (die entscheidet
  der Feinschliff). Die bestehende Szenenfolge wird dabei **abgeglichen, nicht
  ersetzt** (`repo.gleiche_szenenfolge_ab`: gleiche Nummer → aktualisieren,
  fehlende → ergänzen, überzählige → stehen lassen), das Journal hält die
  Herkunft fest. Keine Herkules-Zahlen in `formen/prosa.md`.
  **Wie viele Abschnitte, entscheidet die Szenenfolge** (Birk, 02.10.2026,
  Karte P2-Fix): steht eine, bindet ihre Zahl — ein Abschnitt je geplanter
  Szene, in deren Reihenfolge. Genannt wird sie im **Auftrag**
  (`kurzgeschichte.abschnittszahl` → `_ZEILE_ABSCHNITTE`); trägt der
  Nutzertext schon einen Längen-Block, nennt ihn dieser
  (`laengen.SATZ_BINDUNG`) — **nie beide**, ein Fakt hat genau eine Stelle
  im Prompt. Steht **keine** Szenenfolge, wählt das Modell die Zahl selbst
  (typisch 3–7); `kurzgeschichte.ANWEISUNG` formuliert genau diese zwei
  Fälle, weil eine Systemanweisung die Datenlage nicht kennt. Der Grund für
  die Bindung ist der Abgleich oben: bei zu wenigen Abschnitten bleiben
  prosalose Szenen stehen, und Phase 7 verlangt Prosa für **jede** geplante
  Szene (`phasen.voraussetzungen`) — ohne Vorfall und ohne Zeile im Chat.
  **Das ist die bekannte Grenze dieses Wegs** (Befund
  `docs/prompt-audit/2026-10-02-padua-p2/BEFUND.md`): verfehlt das Modell
  die bindende Zahl trotzdem, räumt niemand auf.
  Die Zerlegung selbst hängt an keiner Zahl — ein Test misst das
  (`test_teil4_kurzgeschichte`: vier Überschriften → vier Szenen, sechs →
  sechs; dort ist **keine** Szenenfolge angelegt, also genau der freie Fall).

- **Der Prosa-Lauf startet nur aus einem Knopf, und die USA-Frage steht beim
  Eintritt in Phase 6** (06.09.2026, Birk 12:25). Beim Eintritt kommen
  Einleitung und — einmal je Gruppe, **vor** dem ersten Lauf — die
  USA-Einwilligung als eigene Nachricht mit genau „Ja, US-Modell" / „Nein,
  Schweiz"; erst nach der Antwort steht der Knopf „Geschichte schreiben".
  Vorher kam die Frage mitten aus dem Szenenlauf, wenn die Gruppe schon
  wartete, und der Lauf brach dafür ab. Der Gesprächs-Bot löst **nie** einen
  Lauf aus: eine Antwort mit „Start frei", „ich schreibe die Szene aus",
  „US-Server"/„Schweiz" ohne laufenden Lauf wird verworfen
  (`ablauf.ist_erfundene_systemzeile`, Vorfall
  `gespraech_systemzeile_erfunden`), und `system.md` verbietet die Ansage.

- **Was fehlt, steht neben dem, was dasteht** (06.09.2026,
  `fehlstellen.py`). `/stand` und die Gruppenseite zeigten bis dahin nur den
  gefüllten Arbeitsstand; woran die Gruppe als nächstes arbeiten müsste,
  musste sie sich aus sieben Blöcken mit „noch offen"-Zeilen selbst
  zusammenreimen. Das Register dreht dieselbe Datenlage um und liefert je
  Fehlstelle `bereich`, einen deutschen Satz, `szene`/`figur` wo zutreffend
  und die Phase, in der das dranwäre. **Reine Leseabfrage, kein
  Modellaufruf**, wie `phasen.voraussetzungen` — und geprüft wird genau das,
  woran der Code schon hängt (`phasen.voraussetzungen`,
  `szene.PFLICHTFELDER`, `aufnahme.unausgewertete_interviews`,
  Ebene 2 der Figuren erst ab Phase 5 wie in `knoepfe.ebene2_erlaubt`); eine
  zweite, frei erfundene Wunschliste wäre der erste Stand, der ausschert.
  Ausgespielt wird an genau **zwei bestehenden Orten** — ein Abschnitt in
  `/stand` und einer auf der Gruppenseite —, **nur wenn es Fehlstellen
  gibt** (eine Zeile „nichts fehlt" ist Lärm), höchstens `HOECHSTENS` = 8
  Zeilen. Kein neuer Knopf, keine eigene Bot-Nachricht. Auf der
  Gruppenseite steht der Abschnitt seit dem 03.10.2026 direkt nach dem
  Überblick und **vor** den Formularen des Arbeitsstands (UX-Karte Padua,
  `web.gruppe_koerper`) — vorher kam man am Telefon erst nach rund zwei
  Bildschirmen Formularen dort an. Sortiert wird nach
  Arbeits-, nicht nach Phasenreihenfolge: erst die aktuelle Phase, dann der
  Rückstand aus früheren (er blockiert), dann das Kommende. Wie beim
  Leitfaden gibt es **einen Zusammenbau und zwei Aufrufer**: `aus_daten` ist
  rein und kennt nur Dicts, `register` holt sie über `repo`,
  `web_daten.fehlstellen` über die read-only geöffnete Verbindung — der
  Webserver bekommt dadurch keinen `repo`-Pfad.

- **Der Leitfaden hat eine eigene Seite** (06.09.2026, Route
  `/g/<token>/leitfaden`, auch unter `IT_WEB_PREFIX`). Der gebaute Leitfaden
  ging einmal in den Chat und versank — dabei ist genau er das Dokument, das
  eine Sechzehnjährige in der Hand hält, wenn sie eine fremde Person
  anspricht. Die Seite ist **rein lesend**: kein Nachladen, kein POST, kein
  Nonce, und deshalb auch nicht der Rahmen der beiden anderen Seiten
  (`web._seite` hängt das sanfte Nachladen an, das einer Interviewerin mitten
  im Gespräch den Text unter dem Daumen austauschen würde). Groß gesetzt,
  hoher Kontrast, jede Frage in einem eigenen Block, dazu eine
  `@media print`-Regel. **Keine zweite Wahrheit:** Route und Chat-Text stehen
  beide auf `leitfaden.bausteine` — `aus_feldern` setzt daraus den Chattext,
  `web.leitfaden_html` die Handy-Ansicht. `web_daten.leitfaden_nach_token`
  lädt bewusst **nur** den Arbeitsstand und weder Szenen noch Interviews noch
  Journal: was gar nicht geladen wird, kann auch nicht versehentlich
  ausgeliefert werden (Test wie der bestehende in `tests/test_web.py`: kein
  Transkript, kein Nachrichtentext im HTML). Verlinkt an zwei Orten —
  auf der Gruppenseite unter dem Leitfaden-Text (relativ,
  `<token>/leitfaden`, damit es hinter nginx genauso geht) und im Chat unter
  dem Leitfaden selbst (`leitfaden.TEXT_WEBLINK`, **zusätzlich**; der
  bestehende Text bleibt, weil eine Gruppe ohne Netz im Probenraum sonst
  nichts mehr hätte). Steht noch kein Leitfaden, kommt eine ruhige Seite
  („Der Leitfaden entsteht in Phase 2.") statt eines Fehlers. Dafür nehmen
  `leitfaden.sende`/`sende_einmal` seit heute ein optionales `e` entgegen —
  ohne Basis-URL steht die Zeile gar nicht da.

- **Eine Szene bekommt Fassungen, statt überschrieben zu werden**
  (06.09.2026, Tabelle `szenenfassung`). „Neu schreiben" ersetzte bis dahin
  `szene.volltext`; die Gruppe kam nicht zurück, und in der Probe will man
  zwei Fassungen nebeneinander lesen. Jeder **erfolgreiche** Szenenlauf
  (`szene.schreibe` und der Prosalauf in `kurzgeschichte.lege_szenen_an`)
  hängt seine Fassung **zusätzlich** an — `szene.volltext` bleibt genau wie
  bisher die aktuelle Fassung, **kein Aufrufer außerhalb ändert sich**.
  Dasselbe Prinzip wie beim Journal: **nur anhängen, nie ändern, nie
  löschen** — es gibt bewusst kein `aktualisiere_szenenfassung` und kein
  `entfernt_am`. Scheitert das Anhängen, ist die Szene trotzdem geschrieben:
  eine verlorene Historienzeile darf keinen bezahlten Lauf kosten. Migration:
  `db._migriere_erste_szenenfassung` gibt jeder bestehenden Szene mit
  Volltext **eine** Fassung Nummer 1 mit `szene.geaendert_am` als Zeitpunkt —
  idempotent über ein `NOT EXISTS` und ohne eigenen `user_version`-Schritt,
  damit auch eine später importierte Szene noch richtig durchläuft. Gezeigt
  wird sie an zwei Orten, beide **read-only**: die Fassungsleiste je Szene auf
  der Gruppenseite (seit dem 07.09.2026 zum Umschalten, siehe unten) und ein
  Knopf „Fruehere Fassungen" unter einer angesehenen Szene
  (`knoepfe.ART_FASSUNGEN`, deterministisch, Zusage 2 gilt) — der Knopf zeigt
  die **aktuelle** Fassung nicht noch einmal, und beide fehlen ganz, solange
  es nur eine gibt. **Zurücksetzen auf eine frühere
  Fassung ist bewusst nicht gebaut:** das ist eine Entscheidung mit
  Datenwirkung, die Birk erst freigeben muss. `szene.fruehere_fassungen`
  (der `FASSUNGSTRENNER`-Text aus `repo.hebe_fassung_auf`) bleibt daneben
  unverändert stehen — er ist der ältere, gröbere Weg und wird von der neuen
  Tabelle nicht angefasst.

- **Sprechanteile sind gezählt, nicht geschätzt** (06.09.2026,
  `sprecher.py`). Der praktisch wichtigste Befund für eine Laiengruppe stand
  nirgends: eine Spielerin mit vier Zeilen merkt das in der Probe, und dann
  ist der Text geschrieben. Gezählt wird über `szene.volltext` — den
  Theatertext, nicht die Prosafassung —, **kein Modellaufruf**. Die Regel für
  eine Sprecherzeile ist bewusst schlank: am Zeilenanfang ein Name, danach
  ein Doppelpunkt; ein Name gilt, wenn er in der Figurenliste steht oder
  durchgehend großgeschrieben ist. **Die Grenze steht im Docstring und in
  einem Test:** Namen mit Punkt (`FRAU K.:`) oder Komma (`MIRA, LEISE:`)
  werden nicht erkannt — sie mitzunehmen hieße, „Sie sagt: nein." als
  Sprecherzeile zu lesen. Eine Ziffer im Kopf schließt aus, gemessen an den
  echten Opus-Texten unter `docs/prompt-audit/2026-09-06/opus-thinking-texte/`:
  dort stand `SZENE 1: … ca. 10 min` über dem Text und zählte ohne diese
  Regel mit rund 30 Wörtern als Sprecher mit. **Erkennt eine Szene keine
  einzige Sprecherzeile, liefert sie gar nichts** (Lied, Rap und Chor können
  ohne Sprecherkopf geschrieben sein) und zählt auch nicht in den Nenner:
  lieber „1 von 4 Szenen" als eine erfundene Null. Regieanweisungen in runden
  Klammern zählen nicht als gesprochenes Wort. Ausgespielt auf der
  Gruppenseite als Tabelle (Figur, Anteil, Repliken, Szenen) mit einer
  sachlichen Hinweiszeile je Figur unter `SCHWELLE_ANTEIL` = 3 %, und im Chat
  als Zeile „Wer spricht wie viel" im Durchlauf-Knopfmenü
  (`knoepfe.ART_SPRECHANTEILE`, deterministisch, Zusage 2 gilt).
- **Was in kein Feld passt, geht in die Tabelle `festlegung` — nicht ins
  Journal** (06.09.2026, `docs/analyse-phase4-datenverlust-2026-09-06.md`).
  Der Befund: von 42 Festlegungen einer Gruppe in Phase 4 waren **22
  verloren**. Das Schema kennt nur einen festen Satz vorab definierter Slots;
  alles daneben — Gruppenzugehörigkeit einer Figur, ihre Herkunft, „nur eine
  Szene, erste Folge einer Serie", eine Längenvorgabe für Szenentexte —
  landete höchstens als `journal`-Eintrag und fiel nach `JOURNAL_EINTRAEGE`
  = 8 weiteren Zeilen aus dem Prompt, ohne je zurückzukehren.
  **Journal und Festlegung sind Chronik gegen Geltungsanspruch:** das Journal
  hält den *Weg* fest und wird gekappt, eine Festlegung *gilt* und geht
  vollständig mit. Beides in einer Tabelle zu mischen erzwingt genau die
  Kappung, die den Verlust erzeugt hat.
  Drei Schreibwege, einer davon die Rückfallebene: die Erkenner-art
  `festlegung_setzen` (der Regelweg), der versteckte Befehl `/festlegung
  <bereich>: <text>` (weil der Erkenner über ein Modell läuft, und das ist
  am 06.09. mitten in Phase 4 mit HTTP 5xx ausgefallen) und der Knopfweg für
  die Formwahl. Zurückgenommen wird über `entfernen` („Festlegung: …"),
  `/festlegung weg <suchwort>` oder den Löschknopf auf der Gruppenseite —
  **Pflicht, nicht Kür**: ohne ihn erbt die Tabelle den alten Fehler mit den
  veralteten Einträgen.
  Zwei Sperren gegen die **doppelte Wahrheit**: kein `bereich` heißt wie ein
  Arbeitsstandfeld (`repo.FESTLEGUNG_BEREICHE`), und ein Text, der in einem
  gesetzten Feld ohnehin schon steht, wird verworfen (Vorfall
  `festlegung_stand_schon_im_feld`) — das Gegenstück zu
  `erkenner._ist_geschichte` in der anderen Richtung. Im Prompt steht der
  Block **direkt hinter dem Arbeitsstand**, gedeckelt auf 20 Zeilen und 800
  Token, und gekappt wird **die jüngste Zeile zuerst**: anders als beim
  Journal, weil eine frühe Grundfestlegung mehr wiegt als eine späte
  Detailnotiz. Auf der Gruppenseite steht er **aufgeklappt** — das Journal
  war dort auch sichtbar und trotzdem unwirksam.
  **Der Erkenner-Korpuslauf für `festlegung_setzen` steht aus**
  (`korpus/erkenner.jsonl`, Fälle `fl01`–`fl09`).

- **Eine Menüzeile ist keine Geschichte** (06.09.2026, aus derselben
  Analyse). `knoepfe._speichere_geschichte` speicherte eine angetippte
  Auswahlzeile ohne Szenenzeilen als ganze Geschichte — die Absicht trägt
  aber nur, wenn die Zeile eine *Handlungs*richtung beschreibt. Live
  beschrieb sie eine **Formabfolge** über drei Szenen:
  `arbeitsstand.geschichte` trug 113 Zeichen Formwahl statt der 665 Zeichen
  langen, vierteiligen Handlung, und `szene.form` war in allen 15 Zeilen
  NULL. `szenenfolge.formabfolge` erkennt so eine Zeile eng — mindestens
  zwei verschiedene Formen, und strukturell verwendet (an „Szene N"
  gebunden oder als Kette „Chor-Dialog-Rap") —, und die Wahl wird
  **übernommen statt verworfen**: in `szene.form`, wo die Szene existiert,
  sonst als Festlegung im Bereich `form`. `form` und nicht `form_vorschlag`:
  die Regel „die Form ist ein Vorschlag" hält den Vorschlag eines Modells
  aus dem Feld heraus, nicht die Wahl der Gruppe — und hier hat sie
  gedrückt.

- **Eine nachbenannte Figur schluckt ihren Platzhalter** (06.09.2026, aus
  derselben Analyse). `figur` führte 16 Zeilen statt 10, drei Paare mit
  wortgleicher Beschreibung, keine weich gelöscht — und der Schaden war
  nicht die Dublette, sondern ihre Richtung: die im Chat erarbeiteten
  Sprachstile hingen an den **Platzhaltern**, die benannten Figuren hatten
  `sprachstil` NULL, und `szene_figur` verwies gemischt auf beide Seiten.
  `repo.fuehre_figur_zusammen` schmilzt sie zusammen — Stil, Profil, Zitate,
  Interviewzuordnung und Besetzung wandern auf den Namen, aber nur, wo der
  Name dort nichts hat; der Platzhalter bekommt `entfernt_am`.
  **Zusammenführen und nicht löschen**: den Platzhalter samt Stil
  wegzuwerfen wäre derselbe Verlust noch einmal. Ausgelöst wird es nur von
  einem **Platzhalternamen** mit wortgleicher Beschreibung
  (`repo.ist_platzhaltername`) — zwei benannte Figuren werden nie
  verschmolzen.

- **Vor dem Text steht, wer vorkommt** (07.09.2026, `vorspann.py`). Phase 6
  lieferte die Kurzgeschichte ohne Vorspann; die Gruppe — und jeder, der den
  Text später liest — hatte dreizehn Figuren vor sich, ohne zu wissen, wer wer
  ist. Der Vorspann ist ausdrücklich **nicht Teil der Geschichte**, sondern
  steht davor, an **drei Orten mit demselben Inhalt**: im Chat vor den
  Abschnitten (`knoepfe.zeige_kurzgeschichte`), ganz oben auf der Gruppenseite
  (`web._vorspann_html`, read-only) und unter der Überschrift des
  Textbuch-Exports (`szenenfolge.textbuch`).
  **Deterministisch, kein Modellaufruf** — und das ist die Entscheidung, nicht
  eine Sparmaßnahme: der Vorspann darf nichts erfinden, und er soll bei jedem
  Abruf identisch sein. Ein Modell dazwischen hätte drei Fassungen derselben
  Liste erzeugt. Datengetrieben wie `kontext.baue`: jeder Block fällt weg,
  solange seine Daten leer sind.
  Zwei am echten Material gemessene Fallen sind im Code:
  (1) `figur.beschreibung` trägt die **Schärfungsnotizen aus Phase 5 ohne
  Trennzeichen angeklebt** („kaempft mit sich selbst liefert den Hintergrund
  fuer ihre Ablehnung", 371 Zeichen) — es gibt dort kein Satzende, an dem sich
  schneiden ließe, deshalb schneidet `vorspann.erster_satz` an den Formeln
  (`liefert`, `macht deutlich`, `zeigt`, `begruendet`, `erklaert`,
  `verstaerkt`, `unterstreicht`, mit und ohne Umlaut), sonst am Satzende. Die
  Untergrenze `MINDEST_ZEICHEN` (20) ist der Grund, warum „Mira zeigt Härte."
  nicht zu „Mira" wird: die Formeln sind Notiz-Anfänge, keine verbotenen
  Wörter. (2) Figuren mit `entfernt_am IS NOT NULL` gehören nicht hinein — hier
  noch einmal gefiltert, obwohl `repo.figuren` und `web_daten._figuren` es
  schon tun: der Vorspann ist die eine Liste, die ein Außenstehender liest.
- **Zwischen Fassungen wird umgeschaltet, nicht aufgeklappt** (07.09.2026,
  auf der Tabelle `szenenfassung` von oben). Der aufklappbare Block zeigte
  alle früheren Fassungen am Stück; wer die zweite von vier lesen wollte,
  bekam vier Texte hintereinander. Seitdem steht im Szenenblock eine **Leiste
  mit einer Nummer je Fassung** und darunter **genau eine** — die gewählte —,
  dazu ein Link auf die vorige; in der Szenenübersicht steht je Szene der
  Zähler („3 Fassungen") als Weg dorthin. `web._fassungen_html` ersetzt damit
  den früheren Block: der aktuelle Text stünde sonst zweimal auf der Seite,
  einmal als „der Text" und einmal als „Fassung N". Ab **zwei** Fassungen —
  bei einer gibt es nichts umzuschalten, dann steht der Volltext wie bisher
  da.
  **Rein serverseitig, rein lesend**: `?szene=<id>&fassung=<n>` plus Anker
  (`web.fassungslink`, gelesen von `web.fassungswahl`), kein JS, kein POST,
  kein Cookie — das Token bleibt im Pfad, das Auth-Modell unverändert, und
  das sanfte Nachladen holt `location.href` samt Query, die Auswahl übersteht
  also den Austausch des `<body>`. Eine frühere Fassung wieder in Kraft zu
  setzen ist weiterhin **nicht gebaut** (Entscheidung mit Datenwirkung).
  **Rückwärtskompatibel**: `web_daten.szenenfassungen` legt drei Quellen
  zusammen — das Altfeld `szene.fruehere_fassungen`, die Tabelle und den
  aktuellen `volltext` —, zählt doppelte Texte einmal und nummeriert die
  Liste **selbst** von 1 durch: die Nummer in der URL ist die Nummer in der
  Ansicht, nicht die aus der Tabelle, sonst zeigte ein Link nach dem
  Nachrüsten auf die falsche Fassung. Fehlt die Tabelle noch, ist das
  Ergebnis kleiner statt ein Fehler — der Webserver migriert nichts.
- **Der Stil ist eine Auswahl je Szene, kein Overlay je Bot** (06.09.2026,
  Birk 12:50, `stile.py` + `prompts/stile/<slug>.md`). Birk: „alle Gruppen
  sollen auf alle Stile zugreifen können, als Auswahl, mit Nennung des
  Originalmaterials." Im Feinschliff folgt auf die Form-Frage **eine**
  Nachricht „Welcher Stil?" als Optionen-Menü (fetter Titel, ein Satz,
  Herkunft — Schatten/Morpheuz x Monet192, Lovesong/Adele,
  Herkules.exe/ArtesMobiles) plus „Ohne Stilvorlage"; der Bot schlägt
  passend zur Form vor (Rap → Schlagabtausch, Lied/Chor → Litanei,
  Dialog/Monolog → Herkules) **mit Begründung**, gesetzt wird aber allein
  durch den Druck (`szene.stil`, additive Spalte über
  `_migriere_fehlende_spalten`). `szene.systemanweisung(form, stil)` hängt
  den Stil-Block **nach** dem Formen-Regelblock und **vor** die Tells — und
  **nur bei `form != prosa`**: die Prosafassung ist eine Geschichte, kein
  Bühnentext. Die Web-Gruppenseite hat dasselbe als Dropdown je Szene;
  `web_schreiben.STILE` muss wortgleich zu `stile.STILE` bleiben (Test).

## Workshop-Profil

**Anlass** (Birk, 06.09.2026, nach `docs/workshop-profil-analyse-2026-09-06.md`):
das Repository war an 1217 gemessenen Stellen „Dortmund" — Alter der Gruppe,
Trägerverein, Aufführungsort, Formenliste, Phasennamen, der Wortlaut der
Einleitungen. Für einen zweiten Einsatzort hieße das entweder das Repo
gabeln oder bei jedem Workshop dieselben sechs Dateien von Hand umschreiben;
beim nächsten `git pull` wäre es wieder weg. Seither liegt alles
Individuelle unter `workshop/<name>/` und wird über **`IT_WORKSHOP`** je
Prozess eingehängt (`betrieb/gruppeN.env`, nie global — zwei Workshops
können damit parallel auf einem Server laufen).

**Ohne Variable gilt das eingebaute Vorgabeprofil**
(`workshop.VORGABE_WERTE` und die drei Geschwister) mit exakt den Werten,
die vorher im Code standen. `workshop/dortmund-2026/` trägt dieselben. Das
ist keine Redundanz aus Bequemlichkeit, sondern das Abnahmekriterium des
Umbaus: mit `IT_WORKSHOP=dortmund-2026` und ohne Variable entstehen
zeichengleiche Prompts. Geprüft wird das dreifach in
`tests/test_profil_bitgleich.py` gegen
`docs/prompt-audit/schnappschuss-vor-profilumbau.txt` — 114 Abschnitte, je
ein SHA-256, erzeugt mit `scripts/prompt_schnappschuss.py` vor dem ersten
Umbauschritt.

**Der Einhängepunkt ist `anweisungen.py`** und nur der: es ist die einzige
Stelle, an der Prompt-Text entsteht. Die Reihenfolge im Gesprächs-Prompt
lautet seither

Basis → Phase → **Profil** (`workshop/<name>/prompts/anweisung.md`) →
`zusatz.md` → `zusatz.<bot>.md`.

Der Regie-Zettel bleibt hinten, weil das Ende des Prompts am schwersten
wiegt (SPEC § 6.1): eine spontane Regieanweisung soll Basis, Phase **und**
Profil überstimmen können.

**Platzhalter statt Dateiersatz** ist der Normalfall (E.1 Frage 2 der
Analyse). `{{rahmen}}`, `{{zielgruppe}}`, `{{formen_liste}}` werden aus dem
aktiven Profil gefüllt; jede Prompt-Datei ist zugleich der Wert ihres
Platzhalters (`prompts/rahmen.md` → `{{rahmen}}`,
`prompts/formen/dialog.md` → `{{formen_dialog}}`, Bindestrich wird
Unterstrich), und die Fassung des Profils gewinnt über die des Repos. Ganze
Dateien zu ersetzen ist **erlaubt** — eine gleichnamige Datei in
`workshop/<name>/prompts/` schlägt die Repo-Datei —, aber der Ausnahmefall:
wer eine ganze Datei ersetzt, bekommt jede spätere Verbesserung am
generischen Prompt nicht mehr mit. Für ein Prompt-Set in einer anderen
Sprache ist Ersetzen richtig, für eine andere Altersgruppe nicht.

**Der Cache trägt das Profil im Schlüssel**: `_CACHE[(Profilname, Herkunft,
Prompt-Name)]` statt wie früher nur den Namen. Solange ein Prozess ein
Profil hat (heute so: ein Prozess je Gruppe), fällt das alte Verhalten nicht
auf — sobald zwei Profile in **einem** Prozess vorkommen, liefert der Cache
den Text des falschen Workshops. Das ist kein hypothetischer Fall: der
Web-Dienst läuft einmal für alle Gruppen (D.5 der Analyse). Aus demselben
Grund beantworten `szene.FORMEN`, `szene.FORM_STICHWOERTER`,
`web_schreiben.FORMEN`, `szenenfolge.FORM_VORGABE`, `phasen.PHASEN`,
`phasen.STICHWOERTER`, `phasen.MEHRDEUTIG`, `phasen.MELDUNG`,
`phasen.ERSTE`, `phasen.LETZTE` und `phasentexte.EINLEITUNGEN` ihren Wert
über ein Modul-`__getattr__` (PEP 562) bei **jedem** Zugriff frisch, nicht
einmal beim Import. Innerhalb desselben Moduls greift das nicht — dort
rufen die Funktionen `workshop.*` direkt auf.

**Format ist TOML, nicht YAML.** PyYAML ist keine Abhängigkeit dieses
Projekts, und eine neue Abhängigkeit für eine Konfigurationsdatei ist der
falsche Preis; `tomllib` steht seit Python 3.11 in der Standardbibliothek.
Kein Profil-Element ist Python (E.1 Frage 10): wenn eine Anpassung Code
braucht, liegt sie in der falschen Schicht.

**Kein Halbstart.** Ein fehlendes oder kaputtes Profil bricht `bot.main` ab,
bevor eine Datenbank geöffnet wird; `scripts/pruefe_profil.py` prüft
dasselbe vorher und läuft in `scripts/betrieb-start.sh` **vor** dem Bot.
Ein angefangenes Profil trägt `geruest = true` in `profil.toml`: es lädt und
lässt sich ansehen (damit ein Test nicht daran scheitert, E.1 Frage 8),
aber kein Bot startet damit. Fehlerbild am Workshoptag ist die teuerste
Währung.

**Verhaltensänderung für den Workshoptag** (D.10): der Block „Rahmen des
Stuecks" steht nicht mehr in `prompts/system.md`, dort steht `{{rahmen}}`.
Wer ihn im laufenden Workshop ändert, ändert
`workshop/dortmund-2026/prompts/rahmen.md` — hot-reload gilt dort genauso.
Die TOML-Dateien werden dagegen nur beim Start gelesen: eine halb
gespeicherte `profil.toml` mitten im Gespräch wäre genau der Halbstart, den
der Lader verhindert.

**Tests zweistufig** (D.1): generische Tests prüfen Struktur und gelten für
jedes Profil; `tests/profile/test_dortmund.py` prüft die Werte im Wortlaut
und läuft ausdrücklich mit `IT_WORKSHOP=dortmund-2026`. Wer ein Literal
durch einen Profil-Lookup ersetzt, prüft am Ende nur noch, dass zwei
Stellen dasselbe sagen.

Anleitung zum Anlegen eines Profils, offene Punkte und der Grund für jede
Abweichung von der Analyse: `docs/workshop-profil-umbau-2026-09-06.md`.

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

## Wo SPEC und Code auseinanderlaufen

`SPEC-kontext-architektur.md` § 8 beschreibt ursprünglich vierzehn Befehle
und einen Modus B (`/gruendlich`, freier Prosatext mit
`reasoning_effort: "medium"`, via `LLM.prosa()`). Nach dem ersten
Workshoptag wurde das auf sechs Befehle reduziert (Commit „Sechs Befehle als
Notausgang"): `/merken`, `/verworfen`, `/konflikt`, `/begriffe`, `/name`,
`/material` und `/gruendlich` existieren in der SPEC, aber nicht mehr im
Code. Seitdem sind Befehle wieder dazugekommen; **die Wahrheit ist
`befehle._BEKANNTE_BEFEHLE`, nicht diese Aufzählung und nicht die
SPEC-Tabelle.** Stand 06.09.2026 sind es dreizehn:

| Befehl | Wirkung |
|---|---|
| `/aufnahme` | Interview-Umschalter (an, und nochmal für aus) |
| `/interview` · `/fertig` | dasselbe in zwei Richtungen: nur an, nur aus |
| `/auswerten [N]` | ein Interview unter `aufnahme.MINDEST_WOERTER` doch noch verdichten (N2) |
| `/stand` · `/hilfe` | Arbeitsstand zeigen, Bedienung erklären |
| `/phase [Nummer\|Name]` | Arbeitsphase zeigen oder umschalten, auch zurück |
| `/kernthema <Text>` | Kernthema setzen, `/kernthema aus` nimmt es zurück |
| `/stueck [rahmen <Text>]` | das Setting zeigen oder setzen (`format` bleibt stilles Synonym) |
| `/szene <Auftrag>` | Szene planen, Form setzen, schreiben lassen — mit `/szene` ist `LLM.prosa()` verdrahtet (SPEC § 4.5 Nachtrag) |
| `/figur <Name> entfernen` | weiches Löschen (NACHTRAG N3); `/figur` legt bewusst **nichts** an, das macht weiterhin der Erkenner im Gespräch |
| `/wortlaut [Name\|aus]` | Originaltranskripte im Prompt mitlesen |
| `/leitfaden` | den gebauten Gesprächsleitfaden zeigen (versteckt) |

Im Telegram-Menü (`setMyCommands`, `befehle.BEFEHLE_LISTE`) stehen davon
**acht** — `/interview`, `/fertig`, `/figur`, `/wortlaut` und `/leitfaden`
sind bewusst nicht beworben. Das ist kein Versehen: **Slash-Befehle werden
nicht mehr beworben**, beworben wird der Knopf.

`befehle.behandle()` nimmt seit `/szene` ein optionales `klm` entgegen. Die
alte strukturelle Garantie („behandle bekommt kein LLM-Objekt, also kann ein
Befehl nicht am Modell scheitern") ist damit eine Zusage geworden, die der
Code weiterhin einhält: **kein Befehl ruft synchron ein Modell** — `/szene`,
`/fertig` und `/auswerten` geben sofort an einen eigenen Thread ab. Wer einen
vierzehnten Befehl anhängt, halte sich daran.

**Toter Code, der stehenbleibt:** die Spalte `gruppe.gruendlich_naechster_zug`
gehörte zum gestrichenen `/gruendlich` und wird von keiner Zeile Python mehr
gelesen. Sie bleibt trotzdem im Schema (06.09.2026, Refactoring): sie zu
entfernen hieße, das Schema einer laufenden Datenbank umzubauen — SQLite
braucht dafür je nach Version einen Tabellenneubau, `db.py` migriert
ausschließlich additiv, und im Betrieb laufen vier Bots auf denselben
Dateien. Eine tote Spalte kostet ein Byte je Gruppe; ein misslungener
Schema-Umbau kostet den Workshop.

## Starten und testen

**Regelweg: systemd-User-Units, nie Handstart.** Zwei Handstarts desselben
Bots = beide bekommen `409 Conflict` bei `getUpdates`, keiner empfaengt —
passiert am 04.09.2026 zweimal. Unit-Vorlage `docs/interview-theater@.service`
(nach `~/.config/systemd/user/`, `daemon-reload`), Start ueber
`scripts/betrieb-start.sh <gruppe>` (waehlt Python 3.11 aus `.venv`/uv —
das System-Python 3.9 kann `X | None` nicht importieren).

```
systemctl --user enable --now interview-theater@gruppe1.service   # je Gruppe
systemctl --user restart interview-theater@gruppe1.service        # Neustart
tail -f betrieb/gruppe1.log                                 # Log je Gruppe
```

**Verhalten aendern ohne Neustart** (`interview_theater/anweisungen.py`): alle
Prompts unter `interview_theater/prompts/` werden bei jedem Aufruf per mtime
geprueft und heiss nachgeladen -- auch `szene.md` und die Negativliste
`theater-tells.md`, die im Workshop waechst und beim naechsten Szenenauftrag
wirkt. Fuer spontane Regieanweisungen gibt es
`betrieb/zusatz.md` (alle Bots) und `betrieb/zusatz.<IT_BOT_NAME>.md` (ein
Bot); der Inhalt wird ans Ende der Gespraechs-Systemanweisung gehaengt,
Loeschen der Datei nimmt ihn zurueck. Erkenner/Journal/Verdichter bekommen
bewusst keinen Zusatz (gemessene Few-Shot-Prompts). Bedienung aus Hermes:
Skill `interview-theater-live-ops`.

Umgebungsvariablen: siehe `docs/betrieb-env.beispiel` zum Kopieren nach
`betrieb/<name>.env`. Handstart nur zum Debuggen, und nur wenn die Unit
gestoppt ist:

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m interview_theater.bot
```

- `pytest` — die Testsuite unter `tests/`, läuft ohne Netzzugriff (Attrappen
  statt echter Dienste). Enthält die Korpus-Validierung und die
  Bewertungsfunktionen aus `scripts/pruefe_prompts.py`, nicht den Lauf gegen
  das Modell.
- `python -m scripts.rauchtest [pfad-zu-audio.ogg]` — **kein Test, läuft nie
  automatisch, kostet Geld.** Ein echter Aufruf gegen Sprachmodell und
  optional Whisper, zur Kalibrierung der Token-Schätzung und als
  Erreichbarkeitsprüfung vor einem Einsatz.
- `python scripts/chat_leeren.py <chat_id> [--ja]` — setzt eine Gruppe auf
  null: löscht alle dem Bot bekannten Nachrichten aus dem Telegram-Chat
  (`deleteMessages`, Bot muss Admin sein; Nachrichten von vor seinem
  Eintritt und Telegram-Servicezeilen bleiben) und danach DB + Audio wie
  `loeschen.py`. Für den Workshop-Start nach einem Probelauf. Env der
  jeweiligen Gruppe laden — das Skript prüft, dass der Bot zur Gruppe passt.
- `python -m scripts.chat_leeren_blind <chat_id> [--zurueck 300]` — wenn die
  DB die Nachrichten nicht mehr kennt (nach `loeschen.py` oder nach einem
  Simulationslauf mit `--echte-db`): Marker senden, dann die letzten 300
  IDs rückwärts löschen. Telegram-Grenze: nur 48 h, nur als Admin.
- `python -m scripts.szenen_vergleich --nur opus,kimi,mistral,apertus` —
  eine Szene, gleicher Prompt, vier Modelle; Ausgabe als Markdown mit dem
  Prompt als Anhang. Grundlage der Entscheidung für Opus (05.09.).
- `python -m scripts.interviews_uebernehmen <ziel> <quelle> [<quelle> …] [--ja]`
  — hebt die Gruppengrenze für **Material** auf (06.09.2026, Ende Tag 2: nur
  noch eine Gruppe arbeitet weiter und soll alle Interviews sehen). Kopiert je
  Quellinterview Kopf, Teile, Transkripte, Verdichtung und
  `verdichtung_thema` (inkl. `zitat_geprueft`) sowie die Audiodateien in die
  Zielgruppe; **kein Modellaufruf**, die Quellen bleiben unverändert.
  Arbeitsstand, Figuren, Szenen, Knöpfe, Nachrichten, Journal und Kernzitate
  wandern bewusst **nicht** — das ist die Arbeit der Quellgruppe an ihrem
  Material, nicht das Material. `zum_kernthema_am` wird auf NULL gesetzt: was
  zur Kernfrage passt, entscheidet die Zielgruppe selbst. Die Nummerierung
  läuft weiter, weil `kontext.interviewbezeichnung` nach `id` zählt und neue
  Zeilen höhere ids bekommen; `name` wird beim Import auf „Interview N"
  gesetzt und nie aus der Quelle übernommen (dort kann ein Klarname stehen).
  Idempotent über `aufnahme.uebernommen_von` („`<quell_chat_id>:<alte_id>`",
  additiv migriert), alles in einer Transaktion, ohne `--ja` reiner
  Trockenlauf mit Zählung. Verweigert den Dienst, solange in Ziel oder Quelle
  eine Aufnahme läuft oder der Interviewmodus an ist. Mit `--ja` legt es
  selbst ein DB-Backup an, schreibt einen Journaleintrag in die Zielgruppe und
  eine Zeile in den Zielchat. Env der **Ziel**gruppe laden — die Quellen
  dürfen anderen Bots gehören, sie liegen in derselben Datenbank.
- `python scripts/loeschen.py <chat_id>` — der Löschweg: entfernt alle
  Datenbankzeilen einer Gruppe und ihr Audioverzeichnis, fragt vorher
  interaktiv nach Bestätigung. Es gibt bewusst keinen Löschbefehl im Chat.

`scripts/simulation_abdeckung.py` erzeugt die Abdeckungstabelle der
Simulation aus dem Code (Phasen aus `phasen.PHASEN`, Schritte aus den drei
`skript`-Listen, Pruefung aus `schritt.fertig.__name__`) und prueft jede
Behauptung der Simulations-Doku dagegen — kein Modell, kein Netz, keine
Kosten.

**Simulation** (`simulation/`, `scripts/simulation.py`, Stand 06.09.2026 nachts):
simulierte Gruppen spielen den Bot durch **alle Phasen** — mit Inline-Knöpfen
(`attrappe` merkt die Leisten, die Stimme drückt per Knopftext oder schreibt
frei) und dem Schrittplan `skript.SCHRITTE_TAG2`. Wie viele Phasen das sind,
steht nirgends im Simulator: er liest `phasen.PHASEN`, die Arbeitsstandfelder
aus `PRAGMA table_info(arbeitsstand)` und die Zielphase über
`skript.phase_szenen()` — ein Umbau an den Phasen soll ihn nicht mitreißen. Stimmen: drei erfundene Sets
plus **PII-freie Personas aus Tag 1** (`simulation/tag1.py`,
`simulation/stimmen/tag1-gruppe{1,2,3}.md`, `regie.md`): nur Begriffe/Fragen der
echten Gruppen, Themen-Stichworte und Verhaltensaggregate, nie Transkripte oder
Klarnamen — `tests/test_simulation_tag1.py` prüft das gegen die echte DB, wenn
sie da ist. Der Richter (Claude Opus über den Proxy) bewertet zusätzlich:
Nachrichten bis zum Speichern, Fragen je Bot-Nachricht, Wiederholungsquote,
„Bot redet parallel zum Auftrag", Knöpfe angeboten→gedrückt, Phasenwechsel
proaktiv, Form je Szene bestätigt, Exposition der Szene 1. Berichte
`simulation/laeufe/2026-09-06-*.md` + Sammelbericht. Läuft gegen ein anderes
Modell als der Bot. **Kein Test, kein Ersatz für `pytest` oder
`pruefe_prompts.py`**; Doku `simulation/README.md`.

**`python -m simulation.browser_lauf`** (Padua-UX-Simulation, 03.10.2026)
ist ein anderer Weg: statt den Bot-Code direkt anzufahren, bedient eine
Opus-Persona die echte Webseite in einem echten, headless Chromium
(Playwright) und sammelt dabei Screenshots, mechanische UX-Zaehler und ein
Opus-Urteil je Phase gegen `simulation/ux_rubrik.md` — eigene Module
(`simulation/browser_*.py`), eigene Doku (`simulation/README.md`, Abschnitt
„Der Browserlauf").

## Weboberfläche

Ein einziger Prozess für alle Gruppen, neben den Bots:

```
IT_DB=betrieb/soap.db python -m interview_theater.web
```

Unit-Vorlage `docs/interview-theater-web.service` (nach `~/.config/systemd/user/`,
`daemon-reload`, dann `systemctl --user enable --now interview-theater-web`), Log
nach `betrieb/web.log`.

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `IT_DB` | — (Pflicht) | dieselbe SQLite wie die Bots, **read-only** geöffnet |
| `IT_WEB_BIND` | `127.0.0.1:8010` | im Betrieb `100.75.24.33:8010` (Tailnet) |
| `IT_WEB_PREFIX` | `/theatersoap` | Präfix, unter dem nginx den Server durchreicht |
| `IT_WEB_URL` | `https://lab.artesmobiles.art/theatersoap` | nur für `scripts/web_links.py` |

Routen: `/` (Team-Dashboard, projiziert, alle Gruppen), `/g/<token>`
(seit Karte W die **vereinte** Seite mit den drei Tabs Chat · Arbeitsstand ·
Textbuch, siehe „Eine Oberfläche je Gruppe" unten), `/g/<token>/teil/stand`
und `/g/<token>/teil/roadmap` (die beiden Panel-Ausschnitte fürs sanfte
Nachladen, `web_vereint.sende_teil`), `GET /g/<token>/chat/strom` (der
SSE-Kanal des laufenden Texts, siehe „Der Strom"), `POST /g/<token>/chat/phase`
(der Klick auf eine Phase, siehe „Die Phasenübersicht"), `/g/<token>/textbuch`
(Probenansicht, siehe unten) samt `/g/<token>/textbuch.md` und `.txt`,
`/g/<token>/leitfaden` (der Gesprächsleitfaden groß und druckbar, rein
lesend, ohne Nachladen — siehe „Der Leitfaden hat eine eigene Seite"),
`/g/<token>/chat` (seit Karte W ein **302** auf `/g/<token>#chat` — die
Chatansicht des Web-Kanals ist in der vereinten Seite aufgegangen, siehe „Der
Web-Kanal" und „Eine Oberfläche je Gruppe") samt den weiter gültigen
Chat-Endpunkten `chat/zustand`, `chat/datei/<id>` und den POST-Wegen
`chat/senden`, `chat/knopf`, `chat/audio`, `chat/interview` und
`/gesund` (Health-Check, antwortet ohne Datenbankzugriff). Jede Route greift
auch mit vorangestelltem `IT_WEB_PREFIX`, weil erst die nginx-Konfiguration
entscheidet, ob das Präfix beim Server ankommt. Was hinter `/g/<token>/`
nicht in dieser Liste steht, ist 404 und nicht etwa Teil des Tokens
(`web._beantworte_gruppenseite`).

`python scripts/web_links.py` gibt aus, welche Gruppe welchen Link bekommt.
Das Token steht in `gruppe.web_token`, erzeugt wird es beim ersten Kontakt
vom Bot (`repo.stelle_web_token_sicher`, aufgerufen aus `sichere_gruppe`) —
der Webserver kann es nicht anlegen, er liest read-only.

**Drei Grenzen, die nicht verhandelbar sind**, weil beide Seiten ohne Login
erreichbar sind und das Dashboard projiziert wird:

- kein Nachrichtentext und keine Transkripte auf dem Dashboard,
- kein Volltranskript auf der Gruppenseite (dafür gibt es `/wortlaut` im Chat),
- kein Belegzitat ohne `zitat_geprueft = 1`.

`IT_WEB_BIND` lehnt `0.0.0.0` mit einem Fehler ab: ein Tippfehler in einer
Env-Datei soll die Interviews nicht ins offene Netz stellen.

### Die Probenansicht (06.09.2026)

`/g/<token>/textbuch` ist das ganze Stück am Stück — Szene für Szene mit
Nummer, Titel, Form, Ort/Zeit/Anlass, Besetzung und Volltext, eine
ungeschriebene Szene als Platzhalter mit ihrer Planung (dieselbe Entscheidung
wie in `szenenfolge.textbuch`: eine fehlende Szene 4 sieht aus wie ein
Fehler). Anlass ist Birks UX-Frage: bis dahin war Telegram der Arbeitsraum
und das Web die Anzeige, und für die eigentliche Theaterarbeit — Rollen
lesen, laut sprechen — ist ein Chatverlauf das falsche Medium. Der fertige
Text versinkt zwischen hunderten Nachrichten, und in der Probe hält jede
Person ihr eigenes Telefon in der Hand, nicht den Gruppenchat.

**Sie bleibt rein lesend**, und das ist keine Sparmaßnahme: die Gruppenseite
ändert seit dem 05.09. eine feste Liste von Parametern, weil dort *entschieden*
wird. In der Probe wird *gespielt*. Ein Formular unter einem Szenentext, den
man gerade laut liest, wäre eine Einladung zum Vertippen an der einen Stelle,
die ohnehin dem Chat gehört (der Volltext entsteht aus einem Modellauf und
wird dort abgenommen). Also: kein POST auf dieser Route (404), kein Nonce,
keine Zeile in `web_schreiben.FELDER`. Und **kein Nachladen** — weder `meta
refresh` noch das sanfte `fetch` der anderen Seiten: es würde alle zehn
Sekunden Rollenfilter und Schriftgröße zurücksetzen, und ein Textbuch ändert
sich nicht, während man es liest (`web._seite(..., nachladen=False)`).

Die Grenze ist hier **enger als auf der Gruppenseite**: nur Szenentexte und
Szenenplanung. Keine Interviews, kein Journal, keine Verdichtung, kein
Belegzitat — der Link geht in der Probe von Hand zu Hand. Test:
`test_kein_material_in_der_probenansicht`.

**Der Rollenfilter parst defensiv** (`web.sprecher_der_zeile`). Erkannt wird
die Grundform aus `prompts/szene.md` — „Figurennamen in GROSSBUCHSTABEN,
danach ein Doppelpunkt, dann die Replik" — samt der engen Schreibweise aus
`prompts/formen/dialog.md` (`LEYLA:(steht auf)Text`) und `CHOR:`. Dagegen
gesperrt sind: Satzzeichen im Namen, mehr als 30 Zeichen, und die Wörter, die
in echten Texten am Zeilenanfang mit Doppelpunkt stehen, ohne eine Figur zu
sein (`SZENE 1: …` aus dem Szenenkopf, `TITEL:`, `KURZ:` — sonst hätte jedes
Stück eine Figur namens „SZENE 1"). Ein kleingeschriebener Name gilt **nur**,
wenn die Gruppe wirklich eine Figur dieses Namens hat. **Wird keine
Sprecherzeile erkannt, fehlt die Leiste ganz** statt falsch zu markieren —
genau der Fall eines Stücks, das erst als Geschichte dasteht (Phase 6, Prosa).
Hervorgehoben wird gedämpft, nicht gelöscht: die Stichworte muss man
mitlesen können, sonst weiß niemand, wann sein Einsatz kommt.

Rollenfilter, Schriftgröße (drei Stufen) und „Regieanweisungen ausblenden"
laufen clientseitig, ihr Zustand steht im **URL-Fragment**
(`#figur=Leyla&schrift=gross&regie=aus`) und sonst nirgends — kein Cookie,
kein localStorage, kein Server-Roundtrip: der Link soll teilbar sein („so
liest sich das mit meiner Rolle"). Fällt JavaScript aus, bleibt das ganze
Stück lesbar, nur die Leisten wirken nicht.

**„PDF" ist ein Browser-Ausdruck.** Der `@media print`-Block wirft Leisten,
Wege und Farben weg und setzt ein Manuskript: Serifenschrift, Sprecher fett,
je Szene ein Seitenumbruch, und im Ausdruck gilt kein Rollenfilter (gedruckt
wird das ganze Stück, auch wenn am Telefon gerade eine Rolle hervorgehoben
ist). Damit braucht der Weg zum Papier keine Abhängigkeit.

`/g/<token>/textbuch.md` und `.txt` liefern **wörtlich**
`szenenfolge.textbuch(conn, chat_id)` — dieselbe Funktion, die der Knopf
„Textbuch als Datei" im Chat verschickt, gelesen über die read-only geöffnete
Verbindung. Keine zweite Wahrheit: zwei Textbücher, die irgendwann
auseinanderlaufen, wären schlimmer als eines, das nicht jedes Format kennt.
Im Chat steht der Link zur Probenansicht seitdem **neben** dem Datei-Knopf
(`knoepfe.probenansicht_zeile`, an beiden Stellen: `biete_durchlauf` und
`biete_nach_pruefung`) — als Textzeile, weil eine Inline-Tastatur
`callback_data` trägt und keinen Link. Der Knopf bleibt: die Datei nimmt man
mit, die Seite liest man in der Probe.

### Die Gruppenseite ändert Parameter (05.09.2026 abends)

Bis zu diesem Abend war beides read-only, mit der Begründung „sonst laufen
zwei Schreibwege gegeneinander" (N1). Die Begründung gilt weiter — deshalb
gibt es **keinen zweiten Schreibweg, sondern einen zweiten Auslöser für den
vorhandenen**: `web_schreiben.py` ruft ausschließlich `repo`-Funktionen,
dieselben wie `knoepfe._speichere` und `erkenner.wende_an`. In `web_daten.py`
kommt kein einziger Schreibpfad dazu; es bleibt read-only (`mode=ro`), und nur
der POST-Handler öffnet eine schreibende Verbindung (`db.verbinde` — WAL und
`busy_timeout`, wie `scripts/begruessen.py` aus einem fremden Prozess). Zwei
Tests halten das fest: kein `SELECT`/`INSERT`/`UPDATE` in `web_schreiben.py`,
kein Schreibpfad in `web_daten.py`. Änderbar ist **genau** `web_schreiben.FELDER`
und nichts sonst: Setting (`rahmen`), Geschichte, je Figur
Name/Beschreibung/Interview/Entfernen/Hinzufügen und je Szene Titel, Form,
Ort, Zeit, Anlass, was passiert, was anders, Ton und die Besetzung — also
genau das, was die Gruppe hier **fertig entscheiden** kann. Setting und
Geschichte sind dabei **unabhängig voneinander**: ein neues Setting ändert die
Geschichte nicht und stößt auch nichts an, was sie später ändern würde (Birk,
06.09.2026 10:25 — kein Auftragsweg vom Web an den Bot, keine automatische
Geschichte). Nicht änderbar: **nie Material** (Aufnahmen, Transkripte,
Verdichtungen, Belegzitate), nie der Szenen-Volltext, nie das Journal, nie die
USA-Einwilligung, nie der Sprachprofil-Text, nie die Schärfungs-Zuordnungen.
**Was der Chat führt** (`web_schreiben.FUEHRT_DER_CHAT`): Phase, Begriffe,
Fragen und die drei Leitfaden-Felder. Sie stehen auf der Seite an ihrem Platz,
aber als Anzeige — sie entstehen im Gespräch über Knöpfe und Ping-Pong, oft mit
einem Modellaufruf dahinter, und der Webserver hat keinen Modellklienten; sie
hier umtippen zu lassen hieße, denselben Wert auf zwei Wegen zu pflegen, von
denen einer die halbe Kette auslässt. Von den drei Leitfaden-Feldern steht
nicht einmal das Rohfeld da, sondern der **gebaute Leitfaden**
(`leitfaden.aus_feldern`, dieselbe Funktion wie im Chat): das, was die Gruppe
im Interview in der Hand hält. Seit dem Phasen-Umbau fehlen außerdem
**Kernthema, Kernthema-Richtung und Kernfrage**: sie sind keine Station mehr,
`geschichte` hat ihre Rolle übernommen; gesetzte Werte bleiben sichtbar
(`web_schreiben.NUR_ANZEIGE`, nur wenn gesetzt), änderbar sind sie nicht.
Ebenfalls nur Anzeige: der Formvorschlag je Szene (`szene.form_vorschlag` —
bestätigt ist allein `form`, und wer hier wählt, bestätigt gerade selbst) und
die Schärfungen aus Phase 6, als Zähler mit Kurzformen und **ohne Belegzitat**.
Die Dropdowns holen ihre Vorschläge aus der Tabelle `knopf`, zeigen also nur,
was im Chat ohnehin schon zur Auswahl stand. Jede Änderung hängt einen Journaleintrag an, `art
'entschieden'`, **`quelle 'web'`**, mit altem und neuem Wert (120 Zeichen je
Seite) — das ist der einzige Weg, auf dem der Gesprächs-Bot davon erfährt, denn
der Webserver spricht nicht mit Telegram: er liest das Journal bei jedem Zug
frisch (`kontext._baue_journal`). Wie in einem Knopf-Handler fällt hier **kein
Modellaufruf** an; wechselt eine Figur ihr Interview, wird deshalb das alte
Sprachprofil geleert und `geprueft_am` zurückgenommen, `knoepfe.stelle_figur_vor`
holt es im nächsten Zug im eigenen Thread nach. Das **Dashboard bleibt
vollständig read-only** und nimmt gar kein POST an — es hängt am Beamer. CSRF:
das Token in der URL ist das Geheimnis, dazu ein Formular-Nonce aus Token und
Stundenfenster (abgeleitet, nicht gewürfelt — ein zufälliger Nonce ließe das
sanfte Nachladen die Seite alle zehn Sekunden austauschen und risse jedes
offene Eingabefeld mit); aus demselben Grund lädt die Seite gar nicht erst
nach, solange der Fokus in einem Feld steht oder eines ungespeichert geändert
ist. Ein Neustart der Unit `interview-theater-web.service` ist nötig, die Bots
nicht.

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

**Architekt-Korrektur 30.09.2026** (drei Fehler im ersten Entwurf, selbst geprueft):
(1) `limit_req_zone` kennt nur `r/s` und `r/m` — `rate=200r/h` laesst `nginx -t`
scheitern. Audio je IP deshalb 10r/m: ein laufendes Interview schickt alle 45 s ein
Segment (1,33/min), sechs Gruppen hinter einer IP ≈ 8/min.
(2) Der Webdienst laeuft **nicht** auf herkules, sondern auf dem vServer, im Betrieb
gebunden an `IT_WEB_BIND=100.75.24.33:8010` (Tailnet, AGENTS.md „Weboberflaeche\");
`127.0.0.1` auf herkules waere der falsche Rechner. ANNAHME: herkules erreicht den
vServer ueber diese Tailnet-Adresse und die bestehende `location /theatersoap/` dort
nutzt sie schon — der Admin gleicht `proxy_pass` mit der vorhandenen Konfiguration ab,
statt diesen Block blind einzusetzen.
(3) Im Workshop sitzen alle Gruppen haeufig hinter **einer** IP (Raum-WLAN). Eine
IP-Zone mit 30r/m laege dann **unter** der Summe der App-Grenzen (4 Gruppen × 20/min),
und nginx saehe vor der App ab — genau das, was der Hinweis unten vermeiden will.
Deshalb 120r/m je IP (= 6 Gruppen × 20/min).

```nginx
# http { } -- einmal, ausserhalb des server-Blocks
limit_req_zone  $binary_remote_addr  zone=theatersoap_post:10m  rate=120r/m;
limit_req_zone  $binary_remote_addr  zone=theatersoap_audio:10m rate=10r/m;
limit_conn_zone $binary_remote_addr  zone=theatersoap_conn:10m;

location /theatersoap/ {
    proxy_pass http://100.75.24.33:8010/theatersoap/;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;

    # Etwas ueber der App-Grenze (8 MiB je Segment): nginx soll die
    # Verbindung kappen, bevor die App liest -- aber nicht frueher als sie,
    # sonst diagnostiziert man einen Fehler an der falschen Stelle.
    client_max_body_size 10m;
    client_body_timeout  60s;

    limit_conn theatersoap_conn 20;
}

location ~ ^/theatersoap/g/[^/]+/chat/audio$ {
    proxy_pass http://100.75.24.33:8010;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;
    limit_req  zone=theatersoap_audio burst=20 nodelay;
    client_max_body_size 10m;
}

location ~ ^/theatersoap/g/[^/]+/chat/(senden|knopf|interview)$ {
    proxy_pass http://100.75.24.33:8010;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;
    limit_req  zone=theatersoap_post burst=10 nodelay;
}
```

Die zwei `proxy_set_header`-Zeilen stehen in **jedem** `location`-Block (nginx
erbt sie nicht in einen Block, der eigene Direktiven setzt), und sie sind keine
Kür: `web.eigene_herkunft` vergleicht den `Origin` des Browsers mit `Host` oder
dem ersten Wert von `X-Forwarded-Host` — reicht nginx nur den internen Host
weiter (`$proxy_host`, die Vorgabe), wäre jeder echte POST aus dem Browser
ein 403.

Drei Hinweise dazu: die nginx-Zonen zaehlen je **IP**, die App je **Gruppe** —
das ist Absicht, zwei Achsen fangen zwei verschiedene Angriffe. Die
nginx-Raten liegen **ueber** den App-Grenzen, damit die App die Absage gibt
(mit `Retry-After` und einem Satz) und nicht nginx mit einer nackten 503. Und
die Gruppen sitzen im Workshop haeufig hinter **einer** IP (Raum-WLAN) —
deshalb die grosszuegigen `burst`-Werte.

### Der Web-Kanal: derselbe Bot ohne Telegram (30.09.2026, Karte Padua A2)

**Die Idee in einem Satz:** der Webserver ist für den Bot das, was Telegrams
Server heute ist — er nimmt Browser-Ereignisse an und legt sie als
Telegram-förmige Updates in die Tabelle `web_post`; ein normaler Bot-Prozess
liest sie mit `web_kanal.WebKanal` statt mit `telegram.Telegram`. Gewählt
wird der Kanal an genau einer Stelle, `bot.baue_kanal`.

**Was dadurch NICHT passiert ist:** `knoepfe/` (rund 4.500 Zeilen) wurde nicht
angefasst, `bot.schleife` nicht geändert, und der Telegram-Weg ist
unverändert funktionsfähig (E1: Telegram bleibt Plan B). Ohne `IT_KANAL`
verhält sich alles wie vorher — `tests/test_kanal_wahl.py` hält das fest.
Ein Tippfehler in `IT_KANAL` fällt **nicht** still auf Telegram zurück, der
Start bricht ab (`einstellungen.laden`).

**Warum die Naht trägt, ist gemessen und nicht geraten.** Die ganze
Kanalfläche sind zwölf Methoden, und `interview_theater/` ruft sie
ausnahmslos über das durchgereichte `tg`-Objekt (kein `httpx` gegen
`api.telegram.org`, `from.first_name` an genau einer Stelle,
`telegram.lies_nachricht`). `simulation/attrappe.py` beweist es seit dem
06.09.2026 empirisch: sie ersetzt `Telegram` und fährt einen ganzen Workshop
durch. `tests/test_web_kanal_naht.py` liest das Paket per AST und hält es am
Quelltext fest — **wer eine dreizehnte Kanalmethode benutzt, merkt es dort**,
nicht im Betrieb.

**EINE message_id-Folge für Gruppe UND Bot.** `web_post.id` ist zugleich
`message_id` und `update_id`. Das ist kein Detail: der Bot merkt sich seinen
Stand als `gruppe.letzte_beantwortete_message_id` und liest danach nur, was
größer ist. Zählten Gruppe und Bot in getrennten Folgen, läge jede
Gruppennachricht ab dem zweiten Zug unter dem Wasserzeichen — der Bot
beantwortete sie nie (gemessen in `simulation.attrappe.naechste_message_id`).
Telegram vergibt seine ids ebenfalls fortlaufend je Chat, über alle Absender.

**Die Tippanzeige ist keine Nachricht** und steht deshalb in
`gruppe.web_tippt_bis`, acht Sekunden gültig (`web_kanal.TIPPT_GUELTIG_S` = 8):
`arbeitszeilen.TIPP_S` ist 4,0 s, und ein vierminütiger Szenenlauf gäbe 60
Zeilen, die je eine `message_id` aus der gemeinsamen Folge verbrauchen.

**Web-Gruppen haben positive, synthetische chat_ids** ab
`repo.WEB_CHAT_ID_BASIS` (7 000 000 000 000) — weit oberhalb aller
Telegram-Bereiche, und im ganzen Repo leitet keine Stelle aus dem Vorzeichen
einer chat_id etwas ab (Test). Angelegt werden sie mit
`python -m scripts.web_gruppe anlegen <bot_name>` (Datei
`scripts/web_gruppe.py`); das Skript gibt den Link, die chat_id und die zwei
Env-Zeilen aus und **liest nie `betrieb/`**. Der Webserver könnte es nicht:
er öffnet die Datenbank read-only. `gruppe.kanal` hält fest, welcher Kanal
eine Gruppe bedient. Eine `IT_WEB_CHAT_ID`, die die Datenbank nicht kennt,
bricht den Start ab — ein Bot, der auf eine nicht vorhandene Gruppe hört,
sähe sonst aus wie ein hängender.

**E8 im Web:** Nachrichten tragen keinen Vornamen. `nachricht.absender` trägt
das Rollenwort `web_kanal.ABSENDER` (`"Gruppe"`) — nicht `None`, weil
`kontext.sprecherzeile` sonst wörtlich `"None:"` in jeden Gesprächs-Prompt
schriebe.

**Drei Dinge, die der Web-Kanal anders macht als Telegram** (alle drei
absichtlich):
1. **Kein Teilen bei 4.000 Zeichen.** Der Browser hat keine Längengrenze, und
   ein Text, der in vier Stücke zerfällt, macht aus einer Bot-Antwort vier
   Blasen, unter deren letzter dann die Knöpfe hängen.
2. **`setze_befehle` ist ein No-Op.** Im Browser gibt es kein Slash-Menü, und
   Slash-Befehle werden nicht beworben — beworben wird der Knopf.
3. **`loesche_nachrichten` löscht weich** (`web_post.geloescht_am`), wie alles
   Entfernte in diesem Projekt.

**Die Chatansicht** (`/g/<token>/chat`, Modul `web_chat.py`, Handy zuerst,
390×844) ist rein Vanilla-JS, ohne Build, ohne WebSocket, ohne Cookie, ohne
localStorage: sie pollt `chat/zustand?nach=<id>&seit=<aenderung>` alle zwei
Sekunden (sichtbar, `POLL_MS`) bzw. alle zehn (Hintergrund), und nie zwei
Polls gleichzeitig. `nach` holt neue Zeilen, `seit` holt **geänderte** —
`aendere_text`, `entferne_knoepfe` und `loesche_nachrichten` zählen die
additive Spalte `web_post.aenderung` hoch (ein Zähler, keine Uhrzeit: SQLite
serialisiert die Schreiber, also ist er monoton in Commit-Reihenfolge), und
die Blase wird ohne Neuladen ersetzt oder entfernt. Der Poll liefert außerdem
den aktuellen Formular-Nonce; ein POST mit 403 holt ihn einmal nach und
versucht es erneut. **Kein sanftes Nachladen** wie auf der Gruppenseite —
`web._seite(..., nachladen=False)`: das tauscht den `<body>` aus, und mitten in
einer laufenden Aufnahme risse das Recorder, Timer und Warteschlange mit.
Jeder Chat-Pfad mit Schrägstrich am Ende (`/chat/`) ist 404, und das JS baut
alle Wege absolut aus `location.pathname` — sonst zeigten die relativen
Verweise ins Leere, und `IT_WEB_PREFIX` bleibt dabei erhalten. Die Gruppenseite
verlinkt den Chat („Chat mit dem Bot") — **nur bei `gruppe.kanal = 'web'`**,
und alle Wege unter `/chat` (GET und POST) sind für jede andere Gruppe 404
(`web_daten.web_chat_id_nach_token`, Abschlussreview I3). Der Plan
(Aufgabe 6) schrieb den Link für jede Gruppe vor; **E1 geht vor**: eine
Telegram-Gruppe hat keinen Bot, der `web_post` liest, und was sie im Browser
schriebe, ginge still verloren. Gruppenseite, Probenansicht und Leitfaden
bleiben für alle Gruppen.

**Der Eingang wird als lückenloses Präfix geliefert** (Abschlussreview C1,
I1, `WebKanal._lieferbar`). `bot.schleife` rückt den Offset je Update vor —
eine zurückgehaltene Zeile mit etwas Späterem dahinter wäre danach für immer
übersprungen. Zurückgehalten wird an zwei Stellen, beide mit Frist und Log:
(1) eine **Sprachzeile ohne `datei`** — der Webserver legt erst die Zeile an,
schreibt dann die Datei und setzt danach den Verweis (`DATEI_FRIST_S` = 30);
(2) **jeder Nicht-Segment-Post** (Text, Knopf, Befehl) hinter einem Segment,
das beim Bot noch nicht angekommen ist — angekommen heißt: es gibt die
`aufnahme`-Zeile mit dieser `message_id`, oder `aufnahme.empfange` hat den
Vorfall `download_fehlgeschlagen` geschrieben (`repo.web_segmente_unterwegs`,
`ANKUNFT_FRIST_S` = 60). Ohne (2) lief /fertig im Pool (`bot.POOL_GROESSE`)
parallel zum letzten Segment und konnte es überholen: `aufnahme.klasse_fuer`
liest den Modus erst bei der Verarbeitung, das Segment wurde ein
Gesprächsbeitrag. Die Endung im Update kommt aus der Spalte `mime`
(`web_kanal.MIME_ERLAUBT`, die eine Tabelle, die auch der Webserver nimmt).
Telegram ist davon nicht berührt — es liefert seine Updates selbst.

**Keine Nachzügler im Web** (Abschlussreview I4): `aufnahme.stelle_interview_sicher`
sammelt beim Anlegen eines Kopfes die `kurz`-Aufnahmen der letzten zehn
Minuten nur bei `kanal != 'web'` ein. Im Browser ist eine PTT-Nachricht
ausdrücklich „an den Bot", und Segmente gehen erst raus, wenn der Poll den
Modus meldet. Telegram bitgleich (Test).

**Der Offset hängt am `bot_name`, nicht am Kanal** (Abschlussreview I2). Ein
Bot, der vorher Telegram fuhr, bringt eine getUpdates-Position um 10^8 mit
und hörte im Web nie etwas. `scripts/web_gruppe.py` setzt den Offset deshalb
auf 0, und `bot.baue_kanal` setzt ihn im Web-Kanal laut geloggt zurück, wenn
er hinter `repo.hoechste_web_post_id` liegt (bereits Gesehenes fängt die
Duplikatprüfung). `web_post.id` trägt `AUTOINCREMENT`, damit der Löschweg
einer Gruppe keine ids zur Wiedervergabe freigibt; eine schon angelegte
Entwicklungs-DB behält ihre Tabelle (`CREATE TABLE IF NOT EXISTS`),
`hoechste_web_post_id` fällt dort auf `MAX(id)` zurück.

**Bot-Ausgaben tragen Telegram-HTML** (`parse_mode="HTML"`, u. a.
`vorschlag.menuetext`). `web_chat.sichere_html` maskiert deshalb **alles** und
lässt dann eine geschlossene Liste wieder zu — `b i u s code pre blockquote`
und `a` mit `http`/`https`. In dieser Richtung, nicht in der anderen: ein
Filter, der `<script>` entfernt, ist eine Liste von Dingen, an die jemand
gedacht hat. Gefiltert wird **serverseitig** (auch im Poll); ein Filter im
JavaScript läge auf der Seite, die er schützen soll.

**Ein Knopfdruck wird gegen die hängende Leiste geprüft**
(`web_chat.knopf_erlaubt`), nicht gegen `knopf.message_id`: die ist nur
gesetzt, wenn ein Aufrufer `repo.merke_knopf_nachricht` ruft, und das tut nur
ein Teil der Sendestellen — `knoepfe.biete_einstieg` zum Beispiel nicht.
Geprüft wird gegen `web_post.knoepfe`, das `WebKanal.sende_mit_knoepfen`
selbst schreibt; es **ist** per Konstruktion, was gerade hängt. Steht `data`
dort nicht, gibt es 400 und **keinen Eingang** — sonst wäre jeder Knopf jeder
Gruppe per `curl` drückbar, sobald jemand einen Link hat, und die `k:<id>`
sind fortlaufende Zahlen. Die Wirkung macht danach `knoepfe.behandle` im
Bot-Prozess, unverändert: **kein zweiter Knopf-Handler**, und die Idempotenz
bleibt `repo.beanspruche_knopf` (Zusage 3).

**Audio im Browser sind ZWEI getrennte Knöpfe** (Birk, 30.09.2026,
verbindlich — **kein** Schieben-zum-Sperren, ein Test sucht das Wort im JS):

1. **Interview-Aufnahme**, ein Umschalter: einmal tippen = läuft, erneut
   tippen = Stopp, mit Timer, Pegel (`AnalyserNode`) und großem Stopp-Knopf.
   Er schaltet den Interviewmodus über die vorhandenen Befehlswege
   `/interview` und `/fertig` (POST `chat/interview`) — **keine zweite
   Moduslogik**, denn die Klasse einer Aufnahme hängt allein am Modus
   (`aufnahme.klasse_fuer`). Hochgeladen wird in **Segmenten von 45 Sekunden**
   (`IT_WEB_SEGMENT_MS`, Vorgabe `einstellungen.VORGABE_SEGMENT_MS`): Netz weg
   oder Tab zu verliert höchstens das letzte Segment, nie das ganze Interview.
   **Jedes Segment ist ein eigener MediaRecorder-Lauf** (`stop()` +
   `start()`), nicht eine Zeitscheibe: `start(timeslice)`-Stücke sind einzeln
   nicht dekodierbar, nur das erste trägt den Container-Kopf.
2. **Push-to-Talk** für Sprachnavigation, neben dem Textfeld: halten =
   sprechen, loslassen = senden, Klasse `kurz` (der Modus wird nicht
   geschaltet). Pointer Events mit `setPointerCapture`, je Druck ein eigenes
   Objekt; **unter 500 ms Haltezeit (`web_chat.PTT_MIN_MS`) wird verworfen**,
   und `pointercancel`, `lostpointercapture` oder Loslassen außerhalb des
   Knopfs senden **nichts**. Wird losgelassen, bevor `getUserMedia` das
   Mikrofon liefert, startet gar kein Recorder. Während eine
   Interview-Aufnahme läuft, ist PTT ausgeblendet, und ein Interviewstart
   verwirft einen gerade gehaltenen PTT-Druck — zwei Mikrofone gleichzeitig
   sind keine Bedienung.

**Die Warteschlange im JS ist der Kern der Audio-Seite** (Aufgabe 11 samt drei
Review-Runden). **Eine** sequentielle Schlange für Befehle (`/interview`,
`/fertig`) **und** Audio (Segmente, PTT): die Reihenfolge beim Bot ist die
Reihenfolge der Aufnahme. Ein Auftrag bleibt vorn, bis er 2xx bekommt;
Netzfehler, 5xx, 408, 429 und 403 werden **ohne Höchstzahl** wiederholt
(Abstand `UPLOAD_WARTEN_MS` = 1/3/8 s, das `online`-Ereignis löst sofort aus),
nur ein endgültiges 4xx verwirft — sichtbar, mit dem Servertext in `#fehler`.
Segmente tragen eine laufende Nummer und werden strikt in dieser Reihenfolge
eingereiht, auch wenn ein späteres `onstop` früher feuert. Daran hängen vier
Regeln:
- **Sofort aufnehmen, später hochladen.** Die Aufnahme startet sofort (sonst
  fehlen die ersten Worte), das erste Segment wartet aber, bis `/interview`
  dieser Aufnahme angenommen ist **und** der Poll einmal `interviewmodus`
  meldet — sonst machte `aufnahme.klasse_fuer` daraus eine `kurz`-Aufnahme.
  Danach rastet eine **Sperrklinke je Aufnahme** ein (`sitzung.bestaetigt`).
  Läuft der Bot gar nicht, warten Segmente und `/fertig` sichtbar
  (`_TEXT_WARTE_MODUS`) — ohne Bot gibt es keinen Ort für sie.
- **`/fertig` erst nach dem letzten Segment.** Es wird erst eingereiht, wenn
  der letzte Recorder sein `onstop` hatte — sonst verdichtet der Bot ein
  Interview, dem das letzte Segment fehlt. Ist der Servermodus schon aus
  (anderes Telefon, Erkenner), wird es nicht mehr gesendet.
- **Modusende hält an, statt still nachzuschicken.** Endet der Interviewmodus
  serverseitig, während dieses Telefon noch aufnimmt oder Segmente offen hat,
  stoppt die Aufnahme, die offenen Segmente werden **geparkt** (auch eines,
  dessen Upload erst danach scheitert), und die Gruppe entscheidet:
  „Rest als Interview nachreichen" (`/interview`, die Segmente, `/fertig` —
  nur, solange kein anderes Interview läuft, `_TEXT_NACHREICHEN_SPAETER`) oder
  „Rest verwerfen". Ohne Modus wäre ein 45-s-Segment ein Gesprächsbeitrag,
  und Gesprächszug, Erkenner und Journal liefen über Interviewmaterial.
  **Vorläufige Voreinstellung, die Entscheidung liegt bei Birk.**
- **Das Mikrofon wird freigegeben** (Tracks gestoppt, `AudioContext.close()`)
  nach jedem Interview-Ende, jedem PTT-Druck und in jedem Fehlerzweig; und
  `beforeunload` warnt bei laufender Aufnahme, gehaltenem PTT, voller Schlange
  oder geparkten Segmenten.
Der Leer-Schutz ist der vorhandene (`aufnahme._TEXT_LEER_VERWORFEN`). **Zwei
bekannte Grenzen, bewusst offen:** `fetch` hat kein Timeout (ein hängender
Upload hält die Schlange, bis der Browser aufgibt), und eine Wiederholung nach
Netzfehler kann einen schon angekommenen Upload doppelt anlegen (keine
Idempotenz-Kennung); PTT nimmt erst nach `getUserMedia` auf, der Anfang kann
fehlen.

**Die Endung entscheidet über den MIME-Typ** (Falle 3, und hier war die eine
Stelle, die dafür angefasst werden musste): `web_kanal.MIME_ERLAUBT`
(= `web_chat.MIME_ERLAUBT`, eine Tabelle an einer Stelle) ist eine
Allowlist **Content-Type → Endung** (`audio/webm` → `.webm`, `audio/mp4` →
`.m4a` für Safari, dazu `audio/ogg` und `audio/mpeg`), die Datei landet mit
dieser Endung unter `IT_AUDIO/<chat_id>/web-eingang/`, und
`telegram.lies_nachricht` trägt sie als neuen, optionalen Schlüssel `endung`
weiter, den `aufnahme.empfange` in den Zielpfad setzt. Ohne das bekäme ein
WebM den Pfad `<message_id>.ogg` und damit `audio/ogg`. Telegram nennt keine
Endung; dort bleibt es bei `aufnahme.ENDUNG_VORGABE` (`.ogg`), bitgleich wie
vorher. Größengrenze je Segment: **8 MiB** (`MAX_AUDIO_BYTES`) — gerechnet
aus Opus 32 kbit/s ≈ 180 KiB je 45 s mit zwanzigfacher Luft, und klar unter
`stt.MAX_UPLOAD_BYTES` (25 MiB).

**Betrieb:** dieselbe Unit-Vorlage, dasselbe `scripts/betrieb-start.sh`,
derselbe Profil-Check — ein Web-Bot unterscheidet sich allein durch
`IT_KANAL=web` und `IT_WEB_CHAT_ID` in `betrieb/<gruppe>.env`.
`IT_BOT_TOKEN` ist dort nicht Pflicht. **Zwei Variablen gehören dagegen
(auch) in die Web-Unit**, weil der Webserver keine `Einstellungen` lädt und
selbst aus seiner Umgebung liest: `IT_WEB_SEGMENT_MS` (die Seite gibt den Wert
an den Browser weiter — in der Env eines Bots wirkt er auf den Browser
nicht) und `IT_AUDIO` (der Webserver legt die Uploads dort ab, und
`WebKanal.lade_datei` verweigert jeden Pfad außerhalb des **eigenen**
`IT_AUDIO` — Web-Unit und Web-Bots müssen aufs selbe Verzeichnis zeigen;
beide laufen im Repo-Verzeichnis, Vorgabe `audio`). Die Web-Unit setzt
`IT_AUDIO` deshalb ausdrücklich (`docs/interview-theater-web.service`), der
Webserver speichert den Upload-Pfad **absolut** und nennt das Verzeichnis
beim Start in `betrieb/web.log` (Abschlussreview I5).

**Abnahme:** `tests/test_web_e2e_http.py` fährt eine Gruppe per HTTP von
Phase 1 bis zum ersten Interview (`bot.schleife` mit `WebKanal` und ein echter
Webserver; Attrappen nur für Sprachmodell und Whisper). `tests/e2e/test_web_chat_e2e.py` (Playwright, 29 Tests,
Fakes für `getUserMedia`/`MediaRecorder`) prüft im Browser Segmente,
PTT-Abbruch, Warteschlange, Modusende und das Handy-Bild; der Screenshot
`docs/web-chat/handy-2026-09-30.png` wird nur mit
`IT_SCHUSS_AKTUALISIEREN=1` überschrieben. Ohne Playwright wird die Datei
übersprungen.

**Was bewusst fehlt** (siehe „Was bewusst fehlt" unten): ein QR-Code zum
Link, die englischen UI-Texte, die Härtung (Rate-Limit, Nonce in der Query)
und die Kennzeichnung des Transkript-Echos — die Härtung macht die Karte
„Absicherung Web".

### Fassungen umschalten (07.09.2026)

Die Szenenübersicht trägt je Szene einen Zähler („3 Fassungen"), der auf die
Szene zeigt; im Szenenblock steht dann eine Leiste mit einer Nummer je
Fassung, **genau ein** Text und darunter der Link auf die vorige. **Rein
serverseitig** über `?szene=<id>&fassung=<n>` (`web.fassungswahl`,
`web.fassungslink`) — kein neues Framework, kein JavaScript, kein POST, und
**keine Änderung am Auth-Modell**: das Token steht weiter im Pfad, nicht in
der Query. Das sanfte Nachladen holt `location.href` samt Query, die Auswahl
überlebt also den Austausch des `<body>`; der Anker `#szene-<id>` bringt den
Browser an die Szene zurück, die deshalb bei einer Auswahl serverseitig `open`
bekommt. **Read-only**: eine frühere Fassung wieder in Kraft zu setzen ist
eine Entscheidung der Gruppe und gehört in den Chat, wo die Knöpfe darunter
hängen — `web_schreiben.FELDER` kennt kein Feld dafür. Auch hierfür genügt ein
Neustart von `interview-theater-web.service`; die Bots brauchen einen nur, weil
`szene.schreibe` die neuen Zeilen anlegt.

### Die Gestaltung (01.10.2026, Padua)

Alles Gestalterische liegt in **einem** Modul (`web_gestalt.py`) und wird
an neun Zeilen eingehaengt (gezaehlt am 03.10.2026): sechs in
`web_vereint.seite` (Rahmen-CSS, drei gescopte Bloecke, `css_interview()`
nur mit Chat, dazu das Effekt-JS), je eine in `web.textbuch_html` und
`web.leitfaden_html` und eine in `web.dashboard_html` (`tokens_css()` +
`css_dashboard()`, nur mit Profilschalter, siehe unten). Dazu seit der
read-only Werkbank eine zehnte, ebenfalls in `web_vereint.seite`
(`css_werkbank()`, nur mit `[web] workbench_bearbeitbar = false`). Es fasst **kein
Markup** an — was die Gestaltung zusaetzlich braucht, legt das Effekt-JS
zur Laufzeit an (alles mit dem Praefix `ux-`). **Zwei Ausnahmen**, beide
in `web.py` (Nacharbeit 03.10.2026): (1) `web.gruppe_koerper` stellt „Was
noch fehlt" vor die Formulare des Arbeitsstands, statt dahinter — eine
Umstellung, kein neues Element (Test
`test_was_fehlt_steht_vor_den_formularen_des_arbeitsstands`); (2) das
Team-Dashboard bekommt **neues Markup** (`_fortschritt_html`,
`_achtung_html`, `_dashboard_inhalt_html`: Akt n/7 mit sieben Segmenten,
der Hinweis „Needs attention", die gekappte Karte) — aber **nur hinter dem
Profilschalter `[web] dashboard_gestaltet`** (gesetzt allein in
`workshop/padua-2026/profil.toml`); ohne ihn bleibt das Dashboard-HTML
byte-gleich (`tests/test_web_dashboard_en.py`).

**Ein Block Design-Tokens ist der ganze Entwurf.** `TOKENS["a"]`
(„Terminal zuerst": Phosphor auf Schwarzblau, Monospace, Tableiste unten)
und `TOKENS["b"]` („Buehne zuerst": Amber auf Samtschwarz, Serife, Tabs
oben) tragen **dieselben Schluessel**; umgeschaltet wird ueber
`VORGABE_ENTWURF` oder `IT_UX_ENTWURF`, dazu vier benannte
Komponenten-Abweichungen (Tab-Ort, Knopfform, Akt-Moment, Skript-Satz).
Die klickbaren Muster, an denen entschieden wurde, liegen unter
`docs/ux-padua/entwurf-{a,b}.html`.

**Drei CSP-Regeln, die im Code stehen und nicht im Kommentar** (die
Richtlinie aus der Absicherungs-Karte hat `default-src 'none'`,
`script-src`/`style-src` nur mit Nonce und **kein `font-src`**):

1. **Kein Webfont, kein `@font-face`, kein `@import`, keine Fremdquelle** —
   System-Schriftstacks (`--schrift-lesen/-tech/-skript`). Ein
   eingebetteter Font waere geblockt, auch mit `data:`-URL.
2. **Kein `style="…"`-Attribut, kein `on…=`-Handler** im ausgelieferten
   HTML. Dynamische Werte gehen ueber **CSSOM**
   (`el.style.setProperty('--fortschritt', …)`) — das ist unter
   `style-src 'nonce-…'` erlaubt, `setAttribute('style', …)` waere es
   nicht. Ein Test misst das am fertigen HTML der vereinten Seite, der
   Probenansicht und des Leitfadens.
3. **`@keyframes` und `@media` nur in `css_rahmen()`.** Die drei anderen
   CSS-Funktionen laufen beim Aufrufer durch `web_vereint.scope_css`, und
   dessen Regex machte aus dem Rumpf eines `@keyframes` (`50% { … }`) eine
   gescopte Regel `.panel-chat 50%`.

**`prefers-reduced-motion: reduce` legt alles still**, und zwar mit
`!important` — die Animationen aus A2/W sind gescopt und damit
spezifischer als jede Regel dieses Moduls. Der Strom baut seinen Text
trotzdem stueckweise auf: das ist Information, keine Animation. **Kein
Zustand haengt an einer Bewegung**; jeder steht zusaetzlich im Text.

**Der Kontrast ist gerechnet, nicht geschaetzt.** `web_gestalt.KONTRAST`
ist die Tabelle der Paare, die die Gestaltung wirklich uebereinanderlegt;
`tests/test_web_gestalt_tokens.py` rechnet fuer **beide** Entwuerfe das
WCAG-Verhaeltnis nach (≥ 4.5 fuer Text, ≥ 3 fuer Bedienelemente). Wer eine
Farbkombination hinzufuegt, traegt sie dort ein — sonst prueft sie
niemand. `--linie` steht bewusst nicht darin (dekorative Haarlinie);
Raender, die einen Zustand tragen, benutzen `--rand`.

**Der Aufnahmeknopf ist das wichtigste Element** (Dortmund Tag 1: 13 von
20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden gedrueckt). Vier
Zustaende, aus dem DOM abgeleitet und **ohne neuen Schluessel im
Zustands-Poll**: `ruht` → `startet` → `laeuft` → `laedt`. Jeder steht im
**Text** (zweite Zeile `#ux-rec-zeile` **neben** dem Knopf — `_CHAT_JS`
schreibt in den Knopf selbst), der laufende ist **groesser** als der
ruhende, und `:active` gibt die Rueckmeldung in unter 100 ms. Die
Gestaltung **sperrt keinen Druck**: dass `_CHAT_JS` waehrend eines
Uebergangs weiter auf Klicks reagiert, ist ein Logikbefund an der
Web-Chat-Karte und steht in `docs/ux-padua/BERICHT.md`.

**Der Ausdruck bleibt hell.** `css_rahmen()` traegt einen eigenen
`@media print`-Block, weil die Gestaltung im `<style>` **nach**
`_CSS_TEXTBUCH` steht — ohne ihn kaeme ein schwarzes Blatt aus dem
Drucker.

**Der Interview-Modus zeigt nur noch die Aufnahme** (03.10.2026,
`web_gestalt.css_interview()` und `_JS_INTERVIEW`). Erkannt allein am DOM:
`html[data-ux-interview="1"]`, solange `#fuss[data-interview="1"]` **und**
`#uhr` sichtbar ist — `data-interview` allein steht schon beim Druck und
auch dann, wenn ein anderes Telefon den Modus haelt. Im Modus fallen
Aktzeile, Tableiste, Verlauf, Eingabe, PTT und alle Effekte weg; es bleiben
ein zugeklappter Leitfaden (Text per `textContent` aus dem schon
ausgelieferten `pre.leitfaden`), eine grosse Uhr, der Pegel, eine kleine
Lampe statt des runden Knopfs, die Zustandszeile, „Pause" und **ein**
Hauptknopf „■ Beenden" unten in der Daumenzone. Das Chat-Panel ist im
Modus erzwungen sichtbar (ein Zurueck-Wischen auf `#stand` nahm sonst den
Stopp mit). Dazu ein **Wake Lock**: feature-detected, jede Ablehnung
geschluckt, angefordert beim Eintritt, freigegeben bei Modusende,
`visibilitychange` → hidden und `pagehide`, neu angefordert beim
Zurueckkommen. Er verhindert nur das automatische Sperren; was beim
Sperren von Hand, bei einem Anruf oder ohne Netz mit der Aufnahme
geschieht, steht als Befund an A2 in `docs/ux-padua/DESIGN-REVIEW.md`.
Ueber jedem Tab steht ausserdem eine Zeile „Als Nächstes: …"
(`_JS_NAECHSTES`), gelesen aus der ersten offenen Aufgabe der aktiven Phase
in der Aktfolge — kein neuer Serverschluessel.

**Das Team-Dashboard `/` ist nur im Padua-Profil gestaltet.** Der
Profilschalter `[web] dashboard_gestaltet` (Vorgabe `false`, `true` nur in
`workshop/padua-2026/profil.toml`) haengt `css_dashboard()` ein und stellt
die Karte um: Akt n/7 mit sieben Segmenten, ein Hinweis „Needs attention"
nur bei einem Problem (`web.ACHTUNG_VORFAELLE`, Fehlschlaege und Vorfaelle
der letzten 2 h, Kosten ab 80 % des Deckels, Web-Eingaenge, die der Bot seit
3 min nicht abgeholt hat), keine leeren Felder, kein Leitfaden, kein
Botname. Ohne Profil und mit `dortmund-2026` bleibt das HTML byte-gleich —
`tests/test_web_dashboard_en.py` haelt es fest. **Betrieb:** die
Kostenwarnung liest `IT_KOSTEN_DECKEL_CHF` aus der Umgebung des
**Webdienstes** (Vorgabe 5.0); `docs/interview-theater-web.service` setzt
die Variable nicht. Wer den Deckel in den Bot-Envs aendert, setzt ihn auch
dort, sonst warnt das Dashboard gegen die Vorgabe. Begruendungen je
Element: `docs/ux-padua/DESIGN-REVIEW.md`.

**Die Werkbank ist in Padua reine Anzeige** (03.10.2026, Karte
t_49e7354c, Birk: „Workbench reiner Status-Ausspieler. Änderungen passieren
über Chat."). Profilschalter `[web] workbench_bearbeitbar` (Vorgabe `true`,
`false` nur in `workshop/padua-2026/profil.toml`). Mit `false` ersetzt
`web.werkbank_koerper` den Rumpf von `gruppe_koerper`: EINE Achse, die
sieben Phasen in Reihenfolge, je ein `<details>` mit Zähler („4 of 5", ✓
wenn alles erledigt), aufgeklappt nur die aktuelle Phase, darunter je
Attribut ein Punkt in drei **Formen** — gefüllt mit Haken `--signal`
(erledigt), Ring `--warn` (offen, bis zur aktuellen Phase), gestrichelter
Ring `--text-leise` (später) — und ein `aria-label`; Roadmap-„läuft"
erscheint als offen plus Wort. **Eine Quelle:** `roadmap.werkbank` auf
derselben `lage` wie `roadmap.aus_daten`, `AUFGABEN` unverändert; die
Detailzeilen (Diskussion, je Interview, je Szene Prosa/Überarbeitung/Form,
je Figur Sprechweise) lesen nur, was `web_daten.werkbank` read-only lädt.
`fehlstellen.py` bleibt für `/stand` und Dortmund; in Padua sind die
offenen Punkte die Liste. Kein Formular, kein `_BEARBEITEN_JS`, kein
Probenansicht-/Chat-Link, keine Phasenanzeige im Panel; der Inhalt je
Phase kommt aus denselben Bausteinen wie vorher (`_interview_html`,
`_festlegungen_html` ohne Löschknopf, `_dramaturgie_html`,
`_sprechanteile_html`, `_leitfaden_html` — `pre.leitfaden` muss bleiben,
der Interview-Modus liest ihn). Der Werkbank-POST (`POST /g/<token>`)
antwortet dann **403**; die Chat-POSTs laufen weiter. Der Nonce steht in
Padua im Chat-Panel (`chat_koerper(mit_nonce=True)`); `friskeNonce()` findet
in `teil/stand` keinen mehr, der Chat-Poll hält ihn frisch. Das CSS
(`web_gestalt.css_werkbank`) ist die zehnte Einhängezeile, nur mit dem
Schalter `false`. Ohne Profil und mit `dortmund-2026` bleibt alles
byte-gleich — `tests/test_werkbank_bitgleich.py` gegen
`tests/fixtures/werkbank_vorher_*.html`. Grenze: die Einzelseite
`gruppe_html` (von keiner Route mehr ausgeliefert) zeigt die Punkte
ungestaltet. Screenshots: `docs/ux-padua/workbench/`.

### Eine Oberfläche je Gruppe (30.09.2026, Karte W)

`/g/<token>` ist seitdem **eine** Seite mit drei Tabs — **Chat** (der Ersatz
für Telegram, Karte A2), **Arbeitsstand** (die bisherige Gruppenseite, weiter
editierbar) und **Textbuch** (die Probenansicht). Alle drei liegen im
**selben Dokument**; umgeschaltet wird nur über `hidden`, nie über einen
Seitenwechsel — sonst risse jeder Tabwechsel die laufende Aufnahme, die halb
getippte Nachricht und den laufenden Stream mit. Der Tab steht als bloßes
Wort im Fragment (`#chat`, `#stand`, `#textbuch`), damit die Zurück-Taste des
Handys funktioniert und ein Link teilbar bleibt; ein Rollenlink der
Probenansicht behält dabei seine Form (`#textbuch&figur=Leyla`).

**Die alten Adressen leben weiter**, und das ist keine Höflichkeit: die
Probenansicht (`/g/<token>/textbuch`, `.md`, `.txt`) und der Leitfaden
(`/g/<token>/leitfaden`) bleiben **eigene** Seiten mit ihrem `@media print`
und ohne Nachladen — gedruckte QR-Codes und geteilte Rollenlinks dürfen nicht
sterben. `/g/<token>/chat` (Karte A2) leitet mit **302** auf `/g/<token>#chat`.

**Nachgeladen wird nur noch das Stand-Panel** (`/g/<token>/teil/stand`,
`web_vereint.sende_teil`), mit denselben zwei Sperren wie bisher (Fokus in
einem Feld, ungespeicherte Änderung) und **nur, wenn es sichtbar ist**.
`web._SCROLL_JS` steht weiter, aber die vereinte Seite lädt es nicht: es
tauscht `document.body.innerHTML`, und daran hängen Recorder, Eingabefeld und
Strom.

**Das CSS wird zur Laufzeit eingeschränkt** (`web_vereint.scope_css`), die
bestehenden Konstanten bleiben Zeichen für Zeichen. Gemessen am 30.09.2026
kollidieren `_CSS_GRUPPE` und `_CSS_TEXTBUCH` in `body` und `h1`, und
`.leiste` heißt im Textbuch die Rollenleiste und im Chat die Knopfleiste; die
Probenansicht hängt ihren Zustand außerdem an `<body>`, was im gemeinsamen
Dokument den Chat mitfärben würde (deshalb `data-textbuch` als Wurzel).

**Das Team-Dashboard `/` bleibt unverändert** — es hängt am Beamer, es zeigt
alle Gruppen, und es ist nicht diese Karte. (Gestaltet wurde es später von
der UX-Karte Padua, und nur hinter dem Profilschalter
`[web] dashboard_gestaltet` — siehe „Die Gestaltung".)

**Ein vierter Tab braucht nur drei Stellen.** `web_vereint.TABS` ist die
EINE Liste, die Tableiste, Panel-Schleife und das Hash-Routing im Browser
treibt (sie geht als `__TABS__` in `_VEREINT_JS` ein) — der inzwischen
gebaute „Bühne"-Tab (CoThinker, Phase-4-Regiekarten, seit 04.10.2026 auch
Phase 1, siehe oben) brauchte dafür nur einen Eintrag in `TABS`, eine
Beschriftung in `_TEXT_TAB` (plus ihre englische Fassung in
`sprachen/en/texte.toml`) und einen Panel-Rumpf im `panels`-Dict von
`web_vereint.seite` — sonst nichts.

### Die Phasenübersicht (30.09.2026, Karte W)

Oben auf der vereinten Seite, **eine Zeile hoch**: „Phase N von 7 · Name —
2/4". Per `<details>` aufklappbar zur vollen Liste aller sieben Phasen mit
ihren Aufgaben (✅ erledigt · ⏳ läuft · ⬜ offen) — **ohne JavaScript
benutzbar**. Auf einem Telefon ist der Chat die Arbeitsfläche; eine dauerhaft
aufgeklappte Liste nähme ein Drittel des Bildschirms für etwas, das man
dreimal am Tag braucht.

Die Daten kommen aus `roadmap.aus_daten` — **rein**, kein Modellaufruf, und
die Aufgabenliste ist per Test an `phasentexte.PARAMETER` genagelt: eine
zweite, frei erfundene Wunschliste wäre der erste Stand, der ausschert
(dieselbe Regel wie bei `fehlstellen`). **'läuft' zeigt nur, was in der
Datenbank steht** — Interviewmodus, `gruppe.web_tippt_bis`, eine laufende
Zeile in `web_strom`; ein Szenenlauf-Lock lebt im Bot-Prozess und ist für den
Webserver unsichtbar. Ein Klick auf eine **Aufgabe** springt zu ihrer Stelle
(Tab + Feld) und setzt **nichts**; ein Klick auf eine **Phase** schaltet um
(siehe Phasenregel oben).

### Der Strom (30.09.2026, Karte W)

Birk: „die website soll die llm antworten streamen können." Gestreamt werden
**Gesprächszug, Auftragszug, Szenenlauf und Prosalauf** — alles, dessen
Ergebnis ein Mensch liest. **Nicht** gestreamt werden Erkenner, Journal,
Verdichter, Sprachprofil, Schärfung, Szenenfolge-Vorschlag und Dramaturgie:
ihr Ergebnis liest eine Maschine.

**Der Gesprächszug ist dabei ein Schema-Aufruf** (`ablauf.SCHEMA`,
`{"antwort": string}`) — was ankommt, ist ein wachsender JSON-Präfix, kein
Text. `strom.wert_aus_praefix` dekodiert daraus den bisherigen Wert, samt
halbem Escape, halber `\uXXXX`-Folge und halbem Surrogatpaar. **Kein Prompt
und kein Response-Format ändert sich dafür** — der Korpus gilt unverändert.

Der Weg: das Modell wird im **Bot**-Prozess gerufen, der Browser hängt am
**Web**-Prozess; dazwischen liegt die Tabelle `web_strom` (eine Zeile je
laufendem Aufruf, `zustand` läuft/fertig/abgebrochen, `post_id` der fertigen
Nachricht). Der Bot schreibt gedrosselt (`strom.INTERVALL_S` = 0,15 s), der
Webserver liest read-only und schickt die Deltas per **SSE** über
`GET /g/<token>/chat/strom` (`text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, `Connection: close`, Keepalive alle 15 s, Ende nach
`STROM_MAX_S` = 300 s). **Karte A2 sagt „kein SSE" — diese eine Route ist die
Ausnahme**, für alles andere bleibt der Poll.

**Was sichtbar streamt, ist schon gesäubert:** `strom.sichtbar` nimmt die
VORSCHLAG-Markerzeilen heraus, auch die halb getippte. **Kein halber Text wird
je eine Nachricht:** reißt der Anbieterstream nach dem ersten Stück ab, geht
die Zeile auf `abgebrochen`, die vorläufige Blase verschwindet, und **genau
ein** Wiederholungsversuch ohne Stream holt die vollständige Antwort — eine
Buchung, nicht zwei. Lehnt der Anbieter `stream` ab oder liefert keine
`usage`, fällt der Prozess still auf den blockierenden Weg zurück und
vermerkt das **einmal** (`strom_nicht_verfuegbar`), damit der Kostendeckel
nicht dauerhaft auf Schätzungen steht. **Der Telegram-Weg bleibt unangetastet**:
`telegram.Telegram` hat kein `strom`, und ohne `bei_teil` ist jeder
Anbieteraufruf zeichengleich wie vorher (Test).

**Betriebshinweis nginx:** ohne `proxy_buffering off;` (oder mit einem Proxy,
der `X-Accel-Buffering` ignoriert) kommen die Teilstücke am Stück an. Die
nginx-Konfiguration liegt nicht im Repository; gemessen wird sie mit
`curl -N <URL>/g/<token>/chat/strom`.

**Ob der Gesprächszug wirklich streamt** (ANNAHME 4: Infomaniak akzeptiert
`stream` zusammen mit `json_schema` und liefert `usage` mit), misst erst ein
echter, bezahlter Lauf: `python -m scripts.strom_probe --bericht` (kein Test,
kostet Geld), Bericht unter `docs/web-vereint/strom-probe-<datum>.md`. Das
Skript steht seit `1e0f9ec`; der Lauf selbst steht zum Stand dieser Karte
noch aus — die Betriebszugänge dafür lagen dieser Session nicht vor.

### Prompt geändert? → Korpus laufen lassen

Die fünf Prompts werden heiß nachgeladen, also ändert sie jemand **während**
des Workshops. Der Regressionskorpus unter `korpus/` ist das Gegenmittel gegen
den Blindflug: 150 Absichtserkenner-Fälle (davon 53 Negativfälle; darunter
11 aus einer laufenden Aufnahme — `aufnahme` statt `nachrichten`, N1 —, und
20 mit `zustimmung: true` markiert, N7; Stand 30.09.2026, alle `art`-Werte
mindestens zweimal, `szene_planen` mit Szenenbezug), 22 Journal-Abschnitte
(davon 11 leere), 7 erfundene Interviewtranskripte — darunter einer, dessen
Sollwert **null** Kernthemen sind (der Live-Fall aus dem Probelauf, N2) —
und 5 Sprachprofil-Fälle (T3, eine je Sprechweise: kurze Sätze mit
Selbstkorrektur, Code-Switching, „man"-Distanz, Reihungen, Rückfragen), alle
mit Sollwert.

(Stand 30.09.2026 nachgemessen — die Zahlen davor waren seit dem 05.09. nicht
mitgewachsen. Wer Fälle ergänzt, zählt mit
`python3.11 -c "import json; f=[json.loads(l) for l in open('korpus/erkenner.jsonl') if l.strip()]; print(len(f), sum(1 for x in f if not x['erwartet']))"`
nach, statt zu schätzen.)

Seit dem 30.09.2026 dazu `szene_kuerzen` mit `sk01`/`sk02` (positiv, beide
`zustimmung: true`) und `sk03`–`sk05` (negativ) — die Art liegt direkt neben
n20, n27 und fl04, und
`tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle` hält deren
Sollwerte fest.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner             # nach einer Änderung an erkenner.md
python -m scripts.pruefe_prompts alle --bericht       # vollständig, mit Markdown-Bericht
python -m scripts.pruefe_prompts erkenner --nur e18-verworfen-kindheitsfragen
python -m scripts.pruefe_prompts erkenner --modell <anderes>   # Modellvergleich
```

**Kein Test, läuft nie automatisch, kostet Rappen** — wie `rauchtest.py`. Rund
70 Aufrufe für `alle`, sequenziell (Infomaniak liefert bei Parallelität
429/5xx). Der Lauf schreibt seine `aufruf`- und `vorfall`-Zeilen in eine
Wegwerf-Datenbank, nie in `IT_DB`.

> **Die Regel: eine Änderung am Erkenner-Prompt gilt nur, wenn FP = 0 bleibt.**
> Null Falsch-Positive bei 25 Negativfällen ist die Zahl, die den Erkenner
> qualifiziert und die acht nicht gebauten Befehle begründet hat (SPEC § 4.3a,
> § 8.1). Genau das ist deshalb der Exit-Code: das Skript endet mit 1, sobald
> der Erkenner auch nur ein Falsch-Positiv liefert.
>
> **Was FP heißt, hat sich am 05.09.2026 gedreht (N7) — die Zahl nicht.** Ein
> Falsch-Positiv ist jetzt: ein Eintrag, dem im Abschnitt **kein konkreter
> Vorschlag und keine Zustimmung** vorausgeht. Ein Eintrag *nach* einer
> Zustimmung ist keiner mehr, auch wenn sie beiläufig war („passt", „nehmen
> wir", „das können wir so fix machen"). Grund: seit es weiches Löschen und
> `transkript_korrigieren` gibt, ist ein falscher Eintrag billig — ein Satz der
> Gruppe nimmt ihn zurück —, ein fehlender teuer: die Website bleibt leer, der
> Bot weiß nichts davon, und die Gruppe muss alles noch einmal sagen. Im
> Probelauf stimmte sie dreimal zu (Fragen, Kernthema, drei Figuren), und
> dreimal blieb der Arbeitsstand leer. **Das Prüfskript rechnet dafür nicht
> anders — es sind die Sollwerte im Korpus, die sich gedreht haben.** Daneben
> steht seither eine zweite Kennzahl (nicht im Exit-Code): **Falsch-Negative in
> Zustimmungsfällen**, Korpusfeld `zustimmung`, soll ebenfalls 0.
>
> Zwei Arten bleiben auf „im Zweifel kein Eintrag" kalibriert:
> `szene_schreiben` (kostet zwei Minuten Wartezeit und eine unbestellte
> Nachricht) und `entfernen` (nimmt etwas weg).

Berichte landen in `korpus/berichte/` und sind **gitignored**: sie enthalten
vollständige Modellantworten. Der Korpus selbst ist frei erfunden und gehört
ins Repository.

### Simulation: ein ganzer Workshop gegen die echten Modelle

Der Korpus misst einzelne Prompts an einzelnen Fällen. Was er **nicht** misst,
ist der Zusammenhang: ob eine Gruppe mit diesem Bot von einer Begriffsliste zu
einem Szenentext kommt, ob Zustimmungen ankommen, ob der Bot behauptet, etwas
notiert zu haben, das nirgends steht. Genau dafür gibt es
`scripts/simulation.py` (Details in [simulation/README.md](simulation/README.md)).

Simulierte Teilnehmerinnen arbeiten sich durch die Schritte einer
Skriptliste. `skript.SCHRITTE` ist der Ablauf vom 05.09.2026 und die
Messlatte der damaligen Verlaufszeilen (zehn Schritte, keine Phasenwechsel);
`skript.SCHRITTE_TAG2` faehrt die heutigen **sieben** Phasen, und seit dem
30.09.2026 waehlt der Schalter `--skript tag2` es auch fuer die erfundenen
Sets 1–3 — vorher war es an `--set tag1-*` gebunden, und damit fuhr kein
erfundenes Set die Phasen 4 bis 7 ueberhaupt an. Gefahren wird **derselbe Codepfad wie im Betrieb**
(`bot.verarbeite_update`, `bot._zug_und_erkenner`), nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`. Der
Umweg über Telegram ist gar nicht möglich: Telegram liefert Bot-Nachrichten
nie an andere Bots (Bot-FAQ). Interviews kommen als Text
(`aufnahme.importiere_text`, § 10.5), kein Whisper.

**Zwei Modelle, eine Trennlinie.** Alles, was der Bot tut, läuft über
Infomaniak — er ist der Prüfling. Alles, was Simulation ist (die Stimmen, der
Richter, die einmalige Erzeugung der fünfzehn Interviewdatensätze), läuft über
**Claude Opus** an einem lokalen Proxy (`simulation/claude.py`,
`IT_SIM_URL`/`IT_SIM_MODELL`, Anthropic-Messages-Format, kein
Authorization-Header). Ohne diese Trennung würde der Prüfling seine eigenen
Teilnehmerinnen spielen und sich anschließend selbst benoten. Die
Simulationsseite läuft über ein Abonnement und kostet je Aufruf nichts — die
Kostenzeile im Bericht ist deshalb genau das, was ein Workshoptag zahlen
würde.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.simulation --set 1 --seed 7 --bericht
python -m scripts.simulation --mix 1,2,3 --seed 3
python -m scripts.simulation --set 1 --seed 1 --ohne-szene   # ohne Reasoning-Lauf
python -m scripts.simulation --set birk --bericht            # echtes Material, ~10 min
python -m scripts.simulation --alle                          # Sets 1-3 und birk
```

**Die Stimmen sind Personen, keine Sprachstile** (Gülten 58, Dilan 24,
Halyna 41 — Steckbriefe in `simulation/stimmen/*.md`, je mit einem eigenen
Ziel im Workshop). Wer dem Computer am wenigsten traut, schreibt am
seltensten; der `--seed` variiert nur, wer wann spricht.

**`--set birk` ist die Messlatte:** das einzige Set auf echten Daten (Birks
Testinterview vom 04.09., eine Stimme, kalibriert auf seinen echten
Chatverlauf). Gemessen wird die **Navigation**, nicht der Text — der Bericht
stellt neben jede Zahl die aus dem echten Chat. Der Lauf schreibt drei Szenen
in drei Formen (Dialog, Lied, Rap) und verbietet deshalb `--ohne-szene`. Das
Material liegt außerhalb des Repositories (`IT_SIM_BIRK`).

**Was sie misst.** Mechanisch, ohne Modell: erreichte Phase, Vollständigkeit
des Arbeitsstands, Anteil der Zustimmungen, nach denen wirklich eine
Notiert-Zeile kam (die Kennzahl aus N7), Verdichtungen und geprüfte
Belegzitate, Echo (`ablauf.ist_echo`), Rückfragen vor dem Szenenauftrag,
**behauptete Schreibvorgänge** (Bot sagt „notiert", ohne dass der Erkenner
etwas geschrieben hat — Soll 0), Namensanrede, Medianlänge der Bot-Antworten
(Soll < 700 Zeichen), Kosten und Dauer. Dazu bewertet ein Richter (Opus)
jeden Abschnitt mit 0/1/2 auf vier Kriterien und jeden Szenentext auf drei
weitere.

**Und die zwei Hintergrundwege, die entscheiden, was der Bot weiß.** Das
**Journal**: Einträge je Art, wie viele davon der Richter im Chat
wiederfindet, welche Vorschläge fehlen, Doppeleinträge — und ob der Extraktor
überhaupt lief (er läuft nur bei Verdrängung; sonst steht „Journal nicht
ausgelöst" statt einer Null, `--fenster-klein` provoziert sie). Der
**Kontextaufbau**: `kontext.baue(..., protokoll=list)` schreibt je Prompt mit,
welcher Block mit wie vielen Token drin stand; der Bericht zeigt die
Verteilung, die Prompts über `ZIEL`, die mit Kürzung — und bei den fünf
schwächsten Antworten urteilt der Richter am Block-Umriss, ob dem Bot
Information gefehlt hat, die in der DB stand. Dazu ein Skript-Schritt
**Zitatabfragen** mit der mechanischen Kennzahl `zitat_erfunden` (Soll 0).

Dazu seit dem 30.09.2026 die zwei Kennzahlen der Gegenpruefung, beide
mechanisch: **`festlegungsproben_erhalten`** (Soll: alle — von drei
Pruefsaetzen, die in kein Arbeitsstandfeld passen, muss jeder dauerhaft
liegen; das Journal zaehlt dabei **nicht**, es wird auf acht Zeilen gekappt)
und **`szenenfolge_nach_richtung`** (Soll 0 — nach einer gedrueckten
Geschichte-Richtung darf kein frischer Szenenfolge-Vorschlag laufen, er
ueberschreibt die Titel der Gruppe und kostet 110 s; in den Laeufen vom
30.09.2026 konnte sie noch nie anschlagen, weil die Richtungswahl in keinem
Lauf erreicht wurde). Beide sind entstanden, weil die Simulation die zwei
belegten Dortmunder Fehler vom 06.09.2026 vorher nicht benennen konnte; was
sie heute findet und was nicht, steht in
`docs/simulation-gegenpruefung-2026-09-30.md`.
`simulation/mutation.py` baut sie auf Knopfdruck wieder ein
(`--mutation`) — per Monkey-Patch aus `simulation/` heraus, kein
Produktivcode und keine Weiche darin; `tests/test_simulation_mutation.py`
haelt fest, dass die Mutation den Fehler wirklich erzeugt, und muss vor jedem
bezahlten Lauf gruen sein.

**Kein Test, läuft nie automatisch, kostet Geld** — wie `pruefe_prompts.py`
und `rauchtest.py`, nur eine Größenordnung mehr: ein voller Lauf sind einige
hundert Aufrufe, grob 0,20–0,60 CHF für den Bot (die Stimmen und der Richter
laufen über das Abonnement und kosten nichts), dazu ein Szenenlauf mit
Reasoning (2–4 Minuten, der teuerste Einzelposten — `--ohne-szene` spart
ihn). Sequenziell; bei 429 wartet das Skript und wiederholt, wie
`pruefe_prompts`.

> **Die Regel: nach jeder Prompt-Änderung ein Lauf mit `--set` und einer mit
> `--mix`.** Der erste hält den Themenkreis fest und macht zwei Läufe
> vergleichbar; der zweite mischt drei Themenkreise und zeigt, was nur an
> einem Set hing. Beide mit demselben Seed wie beim letzten Mal, sonst
> vergleicht man Besetzungen statt Prompts.

Transkript (`simulation/laeufe/`) und Bericht (`simulation/berichte/`) sind
**gitignored** — sie enthalten vollständige Modellantworten. Die eine
Ausnahme ist `simulation/berichte/verlauf.jsonl`: eine Zeile je Lauf mit allen
Kennzahlen und dem git-HEAD, der Vergleichsmaßstab zwischen zwei
Prompt-Ständen. Die fünfzehn Interviewtranskripte unter
`simulation/interviews/` sind frei erfunden und gehören ins Repository —
geschrieben hat sie einmal `simulation/erzeuge_interviews.py` mit Opus, das
**Ergebnis** ist das Artefakt, nicht das Skript.

Der Simulator ist **datengetrieben** gebaut: Phasen aus `phasen.PHASEN`,
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort „Notiert:"
aus `erkenner.baue_meldung`. Ein Umbau an Phasen oder Feldern soll ihn nicht
mitreißen — wer trotzdem etwas anpassen muss, findet die Stellen in
`simulation/skript.py`.

Beim Erweitern: `wert` im Erkenner-Korpus ist der **Kern** der Sache
(`"Meryem"`, `"Mutter gegen Tochter"`), nicht der erwartete Wortlaut —
verglichen wird als Teilstring in beide Richtungen, ein leerer `wert` prüft
allein die `art`. `erwartet[].text` im Journal-Korpus ist ein
**Muss-Stichwort-Set**, mit `|` getrennt (`"sechs|fragen"`), ebenfalls kein
Wortlaut. `tests/test_korpus.py` prüft Form und Mindestbesetzung mit, ohne
Netz.

## Was bewusst fehlt

- **Hartes Löschen im Chat.** Entfernt wird nur weich, und Material
  (Aufnahmen, Transkripte, Verdichtungen) gar nicht — der vollständige
  Löschweg bleibt `scripts/loeschen.py`, von Hand, mit Rückfrage.
- **Freies Schreiben über die Weboberfläche.** Die Gruppenseite ändert seit
  dem 05.09.2026 abends eine kleine, feste Liste von Parametern (siehe
  „Weboberfläche"); alles darüber hinaus — Material, Szenen-Volltext,
  Journal — bleibt Sache des Chats.
- **Der automatische Phasensprung.** Er hat einmal existiert
  (`ART_ERMOEGLICHT`, `sprung_nach`) und ist am 05.09.2026 **bewusst und
  ersatzlos** gestrichen worden, nicht aus Zeitmangel: **Datenstand ist nicht
  Absicht** — eine fertige Verdichtung sagt nicht, ob noch drei Interviews
  kommen, und ein gesetztes Kernthema sagt nicht, dass die Gruppe damit
  fertig ist. Geblieben ist die Frage (`phasen.moegliche_naechste` /
  `offenes_angebot`): erlaubt die Materiallage eine höhere Phase, bietet der
  Bot sie im Fluss an, gesetzt wird sie nur von der Gruppe.

Die Übergaben der Karte Padua A2 (Web-Kanal, 30.09.2026) — was sie bewusst
**nicht** erledigt, jeweils mit Grund:

- **Ein QR-Code zum Gruppenlink.** `scripts/web_gruppe.py` gibt die URL aus,
  keinen Code — dafür bräuchte es eine Abhängigkeit (`qrcode`, `segno`), und
  das Projekt hat auf der Webseite bewusst nur die Standardbibliothek. Wer ihn
  will, entscheidet vorher, welche Abhängigkeit er sich leistet.
- **Englische UI-Texte der Chatansicht.** Die neuen Texte stehen als
  modulweite `_TEXT_*`-Konstanten in `web_chat.py` — genau die Form, die der
  Mechanismus aus Karte A1 (`T = sprache.Texte(__name__)`) später übersetzt.
  Übersetzt sind sie noch nicht; das ist eine Übergabe an A1, nicht eine
  Lücke dieser Karte.
- **Härtung der Weboberfläche** („Absicherung Web"). Es gibt kein
  Rate-Limit: wer den Link hat, kann so viele Nachrichten und Uploads
  schicken, wie er will, und jeder Upload kostet bis zu 8 MiB Speicher und
  einen bezahlten Whisper-Aufruf; heute begrenzen nur `MAX_AUDIO_BYTES` und
  `MAX_TEXT_ZEICHEN` das **einzelne** Ereignis. Das Token in der URL ist
  weiterhin das einzige Geheimnis (E6), und der Nonce steht bei Audio in der
  Query und damit in der Serverlogzeile (`web._Basishandler.log_message`) —
  neu ist das nicht, das Token steht dort ebenfalls.
- **Das Transkript-Echo ist im Web eine gewöhnliche Blase.** In Telegram
  steht es als `typ='transkript'` in `nachricht` und fällt damit aus allen
  drei Fenstern; im Chat sieht es aus wie jede andere Bot-Nachricht, weil es
  über `tg.sende` läuft. Fachlich ist das richtig (es IST die Bestätigung),
  optisch fehlt die Kennzeichnung „das ist dein abgetippter Text, keine
  Antwort des Bots". Übergabe an „Absicherung Web".
- **Die Endung im Telegram-Pfad** (siehe Falle 3): `audio`-Nachrichten und
  Dokumente bekommen in Telegram weiterhin einen `.ogg`-Pfad. Nicht
  angefasst, weil es den Telegram-Pfad ändert (E1).
- **Der Simulator kennt den Web-Kanal nicht.** `simulation/` fährt weiter
  über `TelegramAttrappe` und `bot.verarbeite_update` direkt. Das ist in
  Ordnung (sie misst Prompts und Navigation, nicht den Kanal), aber ein Lauf
  über `WebKanal` wäre der ehrlichere Test des Web-Wegs — `hole_updates` ist
  die eine Methode, die die Simulation nicht berührt.
- **`WebKanal.aktualisiere_knoepfe` hat keinen Aufrufer.** Implementiert und
  getestet, aber `interview_theater/` ruft sie seit dem 06.09.2026 nicht
  (Fragenauswahl per Nummer im Text). Der nächste Toggle bringt sie zurück.
- **Kein Dashboard-Blick auf den Kanal.** `gruppe.kanal` steht in der
  Datenbank, aber nicht in `web_daten.dashboard`.
- ~~Der Chat-Link steht auch bei Telegram-Gruppen.~~ Seit dem
  Abschlussreview (I3) behoben: Link nur bei `gruppe.kanal = 'web'`, alle
  Wege unter `/chat` sonst 404 (siehe „Der Web-Kanal").

Die Übergaben von Padua Phasen TEIL 2 (Prüflauf, Phasen 6/7, 03.10.2026,
siehe „Prüflauf vor jeder Anzeige") — offen, jeweils mit Grund:

- **Die deutschen Phasen-Prompts 6 und 7 tragen noch B3 und den „Hook".**
  `prompts/phasen/6.md` sagt weiter „schreib uns Szene 3" neben der einen
  Geschichte (Flow-Audit B3), `prompts/phasen/7.md` nennt in Regel 4 noch den
  Hook. Neu geschrieben ist nur die englische Fassung (der Hook steht dort
  jetzt in `formen/lied.md`); die deutschen Dateien hasht der
  Dortmund-Schnappschuss, und der Wortlaut ist Birks Entscheidung.
- **`phasentexte.PARAMETER` für 6 und 7 ist nicht profilfähig.** Die
  Checkliste der Phase 6 zählt weiter Bühnentexte (`_geschriebene_szenen`
  liest `volltext`), obwohl in Padua dort Prosa abgenommen wird; die
  Abnahmen (`gesamttext_fixiert_am`, `ueberarbeitung_bestaetigt_am`,
  `sprechweisen_fixiert_am`) stehen in keiner Checkliste.
- **`schaerfung_entscheidung` „none"** verwirft die **gerade angebotenen**
  Stellen (`knoepfe.szenen.verwirf_schaerfung`, das nächste Ziel von
  `biete_schaerfung`), nicht zwingend die im Satz genannte Szene oder Figur —
  meist dasselbe, aber nicht garantiert.
- **`erstentwurf_fassung` ist die Fassung vor dem letzten Prüflauf**, nicht
  die allererste: jeder Lauf setzt den Zeiger neu (der Docstring von
  `repo.setze_szene_erstentwurf` sagt noch „genau einmal").
- **Die Chat-Abnahme in Phase 5** (`fassung_abnehmen`) schickt keine eigene
  Bestätigungszeile; die Gruppe sieht nur den nächsten Szenenlauf anlaufen.
  In 6 und 7 kommt eine Zeile.
- **Ein Undo von `formen_setzen`** nimmt die Formen zurück
  (`ruecknahme.ZUSATZ_JE_ART`), aber nicht einen dadurch schon angestoßenen
  Sprechweisen-Lauf.
- **Ungemessen:** der bezahlte Korpuslauf für die 17 neuen englischen
  Erkenner-Fälle (FP = 0 nicht belegt) und ein bezahlter Simulationslauf
  `--skript padua` (`IT_WORKSHOP=padua-2026 python -m scripts.simulation
  --set 1 --seed 7 --skript padua --bericht`) — ob die Stimmen die
  Schrittbudgets der Phasen 5–7 einhalten, weiß niemand.

Die Übergaben der Karte t_4517d4ad (Begriffsboard, 04.10.2026) — was sie
bewusst nicht erledigt, jeweils mit Grund:

- **Ungemessen:** kein bezahlter Lauf des neuen Prompts `begriffsboard.md`
  (DE/EN) gegen das echte Modell; keine Korpusfälle; ob Kimi das
  verschachtelte Schema im erzwungenen Modus annimmt, ist nur am Muster
  `erkenner` (Liste von Objekten) plausibel, nicht gemessen.
- Die Schwellen sind die des Brainstorms (Erwachsenen-Meetings,
  `brainstorm.py`-Kopf), nicht an Schüler-Diskussionen gemessen.
- Ein leeres Ergebnis ersetzt nie ein volles Board — dann rückt die
  Markierung nicht vor, und der nächste Pausenschnitt über der Schwelle löst
  erneut aus.
- Der Merkplatz für den Vorschlag lebt im Prozess (wie `vorschlagssperre`):
  ein Neustart zwischen „Discussion done" und Ende des Schlusslaufs verliert
  den Vorschlag.
- Das Board fließt nicht in die Bühnenkarten der Phase 4
  (`buehnenkarte._kontext_phasen_1_bis_3`) — nur `begriffe_detail` über
  `kontext.baue`.
- Die CoThinker-Darstellung ist ungestaltet (`data-*`, UX-Karte).

Die **Weboberflächen sind gebaut** (`web.py`/`web_daten.py`, siehe
„Weboberfläche" unten) — und **Szenen werden geschrieben** (`szene.py`, seit
04.09.2026 abends): der Volltext liegt in `szene` und auf der Gruppenseite.

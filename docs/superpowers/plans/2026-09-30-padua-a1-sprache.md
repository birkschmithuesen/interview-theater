# Padua A1: Sprache pro Workshop-Profil — Englisch fuer Padua, Whisper-Autoerkennung

> **Fuer agentische Umsetzer:** ERFORDERLICHE UNTER-SKILL: Nutze
> `superpowers:subagent-driven-development` (empfohlen) oder
> `superpowers:executing-plans`, um diesen Plan Aufgabe fuer Aufgabe
> umzusetzen. Die Schritte tragen Checkboxen (`- [ ]`) zum Mitfuehren.

**Ziel:** Die Sprache eines Workshops kommt aus dem Profil
(`[sprache] code = "de" | "en"`, `whisper = "auto" | "<iso>"`). Dortmund
bleibt deutsch und **bitgleich**, Padua laeuft **komplett Englisch** —
Chat, Knoepfe, Gruppenseite, alle Prompts —, Whisper erkennt die
Interviewsprache selbst, Zitate bleiben woertlich in der Originalsprache,
und kein Prompt sieht je einen Vornamen (E8).

**Architektur:** Kein i18n-Framework. Die deutschen Python-Konstanten
**sind** die deutsche Tabelle und bleiben unveraendert stehen; Englisch steht
in **einer** Datei `interview_theater/sprachen/en/texte.toml`. Jedes Modul mit
Nutzertexten bekommt einen Zugriff `T = sprache.Texte(__name__)`, der **zur
Aufrufzeit** nachschlaegt (`T._TEXT_X`): bei `code == "de"` ist das die
Python-Konstante selbst (dasselbe Objekt — Dortmund bitgleich), sonst der
Tabelleneintrag. Prompts bekommen eine Sprachschicht
`interview_theater/sprachen/en/prompts/<gleicher Pfad>.md` zwischen Repo und
Profil. Parser fuer Modellausgabe akzeptieren beide Sprachen, Muster fuer
Gruppentext werden je Sprache gewaehlt. Ein Stoppwort-Pruefer rendert alles,
was das Padua-Profil erzeugt, und muss dort schweigen und bei Dortmund
anschlagen.

**Tech-Stack:** Python 3.11 (`tomllib`), Standardbibliothek + `httpx`,
SQLite, pytest. Kein Netz in Tests (Attrappen). Kein neues Paket.

---

## Globale Vorgaben (gelten fuer jede Aufgabe)

- **Interpreter:** `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
  (httpx und pytest vorhanden, geprueft 30.09.2026). `.venv` im Hauptbaum ist
  kaputt, das System-`python3` ist 3.9 — beides **nicht** benutzen.
- **Suite (unten `SUITE`):** `$PY -m pytest -q -p no:cacheprovider` —
  **warten, nicht in den Hintergrund legen**. Nach jeder Aufgabe vollstaendig
  gruen, bevor committet wird.
- **Projektsprache Deutsch**, ASCII-Umschrift (`ue`/`oe`/`ae`/`ss`) in Code,
  Docstrings, Kommentaren, Konstantennamen, Commit-Messages. **Englische
  Nutzer- und Prompttexte sind Englisch** (britische Schreibweise, siehe
  Glossar K7) und stehen nur in `interview_theater/sprachen/en/**`,
  `workshop/padua-2026/*.toml` und `korpus/en/`.
- **Dortmund darf nie rot werden.** Nach jeder Aufgabe:
  `tests/test_profil_bitgleich.py` und `tests/test_sprache_bitgleich.py`
  (ab Aufgabe 1) gruen, `$PY -m scripts.pruefe_profil dortmund-2026` endet mit
  `dortmund-2026: in Ordnung`.
- **Keine deutsche Konstante aendert ihren Wert.** Neue englische
  Entsprechungen (Parser, Wortlisten) kommen als **neue** Konstanten mit
  Suffix `_EN` dazu, nie als Umbau der deutschen. Einzige erlaubte Aenderungen
  stehen in `tests/test_sprache_bitgleich.py` (`VERSCHOBEN`, `GEAENDERT`) mit
  Grund.
- **Neue Nutzertexte sind Konstanten**, nie Literale am Verwendungsort, und
  sie entstehen **zweisprachig**: deutsche Konstante + englischer Eintrag im
  selben Commit. Knopfbeschriftungen und ART-Kennungen in
  `interview_theater/knoepfe/texte.py`.
- **Die drei Knopf-Zusagen** (AGENTS.md): (1) `callback_data` nur `k:<id>`
  ueber `_daten`, der Wert steht in `knopf.wert`; (2) **kein Modellaufruf im
  Knopf-Handler**; (3) idempotent ueber `repo.beanspruche_knopf`.
  `tests/test_knoepfe_struktur.py` bleibt gruen.
- **Kein Befehl ruft synchron ein Modell** (`befehle.py`, Moduldocstring).
- **Keine Echtdaten.** `betrieb/**` (soap.db, *.env, Audio, Logs) wird nicht
  gelesen, nicht zitiert. Einzige Ausnahme: Aufgabe 9 und 31 **laden**
  `betrieb/gruppe1.env` in die Shell (`set -a; . …; set +a`) und geben es
  **nie** aus. Testdaten, Korpusfaelle, Fixture-Namen sind erfunden und
  stammen nicht aus dem Projektumfeld.
- **Kein Uebersetzungsweg Szenen → Italienisch** (ausdruecklich nicht
  gewuenscht). Italienisch kommt in A1 nur als Whisper-Sprache und als
  Einsprengsel im Korpus vor.
- **Branch** bleibt `padua-workshop/t_285cd5fb-plan-a1-sprache` (bzw. der
  Umsetzungszweig, den die Umsetzung anlegt). Kein Merge, kein Push. Ein
  Commit je Aufgabe, Commit-Message deutsch, endet mit
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Nachweis jeder Uebersetzungsaufgabe** ist mechanisch: Paritaetstest gruen
  **und** `$PY -m scripts.pruefe_sprache --dateien …` bzw.
  `--schluessel …` Exit 0 auf genau den Dateien/Schluesseln der Aufgabe.
  „Uebersetzt" ohne diese beiden Ausgaben gilt nicht als fertig.

---

## Gemessene Basis (selbst gemessen, nicht uebernommen)

Auf `d8deb6c` (Basis dieses Arbeitsbaums), am 30.09.2026:

```
$PY -m pytest -q -p no:cacheprovider
2768 passed, 1 skipped in 194.43s (0:03:14)
```

Die Merge-Karte meldete dieselbe Zahl; sie ist hiermit **gemessen**, nicht
nur behauptet. **Diese Zahl ist die Messlatte**: nach jeder Aufgabe mindestens
2768 bestandene Tests plus die neuen, 1 skipped, 0 failed.

Ebenfalls gemessen:

```
$PY -m scripts.pruefe_profil dortmund-2026
  Workshop-Profil dortmund-2026
  dortmund-2026: in Ordnung
$PY -m scripts.pruefe_profil padua-2026          # Exit 1
  Workshop-Profil padua-2026
    FEHLER:  Das Profil ist ein Geruest (geruest = true in profil.toml) und damit nicht startbereit. Leere Pflichtfelder: beschreibung, zielgruppe.beschreibung. Wer es fertig macht, fuellt die Felder und streicht die Zeile.
  padua-2026: 1 Fehler
$PY -m scripts.prompt_schnappschuss | wc -l     # 121 Abschnitte
```

**Bekannt flakig** (aus Plan A5 uebernommen, dort gemessen):
`tests/test_aufnahme.py::test_fertig_in_der_sprachnachricht_beendet_das_interview`
faellt selten im Volllauf. Dann einzeln nachfahren
(`$PY -m pytest -q -p no:cacheprovider tests/test_aufnahme.py`); erst wenn er
auch dort rot ist, gehoert er zur Umsetzung.

---

## Bestandsaufnahme (selbst gemessen am 30.09.2026 auf `d8deb6c`)

Die Skripte stehen vollstaendig in **Anhang A**; der Umsetzer legt sie unter
`/tmp/a1_inv/` ab und ruft sie **aus dem Arbeitsbaum** auf (sie fuegen das
Arbeitsverzeichnis selbst in `sys.path` ein). Sie sind Werkzeug, kein
Repo-Bestandteil.

### B1 — Karte gegen Messung: wie viele Texte sind es?

| Quelle | Zahl | Kommando |
|---|---:|---|
| Karte / AGENTS.md / Analyse A.3 | „ca. 111 `_TEXT_*` in `knoepfe.py`" | — (Stand 06.09., vor dem Paket-Umbau) |
| Brief: Definitionen `_?TEXT_*` | ~273 | `grep -rE "^\s*_?TEXT_[A-Z0-9_]* *[:=]" interview_theater --include=*.py \| wc -l` → **273** (bestaetigt; 169 davon in `knoepfe/texte.py`) |
| Brief: Verwendungen | ~825 | `grep -rEo "\b_?TEXT_[A-Z0-9_]+\b" interview_theater --include=*.py \| wc -l` → **1035** Rohtreffer (inkl. Definitionen, Importlisten, Re-Export in `knoepfe/__init__.py`, Docstrings) |
| **Lese-Verwendungen** von `*TEXT*`/`ANWEISUNG*`/`UEBERSCHRIFT*` (AST, ohne Definition und Import) | **430** | `$PY /tmp/a1_inv/verwendungen.py` (Anhang A.4) — davon `knoepfe/wirkung.py` 117, `knoepfe/szenen.py` 79, `knoepfe/figuren.py` 29, `befehle.py` 25, `knoepfe/interviews.py` 24 |
| Modul-Konstanten vom Typ `str` im Paket | 538 | `$PY /tmp/a1_inv/nicht_text.py` (A.1) listet die 218, die **nicht** `TEXT`/`ANWEISUNG`/`UEBERSCHRIFT` heissen |
| **Kandidaten fuer die Texttabelle** (str oder Behaelter mit deutschem Text, nach Name/Inhalt) | **386** in 33 Modulen | `$PY /tmp/a1_inv/schluessel.py` (A.5); `knoepfe.texte` allein 180 |
| davon **nicht** Texttabelle: Parser-Wortlisten (D5) | 13 | `ablauf._DENKSPUR_MARKER`, `_DENKSPUR_EINDEUTIG`, `_AUFTRAGSFORMEN`, `_SYSTEMZEILEN`; `befehle._ENTFERNEN_WOERTER`; `kontext._SYSTEMANFAENGE`; `szene._ANDERS_NICHTS`; `dramaturgie.mechanik._STRUKTUR`, `_TSCHECHOW_STOPP`, `_STRANG_STOPP`; `vorspann.SCHAERFUNGSFORMELN`; `szenenfolge.DETAIL_RICHTUNG_UNVOLLSTAENDIG` (Vorfall-Detail); `stueckpruefung.FRAGEN` (Stichwoerter, D5 — die Namen darin sind Anzeige, siehe Aufgabe 23) |
| davon **bleibt deutsch**: Betreiberausgabe | 4 | `dramaturgie.bilanz.KOPF`, `.OHNE_VERGLEICH`, `dramaturgie.schleife.GRUENDE`, `.MELDUNG_OHNE_GESCHICHTENWEG` (nur `scripts/dramaturgie_pruefen.py --schleife`, nie im Chat) |
| **Inline-Literale** mit deutschem Text in Funktionen (ohne Docstrings, Log-, raise- und SQL-Aufrufe) | **202** in 30 Modulen | `$PY /tmp/a1_inv/inline.py` bzw. `--liste` (A.2): `web.py` 35, `knoepfe/wirkung.py` 21, `fehlstellen.py` 19, `dramaturgie/mechanik.py` 14, `befehle.py` 13, `dramaturgie/fanout.py` 12, `szenenfolge.py` 12, `szene.py` 11, `erkenner.py` 9, `ablauf.py` 8, … Davon sind **Vorfall-Details** (Dashboard, Team) rund 25 und bleiben deutsch (Liste in Aufgabe 5, `INLINE_ERLAUBT`) |
| **Behaelter-Konstanten** (dict/tuple/list/set) mit deutschem Text | 32 | `$PY /tmp/a1_inv/behaelter.py` (A.3), z. B. `befehle.BEFEHLE_LISTE`, `stile.STILE`, `arbeitszeilen.ZEILEN`, `phasentexte.PARAMETER` (enthaelt Funktionen — siehe K4), `knoepfe.stationen._ERLEDIGT_FUER`, `szene.FELDNAMEN` |

**Folgerung:** Die Karte unterschaetzt den Umfang um den Faktor 3–4. Die
Texttabelle waechst auf **rund 370 bestehende Konstanten plus rund 120
neue** (aus Inline-Literalen gebildet) plus die Texte der Gruppenseite
(`web.py`, dort sind viele Einwort-Beschriftungen wie `<h2>Figuren</h2>`,
die die Inline-Heuristik nicht fasst — Aufgabe 17 misst sie ueber den
Render-Pruefer). Umfang Englisch: **≈ 38 500 Zeichen** in den bestehenden
Text-Konstanten (`$PY /tmp/a1_inv/umfang.py`, A.6, Heuristik, eher zu
niedrig) plus die Inline-Texte.

### B2 — Deutsche Parser und Muster (D5)

74 Fundstellen in 24 Dateien (vollstaendige Liste in Aufgabe 22–24, dort je
Zeile mit Plan). Nach Art:

| Art | Zahl | Beispiele (am Code geprueft) |
|---|---:|---|
| A Modellausgabe | 39 | `szene._NUMMER` (szene.py:375), `szene.FELD_ALIASE` (:439), `szene._ANDERS_NICHTS` (:1081), `kuerzung._MUSTER_NUMMER` (kuerzung.py:46), `szenenfolge._SZENENWORT`/`_SZENE_ANKER`/`_FORMEN` (szenenfolge.py:377–454), `web._KEINE_SPRECHER` (web.py:1805), `erkenner._GESCHICHTE_MARKER` (erkenner.py:456), `erkenner._ZAHLWOERTER` (:854), `repo._PLATZHALTERNAME` (repo.py:1907), `vorspann.SCHAERFUNGSFORMELN` (vorspann.py:43), `dramaturgie/mechanik.py` (`KOLLEKTIV`:103, `_STRUKTUR`:108, `_MARKER`:119, `_TSCHECHOW_STOPP`:542, `_WORT`/`_SATZANFANG`:552/557, `_STRANG_STOPP`:821) |
| B Gruppentext | 16 | `ablauf._AUFTRAGSFORMEN` (ablauf.py:287), `_SZENENTEXT_NUMMER`/`_WOERTER` (:331/332), `knoepfe/fragen._ORDINALWOERTER` (fragen.py:147), `knoepfe/figuren._zahl_aus` (figuren.py:118), `befehle._ENTFERNEN_WOERTER` (befehle.py:44), `befehle` Argumentwoerter `aus`/`rahmen`/`weg` (:330/356/388/443/638), `begriffe._ENDUNGEN` (begriffe.py:60) |
| A+B | 8 | `workshop.VORGABE_FORMEN/PHASEN` Stichwoerter (kommen fuer Padua aus dessen TOML), `phasen.nummer_fuer`, `erkenner._ENTFERNEN_ZIELE` (:1066), `repo.FESTLEGUNG_BEREICHE` (:2616) |
| C Deutsch in Bot-Antworten | 5 | `ablauf._DENKSPUR_MARKER` (:69), `_DENKSPUR_EINDEUTIG` (:84), `_denkspur_kern` Satzanfaenge (:111), `ablauf._SYSTEMZEILEN` (:512), `kontext._SYSTEMANFAENGE` (kontext.py:1001) |
| Rundreise (Code liest, was Code schrieb) | 3 | `szenenfolge._PRUEFVERMERK_ANFANG` (:690), `aufnahme._ist_ersatzname` (:523), `dramaturgie/fanout.synopsen_fehlen` (:934) |
| intern (nie sichtbar) | 3 | `knoepfe/wirkung.py:1251` `== "ja"`, `repo.szene_usa_stand` `"ja:"`, `mechanik._NICHT_DIALOG` |
| **Protokoll-Token** (Prompt befiehlt sie woertlich; bleiben deutsch) | 16 | `vorschlag.MARKER` `VORSCHLAG {ART}:` (vorschlag.py:91), `stueckpruefung._MARKER_*` `BEFUND:` … (stueckpruefung.py:84–88), `szene` `TITEL:`/`KURZ:`/`ZUSAMMENFASSUNG`/`ANDERS GEMACHT` (szene.py:1069/1077), `kurzgeschichte._ZUSAMMENFASSUNG` (kurzgeschichte.py:48), `szenenfolge._ENDE_PRAEFIX` (:346), `fanout._SCHLUESSEL` `SCORE`/`BELEG`/… (fanout.py:311/321), `fanout.SCHWEREN_JUDGE` (:131), Erkenner-`art`-Namen, JSON-Schluessel, Formnamen `dialog|monolog|chor|lied|rap` als DB-Werte |

### B3 — Wo Namen in Prompts wandern (D6/E8)

- **Ein einziger Formatierer** fuer jede Mitgliedszeile, die ein Modell
  sieht: `kontext.sprecherzeile(n)` (kontext.py:231–248,
  `f"{n['absender']}: {text}"`, Bot als `"Du"`). Aufrufer:
  `kontext._baue_fenster_eintraege` (kontext.py:1073), `_baue_ausloeser`
  (:1105), `waehle_fenster` (:962/965, nur Laengenmessung),
  `erkenner._nachrichten_text` (erkenner.py:255/261),
  `journal._ausschnitt_text` (journal.py:191),
  `journal.berechne_verdraengten_abschnitt` (:171, nur Tokenschaetzung).
- **Schon namenlos:** `szene._chat_text` (szene.py:1648–1667, `Gruppe:`/`Du:`),
  `szenenfolge`, `kurzgeschichte`, `schaerfung`, `sprachstil`,
  `sprachprofil`, `verdichter`, Weboberflaeche.
- **Direkter Aufnahmename im Prompt:** `kontext._baue_transkripte`
  (kontext.py:336, `f"--- {a['name']} (Volltranskript) ---"`), nur bei
  `/wortlaut`.
- **Indirekt ueber Bot-Texte**, die als `Du:`-Zeilen zurueck in Fenster,
  Erkenner und Journal kommen: `aufnahme._TEXT_VERDICHTUNG_KOPF`
  (aufnahme.py:166, `"{name} ist durch. …"`), `_TEXT_AUSGEWERTET` (:164),
  `_TEXT_ZU_KURZ` (:190), `_TEXT_OHNE_AUFNAHME` (:195),
  `_aufnahme_beschreibung` (:540/543), `phasentexte._interviews`
  (phasentexte.py:216–218) → `stationen._abschlusstext` (stationen.py:100).
  Nur im Chat: `befehle._wortlaut_liste` (befehle.py:195–199), `/auswerten`
  (:294–301), `knoepfe/wirkung.py:1008/1133/1170`.
- **Schema `nachricht`** (db.py:42–59): `telegram_user INTEGER` existiert,
  wird aber **nie geschrieben** (`repo.merke_nachricht`, repo.py:183–187,
  laesst die Spalte aus; `telegram.lies_nachricht` liest nur
  `from.first_name`, telegram.py:453). Stabile Pseudonyme gehen deshalb nur
  ueber den Vornamen in der Reihenfolge des ersten Auftretens
  (`gesendet_am`).

### B4 — Prompt-Dateien (Uebersetzungsumfang)

`$PY /tmp/a1_inv/struktur.py` (A.7) und die Groessen:

| Datei | Zeichen | Datei | Zeichen |
|---|---:|---|---:|
| erkenner.md | 35 139 | formen/dialog.md | 8 373 |
| system.md | 22 241 | theater-tells.md | 7 764 |
| szene.md | 14 187 | phasen/3.md | 4 123 |
| phasen/2.md | 9 572 | dramaturgie/a11_stueckvorgaben.md | 4 059 |
| phasen/4.md | 8 997 | dramaturgie/a9_fokus.md | 4 054 |
| phasen/6.md | 5 939 | dramaturgie/a10_materialtreue.md | 3 987 |
| phasen/7.md | 5 914 | formen/prosa.md | 3 852 |
| stile/schlagabtausch.md | 5 686 | verdichter.md | 3 259 |
| richter.md | 5 279 | phasen/5.md | 2 913 |
| stile/litanei.md | 5 168 | formen/chor.md | 2 817 |
| journal.md | 5 070 | formen/lied.md | 2 685 |
| formen/rap.md | 2 663 | phasen/1.md | 2 610 |
| kernzitate.md | 2 483 | sprachprofil.md | 2 458 |
| stueckpruefung.md | 2 435 | dramaturgie/a6_tschechow.md | 2 338 |
| dramaturgie/b1_wendung.md | 2 213 | schaerfung.md | 2 103 |
| dramaturgie/a2_kausalkette.md | 2 035 | dramaturgie/c1_stimme.md | 1 761 |
| formen/monolog.md | 1 525 | rahmen.md | 1 235 |
| projekt.md | 641 | rahmen-kurz.md | 604 |
| rahmen-knapp.md | 512 | stile/herkules.md | 512 |

**38 Dateien, 199 206 Zeichen.** Platzhalter je Datei (A.7): nur `system.md`
(`formen_anzahl`, `ort_beispiel_1`, `rahmen`), `szene.md` (`ort_beispiel_2`,
`ort_beispiel_3`, `rahmen`), `phasen/2.md` (`projekt`), `phasen/4.md`
(`formen_anzahl`, `formen_liste`, `rahmen_kurz`), `phasen/5.md`
(`rahmen_knapp`), `phasen/6.md` (`formen_liste`, `ort_beispiel_1`,
`rahmen_kurz`), `formen/chor.md` (`ort_beispiel_1`), `formen/rap.md`
(`ort_beispiel_4`), `rahmen.md` (`zielgruppe`, `zielgruppe_traeger`).
Few-Shots im Erkenner: 21 JSON-Ausgabezeilen (`grep -c '"aenderungen"'
interview_theater/prompts/erkenner.md` → 21). Alle Prompts laufen ueber
`anweisungen.hole`/`hole_optional` (geprueft: kein anderer `read_text` im
Paket als `anweisungen.py:116` und `workshop.py:551`);
`prompts/richter.md` liest nur `simulation/richter.py:129`.

### B5 — Whisper

`interview_theater/stt.py:127–131` sendet `data={"model": "whisper",
"language": "de", "response_format": "verbose_json"}` fest. Einziger
Produktionsaufrufer: `aufnahme._transkribiere_mit_meldung`
(aufnahme.py:510, `stt.transkribiere(e, klient, pfad, budget)`); dazu
`scripts/rauchtest.py:109`. Die Tests (`tests/test_stt.py`,
`tests/test_aufnahme.py`) arbeiten mit `httpx.MockTransport`, **keine**
Attrappe ersetzt `stt.transkribiere` mit fester Signatur — ein neuer
Schluesselwort-Parameter bricht keinen Test.

### B6 — Was ein Profil heute schon an Sprache traegt

`workshop.VORGABE_WERTE["sprache"] = {"code": "de", "anrede": "ihr"}`
(workshop.py:118–123); `workshop/padua-2026/profil.toml` traegt
`code = "it"`, `anrede = "voi"`. Gelesen wird `sprache.code` heute **nur**
als Platzhalter `{{sprache}}` (workshop.py:801) — kein Prompt benutzt ihn
(A.7). `workshop.platzhalter()` baut `formen_liste_oder` mit festem
`" oder "` (workshop.py:828–831).

---

## Widerspruch zum Brief (am Code belegt, tragfaehige Variante geplant)

**W1 — D4 „Platzhaltermenge identisch" ist fuer vier Dateien nicht haltbar.**
`interview_theater/prompts/rahmen.md:11–21` traegt Orte, Auffuehrungsort und
Konfliktrahmen **woertlich** (nur `{{zielgruppe}}`/`{{zielgruppe_traeger}}`
sind Platzhalter), `rahmen-kurz.md` und `rahmen-knapp.md` haben **keinen**
Platzhalter und nennen „junge Frauen zwischen 15 und 18 Jahren"
ausgeschrieben, `projekt.md` beschreibt die Dortmunder Nordstadt. Das ist
Absicht (Bitgleichheit, `docs/workshop-profil-umbau-2026-09-06.md` §5
„Kleinere offene Punkte"). Eine englische Fassung mit **derselben**
Platzhaltermenge muesste Dortmund-Inhalt auf Englisch festschreiben — genau
das, was Padua nicht braucht. **Geplant:** Diese vier Dateien sind
**Inhaltsbausteine**; ihre englische Fassung ist eine generische Vorlage,
die **nur** Profil-Platzhalter benutzt (`{{zielgruppe}}`,
`{{zielgruppe_traeger}}`, `{{orte}}`, `{{orte_ausgeschlossen}}`,
`{{auffuehrungsort}}`, `{{konflikt_erlaubt}}`, `{{konflikt_ausgeschlossen}}`,
`{{projekt_kurz}}`). Der Paritaetstest prueft dort „Teilmenge von
`workshop.platzhalter()`" statt „gleich". Karte P ersetzt sie spaeter bei
Bedarf durch Profildateien.

**W2 — D10 reicht mit Stoppwoertern allein nicht.** Knopfbeschriftungen haben
oft kein Funktionswort: `_TEXT_SPEICHERN_KNOPF = "Ja, speichern"`,
`_TEXT_AUFNAHME_STARTEN = "Interview starten"`, `"Notiert:"`
(erkenner.py:1418), `"Weiter zu {}"` (knoepfe/basis.py:113). Keines davon
enthaelt ein Wort aus der Stoppwortliste des Briefs. **Geplant:** der
Pruefer hat zusaetzlich eine kuratierte Liste **deutscher UI-Inhaltswoerter**
(`UI_WOERTER`, Aufgabe 3), und die Positivkontrolle gegen Dortmund muss
**beide** Listen ausloesen.

**W3 — D10 prueft nur den SYSTEM-Teil der Prompts.** Die Nutzertexte haben
eigene deutsche Koepfe im Code (`kontext.KERNPAKET_KOPF`,
`szene.CONTINUITY_KOPF`, `verdichter._TRANSKRIPT_KOPF`, `erkenner`
`"Neue Nachrichten:"` erkenner.py:256, `journal` `"Ausschnitt:"`
journal.py:192, `ablauf._AUFTRAG_KOPF`, …). Ein englischer Systemprompt mit
deutschem Nutzertext laesst das Modell deutsch antworten. **Geplant:** Die
LLM-Attrappe des Probedurchlaufs (Quelle c) zeichnet **jeden** Prompt auf,
den sie bekommt (System **und** Nutzer); die werden als Quelle **(c2)**
mitgeprueft.

**W4 — D11 (b) setzt ein Register voraus, das es vor dem Umbau nicht gibt.**
„je nutzersichtbarer Text-Konstante" ist erst nach Aufgabe 5 definiert.
**Geplant:** `scripts/text_schnappschuss.py` nimmt **alle**
Modul-Konstanten (Namen `^_?[A-Z][A-Z0-9_]*$`) aller Module ausser
Datenhaltung/Transport/Konfiguration, deren Wert Text ist oder nur aus Daten
mit Text besteht (Obermenge). Damit ist jede spaeter registrierte Konstante
schon im Massstab.

**W5 — D5 „Parser als Vereinigung" darf keine deutsche Konstante aendern.**
Wer `kuerzung._MUSTER_NUMMER` (kuerzung.py:46) auf `(szene|scene)`
umschreibt, veraendert den Text-Schnappschuss (W4) und damit die
Bitgleichheits-Pruefung. **Geplant:** je Parser eine **neue** Konstante
`…_EN`; die Funktion probiert beide (Ausgabeparser) bzw. waehlt je Sprache
(Gruppentext). Deutsches Verhalten bleibt dadurch zeichengleich, ein
Test haelt es fest.

**W6 — `formen_liste_oder` ist deutsch verdrahtet** (workshop.py:828–831,
`" oder ".join(...)`). Nicht im Brief. **Geplant:** Aufgabe 4, Verbinder je
Sprache in `workshop.py` (die Dienste-Schicht darf `sprache.py` nicht
importieren, weil `sprache.py` `workshop` importiert).

**W7 — Die Spaetstand-Fixture traegt einen echten Vornamen.**
`tests/fixture_spaetstand.py:109–114` schreibt 400 Nachrichten mit
`absender = "Birk"`. D6(c) nennt sie als Pruefgrundlage. **Geplant:** die
E8-Tests laufen gegen eine **eigene, erfundene** Fixture
(`tests/fixture_sprache.py`, Aufgabe 25); die Spaetstand-Fixture bleibt
unangetastet.

**W8 — `tests/test_profile_geruest.py` haelt das alte Padua fest**
(`:64–68` Pflichtfelder leer, `:77–82` `code == "it"`/`anrede == "voi"`,
`:85–95` keine Inhalte). D1/D9 aendern genau das. **Geplant:** Aufgabe 2
dreht `:77–82` auf `en`/`you`/`auto`; Aufgabe 29 formuliert `:64–68` und
`:85–95` um (Zusicherung neu: „Geruest bleibt gesetzt, **alle** Inhaltsfelder
tragen den Marker `ANNAHME (Platzhalter A1`", „kein `prompts/`-Verzeichnis
im Profil" bleibt wahr, weil die englischen Rahmen-Vorlagen in der
Sprachschicht liegen, siehe W1).

**W9 — `scripts/rauchtest.py` schreibt in die Betriebsdatenbank.**
`main()` oeffnet `db.verbinde(einst.db_pfad)` = `IT_DB` (rauchtest.py,
`main`). Mit `betrieb/gruppe1.env` geladen, landete die `aufruf`-Zeile in
`betrieb/soap.db`. **Geplant:** Aufgabe 9 setzt `IT_DB` im selben Kommando
auf eine Wegwerf-Datei. Ausserdem liegt **kein** TTS-Werkzeug auf dem
Server (`which espeak-ng espeak ffmpeg pico2wave flite` → nichts) — die
Testaufnahmen muss Birk mitbringen (A-Annahme A3).

**W10 — Befehlszahl.** AGENTS.md sagt „dreizehn"; `befehle._BEKANNTE_BEFEHLE`
(befehle.py:757–767) hat **vierzehn** (inkl. `/festlegung`). Mit `/sprache`
werden es fuenfzehn. Aufgabe 32 zieht die Doku nach.

**W11 — Reihenfolge Pruefer.** Der Brief stellt den Stoppwort-Pruefer ans
Ende, verlangt aber seine Pruefung als Nachweis **jeder**
Uebersetzungsaufgabe. **Geplant:** Der Kern (`deutsche_treffer`,
`--dateien`, `--schluessel`) entsteht in Aufgabe 3; die Render-Quellen
(c)/(c2)/(d) kommen in Aufgabe 30 dazu.

**W12 — `pruefe_prompts --sprache en` braucht ein englisches Profil.**
Es gibt nur Padua, und das ist ein Geruest. `workshop.aktiv()` laedt ein
Geruest trotzdem (workshop.py:531–540, nur `bot.main` weist es ab). **Geplant:**
`--sprache en` setzt `IT_WORKSHOP=padua-2026`, sofern nicht `--workshop`
angegeben ist, und bricht ab, wenn `sprache.code()` danach nicht `"en"` ist.

Keine Entscheidung D1–D13 ist damit **inhaltlich** umgeworfen; W1, W4 und W5
praezisieren die Pruefregel, W2/W3 erweitern den Pruefer, W6–W12 sind
Luecken, die der Brief nicht nennt.

---

## Annahmen (nicht am Code pruefbar — mit Nachpruefung)

- **A1 (D2, Whisper-Autoerkennung):** ANNAHME: Infomaniak-Whisper erkennt die
  Sprache selbst, wenn das Multipart-Feld `language` **fehlt**, und das
  Ergebnis (`data`, ein JSON-String) traegt dann ein Feld `language`. Im Repo
  gibt es keine Audiodatei, um das zu messen. Nachpruefung: Aufgabe 9
  (manueller, kostenpflichtiger Rauchtest). Faellt sie, ist der Fallback in
  Aufgabe 9 beschrieben (Profilwert `whisper = "en"`, Gruppenwert per Knopf).
- **A2 (Whisper-Feldname):** ANNAHME: ein unbekanntes Feld im Multipart wird
  nicht abgelehnt und `language` fehlt ohne Fehler — Aufgabe 9 misst beides.
- **A3 (Testaudio):** ANNAHME: Birk bringt zwei kurze Aufnahmen mit (je
  15–30 s, eine englisch, eine italienisch, eigene Stimme oder mit
  Einwilligung der sprechenden Person), als `.ogg` aus Telegram exportiert.
  Sie werden **nicht** ins Repo gelegt.
- **A4 (Telegram-Menue):** ANNAHME: Die Slash-Befehle behalten ihre deutschen
  Namen (`/hilfe`, `/stand`, …), nur die Beschreibungen in
  `befehle.BEFEHLE_LISTE` werden englisch. Englische Aliase (`/help`,
  `/status`) sind **nicht** Teil von A1 — Rueckfrage an Birk, falls Padua
  getippte Befehle braucht (Slash-Befehle werden ohnehin nicht beworben).
- **A5 (Pseudonym-Schalter):** ANNAHME: E8 ist eine Datenschutzentscheidung,
  keine Sprachentscheidung. Deshalb ein eigenes Profilfeld
  `[datenschutz] pseudonyme` (Vorgabe `false` = Dortmund unveraendert, Padua
  `true`) statt der Kopplung an `sprache.code != "de"`. Begruendung: ein
  kuenftiger deutschsprachiger Workshop kann E8 wollen, und ein englisches
  Testprofil ohne Pseudonyme bleibt moeglich. Rueckfrage an Birk nur, falls er
  die Kopplung an die Sprache vorzieht — der Code aendert sich dann an einer
  Stelle (`sprache.pseudonyme()`).
- **A6 (Englisch-Variante):** ANNAHME: britische Schreibweise
  (`summarise`, `colour`, `analyse`) — Europa, Schulkontext. Karte P kann das
  am Prompt-Dump umwerfen; der Pruefer ist davon unabhaengig.
- **A7 (Tschechow-/Motiv-Heuristik):** ANNAHME: Die
  Grossschreibungs-Heuristiken in `dramaturgie/mechanik.py:552/557/856`
  (Substantive erkennt man am Grossbuchstaben) tragen im Englischen nicht.
  Geplant ist, sie bei `code != "de"` **abzuschalten** (leere
  Kandidatenliste) statt eine englische Heuristik zu erfinden — „ein
  fehlender Befund kostet nur eine Gelegenheit" (AGENTS.md,
  Dramaturgie-Pruefung). Rueckfrage nur, falls Birk die Tschechow-Pruefung in
  Padua braucht.
- **A8 (Uebersetzungsqualitaet):** Die englischen Prompts und Texte sind
  **Uebersetzungen durch den Umsetzer**; Birk nimmt sie in **Karte P** am
  vollstaendigen Prompt-Dump ab. A1 garantiert Struktur, Platzhalter,
  Protokoll-Token und Stoppwortfreiheit, nicht Idiomatik.
- **A9 (Korpus Journal/Verdichter/Sprachprofil):** Nur der Erkenner bekommt
  einen englischen Korpus (D8). Journal-, Verdichter- und
  Sprachprofil-Prompts laufen in Padua **ungemessen** — offene Folgearbeit,
  im Korpusbericht (Aufgabe 31) und in AGENTS.md (Aufgabe 32) benannt.

---

## Konventionen (fuer alle Aufgaben bindend)

### K1 — Der Textzugriff `T`

```python
# am Modulende jedes Moduls mit Nutzertexten (nach allen Konstanten):
from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
```

- Verwendung **nur** als Attributzugriff zur Aufrufzeit: `T._TEXT_X`,
  `T.ANWEISUNG_Y.format(...)`. **Nie** `T._TEXT_X` in einem Default-Argument,
  einer Modul-Konstante oder einem Klassenattribut (dort wuerde es beim
  Import ausgewertet).
- Fremde Texte ueber den Modulnamen: `szene_modul.T._TEXT_ANGEBOT_USA`,
  `knoepfe.T._TEXT_X` (`knoepfe/__init__.py` re-exportiert `T` aus
  `knoepfe.texte`).
- In `knoepfe/*.py` wird `T` aus `knoepfe.texte` importiert
  (`from interview_theater.knoepfe.texte import T`); **alle** Texte des
  Pakets liegen in `texte.py` (dort gehoeren sie laut Paket-Docstring hin).
  Das betrifft auch `stationen._ERLEDIGT_FUER` (wandert in Aufgabe 10 nach
  `texte.py`) und alle Inline-Literale der Submodule.
- `knoepfe/__init__.py` re-exportiert die deutschen Konstanten **weiter**
  (bestehende Aufrufer und Tests lesen `knoepfe.TEXT_X`); die Importlisten der
  **Submodule** verlieren die Namen, die sie nur noch ueber `T` lesen.

### K2 — Die Tabelle `interview_theater/sprachen/en/texte.toml`

- Eine Tabelle je **definierendem** Modul, Modulname ohne
  `interview_theater.`-Praefix, **in Anfuehrungszeichen**; darin der
  Konstantenname als Schluessel:

```toml
["knoepfe.texte"]
_TEXT_SPEICHERN_KNOPF = "Yes, save"
_TEXT_PHASE_WEITER = "On to {phase}?"

["szene"]
_TEXT_USA_JA = "Good, scenes will come from the US model from now on. I'll mention it again before every scene."
```

- Mehrzeilige Texte als TOML-`"""…"""` mit denselben `\n`-Stellen wie das
  deutsche Original (Absatzstruktur gleich).
- **Behaelter:** ein `dict` wird eine Untertabelle
  (`["knoepfe.stationen"._ERLEDIGT_FUER]` bzw. nach dem Umzug
  `["knoepfe.texte"._ERLEDIGT_FUER]` mit Schluesseln `"2" = "Your terms"`
  — `sprache.angleichen` macht aus `"2"` wieder `2`, weil die deutschen
  Schluessel Zahlen sind); `tuple`/`list` ein Array; `list[dict]` ein Array
  von Inline-Tabellen. Schluessel `slug` und `command` sind **Protokoll** und
  muessen woertlich gleich bleiben (Paritaetstest).
- Sortierung: Tabellen in der Reihenfolge der Aufgaben, darin die Schluessel
  in Reihenfolge der Definition im Modul (erleichtert das Gegenlesen).

### K3 — Platzhalter

Gleich sein muessen je Text (und je Blatt eines Behaelters) die **Mengen**
aus `sprache.platzhalter(text)`: Format-Felder `{name}` (auch
`{name!r}`/`{name:>3}`), Profil-Platzhalter `{{name}}`, Prozent-Felder
`%s`/`%d`. Reihenfolge darf sich aendern (Englisch stellt Saetze um), die
Menge nicht.

### K4 — Beschriftungstabellen fuer Strukturen mit Funktionen

`phasentexte.PARAMETER` (phasentexte.py, `{1: (("Begriffe", <lambda>,
"noch keine"),), …}`) und aehnliche Strukturen enthalten Funktionen und
passen nicht in TOML. Fuer sie gibt es **eine** Beschriftungstabelle im
selben Modul, deutsch als Identitaet:

```python
#: Die sichtbaren Woerter aus PARAMETER -- deutsch auf sich selbst
#: abgebildet; die englische Fassung steht in sprachen/en/texte.toml.
PARAMETER_BESCHRIFTUNG = {
    "Begriffe": "Begriffe", "noch keine": "noch keine", ...
}
```

und am Verwendungsort `T.PARAMETER_BESCHRIFTUNG.get(wort, wort)`. Die
TOML-Tabelle hat dann **deutsche Schluessel** und englische Werte;
`pruefe_sprache --schluessel` prueft nur die **Werte**.

### K5 — Parser je Sprache

```python
# Gruppentext: je Sprache waehlen (deutsches Verhalten zeichengleich)
_AUFTRAG = re.compile("|".join(_AUFTRAGSFORMEN), re.IGNORECASE)
_AUFTRAG_EN = re.compile("|".join(_AUFTRAGSFORMEN_EN), re.IGNORECASE)

def ist_auftrag(text):
    ...
    muster = sprache.je_sprache({"de": _AUFTRAG, "en": _AUFTRAG_EN})
    return muster.search(roh) is not None

# Modellausgabe: beide probieren (ein englisches Modell labelt manchmal
# deutsch und umgekehrt) -- deutsch zuerst, damit Dortmund dasselbe Ergebnis
# bekommt wie vorher.
def nummer_aus_wert(wert):
    for muster in (_MUSTER_NUMMER, _MUSTER_NUMMER_EN):
        treffer = muster.match(wert or "")
        if treffer:
            return int(treffer.group(1))
    return None
```

Jede Parserstelle bekommt zwei Tests: englisches Beispiel wird erkannt;
deutsches Beispiel liefert **dasselbe** wie vor der Aenderung (der Test nennt
den Wert ausdruecklich).

### K6 — Stil der englischen Texte

- Anrede **you** (Gruppe, informell, direkt), kurze Saetze, keine Floskeln.
- Emojis, Zeilenumbrueche, Aufzaehlungszeichen, Leerzeichen um Platzhalter
  bleiben wie im Deutschen.
- **Keine Slash-Befehle bewerben** (wie im Deutschen: wo das Deutsche einen
  Befehl nennt, darf das Englische ihn nennen — `_TEXT_HILFE` —, sonst nicht).
- Keine Eigennamen, keine Beispielorte ausser den Profil-Platzhaltern.
- Protokoll-Token (B2, letzte Zeile) **woertlich** und in Grossbuchstaben
  wie im Deutschen: `VORSCHLAG FRAGENAUSWAHL:`, `BEFUND:`,
  `ZUSAMMENFASSUNG:`, Erkenner-`art`-Namen, JSON-Schluessel,
  `dialog|monolog|chor|lied|rap` als Werte.

### K7 — Glossar Deutsch → Englisch (verbindlich)

| Deutsch | Englisch | Deutsch | Englisch |
|---|---|---|---|
| Begriffe (Phase 1) | Terms | Fragen (Phase 2) | Questions |
| Interviews (Phase 3) | Interviews | Setting, Figuren & Geschichte (4) | Setting, Characters & Story |
| Schaerfung (5) | Sharpening | Szenen als Geschichte (6) | Scenes as Story |
| Feinschliff (7) | Polish | Phase | phase |
| Figur | character | Szene | scene |
| Geschichte | story | Kurzgeschichte | short story |
| Szenenfolge | scene sequence | Textbuch | script |
| Probenansicht | rehearsal view | Gruppenseite | group page |
| Leitfaden | interview guide | Eroeffnung / Abschluss | opening / closing |
| Einleitung (vor heikler Frage) | lead-in | Verdichtung | summary |
| Kernthema | core theme | Belegzitat | supporting quote |
| Arbeitsstand | progress (`/stand` → "Where we are") | Festlegung | agreement |
| Aufnahme | recording | Sprachnachricht | voice message |
| Transkript | transcript | auswerten | analyse |
| Notiert: | Noted: | Speichern | Save |
| Weiter zu … | On to … | Noch etwas aendern | Change something first |
| Passt | Looks good | Neu schreiben | Rewrite |
| Kuerzer (25 %) | Shorter (25 %) | Fassung | version |
| Regie-Notiz | director's note | Sprechanteile | speaking shares |
| Form: Dialog/Monolog/Chor/Lied/Rap | Dialogue/Monologue/Chorus/Song/Rap | Stil | style |
| US-Modell / Schweiz | US model / Switzerland | Einwilligung | consent |
| Knopf | button | ihr/euch/euer | you/your |

### K8 — Nachweisformen

- **Rotsehen:** jede Aufgabe nennt den Test, der **vor** der Umsetzung rot
  ist, und die erwartete Fehlerzeile.
- **Mutationsnachweis:** jede Aufgabe nennt eine Zeile, die man nach dem
  Gruenwerden rueckgaengig macht (oder verfaelscht), und den Test, der dann
  rot wird. Danach die Zeile wiederherstellen und `SUITE` erneut.
- **Uebersetzungsnachweis:** `$PY -m scripts.pruefe_sprache --dateien <…>`
  bzw. `--schluessel <modul>[,<modul>…]` mit Ausgabe `0 Treffer` und Exit 0.

---

## Dateien im Ueberblick

| Datei | Aufgabe | Verantwortung |
|---|---|---|
| `scripts/text_schnappschuss.py` | **neu**, 1 | SHA-256 + Laenge je Text-Konstante (Obermenge, W4) |
| `docs/prompt-audit/schnappschuss-vor-sprache-a1.txt` | **neu**, 1 | Prompt-Fingerabdruck vor A1 (identisch mit/ohne `dortmund-2026`) |
| `docs/prompt-audit/texte-vor-sprache-a1.txt` | **neu**, 1 | Text-Fingerabdruck vor A1 |
| `tests/test_sprache_bitgleich.py` | **neu**, 1 | Beide Massstaebe, ohne Variable und mit Dortmund |
| `interview_theater/workshop.py` | 2, 4 | `sprache.whisper`, `datenschutz.pseudonyme`, `SPRACHEN`, Verbinder je Sprache |
| `workshop/dortmund-2026/profil.toml` | 2 | dieselben neuen Felder mit Vorgabewert |
| `scripts/pruefe_profil.py` | 2 | prueft `code`, `whisper`, englische Zahlwoerter |
| `interview_theater/sprache.py` | **neu**, 3 | `code()`, `whisper_vorgabe()`, `pseudonyme()`, `je_sprache`, `Texte`, `text`, `platzhalter`, `angleichen`, `SPRACHNAMEN` |
| `interview_theater/sprachen/en/texte.toml` | **neu**, 3; waechst 4–17, 22–25 | die englische Texttabelle |
| `interview_theater/sprachen/en/prompts/**.md` | **neu**, 18–21 | 38 englische Prompt-Dateien |
| `scripts/pruefe_sprache.py` | **neu**, 3; 30 | Stoppwort-Pruefer (Kern 3, Render-Quellen 30) |
| `interview_theater/anweisungen.py` | 4 | Sprachschicht in `_roh`/`_bausteine`, `T.UEBERSCHRIFT` |
| `scripts/prompt_schnappschuss.py` | 4, 10, 14 | Konstanten ueber `T` lesen (Dortmund gleich) |
| `tests/test_sprache.py`, `tests/test_pruefe_sprache.py`, `tests/test_sprache_prompts.py`, `tests/test_sprache_texte.py` | **neu**, 3–5 | Mechanik, Pruefer, Prompt-Paritaet, Text-Waechter (AST) |
| `interview_theater/stt.py` | 6 | `sprache=`-Parameter, `auto` ohne `language`, erkannte Sprache ins Log |
| `interview_theater/db.py`, `repo.py`, `aufnahme.py` | 7 | `gruppe.stt_sprache`, Getter/Setter, wirksame Sprache |
| `interview_theater/befehle.py`, `knoepfe/texte.py`, `knoepfe/interviews.py`, `knoepfe/stationen.py`, `knoepfe/wirkung.py`, `knoepfe/__init__.py` | 8 | `/sprache`, Knopfangebot Phase 3 |
| alle Module mit Nutzertexten | 10–17 | Verwendungen auf `T`, Inline-Literale zu Konstanten |
| `interview_theater/web.py` | 17 | Gruppenseite, Probenansicht, Leitfaden ueber `T`, `lang` |
| Parser-Module (ablauf, befehle, szene, kuerzung, szenenfolge, kurzgeschichte, stueckpruefung, web, erkenner, repo, vorspann, knoepfe/fragen, knoepfe/figuren, dramaturgie/mechanik, kontext, begriffe) | 22–24 | `_EN`-Konstanten, Auswahl/Vereinigung |
| `tests/test_sprache_parser.py` | **neu**, 22–24 | je Parser en + de-unveraendert |
| `interview_theater/kontext.py`, `erkenner.py`, `journal.py`, `aufnahme.py`, `phasentexte.py`, `befehle.py`, `repo.py` | 25 | Pseudonyme (E8) |
| `tests/fixture_sprache.py` | **neu**, 17 (Code steht in 25) | erfundene englische Gruppe fuer Web-, E8- und Pruefertests |
| `tests/test_pseudonyme.py` | **neu**, 25 | E8-Nachweis |
| `tests/test_knoepfe_sprache.py`, `tests/test_chat_sprache.py`, `tests/test_szene_sprache.py`, `tests/test_web_sprache.py`, `tests/test_stt_sprache.py` | **neu**, 7–17 | Englisch je Bereich, Dortmund unveraendert |
| `tests/test_zitat.py` | 26 | D7-Faelle |
| `korpus/en/erkenner.jsonl`, `tests/test_korpus.py` | **neu**/27 | englischer Erkenner-Korpus |
| `scripts/pruefe_prompts.py`, `tests/test_pruefe_prompts.py` | 28 | `--sprache en`, `--workshop` |
| `workshop/padua-2026/{profil,phasen,phasentexte,formen}.toml`, `LIESMICH.md`, `tests/test_profile_geruest.py` | 2, 29 | Padua englisch, minimal |
| `docs/sprache-a1-korpuslauf-<datum>.md` | **neu**, 31 | Trefferquoten de/en |
| `AGENTS.md`, `docs/workshop-profil-umbau-2026-09-06.md`, `workshop/padua-2026/LIESMICH.md` | 32 | Doku |

**Aufgaben: 33** (30 Umsetzungsaufgaben, zwei manuelle kostenpflichtige
Laeufe — 9 und 31 —, eine Abschlussaufgabe).

---

## Reihenfolge, und was fuer Montag unverzichtbar ist

Die Reihenfolge folgt dem Brief (Mechanik/Bitgleichheit → STT → Texte und
Prompts → Parser → E8 → Korpus → Padua-Profil → Pruefer → Korpuslauf →
Doku). Innerhalb von „Texte und Prompts" kommt zuerst, was die Gruppe am
ersten Tag sieht (Knoepfe, Begruessung, Phasen 1–3, Gespraechsprompt),
zuletzt, was erst in Phase 7 oder nur im Betreiberwerkzeug laeuft
(Dramaturgie, `richter.md`).

**Schnittlinie, falls die Zeit bis Fr 02.10. abends nicht reicht:** Die
Aufgaben 1–8, 10–16, 18–20, 22, 25, 27–30 sind fuer einen englischen
Workshoptag unverzichtbar. Aufgabe 17 (Gruppenseite), 21 (Pruef-Prompts),
23/24 (Modellausgabe-Parser, Rundreise) und 26 (Zitat-Tests, rein
nachweisend) sind fuer Tag 1–2 von Padua verzichtbar (Phasen 1–4), fuer
Phase 5–7 nicht. **Die Abnahme (3) der Karte verlangt alle** — eine
Schnittlinie ist eine Entscheidung Birks, keine des Umsetzers.

---

## Aufgabe 1: Der Massstab vor dem Umbau (D11)

**Vor jeder anderen Aenderung.** Danach darf kein Commit dieses Plans einen
Abschnitt der beiden Massstaebe veraendern, ausser ueber `VERSCHOBEN` /
`GEAENDERT` mit Grund.

**Files:**
- Create: `scripts/text_schnappschuss.py`
- Create: `docs/prompt-audit/schnappschuss-vor-sprache-a1.txt`
- Create: `docs/prompt-audit/texte-vor-sprache-a1.txt`
- Create: `tests/test_sprache_bitgleich.py`

**Interfaces:**
- Produces: `text_schnappschuss.teile() -> list[tuple[str, str]]`
  (Abschnittsname `"<modul ohne interview_theater.>.<NAME>"`, Text),
  `text_schnappschuss.form(wert) -> str | None`,
  `text_schnappschuss.wert(modul, name)` (Haken fuer Aufgabe 3),
  `text_schnappschuss.AUSGENOMMEN`. Fingerabdruck-Format wie
  `prompt_schnappschuss.fingerabdruck` (`sha256  laenge  name`).
- Produces: `tests/test_sprache_bitgleich.VERSCHOBEN: dict[str, str]`,
  `GEAENDERT: dict[str, str]` — spaetere Aufgaben tragen dort ein.

- [x] **Schritt 1: Den Test schreiben** — `tests/test_sprache_bitgleich.py`:

```python
"""Dortmund bleibt bitgleich -- auch durch die Sprachumstellung (Karte A1).

Zwei Massstaebe, beide VOR dem ersten Umbauschritt abgelegt (30.09.2026):

* ``docs/prompt-audit/schnappschuss-vor-sprache-a1.txt`` -- jede Prompt-Datei
  und jede zusammengesetzte Systemanweisung (``scripts/prompt_schnappschuss``),
* ``docs/prompt-audit/texte-vor-sprache-a1.txt`` -- jede Modul-Konstante,
  aus der ein Nutzer- oder Modelltext entstehen kann
  (``scripts/text_schnappschuss``, eine Obermenge der spaeteren Texttabelle).

Geprueft wird ohne ``IT_WORKSHOP`` und mit ``dortmund-2026``. Neue Abschnitte
sind erlaubt (eine neue Konstante ist keine Undichtigkeit), ein
verschwundener oder veraenderter ist ein Befund -- ausser er steht in
``VERSCHOBEN`` oder ``GEAENDERT``, mit Grund.
"""

import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, workshop
from scripts import prompt_schnappschuss, text_schnappschuss

WURZEL = Path(__file__).resolve().parent.parent
PROMPTS = WURZEL / "docs" / "prompt-audit" / "schnappschuss-vor-sprache-a1.txt"
TEXTE = WURZEL / "docs" / "prompt-audit" / "texte-vor-sprache-a1.txt"
DORTMUND = "dortmund-2026"

#: Abschnitte, die A1 absichtlich an einen anderen Ort legt: alt -> neu.
#: Der Wert muss am neuen Ort zeichengleich sein.
VERSCHOBEN: dict[str, str] = {}

#: Abschnitte, deren Wert A1 absichtlich aendert -- mit Grund. Jede Zeile
#: hier ist eine Verhaltensaenderung fuer Dortmund.
GEAENDERT: dict[str, str] = {}

_ZEILE = re.compile(r"^(\S+)\s+(\d+)\s+(.*)$")


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _lies(text: str) -> dict[str, str]:
    fertig = {}
    for zeile in text.splitlines():
        pruef, laenge, name = _ZEILE.match(zeile).groups()
        fertig[name] = f"{pruef} {laenge}"
    return fertig


def _vergleiche(erwartet: dict[str, str], jetzt: dict[str, str]) -> None:
    fehlend, abweichend = [], []
    for name, wert in erwartet.items():
        if name in GEAENDERT:
            continue
        ziel = VERSCHOBEN.get(name, name)
        if ziel not in jetzt:
            fehlend.append(name)
        elif jetzt[ziel] != wert:
            abweichend.append(
                f"\n  {name}\n    erwartet: {wert}\n    bekommen: {jetzt[ziel]}")
    assert not fehlend, "verschwunden: " + ", ".join(sorted(fehlend))
    assert not abweichend, "".join(abweichend)


def _prompts_jetzt() -> dict[str, str]:
    anweisungen._CACHE.clear()
    return _lies(prompt_schnappschuss.fingerabdruck())


def _texte_jetzt() -> dict[str, str]:
    return _lies(prompt_schnappschuss.fingerabdruck(text_schnappschuss.teile()))


def test_prompts_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_prompts_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_texte_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_texte_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_massstaebe_sind_nicht_leer():
    assert len(_lies(PROMPTS.read_text(encoding="utf-8"))) >= 121
    assert len(_lies(TEXTE.read_text(encoding="utf-8"))) >= 600


def test_jede_ausnahme_hat_einen_grund():
    for name, grund in GEAENDERT.items():
        assert grund.strip(), name
    for alt, neu in VERSCHOBEN.items():
        assert alt != neu, alt
```

- [x] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_bitgleich.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.text_schnappschuss'`
(Sammelfehler), danach `FileNotFoundError` fuer die beiden Massstabsdateien.

- [x] **Schritt 3: `scripts/text_schnappschuss.py` schreiben**

```python
"""Ein Schnappschuss aller Modul-Konstanten, aus denen ein Nutzer- oder
Modelltext entstehen kann -- der Massstab dafuer, dass Dortmund durch die
Sprachumstellung (Karte A1, 30.09.2026) bitgleich bleibt.

``scripts/prompt_schnappschuss.py`` deckt Prompt-Dateien und zusammengesetzte
Systemanweisungen ab. Die Chat- und Knopftexte, die Auftragsvorlagen und die
Koepfe der Nutzertexte stehen aber als Python-Konstanten im Code -- und genau
die werden in A1 auf einen Nachschlagezugriff umgestellt. Dieser
Schnappschuss nimmt **jede** Modul-Konstante (Name in Grossbuchstaben), deren
Wert Text ist oder nur aus Daten mit Text besteht, in allen Modulen ausser
Datenhaltung, Transport und Konfiguration. Das ist absichtlich eine
Obermenge: die Texttabelle entsteht erst waehrend des Umbaus, der Massstab
muss vorher feststehen.

Abgelegt wird je Abschnitt ``sha256  laenge  name``, dasselbe Format wie im
Prompt-Schnappschuss (``prompt_schnappschuss.fingerabdruck``).

Aufruf::

    python -m scripts.text_schnappschuss            # nach stdout
    python -m scripts.text_schnappschuss <datei>    # in eine Datei
"""

import ast
import importlib
import pkgutil
import re
import sys
from pathlib import Path

import interview_theater
from scripts import prompt_schnappschuss

#: Module ohne Nutzertexte. ``workshop`` hat seinen eigenen Feld-fuer-Feld-Test
#: (tests/test_workshop.py), ``sprache`` entsteht erst in Aufgabe 3.
AUSGENOMMEN = frozenset({
    "interview_theater.db", "interview_theater.repo",
    "interview_theater.web_daten", "interview_theater.telegram",
    "interview_theater.llm", "interview_theater.einstellungen",
    "interview_theater.szene_claude", "interview_theater.workshop",
    "interview_theater.sprache",
})

PAKET = "interview_theater."
_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")


def _nur_daten(wert) -> bool:
    if isinstance(wert, (str, int, float, bool)) or wert is None:
        return True
    if isinstance(wert, dict):
        return all(_nur_daten(k) and _nur_daten(v) for k, v in wert.items())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return all(_nur_daten(v) for v in wert)
    return False


def _hat_text(wert) -> bool:
    if isinstance(wert, str):
        return True
    if isinstance(wert, dict):
        return any(_hat_text(v) for v in wert.values())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return any(_hat_text(v) for v in wert)
    return False


def form(wert) -> str | None:
    """Die vergleichbare Form eines Konstantenwerts, oder None, wenn er kein
    Text ist. Mengen werden sortiert (ihre Reihenfolge ist zufaellig),
    Regex als Muster plus Flags, alles andere als ``repr``."""
    if isinstance(wert, str):
        return wert
    if isinstance(wert, re.Pattern):
        return f"re.compile({wert.pattern!r}, {int(wert.flags)})"
    if isinstance(wert, (set, frozenset)) and _nur_daten(wert) and _hat_text(wert):
        return repr(sorted(wert, key=repr))
    if isinstance(wert, (dict, list, tuple)) and _nur_daten(wert) and _hat_text(wert):
        return repr(wert)
    return None


def _zugewiesene_namen(modul) -> list[str]:
    """Die Namen, die das Modul auf oberster Ebene selbst zuweist --
    importierte Namen gehoeren dem Modul, aus dem sie kommen."""
    baum = ast.parse(Path(modul.__file__).read_text(encoding="utf-8"))
    namen: list[str] = []
    for knoten in baum.body:
        if isinstance(knoten, ast.Assign):
            namen += [z.id for z in knoten.targets if isinstance(z, ast.Name)]
        elif (isinstance(knoten, ast.AnnAssign)
              and isinstance(knoten.target, ast.Name) and knoten.value is not None):
            namen.append(knoten.target.id)
    return [n for n in dict.fromkeys(namen) if _NAME.match(n)]


def wert(modul, name: str):
    """Der Wert, wie ihn der Code zur Laufzeit sieht. Aufgabe 3 leitet ihn
    ueber ``sprache.text``, sobald das Modul einen Zugriff ``T`` hat."""
    return getattr(modul, name)


def teile() -> list[tuple[str, str]]:
    stuecke: list[tuple[str, str]] = []
    module = sorted(
        pkgutil.walk_packages(interview_theater.__path__, PAKET),
        key=lambda info: info.name,
    )
    for info in module:
        if info.name in AUSGENOMMEN:
            continue
        modul = importlib.import_module(info.name)
        kurz = info.name[len(PAKET):]
        for name in _zugewiesene_namen(modul):
            text = form(wert(modul, name))
            if text is not None:
                stuecke.append((f"{kurz}.{name}", text))
    return stuecke


def main() -> None:
    text = prompt_schnappschuss.fingerabdruck(teile())
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10))} Abschnitte nach {sys.argv[1]}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
```

- [x] **Schritt 4: Die beiden Massstaebe ablegen und gegenpruefen**

```bash
$PY -m scripts.prompt_schnappschuss docs/prompt-audit/schnappschuss-vor-sprache-a1.txt
IT_WORKSHOP=dortmund-2026 $PY -m scripts.prompt_schnappschuss /tmp/a1-prompts-dortmund.txt
cmp docs/prompt-audit/schnappschuss-vor-sprache-a1.txt /tmp/a1-prompts-dortmund.txt && echo IDENTISCH
wc -l docs/prompt-audit/schnappschuss-vor-sprache-a1.txt
$PY -m scripts.text_schnappschuss docs/prompt-audit/texte-vor-sprache-a1.txt
IT_WORKSHOP=dortmund-2026 $PY -m scripts.text_schnappschuss /tmp/a1-texte-dortmund.txt
cmp docs/prompt-audit/texte-vor-sprache-a1.txt /tmp/a1-texte-dortmund.txt && echo IDENTISCH
```

Expected: zweimal `IDENTISCH`, `121 docs/prompt-audit/schnappschuss-vor-sprache-a1.txt`,
`655 Abschnitte nach docs/prompt-audit/texte-vor-sprache-a1.txt` (gemessen
mit derselben Logik auf `d8deb6c`; weicht die Zahl ab, weil zwischen Plan und
Umsetzung ein Commit Konstanten hinzugefuegt hat, gilt die gemessene Zahl —
im Commit-Text nennen).

- [x] **Schritt 5: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py`
Expected: `6 passed` plus die bestehenden von `test_profil_bitgleich.py`, 0 failed.

- [x] **Schritt 6: Mutationsnachweis**

In `interview_theater/knoepfe/texte.py:324` `_TEXT_SCHON_BENUTZT` um einen
Punkt kuerzen → `test_texte_ohne_variable_wie_vor_a1` rot mit
`knoepfe.texte._TEXT_SCHON_BENUTZT` in der Meldung. Zuruecksetzen
(`git checkout interview_theater/knoepfe/texte.py`).

- [x] **Schritt 7: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider      # erwartet: 2774 passed, 1 skipped
git add scripts/text_schnappschuss.py docs/prompt-audit/schnappschuss-vor-sprache-a1.txt \
        docs/prompt-audit/texte-vor-sprache-a1.txt tests/test_sprache_bitgleich.py
git commit -m "Massstab vor der Sprachumstellung: Prompt- und Text-Schnappschuss (A1)"
```

---

## Aufgabe 2: Profilfelder `sprache.whisper` und `datenschutz.pseudonyme` (D1, A5)

**Files:**
- Modify: `interview_theater/workshop.py:108–167` (`VORGABE_WERTE`), neue
  Konstante `SPRACHEN`
- Modify: `workshop/dortmund-2026/profil.toml` (Abschnitt `[sprache]`, neuer
  Abschnitt `[datenschutz]`)
- Modify: `workshop/padua-2026/profil.toml` (`[sprache]`, `[datenschutz]`)
- Modify: `scripts/pruefe_profil.py:49–56` (`ZAHLWOERTER`), `pruefe()` (neuer
  Block „Sprache")
- Modify: `tests/test_profile_geruest.py:77–82`
- Test: `tests/test_workshop.py`, `tests/test_pruefe_profil.py`

**Interfaces:**
- Produces: `workshop.SPRACHEN = ("de", "en")`; Profilfelder
  `sprache.whisper` (Vorgabe `"de"`), `datenschutz.pseudonyme` (Vorgabe
  `False`). `pruefe_profil.pruefe()` meldet FEHLER bei `code` ausserhalb
  `SPRACHEN` und bei `whisper` weder `"auto"` noch `[a-z]{2}`.

- [x] **Schritt 1: Tests schreiben**

In `tests/test_workshop.py` anhaengen:

```python
def test_vorgabe_hoert_deutsch_und_ohne_pseudonyme():
    """D1/A5: ohne Profil bleibt Whisper auf Deutsch und niemand wird
    pseudonymisiert -- das heutige Verhalten."""
    profil = workshop.aktiv()
    assert profil.wert("sprache.whisper") == "de"
    assert profil.wert("datenschutz.pseudonyme") is False


def test_nur_gebaute_sprachen():
    assert workshop.SPRACHEN == ("de", "en")
```

In `tests/test_pruefe_profil.py` anhaengen (die Datei baut Profile in
`tmp_path` — Muster `test_rahmen.py:75–84`: Verzeichnis anlegen,
`IT_WORKSHOP_BASIS` setzen):

```python
import pytest

from interview_theater import workshop
from scripts import pruefe_profil


def _profil(tmp_path, monkeypatch, sprache_toml: str):
    verz = tmp_path / "sprachtest"
    verz.mkdir()
    (verz / "profil.toml").write_text(
        'beschreibung = "Test"\n'
        f"[sprache]\n{sprache_toml}\n"
        '[zielgruppe]\nbeschreibung = "junge Frauen zwischen 15 und 18 Jahren"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    workshop.vergiss()
    return "sprachtest"


@pytest.mark.parametrize("zeilen, fehler", [
    ('code = "it"\nanrede = "voi"', "sprache.code"),
    ('code = "en"\nanrede = "you"\nwhisper = "english"', "sprache.whisper"),
    ('code = "en"\nanrede = "you"\nwhisper = "EN"', "sprache.whisper"),
])
def test_sprache_und_whisper_werden_geprueft(tmp_path, monkeypatch, capsys, zeilen, fehler):
    name = _profil(tmp_path, monkeypatch, zeilen)
    assert pruefe_profil.pruefe_namen(name) == 1
    assert fehler in capsys.readouterr().out


@pytest.mark.parametrize("zeilen", [
    'code = "en"\nanrede = "you"\nwhisper = "auto"',
    'code = "en"\nanrede = "you"\nwhisper = "it"',
    'code = "de"\nanrede = "ihr"',
])
def test_gueltige_sprachangaben_laufen_durch(tmp_path, monkeypatch, capsys, zeilen):
    name = _profil(tmp_path, monkeypatch, zeilen)
    pruefe_profil.pruefe_namen(name)
    ausgabe = capsys.readouterr().out
    assert "sprache.code" not in ausgabe and "sprache.whisper" not in ausgabe


def test_englisches_zahlwort_wird_geprueft():
    assert pruefe_profil.ZAHLWOERTER["five"] == 5
    assert pruefe_profil.ZAHLWOERTER["fuenf"] == 5
```

`tests/test_profile_geruest.py:77–82` ersetzen:

```python
def test_padua_traegt_seine_eigene_sprache_und_orte():
    """Birks Entscheidung vom 29.09.2026: Padua laeuft auf Englisch, die
    Interviewsprache erkennt Whisper selbst (E5), und kein Prompt sieht einen
    Vornamen (E8)."""
    profil = workshop.lade("padua-2026")
    assert profil.wert("sprache.code") == "en"
    assert profil.wert("sprache.anrede") == "you"
    assert profil.wert("sprache.whisper") == "auto"
    assert profil.wert("datenschutz.pseudonyme") is True
    assert tuple(profil.wert("orte.beispiele")) == (
        "fermata", "piazza", "bar", "stazione")
```

- [x] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_workshop.py tests/test_pruefe_profil.py tests/test_profile_geruest.py`
Expected: FAIL — `AttributeError: module 'interview_theater.workshop' has no attribute 'SPRACHEN'`,
`assert None == 'de'`, `KeyError: 'five'`, `assert 'it' == 'en'`.

- [x] **Schritt 3: Umsetzen**

`interview_theater/workshop.py` — nach `PFLICHTFELDER`:

```python
#: Die Sprachen, fuer die es Chat- und Prompttexte gibt (Karte A1,
#: 30.09.2026). Deutsch steht im Code, jede weitere unter
#: ``interview_theater/sprachen/<code>/``. Ein Profil mit einer anderen
#: Sprache weist ``scripts/pruefe_profil.py`` ab: es liefe sonst halb
#: deutsch, ohne dass es jemand merkt.
SPRACHEN = ("de", "en")
```

In `VORGABE_WERTE["sprache"]` nach `"anrede": "ihr",`:

```python
        # Was Whisper erkennen soll: ein ISO-639-1-Code ("de", "it") oder
        # "auto" -- dann schickt stt.py gar keine Sprache mit und Whisper
        # erkennt sie selbst (Karte A1, Birk E5). Eine Gruppe kann den Wert
        # fuer sich umstellen (gruppe.stt_sprache, /sprache, Knopf in Phase 3).
        "whisper": "de",
```

und nach dem `"sprache"`-Block einen neuen:

```python
    "datenschutz": {
        # E8 (Birk, 29.09.2026): ersetzt die Vornamen im Gespraechsverlauf
        # durch "Mitglied 1", "Mitglied 2" ..., bevor sie in einen Prompt
        # gehen -- ein Modell kann keinen Namen verwenden, den es nie sieht.
        # Aus in Dortmund: dort war der Name im Verlauf gewollt.
        "pseudonyme": False,
    },
```

`workshop/dortmund-2026/profil.toml`, im Abschnitt `[sprache]` nach
`anrede = "ihr"`:

```toml
# Was Whisper erkennen soll: ISO-639-1 ("de") oder "auto".
whisper = "de"

[datenschutz]
# Vornamen im Verlauf durch "Mitglied 1, 2, ..." ersetzen (E8, Padua).
pseudonyme = false
```

(`[datenschutz]` steht **nach** dem `[sprache]`-Block und **vor**
`[zielgruppe]`, sonst gehoeren die Folgezeilen in die falsche Tabelle.)

`workshop/padua-2026/profil.toml`, `[sprache]` ersetzen:

```toml
[sprache]
# Prompt- und Chatsprache (Birk, 29.09.2026: Padua laeuft auf Englisch).
code = "en"
# Wie die Gruppe angesprochen wird.
anrede = "you"
# Die Interviewsprache ist offen -- Whisper erkennt sie selbst (E5). Eine
# Gruppe kann per Knopf in Phase 3 oder /sprache umstellen.
whisper = "auto"

[datenschutz]
# E8: der Bot spricht nie mit Vornamen an; im Prompt stehen "Member 1, 2, ...".
pseudonyme = true
```

`scripts/pruefe_profil.py:49–56` — `ZAHLWOERTER` um die englischen Woerter
ergaenzen:

```python
ZAHLWOERTER = {
    "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fuenf": 5, "sechs": 6,
    "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12,
    # Englisch seit Karte A1 (Padua): "exactly five: ..."
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
```

In `pruefe()` direkt nach dem Geruest-Block:

```python
    # --- Sprache (Karte A1) ----------------------------------------------
    code = (profil.wert("sprache.code") or "").strip()
    if code not in workshop.SPRACHEN:
        bericht.fehlt(
            f"sprache.code={code!r} ist nicht gebaut. Moeglich: "
            f"{', '.join(workshop.SPRACHEN)}."
        )
    whisper = (profil.wert("sprache.whisper") or "").strip()
    if not re.fullmatch(r"auto|[a-z]{2}", whisper):
        bericht.fehlt(
            f"sprache.whisper={whisper!r} ist weder 'auto' noch ein "
            f"zweistelliger Sprachcode in Kleinbuchstaben (ISO 639-1, z. B. 'it')."
        )
```

und oben `import re` ergaenzen. Den Docstring-Punkt 4 ("nur fuer
deutschsprachige Profile pruefbar") auf "fuer deutsche und englische
Zahlwoerter" aendern.

- [x] **Schritt 4: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_workshop.py tests/test_pruefe_profil.py tests/test_profile_geruest.py tests/test_sprache_bitgleich.py`
Expected: alle gruen. `test_dortmund_traegt_dieselben_werte_wie_die_vorgabe`
bleibt gruen, weil Vorgabe **und** `dortmund-2026/profil.toml` beide Felder
tragen.

```bash
$PY -m scripts.pruefe_profil dortmund-2026
```
Expected: `dortmund-2026: in Ordnung`.

- [x] **Schritt 5: Mutationsnachweis**

`whisper = "de"` aus `workshop/dortmund-2026/profil.toml` loeschen → **gruen**
(Vorgabe fuellt) — also stattdessen `whisper = "it"` setzen →
`test_dortmund_traegt_dieselben_werte_wie_die_vorgabe` rot. Zuruecksetzen.
`re.fullmatch(r"auto|[a-z]{2}", …)` auf `r".+"` aendern →
`test_sprache_und_whisper_werden_geprueft[…whisper = "english"…]` rot.
Zuruecksetzen.

- [x] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/workshop.py workshop/dortmund-2026/profil.toml \
        workshop/padua-2026/profil.toml scripts/pruefe_profil.py \
        tests/test_workshop.py tests/test_pruefe_profil.py tests/test_profile_geruest.py
git commit -m "Profil: sprache.whisper und datenschutz.pseudonyme, Padua auf Englisch (A1)"
```

---

## Aufgabe 3: `sprache.py`, die leere Tabelle und der Stoppwort-Kern (D3, D10-Kern)

**Files:**
- Create: `interview_theater/sprache.py`
- Create: `interview_theater/sprachen/en/texte.toml` (nur Kopfkommentar)
- Create: `scripts/pruefe_sprache.py` (Kern: `deutsche_treffer`, `--dateien`, `--schluessel`)
- Modify: `scripts/text_schnappschuss.py` (`wert()` ueber `sprache.text`)
- Test: `tests/test_sprache.py`, `tests/test_pruefe_sprache.py`

**Interfaces:**
- Produces (`interview_theater/sprache.py`):
  - `DEUTSCH = "de"`, `AUTO = "auto"`, `GEBAUT = workshop.SPRACHEN`,
    `VERZEICHNIS: Path` (= `interview_theater/sprachen`),
    `SPRACHNAMEN = {"de": "Deutsch", "en": "English", "it": "Italiano"}`
  - `code() -> str`, `whisper_vorgabe() -> str`, `pseudonyme() -> bool`
  - `je_sprache(werte: dict[str, Any]) -> Any` (faellt auf `"de"` zurueck)
  - `tabelle(code: str) -> dict[str, dict[str, Any]]`, `vergiss() -> None`
  - `modulschluessel(modul: str) -> str`
  - `text(modul: str, name: str) -> Any`
  - `angleichen(deutsch: Any, eintrag: Any) -> Any`
  - `platzhalter(text: str) -> frozenset[str]`
  - `class Texte(modul: str)` mit `__getattr__`
- Produces (`scripts/pruefe_sprache.py`): `STOPPWOERTER: frozenset[str]`,
  `UI_WOERTER: frozenset[str]`, `ERLAUBT: frozenset[str]`,
  `@dataclass(frozen=True) Treffer(quelle: str, wort: str, ausschnitt: str)`,
  `deutsche_treffer(quelle: str, text: str) -> list[Treffer]`,
  `pruefe_dateien(pfade: list[Path]) -> list[Treffer]`,
  `pruefe_schluessel(module: list[str]) -> list[Treffer]`, `main(argv=None) -> int`.

- [x] **Schritt 1: Tests schreiben** — `tests/test_sprache.py`:

```python
"""Der Sprachzugriff: Deutsch ist die Konstante selbst, Englisch die Tabelle."""

import sys
import types

import pytest

from interview_theater import sprache, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def testmodul(monkeypatch):
    """Ein erfundenes Modul mit deutschen Konstanten und eine erfundene
    englische Tabelle -- unabhaengig vom Stand der echten texte.toml."""
    modul = types.ModuleType("interview_theater._sprachtest")
    modul._TEXT_GRUSS = "Hallo {name}, schoen, dass ihr da seid."
    modul._ERLEDIGT = {2: "Eure Begriffe", 3: "Eure Fragen"}
    modul.ZEILEN = ("eins", "zwei")
    modul.LISTE = [{"command": "stand", "description": "Arbeitsstand anzeigen"}]
    monkeypatch.setitem(sys.modules, modul.__name__, modul)
    monkeypatch.setitem(sprache._TABELLEN, "en", {"_sprachtest": {
        "_TEXT_GRUSS": "Hello {name}, good to have you here.",
        "_ERLEDIGT": {"2": "Your terms", "3": "Your questions"},
        "ZEILEN": ["one", "two"],
        "LISTE": [{"command": "stand", "description": "Show where we are"}],
    }})
    return modul


def _englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")


def test_deutsch_ist_die_konstante_selbst(testmodul):
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS is testmodul._TEXT_GRUSS
    assert t._ERLEDIGT is testmodul._ERLEDIGT


def test_englisch_kommt_aus_der_tabelle(testmodul, monkeypatch):
    _englisch(monkeypatch)
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS == "Hello {name}, good to have you here."


def test_behaelter_bekommen_ihre_deutsche_form(testmodul, monkeypatch):
    _englisch(monkeypatch)
    t = sprache.Texte(testmodul.__name__)
    assert t._ERLEDIGT == {2: "Your terms", 3: "Your questions"}
    assert t.ZEILEN == ("one", "two")
    assert t.LISTE == [{"command": "stand", "description": "Show where we are"}]


def test_nachgeschlagen_wird_zur_aufrufzeit(testmodul, monkeypatch):
    """Ein Web-Prozess bedient mehrere Gruppen (A2), Tests schalten das
    Profil um -- ein beim Import gemerkter Text waere danach falsch."""
    t = sprache.Texte(testmodul.__name__)
    vorher = t._TEXT_GRUSS
    _englisch(monkeypatch)
    assert t._TEXT_GRUSS != vorher


def test_fehlender_eintrag_bleibt_deutsch_und_meldet_sich(testmodul, monkeypatch, caplog):
    _englisch(monkeypatch)
    testmodul._TEXT_NEU = "Neu hier"
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_NEU == "Neu hier"
    assert "_sprachtest._TEXT_NEU" in caplog.text


def test_unbekannte_konstante_ist_ein_programmierfehler(testmodul):
    with pytest.raises(AttributeError):
        sprache.Texte(testmodul.__name__)._TEXT_GIBT_ES_NICHT


def test_texte_sind_nur_lesbar(testmodul):
    with pytest.raises(AttributeError):
        sprache.Texte(testmodul.__name__)._TEXT_GRUSS = "x"


def test_code_whisper_pseudonyme_aus_dem_profil(monkeypatch):
    assert sprache.code() == "de"
    assert sprache.whisper_vorgabe() == "de"
    assert sprache.pseudonyme() is False
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert sprache.code() == "en"
    assert sprache.whisper_vorgabe() == "auto"
    assert sprache.pseudonyme() is True


def test_je_sprache_faellt_auf_deutsch_zurueck(monkeypatch):
    assert sprache.je_sprache({"de": 1, "en": 2}) == 1
    _englisch(monkeypatch)
    assert sprache.je_sprache({"de": 1, "en": 2}) == 2
    assert sprache.je_sprache({"de": 1}) == 1


@pytest.mark.parametrize("text, erwartet", [
    ("Hallo {name}", {"{name}"}),
    ("{nummer:>3} von {gesamt!r}", {"{nummer}", "{gesamt}"}),
    ("worum es geht ({{projekt_kurz}})", {"{{projekt_kurz}}"}),
    ("%s Zeichen, %d Token", {"%s", "%d"}),
    ('JSON {"a": 1} bleibt aussen vor', set()),
])
def test_platzhalter(text, erwartet):
    assert sprache.platzhalter(text) == frozenset(erwartet)


def test_die_echte_tabelle_ist_gueltiges_toml():
    sprache.vergiss()
    assert isinstance(sprache.tabelle("en"), dict)
```

`tests/test_pruefe_sprache.py`:

```python
"""Der Stoppwort-Pruefer (D10) -- Kern: Woerter, Ausnahmen, Dateien, Schluessel."""

from scripts import pruefe_sprache


def _woerter(text):
    return [t.wort for t in pruefe_sprache.deutsche_treffer("test", text)]


def test_deutsche_funktionswoerter_schlagen_an():
    assert "und" in _woerter("Figuren und Szenen")
    assert "euch" in _woerter("Ich zeige es euch.")


def test_ui_woerter_schlagen_an_auch_ohne_funktionswort():
    """W2: 'Ja, speichern' hat kein Funktionswort."""
    assert _woerter("Ja, speichern") == ["ja", "speichern"]
    assert "notiert" in _woerter("Notiert:\n- Begriffe")


def test_umlaut_ist_ein_eigenes_signal():
    assert "ä" in "".join(_woerter("Gespräch"))


def test_englisch_bleibt_still():
    assert _woerter("Yes, save. On to phase 3? Your terms are noted.") == []


def test_italienisch_bleibt_still():
    assert _woerter("Ciao, com'è andata l'intervista? Ci vediamo in piazza.") == []


def test_protokoll_token_sind_erlaubt():
    text = ('Append the block VORSCHLAG FRAGENAUSWAHL: and use '
            '{"art": "fragen_setzen"} with form "chor" or "lied". '
            'ZUSAMMENFASSUNG: one line. {{rahmen_kurz}} {name}')
    assert _woerter(text) == []


def test_treffer_nennt_quelle_und_ausschnitt():
    treffer = pruefe_sprache.deutsche_treffer("prompt system", "Please write und so.")
    assert treffer[0].quelle == "prompt system"
    assert "write und so" in treffer[0].ausschnitt


def test_dateien_modus(tmp_path):
    gut = tmp_path / "gut.md"
    gut.write_text("Write in English, in short sentences.", encoding="utf-8")
    schlecht = tmp_path / "schlecht.md"
    schlecht.write_text("Schreibe auf Deutsch, bitte.", encoding="utf-8")
    assert pruefe_sprache.pruefe_dateien([gut]) == []
    assert pruefe_sprache.pruefe_dateien([schlecht])
    assert pruefe_sprache.main(["--dateien", str(gut)]) == 0
    assert pruefe_sprache.main(["--dateien", str(schlecht)]) == 1
```

- [x] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache.py tests/test_pruefe_sprache.py`
Expected: FAIL — `ImportError: cannot import name 'sprache' from 'interview_theater'`
und `ModuleNotFoundError: No module named 'scripts.pruefe_sprache'`.

- [x] **Schritt 3: `interview_theater/sprache.py`**

```python
"""Die Sprache eines Workshops: Chat- und Promptsprache, Whisper-Vorgabe,
Pseudonyme, und der Nachschlagezugriff auf die Texttabelle (Karte A1,
30.09.2026).

**Kein i18n-Framework.** Die deutschen Nutzertexte stehen als
Python-Konstanten in ihren Modulen und **sind** die deutsche Tabelle -- sie
bleiben zeichengleich stehen, damit Dortmund bitgleich bleibt
(``tests/test_sprache_bitgleich.py``). Jede weitere Sprache steht in genau
einer Datei ``sprachen/<code>/texte.toml``: eine Tabelle je definierendem
Modul, darin der Konstantenname als Schluessel.

**Nachgeschlagen wird zur Aufrufzeit, nie beim Import.** Ein Modul mit
Nutzertexten traegt am Ende ``T = sprache.Texte(__name__)`` und liest
``T._TEXT_X`` dort, wo der Text gebraucht wird. Das ist dieselbe Regel wie
bei den PEP-562-Zugriffen in ``phasen``/``szene``/``szenenfolge`` (D.5 der
Profil-Analyse): ein Web-Prozess bedient mehrere Gruppen, und Tests
schalten das Profil per monkeypatch um.

**Deutsch ist die Konstante selbst** -- dasselbe Objekt, kein Umweg ueber
eine Datei. **Fehlt ein englischer Eintrag, bleibt es Deutsch** und die
Luecke wird einmal je Prozess geloggt: ein Zug, der mitten im Workshop an
einem vergessenen Knopftext abbricht, waere teurer als ein deutsches Wort.
``tests/test_sprache_texte.py`` sorgt dafuer, dass es die Luecke gar nicht
erst gibt.

Nur Standardbibliothek plus ``workshop`` -- Dienste-Schicht, von jedem
Modul aus importierbar.
"""

import logging
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from interview_theater import workshop

log = logging.getLogger(__name__)

DEUTSCH = "de"
#: Whisper-Wert fuer "Sprache selbst erkennen" (Birk E5).
AUTO = "auto"
GEBAUT = workshop.SPRACHEN
VERZEICHNIS = Path(__file__).resolve().parent / "sprachen"
TABELLENDATEI = "texte.toml"
PAKET = "interview_theater."

#: Sprachnamen in ihrer eigenen Sprache -- fuer Knopf und /sprache. Nicht
#: uebersetzt: wer Italienisch spricht, sucht "Italiano".
SPRACHNAMEN = {"de": "Deutsch", "en": "English", "it": "Italiano"}


def code() -> str:
    """Die Chat- und Promptsprache des aktiven Profils."""
    return str(workshop.aktiv().wert("sprache.code", DEUTSCH) or DEUTSCH)


def whisper_vorgabe() -> str:
    """Was Whisper erkennen soll, solange die Gruppe nichts anderes sagt:
    ein ISO-639-1-Code oder ``AUTO``."""
    return str(workshop.aktiv().wert("sprache.whisper", DEUTSCH) or DEUTSCH)


def pseudonyme() -> bool:
    """E8: Vornamen im Gespraechsverlauf durch "Member N" ersetzen?"""
    return bool(workshop.aktiv().wert("datenschutz.pseudonyme", False))


def je_sprache(werte: dict[str, Any]) -> Any:
    """Waehlt aus ``{"de": …, "en": …}`` den Wert der aktiven Sprache.
    Fehlt er, gilt der deutsche -- ein Parser ohne englische Fassung
    verhaelt sich dann wie vorher."""
    return werte.get(code(), werte[DEUTSCH])


_TABELLEN: dict[str, dict[str, dict[str, Any]]] = {}
_GEMELDET: set[tuple[str, str, str]] = set()


def tabelle(sprachcode: str) -> dict[str, dict[str, Any]]:
    """Die Tabelle einer Sprache, einmal je Prozess gelesen (wie das Profil:
    kein Hot-Reload, eine halb gespeicherte Datei waere ein Halbstart)."""
    if sprachcode not in _TABELLEN:
        pfad = VERZEICHNIS / sprachcode / TABELLENDATEI
        _TABELLEN[sprachcode] = (
            tomllib.loads(pfad.read_text(encoding="utf-8")) if pfad.is_file() else {}
        )
    return _TABELLEN[sprachcode]


def vergiss() -> None:
    """Nur fuer Tests und Pruefskripte."""
    _TABELLEN.clear()
    _GEMELDET.clear()


def modulschluessel(modul: str) -> str:
    """``interview_theater.knoepfe.texte`` -> ``knoepfe.texte``."""
    return modul[len(PAKET):] if modul.startswith(PAKET) else modul


def angleichen(deutsch: Any, eintrag: Any) -> Any:
    """Gibt dem Tabelleneintrag die Form der deutschen Konstante: TOML kennt
    weder Tupel noch Zahlen als Schluessel, der Code erwartet beides."""
    if isinstance(deutsch, dict) and isinstance(eintrag, dict):
        schluesseltyp = type(next(iter(deutsch))) if deutsch else str
        muster = next(iter(deutsch.values())) if deutsch else None
        return {schluesseltyp(k): angleichen(muster, v) for k, v in eintrag.items()}
    if isinstance(deutsch, (tuple, list, set, frozenset)) and isinstance(eintrag, list):
        muster = next(iter(deutsch)) if deutsch else None
        return type(deutsch)(angleichen(muster, v) for v in eintrag)
    return eintrag


def text(modul: str, name: str) -> Any:
    """Der Text ``name`` aus ``modul`` in der aktiven Sprache."""
    deutsch = getattr(sys.modules[modul], name)
    sprachcode = code()
    if sprachcode == DEUTSCH:
        return deutsch
    eintrag = tabelle(sprachcode).get(modulschluessel(modul), {}).get(name)
    if eintrag is None:
        schluessel = (sprachcode, modul, name)
        if schluessel not in _GEMELDET:
            _GEMELDET.add(schluessel)
            log.warning("Kein %s-Text fuer %s.%s -- es bleibt Deutsch",
                        sprachcode, modulschluessel(modul), name)
        return deutsch
    return angleichen(deutsch, eintrag)


class Texte:
    """Die Texte eines Moduls, zur Aufrufzeit in der aktiven Sprache:
    ``T = sprache.Texte(__name__)``, dann ``T._TEXT_X``."""

    __slots__ = ("_modul",)

    def __init__(self, modul: str) -> None:
        object.__setattr__(self, "_modul", modul)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return text(self._modul, name)

    def __setattr__(self, name: str, wert: Any) -> None:
        raise AttributeError("Texte sind nur lesbar")


_FELD = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)(?:[!:][^{}]*)?\}(?!\})")
_PROFIL = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_PROZENT = re.compile(r"%(?:\([^)]*\))?[#0\- +]*\d*(?:\.\d+)?[sdifr]")


def platzhalter(text: str) -> frozenset[str]:
    """Die Platzhalter eines Textes als Menge: ``{name}``, ``{{name}}``,
    ``%s``. Deutsch und Englisch muessen dieselbe Menge tragen (K3)."""
    return frozenset(
        [f"{{{n}}}" for n in _FELD.findall(text)]
        + [f"{{{{{n}}}}}" for n in _PROFIL.findall(text)]
        + _PROZENT.findall(text)
    )
```

`interview_theater/sprachen/en/texte.toml`:

```toml
# Die englische Texttabelle (Karte A1, 30.09.2026).
#
# Je definierendem Modul eine Tabelle (Modulname ohne "interview_theater.",
# in Anfuehrungszeichen), darin der Name der deutschen Konstante. Gelesen
# wird ueber interview_theater/sprache.py (T._TEXT_X). Platzhalter
# ({name}, {{name}}, %s) muessen dieselben sein wie im Deutschen --
# tests/test_sprache_texte.py prueft das. Die Texte sind Uebersetzungen;
# Birk nimmt sie in Karte P am Prompt-Dump ab.
```

- [x] **Schritt 4: `scripts/pruefe_sprache.py` (Kern)**

```python
"""Findet deutsche Saetze in allem, was ein Profil erzeugt (Karte A1, D10).

Die Abnahme (3) der Karte: mit ``padua-2026`` enthaelt **kein** Chat-,
Knopf- oder Prompttext mehr einen deutschen Satz -- mechanisch geprueft,
nicht gelesen. Positivkontrolle: gegen ``dortmund-2026`` muss der Pruefer
anschlagen, sonst prueft er nichts.

Zwei Signale, casefold, an Wortgrenzen:

* ``STOPPWOERTER`` -- deutsche Funktionswoerter, die weder englisch noch
  italienisch sind,
* ``UI_WOERTER`` -- deutsche Inhaltswoerter aus Knopf- und Systemzeilen
  ("Ja, speichern", "Notiert:"), die kein Funktionswort tragen (W2),

dazu Umlaute/ß als eigenes Signal. Ausgenommen: Protokoll-Token (Woerter
nur aus Grossbuchstaben, snake_case, ``{…}``/``{{…}}``-Platzhalter) und
``ERLAUBT`` (Formnamen als Datenbankwerte, Stil-Slugs, erfundene Namen).

Aufruf::

    python -m scripts.pruefe_sprache --dateien <pfad> [<pfad> ...]
    python -m scripts.pruefe_sprache --schluessel <modul>[,<modul> ...]
    python -m scripts.pruefe_sprache <profil> [--quelle prompts,texte,durchlauf,web]   # ab Aufgabe 30

Exit 0 nur ohne Treffer.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: Deutsche Funktionswoerter (Brief D10) plus einige, die in Knopftexten
#: tragen. Keins davon ist ein englisches oder italienisches Wort.
STOPPWOERTER = frozenset({
    "und", "nicht", "ist", "ihr", "euch", "wir", "ich", "mit", "fuer", "für",
    "auf", "eine", "einen", "noch", "schon", "auch", "oder", "wenn", "dass",
    "sich", "werden", "bitte", "jetzt", "hier", "sind", "habt", "eure",
    "euer", "uns", "kein", "keine", "nichts", "dann", "weil", "aber", "zum",
    "zur", "beim", "ueber", "über", "wird", "seid", "wollt", "koennt",
    "könnt", "sagt", "mir", "dir", "du", "dein", "deine",
})

#: Deutsche Inhaltswoerter aus Knopf- und Systemzeilen, die ohne
#: Funktionswort stehen (W2). Kuratiert aus knoepfe/texte.py, befehle.py,
#: aufnahme.py, erkenner.baue_meldung und web.py; keins ist ein englisches
#: Wort.
UI_WOERTER = frozenset({
    "ja", "nein", "speichern", "gespeichert", "notiert", "weiter", "zurueck",
    "zurück", "fertig", "aufnahme", "aufnahmen", "auswerten", "ausgewertet",
    "begriffe", "fragen", "figur", "figuren", "szene", "szenen", "geschichte",
    "kurzgeschichte", "textbuch", "fassung", "fassungen", "leitfaden",
    "eroeffnung", "eröffnung", "abschluss", "einleitung", "einleitungen",
    "verdichtung", "kernthema", "stueck", "stück", "passt", "anders", "neu",
    "schreiben", "zeigen", "ansehen", "kuerzer", "kürzer", "hinweis",
    "schweiz", "bereit", "laeuft", "läuft", "beendet", "gruppe",
    "feinschliff", "schaerfung", "schärfung", "sprechanteile",
    "probenansicht", "arbeitsstand", "festlegung", "festlegungen", "stand",
    "hilfe", "starten", "beenden", "interviewpartnerin", "sprachnachricht",
    "sprachnachrichten", "zusammenfassung", "transkript", "knopf", "knoepfe",
    "knöpfe", "vorschlag", "runde", "entfernt", "zurueckgenommen",
    "zurückgenommen", "uebernommen", "übernommen", "abgeschlossen",
})

#: Woerter, die in englischen Texten legitim stehen: Formnamen als
#: Datenbankwerte (``szene.form``), Stil-Slugs, Profil-Beispielorte (Padua,
#: italienisch), und die Namen der Phasen, soweit sie Protokoll sind.
ERLAUBT = frozenset({
    "dialog", "monolog", "chor", "lied", "rap", "prosa",
    "herkules", "schlagabtausch", "litanei",
    "fermata", "piazza", "bar", "stazione",
})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")
_UMLAUT = re.compile(r"[äöüÄÖÜß]")
#: Was vor dem Pruefen herausgenommen wird: Platzhalter, snake_case-Namen
#: (Erkenner-Arten, JSON-Schluessel, Feldnamen), Woerter nur aus
#: Grossbuchstaben (Protokoll-Marker wie VORSCHLAG FRAGENAUSWAHL:, BEFUND:),
#: URLs und Dateipfade.
_AUSSEN_VOR = re.compile(
    r"\{\{[a-z0-9_]+\}\}|\{[A-Za-z0-9_!:>< .]*\}"
    r"|\b[a-z]+(?:_[a-z0-9]+)+\b"
    r"|\b[A-ZÄÖÜ]{2,}(?:[ _][A-ZÄÖÜ]{2,})*\b"
    r"|https?://\S+|\b[\w./-]+\.(?:md|toml|py|txt|json|jsonl)\b"
)


@dataclass(frozen=True)
class Treffer:
    quelle: str
    wort: str
    ausschnitt: str


def deutsche_treffer(quelle: str, text: str) -> list[Treffer]:
    """Jedes deutsche Signal in ``text``, mit Ausschnitt."""
    gesaeubert = _AUSSEN_VOR.sub(lambda t: " " * len(t.group(0)), text or "")
    treffer = []
    for wort in _WORT.finditer(gesaeubert):
        roh = wort.group(0)
        klein = roh.casefold()
        if klein in ERLAUBT:
            continue
        if klein in STOPPWOERTER or klein in UI_WOERTER:
            zeichen = klein
        elif _UMLAUT.search(roh):
            zeichen = _UMLAUT.search(roh).group(0)
        else:
            continue
        anfang = max(0, wort.start() - 30)
        ausschnitt = " ".join(text[anfang:wort.end() + 30].split())
        treffer.append(Treffer(quelle, zeichen, ausschnitt))
    return treffer


def pruefe_dateien(pfade: list[Path]) -> list[Treffer]:
    treffer = []
    for pfad in pfade:
        treffer += deutsche_treffer(str(pfad), Path(pfad).read_text(encoding="utf-8"))
    return treffer


def _blaetter(wert, pfad: str):
    if isinstance(wert, str):
        yield pfad, wert
    elif isinstance(wert, dict):
        for k, v in wert.items():
            if k in ("slug", "command"):
                continue
            yield from _blaetter(v, f"{pfad}.{k}")
    elif isinstance(wert, (list, tuple)):
        for i, v in enumerate(wert):
            yield from _blaetter(v, f"{pfad}[{i}]")


def pruefe_schluessel(module: list[str], sprachcode: str = "en") -> list[Treffer]:
    """Die Werte der Tabelle fuer ``module`` (leer = alle) -- genau das, was
    ``sprache.text`` zur Laufzeit liefert. Schluessel werden nicht geprueft:
    Beschriftungstabellen (K4) haben deutsche Schluessel."""
    from interview_theater import sprache

    sprache.vergiss()
    tabelle = sprache.tabelle(sprachcode)
    treffer = []
    for modul in module or sorted(tabelle):
        for name, wert in tabelle.get(modul, {}).items():
            for pfad, text in _blaetter(wert, f"{modul}.{name}"):
                treffer += deutsche_treffer(pfad, text)
    return treffer


def _ausgabe(treffer: list[Treffer]) -> int:
    for t in treffer:
        print(f"{t.quelle}: {t.wort!r} in: {t.ausschnitt}")
    print(f"{len(treffer)} Treffer")
    return 1 if treffer else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.pruefe_sprache")
    p.add_argument("profil", nargs="?")
    p.add_argument("--dateien", nargs="+", type=Path)
    p.add_argument("--schluessel")
    args = p.parse_args(argv)
    if args.dateien:
        return _ausgabe(pruefe_dateien(args.dateien))
    if args.schluessel is not None:
        module = [m.strip() for m in args.schluessel.split(",") if m.strip()]
        return _ausgabe(pruefe_schluessel(module))
    p.error("--dateien, --schluessel oder (ab Aufgabe 30) ein Profilname")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Schritt 5: `text_schnappschuss.wert` ueber die Sprache leiten**

```python
def wert(modul, name: str):
    """Der Wert, wie ihn der Code zur Laufzeit sieht: hat das Modul einen
    Textzugriff ``T`` (Karte A1), dann ueber ``sprache.text`` -- so prueft
    der Bitgleichheits-Test auch, dass der Zugriff im Deutschen dasselbe
    liefert wie die Konstante."""
    from interview_theater import sprache

    if isinstance(getattr(modul, "T", None), sprache.Texte):
        return sprache.text(modul.__name__, name)
    return getattr(modul, name)
```

- [x] **Schritt 6: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache.py tests/test_pruefe_sprache.py tests/test_sprache_bitgleich.py`
Expected: alle gruen.

- [x] **Schritt 7: Mutationsnachweis**

- In `sprache.text` die Zeile `if sprachcode == DEUTSCH: return deutsch`
  entfernen → `test_deutsch_ist_die_konstante_selbst` rot (`is`-Vergleich
  scheitert, weil die Tabelle den Eintrag liefert).
- In `angleichen` die Zeile mit `schluesseltyp(k)` durch `k` ersetzen →
  `test_behaelter_bekommen_ihre_deutsche_form` rot.
- In `UI_WOERTER` `"speichern"` streichen →
  `test_ui_woerter_schlagen_an_auch_ohne_funktionswort` rot.
Jeweils zuruecksetzen.

- [x] **Schritt 8: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/sprache.py interview_theater/sprachen/en/texte.toml \
        scripts/pruefe_sprache.py scripts/text_schnappschuss.py \
        tests/test_sprache.py tests/test_pruefe_sprache.py
git commit -m "sprache.py: Textzugriff zur Aufrufzeit, englische Tabelle, Stoppwort-Kern (A1)"
```

---

## Aufgabe 4: Die Sprachschicht fuer Prompts (D4, W6)

**Files:**
- Modify: `interview_theater/anweisungen.py:71` (neues `_SPRACHEN`),
  `:170–202` (`_bausteine`), `:247–256` (`_roh`), `:85` (`UEBERSCHRIFT` bleibt,
  Verwendung `:334` ueber `T`), Modulende (`T`)
- Modify: `interview_theater/workshop.py:828–831` (`formen_liste_oder`)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["anweisungen"]`)
- Create: `interview_theater/sprachen/en/prompts/.gitkeep`
- Test: `tests/test_sprache_prompts.py` (neu), `tests/test_anweisungen_profil.py`

**Interfaces:**
- Consumes: `sprache.code()`, `sprache.DEUTSCH`, `sprache.Texte`.
- Produces: `anweisungen.sprach_verzeichnis() -> Path | None`
  (`None` bei Deutsch), Suchreihenfolge **Profil → Sprachschicht → Repo** in
  `hole`/`hole_optional`/`_roh`, Bausteine **Repo → Sprachschicht → Profil**,
  Cache-Herkunft `f"sprache-{code}"` bzw. `f"baustein-sprache-{code}"`.
  `tests/test_sprache_prompts.NOCH_OFFEN: set[str]` — die Uebersetzungsaufgaben
  18–21 nehmen dort Namen heraus.

- [ ] **Schritt 1: Tests schreiben** — `tests/test_sprache_prompts.py`:

```python
"""Jede Repo-Prompt-Datei hat eine englische Fassung mit gleicher Struktur (D4).

``NOCH_OFFEN`` schrumpft mit jeder Uebersetzungsaufgabe (18-21) und ist am
Ende leer. Ein Name darf dort nur stehen, solange es die englische Datei noch
nicht gibt -- ``test_noch_offen_ist_ehrlich`` haelt das fest.
"""

import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, sprache, workshop

REPO = anweisungen._VERZEICHNIS
EN = sprache.VERZEICHNIS / "en" / "prompts"


def _namen(wurzel: Path) -> set[str]:
    if not wurzel.is_dir():
        return set()
    return {str(p.relative_to(wurzel).with_suffix("")).replace("\\", "/")
            for p in wurzel.rglob("*.md")}


REPO_NAMEN = _namen(REPO)

#: Noch nicht uebersetzt. Am Anfang alle 38; Aufgabe 21 leert die Menge.
NOCH_OFFEN = set(REPO_NAMEN)

#: Inhaltsbausteine (W1): ihre deutsche Fassung traegt Dortmund-Inhalt
#: woertlich, die englische ist eine generische Vorlage aus Profilwerten.
INHALTSBAUSTEINE = {"rahmen", "rahmen-kurz", "rahmen-knapp", "projekt"}

_PLATZ = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")


def _struktur(text: str) -> tuple[int, int, int]:
    """Ueberschriften, Code-Zaeune, JSON-Beispielzeilen -- was eine
    Uebersetzung nicht verlieren darf (Few-Shots im Erkenner: 21)."""
    return (
        len(re.findall(r"(?m)^#{1,6} ", text)),
        len(re.findall(r"(?m)^```", text)),
        len(re.findall(r'(?m)^\{"', text)),
    )


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_jede_repo_datei_hat_eine_englische_fassung():
    fehlend = sorted(REPO_NAMEN - _namen(EN) - NOCH_OFFEN)
    assert fehlend == []


def test_noch_offen_ist_ehrlich():
    assert sorted(NOCH_OFFEN & _namen(EN)) == [], "uebersetzt, aber noch in NOCH_OFFEN"


def test_keine_englische_datei_ohne_repo_gegenstueck():
    assert sorted(_namen(EN) - REPO_NAMEN) == []


@pytest.mark.parametrize("name", sorted(REPO_NAMEN - INHALTSBAUSTEINE))
def test_gleiche_platzhalter_und_struktur(name):
    en = EN / f"{name}.md"
    if not en.is_file():
        pytest.skip("noch nicht uebersetzt")
    deutsch = (REPO / f"{name}.md").read_text(encoding="utf-8")
    englisch = en.read_text(encoding="utf-8")
    assert set(_PLATZ.findall(englisch)) == set(_PLATZ.findall(deutsch))
    assert _struktur(englisch) == _struktur(deutsch)


@pytest.mark.parametrize("name", sorted(INHALTSBAUSTEINE))
def test_inhaltsbausteine_nutzen_nur_profilwerte(name):
    en = EN / f"{name}.md"
    if not en.is_file():
        pytest.skip("noch nicht uebersetzt")
    bekannt = set(workshop.platzhalter())
    assert set(_PLATZ.findall(en.read_text(encoding="utf-8"))) <= bekannt


def test_deutsch_liest_nie_die_sprachschicht(monkeypatch, tmp_path):
    """Dortmund bleibt bitgleich: bei code == 'de' gibt es keine Schicht."""
    assert anweisungen.sprach_verzeichnis() is None


def test_englisch_liest_die_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "journal.md").write_text("Answer in English.", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path)
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert anweisungen.hole("journal") == "Answer in English."
    # Wo es keine englische Datei gibt, gilt weiter das Repo.
    assert anweisungen.hole("verdichter") == (REPO / "verdichter.md").read_text(encoding="utf-8")


def test_profil_schlaegt_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "sprachen" / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "journal.md").write_text("From the language layer.", encoding="utf-8")
    profil = tmp_path / "workshops" / "englisch-test"
    (profil / "prompts").mkdir(parents=True)
    (profil / "profil.toml").write_text(
        'beschreibung = "t"\n[sprache]\ncode = "en"\nanrede = "you"\n'
        '[zielgruppe]\nbeschreibung = "x"\n', encoding="utf-8")
    (profil / "prompts" / "journal.md").write_text("From the profile.", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path / "sprachen")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path / "workshops"))
    monkeypatch.setenv(workshop.VARIABLE, "englisch-test")
    workshop.vergiss()
    assert anweisungen.hole("journal") == "From the profile."


def test_bausteine_aus_der_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "rahmen.md").write_text("FRAME for {{zielgruppe}}", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path)
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert anweisungen.platzhalter()["rahmen"] == "FRAME for {{zielgruppe}}"


def test_formenliste_oder_je_sprache(monkeypatch):
    workshop.vergiss()
    assert " oder " in workshop.platzhalter()["formen_liste_oder"]
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert " or " in workshop.platzhalter()["formen_liste_oder"]


def test_ueberschrift_des_regiezettels_ueber_die_tabelle(monkeypatch):
    assert anweisungen.T.UEBERSCHRIFT == anweisungen.UEBERSCHRIFT
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert "Additional instruction" in anweisungen.T.UEBERSCHRIFT
```

- [ ] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py`
Expected: FAIL — `AttributeError: module 'interview_theater.anweisungen' has no attribute 'sprach_verzeichnis'`
(bzw. `… has no attribute 'T'`) und `assert ' or ' in 'Dialog, Monolog, Chor, Lied oder Rap'`.

- [ ] **Schritt 3: Umsetzen**

`interview_theater/anweisungen.py` nach `_VERZEICHNIS = …` (Zeile 71):

```python
def sprach_verzeichnis() -> Path | None:
    """Die Sprachschicht des aktiven Profils (Karte A1): englische Fassungen
    der Repo-Prompts unter ``sprachen/<code>/prompts/``, gleicher relativer
    Pfad. Bei Deutsch gibt es keine -- dort sind die Repo-Dateien die
    Sprache, und Dortmund bleibt bitgleich.

    Die Schicht liegt bewusst NICHT unter ``prompts/``: dort sammelt
    ``scripts/prompt_schnappschuss._prompt_namen`` per rglob, und neue
    Abschnitte veraenderten den Dortmund-Massstab."""
    from interview_theater import sprache

    if sprache.code() == sprache.DEUTSCH:
        return None
    return sprache.VERZEICHNIS / sprache.code() / "prompts"


def _sprach_pfad(name: str) -> Path | None:
    """Pfad einer Prompt-Datei in der Sprachschicht, dieselbe Pfadpruefung
    wie ``_pfad``."""
    wurzel = sprach_verzeichnis()
    if wurzel is None:
        return None
    pfad = (wurzel / f"{name}.md").resolve()
    if not pfad.is_relative_to(wurzel.resolve()):
        raise ValueError(f"Prompt-Name zeigt aus der Sprachschicht heraus: {name!r}")
    return pfad
```

(Der Import steht **in** der Funktion: `sprache` importiert `workshop`,
`anweisungen` wird von `workshop` nicht importiert — ein Kopfimport ginge
auch, der lokale Import haelt aber die Regel „Dienste lesen nur nach unten"
sichtbar. Wer ihn nach oben zieht, laesst `test_anweisungen*.py` laufen.)

`_bausteine` (Zeile 194) — die Schleife bekommt die Schicht in die Mitte:

```python
    from interview_theater import sprache

    profil = workshop.name()
    werte: dict[str, str] = {}
    schichten = (
        ("repo", _VERZEICHNIS),
        (f"sprache-{sprache.code()}", sprach_verzeichnis()),
        ("profil", profil_verzeichnis()),
    )
    for herkunft, wurzel in schichten:
        if wurzel is None or not wurzel.is_dir():
            continue
        ...  # Rest unveraendert
```

Den Docstring von `_bausteine` um einen Satz ergaenzen: „Seit Karte A1 liegt
zwischen Repo und Profil die Sprachschicht; bei Deutsch ist sie leer."

`_roh` (Zeile 247):

```python
def _roh(name: str) -> str | None:
    """Der Prompt-Text ohne Platzhalter -- aus dem Profil, sonst aus der
    Sprachschicht (Karte A1, nur bei code != "de"), sonst aus dem Repo."""
    from interview_theater import sprache

    profil = workshop.name()
    eigen = _profil_pfad(name)
    if eigen is not None:
        text = _lies(eigen, (profil, "profil", name))
        if text is not None:
            return text
    uebersetzt = _sprach_pfad(name)
    if uebersetzt is not None:
        text = _lies(uebersetzt, (profil, f"sprache-{sprache.code()}", name))
        if text is not None:
            return text
    return _lies(_pfad(name), (profil, "repo", name))
```

In `system()` Zeile 334: `teile.append(UEBERSCHRIFT + text.strip())` →
`teile.append(T.UEBERSCHRIFT + text.strip())`. Am Dateiende:

```python
from interview_theater import sprache  # noqa: E402  (unten: kein Zyklus beim Import)

T = sprache.Texte(__name__)
```

`interview_theater/workshop.py` — vor `platzhalter()`:

```python
#: Wie eine Auswahl im Fliesstext verbunden wird ("Lied oder Rap"). Hier und
#: nicht in sprache.py, weil sprache.py dieses Modul importiert (Karte A1).
_ODER = {"de": " oder ", "en": " or "}
```

und in `platzhalter()` (Zeile 829) `" oder ".join(` →
`_ODER.get(str(profil.wert("sprache.code", "de")), " oder ").join(`.

`interview_theater/sprachen/en/texte.toml` anhaengen:

```toml
["anweisungen"]
UEBERSCHRIFT = "\n\nAdditional instruction for this workshop:\n\n"
```

`interview_theater/sprachen/en/prompts/.gitkeep` leer anlegen.

- [ ] **Schritt 4: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_anweisungen.py tests/test_anweisungen_profil.py tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py`
Expected: alle gruen; in `test_sprache_prompts.py` 34 + 4 Faelle `skipped`
(„noch nicht uebersetzt").

- [ ] **Schritt 5: Mutationsnachweis**

In `sprach_verzeichnis` die Deutsch-Abfrage entfernen → nichts wird rot,
**solange** `sprachen/de/` fehlt — deshalb die zweite Mutation: in `_roh` die
Reihenfolge Profil/Sprachschicht tauschen → `test_profil_schlaegt_sprachschicht`
rot. `_ODER` auf nur `{"de": " oder "}` → `test_formenliste_oder_je_sprache` rot.

- [ ] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/anweisungen.py interview_theater/workshop.py \
        interview_theater/sprachen/en/texte.toml interview_theater/sprachen/en/prompts/.gitkeep \
        tests/test_sprache_prompts.py
git commit -m "Prompts: Sprachschicht zwischen Repo und Profil, Verbinder je Sprache (A1)"
```

---

## Aufgabe 5: Der Text-Waechter (AST) — Vollstaendigkeit, Platzhalter, keine nackten Texte (D3)

Ab hier gilt fuer jedes Modul in `UMGESTELLT`: jede Nutzertext-Konstante
laeuft ueber `T`, hat einen englischen Eintrag mit gleichen Platzhaltern, und
es gibt dort keine deutschen Inline-Literale mehr (ausser erlaubten
Vorfall-Details). Die Aufgaben 8 und 10–17 fuegen ihre Module hinzu.

**Files:**
- Create: `tests/test_sprache_texte.py`

**Interfaces:**
- Produces: `tests/test_sprache_texte.UMGESTELLT: set[str]` (Modulkurznamen),
  `BLEIBT_DEUTSCH: dict[str, str]` (`"<modul>.<NAME>" -> Grund`),
  `PARSER: set[str]` (D5-Wortlisten, keine Texttabelle),
  `INLINE_ERLAUBT: dict[tuple[str, str], str]`
  (`(modul, Anfang des Literals bis 40 Zeichen) -> Grund`).
  `ALLE_MODULE: set[str]` — die Menge, die `UMGESTELLT` in Aufgabe 17
  erreichen muss.

- [ ] **Schritt 1: Den Test schreiben**

```python
"""Die Texttabelle ist vollstaendig, und jeder Nutzertext laeuft ueber sie (D3).

Am Quelltext geprueft (AST), wie ``test_knoepfe_struktur.py``: ein neuer
Knopftext, der am Zugriff ``T`` vorbeigeht, faellt hier auf und nicht erst
in Padua im Chat.

1. Jeder Zugriff ``T.NAME`` / ``modul.T.NAME`` zeigt auf eine deutsche
   Modul-Konstante und hat einen englischen Eintrag.
2. Kein englischer Eintrag ohne deutsche Konstante.
3. Platzhalter (``{name}``, ``{{name}}``, ``%s``) gleich, Blatt fuer Blatt;
   Behaelter gleich gebaut; ``slug``/``command`` woertlich gleich.
4. In einem umgestellten Modul liest niemand eine registrierte Konstante
   mehr nackt (``_TEXT_X`` statt ``T._TEXT_X``).
5. Ein umgestelltes Modul hat keine deutsche Konstante ausserhalb der
   Tabelle und keine deutschen Inline-Literale -- ausser mit Grund.
"""

import ast
import pathlib
import re

import pytest

from interview_theater import sprache

PAKET = pathlib.Path(sprache.__file__).resolve().parent

#: Module (Kurzname), deren Texte ueber T laufen. Waechst je Aufgabe.
UMGESTELLT: set[str] = {"anweisungen"}

#: Was UMGESTELLT in Aufgabe 17 erreicht haben muss.
ALLE_MODULE = {
    "ablauf", "anweisungen", "arbeitszeilen", "aufnahme", "befehle", "bot",
    "dramaturgie.beleg", "dramaturgie.fanout", "dramaturgie.mechanik",
    "erkenner", "fehlstellen", "journal", "kernzitate", "knoepfe.basis",
    "knoepfe.figuren", "knoepfe.fragen", "knoepfe.interviews",
    "knoepfe.stationen", "knoepfe.szenen", "knoepfe.texte", "knoepfe.wirkung",
    "kontext", "kuerzung", "kurzgeschichte", "leitfaden", "phasen",
    "phasentexte", "schaerfung", "sprachprofil", "sprachstil", "sprecher",
    "stile", "stueckpruefung", "szene", "szenenfolge", "verdichter",
    "vorspann", "web", "web_schreiben",
}

#: Bleibt deutsch, mit Grund (nie im Chat, nie im Prompt einer Gruppe).
BLEIBT_DEUTSCH = {
    "dramaturgie.bilanz.KOPF": "Betreiberausgabe (scripts/dramaturgie_pruefen.py)",
    "dramaturgie.bilanz.OHNE_VERGLEICH": "Betreiberausgabe",
    "dramaturgie.schleife.GRUENDE": "Betreiberausgabe (--schleife)",
    "dramaturgie.schleife.MELDUNG_OHNE_GESCHICHTENWEG": "Betreiberausgabe (--schleife)",
    "szenenfolge.DETAIL_RICHTUNG_UNVOLLSTAENDIG": "Vorfall-Detail, Dashboard des Teams",
}

#: Wortlisten fuer Parser (D5) -- keine Texttabelle, sondern Code mit
#: englischem Gegenstueck *_EN (Aufgaben 22-24).
PARSER = {
    "ablauf._DENKSPUR_MARKER", "ablauf._DENKSPUR_EINDEUTIG",
    "ablauf._AUFTRAGSFORMEN", "ablauf._SYSTEMZEILEN",
    "befehle._ENTFERNEN_WOERTER", "kontext._SYSTEMANFAENGE",
    "szene._ANDERS_NICHTS", "dramaturgie.mechanik._STRUKTUR",
    "dramaturgie.mechanik._TSCHECHOW_STOPP", "dramaturgie.mechanik._STRANG_STOPP",
    "vorspann.SCHAERFUNGSFORMELN", "stueckpruefung.FRAGEN",
}

#: Deutsche Inline-Literale, die bleiben duerfen: Vorfall-Details
#: (repo.merke_vorfall, Dashboard des Teams). Schluessel: Modul und die
#: ersten 40 Zeichen des Literals, wie ``_inline_texte`` sie liefert.
INLINE_ERLAUBT: dict[tuple[str, str], str] = {}

_STOPP = re.compile(
    r"\b(und|nicht|ist|ihr|euch|wir|ich|mit|fuer|für|auf|eine|noch|schon|"
    r"auch|oder|wenn|dass|sich|bitte|jetzt|hier|sind|eure|euer|uns|kein|"
    r"keine|den|dem|du|dein|deine)\b", re.I)
_TEXTNAME = re.compile(r"^_?(TEXT|UEBERSCHRIFT|ANWEISUNG|MELDUNG|JOURNAL|HINWEIS|ZEILE)"
                       r"|_(KOPF|ANSCHLUSS|HINWEIS)$")


def _kurz(pfad: pathlib.Path) -> str:
    return ".".join(pfad.relative_to(PAKET).with_suffix("").parts).removesuffix(".__init__")


BAEUME = {_kurz(p): ast.parse(p.read_text(encoding="utf-8"))
          for p in sorted(PAKET.rglob("*.py"))}


def _konstanten(baum) -> dict[str, ast.AST]:
    fertig = {}
    for knoten in baum.body:
        ziele = []
        if isinstance(knoten, ast.Assign):
            ziele = [z.id for z in knoten.targets if isinstance(z, ast.Name)]
        elif isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
            ziele = [knoten.target.id]
        for z in ziele:
            if re.match(r"^_?[A-Z][A-Z0-9_]*$", z):
                fertig[z] = knoten
    return fertig


KONSTANTEN = {m: _konstanten(b) for m, b in BAEUME.items()}


def _hat_eigenes_t(baum) -> bool:
    return any(
        isinstance(k, ast.Assign)
        and any(isinstance(z, ast.Name) and z.id == "T" for z in k.targets)
        for k in baum.body
    )


def _aliase(modul: str, baum) -> dict[str, str]:
    """Name im Modul -> Kurzname des Moduls, aus dem er stammt, fuer alle
    Importe (auch lokale in Funktionen)."""
    aliase = {}
    for k in ast.walk(baum):
        if isinstance(k, ast.ImportFrom) and k.module and k.module.startswith("interview_theater"):
            basis = k.module[len("interview_theater"):].lstrip(".")
            for n in k.names:
                ziel = f"{basis}.{n.name}".lstrip(".") if f"{basis}.{n.name}".lstrip(".") in BAEUME else basis
                aliase[n.asname or n.name] = ziel
        elif isinstance(k, ast.Import):
            for n in k.names:
                if n.name.startswith("interview_theater."):
                    aliase[n.asname or n.name.split(".")[-1]] = n.name[len("interview_theater."):]
    # ``knoepfe`` re-exportiert T aus knoepfe.texte
    return {name: ("knoepfe.texte" if ziel == "knoepfe" else ziel) for name, ziel in aliase.items()}


def _zugriffe() -> list[tuple[str, str, str, int]]:
    """(lesendes Modul, Zielmodul, NAME, Zeile) fuer jedes T.NAME."""
    fertig = []
    for modul, baum in BAEUME.items():
        aliase = _aliase(modul, baum)
        eigenes = _hat_eigenes_t(baum)
        for k in ast.walk(baum):
            if not isinstance(k, ast.Attribute) or not isinstance(k.value, (ast.Name, ast.Attribute)):
                continue
            wert = k.value
            if isinstance(wert, ast.Name) and wert.id == "T":
                ziel = modul if eigenes else aliase.get("T")
            elif (isinstance(wert, ast.Attribute) and wert.attr == "T"
                  and isinstance(wert.value, ast.Name)):
                ziel = aliase.get(wert.value.id)
                ziel = "knoepfe.texte" if ziel == "knoepfe" else ziel
            else:
                continue
            if ziel is not None:
                fertig.append((modul, ziel, k.attr, k.lineno))
    return fertig


ZUGRIFFE = _zugriffe()


def _tabelle():
    sprache.vergiss()
    return sprache.tabelle("en")


def test_jeder_zugriff_zeigt_auf_eine_deutsche_konstante():
    falsch = [f"{m}:{z} {ziel}.{n}" for m, ziel, n, z in ZUGRIFFE
              if n not in KONSTANTEN.get(ziel, {})]
    assert falsch == []


def test_jeder_zugriff_hat_einen_englischen_eintrag():
    tabelle = _tabelle()
    fehlend = sorted({f"{ziel}.{n}" for _, ziel, n, _ in ZUGRIFFE
                      if n not in tabelle.get(ziel, {})})
    assert fehlend == []


def test_kein_englischer_eintrag_ohne_deutsche_konstante():
    tabelle = _tabelle()
    verwaist = [f"{m}.{n}" for m, eintraege in tabelle.items()
                for n in eintraege if n not in KONSTANTEN.get(m, {})]
    assert verwaist == []


def _paare(deutsch, englisch, pfad):
    if isinstance(deutsch, str):
        yield pfad, deutsch, englisch
    elif isinstance(deutsch, dict):
        assert isinstance(englisch, dict), pfad
        assert {str(k) for k in deutsch} == {str(k) for k in englisch}, pfad
        for k, v in deutsch.items():
            e = englisch[k] if k in englisch else englisch[str(k)]
            if k in ("slug", "command"):
                assert e == v, f"{pfad}.{k} ist Protokoll"
                continue
            yield from _paare(v, e, f"{pfad}.{k}")
    elif isinstance(deutsch, (list, tuple, set, frozenset)):
        assert isinstance(englisch, (list, tuple, set, frozenset)), pfad
        assert len(deutsch) == len(englisch), pfad
        for i, (d, e) in enumerate(zip(deutsch, englisch)):
            yield from _paare(d, e, f"{pfad}[{i}]")


@pytest.mark.parametrize("modul, name", sorted(
    (m, n) for m, eintraege in _tabelle().items() for n in eintraege))
def test_platzhalter_und_form_gleich(modul, name):
    import importlib

    deutsch = getattr(importlib.import_module(f"interview_theater.{modul}"), name)
    englisch = sprache.angleichen(deutsch, _tabelle()[modul][name])
    if isinstance(deutsch, dict) and englisch.keys() != deutsch.keys() and all(
            isinstance(k, str) for k in deutsch):
        # Beschriftungstabelle (K4): deutsche Schluessel, englische Werte
        assert set(englisch) <= set(deutsch), f"{modul}.{name}"
        return
    for pfad, d, e in _paare(deutsch, englisch, f"{modul}.{name}"):
        assert sprache.platzhalter(d) == sprache.platzhalter(e), pfad


def _registriert(tabelle) -> set[tuple[str, str]]:
    return {(m, n) for m, eintraege in tabelle.items() for n in eintraege}


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_nackte_verwendung(modul):
    tabelle = _tabelle()
    registriert = _registriert(tabelle)
    baum = BAEUME[modul]
    aliase = _aliase(modul, baum)
    nackt = set()
    # Nur Lesezugriffe in Funktionen und Lambdas: dort laeuft Code zur
    # Aufrufzeit. Auf Modulebene setzt die deutsche Tabelle sich aus ihren
    # eigenen Konstanten zusammen -- das ist Definition, keine Verwendung.
    for funktion in ast.walk(baum):
        if not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        for k in ast.walk(funktion):
            if isinstance(k, ast.Name) and isinstance(k.ctx, ast.Load):
                herkunft = modul if k.id in KONSTANTEN[modul] else aliase.get(k.id)
                if herkunft and (herkunft, k.id) in registriert:
                    nackt.add(f"{modul}:{k.lineno} {k.id}")
    assert sorted(nackt) == []


def _sieht_deutsch_aus(wert) -> bool:
    if isinstance(wert, str):
        return bool(_STOPP.search(wert) or re.search(r"[äöüß]", wert))
    if isinstance(wert, dict):
        return any(_sieht_deutsch_aus(v) for v in wert.values())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return any(_sieht_deutsch_aus(v) for v in wert)
    return False


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_unuebersetzte_konstante(modul):
    import importlib

    tabelle = _tabelle()
    m = importlib.import_module(f"interview_theater.{modul}")
    offen = []
    for name in KONSTANTEN[modul]:
        schluessel = f"{modul}.{name}"
        if name in tabelle.get(modul, {}) or schluessel in BLEIBT_DEUTSCH or schluessel in PARSER:
            continue
        if name.startswith("ART_") or name.endswith("_EN"):
            continue
        wert = getattr(m, name, None)
        if isinstance(wert, re.Pattern):
            continue
        if _sieht_deutsch_aus(wert) or (_TEXTNAME.search(name) and isinstance(wert, str) and wert.strip()):
            offen.append(schluessel)
    assert offen == []


def _inline_texte(baum) -> list[tuple[int, str]]:
    """Deutsche String-Literale in Funktionen -- ohne Docstrings,
    log-/raise-Aufrufe und SQL (dieselbe Heuristik wie
    Anhang A.2 des Plans)."""
    verboten: set[int] = set()
    fertig = []

    class Sammler(ast.NodeVisitor):
        tiefe = 0

        def visit_FunctionDef(self, k):
            if k.body and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant):
                verboten.add(id(k.body[0].value))
            self.tiefe += 1
            self.generic_visit(k)
            self.tiefe -= 1

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, k):
            name = ast.unparse(k.func)
            if re.match(r"^(log|logging|_log|logger)\.", name) or name.endswith(("Fehler", "Error")):
                verboten.update(id(x) for x in ast.walk(k))
            self.generic_visit(k)

        def visit_Raise(self, k):
            verboten.update(id(x) for x in ast.walk(k))
            self.generic_visit(k)

        def visit_JoinedStr(self, k):
            self._pruefe(k, "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in k.values))
            verboten.update(id(x) for x in ast.walk(k))

        def visit_Constant(self, k):
            if isinstance(k.value, str):
                self._pruefe(k, k.value)

        def _pruefe(self, k, text):
            if self.tiefe == 0 or id(k) in verboten:
                return
            if re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|PRAGMA|WITH)\b", text, re.I):
                return
            worte = _STOPP.findall(text)
            if len(worte) >= 2 or (re.search(r"[äöüß]", text) and len(text) > 3) \
                    or (worte and len(text.split()) >= 3):
                fertig.append((k.lineno, text))

    Sammler().visit(baum)
    return fertig


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_deutschen_inline_texte(modul):
    offen = [f"{modul}:{zeile} {text[:60]!r}"
             for zeile, text in _inline_texte(BAEUME[modul])
             if (modul, text[:40]) not in INLINE_ERLAUBT]
    assert offen == []


def test_umgestellt_ist_teilmenge_von_alle_module():
    assert UMGESTELLT <= ALLE_MODULE
```

- [ ] **Schritt 2: Rot sehen, dann gruen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py`
Expected zuerst: gruen fuer `anweisungen` — **Rotsehen erzwingen:** in
`interview_theater/sprachen/en/texte.toml` den Eintrag `UEBERSCHRIFT` loeschen
→ `test_jeder_zugriff_hat_einen_englischen_eintrag` rot mit
`anweisungen.UEBERSCHRIFT`. Wiederherstellen → gruen.

- [ ] **Schritt 3: Mutationsnachweise**

- In `anweisungen.system()` `T.UEBERSCHRIFT` zurueck auf `UEBERSCHRIFT` →
  `test_keine_nackte_verwendung[anweisungen]` rot (`anweisungen:… UEBERSCHRIFT`).
- In `texte.toml` `"\n\nAdditional instruction for this workshop:\n\n"` durch
  `"Additional {x} instruction"` ersetzen → `test_platzhalter_und_form_gleich`
  rot. Zuruecksetzen.

- [ ] **Schritt 4: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add tests/test_sprache_texte.py
git commit -m "Text-Waechter: jeder Nutzertext ueber T, Tabelle vollstaendig, Platzhalter gleich (A1)"
```

**Hinweis fuer alle Folgeaufgaben (10–17):** Ein Modul „umstellen" heisst
immer dieselben fuenf Schritte:
1. `T = sprache.Texte(__name__)` ans Modulende (falls noch nicht da).
2. Jede Lese-Verwendung einer Text-Konstante `X` → `T.X` (fremde:
   `modul.T.X`). Liste der Stellen:
   `grep -nE "\b_?(TEXT|ANWEISUNG|UEBERSCHRIFT|MELDUNG|JOURNAL)[A-Z0-9_]*\b" interview_theater/<modul>.py`.
3. Jedes deutsche Inline-Literal, das an die Gruppe, in einen Knopf, ins
   Journal oder in einen Prompt geht, wird eine Konstante im selben Modul
   (in `knoepfe/*` in `knoepfe/texte.py`) — Name `_TEXT_…`, `JOURNAL_…`,
   `…_KOPF`. Vorfall-Details (`repo.merke_vorfall`) bleiben und kommen nach
   `INLINE_ERLAUBT`.
4. Englische Eintraege in `texte.toml` (Glossar K7, Stil K6, Platzhalter K3).
5. Modul in `UMGESTELLT` eintragen; `test_sprache_texte.py`,
   `test_sprache_bitgleich.py` und das Modul-Testfile laufen lassen;
   `$PY -m scripts.pruefe_sprache --schluessel <modul>` → `0 Treffer`.

---

## Aufgabe 6: Whisper bekommt die Sprache als Parameter, `auto` sendet keine (D2)

**Files:**
- Modify: `interview_theater/stt.py:29–36` (Logger), `:99` (`absenden`),
  `:127–131` (Multipart), `:164`/`:213–220` (`abholen`, erkannte Sprache),
  `:223` (`transkribiere`)
- Test: `tests/test_stt.py`

**Interfaces:**
- Produces: `stt.AUTO = "auto"`,
  `stt.absenden(e, klient, pfad, budget_s, *, sprache: str | None = "de") -> str`,
  `stt.transkribiere(e, klient, pfad, budget_s, *, sprache: str | None = "de") -> str`.
  `sprache in (None, "auto")` → kein Feld `language`. Vorgabe `"de"` haelt
  `scripts/rauchtest.py` und jeden Altaufrufer beim heutigen Verhalten.
  `stt.py` liest **keine** Datenbank (Dienste-Schicht, D2).

- [ ] **Schritt 1: Tests schreiben** (in `tests/test_stt.py` anhaengen; nutzt
  `_klient` und die Fixture `einst` aus der Datei bzw. `conftest.py`):

```python
def _multipart_mitschnitt(zustand):
    def handler(request):
        if "audio/transcriptions" in request.url.path:
            zustand["body"] = request.read()
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success",
            "data": json.dumps({"text": "Ciao a tutti.", "language": "italian"})})
    return handler


def test_ohne_angabe_bleibt_es_bei_deutsch(einst, tmp_path, monkeypatch):
    """Dortmund unveraendert: dasselbe Feld, derselbe Wert wie vor A1."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {}
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS")
    stt.transkribiere(einst, _klient(_multipart_mitschnitt(zustand)), datei, 30.0)
    assert b'name="language"\r\n\r\nde\r\n' in zustand["body"]


def test_auto_schickt_kein_language_feld(einst, tmp_path, monkeypatch):
    """Birk E5: die Interviewsprache ist offen -- Whisper erkennt sie selbst."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {}
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS")
    text = stt.transkribiere(
        einst, _klient(_multipart_mitschnitt(zustand)), datei, 30.0, sprache="auto")
    assert text == "Ciao a tutti."
    assert b'name="language"' not in zustand["body"]
    assert b'name="response_format"' in zustand["body"]


def test_gruppenwert_it_geht_als_language_it(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {}
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS")
    stt.transkribiere(einst, _klient(_multipart_mitschnitt(zustand)), datei, 30.0, sprache="it")
    assert b'name="language"\r\n\r\nit\r\n' in zustand["body"]


def test_erkannte_sprache_steht_im_log(einst, tmp_path, monkeypatch, caplog):
    """ANNAHME A1: das Ergebnis traegt ein Feld 'language'. Wenn ja, soll es
    im Log stehen -- dort sieht der Betrieb, was Whisper gehoert hat."""
    import logging

    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS")
    with caplog.at_level(logging.INFO, logger="interview_theater.stt"):
        stt.transkribiere(einst, _klient(_multipart_mitschnitt({})), datei, 30.0, sprache="auto")
    assert "italian" in caplog.text
```

- [ ] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt.py`
Expected: FAIL — `TypeError: transkribiere() got an unexpected keyword argument 'sprache'`
(drei Tests), `test_ohne_angabe_bleibt_es_bei_deutsch` **gruen** (haelt das
alte Verhalten fest).

- [ ] **Schritt 3: Umsetzen** (`interview_theater/stt.py`)

Kopf: `import logging` ergaenzen, nach den Importen
`log = logging.getLogger(__name__)` und

```python
#: Whisper erkennt die Sprache selbst (Karte A1, Birk E5): das Feld
#: ``language`` wird dann gar nicht gesendet.
AUTO = "auto"
```

`absenden`-Signatur und Multipart:

```python
def absenden(e, klient: httpx.Client, pfad: Path, budget_s: float,
             *, sprache: str | None = "de") -> str:
    """… (bisheriger Text) …

    ``sprache`` ist die Sprache der Aufnahme (ISO 639-1) oder ``AUTO``/None
    -- dann fehlt das Feld ``language``, und Whisper erkennt selbst. Der
    Aufrufer ermittelt sie (``aufnahme.whisper_sprache``); dieses Modul
    liest keine Datenbank."""
    …
    # Reihenfolge wie vor A1 (model, language, response_format), damit der
    # Upload fuer Deutsch byte-gleich bleibt.
    daten = {"model": "whisper"}
    if sprache and sprache != AUTO:
        daten["language"] = sprache
    daten["response_format"] = "verbose_json"
    …
                    data=daten,
```

`abholen`, vor dem `return` (Zeile 220):

```python
    ergebnis = daten or {}
    if ergebnis.get("language"):
        log.info("Whisper erkannte Sprache %s (Auftrag %s)", ergebnis["language"], batch_id)
    return str(ergebnis.get("text") or "").strip()
```

`transkribiere`: Signatur `…, budget_s: float, *, sprache: str | None = "de") -> str:`
und im Rumpf `batch_id = absenden(e, klient, pfad, rest, sprache=sprache)`.
Docstring um einen Satz zu `sprache` ergaenzen.

- [ ] **Schritt 4: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt.py tests/test_aufnahme.py`
Expected: alle gruen.

- [ ] **Schritt 5: Mutationsnachweis**

`if sprache and sprache != AUTO:` → `if sprache:` →
`test_auto_schickt_kein_language_feld` rot. Zuruecksetzen.

- [ ] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/stt.py tests/test_stt.py
git commit -m "Whisper: Sprache als Parameter, auto ohne language-Feld, erkannte Sprache ins Log (A1)"
```

---

## Aufgabe 7: Die wirksame Whisper-Sprache je Gruppe (`gruppe.stt_sprache`)

**Files:**
- Modify: `interview_theater/db.py:17–40` (Spalte `stt_sprache` in `gruppe`)
- Modify: `interview_theater/repo.py` (nach `setze_wortlaut_modus`, ~Z. 2956:
  `setze_stt_sprache`, `stt_sprache`)
- Modify: `interview_theater/aufnahme.py` (neue Funktion `whisper_sprache`,
  Aufruf in `_transkribiere_mit_meldung`, Zeile 510)
- Test: `tests/test_stt_sprache.py` (neu)

**Interfaces:**
- Consumes: `stt.transkribiere(..., sprache=)` (Aufgabe 6), `sprache.whisper_vorgabe()` (Aufgabe 3).
- Produces: `repo.setze_stt_sprache(conn, chat_id, wert: str | None) -> None`,
  `repo.stt_sprache(conn, chat_id) -> str | None`,
  `aufnahme.whisper_sprache(conn, chat_id) -> str` (Gruppenwert vor Profilwert).

- [ ] **Schritt 1: Tests schreiben** — `tests/test_stt_sprache.py`:

```python
"""Welche Sprache Whisper hoert: der Gruppenwert vor dem Profilwert (D2)."""

import pytest

from interview_theater import aufnahme, db, repo, stt, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_neue_spalte_ist_zuerst_leer(conn):
    assert repo.stt_sprache(conn, 1) is None


def test_setzen_und_zuruecknehmen(conn):
    repo.setze_stt_sprache(conn, 1, "it")
    assert repo.stt_sprache(conn, 1) == "it"
    repo.setze_stt_sprache(conn, 1, None)
    assert repo.stt_sprache(conn, 1) is None


def test_alte_datenbank_bekommt_die_spalte(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.execute("CREATE TABLE gruppe (chat_id INTEGER PRIMARY KEY, bot_name TEXT NOT NULL)")
    c.commit()
    db.initialisiere(c)
    spalten = {z[1] for z in c.execute("PRAGMA table_info(gruppe)")}
    assert "stt_sprache" in spalten


def test_ohne_gruppenwert_gilt_das_profil(conn, monkeypatch):
    assert aufnahme.whisper_sprache(conn, 1) == "de"
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert aufnahme.whisper_sprache(conn, 1) == "auto"


def test_gruppenwert_schlaegt_profil(conn, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_stt_sprache(conn, 1, "it")
    assert aufnahme.whisper_sprache(conn, 1) == "it"


def test_die_aufnahme_reicht_die_sprache_an_whisper(conn, einst, tmp_path, monkeypatch):
    gesehen = []

    def transkribiere(e, klient, pfad, budget, *, sprache="de"):
        gesehen.append(sprache)
        return "Ciao."

    monkeypatch.setattr(stt, "transkribiere", transkribiere)
    repo.setze_stt_sprache(conn, 1, "auto")

    class TG:
        def tippt(self, chat_id): pass
        def sende(self, chat_id, text): return 1

    zeile = {"id": 1, "chat_id": 1, "klasse": "kurz",
             "audio_pfad": str(tmp_path / "a.ogg")}
    assert aufnahme._transkribiere_mit_meldung(conn, TG(), einst, None, zeile) == "Ciao."
    assert gesehen == ["auto"]
```

- [ ] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt_sprache.py`
Expected: FAIL — `AttributeError: module 'interview_theater.repo' has no attribute 'stt_sprache'`.

- [ ] **Schritt 3: Umsetzen**

`db.py`, in `CREATE TABLE IF NOT EXISTS gruppe` nach `web_token TEXT`
(Komma an `web_token` nicht vergessen):

```sql
  web_token                       TEXT,
  -- Whisper-Sprache dieser Gruppe (Karte A1): NULL = Profilwert
  -- (sprache.whisper), sonst 'auto' oder ein ISO-639-1-Code. Additiv
  -- nachgeruestet ueber _migriere_fehlende_spalten.
  stt_sprache                     TEXT
```

`repo.py` nach `setze_wortlaut_modus`:

```python
@_gesperrt
def setze_stt_sprache(conn: sqlite3.Connection, chat_id: int, wert: str | None) -> None:
    """Die Whisper-Sprache dieser Gruppe (Karte A1, D2): 'auto', ein
    ISO-639-1-Code oder None (= wieder der Profilwert). Gesetzt ueber den
    Knopf in Phase 3 oder /sprache."""
    conn.execute("UPDATE gruppe SET stt_sprache = ? WHERE chat_id = ?", (wert, chat_id))
    conn.commit()


@_gesperrt
def stt_sprache(conn: sqlite3.Connection, chat_id: int) -> str | None:
    """Der Gruppenwert oder None -- None heisst: der Profilwert gilt."""
    g = hole_gruppe(conn, chat_id)
    if g is None or "stt_sprache" not in g.keys():
        return None
    return g["stt_sprache"] or None
```

`aufnahme.py`: `from interview_theater import sprache` in den Kopfimport
aufnehmen (neben `stt`), dann vor `_transkribiere_mit_meldung`:

```python
def whisper_sprache(conn, chat_id: int) -> str:
    """Welche Sprache Whisper fuer diese Gruppe hoeren soll (Karte A1, D2):
    der Gruppenwert (``gruppe.stt_sprache``, per Knopf oder /sprache
    gesetzt) vor dem Profilwert (``sprache.whisper``). ``"auto"`` heisst:
    Whisper erkennt selbst."""
    return repo.stt_sprache(conn, chat_id) or sprache.whisper_vorgabe()
```

und Zeile 510:

```python
        return stt.transkribiere(e, klient, pfad, budget,
                                 sprache=whisper_sprache(conn, chat_id))
```

- [ ] **Schritt 4: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt_sprache.py tests/test_aufnahme.py tests/test_db.py`
Expected: alle gruen.

- [ ] **Schritt 5: Mutationsnachweis**

`return repo.stt_sprache(conn, chat_id) or sprache.whisper_vorgabe()` →
`return sprache.whisper_vorgabe()` → `test_gruppenwert_schlaegt_profil` rot.

- [ ] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/db.py interview_theater/repo.py interview_theater/aufnahme.py tests/test_stt_sprache.py
git commit -m "Whisper-Sprache je Gruppe: gruppe.stt_sprache vor dem Profilwert (A1)"
```

---

## Aufgabe 8: Umstellen pro Gruppe — `/sprache` und drei Knoepfe in Phase 3 (D2)

Die ersten Texte, die **zweisprachig geboren** werden. `knoepfe/texte.py`
und `befehle.py` bekommen hier ihren Zugriff `T`; ihre **alten** Texte
bleiben bis Aufgabe 10/14 nackt (der Text-Waechter prueft Module erst, wenn
sie in `UMGESTELLT` stehen — Test 1–3 gelten aber schon fuer die neuen
`T.`-Zugriffe).

**Files:**
- Modify: `interview_theater/knoepfe/texte.py` (neue Konstanten, `T` am Ende)
- Modify: `interview_theater/knoepfe/interviews.py` (`biete_stt_sprache`)
- Modify: `interview_theater/knoepfe/stationen.py:152–160` (Phase-3-Zweig)
- Modify: `interview_theater/knoepfe/wirkung.py` (`_wirkung_stt_sprache`,
  Eintrag in `_WIRKUNGEN` ab Zeile 1291)
- Modify: `interview_theater/knoepfe/__init__.py` (Re-Export
  `ART_STT_SPRACHE`, `STT_KNOEPFE`, `T`, `biete_stt_sprache`,
  `_wirkung_stt_sprache`)
- Modify: `interview_theater/befehle.py` (`_BEKANNTE_BEFEHLE` Z. 757,
  `behandle` Z. 800–827, `_befehl_sprache`, neue Konstanten, `T`)
- Modify: `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_stt_sprache.py`

**Interfaces:**
- Consumes: `repo.setze_stt_sprache`, `aufnahme.whisper_sprache`,
  `sprache.whisper_vorgabe`, `sprache.AUTO`, `sprache.SPRACHNAMEN`.
- Produces: `knoepfe.ART_STT_SPRACHE = "stt_sprache"`,
  `knoepfe.STT_KNOEPFE = (("auto", "Auto"), ("en", "English"), ("it", "Italiano"))`,
  `knoepfe.biete_stt_sprache(conn, tg, chat_id) -> bool` (True, wenn Knoepfe
  rausgingen), Befehl `/sprache [auto|<xx>]` (versteckt, **nicht** in
  `BEFEHLE_LISTE`).

- [ ] **Schritt 1: Tests schreiben** (in `tests/test_stt_sprache.py` anhaengen):

```python
from interview_theater import befehle, knoepfe, sprache
from simulation.attrappe import TelegramAttrappe


def _padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()


def _druecke(conn, tg, einst, beschriftung):
    knopf = next(k for k in tg.offene_knoepfe() if k["beschriftung"] == beschriftung)
    knoepfe.behandle(conn, tg, None, einst, {
        "callback_query_id": "q", "data": knopf["daten"],
        "chat_id": 1, "message_id": knopf["message_id"]})


def test_phase_3_bietet_in_padua_die_drei_sprachknoepfe(conn, einst, monkeypatch):
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, knoepfe.PHASE_INTERVIEWS)
    beschriftungen = [k["beschriftung"] for k in tg.offene_knoepfe()]
    assert {"Auto", "English", "Italiano"} <= set(beschriftungen)


def test_dortmund_sieht_die_sprachknoepfe_nie(conn, einst):
    tg = TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 3)
    assert "Italiano" not in [k["beschriftung"] for k in tg.offene_knoepfe()]


def test_knopf_setzt_die_gruppensprache_und_wirkt_nur_einmal(conn, einst, monkeypatch):
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    knoepfe.biete_stt_sprache(conn, tg, 1)
    _druecke(conn, tg, einst, "Italiano")
    assert repo.stt_sprache(conn, 1) == "it"
    assert "Italiano" in tg.texte()[-1]
    # Zweiter Druck auf "English" derselben Leiste wirkt (andere Knopf-id),
    # ein zweiter Druck auf denselben Knopf nicht.
    knopf = next(k for k in tg.knoepfe[-1]["knoepfe"] if k[0] == "Italiano")
    vorher = len(tg.gesendet)
    knoepfe.behandle(conn, tg, None, einst, {
        "callback_query_id": "q2", "data": knopf[1], "chat_id": 1, "message_id": 1})
    assert len(tg.gesendet) == vorher


def test_befehl_sprache_zeigt_und_setzt(conn, einst):
    tg = TelegramAttrappe()
    assert befehle.behandle(conn, tg, einst, 1, "/sprache", None)
    assert "Deutsch" in tg.texte()[-1]
    befehle.behandle(conn, tg, einst, 1, "/sprache auto", None)
    assert repo.stt_sprache(conn, 1) == "auto"
    befehle.behandle(conn, tg, einst, 1, "/sprache klingonisch", None)
    assert repo.stt_sprache(conn, 1) == "auto"


def test_befehl_sprache_steht_nicht_im_menue():
    assert "sprache" not in {b["command"] for b in befehle.BEFEHLE_LISTE}


def test_englische_texte_des_sprachwegs(conn, einst, monkeypatch):
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/sprache", None)
    assert tg.texte()[-1] == "Interview language: automatic (I detect it myself)."
```

- [ ] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt_sprache.py`
Expected: FAIL — `AttributeError: module 'interview_theater.knoepfe' has no attribute 'biete_stt_sprache'`,
`/sprache` beantwortet mit „Diesen Befehl kenne ich nicht."

- [ ] **Schritt 3: Umsetzen**

`knoepfe/texte.py` — neben den anderen `ART_*` (nach `ART_SZENE_USA`, Z. 49):

```python
#: Die Interviewsprache fuer Whisper (Karte A1, D2) -- nur in Profilen mit
#: sprache.whisper = "auto" (Padua), beim Eintritt in Phase 3.
ART_STT_SPRACHE = "stt_sprache"
```

bei den Texten der Phase 3 (nach `_TEXT_USA_NEIN`, Z. 436):

```python
#: Die drei Knoepfe: fest benannt, Sprachnamen in ihrer eigenen Sprache --
#: nicht uebersetzt, wer Italienisch spricht, sucht "Italiano".
STT_KNOEPFE = (("auto", "Auto"), ("en", "English"), ("it", "Italiano"))
_TEXT_STT_SPRACHE_FRAGE = (
    "In welcher Sprache fuehrt ihr eure Interviews? Mit \"Auto\" hoere ich "
    "selbst heraus, welche es ist."
)
_TEXT_STT_SPRACHE_GESETZT = "Interviewsprache ab jetzt: {sprache}."
_TEXT_STT_SPRACHE_AUTO = "automatisch (ich erkenne sie selbst)"
_TEXT_STT_SPRACHE_KURZ = "Sprache gesetzt"
_JOURNAL_STT_SPRACHE = "Interviewsprache fuer Whisper: {sprache}"
```

und am Dateiende:

```python
from interview_theater import sprache  # noqa: E402  (unten: kein Zyklus beim Import)

T = sprache.Texte(__name__)
```

`knoepfe/interviews.py` — Import `from interview_theater import phasen, repo, sprache`,
aus `texte` zusaetzlich `ART_STT_SPRACHE, STT_KNOEPFE, T`, aus `basis`
zusaetzlich `_daten, _id_aus_daten, _sende_knoepfe` (sofern nicht schon
importiert). Neue Funktion:

```python
def biete_stt_sprache(conn, tg, chat_id: int) -> bool:
    """Drei Knoepfe fuer die Interviewsprache (Karte A1, D2): Auto, English,
    Italiano. Eine feste, benannte Auswahl -- genau der Fall, fuer den es
    Knoepfe gibt. Nur, wenn das Profil Whisper selbst erkennen laesst
    (``sprache.whisper = "auto"``); Dortmund sieht sie nie.

    Kein Modellaufruf (Zusage 2). Liefert True, wenn die Leiste rausging."""
    if sprache.whisper_vorgabe() != sprache.AUTO:
        return False
    leiste = [
        (beschriftung, _daten(repo.lege_knopf_an(conn, chat_id, ART_STT_SPRACHE, wert)))
        for wert, beschriftung in STT_KNOEPFE
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, T._TEXT_STT_SPRACHE_FRAGE, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return True
```

`knoepfe/stationen.py:152–160`, im Zweig `if nummer == PHASE_INTERVIEWS:`
nach `leitfaden.sende_einmal(conn, tg, chat_id, e=e)`:

```python
        # Die Interviewsprache (Karte A1): nur, wo das Profil sie offen
        # laesst. Nach dem Leitfaden, weil er die erste Frage ist, die sich
        # die Gruppe vor dem Losgehen stellt.
        biete_stt_sprache(conn, tg, chat_id)
```

mit `from interview_theater.knoepfe.interviews import biete_stt_sprache` im
Kopf (`interviews` importiert `stationen` nicht — kein Zyklus).

`knoepfe/wirkung.py` — Importe aus `texte` um `ART_STT_SPRACHE, STT_KNOEPFE, T`
ergaenzen, `from interview_theater import phasen, repo, sprache`, Handler vor
`_WIRKUNGEN`:

```python
def _wirkung_stt_sprache(conn, d: Druck) -> str:
    """Die Interviewsprache fuer Whisper (Karte A1, D2). Kein Modellaufruf:
    nur ein Feld in ``gruppe`` und eine Journalzeile."""
    wert = d.wert.strip().lower()
    if wert not in {w for w, _ in STT_KNOEPFE}:
        return _TEXT_UNBEKANNT
    repo.setze_stt_sprache(conn, d.chat_id, wert)
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_STT_SPRACHE.format(sprache=wert), quelle="knopf")
    anzeige = (T._TEXT_STT_SPRACHE_AUTO if wert == sprache.AUTO
               else sprache.SPRACHNAMEN.get(wert, wert))
    d.tg.sende(d.chat_id, T._TEXT_STT_SPRACHE_GESETZT.format(sprache=anzeige))
    return T._TEXT_STT_SPRACHE_KURZ
```

und in `_WIRKUNGEN`: `ART_STT_SPRACHE: _wirkung_stt_sprache,`.

`knoepfe/__init__.py`: in der `texte`-Importliste `ART_STT_SPRACHE,
STT_KNOEPFE, T, _JOURNAL_STT_SPRACHE, _TEXT_STT_SPRACHE_AUTO,
_TEXT_STT_SPRACHE_FRAGE, _TEXT_STT_SPRACHE_GESETZT, _TEXT_STT_SPRACHE_KURZ`;
in der `interviews`-Liste `biete_stt_sprache`; in der `wirkung`-Liste
`_wirkung_stt_sprache`.

`befehle.py` — `from interview_theater import (aufnahme, erkenner, knoepfe,
leitfaden, phasen, repo, sprache, szene)`; Konstanten bei den anderen
`_TEXT_*`:

```python
#: /sprache (Karte A1, D2) -- versteckt, wie /leitfaden: der Weg ist der
#: Knopf in Phase 3, der Befehl der Notausgang und die Anzeige.
_TEXT_SPRACHE_STAND = "Interviewsprache: {sprache}."
_TEXT_SPRACHE_GESETZT = "Interviewsprache ab jetzt: {sprache}."
_TEXT_SPRACHE_UNBEKANNT = (
    "Das kenne ich nicht. Moeglich sind auto oder ein Sprachkuerzel wie "
    "it, en, de."
)
_TEXT_SPRACHE_AUTO = "automatisch (ich erkenne sie selbst)"
_JOURNAL_SPRACHE = "Interviewsprache fuer Whisper: {sprache}"
_SPRACHWERT = re.compile(r"^(auto|[a-z]{2})$")
```

Funktion:

```python
def _befehl_sprache(conn, tg, chat_id: int, rest: str) -> None:
    """``/sprache`` zeigt, ``/sprache auto|it|en|…`` setzt die Whisper-Sprache
    dieser Gruppe (Karte A1). Kein Modellaufruf."""

    def anzeige(wert: str) -> str:
        return (T._TEXT_SPRACHE_AUTO if wert == sprache.AUTO
                else sprache.SPRACHNAMEN.get(wert, wert))

    wert = rest.strip().lower()
    if not wert:
        tg.sende(chat_id, T._TEXT_SPRACHE_STAND.format(
            sprache=anzeige(aufnahme.whisper_sprache(conn, chat_id))))
        return
    if not _SPRACHWERT.match(wert):
        tg.sende(chat_id, T._TEXT_SPRACHE_UNBEKANNT)
        return
    repo.setze_stt_sprache(conn, chat_id, wert)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          T._JOURNAL_SPRACHE.format(sprache=wert), quelle="befehl")
    tg.sende(chat_id, T._TEXT_SPRACHE_GESETZT.format(sprache=anzeige(wert)))
```

In `_BEKANNTE_BEFEHLE` unter `"/festlegung",`:

```python
    # Versteckt (Karte A1): die Whisper-Sprache dieser Gruppe zeigen oder
    # umstellen. Der Weg ist der Knopf in Phase 3.
    "/sprache",
```

In `behandle` vor `return True`:

```python
    elif befehl == "/sprache":
        _befehl_sprache(conn, tg, chat_id, rest)
```

Am Dateiende von `befehle.py`: `T = sprache.Texte(__name__)` (das Modul
importiert `sprache` schon im Kopf, der Zugriff steht trotzdem unten, bei den
anderen Modulen gleich).

`sprachen/en/texte.toml` anhaengen:

```toml
["knoepfe.texte"]
_TEXT_STT_SPRACHE_FRAGE = "Which language are your interviews in? With \"Auto\" I work it out myself."
_TEXT_STT_SPRACHE_GESETZT = "Interview language from now on: {sprache}."
_TEXT_STT_SPRACHE_AUTO = "automatic (I detect it myself)"
_TEXT_STT_SPRACHE_KURZ = "Language set"
_JOURNAL_STT_SPRACHE = "Interview language for Whisper: {sprache}"

["befehle"]
_TEXT_SPRACHE_STAND = "Interview language: {sprache}."
_TEXT_SPRACHE_GESETZT = "Interview language from now on: {sprache}."
_TEXT_SPRACHE_UNBEKANNT = "I don't know that one. Use auto or a language code like it, en, de."
_TEXT_SPRACHE_AUTO = "automatic (I detect it myself)"
_JOURNAL_SPRACHE = "Interview language for Whisper: {sprache}"
```

(`["knoepfe.texte"]` wird in Aufgabe 10 um alle weiteren Eintraege
ergaenzt — **eine** Tabelle je Modul, nicht zwei gleichnamige: TOML weist
eine doppelte Tabelle ab.)

- [ ] **Schritt 4: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_stt_sprache.py tests/test_knoepfe_struktur.py tests/test_befehle.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py`
Expected: alle gruen; `test_jede_knopfart_hat_genau_einen_handler` kennt
`ART_STT_SPRACHE`. `$PY -m scripts.pruefe_sprache --schluessel knoepfe.texte,befehle` → `0 Treffer`.

- [ ] **Schritt 5: Mutationsnachweis**

In `biete_stt_sprache` die Profilabfrage entfernen →
`test_dortmund_sieht_die_sprachknoepfe_nie` rot. `_WIRKUNGEN`-Eintrag
streichen → `test_jede_knopfart_hat_genau_einen_handler` rot.

- [ ] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/knoepfe interview_theater/befehle.py \
        interview_theater/sprachen/en/texte.toml tests/test_stt_sprache.py
git commit -m "Interviewsprache umstellbar: /sprache und drei Knoepfe beim Eintritt in Phase 3 (A1)"
```

**Uebergabe an Karte A2:** das Web-Feld fuer `gruppe.stt_sprache` baut A2
(Web-Chat als Arbeitsplatz), ueber `repo.setze_stt_sprache` — kein zweiter
Schreibweg. In `web_schreiben.FELDER` steht es in A1 **nicht**.

---

## Aufgabe 9 (manuell, kostenpflichtig): Whisper-Rauchtest fuer `auto`, `it`, `en` (ANNAHME A1/A2)

**Kein Test, laeuft nie automatisch, kostet Rappen.** Voraussetzung: A3 —
Birk hat zwei Aufnahmen bereitgelegt, z. B. `/tmp/a1-en.ogg` (Englisch) und
`/tmp/a1-it.ogg` (Italienisch). Liegen sie nicht vor, Aufgabe als
**offen** markieren und weiter mit Aufgabe 10; die Umsetzung haengt nicht
davon ab, nur die Annahme bleibt unbestaetigt.

**Files:**
- Modify: `scripts/rauchtest.py` (`teste_whisper` bekommt `sprache`,
  `main` liest `--whisper <wert>`; Vorgabe `de` = heutiges Verhalten)

- [ ] **Schritt 1:** `scripts/rauchtest.py` — `teste_whisper(einst, klient,
  audio_pfad, sprache="de")` ruft `stt.transkribiere(…, 90.0, sprache=sprache)`
  und druckt zusaetzlich `print(f"Whisper-Sprache: {sprache}")`. In `main`:
  `--whisper <wert>` aus `sys.argv` herausnehmen (wie `--voll` in
  `prompt_schnappschuss.main`), Rest wie bisher. Kein Test noetig
  (Skript), aber `$PY -m scripts.rauchtest --help` darf nicht abstuerzen —
  ohne Env bricht `einstellungen.laden()` mit seiner eigenen Meldung ab, das
  ist in Ordnung.
- [ ] **Schritt 2: Laufen lassen** — Env laden, **nie ausgeben**, und
  `IT_DB` auf eine Wegwerf-Datei umbiegen (W9):

```bash
set -a; . ../../betrieb/gruppe1.env; set +a
export IT_DB=/tmp/a1-rauch.db
$PY -m scripts.rauchtest /tmp/a1-it.ogg --whisper auto 2>&1 | tee /tmp/a1-rauch-it-auto.txt
$PY -m scripts.rauchtest /tmp/a1-it.ogg --whisper it   2>&1 | tee /tmp/a1-rauch-it-it.txt
$PY -m scripts.rauchtest /tmp/a1-en.ogg --whisper auto 2>&1 | tee /tmp/a1-rauch-en-auto.txt
grep -h "Whisper erkannte\|Transkript\|Dauer" /tmp/a1-rauch-*.txt
```

(Der Pfad `../../betrieb/gruppe1.env` gilt aus dem Worktree
`.worktrees/t_…` heraus; vorher mit `ls ../../betrieb/gruppe1.env` pruefen,
nicht mit `cat`.)

- [ ] **Schritt 3: Befund notieren** — in `docs/sprache-a1-korpuslauf-<datum>.md`
  (legt Aufgabe 31 an; hier vorab erzeugen, falls noetig) einen Abschnitt
  „Whisper-Rauchtest" mit: Transkript in der Originalsprache ja/nein (ohne
  den Transkripttext zu zitieren — eigene Stimme ist kein Echtdatum, trotzdem
  nur „italienisch, 23 Woerter, korrekt"), Dauer je Lauf, ob `Whisper erkannte
  Sprache …` im Log stand (A1: Feld `language` vorhanden?), ob ohne
  `language` ein HTTP-Fehler kam (A2).
- [ ] **Schritt 4: Wenn A1 faellt** (italienische Aufnahme mit `auto` wird
  englisch oder deutsch transkribiert): Befund stehen lassen, **Padua-Vorgabe
  in Aufgabe 29 auf `whisper = "it"` setzen** statt `auto`, und im
  LIESMICH festhalten, dass eine englischsprachige Interviewrunde per Knopf
  „English" umstellt. Birk informieren. Faellt nur das Log-Feld (A1 zweiter
  Teil), ist das kein Befund fuer den Betrieb.
- [ ] **Schritt 5: Commit** (nur das Skript; Aufnahmen und Ausgaben bleiben in
  `/tmp`):

```bash
git add scripts/rauchtest.py
git commit -m "Rauchtest: Whisper-Sprache waehlbar (auto/it/en) fuer die A1-Pruefung"
```

---

## Aufgabe 10: `knoepfe/texte.py` — die Knopftabelle auf Englisch (D3)

Die groesste einzelne Tabelle (180 Kandidaten). Hier werden **nur** die
bestehenden Konstanten von `texte.py` registriert und uebersetzt;
die Submodule stellen ihre Verwendungen in 11–13 um.

**Files:**
- Modify: `interview_theater/knoepfe/texte.py` (nimmt `_ERLEDIGT_FUER` auf)
- Modify: `interview_theater/knoepfe/stationen.py:35–42` (`_ERLEDIGT_FUER`
  entfernen, aus `texte` importieren)
- Modify: `interview_theater/knoepfe/__init__.py:224–228` (`_ERLEDIGT_FUER`
  aus `texte` statt aus `stationen` re-exportieren)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["knoepfe.texte"]`)
- Modify: `scripts/prompt_schnappschuss.py:137–141`,
  `scripts/pruefe_profil.py:106–112` (ANWEISUNG_* ueber `knoepfe.T`)
- Modify: `tests/test_sprache_bitgleich.py` (`VERSCHOBEN`),
  `tests/test_sprache_texte.py` (`UMGESTELLT += {"knoepfe.texte"}`)
- Test: `tests/test_knoepfe_sprache.py` (neu)

**Schluessel dieser Aufgabe** (gemessen mit `$PY /tmp/a1_inv/schluessel.py`,
Abschnitt `## knoepfe.texte (180)`, plus `_ERLEDIGT_FUER`): alle 180 dort
gelisteten Namen — von `_TEXT_EIGENE_KNOPF` bis `ANWEISUNG_EROEFFNUNG`,
darunter `ANWEISUNGEN` (dict, Phasen 1–7 → Auftragstext) und
`_ANWEISUNG_ALLGEMEIN` — und die in Aufgabe 8 schon angelegten sieben.
Nicht dabei: `ART_*`, `PHASE_*`, `PRAEFIX`, `TRENNER`, `_HAKEN`,
Zahlenkonstanten, `STT_KNOEPFE`. Findet der Waechter
(`test_keine_unuebersetzte_konstante[knoepfe.texte]`) weitere deutsche
Konstanten, gehoeren sie ebenfalls in diese Aufgabe (oder, wenn sie reine
Protokoll-Werte sind, nach `PARSER`/`BLEIBT_DEUTSCH` mit Grund).

**Uebersetzungsbeispiele (verbindlich im Ton, K6/K7):**

| Konstante | Deutsch | Englisch |
|---|---|---|
| `_TEXT_SPEICHERN_KNOPF` | `Ja, speichern` | `Yes, save` |
| `_TEXT_ANDERS_KNOPF` | `Nein, nochmal aendern` | `No, change it again` |
| `_TEXT_SCHON_BENUTZT` | `Das habe ich schon uebernommen.` | `I've already taken that on.` |
| `_TEXT_AUFNAHME_STARTEN` | `Interview starten` | `Start interview` |
| `_TEXT_AUFNAHME_BEENDEN` | `Interview beenden` | `End interview` |
| `_TEXT_TEIL_WEITER_KNOPF` | `Interview geht weiter` | `Interview continues` |
| `_TEXT_TEIL_FERTIG_KNOPF` | `Interview ist fertig` | `Interview is finished` |
| `_TEXT_PHASE_WEITER` | `Weiter zu {phase}?` | `On to {phase}?` |
| `_TEXT_PHASE_ANGEBOT` | `{erledigt} steht. Weiter zu {phase}?` | `{erledigt} are in place. On to {phase}?` |
| `_TEXT_PHASE_NOCH_NICHT_KNOPF` | `Noch etwas aendern` | `Change something first` |
| `_TEXT_PROAKTIV` | `Bevor ich vorschlage: habt ihr selbst schon Ideen?` | `Before I suggest anything: do you have ideas of your own?` |
| `TEXT_KUERZEN_KNOPF` | `Kuerzer ({prozent} %)` | `Shorter ({prozent} %)` |
| `_TEXT_USA_FRAGE_KNOEPFE` | `Tippt an, was gelten soll:` | `Tap what should apply:` |
| `_TEXT_USA_JA_KNOPF` / `_NEIN_KNOPF` | `Ja, US-Modell` / `Nein, Schweiz` | `Yes, US model` / `No, Switzerland` |
| `_ERLEDIGT_FUER` | `{2: "Eure Begriffe", …, 7: "Alle Szenentexte"}` | `{"2" = "Your terms", "3" = "Your questions", "4" = "The interviews are analysed and", "5" = "Setting, characters and story", "6" = "Story and scene sequence", "7" = "All scene texts"}` |

`ANWEISUNG_*`/`ANWEISUNGEN` sind **Auftragsvorlagen an das Modell** (Prompt):
dieselben Protokoll-Token (`'VORSCHLAG BEGRIFFE:'`, `'Abschluss:'` wird zu
`'Closing:'` **nur**, wenn Aufgabe 23 den Parser dafuer zweisprachig macht —
bis dahin bleibt `'Abschluss:'` woertlich im englischen Auftrag, siehe
Aufgabe 23, Zeile `knoepfe/fragen.py:317/322`), dieselben Profil-Platzhalter
(`{{projekt_kurz}}`), und die E8-Regel wird **nicht** hier, sondern im
Systemprompt verankert.

- [ ] **Schritt 1: Test schreiben** — `tests/test_knoepfe_sprache.py`:

```python
"""Die Knopftabelle: Deutsch unveraendert ueber knoepfe.X und knoepfe.T.X,
Englisch ueber knoepfe.T.X (D3)."""

import pytest

from interview_theater import knoepfe, sprache, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_reexport_bleibt_deutsch():
    assert knoepfe._TEXT_SCHON_BENUTZT == "Das habe ich schon uebernommen."
    assert knoepfe.T._TEXT_SCHON_BENUTZT is knoepfe._TEXT_SCHON_BENUTZT
    assert knoepfe._ERLEDIGT_FUER[2] == "Eure Begriffe"


def test_padua_liest_englisch(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert knoepfe.T._TEXT_SPEICHERN_KNOPF == "Yes, save"
    assert knoepfe.T._ERLEDIGT_FUER[2] == "Your terms"
    assert knoepfe.T.ANWEISUNGEN.keys() == knoepfe.ANWEISUNGEN.keys()
    assert "{{projekt_kurz}}" in knoepfe.T.ANWEISUNG_EROEFFNUNG
    assert "VORSCHLAG EROEFFNUNG:" in knoepfe.T.ANWEISUNG_EROEFFNUNG
```

- [ ] **Schritt 2: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_knoepfe_sprache.py`
Expected: FAIL — `assert 'Ja, speichern' == 'Yes, save'` (Eintrag fehlt, es
bleibt Deutsch).

- [ ] **Schritt 3: Umsetzen**

1. `_ERLEDIGT_FUER` samt Kommentar aus `stationen.py:32–42` **wortgleich**
   nach `texte.py` (Abschnitt Phasenrahmen, nahe `_TEXT_PHASE_ANGEBOT`)
   verschieben; `stationen.py` importiert es aus `texte`.
   `tests/test_sprache_bitgleich.py`:
   `VERSCHOBEN = {"knoepfe.stationen._ERLEDIGT_FUER": "knoepfe.texte._ERLEDIGT_FUER"}`.
2. `["knoepfe.texte"]` in `texte.toml` um alle Schluessel dieser Aufgabe
   ergaenzen (in Definitionsreihenfolge, K2).
3. `scripts/prompt_schnappschuss.py:137–141`:

```python
    for feld in sorted(f for f in dir(knoepfe) if f.startswith("ANWEISUNG_")):
        wert = getattr(knoepfe, feld)
        if isinstance(wert, str):
            # Ueber den Sprachzugriff (Karte A1): im Deutschen dasselbe
            # Objekt, unter einem englischen Profil der englische Auftrag.
            stuecke.append((f"knoepfe.{feld}", anweisungen.fuelle(getattr(knoepfe.T, feld))))
```

   `scripts/pruefe_profil.py:106–112` entsprechend: `wert = getattr(modul.T, feld)`
   fuer `knoepfe` (fuer `szenenfolge` erst in Aufgabe 16 — bis dahin
   `getattr(getattr(modul, "T", modul), feld)`).
4. `UMGESTELLT` in `tests/test_sprache_texte.py` um `"knoepfe.texte"` ergaenzen.

- [ ] **Schritt 4: Gruen sehen und Uebersetzung nachweisen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_knoepfe_sprache.py tests/test_sprache_texte.py \
    tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py tests/test_knoepfe_struktur.py
$PY -m scripts.pruefe_sprache --schluessel knoepfe.texte
```
Expected: alle gruen; `0 Treffer`.

- [ ] **Schritt 5: Mutationsnachweis**

Einen englischen Eintrag mit `{phase}` (`_TEXT_PHASE_WEITER`) auf `"On to it?"`
aendern → `test_platzhalter_und_form_gleich[knoepfe.texte-_TEXT_PHASE_WEITER]`
rot. In einem englischen Eintrag ein deutsches Wort lassen (`"Yes, speichern"`)
→ `pruefe_sprache --schluessel knoepfe.texte` Exit 1. Zuruecksetzen.

- [ ] **Schritt 6: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/knoepfe interview_theater/sprachen/en/texte.toml \
        scripts/prompt_schnappschuss.py scripts/pruefe_profil.py \
        tests/test_knoepfe_sprache.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py
git commit -m "Knopftabelle auf Englisch: knoepfe/texte.py ueber T, _ERLEDIGT_FUER nach texte (A1)"
```

---

## Aufgabe 11: `knoepfe/basis.py`, `fragen.py`, `interviews.py`, `stationen.py` ueber `T`

**Files:**
- Modify: `interview_theater/knoepfe/basis.py`, `fragen.py`, `interviews.py`,
  `stationen.py` (Verwendungen; Importlisten verlieren die nur noch ueber `T`
  gelesenen Namen)
- Modify: `interview_theater/knoepfe/texte.py` (neue Konstanten aus
  Inline-Literalen), `texte.toml`
- Modify: `tests/test_sprache_texte.py` (`UMGESTELLT`, `INLINE_ERLAUBT`)

**Stellen (gemessen):** Lese-Verwendungen: `basis.py` 16, `fragen.py` 12,
`interviews.py` 24, `stationen.py` 7 (`$PY /tmp/a1_inv/verwendungen.py`).
Inline-Literale (`$PY /tmp/a1_inv/inline.py --liste | grep knoepfe/`):

| Stelle | Literal | wird |
|---|---|---|
| `knoepfe/basis.py:113` und `:131` | `f"Weiter zu {…}"` (Knopf) | `texte._TEXT_WEITER_ZU_KNOPF = "Weiter zu {phase}"`, en `"On to {phase}"` |
| `knoepfe/stationen.py:73` | `f"Weiter zu {phasen.knopfbezeichnung(stufe)}"` | dieselbe Konstante |
| `knoepfe/basis.py:699` | `"'{}' steht bereits und wurde durch einen Speicher-Knopf nicht ersetzt"` | Vorfall-Detail → `INLINE_ERLAUBT[("knoepfe.basis", "'{}' steht bereits und wurde durch einen ")]` |
| `knoepfe/fragen.py:336` | `"Eroeffnung und Abschluss festgelegt"` (Journal) | `texte._JOURNAL_EROEFFNUNG_FESTGELEGT`, en `"Opening and closing agreed"` |
| `knoepfe/stationen.py:95` | `_ERLEDIGT_FUER.get(stufe, "Alles Noetige")` | `texte._TEXT_ALLES_NOETIGE = "Alles Noetige"`, en `"Everything needed"` (Default-Argument **im Aufruf**, nicht in der Signatur: `T._ERLEDIGT_FUER.get(stufe, T._TEXT_ALLES_NOETIGE)`) |

Einwort-Literale an `tg.sende`/`_sende_knoepfe`/`beantworte_knopf`, die die
Heuristik nicht fasst, findet
`grep -nE "(sende|_sende_knoepfe|_sende_menue|beantworte)\([^)]*\"[A-Z]" interview_theater/knoepfe/{basis,fragen,interviews,stationen}.py`
— jedes deutsche davon wird ebenfalls eine Konstante.

- [ ] **Schritt 1: `UMGESTELLT` ergaenzen, rot sehen**

`UMGESTELLT |= {"knoepfe.basis", "knoepfe.fragen", "knoepfe.interviews", "knoepfe.stationen"}`

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py`
Expected: FAIL in `test_keine_nackte_verwendung[knoepfe.basis]` usw. mit der
Liste der Zeilen, und `test_keine_deutschen_inline_texte[...]` mit den
Literalen oben. **Diese Ausgabe ist die Arbeitsliste.**

- [ ] **Schritt 2: Umstellen** nach den fuenf Schritten am Ende von
  Aufgabe 5. Beispiel `stationen.py:94–97` vorher/nachher:

```python
# vorher
    frage = _TEXT_PHASE_WEITER.format(phase=phasen.knopfbezeichnung(stufe))
    if jetzige >= stufe:
        return _TEXT_PHASE_ANGEBOT.format(
            erledigt=_ERLEDIGT_FUER.get(stufe, "Alles Noetige"),
            phase=phasen.knopfbezeichnung(stufe),
        )
# nachher
    frage = T._TEXT_PHASE_WEITER.format(phase=phasen.knopfbezeichnung(stufe))
    if jetzige >= stufe:
        return T._TEXT_PHASE_ANGEBOT.format(
            erledigt=T._ERLEDIGT_FUER.get(stufe, T._TEXT_ALLES_NOETIGE),
            phase=phasen.knopfbezeichnung(stufe),
        )
```

  und die Importliste `from interview_theater.knoepfe.texte import (ART_NOCH_NICHT,
  ART_PHASE, PHASE_INTERVIEWS, …, T)` ohne die `_TEXT_*`-Namen.

- [ ] **Schritt 3: Gruen sehen und nachweisen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py tests/test_sprache_bitgleich.py \
    tests/test_knoepfe.py tests/test_knoepfe_struktur.py tests/test_stt_sprache.py
$PY -m scripts.pruefe_sprache --schluessel knoepfe.texte
```
Expected: alle gruen, `0 Treffer`. `test_texte_*_wie_vor_a1` gruen heisst:
kein deutscher Wert hat sich geaendert.

- [ ] **Schritt 4: Mutationsnachweis** — in `stationen.py` eine Stelle
  zurueck auf `_TEXT_PHASE_WEITER` (und den Namen wieder importieren) →
  `test_keine_nackte_verwendung[knoepfe.stationen]` rot.

- [ ] **Schritt 5: SUITE, Commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/knoepfe interview_theater/sprachen/en/texte.toml tests/test_sprache_texte.py
git commit -m "Knoepfe Phase 2/3 und Phasenrahmen ueber T (A1)"
```

---

## Aufgabe 12: `knoepfe/figuren.py` und `knoepfe/szenen.py` ueber `T`

Wie Aufgabe 11. **Stellen:** `figuren.py` 29, `szenen.py` 79
Lese-Verwendungen. Inline:

| Stelle | Literal | wird |
|---|---|---|
| `knoepfe/figuren.py:118–125` | Zahlwoerter `eine … zwoelf` in `_zahl_aus` | **Parser**, nicht hier — Aufgabe 22 |
| `knoepfe/szenen.py:1034` | `"Eine Formwahl sollte als Geschichte gespeichert werden"` | Vorfall-Detail → `INLINE_ERLAUBT` |
| `knoepfe/szenen.py:1039` | `"Formwahl uebernommen, Geschichte fehlt noch"` | ist es Journal → `_JOURNAL_FORMWAHL`, ist es Vorfall → `INLINE_ERLAUBT` (am Aufruf ablesen) |
| `knoepfe/szenen.py:1180` | `"Geschichte mit {} Szenen uebernommen"` (Journal) | `_JOURNAL_GESCHICHTE_MIT_SZENEN = "Geschichte mit {anzahl} Szenen uebernommen"`, en `"Story taken on with {anzahl} scenes"` |
| `knoepfe/szenen.py:1256` | `"Ich schlage die fehlenden Angaben vor"` | `_TEXT_SCHLAGE_ANGABEN_VOR`, en `"I'll suggest the missing details"` |

Zusaetzlich: `probenansicht_zeile` (szenen.py) und `biete_szene_usa`
(szenen.py:165–185) lesen `_TEXT_USA_*` — ueber `T`. `stationen.py:194`
(`szene_modul._TEXT_ANGEBOT_USA`) bleibt bis Aufgabe 16 nackt (Modul
`szene` noch nicht umgestellt; `stationen` ist dann schon in `UMGESTELLT`
— der Waechter meldet die Stelle erst, wenn `szene._TEXT_ANGEBOT_USA` in
der Tabelle steht; Aufgabe 16 stellt sie um).

- [ ] **Schritt 1:** `UMGESTELLT |= {"knoepfe.figuren", "knoepfe.szenen"}`,
  `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py` → rot mit Arbeitsliste.
- [ ] **Schritt 2:** umstellen (fuenf Schritte, Aufgabe 5).
- [ ] **Schritt 3:** gruen:
  `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_knoepfe*.py tests/test_geschichte.py tests/test_kuerzung.py`,
  `$PY -m scripts.pruefe_sprache --schluessel knoepfe.texte` → `0 Treffer`.
- [ ] **Schritt 4: Mutationsnachweis:** eine `T.`-Stelle in `szenen.py`
  zuruecknehmen → `test_keine_nackte_verwendung[knoepfe.szenen]` rot.
- [ ] **Schritt 5:** SUITE; Commit
  `"Knoepfe Figuren und Szenen ueber T (A1)"`.

---

## Aufgabe 13: `knoepfe/wirkung.py` ueber `T` — auch die Knopf-Antworten

117 Lese-Verwendungen, 21 Inline-Literale, **70 literale `return`-Werte**
(`grep -cE 'return f?"' interview_theater/knoepfe/wirkung.py` → 70): das ist
der Text, den `answerCallbackQuery` als kurze Einblendung zeigt
(`knoepfe.behandle` → `_beantworte`, wirkung.py:1440–1441). Die Heuristik
fasst davon nur die mit Funktionswort (`"Wir hoeren zu"`), nicht
`"Passt"`, `"Bleibt"`, `"Textbuch"`, `"Erzaehlt"`.

**Files:**
- Modify: `interview_theater/knoepfe/wirkung.py`, `knoepfe/texte.py`, `texte.toml`
- Test: `tests/test_knoepfe_sprache.py`, `tests/test_sprache_texte.py`

- [ ] **Schritt 1: Test schreiben** (in `tests/test_knoepfe_sprache.py`):

```python
import ast
import inspect


def test_kein_handler_gibt_ein_textliteral_zurueck():
    """Die Einblendung nach einem Druck ist Nutzertext (Karte A1): sie kommt
    aus der Tabelle, nie als Literal aus dem Handler."""
    from interview_theater.knoepfe import wirkung

    baum = ast.parse(inspect.getsource(wirkung))
    literal = []
    for funktion in ast.walk(baum):
        if isinstance(funktion, ast.FunctionDef) and funktion.name.startswith("_wirkung_"):
            for k in ast.walk(funktion):
                if isinstance(k, ast.Return) and isinstance(k.value, (ast.Constant, ast.JoinedStr)):
                    if not (isinstance(k.value, ast.Constant) and not isinstance(k.value.value, str)):
                        literal.append(f"{funktion.name}:{k.lineno}")
    assert literal == []
```

- [ ] **Schritt 2: Rot sehen** — `$PY -m pytest -q -p no:cacheprovider tests/test_knoepfe_sprache.py::test_kein_handler_gibt_ein_textliteral_zurueck`
  → FAIL mit 70 Eintraegen (`_wirkung_geschichte_schreiben:135`, …).
- [ ] **Schritt 3: Umsetzen.** Je **verschiedenem** Literal eine Konstante in
  `texte.py`, Praefix `_ANTWORT_` (die Knopfantwort ist eine eigene
  Textsorte: ein bis vier Woerter), mit Platzhaltern statt f-String:

```python
#: Was nach einem Druck kurz eingeblendet wird (answerCallbackQuery,
#: Karte A1 aus Literalen gebildet). Ein bis vier Woerter.
_ANTWORT_LAEUFT_SCHON = "Laeuft schon"
_ANTWORT_GESCHICHTE_LAEUFT = "Geschichte laeuft"
_ANTWORT_PASST = "Passt"
_ANTWORT_WAS_ANDERS = "Was soll anders sein?"
_ANTWORT_SZENE_GESCHAERFT = "Szene {nummer} geschaerft"
_ANTWORT_UEBERNOMMEN = "Uebernommen: {was}"
…
```

  en z. B.: `_ANTWORT_LAEUFT_SCHON = "Already running"`,
  `_ANTWORT_GESCHICHTE_LAEUFT = "Story is on its way"`,
  `_ANTWORT_PASST = "Good"`, `_ANTWORT_WAS_ANDERS = "What should change?"`,
  `_ANTWORT_SZENE_GESCHAERFT = "Scene {nummer} sharpened"`,
  `_ANTWORT_UEBERNOMMEN = "Taken on: {was}"`. Im Handler:
  `return T._ANTWORT_SZENE_GESCHAERFT.format(nummer=ziel["nummer"])`.
  **Achtung** `wirkung.py:1255`: die Journalzeile
  `"US-Modell fuer Szenentexte: ja" if ja else "… nein"` wird
  `T._JOURNAL_USA_JA` / `T._JOURNAL_USA_NEIN` — **die Logik
  `ja = str(d.knopf["wert"]).strip().lower() == "ja"` (Zeile 1251) bleibt
  unveraendert** (interner Wert, kein Text; AGENTS.md-Fallstrick `bool`).
- [ ] **Schritt 4:** `UMGESTELLT |= {"knoepfe.wirkung"}`; restliche
  Verwendungen umstellen (fuenf Schritte). Gruen:
  `$PY -m pytest -q -p no:cacheprovider tests/test_knoepfe*.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_interview_ohne_knopf.py tests/test_kuerzung.py`;
  `$PY -m scripts.pruefe_sprache --schluessel knoepfe.texte` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** in `_wirkung_geschichte_passt` wieder
  `return "Passt"` → `test_kein_handler_gibt_ein_textliteral_zurueck` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Knopf-Wirkungen und ihre Einblendungen ueber T (A1)"`.

---

## Aufgabe 14: Das Geruest des Chats — `befehle`, `bot`, `leitfaden`, `phasentexte`, `fehlstellen`, `phasen`

Was die Gruppe am ersten Tag liest: Begruessung, `/hilfe`, `/stand`,
Phasen-Kopfzeilen, Checklisten, Leitfaden, Fehlstellen.

**Schluessel** (`$PY /tmp/a1_inv/schluessel.py`): `befehle` 22 (ohne
`_ENTFERNEN_WOERTER` = Parser, Aufgabe 22) → 21, darunter `_TEXT_HILFE` und
`BEFEHLE_LISTE` (Beschreibungen englisch, `command` woertlich),
`_BEISPIEL_ARBEITSSTAND`; `bot` 5; `leitfaden` 7; `phasentexte` 5
(`_KOPF_EINTRITT`, `_ZEILE_CHECKLISTE`, `ZEILE_ANGEBOT`, `_KOPF_ABSCHLUSS`,
`PARAMETER` — letzteres ueber K4); `fehlstellen` 1 (`UEBERSCHRIFT`) plus 19
Inline-Saetze (fehlstellen.py:106–251, jeder eine Konstante `_SATZ_…`).

**Files:**
- Modify: `interview_theater/befehle.py`, `bot.py`, `leitfaden.py`,
  `phasentexte.py`, `fehlstellen.py`, `phasen.py`, `texte.toml`
- Modify: `bot.py` Setzen der Befehlsliste (`setze_befehle(BEFEHLE_LISTE)`)
  → `T.BEFEHLE_LISTE` ueber `befehle.T`
- Modify: `scripts/prompt_schnappschuss.py:131–133` (Leitfaden-Felder ueber
  `leitfaden.T`)
- Test: `tests/test_chat_sprache.py` (neu), `tests/test_sprache_texte.py`

**Sonderfaelle:**
- `phasentexte.PARAMETER` enthaelt Lambdas (K4): neue Konstante
  `PARAMETER_BESCHRIFTUNG = {"Begriffe": "Begriffe", "noch keine":
  "noch keine", "Fragen": "Fragen", "Einleitungen": "Einleitungen",
  "noch nicht geprueft": "noch nicht geprueft", "Eroeffnung": "Eroeffnung",
  "noch offen": "noch offen", "Abschluss": "Abschluss", "Interviews":
  "Interviews", "Auswertungen": "Auswertungen", "Setting": "Setting",
  "Figuren": "Figuren", "Geschichte": "Geschichte", "Szenenfolge":
  "Szenenfolge", "Zuordnungen": "Zuordnungen", "Szenentexte": "Szenentexte",
  "Stueckpruefung": "Stueckpruefung"}` (vollstaendig aus `PARAMETER`
  ablesen), Verwendung in `parameterzeilen`/`checkliste`/`standzeilen`:
  `T.PARAMETER_BESCHRIFTUNG.get(wort, wort)`. Dazu die drei
  Inline-Literale `phasentexte.py:213` (`"geprueft, keine noetig"`), `:257`,
  `:309` als Konstanten.
- `phasen.py`: Journalzeilen und Meldungen pruefen (der Waechter zeigt,
  ob es deutsche Literale gibt; die Phasen-**Namen** und `MELDUNG` kommen
  aus dem Profil — Padua bekommt englische in Aufgabe 29).
- `befehle.py` Inline (befehle.py:199, 298, 312, 338, 344, 352, 358, 390,
  425, 527, 716, 718, 742): jede eine Konstante. `:716`/`:718` sind
  wortgleich mit `szene._TEXT_USA_JA/_NEIN` — **auf diese verweisen**
  (`szene.T._TEXT_USA_JA`) statt eine dritte Kopie anzulegen.
- `/hilfe` nennt Befehle (das darf es, K6); die Befehlsnamen bleiben
  (Annahme A4), die Erklaerung wird englisch.

- [ ] **Schritt 1: Test schreiben** — `tests/test_chat_sprache.py`:

```python
"""Begruessung, Hilfe, Stand und Phasenrahmen auf Englisch (Karte A1)."""

import pytest

from interview_theater import befehle, bot, leitfaden, phasentexte, sprache, workshop
from simulation.attrappe import TelegramAttrappe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_hilfe_auf_englisch(conn, einst, padua):
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/hilfe", None)
    assert tg.texte()[-1].startswith("Just write or speak")


def test_menue_behaelt_die_befehlsnamen(padua):
    deutsch = [b["command"] for b in befehle.BEFEHLE_LISTE]
    assert [b["command"] for b in befehle.T.BEFEHLE_LISTE] == deutsch


def test_eintrittskopf_auf_englisch(conn, padua):
    assert phasentexte.T._ZEILE_CHECKLISTE.startswith("What it takes:")
    assert "noch" not in " ".join(phasentexte.checkliste(conn, 1, 2).split())


def test_leitfaden_leer_auf_englisch(conn, padua):
    assert leitfaden.T.TEXT_LEER.startswith("I don't have an interview guide yet")


def test_dortmund_unveraendert(conn, einst):
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/hilfe", None)
    assert tg.texte()[-1] == befehle._TEXT_HILFE
```

- [ ] **Schritt 2:** rot: `$PY -m pytest -q -p no:cacheprovider tests/test_chat_sprache.py`
  → `AssertionError` (Deutsch statt Englisch). `UMGESTELLT |= {"befehle",
  "bot", "leitfaden", "phasentexte", "fehlstellen", "phasen"}` →
  `tests/test_sprache_texte.py` rot mit der Arbeitsliste.
- [ ] **Schritt 3:** umstellen (fuenf Schritte). Englische Kernsaetze:
  `_TEXT_HILFE` beginnt `"Just write or speak - I read everything and answer.\n\nHOW TO DO AN INTERVIEW:\n1. Tap \"Start interview\"\n…"`
  (die Aufzaehlungsstruktur 1.–4. und die Befehlszeilen bleiben);
  `_ZEILE_CHECKLISTE = "What it takes: {liste}"`;
  `leitfaden.TEXT_KOPF = "Your interview guide:"`,
  `UEBERSCHRIFT_EROEFFNUNG = "How to start:"`,
  `UEBERSCHRIFT_FRAGEN = "Your questions:"`,
  `UEBERSCHRIFT_ABSCHLUSS = "How to finish:"`,
  `TEXT_LEER = "I don't have an interview guide yet - for that I need your questions first."`;
  `bot._TEXT_WIEDERKEHR = "I'm back. We're at {phase}."`.
- [ ] **Schritt 4:** gruen:
  `$PY -m pytest -q -p no:cacheprovider tests/test_chat_sprache.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py tests/test_befehle.py tests/test_bot.py tests/test_leitfaden.py tests/test_phasentexte.py tests/test_fehlstellen.py`;
  `$PY -m scripts.pruefe_sprache --schluessel befehle,bot,leitfaden,phasentexte,fehlstellen,phasen` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** `_TEXT_HILFE` in `_befehl_hilfe`
  wieder nackt → `test_keine_nackte_verwendung[befehle]` rot **und**
  `test_hilfe_auf_englisch` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Chat-Geruest auf Englisch: Befehle, Begruessung, Leitfaden, Phasenrahmen (A1)"`.

---

## Aufgabe 15: Aufnahme, Gespraech, Erkenner-Meldung, Kontext-Koepfe, kleine Module

**Module:** `aufnahme` (19: `_TEXT_*`, `_JOURNAL_PHASE_DURCH_AUFNAHME`;
Inline aufnahme.py:395, 540, 543, 550, 561; `:710` Vorfall → erlaubt),
`ablauf` (`_TEXT_HINWEIS`, `_TEXT_FEHLER`, `_TEXT_ECHO_ERMAHNUNG`,
`_AUFTRAG_KOPF`; Inline ablauf.py:135 — der Nachschlag an den Nutzertext
„Deine letzte Antwort war dein Selbstgespraech…" — als
`_TEXT_DENKSPUR_ERMAHNUNG`; ablauf.py:129/143/552/564/698/719/731 sind
Vorfall-/Logtexte → erlaubt), `erkenner` (`_AUFNAHME_KOPF`,
`_JOURNAL_ENTFERNT`, `_JOURNAL_ZURUECK`; Inline erkenner.py:259 Vorlauf-Kopf,
`:586` Meldung, `:1319`, `:1519/1521/1523` Meldungen, **`"Notiert:\n"`
erkenner.py:1418** und die Zeilenbeschriftungen in `_meldungszeilen`;
`"Neue Nachrichten:\n"` erkenner.py:256; `:488`/`:837`/`:1301` Vorfall →
erlaubt), `kontext` (`KERNPAKET_KOPF`, `FESTLEGUNGEN_KOPF`,
`_PHASENHINWEIS`, `_FIGURENHINWEIS`, `_TEXT_SZENE_GEKUERZT`,
`ERSTKONTAKT`, `ERSTKONTAKT_LINK`; Inline kontext.py:390; **neu**
`_SPRECHER_BOT = "Du"` fuer `sprecherzeile` kontext.py:245 und alle
Blockkoepfe in `baue`/`_bloecke`, z. B. `"Aktuell:\n"`; `:1380`/`:1401`
Log → erlaubt), `journal` (`"Ausschnitt:\n"` journal.py:192 als
`_AUSSCHNITT_KOPF`), `verdichter` (`_FRAGEN_KOPF`, `_TRANSKRIPT_KOPF`,
`_NACHTRAG_WOERTLICH`), `kuerzung` (7), `vorspann` (Inline
vorspann.py:221/223 „Wo und wann"/„Worum es geht" und die weiteren
Abschnittsnamen), `sprecher` (2 + Inline sprecher.py:223), `stile`
(`TEXT_OHNE`, `STILE`, `VORSCHLAG_GRUND`; Inline stile.py:167),
`arbeitszeilen` (`ZEILEN`, `VORGABE`).

**Sonderfaelle:**
- `stile._NACH_SLUG` (stile.py:101) wird beim Import aus `STILE` gebaut.
  Die Mitgliedschaftspruefung (`slug in _NACH_SLUG`) bleibt; die
  **Anzeige** (Name, Beschreibung, Herkunft) liest eine neue Funktion
  `_eintrag(slug) -> dict | None`, die `{s["slug"]: s for s in T.STILE}`
  zur Aufrufzeit baut. Die Slugs sind Protokoll (Paritaetstest).
- `kontext._SYSTEMANFAENGE` und `ablauf._SYSTEMZEILEN`/`_DENKSPUR_*` sind
  **Parser** (Aufgabe 22/24), nicht hier.
- `erkenner.baue_meldung`: das Wort `"Notiert:"` ist zugleich Kennzeichen
  im Simulator (`simulation/skript.py` liest es aus `erkenner.baue_meldung`)
  — dort wird es datengetrieben gelesen, **also nichts anpassen**, nur
  pruefen: `grep -rn "Notiert" simulation/*.py`.

- [ ] **Schritt 1: Tests** (in `tests/test_chat_sprache.py` anhaengen):

```python
from interview_theater import aufnahme, erkenner, kontext, stile


def test_notiert_zeile_auf_englisch(padua):
    meldung = erkenner.baue_meldung([{"art": "begriffe_setzen", "wert": "love, anger"}])
    assert meldung.startswith("Noted:")


def test_bot_heisst_im_verlauf_you(padua):
    assert kontext.sprecherzeile({"ist_bot": 1, "absender": "x", "text": "hi", "typ": "text"}) == "You: hi"


def test_bot_heisst_im_verlauf_weiter_du():
    assert kontext.sprecherzeile({"ist_bot": 1, "absender": "x", "text": "hi", "typ": "text"}) == "Du: hi"


def test_stile_zeigen_englisch_aber_gleiche_slugs(padua):
    assert [s["slug"] for s in stile.T.STILE] == [s["slug"] for s in stile.STILE]
```

- [ ] **Schritt 2:** rot, dann `UMGESTELLT |= {"aufnahme", "ablauf",
  "erkenner", "kontext", "journal", "verdichter", "kuerzung", "vorspann",
  "sprecher", "stile", "arbeitszeilen"}` → Arbeitsliste.
- [ ] **Schritt 3:** umstellen. Englische Kernwerte:
  `"Notiert:\n"` → `"Noted:\n"`; `_SPRECHER_BOT` → `"You"`;
  `aufnahme._TEXT_VERDICHTUNG_KOPF = "{name} is done. What I hear in it:"`;
  `aufnahme._TEXT_TEIL_ECHO = "{name}, part {nummer}:\n{transkript}"`;
  `kontext.ERSTKONTAKT` — die Anweisung an das Modell, die Begruessung zu
  schreiben: auf Englisch, **mit** dem Satz „Never address anyone by first
  name." am Ende (E8, siehe Aufgabe 18) und mit `{link}` an derselben Stelle.
- [ ] **Schritt 4:** gruen: die betroffenen Modul-Tests
  (`tests/test_aufnahme.py tests/test_ablauf.py tests/test_erkenner.py tests/test_kontext.py tests/test_journal.py tests/test_verdichter.py tests/test_kuerzung.py tests/test_vorspann*.py tests/test_sprecher.py tests/test_teil4_stile.py`)
  plus `tests/test_chat_sprache.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py tests/test_prompt_audit.py`;
  `$PY -m scripts.pruefe_sprache --schluessel aufnahme,ablauf,erkenner,kontext,journal,verdichter,kuerzung,vorspann,sprecher,stile,arbeitszeilen` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** `sprecherzeile` wieder mit `"Du"`
  als Literal → `test_bot_heisst_im_verlauf_you` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Aufnahme, Gespraech, Erkenner-Meldung und Prompt-Koepfe ueber T (A1)"`.

---

## Aufgabe 16: Szene, Einwilligung (E9), Szenenfolge, Geschichte, Schaerfung, Pruefung

**Module:** `szene` (36 Schluessel ohne `_ANDERS_NICHTS`=Parser → 35, darunter
die sieben USA-Texte `_TEXT_WARNUNG_USA`, `_TEXT_ANGEBOT_USA`,
`_TEXT_USA_JA`, `_TEXT_USA_NEIN`, `_TEXT_USA_ERINNERUNG`,
`_TEXT_USA_KEINE_ANTWORT` (szene.py:123–163), `FELDNAMEN`, die
Nutzertext-Koepfe `KERNPAKET_KOPF`, `FIGUREN_KOPF`, `CONTINUITY_*`,
`DIESE_SZENE_KOPF`, `_AUFGABE_ERSTE/_MITTE/_LETZTE`, `NEU_HINWEIS`,
`BISHER_KOPF`, `VORLAGE_KOPF`, `CHAT_KOPF`, `CHAT_ANSCHLUSS`,
`CHAT_REGIE_KOPF`; Inline szene.py:848, 854, 1256, 1542; `:1841–2097`
Log/Vorfall → erlaubt; **`szene._chat_text` (szene.py:1648–1667)**:
`"Du:"`/`"Gruppe:"` → `_SPRECHER_DU`/`_SPRECHER_GRUPPE`), `szenenfolge` (13
ohne `DETAIL_RICHTUNG_UNVOLLSTAENDIG`; Inline szenenfolge.py:654–961, 1201),
`kurzgeschichte` (7; Inline :258, :261, :263), `schaerfung` (4; Inline
:161, :424, :428, :487, :498), `sprachprofil` (3; Inline :161),
`sprachstil` (4; Inline :116, :135), `kernzitate` (2; Inline :118, :247),
`stueckpruefung` (9 ohne `FRAGEN`; Inline :265), `dramaturgie.beleg`
(`HINWEIS`), `dramaturgie.fanout` (12; Inline fanout.py:593–1146 — die
Nutzertexte an den Richter und die Befundsaetze an die Gruppe),
`dramaturgie.mechanik` (Inline mechanik.py:401–984 — Befundsaetze an die
Gruppe), `web_schreiben` (`STIL_BESCHRIFTUNG`, `SZENENFELDER`; Inline
web_schreiben.py:206, 356, 372, 391, 418 = Journalzeilen „… über die
Gruppenseite" → `JOURNAL_*`).

**E9 — die Einwilligung bleibt inhaltlich gleich, nur Englisch.** Die
Entscheidungslogik (`repo.setze_szene_usa(bool)`, `szene_claude.angebot_faellig`,
`USA_ERINNERUNGEN_MAX`) wird **nicht** angefasst. Englisch fuer
`_TEXT_ANGEBOT_USA` (Absatzstruktur wie szene.py:133–143):

```
Before I write the first scene, a decision for you.

Until now everything ran in Switzerland: your recordings, the interviews, everything with names. That stays that way.

For the scene text there is a better model - from Anthropic, in the USA. We compared them this morning: it writes much better stage texts. If you choose it, your core theme, the characters with their quotes and the scene details go to a server in the USA - that is, what will be on stage anyway. No recordings, no complete interviews, no names from this chat.

Do you want that? Say yes or no. If you say no, I'll write the scene in Switzerland - that works too, the text will be simpler.
```

(Der Satz „We compared them this morning" steht so im Deutschen — Birk
entscheidet in Karte P, ob er fuer Padua stimmt; A1 uebersetzt treu.)

- [ ] **Schritt 1: Tests** (neu `tests/test_szene_sprache.py`):

```python
"""Szenenweg auf Englisch, Einwilligung inhaltlich gleich (E9)."""

import pytest

from interview_theater import repo, sprache, szene, workshop


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    yield
    sprache.vergiss()


@pytest.mark.parametrize("deutsch, englisch_", [
    ("Anthropic", "Anthropic"), ("USA", "USA"), ("Schweiz", "Switzerland"),
    ("Keine\nAufnahmen", "No recordings"), ("keine Namen aus diesem Chat", "no names from this chat"),
    ("ja oder nein", "yes or no"),
])
def test_einwilligung_traegt_dieselben_kernaussagen(englisch, deutsch, englisch_):
    assert " ".join(deutsch.split()) in " ".join(szene._TEXT_ANGEBOT_USA.split())
    assert englisch_ in " ".join(szene.T._TEXT_ANGEBOT_USA.split())


def test_warnung_vor_jeder_szene_auf_englisch(englisch):
    for kern in ("Anthropic", "USA", "no audio recordings", "no names from this chat", "Switzerland"):
        assert kern in " ".join(szene.T._TEXT_WARNUNG_USA.split())


def test_nein_bleibt_ein_nein(conn):
    """AGENTS.md-Fallstrick: setze_szene_usa nimmt bool."""
    repo.setze_szene_usa(conn, 1, False)
    assert repo.szene_usa_stand(conn, 1) == "nein"


def test_chatblock_des_szenenlaufs_englisch(englisch):
    assert szene.T._SPRECHER_GRUPPE == "Group"
    assert szene.T._SPRECHER_DU == "You"
```

  (Die Keine-Aufnahmen-Zeile im deutschen Original ist umbrochen; der Test
  vergleicht whitespace-normalisiert. Stimmen die deutschen Kernwoerter im
  Parametersatz nicht zeichengenau mit szene.py:132–144 ueberein, den
  **Parametersatz** an den Code anpassen, nie den Code.)
- [ ] **Schritt 2:** rot; `UMGESTELLT |= {"szene", "szenenfolge",
  "kurzgeschichte", "schaerfung", "sprachprofil", "sprachstil",
  "kernzitate", "stueckpruefung", "dramaturgie.beleg",
  "dramaturgie.fanout", "dramaturgie.mechanik", "web_schreiben"}` → Arbeitsliste.
- [ ] **Schritt 3:** umstellen. Mit dieser Aufgabe wird auch
  `knoepfe/stationen.py:194` (`szene_modul._TEXT_ANGEBOT_USA`) zu
  `szene_modul.T._TEXT_ANGEBOT_USA`, und `befehle.py:716/718` verweisen auf
  `szene.T._TEXT_USA_JA/_NEIN` (Aufgabe 14). `scripts/pruefe_profil.py`
  liest `szenenfolge.ANWEISUNG_*` jetzt ueber `szenenfolge.T`.
  `scripts/prompt_schnappschuss.py:111` (`szenenfolge.ANWEISUNG_FELDER`) →
  `szenenfolge.T.ANWEISUNG_FELDER`.
- [ ] **Schritt 4:** gruen: `tests/test_szene*.py tests/test_szenenfolge.py tests/test_teil4_kurzgeschichte.py tests/test_schaerfung.py tests/test_sprachprofil.py tests/test_sprachstil.py tests/test_kernzitate.py tests/test_stueckpruefung.py tests/test_dramaturgie*.py tests/test_web_schreiben.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py tests/test_prompt_audit.py`;
  `$PY -m scripts.pruefe_sprache --schluessel szene,szenenfolge,kurzgeschichte,schaerfung,sprachprofil,sprachstil,kernzitate,stueckpruefung,dramaturgie.beleg,dramaturgie.fanout,dramaturgie.mechanik,web_schreiben` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** im englischen `_TEXT_ANGEBOT_USA`
  „no names from this chat" streichen →
  `test_einwilligung_traegt_dieselben_kernaussagen` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Szenenweg, US-Einwilligung und Pruefung ueber T (A1, E9)"`.

---

## Aufgabe 17: Die Gruppenseite, Probenansicht und Leitfaden-Seite auf Englisch (D10d)

**Nicht** das Team-Dashboard `/` (`web.dashboard_html`): es wird projiziert,
ist fuer das Team, und Karte A2/UX fasst es an. Seine Texte bleiben deutsch
und stehen in `INLINE_ERLAUBT` mit Grund „Dashboard, Team".

**Files:**
- Modify: `interview_theater/web.py` (Texte der Funktionen `gruppe_html`,
  `textbuch_html`, `leitfaden_html`, `_leitfaden_blocks`,
  `nicht_gefunden_html`, `_seite` und aller `_…_html`-Helfer, die sie
  rufen; `lang="de"` an web.py:601, 2242, 2290 → `lang="{sprache.code()}"`;
  Konstanten `TEXT_LEITFADEN_LINK`, `TEXT_FASSUNGEN`, `_PROBE_PLANUNG`,
  `TEXT_UNGESCHRIEBEN`, `TEXT_LEITFADEN_LEER`, `TEXT_LEITFADEN_ZURUECK`
  ueber `T`)
- Modify: `texte.toml`, `tests/test_sprache_texte.py`
  (`UMGESTELLT |= {"web"}`, `INLINE_ERLAUBT` fuer Dashboard und Logs)
- Test: `tests/test_web_sprache.py` (neu)

**Arbeitsliste:** `$PY /tmp/a1_inv/inline.py --liste | grep web.py` (35
Treffer) **plus** die Einwort-Beschriftungen, die die Heuristik nicht fasst
(`<h2>Arbeitsstand</h2>`, `<h2>Szenen</h2>`, `"Speichern"` als
`_rahmen(…, knopf="Speichern")` web.py:772 — Achtung: **Default-Argument**,
wird zu `knopf: str | None = None` und im Rumpf `knopf or T.TEXT_SPEICHERN`).
Das **Orakel** fuer Vollstaendigkeit ist der Render-Test unten: er rendert
die drei Seiten fuer eine englische Fixture-Gruppe und laesst
`pruefe_sprache.deutsche_treffer` darueber laufen.

- [ ] **Schritt 1: Test schreiben** — `tests/test_web_sprache.py`:

```python
"""Gruppenseite, Probenansicht, Leitfaden-Seite ohne deutsches Wort (D10d)."""

import pytest

from interview_theater import db, sprache, web, web_daten, workshop
from scripts import pruefe_sprache
from tests.fixture_sprache import baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _seiten(tmp_path):
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    lesend = web_daten.oeffne_lesend(pfad)       # web_daten.py:40, wie web.py:2653
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)          # web_daten.py:1066
        leitfaden = web_daten.leitfaden_nach_token(lesend, token)   # web_daten.py:1206
    finally:
        lesend.close()
    return {
        "gruppe": web.gruppe_html(daten, web.nonce(b"k", token), token),
        "textbuch": web.textbuch_html(daten, token),
        "leitfaden": web.leitfaden_html(leitfaden | {"token": token}),
    }


def test_padua_seiten_ohne_deutsch(tmp_path, padua):
    treffer = []
    for name, html in _seiten(tmp_path).items():
        treffer += pruefe_sprache.deutsche_treffer(f"web {name}", pruefe_sprache.nur_text(html))
    assert [f"{t.quelle}: {t.wort} | {t.ausschnitt}" for t in treffer] == []


def test_dortmund_seiten_schlagen_an(tmp_path):
    """Positivkontrolle: ohne sie prueft der erste Test womoeglich nichts."""
    treffer = []
    for name, html in _seiten(tmp_path).items():
        treffer += pruefe_sprache.deutsche_treffer(f"web {name}", pruefe_sprache.nur_text(html))
    assert treffer


def test_lang_attribut(tmp_path, padua):
    assert '<html lang="en">' in _seiten(tmp_path)["gruppe"]
```

  Dazu zwei Hilfen, die dieser Test **mitbringt**:
  - `pruefe_sprache.nur_text(html: str) -> str` (in `scripts/pruefe_sprache.py`):
    entfernt `<script>…</script>`, `<style>…</style>` und Tags, dekodiert
    Entitaeten (`html.unescape`) — geprueft wird, was man liest, nicht CSS
    und JavaScript.
  - `tests/fixture_sprache.py` legt **diese** Aufgabe an, und zwar
    vollstaendig in der Fassung, die in **Aufgabe 25, Schritt 1** steht
    (erfundene englische Gruppe: Arbeitsstand, zwei Figuren, zwei Szenen,
    ein Interview mit Verdichtung, 24 Nachrichten dreier Absender;
    `baue_englische_gruppe(conn) -> str` liefert `gruppe.web_token`).
    Aufgabe 25 benutzt sie dann nur noch.
  - `web_daten.oeffne_lesend(pfad)` (web_daten.py:40),
    `gruppe_nach_token(conn, token)` (:1066) und
    `leitfaden_nach_token(conn, token)` (:1206) sind die bestehenden
    Lesezugriffe — derselbe Weg wie im Server (web.py:2652–2657).
- [ ] **Schritt 2:** rot: `$PY -m pytest -q -p no:cacheprovider tests/test_web_sprache.py`
  → `test_padua_seiten_ohne_deutsch` listet jeden deutschen Rest (das ist die
  Arbeitsliste), `test_lang_attribut` rot.
- [ ] **Schritt 3:** umstellen (fuenf Schritte), bis die Liste leer ist.
  `_SCROLL_JS`/`_BEARBEITEN_JS` enthalten Kommentare, keine Nutzertexte
  (`nur_text` entfernt `<script>`); pruefen, ob sie Meldungen an den Nutzer
  enthalten (`alert(`, `textContent =`) — wenn ja, ueber ein `data-`-Attribut
  aus `T` einspeisen.
- [ ] **Schritt 4:** gruen: `tests/test_web*.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py`.
- [ ] **Schritt 5: Mutationsnachweis:** in `gruppe_html` eine Ueberschrift
  zurueck auf das deutsche Literal → `test_padua_seiten_ohne_deutsch` rot.
- [ ] **Schritt 6:** SUITE; `test_umgestellt_ist_teilmenge_von_alle_module`
  und zusaetzlich einmal von Hand `assert UMGESTELLT == ALLE_MODULE` (in
  den Test aufnehmen: `test_alle_module_sind_umgestellt`) — ab jetzt gilt
  der Waechter fuer das ganze Paket. Commit
  `"Gruppenseite, Probenansicht und Leitfaden-Seite auf Englisch (A1)"`.

---

## Gemeinsame Regeln fuer die Prompt-Uebersetzungen (Aufgaben 18–21)

1. **Gleiche Struktur:** gleiche Ueberschriften (Anzahl und Ebene), gleiche
   Code-Zaeune, gleiche Zahl JSON-Beispielzeilen (`^{"`), gleiche
   Reihenfolge der Abschnitte. `test_gleiche_platzhalter_und_struktur`
   misst die ersten drei.
2. **Gleiche Platzhalter** `{{…}}` — ausser in den vier Inhaltsbausteinen
   (W1).
3. **Protokoll-Token woertlich** (K6): `VORSCHLAG …:`-Marker, Feldnamen in
   JSON-Beispielen (`"aenderungen"`, `"art"`, `"wert"`, `"antwort"`), die
   Erkenner-`art`-Namen, `BEFUND:`/`BEWERTUNG:`/…, `SCORE`/`BELEG`/…,
   `TITEL:`/`KURZ:`/`ZUSAMMENFASSUNG:`/`ANDERS GEMACHT:`, `Ende:` (bis
   Aufgabe 23 den Parser zweisprachig macht, siehe dort), Formwerte
   `dialog|monolog|chor|lied|rap|prosa`.
4. **Sprachsaetze umdrehen, nicht uebersetzen:** „Schreibe auf Deutsch"
   (system.md:352, journal.md:23/58, verdichter.md:59, erkenner.md:407,
   szene.md:201, sprachprofil.md:48, stueckpruefung.md:48,
   theater-tells.md:44/95) wird „Write in English" **mit** der D7-Regel, wo
   Material zitiert wird.
5. **Keine deutschen Beispielnamen, -orte, -zitate.** Beispielnamen werden
   neu erfunden (nicht aus dem Projektumfeld; Vorschlag: `Nadia`, `Tomas`,
   `Ines`, `Karim`, `Lena` — bewusst europaeisch-neutral), Beispielorte
   kommen aus `{{ort_beispiel_N}}`, wo der deutsche Text einen Platzhalter
   hat, sonst neutral („a bus stop" nur, wo das Deutsche einen festen Ort
   nennt).
6. **Datum-/Herkunftsnotizen** in Ueberschriften („(06.09.2026, Birk)")
   bleiben als Zahl, das deutsche Wort faellt weg: `## How a suggestion comes
   about (06.09.2026)`.
7. **Nachweis je Aufgabe:** Namen aus `NOCH_OFFEN` nehmen,
   `tests/test_sprache_prompts.py` gruen,
   `$PY -m scripts.pruefe_sprache --dateien <alle Dateien der Aufgabe>` →
   `0 Treffer`, `$PY -m scripts.pruefe_profil padua-2026` meldet **keinen**
   Platzhalter ohne Wert, `tests/test_sprache_bitgleich.py` gruen (die
   Repo-Dateien sind unberuehrt).

**E8-Satz (verbindlich, woertlich in `system.md`, `phasen/*.md` nicht):**

```
Never address anyone by their first name. Never write the real name of a
group member or of an interviewee - not in your reply, not in a summary, not
in a scene. The people in the chat appear to you as "Member 1", "Member 2";
interviewees are "Interview 1", "Interview 2". Characters always carry
invented names.
```

**D7-Satz (verbindlich, woertlich in `verdichter.md`, `kernzitate.md`,
`schaerfung.md`, `sprachprofil.md`):**

```
Write your summary in English. Supporting quotes stay word for word in the
language of the transcript - never translate them, never tidy them up. An
Italian sentence stays Italian, an Arabic sentence stays Arabic.
```

---

## Aufgabe 18: Englische Prompts I — das Gespraech (`system`, `phasen/1–7`, Rahmen, Projekt)

**Files (Create):** `interview_theater/sprachen/en/prompts/system.md`,
`phasen/1.md` … `phasen/7.md`, `rahmen.md`, `rahmen-kurz.md`,
`rahmen-knapp.md`, `projekt.md` — **12 Dateien, ≈ 65 000 Zeichen**
(Groessen B4). `.gitkeep` loeschen.
**Modify:** `tests/test_sprache_prompts.py` (`NOCH_OFFEN` minus diese 12;
neue Tests unten).

**Besonderheiten:**
- `phasen/N.md` behalten den Abschnitt „Was du nicht von dir aus anfaengst"
  als **„What you don't start on your own:"** und den festen Schlusssatz
  (`tests/test_anweisungen.py:125–131` verlangt das Deutsche) als
  **„If the group explicitly asks for it, you do it anyway; the phase is
  your focus, not its limit. The phase is set afterwards."** — keine
  Slash-Befehle (Test wie `test_keine_phasenanweisung_bewirbt_einen_slash_befehl`).
- `phasen/2.md` Zeile mit `{{projekt}}` bleibt, der Absatz um
  „Behoerdendeutsch" (phasen/2.md:118) wird „no officialese".
- **Inhaltsbausteine (W1):** `rahmen.md` englisch als Vorlage:

```markdown
## Frame of the play

These rules are fixed. They stand above every suggestion you make yourself --
if you suggest something that contradicts them, the suggestion is wrong, not
the frame. Only the group's material (their interviews, their summaries, what
they say in the chat) takes precedence; it comes before every example in
these instructions.

- **Who performs:** The group are {{zielgruppe}}
  ({{zielgruppe_traeger}}). The characters, the language and the conflicts are theirs.
- **Where it is set:** {{orte}} **Not:** {{orte_ausgeschlossen}}.
- **Where it is shown:** {{auffuehrungsort}}. The scenes need **no set and no
  props** except what people wear. **First a script is written**; how it is
  staged -- dance, music, stage -- the team decides in rehearsal. The script is
  source material.
- **What may be in it:** conflict may be serious -- {{konflikt_erlaubt}}.
  {{konflikt_ausgeschlossen}}.
```

  `rahmen-kurz.md` und `rahmen-knapp.md` entsprechend kurz aus denselben
  Platzhaltern; `projekt.md` = `{{projekt_kurz}}` in einem Satz
  eingebettet („We are developing a piece of theatre: {{projekt_kurz}}.").
  (`scripts/pruefe_profil.py` prueft danach „Rahmenblock nennt die
  Zielgruppe" — mit `{{zielgruppe}}` erfuellt.)
- **E8-Satz** am Ende des Abschnitts, der die Anrede regelt (system.md
  „Schreibe auf Deutsch, in kurzen, natuerlichen Saetzen" Zeile 352 →
  „Write in English, in short, natural sentences …" und direkt danach der
  E8-Absatz).

- [ ] **Schritt 1: Tests** (in `tests/test_sprache_prompts.py`):

```python
@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_e8_steht_im_englischen_gespraechsprompt(padua):
    text = " ".join(anweisungen.hole("system").split())
    assert "Never address anyone by their first name." in text
    assert "Characters always carry invented names." in text


@pytest.mark.parametrize("nummer", range(1, 8))
def test_englische_phasen_sind_fokus_kein_kaefig(padua, nummer):
    text = " ".join(anweisungen.hole(f"phasen/{nummer}").split())
    assert "What you don't start on your own:" in text
    assert "the phase is your focus, not its limit" in text


@pytest.mark.parametrize("nummer", range(1, 8))
def test_englische_phasen_bewerben_keinen_befehl(padua, nummer):
    assert not re.search(r"(?<![\w/])/[a-z]{3,}", anweisungen.hole(f"phasen/{nummer}"))


def test_padua_systemanweisung_ohne_offenen_platzhalter(padua):
    for phase in range(1, 8):
        assert "{{" not in anweisungen.system("gruppe1", phase)
```

- [ ] **Schritt 2:** rot: `test_e8_…` → `AssertionError` (deutscher Prompt).
- [ ] **Schritt 3:** die 12 Dateien schreiben; `NOCH_OFFEN -= {"system",
  "phasen/1", …, "phasen/7", "rahmen", "rahmen-kurz", "rahmen-knapp", "projekt"}`.
- [ ] **Schritt 4: Gruen und Nachweis**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_anweisungen.py \
    tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py tests/test_profile_geruest.py
$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/system.md \
    interview_theater/sprachen/en/prompts/phasen/*.md interview_theater/sprachen/en/prompts/rahmen*.md \
    interview_theater/sprachen/en/prompts/projekt.md
$PY -m scripts.pruefe_profil padua-2026
```
Expected: gruen; `0 Treffer`; `pruefe_profil` meldet nur das Geruest (Text
siehe Aufgabe 29), keinen Platzhalter.

- [ ] **Schritt 5: Mutationsnachweis:** in `en/prompts/phasen/4.md`
  `{{rahmen_kurz}}` loeschen → `test_gleiche_platzhalter_und_struktur[phasen/4]` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Englische Gespraechsprompts: system, Phasen, Rahmen-Vorlagen (A1, E8)"`.

---

## Aufgabe 19: Englische Prompts II — die Extraktion (`erkenner`, `journal`, `verdichter`, `kernzitate`, `schaerfung`, `sprachprofil`)

**Files (Create):** `sprachen/en/prompts/erkenner.md` (35 139 Zeichen im
Original), `journal.md`, `verdichter.md`, `kernzitate.md`, `schaerfung.md`,
`sprachprofil.md` — **6 Dateien, ≈ 50 500 Zeichen**.

**Besonderheiten:**
- **`erkenner.md` ist gemessen (FP = 0) — die englische Fassung ist
  ungemessen, bis Aufgabe 31 laeuft.** Alle 21 Few-Shots bleiben (gleiche
  `"aenderungen"`-Zeilen, gleiche `art`), ihre **Gruppennachrichten** werden
  englisch neu geschrieben (nicht Wort fuer Wort: Zustimmung klingt
  englisch „sounds good", „let's take that", „ok do it"), **zwei** der
  Few-Shots bekommen italienische Einsprengsel („va bene", „sì, perfetto")
  — Padua-Wirklichkeit, und dieselben Faelle kommen in den Korpus
  (Aufgabe 27). Regel 8 (erkenner.md:407 „Antworte auf Deutsch,
  ausschliesslich mit dem JSON-Objekt") → „Answer only with the JSON object.
  `wert` stays in the group's own words and language."
- `journal.md:23` „ein deutscher Satz von 8 bis 20 Woertern" → „one English
  sentence of 8 to 20 words"; `:58` → „Answer in English, in the group's words."
- `verdichter.md:59`, `kernzitate.md`, `schaerfung.md`, `sprachprofil.md:48`:
  **D7-Satz** woertlich.
- Absendernamen in den Few-Shots erscheinen schon als **„Member 1:"**,
  **„Member 2:"** — so sieht das Modell den Verlauf in Padua (Aufgabe 25).

- [ ] **Schritt 1: Test** (in `tests/test_sprache_prompts.py`):

```python
@pytest.mark.parametrize("name", ["verdichter", "kernzitate", "schaerfung", "sprachprofil"])
def test_d7_zitate_bleiben_im_original(padua, name):
    text = " ".join(anweisungen.hole(name).split())
    assert "Supporting quotes stay word for word in the language of the transcript" in text
    assert "never translate them" in text


def test_erkenner_behaelt_seine_few_shots(padua):
    deutsch = (REPO / "erkenner.md").read_text(encoding="utf-8").count('"aenderungen"')
    assert anweisungen.hole("erkenner").count('"aenderungen"') == deutsch == 21
```

- [ ] **Schritt 2:** rot; **Schritt 3:** schreiben, `NOCH_OFFEN -= {…6…}`.
- [ ] **Schritt 4:** gruen wie Aufgabe 18 (Test-Dateien plus
  `tests/test_erkenner.py tests/test_journal.py tests/test_verdichter.py tests/test_korpus.py`);
  `$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/{erkenner,journal,verdichter,kernzitate,schaerfung,sprachprofil}.md` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** einen Few-Shot im englischen
  Erkenner loeschen → `test_gleiche_platzhalter_und_struktur[erkenner]`
  und `test_erkenner_behaelt_seine_few_shots` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Englische Extraktionsprompts, Zitate im Original (A1, D7)"`.

---

## Aufgabe 20: Englische Prompts III — die Szene (`szene`, `theater-tells`, `formen/*`, `stile/*`)

**Files (Create):** `sprachen/en/prompts/szene.md`, `theater-tells.md`,
`formen/{dialog,monolog,chor,lied,rap,prosa}.md`,
`stile/{herkules,litanei,schlagabtausch}.md` — **11 Dateien, ≈ 55 000 Zeichen**.

**Besonderheiten:**
- `szene.md:201` „Deutsch. Kommen in den Zitaten andere Sprachen vor, duerfen
  sie in den …" → „English. If other languages appear in the quotes, they may
  stay in the characters' lines …" (Mehrsprachigkeit bleibt erlaubt — die
  Figuren duerfen italienisch einwerfen, wenn das Material es tut).
  **E8-Satz** (nur der Teil zu Figuren und echten Namen) im Abschnitt zu
  Figuren.
- `theater-tells.md:44` „Alle Figuren sprechen dasselbe Deutsch" → „All
  characters speak the same English"; `:95`/`:143` die deutschen
  Beispielzitate durch englische ersetzen (erfundene).
- `formen/lied.md:29` „nicht ploetzlich alle in Hochdeutsch singen:
  Fuellwoerter, Dialekt …" → „not suddenly all singing textbook English:
  filler words, dialect …".
- `stile/schlagabtausch.md:15` nennt eine deutschsprachige Rap-Vorlage mit
  gemessenen Zahlen — die Zahlen bleiben (Messung), der Satz sagt „measured
  on a German-language rap source".
- Formnamen im Text **Anzeige**: Dialogue, Monologue, Chorus, Song, Rap;
  **Werte** (`form: chor`) woertlich.

- [ ] **Schritt 1: Test:**

```python
def test_szene_englisch_mit_erfundenen_namen(padua):
    text = " ".join(anweisungen.hole("szene").split())
    assert "Characters always carry invented names." in text
    assert "Write in English" in text or "English." in text


def test_szenen_systemanweisung_englisch(padua):
    from interview_theater import szene
    from scripts import pruefe_sprache

    for form in ("dialog", "monolog", "chor", "lied", "rap", szene.PROSA):
        assert pruefe_sprache.deutsche_treffer(form, szene.systemanweisung(form)) == []
```

- [ ] **Schritt 2–4** wie oben; `NOCH_OFFEN -= {…11…}`;
  `$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/{szene,theater-tells}.md interview_theater/sprachen/en/prompts/formen/*.md interview_theater/sprachen/en/prompts/stile/*.md` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** in `en/prompts/formen/chor.md`
  `{{ort_beispiel_1}}` durch ein Wort ersetzen → Paritaetstest rot.
- [ ] **Schritt 6:** SUITE; Commit `"Englische Szenenprompts, Formen und Stile (A1)"`.

---

## Aufgabe 21: Englische Prompts IV — die Pruefung (`stueckpruefung`, `richter`, `dramaturgie/*`)

**Files (Create):** `sprachen/en/prompts/stueckpruefung.md`, `richter.md`,
`dramaturgie/{a2_kausalkette,a6_tschechow,a9_fokus,a10_materialtreue,a11_stueckvorgaben,b1_wendung,c1_stimme}.md`
— **9 Dateien, ≈ 28 000 Zeichen**. Nach dieser Aufgabe ist `NOCH_OFFEN`
**leer** — die Zuweisung wird zu `NOCH_OFFEN: set[str] = set()`.

**Besonderheiten:**
- `stueckpruefung.md:48` „Schreib deutsch, konkret und ohne Fachjargon" →
  „Write in English, concretely and without jargon".
- `dramaturgie/*.md`: die erste Zeile `prompt_version: <wert>` (z. B.
  `prompt_version: b1-2026-09-06-1`) bleibt **erste Zeile** und bekommt den
  Suffix `-en` (`prompt_version: b1-2026-09-06-1-en`). `fanout._VERSION`
  (fanout.py:288, `^\s*prompt_version:\s*(\S+)\s*$`) liest jeden Wert ohne
  Leerzeichen, und die Version landet in `dramaturgie_befund`
  (fanout.py:1148/1164) — so lassen sich deutsche und englische Laeufe
  trennen.
- `a6_tschechow.md:15` erklaert die deutsche Substantiv-Grossschreibung —
  im Englischen entfaellt der Satz sinngemaess (die Heuristik ist in Padua
  aus, Annahme A7, Aufgabe 23); die Ueberschriftenzahl bleibt gleich.
- `richter.md` benutzt nur `simulation/richter.py` (B4) — uebersetzen fuer die
  Paritaet; ob der Simulator englische Laeufe fahren kann, ist **nicht**
  Teil von A1 (die Stimmen in `simulation/stimmen/` sind deutsch).

- [ ] **Schritt 1–4** wie oben. Zusaetzlich in `tests/test_sprache_prompts.py`:

```python
def test_alle_prompts_sind_uebersetzt():
    assert NOCH_OFFEN == set()
    assert REPO_NAMEN <= _namen(EN)
```

  Nachweis:
  `$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/stueckpruefung.md interview_theater/sprachen/en/prompts/richter.md interview_theater/sprachen/en/prompts/dramaturgie/*.md` → `0 Treffer`,
  und einmal ueber **alle**:
  `$PY -m scripts.pruefe_sprache --dateien $(find interview_theater/sprachen/en/prompts -name '*.md')` → `0 Treffer`.
- [ ] **Schritt 5: Mutationsnachweis:** eine englische Dramaturgie-Datei
  loeschen → `test_jede_repo_datei_hat_eine_englische_fassung` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Englische Pruefprompts, alle 38 Prompts uebersetzt (A1)"`.

---

## Aufgabe 22: Parser A — Gruppentext je Sprache (D5, Art B)

Was die **Gruppe** tippt oder sagt, wird mit den Mustern **ihrer** Sprache
gelesen (Brief: „Profil waehlt"). Muster nach K5: deutsche Konstante bleibt,
`…_EN` kommt dazu, Auswahl ueber `sprache.je_sprache`.

**Files:** `interview_theater/ablauf.py:287–358`, `befehle.py:44–77,
330–358, 388, 443, 638`, `knoepfe/fragen.py:147–183`,
`knoepfe/figuren.py:108–125`, `begriffe.py:48–114`; Test:
`tests/test_sprache_parser.py` (neu).

| Stelle | Deutsch (bleibt) | neu `_EN` |
|---|---|---|
| `ablauf._AUFTRAGSFORMEN` (287) + `_AUFTRAG` (307) | 10 Muster | `_AUFTRAGSFORMEN_EN = (r"re-?write", r"(write|make)\s*(me\s*|us\s*)?(the\s*)?scene\b", r"^\s*(again|once more)\s*$", r"^\s*(keep|continue)\s*writing\s*$", r"^\s*write\s*it\s*out\s*$", r"(start|begin)\s*(the\s*|an?\s*)?interview", r"^\s*(start|stop|end)\s*(the\s*)?recording\s*$", r"interview\b.{0,20}\b(start|begin|go)\b", r"\b(start|begin|let'?s\s+do)\b.{0,20}\binterview\b", r"(end|finish|stop)\s*(the\s*)?interview\b|interview\s*(done|finished|over)\b")`, `_AUFTRAG_EN` |
| `ablauf._SZENENTEXT_NUMMER`/`_WOERTER` (331/332) | `szene\s*(nr)?(\d)`; `zeig|lies|vorles…` | `_SZENENTEXT_NUMMER_EN = re.compile(r"scene\s*(?:no\.?\s*|number\s*)?(\d{1,3})", re.I)`, `_SZENENTEXT_WOERTER_EN = re.compile(r"show|read|look at|\btext\b|wording|what does", re.I)` |
| `befehle._ENTFERNEN_WOERTER` (44) → `_SZENE_ENTFERNEN` (47) | `entfernen…raus` | `_ENTFERNEN_WOERTER_EN = {"remove", "delete", "drop", "out"}`, `_SZENE_ENTFERNEN_EN` mit `(?:scene\s*)?` |
| `befehle` Argumentwort `aus` (356, 388, 638) | `== "aus"` | `_AUS = {"de": ("aus",), "en": ("off",)}` |
| `befehle` `/stueck`-Feld `rahmen` (330) | `"rahmen", "format"` | `"setting"` als englisches Synonym fuer `rahmen` |
| `befehle._FESTLEGUNG_WEG` (443) | `^weg\s+(.+)$` | `_FESTLEGUNG_WEG_EN = re.compile(r"^remove\s+(.+)$", re.I)` |
| `befehle._SZENE_FORM_LEER`/`_SZENE_FELD` (68/75) | `(?:szene\s*)?` | `_EN`-Varianten mit `(?:scene\s*)?`; der Feldname laeuft ueber `szene.feldname` (Aufgabe 23, Vereinigung) |
| `knoepfe/fragen._ORDINALWOERTER` (147) | `erste … zehnte` | `_ORDINALWOERTER_EN = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}` |
| `knoepfe/figuren._zahl_aus` Wortliste (118) | `eine … zwoelf` | `_ZAHLWOERTER_EN = {"one": 1, …, "twelve": 12}` (als Modulkonstante, die deutsche Liste bleibt im Funktionsrumpf wie sie ist) |
| `begriffe._UMLAUTE`/`_ENDUNGEN` (48/60) | deutsche Stammbildung | `_ENDUNGEN_EN = ("ings", "ing", "ies", "es", "s", "ed")`; `stamm` waehlt je Sprache, Umlautfaltung nur fuer Deutsch |

- [ ] **Schritt 1: Tests** — `tests/test_sprache_parser.py`:

```python
"""Parser zweisprachig (D5): Englisch wird erkannt, Deutsch bleibt, wie es war.

Die deutschen Sollwerte sind am 30.09.2026 auf d8deb6c gemessen (Plan A1,
Aufgaben 22-24) -- sie aendern sich durch A1 nicht.
"""

import pytest

from interview_theater import ablauf, begriffe, sprache
from interview_theater.knoepfe import figuren, fragen


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")


# --- Gruppentext je Sprache (Aufgabe 22) ---------------------------------

@pytest.mark.parametrize("text, soll", [
    ("schreib die szene", True), ("neu schreiben", True),
    ("interview starten", True), ("write the scene", False),
])
def test_auftrag_deutsch_wie_vorher(text, soll):
    assert ablauf.ist_auftrag(text) is soll


@pytest.mark.parametrize("text, soll", [
    ("write the scene", True), ("rewrite", True), ("start the interview", True),
    ("let's do an interview", True), ("interview done", True),
    ("I think the interview was good but long", False),
])
def test_auftrag_englisch(englisch, text, soll):
    assert ablauf.ist_auftrag(text) is soll


@pytest.mark.parametrize("text, soll", [
    ("zeig mal szene 2", 2), ("lies uns Szene 3 vor", 3), ("show us scene 2", None),
])
def test_szenentext_deutsch_wie_vorher(text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("show us scene 2", 2), ("read scene 3", 3), ("in scene 2 he should leave", None),
])
def test_szenentext_englisch(englisch, text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("die erste und die dritte", [1, 3]), ("1, 4 und 7", [1, 4, 7]),
    ("the first and the third", []),
])
def test_fragennummern_deutsch_wie_vorher(text, soll):
    assert fragen.lies_fragennummern(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("the first and the third", [1, 3]), ("2, 5 and 8", [2, 5, 8]),
])
def test_fragennummern_englisch(englisch, text, soll):
    assert fragen.lies_fragennummern(text) == soll


@pytest.mark.parametrize("text, soll", [("drei", 3), ("fuenf Figuren", 5), ("three", None), ("4", 4)])
def test_figurenzahl_deutsch_wie_vorher(text, soll):
    assert figuren._zahl_aus(text) == soll


@pytest.mark.parametrize("text, soll", [("three", 3), ("five characters", 5), ("4", 4)])
def test_figurenzahl_englisch(englisch, text, soll):
    assert figuren._zahl_aus(text) == soll


def test_begriffe_deutsch_wie_vorher():
    assert begriffe.passt("Freundschaft", "Sie reden ueber Freundschaften.") is True
    assert begriffe.passt("Freundschaft", "They talk about friendships.") is False


def test_begriffe_englisch(englisch):
    assert begriffe.passt("friendship", "They talk about friendships.") is True


def test_befehl_entfernen_englisch(conn, einst, englisch):
    from interview_theater import befehle, repo
    from simulation.attrappe import TelegramAttrappe

    repo.setze_figur(conn, 1, "Nadia", "sister")
    befehle.behandle(conn, TelegramAttrappe(), einst, 1, "/figur Nadia remove", None)
    assert all(f["name"] != "Nadia" for f in repo.figuren(conn, 1))
```

- [ ] **Schritt 2:** rot: die `…_englisch`-Tests scheitern (Sollwerte aus
  der Messung: `write the scene` → heute `False`, `show us scene 2` → `None`,
  `the first and the third` → `[]`, `three` → `None`,
  `friendships` → `False`); die `…_wie_vorher`-Tests sind **gruen** und
  bleiben es.
- [ ] **Schritt 3:** umsetzen nach K5. Beispiel `ablauf.py`:

```python
_AUFTRAG_EN = re.compile("|".join(_AUFTRAGSFORMEN_EN), re.IGNORECASE)


def ist_auftrag(text: str | None) -> bool:
    """… (bisheriger Text) … Die Muster kommen aus der Sprache des Profils
    (Karte A1): eine englische Gruppe schreibt 'write the scene'."""
    roh = (text or "").strip()
    if not roh or len(roh) > AUFTRAG_HOECHSTLAENGE:
        return False
    muster = sprache.je_sprache({"de": _AUFTRAG, "en": _AUFTRAG_EN})
    return muster.search(roh) is not None
```

  `befehle._figur`-Zweig (befehle.py:408–445) prueft das Entfernungswort
  gegen `sprache.je_sprache({"de": _ENTFERNEN_WOERTER, "en": _ENTFERNEN_WOERTER_EN})`.
  `repo.setze_figur`/`repo.figuren` — Namen am Code pruefen
  (`grep -n "^def setze_figur\|^def figuren" interview_theater/repo.py`);
  heisst der Getter anders, den Test anpassen, nicht den Code.
- [ ] **Schritt 4:** gruen: `tests/test_sprache_parser.py tests/test_ablauf.py tests/test_befehle.py tests/test_knoepfe*.py tests/test_begriffe.py tests/test_sprache_bitgleich.py`.
- [ ] **Schritt 5: Mutationsnachweis:** in `ist_auftrag` `_AUFTRAG_EN` durch
  `_AUFTRAG` ersetzen → `test_auftrag_englisch` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Gruppentext-Muster je Sprache: Auftraege, Szenentext, Nummern, Zahlen, Befehle (A1)"`.

---

## Aufgabe 23: Parser B — Modellausgabe in beiden Sprachen (D5, Art A)

Ein englisches Modell labelt manchmal deutsch und umgekehrt — Ausgabeparser
nehmen **beide** (deutsch zuerst, damit Dortmund dasselbe Ergebnis bekommt).

**Files:** `szene.py` (375, 439/473, 469, 554/559, 1069–1081, 1891–1953),
`kuerzung.py:46/105`, `kurzgeschichte.py:43/48/113`, `szenenfolge.py`
(254, 346, 377–501), `stueckpruefung.py:74/156`, `web.py:1805/1815`,
`erkenner.py` (456/463, 854–887, 1066/1081, 1244), `repo.py:1907/1912`,
`vorspann.py:43/81`, `knoepfe/fragen.py:317/322`, `ablauf.py:69–114`,
`dramaturgie/mechanik.py` (103, 108, 119, 542–578, 821–859);
Test: `tests/test_sprache_parser.py`.

| Stelle | neu |
|---|---|
| `szene._NUMMER` (375) | `_NUMMER_EN = re.compile(r"\bscene\s*(?:no\.?|number)?\s*(\d{1,3})\b", re.I)`; `nummer_aus_auftrag` probiert beide |
| `szene.FELD_ALIASE` (439) → `feldname` (473) | `FELD_ALIASE_EN = {"place": "ort", "location": "ort", "time": "zeit", "occasion": "anlass", "characters": "figuren", "cast": "figuren", "who": "figuren", "what happens": "was_passiert", "plot": "was_passiert", "what's different": "was_anders", "what is different": "was_anders", "key lines": "kernsaetze", "tone": "ton", "title": "titel", "summary": "kurz"}` — Ziel sind die **deutschen Spaltennamen** (Protokoll); `feldname` sucht erst deutsch, dann englisch. **Vorher** die Struktur von `FELD_ALIASE` am Code lesen (Alias → Spalte?) und die Tabelle daran angleichen |
| `szene._PLANUNG_NUMMER` (469) | `(szene|scene)` im `_EN`-Muster |
| `szene._RAHMEN_FELD` (554) | `_RAHMEN_FELD_EN = re.compile(r"(Place|Time|Occasion)\s*:", re.I)` mit Zuordnung auf `ort/zeit/anlass`; `rahmenfelder` probiert beide |
| `szene.zerlege` Kopfzeilen (1932–1947) | Alternativen `TITEL|TITLE`, `KURZ|SHORT`, `ZUSAMMENFASSUNG|SUMMARY`, `ANDERS GEMACHT|DONE DIFFERENTLY` ueber eine kleine Hilfe `_kopfwert_einer(zeile, schluessel: tuple[str, ...])`; `ZUSAMMENFASSUNG_SCHLUESSEL`/`ANDERS_SCHLUESSEL` bleiben unveraendert |
| `szene._ANDERS_NICHTS` (1081) | `_ANDERS_NICHTS_EN = ("nothing", "none", "no deviation", "nothing different", "-")`, Vereinigung |
| `kuerzung._MUSTER_NUMMER` (46) | `_MUSTER_NUMMER_EN = re.compile(r"^\s*(?:scene\s*)?(\d+)\s*$", re.I)` |
| `kurzgeschichte._UEBERSCHRIFT` (43), `_ZUSAMMENFASSUNG` (48) | `(ABSCHNITT|SECTION|PART)` im `_EN`-Muster; `_ZUSAMMENFASSUNG_EN = re.compile(r"^Summary\s*:", re.I)` |
| `szenenfolge` Praefix (254), `_ENDE_PRAEFIX` (346), `_FORMEN`/`_FORMWORT`/`_FORMENKETTE`/`_FORM_ANHANG` (377–454), `_SZENENWORT` (383), `_SZENE_ANKER` (448) | `_EN`-Muster mit `scene`, `end(ing)?`; Formwoerter `dialogue→dialog, monologue→monolog, chorus|choir→chor, song→lied, rap→rap` ueber `_FORM_AUS_EN = {…}` — Rueckgabe sind immer die **deutschen DB-Werte** |
| `stueckpruefung.FRAGEN` Stichwoerter (74) → `frage_fuer` (156) | `_STICHWOERTER_EN = {"Spannungsbogen": ("tension arc", "arc"), "Figuren": ("characters", "character"), "Spannung": ("suspense", "tension"), "Nachvollziehbarkeit": ("plausibility", "logic", "motivation"), "Anfang und Ende": ("beginning", "ending", "exposition"), "Sprechbarkeit": ("speakability", "spoken", "language")}` — Schluessel sind die deutschen Fragenamen aus `FRAGEN` (am Code angleichen); **Anzeige** der Fragenamen ueber eine Beschriftungstabelle `FRAGEN_BESCHRIFTUNG` (K4) |
| `web._KEINE_SPRECHER` (1805) | `_KEINE_SPRECHER_EN = frozenset({"SCENE", "ACT", "TITLE", "SHORT", "SUMMARY", "CHANGED", "DONE DIFFERENTLY", "PLACE", "TIME", "OCCASION", "FORM", "CAST", "CHARACTERS", "DURATION"})`, Vereinigung |
| `erkenner._GESCHICHTE_MARKER` (456) | `_GESCHICHTE_MARKER_EN = re.compile(r"\bEnd(?:ing)?\s*:|\bin the end\b|\bthen\b.*\bthen\b", re.I)`, Vereinigung |
| `erkenner._ZAHLWOERTER`/`_FIGURENZAHL`/`_FIGURENZAHL_UMGEKEHRT` (854–875) | englische Zahlwoerter, `to` statt `bis`, `characters?` statt `figuren`; Ergebnisformat bleibt `"4 bis 5"` (Protokoll zum Arbeitsstand) |
| `erkenner._ENTFERNEN_ZIELE` (1066) | `_ENTFERNEN_ZIELE_EN = {"character": "figur", "core theme": "kernthema", "setting": "rahmen", "story": "geschichte", "terms": "begriffe", "questions": "fragen", "scene": "szene", "agreement": "festlegung", "interview": "interview", "recording": "aufnahme"}` → deutsche Ziele |
| `erkenner` `szene_usa`-Wert (1244) | `yes→ja`, `no→nein` vor dem Vergleich |
| `repo._PLATZHALTERNAME` (1907) | `_PLATZHALTERNAME_EN = re.compile(r"^\s*(main\s+|side\s+)?character\b|^\s*placeholder\b", re.I)`, Vereinigung |
| `vorspann.SCHAERFUNGSFORMELN` (43) | `SCHAERFUNGSFORMELN_EN = ("makes clear", "provides", "shows", "justifies", "explains", "reinforces", "underlines")`, Vereinigung (die Untergrenze `MINDEST_ZEICHEN` schuetzt wie im Deutschen) |
| `knoepfe/fragen._speichere_eroeffnung` (317/322) | `startswith(("abschluss", "closing"))` / `(("eroeffnung", "opening"))` — danach duerfen die englischen `ANWEISUNG_EROEFFNUNG`-Texte `'Closing:'` verlangen (Aufgabe 10 nachziehen, falls dort noch `'Abschluss:'` steht) |
| `ablauf._DENKSPUR_MARKER`/`_EINDEUTIG` (69/84), `_denkspur_kern` (111) | `_DENKSPUR_MARKER_EN = ("i should:", "i should ", "the group wants", "what is in the material", "possible core themes:", "i suggest a ", "perfect. that is", "the rule says", "the recogniser sets", "no markdown", "under 500 characters", "phrase it as an offer", "you should ", "your turn is", "system line", "system announcement", "the system instruction", "one sentence of encouragement")`, `_DENKSPUR_EINDEUTIG_EN` entsprechend; Satzanfaenge `("You", "Your", "A", "An", "The", "What", "How", "This", "Here")` dazu; Vereinigung |
| `dramaturgie/mechanik.py` `KOLLEKTIV` (103), `_STRUKTUR` (108), `_MARKER` (119) | englische Zusaetze (`ALL`, `BOTH`, `CHOIR`, `GROUP`, `EVERYONE`; `scene`, `title`, `summary`, `place`, `time`, `cast`, `act`, `prologue`, `epilogue`; `verse`, `interlude`), Vereinigung |
| `dramaturgie/mechanik.py` Tschechow-/Motiv-Heuristik (542–578, 821–859) | **aus** bei `sprache.code() != "de"` (Annahme A7): `tschechow_kandidaten` liefert `[]`, `_motive` `set()` |

- [ ] **Schritt 1: Tests** (anhaengen, deutsche Sollwerte gemessen):

```python
from interview_theater import erkenner, kuerzung, kurzgeschichte, repo, stueckpruefung, szene, szenenfolge, vorspann, web

DE_SZENE = ("TITEL: Nacht\nKURZ: Zwei streiten.\nZUSAMMENFASSUNG: Sie streiten.\n"
            "ANDERS GEMACHT: nichts\n\nNADIA: Hallo")
EN_SZENE = ("TITLE: Night\nSHORT: Two argue.\nSUMMARY: They argue.\n"
            "DONE DIFFERENTLY: nothing\n\nNADIA: Hi")


def test_szenenkopf_deutsch_wie_vorher():
    assert szene.zerlege(DE_SZENE) == ("Nacht", "Zwei streiten.", "Sie streiten.", None, "NADIA: Hallo")


def test_szenenkopf_englisch_auch_unter_deutschem_profil():
    assert szene.zerlege(EN_SZENE) == ("Night", "Two argue.", "They argue.", None, "NADIA: Hi")


@pytest.mark.parametrize("text, soll", [("Schreib Szene 2", 2), ("write scene 2", 2), ("scene no. 4 please", 4)])
def test_szenennummer_beide(text, soll):
    assert szene.nummer_aus_auftrag(text) == soll


@pytest.mark.parametrize("wort, soll", [("ort", "ort"), ("was passiert", "was_passiert"),
                                        ("place", "ort"), ("what happens", "was_passiert"), ("tone", "ton")])
def test_feldname_beide(wort, soll):
    assert szene.feldname(wort) == soll


@pytest.mark.parametrize("wert, soll", [("Szene 3", 3), ("3", 3), ("Scene 3", 3)])
def test_kuerzung_nummer_beide(wert, soll):
    assert kuerzung.nummer_aus_wert(wert) == soll


def test_kurzgeschichte_englische_zusammenfassung():
    text = "## 1. Arrival\nText one.\nSummary: She arrives.\n\n## 2. Fight\nText two.\nSummary: It explodes."
    assert kurzgeschichte.zerlege(text) == [("Arrival", "She arrives.", "Text one."),
                                           ("Fight", "It explodes.", "Text two.")]


def test_kurzgeschichte_deutsch_wie_vorher():
    text = "## 1. Ankunft\nText eins.\nZusammenfassung: Sie kommt an.\n\n## 2. Streit\nText zwei.\nZusammenfassung: Es kracht."
    assert kurzgeschichte.zerlege(text) == [("Ankunft", "Sie kommt an.", "Text eins."),
                                           ("Streit", "Es kracht.", "Text zwei.")]


@pytest.mark.parametrize("text, soll", [
    ("Szene 1: Dialog, Szene 2: Monolog, Szene 3: Chor", {1: "dialog", 2: "monolog", 3: "chor"}),
    ("Chor-Dialog-Rap", {1: "chor", 2: "dialog", 3: "rap"}),
    ("Scene 1: Dialogue, Scene 2: Monologue, Scene 3: Chorus", {1: "dialog", 2: "monolog", 3: "chor"}),
])
def test_formabfolge_beide(text, soll):
    assert szenenfolge.formabfolge(text) == soll


def test_szenen_in_zeile_beide():
    assert szenenfolge.szenen_in_zeile(
        "Nacht am Kanal. Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis.") == [
        (1, "Ankunft am Steg", ""), (2, "Das Gestaendnis", "")]
    assert szenenfolge.szenen_in_zeile(
        "Night by the canal. Scene 1: Arrival at the pier. Scene 2: The confession.") == [
        (1, "Arrival at the pier", ""), (2, "The confession", "")]


def test_ende_zeile_englisch():
    assert szenenfolge.zerlege_geschichte("They meet.\nEnd: They leave.") == (
        "They meet.\nEnd: They leave.", [])


@pytest.mark.parametrize("zeile, soll", [
    ("SZENE 1: Der Anfang", None), ("NADIA: Hallo", "NADIA"),
    ("SCENE 1: The beginning", None), ("TITLE: Night", None),
])
def test_sprecher_der_zeile_beide(zeile, soll):
    assert web.sprecher_der_zeile(zeile) == soll


@pytest.mark.parametrize("wert, soll", [
    ("Sie streiten. Ende: Versoehnung.", True), ("They fight. End: reconciliation.", True),
    ("In the end they make up, then they leave, then it rains.", True),
])
def test_ist_geschichte_beide(wert, soll):
    assert erkenner._ist_geschichte(wert) is soll


@pytest.mark.parametrize("text, soll", [
    ("Wir wollen drei Figuren", "3"), ("vier bis fuenf Figuren", "4 bis 5"),
    ("We want three characters", "3"), ("four to five characters", "4 bis 5"),
])
def test_figurenzahl_beide(text, soll):
    assert erkenner.figurenzahl_aus(text) == soll


@pytest.mark.parametrize("name, soll", [
    ("Figur 2", True), ("Nebenfigur 1", True), ("Character 2", True),
    ("Placeholder", True), ("Nadia", False),
])
def test_platzhaltername_beide(name, soll):
    assert repo.ist_platzhaltername(name) is soll


def test_vorspann_schneidet_englische_formeln():
    assert vorspann.erster_satz(
        "Nadia fights with herself provides the background for her refusal") == "Nadia fights with herself"
    assert vorspann.erster_satz(
        "Mira kaempft mit sich selbst liefert den Hintergrund fuer ihre Ablehnung") == "Mira kaempft mit sich selbst"


@pytest.mark.parametrize("text, soll", [
    ("Spannungsbogen", "Spannungsbogen"), ("Anfang und Ende", "Anfang und Ende"),
    ("Tension arc", "Spannungsbogen"), ("Beginning and end", "Anfang und Ende"),
])
def test_frage_fuer_beide(text, soll):
    assert stueckpruefung.frage_fuer(text) == soll


def test_denkspur_englisch():
    assert ablauf.ist_denkspur("I should: help the group. The group wants more. The rule says no markdown.")
    assert ablauf.ist_denkspur("Ich soll: der Gruppe helfen. Die Gruppe will mehr.")


def test_tschechow_ist_im_englischen_aus(englisch):
    from interview_theater.dramaturgie import mechanik

    assert mechanik._motive("The Suitcase stands in the Kitchen again and again.", ()) == set()
```

  (Die deutschen Sollwerte stammen aus `$PY /tmp/a1_inv/parser_basis.py`,
  Anhang A.8 — **dort nachmessen**, bevor ein deutscher Test angepasst wird.
  `test_ende_zeile_englisch`: heute trennt `zerlege_geschichte` die
  englische `End:`-Zeile als **Szene** ab (gemessen:
  `('They meet.', [('End: They leave', '', [], 'dialog', '')])`); Soll ist das
  deutsche Verhalten — die Ende-Zeile gehoert zur Geschichte. Den genauen
  Sollwert vorher mit der deutschen Zeile `"Sie treffen sich.\nEnde: Sie
  gehen."` → `('Sie treffen sich.\nEnde: Sie gehen.', [])` abgleichen.)
- [ ] **Schritt 2:** rot (die englischen Faelle; deutsche gruen).
- [ ] **Schritt 3:** umsetzen, Muster K5 („beide probieren, deutsch
  zuerst"). Beispiel `kuerzung.py`:

```python
#: Dasselbe auf Englisch (Karte A1): ein englisches Modell schreibt "Scene 3".
_MUSTER_NUMMER_EN = re.compile(r"^\s*(?:scene\s*)?(\d+)\s*$", re.IGNORECASE)


def nummer_aus_wert(wert: str | None) -> int | None:
    """… (bisheriger Text) …"""
    for muster in (_MUSTER_NUMMER, _MUSTER_NUMMER_EN):
        treffer = muster.match(wert or "")
        if treffer:
            return int(treffer.group(1))
    return None
```

  (Die bestehende Funktion am Code lesen und nur die Schleife ergaenzen —
  weitere Pruefungen darin bleiben.)
- [ ] **Schritt 4:** gruen: `tests/test_sprache_parser.py` plus die
  Modultests der Tabelle (`tests/test_szene*.py tests/test_kuerzung.py
  tests/test_teil4_kurzgeschichte.py tests/test_szenenfolge.py
  tests/test_geschichte.py tests/test_stueckpruefung.py tests/test_web*.py
  tests/test_erkenner.py tests/test_repo.py tests/test_vorspann*.py
  tests/test_dramaturgie*.py tests/test_ablauf.py`) und
  `tests/test_sprache_bitgleich.py` (keine deutsche Konstante veraendert).
- [ ] **Schritt 5: Mutationsnachweis:** in `szene.zerlege` die
  englischen Alternativen streichen →
  `test_szenenkopf_englisch_auch_unter_deutschem_profil` rot; in
  `mechanik._motive` die Sprachabfrage entfernen → `test_tschechow_ist_im_englischen_aus` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Modellausgabe zweisprachig lesen: Szenenkopf, Nummern, Formen, Figurenzahl, Denkspur (A1)"`.

---

## Aufgabe 24: Parser C — Systemzeilen und Rundreisen (D5, Arten C und RT)

Code, der **eigene** Bot-Texte wiedererkennt, muss die englischen kennen —
sonst stehen in Padua „Noted:"-Zeilen im Gespraechsfenster, und erfundene
Systemzeilen des Gespraechs-Bots gehen durch.

| Stelle | neu |
|---|---|
| `kontext._SYSTEMANFAENGE` (1001) → `_ist_systemzeile` (1015) | `_SYSTEMANFAENGE_EN` = die **Anfaenge der englischen Eintraege** derselben Texte: `"I'm back."` (bot._TEXT_WIEDERKEHR), `"Noted:"`, die englischen Anfaenge von „Aufnahme laeuft." / „Aufnahme beendet." (befehle/aufnahme), `"Ready -"` (befehle._TEXT_INTERVIEW_AN), `"Note: The scene text"` (szene._TEXT_WARNUNG_USA), die englischen Anfaenge von szene._TEXT_ANGEKUENDIGT, „Ich schreibe gerade noch", „Ich werte die offenen Interviews aus", `"Removed:"`; Vereinigung |
| `ablauf._SYSTEMZEILEN` (512) | `_SYSTEMZEILEN_EN = (r"start\s*clear", r"writing\s+(the|your)\s+scene\s+(now|out)\b", r"us[- ]?server", r"us[- ]?model.*\?", r"\bswitzerland\b.*\bus\b|\bus\b.*\bswitzerland\b")` — **an die tatsaechlichen englischen Texte** aus Aufgabe 16 anpassen; Vereinigung |
| `szenenfolge._PRUEFVERMERK_ANFANG` (690) ↔ `PRUEFVERMERK` → `zu_pruefen` (725) | `PRUEFVERMERK` laeuft seit Aufgabe 16 ueber `T`; `zu_pruefen` erkennt **beide** Anfaenge (alte deutsche Eintraege im Journal bleiben) |
| `szene._regienotizen` (1630/1641) | Marke `"Szene {nummer}"` **oder** `"Scene {nummer}"` |
| `dramaturgie/fanout.synopsen_fehlen` (907/934) | `^(Szene|Scene) (\d+)` — die Synopsen baut der Code selbst, ueber `T` |

- [ ] **Schritt 1: Tests** (anhaengen):

```python
from interview_theater import kontext


def test_jeder_englische_systemanfang_steht_in_der_tabelle():
    """Rundreise: der Anfang muss zu einem englischen Text passen, sonst
    erkennt der Code seine eigene Zeile nicht wieder."""
    sprache.vergiss()
    werte = []
    for eintraege in sprache.tabelle("en").values():
        for wert in eintraege.values():
            if isinstance(wert, str):
                werte.append(wert.lstrip())
    for anfang in kontext._SYSTEMANFAENGE_EN:
        assert any(w.startswith(anfang) for w in werte), anfang


def test_englische_notiert_zeile_faellt_aus_dem_fenster():
    assert kontext._ist_systemzeile({"ist_bot": 1, "text": "Noted:\n- Terms: love"})
    assert kontext._ist_systemzeile({"ist_bot": 1, "text": "Notiert:\n- Begriffe: Liebe"})
    assert not kontext._ist_systemzeile({"ist_bot": 0, "text": "Noted: we agree"})


def test_erfundene_englische_systemzeile():
    assert ablauf.ist_erfundene_systemzeile("I'm writing the scene now.")
    assert ablauf.ist_erfundene_systemzeile("Ich schreibe die Szene jetzt aus.")
    assert not ablauf.ist_erfundene_systemzeile("I like how the scene ends.")
```

  (`"I'm writing the scene now."` muss zum englischen
  `szene._TEXT_ANGEKUENDIGT` passen — den Testsatz an den in Aufgabe 16
  gewaehlten Wortlaut angleichen.)
- [ ] **Schritt 2–4:** rot, umsetzen, gruen
  (`tests/test_sprache_parser.py tests/test_kontext.py tests/test_ablauf.py tests/test_szenenfolge.py tests/test_szene*.py tests/test_dramaturgie*.py tests/test_sprache_bitgleich.py`).
- [ ] **Schritt 5: Mutationsnachweis:** den englischen Eintrag
  `bot._TEXT_WIEDERKEHR` in `texte.toml` umformulieren (`"Back again. …"`) →
  `test_jeder_englische_systemanfang_steht_in_der_tabelle` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Eigene Systemzeilen auch auf Englisch wiedererkennen (A1)"`.

---

## Aufgabe 25: E8 im Code — Pseudonyme statt Vornamen, Interviewnummern statt Aufnahmenamen (D6)

„Ein Modell kann keinen Namen verwenden, den es nie sieht." Der Prompt
bekommt die Regel (Aufgabe 18/19/20), der **Code** sorgt dafuer, dass kein
Vorname und kein Aufnahmename im Prompt steht — sobald das Profil
`datenschutz.pseudonyme = true` traegt (Padua). Dortmund bleibt bitgleich.

**Files:**
- Modify: `interview_theater/repo.py` (neu `absender_in_reihenfolge`)
- Modify: `interview_theater/kontext.py:231–248` (`sprecherzeile`), neu
  `pseudonyme`, `_PSEUDONYM`, `_PSEUDONYM_UNBEKANNT`; Aufrufer `:962/965`
  (`waehle_fenster`), `:1073` (`_baue_fenster_eintraege`), `:1105`
  (`_baue_ausloeser`); `:336` (`_baue_transkripte`, Aufnahmename)
- Modify: `interview_theater/erkenner.py:254–266` (`_nachrichten_text`,
  `_baue_nutzertext`)
- Modify: `interview_theater/journal.py:135/171/190–192`
  (`berechne_verdraengten_abschnitt`, `_ausschnitt_text` und ihre Aufrufer)
- Modify: `interview_theater/aufnahme.py` (neu `anzeigename`; Stellen
  539/541, 903, 1025, 1052, 1103, 1173, 1331)
- Modify: `interview_theater/phasentexte.py:216–218` (`_interviews`),
  `befehle.py:195–199` (`_wortlaut_liste`), `:294–301` (`/auswerten`),
  `knoepfe/wirkung.py` (Stellen mit `kopf["name"]`, gemessen 1008/1133/1170)
- Create: `tests/test_pseudonyme.py` (`tests/fixture_sprache.py` hat
  Aufgabe 17 schon angelegt — der Code steht unten in Schritt 1, weil er
  hier fachlich hingehoert: die Absenderspalte ist der Gegenstand von E8)

**Interfaces:**
- Produces: `repo.absender_in_reihenfolge(conn, chat_id) -> list[str]`;
  `kontext.pseudonyme(conn, chat_id, zeilen=()) -> dict[str, str] | None`
  (`None` = Profil will keine Pseudonyme → altes Verhalten);
  `kontext.sprecherzeile(n, namen: dict[str, str] | None = None) -> str`;
  `erkenner._nachrichten_text(nachrichten, vorlauf=None, namen=None)`;
  `journal._ausschnitt_text(verdraengt, namen=None)`,
  `journal.berechne_verdraengten_abschnitt(nachrichten, namen=None)`;
  `aufnahme.anzeigename(conn, row, ersatz: str) -> str`;
  `tests.fixture_sprache.ABSENDER = ("Giulia", "Tomasz", "Amara")`,
  `AUFNAHMENAME = "Rosa"`, `baue_englische_gruppe(conn) -> str` (Token).

- [ ] **Schritt 1: Fixture pruefen** — `tests/fixture_sprache.py` (in
  Aufgabe 17 angelegt; steht sie noch nicht da, jetzt so anlegen):

```python
"""Eine erfundene, englischsprachige Gruppe fuer die Sprachtests (Karte A1).

Alle Namen sind erfunden und stammen nicht aus dem Projektumfeld. Die
Absendernamen sind absichtlich ungewoehnlich genug, dass ein Teilstring-Test
sie in keinem Prompttext zufaellig findet.
"""

from datetime import datetime, timedelta, timezone

from interview_theater import repo

ABSENDER = ("Giulia", "Tomasz", "Amara")
AUFNAHMENAME = "Rosa"
_BASIS = datetime(2026, 10, 5, 9, 0, 0, tzinfo=timezone.utc)


def _zeit(minuten: int) -> str:
    return (_BASIS + timedelta(minutes=minuten)).isoformat(timespec="seconds")


def baue_englische_gruppe(conn, chat_id: int = 1) -> str:
    repo.sichere_gruppe(conn, chat_id, "gruppe1", "Test group")
    stand = {
        "begriffe": "belonging, family, noise, courage",
        "fragen": "1. Where do you feel at home?\n2. Who do you argue with?\n3. What gives you courage?",
        "interview_eroeffnung": "Hi, we are a youth theatre group making a play about this city.",
        "interview_abschluss": "Thank you - your story will become part of a scene.",
        "rahmen": "A bus stop at night, two sisters wait for the last bus.",
        "geschichte": "Nadia wants to leave, Tomas wants her to stay. In the end she stays one more night.",
    }
    for feld, wert in stand.items():
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    repo.setze_figur(conn, chat_id, "Nadia", "the older sister, restless")
    repo.setze_figur(conn, chat_id, "Tomas", "the younger brother, stubborn")
    repo.setze_phase(conn, chat_id, 6)
    for nummer, (titel, text) in enumerate([
        ("Last bus", "NADIA: I'm going.\nTOMAS: You always say that."),
        ("One more night", "TOMAS: Stay.\nNADIA: One night. Then we'll see."),
    ], start=1):
        repo.lege_szene_an(conn, chat_id, nummer, titel, None, text)
    # Wie tests/fixture_spaetstand.py: quelle "sprache", status gleich "fertig".
    aufnahme_id = repo.lege_aufnahme_an(conn, chat_id, 10, "lang", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "Allora, I grew up above a bakery. Home is the smell of bread.")
    repo.setze_aufnahme_name(conn, aufnahme_id, AUFNAHMENAME)
    repo.speichere_verdichtung(conn, chat_id, aufnahme_id, "She talks about home and the bakery.", [
        {"thema": "home", "beleg_zitat": "Home is the smell of bread.", "zitat_geprueft": 1, "kurz": "home"},
    ])
    message_id = 100
    for runde in range(6):
        for absender in ABSENDER:
            message_id += 1
            repo.merke_nachricht(conn, chat_id, message_id, absender, 0, "text",
                                 f"Idea number {runde}: the bus is late again.",
                                 _zeit(message_id))
        message_id += 1
        repo.merke_nachricht(conn, chat_id, message_id, "gruppe1", 1, "text",
                             "Noted. What happens when the bus finally comes?", _zeit(message_id))
    return repo.stelle_web_token_sicher(conn, chat_id)
```

  (Signaturen am Code geprueft: `repo.sichere_gruppe` :86, `setze_arbeitsstand`
  :1645, `setze_figur` :1827, `setze_phase` :1689, `lege_szene_an` :2066,
  `lege_aufnahme_an` :409 (mit `status=`, wie `tests/fixture_spaetstand.py`),
  `setze_transkript` :567, `setze_aufnahme_name` :576,
  `speichere_verdichtung` :705, `merke_nachricht` :168,
  `stelle_web_token_sicher` :124. Die Nachrichtentexte nennen **keinen**
  Absendernamen: geprueft wird die Absenderspalte. Ein Name, den die Gruppe
  selbst in den Text schreibt, ist Inhalt der Gruppe — das regelt der
  Prompt (E8-Satz), nicht der Code.)

- [ ] **Schritt 2: Tests** — `tests/test_pseudonyme.py`:

```python
"""E8: in Padua sieht kein Prompt einen Vornamen oder Aufnahmenamen (D6)."""

import pytest

from interview_theater import aufnahme, erkenner, journal, kontext, repo, sprache, workshop
from tests.fixture_sprache import ABSENDER, AUFNAHMENAME, baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _ohne_namen(text: str) -> list[str]:
    return [n for n in (*ABSENDER, AUFNAHMENAME) if n in text]


def test_gespraechsprompt_ohne_namen(conn, einst, padua):
    baue_englische_gruppe(conn)
    ausloeser = repo.letzte_nachrichten(conn, 1)[-2:]
    text = kontext.baue(conn, 1, ausloeser, einst)
    assert _ohne_namen(text) == []
    assert "Member 1:" in text


def test_pseudonyme_sind_stabil_nach_erstem_auftreten(conn, padua):
    baue_englische_gruppe(conn)
    assert kontext.pseudonyme(conn, 1) == {
        "Giulia": "Member 1", "Tomasz": "Member 2", "Amara": "Member 3"}


def test_erkenner_und_journal_ohne_namen(conn, padua):
    baue_englische_gruppe(conn)
    zeilen = repo.unextrahierte(conn, 1)
    assert _ohne_namen(erkenner._baue_nutzertext(conn, 1, zeilen)) == []
    namen = kontext.pseudonyme(conn, 1)
    assert _ohne_namen(journal._ausschnitt_text(zeilen, namen)) == []


def test_wortlaut_zeigt_interviewnummer_statt_aufnahmename(conn, einst, padua):
    baue_englische_gruppe(conn)
    repo.setze_wortlaut_modus(conn, 1, "*")
    text = kontext.baue(conn, 1, repo.letzte_nachrichten(conn, 1)[-1:], einst)
    assert AUFNAHMENAME not in text
    assert "Interview 1" in text


def test_aufnahme_texte_nennen_die_nummer(conn, padua):
    baue_englische_gruppe(conn)
    zeile = [a for a in repo.transkripte(conn, 1) if a["klasse"] == "lang"][0]
    assert aufnahme.anzeigename(conn, zeile, "The interview") == "Interview 1"


def test_dortmund_behaelt_die_vornamen(conn, einst):
    """Bitgleich: ohne Pseudonym-Schalter bleibt der Verlauf, wie er war."""
    baue_englische_gruppe(conn)
    text = kontext.baue(conn, 1, repo.letzte_nachrichten(conn, 1)[-2:], einst)
    assert "Giulia:" in text
    assert kontext.pseudonyme(conn, 1) is None
    zeile = [a for a in repo.transkripte(conn, 1) if a["klasse"] == "lang"][0]
    assert aufnahme.anzeigename(conn, zeile, "Das Interview") == AUFNAHMENAME
```

- [ ] **Schritt 3: Rot sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_pseudonyme.py`
Expected: FAIL — `AttributeError: … has no attribute 'pseudonyme'`, dann
`assert ['Giulia', 'Tomasz', 'Amara'] == []`.

- [ ] **Schritt 4: Umsetzen**

`repo.py` (bei den Nachrichten-Lesern, nach `letzte_nachrichten` :321):

```python
@_gesperrt
def absender_in_reihenfolge(conn: sqlite3.Connection, chat_id: int) -> list[str]:
    """Die Absendernamen der Gruppe (ohne Bot) in der Reihenfolge ihres
    ersten Auftretens -- die Grundlage stabiler Pseudonyme (E8, Karte A1).
    ``telegram_user`` wird nie geschrieben (db.py:45), also bleibt der
    Vorname der einzige Schluessel."""
    zeilen = conn.execute(
        "SELECT absender, MIN(gesendet_am) AS zuerst FROM nachricht "
        "WHERE chat_id = ? AND ist_bot = 0 AND absender IS NOT NULL AND absender != '' "
        "GROUP BY absender ORDER BY zuerst, absender",
        (chat_id,),
    ).fetchall()
    return [z["absender"] for z in zeilen]
```

`kontext.py` (Konstanten bei `_SPRECHER_BOT`, Aufgabe 15):

```python
#: Wie ein Mitglied der Gruppe im Prompt heisst, wenn das Profil Pseudonyme
#: verlangt (E8, Karte A1). In Dortmund nie benutzt -- die deutsche Tabelle
#: braucht trotzdem einen Wert.
_PSEUDONYM = "Mitglied {nummer}"
_PSEUDONYM_UNBEKANNT = "Mitglied"


def pseudonyme(conn, chat_id: int, zeilen=()) -> dict[str, str] | None:
    """{Vorname: "Member N"} nach erstem Auftreten, oder None, wenn das
    Profil keine Pseudonyme verlangt (dann bleibt alles, wie es war).
    ``zeilen`` ergaenzt Namen, die (noch) nicht in der Datenbank stehen --
    der Korpuslauf fuettert den Erkenner mit Zeilen ohne DB (pruefe_prompts)."""
    if not sprache.pseudonyme():
        return None
    namen = list(repo.absender_in_reihenfolge(conn, chat_id))
    for n in zeilen:
        absender = n["absender"]
        if not n["ist_bot"] and absender and absender not in namen:
            namen.append(absender)
    return {name: T._PSEUDONYM.format(nummer=i) for i, name in enumerate(namen, start=1)}


def sprecherzeile(n, namen: dict[str, str] | None = None) -> str:
    """… (bisheriger Text) …

    ``namen`` (E8, Karte A1): steht dort ein Mapping, ersetzt es den
    Vornamen; ein Name, der darin fehlt, wird nie durchgereicht, sondern
    heisst "Member". ``None`` ist das alte Verhalten."""
    if n["ist_bot"]:
        sprecher = T._SPRECHER_BOT
    elif namen is None:
        sprecher = n["absender"]
    else:
        sprecher = namen.get(n["absender"], T._PSEUDONYM_UNBEKANNT)
    text = n["text"]
    if text:
        return f"{sprecher}: {text}"
    return f"{sprecher}: ({n['typ']})"
```

  Jeder Aufrufer bildet `namen = pseudonyme(conn, chat_id, <seine Zeilen>)`
  **einmal** und reicht es durch (`waehle_fenster` auch fuer die
  Laengenmessung — sonst schneidet das Fenster in Padua an einer anderen
  Stelle als es misst). `_baue_transkripte` (:336):
  `name = interviewbezeichnung(conn, chat_id, a["id"]) if sprache.pseudonyme() else a["name"]`.
  `erkenner._baue_nutzertext`: `namen = kontext.pseudonyme(conn, chat_id,
  list(nachrichten) + ([vorlauf] if vorlauf is not None else []))`, dann
  `_nachrichten_text(nachrichten, vorlauf, namen)`. `journal`: der Aufrufer
  von `_ausschnitt_text`/`berechne_verdraengten_abschnitt` hat `conn`/`chat_id`
  (`grep -n "_ausschnitt_text\|berechne_verdraengten_abschnitt" interview_theater/*.py`).

  `aufnahme.py`:

```python
def anzeigename(conn, row, ersatz: str) -> str:
    """Wie eine Aufnahme in einem Bot-Text heisst (E8, Karte A1): in einem
    Profil mit Pseudonymen immer "Interview N" -- ein Aufnahmename ist oft
    ein Klarname ("das war Marias Interview") oder der Telegram-Name dessen,
    der das Handy hielt, und Bot-Texte kommen als "Du:"-Zeilen zurueck in
    jedes Fenster. Sonst wie bisher: der Name oder ``ersatz``."""
    if sprache.pseudonyme():
        from interview_theater import kontext

        return kontext.interviewbezeichnung(conn, row["chat_id"], row["id"]) or ersatz
    return row["name"] or ersatz
```

  An den gemessenen Stellen (539/541, 903, 1025, 1052, 1103, 1173, 1331)
  ersetzt `anzeigename(conn, row_oder_kopf, T._TEXT_DAS_INTERVIEW)` den
  Ausdruck `row["name"] or "Das Interview"` (der Ersatztext „Das Interview"
  bzw. „Interview" wird dabei Konstante, falls Aufgabe 15 es noch nicht
  getan hat). Dasselbe fuer `phasentexte._interviews`,
  `befehle._wortlaut_liste`, `/auswerten` und `knoepfe/wirkung.py`
  (`grep -n 'kopf\["name"\]' interview_theater/knoepfe/wirkung.py`).
  **Nicht** anfassen: `aufnahme.finde_interview` (1308–1313) — das liest,
  was die Gruppe tippt.

- [ ] **Schritt 5: Gruen sehen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_pseudonyme.py tests/test_kontext.py tests/test_erkenner.py tests/test_journal.py tests/test_aufnahme.py tests/test_prompt_audit.py tests/test_kontext_recall.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py`
Expected: alle gruen.

- [ ] **Schritt 6: Mutationsnachweis:** in `sprecherzeile`
  `namen.get(n["absender"], T._PSEUDONYM_UNBEKANNT)` →
  `namen.get(n["absender"], n["absender"])` und in `pseudonyme` `Amara`
  vergessen lassen (`namen = namen[:2]`) → `test_gespraechsprompt_ohne_namen`
  rot mit `['Amara']`. Zuruecksetzen.

- [ ] **Schritt 7:** SUITE; Commit `"E8: Pseudonyme statt Vornamen, Interviewnummer statt Aufnahmename im Prompt (A1)"`.

---

## Aufgabe 26: Zitate im Original — Nachweis an `zitat.pruefe` (D7)

`zitat.pruefe` bleibt **unveraendert** (keine zweite, grosszuegigere
Normalisierung, AGENTS.md). Gemessen am Code: `normalisiere` macht NFC und
setzt `’` auf `'` (zitat.py:18–26), `pruefe` vergleicht als Teilstring
(zitat.py:29–34) — das traegt Italienisch und jede Schrift. Diese Aufgabe
haelt es fest.

**Files:** Test: `tests/test_zitat.py` (anhaengen).

- [ ] **Schritt 1: Tests**

```python
import pytest

from interview_theater import zitat

IT_TRANSKRIPT = "Allora, l’ho detto a mia madre: qui non è casa mia, però ci provo."
UK_TRANSKRIPT = "Я приїхала сюди два роки тому, і ще досі вчу мову."
AR_TRANSKRIPT = "جئت إلى هنا قبل سنتين وما زلت أتعلم اللغة."


@pytest.mark.parametrize("zitat_, transkript, soll", [
    ("l'ho detto a mia madre", IT_TRANSKRIPT, True),          # typografischer Apostroph im Transkript
    ("qui non è casa mia", IT_TRANSKRIPT, True),
    ("I told my mother", IT_TRANSKRIPT, False),                # uebersetzt = kein Beleg
    ("here is not my home", IT_TRANSKRIPT, False),
    ("і ще досі вчу мову", UK_TRANSKRIPT, True),               # Kyrillisch
    ("وما زلت أتعلم اللغة", AR_TRANSKRIPT, True),               # Arabisch
    ("and I am still learning the language", AR_TRANSKRIPT, False),
])
def test_zitate_bleiben_im_original(zitat_, transkript, soll):
    assert zitat.pruefe(zitat_, transkript) is soll
```

- [ ] **Schritt 2:** `$PY -m pytest -q -p no:cacheprovider tests/test_zitat.py`
  → **gruen beim ersten Lauf** (gemessene Erwartung: der Code traegt das
  schon). Rotsehen ersetzt der Mutationsnachweis.
- [ ] **Schritt 3: Mutationsnachweis:** in `zitat._ERSETZUNGEN` den Eintrag
  `"’": "'"` entfernen → `test_zitate_bleiben_im_original[l'ho detto…]` rot.
  Zuruecksetzen (`git checkout interview_theater/zitat.py`).
- [ ] **Schritt 4:** SUITE; Commit `"Zitatpruefung: Italienisch, Kyrillisch, Arabisch im Original, Uebersetzung kein Beleg (A1, D7)"`.

---

## Aufgabe 27: Der englische Erkenner-Korpus (D8)

**Files:**
- Create: `korpus/en/erkenner.jsonl`
- Modify: `tests/test_korpus.py` (neuer Block „englischer Korpus")

**Mindestbesetzung (bindend):** ≥ 60 Faelle, davon ≥ 24 Negativfaelle
(`"erwartet": []`); **jede** `art`, die im deutschen Korpus positiv vorkommt
(gemessen 24: `an_den_bot`, `begriffe_setzen`, `entfernen`, `entschieden`,
`festlegung_setzen`, `figur_quelle_setzen`, `figur_setzen`, `format_setzen`,
`fragen_setzen`, `hauptkonflikt_setzen`, `interview_beenden`,
`interview_benennen`, `interview_starten`, `kernthema_setzen`,
`phase_setzen`, `rahmen_setzen`, `szene_kuerzen`, `szene_planen`,
`szene_schreiben`, `szene_usa`, `transkript_korrigieren`, `verworfen`,
`wortlaut_an`, `wortlaut_aus`), mindestens einmal positiv; ≥ 3 Faelle aus
einer laufenden Aufnahme (Feld `aufnahme` statt `nachrichten`, erwartet nur
`ARTEN_IN_AUFNAHME` = `interview_beenden`, `interview_benennen`,
`an_den_bot`), ≥ 5 mit `"zustimmung": true`, ≥ 2 mit italienischen
Einsprengseln in sonst englischer Gruppe. Ids mit Praefix `en-`. **Alle
Namen erfunden**, nicht aus dem Projektumfeld; Absender duerfen Vornamen
tragen (so sieht es der Code, bevor Aufgabe 25 sie pseudonymisiert —
`pruefe_prompts` laeuft durch denselben Weg). Format wie
`korpus/erkenner.jsonl` (Felder `id`, `arbeitsstand`, `nachrichten`
bzw. `aufnahme`, `erwartet`, `notiz`, optional `vorlauf`, `zustimmung`).

**Beispielzeilen (so, in dieser Form):**

```json
{"id": "en-e01-interview-starten", "arbeitsstand": {}, "nachrichten": [{"absender": "Lina", "text": "ok she's here now"}, {"absender": "Lina", "text": "we're starting the interview"}], "erwartet": [{"art": "interview_starten", "wert": ""}], "notiz": "Gegenstueck zu e01, Kanarienvogel auf Englisch."}
{"id": "en-n01-interview-nur-erwaehnt", "arbeitsstand": {}, "nachrichten": [{"absender": "Jonas", "text": "the interview yesterday was really long"}, {"absender": "Mei", "text": "yeah but good"}], "erwartet": [], "notiz": "Negativ: ueber ein Interview reden ist kein Start."}
{"id": "en-z01-begriffe-zustimmung-italienisch", "arbeitsstand": {}, "vorlauf": "VORSCHLAG BEGRIFFE:\nbelonging, family, noise, courage", "nachrichten": [{"absender": "Chiara", "text": "va bene, perfetto, take those"}], "erwartet": [{"art": "begriffe_setzen", "wert": "belonging"}], "zustimmung": true, "notiz": "Zustimmung mit italienischem Einsprengsel (Padua)."}
{"id": "en-a01-aufnahme-an-den-bot", "arbeitsstand": {}, "aufnahme": "hey bot, can you show us the summaries so far?", "erwartet": [{"art": "an_den_bot", "wert": ""}], "notiz": "N4 auf Englisch: Frage an den Bot mitten im Interview."}
{"id": "en-a02-aufnahme-material", "arbeitsstand": {}, "aufnahme": "and then my father said, show me your hands, and I showed him", "erwartet": [], "notiz": "Negativ: Imperativ im Interviewinhalt ist keine Frage an den Bot."}
```

- [ ] **Schritt 1: Tests** (in `tests/test_korpus.py` anhaengen; nutzt
  `ist_aufnahmefall`, `texte_von`, `erkenner` aus der Datei):

```python
KORPUS_EN = KORPUS / "en"
MIN_EN = 60
MIN_EN_NEGATIV = 24
MIN_EN_AUFNAHME = 3
MIN_EN_ZUSTIMMUNG = 5
MIN_EN_ITALIENISCH = 2
ITALIENISCH = ("va bene", "perfetto", "allora", "dai", "grazie", "basta", "andiamo", "sì", "certo")
#: Namen aus dem Projektumfeld, die im Korpus nie stehen duerfen.
NICHT_ERLAUBT = {"Birk", "Nina"}


@pytest.fixture(scope="module")
def en_faelle():
    zeilen = (KORPUS_EN / "erkenner.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(z) for z in zeilen if z.strip()]


def test_en_ids_eindeutig_mit_praefix(en_faelle):
    ids = [f["id"] for f in en_faelle]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("en-") for i in ids)


def test_en_mindestbesetzung(en_faelle):
    assert len(en_faelle) >= MIN_EN
    assert sum(1 for f in en_faelle if not f["erwartet"]) >= MIN_EN_NEGATIV
    assert sum(1 for f in en_faelle if ist_aufnahmefall(f)) >= MIN_EN_AUFNAHME
    assert sum(1 for f in en_faelle if f.get("zustimmung")) >= MIN_EN_ZUSTIMMUNG
    italienisch = [f for f in en_faelle if any(w in t for t in texte_von(f) for w in ITALIENISCH)]
    assert len(italienisch) >= MIN_EN_ITALIENISCH


def test_en_jede_deutsch_belegte_art_positiv(erkenner_faelle, en_faelle):
    deutsch = {a["art"] for f in erkenner_faelle for a in f["erwartet"]}
    englisch = {a["art"] for f in en_faelle for a in f["erwartet"]}
    assert sorted(deutsch - englisch) == []


def test_en_form_wie_der_deutsche_korpus(en_faelle):
    for fall in en_faelle:
        assert fall.get("notiz", "").strip(), fall["id"]
        assert isinstance(fall.get("arbeitsstand"), dict), fall["id"]
        for aenderung in fall["erwartet"]:
            assert aenderung["art"] in erkenner.ARTEN, fall["id"]
            assert isinstance(aenderung.get("wert"), str), fall["id"]
        if ist_aufnahmefall(fall):
            assert "nachrichten" not in fall, fall["id"]
            assert all(a["art"] in erkenner.ARTEN_IN_AUFNAHME for a in fall["erwartet"]), fall["id"]
        else:
            assert fall["nachrichten"] and all(n.get("absender") and n.get("text") for n in fall["nachrichten"])


def test_en_keine_namen_aus_dem_projektumfeld(en_faelle):
    for fall in en_faelle:
        text = json.dumps(fall, ensure_ascii=False)
        assert not [n for n in NICHT_ERLAUBT if n in text], fall["id"]


def test_deutscher_korpus_unveraendert_gezaehlt(erkenner_faelle):
    """D8: der deutsche Korpus bleibt, wie er ist (150 Faelle, 53 negativ,
    gemessen 30.09.2026) -- seine FP=0-Zusage haengt an genau diesen Faellen."""
    assert len(erkenner_faelle) == 150
    assert sum(1 for f in erkenner_faelle if not f["erwartet"]) == 53
```

  (Die deutschen Zahlen 150/53 sind gemessen:
  `python3.11 -c "import json; …"` aus AGENTS.md, „Prompt geaendert?".)
- [ ] **Schritt 2:** rot: `FileNotFoundError: …/korpus/en/erkenner.jsonl`.
- [ ] **Schritt 3:** Korpus schreiben. Vorgehen: fuer jede der 24 Arten
  mindestens einen Positivfall (wo der deutsche Korpus einen gemessenen
  Grenzfall hat — n20/n27/fl04 bei `szene_kuerzen`, e18 bei `verworfen` —
  einen englischen Gegenfall dazu); 24+ Negativfaelle aus den Mustern des
  deutschen Korpus (Erwaehnen statt Beschliessen, Frage statt Festlegung,
  Kritik statt Auftrag, Interviewinhalt im Imperativ); die zwei
  italienischen Einsprengsel in Zustimmungsfaellen. Keine Uebersetzung
  Satz fuer Satz: die Faelle muessen klingen, wie eine englisch schreibende
  Gruppe schreibt.
- [ ] **Schritt 4:** gruen: `$PY -m pytest -q -p no:cacheprovider tests/test_korpus.py`.
- [ ] **Schritt 5: Mutationsnachweis:** den einzigen `wortlaut_aus`-Fall
  loeschen → `test_en_jede_deutsch_belegte_art_positiv` rot.
- [ ] **Schritt 6:** SUITE; Commit `"Englischer Erkenner-Korpus: 60+ Faelle, alle Arten, italienische Einsprengsel (A1, D8)"`.

---

## Aufgabe 28: `pruefe_prompts --sprache en` (D8, W12)

**Files:** Modify `scripts/pruefe_prompts.py:78` (`KORPUS`), `:407–427`
(`lade_korpus`), `:868–874` (`berichtspfad`), `:877–891`
(`baue_argumente`), `:894–964` (`main`); Test `tests/test_pruefe_prompts.py`.

**Interfaces:** `lade_korpus(name, nur=None, sprache="de")` liest bei
`"en"` `korpus/en/<name>.jsonl`; `baue_argumente` kennt
`--sprache {de,en}` (Vorgabe `de`) und `--workshop <name>`;
`berichtspfad(angabe, prompts, sprache="de")` haengt `-en` an den
Dateinamen. `--sprache en` erlaubt **nur** `erkenner` (sonst
`SystemExit("--sprache en gibt es nur fuer den Erkenner (D8) …")`), setzt
`IT_WORKSHOP` auf `--workshop` bzw. `padua-2026`, ruft `workshop.vergiss()`
und bricht ab, wenn `sprache.code() != "en"`.

- [ ] **Schritt 1: Tests** (anhaengen):

```python
import pytest

from scripts import pruefe_prompts


def test_sprache_en_liest_den_englischen_korpus():
    faelle = pruefe_prompts.lade_korpus("erkenner", sprache="en")
    assert faelle and all(f["id"].startswith("en-") for f in faelle)


def test_deutsch_bleibt_vorgabe():
    args = pruefe_prompts.baue_argumente(["erkenner"])
    assert args.sprache == "de"
    assert pruefe_prompts.lade_korpus("erkenner")[0]["id"].startswith("e01")


def test_sprache_en_nur_fuer_den_erkenner():
    with pytest.raises(SystemExit):
        pruefe_prompts.main(["journal", "--sprache", "en"])


def test_bericht_traegt_die_sprache(tmp_path):
    assert pruefe_prompts.berichtspfad(None, ["erkenner"], sprache="en").name.endswith("-erkenner-en.md")
```

  (`test_sprache_en_nur_fuer_den_erkenner` muss **vor** `einstellungen.laden()`
  abbrechen — die Pruefung steht deshalb in `main` direkt nach
  `baue_argumente`, ohne Netz, ohne Env.)
- [ ] **Schritt 2–4:** rot (`TypeError: … unexpected keyword 'sprache'`),
  umsetzen, gruen: `$PY -m pytest -q -p no:cacheprovider tests/test_pruefe_prompts.py`.
- [ ] **Schritt 5: Mutationsnachweis:** in `lade_korpus` den Sprachpfad
  ignorieren → `test_sprache_en_liest_den_englischen_korpus` rot.
- [ ] **Schritt 6:** SUITE; Commit `"pruefe_prompts: --sprache en fuer den englischen Erkenner-Korpus (A1)"`.

---

## Aufgabe 29: Padua minimal englisch (D9)

**Files:** `workshop/padua-2026/profil.toml`, `phasen.toml`,
`phasentexte.toml`, `formen.toml`, `LIESMICH.md`;
`tests/test_profile_geruest.py:64–68, 85–95`.

- [ ] **Schritt 1: Tests anpassen** (`tests/test_profile_geruest.py`, oben
  `import re` ergaenzen):

```python
def test_padua_ist_ein_geruest():
    """Karte P entfernt die Zeile -- bis dahin startet kein Bot damit."""
    profil = workshop.lade("padua-2026")
    assert profil.geruest()


def test_padua_traegt_nur_platzhalter_fuer_den_inhalt():
    """A1 setzt die Methode (Sprache, Phasen, Formen), Karte P den Inhalt aus
    Birks Vault. Jede Inhaltszeile traegt deshalb den Marker."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "prompts").exists(), "Rahmen-Vorlagen liegen in der Sprachschicht (W1)"
    assert not (verz / "korpus").exists(), "der englische Korpus liegt unter korpus/en/ (D8)"
    text = (verz / "profil.toml").read_text(encoding="utf-8")
    inhalt = [z for z in text.splitlines() if re.match(
        r"^(beschreibung|traeger|ausgeschlossen|auffuehrung|erlaubt|kurzbeschreibung)\s*=", z.strip())]
    # beschreibung (oben), zielgruppe.beschreibung, traeger, orte.beschreibung,
    # orte.ausgeschlossen, auffuehrung, konflikt.erlaubt,
    # konflikt.ausgeschlossen, projekt.kurzbeschreibung
    assert len(inhalt) == 9
    assert all("ANNAHME (Platzhalter A1" in z for z in inhalt), inhalt


def test_padua_phasen_und_formen_englisch():
    profil = workshop.lade("padua-2026")
    assert [n for _, n, _ in workshop.phasenliste(profil)] == [
        "Terms", "Questions", "Interviews", "Setting, Characters & Story",
        "Sharpening", "Scenes as Story", "Polish"]
    assert workshop.form_anzeige(profil) == ("Dialogue", "Monologue", "Chorus", "Song", "Rap")
    assert workshop.formen(profil) == ("dialog", "monolog", "chor", "lied", "rap")
```

  und `test_die_pruefung_weist_ein_geruest_ab` behaelt seine Zusicherung
  (Exit 1, „Geruest" in der Ausgabe).
- [ ] **Schritt 2: Rot sehen** — `$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py`
  → `test_padua_phasen_und_formen_englisch` rot (`['Begriffe', …]`).
- [ ] **Schritt 3: Dateien schreiben**

`workshop/padua-2026/profil.toml` (Kopfkommentar anpassen: „A1 hat Sprache,
Phasen und Formen gesetzt; die Inhaltsfelder sind Platzhalter, Karte P
ersetzt sie aus Birks Vault. `geruest = true` streicht Karte P."):

```toml
geruest = true

beschreibung = "Theatre workshop in Padua, October 2026."   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)

[sprache]
code = "en"
anrede = "you"
whisper = "auto"

[datenschutz]
pseudonyme = true

[zielgruppe]
beschreibung = "young people taking part in this workshop"   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
traeger = "the workshop partner in Padua"                      # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)

[orte]
beschreibung = "everyday, age-appropriate places from the group's own world -- the group decides which (no example places from these instructions)."   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
ausgeschlossen = ["club", "disco", "alcohol", "nightlife", "drugs"]   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
auffuehrung = "in a public space or a large hall"                     # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
beispiele = ["fermata", "piazza", "bar", "stazione"]

[konflikt]
erlaubt = "family, expectations, belonging, language, future"   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
ausgeschlossen = "No glorification of violence."                 # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)

[projekt]
kurzbeschreibung = "a piece of theatre about the lives of people in this city; the people we interview are experts on life here, and their personal stories become visible on stage"   # ANNAHME (Platzhalter A1, Karte P ersetzt aus dem Vault)
```

`workshop/padua-2026/phasen.toml`:

```toml
# Die Arbeitsphasen fuer Padua 2026 (Karte A1): dieselben sieben Stationen
# wie in Dortmund -- die Methode, nicht der Einsatzort --, englisch benannt.
erste = 1
meldung = "We're now at {bezeichnung}. If that's not right, tell me."

[[phase]]
nummer = 1
name = "Terms"
satz = "Take in and sort the list of terms collected in the plenary."
stichwoerter = ["terms", "term", "term list", "keywords"]

[[phase]]
nummer = 2
name = "Questions"
satz = "Develop interview questions from the terms."
# "interview questions" bewusst nicht: der Vergleich laeuft in beide
# Richtungen, "interview" waere darin enthalten (wie im Deutschen).
stichwoerter = ["questions", "question", "question list"]

[[phase]]
nummer = 3
name = "Interviews"
satz = "Conduct the interviews, summarise the material."
stichwoerter = ["interviews", "interview", "recordings"]

[[phase]]
nummer = 4
name = "Setting, Characters & Story"
satz = "Invent freely: where it is set, who is in it, what happens."
stichwoerter = ["setting", "characters", "character", "frame", "core theme",
                "format", "conflict", "story", "plot", "outline"]

[[phase]]
nummer = 5
name = "Sharpening"
satz = "Sharpen the invented story against the interview material."
stichwoerter = ["sharpening", "sharpen", "clustering", "summaries"]

[[phase]]
nummer = 6
name = "Scenes as Story"
satz = "Tell each scene as prose -- what happens, still without a form."
stichwoerter = ["scene texts", "scene text", "scenes", "scene"]

[[phase]]
nummer = 7
name = "Polish"
satz = "Choose the form of each scene, translate the story into it, check the play."
stichwoerter = ["run-through", "polish", "play check", "review round"]
```

`workshop/padua-2026/phasentexte.toml` (Regeln aus der Datei gelten: zwei
bis vier Saetze, ≤ 700 Zeichen, keine Eigennamen, keine Slash-Befehle,
Anrede „you"):

```toml
letzte_offen = """\
Here is your script in one piece. Some of the scenes are not written yet - \
tap one of them and I'll catch up. In the finished ones we look at the \
transitions and at whatever feels awkward to say out loud."""

[einleitung]
1 = """\
This is where your list of terms from the plenary comes to me. Send it typed \
or as a voice message, just as it is on your wall. I keep it, sort it and ask \
where a term is still too big. At the end you have the core terms you will \
keep working with."""
2 = """\
Now your terms become interview questions. I suggest ten, you tell me the \
numbers of exactly three. Then we look at which question is sensitive and how \
to ask it so it is easy to answer, and how you start and end a conversation. \
At the end you have an interview guide to take with you."""
3 = """\
Now you do the interviews - you have the guide with you. Tap Start interview, \
then record the conversation as voice messages, as many as you need. I type \
everything up. At the end tap End interview (or say "done" at the end of the \
recording), and I summarise the interview by myself - the themes and the \
word-for-word quotes we will work with later."""
4 = """\
From here on we invent - freely, without material. You decide where your play \
is set (place, time, occasion), who is in it, and what happens: the story in \
outline, how it ends, and the sequence of scenes with a title, one sentence, \
the characters and a suggested form. I help with suggestions if you want. \
Right after that the interviews come in and sharpen what you have built."""
5 = """\
Now the interviews come back. Next to every scene and every character I put \
the passages from your recordings that fit, with the word-for-word quote. \
Your story does not change, it gets more precise. You decide suggestion by \
suggestion and can go another round."""
6 = """\
Now I write your story in one piece - a short story, like in a book: what \
happens, who is there, what is said and felt, in prose. The story decides how \
many sections it gets. Each section then becomes a scene. No stage text, no \
form yet; that comes in the polish. You read it and tell me what should change."""
7 = """\
All scenes are there as a story. Now the polish: scene by scene you choose the \
form - {{formen_liste_oder}} - and I translate the story into exactly that \
form. Then I read your play once as a whole, like an audience, and tell you \
where it holds and where it doesn't. You can get the script as a file at any time."""
```

  (Laenge je Einleitung vor dem Commit messen:
  `$PY -c "import tomllib;d=tomllib.load(open('workshop/padua-2026/phasentexte.toml','rb'));print({k: len(v) for k, v in d['einleitung'].items()})"`
  — jede ≤ 700 (`phasentexte.EINLEITUNG_GRENZE`); Einleitung 3 kuerzen,
  falls noetig.)

`workshop/padua-2026/formen.toml`:

```toml
# Der Formen-Katalog fuer Padua (Karte A1): dieselben fuenf Formen wie in
# Dortmund, englisch angezeigt. "name" ist der Datenbankwert und bleibt.
vorgabe = "dialog"
anzahl_wort = "five"

[[form]]
name = "dialog"
anzeige = "Dialogue"
stichwoerter = ["dialogue", "dialog", "conversation", "spoken", "spoken theatre", "text", "scene"]

[[form]]
name = "monolog"
anzeige = "Monologue"
stichwoerter = ["monologue", "monolog", "solo"]

[[form]]
name = "chor"
anzeige = "Chorus"
stichwoerter = ["chorus", "choir", "choral", "we-form", "speaking choir"]

[[form]]
name = "lied"
anzeige = "Song"
stichwoerter = ["song", "sung", "singing", "sing", "music", "aria"]

[[form]]
name = "rap"
anzeige = "Rap"
stichwoerter = ["rap", "beat", "rhyme", "hip-hop", "hiphop", "spoken word"]
```

  (Wie in Dortmund steht „scene" bei Dialog zuletzt geprueft — das Wort
  steht in fast jeder Formangabe, und Dialog ist der Rueckfall.)

`workshop/padua-2026/LIESMICH.md` neu schreiben (Pflicht: >500 Zeichen, das
Wort „eigenstaendig" — `test_jedes_profil_hat_ein_liesmich`): Stand
30.09.2026; was A1 gesetzt hat (Sprache `en`, Whisper `auto` mit Knopf in
Phase 3, Pseudonyme, englische Phasen/Einleitungen/Formen, englische Prompts
und Texte in `interview_theater/sprachen/en/`); was Karte P ersetzt (jede
Zeile mit `ANNAHME (Platzhalter A1`, die Rahmen-Vorlagen, die Pruefung am
Prompt-Dump); was offen bleibt (Journal-/Verdichter-/Sprachprofil-Korpus
englisch, Simulations-Personas, englische Befehlsaliase A4, Web-Feld fuer
die Whisper-Sprache → A2); der alte Satz „Kein Satz hier drin ist von einem
Agenten geschrieben worden" faellt weg, weil er nicht mehr stimmt — mit
Verweis auf Birks Entscheidung vom 29.09.2026.

- [ ] **Schritt 4: Gruen und erwartete Ausgabe**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_workshop.py tests/test_phasen_profil.py tests/test_formen_katalog.py
$PY -m scripts.pruefe_profil padua-2026
$PY -m scripts.pruefe_profil dortmund-2026
```

Expected fuer Padua, **Exit 1**, genau:

```
Workshop-Profil padua-2026
  FEHLER:  Das Profil ist ein Geruest (geruest = true in profil.toml) und damit nicht startbereit. Wer es fertig macht, fuellt die Felder und streicht die Zeile.
padua-2026: 1 Fehler
```

(keine „Leere Pflichtfelder", kein Platzhalter ohne Wert, kein
Zahlwort-Hinweis, kein Rahmen-Hinweis). Dortmund: `dortmund-2026: in Ordnung`.

- [ ] **Schritt 5: Mutationsnachweis:** `anzahl_wort = "four"` →
  `pruefe_profil padua-2026` meldet zusaetzlich den Zahlwort-FEHLER.
  Zuruecksetzen.
- [ ] **Schritt 6:** SUITE; Commit `"Padua englisch: Sprache, Phasen, Einleitungen, Formen, Platzhalter fuer Karte P (A1, D9)"`.

---

## Aufgabe 30: Der Render-Pruefer — Abnahme (3) mechanisch (D10)

**Files:** Modify `scripts/pruefe_sprache.py` (Quellen a–d, Profilmodus,
`nur_text` aus Aufgabe 17 bleibt); Test `tests/test_pruefe_sprache.py`.

**Interfaces:**
- `quellen(profil: str) -> dict[str, list[tuple[str, str]]]` mit den
  Schluesseln `"prompts"` (a), `"texte"` (b), `"durchlauf"` (c: gesendete
  Texte, Knopfbeschriftungen, Einblendungen, Befehlsmenue),
  `"modellprompts"` (c2: System und Nutzer jedes Attrappen-Aufrufs),
  `"web"` (d); Werte `[(quelle, text), …]`.
- `pruefe_profil(profil: str, nur: set[str] | None = None) -> list[Treffer]`.
- CLI: `python -m scripts.pruefe_sprache <profil> [--quelle a,b,…]`.

- [ ] **Schritt 1: Tests** (anhaengen):

```python
import pytest


@pytest.fixture(scope="module")
def padua_quellen():
    return pruefe_sprache.quellen("padua-2026")


@pytest.fixture(scope="module")
def dortmund_quellen():
    return pruefe_sprache.quellen("dortmund-2026")


def test_padua_ist_frei_von_deutsch(padua_quellen):
    treffer = [t for liste in padua_quellen.values() for q, text in liste
               for t in pruefe_sprache.deutsche_treffer(q, text)]
    assert [f"{t.quelle}: {t.wort} | {t.ausschnitt}" for t in treffer] == []


@pytest.mark.parametrize("quelle", ["prompts", "texte", "durchlauf", "modellprompts", "web"])
def test_dortmund_schlaegt_in_jeder_quelle_an(dortmund_quellen, quelle):
    """Positivkontrolle: jede Quelle liefert Text, und im Deutschen findet
    der Pruefer darin Deutsch -- sonst pruefte die Padua-Seite nichts."""
    assert dortmund_quellen[quelle], quelle
    assert any(pruefe_sprache.deutsche_treffer(q, t) for q, t in dortmund_quellen[quelle])


def test_padua_quellen_sind_nicht_leer(padua_quellen):
    for name, liste in padua_quellen.items():
        assert liste, name


def test_cli_exit_codes():
    assert pruefe_sprache.main(["padua-2026"]) == 0
    assert pruefe_sprache.main(["dortmund-2026", "--quelle", "texte"]) == 1
```

- [ ] **Schritt 2: Rot sehen** — `AttributeError: … has no attribute 'quellen'`.
- [ ] **Schritt 3: Umsetzen** — in `scripts/pruefe_sprache.py`:

```python
import contextlib
import os
import tempfile
import threading


@contextlib.contextmanager
def _profil(name: str):
    """Haengt ein Profil ein wie scripts/pruefe_profil.pruefe_namen und
    stellt die Umgebung danach wieder her."""
    from interview_theater import anweisungen, sprache, workshop

    vorher = os.environ.get(workshop.VARIABLE)
    os.environ[workshop.VARIABLE] = name
    workshop.vergiss(); sprache.vergiss(); anweisungen._CACHE.clear()
    try:
        yield
    finally:
        if vorher is None:
            os.environ.pop(workshop.VARIABLE, None)
        else:
            os.environ[workshop.VARIABLE] = vorher
        workshop.vergiss(); sprache.vergiss(); anweisungen._CACHE.clear()


def _quelle_prompts() -> list[tuple[str, str]]:
    from scripts import prompt_schnappschuss

    return [(f"prompt {name}", text) for name, text in prompt_schnappschuss.teile()]


def _quelle_texte() -> list[tuple[str, str]]:
    """Jeder Schluessel der englischen Tabelle, geliefert ueber
    sprache.text -- also genau das, was der Code unter DIESEM Profil sieht
    (Dortmund: die deutsche Konstante)."""
    import importlib

    from interview_theater import sprache

    fertig = []
    for modul, eintraege in sprache.tabelle("en").items():
        importlib.import_module(f"interview_theater.{modul}")
        for name in eintraege:
            wert = sprache.text(f"interview_theater.{modul}", name)
            for pfad, text in _blaetter(wert, f"{modul}.{name}"):
                fertig.append((pfad, text))
    return fertig


ANTWORT_EN = "Here is a short answer in plain English for the group."


def _minimal(schema: dict):
    """Eine gueltige Minimalantwort zu einem JSON-Schema -- die Attrappe
    braucht keine Fachlogik, nur Form."""
    if "enum" in schema:
        return schema["enum"][0]
    typ = schema.get("type")
    if typ == "object":
        pflicht = schema.get("required", [])
        return {k: _minimal(v) for k, v in schema.get("properties", {}).items() if k in pflicht}
    if typ == "array":
        return []
    if typ in ("integer", "number"):
        return 1
    if typ == "boolean":
        return False
    return ANTWORT_EN


class LLMAttrappe:
    """Zeichnet jeden Prompt auf (Quelle c2) und antwortet in Minimalform."""

    def __init__(self):
        self.aufgezeichnet: list[tuple[str, str, str]] = []

    def schema(self, chat_id, system, nutzer, schema, art, **_kw):
        self.aufgezeichnet.append((art, system, nutzer))
        return _minimal(schema)

    def prosa(self, chat_id, system, nutzer, art, **_kw):
        self.aufgezeichnet.append((art, system, nutzer))
        return ("TITLE: Night\nSHORT: Two wait.\nSUMMARY: They wait.\n"
                "DONE DIFFERENTLY: nothing\n\nNADIA: The bus is late.\nTOMAS: It always is.")


def _warte_auf_threads(sekunden: float = 10.0) -> None:
    for t in threading.enumerate():
        if t is not threading.main_thread() and not t.daemon:
            t.join(sekunden)


def _durchlauf() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Ein skriptierter Workshop gegen Attrappen: Begruessung, Phaseneintritte
    1-7, jeder angebotene Knopf einmal, /stand, /hilfe, /sprache, Aufnahme
    per Textimport, US-Einwilligung. Kein Netz, keine Betriebsdatenbank."""
    from interview_theater import (aufnahme, befehle, bot, db, einstellungen, knoepfe,
                                   repo, szene_claude)
    from simulation.attrappe import TelegramAttrappe
    from tests.fixture_sprache import baue_englische_gruppe

    with tempfile.TemporaryDirectory(prefix="a1-sprache-") as verz:
        e = einstellungen.Einstellungen(
            bot_token="T", bot_name="gruppe1", db_pfad=f"{verz}/t.db",
            audio_verz=f"{verz}/audio", llm_url="https://llm.invalid/v1/chat/completions",
            llm_key="K", llm_modell="kimi", stt_basis="https://stt.invalid",
            stt_produkt="P", erkenner_modell="gemma",
        )
        conn = db.verbinde(e.db_pfad)
        db.initialisiere(conn)
        baue_englische_gruppe(conn)
        tg, klm = TelegramAttrappe(), LLMAttrappe()
        original = szene_claude.ist_aktiv
        szene_claude.ist_aktiv = lambda *a, **k: False   # kein Weg ins Netz
        try:
            bot.erstkontakt(conn, tg, e, 1)
            for befehl in ("/hilfe", "/stand", "/sprache", "/leitfaden", "/phase"):
                befehle.behandle(conn, tg, e, 1, befehl, None, klm=klm)
            befehle.behandle(conn, tg, e, 1, "/aufnahme", None, klm=klm)
            aufnahme.importiere_text(conn, e, 1, 900, "Allora, home is the smell of bread.")
            befehle.behandle(conn, tg, e, 1, "/aufnahme", None, klm=klm)
            _warte_auf_threads()
            for phase in range(1, 8):
                repo.setze_phase(conn, 1, phase)
                knoepfe.eintritt_in_phase(conn, tg, klm, e, 1, phase)
                _warte_auf_threads()
            gedrueckt: set[str] = set()
            for _ in range(200):
                offen = [k for k in tg.offene_knoepfe() if k["daten"] not in gedrueckt]
                if not offen:
                    break
                knopf = offen[0]
                gedrueckt.add(knopf["daten"])
                knoepfe.behandle(conn, tg, klm, e, {
                    "callback_query_id": "q", "data": knopf["daten"],
                    "chat_id": 1, "message_id": knopf["message_id"]})
                _warte_auf_threads()
        finally:
            szene_claude.ist_aktiv = original
            conn.close()
    gesendet = [("chat", n["text"]) for n in tg.gesendet]
    gesendet += [("knopf", b) for leiste in tg.knoepfe for b, _ in leiste["knoepfe"]]
    gesendet += [("einblendung", text) for _, text in tg.beantwortet if text]
    gesendet += [("menue", b["description"]) for b in befehle.T.BEFEHLE_LISTE]
    modell = [(f"{art} system", s) for art, s, _ in klm.aufgezeichnet]
    modell += [(f"{art} nutzer", n) for art, _, n in klm.aufgezeichnet]
    return gesendet, modell


def _quelle_web() -> list[tuple[str, str]]:
    from interview_theater import db, web, web_daten
    from tests.fixture_sprache import baue_englische_gruppe

    with tempfile.TemporaryDirectory(prefix="a1-web-") as verz:
        pfad = f"{verz}/web.db"
        conn = db.verbinde(pfad)
        db.initialisiere(conn)
        token = baue_englische_gruppe(conn)
        conn.close()
        lesend = web_daten.oeffne_lesend(pfad)
        try:
            daten = web_daten.gruppe_nach_token(lesend, token)
            leitfaden = web_daten.leitfaden_nach_token(lesend, token)
        finally:
            lesend.close()
    return [
        ("web gruppe", nur_text(web.gruppe_html(daten, web.nonce(b"k", token), token))),
        ("web textbuch", nur_text(web.textbuch_html(daten, token))),
        ("web leitfaden", nur_text(web.leitfaden_html(leitfaden | {"token": token}))),
    ]


def quellen(profil: str) -> dict[str, list[tuple[str, str]]]:
    with _profil(profil):
        durchlauf, modell = _durchlauf()
        return {
            "prompts": _quelle_prompts(),
            "texte": _quelle_texte(),
            "durchlauf": durchlauf,
            "modellprompts": modell,
            "web": _quelle_web(),
        }


def pruefe_profil(profil: str, nur: set[str] | None = None) -> list[Treffer]:
    treffer = []
    for name, liste in quellen(profil).items():
        if nur and name not in nur:
            continue
        for quelle, text in liste:
            treffer += deutsche_treffer(f"{name} | {quelle}", text)
    return treffer
```

  In `main`: ist `args.profil` gesetzt, `--quelle` (Kommaliste) lesen und
  `return _ausgabe(pruefe_profil(args.profil, nur))`.

  **Was hier auffaellt, ist Arbeit fuer die Aufgabe, die das Modul
  umgestellt hat** — nicht fuer den Pruefer. Findet der Padua-Lauf einen
  deutschen Rest, wird er dort behoben (Konstante + Eintrag) und der
  Pruefer bleibt unveraendert. **Ausnahmen:**
  - Gruppeninhalt der Fixture ist englisch, es gibt dort nichts zu erlauben.
  - Ruft der Durchlauf einen Weg, der trotz Attrappe ins Netz will
    (`httpx`-Fehler im Log), die Stelle am Code finden und dort eine
    Attrappe einsetzen — **nicht** den Weg aus dem Durchlauf nehmen.
  - `importiere_text` legt die Aufnahme nur bis `transkribiert` an
    (aufnahme.py:1429–1435); wer die Verdichtung im Durchlauf sehen will,
    ruft danach `aufnahme.verarbeite(conn, tg, klm, e, None, aufnahme_id)`
    (Signatur aufnahme.py:418) — das gehoert hinein, damit die
    Verdichtungsnachricht (Quelle c) und der Verdichter-Prompt (c2)
    mitgeprueft werden.
- [ ] **Schritt 4: Gruen und Abnahme**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_pruefe_sprache.py
$PY -m scripts.pruefe_sprache padua-2026 ; echo "exit=$?"
$PY -m scripts.pruefe_sprache dortmund-2026 | tail -1 ; echo "exit=$?"
```
Expected: gruen; Padua `0 Treffer`, `exit=0`; Dortmund `<N> Treffer` mit
N > 0, `exit=1`. Die Zahl N in den Commit-Text schreiben.

- [ ] **Schritt 5: Mutationsnachweis:** in `texte.toml` einen englischen
  Knopftext auf Deutsch zuruecksetzen (`_TEXT_SPEICHERN_KNOPF = "Ja, speichern"`)
  → `test_padua_ist_frei_von_deutsch` rot mit Quelle `texte` **und**
  `durchlauf | knopf`. Zuruecksetzen.
- [ ] **Schritt 6:** SUITE; Commit `"Sprachpruefer: Prompts, Tabelle, Probedurchlauf, Modellprompts, Gruppenseite (A1, D10)"`.

---

## Aufgabe 31 (manuell, kostenpflichtig — freigegeben): Korpuslauf deutsch und englisch (D12)

**Kein Test, laeuft nie automatisch, kostet wenige CHF bei Infomaniak
(freigegeben laut Karte).** Laeuft sequenziell (Falle 8).

**Files:** Create `docs/sprache-a1-korpuslauf-<JJJJ-MM-TT>.md` (nur Zahlen
und Fall-ids, **keine** Modellantworten — die Berichte unter
`korpus/berichte/` bleiben gitignored).

- [ ] **Schritt 1: Laufen lassen** (Env laden, **nie ausgeben**; `IT_DB`
  verwirft `pruefe_prompts` ohnehin, scripts/pruefe_prompts.py:903–906):

```bash
set -a; . ../../betrieb/gruppe1.env; set +a
$PY -m scripts.pruefe_prompts erkenner --bericht               2>&1 | tee /tmp/a1-korpus-de.txt
$PY -m scripts.pruefe_prompts erkenner --sprache en --bericht  2>&1 | tee /tmp/a1-korpus-en.txt
```

- [ ] **Schritt 2: Zahlen herausziehen** — aus den beiden Berichten
  (`korpus/berichte/<datum>-erkenner.md`, `…-erkenner-en.md`, Abschnitt
  der Summe von `baue_summe`, scripts/pruefe_prompts.py:734): Faelle,
  Treffer, Falsch-Positive (FP), Falsch-Negative, FN in Zustimmungsfaellen
  (`zustimmungszeilen`, :706), Eingabe-/Ausgabe-Token, Kosten in CHF
  (`kosten_chf`, :695). Die Kosten stehen in der Summe; wer sie aus der
  Wegwerf-DB will: der Lauf loescht sie am Ende (TemporaryDirectory) — die
  Summe im Bericht **ist** die Kostenquelle.
- [ ] **Schritt 3: Bericht schreiben** — `docs/sprache-a1-korpuslauf-<datum>.md`:

```markdown
# Erkenner-Korpuslauf Deutsch und Englisch (Karte A1, <datum>)

Modell: <e.erkenner_modell>, sequenziell, je Fall ein Aufruf.
Commit: <git rev-parse --short HEAD>

| | Deutsch (`korpus/erkenner.jsonl`) | Englisch (`korpus/en/erkenner.jsonl`) |
|---|---:|---:|
| Faelle (davon negativ) | 150 (53) | <n> (<neg>) |
| Treffer / erwartet | … | … |
| Falsch-Positive (Exit-Kriterium, Soll 0) | … | … |
| Falsch-Negative | … | … |
| FN in Zustimmungsfaellen (Soll 0) | … | … |
| Token ein / aus | … | … |
| Kosten CHF | … | … |

## Befunde
- FP-Faelle (nur ids): …
- FN-Faelle (nur ids): …

## Whisper-Rauchtest (Aufgabe 9)
…

## Offen
- Journal-, Verdichter-, Sprachprofil-Prompts auf Englisch sind **ungemessen**
  (A9) — Folgearbeit: englische Korpora `korpus/en/{journal,verdichter,sprachprofil}.jsonl`.
```

- [ ] **Schritt 4: Wenn Deutsch FP > 0:** das ist **kein** A1-Befund, solange
  `interview_theater/prompts/erkenner.md` unveraendert ist
  (`git diff d8deb6c -- interview_theater/prompts/erkenner.md` leer) —
  Modellstreuung; als solche im Bericht benennen und den Lauf fuer die
  betroffenen ids mit `--nur <ids> --wiederholungen 3` wiederholen.
- [ ] **Schritt 5: Wenn Englisch FP > 0:** **kein stilles Weitermachen.**
  Befund mit ids in den Bericht, dann **hoechstens zwei** Iterationsrunden
  am englischen Erkenner-Prompt
  (`interview_theater/sprachen/en/prompts/erkenner.md`): je Runde die
  FP-Faelle lesen, eine Regel schaerfen oder einen Few-Shot **ersetzen**
  (nicht hinzufuegen: `test_gleiche_platzhalter_und_struktur[erkenner]`
  und `test_erkenner_behaelt_seine_few_shots` halten die Zahl 21 fest).
  Geht es nur mit einem zusaetzlichen Few-Shot, bekommt der Paritaetstest
  eine benannte Ausnahme (`STRUKTUR_AUSNAHMEN = {"erkenner": "<Grund,
  Fall-ids>"}` in `tests/test_sprache_prompts.py`, und
  `test_erkenner_behaelt_seine_few_shots` vergleicht dann gegen 21 plus die
  Zahl der Ausnahme) — und der Bericht sagt das. Danach nur die FP-ids plus
  alle Negativfaelle nachlaufen lassen (`--sprache en --nur <ids>`). Nach
  der zweiten Runde steht, was steht — als Befund, und Birk entscheidet vor
  Padua.
- [ ] **Schritt 6: Commit** (Bericht und ggf. Prompt):

```bash
git add docs/sprache-a1-korpuslauf-*.md interview_theater/sprachen/en/prompts/erkenner.md
git commit -m "Erkenner-Korpuslauf deutsch/englisch: Trefferquoten nebeneinander (A1, D12)"
```

---

## Aufgabe 32: Doku nachziehen (D13)

**Files:** `AGENTS.md`, `docs/workshop-profil-umbau-2026-09-06.md` (§5),
`workshop/padua-2026/LIESMICH.md` (Feinschliff nach Aufgabe 29/31).

- [ ] **Schritt 1: `AGENTS.md`**
  - Modultabelle: Zeile `sprache.py` (Dienste-Schicht: `code()`,
    `whisper_vorgabe()`, `pseudonyme()`, `Texte`/`T`, Tabelle je Sprache,
    Nachschlagen zur Aufrufzeit), Zeile `sprachen/` (`en/texte.toml`,
    `en/prompts/**` — die Sprachschicht zwischen Repo und Profil), in der
    Modulkarte `sprache.py` unter **Dienste**.
  - Abschnitt „Workshop-Profil": ein Absatz **Sprache** — Felder
    `sprache.code` (`de`|`en`), `sprache.whisper` (`auto`|ISO), 
    `datenschutz.pseudonyme`; Reihenfolge der Prompt-Suche
    **Profil → Sprachschicht → Repo**, Bausteine Repo → Sprachschicht →
    Profil; „deutsche Konstanten sind die deutsche Tabelle, `T.X` statt `X`";
    der Text-Waechter `tests/test_sprache_texte.py`; die zwei
    Bitgleichheits-Massstaebe `docs/prompt-audit/*-vor-sprache-a1.txt`.
  - Bindende Entscheidungen: ein Absatz **E8** (Pseudonyme im Code, nicht nur
    im Prompt; `kontext.sprecherzeile` ist die eine Stelle; Aufnahmenamen
    ueber `aufnahme.anzeigename`), ein Satz **D7** (`zitat.pruefe`
    unveraendert, Zitate im Original).
  - Befehlstabelle: **fuenfzehn** Befehle (W10: heute vierzehn inkl.
    `/festlegung`, dazu `/sprache` versteckt).
  - „Prompt geaendert? → Korpus laufen lassen": englischer Korpus
    `korpus/en/erkenner.jsonl`, `--sprache en`, die FP-Regel gilt fuer
    **beide** Sprachen; Journal/Verdichter/Sprachprofil englisch ungemessen.
  - Fallen: eine Zeile „`T._TEXT_X` nie in Default-Argumenten oder
    Modulkonstanten — dort wird beim Import ausgewertet, und ein Web-Prozess
    mit zwei Profilen zeigte die falsche Sprache".
- [ ] **Schritt 2: `docs/workshop-profil-umbau-2026-09-06.md` §5** — die
  Punkte `stt.py`, `_TEXT_*`, Auftragsmuster, Einwilligung als **gebaut
  (Karte A1, 30.09.2026)** markieren, mit Verweis auf diesen Plan; offen
  bleiben: Anti-Nachplapper-Wortlisten in den Tests, Korpus je Profil im
  Betriebscode, zweite Web-Instanz je Workshop, Betriebsnamen, Simulations-
  Personas, englische Nicht-Erkenner-Korpora.
- [ ] **Schritt 3:** `$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py` (LIESMICH-Test) gruen.
- [ ] **Schritt 4:** Commit `"Doku: Sprache pro Profil, E8, /sprache, englischer Korpus (A1)"`.

---

## Aufgabe 33: Abschluss

- [ ] **Schritt 1: volle Suite**

```bash
$PY -m pytest -q -p no:cacheprovider
```
Expected: `<N> passed, 1 skipped`, 0 failed, N ≥ 2768 + neue Tests. Die Zahl
N in die Schlussmeldung.

- [ ] **Schritt 2: Profile**

```bash
$PY -m scripts.pruefe_profil dortmund-2026     # "dortmund-2026: in Ordnung", Exit 0
$PY -m scripts.pruefe_profil padua-2026        # nur die Geruest-Zeile (Aufgabe 29), Exit 1
```

- [ ] **Schritt 3: Sprachpruefer**

```bash
$PY -m scripts.pruefe_sprache padua-2026 ; echo "exit=$?"      # 0 Treffer, exit=0
$PY -m scripts.pruefe_sprache dortmund-2026 | tail -1 ; echo "exit=$?"   # N Treffer, exit=1
```

- [ ] **Schritt 4: Bitgleichheit, beide Massstaebe, beide Wege**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py
$PY -m scripts.prompt_schnappschuss /tmp/a1-nach-ohne.txt
IT_WORKSHOP=dortmund-2026 $PY -m scripts.prompt_schnappschuss /tmp/a1-nach-dortmund.txt
cmp /tmp/a1-nach-ohne.txt /tmp/a1-nach-dortmund.txt && echo IDENTISCH
```
Expected: gruen; `IDENTISCH`. (Die Vergleiche gegen die Massstaebe
`docs/prompt-audit/*-vor-sprache-a1.txt` fuehrt der Test; neue Abschnitte
sind erlaubt, veraenderte nur ueber `VERSCHOBEN`/`GEAENDERT`.)

- [ ] **Schritt 5: Nachbarkarten** — die Uebergaben unten sind erfuellt
  bzw. benannt.
- [ ] **Schritt 6:** `git status` → sauber (keine unversionierten Dateien
  ausser den bekannten `.cc-*`-Laufdateien des Harness).

---

## Uebergaben an die Nachbarkarten

- **Karte P** (Padua-Inhalt): ersetzt jede Zeile mit `ANNAHME (Platzhalter
  A1` in `workshop/padua-2026/profil.toml` aus Birks Vault; entscheidet, ob
  die generischen englischen Rahmen-Vorlagen
  (`interview_theater/sprachen/en/prompts/rahmen*.md`, `projekt.md`) reichen
  oder Padua eigene `workshop/padua-2026/prompts/rahmen*.md` bekommt (der
  Mechanismus: Profil schlaegt Sprachschicht); nimmt alle englischen Texte
  und Prompts am Dump ab (`$PY -m scripts.prompt_schnappschuss --voll
  /tmp/padua-dump.txt` mit `IT_WORKSHOP=padua-2026`, dazu
  `$PY -m scripts.pruefe_sprache padua-2026` als Kontrolle, dass beim
  Umschreiben nichts Deutsches zurueckkommt); streicht `geruest = true`;
  prueft Annahme A3/A1 (Whisper) und A4 (Befehlsaliase) mit Birk.
- **Karte A2** (Web-Chat): das Web-Feld fuer `gruppe.stt_sprache` ueber
  `repo.setze_stt_sprache` (kein zweiter Schreibweg); der Web-Chat benutzt
  dieselben `T`-Texte und `knoepfe`-Wege; ein Web-Prozess mit mehreren
  Gruppen bekommt die Sprache ueber das Profil **des Prozesses** — zwei
  Workshops in einem Web-Prozess brauchen dort eine Profilwahl je Gruppe
  (heute: eine Web-Instanz je Workshop). Das Team-Dashboard `/` bleibt
  deutsch (Aufgabe 17).
- **Karte S** (Kostendeckel): ihre englische Meldung kommt als
  zweisprachig geborene Konstante mit `T` (Konvention K1–K3) — der
  Text-Waechter faengt sie sonst.

---

## Selbstdurchsicht (nach dem Schreiben, gegen Karte und Brief gehalten)

**Abdeckung der Karte:**
- Whisper `de` → Profilwert, `auto`, pro Gruppe umstellbar (Befehl + Knopf;
  Web-Feld → A2), Transkript in Originalsprache: Aufgaben 6–9.
- ~111 → gemessen ≈ 370 + ≈ 120 Chat-/Knopftexte: Aufgaben 8, 10–17.
- Auftragsmuster je Sprache: Aufgabe 22. Einwilligungstexte inhaltlich
  gleich (E9): Aufgabe 16. Prompts englisch: 18–21. Erkenner-Korpus
  englisch: 27, Lauf: 28/31.
- Mehrsprachiges Material, Zitate im Original: D7-Satz (19), Test (26).
- E8 Anweisung + Code + Test: 18 (Satz), 25 (Code, Test).
- Keine Uebersetzung Szenen→Italienisch: nirgends geplant, globale Vorgabe.
- Kein i18n-Framework: `sprache.py` (Standardbibliothek + `workshop`).
- Abnahme (1) Suite gruen: jede Aufgabe, 33. (2) Dortmund bitgleich: 1,
  jede Aufgabe, 33. (3) Padua ohne deutsche Saetze, mechanisch, mit
  Positivkontrolle: 3 (Kern), 17 (Web), 30 (alle Quellen), 33.
  (4) Korpuslauf gegen das echte Modell, Quoten nebeneinander: 31.

**Abdeckung D1–D13:** D1 → 2; D2 → 6–9; D3 → 3, 5, 8, 10–17; D4 → 4,
18–21; D5 → 22–24; D6 → 25; D7 → 19, 26; D8 → 27, 28; D9 → 2 (Sprache),
29; D10 → 3, 17, 30; D11 → 1, 3 (Hook), 33; D12 → 31; D13 → 32.

**Platzhalter-Scan:** keine „TBD"/„spaeter"; wo ein Umsetzer am Code
nachlesen muss (Struktur von `FELD_ALIASE`, exakte deutsche Fragenamen in
`stueckpruefung.FRAGEN`, Journal-Aufrufer von `_ausschnitt_text`), steht der
`grep`, der die Stelle findet, und die Regel, wie zu entscheiden ist.

**Typ-Konsistenz:** `sprache.Texte`/`T`, `sprache.text(modul, name)`,
`sprache.platzhalter`, `sprache.angleichen`, `sprache.je_sprache`,
`sprache.pseudonyme()`, `kontext.pseudonyme(conn, chat_id, zeilen)`,
`kontext.sprecherzeile(n, namen)`, `aufnahme.whisper_sprache(conn, chat_id)`,
`aufnahme.anzeigename(conn, row, ersatz)`, `repo.setze_stt_sprache`/
`stt_sprache`/`absender_in_reihenfolge`, `stt.transkribiere(…, *, sprache=)`,
`knoepfe.biete_stt_sprache`, `ART_STT_SPRACHE`, `STT_KNOEPFE`,
`pruefe_sprache.deutsche_treffer/pruefe_dateien/pruefe_schluessel/quellen/
pruefe_profil/nur_text/main` — in allen Aufgaben gleich benutzt.

---

## Anhang A: Die Inventurskripte (Bestandsaufnahme wiederholbar)

Unter `/tmp/a1_inv/` ablegen, aus dem Arbeitsbaum aufrufen
(`$PY /tmp/a1_inv/<name>.py`). Sie aendern nichts.

**A.1 `nicht_text.py`** — Modul-Konstanten vom Typ `str`, die nicht
`TEXT`/`ANWEISUNG`/`UEBERSCHRIFT` heissen:

```python
import ast, pathlib, re, importlib, sys, os
sys.path.insert(0, os.getcwd())
muster = re.compile(r'^_?[A-Z][A-Z0-9_]*$')
for f in sorted(pathlib.Path('interview_theater').rglob('*.py')):
    mod = '.'.join(f.with_suffix('').parts)
    m = importlib.import_module(mod)
    for knoten in ast.parse(f.read_text(encoding='utf-8')).body:
        ziele = []
        if isinstance(knoten, ast.Assign):
            ziele = [t.id for t in knoten.targets if isinstance(t, ast.Name)]
        elif isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name) and knoten.value is not None:
            ziele = [knoten.target.id]
        for z in ziele:
            v = getattr(m, z, None)
            if muster.match(z) and isinstance(v, str) and not re.match(r'^_?(TEXT|UEBERSCHRIFT|ANWEISUNG)', z) and not z.startswith('ART_'):
                print(mod.split('.', 1)[1], z, '=', repr(v)[:100])
```

**A.2 `inline.py`** — deutsche Inline-Literale in Funktionen (`--liste`
zeigt jede Stelle):

```python
import ast, pathlib, re, sys, collections
STOPP = re.compile(r"\b(und|nicht|ist|ihr|euch|wir|ich|mit|fuer|für|auf|eine|einen|noch|schon|auch|oder|wenn|dass|sich|werden|bitte|jetzt|hier|sind|habt|eure|euer|uns|kein|keine|die|der|das|den|dem|des|zu|von|es|du|dein|deine)\b", re.I)
UMLAUT = re.compile(r"[äöüÄÖÜß]")
SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|PRAGMA|WITH)\b", re.I)


def text_von(k):
    if isinstance(k, ast.Constant) and isinstance(k.value, str):
        return k.value
    if isinstance(k, ast.JoinedStr):
        return "".join(t.value if isinstance(t, ast.Constant) else "{}" for t in k.values)
    return None


class Sammler(ast.NodeVisitor):
    def __init__(self):
        self.tiefe, self.treffer, self.verboten = 0, [], set()

    def visit_FunctionDef(self, k):
        if k.body and isinstance(k.body[0], ast.Expr) and isinstance(getattr(k.body[0], "value", None), ast.Constant):
            self.verboten.add(id(k.body[0].value))
        self.tiefe += 1
        self.generic_visit(k)
        self.tiefe -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, k):
        name = ast.unparse(k.func)
        if re.match(r"^(log|logging|_log|logger)\.", name) or name.endswith(("Fehler", "Error", "Exception")):
            self.verboten.update(id(x) for x in ast.walk(k))
        self.generic_visit(k)

    def visit_Raise(self, k):
        self.verboten.update(id(x) for x in ast.walk(k))
        self.generic_visit(k)

    def visit_JoinedStr(self, k):
        self._pruefe(k)
        self.verboten.update(id(x) for x in ast.walk(k))

    def visit_Constant(self, k):
        self._pruefe(k)

    def _pruefe(self, k):
        if self.tiefe == 0 or id(k) in self.verboten:
            return
        t = text_von(k)
        if not t or SQL.match(t):
            return
        worte = STOPP.findall(t)
        if len(worte) >= 2 or (UMLAUT.search(t) and len(t) > 3) or (worte and len(t.split()) >= 3):
            self.treffer.append((k.lineno, t))


zaehl = collections.Counter()
for f in sorted(pathlib.Path("interview_theater").rglob("*.py")):
    s = Sammler()
    s.visit(ast.parse(f.read_text(encoding="utf-8")))
    zaehl[str(f)] = len(s.treffer)
    if "--liste" in sys.argv:
        for zeile, t in s.treffer:
            print(f"{f}:{zeile}: {t[:110]!r}")
for f, n in zaehl.most_common():
    if n:
        print(f"{n:4d}  {f}")
print("SUMME", sum(zaehl.values()))
```

**A.3 `behaelter.py`** — Behaelter-Konstanten mit deutschem Text: wie A.1,
aber fuer `dict`/`list`/`tuple`/`set`, rekursiv alle `str`-Blaetter, Treffer
bei Stoppwort (`und|nicht|ist|ihr|euch|wir|ich|mit|fuer|für|auf|eine|noch|
schon|auch|oder|wenn|dass|sich|bitte|jetzt|hier|sind|eure|euer|uns|die|der|
das|zu|von`) oder Umlaut; Ausgabe `modul.NAME (typ, n Texte, k deutsch):
erstes Beispiel`.

**A.4 `verwendungen.py`** — Lese-Verwendungen der Text-Konstanten:

```python
import ast, pathlib, re, collections
MUSTER = re.compile(r"^_?(TEXT|UEBERSCHRIFT|ANWEISUNG)[A-Z0-9_]*$")
je_datei = collections.Counter()
for f in sorted(pathlib.Path("interview_theater").rglob("*.py")):
    for k in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
        if isinstance(k, ast.Name) and isinstance(k.ctx, ast.Load) and MUSTER.match(k.id):
            je_datei[str(f)] += 1
        elif isinstance(k, ast.Attribute) and isinstance(k.ctx, ast.Load) and MUSTER.match(k.attr):
            je_datei[str(f)] += 1
for f, n in je_datei.most_common():
    print(f"{n:4d}  {f}")
print("SUMME", sum(je_datei.values()))
```

**A.5 `schluessel.py`** — Kandidaten fuer die Texttabelle je Modul (die
Listen der Aufgaben 10–16 kommen hieraus): Modul-Konstanten (ohne
`workshop, db, repo, web_daten, telegram, szene_claude, llm,
einstellungen`, ohne `__init__`), Name `^_?[A-Z][A-Z0-9_]*$`, nicht
`ART_*`/`PHASE_*`/`_CSS*`/`*_JS`/`*TRENNER`/`*_SCHLUESSEL`/`MARKER`/
`PRAEFIX` u. ae., Wert `str` oder Behaelter mit Text, und entweder deutsch
(Stoppwort oder Umlaut) oder ein Textname
(`^_?(TEXT|UEBERSCHRIFT|ANWEISUNG|MELDUNG|JOURNAL|HINWEIS|ZEILE|KOPF)` bzw.
Endung `_KOPF`/`_ANSCHLUSS`/`_HINWEIS`). Gemessen: **386 in 33 Modulen**,
Ausgabe je Modul `## <modul> (<n>)` plus Namensliste.

**A.6 `umfang.py`** — dasselbe, summiert Zeichen je Modul (Heuristik,
eher zu niedrig): **297 Konstanten, 38 512 Zeichen**.

**A.7 `struktur.py`** — je Prompt-Datei Ueberschriften, Code-Zaeune,
Beispielzeilen, Platzhalter:

```python
import pathlib, re
for f in sorted(pathlib.Path("interview_theater/prompts").rglob("*.md")):
    t = f.read_text(encoding="utf-8")
    print(f"{str(f)[len('interview_theater/prompts/'):]:32s}",
          len(re.findall(r"(?m)^#{1,6} ", t)), len(re.findall(r"(?m)^```", t)),
          sorted(set(re.findall(r"\{\{([a-z][a-z0-9_]*)\}\}", t))))
```

**A.8 `parser_basis.py`** — die gemessenen deutschen (und heutigen
englischen) Ergebnisse der Parser, Grundlage der Sollwerte in Aufgabe 22/23:
ruft `ablauf.ist_auftrag`, `ablauf.szenentext_gewuenscht`,
`ablauf.ist_denkspur`, `ablauf.ist_erfundene_systemzeile`,
`szene.nummer_aus_auftrag`, `szene.feldname`, `szene.rahmenfelder`,
`kuerzung.nummer_aus_wert`, `kurzgeschichte.zerlege`,
`szenenfolge.formabfolge`, `szenenfolge.szenen_in_zeile`,
`szenenfolge.zerlege_geschichte`, `web.sprecher_der_zeile`,
`erkenner._ist_geschichte`, `erkenner.figurenzahl_aus`,
`repo.ist_platzhaltername`, `vorspann.erster_satz`,
`knoepfe.fragen.lies_fragennummern`, `knoepfe.figuren._zahl_aus`,
`stueckpruefung.frage_fuer`, `szene.zerlege`, `begriffe.passt` mit den
Eingaben aus den Tests und druckt `name(eingabe) -> ergebnis`. Auf
`d8deb6c` gemessen, u. a.: `ist_auftrag('write the scene') -> False`,
`szenentext_gewuenscht('show us scene 2') -> None`,
`kuerzung.nummer_aus_wert('Scene 3') -> None`,
`formabfolge('Scene 1: Dialogue, …') -> None`,
`web.sprecher_der_zeile('SCENE 1: The beginning') -> 'SCENE 1'`,
`figurenzahl_aus('We want three characters') -> None`,
`kurzgeschichte.zerlege(<englisch>)` liefert leere Zusammenfassungen,
`zerlege_geschichte('They meet.\nEnd: They leave.')` trennt die End-Zeile
faelschlich als Szene ab.

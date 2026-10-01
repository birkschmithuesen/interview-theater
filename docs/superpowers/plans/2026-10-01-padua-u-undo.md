# Padua U: Undo-Knopf unter jeder Notiert-Meldung

> **Fuer agentische Arbeiterinnen:** PFLICHT-SUB-SKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Aufgabe fuer Aufgabe. Die
> Schritte tragen Checkboxen (`- [ ]`).

**Ziel:** Unter jeder "Notiert:"-Meldung des Absichtserkenners steht ein
ruhiger Knopf, der mit EINEM Tipp den Stand vor diesem Erkennerlauf
wiederherstellt -- deterministisch, ohne Modellaufruf, alles-oder-nichts.

**Architektur:** `erkenner.laufe` nimmt vor und nach `wende_an` einen
**Schnappschuss** der verfolgten Tabellen dieser `chat_id`; die Differenz sind
die Ruecknahme-Schritte und liegen in zwei neuen Tabellen (`erkenner_lauf`,
`erkenner_lauf_schritt`). Die reine Diff-Logik steht im neuen Modul
`interview_theater/ruecknahme.py` (Fachlogik, kein SQL), jedes SQL als neue
`_gesperrt`-Funktion in `repo.py`, der Knopf als neue `ART_UNDO` im Paket
`knoepfe/`. Kein Nachbau je Erkenner-Art -- der Diff ist die eine Wahrheit.

**Technik:** Python 3.11, nur Standardbibliothek (`json`, `sqlite3`), pytest.
Kein Netz, kein Modellaufruf, keine neue Abhaengigkeit.

---

## Plan-Kopf

### Baseline (in diesem Worktree gemessen, 01.10.2026)

```
$PY -m pytest -q -p no:cacheprovider
→ 4350 passed, 1 skipped in 234.77s
```

`PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
Das `.venv` im Hauptbaum wird **nicht** verwendet. **Jede Aufgabe endet mit
mindestens der Baseline bestandenen Tests und 0 Fehlern**; neue Tests kommen
dazu, es geht keiner weg.

**Nachtrag Architekt (01.10.2026, nach dem Plan-Lauf):** 4350 ist auf der
Basis `A1 + A3` gemessen (dieser Worktree: `8eb52d7` = A1-Branch + `f66f68b`).
A1 liegt inzwischen in main (`04e57dd`), aber **ohne** den A3-Merge
`f66f68b` -- `git merge-base --is-ancestor f66f68b origin/main` schlaegt fehl,
22 Dateien Simulation/A3 fehlen dort. Deshalb gilt fuer die Umsetzung: **Vor
Aufgabe 1 die Baseline im Umsetzungs-Worktree selbst messen**
(`$PY -m pytest -q -p no:cacheprovider`, letzte Zeile notieren). Diese Zahl
ersetzt ueberall im Plan die 4350; die in den Aufgaben genannten Zielzahlen
(`4354`, `4456` ...) verschieben sich um dieselbe Differenz. Kein Test, den
dieser Plan anlegt oder anfasst, haengt an A3-Dateien (geprueft:
`git diff --name-only 8eb52d7 origin/main -- interview_theater/` zeigt nur
`sprachen/en/prompts/erkenner.md`, das der Plan nicht anfasst).

### Voraussetzung: A1 liegt in main

Dieser Worktree steht auf `A1 + origin/main` (Merge `8eb52d7`). Die Umsetzung
startet erst, wenn A1 in main ist. **Erster Schritt der Umsetzung, vor
Aufgabe 1:**

```bash
test -f interview_theater/sprache.py \
  && grep -q "class Texte" interview_theater/sprache.py \
  && echo "A1 DA" || echo "A1 FEHLT"
```

Erwartete Ausgabe: `A1 DA`. Steht dort `A1 FEHLT`, wird **abgebrochen** und
genau das gemeldet ("Karte U braucht den Sprachmechanismus aus A1
(`sprache.Texte`); er liegt nicht vor -- Board-Abhaengigkeit t_7b420154 noch
offen"). Ohne A1 gibt es keinen Weg, die Knopfbeschriftung fuer Padua
englisch zu machen, und ein deutscher Knopf im englischen Chat waere die
sichtbarste Stelle des Workshops.

### Hotspots (wenige additive Zeilen je Stelle, die Logik liegt woanders)

| Datei | Stelle | was dazukommt |
|---|---|---|
| `interview_theater/db.py` | `SCHEMA`, `TABELLEN_MIT_CHAT_ID` | zwei Tabellen, zwei Namen |
| `interview_theater/repo.py` | Ende, neuer Abschnitt | `schnappschuss`, `lege_erkenner_lauf_an`, `hole_erkenner_lauf`, `erkenner_lauf_schritte`, `merke_erkenner_lauf_nachricht`, `offene_knoepfe_der_nachricht`, `nimm_erkenner_lauf_zurueck` |
| `interview_theater/ruecknahme.py` | **neu** | `VERFOLGT`, `MATERIAL`, `plan`, `schritte`, `verweise`, `gleich` |
| `interview_theater/knoepfe/texte.py` | ART-Block, Textblock | `ART_UNDO` + fuenf Texte |
| `interview_theater/knoepfe/basis.py` | `_nimm_alte_leiste_ab` (163), `sende_notiert_mit_leiste` (567) | `undo_leiste`, `sende_notiert_nur_undo`, `_reduziere_auf_undo`, Parameter `zusatz` |
| `interview_theater/knoepfe/wirkung.py` | `_WIRKUNGEN` (1309) | `_wirkung_undo` |
| `interview_theater/knoepfe/__init__.py` | Re-Export-Listen | die neuen Namen |
| `interview_theater/erkenner.py` | `_sende_meldung` (1871), `laufe` (1923) | Schnappschuss, `undo_zeilen`, `_lege_ruecknahme_an`, ein Parameter |
| `interview_theater/sprachen/en/texte.toml` | `["knoepfe.texte"]` | fuenf englische Eintraege |

### Entscheidungen A-J: gepruefte Fassung

Jede Entscheidung des Architekten gilt. Wo der Code etwas anderes verlangt,
steht die Abweichung hier mit Beleg.

**A -- Erfassung per Diff.** Uebernommen. `wende_an` bleibt unangetastet (auch
in der Signatur -- `tests/test_erkenner.py` ruft es an 20 Stellen direkt auf);
der Schnappschuss wird in `laufe` genommen. Damit bekommt
`wende_aus_aufnahme_an` automatisch kein Undo.

* **Abweichung A.1 (Beleg):** Die **Material**-Tabellen werden mit
  **explizit genannten Spalten** verfolgt, nicht als ganze Zeilen.
  `repo.korrigiere_transkripte` (repo.py:1441-1455) schreibt genau fuenf
  Spalten: `aufnahme.transkript`, `verdichtung.zusammenfassung`,
  `verdichtung_thema.thema`, `.kurz`, `.beleg_zitat`. Ein Lauf kann aber
  `transkript_korrigieren` **und** `interview_beenden` enthalten, und
  `aufnahme.beende_interview` schreibt ebenfalls in `aufnahme`
  (`beendet_am`, `status`). Ein Zeilen-Schnappschuss wuerde die
  Interview-Buchhaltung mit zurueckdrehen -- ein Interview, das die Gruppe
  beendet hat, waere nach einem Undo wieder offen. Zweiter Grund: ein
  Zeilen-Schnappschuss laed alle Transkripte einer Gruppe (Megabytes) bei
  jedem solchen Lauf.
* **Abweichung A.2 (Beleg):** `ruecknahme.py` importiert `db` -- aber nur
  `db._tabellenspalten_aus_schema()` (db.py:767), um die verfolgten Spalten
  **aus dem Schema herzuleiten** statt sie ein zweites Mal aufzulisten. Das
  ist kein SQL; die Zusage "kein SQL in `ruecknahme.py`" bleibt und wird in
  Aufgabe 2 mit einem Test festgehalten.
* Spalten, die nie verglichen und nie zurueckgesetzt werden, stehen als
  `AUSSEN` je Tabelle in `ruecknahme.py`, je mit Grund im Kommentar:
  Zeitstempel (`geaendert_am`, `erstellt_am`), die Phasen-Buchhaltung
  (`phase`, `phase_angeboten`, `phase_gesetzt_am`) und die Felder, die
  **erst spaeter ein anderer Lauf** schreibt und `wende_an` nie anfasst
  (`figur.sprachprofil`, `figur.zitate`, `figur.geprueft_am`,
  `szene.volltext`, `szene.prosa`, `szene.zusammenfassung`,
  `szene.fertig_am`, `szene.fruehere_fassungen`, `szene.form`, `szene.stil`).
  Der letzte Punkt ist gemessen: `_wende_szene_planen_an` (erkenner.py:752)
  bildet das Feld `form` bewusst auf `form_vorschlag` ab -- `szene.form`
  traegt allein ein Knopfdruck der Gruppe. Ohne diese Ausnahmen wuerde ein
  Undo fuer das Kernthema an einem Sprachprofil scheitern, das ein Thread
  danach geschrieben hat.
* `gruppe` wird nicht verfolgt (USA-Einwilligung, Interviewmodus,
  Wortlaut-Modus). `journal` wird nie veraendert: die Zeilen des Laufs
  bleiben stehen, die Ruecknahme haengt eine neue an.

**B -- Ruecknahme einer Neuanlage = weich entfernen.** Uebernommen.
`WEICH = ("figur", "szene", "festlegung")` bekommen `entfernt_am`;
`HART = ("szene_figur",)` wird geloescht; hart geloeschte Verknuepfungen
werden wieder eingefuegt; ein im Lauf weich entferntes Objekt bekommt
`entfernt_am = NULL` zurueck (das ist ein `geaendert`-Schritt, kein eigener
Fall).

* **Abweichung B.1 (Beleg):** `arbeitsstand` hat kein `entfernt_am` und genau
  eine Zeile je Gruppe (db.py:204, `chat_id INTEGER PRIMARY KEY`). Eine im
  Lauf **entstandene** Zeile (die Gruppe hat zum ersten Mal ueberhaupt etwas
  festgelegt) wird deshalb **geleert** statt geloescht:
  `GELEERT = ("arbeitsstand",)`. Jeder Leser prueft `(stand[feld] or "")`,
  eine leere Zeile ist also von "keine Zeile" nicht zu unterscheiden -- und
  die Zeile zu loeschen hiesse, die Phasen-Buchhaltung in derselben Zeile
  mitzureissen.

**C -- "Changed since" per Wertvergleich.** Uebernommen, alles-oder-nichts in
EINER Transaktion unter `repo._LOCK`. Verglichen wird der **Nach-Wert** des
Laufs gegen den aktuellen Wert, Spalte fuer Spalte, nach JSON-Rundreise
(`ruecknahme.gleich`) -- damit `4` und `"4"` nicht an einem Typwechsel
auseinanderlaufen (`figuren_anzahl` kommt als `int` aus
`erkenner.figurenzahl_aus`, erkenner.py:984). Zusaetzlich der Waisen-Test fuer
jede im Lauf **angelegte** `figur`/`szene`.

Die Verweis-Spalten werden aus `db.SCHEMA` hergeleitet, nicht aufgezaehlt.
Pruefkommando:

```bash
grep -n "figur_id\|szene_id" interview_theater/db.py
```

Erwartet (Stand 01.10.2026): `szenenfassung.szene_id` (456),
`schaerfung.szene_id` (484), `schaerfung.figur_id` (485),
`szene_figur.szene_id` (606), `szene_figur.figur_id` (607) -- fuenf Paare,
drei Tabellen. Ein Test in Aufgabe 2 haelt genau diese Liste fest, damit eine
spaeter dazukommende referenzierende Tabelle auffaellt.

**D -- Datenmodell.** Uebernommen, Namen endgueltig:

```
erkenner_lauf(id, chat_id, meldung, message_id, erstellt_am, zurueckgenommen_am)
erkenner_lauf_schritt(id, chat_id, lauf_id, tabelle, schluessel, art,
                      vorher, nachher, erstellt_am)
```

`schluessel` ist das JSON-Objekt der Primaerschluesselspalten
(`json.dumps(..., sort_keys=True)`, weil `szene_figur` einen zusammengesetzten
hat), `vorher`/`nachher` die JSON-Objekte der verglichenen Spalten,
`art ∈ {geaendert, angelegt, geloescht}`. Beide Tabellen kommen in
`db.TABELLEN_MIT_CHAT_ID` (Loeschzusage), additiv per
`CREATE TABLE IF NOT EXISTS`, **kein** `SCHEMA_VERSION`-Schritt. Idempotenz
doppelt: `repo.beanspruche_knopf` wie bei jedem Knopf **und** das bedingte
`UPDATE erkenner_lauf SET zurueckgenommen_am = ? WHERE id = ?
AND zurueckgenommen_am IS NULL` in derselben Transaktion wie die Ruecknahme.

Ein Lauf-Datensatz entsteht nur, wenn **beides** dasteht: mindestens ein
Schritt **und** mindestens eine Undo-Zeile -- und nur dort, wo die Meldung
wirklich verschickt wird (nicht bei `_steht_schon_da`, nicht bei
`text is None`).

**E -- Welche Arten.** Uebernommen: kein Undo fuer `phase_setzen` (Karte) und
`szene_usa` (Architektenentscheidung). Beide fallen automatisch heraus, weil
`gruppe` und die Phasenspalten nicht verfolgt werden.

* **Abweichung E.1 (Beleg):** Der Filter fuer die Undo-Zeilen ist eine
  **Ausschluss**liste (`ZEILEN_OHNE_UNDO = {"phase_setzen", "szene_usa"}`) und
  keine Einschlussliste. Grund: `entschieden` ist in der Meldung still, setzt
  aber nebenbei `arbeitsstand.figuren_anzahl` (erkenner.py:981-986), und diese
  Spalte ist verfolgt -- die Zeile "Anzahl Figuren: 4" gehoert also in
  "Rueckgaengig gemacht:". Eine Einschlussliste haette sie verschluckt.
  Gebaut werden die Zeilen aus derselben Quelle wie die Meldung
  (`_sammle_meldbares` → `_meldungszeilen`), nur mit gefilterter Eingabe --
  keine zweite Formulierung.

**F -- Knopf.** Uebernommen: neue `ART_UNDO`, Handler in `_WIRKUNGEN`,
`callback_data` nur `k:<id>`, die Lauf-ID im `wert`, kein Modellaufruf, ohne
Emoji, als **letzte Zeile** der Tastatur (`telegram.sende_mit_knoepfen`
telegram.py:212 legt eine Zeile je Eintrag an -- am Code geprueft).

* **Abweichung F.1 (Beleg):** Die deutsche Beschriftung ist
  **"Rueckgaengig"** in ASCII-Umschrift, nicht "Rückgängig".
  `grep -c "[äöüßÄÖÜ]" interview_theater/knoepfe/texte.py` → **0**: die Datei
  traegt keinen einzigen Umlaut ("Nein, nochmal aendern", "Anzahl aendern",
  "Ueberspringen"). Ein Umlaut hier waere der erste im Modul.
* **Abweichung F.2 (Beleg):** "Nach wirksamem Undo die GANZE Tastatur dieser
  Meldung abnehmen" muss der Handler **nicht** selbst tun -- `behandle` tut
  es fuer jeden Knopf (wirkung.py:1461, `_entferne_tastatur(tg, chat_id,
  druck["message_id"])`). Neu ist allein das `verfallen_lassen` der
  Grundleisten-Knoepfe derselben Nachricht, damit "Ja, speichern" den gerade
  zurueckgenommenen Wert nicht wieder schreibt (der Wert steckt im Knopf,
  `basis.speicherleiste` basis.py:202).
* **Abweichung F.3 (Beleg):** Die Reduktion auf den Undo-Knopf in
  `_nimm_alte_leiste_ab` **verfallen-laesst zugleich alle Nicht-Undo-Knoepfe
  derselben Nachricht**, nicht nur die der uebergebenen `art`. Grund:
  `sende_notiert_mit_leiste` ruft `_nimm_alte_leiste_ab` dreimal hintereinander
  (basis.py:581-582, fuer `ART_SPEICHERN`, `ART_ANDERS`, `ART_EIGENE`), und
  `tg.aktualisiere_knoepfe` **wirft** `TelegramFehler` bei HTTP 400
  ("message is not modified", telegram.py:337-346). Ohne diese Erweiterung
  liefe jeder Notiert-Lauf mit Grundleiste in zwei vermeidbare 400er und zwei
  Warnungen im Log. Mit ihr findet der zweite und dritte Aufruf nichts mehr
  und kehrt frueh zurueck -- eine API-Anfrage je Nachricht. Nebenwirkung, die
  eine Verbesserung ist: eine ueberholte Leisten-Nachricht behaelt keinen
  einzigen lebenden Nicht-Undo-Knopf mehr.
* Die Antwortzeile nach dem Undo wird mit `repo.merke_bot_zeile`
  mitgeschrieben, wie jede andere Bot-Zeile.

**G -- Einhaengen.** Uebernommen. `laufe` nimmt den Schnappschuss (nicht
`wende_an`, siehe A). `_sende_meldung` haengt den Undo-Knopf an **beide** Wege;
ohne Grundleiste wird aus `tg.sende` ein `knoepfe.sende_notiert_nur_undo`.
Faellt das Anlegen aus, geht die Meldung ohne Knopf raus, mit Vorfall
`undo_nicht_angelegt`.

* **Befund G.1: kein Bitgleich-Test aendert sich.**
  `tests/test_sprache_bitgleich.py:13` sagt ausdruecklich "Neue Abschnitte
  sind erlaubt (eine neue Konstante ist keine Undichtigkeit)"; geprueft wird
  nur, dass vorhandene Abschnitte nicht verschwinden oder sich aendern. Wir
  fuegen ausschliesslich **neue** Konstanten hinzu und aendern keinen
  bestehenden Wortlaut. `tests/test_profil_bitgleich.py` prueft Prompts,
  Formen, Phasen und Leitfaden-Bausteine -- nichts davon wird angefasst.
  `VERSCHOBEN`/`GEAENDERT` bleiben leer von neuen Eintraegen. Fuer jeden
  Bitgleich-Test gilt also: **unveraendert und gruen**, und das ist die
  Begruendung.
* **Befund G.2: kein bestehender Erkenner-Test bricht am Meldungstext.**
  `tests/test_erkenner.py::TelegramAttrappe.sende_mit_knoepfen` (Zeile 612)
  ruft intern `self.sende(...)` auf und schreibt damit auch in `tg.gesendet`.
  `test_laufe_sendet_meldung_und_schreibt_sie_als_bot_nachricht` (Zeile 627)
  prueft `len(tg.gesendet) == 1` und den Text -- das bleibt wahr, wenn die
  Meldung ueber `sende_mit_knoepfen` geht. Die einzige Anpassung an
  bestehenden Tests ist eine neue Methode `aktualisiere_knoepfe` an dieser
  Attrappe (Aufgabe 7), damit die Reduktion aus F.3 beobachtbar ist statt
  geschluckt. `tests/test_aufnahme.py:1301`
  (`assert tg.mit_knoepfen == []`) liegt am `/aufnahme`-Pfad und ist nicht
  betroffen.

**H -- Erkenner liest es nicht wieder: geprueft, Zeilenangaben.**
`erkenner.erkenne` rueckt das Wasserzeichen am Ende jedes erfolgreichen Laufs
vor (`repo.setze_extrahiert_bis`, **erkenner.py:372**), und
`repo.unextrahierte` (**repo.py:274-284**) liefert ausschliesslich
Nachrichten mit `message_id > g.letzte_extrahierte_message_id`. Die Nachricht,
aus der der falsche Wert kam, wird vom naechsten Lauf **nicht erneut
gelesen** -- es gibt also keinen Pfad, auf dem der Erkenner den gerade
zurueckgenommenen Wert von sich aus wieder setzt.

Zwei Nebenbefunde, beide guenstig und beide durch die kleinste Massnahme
(die Undo-Zeile als Bot-Zeile) abgedeckt:

1. `repo.letzte_bot_nachricht_vor` (**repo.py:294-304**) schliesst Zeilen aus,
   die mit `Notiert:` oder `Noted:` beginnen -- die Undo-Zeile beginnt mit
   "Rueckgaengig gemacht:" / "Undone:" und **kann** deshalb der Vorlauf des
   naechsten Laufs sein. Genau richtig: das Modell soll sehen, dass
   zurueckgenommen wurde.
2. Weil `merke_bot_zeile` in `nachricht` schreibt, steht die Undo-Zeile auch
   im Gespraechsfenster (`kontext.baue` ueber `letzte_nachrichten`) -- der
   Gespraechs-Bot behauptet im naechsten Zug nicht mehr, der Wert stehe.

Ein Test haelt beides fest (Aufgabe 7:
`test_nach_undo_liest_der_erkenner_die_alte_nachricht_nicht_erneut`).

**I -- Web (A2).** A2 liegt **heute nicht** in main:
`test -f interview_theater/web_kanal.py` → **FEHLT** (am 01.10.2026 in diesem
Worktree gemessen). Gebaut wird der Telegram-Pfad, und zwar ausschliesslich
ueber die vier Kanal-Verben, die A2 laut seinem Plan nachbaut:
`sende_mit_knoepfen`, `aktualisiere_knoepfe`, `entferne_knoepfe`,
`beantworte_knopf`. **Kein neuer Code in dieser Karte ruft etwas
Telegram-Spezifisches** -- der neue Code geht durchweg ueber
`knoepfe.basis._sende_knoepfe` und `tg.<verb>`, nie an `httpx` oder eine
Telegram-URL. Aufgabe 10 prueft bedingt: liegt `web_kanal.py` beim Umsetzen
vor, kommt ein Test ueber den WebKanal dazu; sonst ist es ein Uebergabe-Punkt.

**J -- Doku.** AGENTS.md bekommt drei Stellen (Modultabelle, Modulkarte "Wo
man anfaengt", ein Absatz unter den bindenden Entwurfsentscheidungen).
Aufgabe 10.

### Offener Punkt fuer Birk

**Undo fuer die USA-Einwilligung (`szene_usa`) ist bewusst nicht gebaut.** Die
Einwilligung hat ihre eigene Nachricht, ihre eigenen zwei Knoepfe und ihren
eigenen Nachfrage-Ablauf (E9); sie per Undo auf "offen" zurueckzudrehen
aendert diesen Ablauf und faellt damit unter eine Datenschutz-Entscheidung,
nicht unter diese Karte. Die Zeile "Szenentexte kommen ab jetzt vom
US-Modell ..." steht deshalb in der Meldung, aber **nicht** in
"Rueckgaengig gemacht:". Zuruecknehmen geht weiter im Chat
(`repo.setze_szene_usa` ueber den Erkenner). Entscheidung liegt bei Birk.

### Annahmen

* **ANNAHME:** A1 liegt beim Umsetzen in main.
  `test -f interview_theater/sprache.py && grep -q "class Texte" interview_theater/sprache.py && echo OK`
  → `OK`. Schlaegt es fehl: **Abbruch mit genau dieser Meldung** (siehe oben).
* **ANNAHME:** A2 (`interview_theater/web_kanal.py`) liegt beim Umsetzen
  nicht vor. `test -f interview_theater/web_kanal.py && echo DA || echo FEHLT`
  → `FEHLT`. Steht dort `DA`, laeuft Aufgabe 10 im Zweig "WebKanal-Test".
* **ANNAHME:** `repo.korrigiere_transkripte` schreibt genau die fuenf Spalten
  aus A.1. Pruefkommando ist der Waechter-Test selbst:
  `$PY -m pytest tests/test_ruecknahme_rundreise.py::test_verfolgt_deckt_jede_geschriebene_spalte -q`
  → `1 passed`. Kommt eine sechste dazu, wird der Test rot.
* **ANNAHME:** `wende_an` schreibt nie `szene.form`, `szene.volltext`,
  `szene.prosa`, `figur.sprachprofil`, `figur.zitate`. Derselbe Waechter-Test.
* **ANNAHME:** Die Tabellen mit `figur_id`/`szene_id` sind `szene_figur`,
  `schaerfung`, `szenenfassung`.
  `grep -n "figur_id\|szene_id" interview_theater/db.py` → die fuenf Zeilen
  aus C. Test: `test_verweise_kommen_aus_dem_schema` (Aufgabe 2).
* **ANNAHME:** Bezahlte Modellaufrufe finden in dieser Karte nicht statt --
  weder Infomaniak noch der Proxy auf `127.0.0.1:28764`. Die Suite laeuft
  ohne Netz (Attrappen); `scripts/pruefe_profil.py` ruft kein Modell.

### Dateikarte

| Datei | Verantwortung |
|---|---|
| `interview_theater/ruecknahme.py` (**neu**, ~180 Zeilen) | Was verfolgt wird und wie aus zwei Schnappschuessen Schritte werden. Reine Funktionen, kein SQL, kein Nutzertext. |
| `interview_theater/db.py` | Zwei Tabellen im `SCHEMA`, zwei Namen in `TABELLEN_MIT_CHAT_ID`. |
| `interview_theater/repo.py` | Alles SQL: Schnappschuss lesen, Lauf speichern, Lauf zuruecknehmen (eine Transaktion), offene Knoepfe einer Nachricht. |
| `interview_theater/knoepfe/texte.py` | `ART_UNDO` und die fuenf Wortlaute. |
| `interview_theater/knoepfe/basis.py` | Die Leisten-Bausteine des Undo-Knopfs und die Reduktion statt Abnahme. |
| `interview_theater/knoepfe/wirkung.py` | `_wirkung_undo` und sein Eintrag in `_WIRKUNGEN`. |
| `interview_theater/erkenner.py` | Schnappschuss um `wende_an`, `undo_zeilen`, Knopf unter die Meldung. |
| `interview_theater/sprachen/en/texte.toml` | Die fuenf englischen Eintraege. |
| `tests/test_ruecknahme.py` (**neu**) | Die reine Diff-Logik, Spalte fuer Spalte. |
| `tests/test_ruecknahme_repo.py` (**neu**) | Schnappschuss, Speichern, die Transaktion, Idempotenz. |
| `tests/test_undo_knopf.py` (**neu**) | Die sieben Abnahmepunkte, Ende zu Ende ueber `laufe` und `behandle`. |
| `tests/test_ruecknahme_rundreise.py` (**neu**) | Der mutationsfeste Rundreise-Test je Art und die Vollstaendigkeit von `VERFOLGT`. |

### Aufgabenuebersicht

| # | Aufgabe | Deliverable |
|---|---|---|
| 1 | Schema und Loeschzusage | zwei Tabellen, `TABELLEN_MIT_CHAT_ID`, Migration laeuft auf einer Altdatenbank |
| 2 | `ruecknahme.py` -- die reine Diff-Logik | `VERFOLGT`, `plan`, `schritte`, `gleich`, `verweise` |
| 3 | Schnappschuss und Speichern in `repo.py` | `schnappschuss`, `lege_erkenner_lauf_an`, die drei Leser |
| 4 | `repo.nimm_erkenner_lauf_zurueck` | die eine Transaktion: pruefen, anwenden, stempeln |
| 5 | Texte, `ART_UNDO`, Leisten-Bausteine | Knopf DE/EN, `undo_leiste`, Reduktion statt Abnahme |
| 6 | Der Handler | `_wirkung_undo` in `_WIRKUNGEN`, Strukturtest gruen |
| 7 | Einhaengen in `erkenner.laufe` | Knopf steht unter jeder Notiert-Meldung |
| 8 | Die sieben Abnahmepunkte | `tests/test_undo_knopf.py` |
| 9 | Rundreise je Art, mutationsfest | `tests/test_ruecknahme_rundreise.py` |
| 10 | Web bedingt, AGENTS.md, Abschluss | Doku, Uebergaben, Suite >= 4350 |

### Abnahmepunkt → Test → Aufgabe

| Abnahmepunkt der Karte | Testname | Aufgabe | Mutation, die ihn rot macht |
|---|---|---|---|
| Kernthema gesetzt → Undo → wie vorher (auch "leer") | `test_undo_stellt_das_kernthema_wieder_her`, `test_undo_stellt_ein_leeres_feld_wieder_her` | 8 | in `nimm_erkenner_lauf_zurueck` `vorher` statt auf `NULL` auf `nachher` setzen (also nichts tun) |
| Figur neu angelegt → Undo → Figur weg, keine Waisen | `test_undo_nimmt_eine_neue_figur_weich_zurueck`, `test_undo_laesst_keine_waisen_in_szene_figur` | 8 | `entfernt_am` nicht setzen (Figur bleibt in `repo.figuren`) / den `szene_figur`-Schritt ueberspringen (Verknuepfung bleibt) |
| Szene geplant → Undo → Szene weg | `test_undo_nimmt_eine_geplante_szene_zurueck` | 8 | `"szene"` aus `ruecknahme.WEICH` entfernen |
| Zwei Aenderungen in einer Meldung → ein Undo nimmt beide zurueck | `test_ein_undo_nimmt_beide_aenderungen_der_meldung_zurueck` | 8 | in `erkenner_lauf_schritte` `LIMIT 1` einbauen |
| Feld nach dem Lauf erneut geaendert → Undo aendert nichts, meldet es | `test_undo_aendert_nichts_wenn_das_feld_seitdem_anders_ist`, `test_ruecknahme_ist_alles_oder_nichts` | 8, 4 | die Wertpruefung weglassen / je Schritt einzeln `commit()` statt einer Transaktion |
| Doppeltipp → einmal gewirkt | `test_doppeltipp_wirkt_einmal`, `test_ruecknahme_wirkt_nur_einmal` | 8, 4 | `AND zurueckgenommen_am IS NULL` im UPDATE weglassen |
| Dortmund deutsch, Padua englisch, Verhalten gleich | `test_undo_texte_dortmund_deutsch`, `test_undo_knopf_traegt_in_padua_englisch`, `test_undo_wirkt_in_padua_genauso` | 5, 8 | den Text nackt lesen (`_TEXT_UNDO_KNOPF` statt `T._TEXT_UNDO_KNOPF`) |

Zusaetzliche mutationsfeste Waechter:

| Test | Aufgabe | Mutation, die ihn rot macht |
|---|---|---|
| `test_rundreise_je_art_stellt_den_dump_wieder_her` | 9 | eine Spalte aus `VERFOLGT` streichen; `_schmelze_platzhalter_ein` nicht mit erfassen |
| `test_verfolgt_deckt_jede_geschriebene_spalte` | 9 | eine von `wende_an` geschriebene Spalte nach `AUSSEN` verschieben |
| `test_phase_bleibt_nach_undo` | 8 | `phase` aus `AUSSEN["arbeitsstand"]` entfernen |
| `test_usa_bleibt_nach_undo` | 8 | `gruppe` in `VERFOLGT` aufnehmen |
| `test_journal_bleibt_stehen_und_bekommt_eine_zeile` | 8 | `journal` in `VERFOLGT` aufnehmen; die Ruecknahme-Journalzeile weglassen |
| `test_undo_verfallen_laesst_die_grundleiste` | 8 | `repo.verfallen_lassen` im Handler weglassen |
| `test_alte_leiste_behaelt_ihren_undo_knopf` | 5 | `_entferne_tastatur` statt `_reduziere_auf_undo` |
| `test_ruecknahme_enthaelt_kein_sql` | 2 | ein `conn.execute` nach `ruecknahme.py` schreiben |
| `test_verweise_kommen_aus_dem_schema` | 2 | die Liste von Hand aufzaehlen statt aus `db.SCHEMA` lesen |
| `test_kein_lauf_ohne_schritte_und_ohne_zeilen` | 7 | den Lauf auch bei leerem Diff anlegen (Knopf ohne Wirkung) |

---

### Aufgabe 1: Schema und Loeschzusage

**Dateien:**
- Aendern: `interview_theater/db.py` (`SCHEMA` nach dem `knopf`-Block ~Zeile 695, `TABELLEN_MIT_CHAT_ID` ~Zeile 725)
- Test: `tests/test_ruecknahme_repo.py` (neu)

**Schnittstellen:**
- Liefert: die Tabellen `erkenner_lauf` und `erkenner_lauf_schritt`, beide mit
  `chat_id`, beide in `db.TABELLEN_MIT_CHAT_ID`.

- [x] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_ruecknahme_repo.py`:

```python
"""Die Ablage der Ruecknahme: Schema, Schnappschuss, Speichern, die eine
Transaktion (Karte U, 01.10.2026).

Kein Netz, kein Modell -- die Schicht darunter ist SQLite.
"""

import json

import pytest

from interview_theater import db, repo


def test_beide_tabellen_stehen_im_schema(conn):
    """Additiv per CREATE TABLE IF NOT EXISTS, wie jede Tabelle hier."""
    vorhandene = {
        zeile[0]
        for zeile in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene


def test_beide_tabellen_tragen_chat_id_und_stehen_in_der_loeschzusage(conn):
    """Jede Tabelle ausser bot_zustand hat chat_id -- daran haengt
    db.loesche_gruppe (AGENTS.md)."""
    for tabelle in ("erkenner_lauf", "erkenner_lauf_schritt"):
        spalten = {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}
        assert "chat_id" in spalten, tabelle
        assert tabelle in db.TABELLEN_MIT_CHAT_ID, tabelle


def test_loeschen_einer_gruppe_nimmt_die_laeufe_mit(conn):
    conn.execute(
        "INSERT INTO erkenner_lauf (chat_id, meldung, erstellt_am) "
        "VALUES (1, 'Kernthema: X', '2026-10-01T10:00:00')"
    )
    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    conn.execute(
        "INSERT INTO erkenner_lauf_schritt "
        "(chat_id, lauf_id, tabelle, schluessel, art, vorher, nachher, erstellt_am) "
        "VALUES (1, ?, 'arbeitsstand', ?, 'geaendert', ?, ?, '2026-10-01T10:00:00')",
        (lauf_id, json.dumps({"chat_id": 1}), json.dumps({"kernthema": None}),
         json.dumps({"kernthema": "X"})),
    )
    conn.commit()

    db.loesche_gruppe(conn, 1)

    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM erkenner_lauf_schritt"
    ).fetchone()[0] == 0


def test_eine_altdatenbank_ohne_die_tabellen_laeuft_durch(tmp_path):
    """db.initialisiere ist additiv: eine Datenbank, die vor dieser Aenderung
    entstanden ist, bekommt die Tabellen beim Start -- ohne
    SCHEMA_VERSION-Schritt, weil nichts umgedeutet wird."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    alt.executescript(db.SCHEMA)
    alt.execute("DROP TABLE erkenner_lauf")
    alt.execute("DROP TABLE erkenner_lauf_schritt")
    alt.commit()
    version_vorher = alt.execute("PRAGMA user_version").fetchone()[0]
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)

    vorhandene = {
        z[0] for z in neu.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene
    assert neu.execute("PRAGMA user_version").fetchone()[0] == version_vorher
    assert db.SCHEMA_VERSION == 3, "keine Erhoehung: es wird nichts umgedeutet"
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py -q -p no:cacheprovider`
Erwartet: FAIL -- `assert {'erkenner_lauf', 'erkenner_lauf_schritt'} <= vorhandene`

- [x] **Schritt 3: Schema ergaenzen**

In `interview_theater/db.py`, in `SCHEMA` nach dem `CREATE INDEX ... idx_knopf_chat`
und vor `CREATE TABLE IF NOT EXISTS vorfall`:

```sql
-- Die Ruecknahme eines Erkennerlaufs (Karte U, 01.10.2026).
--
-- Der Anlass (Birk, 30.09.2026): Korpus und Simulation bilden die echte
-- Chatrealitaet der Studierenden nur begrenzt ab, und ein falsch
-- gespeicherter Wert darf deshalb nicht STILL bleiben. Unter jeder
-- "Notiert:"-Meldung steht seitdem ein Undo-Knopf, und was er
-- wiederherstellt, liegt hier -- **nicht** als Nachbau je Erkenner-Art
-- (das waere eine zweite Wahrheit neben erkenner._wende_*_an), sondern als
-- DIFFERENZ zweier Schnappschuesse um ``erkenner.wende_an`` herum
-- (interview_theater/ruecknahme.py).
--
-- ``meldung`` sind die Zeilen der Notiert-Meldung ohne Kopf -- dieselbe
-- Quelle wie die Meldung selbst (erkenner.undo_zeilen), damit "Rueckgaengig
-- gemacht:" nicht anders klingt als "Notiert:". ``message_id`` ist die
-- Nachricht, unter der der Knopf haengt: nach einer wirksamen Ruecknahme
-- werden ihre Grundleisten-Knoepfe verfallen gelassen, sonst schriebe
-- "Ja, speichern" den gerade zurueckgenommenen Wert wieder (der Wert steckt
-- im Knopf). ``zurueckgenommen_am`` ist die zweite Idempotenz-Sperre neben
-- ``knopf.benutzt_am`` -- bedingtes UPDATE in derselben Transaktion wie die
-- Ruecknahme, SQLite entscheidet.
CREATE TABLE IF NOT EXISTS erkenner_lauf (
  id                  INTEGER PRIMARY KEY,
  chat_id             INTEGER NOT NULL,
  meldung             TEXT,
  message_id          INTEGER,
  erstellt_am         TEXT NOT NULL,
  zurueckgenommen_am  TEXT
);
CREATE INDEX IF NOT EXISTS idx_erkenner_lauf_chat ON erkenner_lauf(chat_id, id);

-- Ein Schritt der Ruecknahme: eine Zeile einer verfolgten Tabelle.
--
-- ``schluessel`` ist das JSON-Objekt der Primaerschluesselspalten
-- (sort_keys, weil ``szene_figur`` einen zusammengesetzten hat),
-- ``vorher``/``nachher`` die JSON-Objekte der verglichenen Spalten.
-- ``art``: ``geaendert`` (beide da), ``angelegt`` (nur nachher -- die
-- Ruecknahme entfernt weich, N3) oder ``geloescht`` (nur vorher -- die
-- Ruecknahme fuegt wieder ein; im Betrieb nur bei ``szene_figur``,
-- repo.setze_szene_figuren loescht dort hart).
--
-- ``nachher`` ist zugleich die "Seitdem geaendert"-Probe: stimmt der
-- aktuelle Wert nicht mehr damit, wird NICHTS geaendert.
CREATE TABLE IF NOT EXISTS erkenner_lauf_schritt (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  lauf_id      INTEGER NOT NULL,
  tabelle      TEXT NOT NULL,
  schluessel   TEXT NOT NULL,
  art          TEXT NOT NULL,           -- geaendert|angelegt|geloescht
  vorher       TEXT,
  nachher      TEXT,
  erstellt_am  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_erkenner_lauf_schritt_lauf
  ON erkenner_lauf_schritt(lauf_id);
```

Und in `TABELLEN_MIT_CHAT_ID`, hinter `"knopf",`:

```python
    # Karte U (01.10.2026): die Ruecknahme eines Erkennerlaufs.
    "erkenner_lauf",
    "erkenner_lauf_schritt",
```

- [x] **Schritt 4: Test laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py tests/test_db.py -q -p no:cacheprovider`
Erwartet: `4 passed` in der neuen Datei, `tests/test_db.py` unveraendert gruen
(keine Zeile `F`).

- [x] **Schritt 5: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4354 passed, 1 skipped` (4350 + 4 neue)

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/db.py tests/test_ruecknahme_repo.py
git commit -m "Karte U: Tabellen erkenner_lauf und erkenner_lauf_schritt (Loeschzusage, additiv)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 2: `ruecknahme.py` -- die reine Diff-Logik

**Dateien:**
- Erstellen: `interview_theater/ruecknahme.py`
- Test: `tests/test_ruecknahme.py` (neu)

**Schnittstellen:**
- Verbraucht: `db._tabellenspalten_aus_schema()` (Aufgabe 1 hat das Schema
  erweitert, aber dieses Modul liest nur die **verfolgten** Tabellen).
- Liefert:
  - `VERFOLGT: tuple[str, ...]` -- die immer verfolgten Tabellen
  - `MATERIAL: dict[str, tuple[str, ...]]` -- Tabelle → verfolgte Spalten,
    nur bei `transkript_korrigieren`
  - `SCHLUESSEL: dict[str, tuple[str, ...]]` -- Tabelle → Primaerschluesselspalten
  - `AUSSEN: dict[str, frozenset[str]]` -- Tabelle → nie verglichene Spalten
  - `WEICH`, `HART`, `GELEERT: tuple[str, ...]`
  - `ZEILEN_OHNE_UNDO: frozenset[str]`
  - `plan(arten: Iterable[str]) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]`
    -- Tabelle → (Schluesselspalten, verglichene Spalten)
  - `schritte(vorher: dict, nachher: dict) -> list[dict]` -- je Schritt
    `{"tabelle", "schluessel", "art", "vorher", "nachher"}` mit `schluessel`
    als dict und `vorher`/`nachher` als dict oder `None`
  - `gleich(a, b) -> bool`
  - `verweise() -> tuple[tuple[str, str, str], ...]` -- (Tabelle, Spalte,
    Zieltabelle)

- [x] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_ruecknahme.py`:

```python
"""Die reine Diff-Logik der Ruecknahme (Karte U, 01.10.2026).

Kein SQL, keine Datenbank, kein Netz: zwei Dicts rein, Schritte raus. Genau
das ist der Punkt der Aufteilung -- die Entscheidung, WAS zurueckgenommen
wird, ist hier pruefbar, ohne eine Datenbank zu bauen.
"""

import ast
import inspect
import pathlib

from interview_theater import ruecknahme


def test_verfolgt_traegt_die_inhaltstabellen_und_nicht_die_gruppe():
    assert set(ruecknahme.VERFOLGT) == {
        "arbeitsstand", "figur", "szene", "szene_figur", "festlegung",
    }
    assert "gruppe" not in ruecknahme.VERFOLGT, "USA-Einwilligung: eigene Knoepfe"
    assert "journal" not in ruecknahme.VERFOLGT, "nur-anhaengend (AGENTS.md)"


def test_die_phasenbuchhaltung_und_zeitstempel_stehen_aussen_vor():
    aussen = ruecknahme.AUSSEN["arbeitsstand"]
    assert {"phase", "phase_angeboten", "phase_gesetzt_am", "geaendert_am"} <= aussen
    assert "kernthema" not in aussen


def test_spaeter_geschriebene_felder_stehen_aussen_vor():
    """Was erst ein anderer, spaeterer Lauf schreibt, wird nie verglichen --
    sonst scheiterte ein Kernthema-Undo an einem Sprachprofil, das ein Thread
    danach geschrieben hat."""
    assert {"sprachprofil", "zitate", "geprueft_am"} <= ruecknahme.AUSSEN["figur"]
    assert {"volltext", "prosa", "form", "stil"} <= ruecknahme.AUSSEN["szene"]


def test_plan_nimmt_material_nur_mit_transkript_korrektur():
    ohne = ruecknahme.plan(["kernthema_setzen", "figur_setzen"])
    assert set(ohne) == set(ruecknahme.VERFOLGT)

    mit = ruecknahme.plan(["kernthema_setzen", "transkript_korrigieren"])
    assert set(mit) == set(ruecknahme.VERFOLGT) | set(ruecknahme.MATERIAL)
    assert mit["aufnahme"] == (("id",), ("transkript",))


def test_plan_liest_die_spalten_aus_dem_schema_und_nicht_aus_einer_liste():
    """Eine neue Spalte in db.SCHEMA wird automatisch verfolgt."""
    from interview_theater import db

    soll = {
        name for name, _ in db._tabellenspalten_aus_schema()["figur"]
    } - ruecknahme.AUSSEN["figur"] - {"id"}
    assert set(ruecknahme.plan(["figur_setzen"])["figur"][1]) == soll


def test_schluessel_von_szene_figur_ist_zusammengesetzt():
    assert ruecknahme.SCHLUESSEL["szene_figur"] == ("szene_id", "figur_id")
    assert ruecknahme.SCHLUESSEL["arbeitsstand"] == ("chat_id",)


def test_geaenderte_spalte_wird_ein_schritt():
    vorher = {"arbeitsstand": {'{"chat_id": 1}': {"kernthema": None, "rahmen": "Bahnhof"}}}
    nachher = {"arbeitsstand": {'{"chat_id": 1}': {"kernthema": "Ankommen", "rahmen": "Bahnhof"}}}

    schritte = ruecknahme.schritte(vorher, nachher)

    assert len(schritte) == 1
    s = schritte[0]
    assert s["tabelle"] == "arbeitsstand"
    assert s["art"] == "geaendert"
    # Nur die geaenderte Spalte, nicht die ganze Zeile: sonst schriebe die
    # Ruecknahme ueber etwas, das dieser Lauf nie angefasst hat.
    assert s["vorher"] == {"kernthema": None}
    assert s["nachher"] == {"kernthema": "Ankommen"}


def test_unveraenderte_zeile_wird_kein_schritt():
    gleich = {"figur": {'{"id": 3}': {"name": "Mira", "beschreibung": "laut"}}}
    assert ruecknahme.schritte(gleich, dict(gleich)) == []


def test_neue_zeile_wird_angelegt_schritt():
    schritte = ruecknahme.schritte(
        {"figur": {}},
        {"figur": {'{"id": 3}': {"name": "Mira", "beschreibung": "laut"}}},
    )
    assert [(s["art"], s["vorher"]) for s in schritte] == [("angelegt", None)]
    assert schritte[0]["schluessel"] == {"id": 3}


def test_verschwundene_zeile_wird_geloescht_schritt():
    schritte = ruecknahme.schritte(
        {"szene_figur": {'{"figur_id": 3, "szene_id": 7}':
                         {"chat_id": 1, "szene_id": 7, "figur_id": 3}}},
        {"szene_figur": {}},
    )
    assert [(s["art"], s["nachher"]) for s in schritte] == [("geloescht", None)]
    assert schritte[0]["vorher"]["figur_id"] == 3


def test_schritte_sind_stabil_sortiert():
    """Zwei Laeufe ueber denselben Diff liefern dieselbe Reihenfolge -- sonst
    waere der Rundreise-Test in Aufgabe 9 vom dict-Zufall abhaengig."""
    vorher = {"figur": {'{"id": 2}': {"name": "A"}, '{"id": 1}': {"name": "B"}}}
    nachher = {"figur": {'{"id": 2}': {"name": "A2"}, '{"id": 1}': {"name": "B2"}}}
    einmal = [(s["tabelle"], s["schluessel"]) for s in ruecknahme.schritte(vorher, nachher)]
    assert einmal == sorted(einmal, key=lambda p: (p[0], sorted(p[1].items())))


def test_gleich_ueberlebt_den_typwechsel_zwischen_zahl_und_text():
    """``figuren_anzahl`` kommt als int aus erkenner.figurenzahl_aus und als
    str aus einem Knopf -- ein Typwechsel darf keine Aenderung sein."""
    assert ruecknahme.gleich(4, 4)
    assert ruecknahme.gleich(None, None)
    assert not ruecknahme.gleich(None, "")
    assert not ruecknahme.gleich("Ankommen", "ankommen")


def test_verweise_kommen_aus_dem_schema():
    """Die Tabellen, die auf eine figur oder szene zeigen -- hergeleitet, nicht
    aufgezaehlt: eine spaeter dazukommende referenzierende Tabelle faellt hier
    auf, bevor sie Waisen erzeugt.

    Pruefkommando: grep -n "figur_id\\|szene_id" interview_theater/db.py
    """
    assert set(ruecknahme.verweise()) == {
        ("szene_figur", "szene_id", "szene"),
        ("szene_figur", "figur_id", "figur"),
        ("schaerfung", "szene_id", "szene"),
        ("schaerfung", "figur_id", "figur"),
        ("szenenfassung", "szene_id", "szene"),
    }


def test_ruecknahme_enthaelt_kein_sql():
    """Die Schichtzusage: alles SQL steht in repo.py. Hier stehen reine
    Funktionen -- ``db`` wird importiert, aber nur fuer die Spaltenliste
    (db._tabellenspalten_aus_schema), nicht fuer eine Abfrage."""
    quelle = pathlib.Path(inspect.getfile(ruecknahme)).read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    aufrufe = {
        ast.unparse(k.func)
        for k in ast.walk(baum)
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
    }
    assert not {a for a in aufrufe if a.endswith((".execute", ".executemany",
                                                  ".executescript", ".commit"))}
    assert "conn" not in {
        a.arg for k in ast.walk(baum)
        if isinstance(k, ast.arguments) for a in k.args
    }


def test_ruecknahme_traegt_keinen_nutzertext():
    """Die Wortlaute stehen in knoepfe/texte.py (K1 aus Karte A1) -- dieses
    Modul ist Logik und kommt ohne ``sprache.Texte`` aus."""
    quelle = pathlib.Path(inspect.getfile(ruecknahme)).read_text(encoding="utf-8")
    assert "sprache.Texte" not in quelle
    assert not [
        n for n in dir(ruecknahme)
        if n.lstrip("_").startswith(("TEXT", "MELDUNG", "ZEILE", "ANTWORT"))
    ]
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_ruecknahme.py -q -p no:cacheprovider`
Erwartet: FAIL -- `ModuleNotFoundError: No module named 'interview_theater.ruecknahme'`

- [x] **Schritt 3: Das Modul schreiben**

`interview_theater/ruecknahme.py`:

```python
"""Was ein Undo-Knopf zurueckdreht -- die reine Differenz zweier
Schnappschuesse (Karte U, 01.10.2026).

**Warum Diff und nicht Nachbau je Art.** Jede ``erkenner._wende_*_an``-Funktion
nachzubilden ("was schreibt ``kernthema_setzen``?") waere eine zweite Wahrheit
neben der ersten, und sie wuerde beim naechsten Umbau still ausscheren: die
Platzhalter-Zusammenfuehrung (``repo.fuehre_figur_zusammen``) beruehrt drei
Tabellen auf einmal, ``repo.korrigiere_transkripte`` vier. Stattdessen nimmt
``erkenner.laufe`` **vor** und **nach** ``wende_an`` einen Schnappschuss der
verfolgten Tabellen dieser ``chat_id``; was hier daraus entsteht, sind die
Schritte, und ein Umbau an den Schreibpfaden kommt automatisch mit.

**Reine Funktionen, kein SQL.** Der Schnappschuss kommt aus
``repo.schnappschuss``, angewendet wird in ``repo.nimm_erkenner_lauf_zurueck``
-- dieses Modul kennt keine Verbindung. ``db`` wird importiert, aber nur fuer
``_tabellenspalten_aus_schema``: die verglichenen Spalten werden **aus dem
Schema hergeleitet**, damit eine spaeter dazukommende Spalte nicht vergessen
wird (``tests/test_ruecknahme_rundreise.py`` haelt das fest).

**Kein Nutzertext.** Die Wortlaute stehen in ``knoepfe/texte.py``, wie alle
Texte des Knopf-Pakets (K1 aus Karte A1).
"""

import json
from typing import Any, Iterable

from interview_theater import db

#: Die Tabellen, die bei JEDEM Erkennerlauf verfolgt werden -- der Inhalt,
#: den die Gruppe erarbeitet. ``gruppe`` fehlt bewusst (USA-Einwilligung und
#: Interviewmodus haben eigene Knoepfe und eine eigene Nachfrage), ``journal``
#: ebenfalls: es ist nur-anhaengend, die Zeilen des Laufs bleiben stehen und
#: die Ruecknahme haengt eine neue an (AGENTS.md).
VERFOLGT = ("arbeitsstand", "figur", "szene", "szene_figur", "festlegung")

#: Nur bei einem ``transkript_korrigieren`` im Lauf -- und dann nur diese
#: Spalten, nicht die ganzen Zeilen. Zwei Gruende, beide am Code gemessen:
#: ``repo.korrigiere_transkripte`` schreibt genau diese fuenf, und ein Lauf
#: kann daneben ein ``interview_beenden`` tragen, das ebenfalls in
#: ``aufnahme`` schreibt (``beendet_am``, ``status``) -- ein
#: Zeilen-Schnappschuss wuerde ein beendetes Interview wieder oeffnen.
#: Ausserdem liegen in ``aufnahme.transkript`` Megabytes.
MATERIAL = {
    "aufnahme": ("transkript",),
    "verdichtung": ("zusammenfassung",),
    "verdichtung_thema": ("thema", "kurz", "beleg_zitat"),
}

#: Die Erkenner-art, die den Materialteil zuschaltet.
ART_MATERIAL = "transkript_korrigieren"

#: Tabelle -> Primaerschluesselspalten. ``szene_figur`` hat einen
#: zusammengesetzten (db.SCHEMA: PRIMARY KEY (szene_id, figur_id)).
SCHLUESSEL = {
    "arbeitsstand": ("chat_id",),
    "figur": ("id",),
    "szene": ("id",),
    "szene_figur": ("szene_id", "figur_id"),
    "festlegung": ("id",),
    "aufnahme": ("id",),
    "verdichtung": ("id",),
    "verdichtung_thema": ("id",),
}

#: Spalten, die weder verglichen noch zurueckgesetzt werden -- je mit Grund.
#:
#: Drei Sorten: der Primaerschluessel selbst (er ist die Adresse), die
#: Zeitstempel (sie sagen nichts ueber den Inhalt), und die Felder, die
#: **ein anderer, spaeterer Lauf** schreibt und ``wende_an`` nie anfasst.
#: Die dritte Sorte ist die wichtige: ohne sie scheiterte ein Kernthema-Undo
#: daran, dass ein Sprachprofil-Thread danach ``figur.sprachprofil``
#: geschrieben hat, und ein Szenen-Undo daran, dass die Gruppe inzwischen
#: eine Form bestaetigt hat. ``szene.form`` traegt allein ein Knopfdruck:
#: ``erkenner._wende_szene_planen_an`` bildet das Feld ``form`` bewusst auf
#: ``form_vorschlag`` ab (AGENTS.md, "Die Form je Szene ist ein Vorschlag").
AUSSEN = {
    "arbeitsstand": frozenset({
        "chat_id", "geaendert_am",
        # Karte U: kein Undo fuer die Phase. Sie setzt allein die Gruppe.
        "phase", "phase_angeboten", "phase_gesetzt_am",
    }),
    "figur": frozenset({
        "id", "geaendert_am",
        # sprachprofil.py (eigener Thread), Ebene 2 der Figurenarbeit.
        "sprachprofil", "zitate", "geprueft_am",
    }),
    "szene": frozenset({
        "id", "geaendert_am",
        # Geschriebene Texte und die Entscheidungen der Gruppe per Knopf.
        "volltext", "prosa", "zusammenfassung", "fertig_am",
        "fruehere_fassungen", "form", "stil",
    }),
    "szene_figur": frozenset(),
    "festlegung": frozenset({"id", "erstellt_am"}),
}

#: Tabellen mit ``entfernt_am``: eine im Lauf ENTSTANDENE Zeile wird weich
#: entfernt, nicht geloescht (N3, "Weiches Loeschen statt Loeschen").
WEICH = ("figur", "szene", "festlegung")

#: Reine Verknuepfungszeilen ohne ``entfernt_am``: die im Lauf entstandene
#: wird geloescht -- genau das tut ``repo.setze_szene_figuren`` heute schon.
HART = ("szene_figur",)

#: Genau eine Zeile je Gruppe und kein ``entfernt_am``: eine im Lauf
#: entstandene Zeile wird GELEERT statt geloescht. Jeder Leser prueft
#: ``(stand[feld] or "")``, eine leere Zeile ist also von keiner Zeile nicht
#: zu unterscheiden -- und die Zeile zu loeschen hiesse, die
#: Phasen-Buchhaltung in derselben Zeile mitzureissen.
GELEERT = ("arbeitsstand",)

#: Die Arten, deren Meldungszeile NICHT in "Rueckgaengig gemacht:" gehoert.
#: Eine Ausschluss- und keine Einschlussliste: ``entschieden`` ist in der
#: Meldung still, setzt aber nebenbei ``arbeitsstand.figuren_anzahl``
#: (erkenner._wende_journal_an) -- diese Zeile MUSS mitgenannt werden.
ZEILEN_OHNE_UNDO = frozenset({"phase_setzen", "szene_usa"})

#: Spaltennamen, die auf eine verfolgte Tabelle zeigen.
_ZEIGT_AUF = {"figur_id": "figur", "szene_id": "szene"}


def spalten(tabelle: str) -> tuple[str, ...]:
    """Die verglichenen Spalten einer Tabelle -- aus ``db.SCHEMA`` hergeleitet
    (Materialtabellen ausgenommen, dort steht die Liste in ``MATERIAL``)."""
    if tabelle in MATERIAL:
        return MATERIAL[tabelle]
    aussen = AUSSEN.get(tabelle, frozenset())
    alle = db._tabellenspalten_aus_schema()[tabelle]
    return tuple(name for name, _ in alle if name not in aussen)


def plan(arten: Iterable[str]) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Tabelle -> (Schluesselspalten, verglichene Spalten) fuer diesen Lauf.

    Die Materialtabellen kommen nur dazu, wenn im Lauf eine
    Transkriptkorrektur steckt: sonst waere jeder Erkennerlauf ein Lesen aller
    Transkripte einer Gruppe."""
    tabellen = list(VERFOLGT)
    if ART_MATERIAL in set(arten):
        tabellen += list(MATERIAL)
    return {t: (SCHLUESSEL[t], spalten(t)) for t in tabellen}


def gleich(a: Any, b: Any) -> bool:
    """Sind zwei Werte derselbe -- nach JSON-Rundreise?

    Die Rundreise ist der Punkt: ``arbeitsstand.figuren_anzahl`` kommt als
    ``int`` aus ``erkenner.figurenzahl_aus`` und als ``str`` aus einem Knopf.
    Verglichen wird, was nach ``json.dumps``/``loads`` dasteht -- also
    typtreu, aber ohne die Unterschiede, die erst beim Speichern entstehen."""
    return json.loads(json.dumps(a)) == json.loads(json.dumps(b))


def _geaendert(vorher: dict, nachher: dict) -> tuple[dict, dict]:
    """Nur die Spalten, die sich unterscheiden -- Spalte fuer Spalte, nicht
    die ganze Zeile. Sonst schriebe die Ruecknahme ueber Spalten, die dieser
    Lauf nie angefasst hat."""
    namen = [k for k in nachher if not gleich(vorher.get(k), nachher[k])]
    return ({k: vorher.get(k) for k in namen}, {k: nachher[k] for k in namen})


def schritte(vorher: dict, nachher: dict) -> list[dict]:
    """Die Ruecknahme-Schritte aus zwei Schnappschuessen.

    Ein Schnappschuss ist ``{Tabelle: {Schluessel-JSON: {Spalte: Wert}}}``
    (so liefert ihn ``repo.schnappschuss``). Ergebnis: je Zeile hoechstens
    ein Schritt, stabil sortiert nach (Tabelle, Schluessel) -- zwei Laeufe
    ueber denselben Diff liefern dieselbe Reihenfolge."""
    fertig = []
    for tabelle in sorted(set(vorher) | set(nachher)):
        alt = vorher.get(tabelle, {})
        neu = nachher.get(tabelle, {})
        for roh in sorted(set(alt) | set(neu)):
            schluessel = json.loads(roh)
            if roh in alt and roh in neu:
                a, n = _geaendert(alt[roh], neu[roh])
                if not n:
                    continue
                art, a_wert, n_wert = "geaendert", a, n
            elif roh in neu:
                art, a_wert, n_wert = "angelegt", None, dict(neu[roh])
            else:
                art, a_wert, n_wert = "geloescht", dict(alt[roh]), None
            fertig.append({
                "tabelle": tabelle, "schluessel": schluessel, "art": art,
                "vorher": a_wert, "nachher": n_wert,
            })
    return fertig


def verweise() -> tuple[tuple[str, str, str], ...]:
    """(Tabelle, Spalte, Zieltabelle) fuer jede Spalte, die auf eine ``figur``
    oder ``szene`` zeigt -- **aus ``db.SCHEMA`` hergeleitet**, nicht
    aufgezaehlt.

    Gebraucht fuer die Waisen-Probe: zeigt jetzt eine Zeile auf eine im Lauf
    neu angelegte Figur oder Szene und ist sie nicht selbst im Lauf
    entstanden, gilt das als "seitdem geaendert" -- sonst hinterliesse die
    Ruecknahme eine Waise. Kommt eine neue referenzierende Tabelle dazu, steht
    sie hier automatisch (Pruefkommando:
    ``grep -n "figur_id\\|szene_id" interview_theater/db.py``)."""
    return tuple(
        (tabelle, name, _ZEIGT_AUF[name])
        for tabelle, felder in db._tabellenspalten_aus_schema().items()
        for name, _ in felder
        if name in _ZEIGT_AUF
    )
```

- [x] **Schritt 4: Test laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_ruecknahme.py -q -p no:cacheprovider`
Erwartet: `15 passed`

- [x] **Schritt 5: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4369 passed, 1 skipped`

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/ruecknahme.py tests/test_ruecknahme.py
git commit -m "Karte U: ruecknahme.py -- die Ruecknahme als Diff zweier Schnappschuesse

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 3: Schnappschuss und Speichern in `repo.py`

**Dateien:**
- Aendern: `interview_theater/repo.py` (neuer Abschnitt hinter `beanspruche_knopf`, ~Zeile 3145)
- Test: `tests/test_ruecknahme_repo.py` (erweitern)

**Schnittstellen:**
- Verbraucht: `ruecknahme.plan` (Aufgabe 2) -- als **Parameter**, nicht als
  Import: `repo.py` ist die Ablage-Schicht und liest nicht nach oben.
- Liefert:
  - `schnappschuss(conn, chat_id, plan) -> dict[str, dict[str, dict]]`
  - `lege_erkenner_lauf_an(conn, chat_id, meldung, schritte) -> int | None`
  - `merke_erkenner_lauf_nachricht(conn, lauf_id, message_id) -> None`
  - `hole_erkenner_lauf(conn, lauf_id) -> sqlite3.Row | None`
  - `erkenner_lauf_schritte(conn, lauf_id) -> list[sqlite3.Row]`
  - `offene_knoepfe_der_nachricht(conn, chat_id, message_id, art=None) -> list[sqlite3.Row]`

- [x] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_ruecknahme_repo.py` anhaengen:

```python
from interview_theater import ruecknahme


def _schnappschuss(conn, arten=("kernthema_setzen",)):
    return repo.schnappschuss(conn, 1, ruecknahme.plan(arten))


def test_schnappschuss_liefert_je_tabelle_die_zeilen_nach_schluessel(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Mira", "laut")

    stand = _schnappschuss(conn, ("kernthema_setzen", "figur_setzen"))

    assert set(stand) == set(ruecknahme.VERFOLGT)
    assert stand["arbeitsstand"][json.dumps({"chat_id": 1}, sort_keys=True)][
        "kernthema"] == "Ankommen"
    figur = repo.hole_figur(conn, 1, "Mira")
    schluessel = json.dumps({"id": figur["id"]}, sort_keys=True)
    assert stand["figur"][schluessel]["beschreibung"] == "laut"
    assert "geaendert_am" not in stand["figur"][schluessel], "Zeitstempel bleiben aussen"


def test_schnappschuss_sieht_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    repo.setze_arbeitsstand(conn, 2, "kernthema", "Fremd")
    repo.setze_figur(conn, 2, "Fremdfigur", "x")

    stand = _schnappschuss(conn, ("kernthema_setzen", "figur_setzen"))

    assert stand["arbeitsstand"] == {}
    assert stand["figur"] == {}


def test_schnappschuss_nimmt_material_nur_mit_korrektur(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "d", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "wir haben gepoekt")

    ohne = _schnappschuss(conn, ("kernthema_setzen",))
    mit = _schnappschuss(conn, ("transkript_korrigieren",))

    assert "aufnahme" not in ohne
    schluessel = json.dumps({"id": aufnahme_id}, sort_keys=True)
    assert mit["aufnahme"][schluessel] == {"transkript": "wir haben gepoekt"}


def test_schnappschuss_nimmt_auch_weich_entfernte_zeilen_mit(conn):
    """Sonst saehe ein Undo eine im Lauf weich entfernte Figur als
    "verschwunden" und fuegte sie als geloescht-Schritt neu ein, statt
    ``entfernt_am`` zurueckzunehmen."""
    repo.setze_figur(conn, 1, "Mira", "laut")
    repo.entferne_figur(conn, 1, "Mira")

    stand = _schnappschuss(conn, ("figur_setzen",))

    assert len(stand["figur"]) == 1
    (zeile,) = stand["figur"].values()
    assert zeile["entfernt_am"] is not None


def test_lege_erkenner_lauf_an_speichert_meldung_und_schritte(conn):
    schritte = [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {"kernthema": None},
         "nachher": {"kernthema": "Ankommen"}},
    ]
    lauf_id = repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: Ankommen", schritte)

    lauf = repo.hole_erkenner_lauf(conn, lauf_id)
    assert lauf["chat_id"] == 1
    assert lauf["meldung"] == "Kernthema: Ankommen"
    assert lauf["message_id"] is None
    assert lauf["zurueckgenommen_am"] is None

    (gespeichert,) = repo.erkenner_lauf_schritte(conn, lauf_id)
    assert gespeichert["tabelle"] == "arbeitsstand"
    assert json.loads(gespeichert["schluessel"]) == {"chat_id": 1}
    assert json.loads(gespeichert["nachher"]) == {"kernthema": "Ankommen"}


def test_kein_lauf_ohne_schritte_und_keiner_ohne_meldung(conn):
    """Ein Knopf, der nichts zurueckzunehmen hat, waere ein Knopf ohne
    Wirkung -- und eine Ruecknahme ohne Zeilen koennte nicht sagen, WAS sie
    zurueckgenommen hat."""
    assert repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: X", []) is None
    assert repo.lege_erkenner_lauf_an(conn, 1, "", [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {}, "nachher": {"kernthema": "X"}},
    ]) is None
    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_merke_erkenner_lauf_nachricht(conn):
    lauf_id = repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: X", [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {}, "nachher": {"kernthema": "X"}},
    ])
    repo.merke_erkenner_lauf_nachricht(conn, lauf_id, 4242)
    assert repo.hole_erkenner_lauf(conn, lauf_id)["message_id"] == 4242


def test_offene_knoepfe_der_nachricht(conn):
    a = repo.lege_knopf_an(conn, 1, "speichern", "rahmen|Bahnhof")
    b = repo.lege_knopf_an(conn, 1, "undo", "7")
    fremd = repo.lege_knopf_an(conn, 1, "speichern", "anderswo")
    repo.merke_knopf_nachricht(conn, [a, b], 500)
    repo.merke_knopf_nachricht(conn, [fremd], 501)

    alle = repo.offene_knoepfe_der_nachricht(conn, 1, 500)
    assert {k["id"] for k in alle} == {a, b}
    nur_undo = repo.offene_knoepfe_der_nachricht(conn, 1, 500, "undo")
    assert [k["id"] for k in nur_undo] == [b]

    repo.verfallen_lassen(conn, [b])
    assert repo.offene_knoepfe_der_nachricht(conn, 1, 500, "undo") == []
```

- [x] **Schritt 2: Tests laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py -q -p no:cacheprovider`
Erwartet: FAIL -- `AttributeError: module 'interview_theater.repo' has no attribute 'schnappschuss'`

- [x] **Schritt 3: Die Funktionen schreiben**

In `interview_theater/repo.py`, hinter `beanspruche_knopf` (Ende des
Knopf-Abschnitts), ein neuer Abschnitt:

```python
# --- Ruecknahme eines Erkennerlaufs (Karte U, 01.10.2026) ------------------


@_gesperrt
def offene_knoepfe_der_nachricht(
    conn: sqlite3.Connection, chat_id: int, message_id: int,
    art: str | None = None,
) -> list[sqlite3.Row]:
    """Die noch ungedrueckten Knoepfe EINER Nachricht, juengste zuerst.

    Gebraucht fuer zwei Dinge (Karte U): eine ueberholte Leisten-Nachricht auf
    ihren Undo-Knopf zu reduzieren, statt ihre Tastatur ganz abzunehmen -- und
    nach einer wirksamen Ruecknahme die Grundleisten-Knoepfe genau dieser
    Nachricht verfallen zu lassen, damit "Ja, speichern" den gerade
    zurueckgenommenen Wert nicht wieder schreibt (der Wert steckt im Knopf)."""
    wenn_art = " AND art = ?" if art else ""
    werte = [chat_id, message_id] + ([art] if art else [])
    return conn.execute(
        "SELECT * FROM knopf WHERE chat_id = ? AND message_id = ? "
        f"AND benutzt_am IS NULL{wenn_art} ORDER BY id DESC",
        werte,
    ).fetchall()


@_gesperrt
def schnappschuss(
    conn: sqlite3.Connection, chat_id: int,
    plan: dict[str, tuple[tuple[str, ...], tuple[str, ...]]],
) -> dict[str, dict[str, dict]]:
    """Der Stand der verfolgten Tabellen dieser Gruppe, Zeile fuer Zeile.

    ``plan`` kommt aus ``ruecknahme.plan`` -- Tabelle -> (Schluesselspalten,
    verglichene Spalten). Der Plan wird uebergeben und nicht hier gebaut: die
    Entscheidung, WAS verfolgt wird, ist Fachlogik (``ruecknahme.py``), und
    diese Datei liest nicht nach oben.

    Weich entfernte Zeilen kommen MIT (kein ``entfernt_am IS NULL``): sonst
    saehe der Diff eine im Lauf weich entfernte Figur als verschwunden und
    fuegte sie beim Undo neu ein, statt ``entfernt_am`` zurueckzunehmen.

    Ergebnis: ``{Tabelle: {Schluessel-JSON: {Spalte: Wert}}}``. Der Schluessel
    ist ``json.dumps(..., sort_keys=True)``, damit er bei einem
    zusammengesetzten Schluessel (``szene_figur``) stabil bleibt."""
    fertig: dict[str, dict[str, dict]] = {}
    for tabelle, (schluesselspalten, spalten) in plan.items():
        namen = list(dict.fromkeys(list(schluesselspalten) + list(spalten)))
        auswahl = ", ".join(namen)
        zeilen = conn.execute(
            f"SELECT {auswahl} FROM {tabelle} WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        fertig[tabelle] = {
            json.dumps({k: zeile[k] for k in schluesselspalten}, sort_keys=True):
                {k: zeile[k] for k in spalten}
            for zeile in zeilen
        }
    return fertig


@_gesperrt
def lege_erkenner_lauf_an(
    conn: sqlite3.Connection, chat_id: int, meldung: str,
    schritte: list[dict],
) -> int | None:
    """Speichert die Ruecknahme-Schritte eines Erkennerlaufs und liefert die
    Lauf-id -- oder ``None``, wenn es nichts anzulegen gab.

    ``None`` bei leeren Schritten (ein Knopf ohne Wirkung waere schlimmer als
    keiner) und bei leerer Meldung (eine Ruecknahme, die nicht sagen kann, WAS
    sie zurueckgenommen hat, ist keine). Alles in EINER Transaktion: ein Lauf
    mit halben Schritten wuerde beim Undo den Stand halb wiederherstellen."""
    if not schritte or not (meldung or "").strip():
        return None
    jetzt = _jetzt()
    cur = conn.execute(
        "INSERT INTO erkenner_lauf (chat_id, meldung, erstellt_am) VALUES (?, ?, ?)",
        (chat_id, meldung, jetzt),
    )
    lauf_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO erkenner_lauf_schritt "
        "(chat_id, lauf_id, tabelle, schluessel, art, vorher, nachher, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                chat_id, lauf_id, s["tabelle"],
                json.dumps(s["schluessel"], sort_keys=True), s["art"],
                None if s["vorher"] is None else json.dumps(s["vorher"], sort_keys=True),
                None if s["nachher"] is None else json.dumps(s["nachher"], sort_keys=True),
                jetzt,
            )
            for s in schritte
        ],
    )
    conn.commit()
    return lauf_id


@_gesperrt
def merke_erkenner_lauf_nachricht(
    conn: sqlite3.Connection, lauf_id: int, message_id: int
) -> None:
    """Haelt fest, unter welcher Nachricht der Undo-Knopf dieses Laufs haengt
    -- gebraucht, um nach der Ruecknahme genau ihre Grundleiste verfallen zu
    lassen."""
    conn.execute(
        "UPDATE erkenner_lauf SET message_id = ? WHERE id = ?",
        (message_id, lauf_id),
    )
    conn.commit()


@_gesperrt
def hole_erkenner_lauf(conn: sqlite3.Connection, lauf_id: int) -> sqlite3.Row | None:
    """Der Lauf zu einer id, egal ob schon zurueckgenommen -- der Aufrufer muss
    den Unterschied kennen, um einen zweiten Druck freundlich zu beantworten
    (dieselbe Ueberlegung wie bei ``hole_knopf``)."""
    return conn.execute(
        "SELECT * FROM erkenner_lauf WHERE id = ?", (lauf_id,)
    ).fetchone()


@_gesperrt
def erkenner_lauf_schritte(
    conn: sqlite3.Connection, lauf_id: int
) -> list[sqlite3.Row]:
    """Die Schritte eines Laufs in Anlegereihenfolge."""
    return conn.execute(
        "SELECT * FROM erkenner_lauf_schritt WHERE lauf_id = ? ORDER BY id ASC",
        (lauf_id,),
    ).fetchall()
```

`import json` steht in `repo.py` bereits im Modulkopf -- falls nicht, dazu.
Pruefen mit `grep -n "^import json" interview_theater/repo.py`; fehlt die
Zeile, in den Importblock einfuegen.

- [x] **Schritt 4: Tests laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py -q -p no:cacheprovider`
Erwartet: `12 passed`

- [x] **Schritt 5: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4377 passed, 1 skipped`

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/repo.py tests/test_ruecknahme_repo.py
git commit -m "Karte U: Schnappschuss, Lauf speichern, offene Knoepfe einer Nachricht

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 4: `repo.nimm_erkenner_lauf_zurueck` -- die eine Transaktion

**Dateien:**
- Aendern: `interview_theater/repo.py` (denselben Abschnitt)
- Test: `tests/test_ruecknahme_repo.py` (erweitern)

**Schnittstellen:**
- Verbraucht: `ruecknahme.verweise()`, `ruecknahme.WEICH`, `.HART`,
  `.GELEERT`, `.gleich` -- als **Parameter** bzw. ueber einen lokalen Import
  in der Funktion (das ist im ganzen Repo die Bauart, mit der Zyklen aufgeloest
  werden; hier reicht der Parameter).
- Liefert:
  - `ZURUECK_OK = "ok"`, `ZURUECK_GEAENDERT = "geaendert"`,
    `ZURUECK_SCHON = "schon"`
  - `nimm_erkenner_lauf_zurueck(conn, lauf_id, verweise, weich, hart, geleert) -> str`

- [x] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_ruecknahme_repo.py` anhaengen:

```python
def _nimm_zurueck(conn, lauf_id):
    return repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


def _lauf_um(conn, arten, tat):
    """Nimmt den Schnappschuss um ``tat`` herum und legt den Lauf an -- genau
    der Ablauf, den ``erkenner.laufe`` in Aufgabe 7 fahren wird."""
    vorher = repo.schnappschuss(conn, 1, ruecknahme.plan(arten))
    tat()
    nachher = repo.schnappschuss(conn, 1, ruecknahme.plan(arten))
    return repo.lege_erkenner_lauf_an(
        conn, 1, "Probe",
        ruecknahme.schritte(vorher, nachher),
    )


def test_ruecknahme_stellt_ein_feld_wieder_her(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"


def test_ruecknahme_wirkt_nur_einmal(conn):
    """Die zweite Idempotenz-Sperre neben ``beanspruche_knopf``: ein bedingtes
    UPDATE in derselben Transaktion. Zwei direkte Aufrufe -- der zweite aendert
    nichts.

    Mutation, die diesen Test rot macht: ``AND zurueckgenommen_am IS NULL``
    im UPDATE weglassen."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )
    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK

    repo.setze_arbeitsstand(conn, 1, "kernthema", "Spaeter")
    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_SCHON
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Spaeter"


def test_ruecknahme_verweigert_wenn_der_wert_seitdem_anders_ist(conn):
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand")

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand"
    assert repo.hole_erkenner_lauf(conn, lauf_id)["zurueckgenommen_am"] is None


def test_ruecknahme_ist_alles_oder_nichts(conn):
    """Zwei Schritte, einer davon seitdem geaendert: NICHTS wird angefasst.

    Mutation, die diesen Test rot macht: je Schritt einzeln pruefen und
    committen statt erst alle pruefen, dann alle anwenden."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    def tat():
        repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu")
        repo.setze_arbeitsstand(conn, 1, "rahmen", "Bahnhof")

    lauf_id = _lauf_um(conn, ("kernthema_setzen", "rahmen_setzen"), tat)
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Schulhof")

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema"] == "Neu", "kein halber Rueckschritt"
    assert stand["rahmen"] == "Schulhof"


def test_ruecknahme_entfernt_eine_neue_figur_weich(conn):
    """N3: weich entfernen, nicht loeschen -- und geprueft wird ueber den
    LESER, nicht ueber rohes SQL.

    Mutation: ``entfernt_am`` nicht setzen -- ``repo.figuren`` liefert die
    Figur weiter."""
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.setze_figur(conn, 1, "Mira", "laut"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert [f["name"] for f in repo.figuren(conn, 1)] == []
    assert conn.execute("SELECT count(*) FROM figur").fetchone()[0] == 1, (
        "die Zeile bleibt stehen -- weich, nicht hart"
    )


def test_ruecknahme_nimmt_ein_weiches_entfernen_zurueck(conn):
    repo.setze_figur(conn, 1, "Mira", "laut")
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.entferne_figur(conn, 1, "Mira"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_ruecknahme_loescht_eine_neue_verknuepfung_hart(conn):
    """``szene_figur`` hat kein ``entfernt_am`` -- eine im Lauf entstandene
    Verknuepfung wird geloescht, genau wie ``setze_szene_figuren`` es tut."""
    repo.setze_figur(conn, 1, "Mira", "laut")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    lauf_id = _lauf_um(
        conn, ("szene_planen",),
        lambda: repo.setze_szene_figuren(conn, 1, szene_id, [figur_id]),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.szene_figuren(conn, szene_id) == []


def test_ruecknahme_fuegt_eine_hart_geloeschte_verknuepfung_wieder_ein(conn):
    repo.setze_figur(conn, 1, "Mira", "laut")
    repo.setze_figur(conn, 1, "Pola", "still")
    mira = repo.hole_figur(conn, 1, "Mira")["id"]
    pola = repo.hole_figur(conn, 1, "Pola")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [mira, pola])

    lauf_id = _lauf_um(
        conn, ("szene_planen",),
        lambda: repo.setze_szene_figuren(conn, 1, szene_id, [mira]),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert {f["id"] for f in repo.szene_figuren(conn, szene_id)} == {mira, pola}


def test_ruecknahme_verweigert_bei_einer_waise(conn):
    """Zeigt jetzt etwas auf die im Lauf neu angelegte Figur, das nicht im
    Lauf entstanden ist, wird NICHTS geaendert -- sonst blieben Waisen in
    ``szene_figur``/``schaerfung``/``szenenfassung`` stehen.

    Mutation: die Waisen-Probe weglassen."""
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.setze_figur(conn, 1, "Mira", "laut"),
    )
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    # NACH dem Lauf besetzt: die Gruppe hat die Figur inzwischen eingebaut.
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_ruecknahme_leert_eine_neue_arbeitsstandzeile_statt_sie_zu_loeschen(conn):
    """``arbeitsstand`` hat genau eine Zeile je Gruppe und kein
    ``entfernt_am`` -- sie zu loeschen hiesse, die Phasen-Buchhaltung
    mitzureissen."""
    assert repo.hole_arbeitsstand(conn, 1) is None
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand is not None, "die Zeile bleibt"
    assert stand["kernthema"] is None


def test_ruecknahme_eines_unbekannten_laufs_ist_kein_fehler(conn):
    assert _nimm_zurueck(conn, 999) == repo.ZURUECK_SCHON
```

- [x] **Schritt 2: Tests laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py -q -p no:cacheprovider`
Erwartet: FAIL -- `AttributeError: module 'interview_theater.repo' has no attribute 'nimm_erkenner_lauf_zurueck'`

- [x] **Schritt 3: Die Funktion schreiben**

In `interview_theater/repo.py`, hinter `erkenner_lauf_schritte`:

```python
#: Die Ergebnisse von ``nimm_erkenner_lauf_zurueck``. Drei und nicht ein bool:
#: "seitdem geaendert" und "schon zurueckgenommen" sind fuer die Gruppe zwei
#: verschiedene Saetze.
ZURUECK_OK = "ok"
ZURUECK_GEAENDERT = "geaendert"
ZURUECK_SCHON = "schon"


def _zeile_jetzt(conn, tabelle, schluessel, spalten):
    """Die verglichenen Spalten einer Zeile, oder None wenn sie fehlt."""
    bedingung = " AND ".join(f"{k} = ?" for k in schluessel)
    auswahl = ", ".join(spalten) if spalten else "1"
    zeile = conn.execute(
        f"SELECT {auswahl} FROM {tabelle} WHERE {bedingung}",
        list(schluessel.values()),
    ).fetchone()
    return None if zeile is None else {k: zeile[k] for k in spalten}


def _hat_fremden_verweis(conn, verweise, tabelle, zeilen_id, eigene) -> bool:
    """Zeigt jetzt eine Zeile auf diese figur/szene, die nicht im Lauf
    entstanden ist? Dann waere die Ruecknahme eine Waisenfabrik."""
    for quelle, spalte, ziel in verweise:
        if ziel != tabelle:
            continue
        for zeile in conn.execute(
            f"SELECT rowid FROM {quelle} WHERE {spalte} = ?", (zeilen_id,)
        ):
            if (quelle, zeile["rowid"]) not in eigene:
                return True
    return False


@_gesperrt
def nimm_erkenner_lauf_zurueck(
    conn: sqlite3.Connection, lauf_id: int,
    verweise: tuple[tuple[str, str, str], ...],
    weich: tuple[str, ...], hart: tuple[str, ...], geleert: tuple[str, ...],
) -> str:
    """Nimmt einen ganzen Erkennerlauf zurueck -- **alles oder nichts**, in
    EINER Transaktion unter ``_LOCK``.

    Erst wird JEDER Schritt geprueft (steht der Wert noch so, wie ihn der Lauf
    hinterlassen hat? haengt an einer neu angelegten Figur/Szene inzwischen
    etwas Fremdes?), und nur wenn alle durchkommen, wird angewendet. Ein
    halber Rueckschritt waere schlimmer als keiner: die Gruppe saehe einen
    Stand, den es nie gegeben hat.

    Die Idempotenz haengt an zwei Dingen: ``beanspruche_knopf`` beim Druck
    (``knoepfe.behandle``) und dem bedingten UPDATE hier -- wer die Zeile
    nicht bekommt, wirkt nicht. Das zweite ist noetig, weil die Ruecknahme
    auch ohne Knopf aufrufbar ist (Web-Kanal, Aufgabe 10) und weil zwei
    Knoepfe auf denselben Lauf zeigen koennen (Undo auf einer reduzierten
    aelteren Leiste).

    ``verweise``/``weich``/``hart``/``geleert`` kommen aus ``ruecknahme`` und
    werden uebergeben: die Entscheidung, WAS wie zurueckgenommen wird, ist
    Fachlogik, und diese Datei liest nicht nach oben."""
    lauf = conn.execute(
        "SELECT * FROM erkenner_lauf WHERE id = ?", (lauf_id,)
    ).fetchone()
    if lauf is None or lauf["zurueckgenommen_am"] is not None:
        return ZURUECK_SCHON

    schritte = conn.execute(
        "SELECT * FROM erkenner_lauf_schritt WHERE lauf_id = ? ORDER BY id ASC",
        (lauf_id,),
    ).fetchall()
    if not schritte:
        return ZURUECK_SCHON

    # Die Zeilen, die dieser Lauf selbst angelegt hat -- sie duerfen beim
    # Waisen-Test nicht als fremder Verweis zaehlen.
    eigene = set()
    for s in schritte:
        if s["art"] != "angelegt":
            continue
        schluessel = json.loads(s["schluessel"])
        bedingung = " AND ".join(f"{k} = ?" for k in schluessel)
        for zeile in conn.execute(
            f"SELECT rowid FROM {s['tabelle']} WHERE {bedingung}",
            list(schluessel.values()),
        ):
            eigene.add((s["tabelle"], zeile["rowid"]))

    # 1. Pruefen -- jeder Schritt, bevor einer wirkt.
    for s in schritte:
        schluessel = json.loads(s["schluessel"])
        nachher = json.loads(s["nachher"]) if s["nachher"] else None
        jetzt = _zeile_jetzt(
            conn, s["tabelle"], schluessel,
            list(nachher or json.loads(s["vorher"])),
        )
        if s["art"] == "geloescht":
            if jetzt is not None:
                return ZURUECK_GEAENDERT
            continue
        if jetzt is None:
            return ZURUECK_GEAENDERT
        for spalte, wert in nachher.items():
            if json.loads(json.dumps(jetzt.get(spalte))) != \
                    json.loads(json.dumps(wert)):
                return ZURUECK_GEAENDERT
        if s["art"] == "angelegt" and s["tabelle"] in weich:
            zeilen_id = schluessel.get("id")
            if zeilen_id is not None and _hat_fremden_verweis(
                conn, verweise, s["tabelle"], zeilen_id, eigene
            ):
                return ZURUECK_GEAENDERT

    # 2. Stempeln -- bedingt, in derselben Transaktion. Wer die Zeile nicht
    #    bekommt, wirkt nicht.
    cur = conn.execute(
        "UPDATE erkenner_lauf SET zurueckgenommen_am = ? "
        "WHERE id = ? AND zurueckgenommen_am IS NULL",
        (_jetzt(), lauf_id),
    )
    if cur.rowcount != 1:
        conn.rollback()
        return ZURUECK_SCHON

    # 3. Anwenden.
    for s in schritte:
        tabelle = s["tabelle"]
        schluessel = json.loads(s["schluessel"])
        bedingung = " AND ".join(f"{k} = ?" for k in schluessel)
        werte = list(schluessel.values())
        if s["art"] == "geaendert":
            vorher = json.loads(s["vorher"])
            satz = ", ".join(f"{k} = ?" for k in vorher)
            conn.execute(
                f"UPDATE {tabelle} SET {satz} WHERE {bedingung}",
                list(vorher.values()) + werte,
            )
        elif s["art"] == "angelegt":
            if tabelle in weich:
                conn.execute(
                    f"UPDATE {tabelle} SET entfernt_am = ? WHERE {bedingung}",
                    [_jetzt()] + werte,
                )
            elif tabelle in geleert:
                spalten = list(json.loads(s["nachher"]))
                satz = ", ".join(f"{k} = NULL" for k in spalten)
                conn.execute(f"UPDATE {tabelle} SET {satz} WHERE {bedingung}", werte)
            elif tabelle in hart:
                conn.execute(f"DELETE FROM {tabelle} WHERE {bedingung}", werte)
        else:  # geloescht -- wieder einfuegen
            zeile = dict(json.loads(s["vorher"]))
            zeile.update(schluessel)
            zeile.setdefault("chat_id", lauf["chat_id"])
            namen = ", ".join(zeile)
            fragen = ", ".join("?" for _ in zeile)
            conn.execute(
                f"INSERT OR IGNORE INTO {tabelle} ({namen}) VALUES ({fragen})",
                list(zeile.values()),
            )
    conn.commit()
    return ZURUECK_OK
```

- [x] **Schritt 4: Tests laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_ruecknahme_repo.py -q -p no:cacheprovider`
Erwartet: `23 passed`

- [x] **Schritt 5: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4388 passed, 1 skipped`

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/repo.py tests/test_ruecknahme_repo.py
git commit -m "Karte U: nimm_erkenner_lauf_zurueck -- alles oder nichts, in einer Transaktion

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 5: Texte, `ART_UNDO`, Leisten-Bausteine

**Dateien:**
- Aendern: `interview_theater/knoepfe/texte.py`, `interview_theater/knoepfe/basis.py`,
  `interview_theater/knoepfe/__init__.py`, `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_undo_knopf.py` (neu)

**Schnittstellen:**
- Liefert:
  - `knoepfe.ART_UNDO = "undo"`
  - `knoepfe.T._TEXT_UNDO_KNOPF`, `._TEXT_UNDO_ERLEDIGT`,
    `._TEXT_UNDO_GEAENDERT`, `._ANTWORT_UNDO`, `._ANTWORT_UNDO_GEAENDERT`
  - `knoepfe.undo_leiste(conn, chat_id: int, lauf_id: int | None) -> list[tuple[str, str]]`
  - `knoepfe.sende_notiert_nur_undo(conn, tg, chat_id: int, text: str, lauf_id: int) -> int`
  - `knoepfe.sende_notiert_mit_leiste(conn, tg, chat_id, text, art, wert, zusatz=())`
    -- neuer letzter Parameter, Vorgabe leer (jeder bestehende Aufruf bleibt gueltig)

- [x] **Schritt 1: Die fehlschlagenden Tests schreiben**

`tests/test_undo_knopf.py`:

```python
"""Der Undo-Knopf unter der Notiert-Meldung (Karte U, 01.10.2026).

Birk, 30.09.: "Ein falsch gespeicherter Wert darf nicht STILL bleiben: die
Gruppe muss ihn im Moment sehen und mit EINEM Tipp zuruecknehmen koennen."

Kein Netz, kein Modell: Telegram ist eine Attrappe, das Sprachmodell liefert
vorbereitete Antworten. Erfundenes Material, keine Echtdaten.
"""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo, ruecknahme, workshop


class TelegramAttrappe:
    """Dieselbe Schnittstelle wie ``telegram.Telegram``, soweit die Karte sie
    braucht -- inklusive ``aktualisiere_knoepfe``, damit die Reduktion einer
    aelteren Leiste auf ihren Undo-Knopf beobachtbar ist statt geschluckt."""

    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.aktualisiert = []
        self.naechste_message_id = 500

    def sende(self, chat_id, text, **_kw):
        self.naechste_message_id += 1
        self.gesendet.append((chat_id, text))
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        message_id = self.sende(chat_id, text)
        self.knoepfe.append((chat_id, text, list(knoepfe_), message_id))
        return message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    def aktualisiere_knoepfe(self, chat_id, message_id, knoepfe_):
        self.aktualisiert.append((chat_id, message_id, list(knoepfe_)))

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    """Das englische Profil. ``sprache.vergiss`` raeumt den Tabellen-Cache ab,
    ``workshop.vergiss`` das Profil -- beides wie in tests/fixture_sprache.py."""
    from interview_theater import sprache

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    return {
        "callback_query_id": query_id, "data": daten, "chat_id": chat_id,
        "chat_titel": "Testgruppe", "message_id": message_id,
    }


# --- Aufgabe 5: die Bausteine ---------------------------------------------


def test_undo_leiste_traegt_nur_die_lauf_id(conn):
    """Zusage 1: ``callback_data`` ist ``k:<id>``, der Wert steht in der
    Tabelle ``knopf``."""
    leiste = knoepfe.undo_leiste(conn, 1, 42)

    assert len(leiste) == 1
    beschriftung, daten = leiste[0]
    assert daten.startswith(knoepfe.PRAEFIX)
    assert len(daten.encode("utf-8")) < 64
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    knopf = repo.hole_knopf(conn, knopf_id)
    assert knopf["art"] == knoepfe.ART_UNDO
    assert knopf["wert"] == "42"


def test_undo_leiste_ohne_lauf_ist_leer(conn):
    assert knoepfe.undo_leiste(conn, 1, None) == []


def test_undo_texte_dortmund_deutsch(conn):
    """Dortmund: deutsch, in der ASCII-Umschrift des Moduls. ``texte.py``
    traegt keinen einzigen Umlaut (grep -c "[aeoeue...]" → 0), deshalb
    "Rueckgaengig" und nicht "Rückgängig"."""
    assert knoepfe.T._TEXT_UNDO_KNOPF == "Rueckgaengig"
    assert knoepfe.T._TEXT_UNDO_ERLEDIGT.startswith("Rueckgaengig gemacht:")
    assert "Arbeitsstand" in knoepfe.T._TEXT_UNDO_GEAENDERT


def test_undo_knopf_traegt_in_padua_englisch(conn, padua):
    assert knoepfe.T._TEXT_UNDO_KNOPF == "Undo"
    assert knoepfe.T._TEXT_UNDO_ERLEDIGT == "Undone:\n{zeilen}"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT == (
        "Changed since - please fix it in the work status"
    )


def test_undo_steht_als_letzte_zeile_unter_der_grundleiste(conn):
    """Mobil gilt: ein Hauptknopf je Bildschirm. Undo ist Nebenknopf und steht
    deshalb unten -- ``telegram.sende_mit_knoepfen`` legt eine Zeile je
    Eintrag an."""
    tg = TelegramAttrappe()
    zusatz = knoepfe.undo_leiste(conn, 1, 7)

    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=zusatz,
    )

    _, _, leiste, _ = tg.knoepfe[-1]
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF,
        knoepfe.T._TEXT_ANDERS_KNOPF,
        knoepfe.T._TEXT_UNDO_KNOPF,
    ]


def test_sende_notiert_nur_undo_schreibt_die_nachricht_mit(conn):
    """Wie jede Knopfnachricht: ueber ``_sende_knoepfe``, damit sie im
    Gespraechsfenster des naechsten Zuges steht (06.09.2026, Birk 12:05)."""
    tg = TelegramAttrappe()

    message_id = knoepfe.sende_notiert_nur_undo(
        conn, tg, 1, "Notiert:\nKernthema: Ankommen", 7)

    assert [b for b, _ in tg.knoepfe[-1][2]] == [knoepfe.T._TEXT_UNDO_KNOPF]
    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND ist_bot = 1"
    ).fetchone()
    assert zeile["text"] == "Notiert:\nKernthema: Ankommen"
    daten = tg.knoepfe[-1][2][0][1]
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    assert repo.hole_knopf(conn, knopf_id)["message_id"] == message_id


def test_alte_leiste_behaelt_ihren_undo_knopf(conn):
    """Eine ueberholte Leisten-Nachricht verliert ihre Speicher-Knoepfe, aber
    NICHT ihr Undo: sonst verschwaende eine zweite Notiert-Meldung die
    Ruecknahme der ersten.

    Mutation, die diesen Test rot macht: ``_entferne_tastatur`` statt der
    Reduktion auf den Undo-Knopf."""
    tg = TelegramAttrappe()
    erste = knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 7),
    )[0]

    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Schulhof", "rahmen", "Schulhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 8),
    )

    assert tg.entfernt == [], "nicht abgenommen -- reduziert"
    assert len(tg.aktualisiert) == 1, "genau eine Anfrage je Nachricht"
    chat_id, message_id, leiste = tg.aktualisiert[0]
    assert (chat_id, message_id) == (1, erste)
    assert [b for b, _ in leiste] == [knoepfe.T._TEXT_UNDO_KNOPF]


def test_die_speicher_knoepfe_der_alten_leiste_wirken_nicht_mehr(conn):
    """Sie werden verfallen gelassen, auch wenn die App die Tastatur noch
    einen Moment zeigt -- und zwar ALLE Nicht-Undo-Knoepfe der Nachricht auf
    einmal, damit der zweite und dritte ``_nimm_alte_leiste_ab``-Aufruf nichts
    mehr findet (Telegram antwortet auf eine unveraenderte Tastatur mit 400)."""
    tg = TelegramAttrappe()
    erste = knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 7),
    )[0]
    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Schulhof", "rahmen", "Schulhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 8),
    )

    offen = repo.offene_knoepfe_der_nachricht(conn, 1, erste)
    assert [k["art"] for k in offen] == [knoepfe.ART_UNDO]
```

- [x] **Schritt 2: Tests laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_undo_knopf.py -q -p no:cacheprovider`
Erwartet: FAIL -- `AttributeError: module 'interview_theater.knoepfe' has no attribute 'undo_leiste'`

- [x] **Schritt 3: `knoepfe/texte.py` ergaenzen**

Bei den ART-Konstanten (hinter `ART_STT_SPRACHE = "stt_sprache"`, ~Zeile 52):

```python
#: Der Undo-Knopf unter einer "Notiert:"-Meldung des Erkenners (Karte U,
#: 01.10.2026). ``wert`` ist die ``erkenner_lauf.id`` -- eine Meldung, eine
#: Ruecknahme, keine Einzelauswahl.
ART_UNDO = "undo"
```

Bei den Texten (hinter `_TEXT_UNBEKANNT`, ~Zeile 332):

```python
#: Der Undo-Knopf (Karte U). Ruhig: kein Emoji, ein Wort, letzte Zeile der
#: Tastatur -- mobil gilt ein Hauptknopf je Bildschirm, und Undo ist
#: Nebenknopf. ASCII-Umschrift wie jede Beschriftung in dieser Datei.
_TEXT_UNDO_KNOPF = "Rueckgaengig"
#: Was zurueckgenommen wurde -- dieselben Zeilen wie in der Meldung
#: (erkenner.undo_zeilen), keine zweite Formulierung.
_TEXT_UNDO_ERLEDIGT = "Rueckgaengig gemacht:\n{zeilen}"
#: Ein betroffenes Feld hat sich seit dem Lauf erneut geaendert: NICHTS wird
#: angefasst, und die Gruppe erfaehrt, wo sie stattdessen hingehen kann.
_TEXT_UNDO_GEAENDERT = "Seitdem geaendert -- bitte im Arbeitsstand korrigieren."
#: Die kurzen Zeilen fuer answerCallbackQuery.
_ANTWORT_UNDO = "Zurueckgenommen."
_ANTWORT_UNDO_GEAENDERT = "Seitdem geaendert."
```

- [x] **Schritt 4: `sprachen/en/texte.toml` ergaenzen**

Im Abschnitt `["knoepfe.texte"]`, hinter `_TEXT_UNBEKANNT` (in
Definitionsreihenfolge, K2):

```toml
# Karte U: der Undo-Knopf unter jeder Notiert-Meldung.
_TEXT_UNDO_KNOPF = "Undo"
_TEXT_UNDO_ERLEDIGT = "Undone:\n{zeilen}"
_TEXT_UNDO_GEAENDERT = "Changed since - please fix it in the work status"
_ANTWORT_UNDO = "Undone."
_ANTWORT_UNDO_GEAENDERT = "Changed since."
```

- [x] **Schritt 5: `knoepfe/basis.py` ergaenzen**

`ART_UNDO` in den Import aus `knoepfe.texte` aufnehmen. Dann
`_nimm_alte_leiste_ab` ersetzen und zwei Funktionen ergaenzen:

```python
def _reduziere_auf_undo(tg, chat_id, message_id, undo) -> None:
    """Laesst von einer ueberholten Leisten-Nachricht **nur den Undo-Knopf**
    stehen (Karte U), statt die Tastatur ganz abzunehmen.

    Der Grund: der Undo-Knopf dieser Nachricht ist der einzige Weg, ihren Wert
    zurueckzunehmen -- er darf nicht verschwinden, nur weil eine neue Leiste
    kommt. Die Speicher-Knoepfe daneben muessen weg (der Wert steckt im Knopf,
    und ein Druck auf die alte Leiste speicherte den ueberholten Vorschlag).

    Fehlschlaege werden geschluckt wie in ``_entferne_tastatur``: die Knoepfe
    sind in der Datenbank schon verfallen, die Tastatur zeigt es nur an."""
    try:
        tg.aktualisiere_knoepfe(
            chat_id, message_id,
            [(T._TEXT_UNDO_KNOPF, _daten(k["id"])) for k in undo],
        )
    except Exception:
        log.warning("Leiste auf Undo reduzieren fehlgeschlagen, chat_id=%s", chat_id)


def _nimm_alte_leiste_ab(conn, tg, chat_id: int, art: str) -> None:
    """Nimmt die Tastatur einer aelteren, ungedrueckten Speicher-Leiste
    derselben Art ab, bevor eine neue kommt.

    Warum: der Wert steckt im Knopf, nicht im Text. Nach drei Vorschlaegen
    staenden sonst drei Leisten im Chat, und ein Druck auf die von vor zwei
    Nachrichten speicherte den ueberholten Vorschlag -- genau die Sorte
    stiller Fehler, gegen die die Knoepfe angetreten sind. Die alten
    Knopfzeilen werden zusaetzlich als benutzt gestempelt
    (``repo.verfallen_lassen``), damit sie auch dann nicht mehr wirken, wenn
    die App die Tastatur noch einen Moment zeigt.

    **Traegt die Nachricht einen unbenutzten Undo-Knopf** (Karte U), wird ihre
    Tastatur auf ihn allein reduziert statt ganz abgenommen: er ist der einzige
    Weg, den Wert dieser Meldung zurueckzunehmen.

    Verfallen gelassen werden dabei **alle** Nicht-Undo-Knoepfe dieser
    Nachrichten, nicht nur die der uebergebenen ``art``. Zwei Gruende: eine
    ueberholte Leisten-Nachricht soll keinen einzigen lebenden Speicher-Knopf
    behalten, und ``sende_notiert_mit_leiste`` ruft diese Funktion dreimal
    hintereinander -- ohne das liefe der zweite und dritte Aufruf in ein
    ``editMessageReplyMarkup`` mit unveraenderter Tastatur, und Telegram
    antwortet darauf mit 400."""
    alte = repo.offene_knoepfe(conn, chat_id, art)
    if not alte:
        return
    nachrichten = list(dict.fromkeys(k["message_id"] for k in alte))
    offen = [
        k for message_id in nachrichten
        for k in repo.offene_knoepfe_der_nachricht(conn, chat_id, message_id)
    ]
    repo.verfallen_lassen(conn, [k["id"] for k in offen if k["art"] != ART_UNDO])
    for message_id in nachrichten:
        undo = [
            k for k in offen
            if k["message_id"] == message_id and k["art"] == ART_UNDO
        ]
        if undo:
            _reduziere_auf_undo(tg, chat_id, message_id, undo)
        else:
            _entferne_tastatur(tg, chat_id, message_id)
```

`sende_notiert_mit_leiste` bekommt den Zusatz:

```python
def sende_notiert_mit_leiste(conn, tg, chat_id: int, text: str, art: str,
                             wert: str, zusatz=()) -> tuple[int, bool]:
    """... (Docstring unveraendert, plus:)

    ``zusatz`` haengt weitere Knopfzeilen UNTER die Grundleiste -- gebraucht
    fuer den Undo-Knopf (Karte U), der als ruhiger Nebenknopf zuletzt steht.
    Vorgabe leer, damit jeder bestehende Aufruf unveraendert gueltig bleibt."""
    for alte in (ART_SPEICHERN, ART_ANDERS, ART_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, alte)
    leiste = speicherleiste(conn, chat_id, art, wert) + list(zusatz)
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True
```

Und die zwei neuen oeffentlichen Funktionen, direkt darunter:

```python
def undo_leiste(conn, chat_id: int, lauf_id: int | None) -> list[tuple[str, str]]:
    """Der EINE ruhige Undo-Knopf zu einem Erkennerlauf -- oder eine leere
    Leiste, wenn es keinen Lauf gibt (Karte U, 01.10.2026).

    Eine Meldung, eine Ruecknahme: der Knopf traegt die ``erkenner_lauf.id``
    im ``wert`` der Knopfzeile, nie in ``callback_data`` (Zusage 1). Eine
    Einzelauswahl ("nur das Kernthema, nicht die Figur") gibt es bewusst
    nicht -- sie waere eine Liste dort, wo die Gruppe einen Fehler wegtippen
    will."""
    if lauf_id is None:
        return []
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_UNDO, str(lauf_id))
    return [(T._TEXT_UNDO_KNOPF, _daten(knopf_id))]


def sende_notiert_nur_undo(conn, tg, chat_id: int, text: str, lauf_id: int) -> int:
    """Die "Notiert:"-Meldung mit dem Undo-Knopf als einziger Zeile -- der Weg
    fuer alle Phasen, in denen keine Grundleiste darunter gehoert.

    Aus ``tg.sende`` wird damit ``_sende_knoepfe``: dieselbe Mitschrift in
    ``nachricht`` wie bei jeder anderen Knopfnachricht (06.09.2026, Birk
    12:05), und ``merke_knopf_nachricht`` haelt fest, unter welcher Nachricht
    der Knopf haengt."""
    leiste = undo_leiste(conn, chat_id, lauf_id)
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id
```

- [x] **Schritt 6: `knoepfe/__init__.py` ergaenzen**

`ART_UNDO` in den Re-Export aus `knoepfe.texte` (alphabetisch bei den
`ART_*`), und `sende_notiert_nur_undo`, `undo_leiste`, `_reduziere_auf_undo`
in den Re-Export aus `knoepfe.basis`.

- [x] **Schritt 7: Tests laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_undo_knopf.py tests/test_sprache_texte.py tests/test_sprache_bitgleich.py tests/test_profil_bitgleich.py -q -p no:cacheprovider`

Erwartet: `8 passed` in `test_undo_knopf.py`, und die drei Sprach- und
Profiltests **unveraendert gruen** (siehe Befund G.1: neue Konstanten sind
erlaubt, kein Abschnitt aendert sich).

`tests/test_knoepfe_struktur.py::test_jede_knopfart_hat_genau_einen_handler`
ist jetzt **rot** -- `ART_UNDO` hat noch keinen Handler. Das ist Aufgabe 6 und
erwartet:

Run: `$PY -m pytest tests/test_knoepfe_struktur.py -q -p no:cacheprovider`
Erwartet: FAIL -- `assert ohne_handler == []` mit `['undo']`

- [x] **Schritt 8: Commit**

Diese Aufgabe endet mit einem bekannten roten Test, und nur mit diesem einen.
Der Commit haelt das fest:

Run: `$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3`
Erwartet: `1 failed, 4395 passed, 1 skipped` -- der Fehlschlag ist
`test_jede_knopfart_hat_genau_einen_handler`.

```bash
git add interview_theater/knoepfe/texte.py interview_theater/knoepfe/basis.py \
        interview_theater/knoepfe/__init__.py \
        interview_theater/sprachen/en/texte.toml tests/test_undo_knopf.py
git commit -m "Karte U: ART_UNDO, die Texte DE/EN und die Leisten-Bausteine

Die alte Leiste wird auf ihren Undo-Knopf reduziert statt abgenommen -- er ist
der einzige Weg, den Wert dieser Meldung zurueckzunehmen. Der Handler folgt in
der naechsten Aufgabe; bis dahin ist test_jede_knopfart_hat_genau_einen_handler
erwartet rot.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 6: Der Handler

**Dateien:**
- Aendern: `interview_theater/knoepfe/wirkung.py`
- Test: `tests/test_undo_knopf.py` (erweitern)

**Schnittstellen:**
- Verbraucht: `repo.nimm_erkenner_lauf_zurueck`, `repo.hole_erkenner_lauf`,
  `repo.offene_knoepfe_der_nachricht`, `repo.verfallen_lassen`,
  `repo.merke_bot_zeile`, `repo.schreibe_journal`, `ruecknahme.verweise/WEICH/HART/GELEERT`
- Liefert: `_wirkung_undo(conn, d: Druck) -> str`, Eintrag
  `ART_UNDO: _wirkung_undo` in `_WIRKUNGEN`

- [x] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_undo_knopf.py` anhaengen:

```python
# --- Aufgabe 6: der Handler ----------------------------------------------


def _lauf_mit_kernthema(conn, alt=None, neu="Ankommen"):
    """Ein gespeicherter Lauf, der ``kernthema`` von ``alt`` auf ``neu``
    gesetzt hat -- ohne den Erkenner, damit der Handler allein geprueft wird."""
    if alt is not None:
        repo.setze_arbeitsstand(conn, 1, "kernthema", alt)
    plan = ruecknahme.plan(["kernthema_setzen"])
    vorher = repo.schnappschuss(conn, 1, plan)
    repo.setze_arbeitsstand(conn, 1, "kernthema", neu)
    nachher = repo.schnappschuss(conn, 1, plan)
    return repo.lege_erkenner_lauf_an(
        conn, 1, f"Kernthema: {neu}", ruecknahme.schritte(vorher, nachher)
    )


def _druecke_undo(conn, tg, einst, lauf_id, message_id=777, query_id="q1"):
    daten = knoepfe.undo_leiste(conn, 1, lauf_id)[0][1]
    repo.merke_knopf_nachricht(
        conn, [int(daten[len(knoepfe.PRAEFIX):])], message_id)
    repo.merke_erkenner_lauf_nachricht(conn, lauf_id, message_id)
    return knoepfe.behandle(
        conn, tg, None, einst, _druck(daten, message_id=message_id,
                                      query_id=query_id))


def test_der_handler_stellt_den_alten_wert_wieder_her(conn, tg, einst):
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")

    assert _druecke_undo(conn, tg, einst, lauf_id) is True

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert any("Rueckgaengig gemacht:" in t for t in tg.texte)
    assert any("Kernthema: Ankommen" in t for t in tg.texte)


def test_der_handler_meldet_seitdem_geaendert_und_aendert_nichts(conn, tg, einst):
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand")

    _druecke_undo(conn, tg, einst, lauf_id)

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT in tg.texte
    assert not any("Rueckgaengig gemacht:" in t for t in tg.texte)


def test_die_undo_zeile_wird_als_bot_zeile_mitgeschrieben(conn, tg, einst):
    """Damit das Gespraechsmodell im naechsten Zug sieht, dass zurueckgenommen
    wurde -- und nicht behauptet, der Wert stehe (H)."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")

    _druecke_undo(conn, tg, einst, lauf_id)

    zeilen = [
        z["text"] for z in conn.execute(
            "SELECT text FROM nachricht WHERE chat_id = 1 AND ist_bot = 1")
    ]
    assert any((t or "").startswith("Rueckgaengig gemacht:") for t in zeilen)


def test_undo_verfallen_laesst_die_grundleiste(conn, tg, einst):
    """Sonst schriebe "Ja, speichern" den gerade zurueckgenommenen Wert wieder
    -- der Wert steckt im Knopf, nicht im Text (basis.speicherleiste).

    Mutation, die diesen Test rot macht: ``repo.verfallen_lassen`` im Handler
    weglassen."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    speichern = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN, "kernthema|Ankommen")
    repo.merke_knopf_nachricht(conn, [speichern], 777)

    _druecke_undo(conn, tg, einst, lauf_id, message_id=777)

    assert repo.beanspruche_knopf(conn, speichern) is False, "schon verfallen"
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"


def test_die_ruecknahme_haengt_eine_journalzeile_an(conn, tg, einst):
    """Das Journal wird nur angehaengt (AGENTS.md): die Zeilen des Laufs
    bleiben stehen, die Ruecknahme kommt daneben -- mit ``quelle 'undo'``,
    damit der Weg nachvollziehbar bleibt."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    vorher = len(repo.journal(conn, 1))

    _druecke_undo(conn, tg, einst, lauf_id)

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == vorher + 1
    neu = eintraege[-1]
    assert neu["quelle"] == "undo"
    assert "Kernthema: Ankommen" in neu["text"]


def test_ein_unbekannter_lauf_ist_kein_absturz(conn, tg, einst):
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_UNDO, "999")
    assert knoepfe.behandle(
        conn, tg, None, einst, _druck(knoepfe._daten(knopf_id))) is True
    assert tg.beantwortet, "answerCallbackQuery kommt immer"


def test_ein_undo_aus_einer_fremden_gruppe_wirkt_nicht(conn, tg, einst):
    """Dieselbe Datenbank traegt alle Gruppen des Workshops."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    daten = knoepfe.undo_leiste(conn, 1, lauf_id)[0][1]

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, chat_id=2))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"
```

- [x] **Schritt 2: Tests laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_undo_knopf.py -q -p no:cacheprovider`
Erwartet: FAIL -- der Druck landet bei `_TEXT_UNBEKANNT`, `kernthema` bleibt
`"Ankommen"`.

- [x] **Schritt 3: Den Handler schreiben**

In `interview_theater/knoepfe/wirkung.py`: `ART_UNDO` in den Import aus
`knoepfe.texte`, `ruecknahme` in den Import aus `interview_theater` (neben
`phasen, repo, sprache`). Dann hinter `_wirkung_stt_sprache`:

```python
def _wirkung_undo(conn, d: Druck) -> str:
    """Nimmt einen ganzen Erkennerlauf zurueck (Karte U, 01.10.2026).

    Eine Meldung, eine Ruecknahme -- keine Einzelauswahl. **Kein
    Modellaufruf** (Zusage 2): die Schritte liegen seit dem Lauf in
    ``erkenner_lauf_schritt``, und was hier passiert, ist ein
    ``UPDATE``/``DELETE`` je Schritt in EINER Transaktion
    (``repo.nimm_erkenner_lauf_zurueck``).

    Drei Ausgaenge: zurueckgenommen (die Zeilen der Meldung gehen als
    "Rueckgaengig gemacht:" zurueck in den Chat und ins Journal), seitdem
    geaendert (nichts passiert, die Gruppe erfaehrt, wo sie stattdessen
    hingeht) und schon zurueckgenommen (zweiter Druck -- beantwortet, wirkt
    nicht; die Sperre steht doppelt, hier und in ``behandle``).

    Nach der wirksamen Ruecknahme werden die **Grundleisten-Knoepfe derselben
    Nachricht verfallen gelassen**: der Wert steckt im Knopf, und "Ja,
    speichern" schriebe sonst genau den Wert wieder, den die Gruppe gerade
    weggetippt hat. Die Tastatur selbst nimmt ``behandle`` ab, wie bei jedem
    Knopf."""
    if not d.wert.strip().isdigit():
        return T._TEXT_UNBEKANNT
    lauf_id = int(d.wert.strip())
    lauf = repo.hole_erkenner_lauf(conn, lauf_id)
    if lauf is None or lauf["chat_id"] != d.chat_id:
        return T._TEXT_UNBEKANNT

    stand = repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )
    if stand == repo.ZURUECK_GEAENDERT:
        d.tg.sende(d.chat_id, T._TEXT_UNDO_GEAENDERT)
        return T._ANTWORT_UNDO_GEAENDERT
    if stand != repo.ZURUECK_OK:
        return T._TEXT_SCHON_BENUTZT

    if lauf["message_id"]:
        repo.verfallen_lassen(conn, [
            k["id"] for k in repo.offene_knoepfe_der_nachricht(
                conn, d.chat_id, lauf["message_id"])
        ])
    zeilen = lauf["meldung"] or ""
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_UNDO.format(zeilen=" / ".join(zeilen.splitlines())),
        quelle="undo",
    )
    text = T._TEXT_UNDO_ERLEDIGT.format(zeilen=zeilen)
    message_id = d.tg.sende(d.chat_id, text)
    repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, text)
    return T._ANTWORT_UNDO
```

Dazu in `knoepfe/texte.py` eine sechste Konstante (und ihr TOML-Gegenstueck):

```python
#: Die Journalzeile der Ruecknahme -- das Journal wird nur angehaengt, die
#: Zeilen des Laufs bleiben stehen (AGENTS.md).
_JOURNAL_UNDO = "Zurueckgenommen: {zeilen}"
```

```toml
_JOURNAL_UNDO = "Withdrawn: {zeilen}"
```

Und in `_WIRKUNGEN`, hinter `ART_STT_SPRACHE: _wirkung_stt_sprache,`:

```python
    ART_UNDO: _wirkung_undo,
```

- [x] **Schritt 4: Tests laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_undo_knopf.py tests/test_knoepfe_struktur.py tests/test_sprache_texte.py -q -p no:cacheprovider`
Erwartet: alles `passed`; `test_jede_knopfart_hat_genau_einen_handler` ist
wieder gruen, `test_kein_handler_ruft_das_sprachmodell[_wirkung_undo]` ist
neu und gruen.

- [x] **Schritt 5: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4403 passed, 1 skipped` -- **0 failed**.

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/knoepfe/wirkung.py interview_theater/knoepfe/texte.py \
        interview_theater/sprachen/en/texte.toml tests/test_undo_knopf.py
git commit -m "Karte U: _wirkung_undo -- deterministisch, idempotent, kein Modellaufruf

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 7: Einhaengen in `erkenner.laufe`

**Dateien:**
- Aendern: `interview_theater/erkenner.py` (`_sende_meldung` ~1871, `laufe` ~1923,
  neue Funktionen davor)
- Aendern: `tests/test_erkenner.py` (`TelegramAttrappe` um `aktualisiere_knoepfe`)
- Test: `tests/test_undo_knopf.py` (erweitern)

**Schnittstellen:**
- Liefert:
  - `erkenner.undo_zeilen(wirkliche: list[dict]) -> list[str]`
  - `erkenner._lege_ruecknahme_an(conn, e, chat_id, plan, vorher, wirkliche) -> int | None`
  - `erkenner._sende_meldung(conn, tg, chat_id, text, wirkliche, lauf_id=None) -> int`
    -- neuer letzter Parameter, Vorgabe `None`

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_undo_knopf.py` anhaengen:

```python
# --- Aufgabe 7: der Knopf steht unter jeder Notiert-Meldung ---------------


class LLMAttrappe:
    def __init__(self, antwort):
        self._antwort = antwort

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        return self._antwort


def _nachricht(conn, text, message_id=1):
    repo.merke_nachricht(
        conn, 1, message_id, "Mert", 0, "text", text, repo._jetzt())


def _laufe(conn, tg, einst, aenderungen, text="wir haben was entschieden",
           message_id=1):
    _nachricht(conn, text, message_id)
    erkenner.laufe(
        LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, 1)


def _undo_daten(tg):
    """Die callback_data des Undo-Knopfs unter der letzten Knopfnachricht."""
    for _, _, leiste, _ in reversed(tg.knoepfe):
        for beschriftung, daten in leiste:
            if beschriftung == knoepfe.T._TEXT_UNDO_KNOPF:
                return daten
    raise AssertionError(f"kein Undo-Knopf in {tg.knoepfe!r}")


def test_undo_steht_unter_der_notiert_meldung_ohne_grundleiste(conn, tg, einst):
    """Phase 3: keine Ping-Pong-Art offen, also keine Grundleiste -- der
    Undo-Knopf steht trotzdem da, als einzige Zeile."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    chat_id, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [knoepfe.T._TEXT_UNDO_KNOPF]


def test_undo_steht_unter_der_grundleiste_wenn_es_eine_gibt(conn, tg, einst):
    """Phase 4, Setting offen: die bestehende Grundleiste bleibt, Undo kommt
    als ruhiger Nebenknopf darunter (Karte U Punkt 5)."""
    phasen.setze(conn, 1, 4, "test")
    _laufe(conn, tg, einst, [{"art": "rahmen_setzen", "wert": "Bahnhof, abends"}])

    _, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF,
        knoepfe.T._TEXT_ANDERS_KNOPF,
        knoepfe.T._TEXT_UNDO_KNOPF,
    ]


def test_der_meldungstext_bleibt_zeichengleich(conn, tg, einst):
    """Der Knopf kommt dazu, der Text nicht: ``baue_meldung`` ist unveraendert
    die eine Quelle."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert tg.knoepfe[-1][1] == erkenner.baue_meldung(
        [{"art": "kernthema_setzen", "wert": "Ankommen"}])


def test_kein_lauf_ohne_schritte_und_ohne_zeilen(conn, tg, einst):
    """Eine Meldung, die nur die Phase nennt, bekommt keinen Knopf: es gibt
    nichts zurueckzunehmen (``phase`` und ``gruppe`` sind nicht verfolgt).

    Mutation, die diesen Test rot macht: den Lauf auch bei leerem Diff anlegen
    -- ein Knopf ohne Wirkung."""
    phasen.setze(conn, 1, 1, "test")
    _laufe(conn, tg, einst, [{"art": "phase_setzen", "wert": "2"}])

    assert any(t.startswith("Notiert:") for t in tg.texte), "die Meldung kommt"
    assert not any(
        b == knoepfe.T._TEXT_UNDO_KNOPF
        for _, _, leiste, _ in tg.knoepfe for b, _ in leiste
    )
    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_eine_wiederholte_meldung_bekommt_keinen_lauf(conn, tg, einst):
    """``_steht_schon_da``: die Meldung geht nicht raus, also entsteht auch
    kein Knopf und kein Lauf-Datensatz."""
    phasen.setze(conn, 1, 3, "test")
    repo.merke_nachricht(
        conn, 1, 50, "Bot", 1, "text", "Notiert:\nKernthema: Ankommen",
        repo._jetzt())
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}],
           message_id=51)

    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_ein_fehlschlag_beim_anlegen_schickt_die_meldung_trotzdem(
        conn, tg, einst, monkeypatch):
    """"Der Wert ist wichtiger als seine Knoepfe" -- wie ``_sende_meldung``
    es heute schon fuer die Grundleiste haelt. Mit Vorfall fuers Dashboard."""
    phasen.setze(conn, 1, 3, "test")

    def kaputt(*_a, **_kw):
        raise RuntimeError("Datenbank zickt")

    monkeypatch.setattr(repo, "lege_erkenner_lauf_an", kaputt)
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert any(t.startswith("Notiert:") for t in tg.texte)
    arten = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "undo_nicht_angelegt" in arten


def test_undo_zeilen_nennen_die_phase_und_die_usa_zeile_nicht(conn):
    """Nur die zurueckgenommenen Zeilen. Die Phase steht in der Meldung, aber
    nicht in "Rueckgaengig gemacht:" -- und die USA-Zeile ebenso nicht
    (offener Punkt fuer Birk)."""
    zeilen = erkenner.undo_zeilen([
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "phase_setzen", "wert": "2"},
        {"art": "szene_usa", "wert": "ja"},
    ])
    assert zeilen == ["Kernthema: Ankommen"]


def test_undo_zeilen_nennen_die_figurenanzahl_aus_einem_stillen_entschieden(conn):
    """``entschieden`` ist in der Meldung still, setzt aber nebenbei
    ``arbeitsstand.figuren_anzahl`` -- und diese Spalte ist verfolgt, also
    gehoert die Zeile in die Ruecknahme (Abweichung E.1)."""
    zeilen = erkenner.undo_zeilen([
        {"art": "entschieden", "wert": "Wir nehmen vier Figuren.",
         "figuren_anzahl": 4},
    ])
    assert zeilen == ["Anzahl Figuren: 4"]


def test_nach_undo_liest_der_erkenner_die_alte_nachricht_nicht_erneut(
        conn, tg, einst):
    """Befund H, am Code geprueft: ``erkenne`` rueckt das Wasserzeichen vor
    (``repo.setze_extrahiert_bis``), ``repo.unextrahierte`` liefert nur
    Nachrichten darueber. Die Nachricht, aus der der falsche Wert kam, kommt
    nie wieder -- der Erkenner setzt ihn also nicht von sich aus erneut.

    Und die Undo-Zeile ist als Vorlauf brauchbar: ``letzte_bot_nachricht_vor``
    schliesst nur "Notiert:"/"Noted:" aus."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}],
           text="das Kernthema ist Ankommen", message_id=1)
    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    _druecke_undo(conn, tg, einst, lauf_id, message_id=777, query_id="q9")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] is None

    # Der naechste Lauf sieht die alte Nachricht nicht mehr.
    offen = [z["message_id"] for z in repo.unextrahierte(conn, 1)]
    assert 1 not in offen

    vorlauf = repo.letzte_bot_nachricht_vor(conn, 1, 10_000)
    assert (vorlauf["text"] or "").startswith("Rueckgaengig gemacht:")
```

- [ ] **Schritt 2: Tests laufen lassen, Fehlschlag sehen**

Run: `$PY -m pytest tests/test_undo_knopf.py -q -p no:cacheprovider`
Erwartet: FAIL -- `AssertionError: kein Undo-Knopf in []`

- [ ] **Schritt 3: `erkenner.py` ergaenzen**

`ruecknahme` in den Modulkopf-Import (`from interview_theater import ...`).
Dann hinter `_meldungszeilen` (~Zeile 1644):

```python
def undo_zeilen(wirkliche_aenderungen: list[dict]) -> list[str]:
    """Die Zeilen, die eine Ruecknahme dieses Laufs nennen wuerde.

    **Dieselbe Quelle wie die Meldung** (``_sammle_meldbares`` →
    ``_meldungszeilen``), nur mit gefilterter Eingabe -- "Rueckgaengig
    gemacht:" soll nicht anders klingen als "Notiert:", und ein zweiter
    Formulierungsweg waere die naechste Stelle, an der beide auseinanderlaufen.

    Gefiltert wird mit einer **Ausschluss**liste
    (``ruecknahme.ZEILEN_OHNE_UNDO``: ``phase_setzen``, ``szene_usa``) und
    nicht mit einer Einschlussliste. Der Grund ist gemessen am Code:
    ``entschieden`` ist in der Meldung still, setzt aber nebenbei
    ``arbeitsstand.figuren_anzahl`` (``_wende_journal_an``) -- eine
    Einschlussliste haette die Zeile "Anzahl Figuren: 4" verschluckt, obwohl
    das Feld verfolgt wird und die Ruecknahme es zurueckdreht."""
    behalten = [
        a for a in wirkliche_aenderungen
        if a.get("art") not in ruecknahme.ZEILEN_OHNE_UNDO
    ]
    return _meldungszeilen(_sammle_meldbares(behalten))


def _lege_ruecknahme_an(conn, e, chat_id: int, plan: dict, vorher: dict | None,
                        wirkliche: list[dict]) -> int | None:
    """Schreibt die Ruecknahme-Schritte dieses Laufs und liefert die Lauf-id,
    oder ``None``, wenn es keinen Knopf geben soll.

    Kein Knopf gibt es in drei Faellen: der Schnappschuss davor ist
    ausgefallen, der Diff ist leer (nur Phase, nur USA -- beides nicht
    verfolgt), oder es gibt keine Zeile, die die Ruecknahme benennen koennte.

    **Ein Fehlschlag hier reisst die Meldung nicht mit** -- dieselbe Haltung wie
    bei der Grundleiste in ``_sende_meldung``: der Wert ist wichtiger als seine
    Knoepfe. Fuers Dashboard bleibt ein Vorfall stehen."""
    if vorher is None:
        return None
    try:
        nachher = repo.schnappschuss(conn, chat_id, plan)
        return repo.lege_erkenner_lauf_an(
            conn, chat_id, "\n".join(undo_zeilen(wirkliche)),
            ruecknahme.schritte(vorher, nachher),
        )
    except Exception:
        log.exception("Ruecknahme konnte nicht angelegt werden, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "undo_nicht_angelegt",
            "Notiert-Meldung ohne Undo-Knopf verschickt",
        )
        return None
```

`_sende_meldung` bekommt den Undo-Knopf an beide Wege:

```python
def _sende_meldung(conn, tg, chat_id: int, text: str, wirkliche: list[dict],
                   lauf_id: int | None = None) -> int:
    """Schickt die Notiert-Meldung -- mit Grundleiste, wenn der Erkenner
    gerade die Art gespeichert hat, die in dieser Phase offen ist, und seit
    Karte U (01.10.2026) mit dem Undo-Knopf darunter.

    ... (bisheriger Docstring) ...

    Der Undo-Knopf steht an BEIDEN Wegen: unter der Grundleiste als letzte,
    ruhige Zeile (mobil gilt ein Hauptknopf je Bildschirm), und ohne
    Grundleiste als einzige. Deshalb wird aus ``tg.sende`` dort
    ``knoepfe.sende_notiert_nur_undo`` -- derselbe Sendeweg wie jede andere
    Knopfnachricht, samt Mitschrift in ``nachricht``."""
    from interview_theater import knoepfe

    zusatz = []
    try:
        zusatz = knoepfe.undo_leiste(conn, chat_id, lauf_id)
        phase = phasen.aktuelle(conn, chat_id)
        for aenderung in wirkliche:
            eintrag = _LEISTENARTEN.get(aenderung.get("art"))
            if eintrag is None or eintrag[1] != phase:
                continue
            wert = str(aenderung.get("wert") or "").strip()
            if not wert:
                continue
            message_id, _ = knoepfe.sende_notiert_mit_leiste(
                conn, tg, chat_id, text, eintrag[0], wert, zusatz=zusatz
            )
            return message_id
    except Exception:
        log.exception("Leiste unter der Notiert-Meldung fehlgeschlagen, chat_id=%s", chat_id)
    if zusatz:
        try:
            return knoepfe.sende_notiert_nur_undo(conn, tg, chat_id, text, lauf_id)
        except Exception:
            log.exception("Undo-Knopf unter der Notiert-Meldung fehlgeschlagen, "
                          "chat_id=%s", chat_id)
    return tg.sende(chat_id, text)
```

In `laufe`: der Schnappschuss vor `wende_an`, das Anlegen vor dem Senden.
Direkt vor `wirkliche = wende_an(...)`:

```python
        # Der Stand VOR dem Anwenden -- Grundlage des Undo-Knopfs (Karte U).
        # Hier und nicht in ``wende_an``: ``wende_aus_aufnahme_an`` schickt
        # keine Meldung und bekommt deshalb auch kein Undo, und die Signatur
        # von ``wende_an`` bleibt, was sie ist.
        plan = ruecknahme.plan(a.get("art") for a in aenderungen)
        try:
            vorher = repo.schnappschuss(conn, chat_id, plan)
        except Exception:
            log.exception("Schnappschuss vor dem Anwenden fehlgeschlagen, "
                          "chat_id=%s", chat_id)
            vorher = None
        wirkliche = wende_an(conn, e, chat_id, aenderungen)
```

und hinter `if _steht_schon_da(...)`-Block, vor `message_id = _sende_meldung(...)`:

```python
        lauf_id = _lege_ruecknahme_an(conn, e, chat_id, plan, vorher, wirkliche)
        message_id = _sende_meldung(conn, tg, chat_id, text, wirkliche, lauf_id)
        if lauf_id is not None:
            # Unter welcher Nachricht der Knopf haengt -- gebraucht, um nach
            # der Ruecknahme genau ihre Grundleiste verfallen zu lassen.
            repo.merke_erkenner_lauf_nachricht(conn, lauf_id, message_id)
```

- [ ] **Schritt 4: Die Attrappe in `tests/test_erkenner.py` ergaenzen**

An `TelegramAttrappe` (Zeile ~593) eine Methode anhaengen, damit die Reduktion
einer aelteren Leiste beobachtbar ist statt in `_reduziere_auf_undo`
geschluckt zu werden:

```python
    def aktualisiere_knoepfe(self, chat_id, message_id, knoepfe_):
        """Seit Karte U: eine aeltere Leisten-Nachricht wird auf ihren
        Undo-Knopf reduziert statt abgenommen."""
        self.aktualisiert.append((chat_id, message_id, list(knoepfe_)))
```

und `self.aktualisiert = []` in `__init__`.

- [ ] **Schritt 5: Tests laufen lassen, gruen sehen**

Run: `$PY -m pytest tests/test_erkenner.py tests/test_undo_knopf.py -q -p no:cacheprovider`
Erwartet: `tests/test_erkenner.py` vollstaendig gruen (Befund G.2: die
Attrappe delegiert `sende_mit_knoepfen` an `sende`, die Textzusagen bleiben
wahr), `tests/test_undo_knopf.py` `25 passed`.

- [ ] **Schritt 6: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4412 passed, 1 skipped`

Geht hier etwas anderes rot, ist es ein Test, der die Notiert-Meldung ohne
Tastatur erwartet. Dann gilt: **der Meldungstext wird weiter zeichengleich
geprueft** (`tg.gesendet` bleibt die Quelle, weil jede Attrappe
`sende_mit_knoepfen` an `sende` delegiert); angepasst wird nur die Erwartung
"keine Tastatur", und zwar mit einem Satz im Test, warum jetzt eine da ist.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/erkenner.py tests/test_erkenner.py tests/test_undo_knopf.py
git commit -m "Karte U: Schnappschuss um wende_an, Undo-Knopf unter jeder Notiert-Meldung

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 8: Die sieben Abnahmepunkte

**Dateien:**
- Test: `tests/test_undo_knopf.py` (erweitern) -- **kein Produktivcode**

Diese Aufgabe schreibt nur Tests. Geht einer rot, ist das ein Befund in den
Aufgaben 1-7 und wird dort behoben, nicht hier umgeschrieben.

- [ ] **Schritt 1: Die sieben Abnahmepunkte schreiben**

An `tests/test_undo_knopf.py` anhaengen:

```python
# --- Aufgabe 8: die sieben Abnahmepunkte der Karte ------------------------


def _laufe_und_undo(conn, tg, einst, aenderungen, message_id=1):
    """Ein ganzer Erkennerlauf und der Druck auf seinen Undo-Knopf -- der Weg,
    den die Gruppe im Chat geht."""
    _laufe(conn, tg, einst, aenderungen, message_id=message_id)
    daten = _undo_daten(tg)
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    message = repo.hole_knopf(conn, knopf_id)["message_id"]
    return knoepfe.behandle(
        conn, tg, None, einst,
        _druck(daten, message_id=message, query_id=f"q{knopf_id}"))


# 1. Kernthema gesetzt -> Undo -> Kernthema wie vorher (auch "leer").

def test_undo_stellt_das_kernthema_wieder_her(conn, tg, einst):
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Zusammenhalten")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Zusammenhalten"


def test_undo_stellt_ein_leeres_feld_wieder_her(conn, tg, einst):
    """"Wie vorher" heisst auch "leer" -- der haeufigste Fall: der erste,
    falsche Wert ueberhaupt."""
    phasen.setze(conn, 1, 3, "test")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand is None or stand["kernthema"] is None


# 2. Figur neu angelegt -> Undo -> Figur weg, keine Waisen.

def test_undo_nimmt_eine_neue_figur_weich_zurueck(conn, tg, einst):
    """Geprueft ueber den LESER (``repo.figuren``), nicht ueber rohes SQL:
    "Figur weg" heisst, dass kein Leser sie mehr sieht (N3).

    Mutation: ``entfernt_am`` nicht setzen -- die Figur bleibt in der Liste."""
    phasen.setze(conn, 1, 4, "test")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "figur_setzen", "wert": "Mira: laesst nicht locker"}])

    assert [f["name"] for f in repo.figuren(conn, 1)] == []


def test_undo_laesst_keine_waisen_in_szene_figur(conn, tg, einst):
    """Eine im selben Lauf entstandene Besetzung geht mit zurueck -- sonst
    zeigte ``szene_figur`` auf eine Figur, die es nicht mehr gibt.

    Mutation: den ``szene_figur``-Schritt ueberspringen."""
    phasen.setze(conn, 1, 4, "test")
    repo.setze_figur(conn, 1, "Pola", "still")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [repo.hole_figur(conn, 1, "Pola")["id"]])

    _laufe_und_undo(conn, tg, einst, [
        {"art": "figur_setzen", "wert": "Mira: laesst nichts gefallen"},
        {"art": "szene_planen", "wert": "Szene 1 | figuren: Pola, Mira"},
    ])

    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Pola"]
    assert [f["name"] for f in repo.szene_figuren(conn, szene_id)] == ["Pola"]
    # Und roh nachgezaehlt: keine Zeile zeigt auf eine entfernte Figur.
    waisen = conn.execute(
        "SELECT count(*) FROM szene_figur sf "
        "JOIN figur f ON f.id = sf.figur_id WHERE f.entfernt_am IS NOT NULL"
    ).fetchone()[0]
    assert waisen == 0


# 3. Szene geplant -> Undo -> Szene weg.

def test_undo_nimmt_eine_geplante_szene_zurueck(conn, tg, einst):
    """Mutation: ``"szene"`` aus ``ruecknahme.WEICH`` entfernen."""
    phasen.setze(conn, 1, 4, "test")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "szene_planen", "wert": "Szene 1 | ort: Bahnsteig | was_passiert: Warten"},
    ])

    assert repo.hole_szenen(conn, 1) == []


# 4. Zwei Aenderungen in einer Meldung -> ein Undo nimmt beide zurueck.

def test_ein_undo_nimmt_beide_aenderungen_der_meldung_zurueck(conn, tg, einst):
    """Eine Meldung, eine Ruecknahme -- keine Einzelauswahl.

    Mutation: in ``erkenner_lauf_schritte`` ein ``LIMIT 1`` einbauen."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Alter Konflikt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "hauptkonflikt_setzen", "wert": "Neuer Konflikt"},
    ])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["kernthema"], stand["hauptkonflikt"]) == ("Alt", "Alter Konflikt")
    assert "Kernthema: Neu" in tg.texte[-1]
    assert "Hauptkonflikt: Neuer Konflikt" in tg.texte[-1]


# 5. Feld nach dem Lauf erneut geaendert -> Undo aendert nichts, meldet es.

def test_undo_aendert_nichts_wenn_das_feld_seitdem_anders_ist(conn, tg, einst):
    """Mutation: die Wertpruefung in ``nimm_erkenner_lauf_zurueck`` weglassen
    -- dann ueberschriebe das Undo den Wert von Hand."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Neu"}])
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand gesetzt")

    daten = _undo_daten(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand gesetzt"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT in tg.texte


# 6. Doppeltipp -> einmal gewirkt.

def test_doppeltipp_wirkt_einmal(conn, tg, einst):
    """Die Sperre steht doppelt: ``beanspruche_knopf`` in ``behandle`` und das
    bedingte UPDATE auf ``erkenner_lauf``.

    Mutation: ``AND zurueckgenommen_am IS NULL`` weglassen."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Neu"}])
    daten = _undo_daten(tg)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q1"))
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Danach")
    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q2"))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Danach"
    assert len([t for t in tg.texte if t.startswith("Rueckgaengig gemacht:")]) == 1
    assert len(tg.beantwortet) == 2, "beide Druecke bekommen eine Antwort"


# 7. Dortmund deutsch, Padua englisch -- Verhalten gleich.

def test_undo_wirkt_in_padua_genauso(conn, tg, einst, padua):
    """Dasselbe Verhalten, englische Texte. ``_laufe`` faehrt denselben
    Codepfad; nur die Beschriftung und die Zeilen sind englisch."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Belonging")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Arriving"}])

    beschriftungen = [b for _, _, leiste, _ in tg.knoepfe for b, _ in leiste]
    assert "Undo" in beschriftungen
    daten = next(
        d for _, _, leiste, _ in tg.knoepfe for b, d in leiste if b == "Undo")
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Belonging"
    assert any(t.startswith("Undone:") for t in tg.texte)


# --- Die Waechter daneben -------------------------------------------------


def test_phase_bleibt_nach_undo(conn, tg, einst):
    """Kein Undo fuer die Phase (Karte): sie setzt allein die Gruppe.

    Mutation: ``phase`` aus ``ruecknahme.AUSSEN["arbeitsstand"]`` entfernen."""
    phasen.setze(conn, 1, 1, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "phase_setzen", "wert": "2"},
    ])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert phasen.aktuelle(conn, 1) == 2, "die Phase bleibt, wo die Gruppe sie hinstellte"


def test_usa_bleibt_nach_undo(conn, tg, einst):
    """Die US-Einwilligung ist eine Datenschutzentscheidung mit eigenen zwei
    Knoepfen -- offener Punkt fuer Birk, nicht diese Karte.

    Mutation: ``gruppe`` in ``ruecknahme.VERFOLGT`` aufnehmen."""
    phasen.setze(conn, 1, 6, "test")
    repo.merke_szene_usa_angeboten(conn, 1)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "szene_usa", "wert": "ja"},
    ])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert repo.szene_usa_stand(conn, 1) != "offen", "die Einwilligung steht weiter"


def test_journal_bleibt_stehen_und_bekommt_eine_zeile(conn, tg, einst):
    """Das Journal wird nur angehaengt (AGENTS.md): die Zeilen des Laufs
    bleiben, die Ruecknahme kommt daneben.

    Mutation: ``journal`` in ``VERFOLGT`` aufnehmen (dann verschwaende das Undo
    die Chronik) oder die Ruecknahme-Journalzeile weglassen."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "entschieden", "wert": "Wir bleiben bei vier Figuren."},
    ])
    vorher = [z["text"] for z in repo.journal(conn, 1)]
    assert any("vier Figuren" in t for t in vorher)

    daten = _undo_daten(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    nachher = [z["text"] for z in repo.journal(conn, 1)]
    assert all(t in nachher for t in vorher), "keine Zeile verschwindet"
    assert any(t.startswith("Zurueckgenommen:") for t in nachher)
```

- [ ] **Schritt 2: Laufen lassen**

Run: `$PY -m pytest tests/test_undo_knopf.py -q -p no:cacheprovider`
Erwartet: `38 passed`

Vor dem Lauf die Hilfsnamen gegen den Code pruefen -- sie existieren, aber die
Signaturen wollen gesehen sein:

```bash
grep -n "def merke_szene_usa_angeboten\|def szene_usa_stand\|def hole_szenen\|def stelle_szene_sicher" interview_theater/repo.py
grep -n "def zerlege_planung" interview_theater/szene.py
```

Weicht ein Name ab, wird der **Test** angepasst, nicht der Produktivcode.
Der `wert` von `szene_planen` folgt der Form aus `szene.zerlege_planung`
(`|`-getrennte Felder); stimmt die Form im Test nicht, liefert
`_wende_szene_planen_an` `None` und der Test schlaegt sofort mit "kein
Undo-Knopf" fehl -- das ist die Rueckmeldung, die ihn korrigiert.

- [ ] **Schritt 3: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4425 passed, 1 skipped`

- [ ] **Schritt 4: Commit**

```bash
git add tests/test_undo_knopf.py
git commit -m "Karte U: die sieben Abnahmepunkte als Tests, mutationsfest

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 9: Rundreise je Art, mutationsfest

**Dateien:**
- Test: `tests/test_ruecknahme_rundreise.py` (neu) -- **kein Produktivcode**

Der Beweis, dass der Diff alles erfasst: ein parametrisierter Test ueber
**jede** undo-faehige Art. Fixture-DB im Spaetstand
(`tests/fixture_spaetstand.py` -- dieselbe Gruppe, gegen die schon die
Prompt-Audit-Tests messen; eine frische Datenbank zeigt keinen der
interessanten Faelle), Dump aller verfolgten Tabellen, Lauf anwenden, Undo,
Dump wieder vergleichen.

**Schnittstellen:**
- Verbraucht: `fixture_spaetstand.baue_spaetstand`, `erkenner.wende_an`,
  `repo.schnappschuss`, `ruecknahme.*`, `repo.nimm_erkenner_lauf_zurueck`

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_ruecknahme_rundreise.py`:

```python
"""Der Beweis, dass die Ruecknahme wirklich ALLES erfasst (Karte U, Aufgabe 9).

Die Gefahr, gegen die dieser Test steht: der Diff vergisst eine Spalte, weil
sie in ``ruecknahme.AUSSEN`` gelandet ist oder weil ein Schreibpfad eine
Tabelle anfasst, die niemand verfolgt. Beides faellt im Betrieb erst auf, wenn
eine Gruppe ein Undo druckt und die Haelfte stehen bleibt.

Zwei Waechter:

1. **Rundreise je Art**: Dump aller verfolgten Tabellen -> Lauf anwenden ->
   Undo -> Dump ist wieder derselbe (bis auf Zeitstempel und die weich
   entfernten Neuanlagen).
2. **Vollstaendigkeit von VERFOLGT**: Dump ALLER Spalten ALLER Tabellen dieser
   ``chat_id`` vor und nach dem Anwenden -- jede geaenderte Spalte muss
   verfolgt sein oder in ``AUSSEN_VOR`` stehen, mit Grund. Damit faellt eine
   neue, ungeprueft beschriebene Spalte beim naechsten Umbau hier auf und
   nicht im Workshop.

Kein Netz, kein Modell: ``wende_an`` bekommt die Aenderungen als Liste, wie es
``erkenner.laufe`` nach dem Modellaufruf auch tut. Erfundenes Material.
"""

import json

import pytest

from interview_theater import db, erkenner, repo, ruecknahme
from tests.fixture_spaetstand import baue_spaetstand


#: Spalten, die ``wende_an`` aendert und die bewusst NICHT zurueckgenommen
#: werden -- je Eintrag ein Grund, wie ``BLEIBT_DEUTSCH`` in
#: tests/test_sprache_texte.py. Wer hier etwas eintraegt, trifft eine
#: Entscheidung und schreibt sie hin.
AUSSEN_VOR = {
    "arbeitsstand.phase": "Karte U: kein Undo fuer die Phase, sie setzt allein die Gruppe",
    "arbeitsstand.phase_angeboten": "Phasen-Buchhaltung (Merkposten des Angebots)",
    "arbeitsstand.phase_gesetzt_am": "Phasen-Buchhaltung",
    "arbeitsstand.geaendert_am": "Zeitstempel",
    "figur.geaendert_am": "Zeitstempel",
    "szene.geaendert_am": "Zeitstempel",
    "gruppe.letzte_extrahierte_message_id": "Wasserzeichen des Erkenners, kein Inhalt",
    "gruppe.interviewmodus_seit": "Interviewmodus: eigener Umschalter (Knopf/aufnahme)",
    "gruppe.wortlaut_modus": "wortlaut_an/aus bleiben still und haben ihren eigenen Weg",
    "gruppe.szene_usa_bestaetigt_am": "US-Einwilligung: eigene zwei Knoepfe (offener Punkt fuer Birk)",
    "gruppe.szene_usa_angeboten_am": "dito",
    "gruppe.szene_usa_offener_auftrag": "dito",
    "aufnahme.beendet_am": "Interviewmodus, eigener Umschalter",
    "aufnahme.status": "Interview-Buchhaltung, eigener Umschalter",
    "aufnahme.name": "interview_benennen bleibt still (baue_meldung)",
    "figur.quelle_aufnahme_id": (
        "figur_quelle_setzen bleibt still; die Zeile, die zaehlt, kommt aus "
        "sprachprofil.py -- verfolgt wird die Spalte trotzdem, siehe Test unten"
    ),
}

#: Ein Fall je undo-faehige Art: (Name, Vorbereitung, Aenderungen).
#: ``vorbereiten`` laeuft VOR dem Schnappschuss.
FAELLE = [
    (
        "kernthema_setzen",
        lambda conn: None,
        [{"art": "kernthema_setzen", "wert": "Was uns hier haelt"}],
    ),
    (
        "rahmen_setzen",
        lambda conn: None,
        [{"art": "rahmen_setzen", "wert": "Kiosk am Nordmarkt, Freitagabend"}],
    ),
    (
        "begriffe_setzen",
        lambda conn: None,
        [{"art": "begriffe_setzen", "wert": "Bleiben, Gehen, Geld"}],
    ),
    (
        "figur_setzen-neu",
        lambda conn: None,
        [{"art": "figur_setzen", "wert": "Nuran: zaehlt jeden Cent"}],
    ),
    (
        "figur_setzen-beschreibung",
        lambda conn: None,
        [{"art": "figur_setzen", "wert": "Leyla: will endlich gehoert werden"}],
    ),
    (
        # Der Fall, der den Nachbau je Art unmoeglich macht: ein
        # Platzhalter wird nachbenannt, und repo.fuehre_figur_zusammen
        # beruehrt figur, szene_figur und (weich) eine zweite figur-Zeile.
        "figur_setzen-platzhalter",
        lambda conn: _platzhalter(conn),
        [{"art": "figur_setzen", "wert": "Nesrin: laesst sich nichts gefallen"}],
    ),
    (
        "szene_planen-felder",
        lambda conn: None,
        [{"art": "szene_planen",
          "wert": "Szene 2 | ort: Kiosk | was_passiert: Cemre stellt Leyla"}],
    ),
    (
        "szene_planen-besetzung",
        lambda conn: None,
        [{"art": "szene_planen", "wert": "Szene 2 | figuren: Leyla, Cemre"}],
    ),
    (
        "festlegung_setzen",
        lambda conn: None,
        [{"art": "festlegung_setzen",
          "wert": "figur/Leyla: kommt aus der Nordstadt"}],
    ),
    (
        "entfernen-figur",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Figur Zeynep"}],
    ),
    (
        "entfernen-szene",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Szene 3"}],
    ),
    (
        "entfernen-arbeitsstandfeld",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Kernthema"}],
    ),
    (
        "transkript_korrigieren",
        lambda conn: None,
        [{"art": "transkript_korrigieren", "wert": "TTT -> UUU"}],
    ),
    (
        "entschieden-mit-figurenzahl",
        lambda conn: None,
        [{"art": "entschieden", "wert": "Wir nehmen vier Figuren."}],
    ),
    (
        "zwei-auf-einmal",
        lambda conn: None,
        [{"art": "kernthema_setzen", "wert": "Bleiben oder gehen"},
         {"art": "figur_setzen", "wert": "Nuran: zaehlt jeden Cent"}],
    ),
]


def _platzhalter(conn):
    """Eine Platzhalterfigur mit einer Beschreibung, die der naechste
    ``figur_setzen``-Eintrag wortgleich mitbringt -- das Signal, an dem
    ``erkenner._schmelze_platzhalter_ein`` zusammenfuehrt."""
    repo.setze_figur(conn, 1, "Figur 5", "laesst sich nichts gefallen")
    figur_id = repo.hole_figur(conn, 1, "Figur 5")["id"]
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])


@pytest.fixture
def spaet(tmp_path):
    """Die Spaetstand-Gruppe: Phase 6, vier Figuren, vier Szenen, ein
    Interview mit Themen, ein langer Verlauf. Eine frische Datenbank zeigt
    keinen der interessanten Faelle."""
    conn = db.verbinde(str(tmp_path / "spaet.db"))
    db.initialisiere(conn)
    baue_spaetstand(conn)
    return conn


ZEITSTEMPEL = ("geaendert_am", "erstellt_am", "phase_gesetzt_am")


def _dump(conn, tabellen):
    """Alle Spalten aller Zeilen dieser Gruppe, Zeitstempel ausgenommen --
    ein Vergleichswert, der von der Uhr unabhaengig ist."""
    fertig = {}
    for tabelle in tabellen:
        spalten = [
            name for name, _ in db._tabellenspalten_aus_schema()[tabelle]
            if name not in ZEITSTEMPEL
        ]
        zeilen = conn.execute(
            f"SELECT {', '.join(spalten)} FROM {tabelle} WHERE chat_id = ? "
            f"ORDER BY {', '.join(spalten)}",
            (1,),
        ).fetchall()
        fertig[tabelle] = [
            json.dumps({k: z[k] for k in spalten}, sort_keys=True) for z in zeilen
        ]
    return fertig


#: Die Tabellen, die der Rundreise-Vergleich ansieht -- die verfolgten plus die
#: Materialtabellen, damit eine Transkriptkorrektur mitgemessen wird.
ALLE = tuple(ruecknahme.VERFOLGT) + tuple(ruecknahme.MATERIAL)


def _lauf(conn, aenderungen, einst=None):
    """``wende_an`` mit Schnappschuss davor und danach, Lauf gespeichert --
    derselbe Ablauf wie in ``erkenner.laufe``, ohne Chat und ohne Modell."""
    plan = ruecknahme.plan(a["art"] for a in aenderungen)
    vorher = repo.schnappschuss(conn, 1, plan)
    wirkliche = erkenner.wende_an(conn, einst, 1, aenderungen)
    nachher = repo.schnappschuss(conn, 1, plan)
    lauf_id = repo.lege_erkenner_lauf_an(
        conn, 1, "\n".join(erkenner.undo_zeilen(wirkliche)) or "Probe",
        ruecknahme.schritte(vorher, nachher),
    )
    return lauf_id, wirkliche


def _nimm_zurueck(conn, lauf_id):
    return repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


@pytest.mark.parametrize("name, vorbereiten, aenderungen",
                         FAELLE, ids=[f[0] for f in FAELLE])
def test_rundreise_je_art_stellt_den_dump_wieder_her(
        spaet, einst, name, vorbereiten, aenderungen):
    """Anwenden, Undo, und der Dump ist wieder derselbe.

    Die eine erlaubte Abweichung: eine im Lauf ANGELEGTE Zeile bleibt als
    weich entfernte stehen (N3, "Weiches Loeschen statt Loeschen") -- sie
    wird deshalb aus dem Vergleich genommen und stattdessen einzeln geprueft.

    Mutation, die diesen Test rot macht: eine Spalte aus ``VERFOLGT``
    streichen (z. B. ``figur.beschreibung`` nach ``AUSSEN`` verschieben) --
    dann kommt der Dump nicht zurueck. Oder die Tabelle ``szene_figur``
    weglassen: dann schlaegt ``figur_setzen-platzhalter`` fehl."""
    vorbereiten(spaet)
    vorher = _dump(spaet, ALLE)

    lauf_id, wirkliche = _lauf(spaet, aenderungen, einst)
    assert wirkliche, f"{name}: der Lauf hat nichts geschrieben -- Fall pruefen"
    assert lauf_id is not None, f"{name}: kein Undo angelegt"
    assert _dump(spaet, ALLE) != vorher, f"{name}: der Lauf hat nichts veraendert"

    assert _nimm_zurueck(spaet, lauf_id) == repo.ZURUECK_OK

    nachher = _dump(spaet, ALLE)
    # Die weich entfernten Neuanlagen aus dem Vergleich nehmen und einzeln
    # pruefen: sie STEHEN noch, aber kein Leser sieht sie mehr.
    neu = [
        s for s in repo.erkenner_lauf_schritte(spaet, lauf_id)
        if s["art"] == "angelegt" and s["tabelle"] in ruecknahme.WEICH
    ]
    for schritt in neu:
        schluessel = json.loads(schritt["schluessel"])
        zeile = spaet.execute(
            f"SELECT entfernt_am FROM {schritt['tabelle']} WHERE id = ?",
            (schluessel["id"],),
        ).fetchone()
        assert zeile["entfernt_am"] is not None, (
            f"{name}: Neuanlage in {schritt['tabelle']} nicht weich entfernt"
        )
        nachher[schritt["tabelle"]] = [
            z for z in nachher[schritt["tabelle"]]
            if json.loads(z).get("id") != schluessel["id"]
        ]
        vorher[schritt["tabelle"]] = [
            z for z in vorher[schritt["tabelle"]]
            if json.loads(z).get("id") != schluessel["id"]
        ]

    assert nachher == vorher, f"{name}: der Stand kam nicht zurueck"


@pytest.mark.parametrize("name, vorbereiten, aenderungen",
                         FAELLE, ids=[f[0] for f in FAELLE])
def test_verfolgt_deckt_jede_geschriebene_spalte(
        spaet, einst, name, vorbereiten, aenderungen):
    """Jede Spalte, die ``wende_an`` tatsaechlich aendert, ist verfolgt -- oder
    steht in ``AUSSEN_VOR`` mit Grund.

    Verglichen wird ALLES: jede Spalte jeder Tabelle mit ``chat_id``, vorher
    und nachher. Damit faellt eine neue, ungeprueft beschriebene Spalte beim
    naechsten Umbau hier auf.

    Mutation, die diesen Test rot macht: eine von ``wende_an`` geschriebene
    Spalte nach ``ruecknahme.AUSSEN`` verschieben, ohne sie in ``AUSSEN_VOR``
    einzutragen."""
    vorbereiten(spaet)
    tabellen = [t for t in db.TABELLEN_MIT_CHAT_ID
                if t not in ("erkenner_lauf", "erkenner_lauf_schritt", "aufruf")]
    vorher = _alles(spaet, tabellen)

    erkenner.wende_an(spaet, einst, 1, aenderungen)

    verfolgt = ruecknahme.plan(a["art"] for a in aenderungen)
    offen = []
    for schluessel in _unterschiede(vorher, _alles(spaet, tabellen)):
        tabelle, spalte = schluessel.split(".", 1)
        if f"{tabelle}.{spalte}" in AUSSEN_VOR:
            continue
        if tabelle == "journal":
            continue  # nur-anhaengend, wird nie zurueckgenommen (AGENTS.md)
        if tabelle == "vorfall":
            continue  # Dashboard des Teams, kein Inhalt der Gruppe
        if tabelle in verfolgt and spalte in verfolgt[tabelle][1]:
            continue
        offen.append(f"{name}: {tabelle}.{spalte}")
    assert offen == [], (
        "geschrieben, aber nicht verfolgt und nicht begruendet -- entweder in "
        "ruecknahme.VERFOLGT/MATERIAL aufnehmen oder in AUSSEN_VOR eintragen"
    )


def _alles(conn, tabellen):
    """Tabelle.Spalte -> sortierte Werteliste, ueber alle Zeilen der Gruppe."""
    fertig = {}
    for tabelle in tabellen:
        spalten = [n for n, _ in db._tabellenspalten_aus_schema()[tabelle]]
        zeilen = conn.execute(
            f"SELECT {', '.join(spalten)} FROM {tabelle} WHERE chat_id = ?", (1,)
        ).fetchall()
        for spalte in spalten:
            if spalte in ZEITSTEMPEL:
                continue
            fertig[f"{tabelle}.{spalte}"] = sorted(
                json.dumps(z[spalte]) for z in zeilen)
    return fertig


def _unterschiede(vorher, nachher):
    return sorted(k for k in set(vorher) | set(nachher)
                  if vorher.get(k) != nachher.get(k))


def test_die_faelle_decken_jede_undo_faehige_art_ab():
    """Kein blinder Fleck: jede ``art``, die in der Notiert-Meldung landen kann
    und nicht ausgeschlossen ist, hat einen Fall."""
    gepruefte = {a["art"] for _, _, aenderungen in FAELLE for a in aenderungen}
    meldbar = {
        "kernthema_setzen", "format_setzen", "rahmen_setzen",
        "geschichte_setzen", "hauptkonflikt_setzen", "begriffe_setzen",
        "fragen_setzen", "figur_setzen", "szene_planen", "festlegung_setzen",
        "transkript_korrigieren", "entfernen", "entschieden",
    }
    fehlend = meldbar - gepruefte - ruecknahme.ZEILEN_OHNE_UNDO
    # format/geschichte/hauptkonflikt/fragen laufen durch denselben Pfad wie
    # kernthema (erkenner._wende_arbeitsstand_an, ein Feld) -- sie sind mit
    # kernthema_setzen und rahmen_setzen abgedeckt.
    assert fehlend <= {
        "format_setzen", "geschichte_setzen", "hauptkonflikt_setzen",
        "fragen_setzen",
    }, f"ohne Fall: {sorted(fehlend)}"
```

- [ ] **Schritt 2: Laufen lassen, Faelle nachziehen**

Run: `$PY -m pytest tests/test_ruecknahme_rundreise.py -q -p no:cacheprovider`
Erwartet: `31 passed` (15 Faelle x 2 + 1)

Schlaegt ein Fall mit "der Lauf hat nichts geschrieben" fehl, passt der `wert`
nicht zum Parser dieser Art -- dann wird der **Fall** korrigiert (der Wortlaut
steht in `erkenner.ARTEN` und in `prompts/erkenner.md`), nicht der
Produktivcode. Schlaegt `test_verfolgt_deckt_jede_geschriebene_spalte` fehl,
ist das ein **echter Befund**: entweder die Spalte gehoert nach
`ruecknahme.VERFOLGT`/`MATERIAL`, oder sie gehoert mit Grund nach
`AUSSEN_VOR`. Beides ist eine Entscheidung und wird hingeschrieben.

- [ ] **Schritt 3: Die ganze Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4456 passed, 1 skipped`

- [ ] **Schritt 4: Commit**

```bash
git add tests/test_ruecknahme_rundreise.py
git commit -m "Karte U: Rundreise je Art und der Waechter fuer VERFOLGT

Dump aller verfolgten Tabellen im Spaetstand, Lauf anwenden, Undo, Dump wieder
gleich -- fuer jede undo-faehige Art. Dazu der Vergleich ALLER Spalten aller
Tabellen der Gruppe: eine geschriebene, aber nicht verfolgte Spalte faellt hier
auf und nicht im Workshop.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Aufgabe 10: Web bedingt, AGENTS.md, Abschluss

**Dateien:**
- Aendern: `AGENTS.md`
- Test (bedingt): `tests/test_undo_web.py` (nur wenn `web_kanal.py` existiert)

- [ ] **Schritt 1: Den Web-Zweig pruefen**

```bash
test -f interview_theater/web_kanal.py && echo DA || echo FEHLT
```

* **`FEHLT`** (erwartet): kein Test, kein Webserver-Code. Statt dessen ein
  Uebergabe-Punkt im Abschlussbericht (siehe unten). Weiter mit Schritt 3.
* **`DA`**: A2 ist inzwischen gemergt. Dann Schritt 2.

- [ ] **Schritt 2 (nur bei `DA`): Der WebKanal-Test**

`tests/test_undo_web.py`:

```python
"""Der Undo-Knopf im Web-Chat -- derselbe Weg, keine eigene Logik (Karte U,
Punkt 4).

Laeuft nur, wenn Karte A2 den Kanal geliefert hat: der Knopf haengt an
``knoepfe.behandle`` im Bot-Prozess, und dieser Test prueft, dass der neue
Code ausschliesslich ueber die vier Kanal-Verben geht.
"""

import pytest

web_kanal = pytest.importorskip("interview_theater.web_kanal")

from interview_theater import erkenner, knoepfe, phasen, repo


def test_der_undo_knopf_erscheint_im_web_post(conn, einst):
    kanal = web_kanal.WebKanal(conn, 1)
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    repo.merke_nachricht(conn, 1, 1, "Mert", 0, "text", "neues Kernthema",
                         repo._jetzt())

    class KLM:
        def schema(self, *_a, **_kw):
            return {"aenderungen": [{"art": "kernthema_setzen", "wert": "Neu"}]}

    erkenner.laufe(KLM(), kanal, conn, einst, 1)

    knoepfe_im_web = [
        b for eintrag in kanal.verlauf() for b, _ in eintrag.get("knoepfe", [])
    ]
    assert knoepfe.T._TEXT_UNDO_KNOPF in knoepfe_im_web


def test_der_druck_im_web_wirkt(conn, einst):
    """Derselbe ``knoepfe.behandle``-Eingang, dieselbe Wirkung."""
    kanal = web_kanal.WebKanal(conn, 1)
    lauf_id = repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: Neu", [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {"kernthema": "Alt"},
         "nachher": {"kernthema": "Neu"}},
    ])
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu")
    daten = knoepfe.undo_leiste(conn, 1, lauf_id)[0][1]

    knoepfe.behandle(conn, kanal, None, einst, {
        "callback_query_id": "w1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 1,
    })

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"


def test_der_neue_code_ruft_nichts_telegram_spezifisches():
    """Die Kanal-Zusage: ``sende``, ``sende_mit_knoepfen``,
    ``aktualisiere_knoepfe``, ``entferne_knoepfe``, ``beantworte_knopf`` --
    und sonst nichts an ``tg``."""
    import ast
    import inspect
    import pathlib

    erlaubt = {"sende", "sende_mit_knoepfen", "aktualisiere_knoepfe",
               "entferne_knoepfe", "beantworte_knopf", "sende_datei"}
    for modul in (knoepfe.basis, knoepfe.wirkung, erkenner):
        baum = ast.parse(
            pathlib.Path(inspect.getfile(modul)).read_text(encoding="utf-8"))
        for k in ast.walk(baum):
            if (isinstance(k, ast.Attribute)
                    and isinstance(k.value, ast.Name) and k.value.id == "tg"):
                assert k.attr in erlaubt, f"{modul.__name__}: tg.{k.attr}"
```

Run: `$PY -m pytest tests/test_undo_web.py -q -p no:cacheprovider`
Erwartet: `3 passed`

- [ ] **Schritt 3: AGENTS.md**

Drei Stellen, alle additiv.

**(a) Modultabelle** -- hinter der Zeile zu `repo.py`, alphabetisch bei den
Fachlogik-Modulen (neben `kuerzung.py`):

```markdown
| `ruecknahme.py` | Die Ruecknahme eines Erkennerlaufs (01.10.2026, Karte U): welche Tabellen und Spalten verfolgt werden (`VERFOLGT`, `MATERIAL`, `AUSSEN`) und wie aus zwei Schnappschuessen um `wende_an` die Ruecknahme-Schritte werden (`schritte`). **Reine Funktionen, kein SQL, kein Nutzertext** -- alles SQL steht in `repo.py`, die Wortlaute in `knoepfe/texte.py`. `db` wird nur fuer die Spaltenliste gelesen (`_tabellenspalten_aus_schema`), damit eine neue Spalte automatisch mitverfolgt wird |
```

Und in der Schichtentabelle der Modulkarte, bei **Fachlogik**, `ruecknahme.py`
hinter `kuerzung.py` ergaenzen.

**(b) "Wo man anfaengt, je nach Frage"** -- eine Zeile:

```markdown
| Wie nehme ich einen Erkennerlauf zurueck? | `knoepfe.wirkung._wirkung_undo` → `repo.nimm_erkenner_lauf_zurueck`; was erfasst wird: `ruecknahme.VERFOLGT` |
```

**(c) Ein Absatz unter den bindenden Entwurfsentscheidungen**, hinter
"Kuerzen ist eine Ueberarbeitung, keine neue Szenenfolge":

```markdown
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
```

Und bei den Tabellen im Abschnitt zu `db.py` bzw. in der Fallen-Liste nichts --
es kommt keine Falle dazu.

- [ ] **Schritt 4: Die Abschlusspruefungen**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `4456 passed, 1 skipped` (bzw. `4459` mit dem Web-Zweig) --
**mindestens 4350, 0 failed**.

Run: `$PY -m scripts.pruefe_profil dortmund-2026`
Erwartet: Exit-Code 0, keine Fehlerzeile (E3 -- das Dortmunder Profil bleibt
gruen; die Karte fasst kein Profil an).

Run: `$PY -m scripts.pruefe_profil padua-2026`
Erwartet: Exit-Code 0.

Run: `git status --short`
Erwartet: leer bis auf die Arbeiterdateien (`.cc-*`, `.superpowers-brief-*`) --
die werden **nie** committet.

Kein Modellaufruf in dieser Karte: weder `scripts/pruefe_prompts.py` noch
`scripts/simulation.py` noch `scripts/rauchtest.py` laufen. Der Erkenner-Prompt
(`prompts/erkenner.md`) wird **nicht** angefasst -- es kommt keine Erkenner-art
dazu, also ist kein Korpuslauf faellig.

- [ ] **Schritt 5: Commit**

```bash
git add AGENTS.md
git commit -m "Karte U: AGENTS.md -- ein Erkennerlauf ist mit einem Tipp zuruecknehmbar

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

(Mit Web-Zweig zusaetzlich `tests/test_undo_web.py`.)

---

## Uebergaben

1. **Web-Anbindung (A2), falls `web_kanal.py` beim Umsetzen fehlt.** Der
   Undo-Knopf laeuft ausschliesslich ueber die vier Kanal-Verben
   (`sende_mit_knoepfen`, `aktualisiere_knoepfe`, `entferne_knoepfe`,
   `beantworte_knopf`) und ueber `knoepfe.behandle` -- er funktioniert im
   Web-Chat, sobald A2 den Kanal liefert, **ohne eine Zeile eigener Logik**.
   Was noch fehlt: der Test darueber (`tests/test_undo_web.py`, Code steht in
   Aufgabe 10 Schritt 2, fertig zum Einsetzen). Fuer die W/UX-Karten.
2. **Undo fuer Knopf- und Web-Speicherungen ist bewusst NICHT gebaut.** Eine
   Notiert-Zeile aus `knoepfe.basis._speichere` oder aus der Gruppenseite ist
   eine bewusste Handlung der Gruppe an einem fixen Wert -- dort hat sich
   keine Schicht geirrt. Die Karte richtet sich gegen den stillen Fehler der
   Modell-Schicht. Wer das aendern will, braucht je Weg einen Schnappschuss und
   eine Lauf-Zeile; die Bausteine (`ruecknahme`, `repo.lege_erkenner_lauf_an`,
   `knoepfe.undo_leiste`) sind dafuer schon offen.
3. **Undo fuer die USA-Einwilligung: offener Punkt fuer Birk.** Siehe
   Plan-Kopf. Die Zeile steht in der Meldung, aber nicht in der Ruecknahme.
4. **Grenzen, die im Code stehen und bleiben:**
   * Der Schnappschuss laeuft je Erkennerlauf zweimal ueber fuenf Tabellen
     dieser `chat_id` (bei einer Transkriptkorrektur ueber acht). Das ist ein
     `SELECT` je Tabelle ohne Join; gemessen wurde es nicht, weil der
     Erkenner-Nachlauf ohnehin hinter einem Modellaufruf haengt. Wird eine
     Gruppe sehr gross, ist `repo.schnappschuss` die Stelle, die man ansieht.
   * `ruecknahme.AUSSEN` nimmt die Felder heraus, die ein **spaeterer**
     Lauf schreibt (Sprachprofil, Volltext, bestaetigte Form und Stil).
     Folge: ein Undo dreht sie nie zurueck -- und blockiert auch nicht an
     ihnen. Ein Lauf, der ausser einem Kernthema nur `figur_quelle_setzen`
     enthaelt, nimmt die Interview-Zuordnung mit zurueck, ohne sie zu nennen
     (sie ist in der Meldung still). Gemessen selten, weil die beiden Arten in
     verschiedenen Phasen leben; wenn es stoert, ist die Stelle
     `erkenner.undo_zeilen`.
   * Der Undo-Knopf lebt so lange, wie Telegram die Nachricht zeigt. Es gibt
     **keine Verfallszeit** -- die "Seitdem geaendert"-Probe ist der Schutz,
     nicht die Uhr. Ein Undo auf einen drei Tage alten Lauf ist damit
     moeglich, solange niemand die betroffenen Felder angefasst hat.
   * `erkenner_lauf_schritt` waechst mit jedem Lauf und wird nie aufgeraeumt.
     Eine Zeile ist ein kurzes JSON; bei einer Transkriptkorrektur traegt sie
     ein ganzes Transkript zweimal. Aufgeraeumt wird beim Loeschen der Gruppe
     (`db.loesche_gruppe`), sonst nicht -- wie beim Journal.




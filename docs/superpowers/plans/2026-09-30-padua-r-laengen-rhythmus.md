# Padua R: Laengen-Rhythmus je Szene und deterministischer Sprachpass am Ende

> **Fuer agentische Umsetzer:** ERFORDERLICHE UNTER-SKILL: Nutze
> `superpowers:subagent-driven-development` (empfohlen) oder
> `superpowers:executing-plans`, um diesen Plan Aufgabe fuer Aufgabe
> umzusetzen. Die Schritte tragen Checkboxen (`- [ ]`) zum Mitfuehren.

**Ziel:** Fuer das Padua-Profil waehlt der **Code** je Szene ein Wortbudget
aus einem gewuerfelten Rhythmus-Muster (nie alle Szenen gleich lang), zaehlt
nach dem Schreiben nach und haengt genau **einen** Ueberarbeitungslauf an, der
zugleich vier mechanisch gezaehlte Sprachmuster (Gedankenstrich-Inflation,
"not X but Y", Adjektiv-Dreierketten, Fazitsatz) beseitigt -- ohne ein
woertliches Belegzitat zu verlieren. Dortmund verhaelt sich zeichengleich wie
vorher.

**Architektur:** Drei neue Module in der Fachlogik-Schicht, streng getrennt
nach "rechnet" / "zaehlt" / "stoesst an":

| Modul | Aufgabe | Modell? | Datenbank? |
|---|---|---|---|
| `interview_theater/laengen.py` | Wortzaehler, Rhythmus-Wuerfel, Budgets, Prompt-Bausteine | nein | nein (nur reine Werte; der Faktor kommt als Argument) |
| `interview_theater/sprachpass.py` | vier Regex-Zaehler, Grenzwertvergleich, Notiztext, Zitatschutz | nein | nur lesend, eine Funktion (`gepruefte_zitate`) |
| `interview_theater/nachpass.py` | der EINE Ueberarbeitungslauf je Schreibweg, Wache dagegen, dass es ein zweiter wird | ja, ueber die bestehenden Schreibwege | ja |

Die Konfiguration liegt vollstaendig im Workshop-Profil
(`profil.toml`, Abschnitte `[laengen]` und `[sprachpass]`); der Hauptschalter
`laengen.aktiv` steht im eingebauten Vorgabeprofil auf `false`, und **das** ist
die Zusage an Dortmund. Angehaengt wird der Nachpass **innerhalb der
bestehenden Schreib-Threads und unter deren Sperre** (`szene._lauf`,
`kurzgeschichte._lauf`) -- dadurch ist "hoechstens ein zusaetzlicher Lauf je
Szene" keine Absprache, sondern ein gerader Codepfad ohne Schleife.

**Tech Stack:** Python 3.11, Standardbibliothek (`re`, `tomllib`), `pytest`,
SQLite. Keine neue Abhaengigkeit.

---

## Globale Vorgaben (gelten fuer jede Aufgabe)

- **Python:** `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
  Das `.venv` im Hauptbaum **nicht** verwenden; `python3` des Systems ist 3.9
  und kann `X | None` nicht importieren.
- **Suite:** `SUITE="$PY -m pytest -q -p no:cacheprovider"`.
- **Basislinie, selbst gemessen am 30.09.2026 auf `d8deb6c` in diesem
  Worktree:** `2768 passed, 1 skipped in 237.98s`. Nach **jeder** Aufgabe muss
  die Suite mindestens auf dieser Zahl stehen (neue Tests erhoehen sie; ein
  `failed` oder ein Rueckgang bei `passed` ist ein Abbruch).
- **Branch:** eigener Branch, aus dem Stand nach dem Merge von A1 und P.
  **Kein Merge, kein Push, kein PR.** Ein Commit je Aufgabe.
- **Projektsprache Deutsch** fuer Bezeichner, Docstrings, Kommentare,
  Commit-Messages. ASCII-Umschrift `ue/oe/ae/ss` wie im ganzen Repo; Umlaute
  nur, wo sie schon stehen (Prompt-Dateien, einzelne Kommentare).
- **Datenschutz:** `betrieb/**` (soap.db, Audio, Transkripte, `.env`) wird
  **nie** gelesen, nie in einen Prompt gelegt, nie committet. Fuer Tests und
  Messungen nur erfundene Fixtures bzw. `simulation/interviews/`. Eine
  `betrieb/<gruppe>.env` wird ausschliesslich mit
  `set -a; . betrieb/gruppe1.env; set +a` geladen und nie ausgegeben.
- **Kostendeckel** (Birk E7): 5 CHF je Gruppe und Tag. Bezahlte Aufgaben
  stehen am Ende und sind als solche markiert.
- **Zusage 2 bleibt:** kein Modellaufruf in einem Knopf-Handler und in keinem
  Slash-Befehl. Der Nachpass laeuft in dem Thread, den der Schreibweg ohnehin
  schon aufgemacht hat.
- **Journal wird nur angehaengt** (`repo.schreibe_journal`), nie geaendert,
  nie geloescht.
- **`zitat.pruefe` ist die einzige Zitat-Normalisierung.** Es gibt keine
  zweite, groosszuegigere.
- **Dortmund-Nachweis nach jeder Aufgabe, die Prompt-Text beruehrt:**
  `$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/profile/` -> `passed`,
  und `$PY -m scripts.pruefe_profil dortmund-2026` -> Exit 0.

---

## Praemissenpruefung (selbst am Code geprueft, 30.09.2026, `d8deb6c`)

Alle von der Karte genannten Stellen stimmen; zwei Zeilennummern liegen
etwas anders als genannt, und ein Punkt der Karte trifft nicht zu. Die Liste
ist die Grundlage der Planung -- wer sie nachprueft, braucht keinen
Modellaufruf.

| Behauptung | Befund |
|---|---|
| `kurzgeschichte.py:62` -- feste Gesamtlaenge | **stimmt.** `interview_theater/kurzgeschichte.py:62` ist die Zeile `Insgesamt 1.500 bis 3.500 Woerter.` Sie steht als **eigener Absatz** in `ANWEISUNG` (gemessen: davor und danach `\n\n`), ist also ohne Rest ersetzbar. |
| `kurzgeschichte.py:204` -- `theater-tells` im Schreib-Prompt | **stimmt.** `:201` haengt `formen/prosa` an, `:204` `theater-tells`, beide ueber `anweisungen.hole_optional` (heiss nachgeladen). |
| `kurzgeschichte.py:248` -- die Zahl noch einmal | **stimmt.** Im Docstring von `baue_nutzertext` (`"1.500 bis 3.500 Woerter"`) als Begruendung dafuer, dass es dort **keine** Eingabe-Budgetpruefung gibt. |
| `formen/prosa.md:27` -- dieselbe Zahl im Regelblock | **stimmt** (`:26-28`). Damit steht der Fakt an **zwei** Stellen desselben Prompts -- gegen die Audit-Regel "ein Fakt hat genau eine Stelle". Beide gehen in `kurzgeschichte.systemanweisung()`. |
| `szene.py` -- `theater-tells`-Einbindung "um :322-362" | **stimmt der Sache nach, Zeilen etwas anders:** die Erwaehnung im Docstring steht `:322`, die tatsaechlichen Anhaenge stehen `:351` (Prosa-Pfad: `formen/prosa` + `theater-tells`) und `:362` (Formen-Pfad). |
| `kuerzung.py` -- der Kuerzungspfad | **stimmt.** `PROZENT = 25` (`:56`), `notiz_fuer_szene()`, `notiz_fuer_prosa(anzahl)`, `nummer_aus_wert()`, `starte(...) -> (quittung, gestartet)`. Mit Nummer -> `szene.starte` mit `BISHER_MARKER`; ohne -> `kurzgeschichte.starte(..., vorlage=True)`. **Kein eigener Modellaufruf.** |
| Erkenner-Art `szene_kuerzen` | **stimmt.** In `erkenner.py:127` (Artenliste), ausgewertet in `_starte_kuerzung` (`:1628`), hoechstens eine je Lauf (`:1658`), gerufen aus `laufe()` (`:1855`). `prompts/erkenner.md:183` ist Punkt 23. **Nicht** in `ARTEN_IN_AUFNAHME` (`:167`). |
| Knopfweg | **stimmt.** `knoepfe/wirkung.py:385 _wirkung_geschichte_kuerzen` (ganze Geschichte) und `:381 _wirkung_szene_kuerzen` (eine Szene), beide rufen nur `kuerzung.starte`. |
| "Phase 6 hat keine Form, ein Budget je Form kann dort nicht greifen" | **trifft nicht zu -- siehe den eigenen Abschnitt unten.** Die Szenenfolge steht beim Eintritt in Phase 6 fest (`phasen.voraussetzungen`, `interview_theater/phasen.py:373-375`: `6` verlangt `geschichte` **und** `szenen`), `formen/prosa.md:29-33` erklaert eine vorhandene Folge fuer **verbindlich**, und je Szene liegt eine Form **vor** -- entweder bestaetigt in `szene.form` oder als `szene.form_vorschlag`. |

### Weitere Stellen, auf denen der Plan aufsetzt (alle selbst geprueft)

- `szene.schreibe(conn, tg, klm, e, chat_id, auftrag) -> int` (`szene.py:2046`)
  ist synchron und prueft die Sperre **nicht** selbst; `szene._lauf`
  (`:2195`) haelt sie und gibt sie im `finally` frei; `szene.starte`
  (`:2221`) prueft, kuendigt an und startet den Thread. Ein Nachpass kann
  deshalb **nicht** `szene.starte` rufen (die Sperre liegt noch), sondern nur
  `szene.schreibe` -- genau wie `dramaturgie/schleife.py` es schon tut.
- `szene.baue_nutzertext` baut Bloecke in `_bloecke` und fuegt sie in der
  Reihenfolge `_REIHENFOLGE` (`szene.py:1698`) zusammen; ein leerer Block
  faellt ersatzlos weg (`_zusammen`, `:1704`). Ein neuer Block, der leer
  bleibt, laesst den Nutzertext **zeichengleich**.
- `kurzgeschichte._lauf` ist eine geschachtelte Funktion in `starte`
  (`:275-330`) und gibt die Sperre im `finally` frei. Sie ist heute von
  ausserhalb **nicht** synchron aufrufbar -- Aufgabe 7 holt sie heraus.
- `repo.aktualisiere_szene(conn, szene_id, titel, kurzbeschreibung,
  volltext, zusammenfassung=None, prosa=None)` (`repo.py:2092`) schreibt
  `volltext`/`prosa` nur, **wenn sie mitkommen**. Das ist der Rueckweg fuer
  einen verworfenen Nachpass. `repo.setze_szenenfeld` kann es nicht:
  `volltext`/`prosa` stehen nicht in `repo.SZENENFELDER` (`:2143`), sondern
  in `repo.GESCHUETZTE_SZENENFELDER` (`:2277`).
- `repo.haenge_szenenfassung_an` ist **nur anhaengend**; es gibt bewusst kein
  Aktualisieren und kein `entfernt_am` (`db.py`, Schema `szenenfassung`).
  Eine verworfene Nachpass-Fassung bleibt also als Zeile stehen -- richtig
  so, sie ist die Spur.
- Geprueefte Zitate: `repo.gepruefte_themen(conn, chat_id)` (`repo.py:867`,
  SQL `zitat_geprueft = 1`, Spalte `beleg_zitat`) und `figur.zitate`
  (`db.py:342`; ohne ein einziges belegtes Zitat wird gar nichts
  gespeichert). `repo.schaerfungen` liefert `zitat` als Alias auf
  `verdichtung_thema.beleg_zitat` (`_SCHAERFUNG_SELECT`, `repo.py:1027`) --
  also eine Teilmenge der ersten Quelle, kein dritter Ort.
- `zitat.pruefe(zitat, transkript)` normalisiert Whitespace-Folgen und
  typografische Anfuehrungszeichen, sonst nichts (`zitat.py`).
- `llm.prosa(chat_id, system, nutzer, art, max_tokens=None, timeout=None)`
  (`llm.py:209`) und `szene_claude.prosa(..., art, timeout=...)`
  (`szene_claude.py:89`) nehmen `art` als **Parameter**. Die Tabelle `aufruf`
  hat `art TEXT NOT NULL` frei (`db.py:705-717`) -- eigene `art`-Werte sind
  also getrennt zaehlbar, wie `dramaturgie_b1` es vormacht.
- `db._migriere_fehlende_spalten` (`db.py:783`) liest die Sollspalten aus
  `SCHEMA` (`_tabellenspalten_aus_schema`, `:763`) und ergaenzt fehlende per
  `ALTER TABLE ... ADD COLUMN`. Eine neue Spalte in `SCHEMA` genuegt; kein
  `SCHEMA_VERSION`-Schritt (der ist fuer Umnummerierungen).
- `repo.setze_arbeitsstand` laesst nur Felder aus `_ARBEITSSTAND_FELDER`
  (`repo.py:1608`) zu -- eine neue Spalte muss dort **auch** eingetragen
  werden, sonst `ValueError`.
- Eine neue `arbeitsstand`-Spalte ist fuer die Weboberflaeche unsichtbar
  (`web_schreiben.FELDER`/`NUR_ANZEIGE` sind explizite Listen) und fuer die
  Simulationskennzahl `arbeitsstand_vollstaendig` ebenfalls
  (`simulation/kennzahlen.py:549` zaehlt genannte Felder; `skript.felder_fuer_phase`
  gleicht ueber **Phasen-Kurznamen** ab, und "Laengen" ist keiner).
- `workshop.Profil.wert("a.b", vorgabe)` (`workshop.py:435`) liest einen
  Punktpfad und liefert `vorgabe`, wenn irgendein Schritt fehlt. Ein neuer
  Abschnitt in `VORGABE_WERTE` braucht deshalb **keinen** neuen Accessor.
- `_vereinige` (`workshop.py:402`) legt Profilwerte Ebene fuer Ebene ueber
  die Vorgabe; eine **Liste** ersetzt die Vorgabeliste vollstaendig.
  `_einfrieren` (`:388`) macht Dicts zu `MappingProxyType` und Listen zu
  Tupeln -- `muster` kommt als Tupel von Tupeln zurueck.
- `tests/test_workshop.py:41` vergleicht
  `_entpacke(dortmund.werte) == workshop.VORGABE_WERTE`. Weil `_vereinige`
  die Vorgabe darunter legt, bleibt dieser Test **gruen**, wenn ein neuer
  Abschnitt nur in `VORGABE_WERTE` steht und nicht in
  `workshop/dortmund-2026/profil.toml`. Dortmunds `profil.toml` wird also
  **nicht angefasst**.
- `tests/test_profil_bitgleich.py:_vergleiche` (`:90-105`) erlaubt **neue**
  Abschnitte im Fingerabdruck und verbietet fehlende oder veraenderte.
  `prompt_schnappschuss.teile()` (`scripts/prompt_schnappschuss.py:62`)
  enthaelt heute **nicht** `kurzgeschichte.systemanweisung()` -- Aufgabe 6
  traegt es nach, ohne die Massstab-Datei anzufassen.
- **Selbst gemessen als Massstab fuer Aufgabe 6:**
  `kurzgeschichte.systemanweisung()` ist auf `d8deb6c`
  **12785 Zeichen**, `sha256 = 704119e3dd886eef7ac619511b4ab70cc7c6fb6858a8618e4ee2da19ffddc729`.
- Wortzaehlung: es gibt heute **keinen** gemeinsamen Zaehler.
  `sprecher._worte` (`sprecher.py:100`) zaehlt `[\w'’]+` **nach** Entfernen
  der Regieanweisungen (fuer Sprechanteile richtig, fuer ein Laengenbudget
  falsch); `ablauf.py:211`, `aufnahme.py:1018`,
  `dramaturgie/mechanik.py:765` und `dramaturgie/fanout.py:941` nutzen
  `len(text.split())` (Satzzeichen zaehlen mit). Aufgabe 2 legt **einen**
  Zaehler an und laesst die bestehenden unberuehrt.
- `simulation/` kennt `IT_WORKSHOP` **nicht** -- kein Schalter, keine
  Erwaehnung (`grep` ueber `simulation/` und `scripts/simulation.py`: kein
  Treffer). Das Profil wirkt dort allein ueber die Umgebungsvariable des
  Prozesses. `SET_WAHL` ist `("1","2","3", "birk") + tag1.SETS`
  (`scripts/simulation.py:131`).
- **Gemessene Kosten-Basislinie fuer Aufgabe 21**, aus
  `simulation/berichte/verlauf.jsonl` gelesen (nicht geschaetzt): der teuerste
  Lauf mit Szenentext ist `2026-09-06-regie-1` mit `chf_bot = 0.636`,
  `aufrufe = 95`, `dauer_s = 1848`. Laeufe ohne eigenen Szenenlauf liegen bei
  `0.206`-`0.408` CHF und 71-123 Aufrufen.

---

## Phase 6 und Phase 7: wo das Budget herkommt (die Entscheidung)

Die Karte vermutet, ein Budget je Form koenne in Phase 6 nicht greifen, weil
dort `szene.form` NULL bleibt. **Am Code stimmt das nicht**, und die
Eichungszahlen des Architekten belegen es zusaetzlich (Dortmund v2, Abschnitt
1 "Am Steg" traegt `chor`, Abschnitt 3 "Fronten" `rap` -- in einem
Phase-6-Prosalauf).

Drei Befunde, jeder am Code:

1. **Die Zahl der Abschnitte steht vor dem Lauf fest.**
   `phasen.voraussetzungen` (`phasen.py:373-375`) laesst Phase 6 erst zu, wenn
   `geschichte` gesetzt **und** mindestens eine Szene angelegt ist. Und
   `interview_theater/prompts/formen/prosa.md:29-33` sagt dem Modell
   woertlich: *"Steht schon eine Szenenfolge, ist sie verbindlich ... so viele
   Abschnitte wie geplante Szenen, in derselben Reihenfolge ... Du erfindest
   keine Szene dazu, streichst keine und ordnest keine um."* Eine Liste von
   Budgets je Abschnitt hat also einen Adressaten.
2. **Eine Form liegt je Szene vor, auch in Phase 6.** Entweder bestaetigt
   (`szene.form` -- gesetzt vom Richtungs- bzw. Formabfolge-Weg in Phase 4,
   `szenenfolge.lege_inline_an` / `_uebernimm_formwahl`, genau der Weg, ueber
   den die Dortmunder Abschnitte ihr `chor`/`rap` bekamen) oder als Vorschlag
   (`szene.form_vorschlag`, die vierte Spalte der Szenenzeile). Fehlt beides,
   gilt `workshop.form_vorgabe()` (`dialog`).
   **Das Budget liest diese Form, es setzt sie nicht.** `szene.form` wird vom
   Laengenweg an keiner Stelle geschrieben -- die Regel "die Form bestaetigt
   allein die Gruppe" bleibt unberuehrt. Ein Laengenrahmen ist keine
   Formentscheidung; er sagt nur, wie lang ein Chorstueck ueblicherweise ist.
3. **Der Prompt widerspricht sich heute selbst.**
   `kurzgeschichte.ANWEISUNG:56-60` stellt dem Modell die Abschnittszahl
   ausdruecklich frei ("Du waehlst die Zahl der Abschnitte selbst"), waehrend
   `formen/prosa.md:29` sie fuer verbindlich erklaert -- und **beide** gehen
   in `kurzgeschichte.systemanweisung()`. `kuerzung.notiz_fuer_prosa` arbeitet
   schon heute gegen diesen Widerspruch an, indem es die Zahl im Auftrag
   nennt.

**Daraus die Entscheidung dieses Plans:**

- **Phase 6** (ein Prosalauf ueber die ganze Geschichte): der Code baut aus
  den vorhandenen Szenen -- Nummer und Form in der Reihenfolge der Nummern --
  eine **Budgetliste**. Sie geht als eigener Block in den **Nutzertext** (dort
  ist er je Gruppe verschieden) und ersetzt in der **Systemanweisung** die
  eine feste Zeile `Insgesamt 1.500 bis 3.500 Woerter.` durch die Summe. Der
  Block bindet die Abschnittszahl ausdruecklich -- wie `notiz_fuer_prosa` es
  schon tut. **Nur bei aktivem Profil**; ohne Budget bleibt jedes Zeichen,
  wie es ist.
- **Phase 7** (ein Lauf je Szene, Form bestaetigt): das Budget dieser einen
  Szene geht als eigener Block in den Nutzertext, direkt hinter die Aufgabe
  der Szene und damit in den nie gekuerzten Teil.
- **Nachgezaehlt wird in beiden Phasen ueber denselben Zaehler**
  (`laengen.zaehle_woerter`), in Phase 6 je Abschnitt aus `szene.prosa`, in
  Phase 7 aus `szene.volltext`.

---

## OFFENE FRAGEN AN BIRK

Alle fuenf sind so geplant, dass die Umsetzung **ohne** Antwort nichts
verbaut: jeder Wert steht in `workshop/padua-2026/profil.toml` und ist ohne
Code aenderbar, und jede offene Variante ist spaeter eine Zeile.

1. **Sind die Rahmenwerte der Karte der Normalfall oder schon die
   Instagram-Laenge?** Gemessen (Architekt, 30.09.2026): Herkules-Mass im Repo
   700-1500 Woerter je Szene, Median 1400
   (`interview_theater/prompts/formen/dialog.md`); Dortmund v2 (Phase-6-Prosa,
   06.09. 19:08) 825 / 802 / 603 Woerter. Die Startwerte der Karte (Dialog
   200-450) liegen damit **schon bei etwa einem Viertel** dieses Masses. Der
   Faktor 0,25 obendrauf ergaebe Dialog **50-110 Woerter** je Szene -- rund
   eine Minute Buehnenzeit. Geplant ist: die Rahmen **wie in der Karte**, in
   `[laengen.rahmen]`, jede Zahl als `Vorschlag, ungemessen` markiert, und der
   Faktor wirkt darauf. Wer sie verdoppeln will, aendert eine Zeile TOML.
2. **Soll der Budget-Block in Phase 6 die Abschnittszahl binden?** Ohne
   Bindung hat eine Liste von Budgets je Abschnitt keinen Adressaten (das
   Modell darf die Zahl heute frei waehlen, `ANWEISUNG:56-60`) -- mit Bindung
   folgt der Prompt der Regel, die `formen/prosa.md:29` ohnehin aufstellt, und
   der Selbstwiderspruch verschwindet. Geplant: **binden, aber nur bei
   aktivem Budget.** Dortmund bleibt unberuehrt.
3. **Setzt ein "Kuerzer (25 %)" unter EINER Szene auch den dauerhaften Faktor
   fuer alle kommenden Szenen?** Geplant: **nein** -- den Faktor setzt nur das
   "Kuerzer" unter der **ganzen Geschichte** und eine ausdrueckliche
   Laengenansage der Gruppe. Begruendung: eine Entscheidung ueber eine Szene
   ist keine ueber alle. Die weite Lesart ist spaeter eine Zeile in
   `kuerzung.starte`.
4. **Welchen Rahmen bekommt `monolog`?** Die Karte nennt Chor/Lied 80-200,
   Rap 120-250, Dialog 200-450 -- Monolog nicht. Geplant: **150-350**, als
   `Vorschlag, ungemessen` markiert.
5. **Bleibt der Sprachpass fuer Dortmund aus?** Die deutschen Muster
   existieren im Code und sind getestet, aber `[sprachpass] aktiv = false`
   gilt im Vorgabeprofil. Geplant: **aus.** Anschalten ist eine Zeile TOML und
   kostet je Szene einen Lauf.

---

## ANNAHMEN (nicht am Code dieses Stands pruefbar)

Jede Annahme tragt ein Pruefkommando. **Aufgabe 0 fuehrt sie alle aus und
bricht ab, wenn eine faellt.**

| # | Annahme | Pruefkommando |
|---|---|---|
| A1 | Karte A1 ist gemergt: `interview_theater/sprache.py` existiert mit `code()`, `je_sprache(dict)`, `Texte(modul)`, `VERZEICHNIS`, `DEUTSCH`. | `$PY -c "from interview_theater import sprache; print(sprache.code(), sprache.DEUTSCH, sprache.VERZEICHNIS); sprache.je_sprache({'de': 1}); sprache.Texte('interview_theater.szene')"` |
| A2 | Die englische Prompt-Schicht existiert und traegt `theater-tells`. | `test -f interview_theater/sprachen/en/prompts/theater-tells.md && echo da` |
| A3 | Die englische Texttabelle existiert mit Tabellen je Modul. | `test -f interview_theater/sprachen/en/texte.toml && echo da` |
| A4 | `scripts/pruefe_sprache.py` mit `deutsche_treffer(quelle, text)`. | `$PY -c "from scripts import pruefe_sprache; print(pruefe_sprache.deutsche_treffer('x','hello world'))"` |
| A5 | `kurzgeschichte` liest seine Texte ueber `T` (A1 Aufgabe 16), also auch `ANWEISUNG`. Wenn **nicht**, liest dieser Plan `kurzgeschichte.ANWEISUNG` direkt -- Aufgabe 6 nennt beide Varianten. | `$PY -c "from interview_theater import kurzgeschichte as k; print(hasattr(k,'T'))"` |
| A6 | Die englischen Ausgabeparser aus A1 Aufgabe 23 sind da: `kurzgeschichte._UEBERSCHRIFT_EN`, `kurzgeschichte._ZUSAMMENFASSUNG_EN`, `kuerzung._MUSTER_NUMMER_EN`. | `$PY -c "from interview_theater import kurzgeschichte as k, kuerzung as z; print(bool(k._UEBERSCHRIFT_EN and k._ZUSAMMENFASSUNG_EN and z._MUSTER_NUMMER_EN))"` |
| A7 | Karte P ist gemergt: `workshop/padua-2026/profil.toml` ist **kein** Geruest mehr und `formen.toml` traegt `[[form]]`-Eintraege. | `$PY -c "import os; os.environ['IT_WORKSHOP']='padua-2026'; from interview_theater import workshop; p=workshop.aktiv(); assert not p.geruest(), 'noch Geruest'; print(len(p.formen['form']), 'Formen')"` |
| A8 | Die Formnamen des Padua-Profils, gegen die `[laengen.rahmen]` schluesselt. Die Karte nennt deutsche Namen (dialog, chor, lied, rap); Karte P darf andere waehlen. **Ein Rahmen ohne passende Form ist stumm** (Rueckfall `vorgabe_min/max`) -- Aufgabe 1 baut dafuer einen Profil-Check, der die Luecke **meldet** statt sie zu verschweigen. | `$PY -m scripts.pruefe_profil padua-2026` |
| A9 | Die Eichungszahlen des Architekten (Dortmund v2: 825/802/603 Woerter, ein Gedankenstrich in 2230 Woertern; v1: 794/309/317/293) stammen aus Birks Vault und sind **nicht** im Repo. Sie werden als Fremdmessung zitiert, nicht nachgerechnet. Nachrechenbar im Repo sind allein das Herkules-Mass (`prompts/formen/dialog.md`) und der Replikenmedian (`docs/stilvorlagen/2026-09-06/analyse.md`). | `grep -n "700\|1400\|1500\|12.300\|12300" interview_theater/prompts/formen/dialog.md; grep -n "8 Woert\|median" docs/stilvorlagen/2026-09-06/analyse.md` |
| A10 | Der Simulator erreicht mit `--set 1..3` die Prosa-Phase und schreibt mindestens einen Abschnitt (die letzten Laeufe in `verlauf.jsonl` zeigen `phase_erreicht = 8` der alten Zaehlung und einen `szenen`-Eintrag). Den **Kuerzungsweg** und Phase 7 erreicht er **nicht** -- deshalb Aufgabe 18 (deterministischer Ersatznachweis) und Aufgabe 22 (gezielter Einzellauf). | Aufgabe 21, Schritt 1 (`--ohne-szene`, Trockenlesung des Transkripts) |

---

## Nicht im Umfang (ausdruecklich)

- `interview_theater/dramaturgie/schleife.py` automatisieren. Sie steht im
  "Why" der Karte als Diagnose, nicht als Auftrag, und bleibt der teuerste
  Schalter des Repos gegen eine DB-Kopie.
- Italienische Uebersetzung. Padua faehrt nach Birk E-Entscheidung auf
  **Englisch**; Italienisch ist eine eigene Karte.
- Jede Aenderung an Dortmunder Texten, an
  `interview_theater/prompts/theater-tells.md`, an
  `workshop/dortmund-2026/**` und an
  `docs/prompt-audit/schnappschuss-vor-profilumbau.txt`.
- Streichen vorhandener Funktionen. `sprecher._worte`,
  `len(text.split())`-Zaehlungen, `kuerzung.PROZENT`,
  `szenenfolge._TEXT_BESETZT` und die feste Zeile in `formen/prosa.md`
  bleiben, wo sie sind.
- Eine neue Erkenner-Art. Aufgabe 10 belegt am Prompt, dass
  `festlegung_setzen` (Bereich `stil`, laut `repo.FESTLEGUNG_BEREICHE`
  ausdruecklich "Stil- und **Laengen**vorgaben fuer Texte") den Fall schon
  traegt -- eine neue Art brauchte Korpusfaelle und einen bezahlten
  Korpuslauf mit FP = 0.

---

## Dateien im Ueberblick

**Neu:**

| Datei | Verantwortung |
|---|---|
| `interview_theater/laengen.py` | Wortzaehler, Rahmen je Form, Stufen, Rhythmus-Muster, Budgets, Faktor, Prompt-Bausteine, Journalzeile. Rein: kein Modell, keine Datenbank. |
| `interview_theater/sprachpass.py` | `entkleide`, vier Regex-Zaehler, Grenzwertvergleich, Notiztext, Zitatsammlung und Zitatschutz. |
| `interview_theater/nachpass.py` | Der EINE Ueberarbeitungslauf je Schreibweg -- Phase 7 (eine Szene) und Phase 6 (ganze Geschichte). |
| `scripts/laengen_probe.py` | Deterministischer Ersatznachweis mit Attrappe: Budget -> zu langer Text -> genau ein Nachpass -> Zahlen als Tabelle. Kostet nichts. |
| `docs/padua-r-laengen-2026-09-30/BEFUND.md` | Eichungstabelle, Budget-gegen-Wortzahl, Sprachpass-Zaehler vorher/nachher, Kosten. |
| `tests/test_laengen.py`, `tests/test_laengen_budget.py`, `tests/test_laengen_prompt.py`, `tests/test_sprachpass.py`, `tests/test_nachpass.py`, `tests/test_laengen_aus.py` | je Aufgabe. |

**Geaendert:**

| Datei | Was |
|---|---|
| `interview_theater/workshop.py` | `VORGABE_WERTE` bekommt `[laengen]` und `[sprachpass]`. |
| `scripts/pruefe_profil.py` | prueft die neuen Abschnitte, meldet Rahmen ohne Form. |
| `workshop/padua-2026/profil.toml` | `[laengen]` + `[sprachpass]` mit den Werten der Karte, als Vorschlag markiert. |
| `interview_theater/kurzgeschichte.py` | `ZEILE_GESAMTLAENGE`, `systemanweisung(budgets=None)`, Budget-Block im Nutzertext, `hole_text` + `schreibe` synchron herausgezogen, `art`-Parameter. |
| `interview_theater/szene.py` | Budget-Block in `_bloecke`/`_REIHENFOLGE`, `art`-Parameter in `schreibe`/`starte`/`_lauf`, Nachpass-Aufruf am Ende von `_lauf`. |
| `interview_theater/kuerzung.py` | setzt beim Kuerzen der ganzen Geschichte den Faktor. |
| `interview_theater/db.py` | Spalte `arbeitsstand.laengen_faktor` (additiv). |
| `interview_theater/repo.py` | `laengen_faktor` in `_ARBEITSSTAND_FELDER`. |
| `scripts/prompt_schnappschuss.py` | `kurzgeschichte.systemanweisung()` als eigener Abschnitt. |
| `interview_theater/sprachen/en/prompts/theater-tells.md` | vier englische Negativbeispiele (Satzmuster). **Die deutsche Datei bleibt unberuehrt.** |
| `AGENTS.md`, `workshop/padua-2026/LIESMICH.md`, `simulation/README.md` | Doku. |

---

## Aufgabe 0: Vorbedingungs-Check (STOP-Tor, kostenlos)

Diese Karte setzt auf A1 und P auf. Laeuft sie auf einem Stand ohne die
beiden, entstehen Tests, die gegen nicht existierende Namen laufen -- und das
faellt erst in Aufgabe 6 auf.

**Files:** keine. Nur Kommandos.

- [x] **Schritt 1: Alle Annahmen der Tabelle oben ausfuehren**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
set -e
git log --oneline -1
# A1
$PY -c "from interview_theater import sprache; print('A1', sprache.code(), sprache.DEUTSCH, sprache.VERZEICHNIS); sprache.je_sprache({'de': 1}); sprache.Texte('interview_theater.szene')"
# A2 / A3
test -f interview_theater/sprachen/en/prompts/theater-tells.md && echo "A2 da"
test -f interview_theater/sprachen/en/texte.toml && echo "A3 da"
# A4
$PY -c "from scripts import pruefe_sprache; print('A4', pruefe_sprache.deutsche_treffer('x','hello world'))"
# A5 (darf fehlschlagen -- dann gilt die Variante ohne T, siehe Aufgabe 6)
$PY -c "from interview_theater import kurzgeschichte as k; print('A5', hasattr(k,'T'))"
# A6
$PY -c "from interview_theater import kurzgeschichte as k, kuerzung as z; print('A6', bool(k._UEBERSCHRIFT_EN and k._ZUSAMMENFASSUNG_EN and z._MUSTER_NUMMER_EN))"
# A7
$PY -c "import os; os.environ['IT_WORKSHOP']='padua-2026'; from interview_theater import workshop; p=workshop.aktiv(); assert not p.geruest(), 'padua ist noch Geruest'; print('A7', len(p.formen['form']), 'Formen:', [f['name'] for f in p.formen['form']])"
```

Erwartet: jede Zeile mit `A1`-`A7` erscheint, `A7` nennt die Formnamen des
Padua-Profils.

**Faellt A1, A2, A3, A4, A6 oder A7: STOP.** Nichts umsetzen, den Stand
melden ("Karte R blockiert: A1 bzw. P nicht gemergt, Kommando X liefert Y").
Faellt nur A5, weiter -- Aufgabe 6 hat dafuer eine zweite Variante.

- [x] **Schritt 2: Basislinie bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768). Die Zahl notieren; sie ist der
Massstab fuer jede weitere Aufgabe.

- [x] **Schritt 3: Dortmund laedt (Birk E3)**

Run: `$PY -m scripts.pruefe_profil dortmund-2026`
Erwartet: Exit 0.

- [x] **Schritt 4: Die Formnamen des Padua-Profils in diesen Plan eintragen**

Die Ausgabe von A7 nennt die tatsaechlichen Formnamen. Weichen sie von
`dialog/monolog/chor/lied/rap` ab, werden in **Aufgabe 1** die Schluessel
unter `[laengen.rahmen]` entsprechend benannt -- die Zahlen bleiben
(Chor-artig 80-200, Rap-artig 120-250, Dialog-artig 200-450, Monolog-artig
150-350). Das ist eine Umbenennung, keine Entscheidung.

- [x] **Schritt 5: Kein Commit.** Diese Aufgabe aendert keine Datei.

Run: `git status --porcelain`
Erwartet: leer (bzw. nur die vom Harness angelegten `.cc-*`-Dateien).

---

## Aufgabe 1: Der Profilschalter -- `[laengen]` und `[sprachpass]`

**Files:**
- Modify: `interview_theater/workshop.py` (`VORGABE_WERTE`, hinter dem
  bestehenden letzten Abschnitt)
- Modify: `scripts/pruefe_profil.py` (`pruefe`, neue Pruefungen)
- Modify: `workshop/padua-2026/profil.toml` (neue Abschnitte am Ende)
- Test: `tests/test_laengen.py` (neu, Teil 1)

**Interfaces:**
- Produces: `workshop.VORGABE_WERTE["laengen"]` mit den Schluesseln `aktiv`
  (bool), `kurz_faktor` (float), `nachzaehl_schwelle` (float), `vorgabe_min`
  (int), `vorgabe_max` (int), `rahmen` (dict `formname -> [min, max]`),
  `muster` (Liste von Listen aus Stufennamen); und
  `workshop.VORGABE_WERTE["sprachpass"]` mit `aktiv` (bool),
  `gedankenstriche_je_1000`, `nicht_sondern_je_1000`,
  `adjektiv_dreier_je_1000` (floats), `fazitsatz_je_text` (int).
  Gelesen wird ausschliesslich ueber `workshop.Profil.wert("laengen.aktiv",
  False)` -- **kein** neuer Accessor in `workshop.py`.
- Produces: `scripts.pruefe_profil` meldet: unbekannte Stufennamen, ein
  `muster` mit weniger als zwei verschiedenen Stufen, `kurz_faktor` ausserhalb
  `(0, 1]`, `nachzaehl_schwelle < 1.0`, `vorgabe_min >= vorgabe_max`, einen
  `[laengen.rahmen]`-Schluessel, der keine Form des Profils ist (A8), und eine
  Form ohne eigenen Rahmen (nur als Hinweis, nicht als Fehler).

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen.py`

```python
"""Laengen-Rhythmus je Szene (30.09.2026, Karte R) -- Teil 1: das Profil.

Der Hauptschalter ``laengen.aktiv`` steht im eingebauten Vorgabeprofil auf
``False``, und das ist die Zusage an Dortmund: ohne ``IT_WORKSHOP`` und mit
``IT_WORKSHOP=dortmund-2026`` aendert sich kein Zeichen an einem Prompt.
"""

import pytest

from interview_theater import workshop

STUFEN = ("schlag", "kurz", "mittel", "lang")


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_die_vorgabe_hat_den_schalter_aus():
    """Die Zusage an Dortmund, als Test statt als Absichtserklaerung."""
    assert workshop.VORGABE.wert("laengen.aktiv") is False
    assert workshop.VORGABE.wert("sprachpass.aktiv") is False


def test_dortmund_hat_den_schalter_ebenfalls_aus(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    assert profil.wert("laengen.aktiv") is False
    assert profil.wert("sprachpass.aktiv") is False


def test_die_vorgabewerte_stehen_fest():
    v = workshop.VORGABE
    assert v.wert("laengen.kurz_faktor") == 0.25
    assert v.wert("laengen.nachzaehl_schwelle") == 1.3
    assert v.wert("laengen.vorgabe_min") == 200
    assert v.wert("laengen.vorgabe_max") == 450
    assert v.wert("sprachpass.gedankenstriche_je_1000") == 6.0
    assert v.wert("sprachpass.nicht_sondern_je_1000") == 2.0
    assert v.wert("sprachpass.adjektiv_dreier_je_1000") == 2.0
    assert v.wert("sprachpass.fazitsatz_je_text") == 1


def test_jedes_muster_traegt_mindestens_zwei_verschiedene_stufen():
    """"Nie alle gleich" faengt in der Tabelle an, nicht erst im Ergebnis:
    ein Muster aus einer einzigen Stufe koennte gar nichts anderes als flach
    werden."""
    muster = workshop.VORGABE.wert("laengen.muster")
    assert muster, "keine Muster in der Vorgabe"
    for eintrag in muster:
        assert len(eintrag) >= 2, eintrag
        assert set(eintrag) <= set(STUFEN), eintrag
        assert len(set(eintrag)) >= 2, f"flaches Muster: {eintrag}"


def test_jedes_muster_spannt_von_kurz_bis_lang():
    """Die Spreizung ist eine Zahl, kein Gefuehl: jedes Muster nennt eine
    Stufe mit Gewicht <= 0,2 und eine mit >= 1,0. Sonst kann die numerische
    Mindestspreizung (Aufgabe 3) nicht eingehalten werden."""
    gewicht = {"schlag": 0.0, "kurz": 0.2, "mittel": 0.5, "lang": 1.0}
    for eintrag in workshop.VORGABE.wert("laengen.muster"):
        werte = [gewicht[s] for s in eintrag]
        assert min(werte) <= 0.2, eintrag
        assert max(werte) >= 1.0, eintrag


def test_padua_traegt_die_rahmen_der_karte(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    profil = workshop.aktiv()
    assert profil.wert("laengen.aktiv") is True
    assert profil.wert("sprachpass.aktiv") is True
    rahmen = profil.wert("laengen.rahmen")
    formen = {f["name"] for f in profil.formen["form"]}
    assert rahmen, "Padua ohne Rahmen"
    # Jeder Rahmen gehoert zu einer Form dieses Profils (A8) ...
    assert set(rahmen) <= formen, sorted(set(rahmen) - formen)
    # ... und jede Zahl ist ein Paar min < max.
    for name, paar in rahmen.items():
        assert len(paar) == 2, (name, paar)
        assert 0 < paar[0] < paar[1], (name, paar)
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen.py`
Erwartet: FAIL, `assert None is False` in
`test_die_vorgabe_hat_den_schalter_aus` (der Pfad `laengen.aktiv` fehlt und
`wert()` liefert `None`).

- [x] **Schritt 3: `VORGABE_WERTE` erweitern**

In `interview_theater/workshop.py`, **am Ende** des Dicts `VORGABE_WERTE`
(hinter dem bisher letzten Abschnitt, vor der schliessenden Klammer):

```python
    # Laengen-Rhythmus je Szene (30.09.2026, Karte R). **aktiv = False** ist
    # die Zusage an Dortmund: ohne Variable und mit
    # IT_WORKSHOP=dortmund-2026 aendert sich kein Zeichen an einem Prompt,
    # und keine dieser Zahlen wird gelesen. Wer den Schalter umlegt, aendert
    # das Verhalten seines Profils -- nicht das des Repos.
    "laengen": {
        "aktiv": False,
        # Was "Kuerzer/Instagram" auf alle Budgets legt (Karte: 0,25).
        "kurz_faktor": 0.25,
        # Ab welchem Anteil des Budgets EIN Kuerzungslauf angehaengt wird.
        "nachzaehl_schwelle": 1.3,
        # Rueckfall fuer eine Form, die unter ``rahmen`` nicht steht.
        "vorgabe_min": 200,
        "vorgabe_max": 450,
        # Woerter je Szene, Formname -> [min, max]. Leer heisst: jede Form
        # nimmt vorgabe_min/vorgabe_max. Die Werte gehoeren ins Profil, weil
        # sie von Ort, Altersgruppe und Spieldauer abhaengen.
        "rahmen": {},
        # Die Rhythmus-Muster. Der Code waehlt eines je Gruppe und liest es
        # zyklisch ueber die Szenennummern -- ``kurz-lang-kurz`` heisst also
        # auch bei sieben Szenen kurz, lang, kurz, kurz, lang, kurz, kurz.
        # Jedes Muster traegt mindestens zwei VERSCHIEDENE Stufen: eine
        # Liste aus einer Stufe koennte gar nichts anderes als flach werden.
        "muster": [
            ["kurz", "lang", "kurz"],
            ["lang", "kurz", "schlag"],
            ["kurz", "kurz", "lang"],
            ["mittel", "lang", "schlag"],
        ],
    },
    # Der letzte Sprachpass (30.09.2026, Karte R). Vier mechanisch gezaehlte
    # Muster, Grenzwerte je 1.000 Woerter -- ausser dem Fazitsatz, der
    # positionell gezaehlt wird (nur in den letzten Saetzen) und deshalb je
    # TEXT zaehlt. Die Einheit steht im Schluesselnamen, damit sie niemand
    # raten muss.
    "sprachpass": {
        "aktiv": False,
        "gedankenstriche_je_1000": 6.0,
        "nicht_sondern_je_1000": 2.0,
        "adjektiv_dreier_je_1000": 2.0,
        "fazitsatz_je_text": 1,
    },
```

- [x] **Schritt 4: Padua-Profil fuellen**

An das Ende von `workshop/padua-2026/profil.toml`:

```toml
# --- Laengen-Rhythmus je Szene (30.09.2026, Karte R) ----------------------
#
# Der Code waehlt je Szene ein Wortbudget aus einem Rhythmus-Muster, damit
# nicht alle Szenen gleich lang werden. Alle Zahlen hier sind VORSCHLAEGE
# und UNGEMESSEN -- sie stammen aus der Kartenbeschreibung, nicht aus einer
# Messung an einem fertigen Stueck.
#
# Zum Vergleich, was gemessen ist:
#   * Herkules.exe (prompts/formen/dialog.md): 700-1500 Woerter je Szene,
#     Median 1400, neun Szenen rund 12.300 Woerter.
#   * Dortmund Textbuch v2 (06.09.2026, Phase-6-Prosa): 825 / 802 / 603
#     Woerter -- flach, alle im gleichen Bereich. Genau dagegen ist der
#     Rhythmus gebaut.
# Die Werte unten liegen damit bei etwa einem VIERTEL des Herkules-Masses.
# Ob das der Normalfall ist oder schon die "Instagram"-Laenge, entscheidet
# Birk -- siehe OFFENE FRAGE 1 im Plan. Geaendert wird hier, nicht im Code.
[laengen]
aktiv = true
# "Kuerzer/Instagram": Faktor auf ALLE Budgets. 0,25 auf die Werte unten
# ergibt Dialog 50-110 Woerter je Szene.
kurz_faktor = 0.25
# Ab 130 % des Budgets haengt der Code GENAU EINEN Kuerzungslauf an.
nachzaehl_schwelle = 1.3
# Rueckfall fuer eine Form ohne eigenen Rahmen.
vorgabe_min = 200
vorgabe_max = 450

# Woerter je Szene, Formname -> [min, max]. Die Formnamen muessen zu
# formen.toml passen -- scripts/pruefe_profil.py meldet jeden Rahmen ohne
# Form und jede Form ohne Rahmen.
[laengen.rahmen]
dialog  = [200, 450]   # Vorschlag, ungemessen
monolog = [150, 350]   # Vorschlag, ungemessen -- die Karte nennt Monolog nicht
chor    = [80, 200]    # Vorschlag, ungemessen
lied    = [80, 200]    # Vorschlag, ungemessen
rap     = [120, 250]   # Vorschlag, ungemessen

# --- Der letzte Sprachpass ------------------------------------------------
#
# Vier Muster, mechanisch gezaehlt, ohne Modell. Ueberschreitet eines seinen
# Grenzwert, haengt derselbe EINE Lauf, der auch kuerzt, eine
# Ueberarbeitungs-Notiz an. Grenzwerte je 1.000 Woerter -- ausser dem
# Fazitsatz, der je Text zaehlt.
#
# Anker aus der Messung: Dortmund v2 hatte EINEN Gedankenstrich in 2.230
# Woertern (0,45 je 1.000). 6,0 ist also reichlich Luft und trifft nur die
# Inflation, nicht den einzelnen Strich.
[sprachpass]
aktiv = true
gedankenstriche_je_1000 = 6.0
nicht_sondern_je_1000 = 2.0
adjektiv_dreier_je_1000 = 2.0
fazitsatz_je_text = 1
```

**Wichtig:** Weichen die Formnamen aus Aufgabe 0 Schritt 4 ab, werden die
Schluessel unter `[laengen.rahmen]` umbenannt -- die Zahlen bleiben den
Formarten zugeordnet (chorisch 80-200, rapartig 120-250, dialogisch 200-450,
monologisch 150-350).

- [x] **Schritt 5: `scripts/pruefe_profil.py` erweitern**

In `pruefe(profil)`, hinter den vorhandenen Pruefungen. `Bericht.fehlt(text)`
meldet einen Fehler, `Bericht.merke(text)` einen Hinweis (die vorhandenen
Methoden, `scripts/pruefe_profil.py:76`/`:79`).

```python
    # --- Laengen-Rhythmus (30.09.2026, Karte R) ---------------------------
    # Steht der Schalter aus, wird keine dieser Zahlen gelesen; dann sind
    # auch Fehler darin harmlos und werden nur gemerkt. Steht er an, ist eine
    # kaputte Zahl ein Startfehler -- Fehlerbild am Workshoptag ist die
    # teuerste Waehrung.
    laengen_an = bool(profil.wert("laengen.aktiv", False))
    melde = bericht.fehlt if laengen_an else bericht.merke
    stufen = ("schlag", "kurz", "mittel", "lang")
    gewicht = {"schlag": 0.0, "kurz": 0.2, "mittel": 0.5, "lang": 1.0}

    faktor = profil.wert("laengen.kurz_faktor", 0.25)
    if not isinstance(faktor, (int, float)) or not 0 < float(faktor) <= 1:
        melde(f"laengen.kurz_faktor muss zwischen 0 und 1 liegen, ist {faktor!r}")
    schwelle = profil.wert("laengen.nachzaehl_schwelle", 1.3)
    if not isinstance(schwelle, (int, float)) or float(schwelle) < 1.0:
        melde(
            "laengen.nachzaehl_schwelle muss >= 1.0 sein (1.3 = ab 130 % des "
            f"Budgets), ist {schwelle!r}"
        )
    unten = profil.wert("laengen.vorgabe_min", 0)
    oben = profil.wert("laengen.vorgabe_max", 0)
    if not (isinstance(unten, int) and isinstance(oben, int) and 0 < unten < oben):
        melde(f"laengen.vorgabe_min/max muss 0 < min < max sein, ist {unten!r}/{oben!r}")

    for eintrag in profil.wert("laengen.muster", ()) or ():
        unbekannt = [s for s in eintrag if s not in stufen]
        if unbekannt:
            melde(
                f"laengen.muster {list(eintrag)}: unbekannte Stufe(n) "
                f"{unbekannt} -- erlaubt sind {list(stufen)}"
            )
            continue
        if len(set(eintrag)) < 2:
            melde(f"laengen.muster {list(eintrag)} ist flach -- mindestens "
                  "zwei verschiedene Stufen")
        else:
            werte = [gewicht[s] for s in eintrag]
            if min(werte) > 0.2 or max(werte) < 1.0:
                melde(
                    f"laengen.muster {list(eintrag)} spreizt nicht: es braucht "
                    "eine Stufe 'kurz' oder 'schlag' UND eine Stufe 'lang'"
                )

    formnamen = {f["name"] for f in (profil.formen or {}).get("form", ())}
    rahmen = profil.wert("laengen.rahmen", {}) or {}
    for name, paar in rahmen.items():
        if name not in formnamen:
            melde(
                f"laengen.rahmen: '{name}' ist keine Form dieses Profils "
                f"(formen.toml kennt {sorted(formnamen)}) -- der Rahmen "
                "wuerde nie gelesen"
            )
        if len(paar) != 2 or not (0 < paar[0] < paar[1]):
            melde(f"laengen.rahmen['{name}'] muss [min, max] mit 0 < min < max "
                  f"sein, ist {list(paar)}")
    if laengen_an:
        for name in sorted(formnamen - set(rahmen)):
            bericht.merke(
                f"Form '{name}' hat keinen eigenen Laengenrahmen -- sie nimmt "
                f"laengen.vorgabe_min/max ({unten}-{oben} Woerter)"
            )

    # --- Sprachpass -------------------------------------------------------
    pass_an = bool(profil.wert("sprachpass.aktiv", False))
    melde_pass = bericht.fehlt if pass_an else bericht.merke
    for schluessel in ("gedankenstriche_je_1000", "nicht_sondern_je_1000",
                       "adjektiv_dreier_je_1000", "fazitsatz_je_text"):
        wert = profil.wert(f"sprachpass.{schluessel}")
        if not isinstance(wert, (int, float)) or float(wert) < 0:
            melde_pass(f"sprachpass.{schluessel} muss eine Zahl >= 0 sein, "
                       f"ist {wert!r}")
```

- [x] **Schritt 6: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m scripts.pruefe_profil dortmund-2026`
Erwartet: Exit 0 -- Dortmund hat `[laengen]` nicht in seiner `profil.toml`,
erbt `aktiv = false` und wird daher nur gemerkt, nicht beanstandet.

Run: `$PY -m scripts.pruefe_profil padua-2026`
Erwartet: Exit 0, und in der Ausgabe kein `laengen.`-Fehler.

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/test_workshop.py tests/profile/`
Erwartet: `passed`, kein `failed`.

- [x] **Schritt 7: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/workshop.py scripts/pruefe_profil.py \
        workshop/padua-2026/profil.toml tests/test_laengen.py
git commit -m "Laengen-Rhythmus: Profilschalter [laengen] und [sprachpass], aus in der Vorgabe (R)"
```

---

## Aufgabe 2: `laengen.py` I -- der eine Wortzaehler und der Rahmen je Form

**Files:**
- Create: `interview_theater/laengen.py`
- Test: `tests/test_laengen.py` (anhaengen)

**Interfaces:**
- Consumes: `workshop.aktiv()`, `workshop.Profil.wert`, `workshop.form_vorgabe()`.
- Produces:
  - `laengen.zaehle_woerter(text: str) -> int`
  - `laengen.aktiv(profil=None) -> bool`
  - `laengen.sprachpass_aktiv(profil=None) -> bool`
  - `laengen.rahmen_fuer(form: str | None, profil=None) -> tuple[int, int]`
  - `laengen.form_der_szene(szene) -> str`
  - `laengen.MINDEST_WOERTER = 20`

- [x] **Schritt 1: Den failenden Test schreiben** -- an `tests/test_laengen.py`
anhaengen

```python
# --- Teil 2: der Wortzaehler und der Rahmen je Form -----------------------

from interview_theater import laengen


def test_der_zaehler_zaehlt_woerter_und_keine_satzzeichen():
    """EINE Zaehlung fuer Eichung, Budget, Nachzaehlen und Befund -- gemessen
    wie die Eichung vom 30.09.2026: Markdown weg, dann Tokens ``\\w+('\\w+)?``."""
    assert laengen.zaehle_woerter("Zwei Woerter.") == 2
    assert laengen.zaehle_woerter("Eins, zwei -- drei!") == 3
    assert laengen.zaehle_woerter("**Am Steg**") == 2
    assert laengen.zaehle_woerter("## 1. Am Steg") == 4   # "1" zaehlt mit
    assert laengen.zaehle_woerter("don't stop") == 2
    assert laengen.zaehle_woerter("") == 0
    assert laengen.zaehle_woerter(None) == 0


def test_der_zaehler_zaehlt_auch_regieanweisungen_mit():
    """Anders als ``sprecher._worte``: fuer ein Laengenbudget zaehlt alles,
    was auf dem Blatt steht -- eine Seite Regie ist eine Seite."""
    assert laengen.zaehle_woerter("MIRA: (steht auf) Nein.") == 5


def test_aus_ist_der_vorgabezustand():
    assert laengen.aktiv() is False
    assert laengen.sprachpass_aktiv() is False


def test_padua_ist_an(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.aktiv() is True
    assert laengen.sprachpass_aktiv() is True


def test_der_rahmen_kommt_aus_dem_profil(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.rahmen_fuer("chor") == (80, 200)
    assert laengen.rahmen_fuer("rap") == (120, 250)
    assert laengen.rahmen_fuer("dialog") == (200, 450)


def test_eine_unbekannte_form_nimmt_den_rueckfall(monkeypatch):
    """Ein freier Formwert ("Bewegungsszene") darf kein Absturz sein --
    ``szene.form`` ist ein freies Textfeld."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.rahmen_fuer("Bewegungsszene") == (200, 450)
    assert laengen.rahmen_fuer(None) == (200, 450)
    assert laengen.rahmen_fuer("  CHOR  ") == (80, 200)   # getrimmt, kleingeschrieben


def test_ein_kaputter_rahmen_faellt_zurueck_statt_zu_werfen(monkeypatch):
    """Die Leser sind nachsichtig, ``scripts/pruefe_profil.py`` ist streng:
    ein Tippfehler in der TOML soll den Start aufhalten, nicht einen Lauf
    mitten im Workshop."""
    monkeypatch.setattr(laengen, "_werte", lambda profil=None: {
        "rahmen": {"chor": [200]}, "vorgabe_min": 200, "vorgabe_max": 450,
    })
    assert laengen.rahmen_fuer("chor") == (200, 450)


def test_die_form_einer_szene_bestaetigt_schlaegt_vorschlag():
    """In Phase 6 ist ``form`` oft leer und ``form_vorschlag`` gesetzt. Das
    Budget LIEST die Form, es SETZT sie nie -- die Regel "die Form bestaetigt
    allein die Gruppe" bleibt unberuehrt."""
    assert laengen.form_der_szene({"form": "chor", "form_vorschlag": "rap"}) == "chor"
    assert laengen.form_der_szene({"form": "", "form_vorschlag": "rap"}) == "rap"
    assert laengen.form_der_szene({"form": None, "form_vorschlag": None}) == \
        workshop.form_vorgabe()
    assert laengen.form_der_szene({}) == workshop.form_vorgabe()
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen.py`
Erwartet: FAIL, `ModuleNotFoundError: No module named 'interview_theater.laengen'`.

- [x] **Schritt 3: `interview_theater/laengen.py` anlegen**

```python
"""Laengen-Rhythmus je Szene (30.09.2026, Karte R).

**Warum es das gibt.** Am 06.09.2026 hat Birk den Gruppentext vor dem
Versand an die Auftraggeberin von Hand nachbearbeitet, und zwei der
Eingriffe sind Maschinenarbeit: die Gruppe hatte "Instagram-Kuerze"
beschlossen (etwa ein Viertel der vorgesehenen Laenge), und alle Abschnitte
waren gleich lang. Gemessen am Textbuch v2 dieses Tages: 825, 802, 603
Woerter -- drei Abschnitte, praktisch eine Laenge. Das Modell glaettet auf
Mittelmass, weil der Prompt eine Gesamtlaenge nennt und sonst nichts
(``kurzgeschichte.ANWEISUNG``: "Insgesamt 1.500 bis 3.500 Woerter").

**Was hier passiert.** Der Code -- nicht das Modell -- waehlt je Szene ein
Wortbudget. Er tut es aus einem **Rhythmus-Muster** (kurz-lang-kurz,
lang-kurz-Schlag, ...), das er je Gruppe wuerfelt und zyklisch ueber die
Szenennummern liest. Damit ist "nie alle gleich" keine Bitte an ein Modell,
sondern eine Eigenschaft der Zahlen.

**Was hier NICHT passiert.** Kein Modellaufruf, keine Datenbank, keine
Entscheidung ueber die **Form** einer Szene. Dieses Modul liest die Form und
leitet daraus eine Laenge ab; gesetzt wird ``szene.form`` allein durch einen
Knopfdruck der Gruppe, wie bisher.

**Alles Konfigurierbare liegt im Profil** (``[laengen]`` in
``workshop/<name>/profil.toml``), und der Hauptschalter ``aktiv`` steht im
eingebauten Vorgabeprofil auf ``False``: ohne ``IT_WORKSHOP`` und mit
``IT_WORKSHOP=dortmund-2026`` wird hier nichts gelesen und kein Prompt
geaendert.

**Die Leser sind nachsichtig, der Profil-Pruefer ist streng.** Ein kaputter
Wert in der TOML faellt hier auf die Vorgabe zurueck und schreibt eine
Logzeile; beanstandet wird er in ``scripts/pruefe_profil.py``, das in
``scripts/betrieb-start.sh`` **vor** dem Bot laeuft. Ein Absturz mitten im
Workshop wegen eines Tippfehlers waere der teurere Fehler.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Mapping, Sequence

from interview_theater import workshop

log = logging.getLogger(__name__)

#: Markdown-Zeichen, die keine Woerter sind. Sie fallen weg, bevor gezaehlt
#: wird -- ein Modell setzt Ueberschriften und Betonungen auch dann, wenn der
#: Prompt es nicht verlangt.
_MARKDOWN = re.compile(r"[*_`#>\[\]]")

#: Ein Wort: Wortzeichen, optional mit einem Apostroph-Anhang ("don't").
#: Genau die Tokenisierung der Eichung vom 30.09.2026.
_WORT = re.compile(r"\w+(?:['’]\w+)?", re.UNICODE)

#: Unter so viele Woerter geht kein Budget. ``kurz_faktor`` = 0,25 auf den
#: kleinsten Rahmen (Chor 80) ergaebe 20 -- weniger waere keine Szene mehr.
MINDEST_WOERTER = 20

#: Auf so viel wird jedes Budget gerundet. Eine Zahl wie "247 Woerter" gibt
#: eine Genauigkeit vor, die es nicht gibt.
RUNDUNG = 10

#: Die Stufen des Rhythmus und ihr Gewicht im Rahmen einer Form: 0,0 ist das
#: Minimum, 1,0 das Maximum. "schlag" ist die ganz kurze Szene, die einen
#: Rhythmus erst hoerbar macht.
STUFEN: dict[str, float] = {
    "schlag": 0.0,
    "kurz": 0.2,
    "mittel": 0.5,
    "lang": 1.0,
}


def zaehle_woerter(text: str | None) -> int:
    """Wie viele Woerter ein Text hat -- **die eine Zaehlung** fuer Eichung,
    Budget, Nachzaehlen und Befund.

    Gemessen wie die Eichung vom 30.09.2026: Markdown-Zeichen weg, dann
    Tokens ``\\w+('\\w+)?``. Bewusst **nicht** ``len(text.split())`` (dort
    zaehlen Satzzeichen als Wortteil mit) und bewusst **nicht**
    ``sprecher._worte`` (das entfernt Regieanweisungen, weil es Sprechanteile
    zaehlt -- fuer ein Laengenbudget zaehlt aber alles, was auf dem Blatt
    steht). Die bestehenden Zaehlungen bleiben, wo sie sind; sie messen
    etwas anderes."""
    return len(_WORT.findall(_MARKDOWN.sub(" ", text or "")))


def _werte(profil: workshop.Profil | None = None) -> Mapping[str, Any]:
    """Der Abschnitt ``[laengen]`` des aktiven Profils, oder ein leeres Dict.

    Bei **jedem** Aufruf frisch geholt (``workshop.aktiv()``), nicht einmal
    beim Import: derselbe Grund wie beim Modul-``__getattr__`` in
    ``phasen.py`` -- ein Prozess koennte spaeter mehr als ein Profil sehen."""
    p = profil or workshop.aktiv()
    wert = p.wert("laengen", {})
    return wert if isinstance(wert, Mapping) else {}


def _zahl(quelle: Mapping[str, Any], name: str, vorgabe: float) -> float:
    """Eine Zahl aus dem Profil, nachsichtig: was keine ist, wird die
    Vorgabe, und der Fall steht im Log."""
    wert = quelle.get(name, vorgabe)
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        log.warning("laengen.%s ist keine Zahl (%r) -- nehme %r", name, wert, vorgabe)
        return vorgabe
    return float(wert)


def aktiv(profil: workshop.Profil | None = None) -> bool:
    """Waehlt dieses Profil die Budgets? Vorgabe: nein."""
    return bool(_werte(profil).get("aktiv", False))


def sprachpass_aktiv(profil: workshop.Profil | None = None) -> bool:
    """Laeuft der letzte Sprachpass? Vorgabe: nein.

    Steht hier und nicht in ``sprachpass.py``, damit es **einen** Ort fuer
    beide Schalter gibt: wer die Konfiguration sucht, sucht sie einmal."""
    p = profil or workshop.aktiv()
    wert = p.wert("sprachpass", {})
    return bool(wert.get("aktiv", False)) if isinstance(wert, Mapping) else False


def kurz_faktor(profil: workshop.Profil | None = None) -> float:
    """Was "Kuerzer/Instagram" auf alle Budgets legt. Vorgabe 0,25."""
    faktor = _zahl(_werte(profil), "kurz_faktor", 0.25)
    return faktor if 0 < faktor <= 1 else 0.25


def nachzaehl_schwelle(profil: workshop.Profil | None = None) -> float:
    """Ab welchem Anteil des Budgets EIN Kuerzungslauf angehaengt wird.
    Vorgabe 1,3 -- also ab 130 %."""
    schwelle = _zahl(_werte(profil), "nachzaehl_schwelle", 1.3)
    return schwelle if schwelle >= 1.0 else 1.3


def rahmen_fuer(form: str | None,
                profil: workshop.Profil | None = None) -> tuple[int, int]:
    """Der Wortrahmen ``(min, max)`` dieser Form.

    Die Form wird getrimmt und kleingeschrieben verglichen -- ``szene.form``
    ist ein freies Textfeld, und "CHOR" ist dieselbe Form wie "chor". Eine
    Form, die im Profil keinen Rahmen hat (auch eine frei erfundene
    "Bewegungsszene"), bekommt ``vorgabe_min``/``vorgabe_max``: ein
    unbekannter Formname darf kein Absturz und keine fehlende Laenge sein."""
    werte = _werte(profil)
    unten = int(_zahl(werte, "vorgabe_min", 200))
    oben = int(_zahl(werte, "vorgabe_max", 450))
    if not 0 < unten < oben:
        unten, oben = 200, 450
    rahmen = werte.get("rahmen") or {}
    schluessel = (form or "").strip().lower()
    paar = rahmen.get(schluessel) if isinstance(rahmen, Mapping) else None
    if paar is None:
        return unten, oben
    try:
        a, b = int(paar[0]), int(paar[1])
    except (TypeError, ValueError, IndexError):
        log.warning("laengen.rahmen[%r] ist kein [min, max] (%r)", schluessel, paar)
        return unten, oben
    if not 0 < a < b:
        log.warning("laengen.rahmen[%r] ist kein 0 < min < max (%r)", schluessel, paar)
        return unten, oben
    return a, b


def form_der_szene(szene: Any) -> str:
    """Die Form, an der die Laenge dieser Szene haengt: **bestaetigt vor
    vorgeschlagen vor Vorgabe**.

    In Phase 6 ist ``form`` oft leer, weil die Gruppe sie erst im Feinschliff
    bestaetigt -- ``form_vorschlag`` steht dort aber schon (die vierte Spalte
    der Szenenzeile). Das Budget **liest** hier, es **schreibt** nichts: eine
    Laenge ist keine Formentscheidung, und ``szene.form`` bleibt
    unberuehrt."""
    def feld(name: str) -> str:
        try:
            return (szene[name] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""

    return feld("form") or feld("form_vorschlag") or workshop.form_vorgabe()
```

- [x] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

- [x] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/laengen.py tests/test_laengen.py
git commit -m "laengen.py: der eine Wortzaehler und der Rahmen je Form (R)"
```

---

## Aufgabe 3: `laengen.py` II -- der Rhythmus-Wuerfel

**Files:**
- Modify: `interview_theater/laengen.py`
- Test: `tests/test_laengen_budget.py` (neu)

**Interfaces:**
- Produces:
  - `laengen.SPREIZUNG_MIN = 1.5`
  - `laengen.muster_fuer(seed: int, profil=None) -> tuple[str, ...]`
  - `laengen.stufe_fuer(nummer: int | None, muster: Sequence[str]) -> str`
  - `laengen.stufen(nummern: Sequence[int | None], seed: int, profil=None) -> list[str]`
  - `laengen.ist_flach(stufen: Sequence[str]) -> bool`
  - `laengen.spreizung(werte: Sequence[int]) -> float`

**Die Begriffe, mit Zahl:**

- **Seed** ist die `chat_id` der Gruppe. Kein gespeicherter Wert, kein
  `random`-Aufruf: derselbe Chat bekommt immer dasselbe Muster, ohne dass
  irgendwo etwas stehen muss, das verlorengehen kann. Dass er reproduzierbar
  ist, ist deshalb keine Zusage an eine Tabelle, sondern eine Eigenschaft der
  Funktion -- und die Journalzeile (Aufgabe 5) macht ihn fuer Menschen
  sichtbar.
- **Zyklisch statt ueber die Gesamtzahl**: die Stufe einer Szene haengt an
  `(nummer - 1) % len(muster)` und **nicht** an der Zahl der Szenen. Sonst
  verschoebe eine nachtraeglich eingefuegte Szene 6 das Budget von Szene 1,
  und ein spaeteres Nachzaehlen rechnete gegen eine andere Zahl als der Lauf.
- **Flach** heisst: alle Szenen bekommen dieselbe Stufe.
- **Mindestspreizung** `SPREIZUNG_MIN = 1.5`: das groesste Budget einer Form
  geteilt durch das kleinste derselben Form ist mindestens 1,5. Gerechnet je
  Form, weil die Form die Laenge dominiert -- eine lange Chorszene (200) ist
  legitim kuerzer als eine kurze Dialogszene (250), und eine Spreizung ueber
  verschiedene Formen hinweg waere keine Aussage ueber den Rhythmus.

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_budget.py`

```python
"""Der Rhythmus-Wuerfel und die Budgets (30.09.2026, Karte R).

Reine Funktionen: kein Modell, keine Datenbank, kein Netz. Gemessen wird,
dass dasselbe Seed dasselbe Muster liefert, dass kein Muster flach wird und
dass die Uebersteuerung greift.
"""

import pytest

from interview_theater import laengen, workshop


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    """Alle Tests hier laufen unter dem Padua-Profil -- ohne aktiven Schalter
    gaebe es nichts zu wuerfeln."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Das Muster -----------------------------------------------------------


def test_dasselbe_seed_liefert_dasselbe_muster():
    """Reproduzierbarkeit ohne gespeicherten Zustand: der Seed IST die
    chat_id, es gibt keinen ``random``-Aufruf."""
    assert laengen.muster_fuer(4711) == laengen.muster_fuer(4711)


def test_verschiedene_seeds_liefern_verschiedene_muster():
    """Vier Muster in der Vorgabe -- ueber vier aufeinanderfolgende Seeds
    muessen mindestens zwei verschiedene dabei sein, sonst wuerfelt es nicht."""
    gesehen = {laengen.muster_fuer(s) for s in range(4)}
    assert len(gesehen) >= 2, gesehen


def test_eine_negative_chat_id_ist_ein_gueltiges_seed():
    """Telegram-Gruppen haben negative ids. Ein Absturz oder ein
    Index-Fehler hier waere ein Ausfall fuer jede echte Gruppe."""
    muster = laengen.muster_fuer(-1001234567890)
    assert muster in tuple(workshop.aktiv().wert("laengen.muster"))


def test_das_muster_wird_zyklisch_gelesen():
    """Die Stufe haengt an der Nummer, nicht an der Gesamtzahl: eine
    nachtraeglich eingefuegte Szene 6 darf das Budget von Szene 1 nicht
    verschieben."""
    muster = ("kurz", "lang", "schlag")
    assert [laengen.stufe_fuer(n, muster) for n in range(1, 8)] == [
        "kurz", "lang", "schlag", "kurz", "lang", "schlag", "kurz",
    ]


def test_eine_fehlende_nummer_gilt_als_erste_szene():
    """``szene.nummer`` darf NULL sein. Dann ist die erste Stufe die
    richtige Vermutung -- eine Ausnahme waere ein Lauf ohne Budget."""
    assert laengen.stufe_fuer(None, ("kurz", "lang")) == "kurz"
    assert laengen.stufe_fuer(0, ("kurz", "lang")) == "kurz"


# --- Flach und Spreizung --------------------------------------------------


def test_flach_heisst_alle_gleich():
    assert laengen.ist_flach(["kurz", "kurz", "kurz"]) is True
    assert laengen.ist_flach(["kurz"]) is True
    assert laengen.ist_flach([]) is True
    assert laengen.ist_flach(["kurz", "lang"]) is False


def test_kein_muster_der_vorgabe_ist_flach():
    """Der Kern der Zusage "nie alle gleich": schon die Tabelle kann es
    nicht."""
    for muster in workshop.aktiv().wert("laengen.muster"):
        stufen = [laengen.stufe_fuer(n, muster) for n in range(1, len(muster) + 1)]
        assert laengen.ist_flach(stufen) is False, muster


def test_die_spreizung_ist_eine_zahl():
    assert laengen.spreizung([100, 200]) == 2.0
    assert laengen.spreizung([200, 200]) == 1.0
    assert laengen.spreizung([]) == 1.0
    assert laengen.spreizung([0, 200]) == 1.0   # keine Division durch Null


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_jedes_muster_spreizt_in_jeder_form_ueber_die_mindestgrenze(form):
    """Die Mindestspreizung ist gegen JEDEN Rahmen des Profils geprueft, nicht
    nur gegen den bequemsten -- ein schmaler Rahmen (Chor 80-200) ist der
    harte Fall."""
    for muster in workshop.aktiv().wert("laengen.muster"):
        werte = laengen.budgets([form] * len(muster),
                                nummern=list(range(1, len(muster) + 1)), seed=0)
        # ``budgets`` waehlt das Muster selbst; erzwungen wird hier nur, dass
        # jedes Muster der Tabelle die Grenze haelt.
        assert werte, muster
    for muster in workshop.aktiv().wert("laengen.muster"):
        unten, oben = laengen.rahmen_fuer(form)
        roh = [laengen._aus_stufe(s, unten, oben, 1.0) for s in muster]
        assert laengen.spreizung(roh) >= laengen.SPREIZUNG_MIN, (form, muster, roh)
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_budget.py`
Erwartet: FAIL, `AttributeError: module 'interview_theater.laengen' has no attribute 'muster_fuer'`.

- [x] **Schritt 3: An `interview_theater/laengen.py` anhaengen**

```python
#: Die Mindestspreizung innerhalb einer Form: das groesste Budget geteilt
#: durch das kleinste. Je Form gerechnet, weil die Form die Laenge dominiert
#: -- eine lange Chorszene (200) darf kuerzer sein als eine kurze
#: Dialogszene (250), ohne dass der Rhythmus verlorengegangen waere.
SPREIZUNG_MIN = 1.5

#: Das Muster, das gilt, wenn das Profil keines nennt. Gleichlautend mit dem
#: ersten Eintrag der Vorgabe, damit ein Profil ohne ``muster`` nicht flach
#: wird.
MUSTER_RUECKFALL: tuple[str, ...] = ("kurz", "lang", "kurz")


def muster_liste(profil: workshop.Profil | None = None) -> tuple[tuple[str, ...], ...]:
    """Die brauchbaren Muster des Profils.

    Nachsichtig wie ``rahmen_fuer``: ein Eintrag mit einer unbekannten Stufe
    oder mit weniger als zwei verschiedenen Stufen fliegt hier heraus statt
    einen Lauf mitzunehmen -- ``scripts/pruefe_profil.py`` hat ihn vorher
    beanstandet. Bleibt nichts uebrig, gilt ``MUSTER_RUECKFALL``: ein Profil
    ohne brauchbares Muster soll kurze und lange Szenen bekommen und nicht
    lauter mittlere."""
    roh = _werte(profil).get("muster") or ()
    gut: list[tuple[str, ...]] = []
    for eintrag in roh:
        try:
            stufen = tuple(str(s).strip().lower() for s in eintrag)
        except TypeError:
            log.warning("laengen.muster: %r ist keine Liste", eintrag)
            continue
        if len(stufen) < 2 or any(s not in STUFEN for s in stufen):
            log.warning("laengen.muster: %r unbrauchbar -- uebersprungen", eintrag)
            continue
        if len(set(stufen)) < 2:
            log.warning("laengen.muster: %r ist flach -- uebersprungen", eintrag)
            continue
        gut.append(stufen)
    return tuple(gut) or (MUSTER_RUECKFALL,)


def muster_fuer(seed: int,
                profil: workshop.Profil | None = None) -> tuple[str, ...]:
    """Das Rhythmus-Muster dieser Gruppe.

    ``seed`` ist die ``chat_id``. Kein ``random``, kein gespeicherter Wert:
    derselbe Chat bekommt immer dasselbe Muster, und niemand muss es
    aufbewahren. Telegram-Gruppen haben **negative** ids -- ``abs()`` steht
    hier, damit der Index unabhaengig von der Vorzeichen-Konvention von ``%``
    lesbar bleibt."""
    liste = muster_liste(profil)
    return liste[abs(int(seed)) % len(liste)]


def stufe_fuer(nummer: int | None, muster: Sequence[str]) -> str:
    """Die Stufe der Szene ``nummer`` in diesem Muster -- **zyklisch**.

    Zyklisch und nicht ueber die Gesamtzahl verteilt: sonst verschoebe eine
    nachtraeglich eingefuegte Szene 6 das Budget von Szene 1, und das
    Nachzaehlen rechnete gegen eine andere Zahl als der Lauf. ``nummer``
    ``None`` oder 0 gilt als erste Szene -- ``szene.nummer`` darf NULL sein,
    und eine Ausnahme waere ein Lauf ohne Budget."""
    if not muster:
        muster = MUSTER_RUECKFALL
    n = int(nummer or 1)
    if n < 1:
        n = 1
    return muster[(n - 1) % len(muster)]


def stufen(nummern: Sequence[int | None], seed: int,
           profil: workshop.Profil | None = None) -> list[str]:
    """Die Stufen einer ganzen Szenenfolge, in deren Reihenfolge."""
    muster = muster_fuer(seed, profil)
    return [stufe_fuer(n, muster) for n in nummern]


def ist_flach(werte: Sequence[str]) -> bool:
    """Bekommen alle Szenen dieselbe Stufe?

    Eine einzelne Szene ist immer flach -- ein Rhythmus braucht zwei. Das ist
    keine Beanstandung, sondern die Wahrheit: bei einer Szene gibt es keinen
    Rhythmus, und der Test dazu verlangt ihn nicht."""
    return len(set(werte)) <= 1


def spreizung(werte: Sequence[int]) -> float:
    """Groesstes durch kleinstes Budget -- 1,0, wenn es nichts zu vergleichen
    gibt oder ein Wert 0 ist (keine Division durch Null)."""
    zahlen = [int(w) for w in werte if int(w) > 0]
    if len(zahlen) < 2:
        return 1.0
    return max(zahlen) / min(zahlen)
```

- [x] **Schritt 4: Tests laufen lassen**

Die Tests brauchen `laengen.budgets` und `laengen._aus_stufe` aus Aufgabe 4 --
deshalb laufen hier zunaechst nur die Muster- und Spreizungstests.

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_budget.py -k "muster or flach or spreizung_ist"`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_budget.py`
Erwartet: FAIL nur in `test_jedes_muster_spreizt_...` mit
`AttributeError: ... has no attribute 'budgets'`. **Das ist gewollt** -- Aufgabe 4
macht es gruen. Wer die Aufgabe getrennt abschliessen will, markiert diesen
einen Test bis dahin mit `@pytest.mark.xfail(reason="Aufgabe 4")` und nimmt
die Markierung dort wieder heraus.

- [x] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, `passed` >= Basislinie (2768) + die in dieser Aufgabe hinzugekommenen Tests; der `xfail` aus Schritt 4 erscheint als `xfailed`, nicht als `failed`.

```bash
git add interview_theater/laengen.py tests/test_laengen_budget.py
git commit -m "laengen.py: Rhythmus-Muster je Gruppe, zyklisch gelesen, nie flach (R)"
```

---

## Aufgabe 4: `laengen.py` III -- Budget, Faktor, Rundung

**Files:**
- Modify: `interview_theater/laengen.py`
- Test: `tests/test_laengen_budget.py` (anhaengen; `xfail` aus Aufgabe 3
  entfernen)

**Interfaces:**
- Consumes: `rahmen_fuer`, `muster_fuer`, `stufe_fuer`, `STUFEN`,
  `MINDEST_WOERTER`, `RUNDUNG`, `kurz_faktor`.
- Produces:
  - `laengen._aus_stufe(stufe: str, unten: int, oben: int, faktor: float) -> int`
  - `laengen.budget_fuer(nummer, form, seed, faktor=1.0, profil=None) -> int`
  - `laengen.budgets(formen: Sequence[str | None], nummern: Sequence[int | None], seed: int, faktor=1.0, profil=None) -> list[int]`
  - `laengen.zu_lang(woerter: int, budget: int, profil=None) -> bool`

- [x] **Schritt 1: Den failenden Test schreiben** -- an
`tests/test_laengen_budget.py` anhaengen

```python
# --- Die Budgets ----------------------------------------------------------


def test_das_budget_liegt_im_rahmen_der_form():
    for nummer in range(1, 7):
        wert = laengen.budget_fuer(nummer, "chor", seed=1)
        assert 80 <= wert <= 200, (nummer, wert)


def test_das_budget_ist_auf_zehn_gerundet():
    """"247 Woerter" gibt eine Genauigkeit vor, die es nicht gibt."""
    for nummer in range(1, 7):
        for form in ("dialog", "chor", "rap"):
            assert laengen.budget_fuer(nummer, form, seed=3) % 10 == 0


def test_dasselbe_seed_liefert_dasselbe_budget():
    a = laengen.budgets(["dialog"] * 5, nummern=[1, 2, 3, 4, 5], seed=99)
    b = laengen.budgets(["dialog"] * 5, nummern=[1, 2, 3, 4, 5], seed=99)
    assert a == b


def test_budgets_und_budget_fuer_sagen_dasselbe():
    """Zwei Wege zu einer Zahl muessen dieselbe Zahl liefern -- sonst plant
    der Prompt gegen ein anderes Budget als der Nachzaehler prueft."""
    formen = ["dialog", "chor", "rap", "dialog"]
    nummern = [1, 2, 3, 4]
    liste = laengen.budgets(formen, nummern=nummern, seed=7)
    einzeln = [laengen.budget_fuer(n, f, seed=7)
               for n, f in zip(nummern, formen)]
    assert liste == einzeln


def test_eine_folge_aus_einer_form_ist_nicht_flach():
    """Der eigentliche Zweck: vier Dialogszenen duerfen nicht vier gleiche
    Zahlen sein."""
    werte = laengen.budgets(["dialog"] * 4, nummern=[1, 2, 3, 4], seed=5)
    assert len(set(werte)) >= 2, werte
    assert laengen.spreizung(werte) >= laengen.SPREIZUNG_MIN, werte


def test_der_faktor_verkuerzt_alle_budgets():
    """"Instagram": ein Viertel, auf jedes Budget."""
    voll = laengen.budgets(["dialog"] * 3, nummern=[1, 2, 3], seed=2)
    kurz = laengen.budgets(["dialog"] * 3, nummern=[1, 2, 3], seed=2, faktor=0.25)
    assert len(voll) == len(kurz) == 3
    for a, b in zip(voll, kurz):
        assert b < a
        # Gerundet auf 10, also nicht exakt ein Viertel -- aber nah dran.
        assert abs(b - a * 0.25) <= laengen.RUNDUNG


def test_der_faktor_unterschreitet_nie_die_mindestlaenge():
    """0,25 auf den kleinsten Rahmen (Chor 80) ergaebe 20; ein kleinerer
    Faktor duerfte nicht auf 0 fallen -- eine Szene mit null Woertern ist
    keine."""
    werte = laengen.budgets(["chor"] * 3, nummern=[1, 2, 3], seed=1, faktor=0.05)
    assert min(werte) >= laengen.MINDEST_WOERTER, werte


def test_ohne_szenen_gibt_es_keine_budgets():
    assert laengen.budgets([], nummern=[], seed=1) == []


def test_zu_lang_greift_erst_ab_der_schwelle():
    """130 % des Budgets, an EINER Stelle konfiguriert."""
    assert laengen.zu_lang(100, 100) is False
    assert laengen.zu_lang(129, 100) is False
    assert laengen.zu_lang(130, 100) is True
    assert laengen.zu_lang(400, 100) is True
    # Kein Budget heisst keine Beanstandung.
    assert laengen.zu_lang(400, 0) is False
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_budget.py -k budget`
Erwartet: FAIL, `AttributeError: ... has no attribute 'budget_fuer'`.

- [x] **Schritt 3: An `interview_theater/laengen.py` anhaengen**

```python
def _aus_stufe(stufe: str, unten: int, oben: int, faktor: float) -> int:
    """Eine Stufe im Rahmen ``(unten, oben)`` zu einer Wortzahl.

    Linear zwischen Minimum (Gewicht 0,0) und Maximum (1,0), dann mit
    ``faktor`` skaliert, auf ``RUNDUNG`` gerundet und nie unter
    ``MINDEST_WOERTER``. Die Rundung steht **nach** dem Faktor: sonst waere
    "ein Viertel von einer runden Zahl" wieder keine runde Zahl."""
    gewicht = STUFEN.get(stufe, STUFEN["mittel"])
    roh = (unten + gewicht * (oben - unten)) * float(faktor)
    gerundet = int(round(roh / RUNDUNG) * RUNDUNG)
    return max(gerundet, MINDEST_WOERTER)


def budget_fuer(nummer: int | None, form: str | None, seed: int,
                faktor: float = 1.0,
                profil: workshop.Profil | None = None) -> int:
    """Das Wortbudget EINER Szene.

    ``form`` ist die Form, die ``form_der_szene`` geliefert hat; ``seed`` die
    ``chat_id``; ``faktor`` die Uebersteuerung (1,0 = keine). Deckungsgleich
    mit dem entsprechenden Eintrag aus ``budgets`` -- ein Test haelt das fest,
    denn zwei Wege zu einer Zahl, die auseinanderlaufen, planen gegen ein
    anderes Budget als sie pruefen."""
    unten, oben = rahmen_fuer(form, profil)
    return _aus_stufe(stufe_fuer(nummer, muster_fuer(seed, profil)),
                      unten, oben, faktor)


def budgets(formen: Sequence[str | None], nummern: Sequence[int | None],
            seed: int, faktor: float = 1.0,
            profil: workshop.Profil | None = None) -> list[int]:
    """Die Budgets einer ganzen Szenenfolge, in der Reihenfolge von
    ``formen``/``nummern``.

    Die beiden Listen gehoeren paarweise zusammen; ist ``nummern`` kuerzer,
    wird ab dort durchgezaehlt (eine Szene ohne Nummer ist die naechste)."""
    ergebnis: list[int] = []
    for i, form in enumerate(formen):
        nummer = nummern[i] if i < len(nummern) else i + 1
        ergebnis.append(budget_fuer(nummer, form, seed, faktor, profil))
    return ergebnis


def zu_lang(woerter: int, budget: int,
            profil: workshop.Profil | None = None) -> bool:
    """Ist dieser Text ueber der Nachzaehl-Schwelle?

    Kein Budget (0 oder negativ) heisst **keine** Beanstandung: wo nichts
    geplant war, ist nichts ueberschritten."""
    if int(budget) <= 0:
        return False
    return int(woerter) >= int(budget) * nachzaehl_schwelle(profil)
```

- [x] **Schritt 4: Das `xfail` aus Aufgabe 3 entfernen**

In `tests/test_laengen_budget.py` die Zeile
`@pytest.mark.xfail(reason="Aufgabe 4")` ueber
`test_jedes_muster_spreizt_in_jeder_form_ueber_die_mindestgrenze` loeschen.

- [x] **Schritt 5: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_budget.py -v`
Erwartet: `21 passed`, kein `xfail`, kein `xpass`.

Sollte `test_eine_folge_aus_einer_form_ist_nicht_flach` oder
`test_jedes_muster_spreizt_...` fehlschlagen, ist **die Muster-Tabelle** das
Problem und nicht die Rechnung: die Grenze `SPREIZUNG_MIN` wird nicht gesenkt,
sondern das beanstandete Muster in `workshop.VORGABE_WERTE["laengen"]["muster"]`
so geaendert, dass es eine Stufe `kurz`/`schlag` **und** eine Stufe `lang`
traegt. Kontrollrechnung fuer Chor (80-200), der schmalste Rahmen:
`schlag = 80`, `kurz = 80 + 0.2*120 = 104 -> 100`, `mittel = 140`,
`lang = 200`; `200/100 = 2.0 >= 1.5`. Fuer Dialog (200-450): `schlag = 200`,
`kurz = 250`, `mittel = 320`, `lang = 450`; `450/250 = 1.8 >= 1.5`.

- [x] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/laengen.py tests/test_laengen_budget.py
git commit -m "laengen.py: Budget je Szene, Faktor, Rundung, Nachzaehl-Schwelle (R)"
```

---

## Aufgabe 5: `laengen.py` IV -- die Prompt-Bausteine und die Journalzeile

**Files:**
- Modify: `interview_theater/laengen.py`
- Test: `tests/test_laengen_prompt.py` (neu)

**Interfaces:**
- Produces:
  - `laengen.BLOCK_KOPF_SZENE: str`, `laengen.BLOCK_KOPF_PROSA: str`,
    `laengen.ZEILE_ABSCHNITT: str`, `laengen.ZEILE_GESAMT: str`,
    `laengen.SATZ_BINDUNG: str`, `laengen.SATZ_VORRANG: str`
  - `laengen.block_szene(budget: int) -> str`
  - `laengen.block_prosa(eintraege: Sequence[tuple[int, str, int]]) -> str`
    (je Abschnitt `(nummer, form, budget)`)
  - `laengen.gesamtzeile(budgets: Sequence[int]) -> str`
  - `laengen.journalzeile(seed, muster, faktor, eintraege) -> str`
  - `laengen.JOURNAL_ART = "entschieden"`, `laengen.JOURNAL_QUELLE = "szene"`
- **Alle Nutzertexte dieses Moduls laufen ueber `T`** (A1-Konvention K1), die
  englischen Fassungen stehen in
  `interview_theater/sprachen/en/texte.toml` unter `["laengen"]`.

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_prompt.py`

```python
"""Die Prompt-Bausteine des Laengen-Rhythmus (30.09.2026, Karte R).

Die Bausteine sind Text, kein Modellaufruf: derselbe Stand liefert denselben
Block. Gemessen wird, dass jede Zahl genau EINMAL im Block steht, dass der
Block das Budget als Vorrang ausweist (sonst gewinnt die Laengenangabe aus
``formen/prosa.md``) und dass ohne Budget nichts dasteht.
"""

import pytest

from interview_theater import laengen, workshop


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_der_szenenblock_nennt_das_budget_einmal():
    block = laengen.block_szene(320)
    assert "320" in block
    assert block.count("320") == 1
    assert laengen.BLOCK_KOPF_SZENE in block


def test_ohne_budget_gibt_es_keinen_block():
    """Datengetrieben wie ``kontext.baue``: ein leerer Block faellt ersatzlos
    weg, und der Nutzertext bleibt zeichengleich."""
    assert laengen.block_szene(0) == ""
    assert laengen.block_prosa([]) == ""


def test_der_prosablock_nennt_jeden_abschnitt_mit_nummer_form_und_budget():
    block = laengen.block_prosa([(1, "chor", 100), (2, "dialog", 450),
                                 (3, "rap", 120)])
    for teil in ("1", "chor", "100", "2", "dialog", "450", "3", "rap", "120"):
        assert teil in block, teil
    # Die Summe steht auch da -- sie tritt an die Stelle der festen Zeile
    # "Insgesamt 1.500 bis 3.500 Woerter".
    assert "670" in block


def test_der_prosablock_bindet_die_abschnittszahl():
    """Ohne Bindung hat eine Liste von Budgets je Abschnitt keinen Adressaten:
    ``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Zahl sonst frei."""
    block = laengen.block_prosa([(1, "chor", 100), (2, "dialog", 450)])
    assert laengen.SATZ_BINDUNG.format(anzahl=2) in block


def test_der_block_weist_sich_selbst_als_vorrang_aus():
    """``formen/prosa.md`` und die Formen-Regelbloecke nennen eigene Laengen.
    Steht die Zahl an zwei Stellen, muss eine von beiden ausdruecklich die
    gueltige sein -- sonst ergaenzt das Modell selbst."""
    assert laengen.SATZ_VORRANG in laengen.block_szene(300)
    assert laengen.SATZ_VORRANG in laengen.block_prosa([(1, "chor", 100)])


def test_die_gesamtzeile_ist_eine_zeile_mit_einer_zahl():
    zeile = laengen.gesamtzeile([100, 450, 120])
    assert "670" in zeile
    assert "\n" not in zeile


def test_die_journalzeile_haelt_seed_muster_und_budgets_fest():
    """Reproduzierbar heisst: ein Mensch kann es nachrechnen. Seed, Muster und
    Faktor stehen deshalb in EINER Journalzeile -- angehaengt, nie geaendert."""
    zeile = laengen.journalzeile(
        seed=-100123, muster=("kurz", "lang", "kurz"), faktor=0.25,
        eintraege=[(1, "chor", 20), (2, "dialog", 110)],
    )
    assert "-100123" in zeile
    assert "kurz" in zeile and "lang" in zeile
    assert "0.25" in zeile or "25" in zeile
    assert "20" in zeile and "110" in zeile
    assert "\n" not in zeile, "eine Journalzeile ist eine Zeile"


def test_die_texte_laufen_ueber_T():
    """A1-Konvention K1: jeder Nutzertext ist ueber ``T`` erreichbar, damit
    die englische Fassung aus ``sprachen/en/texte.toml`` kommt."""
    assert laengen.T.BLOCK_KOPF_SZENE == laengen.BLOCK_KOPF_SZENE
    assert laengen.T.SATZ_VORRANG == laengen.SATZ_VORRANG
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prompt.py`
Erwartet: FAIL, `AttributeError: ... has no attribute 'block_szene'`.

- [x] **Schritt 3: An `interview_theater/laengen.py` anhaengen**

```python
# ---------------------------------------------------------------------------
# Die Prompt-Bausteine
#
# Sie sind Text und kein Modellaufruf: derselbe Stand liefert denselben Block.
# Ein leerer Block faellt beim Zusammenbau ersatzlos weg -- datengetrieben wie
# ``kontext.baue`` --, und genau daran haengt die Zusage an Dortmund: ohne
# Budget bleibt jeder Nutzertext zeichengleich.
# ---------------------------------------------------------------------------

#: Der Kopf des Budget-Blocks im Szenen-Prompt (Phase 7, eine Szene).
BLOCK_KOPF_SZENE = "Die Laenge dieser Szene:"

#: Der Kopf im Prosa-Prompt (Phase 6, die ganze Geschichte).
BLOCK_KOPF_PROSA = "Die Laenge der Abschnitte:"

#: Eine Zeile je Abschnitt. Die Form steht mit, weil sie erklaert, warum
#: dieser Abschnitt kuerzer sein darf als der naechste.
ZEILE_ABSCHNITT = "- Abschnitt {nummer} ({form}): etwa {budget} Woerter"

#: Die Laenge EINER Szene.
ZEILE_SZENE = "Etwa {budget} Woerter. Deutlich kuerzer ist gut, laenger nicht."

#: Die Summe. Sie tritt an die Stelle der festen Zeile "Insgesamt 1.500 bis
#: 3.500 Woerter" aus ``kurzgeschichte.ANWEISUNG``.
ZEILE_GESAMT = "Insgesamt etwa {gesamt} Woerter."

#: Die Bindung der Abschnittszahl. Ohne sie hat eine Liste von Budgets je
#: Abschnitt keinen Adressaten: ``kurzgeschichte.ANWEISUNG`` stellt dem
#: Modell die Zahl ausdruecklich frei, und ``formen/prosa.md`` erklaert eine
#: vorhandene Szenenfolge fuer verbindlich -- zwei Saetze, die sich
#: widersprechen. Dieser bindet, wie ``kuerzung.notiz_fuer_prosa`` es schon
#: tut.
SATZ_BINDUNG = ("Genau {anzahl} Abschnitte, in dieser Reihenfolge, mit diesen "
                "Laengen.")

#: Der Vorrang. Die Formen-Regelbloecke und ``formen/prosa.md`` nennen eigene
#: Laengen; steht eine Zahl an zwei Stellen, muss eine von beiden
#: ausdruecklich die gueltige sein -- sonst ergaenzt das Modell selbst
#: (Prompt-Audit 06.09.2026).
SATZ_VORRANG = ("Diese Laengen gelten. Andere Laengenangaben in den Regeln "
                "unten sind damit ueberschrieben.")

#: Der Rhythmus als Satz. Er sagt, dass die Ungleichheit Absicht ist -- ohne
#: ihn glaettet ein Modell sie weg, weil Gleichmass wie Sorgfalt aussieht.
SATZ_RHYTHMUS = ("Die Laengen sind absichtlich verschieden. Gleich lange "
                 "Abschnitte nehmen dem Stueck den Rhythmus.")

#: Journal: Art und Quelle. Angehaengt, nie geaendert (AGENTS.md).
JOURNAL_ART = "entschieden"
JOURNAL_QUELLE = "szene"
JOURNAL_ZEILE = ("Laengen gewuerfelt (Seed {seed}, Muster {muster}, Faktor "
                 "{faktor}): {budgets}")


def block_szene(budget: int) -> str:
    """Der Budget-Block fuer EINE Szene, oder "" ohne Budget."""
    if int(budget) <= 0:
        return ""
    return "\n".join([
        T.BLOCK_KOPF_SZENE,
        T.ZEILE_SZENE.format(budget=int(budget)),
        T.SATZ_VORRANG,
    ])


def block_prosa(eintraege: Sequence[tuple[int, str, int]]) -> str:
    """Der Budget-Block fuer die ganze Geschichte, oder "" ohne Abschnitte.

    ``eintraege`` sind ``(nummer, form, budget)`` in der Reihenfolge der
    Abschnitte."""
    brauchbar = [(int(n), str(f or ""), int(b)) for n, f, b in eintraege
                 if int(b) > 0]
    if not brauchbar:
        return ""
    zeilen = [T.BLOCK_KOPF_PROSA]
    zeilen += [T.ZEILE_ABSCHNITT.format(nummer=n, form=f, budget=b)
               for n, f, b in brauchbar]
    zeilen.append(T.ZEILE_GESAMT.format(gesamt=sum(b for _, _, b in brauchbar)))
    zeilen.append(T.SATZ_BINDUNG.format(anzahl=len(brauchbar)))
    zeilen.append(T.SATZ_RHYTHMUS)
    zeilen.append(T.SATZ_VORRANG)
    return "\n".join(zeilen)


def gesamtzeile(werte: Sequence[int]) -> str:
    """Die eine Zeile, die in ``kurzgeschichte.ANWEISUNG`` an die Stelle von
    ``ZEILE_GESAMTLAENGE`` tritt."""
    return T.ZEILE_GESAMT.format(gesamt=sum(int(w) for w in werte))


def journalzeile(seed: int, muster: Sequence[str], faktor: float,
                 eintraege: Sequence[tuple[int, str, int]]) -> str:
    """Seed, Muster, Faktor und Budgets als EINE Journalzeile.

    Der Seed ist die ``chat_id`` und muss nirgends gespeichert werden -- diese
    Zeile ist trotzdem noetig, damit ein Mensch nachrechnen kann, warum Szene
    2 laenger sein durfte als Szene 1. Das Journal wird nur angehaengt, also
    steht hier eine Zeile je Lauf und nie eine Korrektur."""
    return T.JOURNAL_ZEILE.format(
        seed=int(seed),
        muster="-".join(muster),
        faktor=f"{float(faktor):g}",
        budgets=", ".join(f"{int(n)}:{int(b)}" for n, _f, b in eintraege),
    )


# Der Textzugriff steht am Modulende, nach allen Konstanten (A1-Konvention
# K1): Deutsch ist die Konstante selbst, Englisch kommt aus
# ``sprachen/en/texte.toml`` unter ``["laengen"]``. Gelesen wird ausschliesslich
# zur Aufrufzeit -- nie in einem Default-Argument und nie in einer
# Modulkonstante.
from interview_theater import sprache  # noqa: E402

T = sprache.Texte(__name__)
```

- [x] **Schritt 4: Die englischen Fassungen eintragen**

An `interview_theater/sprachen/en/texte.toml` anhaengen (A1-Konvention K2:
Tabelle je definierendem Modul, Modulname in Anfuehrungszeichen, Schluessel in
Definitionsreihenfolge; Platzhaltermengen identisch zur deutschen Fassung,
A1-Konvention K3):

```toml
["laengen"]
BLOCK_KOPF_SZENE = "How long this scene should be:"
BLOCK_KOPF_PROSA = "How long the sections should be:"
ZEILE_ABSCHNITT = "- Section {nummer} ({form}): about {budget} words"
ZEILE_SZENE = "About {budget} words. Clearly shorter is fine, longer is not."
ZEILE_GESAMT = "About {gesamt} words in total."
SATZ_BINDUNG = "Exactly {anzahl} sections, in this order, with these lengths."
SATZ_VORRANG = "These lengths apply. Any other length given in the rules below is overridden."
SATZ_RHYTHMUS = "The lengths differ on purpose. Sections of equal length take the rhythm out of the play."
JOURNAL_ZEILE = "Lengths rolled (seed {seed}, pattern {muster}, factor {faktor}): {budgets}"
```

Hinweis: `JOURNAL_ART` und `JOURNAL_QUELLE` sind **Protokoll**
(`repo.schreibe_journal` prueft die Werte nicht, aber `kontext` und die
Weboberflaeche lesen sie) und bleiben woertlich `entschieden`/`szene` -- sie
stehen deshalb **nicht** in der Tabelle.

- [x] **Schritt 5: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prompt.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m scripts.pruefe_sprache --schluessel laengen`
Erwartet: `0 Treffer`, Exit 0.

- [x] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/laengen.py interview_theater/sprachen/en/texte.toml \
        tests/test_laengen_prompt.py
git commit -m "laengen.py: Prompt-Bausteine mit Vorrang-Satz und die Journalzeile (R)"
```

---

## Aufgabe 6: Phase 6 -- das Budget im Prosa-Prompt

**Files:**
- Modify: `interview_theater/kurzgeschichte.py` (`ANWEISUNG` um
  `ZEILE_GESAMTLAENGE` herum aufgebaut, `systemanweisung`, `baue_nutzertext`,
  neu `budget_eintraege`)
- Modify: `scripts/prompt_schnappschuss.py` (`teile()`)
- Test: `tests/test_laengen_prosa.py` (neu)

**Interfaces:**
- Consumes: `laengen.aktiv`, `laengen.form_der_szene`, `laengen.budgets`,
  `laengen.block_prosa`, `laengen.gesamtzeile`, `laengen.journalzeile`,
  `repo.hole_szenen`, `repo.schreibe_journal`.
- Produces:
  - `kurzgeschichte.ZEILE_GESAMTLAENGE: str` (= `"Insgesamt 1.500 bis 3.500 Woerter."`)
  - `kurzgeschichte.systemanweisung(budgets: Sequence[int] | None = None) -> str`
  - `kurzgeschichte.budget_eintraege(conn, chat_id, faktor=1.0) -> list[tuple[int, str, int]]`
  - `kurzgeschichte.baue_nutzertext(conn, chat_id, regie=None, vorlage=False, eintraege=None)`

**Der Dortmund-Nachweis dieser Aufgabe** ist eine Zahl, die ich auf `d8deb6c`
selbst gemessen habe: `kurzgeschichte.systemanweisung()` ist **12785 Zeichen**
mit `sha256 = 704119e3dd886eef7ac619511b4ab70cc7c6fb6858a8618e4ee2da19ffddc729`.
Der Test unten prueft genau das.

**ANNAHME A5** (aus Aufgabe 0): liest `kurzgeschichte` seine Texte schon ueber
`T` (A1 Aufgabe 16), lauten die Zugriffe `T.ANWEISUNG` und
`T.ZEILE_GESAMTLAENGE`; sonst `ANWEISUNG` und `ZEILE_GESAMTLAENGE` direkt. Der
Code unten steht in der `T`-Variante; ohne `T` wird `T.` gestrichen. Beide
Varianten brauchen `test_die_ersetzbare_zeile_steht_wirklich_in_der_anweisung`
-- eine Ersetzung, die ins Leere greift, ist ein stiller Durchfall.

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_prosa.py`

```python
"""Phase 6: das Budget im Prosa-Prompt (30.09.2026, Karte R).

Zwei Zusagen in einer Datei: ohne aktives Profil ist die Systemanweisung
**zeichengleich** zu dem Stand, der auf ``d8deb6c`` gemessen wurde -- und mit
aktivem Profil tritt die Summe an die Stelle der festen Zeile "Insgesamt
1.500 bis 3.500 Woerter", waehrend die Liste je Abschnitt im Nutzertext steht.
"""

import hashlib

import pytest

from interview_theater import kurzgeschichte, laengen, repo, workshop

#: Selbst gemessen am 30.09.2026 auf ``d8deb6c``, vor jeder Aenderung dieser
#: Karte. Der Massstab fuer Dortmund -- er steht hier und nicht in einer
#: Golden-Datei, weil eine Zahl in einem Test schwerer zu uebersehen ist.
SYSTEM_SHA_D8DEB6C = "704119e3dd886eef7ac619511b4ab70cc7c6fb6858a8618e4ee2da19ffddc729"
SYSTEM_LAENGE_D8DEB6C = 12785


@pytest.fixture(autouse=True)
def ohne_profil(monkeypatch):
    from interview_theater import anweisungen
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Dortmund bleibt zeichengleich ----------------------------------------


def test_ohne_budget_ist_die_systemanweisung_zeichengleich():
    text = kurzgeschichte.systemanweisung()
    assert len(text) == SYSTEM_LAENGE_D8DEB6C
    assert _sha(text) == SYSTEM_SHA_D8DEB6C


def test_budget_none_ist_derselbe_text_wie_kein_argument():
    assert kurzgeschichte.systemanweisung(None) == kurzgeschichte.systemanweisung()


def test_die_ersetzbare_zeile_steht_wirklich_in_der_anweisung():
    """Eine Ersetzung, die ins Leere greift, ist ein stiller Durchfall: der
    Prompt behielte die feste Zahl, das Budget stuende daneben, und beides
    waere wahr. Deshalb ist die Anwesenheit der Zeile ein Test und keine
    Annahme."""
    anweisung = getattr(kurzgeschichte, "T", kurzgeschichte).ANWEISUNG
    zeile = getattr(kurzgeschichte, "T", kurzgeschichte).ZEILE_GESAMTLAENGE
    assert anweisung.count(zeile) == 1, "genau einmal, sonst ersetzt es zu viel"


# --- Mit Budget -----------------------------------------------------------


def test_mit_budget_tritt_die_summe_an_die_stelle_der_festen_zahl():
    text = kurzgeschichte.systemanweisung([100, 450, 120])
    zeile = getattr(kurzgeschichte, "T", kurzgeschichte).ZEILE_GESAMTLAENGE
    assert zeile not in text, "die feste Zahl steht noch da"
    assert "670" in text
    assert "1.500" not in text and "3.500" not in text


def test_der_prompt_nennt_die_gesamtlaenge_nur_einmal():
    """Prompt-Audit-Regel: ein Fakt hat genau eine Stelle. Die Summe steht in
    der Systemanweisung, die Liste je Abschnitt im Nutzertext."""
    text = kurzgeschichte.systemanweisung([100, 450, 120])
    assert text.count("670") == 1


# --- Die Eintraege aus den Szenen -----------------------------------------


@pytest.fixture
def drei_szenen(conn, monkeypatch):
    """Drei Szenen, wie sie beim Eintritt in Phase 6 dastehen: Nummer, Titel,
    Form teils bestaetigt, teils nur vorgeschlagen, kein Text."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    for nummer, form, vorschlag in ((1, "chor", None), (2, None, "dialog"),
                                    (3, None, None)):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        if form:
            repo.setze_szenenfeld(conn, szene_id, "form", form)
        if vorschlag:
            repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", vorschlag)
    return conn


def test_die_eintraege_lesen_form_bestaetigt_vor_vorgeschlagen(drei_szenen):
    eintraege = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    assert [n for n, _f, _b in eintraege] == [1, 2, 3]
    assert [f for _n, f, _b in eintraege] == ["chor", "dialog",
                                              workshop.form_vorgabe()]
    assert all(b > 0 for _n, _f, b in eintraege)


def test_die_eintraege_haengen_nicht_an_der_zahl_der_szenen(drei_szenen):
    """Zyklisches Muster: eine vierte Szene darf das Budget von Szene 1 nicht
    verschieben -- sonst rechnet das Nachzaehlen gegen eine andere Zahl."""
    vorher = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    repo.stelle_szene_sicher(drei_szenen, 1, 4)
    nachher = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    assert nachher[:3] == vorher
    assert len(nachher) == 4


def test_ohne_aktives_profil_gibt_es_keine_eintraege(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.stelle_szene_sicher(conn, 1, 1)
    assert kurzgeschichte.budget_eintraege(conn, 1) == []


def test_der_faktor_verkuerzt_die_eintraege(drei_szenen):
    voll = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    kurz = kurzgeschichte.budget_eintraege(drei_szenen, 1, faktor=0.25)
    assert [b for _n, _f, b in kurz] != [b for _n, _f, b in voll]
    assert all(k <= v for (_a, _b, k), (_c, _d, v) in zip(kurz, voll))


# --- Der Nutzertext -------------------------------------------------------


def test_ohne_eintraege_bleibt_der_nutzertext_zeichengleich(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    ohne = kurzgeschichte.baue_nutzertext(conn, 1)
    mit_none = kurzgeschichte.baue_nutzertext(conn, 1, eintraege=None)
    leer = kurzgeschichte.baue_nutzertext(conn, 1, eintraege=[])
    assert ohne == mit_none == leer


def test_mit_eintraegen_steht_der_block_im_nutzertext(drei_szenen):
    repo.setze_arbeitsstand(drei_szenen, 1, "rahmen", "Am Kanal, nachts")
    eintraege = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    text = kurzgeschichte.baue_nutzertext(drei_szenen, 1, eintraege=eintraege)
    assert laengen.BLOCK_KOPF_PROSA in text
    assert laengen.SATZ_BINDUNG.format(anzahl=3) in text
    for nummer, form, budget in eintraege:
        assert f"{budget}" in text
        assert form in text


def test_der_schnappschuss_deckt_die_prosa_systemanweisung_ab():
    """``scripts/prompt_schnappschuss.py`` ist der Waechter gegen ein undichtes
    Profil. Was dort nicht steht, prueft der Bitgleichheits-Test nicht --
    und diese Anweisung stand bis heute nicht drin."""
    from scripts import prompt_schnappschuss
    namen = {name for name, _ in prompt_schnappschuss.teile()}
    assert "kurzgeschichte.systemanweisung()" in namen
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prosa.py`
Erwartet: FAIL. Zuerst
`AttributeError: module 'interview_theater.kurzgeschichte' has no attribute 'ZEILE_GESAMTLAENGE'`.
`test_ohne_budget_ist_die_systemanweisung_zeichengleich` ist an diesem Punkt
schon **gruen** -- richtig so: es ist der Waechter, nicht das Ziel.

- [x] **Schritt 3: `ANWEISUNG` um die ersetzbare Zeile herum aufbauen**

In `interview_theater/kurzgeschichte.py`, **vor** `ANWEISUNG`:

```python
#: Die eine Zeile in ``ANWEISUNG``, die ein Laengenbudget ersetzt
#: (30.09.2026, Karte R). Sie steht als eigener Absatz und kommt genau
#: einmal vor -- ein Test haelt beides fest, denn eine Ersetzung, die ins
#: Leere greift, waere ein stiller Durchfall: der Prompt behielte die feste
#: Zahl, das Budget stuende daneben, und das Modell muesste raten.
#:
#: **Sie bleibt zeichengleich.** Ohne Budget ist ``systemanweisung()`` genau
#: der Text, der vor dieser Karte entstand (gemessen: 12.785 Zeichen,
#: sha256 704119e3...).
ZEILE_GESAMTLAENGE = "Insgesamt 1.500 bis 3.500 Woerter."
```

Und in `ANWEISUNG` die Zeile durch die Interpolation ersetzen -- der Text
bleibt dabei buchstabengleich, weil `ZEILE_GESAMTLAENGE` genau die alte Zeile
ist. Konkret wird aus

```python
Insgesamt 1.500 bis 3.500 Woerter.
```

innerhalb des Tripelstrings ein `{zeile}` und der String bekommt ein
`.format(zeile=ZEILE_GESAMTLAENGE)` -- **aber das geht nicht**, weil
`ANWEISUNG` geschweifte Klammern im Beispielblock enthaelt. Deshalb die
sichere Variante ohne `format`: `ANWEISUNG` bleibt woertlich unveraendert,
und `systemanweisung` ersetzt die Zeile per `str.replace`. Der Test aus
Schritt 1 prueft, dass sie genau einmal vorkommt.

- [x] **Schritt 4: `systemanweisung` ein Budget geben**

`systemanweisung()` in `interview_theater/kurzgeschichte.py` ersetzen:

```python
def systemanweisung(budgets: Sequence[int] | None = None) -> str:
    """Die Anweisung plus dem Prosa-Regelblock -- heiss nachgeladen wie jeder
    Prompt.

    ``budgets`` (30.09.2026, Karte R) sind die Wortbudgets der Abschnitte.
    Sind sie da, tritt ihre **Summe** an die Stelle der festen Zeile
    ``ZEILE_GESAMTLAENGE``; die Liste je Abschnitt steht im **Nutzertext**,
    weil sie je Gruppe verschieden ist. Ein Fakt hat genau eine Stelle im
    Prompt (Prompt-Audit 06.09.2026) -- deshalb wird die feste Zeile
    **ersetzt** und nicht ergaenzt.

    Ohne ``budgets`` ist der Text **zeichengleich** zu dem Stand vor dieser
    Karte (gemessen: 12.785 Zeichen). Daran haengt die Zusage an Dortmund."""
    anweisung = T.ANWEISUNG
    if budgets:
        from interview_theater import laengen

        anweisung = anweisung.replace(
            T.ZEILE_GESAMTLAENGE, laengen.gesamtzeile(budgets),
        )
    teile = [anweisung]
    prosa = anweisungen.hole_optional("formen/prosa")
    if prosa and prosa.strip():
        teile.append(prosa.strip())
    tells = anweisungen.hole_optional("theater-tells")
    if tells and tells.strip():
        teile.append(tells.strip())
    return "\n\n".join(teile)
```

Dazu am Modulkopf `from typing import Sequence` ergaenzen (bzw.
`from collections.abc import Sequence`, wie das Repo es an anderer Stelle
haelt -- `grep -n "import Sequence" interview_theater/*.py` zeigt die dort
gewaehlte Form; in `laengen.py` steht `from typing import ... Sequence`).

**Ohne `T`** (Annahme A5 faellt) lauten die beiden Zugriffe `ANWEISUNG` und
`ZEILE_GESAMTLAENGE`.

- [x] **Schritt 5: `budget_eintraege` und der Nutzertext-Block**

An `interview_theater/kurzgeschichte.py` anhaengen bzw. `baue_nutzertext`
erweitern:

```python
def budget_eintraege(conn, chat_id: int,
                     faktor: float = 1.0) -> list[tuple[int, str, int]]:
    """Je Abschnitt ``(nummer, form, budget)`` -- oder ``[]``, wenn dieses
    Profil keine Budgets waehlt.

    **Die Zahl der Abschnitte steht hier schon fest**: Phase 6 ist erst
    erreichbar, wenn mindestens eine Szene angelegt ist
    (``phasen.voraussetzungen``), und ``prompts/formen/prosa.md`` erklaert
    eine vorhandene Szenenfolge fuer verbindlich. Die **Form** kommt aus
    ``laengen.form_der_szene``: bestaetigt (``szene.form``) vor
    vorgeschlagen (``form_vorschlag``) vor Profilvorgabe. Gelesen, nicht
    geschrieben -- ``szene.form`` bleibt unberuehrt, sie bestaetigt allein
    die Gruppe.

    Reine Leseabfrage, kein Modellaufruf."""
    from interview_theater import laengen

    if not laengen.aktiv():
        return []
    szenen = sorted(
        (s for s in repo.hole_szenen(conn, chat_id) if not s["entfernt_am"]),
        key=lambda s: s["nummer"] or 0,
    )
    if not szenen:
        return []
    nummern = [s["nummer"] or i + 1 for i, s in enumerate(szenen)]
    formen = [laengen.form_der_szene(s) for s in szenen]
    werte = laengen.budgets(formen, nummern=nummern, seed=chat_id, faktor=faktor)
    return list(zip(nummern, formen, werte))
```

In `baue_nutzertext` die Signatur um `eintraege` erweitern und den Block
einfuegen -- **vor** dem Auftrag, damit er nahe am Ende steht (das Ende des
Prompts wiegt am schwersten, SPEC § 6.1):

```python
def baue_nutzertext(
    conn, chat_id: int, regie: str | None = None, vorlage: bool = False,
    eintraege: Sequence[tuple[int, str, int]] | None = None,
) -> str:
    """... (bestehender Docstring bleibt) ...

    ``eintraege`` (30.09.2026, Karte R) sind die Wortbudgets je Abschnitt.
    Ohne sie -- und mit einer leeren Liste -- bleibt der Nutzertext
    **zeichengleich** wie vorher; der Block faellt ersatzlos weg,
    datengetrieben wie in ``kontext.baue``."""
    from interview_theater import laengen, szenenfolge

    teile = [szenenfolge._erfundenes(conn, chat_id)]
    stile = [
        f"- {f['name']}: {(f['sprachstil'] or '').strip()}"
        for f in repo.figuren(conn, chat_id)
        if (f["sprachstil"] or "").strip()
    ]
    if stile:
        teile.append("So sprechen die Figuren:\n" + "\n".join(stile))
    if vorlage:
        teile.append(vorlage_text(conn, chat_id))
    if eintraege:
        teile.append(laengen.block_prosa(eintraege))
    auftrag = "Euer Auftrag:\nSchreib die Geschichte am Stueck."
    if regie and regie.strip():
        auftrag += f"\nDie Gruppe sagt dazu: {regie.strip()}"
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)
```

- [x] **Schritt 6: Den Schnappschuss-Waechter nachziehen**

In `scripts/prompt_schnappschuss.py`, in `teile()` hinter dem
`szenenfolge`-Block:

```python
    # Die Prosa-Systemanweisung (Phase 6). Sie stand bis zum 30.09.2026 nicht
    # im Schnappschuss -- also prueefte der Bitgleichheits-Test daran vorbei,
    # obwohl sie ``formen/prosa.md`` und ``theater-tells`` einsammelt und damit
    # profilabhaengig ist. **Ohne Argument**, also in genau der Form, die
    # Dortmund bekommt.
    stuecke.append(("kurzgeschichte.systemanweisung()",
                    kurzgeschichte.systemanweisung()))
```

und `kurzgeschichte` in die Importliste der Datei aufnehmen.

**Die Massstab-Datei `docs/prompt-audit/schnappschuss-vor-profilumbau.txt`
wird NICHT angefasst.** `tests/test_profil_bitgleich._vergleiche` erlaubt neue
Abschnitte ausdruecklich und verbietet nur fehlende und veraenderte -- der
neue Abschnitt wird also ab jetzt zwischen "ohne Variable" und
"`IT_WORKSHOP=dortmund-2026`" verglichen (`test_dortmund_und_keine_variable_sind_identisch`),
und der sha aus Schritt 1 haelt ihn gegen `d8deb6c`.

- [x] **Schritt 7: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prosa.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/test_kuerzung.py tests/profile/`
Erwartet: `passed`, kein `failed`.

- [x] **Schritt 8: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/kurzgeschichte.py scripts/prompt_schnappschuss.py \
        tests/test_laengen_prosa.py
git commit -m "Phase 6: Budget je Abschnitt im Nutzertext, Summe statt der festen Zeile (R)"
```

---

## Aufgabe 7: Phase 6 -- `hole_text` und `schreibe` synchron herausgezogen

**Files:**
- Modify: `interview_theater/kurzgeschichte.py` (`starte`/`_lauf` zerlegt)
- Test: `tests/test_laengen_prosa.py` (anhaengen)

**Warum.** `kurzgeschichte._lauf` ist heute eine geschachtelte Funktion in
`starte` und haelt die Sperre je `chat_id`. Der Nachpass (Aufgabe 14) laeuft
**in genau diesem Thread und unter genau dieser Sperre** -- er kann `starte`
also nicht rufen (die Sperre liegt noch) und braucht einen synchronen
Einstieg. Dasselbe Verhaeltnis wie `szene.schreibe` zu `szene._lauf`, das es
schon gibt.

Ausserdem braucht der Nachpass die Modellantwort **vor** dem Speichern: er
muss pruefen, ob die Abschnittszahl gleich geblieben ist und ob ein
Belegzitat verlorenging, und eine Antwort verwerfen, die das nicht haelt.
Deshalb zwei Funktionen statt einer.

**Interfaces:**
- Produces:
  - `kurzgeschichte.hole_text(conn, klm, e, chat_id, regie=None, vorlage=False, eintraege=None, art=ART) -> str`
    (nur der Modellaufruf -- kein Speichern, keine Chatnachricht)
  - `kurzgeschichte.schreibe(conn, tg, klm, e, chat_id, regie=None, vorlage=False, art=ART) -> list[int]`
    (Modellaufruf, zerlegen, speichern, Chat -- synchron, **ohne** Sperre)
  - `kurzgeschichte.starte(...)` unveraendert in Signatur und Verhalten.

- [x] **Schritt 1: Den failenden Test schreiben** -- an
`tests/test_laengen_prosa.py` anhaengen

```python
# --- Der synchrone Einstieg (Aufgabe 7) -----------------------------------


class ProsaAttrappe:
    """Liefert eine Kurzgeschichte und merkt jeden Aufruf samt ``art``."""

    ANTWORT = (
        "## 1. Ankunft\nZusammenfassung: Sie kommt an.\n\nText eins.\n\n"
        "## 2. Streit\nZusammenfassung: Es kracht.\n\nText zwei.\n"
    )

    def __init__(self, antwort=None):
        self.antwort = antwort or self.ANTWORT
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


@pytest.fixture
def prosa_bereit(conn, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    for nummer in (1, 2):
        repo.stelle_szene_sicher(conn, 1, nummer)
    return conn


def test_hole_text_ruft_nur_das_modell(prosa_bereit, einst):
    """Kein Speichern, keine Chatnachricht -- der Nachpass muss erst pruefen
    duerfen, bevor etwas in der Datenbank steht."""
    klm = ProsaAttrappe()
    vorher = [dict(s) for s in repo.hole_szenen(prosa_bereit, 1)]
    text = kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1)
    assert "Ankunft" in text
    assert len(klm.aufrufe) == 1
    nachher = [dict(s) for s in repo.hole_szenen(prosa_bereit, 1)]
    assert [s["prosa"] for s in nachher] == [s["prosa"] for s in vorher]


def test_hole_text_gibt_die_art_weiter(prosa_bereit, einst):
    """Eigene ``art``-Werte machen die Nachpass-Laeufe in der Tabelle
    ``aufruf`` getrennt zaehlbar -- so wie ``dramaturgie_b1`` es vormacht."""
    klm = ProsaAttrappe()
    kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1, art="kurzgeschichte_nachpass")
    assert klm.aufrufe[0]["art"] == "kurzgeschichte_nachpass"


def test_hole_text_legt_das_budget_in_den_nutzertext(prosa_bereit, einst):
    klm = ProsaAttrappe()
    eintraege = kurzgeschichte.budget_eintraege(prosa_bereit, 1)
    kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1, eintraege=eintraege)
    assert laengen.BLOCK_KOPF_PROSA in klm.aufrufe[0]["nutzer"]
    assert laengen.gesamtzeile([b for _n, _f, b in eintraege]) in \
        klm.aufrufe[0]["system"]


def test_schreibe_speichert_und_meldet(prosa_bereit, einst, tg):
    klm = ProsaAttrappe()
    nummern = kurzgeschichte.schreibe(prosa_bereit, tg, klm, einst, 1)
    assert nummern == [1, 2]
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa_bereit, 1)}
    assert "Text eins" in prosa[1] and "Text zwei" in prosa[2]


def test_starte_verhaelt_sich_wie_vorher(prosa_bereit, einst, tg):
    """Die Zerlegung darf am aeusseren Weg nichts aendern: ein Thread, eine
    Sperre, dieselbe Meldung."""
    klm = ProsaAttrappe()
    thread = kurzgeschichte.starte(prosa_bereit, tg, klm, einst, 1)
    assert thread is not None
    thread.join(timeout=20)
    assert kurzgeschichte.laeuft(1) is False
    assert any("Abschnitt" in n for n in tg.nachrichten_texte()), tg.nachrichten
```

Hinweis zur Attrappe: `TelegramAttrappe` aus `tests/test_knoepfe.py` wird wie
in `tests/test_kuerzung.py` importiert (`from test_knoepfe import
TelegramAttrappe`). `nachrichten_texte()` steht dort ggf. anders -- die
vorhandene Zugriffsform aus `tests/test_kuerzung.py` uebernehmen, statt eine
neue zu erfinden (`grep -n "def " tests/test_knoepfe.py | head -30`).

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prosa.py -k hole_text`
Erwartet: FAIL, `AttributeError: ... has no attribute 'hole_text'`.

- [x] **Schritt 3: `hole_text` und `schreibe` aus `_lauf` herausziehen**

`starte` in `interview_theater/kurzgeschichte.py` bleibt in Signatur und
Verhalten; nur der Rumpf von `_lauf` wandert in die beiden neuen Funktionen.

```python
def hole_text(conn, klm, e, chat_id: int, regie: str | None = None,
              vorlage: bool = False,
              eintraege: Sequence[tuple[int, str, int]] | None = None,
              art: str = ART) -> str:
    """**Nur** der Modellaufruf -- Prompt bauen, fragen, Antwort liefern.

    Kein Speichern, keine Chatnachricht, keine Sperre. Herausgezogen am
    30.09.2026 (Karte R), weil der Nachpass die Antwort **pruefen** muss,
    bevor sie in der Datenbank steht: hat sie eine andere Abschnittszahl oder
    fehlt ein Belegzitat, wird sie verworfen und die alte Fassung bleibt.

    ``art`` landet in der Tabelle ``aufruf`` und macht Nachpass-Laeufe
    getrennt zaehlbar."""
    from interview_theater import szene_claude

    system = systemanweisung([b for _n, _f, b in (eintraege or [])] or None)
    nutzer = baue_nutzertext(conn, chat_id, regie, vorlage=vorlage,
                             eintraege=eintraege)
    if szene_claude.ist_aktiv(e, conn, chat_id):
        import httpx

        return szene_claude.prosa(
            conn, e,
            getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
            chat_id, system, nutzer, art, timeout=TIMEOUT_S,
        )
    return klm.prosa(chat_id, system, nutzer, art,
                     max_tokens=MAX_TOKENS, timeout=TIMEOUT_S)


def schreibe(conn, tg, klm, e, chat_id: int, regie: str | None = None,
             vorlage: bool = False, art: str = ART) -> list[int]:
    """Der ganze Lauf, **synchron und ohne Sperre**: Modell fragen, zerlegen,
    Szenen anlegen, in den Chat melden. Liefert die Nummern der Abschnitte.

    Wie ``szene.schreibe`` verhaelt es sich zu ``starte``: die Sperre haelt
    der Aufrufer (``_lauf``), Fehler fliegen heraus. Wer es direkt ruft
    (Tests, der Nachpass), kuemmert sich selbst darum."""
    eintraege = budget_eintraege(conn, chat_id, faktor=_faktor(conn, chat_id))
    antwort = hole_text(conn, klm, e, chat_id, regie, vorlage, eintraege, art)
    abschnitte = zerlege(antwort or "")
    if not abschnitte:
        raise ValueError("Kurzgeschichte ohne erkennbare Abschnitte")
    nummern = lege_szenen_an(conn, chat_id, abschnitte)
    if eintraege:
        # Der Wuerfel ist reproduzierbar (Seed = chat_id), aber niemand soll
        # ihn nachrechnen muessen, um zu verstehen, warum Abschnitt 2 laenger
        # sein durfte. Angehaengt, nie geaendert.
        from interview_theater import laengen

        repo.schreibe_journal(
            conn, chat_id, laengen.JOURNAL_ART,
            laengen.journalzeile(
                seed=chat_id, muster=laengen.muster_fuer(chat_id),
                faktor=_faktor(conn, chat_id), eintraege=eintraege,
            ),
            quelle=laengen.JOURNAL_QUELLE,
        )
    from interview_theater import knoepfe, szene as szene_modul

    szene_modul._sende_und_merke(
        conn, tg, e, chat_id, _TEXT_FERTIG.format(anzahl=len(nummern)),
    )
    knoepfe.zeige_kurzgeschichte(conn, tg, chat_id)
    return nummern
```

`_faktor(conn, chat_id)` kommt aus Aufgabe 9. **Bis dahin** steht dort `1.0`
als Konstante mit einem `# Aufgabe 9`-Kommentar; Aufgabe 9 tauscht sie gegen
den Aufruf. (Wer die Aufgaben in Reihe abarbeitet, schreibt hier direkt
`laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, chat_id))` -- dann
entfaellt der Zwischenschritt.)

Und `_lauf` in `starte` schrumpft auf:

```python
    def _lauf() -> None:
        from interview_theater import arbeitszeilen, szene as szene_modul

        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "prosa")
        try:
            schreibe(conn, tg, klm, e, chat_id, regie, vorlage=vorlage)
        except Exception:
            log.exception("Kurzgeschichte fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "kurzgeschichte_fehlgeschlagen", "Lauf gescheitert",
                )
                szene_modul._sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)
            except Exception:
                log.exception("Fehlermeldung zur Kurzgeschichte fehlgeschlagen")
        finally:
            zeilen.stoppe()
            sperre.release()
```

**Ein Unterschied zum bisherigen Verhalten, bewusst:** `zeilen.stoppe()` stand
bisher **vor** der Fertig-Meldung und noch einmal im `finally`. Jetzt steht es
nur im `finally`, also **nach** der Meldung. Die Arbeitszeile lebt damit
wenige Millisekunden laenger. Wer das nicht will, gibt `schreibe` ein
optionales `zeilen=None` mit und stoppt es dort vor der Meldung -- der Test
`test_starte_verhaelt_sich_wie_vorher` deckt beide Varianten.

- [x] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_prosa.py tests/test_kuerzung.py`
Erwartet: `passed`, kein `failed`. `tests/test_kuerzung.py` ist hier der
eigentliche Waechter: es fuhr den Prosa-Weg schon vorher ueber `starte`.

Run: `$PY -m pytest -q -p no:cacheprovider -k "kurzgeschichte or prosa"`
Erwartet: `passed`, kein `failed`.

- [x] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/kurzgeschichte.py tests/test_laengen_prosa.py
git commit -m "Kurzgeschichte: hole_text und schreibe synchron herausgezogen, art als Parameter (R)"
```

---

## Aufgabe 8: Phase 7 -- das Budget im Szenen-Prompt, `art` als Parameter

**Files:**
- Modify: `interview_theater/szene.py` (`_REIHENFOLGE`, `_bloecke` in
  `baue_nutzertext`, neu `budget_fuer_szene`, `art` in
  `schreibe`/`_lauf`/`starte`)
- Test: `tests/test_laengen_szene.py` (neu)

**Interfaces:**
- Produces:
  - `szene.budget_fuer_szene(conn, chat_id, ziel) -> int` (0 = kein Budget)
  - `szene.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART) -> int`
  - `szene.starte(conn, tg, klm, e, chat_id, auftrag, art=ART) -> Thread | None`
  - `szene._REIHENFOLGE` enthaelt `"laenge"` **direkt hinter** `"aufgabe"`
    (damit es im nie gekuerzten Teil steht, wie Rahmen, Aufgabe, Angaben und
    Auftrag).

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_szene.py`

```python
"""Phase 7: das Budget im Szenen-Prompt (30.09.2026, Karte R).

Der Block steht im **nie gekuerzten** Teil des Nutzertexts: eine Laenge, die
die Kuerzungsleiter wegwerfen darf, ist keine Vorgabe. Ohne aktives Profil
bleibt der Nutzertext zeichengleich.
"""

import pytest

from interview_theater import laengen, phasen, repo, szene, workshop

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


class SzeneAttrappe:
    ANTWORT = (
        "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
        "ZUSAMMENFASSUNG: Mira und Pal treffen sich.\nANDERS GEMACHT: nichts\n\n"
        "MIRA: Du bist zu spaet.\nPAL: Ich war da.\n"
    )

    def __init__(self, antwort=None):
        self.antwort = antwort or self.ANTWORT
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


@pytest.fixture
def szene7(conn):
    """Phase 7, eine planungsvollstaendige Szene 1 mit bestaetigter Form."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    # ``setze_figur`` liefert **kein** id zurueck (repo.py:1827, Rueckgabe
    # ``None``) -- die id wird danach gelesen, so wie es auch
    # ``tests/test_kuerzung.py`` tut.
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Der Block ------------------------------------------------------------


def test_der_laengenblock_steht_direkt_hinter_der_aufgabe():
    """Reihenfolge ist Wirkung: die Laenge gehoert zu dem, was die Gruppe
    entschieden hat, und steht deshalb im nie gekuerzten Teil."""
    i = list(szene._REIHENFOLGE).index("aufgabe")
    assert szene._REIHENFOLGE[i + 1] == "laenge"


def test_der_laengenblock_wird_nie_gekuerzt():
    """``_kuerze_szenenprompt`` kuerzt Vorszenen, Chat, Kernpaket und
    Sprachprofil-Zitate -- die Laenge darf in keiner dieser Stufen
    verschwinden."""
    import inspect
    quelle = inspect.getsource(szene._kuerze_szenenprompt)
    assert "laenge" not in quelle


def test_ohne_profil_bleibt_der_nutzertext_zeichengleich(szene7):
    ziel = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    assert szene.budget_fuer_szene(szene7, 1, ziel) == 0
    text = szene.baue_nutzertext(szene7, 1, "Schreib Szene 1", ziel)
    assert laengen.BLOCK_KOPF_SZENE not in text


def test_mit_profil_steht_das_budget_im_nutzertext(szene7, padua):
    ziel = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    budget = szene.budget_fuer_szene(szene7, 1, ziel)
    assert 200 <= budget <= 450, budget          # Dialog-Rahmen
    text = szene.baue_nutzertext(szene7, 1, "Schreib Szene 1", ziel)
    assert laengen.BLOCK_KOPF_SZENE in text
    assert str(budget) in text
    assert laengen.SATZ_VORRANG in text


def test_das_budget_folgt_der_bestaetigten_form(szene7, padua):
    """Chor ist kuerzer als Dialog -- dieselbe Szene, andere Form, anderes
    Budget."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    ziel_dialog = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    dialog = szene.budget_fuer_szene(szene7, 1, ziel_dialog)
    repo.setze_szenenfeld(szene7, szene_id, "form", "chor")
    ziel_chor = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    chor = szene.budget_fuer_szene(szene7, 1, ziel_chor)
    assert chor < dialog, (chor, dialog)


def test_ohne_ziel_gibt_es_kein_budget(szene7, padua):
    assert szene.budget_fuer_szene(szene7, 1, None) == 0


# --- ``art`` als Parameter ------------------------------------------------


def test_schreibe_nimmt_eine_eigene_art(szene7, tg, einst):
    klm = SzeneAttrappe()
    szene.schreibe(szene7, tg, klm, einst, 1, "Schreib Szene 1",
                   art="szene_nachpass")
    assert klm.aufrufe[0]["art"] == "szene_nachpass"


def test_ohne_art_bleibt_es_bei_der_bisherigen(szene7, tg, einst):
    klm = SzeneAttrappe()
    szene.schreibe(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    assert klm.aufrufe[0]["art"] == szene.ART


def test_starte_gibt_die_art_durch(szene7, tg, einst):
    klm = SzeneAttrappe()
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1",
                          art="szene_nachpass")
    assert thread is not None
    thread.join(timeout=20)
    assert klm.aufrufe and klm.aufrufe[0]["art"] == "szene_nachpass"
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_szene.py`
Erwartet: FAIL, `ValueError: 'laenge' is not in list` in
`test_der_laengenblock_steht_direkt_hinter_der_aufgabe`.

- [x] **Schritt 3: `budget_fuer_szene` anlegen**

In `interview_theater/szene.py`, neben `_aufgabe_text`:

```python
def budget_fuer_szene(conn, chat_id: int, ziel) -> int:
    """Das Wortbudget dieser Szene, oder 0, wenn dieses Profil keine waehlt.

    Die Form kommt aus ``laengen.form_der_szene``: bestaetigt vor
    vorgeschlagen vor Profilvorgabe. Der Seed ist die ``chat_id``, das Muster
    wird zyklisch ueber die Szenennummer gelesen -- eine spaeter eingefuegte
    Szene verschiebt deshalb kein Budget einer frueheren.

    Reine Leseabfrage, kein Modellaufruf."""
    from interview_theater import laengen

    if ziel is None or not laengen.aktiv():
        return 0
    stand = repo.hole_arbeitsstand(conn, chat_id)
    return laengen.budget_fuer(
        ziel["nummer"], laengen.form_der_szene(ziel), seed=chat_id,
        faktor=laengen.faktor_aus_stand(stand),
    )


def _laenge_text(conn, chat_id: int, ziel) -> str:
    """Block: die Laenge dieser Szene. Leer, solange kein Profil sie waehlt --
    dann faellt er in ``_zusammen`` ersatzlos weg und der Nutzertext bleibt
    zeichengleich."""
    from interview_theater import laengen

    return laengen.block_szene(budget_fuer_szene(conn, chat_id, ziel))
```

`laengen.faktor_aus_stand` kommt aus Aufgabe 9. **Bis dahin** steht dort
`faktor=1.0`; Aufgabe 9 tauscht es.

- [x] **Schritt 4: Den Block einhaengen**

In `interview_theater/szene.py`:

```python
_REIHENFOLGE = (
    # "laenge" steht direkt hinter "aufgabe" und damit im nie gekuerzten
    # Teil (30.09.2026, Karte R): eine Laengenvorgabe, die die
    # Kuerzungsleiter wegwerfen darf, ist keine.
    "format_rahmen", "aufgabe", "laenge", "thema", "kernpaket", "figuren",
    "continuity", "verworfen", "chat", "diese_szene", "auftrag",
)
```

und in `_bloecke` innerhalb von `baue_nutzertext`, hinter `"aufgabe"`:

```python
            "laenge": _laenge_text(conn, chat_id, ziel),
```

Im Docstring von `baue_nutzertext` die Blockliste um "die Laenge dieser
Szene" ergaenzen und in der Aufzaehlung "Nie gekuerzt werden ..." das Wort
`Laenge` aufnehmen.

- [x] **Schritt 5: `art` durchreichen**

Drei Signaturen, jede mit Vorgabewert -- **kein** bestehender Aufrufer aendert
sich:

```python
def schreibe(conn, tg, klm, e, chat_id: int, auftrag: str,
             art: str = ART) -> int:
    """... (bestehender Docstring bleibt) ...

    ``art`` (30.09.2026, Karte R) landet in der Tabelle ``aufruf``. Der
    Nachpass setzt ``szene_nachpass``, damit sich seine Laeufe getrennt zaehlen
    lassen -- wie ``dramaturgie_b1`` es vormacht. Ohne Angabe bleibt es
    ``ART``."""
```

Darin die beiden Aufrufstellen (`szene.py:2076` und `:2081`) von `ART` auf
`art` umstellen. Achtung: `szene.py:2018` (`(ART, chat_id)`) ist eine **andere
Stelle** -- eine Abfrage auf frueher gestellte Aufrufe -- und bleibt `ART`.

```python
def _lauf(conn, tg, klm, e, chat_id: int, auftrag: str,
          sperre: threading.Lock, art: str = ART) -> None:
        ...
        schreibe(conn, tg, klm, e, chat_id, auftrag, art=art)


def starte(conn, tg, klm, e, chat_id: int, auftrag: str,
           art: str = ART) -> threading.Thread | None:
        ...
    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, auftrag, sperre, art),
        daemon=True,
    )
```

- [x] **Schritt 6: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_szene.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_szene.py tests/test_kuerzung.py tests/test_prompt_audit.py tests/test_dramaturgie_schleife.py`
Erwartet: `passed`, kein `failed`. Diese vier sind die Waechter: sie fahren
`szene.schreibe`/`starte` und messen den Nutzertext.

- [x] **Schritt 7: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/szene.py tests/test_laengen_szene.py
git commit -m "Phase 7: Laengenblock im nie gekuerzten Teil, art als Parameter (R)"
```

---

## Aufgabe 9: Uebersteuerung I -- der Faktor an den Kuerzen-Weg angeschlossen

**Files:**
- Modify: `interview_theater/db.py` (`SCHEMA`, Tabelle `arbeitsstand`)
- Modify: `interview_theater/repo.py` (`_ARBEITSSTAND_FELDER`)
- Modify: `interview_theater/laengen.py` (`FELD_FAKTOR`, `faktor_aus_stand`)
- Modify: `interview_theater/kuerzung.py` (`starte` setzt den Faktor)
- Modify: `interview_theater/szene.py` und
  `interview_theater/kurzgeschichte.py` (die `1.0`-Platzhalter aus Aufgabe 7/8
  gegen den echten Faktor tauschen)
- Test: `tests/test_laengen_faktor.py` (neu)

**Wo der Faktor liegt, und warum.** In einer **neuen Spalte**
`arbeitsstand.laengen_faktor` (TEXT, wie `figuren_anzahl`), additiv ueber
`db._migriere_fehlende_spalten`. Begruendung gegen die beiden Alternativen:

- **`festlegung` (Bereich `stil`)** waere die bestehende Tabelle, aber ihr
  Inhalt ist **Freitext fuer den Prompt**. Einen Faktor daraus zu lesen hiesse,
  denselben Wert zweimal zu fuehren: einmal als Satz fuers Modell, einmal als
  Zahl fuer den Code. Genau die "doppelte Wahrheit", gegen die
  `repo.FESTLEGUNG_BEREICHE` ausdruecklich gebaut ist.
- **Kein Speichern, sondern jedes Mal neu entscheiden** ginge nicht: die
  Gruppe sagt einmal "kuerzer", und danach sollen **alle kommenden** Szenen
  kuerzer geplant werden. Das ist ein Zustand.

**Interfaces:**
- Produces:
  - `db.SCHEMA` hat `arbeitsstand.laengen_faktor TEXT`
  - `repo._ARBEITSSTAND_FELDER` enthaelt `"laengen_faktor"`
  - `laengen.FELD_FAKTOR = "laengen_faktor"`
  - `laengen.faktor_aus_stand(stand) -> float`
  - `laengen.setze_faktor(conn, chat_id, faktor) -> None`
  - `kuerzung.starte` setzt bei `nummer is None` den Faktor auf
    `laengen.kurz_faktor()` -- **nur bei aktivem Profil und nur, wenn ein Lauf
    wirklich gestartet ist**.

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_faktor.py`

```python
"""Die Uebersteuerung: "Kuerzer/Instagram" als dauerhafter Faktor
(30.09.2026, Karte R).

Der Faktor ist ein ZUSTAND: die Gruppe sagt einmal "kuerzer", und danach
werden alle kommenden Szenen kuerzer geplant. Deshalb eine Spalte im
Arbeitsstand und keine Festlegung -- eine Festlegung ist Freitext fuer den
Prompt, und derselbe Wert zweimal zu fuehren waere die doppelte Wahrheit,
gegen die ``repo.FESTLEGUNG_BEREICHE`` gebaut ist.
"""

import pytest

from interview_theater import (
    db, kuerzung, kurzgeschichte, laengen, phasen, repo, szene, workshop,
)

from test_knoepfe import TelegramAttrappe
from test_laengen_prosa import ProsaAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Die Spalte -----------------------------------------------------------


def test_die_spalte_steht_im_schema(conn):
    spalten = {z["name"] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    assert laengen.FELD_FAKTOR in spalten


def test_eine_alte_datenbank_bekommt_die_spalte_nachgeruestet(tmp_path):
    """Additiv ueber ``_migriere_fehlende_spalten``: im Betrieb laufen vier
    Bots auf denselben Dateien, ein Schema-Neubau kostet den Workshop."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    c.execute(f"ALTER TABLE arbeitsstand DROP COLUMN {laengen.FELD_FAKTOR}")
    c.commit()
    c.close()
    c2 = db.verbinde(pfad)
    db.initialisiere(c2)
    spalten = {z["name"] for z in c2.execute("PRAGMA table_info(arbeitsstand)")}
    assert laengen.FELD_FAKTOR in spalten


def test_der_schreibweg_ist_der_vorhandene(conn):
    """``repo.setze_arbeitsstand`` und kein eigenes SQL -- sonst waere es ein
    zweiter Schreibweg fuer denselben Wert."""
    laengen.setze_faktor(conn, 1, 0.25)
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand[laengen.FELD_FAKTOR] == "0.25"


# --- Der gelesene Faktor --------------------------------------------------


def test_ohne_faktor_gilt_eins(conn):
    assert laengen.faktor_aus_stand(None) == 1.0
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


def test_ein_gesetzter_faktor_wird_gelesen(conn):
    laengen.setze_faktor(conn, 1, 0.25)
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 0.25


def test_ein_unsinniger_faktor_gilt_als_keiner(conn):
    """Nachsichtig wie alle Leser dieses Moduls: ein kaputter Wert darf keinen
    Lauf mitnehmen. 0 oder negativ waere eine Szene ohne Woerter, ueber 1 waere
    eine Verlaengerung -- beides ist keine Uebersteuerung."""
    for wert in ("0", "-1", "2", "keine Ahnung", ""):
        repo.setze_arbeitsstand(conn, 1, laengen.FELD_FAKTOR, wert)
        assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


# --- Der Anschluss an den Kuerzen-Weg ------------------------------------


@pytest.fixture
def prosa6(conn, padua):
    """Phase 6, zwei Abschnitte mit Prosa -- der Stand nach einem Prosalauf."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Streit")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.aktualisiere_szene(conn, szene_id, titel, "kurz", None,
                                "passiert", prosa="Ein langer Text. " * 50)
    phasen.setze(conn, 1, 6, "test")
    return conn


def test_kuerzen_der_ganzen_geschichte_setzt_den_faktor(prosa6, tg, einst):
    """"Kuerzer (25 %)" unter der ganzen Geschichte ist die
    Instagram-Entscheidung: sie gilt fuer alles, was danach kommt."""
    klm = ProsaAttrappe()
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == 1.0
    _meldung, gestartet = kuerzung.starte(prosa6, tg, klm, einst, 1)
    assert gestartet is True
    assert kurzgeschichte._sperre_fuer(1).acquire(timeout=20)
    kurzgeschichte._sperre_fuer(1).release()
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == \
        laengen.kurz_faktor()


def test_kuerzen_EINER_szene_setzt_den_faktor_nicht(prosa6, tg, einst):
    """OFFENE FRAGE 3 im Plan, geplante Variante: eine Entscheidung ueber eine
    Szene ist keine ueber alle."""
    klm = ProsaAttrappe()
    _meldung, gestartet = kuerzung.starte(prosa6, tg, klm, einst, 1, nummer=1)
    assert kurzgeschichte._sperre_fuer(1).acquire(timeout=20) or True
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == 1.0


def test_ohne_lauf_kein_faktor(conn, padua, tg, einst):
    """Gibt es nichts zu kuerzen, gibt es keinen Lauf -- und dann auch keine
    Entscheidung. ``kuerzung.starte`` liefert ``gestartet = False``."""
    klm = ProsaAttrappe()
    meldung, gestartet = kuerzung.starte(conn, tg, klm, einst, 1)
    assert gestartet is False
    assert meldung == kuerzung.TEXT_NICHTS_ZU_KUERZEN
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


def test_ohne_aktives_profil_wird_kein_faktor_gesetzt(prosa6, tg, einst, monkeypatch):
    """Dortmund: der Kuerzen-Weg bleibt genau, was er war."""
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    klm = ProsaAttrappe()
    kuerzung.starte(prosa6, tg, klm, einst, 1)
    assert kurzgeschichte._sperre_fuer(1).acquire(timeout=20)
    kurzgeschichte._sperre_fuer(1).release()
    stand = repo.hole_arbeitsstand(prosa6, 1)
    assert (stand[laengen.FELD_FAKTOR] or "") == ""


def test_der_faktor_wirkt_auf_das_naechste_budget(prosa6, padua):
    ziel_vorher = kurzgeschichte.budget_eintraege(prosa6, 1)
    laengen.setze_faktor(prosa6, 1, 0.25)
    ziel_nachher = kurzgeschichte.budget_eintraege(
        prosa6, 1, faktor=laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)),
    )
    assert [b for _n, _f, b in ziel_nachher] != [b for _n, _f, b in ziel_vorher]
```

Hinweis: `ALTER TABLE ... DROP COLUMN` gibt es in SQLite ab 3.35. Liefert die
mitgelieferte Bibliothek den Fehler `near "DROP"`, wird der Test stattdessen
mit einer von Hand angelegten Alt-Tabelle gebaut (`CREATE TABLE arbeitsstand
(chat_id INTEGER PRIMARY KEY)` in einer frischen Datei, dann
`db.initialisiere`) -- die Aussage bleibt dieselbe. Erst pruefen:
`$PY -c "import sqlite3; print(sqlite3.sqlite_version)"`.

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_faktor.py`
Erwartet: FAIL, `AttributeError: ... has no attribute 'FELD_FAKTOR'`.

- [x] **Schritt 3: Die Spalte anlegen**

In `interview_theater/db.py`, in `CREATE TABLE IF NOT EXISTS arbeitsstand`,
**vor** der schliessenden Klammer:

```sql
  -- Der Laengen-Faktor der Gruppe (30.09.2026, Karte R). Gesetzt, wenn die
  -- Gruppe "Kuerzer" fuer das GANZE Stueck gedrueckt oder eine Laenge
  -- ausdruecklich genannt hat ("Instagram-Kuerze", Dortmund 06.09.2026):
  -- ein Faktor auf jedes kuenftige Wortbudget, 0,25 heisst ein Viertel.
  -- TEXT wie figuren_anzahl, damit derselbe eine Schreibweg
  -- (repo.setze_arbeitsstand) genuegt und "nicht gesetzt" NULL bleibt.
  -- Additiv nachgeruestet ueber _migriere_fehlende_spalten; ohne aktives
  -- Workshop-Profil liest die Spalte niemand.
  laengen_faktor         TEXT,
```

In `interview_theater/repo.py`, an `_ARBEITSSTAND_FELDER`:

```python
    # Der Laengen-Faktor (30.09.2026, Karte R): derselbe eine Schreibweg wie
    # alles andere im Arbeitsstand.
    "laengen_faktor",
```

- [x] **Schritt 4: Lesen und Schreiben in `laengen.py`**

An `interview_theater/laengen.py` anhaengen:

```python
#: Die Arbeitsstand-Spalte, in der der Faktor steht. EINE Stelle, damit
#: ``repo``, ``kuerzung`` und die Leser denselben Namen meinen.
FELD_FAKTOR = "laengen_faktor"


def faktor_aus_stand(stand: Any) -> float:
    """Der Laengen-Faktor dieser Gruppe -- 1,0, solange keiner gesetzt ist.

    Nachsichtig wie alle Leser dieses Moduls: was keine Zahl in ``(0, 1]``
    ist, gilt als "keiner". 0 oder negativ waere eine Szene ohne Woerter,
    ueber 1 waere eine Verlaengerung -- beides ist keine Uebersteuerung,
    sondern ein Fehler, und ein Fehler darf keinen bezahlten Lauf
    verunstalten."""
    if stand is None:
        return 1.0
    try:
        roh = (stand[FELD_FAKTOR] or "").strip()
    except (KeyError, IndexError, TypeError):
        return 1.0
    if not roh:
        return 1.0
    try:
        wert = float(roh)
    except ValueError:
        log.warning("%s ist keine Zahl (%r) -- nehme 1.0", FELD_FAKTOR, roh)
        return 1.0
    if not 0 < wert <= 1:
        log.warning("%s ausserhalb (0, 1] (%r) -- nehme 1.0", FELD_FAKTOR, wert)
        return 1.0
    return wert


def setze_faktor(conn, chat_id: int, faktor: float) -> None:
    """Schreibt den Faktor -- ueber ``repo.setze_arbeitsstand`` und kein
    eigenes SQL (die Regel des Repos: SQL nur in ``repo`` und ``db``)."""
    from interview_theater import repo

    repo.setze_arbeitsstand(conn, chat_id, FELD_FAKTOR, f"{float(faktor):g}")
```

- [x] **Schritt 5: `kuerzung.starte` anschliessen**

In `interview_theater/kuerzung.py`, **im `nummer is None`-Zweig, nach dem
erfolgreich angestossenen Lauf** (also unmittelbar vor
`return TEXT_GESCHICHTE_GESTARTET, True`):

```python
    # "Kuerzer" unter der GANZEN Geschichte ist die Entscheidung ueber das
    # ganze Stueck -- die Instagram-Kuerze vom 06.09.2026. Sie wird als
    # dauerhafter Faktor gemerkt, damit auch die Szenen, die es noch nicht
    # gibt, kuerzer GEPLANT werden und nicht erst nachtraeglich gekuerzt.
    #
    # Nur hier und nicht im Szenen-Zweig: eine Entscheidung ueber eine Szene
    # ist keine ueber alle (OFFENE FRAGE 3). Und nur bei aktivem Profil --
    # ohne es kennt niemand den Wert, und Dortmund bleibt, was es war. Und
    # nur mit Lauf: gibt es nichts zu kuerzen, gibt es keine Entscheidung.
    from interview_theater import laengen

    if laengen.aktiv():
        laengen.setze_faktor(conn, chat_id, laengen.kurz_faktor())
    return TEXT_GESCHICHTE_GESTARTET, True
```

Der Moduldocstring von `kuerzung.py` bekommt einen Absatz dazu:

```
**Was hier seit dem 30.09.2026 zusaetzlich passiert** (Karte R, nur bei
aktivem Laengen-Profil): das "Kuerzer" unter der GANZEN Geschichte merkt
seinen Faktor im Arbeitsstand (``laengen.setze_faktor``). Damit werden auch
die Szenen, die es noch nicht gibt, kuerzer **geplant** -- statt sie erst zu
schreiben und dann zu kuerzen, was einen Lauf kostet. Das "Kuerzer" unter
EINER Szene tut das bewusst nicht.
```

- [x] **Schritt 6: Die `1.0`-Platzhalter tauschen**

In `interview_theater/szene.py` (`budget_fuer_szene`) und
`interview_theater/kurzgeschichte.py` (`schreibe`, Hilfsfunktion `_faktor`)
die aus Aufgabe 7/8 stehengebliebenen `1.0` gegen den echten Wert tauschen:

```python
# interview_theater/kurzgeschichte.py
def _faktor(conn, chat_id: int) -> float:
    """Der Laengen-Faktor der Gruppe, oder 1,0. Eine Zeile, aber an zwei
    Stellen gebraucht (Nutzertext und Journalzeile) -- und zweimal gelesen
    waeren zwei Wahrheiten."""
    from interview_theater import laengen

    return laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, chat_id))
```

In `szene.budget_fuer_szene` steht der Aufruf bereits als
`faktor=laengen.faktor_aus_stand(stand)` -- dort entfaellt nur der
`# Aufgabe 9`-Kommentar.

Kontrollsuche, dass kein Platzhalter stehenblieb:
Run: `grep -n "Aufgabe 9" interview_theater/*.py`
Erwartet: keine Ausgabe.

- [x] **Schritt 7: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_faktor.py`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_db.py tests/test_repo.py tests/test_kuerzung.py tests/test_web.py tests/test_simulation_skript.py`
Erwartet: `passed`, kein `failed`. Die letzten drei sind die Waechter gegen
Nebenwirkungen einer neuen Arbeitsstand-Spalte.

- [x] **Schritt 8: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/db.py interview_theater/repo.py \
        interview_theater/laengen.py interview_theater/kuerzung.py \
        interview_theater/szene.py interview_theater/kurzgeschichte.py \
        tests/test_laengen_faktor.py
git commit -m "Uebersteuerung: laengen_faktor im Arbeitsstand, gesetzt vom Kuerzen der ganzen Geschichte (R)"
```

---

## Aufgabe 10: Uebersteuerung II -- eine ausdrueckliche Laengenansage schlaegt den Wuerfel

**Files:**
- Modify: `interview_theater/laengen.py` (`woerter_aus_festlegungen`,
  `budget_mit_ansage`)
- Modify: `interview_theater/szene.py` (`budget_fuer_szene` liest die
  Festlegungen)
- Modify: `interview_theater/kurzgeschichte.py` (`budget_eintraege` ebenso)
- Test: `tests/test_laengen_ansage.py` (neu)

**Warum keine neue Erkenner-Art.** Am Prompt geprueft: `prompts/erkenner.md`
Punkt 23 grenzt `szene_kuerzen` ausdruecklich gegen die dauerhafte
Laengenvorgabe ab -- *"nicht szene_kuerzen: 'hoechstens eine Seite pro Szene ab
jetzt'"* -- und weist sie `festlegung_setzen` zu (Korpusfall `fl04`). Und
`repo.FESTLEGUNG_BEREICHE` nennt den Bereich `stil` woertlich "Stil- und
**Laengen**vorgaben fuer Texte". Der Weg ist also schon gebaut und getestet.
Eine neue Art brauchte neue Korpusfaelle und einen **bezahlten** Korpuslauf mit
FP = 0 -- fuer einen Fall, der bereits ankommt.

Was fehlt, ist allein, dass der **Code** die Zahl aus so einer Festlegung
liest. Das ist ein deterministischer Regexschritt, kein Modellaufruf.

**Interfaces:**
- Produces:
  - `laengen.BEREICH_ANSAGE = "stil"`
  - `laengen.WOERTER_JE_SEITE = 250`
  - `laengen.woerter_aus_festlegungen(zeilen) -> int | None`
  - `laengen.budget_mit_ansage(budget: int, ansage: int | None) -> int`

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_ansage.py`

```python
"""Eine ausdrueckliche Laengenansage der Gruppe schlaegt den Wuerfel
(30.09.2026, Karte R).

Der Weg ist der vorhandene: die Erkenner-Art ``festlegung_setzen`` im Bereich
``stil`` -- ``prompts/erkenner.md`` Punkt 23 weist "hoechstens eine Seite pro
Szene ab jetzt" ausdruecklich dorthin (Korpusfall fl04), und
``repo.FESTLEGUNG_BEREICHE`` nennt den Bereich woertlich "Stil- und
Laengenvorgaben fuer Texte". Neu ist allein, dass der CODE die Zahl daraus
liest -- deterministisch, ohne Modell, ohne neue Erkenner-Art und damit ohne
bezahlten Korpuslauf.
"""

import pytest

from interview_theater import kurzgeschichte, laengen, repo, szene, workshop


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Die Zahl aus der Festlegung -----------------------------------------


class Zeile(dict):
    """Eine Festlegungszeile, wie ``repo.festlegungen`` sie liefert."""


def _z(bereich, text):
    return Zeile(bereich=bereich, bezug=None, text=text)


@pytest.mark.parametrize("text, soll", [
    ("hoechstens 120 Woerter pro Szene ab jetzt", 120),
    ("maximal 300 words per scene", 300),
    ("jede Szene hoechstens eine Seite", laengen.WOERTER_JE_SEITE),
    ("at most one page per scene", laengen.WOERTER_JE_SEITE),
    ("hoechstens zwei Seiten je Szene", 2 * laengen.WOERTER_JE_SEITE),
])
def test_eine_ansage_wird_gelesen(text, soll):
    assert laengen.woerter_aus_festlegungen([_z("stil", text)]) == soll


@pytest.mark.parametrize("text", [
    # Keine Laengenansage, sondern eine Stilvorgabe.
    "kurze, harte Saetze, kein Pathos",
    # Eine Zahl, aber keine Laenge.
    "drei Figuren pro Szene",
    "Szene 3 soll kuerzer werden",
    "shorter, please",
    # Eine Laenge fuer etwas anderes.
    "das Interview hoechstens 20 Minuten",
    "",
])
def test_was_keine_ansage_ist_wird_nicht_gelesen(text):
    """Im Zweifel keine Ansage: eine falsch gelesene Zahl wuerde jede Szene
    des Stuecks auf eine erfundene Laenge zwingen -- teurer als eine
    uebersehene Bitte, die die Gruppe wiederholen kann."""
    assert laengen.woerter_aus_festlegungen([_z("stil", text)]) is None


def test_nur_der_bereich_stil_zaehlt():
    """Ein anderer Bereich ist ein anderes Thema. "hoechstens 120 Woerter" im
    Bereich ``figur`` ist die Beschreibung einer Figur, keine Szenenlaenge."""
    assert laengen.woerter_aus_festlegungen(
        [_z("figur", "hoechstens 120 Woerter pro Szene")]) is None


def test_die_jueengste_ansage_gewinnt():
    """``repo.festlegungen`` liefert **aelteste zuerst**. Sagt die Gruppe
    zweimal etwas, gilt das Letzte -- eine Festlegung ist ein Zustand."""
    assert laengen.woerter_aus_festlegungen([
        _z("stil", "hoechstens 400 Woerter pro Szene"),
        _z("stil", "hoechstens 120 Woerter pro Szene"),
    ]) == 120


def test_ohne_festlegungen_gibt_es_keine_ansage():
    assert laengen.woerter_aus_festlegungen([]) is None
    assert laengen.woerter_aus_festlegungen(None) is None


# --- Die Ansage schlaegt den Wuerfel --------------------------------------


def test_die_ansage_deckelt_das_budget():
    """"Hoechstens" heisst hoechstens: der Wuerfel darf darunter bleiben
    (Rhythmus!), aber nie darueber. Sonst waere eine ausdrueckliche Ansage
    weniger wert als ein Muster."""
    assert laengen.budget_mit_ansage(450, 120) == 120
    assert laengen.budget_mit_ansage(100, 120) == 100
    assert laengen.budget_mit_ansage(450, None) == 450


def test_die_ansage_unterschreitet_nie_die_mindestlaenge():
    assert laengen.budget_mit_ansage(450, 5) == laengen.MINDEST_WOERTER


def test_die_ansage_wirkt_im_szenenbudget(conn, padua):
    ziel_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, ziel_id, "form", "dialog")
    ziel = repo.hole_szene(conn, ziel_id)
    ohne = szene.budget_fuer_szene(conn, 1, ziel)
    repo.schreibe_festlegung(conn, 1, "stil",
                             "hoechstens 120 Woerter pro Szene ab jetzt")
    mit = szene.budget_fuer_szene(conn, 1, ziel)
    assert ohne > 120
    assert mit == 120


def test_die_ansage_wirkt_in_den_prosa_eintraegen(conn, padua):
    for nummer in (1, 2):
        repo.stelle_szene_sicher(conn, 1, nummer)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 90 Woerter pro Szene")
    eintraege = kurzgeschichte.budget_eintraege(conn, 1)
    assert [b for _n, _f, b in eintraege] == [90, 90]


def test_ansage_und_faktor_wirken_beide(conn, padua):
    """Der Faktor verkuerzt den Wuerfel, die Ansage deckelt das Ergebnis --
    die Reihenfolge ist festgelegt und getestet, damit nicht zwei Lesarten
    entstehen."""
    repo.stelle_szene_sicher(conn, 1, 1)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 120 Woerter pro Szene")
    laengen.setze_faktor(conn, 1, 0.25)
    eintraege = kurzgeschichte.budget_eintraege(
        conn, 1, faktor=laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)),
    )
    # Erst Faktor (Dialog 200-450 -> 50-110), dann Deckel 120: der Deckel
    # greift hier nicht mehr, weil der Faktor schon darunter liegt.
    assert all(b <= 120 for _n, _f, b in eintraege)
    assert all(b >= laengen.MINDEST_WOERTER for _n, _f, b in eintraege)


def test_ohne_aktives_profil_wird_keine_ansage_gelesen(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.stelle_szene_sicher(conn, 1, 1)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 120 Woerter pro Szene")
    assert kurzgeschichte.budget_eintraege(conn, 1) == []
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_ansage.py`
Erwartet: FAIL, `AttributeError: ... has no attribute 'WOERTER_JE_SEITE'`.

- [x] **Schritt 3: Die Ansage lesen**

An `interview_theater/laengen.py` anhaengen:

```python
#: Der Bereich, in dem eine Laengenansage der Gruppe landet.
#: ``repo.FESTLEGUNG_BEREICHE`` nennt ihn woertlich "Stil- und
#: Laengenvorgaben fuer Texte", und ``prompts/erkenner.md`` Punkt 23 weist
#: "hoechstens eine Seite pro Szene ab jetzt" ausdruecklich dorthin
#: (Korpusfall fl04). Deshalb **keine** neue Erkenner-Art: der Weg ist
#: gebaut, gemessen und kostet keinen weiteren Korpuslauf.
BEREICH_ANSAGE = "stil"

#: Wie viele Woerter eine "Seite" ist. Eine Zahl, damit "hoechstens eine
#: Seite" ueberhaupt eine Zahl werden kann -- eine Manuskriptseite mit
#: doppeltem Zeilenabstand traegt rund 250 Woerter.
WOERTER_JE_SEITE = 250

#: Zahlwoerter, die in einer Seitenangabe vorkommen. Nur bis fuenf: "zwoelf
#: Seiten pro Szene" ist keine Kuerzungsansage mehr.
_ZAHLWOERTER = {
    "eine": 1, "einer": 1, "one": 1, "a": 1, "zwei": 2, "two": 2,
    "drei": 3, "three": 3, "vier": 4, "four": 4, "fuenf": 5, "five": 5,
}

#: "hoechstens 120 Woerter [je|pro] Szene". Eng: die Einheit muss ein Wort
#: sein, und der Bezug muss die Szene (bzw. der Abschnitt) sein -- sonst
#: laese "das Interview hoechstens 20 Minuten" wie eine Szenenlaenge.
_ANSAGE_WOERTER = re.compile(
    r"\b(?:hoechstens|höchstens|maximal|max\.?|nicht mehr als|at most|no more "
    r"than|maximum(?: of)?|up to)\s+(\d{2,4})\s*"
    r"(?:woerter|wörter|words)\b[^.;]{0,20}?"
    r"\b(?:szene|szenen|scene|scenes|abschnitt|abschnitte|section|sections)\b",
    re.IGNORECASE,
)

#: Dieselbe Form mit "Seite" statt "Woerter", Zahl oder Zahlwort.
_ANSAGE_SEITEN = re.compile(
    r"\b(?:hoechstens|höchstens|maximal|max\.?|nicht mehr als|at most|no more "
    r"than|maximum(?: of)?|up to)?\s*"
    r"(\d{1,2}|eine|einer|zwei|drei|vier|fuenf|one|a|two|three|four|five)\s*"
    r"(?:seite|seiten|page|pages)\b[^.;]{0,20}?"
    r"\b(?:szene|szenen|scene|scenes|abschnitt|abschnitte|section|sections)\b",
    re.IGNORECASE,
)

#: Und die umgekehrte Wortstellung ("jede Szene hoechstens eine Seite").
_ANSAGE_UMGEKEHRT = re.compile(
    r"\b(?:szene|szenen|scene|scenes|abschnitt|abschnitte|section|sections)\b"
    r"[^.;]{0,30}?"
    r"(?:hoechstens|höchstens|maximal|max\.?|at most|no more than|up to)\s+"
    r"(\d{1,4}|eine|einer|zwei|drei|vier|fuenf|one|a|two|three|four|five)\s*"
    r"(seite|seiten|page|pages|woerter|wörter|words)\b",
    re.IGNORECASE,
)


def _zahl_oder_wort(roh: str) -> int | None:
    roh = (roh or "").strip().lower()
    if roh.isdigit():
        return int(roh)
    return _ZAHLWOERTER.get(roh)


def _ansage_einer_zeile(text: str) -> int | None:
    """Die Wortzahl aus EINER Festlegungszeile, oder None.

    Auf **"im Zweifel keine Ansage"** kalibriert, wie ``szene_schreiben`` und
    ``entfernen`` beim Erkenner: eine falsch gelesene Zahl zwingt jede Szene
    des Stuecks auf eine erfundene Laenge, eine uebersehene Bitte wiederholt
    die Gruppe."""
    treffer = _ANSAGE_WOERTER.search(text or "")
    if treffer is not None:
        return int(treffer.group(1))
    treffer = _ANSAGE_SEITEN.search(text or "")
    if treffer is not None:
        seiten = _zahl_oder_wort(treffer.group(1))
        if seiten and 1 <= seiten <= 5:
            return seiten * WOERTER_JE_SEITE
    treffer = _ANSAGE_UMGEKEHRT.search(text or "")
    if treffer is not None:
        zahl = _zahl_oder_wort(treffer.group(1))
        einheit = treffer.group(2).lower()
        if not zahl:
            return None
        if einheit.startswith(("seite", "page")):
            return zahl * WOERTER_JE_SEITE if 1 <= zahl <= 5 else None
        return zahl if zahl >= 10 else None
    return None


def woerter_aus_festlegungen(zeilen: Iterable[Any] | None) -> int | None:
    """Die ausdrueckliche Laengenansage der Gruppe, oder None.

    Gelesen werden nur Zeilen im Bereich ``BEREICH_ANSAGE``. **Die jueengste
    gewinnt**: ``repo.festlegungen`` liefert aelteste zuerst, und eine
    Festlegung ist ein Zustand -- sagt die Gruppe zweimal etwas, gilt das
    Letzte.

    Kein Modellaufruf, reine Regexarbeit."""
    ergebnis: int | None = None
    for zeile in zeilen or ():
        try:
            bereich = (zeile["bereich"] or "").strip().lower()
            text = zeile["text"] or ""
        except (KeyError, IndexError, TypeError):
            continue
        if bereich != BEREICH_ANSAGE:
            continue
        wert = _ansage_einer_zeile(text)
        if wert is not None:
            ergebnis = wert
    return ergebnis


def budget_mit_ansage(budget: int, ansage: int | None) -> int:
    """Die Ansage **deckelt** das gewuerfelte Budget.

    "Hoechstens" heisst hoechstens: der Wuerfel darf darunter bleiben -- das
    ist der Rhythmus, und den soll eine Obergrenze nicht platt machen --, aber
    nie darueber. Andernfalls waere eine ausdrueckliche Bitte der Gruppe
    weniger wert als ein Muster aus einer TOML-Datei."""
    if ansage is None:
        return int(budget)
    return max(min(int(budget), int(ansage)), MINDEST_WOERTER)
```

`Iterable` steht schon im `typing`-Import des Moduls (Aufgabe 2).

- [x] **Schritt 4: Die beiden Budget-Wege anschliessen**

In `interview_theater/szene.py`, `budget_fuer_szene`:

```python
    stand = repo.hole_arbeitsstand(conn, chat_id)
    budget = laengen.budget_fuer(
        ziel["nummer"], laengen.form_der_szene(ziel), seed=chat_id,
        faktor=laengen.faktor_aus_stand(stand),
    )
    # Erst der Faktor (im Wuerfel), dann der Deckel: eine ausdrueckliche
    # Ansage der Gruppe ist eine Obergrenze und keine Zielzahl.
    return laengen.budget_mit_ansage(
        budget, laengen.woerter_aus_festlegungen(repo.festlegungen(conn, chat_id)),
    )
```

In `interview_theater/kurzgeschichte.py`, `budget_eintraege`, hinter
`werte = laengen.budgets(...)`:

```python
    ansage = laengen.woerter_aus_festlegungen(repo.festlegungen(conn, chat_id))
    werte = [laengen.budget_mit_ansage(w, ansage) for w in werte]
```

- [x] **Schritt 5: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_ansage.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Schlaegt ein Negativfall an (ein Muster feuert, wo es nicht soll), wird **das
Muster enger gemacht**, nicht der Testfall geloescht: "im Zweifel keine
Ansage" ist die Kalibrierung, und ein Falsch-Positiv hier zwingt jede Szene
des Stuecks auf eine erfundene Laenge.

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_festlegung.py tests/test_festlegung_erkenner.py tests/test_korpus.py`
Erwartet: `passed`, kein `failed` -- der Beweis, dass **keine** Erkenner-Art
dazugekommen ist und der Korpus unberuehrt bleibt.

- [x] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/laengen.py interview_theater/szene.py \
        interview_theater/kurzgeschichte.py tests/test_laengen_ansage.py
git commit -m "Uebersteuerung: Laengenansage aus festlegung/stil deckelt das Budget, ohne neue Erkenner-Art (R)"
```

---

## Aufgabe 11: `sprachpass.py` I -- die vier Zaehler

**Files:**
- Create: `interview_theater/sprachpass.py`
- Test: `tests/test_sprachpass.py` (neu)

**Was gezaehlt wird, und warum genau das.** Die vier Muster stehen in der
Karte, und drei davon haben schon einen Eintrag in
`interview_theater/prompts/theater-tells.md`: die rhetorische Dreierfigur
(Nr. 13), der Themensatz, der die Szene ankuendigt (Nr. 19), Fazit und Moral
(Nr. 3 und 4). Die Negativliste steht **praeventiv** im Schreib-Prompt -- und
die Messung am Dortmunder Text vom 06.09. zeigt, dass das nicht genuegt: Birk
hat von Hand nachbearbeitet. Ein Zaehler **nach** dem Lauf ist die fehlende
Haelfte.

**Was vor dem Zaehlen weggeraeumt wird.** `entkleide` entfernt
Sprecherkoepfe (`NAME:` am Zeilenanfang) und Regieanweisungen (runde
Klammern) -- dieselbe Abgrenzung wie in `sprecher.py`, aber eine eigene
Funktion: `sprecher` bestimmt einen **Sprecher** und verlangt dafuer einen
Namen, hier wird nur Text entfernt. Das ist die Falle, gegen die es gebaut
ist: `(a table, a chair, and a lamp)` in einer Regieanweisung ist eine
Requisitenliste und keine Adjektiv-Dreierkette.

**Einheiten:** drei Zaehler je 1.000 Woerter, der Fazitsatz je Text. Die
Einheit steht im Schluesselnamen (`gedankenstriche_je_1000`,
`fazitsatz_je_text`), damit sie niemand raten muss.

**Interfaces:**
- Consumes: `sprache.je_sprache` (A1), `laengen.zaehle_woerter`.
- Produces:
  - `sprachpass.entkleide(text: str) -> str`
  - `sprachpass.MUSTER_GEDANKENSTRICH`, `MUSTER_NICHT_SONDERN_DE/_EN`,
    `MUSTER_DREIER_DE/_EN`, `MUSTER_FAZIT_DE/_EN`, `FAZIT_FENSTER_SAETZE = 2`
  - `sprachpass.NAMEN = ("gedankenstriche", "nicht_sondern", "adjektiv_dreier", "fazitsatz")`
  - `sprachpass.zaehle(text: str, code: str | None = None) -> dict[str, float]`
    (Werte: die ersten drei je 1.000 Woerter als float, `fazitsatz` als
    absolute Zahl)
  - `sprachpass.rohzahlen(text: str, code=None) -> dict[str, int]`
    (die unskalierten Treffer -- fuer den Befund)

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_sprachpass.py`

```python
"""Der letzte Sprachpass: vier mechanisch gezaehlte Muster (30.09.2026, Karte R).

Kein Modell, kein Netz. Je Muster mindestens drei Positiv- und drei
Negativfaelle, und die Negativfaelle sind die eigentliche Arbeit: eine
Requisitenliste in einer Regieanweisung, ein Bindestrich-Kompositum, ein
Sprecherkopf und ein "but" als gewoehnliche Konjunktion duerfen nicht feuern.
Ein falscher Befund kostet einen bezahlten Lauf und Vertrauen; ein fehlender
kostet eine Gelegenheit.

Das Material ist erfunden.
"""

import pytest

from interview_theater import sprachpass


# --- entkleide ------------------------------------------------------------


def test_entkleide_nimmt_sprecherkoepfe_und_regie():
    text = "MIRA: (steht auf, sehr langsam) Nein.\nPAL: Doch."
    ohne = sprachpass.entkleide(text)
    assert "MIRA:" not in ohne
    assert "steht auf" not in ohne
    assert "Nein." in ohne and "Doch." in ohne


def test_entkleide_laesst_prosa_stehen():
    """Phase 6 ist Prosa ohne Sprecherkoepfe -- dort darf nichts wegfallen."""
    text = "Sie steht am Fenster und wartet. Der Kanal liegt still."
    assert sprachpass.entkleide(text) == text


def test_entkleide_nimmt_auch_die_kopfzeilen_des_szenenformats():
    """``TITEL:``, ``ZUSAMMENFASSUNG:`` und ``ANDERS GEMACHT:`` sind
    Protokoll und kein Text der Szene -- sie duerfen nicht mitgezaehlt
    werden."""
    ohne = sprachpass.entkleide("ZUSAMMENFASSUNG: Sie gehen.\n\nMIRA: Ja.")
    assert "ZUSAMMENFASSUNG" not in ohne


# --- 1. Gedankenstriche ---------------------------------------------------


@pytest.mark.parametrize("text", [
    "She waited—and waited—and waited.",
    "Das war es – jedenfalls fast – gewesen.",
    "Sie kam spaet -- wie immer.",
])
def test_gedankenstriche_positiv(text):
    assert sprachpass.rohzahlen(text)["gedankenstriche"] >= 1, text


@pytest.mark.parametrize("text", [
    # Bindestrich-Kompositum: ein Bindestrich ohne Leerzeichen ist kein
    # Gedankenstrich.
    "a well-known face in the neighbourhood",
    "die Sechzehn-Stunden-Schicht",
    # Listenstrich am Zeilenanfang -- davor steht kein Wortzeichen.
    "- Milch\n- Brot\n- Zucker",
])
def test_gedankenstriche_negativ(text):
    assert sprachpass.rohzahlen(text)["gedankenstriche"] == 0, text


def test_gedankenstriche_werden_je_tausend_woerter_gerechnet():
    """Ein Strich in 2.230 Woertern (Dortmund v2, gemessen) sind 0,45 je
    1.000 -- weit unter dem Grenzwert 6,0. Die Einheit macht den
    Unterschied zwischen "ein Strich" und "Inflation"."""
    text = ("wort " * 999) + "eins—zwei"
    zahl = sprachpass.zaehle(text)["gedankenstriche"]
    assert 0.9 <= zahl <= 1.1, zahl


# --- 2. not X but Y / nicht X, sondern Y ---------------------------------


@pytest.mark.parametrize("text", [
    "It was not a home but a waiting room.",
    "She was not only tired but also angry.",
    "It was not loud, but heavy.",
])
def test_nicht_sondern_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["nicht_sondern"] >= 1, text


@pytest.mark.parametrize("text", [
    # "but" als gewoehnliche Konjunktion nach einer Verneinung.
    "She was not ready but I tried anyway.",
    "He could not hear her. But she stayed.",
    # "nothing but" ist kein Muster.
    "There was nothing but water.",
])
def test_nicht_sondern_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["nicht_sondern"] == 0, text


@pytest.mark.parametrize("text, soll", [
    ("Es war nicht Heimat, sondern Warteraum.", 1),
    ("Sie war nicht muede, sondern wuetend.", 1),
    ("Sie konnte nicht schlafen. Sondern? Nichts.", 0),
])
def test_nicht_sondern_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["nicht_sondern"] == soll, text


# --- 3. Adjektiv-Dreierketten -------------------------------------------


@pytest.mark.parametrize("text", [
    "She was tired, angry, and alone.",
    "It felt cold, wet, empty.",
    "The room seemed smaller, darker, colder.",
])
def test_dreier_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["adjektiv_dreier"] >= 1, text


@pytest.mark.parametrize("text", [
    # Namensliste -- grossgeschrieben.
    "There was John, Mary, and Sue.",
    # Requisitenliste mit Artikel.
    "On the table was a cup, a plate, and a knife.",
    # Aufzaehlung in einer Regieanweisung -- ``entkleide`` raeumt sie weg.
    "MIRA: Ja.\n(Auf dem Tisch: a cup, a plate, and a knife.)",
    # Nur zwei.
    "She was tired and angry.",
])
def test_dreier_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["adjektiv_dreier"] == 0, text


@pytest.mark.parametrize("text, soll", [
    ("Sie war muede, wuetend und allein.", 1),
    ("Es war kalt, nass, leer.", 1),
    ("Da waren Mira, Pal und Nadia.", 0),
])
def test_dreier_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["adjektiv_dreier"] == soll, text


# --- 4. Fazitsatz -------------------------------------------------------


@pytest.mark.parametrize("text", [
    "She closed the door. Maybe home is just where you stop explaining.",
    "He left. We all should listen more.",
    "Nobody moved. That's just how it is.",
])
def test_fazitsatz_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["fazitsatz"] >= 1, text


@pytest.mark.parametrize("text", [
    # Dieselben Worte MITTEN im Text: dort ist es kein Fazit.
    "Maybe home is just where you stop explaining. "
    "She opened the window. Rain came in. He said nothing. She waited.",
    # "Maybe" ohne den Fazit-Bau.
    "Maybe she is late again.",
    # Ein Satz ueber jemanden, der zuhoert -- keine Moral.
    "He listened to everyone in the room.",
])
def test_fazitsatz_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["fazitsatz"] == 0, text


def test_der_fazitsatz_wird_nur_am_schluss_gezaehlt():
    """Das ist der ganze Unterschied zwischen einer Floskel und einer Moral:
    die Stelle. Gezaehlt wird in den letzten ``FAZIT_FENSTER_SAETZE`` Saetzen."""
    schluss = "Maybe home is just where you stop explaining."
    fuellung = " ".join(["She waited."] * 5)
    assert sprachpass.rohzahlen(fuellung + " " + schluss, "en")["fazitsatz"] == 1
    assert sprachpass.rohzahlen(schluss + " " + fuellung, "en")["fazitsatz"] == 0


@pytest.mark.parametrize("text, soll", [
    ("Sie ging. Vielleicht ist Heimat einfach da, wo man nichts erklaert.", 1),
    ("Er schwieg. Wir alle sollten mehr zuhoeren.", 1),
    ("Sie ging. Es regnete.", 0),
])
def test_fazitsatz_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["fazitsatz"] == soll, text


# --- Die Zaehlung als Ganzes --------------------------------------------


def test_alle_namen_kommen_in_der_zaehlung_vor():
    zahlen = sprachpass.zaehle("Ein kurzer Text.", "de")
    assert set(zahlen) == set(sprachpass.NAMEN)


def test_ein_leerer_text_zaehlt_nichts():
    for text in ("", None):
        assert all(v == 0 for v in sprachpass.zaehle(text, "de").values())


def test_die_sprache_kommt_aus_dem_profil(monkeypatch):
    """``sprache.je_sprache`` waehlt die Musterliste; ``code`` ist nur der
    Ueberschreibweg fuer Tests und den Befund."""
    monkeypatch.setattr(sprachpass.sprache, "code", lambda: "en")
    assert sprachpass.rohzahlen("It was not a home but a room.")["nicht_sondern"] >= 1
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass.py`
Erwartet: FAIL, `ModuleNotFoundError: No module named 'interview_theater.sprachpass'`.

- [x] **Schritt 3: `interview_theater/sprachpass.py` anlegen**

```python
"""Der letzte Sprachpass: vier mechanisch gezaehlte Muster (30.09.2026, Karte R).

**Warum es das gibt.** ``interview_theater/prompts/theater-tells.md`` steht
**praeventiv** im Schreib-Prompt und nennt drei dieser Muster schon (Nr. 13
rhetorische Dreierfigur, Nr. 19 Themensatz, Nr. 3/4 Fazit und Moral).
Gemessen hat das nicht genuegt: am 06.09.2026 hat Birk den Gruppentext vor dem
Versand von Hand nachbearbeitet -- Gedankenstrich-Inflation, "nicht X, sondern
Y", Adjektiv-Trippel, Geruestsprache. Eine Negativliste im Prompt ist die
halbe Massnahme; die andere Haelfte ist ein Zaehler **nach** dem Lauf.

**Kein Modell.** Vier Regex-Zaehler. Ein Judge, der Sprache beurteilt,
begruendet jede Note -- auch eine falsche -- und kostet je Szene einen Aufruf;
eine Zaehlung ist nachrechenbar und kostet nichts. Ueberschreitet ein Zaehler
seinen Grenzwert, entsteht daraus eine Regie-Notiz, und **erst die** kostet
einen Lauf (``nachpass.py``).

**Die Negativfaelle sind die Arbeit.** Ein falscher Befund kostet einen
bezahlten Lauf und Vertrauen, ein fehlender nur eine Gelegenheit -- dieselbe
Kalibrierung wie beim Sprecherzeilen-Parser in ``dramaturgie/mechanik.py``
("erkennt er keine Sprecherzeile, liefert er gar keinen Befund"). Deshalb
raeumt ``entkleide`` erst Sprecherkoepfe und Regieanweisungen weg, und deshalb
sind die Muster eng: ein Bindestrich-Kompositum ist kein Gedankenstrich, eine
Requisitenliste keine Adjektivkette, ein "but" nach einer Verneinung nicht
automatisch "not X but Y".

**Einheiten.** Drei Zaehler rechnen **je 1.000 Woerter** -- ein Strich in
2.230 Woertern (Dortmund v2, gemessen) ist kein Befund, sechs in 1.000 sind
einer. Der Fazitsatz zaehlt **je Text**, weil er positionell gezaehlt wird:
nur in den letzten ``FAZIT_FENSTER_SAETZE`` Saetzen. Die Einheit steht im
Namen des Grenzwerts (``gedankenstriche_je_1000``, ``fazitsatz_je_text``).

**Zwei Sprachen, eine Auswahl.** Die deutschen Muster existieren und sind
getestet; ob der Pass laeuft, entscheidet ``[sprachpass] aktiv`` im Profil --
fuer Dortmund steht er aus.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Sequence

log = logging.getLogger(__name__)

#: Ein Sprecherkopf bzw. eine Protokoll-Kopfzeile am Zeilenanfang: bis zu 40
#: Zeichen ohne Doppelpunkt, dann ein Doppelpunkt. Deckt ``MIRA:``, ``CHOR:``,
#: ``TITEL:``, ``ZUSAMMENFASSUNG:`` und ``ANDERS GEMACHT:`` ab -- alles, was
#: nicht gesprochener Text ist.
_SPRECHERKOPF = re.compile(r"(?m)^[^\n:]{1,40}:")

#: Eine Regieanweisung. Nicht geschachtelt -- wie ``sprecher._KLAMMER``.
_KLAMMER = re.compile(r"\([^()]*\)")

#: Satzgrenzen fuer das Fazit-Fenster. Schlicht und dokumentiert: Punkt,
#: Ausrufe- oder Fragezeichen, dann Leerraum.
_SATZENDE = re.compile(r"(?<=[.!?])\s+")

#: In so vielen Saetzen am Schluss wird der Fazitsatz gesucht. Zwei, weil ein
#: Fazit gern hinter einem letzten Bild steht.
FAZIT_FENSTER_SAETZE = 2

#: Die Namen der vier Zaehler -- EINE Reihenfolge fuer Zaehlung, Grenzwerte,
#: Notiz und Befund.
NAMEN = ("gedankenstriche", "nicht_sondern", "adjektiv_dreier", "fazitsatz")

# --- 1. Gedankenstrich-Inflation ------------------------------------------
#
# Em- und En-Dash zwischen Wortzeichen (``word—word``, die Maschinenform) und
# der ASCII-Doppelstrich mit Leerzeichen (``wort -- wort``, die Schreibweise
# dieses Repos). Ein einzelner Bindestrich ist NICHT dabei: ``well-known``
# waere sonst ein Befund. Und ein Strich am Zeilenanfang auch nicht -- davor
# steht kein Wortzeichen, dort ist es ein Listenpunkt.
MUSTER_GEDANKENSTRICH = re.compile(r"(?<=\w)\s*(?:[—–]|--)\s*(?=\w)")

# --- 2. "not X but Y" / "nicht X, sondern Y" ------------------------------
#
# Eng: zwischen den Haelften steht kein Satzzeichen ausser einem Komma (sonst
# waeren zwei Saetze ein Muster), die erste Haelfte ist kurz, und nach ``but``
# darf kein Subjektpronomen stehen -- "not ready but I tried" ist ein
# gewoehnlicher Nebensatz. ``\bnot\s`` trifft "nothing but" nicht, weil dort
# kein Leerzeichen hinter "not" steht.
MUSTER_NICHT_SONDERN_EN = re.compile(
    r"\bnot\s+(?:just\s+|only\s+|merely\s+|simply\s+)?"
    r"[^,.;:!?()]{2,40},?\s+but\s+(?:also\s+|rather\s+|instead\s+)?"
    r"(?!(?:i|you|he|she|it|we|they|there)\b)\w",
    re.IGNORECASE,
)
MUSTER_NICHT_SONDERN_DE = re.compile(
    r"\bnicht\s+[^,.;:!?()]{2,40},\s*sondern\s+\w", re.IGNORECASE,
)

# --- 3. Adjektiv-Dreierkette ---------------------------------------------
#
# Kopula plus drei kleingeschriebene Woerter ab drei Buchstaben. **Bewusst
# case-sensitiv**: "was John, Mary, and Sue" ist eine Namensliste, und Namen
# sind gross. Ein Artikel faellt an ``{3,}`` heraus ("a cup, a plate" -- "a"
# hat einen Buchstaben), und Requisitenlisten in Regieanweisungen sind von
# ``entkleide`` ohnehin schon weg.
MUSTER_DREIER_EN = re.compile(
    r"\b(?:is|was|are|were|felt|feels|seemed|seems|looked|looks|becomes|became)"
    r"\s+(?:so\s+|very\s+|too\s+|much\s+)?"
    r"[a-z]{3,},\s+[a-z]{3,},\s+(?:and\s+|or\s+)?[a-z]{3,}\b"
)
MUSTER_DREIER_DE = re.compile(
    r"\b(?:ist|war|sind|waren|wirkt|wirkte|klingt|klang|bleibt|blieb|wurde)"
    r"\s+(?:so\s+|sehr\s+|zu\s+)?"
    r"[a-zäöüß]{3,},\s+[a-zäöüß]{3,}\s*,?\s+(?:und\s+|oder\s+)?[a-zäöüß]{3,}\b"
)

# --- 4. Fazit- und Themensatz --------------------------------------------
#
# Nur in den letzten Saetzen gezaehlt: dieselben Worte mitten im Text sind
# eine Floskel, am Schluss sind sie eine Moral (theater-tells 3, 4, 19).
MUSTER_FAZIT_EN = (
    re.compile(r"\b(?:we all|everyone|everybody|people)\s+"
               r"(?:should|must|need to|have to|ought to)\b", re.IGNORECASE),
    re.compile(r"\b(?:maybe|perhaps)\b[^.!?]{0,60}?\b(?:is|are)\s+"
               r"(?:just\s+|simply\s+|really\s+)?(?:about|where|what)\b",
               re.IGNORECASE),
    re.compile(r"\bthat(?:'s|’s| is)\s+(?:just\s+|simply\s+)?(?:how|what)\s+"
               r"(?:it|life|things|we|they)\b", re.IGNORECASE),
)
MUSTER_FAZIT_DE = (
    re.compile(r"\b(?:wir alle|jeder|man)\s+"
               r"(?:sollte|sollten|muss|muessen|müssen)\b", re.IGNORECASE),
    re.compile(r"\bvielleicht\b[^.!?]{0,60}?\bist\s+"
               r"(?:einfach\s+|eben\s+|wirklich\s+)?(?:da|dort|wo|was|das)\b",
               re.IGNORECASE),
    re.compile(r"\bso\s+ist\s+(?:das|es|das leben)\b", re.IGNORECASE),
)


def entkleide(text: str | None) -> str:
    """Sprecherkoepfe und Regieanweisungen weg -- gezaehlt wird, was
    gesprochen wird.

    Dieselbe Abgrenzung wie in ``sprecher.py`` (Kopf am Zeilenanfang bis zum
    Doppelpunkt, Regie in runden Klammern), aber bewusst eine **eigene**
    Funktion: ``sprecher`` bestimmt einen Sprecher und verlangt dafuer einen
    Namen aus der Figurenliste; hier wird nur Text entfernt.

    Das ist die Wache gegen den teuersten Falsch-Positiv: eine
    Requisitenliste in einer Regieanweisung (``(a cup, a plate, and a
    knife)``) ist keine Adjektiv-Dreierkette. Prosa ohne Sprecherkoepfe (Phase
    6) bleibt unveraendert."""
    return _SPRECHERKOPF.sub(" ", _KLAMMER.sub(" ", text or ""))


def _je_sprache(code: str | None, werte: dict[str, Any]) -> Any:
    """``sprache.je_sprache`` mit einem Ueberschreibweg fuer Tests und den
    Befund. Ohne ``code`` entscheidet das aktive Profil."""
    if code:
        return werte.get(code, werte["de"])
    return sprache.je_sprache(werte)


def _saetze(text: str) -> list[str]:
    return [s for s in _SATZENDE.split((text or "").strip()) if s.strip()]


def rohzahlen(text: str | None, code: str | None = None) -> dict[str, int]:
    """Die **unskalierten** Treffer je Muster -- die Zahl, die im Befund
    steht.

    Gezaehlt wird auf dem entkleideten Text. Der Fazitsatz nur in den letzten
    ``FAZIT_FENSTER_SAETZE`` Saetzen: die Stelle ist der ganze Unterschied
    zwischen einer Floskel und einer Moral."""
    nackt = entkleide(text)
    nicht_sondern = _je_sprache(
        code, {"de": MUSTER_NICHT_SONDERN_DE, "en": MUSTER_NICHT_SONDERN_EN})
    dreier = _je_sprache(code, {"de": MUSTER_DREIER_DE, "en": MUSTER_DREIER_EN})
    fazit = _je_sprache(code, {"de": MUSTER_FAZIT_DE, "en": MUSTER_FAZIT_EN})
    schluss = " ".join(_saetze(nackt)[-FAZIT_FENSTER_SAETZE:])
    return {
        "gedankenstriche": len(MUSTER_GEDANKENSTRICH.findall(nackt)),
        "nicht_sondern": len(nicht_sondern.findall(nackt)),
        "adjektiv_dreier": len(dreier.findall(nackt)),
        "fazitsatz": sum(1 for m in fazit if m.search(schluss)),
    }


def zaehle(text: str | None, code: str | None = None) -> dict[str, float]:
    """Die Zahlen, gegen die die Grenzwerte gerechnet werden.

    Die ersten drei **je 1.000 Woerter**, der Fazitsatz als absolute Zahl --
    genau wie die Grenzwerte im Profil heissen
    (``gedankenstriche_je_1000`` / ``fazitsatz_je_text``). Gezaehlt werden die
    Woerter mit ``laengen.zaehle_woerter``: EIN Zaehler fuer Eichung, Budget
    und Sprachpass."""
    from interview_theater import laengen

    roh = rohzahlen(text, code)
    woerter = laengen.zaehle_woerter(entkleide(text))
    je_tausend = (woerter / 1000.0) if woerter else 0.0
    ergebnis: dict[str, float] = {"fazitsatz": float(roh["fazitsatz"])}
    for name in ("gedankenstriche", "nicht_sondern", "adjektiv_dreier"):
        ergebnis[name] = (roh[name] / je_tausend) if je_tausend else 0.0
    return {name: ergebnis[name] for name in NAMEN}


# Der Sprachzugriff steht am Modulende (A1-Konvention K1). Hier wird nur
# ``je_sprache`` gebraucht -- die Nutzertexte dieses Pfads stehen in
# ``nachpass.py``.
from interview_theater import sprache  # noqa: E402
```

Hinweis zur Importreihenfolge: `sprache` wird in `_je_sprache` **zur
Aufrufzeit** gelesen, der Modulimport steht am Ende (A1-Konvention). Faellt
`flake8`/`ruff` darueber, bleibt `# noqa: E402` stehen -- so machen es alle
Module nach A1.

- [x] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Schlaegt ein **Negativfall** an, wird das Muster enger gemacht -- nie der
Testfall geloescht. Schlaegt ein **Positivfall** nicht an, wird das Muster
erweitert und dabei jeder Negativfall erneut gefahren: die Negativfaelle sind
die Zusage, nicht die Positivfaelle.

- [x] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/sprachpass.py tests/test_sprachpass.py
git commit -m "sprachpass.py: vier Regex-Zaehler mit Negativfaellen, ohne Modell (R)"
```

---

## Aufgabe 12: `sprachpass.py` II -- Grenzwerte, Notiz und Zitatschutz

**Files:**
- Modify: `interview_theater/sprachpass.py`
- Modify: `interview_theater/sprachen/en/texte.toml` (`["sprachpass"]`)
- Test: `tests/test_sprachpass_notiz.py` (neu)

**Der Zitatschutz, genau gesagt.** Geprueft wird ueber `zitat.pruefe` -- die
**eine** Normalisierung des Repos, wie es die Regel verlangt. Sie glaettet
Whitespace-Folgen und typografische Anfuehrungszeichen; sie ist damit
*nicht* byte-genau im strengen Sinn, aber genau die Pruefung, an der jedes
Belegzitat in Verdichter, Kernzitaten, Sprachprofil, Schaerfung und
Dramaturgie haengt. Eine zweite, strengere Vergleichsform hier waere ein
zweiter Massstab fuer denselben Begriff -- **das** ist der teurere Fehler. Die
Zusage lautet deshalb praezise: **jedes Zitat, das vor dem Nachpass im Text
stand, steht danach noch darin -- gemessen mit `zitat.pruefe`.** Der Test
heisst entsprechend `test_ein_veraendertes_zitat_faellt_auf`, und der
veraenderte Wortlaut in seiner Attrappe ist eine echte Aenderung, nicht ein
zusaetzliches Leerzeichen.

**Interfaces:**
- Consumes: `zitat.pruefe`, `repo.gepruefte_themen`, `repo.figuren`,
  `laengen.sprachpass_aktiv`, `workshop.Profil.wert`.
- Produces:
  - `sprachpass.grenzwerte(profil=None) -> dict[str, float]`
  - `sprachpass.ueberschreitungen(zahlen, grenzen) -> list[str]` (Namen aus
    `NAMEN`, in dieser Reihenfolge)
  - `sprachpass.NOTIZ_KOPF: str`, `sprachpass.NOTIZ: dict[str, str]`
  - `sprachpass.notiz(namen: Sequence[str]) -> str`
  - `sprachpass.gepruefte_zitate(conn, chat_id) -> list[str]`
  - `sprachpass.enthaltene(text, zitate) -> list[str]`
  - `sprachpass.verlorene(alt, neu, zitate) -> list[str]`

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_sprachpass_notiz.py`

```python
"""Grenzwerte, Notiz und Zitatschutz (30.09.2026, Karte R).

Der Zitatschutz ist die wichtigste einzelne Massnahme dieses Pfades: ein
Ueberarbeitungslauf, der einen woertlichen Interviewsatz glattzieht, nimmt der
Gruppe genau das, was sie selbst gesammelt hat (theater-tells Nr. 21, 25, 28).
Geprueft wird mit ``zitat.pruefe`` -- der EINEN Normalisierung des Repos, ohne
eine zweite daneben.
"""

import pytest

from interview_theater import repo, sprachpass, workshop, zitat


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Grenzwerte und Ueberschreitungen ------------------------------------


def test_die_grenzwerte_kommen_aus_dem_profil(padua):
    grenzen = sprachpass.grenzwerte()
    assert set(grenzen) == set(sprachpass.NAMEN)
    assert grenzen["gedankenstriche"] == 6.0
    assert grenzen["fazitsatz"] == 1


def test_unter_der_grenze_gibt_es_nichts_zu_tun():
    zahlen = {"gedankenstriche": 5.9, "nicht_sondern": 1.0,
              "adjektiv_dreier": 0.0, "fazitsatz": 0}
    grenzen = {"gedankenstriche": 6.0, "nicht_sondern": 2.0,
               "adjektiv_dreier": 2.0, "fazitsatz": 1}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == []


def test_ab_der_grenze_wird_gemeldet():
    grenzen = {"gedankenstriche": 6.0, "nicht_sondern": 2.0,
               "adjektiv_dreier": 2.0, "fazitsatz": 1}
    zahlen = {"gedankenstriche": 6.0, "nicht_sondern": 0.0,
              "adjektiv_dreier": 0.0, "fazitsatz": 1}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == [
        "gedankenstriche", "fazitsatz"]


def test_die_reihenfolge_ist_die_von_NAMEN():
    """Eine Notiz mit wechselnder Reihenfolge waere zwei Notizen fuer
    denselben Befund -- und im Prompt zwei verschiedene Auftraege."""
    grenzen = {n: 0 for n in sprachpass.NAMEN}
    zahlen = {n: 1 for n in sprachpass.NAMEN}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == list(sprachpass.NAMEN)


# --- Die Notiz -----------------------------------------------------------


def test_ohne_ueberschreitung_gibt_es_keine_notiz():
    assert sprachpass.notiz([]) == ""


def test_die_notiz_nennt_jedes_muster_einmal():
    text = sprachpass.notiz(["gedankenstriche", "fazitsatz"])
    assert sprachpass.NOTIZ_KOPF in text
    assert sprachpass.NOTIZ["gedankenstriche"] in text
    assert sprachpass.NOTIZ["fazitsatz"] in text
    assert sprachpass.NOTIZ["nicht_sondern"] not in text


def test_die_notiz_verbietet_das_umschreiben_von_zitaten():
    """Der Auftrag muss es SAGEN und der Code muss es PRUEFEN. Beides -- der
    Satz allein ist eine Bitte, die Pruefung allein eine Ueberraschung."""
    text = sprachpass.notiz(["gedankenstriche"])
    assert sprachpass.NOTIZ_ZITATE in text


def test_die_notiz_ist_eine_regie_notiz_und_kein_neuschrieb():
    """Derselbe Weg wie "Passt, aber anders": derselbe Text, ueberarbeitet.
    Ein Wort wie "neu" darin wuerde einen Neuschrieb ausloesen."""
    text = sprachpass.notiz(list(sprachpass.NAMEN))
    for verboten in ("Schreib eine andere", "ganz neu", "[NEU]"):
        assert verboten not in text


def test_die_texte_laufen_ueber_T():
    assert sprachpass.T.NOTIZ_KOPF == sprachpass.NOTIZ_KOPF
    assert sprachpass.T.NOTIZ["fazitsatz"] == sprachpass.NOTIZ["fazitsatz"]


# --- Die geprueften Zitate -----------------------------------------------


@pytest.fixture
def mit_zitaten(conn):
    """Ein geprueftes Verdichtungsthema und ein Sprachprofil-Zitat."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, "datei.ogg", 1)
    repo.setze_transkript(conn, aufnahme_id,
                          "also ich, ja, ich weiss nicht, das war halt so")
    verdichtung_id = repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Sie erzaehlt vom Warten.",
        [{"thema": "Warten", "kurz": "Warten",
          "beleg_zitat": "das war halt so", "zitat_geprueft": 1}],
    )
    repo.setze_figur(conn, 1, "Mira", "wartet")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    repo.setze_figur_feld(conn, figur_id, "zitate",
                          "Seit drei Jahren und vier Monaten.")
    return conn
```

**Achtung:** die Namen `repo.lege_aufnahme_an`, `repo.setze_transkript` und
`repo.speichere_verdichtung` sind hier aus der Erinnerung geschrieben. **Vor
dem Schreiben des Tests** die tatsaechlichen Signaturen lesen und die Fixture
daran angleichen -- eine bestehende Fixture abschauen ist schneller:

```bash
grep -n "speichere_verdichtung\|lege_aufnahme_an" tests/test_kernzitate.py | head
grep -n "def speichere_verdichtung\|def lege_aufnahme_an\|def setze_transkript" -A 6 interview_theater/repo.py
```

Weiter im Test:

```python
def test_die_zitate_kommen_aus_beiden_quellen(mit_zitaten):
    zitate = sprachpass.gepruefte_zitate(mit_zitaten, 1)
    assert "das war halt so" in zitate
    assert "Seit drei Jahren und vier Monaten." in zitate


def test_ungepruefte_zitate_zaehlen_nicht(conn):
    """``repo.gepruefte_themen`` filtert ``zitat_geprueft = 1``. Ein
    unbelegtes Zitat zu schuetzen hiesse, eine Erfindung festzuschreiben."""
    assert sprachpass.gepruefte_zitate(conn, 1) == []


def test_enthaltene_findet_nur_was_dasteht():
    text = "MIRA: das war halt so. / PAL: Und dann?"
    assert sprachpass.enthaltene(text, ["das war halt so", "nie gesagt"]) == \
        ["das war halt so"]


def test_enthaltene_normalisiert_wie_zitat_pruefe():
    """Keine zweite Normalisierung: Zeilenumbrueche und typografische
    Anfuehrungszeichen behandelt ``zitat.pruefe``, und nur es."""
    text = "MIRA: das war\n   halt so."
    assert sprachpass.enthaltene(text, ["das war halt so"]) == ["das war halt so"]
    assert zitat.pruefe("das war halt so", text) is True


def test_verlorene_meldet_nur_was_vorher_dastand():
    alt = "MIRA: das war halt so."
    neu = "MIRA: So war das eben."
    assert sprachpass.verlorene(alt, neu, ["das war halt so"]) == ["das war halt so"]
    # Was vorher schon nicht dastand, kann nicht verlorengehen.
    assert sprachpass.verlorene(alt, neu, ["nie gesagt"]) == []


def test_ein_unveraendertes_zitat_faellt_nicht_auf():
    alt = "MIRA: das war halt so. Und dann ging sie."
    neu = "MIRA: das war halt so.\n(Sie geht.)"
    assert sprachpass.verlorene(alt, neu, ["das war halt so"]) == []


def test_ein_veraendertes_zitat_faellt_auf():
    """Der Kern: ein glattgezogener Interviewsatz ist ein verlorenes Zitat.
    Aus "also ich, ja, ich weiss nicht" wird "Es war eine schwierige Zeit" --
    theater-tells Nr. 21."""
    alt = "MIRA: also ich, ja, ich weiss nicht, das war halt so."
    neu = "MIRA: Es war eine schwierige Zeit fuer mich."
    assert sprachpass.verlorene(
        alt, neu, ["also ich, ja, ich weiss nicht"]) == \
        ["also ich, ja, ich weiss nicht"]
```

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass_notiz.py`
Erwartet: FAIL, `AttributeError: ... has no attribute 'grenzwerte'`.

- [x] **Schritt 3: An `interview_theater/sprachpass.py` anhaengen**

```python
#: Die Vorgabe-Grenzwerte, falls ein Profil einen nicht nennt. Gleichlautend
#: mit ``workshop.VORGABE_WERTE["sprachpass"]`` -- die Wiederholung ist hier
#: Absicht: der Leser dieses Moduls soll die Zahl sehen, ohne die TOML zu
#: oeffnen, und ein Test haelt beide Seiten aneinander.
GRENZEN_VORGABE: dict[str, float] = {
    "gedankenstriche": 6.0,
    "nicht_sondern": 2.0,
    "adjektiv_dreier": 2.0,
    "fazitsatz": 1,
}

#: Der Profil-Schluessel je Zaehler. Die Einheit steht im Namen, damit
#: niemand sie raten muss.
SCHLUESSEL: dict[str, str] = {
    "gedankenstriche": "gedankenstriche_je_1000",
    "nicht_sondern": "nicht_sondern_je_1000",
    "adjektiv_dreier": "adjektiv_dreier_je_1000",
    "fazitsatz": "fazitsatz_je_text",
}

#: Der Kopf der Regie-Notiz. **Eine Ueberarbeitung, kein Neuschrieb** -- wie
#: "Passt, aber anders": derselbe Text, dieselben Ereignisse, dieselbe
#: Reihenfolge.
NOTIZ_KOPF = ("Ueberarbeite den Text sprachlich. Dieselben Ereignisse, "
              "dieselbe Reihenfolge, dieselben Figuren, dasselbe Ende -- "
              "geaendert wird nur, wie es dasteht:")

#: Der Satz, der die Zitate schuetzt. Er steht **immer** in der Notiz, egal
#: welches Muster gemeldet wurde: das Modell soll es sagen bekommen, und der
#: Code prueft es danach nach (``verlorene``). Der Satz allein waere eine
#: Bitte, die Pruefung allein eine Ueberraschung.
NOTIZ_ZITATE = ("Woertliche Zitate aus den Interviews bleiben Wort fuer Wort "
                "stehen -- auch die Brueche, Wiederholungen und Fuellwoerter "
                "darin. Sie sind die Information, nicht der Fehler.")

#: Je Zaehler ein Satz, der sagt, was zu tun ist. Keine Zahl darin: das
#: Modell soll nicht zaehlen, sondern schreiben.
NOTIZ: dict[str, str] = {
    "gedankenstriche": ("Weniger Gedankenstriche. Wo einer steht, geht meist "
                        "ein Punkt, ein Komma oder gar kein Zeichen."),
    "nicht_sondern": ("Keine Saetze der Form \"nicht X, sondern Y\". Sag "
                      "gleich Y."),
    "adjektiv_dreier": ("Keine Dreierketten aus Eigenschaftswoertern. Eines "
                        "genuegt, oder ein Bild statt aller drei."),
    "fazitsatz": ("Kein Fazit und keine Moral am Schluss. Der letzte Satz "
                  "sagt nicht, worum es ging."),
}


def grenzwerte(profil: Any = None) -> dict[str, float]:
    """Die Grenzwerte dieses Profils, je Zaehler.

    Nachsichtig wie alle Leser dieses Pfades: was keine Zahl ist, wird die
    Vorgabe. ``scripts/pruefe_profil.py`` hat es vorher beanstandet."""
    from interview_theater import workshop

    p = profil or workshop.aktiv()
    ergebnis: dict[str, float] = {}
    for name in NAMEN:
        wert = p.wert(f"sprachpass.{SCHLUESSEL[name]}", GRENZEN_VORGABE[name])
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            log.warning("sprachpass.%s ist keine Zahl (%r)", SCHLUESSEL[name], wert)
            wert = GRENZEN_VORGABE[name]
        ergebnis[name] = wert
    return ergebnis


def ueberschreitungen(zahlen: dict[str, float],
                      grenzen: dict[str, float]) -> list[str]:
    """Welche Zaehler ihren Grenzwert erreichen -- **in der Reihenfolge von
    ``NAMEN``**.

    Erreichen, nicht ueberschreiten: der Grenzwert ist die Zahl, ab der es
    auffaellt. Die feste Reihenfolge ist keine Kosmetik -- eine Notiz mit
    wechselnder Reihenfolge waere im Prompt zwei verschiedene Auftraege fuer
    denselben Befund."""
    return [name for name in NAMEN
            if float(zahlen.get(name, 0)) >= float(grenzen.get(name, 0))
            and float(grenzen.get(name, 0)) > 0]


def notiz(namen: Sequence[str]) -> str:
    """Die Regie-Notiz aus den gemeldeten Zaehlern, oder "".

    Sie geht ueber denselben Weg wie "Passt, aber anders" in den Auftrag: der
    Text wird **ueberarbeitet**, nicht neu geschrieben. Deshalb kommt hier
    kein ``szene.NEU_MARKER`` vor -- der wuerde die alte Fassung aus dem
    Prompt nehmen und einen zweiten Text erzeugen statt denselben besser."""
    gemeldet = [n for n in NAMEN if n in set(namen)]
    if not gemeldet:
        return ""
    zeilen = [T.NOTIZ_KOPF]
    zeilen += [f"- {T.NOTIZ[n]}" for n in gemeldet]
    zeilen.append(T.NOTIZ_ZITATE)
    return "\n".join(zeilen)


def gepruefte_zitate(conn, chat_id: int) -> list[str]:
    """Alle woertlichen Zitate dieser Gruppe, die eine Pruefung bestanden
    haben.

    Zwei Quellen, und nur zwei: die Verdichtungsthemen mit
    ``zitat_geprueft = 1`` (``repo.gepruefte_themen``) und die
    Sprachprofil-Zitate der Figuren (``figur.zitate`` -- ohne ein einziges
    belegtes Zitat wird dort gar nichts gespeichert). Die Schaerfungen
    (``repo.schaerfungen``) liefern denselben ``beleg_zitat`` und sind damit
    eine Teilmenge der ersten Quelle, kein dritter Ort.

    **Ungeprueftes zaehlt nicht.** Ein unbelegtes Zitat zu schuetzen hiesse,
    eine Erfindung festzuschreiben -- genau das, was ``zitat.py`` seit N2
    verhindert.

    Reine Leseabfrage; die einzige Funktion dieses Moduls, die die Datenbank
    anfasst."""
    from interview_theater import repo

    zitate: list[str] = []
    for thema in repo.gepruefte_themen(conn, chat_id):
        text = (thema["beleg_zitat"] or "").strip()
        if text:
            zitate.append(text)
    for figur in repo.figuren(conn, chat_id):
        for zeile in (figur["zitate"] or "").splitlines():
            text = zeile.strip().lstrip("-• ").strip()
            if text:
                zitate.append(text)
    # Reihenfolge erhalten, Dubletten weg -- dasselbe Zitat zweimal zu
    # pruefen kostet nichts, aber es stuende zweimal im Vorfall.
    gesehen: set[str] = set()
    eindeutig = []
    for text in zitate:
        if text not in gesehen:
            gesehen.add(text)
            eindeutig.append(text)
    return eindeutig


def enthaltene(text: str | None, zitate: Iterable[str]) -> list[str]:
    """Welche dieser Zitate im Text stehen -- geprueft mit ``zitat.pruefe``.

    **Keine zweite Normalisierung.** ``zitat.pruefe`` glaettet
    Whitespace-Folgen und typografische Anfuehrungszeichen und sonst nichts;
    es ist dieselbe Funktion, an der jedes Belegzitat in Verdichter,
    Kernzitaten, Sprachprofil, Schaerfung und Dramaturgie haengt. Eine
    strengere Vergleichsform hier waere ein zweiter Massstab fuer denselben
    Begriff."""
    from interview_theater import zitat as zitat_modul

    return [z for z in zitate if zitat_modul.pruefe(z, text or "")]


def verlorene(alt: str | None, neu: str | None,
              zitate: Iterable[str]) -> list[str]:
    """Welche Zitate **vorher** im Text standen und **nachher** nicht mehr.

    Nur was vorher dastand: ein Zitat, das die Szene nie enthielt, kann sie
    nicht verlieren, und es einzufordern hiesse, dem Modell einen Satz
    aufzuzwingen, den die Gruppe hier nicht wollte."""
    liste = list(zitate)
    vorher = set(enthaltene(alt, liste))
    nachher = set(enthaltene(neu, liste))
    return [z for z in liste if z in vorher and z not in nachher]


# Der Textzugriff (A1-Konvention K1) -- **am Modulende**, nach allen
# Konstanten. Der Import von ``sprache`` steht schon oben aus Aufgabe 11.
T = sprache.Texte(__name__)
```

- [x] **Schritt 4: Die englischen Fassungen eintragen**

An `interview_theater/sprachen/en/texte.toml` (A1-Konvention K2/K3 -- die
Platzhaltermengen sind hier leer, also ist nur der Wortlaut zu uebersetzen):

```toml
["sprachpass"]
NOTIZ_KOPF = "Revise the language of the text. Same events, same order, same characters, same ending -- change only how it reads:"
NOTIZ_ZITATE = "Verbatim quotes from the interviews stay word for word, including the breaks, repetitions and filler words in them. They are the information, not the mistake."

["sprachpass".NOTIZ]
gedankenstriche = "Fewer dashes. Where one stands, a full stop, a comma or nothing at all usually works."
nicht_sondern = "No sentences of the form \"not X but Y\". Say Y straight away."
adjektiv_dreier = "No chains of three adjectives. One is enough, or an image instead of all three."
fazitsatz = "No conclusion and no moral at the end. The last line does not say what it was about."
```

- [x] **Schritt 5: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass_notiz.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m scripts.pruefe_sprache --schluessel sprachpass`
Erwartet: `0 Treffer`, Exit 0.

Zusaetzlich ein Gleichlauftest zwischen Modulkonstante und Profil-Vorgabe --
sonst driften `GRENZEN_VORGABE` und `workshop.VORGABE_WERTE` auseinander. An
`tests/test_sprachpass_notiz.py` anhaengen:

```python
def test_die_vorgabe_im_modul_und_im_profil_sagen_dasselbe():
    """Zwei Orte fuer eine Zahl sind erlaubt, solange ein Test sie
    aneinanderhaelt -- der Leser des Moduls soll die Zahl sehen, ohne die
    TOML zu oeffnen."""
    for name, wert in sprachpass.GRENZEN_VORGABE.items():
        schluessel = sprachpass.SCHLUESSEL[name]
        assert workshop.VORGABE.wert(f"sprachpass.{schluessel}") == wert, name
```

- [x] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/sprachpass.py interview_theater/sprachen/en/texte.toml \
        tests/test_sprachpass_notiz.py
git commit -m "sprachpass.py: Grenzwerte, Regie-Notiz und Zitatschutz ueber zitat.pruefe (R)"
```

---

## Aufgabe 13: `nachpass.py` I -- Phase 7, genau EIN Lauf

**Files:**
- Create: `interview_theater/nachpass.py`
- Modify: `interview_theater/sprachen/en/texte.toml` (`["nachpass"]`)
- Test: `tests/test_nachpass.py` (neu)

**Der Kern des Kostendeckels.** Nachzaehlen und Sprachpass ergeben **eine**
Notiz und **einen** Lauf. Waeren es zwei Wege, waeren es bis zu zwei Laeufe je
Szene -- die Karte erlaubt im Schnitt einen. Und "genau einer" ist hier keine
Absprache, sondern ein **gerader Codepfad ohne Schleife**: `nach_szene` ruft
`szene.schreibe` genau einmal und kehrt danach zurueck, egal wie das Ergebnis
aussieht.

**Wo er laeuft.** Im Thread, den `szene._lauf` ohnehin schon aufgemacht hat,
**unter dessen Sperre**. Deshalb `szene.schreibe` und nicht `szene.starte` --
`starte` wollte die Sperre erst nehmen und liefe ins Leere. Genau so macht es
`dramaturgie/schleife.py` schon.

**Der Rueckweg.** Vor dem Lauf wird der Stand der Szene gemerkt
(`titel`, `kurzbeschreibung`, `zusammenfassung`, `volltext`, `prosa`); geht ein
Zitat verloren, wird er mit `repo.aktualisiere_szene` zurueckgeschrieben. Die
**Fassungszeile** des verworfenen Laufs bleibt in `szenenfassung` stehen --
diese Tabelle wird nur angehaengt, nie geaendert, nie geloescht (AGENTS.md),
und die Spur ist richtig: der Lauf hat stattgefunden, und wer wissen will, was
er geschrieben haette, findet es auf der Gruppenseite.

**Interfaces:**
- Consumes: `laengen.aktiv`, `laengen.sprachpass_aktiv`,
  `laengen.zaehle_woerter`, `laengen.zu_lang`, `szene.budget_fuer_szene`,
  `szene.schreibe`, `szene.prosa_von`, `szene.schreibt_prosa`,
  `sprachpass.zaehle`, `sprachpass.grenzwerte`, `sprachpass.ueberschreitungen`,
  `sprachpass.notiz`, `sprachpass.gepruefte_zitate`, `sprachpass.verlorene`,
  `repo.hole_szenen`, `repo.aktualisiere_szene`, `repo.merke_vorfall`,
  `kuerzung.notiz_fuer_szene`.
- Produces:
  - `nachpass.ART_SZENE = "szene_nachpass"`
  - `nachpass.VORFALL_GELAUFEN = "nachpass_gelaufen"`
  - `nachpass.VORFALL_VERWORFEN = "nachpass_verworfen_zitat"`
  - `nachpass.VORFALL_IMMER_NOCH = "nachpass_reicht_nicht"`
  - `nachpass.befund(conn, chat_id, nummer) -> dict` (reine Leseabfrage:
    `{"budget", "woerter", "zu_lang", "zahlen", "gemeldet"}`)
  - `nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer) -> str | None`
    (die Notiz, mit der gelaufen wurde -- oder `None`, wenn nichts lief)

- [x] **Schritt 1: Den failenden Test schreiben** -- `tests/test_nachpass.py`

```python
"""Der EINE Ueberarbeitungslauf nach einem Szenentext (30.09.2026, Karte R).

Drei Zusagen, jede als Test:
1. Nachzaehlen und Sprachpass ergeben EINE Notiz und EINEN Lauf -- sonst
   waeren es bis zu zwei je Szene, und der Kostendeckel der Karte (+1 im
   Schnitt) waere gerissen.
2. Auch zwei zu lange Ergebnisse hintereinander ergeben genau einen Lauf: der
   Pfad ist gerade, ohne Schleife.
3. Verliert der Lauf ein geprueftes Belegzitat, wird er verworfen und die
   alte Fassung bleibt.

Kein Netz: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import (
    kuerzung, laengen, nachpass, phasen, repo, sprachpass, szene, workshop,
)

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _szenentext(koerper: str) -> str:
    return (
        "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
        "ZUSAMMENFASSUNG: Mira und Pal treffen sich.\nANDERS GEMACHT: nichts\n\n"
        + koerper
    )


#: Ein Text weit ueber jedem Dialog-Budget (450 * 1,3 = 585).
LANG = _szenentext("MIRA: " + ("wort " * 900) + "\n")

#: Derselbe Text, aber kurz -- und sauber.
KURZ = _szenentext("MIRA: Du bist zu spaet.\nPAL: Ich war da.\n")


class LLMAttrappe:
    """Liefert der Reihe nach die vorgegebenen Antworten und merkt jeden
    Aufruf samt ``art``. Ist die Liste leer, wiederholt sie die letzte."""

    def __init__(self, *antworten):
        self.antworten = list(antworten) or [KURZ]
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        i = min(len(self.aufrufe) - 1, len(self.antworten) - 1)
        return self.antworten[i]


@pytest.fixture
def szene7(conn, padua):
    """Phase 7, eine planungsvollstaendige Szene 1 mit Form ``dialog``."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


# --- Der Befund (reine Leseabfrage) --------------------------------------


def test_ein_kurzer_sauberer_text_meldet_nichts(szene7):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", KURZ, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["zu_lang"] is False
    assert befund["gemeldet"] == []


def test_ein_zu_langer_text_wird_gemeldet(szene7):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["budget"] > 0
    assert befund["woerter"] > befund["budget"]
    assert befund["zu_lang"] is True


def test_der_befund_ruft_kein_modell(szene7):
    """Reine Leseabfrage wie ``phasen.voraussetzungen`` -- damit ihn jeder
    Ort rufen darf, auch ein Knopf-Handler (Zusage 2)."""
    import inspect
    quelle = inspect.getsource(nachpass.befund)
    for verboten in ("klm", ".prosa(", "schreibe("):
        assert verboten not in quelle, verboten


def test_ohne_aktives_profil_meldet_der_befund_nichts(szene7, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["budget"] == 0
    assert befund["zu_lang"] is False
    assert befund["gemeldet"] == []


# --- Genau EIN Lauf -----------------------------------------------------


def test_ein_sauberer_text_loest_keinen_lauf_aus(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", KURZ, "passiert")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_szene(szene7, tg, klm, einst, 1, 1) is None
    assert klm.aufrufe == []


def test_ein_zu_langer_text_loest_genau_einen_lauf_aus(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert notiz and str(kuerzung.PROZENT) in notiz
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["art"] == nachpass.ART_SZENE


def test_zwei_zu_lange_ergebnisse_ergeben_trotzdem_einen_lauf(szene7, tg, einst):
    """Der Kern des Kostendeckels: auch wenn der gekuerzte Text noch ueber dem
    Budget liegt, gibt es keinen zweiten Lauf. Nur einen Vorfall."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    klm = LLMAttrappe(LANG)          # der Nachpass liefert wieder zu viel
    nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert len(klm.aufrufe) == 1
    arten = _vorfallarten(szene7)
    assert nachpass.VORFALL_IMMER_NOCH in arten


def test_laenge_und_sprache_ergeben_EINE_notiz(szene7, tg, einst):
    """Nachzaehlen und Sprachpass buendeln in einem Lauf. Waeren es zwei Wege,
    waeren es bis zu zwei Laeufe je Szene."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    text = _szenentext(
        "MIRA: " + ("wort " * 900) + "\nPAL: She was tired, angry, and alone.\n"
        "MIRA: It was not a home but a waiting room.\n"
    )
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert len(klm.aufrufe) == 1
    assert str(kuerzung.PROZENT) in notiz            # die Laenge
    assert sprachpass.NOTIZ_KOPF in notiz            # die Sprache
    assert sprachpass.NOTIZ_ZITATE in notiz          # der Zitatschutz


def test_nur_sprache_ohne_laenge_laeuft_auch(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    text = _szenentext(
        "MIRA: She was tired, angry, and alone.\n"
        "PAL: It felt cold, wet, empty.\n"
        "MIRA: Maybe home is just where you stop explaining.\n"
    )
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert notiz and sprachpass.NOTIZ_KOPF in notiz
    assert str(kuerzung.PROZENT) not in notiz
    assert len(klm.aufrufe) == 1


def test_bei_ausgeschaltetem_sprachpass_zaehlt_nur_die_laenge(szene7, tg, einst,
                                                              monkeypatch):
    monkeypatch.setattr(laengen, "sprachpass_aktiv", lambda profil=None: False)
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    text = _szenentext("MIRA: She was tired, angry, and alone.\n")
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_szene(szene7, tg, klm, einst, 1, 1) is None
    assert klm.aufrufe == []


# --- Der Zitatschutz ----------------------------------------------------


@pytest.fixture
def mit_zitat(szene7):
    """Ein geprueftes Belegzitat, das im Szenentext woertlich vorkommt."""
    conn = szene7
    repo.setze_figur(conn, 1, "Mira", "wartet")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    repo.setze_figur_feld(conn, figur_id, "zitate",
                          "also ich, ja, ich weiss nicht")
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    text = _szenentext(
        "MIRA: also ich, ja, ich weiss nicht. " + ("wort " * 900) + "\n")
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", "kurz", text, "passiert")
    return conn


def test_ein_lauf_der_das_zitat_behaelt_bleibt_stehen(mit_zitat, tg, einst):
    gut = _szenentext("MIRA: also ich, ja, ich weiss nicht.\nPAL: Und?\n")
    klm = LLMAttrappe(gut)
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    aktuell = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    assert "also ich, ja, ich weiss nicht" in aktuell
    assert "wort wort" not in aktuell, "der gekuerzte Text ist nicht angekommen"


def test_ein_veraendertes_zitat_verwirft_den_lauf(mit_zitat, tg, einst):
    """Die Attrappe glaettet den Interviewsatz -- genau theater-tells Nr. 21.
    Dann bleibt die alte Fassung, und es gibt einen Vorfall."""
    schlecht = _szenentext("MIRA: Es war eine schwierige Zeit fuer mich.\n")
    klm = LLMAttrappe(schlecht)
    vorher = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    nachher = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    assert nachher == vorher, "die alte Fassung muss stehenbleiben"
    arten = _vorfallarten(mit_zitat)
    assert nachpass.VORFALL_VERWORFEN in arten


def test_die_fassungszeile_des_verworfenen_laufs_bleibt_stehen(mit_zitat, tg, einst):
    """``szenenfassung`` wird nur angehaengt (AGENTS.md). Der Lauf hat
    stattgefunden -- die Spur ist richtig, und wer den Text sehen will, findet
    ihn auf der Gruppenseite."""
    szene_id = repo.hole_szenen(mit_zitat, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(mit_zitat, szene_id))
    klm = LLMAttrappe(_szenentext("MIRA: Es war eine schwierige Zeit.\n"))
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    assert len(repo.szenenfassungen(mit_zitat, szene_id)) == vorher + 1


def test_ein_gescheiterter_lauf_laesst_die_szene_unberuehrt(szene7, tg, einst):
    """Der Nachpass ist eine Zugabe. Reisst er, bleibt die Szene, die die
    Gruppe schon hat -- und die Gruppe erfaehrt nichts davon: sie kann nichts
    tun und wartet nicht darauf (SPEC § 11.1)."""
    class Kaputt:
        def prosa(self, *a, **k):
            raise RuntimeError("Modell weg")

    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    vorher = repo.hole_szenen(szene7, 1)[0]["volltext"]
    assert nachpass.nach_szene(szene7, tg, Kaputt(), einst, 1, 1) is None
    assert repo.hole_szenen(szene7, 1)[0]["volltext"] == vorher
    assert tg.nachrichten == [] or all(
        "nicht gelungen" not in str(n) for n in tg.nachrichten)
```

**Es gibt kein `repo.vorfaelle`** (selbst geprueft: `repo.py` hat nur
`merke_vorfall:373`, der Leser liegt in `web_daten._vorfaelle:220` und haengt
an der read-only Verbindung). Tests lesen die Tabelle deshalb direkt -- so wie
`tests/test_festlegung_erkenner.py:115` es tut. Diese Hilfe steht oben in
`tests/test_nachpass.py` und wird von `tests/test_nachpass_prosa.py` und
`tests/test_laengen_aus.py` importiert:

```python
def _vorfallarten(conn, chat_id: int = 1) -> list[str]:
    """Die ``art``-Werte der Vorfaelle dieser Gruppe.

    Direkt gelesen und nicht ueber ``repo``: es gibt dort keinen Leser
    (``merke_vorfall`` schreibt nur), und der einzige vorhandene liegt in
    ``web_daten`` an der read-only geoeffneten Verbindung. Dieselbe Bauart wie
    in ``tests/test_festlegung_erkenner.py``."""
    return [z["art"] for z in conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = ? ORDER BY id", (chat_id,))]
```

`repo.szenenfassungen(conn, szene_id)` und `repo.journal(conn, chat_id)`
existieren dagegen (selbst geprueft: `repo.py:2501` und `:2529`).
`tg.nachrichten` vor dem Schreiben an `tests/test_knoepfe.TelegramAttrappe`
abgleichen (`grep -n "self\." tests/test_knoepfe.py | head -20`).

- [x] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_nachpass.py`
Erwartet: FAIL, `ModuleNotFoundError: No module named 'interview_theater.nachpass'`.

- [x] **Schritt 3: `interview_theater/nachpass.py` anlegen**

```python
"""Der EINE Ueberarbeitungslauf am Ende eines Schreibvorgangs (30.09.2026,
Karte R).

**Warum es das gibt.** Zwei Befunde vom 06.09.2026 haben dieselbe Wurzel: der
Bot liefert einen Text, und **danach** passiert nichts mehr. Er ist zu lang
(die Gruppe hatte Instagram-Kuerze beschlossen), und er traegt
Maschinensprache (Gedankenstrich-Inflation, "nicht X, sondern Y",
Adjektiv-Trippel, Fazitsatz). Birk hat beides von Hand nachgearbeitet. Die
Negativliste ``theater-tells.md`` steht **praeventiv** im Prompt -- das ist
die halbe Massnahme; hier ist die andere.

**Der Kostendeckel ist gebaut, nicht abgesprochen.** Nachzaehlen und
Sprachpass ergeben **eine** Notiz und **einen** Lauf, und der Pfad ist gerade:
``nach_szene`` ruft den Schreibweg genau einmal und kehrt danach zurueck --
egal, wie das Ergebnis aussieht. Bleibt der gekuerzte Text ueber dem Budget,
gibt es einen **Vorfall** und keinen zweiten Lauf. Eine Schleife hier waere
die teuerste Zeile des Repos.

**Wo er laeuft.** In dem Thread, den der Schreibweg ohnehin schon aufgemacht
hat, **unter dessen Sperre**. Deshalb ``szene.schreibe`` und nicht
``szene.starte``: ``starte`` wollte die Sperre nehmen, die der eigene Thread
gerade haelt, und liefe ins Leere. Genau so macht es
``dramaturgie/schleife.py`` schon.

**Der Zitatschutz ist die wichtigste einzelne Massnahme.** Ein Lauf, der einen
woertlichen Interviewsatz glattzieht, nimmt der Gruppe genau das, was sie
selbst gesammelt hat -- aus "also ich, ja, ich weiss nicht" wird "Es war eine
schwierige Zeit fuer mich" (theater-tells Nr. 21). Gemessen wird mit
``zitat.pruefe``, der EINEN Normalisierung des Repos. Verliert der Lauf ein
Zitat, wird sein Ergebnis **verworfen**: die alte Fassung wird
zurueckgeschrieben, und der Vorfall nennt das Zitat nicht (Belegzitate gehoeren
nicht in ein projiziertes Dashboard) -- nur seine Zahl und die Szene.

**Die Gruppe erfaehrt nichts davon.** Der Nachpass ist eine Zugabe: sie hat
ihren Text, sie wartet nicht darauf, und sie kann nichts tun. Ein
gescheiterter Nachpass ist deshalb unsichtbar und bekommt einen Vorfall
(SPEC § 11.1) -- anders als ein gescheiterter Szenenlauf, auf den die Gruppe
gerade wartet.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Die ``art`` in der Tabelle ``aufruf``. Eigene Werte, damit Dashboard und
#: Kostenzeile den Nachpass **getrennt** zaehlen koennen -- so wie
#: ``dramaturgie_b1`` es vormacht. Ohne das waere "+1 Lauf je Szene" im Befund
#: nicht nachweisbar.
ART_SZENE = "szene_nachpass"
ART_PROSA = "kurzgeschichte_nachpass"

#: Vorfaelle. Alle drei sind fuer das Dashboard, nicht fuer den Chat.
VORFALL_GELAUFEN = "nachpass_gelaufen"
VORFALL_VERWORFEN = "nachpass_verworfen_zitat"
VORFALL_IMMER_NOCH = "nachpass_reicht_nicht"
VORFALL_FEHLER = "nachpass_fehlgeschlagen"


def befund(conn, chat_id: int, nummer: int | None) -> dict:
    """Was an dieser Szene zu beanstanden ist -- **reine Leseabfrage**.

    Liefert ``{"budget", "woerter", "zu_lang", "zahlen", "gemeldet"}``. Kein
    Modellaufruf, keine Schreiboperation; damit darf sie jeder Ort rufen, auch
    ein Knopf-Handler (Zusage 2) und ``scripts/laengen_probe.py``.

    Steht das Profil aus, ist das Budget 0 und ``gemeldet`` leer -- dann ist
    nichts zu tun, und der Aufrufer sieht das an einer Zahl statt an einem
    Schalter."""
    from interview_theater import laengen, repo, sprachpass, szene as szene_modul

    leer = {"budget": 0, "woerter": 0, "zu_lang": False, "zahlen": {},
            "gemeldet": []}
    ziel = None
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] == nummer and not s["entfernt_am"]:
            ziel = s
            break
    if ziel is None:
        return leer
    # Der Text dieses Laufs: im Feinschliff der Theatertext, in Phase 6 die
    # Prosafassung. ``szene.schreibt_prosa`` entscheidet das schon fuer den
    # Schreibweg -- hier dieselbe Weiche, damit nicht zwei Lesarten entstehen.
    text = (szene_modul.prosa_von(ziel)
            if szene_modul.schreibt_prosa(conn, chat_id)
            else (ziel["volltext"] or ""))
    budget = szene_modul.budget_fuer_szene(conn, chat_id, ziel)
    woerter = laengen.zaehle_woerter(text)
    zahlen: dict = {}
    gemeldet: list[str] = []
    if laengen.sprachpass_aktiv():
        zahlen = sprachpass.zaehle(text)
        gemeldet = sprachpass.ueberschreitungen(zahlen, sprachpass.grenzwerte())
    return {
        "budget": budget,
        "woerter": woerter,
        "zu_lang": laengen.zu_lang(woerter, budget),
        "zahlen": zahlen,
        "gemeldet": gemeldet,
    }


def _notiz(zu_lang: bool, gemeldet: list[str]) -> str:
    """Laenge und Sprache in EINER Regie-Notiz.

    Die Laengenhaelfte ist wortgleich die des Kuerzen-Wegs
    (``kuerzung.notiz_fuer_szene``) -- **nicht** eine zweite Formulierung
    desselben Auftrags: der Prozentwert steht an einer Stelle
    (``kuerzung.PROZENT``), und zwei Notizen fuer dieselbe Sache waeren zwei
    Wahrheiten."""
    from interview_theater import kuerzung, sprachpass

    teile = []
    if zu_lang:
        teile.append(kuerzung.notiz_fuer_szene())
    sprachlich = sprachpass.notiz(gemeldet)
    if sprachlich:
        teile.append(sprachlich)
    return "\n\n".join(teile)


def nach_szene(conn, tg, klm, e, chat_id: int, nummer: int | None) -> str | None:
    """Der Nachpass fuer EINE Szene. Liefert die Notiz, mit der gelaufen wurde
    -- oder ``None``, wenn nichts lief.

    **Genau ein Lauf**, ohne Schleife: gemessen, Notiz gebaut, ``schreibe``
    einmal gerufen, geprueft, zurueck. Wird auch der neue Text nicht kurz
    genug, gibt es ``VORFALL_IMMER_NOCH`` und keinen zweiten Aufruf.

    Aufgerufen wird sie am Ende von ``szene._lauf``, also **im schon
    laufenden Thread und unter dessen Sperre** -- deshalb ``szene.schreibe``
    und nicht ``szene.starte``."""
    from interview_theater import laengen, repo, sprachpass, szene as szene_modul

    if not laengen.aktiv():
        return None
    stand = befund(conn, chat_id, nummer)
    notiz = _notiz(stand["zu_lang"], stand["gemeldet"])
    if not notiz:
        return None

    ziel = next((s for s in repo.hole_szenen(conn, chat_id)
                 if s["nummer"] == nummer and not s["entfernt_am"]), None)
    if ziel is None:
        return None
    # Der Rueckweg, falls ein Zitat verlorengeht. Gemerkt wird, was
    # ``repo.aktualisiere_szene`` zurueckschreiben kann.
    alt = {
        "id": ziel["id"],
        "titel": ziel["titel"],
        "kurzbeschreibung": ziel["kurzbeschreibung"],
        "zusammenfassung": ziel["zusammenfassung"],
        "volltext": ziel["volltext"],
        "prosa": szene_modul.prosa_von(ziel),
    }
    prosa_lauf = szene_modul.schreibt_prosa(conn, chat_id)
    alter_text = alt["prosa"] if prosa_lauf else (alt["volltext"] or "")
    zitate = sprachpass.gepruefte_zitate(conn, chat_id)

    auftrag = f"Schreib Szene {nummer} neu. {notiz}"
    if prosa_lauf:
        # Wie beim Kuerzen in Phase 6: ohne den Marker saehe das Modell die
        # Prosa dieser Szene nicht, weil ``volltext`` dort leer ist.
        auftrag += f" {szene_modul.BISHER_MARKER}"
    try:
        szene_modul.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART_SZENE)
    except Exception:
        # Der Nachpass ist eine Zugabe. Reisst er, bleibt die Szene, die die
        # Gruppe schon hat -- und sie erfaehrt nichts davon: sie wartet nicht
        # darauf und kann nichts tun (SPEC § 11.1).
        log.exception("Nachpass fehlgeschlagen, chat_id=%s, Szene %s",
                      chat_id, nummer)
        _vorfall(conn, chat_id, e, VORFALL_FEHLER,
                 f"Szene {nummer}: Nachpass-Lauf gescheitert, alte Fassung bleibt")
        return None

    neu = next((s for s in repo.hole_szenen(conn, chat_id)
                if s["id"] == alt["id"]), None)
    if neu is None:
        return notiz
    neuer_text = (szene_modul.prosa_von(neu) if prosa_lauf
                  else (neu["volltext"] or ""))
    verloren = sprachpass.verlorene(alter_text, neuer_text, zitate)
    if verloren:
        # Verworfen, nicht abgewertet: die alte Fassung wird
        # zurueckgeschrieben. Die Fassungszeile des Laufs bleibt in
        # ``szenenfassung`` stehen -- diese Tabelle wird nur angehaengt, und
        # die Spur ist richtig.
        repo.aktualisiere_szene(
            conn, alt["id"], alt["titel"], alt["kurzbeschreibung"],
            alt["volltext"], alt["zusammenfassung"],
            prosa=alt["prosa"] or None,
        )
        _vorfall(
            conn, chat_id, e, VORFALL_VERWORFEN,
            f"Szene {nummer}: Nachpass verworfen, {len(verloren)} geprueftes "
            f"Belegzitat/e waere(n) verlorengegangen -- alte Fassung bleibt",
        )
        return notiz

    nachher = laengen.zaehle_woerter(neuer_text)
    _vorfall(
        conn, chat_id, e, VORFALL_GELAUFEN,
        f"Szene {nummer}: {stand['woerter']} -> {nachher} Woerter "
        f"(Budget {stand['budget']}), Sprachmuster "
        f"{', '.join(stand['gemeldet']) or 'keine'}",
    )
    if laengen.zu_lang(nachher, stand["budget"]):
        # Kein zweiter Lauf. "Noch zu lang" ist eine Meldung und kein Auftrag
        # -- ein Modell, das zweimal zu lang schreibt, schreibt es beim
        # dritten Mal auch (dieselbe Begruendung wie bei
        # ``ablauf.echo_wiederholt``).
        _vorfall(
            conn, chat_id, e, VORFALL_IMMER_NOCH,
            f"Szene {nummer}: nach dem Nachpass {nachher} Woerter bei Budget "
            f"{stand['budget']} -- kein zweiter Lauf",
        )
    return notiz


def _vorfall(conn, chat_id: int, e, art: str, text: str) -> None:
    """Ein Vorfall fuer das Dashboard -- nie eine Nachricht in den Chat, und
    **nie** mit einem Belegzitat darin (dieselbe Grenze wie bei den
    Verdichtungen: das Dashboard haengt am Beamer)."""
    from interview_theater import repo

    log.info("%s: %s", art, text)
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None), art, text)
    except Exception:
        log.exception("Vorfall %s nicht schreibbar", art)
```

- [x] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_nachpass.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

- [x] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/nachpass.py tests/test_nachpass.py
git commit -m "nachpass.py: genau EIN Lauf je Szene, Laenge und Sprache in einer Notiz, Zitatschutz (R)"
```

---

## Aufgabe 14: `nachpass.py` II -- Phase 6, ein Lauf fuer die ganze Geschichte

**Files:**
- Modify: `interview_theater/nachpass.py`
- Test: `tests/test_nachpass_prosa.py` (neu)

**Warum hier ein anderer Ablauf.** In Phase 6 schreibt **ein** Lauf alle
Abschnitte. Ein Nachpass je Abschnitt waere bei sechs Abschnitten sechs
Laeufe -- weit ueber dem Deckel. Also: **ein** Lauf ueber die ganze
Geschichte, mit allen Befunden in **einer** Notiz. Bei sechs Abschnitten ist
das +1 Lauf fuer sechs Szenen und damit deutlich unter "+1 je Szene".

**Und warum hier vor dem Speichern geprueft wird.** `kurzgeschichte.hole_text`
(Aufgabe 7) liefert die Antwort, ohne etwas zu speichern. Damit kann der
Nachpass **zwei** Dinge pruefen, bevor irgendetwas in der Datenbank steht:

1. **Die Abschnittszahl.** Kommt eine andere zurueck, waere der Abgleich in
   `lege_szenen_an` ergaenzend -- und zwei Abschnitte behielten ihren alten,
   langen Text (genau der Fall, gegen den `kuerzung.notiz_fuer_prosa`
   geschrieben wurde).
2. **Die Zitate.**

Deshalb braucht Phase 6 **keinen** Rueckweg: es wird gar nichts geschrieben,
was zurueckzunehmen waere. In Phase 7 gibt es diesen Zwischenstand nicht --
`szene.schreibe` ist eine Einheit aus Aufruf und Speichern, und sie zu
zerlegen waere ein groesserer Umbau als diese Karte traegt. Die beiden
Verfahren sind also nicht zwei Lesarten derselben Regel, sondern zwei Wege zum
selben Ergebnis, jeder an der Form seines Schreibwegs.

**Interfaces:**
- Consumes: `kurzgeschichte.hole_text`, `kurzgeschichte.zerlege`,
  `kurzgeschichte.lege_szenen_an`, `kurzgeschichte.budget_eintraege`,
  `kurzgeschichte._faktor`, `laengen.*`, `sprachpass.*`, `kuerzung.notiz_fuer_prosa`.
- Produces:
  - `nachpass.VORFALL_ABSCHNITTSZAHL = "nachpass_abschnittszahl"`
  - `nachpass.befund_prosa(conn, chat_id) -> dict`
    (`{"eintraege", "zu_lang", "zahlen", "gemeldet"}`; `eintraege` je Abschnitt
    `(nummer, form, budget, woerter)`)
  - `nachpass.nach_geschichte(conn, tg, klm, e, chat_id) -> str | None`

- [ ] **Schritt 1: Den failenden Test schreiben** -- `tests/test_nachpass_prosa.py`

```python
"""Der EINE Nachpass fuer die ganze Kurzgeschichte (30.09.2026, Karte R).

Phase 6 schreibt alle Abschnitte in einem Lauf -- ein Nachpass je Abschnitt
waere bei sechs Abschnitten sechs Laeufe. Also einer fuer alle, mit allen
Befunden in einer Notiz. Und er prueft VOR dem Speichern: kommt eine andere
Abschnittszahl zurueck oder fehlt ein Zitat, wird gar nichts geschrieben.
"""

import pytest

from interview_theater import (
    kuerzung, kurzgeschichte, laengen, nachpass, phasen, repo, sprachpass,
    workshop,
)

from test_knoepfe import TelegramAttrappe
from test_nachpass import _vorfallarten


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _geschichte(*abschnitte: tuple[str, str, str]) -> str:
    """``(titel, zusammenfassung, koerper)`` je Abschnitt zu einer Antwort."""
    teile = []
    for i, (titel, fassung, koerper) in enumerate(abschnitte, start=1):
        teile.append(f"## {i}. {titel}\nZusammenfassung: {fassung}\n\n{koerper}")
    return "\n\n".join(teile)


LANG = _geschichte(
    ("Ankunft", "Sie kommt an.", "wort " * 900),
    ("Streit", "Es kracht.", "wort " * 900),
)
KURZ = _geschichte(
    ("Ankunft", "Sie kommt an.", "Sie kommt an. Es ist kalt."),
    ("Streit", "Es kracht.", "Sie streiten. Dann gehen sie."),
)
DREI = _geschichte(
    ("Ankunft", "Sie kommt an.", "Kurz."),
    ("Streit", "Es kracht.", "Kurz."),
    ("Morgen", "Es wird hell.", "Kurz."),
)


class LLMAttrappe:
    def __init__(self, *antworten):
        self.antworten = list(antworten) or [KURZ]
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        i = min(len(self.aufrufe) - 1, len(self.antworten) - 1)
        return self.antworten[i]


@pytest.fixture
def prosa6(conn, monkeypatch):
    """Phase 6, zwei Abschnitte mit langer Prosa -- der Stand nach einem Lauf."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Streit")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", "chor")
        repo.aktualisiere_szene(conn, szene_id, titel, "kurz", None, "passiert",
                                prosa="wort " * 900)
    phasen.setze(conn, 1, 6, "test")
    yield conn
    workshop.vergiss()


# --- Der Befund ---------------------------------------------------------


def test_der_befund_nennt_jeden_abschnitt_mit_budget_und_wortzahl(prosa6):
    stand = nachpass.befund_prosa(prosa6, 1)
    assert [n for n, _f, _b, _w in stand["eintraege"]] == [1, 2]
    assert all(b > 0 for _n, _f, b, _w in stand["eintraege"])
    assert all(w > b for _n, _f, b, w in stand["eintraege"])
    assert stand["zu_lang"] is True


def test_der_befund_ruft_kein_modell(prosa6):
    import inspect
    quelle = inspect.getsource(nachpass.befund_prosa)
    for verboten in ("klm", ".prosa(", "hole_text"):
        assert verboten not in quelle, verboten


def test_ohne_profil_meldet_der_befund_nichts(prosa6, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    stand = nachpass.befund_prosa(prosa6, 1)
    assert stand["eintraege"] == []
    assert stand["zu_lang"] is False


# --- Genau EIN Lauf fuer alle Abschnitte -------------------------------


def test_ein_lauf_fuer_alle_abschnitte(prosa6, tg, einst):
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert notiz
    assert len(klm.aufrufe) == 1, "ein Lauf, nicht einer je Abschnitt"
    assert klm.aufrufe[0]["art"] == nachpass.ART_PROSA


def test_die_notiz_bindet_die_abschnittszahl(prosa6, tg, einst):
    """``kuerzung.notiz_fuer_prosa`` bindet sie schon -- hier dieselbe
    Formulierung und keine zweite."""
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert kuerzung.notiz_fuer_prosa(2) in notiz


def test_die_notiz_traegt_laenge_und_sprache(prosa6, tg, einst):
    szenen = repo.hole_szenen(prosa6, 1)
    repo.aktualisiere_szene(
        prosa6, szenen[0]["id"], "Ankunft", "kurz", None, "passiert",
        prosa=("wort " * 900) + " She was tired, angry, and alone."
              " It was not a home but a waiting room.",
    )
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert kuerzung.notiz_fuer_prosa(2) in notiz
    assert sprachpass.NOTIZ_KOPF in notiz
    assert len(klm.aufrufe) == 1


def test_die_neue_fassung_kommt_an(prosa6, tg, einst):
    klm = LLMAttrappe(KURZ)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa6, 1)}
    assert "Es ist kalt" in prosa[1]
    assert "wort wort" not in prosa[1]


def test_ein_sauberer_stand_loest_keinen_lauf_aus(prosa6, tg, einst):
    for s in repo.hole_szenen(prosa6, 1):
        repo.aktualisiere_szene(prosa6, s["id"], s["titel"], "kurz", None,
                                "passiert", prosa="Kurz und sauber.")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_geschichte(prosa6, tg, klm, einst, 1) is None
    assert klm.aufrufe == []


def test_zwei_zu_lange_ergebnisse_ergeben_einen_lauf(prosa6, tg, einst):
    klm = LLMAttrappe(LANG)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(klm.aufrufe) == 1
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_IMMER_NOCH in arten


# --- Die Wachen vor dem Speichern -------------------------------------


def test_eine_andere_abschnittszahl_wird_verworfen(prosa6, tg, einst):
    """Der Abgleich in ``lege_szenen_an`` ist ERGAENZEND: kaeme eine dritte
    Szene dazu, behielten die vorhandenen ihren alten Text und die neue waere
    frei erfunden. Also gar nicht speichern."""
    klm = LLMAttrappe(DREI)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(repo.hole_szenen(prosa6, 1)) == 2
    assert all("wort wort" in (s["prosa"] or "")
               for s in repo.hole_szenen(prosa6, 1))
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_ABSCHNITTSZAHL in arten


def test_ein_verlorenes_zitat_wird_verworfen(prosa6, tg, einst):
    repo.setze_figur(prosa6, 1, "Mira", "wartet")
    figur_id = repo.figuren(prosa6, 1)[0]["id"]
    repo.setze_figur_feld(prosa6, figur_id, "zitate",
                          "also ich, ja, ich weiss nicht")
    szenen = repo.hole_szenen(prosa6, 1)
    repo.aktualisiere_szene(
        prosa6, szenen[0]["id"], "Ankunft", "kurz", None, "passiert",
        prosa="also ich, ja, ich weiss nicht. " + ("wort " * 900),
    )
    klm = LLMAttrappe(KURZ)          # ohne das Zitat
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa6, 1)}
    assert "also ich, ja, ich weiss nicht" in prosa[1], "alte Fassung muss bleiben"
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_VERWORFEN in arten


def test_bei_verwerfen_wird_nichts_geschrieben(prosa6, tg, einst):
    """Phase 6 braucht keinen Rueckweg: geprueft wird VOR dem Speichern, also
    gibt es nichts zurueckzunehmen -- und auch keine Fassungszeile."""
    szene_id = repo.hole_szenen(prosa6, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(prosa6, szene_id))
    klm = LLMAttrappe(DREI)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(repo.szenenfassungen(prosa6, szene_id)) == vorher


def test_ein_gescheiterter_lauf_laesst_alles_stehen(prosa6, tg, einst):
    class Kaputt:
        def prosa(self, *a, **k):
            raise RuntimeError("Modell weg")

    vorher = [(s["nummer"], s["prosa"]) for s in repo.hole_szenen(prosa6, 1)]
    assert nachpass.nach_geschichte(prosa6, tg, Kaputt(), einst, 1) is None
    assert [(s["nummer"], s["prosa"]) for s in repo.hole_szenen(prosa6, 1)] == vorher
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_nachpass_prosa.py`
Erwartet: FAIL, `AttributeError: ... has no attribute 'befund_prosa'`.

- [ ] **Schritt 3: An `interview_theater/nachpass.py` anhaengen**

```python
#: Der Lauf hat eine andere Abschnittszahl geliefert und wurde verworfen.
#: Eigener Vorfall, weil er etwas anderes heisst als ein verlorenes Zitat:
#: hier hat das Modell die Struktur geaendert, nicht den Wortlaut.
VORFALL_ABSCHNITTSZAHL = "nachpass_abschnittszahl"


def befund_prosa(conn, chat_id: int) -> dict:
    """Was an der ganzen Kurzgeschichte zu beanstanden ist -- **reine
    Leseabfrage**.

    ``eintraege`` sind ``(nummer, form, budget, woerter)`` je Abschnitt,
    ``zu_lang`` ist wahr, sobald **ein** Abschnitt ueber der Schwelle liegt
    (einer reicht: der Lauf geht ohnehin ueber alle), und ``gemeldet`` sind die
    Sprachmuster ueber dem Grenzwert, gezaehlt am **ganzen** Text -- ein
    Fazitsatz gehoert zum Schluss der Geschichte, nicht zum Schluss jedes
    Abschnitts."""
    from interview_theater import (
        kurzgeschichte, laengen, repo, sprachpass, szene as szene_modul,
    )

    leer = {"eintraege": [], "zu_lang": False, "zahlen": {}, "gemeldet": []}
    if not laengen.aktiv():
        return leer
    budgets = kurzgeschichte.budget_eintraege(
        conn, chat_id, faktor=kurzgeschichte._faktor(conn, chat_id))
    if not budgets:
        return leer
    texte = {}
    for s in repo.hole_szenen(conn, chat_id):
        if not s["entfernt_am"] and s["nummer"] is not None:
            texte[s["nummer"]] = szene_modul.prosa_von(s)
    eintraege = [
        (n, f, b, laengen.zaehle_woerter(texte.get(n, "")))
        for n, f, b in budgets
    ]
    ganz = "\n\n".join(texte[n] for n, _f, _b, _w in eintraege if texte.get(n))
    zahlen: dict = {}
    gemeldet: list[str] = []
    if laengen.sprachpass_aktiv() and ganz:
        zahlen = sprachpass.zaehle(ganz)
        gemeldet = sprachpass.ueberschreitungen(zahlen, sprachpass.grenzwerte())
    return {
        "eintraege": eintraege,
        # Einer reicht: der Lauf geht ohnehin ueber die ganze Geschichte.
        "zu_lang": any(laengen.zu_lang(w, b) for _n, _f, b, w in eintraege),
        "zahlen": zahlen,
        "gemeldet": gemeldet,
    }


def nach_geschichte(conn, tg, klm, e, chat_id: int) -> str | None:
    """Der Nachpass fuer die ganze Kurzgeschichte (Phase 6). Liefert die
    Notiz, mit der gelaufen wurde -- oder ``None``.

    **Ein Lauf fuer alle Abschnitte.** Einer je Abschnitt waere bei sechs
    Abschnitten sechs Laeufe; so ist es +1 fuer sechs Szenen.

    **Geprueft wird VOR dem Speichern.** ``kurzgeschichte.hole_text`` liefert
    die Antwort, ohne etwas zu schreiben -- damit koennen zwei Dinge die
    Fassung noch verhindern: eine geaenderte Abschnittszahl (der Abgleich in
    ``lege_szenen_an`` ist **ergaenzend**, also behielten vorhandene
    Abschnitte ihren alten, langen Text -- genau der Fall, gegen den
    ``kuerzung.notiz_fuer_prosa`` geschrieben wurde) und ein verlorenes
    Belegzitat. Deshalb braucht dieser Weg keinen Rueckweg: es steht nichts
    da, was zurueckzunehmen waere."""
    from interview_theater import (
        kuerzung, kurzgeschichte, laengen, repo, sprachpass,
        szene as szene_modul,
    )

    if not laengen.aktiv():
        return None
    stand = befund_prosa(conn, chat_id)
    if not stand["eintraege"]:
        return None
    anzahl = len(stand["eintraege"])
    teile = []
    if stand["zu_lang"]:
        # Wortgleich die Notiz des Kuerzen-Wegs -- der Prozentwert steht an
        # einer Stelle (``kuerzung.PROZENT``), und sie bindet die
        # Abschnittszahl schon mit.
        teile.append(kuerzung.notiz_fuer_prosa(anzahl))
    sprachlich = sprachpass.notiz(stand["gemeldet"])
    if sprachlich:
        teile.append(sprachlich)
    if not teile:
        return None
    notiz = "\n\n".join(teile)

    alte_texte = {}
    for s in repo.hole_szenen(conn, chat_id):
        if not s["entfernt_am"] and s["nummer"] is not None:
            alte_texte[s["nummer"]] = szene_modul.prosa_von(s)
    zitate = sprachpass.gepruefte_zitate(conn, chat_id)
    budgets = [(n, f, b) for n, f, b, _w in stand["eintraege"]]

    try:
        # ``vorlage=True``: ohne die bestehende Fassung im Prompt schriebe das
        # Modell "kuerzer" ueber einen Text, den es nie sah -- dieselbe
        # Begruendung wie in ``kuerzung.starte``.
        antwort = kurzgeschichte.hole_text(
            conn, klm, e, chat_id, notiz, vorlage=True, eintraege=budgets,
            art=ART_PROSA,
        )
        abschnitte = kurzgeschichte.zerlege(antwort or "")
    except Exception:
        log.exception("Prosa-Nachpass fehlgeschlagen, chat_id=%s", chat_id)
        _vorfall(conn, chat_id, e, VORFALL_FEHLER,
                 "Prosa-Nachpass gescheitert, alte Fassung bleibt")
        return None

    if len(abschnitte) != anzahl:
        _vorfall(
            conn, chat_id, e, VORFALL_ABSCHNITTSZAHL,
            f"Prosa-Nachpass verworfen: {len(abschnitte)} statt {anzahl} "
            "Abschnitte -- nichts gespeichert, alte Fassung bleibt",
        )
        return notiz

    neu_ganz = "\n\n".join(prosa for _t, _z, prosa in abschnitte)
    alt_ganz = "\n\n".join(alte_texte[n] for n in sorted(alte_texte)
                           if alte_texte[n])
    verloren = sprachpass.verlorene(alt_ganz, neu_ganz, zitate)
    if verloren:
        _vorfall(
            conn, chat_id, e, VORFALL_VERWORFEN,
            f"Prosa-Nachpass verworfen: {len(verloren)} geprueftes "
            "Belegzitat/e waere(n) verlorengegangen -- nichts gespeichert",
        )
        return notiz

    kurzgeschichte.lege_szenen_an(conn, chat_id, abschnitte)
    nachher = {n: laengen.zaehle_woerter(p)
               for n, (_t, _z, p) in enumerate(abschnitte, start=1)}
    _vorfall(
        conn, chat_id, e, VORFALL_GELAUFEN,
        "Prosa-Nachpass: "
        + "; ".join(
            f"Abschnitt {n} {w} -> {nachher.get(n, 0)} Woerter (Budget {b})"
            for n, _f, b, w in stand["eintraege"]
        )
        + f"; Sprachmuster {', '.join(stand['gemeldet']) or 'keine'}",
    )
    if any(laengen.zu_lang(nachher.get(n, 0), b)
           for n, _f, b, _w in stand["eintraege"]):
        _vorfall(
            conn, chat_id, e, VORFALL_IMMER_NOCH,
            "Prosa-Nachpass: mindestens ein Abschnitt liegt weiter ueber dem "
            "Budget -- kein zweiter Lauf",
        )
    return notiz
```

- [ ] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_nachpass_prosa.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

- [ ] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/nachpass.py tests/test_nachpass_prosa.py
git commit -m "nachpass.py: ein Lauf fuer die ganze Geschichte, geprueft vor dem Speichern (R)"
```

---

## Aufgabe 15: Die Verdrahtung -- und der Nachweis, dass Dortmund nichts merkt

**Files:**
- Modify: `interview_theater/szene.py` (`_lauf`)
- Modify: `interview_theater/kurzgeschichte.py` (`_lauf`)
- Test: `tests/test_laengen_aus.py` (neu)

**Wo der Aufruf steht, und warum genau dort.** Am **Ende** von `_lauf`,
**nach** dem erfolgreichen `schreibe`, **im `try`** (nicht im `finally`) und
**vor** der Freigabe der Sperre. Vier Gruende, jeder gegen eine Alternative:

- **Nicht in `schreibe`**: dort wuerde der Nachpass sich selbst rufen, denn er
  ruft `schreibe`. Eine Rekursionsbremse waere eine Wache gegen einen Fehler,
  den es an dieser Stelle gar nicht geben muss.
- **Nicht in `starte`**: das laeuft vor dem Thread, da gibt es noch keinen
  Text.
- **Im `try`, nicht im `finally`**: nach einem gescheiterten Szenenlauf gibt
  es keinen Text, ueber den nachzuzaehlen waere.
- **Vor der Freigabe der Sperre**: waehrend der Nachpass laeuft, darf kein
  zweiter Szenenlauf derselben Gruppe dazwischenkommen. Die Sperre haelt das
  schon -- man muss sie nur nicht vorher loslassen.

- [ ] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_aus.py`

```python
"""Die Zusage an Dortmund: der ganze Pfad ist ein No-Op (30.09.2026, Karte R).

Ohne aktives Profil darf kein zusaetzlicher Modellaufruf entstehen, kein
zusaetzlicher Vorfall, keine zusaetzliche Journalzeile und kein Zeichen mehr
im Prompt. Geprueft wird nicht der Schalter, sondern die WIRKUNG.
"""

import pytest

from interview_theater import (
    kurzgeschichte, laengen, nachpass, phasen, repo, szene, workshop,
)

from test_knoepfe import TelegramAttrappe
from test_nachpass import LLMAttrappe, LANG, KURZ, _vorfallarten, szene7  # noqa: F401


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def ohne_profil(monkeypatch):
    from interview_theater import anweisungen
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture
def szene7_dortmund(conn, ohne_profil):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


# --- Dortmund: genau EIN Modellaufruf je Szene --------------------------


def test_ein_szenenlauf_bleibt_ein_aufruf(szene7_dortmund, tg, einst):
    """Der Kern der Zusage: kein Nachpass, keine Zusatzkosten."""
    klm = LLMAttrappe(LANG)          # bewusst zu lang -- ohne Profil egal
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["art"] == szene.ART


def test_kein_nachpass_vorfall(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(LANG)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    arten = set(_vorfallarten(szene7_dortmund))
    assert not (arten & {nachpass.VORFALL_GELAUFEN, nachpass.VORFALL_VERWORFEN,
                         nachpass.VORFALL_IMMER_NOCH,
                         nachpass.VORFALL_ABSCHNITTSZAHL,
                         nachpass.VORFALL_FEHLER})


def test_keine_laengen_journalzeile(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(KURZ)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    texte = [j["text"] for j in repo.journal(szene7_dortmund, 1)]
    assert not any("Seed" in t or "gewuerfelt" in t for t in texte)


def test_kein_laengenblock_im_prompt(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(KURZ)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert laengen.BLOCK_KOPF_SZENE not in klm.aufrufe[0]["nutzer"]


def test_die_drei_funktionen_liefern_nichts_zu_tun(szene7_dortmund):
    """Nicht der Schalter wird geprueft, sondern die Wirkung: ohne Profil
    liefern Budget, Nachzaehlen und Sprachpass "nichts"."""
    ziel = szene.ziel_fuer(szene7_dortmund, 1, "Schreib Szene 1")
    assert szene.budget_fuer_szene(szene7_dortmund, 1, ziel) == 0
    stand = nachpass.befund(szene7_dortmund, 1, 1)
    assert stand["zu_lang"] is False and stand["gemeldet"] == []
    assert nachpass.befund_prosa(szene7_dortmund, 1)["eintraege"] == []


# --- Padua: der Nachpass laeuft wirklich ------------------------------


def test_padua_haengt_genau_einen_lauf_an(szene7, tg, einst):  # noqa: F811
    """Die Gegenprobe: mit Profil sind es zwei Aufrufe -- der Szenenlauf und
    genau ein Nachpass."""
    klm = LLMAttrappe(LANG, KURZ)
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=30)
    assert [a["art"] for a in klm.aufrufe] == [szene.ART, nachpass.ART_SZENE]


def test_der_nachpass_laeuft_unter_derselben_sperre(szene7, tg, einst):  # noqa: F811
    """Waehrend er laeuft, darf kein zweiter Szenenlauf derselben Gruppe
    dazwischenkommen -- die Sperre haelt das schon, man darf sie nur nicht
    vorher loslassen."""
    klm = LLMAttrappe(LANG, KURZ)
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    assert szene._sperre_fuer(1).locked() is True
    thread.join(timeout=30)
    assert szene._sperre_fuer(1).locked() is False
    assert len(klm.aufrufe) == 2


def test_ein_gescheiterter_szenenlauf_loest_keinen_nachpass_aus(szene7, tg, einst):  # noqa: F811
    """Der Aufruf steht im ``try``, nicht im ``finally``: nach einem
    gescheiterten Lauf gibt es keinen Text, ueber den nachzuzaehlen waere."""
    class Kaputt:
        def __init__(self):
            self.aufrufe = []

        def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                  timeout=None):
            self.aufrufe.append(art)
            raise RuntimeError("Modell weg")

    klm = Kaputt()
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert klm.aufrufe == [szene.ART]
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_aus.py -k padua`
Erwartet: FAIL, `assert ['szene'] == ['szene', 'szene_nachpass']` -- der
Nachpass ist noch nicht verdrahtet. Die Dortmund-Tests sind an diesem Punkt
schon gruen; das ist richtig, sie sind der Waechter.

- [ ] **Schritt 3: `szene._lauf` verdrahten**

```python
def _lauf(conn, tg, klm, e, chat_id: int, auftrag: str,
          sperre: threading.Lock, art: str = ART) -> None:
    """Der Thread-Rumpf: ``schreibe()`` mit Fehlerbehandlung und garantierter
    Freigabe der Sperre. Bliebe sie bei einem Fehlschlag liegen, koennte die
    Gruppe fuer den Rest des Workshops keine Szene mehr schreiben lassen.

    **Und, seit dem 30.09.2026 (Karte R), der Nachpass**: nachzaehlen und
    Sprachmuster pruefen, und wenn etwas dran ist, GENAU EINEN
    Ueberarbeitungslauf anhaengen. Er steht hier und nicht in ``schreibe``,
    weil er ``schreibe`` selbst ruft -- in ``schreibe`` waere es eine
    Rekursion. Er steht im ``try`` und nicht im ``finally``, weil es nach
    einem gescheiterten Lauf keinen Text gibt, ueber den nachzuzaehlen waere.
    Und er steht **vor** der Freigabe der Sperre, damit ihm kein zweiter
    Szenenlauf derselben Gruppe dazwischenkommt.

    Ein Nachpass auf einem Nachpass gibt es nicht: der ruft ``schreibe``
    direkt und kommt hier nie vorbei."""
    from interview_theater import arbeitszeilen

    zeilen = arbeitszeilen.sichtbar(tg, chat_id, ARBEITSART)
    try:
        nummer = schreibe(conn, tg, klm, e, chat_id, auftrag, art=art)
        if art == ART:
            from interview_theater import nachpass

            nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer)
    except Exception:
        ...   # unveraendert
    finally:
        zeilen.stoppe()
        sperre.release()
```

`if art == ART`: der Nachpass laeuft nur nach einem **gewoehnlichen**
Szenenlauf. Kaeme er auch nach einem Nachpass-Lauf, waere der gerade Pfad eine
Schleife -- und heute ruft der Nachpass `schreibe` ohnehin direkt, also ist die
Bedingung eine zweite Wache und kein Ersatz fuer die erste. Ein Kommentar im
Code sagt das.

- [ ] **Schritt 4: `kurzgeschichte._lauf` verdrahten**

```python
    def _lauf() -> None:
        from interview_theater import arbeitszeilen, szene as szene_modul

        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "prosa")
        try:
            schreibe(conn, tg, klm, e, chat_id, regie, vorlage=vorlage)
            # Der Nachpass (30.09.2026, Karte R): EIN Lauf fuer alle
            # Abschnitte, im selben Thread und unter derselben Sperre. Im
            # ``try``, weil es nach einem gescheiterten Lauf keine Geschichte
            # gibt, ueber die nachzuzaehlen waere.
            from interview_theater import nachpass

            nachpass.nach_geschichte(conn, tg, klm, e, chat_id)
        except Exception:
            ...   # unveraendert
        finally:
            zeilen.stoppe()
            sperre.release()
```

Der Prosa-Nachpass geht ueber `kurzgeschichte.hole_text` und nie ueber
`schreibe`, kommt hier also nie wieder vorbei -- eine `art`-Wache wie in
`szene._lauf` braucht er nicht. Ein Kommentar sagt das.

- [ ] **Schritt 5: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_aus.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_szene.py tests/test_kuerzung.py tests/test_knoepfe.py tests/test_dramaturgie_schleife.py tests/test_profil_bitgleich.py tests/profile/`
Erwartet: `passed`, kein `failed`.

- [ ] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/szene.py interview_theater/kurzgeschichte.py \
        tests/test_laengen_aus.py
git commit -m "Nachpass verdrahtet: im Schreib-Thread, unter der Sperre, fuer Dortmund ein No-Op (R)"
```

---

## Aufgabe 16: Die englische Negativliste um die vier Satzmuster ergaenzen

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/theater-tells.md`
- Test: `tests/test_sprachpass_prompt.py` (neu)

**Was hier NICHT passiert.** `interview_theater/prompts/theater-tells.md`
(deutsch, 179 Zeilen, 30 Eintraege) wird **nicht angefasst**. Die Karte sagt
es ausdruecklich, und der Grund ist die Bitgleichheit: die Datei geht in
`szene.systemanweisung()` **und** in `kurzgeschichte.systemanweisung()`, beide
stehen im Schnappschuss.

**Was dazukommt.** Vier Eintraege in der **englischen** Fassung, in der Form
der Datei (`**N. Titel.**`, dann `- Bad:` / `- Better:`) und **nur als
Negativbeispiele**. Sie sind das praeventive Gegenstueck zu den vier Zaehlern:
der Prompt sagt es vorher, der Zaehler prueft es nachher. Drei der vier haben
in der deutschen Liste schon einen Verwandten (Nr. 13 rhetorische
Dreierfigur, Nr. 19 Themensatz, Nr. 3/4 Fazit und Moral) -- der
Gedankenstrich hat keinen, und **das** ist der Eintrag, der in Dortmund
gefehlt hat.

**Die Beispiele sind erfunden** -- kein Satz aus einem echten Interview, kein
Klarname (die Namen sind die erfundenen der englischen Datei).

- [ ] **Schritt 1: Den failenden Test schreiben** -- `tests/test_sprachpass_prompt.py`

```python
"""Die englische Negativliste traegt die vier Muster des Sprachpasses
(30.09.2026, Karte R).

Der Prompt sagt es vorher, der Zaehler prueft es nachher -- beides, weil am
06.09.2026 das Vorhersagen allein nicht genuegte. Die deutsche Datei bleibt
unberuehrt: sie steht im Prompt-Schnappschuss, und Dortmund bleibt
zeichengleich.
"""

import hashlib
from pathlib import Path

import pytest

from interview_theater import anweisungen, sprachpass, workshop

WURZEL = Path(__file__).resolve().parent.parent
DEUTSCH = WURZEL / "interview_theater" / "prompts" / "theater-tells.md"
ENGLISCH = (WURZEL / "interview_theater" / "sprachen" / "en" / "prompts"
            / "theater-tells.md")

#: Selbst gemessen am 30.09.2026 auf ``d8deb6c``. Wer die deutsche Datei
#: anfasst, sieht es hier -- und im Bitgleichheits-Test.
DEUTSCH_SHA_D8DEB6C = (
    "ce75dd90397aca82440c77f0c9638cab6e69f168317a276b77f9483129904d6d")


def test_die_deutsche_liste_bleibt_unberuehrt():
    """Sie geht in ``szene.systemanweisung()`` UND in
    ``kurzgeschichte.systemanweisung()``, beide im Schnappschuss."""
    roh = DEUTSCH.read_bytes()
    assert hashlib.sha256(roh).hexdigest() == DEUTSCH_SHA_D8DEB6C


@pytest.mark.parametrize("marke", [
    "dash", "not X but Y", "three adjectives", "closing line",
])
def test_die_englische_liste_nennt_jedes_muster(marke):
    text = ENGLISCH.read_text(encoding="utf-8")
    assert marke.lower() in text.lower(), marke


def test_die_englische_liste_bleibt_in_der_form_der_datei():
    """Jeder Eintrag: fette Nummer, dann "Bad:" und "Better:". Wer die Form
    bricht, bricht das Muster, an dem das Modell die Liste liest."""
    text = ENGLISCH.read_text(encoding="utf-8")
    import re
    nummern = [int(n) for n in re.findall(r"(?m)^\*\*(\d+)\.", text)]
    assert nummern == list(range(1, len(nummern) + 1)), nummern
    assert text.count("- Bad:") == len(nummern)
    assert text.count("- Better:") == len(nummern)


def test_die_neuen_eintraege_stehen_am_ende():
    """Angehaengt, nicht eingeschoben: die bestehenden Nummern sind in
    Berichten und Notizen zitiert."""
    text = ENGLISCH.read_text(encoding="utf-8")
    import re
    nummern = [int(n) for n in re.findall(r"(?m)^\*\*(\d+)\.", text)]
    letzte_vier = text[text.index(f"**{nummern[-4]}."):]
    for marke in ("dash", "not ", "three", "closing"):
        assert marke.lower() in letzte_vier.lower(), marke


def test_die_beispiele_sind_englisch():
    from scripts import pruefe_sprache
    text = ENGLISCH.read_text(encoding="utf-8")
    assert pruefe_sprache.deutsche_treffer(str(ENGLISCH), text) == []


def test_jedes_beispiel_wuerde_vom_zaehler_gefunden():
    """Der Beweis, dass Prompt und Zaehler dasselbe meinen: jedes
    "Bad:"-Beispiel der vier neuen Eintraege loest seinen Zaehler aus.

    Ohne diesen Test koennten Negativliste und Zaehler zwei verschiedene
    Dinge verbieten -- und die Gruppe bekaeme einen Ueberarbeitungsauftrag fuer
    etwas, das im Prompt nie stand."""
    beispiele = {
        "gedankenstriche": "She waited—and waited—and waited.",
        "nicht_sondern": "It was not a home but a waiting room.",
        "adjektiv_dreier": "She was tired, angry, and alone.",
        "fazitsatz": "Maybe home is just where you stop explaining.",
    }
    for name, satz in beispiele.items():
        assert sprachpass.rohzahlen(satz, "en")[name] >= 1, name
        # Und der Satz steht wirklich in der Datei.
        assert satz in ENGLISCH.read_text(encoding="utf-8"), name


def test_die_englische_liste_kommt_im_prompt_an(monkeypatch):
    """Sie wird ueber die Sprachschicht geholt (A1 Aufgabe 4), nicht ueber
    einen eigenen Pfad."""
    from interview_theater import sprache
    monkeypatch.setattr(sprache, "code", lambda: "en")
    anweisungen._CACHE.clear()
    text = anweisungen.hole("theater-tells")
    assert "not a home but a waiting room" in text
    anweisungen._CACHE.clear()
```

Der sha ist am 30.09.2026 auf `d8deb6c` selbst gemessen. Nachrechnen:

```bash
$PY -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('interview_theater/prompts/theater-tells.md').read_bytes()).hexdigest())"
```
Erwartet: `ce75dd90397aca82440c77f0c9638cab6e69f168317a276b77f9483129904d6d`
(179 Zeilen, 30 Eintraege).

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass_prompt.py`
Erwartet: FAIL in `test_die_englische_liste_nennt_jedes_muster[dash]` --
`assert 'dash' in ...`.

- [ ] **Schritt 3: Die vier Eintraege anhaengen**

An das **Ende** von `interview_theater/sprachen/en/prompts/theater-tells.md`.
`N` ist die naechste freie Nummer (die englische Datei hat nach A1 Aufgabe 20
dieselbe Zahl an Eintraegen wie die deutsche, also `N = 31`; die tatsaechliche
Nummer aus der Datei ablesen und nicht raten):

```markdown
The following four are machine tells in the narrow sense: they are counted,
not judged (interview_theater/sprachpass.py). Each one was measured in a real
group text on 06.09.2026 and removed by hand afterwards.

**31. The dash instead of a decision.**
- Bad: She waited—and waited—and waited.
- Better: She waited. (Pause) She waited.
  A dash joins what a full stop would separate. On stage the pause does that
  work, and it does it better. One dash in two thousand words is nothing; six
  in a thousand is a habit.

**32. "not X but Y".**
- Bad: It was not a home but a waiting room.
- Better: A waiting room. With a kettle.
  The negation carries the thing it denies into the sentence and keeps it
  there. Say the second half and drop the first.

**33. Three adjectives in a row.**
- Bad: She was tired, angry, and alone.
- Better: She had not taken her coat off.
  Three words for one state is one word three times. An action shows it; a
  list only sorts it.

**34. The closing line that says what it was about.**
- Bad: Maybe home is just where you stop explaining.
- Better: NADIA: Are you turning the light off? / ELIF: I'm still sitting.
  The last line is the one the audience takes home. If it names the theme, it
  takes the theme instead of the scene.
```

Zwei Zusagen dieser Datei bleiben: **nur Negativbeispiele** (jeder Eintrag hat
sein `Bad:`/`Better:`-Paar), und **kein echter Satz und kein Klarname** --
die Namen sind die erfundenen der Datei.

- [ ] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprachpass_prompt.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m scripts.pruefe_sprache --dateien interview_theater/sprachen/en/prompts/theater-tells.md`
Erwartet: `0 Treffer`, Exit 0.

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_profil_bitgleich.py`
Erwartet: `passed`. Der Paritaetstest aus A1 zaehlt Ueberschriften, Code-Zaeune
und JSON-Zeilen -- vier fette Eintraege veraendern keinen dieser drei Werte,
der Test bleibt gruen. Faellt er doch, ist die **Struktur** der Ergaenzung das
Problem (eine `#`-Ueberschrift oder ein Code-Zaun darin) und nicht der Test.

- [ ] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add interview_theater/sprachen/en/prompts/theater-tells.md \
        tests/test_sprachpass_prompt.py
git commit -m "Englische Negativliste: die vier Satzmuster des Sprachpasses (R)"
```

---

## Aufgabe 17: Die Eichungstabelle und das Geruest des Befunds (kostenlos)

**Files:**
- Create: `docs/padua-r-laengen-2026-09-30/BEFUND.md`
- Test: `tests/test_laengen_eichung.py` (neu)

**Warum das eine eigene Aufgabe ist.** Die Karte verlangt, die Eichung zu
**belegen** und die Rahmenwerte als Vorschlag zu markieren. Das geht ohne
einen einzigen Modellaufruf: die Vergleichszahlen stehen teils im Repo
(Herkules-Mass, Replikenmedian), teils sind sie vom Architekten gemessen
(Dortmund v1/v2, Birks Vault). Was fehlt, ist die Tabelle, die beides
nebeneinanderstellt -- und der Test, der die Rahmenwerte des Profils an dieser
Tabelle festhaelt.

- [ ] **Schritt 1: Die im Repo nachrechenbaren Zahlen holen**

```bash
grep -n "700\|1400\|1500\|12.300\|12300" interview_theater/prompts/formen/dialog.md
grep -n -i "median\|8 Woert" docs/stilvorlagen/2026-09-06/analyse.md
```

Erwartet: `formen/dialog.md` nennt 700-1500 Woerter je Szene, Median 1400 und
rund 12.300 Woerter fuer neun Szenen; `analyse.md` nennt den Replikenmedian.
Die tatsaechlich gefundenen Zahlen in die Tabelle unten eintragen -- **nicht**
die hier vermuteten.

- [ ] **Schritt 2: `docs/padua-r-laengen-2026-09-30/BEFUND.md` anlegen**

```markdown
# Befund: Laengen-Rhythmus je Szene und Sprachpass (Karte R)

Stand 30.09.2026. Dieses Dokument haelt fest, **woran die Rahmenwerte
geeicht sind** und **was ein Lauf tatsaechlich geliefert hat**. Die Tabellen
unter "Simulationslauf" und "Einzel-Szenenlauf" fuellt Aufgabe 21 bzw. 22.

Alles Material in diesem Dokument ist **erfunden** oder aggregiert: kein
Transkript, kein Klarname, kein Belegzitat aus einem echten Interview.

## 1. Eichung der Rahmenwerte

Die Startwerte der Karte sind **Vorschlaege und ungemessen**. Sie stehen in
`workshop/padua-2026/profil.toml` unter `[laengen.rahmen]` und sind ohne
Codeaenderung aenderbar. Woran sie zu messen sind:

| Quelle | Wie gemessen | Woerter je Szene/Abschnitt |
|---|---|---|
| Herkules.exe, Textbuch (im Repo: `interview_theater/prompts/formen/dialog.md`) | im Regelblock als Zielwert genannt | 700-1500, Median 1400; neun Szenen rund 12.300 |
| Herkules.exe, Repliken (`docs/stilvorlagen/2026-09-06/analyse.md`) | Median je Replik | 8 Woerter |
| Dortmund Gruppe 1, Textbuch **v2** (06.09.2026, 19:08, Phase-6-Prosa, drei Abschnitte) | Architekt, 30.09.2026; Abschnittskoerper nach der Ueberschrift, Tokens `\w+('\w+)?`, Markdown entfernt | "Am Steg" (chor) **825**, "Elf Grad" (dialog) **802**, "Fronten" (rap) **603** |
| Dortmund Gruppe 1, Textbuch **v1** (06.09.2026, 14:09, vier erhaltene Abschnitte) | ebenso | **794 / 309 / 317 / 293** |

**Der Befund an diesen Zahlen -- zwei Saetze, und beide tragen die Karte:**

1. **v2 ist flach.** 825 / 802 / 603 Woerter, drei verschiedene Formen
   (chor / dialog / rap), und trotzdem praktisch eine Laenge. Genau dagegen ist
   der Rhythmus-Wuerfel gebaut. v1 war ungleich (794 / 309 / 317 / 293) -- der
   Unterschied zwischen v1 und v2 ist also nicht die Geschichte, sondern die
   Glaettung.
2. **Die Startwerte der Karte liegen schon bei etwa einem Viertel.** Dialog
   200-450 gegen Herkules 700-1500 und gegen Dortmund v2 (802 fuer die
   Dialogszene). Der Faktor 0,25 obendrauf ergibt **50-110 Woerter** je
   Dialogszene -- rund eine Minute Buehnenzeit.
   **Das ist OFFENE FRAGE 1 an Birk:** sind die Startwerte der Normalfall oder
   schon die Instagram-Laenge? Beide Antworten sind eine Zeile TOML.

**Was die Formen betrifft:** die Karte nennt Chor/Lied 80-200, Rap 120-250,
Dialog 200-450. **Monolog nennt sie nicht** -- hier steht 150-350 als
Vorschlag (OFFENE FRAGE 4). Gegen Dortmund v2 gemessen sind alle vier Rahmen
deutlich kuerzer als das, was dort entstand; die Rangfolge (Chor kuerzer als
Dialog) deckt sich dagegen **nicht** mit v2, wo die Chorszene die laengste war
-- ein weiteres Zeichen fuer die Glaettung.

## 2. Gedankenstriche: der Anker

Dortmund v2 hatte **einen** Gedankenstrich in **2.230** Woertern (Architekt,
30.09.2026) -- also **0,45 je 1.000**. Der Grenzwert
`sprachpass.gedankenstriche_je_1000 = 6.0` liegt damit gut dreizehnmal
darueber: er trifft die Inflation und nicht den einzelnen Strich. Die drei
anderen Grenzwerte (je 1.000: `nicht_sondern` 2,0, `adjektiv_dreier` 2,0; je
Text: `fazitsatz` 1) sind **ungemessen** -- sie stehen im Profil und sind ohne
Code aenderbar.

## 3. Was die Zaehler an erfundenem Material finden

(Fuellt Aufgabe 18 mit der Ausgabe von `scripts/laengen_probe.py`.)

## 4. Simulationslauf Padua

(Fuellt Aufgabe 21. Tabelle: Szene | Form | Budget | Wortzahl erster Lauf |
nach Kuerzung | Sprachpass-Zaehler vorher/nachher; dazu Kosten und Laeufe je
Szene.)

## 5. Einzel-Szenenlauf Phase 7

(Fuellt Aufgabe 22. Derselbe Tabellenkopf, plus ein Vorher/Nachher-Auszug von
hoechstens zehn Zeilen.)

## 6. Kosten

(Fuellt Aufgabe 21/22 aus der Tabelle `aufruf`, getrennt nach `art`:
`szene`, `kurzgeschichte`, `szene_nachpass`, `kurzgeschichte_nachpass`.)
```

- [ ] **Schritt 3: Den Test schreiben, der die Tabelle und das Profil
aneinanderhaelt** -- `tests/test_laengen_eichung.py`

```python
"""Die Rahmenwerte stehen im Profil UND im Befund -- und beide sagen dasselbe
(30.09.2026, Karte R).

Zwei Orte fuer eine Zahl sind erlaubt, solange ein Test sie aneinanderhaelt.
Ohne diesen Test waere der Befund nach der ersten Aenderung am Profil eine
falsche Aussage ueber den Betrieb -- und genau so ein Dokument hat am
06.09.2026 gefehlt.
"""

import re
from pathlib import Path

import pytest

from interview_theater import laengen, workshop

BEFUND = (Path(__file__).resolve().parent.parent / "docs"
          / "padua-r-laengen-2026-09-30" / "BEFUND.md")


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_der_befund_existiert():
    assert BEFUND.is_file(), BEFUND


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_jeder_rahmen_des_profils_steht_im_befund(form):
    unten, oben = laengen.rahmen_fuer(form)
    text = BEFUND.read_text(encoding="utf-8")
    assert f"{unten}-{oben}" in text or f"{unten}–{oben}" in text, (form, unten, oben)


def test_der_befund_markiert_die_werte_als_vorschlag():
    """Die Karte verlangt es ausdruecklich: "Rahmenwerte als Vorschlag
    markieren"."""
    text = BEFUND.read_text(encoding="utf-8").lower()
    assert "vorschlag" in text and "ungemessen" in text


def test_der_befund_nennt_die_gemessenen_vergleichszahlen():
    """Die Eichung muss belegt sein, nicht behauptet."""
    text = BEFUND.read_text(encoding="utf-8")
    for zahl in ("825", "802", "603", "794", "1400", "2.230"):
        assert zahl in text, zahl


def test_das_profil_markiert_die_werte_ebenfalls():
    """Wer die TOML oeffnet, soll es dort lesen und nicht im Befund suchen."""
    pfad = (Path(__file__).resolve().parent.parent / "workshop"
            / "padua-2026" / "profil.toml")
    text = pfad.read_text(encoding="utf-8").lower()
    assert "vorschlag" in text and "ungemessen" in text


def test_der_grenzwert_liegt_ueber_dem_gemessenen_anker():
    """Ein Grenzwert unter dem gemessenen Normalfall wuerde jeden Text
    beanstanden. Dortmund v2: 0,45 Gedankenstriche je 1.000 Woerter."""
    from interview_theater import sprachpass
    assert sprachpass.grenzwerte()["gedankenstriche"] > 0.45 * 2
```

- [ ] **Schritt 4: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_eichung.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Schlaegt `test_jeder_rahmen_des_profils_steht_im_befund` fehl, wird **der
Befund** nachgezogen, nicht der Test gelockert: das Dokument soll sagen, was
der Betrieb tut.

- [ ] **Schritt 5: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add docs/padua-r-laengen-2026-09-30/BEFUND.md tests/test_laengen_eichung.py
git commit -m "Befund: Eichungstabelle der Rahmenwerte, an das Profil gebunden (R)"
```

---

## Aufgabe 18: Der deterministische Ersatznachweis (kostenlos)

**Files:**
- Create: `scripts/laengen_probe.py`
- Modify: `docs/padua-r-laengen-2026-09-30/BEFUND.md` (Abschnitt 3)
- Test: `tests/test_laengen_probe.py` (neu)

**Warum es das braucht.** Der Simulator erreicht nach Messung
(`simulation/berichte/verlauf.jsonl`) die Prosa-Phase und **einen** Abschnitt,
aber **nicht** Phase 7 und **nicht** den Kuerzungsweg (ANNAHME A10). Ein
bezahlter Lauf ist also kein vollstaendiger Nachweis. Dieses Skript fuehrt
denselben Codepfad **mit einer Attrappe** und zeigt die Zahlen als Tabelle --
kostenlos, wiederholbar, und es ist der Nachweis, auf den sich die Karte
stuetzen kann, wenn der bezahlte Lauf nicht alles hergibt.

**Was es NICHT ist.** Kein Test (es hat keine Sollwerte) und kein Ersatz fuer
`pytest` -- die Zusagen stehen in `tests/test_nachpass*.py`. Es ist ein
Berichtswerkzeug, so wie `scripts/dramaturgie_pruefen.py --nur-mechanik`.

**Interfaces:**
- Produces: `scripts/laengen_probe.py` mit `TEXTE: dict[str, str]`,
  `zeilen(conn, chat_id) -> list[dict]`, `tabelle(zeilen) -> str`,
  `main(argv=None) -> int`; Optionen `--formen`, `--faktor`, `--markdown`.
- Das Skript legt eine **Wegwerf-Datenbank** an (`tempfile`), nie `IT_DB` --
  wie `scripts/pruefe_prompts.py`.

- [ ] **Schritt 1: Den failenden Test schreiben** -- `tests/test_laengen_probe.py`

```python
"""Der kostenlose Ersatznachweis (30.09.2026, Karte R).

Kein bezahlter Lauf: die Attrappe liefert einen zu langen, sprachlich
auffaelligen Text, und gemessen wird, dass genau EIN Nachpass folgt und die
Tabelle die Zahlen traegt.
"""

import pytest

from scripts import laengen_probe


def test_die_texte_der_attrappe_sind_alle_auffaellig():
    """Die Probe taugt nur, wenn ihr Material wirklich etwas ausloest -- sonst
    beweist eine leere Tabelle gar nichts."""
    from interview_theater import sprachpass
    for name, text in laengen_probe.TEXTE.items():
        roh = sprachpass.rohzahlen(text, "en")
        assert any(v > 0 for v in roh.values()), name


def test_der_lauf_liefert_eine_zeile_je_szene(tmp_path):
    zeilen = laengen_probe.probe(formen=["dialog", "chor", "rap"], faktor=1.0)
    assert [z["nummer"] for z in zeilen] == [1, 2, 3]
    for z in zeilen:
        assert z["budget"] > 0
        assert z["woerter_vorher"] > 0
        assert z["laeufe"] in (1, 2)


def test_genau_ein_nachpass_je_szene():
    """Der Kostendeckel, kostenlos nachgewiesen: ein Szenenlauf plus
    hoechstens ein Nachpass."""
    zeilen = laengen_probe.probe(formen=["dialog", "dialog"], faktor=1.0)
    assert all(z["laeufe"] <= 2 for z in zeilen), zeilen


def test_die_budgets_sind_nicht_flach():
    zeilen = laengen_probe.probe(formen=["dialog"] * 4, faktor=1.0)
    budgets = [z["budget"] for z in zeilen]
    assert len(set(budgets)) >= 2, budgets


def test_die_tabelle_traegt_jede_spalte():
    zeilen = laengen_probe.probe(formen=["dialog"], faktor=1.0)
    text = laengen_probe.tabelle(zeilen)
    for kopf in ("Szene", "Form", "Budget", "Woerter", "Laeufe"):
        assert kopf in text, kopf


def test_das_skript_nimmt_niemals_IT_DB(monkeypatch):
    """Wie ``scripts/pruefe_prompts.py``: die Betriebsdatenbank wird nicht
    angefasst -- auch nicht lesend."""
    monkeypatch.setenv("IT_DB", "/nicht/vorhanden/soap.db")
    zeilen = laengen_probe.probe(formen=["dialog"], faktor=1.0)
    assert zeilen


def test_es_gibt_keinen_echten_modellaufruf():
    import inspect
    quelle = inspect.getsource(laengen_probe)
    assert "httpx" not in quelle
    assert "IT_LLM_URL" not in quelle
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_probe.py`
Erwartet: FAIL, `ModuleNotFoundError: No module named 'scripts.laengen_probe'`.

- [ ] **Schritt 3: `scripts/laengen_probe.py` anlegen**

```python
"""Der kostenlose Nachweis fuer Laengen-Budget und Sprachpass (30.09.2026,
Karte R).

**Warum es das gibt.** Der Simulator (``scripts/simulation.py``) erreicht
gemessen die Prosa-Phase, aber nicht den Feinschliff und nicht den
Kuerzungsweg. Ein bezahlter Lauf ist damit kein vollstaendiger Nachweis fuer
die Zusagen dieser Karte. Dieses Skript fuehrt denselben Codepfad
(``szene.starte`` -> ``szene.schreibe`` -> ``nachpass.nach_szene``) mit einer
**Attrappe** statt eines Modells und zeigt die Zahlen als Tabelle.

**Kein Test, kein Ersatz fuer pytest -- aber auch kein Geld.** Es hat keine
Sollwerte; die Zusagen stehen in ``tests/test_nachpass*.py``. Es ist ein
Berichtswerkzeug wie ``scripts/dramaturgie_pruefen.py --nur-mechanik``.

**Die Datenbank ist eine Wegwerf-Datei** (``tempfile``), nie ``IT_DB`` -- wie
``scripts/pruefe_prompts.py``. Das Material ist erfunden.

    $PY -m scripts.laengen_probe
    $PY -m scripts.laengen_probe --formen dialog,chor,rap,lied --faktor 0.25
    $PY -m scripts.laengen_probe --markdown   # fuer BEFUND.md
"""

from __future__ import annotations

import argparse
import os
import tempfile

#: Erfundenes Material, jedes Stueck absichtlich auffaellig: zu lang UND mit
#: mindestens einem der vier Sprachmuster. Eine Probe, deren Material nichts
#: ausloest, beweist eine leere Tabelle.
TEXTE: dict[str, str] = {
    "lang_und_dashes": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: She waited—and waited—and waited—and then she left.\n"
    ),
    "lang_und_nicht_sondern": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: It was not a home but a waiting room.\n"
    ),
    "lang_und_dreier": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: She was tired, angry, and alone.\n"
    ),
    "lang_und_fazit": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: Maybe home is just where you stop explaining.\n"
    ),
}

#: Die Antwort des Nachpasses: kurz und sauber. Damit zeigt die Tabelle den
#: Erfolgsfall; den Fehlschlagfall zeigen die Tests.
SAUBER = "MIRA: You are late.\nPAL: I was here.\n"

_KOPF = ("TITEL: At the pier\nKURZ: They meet.\n"
         "ZUSAMMENFASSUNG: Mira and Pal meet at the pier.\n"
         "ANDERS GEMACHT: nothing\n\n")


class Attrappe:
    """Erst der lange Text, danach der saubere -- und sie zaehlt mit."""

    def __init__(self, lang: str):
        self.antworten = [_KOPF + lang, _KOPF + SAUBER]
        self.aufrufe: list[str] = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append(art)
        return self.antworten[min(len(self.aufrufe) - 1, 1)]


class TelegramStumm:
    """Nimmt alles an und sagt nichts. Kein Netz."""

    def sende(self, *a, **k):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: None


def probe(formen: list[str], faktor: float = 1.0) -> list[dict]:
    """Fuehrt je Form eine Szene durch den echten Codepfad und liefert je
    Szene eine Zeile.

    ``IT_WORKSHOP`` wird hier gesetzt, nicht vom Aufrufer erwartet: das Skript
    misst ausdruecklich das Padua-Verhalten."""
    os.environ["IT_WORKSHOP"] = "padua-2026"
    from interview_theater import (
        db, einstellungen, laengen, nachpass, phasen, repo, sprachpass,
        szene, workshop,
    )

    workshop.vergiss()
    verzeichnis = tempfile.mkdtemp(prefix="laengen-probe-")
    conn = db.verbinde(os.path.join(verzeichnis, "probe.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "probe", "Probe")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "At the canal, at night")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Two lose each other.\nEnd: open")
    repo.setze_figur(conn, 1, "Mira", "wants to be asked")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    if faktor != 1.0:
        laengen.setze_faktor(conn, 1, faktor)
    e = einstellungen.Einstellungen(
        bot_token="T", bot_name="probe",
        db_pfad=os.path.join(verzeichnis, "probe.db"),
        audio_verz=os.path.join(verzeichnis, "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K",
        llm_modell="attrappe", stt_basis="https://stt.test",
        stt_produkt="P", erkenner_modell="attrappe",
    )
    for nummer, form in enumerate(formen, start=1):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        for feld, wert in (("form", form), ("ort", "pier"),
                           ("was_passiert", "They meet.")):
            repo.setze_szenenfeld(conn, szene_id, feld, wert)
        repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "probe")

    zeilen: list[dict] = []
    namen = list(TEXTE)
    tg = TelegramStumm()
    for nummer, form in enumerate(formen, start=1):
        klm = Attrappe(TEXTE[namen[(nummer - 1) % len(namen)]])
        ziel = szene.ziel_fuer(conn, 1, f"Schreib Szene {nummer}")
        budget = szene.budget_fuer_szene(conn, 1, ziel)
        thread = szene.starte(conn, tg, klm, e, 1, f"Schreib Szene {nummer}")
        if thread is not None:
            thread.join(timeout=60)
        # Nach dem Lauf: was steht in der Szene, und was fand der Zaehler?
        aktuell = next(s for s in repo.hole_szenen(conn, 1)
                       if s["nummer"] == nummer)
        vorher_text = _KOPF + TEXTE[namen[(nummer - 1) % len(namen)]]
        nachher_text = aktuell["volltext"] or ""
        zeilen.append({
            "nummer": nummer,
            "form": form,
            "budget": budget,
            "woerter_vorher": laengen.zaehle_woerter(vorher_text),
            "woerter_nachher": laengen.zaehle_woerter(nachher_text),
            "zaehler_vorher": sprachpass.rohzahlen(vorher_text),
            "zaehler_nachher": sprachpass.rohzahlen(nachher_text),
            "laeufe": len(klm.aufrufe),
            "arten": ",".join(klm.aufrufe),
        })
    conn.close()
    return zeilen


def tabelle(zeilen: list[dict]) -> str:
    """Die Zeilen als Markdown-Tabelle -- dieselbe Form, die in
    ``BEFUND.md`` steht."""
    kopf = ("| Szene | Form | Budget | Woerter vorher | Woerter nachher | "
            "Zaehler vorher | Zaehler nachher | Laeufe |")
    strich = "|---|---|---|---|---|---|---|---|"
    def kurz(z: dict) -> str:
        return ", ".join(f"{k[:4]}={v}" for k, v in z.items() if v)
    reihen = [
        f"| {z['nummer']} | {z['form']} | {z['budget']} | "
        f"{z['woerter_vorher']} | {z['woerter_nachher']} | "
        f"{kurz(z['zaehler_vorher']) or '-'} | "
        f"{kurz(z['zaehler_nachher']) or '-'} | {z['laeufe']} ({z['arten']}) |"
        for z in zeilen
    ]
    return "\n".join([kopf, strich] + reihen)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--formen", default="dialog,chor,rap,lied,monolog",
                   help="Kommaliste der Formen, eine Szene je Form")
    p.add_argument("--faktor", type=float, default=1.0,
                   help="Laengen-Faktor (0,25 = Instagram)")
    p.add_argument("--markdown", action="store_true",
                   help="nur die Tabelle, zum Einfuegen in BEFUND.md")
    a = p.parse_args(argv)
    zeilen = probe([f.strip() for f in a.formen.split(",") if f.strip()],
                   a.faktor)
    text = tabelle(zeilen)
    if not a.markdown:
        text = (f"Laengen-Probe, Faktor {a.faktor:g}, Attrappe statt Modell "
                f"-- kostet nichts.\n\n{text}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Schritt 4: Tests laufen lassen und das Skript fahren**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_laengen_probe.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m scripts.laengen_probe --markdown`
Erwartet: eine Markdown-Tabelle mit fuenf Zeilen. Jede Zeile hat
`Laeufe = 2 (szene,szene_nachpass)` und `Woerter nachher` weit unter
`Woerter vorher`; die Spalte `Zaehler nachher` ist `-`.

Run: `$PY -m scripts.laengen_probe --formen dialog,dialog,dialog,dialog --markdown`
Erwartet: vier Zeilen mit **mindestens zwei verschiedenen** Budgets -- der
sichtbare Beweis, dass der Rhythmus nicht flach ist.

Run: `$PY -m scripts.laengen_probe --faktor 0.25 --markdown`
Erwartet: dieselben Formen mit deutlich kleineren Budgets.

- [ ] **Schritt 5: Die Ausgabe in den Befund eintragen**

Abschnitt 3 von `docs/padua-r-laengen-2026-09-30/BEFUND.md` mit der
tatsaechlichen Ausgabe fuellen, darunter zwei Saetze: das verwendete Kommando
und der Hinweis, dass es eine Attrappe war und nichts gekostet hat.

- [ ] **Schritt 6: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add scripts/laengen_probe.py tests/test_laengen_probe.py \
        docs/padua-r-laengen-2026-09-30/BEFUND.md
git commit -m "laengen_probe.py: kostenloser Nachweis fuer Budget, Nachzaehlen und Sprachpass (R)"
```

---

## Aufgabe 19: Mutationsnachweis je Kernregel (kostenlos)

**Files:** keine dauerhaften. Jede Mutation wird **sofort** zurueckgenommen.

**Warum.** Ein gruener Test beweist nicht, dass er etwas bewacht. Acht Regeln
tragen diese Karte; fuer jede wird hier gezeigt, welche eine Zeile sie tragt
und welcher Test rot wird, wenn man sie verletzt.

**Das Verfahren fuer jede Zeile der Tabelle:**

```bash
# 1. mutieren (die Aenderung aus Spalte "Mutation")
# 2. den genannten Test fahren -- er MUSS rot werden:
$PY -m pytest -q -p no:cacheprovider <Test>
# 3. zurueck:
git checkout -- <Datei>
# 4. beweisen, dass nichts liegenblieb:
git status --porcelain     # leer (ausser .cc-*)
```

| # | Regel | Mutation (Datei, Zeile, Aenderung) | Dieser Test wird rot |
|---|---|---|---|
| 1 | **Der Wuerfel ist nie flach** | `interview_theater/workshop.py`, `VORGABE_WERTE["laengen"]["muster"]`: alle vier Eintraege durch `["mittel", "mittel", "mittel"]` ersetzen | `tests/test_laengen.py::test_jedes_muster_traegt_mindestens_zwei_verschiedene_stufen` **und** `tests/test_laengen_budget.py::test_kein_muster_der_vorgabe_ist_flach` **und** `tests/test_laengen_budget.py::test_eine_folge_aus_einer_form_ist_nicht_flach` |
| 2 | **Dasselbe Seed liefert dasselbe Muster** | `interview_theater/laengen.py`, `muster_fuer`: `abs(int(seed)) % len(liste)` durch `random.randrange(len(liste))` ersetzen (plus `import random`) | `tests/test_laengen_budget.py::test_dasselbe_seed_liefert_dasselbe_muster` **und** `::test_dasselbe_seed_liefert_dasselbe_budget` |
| 3 | **Das Muster wird zyklisch gelesen** | `interview_theater/laengen.py`, `stufe_fuer`: `(n - 1) % len(muster)` durch `min(n - 1, len(muster) - 1)` ersetzen | `tests/test_laengen_budget.py::test_das_muster_wird_zyklisch_gelesen` |
| 4 | **Faktor 0,25** | `interview_theater/laengen.py`, `_aus_stufe`: `* float(faktor)` streichen | `tests/test_laengen_budget.py::test_der_faktor_verkuerzt_alle_budgets` **und** `tests/test_laengen_faktor.py::test_der_faktor_wirkt_auf_das_naechste_budget` |
| 5 | **Die 130-%-Schwelle** | `interview_theater/laengen.py`, `zu_lang`: `* nachzaehl_schwelle(profil)` streichen (also ab 100 % melden) | `tests/test_laengen_budget.py::test_zu_lang_greift_erst_ab_der_schwelle` |
| 6 | **Genau EIN Lauf** | `interview_theater/nachpass.py`, `nach_szene`: den Block nach `VORFALL_IMMER_NOCH` durch einen zweiten Aufruf ersetzen (`szene_modul.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART_SZENE)`) | `tests/test_nachpass.py::test_zwei_zu_lange_ergebnisse_ergeben_trotzdem_einen_lauf` **und** `tests/test_laengen_aus.py::test_padua_haengt_genau_einen_lauf_an` |
| 7 | **Der Grenzwert des Zaehlers** | `interview_theater/sprachpass.py`, `ueberschreitungen`: `>=` durch `>` und den Grenzwert-Vergleich auf `> 1000` setzen (nie melden) | `tests/test_sprachpass_notiz.py::test_ab_der_grenze_wird_gemeldet` **und** `tests/test_nachpass.py::test_nur_sprache_ohne_laenge_laeuft_auch` |
| 8 | **Der Zitatschutz** | `interview_theater/nachpass.py`, `nach_szene`: den `if verloren:`-Block durch `pass` ersetzen (Ergebnis behalten) | `tests/test_nachpass.py::test_ein_veraendertes_zitat_verwirft_den_lauf` |
| 9 | **Der Zitatschutz auch in Phase 6** | `interview_theater/nachpass.py`, `nach_geschichte`: `if verloren:` durch `if False:` ersetzen | `tests/test_nachpass_prosa.py::test_ein_verlorenes_zitat_wird_verworfen` |
| 10 | **Die Abschnittszahl-Wache** | `interview_theater/nachpass.py`, `nach_geschichte`: `if len(abschnitte) != anzahl:` durch `if False:` ersetzen | `tests/test_nachpass_prosa.py::test_eine_andere_abschnittszahl_wird_verworfen` **und** `::test_bei_verwerfen_wird_nichts_geschrieben` |
| 11 | **Dortmund ist aus** | `interview_theater/workshop.py`, `VORGABE_WERTE["laengen"]["aktiv"]`: `False` -> `True` | `tests/test_laengen.py::test_die_vorgabe_hat_den_schalter_aus` **und** `tests/test_laengen_aus.py::test_ein_szenenlauf_bleibt_ein_aufruf` **und** `tests/test_laengen_aus.py::test_kein_laengenblock_im_prompt` |
| 12 | **Dortmunds Prosa-Prompt bleibt zeichengleich** | `interview_theater/kurzgeschichte.py`, `ZEILE_GESAMTLAENGE`: eine Zahl aendern (`1.500` -> `1.400`) | `tests/test_laengen_prosa.py::test_ohne_budget_ist_die_systemanweisung_zeichengleich` **und** `tests/test_laengen_prosa.py::test_die_ersetzbare_zeile_steht_wirklich_in_der_anweisung` |
| 13 | **Die deutsche Negativliste bleibt unberuehrt** | `interview_theater/prompts/theater-tells.md`: ein Zeichen aendern | `tests/test_sprachpass_prompt.py::test_die_deutsche_liste_bleibt_unberuehrt` **und** `tests/test_profil_bitgleich.py` |
| 14 | **Der Laengenblock wird nie gekuerzt** | `interview_theater/szene.py`, `_REIHENFOLGE`: `"laenge"` streichen | `tests/test_laengen_szene.py::test_der_laengenblock_steht_direkt_hinter_der_aufgabe` **und** `::test_mit_profil_steht_das_budget_im_nutzertext` |
| 15 | **Kein Modellaufruf im Befund** | `interview_theater/nachpass.py`, `befund`: eine Zeile `klm = None` einfuegen | `tests/test_nachpass.py::test_der_befund_ruft_kein_modell` |

- [ ] **Schritt 1: Die Tabelle abarbeiten**

Fuer **jede** der 15 Zeilen die vier Schritte oben. Wird ein genannter Test
**nicht** rot, ist das ein Befund und keine Formalie: die Regel ist dann nicht
bewacht. Dann wird ein Test ergaenzt, der sie bewacht -- und die Mutation
danach erneut gefahren.

- [ ] **Schritt 2: Der Arbeitsbaum ist sauber**

Run: `git status --porcelain`
Erwartet: leer (bzw. nur `.cc-*`). **Keine** Mutation darf stehenbleiben.

Run: `git diff --stat HEAD`
Erwartet: keine Ausgabe.

- [ ] **Schritt 3: Suite**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist **genau** der Stand nach
Aufgabe 18 -- diese Aufgabe legt keinen Test an, sie nimmt nur
Mutationen und wieder zurueck.

- [ ] **Schritt 4: Das Ergebnis in den Befund eintragen und committen**

An `docs/padua-r-laengen-2026-09-30/BEFUND.md` einen Abschnitt
"7. Mutationsnachweis" mit der Tabelle oben und je Zeile einem Haken bzw. dem
Befund anhaengen.

```bash
git add docs/padua-r-laengen-2026-09-30/BEFUND.md
git commit -m "Befund: Mutationsnachweis fuer 15 Kernregeln (R)"
```

---

## Aufgabe 20: Doku nachziehen (kostenlos)

**Files:**
- Modify: `AGENTS.md` (Modultabelle, Modulkarte, ein neuer Absatz unter
  "Bindende Entwurfsentscheidungen")
- Modify: `workshop/padua-2026/LIESMICH.md`
- Modify: `simulation/README.md`
- Test: `tests/test_doku_laengen.py` (neu)

**Warum als eigene Aufgabe.** `AGENTS.md` ist die Karte, mit der der naechste
Mensch anfaengt. Drei neue Module, eine neue Spalte, ein neuer Profilabschnitt
und zwei neue `art`-Werte, die nirgends stehen, sind genau der Zustand, gegen
den das Dokument geschrieben ist.

- [ ] **Schritt 1: Den failenden Test schreiben** -- `tests/test_doku_laengen.py`

```python
"""Die Doku nennt, was diese Karte gebaut hat (30.09.2026, Karte R).

Kein Stilwaechter: geprueft wird nur, dass ein Mensch, der AGENTS.md liest,
die drei neuen Module, die neue Spalte, den Profilabschnitt und die beiden
neuen ``art``-Werte ueberhaupt findet. Ein Modul, das dort fehlt, wird beim
naechsten Umbau versehentlich umgangen.
"""

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
AGENTS = (WURZEL / "AGENTS.md").read_text(encoding="utf-8")
LIESMICH = (WURZEL / "workshop" / "padua-2026" / "LIESMICH.md").read_text(
    encoding="utf-8")


@pytest.mark.parametrize("modul", ["laengen.py", "sprachpass.py", "nachpass.py"])
def test_jedes_neue_modul_steht_in_der_modultabelle(modul):
    assert modul in AGENTS, modul


@pytest.mark.parametrize("name", ["laengen", "sprachpass", "nachpass"])
def test_jedes_neue_modul_steht_in_der_modulkarte(name):
    """Die Modulkarte sagt, in welche Richtung die Abhaengigkeiten zeigen --
    ``laengen`` und ``sprachpass`` sind Fachlogik, ``nachpass`` auch."""
    karte = AGENTS[AGENTS.index("## Modulkarte"):]
    assert f"`{name}.py`" in karte, name


def test_die_neue_spalte_steht_in_agents():
    assert "laengen_faktor" in AGENTS


def test_der_profilabschnitt_steht_in_agents():
    assert "[laengen]" in AGENTS
    assert "[sprachpass]" in AGENTS


@pytest.mark.parametrize("art", ["szene_nachpass", "kurzgeschichte_nachpass"])
def test_die_neuen_aufruf_arten_stehen_in_agents(art):
    """Wie ``dramaturgie_b1``: damit Dashboard und Kostenzeile den Weg
    getrennt sehen -- und damit jemand weiss, wonach er zaehlen kann."""
    assert art in AGENTS, art


def test_agents_nennt_die_zusage_an_dortmund():
    assert "aktiv = false" in AGENTS.lower()


def test_agents_nennt_den_einen_lauf():
    """Die Zahl, an der der Kostendeckel haengt."""
    abschnitt = AGENTS[AGENTS.index("Laengen-Rhythmus"):]
    assert "genau ein" in abschnitt.lower() or "GENAU EIN" in abschnitt


def test_die_liesmich_des_padua_profils_nennt_die_rahmenwerte():
    assert "[laengen" in LIESMICH
    assert "vorschlag" in LIESMICH.lower()


def test_der_befund_ist_verlinkt():
    assert "padua-r-laengen-2026-09-30" in AGENTS
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_doku_laengen.py`
Erwartet: FAIL, `assert 'laengen.py' in ...`.

- [ ] **Schritt 3: `AGENTS.md` ergaenzen**

**(a) Drei Zeilen in die Modultabelle**, alphabetisch an ihren Platz:

```markdown
| `laengen.py` | Laengen-Rhythmus je Szene (30.09.2026, Karte R): der eine Wortzaehler (`zaehle_woerter`), der Rahmen je Form aus dem Profil, die Rhythmus-Muster, das Budget je Szene, der Faktor und die Prompt-Bausteine. **Kein Modellaufruf, keine Datenbank** (ausser `setze_faktor`, das ueber `repo` geht). Ohne `[laengen] aktiv = true` im Profil liest es niemand |
| `sprachpass.py` | Der letzte Sprachpass (30.09.2026, Karte R): vier Regex-Zaehler (Gedankenstriche, "not X but Y", Adjektiv-Dreierketten, Fazitsatz), Grenzwerte aus dem Profil, die Regie-Notiz und der **Zitatschutz** ueber `zitat.pruefe`. **Kein Modellaufruf**; `gepruefte_zitate` ist die einzige Funktion mit Datenbankzugriff |
| `nachpass.py` | Der EINE Ueberarbeitungslauf am Ende eines Schreibvorgangs (30.09.2026, Karte R): `nach_szene` (Phase 7) und `nach_geschichte` (Phase 6). Laeuft **im Thread und unter der Sperre** des Schreibwegs, deshalb `szene.schreibe`/`kurzgeschichte.hole_text` und nie `starte`. Eigene `art`-Werte (`szene_nachpass`, `kurzgeschichte_nachpass`) |
```

**(b) In der Modulkarte**, Zeile "Fachlogik": `· laengen.py · sprachpass.py ·
nachpass.py` anhaengen. Und in "Wo man anfaengt, je nach Frage" zwei Zeilen:

```markdown
| Warum ist die Szene so lang? | `laengen.budget_fuer` -> `muster_fuer` -> `stufe_fuer` |
| Warum lief die Szene zweimal? | `nachpass.nach_szene` -> `befund` -> `_notiz` |
```

**(c) Ein Absatz unter "Bindende Entwurfsentscheidungen"** (der eigentliche
Text):

```markdown
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
  Seitdem, **nur bei aktivem Profil** (`[laengen] aktiv`, im Vorgabeprofil und
  in Dortmund `false`): der Code wuerfelt je Gruppe ein **Rhythmus-Muster**
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
```

**(d) Bei den Fallen bzw. im Abschnitt "Prompt geaendert?"** einen Satz, dass
`workshop/padua-2026/profil.toml` die Zahlen traegt und eine Aenderung dort
**keinen** Korpuslauf und **keinen** Neustart des Webdienstes braucht, aber
einen Neustart des Bots (die TOML wird nur beim Start gelesen).

- [ ] **Schritt 4: `workshop/padua-2026/LIESMICH.md` ergaenzen**

Ein Abschnitt, der sagt: wo die Rahmenwerte stehen, dass sie Vorschlaege sind,
woran sie geeicht werden (Verweis auf den Befund), dass der Faktor 0,25 die
Instagram-Entscheidung ist, und dass `[laengen] aktiv = false` das Verhalten
von vor dieser Karte wiederherstellt.

- [ ] **Schritt 5: `simulation/README.md` ergaenzen**

Zwei Saetze: dass der Simulator das Padua-Profil **nur** ueber `IT_WORKSHOP`
sieht (er hat keinen eigenen Schalter), und dass er Phase 7 und den
Kuerzungsweg nicht erreicht -- dafuer gibt es `scripts/laengen_probe.py`.

- [ ] **Schritt 6: Tests laufen lassen**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_doku_laengen.py -v`
Erwartet: alle Tests der Datei gruen, `failed = 0` (die Zahl der Tests steht in der Datei -- sie hier vorherzusagen waere geraten).

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_anweisungen.py`
Erwartet: `passed` -- dort haengt der Test, der prueft, dass keine
Phasenanweisung einen Slash-Befehl bewirbt; die Doku faellt nicht darunter,
aber ein versehentlicher Eingriff in eine Prompt-Datei schon.

- [ ] **Schritt 7: Suite und Commit**

Run: `$PY -m pytest -q -p no:cacheprovider`
Erwartet: `failed` = 0, und `passed` ist um die in dieser Aufgabe hinzugekommenen Tests gewachsen (Basislinie 2768).

```bash
git add AGENTS.md workshop/padua-2026/LIESMICH.md simulation/README.md \
        tests/test_doku_laengen.py
git commit -m "Doku: Laengen-Rhythmus, Sprachpass und Nachpass in AGENTS.md und LIESMICH (R)"
```

---

## Aufgabe 21 (BEZAHLT): Ein Simulationslauf unter dem Padua-Profil

> **Diese Aufgabe kostet Geld.** Sie laeuft erst, wenn **alle** Aufgaben 0-20
> gruen und committet sind. Vorher nicht anfangen.

**Files:**
- Modify: `docs/padua-r-laengen-2026-09-30/BEFUND.md` (Abschnitte 4 und 6)

**Was der Simulator kann und was nicht -- selbst nachgesehen.**
`simulation/` und `scripts/simulation.py` kennen `IT_WORKSHOP` **nicht** (kein
Treffer im `grep`). Das Profil wirkt dort allein ueber die Umgebungsvariable
des Prozesses, und der Simulator liest die Phasen datengetrieben aus
`phasen.PHASEN` -- ein Profilwechsel reisst ihn also nicht mit, aber er
bekommt auch keinen eigenen Schalter.

Gemessen aus `simulation/berichte/verlauf.jsonl`: die letzten Laeufe erreichten
`phase_erreicht = 8` (alte Zaehlung) und schrieben **einen** Abschnitt
(`szenen: [{nummer: 1, form: "", zeichen: 2711, ...}]`, `form` leer = der
Prosaweg). **Phase 7 und den Kuerzungsweg erreicht er nicht** -- dafuer gibt
es Aufgabe 18 (kostenlos) und Aufgabe 22.

**Kosten, aus derselben Datei gelesen und nicht geschaetzt:** der teuerste
bisherige Lauf mit Szenentext ist `2026-09-06-regie-1` mit `chf_bot = 0.636`,
`aufrufe = 95`, `dauer_s = 1848`. Laeufe ohne eigenen Szenenlauf liegen bei
`0.206`-`0.408` CHF und 71-123 Aufrufen.

**Abbruchkriterium:** ueberschreitet `chf_bot` **1,30 CHF** (das Doppelte des
teuersten bisherigen Laufs) oder `aufrufe` **190** (das Doppelte von 95), wird
der Lauf abgebrochen (`Ctrl-C`), der Stand notiert und **nicht** wiederholt.
Der Kostendeckel der Serie ist 5 CHF je Gruppe und Tag (Birk E7).

- [ ] **Schritt 1: Trockenlesung ohne Szenenlauf (billig)**

```bash
cd /mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_316d3027
set -a; . ./betrieb/gruppe1.env; set +a     # NIE ausgeben
export IT_WORKSHOP=padua-2026
$PY -m scripts.simulation --set 1 --seed 7 --ohne-szene --bericht
```

Erwartet: der Lauf kommt durch, der Bericht landet unter
`simulation/berichte/` (gitignored). Aus ihm ablesen und notieren: `chf_bot`,
`aufrufe`, `phase_erreicht`. **Das Env-File wird nur so geladen und nie
ausgegeben** -- kein `cat`, kein `echo $IT_LLM_KEY`.

Faellt der Lauf mit einem Profilfehler aus, zuerst
`$PY -m scripts.pruefe_profil padua-2026` fahren: `geruest = true` in
`workshop/padua-2026/profil.toml` verhindert jeden Start (ANNAHME A7, in
Aufgabe 0 geprueft).

- [ ] **Schritt 2: Der Lauf mit Prosa (der teure)**

```bash
set -a; . ./betrieb/gruppe1.env; set +a
export IT_WORKSHOP=padua-2026
$PY -m scripts.simulation --set 1 --seed 7 --bericht
```

Erwartet: 2-4 Minuten fuer den Prosalauf, danach der Nachpass -- also **ein
Aufruf mehr** als bisher, mit `art = kurzgeschichte_nachpass`.

Waehrend des Laufs (in einem zweiten Terminal) die Aufrufe je `art` zaehlen.
Die Wegwerf-Datenbank des Laufs nennt der Bericht bzw. die erste Logzeile:

```bash
sqlite3 <wegwerf.db> \
  "SELECT art, count(*), sum(antwort_token) FROM aufruf GROUP BY art ORDER BY 2 DESC;"
```

**NICHT** gegen `betrieb/soap.db` -- der Simulator schreibt ohnehin in eine
Wegwerf-Datei, und ein Lesezugriff auf die Betriebsdatenbank ist verboten.

- [ ] **Schritt 3: Die Zahlen je Abschnitt holen**

Aus derselben Wegwerf-Datenbank, mit dem **einen** Wortzaehler des Repos:

```bash
IT_WORKSHOP=padua-2026 $PY - <<'PY'
import os, sqlite3, sys
sys.path.insert(0, ".")
from interview_theater import laengen, sprachpass
pfad = os.environ["PROBE_DB"]          # der Pfad aus Schritt 2
c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
chat = c.execute("SELECT DISTINCT chat_id FROM szene").fetchone()[0]
print("| Szene | Form | Budget | Woerter | ueber Budget? | Zaehler |")
print("|---|---|---|---|---|---|")
for s in c.execute("SELECT * FROM szene WHERE chat_id=? AND entfernt_am IS NULL "
                   "ORDER BY nummer", (chat,)):
    text = (s["prosa"] or s["volltext"] or "")
    form = laengen.form_der_szene(s)
    budget = laengen.budget_fuer(s["nummer"], form, seed=chat)
    w = laengen.zaehle_woerter(text)
    zaehler = {k: v for k, v in sprachpass.rohzahlen(text).items() if v}
    print(f"| {s['nummer']} | {form} | {budget} | {w} | "
          f"{'ja' if laengen.zu_lang(w, budget) else 'nein'} | {zaehler or '-'} |")
for v in c.execute("SELECT art, detail FROM vorfall WHERE chat_id=? AND "
                   "art LIKE 'nachpass%' ORDER BY id", (chat,)):
    print("VORFALL", v["art"], v["detail"])
PY
```

Erwartet: je Abschnitt eine Zeile; **mindestens zwei verschiedene Budgets**
(der Rhythmus), und ein Vorfall `nachpass_gelaufen` mit den Wortzahlen vor und
nach dem Nachpass.

**Wenn der Lauf die Prosa-Phase nicht erreicht:** das notieren
(`phase_erreicht` aus dem Bericht), nicht wiederholen, und in Abschnitt 4 des
Befunds ausdruecklich schreiben, dass der Nachweis fuer diesen Weg aus
Aufgabe 18 kommt.

- [ ] **Schritt 4: Der Mix-Lauf (die Regel des Repos)**

Die Regel aus AGENTS.md lautet: nach jeder Prompt-Aenderung **ein** Lauf mit
`--set` und **einer** mit `--mix`, beide mit demselben Seed wie beim letzten
Mal. Diese Karte aendert Prompt-Text (den Budget-Block, die Summenzeile, die
englische Negativliste), also gilt sie.

```bash
set -a; . ./betrieb/gruppe1.env; set +a
export IT_WORKSHOP=padua-2026
$PY -m scripts.simulation --mix 1,2,3 --seed 3 --ohne-szene --bericht
```

`--ohne-szene`, weil der Prosalauf schon in Schritt 2 gemessen wurde und der
Mix hier die **Navigation** prueft, nicht den Text -- das haelt die Kosten bei
rund 0,2-0,4 CHF.

**`--set birk` und die `tag1`-Sets werden NICHT gefahren**: sie tragen
Personas und Material aus den echten Dortmunder Gruppen (`simulation/tag1.py`,
`IT_SIM_BIRK`). Diese Karte baut fuer Padua und braucht sie nicht.

- [ ] **Schritt 5: Kosten je `art` in den Befund**

```bash
sqlite3 <wegwerf.db> \
  "SELECT art, count(*) AS laeufe, sum(antwort_token) AS aus,
          sum(tatsaechliche_token) AS ein
   FROM aufruf GROUP BY art ORDER BY laeufe DESC;"
```

Daraus in Abschnitt 6 des Befunds eintragen:
- `szene` bzw. `kurzgeschichte`: die Zahl der **Schreiblaeufe**
- `szene_nachpass` bzw. `kurzgeschichte_nachpass`: die Zahl der
  **Nachpass-Laeufe**
- **Laeufe je Szene** = (Schreiblaeufe + Nachpass-Laeufe) / Zahl der Szenen.
  **Die Zahl, an der die Karte gemessen wird: hoechstens 2,0** (ein Schreiblauf
  plus hoechstens ein Nachpass).
- `chf_bot` aus dem Bericht, danebengestellt der gemessene Vergleichswert
  `0.636` (`2026-09-06-regie-1`).

- [ ] **Schritt 6: Befund fuellen und committen**

Abschnitte 4 und 6 von `docs/padua-r-laengen-2026-09-30/BEFUND.md` mit den
echten Zahlen fuellen. Dazu ein **Vorher/Nachher-Auszug** des Sprachpasses:
hoechstens zehn Zeilen aus dem erfundenen Material, die Stelle, an der ein
Zaehler angesprungen ist, und dieselbe Stelle danach. **Kein** Satz aus einem
echten Interview, kein Klarname.

```bash
git add docs/padua-r-laengen-2026-09-30/BEFUND.md
git commit -m "Befund: Simulationslauf Padua -- Budgets, Wortzahlen und Kosten je art (R)"
```

Die Berichte selbst (`simulation/berichte/*.md`, `simulation/laeufe/*`) sind
gitignored und werden **nicht** committet -- sie enthalten vollstaendige
Modellantworten. Die eine Ausnahme ist
`simulation/berichte/verlauf.jsonl`, die der Lauf selbst fortschreibt; sie
gehoert mit in den Commit, wenn `git status` sie zeigt.

---

## Aufgabe 22 (BEZAHLT): Ein gezielter Einzel-Szenenlauf in Phase 7

> **Diese Aufgabe kostet Geld.** Sie laeuft nach Aufgabe 21.

**Files:**
- Modify: `docs/padua-r-laengen-2026-09-30/BEFUND.md` (Abschnitt 5)

**Warum sie noetig ist.** Der Simulator erreicht Phase 7 nicht (ANNAHME A10,
in Aufgabe 21 Schritt 1 bestaetigt oder widerlegt). Genau dort aber laeuft der
Weg, der die Karte tragt: **eine** Szene, **eine** bestaetigte Form, Budget je
Szene, Nachzaehlen, Kuerzungslauf, Sprachpass, Zitatschutz. Das wird einmal
gegen das echte Modell gefahren -- gegen eine **Kopie**-Datenbank, mit
erfundenem Material.

**Ein Lauf, nicht mehr.** Ein Szenenlauf mit Reasoning ist der teuerste
Einzelposten des Repos (2-4 Minuten, gemessen). Einer genuegt: was die
**Mechanik** betrifft, zeigt `scripts/laengen_probe.py` es kostenlos und
wiederholbar; hier wird nur gemessen, ob ein **echtes** Modell auf den
Budget-Block und die Notiz reagiert.

- [ ] **Schritt 1: Eine Kopie-Datenbank mit erfundenem Material anlegen**

Ein Wegwerf-Skript in `/tmp` (nicht im Repo), das eine leere Datenbank anlegt,
eine Gruppe, ein Setting, eine Geschichte, zwei Figuren mit Sprachstil, **ein
geprueftes Belegzitat** aus einem erfundenen Transkript und drei geplante
Szenen mit bestaetigter Form (`dialog`, `chor`, `rap`), dann `phasen.setze(...,
7, ...)`. Das Muster dafuer steht in `scripts/laengen_probe.py::probe` --
uebernehmen und nur `IT_DB` auf die Kopie zeigen lassen.

**`IT_DB` zeigt NIE auf `betrieb/soap.db`.** Wie
`scripts/dramaturgie_pruefen.py` es verweigert: die Betriebsdatenbank wird
nicht angefasst, auch nicht lesend.

- [ ] **Schritt 2: Den Lauf fahren**

```bash
set -a; . ./betrieb/gruppe1.env; set +a
export IT_WORKSHOP=padua-2026
export IT_DB=/tmp/laengen-einzel/kopie.db
$PY - <<'PY'
import logging, os, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO)
import httpx
from interview_theater import db, einstellungen, repo, szene
from interview_theater.llm import LLM

CHAT_ID = 1            # die Gruppe aus Schritt 1

# Genau wie bot.main:466-496 -- dieselben drei Zeilen, nur ohne Long-Poll.
e = einstellungen.laden()
conn = db.verbinde(e.db_pfad)
db.initialisiere(conn)
klient = httpx.Client(timeout=30.0)
klm = LLM(e, klient, conn)

# Die USA-Einwilligung: Padua schreibt mit claude-opus-5-5 ueber den Proxy
# (Birk E9), und ``szene.starte`` verweigert ohne sie den Lauf. **Ein bool** --
# ein nicht-leerer String waere wahr, und "nein" endete als Zustimmung
# (AGENTS.md, Fallstrick zu ``repo.setze_szene_usa``).
repo.setze_szene_usa(conn, CHAT_ID, True)

class Stumm:
    """Nimmt alles an und sagt nichts. Der Chat interessiert hier nicht."""
    def sende(self, *a, **k): return None
    def __getattr__(self, n): return lambda *a, **k: None

thread = szene.starte(conn, Stumm(), klm, e, CHAT_ID, "Schreib Szene 1")
assert thread is not None, "kein Lauf angestossen -- siehe Log (Sperrtext?)"
thread.join(timeout=1200)
PY
```

Die Zeilen `einstellungen.laden()`, `db.verbinde(e.db_pfad)` und
`LLM(e, klient, conn)` sind woertlich die aus `interview_theater/bot.py:490-496`
-- selbst nachgelesen, damit dieser Lauf denselben Klienten baut wie der
Betrieb und nicht einen zweiten, aehnlichen.

`e.db_pfad` kommt aus `IT_DB`; dass die Variable auf die **Kopie** zeigt, ist
Schritt 2 oben. Faellt `assert thread is not None`, steht der Grund im Log --
in der Regel `szene.sperrtext` (ein Pflichtfeld oder ein Sprachprofil fehlt),
und dann fehlt etwas im Aufbau aus Schritt 1, nicht im Code.

- [ ] **Schritt 3: Messen**

Dasselbe Auswerte-Skript wie in Aufgabe 21 Schritt 3, gegen die Kopie. Notiert
werden je Szene: Budget, Wortzahl des ersten Laufs, Wortzahl nach dem
Nachpass, die Sprachpass-Zaehler vorher und nachher, und die Vorfaelle
`nachpass_*`.

Und die Aufrufe:

```bash
sqlite3 "$IT_DB" \
  "SELECT art, count(*), sum(antwort_token), sum(dauer_ms)/1000 AS s
   FROM aufruf GROUP BY art;"
```

Erwartet: `szene` = 1 und `szene_nachpass` <= 1. **Steht dort
`szene_nachpass` = 2 oder mehr, ist das ein Befund und ein Abbruch** -- die
Zusage "genau ein Lauf" ist verletzt, und die Ursache gehoert gesucht (der
Test `tests/test_nachpass.py::test_zwei_zu_lange_ergebnisse_ergeben_trotzdem_einen_lauf`
muesste sie eigentlich fangen).

- [ ] **Schritt 4: Der Vorher/Nachher-Auszug**

Aus `repo.szenenfassungen(conn, szene_id)` die Fassung 1 und die Fassung 2
holen und **hoechstens zehn Zeilen** je Seite in Abschnitt 5 des Befunds
setzen -- die Stelle, an der ein Zaehler angesprungen ist, und dieselbe Stelle
danach. Material ist erfunden; trotzdem wird nur der Auszug gezeigt und nicht
der ganze Text (Berichte mit vollstaendigen Modellantworten sind im Repo
gitignored, und dieser Befund ist es nicht).

- [ ] **Schritt 5: Befund fuellen und committen**

```bash
git add docs/padua-r-laengen-2026-09-30/BEFUND.md
git commit -m "Befund: Einzel-Szenenlauf Phase 7 -- Budget, Nachpass, Zitatschutz am echten Modell (R)"
```

- [ ] **Schritt 6: Aufraeumen**

```bash
rm -rf /tmp/laengen-einzel
unset IT_DB IT_WORKSHOP
git status --porcelain      # leer ausser .cc-*
```

---

## Abschluss

- [ ] Alle Aufgaben 0-22 abgehakt.
- [ ] `$PY -m pytest -q -p no:cacheprovider` -> `failed` = 0, `passed`
      deutlich ueber der Basislinie 2768 (rund 200 neue Tests).
- [ ] `$PY -m scripts.pruefe_profil dortmund-2026` -> Exit 0 (Birk E3).
- [ ] `$PY -m scripts.pruefe_profil padua-2026` -> Exit 0.
- [ ] `$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/profile/`
      -> `passed`: Dortmund ist zeichengleich.
- [ ] `$PY -m scripts.pruefe_sprache --schluessel laengen,sprachpass` ->
      `0 Treffer` (nach A1).
- [ ] `git status --porcelain` leer (ausser `.cc-*`).
- [ ] `git log --oneline origin/main..HEAD` zeigt einen Commit je Aufgabe,
      **kein** Merge-Commit.
- [ ] `docs/padua-r-laengen-2026-09-30/BEFUND.md` hat alle sieben Abschnitte
      gefuellt -- oder nennt ausdruecklich, welcher Nachweis aus Aufgabe 18
      statt aus 21/22 kommt und warum.
- [ ] **Kein Merge, kein Push, kein PR.** Der Branch bleibt stehen.
- [ ] Die fuenf OFFENEN FRAGEN aus dem Plan-Kopf in der Abschlussmeldung
      wiederholen -- sie sind Entscheidungen fuer Birk und nicht fuer die
      Umsetzung.

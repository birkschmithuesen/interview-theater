# Prompt-Check Padua, Phase 1+2 -- BEFUND

Datum: 05.10.2026. Karte: `t_bf16f3a7` (abgespalten vom Prompt-Check-Gesamtplan
`docs/superpowers/plans/2026-10-05-padua-prompt-check-voll.md`, dort nur
Tasks 6/7/8/9/10 als Baustein-Referenz, beschraenkt auf Phase 1+2). Branch:
`wt/t_bf16f3a7`. Profil: `padua-2026`. Umgebung des Dump-Laufs (fest in
`scripts/erzeuge_prompts_padua_voll.umgebung()`): `szene_anbieter=claude`,
`szene_modell=claude-opus-5`, `llm_modell=moonshotai/Kimi-K2.6`,
`erkenner_modell=google/gemma-4-31B-it`.

Drei Kommandos, alle kostenlos (Dump und Mechanik rein lokal, die Lesung
laeuft -- wenn sie laeuft -- ueber das Abo, 0 CHF je Aufruf):

```
python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-p12 \
  --nur 01-gespraech-phase1,05-gespraech-phase2,13-begriffsboard,14-diskussion-verdichtung,15-fragen-ki
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-p12 \
  --nach docs/prompt-audit/2026-10-05-padua-p12/mechanik.md
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p12 --phase 1
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p12 --phase 2
```

## 1. Scope dieser Karte

Nur fuenf der 39 moeglichen Prompt-Dumps -- die aus Phase 1 (Begriffe) und
Phase 2 (Fragen):

| Datei | art | Phase |
|---|---|---|
| `01-gespraech-phase1.txt` | gespraech | 1 |
| `05-gespraech-phase2.txt` | gespraech | 2 |
| `13-begriffsboard.txt` | begriffsboard | 1 |
| `14-diskussion-verdichtung.txt` | diskussion_verdichtung | 1 |
| `15-fragen-ki.txt` | fragen_ki_vorschlag | 2 |

Die restlichen 34 Inventareintraege (Phasen 3-7, Dramaturgie-Richterfragen)
sind **nicht** Teil dieses Laufs -- `scripts/erzeuge_prompts_padua_voll.py`
traegt dafuer bewusst **keinen** Treiber (`TREIBER` hat exakt fuenf
Eintraege, `SCOPE_P1_P2`). Ein Lauf ohne `--nur` faehrt automatisch nur
diese fuenf; ein Versuch, einen der anderen 34 Namen zu dumpen, bricht mit
`TreiberFehler` ab (gewollt).

## 2. Inventartabelle und Groessen (aus `uebersicht.tsv`, nach dem Fix in Abschnitt 8)

| art | pfad | Phase | weg/Modell | quelle | system_zeichen | nutzer_zeichen |
|---|---|---|---|---|---|---|
| gespraech | 01-gespraech-phase1 | 1 | claude / claude-opus-5 | abgefangen | 29767 | 1657 |
| gespraech | 05-gespraech-phase2 | 2 | claude / claude-opus-5 | abgefangen | 34370 | 1802 |
| begriffsboard | 13-begriffsboard | 1 | claude / claude-opus-5 | abgefangen | 6633 | 729 |
| diskussion_verdichtung | 14-diskussion-verdichtung | 1 | claude / claude-opus-5 | abgefangen | 1672 | 208 |
| fragen_ki_vorschlag | 15-fragen-ki | 2 | claude / claude-opus-5 | abgefangen | 2390 | 114 |

Alle fuenf laufen auf dem Claude-Weg (`weg=claude`) -- in Padua ist jede
Phase ausser 3 (Interviews) Opus-faehig, nur Phase 3 bleibt auf Kimi
(`modellwahl.py`, nicht Teil dieses Scopes). `quelle=abgefangen` fuer alle
fuenf: jeder Dump ist ein echter, synchron gefahrener Aufruf des
Produktionswegs (`ablauf.antworte`, `begriffsboard._lauf_einmal`,
`diskussion.starte`, `fragen_ki.starte`), kein nachgebauter Prompt --
`weg="gebaut"` kommt in diesem Scope nicht vor.

`prompt_inventar.NICHT_LIVE_IN_PADUA`: keine der fuenf Phase-1/2-Eintraege
steht dort; alle fuenf sind live erreichbare Pfade.

## 3. Groessen gegen die Basis vom 02.10.2026

Die einzige vergleichbare Datei aus `docs/prompt-audit/2026-10-02-padua-p2/`
ist `01-gespraech-phase1` (`system_zeichen=26943` damals). Nach dem Fix in
Abschnitt 8 steht sie bei 29767 -- rund **+2824 Zeichen** Drift seit dem
02.10.2026 (davon rund 220 Zeichen aus dem eigenen Fix dieser Karte, siehe
Abschnitt 8; der Rest -- rund 2600 Zeichen -- ist Drift aus anderen,
dazwischenliegenden Karten, vor allem der inzwischen gemergten
Abnahme-P1-2-Arbeit von `t_0b702d1d`, die denselben `system.md` mehrfach
geaendert hat, siehe `git log -3 -- interview_theater/sprachen/en/prompts/system.md`).
`05-gespraech-phase2`, `13-begriffsboard`, `14-diskussion-verdichtung` und
`15-fragen-ki` sind in der Basis nicht enthalten (`neu`) -- sie existieren
erst seit dem Padua-Phase-1+2-Umbau vom 03./04.10.2026.

## 4. Token-Anteil je Blockgruppe (nur die zwei Gespraechs-Dumps)

| Datei | tok_system | tok_status | tok_verlauf | tok_zusammenfassung |
|---|---|---|---|---|
| 01-gespraech-phase1 | 9904 | 191 | 319 | 37 |
| 05-gespraech-phase2 | 11438 | 247 | 311 | 37 |

Die Systemanweisung dominiert den Prompt klar (ueber 90 % der Token in
beiden Faellen) -- erwartbar fuer Phase 1/2, wo noch kaum Arbeitsstand
(`tok_status`) und kein Material (`tok_zusammenfassung`) vorliegt; der
Chatverlauf (`tok_verlauf`) traegt knapp 3 % bei. `13-begriffsboard`,
`14-diskussion-verdichtung` und `15-fragen-ki` haben keine Blockanteile
(leere Spalten in der TSV): sie laufen nicht ueber `kontext.baue`, sondern
mit isoliertem Nutzertext (Transkript bzw. Begriffe), wie von ihren
Modulen dokumentiert ("Der Nutzertext ist bewusst isoliert").

## 5. Gemessene Fenstergrenzen

Nicht gesondert nachgemessen in diesem beschraenkten Lauf (Schritt 2 aus
Task 9 des Gesamtplans ist nicht Teil dieses Auftrags) -- die beiden
Gespraechs-Dumps zeigen `tok_verlauf` nur ueber `kontext.umriss` aggregiert
(Abschnitt 4), nicht Zeile fuer Zeile. Wer die genaue Fensterschnitt-Stelle
je Phase braucht, faehrt `fixture_padua_voll.fensterbefund(conn, chat_id)`
wie in Task 9 Schritt 2 des Gesamtplans beschrieben.

## 6. Mechanische Treffer (aus `mechanik.md`, nach dem Fix)

**Deutsche Reste (Soll 0): 1 Fund, nicht behoben in diesem Lauf.**
`14-diskussion-verdichtung.txt:41`: `Das Transkript der Diskussion:` --
der komplette System-Teil dieses Dumps ist Englisch, nur die eine
Nutzertext-Kopfzeile ist hartcodiertes Deutsch
(`interview_theater/diskussion.py:96`, `_nutzertext`). Warum nicht in
diesem Lauf behoben: siehe Abschnitt 9.

**UX-Muster (`Yes, save` / `No, change it again`, Z276 in beiden
Gespraechs-Dumps):** echte Knopfbeschriftungen aus
`interview_theater/sprachen/en/texte.toml` (`_TEXT_SPEICHERN_KNOPF` /
`_TEXT_ANDERS_KNOPF`) -- liegt bei Karte `t_e5b1df39` (siehe Auftrag,
explizit ausgenommen). Nicht angefasst.

**Frageregeln (`ask whether`, Z291/330/511, "nebeneinander lesen"):**
manuell im Volltext geprueft (nicht nur die Fundstelle, der ganze Satz) --
in allen Faellen steht die Verneinung direkt davor ("you neither have to
... nor ask whether it arrived", "Never ask whether an interim result ...",
"Never ask whether something should go to the plenary"). Das sind
Formulierungen der Regel selbst ("frag nicht, ob ..."), keine Verstoesse
gegen "speichern beim ersten Mal, keine Rueckfrage davor" -- der
mechanische Scanner matcht nur die Zeichenkette "ask whether" ohne die
Verneinung zu erkennen und listet sie absichtlich zum
Nebeneinander-Lesen, nicht als automatischen Befund. **Kein Fund, kein
Fix noetig.**

**Frageregeln ("No chain of follow-up questions ...", "first one more
system question ... forbidden", Z345/361 und Umgebung):** ebenfalls
manuell geprueft -- das sind Regelsaetze, die das gewuenschte Verhalten
korrekt beschreiben (keine Fragenkette vor einer Szene; die US-Frage nicht
wiederholen), keine Widersprueche untereinander. **Kein Fund.**

**`15-fragen-ki.txt` (Z6, Z11, Z40):** derselbe Befund -- beim
Nebeneinanderlesen konsistent mit dem isolierten KI-Fragen-Lauf
(kein Zugriff auf die eigenen Fragen der Gruppe, Begruendung dafuer im
selben Absatz). **Kein Fund.**

**`13-begriffsboard.txt`:** keine mechanischen Treffer; manuell
quergelesen, keine Auffaelligkeit gefunden.

**Marker-Katalog (nicht aus `mechanik.md`, sondern aus manueller
Durchsicht von `system.md` gegen die funktionale Nutzung in Phase 2):**
siehe Abschnitt 8 -- behoben.

## 7. Opus-Befunde je Phase

**Nicht gelaufen.** Drei Versuche (ein Hintergrundlauf, der durch einen
Sitzungsneustart unterbrochen wurde, und zwei vordergruendige Laeufe mit
voller Wartezeit) scheiterten alle an
`simulation.claude.ClaudeFehler: Simulationsmodell nach 4 Versuchen nicht
erreichbar (zuletzt: ReadTimeout)` -- 3 Retries je 120 s plus ein finaler
Versuch, dann Abbruch. Vermutliche Ursache: der lokale Opus-Proxy
(`http://127.0.0.1:28764/v1/messages` bzw. `IT_SIM_URL`) war waehrend
dieser Session durch parallel laufende andere Padua-Karten ausgelastet,
die denselben Proxy nutzen -- der Proxy selbst antwortet auf einen
einfachen GET mit HTTP 404 (normal fuer einen reinen POST-Endpunkt), lebt
also.

Nachfahren, sobald der Proxy wieder frei ist:
```
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p12 --phase 1
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p12 --phase 2
```
Das Werkzeug selbst (`scripts/pruefe_prompts_lesung.py`) ist fertig,
getestet (12 offline Tests gegen eine Attrappe, kein Netzaufruf) und
committet (siehe Abschnitt 8); nur der echte Lauf gegen das Modell steht
aus. Keine erfundenen Befunde, keine geschaetzte Lesung -- dieser Abschnitt
bleibt bewusst leer, bis der Lauf tatsaechlich stattfindet.

## 8. Behoben in diesem Lauf

**Fix 1 -- Marker-Katalog im EN-Systemprompt unvollstaendig.**
`interview_theater/sprachen/en/prompts/system.md` behauptete "There are
twelve markers, no more" und listete die zwoelf generischen
`VORSCHLAG <ART>:`-Marker -- aber Padua's Phase-2-Umbau
(`workshop/padua-2026/prompts/phasen/2.md`, "Padua Phase 1+2 card, Task 13")
laesst den Bot zusaetzlich `VORSCHLAG EIGENE FRAGEN:` schreiben
(`interview_theater/knoepfe/fragen.py:uebernimm_eigene`, geparst ueber
denselben generischen `vorschlag`-Mechanismus, Block-Schluessel
`eigene_fragen`). Ein Modell, das die Zwoelf-Marker-Behauptung ernst nimmt,
koennte den 13. Marker fuer ungueltig oder erfunden halten. Klasse B
(Prompt widerspricht Prompt): `system.md` behauptet eine abschliessende
Liste, ein anderer, gleichzeitig geladener Prompt (die Padua-Phase-2-Datei)
verlangt einen Marker ausserhalb dieser Liste.

Fix: "twelve" -> "thirteen", ein neuer Aufzaehlungspunkt fuer
`VORSCHLAG EIGENE FRAGEN:` direkt nach `VORSCHLAG FRAGEN:` (gleicher Stil
wie die anderen elf), mit dem Hinweis, dass dieser Marker -- anders als
die anderen zwoelf -- **keinen Knopf** erzeugt (das ist die bestehende,
dokumentierte Sonderrolle aus `KORREKTUR-PHASE2-KEIN-KNOPF.md` /
`knoepfe/basis.py:526-534`; ohne diesen Hinweis haette die Ergaenzung
selbst einen neuen Widerspruch zur allgemeinen Regel "Each line of a
multi-line block becomes a button" erzeugt).

Nur `interview_theater/sprachen/en/prompts/system.md` geaendert --
**nicht** die deutsche Basisdatei `interview_theater/prompts/system.md`:
dort gilt "Zwoelf Marker gibt es, mehr nicht" weiterhin korrekt, weil
Dortmund (das einzige Profil, das die deutsche Fassung liest) den
Padua-only Phase-2-Umbau nicht hat und `VORSCHLAG EIGENE FRAGEN:` dort nie
vorkommt -- die deutsche Datei ist nicht falsch, nur Englisch (Padua) und
Deutsch (Dortmund) sind an dieser einen Stelle inhaltlich keine 1:1-Uebersetzung
mehr. Deutsche Prompt-Dateien bleiben unangetastet (eingefroren).

Test: `tests/test_phasen_prompts_teil2.py::test_system_en_marker_katalog_nennt_eigene_fragen`
(prueft, dass "twelve markers" weg ist, "thirteen markers" drinsteht und
der neue Marker genannt wird).

Nachgewiesen: Dumps neu erzeugt (`01-gespraech-phase1.txt`,
`05-gespraech-phase2.txt`), `grep -n "thirteen markers\|VORSCHLAG EIGENE
FRAGEN"` zeigt die neue Zeile in beiden System-Teilen, `mechanik.md` neu
geschrieben. Volltestlauf siehe Abschnitt 11 (unten).

Commit: siehe `git log` nach diesem BEFUND-Commit (diese Datei wird im
selben Commit wie der Fix erzeugt).

## 9. Liegt bei anderen Karten / anderen Dateien

**Deutscher Rest in `interview_theater/diskussion.py:96` (`_nutzertext`).**
Der vollstaendige Fix braucht zwei Teile: (1) in `diskussion.py` die
hartcodierte Zeile `return f"Das Transkript der Diskussion:\n{transkript}"`
durch einen Sprachschicht-Zugriff ersetzen -- Modulkonstante
`_TRANSKRIPT_KOPF = "Das Transkript der Diskussion:"` (unveraendert
Deutsch, "Deutsch bleibt die Python-Konstante selbst", AGENTS.md), dazu
`from interview_theater import sprache` und `T = sprache.Texte(__name__)`
am Dateiende (genau das Muster aus `begriffsboard.py:63/72/456`, derselben
Padua-Phase-1-Karte); und (2) in
`interview_theater/sprachen/en/texte.toml` eine neue Tabelle `["diskussion"]`
mit `_TRANSKRIPT_KOPF = "The transcript of the discussion:"` ergaenzen.
Teil (2) betrifft eine Datei, die laut Gesamtplan (Task 10, Entscheidungsregel 1,
"gemessen 05.10.2026") von Karte `t_0b702d1d` besessen wird
(`git log --oneline main..padua-workshop/t_0b702d1d-... -- interview_theater/sprachen/en/texte.toml`
zeigt zwei eigene Commits dieser Karte). Der Auftrag fuer diese Karte hat
nur drei namentlich genannte Dateien aus der sonstigen Besitzregel
herausgenommen (`system.md`, `workshop/padua-2026/prompts/phasen/1.md`,
`interview_theater/sprachen/en/prompts/phasen/2.md`) -- `texte.toml` steht
nicht darunter, die allgemeine Besitzregel gilt also weiter. Ein
Halbfix (nur `diskussion.py` auf `T.`-Zugriff umstellen, ohne den
`texte.toml`-Eintrag) wuerde am Verhalten nichts aendern (``sprache.text()``
faellt ohne Eintrag auf Deutsch zurueck, mit einem Log-Vermerk) und damit
keinen echten Fix darstellen, nur toten Umbau -- deshalb in diesem Lauf
nicht angefasst, komplett dokumentiert als Fix-Rezept fuer wen auch immer
`texte.toml` als naechstes anfasst.

**Ja/Nein-Speicherfrage** ("Yes, save" / "No, change it again",
`01-gespraech-phase1.txt:276`, `05-gespraech-phase2.txt:276`) -- eigene
Karte `t_e5b1df39`, laut Auftrag explizit nicht anfassen.

**Raumcheck-Erklaerung** -- in keinem der fuenf Phase-1/2-Dumps gefunden
(`grep -ni "room check\|raumcheck"` liefert keinen Treffer); betrifft
offenbar eine spaetere Phase. Nichts zu tun in diesem Scope, Vollstaendigkeit
halber vermerkt (Abnahme #1016 bleibt zustaendig, falls es doch auftaucht).

**`erkenner.md`** (DE und EN) -- nicht geprueft und nicht angefasst, wie
im Auftrag verlangt (bezahlter Korpuslauf noetig).

## 10. Fuer Birk, offene Fragen

Keine. Alle in diesem Lauf gefundenen Mehrdeutigkeiten liessen sich klar
einer der Kategorien "eindeutiger Fix" (Abschnitt 8), "falsch-positiv,
manuell widerlegt" (Abschnitt 6) oder "liegt bei einer anderen Karte/Datei"
(Abschnitt 9) zuordnen -- keine erforderte eine Design-Entscheidung, die
nur Birk treffen kann.

## 11. Grenzen dieses Laufs

- Die Dumps entstehen gegen eine **erfundene** Fixture
  (`scripts/fixture_padua_voll.py`: Giulia/Marco/Chiara/Luca/InScribe sind
  frei erfundene Namen), nicht gegen eine echte Gruppe.
- Nur fuenf von 39 moeglichen Inventareintraegen (Phase 1+2) -- die Phasen
  3-7 und die Dramaturgie-Richterfragen sind nicht Teil dieser Karte.
- **Kein bezahlter Infomaniak-Lauf** -- alle fuenf Dumps laufen ueber den
  Claude-Weg (`weg=claude`), der echte Infomaniak-Pfad fuer Phase 3
  (Kimi) ist in diesem Scope ohnehin nicht enthalten.
- **Die Opus-Lesung ist nicht gelaufen** (siehe Abschnitt 7) -- jeder
  Befund, der nur eine tiefere semantische Lesung gefunden haette (nicht
  nur Stichwort-Matching), fehlt in diesem BEFUND.
- `ZEICHEN_MAX` der Lesung (240.000) ist ungemessen (uebernommen aus dem
  Gesamtplan, nie gegen einen echten Lauf kalibriert).
- `ANNAHME` (aus dem Gesamtplan uebernommen, hier nicht erneut geprueft):
  die Live-Envs setzen `IT_SZENE_ANBIETER=claude` und
  `IT_LLM_MODELL=moonshotai/Kimi-K2.6` -- nicht im Code gelesen, nur in
  `scripts/erzeuge_prompts_padua_voll.umgebung()` fest nachgebildet.
- Die mechanische Pruefung (`pruefe_prompt_dumps.py`) matcht auf
  Stichwoerter ohne Negations-Erkennung ("ask whether" findet auch "never
  ask whether") -- mehrere der in Abschnitt 6 genannten Funde waren deshalb
  beim manuellen Nachlesen falsch-positiv. Das ist eine bekannte, akzeptierte
  Eigenschaft des Werkzeugs (es listet zum Nebeneinanderlesen, es urteilt
  nicht selbst), keine Karte dieser Session.
- Eine unrelated Nebenwirkung eines Testlaufs waehrend dieser Session hat
  mehrere Screenshot-PNGs unter `docs/ux-padua/` veraendert (binaer anders,
  nicht neu generiert durch diese Karte). Sie sind **nicht** committet --
  sie bleiben als unbestaetigte Arbeitsverzeichnis-Aenderung stehen, weil
  ein `git checkout` ohne Rueckfrage in dieser Sitzung nicht autorisiert
  werden konnte. Empfehlung an Birk: `git checkout -- docs/ux-padua` vor
  dem naechsten Commit auf diesem Branch, falls die Dateien nicht aus
  anderem Grund gebraucht werden.

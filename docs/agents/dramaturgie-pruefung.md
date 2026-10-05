# Die Dramaturgie-Pruefung

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 1122–1269).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

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

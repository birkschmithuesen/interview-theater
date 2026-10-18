# Korpuslauf: 4 Falsch-Positive im EN-Erkenner (Karte t_82569faf)

Ausgangsbefund (dokumentiert in `wt/t_7021ee7b:docs/prompt-audit/2026-10-18-erkenner-en-recherche/BEFUND.md`,
reproduziert mit gezieltem Re-Lauf nur dieser vier ids):

| id | erwartet | geliefert vom Modell (`google/gemma-4-31B-it`, Infomaniak) |
|---|---|---|
| en-e26-usa-ja | szene_usa=JA | szene_schreiben=JA |
| en-e27-usa-nein | szene_usa=NEIN | szene_schreiben=NEIN |
| en-e35-overview-ending-sadder | uebersicht_aendern=... | text_ueberarbeiten=... |
| en-ssn02-ohne-nummer | stagescript_notiz=... | text_ueberarbeiten=... |

Alle vier existierten bereits vor Commit `c1c86d1` (recherche_starten) --
keine Regression dieser Karte. Root-Cause je Fall, Methodik wie in
`.worktrees/erkenner-fp/.erkenner-fp-report.md` (Fall fuer Fall, mit Beleg
statt Vermutung).

## en-e26-usa-ja / en-e27-usa-nein: szene_usa vs. szene_schreiben

Prompt, Punkt 22 (`szene_usa`), definiert den Ausloeser eng: der Bot muss im
Vorlauf genau die USA-Modellfrage gestellt haben ("For the scene text there
is a better model - from Anthropic, in the USA ... Do you want that? Say yes
or no."); die Antwort ("yes, let's do it" / "rather not, keep it in
Switzerland") wird JA/NEIN.

Punkt 18 (`szene_schreiben`) lehrt direkt daneben: "After planning, a short
word is enough ... 'Go', 'do the text', 'write it', that is a job" -- und der
Bot-Satz der USA-Frage enthaelt woertlich "the scene text". Oberflaechlich
teilen sich beide Faelle das Bigramm "scene text" plus ein zustimmendes
Kurzwort ("let's do it" / "Go"). Nichts im Prompt sagt dem Modell, dass eine
Antwort auf GENAU diese Frage **nie** `szene_schreiben` ist, selbst wenn der
gelieferte Wert (`JA`/`NEIN`) gar nicht zum Wertformat von `szene_schreiben`
(ein Auftragssatz) passt -- das Modell hat den richtigen Wert extrahiert,
aber unter der falschen `art` abgelegt, weil die naeherliegende, inhaltlich
"scene text"-aehnliche Regel (Punkt 18) stärker zieht als die entferntere,
engere Regel (Punkt 22).

**Einordnung: schwammige Prompt-Abgrenzung**, keine Modell-Drift, kein
Testharness-Artefakt -- die Luecke (keine explizite Gegenprobe gegen
`szene_schreiben`) bestand unveraendert seit Einfuehrung von `szene_usa` und
wurde nie gegen das echte Modell nachgewiesen.

## en-e35-overview-ending-sadder: uebersicht_aendern vs. text_ueberarbeiten

Punkt 26 (`uebersicht_aendern`) kalibriert nur ueber eine Negativabgrenzung
("Ein plain 'yes' ... ist NICHT uebersicht_aendern") und einen vagen
Nachsatz ("ist nur fuer Feedback, das in kein bestehendes Feld passt").
Punkt 27 (`text_ueberarbeiten`) nennt als eigenes Beispiel **fast wortgleich**
dieselbe Formulierung wie der Testfall: "the ending is too soft, make it
hurt more" (Prompt) gegen "make the ending sadder" (Testfall) -- beide sind
ein "mach das Ende trauriger/haerter"-Satz. Der Prompt gibt dem Modell also
selbst ein Beispiel, das dem Fehlerfall oberflaechlich naeher ist als die
richtige Regel.

Unabhaengiger Beleg, dass das keine Eigenheit von gemma ist: die
InScribe-Opus-Messung (`docs/messung/2026-10-erkenner-baseline.md`,
Befund 1) listet **denselben Fall** `en-e35-overview-ending-sadder` als FP
gegen `claude-opus-5-5` -- dort lieferte Opus `festlegung_setzen` statt
`uebersicht_aendern`, mit der woertlichen Einordnung "die Abgrenzung ...
scheint fuer Opus weniger scharf als fuer gemma". Zwei verschiedene Modelle
stolpern an derselben Prompt-Stelle, nur in unterschiedliche Nachbar-`art`en
-- das ist das Muster einer schwammigen Prompt-Formulierung, nicht
Zufallsrauschen eines einzelnen Modells.

**Einordnung: schwammige Prompt-Abgrenzung**, cross-model reproduzierbar.

## en-ssn02-ohne-nummer: stagescript_notiz vs. text_ueberarbeiten

Punkt 33 (`stagescript_notiz`) und Punkt 27 (`text_ueberarbeiten`)
unterscheiden nur zwei Zustaende: eine Szene wird GERADE mit "Yes, save" /
"No, change it again" gezeigt (-> `text_ueberarbeiten`), oder sie ist noch
nicht geschrieben / wird gerade geschrieben (-> `stagescript_notiz`). Der
Testfall liegt in einem dritten, vom Prompt nicht benannten Zustand: der Bot
hat die Szene bereits **bestaetigt gespeichert** ("Scene 1 saved" -- Vorgang
abgeschlossen, keine Yes/No-Entscheidung mehr offen), und der naechste Wunsch
("no interview quotes in this one, please") bezieht sich auf die naechste,
noch ungeschriebene Szene. Ohne eine explizite Regel fuer "schon bestaetigt
gespeichert, keine Entscheidung mehr offen" faellt das Modell auf die
oberflaechlich naheliegendere Regel (ein Wunsch zu "diesem" Text) zurueck.

Unabhaengiger Beleg: dieselbe Grenze ist bereits in der Opus-Messung
(`docs/messung/2026-10-erkenner-baseline.md`, Befund 2, "Muster A") als
dominanter Fehlerclusters dokumentiert (mind. 19 von 29 FP im
Padua-Testsatz) -- dort wird explizit festgehalten, dass die
Review-Rueckfrage des Bots ("passt das so? Sonst sag mir, was sich aendern
soll.") ohne woertliche Knopftexte als "Szene wird gerade gezeigt" gelesen
wird, obwohl inhaltlich keine Yes/No-Entscheidung mehr offen ist.

**Einordnung: schwammige Prompt-Abgrenzung** (fehlender dritter Zustand
"bereits bestaetigt gespeichert"), ebenfalls cross-model reproduzierbar.

## Gesamtergebnis der Ursachenklaerung

Alle vier Faelle sind **keine Modell-Drift** und **kein
Testharness-Artefakt**: fuer zwei der vier (`en-e35`, `en-ssn02`) gibt es
einen unabhaengigen zweiten Beleg gegen ein komplett anderes Modell
(`claude-opus-5-5`, InScribe Messung 1, 11.10.2026) an derselben Prompt-
Stelle; fuer die anderen zwei (`en-e26`/`en-e27`) liegt die Ursache offen in
der Oberflaechenaehnlichkeit zweier benachbarter Prompt-Regeln, die nie
gegeneinander abgegrenzt wurden. Konsequenz: Punkt 22 (`szene_usa`), 26
(`uebersicht_aendern`), 27 (`text_ueberarbeiten`) und 33
(`stagescript_notiz`) im EN-Erkenner-Prompt bekommen je ein konkretes
Negativ-Gegenbeispiel (siehe Prompt-Diff, Abschnitt unten).

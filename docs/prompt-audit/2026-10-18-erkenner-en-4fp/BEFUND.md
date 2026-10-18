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

## en-e35-overview-ending-sadder: eigentlich ein Korpus-Konstruktionsfehler, nicht primaer ein Prompt-Problem

Erster Verdacht war eine schwammige Abgrenzung zwischen Punkt 26
(`uebersicht_aendern`) und Punkt 27 (`text_ueberarbeiten`): Punkt 27 nennt
als eigenes Beispiel fast wortgleich dieselbe Formulierung wie der Testfall
("the ending is too soft, make it hurt more" vs. "make the ending sadder").
Nachgewiesen (Nachbau von `erkenner._baue_nutzertext` **ohne** Modellaufruf,
mit genau den Funktionen, die `scripts/pruefe_prompts.py::_laufe_erkenner`
selbst benutzt) zeigt sich die eigentliche Ursache: der Nutzertext, den das
Modell fuer diesen Fall bekommt, enthaelt die generierte Uebersicht **gar
nicht**:

```
Arbeitsstand:
Figur Mira
Figur Nora

Neue Nachrichten:
Member 1: the confession at the end feels too neat
Member 1: make the ending sadder, they shouldn't really find each other
```

Der Korpusfall trug die Uebersicht nur in `arbeitsstand.geschichte_uebersicht`
-- ein Feld, das `scripts/pruefe_prompts.py::_fuelle_arbeitsstand()` in
seiner festen Feldliste (`"begriffe", "fragen", "kernthema", "format",
"rahmen", "hauptkonflikt"`) nicht schreibt, und das `erkenner.py`s
`_STAND_BESCHRIFTUNG` (die Liste, die `_arbeitsstand_text()` tatsaechlich
rendert) ebenfalls nicht kennt. Punkt 26 selbst verlangt wortgleich, dass
die Uebersicht "directly in the lead-up" steht -- das ist in diesem Code
exakt der `vorlauf`-Mechanismus (`erkenner.laufe()`: `vorlauf =
repo.letzte_bot_nachricht_vor(...)`, die letzte Bot-Nachricht vor dem
Fenster), nicht `arbeitsstand`. Der Schwesterfall `en-n34-overview-yes-is-not-aendern`
bestaetigt das explizit in seiner eigenen `notiz`: dort steht die Uebersicht
bewusst NUR im Arbeitsstand, "also bleibt es leer" -- der Korpus selbst
unterscheidet also "nur im Arbeitsstand" (kein Treffer erwartet) von
"direkt im Vorlauf" (Treffer erwartet). `en-e35` benutzte versehentlich die
erste Form, obwohl laut eigenem `erwartet`-Feld die zweite gemeint war.

**Konsequenz:** kein Prompt-Wortlaut kann diesen Fall zuverlaessig loesen,
solange das Modell die Uebersicht nie sieht -- bestaetigt durch den eigenen
Testlauf dieser Karte (Abschnitt "Nebenbefund" unten): nach der reinen
Prompt-Schaerfung blieb der Fall FP=0, aber FN (leere Liste statt Treffer),
weil das Modell mangels Beleg korrekterweise nichts eintrug. **Einordnung:
Korpus-Fallkonstruktion fehlerhaft** (fehlendes `vorlauf`-Feld), keine
Modell-Drift, keine schwammige Prompt-Abgrenzung als Hauptursache -- Fix im
Korpus (`korpus/en/erkenner.jsonl`, `en-e35` bekommt den fehlenden `vorlauf`
mit der Uebersicht, exakt wie `entwurf.baue_anzeige()` sie in der Produktion
als Chat-Nachricht zeigen wuerde), nicht nur im Prompt.

Die vermutete Oberflaechenaehnlichkeit zu Punkt 27 bleibt trotzdem real genug,
um sie im Prompt abzusichern (Negativ-Gegenbeispiel ergaenzt, siehe Diff
unten) -- falls eine Gruppe wirklich Feedback zur Uebersicht UND kurz davor
eine geschriebene Szene gezeigt bekommen hat, soll das Modell die beiden
nicht verwechseln. Das war aber nicht die Ursache dieses konkreten FP.

Die InScribe-Opus-Messung (`docs/messung/2026-10-erkenner-baseline.md`,
Befund 1) listet denselben Fall ebenfalls als FP (Opus lieferte
`festlegung_setzen`) -- lief aber ueber **denselben** Korpus und **denselben**
Testharness-Code (`korpus/en/erkenner.jsonl` + `pruefe_prompts.py`), ist
also keine unabhaengige Bestaetigung einer Prompt-Schwaeche, sondern
derselbe Konstruktionsfehler, nur mit einem anderen Modell, das anders rät.

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

Verwandter, aber nicht identischer Befund in der Opus-Messung
(`docs/messung/2026-10-erkenner-baseline.md`, Befund 2, "Muster A",
`betrieb/korpus/en/padua_testsatz.jsonl`, ein ANDERER Korpus aus echten
Padua-Chats): dieselbe Art-Grenze dominiert dort die Fehler (mind. 19 von 29
FP), die Messung selbst haelt aber fest, dass ihr eigener Testsatz den
echten `prueflauf`/Review-Zustand aus der Datenbank nicht nachbilden konnte
und die Grenze "aus dem Chatverlauf allein nicht zuverlaessig" rekonstruiert
werden kann -- also selbst eine Korpus-Unsicherheit, keine saubere zweite
Bestaetigung. Anders als bei `en-e35` ist der Nutzertext fuer `en-ssn02` in
`korpus/en/erkenner.jsonl` aber korrekt gebaut (eigener `vorlauf` mit der
Review-Rueckfrage, bestaetigt per Nachbau wie oben) -- hier ist die
Prompt-Abgrenzung selbst die Lücke, nicht die Korpuskonstruktion, und der
Fix unten behebt sie nachweislich (siehe Korpuslauf-Ergebnis).

**Einordnung: schwammige Prompt-Abgrenzung** (fehlender dritter Zustand
"bereits bestaetigt gespeichert").

## Gesamtergebnis der Ursachenklaerung

Keiner der vier Faelle ist Modell-Drift. Drei (`en-e26`, `en-e27`,
`en-ssn02`) sind schwammige Prompt-Abgrenzungen gegen eine Oberflaechen-
aehnliche Nachbarregel (`szene_schreiben` bzw. `text_ueberarbeiten`) -- sie
bekommen je ein konkretes Negativ-Gegenbeispiel in Punkt 18/22
(`szene_usa`) bzw. 27/33 (`stagescript_notiz`). Der vierte (`en-e35`) ist
primaer ein **Korpus-Konstruktionsfehler**: die generierte Uebersicht
erreichte das Modell wegen eines fehlenden `vorlauf`-Feldes gar nicht --
behoben direkt im Korpus (`korpus/en/erkenner.jsonl`); die zusaetzliche
Prompt-Schaerfung in Punkt 26/27 bleibt als Absicherung gegen die echte,
aber nicht ursaechliche Oberflaechenaehnlichkeit stehen.

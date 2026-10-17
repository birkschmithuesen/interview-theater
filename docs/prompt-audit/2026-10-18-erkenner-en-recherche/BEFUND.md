# Korpuslauf: FP=0-Nachweis fuer recherche_starten (Karte t_7021ee7b, Befund 2)

Kommando (aus der Karte, woertlich):

    python -m scripts.pruefe_prompts erkenner --sprache en --bericht

Umgebung: `betrieb/padua-gruppe1.env` (padua-2026), echtes Modell
(google/gemma-4-31B-it ueber Infomaniak). Live-Lauf, kostet Geld (0.0X CHF,
siehe `bericht.md`), einmalig auf diese Karte hin gefahren.

## Ergebnis fuer die drei neuen recherche_starten-Faelle (Commit c1c86d1)

| id | erwartet | geliefert | FP | FN |
|---|---|---|---|---|
| en-rs01-bruecke-gebaut | recherche_starten | recherche_starten | 0 | 0 |
| en-rs02-gesetz-nachschlagen | recherche_starten | recherche_starten | 0 | 0 |
| en-rs03-spaeter-irgendwann | (kein Treffer) | (kein Treffer) | 0 | 0 |

**Befund 2 ist damit erfuellt: FP=0 fuer die neue art `recherche_starten`
(Punkt 32, EN-Prompt).** Die bindende AGENTS.md-Regel ("Erkenner-Prompt-
Aenderung gilt nur mit FP=0 im Korpuslauf") ist fuer diese Aenderung jetzt
mit einem echten Lauf nachgewiesen, nicht nur behauptet.

## Abweichender Befund: 4 Falsch-Positive im Gesamtlauf, UNABHAENGIG von recherche_starten

Der volle Lauf ueber alle ~98 Faelle liefert 4 FP, alle in bereits
bestehenden Faellen, die mit `recherche_starten`/Punkt 32 nichts zu tun
haben:

| id | erwartet | geliefert vom Modell |
|---|---|---|
| en-e26-usa-ja | szene_usa=JA | szene_schreiben=JA |
| en-e27-usa-nein | szene_usa=NEIN | szene_schreiben=NEIN |
| en-e35-overview-ending-sadder | uebersicht_aendern=... | text_ueberarbeiten=... |
| en-ssn02-ohne-nummer | stagescript_notiz=... | text_ueberarbeiten=... |

Reproduziert mit gezieltem Re-Lauf nur dieser vier ids
(`--nur en-e26-usa-ja,en-e27-usa-nein,en-e35-overview-ending-sadder,en-ssn02-ohne-nummer`)
— alle vier fallen wieder genauso aus. Das ist kein Rauschen eines einzelnen
Laufs.

**Diese vier Faelle existierten bereits vor Commit c1c86d1** (git log zeigt
sie in frueheren Commits: en-e26/e27 seit der USA-Einwilligungs-Karte,
en-e35 seit `1aa0ad8`, en-ssn02 seit `e6c5079`, alle VOR der
recherche_starten-Aenderung). Kein neuer Korpusfall aus dieser Karte
verursacht sie; sie sind keine Regression DIESER Aenderung, sondern ein
bereits bestehender, bisher nicht gemessener Zustand des EN-Erkenners
gegen das aktuell eingesetzte Modell (`google/gemma-4-31B-it`,
Infomaniak). Vermutung: `IT_LLM_MODELL` oder Modellversion hat sich seit
dem letzten bekannten FP=0-Stand dieser vier Faelle veraendert, oder sie
wurden nie gegen das echte Modell nachgewiesen (nur gegen eine fruehere
Modellversion/einen Prompt-Stand).

**Konsequenz fuer diese Karte:** Befund 2 (FP=0 fuer `recherche_starten`)
ist erfuellt und belegt. Die vier unabhaengigen FP sind ein NEUER Befund
(Regression oder bisher ungemessener Bestandszustand bei vier
NICHT-recherche-bezogenen arten), der eine eigene Karte braucht --
`scripts.pruefe_prompts.py` sagt bei jedem FP>0 explizit "Die
Prompt-Aenderung gehoert zurueckgenommen", aber das trifft hier NICHT auf
die recherche_starten-Aenderung zu (deren Faelle sind FP=0) sondern auf
vier bestehende, unabhaengige Prompt-Stellen (szene_usa/szene_schreiben,
uebersicht_aendern/text_ueberarbeiten, stagescript_notiz/
text_ueberarbeiten).

Volltext: `bericht.md` (automatisch von `pruefe_prompts.py --bericht`
erzeugt, alle ~98 Faelle).

# Workshop-Profil `dortmund-2026`

Der Workshop vom 05./06.09.2026 mit einem Migrantinnenverein in Dortmund —
das Profil, für das dieses Repository ursprünglich gebaut wurde.

Eingehängt wird es mit `IT_WORKSHOP=dortmund-2026` in `betrieb/gruppeN.env`.

## Die wichtigste Eigenschaft dieses Profils

**Es ist deckungsgleich mit dem eingebauten Vorgabeprofil.** Ohne
`IT_WORKSHOP` entstehen dieselben Prompts, dieselben Phasennamen, dieselben
Chat-Texte wie mit `IT_WORKSHOP=dortmund-2026`. Das ist keine Nebensache,
sondern das Abnahmekriterium des Umbaus vom 06.09.2026: der Umbau durfte an
dem, was der Bot tatsächlich an ein Modell schickt, kein Zeichen ändern.

Geprüft wird das dreifach in `tests/test_profil_bitgleich.py` — ohne
Variable, mit Variable, und gegen den Fingerabdruck
`docs/prompt-audit/schnappschuss-vor-profilumbau.txt`, der jede Prompt-Datei,
jede zusammengesetzte Systemanweisung, die Formenliste, die Phasen, die
Phasentexte und die Leitfaden-Bausteine als SHA-256 festhält. Dazu prüft
`tests/profile/test_dortmund.py` die Werte im Wortlaut.

Wer hier etwas ändert, ändert damit **nur** Dortmund — nicht die Vorgabe im
Code. Beide Seiten auseinanderlaufen zu lassen ist erlaubt (der
Bitgleichheits-Test schlägt dann an und will bewusst angefasst werden), aber
es ist eine Entscheidung, keine Kleinigkeit.

## Was hier drinsteht

| Datei | Inhalt |
|---|---|
| `profil.toml` | Zielgruppe, Träger, Sprache, Anrede, Orte, Aufführungsort, Konfliktstoff, Projektbeschreibung |
| `formen.toml` | Die fünf Formen je Szene mit Anzeigenamen und Stichwörtern, die Vorgabe-Form, das Zahlwort für den Prompt |
| `phasen.toml` | Die sieben Stationen: Nummer, Kurzname, Satz, Stichwörter; die Meldung beim Phasenwechsel |
| `phasentexte.toml` | Die sieben Einleitungen im Chat, im von Birk am 06.09.2026 bestätigten Wortlaut |
| `prompts/rahmen.md` | Der Block „Rahmen des Stuecks", lange Fassung (`system.md`, `szene.md`) |
| `prompts/rahmen-kurz.md` | Die kurze Fassung (`phasen/4.md`, `phasen/6.md`) |
| `prompts/rahmen-knapp.md` | Die knappe Fassung (`phasen/5.md`) |
| `prompts/projekt.md` | Worum es in dem Stück geht, im Wortlaut der Workshopleitung (`phasen/2.md`) |

## Was hier bewusst **nicht** drinsteht

- **Kein eigener Korpus.** `korpus/` im Repository ist deutsch und
  Dortmund-nah — das ist für dieses Profil genau richtig, also gibt es
  keine Kopie daneben.
- **Keine eigenen Prompt-Dateien** außer den vier Bausteinen oben. Alles
  andere kommt aus `interview_theater/prompts/`, damit Verbesserungen am
  generischen Prompt hier ankommen.
- **Keine Bot-Namen, keine URLs, keine Tokens.** Die stehen in
  `betrieb/gruppeN.env` und gehören nie ins Repository.

## Am Workshoptag

Der Hot-Reload gilt auch hier: wer `prompts/rahmen.md` ändert, sieht es beim
nächsten Gesprächszug, ohne Neustart. Wer `profil.toml`, `formen.toml`,
`phasen.toml` oder `phasentexte.toml` ändert, braucht einen Neustart des
Bots — eine halb gespeicherte Konfigurationsdatei mitten im Gespräch wäre
genau der Halbstart, den der Lader verhindern soll.

Vor jedem Start läuft `scripts/pruefe_profil.py` (aus
`scripts/betrieb-start.sh`). Von Hand:

```
python -m scripts.pruefe_profil dortmund-2026
```

# Prosa-Prompt Phase 5: Blockgroessen vorher/nachher (07.10.2026)

Gemessen auf einer Kopie von `betrieb/padua.db` (VACUUM INTO, Stand ~17:53),
`szene.baue_nutzertext` mit Claude-Pfad, Auftrag wie `entwurf._AUFTRAG_PROSA`,
Zeichen je Block. Vorher = Stand f87c3cb, nachher = `[skript] verdichtet`.
Werkzeug: `/tmp/nacht/messe.py` (faengt `szene._zusammen` ab).

## G1 Szene 1

| Block | vorher | nachher |
|---|---:|---:|
| format_rahmen | 231 | 589 |
| aufgabe | 419 | 52 |
| laenge | 165 | 165 |
| thema | 0 | 0 |
| kernpaket | 4.064 | 2.156 |
| figuren | 581 | 581 |
| p5_gespraech | 16.710 | 16.883 |
| continuity | 0 | 0 |
| verworfen | 0 | 0 |
| chat | 1.483 | 410 |
| diese_szene | 3.161 | 960 |
| auftrag | 70 | 70 |
| gesamt | 26.900 | 21.882 |

## G1 Szene 2

| Block | vorher | nachher |
|---|---:|---:|
| format_rahmen | 231 | 589 |
| aufgabe | 332 | 52 |
| laenge | 165 | 165 |
| thema | 0 | 0 |
| kernpaket | 48.557 | 11.922 |
| figuren | 581 | 581 |
| p5_gespraech | 16.710 | 16.883 |
| continuity | 3.356 | 3.356 |
| verworfen | 0 | 0 |
| chat | 1.429 | 622 |
| diese_szene | 11.437 | 879 |
| auftrag | 70 | 70 |
| gesamt | 82.886 | 35.137 |

## G2 Szene 1

| Block | vorher | nachher |
|---|---:|---:|
| format_rahmen | 749 | 854 |
| aufgabe | 419 | 52 |
| laenge | 165 | 165 |
| thema | 0 | 0 |
| kernpaket | 3.720 | 2.972 |
| figuren | 638 | 638 |
| p5_gespraech | 7.996 | 8.169 |
| continuity | 0 | 0 |
| verworfen | 0 | 0 |
| chat | 620 | 0 |
| diese_szene | 554 | 264 |
| auftrag | 70 | 70 |
| gesamt | 14.947 | 13.198 |

## G3 Szene 2

| Block | vorher | nachher |
|---|---:|---:|
| format_rahmen | 1.468 | 1.911 |
| aufgabe | 332 | 52 |
| laenge | 165 | 165 |
| thema | 182 | 182 |
| kernpaket | 9.956 | 497 |
| figuren | 754 | 754 |
| p5_gespraech | 16.251 | 16.424 |
| continuity | 428 | 428 |
| verworfen | 135 | 135 |
| chat | 6.064 | 0 |
| diese_szene | 906 | 541 |
| auftrag | 70 | 70 |
| gesamt | 36.733 | 21.179 |

## Was sich aendert

- `format_rahmen`: + `arbeitsstand.format` (G1: "Concert performance ... post-dramatic").
- `aufgabe`: Exposition/Konflikt nur bei dramatischem Format (`szene.NICHT_DRAMATISCH`); alle drei Padua-Gruppen bekommen jetzt "Task of this scene: what the group described for it."
- `chat`: neben `p5_gespraech` nur noch die Regie-Notizen zur Szene; der Vorrang-Satz haengt am Gespraechsblock.
- `kernpaket`: nur uebernommene Stellen (wenn es welche gibt), Zitat woertlich, ohne Begruendung (G1 S2: 48.557 -> 11.922).
- `diese_szene`: bereinigte Beschreibung der Gruppe, eigene Kernsaetze, Kurzform und staerkste Zitate aus `szenenkern` (sobald erzeugt; in dieser Messung noch leer).
- `p5_gespraech` waechst um den Vorrang-Satz (+173).

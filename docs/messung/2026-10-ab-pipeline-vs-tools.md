# Messung 2: Pipeline gegen Agent (Karte t_9b2b33cb)

Stand: 2026-10-11 · Modell Achse A/B/C-Opus: `claude-opus-5-5` über den Abo-Proxy · Spec und Vorbedingungen: `docs/messung/2026-10-ab-vorbedingungen.md`.

Korpusgrößen: Achse A (de): 157 Fälle; Achse A (en): 103 Fälle; Achse B (en): 37 Fälle.

Dieser Bericht ist aus den Rohzeilen (`korpus/berichte/ab/*.jsonl`) erzeugt, nicht von Hand geschrieben. Er enthält nur Kennungen und Zahlen.

## Vorbedingungen

| Schlüssel | Wert |
|---|---|
| ACHSE_A | ja |
| ACHSE_B | ja |
| ACHSE_C | nein |

## Ergebnisse

Hinweis zur Nebenzählung: Die Hauptzählung (Treffer/FP/FN) zählt, was das Stück tatsächlich angenommen hat. Die Nebenzählung „Absicht erkannt“ zählt auch abgelehnte Werkzeugaufrufe als erkannte Absicht (die Gruppe hätte ihre Absicht geäußert, das Stück lehnte nur ab). Im json-Modus sind beide Zählungen gleich.

## Achse A: Erkenner-Korpus

### Achse A, Sprache de: Gesprächsfälle

| Kennzahl | json | tools |
|---|---|---|
| Fälle | 146 | 146 |
| Treffer (Summe / erwartet gesamt) | 109 / 116 | 110 / 116 |
| FN | 7 | 6 |
| FP | 9 | 10 |
| Absicht erkannt, Nebenzählung (Treffer / FP / FN) | 109 / 9 / 7 | 110 / 10 / 6 |
| stille Fehler (still_fp) | 9 (davon ohne Korpus-Art: 0) | 10 (davon ohne Korpus-Art: 0) |
| abgelehnt (laut) | 0 | 0 |
| Abbrüche | 0 | 0 |
| Runden (Median) | 1 | 2 |
| Latenz Median / p90 (ms) | 1923 / 3659 | 3418 / 6704 |
| Token ein / aus (Summe) | 16355 / 12248 | 70417 / 31826 |
| Kosten | 0 CHF (Abo) | 0 CHF (Abo) |
| Modellaufrufe (Summe) | 146 | 243 |
| Fehler (Anzahl) | 0 | 0 |

### Achse A, Sprache de: Aufnahme-Fälle (getrennt)

Live laufen Aufnahmen über Infomaniak, hier über Opus; die Zahlen stehen deshalb nicht in der Tabelle der Gesprächsfälle.

| Kennzahl | json | tools |
|---|---|---|
| Fälle | 11 | 11 |
| Treffer (Summe / erwartet gesamt) | 8 / 8 | 8 / 8 |
| FN | 0 | 0 |
| FP | 0 | 0 |
| Absicht erkannt, Nebenzählung (Treffer / FP / FN) | 8 / 0 / 0 | 8 / 0 / 0 |
| stille Fehler (still_fp) | 0 (davon ohne Korpus-Art: 0) | 0 (davon ohne Korpus-Art: 0) |
| abgelehnt (laut) | 0 | 0 |
| Abbrüche | 0 | 0 |
| Runden (Median) | 1 | 2 |
| Latenz Median / p90 (ms) | 1805 / 2291 | 3446 / 9362 |
| Token ein / aus (Summe) | 946 / 384 | 3607 / 1503 |
| Kosten | 0 CHF (Abo) | 0 CHF (Abo) |
| Modellaufrufe (Summe) | 11 | 17 |
| Fehler (Anzahl) | 0 | 0 |

### Achse A, Sprache en: Gesprächsfälle

| Kennzahl | json | tools |
|---|---|---|
| Fälle | 96 | 96 |
| Treffer (Summe / erwartet gesamt) | 61 / 63 | 60 / 63 |
| FN | 2 | 3 |
| FP | 2 | 3 |
| Absicht erkannt, Nebenzählung (Treffer / FP / FN) | 61 / 2 / 2 | 60 / 3 / 3 |
| stille Fehler (still_fp) | 2 (davon ohne Korpus-Art: 0) | 3 (davon ohne Korpus-Art: 0) |
| abgelehnt (laut) | 0 | 0 |
| Abbrüche | 0 | 0 |
| Runden (Median) | 1 | 2 |
| Latenz Median / p90 (ms) | 1900 / 2749 | 2958 / 4827 |
| Token ein / aus (Summe) | 7385 / 5462 | 33659 / 12914 |
| Kosten | 0 CHF (Abo) | 0 CHF (Abo) |
| Modellaufrufe (Summe) | 96 | 156 |
| Fehler (Anzahl) | 0 | 0 |

### Achse A, Sprache en: Aufnahme-Fälle (getrennt)

Live laufen Aufnahmen über Infomaniak, hier über Opus; die Zahlen stehen deshalb nicht in der Tabelle der Gesprächsfälle.

| Kennzahl | json | tools |
|---|---|---|
| Fälle | 7 | 7 |
| Treffer (Summe / erwartet gesamt) | 4 / 4 | 4 / 4 |
| FN | 0 | 0 |
| FP | 0 | 0 |
| Absicht erkannt, Nebenzählung (Treffer / FP / FN) | 4 / 0 / 0 | 4 / 0 / 0 |
| stille Fehler (still_fp) | 0 (davon ohne Korpus-Art: 0) | 0 (davon ohne Korpus-Art: 0) |
| abgelehnt (laut) | 0 | 0 |
| Abbrüche | 0 | 0 |
| Runden (Median) | 1 | 2 |
| Latenz Median / p90 (ms) | 1644 / 2288 | 2897 / 3965 |
| Token ein / aus (Summe) | 370 / 207 | 1743 / 646 |
| Kosten | 0 CHF (Abo) | 0 CHF (Abo) |
| Modellaufrufe (Summe) | 7 | 11 |
| Fehler (Anzahl) | 0 | 0 |

## Achse B: Padua-Testsatz

### Achse B, Sprache en: Gesprächsfälle

| Kennzahl | json | tools |
|---|---|---|
| Fälle | 37 | 37 |
| Treffer (Summe / erwartet gesamt) | 3 / 27 | 3 / 27 |
| FN | 24 | 24 |
| FP | 28 | 25 |
| Absicht erkannt, Nebenzählung (Treffer / FP / FN) | 3 / 28 / 24 | 3 / 25 / 24 |
| stille Fehler (still_fp) | 28 (davon ohne Korpus-Art: 0) | 25 (davon ohne Korpus-Art: 0) |
| abgelehnt (laut) | 0 | 0 |
| Abbrüche | 0 | 0 |
| Runden (Median) | 1 | 2 |
| Latenz Median / p90 (ms) | 3549 / 6163 | 4709 / 7828 |
| Token ein / aus (Summe) | 5897 / 9851 | 24437 / 12184 |
| Kosten | 0 CHF (Abo) | 0 CHF (Abo) |
| Modellaufrufe (Summe) | 37 | 63 |
| Fehler (Anzahl) | 0 | 0 |

## Achse C: Zitatsuche

Achse C: 0 — nicht freigegeben (Kosten, Schätzung ~0,5–1 CHF Kimi)

## Messgrenzen

Abbildung Werkzeug auf Korpus-Art (`erkenner_werkzeuge.ART_FUER_WERKZEUG`), über die die Tools-Seite in die Korpus-Sprache zurückübersetzt wird:

| Werkzeug | Korpus-Art |
|---|---|
| setze_rahmen | rahmen_setzen |
| setze_ort | szene_planen |
| setze_besetzung | szene_planen |
| figur_aus_szene | szene_planen |
| karte_aendern | szene_planen |
| figur_hinzu | figur_setzen |

- Undo: im tools-Modus gibt es keinen Erkenner-Undo-Schnappschuss für Stück-Schritte (Spec § 3.4); der Vergleich der Rücknehmbarkeit ist deshalb nicht Teil der Zahlen.
- Achse C hat einen Modell-Störfaktor: Pipeline und Agent laufen auf Kimi, die Opus-Pipeline auf Opus; ein Unterschied kann am Modell oder am Verfahren liegen. Opus-Zeilen mit Rückfall auf Kimi sind markiert und nicht gemittelt.

## Kommandos zum Nachrechnen

```
uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide
uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache en --modus beide
uv run --extra dev python -m scripts.ab_padua --modus beide
uv run --extra dev python -m scripts.ab_zitate --ohne-modell
uv run --extra dev python -m scripts.ab_zitate --gruppe G1 G2 G3 --kosten-ok
uv run --extra dev python -m scripts.ab_pipeline_vs_tools bericht --roh korpus/berichte/ab/A-de-20261011.jsonl korpus/berichte/ab/A-en-20261011.jsonl korpus/berichte/ab/B-20261011.jsonl --aus docs/messung/2026-10-ab-pipeline-vs-tools.md --achse-c-grund "nicht freigegeben (Kosten, Schätzung ~0,5–1 CHF Kimi)"
```

## Was die Messung NICHT zeigt

- Live mit Laien: keine Gruppe hat mit dem tools-Modus gearbeitet.
- Gruppenerlebnis: Tempo, Vertrauen, ob die Gruppe die „Notiert:“-Meldungen versteht.
- Gesprächsführung durch einen Agenten: getauscht wurde nur der Erkenner.
- Langzeitstabilität über einen ganzen Workshoptag.
- Undo im tools-Modus deckt Stück-Schritte nicht ab (Spec § 3.4); die Wirkung fehlender Undo-Knöpfe für Werkzeugschritte ist nicht gemessen.
- Der Szenenkern wird im tools-Modus nicht neu angestoßen.
- Der Padua-Testsatz ist laut Messung 1 (3/27) kein scharfes Gate.
- Aufnahme-Fälle laufen live über Infomaniak, in der Messung über Opus; ihre Zahlen sind deshalb nur getrennt und mit Vorsicht zu lesen.

Keine Empfehlung. Die Entscheidung trifft Birk (Kriterium 1: bei Gleichstand zählen Vision/Pflege, das heißt Agent).

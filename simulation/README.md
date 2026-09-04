# Simulation

Ein kompletter Workshop, gefahren gegen den echten Bot-Code und die echten
Modelle. Drei simulierte Teilnehmerinnen arbeiten sich durch neun Schritte --
Begriffe, Fragen, fuenf Interviews, Kernthema, Figuren, Phase 5, eine Szene,
eine Korrektur, `/stand` --, danach bewertet ein Richter den Verlauf nach
einer festen Metrik.

```
set -a; . ./betrieb/gruppe1.env; set +a
PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
$PY -m scripts.simulation --set 1 --seed 7 --bericht
$PY -m scripts.simulation --mix 1,2,3 --seed 3
$PY -m scripts.simulation --set 1 --seed 1 --ohne-szene    # ohne Reasoning-Lauf
$PY -m scripts.simulation --alle                           # drei Laeufe, Sets 1-3
```

**Kostet Geld, laeuft nie automatisch** -- wie `scripts/pruefe_prompts.py`.
Die Testsuite deckt alles ab, was ohne Netz pruefbar ist
(`tests/test_simulation*.py`).

## Warum nicht ueber Telegram

Telegram liefert Bot-Nachrichten nie an andere Bots (Bot-FAQ). Ein Testbot,
der den Theaterbot bespielt, ist damit ausgeschlossen. Der Simulator faehrt
deshalb **denselben Codepfad wie der Live-Bot** im selben Prozess --
`bot.verarbeite_update`, `bot._zug_und_erkenner` -- nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`.
Interviews kommen als Text (`aufnahme.importiere_text`, § 10.5); der
Whisper-Weg ist getrennt getestet und wuerde einen Lauf nur teurer und
langsamer machen.

## Die Teile

| Datei | Zustaendigkeit |
|---|---|
| `scripts/simulation.py` | Aufruf, Wegwerf-DB, 429-Pause, Bericht |
| `lauf.py` | der Durchlauf: Updates bauen, Zug fahren, Interviews importieren |
| `skript.py` | die neun Schritte: Ziel und Zielzustand je Schritt |
| `stimmen.py` + `stimmen/*.md` | drei Sprachprofile (knapp, ausschweifend, skeptisch) |
| `material.py` + `interviews/set{1,2,3}/*.md` | 15 erfundene Transkripte, Mischung per Seed |
| `attrappe.py` | Telegram ohne Netz |
| `kennzahlen.py` | die mechanischen Zahlen -- kein Modell |
| `richter.py` + `interview_theater/prompts/richter.md` | die Noten (gemma, Schema) |
| `bericht.py` | Markdown-Bericht, Transkript, `verlauf.jsonl` |

## Was ein Lauf hinterlaesst

* `simulation/laeufe/<datum>-<mischung>-<seed>.md` -- das Transkript
* `simulation/berichte/<datum>-<mischung>-<seed>.md` -- Kennzahlen, Noten,
  die fuenf schlechtesten Bot-Antworten, drei Saetze zur Ableitung
* `simulation/berichte/verlauf.jsonl` -- eine Zeile je Lauf, mit git-HEAD

Transkript und Bericht sind gitignored (sie enthalten vollstaendige
Modellantworten), `verlauf.jsonl` nicht: sie ist der Vergleichsmassstab
zwischen zwei Prompt-Staenden.

## Drei Dinge, die man wissen sollte

**Der Simulator laeuft einfaedig.** `lauf.einfaedig()` ersetzt
`szene.starte`, `aufnahme.starte_abschluss` und `aufnahme.starte_auswertung`
durch synchrone Aufrufe. Im Betrieb geben die an Threads ab, weil dort
niemand warten soll; hier muss jede Wirkung in der Datenbank stehen, bevor
der naechste Schritt seinen Zielzustand prueft.

**Ein Schritt darf scheitern.** Ist der Zielzustand nach sechs
Stimm-Nachrichten nicht erreicht, wird das vermerkt und der Lauf geht
weiter. Bekommt der Bot das Ende eines Interviews nicht mit, schliesst der
Simulator es selbst ab (`notausgaenge` im Bericht) -- sonst waere ein Lauf mit
einem tauben Erkenner ab Schritt 3 wertlos und trotzdem bezahlt.

**Alles ist datengetrieben.** Die Phasen kommen aus `phasen.PHASEN`, die
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort
"Notiert:" aus `erkenner.baue_meldung`. Der Simulator soll einen Umbau an
Phasen, Feldern und Formulierungen ueberleben, ohne dass jemand ihn
nachzieht.

## Die Interviews erweitern

Eine Datei je Interview, Kopf zwischen zwei `---`-Zeilen:

```
---
name: Meryem
set: 1
themen: [Koffer, Ankommen, Warten]
sprachmerkmale: [kurze Saetze, Abbrueche, tuerkische Einsprengsel]
zitate_soll:
  - Ein Koffer und eine Tuete mit Brot
  - ...
---
Leyla: Erzaehl mal, was hattest du dabei?

Meryem: Ein Koffer und eine Tuete mit Brot. ...
```

250 bis 450 Woerter, gesprochenes Deutsch, zwei Sprecherinnen im Wechsel,
Umschrift statt Umlauten. Die drei `zitate_soll` muessen **woertlich** im
Text stehen (`tests/test_simulation_material.py` prueft das mit derselben
Funktion, die im Betrieb ueber Belegzitate entscheidet) -- sie sind der
Sollwert der Kennzahl `zitate_soll`.

Alles darin ist frei erfunden. Kein Satz stammt aus einem echten Interview.

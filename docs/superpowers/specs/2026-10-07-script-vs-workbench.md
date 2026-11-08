# Script vs. Workbench — klare Aufgabenteilung (Padua, 07.10.2026)

Birk, 07.10.2026 ~17:45: *"Reduktion auf das Wesentliche. Fokus halten.
Design schoen machen. Gut lesbar. Text soll Spass machen zu lesen."*

Alles unter dem EINEN Padua-Schalter `[skript] verdichtet`
(`workshop.skript_verdichtet_aktiv`). Ohne die Zeile (Dortmund, Vorgabe)
bleibt jede Ansicht und jeder Prompt byte-gleich.

## Befund vorher

- `schaerfung._ergaenze_szene` haengte jede uebernommene Interviewstelle an
  `szene.was_passiert` (Begruendung, `"; "`) und `szene.kernsaetze` (Zitat,
  `" | "`). G1 Szene 2: 3.849 bzw. 7.332 Zeichen.
- Script-Tab (`web._probe_szene_html`) zeigte diesen Brei als "What
  happens"/"Key lines" (seit ff216d4 nur in der Anzeige gekappt), mit
  Prosa obendrein die Key-lines-Liste im IT-Block.
- Workbench (`web._wb_inhalt_html`, Phase 4) zeigte je Szene denselben
  `was_passiert`-Brei in einer Zeile.

## Datenmodell (Teil A)

- `was_passiert` bleibt die Beschreibung der Gruppe; die Begruendungen
  bleiben an den `schaerfung`-Zeilen. Altbestand wird beim Lesen bereinigt
  (`szenenkern.gruppenbeschreibung`: die angehaengten Begruendungen der
  uebernommenen Stellen fallen heraus) und per Nachtrag-Skript in der DB.
- Neue Spalten `szene.kern` (3–6 Punkte, je Zeile einer: worum es in der
  Szene geht), `szene.kernsaetze_kurz` (die 5 staerksten Zitate, je Zeile
  `"…" (Interview N)`), `szene.kern_quelle` (Fingerabdruck der Eingabe —
  gleiche Eingabe = kein zweiter Modellaufruf).
- EIN Schema-Aufruf je Szene (`szenenkern.verdichte`, `modellwahl.aufruf_schema`
  — Claude bei Freigabe, sonst Kimi), im Thread, nach "Done" in der
  Sortierliste und nach einer Aenderung der Szene im Chat (Erkenner
  `szene_planen`). Die Zitate waehlt das Modell nur per Nummer aus der
  Liste — der Wortlaut kommt aus der DB, nie aus dem Modell. Fehler = alte
  Anzeige (gekappte Liste).

## Script = was die Gruppe liest und probt

- Titel, Ort/Zeit (Angaben), Besetzung, der Szenentext (Prosa EN/IT bzw.
  Sprechtext) — Absaetze, Sprecher fett, Regie kursiv/grau.
- Darunter klein **"What it's about"** (Kurzform) — NUR solange kein Text
  da ist. Ohne Kurzform die bereinigte Beschreibung.
- Keine Key-lines-Liste, sobald Text da ist (die Zitate stehen im Text).
  Ohne Text: hoechstens die 5 staerksten Zitate.
- Lesbarkeit: Textspalte `max-width: 65ch`, Zeilenhoehe 1.6, ruhige
  Serifenschrift fuer den Text, Absatzabstand, Szenenkopf mit Luft,
  Angaben/Besetzung klein und grau.

## Workbench = Arbeitsmaterial

- Setting, Format, Geschichte, Festlegungen wie bisher.
- Je Szene: Titel + Kurzform (Punkte); darunter die 5 staerksten Zitate
  und aufklappbar (`<details>`) alle uebernommenen Zitate — nur geprueft
  (`zitat_geprueft = 1`, Datenschutz-Invariante der Weboberflaeche).
- Keine Szenentexte (die stehen im Script).

## Prosa-Prompt (Teil C)

- `format_rahmen` traegt `arbeitsstand.format`.
- `chat` faellt weg, wenn `p5_gespraech` steht (Dublette); die
  Regie-Notizen zur Szene bleiben.
- `diese_szene`: bereinigte Beschreibung + Kurzform + 5 staerkste Zitate,
  keine Begruendungskette; `kernpaket` nur die uebernommenen Stellen,
  ohne Begruendungen, Zitate woertlich.
- `aufgabe`: Expositions-/Konfliktlogik nur bei dramatisch-narrativem
  Format; sonst "Task of this scene: what the group described for it."

## Matcher (Teil D)

- Hintergrund bekommt "Discarded by the group" aus den `verworfen`-Zeilen
  des Journals (derselbe Datenweg wie `szene._verworfen_text`).

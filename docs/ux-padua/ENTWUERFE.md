# Zwei Stil-Entwuerfe fuer Padua

**Entscheidung Birk: offen**

Zum Anklicken, ohne Server, ohne Netz:

```
xdg-open docs/ux-padua/entwurf-a.html      # Terminal zuerst
xdg-open docs/ux-padua/entwurf-b.html      # Buehne zuerst
```

Beide Dateien sind selbststaendig (Inline-CSS/-JS, keine Fremdquelle) und
laufen per `file://`. Beide zeigen **dieselbe** Struktur — die aus Karte W
(drei Tabs, Phasenuebersicht, gestreamte Antwort) und Karte A2 (zwei
Aufnahmeknoepfe) — mit erfundenem Material aus `simulation/interviews/set1`.
Die Logik in beiden ist zeichengleich; verglichen wird allein die Gestaltung.

Zustaende fuer Screenshots und zum Nachsehen: `?halt=strom` haelt den
Textaufbau bei 55 %, `?halt=aufnahme` setzt den Interviewknopf auf „laeuft",
`?halt=belohnung` zeigt die Belohnung. Das Demo-Pult unten im Chat-Tab
spielt jeden Moment noch einmal ab (Stream, Denken, Aktwechsel, Belohnung,
Aufnahme-Zustaende) — es gehoert nicht zum Produkt.

## Die fuenf Achsen, auf denen sie sich unterscheiden

| Achse | **A — Terminal zuerst** | **B — Buehne zuerst** |
|---|---|---|
| **1. Grund und Signal** | Phosphorgruen `#6ef7a5` auf Schwarzblau `#05070a`, dauerhafte (sehr schwache) Scanlines | Amber `#f0b24a` auf Samtschwarz `#120f10`, ein statischer Scheinwerferkegel von oben |
| **2. Typografie** | Monospace **durchgehend** — auch der Chat. Serife nur im Textbuch | Serife/Humanist fuer alles Gelesene. Monospace **nur** als Akzent: Uhr, Zaehler, Sprechernamen, Statuszeilen |
| **3. Ort der Navigation** | Tableiste **unten**, am Daumen. Aktleiste oben, zugeklappt eine Zeile mit Fortschrittsbalken | Aktleiste **und** Tabs **oben**, wie ein Programmzettel. Die sieben Akte als Reihe von Buehnenlichtern |
| **4. Der Aufnahmeknopf** | Breite Taste ueber die **volle Breite**, 68 px hoch (laufend 80 px), Text in Versalien. PTT: kleiner **runder** Phosphorknopf in der Eingabezeile | Runder **Scheinwerfer**, 76 px (laufend 94 px), Beschriftung daneben. PTT: **Pille** „HOLD TO TALK" links in der Eingabezeile, amber statt rot |
| **5. Der Moment am Aktwechsel** | **Glitch**: Scanlines springen, Aktname in Versalien, 560 ms | **Vorhang**: faellt von oben, Aktname zwischen zwei Linien, 600 ms |

Beide zeigen beide Welten, nur verschieden gewichtet: A hat das Theater im
Textbuch-Tab (Versalien-Namen, Regie kursiv, Serifenschrift) und in der
Akt-Metapher; B hat das Terminal im Strom-Cursor, in der Statuszeile und in
den Sprechernamen.

## Screenshots

| | Handy 390×844 | Laptop 1366×900 |
|---|---|---|
| A · Chat mit laufendem Strom | `entwurf-a-handy-chat.png` | `entwurf-a-laptop-chat.png` |
| A · Aufnahme laeuft | `entwurf-a-handy-aufnahme.png` | |
| A · Akte aufgeklappt + Belohnung | `entwurf-a-handy-akte.png` | |
| A · Textbuch | `entwurf-a-handy-textbuch.png` | |
| B · Chat mit laufendem Strom | `entwurf-b-handy-chat.png` | `entwurf-b-laptop-chat.png` |
| B · Aufnahme laeuft | `entwurf-b-handy-aufnahme.png` | |
| B · Akte aufgeklappt + Belohnung | `entwurf-b-handy-akte.png` | |
| B · Textbuch | `entwurf-b-handy-textbuch.png` | |

Aufgenommen mit `docs/ux-padua/fotografiere_entwuerfe.py` (Playwright aus dem
Wegwerf-venv, siehe `tests/e2e/README.md`).

## Was in beiden gleich ist (und nicht zur Wahl steht)

* **Kein Webfont.** Die CSP aus Karte S hat `default-src 'none'` und **kein**
  `font-src` — eine eingebettete Schrift waere geblockt oder braeuchte eine
  Aenderung an der Richtlinie. Also System-Stacks:
  `ui-monospace, "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace`
  und `ui-serif, Georgia, "Times New Roman", "Liberation Serif", serif`.
* **Kein `style="…"`-Attribut, kein `on…=`-Handler.** Alles ueber
  `addEventListener`; dynamische Werte (Pegel, Fortschritt) ueber CSSOM
  (`el.style.setProperty('--pegel', …)`) — das ist unter CSP ohne
  `'unsafe-inline'` erlaubt, `setAttribute('style', …)` waere es nicht.
* **`prefers-reduced-motion: reduce`** schaltet jede Animation und jeden
  Uebergang ab; Glitch/Vorhang fallen ganz weg, die Aktansage bleibt. Der
  Strom baut sich weiter stueckweise auf — das ist Information, keine
  Animation.
* **Kontrast AA** fuer jedes Text/Grund-Paar (gerechnet, nicht geschaetzt):
  A 14.99 / 14.90 / 7.55 / 6.56 · B 15.45 / 10.14 / 7.08 / 8.98.
* **Tippflaechen ≥ 44 px**, Fliesstext ≥ 16 px (A 16 px, B 17 px).
* **Der Aufnahmeknopf sagt seinen Zustand im TEXT**, nicht nur in der Farbe:
  `Record interview` → `Starting …` → `Stop recording` → `Sending …`, dazu
  eine zweite Zeile („Mic is hot.") und `aria-busy` waehrend der Uebergaenge.
* **Push-to-Talk verschwindet, solange ein Interview laeuft** (Karte A2:
  zwei Mikrofone gleichzeitig sind keine Bedienung).
* **Englische Mikrotexte** mit etwas Humor („Mic is hot.", „Hold on, the tape
  is still walking.", „Curtain up on the interviews.") — nie im Bot-Text, und
  nirgends ein Vorname (E8).

## Empfehlung: **A — Terminal zuerst**

Vier Gruende, in der Reihenfolge ihres Gewichts.

1. **Der Aufnahmeknopf gewinnt.** Er ist das wichtigste Element der Karte
   (Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden
   gedrueckt). A gibt ihm die **volle Breite** und einen Zustandstext in
   Versalien; am Handy sind das rund 340 × 68 px, im laufenden Zustand
   340 × 80 px in Vollrot. B gibt ihm 76 px Durchmesser — schoener, aber
   kleiner, und die Beschriftung steht daneben statt darin. Wer im
   Probenraum im Stehen auf ein Telefon tippt, trifft die Flaeche, nicht den
   Kreis.
2. **A laesst mehr Chat stehen.** Gemessen an den Screenshots: bei A liegt
   die Oberkante des Fusses bei y ≈ 650 von 844, bei B (nach dem
   Nachbessern, Beschriftung neben statt unter dem Knopf) bei y ≈ 655 — fast
   gleich. **Aber** B braucht die Tabs zusaetzlich **oben** (weitere 44 px),
   A hat sie im selben festen Block unten. Netto sieht die Gruppe bei A eine
   Blase mehr.
3. **Der Unterschied der zwei Mikrofone ist bei A groesser.** A trennt sie
   auf vier Achsen zugleich: Form (Rechteck ↔ Kreis), Ort (eigene Zeile ↔
   Eingabezeile), Farbe (Rot ↔ Phosphor), Verb (tap ↔ hold). B trennt nur
   auf dreien — beide Knoepfe sind rund bzw. gerundet, und der PTT-Pille
   fehlt die Formunterscheidung.
4. **Monospace traegt das Technoide ohne Dekoration.** B muss den
   Terminal-Anteil ueber Zusatzelemente hereinholen (Statuszeilen in
   Versalien, `REC`-Aufdruck); bei A ist er die Grundschrift, und das
   Theater kommt genau dort dazu, wo es hingehoert — im Textbuch-Tab, der in
   A **auch** serif gesetzt ist.

**Was fuer B spricht — und im Plan erhalten bleibt.** B ist das schoenere
Dokument: die Skriptseite in Serife mit dem Sprechernamen auf eigener Zeile
ist naeher an einem echten Textbuch als As Variante, und der Vorhang ist ein
klarerer Akt-Moment als der Glitch. Deshalb faellt B nicht weg: der Plan
legt **beide Token-Saetze** an, und B ist durch den Tausch **eines** Blocks
von Custom Properties plus vier benannter Komponenten-Abweichungen
(Tab-Ort, Knopfform, Uebergang, Skript-Typografie) erreichbar.

## Was verworfen wurde

* **Eine dauerhaft aufgeklappte Phasenuebersicht.** Sieben Akte mit ihren
  Aufgaben nehmen am Telefon ein Drittel des Bildschirms fuer etwas, das man
  dreimal am Tag braucht. Zugeklappt eine Zeile mit Fortschritt, aufgeklappt
  ueber `<details>` (geht auch ohne JavaScript).
* **Dauerlaufende Effekte.** Kein flackernder Hintergrund, kein tickernder
  Cursor ausserhalb eines laufenden Stroms. Die Scanlines in A sind
  statisch und bei 3,5 % Deckung; B hat nur einen statischen Lichtkegel.
* **Ein Ton beim Aufnahmestart.** Im Probenraum sitzen drei Gruppen am
  Tisch — sechs Telefone, die piepsen, sind kein Gewinn.
* **Schieben-zum-Sperren bei Push-to-Talk** (wie in Messengern). Karte A2
  legt fest: halten und loslassen, sonst nichts. Eine dritte Geste mehr, die
  man erklaeren muss.
* **Farbe als alleiniger Zustandstraeger.** Jeder Zustand des
  Aufnahmeknopfes steht auch im Text.

## Offene Wuensche (gehen in den BERICHT der Umsetzung)

* Das **Team-Dashboard** (`/`) bleibt unveraendert — es haengt am Beamer und
  ist ein anderer Kontext.
* Eine **Wellenform** der laufenden Aufnahme statt eines Pegelbalkens waere
  schoener, braucht aber ein Canvas und damit `img-src`-Ueberlegungen.
* **Haptik** (`navigator.vibrate`) beim Start/Stopp der Aufnahme: waere die
  klarste Rueckmeldung ueberhaupt, ist aber auf iOS-Safari nicht verfuegbar —
  also ein Gefuehl, das die Haelfte der Gruppe nicht bekommt.

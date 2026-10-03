# Design-Review Padua (03.10.2026)

Abnahme der Gestaltung (Entwurf B, „Buehne zuerst") nach der Umsetzung des
Plans `docs/superpowers/plans/2026-10-01-padua-ux-gestaltung.md`: ein Blick
auf jede Seite im echten Browser, je Element ein Urteil — **behalten**,
**entfernen** oder **ruhiger** —, und die Frage, was davon umgesetzt ist.
Grundregel bleibt Birks Auftrag: nur Look & Feel, keine Logik, kein neuer
Endpunkt, keine Aenderung an `_CHAT_JS`. Was daran scheitern wuerde, steht
unten als offener Punkt und nicht als gebaute Loesung.

Alle Bilder liegen unter `docs/ux-padua/` und zeigen **nur erfundenes
Material** aus den Test-Fixtures (Gruppe „Die Ankommenden" mit Meryem und
Erhan; Dashboard-Gruppen „Canal Crew", „Market Voices", „Bridge Night").
Aufgenommen mit headless Chromium aus `tests/e2e/`, mit demselben
Interpreter wie die Tests:

| Bildreihe | Test | Fenster |
|---|---|---|
| `abnahme-*.png` | `tests/e2e/test_web_gestalt_e2e.py::test_abnahme_screenshots` | Handy 390×844, Laptop 1366×900 |
| `review-*-vorher.png` / `-nachher.png` | `tests/e2e/test_web_uebersicht_e2e.py::test_review_screenshots` (Suffix ueber `IT_REVIEW_SUFFIX`, Vorgabe `nachher`) | Handy 390×844, Beamer 1920×1080 als Gegenprobe |

**Bilder nur auf einem frischen Server aufnehmen** (`-k abnahme` bzw.
`-k review`). Ein voller Lauf der Datei schreibt sie ebenfalls, aber dann
steht im Bild die Rate-Limit-Meldung „Keine Verbindung" und Blasen der
vorigen Tests derselben Wegwerf-Datenbank — der Topf von `web_grenze`
(20 je Minute) ist nach den uebrigen Tests fast leer.

## Befundliste

„vorher/nachher" nennt die Bilder; wo es kein Vorher-Bild gibt, steht der
Befund im Bericht der jeweiligen Aufgabe (`.superpowers/sdd/p2-task-N-report.md`).

### Gruppenseite, Chat und Textbuch (Browserlauf)

| Punkt | Bild vorher / nachher | Urteil | Umgesetzt |
|---|---|---|---|
| Chat-, Stand- und Textbuch-Panel weiss, Bot-Blase hell auf weiss (Basis-CSS von A2/W ist hell und schaltet nur unter `prefers-color-scheme: dark` um) | — / `abnahme-handy-chat.png`, `abnahme-handy-textbuch.png` | ruhiger (dunkle Flaechen) | ja |
| Phasenknoepfe weiss mit heller Schrift, in beiden Farbschemata | — / `abnahme-laptop-akte.png` | ruhiger | ja |
| „Pause"/„Beenden" weisse Kaesten, „Beenden" zweizeilig | — / `abnahme-handy-aufnahme.png` | ruhiger | ja |
| Aufnahmeknopf zeigte „laeuft", bevor das Mikrofon da war | — / `abnahme-handy-aufnahme.png` | Zustand korrigieren („startet" bis `#uhr` sichtbar) | ja |
| Beschriftung „INTERVIEW LAEUFT · 0:00" ragte aus dem Kreis | — / `abnahme-handy-aufnahme.png` | entfernen (sichtbar), fuer Vorleseprogramme behalten (`font-size: 0`) | ja |
| Handy: „Senden" halb ausserhalb des Bildes (x+w = 458 > 390), Pegel ein Strich | — / `abnahme-handy-chat.png` | Zeile neu aufteilen | ja |
| Offene Aktfolge schob im Chat die Tableiste ueber Uhr und Pegel | — / `abnahme-handy-akte.png` | Liste begrenzen (30vh) | ja |
| Laptop: Fuss lief ueber die ganze Breite | — / `abnahme-laptop-chat.png` | auf 46rem wie `body` | ja |
| Textbuch: Wege-Links in Ocker (~2.8:1), gedaempfte Regie/Leerstellen unter 4.5:1, helle Flaeche unter der hervorgehobenen Replik | — / `abnahme-handy-textbuch.png`, `abnahme-handy-probenansicht.png` | ruhiger, lesbar | ja |
| Arbeitsstand: weisse Eingabefelder mit heller Schrift (1.23:1) | — / `abnahme-handy-stand.png` | dunkel | ja |
| Akte-Bild zeigte nur die laufende Aufnahme statt des Aktwechsels; Akt-Marke und Lichter fehlten nach dem Tausch der Aktfolge (`/teil/roadmap`) | — / `abnahme-handy-akte.png` | reparieren (`MutationObserver`) | ja |
| Ruhetext verwies auf einen Stopp-Knopf, den es im Ruhezustand nicht gibt; EN sagte „below" | — / `abnahme-handy-chat.png` | ruhiger: „Einmal tippen zum Starten." / „Tap once to start." | ja |
| „Was als Naechstes kommt" stand nirgends | — / `abnahme-handy-chat.png`, `abnahme-handy-stand.png` | neue Zeile „Als Nächstes: …" unter der Aktzeile, auf jedem Tab | ja |
| „Akt 3/7" vor „Phase 3/7" — dieselbe Zahl zweimal in einer Kopfzeile | `abnahme-handy-chat.png` | ruhiger (eine der beiden weg) | nein — Birks Entwurfsentscheidung |
| Sieben Lichter a ~6 px am Telefon | `abnahme-handy-chat.png` | ruhiger | nein (Zahl steht daneben) |
| Push-to-Talk ist das blosse 🎤 statt der Pille „HOLD TO TALK" aus Entwurf B | `abnahme-handy-chat.png` | behalten (kein Platz bei 390 px, Knopftext setzt A2) | — |
| Entwurf A nie im Browser fotografiert | — | — | nein (Sandbox gab `IT_UX_ENTWURF=a` nicht frei) |

### Uebersichtsseiten

| Punkt | Bild vorher / nachher | Urteil | Umgesetzt |
|---|---|---|---|
| Dashboard: kein Fortschritt auf einen Blick | `review-dashboard-beamer-vorher.png` / `-nachher.png` | behalten und staerken (Akt n/7 + sieben Segmente) | ja |
| Dashboard: Probleme unsichtbar (Vorfall, Fehlschlag, 86 % Kosten, Bot liest nicht) | dito | Hinweis „Needs attention" nur bei einem Problem | ja |
| Dashboard: blaue Links auf Dunkel | dito | Titel in Textfarbe | ja |
| Dashboard: „—" je leeres Feld, Kernthema-Rest | `review-dashboard-handy-vorher.png` / `-nachher.png` | entfernen | ja |
| Dashboard: Interview-Leitfaden doppelt zu den Fragen | `review-dashboard-beamer-vorher.png` / `-nachher.png` | entfernen | ja |
| Dashboard: Botname im Kartenkopf | dito | entfernen (steht in „Bot assignment") | ja |
| Dashboard: Interviewergebnisse klein, ohne Ueberschrift, ganz unten | dito | mit Ueberschrift nach den Figuren | ja |
| Dashboard: Karte im Spaetstand (12 Figuren, lange Story, 5 Interviews) laeuft am Beamer ueber 1080 px | `review-dashboard-beamer-nachher.png` | ruhiger: Figuren nur mit Namen, Langtexte auf drei Zeilen gekappt | ja |
| Dashboard: „As of" bricht am Telefon um | `review-dashboard-handy-nachher.png` | ruhiger (`nowrap`) | ja |
| Stand: „Was noch fehlt" erst nach zwei Bildschirmen Formularen | `review-stand-handy-ganz-vorher.png` / `-nachher.png` | nach oben, vor die Formulare | ja |
| Stand: helle Speichern-Knoepfe (vier je Figur), lauteste Flaeche der Seite | `review-stand-beamer-ganz-vorher.png` / `-nachher.png` | ruhiger | ja |
| Stand: Link „Chat mit dem Bot" auf der vereinten Seite (fuehrt per 302 auf dieselbe Seite) | dito | entfernen (nur CSS, die Einzelseite behaelt ihn) | ja |
| Stand: Festlegung klebte an ihrer Marke („styleEvery scene…") | dito | reparieren | ja |
| Stand: Ueberschriften blass | `review-stand-beamer-nachher.png` | kraeftig (Serife, 700, Textfarbe) | ja |
| Stand: Spielkarte wiederholt Setting/Story aus dem Ueberblick | dito | entfernen waere richtig | nur leiser (Inhaltsentscheidung) |
| Stand: Spalte am Beamer schmal | `review-stand-beamer-nachher.png` | Schrift waechst, Breite bleibt 46rem | teilweise |
| Stand: wer `#stand` direkt oeffnet, landet am Seitenende | `review-stand-handy-vorher.png` | Logik (Chat scrollt beim Laden) | nein — Befund an A2/W |
| Sprechanteile listen „CHOR" als Figur | `review-stand-handy-ganz-nachher.png` | Logik von `sprecher.py` | nein — Befund |

## Interview-Modus

**Zweck in einem Satz:** Waehrend eine Gruppe einer fremden Person
gegenuebersitzt, zeigt das Telefon genau drei Dinge — dass es aufnimmt, wie
lange schon, und wo man aufhoert.

Erkannt wird der Modus allein am DOM (`web_gestalt._JS_INTERVIEW`):
`html[data-ux-interview="1"]`, solange `#fuss[data-interview="1"]` **und**
`#uhr` sichtbar ist. `data-interview` allein reicht nicht — es steht schon
beim Druck auf „1" (Mikrofon noch unterwegs) und auch dann, wenn ein
**anderes** Telefon den Modus haelt; dort bleibt die Uhr verborgen.
Push-to-Talk und das Brainstorming in Phase 4 loesen den Modus nicht aus.
Das CSS steht in `web_gestalt.css_interview()`, eingehaengt nur mit Chat
(`web_vereint.seite`), nicht in `css_rahmen()` — sonst stuende Chat-Markup
auch in der Probenansicht und bei Telegram-Gruppen.

Bilder: `abnahme-handy-aufnahme.png` (Leitfaden zugeklappt oben, Uhr
gross, Pegel, rote Lampe, „Aufnahme läuft.", „Pause", darunter der eine
grosse rote „■ Beenden"), `abnahme-handy-aufnahme-leitfaden.png`
(Leitfaden aufgeklappt, „Beenden" bleibt im Bild),
`abnahme-laptop-aufnahme.png` (gleiche Ordnung, auf 46rem zentriert).

| Element / Effekt / Text | Urteil | Umgesetzt |
|---|---|---|
| Aktzeile, Lichter, „Als Nächstes" | entfernen (im Interview) | ja |
| Tableiste; Chat-Panel erzwungen sichtbar (ein Zurueck-Wischen auf `#stand` nahm vorher Stopp **und** Tableiste weg) | entfernen | ja |
| Chatverlauf, Tippanzeige, Strom-Cursor | entfernen — Bewegung vor dem Gegenueber | ja |
| Eingabezeile, PTT, Senden | entfernen | ja |
| Akt-Vorhang, Ansage, Belohnungen | entfernen — kein Effekt im Interview | ja |
| Runder Knopf mit Puls und Stopp-Quadrat | ruhiger: 1.3rem-Lampe, ohne Puls, ohne Zeiger (`pointer-events: none`); bleibt im DOM fuer Vorleseprogramme und Tests | ja |
| Uhr | behalten, groesser (3.4rem) | ja |
| Pegel | behalten, ohne Transition — einziger Beleg, dass das Mikrofon etwas hoert (Dortmund: 13 von 20 Aufnahmen leer) | ja |
| Zustandszeile | behalten (1.25rem), in Textfarbe statt `--rec` (als Text nur 3.45:1); in der Pause eigener Satz statt „Aufnahme läuft." | ja |
| Warteschlange, Fehler, Anhalt | behalten, lesbar (.95rem) — einzige Stelle fuer „Keine Verbindung" | ja |
| „■ Beenden" | behalten als **der eine Hauptknopf**: 4.5rem, rot, unten in der Daumenzone | ja |
| „⏸ Pause" | behalten, sekundaer ueber „Beenden" | ja |
| Leitfaden | behalten (optional), zugeklappt, Marker ▸/▾; Inhalt per `textContent` aus dem schon ausgelieferten `pre.leitfaden` | ja |
| Doppelter Punkt: „●" vor der Uhr (A2-Text `web_chat._TEXT_UHR`) plus rote Lampe | ruhiger | nein — A2-Text, hier nicht angefasst |
| Interview-Belohnung „Interview ist drin." | behalten, ohne Auftritt-Animation | ja |

**Wake Lock.** Im selben Baustein, feature-detected
(`'wakeLock' in navigator`), jede Ablehnung geschluckt. Angefordert beim
Eintritt in den Modus, freigegeben bei Modusende (Stopp, Mikrofonfehler,
Modusende vom Server), bei `visibilitychange` → hidden und `pagehide`;
zurueck im Bild neu angefordert, solange das Interview laeuft. Gibt der
Browser den Lock selbst frei, ruft das Skript kein `release()` auf das tote
Objekt und holt ihn beim naechsten Sichtbarwerden neu. Er verhindert nur
das **automatische** Sperren, nicht das Sperren von Hand.

**Alle Effekte des Modus stehen in `BEWEGT`** (reduced-motion-Block), und
ein Browsertest prueft, dass im Modus auch **ohne** reduced-motion
`document.getAnimations()` leer ist.

### Fehlerpfade im Interview (Befund, keine Logik geaendert)

Gelesen in `_CHAT_JS` (`interview_theater/web_chat.py`). „Verifiziert" heisst:
im Code eindeutig; „plausibel": eine Kette aus dem Code, nicht auf einem
Geraet gemessen.

| Pfad | Geht Aufnahme verloren? | Sieht die Gruppe es sofort? | Stand |
|---|---|---|---|
| Netz weg | Nein, solange der Tab lebt (Segmente im Speicher, Wiederholung ohne Hoechstzahl). **Ja**, wenn der Tab geschlossen oder vom System verworfen wird — keine Persistenz, `beforeunload` ist mobil unzuverlaessig. | **Nein.** Der Poll scheitert still; sichtbar erst beim ersten gescheiterten Upload, und Segmente gehen erst am VAD-Schnitt raus (Pause 2.5 s, Deckel 90 s): bis zu ~90 s Verzug. | verifiziert |
| 429/403 (Rate-Limit, Nonce) | Nein (wiederholt) | Falsch benannt: erscheint als „Keine Verbindung", obwohl das Netz da ist. Im e2e-Lauf beobachtet. | verifiziert |
| Telefon von Hand gesperrt | Plausibel **ja, still**: kein `visibilitychange`-Pfad fuer den Recorder, kein Handler fuer Track-`ended`/`mute`, kein `MediaRecorder.onerror`; `AudioContext.resume()` nur beim Anlegen. Bleibt der Kontext `suspended`, misst VAD keine Rede mehr, jedes Segment endet am 90-s-Deckel mit zu wenig Rede und wird verworfen. | **Nein.** Die Uhr rechnet Wanduhrzeit und laeuft weiter; der Pegel steht, aber kein Text sagt es. | plausibel |
| Eingehender Anruf | Plausibel **ja**: der Track endet; `sitzung.offen += 1` steht vor `r.start()`, `start()` wirft im `setInterval` ohne `try`. `offen` wird nie wieder 0, `/fertig` wird nie eingereiht — das Interview wird auch nach „Beenden" nicht abgeschlossen. | **Nein.** | plausibel, Geraetetest noetig |
| Mikrofon verweigert | Nein (nichts aufgenommen) | Ja: Fehlertext, Modus endet, Wake Lock frei | verifiziert |

Empfehlungen an A2 (nicht hier gebaut, weil Logik): Track-`ended`/`mute`
und `MediaRecorder.onerror` als sichtbarer Zustand („Aufnahme
unterbrochen"), `AudioContext.resume()` bei `visibilitychange` → visible,
`offen` erst nach erfolgreichem `start()` hochzaehlen, Poll-Fehler in der
Warteschlange anzeigen, 429 nicht „Keine Verbindung" nennen, Segmente in
IndexedDB puffern.

## Die zwei Uebersichtsseiten

### Team-Dashboard `/`

**Zweck in einem Satz:** Dauerhaft im Plenum projiziert, zeigt es
Dramaturgie und Workshopleitung auf einen Blick, wo jede Gruppe steht und
was sie hat — Technik nur, wenn etwas klemmt.

**Was dem Zweck dient:** je Karte gross der Gruppenname (Serife), daneben
nur die Marke „Interview mode"; darunter „Act 5/7 · Sharpening" in
Signalfarbe plus sieben Segmente (erreicht Amber, aktuell Gruen, offen
Umriss; die Segmente sind `aria-hidden`, der Text traegt die Aussage).
„Needs attention" **nur bei einem Problem**, eine Zeile je Anlass:
fehlgeschlagene Modellaufrufe und Vorfaelle aus einer Allow-list
(`web.ACHTUNG_VORFAELLE`) in den letzten 2 h, Kosten ab 80 % des
Tagesdeckels, Web-Eingaenge, die der Bot seit mindestens 3 min nicht
abgeholt hat. Danach der Inhalt in der Reihenfolge der Geschichte:
Setting, Story, Characters, From the interviews, Core theme/Main conflict
nur wenn gesetzt, Terms, Questions. Schrift waechst mit der Breite
(`clamp()`), drei Spalten am Beamer, eine am Telefon. Keine Bewegung (die
Seite laedt alle zehn Sekunden nach).

**Entfernt / umgeordnet / eingeklappt:** entfernt die doppelte Phase, der
Interview-Leitfaden (er wiederholt die Fragen), jedes leere Feld „—", das
leere Kernthema, der Botname im Kopf. Umgeordnet: die Interviewergebnisse
mit Ueberschrift hinter die Figuren. Eingeklappt (wie bisher): Zahlen,
Vorfalldetails und Aufruftabelle im „Log", die Bot-Zuordnung am Ende. Am
Beamer gekappt: Figuren nur mit Namen, Langtexte auf drei Zeilen — ab dem
dritten Interview stehen die Kurzformen nur noch auf der Gruppenseite.

**Nur im Padua-Profil.** Die Gestaltung haengt am Profilschalter
`[web] dashboard_gestaltet` (Vorgabe `false`, gesetzt nur in
`workshop/padua-2026/profil.toml`), weil `tests/test_web_dashboard_en.py`
das HTML des Dashboards ohne Profil und mit `dortmund-2026` byte-genau
festhaelt. Das Dortmunder Dashboard ist also unveraendert, das Paduaner
gestaltet.

Bilder: `review-dashboard-beamer-vorher.png` (ungestaltet, blaue Links,
Leitfaden-Wand in Canal Crew, kein Problem sichtbar) gegen
`review-dashboard-beamer-nachher.png` (drei Karten, Hinweis bei Bridge Night
„The bot hasn't picked up 1 message for 9 min" und bei Market Voices
— ein Fehlschlag, ein Vorfall `transcription_failed`, 86 % Kosten —,
Canal Crew im Spaetstand ohne Hinweis und innerhalb von 1080 px);
`review-dashboard-handy-vorher.png` / `-nachher.png` (eine Spalte,
Kappungen mit Ellipse).

### Gruppenseite `/g/<token>`, Tab Arbeitsstand

**Zweck in einem Satz:** Die Seite der Gruppe selbst und der Stoff fuer die
inhaltliche Diskussion im Plenum — Inhalt statt Technik, am Telefon und
projiziert lesbar.

**Was dem Zweck dient:** „Was noch fehlt" steht direkt nach dem Ueberblick
und **vor** den Formularen des Arbeitsstands (die einzige
Markup-Aenderung dieser Nacharbeit, `web.gruppe_koerper`; Test
`test_was_fehlt_steht_vor_den_formularen_des_arbeitsstands`). Ueberschriften
kraeftig (Serife, 700, Textfarbe), Festlegungen als eigene Zeile mit Marke,
die Spielkarte als Checkliste ohne Aufzaehlungspunkte, Schrift waechst am
Beamer.

**Entfernt / umgeordnet / eingeklappt:** umgeordnet „Was noch fehlt" nach
oben; ruhiger die Speichern-/Entfernen-Knoepfe (transparenter Grund,
Signalschrift) und der Probenansicht-Link; entfernt (nur per CSS, auf der
vereinten Seite) der Link „Chat mit dem Bot". **Bewusst nicht geaendert:**
die uebrige Reihenfolge (durch `tests/test_web.py` und
`tests/test_festlegung_web.py` festgehalten und inhaltlich stimmig), der
Leitfaden unter „Wo wir stehen" (er ist das Dokument, das die Gruppe im
Interview haelt), die Spaltenbreite 46rem (breiter hiesse auch Chat und
Textbuch breiter).

Bilder: `abnahme-handy-stand.png` (Ueberblick, „Was noch fehlt", dann
„Arbeitsstand" im ersten Bildschirm), `review-stand-handy-ganz-vorher.png`
/ `-nachher.png` und `review-stand-beamer-ganz-vorher.png` / `-nachher.png`
(ganze Seite), `review-stand-handy-nachher.png` /
`review-stand-beamer-nachher.png` (erster Bildschirm). In den
`review-stand-*`-Bildern traegt Canal Crew zwoelf Figuren; dort fuellt der
Ueberblick am Telefon den ersten Bildschirm allein, und „Was noch fehlt"
beginnt erst darunter.

## Offene Punkte

Aus den drei Aufgaben zurueckgestellt, jeweils mit Grund:

- **Doppelter Fortschritt in der Kopfzeile** („Akt 3/7 · Phase 3/7 ·
  Interviews"): dieselbe Zahl zweimal, kostet am Telefon die halbe Zeile.
  Birks Entwurfsentscheidung.
- **„Als Nächstes: Interviews" in der Phase „Interviews"**: die Aufgabennamen
  sind die Nomen aus `phasentexte.PARAMETER`, per Test an diese Liste
  genagelt. Eine Verbform braeuchte eine zweite Liste — ausserhalb von Look
  & Feel. Der Rueckfallzweig „Phase <naechste>" ist im Browser nicht
  getestet (nur als Unit).
- **Kommentar in `_INTERVIEW`**: nennt die Pausenlampe „amber,
  `var(--warn)`"; in Entwurf B ist `--warn` gruen (#7fd6a0).
- **Stopp-Leiste nicht uebersetzt**: „⏸ Pause", „▶ Weiter", „■ Beenden" und
  die Uhr-/Warteschlangentexte aus `web_chat._JS_TEXTE` laufen nicht ueber
  `T` — in Padua stehen sie deutsch (Befund an A2/A1).
- **Klicks waehrend eines Uebergangs** werden nicht gesperrt (`_CHAT_JS`,
  Befund an A2; die Gestaltung zeigt nur `aria-busy`).
- **Fehlerpfade im Interview** (Telefon gesperrt, Anruf, Netz weg, 429 als
  „Keine Verbindung"): siehe oben, Befund an A2.
- **Dashboard:** gekappte Interviews 3–5 ohne „+N"-Marke;
  `_fehlschlaege_im_fenster` liest ohne Grenze; die Kontrolle im
  Waechter-Test nutzt ein ungeprueftes Thema; die Routine-Liste nennt
  `nachpass_gelaufen`, das kein Code schreibt; die Allow-list der
  Hinweis-Vorfaelle sind Ermessensentscheidungen fuer Birk.
- **„Bot schweigt" nur im Web-Kanal erkennbar**: bei Telegram-Gruppen
  schreibt erst der Bot in die Datenbank, ein stiller Bot hinterlaesst
  keine Zeile. Ein Herzschlag waere Bot-Logik.
- **Kostendeckel des Dashboards aus der Web-Unit**: siehe BERICHT.md,
  Abschnitt „Betrieb".
- **`#stand` oeffnet am Seitenende**, **„CHOR" als Figur** in den
  Sprechanteilen: Logik, Befunde an A2/W bzw. `sprecher.py`.
- **Leitfaden-Regeln global** (`h2`/`.block`/`.frage` in `css_rahmen()`).
- **Entwurf A nie im Browser fotografiert.**

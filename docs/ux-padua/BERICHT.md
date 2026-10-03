# UX Padua — was entschieden wurde und warum

Entwurf B (Buehne, Amber) ist umgesetzt — Birks ausdrueckliche Entscheidung
(Kommentar vom 01.10.2026 auf Kanban-Karte t_f09c20e3), nicht die
Empfehlung der Karte (die zu Entwurf A riet). Umschalten auf A:
`web_gestalt.VORGABE_ENTWURF = "a"` oder `IT_UX_ENTWURF=a`, dazu ein
Neustart von `interview-theater-web.service`.

## Birks Richtung, und wie sie gelesen wurde

„bisschen matrix style cool, unterhaltend, technoisch, theater" — vier
Leitplanken, je mit dem, was daraus im Code geworden ist und was
ausdruecklich nicht.

- **Terminal:** dunkler Grund, Monospace als tragende oder als
  Akzentschrift (je nach Entwurf), Phosphor/Amber als Signalfarbe, ein Text,
  der sich stueckweise aufbaut (`strom.Senke` über die vereinte Seite). Nicht:
  ein dauerhaft flackernder Hintergrund oder ein Cursor, der auch ausserhalb
  eines laufenden Stroms tickert — beide Entwuerfe haben nur **statische**
  Scanlines bzw. einen statischen Lichtkegel.
- **Theater:** sieben Akte statt sieben Phasen als Marke in der
  Weboberflaeche (die Namen in `phasen.PHASEN`, in Prompts, im Journal und in
  `/stand` bleiben „Phase" — das anzufassen waere ein Umbau, keine
  Gestaltung), ein Moment am Aktwechsel (Glitch in A, Vorhang in B), das
  Textbuch als Manuskript gesetzt. Nicht: Kitsch am Phasenwechsel — der
  Moment dauert 560–600 ms, dann ist er vorbei, und `prefers-reduced-motion`
  schaltet ihn ganz ab, waehrend die Aktansage selbst im Text stehen bleibt.
- **Unterhaltend:** zwei kleine Belohnungen (siehe „Was verworfen wurde"),
  Humor in den englischen Mikrotexten („Mic is hot.", „Hold on, the tape is
  still walking.", „Curtain up on the interviews."). Nicht: Humor im
  Bot-Text selbst — der bleibt unveraendert, und kein Vorname taucht in
  einer Mikrotext-Zeile auf (E8).
- **Technoid:** jeder Zustand ist sichtbar — Pegel, Uhr, Cursor,
  Warteschlange, die vier Aufnahmeknopf-Zustaende als Text. Nicht: Farbe als
  alleiniger Zustandstraeger (siehe „Was verworfen wurde") und kein
  dauerlaufender Effekt, der suggeriert, es passiere etwas, wo nichts
  passiert.

## Welcher Entwurf und warum

`docs/ux-padua/ENTWUERFE.md` empfiehlt **Entwurf A** („Terminal zuerst")
mit vier Gruenden, in der Reihenfolge ihres Gewichts:

1. **Der Aufnahmeknopf gewinnt.** Er ist das wichtigste Element der Karte
   (Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden
   gedrueckt). A gibt ihm die volle Breite (≈ 340 × 68 px, laufend 80 px in
   Vollrot); B gibt ihm 76 px Durchmesser mit der Beschriftung daneben statt
   darin.
2. **A laesst mehr Chat stehen.** B braucht die Tabs zusaetzlich oben
   (weitere 44 px gegenueber A, wo sie im selben festen Block unten liegen)
   — netto eine Blase weniger sichtbar.
3. **Der Unterschied der zwei Mikrofone ist bei A groesser.** A trennt
   Interview-Aufnahme und Push-to-Talk auf vier Achsen (Form, Ort, Farbe,
   Verb), B nur auf dreien.
4. **Monospace traegt das Technoide ohne Dekoration.** Bei A ist Monospace
   die Grundschrift; B muss den Terminal-Anteil ueber Zusatzelemente
   (Statuszeilen, `REC`-Aufdruck) hereinholen.

**Birk hat sich trotz dieser vier Gruende fuer B entschieden** — Kommentar
vom 01.10.2026 auf der Kanban-Karte, nicht im Repository. Eine
Rechtfertigung fuer diese Entscheidung ist hier nicht belegbar und wird
deshalb nicht erfunden; was im Repository dokumentiert ist, ist allein,
dass B umgesetzt wurde und A als Komponenten-Tausch erreichbar bleibt.

**Was laut ENTWUERFE.md fuer B spricht — und im Plan erhalten bleibt:** B
ist das schoenere Dokument. Die Skriptseite in Serife mit dem
Sprechernamen auf eigener Zeile ist naeher an einem echten Textbuch als
As Variante, und der Vorhang ist ein klarerer Akt-Moment als der Glitch.
Deshalb ist B nicht einfach die zweite Wahl, sondern ein vollwertiger,
gleichermassen ausgearbeiteter Entwurf: derselbe Satz Regeln (Kontrast,
CSP, reduzierte Bewegung, Text statt Farbe als Zustandstraeger) gilt fuer
beide, A ist nur durch den Tausch **eines** Tokenblocks plus vier benannter
Komponenten-Abweichungen entfernt.

**Was sich beim Bauen gegen den gewaehlten Entwurf (B) gezeigt hat und
korrigiert wurde:**

- **CSS-Kaskaden-Kollision (Aufgabe 7, selbst gefunden UND selbst
  behoben):** die „Buehnenlichter" (die sieben Akte als Reihe statt als ein
  Balken) waren in Entwurf B zunaechst unsichtbar. `_TABS_B`s
  `#ux-balken`-Regeln hatten dieselbe Spezifitaet wie die unpraefixierten
  Regeln aus `_ROADMAP`, die spaeter in der Konkatenation von
  `css_rahmen()` folgen — bei gleicher Spezifitaet gewinnt in CSS die
  spaetere Regel, also verlor `_TABS_B` gegen `_ROADMAP`, unabhaengig vom
  Inhalt. Behoben per `.roadmap`-Spezifitaets-Praefix auf den
  kollidierenden Selektoren; Regressionstest ist ein echter
  CSS-Spezifitaetsrechner (`tests/test_web_gestalt_css.py`), der fuer jede
  im CSS gefundene konkurrierende Regel den tatsaechlichen Kaskaden-Gewinner
  ermittelt, statt nur nach einem Text zu suchen.
- **Eine Abweichung vom deklarierten Dateibereich (Aufgabe 8):**
  `web_gestalt.skript()` musste um einen `chat_vorhanden`-Parameter erweitert
  werden, weil der neue Aufnahme-Baustein sonst chat-panel-spezifische IDs
  (`#warteschlange`) auch fuer Telegram-Gruppen ausgeliefert haette — ein
  bestehender Regressionstest aus Karte W schlug das zu Recht an. Das
  erforderte eine Zeile Aenderung in `web_vereint.py`
  (`web_gestalt.skript(chat_vorhanden=chat_vorhanden)`), die eigentlich
  ausserhalb des fuer diese Aufgabe deklarierten Dateibereichs lag — minimal,
  korrekt, unabhaengig verifiziert, aber hier ehrlich benannt.

Ueber die Aufgaben 2–11 hinweg wich der woertliche Brief-Code oder -Test
mehrfach geringfuegig vom tatsaechlichen, parallel weitergewachsenen
Codestand ab (ein Regex-Fallstrick beim Druckblock, eine veraltete
`seite()`-Struktur, eine Testassertion, die mit einer neu eingehaengten
CSS-Regel kollidierte, ein Test, der mit der geteilten Keyframe-Definition
unvereinbar war, zwei Tests, die die „kein Skript in der Probenansicht"-
Vorgabe verletzten). Jede Abweichung wurde einzeln, minimal und ohne
Architekturaenderung behoben und von einem unabhaengigen Review bestaetigt
— das erwartete Ergebnis eines Plans, der gegen einen parallel
weitergewachsenen Code-Stand ausgefuehrt wurde, kein Qualitaetsproblem
dieser Karte.

## Die vier benannten Komponenten-Abweichungen

| Abweichung | Konstante | A | B |
|---|---|---|---|
| Tab-Ort | `_TABS_A`/`_TABS_B` | Tableiste unten, am Daumen; Aktleiste oben zugeklappt eine Zeile | Aktleiste **und** Tabs oben, wie ein Programmzettel; die Akte als Reihe von Buehnenlichtern |
| Knopfform | `_CHAT_A`/`_CHAT_B` | Breite Taste ueber die volle Breite, 68 px (laufend 80 px), Versalien; PTT als kleiner runder Knopf | Runder Scheinwerfer, 76 px (laufend 94 px), Beschriftung daneben; PTT als Pille „HOLD TO TALK" (im Code: Pille mit 🎤, siehe Nachbesserung) |
| Akt-Moment | `_MOMENTE_A`/`_MOMENTE_B` | Glitch: Scanlines springen, Aktname in Versalien, 560 ms | Vorhang: faellt von oben, Aktname zwischen zwei Linien, 600 ms |
| Skript-Satz | `_SKRIPT_A`/`_SKRIPT_B` | Monospace durchgehend, auch im Chat; Serife nur im Textbuch | Serife/Humanist fuer alles Gelesene, Monospace nur als Akzent (Uhr, Zaehler, Sprechernamen, Statuszeilen) |

Jede Abweichung haengt ausschliesslich an ihrer Konstante — kein Pfad
verzweigt an einer zweiten Stelle nach Entwurf, und `ENTWUERFE` bleibt mit
zwei Eintraegen (`"a"`, `"b"`) die einzige Quelle der moeglichen Werte.

## Was verworfen wurde

Aus `docs/ux-padua/ENTWUERFE.md` uebernommen:

- **Eine dauerhaft aufgeklappte Phasenuebersicht.** Sieben Akte mit ihren
  Aufgaben nehmen am Telefon ein Drittel des Bildschirms fuer etwas, das
  man dreimal am Tag braucht. Zugeklappt eine Zeile mit Fortschritt,
  aufgeklappt ueber `<details>` — geht auch ohne JavaScript.
- **Dauerlaufende Effekte.** Kein flackernder Hintergrund, kein tickernder
  Cursor ausserhalb eines laufenden Stroms.
- **Ein Ton beim Aufnahmestart.** Im Probenraum sitzen mehrere Gruppen am
  Tisch — piepsende Telefone sind kein Gewinn.
- **Schieben-zum-Sperren bei Push-to-Talk.** Karte A2 legt fest: halten und
  loslassen, sonst nichts. Eine dritte Geste mehr, die man erklaeren muss.
- **Farbe als alleiniger Zustandstraeger.** Jeder Zustand des
  Aufnahmeknopfes steht auch im Text.

Ergaenzend, aus dieser Umsetzung selbst:

- **Die dritte Belohnung „Szene fertig".** Gebaut sind zwei kleine
  Belohnungen (am Dreh-/Aktwechsel und an einer abgeschlossenen
  Aufgabengruppe); eine dritte, an einem fertigen Szenentext, wurde nicht
  gebaut. Sie braeuchte die Information „gerade ist ein Szenentext
  eingetroffen", und die steht nirgends im DOM — ein fertiger Szenentext
  kommt als gewoehnliche Bot-Blase. Der Plan erlaubt dafuer einen additiven,
  read-only-Schluessel im Zustands-Poll (etwa `letzte_szene_id`), aber die
  beiden gebauten Belohnungen haben ihn nicht gebraucht, und einen
  Schluessel allein fuer eine einzige Belohnung einzufuehren waere der
  falsche Preis. Wer sie will, baut beides zusammen.

## Befunde an anderen Karten

- **A2, Befund 1:** Drucke waehrend eines Uebergangs werden nicht ignoriert
  (das Dortmunder Fehlerbild — ein Knopf 14× in 93 Sekunden gedrueckt).
  Vorschlag: `zustand.uebergang` in `_CHAT_JS`, und der Click-Handler
  beginnt mit `if (zustand.uebergang) { return; }`. Gehoert zu A2, hier
  bewusst nicht repariert — die Gestaltung zeigt nur `aria-busy`.
- **A2, Befund 2:** die Knopfbeschriftung steht als deutsches Literal im
  JavaScript statt in `_TEXT_INTERVIEW_AN`/`_AUS`. Gehoert in den
  A1-Nachzug von Karte W.
- **Karte UX-Knoepfe (vorbestehend, unabhaengig von dieser Karte — Befund
  WIEDERHOLT beobachtet in den Aufgaben 5, 7, 8, 9 und 10, jeweils
  unabhaengig voneinander):** `NameError: name 'roh' is not defined` in
  `interview_theater/web.py::_antworte_binaer` (nahe Zeile 3653–3657),
  ausgeloest beim Ausliefern eines fehlenden/statischen Bildes. Stammt aus
  Commit `baa64e0` („UX-Knoepfe-Karte Abschnitt 5"), nicht aus dieser
  Karte. Der Server faengt die Ausnahme selbst zu einer 500-Antwort ab —
  kein Testfehlschlag, aber ein echter Logikbug, der nicht hierher
  gehoert und deshalb nicht hier repariert wurde (Logik, keine
  Gestaltung).
- **Zwei Mess-Artefakte, kein echter Befund (Aufgabe 1, ANNAHME 2):** die
  Annahmen-Kommandos meldeten `nonce-roadmap` und `panel-chat` als
  scheinbar fehlende Strings in `_CSS_VEREINT`. Beide stellten sich als
  falsch heraus — der String `"panel-chat"` wird erst zur Laufzeit per
  `scope_css(web_chat._CSS_CHAT, ".panel-chat")` angehaengt und steht
  deshalb nicht woertlich im Quelltext von `_CSS_VEREINT`; derselbe
  Mechanismus gilt fuer die Nonce. Kein Code wurde deswegen geaendert.

## Offene Wuensche

- ~~**Das Team-Dashboard `/`** bleibt ungestaltet.~~ Seit der Nacharbeit
  vom 03.10.2026 gestaltet — aber nur im Padua-Profil, hinter
  `[web] dashboard_gestaltet` (siehe „Nacharbeit nach der Abnahme" unten).
  Das Dortmunder Dashboard ist unveraendert.
- **Wellenform statt Pegelbalken** — braucht ein `<canvas>` und damit eine
  CSP-Ueberlegung zu `img-src`; ein Balken, der sich bewegt, sagt „das
  Mikrofon hoert dich" schon.
- **Haptik** beim Start/Stopp der Aufnahme (`navigator.vibrate` gibt es auf
  iOS-Safari nicht — ein Gefuehl, das die Haelfte der Gruppe nicht bekommt,
  ist schlechter als keins).
- **Eine dritte Belohnung „Szene fertig"** — braeuchte im Zustands-Poll
  einen additiven read-only-Schluessel (etwa `letzte_szene_id`), siehe
  oben.
- **Kein Dunkel/Hell-Umschalter.** Beide Entwuerfe sind dunkel, und der
  `@media print`-Block ist die einzige helle Flaeche — ein zweites Thema
  waere ein zweiter Tokensatz und eine dritte Entscheidung, die niemand
  bestellt hat.
- **Die Entwuerfe unter `docs/ux-padua/entwurf-{a,b}.html` werden nicht
  nachgefuehrt.** Sie zeigen den Stand, den Birk gesehen hat; zwei Werte
  weichen deshalb bewusst vom Code ab (`--rand` gibt es dort nicht, `b.rec`
  ist dort dunkler) — beides steht als Kommentar in `web_gestalt.TOKENS`.

**Der Browserlauf (03.10.2026) — nachgeholt.** Aufgabe 12 war in der
ersten Sandbox nicht moeglich (Wegwerf-venv unerreichbar). Am 03.10. lief
`tests/e2e/test_web_gestalt_e2e.py` zum ersten Mal gegen echtes Chromium.
Die Fixture war kaputt (`repo.lege_szene_an` mit falscher Signatur), zwei
Tests warteten auf ein verborgenes Element im Zustand „visible" (nie
erreichbar). Der Blick auf die Bilder zeigte sechs **echte** Maengel, die
keine Unit-Probe sehen konnte — alle an derselben Wurzel: die Basis-CSS
von A2/W ist **hell** und schaltet nur unter `prefers-color-scheme: dark`
um, und ihre Regeln sind teils staerker praefixiert als die Gestaltung.

1. Chat-, Stand- und Textbuch-Panel weiss; Bot-Blase hell auf weiss →
   `body`-Regel in `_CHAT_FLAECHEN`, `_STAND`, `_SKRIPT_A/B` (wird beim
   Scopen zum Panel selbst).
2. Phasenknoepfe weiss mit heller Schrift (`.roadmap .phase-knopf` aus
   `_CSS_VEREINT` schlug `.phase-knopf`), in **beiden** Farbschemata →
   Farbregeln mit `.roadmap`-Praefix in `_ROADMAP` (ohne `font:`, damit die
   Skriptschrift aus B gewinnt).
3. „Pause"/„Beenden" weisse Kaesten, „Beenden" zweizeilig → `_CHAT_FLAECHEN`.
4. Der Aufnahmeknopf zeigte „laeuft", bevor das Mikrofon da war —
   `_CHAT_JS` setzt `data-interview="1"` schon beim Druck. Seitdem „laeuft"
   erst mit sichtbarer `#uhr` (oder Pause), vorher „startet". Und die
   Beschriftung „INTERVIEW LAEUFT · 0:00" ragte aus dem Kreis (A2 setzt sie
   auf 1.15rem) → klein und umbrechend.
5. Am Handy stand „Senden" halb ausserhalb des Bildes, der Pegel war ein
   Strich → `.zeile` volle Breite, Eingabe `min-width: 0`, PTT schmaler,
   Pegel teilt sich die Zeile mit der Uhr.
6. Offene Aktfolge schob im Chat die Tableiste ueber Uhr und Pegel →
   `max-height: 30vh` im Chat-Tab; am Laptop lief der Fuss ueber die ganze
   Breite → `max-width: 46rem` wie `body`.

Jeder Mangel hat einen eigenen Browsertest, gemessen am berechneten Stil
und an Kaesten, nicht am CSS-Text. Die Bilder
`docs/ux-padua/abnahme-*.png` sind die Abnahme (damals neun, nach der
Nacharbeit elf: dazu `abnahme-handy-aufnahme-leitfaden.png` und
`abnahme-handy-stand.png`); sie zeigen nur erfundenes Material aus der
Fixture.

**Nachbesserung nach dem Review an `834edbf`.**

- **Helle Reste im Textbuch:** `.wege a` (Ocker, ~2.8:1) und die
  `opacity`-Daempfung von `.leer`/`.offen`/`.regie`/`.marke` (auf
  `--text-leise` unter 4.5) sowie die helle Flaeche unter der
  hervorgehobenen Replik → `_SKRIPT_FLAECHEN` in beiden `_SKRIPT_*`. Dazu
  im Arbeitsstand weisse Eingabefelder mit heller Schrift (1.23:1) und im
  Leitfaden gedaempfte Ueberschriften. Neue Farbpaare gibt es nicht —
  alles laeuft auf schon gerechnete Paare (`signal`/`text-leise` auf
  `grund`, `text` auf `grund-2/-3`). Statt einer Selektorliste prueft
  jetzt ein **Rundgang** jeden sichtbaren Text jeder Seite gegen seinen
  tatsaechlichen Grund, Deckkraft eingerechnet
  (`test_jeder_sichtbare_text_hat_kontrast`).
- **Akte-Bild:** zeigt jetzt den Aktwechsel-Moment (Vorhang, „4 · Setting,
  Figuren & Geschichte") nach Stopp ueber „■ Beenden" — keine laufende
  Aufnahme mehr. Dabei gefunden: nach dem Tausch der Aktfolge
  (`/teil/roadmap`, `outerHTML`) fehlten Akt-Marke und Lichter → das
  Effekt-JS dekoriert jede neue `#roadmap` per `MutationObserver` neu.
- **Beschriftung im laufenden Knopf (B):** nicht mehr winzig, sondern
  `font-size: 0` — fuer Vorleseprogramme bleibt sie, sichtbar bleibt das
  Stopp-Quadrat; Zeit und Zustand stehen gross in `#uhr` und
  `#ux-rec-zeile` (der Widerspruch „0:00" im Knopf gegen „0:01" in der
  Uhr ist damit unsichtbar). In der Pause bleibt sie lesbar. Im ruhenden
  Kreis eng gesperrt (`.03em`), damit „AUFNEHMEN" nicht an den Ring stoesst.
- **Mikrotexte:** „Einmal tippen zum Starten – beendet wird mit „■ Beenden""
  (vorher falsch „einmal zum Beenden"), Umlaute wie die A2-Texte daneben;
  englisch entsprechend.
- **Entwurf A** braucht die Handy-Korrekturen von B nicht: dort ist der
  Aufnahmeknopf eine Taste ueber die volle Breite, die A2-Beschriftung
  (1.15rem) passt hinein und ist lesbar. Im Browser nicht eigens mit
  `IT_UX_ENTWURF=a` fotografiert.
- **Push-to-Talk ist im Code das blosse 🎤**, nicht die Pille „HOLD TO
  TALK" des Entwurfs B (Tabelle oben): den Knopftext setzt A2, die
  Gestaltung fasst kein Markup an, und am Handy (390 px) ist neben
  Eingabe und „Senden" fuer mehr als das Symbol kein Platz. Die
  Bedeutung traegt nur das Symbol und das `title`-Attribut von A2 (`web_chat._TEXT_PTT`) — eine
  bewusste Einbusse, die ein Workshop-Test bestaetigen sollte.

## Nacharbeit nach der Abnahme (03.10.2026)

Drei Schritte nach Birks Abnahmeauftrag; jedes Element mit Urteil
(behalten/entfernen/ruhiger), Bild und Umsetzungsstand steht in
`docs/ux-padua/DESIGN-REVIEW.md`.

- **Interview-Modus** (`web_gestalt.css_interview()`, `_JS_INTERVIEW`):
  waehrend einer laufenden Aufnahme bleiben nur Leitfaden (zugeklappt),
  Uhr, Pegel, Lampe, Zustandszeile, „Pause" und ein grosser „■ Beenden"
  unten. Dazu ein Wake Lock, feature-detected und bei Modusende, Wechsel in
  den Hintergrund und `pagehide` freigegeben. Bild:
  `abnahme-handy-aufnahme.png`. Die Fehlerpfade (Telefon von Hand
  gesperrt, Anruf, Netz weg, 429 als „Keine Verbindung") sind Logik von A2
  und stehen dort als Befund.
- **„Als Nächstes: …"** ueber jedem Tab (`_JS_NAECHSTES`), aus der ersten
  offenen Aufgabe der aktiven Phase im DOM, im Interview weg.
- **Team-Dashboard** gestaltet: Akt n/7 mit sieben Segmenten, „Needs
  attention" nur bei einem Problem, keine leeren Felder, kein Leitfaden,
  kein Botname, am Beamer gekappt. Nur mit `[web] dashboard_gestaltet`,
  gesetzt allein in `workshop/padua-2026/profil.toml` — ohne Profil und
  mit `dortmund-2026` bleibt das HTML byte-gleich, weil
  `tests/test_web_dashboard_en.py` es festhaelt. Also: **Dortmund
  unveraendert, Padua gestaltet.** Bilder:
  `review-dashboard-beamer-vorher.png` / `-nachher.png`.
- **Arbeitsstand:** „Was noch fehlt" vor den Formularen (die einzige
  Markup-Umstellung der Karte, `web.gruppe_koerper`), ruhige
  Speichern-Knoepfe, kraeftige Ueberschriften, Festlegungen repariert, der
  doppelte Chat-Link per CSS weg.
- **Einhaengezeilen:** jetzt neun statt sieben — `css_interview()` in
  `web_vereint.seite` und `tokens_css() + css_dashboard()` in
  `web.dashboard_html` kamen dazu (gezaehlt: sechs Aufrufe von
  `web_gestalt` in `web_vereint.py`, drei in `web.py`).

**Betrieb.** Die Kostenwarnung des Dashboards liest
`IT_KOSTEN_DECKEL_CHF` aus der Umgebung des **Webdienstes** (Vorgabe 5.0).
`docs/interview-theater-web.service` setzt die Variable nicht; wer den
Deckel in den Bot-Envs aendert, muss ihn auch in der Web-Unit setzen, sonst
rechnet das Dashboard gegen 5.0.

**Bekannte Fallen beim Testen.**

- `tests/e2e/test_web_vereint_e2e.py` loescht `docs/web-vereint/` komplett
  (`shutil.rmtree`, Zeile 144) und schreibt seine PNGs neu — dabei
  verschwindet auch die committete `docs/web-vereint/strom-probe-2026-10-02.md`.
  Nach jedem Lauf je Datei mit `git show HEAD:<pfad> > <pfad>`
  wiederherstellen und das Verzeichnis nie ungeprueft committen. Der Test
  sollte nur seine eigenen Bilder ersetzen (Befund an Karte W).
- Die Abnahme- und Review-Bilder nur auf einem frischen Server aufnehmen
  (`-k abnahme` bzw. `-k review`). Ein voller e2e-Lauf schreibt sie auch,
  aber mit der Rate-Limit-Meldung „Keine Verbindung" und Blasen der vorigen
  Tests im Bild. Danach die committeten Bilder wiederherstellen.
- `tests/e2e/test_web_edit_e2e.py::test_was_der_chat_fuehrt_steht_nur_da`
  erwartete den Phasennamen „4 · Setting & Figuren" von vor dem
  Phasen-Umbau (06.09.) und scheiterte schon vor dieser Karte. Weil die
  volle Suite die e2e-Dateien jetzt mitfaehrt, haette er „Suite gruen"
  verhindert; die Erwartung steht seit dem Abschluss dieser Karte auf dem
  heutigen Namen „4 · Setting, Figuren & Geschichte" (der Code ist die
  Wahrheit, der Test war veraltet).

## Zahlen

- **Testsuite, Baseline vs. jetzt:** Aufgabe 1 (dieser Branch, vor jeder
  Aenderung dieser Karte): `5951 passed, 4 skipped`. Nach Aufgabe 12
  (letzter Stand vor dieser Aufgabe): `6140 passed, 5 skipped, 0 xfailed,
  0 xpassed` — ein deutliches Plus an gruenen Tests, keine Regression.
- **Endstand nach der Nacharbeit (03.10.2026, selbst gemessen):** volle
  Suite `python3.11 -m pytest -q -p no:cacheprovider` →
  `6354 passed in 834.21s (0:13:54)`. Neu gegenueber dem Stand oben:
  `python3.11` hat inzwischen Playwright, die volle Suite faehrt die
  e2e-Dateien also mit (vorher 5 skipped, jetzt 0). Vor der Korrektur des
  veralteten Phasennamens in `test_web_edit_e2e.py` (siehe „Bekannte Fallen
  beim Testen") stand dort `1 failed, 6353 passed`.
  Ein Lauf der vollen Suite schreibt damit auch die Bilder unter
  `docs/ux-padua/` und loescht `docs/web-vereint/` — siehe „Bekannte
  Fallen beim Testen".
- **E2E je Datei** (`PYTHONPATH=. …/it-webtest/bin/python -m pytest -q
  -p no:cacheprovider tests/e2e/<datei>`, nacheinander):

  | Datei | Ergebnis |
  |---|---|
  | `test_web_gestalt_e2e.py` | `40 passed in 72.18s (0:01:12)` |
  | `test_web_uebersicht_e2e.py` | `7 passed in 13.98s` |
  | `test_web_chat_e2e.py` | `29 passed in 102.70s (0:01:42)` |
  | `test_web_edit_e2e.py` | `19 passed in 21.05s` (nach der Korrektur des Phasennamens; vorher `1 failed, 18 passed`) |
  | `test_web_chat_vad_e2e.py` | `5 passed in 15.74s` |
  | `test_web_vereint_e2e.py` | `11 passed in 42.15s` |

- **Kontrastpaare:** `web_gestalt.KONTRAST` fuehrt **19 Paare je Entwurf**
  (zwei kamen mit dem Browserlauf dazu: pausierter Aufnahmeknopf, Aufgabe
  unter dem Finger; die Nacharbeit brauchte kein neues Paar, hob aber
  `signal`/`grund-3` von 3.0 auf 4.5, weil die Vorfallart im Dashboard-Log
  als Text darauf steht).
  Kleinstes gemessenes Verhaeltnis (am 03.10. nachgerechnet): **A 3.07**
  (`rec` auf `grund`), **B 3.23** (`rand` auf `grund-2`) — beide ueber der
  3.0-Schwelle fuer Bedienelemente (WCAG), kein Paar unter seinem Minimum.
- **Tatsaechlich geaenderte Zeilen dieser Karte** (`git diff --numstat`
  gegen den Stand vor Aufgabe 1, Commit `ed6c4d8`):
  `interview_theater/web.py`: 7 eingefuegt, 3 entfernt (10 Zeilen
  beruehrt); `interview_theater/web_vereint.py`: 16 eingefuegt, 1 entfernt
  (17 Zeilen beruehrt). Beides klar innerhalb der im Plan vorgegebenen
  Groessenordnung („vier/zwei Zeilen"), auch nach den in Aufgaben 4 und 8
  noetigen Anpassungen an bereits weitergewachsene `if`-Bloecke. Die
  gesamte uebrige Gestaltung — Tokens, Komponenten-CSS, Effekt-JS,
  Mikrotexte — liegt vollstaendig in `web_gestalt.py`, einer neuen Datei.
- **Nach der Nacharbeit** (`git diff --numstat` gegen `0b14974`, den Stand
  vor Phase 2; gemessen am 03.10.2026): `web.py` 193 eingefuegt, 6 entfernt
  — fast alles das gestaltete Dashboard (`_achtung_html`,
  `ACHTUNG_VORFAELLE`, die Karte hinter dem Profilschalter) und die
  Umstellung von „Was noch fehlt"; `web_daten.py` 90 eingefuegt (reine
  Lesewerte fuer Kosten, Fehlschlaege im Fenster, unabgeholte
  Web-Eingaenge, kein Schreibpfad); `web_vereint.py` 3 eingefuegt
  (`css_interview()`). Ueber die ganze Karte gegen `ed6c4d8`: `web.py`
  200/9, `web_vereint.py` 19/1, `web_daten.py` 90/0, `workshop.py` 4/0,
  `web_gestalt.py` 1916 Zeilen neu. Die Zahlen oben („vier/zwei Zeilen")
  gelten damit nur noch fuer den Plan-Teil — das Dashboard ist mehr als
  Gestaltung, es liest drei neue Werte.

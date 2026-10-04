# Padua Web-Chat: neue Phase zeigt ihren Anfang + Bilder zoombar

Kanban-Karte t_abc12cf7. Branch `wt/t_abc12cf7` (schon ausgecheckt in diesem
Worktree, kein Merge nach main, kein Push).

## Kontext

Zwei unabhaengige Korrekturen am Browser-Chat (`interview_theater/web_chat.py`,
mitgebaut von `interview_theater/web_vereint.py` und `web_gestalt.py`):

1. Nach einem Phasenwechsel scrollt der Chat ans Ende statt zum Anfang der
   neuen Phase.
2. Ein im Chat angezeigtes Bild (die Telefon-Organisationskarte,
   `interview_theater/static/handys/phase-N.png`, Klasse `.karte`) laesst
   sich nicht vergroessern, und beim (bisherigen) Seiten-Pinch-Zoom waechst
   der Record-Knopf (`#interview`) ueberproportional mit.

Beide Fixes leben im selben, von beiden Workshop-Profilen (Dortmund +
Padua) gemeinsam genutzten Modul `web_chat.py` (Markup + `_CHAT_JS`/`_js()`,
eingebunden sowohl auf der Chat-Einzelseite als auch — ungeaendert, per
`web_chat.chat_koerper()`/`web_chat._js()` — auf der vereinten Seite
`web_vereint.seite()`). **Beide Profile muessen danach gruen bleiben**
(`scripts/pruefe_profil --alle`), auch wenn die Karte funktional nur fuer
Padua gedacht ist.

**Koordination mit anderen Karten/Worktrees (wichtig, siehe
AGENTS.md-Fallen):**
- Kanban-Karte t_626639a8 ("Web-Chat pro Phase") ist blockiert und baut
  SPAETER eine vollstaendige Phasentrennung des sichtbaren Verlaufs. Diese
  Karte hier baut NUR die Scroll-Korrektur innerhalb des bestehenden,
  ungetrennten Verlaufs — keine Phasentrennung vorwegnehmen.
- Kanban-Karten t_cc4306db und t_4b7e05ad aendern `web_chat.py` bzw.
  `web_vereint.py` in anderen Worktrees parallel. **Vor Abschluss dieser
  Karte**: `git fetch origin && git merge origin/main` in diesem Branch,
  Konflikte gegen den hier beschriebenen Umfang aufloesen (eigene Scroll-
  und Overlay-Aenderungen behalten, fremde Aenderungen aus origin/main
  nicht verwerfen).

## Globale Vorgaben (fuer beide Tasks)

- Python-Interpreter:
  `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
  (Systempython 3.9 kann `X | None` nicht importieren). Playwright +
  Chromium sind unter diesem Interpreter bereits installiert und verifiziert
  lauffaehig.
- CSP (AGENTS.md): **kein** `style="..."`-Attribut, **kein** `on...=`-Handler
  im ausgelieferten HTML. Dynamische Werte ausschliesslich ueber CSSOM
  (`element.style.setProperty(...)`) bzw. `addEventListener`, nie inline.
- `web_chat.py` wird von BEIDEN Profilen genutzt — keine Aenderung darf
  Dortmund sichtbar verschlechtern. Keine profilabhaengige Verzweigung
  einbauen, sofern nicht unbedingt nötig; beide Fixes sind rein
  funktional/strukturell und sollen fuer jede Gruppe gleich wirken.
- Jede neue serverseitige Zeile/jedes neue Markup-Attribut MUSS sowohl in
  `web_chat.chat_koerper()` (von der Chat-Einzelseite UND von
  `web_vereint.seite()` genutzt) als auch im zugehoerigen JS-Teil von
  `web_chat._CHAT_JS`/`web_chat._js()` stehen — es gibt nur EINE Kopie
  dieses Markups/Skripts fuer beide Seiten, nicht duplizieren.
- Tests: `pytest` (Projektkonvention siehe `AGENTS.md`). Es gibt sowohl
  HTML/Server-Vertragstests ohne Browser (`tests/test_web_chat_js.py`,
  `tests/test_web_chat_karte.py`, `tests/test_web_chat.py`, ...) als auch
  echte Browsertests unter `tests/e2e/` (Playwright, siehe
  `tests/e2e/README.md` fuer Konventionen: Server als Subprozess,
  `_warte_auf_server`, Handy-Viewport 390×844, Screenshots nur bei
  `IT_SCHUSS_AKTUALISIEREN=1` ins Repo kopieren, sonst `/tmp`).
  Referenzvorlagen: `tests/e2e/test_web_cothinker_status_screenshot_e2e.py`
  (kurz, Subprozess-Server-Muster) und `tests/e2e/test_web_chat_e2e.py`
  (umfassender, Interaktion mit dem Chat).
- Folge `superpowers:test-driven-development` in jedem Task: Test zuerst
  rot, dann Implementierung gruen. Fuer Task 1 ausdruecklich auch den
  "Mutanten" pruefen: den Fix kurz durch die alte, unbedingte
  `nachUnten()`-Logik ersetzen und bestaetigen, dass der neue e2e-Test dann
  ROT wird (Beleg, dass der Test wirklich etwas pruft) — danach den Fix
  wiederherstellen.
- Commit nach Abschluss JEDES Tasks (nicht erst am Ende), mit Co-Authorship
  gemaess Systemhinweis.

## Task 1 — Scroll zeigt den Anfang der neuen Phase

**Datei:** `interview_theater/web_chat.py` (Markup in `chat_koerper()`,
JS in `_CHAT_JS`).

**Hintergrund/Code-Lage (Stand dieser Planung, siehe Zeilen zur
Orientierung — bei Abweichung gilt der tatsaechliche Code):**
- `_CHAT_JS` definiert `nachUnten()` (web_chat.py ~Zeile 856), das sowohl
  `verlauf.scrollTop = verlauf.scrollHeight` als auch
  `window.scrollTo(0, document.body.scrollHeight)` setzt (deckt die
  Chat-Einzelseite und die vereinte Seite gleichzeitig ab — beide Zeilen
  bleiben so stehen, sie sind kein Zufall).
- `nimmZustand(daten)` (~Zeile 889) ruft `nachUnten()` IMMER, wenn
  `neu.length` (neue Nachrichten da sind), sowie wenn man vorher unten
  stand und die letzte Blase sich aenderte (laufendes Transkript). Dieser
  zweite Fall (laufendes Transkript/Strom) bleibt unveraendert — nur der
  erste Fall (neue Nachrichten) wird um eine Phasenwechsel-Pruefung
  erweitert.
- Am Ende der IIFE (~Zeile 3160) steht beim initialen Seitenaufbau
  `nachUnten(); hole();` — auch das ist zu ersetzen.
- `daten.phase` kommt bei JEDEM Poll vom Server mit
  (`web_daten.web_chatzustand`, Schluessel `"phase"`, Wert `None` oder eine
  Zahl 1..7) — bislang liest `nimmZustand` diesen Wert nur fuer den
  Platzhalter-Text (`_platzhalter_fuer`), nicht fuer den Scroll.
- Der Eintritt in eine Phase schickt IMMER eine Bot-Nachricht mit dem
  wortgleichen Anfang `"▶️ Phase "` (siehe `phasentexte._KOPF_EINTRITT`,
  deutsch `"▶️ Phase {nummer} von {gesamt} · {name}"`, englisch
  `"▶️ Phase {nummer} of {gesamt} · {name}"` in
  `interview_theater/sprachen/en/texte.toml`) — dieser Praefix ist
  sprachunabhaengig gleich und damit ein verlaesslicher, bereits
  vorhandener Marker, OHNE dass eine neue Datenbankspalte noetig ist.

**Aufgabe:**
1. Server (`chat_koerper`): dem `#verlauf`-Div ein zusaetzliches Attribut
   `data-phase="{...}"` mitgeben (Wert aus `daten.get("phase")`, leer/`""`
   wenn `None` — analog zu `data-letzte`/`data-aenderung` direkt daneben).
2. JS: beim Aufbau von `zustand` (wo auch `letzte`/`aenderung` aus den
   `dataset`-Werten gelesen werden) `phase` dazunehmen:
   `phase: parseInt(verlauf.dataset.phase, 10) || 0` (0 = "keine Phase
   bekannt", da echte Phasen 1..7 sind und nie 0).
3. Eine Funktion `function phasenkopfzeile()`, die unter den aktuell im DOM
   stehenden `.blase.bot`-Elementen das LETZTE mit
   `textContent.indexOf('▶️ Phase ') === 0` zurueckgibt (oder `null`).
4. Eine Funktion `function scrolleZuPhasenanfang()`: findet die
   Phasenkopfzeile; wenn vorhanden, `element.scrollIntoView({block:
   'start'})` (das reicht fuer BEIDE Seiten — Chat-Einzelseite mit
   Dokument-Scroll und vereinte Seite mit internem `#verlauf`-Scroll:
   `scrollIntoView` passt automatisch jeden scrollbaren Vorfahren an, ein
   zweigleisiger Hack wie bei `nachUnten()` ist hier nicht noetig); sonst
   Ruckfall auf `nachUnten()`.
5. In `nimmZustand`: VOR dem bestehenden `if (neu.length) { nachUnten(); }`
   feststellen, ob sich die Phase gegenueber dem bisherigen `zustand.phase`
   geaendert hat (`var phaseAlt = zustand.phase; var phaseNeu = (typeof
   daten.phase === 'number') ? daten.phase : null;` — NUR wenn `phaseAlt`
   > 0 UND `phaseNeu` bekannt UND `phaseNeu !== phaseAlt`, gilt es als
   Wechsel). `zustand.phase` IMMER aktualisieren, wenn `daten.phase` eine
   Zahl ist (auch beim allerersten Poll, damit nicht jeder Poll faelschlich
   als "Wechsel" zaehlt).
   Ist ein Wechsel erkannt, ruft der `neu.length`-Zweig
   `scrolleZuPhasenanfang()` statt `nachUnten()`. In JEDEM anderen Fall
   (kein Wechsel, oder der zweite bestehende Zweig fuer das laufende
   Transkript) bleibt alles exakt wie bisher.
6. Beim initialen Seitenaufbau (Ersatz fuer die unbedingte `nachUnten();`
   kurz vor `hole();`): `scrolleZuPhasenanfang();` statt `nachUnten();`
   (Fallback innerhalb der Funktion greift, wenn noch keine Phasenzeile im
   Verlauf steht, z. B. ganz am Anfang von Phase 1 ohne vorherige
   Nachricht).

**Server-Vertragstest (ohne Browser, `tests/test_web_chat_js.py` oder
`tests/test_web_chat.py`, nach bestehendem Muster in der jeweiligen Datei):**
- `data-phase="<n>"` steht im gerenderten `#verlauf` fuer eine Gruppe mit
  gesetzter Phase; leer (oder "0"/fehlend, je nach gewaehlter Kodierung —
  beide sind akzeptabel, Test schreibt fest, welche) ohne Phase.
- `_js()` enthaelt `function phasenkopfzeile` und `function
  scrolleZuPhasenanfang`.

**E2E-Test (Playwright, neue Datei `tests/e2e/test_web_chat_phasenscroll_e2e.py`,
Muster wie `tests/e2e/test_web_chat_e2e.py`/die kurze Vorlage
`test_web_cothinker_status_screenshot_e2e.py`):**
- Datenbank mit EINER Gruppe im Web-Kanal aufbauen (`repo.sichere_gruppe`,
  `repo.setze_gruppe_kanal(..., "web")`, `repo.stelle_web_token_sicher`).
  Phase auf 2 setzen (`repo.setze_phase`), dann per
  `interview_theater.phasentexte.eintritt(conn, chat_id, 2)` (oder die
  vorhandene Chat-Schreibfunktion, die dieselbe Zeile erzeugt — im Code
  nachsehen, WER `phasentexte.eintritt()` normalerweise aufruft, z. B.
  `knoepfe.stationen`/`befehle.wechsle_phase`, und denselben Weg nutzen
  statt den Text von Hand zu duplizieren) eine Phase-2-Eintrittsnachricht
  als Bot-Zeile ablegen (`repo.lege_web_post_an(..., richtung=RICHTUNG_AUS,
  typ=WEB_TYP_TEXT (oder passender Typ), text=<eintrittstext>)`).
  Danach GENUEGEND weitere Bot-/Gruppen-Nachrichten anlegen, dass der
  Verlauf im 390×844-Viewport laenger als der sichtbare Bereich ist (z. B.
  30+ kurze Zeilen).
  Dann Phase auf 3 wechseln (`repo.setze_phase(conn, chat_id, 3)`) und via
  `phasentexte.eintritt(conn, chat_id, 3)` + `repo.lege_web_post_an(...)`
  eine Phase-3-Eintrittsnachricht anlegen (diese muss NACH den langen
  Phase-2-Nachrichten in der `web_post`-Reihenfolge stehen).
- Seite im Playwright-Context oeffnen (390×844, `is_mobile=True`, wie in
  den Referenztests), warten bis der Poll die neuen Nachrichten geholt hat
  (`page.wait_for_timeout` oder auf die Blase mit dem Phase-3-Text warten,
  `page.wait_for_selector` mit Text-Filter oder
  `page.get_by_text("Phase 3", exact=False)`).
- Assertion: die Phase-3-Kopfzeile (`get_by_text` o. ae.) ist im sichtbaren
  Bereich (`element.bounding_box()` innerhalb des Viewports, oder
  `element.scroll_into_view_if_needed()` NICHT aufrufen und statt dessen
  pruefen, dass sie schon sichtbar ist — z. B. per
  `expect(element).to_be_in_viewport()` falls `playwright.sync_api.expect`
  genutzt wird, sonst manuell via `bounding_box()` gegen die Viewport-Hoehe
  pruefen). UND: `verlauf.scrollTop` (per `page.eval_on_selector` o. ae.)
  ist NICHT gleich `verlauf.scrollHeight - verlauf.clientHeight` (also
  nicht am Ende).
- **Mutanten-Gegenprobe** (siehe TDD-Hinweis oben, vor dem finalen Commit
  einmal durchgefuehrt und wieder rueckgaengig gemacht — nicht Teil des
  dauerhaften Diffs): den Phasenwechsel-Zweig in `nimmZustand` kurz
  deaktivieren (so dass immer `nachUnten()` laeuft) und bestaetigen, dass
  genau dieser neue Test dann fehlschlaegt.
- Diese Datei darf, falls hilfreich, zusaetzlich einen Screenshot nach
  `docs/ux-padua/chat-zoom/phasenwechsel-scroll.png` schreiben (nur bei
  `IT_SCHUSS_AKTUALISIEREN=1` ins Repo kopieren, siehe Vorlage) — Pflicht
  ist das nicht, die Scroll-Assertion ist der eigentliche Nachweis.

**Abschluss Task 1:** `pytest` (zumindest die neuen/betroffenen Dateien
gezielt, die volle Suite folgt am Gesamtende) gruen, Commit.

## Task 2 — Bilder zoombar per Overlay, Record-Knopf zoomt nicht mehr mit

**Dateien:** `interview_theater/web_chat.py` (Markup in `chat_koerper()`,
CSS in `_CSS_CHAT`, JS in `_CHAT_JS`). Ggf. `interview_theater/web_gestalt.py`
NUR falls dort beim Audit (Schritt 0) tatsaechlich ein vw/vh-Fund fuer ein
Bedienelement auftaucht (siehe unten) — nicht vorsorglich anfassen.

**Hintergrund/Code-Lage:**
- Ein Bild im Chat ist AUSSCHLIESSLICH die Telefon-Organisationskarte
  (`n.bild`, Dateiname wie `phase-4.png` unter
  `interview_theater/static/handys/`) — es gibt in diesem Code keinen
  Weg, dass eine Gruppe selbst ein Foto in den Chat hochlaedt. Rendering:
  serverseitig `_bild_html()`/`_blase_html()` (~Zeile 3223), clientseitig
  `bildVon(n)`/`inhaltVon(n)` (~Zeile 731). Beide erzeugen
  `<img ... class="karte">`, serverseitig fuer den ersten Seitenaufbau,
  clientseitig fuer jede weitere ueber den Poll ankommende Nachricht — es
  gibt nur diese EINE Bildsorte, kein Code dafuer anfassen, das es nicht
  gibt.
- Ein Test zum erwarteten `_bild_html`-Markup existiert schon:
  `tests/test_web_chat_karte.py` (nicht aendern, nur daran orientieren,
  welche Attribute das `<img>` heute hat: `src`, `alt`, `loading="lazy"`,
  `class="karte"` — das Overlay darf diese Erwartungen nicht brechen, ggf.
  ERGAENZEN um ein neues Test-File statt die bestehenden Assertions zu
  schwaechen).
- `.karte { max-width: 100%; display: block; ... }` in `_CSS_CHAT`
  (~Zeile 256) ist die einzige Groessenregel des Thumbnails — unveraendert
  lassen, das Overlay ist ein zusaetzliches Element, kein Ersatz.
- Record-/PTT-/Senden-Knopf (`#interview`, `#ptt`, `#senden`) sind in
  `_CSS_CHAT` (web_chat.py, Basis-CSS fuer beide Profile) bereits reine
  `rem`-Werte, KEIN `vw`/`vh` (gegengeprueft per Volltextsuche). Das
  Padua-spezifische Overlay-CSS in `web_gestalt.py`
  (`_CHAT_A`/`_CHAT_B`/`_INTERVIEW`) nutzt fuer dieselben Knoepfe
  ausschliesslich `rem`/CSS-Variablen (`--rec-hoehe`, `--tippflaeche`,
  beide in `rem` definiert) — ebenfalls kein `vw`/`vh`. Die einzige
  `vh`-Beziehung im ganzen Chat-Bereich ist `web_vereint._VH_JS`, das
  `--vh` aus `visualViewport.height` setzt und NUR `body { height:
  var(--vh, 100dvh); }` (Hoehe der Flex-Schale) beeinflusst — NICHT die
  Groesse eines Knopfes direkt.
- **Schritt 0 (Pflicht, vor jeder Aenderung):** selbst nachpruefen (z. B.
  `grep -n "vw\|vh\b" interview_theater/web_chat.py interview_theater/web_vereint.py interview_theater/web_gestalt.py`),
  ob sich seit dieser Planung etwas geaendert hat, und das Ergebnis im
  Taskreport kurz zusammenfassen (gefunden/nicht gefunden, wo). Wird DOCH
  ein `vw`/`vh` an einem Bedienelement (Knopf/Icon/Touch-Target) im
  Chat-Fuss-Bereich gefunden, auf `rem`/`px` umstellen.
- **Die eigentliche, im Code nachweisbare Ursache fuer "der Record-Knopf
  waechst beim Zoomen ueberproportional" ist das native Browser-Pinch-Zoom
  der ganzen Seite selbst** — nicht eine fehlerhafte CSS-Einheit (siehe
  Schritt 0: es gibt keine). Browser (insbesondere iOS Safari) behandeln
  `position: fixed`-Elemente beim seitenweiten Pinch-Zoom anders als
  normal fliessenden Inhalt; das Ergebnis ist optisch ein "zu stark
  mitwachsender" fixer Fuss. Der robuste, von der Karte selbst verlangte
  Weg (Abschnitt B2) ist deshalb: seitenweites Pinch-/Doppeltipp-Zoom im
  Chat-Bereich per CSS abschalten (`touch-action`), und dafuer dem Bild
  ein EIGENES, bewusstes Zoom-Overlay geben (Abschnitt B1). Danach kann
  der Fuss gar nicht mehr "beim Zoomen" wachsen, weil es im Chat kein
  Seiten-Zoom mehr gibt. **Wichtiger Hinweis fuer die Entscheidung:** die
  `<meta name="viewport">`-Zeile (`web._VIEWPORT_META`) wird von ALLEN
  Seiten geteilt (Dashboard, Leitfaden, Probenansicht, Gruppenseite) — sie
  hier anzufassen (z. B. `user-scalable=no`) wuerde Seiten ausserhalb
  dieser Karte beeinflussen und ist NICHT Teil dieses Tasks (das ist
  vermutlich der Umfang der separaten Kanban-Karte t_27eb35ba, auf die der
  Kartentext verweist — sie ist aus dieser Umgebung nicht einsehbar).
  Stattdessen: eine CSS-Regel NUR in `_CSS_CHAT` (web_chat.py), die ueber
  `web_vereint.scope_css(web_chat._CSS_CHAT, ".panel-chat")` auf der
  vereinten Seite automatisch auf `.panel-chat` eingeschraenkt wird (ein
  nackter `body`-Selektor wird beim Scopen zur Scope-Klasse selbst, siehe
  Docstring/Kommentare in `web_vereint.py` zu `scope_css` — nicht raten,
  im Code nachsehen) und auf der Chat-Einzelseite direkt auf `<body>`
  wirkt. Damit bleibt der Effekt strikt auf den Chat beschraenkt, andere
  Seiten/Panels sind unberuehrt.

**Aufgabe B1 — Bild-Overlay:**
1. Markup in `chat_koerper()`: EIN zusaetzliches, zunaechst `hidden`
   Overlay-Element anhaengen (z. B.
   `<div class="bild-overlay" id="bild-overlay" hidden><button type="button" id="bild-overlay-schliessen" aria-label="...">✕</button><img id="bild-overlay-img" src="" alt=""></div>`).
   Es gibt nur EINE Stelle im Markup dafuer (wie der Rest von
   `chat_koerper()`, gemeinsam fuer beide Seiten).
2. CSS in `_CSS_CHAT`: `.bild-overlay` als Vollbild-Overlay
   (`position: fixed; inset: 0;` — KEIN `100vw`/`100vh`, `inset: 0` braucht
   das nicht —, hoher `z-index`, dunkler Hintergrund, `display: flex` zum
   Zentrieren, `touch-action: pinch-zoom` fuer natives Pinch-Zoom
   INNERHALB des Overlays trotz der Sperre in Schritt B2);
   `.bild-overlay[hidden] { display: none; }` (gleiches Muster wie
   `.angehalten[hidden]` weiter oben in derselben Datei); `#bild-overlay-img`
   mit `max-width: 100%; max-height: 100%; object-fit: contain;
   touch-action: pinch-zoom;`; `#bild-overlay-schliessen` als Knopf mit
   ausreichender Treffergroesse (`min-width`/`min-height` in `rem`, z. B.
   `2.75rem`), oben rechts positioniert (`position: absolute; top:
   .6rem; right: .6rem;` — innerhalb des `position: fixed`-Overlays, nicht
   nochmal viewport-relativ).
3. JS in `_CHAT_JS`:
   - Referenzen auf die drei neuen Elemente holen
     (`document.getElementById('bild-overlay')` usw.), wie bei den
     bestehenden optionalen Elementen defensiv auf `null` pruefen.
   - EIN delegierter Klick-Listener auf `verlauf` (nicht je Bild einzeln,
     da Bilder sowohl serverseitig vorgerendert als auch spaeter per
     `blase()`/`ersetze()` dynamisch eingefuegt werden): Klick auf ein
     `img.karte` oeffnet das Overlay mit dessen `src`/`alt`.
   - `oeffneBildOverlay(src, alt)` setzt `src`/`alt` am Overlay-Bild,
     entfernt `hidden`, und legt per `history.pushState(...)` einen
     Zustand an (fuer die Zurueck-Geste/-Taste).
   - `schliesseBildOverlay()` setzt `hidden` wieder, leert `src` (keine
     Datei im Hintergrund haengen lassen), und geht per `history.back()`
     zurueck, wenn der aktuelle History-Zustand der selbst gesetzte ist.
   - Schliessen durch: Klick auf den Overlay-Hintergrund SELBST (nicht auf
     das Bild — sonst stoert das die Pinch-Geste, `ev.target ===
     ueberlagerung`), Klick auf den ✕-Knopf, `Escape`-Taste
     (`keydown`-Listener auf `document`), UND `popstate` (Zurueck-Geste/
     -Taste: schliesst das Overlay, OHNE erneut `history.back()`
     aufzurufen — sonst Doppel-Navigation).
4. Bestehende Tests NICHT aendern (`tests/test_web_chat_karte.py`); neuer
   Server-Vertragstest (z. B. in `tests/test_web_chat_karte.py` ergaenzen
   oder neue Datei): `chat_koerper(...)`-Ausgabe enthaelt
   `id="bild-overlay"`, `id="bild-overlay-img"`,
   `id="bild-overlay-schliessen"`, und das Overlay ist `hidden` im
   Ausgangszustand; `_js()` enthaelt `oeffneBildOverlay`,
   `schliesseBildOverlay`, `pinch-zoom`.

**Aufgabe B2 — kein globales Pinch-/Doppeltipp-Zoom im Chat:**
1. In `_CSS_CHAT`: `body { touch-action: pan-x pan-y; }` (NICHT `none` —
   Scrollen/Wischen muss weiter funktionieren, nur Zoomen per Geste
   abschalten). Begruendung als Kommentar im Code: warum `pan-x pan-y`
   und nicht `none` oder `manipulation`.
2. Pruefen (lesend, `scope_css`-Implementierung ansehen), dass dieser
   `body`-Selektor beim Einbinden in die vereinte Seite korrekt zu
   `.panel-chat` wird und NICHT versehentlich auch `.panel-stand`/
   `.panel-textbuch`/das Dashboard trifft.
3. Sicherstellen, dass `.bild-overlay`/`#bild-overlay-img` davon NICHT
   betroffen sind (eigenes `touch-action: pinch-zoom` auf dem Overlay UND
   dem Bild selbst, siehe B1 Schritt 2 — beide testen, ob eins der beiden
   allein in allen relevanten Browsern reicht, ist NICHT Teil des
   Pruefbudgets dieser Karte; beide zu setzen ist die robuste,
   nicht-schaedliche Wahl).

**E2E-Tests (Playwright, neue Datei
`tests/e2e/test_web_chat_bildzoom_e2e.py`, Muster wie oben):**
1. Datenbank mit einer Gruppe aufbauen, EINE Nachricht mit `bild="phase-4.png"`
   anlegen (`repo.lege_web_post_an(conn, chat_id, repo.RICHTUNG_AUS,
   repo.WEB_TYP_SYSTEM, text="...", bild="phase-4.png")` — im Code
   nachsehen, ob `WEB_TYP_SYSTEM` der richtige Typ ist, siehe
   `web_kanal.WebKanal.sende_bild` als Vorbild). Die echte Datei
   `interview_theater/static/handys/phase-4.png` existiert bereits im
   Repo und wird vom laufenden Server ausgeliefert.
2. Seite oeffnen (390×844), auf das `img.karte`-Element klicken/tippen
   (`page.click("img.karte")` oder `page.tap(...)`).
3. Assertion: `#bild-overlay` ist sichtbar (nicht `hidden`),
   `#bild-overlay-img` hat eine `src`, die auf dieselbe Datei zeigt wie
   das Thumbnail, UND `naturalWidth`/`naturalHeight` des Overlay-Bildes
   sind > 0 (das Bild ist wirklich geladen, nicht nur im DOM).
4. Schliessen testen: EINMAL per Klick auf den ✕-Knopf (`#bild-overlay-img`
   danach wieder `hidden`), UND in einem zweiten Testfall per Klick auf
   den Overlay-Hintergrund (nicht auf das Bild selbst).
5. Screenshots (Pflicht laut Kartentext): VOR dem Tippen auf das Bild und
   mit geoeffnetem Overlay nach `docs/ux-padua/chat-zoom/` speichern
   (z. B. `bild-vorher.png`, `bild-overlay-offen.png`) — Verzeichnis ggf.
   neu anlegen. Diese zwei Screenshots IMMER ins Repo schreiben (nicht
   hinter `IT_SCHUSS_AKTUALISIEREN`, anders als die Vorlage — der
   Kartentext verlangt sie als Abnahmebeleg, nicht als optionalen
   Debug-Schuss).

**E2E-Test fuer die Knopfgroesse ueber DeviceScaleFactor (Playwright, kann
in dieselbe neue Datei oder eine weitere, z. B.
`tests/e2e/test_web_chat_knopfgroesse_e2e.py`):**
1. Zwei Browser-Contexts (oder zwei aufeinanderfolgende Seitenaufrufe)
   erzeugen: gleiche `viewport`-Groesse (390×844), aber
   `device_scale_factor=2` einmal und `device_scale_factor=3` das andere
   Mal (`browser.new_context(viewport=..., device_scale_factor=...)`).
2. Auf jeder der beiden Seiten `#interview` (den Record-Knopf) per
   `bounding_box()` oder `page.evaluate("el => el.getBoundingClientRect()")`
   in CSS-Pixeln messen.
3. Assertion: Breite UND Hoehe sind in beiden Faellen (deviceScaleFactor 2
   vs. 3) GLEICH (CSS-Pixel sind per Definition unabhaengig vom
   Device-Pixel-Ratio — dieser Test ist eine Regressionswache gegen ein
   kuenftiges `vw`/`vh` an diesem Knopf, kein Beweis, dass es HEUTE schon
   kaputt waere).

**Abschluss Task 2:** `pytest` (neue/betroffene Dateien gezielt), Commit.

## Abschlussreview (nach beiden Tasks)

1. `git fetch origin && git merge origin/main`, Konflikte in `web_chat.py`/
   `web_vereint.py` gegen den oben beschriebenen Umfang aufloesen (eigene
   Scroll-/Overlay-/Touch-Action-Aenderungen behalten).
2. Volle Suite im VORDERGRUND: `pytest` (ganzer Lauf, Ausgabe zitierbar in
   der Abschlussmeldung).
3. `python -m scripts.pruefe_profil --alle` (deckt `dortmund-2026` UND
   `padua-2026` ab).
4. Finaler Whole-Branch-Review (code-reviewer-Template,
   `superpowers:requesting-code-review`) gegen den ganzen Branch-Diff seit
   dem Abzweigpunkt von `main`.
5. Screenshots unter `docs/ux-padua/chat-zoom/` vorhanden und aussagekraeftig.
6. Abschlussmeldung: Commit-SHAs, Branch, Testkommando + letzte
   Zusammenfassungszeile der Suite, `pruefe_profil`-Ergebnis fuer beide
   Profile, Pfade der Screenshots. Kritische/wichtige, nicht behobene
   Befunde vollstaendig und woertlich nennen.

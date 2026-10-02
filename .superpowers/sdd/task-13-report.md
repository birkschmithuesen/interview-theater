# Aufgabe 13: Phasenleiste und Phase per Klick -- Report

Status: DONE

## Was geaendert wurde

- `interview_theater/befehle.py`
  - Neue Funktion `wechsle_phase(conn, tg, klm, e, chat_id, nummer, quelle="befehl")`:
    der eine Weg fuer Befehl UND Klick (`phasen.setze`, Meldung,
    `knoepfe.eintritt_in_phase` mit Try/Except wie bisher).
  - `_befehl_phase` endet jetzt auf `wechsle_phase(..., quelle="befehl")` statt den
    Umschaltteil selbst zu machen.
  - Neuer versteckter Befehl `_befehl_phaseklick` -> `wechsle_phase(..., quelle="web")`.
  - `"/phaseklick"` zu `_BEKANNTE_BEFEHLE` (Kommentar wie bei `/festlegung`/`/sprache`),
    `behandle()` bekommt den `elif`-Zweig. `BEFEHLE_LISTE` unveraendert (nicht beworben).

- `interview_theater/web_vereint.py`
  - Neue Funktion `phase_post(handler, db_pfad, token, chat_id, schluessel)`:
    `POST /g/<token>/chat/phase` -- Nonce, `bestaetigt`, Nummer pruefen (403, dann 400),
    legt bei Erfolg `/phaseklick <nummer>` als `WEB_TYP_BEFEHL`-Eingang ab (202).
    Setzt selbst nichts.
  - `_leiste_html` ausgefuellt: `<details class="roadmap">` mit Kopf
    "Phase {nummer}/{gesamt} · {name} — {erledigt}/{gesamt_aufgaben}", je Phase ein
    `<li>` mit Phasenknopf/-name und der Aufgabenliste (`data-ziel-tab`,
    `data-ziel-feld`).
  - Neuer Parameter `klickbar: bool = True`: bei `False` wird statt
    `<button class="phase-knopf" data-phase="...">` ein reines
    `<span class="phase-name">` gerendert -- kein `data-phase`, kein Knopf.
    `seite()` ruft `_leiste_html(roadmapdaten, nonce_wert, klickbar=chat_vorhanden)`.
  - `_VEREINT_JS`: Klick-Handler fuer `.phase-knopf` VOR der Tab-Weiche, mit
    Inline-Rueckfrage (zweiter Klick erst loest den POST aus) und `setze('chat')`
    nach Erfolg (die Eintrittsnachricht kommt im Chat an).
  - `seite()` ersetzt `__SICHER__` durch `_TEXT_PHASE_SICHER`.

- `interview_theater/web_chat.py`
  - `_phase(handler, db_pfad, token, chat_id, schluessel)` als duenne Weiche zu
    `web_vereint.phase_post` (lokaler Import, Zyklus-Vermeidung wie bei `strom`).
  - `_POSTWEGE["phase"] = _phase`.

- `interview_theater/web_schreiben.py`
  - Nachtrag am bestehenden Kommentar "Die Phase setzt allein die Gruppe" ueber
    den Klick-Weg und warum er trotzdem kein Feld dieser Seite ist.

- `tests/test_phase_klick.py` (neu): die Brief-Tests woertlich uebernommen, plus
  zwei eigene Tests (siehe Abweichungen).

- `tests/test_web_chat_js.py`: `test_das_js_nennt_jeden_postweg` angepasst (siehe
  Abweichungen) -- bestehender Test, keine neue Datei.

## Abweichungen vom Brief (alle wie vom Dispatch verlangt entschieden und begruendet)

1. **Geteiltes `id="nonce"` statt eigenem `nonce-roadmap`-Feld.** Der Brief fuegt
   ein zweites `<input type="hidden" id="nonce-roadmap">` in `_leiste_html` ein.
   Stattdessen liest der Phase-Klick-Handler das EINE `id="nonce"`-Feld, das schon
   im Stand-Panel steht (geteilt mit dem Chat, `mit_nonce=False`). Begruendung: der
   Chat-Poll aktualisiert dieses Feld alle 2-10 s unabhaengig davon, welches Panel
   gerade sichtbar ist (`document.hidden` bremst ihn nur, verhindert ihn nicht) --
   das Stand-Panel-Nachladen tut dasselbe beim Stand-Tab. Ein eigenes
   `nonce-roadmap`-Feld wuerde dagegen nur beim initialen Laden der Seite einen
   frischen Wert bekommen und nach dem Nonce-Fenster (eine Stunde) mit 403 scheitern,
   wenn die Gruppe laenger auf der Seite war, ohne neu zu laden -- genau der Fall,
   den die Karte mit dem sanften Nachladen vermeiden wollte. Kein Test im Brief
   verlangt ein `nonce-roadmap`-Element; `_leiste_html` behaelt den `nonce_wert`-
   Parameter fuer Signaturstabilitaet, nutzt ihn aber nicht mehr zum Rendern eines
   Feldes.
2. **`data-sicher` als echtes HTML-Attribut (`getAttribute`/`setAttribute`/
   `removeAttribute`) statt `phase.dataset.sicher`.** Der Brief-Code nutzt
   `phase.dataset.sicher` (wie das bestehende Vorbild in `web.py:244-245`), aber
   der Brief-eigene Test prueft den LITERALEN String `"data-sicher"` im JS-Quelltext
   (`assert "data-sicher" in web_vereint._VEREINT_JS`). `"dataset.sicher"` enthaelt
   diesen Substring nicht (kein `-` zwischen `data` und `sicher`). Um den
   vorgegebenen Test woertlich zu erfuellen, schreibt der Handler jetzt
   `phase.getAttribute('data-sicher')` / `setAttribute` / `removeAttribute` --
   funktional identisch, nur mit dem literalen Attributnamen im Quelltext.
3. **`_TEXT_ROADMAP_KOPF` mit `{nummer}/{gesamt}` statt `{nummer} von {gesamt}`.**
   Der Brief-Text schreibt "Phase {nummer} von {gesamt} · ...". Mit den echten
   Werten einer frischen Gruppe (Phase 1 von 7, 0 von 1 Aufgaben in Phase 1) liefert
   das keine Teilzeichenkette "1/7" oder "1 / 7" -- der eigene Test
   `test_die_leiste_steht_auf_der_seite_und_ist_knapp` verlangt aber genau das.
   Geaendert auf `"Phase {nummer}/{gesamt} · {name} — {erledigt}/{gesamt_aufgaben}"`
   (z. B. "Phase 1/7 · Begriffe — 0/1") -- passt zum Testnamen "ist_knapp" und erfuellt
   den Test woertlich.
4. **`web_chat.schreibend(db_pfad)` statt eigenem `db.verbinde`/`close`.** Der Brief
   zeigt in `phase_post` ein manuelles `db.verbinde(...)` mit `try/finally: close()`.
   `web_chat.py` hat dafuer schon den Context-Manager `schreibend()`, den `_senden`/
   `_knopf`/`_interview` benutzen. Verwendet, um keine zweite Schreibverbindungs-
   Logik einzufuehren; verhaelt sich identisch (`db.verbinde`, WAL, busy_timeout).
5. **Zwei zusaetzliche eigene Tests** (ueber den Brief hinaus, vom Dispatch verlangt):
   - `test_die_leiste_ohne_chat_hat_keine_klickbaren_phasen`: eine Telegram-Gruppe
     (kein Web-Kanal) bekommt die Roadmap ohne `data-phase`-Knoepfe, aber weiterhin
     mit `<details class="roadmap">` und `data-ziel-tab=`.
   - `test_phaseklick_fuer_telegram_gruppe_ist_404`: `/chat/phase` ist fuer eine
     Telegram-Gruppe 404 (derselbe Schutz wie jeder andere `/chat/*`-Weg, kein
     Bot, der `web_post` liest).
6. **`tests/test_web_chat_js.py::test_das_js_nennt_jeden_postweg` angepasst.**
   Dieser bestehende Test (nicht aus dem Brief) verlangt, dass jeder Eintrag in
   `web_chat._POSTWEGE` einen Aufrufer in `web_chat._CHAT_JS` hat. `"phase"` wird
   aber ausschliesslich von der vereinten Seite aufgerufen (`web_vereint._VEREINT_JS`)
   -- die Roadmap gibt es nur dort, nicht im Chat-Alleingang (`/g/<token>/chat`).
   Testausnahme fuer `"phase"` ergaenzt, die stattdessen `web_vereint._VEREINT_JS`
   prueft. Ohne diese Anpassung waere die Suite nach dieser Aufgabe nicht gruen
   gewesen.

## Tests

```
$PY -m pytest tests/test_phase_klick.py -q -p no:cacheprovider
21 passed

$PY -m pytest tests/test_phase_klick.py tests/test_befehle.py tests/test_phasen.py \
  tests/test_web_edit.py -q -p no:cacheprovider
216 passed

$PY -m pytest tests/test_sprache_bitgleich.py tests/test_web_chat_js.py \
  tests/test_web_vereint.py tests/test_web_strom_route.py \
  tests/test_web_vereint_nachladen.py -q -p no:cacheprovider
93 passed

$PY -m pytest -q -p no:cacheprovider
1 failed, 5266 passed, 2 skipped in 385.90s
-- einziger Fehlschlag: tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]
   (der bekannte, vorbestehende Fehlschlag aus dem Implementer-Contract, unberuehrt)
```

Baseline (Aufgabe 1): 5008 passed, 1 failed, 2 skipped.
Jetzt: 5266 passed, 1 failed, 2 skipped -- Zahl waechst (+258), kein neuer Fehlschlag.

## Deviations summary (short)

Siehe Abschnitt oben, Punkte 1-6: geteilter Nonce statt eigenem Feld (begruendet),
`data-sicher` als echtes Attribut statt `dataset.sicher` (um den woertlichen Test
zu erfuellen), Kopfzeilenformat mit Bruch statt "von" (um "1/7" im Test zu erfuellen),
`web_chat.schreibend` statt dupliziertem `db.verbinde`, zwei zusaetzliche Tests fuer
Telegram-Gruppen (wie vom Dispatch verlangt), ein bestehender Test
(`test_das_js_nennt_jeden_postweg`) musste um die Ausnahme `"phase"` ergaenzt werden.

## Concerns

- Keine offenen Fragen an Birk. Die Entscheidung "geteilter Nonce statt
  `nonce-roadmap`" ist eine bewusste Verbesserung gegenueber dem Brief-Text und im
  Report begruendet (Punkt 1) -- falls Birk ausdruecklich ein eigenes Feld wollte,
  waere das ein Nachtrag, aber kein Test verlangt es und die Begruendung (Nonce-
  Verfall nach einer Stunde) spricht dagegen.
- `_befehl_phase`s Docstring wurde gekuerzt (der Umschaltteil ist jetzt in
  `wechsle_phase` dokumentiert); inhaltlich nichts verloren.

## Fix-Runde 1

Review-Rueckmeldung zu Commit `b7ac5a3` (vier Minuma, "dieselbe JS wird von der
naechsten Aufgabe wieder angefasst"). Alle vier behoben:

1. **Antwortstatus des Phasenklicks wird jetzt geprueft.** `sendePhase(phase,
   zweiter)` (neue Funktion in `_VEREINT_JS`) schickt den POST und liefert die
   `Response` zurueck. Bei `r.status === 403` und noch keinem zweiten Versuch
   holt `friskeNonce()` einmal `teil/stand`, liest den frischen Nonce **ueber
   `DOMParser`** aus dem zurueckgegebenen Fragment (nicht per Regex auf den
   rohen Text -- dazu gleich mehr) und schreibt ihn ins geteilte
   `id="nonce"`-Feld, danach genau EIN zweiter Versuch
   (`sendePhase(phase, true)`). Derselbe Grundsatz wie
   `web_chat.postJson`/`postAudio`, nur ohne deren Scope (die beiden IIFEs
   teilen sich keinen Gueltigkeitsbereich, siehe Moduldocstring). Bei Erfolg
   (`r.ok`): Roadmap sofort nachladen (`ladeRoadmap()`) und `setze('chat')`.
   Bei jedem anderen Ausgang (4xx/5xx **oder** Netzausfall im `.catch`):
   **kein** Tabwechsel, der Server-Satz (bei 4xx im Klartext-Body) geht in
   `#fehler` (`zeigeFehler(satz)`, 8 s Anzeige, dieselbe Form wie
   `web_chat.meldeFehler`, aber eine eigene kleine Fassung, weil kein Zugriff
   auf `TEXT`/`zustand` aus dem anderen IIFE besteht). `#fehler` existiert
   genau dann, wenn auch die Phasenknoepfe existieren (beide haengen an
   `chat_vorhanden`), die Funktion prueft trotzdem defensiv auf `null`.
2. **Die Roadmap laedt jetzt selbst nach.** Neuer Teil `/g/<token>/teil/roadmap`
   (`web_vereint._TEILE = ("stand", "roadmap")`, Helfer `_roadmap_html`,
   `sende_teil` verzweigt). Im JS: `ladeRoadmap()` (eine neue Funktion, per
   Funktionsdeklaration gehoben, damit der Klick-Handler sie unabhaengig von
   der Definitionsreihenfolge rufen kann) holt den Ausschnitt **im selben
   `setInterval`-Takt wie das Stand-Panel**, aber **ohne** dessen
   Sichtbarkeits-/Bearbeitet-Gate -- die Roadmap steht ausserhalb jedes Panels
   und ist immer sichtbar, unabhaengig vom aktiven Tab. Beim Austausch
   (`outerHTML`) werden `<details open>`-Zustand (wie beim Stand-Panel, per
   Summary-Text) **und** ein gerade "bewaffneter" Knopf (`data-sicher="1"`)
   uebernommen -- sonst wuerde ein Nachladen mitten in der Rueckfrage lautlos
   entwaffnen. Zusaetzlich wird nach einem erfolgreichen Klick sofort
   `ladeRoadmap()` gerufen (muss nicht bis zu `NACHLADEN_MS` warten); da der
   Phasenwechsel selbst asynchron im Bot-Prozess laeuft (der POST liefert nur
   202, der Eingang wird erst danach verarbeitet), zeigt dieser sofortige
   Aufruf die neue Phase nicht garantiert schon -- der naechste periodische
   Takt (max. 10 s) holt sie in jedem Fall nach.
   Server-Test: `tests/test_phase_klick.py::test_der_roadmap_teil_liefert_die_leiste`,
   `test_der_roadmap_teil_zeigt_die_aktuelle_phase`,
   `test_der_roadmap_teil_hat_keine_knoepfe_ohne_chat`,
   `test_der_roadmap_teil_fuer_unbekanntes_token_ist_404`,
   `test_ein_unbekannter_teil_bleibt_404`.
   JS-String-Test: `test_das_js_laedt_die_roadmap_im_selben_takt`.
3. **Ein neu bewaffneter Knopf entwaffnet jeden anderen** (`entwaffneAlle(ausser)`,
   gerufen beim Bewaffnen). **Jeder Ausgang entwaffnet und stellt die
   Beschriftung wieder her** -- Erfolg, Server-Fehler UND der `.catch`-Zweig
   (Netzausfall) teilen sich dieselben zwei Zeilen
   (`removeAttribute('data-sicher')` + `textContent = ...beschriftung`), statt
   wie vorher nur `disabled = false` im `.catch` zu setzen. Test:
   `test_das_js_entwaffnet_auf_jedem_ausgang` (zaehlt die drei Stellen).
4. **`_leiste_html` verliert `nonce_wert`.** Signatur jetzt
   `_leiste_html(roadmapdaten: list[dict], klickbar: bool = True) -> str`; der
   Aufruf in `seite()` reicht nur noch `roadmapdaten` und `klickbar` durch.
   Test: `test_leiste_html_braucht_keinen_nonce_mehr` (Signaturpruefung per
   `inspect`).

**Ein Befund aus dem eigenen Review, nicht aus der Dispatch-Nachricht:**
die erste Fassung von `friskeNonce()` suchte den frischen Nonce per Regex
(`/id="nonce" value="([^"]*)"/`) direkt im rohen Serverantwort-Text. Diese
Regex steht aber als Zeichenkette im ausgelieferten `<script>` und waere
damit ein **zweites** `id="nonce"` auf der Seite -- genau die Invariante, die
`tests/test_web_vereint.py::test_nur_eine_nonce_id_in_der_vereinten_seite`
bewacht (schlug beim ersten Lauf der angeforderten Testdateien fehl).
Behoben, indem `friskeNonce()` stattdessen `DOMParser` benutzt und
`doc.getElementById('nonce')` liest -- dieselbe Technik wie beim Stand- und
jetzt auch beim Roadmap-Nachladen, keine zweite Zeichenkette mit dem
woertlichen Attributnamen im Skript.

**Ein zweiter, kleinerer Kollateralschaden beim ersten Testlauf:** die
urspruengliche Aufgabe-13-Pruefung `test_die_leiste_ohne_chat_hat_keine_klickbaren_phasen`
prueft "data-phase=" nicht im HTML einer Telegram-Gruppe -- seit `ladeRoadmap()`
denselben Selektor-Text (`'.phase-knopf[data-phase="' + ...`) im eingebetteten
Skript traegt, das auf JEDER Seite mitkommt, war das ein Fehlalarm. Der Test
prueft jetzt den Rumpf OHNE das `<script>`-Element (per Regex herausgeschnitten)
statt den ganzen Seitentext.

### Tests (Fix-Runde 1)

```
$PY -m pytest tests/test_phase_klick.py tests/test_web_vereint*.py \
  tests/test_web_chat_js.py tests/test_web.py -q -p no:cacheprovider
140 passed

$PY -m pytest -q -p no:cacheprovider
1 failed, 5277 passed, 2 skipped in 417.42s (0:06:57)
-- einziger Fehlschlag weiterhin der bekannte, vorbestehende:
   tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]
```

Vorher (nach dem ersten Commit `b7ac5a3`): 5266 passed. Jetzt: 5277 passed
(+11, die neuen Fix-Runde-1-Tests) -- waechst, kein neuer Fehlschlag.

### Dateien (Fix-Runde 1)

- `interview_theater/web_vereint.py` (Haupt-Diff: `_VEREINT_JS`,
  `_leiste_html`, `_TEILE`, `_roadmap_html`, `sende_teil`, neue
  `_TEXT_PHASE_FEHLER_NETZ`)
- `tests/test_phase_klick.py` (neue Tests angehaengt, eine bestehende
  Assertion praezisiert)

## Fix-Runde 2

Re-Review zu Commit `f5be2dd`. Ein wichtiger Befund, zwei Minima -- alle
behoben:

**Wichtig: `ladeRoadmap` klappte die aufgeklappte Leiste bei jedem Takt
lautlos wieder zu, und der allererste Takt tauschte immer.**

- **Ursache 1 (verloren gegangenes `open`):** `offene(ziel)` -- die
  Hilfsfunktion vom Stand-Panel -- sucht nur unter **Nachkommen**
  (`panel.querySelectorAll('details[open] > summary')`). Die Roadmap hat
  aber kein verschachteltes `<details>`: `ziel` selbst **ist** das
  `<details id="roadmap">`. `offene(ziel)` fand deshalb nie etwas, die
  Wiederherstellung traf folglich nie zu, und ein aufgeklapptes
  `<details>` klappte bei jedem Austausch zu. Behoben: `var warOffen =
  ziel.open;` vor dem Tausch, `neues.open = warOffen;` danach -- die
  eigene Eigenschaft direkt, statt des fuer verschachtelte Elemente
  gedachten Summary-Text-Abgleichs.
- **Ursache 2 (`roadmapLetzter` startete bei `null`):** anders als
  `panelLetzter` (im `setInterval` aus der Live-DOM geseedet, BEVOR das
  Sichtbarkeits-/Lauf-Gate prueft) startete `roadmapLetzter` bei `null`
  und wurde erst nach der ERSTEN Antwort gesetzt. Jeder String ist
  ungleich `null`, also tauschte `ladeRoadmap` beim allerersten Takt
  immer -- auch ohne jede Aenderung, und dabei (vor der ersten Behebung)
  mit verlorenem `open`. Behoben: in `ladeRoadmap` wird `aktuell`
  (`document.getElementById('roadmap')`) zuerst geholt, `roadmapLetzter`
  bei `null` sofort aus `aktuell.outerHTML` geseedet -- noch **vor** dem
  `roadmapLaeuft || document.hidden`-Gate, exakt wie beim Stand-Panel.

**Minimum 1:** `_roadmap_html` prueft den Web-Kanal jetzt mit
`web_daten.web_chat_id_nach_token(conn, token) is not None` statt mit
`web_daten.web_chatzustand(conn, token) is not None` -- die leichte Abfrage
(nur die `chat_id` zum Token mit `kanal = 'web'`) statt des ganzen
Chat-Polls (Verlauf, Aenderungen, Antworten), den dieser Ausschnitt nicht
braucht.

**Minimum 2:** der Kommentar beim sofortigen `ladeRoadmap()`-Aufruf nach
einem erfolgreichen Klick behauptete vorher sinngemaess "zeigt die neue
Phase sofort" -- tatsaechlich legt der POST nur den Eingang ab, der Bot
verarbeitet ihn danach in seinem eigenen Prozess und Takt. Der Kommentar
sagt jetzt ausdruecklich, dass der sofortige Versuch die neue Phase NICHT
zuverlaessig zeigt und der naechste periodische Takt massgeblich bleibt.

**Tests** (alle neu, `tests/test_phase_klick.py`, Abschnitt "Fix-Runde 2"):
`test_roadmap_letzter_wird_aus_der_live_dom_geseedet` (Seedung UND
Reihenfolge vor dem Gate), `test_der_offene_zustand_der_leiste_selbst_bleibt_erhalten`
(`ziel.open`/`neues.open`, kein Aufruf von `offene(...)` mehr in dieser
Funktion), `test_roadmap_html_nutzt_die_leichte_kanalpruefung`
(Quelltext-Pruefung per `inspect.getsource`), `test_der_sofortige_nachlade_kommentar_behauptet_nichts_falsches`.
Playwright ist in dieser Umgebung nicht installiert
(`ModuleNotFoundError`, `tests/e2e/` wuerde ohnehin uebersprungen) --
deshalb String-/Quelltexttests statt eines Browser-Falls, wie in der
Dispatch-Nachricht als Alternative vorgesehen.

**Ein Nebeneffekt beim Testenschreiben:** die ersten Fassungen von drei
dieser Tests scheiterten an den eigenen erklaerenden Kommentaren (z. B.
enthaelt der Kommentar selbst die Woerter `offene()` und
`web_chatzustand`, um zu sagen, was NICHT mehr passiert) -- die
Assertions wurden daraufhin auf den tatsaechlichen Aufruf
(`offene(ziel)`, `web_chatzustand(conn, token)`) bzw. auf getrennte
Teilwoerter (`"NICHT"`, `"zuverlaessig"`) umgestellt, statt den Kommentar
selbst wortkarger zu machen.

### Tests (Fix-Runde 2)

```
$PY -m pytest tests/test_phase_klick.py tests/test_web_vereint*.py \
  tests/test_web_chat_js.py tests/test_web.py -q -p no:cacheprovider
144 passed

$PY -m pytest -q -p no:cacheprovider
1 failed, 5281 passed, 2 skipped in 391.47s (0:06:31)
-- einziger Fehlschlag weiterhin der bekannte, vorbestehende:
   tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]
```

Vorher (nach `f5be2dd`): 5277 passed. Jetzt: 5281 passed (+4, die neuen
Fix-Runde-2-Tests) -- waechst, kein neuer Fehlschlag.

### Dateien (Fix-Runde 2)

- `interview_theater/web_vereint.py` (`ladeRoadmap`: Seedung + `open`
  direkt am Element; `_roadmap_html`: leichte Kanalpruefung; Kommentar
  beim sofortigen Nachladen praezisiert)
- `tests/test_phase_klick.py` (vier neue Tests)

# Padua UX: die Weboberflaeche gestalten — Matrix/Terminal x Theater

> **Fuer agentische Arbeiterinnen:** PFLICHT-UNTERSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Aufgabe fuer Aufgabe. Die Schritte tragen
> Kaestchen (`- [ ]`) zum Abhaken.

**Ziel:** Die vereinte Weboberflaeche (Karte W) mit dem Web-Chat (Karte A2) sieht aus und
fuehlt sich an wie ein Werkzeug, mit dem vierzehn Schauspielstudierende in Padua am Telefon
gern arbeiten: dunkler Terminal-Grund, Phosphor als Signal, Buehnenmetaphern fuer die sieben
Akte, ein Aufnahmeknopf, dessen Zustand niemand missverstehen kann.

**Architektur:** **Ein neues Modul** `interview_theater/web_gestalt.py` traegt alles:
einen Block Design-Tokens je Entwurf, das Komponenten-CSS, das Effekt-JavaScript und die
englischen Mikrotexte. Es wird an **fuenf** Zeilen eingehaengt — vier in `web_vereint.seite`,
je eine in `web.textbuch_html` und `web.leitfaden_html`. Kein Endpunkt, keine Logik, kein
Modellaufruf, kein SQL. Das Markup bleibt das aus A2/W; was die Gestaltung zusaetzlich
braucht (Zustandsmarken am Aufnahmeknopf, Fortschrittsbalken, Akt-Moment, Belohnung), legt
das Effekt-JS zur Laufzeit an — **kein einziges neues Element im serverseitigen HTML von
A2/W**.

**Technik:** Python 3.11, Standardbibliothek. Vanilla JS ohne Build, kein npm, keine
Fremdquelle, kein Webfont. Tests: `pytest` (ohne Netz, ohne Browser) plus `tests/e2e` mit
Playwright 1.61.0 aus dem Wegwerf-venv.

---

## Baseline

In **diesem** Worktree (`padua-workshop/t_5ad6ac77-plan-ux-gestaltung`, Basis
`origin/main` = `f66f68b`) selbst gemessen:

> Nachtrag Architekt (01.10.2026): der Branch wurde danach auf `origin/main` = `04e57dd`
> (Merge A1) umgesetzt; beide Commits beruehren nur `docs/`. Auf diesem Stand ist A1 da
> (`workshop/padua-2026/profil.toml` Zeile 19: `code = "en"` — ANNAHME 8 ist damit
> erfuellt), `interview_theater/web_chat.py` und `web_vereint.py` fehlen aber noch:
> W und A2 sind nicht gemergt. Die Zahl unten ist deshalb **nicht** die Baseline der
> Umsetzung — Aufgabe 1 misst sie neu, und ohne W/A2 bricht Aufgabe 1 wie vorgesehen ab.

```
/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 \
  -m pytest -q -p no:cacheprovider
→ 2887 passed, 1 skipped in 242.66s
```

`PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
Die `.venv` im Hauptbaum wird **nicht** benutzt.

**Diese Zahl ist nicht die Messlatte der Umsetzung.** A1, A2, W und S bringen jeweils
eigene Tests mit. Aufgabe 1 misst die Baseline auf dem Umsetzungs-Branch **neu** und traegt
sie dort ein; ab Aufgabe 2 gilt diese neue Zahl. `1 skipped` bleibt (`tests/e2e`
ueberspringt sich per `importorskip`).

---

## Vorbedingung: A1, A2, W und S muessen in `main` sein

Diese Karte gestaltet, was andere Karten bauen. Sie steht auf:

| Karte | Branch / Plan | Was daraus gebraucht wird |
|---|---|---|
| **A1** Sprache | `padua-workshop/t_28ed3dde-padua-a1-sprache-pro-workshop-profil-eng` (umgesetzt) | `sprache.Texte`, `sprachen/en/texte.toml`, `tests/test_sprache_texte.py` mit `UMGESTELLT`/`ALLE_MODULE`/`BLEIBT_DEUTSCH` |
| **A2** Web-Chat | `docs/superpowers/plans/2026-09-30-padua-a2-web-arbeitsplatz.md` (geplant) | `web_chat._CSS_CHAT`, `#interview`, `#ptt`, `#fuss[data-interview]`, `#uhr`, `#pegel`, `#warteschlange`, `.blase`, `.leiste`, `.quittung`, `#tippt` |
| **W** Web vereint | `docs/superpowers/plans/2026-09-30-padua-w-web-vereint.md` (geplant) | `web_vereint.seite`, `_CSS_VEREINT`, `scope_css`, `TABS`, `_tabs_html`, `_leiste_html`, `_VEREINT_JS`, `_STROM_JS`, `.blase.vorlaeufig` |
| **S** Absicherung | `docs/superpowers/plans/2026-09-30-padua-s-absicherung-web.md` (geplant) | `web.CSP_VORLAGE`, `web.mit_nonce`, `web.csp_nonce` |

**Aufgabe 1 ist ein Vorbedingungs-Check.** Schlaegt er fehl, **bricht die Umsetzung ab** und
meldet genau, welcher Name fehlt. A1, A2, W oder S nachzubauen ist ausdruecklich
**verboten** — jede ist eine eigene Karte mit eigener Abnahme.

---

## Gewaehlter Entwurf und die Umschaltregel

Die beiden klickbaren Muster liegen fertig im Repo (Commit `ba4d8b9`):
`docs/ux-padua/entwurf-a.html` (**Terminal zuerst**) und `entwurf-b.html`
(**Buehne zuerst**), dazu `docs/ux-padua/ENTWUERFE.md` mit den fuenf
Unterscheidungsachsen, den Screenshots und der Empfehlung.

**Empfohlen ist A.** Der Grund in einem Satz: der Aufnahmeknopf ist das wichtigste Element
dieser Oberflaeche (Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden
gedrueckt), und A gibt ihm die volle Breite statt eines Kreises und trennt die beiden
Mikrofone auf vier Achsen (Form, Ort, Farbe, Verb) statt auf dreien.

**Die Umschaltregel (Aufgabe 1, Schritt 5):**

1. Lies die Zeile `**Entscheidung Birk: …**` in `docs/ux-padua/ENTWUERFE.md`.
2. Lies die Kommentare der Umsetzungskarte `t_f09c20e3`.
3. Steht dort **A** oder **B**, gilt das: setze `web_gestalt.VORGABE_ENTWURF` entsprechend.
4. Steht dort **offen** (der heutige Stand), gilt die Empfehlung **A** — und die **erste
   Zeile** von `docs/ux-padua/BERICHT.md` sagt das ausdruecklich.
5. **Kein Blockieren.** Es wird nie auf eine Antwort gewartet.

Beide Token-Saetze stehen vollstaendig in `web_gestalt.TOKENS` (Aufgabe 2). Der Wechsel von
A nach B ist danach: `VORGABE_ENTWURF = "b"` (eine Zeile) **oder** `IT_UX_ENTWURF=b` in der
Env des Webdienstes. Die vier benannten Komponenten-Abweichungen (Tab-Ort, Knopfform,
Akt-Moment, Skript-Satz) haengen im CSS an derselben Wahl und sind in den Aufgaben 5–9 je
mit einem `# Abweichung B:`-Block ausgewiesen.

---

## Befunde an anderen Karten (hier NICHT repariert)

**Befund 1 (A2, Aufgabe 11, `web_chat._CHAT_JS`): Drucke waehrend eines Uebergangs werden
nicht ignoriert.** Gelesen im A2-Plan:

```js
interviewKnopf.addEventListener('click', function () {
    if (zustand.interview) { beendeInterview(); } else { starteInterview(); }
});
```

`starteInterview()` setzt `setzeInterview(true)` erst **nach** dem `getUserMedia`-Promise.
Ein zweiter Druck in dieser Zeit (auf einem Telefon, das die Mikrofonfreigabe erst
einblendet, sind das leicht zwei Sekunden) ruft `starteInterview()` erneut auf: zweiter
`MediaRecorder`, zweiter `chat/interview`-POST. Und `beendeInterview()` setzt
`setzeInterview(false)` **sofort**, waehrend die Warteschlange noch bis zu 240 × 500 ms auf
ihre Uploads wartet — ein Druck in diesem Fenster startet eine neue Aufnahme, waehrend das
alte `/fertig` noch aussteht. **Das ist genau das Dortmunder Fehlerbild** (ein Knopf 14× in
93 Sekunden).

**Diese Karte repariert das nicht** (es ist Logik, nicht Gestaltung). Sie macht den
Uebergang nur **sichtbar**: `aria-busy="true"`, `cursor: progress`, gedaempfte Flaeche und
der Zustandstext „Starting …" / „Sending …". Der Befund geht in `docs/ux-padua/BERICHT.md`
unter „Befunde an A2/W" **mit dem Vorschlag**, in `_CHAT_JS` eine Zustandsvariable
`zustand.uebergang` zu fuehren und den Click-Handler mit `if (zustand.uebergang) { return; }`
zu beginnen.

**Befund 2 (A2, Aufgabe 11): die Beschriftung des Aufnahmeknopfes steht als deutsches
Literal im JavaScript** (`interviewKnopf.textContent = an ? 'Aufnahme beenden' : 'Interview
aufnehmen';`), nicht in `_TEXT_INTERVIEW_AN`/`_AUS`. In Padua stuende dort Deutsch. W
Aufgabe 15 koennte es mitnehmen; sicher ist es nicht. **Folge fuer diese Karte:**
`web_gestalt` schreibt **nie** in `#interview.textContent` (sonst zwei Schreiber auf einem
Knoten) und legt seinen Zustandstext in ein **eigenes** Element `#ux-rec-zeile` **neben**
den Knopf. Steht der Befund bei der Umsetzung schon behoben, aendert das hier nichts.

---

## Hotspots

| Datei | Regel in diesem Plan |
|---|---|
| `interview_theater/web_vereint.py` | **vier Zeilen** in `seite()` (CSS anhaengen, Skript anhaengen). Kein Umbau von `scope_css`, `_tabs_html`, `_leiste_html`, `_VEREINT_JS`, `_STROM_JS`. |
| `interview_theater/web.py` | **zwei Zeilen**: je eine in `textbuch_html` und `leitfaden_html`. Kein neues HTML, kein neues CSS in dieser Datei. |
| `interview_theater/web_chat.py` | **gar nicht.** Diese Karte fasst sie nicht an. |
| `interview_theater/web_daten.py`, `repo.py`, `db.py` | **gar nicht.** Kein neuer Schluessel im Zustands-Poll (siehe Aufgabe 9). |
| `interview_theater/sprachen/en/texte.toml` | ein neuer Abschnitt `["web_gestalt"]` am Dateiende. |
| `tests/test_sprache_texte.py` | `web_gestalt` in `UMGESTELLT` **und** `ALLE_MODULE`, die CSS-/JS-Konstanten in `BLEIBT_DEUTSCH`. |
| `AGENTS.md` | eine Zeile in der Modultabelle, ein Abschnitt unter „Weboberflaeche". |

Alles Neue geht in **ein** neues Modul: `interview_theater/web_gestalt.py`.

---

## Globale Vorgaben

Gelten fuer **jede** Aufgabe, auch wenn dort nicht wiederholt:

- **Projektsprache Deutsch**, ASCII-Umschrift `ue/oe/ae/ss` in Code, Docstrings, Kommentaren
  und Commit-Zeilen. **Nutzertexte dieser Karte sind englisch** (Padua) und stehen als
  deutsche `_TEXT_*`-Konstante im Modul plus englischem Eintrag in `sprachen/en/texte.toml`
  (A1) — dieselbe Bauart wie ueberall.
- **Kein Frontend-Build**, kein npm, keine CDN-, Google-Fonts- oder sonstige Fremdquelle,
  **kein `@font-face`**, **kein `@import`**. System-Schriftstacks.
- **CSP-Vertrag (Karte S):** kein `style="…"`-Attribut, kein `on…=`-Handler im
  ausgelieferten HTML. Handler nur ueber `addEventListener`. Dynamische Werte ueber
  **CSSOM** (`el.style.setProperty('--pegel', wert)`) — das ist unter
  `style-src 'nonce-…'` erlaubt, `setAttribute('style', …)` waere es nicht.
  Die Richtlinie hat **kein `font-src`** und `default-src 'none'`: eine eingebettete
  Schrift waere geblockt.
- **`prefers-reduced-motion: reduce` schaltet jede Animation und jeden Uebergang ab**, und
  die Seite bleibt vollstaendig bedienbar. Kein Zustand haengt an einer Animation.
- **Kontrast:** jedes deklarierte Text/Grund-Paar ≥ 4.5 : 1, UI-Komponenten und grosse
  Schrift ≥ 3 : 1. Die Tabelle steht im Code (`web_gestalt.KONTRAST`) und wird im Test
  gerechnet, nicht geschaetzt.
- **Tippflaechen ≥ 44 × 44 px** (`--tippflaeche: 2.75rem`), Fliesstext ≥ 16 px. Der
  Aufnahmeknopf ist deutlich groesser (`--rec-hoehe`).
- **Kein Modellaufruf, kein SQL, kein neuer Endpunkt, kein Cookie, kein localStorage.**
- **E1:** der Telegram-Weg bleibt unberuehrt. **E6:** Zugang allein ueber `/g/<token>`.
  **E8:** kein Vorname, nirgends — auch nicht in Mustertexten.
- **Datenschutz:** Tests, Fixtures und Screenshots **nur** mit erfundenem Material
  (`simulation/interviews/`), **nie** `betrieb/**`.
- **Die drei Web-Grenzen gelten weiter** (kein Nachrichtentext/Transkript auf dem
  Dashboard, kein Volltranskript auf der Gruppenseite, kein Belegzitat ohne
  `zitat_geprueft = 1`). Gestaltung aendert daran nichts — aber die bestehenden Tests
  muessen gruen bleiben.
- **Das Team-Dashboard `/` bleibt unveraendert.** Es haengt am Beamer und ist ein anderer
  Kontext (offener Wunsch im BERICHT).
- **Nie `git stash`** ohne `-m <tag>`; nie `checkout`/`switch`; committet wird
  ausschliesslich auf dem Branch der Umsetzungskarte (`t_f09c20e3`). Kein Merge, kein Push.
- Jede Aufgabe endet gruen: `$PY -m pytest -q -p no:cacheprovider` ≥ Baseline aus Aufgabe 1.

---

## Annahmen

Was beim Planen **nicht** am Code geprueft werden konnte — je mit dem Kommando, das es
klaert. Wer eine Aufgabe anfaengt, in der eine Annahme steckt, fuehrt das Kommando
**zuerst** aus.

**ANNAHME 1 (alle Aufgaben) — die Flaeche aus A1/A2/W/S heisst so, wie ihre Plaene sie
nennen.** Gelesen im Plan, nicht am Code.

```
$PY -c "
from interview_theater import sprache, web, web_chat, web_vereint
for n in ('Texte',): print('sprache.'+n, hasattr(sprache,n))
for n in ('CSP_VORLAGE','mit_nonce','csp_nonce','textbuch_html','leitfaden_html'):
    print('web.'+n, hasattr(web,n))
for n in ('_CSS_CHAT','CHAT_PFAD'): print('web_chat.'+n, hasattr(web_chat,n))
for n in ('seite','_CSS_VEREINT','scope_css','TABS','_tabs_html','_leiste_html',
          '_VEREINT_JS','_STROM_JS'):
    print('web_vereint.'+n, hasattr(web_vereint,n))"
```
Erwartet: ueberall `True`. Ein `False` → **Aufgabe 1 bricht ab**.

**ANNAHME 2 (Aufgaben 5–9) — die Klassen und Kennungen im Markup.** Aus den Plaenen
gelesen: `#verlauf`, `#tippt`, `#fuss[data-segment-ms][data-interview]`, `#uhr`, `#pegel`
(mit `<span>` darin), `#warteschlange`, `#interview[data-laeuft]`, `#ptt[data-haelt]`,
`#eingabe`, `#senden`, `#nonce`, `.blase.bot|.gruppe` × `.text|.sprache|.datei`,
`.blase.vorlaeufig`, `.leiste button[data-message][data-daten]`, `.quittung[data-druck]`,
`.tabs button[data-tab][aria-selected]`, `.panel.panel-chat|-stand|-textbuch`,
`details.roadmap#roadmap`, `.phasen`, `.phase(.aktiv)`,
`.phase-knopf[data-phase][data-bezeichnung][data-sicher]`, `.aufgaben`,
`.aufgabe.erledigt|.offen|.laeuft[data-ziel-tab][data-ziel-feld]`, `#nonce-roadmap`.
Aus `web.py` heute schon geprueft: `.probe-szene`, `.szenenkopf`, `.angaben`, `.besetzung`,
`.replik[data-figur]`, `.replik.weiter`, `b.sprecher`, `.regie`, `.regie-zeile`, `.prosa`,
`.leiste button[aria-pressed]`.

```
$PY - <<'EOF'
import re
from interview_theater import web, web_chat, web_vereint
html = web_chat._CHAT_JS + web_vereint._VEREINT_JS + web_vereint._STROM_JS
for kennung in ("verlauf","tippt","fuss","uhr","pegel","warteschlange","interview",
                "ptt","eingabe","senden","nonce-roadmap"):
    print(kennung, kennung in html)
for klasse in ("phase-knopf","aufgabe","roadmap","panel-chat","vorlaeufig"):
    print(klasse, klasse in html or klasse in web_vereint._CSS_VEREINT)
EOF
```
Fehlt eine Kennung, wird sie **in der betroffenen Aufgabe** nachgeschlagen (`grep -n` in
`web_chat.py` / `web_vereint.py`) und der Selektor angepasst — **nicht** das Markup von
A2/W umgebaut. Braucht die Gestaltung wirklich eine Klasse, die es nicht gibt, wird sie
**additiv und minimal** ergaenzt, und der Commit benennt das.

**ANNAHME 3 (Aufgabe 4) — `web_vereint.scope_css` verkraftet kein `@keyframes`.** Gelesen
am Plan-Code: `_REGEL = re.compile(r"([^{}]+)\{([^{}]*)\}")` mit `sub` — der Rumpf
`50% { opacity: 0; }` eines `@keyframes` wuerde als eigene Regel gelesen und zu
`.panel-chat 50% { … }`. Deshalb die harte Regel dieses Plans: **`@keyframes` und `@media`
stehen ausschliesslich in `css_rahmen()`**, nie in `css_chat/stand/textbuch()`. Aufgabe 3
prueft das mit einem Test.

```
$PY -c "
from interview_theater import web_vereint
print(web_vereint.scope_css('@keyframes x { 50% { opacity: 0; } }', '.p'))"
```
Kommt dort `.p 50%` heraus, gilt die Regel wie beschrieben. Kommt `@keyframes` unveraendert
heraus (weil W es doch behandelt), bleibt die Regel trotzdem stehen — sie kostet nichts.

**ANNAHME 4 (Aufgabe 4) — die Reihenfolge im `<style>`.** `web._seite` baut
`<style>{_CSS_GEMEINSAM}{css}</style>`. Gestaltung muss **als letztes** in `css` stehen,
sonst gewinnen die frueheren Regeln bei gleicher Spezifitaet. Und weil A2/W ihr CSS ueber
`scope_css(..., ".panel-chat")` einschraenken, muss das Chat-CSS der Gestaltung **durch
dieselbe Funktion** laufen — sonst ist `#interview` (0,1,0,0) schwaecher als
`.panel-chat #interview` (0,1,1,0) und wirkt nicht.

```
grep -n "_CSS_GEMEINSAM}{css}" interview_theater/web.py
grep -n "scope_css(" interview_theater/web_vereint.py
```

**ANNAHME 5 (Aufgabe 11) — `tests/test_sprache_texte.py` verlangt `UMGESTELLT == ALLE_MODULE`
und kennt `BLEIBT_DEUTSCH` fuer CSS-/JS-Konstanten.** Im A1-Branch gelesen; dort stehen
schon `web._CSS_GRUPPE`, `web._TEXTBUCH_JS` usw. mit dem Grund „CSS, nur Kommentare
deutsch".

```
grep -n "UMGESTELLT\|ALLE_MODULE\|BLEIBT_DEUTSCH" tests/test_sprache_texte.py | head
grep -n "_CSS_GRUPPE\|_TEXTBUCH_JS" tests/test_sprache_texte.py
```

**ANNAHME 6 (Aufgabe 12) — Playwright 1.61.0 + chromium-1228 im Wegwerf-venv**, und
Chromium nimmt `--use-fake-device-for-media-stream`.

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -c "import playwright; print(playwright.__version__)"
```
Erwartet: `1.61.0`.

**ANNAHME 7 (Aufgabe 12) — W Aufgabe 16 hat `tests/e2e/test_web_vereint_e2e.py` samt
`_baue_datenbank` angelegt.** Diese Karte legt eine **eigene** Datei
`tests/e2e/test_web_gestalt_e2e.py` mit **eigener** Wegwerf-Datenbank an (`/tmp/it-ux.db`,
Port `127.0.0.1:8023`) und importiert nichts aus W — zwei Dateien, die sich einen Port
teilen, blockieren einander.

**ANNAHME 8 (Aufgabe 11) — das englische Profil heisst `padua-2026` und traegt
`sprache.code = "en"`.** In diesem Worktree geprueft: `workshop/padua-2026/profil.toml`
existiert und steht auf `code = "it"`; **der A1-Branch setzt es auf `"en"`**
(`git show padua-workshop/t_28ed3dde…:workshop/padua-2026/profil.toml`, Zeile 19). Es
traegt `geruest = true`, also startet damit kein Bot — fuer einen Textnachschlag laedt es
trotzdem (A1: „es laedt und laesst sich ansehen").

```
$PY -c "
import os; os.environ['IT_WORKSHOP'] = 'padua-2026'
from interview_theater import sprache; print(sprache.code())"
```
Erwartet: `en`. Kommt `it`, ist A1 nicht gemergt → **Aufgabe 1 bricht ab**. Heisst das
Profil anders, wird der richtige Name aus `ls workshop/` genommen und der Unterschied im
Commit benannt.

---

## Dateikarte

| Datei | Verantwortung | Aufgabe |
|---|---|---|
| `tests/test_ux_vorbedingung.py` | **neu.** Haelt die A1/A2/W/S-Flaeche fest, auf der diese Karte steht | 1 |
| `interview_theater/web_gestalt.py` | **neu.** Tokens, Kontrasttabelle, Komponenten-CSS, Effekt-JS, Mikrotexte | 2–9 |
| `tests/test_web_gestalt_tokens.py` | **neu.** Kontrast gerechnet, Tokens vollstaendig, Entwurfswahl | 2 |
| `tests/test_web_gestalt_css.py` | **neu.** reduced-motion, keine Fremdquelle, kein `@keyframes` im gescopten Teil, Druck bleibt hell | 3, 10 |
| `tests/test_web_gestalt_einhang.py` | **neu.** Der CSP-Vertrag am ausgelieferten HTML, Reihenfolge im `<style>` | 4 |
| `interview_theater/web_vereint.py` | vier Zeilen in `seite()` | 4 |
| `interview_theater/web.py` | je eine Zeile in `textbuch_html` und `leitfaden_html` | 10 |
| `tests/test_web_gestalt_js.py` | **neu.** Der Vertrag des Effekt-JS ohne Browser | 5–9 |
| `interview_theater/sprachen/en/texte.toml` | Abschnitt `["web_gestalt"]` | 11 |
| `tests/test_sprache_texte.py` | `web_gestalt` in beiden Mengen, CSS/JS in `BLEIBT_DEUTSCH` | 11 |
| `tests/e2e/test_web_gestalt_e2e.py` | **neu.** Browserlauf: Aufnahmezustaende, PTT, Akt-Moment, reduced-motion | 12 |
| `docs/ux-padua/*.png` | Abnahme-Screenshots aus der Demo-Datenbank | 12 |
| `docs/ux-padua/BERICHT.md` | **neu.** Entscheidungen, Verworfenes, offene Wuensche, Befunde | 13 |
| `AGENTS.md` | Modultabelle + Abschnitt unter „Weboberflaeche" | 13 |

---

## Aufgabenuebersicht

| # | Titel | kostet Geld |
|---|---|---|
| 1 | Vorbedingung A1/A2/W/S, Baseline, Entwurfswahl | nein |
| 2 | `web_gestalt.py`: Design-Tokens und die gerechnete Kontrasttabelle | nein |
| 3 | Das Grund-CSS: `css_rahmen`, reduced-motion, keine Fremdquelle | nein |
| 4 | Einhaengen in `web_vereint.seite` — vier Zeilen, CSP-Vertrag am HTML | nein |
| 5 | Der Chat: Blasen, Knopfleisten, Strom-Cursor, Denk-Zustand | nein |
| 6 | Tableiste und Panels (A: unten am Daumen · B: oben) | nein |
| 7 | Die sieben Akte: Phasenleiste, Fortschritt, Bestaetigung | nein |
| 8 | Die zwei Aufnahmeknoepfe — der wichtigste Teil der Karte | nein |
| 9 | Die Momente: Aktwechsel und Belohnung | nein |
| 10 | Probenansicht und Leitfaden — und der Druck bleibt hell | nein |
| 11 | Englische Mikrotexte (A1) und `pruefe_profil dortmund-2026` | nein |
| 12 | Browserlauf und Abnahme-Screenshots aus der Demo-Datenbank | nein |
| 13 | `BERICHT.md`, `AGENTS.md`, Abschluss | nein |

**Keine Aufgabe kostet Geld.** Kein Infomaniak-Aufruf, kein Proxy, kein Whisper. Wer in
dieser Karte einen bezahlten Aufruf braucht, hat sich verlaufen.

---

## Aufgabe 1: Vorbedingung A1/A2/W/S, Baseline, Entwurfswahl

**Dateien:**
- Neu: `tests/test_ux_vorbedingung.py`

**Schnittstellen — Produziert:** nichts fuer spaetere Aufgaben ausser der Gewissheit, dass
es sie gibt.

- [ ] **Schritt 1: Den Vorbedingungstest schreiben**

`tests/test_ux_vorbedingung.py`:

```python
"""Worauf die UX-Karte steht: A1, A2, W und S muessen in ``main`` sein.

Diese Karte gestaltet, was andere Karten bauen. Faellt hier etwas aus,
BRICHT die Umsetzung ab und meldet genau das -- A2 oder W nachzubauen
waere teurer als ein Wartetag, und zwei Fassungen von ``web_vereint.py``
waeren der teuerste Fehler dieser Kette.

Der Test ist absichtlich stumpf: er prueft Namen, nicht Verhalten. Das
Verhalten pruefen die Tests der jeweiligen Karte.
"""

import pytest

from interview_theater import sprache, web, web_chat, web_vereint


@pytest.mark.parametrize("name", ["Texte", "code", "text"])
def test_a1_sprache_ist_da(name):
    assert hasattr(sprache, name), f"A1 fehlt: sprache.{name}"


@pytest.mark.parametrize("name", [
    "CSP_VORLAGE", "mit_nonce", "csp_nonce",          # Karte S
    "_seite", "textbuch_html", "leitfaden_html",      # heute schon da
    "_CSS_TEXTBUCH", "_TEXTBUCH_JS",
])
def test_web_flaeche_ist_da(name):
    assert hasattr(web, name), f"fehlt: web.{name}"


@pytest.mark.parametrize("name", ["_CSS_CHAT", "CHAT_PFAD"])
def test_a2_chatansicht_ist_da(name):
    assert hasattr(web_chat, name), f"A2 fehlt: web_chat.{name}"


@pytest.mark.parametrize("name", [
    "seite", "scope_css", "TABS", "_CSS_VEREINT",
    "_tabs_html", "_leiste_html", "_VEREINT_JS", "_STROM_JS",
])
def test_w_vereinte_seite_ist_da(name):
    assert hasattr(web_vereint, name), f"W fehlt: web_vereint.{name}"


def test_die_csp_hat_kein_font_src():
    """Der Grund, warum diese Karte keinen Webfont einbettet: die
    Richtlinie hat ``default-src 'none'`` und kein ``font-src``. Ein
    ``@font-face`` -- auch mit ``data:``-URL -- waere geblockt."""
    assert "default-src 'none'" in web.CSP_VORLAGE
    assert "font-src" not in web.CSP_VORLAGE


def test_die_csp_erlaubt_kein_unsafe_inline():
    """Deshalb kein ``style="…"``-Attribut und kein ``on…=``-Handler --
    und deshalb CSSOM fuer dynamische Werte."""
    assert "'unsafe-inline'" not in web.CSP_VORLAGE
    assert "'nonce-{nonce}'" in web.CSP_VORLAGE
```

- [ ] **Schritt 2: Lauf**

```
$PY -m pytest tests/test_ux_vorbedingung.py -q -p no:cacheprovider
```
Erwartet: alle passed.

**Schlaegt auch nur einer fehl: HIER ABBRECHEN.** Der Bericht an Birk lautet dann woertlich
„Karte t_f09c20e3 abgebrochen: <Name> fehlt, also ist <A1|A2|W|S> nicht in main." Nichts
nachbauen, nichts umgehen.

- [ ] **Schritt 3: Die Baseline dieses Branches messen**

```
$PY -m pytest -q -p no:cacheprovider
```

Die Zahl (`N passed, 1 skipped`) hier notieren — sie ist die Messlatte fuer **alle**
folgenden Aufgaben und fuer Aufgabe 13:

```
Baseline Umsetzungs-Branch: ______ passed, 1 skipped
```

- [ ] **Schritt 4: Die Annahmen 1–5 durchlaufen**

Die Kommandos aus dem Abschnitt „Annahmen" nacheinander ausfuehren. Jede Abweichung wird
**notiert** (sie geht in den BERICHT), nicht stillschweigend repariert.

- [ ] **Schritt 5: Den Entwurf bestimmen**

```
grep -n "Entscheidung Birk" docs/ux-padua/ENTWUERFE.md
```

* Steht dort `A` → `VORGABE_ENTWURF = "a"` in Aufgabe 2.
* Steht dort `B` → `VORGABE_ENTWURF = "b"` in Aufgabe 2.
* Steht dort `offen` **und** die Kommentare der Karte sagen nichts anderes → `"a"`
  (Empfehlung), **und** die erste Zeile von `BERICHT.md` (Aufgabe 13) lautet:
  „Birk hat nicht entschieden — umgesetzt ist die Empfehlung, Entwurf A (Terminal zuerst).
  Umschalten auf B: `web_gestalt.VORGABE_ENTWURF = \"b\"` oder `IT_UX_ENTWURF=b`."

- [ ] **Schritt 6: Commit**

```bash
git add tests/test_ux_vorbedingung.py
git commit -m "UX: Vorbedingung A1/A2/W/S festhalten, bevor gestaltet wird

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 2: `web_gestalt.py` — Design-Tokens und die gerechnete Kontrasttabelle

**Dateien:**
- Neu: `interview_theater/web_gestalt.py`
- Neu: `tests/test_web_gestalt_tokens.py`

**Schnittstellen — Produziert:**

```python
# interview_theater/web_gestalt.py
ENTWUERFE: tuple[str, ...]            # ("a", "b")
VORGABE_ENTWURF: str                  # "a" (bzw. "b", siehe Aufgabe 1 Schritt 5)
UMGEBUNG: str                         # "IT_UX_ENTWURF"
TOKENS: dict[str, dict[str, str]]     # Entwurf -> Tokenname -> Wert
KONTRAST: tuple[Paar, ...]            # Paar(vorn, hinten, zweck, mindest)

class Paar(NamedTuple):
    vorn: str; hinten: str; zweck: str; mindest: float

def entwurf() -> str
def tokens_css(name: str | None = None) -> str
def kontrastverhaeltnis(vorderfarbe: str, hintergrund: str) -> float
```

**Warum die Tokens ein eigener Block sind.** Die ganze Umschaltbarkeit zwischen Entwurf A
und B haengt daran: ein Satz Custom Properties, dieselben Namen, andere Werte. Alles, was
danach kommt (Komponenten-CSS, Effekt-JS), liest nur die Namen. Deshalb steht in
`TOKENS["a"]` und `TOKENS["b"]` **dieselbe Schluesselmenge** — ein Test haelt das fest.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_gestalt_tokens.py`:

```python
"""Die Design-Tokens: vollstaendig, umschaltbar, und der Kontrast gerechnet.

Der Kontrasttest ist der Kern dieser Datei. Er liest die Tabelle
``web_gestalt.KONTRAST`` und rechnet fuer jedes deklarierte Paar das
WCAG-Verhaeltnis aus den Tokenwerten -- fuer BEIDE Entwuerfe. Eine Farbe,
die jemand spaeter "nur ein bisschen" abdunkelt, faellt hier auf und nicht
erst an einem Telefon im Sonnenlicht eines Probenraums in Padua.
"""

import re

import pytest

from interview_theater import web_gestalt

FARBE = re.compile(r"^#[0-9a-f]{6}$")


# -- Vollstaendigkeit --------------------------------------------------------


def test_es_gibt_genau_zwei_entwuerfe():
    assert web_gestalt.ENTWUERFE == ("a", "b")
    assert set(web_gestalt.TOKENS) == set(web_gestalt.ENTWUERFE)


def test_beide_entwuerfe_tragen_dieselben_tokennamen():
    """Sonst waere der Tausch kein Tausch: eine Regel des
    Komponenten-CSS liefe beim anderen Entwurf ins Leere."""
    a, b = web_gestalt.TOKENS["a"], web_gestalt.TOKENS["b"]
    assert set(a) == set(b), set(a) ^ set(b)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jeder_entwurf_hat_die_pflichttokens(name):
    tokens = web_gestalt.TOKENS[name]
    for pflicht in ("grund", "grund-2", "grund-3", "linie", "rand",
                    "text", "text-leise", "signal", "signal-tief", "auf-signal",
                    "warn", "auf-warn", "rec", "auf-rec",
                    "radius", "radius-gross", "tippflaeche", "rec-hoehe",
                    "tabs-hoehe", "schrift-lesen", "schrift-tech",
                    "schrift-skript", "takt-schnell", "takt-moment"):
        assert pflicht in tokens, f"{name}: {pflicht} fehlt"


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_farbtokens_sind_sechsstellige_hexwerte(name):
    """Kein ``rgba()``, kein Farbname: der Kontrasttest rechnet damit."""
    for schluessel, wert in web_gestalt.TOKENS[name].items():
        if schluessel in web_gestalt.FARBTOKENS:
            assert FARBE.match(wert), f"{name}.{schluessel} = {wert!r}"


# -- Kontrast ----------------------------------------------------------------


def test_die_rechnung_stimmt_an_zwei_bekannten_werten():
    """Schwarz auf Weiss ist 21, Weiss auf Weiss ist 1 -- wenn das nicht
    herauskommt, misst der Test unten gar nichts."""
    assert round(web_gestalt.kontrastverhaeltnis("#000000", "#ffffff"), 2) == 21.0
    assert round(web_gestalt.kontrastverhaeltnis("#ffffff", "#ffffff"), 2) == 1.0


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jedes_deklarierte_paar_haelt_seine_wcag_schwelle(name):
    tokens = web_gestalt.TOKENS[name]
    schwach = []
    for paar in web_gestalt.KONTRAST:
        wert = web_gestalt.kontrastverhaeltnis(tokens[paar.vorn], tokens[paar.hinten])
        if wert < paar.mindest:
            schwach.append(
                f"{name}: {paar.vorn} auf {paar.hinten} ({paar.zweck}) "
                f"= {wert:.2f}, soll >= {paar.mindest}"
            )
    assert not schwach, "\n".join(schwach)


def test_die_tabelle_deckt_die_tragenden_paare_ab():
    """Eine Tabelle, die man leer machen kann, prueft nichts. Diese Zeile
    haelt fest, WELCHE Paare drinstehen muessen."""
    paare = {(p.vorn, p.hinten) for p in web_gestalt.KONTRAST}
    for pflicht in (("text", "grund"), ("text", "grund-2"),
                    ("text-leise", "grund"), ("signal", "grund"),
                    ("auf-signal", "signal"), ("warn", "grund"),
                    ("auf-rec", "rec"), ("rec", "grund"), ("rand", "grund")):
        assert pflicht in paare, pflicht


def test_linie_steht_bewusst_nicht_in_der_tabelle():
    """``--linie`` ist eine dekorative Trennlinie zwischen Listenzeilen --
    WCAG 1.4.11 gilt fuer BEDEUTUNGSTRAGENDE Komponentengrenzen. Wo ein
    Rand einen Zustand traegt (Knopfrahmen), steht ``--rand``, und der ist
    in der Tabelle. Diese Zeile haelt die Entscheidung fest, damit sie
    niemand als Luecke liest."""
    paare = {p.vorn for p in web_gestalt.KONTRAST}
    assert "linie" not in paare
    assert "rand" in paare


# -- Die Umschaltung ---------------------------------------------------------


def test_ohne_umgebung_gilt_die_vorgabe(monkeypatch):
    monkeypatch.delenv(web_gestalt.UMGEBUNG, raising=False)
    assert web_gestalt.entwurf() == web_gestalt.VORGABE_ENTWURF


def test_die_umgebung_schaltet_um(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "b")
    assert web_gestalt.entwurf() == "b"


@pytest.mark.parametrize("wert", ["", "c", "A B", "0"])
def test_ein_unbekannter_wert_faellt_auf_die_vorgabe_zurueck(monkeypatch, wert):
    """Ein Tippfehler in einer Env-Datei soll am Workshoptag keine
    ungestylte Seite ergeben."""
    monkeypatch.setenv(web_gestalt.UMGEBUNG, wert)
    assert web_gestalt.entwurf() == web_gestalt.VORGABE_ENTWURF


def test_grossschreibung_ist_egal(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "B")
    assert web_gestalt.entwurf() == "b"


# -- Der ausgegebene Block ---------------------------------------------------


def test_tokens_css_ist_ein_root_block():
    css = web_gestalt.tokens_css("a")
    assert css.strip().startswith(":root {")
    assert css.strip().endswith("}")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jedes_token_steht_als_custom_property_drin(name):
    css = web_gestalt.tokens_css(name)
    for schluessel, wert in web_gestalt.TOKENS[name].items():
        assert f"--{schluessel}: {wert};" in css, schluessel


def test_tokens_css_ohne_argument_nimmt_den_aktiven_entwurf(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "b")
    assert web_gestalt.TOKENS["b"]["grund"] in web_gestalt.tokens_css()
    assert web_gestalt.TOKENS["a"]["grund"] not in web_gestalt.tokens_css()
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_tokens.py -q -p no:cacheprovider
```
Erwartet: FAIL — `ModuleNotFoundError: No module named 'interview_theater.web_gestalt'`.

- [ ] **Schritt 3: Das Modul anlegen**

`interview_theater/web_gestalt.py`:

```python
"""Die Gestaltung der Weboberflaeche: Tokens, Komponenten-CSS, Effekt-JS
(01.10.2026, Karte Padua UX).

**Warum ein eigenes Modul.** ``web.py``, ``web_chat.py`` (A2) und
``web_vereint.py`` (W) sind Hotspots -- an allen dreien arbeiten parallel
andere Karten. Gestaltung ist die einzige Schicht, die man vollstaendig
herausloesen kann: sie liest kein SQL, ruft kein Modell, kennt keinen
Endpunkt und aendert kein Markup. Eingehaengt wird sie an fuenf Zeilen
(vier in ``web_vereint.seite``, je eine in ``web.textbuch_html`` und
``web.leitfaden_html``).

**Birks Richtung, woertlich:** "bisschen matrix style cool, unterhaltend,
technoisch, theater". Uebersetzt in vier Leitplanken -- Terminal (dunkler
Grund, Monospace, Phosphor als Signal, Text, der sich aufbaut), Theater
(sieben Akte statt sieben Phasen, Vorhang/Glitch am Wechsel, das Textbuch
als Manuskript gesetzt), unterhaltend (kleine Belohnungen, Humor in den
englischen Mikrotexten -- nie im Bot-Text), technoid (jeder Zustand
sichtbar: Pegel, Uhr, Cursor, Warteschlange). Die Begruendung je
Entscheidung steht in ``docs/ux-padua/BERICHT.md``.

**Zwei Entwuerfe, ein Satz Tokennamen.** ``docs/ux-padua/entwurf-a.html``
("Terminal zuerst") und ``entwurf-b.html`` ("Buehne zuerst") sind die
klickbaren Muster, an denen Birk entschieden hat. Umgesetzt ist der
gewaehlte; der andere ist ein Tausch von ``VORGABE_ENTWURF`` (oder
``IT_UX_ENTWURF``) -- alle Regeln unten lesen nur Tokennamen, und die vier
Komponenten-Abweichungen (Tab-Ort, Knopfform, Akt-Moment, Skript-Satz)
haengen an derselben Wahl.

**Drei harte Grenzen, die im Code stehen und nicht im Kommentar:**

1. **Kein Webfont.** Die CSP aus Karte S hat ``default-src 'none'`` und
   kein ``font-src``; ein ``@font-face`` waere geblockt, auch mit
   ``data:``-URL. Also System-Stacks (``--schrift-*``).
2. **Kein ``style="…"``-Attribut, kein ``on…=``-Handler.** Dynamische
   Werte gehen ueber CSSOM (``el.style.setProperty``), was unter
   ``style-src 'nonce-…'`` erlaubt ist -- ``setAttribute('style', …)``
   waere es nicht.
3. **``@keyframes`` und ``@media`` NUR in ``css_rahmen()``.** Die anderen
   drei CSS-Funktionen laufen beim Aufrufer durch
   ``web_vereint.scope_css``, und dessen Regex machte aus dem Rumpf eines
   ``@keyframes`` (``50% { … }``) eine gescopte Regel ``.panel-chat 50%``.

Oberflaechen-Schicht. Importiert **nichts** aus dem Projekt ausser
``sprache`` (A1) -- nicht ``web``, nicht ``web_vereint``, nicht
``web_chat``: die Richtung zeigt von dort hierher.
"""

import os
import re
from typing import NamedTuple

from interview_theater import sprache

#: Die zwei Entwuerfe aus ``docs/ux-padua/``.
ENTWUERFE = ("a", "b")

#: Welcher gilt, solange die Umgebung nichts anderes sagt. Gesetzt in
#: Aufgabe 1 Schritt 5 aus ``docs/ux-padua/ENTWUERFE.md``.
VORGABE_ENTWURF = "a"

#: Die Umgebungsvariable, die umschaltet. Gelesen wird sie hier und nicht
#: in ``einstellungen.py``: das ist die Konfiguration des BOTS, und diese
#: Karte gehoert zum Webdienst, der seine Werte (``IT_DB``,
#: ``IT_WEB_BIND``) ebenfalls direkt aus ``os.environ`` liest.
UMGEBUNG = "IT_UX_ENTWURF"

#: Welche Tokens Farben sind -- der Kontrasttest rechnet nur mit diesen.
FARBTOKENS = frozenset({
    "grund", "grund-2", "grund-3", "linie", "rand",
    "text", "text-leise", "signal", "signal-tief", "auf-signal",
    "warn", "auf-warn", "rec", "auf-rec",
})

#: System-Schriftstacks. Kein Webfont (siehe Modulkopf).
_MONO = ('ui-monospace, "SFMono-Regular", Menlo, Consolas, '
         '"Liberation Mono", monospace')
_SERIF = 'ui-serif, Georgia, "Times New Roman", "Liberation Serif", serif'
_SANS = '-apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif'

#: DER Block, der einen Entwurf ausmacht. Gleiche Schluessel, andere Werte.
#:
#: Die Farbwerte sind nicht gegriffen: jedes Paar in ``KONTRAST`` unten ist
#: gerechnet, und ``tests/test_web_gestalt_tokens.py`` rechnet es bei jedem
#: Lauf nach. Zwei Werte weichen bewusst von den HTML-Entwuerfen ab, weil
#: die dort gewaehlten die 3:1-Grenze fuer Komponentenraender rissen:
#: ``rand`` gibt es in den Entwuerfen gar nicht (dort traegt ``linie``
#: beides), und ``b.rec`` ist von ``#8e1c22`` (2.12 : 1 auf dem Grund) auf
#: ``#c0362c`` (3.45 : 1) angehoben.
TOKENS: dict[str, dict[str, str]] = {
    # -- A: Terminal zuerst -- Phosphor auf Schwarzblau, Monospace als
    #    Grundschrift, Tableiste unten am Daumen, breite Aufnahmetaste.
    "a": {
        "grund": "#05070a",
        "grund-2": "#0c1116",
        "grund-3": "#131b22",
        "linie": "#23303a",
        "rand": "#54697a",
        "text": "#cfe3d6",
        "text-leise": "#8fa398",
        "signal": "#6ef7a5",
        "signal-tief": "#1b3a2a",
        "auf-signal": "#05070a",
        "warn": "#ffc857",
        "auf-warn": "#05070a",
        "rec": "#b3251f",
        "auf-rec": "#ffffff",
        "radius": ".35rem",
        "radius-gross": ".5rem",
        "tippflaeche": "2.75rem",
        "rec-hoehe": "4.25rem",
        "tabs-hoehe": "3.4rem",
        "schrift-lesen": _MONO,
        "schrift-tech": _MONO,
        "schrift-skript": _SERIF,
        "takt-schnell": "90ms",
        "takt-moment": "520ms",
    },
    # -- B: Buehne zuerst -- Amber auf Samtschwarz, Serife fuer alles
    #    Gelesene, Aktleiste und Tabs oben, runder Scheinwerferknopf.
    "b": {
        "grund": "#120f10",
        "grund-2": "#1c1719",
        "grund-3": "#262022",
        "linie": "#3a3134",
        "rand": "#75656a",
        "text": "#f0e6d8",
        "text-leise": "#a79c90",
        "signal": "#f0b24a",
        "signal-tief": "#3a2a13",
        "auf-signal": "#120f10",
        "warn": "#7fd6a0",
        "auf-warn": "#120f10",
        "rec": "#c0362c",
        "auf-rec": "#ffffff",
        "radius": ".7rem",
        "radius-gross": "1.1rem",
        "tippflaeche": "2.75rem",
        "rec-hoehe": "4.75rem",
        "tabs-hoehe": "0rem",
        "schrift-lesen": _SANS,
        "schrift-tech": _MONO,
        "schrift-skript": _SERIF,
        "takt-schnell": "90ms",
        "takt-moment": "560ms",
    },
}


class Paar(NamedTuple):
    """Ein Text/Grund-Paar mit seiner WCAG-Schwelle.

    ``mindest`` ist 4.5 fuer Fliesstext (AA) und 3.0 fuer grosse Schrift
    und fuer Grenzen von Bedienelementen (WCAG 1.4.11)."""

    vorn: str
    hinten: str
    zweck: str
    mindest: float


#: Jedes Paar, das die Gestaltung wirklich uebereinanderlegt. Wer eine
#: Farbkombination hinzufuegt, traegt sie HIER ein -- sonst prueft sie
#: niemand.
#:
#: ``--linie`` steht bewusst nicht darin: das ist die Haarlinie zwischen
#: zwei Listenzeilen, nicht die Grenze eines Bedienelements. Wo ein Rand
#: einen Zustand traegt, steht ``--rand``.
KONTRAST: tuple[Paar, ...] = (
    Paar("text", "grund", "Fliesstext auf dem Seitengrund", 4.5),
    Paar("text", "grund-2", "Fliesstext in Blase, Karte, Eingabefeld", 4.5),
    Paar("text", "grund-3", "Fliesstext auf gehobener Flaeche", 4.5),
    Paar("text", "signal-tief", "Text in der Blase der Gruppe", 4.5),
    Paar("text-leise", "grund", "Nebentext, Zeitangaben, Hinweise", 4.5),
    Paar("text-leise", "grund-2", "Nebentext in der Blase", 4.5),
    Paar("signal", "grund", "Signalfarbe als Text und Rahmen", 4.5),
    Paar("signal", "grund-2", "Signalfarbe in der Blase", 4.5),
    Paar("auf-signal", "signal", "Text auf gefuellter Signalflaeche", 4.5),
    Paar("warn", "grund", "laufender Zustand (Uhr, aktiver Akt)", 4.5),
    Paar("warn", "grund-2", "laufender Zustand in der Karte", 4.5),
    Paar("auf-warn", "warn", "Text auf gefuellter Warnflaeche", 4.5),
    Paar("auf-rec", "rec", "Text auf dem laufenden Aufnahmeknopf", 4.5),
    Paar("rec", "grund", "Rahmen des ruhenden Aufnahmeknopfes", 3.0),
    Paar("rand", "grund", "Grenze eines Bedienelements", 3.0),
    Paar("rand", "grund-2", "Grenze eines Bedienelements in der Karte", 3.0),
    Paar("signal", "grund-3", "gewaehlter Tab, gedrueckter Filter", 3.0),
)


def entwurf() -> str:
    """Der aktive Entwurf: ``IT_UX_ENTWURF``, sonst ``VORGABE_ENTWURF``.

    Ein unbekannter Wert faellt auf die Vorgabe zurueck statt zu werfen:
    ein Tippfehler in einer Env-Datei soll am Workshoptag keine ungestylte
    Seite ergeben."""
    wert = (os.environ.get(UMGEBUNG) or "").strip().lower()
    return wert if wert in ENTWUERFE else VORGABE_ENTWURF


def tokens_css(name: str | None = None) -> str:
    """Der Tokenblock als ``:root``-Regel."""
    tokens = TOKENS[name or entwurf()]
    zeilen = "\n".join(f"  --{k}: {v};" for k, v in tokens.items())
    return ":root {\n" + zeilen + "\n}\n"


def _kanal(wert: float) -> float:
    """Ein sRGB-Kanal (0..1) linearisiert, WCAG 2.x."""
    return wert / 12.92 if wert <= 0.04045 else ((wert + 0.055) / 1.055) ** 2.4


def _leuchtdichte(farbe: str) -> float:
    roh = farbe.lstrip("#")
    r, g, b = (int(roh[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _kanal(r) + 0.7152 * _kanal(g) + 0.0722 * _kanal(b)


def kontrastverhaeltnis(vorderfarbe: str, hintergrund: str) -> float:
    """Das WCAG-Kontrastverhaeltnis zweier Hexfarben, 1.0 bis 21.0.

    Ausgerechnet und nicht geschaetzt: die Oberflaeche liegt auf einem
    Telefon in einem Probenraum, und "sieht dunkel genug aus" ist kein
    Mass."""
    eins, zwei = _leuchtdichte(vorderfarbe), _leuchtdichte(hintergrund)
    hell, dunkel = max(eins, zwei), min(eins, zwei)
    return (hell + 0.05) / (dunkel + 0.05)


T = sprache.Texte(__name__)
```

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_tokens.py -q -p no:cacheprovider
```
Erwartet: alle passed (Kontrast beider Entwuerfe gerechnet: A ab 3.07, B ab 3.23).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1. **Achtung:** `tests/test_sprache_texte.py` kann hier
bereits meckern, weil `web_gestalt` ein `T` hat, aber noch nicht in `UMGESTELLT` steht.
Ist das so, wird **in dieser Aufgabe** nur der Mengeneintrag ergaenzt
(`UMGESTELLT`/`ALLE_MODULE` bekommen `"web_gestalt"`); die Texte selbst kommen in
Aufgabe 11.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_tokens.py \
        tests/test_sprache_texte.py
git commit -m "UX: Design-Tokens fuer beide Entwuerfe, Kontrast gerechnet statt geschaetzt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 3: Das Grund-CSS — `css_rahmen`, reduced-motion, keine Fremdquelle

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py`
- Neu: `tests/test_web_gestalt_css.py`

**Schnittstellen — Produziert:**

```python
def css_rahmen(name: str | None = None) -> str    # ungescopt: Tokens, Keyframes, @media
def css_chat(name: str | None = None) -> str      # wird vom Aufrufer gescopt
def css_stand(name: str | None = None) -> str     # dito
def css_textbuch(name: str | None = None) -> str  # dito (und ungescopt auf der Probenseite)
BEWEGT: tuple[str, ...]        # jeder Selektor, den der reduced-motion-Block stilllegt
KEYFRAMES: tuple[str, ...]     # die Namen der eigenen @keyframes
```

**Die Arbeitsteilung, und warum sie so ist.**

* `css_rahmen()` traegt alles, was **ausserhalb** der drei Panels liegt oder global gilt:
  den Tokenblock, die `@keyframes`, den `@media (prefers-reduced-motion)`-Block, den
  `@media print`-Block, den Seitenrahmen (`body`), Tabs, Roadmap, Akt-Moment und Belohnung.
  W erzeugt Tabs und Roadmap **vor** den Panels, also sind sie ungescopt richtig.
* `css_chat/stand/textbuch()` tragen, was **in** einem Panel liegt. Der Aufrufer schickt
  sie durch `web_vereint.scope_css` — genau wie A2/W ihr eigenes CSS. Nur so gewinnt
  `#interview` gegen das schon gescopte `.panel-chat #interview` aus `_CSS_CHAT` (gleiche
  Spezifitaet, spaetere Position).
* **In den drei gescopten Funktionen steht kein `@keyframes` und kein `@media`**
  (ANNAHME 3). `animation: name …` darf dort stehen — nur die Definition nicht.

**Der reduced-motion-Block ist die einzige Stelle mit `!important`**, und mit Grund: er
muss auch die Animationen von A2/W stilllegen (`.blase.vorlaeufig::after`, der Cursor in
`#tippt`), und die sind **gescopt** und damit spezifischer als jede ungescopte Regel hier.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_gestalt_css.py`:

```python
"""Das CSS der Gestaltung: was drinstehen muss und was nie drinstehen darf.

Drei Vertraege, alle am Text der Konstanten gemessen und ohne Browser:

1. Keine Fremdquelle, kein Webfont -- die CSP aus Karte S hat
   ``default-src 'none'`` und kein ``font-src``.
2. ``prefers-reduced-motion: reduce`` legt JEDE Animation und JEDEN
   Uebergang des Moduls still, und zwar die, die es wirklich gibt: der
   Test sammelt die Selektoren aus dem CSS selbst, statt einer Liste zu
   glauben.
3. ``@keyframes`` und ``@media`` stehen nur im ungescopten Teil --
   ``web_vereint.scope_css`` machte aus dem Rumpf eines ``@keyframes``
   sonst eine gescopte Regel (``.panel-chat 50% { … }``).
"""

import re

import pytest

from interview_theater import web_gestalt, web_vereint

GESCOPT = ("css_chat", "css_stand", "css_textbuch")
ALLE = ("css_rahmen",) + GESCOPT


def _css(funktion: str, name: str) -> str:
    return getattr(web_gestalt, funktion)(name)


def _ganzes_css(name: str) -> str:
    return "".join(_css(f, name) for f in ALLE)


# -- 1. Keine Fremdquelle ----------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("verboten", ["http://", "https://", "@font-face", "@import"])
def test_kein_fremdes_in_der_gestaltung(name, verboten):
    assert verboten not in _ganzes_css(name), verboten


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_keine_url_ueberhaupt(name):
    """Heute braucht die Gestaltung kein einziges ``url()``: Verlaeufe und
    Zeichen kommen aus CSS und aus Unicode. Auch ``//example.org/x.css``
    waere eine Fremdquelle und sieht im Diff aus wie ein Kommentar. Wer
    ein ``url()`` einfuehrt, faellt hier auf und traegt die CSP-Folge
    (``img-src 'self' data:``) im Commit nach."""
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", _ganzes_css(name), flags=re.S)
    assert "url(" not in ohne_kommentare


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_schriften_sind_systemstacks(name):
    for schluessel in ("schrift-lesen", "schrift-tech", "schrift-skript"):
        wert = web_gestalt.TOKENS[name][schluessel]
        assert wert.rstrip().endswith(("monospace", "serif", "sans-serif")), wert


# -- 2. prefers-reduced-motion ----------------------------------------------


def _bewegte_selektoren(css: str) -> set[str]:
    """Jeder Selektor, der ``animation``/``transition`` erklaert -- ohne
    den reduced-motion-Block selbst und ohne die Keyframe-Rumpfe."""
    ohne_ruhig = re.sub(
        r"@media\s*\(prefers-reduced-motion[^{]*\{.*?\n\}", "", css, flags=re.S)
    ohne_keyframes = re.sub(r"@keyframes[^{]*\{.*?\n\}", "", ohne_ruhig, flags=re.S)
    treffer = set()
    for selektoren, koerper in re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_keyframes):
        if not re.search(r"\b(animation|transition)\b\s*:", koerper):
            continue
        for einer in selektoren.split(","):
            if einer.strip() and not einer.strip().startswith("@"):
                treffer.add(einer.strip())
    return treffer


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_es_gibt_ueberhaupt_bewegung_zum_abschalten(name):
    """Ein Test, der eine leere Menge prueft, prueft nichts."""
    assert _bewegte_selektoren(_ganzes_css(name))


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_reduzierte_bewegung_legt_jeden_bewegten_selektor_stumm(name):
    css = _ganzes_css(name)
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}", css, flags=re.S)
    assert block, "kein reduced-motion-Block"
    ruhig = block.group(1)
    fehlen = [s for s in _bewegte_selektoren(css) if s not in ruhig]
    assert not fehlen, fehlen


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_block_setzt_animation_und_transition_auf_none(name):
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
        _ganzes_css(name), flags=re.S).group(1)
    assert "animation: none !important" in block
    assert "transition: none !important" in block


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_block_legt_auch_die_bewegung_aus_a2_und_w_still(name):
    """``.blase.vorlaeufig::after`` (der Strom-Cursor aus Karte W) ist
    GESCOPT und damit spezifischer als alles hier -- ohne ``!important``
    und ohne ausdrueckliche Nennung blinkte er weiter."""
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
        _ganzes_css(name), flags=re.S).group(1)
    assert ".blase.vorlaeufig::after" in block


def test_bewegt_und_das_css_sagen_dasselbe():
    """``BEWEGT`` ist die Liste im Code, der Test oben liest das CSS.
    Laufen beide auseinander, ist die Liste die Luege."""
    for name in web_gestalt.ENTWUERFE:
        block = re.search(
            r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
            _ganzes_css(name), flags=re.S).group(1)
        for selektor in web_gestalt.BEWEGT:
            assert selektor in block, selektor


# -- 3. Was scope_css nicht vertraegt ---------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("funktion", GESCOPT)
def test_kein_keyframes_und_kein_media_im_gescopten_teil(name, funktion):
    assert "@keyframes" not in _css(funktion, name)
    assert "@media" not in _css(funktion, name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jede_benutzte_animation_ist_auch_definiert(name):
    css = _ganzes_css(name)
    definiert = set(re.findall(r"@keyframes\s+([\w-]+)", css))
    benutzt = {t for t in re.findall(r"animation:\s*([\w-]+)", css) if t != "none"}
    assert benutzt <= definiert, benutzt - definiert
    assert set(web_gestalt.KEYFRAMES) == definiert


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_gescopte_teil_ueberlebt_scope_css(name):
    """Der eigentliche Beweis: durch dieselbe Funktion schicken, die der
    Aufrufer benutzt, und nachsehen, dass nichts zerfaellt."""
    for funktion, scope in (("css_chat", ".panel-chat"),
                            ("css_stand", ".panel-stand"),
                            ("css_textbuch", ".panel-textbuch")):
        ergebnis = web_vereint.scope_css(_css(funktion, name), scope)
        assert ergebnis.count("{") == ergebnis.count("}")
        # Kein Rumpf-Fragment ist zu einem Selektor geworden.
        assert not re.search(r"\.panel-\w+ \d+%", ergebnis)


# -- 4. Tokens werden benutzt, nicht umgangen -------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_keine_rohe_hexfarbe_ausserhalb_des_tokenblocks(name):
    """Sonst waere der Entwurfstausch kein Tausch. Ausgenommen ist
    ``@media print``: der Ausdruck ist bewusst nicht themenfaehig, er ist
    IMMER hell."""
    css = _ganzes_css(name)
    ohne_tokens = css.replace(web_gestalt.tokens_css(name), "")
    ohne_druck = re.sub(r"@media\s+print\s*\{.*?\n\}", "", ohne_tokens, flags=re.S)
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", ohne_druck, flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", ohne_kommentare)
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_css.py -q -p no:cacheprovider
```
Erwartet: FAIL — `AttributeError: module 'interview_theater.web_gestalt' has no attribute 'css_rahmen'`.

- [ ] **Schritt 3: `css_rahmen` und die drei Geschwister schreiben**

Weiter in `web_gestalt.py`. Die drei gescopten Funktionen bekommen hier nur ihr Geruest;
sie wachsen in den Aufgaben 5, 6, 8 und 10.

```python
#: Die Namen der eigenen ``@keyframes``. Als Liste, damit ein Test sie
#: gegen das CSS haelt: eine unbenutzte Animation ist toter Code, eine
#: undefinierte ein stiller Ausfall.
KEYFRAMES = ("ux-blinken", "ux-puls", "ux-auftritt", "ux-glitch", "ux-vorhang")

#: Jeder Selektor, den der reduced-motion-Block stilllegt -- die eigenen
#: UND die aus A2/W. Die aus A2/W stehen hier, weil sie GESCOPT und damit
#: spezifischer sind als alles in diesem Modul.
BEWEGT = (
    "#ux-vorhang",
    "#ux-ansage",
    "#ux-belohnung",
    "#interview",
    "#interview::before",
    "#pegel span",
    ".tabs button",
    ".phase-knopf",
    ".blase.vorlaeufig::after",   # Karte W
    "#tippt::after",              # Karte W
)


def _ruhig_block() -> str:
    """Der eine ``@media (prefers-reduced-motion: reduce)``-Block.

    **Die einzige Stelle mit ``!important``** in diesem Modul. Grund: er
    muss auch gescopte Regeln aus A2/W schlagen
    (``.panel-chat .blase.vorlaeufig::after``), und die sind spezifischer
    als jeder ungescopte Selektor hier.

    Der Text des Stroms baut sich weiterhin stueckweise auf -- das ist
    Information, keine Animation (Karte W, Aufgabe 14). Still wird nur,
    was blinkt, pulst, gleitet oder einfliegt. **Kein Zustand haengt an
    einer Animation**: jeder steht zusaetzlich im Text."""
    selektoren = ",\n".join(BEWEGT)
    return (
        "@media (prefers-reduced-motion: reduce) {\n"
        f"{selektoren} {{\n"
        "  animation: none !important;\n"
        "  transition: none !important;\n"
        "}\n"
        "#ux-vorhang { display: none !important; }\n"
        "}\n"
    )


def _druck_block() -> str:
    """Der Ausdruck bleibt ein helles Manuskript.

    Die Probenansicht setzt seit dem 06.09.2026 ein Manuskript
    (``web._CSS_TEXTBUCH``, ``@media print``). Dieses Modul faerbt die
    Seite dunkel und steht im ``<style>`` DANACH -- ohne diesen Block
    kaeme ein schwarzes Blatt aus dem Drucker. Die Farben sind hier
    bewusst roh und nicht aus Tokens: der Ausdruck ist nicht
    themenfaehig, er ist immer hell."""
    return (
        "@media print {\n"
        "body, .panel-textbuch {\n"
        "  background: #fff !important; color: #000 !important;\n"
        '  font-family: ui-serif, Georgia, "Times New Roman", serif !important;\n'
        "}\n"
        "#ux-vorhang, #ux-ansage, #ux-belohnung, .tabs, .roadmap, .fuss,\n"
        "#ux-rec-zeile { display: none !important; }\n"
        ".sprecher { color: #000 !important; font-weight: 700; }\n"
        ".regie, .regie-zeile, .angaben, .besetzung {\n"
        "  color: #333 !important; opacity: 1 !important;\n"
        "}\n"
        "}\n"
    )


def css_rahmen(name: str | None = None) -> str:
    """Alles Ungescopte: Tokens, Seitenrahmen, Tabs, Roadmap, die beiden
    Momente, die Keyframes, reduced-motion und der Druck.

    Wird auf der vereinten Seite **und** auf der Probenansicht
    ausgeliefert. Enthaelt deshalb nichts, was nur in einem Panel Sinn
    ergibt."""
    gewaehlt = name or entwurf()
    return "".join((
        tokens_css(gewaehlt),
        _BASIS,
        _TABS_A if gewaehlt == "a" else _TABS_B,
        _ROADMAP,
        _MOMENTE_A if gewaehlt == "a" else _MOMENTE_B,
        _BELOHNUNG,
        _KEYFRAMES_CSS,
        _ruhig_block(),
        _druck_block(),
    ))


def css_chat(name: str | None = None) -> str:
    """Was IM Chat-Panel liegt. Der Aufrufer scopt das auf
    ``.panel-chat`` -- deshalb hier kein ``@keyframes``, kein ``@media``
    und kein ``body``."""
    return _CHAT_A if (name or entwurf()) == "a" else _CHAT_B


def css_stand(name: str | None = None) -> str:
    """Was IM Arbeitsstand-Panel liegt. Fuer beide Entwuerfe gleich: es
    ist eine Leseflaeche, und die Tokens tragen den Unterschied."""
    return _STAND


def css_textbuch(name: str | None = None) -> str:
    """Was IM Textbuch-Panel liegt -- und, ungescopt, auf der
    Probenansicht ``/g/<token>/textbuch``."""
    return _SKRIPT_A if (name or entwurf()) == "a" else _SKRIPT_B


#: Der Seitenrahmen. ``body`` steht hier und nicht im gescopten Teil: es
#: gibt genau einen, und auf der Probenansicht gibt es gar kein Panel.
#:
#: Die eine ``transition`` traegt den Vertrag aus Aufgabe 3 von Anfang an;
#: der Rest des Aufnahmeknopfes kommt in Aufgabe 8.
_BASIS = """
body {
  background: var(--grund);
  color: var(--text);
  font-family: var(--schrift-lesen);
  font-size: 1rem;
  line-height: 1.5;
  max-width: 46rem;
  margin: 0 auto;
  -webkit-text-size-adjust: 100%;
}
h1 { font-size: 1.05rem; letter-spacing: .05em; color: var(--signal); }
h2 { color: var(--text-leise); border-bottom: 1px solid var(--linie); }
a { color: var(--signal); }
::selection { background: var(--signal); color: var(--auf-signal); }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
.leer { color: var(--text-leise); }
#interview { transition: background var(--takt-schnell) linear,
                         transform var(--takt-schnell) linear; }
"""

#: Keyframes -- ALLE hier, nie im gescopten Teil (siehe Modulkopf).
_KEYFRAMES_CSS = """
@keyframes ux-blinken { 50% { opacity: 0; } }
@keyframes ux-puls { 50% { opacity: .35; } }
@keyframes ux-auftritt { from { opacity: 0; transform: translateY(.6rem); } }
@keyframes ux-glitch {
  0% { opacity: 0; transform: translateY(0); }
  20% { opacity: 1; transform: translateY(-.4rem); }
  45% { opacity: .85; transform: translateY(.3rem); }
  70% { opacity: 1; transform: translateY(-.15rem); }
  100% { opacity: 0; transform: translateY(0); }
}
@keyframes ux-vorhang {
  0% { transform: translateY(-101%); }
  45% { transform: translateY(0); }
  55% { transform: translateY(0); }
  100% { transform: translateY(-101%); }
}
"""

#: Gefuellt in Aufgabe 6.
_TABS_A = ""
_TABS_B = ""
#: Gefuellt in Aufgabe 7.
_ROADMAP = ""
#: Gefuellt in Aufgabe 9.
_MOMENTE_A = ""
_MOMENTE_B = ""
_BELOHNUNG = ""
#: Gefuellt in Aufgabe 5 (Chat) und 8 (Aufnahmeknoepfe).
_CHAT_A = ""
_CHAT_B = ""
#: Gefuellt in Aufgabe 6.
_STAND = ""
#: Gefuellt in Aufgabe 10.
_SKRIPT_A = ""
_SKRIPT_B = ""
```

- [ ] **Schritt 4: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_css.py tests/test_web_gestalt_tokens.py \
  -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 5: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_css.py
git commit -m "UX: Grund-CSS, reduced-motion mit Vertrag, Druck bleibt hell

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 4: Einhaengen in `web_vereint.seite` — vier Zeilen, CSP-Vertrag am HTML

**Dateien:**
- Aendern: `interview_theater/web_vereint.py` (vier Zeilen in `seite()`)
- Aendern: `interview_theater/web_gestalt.py` (`skript()` als Geruest)
- Neu: `tests/test_web_gestalt_einhang.py`

**Schnittstellen — Produziert:**

```python
def skript(name: str | None = None) -> str    # das Effekt-JS mit gesetzten Werten
_GESTALT_JS: str                              # der Rohtext mit __PLATZHALTERN__
```

**Die vier Zeilen.** In `web_vereint.seite()` wird der `css`-Ausdruck um vier Summanden
ergaenzt und das `skript` um einen:

```python
    css = (
        _CSS_VEREINT
        + scope_css(web._CSS_GRUPPE, ".panel-stand")
        + scope_css(web._CSS_TEXTBUCH, ".panel-textbuch")
        + scope_css(web_chat._CSS_CHAT, ".panel-chat")
        # Gestaltung zuletzt (Karte UX): gleiche Spezifitaet, spaetere
        # Position -- und dieselbe Einschraenkung wie die Quellen darueber,
        # sonst waere `#interview` schwaecher als `.panel-chat #interview`.
        + web_gestalt.css_rahmen()
        + scope_css(web_gestalt.css_chat(), ".panel-chat")
        + scope_css(web_gestalt.css_stand(), ".panel-stand")
        + scope_css(web_gestalt.css_textbuch(), ".panel-textbuch")
    )
    skript = (
        _VEREINT_JS.replace("__TABS__", json.dumps(list(TABS)))
        .replace("__VORGABE__", VORGABE_TAB)
        + web._TEXTBUCH_JS + web_chat._CHAT_JS
        + web_gestalt.skript()      # Karte UX: Effekte, zuletzt
    )
```

Dazu `web_gestalt` an den bestehenden lokalen Import in `seite()` anhaengen
(`from interview_theater import web, web_chat` → `from interview_theater import web,
web_chat, web_gestalt`). **Mehr nicht.**

**Warum `skript()` zuletzt steht:** es haengt seine Zuhoerer an Elemente, die `_CHAT_JS`
und `_VEREINT_JS` schon kennen, und seine `MutationObserver` sollen Aenderungen sehen, die
jene ausloesen.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_gestalt_einhang.py`:

```python
"""Der CSP-Vertrag am AUSGELIEFERTEN HTML -- nicht an einer Konstante.

Das ist der Unterschied zu ``test_web_gestalt_css.py``: dort wird der
Quelltext des Moduls gemessen, hier die Seite, die wirklich ueber die
Leitung geht. Ein ``style="…"``-Attribut, das erst beim Zusammenbau
entsteht, faellt nur hier auf -- und in Padua waere es eine Seite ohne
Gestaltung, weil die Richtlinie aus Karte S es blockt.
"""

import inspect
import re
import threading
import urllib.request

import pytest

from interview_theater import db, repo, web, web_gestalt

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32

STIL_ATTRIBUT = re.compile(r"<[^>]*\sstyle\s*=")
EREIGNIS_ATTRIBUT = re.compile(r"<[^>]*\son[a-z]+\s*=")


@pytest.fixture
def dienst(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "We are from the theatre.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam mit einem Koffer")
    nummer = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis")
    repo.aktualisiere_szene(conn, nummer,
                            volltext="MERYEM: Ich bin da.\nERHAN: Endlich.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    server = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap",
                             schluessel=SCHLUESSEL)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", token
    server.shutdown()


def _hole(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.read().decode("utf-8")


@pytest.fixture(params=["", "/textbuch", "/leitfaden"])
def seite(request, dienst):
    basis, token = dienst
    return _hole(f"{basis}/g/{token}{request.param}")


# -- Der CSP-Vertrag ---------------------------------------------------------


def test_kein_style_attribut_im_ausgelieferten_html(seite):
    """``style-src 'nonce-…'`` ohne ``'unsafe-inline'``: ein
    ``style="…"``-Attribut waere im Browser wirkungslos."""
    assert not STIL_ATTRIBUT.search(seite)


def test_kein_ereignisattribut_im_ausgelieferten_html(seite):
    """``onclick=`` waere aus demselben Grund tot -- und ein offenes Tor,
    wenn jemals ``'unsafe-inline'`` dazukaeme."""
    assert not EREIGNIS_ATTRIBUT.search(seite)


def test_keine_fremdquelle_im_ausgelieferten_html(seite):
    for verboten in ("http://", "https://", "@font-face", "@import"):
        assert verboten not in seite, verboten


def test_das_skript_setzt_dynamische_werte_ueber_cssom(seite):
    """``el.style.setProperty`` ist unter der Richtlinie erlaubt,
    ``setAttribute('style', …)`` nicht. Der Unterschied ist eine Zeile und
    faellt sonst erst im Browser auf."""
    assert "setProperty(" in seite
    assert "setAttribute('style'" not in seite
    assert 'setAttribute("style"' not in seite


# -- Die Reihenfolge ---------------------------------------------------------


def test_die_gestaltung_steht_zuletzt_im_style(dienst):
    """Sonst gewinnt bei gleicher Spezifitaet das CSS aus A2/W."""
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    stil = re.search(r"<style[^>]*>(.*?)</style>", html, flags=re.S).group(1)
    assert stil.index("--rec-hoehe") > stil.index(".panel-chat")


def test_die_tokens_des_aktiven_entwurfs_stehen_drin(dienst):
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    tokens = web_gestalt.TOKENS[web_gestalt.entwurf()]
    assert f"--grund: {tokens['grund']};" in html
    assert f"--signal: {tokens['signal']};" in html


def test_das_chat_css_der_gestaltung_ist_gescopt(dienst):
    """Ungescopt waere ``#interview`` (0,1,0,0) schwaecher als das schon
    gescopte ``.panel-chat #interview`` (0,1,1,0) aus ``_CSS_CHAT``."""
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}")
    stil = re.search(r"<style[^>]*>(.*?)</style>", html, flags=re.S).group(1)
    nach = stil[stil.index("--rec-hoehe"):]
    assert ".panel-chat #interview" in nach


# -- Was die Gestaltung NICHT tut -------------------------------------------


def test_die_gestaltung_fasst_keine_daten_an():
    """Sie ist Gestaltung: kein SQL, kein Material, kein Zitat."""
    quelle = inspect.getsource(web_gestalt)
    for verboten in ("SELECT", "INSERT", "UPDATE", "DELETE", "sqlite3",
                     "import repo", "import web_daten", "import db"):
        assert verboten not in quelle, verboten


def test_kein_modellaufruf_in_der_gestaltung():
    quelle = inspect.getsource(web_gestalt)
    for verboten in ("import llm", "import httpx", "import stt", "anthropic"):
        assert verboten not in quelle, verboten
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_einhang.py -q -p no:cacheprovider
```
Erwartet: FAIL — `--rec-hoehe` steht nicht in der Seite, `web_gestalt.skript` fehlt.

- [ ] **Schritt 3: `skript()` als Geruest**

In `web_gestalt.py` (`import json` gehoert in den Modulkopf, nicht in die Funktion):

```python
#: Das Effekt-JavaScript. Vanilla, ES5-nah wie ``_BEARBEITEN_JS`` und
#: ``_CHAT_JS`` -- kein Build, kein Framework.
#:
#: **Es aendert kein Markup von A2/W.** Was die Gestaltung zusaetzlich
#: braucht, legt es selbst an (``#ux-rec-zeile``, ``#ux-balken``,
#: ``#ux-vorhang``, ``#ux-ansage``, ``#ux-belohnung``) -- alles mit dem
#: Praefix ``ux-``, damit im Fehlerfall klar ist, wem es gehoert.
#:
#: **Es schreibt nie in ``#interview.textContent``**: das tut ``_CHAT_JS``
#: (Karte A2, Befund 2 im Plan-Kopf), und zwei Schreiber auf einem Knoten
#: sind ein Fehler, der erst im Workshop auffaellt.
#:
#: Faellt es aus, bleibt die Seite vollstaendig bedienbar: jeder Zustand,
#: den es zeigt, hat schon eine textliche Entsprechung aus A2/W.
_GESTALT_JS = """
(function () {
  'use strict';
  var RUHIG = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var TAKT_MOMENT = __TAKT_MOMENT__;
  var MOMENT = '__MOMENT__';
  var TEXTE = __TEXTE__;
  var el = function (id) { return document.getElementById(id); };
  // Die Bausteine kommen in den Aufgaben 5 bis 9. Ohne sie tut dieses
  // Skript nichts -- und genau das soll es dann auch tun.
  __BAUSTEINE__
})();
"""


def skript(name: str | None = None) -> str:
    """Das Effekt-JS mit eingesetzten Werten.

    Platzhalter statt f-String: das Skript ist voll mit geschweiften
    Klammern. Dieselbe Bauart wie ``web_chat._js()`` (Karte A2)."""
    gewaehlt = name or entwurf()
    takt = TOKENS[gewaehlt]["takt-moment"].removesuffix("ms")
    return (
        _GESTALT_JS
        .replace("__TAKT_MOMENT__", takt)
        .replace("__MOMENT__", "glitch" if gewaehlt == "a" else "vorhang")
        .replace("__TEXTE__", json.dumps(_mikrotexte(), ensure_ascii=False))
        .replace("__BAUSTEINE__", _BAUSTEINE)
    )


#: Gefuellt in den Aufgaben 5 bis 9.
_BAUSTEINE = ""


def _mikrotexte() -> dict[str, str]:
    """Die englischen Kurztexte, die das Skript in den DOM schreibt.

    Sie gehen als JSON ins Skript, statt als Literal darin zu stehen --
    nur so laufen sie ueber ``T`` (A1) und sind uebersetzbar. Ein Literal
    im JS waere in Padua Deutsch; genau das ist Befund 2 an Karte A2.
    Gefuellt in Aufgabe 11."""
    return {}
```

- [ ] **Schritt 4: Die vier Zeilen in `web_vereint.seite`**

Genau die Ersetzung aus dem Kopf dieser Aufgabe.

```
git diff --stat interview_theater/web_vereint.py
```
Erwartet: **eine** Datei, hoechstens 7 geaenderte Zeilen.

- [ ] **Schritt 5: Lauf**

Die beiden Faelle `/textbuch` und `/leitfaden` der `seite`-Fixture bleiben rot, bis
**Aufgabe 10** dort einhaengt (`--rec-hoehe` steht dort noch nicht drin, aber die
CSP-Tests laufen schon — rot wird nur, was Gestaltung erwartet). Deshalb hier:

```
$PY -m pytest tests/test_web_gestalt_einhang.py tests/test_web_vereint.py \
  tests/test_web.py tests/test_web_textbuch.py -q -p no:cacheprovider
```
Erwartet: alle passed. Sollte ein `/textbuch`- oder `/leitfaden`-Fall scheitern, wird er
**nicht** repariert, sondern bis Aufgabe 10 als `xfail` markiert:

```python
@pytest.fixture(params=[
    "",
    pytest.param("/textbuch", marks=pytest.mark.xfail(
        reason="Gestaltung haengt dort erst in Aufgabe 10 ein", strict=False)),
    pytest.param("/leitfaden", marks=pytest.mark.xfail(
        reason="Gestaltung haengt dort erst in Aufgabe 10 ein", strict=False)),
])
def seite(request, dienst):
    ...
```
**In Aufgabe 10 fallen die beiden Marken wieder heraus** — das steht dort als Schritt.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_gestalt.py interview_theater/web_vereint.py \
        tests/test_web_gestalt_einhang.py
git commit -m "UX: Gestaltung an vier Zeilen in web_vereint.seite eingehaengt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 5: Der Chat — Blasen, Knopfleisten, Strom-Cursor, Denk-Zustand

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_CHAT_A`, `_CHAT_B`, ein Baustein im JS)
- Neu: `tests/test_web_gestalt_js.py`

**Schnittstellen — Produziert:** `_CHAT_A`, `_CHAT_B` (CSS), `_JS_DENKT` (Baustein).

**Was gestaltet wird, und was schon da ist.** A2/W liefern die Blasen
(`.blase.bot|.gruppe` × `.text|.sprache|.datei`), die Knopfleiste (`.leiste button`), die
Quittung (`.quittung`), die Tippanzeige (`#tippt`) und die vorlaeufige Strom-Blase
(`.blase.vorlaeufig` mit `::after`-Cursor). Diese Aufgabe **faerbt und setzt** das — und
ergaenzt genau eine Sache, die im Erlebnis fehlt: der Denk-Zustand ist heute die Zeile
„schreibt …"; gestaltet wird daraus eine **Terminal-Zeile mit Cursor**, damit sichtbar ist,
dass die Maschine arbeitet und nicht haengt.

**Abweichung B:** `.blase.bot::before` (die Zeile `bot ~ $` ueber jeder Bot-Blase) gibt es
**nur in A**. In B traegt die Blase keine Kennzeichnung — dort unterscheiden sich Bot und
Gruppe durch Ausrichtung und Flaeche, wie in einem Buehnentext Repliken.

- [ ] **Schritt 1: Den Test schreiben**

`tests/test_web_gestalt_js.py` (er waechst in den Aufgaben 6–9 weiter):

```python
"""Der Vertrag des Effekt-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_gestalt_e2e.py``:
ob die Zustaende im echten Chromium wirklich umschalten. Hier steht, was
man am ausgelieferten Skript messen kann -- und das ist genug fuer die
Entscheidungen, die leicht verloren gehen.
"""

import re

import pytest

from interview_theater import web_gestalt


@pytest.fixture(params=web_gestalt.ENTWUERFE)
def js(request):
    return web_gestalt.skript(request.param)


# -- Der CSP-Vertrag im Skript ----------------------------------------------


def test_keine_platzhalter_bleiben_stehen(js):
    """Ein uebersehener ``__NAME__`` waere im Browser ein Syntaxfehler --
    und die ganze Gestaltung waere weg."""
    assert not re.search(r"__[A-Z_]+__", js)


def test_das_skript_setzt_werte_ueber_cssom(js):
    assert "setProperty(" in js
    assert "setAttribute('style'" not in js


def test_das_skript_haengt_keine_handler_ins_markup(js):
    """Alles ueber ``addEventListener``; ein ``el.onclick =`` waere zwar
    CSP-konform, aber wuerde einen fremden Handler ueberschreiben."""
    assert "addEventListener(" in js
    assert not re.search(r"\.on(click|input|change)\s*=", js)


def test_das_skript_schreibt_nie_in_den_interview_knopf(js):
    """Befund 2 an Karte A2: ``_CHAT_JS`` setzt dort ``textContent``.
    Zwei Schreiber auf einem Knoten sind ein Fehler, der erst im Workshop
    auffaellt -- die Gestaltung legt ihren Text daneben
    (``#ux-rec-zeile``)."""
    assert "ux-rec-zeile" in js
    for verboten in ("interview').textContent", 'interview").textContent',
                     "interviewKnopf.textContent"):
        assert verboten not in js


def test_das_skript_achtet_auf_reduzierte_bewegung(js):
    """Nicht nur im CSS: die Momente sind zeitgesteuert, und ein Timer
    laeuft auch dann, wenn die Animation aus ist."""
    assert "prefers-reduced-motion" in js
    assert "RUHIG" in js


# -- Chat --------------------------------------------------------------------


def test_der_denk_zustand_haengt_an_der_tippanzeige(js):
    """``#tippt`` kommt aus Karte A2 und traegt schon den Text. Die
    Gestaltung macht daraus eine Terminalzeile -- sie erfindet keine
    zweite Anzeige daneben."""
    assert "'tippt'" in js or '"tippt"' in js


def test_die_gestaltung_kennt_die_vorlaeufige_blase(js):
    """Sie gehoert Karte W; gestaltet wird sie, geschrieben nicht."""
    assert "vorlaeufig" in web_gestalt.css_chat("a")
    assert "vorlaeufig" in web_gestalt.css_chat("b")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_das_chat_css_faerbt_beide_blasenarten(name):
    css = web_gestalt.css_chat(name)
    assert ".blase.bot" in css
    assert ".blase.gruppe" in css
    assert ".leiste button" in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_blasen_lesen_sich_gross_genug(name):
    """16 px ist die Untergrenze fuer Fliesstext am Telefon."""
    css = web_gestalt.css_chat(name)
    treffer = re.search(r"\.blase\s*\{[^}]*font-size:\s*([\d.]+)rem", css, flags=re.S)
    assert treffer, "die Blase setzt keine Schriftgroesse"
    assert float(treffer.group(1)) >= 1.0


def test_nur_entwurf_a_kennzeichnet_die_bot_blase():
    """Die Zeile ``bot ~ $`` ist Terminal; in B unterscheiden sich Bot und
    Gruppe wie Repliken -- durch Ausrichtung und Flaeche."""
    assert ".blase.bot::before" in web_gestalt.css_chat("a")
    assert ".blase.bot::before" not in web_gestalt.css_chat("b")
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider
```
Erwartet: FAIL — `_CHAT_A` ist leer, `ux-rec-zeile` steht nirgends.

- [ ] **Schritt 3: Das Chat-CSS**

In `web_gestalt.py` die beiden leeren Konstanten ersetzen:

```python
#: Der Chat, Entwurf A: Terminal. Monospace, Phosphor als Rahmenfarbe der
#: Bot-Blase, eine Kennzeile `bot ~ $` darueber. Die Blase der Gruppe
#: sitzt rechts auf einer tiefen Signalflaeche.
_CHAT_A = """
.verlauf { display: flex; flex-direction: column; gap: .5rem; }
.blase { padding: .5rem .65rem; max-width: 92%; font-size: 1rem;
         border-radius: var(--radius-gross); overflow-wrap: anywhere; }
.blase.bot { background: var(--grund-2); border: 1px solid var(--linie);
             border-left: 2px solid var(--signal); align-self: flex-start; }
.blase.bot::before { content: "bot ~ $"; display: block; font-size: .72rem;
                     letter-spacing: .1em; color: var(--text-leise);
                     font-family: var(--schrift-tech); }
.blase.gruppe { background: var(--signal-tief); border: 1px solid var(--rand);
                align-self: flex-end; }
.blase.sprache { color: var(--text-leise); font-style: italic; }
.blase q { display: block; margin: .5rem 0; padding-left: .7rem;
           border-left: 2px solid var(--warn); color: var(--warn);
           font-family: var(--schrift-skript); font-style: italic;
           quotes: none; }
.blase.vorlaeufig { border-left-color: var(--warn); }
.blase.vorlaeufig::after { color: var(--signal); }
.leiste { display: flex; flex-direction: column; gap: .35rem;
          align-self: flex-start; width: 92%; }
.leiste button { text-align: left; min-height: var(--tippflaeche);
                 padding: .5rem .65rem; background: var(--grund-2);
                 color: var(--text); border: 1px solid var(--signal);
                 border-radius: var(--radius); font: inherit; }
.leiste button::before { content: "> "; color: var(--signal); }
.leiste button:disabled { opacity: .4; }
.quittung { font-size: .82rem; color: var(--text-leise); align-self: flex-start; }
#tippt { min-height: 1.3em; font-size: .85rem; color: var(--text-leise);
         letter-spacing: .05em; font-family: var(--schrift-tech); }
"""

#: Der Chat, Entwurf B: Buehne. Serifenfreie Leseschrift, weiche Formen,
#: keine Kennzeile -- Bot und Gruppe unterscheiden sich wie Repliken.
_CHAT_B = """
.verlauf { display: flex; flex-direction: column; gap: .6rem; }
.blase { padding: .6rem .8rem; max-width: 90%; font-size: 1.0625rem;
         border-radius: var(--radius-gross); overflow-wrap: anywhere; }
.blase.bot { background: var(--grund-2); border: 1px solid var(--linie);
             align-self: flex-start; border-bottom-left-radius: .3rem; }
.blase.gruppe { background: var(--signal-tief); border: 1px solid var(--rand);
                align-self: flex-end; border-bottom-right-radius: .3rem; }
.blase.sprache { color: var(--text-leise); font-style: italic; }
.blase q { display: block; margin: .55rem 0; padding-left: .7rem;
           border-left: 3px solid var(--signal); color: var(--signal);
           font-family: var(--schrift-skript); font-style: italic;
           font-size: 1.15rem; quotes: none; }
.blase.vorlaeufig { border-style: dashed; }
.blase.vorlaeufig::after { color: var(--signal);
                           font-family: var(--schrift-tech); }
.leiste { display: flex; flex-direction: column; gap: .4rem;
          align-self: flex-start; width: 90%; }
.leiste button { text-align: left; min-height: var(--tippflaeche);
                 padding: .55rem .8rem; background: var(--grund-2);
                 color: var(--text); border: 1px solid var(--signal);
                 border-radius: var(--radius);
                 font-family: var(--schrift-skript); font-size: 1.05rem; }
.leiste button:disabled { opacity: .4; }
.quittung { font-size: .85rem; color: var(--text-leise); align-self: flex-start; }
#tippt { min-height: 1.3em; font-size: .8rem; color: var(--text-leise);
         letter-spacing: .06em; text-transform: uppercase;
         font-family: var(--schrift-tech); }
"""
```

- [ ] **Schritt 4: Der Denk-Zustand im JS**

Der erste Baustein. In `web_gestalt.py`:

```python
#: Baustein 1: der Denk-Zustand.
#:
#: ``#tippt`` traegt seit Karte A2 den Text ("schreibt …"); diese Zeile
#: macht daraus eine Terminalzeile mit Cursor. Sie liest nur, ob dort
#: etwas steht -- den Text setzt weiterhin ``_CHAT_JS``.
#:
#: **Warum ein MutationObserver und kein Intervall:** der Zustand wechselt
#: hoechstens alle zwei Sekunden (Polltakt), und ein Intervall, das
#: nichts findet, laeuft trotzdem -- auf einem Telefon, das in der Tasche
#: liegt, den ganzen Workshop lang.
_JS_DENKT = """
  (function denkt() {
    var feld = el('tippt');
    if (!feld) { return; }
    var pruefe = function () {
      feld.dataset.uxDenkt = (feld.textContent || '').trim() ? '1' : '0';
    };
    new MutationObserver(pruefe).observe(
      feld, { childList: true, characterData: true, subtree: true });
    pruefe();
  })();
"""
```

und `_BAUSTEINE = _JS_DENKT` (die weiteren Aufgaben haengen an).

Dazu die Cursorregel — sie gehoert zu `_BASIS` **nicht**, weil sie im Panel liegt; also
ans Ende von `_CHAT_A` **und** `_CHAT_B`:

```css
#tippt[data-ux-denkt="1"]::after { content: "\\258D"; }
```

Der Cursor blinkt dabei ueber die Regel in `_CHAT_A`/`_CHAT_B`:

```css
#tippt[data-ux-denkt="1"]::after { animation: ux-blinken 1s steps(2) infinite; }
```

**`BEWEGT` bekommt dafuer keinen neuen Eintrag** — `#tippt::after` steht schon drin
(Karte W animiert dort ebenfalls), und der Test aus Aufgabe 3 prueft Teilstring-Enthaltensein:
`#tippt[data-ux-denkt="1"]::after` ist **nicht** in `#tippt::after` enthalten. **Also
`BEWEGT` ergaenzen** um `'#tippt[data-ux-denkt="1"]::after'`; der Test aus Aufgabe 3 wird
sonst rot. Das ist genau der Zweck dieses Tests.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_js.py tests/test_web_gestalt_css.py \
  tests/test_web_gestalt_einhang.py -q -p no:cacheprovider
```
Erwartet: alle passed (bis auf die beiden `xfail` aus Aufgabe 4).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_js.py
git commit -m "UX: der Chat -- Blasen, Knopfleisten, Strom-Cursor, Denk-Zustand

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 6: Tableiste und Panels (A: unten am Daumen · B: oben)

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_TABS_A`, `_TABS_B`, `_STAND`)
- Aendern: `tests/test_web_gestalt_js.py` (Abschnitt „Tabs")

**Die Entscheidung, und ihr Preis.** W laesst die Frage offen („auf einem Telefon spricht
viel fuer unten", Uebergabe 1). Entwurf A legt die Leiste **unten**, Entwurf B **oben**.
W erzeugt sie im Markup **vor** den Panels (`_tabs_html` vor der Panel-Schleife) — beide
Orte sind also **reine CSS-Entscheidungen**, ohne eine Zeile an `web_vereint`.

Der Preis von „unten": die Leiste liegt ueber dem Fuss des Chats (`.fuss`, `position:
fixed; bottom: 0` aus A2). Also bekommt der Fuss in A einen Abstand nach unten
(`bottom: var(--tabs-hoehe)`) und der `body` unten Platz fuer beides. In B ist
`--tabs-hoehe: 0rem`, und genau dafuer ist das Token da.

**`.fuss` gehoert zum Chat.** In beiden Entwuerfen wird er ausgeblendet, sobald ein anderes
Panel vorn ist: im Skript liest man, dort tippt niemand. W setzt `document.body.dataset.tab`
— daran haengt die Regel, also braucht es **kein** JavaScript dafuer.

- [ ] **Schritt 1: Den Test ergaenzen**

An `tests/test_web_gestalt_js.py` anhaengen:

```python
# -- Tabs und Panels ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_tableiste_ist_am_daumen_gross_genug(name):
    css = web_gestalt.css_rahmen(name)
    assert ".tabs button" in css
    assert "min-height: var(--tippflaeche)" in css or "--tabs-hoehe" in css


def test_a_legt_die_tabs_unten_und_b_oben():
    """Die eine Entscheidung, die Karte W offen gelassen hat
    (Uebergabe 1: "auf einem Telefon spricht viel fuer unten")."""
    def tabblock(name):
        return re.search(r"\.tabs\s*\{([^}]*)\}",
                         web_gestalt.css_rahmen(name), flags=re.S).group(1)

    assert "position: fixed" in tabblock("a") and "bottom: 0" in tabblock("a")
    assert "position: sticky" in tabblock("b") and "top: 0" in tabblock("b")
    # ``--tabs-hoehe`` ist der Platz, den der Fuss nach unten frei laesst:
    # in B liegt die Leiste oben, also null.
    assert web_gestalt.TOKENS["a"]["tabs-hoehe"] != "0rem"
    assert web_gestalt.TOKENS["b"]["tabs-hoehe"] == "0rem"


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_weicht_der_tableiste(name):
    """In A liegt die Leiste unter dem Fuss; in B ist ``--tabs-hoehe``
    null und dieselbe Regel kostet nichts."""
    assert "bottom: var(--tabs-hoehe)" in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_verschwindet_ausserhalb_des_chats(name):
    """Im Skript liest man, dort tippt niemand. W setzt
    ``body[data-tab]`` -- also braucht das kein JavaScript."""
    css = web_gestalt.css_rahmen(name)
    assert 'body:not([data-tab="chat"]) .fuss' in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_gewaehlte_tab_ist_nicht_nur_farbig_markiert(name):
    """Farbe allein traegt keinen Zustand (WCAG 1.4.1): der gewaehlte Tab
    bekommt zusaetzlich eine Kante."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(
        r'\.tabs button\[aria-selected="true"\]\s*\{([^}]*)\}', css, flags=re.S)
    assert block, "kein Stil fuer den gewaehlten Tab"
    assert "box-shadow" in block.group(1) or "border" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_arbeitsstand_setzt_seine_feldkarten(name):
    css = web_gestalt.css_stand(name)
    assert "[data-feld]" in css or ".feld" in css
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider -k "tab or fuss or arbeitsstand"
```
Erwartet: FAIL — `_TABS_A` und `_STAND` sind leer.

- [ ] **Schritt 3: Die Tableiste**

```python
#: Tableiste, Entwurf A: UNTEN, am Daumen. Auf einem Telefon im Stehen
#: ist das untere Drittel die einzige Flaeche, die eine Hand erreicht --
#: und die Gruppe wechselt oft zwischen Chat und Textbuch.
#:
#: Die Leiste liegt UNTER dem Fuss des Chats, deshalb bekommt der Fuss
#: ``bottom: var(--tabs-hoehe)``. In B ist dieses Token ``0rem``, und
#: dieselbe Regel kostet dort nichts.
_TABS_A = """
.tabs { position: fixed; left: 0; right: 0; bottom: 0; z-index: 7;
        margin: 0 auto; max-width: 46rem; height: var(--tabs-hoehe);
        display: flex; background: var(--grund-3);
        border-top: 1px solid var(--linie); }
.tabs button { flex: 1; min-height: var(--tabs-hoehe); border: 0;
               background: transparent; color: var(--text-leise);
               font-family: var(--schrift-tech); font-size: .8rem;
               letter-spacing: .08em; text-transform: uppercase; }
.tabs button[aria-selected="true"] { color: var(--signal);
                                     background: var(--grund-2);
                                     box-shadow: inset 0 2px 0 var(--signal); }
.tabs button { transition: color var(--takt-schnell) linear; }
.fuss { bottom: var(--tabs-hoehe); z-index: 6; }
body { padding-bottom: calc(var(--tabs-hoehe) + 12.5rem); }
body:not([data-tab="chat"]) .fuss { display: none; }
"""

#: Tableiste, Entwurf B: OBEN, unter der Aktleiste -- zusammen ein
#: Programmzettel. Der Fuss traegt dort den runden Aufnahmeknopf und
#: braucht die ganze untere Kante fuer sich.
_TABS_B = """
.tabs { position: sticky; top: 0; z-index: 7; display: flex; gap: .2rem;
        padding: 0 .55rem; background: var(--grund);
        border-bottom: 1px solid var(--linie); }
.tabs button { flex: 1; min-height: var(--tippflaeche); border: 0;
               border-bottom: 3px solid transparent; background: transparent;
               color: var(--text-leise);
               font-family: var(--schrift-skript); font-size: 1rem;
               padding: .35rem .2rem .45rem; }
.tabs button[aria-selected="true"] { color: var(--signal);
                                     border-bottom-color: var(--signal); }
.tabs button { transition: color var(--takt-schnell) linear; }
.fuss { bottom: var(--tabs-hoehe); z-index: 6; }
body { padding-bottom: 13rem; }
body:not([data-tab="chat"]) .fuss { display: none; }
"""
```

- [ ] **Schritt 4: Das Arbeitsstand-Panel**

Fuer beide Entwuerfe gleich — es ist eine Leseflaeche, und die Tokens tragen den
Unterschied:

```python
#: Der Arbeitsstand: eine Karte je Feld. Die Formulare der Gruppenseite
#: (``web._rahmen``, ``_textfeld``, ``_dropdown``) bleiben, wie sie sind --
#: gestaltet werden nur Flaeche, Rand und Beschriftung.
_STAND = """
[data-feld] { background: var(--grund-2); border: 1px solid var(--linie);
              border-radius: var(--radius); padding: .55rem .65rem;
              margin: 0 0 .5rem; }
dt { font-family: var(--schrift-tech); font-size: .72rem; letter-spacing: .1em;
     text-transform: uppercase; color: var(--text-leise); opacity: 1; }
dd { margin: .15rem 0 0; }
input[type="text"], textarea, select { font: inherit; color: var(--text);
     background: var(--grund-3); border: 1px solid var(--rand);
     border-radius: var(--radius); min-height: var(--tippflaeche);
     padding: .45rem .6rem; width: 100%; }
button { font: inherit; min-height: var(--tippflaeche);
         background: var(--grund-3); color: var(--text);
         border: 1px solid var(--rand); border-radius: var(--radius);
         padding: .4rem .8rem; }
blockquote { border-left: 2px solid var(--warn); color: var(--warn);
             font-family: var(--schrift-skript); font-style: italic; }
.art { background: var(--grund-3); color: var(--text-leise);
       border-radius: 1rem; }
details > summary { min-height: var(--tippflaeche); display: flex;
                    align-items: center; cursor: pointer; }
"""
```

**`BEWEGT` bekommt `.tabs button` schon aus Aufgabe 3** — die `transition` oben ist damit
abgedeckt. Der Test aus Aufgabe 3 laeuft mit.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_js.py tests/test_web_gestalt_css.py \
  tests/test_web_gestalt_einhang.py tests/test_web_vereint.py -q -p no:cacheprovider
```
Erwartet: alle passed (bis auf die beiden `xfail`).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_js.py
git commit -m "UX: Tableiste (A unten, B oben) und das Arbeitsstand-Panel

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 7: Die sieben Akte — Phasenleiste, Fortschritt, Bestaetigung

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_ROADMAP`, `_JS_FORTSCHRITT`)
- Aendern: `tests/test_web_gestalt_js.py` (Abschnitt „Akte")

**Die Metapher, und wo sie aufhoert.** Sieben Phasen werden im Chat-Text **nicht**
umbenannt — `phasentexte` und `phasen.PHASEN` bleiben, wie sie sind, und der Bot sagt
weiter „Phase 3". Umbenannt wird **nur die Beschriftung in der Web-Uebersicht**: dort steht
„Act 3 of 7". Grund: die Phasennamen stehen in Prompts, im Journal, in `/stand` und in den
Migrationen (`db.PHASEN_UMNUMMERIERUNG`); sie dort anzufassen waere ein Umbau, keine
Gestaltung. Die Akt-Beschriftung ist ein Mikrotext dieses Moduls
(`_TEXT_AKT_KOPF`, Aufgabe 11) und wird vom Effekt-JS **vor** den bestehenden Text der
`<summary>` gesetzt — der Text von W bleibt daneben stehen.

**Was hinzukommt:** ein Fortschrittsbalken in der zugeklappten Zeile (A: ein Balken,
B: sieben Buehnenlichter). Er wird aus dem gerechnet, was ohnehin im DOM steht
(`.aufgabe.erledigt` gegen `.aufgabe`), und ueber CSSOM gesetzt — **kein neuer Schluessel
im Zustands-Poll, kein SQL**.

**Was nicht hinzukommt:** die Bestaetigung („Switch to Act 5: …?") baut W schon
(`_VEREINT_JS`, `data-sicher`). Diese Aufgabe **gestaltet** sie: der Knopf im
Bestaetigungszustand wird gefuellt und fett, damit niemand ihn fuer die normale
Beschriftung haelt.

- [ ] **Schritt 1: Den Test ergaenzen**

```python
# -- Die sieben Akte ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_aktleiste_hat_ihre_zustaende(name):
    css = web_gestalt.css_rahmen(name)
    for selektor in (".phase.aktiv", ".phase-knopf", ".aufgabe.erledigt",
                     ".aufgabe.laeuft"):
        assert selektor in css, selektor


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_bestaetigungszustand_sieht_anders_aus(name):
    """W schreibt beim ersten Druck die Rueckfrage in den Knopf
    (``data-sicher``). Sieht der Knopf dabei aus wie vorher, liest ihn
    niemand -- und der zweite Druck kommt aus Versehen."""
    assert '.phase-knopf[data-sicher="1"]' in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_eine_aufgabe_ist_gross_genug_zum_antippen(name):
    """Jede Aufgabe ist ein Sprungziel (``data-ziel-tab``)."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(r"\.aufgabe\s*\{([^}]*)\}", css, flags=re.S)
    assert block and "min-height: var(--tippflaeche)" in block.group(1)


def test_der_fortschritt_wird_aus_dem_dom_gerechnet(js):
    """Kein neuer Schluessel im Zustands-Poll: die Zahlen stehen schon
    da."""
    assert "aufgabe" in js
    assert "erledigt" in js
    assert "setProperty('--fortschritt'" in js


def test_der_fortschritt_haengt_nicht_an_einer_festen_sieben(js):
    """``phasen.PHASEN`` hat sich seit dem 04.09.2026 dreimal geaendert.
    Die Gestaltung zaehlt, was da ist."""
    assert "querySelectorAll" in js
    assert re.search(r"/\s*7\b", js) is None


def test_die_akt_beschriftung_kommt_aus_den_mikrotexten(js):
    """Sonst stuende in Dortmund Englisch und in Padua Deutsch."""
    assert "TEXTE" in js
    assert "akt_kopf" in js
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider -k "akt or aufgabe or fortschritt or bestaetigung"
```
Erwartet: FAIL — `_ROADMAP` ist leer.

- [ ] **Schritt 3: Das Roadmap-CSS**

```python
#: Die Phasenuebersicht als Aktfolge. Fuer beide Entwuerfe dieselbe
#: Struktur -- die Tokens und die zwei Abweichungen unten tragen den
#: Unterschied.
#:
#: **Zugeklappt eine Zeile** (Karte W): sieben Akte mit ihren Aufgaben
#: naehmen am Telefon ein Drittel des Bildschirms fuer etwas, das man
#: dreimal am Tag braucht. Aufgeklappt bekommt die Liste
#: ``max-height: 58vh`` -- sonst schiebt sie am Telefon die Tableiste aus
#: dem Bild (gemessen am Entwurf, Screenshot ``entwurf-b-handy-akte.png``
#: vor der Nachbesserung).
_ROADMAP = """
header { position: sticky; top: 0; z-index: 4; background: var(--grund);
         border-bottom: 1px solid var(--linie); padding: .5rem .75rem; }
.roadmap > summary { list-style: none; cursor: pointer;
                     min-height: var(--tippflaeche); display: flex;
                     align-items: center; gap: .5rem; color: var(--signal);
                     font-family: var(--schrift-tech); font-size: .9rem;
                     letter-spacing: .04em; }
.roadmap > summary::-webkit-details-marker { display: none; }
.phasen { list-style: none; margin: .4rem 0 .2rem; padding: 0;
          max-height: 58vh; overflow-y: auto; }
.phase { border-left: 2px solid var(--linie); padding: 0 0 .35rem .55rem;
         margin: 0 0 .35rem; }
.phase.aktiv { border-left-color: var(--warn); }
.phase-knopf { display: block; width: 100%; text-align: left; font: inherit;
               min-height: var(--tippflaeche); background: var(--grund-2);
               color: var(--text); border: 1px solid var(--rand);
               border-radius: var(--radius); padding: .45rem .6rem;
               transition: background var(--takt-schnell) linear; }
.phase.aktiv .phase-knopf { border-color: var(--warn); color: var(--warn); }
.phase-knopf[data-sicher="1"] { background: var(--warn); color: var(--auf-warn);
                                border-color: var(--warn); font-weight: 700; }
.aufgaben { list-style: none; margin: .3rem 0 0; padding: 0 0 0 .1rem;
            font-size: .88rem; }
.aufgabe { min-height: var(--tippflaeche); display: flex; align-items: center;
           gap: .45rem; cursor: pointer; color: var(--text-leise); }
.aufgabe.erledigt { color: var(--signal); }
.aufgabe.laeuft { color: var(--warn); }
#ux-balken { flex: 1; height: .4rem; background: var(--grund-3);
             border: 1px solid var(--linie); border-radius: var(--radius); }
#ux-balken i { display: block; height: 100%; width: var(--fortschritt, 0%);
               background: var(--signal); }
"""
```

**Abweichung B** — ans Ende von `_TABS_B` (es ist entwurfsabhaengig und `_ROADMAP` ist es
nicht):

```css
/* B: die sieben Akte als Reihe von Buehnenlichtern statt als ein
   Balken. Dieselbe Zahl, andere Metapher. */
#ux-balken { display: flex; gap: .28rem; height: .5rem;
             background: none; border: 0; }
#ux-balken i { flex: 1; width: auto; border-radius: .25rem;
               background: var(--grund-3); border: 1px solid var(--linie); }
.roadmap > summary { font-family: var(--schrift-skript); font-size: .95rem; }
.phase-knopf { font-family: var(--schrift-skript); }
```

- [ ] **Schritt 4: Der Fortschritt im JS**

```python
#: Baustein 2: der Fortschritt in der zugeklappten Aktzeile.
#:
#: Gerechnet aus dem, was ohnehin im DOM steht -- **kein neuer Schluessel
#: im Zustands-Poll und kein SQL**. In A ist das EIN Balken (Breite ueber
#: ``--fortschritt``), in B sind es sieben Lichter (je eins je Akt, mit
#: ``data-stand``). Beides derselbe Code, weil beides aus denselben zwei
#: Zahlen faellt.
#:
#: Die Zahl 7 steht nirgends: ``phasen.PHASEN`` hat sich seit dem
#: 04.09.2026 dreimal geaendert, und eine feste Sieben waere beim
#: naechsten Mal falsch.
_JS_FORTSCHRITT = """
  (function fortschritt() {
    var roadmap = el('roadmap');
    if (!roadmap) { return; }
    var summary = roadmap.querySelector('summary');
    var phasen = roadmap.querySelectorAll('.phase');
    if (!summary || !phasen.length) { return; }

    var balken = document.createElement('span');
    balken.id = 'ux-balken';
    if (MOMENT === 'vorhang') {           // Entwurf B: ein Licht je Akt
      for (var i = 0; i < phasen.length; i++) {
        var licht = document.createElement('i');
        var knoten = phasen[i];
        licht.dataset.stand = knoten.classList.contains('aktiv') ? 'aktiv'
          : (knoten.querySelector('.aufgabe:not(.erledigt)') ? 'offen' : 'fertig');
        balken.appendChild(licht);
      }
    } else {                              // Entwurf A: ein Balken
      balken.appendChild(document.createElement('i'));
      var alle = roadmap.querySelectorAll('.aufgabe').length;
      var fertig = roadmap.querySelectorAll('.aufgabe.erledigt').length;
      balken.style.setProperty(
        '--fortschritt', (alle ? Math.round(fertig * 100 / alle) : 0) + '%');
    }
    summary.appendChild(balken);

    // Die Akt-Beschriftung VOR den Text von Karte W, nicht statt ihm:
    // dort steht "Phase 3 von 7 · Interviews — 1/3", und das ist die
    // Wahrheit aus der Datenbank.
    var aktiv = roadmap.querySelector('.phase.aktiv');
    if (aktiv && TEXTE.akt_kopf) {
      var marke = document.createElement('b');
      marke.className = 'ux-akt';
      marke.textContent = TEXTE.akt_kopf
        .replace('{nummer}', (Array.prototype.indexOf.call(phasen, aktiv) + 1))
        .replace('{gesamt}', phasen.length);
      summary.insertBefore(marke, summary.firstChild);
    }
  })();
"""
```

`_BAUSTEINE = _JS_DENKT + _JS_FORTSCHRITT`.

Und die Regel fuer die Marke ans Ende von `_ROADMAP`:

```css
.ux-akt { color: var(--warn); letter-spacing: .1em; margin-right: .4rem; }
```

**`BEWEGT` bekommt `.phase-knopf`** — steht schon aus Aufgabe 3 drin.

- [ ] **Schritt 5: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_js.py tests/test_web_gestalt_css.py \
  tests/test_phase_klick.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_js.py
git commit -m "UX: die sieben Akte -- Leiste, Fortschritt aus dem DOM, Bestaetigung sichtbar

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 8: Die zwei Aufnahmeknoepfe — der wichtigste Teil dieser Karte

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_CHAT_A`, `_CHAT_B` erweitern,
  `_JS_AUFNAHME`)
- Aendern: `tests/test_web_gestalt_js.py` (Abschnitt „Aufnahme")

**Warum das die wichtigste Aufgabe ist.** Dortmund Tag 1: **13 von 20 Aufnahmen leer**, und
ein Knopf wurde **14× in 93 Sekunden** gedrueckt. Der Zustand war nicht erkennbar. Alles
andere in dieser Karte ist Ausstattung; das hier ist der Punkt, an dem Gestaltung darueber
entscheidet, ob am Ende des Tages Material da ist.

**Vier Regeln, die im Code stehen:**

1. **Jeder Zustand steht im TEXT, nicht nur in der Farbe** (WCAG 1.4.1, und der
   Probenraum ist schlecht beleuchtet): `Record interview` → `Starting …` →
   `Stop recording` → `Sending …`, dazu eine zweite Zeile mit dem, was gerade passiert
   („Mic is hot.").
2. **Rueckmeldung unter 100 ms beim Tippen.** `#interview:active` gibt sofort eine
   Verformung (`transform: scale(.985)`) — das ist CSS, kein Netz, kein Promise. Die
   Zustandsaenderung kommt spaeter; das Gefuehl „angekommen" sofort.
3. **Der laufende Zustand ist groesser als der ruhende.** Nicht nur anders gefaerbt: die
   Flaeche waechst (`--rec-hoehe` + 0.75rem in A, + 1.1rem in B). Wer im Augenwinkel
   hinsieht, sieht den Unterschied.
4. **Die zwei Mikrofone unterscheiden sich auf vier Achsen** — Form, Ort, Farbe, Verb:

   | | Interview (`#interview`) | Push-to-Talk (`#ptt`) |
   |---|---|---|
   | Form (A) | Taste ueber die volle Breite | Kreis |
   | Form (B) | Kreis (Scheinwerfer) | Pille |
   | Ort | eigene Zeile ueber der Eingabe | **in** der Eingabezeile |
   | Farbe | `--rec` (rot) | `--signal` |
   | Verb | tippen an / tippen aus | halten |

**Was die Gestaltung NICHT tut** (Befund 1 im Plan-Kopf): sie faengt keinen Druck ab. Sie
zeigt `aria-busy="true"` und `cursor: progress`, waehrend ein Uebergang laeuft — die
Sperre selbst gehoert nach A2. Das steht als Kommentar im Code und im BERICHT.

**Woher die vier Zustaende kommen.** A2 liefert nur `an`/`aus`. Der Rest wird **abgeleitet**
aus dem, was im DOM steht — kein neuer Schluessel im Zustands-Poll:

| Zustand | Bedingung |
|---|---|
| `ruht` | `#fuss[data-interview="0"]` und `#warteschlange` leer |
| `startet` | seit dem Druck ist `data-interview` noch `0` |
| `laeuft` | `#fuss[data-interview="1"]` |
| `laedt` | `data-interview` gerade auf `0` gewechselt **und** `#warteschlange` nicht leer |

- [ ] **Schritt 1: Den Test ergaenzen**

```python
# -- Die zwei Aufnahmeknoepfe ------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_aufnahmeknopf_ist_deutlich_groesser_als_eine_tippflaeche(name):
    """Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14x in 93 s
    gedrueckt. Das ist das wichtigste Element dieser Oberflaeche."""
    tippflaeche = float(web_gestalt.TOKENS[name]["tippflaeche"].removesuffix("rem"))
    rec = float(web_gestalt.TOKENS[name]["rec-hoehe"].removesuffix("rem"))
    assert rec >= tippflaeche * 1.5, (rec, tippflaeche)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("zustand", ["startet", "laeuft", "laedt"])
def test_jeder_zustand_hat_seine_regel(name, zustand):
    """``ruht`` ist die Grundregel ``#interview { … }`` und braucht kein
    Attribut; die drei anderen sind Abweichungen davon."""
    assert f'#interview[data-ux-zustand="{zustand}"]' in web_gestalt.css_chat(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_laufende_zustand_ist_groesser_als_der_ruhende(name):
    """Nicht nur anders gefaerbt: wer im Augenwinkel hinsieht, soll den
    Unterschied sehen."""
    css = web_gestalt.css_chat(name)
    block = re.search(
        r'#interview\[data-ux-zustand="laeuft"\]\s*\{([^}]*)\}', css, flags=re.S)
    assert block, "kein Stil fuer den laufenden Zustand"
    assert "calc(var(--rec-hoehe)" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_es_gibt_eine_rueckmeldung_unter_hundert_millisekunden(name):
    """``:active`` ist CSS -- kein Netz, kein Promise, kein Warten."""
    assert "#interview:active" in web_gestalt.css_chat(name)
    takt = int(web_gestalt.TOKENS[name]["takt-schnell"].removesuffix("ms"))
    assert takt < 100, takt


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zwei_mikrofone_unterscheiden_sich_in_der_form(name):
    """Form, Ort, Farbe, Verb -- vier Achsen. Die Form ist die, die man
    im Augenwinkel sieht."""
    css = web_gestalt.css_chat(name)
    rund = re.search(r"#ptt\s*\{[^}]*border-radius:\s*([^;]+);", css, flags=re.S)
    knopf = re.search(r"#interview\s*\{[^}]*border-radius:\s*([^;]+);", css, flags=re.S)
    assert rund and knopf
    assert rund.group(1).strip() != knopf.group(1).strip()


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zwei_mikrofone_haben_verschiedene_farben(name):
    css = web_gestalt.css_chat(name)
    assert "var(--rec)" in re.search(r"#interview\s*\{([^}]*)\}", css, flags=re.S).group(1)
    assert "var(--signal)" in re.search(r"#ptt\s*\{([^}]*)\}", css, flags=re.S).group(1)


def test_das_skript_leitet_die_vier_zustaende_ab(js):
    for zustand in ("ruht", "startet", "laeuft", "laedt"):
        assert zustand in js, zustand
    assert "data-interview" in js or "dataset.interview" in js
    assert "warteschlange" in js


def test_das_skript_zeigt_busy_aber_sperrt_nicht(js):
    """Befund 1 an Karte A2 (Plan-Kopf): dort werden Drucke waehrend eines
    Uebergangs NICHT ignoriert. Das zu reparieren waere Logik. Die
    Gestaltung zeigt es -- und ein ``preventDefault``/``stopPropagation``
    hier waere genau die stille Reparatur, die der Plan verbietet."""
    assert "aria-busy" in js
    assert "stopPropagation" not in js
    assert "stopImmediatePropagation" not in js


def test_der_zustandstext_steht_neben_dem_knopf_nicht_darin(js):
    """Sonst schreiben zwei Stellen in denselben Knoten (Befund 2)."""
    assert "ux-rec-zeile" in js
    assert "createElement" in js


def test_die_zustandstexte_kommen_aus_den_mikrotexten(js):
    for schluessel in ("rec_ruht", "rec_startet", "rec_laeuft", "rec_laedt"):
        assert schluessel in js, schluessel
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider -k "aufnahme or mikrofone or zustand or busy or rueckmeldung"
```
Erwartet: FAIL — `#interview[data-ux-zustand="laeuft"]` gibt es nicht.

- [ ] **Schritt 3: Der Knopf in Entwurf A**

Ans Ende von `_CHAT_A`:

```css
/* -- Knopf 1: Interview (Umschalter) --------------------------------
   Volle Breite, eigene Zeile, Rot. Der wichtigste Knopf der Oberflaeche
   (Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14x in 93 s
   gedrueckt) -- also die groesste Flaeche, die der Fuss hergibt, und ein
   Zustand, der im TEXT steht und nicht nur in der Farbe. */
#interview { width: 100%; min-height: var(--rec-hoehe);
             border-radius: var(--radius-gross);
             border: 2px solid var(--rec); background: var(--grund-2);
             color: var(--text); font: inherit; font-size: 1.05rem;
             letter-spacing: .1em; text-transform: uppercase;
             display: flex; align-items: center; justify-content: center;
             gap: .5rem; }
/* Die Lampe: ein Punkt, kein Bild -- kein url(), keine CSP-Frage. */
#interview::before { content: ""; width: .85rem; height: .85rem;
                     border-radius: 50%; background: var(--rec); }
/* Rueckmeldung unter 100 ms: CSS, kein Netz, kein Promise. */
#interview:active { transform: scale(.985); }
#interview[data-ux-zustand="startet"] { border-color: var(--warn);
                                        color: var(--warn); }
#interview[data-ux-zustand="startet"]::before { background: var(--warn);
    animation: ux-puls .7s ease-in-out infinite; }
#interview[data-ux-zustand="laeuft"] { background: var(--rec);
    color: var(--auf-rec); border-color: var(--rec);
    min-height: calc(var(--rec-hoehe) + .75rem); }
#interview[data-ux-zustand="laeuft"]::before { background: var(--auf-rec);
    animation: ux-puls 1.1s ease-in-out infinite; }
#interview[data-ux-zustand="laedt"] { border-color: var(--warn);
                                      color: var(--warn); }
#interview[data-ux-zustand="laedt"]::before { background: var(--warn); }
#interview[aria-busy="true"] { cursor: progress; }
/* Die zweite Zeile steht NEBEN dem Knopf, nie darin: ``_CHAT_JS`` setzt
   dort ``textContent`` (Befund 2 an Karte A2). */
#ux-rec-zeile { text-align: center; font-size: .76rem;
                color: var(--text-leise); margin-top: -.2rem; }
#interview[data-ux-zustand="laeuft"] + #ux-rec-zeile { color: var(--rec); }

/* -- Knopf 2: Push-to-Talk (halten) ---------------------------------
   Andere Form (Kreis), anderer Ort (in der Eingabezeile), andere Farbe
   (Signal statt Rot), anderes Verb (halten statt tippen). A2 blendet ihn
   aus, solange ein Interview laeuft -- zwei Mikrofone gleichzeitig sind
   keine Bedienung. */
#ptt { width: var(--tippflaeche); min-width: var(--tippflaeche);
       height: var(--tippflaeche); border-radius: 50%;
       border: 1px dashed var(--signal); background: var(--grund-2);
       color: var(--signal); font-size: 1.15rem; touch-action: none; }
#ptt[data-haelt="1"] { background: var(--signal); color: var(--auf-signal);
                       border-style: solid; }

/* -- Messwerk: Uhr, Pegel, Warteschlange ---------------------------- */
#uhr { font-family: var(--schrift-tech); font-variant-numeric: tabular-nums;
       font-size: 1.35rem; color: var(--warn); }
#pegel { height: .55rem; background: var(--grund-3);
         border: 1px solid var(--linie); border-radius: var(--radius);
         overflow: hidden; }
#pegel span { display: block; height: 100%; background: var(--rec);
              transition: width var(--takt-schnell) linear; }
#warteschlange { font-size: .78rem; color: var(--warn); min-height: 1.1em;
                 font-family: var(--schrift-tech); }
.fuss { background: var(--grund); border-top: 1px solid var(--linie); }
.zeile input { background: var(--grund-2); color: var(--text);
               border: 1px solid var(--rand); border-radius: var(--radius);
               min-height: var(--tippflaeche); }
#senden { background: var(--signal); color: var(--auf-signal); border: 0;
          border-radius: var(--radius); min-width: var(--tippflaeche);
          min-height: var(--tippflaeche); font-weight: 700; }
"""
```

- [ ] **Schritt 4: Der Knopf in Entwurf B**

Ans Ende von `_CHAT_B` — **dieselben Selektoren, andere Form**:

```css
/* -- Knopf 1: Interview als Scheinwerfer ---------------------------- */
#interview { width: var(--rec-hoehe); height: var(--rec-hoehe);
             border-radius: 50%; border: 3px solid var(--rec);
             background: var(--grund-2); color: var(--text); font: inherit;
             font-family: var(--schrift-tech); font-size: .66rem;
             letter-spacing: .1em; text-transform: uppercase;
             display: flex; flex-direction: column; align-items: center;
             justify-content: center; gap: .15rem; }
#interview::before { content: ""; width: 1.1rem; height: 1.1rem;
                     border-radius: 50%; background: var(--rec); }
#interview:active { transform: scale(.95); }
#interview[data-ux-zustand="startet"] { border-color: var(--warn); }
#interview[data-ux-zustand="startet"]::before { background: var(--warn);
    animation: ux-puls .7s ease-in-out infinite; }
#interview[data-ux-zustand="laeuft"] { background: var(--rec);
    color: var(--auf-rec); border-color: var(--auf-rec);
    width: calc(var(--rec-hoehe) + 1.1rem);
    height: calc(var(--rec-hoehe) + 1.1rem); }
#interview[data-ux-zustand="laeuft"]::before { background: var(--auf-rec);
    border-radius: .2rem; animation: ux-puls 1.1s ease-in-out infinite; }
#interview[data-ux-zustand="laedt"] { border-color: var(--warn);
                                      color: var(--warn); }
#interview[data-ux-zustand="laedt"]::before { background: var(--warn); }
#interview[aria-busy="true"] { cursor: progress; }
/* Neben dem Knopf statt darunter: sonst nimmt der Fuss ein Drittel des
   Telefons (gemessen am Entwurf vor der Nachbesserung). */
.fuss { flex-direction: row; flex-wrap: wrap; align-items: center;
        gap: .5rem .9rem; background: var(--grund);
        border-top: 1px solid var(--linie); }
#ux-rec-zeile { flex: 1; font-family: var(--schrift-skript);
                font-size: 1.1rem; color: var(--text); }
#interview[data-ux-zustand="laeuft"] + #ux-rec-zeile { color: var(--rec); }

/* -- Knopf 2: Push-to-Talk als Pille -------------------------------- */
#ptt { min-width: 7.5rem; min-height: var(--tippflaeche);
       border-radius: 1.4rem; border: 1px dashed var(--signal);
       background: var(--grund-2); color: var(--signal);
       font-family: var(--schrift-tech); font-size: .76rem;
       letter-spacing: .06em; text-transform: uppercase;
       touch-action: none; padding: 0 .7rem; }
#ptt[data-haelt="1"] { background: var(--signal); color: var(--auf-signal);
                       border-style: solid; font-weight: 700; }

/* -- Messwerk ------------------------------------------------------- */
#uhr { font-family: var(--schrift-tech); font-variant-numeric: tabular-nums;
       font-size: 1.4rem; color: var(--signal); }
#pegel { height: .6rem; background: var(--grund-3);
         border: 1px solid var(--linie); border-radius: 1rem;
         overflow: hidden; }
#pegel span { display: block; height: 100%; background: var(--rec);
              transition: width var(--takt-schnell) linear; }
#warteschlange { font-family: var(--schrift-tech); font-size: .78rem;
                 color: var(--signal); min-height: 1.1em; }
.zeile input { background: var(--grund-2); color: var(--text);
               border: 1px solid var(--rand); border-radius: 1.4rem;
               min-height: var(--tippflaeche); }
#senden { background: var(--signal); color: var(--auf-signal); border: 0;
          border-radius: 1.4rem; min-height: var(--tippflaeche);
          padding: 0 1rem; font-weight: 700; }
"""
```

**`BEWEGT` bekommt zwei neue Eintraege** (sonst wird der Test aus Aufgabe 3 rot — genau
sein Zweck). Er sammelt die Selektoren **woertlich** aus dem CSS, und
`#interview[data-ux-zustand="startet"]::before` ist ein anderer String als
`#interview::before`:

```python
BEWEGT = (
    ...
    '#interview[data-ux-zustand="startet"]::before',
    '#interview[data-ux-zustand="laeuft"]::before',
    ...
)
```

`#interview`, `#interview::before` und `#pegel span` stehen schon aus Aufgabe 3 drin,
`#tippt[data-ux-denkt="1"]::after` seit Aufgabe 5. **Immer gilt: erst den Test laufen
lassen, dann genau die Selektoren nachtragen, die er nennt** — die Liste von Hand zu raten
ist der Weg, auf dem sie das naechste Mal falsch ist.

- [ ] **Schritt 5: Die Zustandsableitung im JS**

```python
#: Baustein 3: die vier Zustaende des Aufnahmeknopfes.
#:
#: **Der wichtigste Teil dieser Karte.** Karte A2 kennt nur an/aus; die
#: beiden Uebergaenge (Mikrofonfreigabe laeuft, Segmente werden noch
#: hochgeladen) sind fuer die Gruppe genau die Momente, in denen sie
#: nachdrueckt -- und in Dortmund ist daraus ein Knopf geworden, der 14x
#: in 93 Sekunden gedrueckt wurde.
#:
#: Abgeleitet wird aus dem, was schon im DOM steht:
#:   ruht     -- data-interview="0" und die Warteschlange ist leer
#:   startet  -- gedrueckt, data-interview noch "0"
#:   laeuft   -- data-interview="1"
#:   laedt    -- gerade auf "0" gewechselt, Warteschlange nicht leer
#: **Kein neuer Schluessel im Zustands-Poll, kein SQL.**
#:
#: **Diese Funktion faengt keinen Druck ab.** Dass ``_CHAT_JS`` waehrend
#: eines Uebergangs weiter auf Klicks reagiert, ist ein Logikbefund an
#: Karte A2 (Plan-Kopf, Befund 1) und gehoert dorthin. Hier wird er nur
#: SICHTBAR: aria-busy, cursor: progress, und ein Text, der sagt, was
#: gerade laeuft. Ein stopPropagation hier waere die stille Reparatur,
#: die der Plan verbietet -- und sie wuerde das Problem verstecken,
#: statt es zu loesen.
_JS_AUFNAHME = """
  (function aufnahme() {
    var knopf = el('interview');
    var fuss = el('fuss');
    var warte = el('warteschlange');
    if (!knopf || !fuss) { return; }

    // Die zweite Zeile NEBEN dem Knopf: _CHAT_JS setzt dort textContent.
    var zeile = document.createElement('div');
    zeile.id = 'ux-rec-zeile';
    knopf.parentNode.insertBefore(zeile, knopf.nextSibling);
    knopf.setAttribute('aria-describedby', 'ux-rec-zeile');

    var gedrueckt = 0;
    var zustand = null;

    var setze = function (neu) {
      if (neu === zustand) { return; }
      zustand = neu;
      knopf.dataset.uxZustand = neu;
      knopf.setAttribute('aria-busy',
        (neu === 'startet' || neu === 'laedt') ? 'true' : 'false');
      // Farbe allein traegt keinen Zustand: der Text sagt ihn auch.
      zeile.textContent = TEXTE['rec_' + neu] || '';
    };

    var lies = function () {
      var an = fuss.dataset.interview === '1';
      var laden = !!(warte && (warte.textContent || '').trim());
      if (an) { setze('laeuft'); return; }
      if (laden) { setze('laedt'); return; }
      // Nach dem Druck bleibt "startet" stehen, bis der Poll den Modus
      // meldet -- bei einer Mikrofonfreigabe sind das leicht zwei
      // Sekunden, und genau da wurde in Dortmund nachgedrueckt.
      if (gedrueckt && Date.now() - gedrueckt < 20000) { setze('startet'); return; }
      setze('ruht');
    };

    knopf.addEventListener('click', function () {
      // Kein preventDefault, kein stopPropagation: _CHAT_JS muss diesen
      // Klick weiterhin sehen (Befund 1).
      gedrueckt = (fuss.dataset.interview === '1') ? 0 : Date.now();
      lies();
    });

    new MutationObserver(function () {
      if (fuss.dataset.interview === '1') { gedrueckt = 0; }
      lies();
    }).observe(fuss, { attributes: true, attributeFilter: ['data-interview'] });

    if (warte) {
      new MutationObserver(lies).observe(
        warte, { childList: true, characterData: true, subtree: true });
    }
    lies();
  })();
"""
```

`_BAUSTEINE = _JS_DENKT + _JS_FORTSCHRITT + _JS_AUFNAHME`.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_js.py tests/test_web_gestalt_css.py \
  tests/test_web_gestalt_einhang.py tests/test_web_chat.py -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_js.py
git commit -m "UX: die zwei Aufnahmeknoepfe -- vier Zustaende im Text, vier Achsen Unterschied

Der wichtigste Teil der Karte: Dortmund Tag 1 waren 13 von 20 Aufnahmen
leer, ein Knopf wurde 14x in 93 s gedrueckt. Jeder Zustand steht jetzt im
Text und nicht nur in der Farbe, der laufende ist groesser als der
ruhende, und die Rueckmeldung beim Tippen ist CSS (<100 ms).

Die Sperre gegen Drucke waehrend eines Uebergangs gehoert zu Karte A2 und
wird hier NICHT eingebaut -- nur sichtbar gemacht (aria-busy).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 9: Die Momente — Aktwechsel und Belohnung

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_MOMENTE_A`, `_MOMENTE_B`, `_BELOHNUNG`,
  `_JS_MOMENT`)
- Aendern: `tests/test_web_gestalt_js.py` (Abschnitt „Momente")

**Die Entscheidung zur Belohnung, und warum sie keinen Serverschluessel braucht.** Die
Karte erlaubt „hoechstens ein additiver read-only-Schluessel" im Zustands-Poll. Er wird
**nicht** gebraucht: die beiden Belohnungen, die wirklich tragen, lassen sich aus dem DOM
ableiten.

| Belohnung | Ausloeser | Woher |
|---|---|---|
| **Akt abgeschlossen** | der zweite (bestaetigende) Druck auf einen Akt-Knopf | `.phase-knopf[data-sicher="1"]`, und der bisher aktive Akt steht in `.phase.aktiv` |
| **Interview ist drin** | `#fuss[data-interview]` wechselt 1 → 0 **und** die Warteschlange wird leer | derselbe Beobachter wie in Aufgabe 8 |

**Eine dritte Belohnung („Szene fertig") entfaellt** und geht als offener Wunsch in den
BERICHT: sie braeuchte die Information „gerade ist ein Szenentext eingetroffen", und die
steht nirgends im DOM — ein fertiger Szenentext kommt als gewoehnliche Bot-Blase. Sie am
Text zu erraten waere ein Raten, und Raten ist genau das, was dieses Projekt an anderer
Stelle abgeschafft hat („Datenstand ist nicht Absicht").

**Der Akt-Moment dauert ≤ 600 ms** und laeuft **nicht** bei `prefers-reduced-motion` — dort
bleibt die Aktansage stehen (900 ms, ohne Bewegung). Der Moment ist reine Zutat: er hat
keinen Einfluss darauf, ob der Wechsel stattfindet. W schickt den POST; dieses Skript
haengt sich nur mit einem **zusaetzlichen** Zuhoerer daran.

**Abweichung B:** `_MOMENTE_A` ist ein **Glitch** (Scanlines springen), `_MOMENTE_B` ein
**Vorhang** (faellt von oben, geht wieder hoch). Dasselbe JS, anderer Klassenname —
`MOMENT` kommt aus `skript()`.

- [ ] **Schritt 1: Den Test ergaenzen**

```python
# -- Die Momente -------------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_akt_moment_ist_kurz(name):
    """Hoechstens ~600 ms: laenger ist keine Zutat mehr, sondern eine
    Wartezeit."""
    takt = int(web_gestalt.TOKENS[name]["takt-moment"].removesuffix("ms"))
    assert takt <= 600, takt


def test_a_glitcht_und_b_zieht_einen_vorhang():
    assert "ux-glitch" in web_gestalt.css_rahmen("a")
    assert "ux-vorhang" in web_gestalt.css_rahmen("b")
    assert "ux-vorhang" not in web_gestalt.css_rahmen("a")
    assert "ux-glitch" not in web_gestalt.css_rahmen("b")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_moment_liegt_ueber_allem_und_faengt_nichts_ab(name):
    """Ein Overlay, durch das man nicht tippen kann, waere ein halber
    Ausfall, wenn das Skript haengt."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(r"#ux-vorhang\s*\{([^}]*)\}", css, flags=re.S).group(1)
    assert "pointer-events: none" in block


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_belohnung_ist_klein_und_verschwindet(name):
    css = web_gestalt.css_rahmen(name)
    assert "#ux-belohnung" in css
    assert "#ux-belohnung[hidden]" in css


def test_der_moment_haengt_am_bestaetigenden_druck(js):
    """Karte W schreibt beim ersten Druck die Rueckfrage in den Knopf
    (``data-sicher``); der Moment gehoert zum ZWEITEN."""
    assert "data-sicher" in js or "uxSicher" in js or "dataset.sicher" in js
    assert "phase-knopf" in js


def test_der_moment_faengt_den_klick_nicht_ab(js):
    """Karte W muss denselben Klick weiterhin sehen -- sonst wechselt die
    Phase gar nicht, und der Vorhang faellt vor eine leere Buehne."""
    assert "preventDefault" not in js or "ptt" in js  # nur PTT darf das
    assert "stopPropagation" not in js


def test_bei_reduzierter_bewegung_bleibt_nur_die_ansage(js):
    assert "RUHIG" in js
    assert "ux-ansage" in js


def test_die_belohnungen_kommen_ohne_neuen_serverschluessel_aus(js):
    """Die Karte erlaubt einen additiven read-only-Schluessel im Poll --
    gebraucht wird er nicht. Beide Belohnungen fallen aus dem DOM."""
    assert "ux-belohnung" in js
    assert "fetch(" not in js
    assert "EventSource" not in js


def test_die_belohnungstexte_kommen_aus_den_mikrotexten(js):
    for schluessel in ("belohnung_akt", "belohnung_aufnahme"):
        assert schluessel in js, schluessel
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider -k "moment or belohnung or glitch"
```
Erwartet: FAIL — `#ux-vorhang` gibt es nicht.

- [ ] **Schritt 3: Die zwei Momente im CSS**

```python
#: Der Aktwechsel, Entwurf A: ein Glitch. Scanlines springen, der Aktname
#: steht in Versalien darueber. ``pointer-events: none``, damit ein
#: haengendes Skript die Bedienung nicht blockiert.
_MOMENTE_A = """
#ux-vorhang { position: fixed; inset: 0; z-index: 9; pointer-events: none;
              opacity: 0; background: repeating-linear-gradient(to bottom,
                rgba(110, 247, 165, .30) 0 2px, rgba(5, 7, 10, .92) 2px 5px); }
#ux-vorhang[data-an="1"] { animation: ux-glitch var(--takt-moment) steps(6) 1; }
#ux-ansage { position: fixed; inset: 0; z-index: 10; display: grid;
             place-items: center; pointer-events: none; }
#ux-ansage[hidden] { display: none; }
#ux-ansage b { font-family: var(--schrift-tech); font-size: 1.5rem;
               letter-spacing: .3em; text-transform: uppercase;
               color: var(--signal); background: var(--grund);
               border: 1px solid var(--signal); padding: .8rem 1.2rem; }
"""

#: Der Aktwechsel, Entwurf B: ein Vorhang. Er faellt von oben und geht
#: wieder hoch -- dieselbe Dauer, andere Metapher.
_MOMENTE_B = """
#ux-vorhang { position: fixed; inset: 0; z-index: 9; pointer-events: none;
              transform: translateY(-101%);
              background: repeating-linear-gradient(to right,
                #2a0f14 0 1.1rem, #3a161c 1.1rem 2.2rem); }
#ux-vorhang[data-an="1"] { animation: ux-vorhang var(--takt-moment) ease-in-out 1; }
#ux-ansage { position: fixed; inset: 0; z-index: 10; display: grid;
             place-items: center; pointer-events: none; }
#ux-ansage[hidden] { display: none; }
#ux-ansage b { font-family: var(--schrift-skript); font-size: 1.7rem;
               letter-spacing: .12em; color: var(--signal);
               background: var(--grund);
               border-top: 1px solid var(--signal);
               border-bottom: 1px solid var(--signal); padding: .7rem 1.4rem; }
"""
```

**Die beiden rohen Hexfarben in `_MOMENTE_B`** (`#2a0f14`, `#3a161c`) wuerden
`test_keine_rohe_hexfarbe_ausserhalb_des_tokenblocks` aus Aufgabe 3 rot machen. Zwei
Moeglichkeiten, und **die zweite ist die richtige**: zwei neue Tokens
`--vorhang-1` / `--vorhang-2` in **beiden** Entwuerfen (in A unbenutzt, aber gesetzt —
`test_beide_entwuerfe_tragen_dieselben_tokennamen` verlangt das ohnehin). Also in `TOKENS`
ergaenzen:

```python
        "vorhang-1": "#1b3a2a",   # A: unbenutzt, aber gesetzt
        "vorhang-2": "#0c1116",
```
```python
        "vorhang-1": "#2a0f14",   # B: der Samt des Vorhangs
        "vorhang-2": "#3a161c",
```
und im CSS `var(--vorhang-1)` / `var(--vorhang-2)`. In `FARBTOKENS` aufnehmen; **nicht** in
`KONTRAST` — auf dem Vorhang steht kein Text, er liegt 560 ms lang da.

Die halbdurchsichtigen `rgba(...)` in `_MOMENTE_A` bleiben roh: der Test sucht nach
`#`-Hexwerten, `rgba()` trifft er nicht — und ein Schleier ist kein Farbwert der Marke.

- [ ] **Schritt 4: Die Belohnung im CSS**

```python
#: Die Belohnung: klein, einmal, verschwindet von selbst.
#:
#: ``aria-live="polite"`` statt ``alert``: sie unterbricht nichts. Und
#: sie liegt UEBER dem Fuss, nicht darin -- der Fuss gehoert dem
#: Aufnahmeknopf, und ein Kasten, der ihn verschiebt, waere genau die
#: Art Bewegung, die man beim Tippen nicht will.
_BELOHNUNG = """
#ux-belohnung { position: fixed; left: .75rem; right: .75rem; z-index: 8;
                bottom: calc(var(--tabs-hoehe) + 13.5rem);
                margin: 0 auto; max-width: 44rem;
                background: var(--grund-2); border: 1px solid var(--signal);
                border-left: 4px solid var(--signal);
                border-radius: var(--radius-gross); padding: .6rem .7rem; }
#ux-belohnung[hidden] { display: none; }
#ux-belohnung b { color: var(--signal); letter-spacing: .05em; }
#ux-belohnung p { margin: .2rem 0 0; font-size: .9rem; color: var(--text-leise); }
#ux-belohnung[data-an="1"] { animation: ux-auftritt 260ms ease-out 1; }
"""
```

- [ ] **Schritt 5: Die Momente im JS**

```python
#: Baustein 4: der Aktwechsel und die zwei Belohnungen.
#:
#: **Der Moment haengt sich AN den Klick von Karte W, er ersetzt ihn
#: nicht.** Kein preventDefault, kein stopPropagation -- sonst faellt der
#: Vorhang vor eine leere Buehne, weil der POST nie rausgeht.
#:
#: **Keine Belohnung braucht einen Serverschluessel.** Beide fallen aus
#: dem DOM: der Aktwechsel aus dem bestaetigenden Druck, das fertige
#: Interview aus dem Wechsel von ``data-interview`` samt leerer
#: Warteschlange. Eine dritte ("Szene fertig") ist bewusst NICHT gebaut --
#: sie muesste aus einem Blasentext erraten werden, und Raten ist genau
#: das, was dieses Projekt anderswo abgeschafft hat.
_JS_MOMENT = """
  (function momente() {
    var vorhang = document.createElement('div');
    vorhang.id = 'ux-vorhang';
    vorhang.setAttribute('aria-hidden', 'true');
    var ansage = document.createElement('div');
    ansage.id = 'ux-ansage';
    ansage.setAttribute('aria-hidden', 'true');
    ansage.hidden = true;
    var name = document.createElement('b');
    ansage.appendChild(name);
    var kasten = document.createElement('div');
    kasten.id = 'ux-belohnung';
    kasten.hidden = true;
    kasten.setAttribute('aria-live', 'polite');
    var kopf = document.createElement('b');
    var satz = document.createElement('p');
    kasten.appendChild(kopf);
    kasten.appendChild(satz);
    document.body.appendChild(vorhang);
    document.body.appendChild(ansage);
    document.body.appendChild(kasten);

    var belohnungTakt = null;
    var belohne = function (titel, text) {
      if (!titel) { return; }
      kopf.textContent = titel;
      satz.textContent = text || '';
      kasten.hidden = false;
      kasten.dataset.an = '1';
      if (belohnungTakt) { clearTimeout(belohnungTakt); }
      belohnungTakt = setTimeout(function () {
        kasten.hidden = true;
        kasten.dataset.an = '0';
      }, 4200);
    };

    var moment = function (titel) {
      name.textContent = titel || '';
      if (RUHIG) {
        // Kein Effekt -- die Ansage allein, und die bleibt lesbar stehen.
        ansage.hidden = false;
        setTimeout(function () { ansage.hidden = true; }, 900);
        return;
      }
      vorhang.dataset.an = '1';
      setTimeout(function () { ansage.hidden = false; },
                 MOMENT === 'vorhang' ? Math.round(TAKT_MOMENT * 0.35) : 0);
      setTimeout(function () {
        vorhang.dataset.an = '0';
        ansage.hidden = true;
      }, TAKT_MOMENT + 40);
    };

    // Der ZWEITE Druck auf einen Akt-Knopf: Karte W hat beim ersten die
    // Rueckfrage hineingeschrieben (data-sicher="1").
    document.addEventListener('click', function (ev) {
      var knopf = ev.target.closest ? ev.target.closest('.phase-knopf') : null;
      if (!knopf || knopf.dataset.sicher !== '1') { return; }
      var vorher = document.querySelector('.phase.aktiv .phase-knopf');
      moment(knopf.dataset.bezeichnung || '');
      if (vorher && vorher !== knopf) {
        belohne(TEXTE.belohnung_akt, (TEXTE.belohnung_akt_satz || '')
          .replace('{akt}', (vorher.dataset.bezeichnung || '')));
      }
    });

    // Ein Interview ist eingetroffen: data-interview 1 -> 0, und die
    // Warteschlange ist leer.
    var fuss = el('fuss');
    var warte = el('warteschlange');
    if (!fuss) { return; }
    var lief = fuss.dataset.interview === '1';
    var pruefe = function () {
      var an = fuss.dataset.interview === '1';
      var laden = !!(warte && (warte.textContent || '').trim());
      if (lief && !an && !laden) {
        belohne(TEXTE.belohnung_aufnahme, TEXTE.belohnung_aufnahme_satz);
        lief = false;
      }
      if (an) { lief = true; }
    };
    new MutationObserver(pruefe).observe(
      fuss, { attributes: true, attributeFilter: ['data-interview'] });
    if (warte) {
      new MutationObserver(pruefe).observe(
        warte, { childList: true, characterData: true, subtree: true });
    }
  })();
"""
```

`_BAUSTEINE = _JS_DENKT + _JS_FORTSCHRITT + _JS_AUFNAHME + _JS_MOMENT`.

**`BEWEGT`**: `#ux-vorhang`, `#ux-ansage`, `#ux-belohnung` stehen schon aus Aufgabe 3 drin.
Der Test aus Aufgabe 3 sucht Teilstrings — `#ux-vorhang[data-an="1"]` enthaelt
`#ux-vorhang` **nicht** als exakten Selektor, wohl aber als Teilstring der Selektorzeile.
Der Test vergleicht `selektor in ruhig`, also passt es; **der andere Test**
(`test_reduzierte_bewegung_legt_jeden_bewegten_selektor_stumm`) sammelt
`#ux-vorhang[data-an="1"]` aus dem CSS und sucht ihn woertlich im Block. Deshalb `BEWEGT`
**ergaenzen** um die drei Formen mit Attribut:

```python
    '#ux-vorhang[data-an="1"]',
    '#ux-belohnung[data-an="1"]',
```

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_web_gestalt_js.py tests/test_web_gestalt_css.py \
  tests/test_web_gestalt_tokens.py tests/test_web_gestalt_einhang.py \
  -q -p no:cacheprovider
```
Erwartet: alle passed.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web_gestalt.py tests/test_web_gestalt_js.py
git commit -m "UX: die zwei Momente -- Aktwechsel (Glitch/Vorhang) und zwei Belohnungen

Beide Belohnungen fallen aus dem DOM: kein neuer Schluessel im
Zustands-Poll, kein SQL. Eine dritte ('Szene fertig') ist bewusst nicht
gebaut -- sie muesste aus einem Blasentext erraten werden.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 10: Probenansicht und Leitfaden — und der Druck bleibt hell

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_SKRIPT_A`, `_SKRIPT_B`)
- Aendern: `interview_theater/web.py` (**zwei Zeilen**: `textbuch_html`, `leitfaden_html`)
- Aendern: `tests/test_web_gestalt_einhang.py` (die beiden `xfail`-Marken fallen weg)
- Aendern: `tests/test_web_gestalt_css.py` (Abschnitte „Druck" und „Skript")

**Die zwei Zeilen in `web.py`.** In `textbuch_html` (heute `_CSS_TEXTBUCH`,
`skript=_TEXTBUCH_JS`):

```python
    from interview_theater import web_gestalt   # lokal, wie web_chat/web_vereint
    ...
    return _seite(
        titel,
        # Gestaltung zuletzt (Karte UX). Die Probenansicht ist eine eigene
        # Seite, also ungescopt -- es gibt hier kein Panel.
        _CSS_TEXTBUCH + web_gestalt.css_rahmen() + web_gestalt.css_textbuch(),
        koerper,
        nachladen=False,
        skript=_TEXTBUCH_JS,
    )
```

In `leitfaden_html` genauso mit `_CSS_LEITFADEN + web_gestalt.css_rahmen()`.

**`web_gestalt.skript()` kommt hier NICHT dazu.** Die Probenansicht laedt nicht nach, hat
keinen Chat, keinen Aufnahmeknopf und keine Aktleiste — jeder Baustein wuerde sein Element
nicht finden und sauber zurueckkehren, aber ein Skript ohne Aufgabe auf einer Seite, die
jemand in der Probe in der Hand haelt, ist unnoetiges Gewicht. Der Leitfaden erst recht:
er ist **rein lesend, ohne Nachladen** (AGENTS.md, „Der Leitfaden hat eine eigene Seite").

**Der Druck ist die Falle dieser Aufgabe.** `_CSS_TEXTBUCH` setzt seit dem 06.09.2026 ein
helles Manuskript (`@media print`). Gestaltung steht **danach** im `<style>` und faerbt
`body` dunkel — ohne den `@media print`-Block aus Aufgabe 3 kaeme ein schwarzes Blatt aus
dem Drucker. Der Block ist da; diese Aufgabe **prueft** ihn am ausgelieferten HTML.

**Abweichung B im Skriptsatz:** A setzt den Sprechernamen **in der Zeile** (Monospace,
Signalfarbe, danach die Replik); B setzt ihn **auf eine eigene Zeile** darueber — die Form
eines gedruckten Textbuchs. Beide lassen die Regieanweisung kursiv und gedaempft, und
beide lassen den Rollenfilter aus `_TEXTBUCH_JS` unberuehrt.

- [ ] **Schritt 1: Den Test ergaenzen**

An `tests/test_web_gestalt_css.py` anhaengen:

```python
# -- 5. Der Druck bleibt ein helles Manuskript ------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_druckblock_macht_die_seite_hell(name):
    """Gestaltung steht im ``<style>`` NACH ``_CSS_TEXTBUCH`` und faerbt
    ``body`` dunkel -- ohne diesen Block kaeme ein schwarzes Blatt aus dem
    Drucker."""
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S)
    assert block, "kein @media print"
    assert "background: #fff !important" in block.group(1)
    assert "color: #000 !important" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_im_druck_faellt_jede_bedienung_weg(name):
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S).group(1)
    for weg in (".tabs", ".roadmap", ".fuss", "#ux-belohnung", "#ux-vorhang"):
        assert weg in block, weg


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_sprecher_ist_im_druck_schwarz_und_fett(name):
    """Ein Manuskript, kein Bildschirmtext: Signalfarbe auf Papier ist
    hellgrau."""
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S).group(1)
    assert ".sprecher" in block
    assert "font-weight: 700" in block


# -- 6. Das Skript als Manuskript -------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_szenentext_ist_in_der_skriptschrift_gesetzt(name):
    css = web_gestalt.css_textbuch(name)
    assert "var(--schrift-skript)" in css
    assert ".replik" in css
    assert ".regie" in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_regieanweisung_ist_kursiv_und_gedaempft(name):
    css = web_gestalt.css_textbuch(name)
    block = re.search(r"\.regie\s*\{([^}]*)\}", css, flags=re.S)
    assert block and "italic" in block.group(1)
    assert "var(--text-leise)" in block.group(1)


def test_a_setzt_den_sprecher_in_die_zeile_und_b_darueber():
    """Die vierte benannte Komponenten-Abweichung."""
    assert "display: block" in re.search(
        r"\.sprecher\s*\{([^}]*)\}", web_gestalt.css_textbuch("b"),
        flags=re.S).group(1)
    assert "display: block" not in re.search(
        r"\.sprecher\s*\{([^}]*)\}", web_gestalt.css_textbuch("a"),
        flags=re.S).group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_rollenfilter_bleibt_unangetastet(name):
    """``body[data-figur] .replik`` gehoert ``_CSS_TEXTBUCH``; die
    Gestaltung faerbt, sie filtert nicht."""
    assert "data-figur" not in web_gestalt.css_textbuch(name)
```

Und in `tests/test_web_gestalt_einhang.py` die `xfail`-Marken aus Aufgabe 4 **entfernen**,
sodass die Fixture wieder schlicht lautet:

```python
@pytest.fixture(params=["", "/textbuch", "/leitfaden"])
def seite(request, dienst):
    basis, token = dienst
    return _hole(f"{basis}/g/{token}{request.param}")
```

plus zwei neue Tests in derselben Datei:

```python
def test_die_probenansicht_traegt_die_tokens_und_den_druckblock(dienst):
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}/textbuch")
    assert "--schrift-skript" in html
    # Der Druckblock der Gestaltung steht NACH dem von _CSS_TEXTBUCH.
    assert html.rindex("background: #fff !important") > html.index("@media print")


def test_die_probenansicht_traegt_kein_effektskript(dienst):
    """Sie laedt nicht nach, hat keinen Chat, keinen Aufnahmeknopf und
    keine Aktleiste -- ein Skript ohne Aufgabe ist Gewicht in der Hand
    einer Person, die gerade eine Rolle liest."""
    basis, token = dienst
    html = _hole(f"{basis}/g/{token}/textbuch")
    assert "ux-rec-zeile" not in html
    assert "ux-belohnung" not in html
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_css.py tests/test_web_gestalt_einhang.py \
  -q -p no:cacheprovider
```
Erwartet: FAIL — `css_textbuch` ist leer, `web.textbuch_html` haengt nichts ein.

- [ ] **Schritt 3: Das Skript-CSS**

```python
#: Das Textbuch, Entwurf A: Terminal-Kopf, Manuskript-Koerper. Der
#: Sprechername steht IN der Zeile (Monospace, Signalfarbe), die Replik
#: daneben in der Skriptschrift.
_SKRIPT_A = """
.szenenkopf { font-family: var(--schrift-tech); font-size: .8rem;
              letter-spacing: .12em; text-transform: uppercase;
              color: var(--text-leise); border-bottom: 1px solid var(--linie);
              padding-bottom: .25rem; }
.angaben, .besetzung { font-family: var(--schrift-tech); font-size: .8rem;
                       color: var(--text-leise); opacity: 1; }
.text, .probe-szene { font-family: var(--schrift-skript); font-size: 1.12rem;
                      line-height: 1.55; }
.replik { margin: 0 0 .55rem; }
.sprecher { font-family: var(--schrift-tech); font-size: .92rem;
            letter-spacing: .08em; color: var(--signal); font-weight: 400; }
.regie { font-style: italic; color: var(--text-leise); }
.regie-zeile { font-style: italic; color: var(--text-leise); margin: 0 0 .7rem; }
.prosa { margin: 0 0 .6rem; }
.rollen button, .leiste button { min-height: var(--tippflaeche);
    padding: .35rem .7rem; border: 1px solid var(--rand); border-radius: 1.2rem;
    background: var(--grund-2); color: var(--text); font-size: .85rem; }
.leiste button[aria-pressed="true"] { background: var(--signal);
    color: var(--auf-signal); border-color: var(--signal); font-weight: 700; }
"""

#: Das Textbuch, Entwurf B: Manuskript. Der Sprechername steht auf einer
#: EIGENEN Zeile darueber -- die Form eines gedruckten Textbuchs.
_SKRIPT_B = """
.szenenkopf { font-family: var(--schrift-skript); font-size: 1.25rem;
              color: var(--signal); border-bottom: 1px solid var(--linie);
              padding-bottom: .3rem; }
.angaben, .besetzung { font-family: var(--schrift-tech); font-size: .78rem;
                       color: var(--text-leise); opacity: 1; }
.text, .probe-szene { font-family: var(--schrift-skript); font-size: 1.15rem;
                      line-height: 1.62; }
.replik { margin: 0 0 .6rem; }
.sprecher { display: block; font-family: var(--schrift-tech); font-size: .88rem;
            letter-spacing: .1em; color: var(--signal); font-weight: 400; }
.regie { font-style: italic; color: var(--text-leise); }
.regie-zeile { font-style: italic; color: var(--text-leise); margin: 0 0 .8rem; }
.prosa { margin: 0 0 .65rem; }
.rollen button, .leiste button { min-height: var(--tippflaeche);
    padding: .35rem .8rem; border: 1px solid var(--rand); border-radius: 1.4rem;
    background: var(--grund-2); color: var(--text);
    font-family: var(--schrift-tech); font-size: .82rem; letter-spacing: .06em; }
.leiste button[aria-pressed="true"] { background: var(--signal);
    color: var(--auf-signal); border-color: var(--signal); font-weight: 700; }
"""
```

- [ ] **Schritt 4: Die zwei Zeilen in `web.py`**

Genau die Ersetzung aus dem Kopf dieser Aufgabe.

```
git diff --stat interview_theater/web.py
```
Erwartet: **eine** Datei, hoechstens 6 geaenderte Zeilen.

- [ ] **Schritt 5: Lauf, alles gruen — und diesmal ohne `-k`**

```
$PY -m pytest tests/test_web_gestalt_einhang.py -q -p no:cacheprovider
```
Erwartet: alle passed — **auch** die `/textbuch`- und `/leitfaden`-Faelle. Steht dort noch
ein `xfail`, ist Schritt 1 nicht vollstaendig ausgefuehrt.

```
$PY -m pytest tests/test_web_textbuch.py tests/test_web.py \
  tests/test_web_fassungen.py tests/test_web_szenenuebersicht.py \
  tests/test_vorspann_web.py tests/test_festlegung_web.py \
  tests/test_web_edit.py tests/test_web_daten.py -q -p no:cacheprovider
```
Erwartet: alle passed — das sind die bestehenden Web-Grenzen-Tests (Vorgabe 6f).

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 6: Commit**

```bash
git add interview_theater/web_gestalt.py interview_theater/web.py \
        tests/test_web_gestalt_css.py tests/test_web_gestalt_einhang.py
git commit -m "UX: Probenansicht und Leitfaden gestaltet, der Ausdruck bleibt hell

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 11: Englische Mikrotexte (A1) und `pruefe_profil dortmund-2026`

**Dateien:**
- Aendern: `interview_theater/web_gestalt.py` (`_TEXT_*`, `_mikrotexte`)
- Aendern: `interview_theater/sprachen/en/texte.toml` (Abschnitt `["web_gestalt"]`)
- Aendern: `tests/test_sprache_texte.py` (`UMGESTELLT`, `ALLE_MODULE`, `BLEIBT_DEUTSCH`)
- Aendern: `tests/test_web_gestalt_js.py` (Abschnitt „Mikrotexte")

**Die Bauart ist die des ganzen Repos** (A1): die deutsche Fassung steht als modulweite
`_TEXT_*`-Konstante und **ist** die deutsche Tabelle; die englische steht in
`sprachen/en/texte.toml`; gelesen wird zur Aufrufzeit ueber `T`. In Padua laeuft der
Webdienst mit dem englischen Profil, in Dortmund mit dem deutschen — **dasselbe Look, zwei
Sprachen**.

**Humor gehoert in die englische Fassung, nicht in die deutsche.** „Mic is hot." ist ein
Studiowitz und traegt auf Englisch; „Das Mikrofon ist heiss." waere in Dortmund Denglisch.
Die deutschen Konstanten sind sachlich, die englischen duerfen zwinkern — das ist kein
Widerspruch, sondern der Grund, warum es zwei Tabellen gibt.

**Der Bot-Text bleibt unangetastet.** Kein einziger dieser Texte geht in einen Prompt, in
eine Chatnachricht oder in `knoepfe/texte.py`. Es sind Beschriftungen der Oberflaeche.
**E8 gilt auch hier**: kein Vorname, nirgends.

- [ ] **Schritt 1: Den Test ergaenzen**

An `tests/test_web_gestalt_js.py`:

```python
# -- Mikrotexte --------------------------------------------------------------


def test_jeder_schluessel_im_skript_hat_einen_text():
    """Ein ``TEXTE.foo``, das es nicht gibt, ist im Browser ``undefined``
    -- und in der Oberflaeche eine leere Zeile, die niemand erklaeren
    kann."""
    quelle = web_gestalt._GESTALT_JS + web_gestalt._BAUSTEINE
    benutzt = set(re.findall(r"TEXTE\.([a-z_]+)", quelle))
    benutzt |= set(re.findall(r"TEXTE\['([a-z_]+)'\]", quelle))
    vorhanden = set(web_gestalt._mikrotexte())
    assert not (benutzt - vorhanden), benutzt - vorhanden
    # Die vier rec_-Schluessel werden dynamisch zusammengesetzt
    # (TEXTE['rec_' + neu]) und stehen deshalb nicht im Regex.
    for zustand in ("ruht", "startet", "laeuft", "laedt"):
        assert f"rec_{zustand}" in vorhanden, zustand


def test_die_mikrotexte_kommen_aus_den_modulkonstanten():
    """Sonst laufen sie nicht ueber ``T`` (A1) und stehen in Padua
    deutsch da -- genau Befund 2 an Karte A2."""
    import inspect
    assert "T._TEXT_" in inspect.getsource(web_gestalt._mikrotexte)


def test_kein_vorname_in_den_mikrotexten():
    """E8 gilt ueberall, auch in einer Beschriftung."""
    zusammen = " ".join(web_gestalt._mikrotexte().values())
    for verboten in ("Meryem", "Erhan", "Leyla", "Birk", "Mira"):
        assert verboten not in zusammen, verboten


def test_die_platzhalter_stehen_in_geschweiften_klammern():
    """Das Skript ersetzt sie mit ``String.replace`` -- eine andere Form
    liefe ins Leere und stuende woertlich in der Oberflaeche."""
    texte = web_gestalt._mikrotexte()
    assert "{akt}" in texte["belohnung_akt_satz"]
    assert "{nummer}" in texte["akt_kopf"]
    assert "{gesamt}" in texte["akt_kopf"]
```

- [ ] **Schritt 2: Lauf, er muss scheitern**

```
$PY -m pytest tests/test_web_gestalt_js.py -q -p no:cacheprovider -k mikrotext
```
Erwartet: FAIL — `_mikrotexte()` gibt `{}` zurueck.

- [ ] **Schritt 3: Die deutschen Konstanten**

In `web_gestalt.py`, **ueber** `T = sprache.Texte(__name__)`:

```python
# -- Mikrotexte der Oberflaeche ---------------------------------------------
#
# Die deutsche Fassung steht hier und IST die deutsche Tabelle (A1); die
# englische steht in ``sprachen/en/texte.toml``. Keiner dieser Texte geht
# in einen Prompt oder in eine Chatnachricht -- es sind Beschriftungen.
#
# Sachlich auf Deutsch, augenzwinkernd auf Englisch: "Mic is hot." ist ein
# Studiowitz und traegt dort; "Das Mikrofon ist heiss." waere in Dortmund
# Denglisch. Genau dafuer gibt es zwei Tabellen.

#: Die vier Zustaende des Aufnahmeknopfes -- die zweite Zeile NEBEN dem
#: Knopf. Der Knopftext selbst gehoert Karte A2.
_TEXT_REC_RUHT = "Einmal tippen zum Starten, einmal zum Beenden"
_TEXT_REC_STARTET = "Das Mikrofon wird freigegeben …"
_TEXT_REC_LAEUFT = "Aufnahme laeuft."
_TEXT_REC_LAEDT = "Die letzten Stuecke gehen noch raus."

#: Die Akt-Marke in der zugeklappten Uebersicht. Sie steht VOR dem Text
#: von Karte W ("Phase 3 von 7 · Interviews — 1/3"), nicht statt ihm.
_TEXT_AKT_KOPF = "Akt {nummer}/{gesamt}"

#: Die zwei Belohnungen. Klein, einmal, und sie verschwinden von selbst.
_TEXT_BELOHNUNG_AKT = "Akt abgeschlossen."
_TEXT_BELOHNUNG_AKT_SATZ = "{akt} steht. Weiter."
_TEXT_BELOHNUNG_AUFNAHME = "Interview ist drin."
_TEXT_BELOHNUNG_AUFNAHME_SATZ = "Aufgenommen und auf dem Weg zur Auswertung."


def _mikrotexte() -> dict[str, str]:
    """Die Kurztexte, die das Skript in den DOM schreibt.

    Sie gehen als JSON ins Skript, statt als Literal darin zu stehen --
    nur so laufen sie ueber ``T`` (A1) und sind uebersetzbar. Ein Literal
    im JS waere in Padua Deutsch; genau das ist Befund 2 an Karte A2.

    Gelesen wird zur AUFRUFZEIT: der Webdienst laeuft einmal fuer alle
    Gruppen, und ``sprache.code()`` haengt am aktiven Profil."""
    return {
        "rec_ruht": T._TEXT_REC_RUHT,
        "rec_startet": T._TEXT_REC_STARTET,
        "rec_laeuft": T._TEXT_REC_LAEUFT,
        "rec_laedt": T._TEXT_REC_LAEDT,
        "akt_kopf": T._TEXT_AKT_KOPF,
        "belohnung_akt": T._TEXT_BELOHNUNG_AKT,
        "belohnung_akt_satz": T._TEXT_BELOHNUNG_AKT_SATZ,
        "belohnung_aufnahme": T._TEXT_BELOHNUNG_AUFNAHME,
        "belohnung_aufnahme_satz": T._TEXT_BELOHNUNG_AUFNAHME_SATZ,
    }
```

- [ ] **Schritt 4: Die englische Tabelle**

Ans Ende von `interview_theater/sprachen/en/texte.toml`:

```toml
["web_gestalt"]
# Die Beschriftungen der Oberflaeche (Karte Padua UX). Kein Bot-Text, kein
# Prompt -- hier darf es zwinkern. Platzhalter wie im Deutschen.
_TEXT_REC_RUHT = "Tap once to start, tap again to stop"
_TEXT_REC_STARTET = "Warming up the mic …"
_TEXT_REC_LAEUFT = "Mic is hot."
_TEXT_REC_LAEDT = "Hold on — the tape is still walking."
_TEXT_AKT_KOPF = "Act {nummer}/{gesamt}"
_TEXT_BELOHNUNG_AKT = "Act closed."
_TEXT_BELOHNUNG_AKT_SATZ = "{akt} is in the can. Curtain up on the next one."
_TEXT_BELOHNUNG_AUFNAHME = "Interview is in."
_TEXT_BELOHNUNG_AUFNAHME_SATZ = "Recorded and on its way to the analysis."
```

- [ ] **Schritt 5: `tests/test_sprache_texte.py` nachziehen**

`"web_gestalt"` in **beide** Mengen (`UMGESTELLT` **und** `ALLE_MODULE`) — sie muessen
gleich bleiben. Dazu in `BLEIBT_DEUTSCH` die Konstanten, die kein Nutzertext sind:

```python
    # Karte Padua UX: CSS und JavaScript, nur Kommentare deutsch. Die
    # Mikrotexte laufen ueber T (siehe web_gestalt._mikrotexte).
    "web_gestalt._BASIS": "CSS, nur Kommentare deutsch",
    "web_gestalt._KEYFRAMES_CSS": "CSS, nur Kommentare deutsch",
    "web_gestalt._TABS_A": "CSS, nur Kommentare deutsch",
    "web_gestalt._TABS_B": "CSS, nur Kommentare deutsch",
    "web_gestalt._ROADMAP": "CSS, nur Kommentare deutsch",
    "web_gestalt._MOMENTE_A": "CSS, nur Kommentare deutsch",
    "web_gestalt._MOMENTE_B": "CSS, nur Kommentare deutsch",
    "web_gestalt._BELOHNUNG": "CSS, nur Kommentare deutsch",
    "web_gestalt._CHAT_A": "CSS, nur Kommentare deutsch",
    "web_gestalt._CHAT_B": "CSS, nur Kommentare deutsch",
    "web_gestalt._STAND": "CSS, nur Kommentare deutsch",
    "web_gestalt._SKRIPT_A": "CSS, nur Kommentare deutsch",
    "web_gestalt._SKRIPT_B": "CSS, nur Kommentare deutsch",
    "web_gestalt._GESTALT_JS": "JavaScript, Texte kommen aus TEXTE (_mikrotexte)",
    "web_gestalt._BAUSTEINE": "JavaScript, Texte kommen aus TEXTE",
    "web_gestalt._JS_DENKT": "JavaScript, nur Kommentare deutsch",
    "web_gestalt._JS_FORTSCHRITT": "JavaScript, nur Kommentare deutsch",
    "web_gestalt._JS_AUFNAHME": "JavaScript, nur Kommentare deutsch",
    "web_gestalt._JS_MOMENT": "JavaScript, nur Kommentare deutsch",
```

**Meldet der Test weitere Konstanten** (`TOKENS`, `KONTRAST`, `BEWEGT`, `KEYFRAMES`,
`FARBTOKENS`, `UMGEBUNG`, `ENTWUERFE`, `VORGABE_ENTWURF`), werden auch sie mit einem
sachlichen Grund eingetragen — z. B. `"web_gestalt.TOKENS": "Farbwerte und Masse, kein
Nutzertext"`. **Nicht** den Test abschwaechen.

- [ ] **Schritt 6: Lauf, alles gruen**

```
$PY -m pytest tests/test_sprache_texte.py tests/test_web_gestalt_js.py \
  -q -p no:cacheprovider
```
Erwartet: alle passed.

Der Beweis, dass beide Sprachen ankommen (der Profilname kommt aus `ls workshop/`; er
heisst zum Zeitpunkt dieses Plans `padua-2026`, das ist **ANNAHME 8**):

```
IT_WORKSHOP=padua-2026 $PY -c "
from interview_theater import web_gestalt
print(web_gestalt._mikrotexte()['rec_laeuft'])"
```
Erwartet: `Mic is hot.`

```
$PY -c "
from interview_theater import web_gestalt
print(web_gestalt._mikrotexte()['rec_laeuft'])"
```
Erwartet: `Aufnahme laeuft.`

Scheitert der erste Aufruf, weil das Profil anders heisst, wird der richtige Name benutzt;
gibt es gar kein englisches Profil, ist das ein **Befund** fuer den BERICHT und **kein**
Grund, die Texte deutsch zu lassen.

Das Dortmunder Profil muss unveraendert laufen:

```
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: Exit 0, keine Fehlerzeile.

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/web_gestalt.py interview_theater/sprachen/en/texte.toml \
        tests/test_sprache_texte.py tests/test_web_gestalt_js.py
git commit -m "UX: die Mikrotexte englisch (A1), dasselbe Look in beiden Profilen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 12: Browserlauf und Abnahme-Screenshots aus der Demo-Datenbank

**Dateien:**
- Neu: `tests/e2e/test_web_gestalt_e2e.py`
- Neu: `docs/ux-padua/abnahme-*.png` (committet)
- Aendern: `tests/e2e/README.md` (ein Absatz)

**Laeuft nicht im normalen `pytest`-Lauf mit** (`pytest.importorskip`), wie
`tests/e2e/test_web_edit_e2e.py`. Gefahren wird mit dem Wegwerf-venv
`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python`, **eigener** Wegwerf-Datenbank
`/tmp/it-ux.db` und **eigenem** Port `127.0.0.1:8023` — zwei e2e-Dateien, die sich einen
Port teilen, blockieren einander (ANNAHME 7).

**Was hier geprueft wird und sonst nirgends:** ob die vier Aufnahmezustaende im echten
Chromium wirklich umschalten, ob Push-to-Talk beim Halten anders aussieht, ob der
Akt-Moment kommt und wieder geht, und ob bei `reduced_motion="reduce"` wirklich **nichts**
laeuft (`getAnimations()` leer).

**Fake-Mikrofon:** `--use-fake-device-for-media-stream` und
`--use-fake-ui-for-media-stream` beim `launch` — sonst blockiert die Freigabe, und der
Zustand bleibt ewig auf `startet`.

**Nur erfundenes Material.** Die Demo-Gruppe wird aus `simulation/interviews/set1` gebaut
(dieselbe Quelle wie die Entwuerfe), **nie** aus `betrieb/`. Die Screenshots gehen ins
Repository und duerfen deshalb nichts Echtes zeigen.

- [ ] **Schritt 1: Den Browsertest schreiben**

`tests/e2e/test_web_gestalt_e2e.py`:

```python
"""Die Gestaltung im echten Chromium -- und die Abnahme-Screenshots.

Was ``tests/test_web_gestalt_*.py`` NICHT pruefen kann: ob die vier
Zustaende des Aufnahmeknopfes wirklich umschalten, ob Push-to-Talk beim
Halten anders aussieht, ob der Akt-Moment kommt und wieder geht, und ob
bei reduzierter Bewegung wirklich nichts laeuft.

**Nur erfundenes Material** (``simulation/interviews/set1``), nie
``betrieb/``. Die Screenshots gehen ins Repository -- sie sind der Beleg
der Abnahme und duerfen nichts Echtes zeigen.
"""

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-ux.db"
BIND = "127.0.0.1:8023"
SCHUSS = WURZEL / "docs" / "ux-padua"
CHAT = 7_000_000_000_007
HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}

#: Das Fake-Mikrofon: ohne diese beiden Schalter blockiert die Freigabe,
#: und der Knopf bleibt ewig auf "startet".
MIKROFON = ["--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream"]


def _baue_datenbank(pfad: str) -> str:
    """Eine Demo-Gruppe mit erfundenem Material aus simulation/."""
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    if os.path.exists(pfad):
        os.remove(pfad)
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe",
                            "Koffer, Bahnhof, Untermiete, Tomatensamen")
    repo.setze_arbeitsstand(conn, CHAT, "fragen",
                            "Was hast du mitgebracht?\nWas hast du nicht ausgepackt?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung",
                            "Wir sind vom Theater und sammeln Geschichten.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhofshalle, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte",
                            "Zwei kommen an und bleiben laenger als geplant.")
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_figur(conn, CHAT, "Meryem", "kam mit einem Koffer")
    repo.setze_figur(conn, CHAT, "Erhan", "holte sie am Bahnhof ab")
    nummer = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis")
    repo.aktualisiere_szene(
        conn, nummer, form="dialog", ort="Bahnhofshalle",
        volltext=("(Nacht. Die Halle ist zu hell.)\n"
                  "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\n"
                  "ERHAN: Du kannst ihn jetzt auspacken.\n"
                  "CHOR: Keiner guckt. Keiner guckt."))
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Wir sind zurueck vom Markt.")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Interview 1 ist ausgewertet. Drei Kernthemen.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


@pytest.fixture(scope="module")
def dienst():
    token = _baue_datenbank(DB_PFAD)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="")
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://{BIND}", token
    prozess.terminate()
    prozess.wait(timeout=10)


def _oeffne(browser, basis, token, viewport=HANDY, **kw):
    seite = browser.new_page(viewport=viewport, permissions=["microphone"], **kw)
    seite.goto(f"{basis}/g/{token}")
    seite.wait_for_selector("#interview")
    return seite


# -- Die vier Zustaende des Aufnahmeknopfes ---------------------------------


def test_der_aufnahmeknopf_durchlaeuft_seine_zustaende(dienst):
    """Der Kern der Karte. Dortmund Tag 1: ein Knopf 14x in 93 s
    gedrueckt, weil der Zustand nicht erkennbar war."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        knopf = seite.locator("#interview")
        assert knopf.get_attribute("data-ux-zustand") == "ruht"

        knopf.click()
        seite.wait_for_function(
            "() => document.getElementById('interview')"
            ".dataset.uxZustand !== 'ruht'", timeout=10_000)
        # 'startet' oder schon 'laeuft' -- beides ist richtig, je nachdem
        # wie schnell der Poll den Modus meldet.
        assert knopf.get_attribute("data-ux-zustand") in ("startet", "laeuft")

        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        assert seite.locator("#uhr").is_visible()
        browser.close()


def test_jeder_zustand_steht_auch_im_text(dienst):
    """Farbe allein traegt keinen Zustand -- der Probenraum ist schlecht
    beleuchtet."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        ruht = seite.locator("#ux-rec-zeile").inner_text().strip()
        assert ruht
        seite.locator("#interview").click()
        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        laeuft = seite.locator("#ux-rec-zeile").inner_text().strip()
        assert laeuft and laeuft != ruht
        browser.close()


def test_der_uebergang_ist_als_busy_markiert(dienst):
    """Er wird NICHT gesperrt -- das ist ein Befund an Karte A2 (Plan-Kopf,
    Befund 1). Sichtbar ist er trotzdem."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.locator("#interview").click()
        seite.wait_for_function(
            "() => ['startet','laeuft'].indexOf("
            "document.getElementById('interview').dataset.uxZustand) >= 0",
            timeout=10_000)
        if seite.locator("#interview").get_attribute("data-ux-zustand") == "startet":
            assert seite.locator("#interview").get_attribute("aria-busy") == "true"
        browser.close()


# -- Push-to-Talk -----------------------------------------------------------


def test_push_to_talk_sieht_beim_halten_anders_aus(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        ptt = seite.locator("#ptt")
        kasten = ptt.bounding_box()
        assert kasten["width"] >= 44 and kasten["height"] >= 44
        seite.mouse.move(kasten["x"] + kasten["width"] / 2,
                         kasten["y"] + kasten["height"] / 2)
        seite.mouse.down()
        seite.wait_for_timeout(700)
        assert ptt.get_attribute("data-haelt") == "1"
        seite.mouse.up()
        seite.wait_for_timeout(300)
        assert ptt.get_attribute("data-haelt") != "1"
        browser.close()


def test_die_zwei_mikrofone_sind_verschieden_gross_und_woanders(dienst):
    """Vier Achsen; zwei davon lassen sich messen."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        rec = seite.locator("#interview").bounding_box()
        ptt = seite.locator("#ptt").bounding_box()
        assert rec["height"] >= ptt["height"] * 1.4
        assert abs(rec["y"] - ptt["y"]) > 20
        browser.close()


# -- Der Akt-Moment ---------------------------------------------------------


def test_der_aktwechsel_zeigt_seinen_moment_und_raeumt_ihn_weg(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="4"]')
        knopf.click()          # erster Druck: die Rueckfrage
        assert knopf.get_attribute("data-sicher") == "1"
        knopf.click()          # zweiter Druck: der Moment
        seite.wait_for_selector("#ux-ansage:not([hidden])", timeout=3000)
        seite.wait_for_selector("#ux-ansage[hidden]", timeout=3000)
        browser.close()


def test_eine_belohnung_erscheint_und_verschwindet_wieder(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="5"]')
        knopf.click()
        knopf.click()
        seite.wait_for_selector("#ux-belohnung:not([hidden])", timeout=3000)
        seite.wait_for_selector("#ux-belohnung[hidden]", timeout=8000)
        browser.close()


# -- Reduzierte Bewegung ----------------------------------------------------


def test_bei_reduzierter_bewegung_laeuft_keine_animation(dienst):
    """``getAnimations()`` leer -- das ist der Test, den die Karte
    verlangt, und er misst mehr als ein Blick ins CSS."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token, reduced_motion="reduce")
        seite.locator("#interview").click()
        seite.wait_for_timeout(1500)
        laufend = seite.evaluate(
            "() => document.getAnimations()"
            ".filter(a => a.playState === 'running').length")
        assert laufend == 0, laufend
        browser.close()


def test_bei_reduzierter_bewegung_bleibt_alles_bedienbar(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token, reduced_motion="reduce")
        seite.click('.tabs button[data-tab="textbuch"]')
        seite.wait_for_selector("#tab-textbuch:not([hidden])")
        seite.click('.tabs button[data-tab="chat"]')
        seite.wait_for_selector("#tab-chat:not([hidden])")
        seite.locator("#interview").click()
        seite.wait_for_function(
            "() => document.getElementById('interview')"
            ".dataset.uxZustand !== 'ruht'", timeout=10_000)
        browser.close()


def test_der_tabwechsel_verliert_die_halb_getippte_nachricht_nicht(dienst):
    """Karte W garantiert das ueber ``hidden``; die Gestaltung darf es
    nicht kaputtmachen (etwa mit ``display: none`` auf dem falschen
    Knoten)."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.fill("#eingabe", "Das tippe ich gerade")
        seite.click('.tabs button[data-tab="stand"]')
        seite.wait_for_selector("#tab-stand:not([hidden])")
        seite.click('.tabs button[data-tab="chat"]')
        seite.wait_for_selector("#tab-chat:not([hidden])")
        assert seite.input_value("#eingabe") == "Das tippe ich gerade"
        browser.close()


# -- Die Abnahme-Screenshots ------------------------------------------------


def test_abnahme_screenshots(dienst):
    """Vier Motive, zwei Groessen -- die Abnahme der Karte.

    Sie liegen in ``docs/ux-padua/`` neben den Entwuerfen, damit man
    Entwurf und Ergebnis nebeneinander sehen kann."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        for name, viewport in (("handy", HANDY), ("laptop", LAPTOP)):
            seite = _oeffne(browser, basis, token, viewport=viewport)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-chat.png"))

            seite.locator("#interview").click()
            seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                    timeout=20_000)
            seite.wait_for_timeout(1200)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-aufnahme.png"))
            seite.locator("#interview").click()
            seite.wait_for_timeout(500)

            seite.eval_on_selector("#roadmap", "el => el.open = true")
            seite.wait_for_timeout(200)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-akte.png"))
            seite.eval_on_selector("#roadmap", "el => el.open = false")

            seite.click('.tabs button[data-tab="textbuch"]')
            seite.wait_for_selector("#tab-textbuch:not([hidden])")
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-textbuch.png"))
            seite.close()

        # Die Probenansicht als eigene Seite -- sie wird gedruckt.
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}/textbuch")
        seite.wait_for_selector(".probe-szene")
        seite.screenshot(path=str(SCHUSS / "abnahme-handy-probenansicht.png"))
        browser.close()

    for datei in SCHUSS.glob("abnahme-*.png"):
        assert datei.stat().st_size > 5_000, datei
```

- [ ] **Schritt 2: Der Lauf**

```
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \
  tests/e2e/test_web_gestalt_e2e.py -q
```
Erwartet: alle passed, und in `docs/ux-padua/` liegen neun `abnahme-*.png`.

- [ ] **Schritt 3: Jeden Screenshot ANSEHEN**

**Das ist ein Arbeitsschritt, kein Haekchen.** Jedes der neun Bilder wird geoeffnet und
gegen diese fuenf Kriterien gelesen:

| Kriterium | Erfuellt, wenn … |
|---|---|
| **Lesbarkeit** | der Fliesstext der Blasen ohne Zoom lesbar ist (≥ 16 px) und kein Text auf seinem Grund verschwimmt |
| **Der Aufnahmeknopf** | er das groesste Element des Fusses ist und sein Zustand **im Bild lesbar** steht — nicht nur an der Farbe erkennbar |
| **Nichts ist abgeschnitten** | keine Blase, kein Knopf, keine Zeile wird von einer festen Leiste ueberdeckt; die unterste Nachricht ist ganz sichtbar |
| **Nichts ueberlappt** | Fuss, Tableiste, Belohnung und Aktleiste liegen nebeneinander, nicht uebereinander (am Entwurf gemessen: genau hier lagen zwei Fehler, `z-index` und `max-height` der Aktliste) |
| **Kein Echtmaterial** | nur die erfundene Gruppe „Die Ankommenden" mit dem Material aus `simulation/` |

Was nicht stimmt, wird **behoben und neu fotografiert**, bevor Schritt 4 kommt. Die
Nachbesserung geht ins CSS des Moduls, nicht in den Test.

- [ ] **Schritt 4: `tests/e2e/README.md` ergaenzen**

Ein Absatz nach dem bestehenden zur Probenansicht:

```markdown
Seit dem 01.10.2026 gehoert die **Gestaltung** dazu
(`test_web_gestalt_e2e.py`, Karte Padua UX): die vier Zustaende des
Aufnahmeknopfes, Push-to-Talk beim Halten, der Akt-Moment und
`prefers-reduced-motion`. Sie braucht ein **Fake-Mikrofon**
(`--use-fake-device-for-media-stream`, `--use-fake-ui-for-media-stream`) —
ohne das blockiert die Freigabe, und der Knopf bleibt auf „startet"
stehen. Eigene Wegwerf-Datenbank (`/tmp/it-ux.db`) und eigener Port
(`127.0.0.1:8023`): zwei e2e-Dateien, die sich einen Port teilen,
blockieren einander. Die Abnahme-Screenshots landen in
`docs/ux-padua/abnahme-*.png` und werden **committet** — sie zeigen nur
erfundenes Material.
```

- [ ] **Schritt 5: Die normale Suite**

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1. **Die Zahl der uebersprungenen Tests steigt von 1 auf
2** — die neue e2e-Datei ueberspringt sich ebenfalls per `importorskip`. Das ist erwartet
und wird im Abschlusscommit benannt.

- [ ] **Schritt 6: Commit**

```bash
git add tests/e2e/test_web_gestalt_e2e.py tests/e2e/README.md \
        docs/ux-padua/abnahme-handy-chat.png docs/ux-padua/abnahme-handy-aufnahme.png \
        docs/ux-padua/abnahme-handy-akte.png docs/ux-padua/abnahme-handy-textbuch.png \
        docs/ux-padua/abnahme-handy-probenansicht.png \
        docs/ux-padua/abnahme-laptop-chat.png docs/ux-padua/abnahme-laptop-aufnahme.png \
        docs/ux-padua/abnahme-laptop-akte.png docs/ux-padua/abnahme-laptop-textbuch.png
git commit -m "UX: Browserlauf mit Fake-Mikrofon, Abnahme-Screenshots aus der Demo-DB

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 13: `BERICHT.md`, `AGENTS.md`, Abschluss

**Dateien:**
- Neu: `docs/ux-padua/BERICHT.md`
- Aendern: `AGENTS.md` (Modultabelle, Modulkarte, ein Abschnitt unter „Weboberflaeche")

- [ ] **Schritt 1: `docs/ux-padua/BERICHT.md` schreiben**

Die Gliederung liegt fest; der Inhalt kommt aus dem, was in den Aufgaben 1–12 wirklich
passiert ist:

```markdown
# UX Padua — was entschieden wurde und warum

<ERSTE ZEILE: welcher Entwurf umgesetzt ist. Bei "Entscheidung Birk: offen"
woertlich: "Birk hat nicht entschieden — umgesetzt ist die Empfehlung,
Entwurf A (Terminal zuerst). Umschalten auf B: web_gestalt.VORGABE_ENTWURF
= \"b\" oder IT_UX_ENTWURF=b, dazu ein Neustart von
interview-theater-web.service.">

## Birks Richtung, und wie sie gelesen wurde

"bisschen matrix style cool, unterhaltend, technoisch, theater" — die vier
Leitplanken (Terminal, Theater, unterhaltend, technoid), je mit dem, was
daraus im Code geworden ist und was ausdruecklich NICHT: keine
dauerlaufenden Effekte, kein Ton, keine Dekoration ohne Funktion, kein
Kitsch am Phasenwechsel.

## Welcher Entwurf und warum

Die vier Gruende aus ENTWUERFE.md, dazu: was sich beim Bauen gegen den
Entwurf gezeigt hat (z. B. die zwei Fehler, die erst im Screenshot
auffielen — `z-index` des Fusses gegen den sticky Kopf, und die
aufgeklappte Aktliste, die am Telefon die Tableiste aus dem Bild schob).

## Die vier benannten Komponenten-Abweichungen

Tab-Ort, Knopfform, Akt-Moment, Skript-Satz — je mit der Konstante, an der
sie haengt (`_TABS_A/_B`, `_CHAT_A/_B`, `_MOMENTE_A/_B`, `_SKRIPT_A/_B`).

## Was verworfen wurde

Aus ENTWUERFE.md uebernehmen (dauerhaft aufgeklappte Uebersicht,
Dauereffekte, Ton, Schieben-zum-Sperren, Farbe als alleiniger
Zustandstraeger) und ergaenzen: die dritte Belohnung ("Szene fertig") und
warum sie nicht gebaut ist.

## Befunde an anderen Karten

- **A2, Befund 1:** Drucke waehrend eines Uebergangs werden nicht
  ignoriert (das Dortmunder Fehlerbild). Vorschlag: `zustand.uebergang` in
  `_CHAT_JS`, und der Click-Handler beginnt mit
  `if (zustand.uebergang) { return; }`. **Gehoert zu A2, hier bewusst
  nicht repariert** — die Gestaltung zeigt nur `aria-busy`.
- **A2, Befund 2:** die Knopfbeschriftung steht als deutsches Literal im
  JavaScript statt in `_TEXT_INTERVIEW_AN`/`_AUS`.
- <weitere Befunde aus den Annahmen-Kommandos, Aufgabe 1 Schritt 4>

## Offene Wuensche

- **Das Team-Dashboard `/`** bleibt ungestaltet (Beamer, anderer Kontext).
- **Wellenform statt Pegelbalken** (braucht ein Canvas und damit eine
  CSP-Ueberlegung zu `img-src`).
- **Haptik** beim Start/Stopp der Aufnahme (`navigator.vibrate` gibt es
  auf iOS-Safari nicht — ein Gefuehl, das die Haelfte der Gruppe nicht
  bekommt).
- **Eine dritte Belohnung "Szene fertig"** — braeuchte im Zustands-Poll
  einen additiven read-only-Schluessel (etwa `letzte_szene_id`).
- <was beim Ansehen der Screenshots aufgefallen ist und nicht mehr in
  diese Karte gehoert>

## Zahlen

Baseline vorher/nachher, Zahl der Kontrastpaare je Entwurf, kleinstes
gemessenes Verhaeltnis, Zahl der Zeilen, die in `web.py` und
`web_vereint.py` wirklich geaendert wurden.
```

- [ ] **Schritt 2: `AGENTS.md` — Modultabelle und Modulkarte**

Eine Zeile in der Modultabelle, bei den `web_*`-Eintraegen:

```markdown
| `web_gestalt.py` | Die Gestaltung der Weboberflaeche (01.10.2026, Padua): ein Block Design-Tokens je Entwurf (A „Terminal zuerst", B „Buehne zuerst"), das Komponenten-CSS, das Effekt-JavaScript und die englischen Mikrotexte. Eingehaengt an **fuenf** Zeilen (vier in `web_vereint.seite`, je eine in `web.textbuch_html`/`leitfaden_html`) — **kein SQL, kein Modellaufruf, kein Endpunkt, kein neues Markup**. Umschalten: `IT_UX_ENTWURF` |
```

In der **Modulkarte** unter „Oberflaeche" `web_gestalt.py` ergaenzen, und in „Wo man
anfaengt, je nach Frage" eine Zeile:

```markdown
| Warum sieht die Weboberflaeche so aus? | `web_gestalt.TOKENS` → `css_rahmen` → `docs/ux-padua/BERICHT.md` |
```

- [ ] **Schritt 3: `AGENTS.md` — der Abschnitt unter „Weboberflaeche"**

Nach „Fassungen umschalten (07.09.2026)":

```markdown
### Die Gestaltung (01.10.2026, Padua)

Alles Gestalterische liegt in **einem** Modul (`web_gestalt.py`) und wird
an fuenf Zeilen eingehaengt: vier in `web_vereint.seite` (Rahmen-CSS plus
drei gescopte Bloecke, dazu das Effekt-JS) und je eine in
`web.textbuch_html` und `web.leitfaden_html`. Es fasst **kein Markup** an —
was die Gestaltung zusaetzlich braucht, legt das Effekt-JS zur Laufzeit an
(alles mit dem Praefix `ux-`).

**Ein Block Design-Tokens ist der ganze Entwurf.** `TOKENS["a"]`
(„Terminal zuerst": Phosphor auf Schwarzblau, Monospace, Tableiste unten)
und `TOKENS["b"]` („Buehne zuerst": Amber auf Samtschwarz, Serife, Tabs
oben) tragen **dieselben Schluessel**; umgeschaltet wird ueber
`VORGABE_ENTWURF` oder `IT_UX_ENTWURF`, dazu vier benannte
Komponenten-Abweichungen (Tab-Ort, Knopfform, Akt-Moment, Skript-Satz).
Die klickbaren Muster, an denen entschieden wurde, liegen unter
`docs/ux-padua/entwurf-{a,b}.html`.

**Drei CSP-Regeln, die im Code stehen und nicht im Kommentar** (die
Richtlinie aus der Absicherungs-Karte hat `default-src 'none'`,
`script-src`/`style-src` nur mit Nonce und **kein `font-src`**):

1. **Kein Webfont, kein `@font-face`, kein `@import`, keine Fremdquelle** —
   System-Schriftstacks (`--schrift-lesen/-tech/-skript`). Ein
   eingebetteter Font waere geblockt, auch mit `data:`-URL.
2. **Kein `style="…"`-Attribut, kein `on…=`-Handler** im ausgelieferten
   HTML. Dynamische Werte gehen ueber **CSSOM**
   (`el.style.setProperty('--fortschritt', …)`) — das ist unter
   `style-src 'nonce-…'` erlaubt, `setAttribute('style', …)` waere es
   nicht. Ein Test misst das am fertigen HTML der vereinten Seite, der
   Probenansicht und des Leitfadens.
3. **`@keyframes` und `@media` nur in `css_rahmen()`.** Die drei anderen
   CSS-Funktionen laufen beim Aufrufer durch `web_vereint.scope_css`, und
   dessen Regex machte aus dem Rumpf eines `@keyframes` (`50% { … }`) eine
   gescopte Regel `.panel-chat 50%`.

**`prefers-reduced-motion: reduce` legt alles still**, und zwar mit
`!important` — die Animationen aus A2/W sind gescopt und damit
spezifischer als jede Regel dieses Moduls. Der Strom baut seinen Text
trotzdem stueckweise auf: das ist Information, keine Animation. **Kein
Zustand haengt an einer Bewegung**; jeder steht zusaetzlich im Text.

**Der Kontrast ist gerechnet, nicht geschaetzt.** `web_gestalt.KONTRAST`
ist die Tabelle der Paare, die die Gestaltung wirklich uebereinanderlegt;
`tests/test_web_gestalt_tokens.py` rechnet fuer **beide** Entwuerfe das
WCAG-Verhaeltnis nach (≥ 4.5 fuer Text, ≥ 3 fuer Bedienelemente). Wer eine
Farbkombination hinzufuegt, traegt sie dort ein — sonst prueft sie
niemand. `--linie` steht bewusst nicht darin (dekorative Haarlinie);
Raender, die einen Zustand tragen, benutzen `--rand`.

**Der Aufnahmeknopf ist das wichtigste Element** (Dortmund Tag 1: 13 von
20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden gedrueckt). Vier
Zustaende, aus dem DOM abgeleitet und **ohne neuen Schluessel im
Zustands-Poll**: `ruht` → `startet` → `laeuft` → `laedt`. Jeder steht im
**Text** (zweite Zeile `#ux-rec-zeile` **neben** dem Knopf — `_CHAT_JS`
schreibt in den Knopf selbst), der laufende ist **groesser** als der
ruhende, und `:active` gibt die Rueckmeldung in unter 100 ms. Die
Gestaltung **sperrt keinen Druck**: dass `_CHAT_JS` waehrend eines
Uebergangs weiter auf Klicks reagiert, ist ein Logikbefund an der
Web-Chat-Karte und steht in `docs/ux-padua/BERICHT.md`.

**Der Ausdruck bleibt hell.** `css_rahmen()` traegt einen eigenen
`@media print`-Block, weil die Gestaltung im `<style>` **nach**
`_CSS_TEXTBUCH` steht — ohne ihn kaeme ein schwarzes Blatt aus dem
Drucker.

**Das Team-Dashboard `/` ist bewusst nicht gestaltet** — es haengt am
Beamer und ist ein anderer Kontext.
```

- [ ] **Schritt 4: Der Schlusslauf**

```
$PY -m pytest -q -p no:cacheprovider
```
Erwartet: ≥ Baseline aus Aufgabe 1 — und **groesser**, diese Karte bringt fuenf
Testdateien mit. `2 skipped` (beide e2e-Dateien).

```
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: Exit 0.

```
$PY -c "
from interview_theater import web_gestalt
for n in web_gestalt.ENTWUERFE:
    t = web_gestalt.TOKENS[n]
    werte = [web_gestalt.kontrastverhaeltnis(t[p.vorn], t[p.hinten])
             for p in web_gestalt.KONTRAST]
    print(n, len(werte), 'Paare, kleinstes', round(min(werte), 2))"
```
Erwartet: `a 17 Paare, kleinstes 3.07` und `b 17 Paare, kleinstes 3.23` (oder besser) —
die genauen Zahlen gehen in den BERICHT.

```
git status --short
```
Erwartet: **leer**.

- [ ] **Schritt 5: Commit**

```bash
git add docs/ux-padua/BERICHT.md AGENTS.md
git commit -m "UX Padua: Bericht und AGENTS.md -- Tokens, CSP-Regeln, der Aufnahmeknopf

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Uebergaben

Was diese Karte bewusst **nicht** erledigt — jeweils mit dem Grund:

1. **Das Team-Dashboard `/`.** Es haengt am Beamer, wird projiziert und aus drei Metern
   gelesen — ein anderer Kontext mit anderen Groessen und anderem Kontrastbedarf. Es
   koennte von `tokens_css()` profitieren (der Tokenblock ist dafuer gebaut), aber die
   Entscheidung „wie sieht ein projiziertes Dashboard aus" ist eine eigene, und diese
   Karte faellt sie nicht nebenbei.

2. **Die zwei Befunde an Karte A2** (Plan-Kopf). Der erste — Drucke waehrend eines
   Uebergangs werden nicht ignoriert — ist **genau das Dortmunder Fehlerbild** und
   verdient eine eigene kleine Karte: eine Zustandsvariable `zustand.uebergang` in
   `_CHAT_JS` und ein `return` am Anfang des Click-Handlers. Der zweite — die
   Knopfbeschriftung als deutsches Literal im JS — gehoert in den A1-Nachzug von Karte W.
   Beide hier zu reparieren hiesse, Logik in einer Gestaltungskarte zu aendern, und das
   faellt bei der naechsten Zusammenfuehrung auf die Fuesse.

3. **Die dritte Belohnung („Szene fertig").** Sie braeuchte die Information „gerade ist
   ein Szenentext eingetroffen", und die steht nirgends im DOM: ein fertiger Szenentext
   kommt als gewoehnliche Bot-Blase. Die Karte erlaubt **einen** additiven
   read-only-Schluessel im Zustands-Poll (etwa `letzte_szene_id`) — gebraucht haben ihn
   die beiden gebauten Belohnungen nicht, und einen Schluessel fuer eine einzige
   Belohnung einzufuehren waere der falsche Preis. Wer sie will, baut beides zusammen.

4. **Eine Wellenform statt des Pegelbalkens.** Schoener und aussagekraeftiger, braucht
   aber ein `<canvas>` — und damit eine Ueberlegung zu `img-src` in der CSP. Ein Balken,
   der sich bewegt, sagt „das Mikrofon hoert dich" schon; mehr braucht der Probenraum
   nicht.

5. **Haptik beim Start und Stopp der Aufnahme.** `navigator.vibrate` waere die klarste
   Rueckmeldung ueberhaupt — es gibt sie auf iOS-Safari nicht. Ein Gefuehl, das die
   Haelfte der Gruppe nicht bekommt, ist schlechter als keins, weil es die Erwartungen
   auseinandertreibt.

6. **Die Phasen heissen im Chat weiter „Phase".** Umbenannt ist nur die Marke in der
   Web-Uebersicht („Akt 3/7"). Die Namen in `phasen.PHASEN` und `phasentexte` stehen in
   Prompts, im Journal, in `/stand` und in den Migrationen
   (`db.PHASEN_UMNUMMERIERUNG*`); sie anzufassen waere ein Umbau, keine Gestaltung — und
   ein Journal, in dem „Phase 5 · Figuren" steht, weil das am 04.09. wahr war, wird
   ohnehin nie umgedeutet.

7. **Telegram bleibt unberuehrt (E1).** Die ganze Karte lebt im Webdienst. Eine Gruppe,
   die ueber Telegram arbeitet, sieht kein einziges Zeichen davon — und soll es auch
   nicht.

8. **Kein Dunkel/Hell-Umschalter.** Beide Entwuerfe sind dunkel, und der
   `@media print`-Block ist die einzige helle Flaeche. Ein zweites Thema waere ein
   zweiter Satz Tokens, ein zweiter Kontrastlauf und eine dritte Entscheidung, die
   niemand bestellt hat. Der Probenraum ist dunkel, die Telefone liegen auf einem Tisch,
   und beide Entwuerfe haben 15 : 1 auf dem Fliesstext.

9. **Die Entwuerfe unter `docs/ux-padua/entwurf-{a,b}.html` werden nicht
   nachgefuehrt.** Sie sind das Artefakt, an dem entschieden wurde, und sollen genau den
   Stand zeigen, den Birk gesehen hat. Zwei Werte weichen deshalb bewusst vom Code ab
   (`--rand` gibt es dort nicht, `b.rec` ist dort dunkler) — beides steht als Kommentar
   in `web_gestalt.TOKENS`.

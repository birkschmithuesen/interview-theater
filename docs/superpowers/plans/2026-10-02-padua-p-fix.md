# Padua P-Fix: Profil-Abnahme Birk umsetzen + Prompt-Widersprueche c1-c10

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Birks sieben Entscheidungen zum Padua-Profil (01.10.2026) im Profil
und in der englischen Sprachschicht umsetzen und dabei die zehn
Prompt-Widersprueche c1-c10 aus `docs/prompt-audit/2026-09-30-padua/BEFUND.md`
nach der **Code-Wahrheit** aufloesen -- belegt, nicht geraten.

**Architektur:** Kein neues Modul, keine neue Schicht. Geaendert werden
(1) `workshop/padua-2026/` (Werte, LIESMICH), (2) die **englische**
Sprachschicht `interview_theater/sprachen/en/` (neun Prompt-Dateien, eine
Zeile in `texte.toml`), (3) zwei berechnete Platzhalter in
`interview_theater/workshop.py`, (4) die Platzhalterpruefung in
`scripts/pruefe_profil.py`, (5) der Dump-Marker in
`scripts/erzeuge_prompts_padua.py`, (6) Tests und (7) Doku samt neuem
Prompt-Dump. **Die deutschen Prompts und `workshop/dortmund-2026/` bleiben
byte-gleich.**

**Tech Stack:** Python 3.11 (stdlib + `tomllib`), pytest. Kein Netz, kein
Modellaufruf -- auch der Prompt-Dump ist reine Textmontage
(`scripts/erzeuge_prompts_padua.py` ruft nur `anweisungen`/`kontext`/
`kurzgeschichte.systemanweisung`/`szene.systemanweisung`, nie `llm`).

---

## Global Constraints

- **Python:** `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
  Suite: `$PY -m pytest -q -p no:cacheprovider`. Alle Befehle aus dem
  Worktree-Wurzelverzeichnis
  `/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_56df06b2`.
- **Basiszahlen dieses Worktrees, selbst gemessen (02.10.2026, HEAD `6364354`):**
  `1 failed, 5008 passed, 2 skipped in 415.36s`. Der eine Fehlschlag ist
  **vorbestehend** und hat mit dieser Karte nichts zu tun:
  `tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]`
  (`_sofort_szene` fehlt der Parameter `art='szene'`). **Soll nach dieser
  Karte: `1 failed, >=5008 passed` -- derselbe eine Fehlschlag, kein neuer.**
  **Nachtrag Architekt (02.10.2026):** `origin/main` steht inzwischen auf
  `1e6bd0d` ("Simulation: _sofort_szene reicht art durch") und behebt genau
  diesen Fehlschlag. Basiert der Umsetzungs-Branch auf `1e6bd0d` oder
  spaeter, ist das Soll **`0 failed`** -- dann die Baseline vor Task 1 im
  eigenen Worktree neu messen und diese Zahl als Vorher-Wert nehmen.
  Die Suite laeuft rund 7 Minuten; **nicht in den Hintergrund schicken**,
  sondern abwarten.
- **Sprache:** Bezeichner, Kommentare, Doku und Commit-Botschaften deutsch mit
  ASCII-Umschrift (`ue`, `oe`, `ae`, `ss`) wie im Repo. Prompt-Text in der
  Sprachschicht `en/` ist **englisch**.
- **Niemals `betrieb/**` lesen oder schreiben** (echte Daten, Tokens).
- **Kein bezahlter Modellaufruf** (Infomaniak, Proxy `127.0.0.1:28764`).
- **Nie** `git add` auf `.superpowers-brief*`, `.cc-run-*`, `.cc-settings.json`.
- Ein Commit je Task, Botschaft am Ende der Task. Attribution-Zeile an jedes
  Commit:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

## Scope-Grenze

**Angefasst wird nur:**

| Pfad | Was |
|---|---|
| `workshop/padua-2026/profil.toml` | Werte zu Birks Punkten 1-7, ANNAHME-Kommentare weg |
| `workshop/padua-2026/prompts/anweisung.md` | Schluss durch Birks Punkt 7 ersetzt |
| `workshop/padua-2026/LIESMICH.md` | ANNAHME-Absatz -> abgenommener Stand |
| `interview_theater/sprachen/en/prompts/{system,szene,rahmen,rahmen-kurz,theater-tells}.md`, `.../phasen/6.md`, `.../formen/{chor,rap,prosa}.md` | Beispielorte -> `<place>`, c1-c9 |
| `interview_theater/sprachen/en/texte.toml` | **eine** Zeile: `["kontext"] KERNPAKET_KOPF` (Z. 848) |
| `interview_theater/workshop.py` | zwei berechnete Platzhalter in `platzhalter()` |
| `scripts/pruefe_profil.py` | `_prompt_texte()` liest die Sprachschicht mit |
| `scripts/erzeuge_prompts_padua.py` | `MARKE` |
| `tests/test_profile_geruest.py`, `tests/test_sprache_prompts.py`, `tests/test_rahmen.py` | Zusicherungen nachziehen, neue Guards |
| `docs/prompt-audit/2026-10-01-padua-fix/` | vier Dumps + `uebersicht.tsv` + `BEFUND.md` (neu) |
| `docs/prompt-audit/2026-09-30-padua/BEFUND.md` | **genau eine** Zeigerzeile oben in Abschnitt c |

**Nicht angefasst, und ein Test belegt es am Ende:**
`workshop/dortmund-2026/**`, `interview_theater/prompts/**` (die deutschen
Prompts), `interview_theater/szene.py`, `interview_theater/sprachen/en/texte.toml`
Zeilen um `["szene"] FIGUREN_KOPF_OHNE_STIMME` (Z. 926/934) und
`["szene"] KERNPAKET_KOPF` (Z. 932).

### Die c9/M1-Teilung

Widerspruch **c9** (Sprechweise) ist zwischen zwei Karten geteilt:

- **M1-Fix** (parallele Karte): `sprachen/en/texte.toml:926`/`:934`
  (`["szene"] FIGUREN_KOPF_OHNE_STIMME`, "Their way of speaking isn't backed
  by interviews yet") und alles in `interview_theater/szene.py`. **Hier nicht
  anfassen.**
- **P-Fix** (diese Karte): nur der Satz in
  `sprachen/en/prompts/phasen/6.md:67` ("No question about a character's way of
  speaking") wird mit dem in Deckung gebracht, was der Phase-6-Prompt
  **tatsaechlich** mitbekommt (Task 9).

### Ueber die Kartenliste hinaus -- der Reviewer kann jedes einzeln streichen

1. **Zwei weitere Beispielorte** (D2, gleiche Begruendung wie Punkt 4:
   "Nachplappern von Beispielorten ist gemessen", 06.09.):
   `theater-tells.md:64` `(station concourse, early)` -> `(<place>, early)`
   und `system.md:201` "what Interview 2 says about the station" ->
   "... about `<place>`". Task 4.
   **Sie sind fuer die Abnahme nicht optional, gemessen** (02.10.2026, die
   acht P1-Treffer im SYSTEM-Teil der alten Dumps, einzeln aufgeloest):
   01 = `bus stop`, `the station`, `bus stop`; 02 = dieselben drei plus
   `bus stop`; 03 = `station concourse`; 04 = `station concourse`. Ohne
   `theater-tells.md:64` bleiben 03 und 04 bei 1, ohne `system.md:201`
   bleiben 01 und 02 bei 1 -- das Kriterium "neu == 0" waere dann nicht
   erreichbar.
2. **`zielgruppe.traeger`** (D5): "academy of the National Theatre of the
   Veneto Region, **Teatro Verdi, Padova**" -> "..., Padova". Grund: "Teatro
   Verdi" soll im Dump 0 sein, und der Traeger ist die zweite Stelle, an der
   es steht. Institution bleibt, Spielort faellt. Task 6.
3. **`system.md:72-76` neutral** (D6): "variants of the **SAME** idea ...
   Multiple choice about their idea, not about yours" widerspricht Birks
   Punkt 7 (eine Option darf einen ueberraschenden Winkel nehmen). System.md
   wird neutral, die Winkel-Regel steht **nur** in `anweisung.md` -- ein Fakt,
   eine Stelle im Prompt. Task 8.
4. **Dump-Marker** (D9): `<!-- VORSCHLAG zur Abnahme -->` ->
   `<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->`. Nur im Dump, der
   Bot sieht ihn nie. Task 13.
5. **`scripts/pruefe_profil.py` liest die Sprachschicht mit** (Folge von D1).
   Begruendung, gemessen: `workshop._vereinige` (`workshop.py:463-475`) legt
   ein Profil **Ebene fuer Ebene** ueber `VORGABE_WERTE`. Wird
   `orte.beispiele` in Padua **geloescht**, erbt Padua die **deutsche** Liste
   `["Bushaltestelle", "Schulhof", "Kiosk", "Bahnhof"]` (`workshop.py:165`) --
   das Gegenteil von "Beispielorte raus". Wird es auf `[]` gesetzt, fehlen die
   Schluessel `ort_beispiel_1..4`, und `pruefe_profil` meldet FEHLER, weil
   `_prompt_texte()` (`scripts/pruefe_profil.py:99-121`) die **deutschen**
   Repo-Prompts gegen die Padua-Platzhalter prueft, obwohl unter `sprache.code
   = "en"` fuer jede dieser Dateien die englische Fassung gilt
   (`anweisungen._roh`, Reihenfolge Profil > Sprache > Repo). Deshalb prueft
   `_prompt_texte()` ab Task 5 die **wirksame** Ebene -- und prueft damit die
   englische Schicht zum ersten Mal ueberhaupt auf offene Platzhalter.
   *Falls der Reviewer Task 5 streicht:* dann in Task 6 statt `beispiele = []`
   `beispiele = ["<place>", "<place>", "<place>", "<place>"]` setzen (Birks
   Punkt 4 nennt diese Variante ausdruecklich: "leer bzw. auf `<place>`"),
   Task 5 entfaellt samt seinem Test, und die Zusicherung
   `test_padua_hat_keine_beispielorte_mehr` prueft dann diese Liste.

## Offene Fragen

**Keine.** Jeder Widerspruch c1-c10 ist entweder durch Birks Punkte 1-7
entschieden (c1, c10) oder aus dem Code belegt (c2-c9, Belege je Task und in
der BEFUND-Tabelle von Task 14). Zwei Dinge bleiben **bewusst** liegen, beide
dokumentiert statt geraten:

- `sprachen/en/prompts/phasen/1..7.md` tragen alle denselben Einschub
  "(variants of the same idea, title — description)" (gemessen: `phasen/1.md:20`,
  `2.md:31`, `3.md:57`, `4.md:94`, `5.md:33`, `6.md:55`, `7.md:31`). Die Karte
  nennt fuer c1 ausdruecklich nur `system.md:67-68`. Aufgeloest wird es
  dadurch, dass `anweisung.md` als **letzter** Block des Prompts steht
  (`anweisungen.system`, `anweisungen.py:368-370`; das Ende wiegt am
  schwersten, SPEC § 6.1) -- die sieben Phasendateien bleiben unangetastet und
  werden in der BEFUND-Tabelle als bekannte Restspannung notiert.
- `texte.toml:932` (`["szene"] KERNPAKET_KOPF`, "filtered by the core theme")
  nennt das Kernthema ebenfalls. D8 zieht die Grenze bei `~l.848`; :932 bleibt
  stehen und wird in der BEFUND-Tabelle als nicht in dieser Karte benannt.

## File Structure

| Datei | Verantwortung nach dieser Karte |
|---|---|
| `workshop/padua-2026/profil.toml` | **Werte** des Workshops, ohne eine einzige `ANNAHME (unbelegt)`-Zeile |
| `workshop/padua-2026/prompts/anweisung.md` | die Padua-Verhaltensanweisung; **die einzige** Stelle mit der Winkel-Regel aus Punkt 7 |
| `interview_theater/workshop.py` | `platzhalter()` liefert zwei **berechnete** Platzhalter (Strich-/Klammerform des Konfliktrahmens) -- die Vorlage soll keine Logik tragen |
| `interview_theater/sprachen/en/prompts/rahmen.md`, `rahmen-kurz.md` | Rahmenvorlagen; bei leerem Feld faellt der Teilsatz **ganz** weg |
| `interview_theater/sprachen/en/prompts/*.md` | englischer Prompt-Text; **kein** Beispielort mehr, nur `<place>` |
| `scripts/pruefe_profil.py` | prueft Platzhalter auf der **wirksamen** Prompt-Ebene |
| `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md` | der Nachweis: c1-c10 Zeile fuer Zeile, Greptabelle, `pruefe_profil`-Ausgabe |

---

### Task 1: Zwei berechnete Platzhalter fuer den Konfliktrahmen

Birks Punkt 5: `konflikt.erlaubt` wird leer, und dann darf in der englischen
Rahmenvorlage weder `-- .` noch `()` uebrig bleiben. Die Vorlage ist Markdown
und kann nicht rechnen -- also rechnet `workshop.platzhalter()`.

**Files:**
- Modify: `interview_theater/workshop.py:860-877` (im `werte`-Dict von `platzhalter()`)
- Test: `tests/test_rahmen.py` (am Ende anhaengen)

**Interfaces:**
- Produces: `workshop.platzhalter()["konflikt_erlaubt_strich"]` -> `" -- <Wert>"`
  bei gesetztem `konflikt.erlaubt`, sonst `""`.
- Produces: `workshop.platzhalter()["konflikt_erlaubt_klammer"]` -> `" (<Wert>)"`
  bei gesetztem `konflikt.erlaubt`, sonst `""`.
- Consumes (Task 2): beide in `sprachen/en/prompts/rahmen.md` bzw. `rahmen-kurz.md`.

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

An das Ende von `tests/test_rahmen.py` anhaengen:

```python
# --- Karte P-Fix: der Konfliktrahmen darf leer sein (Birk, Punkt 5) -------

def test_konfliktrahmen_als_strich_und_als_klammer():
    """Gesetzt: der Teilsatz steht mit seinem Satzzeichen. Leer: er ist weg.

    Die Vorlagen (``sprachen/en/prompts/rahmen*.md``) koennen nicht rechnen --
    deshalb rechnet ``workshop.platzhalter()``. Ohne das stuende in einem
    englischen Padua-Prompt "conflict may be serious -- ." bzw.
    "Conflict may be serious ()."."""
    werte = workshop.platzhalter()
    erlaubt = werte["konflikt_erlaubt"]
    assert erlaubt, "das Vorgabeprofil hat einen Konfliktrahmen"
    assert werte["konflikt_erlaubt_strich"] == f" -- {erlaubt}"
    assert werte["konflikt_erlaubt_klammer"] == f" ({erlaubt})"


def test_leerer_konfliktrahmen_laesst_nichts_uebrig(tmp_path, monkeypatch):
    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[zielgruppe]\nbeschreibung = "students"\n'
        '[konflikt]\nerlaubt = ""\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    werte = workshop.platzhalter()
    assert werte["konflikt_erlaubt"] == ""
    assert werte["konflikt_erlaubt_strich"] == ""
    assert werte["konflikt_erlaubt_klammer"] == ""
```

- [ ] **Step 2: Lauf zum Beweis, dass er fehlschlaegt**

```
$PY -m pytest -q -p no:cacheprovider tests/test_rahmen.py -k konflikt
```
Erwartet: `2 failed` mit `KeyError: 'konflikt_erlaubt_strich'`.

- [ ] **Step 3: Die zwei Platzhalter berechnen**

In `interview_theater/workshop.py`, in `platzhalter()`, **nach** dem
`werte = {...}`-Literal und **vor** dem Block
`# Die Beispielorte einzeln ({{ort_beispiel_1}} ...)` einfuegen:

```python
    # Der Konfliktrahmen in seinen zwei Satzformen (01.10.2026, Karte P-Fix,
    # Birks Punkt 5). Ein Profil darf ``konflikt.erlaubt`` leer lassen; dann
    # soll in der Vorlage kein Satzzeichen verwaisen -- aus "conflict may be
    # serious -- {{konflikt_erlaubt}}." wird sonst "conflict may be serious
    # -- ." und aus "({{konflikt_erlaubt}})" ein leeres Klammerpaar.
    # Gerechnet wird HIER und nicht in der Markdown-Vorlage: eine Vorlage
    # kennt keine Bedingung, und zwei Vorlagen je Fall waeren zwei
    # Wahrheiten. Die Form steht im Namen -- Strich fuer den langen
    # Rahmenblock, Klammer fuer den kurzen.
    erlaubt = werte["konflikt_erlaubt"].strip()
    werte["konflikt_erlaubt_strich"] = f" -- {erlaubt}" if erlaubt else ""
    werte["konflikt_erlaubt_klammer"] = f" ({erlaubt})" if erlaubt else ""
```

- [ ] **Step 4: Lauf zum Beweis, dass er durchgeht**

```
$PY -m pytest -q -p no:cacheprovider tests/test_rahmen.py tests/test_sprache_prompts.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed` (kein Fehlschlag). `test_profil_bitgleich.py` muss
gruen sein: die deutschen Prompts nennen die neuen Platzhalter nicht, also
aendert sich an Dortmund kein Zeichen.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/workshop.py tests/test_rahmen.py
git commit -m "$(cat <<'EOF'
workshop: Konfliktrahmen als Strich- und Klammerform (Karte P-Fix, Punkt 5)

Ein Profil darf konflikt.erlaubt leer lassen. Damit in der englischen
Rahmenvorlage dann kein "-- ." und kein "()" verwaist, rechnet
platzhalter() die zwei Satzformen aus, statt sie in Markdown zu
verzweigen. Deutsche Prompts nennen die Platzhalter nicht -- Dortmund
bleibt bitgleich.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Die englischen Rahmenvorlagen benutzen sie

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/rahmen.md:16-17`
- Modify: `interview_theater/sprachen/en/prompts/rahmen-kurz.md:4-5`
- Test: `tests/test_rahmen.py` (am Ende anhaengen)

**Interfaces:**
- Consumes: `konflikt_erlaubt_strich`, `konflikt_erlaubt_klammer` aus Task 1.

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

An das Ende von `tests/test_rahmen.py` anhaengen:

```python
def test_englischer_rahmen_ohne_konfliktrahmen(tmp_path, monkeypatch):
    """Padua laesst den Konfliktrahmen leer -- dann steht im Prompt
    "conflict may be serious." und sonst nichts (Karte P-Fix, Punkt 5)."""
    from interview_theater import sprache

    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[sprache]\ncode = "en"\nanrede = "you"\n'
        '[zielgruppe]\nbeschreibung = "students"\ntraeger = "an academy"\n'
        '[konflikt]\nerlaubt = ""\nausgeschlossen = "No glorification"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    assert sprache.code() == "en"
    for name in ("rahmen", "rahmen-kurz"):
        roh = anweisungen.hole(name)
        # Whitespace zusammenziehen: in rahmen-kurz.md faellt der
        # Zeilenumbruch mitten in den Satz ("Conflict may be\nserious.").
        text = " ".join(roh.split())
        assert "conflict may be serious." in text.lower(), name
        assert "serious --" not in text, name
        assert "()" not in roh, name
        assert "{{" not in roh, name
```

- [ ] **Step 2: Lauf zum Beweis, dass er fehlschlaegt**

```
$PY -m pytest -q -p no:cacheprovider tests/test_rahmen.py -k englischer_rahmen_ohne
```
Erwartet: `1 failed` -- `assert "()" not in text` schlaegt an
(`rahmen-kurz.md` hat heute `({{konflikt_erlaubt}})`).

- [ ] **Step 3: Die Vorlagen umstellen**

`interview_theater/sprachen/en/prompts/rahmen.md`, Zeile 16-17 heute:

```
- **What may be in it:** conflict may be serious -- {{konflikt_erlaubt}}.
  {{konflikt_ausgeschlossen}}.
```

neu:

```
- **What may be in it:** conflict may be serious{{konflikt_erlaubt_strich}}.
  {{konflikt_ausgeschlossen}}.
```

`interview_theater/sprachen/en/prompts/rahmen-kurz.md`, Zeile 3-6 heute:

```
Where it is shown: {{auffuehrungsort}}. No set, no props except what people wear,
movement carries, text is sparing. Conflict may be serious
({{konflikt_erlaubt}}). {{konflikt_ausgeschlossen}}. The group's
material comes before every example.
```

neu:

```
Where it is shown: {{auffuehrungsort}}. No set, no props except what people wear,
movement carries, text is sparing. Conflict may be
serious{{konflikt_erlaubt_klammer}}. {{konflikt_ausgeschlossen}}. The group's
material comes before every example.
```

- [ ] **Step 4: Lauf zum Beweis, dass er durchgeht**

```
$PY -m pytest -q -p no:cacheprovider tests/test_rahmen.py tests/test_sprache_prompts.py tests/test_profile_geruest.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`. `rahmen`/`rahmen-kurz` stehen in
`test_sprache_prompts.INHALTSBAUSTEINE`, ihre Platzhalter werden also nur
gegen `workshop.platzhalter()` geprueft (`test_inhaltsbausteine_nutzen_nur_profilwerte`)
-- Task 1 hat beide Schluessel angelegt.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/sprachen/en/prompts/rahmen.md \
        interview_theater/sprachen/en/prompts/rahmen-kurz.md \
        tests/test_rahmen.py
git commit -m "$(cat <<'EOF'
en-rahmen: leerer Konfliktrahmen laesst keinen Teilsatz uebrig (Punkt 5)

rahmen.md nimmt {{konflikt_erlaubt_strich}}, rahmen-kurz.md
{{konflikt_erlaubt_klammer}}. Bei leerem Profilfeld bleibt
"Conflict may be serious." stehen -- kein "-- .", kein "()".
Die deutschen Vorlagen tragen die Dortmunder Werte ausgeschrieben und
werden nicht angefasst.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `konflikt.ausgeschlossen` auf Birks Punkt 6

Eigene Task, weil es ein reiner Wertwechsel ist und der Grep der Abnahme
daran haengt ("glorification" -> 0 im Dump; Altstand gemessen: 01=1, 02=2).

**Files:**
- Modify: `workshop/padua-2026/profil.toml:62`
- Test: `tests/test_profile_geruest.py` (neue Zusicherung, Task 7 zieht den Rest nach)

- [ ] **Step 1: Den Wert setzen**

`workshop/padua-2026/profil.toml`, Zeile 62 heute (eine Zeile, Kommentar am
Ende):

```toml
ausgeschlossen = "No glorification of violence; no interviewed person recognisable by name"   # ANNAHME (unbelegt): erster Teil aus Dortmund uebernommen, zweiter aus V1 "fiktiv, NICHT dokumentarisch" abgeleitet
```

neu (zwei Zeilen: Beleg-Kommentar darueber, Wert ohne Anhang):

```toml
# Birk 01.10.2026 (Punkt 6): nur der Schutz der Befragten. "No glorification
# of violence" ist Dortmunds Jugendschutz und faellt weg -- hier sitzen
# Erwachsene, und was auf die Buehne darf, ist ihre kuenstlerische
# Entscheidung. Grossgeschrieben, weil die Vorlagen den Wert an einen
# Satzanfang setzen ("{{konflikt_ausgeschlossen}}.").
ausgeschlossen = "No interviewed person recognisable by name or address"
```

- [ ] **Step 2: Nachsehen, was im Prompt steht**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; print(anweisungen.hole('rahmen'))"
```
Erwartet: die letzte Zeile lautet
`  No interviewed person recognisable by name or address.`
und das Wort `glorification` kommt nicht vor.

- [ ] **Step 3: Pruefung und Suite-Ausschnitt**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_pruefe_sprache.py
```
Erwartet: alles `passed` -- `test_padua_markiert_jede_unbelegte_angabe` prueft
nur, dass die Felder `beschreibung, ausgeschlossen, auffuehrung, beispiele,
erlaubt` je **eine** `# ANNAHME (unbelegt):`-Zeile tragen; `ausgeschlossen`
im Abschnitt `[orte]` (Zeile 54) traegt sie noch, der Satz bleibt also
erfuellt. (Task 7 ersetzt diesen Test.)

- [ ] **Step 4: Commit**

```bash
git add workshop/padua-2026/profil.toml
git commit -m "$(cat <<'EOF'
padua-profil: Konflikt-Ausschluss nur noch Schutz der Befragten (Punkt 6)

Birk 01.10.2026: "No glorification of violence" raus (Erwachsene,
kuenstlerische Entscheidung), es bleibt "No interviewed person
recognisable by name or address".

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Beispielorte raus -- der Ort wird `<place>`

Birks Punkt 4: die sechs Beispielsaetze bleiben, der Ort wird ein neutraler
Platzhalter wie `<character A>`. Dazu die zwei Stellen aus D2 mit derselben
Begruendung. **Die deutschen Prompts behalten `{{ort_beispiel_N}}`** --
`tests/test_orte_beispiele.py` laeuft gegen das deutsche Vorgabeprofil und
muss gruen bleiben.

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/system.md:160`, `:201`, `:318`
- Modify: `interview_theater/sprachen/en/prompts/phasen/6.md:31`
- Modify: `interview_theater/sprachen/en/prompts/szene.md:111-112`
- Modify: `interview_theater/sprachen/en/prompts/formen/chor.md:32`
- Modify: `interview_theater/sprachen/en/prompts/formen/rap.md:49`
- Modify: `interview_theater/sprachen/en/prompts/theater-tells.md:64`
- Modify: `tests/test_sprache_prompts.py` (Ausnahmeliste + zwei Guards)

- [ ] **Step 1: Die fehlschlagenden Tests schreiben**

In `tests/test_sprache_prompts.py` **nach** dem Block `STRUKTUR_AUSNAHMEN`
(heute Zeile 41-43) einfuegen:

```python
#: Platzhalter, die die englische Fassung bewusst NICHT setzt (Karte P-Fix,
#: Birks Punkt 4 vom 01.10.2026). Im englischen Prompt steht statt eines
#: Beispielortes der neutrale Platzhalter ``<place>`` -- wie ``<character A>``
#: --, weil Beispielorte gemessen nachgeplappert werden (Audit 06.09.2026).
#: Die deutsche Fassung behaelt ``{{ort_beispiel_N}}``: Dortmund bleibt
#: bitgleich. Name -> die Platzhalter, die nur im Deutschen stehen.
PLATZHALTER_AUSNAHMEN: dict[str, set[str]] = {
    "system": {"ort_beispiel_1"},
    "szene": {"ort_beispiel_2", "ort_beispiel_3"},
    "phasen/6": {"ort_beispiel_1"},
    "formen/chor": {"ort_beispiel_1"},
    "formen/rap": {"ort_beispiel_4"},
}
```

Danach `test_gleiche_platzhalter_und_struktur` (heute Zeile 79-89) so
aendern, dass die Ausnahme abgezogen wird -- die Zeile

```python
    assert set(_PLATZ.findall(englisch)) == set(_PLATZ.findall(deutsch))
```

wird zu

```python
    assert set(_PLATZ.findall(englisch)) == (
        set(_PLATZ.findall(deutsch)) - PLATZHALTER_AUSNAHMEN.get(name, set())
    )
```

Und zwei neue Tests anhaengen (hinter
`test_struktur_ausnahmen_sind_begruendet_und_bekannt`):

```python
def test_platzhalter_ausnahmen_sind_ehrlich():
    """Wie ``test_noch_offen_ist_ehrlich``: ein Eintrag darf nur dastehen,
    solange er wirklich im Deutschen steht und im Englischen fehlt."""
    for name, platzhalter in PLATZHALTER_AUSNAHMEN.items():
        deutsch = set(_PLATZ.findall((REPO / f"{name}.md").read_text(encoding="utf-8")))
        englisch = set(_PLATZ.findall((EN / f"{name}.md").read_text(encoding="utf-8")))
        assert platzhalter <= deutsch, (name, "nicht mehr im deutschen Prompt")
        assert not (platzhalter & englisch), (name, "steht doch im englischen")


def test_kein_englischer_prompt_nennt_einen_beispielort():
    """Karte P-Fix: kein ``{{ort_beispiel_N}}`` und kein ``{{orte_beispiele}}``
    mehr in der englischen Schicht.

    Das ist die Gegenprobe zu ``orte.beispiele = []`` im Padua-Profil: ein
    stehengelassener Platzhalter wird nicht ersetzt, sondern bleibt roh im
    Prompt stehen und wird nur geloggt (``anweisungen.fuelle``) -- die Gruppe
    bekaeme dann woertlich "{{ort_beispiel_1}}" zu lesen."""
    for pfad in sorted(EN.rglob("*.md")):
        text = pfad.read_text(encoding="utf-8")
        assert "{{ort_beispiel" not in text, pfad
        assert "{{orte_beispiele" not in text, pfad
    # Und kein ausgeschriebener Beispielort aus dem alten A1-Stand.
    for pfad in sorted(EN.rglob("*.md")):
        text = pfad.read_text(encoding="utf-8").lower()
        for wort in ("bus stop", "piazza", "station concourse"):
            assert wort not in text, (pfad, wort)
```

- [ ] **Step 2: Lauf zum Beweis, dass sie fehlschlagen**

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py -k "platzhalter_ausnahmen_sind_ehrlich or beispielort"
```
Erwartet: `2 failed` -- `test_platzhalter_ausnahmen_sind_ehrlich` meldet
`('system', 'steht doch im englischen')`, `test_kein_englischer_prompt_nennt_einen_beispielort`
meldet `interview_theater/sprachen/en/prompts/formen/chor.md`.

- [ ] **Step 3: Die acht Stellen ersetzen**

`sprachen/en/prompts/system.md`, Zeile 159-161 heute:

```
- **What the group says is material -- the most important kind.** A suggestion
  from the chat ("maybe they meet at the {{ort_beispiel_1}}") is not a
  breach of the rule above but its core: the group brings something in,
```

neu:

```
- **What the group says is material -- the most important kind.** A suggestion
  from the chat ("maybe they meet at <place>") is not a
  breach of the rule above but its core: the group brings something in,
```

`sprachen/en/prompts/system.md`, Zeile 199-201 heute:

```
  ("you"), never a single person. If the content is about an interviewee,
  call them by their interview ("Interview 2", "what Interview 2 says about
  the station") -- that is a factual reference, not a way of addressing anyone.
```

neu:

```
  ("you"), never a single person. If the content is about an interviewee,
  call them by their interview ("Interview 2", "what Interview 2 says about
  <place>") -- that is a factual reference, not a way of addressing anyone.
```

`sprachen/en/prompts/system.md`, Zeile 316-320 heute:

```
  tells you itself in ONE message, with everything that is missing. Your job is
  to suggest in the flow, not to interrogate: "I'd set scene 1 at the
  {{ort_beispiel_1}}, with <character A>, <character B> and <character C> -- does
  that fit?" is one sentence,
  "Where is it set? Who is in it? What happens? Which form?" are four.
```

neu:

```
  tells you itself in ONE message, with everything that is missing. Your job is
  to suggest in the flow, not to interrogate: "I'd set scene 1 at
  <place>, with <character A>, <character B> and <character C> -- does
  that fit?" is one sentence,
  "Where is it set? Who is in it? What happens? Which form?" are four.
```

`sprachen/en/prompts/phasen/6.md`, Zeile 31-32 heute:

```
  Suggest instead of interrogating: "I'd set scene 1 at the {{ort_beispiel_1}},
  with <character A> and <character B> -- does that fit?" is one sentence, "Where
```

neu:

```
  Suggest instead of interrogating: "I'd set scene 1 at <place>,
  with <character A> and <character B> -- does that fit?" is one sentence, "Where
```

`sprachen/en/prompts/szene.md`, Zeile 111-113 heute:

```
  the text, without anyone explaining it: whoever has just come from an argument on the {{ort_beispiel_2}}
  still carries it in their shoulders; whoever is standing at the {{ort_beispiel_3}} days later has
  put it down.
```

neu (Praeposition angepasst, "on the X" -> "at <place>"):

```
  the text, without anyone explaining it: whoever has just come from an argument at <place>
  still carries it in their shoulders; whoever is standing at <place> days later has
  put it down.
```

`sprachen/en/prompts/formen/chor.md`, Zeile 32 heute:

```
({{ort_beispiel_1}}, early evening.)
```

neu:

```
(<place>, early evening.)
```

`sprachen/en/prompts/formen/rap.md`, Zeile 49 heute:

```
({{ort_beispiel_4}}, for two hours now.)
```

neu:

```
(<place>, for two hours now.)
```

`sprachen/en/prompts/theater-tells.md`, Zeile 63-65 heute (**ueber die
Kartenliste hinaus**, D2, gleiche Begruendung):

```
- Bad: It is a cold morning. Nadia thinks back to the years in
  which she ...
- Better: (station concourse, early) -- and the rest is in the lines or
  nowhere.
```

neu:

```
- Bad: It is a cold morning. Nadia thinks back to the years in
  which she ...
- Better: (<place>, early) -- and the rest is in the lines or
  nowhere.
```

- [ ] **Step 4: Lauf zum Beweis, dass es durchgeht**

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_orte_beispiele.py tests/test_profile_geruest.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`. `tests/test_orte_beispiele.py` laeuft gegen das
deutsche Vorgabeprofil und ist von dieser Aenderung nicht beruehrt.

- [ ] **Step 5: Gegenprobe, dass im englischen Prompt wirklich `<place>` steht**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; t=anweisungen.hole('system'); print(t.count('<place>')); print('{{' in t)"
```
Erwartet:
```
3
False
```

- [ ] **Step 6: Commit**

```bash
git add interview_theater/sprachen/en/prompts/system.md \
        interview_theater/sprachen/en/prompts/szene.md \
        interview_theater/sprachen/en/prompts/theater-tells.md \
        interview_theater/sprachen/en/prompts/phasen/6.md \
        interview_theater/sprachen/en/prompts/formen/chor.md \
        interview_theater/sprachen/en/prompts/formen/rap.md \
        tests/test_sprache_prompts.py
git commit -m "$(cat <<'EOF'
en-prompts: der Beispielort wird <place> (Birk, Punkt 4)

Sechs Stellen aus der Karte (system.md:160/318, phasen/6.md:31,
szene.md:111-112, formen/chor.md:32, formen/rap.md:49) und zwei mit
derselben Begruendung (theater-tells.md:64 "station concourse",
system.md:201 "about the station"). Die Beispielsaetze bleiben, der Ort
wird neutral wie <character A>; Nachplappern von Beispielorten ist
gemessen (Audit 06.09.2026). Deutsch behaelt {{ort_beispiel_N}} --
test_orte_beispiele laeuft dort und bleibt gruen, dafuer traegt
test_sprache_prompts jetzt PLATZHALTER_AUSNAHMEN samt Ehrlichkeitstest.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `pruefe_profil` prueft die wirksame Prompt-Ebene

**Ueber die Kartenliste hinaus** (Folge von D1, Begruendung im Kopf unter
"Punkt 5"). Ohne das meldet `pruefe_profil padua-2026` nach Task 6 FEHLER fuer
`{{ort_beispiel_1}}` in den **deutschen** Repo-Prompts, die unter
`sprache.code = "en"` gar nicht gelesen werden.

**Files:**
- Modify: `scripts/pruefe_profil.py:99-121` (`_prompt_texte`)
- Test: `tests/test_profile_geruest.py` (ein Test anhaengen)

**Interfaces:**
- Produces: `pruefe_profil._prompt_texte()` -> `dict[str, str]`, Schluessel
  `"<herkunft>/<relativer pfad>"`, je Prompt-Name **nur die wirksame Ebene**
  (Profil > Sprache > Repo).

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

An das Ende von `tests/test_profile_geruest.py` anhaengen:

```python
def test_die_pruefung_sieht_die_englische_schicht(monkeypatch):
    """Karte P-Fix: unter einem englischen Profil prueft pruefe_profil die
    **wirksame** Prompt-Ebene.

    Bis dahin las ``_prompt_texte`` nur Repo und Profil. Unter
    ``sprache.code = "en"`` gilt fuer jede Datei mit englischer Fassung aber
    diese (``anweisungen._roh``): die deutsche wurde gegen Platzhalter
    geprueft, die sie nie einsetzt, und die englische gar nicht."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    texte = pruefe_profil._prompt_texte()
    dateien = [s for s in texte if s.startswith(("prompts/", "sprache/", "profil/"))]
    namen = [s.split("/", 1)[1] for s in dateien]
    assert "system.md" in namen
    # Genau EINE Ebene je Dateiname -- sonst prueft der Pruefer eine Datei,
    # die unter diesem Profil niemand liest.
    assert len(namen) == len(set(namen)), sorted(
        n for n in namen if namen.count(n) > 1)
    system = next(t for s, t in texte.items() if s.endswith("/system.md"))
    assert "<place>" in system, "die englische Fassung, nicht die deutsche"
    assert "{{ort_beispiel" not in system
```

- [ ] **Step 2: Lauf zum Beweis, dass er fehlschlaegt**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py -k englische_schicht
```
Erwartet: `1 failed` mit `AssertionError: die englische Fassung, nicht die
deutsche`.

- [ ] **Step 3: `_prompt_texte` umstellen**

`scripts/pruefe_profil.py`, Funktion `_prompt_texte` (heute Zeile 99-121)
vollstaendig ersetzen durch:

```python
def _prompt_texte() -> dict[str, str]:
    """Jeder Text, in dem ein Platzhalter stehen kann -- je Prompt-Name nur
    die **wirksame** Ebene.

    Drei Schichten wie ``anweisungen._roh``: Repo, Sprachschicht (Karte A1,
    nur bei ``sprache.code != "de"``), Profil. Die spaetere gewinnt, und zwar
    je Dateiname -- unter einem englischen Profil wird also die englische
    Fassung geprueft und nicht die deutsche, die dort niemand liest. Vorher
    las diese Funktion nur Repo und Profil; dadurch meldete sie Platzhalter
    aus deutschen Dateien, die unter dem Profil unerreichbar sind, und sah
    die englische Schicht nie an (Karte P-Fix, 01.10.2026).

    Dazu die Prompt-Konstanten im Code (``ANWEISUNG_*``)."""
    dateien: dict[str, tuple[str, str]] = {}
    schichten = (
        ("prompts", anweisungen._VERZEICHNIS),
        ("sprache", anweisungen.sprach_verzeichnis()),
        ("profil", anweisungen.profil_verzeichnis()),
    )
    for herkunft, wurzel in schichten:
        if wurzel is None or not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.md")):
            name = str(pfad.relative_to(wurzel)).replace("\\", "/")
            dateien[name] = (herkunft, pfad.read_text(encoding="utf-8"))
    texte: dict[str, str] = {
        f"{herkunft}/{name}": text for name, (herkunft, text) in dateien.items()
    }
    for modul in (szenenfolge, knoepfe):
        for feld in sorted(dir(modul)):
            if not feld.startswith("ANWEISUNG_"):
                continue
            wert = getattr(modul, feld)
            if isinstance(wert, str):
                # Ueber den Sprachzugriff (Karte A1), wo das Modul schon
                # einen hat: unter einem englischen Profil wird der
                # englische Auftrag auf Platzhalter geprueft.
                wert = getattr(getattr(modul, "T", modul), feld)
                texte[f"{modul.__name__.split('.')[-1]}.{feld}"] = wert
    return texte
```

- [ ] **Step 4: Lauf zum Beweis, dass es durchgeht**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_pruefe_sprache.py
$PY -m scripts.pruefe_profil padua-2026
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: Tests `passed`; beide Profilpruefungen enden mit einer Zeile
`padua-2026: in Ordnung` bzw. `dortmund-2026: in Ordnung` (ggf. mit
`, N Hinweis(e)`), Exit-Code 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/pruefe_profil.py tests/test_profile_geruest.py
git commit -m "$(cat <<'EOF'
pruefe_profil: Platzhalter auf der wirksamen Prompt-Ebene pruefen

_prompt_texte las Repo und Profil, nicht die Sprachschicht. Unter
sprache.code = "en" gilt aber die englische Fassung jeder Datei
(anweisungen._roh) -- geprueft wurde also die unerreichbare deutsche,
und die englische nie. Jetzt gewinnt je Dateiname die spaetere Schicht,
wie beim Lesen. Unter Dortmund (keine Sprachschicht) aendert sich nichts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Die Profilwerte nach Birks Punkten 1, 3, 4 und 5 (und D5)

**Files:**
- Modify: `workshop/padua-2026/profil.toml` (Kopfkommentar, `zielgruppe.traeger`,
  `[orte]`, `[konflikt] erlaubt`, `projekt.kurzbeschreibung`)

- [ ] **Step 1: `zielgruppe.traeger` ohne Spielort** (D5, ueber die Kartenliste hinaus)

Zeile 49-50 heute:

```toml
# V1: Akademie des National Theatre of the Veneto Region, Teatro Verdi, Padova.
traeger = "academy of the National Theatre of the Veneto Region, Teatro Verdi, Padova"
```

neu:

```toml
# V1: Akademie des National Theatre of the Veneto Region, Teatro Verdi, Padova.
# Der Spielort steht hier NICHT (Birk 01.10.2026, Punkt 3): die Werkschau
# findet in oder an der Akademie statt, nicht im Teatro Verdi. Institution
# bleibt, Haus faellt.
traeger = "academy of the National Theatre of the Veneto Region, Padova"
```

- [ ] **Step 2: `[orte]` auf Punkt 1, 2, 3 und 4**

Der ganze Abschnitt `[orte]` (heute Zeile 52-58) wird ersetzt. Heute:

```toml
[orte]
beschreibung = "places from everyday life in Padua and Venice, where the people the group interviewed live and work -- which ones, the group decides (no example places from these instructions)."   # ANNAHME (unbelegt): V1 belegt nur, dass die Interviews in Padua/Venedig stattfinden; dass das Stueck dort spielt, ist abgeleitet -- die Geschichten sind ausdruecklich fiktiv (V1 "NICHT dokumentarisches Theater")
ausgeschlossen = ["the real home or workplace of an interviewed person, recognisable by name or address"]   # ANNAHME (unbelegt): Dortmunds Liste (Club, Disko, Alkohol ...) war Jugendschutz fuer 15-18-Jaehrige und passt nicht auf Erwachsene; ersetzt durch einen Schutz der Befragten, abgeleitet aus V1 "fiktiv, NICHT dokumentarisch" und E8 (V2) -- Birk entscheidet, ob hier etwas anderes oder gar nichts stehen soll
auffuehrung = "at the public showcase on the last day of the workshop, 10-15 minutes per group, in front of AI-generated projected backgrounds, at Teatro Verdi, Padova"   # ANNAHME (unbelegt): Werkschau Tag 5, 10-15 Min je Gruppe, KI-Hintergruende stehen in V1; der Ort der Werkschau nicht (V1 offene Punkte: "Publikum & Zugang klaeren") -- "at Teatro Verdi" ist aus dem Workshop-Ort geschlossen
# Orte, die in den Prompts als BEISPIEL vorkommen -- nicht die Orte des
# Stuecks. Englisch, weil sie in englischen Prompt-Saetzen stehen.
beispiele = ["bus stop", "piazza", "café", "station"]   # ANNAHME (unbelegt): Wahl von Karte A1, nicht aus dem Vault; stehen nur in Beispielsaetzen der Prompts
```

neu:

```toml
[orte]
# Birk 01.10.2026 (Punkt 1): offen formuliert. Die Orte waehlt die Gruppe aus
# ihren Interviews, erfunden oder real; Padua ist die Herkunft des Materials
# und kein Pflicht-Schauplatz. "Venice" ist raus -- laut Michele bleiben die
# Interviews im Zehn-Minuten-Umkreis des Theaters in Padua.
# Satzglied, kein Satz: die Vorlage schreibt "**Where it is set:** {{orte}}
# **Not:** ...", der Punkt steht deshalb hier.
beschreibung = "wherever the group decides, chosen from its interviews -- invented or real; the material comes from Padua, but the play does not have to be set there (no example places from these instructions)."
# Birk 01.10.2026 (Punkt 2): so lassen. Kein Jugendschutz (Erwachsene), Zweck
# ist der Schutz der Befragten.
ausgeschlossen = ["the real home or workplace of an interviewed person, recognisable by name or address"]
# Birk 01.10.2026 (Punkt 3), woertlich. Teatro Verdi raus, "AI-generated
# projected backgrounds" raus. Ohne Schlusspunkt: die Vorlage setzt ihn
# ("Where it is shown: {{auffuehrungsort}}.").
auffuehrung = "at the public showcase on the last day of the workshop, roughly 10-15 minutes per group; form, place and means are open -- anywhere in or right around the academy (black box, another room, outside in front of the building), with or without projection, sound or just voices"
# Birk 01.10.2026 (Punkt 4): keine Beispielorte. Im englischen Prompt steht
# statt eines Ortes der neutrale Platzhalter "<place>" -- Nachplappern von
# Beispielorten ist gemessen (Audit 06.09.2026). Die Liste bleibt als
# **leere** Liste stehen und wird nicht geloescht: ein fehlender Schluessel
# wuerde ueber workshop._vereinige die deutsche Vorgabeliste
# ("Bushaltestelle" ...) erben.
beispiele = []
```

- [ ] **Step 3: `[konflikt] erlaubt` leeren** (Punkt 5)

Zeile 60-61 heute:

```toml
[konflikt]
erlaubt = "whatever the interviews bring up; the group sets the theme and its framing itself"   # ANNAHME (unbelegt): V1 nennt keinen Konfliktrahmen fuer die Buehne (V1 offene Punkte: "Interview-Thema / Framing mit den Studierenden setzen"); creative ownership, environmental cost, digitale Souveraenitaet sind die Reflexionsebene des Workshops, kein Stoff des Stuecks -- deshalb bewusst nicht hier
```

neu (der `ausgeschlossen`-Block aus Task 3 bleibt darunter stehen):

```toml
[konflikt]
# Birk 01.10.2026 (Punkt 5): leer. Dann faellt der Teilsatz in den englischen
# Vorlagen weg, und es bleibt "Conflict may be serious."
# (workshop.platzhalter: konflikt_erlaubt_strich / _klammer). Die
# Workshop-Themen (KI, Klima, Arbeit ...) gehoeren NICHT in den Prompt.
# Leerer String und kein geloeschter Schluessel: workshop._vereinige wuerde
# sonst die Dortmunder Liste erben.
erlaubt = ""
```

- [ ] **Step 4: "Venice" aus `projekt.kurzbeschreibung`**

Zeile 69 heute:

```toml
kurzbeschreibung = "short fictional plays based on interviews with real people in Padua and Venice - the voices we collect are raw material for new stories, not a documentary, and the plays are shown at a public showcase at the end of the workshop"
```

neu:

```toml
kurzbeschreibung = "short fictional plays based on interviews with real people in Padua - the voices we collect are raw material for new stories, not a documentary, and the plays are shown at a public showcase at the end of the workshop"
```

- [ ] **Step 5: Den Kopfkommentar nachziehen**

`workshop/padua-2026/profil.toml`, Zeile 5-14 heute:

```toml
# Karte A1 hat Sprache, Phasen und Formen gesetzt; den Inhalt hat Karte P
# (01.10.2026) aus zwei Vault-Dateien gefuellt -- und nur aus diesen:
#
#   V1 = projekte/padua-workshop/padua-workshop.md
#   V2 = projekte/padua-workshop/notes/inscribe-padua-todo.md
#
# Belegte Zeilen nennen ihre Quelle ("# V1: ..."). Jede Angabe, die dort
# NICHT woertlich oder eindeutig steht, traegt den Kommentar
# "# ANNAHME (unbelegt): ..." -- Birk nimmt sie am Prompt-Dump ab
# (docs/prompt-audit/2026-09-30-padua/BEFUND.md).
```

neu:

```toml
# Karte A1 hat Sprache, Phasen und Formen gesetzt; den Inhalt hat Karte P
# (01.10.2026) aus zwei Vault-Dateien gefuellt -- und nur aus diesen:
#
#   V1 = projekte/padua-workshop/padua-workshop.md
#   V2 = projekte/padua-workshop/notes/inscribe-padua-todo.md
#
# Belegte Zeilen nennen ihre Quelle ("# V1: ..."). Die sechs Angaben, die
# Karte P als "# ANNAHME (unbelegt)" markiert hatte, sind am 01.10.2026 von
# Birk **abgenommen** und tragen seitdem seine Entscheidung als Kommentar
# ("Birk 01.10.2026 (Punkt N)"). Der Nachweis am Prompt-Dump:
# docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md.
```

Die Zeile 27 (`beschreibung = "Five-day workshop ... (Teatro Verdi, Padova) ..."`)
bleibt **unveraendert**: der Platzhalter `{{beschreibung}}` wird von keinem
Prompt benutzt (gemessen -- Gegenprobe in Step 6), das Feld steht nur in der
Profildatei und in der Pruefausgabe.

- [ ] **Step 6: Gegenproben**

```
grep -rn "ANNAHME" workshop/padua-2026/profil.toml
```
Erwartet: **nur** die Kopfzeile, die das Wort erklaert ("die Karte P als
\"# ANNAHME (unbelegt)\" markiert hatte") -- keine Wertzeile mehr.

```
grep -rn "{{beschreibung}}" interview_theater/prompts interview_theater/sprachen
```
Erwartet: keine Ausgabe (Exit-Code 1). Belegt, dass `beschreibung` in keinen
Prompt geht.

```
$PY -m scripts.pruefe_profil padua-2026
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: beide `in Ordnung`, Exit 0.

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; print(anweisungen.hole('rahmen')); print('---'); print(anweisungen.hole('rahmen-kurz'))"
```
Erwartet: kein `Teatro Verdi`, kein `Venice`, kein `projected backgrounds`,
kein `glorification`, kein `()`, kein `serious --`, kein `{{`.

- [ ] **Step 7: Commit**

```bash
git add workshop/padua-2026/profil.toml
git commit -m "$(cat <<'EOF'
padua-profil: Birks Abnahme vom 01.10.2026 (Punkte 1, 3, 4, 5)

Spielorte offen formuliert (Orte waehlt die Gruppe aus den Interviews,
Venice raus); Werkschau woertlich nach Punkt 3 (kein Teatro Verdi, keine
KI-Projektion); Beispielorte als leere Liste (im Prompt steht <place>);
konflikt.erlaubt leer. Dazu zielgruppe.traeger ohne Spielort und
"Venice" aus projekt.kurzbeschreibung. Alle sechs ANNAHME-Kommentare
ersetzt durch die Entscheidung mit Datum.

Leere Liste bzw. leerer String und KEIN geloeschter Schluessel:
workshop._vereinige legt ein Profil Ebene fuer Ebene ueber
VORGABE_WERTE, ein fehlender Schluessel wuerde die Dortmunder Werte
erben.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Die Zusicherungen zum Padua-Profil nachziehen

Zwei Tests in `tests/test_profile_geruest.py` behaupten den alten Stand und
muessen den neuen behaupten -- sonst ist die Abnahme nirgends festgehalten.

**Files:**
- Modify: `tests/test_profile_geruest.py:73-83` (`test_padua_markiert_jede_unbelegte_angabe`)
- Modify: `tests/test_profile_geruest.py:152-165` (`test_padua_traegt_seine_eigene_sprache_und_orte`)

- [ ] **Step 1: Den ANNAHME-Test umdrehen**

`tests/test_profile_geruest.py`, heute Zeile 73-83:

```python
def test_padua_markiert_jede_unbelegte_angabe():
    """Karte P: was nicht woertlich oder eindeutig aus dem Vault stammt, traegt
    den Kommentar "ANNAHME (unbelegt)" -- kein Platzhalter von A1 bleibt stehen."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "korpus").exists(), "der englische Korpus liegt unter korpus/en/ (D8)"
    text = (verz / "profil.toml").read_text(encoding="utf-8")
    assert "Platzhalter A1" not in text
    annahmen = [z for z in text.splitlines() if "# ANNAHME (unbelegt):" in z]
    felder = {z.split("=", 1)[0].strip() for z in annahmen}
    assert {"beschreibung", "ausgeschlossen", "auffuehrung", "beispiele",
            "erlaubt"} <= felder, felder
```

ersetzen durch:

```python
def test_padua_hat_keine_unbelegte_annahme_mehr():
    """Karte P-Fix: Birk hat die sechs ANNAHME-Angaben am 01.10.2026
    abgenommen -- seitdem traegt jede ihre Entscheidung statt ihrer Annahme.

    Vorher hielt dieser Test fest, dass die Markierung **da** ist (Karte P);
    jetzt haelt er fest, dass sie **weg** ist und keine Wertzeile sie noch
    traegt. Die Entscheidungen: /mnt/.../padua-fabrik/entscheidungen-p.md,
    der Nachweis docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "korpus").exists(), "der englische Korpus liegt unter korpus/en/ (D8)"
    text = (verz / "profil.toml").read_text(encoding="utf-8")
    assert "Platzhalter A1" not in text
    annahmen = [z for z in text.splitlines()
                if "# ANNAHME (unbelegt):" in z and "=" in z.split("#", 1)[0]]
    assert annahmen == [], annahmen
    assert "Birk 01.10.2026" in text


def test_padua_traegt_birks_abgenommene_werte():
    """Die sieben Entscheidungen vom 01.10.2026 als Zusicherung -- sie stehen
    sonst nur in einem Kommentar."""
    profil = workshop.lade("padua-2026")
    orte = profil.wert("orte.beschreibung")
    assert "Venice" not in orte and "Venedig" not in orte
    assert "the group decides" in orte or "the group" in orte
    auffuehrung = profil.wert("orte.auffuehrung")
    assert "Teatro Verdi" not in auffuehrung
    assert "projected backgrounds" not in auffuehrung
    assert "black box" in auffuehrung
    assert profil.wert("konflikt.erlaubt") == ""
    assert profil.wert("konflikt.ausgeschlossen") == (
        "No interviewed person recognisable by name or address")
    assert profil.wert("orte.ausgeschlossen") == [
        "the real home or workplace of an interviewed person, "
        "recognisable by name or address"]
    assert "Teatro Verdi" not in profil.wert("zielgruppe.traeger")
    assert "Venice" not in profil.wert("projekt.kurzbeschreibung")
```

- [ ] **Step 2: Die Beispielort-Zusicherung umdrehen**

`tests/test_profile_geruest.py`, heute Zeile 160-165 (am Ende von
`test_padua_traegt_seine_eigene_sprache_und_orte`):

```python
    assert profil.wert("datenschutz.pseudonyme") is True
    # Englische Beispielorte: sie stehen in einem englischen Prompt-Satz
    # ("maybe they meet at the bus stop"); ein italienisches Wort dort waere
    # ein Fremdkoerper (Review A1). Karte P kann sie aus dem Vault ersetzen.
    assert tuple(profil.wert("orte.beispiele")) == (
        "bus stop", "piazza", "café", "station")
```

ersetzen durch:

```python
    assert profil.wert("datenschutz.pseudonyme") is True
    # Keine Beispielorte mehr (Birk 01.10.2026, Punkt 4): im englischen
    # Prompt steht "<place>". Die **leere Liste** steht ausdruecklich da --
    # ein geloeschter Schluessel wuerde ueber workshop._vereinige die
    # deutschen Vorgabewerte ("Bushaltestelle" ...) erben.
    assert profil.wert("orte.beispiele") == []
    assert "beispiele" in profil.werte["orte"], "der Schluessel bleibt stehen"
```

- [ ] **Step 3: Lauf**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_pruefe_sprache.py tests/test_sprache_prompts.py tests/test_rahmen.py tests/test_orte_beispiele.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_profile_geruest.py
git commit -m "$(cat <<'EOF'
tests: die Padua-Abnahme vom 01.10.2026 festhalten

test_padua_markiert_jede_unbelegte_angabe hielt fest, dass die
ANNAHME-Markierung da ist. Sie ist abgenommen -- der Test haelt jetzt
fest, dass keine Wertzeile sie noch traegt, und ein zweiter haelt die
sieben Entscheidungen im Wortlaut (Orte offen, kein Teatro Verdi, keine
Projektion, konflikt.erlaubt leer, Beispielorte leere Liste).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: `anweisung.md` nach Punkt 7, und c1 in `system.md`

Birks Punkt 7 entscheidet c1 ("ONE thing" gegen "two to three options") in
Richtung Optionen -- und fuehrt die Winkel-Regel ein, die `system.md:72-76`
heute ausschliesst.

**Files:**
- Modify: `workshop/padua-2026/prompts/anweisung.md:3`
- Modify: `interview_theater/sprachen/en/prompts/system.md:67-68`
- Modify: `interview_theater/sprachen/en/prompts/system.md:72-76`

- [ ] **Step 1: `anweisung.md`**

Datei heute (eine Absatzzeile, Zeile 3):

```
The group are acting students in professional training, not an amateur group: talk to them the way a dramaturg talks to colleagues -- direct, precise, in plain English (for most of them it is not their first language), without explaining basic theatre terms. You are their dramaturgical sparring partner: you suggest and push back, but the play, its themes and every decision belong to them. You never invent what is not in the material or the chat, never name a real person, and never claim to have saved anything. You ask at most one open question per message, at the end -- and when you offer options, they are variants of the group's own idea, not yours.
```

neu -- alles ab `You ask at most one open question` ist Birks Text aus Punkt 7,
woertlich:

```
The group are acting students in professional training, not an amateur group: talk to them the way a dramaturg talks to colleagues -- direct, precise, in plain English (for most of them it is not their first language), without explaining basic theatre terms. You are their dramaturgical sparring partner: you suggest and push back, but the play, its themes and every decision belong to them. You never invent what is not in the material or the chat, never name a real person, and never claim to have saved anything. You ask at most one open question per message, at the end. When you offer options, at least one may take the group somewhere they haven't been yet -- a surprising or even contrary angle -- as long as it grows out of the interview material or the group's theme. Don't flag it as the bold one; it simply sits among the others. What you never do is invent topics, quotes or stories that have no root in the material.
```

- [ ] **Step 2: c1 -- `system.md:62-68`**

Heute:

```
Form of your messages: **plain text**, without Markdown -- no asterisks,
no hash signs, no underscores for emphasis. Telegram shows them raw
("**important**" then appears literally like that in the chat). Emphasis
works through line breaks and order, not through symbols. Lists with "-"
are allowed. In short: a message you can read at a glance on a phone --
under 500 characters if possible. Suggest ONE thing, not three to choose
from.
```

neu (letzter Satz an Zeile 75 angeglichen):

```
Form of your messages: **plain text**, without Markdown -- no asterisks,
no hash signs, no underscores for emphasis. Telegram shows them raw
("**important**" then appears literally like that in the chat). Emphasis
works through line breaks and order, not through symbols. Lists with "-"
are allowed. In short: a message you can read at a glance on a phone --
under 500 characters if possible. One question, and two to three options
to choose from -- see below.
```

- [ ] **Step 3: D6 -- `system.md:72-76` neutral**

Heute:

```
**You ask first, you suggest afterwards.** In EVERY phase: ONE open
question about the group's idea. If an answer comes, you don't invent
anything new alongside it -- you take exactly what they said and flesh it
out into **two to three options that are variants of the SAME idea**. Multiple
choice about their idea, not about yours.
```

neu ("You ask first, you suggest afterwards" bleibt; die Winkel-Regel steht ab
jetzt nur in `anweisung.md`):

```
**You ask first, you suggest afterwards.** In EVERY phase: ONE open
question about the group's idea. If an answer comes, you build on it --
you take what they said and flesh it out into **two to three options**. The
options grow out of their answer and out of their material, never out of a
topic of your own.
```

- [ ] **Step 4: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; t=anweisungen.system('padua1', 1); print('ONE thing' in t); print('variants of the SAME idea' in t); print(t.rstrip().endswith('no root in the material.'))"
```
Erwartet:
```
False
False
True
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_sprache_prompts.py tests/test_pruefe_sprache.py tests/test_anweisungen.py tests/test_anweisungen_profil.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`.
(`test_padua_haengt_seine_verhaltensanweisung_an_jeden_gespraechsprompt` prueft
unter anderem, dass `anweisung.md` das Wort `VORSCHLAG` **nicht** traegt --
Birks Text traegt es nicht.)

- [ ] **Step 5: Commit**

```bash
git add workshop/padua-2026/prompts/anweisung.md \
        interview_theater/sprachen/en/prompts/system.md
git commit -m "$(cat <<'EOF'
anweisung + system.md: Punkt 7 und Widerspruch c1

anweisung.md: der Schluss ab "You ask at most one open question" ist
woertlich Birks Text vom 01.10.2026 -- eine der Optionen darf einen
ueberraschenden oder gegenlaeufigen Winkel nehmen, solange er aus dem
Material oder dem Thema der Gruppe waechst.

Damit ist c1 entschieden: system.md:67 sagt nicht mehr "Suggest ONE
thing, not three to choose from", sondern dasselbe wie :75 (Optionen).
Und :72-76 wird neutral -- "variants of the SAME idea ... not about
yours" widersprach Punkt 7. Die Winkel-Regel steht ab jetzt an genau
einer Stelle im Prompt, in anweisung.md, und die steht am Ende
(SPEC 6.1).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: c2, c4 und c9 in `phasen/6.md`

Drei Saetze der Phase-6-Anweisung behaupten etwas, das der Code anders macht.

**Code-Belege** (vor dem Aendern selbst nachsehen, die Zeilen stehen hier):

- **c4** -- `interview_theater/kurzgeschichte.py:72-82` (`ANWEISUNG`: "EINE
  zusammenhaengende Kurzgeschichte"), `interview_theater/szene.py:2241-2246`
  ("In Phase 6 geht IMMER prosa.md in die Systemanweisung"),
  `workshop/padua-2026/phasen.toml:49` (`satz = "Tell each scene as prose --
  what happens, still without a form."`).
- **c2** -- `interview_theater/kurzgeschichte.py:168-186`
  (`lege_szenen_an`: "``form`` bleibt leer: sie entscheidet die Gruppe im
  Feinschliff"), `interview_theater/szenenfolge.py:315`/`:334-335`
  (die Szenenfolge schreibt `form_vorschlag`, `form` bleibt leer),
  `interview_theater/szene.py:2243-2245`,
  `interview_theater/sprachen/en/prompts/system.md:17` ("6 Scenes as Story --
  tell each scene as prose, still without a form").
- **c9** -- `interview_theater/kontext.py:788-798` (`_baue_figurenhinweis`
  laeuft ab `kernpaket_erlaubt`, also ab Phase `PHASE_KERNPAKET = 5`,
  `kontext.py:566`/`:584-590`), `interview_theater/sprachen/en/texte.toml:851`
  (`["kontext"] _FIGURENHINWEIS`: "These characters are still missing the
  interview they speak from ... ONE sentence about it"),
  `interview_theater/knoepfe/figuren.py:358-368` (`ebene2_erlaubt`: die
  Interview-Zuordnung laeuft erst ab Phase 5, nicht in 4).

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/phasen/6.md:3-5`, `:34-36`, `:67-69`

- [ ] **Step 1: c4 -- "scene by scene" gegen "ONE short story in one go"**

Zeile 3-5 heute:

```
The setting, characters, story and scene sequence are in place, and the material has
sharpened them. Now the texts are written -- scene by scene, in
the order of the play.
```

neu:

```
The setting, characters, story and scene sequence are in place, and the material has
sharpened them. Now the story is written -- in ONE go, as one
continuous short story in sections, in the order of the play.
```

- [ ] **Step 2: c2 -- die Form ist in Phase 6 noch nicht entschieden**

Zeile 34-36 heute:

```
- **The form for each scene is already settled** ({{formen_liste}}) -- it
  was decided with the story. The group can change it at any time
  with the button; you don't ask about it on your own.
```

neu (`{{formen_liste}}` bleibt stehen -- die Platzhalter-Paritaet zur
deutschen Fassung haengt daran):

```
- **The form for each scene is NOT settled yet** ({{formen_liste}}) -- it is
  chosen scene by scene in the polish phase, by button. The scene sequence
  may already carry a suggested form; a suggestion is not a decision, and you
  don't ask about the form on your own here.
```

- [ ] **Step 3: c9 -- die Sprechweise, so wie der Prompt sie wirklich bekommt**

Zeile 67-69 heute:

```
- **No question about a character's way of speaking.** The style was decided in phase 4
  (06.09.2026 12:20) and is in the progress; asking about it
  here would mean reopening an agreement.
```

neu:

```
- **You don't reopen a character's way of speaking.** The speech style was
  decided in phase 4 and is in the progress; asking about it again here
  would mean reopening an agreement. The ONE exception is the hint in your
  context: if it lists characters that are still missing the interview they
  speak from, you may ask about that -- one sentence, exactly as the hint
  says, and only for the characters it names.
```

- [ ] **Step 4: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; t=anweisungen.hole('phasen/6'); print('scene by scene, in' in t); print('already settled' in t); print('No question about' in t); print('{{' in t)"
```
Erwartet:
```
False
False
False
False
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_profile_geruest.py tests/test_pruefe_sprache.py tests/test_phasen_profil.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`. Insbesondere
`test_englische_phasen_sind_fokus_kein_kaefig` (der Abschnitt "What you don't
start on your own:" und der Schlusssatz bleiben erhalten) und
`test_englische_phasen_bewerben_keinen_befehl` (kein `/befehl` im Text).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/sprachen/en/prompts/phasen/6.md
git commit -m "$(cat <<'EOF'
en-phasen/6: c2, c4 und c9 nach der Code-Wahrheit

c4: "scene by scene" raus -- Phase 6 schreibt EINE Kurzgeschichte am
Stueck (kurzgeschichte.ANWEISUNG, szene.py:2241-2246, phasen.toml:49),
und :63 sagte es zwei Absaetze spaeter schon.

c2: "The form for each scene is already settled" war falsch -- in Phase
6 bleibt szene.form NULL (kurzgeschichte.lege_szenen_an), die
Szenenfolge schreibt form_vorschlag (szenenfolge.py:315/334), bestaetigt
wird die Form per Knopf im Feinschliff.

c9 (P-Fix-Haelfte, M1-Fix hat texte.toml:926/934 und szene.py): der
Phase-6-Prompt bekommt sehr wohl den Figurenhinweis, der nach dem
Quell-Interview fragt -- ab Phase 5, kontext._baue_figurenhinweis ueber
kernpaket_erlaubt. Der Satz nennt diese eine Ausnahme jetzt.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: c3 -- wer die USA-Frage stellt

**Code-Belege:** `interview_theater/knoepfe/stationen.py:171-189` ("**Die
USA-Frage steht beim EINTRITT**", `nummer == PHASE_SZENEN`,
`knoepfe/texte.py:455`: `PHASE_SZENEN = 6`) und
`interview_theater/szene.py:2488-2496` (ist sie beim Start eines Laufs noch
offen, stellt sie **der Lauf**). Beide Wege existieren; `system.md:376` nennt
den Regelweg richtig, `:322` nur den Rueckfall.

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/system.md:322-324`

- [ ] **Step 1: Den Satz richtig stellen**

Zeile 322-325 heute:

```
**The question about the US model is asked by the scene run, not by you.** Before the
first scene a system message appears once ("Before I write the first
scene, a decision for you ... Do you want that? Say yes or
no."). **You do NOT repeat it, you do NOT summarise it, you do NOT announce
```

neu:

```
**The question about the US model is never asked by you.** It appears once as
a system message with two buttons underneath when the group enters the scene
phase -- and once more from the scene run if it is still open when a scene is
about to be written ("Before I write the first scene, a decision for you ...
Do you want that? Say yes or
no."). **You do NOT repeat it, you do NOT summarise it, you do NOT announce
```

- [ ] **Step 2: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; t=anweisungen.hole('system'); print('asked by the scene run, not by you' in t); print('when the group enters the scene phase' in t); print('{{' in t)"
```
Erwartet:
```
False
True
False
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_pruefe_sprache.py tests/test_profile_geruest.py
```
Erwartet: alles `passed`.

- [ ] **Step 3: Commit**

```bash
git add interview_theater/sprachen/en/prompts/system.md
git commit -m "$(cat <<'EOF'
en-system: c3 -- die USA-Frage steht beim Eintritt in Phase 6

:322 sagte "asked by the scene run ... before the first scene", :376
"when entering the scene phase". Der Code macht beides, in dieser
Rangfolge: knoepfe/stationen.py:171-189 stellt sie beim Eintritt in
PHASE_SZENEN mit zwei Knoepfen, szene.py:2488-2496 nur noch, wenn sie
dann immer noch offen ist. Der Satz nennt jetzt beides und behaelt das
Entscheidende -- nie der Gespraechs-Bot.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: c5 und c6 in `formen/prosa.md`

**Code-Belege:**

- **c5** -- `interview_theater/kurzgeschichte.py:79-82` ("**Du waehlst die Zahl
  der Abschnitte selbst.** ... Eine Szenenfolge aus der Planung ist eine
  Anregung, keine Vorgabe"), `kurzgeschichte.py:168-186`
  (`lege_szenen_an` gleicht **ergaenzend** ab: "gleiche Nummer ->
  aktualisieren, fehlende -> ergaenzen, ueberzaehlige -> stehen lassen").
  Wo die Zahl **doch** bindend ist, sagt es der **Auftrag**:
  `sprachen/en/texte.toml:730` (`["kuerzung"] TEXT_NOTIZ_PROSA`: "Keep exactly
  {anzahl} sections with their titles and in their order"), und
  `interview_theater/nachpass.py:350-353` verwirft einen Lauf mit anderer
  Abschnittszahl (`VORFALL_ABSCHNITTSZAHL`, `nachpass.py:242`).
- **c6** -- `interview_theater/kurzgeschichte.py:137-165` (`zerlege` liest
  **nur** Ueberschrift + `ZUSAMMENFASSUNG:`/`Summary:`, kein `TITEL:`, kein
  `ANDERS GEMACHT:`), gegen `interview_theater/szene.py` (Einzelszene, liest
  die vier Pflichtzeilen). Also: `ANWEISUNG` gibt die Form des
  Ganz-Laufs, `prosa.md`s "Your output" die der Einzelszene.

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/formen/prosa.md:24-33` (Regel 3)
- Modify: `interview_theater/sprachen/en/prompts/formen/prosa.md:41-42` (Regel 6)
- Modify: `interview_theater/sprachen/en/prompts/formen/prosa.md:56-59` (Abschnitt "Your output")

**Achtung:** `tests/test_sprache_prompts.py::test_gleiche_platzhalter_und_struktur`
zaehlt Ueberschriften (`^#{1,6} `), Code-Zaeune (`^```()`) und
JSON-Beispielzeilen und vergleicht sie mit der deutschen Fassung. **Keine neue
Ueberschrift, keinen neuen Code-Zaun anlegen** -- es wird nur Fliesstext
geaendert. `tests/test_sprache_prompts.py::test_maschinenmarker_bleiben_wortgleich`
verlangt, dass `TITEL:`, `KURZ:`, `ZUSAMMENFASSUNG:` und `ANDERS GEMACHT:` in
`formen/prosa` **stehen bleiben**.

- [ ] **Step 1: c5 -- Regel 3**

Zeile 24-33 heute:

```
3. **The length depends on the task.** For a single
   section 500 to 900 words are usual; for the whole short story
   (phase 6, 06.09.2026, 11:50) it is 1,500 to 3,500 words across
   all sections. The Herkules measure doesn't apply here either.
   **If a scene sequence already exists, it is binding** (06.09.2026, after
   the live case of group 1): as many sections as planned scenes, in
   the same order, each section tells what was set for this scene.
   You don't invent an extra scene, you don't cut one and
   you don't reorder any. Only if there is **no** sequence do you decide the
   number of sections from the story (typically three to seven).
```

neu:

```
3. **The length depends on the task.** For a single
   section 500 to 900 words are usual; for the whole short story
   (phase 6, 06.09.2026, 11:50) it is 1,500 to 3,500 words across
   all sections. The Herkules measure doesn't apply here either.
   **You decide the number of sections from the story** (typically three to
   seven): a scene sequence from the planning is a suggestion, not a
   requirement -- if it fits, use it; if it doesn't, do better. Where the
   number IS fixed, the job says so in as many words (a revision, a
   shortening of an existing story): then you keep exactly those sections,
   with their titles and in their order, and you shorten or rework inside
   them.
```

- [ ] **Step 2: c6 -- Regel 6**

Zeile 41-42 heute:

```
6. **The heading is plain.** Above the scene there is only `Scene N — Title`,
   no place/time block in theatre format.
```

neu:

```
6. **The heading is plain.** Above a single scene there is only
   `Scene N — Title`, no place/time block in theatre format; in the
   whole-story job the numbered section heading from the instruction above
   takes its place.
```

- [ ] **Step 3: c6 -- der Abschnitt "Your output"**

Zeile 56-59 heute:

```
## Your output

Plain text, no JSON, no explanation before or after. Exactly in this
form:
```

neu (ein Satz dazu, **keine** neue Ueberschrift, **kein** neuer Zaun):

```
## Your output

This is the form for **one** scene. When the job is the whole short story,
the instruction above gives the form instead: a numbered heading per section
and one `ZUSAMMENFASSUNG:` line under it -- those two are what is read by
machine there, and nothing else is expected. For a single scene:
plain text, no JSON, no explanation before or after. Exactly in this
form:
```

- [ ] **Step 4: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen; t=anweisungen.hole('formen/prosa'); print('it is binding' in t); print('This is the form for' in t); print(all(m in t for m in ('TITEL:','KURZ:','ZUSAMMENFASSUNG:','ANDERS GEMACHT:')))"
```
Erwartet:
```
False
True
True
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_pruefe_sprache.py tests/test_teil4_kurzgeschichte.py tests/test_szene_prosa.py tests/test_nachpass_prosa.py tests/test_laengen_prosa.py tests/test_kuerzung.py
```
Erwartet: alles `passed`. `tests/test_teil4_kurzgeschichte.py` ist der Test,
der die Abschnittszahl misst (vier Ueberschriften -> vier Szenen, sechs ->
sechs) -- er haengt am Parser, nicht am Prompt-Wortlaut, und muss gruen
bleiben.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/sprachen/en/prompts/formen/prosa.md
git commit -m "$(cat <<'EOF'
en-formen/prosa: c5 und c6 nach der Code-Wahrheit

c5: "If a scene sequence already exists, it is binding" stand gegen
kurzgeschichte.ANWEISUNG ("Du waehlst die Zahl der Abschnitte selbst")
und gegen lege_szenen_an, das ERGAENZEND abgleicht. Wo die Zahl bindend
ist, sagt es der Auftrag -- kuerzung.TEXT_NOTIZ_PROSA nennt sie
ausdruecklich, und nachpass verwirft einen Lauf mit anderer
Abschnittszahl. Genau das steht jetzt in Regel 3.

c6: zwei Ausgabeformate in einem Prompt. kurzgeschichte.zerlege liest im
Ganz-Lauf nur Ueberschrift + ZUSAMMENFASSUNG:, die vier Pflichtzeilen
(TITEL:/KURZ:/ZUSAMMENFASSUNG:/ANDERS GEMACHT:) liest szene.py fuer die
Einzelszene. "Your output" und Regel 6 sagen jetzt, welche Form fuer
welchen Auftrag gilt -- das Modell muss nicht mehr raten.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: c7 -- die Tells und der Prosa-Auftrag

**Code-Belege:** `interview_theater/szene.py:338-343` ("Die Prosafassung
(Phase 6) ist die Ausnahme ... **Die Tells bleiben: sie sind Sprachhygiene und
gelten fuer jeden Text**") und `szene.py:351-354` (im Prosa-Fall genau zwei
Teile: `formen/prosa` + `theater-tells`), dazu
`interview_theater/kurzgeschichte.py:246-248` (`systemanweisung` haengt die
Tells an). Der Code haengt sie **absichtlich** an den Prosa-Lauf -- also ist
der Satz in der Datei ("not in prose") der falsche, nicht der Code.

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/theater-tells.md:6-8`
- Modify: `interview_theater/sprachen/en/prompts/theater-tells.md:61`

- [ ] **Step 1: Der Kopf sagt, was der Code tut**

Zeile 6-8 heute:

```
Each entry is a pattern that gets in the way **in spoken stage dialogue** --
not in prose, not in an essay. Some of it would be perfectly fine in a novel.
On stage it gets in an actress's way.
```

neu:

```
Each entry is a pattern that gets in the way **in spoken stage dialogue** --
that is where the examples come from, and on stage it gets in an actress's
way. This list also comes with a **prose** job, and there it counts as
language hygiene: the explained feeling, the moral, the closing conclusion,
the stock phrases of a language model are just as wrong in a story. Only what
is about the stage form itself -- speaker lines, stage directions, entry 11 --
does not apply when the job is prose.
```

- [ ] **Step 2: Eintrag 11 nennt seine Textsorte**

Zeile 61 heute:

```
**11. Narrative prose in the scene text.**
```

neu:

```
**11. Narrative prose in a theatre text** (not in a prose job -- there it is the point).
```

- [ ] **Step 3: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import szene; t=szene.systemanweisung(szene.PROSA); print('not in prose, not in an essay' in t); print('language hygiene' in t); print('<place>' in t)"
```
Erwartet:
```
False
True
True
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_pruefe_sprache.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed` -- insbesondere
`test_szenen_systemanweisung_englisch` (kein deutsches Wort in einer der sechs
Systemanweisungen) und `test_gleiche_platzhalter_und_struktur` (Zahl der
Ueberschriften und Zaeune unveraendert: es kam kein `#` und kein ``` dazu).

- [ ] **Step 4: Commit**

```bash
git add interview_theater/sprachen/en/prompts/theater-tells.md
git commit -m "$(cat <<'EOF'
en-theater-tells: c7 -- der Kopf sagt, was der Code tut

Die Datei sagte "not in prose", und der Code haengt sie ausdruecklich
an den Prosa-Lauf (szene.py:338-343 "Die Tells bleiben: sie sind
Sprachhygiene und gelten fuer jeden Text"; kurzgeschichte.py:246-248).
Jetzt steht im Kopf, was gilt: als Sprachhygiene ja, die
buehnenspezifischen Punkte -- Sprecherzeilen, Regieanweisungen,
Eintrag 11 -- nicht. Eintrag 11 nennt seine Textsorte selbst.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: c8 -- Kernpaket und Station 5

**Code-Belege:**

- `interview_theater/kontext.py:469-479`: "Die Geschichte steht vorn: sie hat
  die Rolle uebernommen, die bis zum Umbau vom 05.09.2026 nachts das
  Kernthema hatte"; die Kernthema-Zeile kommt nur, wenn eine alte Gruppe eine
  gesetzt hat (`kernthema_zeile(stand)`), der Block entsteht auch ohne sie
  (`if not zeilen: return ""`, `kontext.py:549-551`).
- `workshop/padua-2026/phasen.toml:36-39`: `conflict`, `story`, `core theme`
  und `format` sind Stichwoerter der Phase **4** ("Setting, Characters &
  Story"). Also ist "framing decision in station 5" um eine Station
  verschoben; Phase 5 ist "Sharpening".
- `system.md:50` ("we're still on the core theme") **bleibt stehen**: das Wort
  loest auf Phase 4 auf, der Beispielsatz funktioniert also
  (`tests/test_profile_geruest.py:116`, Fall `("core theme", 4)`).

**Files:**
- Modify: `interview_theater/sprachen/en/texte.toml:848` (**eine** Zeile, Tabelle `["kontext"]`)
- Modify: `interview_theater/sprachen/en/prompts/system.md:42-45`

- [ ] **Step 1: `KERNPAKET_KOPF`**

`interview_theater/sprachen/en/texte.toml`, Zeile 848 heute:

```toml
KERNPAKET_KOPF = "The core package - this is what you work from. Characters and scenes come from the core theme and this selection, not from the interviews (they are deliberately no longer available to you here word for word):"
```

neu:

```toml
KERNPAKET_KOPF = "The core package - this is what you work from. Characters and scenes come from the story and this selection, not from the interviews (they are deliberately no longer available to you here word for word):"
```

**Nicht** anfassen: Zeile 932 (`["szene"] KERNPAKET_KOPF`) und Zeile 926/934
(`FIGUREN_KOPF_OHNE_STIMME` -- M1-Fix).

- [ ] **Step 2: Station 5 -> Station 4**

`interview_theater/sprachen/en/prompts/system.md`, Zeile 42-45 heute:

```
**There doesn't always have to be a conflict.** Not every scene needs one
-- it can be a song, a chorus or a harmonious scene. A continuous main
conflict is ONE possible framing decision in station 5, not a precondition
for anything. Ask about it, offer it, and take no for an answer.
```

neu:

```
**There doesn't always have to be a conflict.** Not every scene needs one
-- it can be a song, a chorus or a harmonious scene. A continuous main
conflict is ONE possible framing decision in station 4, not a precondition
for anything. Ask about it, offer it, and take no for an answer.
```

- [ ] **Step 3: Gegenproben**

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import kontext; print(kontext.T.KERNPAKET_KOPF)"
```
Erwartet: eine Zeile mit `come from the story and this selection`.

```
IT_WORKSHOP=padua-2026 $PY -c "from interview_theater import anweisungen, phasen; t=anweisungen.hole('system'); print('framing decision in station 5' in t); print('framing decision in station 4' in t); print(phasen.nummer_fuer('conflict'), phasen.nummer_fuer('core theme'))"
```
Erwartet:
```
False
True
4 4
```

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_prompts.py tests/test_kontext.py tests/test_chat_sprache.py tests/test_pruefe_sprache.py tests/test_profile_geruest.py tests/test_profil_bitgleich.py
```
Erwartet: alles `passed`.

- [ ] **Step 4: Commit**

```bash
git add interview_theater/sprachen/en/texte.toml \
        interview_theater/sprachen/en/prompts/system.md
git commit -m "$(cat <<'EOF'
en: c8 -- das Kernpaket kommt aus der Geschichte, nicht aus dem Kernthema

kontext._baue_kernpaket setzt die Geschichte an die Stelle, die bis zum
Umbau vom 05.09.2026 das Kernthema hatte (kontext.py:469-479); ohne
Kernthema entsteht der Block trotzdem. Der Kopf sagt das jetzt.

Dazu: "framing decision in station 5" -> station 4. Die Stichwoerter
conflict/story/core theme/format gehoeren zur Phase 4 (Setting,
Characters & Story), 5 ist Sharpening (padua-2026/phasen.toml:36-39).
system.md:50 ("we're still on the core theme") bleibt stehen -- das Wort
loest auf Phase 4 auf, der Beispielsatz wirkt.

texte.toml:926/932/934 (M1-Fix) sind nicht angefasst.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: LIESMICH, Dump-Marker und der neue Prompt-Dump

**Files:**
- Modify: `workshop/padua-2026/LIESMICH.md:9-15`, `:29-33`, `:63-65`
- Modify: `scripts/erzeuge_prompts_padua.py:22-23`, `:37-38`
- Create: `docs/prompt-audit/2026-10-01-padua-fix/01-gespraech-phase1.txt`
  (und `02`, `03`, `04`, `uebersicht.tsv` -- alle vom Skript erzeugt)

- [ ] **Step 1: Der Dump-Marker** (D9, ueber die Kartenliste hinaus)

`scripts/erzeuge_prompts_padua.py`, Zeile 37-38 heute:

```python
#: Die Markierung vor dem Vorschlag, nur im Dump.
MARKE = "<!-- VORSCHLAG zur Abnahme -->"
```

neu:

```python
#: Die Markierung vor der Profil-Anweisung, nur im Dump. Bis zum 01.10.2026
#: war sie ein Vorschlag ("<!-- VORSCHLAG zur Abnahme -->"); Birk hat ihn an
#: diesem Tag abgenommen (Karte P-Fix).
MARKE = "<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->"
```

Und im Modul-Docstring, Zeile 20-23 heute:

```
Je Pfad eine Datei mit ``=== SYSTEM ===`` und ``=== NUTZER ===`` (dasselbe
Format wie ``erzeuge_prompts``), plus ``uebersicht.tsv``. Steht die
Profil-Anweisung (``workshop/<name>/prompts/anweisung.md``) im
Systemtext, wird im **Dump** -- und nur dort -- die Zeile
``<!-- VORSCHLAG zur Abnahme -->`` davorgesetzt: der Bot bekommt sie nie.
```

neu:

```
Je Pfad eine Datei mit ``=== SYSTEM ===`` und ``=== NUTZER ===`` (dasselbe
Format wie ``erzeuge_prompts``), plus ``uebersicht.tsv``. Steht die
Profil-Anweisung (``workshop/<name>/prompts/anweisung.md``) im
Systemtext, wird im **Dump** -- und nur dort -- die Zeile ``MARKE``
davorgesetzt: der Bot bekommt sie nie.
```

- [ ] **Step 2: Den Dump erzeugen** (kein Modellaufruf, reine Textmontage)

```
$PY -m scripts.erzeuge_prompts_padua docs/prompt-audit/2026-10-01-padua-fix
```
Erwartet: fuenf Zeilen auf stdout (Kopfzeile + vier Pfade mit
`system_zeichen`, `nutzer_zeichen`, `token_gesamt`) und fuenf neue Dateien im
Zielverzeichnis. Die Systemteile duerfen gegenueber dem Altstand (26 594 /
30 819 / 12 300 / 11 174 Zeichen) abweichen -- die Prompts haben sich ja
geaendert; die Zahlen gehen in die neue BEFUND-Tabelle.

- [ ] **Step 3: `LIESMICH.md` -- abgenommener Stand statt ANNAHME**

Zeile 9-15 heute:

```markdown
**Jede Angabe, die nicht wörtlich oder eindeutig im Vault steht, trägt in
`profil.toml` den Kommentar `# ANNAHME (unbelegt): …`** — mit dem Grund. Birk
nimmt sie am Prompt-Dump ab: `docs/prompt-audit/2026-09-30-padua/BEFUND.md`.
Markiert sind heute: die Spielorte (Padua/Venedig ist nur als Interviewort
belegt), die ausgeschlossenen Orte (Dortmunds Jugendschutz-Liste ersetzt durch
einen Schutz der Befragten), der Ort der Werkschau, die Beispielorte (A1), der
Konfliktrahmen (im Vault offen) und die Konflikt-Ausschlüsse.
```

neu:

```markdown
**Abgenommen am 01.10.2026.** Die sechs Angaben, die Karte P noch als
`# ANNAHME (unbelegt)` markiert hatte, hat Birk am Prompt-Dump entschieden;
`profil.toml` nennt seitdem je Angabe die Entscheidung statt der Annahme.
Gültig ist damit: die **Spielorte** sind offen formuliert — welche Orte
vorkommen, wählt die Gruppe aus ihren Interviews, erfunden oder real, und
Padua ist Herkunft des Materials, nicht Pflicht-Schauplatz („Venice" ist
raus); die **ausgeschlossenen Orte** bleiben wie sie waren (Schutz der
Befragten, kein Jugendschutz); die **Werkschau** findet am letzten Tag in oder
an der Akademie statt, 10–15 Minuten je Gruppe, Form und Mittel offen — kein
Teatro Verdi, keine KI-Projektion; es gibt **keine Beispielorte** mehr (im
englischen Prompt steht `<place>`); der **Konfliktrahmen** ist leer, es bleibt
„Conflict may be serious."; **ausgeschlossen** ist nur noch „No interviewed
person recognisable by name or address". Nachweis mit Prompt-Dump und
Greptabelle: `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md`.
```

Zeile 29-33 heute:

```markdown
**Die Profil-Anweisung** (`prompts/anweisung.md`, Karte P): eine knappe
Verhaltensanweisung an den Gesprächs-Bot (Rolle, Ton, Grenzen, Frageweise),
die `anweisungen.system()` zwischen Phasenanweisung und Regie-Zettel hängt.
Nur Padua hat sie — Dortmund bleibt bitgleich. Begründung und Vorher/Nachher
in `BEFUND.md`. Sie ist ein **Vorschlag zur Abnahme**.
```

neu:

```markdown
**Die Profil-Anweisung** (`prompts/anweisung.md`, Karte P): eine knappe
Verhaltensanweisung an den Gesprächs-Bot (Rolle, Ton, Grenzen, Frageweise),
die `anweisungen.system()` zwischen Phasenanweisung und Regie-Zettel hängt.
Nur Padua hat sie — Dortmund bleibt bitgleich. **Abgenommen am 01.10.2026**;
ihr Schluss ist Birks Wortlaut: eine der angebotenen Optionen darf einen
überraschenden oder gegenläufigen Winkel nehmen, solange er aus dem Material
oder dem Thema der Gruppe wächst. Weil diese Datei am **Ende** des Prompts
steht (SPEC § 6.1), gilt sie gegen jede ältere Formulierung in
`sprachen/en/prompts/`.
```

Zeile 63-65 heute:

```markdown
- **Englische Beispielorte** (`orte.beispiele`): bus stop, piazza, café,
  station. Sie stehen in englischen Prompt-Sätzen; die italienischen Wörter
  des alten Gerüsts (`fermata`, `stazione`) wären dort Fremdkörper gewesen.
```

neu:

```markdown
- **Keine Beispielorte** (`orte.beispiele = []`, Birk 01.10.2026): im
  englischen Prompt steht statt eines Ortes `<place>` — wie `<character A>` —,
  weil Nachplappern von Beispielorten gemessen ist (Audit 06.09.2026). Die
  **leere Liste** steht ausdrücklich da: ein fehlender Schlüssel würde über
  `workshop._vereinige` die deutschen Vorgabewerte erben.
```

- [ ] **Step 4: Lauf**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profile_geruest.py tests/test_doku_laengen.py
```
Erwartet: alles `passed` (`test_jedes_profil_hat_ein_liesmich` verlangt > 500
Zeichen und eines der Worte „eigenstaendig"/„eigenständig"/„Eigenschaft" --
der Abschnitt „Was dieses Profil eigenständig macht" bleibt stehen).

- [ ] **Step 5: Commit**

```bash
git add workshop/padua-2026/LIESMICH.md \
        scripts/erzeuge_prompts_padua.py \
        docs/prompt-audit/2026-10-01-padua-fix/
git commit -m "$(cat <<'EOF'
padua: LIESMICH auf den abgenommenen Stand, neuer Prompt-Dump

LIESMICH nennt statt der sechs ANNAHME-Angaben Birks Entscheidungen vom
01.10.2026. Der Dump-Marker heisst nicht mehr "VORSCHLAG zur Abnahme",
sondern "Profil-Anweisung, abgenommen Birk 01.10.2026" -- nur im Dump,
der Bot sieht ihn nie. Die vier Dumps samt uebersicht.tsv liegen unter
docs/prompt-audit/2026-10-01-padua-fix/ und sind ohne Modellaufruf
erzeugt (reine Textmontage gegen eine Wegwerf-Datenbank).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Der Befund -- c1 bis c10 Zeile fuer Zeile

**Files:**
- Create: `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md`
- Modify: `docs/prompt-audit/2026-09-30-padua/BEFUND.md:151` (**genau eine** Zeigerzeile)

- [ ] **Step 1: Die Zahlen fuer die Tabelle messen**

Der Grep-Block aus Task 16 wird hier **einmal** gefahren und seine Ausgabe in
den Befund kopiert. Dazu die Zeichenzahlen aus `uebersicht.tsv` beider
Verzeichnisse:

```
cat docs/prompt-audit/2026-09-30-padua/uebersicht.tsv
cat docs/prompt-audit/2026-10-01-padua-fix/uebersicht.tsv
$PY -m scripts.pruefe_profil padua-2026
$PY -m scripts.pruefe_profil dortmund-2026
```

- [ ] **Step 2: `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md` schreiben**

Genau diese Gliederung, die gemessenen Zahlen eingesetzt (keine geschaetzten):

````markdown
# Befund: Padua P-Fix -- Profil-Abnahme und Widersprueche c1-c10 (01.10.2026)

Dieser Befund loest `docs/prompt-audit/2026-09-30-padua/BEFUND.md`
Abschnitt c ab. Grundlage: Birks Entscheidungen vom 01.10.2026 (Punkte 1-7,
`hermes/profiles/birk/docs/padua-fabrik/entscheidungen-p.md`) und die
**Code-Wahrheit** fuer c2-c9.

## Wie die Dumps entstehen

`$PY -m scripts.erzeuge_prompts_padua docs/prompt-audit/2026-10-01-padua-fix`
-- unveraendert wie am 30.09.2026: Wegwerf-Datenbank im Temp-Verzeichnis,
zwei erfundene Gruppen (Phase 1 und Phase 6), Interviewmaterial aus
`simulation/interviews/set1/2-ferzan-bahnhof.md` (frei erfunden), `IT_DB` auf
die Wegwerf-DB, damit kein Regie-Zettel aus `betrieb/` hineinrutscht. **Kein
Modellaufruf** -- der Dump ist reine Textmontage.

Die Zeile `<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->` setzt nur
das Dump-Skript (`MARKE`, `_markiere`); der Bot bekommt sie nie, und
`anweisung.md` traegt sie nicht.

| Dump | System-Zeichen alt (30.09.) | System-Zeichen neu | Nutzer |
|---|---|---|---|
| 01 Gespraech Phase 1 | 26 594 | <gemessen> | <gemessen> |
| 02 Gespraech Phase 6 | 30 819 | <gemessen> | <gemessen> |
| 03 Kurzgeschichte Phase 6 | 12 300 | <gemessen> | <gemessen> |
| 04 Einzelszene Prosa Phase 6 | 11 174 | <gemessen> | <gemessen> |

## Teil A -- Birks Punkte 1-7

| Punkt | Entscheidung | Wo umgesetzt |
|---|---|---|
| 1 Spielorte | offen, Orte waehlt die Gruppe aus den Interviews; „Venice" raus | `profil.toml` `[orte] beschreibung` |
| 2 Ausgeschlossene Orte | unveraendert, nur ANNAHME weg | `profil.toml` `[orte] ausgeschlossen` |
| 3 Werkschau | woertlich Birks Text; kein Teatro Verdi, keine KI-Projektion | `profil.toml` `[orte] auffuehrung`, dazu `zielgruppe.traeger` (D5) |
| 4 Beispielorte | raus, im Prompt `<place>` | `[orte] beispiele = []` + 8 Stellen in `sprachen/en/prompts/` |
| 5 Konfliktrahmen | leer; Teilsatz faellt weg | `[konflikt] erlaubt = ""`, `workshop.platzhalter` (`konflikt_erlaubt_strich`/`_klammer`), `en/prompts/rahmen.md`, `rahmen-kurz.md` |
| 6 Konflikt-Ausschluesse | nur „No interviewed person recognisable by name or address" | `[konflikt] ausgeschlossen` |
| 7 Profil-Anweisung | Schluss woertlich ersetzt | `workshop/padua-2026/prompts/anweisung.md` |

Alle sechs `# ANNAHME (unbelegt)`-Kommentare sind entfernt; `profil.toml`
nennt je Angabe „Birk 01.10.2026 (Punkt N)".

## Teil B -- die Widersprueche c1 bis c10

| Nr. | Satz, der **bleibt** | Satz, der **geht** | Code-Beleg |
|---|---|---|---|
| c1 | `en/system.md:75` Optionen; `anweisung.md` traegt die Winkel-Regel | `en/system.md:67-68` „Suggest ONE thing, not three to choose from"; `:72-76` „variants of the **SAME** idea … not about yours" | entschieden durch Birks Punkt 7; `anweisungen.py:368-370` haengt `anweisung.md` als **letzten** Block an (SPEC § 6.1) |
| c2 | `en/system.md:37-40` („already in the scene sequence **suggestion**"), `:17` „still without a form" | `en/phasen/6.md:34` „The form for each scene is **already settled** … decided with the story" | `kurzgeschichte.py:174` („`form` bleibt leer: sie entscheidet die Gruppe im Feinschliff"), `szenenfolge.py:315`/`:334-335` (`form_vorschlag`), `szene.py:2241-2246` |
| c3 | `en/system.md:376` („when entering the scene phase, with two buttons") | `en/system.md:322` „asked by the scene run … **before the first scene**" (als einzige Antwort) | `knoepfe/stationen.py:171-189` (Eintritt in `PHASE_SZENEN`, `knoepfe/texte.py:455`), `szene.py:2488-2496` (nur noch Rueckfall) |
| c4 | `en/phasen/6.md:63` „Phase 6 writes ONE short story in one go" | `en/phasen/6.md:4` „the texts are written -- **scene by scene**" | `kurzgeschichte.py:72-82`, `szene.py:2241-2246`, `workshop/padua-2026/phasen.toml:49` |
| c5 | `texte.toml:1116-1119` (`kurzgeschichte.ANWEISUNG`: „You choose the number of sections yourself … a suggestion, not a requirement") | `en/formen/prosa.md:28` „**If a scene sequence already exists, it is binding**" | `kurzgeschichte.py:79-82`, `lege_szenen_an` gleicht **ergaenzend** ab (`kurzgeschichte.py:168-186`); wo die Zahl bindet, sagt es der Auftrag (`texte.toml:730` `kuerzung.TEXT_NOTIZ_PROSA`, `nachpass.py:350-353`) |
| c6 | `kurzgeschichte.ANWEISUNG` fuer den Ganz-Lauf; `en/formen/prosa.md` „Your output" fuer die **Einzelszene** -- beides jetzt ausdruecklich zugeordnet | der unbedingte Anspruch „This file is the **whole** instruction … Exactly in this form" fuer jeden Auftrag, und `prosa.md:41` „only `Scene N — Title`" fuer den Ganz-Lauf | `kurzgeschichte.zerlege` liest nur Ueberschrift + `ZUSAMMENFASSUNG:` (`kurzgeschichte.py:137-165`), `szene.py` liest die vier Pflichtzeilen |
| c7 | die Tells gelten als Sprachhygiene auch fuer Prosa | `en/theater-tells.md:7` „**not in prose**, not in an essay"; Eintrag 11 ohne Textsortenangabe | `szene.py:338-343` („Die Tells bleiben: sie sind Sprachhygiene und gelten fuer jeden Text"), `szene.py:351-354`, `kurzgeschichte.py:246-248` |
| c8 | `en/system.md:50` („we're still on the core theme") -- das Wort loest auf Phase 4 auf | `texte.toml:848` „come from the **core theme** and this selection" -> „from the **story**"; `en/system.md:44` „station 5" -> „station 4" | `kontext.py:469-479` + `:549-551`, `workshop/padua-2026/phasen.toml:36-39` (`conflict`/`story`/`core theme` = Phase 4), `tests/test_profile_geruest.py` Fall `("core theme", 4)` |
| c9 | der Figurenhinweis im Nutzertext (er ist richtig und gewollt) | `en/phasen/6.md:67` „**No** question about a character's way of speaking" (ohne Ausnahme) | `kontext.py:788-798` (`_baue_figurenhinweis` ab `kernpaket_erlaubt`, `kontext.py:566`/`:584-590`), `texte.toml:851`, `knoepfe/figuren.py:358-368`. **Geteilt mit Karte M1-Fix:** `texte.toml:926`/`:934` (`["szene"] FIGUREN_KOPF_OHNE_STIMME`) und `szene.py` gehoeren dort hin und sind hier **nicht** angefasst |
| c10 | — | **entfaellt durch Birks Punkt 3**: „AI-generated projected backgrounds" steht nicht mehr im Profil, der Widerspruch zu „The scenes need no set" ist weg. Die zweite Haelfte („Places: places from everyday life", Dopplung in `rahmen-kurz.md`) loest der neue `orte.beschreibung`-Wert mit auf: „Places: wherever the group decides, …" | `profil.toml` `[orte] auffuehrung`, `[orte] beschreibung` |

**Bekannte Restspannung, bewusst nicht angefasst:** `en/phasen/1..7.md` tragen
alle den Einschub „(variants of the same idea, title — description)"
(`1.md:20`, `2.md:31`, `3.md:57`, `4.md:94`, `5.md:33`, `6.md:55`, `7.md:31`).
Die Karte nennt fuer c1 nur `system.md`. Aufgeloest wird es ueber die
Position: `anweisung.md` steht als letzter Block im Prompt und gilt gegen die
aelteren Formulierungen. Ebenso bleibt `texte.toml:932`
(`["szene"] KERNPAKET_KOPF`, „filtered by the core theme") stehen -- D8 zieht
die Grenze bei `~l.848`.

## Teil C -- die Greptabelle (Positivkontrolle alt -> neu)

Im **SYSTEM**-Teil (alles vor `=== NUTZER`), Muster
`bus stop|piazza|café|station concourse|\bthe station\b|\(station,`:

| Dump | alt | welche Treffer (alt) | neu |
|---|---|---|---|
| 01 | 3 | `bus stop` (system.md:160), `the station` (:201), `bus stop` (:318) | <gemessen, soll 0> |
| 02 | 4 | dieselben drei plus `bus stop` (phasen/6.md:31) | <gemessen, soll 0> |
| 03 | 1 | `station concourse` (theater-tells.md:64) | <gemessen, soll 0> |
| 04 | 1 | `station concourse` (theater-tells.md:64) | <gemessen, soll 0> |

`szene.md:111-112` ist in keinem dieser vier Dumps messbar: Dump 04 ist ein
**Prosa**-Lauf, und `szene.systemanweisung(PROSA)` laesst `szene.md` weg
(`szene.py:351-354`). Die beiden Stellen sind trotzdem geaendert -- gesichert
wird sie durch `test_kein_englischer_prompt_nennt_einen_beispielort`.

Auf der **ganzen** Dump-Datei:

| Muster | alt (01/02/03/04) | neu | Art |
|---|---|---|---|
| `Teatro Verdi` | 2/3/0/0 | <soll 0> | Positivkontrolle |
| `projected backgrounds` | 1/2/0/0 | <soll 0> | Positivkontrolle |
| `glorification` | 1/2/0/0 | <soll 0> | Positivkontrolle |
| `ONE thing` | 1/1/0/0 | <soll 0> | Positivkontrolle |
| `variants of the group's own idea` | 1/1/0/0 | <soll 0> | Positivkontrolle |
| `Venice` | 1/2/0/0 | <soll 0> | Positivkontrolle |
| `-- \.$` / `serious \(\)` | 0/0/0/0 | <soll 0> | **keine** Positivkontrolle -- im Altstand war `konflikt.erlaubt` gefuellt, das Muster konnte nie anschlagen. Es sichert den **neuen** Stand |
| `{{` | 0/0/0/0 | <soll 0> | wie oben: Dauerzusicherung |

**Praemisse der Karte korrigiert.** Der in der Karte genannte Grep
`bus stop|piazza|café|station` -> 0 kann so nicht gelten:

1. „station" heisst in diesen Prompts auch **Arbeitsphase** -- `system.md:7`
   („seven stations"), `:29` („in station 4"), `:44`, `:53`. Gemessen im
   Altstand: das Rohmuster trifft 12/17/5/7 mal (01/02/03/04), davon der
   grosse Teil auf Phasen.
2. Das Fixture-Interview von `erzeuge_prompts_padua.py` spielt an einem
   Bahnhof („the railway station", „the station café") -- **Nutzertext**,
   erfundenes Material der Gruppe, und es bleibt legitim dort stehen.
3. „café" steht aus demselben Grund im Nutzertext von 02/03/04 (je 3x).

Deshalb die oben gefahrene Fassung: engeres Muster, und nur auf den
SYSTEM-Teil.

## Teil D -- Profilpruefung

```
<Ausgabe von `$PY -m scripts.pruefe_profil padua-2026`>
<Ausgabe von `$PY -m scripts.pruefe_profil dortmund-2026`>
```

`scripts/pruefe_profil.py` prueft seit dieser Karte die **wirksame**
Prompt-Ebene (Profil > Sprache > Repo) -- vorher sah es die englische Schicht
nie an und prueft dafuer deutsche Dateien, die unter `sprache.code = "en"`
niemand liest.
````

> **Hinweis an die Implementierung:** jedes `<gemessen …>` wird durch die
> wirklich gemessene Zahl ersetzt; keine Platzhalter stehen lassen. Die alten
> Zahlen in den Tabellen sind in diesem Plan bereits gemessen (02.10.2026,
> gegen `docs/prompt-audit/2026-09-30-padua/`) und werden nicht neu erhoben.

- [ ] **Step 3: Die eine Zeigerzeile im alten Befund**

`docs/prompt-audit/2026-09-30-padua/BEFUND.md`, Zeile 151 heute:

```markdown
## c) Widersprüche zwischen Blöcken
```

neu (genau **eine** Zeile dazu, der Rest des Abschnitts bleibt unberuehrt --
er ist die Positivkontrolle):

```markdown
## c) Widersprüche zwischen Blöcken

> **Abgelöst am 01.10.2026:** c1–c10 sind entschieden und umgesetzt — was blieb, was ging und mit welchem Code-Beleg, steht in `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md`. Der Abschnitt unten bleibt als Stand von vorher stehen.
```

- [ ] **Step 4: Lauf**

```
$PY -m pytest -q -p no:cacheprovider tests/test_doku_laengen.py
```
Erwartet: `passed` (bzw. keine Testdatei beruehrt diese Dokumente -- dann
`no tests ran` fuer die Auswahl, was ebenfalls in Ordnung ist).

- [ ] **Step 5: Commit**

```bash
git add docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md \
        docs/prompt-audit/2026-09-30-padua/BEFUND.md
git commit -m "$(cat <<'EOF'
befund: c1-c10 Zeile fuer Zeile, mit Code-Beleg und Greptabelle

Neuer Befund unter docs/prompt-audit/2026-10-01-padua-fix/: Birks sieben
Punkte, je Widerspruch welcher Satz blieb und welcher ging mit
Datei:Zeile aus dem Code, die Positivkontrolle alt->neu und die Ausgabe
von pruefe_profil. Darin auch die korrigierte Praemisse der Karte: der
Grep "station" trifft die Arbeitsphasen und das Fixture-Interview mit,
geprueft wird deshalb ein engeres Muster und nur der SYSTEM-Teil.

Der alte Befund bekommt oben in Abschnitt c genau eine Zeigerzeile; der
Abschnitt selbst bleibt als Stand von vorher stehen.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Abnahme

Diese Task aendert nichts -- sie belegt. Jede Ausgabe wird in die Antwort an
den Reviewer kopiert, nicht zusammengefasst.

**Files:**
- Create: nichts (ein Mess-Skript unter `/tmp/`, nicht im Repo)

- [ ] **Step 1: Die Grep-Abnahme (korrigiertes Kriterium)**

Das Mess-Skript nach `/tmp/abnahme_pfix.py` schreiben (**nicht** ins Repo,
**nicht** `git add`):

```python
import re
import pathlib
import sys

ALT = pathlib.Path("docs/prompt-audit/2026-09-30-padua")
NEU = pathlib.Path("docs/prompt-audit/2026-10-01-padua-fix")

P1 = re.compile(r"bus stop|piazza|café|station concourse|\bthe station\b|\(station,")
GANZ = [
    ("Teatro Verdi", r"Teatro Verdi"),
    ("projected backgrounds", r"projected backgrounds"),
    ("glorification", r"glorification"),
    ("ONE thing", r"ONE thing"),
    ("variants of the group's own idea", r"variants of the group's own idea"),
    ("Venice", r"Venice"),
    ("leerer Strich/Klammer", r"-- \.$|serious \(\)"),
    ("offener Platzhalter", r"\{\{"),
]


def system_teil(pfad):
    return pfad.read_text(encoding="utf-8").split("\n\n=== NUTZER")[0]


fehler = 0
print("--- P1 im SYSTEM-Teil (alt muss > 0 sein, neu == 0) ---")
for name in sorted(p.name for p in ALT.glob("0*.txt")):
    alt = len(P1.findall(system_teil(ALT / name)))
    neu = len(P1.findall(system_teil(NEU / name)))
    print(f"{name}  alt={alt}  neu={neu}")
    if alt <= 0 or neu != 0:
        fehler += 1

print("\n--- ganze Datei (alt zur Kontrolle, neu == 0) ---")
for label, pat in GANZ:
    alt = [len(re.findall(pat, (ALT / p.name).read_text(encoding="utf-8"), re.M))
           for p in sorted(ALT.glob("0*.txt"))]
    neu = [len(re.findall(pat, (NEU / p.name).read_text(encoding="utf-8"), re.M))
           for p in sorted(NEU.glob("0*.txt"))]
    print(f"{label:34s} alt={alt}  neu={neu}")
    if any(neu):
        fehler += 1

print("\nFehler:", fehler)
sys.exit(1 if fehler else 0)
```

```
$PY /tmp/abnahme_pfix.py
```

Erwartet (die `alt`-Zahlen sind am 02.10.2026 gemessen und muessen genau so
dastehen -- sie sind die Positivkontrolle):

```
--- P1 im SYSTEM-Teil (alt muss > 0 sein, neu == 0) ---
01-gespraech-phase1.txt  alt=3  neu=0
02-gespraech-phase6.txt  alt=4  neu=0
03-kurzgeschichte-phase6.txt  alt=1  neu=0
04-szene-prosa-phase6.txt  alt=1  neu=0

--- ganze Datei (alt zur Kontrolle, neu == 0) ---
Teatro Verdi                       alt=[2, 3, 0, 0]  neu=[0, 0, 0, 0]
projected backgrounds              alt=[1, 2, 0, 0]  neu=[0, 0, 0, 0]
glorification                      alt=[1, 2, 0, 0]  neu=[0, 0, 0, 0]
ONE thing                          alt=[1, 1, 0, 0]  neu=[0, 0, 0, 0]
variants of the group's own idea   alt=[1, 1, 0, 0]  neu=[0, 0, 0, 0]
Venice                             alt=[1, 2, 0, 0]  neu=[0, 0, 0, 0]
leerer Strich/Klammer              alt=[0, 0, 0, 0]  neu=[0, 0, 0, 0]
offener Platzhalter                alt=[0, 0, 0, 0]  neu=[0, 0, 0, 0]

Fehler: 0
```

Exit-Code 0. **Zwei Zeilen sind keine Positivkontrolle und das ist gewollt:**
`leerer Strich/Klammer` und `offener Platzhalter` waren im Altstand schon 0
(`konflikt.erlaubt` war gefuellt, kein Platzhalter blieb stehen) -- sie
sichern allein den neuen Stand. So steht es auch im Befund.

- [ ] **Step 2: Profilpruefung, beide Profile**

```
$PY -m scripts.pruefe_profil padua-2026
$PY -m scripts.pruefe_profil dortmund-2026
```
Erwartet: je eine Schlusszeile `padua-2026: in Ordnung` bzw.
`dortmund-2026: in Ordnung` (ggf. `, N Hinweis(e)`), Exit 0. **Die Ausgaben
woertlich in die Antwort kopieren und in `BEFUND.md` Teil D eintragen.**

- [ ] **Step 3: Dortmund und die deutschen Prompts sind byte-gleich**

```
git diff origin/main --stat -- workshop/dortmund-2026 interview_theater/prompts
git diff origin/main -- workshop/dortmund-2026 interview_theater/prompts | wc -c
```
Erwartet: erste Zeile leer, zweite `0`.

**Gemessen am 02.10.2026:** `origin/main` ist `1e6bd0d`, der Zweigkopf
`6364354`, und beide Diffs sind **heute schon** leer -- der Vergleich mit
`origin/main` traegt also. Zieht `origin/main` waehrend der Umsetzung weiter
und wird dieser Diff aus fremdem Grund nicht leer, stattdessen gegen den
Zweigpunkt pruefen:
`git diff $(git merge-base origin/main HEAD) --stat -- workshop/dortmund-2026 interview_theater/prompts`
-- und den Unterschied in der Antwort benennen, statt ihn zu uebergehen.

- [ ] **Step 4: M1-Fix-Gebiet nicht angefasst**

```
git diff origin/main -- interview_theater/szene.py | wc -c
grep -n "FIGUREN_KOPF_OHNE_STIMME" interview_theater/sprachen/en/texte.toml
git diff origin/main -- interview_theater/sprachen/en/texte.toml
```
Erwartet: `0` fuer `szene.py`; die `FIGUREN_KOPF_OHNE_STIMME`-Zeilen stehen
unveraendert bei 926/934; der `texte.toml`-Diff zeigt **genau eine**
geaenderte Zeile (848, `["kontext"] KERNPAKET_KOPF`).
Gemessen am 02.10.2026: `git diff --stat origin/main -- interview_theater/szene.py
interview_theater/sprachen/en/texte.toml` ist heute leer -- jede Zeile im
Diff kommt also aus dieser Karte.

- [ ] **Step 5: Kein Beispielort und kein offener Platzhalter in der Sprachschicht**

```
grep -rn "{{ort_beispiel\|{{orte_beispiele" interview_theater/sprachen/en/ ; echo "exit=$?"
grep -rniE "bus stop|piazza|station concourse" interview_theater/sprachen/en/prompts/ ; echo "exit=$?"
```
Erwartet: keine Ausgabe, je `exit=1`.

- [ ] **Step 6: Die Bitgleichheits-Zusage**

```
$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py
```
Erwartet: `passed` fuer alle Faelle, kein `failed`.

- [ ] **Step 7: Die ganze Suite**

```
$PY -m pytest -q -p no:cacheprovider
```
**Abwarten, nicht in den Hintergrund schicken** (rund 7 Minuten).
Erwartet: `1 failed, >=5008 passed, 2 skipped` -- und der eine Fehlschlag ist
derselbe wie vor der Karte:
`tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]`.
(Auf Basis `1e6bd0d` oder spaeter: `0 failed`, siehe Nachtrag in
"Global Constraints".)
**Jeder andere Fehlschlag ist ein Befund dieser Karte und muss behoben
werden, nicht weggedrueckt.** Die Zahl `passed` darf gewachsen sein (neue
Tests aus Task 1, 2, 4, 5, 7).

- [ ] **Step 8: Nichts Fremdes im Index**

```
git status --short
```
Erwartet: ausschliesslich die vier unversionierten Hilfsdateien
`?? .cc-run-t_56df06b2.err`, `?? .cc-run-t_56df06b2.json`,
`?? .cc-settings.json`, `?? .superpowers-brief-t_56df06b2.md` -- **keine** davon
wird je `git add`ed, und sonst ist der Baum leer.

- [ ] **Step 9: Die Messwerte in den Befund nachtragen und commiten**

Die in Step 1-2 gemessenen Zahlen und Ausgaben in
`docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md` einsetzen (Teil C und
Teil D), dann:

```bash
git add docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md
git commit -m "$(cat <<'EOF'
befund: die gemessenen Abnahmezahlen eingetragen

Greptabelle alt->neu im SYSTEM-Teil und auf der ganzen Datei, dazu die
woertliche Ausgabe von pruefe_profil fuer padua-2026 und dortmund-2026.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Selbstpruefung des Plans

- **Teil A der Karte (Punkte 1-7):** 1, 3, 4, 5 -> Task 6; 2 -> Task 6
  (Kommentar) ; 6 -> Task 3; 7 -> Task 8; ANNAHME-Kommentare -> Task 6,
  Zusicherung -> Task 7.
- **Teil B (c1-c10):** c1 -> Task 8; c2, c4, c9 -> Task 9; c3 -> Task 10;
  c5, c6 -> Task 11; c7 -> Task 12; c8 -> Task 13; c10 -> faellt mit Task 6
  (Punkt 3) und wird in Task 15 nachgewiesen. Je Widerspruch eine Zeile in
  der neuen `BEFUND.md` (Task 15).
- **Jede Zusage der Abnahme** hat in Task 16 einen Befehl mit erwarteter
  Ausgabe.
- **Jede Datei, die einen Test umwirft, hat ihre Testanpassung in derselben
  oder einer vorhergehenden Task:** `test_sprache_prompts.py` in Task 4
  (Platzhalter-Paritaet), `test_profile_geruest.py` in Task 5 und 7,
  `test_rahmen.py` in Task 1 und 2.
- **Reihenfolge ist zwingend:** Task 1 vor 2 (Platzhalter vor Vorlage),
  Task 4 vor 5 (erst die EN-Nutzungen weg, dann die Pruefung umstellen),
  Task 5 vor 6 (erst die Pruefung, dann `beispiele = []`), Task 14 vor 15
  (erst der Dump, dann der Befund ueber den Dump).

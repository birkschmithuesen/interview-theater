# Padua M1-Fix: Die Einzelszene liest den Sprachstil der Figur

> **Fuer agentische Arbeiter:** PFLICHT-UNTERSKILL: Nutze
> superpowers:subagent-driven-development (empfohlen) oder
> superpowers:executing-plans, um diesen Plan Aufgabe fuer Aufgabe
> auszufuehren. Die Schritte tragen Checkboxen (`- [ ]`).

**Ziel:** `figur.sprachstil` -- der in Phase 4 per Knopf gewaehlte Sprachstil
-- steht ab jetzt auch im Prompt des Einzelszenenlaufs (`szene._figuren_text`,
Block 3), nicht nur im Prosa-Prompt der Phase 6.

**Architektur:** Eine Funktion wird erweitert (`szene._figuren_text`) und
bekommt zwei neue Textkonstanten (deutsch in `szene.py`, englisch in
`interview_theater/sprachen/en/texte.toml`). Dazu die **Drei-Kopf-Regel**:
der Kopf von Block 3 verspricht nur, was darunter steht -- echte Zitate
(`FIGUREN_KOPF`), sonst gewaehlte Stile (neu: `FIGUREN_KOPF_MIT_STIL`),
sonst nichts von beidem (`FIGUREN_KOPF_OHNE_STIMME`). Kein neuer Modellaufruf,
kein neues Feld, keine Migration, keine Abhaengigkeit.

**Tech-Stack:** Python 3.11, `pytest`, `tomllib` (Sprachschicht),
Standardbibliothek. Nachweis ueber `scripts/sprachstil_wirkung.py pfad`
(baut die echten Prompts offline, kein Netz, kein Modell).

---

## Global Constraints

Jede Aufgabe erbt diesen Abschnitt.

1. **Kein bezahlter Modellaufruf.** Dies ist ein Pfadnachweis. Kein
   `scripts/pruefe_prompts.py`, kein `scripts/simulation.py`, kein
   `sprachstil_wirkung lauf` -- nur `sprachstil_wirkung pfad` (offline).
2. **Nie `betrieb/*.env` oder `betrieb/soap.db` lesen.**
3. **Alles Neue geht ueber die Sprachschicht.** Deutsch als Modulkonstante in
   `interview_theater/szene.py`, Englisch unter `["szene"]` in
   `interview_theater/sprachen/en/texte.toml`, gelesen **ausschliesslich** als
   `T.<NAME>`. Kein deutsches Inline-Literal im Funktionsrumpf -- das faellt
   sonst in `tests/test_sprache_texte.py::test_keine_deutschen_inline_texte`
   und `::test_keine_nackte_verwendung[szene]` auf.
4. **ASCII-Umschrift im deutschen Text** (`woertlich`, `Satzlaenge`,
   `gewaehlt`) -- wie der ganze Rest von `szene.py`.
5. **Ein Sprachstil ist kein Zitat.** `mit_zitat` darf von einem Stil **nie**
   wahr werden (Audit-Befund S4), und die Stilzeile steht **nie** in
   Anfuehrungszeichen.
6. **`prompts/phasen/6.md` wird nicht angefasst** -- das macht Karte
   `t_bce8e55b`.
7. **Dortmund bleibt bitgleich.** `tests/test_profil_bitgleich.py` und
   `tests/test_sprache_bitgleich.py` bleiben gruen.
8. **Branch:** der aktuelle (`padua-workshop/t_b4b8ab61-plan-m1-sprachstil-szene`).
   Kein `push`, kein `merge`.
9. Python fuer jede Ausfuehrung:
   `PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)`
   (hier gemessen:
   `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`).
   Suite immer `$PY -m pytest -q -p no:cacheprovider`.

---

## Ausgangslage -- was vorher nachgemessen wurde

Alles hier ist am 02.10.2026 in diesem Worktree gemessen, nicht aus der Doku
uebernommen.

### Der Ist-Stand im Code

`interview_theater/szene.py:1057-1092` (`_figuren_text`) liest je Figur
genau drei Felder: `beschreibung`, `sprachprofil`, `zitate`. Das Wort
`sprachstil` kommt in `szene.py` **nicht** vor. Der Kopf wird in einer Zeile
gewaehlt (`szene.py:1091`):

```python
kopf = T.FIGUREN_KOPF if mit_zitat else T.FIGUREN_KOPF_OHNE_STIMME
```

Der Prosa-Weg macht es anders (`interview_theater/kurzgeschichte.py:341-347`):

```python
stile = [
    f"- {f['name']}: {(f['sprachstil'] or '').strip()}"
    for f in repo.figuren(conn, chat_id)
    if (f["sprachstil"] or "").strip()
]
if stile:
    teile.append(T._STILE_KOPF + "\n".join(stile))
```

`_STILE_KOPF` ist `"So sprechen die Figuren:\n"` (EN: `"This is how the
characters speak:\n"`, `texte.toml` Tabelle `["kurzgeschichte"]`).

`figur.sprachstil` steht im Basisschema (`interview_theater/db.py:360`), und
`repo.figuren` macht `SELECT *` (`repo.py:1812-1820`) -- `figur["sprachstil"]`
ist also **immer** da, nie ein `IndexError`. Geschrieben wird es von
`repo.setze_figur_sprachstil(conn, figur_id, stil)` (`repo.py:2079`) im
Format `"<Titel>: <Beispielsatz>"`.

### Die gemessene Messlatte (Baseline)

| Kommando | Ergebnis am 02.10.2026, vor der Aenderung |
|---|---|
| `$PY -m pytest -q -p no:cacheprovider` | **`1 failed, 5008 passed, 2 skipped in 426.99s`** |
| der eine Fehlschlag | `tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]` |
| `$PY -m scripts.pruefe_profil dortmund-2026` | `dortmund-2026: in Ordnung` |
| `$PY -m scripts.sprachstil_wirkung pfad --ausgabe .scratch-m1/baseline` | `prosa A-B: 5 Zeilen geaendert (+0/-5)` · `prosa A-C: 3 Zeilen geaendert (+3/-3)` · **`szene A-B: identisch`** · **`szene A-C: identisch`** |
| dasselbe mit `IT_WORKSHOP=padua-2026` | identische vier Zeilen |

**Der Fehlschlag ist vorbestehend und fremd.** `szene.starte` hat einen
Parameter `art="szene"` bekommen, `simulation/lauf.py::_sofort_szene` reicht
ihn nicht durch; der Test vergleicht beide Signaturen. Er hat mit M1 nichts zu
tun und darf am Ende **unveraendert** rot sein. **Die im Karten-Text genannten
"bis zu 5 Errors in `tests/test_flow_fixes_0609.py`" traten hier nicht auf** --
die Messlatte ist die Tabelle oben, nicht die Erwartung.

### Der Fixture-Befund zu Anforderung 4 (Bitgleichheit)

**Geprueft, Ergebnis: kein Konflikt, und der Grund ist strukturell.**
`scripts/prompt_schnappschuss.teile()` (Docstring Zeile 62-68) ist eine
*reine Leseoperation ohne Datenbank*: sie sammelt Prompt-Dateien,
zusammengesetzte Systemanweisungen, Formen-, Phasen- und Leitfadenlisten.
`_figuren_text` ist ein **Nutzertext**-Block und steht dort gar nicht --
nachgezaehlt:

```
grep -c "So spricht jede Figur" docs/prompt-audit/schnappschuss-vor-profilumbau.txt   -> 0
grep -c "sprachstil"            docs/prompt-audit/schnappschuss-vor-profilumbau.txt   -> 0
```

Die Schnappschuss-Fixture setzt also keinen `sprachstil` -- sie hat keine
Figur und keine Datenbank. Dasselbe fuer `tests/test_sprache_bitgleich.py`:
dessen Docstring sagt ausdruecklich *"Neue Abschnitte sind erlaubt (eine neue
Konstante ist keine Undichtigkeit)"*. Zwei **neue** Konstanten sind damit
unkritisch; eine Aenderung an `FIGUREN_KOPF` oder
`FIGUREN_KOPF_OHNE_STIMME` waere es nicht -- deshalb bleiben beide
**zeichengleich**.

Die zweite DB-gestuetzte Fixture, `tests/fixture_spaetstand.py`, setzt
`zitate=[]` und **keinen** `sprachstil` (Zeile 75-77). Darum bleibt
`tests/test_prompt_audit.py::test_szene_verspricht_keine_stimmen_ohne_zitate`
in seinem heutigen Zweig (`FIGUREN_KOPF` steht dort gar nicht im Nutzertext,
die Zusicherung wird uebersprungen).

### Der zweite Verbraucher von `_figuren_text` -- und warum er mitlaeuft

`interview_theater/szenenfolge.py:984-999` (`_material`) ruft
`szene_modul._figuren_text(conn, chat_id)`. Ihr Docstring sagt, warum:

> *Aus `szene.py` geholt statt hier zweitgepflegt -- laeuft der Szenen-Prompt
> auseinander, laeuft auch dieser mit.*

`_material` speist `szenenfolge.baue_nutzertext` (Szenenfolge-Vorschlag) und
`starte_feldvorschlag` (fehlende Angaben je Szene). Beide bekommen die
Stilzeile damit **mit**. Das ist die **am wenigsten invasive** Variante und
genau die Kopplung, die der Docstring verlangt; eine Umgehung (Flag,
zweite Funktion) waere die zweite Wahrheit, die er verhindert. Siehe
"Offene Punkte".

`szenenfolge._erfundenes` (Phase 4, *kein Material*) ruft `_figuren_text`
**nicht** -- der Phase-4-Filter bleibt unberuehrt.

### Die Sprachschicht -- was sie von neuen Konstanten verlangt

`tests/test_sprache_texte.py` prueft am Quelltext (AST):

* `test_jeder_zugriff_hat_einen_englischen_eintrag` -- jedes `T.NAME` braucht
  einen Eintrag in `["szene"]`.
* `test_kein_englischer_eintrag_ohne_deutsche_konstante` -- und umgekehrt.
* `test_platzhalter_und_form_gleich[szene-<NAME>]` -- `{stil}` muss in beiden
  Fassungen stehen (`sprache.platzhalter`).
* `test_keine_nackte_verwendung[szene]` -- im Funktionsrumpf nur `T.NAME`.
* `test_keine_unuebersetzte_konstante[szene]` -- eine Konstante, deren Name
  auf `^_?(TEXT|UEBERSCHRIFT|ANWEISUNG|MELDUNG|JOURNAL|HINWEIS|ZEILE)`
  passt (also auch `ZEILE_SPRACHSTIL`) **muss** in der Tabelle stehen.
* `test_keine_deutschen_inline_texte[szene]`.

Diese Tests sind parametrisiert aus der Tabelle -- neue Schluessel erzeugen
neue Testfaelle von selbst, es ist **kein** Test-Code dafuer zu schreiben.

Sprache in Tests umschalten (Muster aus `tests/test_szene_sprache.py:8-14`):

```python
@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    yield
    sprache.vergiss()
```

`workshop/padua-2026/profil.toml:29-31` setzt `[sprache] code = "en"` -- fuer
Skriptlaeufe genuegt deshalb `IT_WORKSHOP=padua-2026` vor dem Kommando.

---

## Dateistruktur

| Datei | Verantwortung | Aenderung |
|---|---|---|
| `interview_theater/szene.py` | Block 3 des Szenen-Prompts | +2 Konstanten (`FIGUREN_KOPF_MIT_STIL`, `ZEILE_SPRACHSTIL`), `_figuren_text` liest `sprachstil`, Drei-Kopf-Regel |
| `interview_theater/sprachen/en/texte.toml` | englische Fassung, Tabelle `["szene"]` | +2 Schluessel, direkt neben `FIGUREN_KOPF_OHNE_STIMME` (Zeile 934) |
| `tests/test_szene_sprachstil.py` | **neu** -- alles zu M1 an einem Ort: Stilzeile, Drei-Kopf-Regel, deutsch und englisch | Datei anlegen |
| `AGENTS.md` | ein Satz im `szene.py`/Sprachstil-Bereich (nach Zeile 331) | +1 Aufzaehlungspunkt |

**Warum eine neue Testdatei** und nicht `tests/test_szene.py` (1000+ Zeilen,
LLM-/Telegram-Attrappen, Thread-Einsammeln): M1 braucht davon nichts -- nur
`conn`, `einst` und `szene.baue_nutzertext`. Neben
`tests/test_szene_sprache.py` steht damit `tests/test_szene_sprachstil.py`,
derselbe Namensschnitt.

**Nicht angefasst:** `kurzgeschichte.py` (der Prosa-Weg ist in Ordnung),
`prompts/**` (keine Prompt-Datei, nur Konstanten), `db.py` (Spalte existiert),
`repo.py`, `knoepfe/**`, `scripts/sprachstil_wirkung.py` (das Skript baut die
echten Prompts und misst die Aenderung von selbst).

---

## Die festgelegten Wortlaute

Vom Architekten entschieden -- **woertlich so uebernehmen**, nicht
umformulieren.

### Deutsch (`interview_theater/szene.py`)

```python
#: Kopf, wenn keine Figur ein Zitat hat, aber mindestens eine einen von der
#: Gruppe gewaehlten Sprachstil (Widerspruch c9 des Prompt-Audits vom
#: 30.09.2026, ``docs/prompt-audit/2026-09-30-padua/BEFUND.md``): "noch nicht
#: aus Interviews belegt" waere dann die Unwahrheit -- die Gruppe HAT
#: entschieden, wie die Figuren sprechen. Er behauptet umgekehrt auch kein
#: "woertlich aus dem Interview": ein gewaehlter Stil ist kein Belegzitat.
FIGUREN_KOPF_MIT_STIL = (
    "Die Figuren (wer sie sind, was sie wollen). Wie sie sprechen, hat die "
    "Gruppe selbst gewaehlt -- halte die markierten Sprachstile durch; wo "
    "keiner steht, gib der Figur eine eigene, unterscheidbare Art zu reden "
    "(Satzlaenge, Tempo, Lieblingswoerter):"
)
#: Der gewaehlte Sprachstil einer Figur. Eine **Beschriftung**, nie in
#: Anfuehrungszeichen: ein Stil ist kein Belegzitat (Audit-Befund S4), und
#: ``_figuren_mit_wenig_zitaten`` zaehlt genau die Zeilen, die mit ``  "``
#: anfangen.
ZEILE_SPRACHSTIL = "  Sprachstil (von der Gruppe gewaehlt): {stil}"
```

### Englisch (`interview_theater/sprachen/en/texte.toml`, Tabelle `["szene"]`)

```toml
FIGUREN_KOPF_MIT_STIL = "The characters (who they are, what they want). The group chose how they speak -- keep up the speech styles marked below; where none is given, give the character their own distinct way of talking (sentence length, pace, favourite words):"
ZEILE_SPRACHSTIL = "  Speech style (chosen by the group): {stil}"
```

Beide Zeilen gehoeren **unmittelbar hinter** `FIGUREN_KOPF_OHNE_STIMME`
(heute `texte.toml:934`), damit die drei Koepfe in der Datei
beieinanderstehen.

### Die Drei-Kopf-Regel

| Lage | Kopf |
|---|---|
| irgendeine Figur hat ein echtes Zitat | `FIGUREN_KOPF` (**unveraendert**) |
| sonst: irgendeine Figur hat nicht-leeren `sprachstil` | `FIGUREN_KOPF_MIT_STIL` (**neu**) |
| sonst | `FIGUREN_KOPF_OHNE_STIMME` (**unveraendert, zeichengleich**) |

### Die Reihenfolge im Figurenblock

```
Maria -- Naeherin, kam 1998
Kurze Saetze, bricht ab.
  Sprachstil (von der Gruppe gewaehlt): Kurz und abgehackt: Egal. Weiter.
  "Ich hatte nur einen Koffer."
```

Die Stilzeile steht **hinter dem Sprachprofil und vor den Zitaten**. Grund:
`szene._figuren_mit_wenig_zitaten` (letzte Kuerzungsstufe,
`szene.py:1880-1896`) zaehlt aufeinanderfolgende Zeilen, die mit `  "`
beginnen, und setzt den Zaehler bei jeder anderen Zeile auf 0 zurueck -- so
bleibt der Zitatblock je Figur zusammenhaengend und
`SPRACHPROFIL_ZITATE_MAX` wirkt wie vorher.

---

## Aufgabe 1: Die Stilzeile je Figur

**Dateien:**
- Aendern: `interview_theater/szene.py:1057-1092` (`_figuren_text`), neue
  Konstante bei `szene.py:1054` (hinter `FIGUREN_KOPF_OHNE_STIMME`)
- Aendern: `interview_theater/sprachen/en/texte.toml` (Tabelle `["szene"]`,
  hinter Zeile 934)
- Anlegen: `tests/test_szene_sprachstil.py`

**Schnittstellen:**
- Verbraucht: `repo.figuren` (liefert `sqlite3.Row` mit `sprachstil`),
  `repo.setze_figur_sprachstil(conn, figur_id, stil)`, `szene.T`
- Liefert: `szene.ZEILE_SPRACHSTIL` (`str` mit Platzhalter `{stil}`) --
  Aufgabe 2 und 3 lesen sie

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Neue Datei `tests/test_szene_sprachstil.py`:

```python
"""Der in Phase 4 gewaehlte Sprachstil steht auch im Einzelszenen-Prompt
(Padua M1-Fix, 02.10.2026).

Vorher las ``szene._figuren_text`` nur ``beschreibung``, ``sprachprofil`` und
``zitate``; System- und Nutzertext waren mit und ohne Stil byte-identisch
(gemessen in ``docs/sprachstil-wirkung-2026-09-30.md``, Weg 2). Kein Netz,
kein Modell: geprueft wird der Prompt-Bau.
"""

import pytest

from interview_theater import repo, sprache, szene

#: Das Format, das ``knoepfe.wirkung._wirkung_figur_stil`` wirklich
#: speichert: "<Titel>: <Beispielsatz>".
STIL = "Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter."
STIL_ZWEI = "Mit Fuellwoertern: Also, weisst du, der ist halt irgendwie."

#: Die Beschriftung ohne ihren Wert -- sprachunabhaengig aus der Konstante
#: abgeleitet, damit "steht keine Stilzeile da" ohne Literal pruefbar ist.
def _schild(konstante: str) -> str:
    return konstante.split("{stil}")[0]


def _figur(conn, name="Maria", beschreibung="Naeherin, kam 1998",
           profil="Kurze Saetze, bricht ab.", zitate=()):
    """Legt eine Figur an und liefert ihre id. ``zitate=()`` heisst: keine --
    dann bleibt ``mit_zitat`` falsch."""
    repo.setze_figur(conn, 1, name, beschreibung)
    figur_id = repo.hole_figur(conn, 1, name)["id"]
    repo.setze_sprachprofil(conn, figur_id, profil, list(zitate))
    return figur_id


def test_sprachstil_steht_im_szenen_prompt(conn, einst):
    """Der Kern des Fixes: der gewaehlte Stil kommt im Prompt an."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_sprachprofil_und_sprachstil_stehen_nebeneinander(conn, einst):
    """Beides, nicht eins statt des anderen: das Profil ist das Messergebnis
    aus einem Interview, der Stil die Wahl der Gruppe."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert "Kurze Saetze, bricht ab." in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert '"Ich hatte nur einen Koffer."' in text


def test_sprachstil_steht_nie_in_anfuehrungszeichen(conn, einst):
    """Ein Stil ist kein Belegzitat (Audit-Befund S4). Stuende er wie ein
    Zitat da, wuerde das Modell ihn als woertliche Interviewstelle lesen --
    und ``_figuren_mit_wenig_zitaten`` wuerde ihn als Zitat wegkuerzen."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert f'"{STIL}"' not in text
    assert f'  "{STIL}' not in text


def test_jede_figur_bekommt_ihren_eigenen_stil(conn, einst):
    eine = _figur(conn, "Maria", zitate=["Ich hatte nur einen Koffer."])
    andere = _figur(conn, "Elif", beschreibung="Nachbarin",
                    profil="Lange Saetze.", zitate=["Ich bin geblieben."])
    repo.setze_figur_sprachstil(conn, eine, STIL)
    repo.setze_figur_sprachstil(conn, andere, STIL_ZWEI)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL_ZWEI) in text


def test_leerer_sprachstil_erzeugt_keine_zeile(conn, einst):
    """Datengetrieben wie der ganze Prompt: ein Feld mit Leerzeichen ist
    kein Wert, und eine leere Beschriftung waere eine Einladung, etwas zu
    erfinden."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, "   ")

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert _schild(szene.ZEILE_SPRACHSTIL) not in text


def test_ohne_sprachstil_bleibt_der_prompt_wie_vorher(conn, einst):
    """Die Rueckwaertskompatibilitaet in einem Test: eine Gruppe, die nie
    einen Stil gewaehlt hat, bekommt keinen Zeichen mehr."""
    _figur(conn, zitate=["Ich hatte nur einen Koffer."])

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert _schild(szene.ZEILE_SPRACHSTIL) not in text
    assert szene.FIGUREN_KOPF in text
```

- [ ] **Schritt 2: Lauf zur Sicherheit, dass er fehlschlaegt**

```
PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py
```

Erwartet: **Fehler in jedem der sechs Tests**, `AttributeError: module
'interview_theater.szene' has no attribute 'ZEILE_SPRACHSTIL'`. Auch die
beiden Negativtests scheitern, weil `_schild(szene.ZEILE_SPRACHSTIL)` die
Konstante braucht. Also: **6 failed, 0 passed**.

- [ ] **Schritt 3: Die Konstante anlegen -- deutsch**

In `interview_theater/szene.py` direkt hinter `FIGUREN_KOPF_OHNE_STIMME`
(heute endet sie auf Zeile 1054) einfuegen -- nur `ZEILE_SPRACHSTIL`, der
Kopf `FIGUREN_KOPF_MIT_STIL` kommt in Aufgabe 2:

```python
#: Der gewaehlte Sprachstil einer Figur (Padua M1, 02.10.2026). Eine
#: **Beschriftung**, nie in Anfuehrungszeichen: ein Stil ist kein Belegzitat
#: (Audit-Befund S4), und ``_figuren_mit_wenig_zitaten`` zaehlt genau die
#: Zeilen, die mit ``  "`` anfangen.
ZEILE_SPRACHSTIL = "  Sprachstil (von der Gruppe gewaehlt): {stil}"
```

- [ ] **Schritt 4: Die Konstante anlegen -- englisch**

In `interview_theater/sprachen/en/texte.toml`, Tabelle `["szene"]`, direkt
hinter `FIGUREN_KOPF_OHNE_STIMME` (heute Zeile 934):

```toml
ZEILE_SPRACHSTIL = "  Speech style (chosen by the group): {stil}"
```

- [ ] **Schritt 5: `_figuren_text` liest `sprachstil`**

In `interview_theater/szene.py`, in der Schleife von `_figuren_text`: der
Block **zwischen** `sprachprofil` und den Zitaten.

Vorher:

```python
        if figur["sprachprofil"]:
            zeilen.append(figur["sprachprofil"].strip())
        for satz in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
```

Nachher:

```python
        if figur["sprachprofil"]:
            zeilen.append(figur["sprachprofil"].strip())
        # Padua M1 (02.10.2026): der in Phase 4 per Knopf gewaehlte Stil --
        # vor den Zitaten, damit der Zitatblock je Figur zusammenhaengend
        # bleibt (``_figuren_mit_wenig_zitaten`` zaehlt aufeinanderfolgende
        # Zitatzeilen). Er setzt ``mit_zitat`` NICHT: ein Stil ist die Wahl
        # der Gruppe, kein Satz aus einem Interview.
        stil = (figur["sprachstil"] or "").strip()
        if stil:
            zeilen.append(T.ZEILE_SPRACHSTIL.format(stil=stil))
        for satz in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
```

Ausserdem den Docstring von `_figuren_text` in seiner ersten Zeile
nachfuehren:

```python
    """Block 3: je Figur Beschreibung, Sprachprofil, gewaehlter Sprachstil
    und woertliche Zitate.
```

- [ ] **Schritt 6: Lauf zur Sicherheit, dass er besteht**

```
$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py
```

Erwartet: `6 passed`.

- [ ] **Schritt 7: Mutationsprobe (die Zeile wieder wegnehmen)**

Beweist, dass der Test den Fehler wirklich faengt -- Schritt fuer Schritt:

1. In `szene._figuren_text` die drei Zeilen
   `stil = (figur["sprachstil"] or "").strip()` / `if stil:` /
   `zeilen.append(T.ZEILE_SPRACHSTIL.format(stil=stil))` auskommentieren.
2. `$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py`
   -- erwartet: **3 failed, 3 passed**. Rot:
   `test_sprachstil_steht_im_szenen_prompt`,
   `test_sprachprofil_und_sprachstil_stehen_nebeneinander`,
   `test_jede_figur_bekommt_ihren_eigenen_stil`. Gruen bleiben
   `test_sprachstil_steht_nie_in_anfuehrungszeichen` und die beiden
   Negativtests -- sie pruefen Abwesenheit.
3. Kommentar zurueck.
4. Nochmal laufen -- erwartet: `6 passed`.

- [ ] **Schritt 8: Die Sprachschicht pruefen**

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py tests/test_pruefe_sprache.py
```

Erwartet: alles gruen. Wenn
`test_keine_unuebersetzte_konstante[szene]` rot ist, fehlt der TOML-Eintrag
aus Schritt 4; wenn `test_keine_nackte_verwendung[szene]` rot ist, steht im
Rumpf `ZEILE_SPRACHSTIL` statt `T.ZEILE_SPRACHSTIL`.

- [ ] **Schritt 9: Commit**

```bash
git add interview_theater/szene.py interview_theater/sprachen/en/texte.toml \
        tests/test_szene_sprachstil.py
git commit -m "szene: der gewaehlte Sprachstil je Figur steht im Szenen-Prompt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 2: Die Drei-Kopf-Regel

**Dateien:**
- Aendern: `interview_theater/szene.py` (neue Konstante hinter
  `ZEILE_SPRACHSTIL`; Kopfwahl in `_figuren_text`, heute Zeile 1091)
- Aendern: `interview_theater/sprachen/en/texte.toml` (Tabelle `["szene"]`)
- Aendern: `tests/test_szene_sprachstil.py` (anhaengen)

**Schnittstellen:**
- Verbraucht: `szene.ZEILE_SPRACHSTIL` (Aufgabe 1), `szene.FIGUREN_KOPF`,
  `szene.FIGUREN_KOPF_OHNE_STIMME` (beide **unveraendert**)
- Liefert: `szene.FIGUREN_KOPF_MIT_STIL` (`str`, keine Platzhalter) --
  Aufgabe 3 liest sie

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_szene_sprachstil.py` anhaengen:

```python
# ---------------------------------------------------------------------------
# Die Drei-Kopf-Regel: der Kopf verspricht nur, was darunter steht
# ---------------------------------------------------------------------------


def test_stil_allein_setzt_nicht_den_woertlich_kopf(conn, einst):
    """Audit-Befund S4, in die neue Lage uebertragen: nur **echte Zitate**
    rechtfertigen "aus ihrem Interview, woertlich". Ein Stil ist die Wahl der
    Gruppe -- stuende der woertlich-Kopf darueber, erfaende das Modell die
    Interviewstellen dazu, die es nicht sieht."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF not in text
    assert szene.FIGUREN_KOPF_MIT_STIL in text


def test_kopf_mit_stil_behauptet_nicht_mehr_fehlenden_beleg(conn, einst):
    """Widerspruch c9 aus ``docs/prompt-audit/2026-09-30-padua/BEFUND.md``:
    "Sprechweise ist noch nicht aus Interviews belegt" stand im Prompt,
    obwohl jede Figur einen von der Gruppe gewaehlten Stil hatte."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_OHNE_STIMME not in text
    assert "noch nicht aus Interviews belegt" not in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_ein_zitat_schlaegt_den_stil_beim_kopf(conn, einst):
    """Reihenfolge der drei Koepfe: Zitat vor Stil. Wer ein Zitat hat, hat
    die staerkste Vorlage -- und der Stil steht trotzdem darunter."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF in text
    assert szene.FIGUREN_KOPF_MIT_STIL not in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_ohne_stil_und_ohne_zitat_bleibt_der_alte_kopf_zeichengleich(conn, einst):
    """Die dritte Lage ist unveraendert -- und sie muss es sein, sonst
    aenderte sich der Prompt einer Gruppe, die nie einen Stil gewaehlt hat."""
    _figur(conn, zitate=())

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_OHNE_STIMME in text
    assert szene.FIGUREN_KOPF_MIT_STIL not in text
    assert szene.FIGUREN_KOPF not in text


def test_ein_stil_unter_mehreren_figuren_reicht_fuer_den_kopf(conn, einst):
    """Der Kopf gilt fuer den ganzen Block: eine Figur mit Stil genuegt, und
    der Kopf sagt deshalb ausdruecklich, was fuer die uebrigen gilt."""
    mit = _figur(conn, "Maria", zitate=())
    _figur(conn, "Elif", beschreibung="Nachbarin", profil="Lange Saetze.",
           zitate=())
    repo.setze_figur_sprachstil(conn, mit, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_MIT_STIL in text
    assert szene.FIGUREN_KOPF_OHNE_STIMME not in text
```

- [ ] **Schritt 2: Lauf zur Sicherheit, dass sie fehlschlagen**

```
$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py
```

Erwartet: **5 failed, 6 passed** -- die fuenf neuen scheitern mit
`AttributeError: module 'interview_theater.szene' has no attribute
'FIGUREN_KOPF_MIT_STIL'`.

- [ ] **Schritt 3: Den neuen Kopf anlegen -- deutsch**

In `interview_theater/szene.py` hinter `ZEILE_SPRACHSTIL`:

```python
#: Kopf, wenn keine Figur ein Zitat hat, aber mindestens eine einen von der
#: Gruppe gewaehlten Sprachstil (Padua M1, 02.10.2026 -- Widerspruch c9 in
#: ``docs/prompt-audit/2026-09-30-padua/BEFUND.md``). "Noch nicht aus
#: Interviews belegt" waere dann die Unwahrheit: die Gruppe HAT entschieden,
#: wie die Figuren sprechen. Umgekehrt behauptet er auch kein "woertlich aus
#: dem Interview" -- ein gewaehlter Stil ist kein Belegzitat.
FIGUREN_KOPF_MIT_STIL = (
    "Die Figuren (wer sie sind, was sie wollen). Wie sie sprechen, hat die "
    "Gruppe selbst gewaehlt -- halte die markierten Sprachstile durch; wo "
    "keiner steht, gib der Figur eine eigene, unterscheidbare Art zu reden "
    "(Satzlaenge, Tempo, Lieblingswoerter):"
)
```

- [ ] **Schritt 4: Den neuen Kopf anlegen -- englisch**

In `interview_theater/sprachen/en/texte.toml`, Tabelle `["szene"]`, neben die
beiden anderen Koepfe:

```toml
FIGUREN_KOPF_MIT_STIL = "The characters (who they are, what they want). The group chose how they speak -- keep up the speech styles marked below; where none is given, give the character their own distinct way of talking (sentence length, pace, favourite words):"
```

- [ ] **Schritt 5: Die Kopfwahl in `_figuren_text`**

`mit_stil` neben `mit_zitat` setzen und die eine Zeile `kopf = ...` ersetzen.

Die Schleifen-Initialisierung (heute `szene.py:1077`):

```python
    mit_zitat = False
    mit_stil = False
```

Im Stil-Block aus Aufgabe 1 das Merken ergaenzen:

```python
        stil = (figur["sprachstil"] or "").strip()
        if stil:
            zeilen.append(T.ZEILE_SPRACHSTIL.format(stil=stil))
            mit_stil = True
```

Und die Kopfwahl (heute `szene.py:1091`, die eine Zeile mit dem
Bedingungsausdruck) ersetzen durch:

```python
    # Drei Koepfe, in dieser Reihenfolge (Padua M1): ein echtes Zitat
    # rechtfertigt "woertlich"; sonst traegt ein von der Gruppe gewaehlter
    # Stil den Block; sonst verspricht der Kopf nichts.
    if mit_zitat:
        kopf = T.FIGUREN_KOPF
    elif mit_stil:
        kopf = T.FIGUREN_KOPF_MIT_STIL
    else:
        kopf = T.FIGUREN_KOPF_OHNE_STIMME
    return kopf + "\n\n" + "\n\n".join(bloecke)
```

Im Docstring-Kommentarblock ueber der Schleife (heute `szene.py:1071-1076`,
der Absatz zu Audit-Befund S4) einen Satz anhaengen:

```
    # Seit Padua M1 (02.10.2026) steht dazwischen ein dritter Kopf: hat
    # keine Figur ein Zitat, aber eine einen gewaehlten Sprachstil, ist
    # "noch nicht aus Interviews belegt" genauso falsch wie "woertlich".
```

- [ ] **Schritt 6: Lauf zur Sicherheit, dass sie bestehen**

```
$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py
```

Erwartet: `11 passed`.

- [ ] **Schritt 7: Mutationsprobe A -- `mit_zitat` erzwingen**

1. Im Stil-Block `mit_stil = True` **ersetzen** durch `mit_zitat = True`
   (genau der Fehler, gegen den Anforderung 2 schuetzt).
2. `$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py`
   -- erwartet: **3 failed, 8 passed**. Rot:
   `test_stil_allein_setzt_nicht_den_woertlich_kopf`,
   `test_kopf_mit_stil_behauptet_nicht_mehr_fehlenden_beleg`,
   `test_ein_stil_unter_mehreren_figuren_reicht_fuer_den_kopf`.
3. Zurueck auf `mit_stil = True`.
4. Nochmal laufen -- erwartet: `11 passed`.

- [ ] **Schritt 8: Mutationsprobe B -- den alten Kopf wieder waehlen**

1. Die `if/elif/else`-Kopfwahl ersetzen durch die alte Zeile
   `kopf = T.FIGUREN_KOPF if mit_zitat else T.FIGUREN_KOPF_OHNE_STIMME`.
2. Laufen -- erwartet: **3 failed, 8 passed** (dieselben drei; diesmal
   scheitern sie an `FIGUREN_KOPF_MIT_STIL in text` bzw. an
   `"noch nicht aus Interviews belegt" not in text`).
3. Die `if/elif/else`-Fassung zurueck.
4. Laufen -- erwartet: `11 passed`.

- [ ] **Schritt 9: Die Nachbarn pruefen, die an den Koepfen haengen**

```
$PY -m pytest -q -p no:cacheprovider tests/test_szene.py tests/test_prompt_audit.py \
     tests/test_sprache_texte.py tests/test_profil_bitgleich.py \
     tests/test_sprache_bitgleich.py tests/test_szenenfolge.py
```

Erwartet: alles gruen (dieselben Zahlen wie vor Aufgabe 1 -- hier wird
nichts neu gezaehlt, nur nichts rot).
`tests/test_prompt_audit.py::test_szene_verspricht_keine_stimmen_ohne_zitate`
bleibt im uebersprungenen Zweig, weil `tests/fixture_spaetstand.py`
`zitate=[]` und keinen `sprachstil` setzt.

- [ ] **Schritt 10: Commit**

```bash
git add interview_theater/szene.py interview_theater/sprachen/en/texte.toml \
        tests/test_szene_sprachstil.py
git commit -m "szene: drei Koepfe fuer Block 3 -- Zitat, sonst Stil, sonst nichts

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 3: Dasselbe auf Englisch

**Dateien:**
- Aendern: `tests/test_szene_sprachstil.py` (anhaengen)
- **Kein** Produktionscode

**Schnittstellen:**
- Verbraucht: `szene.T.ZEILE_SPRACHSTIL`, `szene.T.FIGUREN_KOPF_MIT_STIL`,
  `szene.T.FIGUREN_KOPF`, `szene.T.FIGUREN_KOPF_OHNE_STIMME`,
  `sprache.code`/`sprache.vergiss`

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_szene_sprachstil.py` anhaengen:

```python
# ---------------------------------------------------------------------------
# Englisch (Padua): dieselbe Regel, die Woerter aus der Sprachschicht
# ---------------------------------------------------------------------------


@pytest.fixture
def englisch(monkeypatch):
    """Dasselbe Muster wie ``tests/test_szene_sprache.py``: nicht das Profil
    umschalten, sondern die eine Funktion, die die Sprache liefert -- der
    Cache wird davor und danach vergessen."""
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    yield
    sprache.vergiss()


def test_englische_stilzeile_steht_im_prompt(conn, einst, englisch):
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert "Speech style (chosen by the group)" in text
    assert _schild(szene.ZEILE_SPRACHSTIL) not in text


def test_englischer_kopf_mit_stil_statt_woertlich(conn, einst, englisch):
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_MIT_STIL in text
    assert szene.T.FIGUREN_KOPF not in text


def test_englischer_kopf_sagt_nicht_mehr_unbelegt(conn, einst, englisch):
    """Widerspruch c9 am englischen Wortlaut (``texte.toml``, heute Zeile
    934): "Their way of speaking isn't backed by interviews yet"."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_OHNE_STIMME not in text
    assert "isn't backed by interviews yet" not in text


def test_englisch_ohne_stil_und_ohne_zitat_bleibt_der_alte_kopf(conn, einst, englisch):
    _figur(conn, zitate=())

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_OHNE_STIMME in text
    assert szene.T.FIGUREN_KOPF_MIT_STIL not in text


def test_beide_fassungen_tragen_denselben_platzhalter():
    """Die Zusicherung aus ``tests/test_sprache_texte.py``, hier noch einmal
    als lesbarer Satz: wer den deutschen Wortlaut aendert und den englischen
    vergisst, merkt es an beiden Stellen."""
    assert "{stil}" in szene.ZEILE_SPRACHSTIL
    assert sprache.platzhalter(szene.ZEILE_SPRACHSTIL) == sprache.platzhalter(
        sprache.tabelle("en")["szene"]["ZEILE_SPRACHSTIL"])
    assert sprache.platzhalter(szene.FIGUREN_KOPF_MIT_STIL) == sprache.platzhalter(
        sprache.tabelle("en")["szene"]["FIGUREN_KOPF_MIT_STIL"])
```

- [ ] **Schritt 2: Lauf zur Sicherheit, dass er die Sprachschicht wirklich prueft**

```
$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py
```

Erwartet: `16 passed` (11 aus Aufgabe 1+2, 5 neu). Diese Tests brauchen
**keinen** neuen Produktionscode -- sie bestehen sofort, wenn die TOML-Zeilen
aus Aufgabe 1 Schritt 4 und Aufgabe 2 Schritt 4 wirklich dastehen.

- [ ] **Schritt 3: Mutationsprobe -- den englischen Eintrag wegnehmen**

1. In `interview_theater/sprachen/en/texte.toml` die Zeile
   `ZEILE_SPRACHSTIL = "  Speech style (chosen by the group): {stil}"`
   in der Tabelle `["szene"]` auskommentieren (`#` davor).
2. `$PY -m pytest -q -p no:cacheprovider tests/test_szene_sprachstil.py tests/test_sprache_texte.py`
   -- erwartet: `test_englische_stilzeile_steht_im_prompt` **rot** (der
   Rueckfall liefert den deutschen Text, also scheitert
   `"Speech style (chosen by the group)" in text`),
   `test_beide_fassungen_tragen_denselben_platzhalter` **rot** (`KeyError`),
   und aus der Sprachschicht
   `tests/test_sprache_texte.py::test_jeder_zugriff_hat_einen_englischen_eintrag`
   **rot** mit `['szene.ZEILE_SPRACHSTIL']`.
3. Kommentar zurueck.
4. Beide Dateien nochmal laufen -- erwartet: alles gruen.

- [ ] **Schritt 4: Die Sprachpruefung des Profils**

```
$PY -m pytest -q -p no:cacheprovider tests/test_sprache_texte.py \
     tests/test_pruefe_sprache.py tests/test_chat_sprache.py \
     tests/test_sprache_prompts.py
```

Erwartet: alles gruen. `tests/test_pruefe_sprache.py::test_padua_ist_frei_von_deutsch`
ist der Waechter dafuer, dass im neuen englischen Wortlaut kein deutsches
Wort steckt.

- [ ] **Schritt 5: Commit**

```bash
git add tests/test_szene_sprachstil.py
git commit -m "test: Stilzeile und Drei-Kopf-Regel auch auf Englisch

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 4: AGENTS.md

**Dateien:**
- Aendern: `AGENTS.md` (nach Zeile 331, hinter dem Punkt "Der Szenen-Prompt
  bekommt die Schaerfungen JE SZENE, nicht global", vor "Die Form je Szene
  ist ein Vorschlag")

**Schnittstellen:** keine.

- [ ] **Schritt 1: Den Aufzaehlungspunkt einfuegen**

Genau dieser Text, als neuer Punkt zwischen den beiden genannten:

```markdown
- **Der Szenen-Prompt liest auch den gewählten Sprachstil** (02.10.2026,
  Padua M1): `szene._figuren_text` setzt `figur.sprachstil` als eigene Zeile
  (`ZEILE_SPRACHSTIL`, nie in Anführungszeichen — ein Stil ist kein
  Belegzitat) neben `sprachprofil` und die Zitate; den Kopf von Block 3
  wählen seitdem **drei** Lagen: ein echtes Zitat → `FIGUREN_KOPF`
  („wörtlich"), sonst ein nicht-leerer Stil → `FIGUREN_KOPF_MIT_STIL`
  (die Gruppe hat gewählt), sonst `FIGUREN_KOPF_OHNE_STIMME` (unverändert).
  Vorher war der Einzelszenen-Prompt mit und ohne Stil byte-identisch
  (`docs/sprachstil-wirkung-2026-09-30.md`, Weg 2).
```

- [ ] **Schritt 2: Die Doku-Tests laufen lassen**

```
$PY -m pytest -q -p no:cacheprovider -k "doku or agents"
```

Erwartet: gruen (oder `no tests ran` -- dann gibt es fuer diesen Bereich
keinen Doku-Test und der Schritt ist erledigt).

- [ ] **Schritt 3: Commit**

```bash
git add AGENTS.md
git commit -m "AGENTS.md: die Einzelszene liest den Sprachstil, drei Koepfe fuer Block 3

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Aufgabe 5: Abnahme -- Pfadnachweis, Profil, ganze Suite

**Dateien:** keine Aenderung. Nur messen und vergleichen.

- [ ] **Schritt 1: Den Pfadnachweis auf Deutsch neu fahren**

**Niemals** nach `docs/sprachstil-wirkung-2026-09-30/` schreiben -- das ist
der eingecheckte Messbericht vom 30.09.2026 und bleibt, wie er ist. Ziel ist
ein Wegwerf-Verzeichnis **im Worktree** (die Werkzeuge dieser Sitzung duerfen
`/tmp` nicht lesen):

```
mkdir -p .scratch-m1
$PY -m scripts.sprachstil_wirkung pfad --ausgabe .scratch-m1/nachher
```

Kein Netz, kein Modell, kein `IT_*` noetig: das Skript baut sein `e` selbst
(`sprachstil_wirkung.einstellungen_szene`, `SimpleNamespace`) und seine
Wegwerf-Datenbanken in einem `TemporaryDirectory`. Ohne `IT_WORKSHOP` gilt
das eingebaute Vorgabeprofil (Dortmunder Werte, deutsch).

Erwartete Ausgabe -- **genau diese vier Zeilen** (vorher waren die beiden
Szenenzeilen `identisch`):

```
prosa A-B: 5 Zeilen geaendert (+0/-5)
prosa A-C: 3 Zeilen geaendert (+3/-3)
szene A-B: 3 Zeilen geaendert (+0/-3)
szene A-C: 3 Zeilen geaendert (+3/-3)
```

- [ ] **Schritt 2: Den Inhalt der beiden Szenen-Diffs pruefen**

```
wc -c .scratch-m1/nachher/prompts/diff-szene-A-B.diff
wc -c .scratch-m1/nachher/prompts/diff-szene-A-C.diff
cat .scratch-m1/nachher/prompts/diff-szene-A-B.diff
cat .scratch-m1/nachher/prompts/diff-szene-A-C.diff
```

**Erwartet, und vorher vorhergesagt:**

`diff-szene-A-B.diff` ist **nicht** 0 Byte und enthaelt **genau drei
entfernte Zeilen** -- je Figur eine, in der Reihenfolge Meryem, Ferzan,
Aynur, mit den Stilwerten aus `sprachstil_wirkung.STILE`:

```
-  Sprachstil (von der Gruppe gewaehlt): Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter.
-  Sprachstil (von der Gruppe gewaehlt): Verschachtelt, gelehrt: Wobei man insofern, als das Zurueckgehen de facto gar keine Option ist, prinzipiell sagen muesste, dass der Koffer per se gewissermassen quasi schon ausgepackt ist.
-  Sprachstil (von der Gruppe gewaehlt): Mit Fuellwoertern: Also, weisst du, der Koffer ist halt irgendwie, also sozusagen, der Koffer ist halt noch zu, weisst du.
```

Keine hinzugefuegte Zeile (`+0`), und jede Stilzeile steht zwischen der
Sprachprofil-Zeile und der ersten Zitatzeile der Figur.

`diff-szene-A-C.diff` zeigt **dieselben drei Zeilen getauscht** (`+3/-3`):
in C traegt Meryem SCHACHTEL, Ferzan FUELL, Aynur KNAPP.

**Kein Kopfwechsel in diesen Diffs** -- und das ist vorhergesagt, nicht
uebersehen: `sprachstil_wirkung.FIGUREN` gibt allen drei Figuren Zitate
(`repo.setze_sprachprofil(..., zitate)`), also ist `mit_zitat` in A, B **und**
C wahr, und der Kopf bleibt in allen drei Fassungen `FIGUREN_KOPF`. Die
Drei-Kopf-Regel ist in Aufgabe 2 am Unit-Test nachgewiesen, nicht hier. Steht
in einem der beiden Diffs eine Kopfzeile, ist etwas anderes passiert als
geplant -- nachsehen, nicht wegdruecken.

Die beiden Prosa-Diffs muessen **unveraendert** `+0/-5` bzw. `+3/-3` sein:
`kurzgeschichte.py` wurde nicht angefasst.

- [ ] **Schritt 3: Denselben Nachweis auf Englisch**

```
IT_WORKSHOP=padua-2026 $PY -m scripts.sprachstil_wirkung pfad --ausgabe .scratch-m1/nachher-en
cat .scratch-m1/nachher-en/prompts/diff-szene-A-B.diff
```

Erwartet: dieselben vier Zaehlzeilen wie in Schritt 1, und im Diff die
englische Beschriftung:

```
-  Speech style (chosen by the group): Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter.
```

(Der **Wert** bleibt deutsch -- es ist der erfundene Stiltext des Skripts,
kein uebersetzter Prompt-Baustein.)

- [ ] **Schritt 4: Das Dortmunder Profil**

```
$PY -m scripts.pruefe_profil dortmund-2026
```

Erwartet, woertlich:

```
Workshop-Profil dortmund-2026
dortmund-2026: in Ordnung
```

- [ ] **Schritt 5: Die ganze Suite, gegen die gemessene Messlatte**

```
$PY -m pytest -q -p no:cacheprovider
```

**Messlatte vom 02.10.2026, vor der Aenderung:**
`1 failed, 5008 passed, 2 skipped in 426.99s`, Fehlschlag
`tests/test_simulation_lauf.py::test_ersatzfunktion_nimmt_die_parameter_des_originals_an[_sofort_szene]`.

**Erwartet nachher:** `1 failed, 5024 passed, 2 skipped` -- derselbe,
vorbestehende Fehlschlag und **16 neue** bestandene Tests aus
`tests/test_szene_sprachstil.py`. (Die Sprachschicht erzeugt zusaetzlich
automatisch zwei neue parametrisierte Faelle
`test_platzhalter_und_form_gleich[szene-ZEILE_SPRACHSTIL]` und
`[szene-FIGUREN_KOPF_MIT_STIL]`; dadurch kann die Gesamtzahl um bis zu zwei
hoeher liegen. Entscheidend ist: **`failed` bleibt bei genau 1, und es ist
derselbe Test.** Jeder andere rote Test ist ein Befund dieser Karte.)

- [ ] **Schritt 6: Das Wegwerf-Verzeichnis entfernen und den Baum pruefen**

```
rm -rf .scratch-m1
git status --short
```

Erwartet: kein `.scratch-m1`, nichts unter `docs/sprachstil-wirkung-2026-09-30/`
geaendert, und ausser den schon vorhandenen Fremddateien
(`.cc-run-*`, `.cc-settings.json`, `.superpowers-brief-*`) nichts Unversioniertes.

- [ ] **Schritt 7: Abschluss melden**

Kein Commit mehr noetig (Aufgaben 1-4 haben committed). Dem Menschen
berichten: die vier Zaehlzeilen aus Schritt 1, die Diff-Inhalte aus Schritt 2,
die Suite-Zahlen aus Schritt 5 -- mit der Messlatte daneben. **Kein `push`,
kein `merge`.**

---

## Offene Punkte

Hier stehen die Stellen, an denen der Entwurf an vorhandenen Code stiess.
Gewaehlt ist jeweils die am wenigsten invasive Variante; wo eine Entscheidung
aussteht, steht sie hier und nicht im Code.

1. **Der Szenenfolge-Prompt bekommt die Stilzeile mit.**
   `szenenfolge._material` (`szenenfolge.py:984-999`) ruft
   `szene._figuren_text` und speist damit `szenenfolge.baue_nutzertext`
   (Szenenfolge-Vorschlag) und `starte_feldvorschlag` (fehlende Angaben je
   Szene). Beide sehen ab jetzt die Stilzeilen. **Bewusst nicht umgangen:**
   der Docstring von `_material` sagt ausdruecklich *"Aus `szene.py` geholt
   statt hier zweitgepflegt -- laeuft der Szenen-Prompt auseinander, laeuft
   auch dieser mit."* Ein Flag oder eine zweite Funktion waere die zweite
   Wahrheit, die er verhindert. Fachlich schadet es nicht (wer eine
   Szenenfolge vorschlaegt, darf wissen, wie die Figuren reden), aber es ist
   eine Prompt-Aenderung an zwei weiteren Stellen -- **Birk sollte es
   wissen.** `szenenfolge._erfundenes` (Phase 4, kein Material) ist nicht
   betroffen.
2. **Zwei Figuren mit demselben Stil erzeugen zwei wortgleiche Zeilen.**
   Die Audit-Regel "kein Satz ueber 80 Zeichen zweimal"
   (`tests/test_prompt_audit.py::_pruefe_ohne_dubletten`) wuerde das als
   Dublette lesen. Heute schlaegt kein Test an, weil
   `tests/fixture_spaetstand.py` keinen `sprachstil` setzt. Im Betrieb kann
   es vorkommen -- es ist dann aber die Wahl der Gruppe (zwei Figuren sollen
   gleich klingen) und keine Prompt-Dublette im Sinne des Audits. **Nicht
   behoben, bewusst:** eine Entdopplung ("Maria und Elif: <Stil>") waere ein
   eigener Entwurf und gehoert nicht in einen Pfadnachweis.
3. **`docs/sprachstil-wirkung-2026-09-30.md` bleibt, wie es ist.** Seine
   Tabellenzeile *"(2) Einzelszene direkt, Phase 7 -- wirkt nicht (per
   Konstruktion)"* und Abschnitt 1 sind ein **datiertes Messergebnis** vom
   30.09.2026; ein Bericht, der nachtraeglich umgeschrieben wird, ist kein
   Bericht mehr. Der neue Stand steht in `AGENTS.md` (Aufgabe 4). Dass die
   Empfehlung aus Abschnitt 7 (*"Wer will, dass der gewaehlte Stil den
   Theatertext praegt, muesste `figur.sprachstil` in den Szenen-Prompt
   nehmen -- das ist eine Produktentscheidung"*) mit dieser Karte
   eingeloest ist, ist der Zweck der Karte. **Birk entscheidet**, ob der
   Bericht einen Nachtrag bekommt.
4. **Was dieser Fix NICHT misst.** Ob der Stil den Theatertext *wirkt*,
   steht nicht fest -- gemessen ist nur, dass er **ankommt** (Pfadnachweis).
   Ein Wirkungslauf waere `sprachstil_wirkung lauf --pfad szene` mit n = 3
   und kostet Modellzeit; er ist in dieser Karte ausdruecklich **nicht**
   enthalten (Global Constraint 1).
5. **Zwei Stimmangaben je Figur koennen sich widersprechen** -- das hat die
   Messkarte vom 30.09. vorhergesagt (Abschnitt 7: *"gehoert vorher gegen
   das Sprachprofil abgewogen"*). Der Entwurf laesst beide stehen und
   benennt sie unterschiedlich (Profil = gemessen, Stil = *von der Gruppe
   gewaehlt*), statt eine Vorrangregel in den Prompt zu schreiben. Welche
   Angabe im Zweifel staerker wiegen soll, ist eine Regieentscheidung --
   **offen fuer Birk**, und sie waere ein Satz im Kopf von Block 3, kein
   Code.
6. **Der vorbestehende Suite-Fehlschlag** (`_sofort_szene` gegen
   `szene.starte`) ist nicht Teil dieser Karte und wird nicht mit behoben --
   er liegt in `simulation/lauf.py` und gehoert zur Karte, die `art="szene"`
   eingefuehrt hat.

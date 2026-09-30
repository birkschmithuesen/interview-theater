# Padua A3: die User-Simulation gegenpruefen — faengt sie echte Fehler?

> **Fuer agentische Umsetzer:** ERFORDERLICHE UNTER-SKILL: Nutze
> `superpowers:subagent-driven-development` (empfohlen) oder
> `superpowers:executing-plans`, um diesen Plan Aufgabe fuer Aufgabe
> umzusetzen. Die Schritte tragen Checkboxen (`- [ ]`) zum Mitfuehren.

**Ziel:** Nachweisen — nicht behaupten —, ob `simulation/` die zwei belegten
Dortmunder Fehler vom 06.09.2026 findet: den Verlust von 22 von 42
Festlegungen in Phase 4 und den Neuaufbau der Szenenfolge (3 → 6 Szenen).
Dazu die Abdeckung der heutigen sieben Phasen deterministisch erheben, die
fehlenden mechanischen Kennzahlen nachruesten, und das Ergebnis in
`docs/simulation-gegenpruefung-2026-09-30.md` mit dem Urteil „prueft sinnvoll
/ teilweise / nicht" festhalten.

**Architektur:** Kein Produktivcode wird geaendert. Die Fehler werden ueber
ein neues Modul `simulation/mutation.py` **zur Laufzeit** wieder eingebaut —
dieselbe Bauart, mit der `simulation/lauf.py` (`einfaedig`,
`kontext_protokoll`) und `simulation/stoerung.py` schon heute
Betriebsverhalten voruebergehend ersetzen. Die neuen Kennzahlen sind reine
Leseabfragen in `simulation/kennzahlen.py` (kein Modell). Das Skript
`skript.SCHRITTE_TAG2` wird auf die heutigen sieben Phasen nachgezogen und
ueber einen neuen Schalter `--skript tag2` auch fuer die erfundenen Sets 1–3
fahrbar gemacht.

**Tech-Stack:** Python 3.11, Standardbibliothek + `httpx`, SQLite, pytest.
Kein Netzzugriff in Tests (Attrappen). Die bezahlten Laeufe gehen gegen
Infomaniak (Bot) und den lokalen Claude-Proxy (Stimmen, Richter).

---

## Gemessene Basis (selbst gemessen, nicht uebernommen)

Auf `d8deb6c` (Basis dieses Arbeitsbaums), mit
`$PY -m pytest -q -p no:cacheprovider`:

```
2768 passed, 1 skipped in 199.49s (0:03:19)
```

0 errors, 0 failures. **Diese Zahl ist die Messlatte** — nach jeder Aufgabe
muessen es mindestens 2768 bestandene Tests sein, plus die neuen.

**Interpreter.** Ueberall unten:

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
```

Das `.venv` des Hauptbaums **nicht** benutzen; das System-`python3` ist 3.9
und scheitert am `X | None` der Modulkoepfe.

**Suite-Kommando (unten `SUITE` genannt):**

```bash
$PY -m pytest -q -p no:cacheprovider
```

Wartend ausfuehren, nie im Hintergrund. Dauer rund 200 s.

---

## Die Praemissenpruefung: was am Verdacht stimmt und was nicht

Der Kartentext vermutet: „README/Skript beschreiben noch neun Schritte,
Phase 5 = Format & Rahmen — alter Phasenstand." **Selbst am Code geprueft
(30.09.2026, `d8deb6c`), Ergebnis gemischt.** Der Plan baut darum nicht
herum, sondern trennt die drei Faelle:

| Behauptung | Fundstelle | Heute im Code | Urteil |
|---|---|---|---|
| „Neun Schritte" | `simulation/README.md:4`, `simulation/README.md:66`, `simulation/skript.py:3`, `simulation/skript.py:288`, `tests/test_simulation_durchlauf.py:1` + `:183` | `len(skript.SCHRITTE) == 10` (`begriffe, fragen, interviews, kernthema, figuren, phase_mitte, szene, zitate, korrektur, stand`) | **falsch** — es sind zehn |
| „Phase 5 (Format & Rahmen)" | `simulation/README.md:5-6` | `phasen.kurzname(5) == "Schaerfung"`; „Format & Rahmen" gibt es seit dem 06.09.2026 nicht mehr | **falsch** |
| Schritt-Titel „Phase 5" | `simulation/skript.py:337` (`Schritt("phase_mitte", "Phase 5", …)`) | `skript.PHASE_MITTE == 4`, und `phasen.kurzname(4) == "Setting, Figuren & Geschichte"` | **falsch** — Titel nennt 5, geprueft wird 4 |
| Docstrings nennen `rahmen`/`format` als Pflichtfeld der mittleren Phase | `simulation/skript.py:12-23`, `:114-127`, `simulation/kennzahlen.py:549-557` | `skript.pflichtfeld_fuer_phase(conn, 4)` liefert **`geschichte`** (gemessen gegen ein frisches Schema) | Doku veraltet, **Verhalten richtig** |
| „Das Skript der acht Phasen" (`SCHRITTE_TAG2`) | `simulation/skript.py:541`, `:550`, `simulation/README.md:243` | `len(phasen.PHASEN) == 7`; `SCHRITTE_TAG2` faehrt `_phasenschritt(2..7)`, also **sieben**. Der Kommentar bei `simulation/skript.py:636` sagt schon „sieben" — die Datei widerspricht sich selbst | **falsch**, aber nur in der Doku |
| `PHASE_SZENENTEXTE = 6`, `PHASE_DURCHLAUF` | `simulation/skript.py:561-563` | Phase 6 heisst „Szenen als Geschichte", Phase 7 „Feinschliff"; „Szenentexte" und „Durchlauf" sind Namen des Stands vom 05.09. | Namen veraltet, Nummern richtig |

**Zwei Befunde, die der Verdacht nicht nennt und die schwerer wiegen:**

1. **Das Skript der erfundenen Sets (`SCHRITTE`) faehrt die heutigen Phasen
   gar nicht.** `scripts/simulation.py:228-235` (`_schritte`) waehlt
   `SCHRITTE_TAG2` **nur** fuer `--set tag1-*`/`--set regie`. `--set 1|2|3`
   faehrt `SCHRITTE` — zehn Schritte **ohne einen einzigen
   `art='phase'`-Schritt**, mit einem Schritt `kernthema`, dessen Station es
   seit dem 06.09. nicht mehr gibt („Das Kernthema ist keine eigene Station
   mehr", AGENTS.md), und **ohne** die Schritte `setting`, `geschichte`,
   `schaerfung`. Beide Dortmunder Fehler liegen genau dort. Die zuletzt
   gefahrenen Set-Laeufe belegen es: `simulation/berichte/verlauf.jsonl`
   Zeilen 5–7 tragen `"phase_erreicht_name": "5 · Format & Rahmen"`.
2. **Die Modellaufrufe der Phasen 4–6 laufen in Daemon-Threads, die der
   Simulator nicht einfaedig macht.** `lauf.einfaedig()` (lauf.py:260-286)
   ersetzt `szene.starte`, `aufnahme.starte_abschluss`,
   `aufnahme.starte_auswertung` und `ablauf.starte_auftrag` — **nicht**
   `szenenfolge.starte_geschichte_szenen` (szenenfolge.py:1125),
   `schaerfung.starte`, `sprachstil.starte`, `kurzgeschichte.starte`. Deren
   Wirkung landet zu einem beliebigen Zeitpunkt in der Datenbank, unter
   Umstaenden nach `conn.close()` in `scripts/simulation.py:408`. Ein
   Mutationslauf, dessen Kernwirkung in so einem Thread haengt, misst nichts.

Daraus folgt die Reihenfolge dieses Plans: erst die Abdeckung erheben
(Aufgabe 1), dann die Mutationen samt deterministischem Nachweis bauen
(Aufgaben 2–3), dann die Kennzahlen (4–6), dann das Skript fahrbar machen
(7), und erst danach Geld ausgeben (9–11).

---

## Global Constraints

- **Branch:** ausschliesslich `padua-workshop/t_a4ae02fa-plan-a3-simulation`.
  Kein `merge`, kein `push`, kein `checkout`/`switch`, kein zweiter
  Arbeitsbaum.
- **Sprache:** Deutsch, ASCII-Umschrift (`ue`/`oe`/`ae`/`ss`) in Code,
  Docstrings, Kommentaren und Commit-Messages. In `docs/*.md` sind Umlaute
  erlaubt, ASCII ist aber ueberall zulaessig — halte es je Datei einheitlich.
- **Kein Produktivcode.** `git diff d8deb6c -- interview_theater/` muss am
  Ende **leer** sein. Geaendert werden nur: `simulation/**`, `scripts/**`,
  `tests/**`, `docs/**`, `AGENTS.md`.
- **Keine Mutationsweiche im Produktivcode** — auch keine Umgebungsvariable,
  die `interview_theater/*` liest. Die Mutationen leben in
  `simulation/mutation.py` und wirken ueber Monkey-Patching.
- **Keine Echtdaten.** `betrieb/soap.db` nicht oeffnen, keine Zeile daraus in
  ein Artefakt. `betrieb/gruppe1.env` wird fuer die bezahlten Laeufe
  gesourct (so steht es in `simulation/README.md:11`), sein Inhalt wandert
  nirgendwohin. `--set birk` und `--set tag1-*`/`--set regie` sind in diesem
  Plan **verboten**: Echtmaterial-Bezug darf nicht an das US-Modell der
  Simulationsseite gehen.
- **Keine Laufberichte ins Repo.** `simulation/laeufe/` und
  `simulation/berichte/` (ausser `verlauf.jsonl`) sind gitignored und
  bleiben es. In `docs/simulation-gegenpruefung-2026-09-30.md` stehen **nur
  Zahlen** — keine Modellantwort, kein Chatverlauf, kein Belegzitat.
- **Budget:** hoechstens **10 CHF** Infomaniak-Kosten insgesamt. Erwartung je
  Lauf 0,55 CHF (Ableitung in Aufgabe 8). Abbruch, sobald ein einzelner Lauf
  `chf_bot > 1.10` meldet (das Doppelte der Erwartung) oder die Summe 8 CHF
  ueberschreitet.
- **Suite nach jeder Aufgabe gruen**, Zahl >= 2768 + neue Tests.
- **Ein Commit je Aufgabe**, nur die in der Aufgabe genannten Dateien.
  `.cc-settings.json`, `.superpowers-brief-*.md`, `.cc-run-*` niemals
  committen.

---

## Dateien, die entstehen oder sich aendern

| Datei | Verantwortung |
|---|---|
| `scripts/simulation_abdeckung.py` | **neu.** Erzeugt die Abdeckungstabelle aus dem Code (Phasen aus `phasen.PHASEN`, Schritte aus `skript.*`, Inventare aus `erkenner.ARTEN` und `knoepfe.texte.ART_*`), prueft die Behauptungen der Doku gegen den Code, liest optional Knopf- und Aufruf-Abdeckung aus einer Lauf-Datenbank. Kein Modell, kein Netz. |
| `simulation/mutation.py` | **neu.** Die zwei Fehler als Kontextmanager `aktiv(art)`, per Monkey-Patch. Kein Projektimport auf Modulebene ausser `importlib`. |
| `simulation/kennzahlen.py` | **+** `festlegungslage`, `szenenlage`, `_dauerhafter_text`; beide in `sammle` eingehaengt. |
| `simulation/skript.py` | **+** `FESTLEGUNGSPROBEN`, Schritt `festlegungen` in `SCHRITTE_TAG2`, `_fertig_festlegungen`; Docstrings und Konstantennamen auf sieben Phasen nachgezogen. |
| `simulation/lauf.py` | **+** `warte_auf_hintergrund`, `HINTERGRUND_S`, Aufruf in `_zug`/`_schliesse_zug`; `_merker` liefert `festlegungsproben`. |
| `simulation/bericht.py` | **+** die neuen Kennzahlen in `kennzahlen_tabelle`; `mutation` in `verlaufszeile`. |
| `scripts/simulation.py` | **+** `--skript {auto,schritte,tag2,birk}`, `--mutation {…}`; `mischungsname` traegt die Mutation. |
| `simulation/README.md` | Phasenstand, Schrittzahl, die neuen Schalter. |
| `tests/test_simulation_abdeckung.py` | **neu.** Der Zensus ohne Netz. |
| `tests/test_simulation_mutation.py` | **neu.** Je Mutation der deterministische Nachweis, dass sie den Fehler wirklich wieder erzeugt. |
| `tests/test_simulation_kennzahlen.py` | **+** die neuen Kennzahlen, beide Richtungen (mutiert schlaegt an, heute nicht). |
| `tests/test_simulation_lauf.py` | **+** `warte_auf_hintergrund`. |
| `tests/test_simulation_skript.py` | **+** der Schritt `festlegungen`, die Proben, die Phasennamen. |
| `docs/simulation-gegenpruefung-2026-09-30.md` | **neu.** Der Ergebnisbericht. |
| `AGENTS.md` | Abschnitt „Simulation" nur angleichen, wenn sich Kennzahlen oder Schritte geaendert haben (sie haben — siehe Aufgabe 13). |

---

## Aufgabe 0: Vorbedingungen pruefen (kostenlos)

Alles hier ist eine **Messung**, keine Aenderung. Ergebnis kommt in die
Notizen und spaeter in den Bericht. Kein Commit.

**Dateien:** keine.

- [ ] **Schritt 1: Basis und Sauberkeit**

```bash
git rev-parse --short HEAD
git status --short
```

Erwartet: `d8deb6c` (oder der Nachfolger auf diesem Branch) und ausser
`.cc-*`/`.superpowers-brief-*` nichts. Sind andere Dateien geaendert, **nicht
weiterarbeiten** — melden.

- [ ] **Schritt 2: Basiszahl der Suite selbst nachmessen**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Erwartet: `2768 passed, 1 skipped`. Weicht die Zahl ab, ist **die eigene
Zahl** die Messlatte; im Bericht steht dann beides.

- [ ] **Schritt 3: ANNAHME — ist der Simulations-Proxy erreichbar?**

Der Richter und die Stimmen laufen ueber `IT_SIM_URL` (Vorgabe
`http://127.0.0.1:28764/v1/messages`, `simulation/README.md:39`). **Diese
Annahme konnte beim Planen nicht geprueft werden.**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -m 5 \
  -X POST "${IT_SIM_URL:-http://127.0.0.1:28764/v1/messages}" \
  -H 'content-type: application/json' \
  -d '{"model":"claude-opus-5","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}'
```

Erwartet: `200`. Kommt `000` (keine Verbindung) oder `4xx/5xx`, sind die
Aufgaben 9–11 **nicht ausfuehrbar**. Dann: Aufgaben 1–8 und 12–13 vollstaendig
erledigen, in Aufgabe 12 alle Laufspalten mit `nicht gemessen (Proxy nicht
erreichbar)` fuellen und das Urteil allein auf die deterministischen
Nachweise stuetzen — ausdruecklich als solches gekennzeichnet.

- [ ] **Schritt 4: ANNAHME — ist die Bot-Seite erreichbar?**

```bash
set -a; . ./betrieb/gruppe1.env; set +a
$PY - <<'PY'
import os
print("IT_LLM_URL gesetzt:", bool(os.environ.get("IT_LLM_URL")))
print("IT_DB gesetzt:", bool(os.environ.get("IT_DB")))
print("IT_MODELL:", os.environ.get("IT_MODELL", "(Vorgabe)"))
PY
```

Erwartet: beide `True`. **Keinen Wert ausgeben, keinen Wert notieren** — nur
das `True`. Fehlt die Env-Datei, gilt dasselbe wie in Schritt 3.

- [ ] **Schritt 5: erwartete Kosten je Lauf aus den echten Zahlen lesen**

```bash
$PY - <<'PY'
import json, statistics
z = [json.loads(l) for l in open("simulation/berichte/verlauf.jsonl") if l.strip()]
erfunden = [x for x in z if x["mischung"].startswith(("set", "mix"))]
tag2 = [x for x in z if x["mischung"].startswith(("tag1", "regie"))]
for name, gruppe in (("erfundene Sets (Skript SCHRITTE)", erfunden),
                     ("Skript SCHRITTE_TAG2", tag2)):
    werte = [x["chf_bot"] for x in gruppe]
    print(f"{name}: n={len(werte)} min={min(werte)} max={max(werte)} "
          f"median={statistics.median(werte)}")
PY
```

Erwartet (gemessen 30.09.2026):

```
erfundene Sets (Skript SCHRITTE): n=4 min=0.2547 max=0.4084 median=0.29125
Skript SCHRITTE_TAG2: n=4 min=0.3280 max=0.6360 median=0.3382
```

Diese Zahlen sind die Grundlage der Budgetrechnung in Aufgabe 8. Weichen sie
ab, gilt die eigene Messung.

---

## Aufgabe 1: Abdeckungszensus, deterministisch aus dem Code (kostenlos)

Die Abdeckungstabelle des Berichts darf nicht abgeschrieben sein. Dieses
Skript erzeugt sie — aus `phasen.PHASEN`, aus den drei Skriptlisten, aus
`erkenner.ARTEN` und `knoepfe.texte.ART_*` — und prueft nebenbei jede
Behauptung der Doku gegen den Code.

**Dateien:**
- Create: `scripts/simulation_abdeckung.py`
- Test: `tests/test_simulation_abdeckung.py`

**Interfaces:**
- Produces:
  - `SKRIPTE: dict[str, tuple]` — `{"schritte": skript.SCHRITTE, "tag2": skript.SCHRITTE_TAG2, "birk": skript.SCHRITTE_BIRK}`
  - `phase_je_schritt(schritte) -> dict[str, int | None]`
  - `titelphasen(schritte) -> list[dict]` — `{"schluessel", "titel", "titel_phase", "zugeordnet", "stimmt"}`
  - `phasentabelle(conn, schritte) -> list[dict]` — je Phase `{"nummer", "kurzname", "felder", "pflichtfeld", "schritte", "pruefungen", "gefahren"}`
  - `inventar() -> dict` — `{"erkenner_arten", "erkenner_in_aufnahme", "knopfarten"}`
  - `BEHAUPTUNGEN: tuple[tuple[str, str, Callable[[], bool]], ...]`
  - `praemissenpruefung(wurzel) -> list[dict]` — `{"datei", "text", "zeilen", "stimmt", "status"}` mit `status in {"gefunden_richtig", "gefunden_falsch", "bereinigt"}`
  - `knopfarten_aus_db(conn) -> list[dict]` — `{"art", "angeboten", "gedrueckt"}`
  - `laeufe_aus_db(conn) -> dict[str, int]` — `art -> Anzahl` aus `aufruf`
  - `als_markdown(conn, wurzel, db=None) -> str`
  - `main(argv=None) -> int`

- [ ] **Schritt 1: Den Test schreiben (er faellt, weil das Modul fehlt)**

`tests/test_simulation_abdeckung.py`:

```python
"""Der Abdeckungszensus -- ohne Netz, ohne Modell.

Er erzeugt die Tabelle, die im Ergebnisbericht steht. Getestet wird deshalb
nicht nur, dass er laeuft, sondern dass er die Befunde **aus dem Code** zieht:
eine Tabelle, die man abschreiben koennte, braeuchte diesen Test nicht.
"""

import tempfile
from pathlib import Path

import pytest

from interview_theater import db, erkenner, phasen, repo
from interview_theater.knoepfe import texte
from scripts import simulation_abdeckung as abdeckung
from simulation import skript


@pytest.fixture
def leer():
    """Ein frisches Schema -- ``felder_fuer_phase`` liest ``PRAGMA
    table_info(arbeitsstand)``, also braucht der Zensus eine Verbindung."""
    ordner = tempfile.mkdtemp(prefix="abdeckung-")
    conn = db.verbinde(str(Path(ordner) / "t.db"))
    db.initialisiere(conn)
    return conn


def test_alle_drei_skripte_sind_erfasst():
    assert set(abdeckung.SKRIPTE) == {"schritte", "tag2", "birk"}
    assert abdeckung.SKRIPTE["tag2"] is skript.SCHRITTE_TAG2


def test_phase_je_schritt_folgt_den_phasenschritten():
    """In ``SCHRITTE_TAG2`` setzt jeder ``art='phase'``-Schritt die laufende
    Phase; die Schritte danach gehoeren zu ihr."""
    zuordnung = abdeckung.phase_je_schritt(skript.SCHRITTE_TAG2)
    assert zuordnung["begriffe"] == phasen.ERSTE
    assert zuordnung["fragen"] == 2
    assert zuordnung["interviews"] == 3
    assert zuordnung["setting"] == 4
    assert zuordnung["geschichte"] == 4
    assert zuordnung["schaerfung"] == 5
    assert zuordnung["szene1"] == 6


def test_ein_skript_ohne_phasenschritte_ordnet_nichts_zu():
    """Der eigentliche Befund an ``SCHRITTE``: es gibt dort keinen
    ``art='phase'``-Schritt, also bleibt jeder Schritt nach dem ersten
    unzugeordnet -- ausser dem ersten, der per Definition in der ersten Phase
    liegt."""
    zuordnung = abdeckung.phase_je_schritt(skript.SCHRITTE)
    assert set(zuordnung.values()) == {phasen.ERSTE}


def test_titelphasen_findet_den_widerspruch_von_phase_mitte():
    """``Schritt("phase_mitte", "Phase 5", ...)`` bei
    ``skript.PHASE_MITTE == 4`` -- der Titel nennt eine andere Phase als die
    Pruefung."""
    zeilen = {z["schluessel"]: z for z in abdeckung.titelphasen(skript.SCHRITTE)}
    assert zeilen["phase_mitte"]["titel_phase"] == 5
    assert zeilen["phase_mitte"]["stimmt"] is False


def test_phasentabelle_nennt_pruefung_und_pflichtfeld(leer):
    zeilen = {z["nummer"]: z for z in abdeckung.phasentabelle(leer, skript.SCHRITTE_TAG2)}
    assert set(zeilen) == {n for n, _k, _b in phasen.PHASEN}
    assert zeilen[4]["kurzname"] == phasen.kurzname(4)
    assert zeilen[4]["pflichtfeld"] == skript.pflichtfeld_fuer_phase(leer, 4)
    assert zeilen[4]["gefahren"] is True
    # Die Pruefung kommt aus dem Funktionsnamen, nicht aus einer Liste.
    assert "_fertig_setting" in zeilen[4]["pruefungen"]


def test_phasentabelle_meldet_ungefahrene_phasen(leer):
    zeilen = {z["nummer"]: z for z in abdeckung.phasentabelle(leer, skript.SCHRITTE)}
    assert zeilen[phasen.LETZTE]["gefahren"] is False
    assert zeilen[phasen.LETZTE]["schritte"] == []


def test_inventar_zaehlt_die_beiden_arten_listen():
    inv = abdeckung.inventar()
    assert inv["erkenner_arten"] == sorted(erkenner.ARTEN)
    assert len(inv["knopfarten"]) == len([n for n in dir(texte) if n.startswith("ART_")])


def test_praemissenpruefung_kennt_drei_zustaende(tmp_path):
    """gefunden+falsch, gefunden+richtig, bereinigt -- alle drei muessen
    unterscheidbar sein, sonst liest der Bericht eine bereinigte Datei wie
    eine korrekte Behauptung."""
    (tmp_path / "a.md").write_text("Zeile eins\nneun Schritte hier\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("nichts davon\n", encoding="utf-8")
    behauptungen = (
        ("a.md", "neun Schritte", lambda: False),
        ("a.md", "Zeile eins", lambda: True),
        ("b.md", "neun Schritte", lambda: False),
    )
    ergebnis = abdeckung.praemissenpruefung(tmp_path, behauptungen)
    assert [z["status"] for z in ergebnis] == [
        "gefunden_falsch", "gefunden_richtig", "bereinigt",
    ]
    assert ergebnis[0]["zeilen"] == [2]


def test_die_eingebauten_behauptungen_treffen_heute_zu(tmp_path):
    """Kein Wunschzettel: jede Behauptung in ``BEHAUPTUNGEN`` muss auf eine
    Datei zeigen, die es gibt, und ihre Pruefung muss aufrufbar sein."""
    wurzel = Path(abdeckung.__file__).resolve().parent.parent
    for datei, text, pruefung in abdeckung.BEHAUPTUNGEN:
        assert (wurzel / datei).exists(), datei
        assert isinstance(pruefung(), bool)
        assert text


def test_knopfarten_aus_db_trennt_angeboten_von_gedrueckt(leer):
    repo.sichere_gruppe(leer, 1, "gruppe1", "Testgruppe")
    eins = repo.lege_knopf_an(leer, 1, texte.ART_PHASE, "2")
    repo.lege_knopf_an(leer, 1, texte.ART_PHASE, "3")
    repo.beanspruche_knopf(leer, eins)
    zeilen = {z["art"]: z for z in abdeckung.knopfarten_aus_db(leer)}
    assert zeilen[texte.ART_PHASE]["angeboten"] == 2
    assert zeilen[texte.ART_PHASE]["gedrueckt"] == 1


def test_laeufe_aus_db_zaehlt_je_art(leer):
    repo.sichere_gruppe(leer, 1, "gruppe1", "Testgruppe")
    repo.merke_aufruf(leer, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    repo.merke_aufruf(leer, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    repo.merke_aufruf(leer, 1, "schaerfung", "A", 0, 10, 10, "stop", 1, 1)
    assert abdeckung.laeufe_aus_db(leer) == {"schaerfung": 1, "szenenfolge": 2}


def test_als_markdown_traegt_die_drei_tabellen(leer):
    text = abdeckung.als_markdown(leer, Path(abdeckung.__file__).resolve().parent.parent)
    assert "## Phasen je Skript" in text
    assert "## Praemissenpruefung" in text
    assert "## Inventar" in text
    assert phasen.kurzname(4) in text
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_abdeckung.py 2>&1 | tail -5
```

Erwartet: Sammelfehler `ModuleNotFoundError: No module named 'scripts.simulation_abdeckung'`.

- [ ] **Schritt 3: `scripts/simulation_abdeckung.py` schreiben**

Zwei Dinge dabei beachten. Erstens: `repo.lege_knopf_an` und
`repo.beanspruche_knopf` heissen im Test so — sind die Namen im Repo andere,
**den Test an das Repo anpassen, nicht das Repo an den Test**
(`grep -n "def lege_knopf_an\|def beanspruche_knopf" interview_theater/repo.py`).
Zweitens: dieses Skript ist **kein Test und kostet nichts** — es darf im
Docstring ausdruecklich so stehen.

```python
"""Was faehrt die Simulation wirklich? -- der Abdeckungszensus.

**Kein Test, kostet nichts, braucht kein Netz.** Er erzeugt die Tabelle, die
in ``docs/simulation-gegenpruefung-2026-09-30.md`` steht: welche der heutigen
Phasen (``phasen.PHASEN``) ein Skript ansteuert, woran es dort seinen
Zielzustand prueft, und was von den Inventaren (``erkenner.ARTEN``,
``knoepfe.texte.ART_*``) dabei ueberhaupt vorkommen kann.

**Warum erzeugt und nicht abgeschrieben.** Eine Abdeckungstabelle von Hand
ist nach dem naechsten Phasenumbau falsch, ohne dass es jemand merkt -- genau
der Fehler, den dieser Zensus an der Simulation selbst nachweist
(``simulation/README.md`` behauptete am 30.09.2026 neun Schritte, es waren
zehn; und "Phase 5 = Format & Rahmen", die es seit dem 06.09. nicht mehr
gibt).

Aufruf::

    PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
    $PY -m scripts.simulation_abdeckung
    $PY -m scripts.simulation_abdeckung --db /tmp/gegenpruefung-basis-1.db

Mit ``--db`` kommen zwei Abschnitte dazu, die sich nur an einem gefahrenen
Lauf ablesen lassen: welche Knopfarten angeboten und welche gedrueckt wurden
(``knopf.art`` / ``benutzt_am``) und welche Modellwege ueberhaupt gelaufen
sind (``aufruf.art``). Beides read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, erkenner, phasen  # noqa: E402
from interview_theater.knoepfe import texte  # noqa: E402
from simulation import skript  # noqa: E402

#: Die drei Skriptlisten, die es gibt. Aus ``skript`` geholt, nicht kopiert.
SKRIPTE = {
    "schritte": skript.SCHRITTE,
    "tag2": skript.SCHRITTE_TAG2,
    "birk": skript.SCHRITTE_BIRK,
}

#: Eine Phasennummer im Titel eines Schritts ("Phase 4: Setting ...").
_TITEL_PHASE = re.compile(r"\bPhase\s+(\d+)")


def phase_je_schritt(schritte) -> dict[str, int | None]:
    """Welche Phase ein Schritt bespielt -- **abgeleitet, nicht hinterlegt**.

    Die ``art='phase'``-Schritte sind die Marken: was zwischen zwei von ihnen
    liegt, gehoert zur Phase des vorangegangenen. Vor dem ersten gilt
    ``phasen.ERSTE`` -- ein Workshop beginnt dort, auch wenn niemand es sagt.

    Ein Skript ohne Phasenschritte (``skript.SCHRITTE``) bekommt damit
    ueberall dieselbe Nummer, und genau das ist die Aussage: es steuert die
    Phasen nicht an."""
    laufend = phasen.ERSTE
    ergebnis: dict[str, int | None] = {}
    for schritt in schritte:
        if schritt.art == "phase" and schritt.phase_nummer:
            laufend = schritt.phase_nummer
        ergebnis[schritt.schluessel] = laufend
    return ergebnis


def titelphasen(schritte) -> list[dict]:
    """Je Schritt: welche Phasennummer sein **Titel** nennt und welche ihm das
    Skript zuordnet.

    Ein Unterschied ist ein Befund und kein Schoenheitsfehler: der Titel ist
    das, was im Lauf-Protokoll und im Bericht steht, und wer dort "Phase 5"
    liest, glaubt, Phase 5 sei gemessen worden."""
    zuordnung = phase_je_schritt(schritte)
    zeilen = []
    for schritt in schritte:
        treffer = _TITEL_PHASE.search(schritt.titel or "")
        genannt = int(treffer.group(1)) if treffer else None
        zugeordnet = zuordnung[schritt.schluessel]
        zeilen.append({
            "schluessel": schritt.schluessel,
            "titel": schritt.titel,
            "titel_phase": genannt,
            "zugeordnet": zugeordnet,
            "stimmt": genannt is None or genannt == zugeordnet,
        })
    return zeilen


def phasentabelle(conn, schritte) -> list[dict]:
    """Je Phase eine Zeile: Kurzname, Arbeitsstandfelder, Pflichtfeld, die
    Schritte, die dort spielen, und woran sie ihren Zielzustand pruefen.

    Die Pruefung kommt aus ``schritt.fertig.__name__`` -- der Funktionsname
    ist die einzige Beschreibung, die nicht auseinanderlaufen kann."""
    zuordnung = phase_je_schritt(schritte)
    zeilen = []
    for nummer, kurz, _beschreibung in phasen.PHASEN:
        eigene = [s for s in schritte if zuordnung[s.schluessel] == nummer]
        zeilen.append({
            "nummer": nummer,
            "kurzname": kurz,
            "felder": skript.felder_fuer_phase(conn, nummer),
            "pflichtfeld": skript.pflichtfeld_fuer_phase(conn, nummer),
            "schritte": [s.schluessel for s in eigene],
            "pruefungen": [getattr(s.fertig, "__name__", "?") for s in eigene],
            "gefahren": bool(eigene),
        })
    return zeilen


def inventar() -> dict:
    """Die zwei Listen, gegen die sich Abdeckung ueberhaupt messen laesst."""
    return {
        "erkenner_arten": sorted(erkenner.ARTEN),
        "erkenner_in_aufnahme": sorted(erkenner.ARTEN_IN_AUFNAHME),
        "knopfarten": sorted(
            getattr(texte, name) for name in dir(texte) if name.startswith("ART_")
        ),
    }


#: Behauptungen der Doku, je mit der Pruefung, die sie heute bestaetigen oder
#: widerlegen wuerde. Drei Zustaende: die Zeichenfolge steht da und die
#: Behauptung stimmt; sie steht da und stimmt nicht; sie steht nicht mehr da
#: (bereinigt). Der dritte Zustand ist der Grund fuer diese Liste -- nach
#: Aufgabe 7 dieses Plans soll sie leer laufen, und das soll man sehen.
BEHAUPTUNGEN: tuple[tuple[str, str, object], ...] = (
    ("simulation/README.md", "neun Schritte", lambda: len(skript.SCHRITTE) == 9),
    ("simulation/skript.py", "Neun Schritte", lambda: len(skript.SCHRITTE) == 9),
    ("simulation/skript.py", "die neun Schritte",
     lambda: len(skript.SCHRITTE) == 9),
    ("tests/test_simulation_durchlauf.py", "neun Schritte",
     lambda: len(skript.SCHRITTE) == 9),
    ("simulation/README.md", "Format & Rahmen",
     lambda: phasen.kurzname(5) == "Format & Rahmen"),
    ("simulation/README.md", "acht Phasen", lambda: len(phasen.PHASEN) == 8),
    ("simulation/skript.py", "acht Phasen", lambda: len(phasen.PHASEN) == 8),
    ("simulation/skript.py", '"Phase 5"', lambda: skript.PHASE_MITTE == 5),
    ("simulation/skript.py", "PHASE_SZENENTEXTE",
     lambda: phasen.kurzname(skript.PHASE_SZENENTEXTE).startswith("Szenentexte")),
    ("simulation/kennzahlen.py", "Pflichtfeld der Phase 5",
     lambda: skript.PHASE_MITTE == 5),
)


def praemissenpruefung(wurzel, behauptungen=BEHAUPTUNGEN) -> list[dict]:
    """Jede Behauptung gegen den Code -- und gegen die Datei, in der sie
    steht."""
    ergebnis = []
    for datei, text, pruefung in behauptungen:
        pfad = Path(wurzel) / datei
        zeilen: list[int] = []
        if pfad.exists():
            for nummer, zeile in enumerate(
                pfad.read_text(encoding="utf-8").splitlines(), 1
            ):
                if text in zeile:
                    zeilen.append(nummer)
        stimmt = bool(pruefung())
        if not zeilen:
            status = "bereinigt"
        elif stimmt:
            status = "gefunden_richtig"
        else:
            status = "gefunden_falsch"
        ergebnis.append({"datei": datei, "text": text, "zeilen": zeilen,
                         "stimmt": stimmt, "status": status})
    return ergebnis


def knopfarten_aus_db(conn) -> list[dict]:
    """Je Knopfart: wie oft angeboten, wie oft gedrueckt. Read-only."""
    return [
        {"art": z["art"], "angeboten": z["angeboten"], "gedrueckt": z["gedrueckt"]}
        for z in conn.execute(
            "SELECT art, count(*) AS angeboten, "
            "sum(CASE WHEN benutzt_am IS NOT NULL THEN 1 ELSE 0 END) AS gedrueckt "
            "FROM knopf GROUP BY art ORDER BY art"
        )
    ]


def laeufe_aus_db(conn) -> dict[str, int]:
    """Welche Modellwege ueberhaupt gelaufen sind (``aufruf.art``)."""
    return {
        z["art"]: z["n"]
        for z in conn.execute(
            "SELECT art, count(*) AS n FROM aufruf GROUP BY art ORDER BY art"
        )
    }


def _ja(wert: bool) -> str:
    return "ja" if wert else "**nein**"


def als_markdown(conn, wurzel, db_conn=None) -> str:
    zeilen = ["# Abdeckung der Simulation (erzeugt, nicht abgeschrieben)", ""]
    zeilen += [
        f"- Phasen laut `phasen.PHASEN`: {len(phasen.PHASEN)}",
        f"- Schritte: `SCHRITTE` {len(skript.SCHRITTE)}, "
        f"`SCHRITTE_TAG2` {len(skript.SCHRITTE_TAG2)}, "
        f"`SCHRITTE_BIRK` {len(skript.SCHRITTE_BIRK)}",
        f"- `skript.PHASE_MITTE` = {skript.PHASE_MITTE} "
        f"(`{phasen.kurzname(skript.PHASE_MITTE)}`), "
        f"`skript.phase_szenen()` = {skript.phase_szenen()}",
        "",
        "## Phasen je Skript",
        "",
    ]
    for name, schritte in SKRIPTE.items():
        zeilen += [f"### `{name}` ({len(schritte)} Schritte)", "",
                   "| Phase | Kurzname | gefahren | Schritte | Pruefung | Pflichtfeld |",
                   "|---|---|---|---|---|---|"]
        for z in phasentabelle(conn, schritte):
            zeilen.append(
                f"| {z['nummer']} | {z['kurzname']} | {_ja(z['gefahren'])} | "
                f"{', '.join(z['schritte']) or '–'} | "
                f"{', '.join(f'`{p}`' for p in z['pruefungen']) or '–'} | "
                f"{z['pflichtfeld'] or '–'} |"
            )
        falsch = [z for z in titelphasen(schritte) if not z["stimmt"]]
        zeilen += [""]
        if falsch:
            zeilen.append("Titel, die eine andere Phase nennen als die Zuordnung:")
            zeilen += [
                f"- `{z['schluessel']}`: Titel „{z['titel']}“ nennt Phase "
                f"{z['titel_phase']}, zugeordnet ist {z['zugeordnet']}"
                for z in falsch
            ]
        else:
            zeilen.append("Kein Titel widerspricht seiner Phasenzuordnung.")
        zeilen.append("")

    zeilen += ["## Praemissenpruefung", "",
               "| Datei | Behauptung | Zeilen | heute | Status |", "|---|---|---|---|---|"]
    for z in praemissenpruefung(wurzel):
        zeilen.append(
            f"| `{z['datei']}` | {z['text']} | "
            f"{', '.join(str(n) for n in z['zeilen']) or '–'} | "
            f"{'stimmt' if z['stimmt'] else 'stimmt nicht'} | {z['status']} |"
        )

    inv = inventar()
    zeilen += ["", "## Inventar", "",
               f"- `erkenner.ARTEN`: {len(inv['erkenner_arten'])} "
               f"({', '.join(inv['erkenner_arten'])})",
               f"- davon aus einer Aufnahme erlaubt: "
               f"{', '.join(inv['erkenner_in_aufnahme'])}",
               f"- `knoepfe.texte.ART_*`: {len(inv['knopfarten'])}", ""]

    if db_conn is not None:
        zeilen += ["## Knopfarten im gefahrenen Lauf", "",
                   "| Knopfart | angeboten | gedrueckt |", "|---|---|---|"]
        for z in knopfarten_aus_db(db_conn):
            zeilen.append(f"| {z['art']} | {z['angeboten']} | {z['gedrueckt']} |")
        zeilen += ["", "## Modellwege im gefahrenen Lauf", "",
                   "| `aufruf.art` | Anzahl |", "|---|---|"]
        for art, n in laeufe_aus_db(db_conn).items():
            zeilen.append(f"| {art} | {n} |")
        zeilen.append("")
    return "\n".join(zeilen) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.simulation_abdeckung",
        description="Die Abdeckungstabelle der Simulation aus dem Code erzeugen. "
                    "Kein Netz, kein Modell, keine Kosten.",
    )
    p.add_argument("--db", help="Lauf-Datenbank, read-only, fuer Knopf- und "
                               "Aufruf-Abdeckung")
    args = p.parse_args(argv)
    wurzel = Path(__file__).resolve().parent.parent
    ordner = tempfile.mkdtemp(prefix="abdeckung-")
    leer = db.verbinde(str(Path(ordner) / "schema.db"))
    db.initialisiere(leer)
    lauf_conn = None
    if args.db:
        import sqlite3
        lauf_conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        lauf_conn.row_factory = sqlite3.Row
    print(als_markdown(leer, wurzel, lauf_conn), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Schritt 4: Test gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_abdeckung.py 2>&1 | tail -3
```

Erwartet: `13 passed`. Schlaegt `test_phase_je_schritt_folgt_den_phasenschritten`
fehl, weil `phasen.ERSTE` nicht existiert: `grep -n "^ERSTE\|def ERSTE\|ERSTE =" interview_theater/phasen.py`
und den vorhandenen Namen verwenden (AGENTS.md nennt `phasen.ERSTE` und
`phasen.LETZTE` ueber `__getattr__`).

- [ ] **Schritt 5: Zensus einmal fahren und die Ausgabe sichern**

```bash
$PY -m scripts.simulation_abdeckung > /tmp/abdeckung-vorher.md
head -40 /tmp/abdeckung-vorher.md
```

Erwartet: die Tabelle `schritte` zeigt in **allen** Phasen ausser der ersten
`gefahren: **nein**`; `tag2` zeigt in allen sieben `ja`; die
Praemissenpruefung listet mehrere Zeilen mit `gefunden_falsch`. Diese Datei
liegt in `/tmp`, **nicht im Repo** — sie wird in Aufgabe 8 in den Bericht
uebertragen.

- [ ] **Schritt 6: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add scripts/simulation_abdeckung.py tests/test_simulation_abdeckung.py
git commit -m "$(cat <<'EOF'
Abdeckungszensus der Simulation: die Tabelle wird erzeugt, nicht abgeschrieben

Phasen aus phasen.PHASEN, Schritte aus den drei skript-Listen, Pruefung aus
schritt.fertig.__name__. Dazu die Praemissenpruefung: jede Behauptung der
Doku ("neun Schritte", "Phase 5 = Format & Rahmen", "acht Phasen") gegen den
Code, mit Datei und Zeile. Kein Test, kostet nichts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

Erwartet: `2781 passed, 1 skipped` (2768 + 13).

---

## Aufgabe 2: `simulation/mutation.py` + Nachweis fuer Fehler 1 (kostenlos)

**Der Fehler.** `docs/analyse-phase4-datenverlust-2026-09-06.md` § 0: 42
Festlegungen in Phase 4, **22 verloren** — „kein Feld, oder nur ein
`journal`-Eintrag der Art `vorgeschlagen`, der nachweislich nicht mehr in den
Prompt kommt" (§ 2.7: `kontext.JOURNAL_EINTRAEGE = 8`, Phase 4 erzeugte 38
Journalzeilen).

**Der Fix im heutigen Code**, per `git log` belegt:

| Commit | Datum | Was |
|---|---|---|
| `e56a892` | 07.09.2026 | „Auffangtabelle festlegung: Schema und Schreibwege" — `db.py`, `repo.py` (`FESTLEGUNG_BEREICHE`, `schreibe_festlegung`, `festlegungen`, `entferne_festlegung`, `festlegungszeile`) |
| `bbe301e` | 07.09.2026 | „Erkenner-Art festlegung_setzen: der Regelweg in die Auffangtabelle" — `erkenner.ARTEN`, `_wende_festlegung_an` (erkenner.py:817) |
| `36030ff` | 07.09.2026 | „Regie-Befehl /festlegung als Rueckfallebene" — `befehle._befehl_festlegung` |
| `3290d70` | 07.09.2026 | „B1/B2: eine Menuezeile ist keine Geschichte" — die zweite Ursache, siehe unten |

Der Kontextblock haengt an `kontext._baue_festlegungen` (kontext.py:593),
`BUDGETS["festlegungen"] = 800`, `FESTLEGUNGEN_ZEILEN = 20`, gekappt **von
hinten**.

**Welche der drei Ursachen mutiert wird — und warum.** Die Analyse nennt drei
(§ 3, § 4.5): (a) es gibt kein Fach fuer nicht kategorisierbare
Festlegungen, (b) eine Menuezeile landet als ganze Geschichte in
`arbeitsstand.geschichte`, (c) nachbenannte Figuren legen eine zweite Zeile
an statt den Platzhalter zu schlucken. Mutiert wird **(a)**:

- (a) ist die **Hauptursache der Zahl 22 von 42** — § 3 fuehrt sieben von acht
  Verlustarten auf „kein Feld, nur ein toter Journaleintrag" zurueck.
  (b) betrifft **eine** Festlegung (#44), (c) ist ein Datenschaden neben der
  Frage nach dem Verlust.
- (a) hat **genau einen** Engpass im Code (`repo.schreibe_festlegung`), also
  eine Mutation von einer Zeile — keine Naeherung an einen Revert, sondern
  derselbe beobachtbare Zustand wie vor `e56a892`: kein `festlegung`-Eintrag,
  kein Prompt-Block, und der Aufrufer bekommt `None`.
- (b) ist bereits als **Fehler 2** abgedeckt: der Neuaufbau der Szenenfolge
  ist die Wirkung derselben Wurzel („eine Menuezeile ist keine Geschichte"),
  und die dortige Mutation trifft sie genauer.
- (c) misst die Simulation heute schon indirekt (`arbeitsstand_vollstaendig`
  zaehlt Figuren inklusive weich geloeschter) und ist ohne Modell nicht
  zuverlaessig auszuloesen: ob eine simulierte Stimme eine Platzhalterfigur
  nachbenennt, entscheidet das Gespraechsmodell. Ein Mutationslauf, dessen
  Ausloeser unsicher ist, misst nichts. **Das gehoert in eine eigene Karte**
  und steht so im Bericht.

**Dateien:**
- Create: `simulation/mutation.py`
- Test: `tests/test_simulation_mutation.py`

**Interfaces:**
- Produces:
  - `mutation.ARTEN: tuple[str, ...]` — `("festlegung_verloren", "richtung_ohne_szenen")`
  - `mutation.aktiv(art: str | None)` — Kontextmanager, liefert `art` oder `None`
  - `mutation.BESCHREIBUNG: dict[str, str]` — ein Satz je Mutation, fuer Bericht und `--help`

- [ ] **Schritt 1: Den Test schreiben (Mutation 1)**

`tests/test_simulation_mutation.py`:

```python
"""Die zwei Dortmunder Fehler wieder einbauen -- und nachweisen, dass sie
wirklich wieder da sind.

**Warum dieser Test der teuerste Teil der Karte ist.** Ein Mutationslauf
gegen das echte Modell kostet Geld. Greift die Mutation nicht, misst der Lauf
nichts und das Geld ist weg. Diese Tests laufen **vor** jedem bezahlten Lauf
und ohne Netz: sie pruefen den beobachtbaren Zustand vor dem Fix, so wie ihn
die beiden Analysen belegen -- nicht die Abwesenheit einer Funktion.
"""

import pytest

from interview_theater import knoepfe, kontext, phasen, repo, szenenfolge, vorschlagssperre
from simulation import mutation

from test_szenenfolge import TelegramAttrappe


@pytest.fixture(autouse=True)
def freie_vorschlagssperre():
    """Die mutierte Richtungswahl startet ``starte_geschichte_szenen``
    wirklich (chat_id=1) -- kein Zustand aus einem frueheren Test soll die
    gemeinsame Vorschlagssperre besetzt lassen."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


PROBE = "Das Stueck ist nur EINE Szene, die erste Folge einer Serie."


def test_alle_arten_haben_eine_beschreibung():
    assert set(mutation.BESCHREIBUNG) == set(mutation.ARTEN)
    assert all(mutation.BESCHREIBUNG[a].strip() for a in mutation.ARTEN)


def test_ohne_art_wird_nichts_angefasst():
    vorher = repo.schreibe_festlegung
    with mutation.aktiv(None) as aktiv:
        assert aktiv is None
        assert repo.schreibe_festlegung is vorher


def test_eine_unbekannte_mutation_bricht_ab():
    with pytest.raises(SystemExit):
        with mutation.aktiv("gibtsnicht"):
            pass


# --- Mutation 1: die Auffangtabelle gab es nicht --------------------------


def test_heute_landet_eine_festlegung_in_der_tabelle_und_im_prompt(conn):
    neu = repo.schreibe_festlegung(conn, 1, "struktur", PROBE)
    assert neu is not None
    assert [z["text"] for z in repo.festlegungen(conn, 1)] == [PROBE]
    assert "nur EINE Szene" in kontext._baue_festlegungen(conn, 1)


def test_mutiert_landet_sie_nirgends(conn):
    """Der Zustand vor ``e56a892``: kein Eintrag, kein Prompt-Block, und der
    Aufrufer bekommt dasselbe ``None`` wie bei einer Dublette -- also keine
    Notiert-Zeile."""
    with mutation.aktiv("festlegung_verloren"):
        assert repo.schreibe_festlegung(conn, 1, "struktur", PROBE) is None
        assert repo.festlegungen(conn, 1) == []
        assert kontext._baue_festlegungen(conn, 1) == ""


def test_mutiert_schreibt_auch_der_erkenner_nichts(conn, einst):
    """Ueber den Produktivpfad, nicht ueber ``repo`` direkt: der Erkenner
    ruft ``repo.schreibe_festlegung`` als Modulattribut, also greift der
    Monkey-Patch."""
    from interview_theater import erkenner

    aenderung = [{"art": "festlegung_setzen", "wert": f"struktur: {PROBE}"}]
    with mutation.aktiv("festlegung_verloren"):
        wirkliche = erkenner.wende_an(conn, einst, 1, list(aenderung))
    assert wirkliche == []
    assert repo.festlegungen(conn, 1) == []

    wirkliche = erkenner.wende_an(conn, einst, 1, list(aenderung))
    assert [a["art"] for a in wirkliche] == ["festlegung_setzen"]
    assert len(repo.festlegungen(conn, 1)) == 1


def test_nach_dem_block_ist_der_originalzustand_wieder_da(conn):
    with mutation.aktiv("festlegung_verloren"):
        pass
    assert repo.schreibe_festlegung(conn, 1, "struktur", PROBE) is not None


def test_verschachtelte_mutationen_stellen_erst_am_ende_zurueck(conn):
    mutiert = None
    with mutation.aktiv("festlegung_verloren"):
        mutiert = repo.schreibe_festlegung
        with mutation.aktiv("festlegung_verloren"):
            assert repo.schreibe_festlegung is mutiert
        assert repo.schreibe_festlegung is mutiert
    assert repo.schreibe_festlegung is not mutiert
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_mutation.py 2>&1 | tail -5
```

Erwartet: `ModuleNotFoundError: No module named 'simulation.mutation'`.

- [ ] **Schritt 3: `simulation/mutation.py` schreiben**

```python
"""Die zwei belegten Dortmunder Fehler auf Knopfdruck wieder einbauen.

**Ein Nachweiswerkzeug, kein Schalter des Betriebs.** Der Zweck ist eine
einzige Frage: findet die Simulation einen Fehler, von dem wir wissen, dass
er ein echter war? Ohne diesen Weg bewertet sich die Simulation selbst -- sie
laeuft durch, meldet Zahlen, und niemand weiss, ob die Zahlen sich bewegen
wuerden, wenn etwas kaputt waere.

**Warum Monkey-Patching und kein Revert im Code.** Drei Gruende, und der
dritte ist der wichtigste:

1. Es ist die Bauart dieses Verzeichnisses. ``lauf.einfaedig()`` ersetzt
   ``szene.starte`` und drei Geschwister, ``lauf.kontext_protokoll()``
   ersetzt ``kontext.baue``, ``stoerung.StoerungsLLM`` haengt sich vor den
   Modellklienten und wirft Fehler, die es nicht gibt. Alles drei ist
   voruebergehende Ersetzung von Betriebsverhalten aus ``simulation/``
   heraus.
2. Der Produktivcode bleibt unangetastet: ``git diff -- interview_theater/``
   ist nach einem Mutationslauf leer, und es gibt keine Weiche, die jemand
   spaeter im Betrieb umlegen koennte. Eine Umgebungsvariable, die
   ``repo.py`` liest, waere genau das.
3. Ein ``.patch`` in einem Wegwerf-Arbeitsbaum haette den Nachweis vom
   Nachweisort getrennt: die Pruefung, dass die Mutation greift, muesste
   dort laufen, die Suite hier -- und ein headless-Arbeiter haette zwei
   Baeume, ein ``git apply -R`` und eine offene Frage, in welchem von beiden
   er gerade steht.

**Die Grenze, und wie sie abgesichert ist.** Ein Monkey-Patch trifft nur die
Stelle, die er ersetzt. Deshalb liegt der Patch je Fehler an dem **einen
Engpass**, den der Fix eingefuehrt hat, und
``tests/test_simulation_mutation.py`` prueft den **beobachtbaren Zustand vor
dem Fix** ueber den Produktivpfad (``erkenner.wende_an``, ``knoepfe._wirke``)
-- nicht, dass eine Funktion fehlt.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import threading

log = logging.getLogger(__name__)

#: Die Mutationen, die es gibt. Der Wert ist der ``--mutation``-Schalter von
#: ``scripts/simulation.py``.
ARTEN = ("festlegung_verloren", "richtung_ohne_szenen")

BESCHREIBUNG = {
    "festlegung_verloren":
        "Der Zustand vor e56a892: es gibt kein Fach fuer eine Festlegung, die "
        "in kein Arbeitsstandfeld passt. 22 von 42 Festlegungen der Gruppe 1 "
        "gingen am 06.09.2026 so verloren "
        "(docs/analyse-phase4-datenverlust-2026-09-06.md § 0, § 2.7, § 3).",
    "richtung_ohne_szenen":
        "Der Zustand vor 3ae76ab/c9af872: eine gewaehlte Geschichte-Richtung, "
        "die ihre Szenen im Satz nennt, verliert sie -- danach laeuft ein "
        "frischer Szenenfolge-Vorschlag und schreibt Titel und Form neu. Aus "
        "3 Szenen wurden am 06.09.2026 sechs "
        "(docs/analyse-phase5-chaos-2026-09-06.md § 4).",
}


def _ohne_festlegung(conn, chat_id, bereich, text, bezug=None, quelle="erkenner"):
    """Ersatz fuer ``repo.schreibe_festlegung``.

    Vor ``e56a892`` gab es die Tabelle nicht. Der Rueckgabewert ``None`` ist
    dabei kein Behelf, sondern genau richtig: die heutige Funktion liefert
    ``None``, wenn nichts geschrieben wurde, und ``erkenner._wende_festlegung_an``
    macht daraus "keine Aenderung" -- also auch keine Notiert-Zeile. Genau so
    verhielt sich der Bot damals."""
    log.info("Mutation festlegung_verloren: verwirft [%s] %s", bereich, text)
    return None


def _keine_szenen_in_der_richtung(zeile):
    """Ersatz fuer ``szenenfolge.szenen_der_richtung``.

    Vor ``3ae76ab`` gab es die Funktion nicht: ``_speichere_geschichte`` sah
    in einer Richtungszeile nie Szenen (``zerlege_geschichte`` liest sie erst
    ab Zeile 3, und ein Richtungs-Knopf traegt immer genau eine Zeile). Die
    ganze Zeile landete in ``arbeitsstand.geschichte``, und danach lief
    ``starte_geschichte_szenen``."""
    return []


#: Je Mutation: welches Modulattribut durch welche Funktion ersetzt wird.
_EINBAU = {
    "festlegung_verloren": (
        "interview_theater.repo", "schreibe_festlegung", _ohne_festlegung,
    ),
    "richtung_ohne_szenen": (
        "interview_theater.szenenfolge", "szenen_der_richtung",
        _keine_szenen_in_der_richtung,
    ),
}

#: Wie in ``lauf.py``: je Umbau ein Zaehler unter einer Sperre. Zwei
#: verschachtelte Blocks derselben Art bauen einmal um und stellen einmal
#: zurueck -- sonst sicherte der innere die schon ersetzte Funktion als
#: "Original" und der Betriebscode blieb mutiert.
_SPERRE = threading.Lock()
_TIEFE: dict[str, int] = {}
_ORIGINAL: dict[str, object] = {}


@contextlib.contextmanager
def aktiv(art: str | None):
    """Baut die Mutation ``art`` ein und danach wieder aus.

    ``None`` heisst "keine Mutation" und fasst nichts an -- damit kann der
    Aufrufer den Kontextmanager bedingungslos betreten und muss nicht zwei
    Codepfade fuehren."""
    if not art:
        yield None
        return
    if art not in _EINBAU:
        raise SystemExit(
            f"unbekannte Mutation: {art!r} (bekannt: {', '.join(ARTEN)})"
        )
    modulname, name, ersatz = _EINBAU[art]
    modul = importlib.import_module(modulname)
    with _SPERRE:
        _TIEFE[art] = _TIEFE.get(art, 0) + 1
        if _TIEFE[art] == 1:
            _ORIGINAL[art] = getattr(modul, name)
            setattr(modul, name, ersatz)
            log.warning("Mutation %s EINGEBAUT (%s.%s)", art, modulname, name)
    try:
        yield art
    finally:
        with _SPERRE:
            _TIEFE[art] -= 1
            if _TIEFE[art] == 0:
                setattr(modul, name, _ORIGINAL.pop(art))
                log.warning("Mutation %s zurueckgenommen", art)
```

- [ ] **Schritt 4: Test gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_mutation.py 2>&1 | tail -3
```

Erwartet: `8 passed`. Scheitert `test_mutiert_schreibt_auch_der_erkenner_nichts`
an der Signatur, mit `grep -n "^def wende_an" -A 2 interview_theater/erkenner.py`
nachsehen — geplant ist `wende_an(conn, e, chat_id, aenderungen)`.

- [ ] **Schritt 5: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add simulation/mutation.py tests/test_simulation_mutation.py
git commit -m "$(cat <<'EOF'
Mutation 1: die Auffangtabelle festlegung wieder wegnehmen

simulation/mutation.py ersetzt zur Laufzeit repo.schreibe_festlegung durch
den Zustand vor e56a892 -- kein Eintrag, kein Prompt-Block, None zurueck,
also keine Notiert-Zeile. Kein Produktivcode angefasst, keine
Mutationsweiche: dieselbe Bauart wie lauf.einfaedig und stoerung.py.

Der Nachweis laeuft ueber den Produktivpfad (erkenner.wende_an), nicht ueber
die Abwesenheit einer Funktion -- er muss vor jedem bezahlten Lauf gruen
sein, sonst misst der Lauf nichts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

Erwartet: `2789 passed, 1 skipped` (2781 + 8).

---

## Aufgabe 3: Nachweis fuer Fehler 2 — 3 Szenen werden 6 (kostenlos)

**Der Fehler.** `docs/analyse-phase5-chaos-2026-09-06.md` § 4: im Feld
`geschichte` und in `journal` 52 standen **drei** Szenen mit festgelegter Form;
13:54:37 lief ein Neuaufbau (ids 1–3 weich entfernt, 4–9 neu, sechs Szenen),
14:09:35 ein zweiter (ids 4–9 raus, 10–15 neu). Ausgeloest nicht von einer
Kuerzungsbitte, sondern vom Regelweg der Richtungswahl:
`_speichere_geschichte` rief am Ende **immer**
`szenenfolge.starte_geschichte_szenen`.

**Der Fix im heutigen Code**, per `git log` belegt:

| Commit | Datum | Was |
|---|---|---|
| `3ae76ab` | 30.09.2026 | „Richtungswahl: Szenen aus der gewaehlten Zeile mitspeichern" — `szenenfolge.szenen_in_zeile`, `lege_inline_an`, `nummern_unvollstaendig`, `JOURNAL_INLINE`; `knoepfe/szenen.py:1084-1146` |
| `c9af872` | 30.09.2026 | „Richtungswahl: Formwahl bleibt vorn, bestaetigte Form bleibt stehen" — `szenenfolge.szenen_der_richtung` als Wache vor dem Inline-Weg |

Nebenbefund, der in den Bericht gehoert: `szenenfolge.lege_an` ist seit dem
06.09.2026 **abgleichend** (`repo.gleiche_szenenfolge_ab`, repo.py:2298) —
ein Szenenfolge-Lauf **entfernt** heute keine Szene mehr. Der Schaden hat
damit eine andere Gestalt als am 06.09.: nicht „drei weg, sechs neu", sondern
„Titel 1–3 ueberschrieben, 4–6 dazu". `titel` steht nicht in
`repo.GESCHUETZTE_SZENENFELDER`. Deshalb messen die Kennzahlen in Aufgabe 5
**beide** Gestalten: Ersetzungen (`entfernt_am`) *und* Szenenfolge-Laeufe nach
der Richtungswahl.

**Mutation:** `szenenfolge.szenen_der_richtung` → `[]`. Genau die Wache, die
`c9af872` eingefuehrt hat; ohne sie faellt `_speichere_geschichte` auf den
Weg von vor `3ae76ab` zurueck — `formabfolge` greift bei einer echten
Richtungszeile nicht, also landet die ganze Zeile in
`arbeitsstand.geschichte`, es entstehen **keine** Szenen aus der Zeile, und am
Ende laeuft `starte_geschichte_szenen`.

**Dateien:**
- Modify: `tests/test_simulation_mutation.py` (anhaengen)

- [ ] **Schritt 1: Die Tests fuer Mutation 2 anhaengen**

An das Ende von `tests/test_simulation_mutation.py`:

```python
# --- Mutation 2: die Richtungswahl verliert ihre Szenen --------------------
#
# Die Zeile ist wortgleich die aus tests/test_geschichte.py (RICHTUNG_MIT_SZENEN)
# -- hier absichtlich wiederholt und nicht importiert: dieser Test soll noch
# gelten, wenn dort jemand die Beispielzeile aendert.

RICHTUNG = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht, am Ende bleiben beide. "
    "Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. "
    "Szene 3: Der Morgen danach."
)


class LLMAttrappe:
    """Zaehlt, ob ein Szenenfolge-Lauf angestossen wurde, und was er sah."""

    def __init__(self, antwort=""):
        self.antwort = antwort
        self.aufrufe = 0
        self.arten: list[str] = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.arten.append(art)
        return self.antwort


@pytest.fixture
def erfunden(conn):
    """Der Stand nach Phase 4: Begriffe, Setting, zwei Figuren, Phase 4."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof, Winter")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Pal", "haelt an seiner Route fest")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T23:00:00")
    phasen.setze(conn, 1, 4, "test")
    return conn


def _druecke_richtung(conn, tg, einst, klm, zeile=RICHTUNG):
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{zeile}"},
        1,
    )


def test_heute_traegt_die_richtung_ihre_szenen_und_startet_keinen_lauf(
        erfunden, einst):
    conn = erfunden
    tg = TelegramAttrappe()
    klm = LLMAttrappe()
    _druecke_richtung(conn, tg, einst, klm)

    titel = [(s["nummer"], s["titel"]) for s in repo.hole_szenen(conn, 1)]
    assert titel == [
        (1, "Ankunft am Steg"), (2, "Das Gestaendnis"), (3, "Der Morgen danach"),
    ]
    assert klm.aufrufe == 0, "kein zweiter, teurer Folge-Lauf"


def test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf(
        erfunden, einst):
    """Der Zustand vor 3ae76ab: keine Szene aus der Zeile, die ganze Zeile im
    Arbeitsstand, und danach ein frischer Szenenfolge-Vorschlag."""
    conn = erfunden
    tg = TelegramAttrappe()
    klm = LLMAttrappe(
        "VORSCHLAG SZENENFOLGE:\n"
        "Am Steg — sie treffen sich — Mira — Dialog\n"
        "Im Flur — sie streiten — Mira, Pal — Dialog\n"
        "Am Morgen — alle gehen — Mira, Pal — Chor\n"
        "Der Kanal — Pal allein — Pal — Monolog\n"
        "Die Bank — Mira wartet — Mira — Monolog\n"
        "Das Ende — beide bleiben — Mira, Pal — Dialog"
    )
    with mutation.aktiv("richtung_ohne_szenen"):
        _druecke_richtung(conn, tg, einst, klm)
        # Der Lauf haengt in einem Thread; auf die Vorschlagssperre warten ist
        # derselbe Weg wie in tests/test_geschichte.py.
        szenenfolge._sperre_fuer(1).acquire(timeout=10)
        szenenfolge._sperre_fuer(1).release()

    assert repo.hole_szenen(conn, 1) == []
    assert "Szene 1" in repo.hole_arbeitsstand(conn, 1)["geschichte"]
    assert klm.aufrufe == 1
    assert klm.arten == [szenenfolge.ART]


def test_mutiert_bleibt_die_reine_formwahl_die_formwahl(erfunden, einst):
    """Die Praezedenz von 3290d70 darf die Mutation nicht mitreissen: eine
    Zeile, die NUR Formen ueber Szenen verteilt, ging schon vor 3ae76ab in
    ``_uebernimm_formwahl``. Eine Mutation, die auch das kaputt macht, wuerde
    zwei Fehler auf einmal messen."""
    conn = erfunden
    tg = TelegramAttrappe()
    with mutation.aktiv("richtung_ohne_szenen"):
        _druecke_richtung(
            conn, tg, einst, LLMAttrappe(),
            "Szene 1: Chor mit Dance. Szene 2: Dialog mit Einschueben. "
            "Szene 3: Rap eskaliert.",
        )
    arten = [z["art"] for z in conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 ORDER BY id"
    )]
    assert "geschichte_war_formwahl" in arten


def test_nach_dem_block_traegt_die_richtung_wieder_ihre_szenen(erfunden, einst):
    conn = erfunden
    with mutation.aktiv("richtung_ohne_szenen"):
        pass
    _druecke_richtung(conn, TelegramAttrappe(), einst, LLMAttrappe())
    assert len(repo.hole_szenen(conn, 1)) == 3
```

- [ ] **Schritt 2: Laufen lassen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_mutation.py 2>&1 | tail -6
```

Erwartet: `12 passed` (8 aus Aufgabe 2 + 4). Es ist **kein neuer
Produktivcode** faellig — die Mutation existiert schon aus Aufgabe 2. Faellt
`test_mutiert_...startet_den_lauf` mit einem Timeout auf der Sperre, pruefe
`grep -n "_sperre_fuer" interview_theater/szenenfolge.py` (der Name delegiert
laut AGENTS.md an `vorschlagssperre`) und ob `freie_vorschlagssperre` greift.

Faellt `test_heute_traegt_die_richtung_ihre_szenen...` mit leerer Szenenliste,
ist etwas an `repo.setze_figur`/`phasen.setze` anders als geplant — mit
`tests/test_geschichte.py::test_richtungswahl_speichert_die_szenen_der_zeile_mit`
vergleichen, der genau diesen Fall heute gruen faehrt, und die dortige
Fixture uebernehmen.

- [ ] **Schritt 3: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add tests/test_simulation_mutation.py
git commit -m "$(cat <<'EOF'
Mutation 2: die Richtungswahl verliert wieder ihre Szenen

szenen_der_richtung -> [] ist der Zustand vor 3ae76ab/c9af872: keine Szene
aus der gewaehlten Zeile, die ganze Zeile im Arbeitsstand, danach ein
frischer Szenenfolge-Lauf. Nachgewiesen ueber knoepfe._wirke, nicht ueber
die Abwesenheit der Funktion -- und mit einem Test, dass die reine Formwahl
(Praezedenz 3290d70) davon unberuehrt bleibt.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

Erwartet: `2793 passed, 1 skipped` (2789 + 4).

---

## Aufgabe 4: Kennzahl `festlegungslage` (kostenlos)

Heute findet **keine** Kennzahl den Fehler 1. `simulation/kennzahlen.py`
enthaelt das Wort `festlegung` nur in `nachrichten_je_festlegung` — und das
zaehlt Nachrichten zwischen Notiert-Zeilen, nicht, ob etwas dauerhaft
gespeichert wurde.

**Die Idee.** Die Dortmunder Analyse klassifiziert jede Festlegung als **OK /
VERKUERZT / VERLOREN**, und ihr Kriterium ist mechanisch: liegt die Angabe in
einem Feld, das ein Prompt noch sieht, oder nur in einem `journal`-Eintrag,
der nach acht Zeilen faellt, oder nirgends? Genau das misst die neue
Kennzahl — an **Pruefsaetzen**, die das Skript die Stimmen sagen laesst
(Aufgabe 7), und die den drei schwersten Dortmunder Verlusten entsprechen
(§ 0: Handlungsstruktur, Gruppenzuordnung, Struktur-/Laengenvorgabe).

**Das Journal zaehlt dabei ausdruecklich NICHT als dauerhaft** — das ist der
ganze Befund aus § 2.7.

**Dateien:**
- Modify: `simulation/skript.py` (nur `FESTLEGUNGSPROBEN`, der Schritt kommt in Aufgabe 7)
- Modify: `simulation/kennzahlen.py`
- Test: `tests/test_simulation_kennzahlen.py` (anhaengen)

**Interfaces:**
- Produces:
  - `skript.FESTLEGUNGSPROBEN: tuple[tuple[str, str, str], ...]` — je Probe `(bereich, stichwort, satz)`
  - `kennzahlen._dauerhafter_text(conn, chat_id) -> str` — gefaltet, alles, was ein Prompt noch sieht
  - `kennzahlen.festlegungslage(conn, chat_id, proben=None) -> dict` mit den Schluesseln
    `festlegungen`, `festlegungen_je_bereich`, `festlegungsproben`,
    `festlegungsproben_erhalten`, `festlegungsproben_nur_journal`,
    `festlegungsproben_nirgends`
- Consumes: `repo.festlegungen`, `repo.festlegungszeile`, `repo.journal`,
  `repo.figuren`, `repo.hole_szenen`, `repo.hole_arbeitsstand`,
  `skript.arbeitsstand_spalten`, `skript._KEINE_FELDER`

- [ ] **Schritt 1: Die Tests schreiben**

An das Ende von `tests/test_simulation_kennzahlen.py`:

```python
# --- Festlegungen: was ueberlebt, was nur im Journal steht, was fehlt -----
#
# Die Kennzahl zu docs/analyse-phase4-datenverlust-2026-09-06.md: 22 von 42
# Festlegungen waren verloren, und das Kriterium der Analyse ist mechanisch --
# liegt die Angabe in einem Feld, das ein Prompt noch sieht, oder nur in einem
# journal-Eintrag, der nach acht Zeilen faellt?

from simulation import mutation, skript as skript_modul  # noqa: E402

PROBEN = (
    ("struktur", "nur eine Szene", "Das Stueck ist nur eine Szene, erste Folge."),
    ("gruppe", "Outsider", "Es gibt zwei Gruppen: die Coolen und die Outsider."),
)


def test_die_proben_des_skripts_sind_vollstaendig_und_eindeutig():
    """Jede Probe traegt Bereich, Stichwort und Satz; der Bereich muss ein
    ``repo.FESTLEGUNG_BEREICHE`` sein, sonst faellt sie beim Schreiben auf
    'sonstiges' und die Zuordnung im Bericht ist falsch. Und das Stichwort
    muss im Satz stehen -- sonst sucht die Kennzahl etwas, das die Stimme nie
    gesagt bekommt."""
    proben = skript_modul.FESTLEGUNGSPROBEN
    assert len(proben) >= 3
    stichworte = [s for _b, s, _t in proben]
    assert len(set(stichworte)) == len(stichworte)
    for bereich, stichwort, satz in proben:
        assert bereich in repo.FESTLEGUNG_BEREICHE
        assert stichwort.lower() in satz.lower()


def test_eine_festlegung_in_der_tabelle_gilt_als_erhalten(conn):
    for bereich, _stichwort, satz in PROBEN:
        repo.schreibe_festlegung(conn, 1, bereich, satz)
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungen"] == 2
    assert lage["festlegungen_je_bereich"] == {"gruppe": 1, "struktur": 1}
    assert lage["festlegungsproben_erhalten"] == 2
    assert lage["festlegungsproben_nur_journal"] == []
    assert lage["festlegungsproben_nirgends"] == []


def test_ein_arbeitsstandfeld_gilt_genauso(conn):
    """Die Kennzahl bestraft keine Angabe, die ordentlich in einem Feld
    gelandet ist -- gefragt ist, ob sie dauerhaft steht, nicht, ob sie in der
    Auffangtabelle steht."""
    repo.setze_arbeitsstand(conn, 1, "geschichte",
                            "Das Stueck ist nur eine Szene, erste Folge.")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 1
    assert lage["festlegungsproben_nirgends"] == ["Outsider"]


def test_eine_figurenbeschreibung_gilt_genauso(conn):
    repo.setze_figur(conn, 1, "Sara", "gehoert zu den Outsider, redet zurueck")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 1
    assert "nur eine Szene" in lage["festlegungsproben_nirgends"]


def test_nur_im_journal_ist_nicht_erhalten(conn):
    """Der Kern des Befunds: ``kontext.JOURNAL_EINTRAEGE = 8`` kappt das
    Journal, ein ``vorgeschlagen``-Eintrag kommt nie zurueck. Die Kennzahl
    zaehlt ihn deshalb getrennt und nicht als Erfolg."""
    for _bereich, _stichwort, satz in PROBEN:
        repo.schreibe_journal(conn, 1, "vorgeschlagen", satz, quelle="erkenner")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 0
    assert sorted(lage["festlegungsproben_nur_journal"]) == ["Outsider",
                                                            "nur eine Szene"]
    assert lage["festlegungsproben_nirgends"] == []


def test_ohne_alles_fehlt_jede_probe(conn):
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 0
    assert len(lage["festlegungsproben_nirgends"]) == 2


def test_die_kennzahl_schlaegt_unter_der_mutation_an_und_sonst_nicht(conn):
    """Beide Richtungen in einem Test, weil nur der Unterschied etwas sagt:
    derselbe Schreibweg, einmal mit und einmal ohne Mutation."""
    def schreibe():
        for bereich, _stichwort, satz in PROBEN:
            geschrieben = repo.schreibe_festlegung(conn, 1, bereich, satz)
            if geschrieben is None:
                # So verhielt sich der Bot vor e56a892: der Inhalt blieb
                # hoechstens als Journalzeile zurueck.
                repo.schreibe_journal(conn, 1, "vorgeschlagen", satz,
                                      quelle="erkenner")

    with mutation.aktiv("festlegung_verloren"):
        schreibe()
    mutiert = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert mutiert["festlegungen"] == 0
    assert mutiert["festlegungsproben_erhalten"] == 0

    schreibe()
    heute = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert heute["festlegungen"] == 2
    assert heute["festlegungsproben_erhalten"] == 2


def test_festlegungslage_steckt_in_sammle(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {}, _E(), PREISE_CHF_JE_MIO_TOKEN, 1.0,
    )
    for schluessel in ("festlegungen", "festlegungen_je_bereich",
                       "festlegungsproben", "festlegungsproben_erhalten",
                       "festlegungsproben_nur_journal",
                       "festlegungsproben_nirgends"):
        assert schluessel in zahlen
    # Ohne Argument nimmt sie die Proben des Skripts, nicht die des Tests.
    assert zahlen["festlegungsproben"] == len(skript_modul.FESTLEGUNGSPROBEN)
```

- [ ] **Schritt 2: Laufen lassen, Fehlschlag bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_kennzahlen.py 2>&1 | tail -6
```

Erwartet: `AttributeError: module 'simulation.skript' has no attribute
'FESTLEGUNGSPROBEN'` bzw. `... 'festlegungslage'`.

- [ ] **Schritt 3: `FESTLEGUNGSPROBEN` in `simulation/skript.py` anlegen**

Direkt unter `FIGUREN_SOLL` (skript.py:42):

```python
#: Drei sachliche Festlegungen, die in **kein** Arbeitsstandfeld passen -- die
#: drei schwersten Verluste der Gruppe 1 vom 06.09.2026 als Pruefsaetze
#: (``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 0: die vierteilige
#: Handlungsstruktur, die Gruppenzuordnung, die Laengen-/Strukturvorgabe).
#:
#: Je Probe ``(bereich, stichwort, satz)``. Der ``satz`` geht ins Ziel des
#: Schritts ``festlegungen`` -- die Stimmen sollen ihn sagen; das
#: ``stichwort`` ist, wonach ``kennzahlen.festlegungslage`` danach in allen
#: dauerhaften Feldern sucht. Der ``bereich`` muss ein
#: ``repo.FESTLEGUNG_BEREICHE`` sein, sonst wandert die Zeile auf
#: 'sonstiges' und die Bereichsspalte im Bericht sagt nichts.
#:
#: Bewusst drei und nicht zehn: jede Probe kostet die Gruppe Nachrichten, und
#: ein Schritt, der zehn Saetze verlangt, misst die Geduld des Simulators und
#: nicht das Gedaechtnis des Bots.
FESTLEGUNGSPROBEN: tuple[tuple[str, str, str], ...] = (
    ("struktur", "erste Folge einer Serie",
     "Das Stueck ist nur eine Szene -- die erste Folge einer Serie."),
    ("gruppe", "Outsider",
     "Die Figuren gehoeren zu zwei Gruppen: den Coolen und den Outsider."),
    ("stil", "hoechstens eine Seite",
     "Jeder Szenentext soll hoechstens eine Seite lang sein."),
)


def festlegungsproben_text(proben=None) -> str:
    """Die Pruefsaetze als Aufzaehlung fuer das Ziel eines Schritts.

    Eine Funktion und keine Konstante, damit ein Aufrufer eigene Proben
    einsetzen kann (die Tests tun das) und die Formatierung trotzdem an einer
    Stelle steht."""
    return "\n".join(f"- {satz}" for _b, _s, satz in
                     (FESTLEGUNGSPROBEN if proben is None else proben))
```

- [ ] **Schritt 4: `festlegungslage` in `simulation/kennzahlen.py` schreiben**

Hinter `datenlage_text` (kennzahlen.py:504), vor `kontextlage`:

```python
# ---------------------------------------------------------------------------
# Festlegungen: was ueberlebt (Analyse Phase 4, 06.09.2026)
# ---------------------------------------------------------------------------
#
# Der Befund, den diese Kennzahl misst: 22 von 42 Festlegungen der Gruppe 1
# waren verloren -- "kein Feld, oder nur ein journal-Eintrag der Art
# vorgeschlagen, der nachweislich nicht mehr in den Prompt kommt"
# (docs/analyse-phase4-datenverlust-2026-09-06.md § 0, § 2.7).
#
# Bis zum 30.09.2026 stand im Bericht dazu **nichts**: das Wort "festlegung"
# kam in dieser Datei nur in ``nachrichten_je_festlegung`` vor, und das zaehlt
# Nachrichten, nicht Speicherorte.


def _dauerhafter_text(conn, chat_id: int) -> str:
    """Alles, was ein Prompt dauerhaft sieht -- gefaltet, in einem String.

    **Das Journal gehoert ausdruecklich nicht dazu.** Es wird in
    ``kontext._baue_journal`` auf ``JOURNAL_EINTRAEGE`` = 8 Zeilen gekappt,
    und es gibt keinen Weg, der einen verdraengten Eintrag zurueckholt. Eine
    Angabe, die nur dort steht, ist nach acht weiteren Zeilen weg -- genau der
    Verlust, um den es geht.

    Drin sind: die Arbeitsstandfelder (ohne Schluessel und Buchhaltung), die
    Auffangtabelle in ihrer Prompt-Form (``repo.festlegungszeile``), Name und
    Beschreibung jeder Figur und die Planungsfelder jeder Szene. Alle vier
    gehen datengetrieben in den Gespraechs-Prompt."""
    teile: list[str] = []
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is not None:
        for spalte in skript.arbeitsstand_spalten(conn):
            if spalte in skript._KEINE_FELDER:
                continue
            try:
                teile.append(str(stand[spalte] or ""))
            except (IndexError, KeyError):
                continue
    for eintrag in repo.festlegungen(conn, chat_id):
        teile.append(repo.festlegungszeile(
            eintrag["bereich"], eintrag["bezug"], eintrag["text"]
        ))
    for figur in repo.figuren(conn, chat_id):
        teile.append(str(figur["name"] or ""))
        teile.append(str(figur["beschreibung"] or ""))
    for szene in repo.hole_szenen(conn, chat_id):
        for feld in ("titel", "was_passiert", "was_anders", "kernsaetze", "ton",
                     "anlass"):
            try:
                teile.append(str(szene[feld] or ""))
            except (IndexError, KeyError):
                continue
    return _falte(" ".join(teile))


def festlegungslage(conn, chat_id: int, proben=None) -> dict:
    """Wie viele Festlegungen stehen, und wie viele der Pruefsaetze haben
    ueberlebt.

    Drei Toepfe, dieselbe Einteilung wie in der Analyse: **erhalten** (steht
    in einem dauerhaften Feld oder in der Auffangtabelle -- OK),
    **nur_journal** (steht nur in der Chronik, faellt nach acht Zeilen aus dem
    Prompt -- VERKUERZT bis VERLOREN), **nirgends** (VERLOREN).

    Gesucht wird nach dem **Stichwort** der Probe, nicht nach dem ganzen Satz:
    eine Gruppe sagt eine Festlegung in ihren Worten, und ein Bot, der sie
    zusammenfasst, hat sie trotzdem gespeichert. Verglichen wird ueber
    ``_falte`` -- dieselbe Faltung, mit der diese Datei ueberall vergleicht.

    Soll: ``festlegungsproben_erhalten == festlegungsproben``, also
    ``nur_journal`` und ``nirgends`` beide leer."""
    proben = skript.FESTLEGUNGSPROBEN if proben is None else proben
    eintraege = repo.festlegungen(conn, chat_id)
    je_bereich: dict[str, int] = {}
    for eintrag in eintraege:
        bereich = eintrag["bereich"] or "?"
        je_bereich[bereich] = je_bereich.get(bereich, 0) + 1

    dauerhaft = _dauerhafter_text(conn, chat_id)
    journaltext = _falte(" ".join(
        str(e["text"] or "") for e in repo.journal(conn, chat_id)
    ))

    erhalten, nur_journal, nirgends = [], [], []
    for _bereich, stichwort, _satz in proben:
        wort = _falte(stichwort)
        if wort and wort in dauerhaft:
            erhalten.append(stichwort)
        elif wort and wort in journaltext:
            nur_journal.append(stichwort)
        else:
            nirgends.append(stichwort)

    return {
        "festlegungen": len(eintraege),
        "festlegungen_je_bereich": dict(sorted(je_bereich.items())),
        "festlegungsproben": len(proben),
        "festlegungsproben_erhalten": len(erhalten),
        "festlegungsproben_nur_journal": nur_journal,
        "festlegungsproben_nirgends": nirgends,
    }
```

In `sammle` (kennzahlen.py:772, direkt hinter `zahlen.update(zitatlage(...))`):

```python
    zahlen.update(festlegungslage(conn, chat_id))
```

- [ ] **Schritt 5: Tests gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_kennzahlen.py 2>&1 | tail -3
```

Erwartet: `31 passed` (23 vorher + 8). Scheitert
`test_eine_figurenbeschreibung_gilt_genauso`, weil `repo.setze_figur` eine
andere Signatur hat:
`grep -n "def setze_figur" -A 4 interview_theater/repo.py`.

- [ ] **Schritt 6: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add simulation/kennzahlen.py simulation/skript.py tests/test_simulation_kennzahlen.py
git commit -m "$(cat <<'EOF'
Kennzahl festlegungslage: was von einer Festlegung uebrigbleibt

Drei Pruefsaetze (skript.FESTLEGUNGSPROBEN) aus den drei schwersten
Dortmunder Verlusten, danach die Einteilung der Analyse: erhalten (Feld oder
Auffangtabelle), nur_journal (faellt nach 8 Zeilen aus dem Prompt), nirgends.
Das Journal zaehlt ausdruecklich NICHT als dauerhaft -- das ist der Befund.

Getestet in beide Richtungen: unter mutation.aktiv("festlegung_verloren")
schlaegt die Kennzahl an, ohne sie nicht.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

Erwartet: `2801 passed, 1 skipped` (2793 + 8).

---

## Aufgabe 5: Kennzahl `szenenlage` (kostenlos)

Heute findet **keine** Kennzahl den Fehler 2. `kennzahlen.formlage`
(kennzahlen.py:954) zaehlt `szenen_gesamt` und die Formbestaetigung —
`repo.hole_szenen` liefert aber nur die **aktiven** Zeilen, und ob eine
Szenenfolge zweimal neu erfunden wurde, steht nirgends.
`rahmen_ueberschrieben` zaehlt Journalzeilen, die mit „rahmen"/„setting"/
„geschichte" anfangen — nicht Szenen.

**Was gemessen werden muss, in beiden Gestalten des Fehlers:**

| Gestalt | Woran erkennbar |
|---|---|
| Der Fehler von damals: Szenen werden weich entfernt und neu angelegt | `szene.entfernt_am` ist gesetzt; je Zeitpunkt ein Neuaufbau |
| Der Fehler von heute (seit `repo.gleiche_szenenfolge_ab`): Titel werden ueberschrieben, Szenen kommen dazu | ein `aufruf` mit `art='szenenfolge'` **nach** der Richtungswahl |

Die Richtungswahl hat einen eindeutigen Zeitstempel: `_speichere_geschichte`
schreibt `journal`-Text `f"Geschichte: {geschichte}"` mit `quelle='knopf'`
(knoepfe/szenen.py:1115-1117). Der Inline-Weg schreibt danach zusaetzlich
`szenenfolge.JOURNAL_INLINE` („Szenen aus der gewaehlten Richtung: …",
szenenfolge.py:459) — ebenfalls ein mechanisches Merkmal und die Gegenprobe.

**Dateien:**
- Modify: `simulation/kennzahlen.py`
- Test: `tests/test_simulation_kennzahlen.py` (anhaengen)

**Interfaces:**
- Produces: `kennzahlen.szenenlage(conn, chat_id) -> dict` mit
  `szenen_aktiv`, `szenen_ersetzt`, `szenen_neuaufbauten`,
  `szenen_form_verloren`, `szenenfolge_laeufe`, `kurzgeschichte_laeufe`,
  `szenenfolge_nach_richtung`, `szenen_aus_richtung`
- Consumes: Tabellen `szene`, `aufruf`, `journal` (alle mit `chat_id`)

- [ ] **Schritt 1: Die Tests schreiben**

An das Ende von `tests/test_simulation_kennzahlen.py`:

```python
# --- Szenen: bleibt die Folge stehen? (Analyse Phase 5, 06.09.2026) -------
#
# Der Befund: aus drei geplanten Szenen mit festgelegter Form wurden sechs,
# und eine Stunde spaeter noch einmal sechs. Ausgeloest vom Regelweg der
# Richtungswahl, die am Ende immer starte_geschichte_szenen rief.

import szenenlage_helfer  # noqa: F401,E402  -- falls ausgelagert; sonst entfernen


def _szene_mit_form(conn, nummer, form="", entfernt=None):
    """Eine Szenenzeile von Hand -- der Simulator soll hier nichts modellieren
    muessen."""
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    if form:
        repo.setze_szenenfeld(conn, szene_id, "form", form)
    if entfernt:
        conn.execute("UPDATE szene SET entfernt_am = ? WHERE id = ?",
                     (entfernt, szene_id))
        conn.commit()
    return szene_id


def test_eine_stehende_folge_hat_keine_neuaufbauten(conn):
    for nummer in (1, 2, 3):
        _szene_mit_form(conn, nummer, "dialog")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_aktiv"] == 3
    assert lage["szenen_ersetzt"] == 0
    assert lage["szenen_neuaufbauten"] == 0
    assert lage["szenen_form_verloren"] == 0


def test_zwei_neuaufbauten_werden_an_den_zeitpunkten_gezaehlt(conn):
    """Der Live-Fall: ids 1-3 entfernt um 13:54:37, ids 4-9 um 14:09:35 --
    zwei Zeitpunkte, zwei Neuaufbauten, auch wenn neun Zeilen betroffen sind."""
    for nummer in (1, 2, 3):
        _szene_mit_form(conn, nummer, "chor", entfernt="2026-09-06T13:54:37")
    for nummer in (4, 5, 6):
        _szene_mit_form(conn, nummer, "", entfernt="2026-09-06T14:09:35")
    for nummer in (7, 8):
        _szene_mit_form(conn, nummer)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_ersetzt"] == 6
    assert lage["szenen_neuaufbauten"] == 2
    assert lage["szenen_form_verloren"] == 3, "nur die mit bestaetigter Form"
    assert lage["szenen_aktiv"] == 2


def test_ein_szenenfolge_lauf_nach_der_richtungswahl_ist_ein_befund(conn):
    """Genau das, was C9 abgeschafft hat: die Gruppe hat eine Richtung
    gedrueckt, und danach erfindet ein Lauf Titel und Form neu."""
    repo.schreibe_journal(conn, 1, "entschieden",
                          "Geschichte: Nacht am Kanal — Szene 1: Ankunft",
                          quelle="knopf")
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_laeufe"] == 1
    assert lage["szenenfolge_nach_richtung"] == 1
    assert lage["szenen_aus_richtung"] is False


def test_ein_lauf_vor_der_richtungswahl_zaehlt_nicht(conn):
    """Der Vorschlag, aus dem die Richtungen ueberhaupt entstanden sind, ist
    kein Befund -- gezaehlt wird nur, was NACH dem Druck kommt."""
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_laeufe"] == 1
    assert lage["szenenfolge_nach_richtung"] == 0


def test_der_inline_weg_wird_erkannt(conn):
    from interview_theater import szenenfolge

    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    repo.schreibe_journal(
        conn, 1, "entschieden",
        szenenfolge.JOURNAL_INLINE.format(liste="1. Ankunft; 2. Gestaendnis"),
        quelle="knopf",
    )
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_aus_richtung"] is True
    assert lage["szenenfolge_nach_richtung"] == 0


def test_ohne_richtungswahl_bleibt_die_zahl_null(conn):
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_nach_richtung"] == 0
    assert lage["szenen_aus_richtung"] is False


def test_der_prosalauf_wird_getrennt_gezaehlt(conn):
    """``kurzgeschichte`` ersetzt in Phase 6 bestimmungsgemaess -- die Zahl
    steht daneben, damit ein Neuaufbau nicht falsch zugeordnet wird."""
    repo.merke_aufruf(conn, 1, "kurzgeschichte", "A", 0, 10, 10, "stop", 1, 1)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["kurzgeschichte_laeufe"] == 1
    assert lage["szenenfolge_laeufe"] == 0


def test_szenenlage_steckt_in_sammle(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {}, _E(), PREISE_CHF_JE_MIO_TOKEN, 1.0,
    )
    for schluessel in ("szenen_aktiv", "szenen_ersetzt", "szenen_neuaufbauten",
                       "szenen_form_verloren", "szenenfolge_laeufe",
                       "kurzgeschichte_laeufe", "szenenfolge_nach_richtung",
                       "szenen_aus_richtung"):
        assert schluessel in zahlen
```

**Achtung, zwei Stellen zum Nachsehen, bevor das laeuft:**
1. Die Zeile `import szenenlage_helfer` im Testblock oben ist ein **Platzhalter
   aus dem Plan und muss geloescht werden** — sie steht hier nur, damit klar
   ist, dass der Block keine externen Helfer braucht. Streiche sie.
2. `repo.stelle_szene_sicher` und `repo.setze_szenenfeld` heissen laut
   `repo.py:2352` und AGENTS.md so; im Zweifel
   `grep -n "def stelle_szene_sicher\|def setze_szenenfeld" interview_theater/repo.py`.

- [ ] **Schritt 2: Laufen lassen, Fehlschlag bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_kennzahlen.py 2>&1 | tail -6
```

Erwartet: `AttributeError: module 'simulation.kennzahlen' has no attribute
'szenenlage'`.

- [ ] **Schritt 3: `szenenlage` in `simulation/kennzahlen.py` schreiben**

Direkt hinter `festlegungslage` aus Aufgabe 4:

```python
# ---------------------------------------------------------------------------
# Szenen: bleibt die Folge stehen? (Analyse Phase 5, 06.09.2026)
# ---------------------------------------------------------------------------
#
# Der Befund: drei geplante Szenen mit festgelegter Form, danach sechs mit
# anderen Titeln und anderen Formen, eine Stunde spaeter noch einmal sechs
# (docs/analyse-phase5-chaos-2026-09-06.md § 4).
#
# Der Fehler hat seit dem 06.09.2026 **zwei Gestalten**, und diese Kennzahl
# misst beide. Alt: ``szenenfolge.lege_an`` entfernte bestehende Szenen weich
# -- sichtbar an ``szene.entfernt_am``. Neu: ``repo.gleiche_szenenfolge_ab``
# entfernt nichts mehr, aber ``titel`` steht nicht in
# ``repo.GESCHUETZTE_SZENENFELDER`` -- ein frischer Vorschlag nach der
# Richtungswahl schreibt die Titel der Gruppe trotzdem um, und das kostet
# gemessene 110 s. Sichtbar ist das nur an einem ``aufruf`` mit
# ``art='szenenfolge'`` NACH dem Druck.

#: Woran die Richtungswahl in der Datenbank haengt: ``_speichere_geschichte``
#: schreibt diese Journalzeile (knoepfe/szenen.py), bevor irgendetwas anderes
#: passiert. Kein zweites Vokabular -- der Praefix steht dort im f-String.
_JOURNAL_RICHTUNG = "Geschichte:"


def szenenlage(conn, chat_id: int) -> dict:
    """Wie oft die Szenenfolge neu aufgebaut wurde -- und ob nach der
    Richtungswahl noch ein Vorschlagslauf kam.

    Sollwerte: ``szenen_neuaufbauten`` 0, ``szenen_form_verloren`` 0,
    ``szenenfolge_nach_richtung`` 0. Der Prosalauf (``kurzgeschichte``) steht
    getrennt daneben: er ersetzt in Phase 6 bestimmungsgemaess, und eine
    Kennzahl, die ihn mitzaehlt, meldete einen Lauf als kaputt, der genau das
    getan hat, was die Phase verlangt.

    ``szenen_aus_richtung`` ist die Gegenprobe zum Inline-Weg aus C9
    (``szenenfolge.JOURNAL_INLINE``): stimmt sie und ist
    ``szenenfolge_nach_richtung`` null, hat die Richtungswahl ihre Szenen
    mitgenommen."""
    from interview_theater import szenenfolge

    zeilen = conn.execute(
        "SELECT form, entfernt_am FROM szene WHERE chat_id = ?", (chat_id,)
    ).fetchall()
    entfernt = [z for z in zeilen if z["entfernt_am"]]

    laeufe = {
        z["art"]: z["n"]
        for z in conn.execute(
            "SELECT art, count(*) AS n FROM aufruf WHERE chat_id = ? "
            "AND art IN ('szenenfolge', 'kurzgeschichte') GROUP BY art",
            (chat_id,),
        )
    }

    # Der **erste** Druck auf eine Richtung ist der Stichtag: alles danach
    # haette die Titel der Gruppe schon vorgefunden.
    richtung = conn.execute(
        "SELECT erstellt_am FROM journal WHERE chat_id = ? "
        "AND entfernt_am IS NULL AND text LIKE ? ORDER BY id ASC LIMIT 1",
        (chat_id, _JOURNAL_RICHTUNG + "%"),
    ).fetchone()
    nach_richtung = 0
    if richtung is not None:
        nach_richtung = conn.execute(
            "SELECT count(*) FROM aufruf WHERE chat_id = ? AND art = ? "
            "AND erstellt_am > ?",
            (chat_id, szenenfolge.ART, richtung["erstellt_am"]),
        ).fetchone()[0]

    inline_praefix = szenenfolge.JOURNAL_INLINE.split("{")[0]
    aus_richtung = conn.execute(
        "SELECT count(*) FROM journal WHERE chat_id = ? "
        "AND entfernt_am IS NULL AND text LIKE ?",
        (chat_id, inline_praefix + "%"),
    ).fetchone()[0] > 0

    return {
        "szenen_aktiv": len(zeilen) - len(entfernt),
        "szenen_ersetzt": len(entfernt),
        "szenen_neuaufbauten": len({z["entfernt_am"] for z in entfernt}),
        "szenen_form_verloren": sum(
            1 for z in entfernt if (z["form"] or "").strip()
        ),
        "szenenfolge_laeufe": laeufe.get("szenenfolge", 0),
        "kurzgeschichte_laeufe": laeufe.get("kurzgeschichte", 0),
        "szenenfolge_nach_richtung": nach_richtung,
        "szenen_aus_richtung": aus_richtung,
    }
```

In `sammle`, direkt hinter `zahlen.update(festlegungslage(conn, chat_id))`:

```python
    zahlen.update(szenenlage(conn, chat_id))
```

**Namenskollision pruefen.** `formlage` liefert bereits `szenen_gesamt`;
`szenenlage` liefert `szenen_aktiv` — beide bleiben. Es gibt keinen doppelten
Schluessel; nachmessen mit:

```bash
$PY - <<'PY'
import inspect, re
from simulation import kennzahlen
quelle = inspect.getsource(kennzahlen.sammle)
print(re.findall(r"zahlen\.update\(([a-z_]+)\(", quelle))
PY
```

Erwartet: `['journallage', 'kontextlage', 'zitatlage', 'festlegungslage', 'szenenlage', 'sammle_knopfzahlen', 'kosten']`
(Reihenfolge je nach Einbau; `festlegungslage` und `szenenlage` muessen
darin stehen).

- [ ] **Schritt 4: Tests gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_kennzahlen.py 2>&1 | tail -3
```

Erwartet: `39 passed` (31 + 8).

- [ ] **Schritt 5: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add simulation/kennzahlen.py tests/test_simulation_kennzahlen.py
git commit -m "$(cat <<'EOF'
Kennzahl szenenlage: bleibt die Szenenfolge stehen?

Misst beide Gestalten des Fehlers aus der Phase-5-Analyse: die alte
(szene.entfernt_am, ein Neuaufbau je Zeitpunkt, verlorene bestaetigte Formen)
und die heutige (ein aufruf art=szenenfolge NACH der Richtungswahl -- titel
ist nicht geschuetzt, ein frischer Vorschlag ueberschreibt sie und kostet
110 s). Der Prosalauf steht getrennt daneben: er ersetzt bestimmungsgemaess.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

Erwartet: `2809 passed, 1 skipped` (2801 + 8).

---

## Aufgabe 6: Die neuen Kennzahlen in Bericht und `verlauf.jsonl` (kostenlos)

`bericht.verlaufszeile` streut `**zahlen` bereits ein
(`simulation/bericht.py:894`), die neuen Schluessel landen also **ohne
Zutun** in `verlauf.jsonl`. Was fehlt: die Zeilen in der Kennzahlentabelle mit
Sollwert daneben (sonst sagt eine nackte Zahl nichts,
`bericht.kennzahlen_tabelle`-Docstring) und das Feld `mutation`, ohne das zwei
Verlaufszeilen nicht auseinanderzuhalten sind.

**Dateien:**
- Modify: `simulation/bericht.py`
- Test: `tests/test_simulation_hintergrund.py` (dort stehen die Berichtstests) — vorher pruefen mit `grep -rn "kennzahlen_tabelle" tests/`; liegt der Test woanders, dort anhaengen.

**Interfaces:**
- Produces: `bericht._gegenpruefzeilen(zahlen) -> list[str]`; `verlaufszeile` traegt `"mutation"`
- Consumes: `kennzahlen.festlegungslage`, `kennzahlen.szenenlage` (ueber `sammle`), `kopfdaten["mutation"]`

- [ ] **Schritt 1: Die Tests schreiben**

```python
# --- Die Kennzahlen der Gegenpruefung im Bericht ---------------------------


def _zahlen_mit(**extra):
    """Eine Kennzahlenmenge, die ``kennzahlen_tabelle`` durchlaeuft."""
    grund = {
        "festlegungen": 0, "festlegungen_je_bereich": {},
        "festlegungsproben": 3, "festlegungsproben_erhalten": 3,
        "festlegungsproben_nur_journal": [], "festlegungsproben_nirgends": [],
        "szenen_aktiv": 3, "szenen_ersetzt": 0, "szenen_neuaufbauten": 0,
        "szenen_form_verloren": 0, "szenenfolge_laeufe": 1,
        "kurzgeschichte_laeufe": 0, "szenenfolge_nach_richtung": 0,
        "szenen_aus_richtung": True,
    }
    grund.update(extra)
    return grund


def test_die_gegenpruefzeilen_stehen_mit_sollwert_da():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit()))
    assert "Festlegungsproben erhalten" in zeilen
    assert "3/3" in zeilen
    assert "Szenen neu aufgebaut" in zeilen
    assert "Szenenfolge-Lauf nach der Richtungswahl" in zeilen
    assert "**daneben**" not in zeilen


def test_ein_verlust_wird_als_daneben_markiert():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit(
        festlegungsproben_erhalten=1,
        festlegungsproben_nur_journal=["Outsider"],
        festlegungsproben_nirgends=["hoechstens eine Seite"],
    )))
    assert "1/3" in zeilen
    assert "**daneben**" in zeilen


def test_ein_neuaufbau_wird_als_daneben_markiert():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit(
        szenen_neuaufbauten=2, szenen_form_verloren=3,
        szenenfolge_nach_richtung=1, szenen_aus_richtung=False,
    )))
    assert zeilen.count("**daneben**") >= 3


def test_eine_alte_verlaufszeile_ohne_die_schluessel_bleibt_lesbar():
    """Wie bei den Knopfzahlen (06.09.2026): fehlt der Block, steht er nicht
    da -- ein KeyError im Bericht waere schlimmer als eine fehlende Zeile."""
    assert bericht._gegenpruefzeilen({"echo": 0}) == []


def test_die_verlaufszeile_traegt_die_mutation():
    class _Ergebnis:
        urteile = {}
        szenen = []
        gezogene = []
        personen = []
        szenen_urteil = {}

    kopf = {"kennung": "k", "mischung": "set1", "seed": 1, "git": "abc",
            "llm_modell": "kimi", "erkenner_modell": "gemma",
            "sim_modell": "claude-opus-5", "mutation": "festlegung_verloren"}
    zeile = bericht.verlaufszeile(_zahlen_mit(), _Ergebnis(), kopf)
    assert zeile["mutation"] == "festlegung_verloren"

    kopf_ohne = {**kopf}
    kopf_ohne.pop("mutation")
    assert bericht.verlaufszeile(_zahlen_mit(), _Ergebnis(), kopf_ohne)["mutation"] == ""
```

- [ ] **Schritt 2: Laufen lassen, Fehlschlag bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_hintergrund.py 2>&1 | tail -5
```

Erwartet: `AttributeError: module 'simulation.bericht' has no attribute
'_gegenpruefzeilen'`.

- [ ] **Schritt 3: `simulation/bericht.py` erweitern**

Hinter `_knopfzeilen` (bericht.py:190):

```python
def _gegenpruefzeilen(zahlen: dict) -> list[str]:
    """Die Kennzahlen der Gegenpruefung vom 30.09.2026 als Tabellenzeilen.

    Zwei Fehler, beide belegt, beide bis dahin unsichtbar im Bericht: der
    Verlust nicht kategorisierbarer Festlegungen
    (``docs/analyse-phase4-datenverlust-2026-09-06.md``, 22 von 42) und der
    Neuaufbau der Szenenfolge (``docs/analyse-phase5-chaos-2026-09-06.md``,
    3 -> 6 -> 6).

    Getrennt aufgebaut wie ``_knopfzeilen``: eine Verlaufszeile von vor dem
    30.09. hat diese Schluessel nicht, und ein ``KeyError`` mitten im Bericht
    waere schlimmer als eine fehlende Zeile."""
    if "festlegungsproben" not in zahlen:
        return []
    zeilen = []

    def zeile(name, wert, soll, gut):
        zeilen.append(f"| {name} | {wert} | {soll} | {_urteil(wert, soll, gut)} |")

    erhalten = zahlen.get("festlegungsproben_erhalten", 0)
    proben = zahlen.get("festlegungsproben", 0)
    zeile("Festlegungsproben erhalten", _anteil(erhalten, proben), "alle",
          bool(proben) and erhalten == proben)
    nur_journal = zahlen.get("festlegungsproben_nur_journal") or []
    zeile("davon nur im Journal (faellt nach 8 Zeilen)",
          f"{len(nur_journal)}" + (f" ({', '.join(nur_journal)})" if nur_journal else ""),
          0, not nur_journal)
    nirgends = zahlen.get("festlegungsproben_nirgends") or []
    zeile("davon nirgends",
          f"{len(nirgends)}" + (f" ({', '.join(nirgends)})" if nirgends else ""),
          0, not nirgends)
    zeile("Eintraege in `festlegung`",
          f"{zahlen.get('festlegungen', 0)} "
          + (str(zahlen.get("festlegungen_je_bereich") or {}) or ""),
          "> 0", zahlen.get("festlegungen", 0) > 0)

    zeile("Szenen neu aufgebaut", zahlen.get("szenen_neuaufbauten", 0), 0,
          not zahlen.get("szenen_neuaufbauten"))
    zeile("bestaetigte Formen dabei verloren",
          zahlen.get("szenen_form_verloren", 0), 0,
          not zahlen.get("szenen_form_verloren"))
    zeile("Szenenfolge-Lauf nach der Richtungswahl",
          zahlen.get("szenenfolge_nach_richtung", 0), 0,
          not zahlen.get("szenenfolge_nach_richtung"))
    zeile("Szenen aus der Richtung uebernommen (C9)",
          "ja" if zahlen.get("szenen_aus_richtung") else "nein",
          "ja, wenn die Richtung welche nennt",
          bool(zahlen.get("szenen_aus_richtung")))
    zeile("Szenen aktiv / Prosalaeufe",
          f"{zahlen.get('szenen_aktiv', 0)} / "
          f"{zahlen.get('kurzgeschichte_laeufe', 0)}",
          "–", True)
    return zeilen
```

In `kennzahlen_tabelle`, in der letzten Zeile vor `return zeilen`:

```python
    zeilen.extend(_knopfzeilen(zahlen))
    zeilen.extend(_gegenpruefzeilen(zahlen))
    return zeilen
```

In `verlaufszeile`, im Rueckgabe-Dict hinter `"sim_modell"`:

```python
        # Ohne dieses Feld sind zwei Verlaufszeilen desselben Sets und Seeds
        # nicht auseinanderzuhalten -- und genau das ist der Vergleich, um den
        # es in der Gegenpruefung geht.
        "mutation": kopfdaten.get("mutation") or "",
```

- [ ] **Schritt 4: Tests gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_hintergrund.py 2>&1 | tail -3
```

Erwartet: die bisherige Zahl + 5.

- [ ] **Schritt 5: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add simulation/bericht.py tests/test_simulation_hintergrund.py
git commit -m "$(cat <<'EOF'
Bericht: die Kennzahlen der Gegenpruefung mit Sollwert, Mutation im Verlauf

Neun Zeilen in der Kennzahlentabelle -- Festlegungsproben erhalten / nur im
Journal / nirgends, Neuaufbauten, verlorene Formen, Szenenfolge-Lauf nach der
Richtungswahl. Getrennt aufgebaut wie _knopfzeilen: eine alte Verlaufszeile
hat die Schluessel nicht, und ein KeyError im Bericht waere schlimmer als
eine fehlende Zeile. verlauf.jsonl traegt jetzt "mutation".

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 7: Das Skript fahrbar machen (kostenlos)

Fuenf Aenderungen, alle aus den Befunden der Praemissenpruefung, **nur so
viel, wie die Nachweislaeufe brauchen** — kein Umbau aus Prinzip:

1. **`--skript {auto,schritte,tag2,birk}`** in `scripts/simulation.py`. Ohne
   den Schalter faehrt `--set 1` weiter `SCHRITTE` (nichts aendert sich fuer
   jemanden, der alte Laeufe vergleicht); mit `--skript tag2` faehrt es
   `SCHRITTE_TAG2` und damit die heutigen sieben Phasen. **Das ist die
   Voraussetzung fuer beide Nachweislaeufe** — `SCHRITTE` hat die Schritte
   `setting`, `geschichte`, `schaerfung` nicht.
2. **`--mutation {festlegung_verloren,richtung_ohne_szenen}`**, wirkt ueber
   `mutation.aktiv`, geht in `kopfdaten` und in den Mischungsnamen.
3. **Hintergrund-Threads abwarten.** `lauf.einfaedig()` macht
   `szenenfolge.starte_geschichte_szenen`, `schaerfung.starte`,
   `sprachstil.starte` und `kurzgeschichte.starte` **nicht** synchron. Statt
   vier weitere Funktionen nachzubauen (jede mit ihrer Sperrlogik — ein
   Sperr-Leck ist am 30.09. eigens repariert worden), wartet der Lauf am Ende
   jedes Zuges auf die Threads, die **dieser Zug** gestartet hat. Ein Ort, kein
   Nachbau, und es erfasst jeden kuenftigen Hintergrundlauf mit.
4. **Der Schritt `festlegungen`** in `SCHRITTE_TAG2`, der die drei Pruefsaetze
   sagen laesst und pruefen kann, ob sie dauerhaft liegen.
5. **Doku und Namen nachziehen**, damit die Praemissenpruefung aus Aufgabe 1
   leer laeuft.

**Dateien:**
- Modify: `scripts/simulation.py`
- Modify: `simulation/lauf.py`
- Modify: `simulation/skript.py`
- Modify: `simulation/README.md`
- Modify: `tests/test_simulation_durchlauf.py` (nur der Name/Docstring „neun Schritte")
- Test: `tests/test_simulation_lauf.py`, `tests/test_simulation_skript.py` (anhaengen)

**Interfaces:**
- Produces:
  - `lauf.HINTERGRUND_S: float` = 300.0
  - `lauf.warte_auf_hintergrund(vorher: frozenset, grenze_s: float = HINTERGRUND_S) -> int` — Anzahl der abgewarteten Threads
  - `skript._fertig_festlegungen(conn, chat_id, merker) -> bool`
  - `skript.SCHRITTE_TAG2` enthaelt den Schritt `festlegungen` zwischen `setting` und `geschichte`
  - `scripts.simulation.baue_argumente` kennt `args.skript` und `args.mutation`
  - `scripts.simulation._schritte(args)` beachtet `args.skript`
- Consumes: `mutation.aktiv`, `skript.FESTLEGUNGSPROBEN`, `kennzahlen.festlegungslage`

- [ ] **Schritt 1: Die Tests fuer das Abwarten schreiben**

An `tests/test_simulation_lauf.py` anhaengen:

```python
# --- Hintergrundlaeufe abwarten (30.09.2026) -------------------------------
#
# lauf.einfaedig() macht szene.starte und drei Geschwister synchron -- nicht
# aber szenenfolge.starte_geschichte_szenen, schaerfung.starte,
# sprachstil.starte, kurzgeschichte.starte. Deren Wirkung landete zu einem
# beliebigen Zeitpunkt in der Datenbank, unter Umstaenden nach conn.close().

import threading
import time


def test_warte_auf_hintergrund_wartet_auf_neue_threads():
    gemerkt = []

    def arbeite():
        time.sleep(0.05)
        gemerkt.append("da")

    vorher = frozenset(threading.enumerate())
    threading.Thread(target=arbeite, daemon=True).start()
    abgewartet = lauf.warte_auf_hintergrund(vorher, grenze_s=5.0)
    assert gemerkt == ["da"]
    assert abgewartet == 1


def test_warte_auf_hintergrund_ignoriert_alte_threads():
    """Bei ``--parallel`` laufen zwei Laeufe in Threads. Der eine darf nicht
    auf den anderen warten -- gewartet wird nur auf Threads, die es beim
    Beginn dieses Zuges noch nicht gab."""
    halt = threading.Event()
    alt = threading.Thread(target=halt.wait, daemon=True)
    alt.start()
    try:
        vorher = frozenset(threading.enumerate())
        assert alt in vorher
        start = time.monotonic()
        assert lauf.warte_auf_hintergrund(vorher, grenze_s=5.0) == 0
        assert time.monotonic() - start < 1.0
    finally:
        halt.set()


def test_warte_auf_hintergrund_gibt_nach_der_grenze_auf():
    """Ein haengender Lauf darf den Simulator nicht festhalten: nach der
    Grenze geht es weiter, und der Bericht zeigt am fehlenden Zielzustand,
    dass etwas nicht fertig wurde."""
    halt = threading.Event()
    vorher = frozenset(threading.enumerate())
    threading.Thread(target=halt.wait, daemon=True).start()
    try:
        start = time.monotonic()
        lauf.warte_auf_hintergrund(vorher, grenze_s=0.2)
        assert time.monotonic() - start < 2.0
    finally:
        halt.set()


def test_der_lauf_merkt_sich_die_threads_beim_zuganfang(conn, einst):
    """``_zug`` legt die Momentaufnahme an, ``_schliesse_zug`` wartet -- damit
    die Nachrichten des Hintergrundlaufs noch in DIESEN Zug fallen und nicht
    in den naechsten."""
    from simulation.attrappe import TelegramAttrappe

    durchlauf = lauf.Lauf(
        conn, TelegramAttrappe(), None, einst, None,
        gezogene=[], seed=1, schritte=[],
    )
    zug = durchlauf._zug()
    assert isinstance(durchlauf._threads_vorher, frozenset)
    assert threading.current_thread() in durchlauf._threads_vorher
    assert zug is durchlauf.ergebnis.zuege[-1]
```

- [ ] **Schritt 2: Tests fuer den neuen Schritt und die Namen schreiben**

An `tests/test_simulation_skript.py` anhaengen:

```python
# --- Der heutige Phasenstand (30.09.2026) ---------------------------------


def test_das_tag2_skript_faehrt_jede_phase_genau_einmal_an():
    """Sieben Phasen, sechs Phasenschritte (in die erste kommt niemand per
    Knopf). Eine achte Phase soll dieses Skript nicht mitreissen -- deshalb
    gegen ``phasen.PHASEN`` geprueft und nicht gegen eine Zahl."""
    nummern = [s.phase_nummer for s in skript.SCHRITTE_TAG2 if s.art == "phase"]
    assert nummern == [n for n, _k, _b in phasen.PHASEN][1:]


def test_die_konstanten_heissen_wie_die_phasen_heute():
    assert phasen.kurzname(skript.PHASE_SCHAERFUNG).startswith("Schaerfung")
    assert skript.PHASE_SETTING == skript.PHASE_GESCHICHTE
    assert phasen.kurzname(skript.PHASE_SETTING) == phasen.kurzname(4)
    # Die frueheren Namen "Szenentexte"/"Durchlauf" gibt es nicht mehr.
    assert not hasattr(skript, "PHASE_SZENENTEXTE")
    assert not hasattr(skript, "PHASE_DURCHLAUF")
    assert phasen.kurzname(skript.PHASE_PROSA) == phasen.kurzname(6)
    assert phasen.kurzname(skript.PHASE_FEINSCHLIFF) == phasen.kurzname(7)


def test_der_titel_von_phase_mitte_nennt_seine_eigene_phase():
    """``Schritt("phase_mitte", "Phase 5", ...)`` bei ``PHASE_MITTE == 4`` war
    der Befund vom 30.09.2026 -- der Titel steht im Lauf-Protokoll und im
    Bericht, und wer dort "Phase 5" liest, glaubt, Phase 5 sei gemessen."""
    titel = skript.schritt_fuer("phase_mitte").titel
    assert str(skript.PHASE_MITTE) in titel
    assert "Phase 5" not in titel


def test_der_festlegungsschritt_liegt_zwischen_setting_und_geschichte():
    schluessel = [s.schluessel for s in skript.SCHRITTE_TAG2]
    assert schluessel.index("setting") < schluessel.index("festlegungen")
    assert schluessel.index("festlegungen") < schluessel.index("geschichte")


def test_das_ziel_des_festlegungsschritts_nennt_alle_pruefsaetze():
    schritt = skript.schritt_fuer("festlegungen", skript.SCHRITTE_TAG2)
    ziel = schritt.ziel_text({
        "festlegungsproben": skript.festlegungsproben_text(),
    })
    for _bereich, _stichwort, satz in skript.FESTLEGUNGSPROBEN:
        assert satz in ziel


def test_der_festlegungsschritt_ist_erst_fertig_wenn_alles_dauerhaft_liegt(conn):
    from interview_theater import repo

    schritt = skript.schritt_fuer("festlegungen", skript.SCHRITTE_TAG2)
    assert schritt.fertig(conn, 1, {}) is False
    for bereich, _stichwort, satz in skript.FESTLEGUNGSPROBEN:
        repo.schreibe_festlegung(conn, 1, bereich, satz)
    assert schritt.fertig(conn, 1, {}) is True


def test_der_merker_liefert_die_pruefsaetze(conn, einst):
    """``ziel_text`` faellt mit ``KeyError`` aus, wenn der Platzhalter fehlt --
    und zwar mitten im Lauf, nach dem ersten bezahlten Modellaufruf."""
    from simulation import lauf as lauf_modul
    from simulation.attrappe import TelegramAttrappe

    durchlauf = lauf_modul.Lauf(
        conn, TelegramAttrappe(), None, einst, None,
        gezogene=[], seed=1, schritte=[],
    )
    merker = durchlauf._merker()
    assert "festlegungsproben" in merker
    for schritt in skript.SCHRITTE_TAG2:
        schritt.ziel_text(merker)   # darf nicht werfen
```

Dazu ein Test fuer die Schalter, an `tests/test_simulation_skript.py`
(oder dort, wo `baue_argumente` heute geprueft wird — vorher
`grep -rn "baue_argumente" tests/`):

```python
def test_skript_schalter_waehlt_die_liste():
    from scripts import simulation as sim

    args = sim.baue_argumente(["--set", "1"])
    assert sim._schritte(args) is skript.SCHRITTE
    args = sim.baue_argumente(["--set", "1", "--skript", "tag2"])
    assert sim._schritte(args) is skript.SCHRITTE_TAG2
    args = sim.baue_argumente(["--set", "1", "--skript", "tag2", "--ohne-szene"])
    assert all(s.art != "szene" for s in sim._schritte(args))


def test_mutation_geht_in_den_mischungsnamen():
    from scripts import simulation as sim

    args = sim.baue_argumente(["--set", "1"])
    assert sim.mischungsname(args) == "set1"
    args = sim.baue_argumente(["--set", "1", "--mutation", "festlegung_verloren"])
    assert sim.mischungsname(args) == "set1-festlegung_verloren"


def test_eine_unbekannte_mutation_wird_vom_parser_abgelehnt():
    from scripts import simulation as sim

    with pytest.raises(SystemExit):
        sim.baue_argumente(["--set", "1", "--mutation", "gibtsnicht"])
```

- [ ] **Schritt 3: Tests laufen lassen, Fehlschlaege bestaetigen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_lauf.py tests/test_simulation_skript.py 2>&1 | tail -8
```

Erwartet: mehrere `AttributeError`/`KeyError` — `lauf.warte_auf_hintergrund`,
`skript.PHASE_PROSA`, `schritt_fuer("festlegungen", ...)`, `args.skript`.

- [ ] **Schritt 4: `simulation/lauf.py` — Threads abwarten**

Neben `SEKUNDEN_JE_NACHRICHT` (lauf.py:54):

```python
#: Wie lange ein Zug hoechstens auf die Hintergrundlaeufe wartet, die er
#: gestartet hat. 300 s, weil die gemessenen Laeufe darunter liegen: die
#: Szenenfolge brauchte am 06.09.2026 110 s, die Kurzgeschichte 150 s
#: (docs/analyse-phase5-chaos-2026-09-06.md § 0). Ein haengender Lauf haelt
#: den Simulator damit hoechstens fuenf Minuten auf; danach geht es weiter,
#: und der fehlende Zielzustand steht als gescheiterter Schritt im Bericht.
HINTERGRUND_S = 300.0


def warte_auf_hintergrund(vorher: frozenset, grenze_s: float = HINTERGRUND_S) -> int:
    """Wartet auf die Threads, die seit ``vorher`` dazugekommen sind.

    **Warum das noetig ist.** ``einfaedig()`` macht vier Stellen synchron, an
    denen der Betrieb einen Thread startet -- ``szenenfolge.starte_geschichte_szenen``,
    ``schaerfung.starte``, ``sprachstil.starte`` und ``kurzgeschichte.starte``
    sind nicht darunter. Ihre Wirkung landete deshalb zu einem beliebigen
    Zeitpunkt in der Datenbank, unter Umstaenden erst nach ``conn.close()`` am
    Ende des Laufs -- und der Zielzustand des naechsten Schritts wurde gegen
    eine Datenbank geprueft, in der noch nichts stand.

    **Warum nicht vier weitere Ersatzfunktionen.** Jede von ihnen traegt ihre
    eigene Sperr- und Merklogik (``vorschlagssperre.nimm_oder_merke``, und ein
    Sperr-Leck darin ist am 30.09.2026 eigens repariert worden). Sie
    nachzubauen hiesse, dieselbe Logik zweimal zu haben -- hier wird statt
    dessen **abgewartet**, und das erfasst jeden kuenftigen Hintergrundlauf
    mit.

    **Nur die neuen Threads.** Bei ``--parallel`` faehrt jeder Lauf in einem
    eigenen Thread; auf den anderen zu warten waere ein Deadlock mit Ansage.
    Deshalb die Momentaufnahme vom Zuganfang.

    Liefert, auf wie viele Threads gewartet wurde -- fuer den Test, nicht fuer
    den Bericht."""
    ende = time.monotonic() + grenze_s
    abgewartet = 0
    ich = threading.current_thread()
    while True:
        neu = [
            t for t in threading.enumerate()
            if t not in vorher and t is not ich and t.is_alive()
        ]
        if not neu:
            return abgewartet
        uebrig = ende - time.monotonic()
        if uebrig <= 0:
            log.warning("Hintergrundlauf nach %.0f s nicht fertig: %s",
                        grenze_s, [t.name for t in neu])
            return abgewartet
        neu[0].join(timeout=uebrig)
        abgewartet += 1
```

In `Lauf.__init__` hinter `self._schritt = ...`:

```python
        #: Die Threads, die es beim Beginn des laufenden Zuges schon gab --
        #: alles, was danach dazukommt, ist ein Hintergrundlauf dieses Zuges.
        self._threads_vorher: frozenset = frozenset(threading.enumerate())
```

In `Lauf._zug`, als erste Zeile:

```python
        self._threads_vorher = frozenset(threading.enumerate())
```

In `Lauf._schliesse_zug`, als erste Zeile (**vor** `zug.bot = ...`, damit die
Nachrichten des Hintergrundlaufs noch in diesen Zug fallen):

```python
        warte_auf_hintergrund(self._threads_vorher)
```

In `Lauf._merker`, im Rueckgabe-Dict:

```python
            "festlegungsproben": skript.festlegungsproben_text(),
```

- [ ] **Schritt 5: `simulation/skript.py` — Schritt, Namen, Docstrings**

(a) Der Docstring-Kopf (Zeilen 1–24): `Neun Schritte` → die Zahl nicht mehr
nennen, und die Feldbeschreibung auf `geschichte` bringen:

```python
"""Der Ablauf, den die simulierten Teilnehmerinnen *wollen*.

Je Schritt ein **Ziel** (was die Stimmen anstreben, nicht was sie woertlich
sagen) und ein **Zielzustand in der Datenbank** (woran der Lauf merkt, dass
der Schritt durch ist). Ist der Zielzustand nach ``MAX_NACHRICHTEN``
Stimm-Nachrichten nicht erreicht, gilt der Schritt als **gescheitert**, wird
so vermerkt, und der Lauf geht trotzdem weiter -- ein Workshop bleibt auch
nicht stehen, weil der Bot etwas nicht mitbekommen hat.

**Drei Skriptlisten, keine ist die eine.** ``SCHRITTE`` ist die Messlatte der
Laeufe vom 05.09.2026 und bleibt deshalb unveraendert -- sie steuert die
Phasen NICHT an (kein ``art='phase'``-Schritt) und kennt eine Station
'Kernthema', die es seit dem 06.09. nicht mehr gibt. ``SCHRITTE_TAG2`` ist
das Skript der heutigen **sieben** Phasen aus ``phasen.PHASEN``.
``SCHRITTE_BIRK`` faehrt echtes Material. Welche gefahren wird, entscheidet
``scripts.simulation._schritte`` (Schalter ``--skript``).

**Datengetrieben, nicht hart codiert.** Die Phasen kommen aus
``phasen.PHASEN``, die Arbeitsstandfelder aus ``PRAGMA
table_info(arbeitsstand)``. Welches Feld zu einer Phase gehoert, wird aus
ihrem Kurznamen abgeleitet (``felder_fuer_phase``): heisst Phase 4 seit dem
06.09.2026 'Setting, Figuren & Geschichte', ist es ``geschichte``; hiesse sie
wieder 'Hauptkonflikt', waere es die Spalte ``hauptkonflikt``. Findet sich gar
keine Spalte, faellt die Pruefung auf 'die Gruppe steht in dieser Phase'
zurueck -- lieber eine schwaechere Aussage als eine falsche.

**Pflicht ist das erste Feld** (``pflichtfeld_fuer_phase``). Ein Kurzname
nennt zuerst die Entscheidung, die die naechste Phase traegt: bei 'Setting,
Figuren & Geschichte' ist das ``geschichte`` -- ohne sie gibt es keine
Szenenfolge --, waehrend ``rahmen`` fuer sich genommen leer bleiben darf.
"""
```

(b) `pflichtfeld_fuer_phase`-Docstring (Zeilen 114–127): `format`/`rahmen`
durch `geschichte` ersetzen, gleicher Sinn.

(c) Kommentar bei `SCHRITTE` (Zeile 288):

```python
#: Die Schritte in der Reihenfolge, in der sie gefahren werden. **Nicht
#: anfassen** -- diese Liste ist die Messlatte der Laeufe vom 05.09.2026, und
#: der Vergleich ueber ``verlauf.jsonl`` ist der einzige Grund, aus dem die
#: Datei im Repository liegt. Fuer die heutigen Phasen: ``SCHRITTE_TAG2``.
```

(d) Der Titel des Schritts `phase_mitte` (Zeile 337):

```python
    Schritt(
        "phase_mitte",
        f"Phase {PHASE_MITTE}",
        ...
```

`PHASE_MITTE` steht bei Zeile 47 und ist vor `SCHRITTE` definiert — der
f-String greift.

(e) Der Kopf des Tag2-Blocks (Zeilen 540–563):

```python
# ---------------------------------------------------------------------------
# Das Skript der sieben Phasen -- ``--skript tag2`` und alle ``--set tag1-*``
# ---------------------------------------------------------------------------
#
# Warum ein zweites Skript und nicht ein umgebautes erstes: ``SCHRITTE`` und
# ``SCHRITTE_BIRK`` sind die Messlatte der vier Laeufe vom 05.09. Ein Umbau an
# ihnen macht die alten Verlaufszeilen unvergleichbar -- und der Vergleich
# ueber die Laeufe hinweg ist der einzige Grund, aus dem ``verlauf.jsonl``
# ueberhaupt im Repository liegt. Das neue Skript steht daneben.
#
# Der Ablauf folgt den Phasen aus ``phasen.PHASEN``. Die Phasennummern stehen
# als Konstanten, nicht als Zahlen im Text: eine achte Phase soll dieses
# Skript nicht mitreissen.

PHASE_BEGRIFFE = 1
PHASE_FRAGEN = 2
PHASE_INTERVIEWS = 3
#: Setting, Figuren UND Geschichte sind seit dem 06.09.2026 eine Station.
PHASE_SETTING = 4
PHASE_GESCHICHTE = PHASE_SETTING
PHASE_SCHAERFUNG = 5
#: Phase 6 heisst seit dem 06.09.2026 abends "Szenen als Geschichte" (Prosa),
#: Phase 7 "Feinschliff" (Form je Szene, Uebersetzung, Stueckpruefung). Die
#: alten Namen ``PHASE_SZENENTEXTE``/``PHASE_DURCHLAUF`` sind weg, damit
#: niemand aus dem Namen auf die falsche Station schliesst.
PHASE_PROSA = 6
PHASE_FEINSCHLIFF = 7
```

Danach `grep -rn "PHASE_SZENENTEXTE\|PHASE_STUECKPRUEFUNG\|PHASE_DURCHLAUF" simulation/ tests/`
und jede Verwendung auf `PHASE_PROSA`/`PHASE_FEINSCHLIFF` umstellen
(`_phasenschritt(PHASE_SZENENTEXTE)` → `_phasenschritt(PHASE_PROSA)`,
`_phasenschritt(PHASE_STUECKPRUEFUNG)` → `_phasenschritt(PHASE_FEINSCHLIFF)`).

(f) Der Zielzustand und der Schritt, hinter `_fertig_setting`:

```python
def _fertig_festlegungen(conn, chat_id, merker):
    """Alle Pruefsaetze liegen **dauerhaft** -- in einem Arbeitsstandfeld, an
    einer Figur, an einer Szene oder in der Auffangtabelle ``festlegung``.

    Das Journal zaehlt nicht mit: es wird in ``kontext._baue_journal`` auf acht
    Zeilen gekappt, und ein verdraengter Eintrag kommt nie zurueck -- genau der
    Verlust aus ``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 2.7.

    Der Import steht in der Funktion, weil ``kennzahlen`` dieses Modul auf
    Modulebene importiert; oben waere das ein Zyklus. Dieselbe Bauart wie
    ueberall im Repo."""
    from simulation import kennzahlen

    lage = kennzahlen.festlegungslage(conn, chat_id)
    return lage["festlegungsproben_erhalten"] == lage["festlegungsproben"]
```

Und in `SCHRITTE_TAG2`, **zwischen** dem Schritt `setting` und dem Schritt
`geschichte`:

```python
    Schritt(
        "festlegungen",
        "Phase 4: was in kein Feld passt (dieselbe Station)",
        "Ihr legt jetzt drei Sachen fest, die in keinen der Bot-Kaesten "
        "passen. Sagt sie ihm in eigenen Worten, eine nach der anderen, und "
        "vergewissert euch, dass er sie festgehalten hat:\n"
        "{festlegungsproben}",
        _fertig_festlegungen,
        max_nachrichten=6,
    ),
```

- [ ] **Schritt 6: `scripts/simulation.py` — die zwei Schalter**

Import ergaenzen:

```python
from simulation import (
    bericht, birk, claude, kennzahlen, lauf, material, mutation, richter, skript,
    stoerung, tag1,
)
```

In `baue_argumente`, hinter `--ohne-szene`:

```python
    p.add_argument("--skript", choices=("auto", "schritte", "tag2", "birk"),
                   default="auto",
                   help="welche Schrittliste gefahren wird. 'auto' (Vorgabe) "
                        "waehlt wie bisher nach dem Set; 'tag2' faehrt das "
                        "Skript der heutigen Phasen (skript.SCHRITTE_TAG2) "
                        "auch fuer die erfundenen Sets 1-3 -- nur damit sind "
                        "Setting, Festlegungen, Geschichte und Schaerfung "
                        "ueberhaupt im Lauf")
    p.add_argument("--mutation", choices=mutation.ARTEN,
                   help="einen belegten Fehler fuer diesen Lauf wieder "
                        "einbauen (simulation/mutation.py) -- nur zum "
                        "Gegenpruefen der Kennzahlen, nie im Betrieb")
```

`_schritte` erweitern:

```python
def _schritte(args):
    """Welche Schrittliste dieser Lauf faehrt.

    ``--skript`` schlaegt die Herkunft aus dem Set. Vorgabe bleibt ``auto``,
    also genau das bisherige Verhalten -- ein alter Aufruf soll nach diesem
    Schalter dieselbe Liste fahren wie vorher, sonst waeren die
    Verlaufszeilen von damals nicht mehr vergleichbar."""
    gewaehlt = getattr(args, "skript", "auto")
    if gewaehlt == "tag2":
        grund = skript.SCHRITTE_TAG2
    elif gewaehlt == "schritte":
        grund = skript.SCHRITTE
    elif gewaehlt == "birk":
        grund = skript.SCHRITTE_BIRK
    elif ist_tag1(args):
        grund = skript.SCHRITTE_TAG2
    elif ist_birk(args):
        grund = skript.SCHRITTE_BIRK
    else:
        grund = skript.SCHRITTE
    return skript.ohne_szene(grund) if args.ohne_szene else grund
```

`mischungsname` erweitern (letzte Zeilen der Funktion):

```python
def mischungsname(args) -> str:
    """Wie der Lauf in Dateinamen und Verlauf heisst.

    Die Mutation gehoert dazu: zwei Laeufe mit demselben Set und demselben
    Seed, einer mutiert, wuerden sonst dieselbe Berichtsdatei ueberschreiben
    -- und im Verlauf staenden zwei Zeilen, die niemand auseinanderhalten
    kann."""
    if ist_birk(args):
        name = birk.NAME
    elif ist_tag1(args):
        name = args.set
    elif args.set:
        name = f"set{args.set}"
    elif args.mix:
        name = "mix" + "-".join(str(n) for n in args.mix)
    else:
        name = "alle15"
    zusatz = getattr(args, "mutation", None)
    return f"{name}-{zusatz}" if zusatz else name
```

In `einen_lauf`, als erste Zeile im `with contextlib.ExitStack() as stapel:`:

```python
        # Vor allem anderen: die Mutation muss stehen, bevor irgendein
        # Produktivmodul aufgerufen wird.
        stapel.enter_context(mutation.aktiv(getattr(args, "mutation", None)))
```

Und in `kopfdaten`:

```python
            "mutation": getattr(args, "mutation", None) or "",
```

Im Ausgabeblock vor `bericht.baue`, damit es im Protokoll steht:

```python
        if kopfdaten["mutation"]:
            print(f"!! MUTATION AKTIV: {kopfdaten['mutation']}", flush=True)
            print(f"   {mutation.BESCHREIBUNG[kopfdaten['mutation']]}", flush=True)
```

`replace_args` muss die neuen Felder mitnehmen — es kopiert `vars(args)`
vollstaendig, also nichts zu tun. **Pruefen**, nicht annehmen:
`grep -n "def replace_args" -A 12 scripts/simulation.py`.

Und im Modul-Docstring den Satz „neun Schritte, drei simulierte
Teilnehmerinnen" ersetzen durch: „alle Schritte des gewaehlten Skripts
(``--skript``), drei simulierte Teilnehmerinnen".

- [ ] **Schritt 7: `simulation/README.md` nachziehen**

Vier Stellen:

1. Zeilen 3–8: der Absatz „Drei simulierte Teilnehmerinnen arbeiten sich durch
   neun Schritte — … Phase 5 (Format & Rahmen) …" wird:

```markdown
Ein kompletter Workshop, gefahren gegen den echten Bot-Code und die echten
Modelle. Simulierte Teilnehmerinnen arbeiten sich durch die Schritte einer
Skriptliste (`simulation/skript.py`), danach bewertet ein Richter den Verlauf
nach einer festen Metrik.

**Drei Skriptlisten, und keine ist die eine.** `SCHRITTE` ist der Ablauf vom
05.09.2026 und die Messlatte der damaligen Laeufe: zehn Schritte, ohne
Phasenwechsel, mit einer Station 'Kernthema', die es seit dem 06.09. nicht
mehr gibt. `SCHRITTE_TAG2` faehrt die heutigen **sieben** Phasen aus
`phasen.PHASEN` — Begriffe · Fragen · Interviews · Setting, Figuren &
Geschichte · Schaerfung · Szenen als Geschichte · Feinschliff.
`SCHRITTE_BIRK` faehrt echtes Material. Der Schalter `--skript` waehlt;
`auto` (Vorgabe) waehlt wie bisher nach dem Set.
```

2. Zeile 66 (Tabelle „Die Teile"): `die neun Schritte: Ziel und Zielzustand je
   Schritt` → `die Schrittlisten: Ziel und Zielzustand je Schritt`.

3. Zeile 243: `Skript der **acht Phasen**` → `Skript der **sieben Phasen**`.

4. Im Aufrufblock (Zeilen 10–18) zwei Zeilen dazu:

```
$PY -m scripts.simulation --set 1 --seed 1 --skript tag2 --ohne-szene --bericht
$PY -m scripts.simulation --set 1 --seed 1 --skript tag2 --ohne-szene \
    --mutation festlegung_verloren        # Gegenpruefung, siehe unten
```

5. Ein neuer Abschnitt am Ende:

```markdown
## Gegenpruefung: faengt sie einen echten Fehler?

`simulation/mutation.py` baut einen der zwei belegten Dortmunder Fehler vom
06.09.2026 fuer die Dauer eines Laufs wieder ein — per Monkey-Patch aus
`simulation/` heraus, wie `lauf.einfaedig()` und `stoerung.py`. Kein
Produktivcode wird dafuer angefasst, und es gibt keine Weiche, die im Betrieb
umlegbar waere.

| `--mutation` | Der Fehler | Kennzahl, die anschlagen muss |
|---|---|---|
| `festlegung_verloren` | Es gibt kein Fach fuer eine Festlegung, die in kein Feld passt (Zustand vor `e56a892`). 22 von 42 Festlegungen gingen so verloren. | `festlegungsproben_erhalten` < `festlegungsproben` |
| `richtung_ohne_szenen` | Die gewaehlte Geschichte-Richtung verliert ihre Szenen, danach laeuft ein frischer Szenenfolge-Vorschlag (Zustand vor `3ae76ab`/`c9af872`). Aus 3 Szenen wurden 6. | `szenenfolge_nach_richtung` > 0 |

**Vor jedem bezahlten Mutationslauf** muss
`tests/test_simulation_mutation.py` gruen sein: er weist ohne Netz nach, dass
die Mutation den Fehler wirklich wieder erzeugt. Greift sie nicht, misst der
Lauf nichts und kostet trotzdem.

Das Ergebnis der ersten Gegenpruefung:
`docs/simulation-gegenpruefung-2026-09-30.md`.
```

- [ ] **Schritt 8: `tests/test_simulation_durchlauf.py` — nur die Zahl**

Zeile 1 (Docstring) und Zeile 183 (Testname) nennen „neun Schritte", es sind
zehn. Umbenennen auf `test_alle_schritte_erreichen_ihren_zielzustand` und im
Docstring die Zahl durch `len(skript.SCHRITTE)` ersetzen bzw. weglassen.
**Keine Logik aendern.**

- [ ] **Schritt 9: Alles gruen bekommen**

```bash
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_lauf.py tests/test_simulation_skript.py tests/test_simulation_durchlauf.py tests/test_simulation_knoepfe.py 2>&1 | tail -5
```

Erwartet: alles `passed`. `tests/test_simulation_knoepfe.py:176-181` liest
`SCHRITTE_TAG2` — der neue Schritt `festlegungen` hat `art="stimmen"` und
darf dort nichts brechen; tut er es doch, den dortigen Test mitlesen und
anpassen (er erwartet je `art='phase'`-Schritt eine Nummer).

- [ ] **Schritt 10: Den Zensus noch einmal fahren — die Praemissenpruefung muss leer laufen**

```bash
$PY -m scripts.simulation_abdeckung > /tmp/abdeckung-nachher.md
grep -A 20 "## Praemissenpruefung" /tmp/abdeckung-nachher.md
```

Erwartet: in der Spalte `Status` steht ueberall `bereinigt`. Steht irgendwo
noch `gefunden_falsch`, ist die Stelle nicht nachgezogen — nachziehen, nicht
die Behauptung aus `BEHAUPTUNGEN` streichen.

```bash
grep -A 12 '### `tag2`' /tmp/abdeckung-nachher.md
```

Erwartet: alle sieben Phasen `gefahren: ja`, Phase 4 mit den Schritten
`setting, festlegungen, geschichte`.

- [ ] **Schritt 11: Suite und Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add scripts/simulation.py simulation/lauf.py simulation/skript.py \
        simulation/README.md tests/test_simulation_lauf.py \
        tests/test_simulation_skript.py tests/test_simulation_durchlauf.py
git commit -m "$(cat <<'EOF'
Simulation auf den heutigen Phasenablauf -- und Hintergrundlaeufe abwarten

--skript tag2 faehrt SCHRITTE_TAG2 auch fuer die erfundenen Sets: nur damit
sind Setting, Geschichte und Schaerfung ueberhaupt im Lauf. --mutation baut
einen der zwei belegten Fehler fuer die Dauer eines Laufs wieder ein.

lauf.warte_auf_hintergrund wartet am Zugende auf die Threads, die DIESER Zug
gestartet hat: szenenfolge.starte_geschichte_szenen, schaerfung.starte,
sprachstil.starte und kurzgeschichte.starte sind in einfaedig() nicht
enthalten, ihre Wirkung landete bisher zu einem beliebigen Zeitpunkt -- unter
Umstaenden nach conn.close(). Abwarten statt vier Ersatzfunktionen: jede
traegt ihre eigene Sperrlogik, und es erfasst kuenftige Laeufe mit.

Neuer Schritt "festlegungen" mit drei Pruefsaetzen. Doku und Konstanten auf
sieben Phasen: PHASE_PROSA/PHASE_FEINSCHLIFF statt PHASE_SZENENTEXTE/
PHASE_DURCHLAUF, "Phase 5" im Titel von phase_mitte war Phase 4.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 8: Berichtsgeruest, Urteilskriterium und Budget (kostenlos)

**Das Urteil muss vor dem ersten bezahlten Lauf festgelegt sein** — sonst
wird es an die Zahlen angepasst, die herauskommen. Diese Aufgabe legt es fest
und traegt schon alles ein, was ohne Geld feststeht.

**Dateien:**
- Create: `docs/simulation-gegenpruefung-2026-09-30.md`

- [ ] **Schritt 1: Das Geruest schreiben**

```markdown
# Gegenpruefung der User-Simulation, 30.09.2026

**Frage** (Birk): prueft `simulation/` sinnvoll — faengt sie echte Fehler?

**Verfahren:** die zwei belegten Dortmunder Fehler vom 06.09.2026 per
Mutation wieder einbauen und messen, ob Kennzahlen oder Richter sie melden.
Mutation ueber `simulation/mutation.py` (Monkey-Patch aus `simulation/`
heraus), Produktivcode unangetastet.

**Basis:** `d8deb6c`, Suite 2768 passed / 1 skipped.

**PII:** keine Echtdaten. Gefahren wurden ausschliesslich die erfundenen Sets
1–3 (`simulation/interviews/`); `--set birk` und die tag1-Sets sind bewusst
NICHT gelaufen — ihr Material ist aus echten Interviews abgeleitet und hat am
US-Modell der Simulationsseite nichts zu suchen. In diesem Bericht stehen nur
Zahlen: keine Modellantwort, kein Chatverlauf, kein Belegzitat. Die
Laufberichte selbst sind gitignored.

---

## 0. Urteil

<!-- Nach Aufgabe 12 zu fuellen. Zwei Urteile, nicht eines. -->

**Urteil A — die Simulation, wie sie auf `d8deb6c` war:** …

**Urteil B — die Simulation nach dieser Karte:** …

### Das Kriterium, vor den Laeufen festgelegt

| Urteil | Bedingung |
|---|---|
| **prueft sinnvoll** | Beide Fehler werden im mutierten Lauf von mindestens einer **mechanischen** Kennzahl ausserhalb ihres Sollwerts gemeldet — und im unmutierten Lauf mit demselben Seed ist dieselbe Kennzahl im Soll. |
| **prueft teilweise** | Einer der beiden wird so gemeldet; der andere nur durch den deterministischen Nachweis (`tests/test_simulation_mutation.py`), weil der Lauf den Pfad nicht erreicht hat oder die Kennzahl in beiden Armen gleich stand. |
| **prueft nicht** | Keiner der beiden wird im Lauf gemeldet. |

Fuer **Urteil A** zaehlen ausschliesslich die Kennzahlen und Richternoten, die
es auf `d8deb6c` schon gab — die in Aufgabe 4–6 gebauten sind fuer A
ausdruecklich ausgenommen. Sonst beantwortete der Bericht die Frage nach dem
Zustand vor der Arbeit mit dem Ergebnis der Arbeit.

**Der Richter zaehlt fuer keines der beiden Urteile als Nachweis** — nur als
Plausibilitaetsprobe (Abschnitt 5). Grund: zwei Laeufe sind keine Verteilung,
und seine Noten schwanken zwischen zwei Laeufen ohne jede Aenderung
(`simulation/kennzahlen.py`-Kopf: „die Noten des Richters schwanken zwischen
zwei Laeufen, diese Zahlen nicht").

---

## 1. Abdeckung: welche Phase faehrt das Skript, und woran prueft es

Erzeugt mit `python -m scripts.simulation_abdeckung` — nicht abgeschrieben.

<!-- Aus /tmp/abdeckung-vorher.md uebernehmen: die drei Phasentabellen. -->

### Was der Verdacht traf und was nicht

<!-- Die Tabelle "Praemissenpruefung" aus /tmp/abdeckung-vorher.md, dazu die
     zwei Befunde, die der Verdacht nicht nennt. -->

### Nach der Korrektur

<!-- Die Praemissenpruefung aus /tmp/abdeckung-nachher.md: alles "bereinigt". -->

### Knoepfe und Modellwege im gefahrenen Lauf

<!-- python -m scripts.simulation_abdeckung --db <Basislauf-DB>, Abschnitte
     "Knopfarten im gefahrenen Lauf" und "Modellwege im gefahrenen Lauf". -->

---

## 2. Fehler 1: 22 von 42 Festlegungen verloren

**Quelle:** `docs/analyse-phase4-datenverlust-2026-09-06.md` § 0, § 2.7, § 3.
**Fix:** `e56a892`, `bbe301e`, `36030ff` (07.09.2026).
**Mutiert wurde** die Hauptursache — es gibt kein Fach fuer eine Festlegung,
die in kein Feld passt (`repo.schreibe_festlegung` → `None`). Warum diese und
nicht die Menuezeile oder die Platzhalterfiguren: siehe Abschnitt 6.

**Deterministischer Nachweis, dass die Mutation greift:**
`tests/test_simulation_mutation.py::test_mutiert_schreibt_auch_der_erkenner_nichts`
— <!-- passed/failed --> .

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? |
|---|---|---|---|---|
| `festlegungen` | | | > 0 | |
| `festlegungsproben_erhalten` | | | alle | |
| `festlegungsproben_nur_journal` | | | 0 | |
| `festlegungsproben_nirgends` | | | 0 | |
| Schritt `festlegungen` gescheitert | | | nein | |
| **vorher vorhandene Kennzahlen** | | | | |
| `zustimmungen_gespeichert` | | | alle | |
| `behauptete_schreibvorgaenge` | | | 0 | |
| `journal_je_art` (`vorgeschlagen`) | | | – | |
| `nachrichten_je_festlegung_median` | | | <= 2 | |
| `arbeitsstand_vollstaendig` | | | voll | |

**Protokoll:** gefunden / nicht gefunden — woran:

<!-- Ein Absatz. "Woran" heisst: welche Kennzahl, welcher Wert, und ob eine
     der VORHER vorhandenen sich mitbewegt hat. -->

---

## 3. Fehler 2: aus 3 Szenen wurden 6

**Quelle:** `docs/analyse-phase5-chaos-2026-09-06.md` § 4, § B.
**Fix:** `3ae76ab`, `c9af872` (30.09.2026); davor schon
`repo.gleiche_szenenfolge_ab` (06.09.2026).
**Mutiert wurde** `szenenfolge.szenen_der_richtung` → `[]`.

**Zu beachten bei der Deutung:** seit `repo.gleiche_szenenfolge_ab` entfernt
ein Szenenfolge-Lauf keine Szene mehr. Der Schaden hat heute eine andere
Gestalt als am 06.09.: nicht „drei weg, sechs neu", sondern „Titel 1–3
ueberschrieben, 4–6 dazu" (`titel` steht nicht in
`repo.GESCHUETZTE_SZENENFELDER`) — plus 110 s Wartezeit. Die Kennzahl misst
beide Gestalten.

**Deterministischer Nachweis:**
`tests/test_simulation_mutation.py::test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf`
— <!-- passed/failed --> .

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? |
|---|---|---|---|---|
| `szenenfolge_nach_richtung` | | | 0 | |
| `szenen_aus_richtung` | | | ja | |
| `szenen_neuaufbauten` | | | 0 | |
| `szenen_form_verloren` | | | 0 | |
| `szenen_aktiv` | | | – | |
| `szenenfolge_laeufe` | | | – | |
| **vorher vorhandene Kennzahlen** | | | | |
| `szenen_gesamt` (`formlage`) | | | – | |
| `form_bestaetigt` / `form_gesetzt_ohne_vorschlag` | | | 0 gesetzt | |
| `rahmen_ueberschrieben` | | | 0 | |
| `dauer_s`, `chf_bot` | | | – | |
| `vorfaelle` | | | – | |

**Protokoll:** gefunden / nicht gefunden — woran:

<!-- Ein Absatz. -->

---

## 4. Die Laeufe

| # | Set | Seed | Skript | Schalter | Mutation | Dauer | `chf_bot` | `phase_erreicht` |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | tag2 | `--ohne-szene` | – | | | |
| 2 | 1 | 2 | tag2 | `--ohne-szene` | – | | | |
| 3 | 1 | 1 | tag2 | `--ohne-szene` | `festlegung_verloren` | | | |
| 4 | 1 | 1 | tag2 | `--ohne-szene` | `richtung_ohne_szenen` | | | |

Summe: <!-- CHF --> von 10 CHF freigegeben.

---

## 5. Plausibilitaet des Richters

Vorher festgelegt: die **Streuung** ist `|noten_summe(Lauf 1) −
noten_summe(Lauf 2)|` — zwei unmutierte Laeufe, verschiedene Seeds, sonst
alles gleich. „Bewertet schlechter" heisst: die Notensumme des mutierten
Laufs liegt **unter** der des Basislaufs mit demselben Seed, **und** die
Differenz ist groesser als diese Streuung. Alles innerhalb der Streuung ist
nicht deutbar und wird so benannt.

| Grösse | Lauf 1 (Seed 1) | Lauf 2 (Seed 2) | Streuung | Lauf 3 (mut. 1) | Lauf 4 (mut. 2) |
|---|---|---|---|---|---|
| `noten_summe` | | | | | |
| `noten_median` | | | | | |
| `geht_auf_gesagtes_ein` (Mittel) | | | | | |
| `bietet_an_statt_vorzuschreiben` | | | | | |
| `phase_transparent` | | | | | |
| `korrektur_angenommen` | | | | | |
| nicht bewertete Abschnitte | | | | | |

Je Abschnitt, Lauf 1 gegen Lauf 3 und Lauf 4:

<!-- Tabelle Abschnitt x Notensumme, aus verlauf.jsonl bzw. den
     Berichtsdateien. Keine Begruendungstexte -- die sind Modellausgabe. -->

**Urteil zur Plausibilitaet:** …

---

## 6. Was diese Karte nicht gemessen hat

- **Ursache (b) von Fehler 1** — „eine Menuezeile ist keine Geschichte"
  (`3290d70`): als eigene Mutation nicht gefahren, weil Fehler 2 dieselbe
  Wurzel praeziser trifft.
- **Ursache (c) von Fehler 1** — Platzhalterfiguren, die beim Nachbenennen
  eine zweite Zeile anlegen (`repo.fuehre_figur_zusammen`): ohne Modell nicht
  zuverlaessig ausloesbar, ob eine simulierte Stimme nachbenennt, entscheidet
  das Gespraechsmodell. **Gehoert in eine eigene Karte.**
- **Der Szenenweg** (`--ohne-szene` in allen vier Laeufen): kein Szenentext
  ist geschrieben worden, also sagt dieser Bericht nichts ueber
  `szene_stimmt_zur_planung`, `stimmen_unterscheidbar`, `form_eingehalten`
  oder `exposition_erfuellt`. Beide Fehler liegen vor dem Schreiben.
- **Die Phasen 6 und 7** in der Tiefe: der Lauf erreicht sie, schreibt aber
  nichts.
- **`--set birk` und die tag1-Sets:** aus Datenschutzgruenden nicht gefahren.
- **`--parallel`, `--stoerung`, `--pause`, `--fenster-klein`:** nicht Teil
  dieser Frage.

---

## 7. Was daraus folgt

<!-- Nach Aufgabe 12: hoechstens fuenf Punkte, jeder mit einer Datei oder
     einem Kennzahlnamen. Keine Wunschliste. -->
```

- [ ] **Schritt 2: Budget und Abbruch festlegen (steht im Plan, nicht im Bericht)**

Gerechnet aus `simulation/berichte/verlauf.jsonl` (Aufgabe 0 Schritt 5):
Set-Laeufe auf dem kurzen Skript 0,25–0,41 CHF (Median 0,29), Laeufe auf
`SCHRITTE_TAG2` 0,33–0,64 CHF (Median 0,34; der Wert 0,636 gehoert zum
`regie`-Lauf mit 1848 s und ist ein Ausreisser).

Unsere Laeufe sind `SCHRITTE_TAG2` **mit** fuenf Interviews und **drei**
Stimmen (die tag1-Laeufe hatten zwei Interviews und eine Stimme), dafuer
**ohne** Szenenlauf. Erwartung: **0,55 CHF je Lauf**.

| | |
|---|---|
| Erwartung je Lauf | 0,55 CHF |
| Vier Laeufe | 2,20 CHF |
| Reserve (bis zu zwei Wiederholungen) | 1,10 CHF |
| **Erwartete Summe** | **3,30 CHF** von 10 freigegeben |
| **Abbruch je Lauf** | `chf_bot > 1.10` (das Doppelte der Erwartung) |
| **Abbruch gesamt** | Summe der `chf_bot` > 8,00 CHF |

- [ ] **Schritt 3: Commit**

```bash
git add docs/simulation-gegenpruefung-2026-09-30.md
git commit -m "$(cat <<'EOF'
Berichtsgeruest der Gegenpruefung -- Urteilskriterium vor den Laeufen

Zwei Urteile, nicht eines: A fuer die Simulation, wie sie auf d8deb6c war
(nur die damals vorhandenen Kennzahlen zaehlen), B fuer die nach dieser
Karte. Sonst beantwortete der Bericht die Frage nach dem Zustand vor der
Arbeit mit dem Ergebnis der Arbeit. Der Richter zaehlt fuer keines der Urteile
als Nachweis -- zwei Laeufe sind keine Verteilung.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Die Laufmatrix (gilt fuer die Aufgaben 9–11)

Gleicher Seed je Vergleich, nur die Mutation unterscheidet sich. Set 1 in
allen vier Laeufen — die Besetzung ist fest (`stimmen.personen`), der Seed
variiert nur, wer wann spricht.

| # | Aufgabe | Set | Seed | Skript | Mutation | Zweck |
|---|---|---|---|---|---|---|
| 1 | 9 | 1 | 1 | tag2 | – | Basis, Vergleichsarm fuer beide Mutationen |
| 2 | 9 | 1 | 2 | tag2 | – | **nur** fuer die Streuung der Richternoten |
| 3 | 10 | 1 | 1 | tag2 | `festlegung_verloren` | Fehler 1 |
| 4 | 11 | 1 | 1 | tag2 | `richtung_ohne_szenen` | Fehler 2 |

**`--ohne-szene` in allen vier.** Begruendung, weil sie nicht selbstverstaendlich
ist: Fehler 2 betrifft die **Szenenfolge**, nicht den Szenentext. Er wirkt
vollstaendig im Schritt `geschichte` — die Richtung wird gedrueckt, und
entweder traegt sie ihre Szenen mit oder ein Lauf erfindet sie neu. Beides ist
messbar, ohne dass eine Szene geschrieben wird. Der Szenenlauf ist der
teuerste Einzelposten (Reasoning, 2–4 Minuten) und wuerde in allen vier
Laeufen dasselbe kosten, ohne eine der beiden Fragen zu beantworten. Was
dadurch ungemessen bleibt, steht in Abschnitt 6 des Berichts.

**Verboten:** `--set birk`, `--set tag1-*`, `--set regie`, `--parallel`,
`--alle`, `--echte-db betrieb/...`.

**Das gemeinsame Vorspiel jedes Laufs** (wird in jeder der drei Aufgaben
wiederholt, damit niemand es ueberspringt):

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3

# 1. Der deterministische Nachweis MUSS gruen sein -- sonst misst der Lauf nichts.
$PY -m pytest -q -p no:cacheprovider tests/test_simulation_mutation.py 2>&1 | tail -3

# 2. Env der Gruppe laden. Kein Wert davon wird notiert oder weitergegeben.
set -a; . ./betrieb/gruppe1.env; set +a
```

Erwartet bei 1.: `12 passed`. Ist er rot, **keinen Lauf starten**.

---

## Aufgabe 9: Die zwei Basislaeufe — **KOSTET GELD** (~1,10 CHF)

**Dateien:** keine im Repo ausser `simulation/berichte/verlauf.jsonl` (waechst
um zwei Zeilen).

- [ ] **Schritt 1: Vorspiel (siehe oben)**

- [ ] **Schritt 2: Basislauf 1, Seed 1**

```bash
rm -f /tmp/gp-basis-1.db
$PY -m scripts.simulation --set 1 --seed 1 --skript tag2 --ohne-szene \
    --bericht --echte-db /tmp/gp-basis-1.db 2>&1 | tail -80
```

Erwartet: die Kopfzeile `=== set1, Seed 1, 5 Interviews, 14 Schritte ===`
(14 = `SCHRITTE_TAG2` ohne den Szenen-Schritt, mit `festlegungen`), dann je
Schritt `-> <Titel>` und `erreicht`/`GESCHEITERT`, am Ende die
Kennzahlentabelle mit den neuen Zeilen „Festlegungsproben erhalten" und
„Szenenfolge-Lauf nach der Richtungswahl". Dauer 5–15 Minuten.

**`--echte-db` zeigt hier auf `/tmp`, nicht auf `betrieb/soap.db`.** Grund:
die Wegwerf-Datenbank wird am Laufende geloescht, und der Abdeckungszensus
(Aufgabe 12) braucht sie noch. Die Datei ist frisch, `db.initialisiere` legt
das Schema an.

- [ ] **Schritt 3: Kosten pruefen, Abbruchkriterium**

```bash
$PY - <<'PY'
import json
z = [json.loads(l) for l in open("simulation/berichte/verlauf.jsonl") if l.strip()]
letzte = z[-1]
print(letzte["kennung"], "mutation=", letzte.get("mutation", ""),
      "chf_bot=", letzte["chf_bot"], "dauer_s=", letzte["dauer_s"])
if letzte["chf_bot"] > 1.10:
    print("ABBRUCH: ueber dem Doppelten der Erwartung (0.55 CHF)")
PY
```

Meldet es `ABBRUCH`: **keinen weiteren Lauf starten.** Stattdessen in Aufgabe 12
den Bericht mit dem einen Lauf fuellen, die Kostenzeile und den Abbruch
protokollieren und das Urteil ausdruecklich auf die deterministischen
Nachweise stuetzen.

- [ ] **Schritt 4: Basislauf 2, Seed 2 — nur fuer die Streuung**

```bash
rm -f /tmp/gp-basis-2.db
$PY -m scripts.simulation --set 1 --seed 2 --skript tag2 --ohne-szene \
    --bericht --echte-db /tmp/gp-basis-2.db 2>&1 | tail -60
```

Dieser Lauf hat **nur** den Zweck, die Streuung der Richternoten zu
bestimmen (Abschnitt 5 des Berichts). Ohne ihn ist eine Notendifferenz nicht
deutbar.

- [ ] **Schritt 5: Kosten pruefen** (Kommando aus Schritt 3 wiederholen)

- [ ] **Schritt 6: Die zwei Zahlenreihen sichern**

Die Berichtsdateien unter `simulation/berichte/<datum>-set1-{1,2}.md` sind
gitignored und bleiben liegen. Fuer Aufgabe 12 die **Zahlen** herausziehen:

```bash
$PY - <<'PY'
import json
SCHLUESSEL = (
    "kennung", "mutation", "seed", "chf_bot", "dauer_s", "aufrufe",
    "phase_erreicht", "phase_erreicht_name", "schritte_gescheitert",
    "noten_summe", "noten_median",
    "festlegungen", "festlegungen_je_bereich", "festlegungsproben",
    "festlegungsproben_erhalten", "festlegungsproben_nur_journal",
    "festlegungsproben_nirgends",
    "szenen_aktiv", "szenen_ersetzt", "szenen_neuaufbauten",
    "szenen_form_verloren", "szenenfolge_laeufe", "kurzgeschichte_laeufe",
    "szenenfolge_nach_richtung", "szenen_aus_richtung",
    "zustimmungen", "zustimmungen_gespeichert", "behauptete_schreibvorgaenge",
    "nachrichten_je_festlegung_median", "arbeitsstand_vollstaendig",
    "journal_je_art", "szenen_gesamt", "form_bestaetigt",
    "form_gesetzt_ohne_vorschlag", "rahmen_ueberschrieben",
    "knoepfe_angeboten", "knoepfe_gedrueckt", "phasenwechsel_proaktiv",
    "phasenwechsel_selbst", "vorfaelle", "notausgaenge",
)
z = [json.loads(l) for l in open("simulation/berichte/verlauf.jsonl") if l.strip()]
for zeile in z[-2:]:
    print("---")
    for s in SCHLUESSEL:
        print(f"{s}: {zeile.get(s)!r}")
PY
```

Die Ausgabe in eine Notiz unter `/tmp/gp-zahlen.txt` schreiben (`… | tee -a
/tmp/gp-zahlen.txt`). **Nicht ins Repo.**

- [ ] **Schritt 7: Kein Commit**

`simulation/berichte/verlauf.jsonl` ist die eine nicht-gitignorierte Datei,
die waechst. Sie wird **zusammen mit dem Bericht** in Aufgabe 12 committet —
ein eigener Commit je Lauf brachte nichts, und die Laufreihenfolge steht
ohnehin in der Datei.

```bash
git status --short
```

Erwartet: `M simulation/berichte/verlauf.jsonl` und sonst nichts ausser den
`.cc-*`-Arbeiterdateien.

---

## Aufgabe 10: Mutationslauf 1 — Festlegungen — **KOSTET GELD** (~0,55 CHF)

- [ ] **Schritt 1: Vorspiel (siehe Laufmatrix)**

- [ ] **Schritt 2: Den Nachweis fuer genau diese Mutation einzeln fahren**

```bash
$PY -m pytest -q -p no:cacheprovider \
    tests/test_simulation_mutation.py -k festlegung -v 2>&1 | tail -10
```

Erwartet: alle `PASSED`, darunter
`test_mutiert_schreibt_auch_der_erkenner_nichts`. **Rot heisst: kein Lauf.**

- [ ] **Schritt 3: Der Lauf**

```bash
rm -f /tmp/gp-mut1.db
$PY -m scripts.simulation --set 1 --seed 1 --skript tag2 --ohne-szene \
    --mutation festlegung_verloren \
    --bericht --echte-db /tmp/gp-mut1.db 2>&1 | tail -80
```

Erwartet in der Ausgabe: `!! MUTATION AKTIV: festlegung_verloren` samt dem
Beschreibungssatz, danach der uebliche Lauf. Der Mischungsname ist
`set1-festlegung_verloren`, die Berichtsdatei kollidiert also nicht mit der
des Basislaufs.

**Erwartete Wirkung** (so soll es im Bericht stehen, wenn es eintritt):
`festlegungen == 0`, `festlegungsproben_erhalten < 3`, der Schritt
`festlegungen` in `schritte_gescheitert`.

**Wenn `festlegungsproben_erhalten` auch im Basislauf unter 3 lag**, ist die
Kennzahl in diesem Lauf nicht unterscheidend — dann ist der Befund „der Bot
hat die Pruefsaetze schon ohne Mutation nicht dauerhaft gespeichert", und das
ist **ein eigener, ernster Befund**, kein Fehlschlag der Gegenpruefung. So
gehoert er in Abschnitt 2 des Berichts, mit beiden Zahlen nebeneinander.

- [ ] **Schritt 4: Kosten pruefen** (Kommando aus Aufgabe 9 Schritt 3)

- [ ] **Schritt 5: Zahlen sichern** (Kommando aus Aufgabe 9 Schritt 6, letzte
      Zeile statt der letzten zwei — `z[-1:]`)

- [ ] **Schritt 6: Pruefen, dass die Mutation wirklich zurueckgenommen ist**

```bash
$PY - <<'PY'
from interview_theater import repo
from simulation import mutation
print("schreibe_festlegung ist:", repo.schreibe_festlegung.__name__)
print("Mutation eingebaut:", bool(getattr(mutation, "_ORIGINAL", {})))
PY
git diff --stat d8deb6c -- interview_theater/
```

Erwartet: der Name **nicht** `_ohne_festlegung`, `Mutation eingebaut: False`,
und `git diff` gibt **nichts** aus. Der Kontextmanager stellt im `finally`
zurueck; dieser Schritt ist die Gegenprobe, weil der Prozess dazwischen
abgebrochen sein koennte.

---

## Aufgabe 11: Mutationslauf 2 — Szenenfolge — **KOSTET GELD** (~0,55 CHF)

- [ ] **Schritt 1: Vorspiel (siehe Laufmatrix)**

- [ ] **Schritt 2: Den Nachweis fuer genau diese Mutation einzeln fahren**

```bash
$PY -m pytest -q -p no:cacheprovider \
    tests/test_simulation_mutation.py -k richtung -v 2>&1 | tail -10
```

Erwartet: alle `PASSED`, darunter
`test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf` und
`test_mutiert_bleibt_die_reine_formwahl_die_formwahl`.

- [ ] **Schritt 3: Der Lauf**

```bash
rm -f /tmp/gp-mut2.db
$PY -m scripts.simulation --set 1 --seed 1 --skript tag2 --ohne-szene \
    --mutation richtung_ohne_szenen \
    --bericht --echte-db /tmp/gp-mut2.db 2>&1 | tail -80
```

Erwartet: `!! MUTATION AKTIV: richtung_ohne_szenen`. Dieser Lauf ist
**laenger** als die anderen: die Mutation loest einen Szenenfolge-Lauf aus
(gemessen 110 s am 06.09.), und `lauf.warte_auf_hintergrund` wartet ihn jetzt
ab. Rechne mit 2–4 Minuten mehr und entsprechend etwas hoeheren Kosten — die
Grenze bleibt 1,10 CHF.

**Erwartete Wirkung:** `szenenfolge_nach_richtung >= 1`,
`szenen_aus_richtung == False`, `szenenfolge_laeufe` um 1 hoeher als im
Basislauf.

**Die eine Voraussetzung, die der Lauf selbst nicht garantiert:** die Gruppe
muss ueberhaupt einen **Richtungs-Knopf** gedrueckt haben — sonst gibt es
keine Richtungswahl, und beide Arme stehen bei 0. Das ist mechanisch
nachpruefbar:

```bash
$PY - <<'PY'
import sqlite3
for name, pfad in (("Basis", "/tmp/gp-basis-1.db"), ("mutiert", "/tmp/gp-mut2.db")):
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    zeilen = conn.execute(
        "SELECT art, count(*) AS n, "
        "sum(CASE WHEN benutzt_am IS NOT NULL THEN 1 ELSE 0 END) AS gedrueckt "
        "FROM knopf WHERE art LIKE 'geschichte%' GROUP BY art"
    ).fetchall()
    print(name, [(z["art"], z["n"], z["gedrueckt"]) for z in zeilen])
PY
```

Steht bei `geschichte_speichern` in **beiden** `gedrueckt = 0`, hat der Lauf
den Pfad nicht erreicht: dann lautet das Protokoll in Abschnitt 3
**„nicht gefunden — der Lauf erreichte die Richtungswahl nicht, gedrueckt
wurden 0 von N Richtungs-Knoepfen"**, und Fehler 2 zaehlt fuer das Urteil nur
ueber den deterministischen Nachweis. **Einen zweiten Lauf mit anderem Seed
darf der Umsetzer dafuer fahren** (einer, aus der Reserve, `--seed 3` in
beiden Armen) — mehr nicht, und nur, wenn die Summe danach unter 8 CHF bleibt.

- [ ] **Schritt 4: Kosten pruefen** (Kommando aus Aufgabe 9 Schritt 3)

- [ ] **Schritt 5: Zahlen sichern** (Kommando aus Aufgabe 9 Schritt 6, `z[-1:]`)

- [ ] **Schritt 6: Mutation zurueckgenommen pruefen**

```bash
$PY - <<'PY'
from interview_theater import szenenfolge
from simulation import mutation
print("szenen_der_richtung ist:", szenenfolge.szenen_der_richtung.__name__)
print("Mutation eingebaut:", bool(getattr(mutation, "_ORIGINAL", {})))
print("Probe:", szenenfolge.szenen_der_richtung(
    "Nacht am Kanal — Bogen. Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis."))
PY
git diff --stat d8deb6c -- interview_theater/
```

Erwartet: Name **nicht** `_keine_szenen_in_der_richtung`,
`Mutation eingebaut: False`, die Probe liefert zwei Tupel, `git diff` leer.

---

## Aufgabe 12: Den Bericht fuellen und das Urteil sprechen (kostenlos)

**Dateien:**
- Modify: `docs/simulation-gegenpruefung-2026-09-30.md`
- Modify: `simulation/berichte/verlauf.jsonl` (waechst durch die Laeufe — mit committen)

- [ ] **Schritt 1: Abschnitt 1 (Abdeckung) fuellen**

Die drei Phasentabellen aus `/tmp/abdeckung-vorher.md`, die
Praemissenpruefung aus **beiden** Zensus-Laeufen (vorher/nachher), und dann:

```bash
$PY -m scripts.simulation_abdeckung --db /tmp/gp-basis-1.db \
  | sed -n '/## Knopfarten im gefahrenen Lauf/,$p'
```

Das liefert die zwei DB-Abschnitte. Sie zeigen, welche Knopfarten der Lauf
angeboten und welche er gedrueckt hat — die eigentliche Antwort auf „welche
Knoepfe faehrt `skript.py` tatsaechlich". Dazu zwei Saetze: wie viele der 83
`ART_*`-Konstanten ueberhaupt vorkamen, und welche Modellwege liefen.

- [ ] **Schritt 2: Abschnitte 2 und 3 fuellen**

Aus `/tmp/gp-zahlen.txt` je Kennzahl die vier Werte in die Tabellen. Die
Spalte `erkannt?` bekommt genau drei moegliche Eintraege:
`ja (Soll verletzt, Basis im Soll)`, `nein (beide gleich)`,
`nicht messbar (Pfad nicht erreicht)`.

Das **Protokoll je Fehler** in einem Absatz, und zwar in dieser Form:

> **Fehler 1: gefunden / nicht gefunden / nicht messbar.** Woran: `<Kennzahl>`
> stand im Basislauf bei `<Wert>` (Soll `<Soll>`) und im mutierten Lauf bei
> `<Wert>`. Von den auf `d8deb6c` vorhandenen Kennzahlen bewegte sich
> `<keine | Liste>`.

Der letzte Satz ist der wichtigste — er entscheidet Urteil A.

- [ ] **Schritt 3: Abschnitt 4 (Laeufe) und Kostensumme fuellen**

```bash
$PY - <<'PY'
import json
z = [json.loads(l) for l in open("simulation/berichte/verlauf.jsonl") if l.strip()]
meine = [x for x in z if x.get("mutation") is not None
         and x["mischung"].startswith("set1")][-4:]
summe = 0.0
for x in meine:
    summe += x["chf_bot"]
    print(f"{x['kennung']:34} mut={x.get('mutation',''):22} "
          f"{x['chf_bot']:.4f} CHF  {x['dauer_s']:.0f} s  "
          f"Phase {x['phase_erreicht']}")
print(f"Summe: {summe:.4f} CHF von 10 freigegeben")
PY
```

**Achtung bei der Auswahl:** `verlauf.jsonl` enthaelt 14 aeltere Zeilen. Der
Filter oben nimmt die letzten vier `set1`-Zeilen; pruefe an den `kennung`- und
`git`-Feldern, dass es die eigenen sind, und korrigiere den Filter sonst auf
`x["git"] == <eigener HEAD>`.

- [ ] **Schritt 4: Abschnitt 5 (Richter) fuellen**

```bash
$PY - <<'PY'
import json, statistics
from simulation import richter
z = [json.loads(l) for l in open("simulation/berichte/verlauf.jsonl") if l.strip()]
meine = [x for x in z if x["mischung"].startswith("set1")][-4:]
for x in meine:
    print(f"{x['kennung']:34} mut={x.get('mutation',''):22} "
          f"summe={x['noten_summe']} median={x['noten_median']}")
basis = [x for x in meine if not x.get("mutation")]
if len(basis) == 2:
    streuung = abs(basis[0]["noten_summe"] - basis[1]["noten_summe"])
    print(f"Streuung der zwei Basislaeufe: {streuung}")
    for x in meine:
        if x.get("mutation"):
            delta = basis[0]["noten_summe"] - x["noten_summe"]
            print(f"{x['mutation']}: Delta {delta} -> "
                  f"{'deutbar' if delta > streuung else 'NICHT deutbar'}")
PY
```

Die Noten **je Kriterium und je Abschnitt** stehen nicht in `verlauf.jsonl`,
sondern in den Berichtsdateien unter `simulation/berichte/`. Dort im
Abschnitt „Noten des Richters" ablesen und in die zweite Tabelle uebertragen
— **nur Zahlen**, keine `satz`/`begruendung`-Felder (Modellausgabe).

`noten_summe` kann `None` sein, wenn ein Abschnitt nicht bewertet wurde
(`richter._leeres_urteil`). Dann steht in der Tabelle `–` und die Zeile
„nicht bewertete Abschnitte" traegt die Zahl.

- [ ] **Schritt 5: Die zwei Urteile sprechen**

Nach dem Kriterium aus Aufgabe 8, wortwoertlich und ohne Nachverhandeln.
Erwartung des Planers — **nicht** ins Urteil uebernehmen, nur als Warnung,
falls das Ergebnis genau so aussieht: Urteil A wird voraussichtlich
**„prueft nicht"** oder **„prueft teilweise"** lauten, weil auf `d8deb6c`
weder `festlegung` noch der Szenenfolge-Lauf in irgendeiner Kennzahl vorkommen
und die Set-Laeufe die betroffenen Phasen nicht einmal anfahren. Kommt etwas
anderes heraus, ist das die interessantere Nachricht — dann steht **im
Bericht**, welche vorhandene Kennzahl sich bewegt hat.

- [ ] **Schritt 6: Abschnitt 7 („Was daraus folgt")**

Hoechstens fuenf Punkte, jeder mit einer Datei oder einem Kennzahlnamen. Wenn
sich in den Laeufen ein Befund gezeigt hat, der **nicht** zu dieser Karte
gehoert (etwa: der Bot speichert die Pruefsaetze auch unmutiert nicht), steht
er hier als **eigene Karte** — nicht als Nebenbeifix.

- [ ] **Schritt 7: Pruefen, dass keine Modellausgabe im Bericht steht**

```bash
grep -niE "^> |begruendung|satz:|Bot:|\[S[0-9]" docs/simulation-gegenpruefung-2026-09-30.md
```

Erwartet: nur die drei Protokollabsaetze in der `>`-Form aus Schritt 2 — kein
`Bot:`, kein `[S7]`, kein `begruendung`. Findet sich etwas anderes, loeschen.

```bash
grep -c "" docs/simulation-gegenpruefung-2026-09-30.md
```

Zur Orientierung: unter 300 Zeilen. Ein Bericht, den niemand liest, ist keiner.

- [ ] **Schritt 8: Commit**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add docs/simulation-gegenpruefung-2026-09-30.md simulation/berichte/verlauf.jsonl
git commit -m "$(cat <<'EOF'
Ergebnisbericht der Gegenpruefung: Abdeckung, Protokoll je Fehler, Urteil

Vier Laeufe (Set 1, Seeds 1/2 Basis, Seed 1 je Mutation, alle --skript tag2
--ohne-szene). Zwei Urteile: eines fuer die Simulation, wie sie auf d8deb6c
war, eines fuer die nach dieser Karte. Nur Zahlen im Bericht -- die
Laufberichte bleiben gitignored.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 13: Abschluss — Mutationen weg, Suite gruen, AGENTS.md angeglichen (kostenlos)

**Dateien:**
- Modify: `AGENTS.md` (nur der Abschnitt „Simulation" und die Zeile zu
  `scripts/`)

- [ ] **Schritt 1: Beweisen, dass keine Mutation im Code steht**

```bash
git status --short
git diff --stat d8deb6c -- interview_theater/
grep -rn "mutation\|MUTATION" interview_theater/ | grep -v "\.pyc"
```

Erwartet:
- `git status --short`: **leer** ausser `.cc-run-t_a4ae02fa.err`,
  `.cc-run-t_a4ae02fa.json`, `.cc-settings.json`,
  `.superpowers-brief-t_a4ae02fa.md` (Arbeiterdateien, nie committen).
- `git diff --stat d8deb6c -- interview_theater/`: **keine Ausgabe.**
- Der `grep`: **keine Treffer.** Findet er etwas, ist eine Mutationsweiche im
  Produktivcode gelandet — entfernen, dann diesen Schritt wiederholen.

- [ ] **Schritt 2: Die Suite ein letztes Mal, wartend**

```bash
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Erwartet: `passed` >= 2768 + alle neuen Tests (geplant: 13 + 12 + 8 + 8 + 5 +
4 + 7 + 3 ≈ 60, also rund `2828 passed, 1 skipped`). Die genaue Zahl ist
nicht vorhersagbar — **gleich oder hoeher als die Basis** ist das Kriterium,
und `0 failed` ist Pflicht.

Faellt genau `tests/test_aufnahme.py::test_fertig_in_der_sprachnachricht_beendet_das_interview`,
ist das die aus dem A5-Plan bekannte Flakiness: einzeln nachfahren
(`$PY -m pytest -q -p no:cacheprovider tests/test_aufnahme.py`), und erst wenn
er auch dort rot ist, gehoert er zur Umsetzung. Nicht reparieren — eigene
Karte.

- [ ] **Schritt 3: AGENTS.md angleichen**

Der Abschnitt „Simulation: ein ganzer Workshop gegen die echten Modelle"
sagt heute „Drei simulierte Teilnehmerinnen arbeiten sich durch neun
Schritte: Begriffe, Fragen, fünf Interviews, Kernthema, Figuren, Phase 5, eine
Szene, eine Korrektur, `/stand`" — und der Abschnitt „Starten und testen"
zweimal „alle acht Phasen" bzw. „alle Phasen". Weil sich **Schritte und
Kennzahlen geaendert haben**, wird angeglichen; mehr nicht.

Drei Aenderungen, jede minimal:

1. Der Satz mit den neun Schritten wird:

```markdown
Simulierte Teilnehmerinnen arbeiten sich durch die Schritte einer
Skriptliste. `skript.SCHRITTE` ist der Ablauf vom 05.09.2026 und die
Messlatte der damaligen Verlaufszeilen (zehn Schritte, keine Phasenwechsel);
`skript.SCHRITTE_TAG2` faehrt die heutigen **sieben** Phasen, und seit dem
30.09.2026 waehlt der Schalter `--skript tag2` es auch fuer die erfundenen
Sets 1–3 — vorher war es an `--set tag1-*` gebunden, und damit fuhr kein
erfundenes Set die Phasen 4 bis 7 ueberhaupt an.
```

2. In der Liste „Was sie misst" hinter `zitat_erfunden` (Soll 0) ergaenzen:

```markdown
Dazu seit dem 30.09.2026 die zwei Kennzahlen der Gegenpruefung, beide
mechanisch: **`festlegungsproben_erhalten`** (Soll: alle — von drei
Pruefsaetzen, die in kein Arbeitsstandfeld passen, muss jeder dauerhaft
liegen; das Journal zaehlt dabei **nicht**, es wird auf acht Zeilen gekappt)
und **`szenenfolge_nach_richtung`** (Soll 0 — nach einer gedrueckten
Geschichte-Richtung darf kein frischer Szenenfolge-Vorschlag laufen, er
ueberschreibt die Titel der Gruppe und kostet 110 s). Beide sind entstanden,
weil die Simulation die zwei belegten Dortmunder Fehler vom 06.09.2026 vorher
**nicht** gefunden hat: `docs/simulation-gegenpruefung-2026-09-30.md`.
`simulation/mutation.py` baut sie auf Knopfdruck wieder ein
(`--mutation`) — per Monkey-Patch aus `simulation/` heraus, kein
Produktivcode und keine Weiche darin; `tests/test_simulation_mutation.py`
haelt fest, dass die Mutation den Fehler wirklich erzeugt, und muss vor jedem
bezahlten Lauf gruen sein.
```

3. In der Liste der `scripts/` (der Absatz mit `scripts/loeschen.py` …)
   ergaenzen:

```markdown
`scripts/simulation_abdeckung.py` erzeugt die Abdeckungstabelle der
Simulation aus dem Code (Phasen aus `phasen.PHASEN`, Schritte aus den drei
`skript`-Listen, Pruefung aus `schritt.fertig.__name__`) und prueft jede
Behauptung der Simulations-Doku dagegen — kein Modell, kein Netz, keine
Kosten.
```

**Nicht** anfassen: die Phasenliste, die Fallen, die bindenden
Entwurfsentscheidungen. Es hat sich nichts am Bot geaendert.

- [ ] **Schritt 4: Pruefen, dass AGENTS.md keine Zahl mehr behauptet, die falsch ist**

```bash
grep -n "neun Schritte\|acht Phasen" AGENTS.md
```

Erwartet: keine Treffer, oder nur solche im historischen Rueckblick („05.09.
nachts wurden aus sieben Phasen acht") — den Kontext lesen, historische
Saetze bleiben stehen.

- [ ] **Schritt 5: Commit**

```bash
git add AGENTS.md
git commit -m "$(cat <<'EOF'
AGENTS.md: Simulation angeglichen -- Skriptlisten, --skript, zwei Kennzahlen

Nur was sich geaendert hat: die neun Schritte waren zehn, SCHRITTE_TAG2
faehrt sieben Phasen und ist ueber --skript auch fuer die erfundenen Sets
erreichbar, und die zwei Kennzahlen der Gegenpruefung stehen jetzt neben
zitat_erfunden. Dazu scripts/simulation_abdeckung.py in der Skriptliste.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Schritt 6: Der Abschlussnachweis**

```bash
git status --short
git log --oneline -3
git diff --stat d8deb6c -- interview_theater/
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Erwartet, in dieser Reihenfolge:
1. `git status --short`: nur die vier `.cc-*`/`.superpowers-brief-*`-Dateien.
2. `git log --oneline -3`: die drei letzten Commits dieser Karte, alle auf
   `padua-workshop/t_a4ae02fa-plan-a3-simulation`.
3. `git diff --stat d8deb6c -- interview_theater/`: **keine Ausgabe.**
4. `passed` >= 2768, `0 failed`.

Kein `merge`, kein `push`.

---

## Wenn etwas schiefgeht

| Symptom | Was zu tun ist |
|---|---|
| Der Proxy (`IT_SIM_URL`) antwortet nicht | Aufgaben 9–11 auslassen, Bericht mit `nicht gemessen (Proxy nicht erreichbar)` fuellen, Urteil ausdruecklich nur auf die deterministischen Nachweise stuetzen. Keine Warterunde, keine Wiederholung. |
| `betrieb/gruppe1.env` fehlt | dasselbe. |
| Ein Lauf kostet > 1,10 CHF | Abbruch der Laufreihe. Was gemessen ist, kommt in den Bericht; die fehlenden Zellen bleiben leer mit `abgebrochen (Kosten)`. |
| Die Summe naehert sich 8 CHF | Keinen weiteren Lauf. Reserve ist damit verbraucht. |
| Ein Lauf haengt > 40 Minuten | abbrechen (`Ctrl-C` ist nicht verfuegbar — den Prozess beenden), `git status --short` pruefen, Mutation-Rueckname nach dem Muster aus Aufgabe 10 Schritt 6 verifizieren, Lauf als `abgebrochen (Laufzeit)` protokollieren. |
| `tests/test_simulation_mutation.py` ist rot | **kein bezahlter Lauf.** Erst reparieren; die Mutation muss den Fehler erzeugen, sonst misst der Lauf nichts. |
| Eine Kennzahl steht in beiden Armen gleich | Das ist ein Ergebnis, kein Fehler. Ins Protokoll: `nein (beide gleich)`, mit beiden Werten. Nicht die Kennzahl nachjustieren, bis sie anschlaegt — das waere ein an die Zahlen angepasstes Urteil. |
| `git diff -- interview_theater/` ist nicht leer | `git checkout -- interview_theater/` ist **nicht** erlaubt (kein `checkout`). Stattdessen die Aenderung mit `git diff` ansehen, per `Edit` von Hand zuruecknehmen und den Schritt wiederholen. |
| Der Zensus meldet noch `gefunden_falsch` nach Aufgabe 7 | Die Stelle nachziehen. Eine Behauptung aus `BEHAUPTUNGEN` zu streichen, damit der Zensus gruen wird, waere genau der Fehler, den er nachweist. |

---

## Selbstpruefung des Plans gegen den Auftrag

| Vorgabe | Wo erledigt |
|---|---|
| A — Bestandsaufnahme als erste Aufgabe, deterministisch, nachfahrbar | Aufgabe 1 (`scripts/simulation_abdeckung.py`, 13 Tests); die Praemissenpruefung mit Datei:Zeile steht im Plan-Kopf und im Bericht |
| A — Praemisse selbst geprueft, Widerlegung im Kopf | Abschnitt „Die Praemissenpruefung", sieben Zeilen mit Fundstelle; zwei zusaetzliche Befunde, die der Verdacht nicht nennt |
| B — Fix-Stellen je Fehler mit Commit-SHA | Aufgabe 2 (Tabelle `e56a892`/`bbe301e`/`36030ff`), Aufgabe 3 (`3ae76ab`/`c9af872`) |
| B — reproduzierbarer Wiedereinbau, Entscheidung begruendet | Aufgabe 2 (`simulation/mutation.py`, Docstring mit drei Gruenden gegen den `.patch`-Weg) |
| B — keine Mutationsweiche im Produktivcode, `git status` sauber | Global Constraints; Aufgabe 10/11 Schritt 6; Aufgabe 13 Schritt 1 |
| B — deterministischer Nachweis vor jedem bezahlten Lauf | `tests/test_simulation_mutation.py`; Vorspiel der Laufmatrix; Aufgabe 10/11 Schritt 2 |
| B — welche Ursache von Fehler 1 mutiert wird und warum | Aufgabe 2, Absatz „Welche der drei Ursachen mutiert wird"; die anderen zwei in Abschnitt 6 des Berichts |
| C — neue Kennzahlen test-first, Fixture-DB, ohne Netz | Aufgaben 4 und 5 (je 8 Tests, `conn`-Fixture aus `tests/conftest.py`) |
| C — schlaegt mutiert an, unmutiert nicht, beides als Test | `test_die_kennzahl_schlaegt_unter_der_mutation_an_und_sonst_nicht` (Aufgabe 4); `test_ein_szenenfolge_lauf_nach_der_richtungswahl_ist_ein_befund` + `test_ein_lauf_vor_der_richtungswahl_zaehlt_nicht` (Aufgabe 5) |
| C — Einbindung in `bericht.py` und `verlauf.jsonl` | Aufgabe 6 (`_gegenpruefzeilen`, `"mutation"`; `**zahlen` traegt den Rest) |
| D — Skript auf sieben Phasen, README und Docstrings | Aufgabe 7 Schritte 5–8 |
| D — Schritte benennen, die erreichbare Knoepfe nicht druecken | Aufgabe 12 Schritt 1 (Knopfarten angeboten gegen gedrueckt aus der Lauf-DB) |
| E — Laufmatrix mit Set, Seed, Schaltern, Kosten je Zelle | Abschnitt „Die Laufmatrix" + Aufgabe 8 Schritt 2 |
| E — Kosten aus `verlauf.jsonl` gelesen, nicht geschaetzt | Aufgabe 0 Schritt 5 (Kommando + gemessene Ausgabe), Aufgabe 8 Schritt 2 |
| E — Summe < 10 CHF, gleicher Seed je Vergleich | Laufmatrix (3,30 CHF erwartet); Seed 1 in Basis und beiden Mutationen |
| E — nur erfundene Sets 1–3, kein `birk`, kein `tag1` | Global Constraints, Laufmatrix („Verboten") |
| E — Abbruchkriterium bei doppelten Kosten | Aufgabe 9 Schritt 3, Tabelle „Wenn etwas schiefgeht" |
| E — ANNAHME-Marker mit Pruefkommando | Aufgabe 0 Schritte 3 und 4 |
| F — Richternoten je Kriterium und Abschnitt, gleicher Seed | Bericht Abschnitt 5; Aufgabe 12 Schritt 4 |
| F — Schwelle und Streuung **vorher** festgelegt | Aufgabe 8 (Bericht Abschnitt 5, erster Absatz); Basislauf 2 dient nur diesem Zweck |
| G — Berichtsaufbau vorgegeben, Urteil mit vorherigem Kriterium | Aufgabe 8 Schritt 1 (vollstaendiges Geruest, Kriteriumstabelle) |
| G — keine Modellantworten, keine Echtdaten im Bericht | Aufgabe 8 (PII-Absatz), Aufgabe 12 Schritt 7 (`grep`-Pruefung) |
| H — Mutationen zurueckgenommen belegen | Aufgabe 13 Schritt 1 und 6 (drei Kommandos mit erwarteter Ausgabe) |
| H — AGENTS.md nur angleichen, wenn sich etwas geaendert hat | Aufgabe 13 Schritt 3 (drei minimale Stellen, Begruendung im Commit) |
| Geld-Aufgaben markiert und nach den kostenlosen | Aufgaben 9–11 tragen **KOSTET GELD** im Titel; 1–8 sind kostenlos und stehen davor. 12 und 13 sind kostenlos und stehen danach, weil sie die Laeufe auswerten — die **vorbereitende** Arbeit ist vollstaendig vor dem ersten Franken erledigt. |
| Keine Rueckfrage noetig | Jede offene Entscheidung ist im Plan getroffen: Mutationsweg (Monkey-Patch), Ursachenwahl bei Fehler 1 (a), `--ohne-szene` in allen Laeufen, Set 1, Seeds 1/2, Streuungsschwelle, Kostengrenzen, Verhalten bei fehlendem Proxy, Verhalten bei nicht erreichter Richtungswahl (ein Reservelauf mit Seed 3), Verhalten bei gleichstehenden Kennzahlen (protokollieren, nicht nachjustieren). |





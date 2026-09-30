# Padua A5: Dortmund-Reste — Kuerzen, Sperre Schaerfung/Szenenfolge, Richtungswahl

> **Fuer agentische Umsetzer:** ERFORDERLICHE UNTER-SKILL: Nutze
> `superpowers:subagent-driven-development` (empfohlen) oder
> `superpowers:executing-plans`, um diesen Plan Aufgabe fuer Aufgabe
> umzusetzen. Die Schritte tragen Checkboxen (`- [ ]`) zum Mitfuehren.

**Ziel:** Die vier offenen Befunde aus
`docs/analyse-phase5-chaos-2026-09-06.md` schliessen — C4 (Kuerzen-Knopf),
C10 (`szene_kuerzen` als Erkenner-Art), C7 (Schaerfung und Szenenfolge nicht
gleichzeitig) und C9 (die Richtungswahl speichert ihre Szenenzeilen mit).

**Architektur:** Kein neuer Anbieterweg, keine neue Tabelle, kein neues
Framework. Kuerzen ist eine **Ueberarbeitung** ueber die zwei vorhandenen
Laeufe (`szene.starte` je Szene, `kurzgeschichte.starte` fuer die ganze
Geschichte) mit einer festen Regie-Notiz; das Ergebnis haengt sich ueber die
seit 06.09. bestehende Mechanik (`repo.haenge_szenenfassung_an`) als neue
Fassung an. Die Sperre gegen das Chaos aus Phase 5 ist **eine** gemeinsame
Sperre je `chat_id` in einem neuen, abhaengigkeitsfreien Modul — sie koppelt
ausschliesslich Schaerfung und die Szenenfolge-Laeufe und laesst
Gespraechszug, Szenenlauf und Prosalauf unberuehrt.

**Tech-Stack:** Python 3.11, Standardbibliothek + `httpx`, SQLite, pytest.
Kein Netzzugriff in Tests (Attrappen).

---

## Gemessene Basis (selbst gemessen, nicht uebernommen)

Auf `17eb5b0` (Basis dieses Arbeitsbaums), mit
`python3.11 -m pytest -q -p no:cacheprovider`:

```
2702 passed, 1 skipped in 190.15s (0:03:10)
```

0 errors, 0 failures. **Diese Zahl ist die Messlatte** — nach jeder Aufgabe
muessen es mindestens 2702 bestandene Tests sein, plus die neuen.

**Bekannt flakig auf der Basis** (Architekt-Pruefung, 30.09.2026, zweiter
Volllauf auf `17eb5b0`): `1 failed, 2701 passed, 1 skipped` — rot war
`tests/test_aufnahme.py::test_fertig_in_der_sprachnachricht_beendet_das_interview`.
Einzeln dreimal und im Modul (`58 passed`) gruen. Faellt genau dieser Test im
Volllauf, ist das kein Befund dieser Karte: einzeln nachfahren
(`python3.11 -m pytest -q -p no:cacheprovider tests/test_aufnahme.py`); erst
wenn er auch dort rot ist, gehoert er zur Umsetzung. Nicht reparieren, nicht
ueberspringen — eigene Karte.

**Zum Interpreter:** `$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)`
war in dieser Sitzung nicht aufrufbar (Sandbox-Regel), `.venv/bin/python`
ebenfalls nicht. Was funktioniert hat und in allen Kommandos unten steht:
`python3.11` (liegt in `/home/birk/.local/bin/python3.11`). Das System-`python3`
ist 3.9 und scheitert am `X | None` der Modulkoepfe — **nicht** benutzen.
Ist `.venv` beim Umsetzer heil, geht auch `.venv/bin/python -m pytest -q`.

**Suite-Kommando (ueberall unten `SUITE` genannt):**

```bash
python3.11 -m pytest -q -p no:cacheprovider
```

---

## Ergebnis der Praemissenpruefung fuer Teil 4 (vor dem Planen durchgefuehrt)

Die Karte verlangt sie zuerst. Sie ist gelaufen, am Code und mit einem
Probelauf gegen die echten Zerleger (ohne Netz, ohne Datenbank):

```python
# gemessen am 30.09.2026 auf 17eb5b0
zeile = ("Nacht am Kanal — Mira stellt sich, Pal gesteht, am Ende bleiben "
         "beide. Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. "
         "Szene 3: Der Morgen danach.")
szenenfolge.zerlege_geschichte(zeile)   # -> (ganze Zeile, [])   <- keine Szenen
szenenfolge.formabfolge(zeile)          # -> None
```

**Die Praemisse ist zur Haelfte widerlegt und zur Haelfte bestaetigt:**

1. **Widerlegt:** `knoepfe/szenen.py:1041-1042`
   (`if not alter_block: zeilen = []`) verwirft heute **nichts**. Auf dem
   Menue-Weg traegt ein Richtungs-Knopf immer genau **eine** Zeile — der
   `wert` entsteht in `knoepfe/szenen.py:284` als
   `f"weiter{TRENNER}{zeile}"` aus `vorschlag.zeilen(wert)` (eine Zeile je
   Knopf), und im Einzelfall aus `knoepfe/szenen.py:273`
   (`richtungen[0]`). Bei einer einzigen Zeile liefert
   `szenenfolge.zerlege_geschichte` (`szenenfolge.py:352-374`) ohnehin eine
   leere Szenenliste, weil `rest` leer ist. Der mehrzeilige Fall erreicht
   `_speichere_geschichte` nur ueber `knoepfe/szenen.py:250`
   (`if alter_block and szenenzeilen:`) — und dort ist `alter_block` **True**,
   die Zeilen bleiben und gehen in `szenenfolge.lege_an`
   (`knoepfe/szenen.py:1067-1068`). `ART_GESCHICHTE_SPEICHERN` wird nirgends
   sonst erzeugt (geprueft: `grep -rn ART_GESCHICHTE_SPEICHERN
   interview_theater/` trifft nur `knoepfe/szenen.py`, `texte.py`,
   `__init__.py`, `wirkung.py`).
2. **Bestaetigt, und das ist die verbleibende Luecke:** eine Richtungszeile,
   die ihre Szenen **innerhalb der Zeile** benennt
   (`… Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. …`), wird
   vollstaendig als `arbeitsstand.geschichte` gespeichert (richtig — sie
   *ist* die Richtung), aber **keine einzige `szene`-Zeile entsteht daraus**.
   Direkt danach laeuft `szenenfolge.starte_geschichte_szenen`
   (`knoepfe/szenen.py:1091`) und erfindet Titel und Anzahl neu. Genau der
   Verlust aus Abschnitt 4 der Analyse, nur eine Ebene tiefer als dort
   beschrieben.
3. **Nebenbefund, ebenfalls gemessen:** nennt dieselbe Zeile zusaetzlich
   Formen (`Szene 1: Ankunft (Dialog). Szene 2: … (Monolog). …`), greift
   `szenenfolge.formabfolge` (liefert `{1: 'dialog', 2: 'monolog', 3: 'chor'}`)
   und `_speichere_geschichte` zweigt in `_uebernimm_formwahl` ab
   (`knoepfe/szenen.py:1055-1058`). Die Formen werden uebernommen —
   `arbeitsstand.geschichte` bleibt dann aber **leer**, obwohl die Zeile
   eine Handlung trug. Das wird in Aufgabe 6 mit behandelt.

**Keine Prompt-Aenderung an `ANWEISUNG_GESCHICHTE`.** Der Prompt verbietet
Szenenfolgen in diesem Schritt (`szenenfolge.py:130-132`), und das bleibt
richtig; die Luecke entsteht dort, wo ein Modell sich trotzdem nicht daran
haelt, und dagegen hilft Code, kein weiterer Satz im Prompt.

---

## Globale Vorgaben (gelten fuer jede Aufgabe)

- **Projektsprache Deutsch**, ASCII-Umschrift wie im Repo: `ue`/`oe`/`ae`/`ss`
  in Code, Docstrings, Konstanten, Commit-Messages. In `korpus/*.jsonl` und in
  bestehenden Nutzertexten stehen echte Umlaute — dort **nicht** umschreiben.
- **Neue Nutzertexte sind Konstanten**, nie Literale am Verwendungsort:
  `_TEXT_…`/`TEXT_…` im jeweiligen Modul, **Knopfbeschriftungen und
  ART-Kennungen in `interview_theater/knoepfe/texte.py`**. Eine spaetere Karte
  uebersetzt alles in einem Zug; was im Code steht, ist dann nicht
  uebersetzbar.
- **Die drei Knopf-Zusagen** (AGENTS.md, „Inline-Knoepfe an den
  Auswahl-Momenten"): (1) `callback_data` nur `k:<id>` ueber `_daten`,
  der Wert steht in `knopf.wert`; (2) **kein Modellaufruf in einem
  Knopf-Handler** — weitergeben von `klm` an einen Thread ist erlaubt,
  `klm.<irgendwas>` nicht; (3) idempotent ueber `repo.beanspruche_knopf`,
  d. h. der Handler braucht keine eigene Sperre.
  `tests/test_knoepfe_struktur.py` haelt alle drei am Quelltext fest und muss
  gruen bleiben — insbesondere
  `test_jede_knopfart_hat_genau_einen_handler`.
- **Ein Sperren-Register je Nebenlaeufigkeit.** Die neue gemeinsame Sperre
  koppelt **ausschliesslich** `schaerfung` und die vier `starte*`-Funktionen
  in `szenenfolge.py`. `szene._sperre_fuer`, `kurzgeschichte._sperre_fuer`,
  `ablauf._sperre_fuer`, `sprachstil._sperre_fuer` bleiben **unberuehrt** —
  eine gemeinsame Sperre wuerde den Gespraechszug am Szenenlauf haengen
  lassen.
- **Fassungen werden nur angehaengt** (`repo.haenge_szenenfassung_an`), nie
  geaendert, nie geloescht. Kein `aktualisiere_szenenfassung`, kein
  `entfernt_am` dort.
- **Keine Echtdaten.** `betrieb/soap.db`, `betrieb/*.log`, Audio und
  Transkripte werden nicht gelesen und nicht zitiert. Alle Testdaten und alle
  Korpusnamen sind erfunden und stammen nicht aus dem Projektumfeld.
- **Nebenlaeufigkeitstests sind deterministisch:** `threading.Event`,
  `threading.Barrier`, `Lock.acquire(timeout=…)` — **nie** `time.sleep` als
  Synchronisation.
- **Branch** bleibt `padua-workshop/t_4489e2ad-plan-a5-dortmund-reste`.
  Kein Merge, kein Push. Ein Commit je Aufgabe.
- **Nach jeder Aufgabe** laeuft `SUITE` vollstaendig und ist gruen, bevor
  committet wird.

---

## Dateien im Ueberblick

| Datei | Aufgabe | Verantwortung |
|---|---|---|
| `interview_theater/vorschlagssperre.py` | **neu**, A1 | Die eine gemeinsame Sperre je `chat_id` fuer Vorschlagslaeufe, plus ein Merkplatz je Auftragsart. Reines `threading`, keine Importe aus dem Projekt. |
| `tests/test_vorschlagssperre.py` | **neu**, A1 | Einheitentests des Registers, ohne Bot, ohne Datenbank. |
| `interview_theater/szenenfolge.py` | A2, A6 | `_sperre_fuer` delegiert; `starte*` merken den zweiten Auftrag; neu: `szenen_in_zeile`, `lege_inline_an`. |
| `interview_theater/schaerfung.py` | A2 | `starte` nimmt die gemeinsame Sperre, merkt bei Belegung, gibt im Thread frei. |
| `tests/test_vorschlagskollision.py` | **neu**, A2 | Die drei Nachweise (a)/(b)/(c) der Sperre gegen echte Modul-Aufrufe mit Attrappen. |
| `interview_theater/kuerzung.py` | **neu**, A3 | Die eine Stelle, an der „kuerzer" zu einem Lauf wird — Notiztexte, Zielwahl, `starte`. Kein eigener Modellaufruf, gibt an die vorhandenen Laeufe ab. |
| `interview_theater/knoepfe/texte.py` | A3 | `ART_SZENE_KUERZEN`, `ART_GESCHICHTE_KUERZEN`, `TEXT_KUERZEN_KNOPF`. |
| `interview_theater/knoepfe/szenen.py` | A3, A6 | Der Knopf in `biete_nach_szenentext` und in `zeige_kurzgeschichte`; `_speichere_geschichte` uebernimmt Inline-Szenen. |
| `interview_theater/knoepfe/wirkung.py` | A3 | Zwei Handler, zwei Zeilen in `_WIRKUNGEN`. |
| `interview_theater/knoepfe/__init__.py` | A3 | Re-Export der drei neuen Namen. |
| `tests/test_kuerzung.py` | **neu**, A3 | Knopf und Modul: Notiz, Fassung angehaengt, keine neue Szenenfolge. |
| `interview_theater/erkenner.py` | A4 | `szene_kuerzen` in `ARTEN`, kein Schreibpfad, `_starte_kuerzung` in `laufe`. |
| `tests/test_erkenner.py` | A4 | `test_arten_enthaelt_alle_werte` ergaenzen, drei neue Tests. |
| `interview_theater/prompts/erkenner.md` | A5 | Art 23, Abgrenzung, Kopfzeile „vierundzwanzig", Kollision in Punkt 17 entschaerfen. |
| `korpus/erkenner.jsonl` | A5 | 2 Positiv-, 3 Negativfaelle (`sk01`…`sk05`). |
| `tests/test_korpus.py` | A5 | Dichte und die drei Grenzfaelle festhalten. |
| `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` | A5 | Die **eine** Zeile `prompt erkenner` nachziehen. |
| `docs/prompt-audit/2026-09-06/04-erkenner.txt` | A5 | Den SYSTEM-Block nachziehen (Golden-Dump). |
| `tests/test_geschichte.py` | A6 | Die Inline-Szenen der Richtungswahl. |
| `AGENTS.md` | A7 | Ein Absatz je Teil. |

**Sieben Umsetzungsaufgaben plus eine Abschlussaufgabe: acht.**

---

## Aufgabe 1: Das gemeinsame Sperren-Register (`vorschlagssperre.py`)

**Dateien:**
- Anlegen: `interview_theater/vorschlagssperre.py`
- Anlegen: `tests/test_vorschlagssperre.py`

**Schnittstellen:**
- Produziert (von A2 genutzt):
  - `vorschlagssperre.sperre_fuer(chat_id: int) -> threading.Lock`
  - `vorschlagssperre.nimm(chat_id: int) -> bool`
  - `vorschlagssperre.gib_frei(chat_id: int) -> None`
  - `vorschlagssperre.merke(chat_id: int, art: str, auftrag) -> bool`
  - `vorschlagssperre.laeuft(chat_id: int) -> bool`
  - `vorschlagssperre.gemerkte_arten(chat_id: int) -> list[str]`
  - `vorschlagssperre.vergiss(chat_id: int) -> None`
- Konsumiert: nur `threading` und `logging` aus der Standardbibliothek.

### Schritte

- [x] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `tests/test_vorschlagssperre.py`:

```python
"""Die EINE gemeinsame Sperre fuer Vorschlagslaeufe (30.09.2026, C7).

Der gemessene Fall (docs/analyse-phase5-chaos-2026-09-06.md Abschnitt 2, Ende):
13:53:42 lief die Schaerfung an, 13:54:10 wurde der Szenenfolge-Lauf fertig,
13:54:20 kam die naechste Schaerfung, 13:54:37 die Szenenspeicherung -- zwei
unabhaengige Fragestraenge im selben Chatfenster. ``schaerfung.starte`` hatte
gar keine Sperre, ``szenenfolge`` eine eigene.

Dieses Modul ist absichtlich abhaengigkeitsfrei: keine Datenbank, kein
Telegram, kein Modell. Damit laesst sich das Verhalten hier pruefen und in
``test_vorschlagskollision.py`` nur noch die Verdrahtung.
"""

import threading

from interview_theater import vorschlagssperre


def test_nimm_gibt_die_sperre_genau_einmal():
    vorschlagssperre.vergiss(1)
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.nimm(1) is False
    assert vorschlagssperre.laeuft(1) is True
    vorschlagssperre.gib_frei(1)
    assert vorschlagssperre.laeuft(1) is False
    assert vorschlagssperre.nimm(1) is True
    vorschlagssperre.gib_frei(1)


def test_zwei_gruppen_stoeren_sich_nicht():
    """Eine Sperre je chat_id, nicht eine globale -- vier Bots teilen einen
    Prozessraum in den Tests."""
    vorschlagssperre.vergiss(1)
    vorschlagssperre.vergiss(2)
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.nimm(2) is True
    vorschlagssperre.gib_frei(1)
    vorschlagssperre.gib_frei(2)


def test_gemerkter_auftrag_laeuft_bei_der_freigabe_genau_einmal():
    """Nichts geht verloren: der zweite Auftrag wartet und laeuft danach."""
    vorschlagssperre.vergiss(1)
    gelaufen = []
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("s"))
    assert vorschlagssperre.gemerkte_arten(1) == ["schaerfung"]
    assert gelaufen == []
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]
    assert vorschlagssperre.gemerkte_arten(1) == []
    # Eine zweite Freigabe holt ihn nicht noch einmal hervor.
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]


def test_ein_platz_je_art_der_zweite_gleiche_auftrag_ersetzt_den_ersten():
    """Ein Platz je (chat_id, art): zwei Schaerfungslaeufe hintereinander
    nachzuholen waere zweimal dasselbe Geld fuer dasselbe Ergebnis."""
    vorschlagssperre.vergiss(1)
    gelaufen = []
    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("erst"))
    vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("dann"))
    vorschlagssperre.merke(1, "szenenfolge", lambda: gelaufen.append("folge"))
    assert sorted(vorschlagssperre.gemerkte_arten(1)) == ["schaerfung", "szenenfolge"]
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["dann", "folge"]


def test_ein_gescheiterter_gemerkter_auftrag_reisst_die_anderen_nicht_mit():
    vorschlagssperre.vergiss(1)
    gelaufen = []

    def kaputt():
        raise RuntimeError("Absicht")

    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(1, "a", kaputt)
    vorschlagssperre.merke(1, "b", lambda: gelaufen.append("b"))
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["b"]
    assert vorschlagssperre.laeuft(1) is False


def test_die_sperre_ist_bei_der_freigabe_schon_frei():
    """Der gemerkte Auftrag nimmt sie selbst wieder -- also muss sie frei
    sein, bevor er laeuft. Sonst waere jeder nachgeholte Auftrag ein
    'gleich, ich denke noch nach'."""
    vorschlagssperre.vergiss(1)
    gesehen = []
    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(
        1, "a", lambda: gesehen.append(vorschlagssperre.laeuft(1))
    )
    vorschlagssperre.gib_frei(1)
    assert gesehen == [False]


def test_sperre_fuer_liefert_immer_dasselbe_objekt():
    """Bestehende Tests warten ueber ``acquire(timeout=10)`` auf das Ende
    eines Laufs (tests/test_szenenfolge.py:169) -- dafuer muss es dasselbe
    Lock-Objekt sein wie das, das der Lauf haelt."""
    vorschlagssperre.vergiss(7)
    eine = vorschlagssperre.sperre_fuer(7)
    assert isinstance(eine, threading.Lock().__class__)
    assert vorschlagssperre.sperre_fuer(7) is eine


def test_freigabe_ohne_sperre_ist_kein_fehler():
    """Ein Thread, der nie genommen hat, darf beim Aufraeumen freigeben --
    dieselbe Haltung wie in ``szenenfolge._lauf`` (finally in JEDEM Fall)."""
    vorschlagssperre.vergiss(99)
    vorschlagssperre.gib_frei(99)
    assert vorschlagssperre.laeuft(99) is False
```

- [x] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagssperre.py
```
Erwartet: Sammelfehler, `ModuleNotFoundError: No module named
'interview_theater.vorschlagssperre'` (bzw. `ImportError` beim Sammeln).

- [x] **Schritt 3: Das Modul schreiben**

Datei `interview_theater/vorschlagssperre.py`:

```python
"""Die EINE Sperre, die Schaerfung und Szenenfolge voneinander trennt.

**Warum es dieses Modul gibt** (30.09.2026, Massnahme C7 aus
``docs/analyse-phase5-chaos-2026-09-06.md``). Am 06.09. lagen in Gruppe 1
zwei Vorschlagsstraenge uebereinander: 13:53:42 startete die Schaerfung aus
dem Phaseneintritt, 13:54:10 wurde der Szenenfolge-Lauf fertig, 13:54:20 kam
die naechste Schaerfung, 13:54:37 wurde die Folge gespeichert. Die Gruppe
bekam zwei unabhaengige Fragen in dasselbe Chatfenster und wusste nicht, auf
welche sie antwortet -- die eigentliche Wall of Text. Grund: ``szenenfolge``
hatte eine eigene Sperre (``_sperre_fuer``), ``schaerfung.starte`` gar keine.

**Was diese Sperre NICHT ist.** Sie koppelt ausschliesslich die
Vorschlagslaeufe: ``schaerfung`` und die vier ``starte*`` in
``szenenfolge.py``. Gespraechszug (``ablauf``), Szenenlauf (``szene``),
Prosalauf (``kurzgeschichte``) und Sprachstil behalten ihre eigenen Register
-- eine gemeinsame Sperre wuerde den Gespraechszug am Szenenlauf haengen
lassen (AGENTS.md, "Ein Sperren-Register je Nebenlaeufigkeit").

**Nichts geht verloren.** Wer die Sperre nicht bekommt, legt seinen Auftrag
auf einen Merkplatz (einen je ``(chat_id, art)``); ``gib_frei`` gibt zuerst
die Sperre zurueck und startet danach, was gemerkt wurde. Ein Platz je art
und nicht eine Warteschlange: zwei nachgeholte Schaerfungslaeufe wuerden
zweimal dasselbe Geld fuer dasselbe Ergebnis kosten.

**Bekannte Grenze:** der Merkplatz liegt im Prozess, nicht in der Datenbank.
Ein Neustart zwischen Ankuendigung und Nachholen verliert den gemerkten
Auftrag -- wie bei jeder anderen Thread-Sperre im Repo
(``szenenfolge._regienotiz_erwartet``, ``szene._usa_erinnerungen``). Die
harmlose Fehlerrichtung: die Gruppe fragt noch einmal, und der Knopf steht
weiter da.

Keine Importe aus dem Projekt: dieses Modul kennt weder Datenbank noch
Telegram noch Modell. Damit ist es von beiden Aufrufern aus importierbar,
ohne einen Zyklus zu bauen.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

#: Eine Sperre je chat_id. Lebt fuer die Laufzeit des Prozesses; ein paar
#: Bytes je jemals gesehener Gruppe sind kein Problem (wie ``ablauf._sperren``).
_sperren: dict[int, threading.Lock] = {}

#: Ein Merkplatz je chat_id, darin einer je Auftragsart.
_gemerkt: dict[int, dict[str, Callable[[], None]]] = {}

#: Schuetzt die beiden Register -- nicht die Laeufe.
_schutz = threading.Lock()


def sperre_fuer(chat_id: int) -> threading.Lock:
    """Die (ggf. neu angelegte) Sperre dieser Gruppe.

    Oeffentlich, weil Tests darauf warten: ``acquire(timeout=10)`` auf
    dasselbe Objekt ist die Art, auf das Ende eines Laufs zu warten, ohne zu
    schlafen (``tests/test_szenenfolge.py``)."""
    with _schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def nimm(chat_id: int) -> bool:
    """Versucht, die Sperre zu nehmen, ohne zu warten. True heisst: du hast
    sie, und du gibst sie mit ``gib_frei`` zurueck."""
    return sperre_fuer(chat_id).acquire(blocking=False)


def laeuft(chat_id: int) -> bool:
    """Haelt gerade jemand die Sperre dieser Gruppe?"""
    return sperre_fuer(chat_id).locked()


def merke(chat_id: int, art: str, auftrag: Callable[[], None]) -> bool:
    """Legt einen Auftrag auf den Merkplatz dieser Art. Liefert True.

    Ein zweiter Auftrag derselben art ersetzt den ersten: was gerade gefragt
    wurde, ist aktueller als das, was vor zwei Minuten gefragt wurde."""
    with _schutz:
        _gemerkt.setdefault(chat_id, {})[art] = auftrag
    return True


def gemerkte_arten(chat_id: int) -> list[str]:
    """Welche Arten warten? Fuer Tests und fuer das Log."""
    with _schutz:
        return list(_gemerkt.get(chat_id, {}))


def gib_frei(chat_id: int) -> None:
    """Gibt die Sperre zurueck und holt nach, was gemerkt wurde.

    **Erst freigeben, dann nachholen** -- der gemerkte Auftrag nimmt die
    Sperre selbst wieder (er laeuft ueber dieselbe ``starte``-Funktion wie
    beim ersten Versuch). In der anderen Reihenfolge bekaeme er nur die
    Wartemeldung, die er gerade abarbeitet.

    Robust gegen den Fall, dass niemand genommen hat: ``finally``-Zweige
    geben in JEDEM Fall frei (wie ``szenenfolge._lauf``), und ein
    ``RuntimeError`` dort duerfte einen Lauf nicht nachtraeglich als
    gescheitert dastehen lassen."""
    with _schutz:
        sperre = _sperren.get(chat_id)
        nachzuholen = list(_gemerkt.pop(chat_id, {}).items())
    if sperre is not None and sperre.locked():
        try:
            sperre.release()
        except RuntimeError:  # pragma: no cover -- Verteidigung, kein Weg
            log.exception("Vorschlagssperre war schon frei, chat_id=%s", chat_id)
    for art, auftrag in nachzuholen:
        log.info("Gemerkten Vorschlagslauf nachgeholt, chat_id=%s, art=%s",
                 chat_id, art)
        try:
            auftrag()
        except Exception:
            log.exception(
                "Gemerkter Vorschlagslauf fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, art,
            )


def vergiss(chat_id: int) -> None:
    """Raeumt Sperre und Merkplatz dieser Gruppe ab -- fuer Tests.

    Im Betrieb gibt es keinen Anlass: ein Prozess je Gruppe, und die Sperre
    lebt so lange wie er."""
    with _schutz:
        _sperren.pop(chat_id, None)
        _gemerkt.pop(chat_id, None)
```

- [x] **Schritt 4: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagssperre.py
```
Erwartet: `8 passed`.

Danach die ganze Suite:

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2710 passed, 1 skipped` (2702 + 8).

- [x] **Schritt 5: Mutationsnachweis**

In `gib_frei` die beiden Zeilen
```python
    with _schutz:
        sperre = _sperren.get(chat_id)
        nachzuholen = list(_gemerkt.pop(chat_id, {}).items())
```
auf `nachzuholen = []` eindampfen (also den Merkplatz nicht leeren und nichts
nachholen), dann:

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagssperre.py
```
Erwartet: **rot** in
`test_gemerkter_auftrag_laeuft_bei_der_freigabe_genau_einmal`,
`test_ein_platz_je_art_der_zweite_gleiche_auftrag_ersetzt_den_ersten`,
`test_ein_gescheiterter_gemerkter_auftrag_reisst_die_anderen_nicht_mit` und
`test_die_sperre_ist_bei_der_freigabe_schon_frei`.
Danach die Aenderung zurueckdrehen und erneut gruen sehen.

- [x] **Schritt 6: Commit**

```bash
git add interview_theater/vorschlagssperre.py tests/test_vorschlagssperre.py
git commit -m "$(cat <<'EOF'
Vorschlagssperre: eine gemeinsame Sperre je chat_id mit Merkplatz

Grundlage fuer C7 aus docs/analyse-phase5-chaos-2026-09-06.md: Schaerfung und
Szenenfolge liefen am 06.09. uebereinander, weil szenenfolge eine eigene
Sperre hatte und schaerfung gar keine. Das Modul ist abhaengigkeitsfrei
(nur threading) und koppelt bewusst NUR die Vorschlagslaeufe -- Gespraechszug,
Szenenlauf und Prosalauf behalten ihre Register.

Noch kein Aufrufer: die Verdrahtung kommt im naechsten Commit.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 2 (Teil 3): Schaerfung und Szenenfolge laufen nie gleichzeitig

**Dateien:**
- Aendern: `interview_theater/szenenfolge.py:204-217` (Register),
  `:803-811` (Texte), `:821-852` (`_lauf`), `:855-889` (`starte`),
  `:892-925` (`starte_geschichte`), `:939-973` (`starte_geschichte_szenen`),
  `:976-1025` (`starte_feldvorschlag`)
- Aendern: `interview_theater/schaerfung.py:30-37` (Importe), `:62-75` (Texte),
  `:246-297` (`_lauf`, `starte`)
- Anlegen: `tests/test_vorschlagskollision.py`

**Schnittstellen:**
- Konsumiert aus A1: `vorschlagssperre.nimm`, `.gib_frei`, `.merke`,
  `.sperre_fuer`, `.vergiss`.
- Produziert:
  - `szenenfolge._TEXT_GEMERKT: str`
  - `schaerfung.TEXT_GEMERKT: str`
  - `schaerfung.GEMERKT: str` — Rueckgabewert von `schaerfung.starte`, wenn
    der Auftrag gemerkt wurde (statt `None`, damit
    `knoepfe.starte_schaerfung` nicht sofort die alte Lage ausspielt).
  - `szenenfolge._sperre_fuer(chat_id) -> threading.Lock` bleibt, delegiert
    an `vorschlagssperre.sperre_fuer` (bestehende Tests warten darauf).
  - `szenenfolge._lauf(conn, tg, klm, e, chat_id, system, nutzer, art,
    nachbereitung)` — der Parameter `sperre` **faellt weg**.

### Schritte

- [x] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `tests/test_vorschlagskollision.py`:

```python
"""Schaerfung und Szenenfolge laufen nie gleichzeitig (30.09.2026, C7).

Der gemessene Fall steht in docs/analyse-phase5-chaos-2026-09-06.md
Abschnitt 2: 13:53:42 Schaerfung, 13:54:10 Szenenfolge fertig, 13:54:20
naechste Schaerfung, 13:54:37 Szenenspeicherung. Zwei Fragestraenge in
demselben Chatfenster.

Drei Nachweise, alle deterministisch (Events, keine Schlafzeiten) und ohne
Netz:

(a) der zweite Auftrag startet KEINEN zweiten Modellaufruf, solange der erste
    laeuft,
(b) er laeuft nach dem Ende des ersten GENAU EINMAL,
(c) die Gruppe bekommt sofort eine freundliche Wartemeldung.
"""

import threading

import pytest

from interview_theater import (
    phasen, repo, schaerfung, szenenfolge, vorschlagssperre,
)

from test_knoepfe import TelegramAttrappe
from test_schaerfung import ZITAT_A, _interview


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def frische_sperre():
    """Kein Zustand aus einem frueheren Test -- das Register lebt im Modul."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


class BlockierendesLLM:
    """Ein Modell, das beim ersten Aufruf haengt, bis der Test es loslaesst.

    Es zaehlt ausserdem, wie viele Aufrufe GLEICHZEITIG im Modell stehen --
    das ist der Nachweis (a). Ein Zaehler und nicht eine Messung von Zeit:
    ein Test, der ueber Zeit argumentiert, ist auf einer langsamen Maschine
    ein Falschalarm."""

    def __init__(self):
        self.haltestelle = threading.Event()
        self.drin = threading.Event()
        self.arten = []
        self.gleichzeitig_max = 0
        self._gleichzeitig = 0
        self._zaehlschutz = threading.Lock()

    def _betrete(self, art):
        with self._zaehlschutz:
            self._gleichzeitig += 1
            self.gleichzeitig_max = max(self.gleichzeitig_max, self._gleichzeitig)
            self.arten.append(art)
        self.drin.set()

    def _verlasse(self):
        with self._zaehlschutz:
            self._gleichzeitig -= 1

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self._betrete(art)
        try:
            assert self.haltestelle.wait(timeout=10), "Test hat nie losgelassen"
            return "VORSCHLAG SZENENFOLGE:\nAm Steg — sie treffen sich — Mira — Dialog"
        finally:
            self._verlasse()

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self._betrete(art)
        try:
            assert self.haltestelle.wait(timeout=10), "Test hat nie losgelassen"
            return {
                "eintrag_nummern": [1], "szenen_nummern": [1],
                "figuren_namen": [""], "begruendungen": ["passt zu Szene 1"],
                "zitate": [ZITAT_A],
            }
        finally:
            self._verlasse()


@pytest.fixture
def lage(conn):
    """Der Stand beim Eintritt in Phase 5: ein ausgewertetes Interview, eine
    Figur, eine Szene, eine Geschichte."""
    _interview(conn, ZITAT_A, [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": ZITAT_A,
         "zitat_geprueft": 1},
    ], name="A")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Im Treppenhaus")
    phasen.setze(conn, 1, 5, "test")
    return conn


def test_schaerfung_wartet_auf_die_laufende_szenenfolge(lage, tg, einst):
    """(a) + (b) + (c) in einem Ablauf -- sie gehoeren zusammen, weil sie
    dieselbe Sekunde beschreiben."""
    conn = lage
    klm = BlockierendesLLM()

    folge = szenenfolge.starte_geschichte_szenen(conn, tg, klm, einst, 1)
    assert folge is not None
    assert klm.drin.wait(timeout=10), "der Szenenfolge-Lauf kam nicht ins Modell"

    vorher = len(tg.texte)
    ergebnis = schaerfung.starte(conn, tg, klm, einst, 1)

    # (a) kein zweiter Modellaufruf, solange der erste steht
    assert klm.gleichzeitig_max == 1
    assert "schaerfung" not in klm.arten
    assert ergebnis == schaerfung.GEMERKT

    # (c) die Wartemeldung steht sofort im Chat
    assert schaerfung.TEXT_GEMERKT in tg.texte[vorher:]

    # (b) nach dem Ende des ersten laeuft sie genau einmal
    klm.haltestelle.set()
    folge.join(timeout=10)
    assert not folge.is_alive()
    # Die nachgeholte Schaerfung laeuft in ihrem eigenen Thread; auf ihr Ende
    # wird ueber dieselbe Sperre gewartet, die sie haelt.
    assert szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.arten.count("schaerfung") == 1
    assert repo.schaerfungen(conn, 1)


def test_szenenfolge_wartet_auf_die_laufende_schaerfung(lage, tg, einst):
    """Die andere Richtung -- und die ist der Live-Fall: die Schaerfung lief
    aus dem Phaseneintritt, die Szenenfolge kam von der Richtungswahl."""
    conn = lage
    klm = BlockierendesLLM()

    schaerfung_thread = schaerfung.starte(conn, tg, klm, einst, 1)
    assert schaerfung_thread not in (None, schaerfung.GEMERKT)
    assert klm.drin.wait(timeout=10), "die Schaerfung kam nicht ins Modell"

    vorher = len(tg.texte)
    assert szenenfolge.starte_geschichte_szenen(conn, tg, klm, einst, 1) is None
    assert klm.gleichzeitig_max == 1
    assert szenenfolge.ART not in klm.arten
    assert szenenfolge._TEXT_GEMERKT in tg.texte[vorher:]

    klm.haltestelle.set()
    schaerfung_thread.join(timeout=10)
    assert szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.arten.count(szenenfolge.ART) == 1


def test_die_sperre_haelt_den_szenenlauf_nicht_auf(lage, tg, einst):
    """Die neue Sperre koppelt NUR Schaerfung und Szenenfolge.

    Ein Szenenlauf, der an einem Schaerfungslauf haengt, waere genau die
    gemeinsame Sperre, gegen die AGENTS.md warnt ('eine gemeinsame Sperre
    wuerde den Gespraechszug am Szenenlauf haengen lassen')."""
    from interview_theater import szene

    conn = lage
    klm = BlockierendesLLM()
    schaerfung_thread = schaerfung.starte(conn, tg, klm, einst, 1)
    assert klm.drin.wait(timeout=10)
    # Die Sperre des Szenenlaufs ist frei, obwohl die Schaerfung laeuft.
    assert szene._sperre_fuer(1).acquire(blocking=False)
    szene._sperre_fuer(1).release()
    assert vorschlagssperre.laeuft(1) is True
    klm.haltestelle.set()
    schaerfung_thread.join(timeout=10)
```

- [x] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagskollision.py
```
Erwartet: rot. Konkret `AttributeError: module 'interview_theater.schaerfung'
has no attribute 'GEMERKT'` beim ersten Test; im zweiten laeuft die
Schaerfung parallel und `klm.gleichzeitig_max == 2`.

- [x] **Schritt 3: `szenenfolge.py` auf die gemeinsame Sperre umstellen**

3a — das Register ersetzen. `interview_theater/szenenfolge.py:204-217`

vorher:
```python
# Eine Sperre je chat_id, wie in ``szene.py`` und ``ablauf.py``: zwei
# gleichzeitige Vorschlaege derselben Gruppe waeren zwei Listen im Chat, und
# die Gruppe wuesste nicht, welche gilt.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre
```

nachher:
```python
# Die Sperre liegt seit dem 30.09.2026 in ``vorschlagssperre.py`` und ist
# dieselbe wie die der Schaerfung (Massnahme C7): zwei gleichzeitige
# Vorschlaege derselben Gruppe waren zwei Fragen in einem Chatfenster, und
# die Gruppe wusste nicht, auf welche sie antwortet. Nur die
# Vorschlagslaeufe teilen sie -- Szenenlauf, Prosalauf und Gespraechszug
# haben weiterhin ihr eigenes Register.
def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Die gemeinsame Vorschlagssperre. Name und Rueckgabe bleiben, damit
    Tests weiter ueber ``acquire(timeout=…)`` auf das Ende eines Laufs warten
    koennen (tests/test_szenenfolge.py, tests/test_geschichte.py)."""
    return vorschlagssperre.sperre_fuer(chat_id)
```

3b — Import ergaenzen, `interview_theater/szenenfolge.py:31`:

```python
from interview_theater import anweisungen, repo, vorschlagssperre, workshop
```

(`import threading` bleibt — die `starte*` erzeugen weiter Threads.)

3c — die Wartemeldung als Konstante, hinter `_TEXT_BESETZT`
(`interview_theater/szenenfolge.py:804`):

```python
_TEXT_BESETZT = "Ich denke gerade schon ueber die Szenenfolge nach, gleich."
#: Wenn ein ANDERER Vorschlagslauf die gemeinsame Sperre haelt (30.09.2026,
#: C7). Anders als ``_TEXT_BESETZT`` ist das keine Abfuhr: der Auftrag ist
#: gemerkt und laeuft, sobald der andere fertig ist
#: (``vorschlagssperre.merke``).
_TEXT_GEMERKT = (
    "Ich denke noch ueber etwas anderes nach. Sobald ich damit fertig bin, "
    "mache ich mit der Szenenfolge weiter."
)
```

3d — `_lauf` gibt ueber die gemeinsame Sperre frei.
`interview_theater/szenenfolge.py:821-852`: die Signatur

```python
def _lauf(conn, tg, klm, e, chat_id: int, system: str, nutzer: str, art: str,
          sperre: threading.Lock, nachbereitung) -> None:
```
wird zu
```python
def _lauf(conn, tg, klm, e, chat_id: int, system: str, nutzer: str, art: str,
          nachbereitung) -> None:
```
und im Docstring der Satz „Sperre in JEDEM Fall freigeben" bleibt, ergaenzt um
„— und dabei nachholen, was waehrenddessen gemerkt wurde
(``vorschlagssperre.gib_frei``)". Der `finally`-Zweig

```python
    finally:
        zeilen.stoppe()
        sperre.release()
```
wird zu
```python
    finally:
        zeilen.stoppe()
        vorschlagssperre.gib_frei(chat_id)
```

3e — die vier `starte*` umstellen. In **allen vier** ersetzt

```python
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
```
den folgenden Block — mit der jeweils passenden Neuauflage des Auftrags:

`starte` (`:867-870`):
```python
    if not vorschlagssperre.nimm(chat_id):
        _sende(conn, tg, e, chat_id, _TEXT_GEMERKT)
        vorschlagssperre.merke(
            chat_id, ART,
            lambda: starte(conn, tg, klm, e, chat_id, anzahl, wunsch),
        )
        return None
```

`starte_geschichte` (`:902-905`):
```python
    if not vorschlagssperre.nimm(chat_id):
        _sende(conn, tg, e, chat_id, _TEXT_GEMERKT)
        vorschlagssperre.merke(
            chat_id, ART_GESCHICHTE,
            lambda: starte_geschichte(conn, tg, klm, e, chat_id, anzahl, wunsch),
        )
        return None
```

`starte_geschichte_szenen` (`:950-953`):
```python
    if not vorschlagssperre.nimm(chat_id):
        _sende(conn, tg, e, chat_id, _TEXT_GEMERKT)
        vorschlagssperre.merke(
            chat_id, ART,
            lambda: starte_geschichte_szenen(
                conn, tg, klm, e, chat_id, anzahl, wunsch
            ),
        )
        return None
```

`starte_feldvorschlag` (`:996-999`):
```python
    if not vorschlagssperre.nimm(chat_id):
        _sende(conn, tg, e, chat_id, _TEXT_GEMERKT)
        vorschlagssperre.merke(
            chat_id, ART_FELDER,
            lambda: starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel),
        )
        return None
```

In allen vier faellt in den `args=(…)` von `threading.Thread` das `sperre`
weg, und der `except`-Zweig um `thread.start()` gibt ueber die gemeinsame
Sperre frei. Beispielhaft `starte` (`:878-889`) vollstaendig:

```python
    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, systemanweisung(anzahl),
              baue_nutzertext(conn, chat_id, anzahl, wunsch), ART, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        vorschlagssperre.gib_frei(chat_id)
        raise
    return thread
```

Dasselbe Muster in `starte_geschichte` (`args=… ART_GESCHICHTE, _fertig`),
`starte_geschichte_szenen` (`args=… ART, _fertig`) und
`starte_feldvorschlag` (`args=… ART_FELDER, _fertig`).

`_TEXT_BESETZT` bleibt als Konstante stehen (kein Aufrufer mehr, aber
**Nutzertext, den eine Uebersetzung braucht** — und die naechste
Nebenlaeufigkeit, die kein Merken erlaubt, greift sie wieder auf).

- [x] **Schritt 4: `schaerfung.py` an dieselbe Sperre haengen**

4a — Import, `interview_theater/schaerfung.py:35`:

```python
from interview_theater import anweisungen, repo, vorschlagssperre, zitat
```

4b — die zwei neuen Konstanten hinter `MELDUNG_OHNE_MATERIAL`
(`interview_theater/schaerfung.py:75`):

```python
#: Was ``starte`` liefert, wenn ein anderer Vorschlagslauf die gemeinsame
#: Sperre haelt (30.09.2026, C7). Bewusst NICHT ``None``: ``None`` heisst
#: "es gab nichts anzustossen", und ``knoepfe.starte_schaerfung`` spielt
#: darauf die vorhandene Lage aus. Gemerkt heisst "kommt noch".
GEMERKT = "gemerkt"

#: Die Wartemeldung. Sie sagt, was passiert -- nicht, dass nichts passiert.
TEXT_GEMERKT = (
    "Ich denke noch ueber etwas anderes nach. Sobald ich damit fertig bin, "
    "lege ich euer Material neben eure Geschichte."
)
```

4c — `_lauf` gibt am Ende frei. `interview_theater/schaerfung.py:246-281`: der
ganze Rumpf wandert in ein `try`, das `finally` gibt frei. Neue Fassung:

```python
def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: mappen, die eine Zeile schicken, weitergehen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still: sie wartet gerade
    darauf (SPEC § 11.1). Die Nachbereitung laeuft in jedem Fall -- der Weg
    durch die Phase darf an einem Mapping-Lauf nicht haengenbleiben.

    **Die gemeinsame Vorschlagssperre wird zuletzt freigegeben** (30.09.2026,
    C7): erst wenn auch die Nachbereitung durch ist, steht die Gruppe nicht
    mehr mitten in einer Frage -- ein Szenenfolge-Vorschlag, der sich
    dazwischen legt, war der gemessene Fehler."""
    anzahl = 0
    from interview_theater import arbeitszeilen

    try:
        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "schaerfung")
        try:
            anzahl, _ = mappe(klm, conn, e, chat_id)
            meldung = MELDUNG.format(anzahl=anzahl) if anzahl else MELDUNG_LEER
        except Exception:
            log.exception("Schaerfung fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "schaerfung_fehlgeschlagen", "Schaerfung fehlgeschlagen",
                )
            except Exception:
                log.exception("Vorfall zur Schaerfung nicht schreibbar")
            meldung = None
        finally:
            zeilen.stoppe()
        if meldung:
            try:
                message_id = tg.sende(chat_id, meldung)
                repo.merke_bot_zeile(conn, chat_id, message_id, e, meldung)
            except Exception:
                log.exception(
                    "Schaerfungs-Meldung fehlgeschlagen, chat_id=%s", chat_id
                )
        if nachbereitung is not None:
            try:
                nachbereitung()
            except Exception:
                log.exception(
                    "Nachbereitung der Schaerfung gescheitert, chat_id=%s", chat_id
                )
    finally:
        vorschlagssperre.gib_frei(chat_id)
```

4d — `starte` nimmt die Sperre. `interview_theater/schaerfung.py:284-297`:

```python
def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt das Mapping an einen eigenen Thread ab -- dasselbe Muster wie
    ``kernzitate.starte`` und ``sprachprofil.starte`` (Zusage 2).

    Liefert den Thread, ``GEMERKT``, wenn ein anderer Vorschlagslauf gerade
    die gemeinsame Sperre haelt (der Auftrag laeuft dann automatisch nach),
    oder ``None``, wenn es nichts anzustossen gab.

    **Die Sperre ist dieselbe wie die der Szenenfolge** (30.09.2026, C7,
    ``vorschlagssperre.py``). Bis dahin hatte dieser Lauf gar keine, und der
    Phaseneintritt legte seine Vorschlaege zeitgleich ueber einen laufenden
    Szenenfolge-Vorschlag."""
    if klm is None:
        log.error("Schaerfung ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    if not vorschlagssperre.nimm(chat_id):
        try:
            message_id = tg.sende(chat_id, TEXT_GEMERKT)
            repo.merke_bot_zeile(conn, chat_id, message_id, e, TEXT_GEMERKT)
        except Exception:
            log.exception("Wartemeldung der Schaerfung fehlgeschlagen, chat_id=%s",
                          chat_id)
        vorschlagssperre.merke(
            chat_id, ART,
            lambda: starte(conn, tg, klm, e, chat_id, nachbereitung),
        )
        return GEMERKT
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
    )
    try:
        thread.start()
    except Exception:
        vorschlagssperre.gib_frei(chat_id)
        raise
    return thread
```

**Kein Aufrufer muss angepasst werden:** `knoepfe/szenen.py:437` prueft
`if schaerfung_modul.starte(...) is None:` — `GEMERKT` ist ein nicht-leerer
String und damit nicht `None`, der Zweig bleibt also aus. Genau deshalb ist
der Rueckgabewert ein Sentinel und nicht `None`.

- [x] **Schritt 5: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagskollision.py tests/test_szenenfolge.py tests/test_geschichte.py tests/test_schaerfung.py
```
Erwartet: alles `passed`, 3 davon neu.

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2713 passed, 1 skipped` (2710 + 3).

- [x] **Schritt 6: Mutationsnachweis**

In `schaerfung.starte` die Wache

```python
    if not vorschlagssperre.nimm(chat_id):
```
zu
```python
    if False:
```
machen (die Schaerfung laeuft also wieder ohne Sperre los). Dann:

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_vorschlagskollision.py
```
Erwartet: **rot** in
`test_schaerfung_wartet_auf_die_laufende_szenenfolge` — `klm.gleichzeitig_max`
ist 2 statt 1, und `ergebnis` ist ein Thread statt `schaerfung.GEMERKT`.

Zweiter Nachweis, fuer die andere Richtung: in `szenenfolge.starte_geschichte_szenen`
das `vorschlagssperre.merke(...)` entfernen (nur Meldung, kein Merken). Dann
ist `test_szenenfolge_wartet_auf_die_laufende_schaerfung` rot bei
`klm.arten.count(szenenfolge.ART) == 1` (es ist 0 — der Auftrag ist weg, genau
der Verlust, den `_TEXT_BESETZT` heute verursacht).

Beide Aenderungen zurueckdrehen, erneut gruen sehen.

- [x] **Schritt 7: Commit**

```bash
git add interview_theater/szenenfolge.py interview_theater/schaerfung.py \
        tests/test_vorschlagskollision.py
git commit -m "$(cat <<'EOF'
Sperre: Schaerfung und Szenenfolge nie gleichzeitig, zweiter Auftrag gemerkt

C7 aus docs/analyse-phase5-chaos-2026-09-06.md. Beide Laeufe teilen jetzt die
Sperre aus vorschlagssperre.py; wer sie nicht bekommt, bekommt eine
Wartemeldung und wird gemerkt, statt abgewiesen zu werden (_TEXT_BESETZT
verlor den Auftrag).

schaerfung.starte liefert dafuer GEMERKT statt None -- knoepfe.starte_schaerfung
prueft auf None und spielt sonst die alte Lage aus.

Grenze: der Merkplatz liegt im Prozess, ein Neustart dazwischen verliert ihn
(wie jede andere Thread-Sperre im Repo).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 3 (Teil 1): Der Knopf „Kuerzer" unter Prosa und unter Szenen

**Entscheidung und ihre Begruendung am Code (D1).** Kuerzen ist **keine** neue
Szenenfolge, sondern die vorhandene Ueberarbeitung mit fester Regie-Notiz.
Welcher Lauf wiederverwendet wird, haengt nur daran, **ob eine Szenennummer
mitkommt** — die Phase entscheidet sich dabei von selbst:

- **Eine Szene** (Nummer da, Phase 6 wie Phase 7): `szene.starte` mit dem
  Auftrag `"Schreib Szene N neu. <Notiz>"`. Genau der Weg, den „Passt, aber
  anders" nimmt (`knoepfe/wirkung.py:352-362` → `ablauf.py:818-824` →
  `szene.starte`). `szene.schreibe` schreibt in Phase 6 nach `prosa` und ab
  Phase 7 nach `volltext` (`szene.py:2033`, `schreibt_prosa`,
  `szene.py:256-274`) und haengt in **beiden** Faellen die Fassung an
  (`szene.py:2093-2104`). Es entsteht keine neue Folge:
  `repo.aktualisiere_szene` fasst Titel, Kurzform, Zusammenfassung und Text
  an und nichts sonst.
- **Die ganze Kurzgeschichte** (keine Nummer, Phase 6):
  `kurzgeschichte.starte(..., regie=<Notiz>)`. Genau der Weg von „Etwas
  aendern" (`knoepfe/wirkung.py:143-150` → `ablauf.py:830-838` →
  `kurzgeschichte.starte`). `lege_szenen_an` laeuft ueber
  `repo.gleiche_szenenfolge_ab(..., ueberschreibbar=("prosa",))`
  (`kurzgeschichte.py:174-176`) — also **abgleichend**: keine Szene wird
  entfernt, `form`/`form_vorschlag`/`stil` bleiben geschuetzt
  (`repo.GESCHUETZTE_SZENENFELDER`, `repo.py:2277-2284`), die Besetzung wird
  gar nicht angefasst, und jeder Abschnitt haengt seine Fassung an
  (`kurzgeschichte.py:182-188`). Die Notiz nennt die **Zahl der Abschnitte
  ausdruecklich**, weil `kurzgeschichte.ANWEISUNG` dem Modell die Wahl der
  Abschnittszahl freistellt (`kurzgeschichte.py:57-60`) — ohne diesen Satz
  waere eine kuerzere Geschichte mit vier statt sechs Abschnitten ein
  plausibles Modellergebnis, und zwei alte Abschnitte blieben mit altem Text
  stehen.

**Kein neuer Anbieterweg, keine neue Tabelle** — die Karte verlangt das
ausdruecklich, und `szenenfassung` traegt es bereits.

**Wo die Knoepfe hinkommen (und wo nicht).** Zwei Orte: unter der fertigen
Kurzgeschichte (`knoepfe.zeige_kurzgeschichte`, Phase 6) und unter einem
frisch geschriebenen Szenentext (`knoepfe.biete_nach_szenentext`, Phase 7 —
und, weil `szene.schreibe` dieselbe Leiste benutzt, auch unter einer einzeln
geschriebenen Prosaszene). **Nicht** unter `knoepfe.zeige_szenentext` („Szene
N ansehen"): dort steht ein Text zum Lesen, und der Knopf „Fruehere
Fassungen" ist die Frage, die dort ansteht — ein bezahlter Lauf unter einer
Leseansicht ist ein Fehlgriff-Risiko ohne Gegenwert.

**Dateien:**
- Anlegen: `interview_theater/kuerzung.py`
- Aendern: `interview_theater/knoepfe/texte.py` (nach `:480` bzw. `:714`)
- Aendern: `interview_theater/knoepfe/szenen.py:20-58` (Importe),
  `:753-786` (`biete_nach_szenentext`), `:1244-1252` (Leiste in
  `zeige_kurzgeschichte`)
- Aendern: `interview_theater/knoepfe/wirkung.py:28-45` (Importe),
  `:143-161` (neuer Handler dazu), `:352-388` (neuer Handler dazu),
  `:1254ff` (`_WIRKUNGEN`)
- Aendern: `interview_theater/knoepfe/__init__.py` (Re-Export)
- Anlegen: `tests/test_kuerzung.py`

**Schnittstellen:**
- Produziert (von A4 genutzt):
  - `kuerzung.PROZENT: int = 25`
  - `kuerzung.TEXT_NOTIZ_SZENE: str` (Platzhalter `{prozent}`)
  - `kuerzung.TEXT_NOTIZ_PROSA: str` (Platzhalter `{prozent}`, `{anzahl}`)
  - `kuerzung.TEXT_NICHTS_ZU_KUERZEN: str`
  - `kuerzung.notiz_fuer_szene() -> str`
  - `kuerzung.notiz_fuer_prosa(anzahl: int) -> str`
  - `kuerzung.nummer_aus_wert(wert: str | None) -> int | None`
  - `kuerzung.starte(conn, tg, klm, e, chat_id: int, nummer: int | None = None) -> str`
    (liefert die Zeile fuer die Knopfquittung)
  - `knoepfe.ART_SZENE_KUERZEN`, `knoepfe.ART_GESCHICHTE_KUERZEN`,
    `knoepfe.TEXT_KUERZEN_KNOPF`
- Konsumiert: `repo.hole_szenen`, `szene.starte`, `kurzgeschichte.starte`
  (alle lokal importiert).

### Schritte

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `tests/test_kuerzung.py`:

```python
"""Kuerzen als eigener Weg (30.09.2026, Massnahme C4).

Der gemessene Fall (docs/analyse-phase5-chaos-2026-09-06.md Abschnitt 4): die
Gruppe bat um Kuerzung, der Bot kannte keinen Kuerzungspfad, das
Gespraechsmodell antwortete mit einer NEUEN Szenenliste, und der Erkenner las
sie als Planung -- aus drei Szenen wurden sechs, und spaeter noch einmal
sechs.

Gemessen wird hier genau das Gegenteil: derselbe Text wird ueberarbeitet, die
Fassung wird ANGEHAENGT, und die Szenenfolge bleibt, wie sie ist.

Kein Netz: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import knoepfe, kuerzung, phasen, repo, szene

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


SZENENTEXT_LANG = (
    "Titel: Am Steg\n"
    "Kurz: Sie treffen sich.\n"
    "Zusammenfassung: Mira und Pal treffen sich am Steg.\n"
    "Anders gemacht: nichts\n"
    "\n"
    "MIRA: Du bist zu spaet.\n"
    "PAL: Ich war da, du hast nicht geschaut.\n"
)


class LLMAttrappe:
    """Liefert einen Szenentext und merkt jeden Nutzertext."""

    def __init__(self, antwort=SZENENTEXT_LANG):
        self.antwort = antwort
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


# --- Die Notiztexte -------------------------------------------------------


def test_die_notiz_nennt_das_kuerzungsziel():
    """25 Prozent steht an EINER Stelle (``kuerzung.PROZENT``) und wandert von
    dort in Notiz und Knopfbeschriftung -- zwei Zahlen waeren zwei
    Wahrheiten."""
    assert kuerzung.PROZENT == 25
    assert "25" in kuerzung.notiz_fuer_szene()
    assert "25" in knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT)


def test_die_prosa_notiz_bindet_die_abschnittszahl():
    """``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Abschnittszahl frei
    (kurzgeschichte.py:57-60). Ohne diesen Satz waere eine kuerzere Geschichte
    mit weniger Abschnitten ein plausibles Ergebnis -- und zwei Abschnitte
    behielten ihren alten, langen Text."""
    notiz = kuerzung.notiz_fuer_prosa(6)
    assert "6" in notiz
    assert "25" in notiz


def test_nummer_aus_wert_liest_nur_zahlen():
    assert kuerzung.nummer_aus_wert("3") == 3
    assert kuerzung.nummer_aus_wert(" 12 ") == 12
    assert kuerzung.nummer_aus_wert("") is None
    assert kuerzung.nummer_aus_wert(None) is None
    assert kuerzung.nummer_aus_wert("Szene drei") is None


# --- Phase 7: eine Szene --------------------------------------------------


@pytest.fixture
def szene7(conn):
    """Phase 7, eine Szene mit Volltext, Form und Besetzung."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Sie treffen sich.")
    figur = repo.figuren(conn, 1)[0]
    repo.setze_szene_figuren(conn, 1, szene_id, [figur["id"]])
    repo.aktualisiere_szene(
        conn, szene_id, "Am Steg", "Sie treffen sich.",
        "MIRA: Du bist zu spaet und ich habe lange gewartet, sehr lange.",
        "Mira wartet.",
    )
    repo.haenge_szenenfassung_an(
        conn, 1, szene_id,
        "MIRA: Du bist zu spaet und ich habe lange gewartet, sehr lange.",
        "Mira wartet.",
    )
    phasen.setze(conn, 1, 7, "test")
    return conn


def test_der_kuerzen_knopf_steht_unter_dem_szenentext(szene7, tg):
    knoepfe.biete_nach_szenentext(szene7, tg, 1, 1, "Szene 1\n\nMIRA: …")
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT) in beschriftungen


def test_kuerzen_schreibt_die_szene_neu_und_haengt_die_fassung_an(szene7, tg, einst):
    conn = szene7
    klm = LLMAttrappe()
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(conn, szene_id))

    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1 neu. "
                          + kuerzung.notiz_fuer_szene())
    assert thread is not None
    thread.join(timeout=20)

    assert len(repo.szenenfassungen(conn, szene_id)) == vorher + 1
    # Der aktuelle Text ist der neue, die alte Fassung steht weiter da.
    aktuell = repo.hole_szene(conn, szene_id)["volltext"]
    assert "du hast nicht geschaut" in aktuell
    assert "sehr lange" in repo.szenenfassungen(conn, szene_id)[0]["volltext"]


def test_der_kuerzen_knopf_traegt_die_notiz_in_den_prompt(szene7, tg, einst):
    """Der Weg hinter dem Knopf, ueber ``knoepfe.behandle`` -- also durch die
    Idempotenz-Wache (Zusage 3) und ohne Modellaufruf im Handler (Zusage 2)."""
    conn = szene7
    klm = LLMAttrappe()
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1\n\nMIRA: …")
    daten = dict(tg.knoepfe[-1][2])[
        knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT)
    ]
    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten)) is True
    # Der Lauf haengt in einem eigenen Thread; auf sein Ende wird ueber die
    # Sperre des Szenenlaufs gewartet.
    assert szene._sperre_fuer(1).acquire(timeout=20)
    szene._sperre_fuer(1).release()
    assert klm.aufrufe, "kein Szenenlauf angestossen"
    assert str(kuerzung.PROZENT) in klm.aufrufe[0]["nutzer"]


def test_kuerzen_legt_keine_neue_szenenfolge_an(szene7, tg, einst):
    """Die Wurzel des Chaos: eine Kuerzungsbitte wurde als Neuaufbau wirksam.
    Nach einer Kuerzung muss es dieselbe Szene mit derselben Nummer und
    derselben Form sein."""
    conn = szene7
    klm = LLMAttrappe()
    vorher = [(s["id"], s["nummer"], s["form"]) for s in repo.hole_szenen(conn, 1)]
    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1 neu. "
                          + kuerzung.notiz_fuer_szene())
    thread.join(timeout=20)
    nachher = [(s["id"], s["nummer"], s["form"]) for s in repo.hole_szenen(conn, 1)]
    assert nachher == vorher


# --- Phase 6: die ganze Kurzgeschichte ------------------------------------


@pytest.fixture
def prosa6(conn):
    """Phase 6, drei Abschnitte mit Prosa -- der Stand nach einem Prosalauf."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Das Gestaendnis"), (3, "Der Morgen")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
        repo.aktualisiere_szene(
            conn, szene_id, titel, None, None, f"{titel} passiert.",
            prosa=f"{titel}: ein langer Abschnitt, sehr lang, viel zu lang.",
        )
    phasen.setze(conn, 1, 6, "test")
    return conn


def test_der_kuerzen_knopf_steht_unter_der_kurzgeschichte(prosa6, tg):
    knoepfe.zeige_kurzgeschichte(prosa6, tg, 1)
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT) in beschriftungen


def test_kuerzen_ohne_nummer_nennt_die_abschnittszahl(prosa6, tg, einst):
    """Drei Abschnitte -> die Notiz bindet auf drei."""
    conn = prosa6
    gemerkt = {}

    def attrappe(c, t, k, ein, chat_id, regie=None):
        gemerkt["regie"] = regie
        return object()

    import interview_theater.kurzgeschichte as kurzgeschichte_modul
    echt = kurzgeschichte_modul.starte
    kurzgeschichte_modul.starte = attrappe
    try:
        kuerzung.starte(conn, tg, LLMAttrappe(), einst, 1)
    finally:
        kurzgeschichte_modul.starte = echt
    assert "3" in gemerkt["regie"]
    assert str(kuerzung.PROZENT) in gemerkt["regie"]


def test_ohne_text_gibt_es_keinen_lauf(conn, tg, einst):
    """Kein bezahlter Lauf auf nichts -- und eine Zeile, die sagt warum."""
    klm = LLMAttrappe()
    phasen.setze(conn, 1, 6, "test")
    meldung = kuerzung.starte(conn, tg, klm, einst, 1)
    assert meldung == kuerzung.TEXT_NICHTS_ZU_KUERZEN
    assert kuerzung.TEXT_NICHTS_ZU_KUERZEN in tg.texte
    assert klm.aufrufe == []


def test_kuerzen_ist_kein_modellaufruf_im_handler():
    """Zusage 2, hier am Handler selbst: ``kuerzung.starte`` gibt an einen
    Thread ab. ``tests/test_knoepfe_struktur.py`` prueft dasselbe am AST des
    ganzen Pakets."""
    assert knoepfe.ART_SZENE_KUERZEN in knoepfe._WIRKUNGEN
    assert knoepfe.ART_GESCHICHTE_KUERZEN in knoepfe._WIRKUNGEN
```

- [ ] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_kuerzung.py
```
Erwartet: Sammelfehler `ModuleNotFoundError: No module named
'interview_theater.kuerzung'`.

- [ ] **Schritt 3: `interview_theater/kuerzung.py` anlegen**

```python
"""Kuerzen als eigener Weg (30.09.2026, Massnahme C4).

**Warum es das gibt.** Am 06.09.2026 bat die Gruppe um eine Kuerzung
(``docs/analyse-phase5-chaos-2026-09-06.md`` Abschnitt 4). Der Bot kannte
keinen Kuerzungspfad: die Kritik lief in den Gespraechszug, das
Gespraechsmodell antwortete mit einer neuen, vollstaendigen Szenenliste im
Fliesstext, und der Absichtserkenner las sie als ``szene_planen``. Aus drei
Szenen wurden sechs, und eine Stunde spaeter noch einmal sechs. Der Bot sagte
dabei selbst, er koenne den Text nicht kuerzen -- er lag ihm nicht vor.

**Was hier NICHT passiert.** Keine neue Szenenfolge, keine Aenderung an
Anzahl, Reihenfolge, Form oder Besetzung, keine neue Tabelle, kein zweiter
Anbieterweg. Kuerzen ist eine **Ueberarbeitung** desselben Textes und benutzt
genau die zwei Laeufe, die es dafuer schon gibt:

* mit Szenennummer -> ``szene.starte`` mit der Notiz im Auftrag, wie bei
  "Passt, aber anders". ``szene.schreibe`` legt das Ergebnis in ``prosa``
  (Phase 6) oder ``volltext`` (ab Phase 7) ab und **haengt die Fassung an**
  (``repo.haenge_szenenfassung_an``).
* ohne Nummer -> ``kurzgeschichte.starte`` mit der Notiz als Regie-Notiz, wie
  bei "Etwas aendern". ``lege_szenen_an`` gleicht ab statt zu ersetzen
  (``repo.gleiche_szenenfolge_ab``) und haengt je Abschnitt eine Fassung an.

**Warum die Prosa-Notiz die Abschnittszahl nennt.**
``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Zahl der Abschnitte
ausdruecklich frei ("Du waehlst die Zahl der Abschnitte selbst"). Eine
kuerzere Geschichte mit vier statt sechs Abschnitten waere also ein
plausibles Ergebnis -- und weil der Abgleich ergaenzend ist, blieben zwei
Abschnitte mit ihrem alten, langen Text stehen. Die Notiz bindet deshalb auf
die Zahl, die dasteht.

**Kein Modellaufruf hier** (Zusage 2): beide Wege geben sofort an einen
eigenen Thread ab. Deshalb darf ein Knopf-Handler diese Funktion rufen.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Das Kuerzungsziel in Prozent. EINE Stelle: Notiz und Knopfbeschriftung
#: lesen von hier (Analyse C4: "Kuerzer (25 %)").
PROZENT = 25

#: Die feste Regie-Notiz fuer EINE Szene. Sie sagt, was gleich bleibt, und
#: nicht nur, was kuerzer wird -- ein Modell, dem man "kuerzer" sagt, kuerzt
#: gern die Handlung mit.
TEXT_NOTIZ_SZENE = (
    "Kuerze diese Szene um etwa {prozent} Prozent. Dieselben Ereignisse, "
    "dieselbe Reihenfolge, dieselben Figuren, dasselbe Ende -- nur knapper: "
    "weniger Wiederholung, kuerzere Repliken, nichts Neues dazu."
)

#: Dieselbe Notiz fuer die ganze Kurzgeschichte, plus die Bindung an die
#: Abschnittszahl (siehe Moduldocstring).
TEXT_NOTIZ_PROSA = (
    "Kuerze die Geschichte um etwa {prozent} Prozent. Behalte genau {anzahl} "
    "Abschnitte mit ihren Titeln und in ihrer Reihenfolge und kuerze "
    "innerhalb der Abschnitte -- dieselben Ereignisse, dasselbe Ende, nichts "
    "Neues dazu."
)

#: Wenn es nichts zu kuerzen gibt. Kein bezahlter Lauf auf nichts, und keine
#: stille Abfuhr: die Gruppe hat gerade gedrueckt.
TEXT_NICHTS_ZU_KUERZEN = "Da ist noch kein Text, den ich kuerzen koennte."


def notiz_fuer_szene() -> str:
    """Die Regie-Notiz fuer eine einzelne Szene."""
    return TEXT_NOTIZ_SZENE.format(prozent=PROZENT)


def notiz_fuer_prosa(anzahl: int) -> str:
    """Die Regie-Notiz fuer die ganze Kurzgeschichte, gebunden an ``anzahl``
    Abschnitte."""
    return TEXT_NOTIZ_PROSA.format(prozent=PROZENT, anzahl=anzahl)


def nummer_aus_wert(wert: str | None) -> int | None:
    """Die Szenennummer aus dem ``wert`` einer Knopfzeile bzw. aus dem Wert
    des Erkenners -- oder None.

    Absichtlich streng: nur eine Zahl. "Szene drei" ist keine Nummer, und ein
    geratener Bezug schriebe die falsche Szene neu."""
    roh = (wert or "").strip()
    if not roh.isdigit():
        return None
    return int(roh)


def _abschnitte_mit_prosa(conn, chat_id: int) -> int:
    """Wie viele Szenen tragen eine Prosafassung? Reine Leseabfrage."""
    from interview_theater import repo, szene as szene_modul

    return sum(
        1 for s in repo.hole_szenen(conn, chat_id) if szene_modul._prosa_von(s)
    )


def _hat_text(conn, chat_id: int, nummer: int) -> bool:
    from interview_theater import repo, szene as szene_modul

    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] != nummer:
            continue
        return bool((s["volltext"] or "").strip() or szene_modul._prosa_von(s))
    return False


def starte(conn, tg, klm, e, chat_id: int, nummer: int | None = None) -> str:
    """Stoesst die Kuerzung an und liefert die Zeile fuer die Knopfquittung.

    ``nummer`` gesetzt -> diese eine Szene; ``nummer`` None -> die ganze
    Kurzgeschichte. **Kein Modellaufruf hier**: beide Wege geben an einen
    eigenen Thread ab (Zusage 2).

    Gibt es nichts zu kuerzen, gibt es keinen Lauf, sondern einen Satz."""
    from interview_theater import kurzgeschichte, szene as szene_modul

    if nummer is not None:
        if not _hat_text(conn, chat_id, nummer):
            tg.sende(chat_id, TEXT_NICHTS_ZU_KUERZEN)
            return TEXT_NICHTS_ZU_KUERZEN
        auftrag = f"Schreib Szene {nummer} neu. {notiz_fuer_szene()}"
        if szene_modul.starte(conn, tg, klm, e, chat_id, auftrag) is None:
            return "Laeuft schon"
        return f"Szene {nummer} wird kuerzer"

    anzahl = _abschnitte_mit_prosa(conn, chat_id)
    if not anzahl:
        tg.sende(chat_id, TEXT_NICHTS_ZU_KUERZEN)
        return TEXT_NICHTS_ZU_KUERZEN
    if kurzgeschichte.starte(
        conn, tg, klm, e, chat_id, notiz_fuer_prosa(anzahl)
    ) is None:
        return "Laeuft schon"
    return "Die Geschichte wird kuerzer"
```

- [ ] **Schritt 4: Die zwei Knopfarten und die Beschriftung anlegen**

In `interview_theater/knoepfe/texte.py`, direkt nach
`TEXT_NAECHSTE_KNOPF = "Naechste Szene"` (`:480`):

```python
#: "Kuerzer" unter einem Szenentext und unter der Kurzgeschichte
#: (30.09.2026, Massnahme C4). Der Prozentwert steht in
#: ``kuerzung.PROZENT`` und wird am Aufrufort eingesetzt -- zwei Zahlen waeren
#: zwei Wahrheiten.
ART_SZENE_KUERZEN = "szene_kuerzen"
TEXT_KUERZEN_KNOPF = "Kuerzer ({prozent} %)"
```

und nach `ART_GESCHICHTE_NEU = "geschichte_neu"` (`:709`):

```python
#: "Kuerzer" unter der ganzen Kurzgeschichte -- dieselbe Beschriftung
#: (``TEXT_KUERZEN_KNOPF``), anderer Weg: ein Prosalauf ueber alle
#: Abschnitte statt ein Szenenlauf.
ART_GESCHICHTE_KUERZEN = "geschichte_kuerzen"
```

- [ ] **Schritt 5: Die Knoepfe in die zwei Leisten haengen**

5a — `interview_theater/knoepfe/szenen.py`: `ART_GESCHICHTE_KUERZEN`,
`ART_SZENE_KUERZEN` und `TEXT_KUERZEN_KNOPF` in den Import aus
`knoepfe.texte` aufnehmen (alphabetisch in die bestehende Liste,
`:20-58`).

5b — `biete_nach_szenentext` (`:753-786`): der Docstring sagt heute „Die vier
Knoepfe"; er wird zu „Die fuenf Knoepfe … · ‚Kuerzer'", mit einem Satz zum
Anlass:

```python
    **"Kuerzer" ist der fuenfte** (30.09.2026, C4): bis dahin gab es keinen
    Kuerzungspfad, und eine Kuerzungsbitte im Chat wurde als neue
    Szenenplanung wirksam. Er wirkt wie "Passt, aber anders", nur mit einer
    festen Regie-Notiz statt einer Rueckfrage (``kuerzung.notiz_fuer_szene``).
```

Und in der Leiste, zwischen `TEXT_ANDERS_KNOPF` und `TEXT_NEU_KNOPF`:

```python
        (
            TEXT_KUERZEN_KNOPF.format(prozent=kuerzung_modul.PROZENT),
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_KUERZEN, str(nummer))),
        ),
```

mit `from interview_theater import kuerzung as kuerzung_modul` als **lokalem
Import am Funktionsanfang** — so wie `biete_szene` es mit `szene`/`szenenfolge`
tut.

5c — `zeige_kurzgeschichte` (`:1244-1252`): einen vierten Knopf hinter
„Etwas aendern":

```python
    from interview_theater import kuerzung as kuerzung_modul
    leiste = [
        (_TEXT_GESCHICHTE_PASST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_PASST, None))),
        (_TEXT_GESCHICHTE_ANDERS_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_ANDERS, None))),
        (TEXT_KUERZEN_KNOPF.format(prozent=kuerzung_modul.PROZENT),
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_KUERZEN, None))),
        (_TEXT_GESCHICHTE_NEU_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_NEU, None))),
    ]
```

Der Docstring bekommt einen Satz: „Seit dem 30.09.2026 sind es vier Wege:
passt / anders / **kuerzer** / ganz neu — ‚kuerzer' ist der eine, der nichts
erfragt, sondern eine feste Notiz mitnimmt."

- [ ] **Schritt 6: Die zwei Handler und die Tabelle**

In `interview_theater/knoepfe/wirkung.py`, hinter
`_wirkung_geschichte_anders` (`:150`):

```python
def _wirkung_geschichte_kuerzen(conn, d: Druck) -> str:
    """"Kuerzer" unter der ganzen Kurzgeschichte (30.09.2026, C4).

    Anders als "Etwas aendern" fragt es nichts: die Notiz steht fest
    (``kuerzung.notiz_fuer_prosa``), und der Lauf startet sofort. Kein
    Modellaufruf hier -- ``kuerzung.starte`` gibt an einen Thread ab
    (Zusage 2)."""
    from interview_theater import kuerzung

    _geschichte_notiz_erwartet.discard(d.chat_id)
    return kuerzung.starte(conn, d.tg, d.klm, d.e, d.chat_id)
```

und hinter `_wirkung_szene_anders` (`:362`):

```python
def _wirkung_szene_kuerzen(conn, d: Druck) -> str:
    """"Kuerzer" unter EINEM Szenentext (30.09.2026, C4).

    Derselbe Ueberarbeitungspfad wie "Passt, aber anders", nur ohne
    Rueckfrage: die Notiz steht fest. Spaetere geschriebene Szenen bekommen
    ihren Pruef-Vermerk wie bei jeder Aenderung (``_melde_spaetere``) -- eine
    kuerzere Szene 2 aendert, was Szene 3 voraussetzen darf. Kein
    Modellaufruf hier (Zusage 2)."""
    from interview_theater import kuerzung

    nummer = kuerzung.nummer_aus_wert(d.wert)
    if nummer is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    meldung = kuerzung.starte(conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    _melde_spaetere(conn, d.tg, d.chat_id, nummer)
    return meldung
```

In `_WIRKUNGEN` (`:1254ff`) zwei Zeilen, bei ihren Geschwistern:

```python
    ART_GESCHICHTE_KUERZEN: _wirkung_geschichte_kuerzen,
```
(direkt nach `ART_GESCHICHTE_ANDERS`) und

```python
    ART_SZENE_KUERZEN: _wirkung_szene_kuerzen,
```
(direkt nach `ART_SZENE_ANDERS`).

Die Importliste aus `knoepfe.texte` am Modulkopf (`:28-45`) um
`ART_GESCHICHTE_KUERZEN`, `ART_SZENE_KUERZEN` ergaenzen.

- [ ] **Schritt 7: Re-Export**

In `interview_theater/knoepfe/__init__.py` in die Importliste aus
`knoepfe.texte` (alphabetisch) aufnehmen: `ART_GESCHICHTE_KUERZEN`,
`ART_SZENE_KUERZEN`, `TEXT_KUERZEN_KNOPF`. Ohne das wuerde
`test_jede_knopfart_hat_genau_einen_handler` die neuen Arten gar nicht sehen
(es liest `dir(knoepfe)`), und die Tests koennten sie nicht ansprechen.

- [ ] **Schritt 8: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_kuerzung.py tests/test_knoepfe_struktur.py
```
Erwartet: alles `passed` (11 neue in `test_kuerzung.py`).

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2726 passed, 1 skipped` — 2713 + 11 neue in `test_kuerzung.py`
**+ 2** in `test_knoepfe_struktur.py`: `test_kein_handler_ruft_das_sprachmodell`
ist ueber `HANDLERNAMEN` parametrisiert und bekommt mit jedem neuen Handler
einen Fall (`_wirkung_szene_kuerzen`, `_wirkung_geschichte_kuerzen`). Wer die
Zahl nachrechnet, rechnet diese zwei mit.

- [ ] **Schritt 9: Mutationsnachweis (drei Stellen)**

1. In `_WIRKUNGEN` die Zeile `ART_SZENE_KUERZEN: _wirkung_szene_kuerzen,`
   entfernen →
   `python3.11 -m pytest -q -p no:cacheprovider tests/test_knoepfe_struktur.py::test_jede_knopfart_hat_genau_einen_handler tests/test_kuerzung.py::test_kuerzen_ist_kein_modellaufruf_im_handler`
   ist **rot**.
2. In `kuerzung.notiz_fuer_prosa` das `anzahl=anzahl` durch `anzahl="einige"`
   ersetzen →
   `tests/test_kuerzung.py::test_kuerzen_ohne_nummer_nennt_die_abschnittszahl`
   ist **rot** (die Notiz nennt die Zahl nicht mehr).
3. In `kuerzung.starte` den Nummern-Zweig auf
   `auftrag = f"Schreib Szene {nummer} neu."` eindampfen (Notiz weg) →
   `tests/test_kuerzung.py::test_der_kuerzen_knopf_traegt_die_notiz_in_den_prompt`
   ist **rot**.

Alle drei zuruecknehmen, erneut gruen sehen.

- [ ] **Schritt 10: Commit**

```bash
git add interview_theater/kuerzung.py interview_theater/knoepfe/texte.py \
        interview_theater/knoepfe/szenen.py interview_theater/knoepfe/wirkung.py \
        interview_theater/knoepfe/__init__.py tests/test_kuerzung.py
git commit -m "$(cat <<'EOF'
Kuerzen: Knopf unter Prosa (Phase 6) und unter Szenen (Phase 7)

C4 aus docs/analyse-phase5-chaos-2026-09-06.md. Kuerzen ist eine
Ueberarbeitung mit fester Regie-Notiz (25 %) und wiederverwendet die zwei
vorhandenen Laeufe: szene.starte je Szene, kurzgeschichte.starte fuer die
ganze Geschichte. Beide haengen ihre Fassung an (szenenfassung) -- keine neue
Tabelle, kein neuer Anbieterweg, keine neue Szenenfolge.

Die Prosa-Notiz bindet auf die vorhandene Abschnittszahl, weil
kurzgeschichte.ANWEISUNG dem Modell die Zahl freistellt und der Abgleich
ergaenzend ist: sonst blieben Abschnitte mit altem Text stehen.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 4 (Teil 2a): Die Erkenner-Art `szene_kuerzen` im Code

**Warum eine eigene Art und nicht `szene_schreiben`.** `szene_schreiben`
nennt heute in Punkt 17 sogar das Beispiel „schreib Szene 3 nochmal, aber
kuerzer" (`interview_theater/prompts/erkenner.md:111`). Drei Unterschiede
machen eine eigene Art nötig, und alle drei sind Code, nicht Geschmack:
(1) `szene_kuerzen` braucht **keine** Szenennummer — „mach das kuerzer" nach
einer Kurzgeschichte trifft die ganze Geschichte, und die schreibt
`kurzgeschichte.starte`, nicht `szene.starte`; (2) der `wert` von
`szene_schreiben` ist ein **ausformulierter Auftrag** („Ein wert aus einem
Wort sagt dem Schreibauftrag nichts", `erkenner.md:120`) — bei einer Kuerzung
gibt es nichts auszuformulieren, der Text steht schon, und die Notiz ist fest;
(3) `szene_schreiben` landet ueber `szene.starte` im **Neu**-Schreiben, wo
`_diese_szene_text` den alten Text als „soll ueberarbeitet werden" mitgibt
oder — mit `NEU_MARKER` — gerade nicht; Kuerzen ist immer das erste.

**Der Prompt bleibt in dieser Aufgabe unangetastet.** Solange
`prompts/erkenner.md` die Art nicht lehrt, kann das Modell sie nicht liefern,
und Korpusfaelle dafuer waeren garantierte Falsch-Negative. Genau dafuer gibt
es `tests/test_korpus.OHNE_KORPUSFAELLE` (`tests/test_korpus.py:218-227`):
die Art wird dort **voruebergehend** eingetragen und in Aufgabe 5 wieder
herausgenommen, zusammen mit Prompt und Korpusfaellen. Das ist der im Repo
dokumentierte Weg, nicht eine Abkuerzung.

**Dateien:**
- Aendern: `interview_theater/erkenner.py:65-141` (`ARTEN`),
  `:1190-1250` (`_wende_eine_an`), `:1577-1605` (neben `_starte_szene`),
  `:1734-1819` (`laufe`)
- Aendern: `tests/test_erkenner.py:163-193` (`test_arten_enthaelt_alle_werte`),
  plus vier neue Tests
- Aendern: `tests/test_korpus.py:227` (`OHNE_KORPUSFAELLE`)

**Schnittstellen:**
- Konsumiert aus A3: `kuerzung.starte`, `kuerzung.nummer_aus_wert`.
- Produziert:
  `erkenner._starte_kuerzung(klm, tg, conn, e, chat_id, aenderungen) -> None`
  und `"szene_kuerzen"` in `erkenner.ARTEN` (und damit im Schema-Enum,
  `erkenner.py:199`).

### Schritte

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

1a — `tests/test_erkenner.py:163-193`, in `test_arten_enthaelt_alle_werte`
das Set ergaenzen (bei `szene_schreiben`):

```python
        "verworfen", "entschieden", "szene_schreiben", "phase_setzen",
        # 30.09.: "mach das kuerzer" -- eine Ueberarbeitung desselben Textes,
        # nicht ein neuer (docs/analyse-phase5-chaos-2026-09-06.md C10).
        "szene_kuerzen",
```

1b — vier neue Tests, hinter dem `szene_schreiben`-Block
(`tests/test_erkenner.py`, nach `test_ohne_erkannten_auftrag_laeuft_keine_szene`):

```python
# ---------------------------------------------------------------------------
# szene_kuerzen (30.09.2026, C10): eine Kuerzung ist keine Planung
# ---------------------------------------------------------------------------


def test_szene_kuerzen_ist_im_schema_enum():
    enum = erkenner.SCHEMA["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    assert "szene_kuerzen" in enum


def test_szene_kuerzen_veraendert_den_arbeitsstand_nicht(conn, einst):
    """Wie ``szene_schreiben``: kein Schreibpfad, keine Notiert-Zeile. Der
    Lauf meldet sich selbst."""
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "szene_kuerzen", "wert": "2"}]
    )

    assert wirkliche == []
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert erkenner.baue_meldung([{"art": "szene_kuerzen", "wert": "2"}]) is None


def test_szene_kuerzen_gilt_nicht_aus_einer_aufnahme():
    """Was eine interviewte Person ueber Laenge sagt, ist Material und nie
    ein Auftrag der Gruppe (N1). ``ARTEN_IN_AUFNAHME`` bleibt bei drei."""
    assert "szene_kuerzen" not in erkenner.ARTEN_IN_AUFNAHME
    assert len(erkenner.ARTEN_IN_AUFNAHME) == 3


def test_laufe_stoesst_die_kuerzung_mit_nummer_an(conn, einst, monkeypatch):
    from interview_theater import kuerzung

    gesehen = []
    monkeypatch.setattr(
        kuerzung, "starte",
        lambda conn, tg, klm, e, chat_id, nummer=None: gesehen.append(
            (chat_id, nummer)
        ),
    )
    _nachricht(conn, 1, 1, "szene 2 ist zu lang, mach sie kuerzer")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_kuerzen", "wert": "2"},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert gesehen == [(1, 2)]


def test_laufe_stoesst_die_kuerzung_ohne_nummer_an(conn, einst, monkeypatch):
    """Nach einer Kurzgeschichte gibt es keine Szenennummer -- dann ist die
    ganze Geschichte gemeint (``kuerzung.starte`` ohne Nummer)."""
    from interview_theater import kuerzung

    gesehen = []
    monkeypatch.setattr(
        kuerzung, "starte",
        lambda conn, tg, klm, e, chat_id, nummer=None: gesehen.append(
            (chat_id, nummer)
        ),
    )
    _nachricht(conn, 1, 1, "kuerz die geschichte mal ein")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_kuerzen", "wert": ""},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert gesehen == [(1, None)]


def test_laufe_kuerzt_hoechstens_einmal_je_lauf(conn, einst, monkeypatch):
    """Wie bei ``szene_schreiben``: die zweite liefe in die Sperre des
    Szenenlaufs und ergaebe nur eine Nachricht fuer nichts."""
    from interview_theater import kuerzung

    gesehen = []
    monkeypatch.setattr(
        kuerzung, "starte",
        lambda conn, tg, klm, e, chat_id, nummer=None: gesehen.append(nummer),
    )
    _nachricht(conn, 1, 1, "kuerz szene 2 und szene 3")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_kuerzen", "wert": "2"},
        {"art": "szene_kuerzen", "wert": "3"},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert gesehen == [2]
```

1c — `tests/test_korpus.py:227`:

```python
#: Arten, die der Korpus (noch) nicht belegt, weil ``prompts/erkenner.md``
#: sie nicht lehrt. ``geschichte_setzen`` ist seit dem Umbau vom 05.09.2026
#: nachts im Code (der Regelweg dorthin ist der Vorschlagsblock mit seinen
#: Knoepfen, ``knoepfe._speichere_geschichte``) -- der Erkenner-Prompt wurde
#: bewusst NICHT angefasst, weil ein Korpuslauf gegen das echte Modell in
#: derselben Nacht nicht moeglich war. Faelle dafuer aufzunehmen, ohne den
#: Prompt zu aendern, hiesse: garantierte Falsch-Negative im naechsten Lauf.
#: **Wer erkenner.md um diese Art erweitert, nimmt sie hier heraus und legt
#: zwei Korpusfaelle an.**
#:
#: ``szene_kuerzen`` steht hier nur fuer EINEN Commit (30.09.2026): der Code
#: kommt zuerst, damit die Verdrahtung getestet ist, Prompt und Korpus im
#: naechsten Schritt -- dann verschwindet die Art hier wieder.
OHNE_KORPUSFAELLE = {"geschichte_setzen", "szene_kuerzen"}
```

- [ ] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_erkenner.py tests/test_korpus.py
```
Erwartet: rot in `test_arten_enthaelt_alle_werte`
(`AssertionError` — `szene_kuerzen` fehlt in `erkenner.ARTEN`),
`test_szene_kuerzen_ist_im_schema_enum`,
`test_laufe_stoesst_die_kuerzung_mit_nummer_an`,
`test_laufe_stoesst_die_kuerzung_ohne_nummer_an`,
`test_laufe_kuerzt_hoechstens_einmal_je_lauf`.
`test_szene_kuerzen_gilt_nicht_aus_einer_aufnahme` und
`test_szene_kuerzen_veraendert_den_arbeitsstand_nicht` sind schon gruen — das
ist richtig so, sie halten Eigenschaften fest, die nicht kaputtgehen duerfen.

- [ ] **Schritt 3: `ARTEN` erweitern**

`interview_theater/erkenner.py`, in `ARTEN` direkt nach `"szene_schreiben"`
(`:112`):

```python
    # Seit 30.09.2026 (Massnahme C10 aus
    # docs/analyse-phase5-chaos-2026-09-06.md): "mach das kuerzer". Wie
    # ``szene_schreiben`` ohne Schreibpfad -- sie stoesst eine Handlung an
    # (interview_theater/kuerzung.py) -- aber mit einem anderen Ziel: derselbe
    # Text wird KUERZER, er wird nicht neu.
    #
    # Der gemessene Anlass: am 06.09. gab es diesen Weg nicht, die
    # Kuerzungsbitte lief in den Gespraechszug, das Gespraechsmodell
    # antwortete mit einer neuen Szenenliste, und der Erkenner las sie als
    # ``szene_planen``. Aus drei Szenen wurden sechs.
    #
    # ``wert``: die Szenennummer als Zahl, oder leer -- dann ist die ganze
    # Kurzgeschichte gemeint. Auf "im Zweifel kein Eintrag" kalibriert wie
    # ``szene_schreiben``: es kostet einen minutenlangen, bezahlten Lauf.
    "szene_kuerzen",
```

- [ ] **Schritt 4: Kein Schreibpfad**

`interview_theater/erkenner.py`, in `_wende_eine_an` direkt nach dem
`szene_schreiben`-Zweig (`:1246`):

```python
    if art == "szene_kuerzen":
        # Kein Schreibpfad, aus demselben Grund wie szene_schreiben: eine
        # Kuerzung ist kein Arbeitsstandfeld, sondern ein Lauf. Den stoesst
        # laufe() an (dort gibt es tg und klm).
        return None
```

In `_sammle_meldbares` ist **nichts** zu tun: `szene_kuerzen` steht in keinem
der Woerterbuecher `einzeln`/`mehrfach` und bleibt damit still — richtig, denn
der Lauf meldet sich selbst (`szene._TEXT_ANGEKUENDIGT` bzw.
`kurzgeschichte._TEXT_LAEUFT`).

- [ ] **Schritt 5: Den Anstoss in `laufe`**

`interview_theater/erkenner.py`, hinter `_starte_szene` (`:1605`):

```python
def _starte_kuerzung(klm, tg, conn, e, chat_id: int,
                     aenderungen: list[dict]) -> None:
    """Stoesst die Kuerzung an, wenn der Erkenner eine erkannt hat (art
    ``szene_kuerzen``, interview_theater/kuerzung.py).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``: dort
    wird nur in die Datenbank geschrieben, hier faellt eine Nachricht in die
    Gruppe an und ein minutenlanger Modellaufruf. ``kuerzung.starte`` gibt ihn
    sofort an einen eigenen Thread ab.

    **Hoechstens EINE je Lauf**, wie beim Schreibauftrag: die zweite liefe in
    die Sperre je chat_id und ergaebe nur ein 'ich schreibe gerade noch'.

    Ein leerer ``wert`` ist kein Fehler, sondern die Aussage "die ganze
    Geschichte": nach einem Prosalauf gibt es keine Szenennummer zu nennen."""
    from interview_theater import kuerzung  # spaeter Import, haelt den Modulkopf frei

    treffer = next(
        (a for a in aenderungen if a.get("art") == "szene_kuerzen"), None
    )
    if treffer is None:
        return
    nummer = kuerzung.nummer_aus_wert(treffer.get("wert"))
    try:
        kuerzung.starte(conn, tg, klm, e, chat_id, nummer)
    except Exception:
        log.exception("Kuerzung konnte nicht gestartet werden, chat_id=%s", chat_id)
```

und in `laufe` direkt hinter dem `_starte_szene`-Aufruf (`:1782`):

```python
        # Und dieselbe Bauart fuer die Kuerzung (30.09.2026, C10): aus den
        # erkannten Aenderungen, weil sie wie ``szene_schreiben`` nichts in
        # den Arbeitsstand schreibt und in ``wirkliche`` deshalb nie auftaucht.
        _starte_kuerzung(klm, tg, conn, e, chat_id, aenderungen)
```

- [ ] **Schritt 6: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_erkenner.py tests/test_korpus.py tests/test_kuerzung.py
```
Erwartet: alles `passed`, 6 neu in `test_erkenner.py`.

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2732 passed, 1 skipped` (2726 + 6).

- [ ] **Schritt 7: Mutationsnachweis**

Den Aufruf `_starte_kuerzung(klm, tg, conn, e, chat_id, aenderungen)` in
`laufe` wieder entfernen →

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_erkenner.py -k kuerz
```
Erwartet: **rot** in `test_laufe_stoesst_die_kuerzung_mit_nummer_an`,
`test_laufe_stoesst_die_kuerzung_ohne_nummer_an`,
`test_laufe_kuerzt_hoechstens_einmal_je_lauf` (`gesehen == []`).

Zweitens: in `_starte_kuerzung` das `next(...)` durch
`[a for a in aenderungen if a.get("art") == "szene_kuerzen"]` mit einer
Schleife ersetzen (also alle starten) →
`test_laufe_kuerzt_hoechstens_einmal_je_lauf` ist rot (`[2, 3]` statt `[2]`).

Beides zuruecknehmen, erneut gruen sehen.

- [ ] **Schritt 8: Commit**

```bash
git add interview_theater/erkenner.py tests/test_erkenner.py tests/test_korpus.py
git commit -m "$(cat <<'EOF'
Erkenner: art szene_kuerzen -- der Code (Prompt und Korpus folgen)

C10 aus docs/analyse-phase5-chaos-2026-09-06.md. Wie szene_schreiben ohne
Schreibpfad: laufe() stoesst hoechstens eine Kuerzung je Lauf an, ueber
kuerzung.starte in einem eigenen Thread. Leerer wert = die ganze
Kurzgeschichte, Zahl = diese Szene.

ARTEN_IN_AUFNAHME bleibt bei drei: was eine interviewte Person ueber Laenge
sagt, ist Material und nie ein Auftrag der Gruppe (N1).

szene_kuerzen steht fuer EINEN Commit in test_korpus.OHNE_KORPUSFAELLE --
Korpusfaelle ohne gelehrten Prompt waeren garantierte Falsch-Negative.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 5 (Teil 2b): Prompt, Korpus, Schnappschuss

**Was hier schiefgehen kann, und warum es einen eigenen Task braucht.** Eine
Aenderung an `interview_theater/prompts/erkenner.md` macht **drei** Tests rot,
und zwei davon sind Massstaebe, die absichtlich nicht automatisch
mitwandern:

1. `tests/test_korpus.py::test_erkenner_jede_art_mindestens_zweimal` — braucht
   zwei Positivfaelle (loest sich, sobald `szene_kuerzen` aus
   `OHNE_KORPUSFAELLE` heraus und in den Korpus hinein wandert).
2. `tests/test_profil_bitgleich.py::test_ohne_variable_wie_vor_dem_umbau` und
   `::test_dortmund_wie_vor_dem_umbau` — vergleichen `erkenner.prompt()` gegen
   die Zeile `prompt erkenner` in
   `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` (heute
   `a16cf9e4… 33680`). `scripts/prompt_schnappschuss.py` schreibt diesen
   Massstab **bewusst nie neu** (`ergaenze()` haengt nur *neue* Abschnitte an,
   Docstring `:173-189`) — die Zeile wird von Hand ersetzt, und der Commit
   sagt warum.
3. `tests/test_profil_bitgleich.py::test_golden_dump_ohne_variable[04-erkenner]`
   und `::test_golden_dump_mit_dortmund[04-erkenner]` — vergleichen dieselbe
   Zeichenkette gegen den SYSTEM-Block in
   `docs/prompt-audit/2026-09-06/04-erkenner.txt` (Zeile 3 bis vor `=== NUTZER`).
   Ebenfalls von Hand nachzuziehen.

**Der Korpuslauf gegen das echte Modell ist NICHT Teil der automatisierten
Abnahme.** Er kostet Geld, braucht `betrieb/<gruppe>.env` und laeuft nie
automatisch. Er steht unten als eigener, **manuell auszufuehrender** Schritt
mit Kommando und erwarteter Ausgabe und ist mit `ANNAHME:` markiert.

**Dateien:**
- Aendern: `interview_theater/prompts/erkenner.md:14-18`, `:107-120`,
  neuer Punkt 23 hinter `:161` (nach `festlegung_setzen`)
- Aendern: `korpus/erkenner.jsonl` (5 neue Zeilen am Ende)
- Aendern: `tests/test_korpus.py:227` (Art heraus), plus zwei neue Tests
- Aendern: `docs/prompt-audit/schnappschuss-vor-profilumbau.txt:8`
- Aendern: `docs/prompt-audit/2026-09-06/04-erkenner.txt` (SYSTEM-Block)

**Schnittstellen:** keine neuen Symbole; `erkenner.prompt()` liefert einen
anderen Text.

### Schritte

- [ ] **Schritt 1: Die fehlschlagenden Korpus-Tests schreiben**

1a — `tests/test_korpus.py:227` wieder auf den Stand von vor Aufgabe 4
bringen (Kommentar zu `szene_kuerzen` entfernen):

```python
OHNE_KORPUSFAELLE = {"geschichte_setzen"}
```

1b — zwei neue Tests, hinter `test_erkenner_traegt_die_auffangart`:

```python
#: ``szene_kuerzen`` (30.09.2026, C10) ist auf "im Zweifel kein Eintrag"
#: kalibriert wie ``szene_schreiben``: sie loest einen minutenlangen,
#: bezahlten Lauf aus. Also mehr Negativ- als Positivfaelle -- und die
#: Negativen sind die wichtigeren, weil die Abgrenzung nicht an einem Wort
#: haengt ("kuerzer" steht in beiden), sondern daran, ob eine Aufforderung
#: dasteht.
PRAEFIX_KUERZEN = "sk0"
MIN_POSITIV_KUERZEN = 2
MIN_NEGATIV_KUERZEN = 3


def test_erkenner_traegt_szene_kuerzen(erkenner_faelle):
    positiv = [
        f for f in erkenner_faelle
        if any(a["art"] == "szene_kuerzen" for a in f["erwartet"])
    ]
    negativ = [
        f for f in erkenner_faelle
        if not f["erwartet"] and f["id"].startswith(PRAEFIX_KUERZEN)
    ]
    assert len(positiv) >= MIN_POSITIV_KUERZEN, f"nur {len(positiv)} Positivfaelle"
    assert len(negativ) >= MIN_NEGATIV_KUERZEN, f"nur {len(negativ)} Negativfaelle"


#: Die drei Faelle, die schon vor ``szene_kuerzen`` an der Grenze lagen und
#: ihr Sollverhalten behalten MUESSEN. Sie sind der eigentliche Nachweis der
#: Kalibrierung: n20 und n27 sind Kritik ohne Aufforderung, fl04 ist eine
#: Vorgabe fuer alles Kommende und kein vorhandener Text.
GRENZFAELLE_LAENGE = {
    "n20-szene-besprechen-kein-auftrag": [],
    "n27-entfernen-szene-kuerzen": [],
    "fl04-festlegung-stil-laenge": ["festlegung_setzen"],
}


def test_erkenner_haelt_die_laengengrenzfaelle(erkenner_faelle):
    """Die neue art darf die drei Faelle nicht an sich ziehen.

    ``szene_kuerzen`` lebt genau in ihrer Nachbarschaft: "zu lang", "da
    muesste einiges raus", "hoechstens eine Seite ab jetzt". Verschiebt sich
    einer von ihnen, ist die Abgrenzung im Prompt zu weit geraten."""
    nach_id = {f["id"]: f for f in erkenner_faelle}
    for fall_id, arten in GRENZFAELLE_LAENGE.items():
        assert fall_id in nach_id, f"Grenzfall {fall_id} fehlt im Korpus"
        assert [a["art"] for a in nach_id[fall_id]["erwartet"]] == arten, (
            f"{fall_id}: Sollwert verschoben"
        )
```

- [ ] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_korpus.py
```
Erwartet: rot in `test_erkenner_jede_art_mindestens_zweimal`
(`zu selten belegte Arten: {'szene_kuerzen': 0}`) und in
`test_erkenner_traegt_szene_kuerzen` (`nur 0 Positivfaelle`).
`test_erkenner_haelt_die_laengengrenzfaelle` ist bereits gruen — sie haelt
den heutigen Stand fest, damit er nicht in Schritt 4 mitwandert.

- [ ] **Schritt 3: Den Prompt lehren**

3a — `interview_theater/prompts/erkenner.md:14-18`: aus zwei Ausnahmen werden
drei, und die Zahl im Kopf wandert mit.

vorher:
```
Zwei Ausnahmen, und nur diese beiden: **szene_schreiben** (loest einen
minutenlangen Schreibauftrag aus) und **entfernen** (nimmt etwas weg). Dort
gilt weiterhin: im Zweifel kein Eintrag.

Du erkennst genau dreiundzwanzig Arten von Aenderungen. Jede Aenderung ist ein
Objekt mit "art" und "wert":
```

nachher:
```
Drei Ausnahmen, und nur diese drei: **szene_schreiben** (loest einen
minutenlangen Schreibauftrag aus), **szene_kuerzen** (dasselbe fuer eine
Ueberarbeitung) und **entfernen** (nimmt etwas weg). Dort gilt weiterhin: im
Zweifel kein Eintrag.

Du erkennst genau vierundzwanzig Arten von Aenderungen. Jede Aenderung ist ein
Objekt mit "art" und "wert":
```

3b — `interview_theater/prompts/erkenner.md:107-111`: das Beispiel „schreib
Szene 3 nochmal, aber kuerzer" gehoert ab jetzt zur neuen Art und muss aus
Punkt 17 heraus, sonst sind zwei Arten fuer dasselbe Beispiel zustaendig
(ein Fakt, zwei Stellen — genau das, was der Prompt-Audit vom 06.09. verbietet).

vorher:
```
17. szene_schreiben        -- wert: der Auftrag in einem Satz, mit
    Szenennummer, wenn eine genannt wird ("Szene 2: Maria kommt am Bahnhof
    an und trifft Elif"). Die Gruppe fordert DICH auf, jetzt einen
    Szenentext zu schreiben ("schreib uns die Szene", "mach daraus einen
    Dialog", "schreib Szene 3 nochmal, aber kuerzer").
```

nachher:
```
17. szene_schreiben        -- wert: der Auftrag in einem Satz, mit
    Szenennummer, wenn eine genannt wird ("Szene 2: Maria kommt am Bahnhof
    an und trifft Elif"). Die Gruppe fordert DICH auf, jetzt einen
    Szenentext zu schreiben ("schreib uns die Szene", "mach daraus einen
    Dialog", "schreib Szene 3 nochmal, ganz anders"). Soll derselbe Text
    bloss KUERZER werden, ist das szene_kuerzen (Punkt 23).
```

3c — der neue Punkt 23, hinter dem Block zu `festlegung_setzen` und **vor**
dem Abschnitt mit den Abgrenzungen (also hinter `erkenner.md:161`, vor der
Zeile „Bereiche, genau eines dieser Woerter:"? **Nein** — hinter dem
vollstaendigen Punkt 22 samt seinen Bereichen, direkt bevor der erste
Abgrenzungs-Abschnitt beginnt. Die genaue Zeile findet man mit
`grep -n 'Abgrenzung "festlegung_setzen"' interview_theater/prompts/erkenner.md`
und fuegt davor ein):

```
23. szene_kuerzen          -- wert: die Szenennummer als Zahl ("3"), oder
    leer (""), wenn keine genannt ist. Die Gruppe fordert DICH auf, einen
    schon geschriebenen Text KUERZER zu machen ("mach das kuerzer", "kuerz
    Szene 3 ein", "schreib es knapper", "das muss kuerzer werden"). Steht
    keine Nummer da, ist der ganze Text gemeint, der zuletzt entstanden ist
    -- schreib dann den leeren wert, rate keine Nummer.

    **Im Zweifel kein Eintrag**, wie bei szene_schreiben: es kostet die
    Gruppe Minuten Wartezeit und einen bezahlten Lauf.

    Abgrenzung nach drei Seiten:

    * **Kritik an der Laenge ist noch keine Aufforderung.** "die Szene ist
      mir zu lang, was meint ihr", "der Mittelteil zieht sich", "da muesste
      einiges raus" -- das ist ein Gespraech ueber den Text, kein Auftrag.
      Erst "mach es kuerzer", "kuerz das", "schreib es knapper" ist einer.
    * **Eine Vorgabe fuer alles Kommende ist festlegung_setzen** (Punkt 22),
      nicht szene_kuerzen: "hoechstens eine Seite pro Szene ab jetzt" sagt
      nichts ueber einen vorhandenen Text, sondern ueber alle kuenftigen.
    * **Kuerzen ist kein Entfernen** (Punkt 19): die Szene bleibt, nur ihr
      Text wird knapper. Und es ist kein szene_schreiben (Punkt 17): dort
      entsteht ein ANDERER Text, hier derselbe in kuerzer.
```

- [ ] **Schritt 4: Die fuenf Korpusfaelle**

An `korpus/erkenner.jsonl` **anhaengen** — je Fall eine Zeile, keine
Leerzeile, echte Umlaute wie im Rest der Datei. Alle Namen frei erfunden und
nicht aus dem Projektumfeld.

```json
{"id": "sk01-kuerzen-mit-nummer", "arbeitsstand": {"kernthema": "Warten"}, "nachrichten": [{"absender": "Alev", "text": "szene 3 ist mir zu lang geworden"}, {"absender": "Tarek", "text": "mach sie kürzer bitte"}], "erwartet": [{"art": "szene_kuerzen", "wert": "3"}], "zustimmung": true, "notiz": "Kritik PLUS Aufforderung -- das ist der Auftrag. Die Nummer steht da, also gehört sie in den wert (C10, 30.09.2026)."}
{"id": "sk02-kuerzen-ohne-nummer", "arbeitsstand": {}, "nachrichten": [{"absender": "Nesrin", "text": "puh, die ganze Geschichte ist echt viel Text"}, {"absender": "Nesrin", "text": "kürz das mal ein, so ein Viertel weniger"}], "erwartet": [{"art": "szene_kuerzen", "wert": ""}], "zustimmung": true, "notiz": "Nach dem Prosalauf gibt es keine Szenennummer -- leerer wert heißt 'die ganze Geschichte'. Eine geratene Nummer schriebe die falsche Szene neu."}
{"id": "sk03-laenge-nur-besprochen", "arbeitsstand": {}, "nachrichten": [{"absender": "Alev", "text": "der Text läuft schon ganz gut"}, {"absender": "Tarek", "text": "vielleicht ist er einen Tick lang"}], "erwartet": [], "notiz": "Negativfall: über die Länge reden ist keine Aufforderung. Ein Falsch-Positiv kostet hier zwei Minuten Wartezeit und eine unbestellte Nachricht."}
{"id": "sk04-kuerzen-erst-ueberlegt", "arbeitsstand": {}, "nachrichten": [{"absender": "Nesrin", "text": "sollen wir Szene 2 kürzen?"}, {"absender": "Alev", "text": "weiß nicht, lass uns erst nochmal durchlesen"}], "erwartet": [], "notiz": "Negativfall: die Frage ist gestellt und ausdrücklich nicht entschieden. Derselbe Schnitt wie bei n28 (Fragen nur überlegt)."}
{"id": "sk05-kuerzer-meint-nicht-den-text", "arbeitsstand": {}, "nachrichten": [{"absender": "Tarek", "text": "wir sollten die Probe kürzer machen"}, {"absender": "Nesrin", "text": "ja, anderthalb Stunden reichen"}], "erwartet": [], "notiz": "Negativfall: 'kürzer' steht da, aber es geht um die Probe, nicht um einen Text. Die Abgrenzung hängt am Ziel, nicht am Wort."}
```

Die drei bestehenden Grenzfaelle **bleiben unveraendert**: `n20` und `n27`
mit leerem `erwartet`, `fl04` mit `festlegung_setzen`. Genau das haelt
`test_erkenner_haelt_die_laengengrenzfaelle` fest.

- [ ] **Schritt 5: Den Massstab nachziehen (die zwei Dateien von Hand)**

5a — die neue Pruefsumme ermitteln:

```bash
python3.11 -m scripts.prompt_schnappschuss | grep "prompt erkenner"
```
Erwartet: eine Zeile `<sha256>  <laenge>  prompt erkenner` mit **anderem**
Hash und anderer Laenge als `a16cf9e4… 33680`.

Diese Zeile ersetzt **genau** Zeile 8 in
`docs/prompt-audit/schnappschuss-vor-profilumbau.txt`. Keine andere Zeile
darf sich aendern — die Kontrolle:

```bash
git diff --stat docs/prompt-audit/schnappschuss-vor-profilumbau.txt
python3.11 -m scripts.prompt_schnappschuss \
  | diff - docs/prompt-audit/schnappschuss-vor-profilumbau.txt
```
Erwartet: `1 file changed, 1 insertion(+), 1 deletion(-)` bzw. kein
`diff`-Ausgang.

> **Warum von Hand und nicht mit `--ergaenze`:** `ergaenze()` haengt nur neue
> Abschnitte an und schreibt den Massstab nie um (`prompt_schnappschuss.py`
> Docstring `:173-180`) — „eine geaenderte Zeile bliebe sonst unbemerkt, und
> genau die soll der Bitgleichheits-Test finden". Dass sich hier eine Zeile
> aendert, ist **der Inhalt dieses Commits** und gehoert in seine Nachricht,
> nicht in ein Skript.

5b — den Golden-Dump nachziehen. Der SYSTEM-Block in
`docs/prompt-audit/2026-09-06/04-erkenner.txt` reicht von Zeile 4 bis zur
Leerzeile vor `=== NUTZER `. Ihn erzeugen und einsetzen:

```bash
python3.11 - <<'PY'
from pathlib import Path
import re
from interview_theater import erkenner

pfad = Path("docs/prompt-audit/2026-09-06/04-erkenner.txt")
alt = pfad.read_text(encoding="utf-8")
neu_system = erkenner.prompt()
kopf = (f"=== SYSTEM ({len(neu_system)} Zeichen, "
        f"~{len(neu_system) // 4} Token) ===")
ersetzt, anzahl = re.subn(
    r"=== SYSTEM \(\d+ Zeichen, ~\d+ Token\) ===\n.*?\n\n=== NUTZER ",
    lambda _m: f"{kopf}\n{neu_system}\n\n=== NUTZER ",
    alt, count=1, flags=re.S,
)
assert anzahl == 1, "SYSTEM-Block nicht gefunden"
pfad.write_text(ersetzt, encoding="utf-8")
print(f"SYSTEM-Block ersetzt: {len(neu_system)} Zeichen")
PY
```

ANNAHME: die Token-Zahl im Kopf ist eine Anzeige und wird von keinem Test
gelesen — `tests/test_profil_bitgleich.py:133-136` liest nur den Rumpf
zwischen den Markierungen (`\d+` im Muster). Nachzupruefen, indem der Test
nach dem Lauf gruen ist; ist er es nicht, ist die Zahl anders zu bilden.

- [ ] **Schritt 6: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_korpus.py tests/test_profil_bitgleich.py tests/test_anweisungen.py tests/test_erkenner.py
```
Erwartet: alles `passed`, 2 neu in `test_korpus.py`.

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2734 passed, 1 skipped` (2732 + 2).

```bash
python3.11 -m scripts.pruefe_profil dortmund-2026
```
Erwartet: Exit 0.

- [ ] **Schritt 7: Mutationsnachweis**

1. Punkt 23 aus `interview_theater/prompts/erkenner.md` wieder entfernen →
   `python3.11 -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py`
   ist **rot** (`prompt erkenner` weicht vom nachgezogenen Massstab ab). Das
   ist der Nachweis, dass der Massstab wirklich greift und nicht bloss
   mitgeschrieben wurde.
2. Im Korpus die Zeile `sk01` loeschen →
   `python3.11 -m pytest -q -p no:cacheprovider tests/test_korpus.py` ist
   **rot** in `test_erkenner_traegt_szene_kuerzen` und
   `test_erkenner_jede_art_mindestens_zweimal`.
3. Im Korpus bei `n20` das `erwartet` auf
   `[{"art": "szene_kuerzen", "wert": "2"}]` setzen →
   `test_erkenner_haelt_die_laengengrenzfaelle` ist **rot**.

Alle drei zuruecknehmen, erneut gruen sehen.

- [ ] **Schritt 8: Der Korpuslauf gegen das echte Modell — MANUELL, kostet Geld**

**Kein Teil der automatisierten Abnahme.** Er braucht die Env einer Gruppe
und Netzzugang; `pruefe_prompts.py` ruft sequenziell auf (AGENTS.md Falle 8:
Infomaniak drosselt Parallelitaet mit 429/5xx statt mit einer Warteschlange —
also **nicht** parallelisieren).

```bash
set -a; . ./betrieb/gruppe1.env; set +a
python3.11 -m scripts.pruefe_prompts erkenner --bericht
```

Erwartet:
- **Exit-Code 0.** Er ist genau dann 1, wenn der Erkenner auch nur **ein**
  Falsch-Positiv liefert (AGENTS.md: „eine Aenderung am Erkenner-Prompt gilt
  nur, wenn FP = 0 bleibt").
- In der Ausgabe: **FP 0** und die zweite Kennzahl
  „Falsch-Negative in Zustimmungsfaellen" ebenfalls **0** (`sk01` und `sk02`
  tragen `zustimmung: true` und zaehlen dort mit).
- Die fuenf neuen Faelle einzeln nachsehen:
  ```bash
  python3.11 -m scripts.pruefe_prompts erkenner --nur sk01-kuerzen-mit-nummer
  python3.11 -m scripts.pruefe_prompts erkenner --nur sk03-laenge-nur-besprochen
  python3.11 -m scripts.pruefe_prompts erkenner --nur fl04-festlegung-stil-laenge
  ```
- Der Bericht landet in `korpus/berichte/` und ist gitignored (er enthaelt
  vollstaendige Modellantworten) — **nicht** committen.

**ANNAHME:** dieser Lauf ist in dieser Planungssitzung nicht ausgefuehrt
worden (kein Netzzugang, keine Env, und er kostet Geld). **Nachzupruefen vom
Umsetzer bzw. von Birk:** ob FP = 0 haelt. Bleibt er nicht bei 0, ist die
Abgrenzung in Punkt 23 zu weit — dann ist der Text zu verengen (der
wahrscheinlichste Kandidat: die Beispielliste in der ersten Klammer, die
„das muss kuerzer werden" enthaelt) und der Lauf zu wiederholen. **Hat der
Umsetzer keinen Zugang, bleibt dieser Schritt offen und wird im Commit und in
der Abschlussmeldung als offen benannt** — die uebrigen Teile der Karte
haengen nicht daran.

- [ ] **Schritt 9: Commit**

```bash
git add interview_theater/prompts/erkenner.md korpus/erkenner.jsonl \
        tests/test_korpus.py \
        docs/prompt-audit/schnappschuss-vor-profilumbau.txt \
        docs/prompt-audit/2026-09-06/04-erkenner.txt
git commit -m "$(cat <<'EOF'
Erkenner-Prompt: szene_kuerzen lehren, fuenf Korpusfaelle, Massstab nachziehen

Punkt 23 mit Abgrenzung nach drei Seiten (Kritik ohne Aufforderung,
Laengenvorgabe = festlegung_setzen, Kuerzen != Entfernen != Neuschreiben) und
das Beispiel "nochmal, aber kuerzer" aus Punkt 17 heraus: ein Fakt hat eine
Stelle im Prompt.

Korpus: sk01/sk02 positiv (mit und ohne Nummer, beide zustimmung: true),
sk03/sk04/sk05 negativ. n20, n27 und fl04 behalten ihr Sollverhalten -- ein
neuer Test haelt das fest, weil sie genau in der Nachbarschaft der neuen art
liegen.

Massstab von Hand nachgezogen, weil prompt_schnappschuss.ergaenze() ihn
bewusst nie neu schreibt: die eine Zeile "prompt erkenner" im Schnappschuss
und der SYSTEM-Block in 04-erkenner.txt. Sonst hat sich keine Zeile geaendert.

OFFEN (kein Test, kostet Geld): der Lauf
`python -m scripts.pruefe_prompts erkenner` gegen das echte Modell, Regel
FP = 0.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 6 (Teil 4): Die Richtungswahl speichert ihre Szenenzeilen mit

**Was aus der Praemissenpruefung folgt** (Abschnitt oben, mit Belegen):

- `knoepfe/szenen.py:1041-1042` (`if not alter_block: zeilen = []`) verwirft
  heute **nichts** — auf dem Menue-Weg ist `wert` immer einzeilig, und
  `zerlege_geschichte` liefert dann ohnehin `[]`. **Diese Zeile wird nicht
  angefasst**; sie entfernen wuerde den `alter_block`-Weg oeffnen, fuer den
  sie gebaut ist.
- Die verbleibende Luecke: eine Richtungszeile, die ihre Szenen **inline**
  nennt (`… Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. …`), erzeugt
  keine einzige `szene`-Zeile, und `starte_geschichte_szenen`
  (`knoepfe/szenen.py:1091`) erfindet Titel und Anzahl danach neu.

**Was bewusst NICHT dazugehoert** (Nebenbefund 3 der Praemissenpruefung):
nennt die Zeile zusaetzlich zwei verschiedene Formen an „Szene N", greift
weiterhin `szenenfolge.formabfolge` und `_uebernimm_formwahl`
(`knoepfe/szenen.py:1055-1058`). Dort bleibt `arbeitsstand.geschichte` leer.
Das ist die Reihenfolge von `3290d70`, und sie bleibt: `_uebernimm_formwahl`
sichert in diesem Fall genau das, was die Gruppe **gedrueckt** hat
(`szene.form`, bzw. eine Festlegung, wenn die Szene noch nicht existiert), und
die Praezedenz umzudrehen riskiert die Regression, die `3290d70` geschlossen
hat (113 Zeichen Formwahl statt 665 Zeichen Handlung in
`arbeitsstand.geschichte`). Der Fall wird im Code als Kommentar und in
AGENTS.md als bekannte Grenze benannt, nicht stillschweigend gelassen.

**Warum danach KEIN `starte_geschichte_szenen` mehr laeuft.** `titel` steht
**nicht** in `repo.GESCHUETZTE_SZENENFELDER` (`repo.py:2277-2284`) — ein
frischer Folge-Lauf wuerde die Titel der Gruppe also ueberschreiben, und er
kostet gemessene 110 s (Analyse, Zeile 13:54:10). Der Inline-Weg mündet
deshalb in denselben Zweig wie der `alter_block`-Weg: Journal, Bestaetigung,
Phasenknopf — kein weiterer Lauf. Ein spaeter **ausdruecklich** bestellter
neuer Folge-Vorschlag („Anzahl aendern", „Reihenfolge aendern") darf
umbenennen; das ist dann eine Bestellung und kein Nebeneffekt.

**Warum nur bei zusammenhaengenden Nummern ab 1.**
`repo.gleiche_szenenfolge_ab` nummeriert **nach Position** in der Liste
(`repo.py:2350`, `enumerate(zeilen, start=1)`). Nennt eine Zeile „Szene 2"
und „Szene 4", wuerden daraus die Szenen 1 und 2 — falsche Zuordnung ist
schlimmer als keine. In diesem Fall bleibt es beim heutigen Weg (frischer
Folge-Vorschlag), und ein `vorfall` haelt es fest.

**Dateien:**
- Aendern: `interview_theater/szenenfolge.py` (neu: `_SZENE_ANKER`,
  `_FORM_ANHANG`, `szenen_in_zeile`, `lege_inline_an`, `JOURNAL_INLINE`;
  bei `formabfolge`, `:398-446`)
- Aendern: `interview_theater/knoepfe/szenen.py:1020-1092`
  (`_speichere_geschichte`)
- Aendern: `tests/test_geschichte.py` (vier neue Tests)

**Schnittstellen:**
- Produziert:
  - `szenenfolge.szenen_in_zeile(zeile: str) -> list[tuple[int, str, str]]`
    — `(nummer, titel, form)` je Szene, `form` ist `""`, wenn keine
    dasteht. Weniger als zwei Treffer oder nicht zusammenhaengend ab 1 → `[]`.
  - `szenenfolge.lege_inline_an(conn, chat_id, szenen) -> list[int]`
  - `szenenfolge.JOURNAL_INLINE: str` (Platzhalter `{liste}`)

### Schritte

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `tests/test_geschichte.py` anhaengen:

```python
# --- Die Szenen INNERHALB einer Richtungszeile (30.09.2026, C9) -----------
#
# Die Praemissenpruefung zu dieser Massnahme steht in
# docs/superpowers/plans/2026-09-30-padua-a5-dortmund-reste.md: die Zeile
# ``if not alter_block: zeilen = []`` verwirft heute nichts (auf dem
# Menue-Weg ist der wert immer einzeilig). Was wirklich verlorengeht, sind
# Szenen, die eine Richtung INNERHALB ihrer Zeile nennt.

RICHTUNG_MIT_SZENEN = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht, am Ende bleiben beide. "
    "Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. "
    "Szene 3: Der Morgen danach."
)
RICHTUNG_MIT_SZENEN_UND_FORMEN = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht. "
    "Szene 1: Ankunft am Steg (Dialog). Szene 2: Das Gestaendnis (Monolog)."
)


def test_szenen_in_zeile_liest_titel_und_form():
    assert szenenfolge.szenen_in_zeile(RICHTUNG_MIT_SZENEN) == [
        (1, "Ankunft am Steg", ""),
        (2, "Das Gestaendnis", ""),
        (3, "Der Morgen danach", ""),
    ]
    assert szenenfolge.szenen_in_zeile(RICHTUNG_MIT_SZENEN_UND_FORMEN) == [
        (1, "Ankunft am Steg", "dialog"),
        (2, "Das Gestaendnis", "monolog"),
    ]


def test_szenen_in_zeile_erkennt_eng():
    """Eine Handlung bleibt eine Handlung: eine einzelne Szenennennung, eine
    Formenkette ohne Titel und eine Zeile ohne Szenen ergeben nichts.

    Die Fehlerrichtung ist bewusst gewaehlt -- eine nicht erkannte
    Szenennennung kostet, was sie heute kostet; eine faelschlich erkannte
    kostet die Handlung."""
    assert szenenfolge.szenen_in_zeile("Nur eine: Szene 1: Ankunft am Steg.") == []
    assert szenenfolge.szenen_in_zeile("Chor-Dialog-Rap ueber drei Szenen") == []
    assert szenenfolge.szenen_in_zeile(
        "Ein Bogen ohne Szenen: Mira geht, Pal bleibt, am Ende regnet es."
    ) == []
    assert szenenfolge.szenen_in_zeile("") == []


def test_szenen_in_zeile_verlangt_zusammenhaengende_nummern_ab_eins():
    """``repo.gleiche_szenenfolge_ab`` nummeriert nach Position in der Liste
    (repo.py:2350). "Szene 2" und "Szene 4" wuerden daraus 1 und 2 -- falsche
    Zuordnung ist schlimmer als keine."""
    assert szenenfolge.szenen_in_zeile(
        "Ein Bogen. Szene 2: Ankunft. Szene 4: Abschied."
    ) == []


def test_richtungswahl_speichert_die_szenen_der_zeile_mit(erfunden, tg, einst):
    """Der Kern von C9: nach dem Druck stehen Geschichte UND Szenen da.

    Und: kein zweiter, teurer Folge-Lauf -- ``titel`` ist nicht geschuetzt,
    ein frischer Vorschlag wuerde die Titel der Gruppe ueberschreiben."""
    conn = erfunden
    klm = LLMAttrappe("")
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{RICHTUNG_MIT_SZENEN}"},
        1,
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert "Nacht am Kanal" in stand["geschichte"]
    assert "Szene 1" in stand["geschichte"]  # die ganze Zeile IST die Richtung

    titel = [(s["nummer"], s["titel"]) for s in repo.hole_szenen(conn, 1)]
    assert titel == [
        (1, "Ankunft am Steg"), (2, "Das Gestaendnis"), (3, "Der Morgen danach")
    ]
    assert klm.aufrufe == 0, "kein zweiter Folge-Lauf nach der Uebernahme"


def test_die_form_aus_der_zeile_ist_gesetzt_nicht_vorgeschlagen(erfunden, tg, einst):
    """Die Regel aus 3290d70: der Vorschlag eines MODELLS bleibt aus
    ``szene.form`` heraus -- die Wahl der GRUPPE nicht, und hier hat sie
    gedrueckt. Ohne Form in der Zeile bleibt ``form`` leer."""
    conn = erfunden
    knoepfe._wirke(
        conn, tg, LLMAttrappe(""), einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{RICHTUNG_MIT_SZENEN_UND_FORMEN}"},
        1,
    )
    formen = {s["nummer"]: (s["form"] or "") for s in repo.hole_szenen(conn, 1)}
    assert formen == {1: "dialog", 2: "monolog"}


def test_eine_richtung_ohne_szenen_startet_weiter_den_folge_lauf(erfunden, tg, einst):
    """Der Regelfall bleibt, wie er ist: eine Richtung ohne Szenen fuehrt in
    ``starte_geschichte_szenen``."""
    conn = erfunden
    klm = LLMAttrappe(
        "VORSCHLAG SZENENFOLGE:\nAm Steg — sie treffen sich — Mira — Dialog"
    )
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}Nacht am Kanal — Mira stellt sich, "
                 "Pal gesteht, am Ende bleiben beide."},
        1,
    )
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.aufrufe == 1
    assert klm.gesehen["art"] == szenenfolge.ART


def test_eine_reine_formabfolge_bleibt_die_formwahl(erfunden, tg, einst):
    """Die Praezedenz von 3290d70 bleibt: eine Zeile, die NUR eine Formwahl
    ueber Szenen beschreibt, geht weiter in ``_uebernimm_formwahl`` -- die
    Geschichte bleibt dort leer, und das ist die gemessene Entscheidung
    (docs/analyse-phase4-datenverlust-2026-09-06.md § 2.1)."""
    conn = erfunden
    knoepfe._wirke(
        conn, tg, LLMAttrappe(""), einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}Szene 1: Chor mit Dance. "
                 "Szene 2: Dialog mit Einschueben. Szene 3: Rap eskaliert."},
        1,
    )
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert zeile is not None and zeile["art"] == "geschichte_war_formwahl"
```

- [ ] **Schritt 2: Rot sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_geschichte.py
```
Erwartet: rot mit `AttributeError: module 'interview_theater.szenenfolge' has
no attribute 'szenen_in_zeile'` in den ersten drei Tests und
`assert titel == [...]` in `test_richtungswahl_speichert_die_szenen_der_zeile_mit`
(`titel` ist `[]`).
`test_eine_richtung_ohne_szenen_startet_weiter_den_folge_lauf` und
`test_eine_reine_formabfolge_bleibt_die_formwahl` sind bereits gruen — sie
halten fest, was in Schritt 3/4 **nicht** kaputtgehen darf.

- [ ] **Schritt 3: Den Zerleger in `szenenfolge.py`**

Direkt hinter `formabfolge` (`interview_theater/szenenfolge.py:446`):

```python
#: "Szene 3:" oder "Szene 3 -" mitten in einem Satz -- der Anker, an dem eine
#: Richtungszeile ihre eigenen Szenen benennt.
_SZENE_ANKER = re.compile(r"\bszene\s*(\d{1,2})\s*[:\-–—]\s*", re.IGNORECASE)

#: Eine Form am ENDE eines Szenenstuecks, mit oder ohne Klammern
#: ("Ankunft am Steg (Dialog)", "Ankunft — Dialog"). Absichtlich nur am Ende:
#: "Der Chor am Morgen" ist ein Titel und keine Formangabe -- gemessen am
#: 30.09.2026 an genau diesem Fall.
_FORM_ANHANG = re.compile(
    r"[\(\[]?\s*(" + "|".join(_FORMEN) + r")\s*[\)\]]?[\s.;,]*$", re.IGNORECASE
)

#: Der Journaleintrag, wenn die gewaehlte Richtung ihre Szenen mitbrachte.
JOURNAL_INLINE = "Szenen aus der gewaehlten Richtung: {liste}"


def szenen_in_zeile(zeile: str) -> list[tuple[int, str, str]]:
    """Die Szenen, die EINE Richtungszeile innerhalb ihres Satzes benennt:
    ``[(nummer, titel, form)]``. ``form`` ist "", wenn keine dasteht.

    **Der Anlass** (30.09.2026, Massnahme C9 aus
    ``docs/analyse-phase5-chaos-2026-09-06.md``): ein Richtungs-Knopf traegt
    immer genau EINE Zeile (``knoepfe.sende_geschichte`` baut je Zeile einen
    Knopf), und ``zerlege_geschichte`` findet in einer einzelnen Zeile nie
    Szenen -- sie liest sie ab Zeile 3. Nennt die Richtung ihre Szenen also
    im Satz, gingen Titel und Form verloren, und der Folge-Lauf danach
    erfand sie neu.

    **Eng erkannt, aus derselben Ueberlegung wie ``formabfolge``:**

    * mindestens **zwei** Anker -- eine einzelne Nennung ("und in Szene 1
      sehen wir das schon") ist ein Satz und keine Liste;
    * je Anker ein nicht-leerer Titel;
    * die Nummern muessen **zusammenhaengend ab 1** laufen.
      ``repo.gleiche_szenenfolge_ab`` nummeriert nach Position in der Liste
      (``repo.py:2350``) -- aus "Szene 2" und "Szene 4" wuerden sonst die
      Szenen 1 und 2, und eine falsche Zuordnung ist schlimmer als keine.

    Die Form wird nur am **Ende** eines Stuecks gelesen (``_FORM_ANHANG``):
    "Der Chor am Morgen" ist ein Titel, "Ankunft am Steg (Dialog)" eine
    Formangabe."""
    roh = " ".join((zeile or "").split())
    anker = list(_SZENE_ANKER.finditer(roh))
    if len(anker) < 2:
        return []
    ergebnis: list[tuple[int, str, str]] = []
    for stelle, treffer in enumerate(anker):
        ende = anker[stelle + 1].start() if stelle + 1 < len(anker) else len(roh)
        stueck = roh[treffer.end():ende].strip()
        form = ""
        anhang = _FORM_ANHANG.search(stueck)
        if anhang is not None:
            form = anhang.group(1).lower()
            stueck = stueck[:anhang.start()]
        titel = stueck.strip(" .;,()[]–—-/|").strip()
        if not titel:
            continue
        ergebnis.append((int(treffer.group(1)), titel, form))
    if len(ergebnis) < 2:
        return []
    if [n for n, _, _ in ergebnis] != list(range(1, len(ergebnis) + 1)):
        return []
    return ergebnis


def lege_inline_an(
    conn, chat_id: int, szenen: list[tuple[int, str, str]]
) -> list[int]:
    """Legt die Szenen einer Richtungszeile an und liefert die Nummern.

    Ueber ``lege_an`` und damit ueber ``repo.gleiche_szenenfolge_ab`` --
    abgleichend, nie ersetzend: eine bestehende Szene 1 behaelt ihren Text,
    ihre Form und ihre Besetzung.

    **Die Form geht in ``szene.form``, nicht in ``form_vorschlag``.** Die
    Regel aus ``3290d70`` haelt den Vorschlag eines MODELLS aus dem Feld
    heraus, nicht die Wahl der Gruppe -- und hier hat sie gedrueckt
    (dieselbe Begruendung wie in ``knoepfe._uebernimm_formwahl``). Nennt die
    Zeile keine Form, bleibt ``form`` leer und die Frage steht spaeter Szene
    fuer Szene (``knoepfe.biete_szenenform``)."""
    zeilen = [(titel, "", [], "", "") for _nummer, titel, _form in szenen]
    nummern = lege_an(conn, chat_id, zeilen)
    nach_nummer = {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, chat_id)}
    for nummer, _titel, form in szenen:
        if not form:
            continue
        szene_id = nach_nummer.get(nummer)
        if szene_id is not None:
            repo.setze_szenenfeld(conn, szene_id, "form", form)
    return nummern
```

> **Achtung beim vierten Tupelelement:** `lege_an` setzt bei leerem Wert die
> Vorgabe ein (`szenenfolge.py:317-318`, `workshop.form_vorgabe()`). Das ist
> hier richtig und gewollt: der **Vorschlag** bleibt Dialog, und die
> **bestaetigte** Form setzt die Schleife danach nur dort, wo die Zeile
> wirklich eine nennt.

- [ ] **Schritt 4: Die Uebernahme in `_speichere_geschichte`**

`interview_theater/knoepfe/szenen.py`, in `_speichere_geschichte` zwischen
dem Speichern der Geschichte (`:1066`, `setze_arbeitsstand … aenderung_offen`)
und dem `if zeilen:`-Zweig (`:1067`):

```python
    # **Nennt die Richtung ihre Szenen selbst, werden sie mitgespeichert**
    # (30.09.2026, Massnahme C9). Ein Richtungs-Knopf traegt immer genau EINE
    # Zeile; ``zerlege_geschichte`` liest Szenen erst ab Zeile 3 und findet
    # darin nie welche. Eine Richtung wie "… Szene 1: Ankunft am Steg.
    # Szene 2: Das Gestaendnis." verlor deshalb Titel und Form, und der
    # Folge-Lauf danach erfand sie neu.
    #
    # Danach laeuft KEIN ``starte_geschichte_szenen``: ``titel`` steht nicht
    # in ``repo.GESCHUETZTE_SZENENFELDER``, ein frischer Vorschlag wuerde die
    # Titel der Gruppe also ueberschreiben -- und er kostet gemessene 110 s.
    # Ein spaeter ausdruecklich bestellter Vorschlag ("Anzahl aendern") darf
    # umbenennen; das ist dann eine Bestellung.
    #
    # Eine reine Formabfolge kommt hier nie an: sie ist oben in
    # ``_uebernimm_formwahl`` abgezweigt (Praezedenz von 3290d70, und dort
    # bleibt sie -- sie sichert genau das, was die Gruppe gedrueckt hat).
    if not zeilen:
        inline = szenenfolge.szenen_in_zeile(wert)
        if inline:
            zeilen = [(titel, "", [], form, "") for _n, titel, form in inline]
            nummern = szenenfolge.lege_inline_an(conn, chat_id, inline)
            repo.schreibe_journal(
                conn, chat_id, "entschieden",
                szenenfolge.JOURNAL_INLINE.format(
                    liste="; ".join(
                        f"{n}. {t}" for n, t, _f in inline
                    )
                ),
                quelle="knopf",
            )
            tg.sende(
                chat_id,
                _TEXT_GESCHICHTE_GESPEICHERT.format(anzahl=len(nummern))
                + "\n" + geschichte,
            )
            if modus.strip() == "anders":
                repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", "geschichte")
                tg.sende(chat_id, _TEXT_ANDERS)
                return "Gespeichert, was soll anders sein?"
            phasenknopf = _phasenknopf(conn, chat_id)
            if phasenknopf is not None:
                _mit_leiste(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE,
                            [phasenknopf])
            else:
                tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
            return f"Geschichte mit {len(nummern)} Szenen uebernommen"
```

Der Docstring von `_speichere_geschichte` bekommt einen dritten Absatz:

```python
    **Nennt die gewaehlte Richtung ihre Szenen selbst**, werden sie
    mitgespeichert und der Folge-Lauf entfaellt (30.09.2026, C9,
    ``szenenfolge.szenen_in_zeile``). Vorher war das der stille Verlust: die
    Zeile stand vollstaendig im Arbeitsstand, aber Titel und Form wurden
    eine Minute spaeter vom naechsten Vorschlag ueberschrieben.
```

> Die Zuweisung an `zeilen` in der ersten Zeile des Blocks ist absichtlich
> **nicht** dazu da, in den `if zeilen:`-Zweig zu fallen (der Block kehrt
> vorher zurueck) — sie haelt die Variable konsistent fuer einen kuenftigen
> Leser und macht sichtbar, dass hier dieselbe Tupelform entsteht wie bei
> `szenenfolge.zerlege`. Wer sie stoerend findet, darf sie weglassen; dann
> aendert sich am Verhalten nichts.

- [ ] **Schritt 5: Gruen sehen**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_geschichte.py tests/test_szenenfolge.py tests/test_knoepfe.py
```
Erwartet: alles `passed`, 7 neu in `test_geschichte.py`.

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `2741 passed, 1 skipped` (2734 + 7).

- [ ] **Schritt 6: Mutationsnachweis**

1. Den ganzen `if not zeilen: inline = …`-Block aus `_speichere_geschichte`
   entfernen →
   `python3.11 -m pytest -q -p no:cacheprovider tests/test_geschichte.py -k "zeile_mit or nicht_vorgeschlagen"`
   ist **rot** (`titel == []`, `formen == {}`).
2. In `szenen_in_zeile` die Nummernpruefung
   `if [n for n, _, _ in ergebnis] != list(range(1, len(ergebnis) + 1)):`
   entfernen →
   `test_szenen_in_zeile_verlangt_zusammenhaengende_nummern_ab_eins` ist
   **rot**.
3. In `szenen_in_zeile` `_FORM_ANHANG` durch das ungebundene
   `re.compile(r"\b(" + "|".join(_FORMEN) + r")\b", re.IGNORECASE)` ersetzen →
   `test_szenen_in_zeile_liest_titel_und_form` bleibt gruen, aber der Fall
   „Der Chor am Morgen" faellt aus. **Deshalb** wird dieser Fall dem ersten
   Test hinzugefuegt, bevor der Nachweis gilt:
   ```python
   assert szenenfolge.szenen_in_zeile(
       "Bogen. Szene 1: Ankunft (Dialog). Szene 2: Der Chor am Morgen (Chor)."
   ) == [(1, "Ankunft", "dialog"), (2, "Der Chor am Morgen", "chor")]
   ```
   Mit dieser Zeile ist der Nachweis **rot** (`"Der am Morgen"` statt
   `"Der Chor am Morgen"`). Die Zeile bleibt im Test stehen.

Alle drei zuruecknehmen, erneut gruen sehen.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/szenenfolge.py interview_theater/knoepfe/szenen.py \
        tests/test_geschichte.py
git commit -m "$(cat <<'EOF'
Richtungswahl: Szenen aus der gewaehlten Zeile mitspeichern

C9 aus docs/analyse-phase5-chaos-2026-09-06.md, nach Praemissenpruefung.

Widerlegt: `if not alter_block: zeilen = []` (knoepfe/szenen.py:1041) verwirft
heute nichts -- auf dem Menue-Weg traegt ein Richtungs-Knopf immer genau eine
Zeile, und zerlege_geschichte liest Szenen erst ab Zeile 3. Die Zeile bleibt
unangetastet.

Bestaetigt: eine Richtung, die ihre Szenen INNERHALB der Zeile nennt
("… Szene 1: Ankunft am Steg. Szene 2: …"), erzeugte keine szene-Zeile, und
starte_geschichte_szenen erfand Titel und Anzahl danach neu. szenen_in_zeile
liest sie eng (>= 2 Anker, Nummern zusammenhaengend ab 1, Form nur am
Stueckende), lege_inline_an legt sie ueber gleiche_szenenfolge_ab an und setzt
szene.form dort, wo die Zeile eine nennt -- die Gruppe hat gedrueckt.

Danach laeuft kein Folge-Lauf mehr: titel ist nicht geschuetzt, und ein
frischer Vorschlag kostet 110 s und die Titel der Gruppe.

Unveraendert: eine reine Formabfolge bleibt _uebernimm_formwahl (Praezedenz
von 3290d70) -- dort bleibt arbeitsstand.geschichte leer, bekannte Grenze.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 7 (D7): AGENTS.md nachziehen — ein Absatz je Teil

**Keine Codeaenderung.** Die Datei ist die technische Referenz; was in ihr
fehlt, findet der naechste Agent nicht. Fuenf Stellen, in dieser Reihenfolge.
Die Abschnitte stehen in AGENTS.md **doppelt** (die Datei traegt „Die Fallen",
„Wo SPEC und Code auseinanderlaufen", „Starten und testen", „Weboberflaeche"
und „Prompt geaendert?" jeweils zweimal) — **jede Aenderung gilt fuer die
erste Fundstelle**, und wo unten „beide" steht, fuer beide. Fundstellen mit
`grep -n` bestimmen, nicht mit Zeilennummern aus diesem Plan.

- [ ] **Schritt 1: Zwei Zeilen in die Modultabelle**

In der Tabelle „Module unter `interview_theater/`" (erste Fundstelle von
`| Modul | Zuständigkeit |`), alphabetisch bei den Nachbarn:

```markdown
| `kuerzung.py` | Kuerzen als eigener Weg (30.09.2026, C4/C10): die feste Regie-Notiz (25 %), die Zielwahl (Szenennummer → `szene.starte`, keine → `kurzgeschichte.starte`) und `nummer_aus_wert`. **Kein eigener Modellaufruf** — beide Wege geben an ihren vorhandenen Thread ab, und beide haengen ihre Fassung an (`szenenfassung`). Eine Kuerzung erzeugt **nie** eine neue Szenenfolge |
| `vorschlagssperre.py` | Die EINE Sperre je `chat_id`, die Schaerfung und die vier `szenenfolge.starte*` voneinander trennt (30.09.2026, C7), plus einen Merkplatz je Auftragsart: wer sie nicht bekommt, wird **gemerkt** und laeuft nach der Freigabe automatisch. Reines `threading`, **kein** Projektimport — deshalb von beiden Seiten importierbar. Grenze: der Merkplatz lebt im Prozess, ein Neustart verliert ihn |
```

- [ ] **Schritt 2: Die Schichten der Modulkarte**

Im Abschnitt „Modulkarte", Tabelle der vier Schichten:

- Zeile **Dienste** um ` · \`vorschlagssperre.py\`` ergaenzen (es haengt unter
  allem und importiert nichts aus dem Projekt).
- Zeile **Fachlogik** um ` · \`kuerzung.py\`` ergaenzen (bei `szene.py`,
  `kurzgeschichte.py`).

Und in der Tabelle „Wo man anfaengt, je nach Frage" eine Zeile:

```markdown
| Warum wartet ein Vorschlag? | `vorschlagssperre.nimm` → `merke` → `gib_frei` |
```

- [ ] **Schritt 3: „Was bewusst mehrfach existiert" praezisieren**

Der Punkt lautet heute:

```markdown
- Ein Sperren-Register je Nebenläufigkeit (`ablauf`, `szene`, `szenenfolge`).
  Gleicher Code, verschiedene Sperren — eine gemeinsame Sperre würde den
  Gesprächszug am Szenenlauf hängen lassen.
```

Er wird zu:

```markdown
- Ein Sperren-Register je Nebenläufigkeit (`ablauf`, `szene`,
  `kurzgeschichte`, `sprachstil`). Gleicher Code, verschiedene Sperren — eine
  gemeinsame Sperre würde den Gesprächszug am Szenenlauf hängen lassen. **Die
  eine Ausnahme** (30.09.2026, C7): `szenenfolge` und `schaerfung` teilen
  seither eine Sperre, und sie liegt deshalb in einem eigenen Modul
  (`vorschlagssperre.py`) statt in einem der beiden. Der Grund ist gemessen:
  am 06.09. lagen Schärfungsvorschlag und Szenenfolge-Vorschlag im selben
  Chatfenster, und die Gruppe wusste nicht, auf welche Frage sie antwortet.
  Ausgeweitet werden darf sie nicht — `szenenfolge._sperre_fuer` bleibt als
  Name bestehen und delegiert dorthin, damit Tests weiter über
  `acquire(timeout=…)` auf das Ende eines Laufs warten können.
```

- [ ] **Schritt 4: Vier Absätze in „Bindende Entwurfsentscheidungen"**

Am Ende des Abschnitts, nach dem Absatz über das Eingabe-Budget des
Szenenlaufs, als **ein** neuer Aufzählungspunkt mit vier Teilen:

```markdown
- **Kürzen ist eine Überarbeitung, keine neue Szenenfolge** (30.09.2026,
  Maßnahmen C4/C7/C9/C10 aus `docs/analyse-phase5-chaos-2026-09-06.md`; der
  Plan dazu: `docs/superpowers/plans/2026-09-30-padua-a5-dortmund-reste.md`).
  Vier Dinge, die eine Wurzel haben — am 06.09. bat die Gruppe um eine
  Kürzung, und weil es dafür keinen Weg gab, wurde daraus ein Neuaufbau:
  aus drei Szenen wurden sechs und eine Stunde später noch einmal sechs.
  1. **Der Knopf „Kürzer (25 %)"** steht an genau zwei Orten — unter der
     fertigen Kurzgeschichte (`knoepfe.zeige_kurzgeschichte`, Phase 6) und
     unter einem frisch geschriebenen Szenentext
     (`knoepfe.biete_nach_szenentext`, Phase 7). **Nicht** unter „Szene N
     ansehen": dort liest man, dort gehört „Frühere Fassungen" hin. Er wirkt
     wie „Passt, aber anders", nur ohne Rückfrage: die Regie-Notiz steht fest
     (`kuerzung.notiz_fuer_szene`, `notiz_fuer_prosa`), der Prozentwert an
     **einer** Stelle (`kuerzung.PROZENT`). Mit Szenennummer läuft
     `szene.starte`, ohne läuft `kurzgeschichte.starte` — die Phase entscheidet
     sich dabei von selbst, weil `szene.schreibt_prosa` ohnehin nach `prosa`
     oder `volltext` verzweigt. **Die Prosa-Notiz nennt die Abschnittszahl
     ausdrücklich**, weil `kurzgeschichte.ANWEISUNG` dem Modell die Zahl
     freistellt und der Abgleich ergänzend ist: ohne den Satz blieben zwei
     Abschnitte mit ihrem alten, langen Text stehen.
  2. **Die Erkenner-Art `szene_kuerzen`** macht „mach das kürzer" im Chat zum
     selben Weg. Sie hat **keinen Schreibpfad** (wie `szene_schreiben`) und
     wird erst in `laufe()` ausgewertet (`erkenner._starte_kuerzung`),
     höchstens **eine je Lauf**. Leerer `wert` heißt „die ganze
     Kurzgeschichte" — eine geratene Nummer schriebe die falsche Szene neu.
     Auf **„im Zweifel kein Eintrag"** kalibriert, wie `szene_schreiben` und
     `entfernen`: Kritik an der Länge („zu lang, was meint ihr", Korpusfall
     n20) feuert nicht, eine dauerhafte Längenvorgabe („höchstens eine Seite
     ab jetzt", fl04) bleibt `festlegung_setzen`, und aus einer **Aufnahme**
     gilt sie nie (`ARTEN_IN_AUFNAHME` bleibt bei drei). Korpus: `sk01`/`sk02`
     positiv, `sk03`–`sk05` negativ, plus ein Test, der n20/n27/fl04 auf ihrem
     Sollwert festhält.
  3. **Schärfung und Szenenfolge laufen nie gleichzeitig**
     (`vorschlagssperre.py`). Wer die Sperre nicht bekommt, wird **gemerkt**
     und läuft nach der Freigabe automatisch — nicht abgewiesen. Das ist der
     Unterschied zum alten `szenenfolge._TEXT_BESETZT`, das den Auftrag verlor;
     die Konstante bleibt als Nutzertext stehen, hat aber keinen Aufrufer mehr.
     `schaerfung.starte` liefert dafür `GEMERKT` statt `None` — `None` heißt
     „es gab nichts anzustoßen", und `knoepfe.starte_schaerfung` spielt darauf
     die vorhandene Lage aus.
  4. **Die Richtungswahl speichert ihre Szenen mit**
     (`szenenfolge.szenen_in_zeile`, `lege_inline_an`). Ein Richtungs-Knopf
     trägt immer genau **eine** Zeile, und `zerlege_geschichte` liest Szenen
     erst ab Zeile 3 — nennt die Richtung ihre Szenen also im Satz („… Szene 1:
     Ankunft am Steg. Szene 2: …"), gingen Titel und Form verloren, und der
     Folge-Lauf erfand sie eine Minute später neu. Eng erkannt (mindestens
     zwei Anker, Nummern zusammenhängend ab 1, Form nur am Stückende), die
     Form geht in `szene.form` und nicht in `form_vorschlag` — die Gruppe hat
     gedrückt —, und **danach läuft kein `starte_geschichte_szenen` mehr**:
     `titel` steht nicht in `repo.GESCHUETZTE_SZENENFELDER`, ein frischer
     Vorschlag würde die Titel der Gruppe überschreiben und kostet gemessene
     110 s.
     **Zwei bekannte Grenzen, beide gemessen:** `if not alter_block: zeilen =
     []` in `knoepfe._speichere_geschichte` verwirft heute **nichts** (auf dem
     Menü-Weg ist der `wert` immer einzeilig) und bleibt für den
     `alter_block`-Weg stehen; und eine Zeile, die zusätzlich zwei
     verschiedene **Formen** an „Szene N" hängt, geht weiterhin in
     `_uebernimm_formwahl` (Präzedenz von `3290d70`) — dort bleibt
     `arbeitsstand.geschichte` leer. Das ist die Entscheidung von `3290d70`
     und bleibt: sie sichert genau das, was die Gruppe gedrückt hat, und die
     Präzedenz umzudrehen riskiert die Regression, die `3290d70` geschlossen
     hat.
```

- [ ] **Schritt 5: Die Korpuszahlen im Abschnitt „Prompt geändert?"**

Der Absatz nennt heute „121 Absichtserkenner-Fälle (davon 45
Negativfälle; … 10 mit `zustimmung: true`)". **Diese Zahlen sind schon vor
dieser Karte veraltet** — gemessen am 30.09.2026 auf `17eb5b0` sind es
**145 Fälle, 50 Negativfälle, 11 Aufnahmefälle, 18 mit `zustimmung: true`**.
Nach dieser Karte sind es **150 / 53 / 11 / 20**. Beide Fundstellen des
Absatzes bekommen die gemessenen Zahlen, plus den Satz:

```markdown
(Stand 30.09.2026 nachgemessen — die Zahlen davor waren seit dem 05.09. nicht
mitgewachsen. Wer Fälle ergänzt, zählt mit
`python3.11 -c "import json; f=[json.loads(l) for l in open('korpus/erkenner.jsonl') if l.strip()]; print(len(f), sum(1 for x in f if not x['erwartet']))"`
nach, statt zu schätzen.)
```

Und einen Satz zu den neuen Fällen, bei der Aufzählung der Arten:

```markdown
Seit dem 30.09.2026 dazu `szene_kuerzen` mit `sk01`/`sk02` (positiv, beide
`zustimmung: true`) und `sk03`–`sk05` (negativ) — die Art liegt direkt neben
n20, n27 und fl04, und `tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle`
hält deren Sollwerte fest.
```

- [ ] **Schritt 6: Prüfen, dass die Doku-Tests halten**

`tests/test_anweisungen.py` prüft Prompt-Dateien, nicht AGENTS.md; es gibt
keinen Test auf diese Datei. Trotzdem die Suite laufen lassen, weil AGENTS.md
in keinem Test referenziert werden **soll**:

```bash
grep -rn "AGENTS.md" tests/ | grep -v "\.pyc" || echo "kein Test haengt an AGENTS.md"
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: `kein Test haengt an AGENTS.md` und `2741 passed, 1 skipped`.

- [ ] **Schritt 7: Commit**

```bash
git add AGENTS.md
git commit -m "$(cat <<'EOF'
AGENTS.md: Kuerzen, die geteilte Vorschlagssperre, die Richtungswahl

Ein Absatz je Teil der Karte A5, dazu zwei Zeilen in der Modultabelle und die
Praezisierung von "Ein Sperren-Register je Nebenlaeufigkeit": szenenfolge und
schaerfung teilen seit dem 30.09. eine, und sie liegt deshalb in einem eigenen
Modul.

Die Korpuszahlen sind nachgemessen statt geschaetzt -- sie waren seit dem
05.09. nicht mitgewachsen (121/45 stand da, 145/50 war der Stand).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Aufgabe 8: Abschluss

**Keine Codeaenderung** — nur Nachweise. Kein Commit, wenn nichts offen
geblieben ist (`git status` muss sauber sein); wird hier doch noch etwas
korrigiert, geht das in einen eigenen Commit.

- [ ] **Schritt 1: Die ganze Suite**

```bash
python3.11 -m pytest -q -p no:cacheprovider
```
Erwartet: **`2741 passed, 1 skipped`**, 0 errors, 0 failures.
Rechnung gegen die Basis: 2702 + 8 (A1) + 3 (A2) + 13 (A3: 11 eigene + 2
parametrisierte in `test_knoepfe_struktur.py`) + 6 (A4) + 2 (A5) + 7 (A6)
= 2741.
Weicht die Zahl ab, ist ein Test dazugekommen oder verlorengegangen — nachsehen,
nicht anpassen. **Die Zahl ist ein Hinweis, das Ergebnis ist „0 failures, 0
errors"**: wer einen Test zusaetzlich schreibt, weil er beim Umsetzen eine
Luecke findet, soll ihn nicht wegen dieser Zeile weglassen.

- [ ] **Schritt 2: Das Profil**

```bash
python3.11 -m scripts.pruefe_profil dortmund-2026
```
Erwartet: Exit 0, keine Fehlerzeile.

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/profile/
```
Erwartet: alles `passed`. Das ist der zweite, strengere Nachweis: mit
`IT_WORKSHOP=dortmund-2026` und ohne Variable entstehen zeichengleiche
Prompts, und der nachgezogene Massstab stimmt.

- [ ] **Schritt 3: Die Knopf-Zusagen am Quelltext**

```bash
python3.11 -m pytest -q -p no:cacheprovider tests/test_knoepfe_struktur.py -v
```
Erwartet: alle `passed`, darunter
`test_jede_knopfart_hat_genau_einen_handler` (die zwei neuen Arten haben
Handler), `test_kein_handler_ruft_das_sprachmodell[_wirkung_szene_kuerzen]`
und `…[_wirkung_geschichte_kuerzen]` (Zusage 2),
`test_wirke_wird_nur_aus_behandle_gerufen` (Zusage 3).

- [ ] **Schritt 4: Keine Echtdaten angefasst**

```bash
git status --porcelain
git log --oneline --stat origin/main..HEAD | grep -E "betrieb/|korpus/berichte/|simulation/laeufe/|simulation/berichte/|docs/dramaturgie-berichte/" || echo "keine Betriebsdaten im Commit"
```
Erwartet: `git status --porcelain` ist **leer** (bis auf die vier
Sitzungsdateien `.cc-*` / `.superpowers-brief-*`, die nicht ins Repo gehoeren
und nicht committet werden), und
`keine Betriebsdaten im Commit`.

- [ ] **Schritt 5: Branch und Historie**

```bash
git branch --show-current
git log --oneline origin/main..HEAD
```
Erwartet: `padua-workshop/t_4489e2ad-plan-a5-dortmund-reste` und **sieben**
Commits (A1 bis A7) plus der Plan-Commit. Kein Merge, kein Push.

- [ ] **Schritt 6: Was offen bleibt, benennen**

In der Abschlussmeldung an Birk ausdruecklich aufzaehlen:

1. **Der Erkenner-Korpuslauf gegen das echte Modell ist nicht gelaufen**
   (Aufgabe 5, Schritt 8): `python3.11 -m scripts.pruefe_prompts erkenner`,
   Regel **FP = 0**, Exit 0. Er kostet Rappen und braucht
   `betrieb/<gruppe>.env`. Ohne ihn gilt die Prompt-Aenderung nach der Regel
   in AGENTS.md **noch nicht als abgenommen**.
2. **Simulation nicht gelaufen** (`python3.11 -m scripts.simulation --set 1
   --seed 7 --bericht` und `--mix 1,2,3 --seed 3`). AGENTS.md verlangt nach
   jeder Prompt-Aenderung einen Lauf je Variante, mit **demselben Seed wie
   beim letzten Mal**. Kostet Geld, laeuft nie automatisch.
3. **Nicht gebaut, bewusst:** ein `_AUFTRAGSFORMEN`-Muster fuer „kuerzer" in
   `ablauf.ist_auftrag`. Es wuerde den Gespraechs-Bot bei einer Kuerzung
   schweigen lassen (heute redet er parallel zum Auftrag — die gemessene
   Doppelung). Dagegen steht die Regel an genau dieser Liste
   (`ablauf.py:285-286`): „Die Liste ist absichtlich eng: eine falsch
   unterdrueckte Antwort ist teurer als eine ueberfluessige." Ein Muster auf
   „kuerzer" traefe auch n20 („die szene 2 ist mir noch zu lang, was meint
   ihr") — also genau den Fall, der **nicht** feuern darf, und der Bot wuerde
   dort stumm bleiben. Eigene Karte, wenn es jemand will.
4. **Nicht gebaut, bewusst:** `kontext._baue_szene` liest weiter nur
   `volltext` und nicht `prosa` (Massnahme C5 der Analyse). Sie steht nicht in
   dieser Karte, und sie beruehrt den Gespraechs-Prompt — das ist eine eigene
   Messung wert.

---

## Selbstdurchsicht (nach dem Schreiben, gegen die Karte gehalten)

**1. Abdeckung der Karte.** Alle vier Teile haben Aufgaben:
Teil 1 → A3 · Teil 2 → A4 (Code) + A5 (Prompt, Korpus, Massstab) ·
Teil 3 → A1 + A2 · Teil 4 → A6. D7 → A7. Abnahme → A8.
Jede Entscheidung D1–D7 ist adressiert:
- **D1** (Kuerzen als Ueberarbeitung, 25 %, angehaengte Fassung, keine neue
  Folge, Begruendung am Code, keine neue Tabelle/kein neuer Anbieterweg) →
  A3, Abschnitt „Entscheidung und ihre Begruendung am Code".
- **D2** (drei Knopf-Zusagen, `test_knoepfe_struktur` gruen) → A3 Schritte
  4–7, A8 Schritt 3.
- **D3** (`szene_kuerzen` auf „im Zweifel kein Eintrag", ≥2 positiv, ≥3 neu
  negativ, eindeutige ids, `test_korpus` gruen, Korpuslauf als manueller
  Schritt mit `ANNAHME:`, nicht aus einer Aufnahme) → A4 + A5.
- **D4** (gemeinsame Sperre nur Schaerfung/Szenenfolge, Merkplatz je Art,
  Wartemeldung als Konstante, Neustart-Grenze benannt, Tests (a)/(b)/(c) mit
  Events) → A1 + A2.
- **D5** (Praemissenpruefung zuerst, Beleg mit Datei:Zeile, nur die
  verbleibende Luecke planen, `gleiche_szenenfolge_ab`, Form nach `3290d70`,
  keine Prompt-Aenderung an `ANWEISUNG_GESCHICHTE` ohne Begruendung) →
  eigener Abschnitt oben + A6.
- **D6** (neue Texte sind Code-Konstanten, `test_profil_bitgleich` nicht rot
  lassen, Schnappschuss-Weg geprueft und beschrieben, `pruefe_profil` gruen) →
  Globale Vorgaben + A5 Schritt 5 + A8 Schritt 2.
- **D7** (AGENTS.md je Teil ein Absatz, eigener Task) → A7.

**2. Platzhalter.** Kein „TBD", kein „analog zu Aufgabe N" ohne den Code, kein
„Fehlerbehandlung ergaenzen". Jeder Test steht im Wortlaut, jeder Codeblock
vollstaendig. Die einzigen Stellen, an denen der Umsetzer selbst suchen muss,
sind die Einfuegepunkte in AGENTS.md — dort steht ausdruecklich, **wie**
(`grep -n`) und **warum** (die Abschnitte stehen doppelt).

**3. Typen und Namen quer durch die Aufgaben.** `vorschlagssperre.nimm/
gib_frei/merke/sperre_fuer/laeuft/gemerkte_arten/vergiss` (A1) werden in A2
genau so gerufen. `kuerzung.PROZENT/notiz_fuer_szene/notiz_fuer_prosa/
nummer_aus_wert/starte(conn, tg, klm, e, chat_id, nummer=None)` (A3) werden in
A4 genau so gerufen (`_starte_kuerzung`) und in A3 genau so getestet.
`ART_SZENE_KUERZEN`/`ART_GESCHICHTE_KUERZEN`/`TEXT_KUERZEN_KNOPF` heissen in
`texte.py`, in `wirkung.py`, in `__init__.py` und im Test gleich.
`szenenfolge.szenen_in_zeile` liefert ueberall `list[tuple[int, str, str]]`,
`lege_inline_an` nimmt genau diese Liste.
`schaerfung.GEMERKT`/`TEXT_GEMERKT` und `szenenfolge._TEXT_GEMERKT` stehen in
A2 und im Test von A2 identisch.

**4. Reihenfolge.** A1 vor A2 (die Sperre existiert, bevor sie verdrahtet
wird). A3 vor A4 (`kuerzung.starte` existiert, bevor der Erkenner sie ruft).
A4 vor A5 (die Art ist im Enum, bevor der Prompt sie lehrt — und steht dafuer
einen Commit lang in `OHNE_KORPUSFAELLE`, so wie es dort dokumentiert ist).
A6 ist unabhaengig und koennte auch zuerst laufen.

"""Die drei Zusagen aus dem Moduldocstring von ``knoepfe.py`` -- strukturell.

Nicht am Verhalten gemessen, sondern **am Quelltext**: die uebrigen Tests
pruefen, dass ein bestimmter Knopf das Richtige tut; diese hier pruefen, dass
kein *neuer* Knopf die Zusagen brechen kann, ohne dass es jemand merkt. Anlass
ist das Refactoring vom 06.09.2026, das die if/elif-Kaskade in ``_wirke`` durch
die Tabelle ``knoepfe._WIRKUNGEN`` ersetzt hat: eine Tabelle laesst sich
auslesen, eine Kaskade nicht.

Die drei Zusagen (AGENTS.md, "Bindende Entwurfsentscheidungen"):

1. ``callback_data`` bleibt unter **64 Bytes** -- ein Knopf traegt nur
   ``k:<id>``, der Wert steht in der Tabelle ``knopf``.
2. **Kein Modellaufruf** in einem Knopf-Handler. Was ein Modell braucht, geht
   an einen eigenen Thread.
3. **Idempotent** ueber ``repo.beanspruche_knopf`` -- der zweite Druck wird
   beantwortet, wirkt aber nicht.

**Was der Scan nicht kann:** er sieht eine Ebene tief. Ruft ein Handler eine
Hilfsfunktion, die ihrerseits das Modell anfasst, faellt das hier nicht auf --
dagegen stehen die Verhaltenstests in ``test_knoepfe*.py``.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from interview_theater import knoepfe


QUELLE = pathlib.Path(inspect.getfile(knoepfe))
BAUM = ast.parse(QUELLE.read_text(encoding="utf-8"))

#: Name -> AST-Knoten aller Funktionen des Moduls, verschachtelte eingeschlossen.
FUNKTIONEN = {
    knoten.name: knoten
    for knoten in ast.walk(BAUM)
    if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef))
}

#: Die Namen der Handler aus der Dispatch-Tabelle, ohne Doppelte.
HANDLERNAMEN = sorted({f.__name__ for f in knoepfe._WIRKUNGEN.values()})


def test_jede_knopfart_hat_genau_einen_handler():
    """Die Tabelle deckt alle ``ART_*``-Konstanten ab.

    Eine Art ohne Handler landet zur Laufzeit bei ``_TEXT_UNBEKANNT`` -- ein
    Knopf, der im Chat steht und nichts tut."""
    arten = {
        getattr(knoepfe, name)
        for name in dir(knoepfe)
        if name.startswith("ART_")
    }
    ohne_handler = sorted(arten - set(knoepfe._WIRKUNGEN))
    assert ohne_handler == []


# --- Zusage 1: callback_data unter 64 Bytes --------------------------------


def test_callback_data_bleibt_unter_64_bytes():
    """Auch bei einer unrealistisch hohen Knopf-id."""
    assert len(knoepfe._daten(999_999_999_999).encode("utf-8")) < 64


def test_nur_daten_und_id_aus_daten_kennen_das_praefix():
    """``PRAEFIX`` steht an genau zwei Stellen: dort, wo callback_data
    entsteht, und dort, wo sie wieder gelesen wird.

    Damit ist ``_daten`` die einzige Quelle von callback_data -- und die
    Laengenzusage haengt an einer einzigen Funktion statt an der Disziplin
    jedes neuen Knopfes."""
    stellen = {
        name
        for name, knoten in FUNKTIONEN.items()
        if any(
            isinstance(k, ast.Name) and k.id == "PRAEFIX" for k in ast.walk(knoten)
        )
    }
    assert stellen == {"_daten", "_id_aus_daten"}


# --- Zusage 2: kein Modellaufruf im Handler --------------------------------


def _fasst_das_modell_an(knoten: ast.AST) -> list[str]:
    """Jeder Zugriff *auf* das Sprachmodell im Rumpf dieser Funktion.

    Weitergeben ist erlaubt (``_starte_auftrag(conn, d.tg, d.klm, ...)`` gibt
    an einen eigenen Thread ab); **anfassen** ist es nicht -- also weder
    ``klm.<irgendwas>`` noch ein Import von ``llm``."""
    treffer = []
    for kind in ast.walk(knoten):
        if isinstance(kind, ast.Attribute):
            ziel = kind.value
            if isinstance(ziel, ast.Name) and ziel.id == "klm":
                treffer.append(f"klm.{kind.attr}")
            elif (
                isinstance(ziel, ast.Attribute)
                and ziel.attr == "klm"
                and isinstance(ziel.value, ast.Name)
            ):
                treffer.append(f"{ziel.value.id}.klm.{kind.attr}")
        elif isinstance(kind, ast.ImportFrom) and kind.module:
            for name in kind.names:
                if name.name == "llm" or kind.module.endswith(".llm"):
                    treffer.append(f"import {name.name}")
    return treffer


@pytest.mark.parametrize("name", HANDLERNAMEN)
def test_kein_handler_ruft_das_sprachmodell(name):
    assert _fasst_das_modell_an(FUNKTIONEN[name]) == []


def test_auch_wirke_und_behandle_fassen_das_modell_nicht_an():
    """Die beiden Funktionen, durch die jeder Knopfdruck laeuft."""
    for name in ("_wirke", "behandle"):
        assert _fasst_das_modell_an(FUNKTIONEN[name]) == []


# --- Zusage 3: Idempotenz ueber repo.beanspruche_knopf ---------------------


def test_wirke_wird_nur_aus_behandle_gerufen():
    """Ein zweiter Aufrufer waere ein zweiter Weg an der Sperre vorbei."""
    aufrufer = {
        name
        for name, knoten in FUNKTIONEN.items()
        if any(
            isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == "_wirke"
            for k in ast.walk(knoten)
        )
    }
    assert aufrufer == {"behandle"}


def test_behandle_beansprucht_vor_der_wirkung():
    """``repo.beanspruche_knopf`` steht in ``behandle`` **vor** dem Aufruf von
    ``_wirke``, und sein negatives Ergebnis fuehrt zu einem ``return``.

    Genau daran haengt die Idempotenz: nicht daran, dass jede einzelne Wirkung
    fuer sich wiederholbar waere."""
    behandle = FUNKTIONEN["behandle"]
    sperre = [
        k
        for k in ast.walk(behandle)
        if isinstance(k, ast.Call)
        and isinstance(k.func, ast.Attribute)
        and k.func.attr == "beanspruche_knopf"
    ]
    wirkung = [
        k
        for k in ast.walk(behandle)
        if isinstance(k, ast.Call)
        and isinstance(k.func, ast.Name)
        and k.func.id == "_wirke"
    ]
    assert len(sperre) == 1 and len(wirkung) == 1
    assert sperre[0].lineno < wirkung[0].lineno

    wache = [
        k
        for k in ast.walk(behandle)
        if isinstance(k, ast.If)
        and isinstance(k.test, ast.UnaryOp)
        and isinstance(k.test.op, ast.Not)
        and any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == "beanspruche_knopf"
            for inner in ast.walk(k.test)
        )
    ]
    assert len(wache) == 1
    assert any(isinstance(k, ast.Return) for k in ast.walk(wache[0]))

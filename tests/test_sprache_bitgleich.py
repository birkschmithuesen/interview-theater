"""Dortmund bleibt bitgleich -- auch durch die Sprachumstellung (Karte A1).

Zwei Massstaebe, beide VOR dem ersten Umbauschritt abgelegt (30.09.2026):

* ``docs/prompt-audit/schnappschuss-vor-sprache-a1.txt`` -- jede Prompt-Datei
  und jede zusammengesetzte Systemanweisung (``scripts/prompt_schnappschuss``),
* ``docs/prompt-audit/texte-vor-sprache-a1.txt`` -- jede Modul-Konstante,
  aus der ein Nutzer- oder Modelltext entstehen kann
  (``scripts/text_schnappschuss``, eine Obermenge der spaeteren Texttabelle).

Geprueft wird ohne ``IT_WORKSHOP`` und mit ``dortmund-2026``. Neue Abschnitte
sind erlaubt (eine neue Konstante ist keine Undichtigkeit), ein
verschwundener oder veraenderter ist ein Befund -- ausser er steht in
``VERSCHOBEN`` oder ``GEAENDERT``, mit Grund.
"""

import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, workshop
from scripts import prompt_schnappschuss, text_schnappschuss

WURZEL = Path(__file__).resolve().parent.parent
PROMPTS = WURZEL / "docs" / "prompt-audit" / "schnappschuss-vor-sprache-a1.txt"
TEXTE = WURZEL / "docs" / "prompt-audit" / "texte-vor-sprache-a1.txt"
DORTMUND = "dortmund-2026"

#: Abschnitte, die A1 absichtlich an einen anderen Ort legt: alt -> neu.
#: Der Wert muss am neuen Ort zeichengleich sein.
VERSCHOBEN: dict[str, str] = {}

#: Abschnitte, deren Wert A1 absichtlich aendert -- mit Grund. Jede Zeile
#: hier ist eine Verhaltensaenderung fuer Dortmund.
GEAENDERT: dict[str, str] = {}

_ZEILE = re.compile(r"^(\S+)\s+(\d+)\s+(.*)$")


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _lies(text: str) -> dict[str, str]:
    fertig = {}
    for zeile in text.splitlines():
        pruef, laenge, name = _ZEILE.match(zeile).groups()
        fertig[name] = f"{pruef} {laenge}"
    return fertig


def _vergleiche(erwartet: dict[str, str], jetzt: dict[str, str]) -> None:
    fehlend, abweichend = [], []
    for name, wert in erwartet.items():
        if name in GEAENDERT:
            continue
        ziel = VERSCHOBEN.get(name, name)
        if ziel not in jetzt:
            fehlend.append(name)
        elif jetzt[ziel] != wert:
            abweichend.append(
                f"\n  {name}\n    erwartet: {wert}\n    bekommen: {jetzt[ziel]}")
    assert not fehlend, "verschwunden: " + ", ".join(sorted(fehlend))
    assert not abweichend, "".join(abweichend)


def _prompts_jetzt() -> dict[str, str]:
    anweisungen._CACHE.clear()
    return _lies(prompt_schnappschuss.fingerabdruck())


def _texte_jetzt() -> dict[str, str]:
    return _lies(prompt_schnappschuss.fingerabdruck(text_schnappschuss.teile()))


def test_prompts_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_prompts_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_texte_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_texte_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_massstaebe_sind_nicht_leer():
    assert len(_lies(PROMPTS.read_text(encoding="utf-8"))) >= 121
    assert len(_lies(TEXTE.read_text(encoding="utf-8"))) >= 600


def test_muster_aus_einer_menge_haengt_nicht_am_hashseed():
    """``befehle._SZENE_ENTFERNEN`` entsteht aus ``"|".join(<Menge>)`` --
    ohne Normalisierung wechselte sein Abschnitt mit ``PYTHONHASHSEED``
    (gemessen beim Ablegen des Massstabs). Der Schnappschuss sortiert die
    Alternativen; derselbe Ausdruck mit sortierter Menge ergibt dieselbe Form."""
    from interview_theater import befehle

    sortiert = re.compile(
        r"^(?:szene\s*)?(\d{1,3})\s+(?:"
        + "|".join(sorted(befehle._ENTFERNEN_WOERTER)) + r")\.?$",
        re.IGNORECASE,
    )
    normal = text_schnappschuss._ohne_mengenreihenfolge(
        befehle, befehle._SZENE_ENTFERNEN)
    assert text_schnappschuss.form(normal) == text_schnappschuss.form(sortiert)


def test_jede_ausnahme_hat_einen_grund():
    for name, grund in GEAENDERT.items():
        assert grund.strip(), name
    for alt, neu in VERSCHOBEN.items():
        assert alt != neu, alt

"""Ein Schnappschuss aller Modul-Konstanten, aus denen ein Nutzer- oder
Modelltext entstehen kann -- der Massstab dafuer, dass Dortmund durch die
Sprachumstellung (Karte A1, 30.09.2026) bitgleich bleibt.

``scripts/prompt_schnappschuss.py`` deckt Prompt-Dateien und zusammengesetzte
Systemanweisungen ab. Die Chat- und Knopftexte, die Auftragsvorlagen und die
Koepfe der Nutzertexte stehen aber als Python-Konstanten im Code -- und genau
die werden in A1 auf einen Nachschlagezugriff umgestellt. Dieser
Schnappschuss nimmt **jede** Modul-Konstante (Name in Grossbuchstaben), deren
Wert Text ist oder nur aus Daten mit Text besteht, in allen Modulen ausser
Datenhaltung, Transport und Konfiguration. Das ist absichtlich eine
Obermenge: die Texttabelle entsteht erst waehrend des Umbaus, der Massstab
muss vorher feststehen.

Abgelegt wird je Abschnitt ``sha256  laenge  name``, dasselbe Format wie im
Prompt-Schnappschuss (``prompt_schnappschuss.fingerabdruck``).

Aufruf::

    python -m scripts.text_schnappschuss            # nach stdout
    python -m scripts.text_schnappschuss <datei>    # in eine Datei
"""

import ast
import importlib
import pkgutil
import re
import sys
from pathlib import Path

import interview_theater
from scripts import prompt_schnappschuss

#: Module ohne Nutzertexte. ``workshop`` hat seinen eigenen Feld-fuer-Feld-Test
#: (tests/test_workshop.py), ``sprache`` entsteht erst in Aufgabe 3.
AUSGENOMMEN = frozenset({
    "interview_theater.db", "interview_theater.repo",
    "interview_theater.web_daten", "interview_theater.telegram",
    "interview_theater.llm", "interview_theater.einstellungen",
    "interview_theater.szene_claude", "interview_theater.workshop",
    "interview_theater.sprache",
})

PAKET = "interview_theater."
_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")


def _nur_daten(wert) -> bool:
    if isinstance(wert, (str, int, float, bool)) or wert is None:
        return True
    if isinstance(wert, dict):
        return all(_nur_daten(k) and _nur_daten(v) for k, v in wert.items())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return all(_nur_daten(v) for v in wert)
    return False


def _hat_text(wert) -> bool:
    if isinstance(wert, str):
        return True
    if isinstance(wert, dict):
        return any(_hat_text(v) for v in wert.values())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return any(_hat_text(v) for v in wert)
    return False


def form(wert) -> str | None:
    """Die vergleichbare Form eines Konstantenwerts, oder None, wenn er kein
    Text ist. Mengen werden sortiert (ihre Reihenfolge ist zufaellig),
    Regex als Muster plus Flags, alles andere als ``repr``."""
    if isinstance(wert, str):
        return wert
    if isinstance(wert, re.Pattern):
        return f"re.compile({wert.pattern!r}, {int(wert.flags)})"
    if isinstance(wert, (set, frozenset)) and _nur_daten(wert) and _hat_text(wert):
        return repr(sorted(wert, key=repr))
    if isinstance(wert, (dict, list, tuple)) and _nur_daten(wert) and _hat_text(wert):
        return repr(wert)
    return None


def _zugewiesene_namen(modul) -> list[str]:
    """Die Namen, die das Modul auf oberster Ebene selbst zuweist --
    importierte Namen gehoeren dem Modul, aus dem sie kommen."""
    baum = ast.parse(Path(modul.__file__).read_text(encoding="utf-8"))
    namen: list[str] = []
    for knoten in baum.body:
        if isinstance(knoten, ast.Assign):
            namen += [z.id for z in knoten.targets if isinstance(z, ast.Name)]
        elif (isinstance(knoten, ast.AnnAssign)
              and isinstance(knoten.target, ast.Name) and knoten.value is not None):
            namen.append(knoten.target.id)
    return [n for n in dict.fromkeys(namen) if _NAME.match(n)]


def wert(modul, name: str):
    """Der Wert, wie ihn der Code zur Laufzeit sieht: hat das Modul einen
    Textzugriff ``T`` (Karte A1), dann ueber ``sprache.text`` -- so prueft
    der Bitgleichheits-Test auch, dass der Zugriff im Deutschen dasselbe
    liefert wie die Konstante."""
    from interview_theater import sprache

    if isinstance(getattr(modul, "T", None), sprache.Texte):
        return sprache.text(modul.__name__, name)
    return getattr(modul, name)


def _ohne_mengenreihenfolge(modul, muster: re.Pattern) -> re.Pattern:
    """Ein Muster, dessen Alternativen aus einer Menge desselben Moduls
    gebaut sind (``"|".join(MENGE)``), mit sortierten Alternativen.

    Gemessen am 30.09.2026: ``befehle._SZENE_ENTFERNEN`` entsteht aus der
    Menge ``_ENTFERNEN_WOERTER``, und ihre Reihenfolge haengt an
    ``PYTHONHASHSEED`` -- der Mustertext wechselte von Lauf zu Lauf, das
    Verhalten nicht. Innerhalb eines Prozesses ist die Reihenfolge dieselbe
    wie beim Kompilieren, die Verbindung ist also wiederzufinden."""
    text = muster.pattern
    for name in _zugewiesene_namen(modul):
        menge = getattr(modul, name, None)
        if (isinstance(menge, (set, frozenset)) and len(menge) > 1
                and all(isinstance(w, str) for w in menge)):
            text = text.replace("|".join(menge), "|".join(sorted(menge)))
    return muster if text == muster.pattern else re.compile(text, muster.flags)


def teile() -> list[tuple[str, str]]:
    stuecke: list[tuple[str, str]] = []
    module = sorted(
        pkgutil.walk_packages(interview_theater.__path__, PAKET),
        key=lambda info: info.name,
    )
    for info in module:
        if info.name in AUSGENOMMEN:
            continue
        modul = importlib.import_module(info.name)
        kurz = info.name[len(PAKET):]
        for name in _zugewiesene_namen(modul):
            roh = wert(modul, name)
            if isinstance(roh, re.Pattern):
                roh = _ohne_mengenreihenfolge(modul, roh)
            text = form(roh)
            if text is not None:
                stuecke.append((f"{kurz}.{name}", text))
    return stuecke


def main() -> None:
    text = prompt_schnappschuss.fingerabdruck(teile())
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10))} Abschnitte nach {sys.argv[1]}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()

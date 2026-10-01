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

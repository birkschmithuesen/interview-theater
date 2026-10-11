"""Die Stueckwerkzeuge als Werkzeuge eines Tool-Calling-Modells (Karte
t_9b2b33cb, Messung 2: Pipeline gegen Agent).

Fachlogik ohne SQL, ohne Modellaufruf, ohne ``tg``. Bindet
``stueck.WERKZEUGE`` (deren Zuschnitt ``(conn, chat_id, *, <JSON-Werte>)``
genau dafuer gebaut ist, ``stueck``-Docstring) plus EIN generisches
Werkzeug ``aenderung_melden`` fuer alle Erkenner-Arten ohne Stueckwerkzeug
(Interview, Phase, Szene schreiben, ...). Das generische fuehrt NICHTS aus:
es sammelt ``{"art", "wert"}`` fuer den heutigen ``erkenner.wende_an``-Weg
mit seinen Waechtern. ``szene_planen`` bleibt dort im Enum, weil kein
Stueckwerkzeug eine NEUE Szene anlegt.

``als_aenderung`` uebersetzt einen Aufruf in die Korpus-Sprache zurueck --
eine Messgrenze, siehe Spec § 2.3."""

from __future__ import annotations

import inspect
import json
import types
import typing
from dataclasses import dataclass

from interview_theater import stueck

GENERISCH = "aenderung_melden"

#: Rueckuebersetzung fuer Korpusvergleich und "Notiert:"-Meldung. Werkzeuge
#: ohne Eintrag (frage_*, szene_wieder_oeffnen, reihenfolge_aendern,
#: pruefe_szene) haben keine Korpus-Art.
ART_FUER_WERKZEUG = {
    "setze_rahmen": "rahmen_setzen",
    "setze_ort": "szene_planen",
    "setze_besetzung": "szene_planen",
    "figur_aus_szene": "szene_planen",
    "karte_aendern": "szene_planen",
    "figur_hinzu": "figur_setzen",
}

_AUSGEBLENDET = ("conn", "chat_id", "quelle", "szene_id")

_BESCHREIBUNG_GENERISCH = (
    "Meldet eine Aenderungsabsicht der Gruppe, fuer die es kein eigenes "
    "Werkzeug gibt (art wie im Erkenner-Prompt, wert als Text)."
)


@dataclass(frozen=True)
class Ausfuehrung:
    name: str
    eingabe: dict
    ok: bool
    ergebnis: dict | None
    fehler: str | None
    generisch: dict | None


def _json_typ(annotation) -> dict:
    herkunft = typing.get_origin(annotation)
    if herkunft in (typing.Union, types.UnionType):
        echte = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _json_typ(echte[0])
    if herkunft is list:
        (inneres,) = typing.get_args(annotation)
        return {"type": "array", "items": _json_typ(inneres)}
    return {int: {"type": "integer"}, str: {"type": "string"},
            bool: {"type": "boolean"}}[annotation]


def _input_schema(funktion) -> dict:
    hinweise = typing.get_type_hints(funktion)
    eigenschaften, pflicht = {}, []
    for name, parameter in inspect.signature(funktion).parameters.items():
        if name in _AUSGEBLENDET or parameter.kind is not parameter.KEYWORD_ONLY:
            continue
        eigenschaften[name] = _json_typ(hinweise[name])
        if parameter.default is parameter.empty:
            pflicht.append(name)
    return {"type": "object", "properties": eigenschaften, "required": pflicht}


def _beschreibung(funktion) -> str:
    text = inspect.getdoc(funktion) or funktion.__name__.replace("_", " ")
    return text.split("\n\n")[0]


def definitionen(arten: tuple[str, ...]) -> list[dict]:
    """Anthropic-``tools``-Liste: je Stueckwerkzeug eine Definition aus der
    Signatur, zuletzt ``aenderung_melden`` mit ``arten`` als Enum."""
    defs = []
    for name in stueck.WERKZEUGE:
        funktion = getattr(stueck, name)
        defs.append({"name": name, "description": _beschreibung(funktion),
                     "input_schema": _input_schema(funktion)})
    defs.append({
        "name": GENERISCH,
        "description": _BESCHREIBUNG_GENERISCH,
        "input_schema": {
            "type": "object",
            "properties": {"art": {"type": "string", "enum": list(arten)},
                           "wert": {"type": "string"}},
            "required": ["art", "wert"],
        },
    })
    return defs


def fuehre_aus(conn, chat_id: int, name: str, eingabe: dict) -> Ausfuehrung:
    """Fuehrt EINEN Werkzeugaufruf aus. Nie eine Ausnahme nach aussen: ein
    falscher Name oder falsche Argumente werden ein ``Ausfuehrung(ok=False)``,
    das das Modell im ``tool_result`` sieht."""
    eingabe = dict(eingabe or {})
    if name == GENERISCH:
        generisch = {"art": str(eingabe.get("art", "")), "wert": str(eingabe.get("wert", ""))}
        return Ausfuehrung(name, eingabe, True, {"ok": True, "vorgemerkt": True}, None, generisch)
    if name not in stueck.WERKZEUGE:
        return Ausfuehrung(name, eingabe, False, None, f"Werkzeug {name!r} unbekannt", None)
    argumente = {k: v for k, v in eingabe.items() if k not in _AUSGEBLENDET}
    try:
        ergebnis = getattr(stueck, name)(conn, chat_id, **argumente,
                                         quelle=stueck.QUELLE_AGENT)
    except TypeError as fehler:
        return Ausfuehrung(name, eingabe, False, None, f"Argumente: {fehler}", None)
    daten = ergebnis.als_dict()
    return Ausfuehrung(name, eingabe, bool(ergebnis.ok), daten, ergebnis.fehler, None)


def als_tool_result(a: Ausfuehrung) -> tuple[str, bool]:
    """Text und ``is_error`` des ``tool_result``-Blocks."""
    if a.ergebnis is None:
        return json.dumps({"ok": False, "fehler": a.fehler}, ensure_ascii=False), True
    return json.dumps(a.ergebnis, ensure_ascii=False), not a.ok


def als_aenderung(a: Ausfuehrung) -> dict | None:
    """``{"art", "wert"}`` in der Korpus-Sprache, oder ``None`` (abgelehnt
    oder Werkzeug ohne Korpus-Art)."""
    if a.generisch is not None:
        return dict(a.generisch)
    if not a.ok or a.name not in ART_FUER_WERKZEUG:
        return None
    teile = [str(v) for v in a.eingabe.values() if isinstance(v, (str, int))]
    teile += [str(x) for v in a.eingabe.values() if isinstance(v, list) for x in v]
    return {"art": ART_FUER_WERKZEUG[a.name], "wert": " ".join(teile)}

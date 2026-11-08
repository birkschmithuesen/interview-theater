"""Werkzeug-Zuschnitt (Karte t_fd88600b): jede Mutation ist 1:1 als Werkzeug
eines spaeteren Agenten aufrufbar -- (conn, chat_id, *, JSON-Werte) ->
Ergebnis, ohne tg/klm/e. Rot, sobald jemand eine Oberflaechen-Abhaengigkeit
in die Schnittstelle zieht."""

import inspect
import typing

from interview_theater import stueck

_JSON = {int, str, bool, type(None), list, dict, float}


def _json_typ(annot) -> bool:
    if annot in _JSON:
        return True
    herkunft = typing.get_origin(annot)
    if herkunft in (list, dict):
        return all(_json_typ(a) for a in typing.get_args(annot))
    if herkunft in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        return all(_json_typ(a) for a in typing.get_args(annot))
    return False


def test_werkzeuge_sind_schlank():
    for name in stueck.WERKZEUGE:
        f = getattr(stueck, name)
        sig = inspect.signature(f, eval_str=True)
        params = list(sig.parameters.values())
        assert [p.name for p in params[:2]] == ["conn", "chat_id"], name
        for p in params[2:]:
            assert p.kind is inspect.Parameter.KEYWORD_ONLY, (name, p.name)
            assert p.name not in {"tg", "klm", "e"}, (name, p.name)
            assert _json_typ(p.annotation), (name, p.name, p.annotation)
        assert sig.return_annotation is stueck.Ergebnis, name

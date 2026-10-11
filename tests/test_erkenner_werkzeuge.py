import json

import pytest

from interview_theater import erkenner_werkzeuge as ew, repo, stueck

CHAT = 1


def _namen(defs):
    return [d["name"] for d in defs]


def test_definitionen_haben_alle_stueckwerkzeuge_und_generisch():
    defs = ew.definitionen(("interview_starten", "szene_planen"))
    assert _namen(defs) == list(stueck.WERKZEUGE) + [ew.GENERISCH]


def test_schema_aus_signatur_ohne_quelle_und_szene_id():
    defs = {d["name"]: d for d in ew.definitionen(("szene_planen",))}
    ort = defs["setze_ort"]["input_schema"]
    assert ort["type"] == "object"
    assert set(ort["properties"]) == {"szene", "ort"}
    assert ort["properties"]["szene"] == {"type": "integer"}
    assert ort["required"] == []
    karte = defs["karte_aendern"]["input_schema"]
    assert karte["required"] == ["szene"]
    assert karte["properties"]["punkte"] == {"type": "array", "items": {"type": "string"}}
    assert karte["properties"]["zitate"] == {"type": "array", "items": {"type": "integer"}}
    for d in defs.values():
        assert "quelle" not in d["input_schema"]["properties"]
        assert "szene_id" not in d["input_schema"]["properties"]


def test_generisch_enum_ist_die_uebergebene_artenliste():
    defs = {d["name"]: d for d in ew.definitionen(("a", "b"))}
    schema = defs[ew.GENERISCH]["input_schema"]
    assert schema["properties"]["art"]["enum"] == ["a", "b"]
    assert schema["required"] == ["art", "wert"]


def test_fuehre_aus_setze_rahmen_schreibt_mit_quelle_agent(conn):
    a = ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"rahmen": "Ein Bahnhof bei Nacht"})
    assert a.ok is True and a.fehler is None
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Ein Bahnhof bei Nacht"
    text, ist_fehler = ew.als_tool_result(a)
    assert ist_fehler is False
    assert json.loads(text)["ok"] is True


def test_fuehre_aus_unbekanntes_werkzeug_ist_fehler_keine_ausnahme(conn):
    a = ew.fuehre_aus(conn, CHAT, "loesche_alles", {})
    assert a.ok is False and "unbekannt" in a.fehler
    assert ew.als_tool_result(a)[1] is True


def test_fuehre_aus_falsche_argumente_ist_fehler(conn):
    a = ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"falsch": 1})
    assert a.ok is False and a.fehler


def test_fuehre_aus_quelle_aus_dem_modell_wird_ignoriert(conn, monkeypatch):
    gesehen = {}

    def attrappe(conn_, chat_id, **kw):
        gesehen.update(kw)
        return stueck.Ergebnis(ok=True)

    monkeypatch.setattr(stueck, "setze_rahmen", attrappe)
    ew.fuehre_aus(conn, CHAT, "setze_rahmen", {"rahmen": "x", "quelle": "script"})
    assert gesehen["quelle"] == stueck.QUELLE_AGENT


def test_generisch_fuehrt_nichts_aus(conn):
    a = ew.fuehre_aus(conn, CHAT, ew.GENERISCH, {"art": "interview_starten", "wert": ""})
    assert a.ok is True and a.generisch == {"art": "interview_starten", "wert": ""}
    assert ew.als_aenderung(a) == {"art": "interview_starten", "wert": ""}


@pytest.mark.parametrize("name, eingabe, art, teil", [
    ("setze_rahmen", {"rahmen": "Bahnhof"}, "rahmen_setzen", "Bahnhof"),
    ("setze_ort", {"szene": 2, "ort": "Küche"}, "szene_planen", "Küche"),
    ("karte_aendern", {"szene": 1, "worum": "Streit"}, "szene_planen", "Streit"),
    ("figur_hinzu", {"name": "Meryem", "beschreibung": "Mutter"}, "figur_setzen", "Meryem"),
])
def test_als_aenderung_uebersetzt_erfolgreiche_stueckaufrufe(name, eingabe, art, teil):
    a = ew.Ausfuehrung(name=name, eingabe=eingabe, ok=True,
                       ergebnis={"ok": True}, fehler=None, generisch=None)
    aenderung = ew.als_aenderung(a)
    assert aenderung["art"] == art and teil in aenderung["wert"]


def test_als_aenderung_none_bei_ablehnung_und_ohne_korpusart():
    abgelehnt = ew.Ausfuehrung("setze_ort", {"szene": 9, "ort": "x"}, False,
                               {"ok": False}, "keine_szene", None)
    assert ew.als_aenderung(abgelehnt) is None
    frage = ew.Ausfuehrung("frage_stellen", {"frage": "Wer?"}, True, {"ok": True}, None, None)
    assert ew.als_aenderung(frage) is None

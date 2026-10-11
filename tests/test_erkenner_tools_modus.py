"""Erkenner im Tools-Modus (IT_ERKENNER_MODUS=tools, Messung 2, t_9b2b33cb).

Kein Netz: ``szene_claude.werkzeug_schleife`` ist eine Attrappe, die die
``ausfuehren``-Funktion mit vorgegebenen Aufrufen ruft."""

import dataclasses

import pytest

from interview_theater import erkenner, modellwahl, repo, szene_claude, workshop
from interview_theater.szene_claude import Schleifenergebnis
from tests.test_undo_knopf import TelegramAttrappe

CHAT = 1


@pytest.fixture
def tools_e(einst):
    return dataclasses.replace(einst, szene_anbieter="claude", erkenner_modus="tools")


@pytest.fixture
def ueber_claude_an(monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: True)
    monkeypatch.setattr(modellwahl, "konversation_ueber_claude", lambda e, c, ch: True)


def _nachricht(conn, text, mid=10):
    repo.merke_nachricht(conn, CHAT, mid, "Sara", 0, "text", text, repo._jetzt())


class KlmVerboten:
    def schema(self, *a, **k):
        raise AssertionError("JSON-Pfad darf im Tools-Modus nicht laufen")


def _schleife(aufrufe_und_ergebnisse):
    """Attrappe fuer ``szene_claude.werkzeug_schleife``: ruft ``ausfuehren``
    mit den vorgegebenen Aufrufen, wie es das Modell taete."""
    def schleife(conn, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        protokoll = []
        for name, eingabe in aufrufe_und_ergebnisse:
            text, fehler = ausfuehren(name, eingabe)
            protokoll.append({"name": name, "eingabe": eingabe, "is_error": fehler})
        return Schleifenergebnis(tuple(protokoll), 2, None, 10, 5, 1, "")
    return schleife


def _vorfaelle(conn):
    return [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]


def test_json_ist_vorgabe(conn, einst, ueber_claude_an):
    assert erkenner.werkzeug_modus(einst, conn, CHAT) is False


def test_tools_ohne_ueber_claude_bleibt_json(conn, tools_e, monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: False)
    assert erkenner.werkzeug_modus(tools_e, conn, CHAT) is False


def test_tools_mit_ueber_claude_ist_werkzeugmodus(conn, tools_e, ueber_claude_an):
    assert erkenner.werkzeug_modus(tools_e, conn, CHAT) is True


def test_tools_modus_schreibt_ueber_stueck_und_sammelt_generisches(
        conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "der Rahmen ist ein Bahnhof bei Nacht, und wir machen jetzt ein Interview")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("setze_rahmen", {"rahmen": "Bahnhof bei Nacht"}),
        ("aenderung_melden", {"art": "interview_starten", "wert": ""}),
    ]))
    aenderungen, schritte = erkenner.erkenne_mit_werkzeugschritten(
        KlmVerboten(), conn, tools_e, CHAT)
    assert aenderungen == [{"art": "interview_starten", "wert": ""}]
    assert schritte == [{"art": "rahmen_setzen", "wert": "Bahnhof bei Nacht"}]
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Bahnhof bei Nacht"
    assert repo.unextrahierte(conn, CHAT) == []


def test_unbekannte_art_aus_generisch_wird_verworfen(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "egal")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("aenderung_melden", {"art": "gibt_es_nicht", "wert": "x"}),
    ]))
    assert erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT) == []


def test_erste_runde_scheitert_faellt_auf_json_zurueck(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "wir machen jetzt ein Interview")

    def kaputt(*a, **k):
        raise szene_claude.ClaudeFehler("proxy weg")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", kaputt)
    gesehen = {}

    def schema_aufruf(klm, conn_, e, chat_id, system, nutzer, schema_, art):
        gesehen["ja"] = True
        return {"aenderungen": [{"art": "interview_starten", "wert": ""}]}

    monkeypatch.setattr(erkenner, "_schema_aufruf", schema_aufruf)
    aenderungen, schritte = erkenner.erkenne_mit_werkzeugschritten(
        KlmVerboten(), conn, tools_e, CHAT)
    assert gesehen["ja"] and aenderungen == [{"art": "interview_starten", "wert": ""}]
    assert schritte == []
    assert "erkenner_werkzeug_fallback" in _vorfaelle(conn)


def test_ausnahme_nach_ausgefuehrtem_werkzeug_kein_json_lauf(
        conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "der Rahmen ist ein Bahnhof bei Nacht")

    def schleife(conn_, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        ausfuehren("setze_rahmen", {"rahmen": "Bahnhof bei Nacht"})
        raise KeyError("id")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    aenderungen, schritte = erkenner.erkenne_mit_werkzeugschritten(
        KlmVerboten(), conn, tools_e, CHAT)
    assert aenderungen == []
    assert schritte == [{"art": "rahmen_setzen", "wert": "Bahnhof bei Nacht"}]
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Bahnhof bei Nacht"
    assert "erkenner_werkzeug_fallback" not in _vorfaelle(conn)
    assert "erkenner_werkzeug_abbruch" in _vorfaelle(conn)
    assert repo.unextrahierte(conn, CHAT) == []


def test_abbruch_wird_als_vorfall_gemeldet(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "x")

    def schleife(*a, **k):
        return Schleifenergebnis((), 6, "runden", 1, 1, 1, "")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT)
    assert "erkenner_werkzeug_abbruch" in _vorfaelle(conn)


def test_werkzeug_prompt_haengt_am_erkenner_prompt(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "x")
    gesehen = {}

    def schleife(conn_, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        gesehen["system"], gesehen["werkzeuge"] = system, werkzeuge
        return Schleifenergebnis((), 1, None, 1, 1, 1, "nichts")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT)
    assert gesehen["system"].startswith(erkenner.prompt())
    assert "aenderung_melden" in gesehen["system"]
    assert gesehen["werkzeuge"][-1]["input_schema"]["properties"]["art"]["enum"] == list(
        erkenner.aktive_arten())


def test_ausfuehren_wirft_nie_auch_bei_kaputtem_werkzeug(conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "x")
    from interview_theater import erkenner_werkzeuge

    def boese(*a, **k):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(erkenner_werkzeuge, "fuehre_aus", boese)
    ergebnisse = []

    def schleife(conn_, e, klient, chat_id, system, nutzer, werkzeuge, ausfuehren, **kw):
        ergebnisse.append(ausfuehren("setze_rahmen", {"rahmen": "x"}))
        return Schleifenergebnis((), 1, None, 1, 1, 1, "")

    monkeypatch.setattr(szene_claude, "werkzeug_schleife", schleife)
    erkenner.erkenne(KlmVerboten(), conn, tools_e, CHAT)
    assert ergebnisse and ergebnisse[0][1] is True


def test_laufe_nennt_werkzeugschritt_in_der_notiert_meldung(
        conn, tools_e, ueber_claude_an, monkeypatch):
    _nachricht(conn, "der Rahmen ist ein Bahnhof bei Nacht")
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _schleife([
        ("setze_rahmen", {"rahmen": "Bahnhof bei Nacht"}),
    ]))
    tg = TelegramAttrappe()
    erkenner.laufe(KlmVerboten(), tg, conn, tools_e, CHAT)
    assert any("Bahnhof bei Nacht" in t for t in tg.texte)

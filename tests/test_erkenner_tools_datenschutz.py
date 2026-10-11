"""Interviews bleiben hart auf Infomaniak -- in BEIDEN Erkenner-Modi
(Spec § 4; modellwahl.konversation_ueber_claude, PHASE_INTERVIEWS)."""

import ast
import dataclasses
from pathlib import Path

import pytest

from interview_theater import erkenner, repo, szene_claude, workshop

CHAT = 1
WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture(params=["json", "tools"])
def e_modus(request, einst):
    return dataclasses.replace(einst, szene_anbieter="claude", erkenner_modus=request.param)


@pytest.fixture
def schalter_an(monkeypatch):
    monkeypatch.setattr(workshop, "erkenner_ueber_claude_aktiv", lambda profil=None: True)


def _verboten(*a, **k):
    raise AssertionError("Proxy darf hier nicht gerufen werden")


def test_kontrolle_phase_5_laeuft_ueber_claude(conn, e_modus, schalter_an):
    """Positivkontrolle: ohne sie waeren die Phase-3-Tests leer."""
    repo.setze_phase(conn, CHAT, 5)
    repo.setze_szene_usa(conn, CHAT, True)
    assert erkenner.ueber_claude(e_modus, conn, CHAT) is True
    assert erkenner.werkzeug_modus(e_modus, conn, CHAT) is (e_modus.erkenner_modus == "tools")


def test_phase_3_nie_ueber_claude_in_beiden_modi(conn, e_modus, schalter_an):
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_szene_usa(conn, CHAT, True)
    assert erkenner.ueber_claude(e_modus, conn, CHAT) is False
    assert erkenner.werkzeug_modus(e_modus, conn, CHAT) is False


def test_phase_3_erkenne_ruft_keinen_proxy(conn, e_modus, schalter_an, monkeypatch):
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_szene_usa(conn, CHAT, True)
    repo.merke_nachricht(conn, CHAT, 10, "Sara", 0, "text",
                         "wir machen jetzt ein Interview", repo._jetzt())
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _verboten)
    monkeypatch.setattr(szene_claude, "schema", _verboten, raising=False)

    class Klm:
        def schema(self, *a, **k):
            return {"aenderungen": [{"art": "interview_starten", "wert": ""}]}

    assert erkenner.erkenne(Klm(), conn, e_modus, CHAT) == [
        {"art": "interview_starten", "wert": ""}]


def test_aufnahme_erkenner_nie_ueber_claude(conn, e_modus, schalter_an, monkeypatch):
    repo.setze_phase(conn, CHAT, 5)
    repo.setze_szene_usa(conn, CHAT, True)
    monkeypatch.setattr(szene_claude, "werkzeug_schleife", _verboten)
    monkeypatch.setattr(szene_claude, "schema", _verboten, raising=False)

    class Klm:
        def schema(self, *a, **k):
            return {"aenderungen": []}

    assert erkenner.erkenne_in_aufnahme(Klm(), conn, e_modus, CHAT, "so das wars") == []


def test_verdichter_kennt_weder_werkzeuge_noch_proxy():
    baum = ast.parse((WURZEL / "interview_theater" / "verdichter.py").read_text(encoding="utf-8"))
    namen = {n.id for n in ast.walk(baum) if isinstance(n, ast.Name)}
    namen |= {n.attr for n in ast.walk(baum) if isinstance(n, ast.Attribute)}
    namen |= {a.name.split(".")[-1] for n in ast.walk(baum) if isinstance(n, ast.ImportFrom)
              for a in n.names}
    assert not {"erkenner_werkzeuge", "werkzeug_schleife", "szene_claude"} & namen

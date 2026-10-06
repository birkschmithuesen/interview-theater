"""Erkenner-art ``recherche_starten`` (Karte t_c5117c91): "research: ..." /
"can you look up ..." im Chat -- nur wirksam, wenn ``recherche.aktiv`` im
Profil an ist. Kein Schreibpfad (wie ``szene_schreiben``): der Netz- und
Modellaufruf geht in einen Thread (``knoepfe.szenen.starte_recherche_lauf``).
"""

import pytest

from interview_theater import erkenner, phasen, repo, workshop
from test_erkenner import LLMAttrappe, TelegramAttrappe, _nachricht


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture
def dortmund(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_dortmund_sieht_recherche_starten_nicht_im_schema(dortmund):
    enum = erkenner.schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    assert "recherche_starten" in erkenner.ARTEN
    assert "recherche_starten" not in enum


def test_padua_hat_recherche_starten_im_schema(padua):
    enum = erkenner.schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    assert "recherche_starten" in enum


def test_recherche_starten_wirkt_nicht_vor_phase_4(conn, padua):
    phasen.setze(conn, 1, 3, "test")
    assert not erkenner._ist_phasenpassend(conn, 1, "recherche_starten")
    phasen.setze(conn, 1, 4, "test")
    assert erkenner._ist_phasenpassend(conn, 1, "recherche_starten")


def test_recherche_starten_wirkt_nirgends_in_dortmund(conn, dortmund):
    phasen.setze(conn, 1, 6, "test")
    assert not erkenner._ist_phasenpassend(conn, 1, "recherche_starten")


def test_recherche_starten_veraendert_den_arbeitsstand_nicht(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "recherche_starten", "wert": "When was it founded?"}]
    )
    assert wirkliche == []
    assert repo.hole_arbeitsstand(conn, 1) is None


def test_laufe_stoesst_die_recherche_an(conn, einst, monkeypatch, padua):
    from interview_theater.knoepfe import szenen

    gesehen = []
    monkeypatch.setattr(
        szenen, "starte_recherche_lauf",
        lambda conn, tg, klm, e, chat_id, frage: gesehen.append((chat_id, frage)),
    )
    phasen.setze(conn, 1, 4, "test")
    _nachricht(conn, 1, 1, "research: when was the bridge built?")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "recherche_starten", "wert": "When was the bridge built?"},
    ]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert gesehen == [(1, "When was the bridge built?")]


def test_ohne_frage_laeuft_keine_recherche(conn, einst, monkeypatch, padua):
    from interview_theater.knoepfe import szenen

    monkeypatch.setattr(
        szenen, "starte_recherche_lauf",
        lambda *a: pytest.fail("keine Frage, kein Lauf"),
    )
    phasen.setze(conn, 1, 4, "test")
    _nachricht(conn, 1, 1, "wir sollten mal recherchieren")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

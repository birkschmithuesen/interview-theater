"""Der Research-Knopf (Karte t_c5117c91): Angebot -> Fragenvorschlag (Thread)
-> Frage waehlen -> Recherchelauf (Thread) -> Karte im Chat. Kein
Modellaufruf in einem Handler selbst (Zusage 2) -- der laeuft hier unter
einer Attrappe synchron, weil ``threading.Thread`` in Tests ohne Daemon-Join
sonst racet; die Produktionsfunktionen starten echte Threads."""

import threading
import time

import pytest

from interview_theater import db, recherche, repo
from interview_theater.knoepfe import szenen
from test_erkenner import TelegramAttrappe

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _warte_auf_threads(vorher: set[int], timeout: float = 2.0) -> None:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        neue = {t.ident for t in threading.enumerate()} - vorher
        laufende = [t for t in threading.enumerate() if t.ident in neue and t.is_alive()]
        if not laufende:
            return
        time.sleep(0.01)


def test_biete_recherche_sendet_genau_einen_knopf(conn):
    tg = TelegramAttrappe()

    message_id = szenen.biete_recherche(conn, tg, CHAT)

    assert message_id is not None
    [(chat_id, text, leiste)] = tg.mit_knoepfen
    assert chat_id == CHAT
    assert len(leiste) == 1


def test_starte_fragenvorschlag_zeigt_drei_fragen_als_knoepfe(conn):
    tg = TelegramAttrappe()
    vorher = {t.ident for t in threading.enumerate()}

    class KLM:
        def schema(self, chat_id, system, nutzer, schema, art, **kw):
            return {"fragen": ["When was it founded?", "Who built it?", "Why there?"]}

    szenen.starte_fragenvorschlag(conn, tg, KLM(), None, CHAT)
    _warte_auf_threads(vorher)

    [(chat_id, text, leiste)] = tg.mit_knoepfen
    assert chat_id == CHAT
    assert len(leiste) == 3
    assert leiste[0][0] == "When was it founded?"


def test_starte_fragenvorschlag_ohne_fragen_sagt_das(conn):
    tg = TelegramAttrappe()
    vorher = {t.ident for t in threading.enumerate()}

    class KLM:
        def schema(self, chat_id, system, nutzer, schema, art, **kw):
            return {"fragen": []}

    szenen.starte_fragenvorschlag(conn, tg, KLM(), None, CHAT)
    _warte_auf_threads(vorher)

    assert tg.mit_knoepfen == []
    assert len(tg.gesendet) >= 1


def test_starte_recherche_lauf_postet_die_karte(conn, monkeypatch):
    tg = TelegramAttrappe()
    vorher = {t.ident for t in threading.enumerate()}
    gesehen = []

    def _starte_attrappe(klm, conn, e, chat_id, frage, **kw):
        gesehen.append(frage)
        return repo.speichere_recherche(
            conn, chat_id, frage, "The bridge was built in 1900 (Example, https://x.test).", []
        )

    monkeypatch.setattr(recherche, "starte", _starte_attrappe)

    szenen.starte_recherche_lauf(conn, tg, None, None, CHAT, "When was the bridge built?")
    _warte_auf_threads(vorher)

    assert gesehen == ["When was the bridge built?"]
    texte = [t for _, t in tg.gesendet]
    assert any("1900" in t for t in texte)


def test_starte_recherche_lauf_ohne_treffer_sagt_das(conn, monkeypatch):
    tg = TelegramAttrappe()
    vorher = {t.ident for t in threading.enumerate()}
    monkeypatch.setattr(recherche, "starte", lambda *a, **kw: None)

    szenen.starte_recherche_lauf(conn, tg, None, None, CHAT, "Irrelevant?")
    _warte_auf_threads(vorher)

    texte = [t for _, t in tg.gesendet]
    assert len(texte) >= 2  # "laeuft" + "nichts gefunden"

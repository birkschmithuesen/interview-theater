"""Der Web-Kanal bekommt eine Senke, der Telegram-Kanal nicht (E1).

Die Senke ist der einzige Ort, an dem ein laufender Modelltext in die
Datenbank geht. Sie merkt sich ihre Zeile im Kanal, damit ``ablauf.antworte``
sie nach dem Versand abschliessen kann, ohne sie durch drei Funktionen
durchzureichen.
"""

import pytest

from interview_theater import db, repo, strom, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def kanal(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio")), conn


def test_telegram_bekommt_keine_senke():
    """E1: der Telegram-Weg bleibt Zeichen fuer Zeichen, wie er war."""
    assert not hasattr(telegram.Telegram, "strom")
    assert not hasattr(telegram.Telegram, "strom_abschluss")


def test_die_senke_legt_erst_beim_ersten_stueck_an(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    assert repo.laufende_stroeme(conn, CHAT) == []
    senke("Hallo")
    assert [z["text"] for z in repo.laufende_stroeme(conn, CHAT)] == ["Hallo"]


def test_der_abschluss_traegt_die_post_id_ein(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    senke("Hallo ihr")
    # strom_id wird VOR dem Abschluss gelesen: ``Senke.fertig`` setzt die
    # eigene id danach auf None zurueck (Idempotenz, siehe
    # ``tests/test_strom.py::test_zweimal_fertig_beendet_nur_einmal``), die
    # Zeile in der Datenbank bleibt aber unter der alten id stehen.
    strom_id = senke.strom_id
    tg.strom_abschluss(CHAT, post_id=99)
    zeile = repo.hole_strom(conn, strom_id)
    assert (zeile["zustand"], zeile["post_id"]) == (repo.STROM_FERTIG, 99)


def test_ein_abbruch_hinterlaesst_keine_nachricht(kanal):
    tg, conn = kanal
    senke = tg.strom(CHAT, "gespraech")
    senke("halb")
    strom_id = senke.strom_id
    tg.strom_abschluss(CHAT, abgebrochen=True)
    assert repo.hole_strom(conn, strom_id)["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.laufende_stroeme(conn, CHAT) == []


def test_ein_abschluss_ohne_laufenden_strom_tut_nichts(kanal):
    tg, _conn = kanal
    tg.strom_abschluss(CHAT, post_id=5)   # wirft nicht


def test_die_hilfsfunktionen_finden_den_kanal(kanal):
    """``strom.senke``/``schliesse``/``verwirf`` sind die EINE Stelle, an der
    ein Callsite nach Streaming fragt (Entscheidung C)."""
    tg, conn = kanal
    senke = strom.senke(tg, CHAT, "gespraech")
    senke("Text")
    strom_id = senke.strom_id
    strom.schliesse(tg, CHAT, 3)
    assert repo.hole_strom(conn, strom_id)["post_id"] == 3


def test_ein_zweiter_strom_beendet_den_ersten_nicht_versehentlich(kanal):
    """Zwei Zuege hintereinander: der zweite bekommt eine eigene Zeile."""
    tg, conn = kanal
    erste = tg.strom(CHAT, "gespraech")
    erste("a")
    erste_id = erste.strom_id
    tg.strom_abschluss(CHAT, post_id=1)
    zweite = tg.strom(CHAT, "gespraech")
    zweite("b")
    zweite_id = zweite.strom_id
    tg.strom_abschluss(CHAT, post_id=2)
    assert erste_id != zweite_id
    assert repo.hole_strom(conn, erste_id)["post_id"] == 1
    assert repo.hole_strom(conn, zweite_id)["post_id"] == 2

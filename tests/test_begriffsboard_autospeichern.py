"""Birk 05.10.2026 (Live-Test Gruppe 2, Nachtrag 2-4): was im CoThinker
steht, IST gespeichert. Nach jedem Boardlauf in Phase 1 gehen die Top 5 nach
``arbeitsstand.begriffe`` (ohne Chatzeile, Undo-faehig) -- nie ueber einen
Wert der Gruppe hinweg. Nach "Discussion done" kommt bei JEDEM
Diskussionsende die Liste, "gespeichert", EINE Frage mit zwei Knoepfen
("Yes, on to the questions" / "Change something") und Undo. Nur erfundenes
Material."""

import time

import pytest

from interview_theater import (aufnahme, begriffsboard, db, diskussion, einstellungen,
                               knoepfe, phasen, repo, sprache, workshop)
from interview_theater.knoepfe import texte

CHAT = 1


def _e(begriff, status="kandidat", zustimmung=0, nennungen=1):
    return {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
            "begruendung": "", "zitat": "", "doppelbedeutung": "", "status": status,
            "vorheriger_begriff": ""}


VIER = [_e("Heimat", "favorit", 2, 3), _e("Grenze", zustimmung=1), _e("Mut"), _e("Schule")]
TEXT = "Heimat und Grenze und Mut und Schule, darueber reden wir."


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet, self.mit_knoepfen, self._id = [], [], 800

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((text, list(knoepfe_)))
        return mid

    def beantworte_knopf(self, callback_query_id, text=""):
        pass

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def aendere_knoepfe(self, *a, **k):
        pass

    def aendere_text(self, *a, **k):
        pass

    def tippt(self, chat_id):
        pass


class _KLM:
    def __init__(self, *boards):
        self.boards, self.aufrufe = list(boards), 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"board": self.boards.pop(0) if self.boards else []}


def _segment(conn, message_id, schnittgrund, text=TEXT):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund=schnittgrund)
    repo.setze_transkript(conn, aid, text)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def _lauf(conn, einst, klm):
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def _begriffe(conn):
    stand = repo.hole_arbeitsstand(conn, CHAT)
    return stand["begriffe"] if stand is not None else None


def test_boardlauf_mit_vier_kandidaten_speichert_und_oeffnet_phase_2(conn, einst):
    repo.setze_status(conn, _segment(conn, 10, "pause")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER))
    assert _begriffe(conn) == "Heimat, Grenze, Mut, Schule"
    assert phasen.voraussetzungen(conn, CHAT)[2] is True
    detail = repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"]
    assert detail and "Heimat" in detail


def test_gespeichert_werden_nur_die_top_fuenf_ohne_verworfene(conn, einst):
    repo.setze_status(conn, _segment(
        conn, 10, "pause", TEXT + " Musik, Angst und Freunde auch.")["id"], "fertig")
    board = VIER + [_e("Musik", "verworfen", 2, 9), _e("Angst"), _e("Freunde")]
    _lauf(conn, einst, _KLM(board))
    gespeichert = _begriffe(conn).split(", ")
    assert len(gespeichert) == 5 and "Musik" not in gespeichert


def test_eigene_begriffe_der_gruppe_werden_nie_ueberschrieben(conn, einst):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Hafen, Nacht")
    repo.setze_status(conn, _segment(conn, 10, "pause")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER))
    assert _begriffe(conn) == "Hafen, Nacht"


def test_ein_spaeterer_lauf_schreibt_den_auto_wert_fort(conn, einst):
    repo.setze_status(conn, _segment(conn, 10, "pause")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER))
    repo.setze_status(conn, _segment(conn, 11, "pause", "Und Angst, ganz klar.")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER + [_e("Angst", "favorit", 2, 5)]))
    assert "Angst" in _begriffe(conn)


def test_der_lauf_selbst_schreibt_keine_chatzeile(conn, einst):
    """Waehrend der Aufnahme schweigt der Bot: der Lauf kennt kein ``tg``."""
    repo.setze_status(conn, _segment(conn, 10, "pause")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER))
    assert repo.letzte_nachrichten(conn, CHAT, 50) is not None
    bot = conn.execute("SELECT COUNT(*) FROM nachricht WHERE chat_id = ? AND ist_bot = 1",
                       (CHAT,)).fetchone()[0]
    assert bot == 0


def _abschluss(conn, einst, tg, klm, message_id=20):
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _segment(conn, message_id, "ende"),
                                aufnahme._kein_zug, False)
    _warte_bis(lambda: tg.mit_knoepfen)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def test_abschlussnachricht_liste_gespeichert_eine_frage_zwei_knoepfe_undo(conn, einst):
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER))
    text, leiste = tg.mit_knoepfen[-1]
    assert text.startswith(knoepfe.T._TEXT_BOARD_GESPEICHERT.split("{")[0])
    for nr, begriff in enumerate(["Heimat", "Grenze", "Mut", "Schule"], 1):
        assert f"{nr}. {begriff}" in text
    beschriftungen = [b for b, _ in leiste]
    assert beschriftungen == [knoepfe.T._TEXT_BOARD_WEITER_KNOPF,
                              knoepfe.T._TEXT_BOARD_AENDERN_KNOPF,
                              knoepfe.T._TEXT_UNDO_KNOPF]
    assert knoepfe.T._TEXT_BOARD_UEBERNEHMEN_KNOPF not in beschriftungen
    weiter = repo.hole_knopf(conn, int(leiste[0][1][2:]))
    assert weiter["art"] == texte.ART_PHASE and weiter["wert"] == "2"


def test_englischer_wortlaut(conn, einst, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        tg = _TG()
        _abschluss(conn, einst, tg, _KLM(VIER))
        text, leiste = tg.mit_knoepfen[-1]
        assert text.startswith("These are your four terms – saved. Shall we move on?\n\n1. Heimat")
        assert [b for b, _ in leiste][:2] == ["Yes, on to the questions", "Change something"]
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


def test_jedes_diskussionsende_bekommt_die_nachricht(conn, einst):
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER), message_id=20)
    _abschluss(conn, einst, tg, _KLM(VIER), message_id=21)
    gespeichert = [t for t, _ in tg.mit_knoepfen
                   if t.startswith(knoepfe.T._TEXT_BOARD_GESPEICHERT.split("{")[0])]
    assert len(gespeichert) == 2


def _druecke(conn, tg, einst, daten):
    return knoepfe.behandle(conn, tg, None, einst, {
        "callback_query_id": "q1", "data": daten, "chat_id": CHAT,
        "chat_titel": "Testgruppe", "message_id": 777,
    })


def test_undo_nimmt_den_auto_wert_zurueck(conn, einst):
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER))
    assert _begriffe(conn)
    _, leiste = tg.mit_knoepfen[-1]
    _druecke(conn, tg, einst, leiste[2][1])
    assert not _begriffe(conn)


def test_undo_ueberlebt_einen_neustart_zwischen_lauf_und_abschluss(conn, einst):
    """R-5 (a): der Undo-Knopf der Abschlussnachricht hing an einem
    Prozess-Merkplatz -- nach einem Bot-Neustart zwischen dem letzten
    Boardlauf und "Discussion done" fehlte er. Jetzt kommt die Lauf-id aus
    der Datenbank (``erkenner_lauf``)."""
    repo.setze_status(conn, _segment(conn, 10, "pause")["id"], "fertig")
    _lauf(conn, einst, _KLM(VIER))
    assert _begriffe(conn)
    # Neustart: kein Prozesszustand traegt die Lauf-id hinueber.
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER))
    _, leiste = tg.mit_knoepfen[-1]
    assert [b for b, _ in leiste][-1] == knoepfe.T._TEXT_UNDO_KNOPF
    _druecke(conn, tg, einst, leiste[-1][1])
    assert not _begriffe(conn)
    assert not hasattr(begriffsboard, "_LETZTER_AUTOLAUF")


def test_etwas_aendern_fragt_in_einem_satz(conn, einst):
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER))
    _, leiste = tg.mit_knoepfen[-1]
    vorher = _begriffe(conn)
    _druecke(conn, tg, einst, leiste[1][1])
    assert tg.gesendet[-1] == knoepfe.T._TEXT_BOARD_WAS_AENDERN
    assert _begriffe(conn) == vorher
    zeile = conn.execute("SELECT text FROM nachricht WHERE chat_id = ? AND ist_bot = 1 "
                         "ORDER BY rowid DESC LIMIT 1", (CHAT,)).fetchone()
    assert zeile["text"] == knoepfe.T._TEXT_BOARD_WAS_AENDERN


def test_eigene_begriffe_bekommen_weiter_den_vorschlag_mit_take_these(conn, einst):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Hafen, Nacht")
    tg = _TG()
    _abschluss(conn, einst, tg, _KLM(VIER))
    text, leiste = tg.mit_knoepfen[-1]
    assert [b for b, _ in leiste] == [knoepfe.T._TEXT_BOARD_UEBERNEHMEN_KNOPF]
    assert _begriffe(conn) == "Hafen, Nacht"

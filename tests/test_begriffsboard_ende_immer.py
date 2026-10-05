"""Birk 05.10.2026 (Live-Test Gruppe 2): nach "Discussion done" laeuft das
Begriffsboard IMMER, sobald ueberhaupt Transkript vorliegt -- gemessen waren
8 Segmente mit zusammen 298 Zeichen, kein Boardlauf (Schwelle 600), und die
Gruppe bekam den alten Satz "Now send me your five terms". Zwischenlaeufe
behalten ihre Regel. Nur erfundenes Material."""

import threading
import time

import pytest

from interview_theater import aufnahme, begriffsboard, db, diskussion, einstellungen, repo, workshop

CHAT = 1
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "",
          "zitat": "", "doppelbedeutung": "", "status": "favorit", "vorheriger_begriff": ""}


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)
    monkeypatch.delenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", raising=False)   # Vorgabe 600


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
        self.gesendet, self.mit_knoepfen, self._id = [], [], 900

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid

    def beantworte_knopf(self, callback_query_id, text=""):
        pass

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _KLM:
    def __init__(self, *boards):
        self.boards, self.aufrufe, self.nutzer = list(boards), 0, []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        self.nutzer.append(nutzer)
        return {"board": self.boards.pop(0) if self.boards else []}


def _segment(conn, message_id, schnittgrund, text, *, status="fertig"):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund=schnittgrund)
    if text is not None:
        repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, status)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def _kurzer_abschluss(conn):
    """3 Segmente, zusammen 120 Zeichen, das letzte ist der Ende-Schnitt."""
    _segment(conn, 10, "pause", "Heimat ist fuer mich der Ort, an dem man bleibt. ")   # 49
    _segment(conn, 11, "pause", "Und Grenze, die man nicht sieht, aber spuert. ")      # 46
    return _segment(conn, 12, "ende", "Ja, Heimat und Grenze.")                       # 22 + 3


def test_kurzer_abschluss_laeuft(conn):
    _kurzer_abschluss(conn)
    assert repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"] < begriffsboard.min_zeichen()
    assert begriffsboard.soll_laufen(conn, CHAT) is True


def test_kurzer_abschluss_fuehrt_zum_vorschlag_statt_zum_alten_satz(conn, einst):
    ende = _kurzer_abschluss(conn)
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, ende, aufnahme._kein_zug, False)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert klm.aufrufe == 1
    assert "Heimat" in tg.mit_knoepfen[0][1]
    texte = [t for _c, t in tg.gesendet]
    assert aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE not in texte
    assert aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE not in texte


def test_null_zeichen_kein_lauf_und_neuer_rueckfalltext(conn, einst):
    _segment(conn, 10, "pause", "   ")
    ende = _segment(conn, 11, "ende", "")
    assert begriffsboard.soll_laufen(conn, CHAT) is False
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, ende, aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert klm.aufrufe == 0
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE)]


def test_modell_liefert_nichts_derselbe_rueckfalltext(conn, einst):
    ende = _kurzer_abschluss(conn)
    klm, tg = _KLM([]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, ende, aufnahme._kein_zug, False)
    _warte_bis(lambda: tg.gesendet)
    assert klm.aufrufe == 1
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE)]


def test_zwischenlauf_unter_schwelle_bleibt_false(conn):
    _segment(conn, 10, "pause", "Heimat ist fuer mich der Ort, an dem man bleibt. ")
    _segment(conn, 11, "pause", "Und Grenze, die man nicht sieht, aber spuert. ")
    assert begriffsboard.soll_laufen(conn, CHAT) is False


def test_ende_ohne_ungelesenes_laeuft_nicht_noch_einmal(conn):
    """Hat der letzte Lauf schon alles gelesen, gibt es nichts nachzuholen --
    der Vorschlag zeigt dann das Board, wie es ist."""
    a = _segment(conn, 10, "pause", "Heimat und Grenze.")
    b = _segment(conn, 11, "ende", "")
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", b["id"])
    assert a["id"] < b["id"]
    assert begriffsboard.soll_laufen(conn, CHAT) is False


def test_englischer_rueckfalltext_ohne_fuenf_begriffe(monkeypatch):
    from interview_theater import sprache

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        text = aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE
        assert text == (
            "I couldn't make out any terms from the discussion - tap \"Start listening\" "
            "and talk again, or type the terms here."
        )
        assert "five" not in text
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


# -- der Schlusslauf liest das KOMPLETTE Transkript --------------------------


def test_lauf_markiert_kein_noch_offenes_segment(conn, einst):
    """Ein Segment, das beim Laufstart noch transkribiert wird, darf nicht
    als gelesen markiert werden -- sonst fehlt es dem Schlusslauf."""
    a = _segment(conn, 10, "pause", "Heimat und Grenze und Mut. " * 30)
    _segment(conn, 11, "pause", None, status="empfangen")
    _segment(conn, 12, "pause", "Spaeter dazu.")
    klm = _KLM([HEIMAT])
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert repo.letztes_begriffsboard(conn, CHAT)["bis_aufnahme_id"] == a["id"]


def test_ende_wartet_auf_ein_noch_offenes_segment(conn, einst, monkeypatch):
    """Segmente werden im Pool parallel transkribiert: das kurze Ende-Segment
    kann vor dem vorigen fertig sein. Der Schluss (Lauf + Vorschlag) wartet,
    bis alle Segmente dieser Sitzung fertig sind."""
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    _segment(conn, 10, "pause", "Heimat ist fuer mich der Ort, an dem man bleibt.")
    offen = _segment(conn, 11, "pause", None, status="empfangen")
    ende = _segment(conn, 12, "ende", "Ja.")
    klm, tg = _KLM([HEIMAT]), _TG()
    t = threading.Thread(target=aufnahme._kurz_abschliessen,
                         args=(conn, tg, klm, einst, ende, aufnahme._kein_zug, False))
    t.start()
    time.sleep(0.2)
    assert klm.aufrufe == 0 and tg.gesendet == []      # wartet
    repo.setze_transkript(conn, offen["id"], "Und Grenze, die man nicht sieht.")
    repo.setze_status(conn, offen["id"], "transkribiert")
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, repo.hole_aufnahme(conn, offen["id"]),
                                aufnahme._kein_zug, False)
    t.join(5)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert any("Grenze, die man nicht sieht" in n for n in klm.nutzer)
    time.sleep(0.1)
    assert len(tg.mit_knoepfen) == 1


def test_ende_wartet_nicht_ewig(conn, einst, monkeypatch):
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_S", 0.1)
    _segment(conn, 10, "pause", "Heimat ist fuer mich der Ort, an dem man bleibt.")
    _segment(conn, 11, "pause", None, status="empfangen")
    ende = _segment(conn, 12, "ende", "Ja.")
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, ende, aufnahme._kein_zug, False)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    vorfaelle = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = ?", (CHAT,))]
    assert "diskussion_ende_segmente_offen" in vorfaelle


def test_offene_segmente_einer_frueheren_sitzung_halten_nicht_auf(conn, einst, monkeypatch):
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_S", 30)
    _segment(conn, 5, "pause", None, status="empfangen")      # alte Sitzung, haengt
    _segment(conn, 6, "ende", "Alt.")
    _segment(conn, 10, "pause", "Heimat ist fuer mich der Ort, an dem man bleibt.")
    ende = _segment(conn, 12, "ende", "Ja.")
    klm, tg = _KLM([HEIMAT]), _TG()
    start = time.monotonic()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, ende, aufnahme._kein_zug, False)
    assert time.monotonic() - start < 2
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)

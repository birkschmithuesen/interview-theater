"""Karte t_4517d4ad, Aufgabe 3: Sperre, Ausloeser und Boardlauf (D1, D2)."""

import inspect
import json
import threading
import time

import pytest

from interview_theater import begriffsboard, db, einstellungen, repo, workshop

CHAT = 1
TEXT = "Wir reden ueber Heimat und Grenze. Heimat ist, wo meine Oma kocht."


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)


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


def _segment(conn, message_id, text=TEXT, schnittgrund="pause"):
    aid = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, "fertig")
    return aid


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


class _KLM:
    def __init__(self, board=None, fehler=None, sperre=None):
        self.aufrufe = 0
        self.nutzer = []
        self.system = []
        self.arten = []
        self._board = board if board is not None else []
        self._fehler = fehler
        self._sperre = sperre

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        self.nutzer.append(nutzer)
        self.system.append(system)
        self.arten.append(art)
        if self._sperre is not None:
            self._sperre.wait(5)
        if self._fehler:
            raise self._fehler
        return {"board": self._board}


HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1, "begruendung": "Oma.",
          "zitat": "wo meine Oma kocht", "doppelbedeutung": "", "status": "favorit"}


# -- Schema -------------------------------------------------------------------

def test_schema_ist_streng():
    s = begriffsboard.SCHEMA
    assert s["additionalProperties"] is False and s["required"] == ["board"]
    zeile = s["properties"]["board"]["items"]
    assert zeile["additionalProperties"] is False
    assert set(zeile["required"]) == set(zeile["properties"]) == {
        "begriff", "nennungen", "zustimmung", "begruendung", "zitat", "doppelbedeutung", "status",
        "vorheriger_begriff",
    }


# -- Isolierter Nutzertext ---------------------------------------------------

def test_nutzertext_kennt_weder_conn_noch_chat_id():
    assert list(inspect.signature(begriffsboard._nutzertext).parameters) == ["transkript", "board"]


def test_nutzertext_traegt_transkript_und_board():
    text = begriffsboard._nutzertext("Hallo Heimat", [HEIMAT])
    assert "Hallo Heimat" in text
    assert '"Heimat"' in text


# -- Ausloeser (D1) -----------------------------------------------------------

def test_vorgabe_min_zeichen_ist_100_nicht_1200(monkeypatch):
    """Birk Live-Test 04.10.2026: eigene, niedrigere Schwelle als der
    Brainstorm (1200) -- ein Testgespraech in Phase 1 ist kuerzer als eine
    echte Brainstorm-Sitzung (-> 600). Birk Live-Test 05.10.2026: kurze
    Begriffsnennungen, 100 Zeichen."""
    monkeypatch.delenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", raising=False)
    assert begriffsboard.min_zeichen() == 100


def test_unter_der_zeichenschwelle_kein_lauf(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")
    _segment(conn, 10, "kurz")
    assert begriffsboard.soll_laufen(conn, CHAT) is False


def test_ueber_der_schwelle_nach_pause_laeuft(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    _segment(conn, 10)
    assert begriffsboard.soll_laufen(conn, CHAT) is True


def test_cap_schnitt_loest_in_phase1_aus(conn, monkeypatch):
    """Live Padua 05.10.2026: wer durchredet, erzeugt nur 90-s-Deckelschnitte;
    das Board darf daran nicht einfrieren."""
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    _segment(conn, 10, schnittgrund="cap")
    assert begriffsboard.soll_laufen(conn, CHAT) is True


def test_cap_schnitt_respektiert_mindestabstand(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ABSTAND_S", "3600")
    a = _segment(conn, 10)
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a)
    _segment(conn, 11, "x" * 200, schnittgrund="cap")
    assert begriffsboard.soll_laufen(conn, CHAT) is False


def test_brainstorm_cap_loest_weiter_nicht_aus():
    from interview_theater import brainstorm
    assert brainstorm.soll_reagieren(
        unreagierte_zeichen=10_000, sekunden_seit_letzter_reaktion=10_000,
        letzter_schnittgrund="cap", ist_abschluss=False) is False


def test_mindestabstand_nach_einem_lauf(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ABSTAND_S", "3600")
    a = _segment(conn, 10)
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a)
    _segment(conn, 11, "x" * 200)
    assert begriffsboard.soll_laufen(conn, CHAT) is False


def test_soll_laufen_ruft_brainstorm_soll_reagieren_unveraendert(conn, monkeypatch):
    gesehen = []
    monkeypatch.setattr(begriffsboard.brainstorm, "soll_reagieren",
                        lambda **kw: gesehen.append(kw) or True)
    _segment(conn, 10, "abc", schnittgrund="pause")
    assert begriffsboard.soll_laufen(conn, CHAT) is True
    assert gesehen == [{
        "unreagierte_zeichen": 3, "sekunden_seit_letzter_reaktion": float("inf"),
        "letzter_schnittgrund": "pause", "ist_abschluss": False,
        "min_zeichen_override": begriffsboard.min_zeichen(),
        "min_abstand_override": begriffsboard.min_abstand_s(),
    }]


# -- Lauf ---------------------------------------------------------------------

def test_lauf_speichert_das_validierte_board_mit_markierung(conn, einst):
    a = _segment(conn, 10)
    erfunden = dict(HEIMAT, begriff="Freiheit")
    klm = _KLM(board=[HEIMAT, erfunden])
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    zeile = repo.letztes_begriffsboard(conn, CHAT)
    assert [e["begriff"] for e in json.loads(zeile["json"])] == ["Heimat"]
    assert zeile["bis_aufnahme_id"] == a
    assert zeile["modell"] == "sovereign"
    assert klm.arten == ["begriffsboard"]
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def test_markierung_wird_vor_dem_lauf_gelesen(conn, einst):
    """Ein waehrend des Laufs eintreffendes Segment bleibt unreagiert."""
    a = _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe == 1)
    _segment(conn, 11, "spaeter dazu")
    halt.set()
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    assert repo.letztes_begriffsboard(conn, CHAT)["bis_aufnahme_id"] == a
    assert repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"] == len("spaeter dazu")
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def test_nur_ein_lauf_je_gruppe_gleichzeitig(conn, einst):
    _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    assert begriffsboard.starte(conn, klm, einst, CHAT) is False
    halt.set()
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert klm.aufrufe == 1


def test_gemerkter_rueckruf_laeuft_nach_dem_laufenden_lauf(conn, einst):
    _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe == 1)
    gerufen = []
    assert begriffsboard.starte(conn, klm, einst, CHAT, danach=lambda: gerufen.append(1)) is False
    assert gerufen == []
    halt.set()
    _warte_bis(lambda: gerufen == [1])


def test_gescheiterter_lauf_verliert_nichts(conn, einst):
    _segment(conn, 10)
    vorher = repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"]
    gerufen = []
    klm = _KLM(fehler=RuntimeError("weg"))
    begriffsboard.starte(conn, klm, einst, CHAT, danach=lambda: gerufen.append(1))
    _warte_bis(lambda: gerufen == [1])
    assert repo.letztes_begriffsboard(conn, CHAT) is None
    assert repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"] == vorher
    vorfaelle = conn.execute("SELECT art FROM vorfall WHERE chat_id = ?", (CHAT,)).fetchall()
    assert "begriffsboard_fehler" in [v["art"] for v in vorfaelle]
    assert not begriffsboard.laeuft(CHAT)


def test_leeres_ergebnis_ersetzt_kein_volles_board(conn, einst):
    a = _segment(conn, 10)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([HEIMAT]), "sovereign", a)
    _segment(conn, 11)
    begriffsboard.starte(conn, _KLM(board=[]), einst, CHAT)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert [e["begriff"] for e in begriffsboard.aktuelles(conn, CHAT)] == ["Heimat"]
    assert conn.execute("SELECT COUNT(*) FROM begriffsboard").fetchone()[0] == 1


def test_ohne_klm_oder_profil_kein_lauf(conn, einst, monkeypatch):
    _segment(conn, 10)
    assert begriffsboard.starte(conn, None, einst, CHAT) is False
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    assert begriffsboard.starte(conn, _KLM(board=[HEIMAT]), einst, CHAT) is False


def test_transkript_ueber_der_grenze_wird_vorn_gekuerzt(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN", "20")
    _segment(conn, 10, "ANFANG " + "x" * 50 + " Heimat ENDE")
    klm = _KLM(board=[])
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert "ANFANG" not in klm.nutzer[0] and "ENDE" in klm.nutzer[0]
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "begriffsboard_transkript_gekuerzt" in arten


def test_der_lauf_kennt_kein_tg():
    """D5 strukturell: weder ``starte`` noch ``_lauf_einmal`` bekommen ein
    Telegram-Objekt."""
    for fn in (begriffsboard.starte, begriffsboard._lauf_einmal):
        assert "tg" not in inspect.signature(fn).parameters

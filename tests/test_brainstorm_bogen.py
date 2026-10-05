"""Brainstorm der Phase 4 als Gedankenbogen (Karte t_cf87ee0a, Birk
03.10.2026): EIN Toggle = EIN Bogen. Waehrend der Toggle an ist, entsteht
keine Karte; erst das Bogenende (``schnittgrund='ende'``) wartet auf alle
Segmente des Bogens und entscheidet genau einmal -- Karte oder sichtbares
Schweigen. Fixtures aus ``tests/test_aufnahme.py`` kopiert, damit die Datei
allein laeuft."""

import threading
import time

import pytest

from interview_theater import aufnahme, brainstorm, db, einstellungen, repo


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
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class TelegramAttrappe:
    """Kein Netzzugriff, zeichnet auf (Kopie aus ``tests/test_aufnahme.py``)."""

    def __init__(self):
        self.gesendet = []
        self._letzte_message_id = 9000

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._letzte_message_id += 1
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _brainstorm_zeile(conn, chat_id, message_id, transkript, schnittgrund="pause"):
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
        schnittgrund=schnittgrund, brainstorm=True,
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.merke_nachricht(
        conn, chat_id, message_id, "Gruppe", 0, "sprache", None,
        "2026-10-02T10:00:00", 1,
    )
    return repo.hole_aufnahme(conn, aufnahme_id)


def test_ende_wartet_auf_offene_segmente_des_bogens(conn, tg, einst, monkeypatch):
    """Reihenfolge sichern: die Karte laeuft erst, wenn das letzte
    Zwischensegment (cap) transkribiert ist -- heute Race zwischen Upload/STT
    und _starte_buehnenkarte."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    gesehen = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda c, t, k, e, chat_id: gesehen.append(
            repo.brainstorm_stand(c, chat_id)["unreagierte_zeichen"]))
    offen = repo.lege_aufnahme_an(conn, 1, 600, "kurz", "sprache", status="empfangen",
                                  brainstorm=True, schnittgrund="cap")
    ende = _brainstorm_zeile(conn, 1, 601, "x" * 20, schnittgrund="ende")

    def spaeter():
        time.sleep(0.2)
        repo.setze_transkript(conn, offen, "y" * 30)
        repo.setze_status(conn, offen, "fertig")

    threading.Thread(target=spaeter).start()
    aufnahme._kurz_abschliessen(conn, tg, None, einst, ende, aufnahme._kein_zug, False)
    assert gesehen == [50]


def test_ende_unter_der_schwelle_ist_sichtbares_schweigen(conn, tg, einst):
    """Nach dem Stopp kommt GENAU eine Reaktion: Karte oder 'nothing to add'
    (cothinker_status.ZUSTAND_SCHWEIGT) -- auch wenn der Bogen kurz war."""
    row = _brainstorm_zeile(conn, 1, 610, "zu kurz", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    karten = repo.buehnenkarten(conn, 1)
    assert len(karten) == 1 and karten[0]["schweigen"] == 1 and karten[0]["text"] == ""


def test_cap_schnitt_loest_nie_eine_karte_aus(conn, tg, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    aufgerufen = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: aufgerufen.append(1))
    row = _brainstorm_zeile(conn, 1, 620, "x" * 5000, schnittgrund="cap")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert not aufgerufen and repo.buehnenkarten(conn, 1) == []


def test_offene_brainstorm_segmente_zaehlt_nur_diese_sitzung(conn):
    alt = repo.lege_aufnahme_an(conn, 1, 700, "kurz", "sprache", status="empfangen",
                                brainstorm=True, schnittgrund="cap")
    repo.lege_aufnahme_an(conn, 1, 701, "kurz", "sprache", status="fertig",
                          brainstorm=True, schnittgrund="ende")
    offen = repo.lege_aufnahme_an(conn, 1, 702, "kurz", "sprache", status="empfangen",
                                  brainstorm=True, schnittgrund="cap")
    ende = repo.lege_aufnahme_an(conn, 1, 703, "kurz", "sprache", status="fertig",
                                 brainstorm=True, schnittgrund="ende")
    assert repo.offene_brainstorm_segmente(conn, 1, ende) == 1
    assert alt < offen


def test_ende_wartet_auf_laufende_karte_des_vorigen_bogens(conn, tg, einst, monkeypatch):
    """Genau eine Reaktion je Bogen: laeuft beim Stopp noch die Karte des
    VORIGEN Bogens (``brainstorm.versuche_start`` waere belegt), darf dieser
    Bogen nicht still leer ausgehen -- das Ende wartet, bis der Lauf frei ist,
    und entscheidet dann."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    beim_start_belegt = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda c, t, k, e, chat_id: beim_start_belegt.append(brainstorm.laeuft(chat_id)))
    assert brainstorm.versuche_start(1)
    try:
        threading.Timer(0.2, brainstorm.beende, args=(1,)).start()
        row = _brainstorm_zeile(conn, 1, 630, "x" * 20, schnittgrund="ende")
        aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    finally:
        brainstorm.beende(1)
    assert beim_start_belegt == [False]

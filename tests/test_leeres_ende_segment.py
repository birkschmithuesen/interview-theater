"""Birk, Live-Test 05.10.2026 (Gruppe 2, Aufnahmen 30-36): das Segment mit
``schnittgrund='ende'`` ("Discussion done") war LEER -- nur Stille nach dem
Druck. ``aufnahme._melde_transkriptionsfehler`` verwarf es still, und weil
nur ein fertig transkribiertes Segment je ``_diskussion_abschliessen``
erreicht, gab es keinen Schlusslauf, keine Verdichtung, keinen Vorschlag:
der Bot schwieg. Seitdem loest auch ein leeres (oder endgueltig
gescheitertes) Ende-Segment den kompletten Abschluss aus; nur das Segment
selbst wird verworfen. Dasselbe fuer den Brainstorm der Phase 4."""

import time

import pytest

from interview_theater import (aufnahme, begriffsboard, brainstorm, db, diskussion,
                               einstellungen, kosten, repo, stt, workshop)

CHAT = 1
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "",
          "zitat": "", "doppelbedeutung": "", "status": "favorit", "vorheriger_begriff": ""}


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(kosten, "deckel_erreicht", lambda *a, **k: False)


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
        self.gesendet.append(text)
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.mit_knoepfen.append((text, list(knoepfe_)))
        return self.sende(chat_id, text)

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def aendere_text(self, *a, **k):
        pass

    def tippt(self, chat_id):
        pass


class _KLM:
    def __init__(self, *boards):
        self.boards, self.nutzer = list(boards), []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.nutzer.append(nutzer)
        return {"board": self.boards.pop(0) if self.boards else []}


def _fertig(conn, message_id, text, *, diskussion=True, brainstorm=False):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=diskussion, brainstorm=brainstorm,
                                schnittgrund="pause")
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, "fertig")
    return aid


def _leeres_ende(conn, tmp_path, message_id, *, diskussion=True, brainstorm=False):
    datei = tmp_path / f"{message_id}.webm"
    datei.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 50)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache",
                                 audio_pfad=str(datei), dauer=2, schnittgrund="ende",
                                 diskussion=diskussion, brainstorm=brainstorm)


def _stille(*_a, **_k):
    raise stt.LeeresTranskript("leeres Transkript")


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_leeres_ende_segment_loest_den_abschluss_aus(conn, einst, tmp_path, monkeypatch):
    verdichtet = []
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: verdichtet.append(1))
    monkeypatch.setattr(stt, "transkribiere", _stille)
    _fertig(conn, 30, "Heimat ist der Ort, an dem man bleibt.")
    _fertig(conn, 31, "Es ist alles so furchtbar kompliziert.")
    aid = _leeres_ende(conn, tmp_path, 36)
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme.verarbeite(conn, tg, klm, einst, None, aid)
    _warte_bis(lambda: tg.gesendet)
    assert repo.hole_aufnahme(conn, aid)["status"] == "fehlgeschlagen"   # das Segment selbst: verworfen
    assert len(klm.nutzer) == 1
    assert "Heimat ist der Ort" in klm.nutzer[0]
    assert "furchtbar kompliziert" in klm.nutzer[0]
    assert verdichtet == [1]
    assert any("Heimat" in t for t in tg.gesendet)


def test_leeres_ende_ohne_jedes_transkript_bekommt_den_rueckfalltext(conn, einst, tmp_path,
                                                                     monkeypatch):
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)
    monkeypatch.setattr(stt, "transkribiere", _stille)
    aid = _leeres_ende(conn, tmp_path, 36)
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme.verarbeite(conn, tg, klm, einst, None, aid)
    assert klm.nutzer == []
    assert tg.gesendet == [aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE]


def test_leeres_zwischensegment_bleibt_still(conn, einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt, "transkribiere", _stille)
    datei = tmp_path / "x.webm"
    datei.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 50)
    aid = repo.lege_aufnahme_an(conn, CHAT, 40, "kurz", "sprache", audio_pfad=str(datei),
                                dauer=2, schnittgrund="pause", diskussion=True)
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme.verarbeite(conn, tg, klm, einst, None, aid)
    assert tg.gesendet == [] and klm.nutzer == []


def test_leeres_ende_im_brainstorm_loest_die_abschlusskarte_aus(conn, einst, tmp_path,
                                                                monkeypatch):
    gestartet = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte",
                        lambda *a, **k: gestartet.append(1))
    monkeypatch.setattr(stt, "transkribiere", _stille)
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    _fertig(conn, 50, "Eine Werkstatt am Hafen, nachts, mit einem Radio.",
            diskussion=False, brainstorm=True)
    aid = _leeres_ende(conn, tmp_path, 51, diskussion=False, brainstorm=True)
    aufnahme.verarbeite(conn, _TG(), _KLM(), einst, None, aid)
    assert gestartet == [1]


# Robo, Simulations-Kontrolllauf 05.10.2026 14:26 gegen 4bf7f5c: das Ende-
# Segment war 110 Bytes / 1 s (nur der WebM-Kopf), Whisper meldete den Auftrag
# als 'failed', und der Nachhol-Arbeiter versuchte es MAX_VERSUCHE-mal im
# 60-s-Takt -- rund fuenf Minuten Stille, bevor der Abschluss lief.

def _ende_mit_bytes(conn, tmp_path, message_id, groesse, *, schnittgrund="ende"):
    datei = tmp_path / f"{message_id}.webm"
    datei.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * (groesse - 4))
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache",
                                 audio_pfad=str(datei), dauer=1, schnittgrund=schnittgrund,
                                 diskussion=True)


def test_winziges_ende_segment_geht_nicht_an_whisper(conn, einst, tmp_path, monkeypatch):
    aufrufe, verdichtet = [], []
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: aufrufe.append(1) or "x")
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: verdichtet.append(1))
    aid = _ende_mit_bytes(conn, tmp_path, 60, 110)
    klm, tg = _KLM(), _TG()
    aufnahme.verarbeite(conn, tg, klm, einst, None, aid)
    assert aufrufe == []
    assert repo.hole_aufnahme(conn, aid)["status"] == "fehlgeschlagen"
    assert tg.gesendet == [aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE]
    assert verdichtet == [1]


def _abgebrochen(*_a, **_k):
    raise stt.AuftragAbgebrochen("Auftrag b1 endete als 'failed'")


def test_ende_segment_mit_failed_schliesst_nach_dem_ersten_anlauf(conn, einst, tmp_path,
                                                                  monkeypatch):
    verdichtet = []
    monkeypatch.setattr(stt, "transkribiere", _abgebrochen)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: verdichtet.append(1))
    aid = _ende_mit_bytes(conn, tmp_path, 61, 5000)
    klm, tg = _KLM(), _TG()
    aufnahme.verarbeite(conn, tg, klm, einst, None, aid)
    row = repo.hole_aufnahme(conn, aid)
    assert row["status"] == "fehlgeschlagen"
    assert tg.gesendet == [aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE]
    assert verdichtet == [1]


def test_ende_segment_mit_netzfehler_wird_weiter_versucht(conn, einst, tmp_path, monkeypatch):
    def _netz(*_a, **_k):
        raise stt.STTFehler("Whisper-Upload nicht erreichbar (zuletzt: HTTPStatusError)")

    verdichtet = []
    monkeypatch.setattr(stt, "transkribiere", _netz)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: verdichtet.append(1))
    aid = _ende_mit_bytes(conn, tmp_path, 62, 5000)
    aufnahme.verarbeite(conn, _TG(), _KLM(), einst, None, aid)
    row = repo.hole_aufnahme(conn, aid)
    assert row["status"] == "empfangen" and row["versuche"] == 1
    assert verdichtet == []


def test_winziges_zwischensegment_geht_weiter_an_whisper(conn, einst, tmp_path, monkeypatch):
    aufrufe = []

    def _zaehle(*_a, **_k):
        aufrufe.append(1)
        raise stt.AuftragAbgebrochen("Auftrag b1 endete als 'failed'")

    monkeypatch.setattr(stt, "transkribiere", _zaehle)
    aid = _ende_mit_bytes(conn, tmp_path, 63, 110, schnittgrund="pause")
    aufnahme.verarbeite(conn, _TG(), _KLM(), einst, None, aid)
    row = repo.hole_aufnahme(conn, aid)
    assert aufrufe == [1]
    assert row["status"] == "empfangen" and row["versuche"] == 1

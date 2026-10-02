"""Whisper bucht in `aufruf` -- vorher tat es das gar nicht.

Gemessen am 30.09.2026: `grep -c merke_aufruf interview_theater/stt.py` -> 0.
Eine Kostengrenze, die die Transkription nicht sieht, waere keine: ein
Workshoptag mit fuenf Interviews a 20 Minuten sind 100 Minuten Audio.

Gebucht wird in aufnahme._transkribiere_mit_meldung und nicht in stt.py:
stt bekommt weder conn noch chat_id (stt.py:223) und soll sie auch nicht
bekommen.

Abweichung vom Brief: ``repo.setze_aufnahme_dauer`` gibt es im Code nicht --
``repo.lege_aufnahme_an`` nimmt die Dauer schon als Parameter ``dauer``
entgegen, die Fixture setzt sie deshalb direkt beim Anlegen.
"""

import pytest

from interview_theater import aufnahme, db, kosten, repo, stt

CHAT = 1


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def tippt(self, chat_id):
        pass


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, 11, "kurz", str(datei), audio_pfad=str(datei), dauer=120,
    )
    conn.commit()
    yield conn, aufnahme_id
    conn.close()


def _zeilen(conn):
    return conn.execute(
        "SELECT * FROM aufruf WHERE chat_id = ? AND art = 'stt'", (CHAT,)
    ).fetchall()


def test_eine_gelungene_transkription_bucht_nach_dauer(aufbau, monkeypatch):
    conn, aufnahme_id = aufbau
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "Hier steht Text.")
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["erfolg"] == 1
    assert zeilen[0]["kosten_chf"] == pytest.approx(kosten.stt_kosten_chf(120))
    assert zeilen[0]["modell"]


def test_eine_gescheiterte_transkription_bucht_trotzdem(aufbau, monkeypatch):
    """Ein Auftrag, der ins Zeitbudget laeuft, wurde abgesendet und ist
    bezahlt -- dieselbe Regel wie das finally in llm._anfrage."""
    conn, aufnahme_id = aufbau

    def kaputt(*a, **k):
        raise stt.STTFehler("Zeitbudget ausgeschoepft")

    monkeypatch.setattr(stt, "transkribiere", kaputt)
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["erfolg"] == 0
    assert zeilen[0]["kosten_chf"] == pytest.approx(kosten.stt_kosten_chf(120))


def test_ohne_dauer_wird_null_gebucht_und_nichts_geraten(aufbau, monkeypatch):
    conn, aufnahme_id = aufbau
    conn.execute("UPDATE aufnahme SET dauer_sekunden = NULL WHERE id = ?", (aufnahme_id,))
    conn.commit()
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "Text.")
    row = repo.hole_aufnahme(conn, aufnahme_id)

    class E:
        bot_name = "gruppe1"

    aufnahme._transkribiere_mit_meldung(conn, TelegramAttrappe(), E(), None, row)
    assert _zeilen(conn)[0]["kosten_chf"] == pytest.approx(0.0)


def test_hundert_minuten_audio_bleiben_unter_dem_deckel():
    """Ein Workshoptag mit fuenf Interviews a 20 Minuten. Die Zahl steht
    hier, damit der Anteil von Whisper am Deckel sichtbar ist -- er ist
    klein, und das ist eine Aussage, keine Selbstverstaendlichkeit."""
    assert kosten.stt_kosten_chf(100 * 60) == pytest.approx(0.6)


def test_stt_py_bucht_weiterhin_nicht_selbst():
    """stt.py bekommt weder conn noch chat_id und soll sie nicht bekommen --
    die Kopplung gehoert in die Fachlogik."""
    from pathlib import Path

    quelle = Path(stt.__file__).read_text(encoding="utf-8")
    assert "merke_aufruf" not in quelle
    assert "import repo" not in quelle

"""Eine Web-Gruppe anlegen -- ohne Telegram, ohne Modell, ohne Netz.

Der Web-Bot-Prozess bedient genau EINE Gruppe, und ihre chat_id ist
synthetisch (repo.WEB_CHAT_ID_BASIS). Sie muss also jemand anlegen: der
Webserver kann es nicht, er liest read-only.
"""

import pytest

from interview_theater import db, repo
from scripts import web_gruppe


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    return verbindung


def test_lege_an_erzeugt_gruppe_token_und_kanal(conn):
    daten = web_gruppe.lege_an(
        conn, "gruppe1", "Die Ankommenden", "https://lab.example/theatersoap"
    )
    assert daten["chat_id"] >= repo.WEB_CHAT_ID_BASIS
    gruppe = repo.hole_gruppe(conn, daten["chat_id"])
    assert gruppe["bot_name"] == "gruppe1"
    assert gruppe["titel"] == "Die Ankommenden"
    assert gruppe["kanal"] == "web"
    assert gruppe["web_token"] == daten["token"]
    assert daten["url"] == f"https://lab.example/theatersoap/g/{daten['token']}/chat"


def test_zwei_gruppen_bekommen_verschiedene_ids(conn):
    erste = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    zweite = web_gruppe.lege_an(conn, "gruppe2", "B", "")
    assert zweite["chat_id"] == erste["chat_id"] + 1
    assert zweite["token"] != erste["token"]


def test_ohne_basis_url_gibt_es_keinen_link(conn):
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    assert daten["url"] is None


def test_die_env_zeilen_nennen_kanal_und_chat_id(conn):
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "")
    assert "IT_KANAL=web" in daten["env"]
    assert f"IT_WEB_CHAT_ID={daten['chat_id']}" in daten["env"]


def test_der_bericht_nennt_keinen_bot_token(conn):
    """Das Skript liest keine Env-Datei einer Gruppe und gibt nichts aus, was
    ein Geheimnis eines anderen Dienstes ist. Der Web-Token IST das Geheimnis
    des Links -- er steht bewusst da, das ist der Zweck."""
    daten = web_gruppe.lege_an(conn, "gruppe1", "A", "https://lab.example/theatersoap")
    text = web_gruppe.bericht(daten)
    assert "IT_BOT_TOKEN" not in text
    assert daten["token"] in text
    assert "IT_KANAL=web" in text


def test_das_skript_liest_niemals_betrieb(tmp_path):
    """Keine Zeile darf 'betrieb/' oeffnen: dort liegen echte Zugangsdaten,
    und ein Skript, das sie einmal liest, gibt sie irgendwann aus."""
    from pathlib import Path

    quelle = Path(web_gruppe.__file__).read_text(encoding="utf-8")
    assert "betrieb" not in quelle


def test_main_ohne_it_db_bricht_ab(monkeypatch, capsys):
    monkeypatch.delenv("IT_DB", raising=False)
    assert web_gruppe.main(["anlegen", "gruppe1"]) == 1
    assert "IT_DB" in capsys.readouterr().err


def test_main_legt_an_und_druckt(monkeypatch, tmp_path, capsys):
    pfad = str(tmp_path / "t.db")
    vorbereitung = db.verbinde(pfad)
    db.initialisiere(vorbereitung)
    vorbereitung.close()
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://lab.example/theatersoap")

    assert web_gruppe.main(["anlegen", "gruppe1", "--titel", "Die Ankommenden"]) == 0
    ausgabe = capsys.readouterr().out
    assert "IT_KANAL=web" in ausgabe
    assert "/chat" in ausgabe

    nachher = db.verbinde(pfad)
    assert repo.hole_gruppe(nachher, repo.WEB_CHAT_ID_BASIS)["kanal"] == "web"


def test_main_kennt_nur_anlegen(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("IT_DB", str(tmp_path / "t.db"))
    with pytest.raises(SystemExit) as beendet:
        web_gruppe.main(["loeschen", "gruppe1"])
    assert beendet.value.code == 2
    assert "anlegen" in capsys.readouterr().err

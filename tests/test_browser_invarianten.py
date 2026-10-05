"""Tests fuer simulation.browser_invarianten (Karte t_fc2c1bfa, 05.10.2026).

Fixture-Schema an das reale Schema angeglichen (Step 1, Schema an cb200e4
UND HEAD geprueft -- identisch an beiden Staenden):

- ``aufnahme``: Spalten ``transkript`` (nicht ``text``), ``status``
  (``laeuft|empfangen|transkribiert|fertig|fehlgeschlagen``), ``diskussion``,
  ``schnittgrund`` -- wie im Brief vorgezeichnet.
- Bot-Blasen im Browser kommen aus ``web_post`` (``richtung = 'aus'``,
  ``geloescht_am IS NULL``), NICHT aus ``nachricht``: ``web_kanal.WebKanal.sende``
  schreibt ausschliesslich nach ``web_post`` (``repo.lege_web_post_an``); die
  Mitschrift in ``nachricht`` ist fuer das Gespraechsmodell/Erkenner-Fenster
  und bleibt bei Hintergrund-Boardlaeufen/Vorschlaegen unberuehrt. Deshalb
  liest ``lese_p1_stand`` die Bot-IDs aus ``web_post`` statt aus ``nachricht``.
"""

import json
import sqlite3

import pytest

from simulation import browser_invarianten as inv


@pytest.fixture
def db(tmp_path):
    pfad = tmp_path / "sim.db"
    conn = sqlite3.connect(pfad)
    conn.executescript(
        """
        CREATE TABLE begriffsboard (id INTEGER PRIMARY KEY, chat_id INTEGER, json TEXT);
        CREATE TABLE aufnahme (id INTEGER PRIMARY KEY, chat_id INTEGER, diskussion INTEGER,
                               schnittgrund TEXT, transkript TEXT, status TEXT);
        CREATE TABLE arbeitsstand (chat_id INTEGER PRIMARY KEY, begriffe TEXT);
        CREATE TABLE web_post (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER,
                               richtung TEXT, typ TEXT, text TEXT, geloescht_am TEXT);
        """
    )
    conn.commit()
    conn.close()
    return pfad


def _schreibe(pfad, sql, *werte):
    conn = sqlite3.connect(pfad)
    conn.execute(sql, werte)
    conn.commit()
    conn.close()


def _bot_post(pfad, chat_id, text, post_id=None):
    _schreibe(
        pfad,
        "INSERT INTO web_post (id, chat_id, richtung, typ, text) VALUES (?, ?, 'aus', 'text', ?)",
        post_id, chat_id, text,
    )


def _stand(pfad, chat_id=7):
    with inv.oeffne_lesend(pfad) as conn:
        return inv.lese_p1_stand(conn, chat_id)


def test_board_json_ohne_verworfene():
    roh = json.dumps([
        {"begriff": "home", "status": "favorit"},
        {"begriff": "noise", "status": "verworfen"},
        {"begriff": "border", "status": "kandidat"},
    ])
    assert inv.board_begriffe_aus_json(roh) == ("home", "border")
    assert inv.board_begriffe_aus_json(json.dumps({"begriffe": [{"begriff": "x"}]})) == ("x",)
    assert inv.board_begriffe_aus_json(None) == ()
    assert inv.board_begriffe_aus_json("kaputt") == ()


def test_knappe_diskussion_ohne_board_ist_befund_board_leer(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because we miss it', 'fertig')")
    nachher = _stand(db)
    befunde = inv.pruefe_nach_diskussion(vorher, nachher, "p1-zuhoeren")
    schluessel = {b.schluessel for b in befunde}
    assert inv.BOARD_LEER in schluessel
    assert inv.WERKBANK_LEER in schluessel
    assert inv.STILLE_NACH_ENDE in schluessel
    assert all(b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT for b in befunde)
    board = next(b for b in befunde if b.schluessel == inv.BOARD_LEER)
    assert "23 Zeichen" in board.text  # Zeichenzahl des Transkripts steht im Text


def test_leeres_ende_segment_ohne_bot_nachricht(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because', 'fertig')")
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'ende', '', 'fertig')")
    nachher = _stand(db)
    assert nachher.ende_leer is True
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert inv.STILLE_LEERES_ENDE in schluessel
    assert inv.STILLE_NACH_ENDE not in schluessel


def test_nicht_fertiges_ende_segment_zaehlt_nicht_als_leer(db):
    # Noch nicht transkribiert (status != 'fertig') -- kein falscher Befund
    # durch eine Rennlage zwischen Ende-Schnitt und fertiger Transkription.
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because', 'fertig')")
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'ende', '', 'transkribiert')")
    nachher = _stand(db)
    assert nachher.ende_leer is False


def test_gesunder_abschluss_ohne_befund(db):
    _bot_post(db, 7, "welcome", post_id=1)
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'home because we miss it', 'fertig')")
    _schreibe(db, "INSERT INTO begriffsboard VALUES (1, 7, ?)", json.dumps([{"begriff": "home", "status": "kandidat"}]))
    _schreibe(db, "INSERT INTO arbeitsstand VALUES (7, 'home')")
    _bot_post(db, 7, "These are your five terms", post_id=2)
    nachher = _stand(db)
    assert inv.pruefe_nach_diskussion(vorher, nachher, "s") == []


def test_bot_nachricht_vor_dem_ende_zaehlt_nicht(db):
    _bot_post(db, 7, "old", post_id=1)
    vorher = _stand(db)
    nachher = _stand(db)
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}


def test_andere_gruppe_zaehlt_nicht(db):
    vorher = _stand(db)
    _bot_post(db, 8, "other group", post_id=1)
    _schreibe(db, "INSERT INTO arbeitsstand VALUES (8, 'home')")
    nachher = _stand(db)
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert {inv.STILLE_NACH_ENDE, inv.WERKBANK_LEER} <= schluessel


def test_geloeschte_bot_nachricht_zaehlt_nicht(db):
    vorher = _stand(db)
    _schreibe(
        db,
        "INSERT INTO web_post (id, chat_id, richtung, typ, text, geloescht_am) "
        "VALUES (1, 7, 'aus', 'text', 'removed', '2026-10-05T00:00:00')",
    )
    nachher = _stand(db)
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}


def test_warten_bricht_ab_sobald_alles_gut(db):
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'home', 'fertig')")
    zeit = [0.0]
    aufrufe = []

    def schlafe(s):
        aufrufe.append(s)
        zeit[0] += s
        _schreibe(db, "INSERT INTO begriffsboard VALUES (NULL, 7, ?)", json.dumps([{"begriff": "home"}]))
        _schreibe(db, "INSERT OR REPLACE INTO arbeitsstand VALUES (7, 'home')")
        _bot_post(db, 7, "saved")

    befunde, stand = inv.warte_nach_diskussion(db, 7, vorher, "s", schlafe=schlafe, uhr=lambda: zeit[0])
    assert befunde == []
    assert len(aufrufe) == 1
    assert stand.board_begriffe == ("home",)


def test_warten_meldet_nach_frist(db):
    vorher = _stand(db)
    zeit = [0.0]

    def schlafe(s):
        zeit[0] += s

    befunde, _ = inv.warte_nach_diskussion(db, 7, vorher, "s", frist_s=6, takt_s=2, schlafe=schlafe, uhr=lambda: zeit[0])
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in befunde}
    assert zeit[0] >= 6


def test_symptomregel_station_nicht_erreicht():
    (b,) = inv.pruefe_station_erreicht("p1-begriffe", False)
    assert b.schluessel == "station_nicht_erreicht:p1-begriffe"
    assert b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT
    assert inv.pruefe_station_erreicht("p1-begriffe", True) == []


def test_symptomregel_beobachter_sah_nie_einen_begriff():
    assert inv.pruefe_beobachter([0, 0, 0], "p1-zuhoeren")[0].schluessel == inv.BOARD_BEOBACHTER_LEER
    assert inv.pruefe_beobachter([], "p1-zuhoeren")[0].schluessel == inv.BOARD_BEOBACHTER_LEER
    assert inv.pruefe_beobachter([0, 3], "p1-zuhoeren") == []


def test_raumcheck_ohne_gruppenschluessel_ist_domainweit():
    alt = ["vad_boden_mess", "vad_rede_mess", "vad_schwelle", "theme"]
    (b,) = inv.pruefe_raumcheck_schluessel(alt, "tok123", "p1-kalibrierung")
    assert b.schluessel == inv.RAUMCHECK_DOMAINWEIT
    assert "vad_schwelle" in b.text
    neu = ["vad_schwelle:tok123:2026-10-05", "vad_boden_mess:tok123:2026-10-05"]
    assert inv.pruefe_raumcheck_schluessel(neu, "tok123", "s") == []


def test_raumcheck_schluessel_einer_anderen_gruppe_ist_gebunden():
    """Seite von Gruppe 2, Messung von Gruppe 1 korrekt gebunden: kein Befund,
    sobald alle Tokens des Laufs bekannt sind -- ein ungebundener bleibt einer."""
    schluessel = ["vad_schwelle:tok1:2026-10-05", "vad_boden_mess:tok1:2026-10-05"]
    assert inv.pruefe_raumcheck_schluessel(schluessel, "tok2", "s",
                                           alle_tokens=("tok1", "tok2")) == []
    (b,) = inv.pruefe_raumcheck_schluessel(schluessel + ["vad_schwelle"], "tok2", "s",
                                           alle_tokens=("tok1", "tok2"))
    assert "vad_schwelle." in b.text and "tok1" not in b.text


def test_raumcheck_ohne_messung_meldet_nichts():
    assert inv.pruefe_raumcheck_schluessel(["theme"], "tok", "s") == []


def test_verhoerer_nicht_korrigiert():
    (b,) = inv.pruefe_verhoerer(("Night shed", "home"), {"night shed": "night shift"}, "s")
    assert b.schluessel == inv.VERHOERER
    assert b.schwere == "mittel"
    assert inv.pruefe_verhoerer(("night shift",), {"night shed": "night shift"}, "s") == []
    assert inv.pruefe_verhoerer((), {"night shed": "night shift"}, "s") == []


def test_p2_werkbank():
    assert inv.zaehle_fragen("1. Why?\n2. How?\n\n") == 2
    assert inv.zaehle_fragen(None) == 0
    assert inv.zaehle_fragen(json.dumps(["Why?", "How?", "When?"])) == 3
    assert inv.pruefe_p2_werkbank("", None, "s")[0].schluessel == inv.P2_FRAGEN_FEHLEN
    assert inv.pruefe_p2_werkbank("1. Why?\n2. How?", 3, "s")[0].schluessel == inv.P2_ZAEHLER
    assert inv.pruefe_p2_werkbank("1. Why?\n2. How?", 2, "s") == []
    assert inv.pruefe_p2_werkbank("1. Why?", None, "s") == []


def test_kontext_kennt_alles():
    prompt = "Board: home, border\nThe group said: we miss home because of the border\nWorkbench terms: home"
    s = inv.Sichtbar(board=("home", "border"), transkripte=("We miss home because of the border.",), werkbank=("home",))
    assert inv.pruefe_kontext(prompt, s, "p1-wissen") == []


def test_kontext_ohne_board_und_transkript():
    prompt = "You are a helpful workshop bot. [voice message]"
    s = inv.Sichtbar(board=("home", "border"), transkripte=("We miss home because of the border.", "Noise at night"))
    schluessel = {b.schluessel for b in inv.pruefe_kontext(prompt, s, "p1-wissen")}
    assert schluessel == {inv.CHAT_KENNT_BOARD_NICHT, inv.CHAT_KENNT_TRANSKRIPT_NICHT}


def test_kontext_ohne_werkbank():
    s = inv.Sichtbar(werkbank=("home", "night shift"))
    (b,) = inv.pruefe_kontext("terms: home", s, "p2")
    assert b.schluessel == inv.CHAT_KENNT_WERKBANK_NICHT
    assert "night shift" in b.text
    assert b.ursache == inv.URSACHE_UNGEKLAERT


def test_kontext_transkript_mehrheit_reicht_und_normalisiert():
    prompt = "we  MISS home because of the border"
    s = inv.Sichtbar(transkripte=("We miss home because of the border.", "Noise at night keeps us awake"))
    assert inv.pruefe_kontext(prompt, s, "s") == []  # 1 von 2 = Haelfte reicht
    s3 = inv.Sichtbar(transkripte=("We miss home because of the border.", "Noise at night", "Waiting rooms"))
    assert inv.pruefe_kontext(prompt, s3, "s")[0].schluessel == inv.CHAT_KENNT_TRANSKRIPT_NICHT


def test_kontext_leer_sichtbar_kein_befund():
    assert inv.pruefe_kontext("", inv.Sichtbar(), "s") == []


def test_wissensantwort():
    board = ("home", "border", "noise", "night shift")
    assert inv.pruefe_wissensantwort("On the CoThinker: home, border and noise.", board, "s") == []
    (b,) = inv.pruefe_wissensantwort("I can't see the cothinker page from here.", board, "s")
    assert b.schluessel == inv.CHAT_NENNT_BOARD_NICHT
    assert inv.pruefe_wissensantwort("home", ("home",), "s") == []
    assert inv.pruefe_wissensantwort("anything", (), "s") == []
    assert inv.WISSENSFRAGE == "Which terms are on the CoThinker right now?"

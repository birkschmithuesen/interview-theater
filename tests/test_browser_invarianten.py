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
from datetime import datetime, timezone

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


def test_verworfenes_leeres_ende_segment_ist_leer(db):
    """Abnahmelauf cb200e4 (05.10.2026, Aufnahme 7): das leere Ende-Segment
    endet als ``fehlgeschlagen`` ("leeres Transkript -- Stille ist kein
    gueltiges Ergebnis") -- genau Birks Live-Fall. Es ist ein leeres Ende,
    kein fehlendes; nur noch laufende Status bleiben aussen vor."""
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home because', 'fertig')")
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'ende', NULL, 'fehlgeschlagen')")
    nachher = _stand(db)
    assert nachher.ende_leer is True
    assert nachher.transkript_zeichen == len("home because")
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert inv.STILLE_LEERES_ENDE in schluessel
    assert inv.STILLE_NACH_ENDE not in schluessel


def test_leeres_ende_einer_frueheren_diskussion_zaehlt_nicht(db):
    """Das leere Ende-Segment der VORIGEN Diskussion (Aufnahme 1) darf die
    jetzige nicht als "leeres Ende" melden -- nur Zeilen hinter
    ``vorher.max_aufnahme_id`` zaehlen."""
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', NULL, 'fehlgeschlagen')")
    vorher = _stand(db)
    assert vorher.max_aufnahme_id == 1
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'pause', 'home because', 'fertig')")
    nachher = _stand(db)
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert inv.STILLE_LEERES_ENDE not in schluessel
    assert inv.STILLE_NACH_ENDE in schluessel


def test_ende_nicht_angekommen(db):
    """Abnahmelauf 05.10.2026: ohne aktiven VAD schickt ``beendeDiskussion``
    kein 'ende' -- nach der Wartezeit gibt es keine neue Ende-Zeile."""
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'old', 'fertig')")
    vorher = _stand(db)
    _schreibe(db, "INSERT INTO aufnahme VALUES (2, 7, 1, 'zeit', 'home because', 'fertig')")
    befunde = inv.pruefe_nach_diskussion(vorher, _stand(db), "p1-zuhoeren")
    (b,) = [b for b in befunde if b.schluessel == inv.ENDE_NICHT_ANGEKOMMEN]
    assert b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT
    # Eine noch laufende Ende-Zeile ist angekommen (Transkription folgt).
    _schreibe(db, "INSERT INTO aufnahme VALUES (3, 7, 1, 'ende', NULL, 'laeuft')")
    befunde = inv.pruefe_nach_diskussion(vorher, _stand(db), "p1-zuhoeren")
    assert inv.ENDE_NICHT_ANGEKOMMEN not in {b.schluessel for b in befunde}


def test_zwischenmeldung_ist_keine_antwort_auf_das_ende(db):
    """Die Zwischenmeldung beim langsamen Abtippen eines frueheren Segments
    (``aufnahme._TEXT_ZWISCHENMELDUNG``) antwortet nicht auf 'Discussion
    done' -- im Lauf gegen cb200e4 verdeckte sie die Stille danach."""
    vorher = _stand(db)
    _bot_post(db, 7, "I'm still typing up the voice message, one moment.")
    _bot_post(db, 7, "Ich tippe die Sprachnachricht noch ab, einen Moment.")
    nachher = _stand(db)
    assert inv.STILLE_NACH_ENDE in {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    _bot_post(db, 7, "The discussion is over.")
    nachher = _stand(db)
    assert not {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")} & {
        inv.STILLE_NACH_ENDE, inv.STILLE_LEERES_ENDE}


@pytest.fixture
def db_bis(tmp_path):
    """Wie ``db``, aber ``begriffsboard`` mit ``bis_aufnahme_id`` (reales
    Schema an cb200e4 und HEAD)."""
    pfad = tmp_path / "sim.db"
    conn = sqlite3.connect(pfad)
    conn.executescript(
        """
        CREATE TABLE begriffsboard (id INTEGER PRIMARY KEY, chat_id INTEGER, json TEXT,
                                    bis_aufnahme_id INTEGER);
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


def test_board_liest_knappe_nennung_nach_dem_ende_nicht(db_bis):
    """Abnahmelauf cb200e4: das Board war schon aus einer frueheren Runde
    gefuellt (Lauf bis Aufnahme 3), die knappe Nennung danach (unter 600
    Zeichen) las es auch nach 'Discussion done' nie -- dasselbe Symptom wie
    das leere Board, nur mit Vorgeschichte."""
    _schreibe(db_bis, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'foam and home', 'fertig')")
    _schreibe(db_bis, "INSERT INTO begriffsboard VALUES (1, 7, ?, 1)",
              json.dumps([{"begriff": "home", "status": "kandidat"}]))
    _bot_post(db_bis, 7, "welcome", post_id=1)
    vorher = _stand(db_bis)
    assert vorher.ungelesen_zeichen == 0
    _schreibe(db_bis, "INSERT INTO aufnahme VALUES (2, 7, 1, 'pause', 'Border. Waiting.', 'fertig')")
    _schreibe(db_bis, "INSERT INTO aufnahme VALUES (3, 7, 1, 'ende', NULL, 'fehlgeschlagen')")
    _schreibe(db_bis, "INSERT INTO arbeitsstand VALUES (7, 'home')")
    _bot_post(db_bis, 7, "The discussion is over.", post_id=2)
    nachher = _stand(db_bis)
    assert nachher.ungelesen_zeichen == len("Border. Waiting.")
    befunde = inv.pruefe_nach_diskussion(vorher, nachher, "p1-zuhoeren")
    assert [b.schluessel for b in befunde] == [inv.BOARD_NICHT_NACHGEZOGEN]
    assert "16 Zeichen" in befunde[0].text and befunde[0].schwere == "hoch"
    # Der Lauf nach dem Ende liest bis Aufnahme 3: kein Befund mehr.
    _schreibe(db_bis, "INSERT INTO begriffsboard VALUES (2, 7, ?, 3)",
              json.dumps([{"begriff": "border", "status": "kandidat"}]))
    assert inv.pruefe_nach_diskussion(vorher, _stand(db_bis), "p1-zuhoeren") == []


def test_ohne_bis_spalte_kein_ungelesen(db):
    _schreibe(db, "INSERT INTO aufnahme VALUES (1, 7, 1, 'pause', 'home', 'fertig')")
    _schreibe(db, "INSERT INTO begriffsboard VALUES (1, 7, ?)", json.dumps([{"begriff": "home"}]))
    assert _stand(db).ungelesen_zeichen == 0


def test_ohne_boardlauf_ist_alles_ungelesen_aber_board_leer_meldet(db_bis):
    vorher = _stand(db_bis)
    _schreibe(db_bis, "INSERT INTO aufnahme VALUES (1, 7, 1, 'ende', 'home', 'fertig')")
    nachher = _stand(db_bis)
    assert nachher.ungelesen_zeichen == 4
    schluessel = {b.schluessel for b in inv.pruefe_nach_diskussion(vorher, nachher, "s")}
    assert inv.BOARD_LEER in schluessel and inv.BOARD_NICHT_NACHGEZOGEN not in schluessel


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


def _ist_nicht_pruefbar(befund, ziel):
    assert befund.schluessel == f"nicht_pruefbar:{ziel}"
    assert befund.schwere == "hoch" and befund.ursache == inv.URSACHE_UNGEKLAERT


def test_raumcheck_ohne_messung_ist_nicht_pruefbar():
    """Abnahmelauf 05.10.2026: ohne bestaetigten Raumcheck gab es keinen
    ``vad_*``-Schluessel -- die leere Pruefung erschien als "–" und sah aus
    wie behoben. Sie ist nicht bestanden, sondern nicht pruefbar."""
    (b,) = inv.pruefe_raumcheck_schluessel(["theme"], "tok", "s")
    _ist_nicht_pruefbar(b, inv.RAUMCHECK_DOMAINWEIT)
    assert "keine Messung" in b.text
    # Ein domainweiter Schluessel (cb200e4) meldet weiter den echten Befund.
    (b,) = inv.pruefe_raumcheck_schluessel(["vad_schwelle"], "tok", "s")
    assert b.schluessel == inv.RAUMCHECK_DOMAINWEIT


def test_raumcheck_nicht_bestaetigt():
    (b,) = inv.pruefe_raumcheck_bestaetigt(["theme"], None, "p1-kalibrierung")
    assert b.schluessel == inv.RAUMCHECK_NICHT_BESTAETIGT
    assert b.schwere == "hoch" and b.ursache == inv.URSACHE_UNGEKLAERT
    assert inv.pruefe_raumcheck_bestaetigt(["theme"], "herumreichen", "s") == []
    assert inv.pruefe_raumcheck_bestaetigt(["vad_schwelle:tok:2026-10-05"], None, "s") == []
    assert inv.pruefe_raumcheck_bestaetigt(["vad_schwelle"], None, "s") == []


def test_verhoerer_nicht_korrigiert():
    (b,) = inv.pruefe_verhoerer(("Night shed", "home"), {"night shed": "night shift"}, "s")
    assert b.schluessel == inv.VERHOERER
    assert b.schwere == "mittel"
    assert inv.pruefe_verhoerer(("night shift",), {"night shed": "night shift"}, "s") == []


def test_verhoerer_bei_leerem_board_nicht_pruefbar():
    (b,) = inv.pruefe_verhoerer((), {"night shed": "night shift"}, "s")
    _ist_nicht_pruefbar(b, inv.VERHOERER)
    assert "Board leer" in b.text
    assert inv.pruefe_verhoerer((), {}, "s") == []   # kein Verhoerer im Skript: nichts zu pruefen


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
    s = inv.Sichtbar(board=("home",), werkbank=("home", "night shift"))
    (b,) = inv.pruefe_kontext("terms: home", s, "p2")
    assert b.schluessel == inv.CHAT_KENNT_WERKBANK_NICHT
    assert "night shift" in b.text
    assert b.ursache == inv.URSACHE_UNGEKLAERT


def test_kontext_transkript_mehrheit_reicht_und_normalisiert():
    prompt = "we  MISS home because of the border"
    s = inv.Sichtbar(board=("home",),
                     transkripte=("We miss home because of the border.", "Noise at night keeps us awake"))
    assert inv.pruefe_kontext(prompt, s, "s") == []  # 1 von 2 = Haelfte reicht
    s3 = inv.Sichtbar(board=("home",),
                      transkripte=("We miss home because of the border.", "Noise at night", "Waiting rooms"))
    assert inv.pruefe_kontext(prompt, s3, "s")[0].schluessel == inv.CHAT_KENNT_TRANSKRIPT_NICHT


def test_kontext_leeres_board_ist_nicht_pruefbar():
    """Leeres Board: "Chat kennt Board" konnte nicht laufen -- kein stilles []."""
    (b,) = inv.pruefe_kontext("", inv.Sichtbar(), "s")
    _ist_nicht_pruefbar(b, inv.CHAT_KENNT_BOARD_NICHT)
    assert "Board leer" in b.text


def test_wissensantwort():
    board = ("home", "border", "noise", "night shift")
    assert inv.pruefe_wissensantwort("On the CoThinker: home, border and noise.", board, "s") == []
    (b,) = inv.pruefe_wissensantwort("I can't see the cothinker page from here.", board, "s")
    assert b.schluessel == inv.CHAT_NENNT_BOARD_NICHT
    assert inv.pruefe_wissensantwort("home", ("home",), "s") == []
    (b,) = inv.pruefe_wissensantwort("anything", (), "s")
    _ist_nicht_pruefbar(b, inv.CHAT_NENNT_BOARD_NICHT)
    assert "Board leer" in b.text
    assert inv.WISSENSFRAGE == "Which terms are on the CoThinker right now?"


# --- Task 2b: Invarianten P3/P4 (Transkriptblase, Statuszeile, Phase-4-Sperre,
# CoThinker je Bogen, Modellwahl, Angebot 5) --------------------------------


@pytest.fixture
def db34(tmp_path):
    pfad = tmp_path / "sim34.db"
    conn = sqlite3.connect(pfad)
    conn.executescript(
        """
        CREATE TABLE web_post (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER,
                               richtung TEXT, typ TEXT, text TEXT, knoepfe TEXT, geloescht_am TEXT);
        CREATE TABLE aufnahme (id INTEGER PRIMARY KEY, chat_id INTEGER, klasse TEXT,
                               teil_von INTEGER, status TEXT, beendet_am TEXT, transkript TEXT,
                               zu_kurz_uebersprungen INTEGER DEFAULT 0, brainstorm INTEGER DEFAULT 0,
                               diskussion INTEGER DEFAULT 0, schnittgrund TEXT, entfernt_am TEXT,
                               echo_message_id INTEGER);
        CREATE TABLE verdichtung (id INTEGER PRIMARY KEY, chat_id INTEGER, aufnahme_id INTEGER);
        CREATE TABLE buehnenkarte (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT,
                                   modell TEXT, schweigen INTEGER DEFAULT 0);
        CREATE TABLE aufruf (id INTEGER PRIMARY KEY, chat_id INTEGER, art TEXT, modus TEXT,
                             erstellt_am TEXT);
        CREATE TABLE arbeitsstand (chat_id INTEGER PRIMARY KEY, phase INTEGER, phase_angeboten INTEGER,
                                   rahmen TEXT, geschichte TEXT, szenen_anzahl TEXT,
                                   figuren_fixiert_am TEXT, begriffe TEXT);
        CREATE TABLE figur (id INTEGER PRIMARY KEY, chat_id INTEGER, name TEXT, entfernt_am TEXT);
        CREATE TABLE szene (id INTEGER PRIMARY KEY, chat_id INTEGER, entfernt_am TEXT);
        CREATE TABLE vorfall (id INTEGER PRIMARY KEY, chat_id INTEGER, art TEXT, erstellt_am TEXT);
        """)
    conn.commit(); conn.close()
    return pfad


def _p34(pfad, chat_id=7):
    with inv.oeffne_lesend(pfad) as conn:
        return inv.lese_p34_stand(conn, chat_id)


def test_interview_ohne_transkriptblase_und_statuszeile(db34):
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript) "
                    "VALUES (1, 7, 'lang', 'fertig', 'x', 'a b c')")
    befunde = inv.pruefe_nach_interview(vorher, _p34(db34), "p3-interview-kurz")
    schluessel = {b.schluessel for b in befunde}
    assert {inv.INTERVIEW_OHNE_BLASE, inv.INTERVIEW_OHNE_STATUS} <= schluessel


def test_interview_mit_blase_und_einer_statuszeile_ist_sauber(db34):
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript, "
                    "zu_kurz_uebersprungen) VALUES (1, 7, 'lang', 'fertig', 'x', 'a b c', 1)")
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'transkript', '🎙 Interview 1\n\nhi')")
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'system', 'Interview 1 is too short to summarise (12 words).')")
    assert inv.pruefe_nach_interview(vorher, _p34(db34), "p3-interview-kurz") == []


def test_doppelte_statuszeile_und_deutscher_status_sind_mittel(db34):
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript, "
                    "zu_kurz_uebersprungen) VALUES (1, 7, 'lang', 'fertig', 'x', 'a', 1)")
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'transkript', '🎙 Interview 1')")
    for _ in range(2):
        _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                        "(7, 'aus', 'system', 'Das Interview ist zu kurz (12 Wörter).')")
    befunde = {b.schluessel: b for b in inv.pruefe_nach_interview(vorher, _p34(db34), "p3")}
    assert befunde[inv.INTERVIEW_STATUS_DOPPELT].schwere == "mittel"
    assert befunde[inv.INTERVIEW_STATUS_DEUTSCH].schwere == "mittel"


def test_interview_nur_mit_beenden_bestaetigung_ist_ohne_statuszeile(db34):
    """I1 (Review 05.10.2026, Fix round 1): jedes '/fertig' schickt zuerst
    die reine Beenden-Bestaetigung ("Recording stopped."/"Aufnahme
    beendet.") als Systemzeile -- sie darf INTERVIEW_OHNE_STATUS nicht
    verdecken, wenn die eigentliche Auswertungszeile (zu kurz/gespeichert)
    nie ankommt. Vorher zaehlte diese eine Zeile schon als "eine
    Statuszeile", INTERVIEW_OHNE_STATUS konnte dadurch nie feuern."""
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript) "
                    "VALUES (1, 7, 'lang', 'fertig', 'x', 'a b c')")
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'transkript', '🎙 Interview 1')")
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'system', 'Recording stopped.')")
    befunde = {b.schluessel for b in inv.pruefe_nach_interview(vorher, _p34(db34), "p3-interview-kurz")}
    assert inv.INTERVIEW_OHNE_STATUS in befunde
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text) VALUES "
                    "(7, 'aus', 'system', 'Aufnahme beendet.')")
    befunde_de = {b.schluessel for b in inv.pruefe_nach_interview(vorher, _p34(db34), "p3-interview-kurz")}
    assert inv.INTERVIEW_OHNE_STATUS in befunde_de


def test_phase4_gesperrt_ohne_laufende_verdichtung(db34):
    # beendet, Transkript da, nicht zu kurz, keine Verdichtung, Status steht
    # (transkribiert nach gescheitertem Versuch) -- sperrt, ohne dass etwas laeuft.
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript) "
                    "VALUES (1, 7, 'lang', 'transkribiert', 'x', 'viele woerter')")
    befunde = inv.pruefe_p4_sperre(_p34(db34), "p3-uebergang")
    assert [b.schluessel for b in befunde] == [inv.P4_GESPERRT_OHNE_VERDICHTUNG]


def test_phase4_sperre_erkennt_haengenden_kopf_status_laeuft(db34):
    """I5 (Review 05.10.2026, Fix round 1): ``aufnahme.unausgewertete_
    interviews`` zaehlt ``beendet_am`` gesetzt ODER Status fertig/
    transkribiert als 'beendet' -- ein Kopf, der WEITERHIN auf 'laeuft'
    steht, obwohl ``beendet_am`` laengst (ueber ``FRIST_NACH_INTERVIEW_S``
    hinaus) gesetzt ist, ist ein haengender Kopf und zaehlt. Vorher schloss
    ``pruefe_p4_sperre`` jeden Status in (laeuft, empfangen) BLIND aus,
    egal wie lange er schon so stand."""
    alt = "2000-01-01T00:00:00+00:00"
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript) "
                    f"VALUES (1, 7, 'lang', 'laeuft', '{alt}', 'viele woerter')")
    befunde = inv.pruefe_p4_sperre(_p34(db34), "p3-uebergang")
    assert [b.schluessel for b in befunde] == [inv.P4_GESPERRT_OHNE_VERDICHTUNG]


def test_phase4_sperre_laesst_frisch_beendeten_kopf_in_ruhe(db34):
    """Gegenstueck: ein Kopf, dessen ``beendet_am`` gerade erst gesetzt
    wurde, bekommt die normale Verarbeitung noch ihre Zeit (keine Sperre)."""
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, beendet_am, transkript) "
                    f"VALUES (1, 7, 'lang', 'laeuft', '{jetzt}', 'viele woerter')")
    assert inv.pruefe_p4_sperre(_p34(db34), "p3-uebergang") == []


def test_brainstorm_genau_eine_reaktion_nach_dem_ende(db34):
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, brainstorm, schnittgrund, "
                    "transkript) VALUES (5, 7, 'kurz', 'fertig', 1, 'ende', 'the bench and the cafe')")
    assert {b.schluessel for b in inv.pruefe_nach_brainstorm(vorher, vorher, _p34(db34), "p4")} \
        == {inv.BRAINSTORM_OHNE_REAKTION}
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell, schweigen) "
                    "VALUES (7, 'The cousin on the bench waits for the cafe to close.', 'claude', 0)")
    assert inv.pruefe_nach_brainstorm(vorher, vorher, _p34(db34), "p4") == []


def test_karte_waehrend_des_bogens_ist_kein_befund_wenn_geerdet(db34):
    """Birk 05.10.2026 22:00: kein Toggle mehr, kontinuierliches Zuhoeren --
    eine Zwischenkarte WAEHREND des Bogens (vor dem Ende-Schnitt) ist jetzt
    erwartetes Verhalten, kein Befund mehr (anders als beim alten Toggle,
    wo eine Karte vor dem Ende unmoeglich war). ``BRAINSTORM_KARTE_
    WAEHREND_BOGEN`` ist deshalb ersatzlos entfallen."""
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The cousin on the bench waits for the cafe to close.', 'claude')")
    vor_ende = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, brainstorm, schnittgrund, "
                    "transkript) VALUES (5, 7, 'kurz', 'fertig', 1, 'ende', 'the bench and the cafe')")
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The broken bag waits by the cafe near the bench.', 'claude')")
    assert inv.pruefe_nach_brainstorm(vorher, vor_ende, _p34(db34), "p4") == []


def test_karte_waehrend_des_bogens_ungeerdet_ist_weiterhin_ein_befund(db34):
    """Eine Zwischenkarte bleibt pruefbar: ist SIE ungeerdet, feuert
    ``COTHINKER_UNGEERDET`` -- nur das "waehrend"-Timing selbst ist kein
    Befund mehr."""
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'Pirates sail to Mars tonight.', 'claude')")
    vor_ende = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, brainstorm, schnittgrund, "
                    "transkript) VALUES (5, 7, 'kurz', 'fertig', 1, 'ende', 'the bench and the cafe')")
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The broken bag waits by the cafe near the bench.', 'claude')")
    schluessel = {b.schluessel for b in inv.pruefe_nach_brainstorm(vorher, vor_ende, _p34(db34), "p4")}
    assert schluessel == {inv.COTHINKER_UNGEERDET}
    assert not hasattr(inv, "BRAINSTORM_KARTE_WAEHREND_BOGEN")


def test_brainstorm_mehrere_karten_zaehlt_nur_karten_nach_dem_ende(db34):
    """``BRAINSTORM_MEHRERE_KARTEN`` heisst seit dem Umbau "mehr als eine
    Reaktion NACH dem Ende" -- eine Zwischenkarte waehrend des Bogens plus
    GENAU EINE Karte nach dem Ende ist weiterhin sauber (keine der beiden
    Befunde), weil die Abschlusspruefung nur zaehlt, was NACH
    ``vor_ende`` entstanden ist."""
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The cousin on the bench waits for the cafe to close.', 'claude')")
    vor_ende = _p34(db34)
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, brainstorm, schnittgrund, "
                    "transkript) VALUES (5, 7, 'kurz', 'fertig', 1, 'ende', 'the bench and the cafe')")
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The broken bag waits by the cafe near the bench.', 'claude')")
    assert inv.pruefe_nach_brainstorm(vorher, vor_ende, _p34(db34), "p4") == []
    # Eine ZWEITE Karte nach dem Ende ist weiterhin ein Befund.
    _schreibe(db34, "INSERT INTO buehnenkarte (chat_id, text, modell) VALUES "
                    "(7, 'The cafe owner remembers the bench too.', 'claude')")
    schluessel = {b.schluessel for b in inv.pruefe_nach_brainstorm(vorher, vor_ende, _p34(db34), "p4")}
    assert inv.BRAINSTORM_MEHRERE_KARTEN in schluessel


def test_karte_geerdet_braucht_zwei_inhaltswoerter():
    assert inv.karte_geerdet("The cousin never comes to the bench.", "bench cousin cafe bag")
    assert not inv.karte_geerdet("A dragon appears.", "bench cousin cafe bag")


def test_karte_geerdet_gegen_bogen_lehnt_generische_saetze_ab():
    """I3 (Review 05.10.2026, Fix round 1): mit ``{4,}`` zaehlten generische
    englische Funktionswoerter (what/that/maybe/could/time/...) als
    'Inhaltswort' -- gegen den echten Brainstorm-Skript-Text getestet, nicht
    nur gegen den kurzen Kunstfall aus dem Brief."""
    from simulation.diskussionen import DISKUSSIONEN

    transkript = DISKUSSIONEN["brainstorm-bogen"].text()
    assert not inv.karte_geerdet("What if that is the whole story?", transkript)
    assert not inv.karte_geerdet("Maybe they could have more time together.", transkript)
    # Eine wirklich geerdete Karte bleibt erkannt.
    assert inv.karte_geerdet(
        "The cousin waits by the bench near the cafe with his broken bag.", transkript)


def test_karte_geerdet_gegen_bogen_lehnt_weitere_generische_saetze_ab():
    """I1 (Review 05.10.2026, Fix round 2): diese drei Saetze trafen vor dem
    Fix alle als 'geerdet', weil (a) ``in karte_cf`` Transkriptwoerter als
    Teilstring statt als ganzes Wort suchte und (b) generische, aber im
    Bogen-Text woertlich vorkommende Fuellwoerter (whole/never/always/same/
    every/single/right/actually) als 'Inhaltswort' zaehlten."""
    from simulation.diskussionen import DISKUSSIONEN

    transkript = DISKUSSIONEN["brainstorm-bogen"].text()
    assert not inv.karte_geerdet("What if the whole thing might never end?", transkript)
    assert not inv.karte_geerdet("Everyone forgets something right away.", transkript)
    assert not inv.karte_geerdet("It is always the same, every single time.", transkript)


def test_modellwahl_phase3_nie_opus_phase4_opus_keine_usa_frage(db34):
    for i, (art, modus) in enumerate([("gespraech", "A"), ("gespraech", "C"), ("verdichter", "A")], 1):
        _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus) VALUES (?, 7, ?, ?)", i, art, modus)
    stand = _p34(db34)
    befunde = inv.pruefe_modellwahl(stand, phase3=(0, 2), phase4=(2, 9), station="p3-uebergang")
    # I4 (Fix round 1): phase4=(2, 9) enthaelt hier keinen einzigen
    # 'gespraech'-Aufruf (nur den 'verdichter') -- das ist nicht "in
    # Ordnung", sondern nicht pruefbar, und wird seitdem auch so gemeldet.
    assert {b.schluessel for b in befunde} == {
        inv.P3_GESPRAECH_OPUS, f"{inv.NICHT_PRUEFBAR}:{inv.P4_GESPRAECH_NICHT_OPUS}"}
    _schreibe(db34, "INSERT INTO web_post (chat_id, richtung, typ, text, knoepfe) VALUES "
                    "(7, 'aus', 'text', 'Tap what should apply:', '[[\"Yes, US model\", \"k:1\"]]')")
    assert inv.EINWILLIGUNG_GEFRAGT in {
        b.schluessel for b in inv.pruefe_modellwahl(_p34(db34), (0, 0), (0, 9), "p3-uebergang")}


def test_modellwahl_phase4_leer_ist_nicht_pruefbar(db34):
    """I4 (Review 05.10.2026, Fix round 1): kein 'gespraech'-Aufruf im
    geprueften Phase-4-Bereich (leerer Bereich ODER nur andersartige
    Aufrufe) -- P4_GESPRAECH_NICHT_OPUS ist nicht pruefbar, nicht stillschweigend
    in Ordnung."""
    _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus) VALUES (1, 7, 'verdichter', 'A')")
    stand = _p34(db34)
    befunde = inv.pruefe_modellwahl(stand, phase3=(0, 0), phase4=(0, 1), station="p4-uebergang")
    assert [b.schluessel for b in befunde] == [f"{inv.NICHT_PRUEFBAR}:{inv.P4_GESPRAECH_NICHT_OPUS}"]
    # Ein leerer Bereich (noch keine Phase-4-Station gelaufen) ist derselbe Fall.
    befunde_leer = inv.pruefe_modellwahl(stand, phase3=(0, 1), phase4=(0, 0), station="p4-uebergang")
    assert [b.schluessel for b in befunde_leer] == [f"{inv.NICHT_PRUEFBAR}:{inv.P4_GESPRAECH_NICHT_OPUS}"]


def test_modellwahl_nur_phase_beschraenkt_auf_die_eigene_stationsphase(db34):
    """M2 (Review 05.10.2026, Fix round 2): ohne Einschraenkung pruefte
    ``pruefe_modellwahl`` an JEDER Station IMMER beide Phasenteile -- an
    ``p3-uebergang`` ist der Phase-4-Bereich noch leer (keine Phase-4-Station
    ist gelaufen), das lieferte dort IMMER
    ``nicht_pruefbar:p4_gespraech_nicht_opus`` als Rauschen; und ein echter
    ``P3_GESPRAECH_OPUS``-Befund wuerde an der spaeteren Phase-4-Station
    (``p4-uebergang``) ein zweites Mal gemeldet, weil derselbe
    Phase-3-Bereich dort erneut geprueft wird. ``nur_phase`` beschraenkt die
    Pruefung auf den zur Station passenden Teil."""
    for i, (art, modus) in enumerate([("gespraech", "C"), ("gespraech", "A")], 1):
        _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus) VALUES (?, 7, ?, ?)", i, art, modus)
    stand = _p34(db34)
    # An der Phase-3-Station (nur_phase=3): der P3-Befund kommt, der leere
    # Phase-4-Bereich bleibt UNGEPRUEFT (kein nicht_pruefbar-Rauschen).
    befunde3 = inv.pruefe_modellwahl(stand, phase3=(0, 1), phase4=(0, 0), station="p3-uebergang",
                                     nur_phase=3)
    assert [b.schluessel for b in befunde3] == [inv.P3_GESPRAECH_OPUS]
    # An der Phase-4-Station (nur_phase=4): derselbe Phase-3-Bereich wird
    # NICHT erneut geprueft -- der P3-Befund kommt kein zweites Mal, nur das
    # Phase-4-Ergebnis (hier: regulaer ueber Opus, also gar kein Befund).
    befunde4 = inv.pruefe_modellwahl(stand, phase3=(0, 1), phase4=(1, 2), station="p4-uebergang",
                                     nur_phase=4)
    assert inv.P3_GESPRAECH_OPUS not in {b.schluessel for b in befunde4}


def test_modellwahl_opus_fallback_exoneriert_den_kimi_zug(db34):
    """H2 (Abnahme P3-4, Lauf 042439, 06.10.2026): Opus scheitert (aufruf 1,
    modus 'C', erfolg egal fuer diese Pruefung), der Fallback laeuft sofort
    danach auf Kimi (aufruf 2, modus 'A') -- derselbe, einzige Zug. Ein
    ``vorfall``-Zeile ``art='opus_fallback'`` im selben Zeitfenster (hier:
    dieselbe Sekunde) exoneriert GENAU DIESEN Zug -- vorher feuerte
    P4_GESPRAECH_NICHT_OPUS hier immer, auch fuer den dokumentierten
    Rueckfall (interview_theater/modellwahl.py, ``aufruf_schema``/
    ``_melde_fallback``, ``VORFALL_OPUS_FALLBACK = 'opus_fallback'``)."""
    _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES "
                    "(1, 7, 'gespraech', 'C', '2026-10-06T02:37:10')")
    _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES "
                    "(2, 7, 'gespraech', 'A', '2026-10-06T02:37:12')")
    _schreibe(db34, "INSERT INTO vorfall (id, chat_id, art, erstellt_am) VALUES "
                    "(1, 7, 'opus_fallback', '2026-10-06T02:37:12')")
    stand = _p34(db34)
    befunde = inv.pruefe_modellwahl(stand, phase3=(0, 0), phase4=(0, 2), station="p4-uebergang")
    assert inv.P4_GESPRAECH_NICHT_OPUS not in {b.schluessel for b in befunde}


def test_modellwahl_non_opus_zug_ohne_vorfall_bleibt_ein_befund(db34):
    """Gegenprobe zu H2: ohne eine passende ``vorfall``-Zeile bleibt ein
    non-Opus-Gespraechsaufruf in Phase 4 weiterhin ein Befund -- die
    Exoneration darf nicht zu grosszuegig werden."""
    _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES "
                    "(1, 7, 'gespraech', 'A', '2026-10-06T02:37:12')")
    stand = _p34(db34)
    befunde = inv.pruefe_modellwahl(stand, phase3=(0, 0), phase4=(0, 1), station="p4-uebergang")
    assert inv.P4_GESPRAECH_NICHT_OPUS in {b.schluessel for b in befunde}


def test_modellwahl_vorfall_ausserhalb_des_fensters_exoneriert_nicht(db34):
    """Ein ``opus_fallback``-Vorfall, der Minuten entfernt liegt (ein
    frueherer, unabhaengiger Fallback), darf einen spaeteren non-Opus-Zug
    nicht exonerieren -- sonst waere die Pruefung wirkungslos."""
    _schreibe(db34, "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES "
                    "(1, 7, 'gespraech', 'A', '2026-10-06T02:50:00')")
    _schreibe(db34, "INSERT INTO vorfall (id, chat_id, art, erstellt_am) VALUES "
                    "(1, 7, 'opus_fallback', '2026-10-06T02:37:12')")
    stand = _p34(db34)
    befunde = inv.pruefe_modellwahl(stand, phase3=(0, 0), phase4=(0, 1), station="p4-uebergang")
    assert inv.P4_GESPRAECH_NICHT_OPUS in {b.schluessel for b in befunde}


# -- H5/Coverage-Luecke: EINE wachsende Transkript-Blase ---------------------


def test_transkriptblase_waechst_ist_sauber_bei_laengerem_text(db34):
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, echo_message_id) "
                    "VALUES (1, 7, 'lang', 'laeuft', 5)")
    _schreibe(db34, "INSERT INTO web_post (id, chat_id, richtung, typ, text) VALUES "
                    "(5, 7, 'aus', 'transkript', '🎙 Interview 1\n\nhi')")
    vorher = _p34(db34)
    _schreibe(db34, "UPDATE web_post SET text = '🎙 Interview 1\n\nhi\n\nhow are you' WHERE id = 5")
    nachher = _p34(db34)
    assert inv.pruefe_transkriptblase_waechst(vorher, nachher, 1, "p3-interview-gemischt") == []


def test_transkriptblase_nicht_gewachsen_ist_ein_befund(db34):
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, echo_message_id) "
                    "VALUES (1, 7, 'lang', 'laeuft', 5)")
    _schreibe(db34, "INSERT INTO web_post (id, chat_id, richtung, typ, text) VALUES "
                    "(5, 7, 'aus', 'transkript', '🎙 Interview 1\n\nhi')")
    vorher = _p34(db34)
    # kein zweites UPDATE -- derselbe Text, die Blase ist nicht gewachsen.
    nachher = _p34(db34)
    befunde = inv.pruefe_transkriptblase_waechst(vorher, nachher, 1, "p3-interview-gemischt")
    assert [b.schluessel for b in befunde] == [inv.TRANSKRIPTBLASE_NICHT_GEWACHSEN]


def test_transkriptblase_mehrere_sichtbare_zeilen_ist_ein_befund(db34):
    """Mutation-Check: ersetzt man die EINE, wiederverwendete Zeile durch
    eine zweite (die alte, von Telegram bekannte 'ein Echo je Teil'-Bauart
    ohne Fliesstext), muss die Pruefung das als Regression erkennen."""
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status, echo_message_id) "
                    "VALUES (1, 7, 'lang', 'laeuft', 5)")
    _schreibe(db34, "INSERT INTO web_post (id, chat_id, richtung, typ, text) VALUES "
                    "(5, 7, 'aus', 'transkript', '🎙 Interview 1\n\nhi')")
    vorher = _p34(db34)
    _schreibe(db34, "INSERT INTO web_post (id, chat_id, richtung, typ, text) VALUES "
                    "(6, 7, 'aus', 'transkript', '🎙 Interview 1\n\nhow are you')")
    nachher = _p34(db34)
    befunde = inv.pruefe_transkriptblase_waechst(vorher, nachher, 1, "p3-interview-gemischt")
    assert [b.schluessel for b in befunde] == [inv.TRANSKRIPTBLASE_NICHT_GEWACHSEN]


def test_transkriptblase_ohne_echo_id_ist_nicht_pruefbar(db34):
    _schreibe(db34, "INSERT INTO aufnahme (id, chat_id, klasse, status) VALUES (1, 7, 'lang', 'laeuft')")
    stand = _p34(db34)
    befunde = inv.pruefe_transkriptblase_waechst(stand, stand, 1, "p3-interview-gemischt")
    assert [b.schluessel for b in befunde] == [f"{inv.NICHT_PRUEFBAR}:{inv.TRANSKRIPTBLASE_NICHT_GEWACHSEN}"]


# -- Coverage-Luecke Pause/Resume --------------------------------------------


def test_pause_resume_erfolgreich_ist_sauber():
    assert inv.pruefe_pause_resume(True, True, "p3-interview-gemischt") == []


def test_pause_resume_angefordert_aber_nicht_bestaetigt_ist_mittel():
    befunde = inv.pruefe_pause_resume(False, True, "p3-interview-gemischt")
    assert befunde[0].schluessel == inv.INTERVIEW_PAUSE_NICHT_BESTAETIGT
    assert befunde[0].schwere == "mittel"


def test_pause_resume_nicht_angefordert_ist_nicht_pruefbar():
    befunde = inv.pruefe_pause_resume(False, False, "p3-eintritt")
    assert [b.schluessel for b in befunde] == [f"{inv.NICHT_PRUEFBAR}:{inv.INTERVIEW_PAUSE_NICHT_BESTAETIGT}"]


def test_p5_nicht_angeboten_obwohl_moeglich(db34):
    _schreibe(db34, "INSERT INTO arbeitsstand (chat_id, phase, phase_angeboten, rahmen, geschichte, "
                    "szenen_anzahl, figuren_fixiert_am) VALUES (7, 4, NULL, 'r', 'g', '3', 'x')")
    _schreibe(db34, "INSERT INTO figur (chat_id, name) VALUES (7, 'Samir')")
    assert [b.schluessel for b in inv.pruefe_p5_angebot(_p34(db34), "p4-uebergang")] \
        == [inv.P5_NICHT_ANGEBOTEN]


def test_p5_nicht_moeglich_wenn_einzige_figur_weich_entfernt_wurde(db34):
    """M2 (Review 05.10.2026, Fix round 1): ``lese_p34_stand`` zaehlte
    weich entfernte Figuren/Szenen mit (``figur.entfernt_am`` ignoriert) --
    ``repo.figuren``/``repo.hole_szenen`` filtern sie ueberall sonst raus.
    Mit einer entfernten Figur ist Phase 5 in Wahrheit NICHT moeglich."""
    _schreibe(db34, "INSERT INTO arbeitsstand (chat_id, phase, phase_angeboten, rahmen, geschichte, "
                    "szenen_anzahl, figuren_fixiert_am) VALUES (7, 4, NULL, 'r', 'g', '3', 'x')")
    _schreibe(db34, "INSERT INTO figur (chat_id, name, entfernt_am) VALUES (7, 'Samir', 'x')")
    assert inv.pruefe_p5_angebot(_p34(db34), "p4-uebergang") == []


# --- I2 (Review 05.10.2026, Fix round 1): ``warte_auf`` darf nicht beim
# ersten befundfreien Zwischenstand zurueckgeben -- eine zweite, verspaetete
# Statuszeile/Karte kam dann nie zur Pruefung. Fake-Leser-Folgen, keine Zeit.


def test_warte_auf_meldet_verspaetetes_duplikat_nach_der_gnadenfrist():
    folge = iter([
        {"status": ()},                 # noch keine Statuszeile -- ende() falsch
        {"status": ("x",)},             # erstes Signal -- ende() wird wahr, Schleife haelt an
        {"status": ("x", "x")},         # erst WAEHREND der Gnadenfrist kommt das Duplikat
    ])
    letzter = {"stand": None}

    def lese():
        letzter["stand"] = next(folge, letzter["stand"])
        return letzter["stand"]

    def pruefe(stand):
        return ["doppelt"] if len(stand["status"]) >= 2 else []

    schlafzeiten = []
    befunde, stand = inv.warte_auf(
        lese, pruefe, frist_s=30.0, ende=lambda s: bool(s["status"]),
        grace_s=5.0, takt_s=1.0, schlafe=schlafzeiten.append, uhr=lambda: 0.0)
    assert befunde == ["doppelt"]
    assert stand == {"status": ("x", "x")}
    assert 5.0 in schlafzeiten    # die Gnadenfrist wurde tatsaechlich abgewartet


def test_warte_auf_wartet_die_gnadenfrist_auch_nach_der_frist_ab():
    """Ohne ``ende`` (oder wenn es nie wahr wird) blieb frueher schon die
    Frist allein massgeblich -- jetzt kommt in JEDEM Fall noch die
    Gnadenfrist VOR der finalen Pruefung dazu."""
    zeit = {"t": 0.0}
    rufe = []

    def lese():
        rufe.append("lese")
        return len(rufe)

    def schlafe(sekunden):
        rufe.append(("schlafe", sekunden))
        zeit["t"] += sekunden

    befunde, stand = inv.warte_auf(
        lese, lambda s: [], frist_s=2.0, ende=lambda s: False, grace_s=7.0,
        takt_s=1.0, schlafe=schlafe, uhr=lambda: zeit["t"])
    assert ("schlafe", 7.0) in rufe
    assert befunde == []


def test_grace_nach_interview_mindestens_nachhol_intervall_plus_fuenf():
    """M3 (Review 05.10.2026, Fix round 2): ``GRACE_NACH_SIGNAL_S`` (10 s)
    ist KUERZER als ``aufnahme.NACHHOL_INTERVALL_S`` (60 s) -- fuer den
    Interview-Pfad reicht das nicht: eine zweite Statuszeile, die erst durch
    einen Nachhol-Lauf entsteht, kommt oft erst nach ueber 60 s. Pinnt die
    Beziehung, statt die Zahl ein zweites Mal zu raten."""
    from interview_theater import aufnahme

    assert inv.GRACE_NACH_INTERVIEW_S == aufnahme.NACHHOL_INTERVALL_S + 5.0
    assert inv.GRACE_NACH_INTERVIEW_S >= aufnahme.NACHHOL_INTERVALL_S + 5.0
    assert inv.GRACE_NACH_SIGNAL_S < aufnahme.NACHHOL_INTERVALL_S

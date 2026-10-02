"""Der Gespraechszug streamt -- und nichts Halbes wird je eine Nachricht.

Vier Faelle, die zusammengehoeren (Entscheidung D und E):
* der Regelfall -- Teiltexte fliessen, am Ende steht die fertige Nachricht
  und die Stromzeile traegt ihre ``post_id``;
* die verworfene Antwort (Wiederholung, erfundene Systemzeile) -- die
  vorlaeufige Blase verschwindet ersatzlos;
* der zweite Aufruf (Echo) -- der Strom beginnt NEU statt anzuhaengen;
* der gescheiterte Zug -- 'abgebrochen', keine halbe Nachricht.
"""

import pytest

from interview_theater import ablauf, db, repo, strom, web_kanal

CHAT = 7_000_000_000_001


class Einstellungen:
    bot_name = "gruppe1"
    llm_modell = "x"


class KlmMitStrom:
    """Ein Sprachmodell, das seine Antwort in Stuecken liefert."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort"):
        text = self._antworten[min(self.aufrufe, len(self._antworten) - 1)]
        self.aufrufe += 1
        if bei_teil is not None:
            gesehen = ""
            for zeichen in text:
                gesehen += zeichen
                bei_teil(gesehen)
        return {"antwort": text}


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    tg = web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"))
    # Der Takt der Drosselung stoert im Test nur.
    monkeypatch.setattr(strom, "INTERVALL_S", 0.0)
    return conn, tg


def _nachricht(conn, text="Womit fangen wir an?"):
    """Legt die Nachricht sowohl als ``web_post`` (das der Kanal fuer die
    Senke braucht) als auch als ``nachricht`` an (das ``unbeantwortete``
    liest). Abweichung vom Plantext: ``lege_web_post_an`` allein fuellt
    ``nachricht`` nicht -- das macht im Betrieb ``bot.verarbeite_update``
    nach ``kanal.hole_updates``, was dieser Test nicht durchlaeuft."""
    message_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN,
                                       repo.WEB_TYP_TEXT, text=text)
    repo.merke_nachricht(conn, CHAT, message_id, web_kanal.ABSENDER, 0,
                         "text", text, repo._jetzt())
    return repo.unbeantwortete(conn, CHAT), message_id


def _stroeme(conn):
    return conn.execute(
        "SELECT * FROM web_strom WHERE chat_id = ? ORDER BY id", (CHAT,)
    ).fetchall()


def test_der_regelfall_endet_mit_fertig_und_post_id(aufbau):
    conn, tg = aufbau
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Fangen wir mit Begriffen an."]),
                    Einstellungen(), CHAT, offen)
    zeilen = _stroeme(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["zustand"] == repo.STROM_FERTIG
    assert zeilen[0]["post_id"] is not None
    # Die fertige Nachricht steht als web_post unter genau dieser id.
    assert repo.hole_web_post(conn, zeilen[0]["post_id"])["richtung"] == repo.RICHTUNG_AUS


def test_der_teiltext_wandert_waehrenddessen_in_die_zeile(aufbau):
    """Ohne diesen Test koennte der ganze Weg auch erst am Ende schreiben --
    und niemand saehe einen Unterschied zu vorher."""
    conn, tg = aufbau
    gesehen = []

    class Mitlesend(KlmMitStrom):
        def schema(self, *args, bei_teil=None, **kw):
            def merke(text):
                bei_teil(text)
                gesehen.append(_stroeme(conn)[0]["text"] if _stroeme(conn) else "")
            return super().schema(*args, bei_teil=merke, **kw)

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Mitlesend(["Hallo ihr"]), Einstellungen(), CHAT, offen)
    assert any(0 < len(t) < len("Hallo ihr") for t in gesehen), gesehen


def test_eine_verworfene_antwort_hinterlaesst_keine_blase(aufbau, monkeypatch):
    """Wiederholungsfilter: die Antwort geht NICHT raus -- dann darf auch die
    vorlaeufige Blase nicht stehenbleiben."""
    conn, tg = aufbau
    monkeypatch.setattr(ablauf, "ist_wiederholung", lambda *a, **k: True)
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Das habe ich schon gesagt.")
    repo.merke_nachricht(conn, CHAT, 1, "gruppe1", 1, "text",
                         "Das habe ich schon gesagt.", repo._jetzt())
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Das habe ich schon gesagt."]),
                    Einstellungen(), CHAT, offen)
    assert _stroeme(conn)[-1]["zustand"] == repo.STROM_ABGEBROCHEN
    assert _stroeme(conn)[-1]["post_id"] is None


def test_ein_gescheiterter_zug_bricht_den_strom_ab(aufbau):
    conn, tg = aufbau

    class Kaputt:
        def schema(self, *a, bei_teil=None, **kw):
            if bei_teil is not None:
                bei_teil("halber ")
            raise RuntimeError("Anbieter weg")

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Kaputt(), Einstellungen(), CHAT, offen)
    assert _stroeme(conn)[-1]["zustand"] == repo.STROM_ABGEBROCHEN


def test_ein_zweiter_anlauf_beginnt_eine_neue_zeile(aufbau, monkeypatch):
    """Entscheidung D: loest ``_ohne_echo`` einen zweiten Aufruf aus, beginnt
    der Strom neu -- die verworfene erste Antwort klebt nicht davor."""
    conn, tg = aufbau
    rufe = {"n": 0}

    def echo(antwort, ausloeser):
        rufe["n"] += 1
        return rufe["n"] == 1

    monkeypatch.setattr(ablauf, "ist_echo", echo)
    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, KlmMitStrom(["Womit fangen wir an?", "Mit den Begriffen."]),
                    Einstellungen(), CHAT, offen)
    zeilen = _stroeme(conn)
    assert len(zeilen) == 2
    assert zeilen[0]["zustand"] == repo.STROM_ABGEBROCHEN
    assert zeilen[1]["zustand"] == repo.STROM_FERTIG
    assert "Womit fangen wir an?" not in zeilen[1]["text"]


def test_ein_vorschlagsblock_erscheint_nie_im_strom(aufbau):
    """Entscheidung D: was sichtbar gestreamt wird, ist schon gesaeubert."""
    conn, tg = aufbau
    antwort = "Wie waere es damit?\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit"
    gesehen = []

    class Mitlesend(KlmMitStrom):
        def schema(self, *args, bei_teil=None, **kw):
            def merke(text):
                bei_teil(text)
                zeilen = _stroeme(conn)
                if zeilen:
                    gesehen.append(zeilen[-1]["text"])
            return super().schema(*args, bei_teil=merke, **kw)

    offen, _ = _nachricht(conn)
    ablauf.antworte(conn, tg, Mitlesend([antwort]), Einstellungen(), CHAT, offen)
    assert all("VORSCHLAG" not in t for t in gesehen), gesehen
    assert all("VORSCHLA" not in t for t in gesehen), gesehen


def test_ein_kanal_ohne_strom_verhaelt_sich_wie_vorher(tmp_path):
    """E1: dieselbe Antwort, kein Strom, keine Ausnahme."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Telegram-Gruppe")

    class TgOhneStrom:
        def __init__(self):
            self.gesendet = []

        def sende(self, chat_id, text, **kw):
            self.gesendet.append(text)
            return len(self.gesendet)

        def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
            return self.sende(chat_id, text)

        def tippt(self, chat_id):
            pass

    tg = TgOhneStrom()
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "Hallo", repo._jetzt())
    offen = repo.unbeantwortete(conn, 1)
    ablauf.antworte(conn, tg, KlmMitStrom(["Hallo zurueck"]), Einstellungen(), 1, offen)
    assert tg.gesendet
    assert conn.execute("SELECT COUNT(*) FROM web_strom").fetchone()[0] == 0

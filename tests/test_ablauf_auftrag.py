"""Der Gespraechs-Bot redet nicht parallel zu einem Auftrag (06.09.2026).

Der Live-Fall (Testgruppe, 00:30):

    00:30:28  Birk:  "neu schreiben"
    00:30:31  Bot:   "Birk, klar -- Szene 1 neu. Eine Frage dazu: Leyla
                      wartet, die anderen kommen dazu. Soll der Typ wirklich
                      kommen ...? Das aendert, wie die Szene endet."
    00:30:32  Bot:   [USA-Hinweis]
    00:30:32  Bot:   "Ich schreibe die Szene aus, das dauert eine Minute."

Die Frage war nie eine -- die Szene lief eine Sekunde spaeter ohnehin los.
Gezaehlt wurden am Testabend **14** solche Doppelungen (Gespraechsantwort
unmittelbar vor einer Systemzeile desselben Ausloesers).
"""

import pytest

from interview_theater import ablauf, repo


# --- Das Mass --------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "neu schreiben",
    "Neu schreiben",
    "szene 1 neu schreiben",
    "Schreib Szene 2",
    "nochmal",
    "nochmal neu",
    "interview starten",
    "Aufnahme beenden",
])
def test_reine_auftraege_werden_erkannt(text):
    assert ablauf.ist_auftrag(text) is True


@pytest.mark.parametrize("text", [
    "",
    "Wir wollen die Szene lieber am Kiosk haben, nicht auf dem Schulhof.",
    "Warum soll sie ausweichen zur Bushaltestelle oder zum Kiosk?",
    # Auftrag PLUS Regieanweisung: die Anweisung darf nicht verlorengehen,
    # also antwortet der Bot hier sehr wohl (Birk, 05.09. 21:52).
    "Schreib Szene 1. Stell immer nur eine Frage auf einmal. Kein grosses Menu.",
    "Das Setting schlagt mal ein anderes vor.",
])
def test_inhaltliche_nachrichten_bleiben_gespraech(text):
    assert ablauf.ist_auftrag(text) is False


# --- Der Zug ---------------------------------------------------------------


class _KLM:
    def __init__(self):
        self.aufrufe = 0

    def schema(self, *a, **k):
        self.aufrufe += 1
        return {"antwort": "Birk, klar -- Szene 1 neu. Eine Frage dazu: ...?"}


class _TG:
    def __init__(self):
        self.gesendet = []
        self.naechste_message_id = 800

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _E:
    bot_name = "testbot"
    web_url = ""
    erkenner_modell = "m"


def test_neu_schreiben_bekommt_keine_gespraechsantwort(conn):
    """Der 00:30-Fall: kein "klar", keine Rueckfrage, kein Modellaufruf."""
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(conn, 1, 30, "Birk", 0, "text", "neu schreiben", repo._jetzt())
    tg, klm = _TG(), _KLM()
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert tg.gesendet == []
    assert klm.aufrufe == 0, "kein Sprachmodell-Aufruf fuer einen reinen Auftrag"


def test_das_wasserzeichen_rueckt_trotzdem_vor(conn):
    """Sonst liefe der unterdrueckte Zug endlos wieder an."""
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(conn, 1, 30, "Birk", 0, "text", "neu schreiben", repo._jetzt())
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg := _TG(), _KLM(), _E(), 1, offen)

    assert repo.unbeantwortete(conn, 1) == []
    assert tg.gesendet == []


def test_eine_inhaltliche_nachricht_wird_normal_beantwortet(conn):
    """Die Gegenprobe -- der Filter darf das Gespraech nicht abwuergen."""
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(
        conn, 1, 30, "Birk", 0, "text",
        "Das Setting schlagt mal ein anderes vor.", repo._jetzt(),
    )
    tg, klm = _TG(), _KLM()
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert klm.aufrufe == 1
    assert tg.gesendet != []

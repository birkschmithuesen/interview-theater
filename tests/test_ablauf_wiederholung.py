"""Der Wiederholungsfilter (06.09.2026, Birk: "Insgesamt viel zu viel
Wiederholung").

Eine Modellantwort, die zu ueber ``ablauf.WIEDERHOLUNG_ANTEIL`` schon in der
vorigen Bot-Nachricht stand, wird gar nicht erst verschickt -- ersatzlos, mit
einem Vorfall ``wiederholung_verworfen`` fuers Dashboard.

Die Schwelle ist an der Testgruppe gemessen (siehe
``docs/analyse-interaktion-testgruppe-2026-09-05.md``): 4 von 59
Bot-Nachrichten waeren gefallen, darunter beide wortgleich verdoppelten
Notiert-Bloecke -- und keine echte Antwort.
"""

import pytest

from interview_theater import ablauf, repo


# --- Das Mass selbst ------------------------------------------------------


def test_wortgleiche_antwort_ist_eine_wiederholung():
    """Der Live-Fall 21:50/21:52: derselbe Notiert-Block zweimal."""
    text = (
        "Szene 1 - Monolog - Schulhof - Leyla, Cemre, Aylin, Zeynep\n"
        "Szene 2 - Dialog - Kiosk - Leyla, Cemre, Aylin, Zeynep\n"
        "Szene 3 - Rap - Wohnzimmer einer von ihnen - Leyla, Cemre, Aylin"
    )
    assert ablauf.ist_wiederholung(text, text) is True


def test_umformulierte_wiederholung_faellt_auch():
    """Gemessen wird die Wortmenge, nicht die Reihenfolge."""
    vorher = (
        "Leyla koennte wie Interview 1 sprechen, mit dem Bahn-Zitat, weil das "
        "zu ihrer Rolle passt, die von aussen schaut und sich selbst nicht "
        "hineinlaesst."
    )
    nachher = (
        "Weil das zu ihrer Rolle passt, die von aussen schaut und sich selbst "
        "nicht hineinlaesst, koennte Leyla wie Interview 1 sprechen, mit dem "
        "Bahn-Zitat."
    )
    assert ablauf.ist_wiederholung(nachher, vorher) is True


def test_eine_echte_antwort_bleibt_stehen():
    """Der Fall, der NICHT fallen darf: eine Antwort, die den Vorschlag
    aufgreift und etwas Neues hinzufuegt."""
    vorher = "Wollt ihr mit dem Schulhof anfangen oder mit dem Kiosk?"
    nachher = (
        "Gut, Schulhof. Dann faengt Szene 1 am Nachmittag an, Leyla steht "
        "allein mit ihrem Handy, die drei anderen halten Abstand und "
        "beobachten. Die Form waere ein Monolog mit Chor im Hintergrund."
    )
    assert ablauf.ist_wiederholung(nachher, vorher) is False


def test_kurze_zeilen_werden_nicht_geprueft():
    """"Gut, ich hoere zu." teilt seine paar Woerter leicht mit irgendetwas."""
    assert ablauf.ist_wiederholung("Gut, ich hoere zu.", "Gut, ich hoere zu.") is False


def test_ohne_vorige_nachricht_keine_wiederholung():
    assert ablauf.ist_wiederholung("Ein langer eigener Beitrag mit vielen "
                                   "verschiedenen inhaltstragenden Woertern "
                                   "darin, wirklich vielen.", None) is False


def test_schwelle_ist_einstellbar():
    """Konfigurierbar, damit sie an einer neuen Messung nachgezogen werden
    kann, ohne den Code anzufassen."""
    vorher = "Alpha Beta Gamma Delta Epsilon Zeta Theta Jota Kappa Lambda Myon Nyon"
    nachher = vorher + " Xion Omikron Pion Rhoxa Sigma Tauon"
    assert ablauf.ist_wiederholung(nachher, vorher, anteil=0.9) is False
    assert ablauf.ist_wiederholung(nachher, vorher, anteil=0.5) is True


# --- Der Zug ---------------------------------------------------------------


class _KLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = 0

    def schema(self, *a, **k):
        self.aufrufe += 1
        return {"antwort": self.antwort}


class _TG:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.naechste_message_id = 900

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _E:
    bot_name = "testbot"
    web_url = ""
    erkenner_modell = "m"


WIEDERHOLTER_TEXT = (
    "Die Aufteilung passt. Szene 1 spielt auf dem Schulhof am Nachmittag, "
    "Szene 2 am Kiosk gleich danach, Szene 3 abends im Wohnzimmer einer von "
    "ihnen, und Szene 4 ist ein gemeinsamer Chor am naechsten Tag."
)


def _lege_vorige_bot_nachricht_an(conn, text):
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(conn, 1, 10, "testbot", 1, "text", text, repo._jetzt())
    repo.merke_nachricht(conn, 1, 11, "Birk", 0, "text", "und weiter?", repo._jetzt())


def test_wiederholte_antwort_wird_nicht_verschickt(conn):
    """Der Kern: der Bot schweigt, statt sich zu wiederholen."""
    _lege_vorige_bot_nachricht_an(conn, WIEDERHOLTER_TEXT)
    tg, klm = _TG(), _KLM(WIEDERHOLTER_TEXT)
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert WIEDERHOLTER_TEXT not in [t for _, t in tg.gesendet]


def test_verworfene_wiederholung_wird_als_vorfall_vermerkt(conn):
    """Fuers Dashboard: der Filter arbeitet sichtbar, nicht heimlich."""
    _lege_vorige_bot_nachricht_an(conn, WIEDERHOLTER_TEXT)
    tg, klm = _TG(), _KLM(WIEDERHOLTER_TEXT)
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    arten = [
        z["art"] for z in conn.execute("select art from vorfall where chat_id=1")
    ]
    assert "wiederholung_verworfen" in arten
    assert "gespraechszug_fehlgeschlagen" not in arten


def test_neue_antwort_geht_ganz_normal_raus(conn):
    """Die Gegenprobe -- der Filter darf den Regelfall nicht anfassen."""
    _lege_vorige_bot_nachricht_an(conn, WIEDERHOLTER_TEXT)
    neu = (
        "Dann schreibe ich Szene 1 aus. Leyla steht vorn, die drei anderen "
        "weit hinten und halb abgewandt; niemand sagt zuerst etwas."
    )
    tg, klm = _TG(), _KLM(neu)
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert neu in [t for _, t in tg.gesendet]


# --- Die Notiert-Zeile -----------------------------------------------------


def test_gleiche_notiert_meldung_kommt_nicht_zweimal(conn):
    """Der Live-Fall 21:50/21:52: derselbe Szenenfolge-Block wortgleich
    zweimal im Chat (``erkenner._steht_schon_da``)."""
    from interview_theater import erkenner

    meldung = (
        "Notiert:\n"
        "Szene 1 - Monolog - Schulhof - Leyla, Cemre, Aylin, Zeynep\n"
        "Szene 2 - Dialog - Kiosk - Leyla, Cemre, Aylin, Zeynep"
    )
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(conn, 1, 20, "testbot", 1, "text", meldung, repo._jetzt())

    assert erkenner._steht_schon_da(conn, 1, meldung) is True


def test_eine_geaenderte_notiert_meldung_kommt_durch(conn):
    """Wortgleich und nicht aehnlich: "Rahmen: A" und "Rahmen: B" teilen fast
    alle Woerter, sind aber zwei verschiedene Entscheidungen."""
    from interview_theater import erkenner

    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    repo.merke_nachricht(
        conn, 1, 20, "testbot", 1, "text", "Notiert:\nRahmen: Schulhof", repo._jetzt(),
    )

    assert erkenner._steht_schon_da(conn, 1, "Notiert:\nRahmen: Kiosk") is False

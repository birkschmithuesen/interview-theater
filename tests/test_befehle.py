"""Tests fuer die sieben Slash-Befehle (teil-b.md Aufgabe 6, plus /szene).

Kein Netzzugriff: Telegram wird durch eine Attrappe ersetzt, die nur
aufzeichnet, was gesendet wurde. Sechs der sieben Befehle werden hier ohne
jedes LLM-Objekt aufgerufen -- "/stand ruft kein Modell" bleibt damit an den
Tests ablesbar, auch seit behandle() ein optionales ``klm`` fuer /szene
entgegennimmt.
"""

import pytest

from theatersoap import befehle, repo


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []  # Liste von (chat_id, text)

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        return 9001


@pytest.fixture
def tg():
    return TelegramAttrappe()


def test_normale_nachricht_wird_nicht_behandelt(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "ich hol mir kaffee", "Ada")
    assert behandelt is False
    assert tg.gesendet == []


def test_interview_schaltet_modus_an_und_bestaetigt(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/interview", "Ada")
    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is not None
    assert tg.gesendet == [(1, "Ich zeichne jetzt auf.")]


def test_fertig_schaltet_modus_aus_und_bestaetigt(conn, einst, tg):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    behandelt = befehle.behandle(conn, tg, einst, 1, "/fertig", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None
    assert tg.gesendet == [(1, "Aufnahme beendet.")]


def test_kernthema_setzt_arbeitsstand(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/kernthema Ankommen und Bleiben", "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen und Bleiben"
    assert "Ankommen und Bleiben" in tg.gesendet[0][1]


def test_kernthema_ohne_text_fragt_freundlich_nach(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/kernthema", "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert "kernthema" in tg.gesendet[0][1].lower()


def test_kernthema_korrigiert_vorhandenen_wert(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/kernthema Ankommen", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/kernthema Abschied", "Ada")

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Abschied"


def test_stand_ruft_kein_modell_und_zeigt_arbeitsstand(conn, einst, tg):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    behandelt = befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    assert behandelt is True
    text = tg.gesendet[0][1]
    assert "Kernthema: Ankommen" in text
    assert "Maria" in text
    assert "Interviewmodus: an" in text


def test_stand_auf_leerer_datenbank_kracht_nicht(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")
    assert behandelt is True
    assert len(tg.gesendet) == 1


def test_wortlaut_mit_bekanntem_namen_schaltet_an(conn, einst, tg):
    repo.lege_aufnahme_an(conn, 1, 1, "lang", "sprache")
    repo.setze_aufnahme_name(conn, 1, "Maria")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut Maria", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "Maria"


def test_wortlaut_mit_unbekanntem_namen_zaehlt_vorhandene_auf(conn, einst, tg):
    repo.lege_aufnahme_an(conn, 1, 1, "lang", "sprache")
    repo.setze_aufnahme_name(conn, 1, "Maria")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut Peter", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None
    assert "Maria" in tg.gesendet[0][1]


def test_wortlaut_aus_schaltet_modus_aus(conn, einst, tg):
    repo.setze_wortlaut_modus(conn, 1, "*")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut aus", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_wortlaut_ohne_argument_schaltet_alle_an(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "*"


def test_hilfe_nennt_ansprache_interviewmodus_und_befehle(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/hilfe", "Ada")

    assert behandelt is True
    text = tg.gesendet[0][1]
    # Live-Test 1: /hilfe behauptet nichts mehr ueber Reply oder @Erwaehnung
    # (die Gruppe ist ein reines Interface zum Bot, er antwortet auf alles).
    assert "antworte" in text
    assert "Interview" in text
    assert "/stand" in text


def test_unbekannter_befehl_antwortet_freundlich_statt_zu_krachen(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/irgendwas", "Ada")

    assert behandelt is True
    assert len(tg.gesendet) == 1
    assert "kenne ich nicht" in tg.gesendet[0][1]


@pytest.mark.parametrize("befehl", ["/interview", "/fertig", "/stand", "/hilfe"])
def test_befehl_mit_botname_wird_erkannt(conn, einst, tg, befehl):
    text = f"{befehl}@{einst.bot_name}"
    behandelt = befehle.behandle(conn, tg, einst, 1, text, "Ada")
    assert behandelt is True
    assert len(tg.gesendet) == 1


def test_kernthema_mit_botname_und_text_wird_erkannt(conn, einst, tg):
    text = f"/kernthema@{einst.bot_name} Ankommen"
    behandelt = befehle.behandle(conn, tg, einst, 1, text, "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


def test_befehle_liste_enthaelt_alle_sieben_ohne_schraegstrich():
    kommandos = {b["command"] for b in befehle.BEFEHLE_LISTE}
    assert kommandos == {
        "interview", "fertig", "kernthema", "szene", "stand", "wortlaut", "hilfe",
    }

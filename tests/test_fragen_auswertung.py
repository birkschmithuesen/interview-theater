"""Aufgabe 14 (03.10.2026): die Auswertung eigene-vs-KI-Fragen.

``fragen_auswertung.aus_daten`` zaehlt, wie viele der final uebernommenen
Fragen (``arbeitsstand.fragen``) von der Gruppe selbst stammen und wie viele
von der KI (``arbeitsstand.fragen_herkunft_final``, von Aufgabe 13 index- und
laengengleich zu ``fragen`` gebaut). Reine Funktion, kein Modellaufruf, kein
SQL -- ``auswertung`` ist der einzige Aufrufer mit ``repo``-Zugriff."""

import pytest

from interview_theater import db, fragen_auswertung, phasen, repo, web, web_daten
from interview_theater import knoepfe
from interview_theater.knoepfe import texte as knoepfe_texte

from test_fragen_eigene_ki import _TG

CHAT = 1


# ---------------------------------------------------------------------------
# aus_daten: die reine Funktion
# ---------------------------------------------------------------------------


FRAGEN = "Heimat: Q1\nHeimat: Q2\nArbeit: Q3"
HERKUNFT = "eigen,ki,ki"


def test_aus_daten_zaehlt_eigen_und_ki_je_begriff_und_gesamt():
    ergebnis = fragen_auswertung.aus_daten(FRAGEN, HERKUNFT)
    assert ergebnis == {
        "gesamt": {"eigen": 1, "ki": 2},
        "je_begriff": {
            "Heimat": {"eigen": 1, "ki": 1},
            "Arbeit": {"eigen": 0, "ki": 1},
        },
    }


def test_mutation_vertauschte_herkunft_aendert_das_ergebnis():
    """Das Karten-Mandat: dieselbe Fixture, jeder ``eigen``/``ki``-Wert
    vertauscht -- das Ergebnis MUSS sich unterscheiden, sonst zaehlt die
    Funktion gar nicht wirklich nach der Herkunft."""
    herkunft_vertauscht = (
        HERKUNFT.replace("eigen", "X").replace("ki", "eigen").replace("X", "ki")
    )
    assert herkunft_vertauscht == "ki,eigen,eigen"

    original = fragen_auswertung.aus_daten(FRAGEN, HERKUNFT)
    vertauscht = fragen_auswertung.aus_daten(FRAGEN, herkunft_vertauscht)

    assert original != vertauscht
    # Das Beleg-Detail aus der Karte: mit der vertauschten Herkunft ist der
    # Original-Erwartungswert aus dem ersten Test FALSCH -- die Zahlen haben
    # sich sichtbar gedreht (1/2 -> 2/1 gesamt, Arbeit eigen/ki getauscht).
    assert vertauscht == {
        "gesamt": {"eigen": 2, "ki": 1},
        "je_begriff": {
            "Heimat": {"eigen": 1, "ki": 1},
            "Arbeit": {"eigen": 1, "ki": 0},
        },
    }
    erwartet_original = {
        "gesamt": {"eigen": 1, "ki": 2},
        "je_begriff": {
            "Heimat": {"eigen": 1, "ki": 1},
            "Arbeit": {"eigen": 0, "ki": 1},
        },
    }
    # Dieselbe Assertion wie im ersten Test, aber gegen die vertauschte
    # Fixture gerechnet -- sie schlaegt fehl, das IST der rote Beleg.
    assert vertauscht != erwartet_original


def test_aus_daten_ohne_jede_herkunft_ist_leer_aber_kein_fehler():
    assert fragen_auswertung.aus_daten(None, None) == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }


def test_aus_daten_mit_fragen_aber_ohne_herkunft_ist_leer():
    """Der klassische Ablauf: ``fragen`` steht, ``fragen_herkunft_final``
    gibt es nicht (kein A/B-Vergleich lief). Keine Zeile zaehlt."""
    assert fragen_auswertung.aus_daten("Heimat: Q1\nHeimat: Q2", None) == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }


def test_aus_daten_leere_herkunftskette_passend_zu_fragen_ist_leer():
    """Wie Aufgabe 13 es ablegt, wenn der A/B-Vergleich lief, aber jede
    Position leer blieb -- darf heute nicht vorkommen (jede Position ist
    immer eigen/ki, sobald die Kette ueberhaupt befuellt wird), ist aber die
    robuste Lesart derselben Regel wie ``fragen_herkunft_final=None``."""
    assert fragen_auswertung.aus_daten("Heimat: Q1\nHeimat: Q2", ",") == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }


def test_aus_daten_zu_kurze_herkunftskette_laesst_rest_unberuecksichtigt():
    """Ein Index ausserhalb der Kette (kuerzer als ``fragen``) zaehlt
    nirgends mit -- weder eigen noch ki, keine dritte Kategorie."""
    ergebnis = fragen_auswertung.aus_daten(FRAGEN, "eigen")
    assert ergebnis == {
        "gesamt": {"eigen": 1, "ki": 0},
        "je_begriff": {"Heimat": {"eigen": 1, "ki": 0}},
    }


def test_aus_daten_zeile_ohne_begriffspraefix_zaehlt_nur_gesamt():
    """Eine Zeile ohne erkennbares ``Begriff:`` (die Pruefung aus
    ``knoepfe.fragen.fragenliste``: nicht-leerer Begriff bis 30 Zeichen,
    nicht-leerer Rest) zaehlt in ``gesamt``, aber in kein ``je_begriff``-Fach."""
    ergebnis = fragen_auswertung.aus_daten("Eine Frage ohne Doppelpunkt", "eigen")
    assert ergebnis == {"gesamt": {"eigen": 1, "ki": 0}, "je_begriff": {}}


# ---------------------------------------------------------------------------
# auswertung(): der Weg des Bots ueber repo
# ---------------------------------------------------------------------------


def test_auswertung_liest_ueber_repo(conn):
    repo.setze_arbeitsstand(conn, CHAT, "fragen", FRAGEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft_final", HERKUNFT)
    assert fragen_auswertung.auswertung(conn, CHAT) == fragen_auswertung.aus_daten(
        FRAGEN, HERKUNFT,
    )


def test_auswertung_frische_gruppe_ohne_arbeitsstand_zeile(conn):
    """``repo.hole_arbeitsstand`` liefert ``None`` fuer eine frische Gruppe
    ohne jede Festlegung -- kein Absturz, dasselbe leere Ergebnis."""
    assert repo.hole_arbeitsstand(conn, CHAT) is None
    assert fragen_auswertung.auswertung(conn, CHAT) == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }


def test_auswertung_mit_arbeitsstand_aber_ohne_ab_vergleich(conn):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    assert fragen_auswertung.auswertung(conn, CHAT) == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }


# ---------------------------------------------------------------------------
# Rundreise durch den echten Abschluss (``knoepfe.fragen._schliesse_fragen_ab``)
# ---------------------------------------------------------------------------


@pytest.fixture
def auftraege(monkeypatch):
    from interview_theater import ablauf

    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None, arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def test_auswertung_passt_zum_echten_abschluss_der_fragenrunde(conn, einst, auftraege):
    """End-to-End durch den echten Weg: ``fragen_herkunft`` -> Annehmen/
    Verwerfen -> ``_schliesse_fragen_ab`` -> ``fragen_herkunft_final`` ->
    ``fragen_auswertung.auswertung`` liest denselben Stand, den der Chat
    gerade bestaetigt hat."""
    tg = _TG()
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl",
        "Heimat: Q1 eigen.\nHeimat: Q2 ki.\nStreit: Q3 ki.\nStreit: Q4 eigen.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki,ki,eigen")
    phasen.setze(conn, CHAT, 2, "befehl")

    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")   # eigen, angenommen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "nein")  # ki, verworfen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 3, "ja")   # ki, angenommen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 4, "ja")   # eigen, angenommen

    ergebnis = fragen_auswertung.auswertung(conn, CHAT)
    assert ergebnis == {
        "gesamt": {"eigen": 2, "ki": 1},
        "je_begriff": {
            "Heimat": {"eigen": 1, "ki": 0},
            "Streit": {"eigen": 1, "ki": 1},
        },
    }

    # Die Chat-Abschlussnachricht traegt dieselbe Auswertung (sichtbarer Teil
    # dieser Aufgabe) -- als String-Enthaltensein, nicht byte-exakt, weil der
    # genaue Wortlaut Sache von ``knoepfe/texte.py`` ist.
    text = tg.texte[-1]
    assert knoepfe_texte.T._TEXT_FRAGEN_AUSWERTUNG.format(ki=1, eigen=2) in text
    assert "Streit: 1 eigene, 1 KI" in text
    assert "Heimat: 1 eigene, 0 KI" in text


# ---------------------------------------------------------------------------
# Web: dieselbe Zeile auf der Gruppenseite und dem Dashboard
# ---------------------------------------------------------------------------


def test_gruppenseite_zeigt_die_auswertungszeile_wenn_ab_vergleich_lief(conn):
    repo.setze_arbeitsstand(conn, CHAT, "fragen", FRAGEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft_final", HERKUNFT)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    daten = web_daten.gruppe_nach_token(conn, token)
    seite = web.gruppe_html(daten)
    assert "Fragen behalten: 1 eigene, 2 KI" in seite


def test_gruppenseite_zeigt_keine_auswertungszeile_ohne_ab_vergleich(conn):
    """Kein A/B-Vergleich gelaufen -- keine Zeile "0 eigene, 0 KI"."""
    token = repo.stelle_web_token_sicher(conn, CHAT)
    daten = web_daten.gruppe_nach_token(conn, token)
    seite = web.gruppe_html(daten)
    assert "Fragen behalten" not in seite


def test_dashboard_zeigt_die_auswertungszeile_wenn_ab_vergleich_lief(conn):
    repo.setze_arbeitsstand(conn, CHAT, "fragen", FRAGEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft_final", HERKUNFT)
    daten = web_daten.dashboard(conn)
    seite = web.dashboard_html(daten)
    assert "Fragen behalten: 1 eigene, 2 KI" in seite


def test_dashboard_zeigt_keine_auswertungszeile_ohne_ab_vergleich(conn):
    daten = web_daten.dashboard(conn)
    seite = web.dashboard_html(daten)
    assert "Fragen behalten" not in seite


def test_auswertung_klassischer_ablauf_bleibt_leer(conn, einst, auftraege):
    """Ohne ``fragen_herkunft`` (klassischer Ablauf, kein A/B-Vergleich) ist
    die Auswertung nach Abschluss der Fragenrunde weiterhin 0/0 -- und die
    Abschlussnachricht traegt KEINE Auswertungszeile."""
    tg = _TG()
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: Q1.\nStreit: Q2.",
    )
    phasen.setze(conn, CHAT, 2, "befehl")

    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "ja")

    assert fragen_auswertung.auswertung(conn, CHAT) == {
        "gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {},
    }
    text = tg.texte[-1]
    assert text == "Notiert, eure 2 Fragen:\n1. Heimat: Q1.\n2. Streit: Q2."

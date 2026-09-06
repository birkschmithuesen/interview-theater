"""Die weichen Fragefassungen (06.09.2026, 10:18, Birk).

Der Anlass steht im Wortlaut: eine sensible Frage bekommt keine Einleitung
davorgeklebt, sondern wird zu EINEM weichen Gespraechsstueck umformuliert --
zwei bis drei Saetze, Du-Form, sprechbar, im Ton einer 15- bis 18-Jaehrigen,
die eine fremde Person anspricht. Der KERN bleibt daneben stehen (das ist,
worueber die Gruppe entschieden hat); im Leitfaden steht er als
``(Kern: ...)`` unter der weichen Fassung.

Und eine Regel, die sich nicht von selbst versteht: der Leerfall-Satz
("Keine der Fragen braucht eine besondere Einleitung.") ist eine Antwort an
die Gruppe im Chat -- er darf NIE im Leitfaden landen.
"""

import pytest

from interview_theater import ablauf, knoepfe, leitfaden, phasen, repo, vorschlag

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


WEICH = (
    "1 — Wir fragen alle danach, und du musst nichts sagen, was du nicht "
    "willst. Woher kommst du eigentlich, und wie ist das fuer dich?"
)


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung, klm=None):
    knoepfe.behandle(conn, tg, klm, einst, _druck(_knopf(tg, beschriftung)))


def _mit_fragen(conn, wert="Woher kommst du?\nWas machst du gern?"):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", wert)


# --- Der Marker -----------------------------------------------------------


def test_der_marker_heisst_fragen_weich():
    """Im Text zwei Woerter, im Code eine Art -- und derselbe Name wie die
    Spalte."""
    assert vorschlag.marker("fragen_weich") == "VORSCHLAG FRAGEN WEICH:"


def test_der_block_wird_als_eigene_art_gelesen():
    text = f"Zwei sind heikel.\n\nVORSCHLAG FRAGEN WEICH:\n{WEICH}"

    assert vorschlag.lies(text, "fragen_weich").startswith("1 — Wir fragen")


def test_fragen_weich_wird_nicht_als_frageliste_verbucht():
    """``FRAGEN WEICH`` steht in der Alternation vor ``FRAGEN`` -- sonst
    ueberschriebe eine weiche Fassung die Frageliste selbst."""
    text = f"VORSCHLAG FRAGEN WEICH:\n{WEICH}"

    assert vorschlag.lies(text, "fragen") is None


# --- Speicherung ----------------------------------------------------------


def test_die_weichen_fassungen_landen_in_ihrer_eigenen_spalte(
    conn, tg, einst, auftraege,
):
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, f"Eine ist heikel.\n\nVORSCHLAG FRAGEN WEICH:\n{WEICH}"
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen_weich"].startswith("1 — Wir fragen alle danach")
    assert stand["fragen"] == "Woher kommst du?\nWas machst du gern?", (
        "der Kern bleibt unangetastet"
    )


def test_nach_den_weichen_fassungen_kommt_die_eroeffnung_von_selbst(
    conn, tg, einst, auftraege,
):
    """Dieselbe Kette wie vorher -- die Gruppe erlebt die Verfeinerung als
    einen Weg, nicht als drei Aufgaben."""
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, f"VORSCHLAG FRAGEN WEICH:\n{WEICH}"
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert len(auftraege) == 1
    assert "VORSCHLAG EROEFFNUNG:" in auftraege[0]


def test_die_pruefung_verlangt_weiche_fassungen_statt_einleitungen(
    conn, tg, einst, auftraege,
):
    _mit_fragen(conn)

    knoepfe.starte_sensibilitaetspruefung(conn, tg, object(), einst, 1)

    anweisung = auftraege[0]
    assert "VORSCHLAG FRAGEN WEICH:" in anweisung
    assert "Du-Form" in anweisung or "Du-Form" in anweisung
    assert "nicht noch einmal unveraendert ab" in anweisung, "Anti-Nachplapper"


def test_weiche_fassungen_machen_phase_3_moeglich(conn):
    """Sie treten an die Stelle der Einleitungen: eine Gruppe, die weiche
    Fassungen hat, braucht keine Einleitungen mehr."""
    _mit_fragen(conn)
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", WEICH)
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo, wir ...")
    repo.setze_arbeitsstand(conn, 1, "interview_abschluss", "Danke dir.")

    assert phasen.voraussetzungen(conn, 1)[3] is True


# --- Der Leitfaden --------------------------------------------------------


def _vollstaendig(conn):
    repo.setze_arbeitsstand(conn, 1, "fragen", "Woher kommst du?\nWas machst du gern?")
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", WEICH)
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo, wir sind ...")
    repo.setze_arbeitsstand(conn, 1, "interview_abschluss", "Danke dir.")


def test_der_leitfaden_zeigt_die_weiche_fassung_mit_kern_zeile(conn):
    _vollstaendig(conn)

    text = leitfaden.baue(conn, 1)

    assert "1. Wir fragen alle danach" in text
    assert "(Kern: Woher kommst du?)" in text


def test_die_weiche_fassung_ersetzt_die_frage_statt_sie_zu_ergaenzen(conn):
    """Sie steht an der Stelle der Frage -- sonst laese die Interviewerin
    zweimal dasselbe und wuesste nicht, was sie sagen soll."""
    _vollstaendig(conn)

    text = leitfaden.baue(conn, 1)

    assert "1. Woher kommst du?" not in text


def test_fragen_ohne_weiche_fassung_stehen_wie_sie_sind(conn):
    """Eine nicht-sensible Frage braucht keine Umformulierung."""
    _vollstaendig(conn)

    text = leitfaden.baue(conn, 1)

    assert "2. Was machst du gern?" in text
    assert "(Kern: Was machst du gern?)" not in text


def test_ohne_weiche_fassungen_bleibt_der_leitfaden_wie_er_war(conn):
    """Der alte Weg (Einleitungen) laeuft unveraendert weiter -- eine
    Gruppe mitten in der Arbeit verliert nichts."""
    repo.setze_arbeitsstand(conn, 1, "fragen", "Woher kommst du?")
    repo.setze_arbeitsstand(
        conn, 1, "frage_einleitungen", "1 — Du musst nicht antworten."
    )

    text = leitfaden.baue(conn, 1)

    assert "1. Woher kommst du?" in text
    assert "↳ vorher sagen: Du musst nicht antworten." in text


def test_der_leerfall_satz_steht_nie_im_leitfaden(conn):
    """"Keine der Fragen braucht eine besondere Einleitung." ist eine
    Rueckmeldung an die Gruppe im Chat, kein Eintrag -- der Leitfaden ist
    der Text, mit dem sie vor einer fremden Person steht."""
    leer = "Keine der Fragen braucht eine besondere Einleitung."
    repo.setze_arbeitsstand(conn, 1, "fragen", "Woher kommst du?")
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", leer)
    repo.setze_arbeitsstand(conn, 1, "frage_einleitungen", leer)

    text = leitfaden.baue(conn, 1)

    assert "Keine der Fragen" not in text
    assert "1. Woher kommst du?" in text


def test_der_leerfall_kommt_trotzdem_als_chat_rueckmeldung(
    conn, tg, einst, auftraege,
):
    """Im Chat steht der Satz sehr wohl -- er ist die Antwort auf "habt ihr
    heikle Fragen dabei?"."""
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG FRAGEN WEICH:\nKeine der Fragen braucht eine besondere "
        "Einleitung.",
    )

    assert any("Keine der Fragen" in t for _, t in tg.gesendet)


# --- /stand und Web -------------------------------------------------------


def test_stand_zeigt_die_weiche_fassung(conn):
    from interview_theater import phasentexte

    _vollstaendig(conn)

    zeilen = phasentexte.standzeilen(conn, 1, 2)

    assert any("Wir fragen alle danach" in z for z in zeilen), zeilen


def test_die_gruppenseite_zeigt_die_weiche_fassung(conn):
    from interview_theater import web

    html = web._leitfaden_html(
        {
            "fragen": "Woher kommst du?",
            "fragen_weich": WEICH,
            "interview_eroeffnung": "Hallo, wir sind ...",
            "interview_abschluss": "Danke dir.",
        }
    )

    assert "Wir fragen alle danach" in html
    assert "Kern: Woher kommst du?" in html

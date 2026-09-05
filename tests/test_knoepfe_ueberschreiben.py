"""Der Live-Schaden vom 05.09.2026, 21:50 -- als Test (06.09.2026).

Was passierte: in Phase 6 bot der Bot drei Szenenbilder als
``VORSCHLAG RAHMEN:`` an. Die Grundleiste darunter trug den ersten davon als
speicherbaren Wert, obwohl ``arbeitsstand.rahmen`` seit 21:37 gesetzt war
("Vier Freundinnen leben im Nordkiez in Dortmund ..."). Ein Druck auf
"Gefaellt uns, weiter" ersetzte ihn still durch "Leyla checkt ihr Handy auf
dem Schulhof, die anderen beobachten sie von weitem" -- Journal-Zeile j5 der
Testgruppe ist der einzige Beleg dafuer.

Zwei Riegel, hier je einzeln geprueft:

1. Die Grundleiste traegt einen Auswahl-Vorschlag nur, wenn seine Art die
   gerade OFFENE ist (``knoepfe.offene_art``).
2. Auch wenn ein Speicher-Knopf mit einem anderen Wert doch gedrueckt wird,
   ueberschreibt er ein gesetztes Feld nicht, solange keine Aenderung offen
   ist (``knoepfe._ist_bestaetigung``).
"""

import pytest

from interview_theater import knoepfe, phasen, repo, vorschlag

from tests.test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


RAHMEN_21_37 = (
    "Vier Freundinnen leben im Nordkiez in Dortmund. Eine ist ungluecklich "
    "verliebt in einen rassistischen Typen."
)
SZENENBILD_21_50 = "Leyla checkt ihr Handy auf dem Schulhof, die anderen beobachten sie von weitem"

VORSCHLAGSTEXT = (
    "Jetzt zur Szenenfolge. Wie wollt ihr anfangen?\n\n"
    f"{vorschlag.marker('rahmen')}\n"
    f"{SZENENBILD_21_50}\n"
    "drei Tage spaeter am Kiosk, die vier treffen sich, aber Leyla sagt nichts\n"
    "abends im Wohnzimmer einer von ihnen, die Wahrheit kommt raus -- Streit"
)


def _stelle_21_50_her(conn):
    """Der Zustand der Testgruppe um 21:50: Phase 6, Rahmen gesetzt, keine
    Aenderung offen."""
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", RAHMEN_21_37)
    repo.setze_arbeitsstand(conn, 1, "aenderung_offen", None)


def test_szenenbild_vorschlag_traegt_keine_grundleiste_fuer_den_rahmen(conn, tg):
    """Riegel 1: ``rahmen`` ist in Phase 6 nicht die offene Art -- also darf
    unter dem Szenenbild-Vorschlag keine Speicher-Leiste stehen."""
    _stelle_21_50_her(conn)

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAGSTEXT)

    arten = {
        repo.hole_knopf(conn, int(daten.split(":")[1]))["art"]
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
    }
    assert knoepfe.ART_SPEICHERN not in arten
    assert knoepfe.ART_ANDERS not in arten


def test_gefaellt_uns_weiter_ueberschreibt_den_gesetzten_rahmen_nicht(conn, tg):
    """Riegel 2: selbst mit einem Speicher-Knopf in der Hand bleibt der
    Rahmen von 21:37 stehen -- und es gibt keinen zweiten Journal-Eintrag."""
    _stelle_21_50_her(conn)
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN,
        f"rahmen{knoepfe.TRENNER}{SZENENBILD_21_50}",
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["rahmen"] == RAHMEN_21_37
    assert not [
        z for z in repo.journal(conn, 1) if str(z["text"]).startswith("Rahmen:")
    ]
    assert any("Steht schon so" in text for _, text in tg.gesendet)


def test_ueberschreiben_wird_als_vorfall_vermerkt(conn, tg):
    """Fuers Dashboard: der verhinderte Verlust ist sichtbar, nicht still."""
    _stelle_21_50_her(conn)
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN,
        f"rahmen{knoepfe.TRENNER}{SZENENBILD_21_50}",
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))

    arten = [
        z["art"] for z in conn.execute(
            "select art from vorfall where chat_id=1"
        ).fetchall()
    ]
    assert "ueberschreiben_verhindert" in arten


def test_nach_passt_aber_anders_darf_ueberschrieben_werden(conn, tg):
    """Die Gegenprobe: hat die Gruppe um eine Aenderung gebeten
    (``aenderung_offen``), ist Ueberschreiben genau das Gewollte."""
    _stelle_21_50_her(conn)
    repo.setze_arbeitsstand(conn, 1, "aenderung_offen", "rahmen")
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN,
        f"rahmen{knoepfe.TRENNER}{SZENENBILD_21_50}",
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == SZENENBILD_21_50


def test_leeres_feld_wird_ganz_normal_gespeichert(conn, tg):
    """Und der Regelfall bleibt unberuehrt: ist nichts gesetzt, speichert der
    Knopf beim ERSTEN Mal, ohne Rueckfrage."""
    phasen.setze(conn, 1, 4, "befehl")
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN,
        f"rahmen{knoepfe.TRENNER}{SZENENBILD_21_50}",
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == SZENENBILD_21_50

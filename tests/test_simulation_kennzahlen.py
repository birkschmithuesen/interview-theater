"""Die mechanischen Kennzahlen an einem synthetischen Transkript -- ohne Netz.

Synthetisch, damit jede Zahl von Hand nachzaehlbar ist: nach einer
Prompt-Aenderung muss man dem Bericht glauben koennen, ohne den Lauf
nachzulesen.
"""

import pytest

from interview_theater import repo
from simulation import kennzahlen
from simulation.kennzahlen import Beitrag, Zug


def beitrag(kennung, text, absender="Ines", schritt="fragen"):
    return Beitrag(kennung=kennung, schritt=schritt, absender=absender,
                   profil="skeptisch", text=text)


def zug(schritt, beitraege, bot, marke=""):
    return Zug(schritt=schritt, beitraege=beitraege, bot=bot, marke=marke)


@pytest.fixture
def protokoll():
    return [
        zug("fragen",
            [beitrag("S1", "Wir nehmen die sechs Fragen so, wie du sie hast.")],
            [f"{kennzahlen.NOTIERT}\nFragen: Koffer: Was war drin?"]),
        zug("fragen",
            [beitrag("S2", "Nein, die zweite Frage ist zu privat, nimm sie raus.")],
            ["Ich habe das korrigiert und im Arbeitsstand vermerkt."]),
        zug("kernthema",
            [beitrag("S3", "Das Kernthema ist das Warten zwischen zwei Laendern.")],
            ["Ines: Das Kernthema ist das Warten zwischen zwei Laendern."]),
    ]


def test_notiert_praefix_kommt_aus_dem_erkenner():
    assert kennzahlen.NOTIERT.startswith("Notiert")


def test_laenge_bot_ist_der_median(protokoll):
    laengen = sorted(len(t) for z in protokoll for t in z.bot)
    assert kennzahlen.laenge_bot(protokoll) == laengen[1]


def test_leeres_protokoll_ergibt_null_laenge():
    assert kennzahlen.laenge_bot([]) == 0


def test_echo_findet_die_zurueckgespiegelte_antwort(protokoll):
    """Die dritte Antwort ist Zug 3 wortgleich, mit 'Ines:' davor -- genau der
    Live-Fall vom 04.09.2026."""
    treffer = kennzahlen.echos(protokoll)
    assert len(treffer) == 1
    assert treffer[0].startswith("Ines:")


def test_namensanrede_zaehlt_nur_die_beteiligten_namen(protokoll):
    assert len(kennzahlen.namensanreden(protokoll, ["Ines", "Jo"])) == 1
    assert kennzahlen.namensanreden(protokoll, ["Marlen"]) == []


def test_namensanrede_erkennt_auch_hat_recht():
    protokoll = [zug("fragen", [beitrag("S1", "doch")], ["Jo hat recht damit."])]
    assert len(kennzahlen.namensanreden(protokoll, ["Jo"])) == 1


def test_behauptete_schreibvorgaenge_nur_ohne_notiert_zeile(protokoll):
    """Zug 1 behauptet nichts und notiert; Zug 2 behauptet 'korrigiert' und
    'im Arbeitsstand', ohne dass der Erkenner etwas geschrieben hat."""
    treffer = kennzahlen.behauptete_schreibvorgaenge(protokoll)
    assert len(treffer) == 1
    assert "korrigiert" in treffer[0]


def test_die_notiert_zeile_selbst_gilt_nicht_als_behauptung():
    protokoll = [zug("fragen", [beitrag("S1", "ja")],
                     [f"{kennzahlen.NOTIERT}\nBegriffe: Koffer"])]
    assert kennzahlen.behauptete_schreibvorgaenge(protokoll) == []


def test_rueckfragen_vor_szene_endet_am_auftrag():
    protokoll = [
        zug("szene", [beitrag("S1", "Am Bahnhof.", schritt="szene")],
            ["Wo genau soll sie spielen?", "Und wer kommt vor?"]),
        zug("szene", [], ["Szene 1: Am Bahnhof"], marke="szene_aufruf"),
        zug("szene", [], ["Passt das so?"]),
    ]
    assert len(kennzahlen.rueckfragen_vor_szene(protokoll)) == 2


def test_rueckfragen_zaehlen_nur_im_szenen_schritt(protokoll):
    assert kennzahlen.rueckfragen_vor_szene(protokoll) == []


def test_zustimmungen_zaehlen_die_markierten(protokoll):
    gespeichert, gesamt = kennzahlen.zustimmungen(protokoll, {"S1", "S3"})
    assert (gespeichert, gesamt) == (1, 2)


def test_zustimmungen_ohne_markierung_sind_null(protokoll):
    assert kennzahlen.zustimmungen(protokoll, set()) == (0, 0)


# --- aus der Datenbank ----------------------------------------------------


def test_arbeitsstand_vollstaendig_zaehlt_je_feld(conn):
    stand = kennzahlen.arbeitsstand_vollstaendig(conn, 1)
    assert set(stand) == {"begriffe", "fragen", "kernthema", "figuren_3",
                          "format"}
    assert sum(stand.values()) == 0

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    for name in ("Meryem", "Ferzan", "Aynur"):
        repo.setze_figur(conn, 1, name, "eine Frau")
    stand = kennzahlen.arbeitsstand_vollstaendig(conn, 1)
    assert stand["begriffe"] == 1
    assert stand["format"] == 1
    assert stand["figuren_3"] == 1
    assert stand["fragen"] == 0


class _Interview:
    def __init__(self, zitate):
        self.zitate_soll = zitate


def test_zitatlage_findet_die_sollzitate(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "text")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Meryem erzaehlt vom Koffer",
        [{"thema": "Koffer", "beleg_zitat": "Ein Koffer und eine Tuete mit Brot",
          "zitat_geprueft": 1},
         {"thema": "Warten", "beleg_zitat": None, "zitat_geprueft": 0}],
    )
    gezogen = [_Interview(["Ein Koffer und eine Tuete mit Brot", "steht nicht da"])]
    lage = kennzahlen.zitatlage(conn, 1, gezogen)
    assert lage["verdichtungen"] == 1
    assert lage["themen"] == 2
    assert lage["zitate_geprueft"] == 1
    assert lage["zitate_soll_gefunden"] == 1
    assert lage["zitate_soll_vermisst"] == ["steht nicht da"]


def test_zitatlage_vergleicht_ueber_zeilenumbrueche_hinweg(conn):
    """Die Soll-Zitate stehen in den Dateien umgebrochen, die Belegzitate
    kommen einzeilig aus dem Modell -- ohne die Normalisierung aus
    ``zitat.py`` waere diese Kennzahl dauerhaft null."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 11, "lang", "text")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "z",
        [{"thema": "T", "beleg_zitat": "Ein Koffer und eine Tuete mit Brot",
          "zitat_geprueft": 1}],
    )
    gezogen = [_Interview(["Ein Koffer und\neine Tuete   mit Brot"])]
    assert kennzahlen.zitatlage(conn, 1, gezogen)["zitate_soll_gefunden"] == 1


class _E:
    llm_modell = "moonshotai/Kimi-K2.6"
    erkenner_modell = "google/gemma-4-31B-it"


def test_kosten_sind_bot_kosten_je_art(conn):
    """Was hier steht, ist genau das, was ein echter Workshoptag an
    Infomaniak zahlen wuerde -- die Simulationsseite laeuft ueber ein
    Abonnement und steht gar nicht mehr in dieser Tabelle."""
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    for art in ("gespraech", "erkenner"):
        repo.merke_aufruf(conn, 1, art, "A", 0, 1_000_000, 1_000_000, "stop", 10, 1)
    zahlen = kennzahlen.kosten(conn, _E(), PREISE_CHF_JE_MIO_TOKEN)
    # Kimi: 0,60 ein + 3,00 aus je Mio -> 3,60; gemma: 0,20 + 0,40 -> 0,60
    assert zahlen["chf_je_art"]["gespraech"] == pytest.approx(3.6)
    assert zahlen["chf_je_art"]["erkenner"] == pytest.approx(0.6)
    assert zahlen["chf_bot"] == pytest.approx(4.2)
    assert zahlen["aufrufe"] == 2


def test_kosten_ohne_hinterlegten_preis_bleiben_null(conn):
    repo.merke_aufruf(conn, 1, "gespraech", "A", 0, 1_000, 1_000, "stop", 10, 1)
    zahlen = kennzahlen.kosten(conn, _E(), {})
    assert zahlen["chf_bot"] == 0
    assert zahlen["token_ein"] == 1_000


def test_sammle_liefert_alle_schluessel_des_berichts(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {"begriffe": True}, _E(),
        PREISE_CHF_JE_MIO_TOKEN, 12.3, notausgaenge=1,
    )
    for schluessel in ("phase_erreicht", "arbeitsstand_vollstaendig", "echo",
                       "verdichtungen", "laenge_bot", "chf_bot", "sim_aufrufe",
                       "interviews_soll", "notausgaenge", "dauer_s"):
        assert schluessel in zahlen
    assert zahlen["notausgaenge"] == 1
    assert zahlen["schritte_gescheitert"] == []

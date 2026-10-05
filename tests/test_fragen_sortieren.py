"""Phase 2, Padua 05.10.2026: die Fragen auf einmal sortieren (CoThinker-
Liste) statt nur Karte fuer Karte -- ``repo.setze_fragen_entscheidung``,
"schaerfen" als offener Zustand, ``knoepfe.fragen.sortierung_abschliessen``
und der versteckte Befehl ``/sortiert``."""

import pytest

from interview_theater import repo, roadmap, workshop
from interview_theater.knoepfe import fragen
from interview_theater.knoepfe.texte import T

from test_knoepfe import TelegramAttrappe

CHAT = 1
FUENF = "A: eins?\nA: zwei?\nA: drei?\nA: vier?\nA: fuenf?"


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    from interview_theater import ablauf

    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def _feld(conn, feld):
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    return zeile[feld] if zeile is not None else None


def _auswahl(conn, wert=FUENF, begriffe="A"):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", begriffe)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", wert)


# --- repo.setze_fragen_entscheidung -----------------------------------------


def test_setze_fragen_entscheidung_fuellt_auf(conn):
    _auswahl(conn)
    assert repo.setze_fragen_entscheidung(conn, CHAT, 3, "nein") is True
    assert _feld(conn, "fragen_entschieden") == ",,nein"
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "schaerfen") is True
    assert _feld(conn, "fragen_entschieden") == "schaerfen,,nein"
    assert repo.setze_fragen_entscheidung(conn, CHAT, 3, "") is True
    assert _feld(conn, "fragen_entschieden") == "schaerfen,,"


@pytest.mark.parametrize("nummer,wert", [
    (0, "ja"), (6, "ja"), (-1, "ja"), (2, "vielleicht"), (2, "Ja"), (2, None),
])
def test_setze_fragen_entscheidung_lehnt_ab(conn, nummer, wert):
    _auswahl(conn)
    repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja")
    assert repo.setze_fragen_entscheidung(conn, CHAT, nummer, wert) is False
    assert _feld(conn, "fragen_entschieden") == "ja"


def test_setze_fragen_entscheidung_ohne_arbeitsstand(conn):
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja") is False
    assert repo.hole_arbeitsstand(conn, CHAT) is None


# --- "schaerfen" ist offen ---------------------------------------------------


def test_schaerfen_gilt_als_offen(conn):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,schaerfen,nein")
    assert fragen._naechste_offene(conn, CHAT, 5) == 2
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")
    assert fragen._aktuelle_offene_nummer(conn, CHAT) == 2
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "3")
    assert fragen._aktuelle_offene_nummer(conn, CHAT) is None


# --- sortierung_abschliessen -------------------------------------------------


def test_sortierung_mit_schaerfen_zeigt_die_karte(conn, tg, auftraege):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,,nein,schaerfen,")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen_entschieden") == "ja,ja,nein,schaerfen,ja"
    assert _feld(conn, "fragen_aktuell") == "4"
    texte = [g[1] for g in tg.gesendet]
    assert any("vier?" in t for t in texte)
    assert texte[-1] == T._TEXT_FRAGE_WAS_AENDERN
    assert _feld(conn, "fragen") is None

    fragen.entscheide(conn, tg, None, None, CHAT, 4, "ja")
    fertig = _feld(conn, "fragen")
    assert "eins?" in fertig and "zwei?" in fertig and "vier?" in fertig
    assert "fuenf?" in fertig and "drei?" not in fertig


def test_sortierung_ohne_schaerfen_schliesst_direkt_ab(conn, tg, auftraege):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    fertig = _feld(conn, "fragen")
    assert fertig and "eins?" in fertig and "zwei?" not in fertig and "fuenf?" in fertig


def test_sortierung_ohne_auswahl(conn, tg):
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert [g[1] for g in tg.gesendet] == [T._TEXT_FRAGEN_KEINE_AUSWAHL]


def test_befehl_sortiert(conn, tg, einst, auftraege):
    from interview_theater import befehle

    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "nein")
    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)
    fertig = _feld(conn, "fragen")
    assert fertig and "drei?" in fertig and "eins?" not in fertig


# --- roadmap.fragenuebersicht: Begriff mit Doppelpunkt ------------------------


def test_fragenuebersicht_begriff_mit_doppelpunkt():
    stand = {"begriffe": "EVENTO: dall’esterno all’interno",
             "fragen": None,
             "fragen_eigene_vorschlag":
                 "EVENTO: dall'esterno all'interno: Dov'eri l'11 settembre 2001?",
             "fragen_herkunft_final": None}
    erg = roadmap.fragenuebersicht(stand)
    assert erg == [{"begriff": "EVENTO: dall’esterno all’interno",
                    "fragen": ["Dov'eri l'11 settembre 2001?"]}]


def test_fragenuebersicht_trennt_zusammengeklebte_fragen():
    # Live G1, 05.10.2026: eine Zeile in ``fragen`` trug vier Fragen.
    stand = {"begriffe": "casa",
             "fragen": "casa: Cosa significa sentirsi a casa? Cosa rende casa "
                       "effettivamente casa? Ti piacerebbe cambiare casa? Perché?",
             "fragen_eigene_vorschlag": None,
             "fragen_herkunft_final": None}
    erg = roadmap.fragenuebersicht(stand)
    assert erg[0]["fragen"] == [
        "Cosa significa sentirsi a casa?",
        "Cosa rende casa effettivamente casa?",
        "Ti piacerebbe cambiare casa? Perché?",
    ]


def test_karte_begriff_mit_doppelpunkt(conn, tg):
    # Live G3: die Karte zeigte "EVENTO" als Kopf und den Rest des Begriffs
    # vor der Frage.
    _auswahl(conn, "EVENTO: dall'esterno all'interno: Dov'eri?",
             begriffe="EVENTO: dall’esterno all’interno")
    fragen._zeige_frage(conn, tg, CHAT, 1)
    text = tg.gesendet[-1][1]
    assert T._TEXT_FRAGE_KOPF.format(
        nummer=1, gesamt=1, begriff="EVENTO: dall’esterno all’interno") in text
    assert text.endswith("\n\nDov'eri?")

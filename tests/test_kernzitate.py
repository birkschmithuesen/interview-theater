"""Tests fuer den Filter am Kernthema (05.09.2026 abends).

Gemessen wird das, was die Umstellung ausmacht: die Auswahl kommt **nur** aus
dem, was schon in der Datenbank steht, sie wird verifiziert, sie landet in
``kernzitat`` und in den Markierungen an ``verdichtung_thema`` -- und in den
Chat geht **eine Zeile**, keine Liste und keine Knopfleiste.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe, die eine feste Antwort
liefert.
"""

import pytest

from interview_theater import kernzitate, repo

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


class KLMAttrappe:
    """Liefert die vorgegebene Schema-Antwort und merkt sich den Nutzertext."""

    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art,
                             "modell": modell})
        return self.antwort


def _interview(conn, transkript, themen, name="Interview"):
    """Ein Interview mit Verdichtung und geprueften Belegzitaten."""
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, name)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Eine Zusammenfassung.", themen)
    return kopf_id


def _material(conn):
    _interview(
        conn, "Ich habe zwanzig Jahre genaeht und keiner hat gefragt.",
        [
            {
                "thema": "Arbeit ohne Anerkennung",
                "beleg_zitat": "Ich habe zwanzig Jahre genaeht und keiner hat gefragt.",
                "zitat_geprueft": 1,
            }
        ],
        name="A",
    )
    _interview(
        conn, "Am Samstag faehrt keiner, da fahre ich.",
        [
            {
                "thema": "Fahrten am Wochenende",
                "beleg_zitat": "Am Samstag faehrt keiner, da fahre ich.",
                "zitat_geprueft": 1,
            }
        ],
        name="B",
    )
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Arbeit, die niemand sieht")
    repo.setze_arbeitsstand(
        conn, 1, "kernfrage",
        "Frage: Was passiert, wenn niemand fragt?\nGegensatz: sehen wollen - "
        "gesehen werden\nEinsatz: ob die Arbeit zaehlt",
    )


def test_die_eingabe_traegt_nur_gepruefte_zitate_und_keine_transkripte(conn, einst):
    """Die Zusage der Umstellung: das Modell waehlt aus, es liest nicht."""
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})

    kernzitate.waehle(klm, conn, einst, 1)

    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Kernfrage:" in nutzer
    assert "[1] Interview 1" in nutzer
    assert "[2] Interview 2" in nutzer
    # Der Wortlaut steht nur als Belegzitat da, nie als Volltranskript.
    assert "Volltranskript" not in nutzer
    assert klm.aufrufe[0]["modell"] == einst.erkenner_modell


def test_die_auswahl_landet_in_der_tabelle_und_markiert_die_verdichtung(conn, einst):
    _material(conn)
    klm = KLMAttrappe(
        {
            "zitat_nummern": [1],
            "zitate": ["Ich habe zwanzig Jahre genaeht und keiner hat gefragt."],
            "begruendungen": ["das Nichtgefragtwerden ist der Einsatz"],
            "verdichtung_nummern": [2],
        }
    )

    meldung = kernzitate.waehle(klm, conn, einst, 1)

    gewaehlt = repo.kernzitate(conn, 1)
    assert len(gewaehlt) == 1
    assert gewaehlt[0]["zitat"].startswith("Ich habe zwanzig Jahre")
    assert gewaehlt[0]["begruendung"] == "das Nichtgefragtwerden ist der Einsatz"
    assert gewaehlt[0]["rang"] == 1
    # Die Verdichtung des gewaehlten Zitats UND die zusaetzlich genannte sind
    # markiert -- ein Zitat ohne seine Verdichtung waere eine Stelle ohne
    # Zusammenhang.
    themen = repo.kernthemen_themen(conn, 1)
    assert {t["thema"] for t in themen} == {
        "Arbeit ohne Anerkennung", "Fahrten am Wochenende",
    }
    assert "1 Stellen" in meldung


def test_eine_erfundene_nummer_wird_verworfen(conn, einst):
    """Nur aus der Eingabe: eine Nummer, die es nicht gibt, wirkt nicht."""
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [99], "zitate": ["frei erfunden"],
                       "begruendungen": ["egal"], "verdichtung_nummern": []})

    kernzitate.waehle(klm, conn, einst, 1)

    assert repo.kernzitate(conn, 1) == []


def test_ein_abweichender_wortlaut_wird_verworfen(conn, einst):
    """Die Verifikation (``zitat.pruefe``): schreibt das Modell etwas
    anderes hin als das Zitat, auf dessen Nummer es zeigt, faellt der Eintrag
    weg -- statt stillschweigend zu passen."""
    _material(conn)
    klm = KLMAttrappe(
        {
            "zitat_nummern": [1],
            "zitate": ["Ich habe dreissig Jahre genaeht."],
            "begruendungen": ["passt schon"],
            "verdichtung_nummern": [],
        }
    )

    kernzitate.waehle(klm, conn, einst, 1)

    assert repo.kernzitate(conn, 1) == []


def test_gespeichert_wird_immer_das_original_aus_der_datenbank(conn, einst):
    """Auch wenn das Modell nur die Nummer liefert."""
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [2], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})

    kernzitate.waehle(klm, conn, einst, 1)

    assert repo.kernzitate(conn, 1)[0]["zitat"] == (
        "Am Samstag faehrt keiner, da fahre ich."
    )


def test_das_journal_haelt_die_auswahl_fest(conn, einst):
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [1, 2], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})

    kernzitate.waehle(klm, conn, einst, 1)

    texte = [e["text"] for e in repo.journal(conn, 1)]
    assert any("Kernzitate: 2 ausgewaehlt" in t for t in texte), texte


def test_ohne_passende_stelle_gibt_es_eine_zeile_und_geht_weiter(conn, einst):
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})

    meldung = kernzitate.waehle(klm, conn, einst, 1)

    assert meldung == kernzitate.MELDUNG_LEER
    assert repo.kernzitate(conn, 1) == []


def test_ohne_material_wird_gar_nicht_erst_gefragt(conn, einst):
    """Ein Modell, das aus nichts auswaehlen soll, erfindet."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    klm = KLMAttrappe({"zitat_nummern": [1], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})

    meldung = kernzitate.waehle(klm, conn, einst, 1)

    assert klm.aufrufe == []
    assert meldung == kernzitate.MELDUNG_LEER


def test_ein_zweiter_lauf_ersetzt_die_alte_auswahl(conn, einst):
    """Aendert die Gruppe die Kernfrage, gilt das neue Ergebnis -- eine alte
    Markierung waere Material einer verworfenen Frage."""
    _material(conn)
    kernzitate.waehle(
        KLMAttrappe({"zitat_nummern": [1], "zitate": [], "begruendungen": [],
                     "verdichtung_nummern": [1]}),
        conn, einst, 1,
    )

    kernzitate.waehle(
        KLMAttrappe({"zitat_nummern": [2], "zitate": [], "begruendungen": [],
                     "verdichtung_nummern": [2]}),
        conn, einst, 1,
    )

    assert [z["zitat"] for z in repo.kernzitate(conn, 1)] == [
        "Am Samstag faehrt keiner, da fahre ich."
    ]
    assert [t["thema"] for t in repo.kernthemen_themen(conn, 1)] == [
        "Fahrten am Wochenende"
    ]


def test_in_den_chat_geht_eine_zeile_ohne_knoepfe(conn, tg, einst):
    """Birks Korrektur vom selben Abend: keine Liste, keine Grundleiste --
    die Zitate sind Arbeitsmaterial fuer den naechsten Schritt, keine
    Entscheidung, die die Gruppe abnicken muss."""
    _material(conn)
    klm = KLMAttrappe({"zitat_nummern": [1], "zitate": [], "begruendungen": [],
                       "verdichtung_nummern": []})
    gelaufen = []

    thread = kernzitate.starte(
        conn, tg, klm, einst, 1, nachbereitung=lambda: gelaufen.append(True)
    )
    thread.join(timeout=5)

    assert tg.knoepfe == [], "keine Knopfleiste unter der Auswahl"
    assert len(tg.gesendet) == 1
    assert "Stellen" in tg.gesendet[0][1]
    assert gelaufen == [True], "danach geht es weiter (Figurenanzahl)"

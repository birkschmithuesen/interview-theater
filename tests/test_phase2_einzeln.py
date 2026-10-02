"""Phase 2, zweiter Umbau: "Fragen einzeln" (02.10.2026, Padua).

Der Vorschlag traegt die Sensibilitaetspruefung im selben Modellzug
(``VORSCHLAG FRAGENAUSWAHL:`` + optional ``VORSCHLAG FRAGEN WEICH:``),
danach ein Ueberblick mit Richtungsfrage ("Ja, einzeln durchgehen" /
"Andere Richtung"), danach die Fragen einzeln (Annehmen / Verwerfen /
Schaerfen -- mit oder ohne Knopfdruck auf "Schaerfen", eine freie Nachricht
waehrend eine Frage aktuell ist zaehlt immer als Schaerfungswunsch).

Kein Netzzugriff, kein Sprachmodell: Auftragszuege werden aufgezeichnet
(``ablauf.starte_auftrag`` gemockt) statt ausgefuehrt -- dieselbe Zusage wie
in ``tests/test_phase2_kette.py`` (AGENTS.md Zusage 2: kein Modellaufruf in
einem Knopf-Handler).
"""

import pytest

from interview_theater import ablauf, knoepfe, phasen, repo, vorschlag

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    """Zeichnet auf, welche Anweisungen an einen eigenen Thread gegangen
    waeren -- statt ein Modell zu rufen."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


VORSCHLAG = (
    "Hier sind ein paar Fragen dazu.\n\nVORSCHLAG FRAGENAUSWAHL:\n"
    "Heimat: Wann hast du dich zuletzt fremd gefuehlt?\n"
    "Heimat: Was nimmst du mit, wenn du umziehen musst?\n"
    "Streit: Wann habt ihr zuletzt richtig gestritten?\n\n"
    "VORSCHLAG FRAGEN WEICH:\n"
    "2 — Du musst nichts Privates teilen. Was nimmst du trotzdem mit, wenn "
    "du umziehen musst?"
)


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung, klm=None):
    knoepfe.behandle(conn, tg, klm, einst, _druck(_knopf(tg, beschriftung)))


def _vorschlag_zeigen(conn, tg, wert=VORSCHLAG):
    phasen.setze(conn, 1, 2, "befehl")
    return knoepfe.sende_mit_speicherleiste(conn, tg, 1, wert)


# --- 1. Ueberblick und Richtungsfrage --------------------------------------


def test_der_ueberblick_zeigt_die_fragen_gruppiert_mit_richtungsfrage(conn, tg):
    _vorschlag_zeigen(conn, tg)

    text = tg.gesendet[-1][1]
    assert "Heimat\n1. Wann hast du dich zuletzt fremd gefuehlt?" in text
    assert "2. Was nimmst du mit, wenn du umziehen musst?" in text
    assert "Streit\n3. Wann habt ihr zuletzt richtig gestritten?" in text
    assert knoepfe.T._TEXT_FRAGEN_RICHTUNG_FRAGE in text
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == ["Ja, einzeln durchgehen", "Andere Richtung"]


def test_die_weiche_fassung_aus_demselben_zug_wird_gespeichert(conn, tg):
    _vorschlag_zeigen(conn, tg)

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen_weich"] == (
        "2 — Du musst nichts Privates teilen. Was nimmst du trotzdem mit, "
        "wenn du umziehen musst?"
    )


def test_ohne_sensible_frage_bleibt_fragen_weich_leer(conn, tg):
    _vorschlag_zeigen(
        conn, tg,
        wert="VORSCHLAG FRAGENAUSWAHL:\nHeimat: Harmlose Frage?",
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["fragen_weich"] or "") == ""


def test_eine_neue_runde_setzt_entscheidungen_und_aktuelle_frage_zurueck(conn, tg):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    knoepfe.entscheide(conn, tg, None, None, 1, 1, "ja")

    # Ein neuer Vorschlag (z. B. nach "Andere Richtung") ersetzt die Liste
    # vollstaendig -- eine alte Entscheidung zu einer ersetzten Frage waere
    # bedeutungslos.
    _vorschlag_zeigen(conn, tg, wert="VORSCHLAG FRAGENAUSWAHL:\nNeu: Frage A?")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["fragen_entschieden"] or "") == ""
    assert stand["fragen_aktuell"] is None


# --- 2. Andere Richtung -----------------------------------------------------


def test_andere_richtung_fragt_deterministisch_und_speichert_nichts(
    conn, tg, einst, auftraege,
):
    _vorschlag_zeigen(conn, tg)

    _druecke(conn, tg, einst, "Andere Richtung")

    assert auftraege == [], "kein Modellaufruf im Knopf-Handler (Zusage 2)"
    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_FRAGEN_RICHTUNG_GEFRAGT
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen_warte_auf"] == "richtung"


def test_die_naechste_freie_nachricht_loest_den_neuen_vorschlag_aus(
    conn, tg, einst, auftraege,
):
    _vorschlag_zeigen(conn, tg)
    _druecke(conn, tg, einst, "Andere Richtung")

    getroffen = knoepfe.nimm_offene_frage_text(
        conn, tg, None, einst, 1, "Mehr zu Streit, weniger zu Heimat.",
    )

    assert getroffen is True
    assert len(auftraege) == 1
    assert "Mehr zu Streit, weniger zu Heimat." in auftraege[0]
    assert "Heimat: Wann hast du dich zuletzt fremd gefuehlt?" in auftraege[0], (
        "die alten Fragen stehen im Auftrag, damit sie nicht wiederkehren"
    )
    assert "VORSCHLAG FRAGENAUSWAHL:" in auftraege[0]
    assert repo.hole_arbeitsstand(conn, 1)["fragen_warte_auf"] is None


def test_eine_neue_antwort_landet_wieder_im_ueberblick(conn, tg, einst, auftraege):
    _vorschlag_zeigen(conn, tg)
    _druecke(conn, tg, einst, "Andere Richtung")
    knoepfe.nimm_offene_frage_text(conn, tg, None, einst, 1, "Andere Richtung bitte.")

    # Die Antwort des Modells (hier simuliert) landet wieder im Ueberblick.
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG FRAGENAUSWAHL:\nNeu: Ganz andere Frage?",
    )

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == ["Ja, einzeln durchgehen", "Andere Richtung"]


def test_ohne_offene_richtung_oder_aktuelle_frage_greift_der_abfang_nicht(
    conn, tg, einst,
):
    """Am Ueberblick, bevor ein Knopf gedrueckt wurde: eine freie Nachricht
    ist der normale Gespraechsweg, kein deterministischer Abfang."""
    _vorschlag_zeigen(conn, tg)

    assert knoepfe.nimm_offene_frage_text(
        conn, tg, None, einst, 1, "Das sieht gut aus.",
    ) is False


# --- 3. Frage fuer Frage: Annehmen, Verwerfen, Schaerfen -------------------


def test_frage_fuer_frage_zeigt_kopf_und_weiche_fassung(conn, tg):
    _vorschlag_zeigen(conn, tg)

    knoepfe.starte_durchgehen(conn, tg, 1)

    text = tg.gesendet[-1][1]
    assert text.startswith("Frage 1/3 · Heimat")
    assert "Wann hast du dich zuletzt fremd gefuehlt?" in text
    assert "sensibel" not in text  # erste Frage ist nicht als heikel markiert
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == ["Annehmen", "Verwerfen", "Schaerfen"]


def test_eine_sensible_frage_zeigt_die_weiche_fassung_darunter(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    _druecke(conn, tg, einst, "Annehmen")  # weiter zu Frage 2

    text = tg.gesendet[-1][1]
    assert text.startswith("Frage 2/3 · Heimat")
    assert "Du musst nichts Privates teilen" in text


def test_annehmen_geht_zur_naechsten_frage(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    _druecke(conn, tg, einst, "Annehmen")

    assert tg.gesendet[-1][1].startswith("Frage 2/3")
    assert repo.hole_arbeitsstand(conn, 1)["fragen_aktuell"] == "2"


def test_verwerfen_geht_ebenfalls_zur_naechsten_frage(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    _druecke(conn, tg, einst, "Verwerfen")

    assert tg.gesendet[-1][1].startswith("Frage 2/3")


def test_schaerfen_fragt_was_sich_aendern_soll(conn, tg, einst, auftraege):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    _druecke(conn, tg, einst, "Schaerfen")

    assert auftraege == [], "kein Modellaufruf im Knopf-Handler (Zusage 2)"
    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_FRAGE_WAS_AENDERN


def test_die_antwort_nach_schaerfen_startet_die_ueberarbeitung(
    conn, tg, einst, auftraege,
):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    _druecke(conn, tg, einst, "Schaerfen")

    getroffen = knoepfe.nimm_offene_frage_text(
        conn, tg, None, einst, 1, "mach sie persoenlicher",
    )

    assert getroffen is True
    assert len(auftraege) == 1
    anweisung = auftraege[0]
    assert "mach sie persoenlicher" in anweisung
    assert "Wann hast du dich zuletzt fremd gefuehlt?" in anweisung
    assert "VORSCHLAG FRAGE:" in anweisung


def test_freie_nachricht_ohne_schaerfen_knopf_zaehlt_ebenfalls_als_schaerfung(
    conn, tg, einst, auftraege,
):
    """Der Kern des Auftrags: die Gruppe muss "Schaerfen" nicht erst
    druecken -- waehrend eine Frage aktuell ist, ist jede freie Nachricht ihr
    Aenderungswunsch."""
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    getroffen = knoepfe.nimm_offene_frage_text(
        conn, tg, None, einst, 1, "mach die persoenlicher",
    )

    assert getroffen is True
    assert len(auftraege) == 1
    assert "mach die persoenlicher" in auftraege[0]


def test_die_ueberarbeitete_frage_ersetzt_nur_diese_eine_zeile(conn, tg):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG FRAGE:\nHeimat: Wann warst du zuletzt fremd?",
    )

    fragen = vorschlag.zeilen(repo.hole_arbeitsstand(conn, 1)["fragen_auswahl"])
    assert fragen[0] == "Heimat: Wann warst du zuletzt fremd?"
    assert fragen[1] == "Heimat: Was nimmst du mit, wenn du umziehen musst?"
    # Dieselbe Frage steht wieder da, mit denselben drei Knoepfen --
    # Schaerfen bringt NICHT automatisch die naechste Frage.
    assert tg.gesendet[-1][1].startswith("Frage 1/3 · Heimat")
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == ["Annehmen", "Verwerfen", "Schaerfen"]
    assert repo.hole_arbeitsstand(conn, 1)["fragen_aktuell"] == "1"


def test_die_ueberarbeitung_kann_die_weiche_fassung_mitbringen(conn, tg):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG FRAGE:\nHeimat: Wann fuehltest du dich das letzte Mal "
        "fremd?\n\nVORSCHLAG FRAGEN WEICH:\n"
        "1 — Du musst nichts Privates teilen. Wann fuehltest du dich das "
        "letzte Mal fremd?",
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert "1 — Du musst nichts Privates teilen" in stand["fragen_weich"]


def test_eine_ueberarbeitung_kann_die_weiche_fassung_auch_wieder_entfernen(
    conn, tg,
):
    """War die urspruengliche Fassung sensibel und die neue nicht mehr, faellt
    die weiche Fassung dieser Nummer weg -- sie gehoert zu einem Text, der
    nicht mehr dasteht."""
    _vorschlag_zeigen(conn, tg)  # Frage 2 ist sensibel
    knoepfe.starte_durchgehen(conn, tg, 1)
    knoepfe.entscheide(conn, tg, None, None, 1, 1, "ja")
    knoepfe._starte_schaerfung(conn, tg, None, None, 1, 2, "weniger privat")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG FRAGE:\nHeimat: Was nimmst du immer mit?",
    )

    assert "2 —" not in (repo.hole_arbeitsstand(conn, 1)["fragen_weich"] or "")


def test_ein_druck_auf_eine_ueberholte_frage_ist_harmlos(conn, tg):
    """Nach einer neuen Auswahlrunde ist die alte Fragenliste ersetzt -- ein
    Druck auf eine ihrer Nummern darf nicht crashen."""
    _vorschlag_zeigen(conn, tg, wert="VORSCHLAG FRAGENAUSWAHL:\nEin: Frage?")

    meldung = knoepfe.entscheide(conn, tg, None, None, 1, 5, "ja")

    assert meldung == knoepfe.T._TEXT_FRAGEN_KEINE_AUSWAHL
    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_FRAGEN_KEINE_AUSWAHL


# --- 4. Abschluss: alle entschieden -> Fragen gesetzt -> Eroeffnung -------


def test_sind_alle_entschieden_wird_fragen_gesetzt_und_eroeffnung_gestartet(
    conn, tg, einst, auftraege,
):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "nein")
    knoepfe.entscheide(conn, tg, None, einst, 1, 3, "ja")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen"] == (
        "Heimat: Wann hast du dich zuletzt fremd gefuehlt?\n"
        "Streit: Wann habt ihr zuletzt richtig gestritten?"
    ), "die verworfene Frage 2 fehlt"
    assert stand["fragen_aktuell"] is None
    assert stand["fragen_entschieden"] is None
    assert len(auftraege) == 1
    assert "VORSCHLAG EROEFFNUNG:" in auftraege[0]
    assert "VORSCHLAG FRAGEN WEICH:" not in auftraege[0], (
        "keine zweite Sensibilitaetspruefung mehr -- sie lief schon im "
        "Vorschlag"
    )


def test_eine_angenommene_sensible_frage_behaelt_ihre_weiche_fassung_mit_neuer_nummer(
    conn, tg, einst, auftraege,
):
    """Frage 2 (sensibel) wird angenommen, Frage 1 verworfen -- die weiche
    Fassung wandert auf die neue Nummer 1."""
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "nein")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 3, "nein")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen"] == "Heimat: Was nimmst du mit, wenn du umziehen musst?"
    assert stand["fragen_weich"].startswith("1 — Du musst nichts Privates teilen")


def test_journal_haelt_die_angenommenen_fragen_fest(conn, tg, einst, auftraege):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "nein")
    knoepfe.entscheide(conn, tg, None, einst, 1, 3, "nein")

    assert any(
        e["text"].startswith("Fragen:") for e in repo.journal(conn, 1)
    )


# --- 5. Keine Frage angenommen ---------------------------------------------


def test_keine_angenommene_frage_schlaegt_neue_vor(conn, tg, einst, auftraege):
    _vorschlag_zeigen(conn, tg, wert="VORSCHLAG FRAGENAUSWAHL:\nEin: Frage A?\nEin: Frage B?")
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "nein")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "nein")

    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_FRAGEN_KEINE_ANGENOMMEN
    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""
    assert len(auftraege) == 1
    assert "VORSCHLAG FRAGENAUSWAHL:" in auftraege[0]
    assert "Frage A?" in auftraege[0], "die verworfenen Fragen stehen als 'alte' im Auftrag"


# --- 6. Alte Knoepfe aus der ersten Fassung (06.09.2026) bleiben harmlos --


def test_der_alte_zehner_toggle_knopf_bleibt_harmlos(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_FRAGE_WAHL, "3")

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}"))

    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""


def test_der_alte_eigene_idee_knopf_bleibt_harmlos(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_FRAGEN_EIGENE, None)

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}"))

    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_FRAGEN_EIGENE
    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""


# --- 7. Keine harte Zahl mehr -----------------------------------------------


def test_kein_hartes_drei_oder_fuenf_im_prompt():
    pfad = (
        knoepfe.ANWEISUNG_FRAGEN_ANDERE,
    )
    for text in pfad:
        assert "genau zehn" not in text
        assert "genau drei" not in text


def test_der_weiche_block_steht_nicht_als_fliesstext_vor_der_liste(conn, tg):
    """Padua-Test 02.10.2026 (Birk): "die Fragen sollen pro Begriff
    vorgeschlagen werden, aber es kommen zuerst 5 - 25, dann geht es richtig
    an". Der weiche Block blieb nach dem Entfernen des Auswahlblocks als
    nackte Zeilen "2 — ..." im Chattext stehen, VOR der Liste nach Begriffen."""
    _vorschlag_zeigen(conn, tg)

    gesendet = tg.knoepfe[-1][1]
    assert "Du musst nichts Privates teilen" not in gesendet
    assert gesendet.startswith("Hier sind ein paar Fragen dazu.")
    assert "Heimat" in gesendet

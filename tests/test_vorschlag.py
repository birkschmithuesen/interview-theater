"""Deterministisches Speichern per Knopf (vorschlag.py + knoepfe-Leiste).

Gemessen wird genau das, was am 05.09.2026 live gefehlt hat: dass ein
Vorschlag des Bots **exakt so** in der Datenbank landet, wie er im Chat
stand -- ohne Erkennerlauf, ohne Raten. Und die Gegenprobe: **ohne** einen
klar markierten Vorschlagsblock gibt es keine Leiste, statt einen falschen
Text zu speichern.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, vorschlag

from test_knoepfe import TelegramAttrappe, _druck  # noqa: F401


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _knopf_daten(tg, beschriftung):
    """Die callback_data des Knopfes mit dieser Beschriftung, aus der
    juengsten Tastatur."""
    for text, daten in tg.knoepfe[-1][2]:
        if text == beschriftung:
            return daten
    raise AssertionError(f"kein Knopf {beschriftung!r} in {tg.knoepfe[-1][2]}")


# --- vorschlag.py: die Extraktion selbst ----------------------------------


def test_block_wird_bis_zur_leerzeile_gelesen():
    text = (
        "Ich habe eure Liste sortiert.\n\n"
        "VORSCHLAG BEGRIFFE:\n"
        "Heimat, Arbeit, Angst\n\n"
        "Passt das so?"
    )
    assert vorschlag.lies(text, "begriffe") == "Heimat, Arbeit, Angst"
    assert vorschlag.lies(text, "fragen") is None


def test_mehrzeiliger_block_bleibt_mehrzeilig():
    text = "VORSCHLAG FRAGEN:\nWann warst du fremd?\nWas nimmst du mit?"
    assert vorschlag.lies(text, "fragen") == "Wann warst du fremd?\nWas nimmst du mit?"


def test_ohne_marker_gibt_es_nichts_zu_lesen():
    """Der Kern der Zusage: kein Block, keine Leiste -- lieber gar nichts
    als der falsche Text."""
    text = "Ich wuerde Heimat, Arbeit und Angst nehmen. Passt das?"
    assert vorschlag.lies(text, "begriffe") is None


def test_marker_verschwindet_aus_dem_chattext():
    text = "Hier mein Vorschlag:\n\nVORSCHLAG KERNTHEMA:\nAnkommen\n"
    sauber = vorschlag.ohne_marker(text)
    assert "VORSCHLAG" not in sauber
    assert "Ankommen" in sauber


def test_figurenzeilen_werden_in_name_und_satz_zerlegt():
    wert = (
        "Mira — Naeherin, will gefragt werden — Interview 1\n"
        "- Pal - Taxifahrer, bleibt auf seiner Route - Interview 2"
    )
    assert vorschlag.figuren(wert) == [
        ("Mira", "Naeherin, will gefragt werden"),
        ("Pal", "Taxifahrer, bleibt auf seiner Route"),
    ]


# --- Die Leiste haengt nur bei extrahierbarem Block ------------------------


def test_leiste_nur_bei_block(conn, tg):
    """Zwei Antworten, dieselbe Phase, derselbe leere Arbeitsstand -- nur die
    mit Block bekommt Knoepfe."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "Was faellt euch noch ein?")
    assert tg.knoepfe == []

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "Vorschlag:\n\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit"
    )
    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter"]


def test_leiste_haengt_nicht_an_einer_schon_gefuellten_art(conn, tg):
    """Steht der Wert, gibt es nichts mehr zu speichern -- die Leiste
    verschwindet von selbst, auch wenn das Modell weiter Bloecke liefert."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat, Arbeit")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit, Angst"
    )

    assert tg.knoepfe == []


def test_in_phase_2_zaehlen_die_fragen_nicht_die_begriffe(conn, tg):
    phasen.setze(conn, 1, 2, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat\n\nVORSCHLAG FRAGEN:\nWarum?"
    )

    assert knoepfe.offene_art(conn, 1) == "fragen"
    assert tg.knoepfe, "die Fragen-Leiste haengt dran"


def test_in_phase_4_erst_setting_dann_figuren_dann_geschichte(conn, tg):
    """Der Ping-Pong der Phase 4 (Umbau 05.09.2026 nachts, zusammengelegt am
    06.09.2026): zuerst das SETTING (``rahmen``), dann die Figuren, dann die
    GESCHICHTE -- kein Kernthema, keine Kernfrage: hier wird erfunden, nicht
    aus dem Material geschaelt. Drei Ebenen, EINE Station: zwischen Figuren
    und Geschichte gibt es keinen Phasenwechsel mehr."""
    phasen.setze(conn, 1, 4, "befehl")
    assert knoepfe.offene_art(conn, 1) == "rahmen"

    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    assert knoepfe.offene_art(conn, 1) == "figuren"

    # Die Figuren-Leiste bleibt, bis die Liste FIXIERT ist -- nicht schon ab
    # zwei Figuren.
    repo.setze_figur(conn, 1, "Mira", "Naeherin")
    repo.setze_figur(conn, 1, "Pal", "Taxifahrer")
    assert knoepfe.offene_art(conn, 1) == "figuren"

    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")
    assert knoepfe.offene_art(conn, 1) == "geschichte"

    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    assert knoepfe.offene_art(conn, 1) is None


# --- "Gefaellt uns, weiter" schreibt exakt den Wert --------------------------------


def test_speichern_schreibt_exakt_den_vorgeschlagenen_wert(conn, tg, einst):
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "Ich schlage vor:\n\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit, Angst"
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Gefaellt uns, weiter")))

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit, Angst"
    assert any("Notiert:" in t for _, t in tg.gesendet)


def test_speichern_ist_idempotent(conn, tg, einst):
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    daten = _knopf_daten(tg, "Gefaellt uns, weiter")

    knoepfe.behandle(conn, tg, None, einst, _druck(daten))
    repo.setze_arbeitsstand(conn, 1, "begriffe", "von Hand geaendert")
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "von Hand geaendert"


def test_kernthema_ueber_die_leiste_landet_im_arbeitsstand(conn, tg, einst):
    """Derselbe Schreibweg wie beim Erkenner (``kernthema_setzen``) und beim
    Kernthema-Knopf -- nur deterministisch."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG KERNTHEMA:\nAnkommen, ohne die Sprache zu verlieren"
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Gefaellt uns, weiter")))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema"] == "Ankommen, ohne die Sprache zu verlieren"


def test_figuren_ueber_die_leiste_werden_alle_angelegt(conn, tg, einst):
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG FIGUREN:\n"
        "Mira — Naeherin, will gefragt werden — Interview 1\n"
        "Pal — Taxifahrer, bleibt auf seiner Route — Interview 2",
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Gefaellt uns, weiter")))

    namen = [f["name"] for f in repo.figuren(conn, 1)]
    assert namen == ["Mira", "Pal"]
    beschreibungen = {f["name"]: f["beschreibung"] for f in repo.figuren(conn, 1)}
    assert beschreibungen["Mira"] == "Naeherin, will gefragt werden"


# --- "Passt, aber anders" ------------------------------------------------------


def test_passt_aber_anders_speichert_trotzdem_und_fragt_gezielt(conn, tg, einst):
    """05.09.2026 abends, Birk: "Passt, aber anders" ist keine Ablehnung --
    es speichert die aktuelle Fassung (damit ueberhaupt etwas in der DB
    steht) und fragt danach gezielt, was anders werden soll."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Passt, aber anders")))

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat"
    assert tg.gesendet[-1][1] == (
        "Gespeichert. Was soll anders sein?"
    )


def test_eigene_idee_speichert_nicht(conn, tg, einst):
    """Der Gegensatz: "Eigene Idee" schreibt NICHTS, der naechste Beitrag der
    Gruppe ist der Vorschlag."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Eigene Idee")))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand and stand["begriffe"])
    assert tg.gesendet[-1][1] == "Erzaehlt - ich baue es ein."


def test_nach_nochmal_anders_traegt_die_naechste_antwort_die_leiste_wieder(
    conn, tg, einst
):
    """Der Kern der Zusage 'das Menue kommt nach jeder Aenderung wieder':
    solange der Wert leer ist, haengt die Leiste erneut dran."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Passt, aber anders")))

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")

    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter"]
    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Gefaellt uns, weiter")))
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"


def test_eine_neue_leiste_nimmt_die_alte_ab(conn, tg, einst):
    """Sonst staenden zwei Leisten im Chat, und ein Druck auf die aeltere
    speicherte den ueberholten Vorschlag."""
    erste = knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")[0]
    alt = _knopf_daten(tg, "Gefaellt uns, weiter")

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")

    assert (1, erste) in tg.entfernt
    knoepfe.behandle(conn, tg, None, einst, _druck(alt))
    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand and stand["begriffe"]), "der ueberholte Knopf wirkt nicht mehr"


# --- Der Erkenner-Pfad bleibt der zweite Weg -------------------------------


def test_schreibt_der_erkenner_zuerst_verschwindet_die_leiste(conn, tg):
    from interview_theater import erkenner

    erkenner.wende_an(
        conn, None, 1, [{"art": "begriffe_setzen", "wert": "Heimat, Arbeit"}]
    )

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    assert tg.knoepfe == []


# --- Die vier Auswahl-Marker (05.09.2026 abends) --------------------------


@pytest.mark.parametrize(
    "marker,art",
    [
        ("RICHTUNGEN", "richtungen"),
        ("NAMEN", "namen"),
        ("DUKTUS", "duktus"),
        ("RAHMEN", "rahmen"),
    ],
)
def test_die_neuen_marker_werden_gelesen(marker, art):
    text = f"Ein Satz.\n\nVORSCHLAG {marker}:\nErste Zeile\nZweite Zeile"

    assert vorschlag.lies(text, art) == "Erste Zeile\nZweite Zeile"
    assert "VORSCHLAG" not in vorschlag.ohne_marker(text)


def test_zeilen_wirft_aufzaehlungszeichen_weg():
    """Aus jeder Zeile wird ein Knopf -- eine Ziffer gehoert nicht in die
    Beschriftung, und Modelle schreiben mal '1) ', mal '- '."""
    wert = "1) Arbeit, die niemand sieht\n- Zwei Sprachen\n\n  Was bleibt  "

    assert vorschlag.zeilen(wert) == [
        "Arbeit, die niemand sieht", "Zwei Sprachen", "Was bleibt",
    ]


def test_alle_liefert_jeden_block_einer_nachricht():
    text = "VORSCHLAG RICHTUNGEN:\nA\n\nVORSCHLAG RAHMEN:\nB"

    assert vorschlag.alle(text) == {"richtungen": "A", "rahmen": "B"}


def test_ohne_marker_streicht_fliesstext_der_den_block_wiederholt():
    """06.09.2026 12:50 (Gruppe 1): Eroeffnung im Fliesstext UND im Block --
    die Gruppe las sie zweimal. Der Fliesstext-Doppel faellt, der Block bleibt."""
    from interview_theater import vorschlag

    satz = ("Hallo, wir sind eine Gruppe von Maedels und machen gerade ein "
            "Theaterstueck ueber Sachen, die uns im Alltag begegnen.")
    text = (f"Klar -- dann wie folgt.\n\n{satz}\nAbschluss: Danke fuer deine Zeit, "
            f"wir melden uns.\n\nTrifft das?\n\nVORSCHLAG EROEFFNUNG:\n{satz}\n"
            "Abschluss: Danke fuer deine Zeit, wir melden uns.")
    sauber = vorschlag.ohne_marker(text)
    assert sauber.count(satz) == 1
    assert sauber.count("Abschluss: Danke") == 1
    assert sauber.startswith("Klar -- dann wie folgt.")
    assert "Trifft das?" in sauber
    # Block-Inhalt bleibt lesbar (er steht hinten)
    assert sauber.rstrip().endswith("wir melden uns.")

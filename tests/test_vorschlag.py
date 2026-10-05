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
    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Ja, speichern", "Nein, nochmal aendern"]


def test_leiste_haengt_nicht_an_einer_schon_gefuellten_art(conn, tg):
    """Steht der Wert, gibt es nichts mehr zu speichern -- die Leiste
    verschwindet von selbst, auch wenn das Modell weiter Bloecke liefert."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat, Arbeit")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit, Angst"
    )

    assert tg.knoepfe == []


def test_zwei_bloecke_verschiedener_arten_werden_zu_einem(conn, tg):
    """Ein Feld je Nachricht (06.09.2026, Birk 11:00): kommen zwei
    Vorschlagsbloecke verschiedener Arten, geht NUR der erste raus -- der
    zweite wird verworfen und als Vorfall vermerkt."""
    phasen.setze(conn, 1, 2, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat\n\nVORSCHLAG FRAGEN:\nWarum?"
    )

    text = tg.gesendet[-1][1] if tg.gesendet else tg.knoepfe[-1][1]
    assert "Heimat" in text
    assert "Warum?" not in text, "der zweite Block ist verworfen"
    arten = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()
    ]
    assert "vorschlag_mehrere_arten" in arten


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


# --- "Ja, speichern" schreibt exakt den Wert --------------------------------


def test_speichern_schreibt_exakt_den_vorgeschlagenen_wert(conn, tg, einst):
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "Ich schlage vor:\n\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit, Angst"
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Ja, speichern")))

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit, Angst"
    # Seit Padua Hotfix B5 (02.10.2026) macht dieses Speichern Phase 1
    # abschliessbar: statt "Notiert:" steht die Abschlussnachricht da, und
    # sie zeigt exakt den gespeicherten Wert.
    assert any("Heimat, Arbeit, Angst" in t for _, t in tg.gesendet[1:])


def test_speichern_ist_idempotent(conn, tg, einst):
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    daten = _knopf_daten(tg, "Ja, speichern")

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

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Ja, speichern")))

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

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Ja, speichern")))

    namen = [f["name"] for f in repo.figuren(conn, 1)]
    assert namen == ["Mira", "Pal"]
    beschreibungen = {f["name"]: f["beschreibung"] for f in repo.figuren(conn, 1)}
    assert beschreibungen["Mira"] == "Naeherin, will gefragt werden"


# --- "Passt, aber anders" ------------------------------------------------------


def test_nein_nochmal_aendern_speichert_vorlaeufig(conn, tg, einst):
    """05.09.2026 abends, Birk: "Passt, aber anders" ist keine Ablehnung --
    es speichert die aktuelle Fassung (damit ueberhaupt etwas in der DB
    steht) und fragt danach gezielt, was anders werden soll."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf_daten(tg, "Nein, nochmal aendern"))
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["begriffe"] == "Heimat", "Nein speichert vorlaeufig (02.10.2026)"
    assert tg.gesendet[-1][1] == "Vorerst gespeichert. Was soll anders sein?"


def test_nach_nochmal_anders_traegt_die_naechste_antwort_die_leiste_wieder(
    conn, tg, einst
):
    """Der Kern der Zusage 'das Menue kommt nach jeder Aenderung wieder':
    solange der Wert leer ist, haengt die Leiste erneut dran."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf_daten(tg, "Nein, nochmal aendern"))
    )

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")

    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Ja, speichern", "Nein, nochmal aendern"]
    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf_daten(tg, "Ja, speichern")))
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"


def test_eine_neue_leiste_nimmt_die_alte_ab(conn, tg, einst):
    """Sonst staenden zwei Leisten im Chat, und ein Druck auf die aeltere
    speicherte den ueberholten Vorschlag."""
    erste = knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")[0]
    alt = _knopf_daten(tg, "Ja, speichern")

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


def test_ohne_marker_streicht_den_grossgeschriebenen_abschluss_marker():
    """Padua-Befund M1 (Lesung Runde 2, 05.10.2026): der EN-Auftrag laesst
    den Bot woertlich 'ABSCHLUSS:' schreiben (K6-Protokoll-Token,
    ``knoepfe.T.ANWEISUNG_EROEFFNUNG``) -- das stand GROSSGESCHRIEBEN im
    Chat (Simulationslauf 2026-10-05-handy-giulia-p12, Nachricht 119/120).
    Nur die GROSSGESCHRIEBENE Form ist Technik; das deutsche Fliesstextwort
    'Abschluss:' (klein geschrieben, siehe Test oben) bleibt unberuehrt --
    deshalb bewusst ohne ``re.IGNORECASE``, wie ``_MARKER_IRGENDWO``."""
    from interview_theater import vorschlag

    text = (
        "Here is a first version.\n\n"
        "VORSCHLAG EROEFFNUNG:\n"
        "Hi, we are from the theatre project. Is it ok to record?\n"
        "ABSCHLUSS: Thank you, that was really good to hear."
    )
    sauber = vorschlag.ohne_marker(text)
    assert "ABSCHLUSS:" not in sauber
    assert "Thank you, that was really good to hear." in sauber

    # Die umbenannte Form (CLOSING:, system.md) faellt genauso weg.
    umbenannt = text.replace("ABSCHLUSS:", "CLOSING:")
    sauber_umbenannt = vorschlag.ohne_marker(umbenannt)
    assert "CLOSING:" not in sauber_umbenannt
    assert "Thank you, that was really good to hear." in sauber_umbenannt


# --- Marker nicht am Zeilenanfang (P2-M4, Prompt-Check 05.10.2026) --------
# Live-Befund: "VORSCHLAG EIGENE FRAGEN:" landete sichtbar im Chat, weil
# das Modell den Marker nicht als eigene Zeile schrieb -- mitten im
# Fliesstext, mit Markdown-Sternchen drumherum, oder direkt nach einem
# Satz ohne Leerzeile davor. ``_ZEILE`` erkannte nur eine Zeile, die GENAU
# mit "VORSCHLAG" beginnt -- alles andere blieb als rohe Markerzeile stehen.


def test_marker_mitten_im_fliesstext_wird_gelesen_und_entfernt():
    text = (
        "Here is my suggestion. VORSCHLAG EIGENE FRAGEN:\n"
        "Home: What makes you feel at home?"
    )
    assert vorschlag.lies(text, "eigene_fragen") == "Home: What makes you feel at home?"
    sauber = vorschlag.ohne_marker(text)
    assert "VORSCHLAG" not in sauber
    assert "Here is my suggestion." in sauber
    assert "What makes you feel at home?" in sauber


def test_marker_mit_markdown_sternchen_wird_gelesen_und_entfernt():
    text = "**VORSCHLAG EIGENE FRAGEN:**\nHome: What makes you feel at home?"
    assert vorschlag.lies(text, "eigene_fragen") == "Home: What makes you feel at home?"
    sauber = vorschlag.ohne_marker(text)
    assert "VORSCHLAG" not in sauber
    assert "*" not in sauber
    assert "What makes you feel at home?" in sauber


def test_marker_direkt_nach_einem_satz_ohne_leerzeile_wird_erkannt():
    """Mid-paragraph: der Marker folgt direkt auf einen Satz, ohne eigene
    Zeile und ohne Leerzeile davor."""
    text = (
        "Thanks, that's clear. VORSCHLAG EIGENE FRAGEN:\n"
        "Home: What makes you feel at home?\n"
        "Fear: What are you afraid of?"
    )
    assert vorschlag.lies(text, "eigene_fragen") == (
        "Home: What makes you feel at home?\nFear: What are you afraid of?"
    )
    sauber = vorschlag.ohne_marker(text)
    assert "VORSCHLAG" not in sauber
    assert "Thanks, that's clear." in sauber
    assert "What are you afraid of?" in sauber


def test_ohne_bloecke_entfernt_jeden_block_fuer_die_echo_pruefung():
    """P2-M9: der Echo-Check soll den sichtbaren Text pruefen, nicht den
    Vorschlagsblock -- in Phase 2 steht die diktierte Frage zwingend auch im
    ``VORSCHLAG EIGENE FRAGEN:``-Block (Format ``Begriff: Frage``)."""
    text = "Noted.\n\nVORSCHLAG EIGENE FRAGEN:\nHome: What makes you feel at home?"
    assert vorschlag.ohne_bloecke(text) == "Noted."


def test_ohne_bloecke_laesst_den_fliesstext_unberuehrt():
    text = "What makes you feel at home?\n\nVORSCHLAG EIGENE FRAGEN:\nHome: etwas anderes"
    assert vorschlag.ohne_bloecke(text) == "What makes you feel at home?"


# --- Mid-line-Treffer nur an einer echten Grenze (Review-Fix 05.10.2026) -
# Befund nach c63e210: ``_MARKER_IRGENDWO`` traf GROSS-/Kleinschreibung
# gleich und ueberall in der Zeile -- ein gewoehnliches deutsches Nomen
# "Vorschlag" (klein geschrieben bis auf den Satzanfang) im Fliesstext wurde
# faelschlich als Marker gelesen und die Zeile zerschnitten.


def test_deutsches_nomen_vorschlag_rahmen_im_fliesstext_bleibt_unberuehrt():
    text = (
        "Mein Vorschlag Rahmen: Mittwochabend, Herbst 1920, "
        "im Hinterzimmer.\n\nWeiter so."
    )
    assert vorschlag.ohne_marker(text) == text
    assert vorschlag.lies(text, "rahmen") is None


def test_deutsches_nomen_vorschlag_namen_im_fliesstext_bleibt_unberuehrt():
    text = "Ihr Vorschlag Namen: Anna, Lotte, schlage ich vor."
    assert vorschlag.ohne_marker(text) == text
    assert vorschlag.lies(text, "namen") is None


def test_marker_nach_einem_satz_wird_weiterhin_erkannt():
    """Gegenprobe zu den beiden Tests oben: der ECHTE Marker (GROSSBUCHSTABEN)
    mitten im Fliesstext muss weiterhin erkannt werden -- nur die
    Kleinschreibung eines normalen Nomens soll verschont bleiben."""
    text = "That's good. VORSCHLAG EIGENE FRAGEN:\nHome: etwas"
    assert vorschlag.lies(text, "eigene_fragen") == "Home: etwas"
    sauber = vorschlag.ohne_marker(text)
    assert "VORSCHLAG" not in sauber
    assert "That's good." in sauber


def test_marker_kleingeschrieben_mitten_in_der_zeile_wird_nicht_erkannt():
    text = "Thanks. vorschlag eigene fragen: Home: etwas"
    assert vorschlag.lies(text, "eigene_fragen") is None
    assert vorschlag.ohne_marker(text) == text


def test_ohne_block_entfernt_auch_den_weichen_fragenblock():
    """Padua-Test 02.10.2026: der weiche Block (Marker mit Leerzeichen,
    Art mit Unterstrich) blieb im Chattext stehen -- die Gruppe sah
    "5 — ... 7 — ..." vor der Fragenliste."""
    text = (
        "One sentence.\n\n"
        "VORSCHLAG FRAGENAUSWAHL:\nApfel: Frage eins?\nApfel: Frage zwei?\n\n"
        "VORSCHLAG FRAGEN WEICH:\n2 — Nur wenn du magst: Frage zwei?\n"
    )
    rest = vorschlag.ohne_block(text, "fragenauswahl", "fragen_weich")
    assert rest == "One sentence."

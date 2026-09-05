"""Tests fuer die Verfeinerungsebene der Phase 2 und den Leitfaden
(06.09.2026, Birk).

Gemessen wird hier die Kette, die zwischen "wir haben Fragen" und "wir stehen
vor einer fremden Person" liegt: zehn Fragen zur Wahl -> genau drei ->
Sensibilitaetspruefung mit Einleitungen -> Eroeffnung und Abschluss ->
Leitfaden. Kein Netzzugriff und kein Sprachmodell: die Modellwege
(``ablauf.starte_auftrag``) werden aufgezeichnet statt ausgefuehrt -- das ist
zugleich die Zusage, die hier geprueft wird (**kein Modellaufruf in einem
Knopf-Handler**, AGENTS.md Zusage 2 in ``knoepfe.py``).
"""

import pytest

from interview_theater import ablauf, befehle, knoepfe, leitfaden, phasen, repo

from test_knoepfe import TelegramAttrappe, _druck


class TelegramMitTastatur(TelegramAttrappe):
    """Wie die Attrappe aus ``test_knoepfe``, nur mit
    ``aktualisiere_knoepfe`` -- die Mehrfachauswahl tauscht die Tastatur
    derselben Nachricht aus, statt zehn Fragen noch einmal zu schicken."""

    def __init__(self):
        super().__init__()
        self.aktualisiert = []

    def aktualisiere_knoepfe(self, chat_id, message_id, knoepfe_):
        self.aktualisiert.append((chat_id, message_id, list(knoepfe_)))
        # Damit ``_knopf`` weiterhin die juengste Tastatur findet.
        self.knoepfe.append((chat_id, None, list(knoepfe_)))


@pytest.fixture
def tg():
    return TelegramMitTastatur()


@pytest.fixture
def auftraege(monkeypatch):
    """Zeichnet auf, welche Anweisungen an einen eigenen Thread gegangen
    waeren -- statt ein Modell zu rufen."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


ZEHN = "\n".join(f"Frage {n}?" for n in range(1, 11))


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung, klm=None):
    knoepfe.behandle(conn, tg, klm, einst, _druck(_knopf(tg, beschriftung)))


def _auswahl(conn, tg, fragen=ZEHN):
    return knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, f"Hier sind zehn.\n\nVORSCHLAG FRAGENAUSWAHL:\n{fragen}"
    )


# --- Die Mehrfachauswahl --------------------------------------------------


def test_zehn_fragen_werden_zu_zehn_knoepfen_plus_drei(conn, tg):
    """Ein Knopf je Frage, darunter die drei Handlungsknoepfe."""
    _auswahl(conn, tg)

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert len(beschriftungen) == knoepfe.FRAGEN_ZUR_WAHL + 3
    assert beschriftungen[0].startswith("1. Frage 1")
    assert beschriftungen[-3:] == ["Diese 3 nehmen", "Andere 10", "Eigene Idee"]


def test_die_fragen_stehen_nicht_zweimal_im_chat(conn, tg):
    """Der Vorschlagsblock ist Technik: im Chat steht der Satz des Bots, die
    Fragen stehen auf den Knoepfen."""
    _auswahl(conn, tg)

    assert tg.gesendet[-1][1] == "Hier sind zehn."


def test_ein_druck_setzt_den_haken_ein_zweiter_nimmt_ihn_weg(conn, tg, einst):
    _auswahl(conn, tg)

    _druecke(conn, tg, einst, "1. Frage 1?")
    assert repo.hole_arbeitsstand(conn, 1)["fragen_gewaehlt"] == "1"
    assert any(b.startswith("✓ 1.") for b, _ in tg.aktualisiert[-1][2])

    _druecke(conn, tg, einst, "✓ 1. Frage 1?")
    assert (repo.hole_arbeitsstand(conn, 1)["fragen_gewaehlt"] or "") == ""


def test_die_tastatur_derselben_nachricht_wird_getauscht(conn, tg, einst):
    """Kein zweiter Zehnerblock im Chat: nur die Tastatur aendert sich."""
    message_id, _ = _auswahl(conn, tg)
    vorher = len(tg.gesendet)

    _druecke(conn, tg, einst, "2. Frage 2?")

    assert len(tg.gesendet) == vorher, "keine neue Nachricht"
    assert tg.aktualisiert[-1][1] == message_id


def test_eine_lange_frage_wird_sichtbar_gekuerzt(conn, tg):
    lang = "Was hast du erlebt, als du zum allerersten Mal ganz allein warst?"
    _auswahl(conn, tg, fragen=lang + "\n" + ZEHN)

    beschriftung = tg.knoepfe[-1][2][0][0]
    assert beschriftung.endswith("…")
    assert len(beschriftung) <= knoepfe.KNOPF_LAENGE + 5


# --- Die Sperre bei falscher Anzahl ---------------------------------------


@pytest.mark.parametrize("anzahl", [0, 1, 2, 4])
def test_uebernehmen_wirkt_nur_bei_genau_drei(conn, tg, einst, anzahl, auftraege):
    _auswahl(conn, tg)
    for nummer in range(1, anzahl + 1):
        _druecke(conn, tg, einst, f"{nummer}. Frage {nummer}?")

    _druecke(conn, tg, einst, "Diese 3 nehmen")

    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""
    assert tg.beantwortet[-1][1] == "Waehlt genau 3."
    assert auftraege == [], "keine Pruefung ohne Fragen"


def test_genau_drei_werden_gespeichert(conn, tg, einst, auftraege):
    _auswahl(conn, tg)
    for nummer in (1, 3, 7):
        _druecke(conn, tg, einst, f"{nummer}. Frage {nummer}?")

    _druecke(conn, tg, einst, "Diese 3 nehmen")

    assert repo.hole_arbeitsstand(conn, 1)["fragen"].splitlines() == [
        "Frage 1?", "Frage 3?", "Frage 7?",
    ]
    assert any(
        e["text"].startswith("Fragen:") for e in repo.journal(conn, 1)
    ), "die Festlegung steht im Journal"


def test_speichern_loest_die_sensibilitaetspruefung_aus(conn, tg, einst, auftraege):
    """Der Kern des Auftrags: nach dem Festlegen prueft der Bot automatisch,
    ohne dass jemand danach fragt -- und ohne Modellaufruf im Handler."""
    _auswahl(conn, tg)
    for nummer in (1, 2, 3):
        _druecke(conn, tg, einst, f"{nummer}. Frage {nummer}?")

    _druecke(conn, tg, einst, "Diese 3 nehmen")

    assert len(auftraege) == 1
    assert "VORSCHLAG EINLEITUNGEN:" in auftraege[0]
    assert "FREMDEN" in auftraege[0]
    assert "Frage 1?" in auftraege[0], "die Fragen stehen im Auftrag"


def test_andere_zehn_nennt_die_alten_als_nicht_wieder(conn, tg, einst, auftraege):
    _auswahl(conn, tg)

    _druecke(conn, tg, einst, "Andere 10")

    assert len(auftraege) == 1
    assert "nimm keine davon wieder" in auftraege[0]
    for nummer in range(1, 11):
        assert f"Frage {nummer}?" in auftraege[0]


def test_eigene_idee_speichert_nichts_und_wartet(conn, tg, einst, auftraege):
    _auswahl(conn, tg)

    _druecke(conn, tg, einst, "Eigene Idee")

    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""
    assert repo.hole_arbeitsstand(conn, 1)["aenderung_offen"] == "fragen"
    assert auftraege == []


def test_diktierte_fragen_loesen_die_pruefung_ebenfalls_aus(conn, tg, einst, auftraege):
    """Der Rueckfallweg: die Gruppe diktiert die Fragen selbst und nimmt sie
    ueber die Grundleiste ab -- die Pruefung haengt an den FRAGEN, nicht am
    Weg dorthin."""
    phasen.setze(conn, 1, 2, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG FRAGEN:\nWas war in deinem Koffer?"
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == "Was war in deinem Koffer?"
    assert len(auftraege) == 1
    assert "VORSCHLAG EINLEITUNGEN:" in auftraege[0]


# --- Einleitungen und Eroeffnung ------------------------------------------


def _mit_fragen(conn, wert="Woher kommst du?\nWas glaubst du?\nWen liebst du?"):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", wert)


def test_die_einleitungen_landen_in_ihrer_eigenen_spalte(conn, tg, einst, auftraege):
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "Zwei sind heikel.\n\nVORSCHLAG EINLEITUNGEN:\n"
        "1 — Wir fragen nach Herkunft, du musst nicht antworten.\n"
        "3 — Das ist privat, sag nur, was du magst.",
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert "1 — Wir fragen nach Herkunft" in stand["frage_einleitungen"]
    assert "3 — Das ist privat" in stand["frage_einleitungen"]


def test_nach_den_einleitungen_kommt_die_eroeffnung_von_selbst(conn, tg, einst, auftraege):
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG EINLEITUNGEN:\n1 — Du musst nicht antworten."
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert len(auftraege) == 1
    assert "VORSCHLAG EROEFFNUNG:" in auftraege[0]


def test_der_leerfall_haelt_nichts_auf(conn, tg, einst, auftraege):
    """"Keine der Fragen braucht eine besondere Einleitung." ist ein
    Ergebnis: es wird gespeichert, und der naechste Schritt laeuft an."""
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG EINLEITUNGEN:\nKeine der Fragen braucht eine besondere "
        "Einleitung.",
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert "Keine der Fragen" in stand["frage_einleitungen"]
    assert leitfaden.einleitungen(stand["frage_einleitungen"]) == {}
    assert len(auftraege) == 1, "die Eroeffnung kommt trotzdem"


def test_eroeffnung_und_abschluss_gehen_in_zwei_felder(conn, tg, einst):
    _mit_fragen(conn)
    repo.setze_arbeitsstand(conn, 1, "frage_einleitungen", "Keine noetig.")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG EROEFFNUNG:\n"
        "Hallo, wir sind vom Theaterprojekt im Verein.\n"
        "Deine Antworten bleiben anonym, du kannst jederzeit aufhoeren.\n"
        "Abschluss: Danke dir. Wir bauen daraus ein Stueck.",
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["interview_eroeffnung"].startswith("Hallo, wir sind")
    assert "anonym" in stand["interview_eroeffnung"]
    assert stand["interview_abschluss"] == "Danke dir. Wir bauen daraus ein Stueck."


# --- Der Leitfaden --------------------------------------------------------


def _vollstaendig(conn):
    repo.setze_arbeitsstand(conn, 1, "fragen", "Woher kommst du?\nWas machst du gern?")
    repo.setze_arbeitsstand(
        conn, 1, "frage_einleitungen", "1 — Wir fragen alle danach, du musst nicht."
    )
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo, wir sind ...")
    repo.setze_arbeitsstand(conn, 1, "interview_abschluss", "Danke dir.")


def test_der_leitfaden_setzt_alles_in_der_richtigen_reihenfolge_zusammen(conn):
    _vollstaendig(conn)

    text = leitfaden.baue(conn, 1)

    assert text.index("So fangt ihr an:") < text.index("Eure Fragen:")
    assert text.index("Eure Fragen:") < text.index("So hoert ihr auf:")
    # Die Einleitung steht VOR ihrer Frage, nicht dahinter.
    assert text.index("1. Woher kommst du?") < text.index("du musst nicht")
    assert text.index("du musst nicht") < text.index("2. Was machst du gern?")


def test_der_leitfaden_ist_deterministisch(conn):
    """Zweimal derselbe Text -- was die Gruppe im Raum liest, aendert sich
    zwischen zwei Abrufen nicht."""
    _vollstaendig(conn)

    assert leitfaden.baue(conn, 1) == leitfaden.baue(conn, 1)


def test_ohne_fragen_gibt_es_keinen_leitfaden(conn):
    assert leitfaden.baue(conn, 1) == leitfaden.TEXT_LEER
    assert leitfaden.steht(conn, 1) is False


def test_ohne_einleitungen_stehen_die_fragen_trotzdem(conn):
    repo.setze_arbeitsstand(conn, 1, "fragen", "Woher kommst du?")
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo.")

    text = leitfaden.baue(conn, 1)

    assert "1. Woher kommst du?" in text
    assert "↳" not in text
    assert "So hoert ihr auf:" not in text, "kein erfundener Abschluss"


def test_leitfaden_befehl_zeigt_ihn(conn, tg, einst):
    _vollstaendig(conn)

    assert befehle.behandle(conn, tg, einst, 1, "/leitfaden", "Ada") is True

    assert "Euer Leitfaden fuers Interview:" in tg.gesendet[-1][1]
    assert "1. Woher kommst du?" in tg.gesendet[-1][1]


def test_der_leitfaden_befehl_wird_nirgends_beworben(conn):
    """Versteckt heisst versteckt: er steht in keiner Befehlsliste."""
    assert "/leitfaden" in befehle._BEKANNTE_BEFEHLE
    assert "leitfaden" not in {b["command"] for b in befehle.BEFEHLE_LISTE}
    assert "/leitfaden" not in befehle._TEXT_HILFE


# --- Einmal zeigen, danach auf Nachfrage ----------------------------------


def test_der_interviewstart_zeigt_den_leitfaden_genau_einmal(conn, tg, einst):
    """Beim ersten Start geht er raus, beim zweiten nicht mehr -- sonst
    schoebe er vor jedem Interview das Transkript aus dem Bild."""
    _vollstaendig(conn)

    befehle.behandle(conn, tg, einst, 1, "/aufnahme", "Ada")
    erste = [t for _, t in tg.gesendet if t.startswith("Euer Leitfaden")]
    assert len(erste) == 1

    befehle.behandle(conn, tg, einst, 1, "/aufnahme", "Ada")  # beenden
    befehle.behandle(conn, tg, einst, 1, "/aufnahme", "Ada")  # zweiter Start
    zweite = [t for _, t in tg.gesendet if t.startswith("Euer Leitfaden")]
    assert len(zweite) == 1, "nur beim ersten Mal ungefragt"


def test_ohne_leitfaden_wird_beim_start_nichts_geschickt(conn, tg, einst):
    befehle.behandle(conn, tg, einst, 1, "/aufnahme", "Ada")

    assert not any(t.startswith("Euer Leitfaden") for _, t in tg.gesendet)


def test_der_phasenknopf_in_die_interviews_zeigt_den_leitfaden(conn, tg, einst):
    _vollstaendig(conn)
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 3)

    _druecke(conn, tg, einst, "Weiter zu Interviews")

    assert any(t.startswith("Euer Leitfaden") for _, t in tg.gesendet)
    assert phasen.aktuelle(conn, 1) == 3


def test_leitfaden_knopf_im_einstieg_der_phase_3(conn, tg, einst):
    _vollstaendig(conn)
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")

    assert "Leitfaden zeigen" in [b for b, _ in tg.knoepfe[-1][2]]


def test_kein_leitfaden_knopf_in_phase_2(conn, tg):
    """In Phase 2 wird der Leitfaden noch gebaut -- ihn dort anzubieten
    hiesse, auf einen halben Text zu zeigen."""
    _vollstaendig(conn)
    phasen.setze(conn, 1, 2, "befehl")

    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")

    assert "Leitfaden zeigen" not in [b for b, _ in tg.knoepfe[-1][2]]


def test_leitfaden_knopf_nach_einem_interview(conn, tg, einst):
    _vollstaendig(conn)
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Fertig.", None)

    assert "Leitfaden zeigen" in [b for b, _ in tg.knoepfe[-1][2]]

    _druecke(conn, tg, einst, "Leitfaden zeigen")
    assert any(t.startswith("Euer Leitfaden") for _, t in tg.gesendet)


# --- Web ------------------------------------------------------------------


def test_die_gruppenseite_zeigt_den_leitfaden_unter_den_fragen(conn):
    from interview_theater import web, web_daten

    _vollstaendig(conn)
    felder = {
        "fragen": "Woher kommst du?",
        "frage_einleitungen": "1 — Du musst nicht antworten.",
        "interview_eroeffnung": "Hallo, wir sind ...",
        "interview_abschluss": "Danke dir.",
    }
    html = web._leitfaden_html(felder)

    assert "<dt>Leitfaden</dt>" in html
    assert "So fangt ihr an:" in html
    assert web_daten is not None


def test_ohne_leitfaden_steht_auf_der_seite_nichts(conn):
    from interview_theater import web

    assert web._leitfaden_html({"fragen": None}) == ""

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

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
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
    phasen.setze(conn, 1, 2, "befehl")
    return knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, f"Hier sind zehn.\n\nVORSCHLAG FRAGENAUSWAHL:\n{fragen}"
    )


# --- Die stillgelegte Nummernwahl (06.09.2026 -> 02.10.2026) --------------
#
# Siehe tests/test_phase2_einzeln.py fuer die heutige Fragenauswahl (Vorschlag
# mit Sensibilitaetspruefung im selben Zug, Ueberblick mit Richtungsfrage,
# Frage fuer Frage). Dieser Test bleibt: ein Druck aus einer alten, schon
# verschickten Nachricht darf nicht ins Leere laufen.


def test_die_alten_toggle_knoepfe_sind_stillgelegt(conn, tg, einst, auftraege):
    """Ein Druck aus einer alten Nachricht darf nicht ins Leere laufen: er
    bekommt den neuen Weg gesagt, statt still nichts zu tun."""
    _auswahl(conn, tg)
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_FRAGE_WAHL, "3")

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}"))

    assert "Nummern" in tg.gesendet[-1][1]
    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "") == ""


# --- Eroeffnung und Abschluss ----------------------------------------------


def _mit_fragen(conn, wert="Woher kommst du?\nWas glaubst du?\nWen liebst du?"):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", wert)


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

    _druecke(conn, tg, einst, "Ja, speichern")

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


def test_fragenliste_gruppiert_fuenf_je_begriff(conn):
    """06.09.2026 11:40 (Birk, live in Gruppe 1): fuenf Fragen je Kernbegriff,
    nach Begriffen gruppiert -- 'Begriff: Frage' wird zur Ueberschrift mit
    durchlaufender Nummerierung; Zeilen ohne Begriff bleiben, wie sie sind."""
    from interview_theater import knoepfe, repo

    chat_id = -900
    repo.stelle_gruppe_sicher(conn, chat_id, "t") if hasattr(repo, "stelle_gruppe_sicher") else None
    wert = "\n".join(
        [f"Heimat: Frage {i}?" for i in range(1, 6)]
        + [f"Streit: Frage {i}?" for i in range(6, 11)]
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", wert)
    liste = knoepfe.fragenliste(conn, chat_id)
    assert liste.startswith("Heimat\n1. Frage 1?")
    assert "\n\nStreit\n6. Frage 6?" in liste
    assert "10. Frage 10?" in liste
    assert "Heimat: " not in liste

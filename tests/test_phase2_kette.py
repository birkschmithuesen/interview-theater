"""Die Kette der Phase 2, an ihren zwei offenen Stellen gemessen
(06.09.2026, Birk, 10:10 und 10:25).

Zwei Dinge, die der Testabend gezeigt hat und die vorher nirgends geprueft
waren:

1. **Die Arbeitszeile** (``ablauf.arbeitet_sichtbar``): nach dem Speichern
   der Fragen schwieg der Bot minutenlang, und die Gruppe wusste nicht, ob
   noch etwas kommt. Die Zeile geht SOFORT raus und verschwindet wieder,
   wenn die Antwort da ist -- eine Arbeitsmeldung, die stehen bleibt, liest
   sich beim naechsten Blick wie eine haengende Aufgabe.

2. **Die Invariante der Phase 2**: nach JEDEM "Ja, speichern" folgt
   eine Aktion, nie Stille. Fragen -> Sensibilitaetspruefung; Einleitungen
   -> Eroeffnungs-Auftrag; Eroeffnung -> Abschlussnachricht mit
   "Weiter zu Interviews". Der Live-Befund vom 10:25 war das Gegenteil:
   nach dem letzten Druck stand nichts mehr da.

Kein Netzzugriff, kein Sprachmodell -- die Modellwege werden aufgezeichnet
(Zusage 2, AGENTS.md).
"""

import pytest

from interview_theater import ablauf, knoepfe, leitfaden, phasen, repo

from test_knoepfe import TelegramAttrappe, _druck


class TelegramMitLoeschen(TelegramAttrappe):
    """Wie die Attrappe aus ``test_knoepfe``, nur zeichnet sie auch
    ``loesche_nachrichten`` auf -- daran haengt die halbe Arbeitszeile."""

    def __init__(self):
        super().__init__()
        self.geloescht = []

    def tippt(self, chat_id):
        pass

    def loesche_nachrichten(self, chat_id, message_ids):
        self.geloescht.extend(message_ids)
        return len(message_ids)

    def aktualisiere_knoepfe(self, chat_id, message_id, knoepfe_):
        self.knoepfe.append((chat_id, None, list(knoepfe_)))


@pytest.fixture
def tg():
    return TelegramMitLoeschen()


@pytest.fixture
def auftraege(monkeypatch):
    """Zeichnet Anweisung UND Arbeitszeile auf -- statt ein Modell zu rufen."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None):
        gesammelt.append((anweisung, arbeitszeile))
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung, klm=None):
    knoepfe.behandle(conn, tg, klm, einst, _druck(_knopf(tg, beschriftung)))


def _mit_fragen(conn, wert="Woher kommst du?\nWas glaubst du?\nWen liebst du?"):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", wert)


# --- 1. Die Arbeitszeile (10:10) ------------------------------------------


def test_die_arbeitszeile_geht_sofort_raus_und_wird_wieder_geloescht(tg):
    """Der ganze Sinn in einem Test: sichtbar VOR der Wartezeit, weg danach."""
    with ablauf.arbeitet_sichtbar(tg, 1, "🤔 Ich sehe die Fragen kurz durch …"):
        assert tg.gesendet == [(1, "🤔 Ich sehe die Fragen kurz durch …")]
        assert tg.geloescht == [], "waehrend der Arbeit bleibt sie stehen"

    assert tg.geloescht == [501], "danach ist sie weg"


def test_ohne_text_gibt_es_keine_arbeitszeile(tg):
    """``arbeitet_sichtbar`` ohne Text ist die reine Tippanzeige -- alle
    alten Aufrufer duerfen unveraendert bleiben."""
    with ablauf.arbeitet_sichtbar(tg, 1):
        pass

    assert tg.gesendet == []
    assert tg.geloescht == []


def test_ein_fehlschlag_beim_loeschen_reisst_den_zug_nicht_mit(tg):
    """Schmuck darf einen Gespraechszug nie mitreissen (SPEC § 11.1)."""
    def _kaputt(chat_id, message_ids):
        raise RuntimeError("Telegram sagt nein")

    tg.loesche_nachrichten = _kaputt

    with ablauf.arbeitet_sichtbar(tg, 1, "arbeite …"):
        pass  # kein Fehler nach aussen


def test_die_sensibilitaetspruefung_traegt_ihre_arbeitszeile(
    conn, tg, einst, auftraege,
):
    _mit_fragen(conn)

    knoepfe.starte_sensibilitaetspruefung(conn, tg, object(), einst, 1)

    assert auftraege[0][1] == knoepfe.TEXT_ARBEIT_SENSIBILITAET


def test_der_eroeffnungsauftrag_traegt_seine_arbeitszeile(
    conn, tg, einst, auftraege,
):
    _mit_fragen(conn)

    knoepfe.starte_eroeffnung(conn, tg, object(), einst, 1)

    assert auftraege[0][1] == knoepfe.TEXT_ARBEIT_EROEFFNUNG


# --- 2. Die Invariante: nach jedem "Gefaellt uns" folgt eine Aktion --------


def test_nach_den_fragen_folgt_die_sensibilitaetspruefung(
    conn, tg, einst, auftraege,
):
    phasen.setze(conn, 1, 2, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "Hier sind zehn.\n\nVORSCHLAG FRAGENAUSWAHL:\n"
        + "\n".join(f"Frage {n}?" for n in range(1, 11)),
    )

    knoepfe.nimm_fragennummern(conn, tg, None, einst, 1, "2, 5 und 9")

    assert len(auftraege) == 1
    assert "VORSCHLAG FRAGEN WEICH:" in auftraege[0][0]


def test_nach_den_einleitungen_folgt_der_eroeffnungsauftrag(
    conn, tg, einst, auftraege,
):
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG EINLEITUNGEN:\n1 — Du musst nicht antworten."
    )

    _druecke(conn, tg, einst, "Ja, speichern")

    assert len(auftraege) == 1
    assert "VORSCHLAG EROEFFNUNG:" in auftraege[0][0]


def _mit_eroeffnungsvorschlag(conn, tg):
    _mit_fragen(conn)
    repo.setze_arbeitsstand(conn, 1, "frage_einleitungen", "Keine noetig.")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG EROEFFNUNG:\n"
        "Hallo, wir sind vom Theaterprojekt im Verein.\n"
        "Abschluss: Danke dir.",
    )


def test_nach_der_eroeffnung_folgt_die_abschlussnachricht(
    conn, tg, einst, auftraege,
):
    """**Der Kettenschluss** (10:25): mit Eroeffnung und Abschluss ist
    Phase 2 fertig -- also kommt sofort das Angebot, nicht Stille."""
    _mit_eroeffnungsvorschlag(conn, tg)

    _druecke(conn, tg, einst, "Ja, speichern")

    letzte = [b for b, _ in tg.knoepfe[-1][2]]
    assert letzte == [
        f"Weiter zu {phasen.knopfbezeichnung(3)}", "Noch etwas aendern",
    ]
    assert tg.knoepfe[-1][1].endswith(
        f"Weiter zu {phasen.knopfbezeichnung(3)}?"
    )


def test_mit_der_eroeffnung_kommt_der_leitfaden_und_sein_knopf(
    conn, tg, einst, auftraege,
):
    """Der Leitfaden steht jetzt -- die Gruppe sieht ihn, ohne zu fragen,
    und behaelt ihn ueber den Knopf erreichbar."""
    _mit_eroeffnungsvorschlag(conn, tg)

    _druecke(conn, tg, einst, "Ja, speichern")

    assert any(t.startswith(leitfaden.TEXT_KOPF) for _, t in tg.gesendet)
    assert leitfaden.steht(conn, 1)


def test_die_kette_endet_nie_stumm(conn, tg, einst, auftraege):
    """Die Invariante als ein Test ueber die ganze Kette: nach JEDEM
    "Ja, speichern" in Phase 2 steht entweder ein Auftrag an oder
    eine Nachricht mit Knoepfen -- nie nichts."""
    _mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG EINLEITUNGEN:\n1 — Du musst nicht antworten."
    )
    _druecke(conn, tg, einst, "Ja, speichern")
    assert len(auftraege) == 1, "Schritt 1: Eroeffnungs-Auftrag"

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG EROEFFNUNG:\nHallo, wir sind da.\nAbschluss: Danke dir.",
    )
    vorher = len(tg.knoepfe)
    _druecke(conn, tg, einst, "Ja, speichern")

    assert len(tg.knoepfe) > vorher, "Schritt 2: das Phasenangebot"
    assert phasen.voraussetzungen(conn, 1)[3] is True

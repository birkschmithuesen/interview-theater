"""Regressionstest: die Kette geht nach der Eroeffnung automatisch weiter zu
Phase 3 (Task 4, Padua Phase-2-Ende, Befund 3 -- Karte t_8f1adaa4).

``fragen.py::_speichere_eroeffnung`` ruft am Ende der Kette
(Fragen -> Sensibilitaet -> Einleitungen -> Eroeffnung) automatisch
``uebergang_nach_speichern``/``biete_phase_proaktiv``, sobald Eroeffnung UND
Abschluss gesetzt sind -- OHNE dass die Gruppe nochmal fragen muss. Dieser
Test beweist das end-to-end: einmal ueber den klassischen Weg (direkter
Aufruf von ``_speichere_eroeffnung``, wie es "Ja, speichern" am Ende des
Eroeffnungs-Auftragszugs tut) und einmal ueber den Redo-Pfad aus Task 3
(Undo auf einen Fragen-Abschluss, dann Redo, dann die Eroeffnung).

**Befund beim Schreiben dieses Tests (keine Codeaenderung noetig, aber eine
Abweichung vom woertlichen Kartentext):** in beiden Szenarien hier
(Phase 2, Fragen schon gesetzt, nur Eroeffnung+Abschluss fehlen noch) liefert
``phasen.naechste_moegliche`` sofort 3, sobald die Eroeffnung steht --
``uebergang_nach_speichern`` feuert deshalb IMMER als ERSTER Zweig der
Weiche in ``_speichere_eroeffnung`` (``if not uebergang_nach_speichern(...):
biete_phase_proaktiv(...)``) und schaltet die Phase DIREKT um
(``phasen.setze`` + ``eintritt_in_phase``, inkl. der Meldung
"Wir sind jetzt bei 3 ..."). ``biete_phase_proaktiv`` (das Angebot mit den
Knoepfen "Weiter zu Phase 3" / "Noch etwas aendern") kommt in DIESEM Pfad
nie zum Zug -- das ist seit dem 02.10.2026 (Padua) ausdruecklich so gebaut,
siehe der Kommentar in ``knoepfe/basis.py::_speichere`` um Zeile 919: "Ja,
speichern" auf die Eroeffnung schliesst Phase 2 direkt ab, kein zweites
Angebot. Die Tests pruefen deshalb den tatsaechlichen, beobachtbaren Ausgang
(die Phase wechselt automatisch, die Gruppe erfaehrt es per Nachricht)
statt eine Angebots-Form zu erzwingen, die hier nie auftritt -- siehe den
Mutationstest-Abschnitt im Task-4-Bericht fuer den empirischen Beleg, dass
ein No-Op von ``biete_phase_proaktiv`` allein diese Tests NICHT rot macht.

Kein Netz, kein Modell: ``_speichere_eroeffnung`` wird direkt mit einem
synthetischen, schon zerlegten ``wert`` aufgerufen (ihre Signatur nimmt den
fertigen Text entgegen, keinen rohen ``VORSCHLAG EROEFFNUNG:``-Block -- das
Zerlegen passiert lediglich an Zeilenkoepfen wie "Eroeffnung:"/"Abschluss:",
siehe ``fragen._speichere_eroeffnung``). Fuer den Redo-Pfad wird der
Auftragszug wie in ``tests/test_redo_knopf.py`` aufgezeichnet statt
ausgefuehrt."""

import pytest

from interview_theater import ablauf, knoepfe, phasen, repo

from test_knoepfe import TelegramAttrappe
from test_redo_knopf import (
    TelegramAttrappe as RedoTelegramAttrappe,
    _druck,
    _knopf_der_letzten_leiste_mit_art,
    _schliesse_beide_fragen_ab,
)


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    """Auftragszuege (hier: die Eroeffnung nach dem Fragen-Abschluss) werden
    aufgezeichnet statt ausgefuehrt -- derselbe Fang wie in
    ``tests/test_redo_knopf.py``, damit kein Modell gebraucht wird."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


#: Der klassische Abschlussblock, wie er aus einem geparsten
#: ``VORSCHLAG EROEFFNUNG:`` entstehen wuerde -- ``_speichere_eroeffnung``
#: nimmt den schon zerlegten Text, keinen rohen Markerblock.
EROEFFNUNG_WERT = (
    "Eroeffnung: Hallo, schoen dass du dir Zeit fuer uns nimmst.\n"
    "Abschluss: Vielen Dank, dass du das mit uns geteilt hast."
)


def _bereite_phase_2_mit_fragen_vor(conn, chat_id: int = 1) -> None:
    """Phase 2, alle Phase-3-Voraussetzungen AUSSER Eroeffnung/Abschluss:
    Fragen stehen, ``fragen_weich`` ist geprueft (leerer String zaehlt als
    geprueft, ``phasen._feld_geprueft``)."""
    phasen.setze(conn, chat_id, 2, "test")
    repo.setze_arbeitsstand(
        conn, chat_id, "fragen",
        "Heimat: Wann hast du dich zuletzt fremd gefuehlt?",
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")


# --- 1. Der klassische Weg --------------------------------------------------


def test_klassischer_weg_geht_ohne_nachfrage_weiter_zu_phase_3(conn, tg):
    _bereite_phase_2_mit_fragen_vor(conn)
    assert phasen.voraussetzungen(conn, 1)[3] is False, (
        "ohne Eroeffnung/Abschluss darf Phase 3 noch nicht erreichbar sein"
    )

    knoepfe._speichere_eroeffnung(conn, tg, 1, EROEFFNUNG_WERT)

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["interview_eroeffnung"] or "").strip()
    assert (stand["interview_abschluss"] or "").strip()
    assert phasen.voraussetzungen(conn, 1)[3] is True

    # Ohne weiteres Zutun der Gruppe: die Kette hat selbst weitergemacht.
    assert phasen.aktuelle(conn, 1) == 3, (
        "die Eroeffnungs-Kette muss die Gruppe automatisch in Phase 3 "
        "weiterfuehren, sobald Eroeffnung UND Abschluss stehen"
    )
    assert phasen.meldung(3) in tg.texte


# --- 2. Derselbe Ausgang ueber den Redo-Pfad (Task 3) -----------------------


def test_ueber_redo_geht_die_eroeffnung_ebenfalls_automatisch_weiter(
    conn, einst, auftraege,
):
    tg = RedoTelegramAttrappe()
    _schliesse_beide_fragen_ab(conn, tg, einst)

    undo_daten, undo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_UNDO)
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(undo_daten, message_id=undo_message, query_id="q-undo"),
    )
    assert not (repo.hole_arbeitsstand(conn, 1)["fragen"] or "").strip()

    redo_daten, redo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_REDO)
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(redo_daten, message_id=redo_message, query_id="q-redo"),
    )

    # Nach dem Redo: Fragen wiederhergestellt, Eroeffnung/Abschluss fehlen
    # noch (Task 3 hat nur den Auftragszug angestossen, nicht ausgefuehrt --
    # ``auftraege`` zeichnet ihn auf, statt ein Modell zu rufen).
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["fragen"], "Redo hat die Fragen wiederhergestellt"
    assert phasen.voraussetzungen(conn, 1)[3] is False
    assert phasen.aktuelle(conn, 1) == 2

    # Der (in Wirklichkeit vom Modell gelieferte) Eroeffnungstext kommt an --
    # derselbe Weg wie "Ja, speichern" am Ende dieses Auftragszugs.
    knoepfe._speichere_eroeffnung(conn, tg, 1, EROEFFNUNG_WERT)

    assert phasen.voraussetzungen(conn, 1)[3] is True
    assert phasen.aktuelle(conn, 1) == 3, (
        "auch nach dem Redo-Pfad muss die Eroeffnung automatisch weiter "
        "zu Phase 3 fuehren, ohne dass die Gruppe extra nachfragen muss"
    )
    assert phasen.meldung(3) in tg.texte

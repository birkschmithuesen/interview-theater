"""Rueckgaengig auch nach "Fragen einzeln" (UX-Knoepfe-Karte, Abschnitt 2).

Der Abschluss von Phase 2 ("Annehmen"/"Verwerfen" bis alle Fragen entschieden
sind, ``knoepfe.fragen._schliesse_fragen_ab``) schrieb bis dahin
``arbeitsstand.fragen`` ohne jede Ruecknahme -- wie "Ja, speichern" vorher.
Dieselbe Maschine wie dort (``erkenner.lauf_fuer_knopf``): die Quittung
"Notiert, eure N Fragen:" bekommt einen Undo-Knopf, und ein Druck macht die
Fragen wieder zum offenen, einzeln entschiedenen Zustand (nicht nur leer).

Kein Netz, kein Modell: Auftragszuege werden aufgezeichnet statt ausgefuehrt
(dieselbe Zusage wie in ``tests/test_phase2_einzeln.py``)."""

import pytest

from interview_theater import ablauf, knoepfe, phasen, repo

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
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
    "Streit: Wann habt ihr zuletzt richtig gestritten?"
)


def _vorschlag_zeigen(conn, tg, wert=VORSCHLAG):
    phasen.setze(conn, 1, 2, "befehl")
    return knoepfe.sende_mit_speicherleiste(conn, tg, 1, wert)


def _undo_knopf_id(conn, tg):
    return next(
        int(daten.split(":")[1])
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"] == knoepfe.ART_UNDO
    )


def test_der_abschluss_haengt_einen_undo_knopf_an(conn, tg, einst, auftraege):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "nein")

    assert repo.hole_arbeitsstand(conn, 1)["fragen"]
    assert _undo_knopf_id(conn, tg) is not None


def test_undo_stellt_die_einzeln_entschiedenen_fragen_wieder_her(
    conn, tg, einst, auftraege,
):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)

    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "nein")
    lauf_knopf_id = _undo_knopf_id(conn, tg)

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{lauf_knopf_id}"))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand["fragen"] or "").strip()
    assert stand["fragen_entschieden"] == "ja,nein"

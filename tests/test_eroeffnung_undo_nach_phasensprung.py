"""Padua-Befund M2 (Feedbackloop P1-2, Runde 2, 05.10.2026): der Undo-Knopf
der automatisch gespeicherten Eroeffnung war sofort verbraucht.

Gemessen in ``simulation/browser_laeufe/2026-10-05-handy-giulia-p12/sim.db``:
knopf 72 (``undo``, Nachricht 120, die 📌-Zeile der Eroeffnung) hat
``erstellt_am = benutzt_am`` 16:07:38; in derselben Sekunde kamen die
Phase-3-Meldung (124) und die Frage nach der Interviewsprache (125, knopf
73-75). Verbraucher: ``knoepfe.basis._kollabiere_letzten_einsamen_undo`` --
``biete_stt_sprache`` sendet ueber ``_sende_knoepfe``, und die zuletzt
angelegte Knopfnachricht war die einsame Undo-Quittung der Eroeffnung. Das
ist der NORMALE Weg (Autosave -> ``uebergang_nach_speichern`` ->
``eintritt_in_phase(3)``), nicht nur der Redo-Weg des Simulationslaufs.

Die Sprachwahl ist kein zweiter Speicherweg fuer dieselbe Sache -- sie
konkurriert nicht mit dem Undo (dieselbe Abwaegung wie ``undo_behalten``
beim Eintritt in Phase 2, ``fragen.sende_mit_vorschlagen``).

Kein Netz, kein Modell."""

import pytest

from interview_theater import knoepfe, phasen, repo, sprache, workshop

from test_knoepfe import TelegramAttrappe, _druck


VORSCHLAG_EROEFFNUNG = (
    "Here is the opening.\n\nVORSCHLAG EROEFFNUNG:\n"
    "Hi, I am part of a theatre project.\n"
    "ABSCHLUSS: Thank you for your time!"
)


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setattr(workshop, "autosave_phase1_2_aktiv", lambda *a, **k: True)
    # Padua laesst die Interviewsprache offen -> die Sprachwahl-Leiste kommt
    # beim Eintritt in Phase 3 (Karte A1).
    monkeypatch.setattr(sprache, "whisper_vorgabe", lambda *a, **k: sprache.AUTO)


def _eroeffnung_mit_sprung(conn, tg, einst):
    phasen.setze(conn, 1, 2, "test")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Wann warst du zuletzt fremd?")
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", "")
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)


def _eroeffnungs_undo(tg):
    """(message_id, daten) des Undo-Knopfs unter der 📌-Zeile der
    Eroeffnung -- der einzige Undo-Knopf in diesem Ablauf."""
    undo = [
        (message_id, daten)
        for message_id, _, leiste in tg.knoepfe
        for beschriftung, daten in leiste
        if beschriftung == "Rueckgaengig"
    ]
    assert len(undo) == 1, tg.knoepfe
    return undo[0]


def _knopf_id(daten: str) -> int:
    return int(daten.split(":", 1)[1])


def test_eroeffnungs_undo_bleibt_nach_dem_sprung_in_phase_3_bedienbar(
    conn, tg, einst, padua,
):
    _eroeffnung_mit_sprung(conn, tg, einst)

    assert phasen.aktuelle(conn, 1) == 3, "der normale Weg springt in Phase 3"
    sprachwahl = {beschriftung for _, beschriftung in knoepfe.STT_KNOEPFE}
    assert any(
        b in sprachwahl for _, _, leiste in tg.knoepfe for b, _ in leiste
    ), "die Sprachwahl muss gekommen sein (Phase-3-Eintritt)"

    message_id, daten = _eroeffnungs_undo(tg)
    assert repo.hole_knopf(conn, _knopf_id(daten))["benutzt_am"] is None, (
        "M2: der Undo der Eroeffnung darf beim Phasensprung nicht verfallen"
    )
    assert (1, message_id) not in tg.entfernt, (
        "die Tastatur der 📌-Zeile darf nicht abgenommen werden"
    )

    ergebnis = knoepfe.behandle(
        conn, tg, None, einst, _druck(daten, message_id=message_id),
    )

    assert ergebnis is True
    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand["interview_eroeffnung"] or "").strip()
    assert not (stand["interview_abschluss"] or "").strip()


def test_naechste_leiste_in_phase_3_laesst_den_undo_ebenfalls_stehen(
    conn, tg, einst, padua,
):
    """Die allgemeine Kollisionsregel (``_kollabiere_letzten_einsamen_undo``)
    greift nur auf die ZULETZT angelegte Knopfnachricht -- nach der
    Sprachwahl ist das nicht mehr die 📌-Zeile, also bleibt der Undo auch
    beim naechsten Angebot (hier: Aufnahme starten) stehen."""
    _eroeffnung_mit_sprung(conn, tg, einst)
    _, daten = _eroeffnungs_undo(tg)

    knoepfe.biete_aufnahme(conn, tg, 1, "Start?")

    assert repo.hole_knopf(conn, _knopf_id(daten))["benutzt_am"] is None

"""Messung (Karte t_1bc96848, Teil 2, Aufgabe 4): die tatsaechliche
Zeichenzahl der drei Prompt-Bloecke, die den Phase-5-Rohdump durch das
Phasen-Summary ersetzen, VOR (Rohdump) und NACH (Summary-Ersatz) --
gegen realistische Testdaten (ein mehrere Tausend Zeichen langes P5-
Gespraech, Szenen, Festlegungen), nicht gegen einen erfundenen Schaetzwert.

Gemessen werden (Moduldocstring ``interview_theater/phasen_summary.py``):

- ``szene.p5_gespraech_block`` / ``szene._p5_gespraech_text``
- ``entwurf._voll_bloecke`` (Uebersicht/Logline-Nutzertext)
- ``schaerfung._hintergrund_voll_zeilen`` (Matcher-Hintergrund)

Jeder Block wird einmal mit ``workshop.phasen_summary_aktiv`` aus bzw.
Phase 5 noch AKTUELL (Rohdump) und einmal mit Schalter an, Phase
ABGESCHLOSSEN und einem gespeicherten Summary gemessen (Summary-Ersatz).
Die Zahlen gehen per ``print`` auf die Konsole (sichtbar mit ``pytest -s``)
und stehen zusaetzlich in den Assertions fest -- als Verhaeltnis
(deutlich kuerzer), nicht als brueckiger Exaktwert, der bei der naechsten
Testdatenaenderung grundlos rot wird.
"""

import pytest

from interview_theater import entwurf, phasen_summary, repo, schaerfung, szene, workshop

#: Realistische, variierte Gespraechssaetze -- keine Namen der Interviewten
#: (AGENTS.md), frei erfunden wie das Beispieltranskript in scripts/rauchtest.py.
_SAETZE = [
    "Let's use interview 3 for the kitchen scene, the part about the suitcase.",
    "I think Mira should enter first and the light comes on slowly.",
    "The sign reading CLOSED felt too on-the-nose, let's drop it.",
    "What if the scene ends with her just sitting down, no line at all?",
    "We agreed the tram sound should be in the background the whole time.",
    "Can we keep the bit about the mother not understanding the theatre?",
    "I liked the image of the suitcase more than an actual explanation.",
    "Let's not invent a conflict that wasn't in any of the interviews.",
    "The friend who moved away could be a voice offstage, not a character.",
    "Should the kitchen scene come before or after the station scene?",
    "I'd rather keep the ending open than force a reconciliation.",
    "The quiet after 'the hall goes completely still' is the whole point.",
]


def _realistisches_phase5_gespraech(conn, chat_id: int = 1, anzahl: int = 140) -> None:
    """Haengt ``anzahl`` Chatzeilen seit dem Eintritt in Phase 5 an --
    mehrere Tausend Zeichen, wie ein echter Workshop-Nachmittag
    (``phasen_summary``-Moduldocstring: 16.710 Zeichen gemessen)."""
    repo.schreibe_journal(
        conn, chat_id, "entschieden", "Phase 5 · Prose Draft", quelle="test",
    )
    seit = repo.phase_eintritt_zeitpunkt(conn, chat_id, "Phase 5")
    for i in range(anzahl):
        absender = "Gruppe" if i % 2 == 0 else "Du"
        satz = _SAETZE[i % len(_SAETZE)]
        repo.merke_nachricht(
            conn, chat_id, 1000 + i, absender, 0 if absender == "Gruppe" else 1,
            "text", satz, seit,
        )


#: Ein Summary, so gross wie ein echter Modell-Lauf es lieferte (nicht der
#: Deckel ``MAX_ZEICHEN``, sondern ein realistischer Umfang darunter --
#: "anderthalb Dutzend kurze Zeilen", Moduldocstring).
_SUMMARY_ERGEBNIS = {
    "entscheidungen": [
        "Use interview 3 for the kitchen scene (the suitcase).",
        "Mira enters first, light comes on slowly.",
        "Keep the tram sound in the background throughout.",
        "Keep the detail about the mother not understanding the theatre.",
        "The friend who moved away stays an offstage voice.",
        "Kitchen scene comes before the station scene.",
        "End on the silence, no closing line.",
    ],
    "discarded": [
        "A sign reading CLOSED -- too on-the-nose.",
        "A forced reconciliation at the end.",
        "Inventing a conflict absent from the interviews.",
    ],
    "offene_punkte": [
        "Whether the station scene needs a second voice.",
        "How long the closing silence should run.",
    ],
}


def _speichere_realistisches_summary(conn, chat_id: int = 1, phase: int = 5) -> str:
    text = phasen_summary.baue_text(_SUMMARY_ERGEBNIS, phase)
    repo.speichere_phasen_summary(conn, chat_id, phase, text)
    return text


@pytest.fixture(autouse=True)
def mitgehoert_voll(monkeypatch):
    """``_p5_gespraech_text``/``_voll_bloecke``/``_hintergrund_voll_zeilen``
    liefern nur unter diesem Schalter etwas (Padua) -- an, wie in
    tests/test_phasen_summary_injektion.py."""
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)


def _vorher(conn, monkeypatch, chat_id: int = 1) -> None:
    """Phase 5 ist die aktuelle -- der Rohdump bleibt, mit ODER ohne
    Profilschalter (Moduldocstring: 'solange Phase 5 noch die AKTUELLE
    Phase ist')."""
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    repo.setze_phase(conn, chat_id, 5)


def _nachher(conn, monkeypatch, chat_id: int = 1) -> None:
    """Phase 5 ist abgeschlossen (Gruppe in Phase 6) und ein Summary liegt
    vor -- das Summary tritt an die Stelle des Rohdumps."""
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    repo.setze_phase(conn, chat_id, 6)


# ---------------------------------------------------------------------------
# szene.p5_gespraech_block / szene._p5_gespraech_text
# ---------------------------------------------------------------------------


def test_messung_szene_p5_gespraech_block(conn, monkeypatch, capsys):
    _realistisches_phase5_gespraech(conn)
    _speichere_realistisches_summary(conn)

    _vorher(conn, monkeypatch)
    rohdump = szene.p5_gespraech_block(conn, 1)

    _nachher(conn, monkeypatch)
    summary = szene.p5_gespraech_block(conn, 1)

    with capsys.disabled():
        print(f"\n[Messung] szene.p5_gespraech_block VOR (Rohdump):   "
              f"{len(rohdump)} Zeichen")
        print(f"[Messung] szene.p5_gespraech_block NACH (Summary):  "
              f"{len(summary)} Zeichen")

    assert len(rohdump) > 5_000, "die Testdaten sollen realistisch gross sein"
    assert len(summary) < len(rohdump) / 3
    assert summary == phasen_summary.hole_text(conn, 1, 5)


# ---------------------------------------------------------------------------
# entwurf._voll_bloecke
# ---------------------------------------------------------------------------


def _bereite_entwurf_daten(conn, chat_id: int = 1) -> None:
    repo.stelle_szene_sicher(conn, chat_id, 1)
    repo.stelle_szene_sicher(conn, chat_id, 2)
    repo.schreibe_festlegung(conn, chat_id, "setting", "A kitchen, late at night.")
    repo.schreibe_festlegung(conn, chat_id, "figur", "Mira wants to be heard.",
                             bezug="Mira")


def test_messung_entwurf_voll_bloecke(conn, monkeypatch, capsys):
    _realistisches_phase5_gespraech(conn)
    _speichere_realistisches_summary(conn)
    _bereite_entwurf_daten(conn)

    _vorher(conn, monkeypatch)
    vorher = "\n\n".join(entwurf._voll_bloecke(conn, 1))

    _nachher(conn, monkeypatch)
    nachher = "\n\n".join(entwurf._voll_bloecke(conn, 1))

    with capsys.disabled():
        print(f"\n[Messung] entwurf._voll_bloecke VOR (Rohdump):      "
              f"{len(vorher)} Zeichen")
        print(f"[Messung] entwurf._voll_bloecke NACH (Summary):     "
              f"{len(nachher)} Zeichen")

    assert len(vorher) > 5_000
    assert len(nachher) < len(vorher) / 2


# ---------------------------------------------------------------------------
# schaerfung._hintergrund_voll_zeilen
# ---------------------------------------------------------------------------


def _bereite_schaerfung_daten(conn, chat_id: int = 1) -> None:
    repo.schreibe_festlegung(conn, chat_id, "setting", "A kitchen, late at night.")
    repo.setze_arbeitsstand(conn, chat_id, "geschichte_uebersicht",
                            "Logline: Two sisters meet again after years apart.")


def test_messung_schaerfung_hintergrund_voll_zeilen(conn, monkeypatch, capsys):
    _realistisches_phase5_gespraech(conn)
    _speichere_realistisches_summary(conn)
    _bereite_schaerfung_daten(conn)

    _vorher(conn, monkeypatch)
    stand_vorher = repo.hole_arbeitsstand(conn, 1)
    vorher = "\n".join(schaerfung._hintergrund_voll_zeilen(conn, 1, stand_vorher))

    _nachher(conn, monkeypatch)
    stand_nachher = repo.hole_arbeitsstand(conn, 1)
    nachher = "\n".join(schaerfung._hintergrund_voll_zeilen(conn, 1, stand_nachher))

    with capsys.disabled():
        print(f"\n[Messung] schaerfung._hintergrund_voll_zeilen VOR:  "
              f"{len(vorher)} Zeichen")
        print(f"[Messung] schaerfung._hintergrund_voll_zeilen NACH: "
              f"{len(nachher)} Zeichen")

    assert len(vorher) > 5_000
    assert len(nachher) < len(vorher) / 2

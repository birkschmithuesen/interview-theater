"""Der Debrief-Block "So arbeitet diese Gruppe" im Gespraechs-Prompt und in
allen drei Schreibwegen (Task 4, Karte phasen-debrief).

Gespeicherte Phasen-Debriefs (``repo.phasen_debriefs``, Task 1-3) werden erst
hier **sichtbar**: im Gespraechs-Prompt (``kontext.baue``) fuer spaetere
Phasen, und in jedem Szenen-/Geschichten-Prompt (``szene.py``,
``kurzgeschichte.py``, ``szenenfolge.py``). Erkenner, Journal-Extraktor und
Verdichter bauen ihre Prompts unabhaengig von ``kontext.py`` und bekommen den
Block nie (negativer Test unten).

Kein Netzzugriff, keine Hintergrund-Threads: die Debriefs werden hier direkt
ueber ``repo.merke_phasen_debrief`` angelegt, ohne den Modellaufruf aus
``phasen_debrief.py`` anzustossen.
"""

import pytest

from interview_theater import (
    erkenner, journal, kontext, kurzgeschichte, phasen, repo, szene,
    szenenfolge, verdichter,
)


def test_ohne_debrief_kein_block(conn):
    assert kontext.baue_debrief_block(conn, 1) == ""


def test_debrief_block_traegt_kopf_und_phasenbezeichnung(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Die Gruppe entscheidet schnell.", "gemma")

    block = kontext.baue_debrief_block(conn, 1)

    assert block.startswith(kontext.DEBRIEF_KOPF)
    assert f"### {phasen.bezeichnung(3)}" in block
    assert "Die Gruppe entscheidet schnell." in block


def test_mehrere_debriefs_stehen_aelteste_phase_zuerst(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Erster Rueckblick.", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Zweiter Rueckblick.", "gemma")

    block = kontext.baue_debrief_block(conn, 1)

    assert block.index("Erster Rueckblick.") < block.index("Zweiter Rueckblick.")


def test_geloeschter_debrief_faellt_aus_dem_block(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Soll verschwinden.", "gemma")
    repo.entferne_phasen_debrief(conn, 1, 1)

    assert kontext.baue_debrief_block(conn, 1) == ""


def test_block_steht_direkt_hinter_den_festlegungen():
    reihenfolge = list(kontext._REIHENFOLGE)
    assert reihenfolge[reihenfolge.index("festlegungen") + 1] == "debrief"


def test_budget_ist_800_token_nicht_2400():
    assert kontext.BUDGETS["debrief"] == 800


def test_kappung_verwirft_die_aelteste_phase_zuerst(conn):
    """Drei Debriefs mit je ~1000 Zeichen Text sprengen das Budget von 800
    Token (= 2.400 Zeichen) -- die aelteste Phase (die kleinste Nummer)
    fliegt zuerst, die juengeren bleiben stehen."""
    repo.merke_phasen_debrief(conn, 1, 1, "A" * 1000, "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "B" * 1000, "gemma")
    repo.merke_phasen_debrief(conn, 1, 3, "C" * 1000, "gemma")

    block = kontext.baue_debrief_block(conn, 1)

    assert "A" * 1000 not in block
    assert "B" * 1000 in block
    assert "C" * 1000 in block
    assert kontext.schaetze(block) <= kontext.BUDGETS["debrief"] + 1


def test_alle_debriefs_zu_gross_ergibt_leeren_block(conn):
    """Passt nicht einmal die juengste Phase hinein, bleibt gar nichts
    stehen -- kein halber Abschnitt."""
    repo.merke_phasen_debrief(conn, 1, 1, "X" * 5000, "gemma")

    assert kontext.baue_debrief_block(conn, 1) == ""


def test_debrief_erscheint_im_gespraechs_prompt_einer_spaeteren_phase(conn, einst):
    repo.merke_phasen_debrief(conn, 1, 3, "Die Gruppe diskutiert laut.", "gemma")
    phasen.setze(conn, 1, 4, "befehl")
    repo.merke_nachricht(conn, 1, 1, "Sara", 0, "text", "weiter", "2026-09-06T10:00:00")
    ausloeser = [repo.hole_nachricht(conn, 1, 1)]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert kontext.DEBRIEF_KOPF in prompt
    assert "Die Gruppe diskutiert laut." in prompt


# ---------------------------------------------------------------------------
# Szenen-schreibende Pfade: derselbe Block, dieselbe Quelle
# ---------------------------------------------------------------------------


def test_debrief_erscheint_im_szenen_prompt(conn, einst):
    repo.merke_phasen_debrief(conn, 1, 3, "Die Gruppe ringt lange um Details.", "gemma")

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert kontext.DEBRIEF_KOPF in text
    assert "Die Gruppe ringt lange um Details." in text


def test_debrief_steht_nach_continuity_und_verworfen_vor_chat():
    reihenfolge = list(szene._REIHENFOLGE)
    assert reihenfolge.index("continuity") < reihenfolge.index("debrief")
    assert reihenfolge.index("verworfen") < reihenfolge.index("debrief")
    assert reihenfolge.index("debrief") < reihenfolge.index("chat")


def test_debrief_erscheint_im_kurzgeschichte_prompt(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Ein Bild traegt mehr als ein Argument.", "gemma")

    text = kurzgeschichte.baue_nutzertext(conn, 1)

    assert kontext.DEBRIEF_KOPF in text
    assert "Ein Bild traegt mehr als ein Argument." in text


def test_debrief_erscheint_in_beiden_szenenfolge_prompts(conn):
    repo.merke_phasen_debrief(conn, 1, 2, "Die Gruppe zoegert vor Entscheidungen.", "gemma")

    geschichte = szenenfolge.baue_nutzertext_geschichte(conn, 1)
    folge = szenenfolge.baue_nutzertext(conn, 1, 4)

    assert kontext.DEBRIEF_KOPF in geschichte
    assert "Die Gruppe zoegert vor Entscheidungen." in geschichte
    assert kontext.DEBRIEF_KOPF in folge
    assert "Die Gruppe zoegert vor Entscheidungen." in folge


# ---------------------------------------------------------------------------
# Negativ: Erkenner, Journal-Extraktor und Verdichter bauen eigene Prompts
# und bekommen den Block nie.
# ---------------------------------------------------------------------------


def test_debrief_fehlt_im_erkenner_prompt(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Nur fuer den Gespraechszug.", "gemma")

    nutzer = erkenner._baue_nutzertext(conn, 1, [])

    assert kontext.DEBRIEF_KOPF not in nutzer
    assert "Nur fuer den Gespraechszug." not in nutzer


def test_debrief_fehlt_im_journal_prompt(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Nur fuer den Gespraechszug.", "gemma")

    nutzer = journal._baue_nutzertext(conn, 1, [])

    assert kontext.DEBRIEF_KOPF not in nutzer
    assert "Nur fuer den Gespraechszug." not in nutzer


def test_debrief_fehlt_im_verdichter_prompt(conn):
    """``verdichter.baue_nutzertext`` nimmt nicht einmal ``chat_id`` entgegen --
    es kann den Block strukturell gar nicht lesen. Hier trotzdem explizit
    belegt, wie von der Aufgabe verlangt."""
    repo.merke_phasen_debrief(conn, 1, 3, "Nur fuer den Gespraechszug.", "gemma")

    nutzer = verdichter.baue_nutzertext("Ein Transkript.", None)

    assert kontext.DEBRIEF_KOPF not in nutzer
    assert "Nur fuer den Gespraechszug." not in nutzer

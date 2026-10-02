"""Flow-Audit Schicht 1 (statisch, kein Modellaufruf, SPEC siehe
``simulation/flow_audit.py``).

Anlass: Birks Generalprobe -- in Phase 5 kam Chat-Feedback zu einem
Schaerfungsvorschlag an, aber es passierte nichts. Phase 5 hat im Erkenner
keinen eigenen Intent, nur Knoepfe wirken. Kein Test hat das gemeldet.

Dieser Test haelt zwei Dinge fest: dass die Erwartungsliste
(``simulation/flow_erwartungen.toml``) nicht gegen einen veralteten Code
pruefen kann (``geist``-Befunde sind in dieser Codebasis immer leer), und
dass genau der Phase-5-Fall -- sowie ein zweiter, strukturell gleicher Fall
in Phase 7 (inhaltliches Feedback statt Kuerzung) -- als "toter
Gespraechsweg" gemeldet wird. Die Mutationsprobe am Ende beweist, dass der
Mechanismus wirklich den Code prueft und nicht nur die Liste gegen sich
selbst: ein Intent, der heute existiert, verschwindet per Monkeypatch, der
Befund erscheint, und nach dem Test (automatisches Zuruecksetzen durch
``monkeypatch``) ist er wieder weg.
"""

from __future__ import annotations

from simulation import flow_audit


def test_erwartungsliste_deckt_alle_sieben_phasen_ab():
    handlungen = flow_audit.lade_erwartungen()
    phasen_mit_eintrag = {h.phase for h in handlungen}
    assert phasen_mit_eintrag == set(range(1, 8))


def test_keine_veraltete_erwartung_im_heutigen_code():
    """'geist'-Befunde heissen: die Liste nennt einen Intent oder Knopf, den
    es nicht mehr gibt. Die Liste ist Handarbeit -- bleibt sie falsch,
    melden sich alle anderen Befunde nicht mehr glaubwuerdig."""
    befunde = flow_audit.pruefe()
    geister = [b for b in befunde if b.schwere == "geist"]
    assert geister == []


def test_phase_5_schaerfung_chat_feedback_ist_ein_toter_gespraechsweg():
    """Der gemessene Fall aus der Generalprobe: Zustimmung/Aenderung zu
    einem Schaerfungsvorschlag per Chat hat keinen Erkenner-Intent."""
    befunde = flow_audit.pruefe()
    treffer = [
        b
        for b in befunde
        if b.phase == 5 and b.schwere == "toter_gespraechsweg"
    ]
    assert len(treffer) == 1
    assert "Schaerfungsvorschlag" in treffer[0].aktion


def test_phase_7_inhaltliches_feedback_ist_ebenfalls_ein_toter_gespraechsweg():
    """Derselbe Fehlerklasse wie Phase 5: 'mach die Mutter wuetender' loest
    per Chat nichts aus -- nur der Knopf 'Passt, aber anders' (ART_SZENE_ANDERS)."""
    befunde = flow_audit.pruefe()
    treffer = [
        b
        for b in befunde
        if b.phase == 7 and b.schwere == "toter_gespraechsweg"
    ]
    assert len(treffer) == 1


def test_bewusste_knopf_only_entscheidungen_sind_kein_befund():
    """'Noch eine Schaerfungsrunde' (Phase 5) und 'Geschichte schreiben'
    (Phase 6) sind bewusst nur per Knopf erreichbar -- dokumentierte
    Entwurfsentscheidungen, kein Befund."""
    befunde = flow_audit.pruefe()
    betroffen = [
        b
        for b in befunde
        if "Schaerfungsrunde" in b.aktion or "Prosa) schreiben" in b.aktion
    ]
    assert betroffen == []


def test_genau_zwei_rote_befunde_im_heutigen_stand():
    """Schliesst mit: kein unbemerktes drittes Loch, keine verschwundene
    Meldung. Steigt die Zahl, gehoert ein Blick in den Bericht dazu --
    faellt sie auf null, ist Phase 5 behoben und dieser Test ist bewusst
    anzupassen, nicht stillschweigend gruen zu uebergehen."""
    befunde = flow_audit.pruefe()
    rote = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    assert len(rote) == 2


def test_mutationsprobe_entfernter_intent_wird_als_toter_weg_gemeldet(monkeypatch):
    """Nimmt einen heute funktionierenden Weg (Phase 4, Setting per Chat
    aendern, Intent ``rahmen_setzen``) **im echten Erkenner-Modul** per
    Monkeypatch heraus -- der Befund muss ueber den ganz normalen
    ``pruefe()``-Aufruf (keine expliziten Parameter) erscheinen. Das ist der
    Beweis, dass Schicht 1 echte Regressionen am Code findet und nicht nur
    eine feste Liste gegen sich selbst spiegelt. ``monkeypatch`` setzt
    ``erkenner.ARTEN`` nach dem Test automatisch zurueck -- das ist das
    "Zuruecksetzen -> gruen" aus der Abnahme."""
    vorher = flow_audit.pruefe()
    assert not any(b.aktion.startswith("Setting/Rahmen") for b in vorher)

    from interview_theater import erkenner

    monkeypatch.setattr(
        erkenner, "ARTEN", tuple(a for a in erkenner.ARTEN if a != "rahmen_setzen")
    )

    waehrend_mutation = flow_audit.pruefe()
    treffer = [
        b
        for b in waehrend_mutation
        if b.aktion.startswith("Setting/Rahmen") and b.schwere == "toter_gespraechsweg"
    ]
    assert len(treffer) == 1

    # Die entfernte Art hinterlaesst folgerichtig auch einen zweiten Befund:
    # die Erwartungsliste nennt jetzt einen Intent, den es nicht mehr gibt.
    geister = [b for b in waehrend_mutation if b.schwere == "geist"]
    assert len(geister) == 1
    assert "rahmen_setzen" in geister[0].was_fehlt


def test_mutationsprobe_wiederhergestellter_intent_wird_wieder_gruen():
    """Die Kehrseite der Mutationsprobe oben, diesmal am Phase-5-Fall
    selbst: wird der fehlende Intent (hypothetisch) ergaenzt, verschwindet
    der Befund. Simuliert ueber die Handlungsliste, nicht ueber echten
    Produktivcode -- das Ziel ist der Mechanismus, nicht ein Feature."""
    handlungen = flow_audit.lade_erwartungen()
    intents_mit_schaerfung = flow_audit.bekannte_intents() | {"schaerfung_entscheidung"}

    geaendert = [
        flow_audit.Handlung(
            phase=h.phase,
            aktion=h.aktion,
            weg=h.weg,
            intent="schaerfung_entscheidung" if h.phase == 5 and h.weg == "chat" and not h.intent else h.intent,
            knopf=h.knopf,
            beleg=h.beleg,
        )
        for h in handlungen
    ]

    befunde = flow_audit.pruefe(handlungen=geaendert, intents=intents_mit_schaerfung)
    assert not any(b.phase == 5 and b.schwere == "toter_gespraechsweg" for b in befunde)

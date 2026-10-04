"""Flow-Audit Schicht 1 (statisch, kein Modellaufruf, SPEC siehe
``simulation/flow_audit.py``).

Geltungsbereich dieser Karte: AUSSCHLIESSLICH Phase 1 (Begriffe/Terms) und
Phase 2 (Fragen/Questions), Padua-Profil, Code-Stand 04.10.2026. Phase 3-7
sind absichtlich nicht Teil dieser Liste -- eine aeltere Fassung mit
Phase 3-7 existiert als Referenz unter ``.flow_audit_ref/`` (vor dem
Phase-1/2-Umbau geschrieben) und ist nicht mehr gueltig.

Diese Suite haelt vier Dinge fest:

1. Die Erwartungsliste deckt genau {1, 2} ab, nicht mehr und nicht weniger.
2. Keine ``geist``-Befunde: jeder in der Liste genannte Intent/Knopf
   existiert im heutigen Code.
3. Die zwei bekannten "roten" Befunde im heutigen Stand -- beide ein
   dokumentierter blinder Fleck der Schicht-1-Pruefung (sie kennt nur
   Erkenner-Intents und ART_*-Knoepfe als Chat-Mechanismus, Phase 2 hat
   aber zwei echte Chat-Wege ausserhalb davon: einen Markerblock des
   Gespraechsmodells und eine deterministische Text-Weiche ohne
   Modellaufruf), kein echter Dialog-Dead-End.
4. Die Mutationsprobe: ein heute funktionierender Intent verschwindet per
   Monkeypatch aus dem echten ``erkenner.ARTEN``, und ``pruefe()`` (ohne
   explizite Parameter, also gegen den echten, mutierten Modulzustand)
   meldet daraufhin einen ``toter_gespraechsweg``. Das ist der Beweis, dass
   Schicht 1 echte Regressionen am Code findet und nicht nur eine feste
   Liste gegen sich selbst spiegelt.
"""

from __future__ import annotations

from simulation import flow_audit


def test_erwartungsliste_deckt_phase_1_und_2_ab():
    """Diese Karte grenzt den Umfang bewusst auf Phase 1+2 ein -- eine
    Zeile fuer Phase 3-7 waere hier falsch (das ist nicht ``range(1, 8)``
    wie in der alten, vor-refactor Referenzfassung unter
    ``.flow_audit_ref/``)."""
    handlungen = flow_audit.lade_erwartungen()
    phasen_mit_eintrag = {h.phase for h in handlungen}
    assert phasen_mit_eintrag == {1, 2}


def test_keine_veraltete_erwartung_im_heutigen_code():
    """'geist'-Befunde heissen: die Liste nennt einen Intent oder Knopf, den
    es nicht mehr gibt. Die Liste ist Handarbeit -- bleibt sie falsch,
    melden sich alle anderen Befunde nicht mehr glaubwuerdig."""
    befunde = flow_audit.pruefe()
    geister = [b for b in befunde if b.schwere == "geist"]
    assert geister == []


def test_begriffe_setzen_deckt_auch_die_begriffsboard_korrektur_per_chat_ab():
    """Der am sorgfaeltigsten zu untersuchende Fall aus dem Auftrag: korrigiert
    die Gruppe den Begriffsboard-Top-5-Vorschlag ('Discussion done') per Chat,
    statt 'Take these' zu druecken, lauft das ueber denselben begriffe_setzen-
    Pfad wie jede andere Begriffe-Aenderung -- kein Sonderfall, kein toter Weg.
    Diese Zeile darf also KEINEN Befund erzeugen."""
    befunde = flow_audit.pruefe()
    betroffen = [b for b in befunde if "Begriffsboard-Top-5-Vorschlag" in b.aktion]
    assert betroffen == []


def test_zwei_bekannte_rote_befunde_sind_dokumentierte_schicht1_blinde_flecken():
    """Schicht 1 kennt nur zwei Chat-Mechanismen: einen Erkenner-Intent oder
    einen Knopf. Phase 2 hat im Padua-A/B-Fragenfluss zwei echte, lebende
    Chat-Wege ausserhalb davon:

    - ``knoepfe.fragen.uebernimm_eigene`` wird ausschliesslich aus einem vom
      GESPRAECHSMODELL selbst erzeugten Markerblock ('VORSCHLAG EIGENE
      FRAGEN:') gefuettert, abgefangen in
      ``knoepfe/basis.py::sende_mit_speicherleiste`` -- kein Erkenner-Lauf,
      kein Knopf. Die mechanische Pruefung sieht weder Intent noch Knopf und
      meldet 'sackgasse', obwohl das der EINZIGE und voll funktionsfaehige Weg
      ist, eigene Fragen beizutragen.
    - ``knoepfe.fragen.nimm_offene_frage_text`` (aufgerufen aus
      ``ablauf.py::_war_die_erwartete_antwort``) ist eine deterministische
      Text-Weiche OHNE Erkenner-Lauf fuer Annehmen/Verwerfen/Schaerfen
      waehrend 'Fragen einzeln durchgehen'. Es gibt dafuer auch Knoepfe
      (ART_FRAGE_ANNEHMEN/_VERWERFEN/_SCHAERFEN) -- die Pruefung sieht also
      ``hat_knopf=True``, ``hat_intent=False`` und meldet
      'toter_gespraechsweg', obwohl der Chat-Weg nachweislich funktioniert.

    Beide sind in ``simulation/flow_erwartungen.toml`` mit einem
    ausfuehrlichen ``beleg`` als genau dieser blinde Fleck dokumentiert, kein
    echter Dialog-Dead-End. Steigt die Zahl der roten Befunde ueber diese
    zwei bekannten, oder verschiebt sich die betroffene Aktion, gehoert ein
    Blick in den Bericht dazu, statt die Zahl stillschweigend hochzusetzen.
    Verschwinden beide (z. B. weil Schicht 1 um einen dritten Mechanismus
    erweitert wird), ist dieser Test bewusst anzupassen."""
    befunde = flow_audit.pruefe()
    rote = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    assert len(rote) == 2

    sackgassen = [b for b in rote if b.schwere == "sackgasse"]
    assert len(sackgassen) == 1
    assert "eigene Fragen" in sackgassen[0].aktion
    assert sackgassen[0].phase == 2

    tote_wege = [b for b in rote if b.schwere == "toter_gespraechsweg"]
    assert len(tote_wege) == 1
    assert "einzeln durchgehen" in tote_wege[0].aktion
    assert tote_wege[0].phase == 2


def test_direkter_interviewstart_und_phasenwechsel_per_chat_sind_kein_befund():
    """'interview_starten' und 'phase_setzen' sind nicht in
    PHASEN_SPEZIFISCHE_ARTEN eingetragen und gelten daher phasenfrei --
    direkt aus Phase 1/2 heraus ein Interview zu starten oder in eine andere
    Phase zu wechseln, funktioniert per Chat genauso wie per Knopf."""
    befunde = flow_audit.pruefe()
    betroffen = [
        b for b in befunde
        if "Interview-Aufnahme per Chat starten" in b.aktion
        or "Weiter zu Phase 3" in b.aktion
    ]
    assert betroffen == []


def test_undo_knopf_ist_eine_bewusste_knopf_only_entscheidung_kein_befund():
    """Die Ruecknahme eines Erkennerlaufs (Karte U) ist dokumentiert
    Knopf-only -- es gibt dafuer keinen Text, der denselben diff-basierten,
    mehrtabelligen Effekt erzeugen koennte. Das darf keinen Befund ergeben,
    weil die Zeile ``weg = "knopf"`` traegt."""
    befunde = flow_audit.pruefe()
    betroffen = [b for b in befunde if "Notiert-Meldung" in b.aktion]
    assert betroffen == []


def test_mutationsprobe_entfernter_intent_wird_als_toter_weg_gemeldet(monkeypatch):
    """Nimmt einen heute funktionierenden Weg (Phase 1, Begriffe per Chat
    setzen, Intent ``begriffe_setzen``) **im echten Erkenner-Modul** per
    Monkeypatch heraus -- der Befund muss ueber den ganz normalen
    ``pruefe()``-Aufruf (keine expliziten Parameter) erscheinen. Das ist der
    Beweis, dass Schicht 1 echte Regressionen am Code findet und nicht nur
    eine feste Liste gegen sich selbst spiegelt. ``monkeypatch`` setzt
    ``erkenner.ARTEN`` nach dem Test automatisch zurueck -- das ist das
    "Zuruecksetzen -> gruen" aus der Abnahme."""
    vorher = flow_audit.pruefe()
    assert not any(
        b.aktion.startswith("Begriffe per Chat nennen") for b in vorher
    )

    from interview_theater import erkenner

    monkeypatch.setattr(
        erkenner, "ARTEN",
        tuple(a for a in erkenner.ARTEN if a != "begriffe_setzen"),
    )

    waehrend_mutation = flow_audit.pruefe()
    treffer = [
        b for b in waehrend_mutation
        if b.aktion.startswith("Begriffe per Chat nennen")
        and b.schwere == "toter_gespraechsweg"
    ]
    assert len(treffer) == 1

    # Die entfernte Art hinterlaesst folgerichtig auch einen zweiten Befund:
    # die Erwartungsliste nennt jetzt einen Intent, den es nicht mehr gibt.
    geister = [
        b for b in waehrend_mutation
        if b.schwere == "geist" and "begriffe_setzen" in b.was_fehlt
    ]
    assert len(geister) == 1

    # monkeypatch setzt ``erkenner.ARTEN`` erst beim Test-Teardown zurueck,
    # nicht automatisch innerhalb dieser Funktion -- ``undo()`` erzwingt das
    # hier, um "Zuruecksetzen -> gruen" noch in diesem Test zu belegen, statt
    # nur auf das (unsichtbare) Teardown-Verhalten zu vertrauen.
    monkeypatch.undo()
    nachher = flow_audit.pruefe()
    assert not any(
        b.aktion.startswith("Begriffe per Chat nennen") for b in nachher
    )
    assert nachher == vorher


def test_mutationsprobe_wiederhergestellter_intent_wird_wieder_gruen():
    """Die Kehrseite der Mutationsprobe oben, diesmal am dokumentierten
    blinden Fleck selbst (Phase 2, 'eigene Fragen beitragen'): wird der
    fehlende Intent (hypothetisch) ergaenzt, verschwindet der Befund.
    Simuliert ueber die Handlungsliste, nicht ueber echten Produktivcode --
    das Ziel ist der Mechanismus, nicht ein Feature."""
    handlungen = flow_audit.lade_erwartungen()
    intents_mit_eigene_fragen = flow_audit.bekannte_intents() | {"eigene_frage_setzen"}

    geaendert = [
        flow_audit.Handlung(
            phase=h.phase,
            aktion=h.aktion,
            weg=h.weg,
            intent=(
                "eigene_frage_setzen"
                if h.phase == 2 and "eigene Fragen" in h.aktion and not h.intent
                else h.intent
            ),
            knopf=h.knopf,
            beleg=h.beleg,
        )
        for h in handlungen
    ]

    befunde = flow_audit.pruefe(
        handlungen=geaendert, intents=intents_mit_eigene_fragen,
    )
    assert not any(
        "eigene Fragen" in b.aktion and b.schwere == "sackgasse" for b in befunde
    )

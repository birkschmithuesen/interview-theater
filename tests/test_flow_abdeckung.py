"""Flow-Audit Schicht 1 (statisch, kein Modellaufruf, SPEC siehe
``simulation/flow_audit.py``).

Geltungsbereich dieser Karte: Phase 1 (Begriffe/Terms), Phase 2
(Fragen/Questions), Phase 3 (Interviews) und Phase 4 (Setting, Figuren &
Geschichte -- Padua: "Frame"), Padua-Profil, Code-Stand 04.10.2026 ff.
(Task A, t_92f99911, erweitert aus der urspruenglichen Phase-1/2-Karte
t_2cdea48b). Phase 5-7 sind absichtlich nicht Teil dieser Liste -- eine
aeltere Fassung mit Phase 3-7 existiert als Referenz unter
``.flow_audit_ref/`` (vor dem Phase-1/2-Umbau geschrieben) und ist nicht
mehr gueltig; die Phase-3/4-Zeilen hier sind neu gegen den heutigen Code
gelesen, keine Uebernahme daraus.

Diese Suite haelt sechs Dinge fest:

1. Die Erwartungsliste deckt genau {1, 2, 3, 4} ab, nicht mehr und nicht
   weniger.
2. Keine ``geist``-Befunde: jeder in der Liste genannte Intent/Knopf
   existiert im heutigen Code.
3. Die zwei ehemals bekannten "roten" Befunde (beide Phase 2) sind seit dem
   ``code_pfad``-Feld (dritter, verifizierter Chat-Mechanismus ausserhalb
   von Erkenner-Intent und ART_*-Knopf -- ein Markerblock des
   Gespraechsmodells bzw. eine deterministische Text-Weiche ohne
   Modellaufruf) kein Befund mehr: ``pruefe()`` meldet fuer den heutigen
   Stand ueberhaupt keine ``sackgasse``/``toter_gespraechsweg``-Zeile.
4. Das ``code_pfad``-Feld selbst: eine Zeile mit gesetztem ``code_pfad``
   erzeugt keinen roten Befund, auch wenn weder Intent noch Knopf greifen;
   ``code_pfad`` erscheint transparent in ``matrix_text`` statt eines
   stillen ``--``; und eine ``geist``-Pruefung feuert nicht auf
   ``code_pfad`` (es wird nicht gegen ein Frozenset aus dem Code
   validiert -- das ist die dokumentierte Grenze dieses Feldes). Die neuen
   Phase-3/4-Zeilen tragen bewusst KEIN ``code_pfad`` -- wo kein
   Intent/Knopf-Paar existiert, ist das entweder eine dokumentierte
   Knopf-only-Entscheidung (``weg = "knopf"``) oder in der Beleg-Prosa
   einer benachbarten Zeile aufgehoben.
5. Die Mutationsprobe: ein heute funktionierender Intent verschwindet per
   Monkeypatch aus dem echten ``erkenner.ARTEN``, und ``pruefe()`` (ohne
   explizite Parameter, also gegen den echten, mutierten Modulzustand)
   meldet daraufhin einen ``toter_gespraechsweg``. Das ist der Beweis, dass
   Schicht 1 echte Regressionen am Code findet und nicht nur eine feste
   Liste gegen sich selbst spiegelt -- einmal fuer Phase 1
   (``begriffe_setzen``, der bestehende Test) und einmal fuer Phase 4
   (``rahmen_setzen``, neu in dieser Karte).
6. Jede neue Phase-3/4-Zeile mit ``weg in ("chat", "beides")`` erzeugt im
   heutigen Stand keinen roten Befund -- oder, wo das (noch) nicht so ist,
   ist es als Knopf-only-Entscheidung deklariert, nicht als Luecke.
"""

from __future__ import annotations

from simulation import flow_audit


def test_erwartungsliste_deckt_phase_1_bis_4_ab():
    """Diese Karte grenzt den Umfang auf Phase 1-4 ein -- eine Zeile fuer
    Phase 5-7 waere hier falsch (das ist nicht ``range(1, 8)`` wie in der
    alten, vor-refactor Referenzfassung unter ``.flow_audit_ref/``)."""
    handlungen = flow_audit.lade_erwartungen()
    phasen_mit_eintrag = {h.phase for h in handlungen}
    assert phasen_mit_eintrag == {1, 2, 3, 4}


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


def test_keine_roten_befunde_im_heutigen_stand():
    """Die beiden ehemals bekannten blinden Flecken dieser Schicht --
    ``uebernimm_eigene`` (Phase 2, 'eigene Fragen beitragen') und
    ``nimm_offene_frage_text`` (Phase 2, 'Fragen einzeln durchgehen') --
    tragen seit dem ``code_pfad``-Feld ihren jeweils dritten, verifizierten
    Chat-Mechanismus explizit in ``flow_erwartungen.toml``. ``pruefe()``
    behandelt eine solche Zeile als erfuellt: der heutige Stand liefert
    ueberhaupt keinen ``sackgasse``/``toter_gespraechsweg``-Befund mehr.
    Taucht hier wieder ein roter Befund auf, ist das jetzt ein echtes
    Signal -- kein bekannter blinder Fleck."""
    befunde = flow_audit.pruefe()
    rote = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    assert rote == []


def test_code_pfad_zeilen_erzeugen_keinen_befund_und_keinen_geist():
    """Die zwei Zeilen mit ``code_pfad`` im echten ``flow_erwartungen.toml``
    duerfen in keiner Befundart auftauchen -- auch nicht als ``geist``:
    ``code_pfad`` ist Freitext und wird nie gegen ein Frozenset aus dem Code
    geprueft (siehe Modul-Docstring, 'Bekannte Grenze von code_pfad')."""
    handlungen = flow_audit.lade_erwartungen()
    code_pfad_zeilen = [h for h in handlungen if h.code_pfad]
    assert len(code_pfad_zeilen) == 2
    aktionen = {h.aktion for h in code_pfad_zeilen}
    assert any("eigene Fragen" in a for a in aktionen)
    assert any("einzeln durchgehen" in a for a in aktionen)

    befunde = flow_audit.pruefe()
    betroffen = [
        b for b in befunde
        if "eigene Fragen" in b.aktion or "einzeln durchgehen" in b.aktion
    ]
    assert betroffen == []


def test_code_pfad_rendert_transparent_in_matrix_text():
    """Eine ``code_pfad``-Zeile soll im Bericht sichtbar bleiben, WARUM sie
    kein Befund ist -- ``matrix_text`` zeigt den Wert statt eines stillen
    ``--``."""
    text = flow_audit.matrix_text()
    assert "Code-Pfad" in text
    assert "knoepfe.fragen.uebernimm_eigene" in text
    assert "knoepfe.fragen.nimm_offene_frage_text" in text


def test_code_pfad_ohne_intent_und_knopf_erzeugt_keinen_befund():
    """Mechanismus-Probe direkt gegen ``pruefe()``, unabhaengig von der
    echten TOML-Datei: eine Handlung mit ``weg='chat'``, leerem Intent,
    leerem Knopf, aber gesetztem ``code_pfad`` ist kein Befund -- das ist
    die neue dritte Spalte der Pruefung, nicht nur ein Zufall der
    bestehenden zwei Zeilen."""
    handlung = flow_audit.Handlung(
        phase=2, aktion="Testhandlung ueber einen dritten Mechanismus",
        weg="chat", intent="", knopf="", beleg="Testbeleg",
        code_pfad="irgendein_modul.irgendeine_funktion (frei erfundener Testpfad)",
    )
    befunde = flow_audit.pruefe(
        handlungen=[handlung],
        intents=flow_audit.bekannte_intents(),
        knoepfe=flow_audit.bekannte_knoepfe(),
    )
    assert befunde == []


def test_code_pfad_mit_weg_beides_und_echtem_knopf_erzeugt_keinen_befund():
    """Derselbe Fall wie oben, aber mit ``weg='beides'`` und einem echten
    Knopf (wie bei ``nimm_offene_frage_text``) -- ohne ``code_pfad`` waere
    das ein ``toter_gespraechsweg`` (Knopf wirkt, Intent fehlt), mit
    ``code_pfad`` ist es keiner."""
    echter_knopf = next(iter(flow_audit.bekannte_knoepfe()))
    handlung = flow_audit.Handlung(
        phase=2, aktion="Testhandlung mit Knopf und drittem Mechanismus",
        weg="beides", intent="", knopf=echter_knopf, beleg="Testbeleg",
        code_pfad="irgendein_modul.irgendeine_funktion (frei erfundener Testpfad)",
    )
    befunde = flow_audit.pruefe(
        handlungen=[handlung],
        intents=flow_audit.bekannte_intents(),
        knoepfe=flow_audit.bekannte_knoepfe(),
    )
    assert befunde == []


def test_code_pfad_befreit_nicht_von_der_geist_pruefung_des_eigenen_knopfs():
    """``code_pfad`` befreit nur von ``sackgasse``/``toter_gespraechsweg``,
    nicht von der ``geist``-Pruefung eines Intent- oder Knopf-Feldes, das
    DANEBEN in derselben Zeile steht: nennt eine Zeile einen nicht mehr
    existierenden Knopf, bleibt das ein ``geist``-Befund, auch wenn
    ``code_pfad`` gesetzt ist."""
    handlung = flow_audit.Handlung(
        phase=2, aktion="Testhandlung mit veraltetem Knopf",
        weg="beides", intent="", knopf="ART_DAS_GIBT_ES_NICHT_MEHR",
        beleg="Testbeleg",
        code_pfad="irgendein_modul.irgendeine_funktion (frei erfundener Testpfad)",
    )
    befunde = flow_audit.pruefe(
        handlungen=[handlung],
        intents=flow_audit.bekannte_intents(),
        knoepfe=flow_audit.bekannte_knoepfe(),
    )
    geister = [b for b in befunde if b.schwere == "geist"]
    assert len(geister) == 1
    assert "ART_DAS_GIBT_ES_NICHT_MEHR" in geister[0].was_fehlt
    # Und trotz des veralteten Knopfs kein sackgasse/toter_gespraechsweg,
    # weil code_pfad den dritten Mechanismus belegt.
    rote = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    assert rote == []


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


# ---------------------------------------------------------------------------
# Phase 3+4 (Task A, t_92f99911) -- dieselben Pruefpunkte wie oben fuer die
# neuen Zeilen, plus die fuer die Karte verbindliche Mutationsprobe.
# ---------------------------------------------------------------------------


def test_phase_3_4_knopf_only_zeilen_erzeugen_keinen_befund():
    """Zwei neue Zeilen sind -- wie der Undo-Knopf in Phase 1 -- bewusste
    Knopf-only-Entscheidungen (``weg = "knopf"``): die Ja/Nein-Fragen zu
    einer langen Sprachnachricht ohne Interviewmodus (Phase 3) und 'Schlag
    du vor' an der Figuren->Geschichte-Naht (Phase 4). Beide duerfen keinen
    Befund ergeben, obwohl sie keinen Erkenner-Intent tragen."""
    befunde = flow_audit.pruefe()
    betroffen = [
        b for b in befunde
        if "Als Interview speichern" in b.aktion
        or "'Schlag du vor' sagen" in b.aktion
    ]
    assert betroffen == []


def test_phase_3_4_chat_und_beides_zeilen_haben_keinen_roten_befund():
    """Jede neue Phase-3/4-Zeile mit ``weg in ("chat", "beides")`` ist im
    heutigen Stand entweder ueber einen Erkenner-Intent oder ueber Intent+
    Knopf gemeinsam abgedeckt -- keine Sackgasse, kein toter Gespraechsweg.
    Eine schaerfere Pruefung als der globale Rote-Befunde-Test unten: diese
    hier filtert explizit auf die neuen Phasen, damit ein kuenftiger Fund in
    Phase 1/2 diesen Test nicht zufaellig mitgruen macht."""
    befunde = flow_audit.pruefe()
    rote_3_4 = [
        b for b in befunde
        if b.phase in (3, 4) and b.schwere in ("sackgasse", "toter_gespraechsweg")
    ]
    assert rote_3_4 == []


def test_mutationsprobe_phase4_rahmen_setzen_wird_als_toter_weg_gemeldet(monkeypatch):
    """Dieselbe Mutationsprobe wie fuer ``begriffe_setzen`` oben (Phase 1),
    hier fuer einen Phase-4-Intent (``rahmen_setzen``, Setting per Chat) --
    das Abnahmekriterium der ganzen Karte t_92f99911 ('einen Intent aus der
    Phasenfreigabe entfernen -> Schicht 1 UND Schicht 2 melden den Befund;
    zuruecksetzen -> gruen'), hier der Schicht-1-Teil davon."""
    vorher = flow_audit.pruefe()
    assert not any(
        b.phase == 4 and b.aktion.startswith("Das Setting") for b in vorher
    )

    from interview_theater import erkenner

    monkeypatch.setattr(
        erkenner, "ARTEN",
        tuple(a for a in erkenner.ARTEN if a != "rahmen_setzen"),
    )

    waehrend_mutation = flow_audit.pruefe()
    treffer = [
        b for b in waehrend_mutation
        if b.phase == 4 and b.aktion.startswith("Das Setting")
        and b.schwere == "toter_gespraechsweg"
    ]
    assert len(treffer) == 1

    geister = [
        b for b in waehrend_mutation
        if b.schwere == "geist" and "rahmen_setzen" in b.was_fehlt
    ]
    assert len(geister) == 1

    monkeypatch.undo()
    nachher = flow_audit.pruefe()
    assert not any(
        b.phase == 4 and b.aktion.startswith("Das Setting") for b in nachher
    )
    assert nachher == vorher

"""Padua Phasen TEIL 2: Gattungsspezifisches nur in formen/<form>.md."""
from pathlib import Path

EN = Path(__file__).resolve().parent.parent / "interview_theater" / "sprachen" / "en" / "prompts"


def test_phase7_en_ohne_hook():
    assert "hook" not in (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()


def test_rap_chor_lied_en_mit_hook():
    for form in ("rap", "chor", "lied"):
        assert "hook" in (EN / "formen" / f"{form}.md").read_text(encoding="utf-8").lower(), form


def test_phase6_en_ohne_alten_einzelszenen_ausloeser():
    """Flow-Audit B3: kein 'write us scene 3' mehr neben dem Ablauf."""
    text = (EN / "phasen" / "6.md").read_text(encoding="utf-8").lower()
    assert "write us scene" not in text
    assert "script tab" in text


def test_phase7_en_nennt_formwahl_sprechweisen_und_script_tab():
    text = (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()
    assert "which form for each number" in text
    assert "script tab" in text


def test_system_en_marker_katalog_nennt_eigene_fragen():
    """Prompt-Check Padua P1-2 (05.10.2026): Padua Phase 2
    (workshop/padua-2026/prompts/phasen/2.md) laesst den Bot
    ``VORSCHLAG EIGENE FRAGEN:`` schreiben
    (interview_theater/knoepfe/fragen.py:uebernimm_eigene) -- der
    EN-Systemprompt muss ihn im Katalog nennen, sonst haelt ein Modell, das
    die 'no more'-Behauptung ernst nimmt, ihn fuer ungueltig. Die genaue
    Zaehlung ('twelve'/'thirteen') aenderte sich seither zweimal (Fix 1
    dieser Karte am 05.10. zaehlte zwoelf -> dreizehn, Befund P2-H1b im
    selben Lauf nahm FRAGENAUSWAHL/FRAGEN wieder heraus und fuegte FRAGE
    hinzu, zurueck auf zwoelf) -- dieser Test prueft nur noch, dass die
    Zahl zur tatsaechlichen Liste passt, nicht eine feste Zahl."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "VORSCHLAG EIGENE FRAGEN:" in text
    assert "There are twelve markers, no more" in text
    assert "There are thirteen markers, no more" not in text


def test_system_en_widerspricht_nicht_dem_echten_phase1_ablauf():
    """Opus-Lesung Prompt-Check P1-2 (05.10.2026, Karte t_bf16f3a7, Befund
    kategorie=b, Zeile 44 von ``01-gespraech-phase1.txt``): der geteilte
    EN-Systemprompt sagte 'Phase 1 is a handover: the terms have been
    collected in the room, you receive the list. You don't collect them
    yourself -- that happens offline, in the plenary session, without the
    chat.' -- genau das Gegenteil von Paduas echtem Ablauf (Hintergrund-
    Zuhoeren im Chat/CoThinker, 'Discussion done', automatischer
    Begriffsvorschlag), der im selben geladenen Prompt-Satz
    (workshop/padua-2026/prompts/phasen/1.md) steht. Ein Modell, das beide
    Saetze liest, bekommt zwei widersprechende Ablaeufe fuer dieselbe
    Phase."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "Phase 1 is a handover" not in text
    assert "that happens offline" not in text


# --- Prompt-Hygiene EN, Runde 1 Task T1 (05.10.2026, Karte Feedback-Schleife
# P1-2) -- Befunde aus docs/prompt-audit/2026-10-05-padua-p12/BEFUND.md und
# lesung.json ---

def test_system_en_beschreibt_die_web_app_statt_telegram():
    """Befund P1-H3: der EN-Systemprompt erklaerte Telegram-Bedienung
    ('Telegram shows them raw') statt der Web-App, die die Gruppe
    tatsaechlich benutzt, und beschrieb ihre Bedienelemente (Start
    listening, Discussion done, Mikro-Knopf, Tabs) gar nicht. Die Gruppe
    kann auch ueber den Web-Kanal laufen, ohne Telegram -- deshalb
    kanalneutral ('the chat'), kein Produktname."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "Telegram" not in text
    assert "The chat shows them raw" in text
    assert "Start listening" in text
    assert "Discussion done" in text
    assert "Workbench" in text
    assert "CoThinker" in text


def test_system_en_erklaert_nie_aufnahmetechnik():
    """Befund P1-N3: 'Stay quiet for 2 seconds' ist Modelltext, keine
    Code-Zeile -- die Regel, Aufnahmetechnik (Pausen, Segmentschnitt,
    Countdown) nie zu erklaeren, steht jetzt im selben Absatz wie die
    Web-App-Beschreibung aus P1-H3."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "never explain the mechanics" in text
    assert "segments" in text


def test_system_en_behauptet_keinen_mikro_check_in_einem_schritt():
    """Review-Fund nach dem ersten T1-Durchgang (05.10.2026): system.md
    behauptete faelschlich, '"Start listening" starts the background
    listening AND the mic check in one step -- there is no separate check
    button'. Tatsaechlich zeigt ``kalEntscheideOderStarte()``
    (web_chat.py:2521-2540), einmal pro Tag (Cache ueber
    ``kalibrierungCacheLesen``), eine eigene Raumcheck-Karte mit eigenem
    Knopf 'Start measuring' (texte.toml:``_TEXT_KALIBRIERUNG_START_KNOPF``,
    ``kalibrierungStarte()`` zeigt ihn ueber ``kalStartKnopf``). Das ist
    genau der Befund P1-H1 ('zwei Start-Bedienelemente') -- Klasse B,
    Birk entscheidet, ob das zusammengelegt wird. Dieser Satz darf die
    Frage nicht vorwegnehmen, nur beschreiben, was heute passiert."""
    text = " ".join((EN / "system.md").read_text(encoding="utf-8").split())
    assert "mic check in one step" not in text
    assert "there is no separate check button" not in text
    assert "a short room check may appear first" in text
    assert "with its own button" in text
    assert "never explain how it measures" in text


def test_system_en_ist_keine_amateurgruppe():
    """Befund P1-L2: system.md sagte 'an amateur theatre group', die
    Padua-Profilanweisung (workshop/padua-2026/prompts/anweisung.md) sagt
    das Gegenteil ('not an amateur group', 'acting students in
    professional training') -- derselbe geladene Prompt widersprach sich."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "amateur" not in text.lower()


def test_system_en_stationen_5_6_nicht_doppelt_prosa():
    """Befund P1-L4: Stationen 5 und 6 behaupteten wortgleich, eine Szene
    werde 'als Prosa' geschrieben -- Station 6 ist aber die Ueberarbeitung
    der in Station 5 geschriebenen Prosa, kein zweiter Schreiblauf."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "Rewrite -- tell each scene as prose" not in text
    assert "go through the prose scenes again" in text


def test_system_en_play_ohne_toten_format_satz():
    """Befund P1-L4: unter '/play setting' stand noch ein toter Satz zum
    nicht mehr existierenden 'format' der Auffuehrung."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "no longer discussed" not in text
    assert "staging in rehearsal" not in text


def test_system_en_form_erst_in_station_7():
    """Befund P2-M1: die Form je Szene wurde schon in Station 4 angeboten
    ('with a suggested form for each scene', 'already in the scene
    sequence suggestion ... changed with a button'), obwohl sie laut
    Station 7 erst dort gewaehlt wird. Das Zeilenformat von
    `VORSCHLAG GESCHICHTE:` liess damals noch ein Form-Feld stehen (Fix
    dafuer: ``test_system_en_geschichte_zeile_ohne_form``, Runde 3)."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "with a suggested form for each scene" not in text
    assert "already in the scene sequence suggestion" not in text
    assert "but only once the group reaches phase 7" in text
    assert "then one line per scene `Title" in text


def test_system_en_geschichte_zeile_ohne_form():
    """Lesung Runde 2 (05.10.2026), Prompt-Check Klasse A, Dump P1 01:174:
    `Title -- one sentence -- characters -- form` verlangte die Form schon
    beim ersten Geschichtsvorschlag (Phase 4) -- Widerspruch zu Zeile 66
    ('but only once the group reaches phase 7'). ``szenenfolge.zerlege``
    (Zeile 278) liest das vierte Feld ohnehin optional und faellt auf
    ``workshop.form_vorgabe()`` zurueck -- die Form faellt in der Zeile
    deshalb ersatzlos weg."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "characters — form`" not in text
    assert "then one line per scene `Title — one sentence — characters`" in text


def test_system_en_frage_ist_keine_pflicht():
    """Lesung Runde 2 (05.10.2026), Prompt-Check Klasse A, Dump P2 05:95:
    'One question, and two to three options' stand als Pflicht am
    Zeilenanfang -- Widerspruch zu Zeile 167 ('At most ONE question per
    message -- never a mandatory close, only when it helps') und zu
    UX-Regel 4 (keine Pflichtfrage je Gedanke). Eine Nachricht darf jetzt
    ohne Frage enden."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "One question, and two to three options" not in text
    assert "at most one question" in text.lower()


def test_system_en_marker_katalog_ohne_fragenauswahl():
    """Befund P2-H1b: `VORSCHLAG FRAGENAUSWAHL:` und `VORSCHLAG FRAGEN:`
    standen im Katalog, obwohl Padua in Phase 2 nie den Zehn-Fragen-Katalog
    schreibt (die eigene-Fragen-Karte ersetzt ihn); das Schaerfen EINER
    Frage in Phase 2 braucht aber den bislang ungenannten Marker
    `VORSCHLAG FRAGE:`."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "VORSCHLAG FRAGENAUSWAHL:" not in text
    assert "`VORSCHLAG FRAGEN:`" not in text
    assert "`VORSCHLAG FRAGE:`" in text
    assert "There are twelve markers, no more" in text
    assert "There are thirteen markers, no more" not in text


def test_system_en_erklaert_diskussion_und_begriffe_detail_koepfe():
    """AGG-1 (offener Teil): die Kopfzeilen 'From your term discussion:'
    und 'Why you chose these terms:' (texte.toml, nicht Teil dieser Karte)
    kamen im Nutzerteil unerklaert vor -- ein Satz in system.md ordnet sie
    jetzt ein, analog zum schon erklaerten CoThinker-Board."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "From your term discussion:" in text
    assert "Why you chose these terms:" in text


def test_system_en_frage_vor_vorschlag_ist_keine_pflicht_je_nachricht():
    """Lesung Runde 3 (05.10.2026), Prompt-Check Klasse A
    (``docs/prompt-audit/2026-10-05-padua-p12-r3/lesung-p1.json``, Zeile
    115): 'In EVERY phase: ONE open question about the group's idea' liest
    sich als Pflichtfrage je Nachricht -- Widerspruch zu UX-Regel 4 ('No
    mandatory question per thought ... The bot may say nothing') und zu
    Zeile 536 ('only when it helps -- never as a closing line'). Die
    Formulierung ist jetzt dieselbe 'at most one question'-Zusage wie an
    Zeile 75 (R3-2), nicht ein zweites Mal wortgleich hingeschrieben."""
    roh = (EN / "system.md").read_text(encoding="utf-8")
    text = " ".join(roh.split())
    assert "In EVERY phase: ONE open" not in roh
    assert "a message may also end without one" in text.lower()
    assert text.lower().count("at most one") >= 2


def test_system_en_scene_ist_kein_alter_name_fuer_record():
    """Prompt-Check Runde 4 (05.10.2026),
    ``docs/prompt-audit/2026-10-05-padua-p12-r4/lesung-p1.json`` Dump-Zeile
    283/``lesung-p2.json`` Zeile 282: system.md zaehlte ``/scene`` unter
    "older names for `/record`". Verifiziert gegen
    ``befehle._BEFEHL_EN``/``befehle.T.BEFEHLE_LISTE`` (texte.toml):
    ``/scene`` ist selbst einer der acht aktiv beworbenen Befehle (Plan a
    scene, set its form, have it written) -- mit dem Interview-Toggle
    ``/record`` hat es nichts zu tun. ``/character``, ``/interview`` und
    ``/done`` bleiben stehen: ``/interview``/``/done`` sind nach
    ``befehle._befehl_interview``/``_befehl_fertig`` tatsaechlich die alten
    Einzelschritte von ``/record``, und ``/character`` ist echt, aber nicht
    in ``BEFEHLE_LISTE``."""
    roh = (EN / "system.md").read_text(encoding="utf-8")
    text = " ".join(roh.split())
    assert "`/scene`" not in roh
    assert "`/character`" in text
    assert "`/interview`" in text
    assert "`/done`" in text
    assert "older names for `/record`" in text


def test_system_en_knopfliste_nennt_fragen_vorschlagen():
    """Prompt-Check Runde 4, ``lesung-p2.json`` Zeile 472: die Knopfliste in
    system.md (wo der Bot nennen darf, welcher Knopf unter seiner Nachricht
    steht) kannte "Suggest questions" nicht, obwohl der Knopf existiert
    (``knoepfe/fragen.py:vorschlagen_leiste``, Art
    ``ART_FRAGEN_VORSCHLAGEN``) und waehrend der ganzen
    Eigene-Fragen-Schreibphase in Phase 2 unter jeder Bot-Nachricht steht."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "Suggest questions" in text


def test_system_en_speichern_knoepfe_nicht_vor_phase_4():
    """Prompt-Check Runde 4, ``lesung-p2.json`` Zeile 292 (Kategorie
    by design/Fehllesung): "under a reflection of ONE value in later
    phases 'Yes, save' and 'No, change it again'" ist laut Mechanik ein
    wiederkehrender falscher Treffer, weil "later phases" unbestimmt
    bleibt. Verifiziert gegen ``knoepfe/basis.py``: Padua laesst Phase 1
    (Begriffe) und die Eroeffnung in Phase 2 ueber ``_AUTOSAVE_ARTEN``
    laufen (stille 📌-Zeile mit Undo statt Ja/Nein), die laufende
    Fragenauswahl ueber ``knoepfe/fragen.py`` (keine Ja/Nein-Leiste); die
    ersten echten "Yes, save"/"No, change it again"-Knoepfe entstehen in
    Phase 4 (Setting/Rahmen, ``knoepfe.basis.offene_art``) und danach
    (Story-Uebersicht, ``entwurf.py``). Die Klammer nennt deshalb die Phase,
    nicht "scene phases" (Phase 4 "Frame" schreibt noch keine Szene)."""
    text = " ".join((EN / "system.md").read_text(encoding="utf-8").split())
    assert "in later phases \"Yes, save\"" not in text
    assert "phase 4 on \"Yes, save\"" in text or "phase 4 on" in text

"""Birk 05.10.2026 13:10 (Padua Phase 1): erst der Raumcheck, dann die
Diskussion. Ein Tipp auf "Start listening" faehrt die Kalibrierung ganz
durch (Stille, dann Sprechprobe) -- ohne zweiten Start-Knopf; erst danach
(oder nach Skip) startet die Diskussionsaufnahme, die Uhr bei 0. Interview
und Brainstorm bleiben beim alten Weg (Aufnahme sofort)."""

from interview_theater import web_chat

JS = web_chat._CHAT_JS


def _fn(name, bis):
    return JS[JS.index(f"function {name}("):JS.index(f"function {bis}(")]


def test_diskussion_startet_ohne_aufnahme_und_ohne_uhr_in_den_raumcheck():
    beginne = _fn("beginneAufnahme", "zeigeBrainstormModus")
    # Die Weiche sitzt VOR neuesSegment()/legStart.
    weiche = beginne.index("sitzung.kalVorStart")
    assert weiche < beginne.index("sitzung.legStart = Date.now()")
    assert weiche < beginne.index("neuesSegment(sitzung)")
    assert "sitzung.art === 'diskussion'" in beginne


def test_kein_start_measuring_knopf_fuer_die_diskussion():
    starte = _fn("kalibrierungStarte", "kalStarteStille")
    assert "sitzung.kalVorStart" in starte
    assert "kalStarteStille(sitzung)" in starte


def test_echte_schnitte_starten_die_diskussion_erst_nach_dem_raumcheck():
    echt = _fn("kalStarteEchteSchnitte", "kalibrierungBeenden")
    vor = echt.index("sitzung.kalVorStart")
    assert vor < echt.index("uhrAn(sitzung)")
    assert "sitzung.kalVorStart = false" in echt
    assert "sitzung.legStart = Date.now()" in echt
    assert "neuesSegment(sitzung)" in echt


def test_kein_diskussionssegment_waehrend_des_raumchecks():
    # Vor dem Start wird nichts als Diskussion verschickt: das Stueck vor der
    # Sprechprobe und ein Rest bei Skip werden verworfen, nach der Probe
    # laeuft kein Recorder weiter.
    ohne = _fn("kalSchneideOhneMarkierung", "kalSchneideAlsKalibrierung")
    assert "kalVorStart" in ohne
    als = _fn("kalSchneideAlsKalibrierung", "kalSchneideUndVerwerfen")
    assert "kalVorStart" in als
    verw = _fn("kalSchneideUndVerwerfen", "kalAufraeumen")
    assert "kalVorStart" in verw
    echt = _fn("kalStarteEchteSchnitte", "kalibrierungBeenden")
    assert "_kalVerworfen = true" in echt


def test_beenden_waehrend_des_raumchecks_verschickt_nichts():
    beenden = _fn("beendeDiskussion", "starteInterview")
    assert "sitzung.kalVorStart" in beenden
    assert "kalAufraeumen(sitzung)" in beenden


def test_interview_und_brainstorm_unveraendert_sofort():
    beginne = _fn("beginneAufnahme", "zeigeBrainstormModus")
    # Nur die Diskussion bekommt kalVorStart; der Rest faellt durch auf den
    # alten Weg (Recorder sofort, dann kalEntscheideOderStarte).
    assert beginne.count("kalEntscheideOderStarte(sitzung)") >= 1
    assert "sitzung.recorder = neuesSegment(sitzung)" in beginne

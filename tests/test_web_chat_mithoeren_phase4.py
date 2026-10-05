"""Birk 05.10.2026 22:00: Phase 4 (Brainstorm) hat KEINEN eigenen
Gedankenbogen-Toggle mehr (t_cf87ee0a abgeloest) -- sie bedient sich mit
genau der Phase-1-Diskussionsbedienung ("Start listening" / "Discussion
done"), inklusive Raumcheck-Wiederverwendung und den normalen VAD-Schnitten.
``sitzung.ziel`` ('diskussion'|'brainstorm', aus dem Server-Feld
``mithoeren_ziel`` bei Sitzungsstart eingefroren) entscheidet nur noch,
wohin das Audio geht und welchen Kalibrierungs-Erfolgstext die Gruppe sieht.

Dieser Test deckt Task 3 (Browser) ab; Task 1/2 (Server) sind in
``tests/test_aufnahme.py``, ``tests/test_brainstorm_bogen.py``,
``tests/test_repo_brainstorm.py``, ``tests/test_web_daten_diskussion_knopf.py``
und ``tests/test_web_chat_mithoeren_ziel.py`` geprueft."""

import json
import shutil
import subprocess

import pytest

from interview_theater import web_chat, sprache

JS = web_chat._CHAT_JS


def _fn(name, bis):
    return JS[JS.index(f"function {name}"):JS.index(f"function {bis}")]


def test_js_kennt_keinen_eigenen_brainstorm_block():
    """Kein eigener Sitzungsslot, keine eigenen DOM-Referenzen, kein
    eigenes Pegel-/CSS-Sonderverhalten mehr fuer Brainstorm -- Phase 4
    laeuft komplett ueber dieselbe ``#diskussion``-Maschinerie wie Phase 1."""
    for verboten in (
        "function starteBrainstorm", "function beendeBrainstorm",
        "function zeigeBrainstormModus", "brainstormKnopf",
        "zustand.brainstorm", "brainstormErlaubt",
        "art !== 'brainstorm'", "data-brainstorm",
    ):
        assert verboten not in JS, verboten


def test_brainstorm_hat_wieder_pausenschnitte():
    # Birk 05.10.2026 22:00: kein Toggle, Phase 4 = Bedienung wie Phase 1 --
    # die Brainstorm-Ausnahme ohne Pausenschnitt (t_cf87ee0a) entfaellt.
    # (Erhalten aus dem geloeschten tests/test_web_chat_brainstorm_toggle.py,
    # per Auftragsnotiz (a) -- main hat den 'weich'-Umbau der Pegel-Schleife
    # bereits gemerged, pegelAn selbst ist nicht mehr Teil dieser Karte.)
    pegel = _fn("pegelAn", "formatiereUhr")
    assert "sitzung.art !== 'brainstorm'" not in pegel
    assert "schneideSegment(sitzung, grund)" in pegel


def test_starte_diskussion_setzt_ziel_aus_zustand_mithoerenziel():
    start = _fn("starteDiskussion", "beendeDiskussion")
    assert "art: 'diskussion', ziel: zustand.mithoerenZiel," in start


def test_zustand_liest_mithoeren_ziel_vom_knopf_dataset_beim_laden():
    zustand_literal = JS[JS.index("var zustand = {"):JS.index("function nonce()")]
    assert (
        "mithoerenZiel: (diskussionKnopf && diskussionKnopf.dataset.mithoerenZiel) "
        "|| 'diskussion',"
    ) in zustand_literal


def test_nimmzustand_haelt_mithoeren_ziel_ueber_jeden_poll_aktuell():
    nimm = _fn("nimmZustand", "zeigeAntworten")
    assert (
        "if (typeof daten.mithoeren_ziel === 'string') "
        "{ zustand.mithoerenZiel = daten.mithoeren_ziel; }"
    ) in nimm


def test_postaudio_nutzt_sitzung_ziel_fuer_das_upload_flag():
    post = _fn("postAudio", "sendeText")
    assert "auftrag.sitzung && auftrag.sitzung.art === 'diskussion'" in post
    assert (
        "weg_ += auftrag.sitzung.ziel === 'brainstorm' ? '&brainstorm=1' : "
        "'&diskussion=1';"
    ) in post


def test_kalantwortja_entscheidet_den_erfolgstext_ueber_ziel_nicht_art():
    """D2 (Plan Task 3): ``kal_erfolg_diskussion`` spricht von "euren
    Begriffen" -- das passt nur zu Phase 1. Seit beide Phasen dieselbe
    Sitzung (``sitzung.art === 'diskussion'``) teilen, muss die Weiche auf
    ``sitzung.ziel`` liegen, nicht mehr auf ``sitzung.art`` -- sonst saehe
    ein Brainstorm in Phase 4 denselben Begriffe-Text wie die Diskussion."""
    ja = _fn("kalAntwortJa", "kalibrierungSkip")
    assert "sitzung.ziel === 'diskussion'" in ja
    assert "sitzung.art === 'diskussion'" not in ja
    assert "? TEXT.kal_erfolg_diskussion : TEXT.kal_erfolg" in ja


def test_keine_eigenen_brainstorm_texte_mehr_im_modul_oder_en_toml():
    assert not hasattr(web_chat, "_TEXT_BRAINSTORM_AN")
    assert not hasattr(web_chat, "_TEXT_BRAINSTORM_LAEUFT")
    en_toml = (sprache.VERZEICHNIS / "en" / sprache.TABELLENDATEI).read_text(
        encoding="utf-8")
    assert "_TEXT_BRAINSTORM_AN" not in en_toml
    assert "_TEXT_BRAINSTORM_LAEUFT" not in en_toml


def test_hoehenaenderung_des_fusses_haelt_den_verlauf_unten():
    # t_a8129d7f Punkt 1, verschoben aus dem geloeschten
    # tests/test_web_chat_brainstorm_toggle.py (Birk 05.10.2026 22:00): der
    # ResizeObserver selbst ist generisch (Fuss UND Verlauf), er bleibt
    # unveraendert -- nur sein frueherer Anlass (der Brainstorm-Knopf
    # erscheint) ist jetzt der gemeinsame Diskussion/Brainstorm-Knopf.
    block = JS[JS.index("if (window.ResizeObserver && fuss) {"):]
    block = block[:block.index("zeigeModus();")]
    assert "hoehenBeobachter.observe(fuss);" in block
    assert "if (verlaufWarUnten && fensterWarUnten) { nachUnten(); }" in block


def _node_oder_skip():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node nicht installiert")
    return node


def _fuehre_js_aus(node: str, quelltext: str, tmp_path) -> str:
    datei = tmp_path / "harness.js"
    datei.write_text(quelltext, encoding="utf-8")
    ergebnis = subprocess.run(
        [node, str(datei)], capture_output=True, text=True, timeout=30,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    return ergebnis.stdout


def test_phase_4_startet_und_beendet_als_brainstorm_in_node(tmp_path):
    """Verhaltensnachweis: mit ``zustand.mithoerenZiel === 'brainstorm'``
    (Phase 4) friert ``starteDiskussion()`` ``sitzung.ziel`` entsprechend
    ein, und ``postAudio()`` haengt darueber ``&brainstorm=1`` an -- NIE
    ``&diskussion=1`` -- sowohl am laufenden Segment als auch am
    Ende-Segment nach "Discussion done"."""
    node = _node_oder_skip()
    start = _fn("starteDiskussion", "beendeDiskussion")
    post_audio = _fn("postAudio", "sendeText")

    quelltext = f"""
    var zustand = {{
      diskussion: null, wechsel: null, ptt: null, mithoerenZiel: 'brainstorm'
    }};
    var aufgerufeneWege = [];
    function modusAn() {{ return false; }}
    function verwirfPtt() {{}}
    function zeigeDiskussionModus() {{}}
    function holeStrom() {{ return new Promise(function () {{}}); }}
    function nonce() {{ return 'n'; }}
    function weg(pfad) {{ return pfad; }}
    function fetch(pfad) {{ aufgerufeneWege.push(pfad); return new Promise(function () {{}}); }}

    {start}
    {post_audio}

    starteDiskussion();
    var sitzung = zustand.diskussion;
    postAudio({{ sitzung: sitzung, dauer: 3,
                 blob: {{ type: 'audio/webm' }}, grund: 'pause' }});
    postAudio({{ sitzung: sitzung, dauer: 1,
                 blob: {{ type: 'audio/webm' }}, grund: 'ende' }});

    console.log(JSON.stringify({{ ziel: sitzung.ziel, wege: aufgerufeneWege }}));
    """
    ausgabe = _fuehre_js_aus(node, quelltext, tmp_path)
    ergebnis = json.loads(ausgabe.strip().splitlines()[-1])
    assert ergebnis["ziel"] == "brainstorm"
    assert len(ergebnis["wege"]) == 2
    for weg_ in ergebnis["wege"]:
        assert "&brainstorm=1" in weg_, weg_
        assert "&diskussion=1" not in weg_, weg_
    assert "grund=ende" in ergebnis["wege"][1]

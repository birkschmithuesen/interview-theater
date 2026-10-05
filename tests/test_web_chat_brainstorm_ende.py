"""Simulation 05.10.2026 (5532c95, Nachtrag "Offen, nicht geaendert"):
beendeBrainstorm/pausiereBrainstorm setzten grund 'ende' nur mit aktiver VAD.
Ohne Pegelmesser (kein AudioContext, Takt-Rueckfall) ging das letzte Segment
ohne 'ende' hoch -- serverseitig lief nie _brainstorm_entscheide mit
ist_abschluss, also keine CoThinker-Karte."""

from interview_theater import web_chat


def _fn(name, bis):
    js = web_chat._CHAT_JS
    return js[js.index(f"function {name}"):js.index(f"function {bis}")]


def test_beenden_markiert_das_ende_immer_auch_ohne_vad():
    beenden = _fn("beendeBrainstorm", "zeigeDiskussionModus")
    assert "letzter && sitzung.vadAktiv) { letzter._grund" not in beenden
    assert "letzter._grund = 'ende'" in beenden
    assert "if (sitzung.vadAktiv) { letzter._redeMs" in beenden



# t_cf87ee0a: Toggle statt Pause/Beenden -- pausiereBrainstorm gibt es nicht
# mehr, der Pause-Test entfaellt (tests/test_web_chat_brainstorm_toggle.py).

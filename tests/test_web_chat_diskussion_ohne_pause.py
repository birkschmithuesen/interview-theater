"""Karte t_cb2c4678, Teil 2 (Birk 04.10.2026 14:50): das Mithoeren der
Phase 1 hat nur noch Start und Fertig. Interview- und Brainstorm-Pause
bleiben unberuehrt."""

import re

from interview_theater import web_chat

DATEN = {"nachrichten": [], "letzte": 0, "aenderung": 0, "interviewmodus": False,
         "titel": None, "phase": 1, "diskussion_knopf": True}


def _seite(**kw):
    return web_chat.chat_html(dict(DATEN, **kw), "1.x", "tok", "", 45000)


def _fn(js, name, bis):
    return js[js.index(f"function {name}"):js.index(f"function {bis}")]


def test_markup_hat_nur_start_und_fertig():
    seite = _seite()
    assert "diskussion-pause" not in seite
    assert 'id="diskussion" data-laeuft="0">' in seite
    assert 'id="diskussion" data-laeuft="0" hidden>' in _seite(diskussion_knopf=False)
    aktionen = re.search(r'id="diskussion-aktionen" hidden>(.*?)</div>', seite, re.S).group(1)
    assert aktionen.count("<button") == 1
    assert 'id="diskussion-beenden" data-discussion-done="1"' in aktionen


def test_js_kennt_keine_diskussionspause():
    js = web_chat._CHAT_JS
    for name in ("pausiereDiskussion", "fortsetzeDiskussion", "diskussionPauseKnopf",
                 "diskussion-pause"):
        assert name not in js, name
    assert "pausiert" not in _fn(js, "zeigeDiskussionModus", "starteDiskussion")
    assert "fortsetzend" not in _fn(js, "starteDiskussion", "beendeDiskussion")


def test_fertig_setzt_weiter_den_grund_ende():
    """Der Ende-Schnitt markiert das Sitzungsende fuer ``diskussion.starte``
    und den Vorschlag -- er kommt allein aus ``beendeDiskussion``."""
    beenden = _fn(web_chat._CHAT_JS, "beendeDiskussion", "starteInterview")
    assert "letzter && sitzung.vadAktiv) { letzter._grund = 'ende'" in beenden


def test_interview_und_brainstorm_pause_bleiben():
    js, seite = web_chat._CHAT_JS, _seite()
    for name in ("function pausiereInterview", "function fortsetzeInterview",
                 "function pausiereBrainstorm", "function fortsetzeBrainstorm",
                 "interviewPauseKnopf", "brainstormPauseKnopf"):
        assert name in js, name
    assert 'id="interview-pause"' in seite and 'id="brainstorm-pause"' in seite
    assert web_chat._TEXT_INTERVIEW_PAUSE in seite

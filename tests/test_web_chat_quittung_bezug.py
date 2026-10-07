"""Birk 07.10.2026: eine Quittung ("✗ Discarded", "Phase 2"), deren Bezug-
Nachricht nicht im geladenen Verlauf steht, haengt NICHT unter der neuesten
Antwort -- sie entfaellt."""
from interview_theater import web_chat


def test_quittung_ohne_sichtbaren_bezug_wird_nicht_unten_angehaengt():
    js = web_chat._CHAT_JS if hasattr(web_chat, "_CHAT_JS") else open(web_chat.__file__, encoding="utf-8").read()
    rumpf = js.split("function zeigeAntworten", 1)[1].split("\n  }\n", 1)[0]
    assert "else if (bezug[id] == null)" in rumpf
    assert rumpf.count("verlauf.appendChild(zeile)") == 1

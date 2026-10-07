"""Der EINE Hintergrund fuer Karten- und Stage-Script-Prompts (Birk
07.10.2026 ~19:40): beide holen ihn aus ``hintergrund.hintergrund_fuer_prompt``
-- die Andockstelle der Phasen-Summary (t_1bc96848). Ersetzt man dort den
Gespraechsblock, sehen es beide Prompts, und kein anderer Weg traegt den
Rohtext alter Phasen hinein."""

import json

from interview_theater import hintergrund, repo, stagescript, szenenkarte

from test_szenenkarte import _lage, padua  # noqa: F401


def test_beide_prompts_holen_den_hintergrund_an_einer_stelle(conn, padua, monkeypatch):
    ids = _lage(conn)
    repo.setze_szenenkarte(conn, ids[0], json.dumps({"typ": "description", "worum": "W",
                                                     "punkte": ["P"], "zitate": []}))
    monkeypatch.setattr(hintergrund, "gespraech_block", lambda c, ch: "SUMMARY-STATT-ROHDUMP")
    karte = szenenkarte.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    stage = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    for text in (karte, stage):
        assert "SUMMARY-STATT-ROHDUMP" in text
        assert "Concert performance, post-dramatic" in text  # Format aus dem Hintergrund


def test_kein_zweiter_weg_zum_p5_wortlaut(conn, padua, monkeypatch):
    ids = _lage(conn)
    from interview_theater import szene
    monkeypatch.setattr(szene, "_p5_gespraech_text", lambda *a, **k: "ROHER-P5-WORTLAUT")
    monkeypatch.setattr(hintergrund, "gespraech_block", lambda c, ch: "")
    karte = szenenkarte.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "ROHER-P5-WORTLAUT" not in karte

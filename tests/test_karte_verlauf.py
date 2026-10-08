"""Karten-Verlauf (Birk 08.10.2026 ~10:35): jede Fassung einer Szenenkarte
bleibt erhalten -- Grundlage fuer den Verfeinerungs-Block in Phase 7
(``stagescript.py``) und das Phase-6-Summary (``phasen_summary.py``)."""

import json

from interview_theater import repo


def _szene_id(conn, chat_id=1, nummer=1) -> int:
    return repo.stelle_szene_sicher(conn, chat_id, nummer)


def test_merke_karte_verlauf_vergibt_aufsteigende_fassung_nr(conn):
    sid = _szene_id(conn)
    repo.merke_karte_verlauf(conn, 1, sid, json.dumps({"worum": "a"}), "erstentwurf")
    repo.merke_karte_verlauf(conn, 1, sid, json.dumps({"worum": "b"}), "aenderung", "mach b")

    reihen = repo.karte_verlauf(conn, 1, sid)

    assert [r["fassung_nr"] for r in reihen] == [1, 2]
    assert reihen[0]["ausloeser"] == "erstentwurf"
    assert reihen[0]["notiz_text"] is None
    assert reihen[1]["ausloeser"] == "aenderung"
    assert reihen[1]["notiz_text"] == "mach b"
    assert json.loads(reihen[1]["karte_json"])["worum"] == "b"


def test_karte_verlauf_ist_leer_ohne_eintraege(conn):
    sid = _szene_id(conn)
    assert repo.karte_verlauf(conn, 1, sid) == []


def test_karte_verlauf_zaehlt_je_szene_getrennt(conn):
    sid1 = _szene_id(conn, nummer=1)
    sid2 = _szene_id(conn, nummer=2)
    repo.merke_karte_verlauf(conn, 1, sid1, json.dumps({"worum": "a"}), "erstentwurf")
    repo.merke_karte_verlauf(conn, 1, sid2, json.dumps({"worum": "x"}), "erstentwurf")
    repo.merke_karte_verlauf(conn, 1, sid1, json.dumps({"worum": "a2"}), "aenderung", "n")

    assert [r["fassung_nr"] for r in repo.karte_verlauf(conn, 1, sid1)] == [1, 2]
    assert [r["fassung_nr"] for r in repo.karte_verlauf(conn, 1, sid2)] == [1]


def test_karte_verlauf_gehoert_zur_loeschzusage(conn):
    from interview_theater import db

    assert "karte_verlauf" in db.TABELLEN_MIT_CHAT_ID

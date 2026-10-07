"""Zaehlbasis der Interviewliste (Birk 07.10.2026 ~19:25, verbindlich): jede
Zahl -- Journal, Checkliste, Roadmap, Done -- zaehlt nur die FESTE, sichtbare
Auswahl der CoThinker-Liste, nie alle Zuordnungen in der Datenbank."""

import pytest

from interview_theater import phasentexte, repo, roadmap, schaerfung, web_daten, workshop
from interview_theater.knoepfe import szenen as ks

from test_szenenkarte import TG, padua  # noqa: F401


def _viele(conn, n):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, "x")
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": f"Thema {i}", "beleg_zitat": f"Zitat {i}", "zitat_geprueft": 1}
        for i in range(n)])
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    themen = [z["id"] for z in conn.execute("SELECT id FROM verdichtung_thema")]
    repo.lege_schaerfung_an(conn, 1, [{"verdichtung_thema_id": t, "szene_id": sid}
                                      for t in themen])
    return sid


def test_padua_zaehlt_nur_die_sichtbare_auswahl(conn, einst, padua):
    n = web_daten.SCHAERFUNGSLISTE_JE_ZIEL + 7
    _viele(conn, n)
    sichtbar = web_daten.SCHAERFUNGSLISTE_JE_ZIEL
    assert web_daten.auswahl_anzahl(conn, 1) == sichtbar
    assert str(sichtbar) in phasentexte._zuordnungen(conn, 1)
    assert str(n) not in phasentexte._zuordnungen(conn, 1)
    assert roadmap._zuordnungen_anzahl(conn, 1) == sichtbar
    # Done: offene sichtbare zaehlen als Keep, ausgeblendete fallen heraus.
    ks._letztes_done.clear()
    tg = TG()
    ks.schliesse_schaerfungsliste(conn, tg, None, einst, 1)
    assert any(f"Taken on: {sichtbar} passages" in t for t in tg.texte)
    assert web_daten.auswahl_anzahl(conn, 1) == sichtbar


def test_journal_der_mapping_runde_zaehlt_die_sichtbare_liste(conn, padua, monkeypatch):
    sid = _viele(conn, 0)
    n = web_daten.SCHAERFUNGSLISTE_JE_ZIEL + 5
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": f"T{i}", "beleg_zitat": f"Z{i}", "zitat_geprueft": 1} for i in range(n)])
    themen = [z["id"] for z in conn.execute("SELECT id FROM verdichtung_thema")]
    zuordnungen = [{"verdichtung_thema_id": t, "szene_id": sid} for t in themen]
    monkeypatch.setattr(schaerfung, "_ziele", lambda c, ch: [{"art": "szene", "id": sid}])
    monkeypatch.setattr(schaerfung, "_mappe_ziel",
                        lambda *a, **k: zuordnungen)
    monkeypatch.setattr(schaerfung, "_eintraege", lambda c, ch: [{"nummer": 1}])
    schaerfung.mappe(None, conn, None, 1)
    zeile = [j["text"] for j in repo.journal(conn, 1) if "passages assigned" in j["text"]]
    assert zeile == [f"Sharpening round 1: {web_daten.SCHAERFUNGSLISTE_JE_ZIEL} passages assigned"]


def test_ohne_liste_zaehlt_es_wie_bisher(conn):
    n = web_daten.SCHAERFUNGSLISTE_JE_ZIEL + 7
    _viele(conn, n)
    assert workshop.diskussion_aktiv() is False
    assert roadmap._zuordnungen_anzahl(conn, 1) == n

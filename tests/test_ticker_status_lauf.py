"""Birk 07.10.2026: der Ticker schreibt ohne neue Daten keinen Eintrag --
"stuck" richtet sich nach dem letzten LAUF (state.json), nicht dem Eintrag."""
from datetime import datetime, timedelta, timezone

from interview_theater import web


def _vor(minuten):
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten)).isoformat()


def test_alter_eintrag_aber_frischer_lauf_ist_nicht_stuck():
    html = web._ticker_status_html([{"zeit": _vor(25), "text": "x"}], _vor(2))
    assert "ticker-stale" not in html


def test_kein_lauf_seit_langem_ist_stuck():
    html = web._ticker_status_html([{"zeit": _vor(25), "text": "x"}], _vor(30))
    assert "ticker-stale" in html


def test_ohne_laufdatum_wie_bisher():
    assert "ticker-stale" in web._ticker_status_html([{"zeit": _vor(25), "text": "x"}])

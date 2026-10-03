"""Die CoThinker-Statuszeile, read-only Seite (Task 3, Phase 4, nur Web,
03.10.2026) -- ``web_daten.cothinker_status`` baut aus vorhandenen Fakten
(laufender Buehnenkarten-Lauf, juengstes Brainstorm-Segment, juengste
Buehnenkarte) den Status zusammen, den ``cothinker_status.leite_ab`` (Task 2)
rein ableitet. Fixture-Muster wie ``tests/test_repo_brainstorm.py``."""

from datetime import datetime, timezone

import pytest
from interview_theater import db, repo, web_daten

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _jetzt_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def test_phase_ungleich_4_liefert_none_selbst_bei_laufendem_lauf(conn):
    repo.markiere_buehnenkarten_lauf(conn, CHAT, _jetzt_iso())
    assert web_daten.cothinker_status(conn, CHAT, 1) is None


def test_denkt_bei_frischem_buehnenkarten_lauf(conn):
    repo.markiere_buehnenkarten_lauf(conn, CHAT, _jetzt_iso())
    status = web_daten.cothinker_status(conn, CHAT, 4)
    assert status is not None
    assert status["zustand"] == "denkt"


def test_transkribiert_bei_segment_im_status_empfangen(conn):
    repo.lege_aufnahme_an(
        conn, CHAT, 1, "kurz", "sprache", status="empfangen", brainstorm=True,
    )
    status = web_daten.cothinker_status(conn, CHAT, 4)
    assert status is not None
    assert status["zustand"] == "transkribiert"


def test_hoert_bei_frisch_fertigem_segment(conn):
    repo.lege_aufnahme_an(
        conn, CHAT, 1, "kurz", "sprache", status="fertig", brainstorm=True,
    )
    status = web_daten.cothinker_status(conn, CHAT, 4)
    assert status is not None
    assert status["zustand"] == "hoert"


def test_schweigt_bei_juengster_karte_ohne_beitrag(conn):
    repo.lege_buehnenkarte_an(conn, CHAT, "", "infomaniak", schweigen=True)
    status = web_daten.cothinker_status(conn, CHAT, 4)
    assert status is not None
    assert status["zustand"] == "schweigt"


def test_none_ohne_jeden_hinweis(conn):
    assert web_daten.cothinker_status(conn, CHAT, 4) is None


def test_ergebnis_ist_ein_einfaches_dict_ohne_row(conn):
    repo.markiere_buehnenkarten_lauf(conn, CHAT, _jetzt_iso())
    status = web_daten.cothinker_status(conn, CHAT, 4)
    assert status == {"zustand": status["zustand"], "seit": status["seit"]}
    assert isinstance(status, dict)


def test_gruppe_nach_token_traegt_den_schluessel_cothinker_status(conn):
    token = repo.stelle_web_token_sicher(conn, CHAT)
    daten = web_daten.gruppe_nach_token(conn, token)
    assert "cothinker_status" in daten
    # Frische Gruppe ohne Phase: kein Status.
    assert daten["cothinker_status"] is None

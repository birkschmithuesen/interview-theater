"""Der Recherche-Block im Gespraechs-Prompt (Karte t_c5117c91): klar vom
Interviewmaterial getrennt -- das Modell soll eine Internet-Recherche nie
als Stimme einer interviewten Person lesen. Jeder Test nennt den Mutanten,
gegen den er faellt."""

from datetime import datetime, timezone

import pytest

from interview_theater import db, einstellungen, kontext, repo

CHAT = 1


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _sende(conn, chat_id, message_id, absender, text, gesendet_am):
    repo.merke_nachricht(conn, chat_id, message_id, absender, 0, "text", text, gesendet_am)
    return repo.hole_nachricht(conn, chat_id, message_id)


def test_ohne_recherche_kein_block(conn):
    """Mutant: _baue_recherche() liefert immer einen Kopf, auch ohne
    gespeicherte Recherche -- datengetrieben wie jeder andere Block."""
    assert kontext._baue_recherche(conn, CHAT) == ""


def test_recherche_block_traegt_kopf_und_text(conn):
    repo.speichere_recherche(
        conn, CHAT, "When was the bridge built?",
        "The bridge was built in 1900 (Example, https://x.test).", [],
    )

    block = kontext._baue_recherche(conn, CHAT)

    assert block.startswith(kontext.T.RECHERCHE_KOPF)
    assert "When was the bridge built?" in block
    assert "1900" in block


def test_recherche_block_erscheint_im_fertigen_prompt_klar_gelabelt(conn, einst):
    """Der Produkt-Test der Karte: der Block steht im Prompt UND ist klar als
    Internet-Recherche beschriftet, nicht als Interviewmaterial. Mutant: der
    Recherche-Block wird nicht in _bloecke() eingehaengt."""
    repo.speichere_recherche(
        conn, CHAT, "When was the bridge built?",
        "The bridge was built in 1900 (Example, https://x.test).", [],
    )
    ausloeser = [_sende(
        conn, CHAT, 1, "Ada", "Stimmt das mit der Bruecke?",
        datetime(2026, 10, 6, 10, 0, 0, tzinfo=timezone.utc).isoformat(timespec="seconds"),
    )]

    prompt = kontext.baue(conn, CHAT, ausloeser, einst)

    assert kontext.T.RECHERCHE_KOPF in prompt
    assert "1900" in prompt


def test_recherche_block_bleibt_getrennt_von_verdichtungen(conn):
    """Eine Recherche darf nie im Verdichtungs- oder Transkriptblock
    auftauchen -- sie ist ein eigener Materialstrang. Mutant: _baue_recherche
    haengt sich an _baue_verdichtungen an statt einen eigenen Block zu
    bilden."""
    repo.speichere_recherche(
        conn, CHAT, "When was the bridge built?",
        "The bridge was built in 1900 (Example, https://x.test).", [],
    )

    bloecke = kontext._bloecke(conn, CHAT, [], None, False, [])

    assert bloecke["recherche"]
    assert "1900" not in (bloecke["verdichtungen"] or "")
    assert "1900" not in (bloecke["transkripte"] or "")

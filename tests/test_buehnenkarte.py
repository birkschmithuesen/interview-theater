import pytest

from interview_theater import buehnenkarte, db, repo, szene_claude

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _FakeKlm:
    """Steht fuer llm.LLM in Tests ohne Einwilligung."""

    def __init__(self, antwort):
        self._antwort = antwort
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append((chat_id, system, nutzer, art))
        return self._antwort


def _segment(conn, message_id: int, transkript: str) -> None:
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", brainstorm=True,
        schnittgrund="pause",
    )
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE id = ?", (transkript, aufnahme_id),
    )
    conn.commit()


def test_nichts_antwort_ergibt_keine_karte(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    klm = _FakeKlm("NICHTS")
    text, modell = buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    assert text is None
    assert modell == "infomaniak"


def test_eine_karte_kommt_durch(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    klm = _FakeKlm("Thema gerade: ein Bahnhof bei Nacht.")
    text, modell = buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    assert text == "Thema gerade: ein Bahnhof bei Nacht."
    assert modell == "infomaniak"


def test_mit_einwilligung_laeuft_es_ueber_claude(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    aufgerufen = {}

    def fake_prosa(conn_, e, klient, chat_id, system, nutzer, art, timeout):
        aufgerufen["lief"] = True
        aufgerufen["art"] = art
        return "Thema gerade: Testkarte."

    monkeypatch.setattr(szene_claude, "prosa", fake_prosa)
    klm = _FakeKlm("sollte nicht gerufen werden")
    text, modell = buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    assert aufgerufen.get("lief") is True
    assert aufgerufen["art"] == "brainstorm_karte"
    assert text == "Thema gerade: Testkarte."
    assert modell == "claude"
    assert not klm.aufrufe


def test_ein_scheiternder_aufruf_liefert_none_und_schreibt_einen_vorfall(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)

    class _KaputterKlm:
        def prosa(self, *a, **k):
            raise RuntimeError("kaputt")

    text, modell = buehnenkarte.erzeuge(conn, object(), _KaputterKlm(), CHAT)
    assert text is None
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (CHAT,),
    ).fetchone()
    assert zeile["art"] == "buehnenkarte_fehlgeschlagen"


def test_grosses_transkript_wird_ab_eigenem_budget_gekuerzt(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_TRANSKRIPT_ZEICHEN", "100")
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _segment(conn, 1, "x" * 500)
    klm = _FakeKlm("Thema gerade: Test.")
    buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    zeile = conn.execute(
        "SELECT art, detail FROM vorfall WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (CHAT,),
    ).fetchone()
    assert zeile["art"] == "brainstorm_transkript_gekuerzt"
    # Der Nutzertext darf das gekuerzte Transkript enthalten, nicht die vollen 500 Zeichen.
    nutzer = klm.aufrufe[0][2]
    assert nutzer.count("x") <= 100


def test_kleines_transkript_wird_nicht_gekuerzt(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _segment(conn, 1, "Ein kurzer Gedanke.")
    klm = _FakeKlm("Thema gerade: Test.")
    buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    zeile = conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE chat_id = ? AND art = 'brainstorm_transkript_gekuerzt'",
        (CHAT,),
    ).fetchone()
    assert zeile[0] == 0


def test_nutzertext_enthaelt_stueckkarte_und_transkript(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Ein Bahnhof bei Nacht")
    _segment(conn, 1, "Wir koennten mit einer Ankunft anfangen.")
    klm = _FakeKlm("Thema gerade: Test.")
    buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    nutzer = klm.aufrufe[0][2]
    assert "Ein Bahnhof bei Nacht" in nutzer
    assert "Wir koennten mit einer Ankunft anfangen." in nutzer


def test_nutzertext_enthaelt_keine_interviewverdichtung(conn, monkeypatch):
    """Phase 4 ist absichtlich interview-frei -- auch wenn die Gruppe schon
    Interviews gefuehrt hat, duerfen deren Verdichtungen nicht im
    Brainstorm-Kontext auftauchen."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 99, "lang", "sprache")
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Geheime Interview-Zusammenfassung.", [],
    )
    klm = _FakeKlm("Thema gerade: Test.")
    buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    nutzer = klm.aufrufe[0][2]
    assert "Geheime Interview-Zusammenfassung" not in nutzer

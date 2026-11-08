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

    def fake_prosa(conn_, e, klient, chat_id, system, nutzer, art, timeout, modell=None):
        aufgerufen["lief"] = True
        aufgerufen["modell"] = modell
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


@pytest.fixture
def padua(monkeypatch):
    from interview_theater import sprache, workshop

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _voller_nutzertext(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "arrival, waiting")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "1. What do you remember?")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "A railway station at night")
    _segment(conn, 1, "What if Samir never leaves the bench?")
    klm = _FakeKlm("NICHTS")
    buehnenkarte.erzeuge(conn, object(), klm, CHAT)
    return klm.aufrufe[0][1], klm.aufrufe[0][2]


def test_padua_nutzertext_ohne_deutsche_ueberschriften(conn, monkeypatch, padua):
    """P34 Runde 1, Befund A5 (= M-17 + L4-10, Dump 17-buehnenkarte.txt:49-62):
    der englische CoThinker-Aufruf trug deutsche Ueberschriften
    ("Begriffe und Fragen", "Stueckkarte", "Figuren", "Geschichte",
    "Mitschnitt des Brainstormings bisher") und nannte die Flaeche "a stage"
    statt "CoThinker"."""
    system, nutzer = _voller_nutzertext(conn, monkeypatch)
    for wort in ("Begriffe", "Fragen", "Stueckkarte", "Figuren", "Geschichte",
                 "Mitschnitt", "noch offen"):
        assert wort not in nutzer, wort
    assert "Terms: arrival, waiting" in nutzer
    assert "Setting: A railway station at night" in nutzer
    assert "Characters: (still open)" in nutzer
    assert "What if Samir never leaves the bench?" in nutzer
    assert "on a stage" not in system
    assert "CoThinker" in system


def test_ohne_profil_bleibt_der_nutzertext_deutsch(conn, monkeypatch):
    """Gegenprobe: Deutsch (Vorgabe/Dortmund) unveraendert."""
    _, nutzer = _voller_nutzertext(conn, monkeypatch)
    assert "Begriffe und Fragen (Phase 1-3):" in nutzer
    assert "Begriffe: arrival, waiting" in nutzer
    assert "Stueckkarte:" in nutzer
    assert "Figuren: (noch offen)" in nutzer
    assert "Mitschnitt des Brainstormings bisher:" in nutzer



def test_eigenes_buehnenmodell_geht_an_claude(conn, monkeypatch):
    """Birk 07.10.2026 (Quota): CoThinker-Karte auf Sonnet, Chat bleibt Opus --
    ``e.buehne_modell`` geht als ``modell`` an ``szene_claude.prosa``."""
    from types import SimpleNamespace
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    gesehen = {}

    def fake_prosa(*a, modell=None, **k):
        gesehen["modell"] = modell
        return "Karte."

    monkeypatch.setattr(szene_claude, "prosa", fake_prosa)
    buehnenkarte.erzeuge(conn, SimpleNamespace(buehne_modell="claude-sonnet-5"), _FakeKlm("x"), CHAT)
    assert gesehen["modell"] == "claude-sonnet-5"

"""Der optionale Zusatz nach "Ja, speichern" (Karte t_c5d68218): kein Zwang,
kein Halluzinieren -- NICHTS-Sentinel wie ``buehnenkarte.py``, gleicher
Modellpfad (Claude mit Einwilligung, sonst Infomaniak), gleicher stiller
Fehlschlag mit Vorfall."""

import pytest

from interview_theater import db, nachspeichern, repo, szene_claude

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


def test_nichts_antwort_ergibt_keinen_zusatz(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    klm = _FakeKlm("NICHTS")
    text, modell = nachspeichern.erzeuge(conn, object(), klm, CHAT, "Setting", "Ein Hinterhof")
    assert text is None
    assert modell == "infomaniak"


def test_echter_zusatz_kommt_durch(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    klm = _FakeKlm("Ein Vorschlag: koennte der Hinterhof auch bei Regen spielen?")
    text, modell = nachspeichern.erzeuge(conn, object(), klm, CHAT, "Setting", "Ein Hinterhof")
    assert text == "Ein Vorschlag: koennte der Hinterhof auch bei Regen spielen?"
    assert modell == "infomaniak"


def test_mit_einwilligung_laeuft_es_ueber_claude(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    aufgerufen = {}

    def fake_prosa(conn_, e, klient, chat_id, system, nutzer, art, timeout):
        aufgerufen["lief"] = True
        aufgerufen["art"] = art
        return "Eine Rueckfrage: wer haelt den Laden eigentlich zusammen?"

    monkeypatch.setattr(szene_claude, "prosa", fake_prosa)
    klm = _FakeKlm("sollte nicht gerufen werden")
    text, modell = nachspeichern.erzeuge(conn, object(), klm, CHAT, "Figuren", "Mira")
    assert aufgerufen.get("lief") is True
    assert aufgerufen["art"] == "nachspeichern"
    assert text == "Eine Rueckfrage: wer haelt den Laden eigentlich zusammen?"
    assert modell == "claude"
    assert not klm.aufrufe


def test_ein_scheiternder_aufruf_liefert_none_und_schreibt_einen_vorfall(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)

    class _KaputterKlm:
        def prosa(self, *a, **k):
            raise RuntimeError("kaputt")

    text, modell = nachspeichern.erzeuge(conn, object(), _KaputterKlm(), CHAT, "Setting", "x")
    assert text is None
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (CHAT,),
    ).fetchone()
    assert zeile["art"] == "nachspeichern_fehlgeschlagen"


def test_nutzertext_enthaelt_gespeichertes_feld_und_stueckkarte(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Ein Hinterhof im Juli")
    klm = _FakeKlm("NICHTS")
    nachspeichern.erzeuge(conn, object(), klm, CHAT, "Figuren", "Mira, Jonas")
    nutzer = klm.aufrufe[0][2]
    assert "Figuren: Mira, Jonas" in nutzer
    assert "Ein Hinterhof im Juli" in nutzer


# --- starte(): der Thread-Weg, der die Zusage 2 haelt -----------------------


class _TgAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append((chat_id, text))
        return 1


def test_starte_ohne_sprachmodell_tut_nichts(conn):
    tg = _TgAttrappe()
    faden = nachspeichern.starte(conn, tg, None, object(), CHAT, "Setting", "x")
    assert faden is None
    assert tg.gesendet == []


def test_starte_sendet_den_zusatz_im_thread(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    tg = _TgAttrappe()
    klm = _FakeKlm("Ein Vorschlag: probiert auch eine Nachtszene.")

    faden = nachspeichern.starte(conn, tg, klm, object(), CHAT, "Setting", "Ein Hinterhof")
    assert faden is not None
    faden.join(timeout=5)

    assert tg.gesendet == [(CHAT, "Ein Vorschlag: probiert auch eine Nachtszene.")]


def test_starte_sendet_nichts_bei_sentinel(conn, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    tg = _TgAttrappe()
    klm = _FakeKlm("NICHTS")

    faden = nachspeichern.starte(conn, tg, klm, object(), CHAT, "Setting", "Ein Hinterhof")
    faden.join(timeout=5)

    assert tg.gesendet == []


def test_starte_sendet_nichts_bei_fehlschlag(conn, monkeypatch):
    """Kriterium (c): ein scheiternder Modellaufruf bleibt stumm -- die
    Bestaetigung ist schon vorher deterministisch rausgegangen, nie bleibt
    die Gruppe unbeantwortet stehen."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    tg = _TgAttrappe()

    class _KaputterKlm:
        def prosa(self, *a, **k):
            raise RuntimeError("kaputt")

    faden = nachspeichern.starte(conn, tg, _KaputterKlm(), object(), CHAT, "Setting", "x")
    faden.join(timeout=5)

    assert tg.gesendet == []

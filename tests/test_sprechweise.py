"""Sprechweise je Figur vor der Buehnenfassung (Padua Phasen TEIL 2, Task 9).

Ein Schema-Aufruf gibt jeder Figur OHNE ``sprachstil`` eine Sprechweise;
Figuren mit Stil bleiben, wie sie sind. Danach EINE Nachricht mit allen
Figuren und "Yes, save" / "No, change it again".
"""

import pytest

from interview_theater import knoepfe, phasen, repo, sprechweise, workshop
from test_knoepfe import TelegramAttrappe, _druck


class KLM:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort or ["Mira: short sentences", "Jo: slow"]
        self.fehler = fehler
        self.schema_aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.schema_aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        if self.fehler:
            raise self.fehler
        return {"sprechweisen": list(self.antwort)}


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _figuren(conn, jo_stil="slow and careful"):
    repo.setze_figur(conn, 1, "Mira", "wants to be asked")
    repo.setze_figur(conn, 1, "Jo", "keeps quiet")
    if jo_stil:
        repo.setze_figur_sprachstil(conn, repo.hole_figur(conn, 1, "Jo")["id"], jo_stil)
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 7, "test")


def _stil(conn, name):
    return repo.hole_figur(conn, 1, name)["sprachstil"]


def test_nur_figuren_ohne_stil_werden_geschrieben(conn, padua, tg, einst):
    _figuren(conn)
    klm = KLM()

    faden = sprechweise.starte(conn, tg, klm, einst, 1)
    faden.join(10)

    assert len(klm.schema_aufrufe) == 1
    assert klm.schema_aufrufe[0]["art"] == sprechweise.ART
    assert _stil(conn, "Mira") == "short sentences"
    assert _stil(conn, "Jo") == "slow and careful"
    # Eine Nachricht, beide Zeilen, zwei Knoepfe.
    (_cid, text, leiste) = tg.knoepfe[-1]
    assert text.startswith("How each character speaks:")
    assert "- Mira: short sentences" in text
    assert "- Jo: slow and careful" in text
    assert [b for b, _d in leiste] == ["Yes, save", "No, change it again"]
    arten = [repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"] for _b, d in leiste]
    assert arten == [knoepfe.ART_SPRECHWEISEN_PASST, knoepfe.ART_SPRECHWEISEN_ANDERS]
    assert sum("How each character speaks" in t for _c, t in tg.gesendet) == 1


def test_nutzertext_nennt_wer_eine_antwort_braucht(conn, padua):
    _figuren(conn)
    text = sprechweise.baue_nutzertext(conn, 1)
    assert "Mira" in text and "Jo" in text
    assert "slow and careful" in text
    assert [f["name"] for f in sprechweise.fehlende(conn, 1)] == ["Mira"]


def test_alle_mit_stil_kein_modellaufruf(conn, padua, tg, einst):
    _figuren(conn)
    repo.setze_figur_sprachstil(conn, repo.hole_figur(conn, 1, "Mira")["id"], "fast")
    klm = KLM()

    faden = sprechweise.starte(conn, tg, klm, einst, 1)
    faden.join(10)

    assert klm.schema_aufrufe == []
    (_cid, text, _leiste) = tg.knoepfe[-1]
    assert "- Mira: fast" in text


def test_fehler_gibt_vorfall_und_trotzdem_die_liste(conn, padua, tg, einst):
    _figuren(conn)
    klm = KLM(fehler=RuntimeError("5xx"))

    faden = sprechweise.starte(conn, tg, klm, einst, 1)
    faden.join(10)

    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "sprechweise_fehlgeschlagen" in arten
    assert _stil(conn, "Mira") is None
    (_cid, text, _leiste) = tg.knoepfe[-1]
    assert "- Mira:" in text
    assert not sprechweise._sperre_fuer(1).locked()


def test_anders_knopf_fragt_nur_nach(conn, padua, tg, einst):
    _figuren(conn)
    knoepfe.biete_sprechweisen(conn, tg, einst, 1)
    daten = tg.knoepfe[-1][2][1][1]

    assert knoepfe.behandle(conn, tg, None, einst, _druck(daten)) is True

    assert tg.gesendet[-1][1] == knoepfe.T._TEXT_SPRECHWEISEN_AENDERN
    assert "Tell me who should speak differently" in tg.gesendet[-1][1]
    assert not (repo.hole_arbeitsstand(conn, 1)["sprechweisen_fixiert_am"] or "").strip()


def test_besetzte_sperre_startet_nichts(conn, padua, tg, einst):
    _figuren(conn)
    sperre = sprechweise._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        assert sprechweise.starte(conn, tg, KLM(), einst, 1) is None
    finally:
        sperre.release()

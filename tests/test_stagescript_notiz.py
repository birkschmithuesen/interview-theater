"""Padua Quickfix (Birk 08.10.2026, Punkt 1): ein Wunsch der Gruppe zu einer
Szene des Stage Scripts (Phase 7), deren Text noch nicht steht oder gerade
geschrieben wird, landet persistent als Notiz fuer GENAU diese Szene statt
in der alten Formwahl-Antwort ("Scene N as Dialogue. The card stays as it
is.") zu verschwinden -- Befund Tester 08.10.2026, chat_id 7000000000099,
betrieb/padua-test.db web_post id 2198-2209.

Kein Netz, kein Modell: der Erkenner bekommt eine Attrappe."""

import json

import pytest

from interview_theater import erkenner, kontext, phasen, repo, stagescript, workshop

from test_erkenner import LLMAttrappe, _nachricht
from test_szenenkarte import TG, padua  # noqa: F401
from test_stagescript import _karten


@pytest.fixture
def tg():
    return TG()


def _texte(tg):
    return list(tg.texte)


# --- repo.py: die Notiz-Tabelle --------------------------------------------


def test_notiz_wird_angehaengt_und_gelesen(conn):
    ids = _karten(conn)
    repo.merke_stagescript_notiz(conn, 1, ids[1], "needs a dialog")
    assert repo.stagescript_notizen(conn, ids[1]) == ["needs a dialog"]
    # Mehrere Notizen sammeln, in der Reihenfolge, in der sie kamen.
    repo.merke_stagescript_notiz(conn, 1, ids[1], "no quotes")
    assert repo.stagescript_notizen(conn, ids[1]) == ["needs a dialog", "no quotes"]
    # Eine andere Szene bleibt unberuehrt.
    assert repo.stagescript_notizen(conn, ids[0]) == []


def test_notizen_markiert_verwendet_fallen_aus_der_liste(conn):
    ids = _karten(conn)
    repo.merke_stagescript_notiz(conn, 1, ids[1], "needs a dialog")
    repo.markiere_stagescript_notizen_verwendet(conn, ids[1])
    assert repo.stagescript_notizen(conn, ids[1]) == []
    # Nur anhaengen (AGENTS.md): die Zeile bleibt in der Tabelle stehen.
    zeile = conn.execute(
        "SELECT * FROM stagescript_notiz WHERE szene_id = ?", (ids[1],)).fetchone()
    assert zeile["verwendet_am"] is not None
    assert zeile["text"] == "needs a dialog"


# --- stagescript.schreibe: die Notiz geht in den Auftrag --------------------


class LLM:
    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == stagescript.ART:
            return {"text": "EMMA: Home.\nGIADA: Yes.", "kopf": ""}
        return {}


def test_schreibe_nimmt_gespeicherte_notiz_mit_und_markiert_sie_verwendet(conn, padua):
    ids = _karten(conn)
    repo.merke_stagescript_notiz(conn, 1, ids[1], "scene 2: needs a real back-and-forth")
    klm = LLM()

    assert stagescript.schreibe(conn, klm, None, 1, 2) is True

    nutzer = klm.aufrufe[0]["nutzer"]
    assert "needs a real back-and-forth" in nutzer
    assert repo.stagescript_notizen(conn, ids[1]) == []


def test_schreibe_ohne_notiz_fragt_nichts_zusaetzliches_ab(conn, padua):
    """Mutationsprobe: ohne die Merge-Zeile in schreibe() faellt die
    gespeicherte Notiz aus dem Auftrag -- dieser Test waere dann gruen,
    waehrend der vorige rot wird (kein falscher gemeinsamer Treffer)."""
    ids = _karten(conn)
    klm = LLM()

    assert stagescript.schreibe(conn, klm, None, 1, 2) is True

    nutzer = klm.aufrufe[0]["nutzer"]
    assert "back-and-forth" not in nutzer


def test_schreibe_notiz_als_parameter_und_gespeicherte_notiz_zusammen(conn, padua):
    ids = _karten(conn)
    repo.merke_stagescript_notiz(conn, 1, ids[1], "no quotes in this one")
    klm = LLM()

    stagescript.schreibe(conn, klm, None, 1, 2, "scene 2: needs a real back-and-forth")

    nutzer = klm.aufrufe[0]["nutzer"]
    assert "needs a real back-and-forth" in nutzer
    assert "no quotes in this one" in nutzer
    # Keine Dublette, wenn dieselbe Notiz schon gespeichert UND als
    # Parameter uebergeben wurde.
    assert nutzer.count("needs a real back-and-forth") == 1


# --- erkenner.py: die neue Art ---------------------------------------------


def test_stagescript_notiz_im_schema_nur_mit_ueberarbeitung(conn, padua, monkeypatch):
    enum = erkenner.schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    assert "stagescript_notiz" in enum
    monkeypatch.setattr(workshop, "ueberarbeitung_aktiv", lambda *a, **k: False)
    assert "stagescript_notiz" not in erkenner.arten_fuer_schema()


def test_stagescript_notiz_nur_in_phase_7(conn, padua):
    phasen.setze(conn, 1, 6, "test")
    assert not erkenner._ist_phasenpassend(conn, 1, "stagescript_notiz")
    phasen.setze(conn, 1, 7, "test")
    assert erkenner._ist_phasenpassend(conn, 1, "stagescript_notiz")


def test_notiz_fuer_noch_nicht_geschriebene_szene_wird_nur_gespeichert(
        conn, einst, padua, tg):
    """Der Live-Befund: 'scene 2 needs a dialog', bevor Szene 1 ueberhaupt
    geschrieben ist. Keine sofortige Schreibung -- nur Notiz + Bestaetigung."""
    ids = _karten(conn)
    _nachricht(conn, 1, 1, "scene 2 needs a dialog")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "stagescript_notiz", "wert": "scene 2: needs a dialog"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.stagescript_notizen(conn, ids[1]) == ["needs a dialog"]
    assert repo.hole_szene(conn, ids[1])["volltext"] is None
    # Statuszeilen ab Phase 7 italienisch (Morgen-Auftrag 4) -- wie
    # ``stagescript.T_IT`` ueberall sonst.
    assert any("scena 2" in t and "needs a dialog" in t for t in _texte(tg))


def test_notiz_ohne_szenennummer_trifft_die_naechste_offene(conn, einst, padua, tg):
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home.", None)
    repo.setze_szene_fertig(conn, ids[0], True)
    _nachricht(conn, 1, 1, "no quotes please")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "stagescript_notiz", "wert": "no quotes please"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.stagescript_notizen(conn, ids[1]) == ["no quotes please"]
    assert any("scena 2" in t for t in _texte(tg))


@pytest.fixture
def stagescript_spion(monkeypatch):
    gerufen = []

    def spion(conn, tg, klm, e, chat_id, nummer, notiz=None):
        gerufen.append((nummer, notiz))
        return None

    monkeypatch.setattr(stagescript, "starte", spion)
    return gerufen


def test_notiz_fuer_geschriebene_nicht_gespeicherte_szene_schreibt_sofort_neu(
        conn, einst, padua, tg, stagescript_spion):
    """Wie 'No, change': die Szene steht schon (Yes/No-Leiste gezeigt),
    noch nicht abgenommen -> sofortiges Neuschreiben MIT der Notiz."""
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home alone.", None)
    _nachricht(conn, 1, 1, "scene 1: give them a back-and-forth")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "stagescript_notiz", "wert": "scene 1: give them a back-and-forth"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert stagescript_spion == [(1, "give them a back-and-forth")]
    assert any("scena 1" in t for t in _texte(tg))
    # Das Markieren als verwendet passiert im echten ``schreibe()``-Lauf
    # (hier gestubbt) -- siehe test_schreibe_nimmt_gespeicherte_notiz_mit_
    # und_markiert_sie_verwendet.


def test_notiz_fuer_laufende_szene_wird_nicht_sofort_neu_geschrieben(
        conn, einst, padua, tg, stagescript_spion):
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home alone.", None)
    sperre = stagescript._sperre_fuer(1)
    sperre.acquire()
    try:
        _nachricht(conn, 1, 1, "scene 1: give them a back-and-forth")
        klm = LLMAttrappe(antwort={"aenderungen": [
            {"art": "stagescript_notiz", "wert": "scene 1: give them a back-and-forth"}]})
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    assert stagescript_spion == []
    assert any("scena 1" in t for t in _texte(tg))
    # Die Notiz bleibt unverwendet liegen -- der naechste Lauf holt sie sich.
    assert repo.stagescript_notizen(conn, ids[0]) == ["give them a back-and-forth"]


def test_ohne_karten_profil_wirkt_die_neue_art_nicht(conn, einst, padua, tg, monkeypatch):
    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: False)
    ids = _karten(conn)
    _nachricht(conn, 1, 1, "scene 2 needs a dialog")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "stagescript_notiz", "wert": "scene 2: needs a dialog"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.stagescript_notizen(conn, ids[1]) == []


# --- kontext.py: keine Formwahl mehr in Phase 7 mit Karten ------------------


def test_formen_block_nicht_mehr_in_phase_7_mit_karten(conn, padua, monkeypatch):
    """Die alte Formwahl-Antwort ('Scene N as Dialogue. The card stays as
    it is.') kam aus dem Formberater-Block im Gespraechs-Prompt -- der lief
    ab Phase 4 ohne obere Grenze, auch in Phase 7 mit Szenenkarten, wo die
    Form schon durch den Kartentyp feststeht."""
    from interview_theater import formberater

    repo.lege_formberater_an(conn, 1, "stichwort", 7, ["fluxus-event-score"], [])
    monkeypatch.setattr(formberater, "kontextblock",
                        lambda *a, **k: "Performative Formen:\n- Fluxus Event Score")
    _karten(conn)  # setzt Phase 7

    assert kontext._baue_formen(conn, 1) == ""

    phasen.setze(conn, 1, 4, "test")
    assert kontext._baue_formen(conn, 1) != ""

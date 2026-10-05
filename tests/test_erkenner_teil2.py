"""Chat wirkt, wo Knoepfe wirken (Padua Phasen TEIL 2, Task 10).

Fuenf neue Erkenner-Arten, alle hinter dem Profilschalter
``workshop.ueberarbeitung_aktiv()`` und phasengebunden ueber dieselbe Tabelle
wie ``uebersicht_aendern`` (``erkenner.PHASEN_SPEZIFISCHE_ARTEN``):

* ``text_ueberarbeiten`` (6, 7) -- Rueckmeldung zum gezeigten Text, Flow-Audit B2;
* ``fassung_abnehmen`` (5, 6, 7) -- "yes, save" im Chat;
* ``formen_setzen`` (7) -- die Antwort auf die Formwahl-Liste;
* ``sprechweise_setzen`` (7) -- eine Sprechweise je Figur;
* ``schaerfung_entscheidung`` (5) -- die Schaerfungsvorschlaege per Chat, B1.

Dazu die Wache gegen ein erfundenes "Noted:" im Gespraechszug (B2).
Kein Netz, kein Modell: der Erkenner bekommt eine Attrappe, die Laeufe werden
an ihrer Einstiegsstelle abgefangen.
"""

import pytest

from interview_theater import (
    ablauf, erkenner, knoepfe, phasen, repo, schaerfung, szene, ueberarbeitung,
    workshop,
)
from test_erkenner import LLMAttrappe, _nachricht
from test_knoepfe import TelegramAttrappe

NEU = ("text_ueberarbeiten", "fassung_abnehmen", "formen_setzen",
       "sprechweise_setzen", "schaerfung_entscheidung")


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture
def dortmund(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def szene_spion(monkeypatch):
    gerufen = []

    def spion(conn, tg, klm, e, chat_id, auftrag, *a, **k):
        gerufen.append(auftrag)
        return None

    monkeypatch.setattr(szene, "starte", spion)
    return gerufen


def _stueck(conn, phase, *, formen=None, sprechweisen_fix=False,
            gesamt_fix=True):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    if gesamt_fix:
        repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jo", "schweigt lieber")
    for nummer in (1, 2):
        sid = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, sid, "ort", "Steg")
        repo.setze_szenenfeld(conn, sid, "was_passiert", "Sie treffen sich.")
        repo.aktualisiere_szene(
            conn, sid, f"Teil {nummer}", None, None,
            f"MIRA: Teil {nummer}.\nJO: Ja.", prosa=f"Mira steht am Steg {nummer}.",
        )
        repo.setze_szene_entwurf_bestaetigt(conn, sid)
        repo.setze_szene_ueberarbeitung_bestaetigt(conn, sid)
        if formen:
            repo.setze_szenenfeld(conn, sid, "form", formen[nummer - 1])
    if sprechweisen_fix:
        repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    phasen.setze(conn, 1, phase, "test")


def _texte(tg):
    return [t for _, t in tg.gesendet]


# --- Schema und Phasentabelle ---------------------------------------------


def test_dortmund_sieht_keine_der_neuen_arten_im_schema(dortmund):
    enum = erkenner.schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    for art in NEU:
        assert art in erkenner.ARTEN
        assert art not in enum
    # szene_usa ist ein Sonderfall: es steht seit der Padua Modellwahl-Karte
    # in PROFILSCHALTER_DER_ARTEN und fehlt deshalb in der statischen
    # ``erkenner.SCHEMA``-Konstante (die alle profilgebundenen Arten
    # ausschliesst) -- bleibt aber ueber den Schalter ``einwilligung``
    # (Vorgabe True) im dynamischen ``schema()`` fuer Dortmund erhalten.
    assert set(enum) == set(erkenner.SCHEMA["properties"]["aenderungen"][
        "items"]["properties"]["art"]["enum"]) | {"szene_usa"}
    assert len(enum) == 27


def test_padua_hat_alle_fuenf_im_schema(padua):
    enum = erkenner.schema()["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    for art in NEU:
        assert art in enum
    assert erkenner.arten_fuer_schema() == enum


def test_text_ueberarbeiten_nicht_in_phase_5(conn, padua):
    phasen.setze(conn, 1, 5, "test")
    assert not erkenner._ist_phasenpassend(conn, 1, "text_ueberarbeiten")
    phasen.setze(conn, 1, 7, "test")
    assert erkenner._ist_phasenpassend(conn, 1, "text_ueberarbeiten")


def test_in_dortmund_wirkt_keine_neue_art_auch_nicht_in_ihrer_phase(conn, dortmund):
    phasen.setze(conn, 1, 7, "test")
    for art in NEU:
        assert not erkenner._ist_phasenpassend(conn, 1, art), art
    # Die alten Arten bleiben phasenfrei.
    assert erkenner._ist_phasenpassend(conn, 1, "festlegung_setzen")


# --- text_ueberarbeiten (B2) ----------------------------------------------


def test_text_ueberarbeiten_startet_die_aktuelle_szene_ohne_notiert(
        conn, einst, padua, tg, szene_spion, monkeypatch):
    _stueck(conn, 7, formen=("chor", "dialog"), sprechweisen_fix=True)
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1
    # Fix-Runde 1: die Szenennummer selbst abfangen, nicht nur eine Ziffer
    # irgendwo im Auftragstext.
    ziele = []
    echt = szene.ueberarbeitungsauftrag

    def auftrag_spion(conn_, chat_id, nummer, notiz):
        ziele.append((nummer, notiz))
        return echt(conn_, chat_id, nummer, notiz)

    monkeypatch.setattr(szene, "ueberarbeitungsauftrag", auftrag_spion)
    _nachricht(conn, 1, 1, "make the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert ziele == [(1, "make the mother angrier")]
    assert len(szene_spion) == 1
    assert "angrier" in szene_spion[0]
    assert not any(t.lstrip().lower().startswith("noted") for t in _texte(tg))


def test_text_ueberarbeiten_mit_szenennummer(conn, einst, padua, tg, szene_spion):
    _stueck(conn, 7, formen=("chor", "dialog"), sprechweisen_fix=True)
    _nachricht(conn, 1, 1, "scene 2: less talking, more silence")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "text_ueberarbeiten", "wert": "scene 2: less talking, more silence"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert len(szene_spion) == 1
    assert "2" in szene_spion[0] and "less talking" in szene_spion[0]


def test_text_ueberarbeiten_verdraengt_festlegung_und_szene_schreiben(
        conn, einst, padua, tg, szene_spion):
    _stueck(conn, 7, formen=("chor", "dialog"), sprechweisen_fix=True)
    _nachricht(conn, 1, 1, "make the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "festlegung_setzen", "wert": "FIGUR/Mother: is angrier"},
        {"art": "szene_schreiben", "wert": "rewrite scene 1"},
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.festlegungen(conn, 1) == []
    assert len(szene_spion) == 1
    assert "angrier" in szene_spion[0]
    assert not any(t.lstrip().lower().startswith("noted") for t in _texte(tg))


def test_text_ueberarbeiten_in_phase_5_wirkt_nicht(conn, einst, padua, tg, szene_spion):
    _stueck(conn, 5)
    _nachricht(conn, 1, 1, "make the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert szene_spion == []


def test_text_ueberarbeiten_schweigt_waehrend_ein_lauf_geht(
        conn, einst, padua, tg, szene_spion):
    _stueck(conn, 7, formen=("chor", "dialog"), sprechweisen_fix=True)
    _nachricht(conn, 1, 1, "make the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    # Fix-Runde 1: nicht still -- genau eine "laeuft noch"-Zeile, wie beim Knopf.
    assert szene_spion == []
    assert _texte(tg) == [ueberarbeitung.T._TEXT_LAEUFT_NOCH]


def test_rueckmeldung_und_abnahme_im_besetzten_lauf_melden_genau_einmal(
        conn, einst, padua, tg, szene_spion):
    """Fix-Runde 1 (Review Task 10): text_ueberarbeiten + fassung_abnehmen +
    festlegung_setzen im selben Lauf, waehrend ein Szenenlauf die Sperre
    haelt -> genau EINE "laeuft noch"-Zeile, keine Ueberarbeitung, keine
    Festlegung (B2-Filter)."""
    _stueck(conn, 7, formen=("chor", "dialog"), sprechweisen_fix=True)
    _nachricht(conn, 1, 1, "make the mother angrier, then save it")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "festlegung_setzen", "wert": "FIGUR/Mother: is angrier"},
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"},
        {"art": "fassung_abnehmen", "wert": ""}]})
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    assert _texte(tg).count(ueberarbeitung.T._TEXT_LAEUFT_NOCH) == 1
    assert len(_texte(tg)) == 1
    assert szene_spion == []
    assert repo.festlegungen(conn, 1) == []
    assert not any(s["fertig_am"] for s in repo.hole_szenen(conn, 1))


# --- formen_setzen --------------------------------------------------------


def test_formen_setzen_schreibt_die_interne_form(conn, einst, padua, tg, monkeypatch):
    _stueck(conn, 7)
    weiter = []
    monkeypatch.setattr(ueberarbeitung, "weiter_7",
                        lambda *a, **k: weiter.append(True))
    _nachricht(conn, 1, 1, "1 chorus, 2 dialogue")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "formen_setzen", "wert": "1:chorus|2:dialogue"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    formen = {s["nummer"]: s["form"] for s in repo.hole_szenen(conn, 1)}
    assert formen == {1: "chor", 2: "dialog"}
    assert _texte(tg)[0].startswith("Noted")
    # Alle Formen stehen, Sprechweisen sind nicht fixiert -> naechster Schritt.
    assert weiter == [True]


def test_formen_setzen_unbekannte_form_und_szene_bleiben_weg(conn, padua):
    _stueck(conn, 7)
    zeilen = ueberarbeitung._wende_formen_an(conn, 1, "1: puppetry | 9: rap | 2 rap")
    formen = {s["nummer"]: s["form"] for s in repo.hole_szenen(conn, 1)}
    assert formen == {1: None, 2: "rap"}
    assert len(zeilen) == 1


def test_formen_setzen_wird_undo_faehig_erfasst(conn, einst, padua):
    _stueck(conn, 7)
    wirkliche, vorher, nachher = erkenner._wende_an_mit_schnappschuss(
        conn, einst, 1, [{"art": "formen_setzen", "wert": "1: song"}])
    assert wirkliche
    lauf_id = erkenner._lege_ruecknahme_an(conn, einst, 1, vorher, nachher, wirkliche)
    assert lauf_id is not None
    from interview_theater import ruecknahme

    assert repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(), ruecknahme.WEICH,
        ruecknahme.HART, ruecknahme.GELEERT) == repo.ZURUECK_OK
    assert {s["nummer"]: s["form"] for s in repo.hole_szenen(conn, 1)}[1] is None


# --- sprechweise_setzen ---------------------------------------------------


def test_sprechweise_setzen_schreibt_den_stil(conn, einst, padua, tg, monkeypatch):
    _stueck(conn, 7, formen=("chor", "dialog"))
    angeboten = []
    monkeypatch.setattr(knoepfe, "biete_sprechweisen",
                        lambda *a, **k: angeboten.append(True))
    _nachricht(conn, 1, 1, "Mira: short sentences")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "sprechweise_setzen", "wert": "Mira: short sentences"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.hole_figur(conn, 1, "Mira")["sprachstil"] == "short sentences"
    assert _texte(tg)[0].startswith("Noted")
    assert angeboten == [True]


def test_sprechweise_setzen_unbekannte_figur_schreibt_nichts(conn, padua):
    _stueck(conn, 7)
    from interview_theater import sprechweise

    assert sprechweise.wende_an(conn, 1, "Nobody: fast") == []
    assert sprechweise.wende_an(conn, 1, "ohne Doppelpunkt") == []


# --- fassung_abnehmen -----------------------------------------------------


def test_fassung_abnehmen_fixiert_das_ganze_in_phase_6(
        conn, einst, padua, tg, monkeypatch):
    _stueck(conn, 6, gesamt_fix=False)
    monkeypatch.setattr(ueberarbeitung, "weiter_6", lambda *a, **k: None)
    _nachricht(conn, 1, 1, "yes, save it")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "fassung_abnehmen", "wert": ""}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert ueberarbeitung.gesamttext_fixiert(conn, 1)


def test_nimm_ab_ohne_offene_abnahme_ist_none(conn, padua, tg, einst):
    _stueck(conn, 7)  # Formen offen
    assert ueberarbeitung.nimm_ab(conn, tg, None, einst, 1) is None


# --- schaerfung_entscheidung (B1) -----------------------------------------


def test_schaerfung_entscheidung_uebernimmt_die_szene(
        conn, einst, padua, tg, monkeypatch):
    _stueck(conn, 5)
    gerufen = []
    monkeypatch.setattr(schaerfung, "uebernimm_szene",
                        lambda conn, chat_id, ziel: gerufen.append(ziel["nummer"]) or 1)
    _nachricht(conn, 1, 1, "yes, take the line for scene 1")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "schaerfung_entscheidung", "wert": "scene 1"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert gerufen == [1]


def test_schaerfung_keine_verwirft_die_gezeigten_stellen(conn, padua, tg, monkeypatch):
    _stueck(conn, 5)
    verworfen = []
    stellen = [{"id": 11}, {"id": 12}]
    monkeypatch.setattr(
        schaerfung, "offene_stellen",
        lambda conn, chat_id, szene_id=None, figur_id=None:
            stellen if szene_id is not None and not verworfen else [])
    monkeypatch.setattr(schaerfung, "verwirf_stellen",
                        lambda conn, ids: verworfen.append(list(ids)) or len(ids))
    monkeypatch.setattr(knoepfe.szenen, "biete_schaerfung", lambda *a, **k: False)

    knoepfe.szenen.verwirf_schaerfung(conn, tg, 1)

    assert verworfen == [[11, 12]]


# --- Erfundenes "Noted:" (B2) ---------------------------------------------


def test_ist_erfundenes_notiert():
    assert ablauf.ist_erfundenes_notiert("Noted: the mother is angrier")
    assert ablauf.ist_erfundenes_notiert("  noted -- scene 2 is shorter")
    assert not ablauf.ist_erfundenes_notiert("I have noted your idea. Shall I?")
    assert not ablauf.ist_erfundenes_notiert(None)


# --- Anbieter-Systeminjektion (Abnahme P1-2, Fortsetzung) -------------------


def test_ist_anbieter_systeminjektion():
    """Echter Browserlauf (handy/giulia, 05.10.2026): die Antwort begann mit
    'Benutzer hat Chat-Standort (New Zealand) erhalten...' -- eine
    anbieterseitige Standort-/Sprachhinweis-Injektion (Infomaniak/Kimi), die
    als Gespraechsantwort durchgereicht und gespeichert wurde."""
    assert ablauf.ist_anbieter_systeminjektion(
        "Benutzer hat Chat-Standort (New Zealand) erhalten. Er/Sie spricht "
        "vielleicht Englisch mit neuseeländischem Dialekt."
    )
    assert ablauf.ist_anbieter_systeminjektion(
        "Du kannst es immer auf \"Wähle eine Sprache\" ändern."
    )
    assert not ablauf.ist_anbieter_systeminjektion(
        "I like the direction for grandmother's kitchen -- sharper."
    )
    assert not ablauf.ist_anbieter_systeminjektion(None)


def test_notiert_wache_nur_in_padua_phase_6_und_7(conn, einst, padua):
    phasen.setze(conn, 1, 7, "test")
    assert ablauf._erfundenes_notiert(conn, einst, 1, "Noted: angrier")
    vorfall = conn.execute(
        "SELECT * FROM vorfall WHERE art ='gespraech_notiert_erfunden'").fetchone()
    assert vorfall is not None
    phasen.setze(conn, 1, 4, "test")
    assert not ablauf._erfundenes_notiert(conn, einst, 1, "Noted: angrier")


def test_notiert_wache_feuert_nicht_in_dortmund(conn, einst, dortmund):
    phasen.setze(conn, 1, 7, "test")
    assert not ablauf._erfundenes_notiert(conn, einst, 1, "Noted: angrier")

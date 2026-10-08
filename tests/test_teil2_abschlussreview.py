"""Abschlussreview Padua Phasen TEIL 2 (03.10.2026): die fuenf wichtigen Funde.

1. Eine Abnahme aus dem Chat nimmt die Leiste der abgenommenen Nachricht ab;
   ein veraltetes "Yes, save" fuer eine Szene, die nicht dran ist, wirkt nicht.
2. Das allgemeine Phasenangebot schweigt fuer die zwei Uebergaenge, die
   Padua selbst vollzieht (5->6, 6->7) -- Dortmund unveraendert.
3. Eine Regie-Notiz, die selbst den Lauf gestartet hat, bekommt danach keine
   "laeuft noch"-Zeile vom Erkenner.
4. Die Formwahl in Phase 7: Teilantwort -> Zeile mit den fehlenden Nummern;
   eine neue Form fuer eine schon uebertragene Szene nimmt ihren Text zurueck.
5. ``szene_kuerzen`` waehrend eines laufenden Laufs startet in Padua nichts.

Kein Netz, kein Modell: Laeufe werden an ihrer Einstiegsstelle abgefangen.
"""

import pytest

from interview_theater import (
    ablauf, erkenner, knoepfe, kuerzung, kurzgeschichte, phasen, repo, szene,
    szenenfolge, ueberarbeitung, workshop,
)
from test_erkenner import LLMAttrappe, _nachricht
from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture(autouse=True)
def _ohne_karten(monkeypatch):
    """Diese Tests pruefen den Padua-Prosaweg (P5 Prosa, P6 Rewrite) -- seit
    dem Phasenumbau (Birk 07.10.2026 ~18:12) das Verhalten OHNE
    ``[karten] aktiv``; der Kartenweg steht in ``tests/test_szenenkarte.py``."""
    from interview_theater import workshop as _workshop

    monkeypatch.setattr(_workshop, "szenenkarten_aktiv", lambda *a, **k: False)



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


def _stueck(conn, phase, *, szenen=(1, 2, 3), formen=None, volltext=True,
            sprechweisen_fix=False, gesamt_fix=True, ueberarbeitet=True):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", repo._jetzt())
    if gesamt_fix:
        repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jo", "schweigt lieber")
    for nummer in szenen:
        sid = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, sid, "ort", "Steg")
        repo.setze_szenenfeld(conn, sid, "was_passiert", "Sie treffen sich.")
        repo.aktualisiere_szene(
            conn, sid, f"Teil {nummer}", None,
            f"MIRA: Teil {nummer}.\nJO: Ja." if volltext else None,
            f"Sie treffen sich, Teil {nummer}.",
            prosa=f"Mira steht am Steg {nummer}.",
        )
        repo.setze_szene_entwurf_bestaetigt(conn, sid)
        if ueberarbeitet:
            repo.setze_szene_ueberarbeitung_bestaetigt(conn, sid)
        if formen:
            repo.setze_szenenfeld(conn, sid, "form", formen[nummer - 1])
    if sprechweisen_fix:
        repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    phasen.setze(conn, 1, phase, "test")


def _szene(conn, nummer):
    return next(s for s in repo.hole_szenen(conn, 1) if s["nummer"] == nummer)


def _texte(tg):
    return [t for _, t in tg.gesendet]


def _knopf_der_art(conn, tg, art, message_index=-1):
    for _b, d in tg.knoepfe[message_index][2]:
        knopf = repo.hole_knopf(conn, knoepfe._id_aus_daten(d))
        if knopf["art"] == art:
            return d
    raise AssertionError(f"kein Knopf {art}")


def _offen(conn, message_id):
    return repo.offene_knoepfe_der_nachricht(conn, 1, message_id)


# ---------------------------------------------------------------------------
# Fix 1 -- Abnahme aus dem Chat nimmt die Leiste ab; veraltete Knoepfe wirken nicht
# ---------------------------------------------------------------------------


def test_veraltetes_ja_fuer_eine_andere_szene_in_phase_6_wirkt_nicht(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, ueberarbeitet=False)
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1
    monkeypatch.setattr(ueberarbeitung, "weiter_6",
                        lambda *a, **k: pytest.fail("weiter_6"))
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SZENE_PASST, "3")

    knoepfe.behandle(conn, tg, None, einst, _druck(knoepfe._daten(knopf_id)))

    assert tg.beantwortet[-1][1] == ueberarbeitung.T._TEXT_NICHT_DRAN
    assert _texte(tg) == [ueberarbeitung.T._TEXT_NICHT_DRAN]
    assert "nothing was saved" in ueberarbeitung.T._TEXT_NICHT_DRAN
    assert all(not s["ueberarbeitung_bestaetigt_am"] for s in repo.hole_szenen(conn, 1))
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1


def test_ja_aus_phase_6_nach_dem_sprung_in_phase_7_wirkt_nicht(
        conn, padua, tg, einst, monkeypatch):
    """Der Befund: das alte "Yes, save" (wert = letzte Szene aus Phase 6)
    rief in Phase 7 ``bestaetige_szene_7`` fuer eine nie uebertragene Szene."""
    _stueck(conn, 7, formen=("chor", "dialog", "rap"))  # Sprechweisen offen
    monkeypatch.setattr(ueberarbeitung, "weiter_7",
                        lambda *a, **k: pytest.fail("weiter_7"))
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SZENE_PASST, "3")

    knoepfe.behandle(conn, tg, None, einst, _druck(knoepfe._daten(knopf_id)))

    assert tg.beantwortet[-1][1] == ueberarbeitung.T._TEXT_NICHT_DRAN
    assert not _szene(conn, 3)["fertig_am"]


def test_ja_fuer_die_aktuelle_szene_in_phase_7_wirkt_weiter(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    weiter = []
    monkeypatch.setattr(ueberarbeitung, "weiter_7", lambda *a, **k: weiter.append(1))

    antwort = ueberarbeitung.bestaetige_szene_7(conn, tg, None, einst, 1, 1)

    assert antwort == knoepfe.T._ANTWORT_SZENE_STEHT.format(nummer=1)
    assert _szene(conn, 1)["fertig_am"]
    assert weiter == [1]


def test_chat_abnahme_des_ganzen_nimmt_die_leiste_ab(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False)
    monkeypatch.setattr(ueberarbeitung, "weiter_6", lambda *a, **k: None)
    message_id = knoepfe.zeige_geprueft_geschichte(conn, tg, einst, 1, None)
    # Padua seit bc19d0a (Birk 07.10.2026 ~17:15): nur "Yes, save" und
    # "No, change" -- kein "Kuerzer", kein "Erste Fassung zeigen" mehr.
    assert len(_offen(conn, message_id)) == 2
    nein = _knopf_der_art(conn, tg, knoepfe.ART_GESCHICHTE_ANDERS)

    ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)

    assert ueberarbeitung.gesamttext_fixiert(conn, 1)
    assert (1, message_id) in tg.entfernt
    assert _offen(conn, message_id) == []
    # Ein liegengebliebenes "No, change" unter dem schon fixierten Ganzen
    # oeffnet es nicht wieder fuer eine Regie-Notiz.
    from interview_theater.knoepfe import wirkung
    monkeypatch.setattr(wirkung, "erwarte_geschichte_notiz",
                        lambda *a, **k: pytest.fail("erwarte_geschichte_notiz"))
    knoepfe.behandle(conn, tg, None, einst, _druck(nein, query_id="alt"))
    assert tg.beantwortet[-1][1] == knoepfe.T._TEXT_SCHON_BENUTZT


def test_chat_abnahme_der_letzten_szene_in_phase_6_nimmt_die_leiste_ab(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, ueberarbeitet=False)
    for s in repo.hole_szenen(conn, 1):
        if s["nummer"] in (1, 2):
            repo.setze_szene_ueberarbeitung_bestaetigt(conn, s["id"])
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 3
    monkeypatch.setattr(knoepfe, "eintritt_in_phase", lambda *a, **k: None)
    message_id = knoepfe.zeige_geprueft_szene(conn, tg, einst, 1, 3, None)
    ja = _knopf_der_art(conn, tg, knoepfe.ART_SZENE_PASST)

    ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)

    assert phasen.aktuelle(conn, 1) == 7
    assert (1, message_id) in tg.entfernt
    assert _offen(conn, message_id) == []
    # Das alte "Yes, save" aus Phase 6 wirkt in Phase 7 nicht mehr.
    monkeypatch.setattr(ueberarbeitung, "bestaetige_szene_7",
                        lambda *a, **k: pytest.fail("bestaetige_szene_7"))
    knoepfe.behandle(conn, tg, None, einst, _druck(ja, query_id="alt"))
    assert tg.beantwortet[-1][1] == knoepfe.T._TEXT_SCHON_BENUTZT


def test_chat_abnahme_der_letzten_buehnenszene_nimmt_die_leiste_ab(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    for s in repo.hole_szenen(conn, 1):
        if s["nummer"] in (1, 2):
            repo.setze_szene_fertig(conn, s["id"], True)
    monkeypatch.setattr(ueberarbeitung, "weiter_7", lambda *a, **k: None)
    message_id = knoepfe.zeige_geprueft_szene(conn, tg, einst, 1, 3, None)

    ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)

    assert _szene(conn, 3)["fertig_am"]
    assert (1, message_id) in tg.entfernt
    assert _offen(conn, message_id) == []


def test_chat_abnahme_im_besetzten_lauf_laesst_die_leiste_stehen(
        conn, padua, tg, einst):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    message_id = knoepfe.zeige_geprueft_szene(conn, tg, einst, 1, 1, None)
    sperre = szene._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        antwort = ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)
    finally:
        sperre.release()

    assert antwort == ueberarbeitung.T._TEXT_LAEUFT_NOCH
    assert (1, message_id) not in tg.entfernt
    # Padua seit bc19d0a: die Leiste ist "Yes, save" / "No, change".
    assert len(_offen(conn, message_id)) == 2


def test_chat_abnahme_der_uebersicht_in_phase_5_nimmt_die_leiste_ab(
        conn, padua, tg, einst, szene_spion):
    _stueck(conn, 5, gesamt_fix=False, ueberarbeitet=False)
    for s in repo.hole_szenen(conn, 1):
        conn.execute("UPDATE szene SET entwurf_bestaetigt_am = NULL WHERE id = ?",
                     (s["id"],))
    conn.commit()
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht", "Logline: x")
    message_id = knoepfe.biete_uebersicht(conn, tg, 1, "Logline: x")

    ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)

    assert (repo.hole_arbeitsstand(conn, 1)["geschichte_uebersicht_fixiert_am"] or "")
    assert (1, message_id) in tg.entfernt
    assert _offen(conn, message_id) == []


# ---------------------------------------------------------------------------
# Fix 2 -- kein allgemeines Phasenangebot mitten im Padua-Ablauf
# ---------------------------------------------------------------------------


def _phasenknoepfe(conn, tg):
    return [
        repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["wert"]
        for _cid, _text, leiste in tg.knoepfe for _b, d in leiste
        if repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"] == knoepfe.ART_PHASE
    ]


def _unverwandte_aenderung(conn, tg, einst):
    _nachricht(conn, 1, 1, "Mira hat eine Schwester, Lea")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "rahmen_setzen", "wert": "Am Hafen, im Winter"}]})
    erkenner.laufe(klm, tg, conn, einst, 1)


def test_padua_phase_6_bietet_phase_7_nicht_an(conn, padua, tg, einst):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 7  # die Materiallage gaebe es her

    _unverwandte_aenderung(conn, tg, einst)

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == "Am Hafen, im Winter"
    assert "7" not in _phasenknoepfe(conn, tg)
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False
    assert phasen.aktuelle(conn, 1) == 6


def test_padua_phase_5_bietet_phase_6_nicht_an(conn, padua, tg, einst):
    _stueck(conn, 5, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht", "Logline: x")
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht_fixiert_am", repo._jetzt())
    assert phasen.offenes_angebot(conn, 1) == 6

    _unverwandte_aenderung(conn, tg, einst)

    assert "6" not in _phasenknoepfe(conn, tg)
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False


def test_padua_andere_uebergaenge_bleiben_angeboten(conn, padua, tg, einst):
    """Nur 5->6 und 6->7 sind Paduas eigene Spruenge -- 1->2 bleibt."""
    phasen.setze(conn, 1, 1, "test")
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Liebe, Streit, Hafen")
    assert phasen.offenes_angebot(conn, 1) == 2
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    assert "2" in _phasenknoepfe(conn, tg)


def test_dortmund_phase_6_bietet_phase_7_weiter_an(conn, dortmund, tg, einst):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 7

    _unverwandte_aenderung(conn, tg, einst)

    assert "7" in _phasenknoepfe(conn, tg)


def test_dortmund_phase_5_bietet_phase_6_weiter_an(conn, dortmund, tg, einst):
    _stueck(conn, 5, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 6
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    assert "6" in _phasenknoepfe(conn, tg)


# ---------------------------------------------------------------------------
# Fix 3 -- die Regie-Notiz, die den Lauf selbst gestartet hat
# ---------------------------------------------------------------------------


def test_notiz_nach_anders_bekommt_keine_laeuft_noch_zeile(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, ueberarbeitet=False)
    sperre = szene._sperre_fuer(1)
    gestartet = []

    def lauf_haelt_die_sperre(conn_, tg_, klm, e, chat_id, auftrag, *a, **k):
        gestartet.append(auftrag)
        assert sperre.acquire(blocking=False)
        return "faden"

    monkeypatch.setattr(szene, "starte", lauf_haelt_die_sperre)
    # "No, change it again" unter Szene 1, dann die Notiz.
    szenenfolge.erwarte_regienotiz(1, 1)
    _nachricht(conn, 1, 41, "make the mother angrier")
    zeile = next(n for n in repo.unextrahierte(conn, 1) if n["message_id"] == 41)
    try:
        assert ablauf._szene_hat_vorfahrt(conn, tg, None, einst, 1, zeile) is True
        assert len(gestartet) == 1 and ueberarbeitung.laeuft(1)
        klm = LLMAttrappe(antwort={"aenderungen": [
            {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    assert ueberarbeitung.T._TEXT_LAEUFT_NOCH not in _texte(tg)
    assert len(gestartet) == 1  # keine zweite Ueberarbeitung
    assert 1 not in ablauf._notiz_verbraucht


def test_ein_fremder_lauf_meldet_weiter_laeuft_noch(
        conn, padua, tg, einst, szene_spion):
    """Gegenprobe zu Task 10: die Sperre haelt ein anderer Lauf, und die
    verbrauchte Notiz war eine FRUEHERE Nachricht -- die Zeile kommt."""
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    ablauf._notiz_verbraucht[1] = 7  # eine aeltere, schon gelesene Nachricht
    _nachricht(conn, 1, 42, "make the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()
        ablauf._notiz_verbraucht.pop(1, None)

    assert _texte(tg) == [ueberarbeitung.T._TEXT_LAEUFT_NOCH]
    assert szene_spion == []


def test_dortmund_merkt_keine_verbrauchte_notiz(conn, dortmund, tg, einst, szene_spion):
    phasen.setze(conn, 1, 7, "test")
    szenenfolge.erwarte_regienotiz(1, 1)
    _nachricht(conn, 1, 43, "kuerzer bitte")
    zeile = next(n for n in repo.unextrahierte(conn, 1) if n["message_id"] == 43)
    ablauf._szene_hat_vorfahrt(conn, tg, None, einst, 1, zeile)
    assert 1 not in ablauf._notiz_verbraucht


# ---------------------------------------------------------------------------
# Fix 4 -- die Formwahl in Phase 7
# ---------------------------------------------------------------------------


def test_teilweise_formwahl_nennt_die_fehlenden_nummern(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 7)
    monkeypatch.setattr(ueberarbeitung, "weiter_7",
                        lambda *a, **k: pytest.fail("weiter_7"))
    _nachricht(conn, 1, 1, "1 chorus")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "formen_setzen", "wert": "1: chorus"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    texte = _texte(tg)
    # chat_id 1 steht in keiner italienisch_ab_phase6_chats-Liste -- englisch.
    assert texte[0].startswith("Noted:")
    assert texte[-1] == ueberarbeitung.T._TEXT_FORMEN_FEHLEN.format(nummern="2, 3")
    assert "Still without a form: scene 2, 3" in texte[-1]


def test_vollstaendige_formwahl_ohne_fehlzeile(conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 7)
    weiter = []
    monkeypatch.setattr(ueberarbeitung, "weiter_7", lambda *a, **k: weiter.append(1))
    _nachricht(conn, 1, 1, "1 chorus 2 dialogue 3 rap")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "formen_setzen", "wert": "1: chorus | 2: dialogue | 3: rap"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert not any("Still without a form" in t for t in _texte(tg))
    assert weiter == [1]


def test_neue_form_fuer_eine_uebertragene_szene_nimmt_den_text_zurueck(
        conn, padua, tg, einst, szene_spion):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    for s in repo.hole_szenen(conn, 1):
        if s["nummer"] in (1, 2):
            repo.setze_szene_fertig(conn, s["id"], True)
    _nachricht(conn, 1, 1, "scene 2 should be a song")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "formen_setzen", "wert": "2: song"}]})

    erkenner.laufe(klm, tg, conn, einst, 1)

    zwei = _szene(conn, 2)
    assert zwei["form"] == "lied"
    assert not zwei["volltext"] and not zwei["fertig_am"]
    assert zwei["prosa"]  # die Vorlage bleibt
    assert _szene(conn, 1)["volltext"] and _szene(conn, 1)["fertig_am"]
    meldung = _texte(tg)[0]
    # chat_id 1 steht in keiner italienisch_ab_phase6_chats-Liste -- englisch.
    assert meldung.startswith("Noted:")
    assert "transferred again" in meldung
    # Szene 2 ist wieder dran und wird neu uebertragen (Thread-Weg).
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2
    assert szene_spion == [ueberarbeitung.T._AUFTRAG_BUEHNE.format(nummer=2)]


def test_neue_form_ohne_uebertragenen_text_bleibt_wie_bisher(conn, padua):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), volltext=False)
    zeilen = ueberarbeitung._wende_formen_an(conn, 1, "2: rap")
    assert zeilen == [ueberarbeitung.T._ZEILE_FORM_GESETZT.format(nummer=2, form="Rap")]


def test_rueckgaengig_bringt_form_und_buehnentext_zurueck(conn, padua, einst):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    vorher_text = _szene(conn, 2)["volltext"]
    wirkliche, vorher, nachher = erkenner._wende_an_mit_schnappschuss(
        conn, einst, 1, [{"art": "formen_setzen", "wert": "2: song"}])
    lauf_id = erkenner._lege_ruecknahme_an(conn, einst, 1, vorher, nachher, wirkliche)
    from interview_theater import ruecknahme

    assert repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(), ruecknahme.WEICH,
        ruecknahme.HART, ruecknahme.GELEERT) == repo.ZURUECK_OK
    zwei = _szene(conn, 2)
    assert zwei["form"] == "dialog"
    assert zwei["volltext"] == vorher_text


# ---------------------------------------------------------------------------
# Fix 5 -- szene_kuerzen waehrend eines laufenden Laufs
# ---------------------------------------------------------------------------


def _kuerzungsspion(monkeypatch):
    gerufen = []
    monkeypatch.setattr(kuerzung, "starte",
                        lambda *a, **k: gerufen.append(a) or ("ok", True))
    return gerufen


def test_padua_kuerzung_waehrend_der_gesamtpruefung_startet_nicht(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False)
    gerufen = _kuerzungsspion(monkeypatch)
    _nachricht(conn, 1, 1, "shorten scene 2")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_kuerzen", "wert": "2"}]})
    sperre = kurzgeschichte._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    assert gerufen == []
    assert _texte(tg) == [ueberarbeitung.T._TEXT_LAEUFT_NOCH]


def test_padua_kuerzung_und_rueckmeldung_im_besetzten_lauf_genau_eine_zeile(
        conn, padua, tg, einst, monkeypatch, szene_spion):
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    gerufen = _kuerzungsspion(monkeypatch)
    _nachricht(conn, 1, 1, "shorter, and the mother angrier")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_kuerzen", "wert": "1"},
        {"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]})
    sperre = kurzgeschichte._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()

    assert gerufen == [] and szene_spion == []
    assert _texte(tg) == [ueberarbeitung.T._TEXT_LAEUFT_NOCH]


def test_padua_kuerzung_ohne_lauf_startet(conn, padua, tg, einst, monkeypatch):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False)
    gerufen = _kuerzungsspion(monkeypatch)
    erkenner._starte_kuerzung(None, tg, conn, einst, 1,
                              [{"art": "szene_kuerzen", "wert": "2"}])
    assert len(gerufen) == 1


def test_dortmund_kuerzung_ist_nicht_gesperrt(conn, dortmund, tg, einst, monkeypatch):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False)
    gerufen = _kuerzungsspion(monkeypatch)
    sperre = kurzgeschichte._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        ergebnis = erkenner._starte_kuerzung(
            None, tg, conn, einst, 1, [{"art": "szene_kuerzen", "wert": "2"}])
    finally:
        sperre.release()

    assert ergebnis is False
    assert len(gerufen) == 1
    assert ueberarbeitung.T._TEXT_LAEUFT_NOCH not in _texte(tg)


# ---------------------------------------------------------------------------
# Fix-Runde 2
# ---------------------------------------------------------------------------


def _szene_2_neu_geformt_waehrend_szene_3_laeuft(conn, tg, einst, szene_spion):
    """Szene 3 wird uebertragen (Sperre), die Gruppe formt Szene 2 um; danach
    ist Szene 3 fertig und steht mit "Yes, save (3)" da."""
    _stueck(conn, 7, formen=("chor", "dialog", "rap"), sprechweisen_fix=True)
    for s in repo.hole_szenen(conn, 1):
        if s["nummer"] in (1, 2):
            repo.setze_szene_fertig(conn, s["id"], True)
    _nachricht(conn, 1, 1, "scene 2 should be a song")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "formen_setzen", "wert": "2: song"}]})
    sperre = szene._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        erkenner.laufe(klm, tg, conn, einst, 1)
    finally:
        sperre.release()
    assert szene_spion == []  # besetzt: keine Uebertragung angestossen
    assert not _szene(conn, 2)["volltext"]
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2
    knoepfe.zeige_geprueft_szene(conn, tg, einst, 1, 3, None)
    return _knopf_der_art(conn, tg, knoepfe.ART_SZENE_PASST)


def test_veraltetes_ja_3_startet_die_neue_uebertragung_von_szene_2(
        conn, padua, tg, einst, szene_spion):
    ja_3 = _szene_2_neu_geformt_waehrend_szene_3_laeuft(conn, tg, einst, szene_spion)

    knoepfe.behandle(conn, tg, None, einst, _druck(ja_3, query_id="ja3"))

    assert szene_spion == [ueberarbeitung.T._AUFTRAG_BUEHNE.format(nummer=2)]
    assert tg.beantwortet[-1][1] == ueberarbeitung.T._ANTWORT_WIRD_UEBERTRAGEN.format(
        nummer=2)
    assert ueberarbeitung.T._TEXT_NICHT_DRAN not in _texte(tg)
    assert not _szene(conn, 3)["fertig_am"]


def test_passt_im_chat_startet_die_neue_uebertragung_von_szene_2(
        conn, padua, tg, einst, szene_spion):
    _szene_2_neu_geformt_waehrend_szene_3_laeuft(conn, tg, einst, szene_spion)

    antwort = ueberarbeitung.nimm_ab(conn, tg, None, einst, 1)

    assert antwort == ueberarbeitung.T._ANTWORT_WIRD_UEBERTRAGEN.format(nummer=2)
    assert szene_spion == [ueberarbeitung.T._AUFTRAG_BUEHNE.format(nummer=2)]


def _prompt(conn, einst, text):
    from interview_theater import kontext

    _nachricht(conn, 1, 90, text)
    ausloeser = [n for n in repo.unextrahierte(conn, 1) if n["message_id"] == 90]
    return kontext.baue(conn, 1, ausloeser, einst)


def _hinweis(stufe):
    from interview_theater import kontext

    return kontext.T._PHASENHINWEIS.format(bezeichnung=phasen.bezeichnung(stufe))


def test_padua_prompt_fragt_mitten_in_phase_6_nicht_nach_phase_7(conn, padua, einst):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 7

    prompt = _prompt(conn, einst, "what do you think of the ending?")

    assert _hinweis(7) not in prompt
    assert repo.hole_phase_angeboten(conn, 1) != 7


def test_padua_prompt_fragt_in_phase_5_nicht_nach_phase_6(conn, padua, einst):
    _stueck(conn, 5, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 6

    assert _hinweis(6) not in _prompt(conn, einst, "what next?")


def test_dortmund_prompt_traegt_den_hinweis_auf_phase_7(conn, dortmund, einst):
    _stueck(conn, 6, gesamt_fix=False, ueberarbeitet=False, volltext=False)
    assert phasen.offenes_angebot(conn, 1) == 7

    assert _hinweis(7) in _prompt(conn, einst, "was meint ihr zum Ende?")

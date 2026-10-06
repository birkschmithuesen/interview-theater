"""Der Dauerknopf "Fragen umformulieren" ("Rephrase questions") im CoThinker
UND in der Werkbank (Padua, Karte t_1f13a707): sichtbar vom Moment, in dem
die Fragen feststehen (Sortierung geschlossen), bis zum ERSTEN
aufgezeichneten Interview der Gruppe (``web_daten.gruppe_nach_token``,
Feld ``umformulieren_knopf_zeigen``).

Ein Tipp legt nur den versteckten Befehl ``/umformulieren`` als Eingang ab
-- derselbe Weg wie ``auswahl_fertig_post``/``/sortiert`` bei "Fertig
sortiert" -- und ist idempotent, waehrend ``fragen_warte_auf ==
'umformulieren'`` schon gesetzt ist (eine laufende Rueckfrage bekommt keine
zweite)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_daten, web_vereint, workshop

CHAT = 7_000_000_000_051
SCHLUESSEL = b"x" * 32


@pytest.fixture
def datenbank(tmp_path):
    """Phase 2, Fragen stehen fest, Sortierung geschlossen, kein Interview --
    genau der Zustand, in dem der Knopf scheinen soll."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Casa\nMare")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen",
        "Casa: Wo ist dein Zuhause?\nMare: Was bringt das Meer?",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", None)
    repo.setze_phase(conn, CHAT, 2)
    conn.commit()
    conn.close()
    return pfad, token


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)


def _gruppe(pfad, token):
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()


# -- web_daten: die drei Bedingungen, jede einzeln umgeklappt -----------------


def test_knopf_zeigt_sich_sortiert_und_ohne_interview(datenbank, padua):
    daten = _gruppe(*datenbank)
    assert daten["umformulieren_knopf_zeigen"] is True


def test_knopf_bleibt_weg_ohne_profil(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    daten = _gruppe(*datenbank)
    assert daten["umformulieren_knopf_zeigen"] is False


def test_knopf_bleibt_weg_waehrend_noch_sortiert_wird(datenbank, padua):
    pfad, token = datenbank
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "")
    conn.close()
    daten = _gruppe(pfad, token)
    assert daten["umformulieren_knopf_zeigen"] is False


def test_knopf_bleibt_weg_nach_dem_ersten_interview(datenbank, padua):
    pfad, token = datenbank
    conn = db.verbinde(pfad)
    repo.lege_aufnahme_an(conn, CHAT, 1, "lang", "telegram", status="fertig")
    conn.commit()
    conn.close()
    daten = _gruppe(pfad, token)
    assert daten["umformulieren_knopf_zeigen"] is False


# -- HTML: CoThinker-Fragen-Panel ---------------------------------------------


def test_cothinker_zeigt_den_knopf_in_der_fragenuebersicht():
    seite = web._fragenuebersicht_html([], zeige_umformulieren_knopf=True)
    assert 'data-ansicht="fragen"' in seite
    assert '<button type="button" class="umformulieren-knopf">' in seite
    assert web.T._TEXT_UMFORMULIEREN_KNOPF in seite


def test_cothinker_zeigt_den_knopf_auch_mit_eintraegen():
    eintraege = [{"begriff": "Casa", "fragen": ["Wo ist dein Zuhause?"]}]
    seite = web._fragenuebersicht_html(eintraege, zeige_umformulieren_knopf=True)
    assert '<button type="button" class="umformulieren-knopf">' in seite


def test_cothinker_ohne_flag_keinen_knopf():
    seite = web._fragenuebersicht_html([], zeige_umformulieren_knopf=False)
    assert "umformulieren-knopf" not in seite


def test_cothinker_ohne_flag_keinen_knopf_vorgabewert():
    # Ohne zweites Argument (Vorgabe) ebenso weg -- bestehende Aufrufer, die
    # das Argument (noch) nicht mitgeben, zeigen nie versehentlich den Knopf.
    seite = web._fragenuebersicht_html([])
    assert "umformulieren-knopf" not in seite


def test_buehne_html_reicht_das_flag_durch():
    mit = web._buehne_html({
        "fragenuebersicht_zeigen": True, "fragenuebersicht": [],
        "umformulieren_knopf_zeigen": True,
    })
    assert "umformulieren-knopf" in mit
    ohne = web._buehne_html({
        "fragenuebersicht_zeigen": True, "fragenuebersicht": [],
        "umformulieren_knopf_zeigen": False,
    })
    assert "umformulieren-knopf" not in ohne


# -- HTML: Werkbank-Fragenabschnitt -------------------------------------------


_STANDFELDER = (
    "phase", "begriffe", "fragen", "frage_einleitungen", "fragen_weich",
    "fragen_herkunft_final", "interview_eroeffnung", "interview_abschluss",
    "kernthema", "kernthema_begruendung", "format", "rahmen", "kernthema_richtung",
    "kernfrage", "geschichte", "figuren_fixiert_am", "hauptkonflikt", "geaendert_am",
)


def _mini(phasen_liste=None, **mehr) -> dict:
    daten = {
        "titel": "Test group", "chat_id": 1, "web_token": None, "kanal": "web",
        "arbeitsstand": dict.fromkeys(_STANDFELDER), "journal": [], "interviews": [],
        "figuren": [], "szenen": [], "festlegungen": [], "fragen_auswertung": None,
        "sprechanteile": None, "dramaturgie": None,
        "werkbank": {"phasen": phasen_liste or [], "begriffe_detail": [], "szenen_anzahl": None},
    }
    daten.update(mehr)
    return daten


def _block(seite: str, nummer: int) -> str:
    anfang = seite.index(f'data-wb-phase="{nummer}"')
    ende = (seite.index('<details class="wb-phase"', anfang + 1) if nummer < 7
            else seite.index('class="wb-journal"'))
    return seite[anfang:ende]


def test_werkbank_zeigt_den_knopf_in_phase_2():
    from interview_theater import roadmap

    phasen_liste = roadmap.werkbank({
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 2,
        "interviewmodus": False, "tippt": False, "strom": None,
    }, 2)
    daten = _mini(phasen_liste, umformulieren_knopf_zeigen=True)
    block = _block(web.werkbank_koerper(daten), 2)
    assert '<button type="button" class="umformulieren-knopf">' in block


def test_werkbank_ohne_flag_keinen_knopf():
    from interview_theater import roadmap

    phasen_liste = roadmap.werkbank({
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 2,
        "interviewmodus": False, "tippt": False, "strom": None,
    }, 2)
    daten = _mini(phasen_liste, umformulieren_knopf_zeigen=False)
    block = _block(web.werkbank_koerper(daten), 2)
    assert "umformulieren-knopf" not in block


def test_werkbank_ohne_das_feld_keinen_absturz_und_keinen_knopf():
    # Bestehende Aufrufer (keine Datenbankspalte, altes Dict) duerfen nicht
    # abstuerzen und zeigen den Knopf nicht.
    from interview_theater import roadmap

    phasen_liste = roadmap.werkbank({
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 2,
        "interviewmodus": False, "tippt": False, "strom": None,
    }, 2)
    daten = _mini(phasen_liste)
    block = _block(web.werkbank_koerper(daten), 2)
    assert "umformulieren-knopf" not in block


# -- Das JS haengt nur unter Padua, genau wie bei "Fertig sortiert" ----------


def test_js_fuer_den_umformulieren_knopf_haengt_nur_unter_padua(datenbank, monkeypatch):
    pfad, token = datenbank
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, CHAT)
    finally:
        lesend.close()

    def rendere():
        return web_vereint.seite(daten, chatdaten, roadmapdaten, "n", token,
                                 "/theatersoap", 45_000, {}, True)

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    assert "umformulieren-knopf" not in rendere()
    assert "chat/umformulieren" not in rendere()
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    assert "chat/umformulieren" in rendere()


# -- POST /g/<token>/chat/umformulieren --------------------------------------


@pytest.fixture
def server(datenbank):
    pfad, token = datenbank
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _post(url, nutzlast):
    anfrage = urllib.request.Request(
        url, data=json.dumps(nutzlast).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _eingaenge(pfad):
    conn = db.verbinde(pfad)
    try:
        return [(z["typ"], z["text"]) for z in repo.web_eingang(conn, CHAT, 0)]
    finally:
        conn.close()


def test_umformulieren_post_legt_den_befehl_in_den_eingang(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/umformulieren",
                      {"nonce": web.nonce(SCHLUESSEL, token)})
    assert status == 202
    assert _eingaenge(pfad) == [(repo.WEB_TYP_BEFEHL, "/umformulieren")]


def test_umformulieren_post_ohne_nonce_ist_403(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/umformulieren", {})
    assert status == 403
    assert _eingaenge(pfad) == []


def test_umformulieren_post_ist_idempotent_waehrend_die_rueckfrage_laeuft(server):
    """Doppel-Tap: die zweite Anfrage legt KEINEN zweiten Eingang an, solange
    ``fragen_warte_auf == 'umformulieren'`` schon gesetzt ist -- das waere
    die zweite Rueckfrage an eine Gruppe, die die erste noch nicht
    beantwortet hat."""
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", "umformulieren")
    conn.close()

    status, _ = _post(f"{basis}/g/{token}/chat/umformulieren",
                      {"nonce": web.nonce(SCHLUESSEL, token)})
    assert status == 202
    assert _eingaenge(pfad) == []


def test_umformulieren_post_nach_der_rueckfrage_wieder_normal(server):
    """Ist die Rueckfrage beantwortet (``fragen_warte_auf`` wieder leer),
    legt ein weiterer Tipp wieder ganz normal einen Eingang an."""
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", None)
    conn.close()

    status, _ = _post(f"{basis}/g/{token}/chat/umformulieren",
                      {"nonce": web.nonce(SCHLUESSEL, token)})
    assert status == 202
    assert _eingaenge(pfad) == [(repo.WEB_TYP_BEFEHL, "/umformulieren")]


def test_umformulieren_weg_ist_registriert():
    assert "umformulieren" in web_chat._POSTWEGE
    assert "umformulieren" in web_chat._TOEPFE

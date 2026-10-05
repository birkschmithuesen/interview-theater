"""Die Auswahlliste im CoThinker (Padua Phase 2, 05.10.2026): je Frage
✓ behalten / ✗ weg / ✎ umformulieren, Zaehler, "Fertig sortiert".

Der Webserver schreibt die Entscheidung selbst (``repo.setze_fragen_entscheidung``,
ein Feldwert wie ``web_schreiben``) -- kein Knopf ``k:<id>``, kein
Modellaufruf. "Fertig sortiert" legt nur den versteckten Befehl ``/sortiert``
als Eingang ab, wie der Phasenklick ``/phaseklick``."""

import json
import re
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_daten, web_vereint, workshop

CHAT = 7_000_000_000_041
SCHLUESSEL = b"x" * 32

LISTE = {
    "gruppen": [
        {"titel": "Casa", "eintraege": [
            {"nummer": 1, "text": "Wo ist <dein> Zuhause?", "herkunft": "eigen",
             "zustand": "ja"},
            {"nummer": 2, "text": "Was riecht nach Casa?", "herkunft": "ki",
             "zustand": ""},
        ]},
        {"titel": "", "eintraege": [
            {"nummer": 3, "text": "Ohne Begriff", "herkunft": "", "zustand": "nein"},
            {"nummer": 4, "text": "Noch eine", "herkunft": "ki", "zustand": "schaerfen"},
        ]},
    ],
    "zaehler": {"ja": 1, "nein": 1, "schaerfen": 1, "offen": 1},
}


# -- HTML --------------------------------------------------------------------


def test_auswahlliste_rendert_gruppen_zaehler_und_knoepfe():
    seite = web._auswahlliste_html(LISTE, liste="fragen")
    assert seite.startswith(
        '<div id="buehne-panel" data-ansicht="auswahl" data-liste="fragen">'
    )
    assert ('<p class="auswahl-zaehler">1 behalten · 1 weg · 1 umformulieren · '
            '1 offen</p>') in seite
    # Gruppentitel nur, wo einer ist.
    assert seite.count("<h3") == 1 and ">Casa</h3>" in seite
    assert '<li data-nummer="1" data-zustand="ja">' in seite
    assert '<li data-nummer="2" data-zustand="offen">' in seite
    assert '<li data-nummer="3" data-zustand="nein">' in seite
    assert '<li data-nummer="4" data-zustand="schaerfen">' in seite
    assert '<span class="herkunft">eigene</span>' in seite
    assert seite.count('<span class="herkunft">KI</span>') == 2
    # je Zeile drei Knoepfe, gedrueckt ist genau der aktuelle Zustand
    assert seite.count('class="auswahl-knopf"') == 12
    assert seite.count('aria-pressed="true"') == 3
    assert re.search(r'data-wert="ja" aria-pressed="true"[^>]*>✓</button>', seite)
    assert 'data-wert="nein"' in seite and 'data-wert="schaerfen"' in seite
    assert ('<button type="button" class="auswahl-fertig">Fertig sortiert – offene '
            'zählen als behalten</button>') in seite


def test_auswahlliste_maskiert_alles():
    seite = web._auswahlliste_html(LISTE, liste="fragen")
    assert "<dein>" not in seite
    assert "Wo ist &lt;dein&gt; Zuhause?" in seite


def test_auswahlliste_ohne_style_und_handler():
    seite = web._auswahlliste_html(LISTE, liste="fragen")
    assert "style=" not in seite
    assert not re.search(r"\son\w+=", seite)


def test_buehne_zeigt_auswahlliste_vor_der_fragenuebersicht():
    seite = web._buehne_html({
        "fragenuebersicht_zeigen": True, "fragenuebersicht": [],
        "auswahlliste": LISTE,
    })
    assert 'data-ansicht="auswahl"' in seite
    ohne = web._buehne_html({
        "fragenuebersicht_zeigen": True, "fragenuebersicht": [],
        "auswahlliste": None,
    })
    assert 'data-ansicht="fragen"' in ohne


# -- web_daten ---------------------------------------------------------------


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Casa\nMare")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl",
        "Casa: Wo ist dein Zuhause?\nMare: Was bringt das Meer?\nCasa: Wer wohnt da?",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki,ki")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,,nein")
    repo.setze_phase(conn, CHAT, 2)
    conn.commit()
    conn.close()
    return pfad, token


def _gruppe(pfad, token):
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()


def test_web_daten_liefert_auswahlliste_in_phase_2_unter_padua(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    daten = _gruppe(*datenbank)
    liste = daten["auswahlliste"]
    assert liste["zaehler"] == {"ja": 1, "nein": 1, "schaerfen": 0, "offen": 1}
    assert [g["titel"] for g in liste["gruppen"]] == ["Casa", "Mare"]
    assert 'data-ansicht="auswahl"' in web._buehne_html(daten)


def test_web_daten_ohne_profil_keine_auswahlliste(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    assert _gruppe(*datenbank)["auswahlliste"] is None


def test_web_daten_andere_phase_keine_auswahlliste(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    conn = db.verbinde(pfad)
    repo.setze_phase(conn, CHAT, 3)
    conn.close()
    assert _gruppe(pfad, token)["auswahlliste"] is None


def test_web_daten_ohne_fragen_auswahl_keine_auswahlliste(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "")
    conn.close()
    daten = _gruppe(pfad, token)
    assert daten["auswahlliste"] is None
    assert 'data-ansicht="fragen"' in web._buehne_html(daten)


# -- Skript nur unter Padua --------------------------------------------------


def test_auswahl_skript_haengt_nur_unter_padua(datenbank, monkeypatch):
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
    assert "sende('chat/auswahl'" not in rendere()
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    mit = rendere()
    assert "sende('chat/auswahl'" in mit and "sende('chat/auswahl_fertig'" in mit


# -- POST ---------------------------------------------------------------------


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


def _entschieden(pfad):
    conn = db.verbinde(pfad)
    try:
        return repo.hole_arbeitsstand(conn, CHAT)["fragen_entschieden"]
    finally:
        conn.close()


def _eingaenge(pfad):
    conn = db.verbinde(pfad)
    try:
        return [(z["typ"], z["text"]) for z in repo.web_eingang(conn, CHAT, 0)]
    finally:
        conn.close()


def test_auswahl_post_schreibt_die_entscheidung(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "fragen",
                       "nummer": 2, "wert": "schaerfen"})
    assert status == 200
    assert _entschieden(pfad) == "ja,schaerfen,nein"
    # Rueckgaengig: derselbe Knopf noch einmal -> ""
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "fragen",
                       "nummer": 1, "wert": ""})
    assert status == 200
    assert _entschieden(pfad) == ",schaerfen,nein"
    # kein Eingang fuer den Bot -- ein Feldwert, kein Befehl
    assert _eingaenge(pfad) == []


@pytest.mark.parametrize("nutzlast", [
    {"liste": "fragen", "nummer": 1, "wert": "vielleicht"},
    {"liste": "fragen", "nummer": 1, "wert": None},
    {"liste": "fragen", "nummer": 99, "wert": "ja"},
    {"liste": "fragen", "nummer": 0, "wert": "ja"},
    {"liste": "fragen", "nummer": True, "wert": "ja"},
    {"liste": "fragen", "nummer": "1", "wert": "ja"},
    {"liste": "figuren", "nummer": 1, "wert": "ja"},
    {"nummer": 1, "wert": "ja"},
])
def test_auswahl_post_lehnt_unsinn_ab(server, nutzlast):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      dict(nutzlast, nonce=web.nonce(SCHLUESSEL, token)))
    assert status == 400
    assert _entschieden(pfad) == "ja,,nein"


def test_auswahl_post_ohne_nonce_ist_403(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      {"liste": "fragen", "nummer": 2, "wert": "ja"})
    assert status == 403
    assert _entschieden(pfad) == "ja,,nein"


def test_fertig_sortiert_legt_sortiert_in_den_eingang(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl_fertig",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "fragen"})
    assert status == 202
    assert _eingaenge(pfad) == [(repo.WEB_TYP_BEFEHL, "/sortiert")]


def test_fertig_sortiert_unbekannte_liste_ist_400(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl_fertig",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "x"})
    assert status == 400
    assert _eingaenge(pfad) == []

"""Szenenkarten im CoThinker-Tab (Birk 07.10.2026 ~19:25, verbindlich):
aktive Karte gross mit "Yes, save" / "No, change", die anderen je EINE Zeile;
"No, change" -> Feedbackfrage im Chat; die geaenderte Karte kommt im Chat zur
Bestaetigung ("Yes, save card" / "No, change again"), "Yes" springt zurueck in
den CoThinker. Nichts wird still gespeichert."""

import json
import threading

import pytest

from interview_theater import (
    befehle, db, phasen, repo, szenenfolge, szenenkarte, ueberarbeitung, web,
    web_daten, web_vereint, workshop,
)

from test_szenenkarte import LLM, TG, _lage, padua  # noqa: F401
from test_web_auswahl import SCHLUESSEL, _post

KARTE = {"typ": "spoken", "modus": "none", "worum": "Die Stimmen werden geteilt.",
         "ort": "Halbkreis", "wer": "Emma", "punkte": ["Emma beginnt"],
         "zitate": [{"zitat": "Casa non sono le mura", "interview": "Interview 19"}],
         "fragen": []}


def test_panel_aktive_karte_gross_andere_eine_zeile(padua):
    liste = [
        {"nummer": 1, "titel": "Tornare", "karte": KARTE, "bestaetigt": True, "aktiv": False},
        {"nummer": 2, "titel": "Le voci", "karte": KARTE, "bestaetigt": False, "aktiv": True},
        {"nummer": 3, "titel": "Il rituale", "karte": None, "bestaetigt": False, "aktiv": False},
    ]
    html = web._szenenkarten_html(liste)
    assert html.startswith('<div id="buehne-panel" data-ansicht="karten">')
    assert '<li class="karte-zeile fertig">✓ 1. Tornare</li>' in html
    assert '<li class="karte-zeile spaeter">3. Il rituale</li>' in html
    assert html.count('class="karte-aktiv"') == 1 and "Die Stimmen werden geteilt." in html
    assert 'data-aktion="ja" data-nummer="2">Yes, save</button>' in html
    assert 'data-aktion="aendern" data-nummer="2">No, change</button>' in html
    assert "Card 2 of 3" in html


def test_panel_karte_entsteht_noch(padua):
    html = web._szenenkarten_html([{"nummer": 1, "titel": "A", "karte": None,
                                    "bestaetigt": False, "aktiv": True}])
    assert "Card 1 is being built" in html
    assert 'data-aktion="bauen" data-nummer="1">Build card now</button>' in html
    assert 'data-aktion="ja"' not in html


def test_web_daten_nur_in_phase_6_mit_schalter(conn, padua, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    ids = _lage(conn)
    repo.setze_szenenkarte(conn, ids[0], json.dumps(KARTE))
    repo.setze_szenenkarte_bestaetigt(conn, ids[0])
    liste = web_daten.szenenkarten(conn, 1)
    assert [(k["nummer"], k["bestaetigt"], k["aktiv"]) for k in liste] == [(1, True, False), (2, False, True)]


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 41, "gruppe1", "G")
    repo.setze_gruppe_kanal(conn, 41, "web")
    token = repo.stelle_web_token_sicher(conn, 41)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def test_karte_post_legt_versteckten_befehl_an(server):
    basis, token, pfad = server
    for aktion, nummer, erwartet in (("ja", 2, 202), ("aendern", 3, 202), ("weg", 1, 400),
                                     ("ja", 0, 400), ("ja", True, 400)):
        status, _ = _post(f"{basis}/g/{token}/chat/karte",
                          {"nonce": web.nonce(SCHLUESSEL, token), "aktion": aktion,
                           "nummer": nummer})
        assert status in ((200, 202) if erwartet == 202 else (400,)), (aktion, nummer, status)
    conn = db.verbinde(pfad)
    try:
        texte = [z["text"] for z in repo.web_eingang(conn, 41, 0)]
    finally:
        conn.close()
    assert texte == ["/karte_ja 2", "/karte_aendern 3"]
    status, _ = _post(f"{basis}/g/{token}/chat/karte", {"nonce": "falsch", "aktion": "ja",
                                                         "nummer": 1})
    assert status == 403


def _web(conn):
    repo.sichere_gruppe(conn, 1, "gruppe1", "G")
    repo.setze_gruppe_kanal(conn, 1, "web")


def test_befehle_und_ablauf_im_cothinker(conn, einst, padua, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    _web(conn)
    ids = _lage(conn)
    schritte = [z["id"] for z in repo.schaerfungen(conn, 1)]
    from interview_theater import schaerfung
    schaerfung.uebernimm_stellen(conn, 1, schritte)
    phasen.setze(conn, 1, 6, "befehl")
    tg, klm = TG(), LLM()

    # Karte 1 entsteht: im Chat nur der Hinweis, keine Knoepfe, kein Kartentext.
    ueberarbeitung.weiter_6(conn, tg, klm, einst, 1).join(5)
    assert tg.texte[-1] == "Card 1 of 2 is ready in the CoThinker tab."
    assert not tg.leisten

    # "No, change" im CoThinker -> Feedbackfrage, naechste Nachricht = Notiz.
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_aendern", "1")
    assert tg.texte[-1] == "What should change on card 1?"
    assert szenenfolge.nimm_regienotiz(1) == 1

    # Die geaenderte Karte kommt im Chat zur Bestaetigung, nicht still.
    ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "Emma sings first", nummer=1).join(5)
    assert "Scene card 1" in tg.texte[-1]
    assert [b for b, _ in tg.leisten[-1]] == ["Yes, save card", "No, change again"]
    assert not repo.hole_szene(conn, ids[0])["karte_bestaetigt_am"]

    # "Yes" (Befehl aus dem CoThinker) speichert und baut die naechste Karte.
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_ja", "1")
    import time
    for _ in range(100):
        if tg.texte[-1] == "Card 2 of 2 is ready in the CoThinker tab.":
            break
        time.sleep(0.05)
    assert repo.hole_szene(conn, ids[0])["karte_bestaetigt_am"]
    assert tg.texte[-1] == "Card 2 of 2 is ready in the CoThinker tab."

    # Veraltet / falsche Phase: wirkungslos.
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_ja", "1")
    assert tg.texte[-1] == szenenkarte.T._TEXT_NICHT_DRAN
    phasen.setze(conn, 1, 5, "befehl")
    vorher = len(tg.texte)
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_ja", "2")
    assert len(tg.texte) == vorher


def test_telegram_behaelt_die_karte_im_chat(conn, einst, padua, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    _lage(conn)
    from interview_theater import schaerfung
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    tg = TG()
    ueberarbeitung.weiter_6(conn, tg, LLM(), einst, 1).join(5)
    assert "Scene card 1" in tg.texte[-1]
    assert [b for b, _ in tg.leisten[-1]] == ["Yes, save", "No, change"]


def test_cothinker_tab_in_phase_6_nur_mit_karten(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    assert web_vereint._karten_im_cothinker() is True
    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: False)
    assert web_vereint._karten_im_cothinker() is False
    assert "__KARTEN_PHASE__" in web_vereint._VEREINT_JS


def test_chat_karte_ohne_zitatzeichen_und_panel_ohne_klassenkollision(padua):
    """Handy-Screens 07.10.2026: der Web-Chat kennt keine Zitatbloecke ("> "
    stand roh da), und ``.karte`` ist im CoThinker schon die Buehnenkarte
    (doppelter Rahmen) -- der Kartenkoerper heisst deshalb ``szenenkarte``."""
    text = szenenkarte.karte_text(KARTE, {"nummer": 2, "titel": "Le voci"})
    assert not any(z.startswith(">") for z in text.splitlines())
    assert '- *“Casa non sono le mura”* (Interview 19)' in text
    html = web._szenenkarten_html([{"nummer": 1, "titel": "A", "karte": KARTE,
                                    "bestaetigt": False, "aktiv": True}])
    assert 'class="szenenkarte"' in html and 'class="karte"' not in html


def test_karte_bauen_rettet_eine_haengende_karte(conn, einst, padua, monkeypatch):
    """Usertest 07.10.2026: Neustart mitten in der Erzeugung -> "being built"
    fuer immer. "/karte_bauen N" stoesst die aktuelle Karte neu an; fuer eine
    andere Nummer passiert nichts."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    _web(conn)
    ids = _lage(conn)
    from interview_theater import schaerfung
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    tg, klm = TG(), LLM()
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_bauen", "2")
    assert klm.aufrufe == []
    befehle._befehl_karte(conn, tg, klm, einst, 1, "/karte_bauen", "1")
    import time
    for _ in range(100):
        if repo.hole_szene(conn, ids[0])["karte"]:
            break
        time.sleep(0.05)
    assert szenenkarte.karte_von(repo.hole_szene(conn, ids[0])) is not None

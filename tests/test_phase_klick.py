"""Ein Klick auf eine Phase ist dasselbe wie ``/phase N`` -- bis auf die Quelle.

Birk, 30.09.2026: "weg von reiner chat navigation, deterministisch ist
vorzuziehen." Der Klick geht durch dieselbe Funktion wie der Befehl
(``befehle.wechsle_phase``), damit er nie in einer anderen Phase landet.

Der Webserver setzt dabei nichts: er legt einen Eingang ab, der Bot fuehrt
ihn aus -- ``knoepfe.eintritt_in_phase`` stoesst Modellarbeit an, und der
Webserver hat kein ``klm``.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import befehle, db, phasen, repo, web, web_vereint

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


class Einstellungen:
    bot_name = "gruppe1"


class TgAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def _gruppe(tmp_path, name="t.db"):
    conn = db.verbinde(str(tmp_path / name))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    return conn


# -- ein Weg, zwei Quellen ---------------------------------------------------


def test_klick_und_befehl_landen_in_derselben_phase(tmp_path):
    """Die Abnahme aus Birks Nachtrag: Klick auf Phase 5 == /phase 5."""
    ergebnisse = {}
    for name, text in (("befehl", "/phase 5"), ("klick", "/phaseklick 5")):
        conn = _gruppe(tmp_path, f"{name}.db")
        tg = TgAttrappe()
        befehle.behandle(conn, tg, Einstellungen(), CHAT, text, None, klm=None)
        journal = conn.execute(
            "SELECT art, text, quelle FROM journal WHERE chat_id = ?", (CHAT,)
        ).fetchall()
        ergebnisse[name] = (phasen.aktuelle(conn, CHAT),
                            [(z["art"], z["text"]) for z in journal],
                            [z["quelle"] for z in journal],
                            tg.gesendet)

    assert ergebnisse["befehl"][0] == ergebnisse["klick"][0] == 5
    # Gleiche Journalzeile BIS AUF die Quelle.
    assert ergebnisse["befehl"][1] == ergebnisse["klick"][1]
    assert ergebnisse["befehl"][2] == ["befehl"]
    assert ergebnisse["klick"][2] == ["web"]
    # Gleiche Eintrittsnachricht(en) im Chat.
    assert ergebnisse["befehl"][3] == ergebnisse["klick"][3]


def test_rueckwaerts_geht_auch(tmp_path):
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 7)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 2",
                     None, klm=None)
    assert phasen.aktuelle(conn, CHAT) == 2


def test_dieselbe_phase_erzeugt_keinen_journaleintrag(tmp_path):
    """Wie ``phasen.setze``: derselbe Wert ist keine Aenderung."""
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 4)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 4",
                     None, klm=None)
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_der_klickbefehl_wird_nirgends_beworben():
    """Slash-Befehle werden nicht beworben (AGENTS.md) -- und dieser hier ist
    ueberhaupt nur der Weg des Knopfes durch die Naht."""
    assert "/phaseklick" in befehle._BEKANNTE_BEFEHLE
    assert "phaseklick" not in {b["command"] for b in befehle.BEFEHLE_LISTE}


def test_eine_unbekannte_nummer_aendert_nichts(tmp_path):
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 3)
    befehle.behandle(conn, TgAttrappe(), Einstellungen(), CHAT, "/phaseklick 99",
                     None, klm=None)
    assert phasen.aktuelle(conn, CHAT) == 3


# -- der Weg durch den Webserver --------------------------------------------


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
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
        return [dict(z) for z in repo.web_eingang(conn, CHAT, 0)]
    finally:
        conn.close()


def test_ein_klick_legt_den_befehl_in_den_eingang(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token),
                           "nummer": 5, "bestaetigt": 1})
    assert status == 202
    eingaenge = _eingaenge(pfad)
    assert [(z["typ"], z["text"]) for z in eingaenge] == [(repo.WEB_TYP_BEFEHL,
                                                          "/phaseklick 5")]


def test_der_webserver_setzt_die_phase_nicht_selbst(server):
    """Er hat kein ``klm``, und ``eintritt_in_phase`` stoesst Modellarbeit an.
    Gesetzt wird sie im Bot-Prozess."""
    basis, token, pfad = server
    _post(f"{basis}/g/{token}/chat/phase",
          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 5, "bestaetigt": 1})
    conn = db.verbinde(pfad)
    assert repo.hole_phase(conn, CHAT) is None
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_ohne_bestaetigung_passiert_nichts(server):
    """Fehlgriff-Schutz: erst die Rueckfrage, dann der Sprung."""
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 5})
    assert status == 400
    assert _eingaenge(pfad) == []


def test_ohne_nonce_passiert_nichts(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nummer": 5, "bestaetigt": 1})
    assert status == 403
    assert _eingaenge(pfad) == []


@pytest.mark.parametrize("nummer", [0, 99, -1, "fuenf", None])
def test_eine_unmoegliche_nummer_ist_400(server, nummer):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token),
                           "nummer": nummer, "bestaetigt": 1})
    assert status == 400
    assert _eingaenge(pfad) == []


def test_alle_sieben_phasen_sind_klickbar(server):
    basis, token, pfad = server
    for nummer, _name, _satz in phasen.PHASEN:
        status, _text = _post(f"{basis}/g/{token}/chat/phase",
                              {"nonce": web.nonce(SCHLUESSEL, token),
                               "nummer": nummer, "bestaetigt": 1})
        assert status == 202, nummer
    assert len(_eingaenge(pfad)) == len(phasen.PHASEN)


def test_phaseklick_fuer_telegram_gruppe_ist_404(tmp_path):
    """Eine Gruppe ohne Web-Kanal hat keinen Bot, der ``web_post`` liest
    (AGENTS.md, Abschlussreview I3) -- derselbe Schutz wie bei jedem
    anderen ``/chat/*``-Weg, nicht nur bei diesem neuen."""
    pfad = str(tmp_path / "telegram.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        status, _text = _post(f"{basis}/g/{token}/chat/phase",
                              {"nonce": web.nonce(SCHLUESSEL, token),
                               "nummer": 5, "bestaetigt": 1})
        assert status == 404
    finally:
        dienst.shutdown()


# -- die Leiste --------------------------------------------------------------


def test_die_leiste_steht_auf_der_seite_und_ist_knapp(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    # Zugeklappt eine Zeile: Phase, Fortschritt -- aufklappbar zur vollen Liste,
    # und das ohne JavaScript (<details>).
    assert "<details" in text and 'class="roadmap"' in text
    assert "1/7" in text or "1 / 7" in text


def test_jede_phase_traegt_ihren_knopf(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    for nummer, _name, _satz in phasen.PHASEN:
        assert f'data-phase="{nummer}"' in text, nummer


def test_jede_aufgabe_traegt_ihr_sprungziel(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    assert "data-ziel-tab=" in text


def test_das_js_fragt_vor_dem_sprung_nach():
    """Kein Sofortsprung: ein Fehlgriff auf dem Telefon soll keine Phase
    kosten -- dieselbe Inline-Rueckfrage wie beim Entfernen einer Figur."""
    assert "bestaetigt" in web_vereint._VEREINT_JS
    assert "data-sicher" in web_vereint._VEREINT_JS


def test_die_leiste_ohne_chat_hat_keine_klickbaren_phasen(tmp_path):
    """Eine Telegram-Gruppe hat kein ``/chat/phase`` (404, siehe oben) -- ein
    Knopf, der dort nie etwas bewirkt, waere eine toter Knopf. Die Uebersicht
    (Phase/Aufgabe je Stand, Sprungziele) bleibt trotzdem stehen, nur ohne
    ``data-phase``-Knoepfe."""
    pfad = str(tmp_path / "telegram_leiste.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as antwort:
            text = antwort.read().decode("utf-8")
    finally:
        dienst.shutdown()
    assert "<details" in text and 'class="roadmap"' in text
    assert "data-phase=" not in text
    assert "data-ziel-tab=" in text

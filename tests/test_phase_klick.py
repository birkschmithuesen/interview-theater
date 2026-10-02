"""Ein Klick auf eine Phase ist dasselbe wie ``/phase N`` -- bis auf die Quelle.

Birk, 30.09.2026: "weg von reiner chat navigation, deterministisch ist
vorzuziehen." Der Klick geht durch dieselbe Funktion wie der Befehl
(``befehle.wechsle_phase``), damit er nie in einer anderen Phase landet.

Der Webserver setzt dabei nichts: er legt einen Eingang ab, der Bot fuehrt
ihn aus -- ``knoepfe.eintritt_in_phase`` stoesst Modellarbeit an, und der
Webserver hat kein ``klm``.
"""

import json
import re
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
    # Nicht einfach "data-phase=" nicht in text: seit Fix-Runde 1 steht die
    # gleiche Zeichenkette auch im eingebetteten Skript (CSS-Selektor in
    # ``ladeRoadmap``), das auf JEDER Seite mitkommt. Massgeblich ist der
    # Rumpf OHNE das Skript.
    rumpf = re.sub(r"<script>.*?</script>", "", text, flags=re.S)
    assert "data-phase=" not in rumpf
    assert "data-ziel-tab=" in text


# -- Fix-Runde 1 (Review b7ac5a3) --------------------------------------------
#
# 1. Die Antwort des Phasenklicks wird geprueft: ein Fehlschlag zeigt den
#    Servertext und wechselt NICHT in den Chat-Tab; ein 403 frischt den
#    Nonce einmal auf und versucht es genau ein zweites Mal.
# 2. Die Roadmap sitzt ausserhalb des Stand-Panels und blieb nach einem
#    erfolgreichen Klick auf dem alten Stand -- ein eigener Teil
#    (``/teil/roadmap``), nachgeladen im selben Takt wie der Stand.
# 3. Ein neu bewaffneter Phasenknopf entwaffnet jeden anderen; der
#    Netzfehler-Zweig entwaffnet ebenfalls (Beschriftung zurueck).
# 4. ``_leiste_html`` verliert den nie gebrauchten ``nonce_wert``.


def test_der_roadmap_teil_liefert_die_leiste(server):
    basis, token, _pfad = server
    with urllib.request.urlopen(f"{basis}/g/{token}/teil/roadmap", timeout=5) as antwort:
        status = antwort.status
        text = antwort.read().decode("utf-8")
    assert status == 200
    assert "<details" in text and 'class="roadmap"' in text
    assert 'data-phase="1"' in text
    # Kein ganzes Dokument, wie beim Stand-Teil -- nur der Ausschnitt.
    assert "<!doctype html>" not in text


def test_der_roadmap_teil_zeigt_die_aktuelle_phase(server):
    """Nach einem Phasenwechsel zeigt der naechste Abruf des Ausschnitts die
    neue Phase -- genau das, was das JS im selben Takt wie das Stand-Panel
    abholt (Review-Befund 2)."""
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    repo.setze_phase(conn, CHAT, 5)
    conn.commit()
    conn.close()
    with urllib.request.urlopen(f"{basis}/g/{token}/teil/roadmap", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    assert "5/7" in text


def test_der_roadmap_teil_hat_keine_knoepfe_ohne_chat(tmp_path):
    """Dieselbe Regel wie auf der ganzen Seite: eine Telegram-Gruppe
    bekommt auch beim Nachladen keine toten Phasenknoepfe."""
    pfad = str(tmp_path / "telegram_teil.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        with urllib.request.urlopen(f"{basis}/g/{token}/teil/roadmap", timeout=5) as antwort:
            text = antwort.read().decode("utf-8")
    finally:
        dienst.shutdown()
    assert "<details" in text and 'class="roadmap"' in text
    assert "data-phase=" not in text


def test_der_roadmap_teil_fuer_unbekanntes_token_ist_404(server):
    basis, _token, _pfad = server
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(f"{basis}/g/nichtda/teil/roadmap", timeout=5)
    assert fehler.value.code == 404


def test_ein_unbekannter_teil_bleibt_404(server):
    """``roadmap`` kam dazu, ``_TEILE`` ist deshalb kein Freifahrtschein."""
    basis, token, _pfad = server
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(f"{basis}/g/{token}/teil/textbuch", timeout=5)
    assert fehler.value.code == 404


def test_leiste_html_braucht_keinen_nonce_mehr():
    """Review-Befund 4: der Parameter war nie gebraucht -- das Stand-Panel
    traegt das einzige ``id=\"nonce\"`` der Seite."""
    import inspect

    parameter = list(inspect.signature(web_vereint._leiste_html).parameters)
    assert "nonce_wert" not in parameter
    assert parameter == ["roadmapdaten", "klickbar"]


def test_das_js_prueft_den_antwortstatus():
    """Review-Befund 1: vorher wurde die Antwort nie angesehen."""
    assert "r.ok" in web_vereint._VEREINT_JS


def test_das_js_friskt_den_nonce_bei_403():
    """Review-Befund 1, derselbe Grundsatz wie ``web_chat.postJson``: ein
    403 heisst fast immer ein abgelaufener Nonce."""
    js = web_vereint._VEREINT_JS
    assert "friskeNonce" in js
    assert "r.status === 403" in js


def test_das_js_zeigt_den_fehler_ohne_tabwechsel():
    """Review-Befund 1: ``setze('chat')`` steht NUR im Erfolgszweig."""
    js = web_vereint._VEREINT_JS
    assert "zeigeFehler" in js
    treffer = re.search(r"if \(r && r\.ok\) \{[^{}]*setze\('chat'\);", js)
    assert treffer is not None, "setze('chat') sollte im r.ok-Zweig stehen"
    # Ausserhalb dieses einen Zweigs taucht der Tabwechsel nicht noch
    # einmal im Phasenklick auf.
    assert js.count("setze('chat')") == 1


def test_das_js_entwaffnet_auf_jedem_ausgang():
    """Review-Befund 3: Erfolg, Fehlschlag und Netzausfall entwaffnen den
    Knopf gleich -- keiner bleibt auf "Wirklich...?" stehen."""
    js = web_vereint._VEREINT_JS
    assert "entwaffneAlle" in js
    assert js.count("removeAttribute('data-sicher')") >= 3


def test_das_js_laedt_die_roadmap_im_selben_takt():
    """Review-Befund 2: der neue Teil wird im selben ``setInterval`` wie der
    Stand abgeholt, nicht an dessen Sichtbarkeits-Gate gehaengt."""
    js = web_vereint._VEREINT_JS
    assert "ladeRoadmap" in js
    assert "BASIS_TEIL + 'roadmap'" in js
    takt = js[js.index("setInterval(function () {"):]
    assert "ladeRoadmap();" in takt[:takt.index("__NACHLADEN_MS__")]

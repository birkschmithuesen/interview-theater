"""Der SSE-Kanal: `GET /g/<token>/chat/strom`.

Das ist die EINE Stelle, an der diese Karte A2s Vorgabe "kein SSE" aufhebt
(Plan-Kopf, Abweichung 6) -- fuer alles andere bleibt der Poll.

Getestet wird ueber echtes HTTP gegen einen Server auf Port 0, wie der Rest
der Web-Tests. Kein Browser: gelesen wird der Bytestrom selbst.
"""

import http.client
import json
import threading
import time

import pytest

from interview_theater import db, repo, web, web_daten, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield dienst.server_address[1], token, conn
    dienst.shutdown()


def _oeffne(port: int, pfad: str):
    """Eine rohe HTTP-Verbindung -- ``urllib`` liest bis zum Ende, und ein
    SSE-Strom hat keines, solange er laeuft."""
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    verbindung.request("GET", pfad)
    return verbindung, verbindung.getresponse()


def _ereignisse(antwort, bis: int, frist_s: float = 8.0):
    """Liest, bis ``bis`` Datenzeilen da sind oder die Frist ablaeuft."""
    gefunden = []
    ende = time.monotonic() + frist_s
    puffer = b""
    while len(gefunden) < bis and time.monotonic() < ende:
        stueck = antwort.read(1)
        if not stueck:
            break
        puffer += stueck
        while b"\n" in puffer:
            zeile, _, puffer = puffer.partition(b"\n")
            text = zeile.decode("utf-8").strip()
            if text.startswith("data:"):
                gefunden.append(json.loads(text[len("data:"):].strip()))
    return gefunden


def _schreibende_verbindung(conn):
    return db.verbinde(conn.execute("PRAGMA database_list").fetchone()[2])


def test_die_kopfzeilen_stimmen(aufbau):
    port, token, conn = aufbau
    repo.beginne_strom(conn, CHAT, "gespraech")
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
        assert antwort.getheader("Content-Type").startswith("text/event-stream")
        assert antwort.getheader("Cache-Control") == "no-cache"
        # Fuer nginx: ohne das puffert der Reverse-Proxy den Strom zu einem
        # einzigen Block (ANNAHME 6 im Plan-Kopf).
        assert antwort.getheader("X-Accel-Buffering") == "no"
        # HTTP/1.1 ohne Content-Length: die Verbindung MUSS als schliessend
        # angekuendigt werden, sonst wartet der Browser auf den naechsten
        # Request auf derselben Verbindung.
        assert antwort.getheader("Connection") == "close"
    finally:
        verbindung.close()


def test_die_teilstuecke_kommen_einzeln(aufbau):
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "Hallo")

    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")

    def weiterschreiben():
        schreibend = _schreibende_verbindung(conn)
        time.sleep(0.3)
        repo.schreibe_strom(schreibend, sid, "Hallo ihr")
        time.sleep(0.3)
        repo.beende_strom(schreibend, sid, repo.STROM_FERTIG, post_id=9)
        schreibend.close()

    threading.Thread(target=weiterschreiben, daemon=True).start()
    try:
        ereignisse = _ereignisse(antwort, bis=3)
    finally:
        verbindung.close()

    texte = [e.get("text") for e in ereignisse if "text" in e]
    assert "Hallo" in texte and "Hallo ihr" in texte
    assert ereignisse[-1]["zustand"] == repo.STROM_FERTIG
    assert ereignisse[-1]["post_id"] == 9


def test_eine_fertige_zeile_liefert_sofort_das_ende(aufbau):
    """Reconnect: wer sich neu verbindet, bekommt den Endstand und keine
    haengende Verbindung."""
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "fertiger Satz")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=4)

    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        ereignisse = _ereignisse(antwort, bis=2, frist_s=4.0)
    finally:
        verbindung.close()
    assert ereignisse[-1]["zustand"] == repo.STROM_FERTIG
    assert ereignisse[-1]["post_id"] == 4


def test_ohne_strom_endet_die_verbindung_ohne_daten(aufbau):
    """Keine Zeile, kein Ereignis -- und die Verbindung haengt nicht ewig."""
    port, token, _conn = aufbau
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
        assert _ereignisse(antwort, bis=1, frist_s=2.0) == []
    finally:
        verbindung.close()


def test_unbekanntes_token_ist_404(aufbau):
    port, _token, _conn = aufbau
    verbindung, antwort = _oeffne(port, f"/g/gibtsnicht/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 404
    finally:
        verbindung.close()


def test_eine_telegram_gruppe_hat_keinen_strom(aufbau):
    """Wie jeder Weg unter ``/chat`` (Abschlussreview I3): nur Web-Gruppen."""
    port, token, conn = aufbau
    repo.setze_gruppe_kanal(conn, CHAT, "telegram")
    conn.commit()
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 404
    finally:
        verbindung.close()


def test_die_route_greift_auch_unter_dem_praefix(aufbau):
    port, token, conn = aufbau
    repo.beginne_strom(conn, CHAT, "gespraech")
    verbindung, antwort = _oeffne(
        port, f"/theatersoap/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        assert antwort.status == 200
    finally:
        verbindung.close()


def test_der_strom_traegt_keinen_dateipfad_und_kein_transkript(aufbau):
    """Dieselben drei Grenzen wie ueberall im Web."""
    port, token, conn = aufbau
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, sid, "Text")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=1)
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    try:
        ereignisse = _ereignisse(antwort, bis=2, frist_s=4.0)
    finally:
        verbindung.close()
    for ereignis in ereignisse:
        assert set(ereignis) <= {"id", "art", "text", "zustand", "post_id"}


# --- Mehrere Stroeme zugleich (Befund aus Aufgabe 7) -------------------------


def test_ein_aelterer_laufender_strom_haelt_die_verbindung_offen(aufbau):
    """Prosalauf (aelter) und Gespraechszug (juenger) laufen gleichzeitig.
    Endet das Gespraech zuerst, darf die Verbindung nicht schliessen: der
    Prosatext waechst weiter, und jedes Ereignis traegt seine id."""
    port, token, conn = aufbau
    prosa = repo.beginne_strom(conn, CHAT, "prosa")
    repo.schreibe_strom(conn, prosa, "Es war")
    gespraech = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, gespraech, "Moment")

    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")

    def weiterschreiben():
        schreibend = _schreibende_verbindung(conn)
        time.sleep(0.3)
        repo.beende_strom(schreibend, gespraech, repo.STROM_FERTIG, post_id=5)
        time.sleep(0.4)
        repo.schreibe_strom(schreibend, prosa, "Es war einmal")
        time.sleep(0.3)
        repo.beende_strom(schreibend, prosa, repo.STROM_FERTIG, post_id=6)
        schreibend.close()

    threading.Thread(target=weiterschreiben, daemon=True).start()
    try:
        ereignisse = _ereignisse(antwort, bis=10)
    finally:
        verbindung.close()

    je_id = {}
    for ereignis in ereignisse:
        je_id.setdefault(ereignis["id"], []).append(ereignis)
    assert set(je_id) == {prosa, gespraech}
    assert "Es war einmal" in [e["text"] for e in je_id[prosa]]
    assert je_id[gespraech][-1]["zustand"] == repo.STROM_FERTIG
    assert je_id[gespraech][-1]["post_id"] == 5
    assert je_id[prosa][-1]["zustand"] == repo.STROM_FERTIG
    assert je_id[prosa][-1]["post_id"] == 6
    # Das Ende des Gespraechs kam VOR dem weiteren Prosatext.
    reihenfolge = [(e["id"], e["text"], e["zustand"]) for e in ereignisse]
    assert reihenfolge.index((gespraech, "Moment", repo.STROM_FERTIG)) < \
        reihenfolge.index((prosa, "Es war einmal", repo.STROM_LAEUFT))


def test_ein_strom_der_waehrend_der_verbindung_beginnt_kommt_mit(aufbau):
    """Eine neue Zeile hinter dem Start gehoert dazu -- der Szenenlauf beginnt
    oft, waehrend das Gespraech noch laeuft."""
    port, token, conn = aufbau
    gespraech = repo.beginne_strom(conn, CHAT, "gespraech")
    verbindung, antwort = _oeffne(port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
    neu = {}

    def weiterschreiben():
        schreibend = _schreibende_verbindung(conn)
        time.sleep(0.3)
        neu["id"] = repo.beginne_strom(schreibend, CHAT, "szene")
        repo.schreibe_strom(schreibend, neu["id"], "SZENE")
        time.sleep(0.3)
        repo.beende_strom(schreibend, gespraech, repo.STROM_FERTIG, post_id=7)
        time.sleep(0.3)
        repo.beende_strom(schreibend, neu["id"], repo.STROM_FERTIG, post_id=8)
        schreibend.close()

    threading.Thread(target=weiterschreiben, daemon=True).start()
    try:
        ereignisse = _ereignisse(antwort, bis=10)
    finally:
        verbindung.close()
    letzte = {e["id"]: e for e in ereignisse}
    assert letzte[gespraech]["post_id"] == 7
    assert letzte[neu["id"]]["post_id"] == 8
    assert letzte[neu["id"]]["art"] == "szene"


def test_nach_ueberspringt_bekannte_fertige_zeilen(aufbau):
    """``?nach=<id>``: was der Browser schon fertig kennt, kommt nicht noch
    einmal -- eine laufende aeltere Zeile aber sehr wohl."""
    port, token, conn = aufbau
    alt = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, alt, repo.STROM_FERTIG, post_id=1)
    laufend = repo.beginne_strom(conn, CHAT, "prosa")
    juengst = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, juengst, repo.STROM_FERTIG, post_id=2)

    verbindung, antwort = _oeffne(
        port, f"/g/{token}/chat/{web_vereint.STROM_PFAD}?nach={juengst}")

    def beenden():
        schreibend = _schreibende_verbindung(conn)
        time.sleep(0.4)
        repo.beende_strom(schreibend, laufend, repo.STROM_FERTIG, post_id=3)
        schreibend.close()

    threading.Thread(target=beenden, daemon=True).start()
    try:
        ereignisse = _ereignisse(antwort, bis=10)
    finally:
        verbindung.close()
    ids = {e["id"] for e in ereignisse}
    assert alt not in ids
    assert laufend in ids
    assert ereignisse[-1]["id"] == laufend
    assert ereignisse[-1]["post_id"] == 3


def test_stromlage_liefert_die_juengste_zeile(aufbau):
    _port, _token, conn = aufbau
    assert web_daten.web_stromlage(conn, CHAT) is None
    erste = repo.beginne_strom(conn, CHAT, "prosa")
    zweite = repo.beginne_strom(conn, CHAT, "gespraech")
    lage = web_daten.web_stromlage(conn, CHAT)
    assert lage["id"] == zweite
    assert set(lage) == {"id", "art", "text", "zustand", "post_id"}
    assert web_daten.web_stromlage(conn, CHAT, nach=zweite + 1) is None
    assert erste < zweite

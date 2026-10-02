"""Eine verwaiste Stromzeile ist keine laufende (Aufgabe 14, Fix-Runde 1).

Stirbt der Bot-Prozess mitten im Strom, bleibt seine ``web_strom``-Zeile
auf ``laeuft`` -- und die Ansicht zeigte die halbe Antwort ohne Ende
("keine halbe Antwort", Entscheidung E). Zwei Wege dagegen:

(a) der Bot schliesst beim Start im Web-Kanal alle laufenden Zeilen SEINER
    Gruppe als ``abgebrochen`` (``repo.brich_laufende_stroeme_ab``);
(b) die Leseseite behandelt eine Zeile, die seit ``db.STROM_VERALTET_S``
    nicht mehr geschrieben wurde, als ``abgebrochen`` -- ohne zu schreiben
    (der Webserver liest read-only).
"""

import http.client
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import (
    bot, db, einstellungen, repo, roadmap, strom, telegram, web, web_daten,
    web_kanal, web_vereint,
)

CHAT = 7_000_000_000_001
ANDERE = 7_000_000_000_002


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    repo.sichere_gruppe(verbindung, ANDERE, "gruppe2", "Andere")
    yield verbindung
    verbindung.close()


def _altere(conn, strom_id: int, sekunden: float) -> None:
    """Setzt die letzte Schreibzeit einer Zeile in die Vergangenheit -- so
    saehe eine Zeile aus, deren Bot vor ``sekunden`` gestorben ist."""
    alt = (datetime.now(timezone.utc) - timedelta(seconds=sekunden)).isoformat(
        timespec="seconds")
    conn.execute("UPDATE web_strom SET aktualisiert_am = ? WHERE id = ?",
                 (alt, strom_id))
    conn.commit()


def _einstellungen(tmp_path, **zusatz):
    return einstellungen.Einstellungen(
        bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p", **zusatz,
    )


# -- Die Grenze selbst -------------------------------------------------------


def test_die_grenze_liegt_weit_ueber_dem_schreibtakt_und_nicht_ueber_dem_strom():
    """Eine lebende Zeile wird im Takt ``strom.INTERVALL_S`` geschrieben;
    die Grenze liegt Groessenordnungen darueber -- und nicht ueber
    ``STROM_MAX_S``: spaetestens wenn eine SSE-Verbindung ohnehin neu
    aufgebaut wird, ist eine verwaiste Zeile als Ende erkannt."""
    assert db.STROM_VERALTET_S >= 100 * strom.INTERVALL_S
    assert db.STROM_VERALTET_S <= web_vereint.STROM_MAX_S


# -- (a) Beim Start des Bots -------------------------------------------------


def test_brich_laufende_ab_trifft_nur_laufende_zeilen_der_gruppe(conn):
    laufend = repo.beginne_strom(conn, CHAT, "gespraech")
    zweite = repo.beginne_strom(conn, CHAT, "szene")
    fertig = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, fertig, repo.STROM_FERTIG, 5)
    fremd = repo.beginne_strom(conn, ANDERE, "gespraech")

    assert repo.brich_laufende_stroeme_ab(conn, CHAT) == 2

    assert repo.hole_strom(conn, laufend)["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.hole_strom(conn, zweite)["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.hole_strom(conn, laufend)["post_id"] is None
    assert repo.hole_strom(conn, fertig)["zustand"] == repo.STROM_FERTIG
    assert repo.hole_strom(conn, fertig)["post_id"] == 5
    assert repo.hole_strom(conn, fremd)["zustand"] == repo.STROM_LAEUFT
    assert repo.brich_laufende_stroeme_ab(conn, CHAT) == 0


def test_der_web_bot_raeumt_beim_start_auf(tmp_path, conn, caplog):
    verwaist = repo.beginne_strom(conn, CHAT, "gespraech")
    fremd = repo.beginne_strom(conn, ANDERE, "gespraech")
    e = _einstellungen(tmp_path, bot_token="", kanal=einstellungen.KANAL_WEB,
                       web_chat_id=CHAT)
    with caplog.at_level("WARNING"):
        kanal = bot.baue_kanal(conn, e, klient=None)
    assert isinstance(kanal, web_kanal.WebKanal)
    assert repo.hole_strom(conn, verwaist)["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.hole_strom(conn, fremd)["zustand"] == repo.STROM_LAEUFT
    assert any("abgebrochen" in r.getMessage() for r in caplog.records)


def test_der_telegram_weg_raeumt_nichts_auf(tmp_path, conn):
    """E1: der Telegram-Weg bleibt unveraendert -- er hat keine Stroeme."""
    zeile = repo.beginne_strom(conn, CHAT, "gespraech")
    e = _einstellungen(tmp_path, bot_token="1:a")
    assert isinstance(bot.baue_kanal(conn, e, klient=None), telegram.Telegram)
    assert repo.hole_strom(conn, zeile)["zustand"] == repo.STROM_LAEUFT


# -- (b) Die Leseseite ---------------------------------------------------------


def test_laufende_stroeme_uebergeht_eine_verwaiste_zeile(conn):
    alt = repo.beginne_strom(conn, CHAT, "prosa")
    frisch = repo.beginne_strom(conn, CHAT, "gespraech")
    _altere(conn, alt, db.STROM_VERALTET_S + 5)
    assert [z["id"] for z in repo.laufende_stroeme(conn, CHAT)] == [frisch]


def test_eine_frische_zeile_gilt_weiter_als_laufend(conn):
    zeile = repo.beginne_strom(conn, CHAT, "gespraech")
    _altere(conn, zeile, db.STROM_VERALTET_S - 30)
    assert [z["id"] for z in repo.laufende_stroeme(conn, CHAT)] == [zeile]
    assert web_daten.web_stromzeilen(conn, CHAT, 0)[0]["zustand"] == "laeuft"


def test_stromzeilen_melden_eine_verwaiste_zeile_als_abgebrochen(conn):
    zeile = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, zeile, "Die halbe Ant")
    _altere(conn, zeile, db.STROM_VERALTET_S + 5)
    [daten] = web_daten.web_stromzeilen(conn, CHAT, 0)
    assert daten["zustand"] == "abgebrochen"
    # Gelesen, nicht geschrieben: in der Datenbank steht sie unveraendert.
    assert repo.hole_strom(conn, zeile)["zustand"] == repo.STROM_LAEUFT


def test_stromanfang_haelt_sich_nicht_an_einer_verwaisten_zeile_fest(conn):
    alt = repo.beginne_strom(conn, CHAT, "prosa")
    juenger = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, juenger, repo.STROM_FERTIG, 3)
    _altere(conn, alt, db.STROM_VERALTET_S + 5)
    # Ohne Grenze waere es ``alt`` (die aelteste laufende), mit ``nach``
    # gaebe min(nach, alt) ebenfalls ``alt``.
    assert web_daten.web_stromanfang(conn, CHAT) == juenger
    assert web_daten.web_stromanfang(conn, CHAT, juenger + 1) == juenger + 1


def test_stromlage_meldet_eine_verwaiste_zeile_als_abgebrochen(conn):
    zeile = repo.beginne_strom(conn, CHAT, "szene")
    _altere(conn, zeile, db.STROM_VERALTET_S + 5)
    assert web_daten.web_stromlage(conn, CHAT)["zustand"] == "abgebrochen"


def test_die_roadmap_ist_auf_beiden_wegen_gleich(conn):
    """``roadmap.register`` (Bot, ueber ``repo.laufende_stroeme``) und
    ``web_daten.roadmap`` (Webserver) sehen dieselbe laufende Zeile -- die
    aelteste nicht verwaiste -- und eine verwaiste auf beiden Wegen nicht."""
    def szenentexte(phasenliste):
        return next(a["zustand"] for p in phasenliste for a in p["aufgaben"]
                    if a["kennung"] == "szenentexte")

    szene = repo.beginne_strom(conn, CHAT, "szene")
    repo.beginne_strom(conn, CHAT, "gespraech")   # juenger, laeuft daneben
    assert szenentexte(web_daten.roadmap(conn, CHAT)) == "laeuft"
    assert szenentexte(roadmap.register(conn, CHAT)) == "laeuft"
    _altere(conn, szene, db.STROM_VERALTET_S + 5)
    assert szenentexte(web_daten.roadmap(conn, CHAT)) != "laeuft"
    assert szenentexte(roadmap.register(conn, CHAT)) != "laeuft"


# -- (b) Die Route -------------------------------------------------------------


def test_die_route_beendet_eine_verwaiste_zeile_sofort(tmp_path, conn):
    zeile = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.schreibe_strom(conn, zeile, "Die halbe Ant")
    _altere(conn, zeile, db.STROM_VERALTET_S + 5)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(str(tmp_path / "t.db"), "127.0.0.1:0",
                             "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        verbindung = http.client.HTTPConnection(
            "127.0.0.1", dienst.server_address[1], timeout=10)
        beginn = time.monotonic()
        verbindung.request("GET", f"/g/{token}/chat/{web_vereint.STROM_PFAD}")
        antwort = verbindung.getresponse()
        rumpf = antwort.read().decode("utf-8")   # endet: nichts laeuft mehr
        dauer = time.monotonic() - beginn
        verbindung.close()
    finally:
        dienst.shutdown()
    ereignisse = [json.loads(z[len("data:"):]) for z in rumpf.splitlines()
                  if z.startswith("data:")]
    assert [(e["id"], e["zustand"]) for e in ereignisse] == [(zeile, "abgebrochen")]
    assert dauer < 5

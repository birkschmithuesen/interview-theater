"""``web_vereint.seite()`` fuer Dortmund: byte-gleich wie vor der
Padua-Stepper-Karte (Padua UX Kopfzeile, Task 5/6, 2026-10-03).

Die Vergleichsdatei ``tests/fixtures/web_vereint_dortmund_vorher.html`` ist
mit dem Code VOR dieser Karte erzeugt worden (ohne Profil -- Dortmund und die
eingebaute Vorgabe sind an dieser Stelle gleich, da ``dortmund-2026`` kein
``[web]``-Abschnitt hat und beide auf dieselben ``VORGABE_WERTE`` fallen).
Sie ist die Beweisgrundlage dafuer, dass Dortmund kein Zeichen anders sieht,
nachdem Task 6 den Padua-Stepper hinter ``[web] phasennav_stepper`` einhaengt.

Aufruf wortgleich zu ``.superpowers/sdd/_erzeuge_bitgleich_fixture.py``, das
die Fixture erzeugt hat: fester Token (``stelle_web_token_sicher`` wuerfelt,
also ungeeignet fuer einen Bytevergleich), fester Nonce-String (der echte
CSP-/Formular-Nonce wird nur ueber den HTTP-Handler gesetzt, nicht beim
direkten Aufruf von ``seite()``)."""

import os
from pathlib import Path

import pytest

from interview_theater import db, repo, sprache, web_daten, web_vereint, workshop

WURZEL = Path(__file__).resolve().parent.parent
VORHER = WURZEL / "tests" / "fixtures" / "web_vereint_dortmund_vorher.html"

DB_PFAD = "/tmp/it-bitgleich-test.db"
CHAT = 7_000_000_000_778
TOKEN = "deterministischer-bitgleich-test-token"


def _baue_datenbank() -> None:
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht, Koffer")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhofshalle, spaet nachts, Winter")
    repo.setze_arbeitsstand(
        conn, CHAT, "geschichte",
        "Zwei kommen nachts am selben Bahnhof an und bleiben laenger als geplant, "
        "weil der letzte Zug schon weg ist und der naechste erst morgens faehrt.",
    )
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998 mit einem Koffer")
    repo.setze_figur(conn, CHAT, "Erhan", "holte sie am Bahnhof ab")
    repo.setze_phase(conn, CHAT, 4)
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis", None, None)
    repo.aktualisiere_szene(
        conn, szene_id, "Ankunft am Gleis", None,
        "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\nERHAN: Du kannst ihn jetzt auspacken.",
    )
    conn.execute("UPDATE gruppe SET web_token = ? WHERE chat_id = ?", (TOKEN, CHAT))
    conn.commit()
    conn.close()


def _rendere() -> str:
    lesend = web_daten.oeffne_lesend(DB_PFAD)
    try:
        daten = web_daten.gruppe_nach_token(lesend, TOKEN)
        chatdaten = web_daten.web_chatzustand(lesend, TOKEN)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    return web_vereint.seite(
        daten, chatdaten, roadmapdaten,
        nonce_wert="deterministischer-test-nonce",
        token=TOKEN,
        praefix="/theatersoap",
        segment_ms=45_000,
        fassungswahl={},
        chat_vorhanden=chatdaten is not None,
    )


def _profil(monkeypatch, name: str | None) -> None:
    if name is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture(scope="module", autouse=True)
def _db():
    _baue_datenbank()
    yield
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)


@pytest.mark.dortmund  # Dortmund eingefroren (AGENTS.md, 04.10.2026): vergleicht gegen eine Dortmund-/Vorgabe-Fixture
@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_vereinte_seite_bleibt_byte_gleich(monkeypatch, profil):
    _profil(monkeypatch, profil)
    assert _rendere() == VORHER.read_text(encoding="utf-8")


@pytest.mark.parametrize("profil,erwartet", [
    (None, False), ("dortmund-2026", False), ("padua-2026", True),
])
def test_phasennav_stepper_nur_im_padua_profil(monkeypatch, profil, erwartet):
    _profil(monkeypatch, profil)
    assert workshop.aktiv().wert("web.phasennav_stepper") is erwartet

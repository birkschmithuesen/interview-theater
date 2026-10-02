"""Die vereinte Seite liefert gueltiges JavaScript -- auch auf Englisch.

Fix-Runde Abschluss, Befund 1 (CRITICAL): ``web_vereint.seite`` klebte
``T._TEXT_PHASE_FEHLER_NETZ`` und ``T._TEXT_PHASE_SICHER`` roh in
einfach-gequotete JS-Stringliterale (``'__FEHLER_NETZ__'``,
``'__SICHER__'``). Die englische Fassung
(``interview_theater/sprachen/en/texte.toml``) traegt einen Apostroph
("didn't go through") -- unter ``IT_WORKSHOP=padua-2026`` brach damit das
ganze ``<script>`` der Seite (Chat, Aufnahme, Tabs, Strom: alles tot).

Die Gegenprobe: beide Texte muessen JSON-kodiert (mit ihren eigenen
Anfuehrungszeichen) im Skript stehen, nie als roher Text innerhalb eines
einfach gequoteten Literals."""

import json
import re
import shutil
import subprocess
import tempfile

import pytest

from interview_theater import db, repo, sprache, web, web_chat, web_daten, web_vereint, workshop
from tests.fixture_sprache import baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _baue_seite(tmp_path, chat_id: int = 1) -> str:
    """Baut dieselbe Seite wie ``web_vereint.beantworte_seite`` -- direkt,
    ohne HTTP-Server, wie ``tests/test_web_sprache.py`` es fuer die anderen
    Web-Seiten tut."""
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn, chat_id)
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return web_vereint.seite(
        daten, chatdaten, roadmapdaten, web.nonce(b"k" * 32, token), token,
        "/theatersoap", web_chat._segment_ms(), chat_vorhanden=True,
    )


def _skript(html: str) -> str:
    treffer = re.search(r"<script>(.*)</script>", html, re.DOTALL)
    assert treffer is not None, "kein <script> in der Seite"
    return treffer.group(1)


def test_die_englischen_phasentexte_stehen_json_kodiert_im_skript(tmp_path, padua):
    skript = _skript(_baue_seite(tmp_path))
    assert "{bezeichnung}" in web_vereint.T._TEXT_PHASE_SICHER
    # Die englische Fassung traegt wirklich einen Apostroph -- sonst prueft
    # dieser Test nichts (Positivkontrolle fuer den Befund selbst).
    assert "'" in web_vereint.T._TEXT_PHASE_FEHLER_NETZ
    erwartet_sicher = json.dumps(web_vereint.T._TEXT_PHASE_SICHER, ensure_ascii=True)
    erwartet_fehler = json.dumps(web_vereint.T._TEXT_PHASE_FEHLER_NETZ, ensure_ascii=True)
    assert erwartet_sicher in skript
    assert erwartet_fehler in skript
    # Der kaputte Weg: der rohe Text, umschlossen von einfachen
    # Anfuehrungszeichen (das brach bei "didn't" mitten im Wort ab).
    assert f"'{web_vereint.T._TEXT_PHASE_FEHLER_NETZ}'" not in skript
    assert f"'{web_vereint.T._TEXT_PHASE_SICHER}'" not in skript


def test_das_skript_der_vereinten_seite_ist_gueltiges_javascript(tmp_path, padua):
    node = shutil.which("node")
    if node is None:
        pytest.skip("kein node auf PATH")
    skript = _skript(_baue_seite(tmp_path))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as datei:
        datei.write(skript)
        js_pfad = datei.name
    lauf = subprocess.run([node, "--check", js_pfad], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr


def test_das_deutsche_skript_bleibt_ebenfalls_gueltiges_javascript(tmp_path):
    """Positivkontrolle ohne ``padua``: das deutsche Profil hat denselben
    Code-Pfad und muss weiterhin durchlaufen."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("kein node auf PATH")
    pfad = str(tmp_path / "web-de.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    chat_id = 1
    repo.sichere_gruppe(conn, chat_id, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    repo.setze_arbeitsstand(conn, chat_id, "begriffe", "Heimat, Arbeit")
    token = repo.stelle_web_token_sicher(conn, chat_id)
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    html = web_vereint.seite(
        daten, chatdaten, roadmapdaten, web.nonce(b"k" * 32, token), token,
        "/theatersoap", web_chat._segment_ms(), chat_vorhanden=True,
    )
    skript = _skript(html)
    node = shutil.which("node")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as datei:
        datei.write(skript)
        js_pfad = datei.name
    lauf = subprocess.run([node, "--check", js_pfad], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr

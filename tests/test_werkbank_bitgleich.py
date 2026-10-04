"""Die Werkbank (Arbeitsstand-Tab) bleibt ohne Profilschalter byte-gleich.

Die Vergleichsdateien ``tests/fixtures/werkbank_vorher_*.html`` sind mit dem
Code VOR dem Umbau zur read-only Werkbank erzeugt (Plan
``docs/superpowers/plans/2026-10-03-padua-workbench-readonly.md``,
Aufgabe 1) -- ohne Profil und mit ``IT_WORKSHOP=dortmund-2026``. Sie sind die
Beweisgrundlage dafuer, dass Dortmund kein Zeichen anders sieht
(dasselbe Muster wie ``tests/test_web_dashboard_en.py``).

Neu geschrieben werden sie NUR mit ``IT_WERKBANK_VORHER_SCHREIBEN=1`` -- und
nur auf einem Stand, von dem man weiss, dass er Dortmund nicht veraendert.

Zeitstempel und Token sind festgenagelt (``_fest``): die Gruppe kommt aus
``tests/fixture_sprache.py`` und damit aus ``repo``-Funktionen, die "jetzt"
stempeln. Nur erfundenes Material.
"""

import os
import pathlib
import re
import sqlite3

import pytest

from interview_theater import db, repo, sprache, web, web_chat, web_daten, web_vereint, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SEITEN = ("gruppe", "koerper", "vereint")
TOKEN = "tok-werkbank"
NONCE = "nonce-werkbank"
FEST = "2026-10-03T10:00:00+00:00"
_ISO = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")
SCHREIBEN = os.environ.get("IT_WERKBANK_VORHER_SCHREIBEN") == "1"


def _datei(name: str, profil: str | None) -> pathlib.Path:
    return FIXTURES / f"werkbank_vorher_{name}_{profil or 'vorgabe'}.html"


def _fest(wert):
    """Jeder ISO-Zeitstempel wird FEST, ``sqlite3.Row`` wird ein Dict."""
    if isinstance(wert, sqlite3.Row):
        return {k: _fest(wert[k]) for k in wert.keys()}
    if isinstance(wert, dict):
        return {k: _fest(v) for k, v in wert.items()}
    if isinstance(wert, list):
        return [_fest(v) for v in wert]
    if isinstance(wert, tuple):
        return tuple(_fest(v) for v in wert)
    if isinstance(wert, str) and _ISO.match(wert):
        return FEST
    return wert


def _profil(monkeypatch, name: str | None) -> None:
    monkeypatch.delenv("IT_UX_ENTWURF", raising=False)
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


def seiten(tmp_path) -> dict[str, str]:
    """Die drei Ausgaben, die der Schalter ``[web] workbench_bearbeitbar``
    nicht beruehren darf: die Einzelseite mit Formularen, der Rumpf ohne
    Nonce (Leseansicht) und die vereinte Seite mit Chat."""
    pfad = str(tmp_path / "werkbank.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    echtes_token = baue_volle_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, echtes_token)
        chat = web_daten.web_chatzustand(lesend, echtes_token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    daten = _fest(daten)
    daten["web_token"] = TOKEN
    chat = _fest(chat)
    for nachricht in chat["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return {
        "gruppe": web.gruppe_html(daten, NONCE, TOKEN),
        "koerper": web.gruppe_koerper(daten, None, TOKEN),
        "vereint": web_vereint.seite(
            daten, chat, _fest(roadmapdaten), NONCE, TOKEN, "/theatersoap", 45000),
    }


@pytest.mark.dortmund  # Dortmund eingefroren (AGENTS.md, 04.10.2026): vergleicht gegen eine Dortmund-/Vorgabe-Fixture
@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_ohne_schalter_bleibt_die_werkbank_byte_gleich(tmp_path, monkeypatch, profil):
    _profil(monkeypatch, profil)
    erzeugt = seiten(tmp_path)
    for name in SEITEN:
        datei = _datei(name, profil)
        if SCHREIBEN:
            datei.write_text(erzeugt[name], encoding="utf-8")
        assert erzeugt[name] == datei.read_text(encoding="utf-8"), name


def test_die_vergleichsdateien_tragen_die_formulare():
    """Gegenprobe: eine leere oder schon umgebaute Vergleichsdatei bewiese
    nichts. Vorher stehen Formulare, Nonce und Speicher-Skript drin."""
    gruppe = _datei("gruppe", None).read_text(encoding="utf-8")
    vereint = _datei("vereint", None).read_text(encoding="utf-8")
    assert "<textarea" in gruppe
    assert 'id="nonce"' in gruppe
    assert web._BEARBEITEN_JS in vereint

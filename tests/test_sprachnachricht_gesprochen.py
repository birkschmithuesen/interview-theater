"""Padua Hotfix Befund 1 (02.10.2026): eine Sprachnachricht bleibt im
Gespraechs-Prompt als gesprochen erkennbar.

Live-Fall: auf "ich schicke dir eine Sprachnachricht, verstehst du mich"
antwortete der Bot "ich kann deine Sprachnachricht jetzt nicht
transkribieren" -- Whisper hatte laengst transkribiert, aber
``repo.aktualisiere_transkribierte_nachricht`` machte aus der Zeile
``typ='text'``, und das Modell sah einen getippten Beitrag.

Seitdem: ``nachricht.gesprochen = 1`` (additive Spalte), ``typ`` bleibt
``'text'`` -- alle Fenster laufen unveraendert --, und
``kontext.sprecherzeile`` markiert die Zeile im Gespraechs-Prompt.

Kein Netzzugriff: Telegram und STT sind Attrappen wie in
test_interview_ohne_knopf.py.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest

from interview_theater import aufnahme, db, einstellungen, kontext, repo, sprache, workshop

KURZ = "Ich schicke dir eine Sprachnachricht, verstehst du mich?"


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self._letzte_message_id = 9000

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._letzte_message_id += 1
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


def stt_attrappe(text: str) -> httpx.Client:
    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


def _sprachnachricht_ohne_modus(conn, einst, message_id=10, dauer=6):
    """Empfang ueber den echten Weg (Zeile typ='sprache', text=NULL), dann
    Transkription mit Fake-STT. Der Gespraechszug wird abgefangen und gibt
    die ausloesenden Nachrichten zurueck, wie ``ablauf`` sie sieht."""
    tg = TelegramAttrappe()
    nachricht = {
        "chat_id": 1, "chat_titel": "Testgruppe", "message_id": message_id,
        "absender": "Ada", "typ": "sprache", "text": None, "file_id": "F1",
        "dauer": dauer,
        "gesendet_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    # Wie bot.verarbeite_update: die Sprachzeile entsteht unterdrueckt, ohne Text.
    repo.merke_nachricht(
        conn, 1, message_id, "Ada", 0, "sprache", None, nachricht["gesendet_am"], 1,
    )
    zuege = []
    aid = aufnahme.empfange(conn, tg, einst, nachricht)
    aufnahme.verarbeite(
        conn, tg, None, einst, stt_attrappe(KURZ), aid,
        zug=lambda conn, tg, klm, e, chat_id, hinweis=None: zuege.append(
            repo.unbeantwortete(conn, chat_id)
        ),
    )
    return zuege


def test_kurze_sprachnachricht_ist_im_kontext_als_gesprochen_markiert(conn, einst):
    zuege = _sprachnachricht_ohne_modus(conn, einst)
    assert len(zuege) == 1, "eine kurze Sprachnachricht loest genau einen Zug aus"
    ausloeser = zuege[0]
    assert [n["text"] for n in ausloeser] == [KURZ]

    zeile = repo.hole_nachricht(conn, 1, 10)
    assert zeile["typ"] == "text", "typ bleibt 'text' -- keine Regression in den Fenstern"
    assert zeile["gesprochen"] == 1

    prompt = kontext.baue(conn, 1, ausloeser, einst)
    assert f"Ada (Sprachnachricht): {KURZ}" in prompt


def test_kurze_sprachnachricht_englisch_markiert(conn, einst, englisch):
    zuege = _sprachnachricht_ohne_modus(conn, einst)
    prompt = kontext.baue(conn, 1, zuege[0], einst)
    assert f"(voice message): {KURZ}" in prompt
    assert "Sprachnachricht)" not in prompt


def test_gesprochene_nachricht_laeuft_in_allen_fenstern_wie_bisher(conn, einst):
    _sprachnachricht_ohne_modus(conn, einst)
    for name in ("letzte_nachrichten", "unextrahierte", "unbeantwortete", "unjournalisierte"):
        texte = [n["text"] for n in getattr(repo, name)(conn, 1)]
        assert KURZ in texte, name


def test_getippte_nachricht_bleibt_unmarkiert(conn, einst):
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "Hallo", repo._jetzt())
    zeile = repo.hole_nachricht(conn, 1, 5)
    assert zeile["gesprochen"] == 0
    assert kontext.sprecherzeile(zeile, gesprochen_markieren=True) == "Ada: Hallo"


def test_erkenner_und_journal_sehen_die_markierung_nicht():
    """Die Few-Shot-Prompts von Erkenner und Journal sind gegen den Korpus
    gemessen; sie rufen ``sprecherzeile`` ohne ``gesprochen_markieren``."""
    n = {"ist_bot": 0, "absender": "Ada", "text": "ja", "typ": "text", "gesprochen": 1}
    assert kontext.sprecherzeile(n) == "Ada: ja"
    assert kontext.sprecherzeile(n, gesprochen_markieren=True) == "Ada (Sprachnachricht): ja"


def test_versteckte_lange_sprachnachricht_bleibt_versteckt_und_traegt_die_marke(conn, einst):
    """Die lange Sprachnachricht ohne Modus bleibt TYP_TRANSKRIPT (in keinem
    Fenster); wird sie per "Nein, war ein Beitrag" sichtbar, ist sie
    gesprochen markiert."""
    _sprachnachricht_ohne_modus(conn, einst, message_id=20, dauer=186)
    zeile = repo.hole_nachricht(conn, 1, 20)
    assert zeile["typ"] == repo.TYP_TRANSKRIPT
    assert KURZ not in [n["text"] for n in repo.letzte_nachrichten(conn, 1)]
    repo.zeige_transkript_nachricht(conn, 1, 20)
    zeile = repo.hole_nachricht(conn, 1, 20)
    assert zeile["typ"] == "text"
    assert kontext.sprecherzeile(zeile, gesprochen_markieren=True).startswith(
        "Ada (Sprachnachricht): "
    )


def test_alte_datenbank_bekommt_die_spalte_additiv(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.execute(
        "CREATE TABLE nachricht (chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, "
        "telegram_user INTEGER, absender TEXT, ist_bot INTEGER NOT NULL DEFAULT 0, "
        "typ TEXT NOT NULL, text TEXT, gesendet_am TEXT NOT NULL, "
        "unterdrueckt INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (chat_id, message_id))"
    )
    c.execute(
        "INSERT INTO nachricht (chat_id, message_id, typ, text, gesendet_am) "
        "VALUES (1, 1, 'text', 'alt', '2026-09-06T10:00:00+00:00')"
    )
    c.commit()
    db.initialisiere(c)
    zeile = c.execute("SELECT gesprochen, text FROM nachricht").fetchone()
    assert tuple(zeile) == (0, "alt")

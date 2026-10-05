"""Padua Modellwahl, Task 4 -- der abschliessende Nachweis, dass die Karte
"Opus ueberall ausser in Interviews, ohne US-Einwilligungsfrage" wirklich
wirkt: Phase 1 (Begriffsboard) und Phase 2 (``fragen_ki``) laufen unter dem
Padua-Profil ueber Claude, OHNE dass ``gruppe.szene_usa_bestaetigt_am`` je
gesetzt wurde -- waehrend Phase 3 (Interviews) unveraendert bei Kimi bleibt.

Siehe ``.superpowers/sdd/task-4-brief.md``. Kein echter Netzaufruf: ein
``klm``-Doppelgaenger mit ``httpx.MockTransport`` ersetzt den Claude-Proxy,
die Kimi-Seite (``klm.schema``) darf in keinem der drei Faelle je gerufen
werden -- das ist die ganze Beweislast dieser Datei."""

import json
import time

import httpx
import pytest

from interview_theater import begriffsboard, fragen_ki, modellwahl, repo, workshop

CHAT = 1

#: Dieselbe Form wie ``tests/test_begriffsboard_lauf.py::HEIMAT`` -- eigene
#: Kopie, kein Cross-Import (Vorgabe des Taskbriefs).
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1, "begruendung": "Oma.",
          "zitat": "wo meine Oma kocht", "doppelbedeutung": "", "status": "favorit"}

TEXT = "Wir reden ueber Heimat und Grenze. Heimat ist, wo meine Oma kocht."


@pytest.fixture
def padua(monkeypatch):
    """Wie ``tests/test_erkenner_teil2.py::padua`` / ``tests/test_modellwahl.py::padua``
    -- ``IT_WORKSHOP=padua-2026`` per ``monkeypatch``, Profil-Cache davor und
    danach vergessen."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture
def opus_e(einst):
    """Dieselbe Einstellungen-Attrappe wie ``tests/test_modellwahl.py::opus_e``
    -- nur mit erlaubtem Claude-Schalter (``IT_SZENE_ANBIETER=claude``)."""
    import dataclasses

    return dataclasses.replace(einst, szene_anbieter="claude")


@pytest.fixture
def opus_e_padua(opus_e, padua):
    """``opus_e`` (Betreiber erlaubt Claude) UNTER dem Padua-Profil
    (``modellwahl.einwilligung = false``): die Einwilligungsfrage ist hier
    komplett abgeschaltet."""
    return opus_e


def _segment(conn, message_id, text=TEXT, chat_id=CHAT):
    """Dasselbe Muster wie ``tests/test_begriffsboard_lauf.py::_segment``:
    eine fertige Diskussions-Aufnahme mit Transkript."""
    aid = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund="pause",
    )
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, "fertig")
    return aid


def _warte_bis(bedingung, timeout=5.0) -> None:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


class _KLMDoppelgaenger:
    """Ein ``klm``-Doppelgaenger: ``_klient`` haengt am ``httpx.MockTransport``
    (``modellwahl.aufruf_schema`` liest ``getattr(klm, "_klient", None)`` und
    nutzt ihn fuer den Claude-Proxy-Aufruf, OHNE echtes Netz); ``schema``
    zaehlt jeden Aufruf -- er muss am Ende 0 bleiben, die Kimi-Seite darf nie
    gerufen werden."""

    def __init__(self, handler):
        self.aufrufe = 0
        self._klient = httpx.Client(transport=httpx.MockTransport(handler))

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"antwort": "NIE GERUFEN -- Kimi"}


def _handler_fuer(payload: dict, gesehen: list):
    """Baut den ``httpx.MockTransport``-Handler: eine Anthropic-foermige
    Antwort, deren ``content[0]["text"]`` ``payload`` als JSON trägt, und
    zaehlt jeden Aufruf in ``gesehen``."""

    def handler(anfrage):
        gesehen.append(anfrage)
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        })

    return handler


class _TG:
    """Minimaler Telegram-Doppelgaenger, wie ``tests/test_fragen_ki.py::_TG``
    -- eigene Kopie, kein Cross-Import."""

    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append((chat_id, text))
        return 1


def _letzter_modus(conn, chat_id: int, art: str) -> str | None:
    zeile = conn.execute(
        "SELECT modus FROM aufruf WHERE chat_id = ? AND art = ? ORDER BY id DESC LIMIT 1",
        (chat_id, art),
    ).fetchone()
    return zeile["modus"] if zeile is not None else None


# ---------------------------------------------------------------------------
# Testfall 1 -- Phase 1 (Begriffsboard) ohne Einwilligung ueber Claude
# ---------------------------------------------------------------------------


def test_phase1_begriffsboard_laeuft_ohne_einwilligung_ueber_claude(
    conn, opus_e_padua,
):
    gesehen: list = []
    klm = _KLMDoppelgaenger(_handler_fuer({"board": [HEIMAT]}, gesehen))

    repo.setze_phase(conn, CHAT, 1)
    _segment(conn, 10)

    # Explizit NICHT aufgerufen: repo.setze_szene_usa(...) -- die Gruppe hat
    # nie zugestimmt, gruppe.szene_usa_bestaetigt_am bleibt NULL. Das ist der
    # Kern des Nachweises.

    assert begriffsboard.starte(conn, klm, opus_e_padua, CHAT) is True
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))

    assert len(gesehen) == 1, "der Claude-Proxy wurde nicht genau einmal gerufen"
    assert klm.aufrufe == 0, "die Kimi-Seite wurde beruehrt"
    assert _letzter_modus(conn, CHAT, "begriffsboard") == "C"
    assert repo.szene_usa_stand(conn, CHAT) == "offen"


# ---------------------------------------------------------------------------
# Testfall 2 -- Phase 2 (fragen_ki) ohne Einwilligung ueber Claude
# ---------------------------------------------------------------------------


def test_phase2_fragen_ki_laeuft_ohne_einwilligung_ueber_claude(
    conn, opus_e_padua,
):
    gesehen: list = []
    antwort = "Heimat: Frage eins.\nHeimat: Frage zwei.\nHeimat: Frage drei."
    klm = _KLMDoppelgaenger(_handler_fuer({"antwort": antwort}, gesehen))

    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Streit")
    # ``workshop.fragen_ab_aktiv()`` ist unter IT_WORKSHOP=padua-2026 bereits
    # True (workshop/padua-2026/profil.toml, [fragen_ab] aktiv = true) --
    # kein zusaetzlicher Monkeypatch noetig.

    # Explizit NICHT aufgerufen: repo.setze_szene_usa(...).

    tg = _TG()
    fragen_ki.starte(conn, tg, klm, opus_e_padua, CHAT)

    def _fertig() -> bool:
        stand = repo.hole_arbeitsstand(conn, CHAT)
        if stand is not None and stand["fragen_ki_vorschlag"]:
            return True
        vorfall = conn.execute(
            "SELECT 1 FROM vorfall WHERE chat_id = ? AND art = 'fragen_ki_fehler'",
            (CHAT,),
        ).fetchone()
        return vorfall is not None

    _warte_bis(_fertig, timeout=5.0)

    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand is not None and stand["fragen_ki_vorschlag"], (
        "der Lauf hat einen fragen_ki_fehler-Vorfall geschrieben statt eines "
        "Vorschlags -- siehe Vorfall-Tabelle fuer den Grund"
    )
    assert len(gesehen) == 1, "der Claude-Proxy wurde nicht genau einmal gerufen"
    assert klm.aufrufe == 0, "die Kimi-Seite wurde beruehrt"
    assert _letzter_modus(conn, CHAT, "fragen_ki_vorschlag") == "C"


# ---------------------------------------------------------------------------
# Testfall 3 -- Phase 3 (Interviews) bleibt Kimi
# ---------------------------------------------------------------------------


def test_phase3_interviews_bleiben_kimi_auch_padua_und_claude_erlaubt(
    conn, opus_e_padua,
):
    """Die bestehende, in Task 1+2 nicht veraenderte Garantie -- hier erneut
    gezeigt, ausdruecklich im Padua+Claude-erlaubt-Kontext, um zu belegen,
    dass Task 2 diese Invariante nicht gebrochen hat. Kein neuer Mechanismus
    noetig."""
    repo.setze_phase(conn, CHAT, 3)
    assert modellwahl.konversation_ueber_claude(opus_e_padua, conn, CHAT) is False

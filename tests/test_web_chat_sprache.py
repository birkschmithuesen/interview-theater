"""Task 4 (Kanban-Karte Buehne/PTT): deutsche Textreste auf der EN-Seite
entfernt -- Brainstorm, PTT, Pause/Beenden. Prueft am gerenderten HTML und am
eingebetteten JS, dass unter dem Padua-Profil keines der bekannten
deutschen Woerter mehr auftaucht, und dass es ohne Profil (Deutsch) weiter
dasteht -- sonst pruefte der erste Teil nichts Echtes.

``_sichtbar`` schneidet das eingebettete ``<style>``-Blatt und JS-Kommentare
(``//`` bis Zeilenende) heraus, bevor verglichen wird: beide tragen deutsche
Entwicklerkommentare (u. a. "Brainstorm mithören", "Rest verwerfen"), die --
wie im ganzen Projekt ueblich (``tests/test_sprache_texte.py``, ``BLEIBT_
DEUTSCH``: "CSS, nur Kommentare deutsch" / "JavaScript, nur Kommentare
deutsch") nie uebersetzt werden, weil sie kein Nutzertext sind. Ohne diesen
Schnitt wuerde der Test genau diese Kommentare treffen, nicht die
Knopfbeschriftungen, die diese Teilaufgabe tatsaechlich umstellt."""

import re

import pytest

from interview_theater import db, repo, sprache, web_chat, workshop

CHAT = 7_000_000_000_001

_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL)
_JS_KOMMENTAR = re.compile(r"//[^\n]*")


def _sichtbar(text: str) -> str:
    return _JS_KOMMENTAR.sub("", _STYLE.sub("", text))


def _enthaelt_wort(text: str, wort: str) -> bool:
    """Wortgrenzen-Treffer -- sonst traegt jedes camelCase-JS-Bezeichner wie
    ``interviewBeendenKnopf`` oder ``brainstormPauseKnopf`` (Code, kein
    Nutzertext, bleibt unveraendert, egal welche Sprache) ein falsches
    Positiv in sich."""
    return re.search(rf"\b{re.escape(wort)}\b", text) is not None


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token


def _zustand(pfad, token):
    from interview_theater import web_daten

    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.web_chatzustand(lesend, token)
    finally:
        lesend.close()


#: Woerter, die diese Teilaufgabe tatsaechlich umstellt -- muessen unter
#: Padua verschwinden UND (Gegenprobe) ohne Profil weiter deutsch dastehen.
_WOERTER_AKTUELL = (
    "Brainstorm mithören", "Tippen und sprechen", "Zur Gruppenseite",
    "Senden", "Rest verwerfen", "Rest als Interview nachreichen",
)

#: Regressionswache: der FRUEHERE deutsche PTT-Text (vor der vorherigen
#: Teilaufgabe dieser Karte, siehe Brief Tabellenzeile zu ``_TEXT_PTT``) --
#: er steht nirgends mehr im Quelltext und darf unter keinem Profil
#: wieder auftauchen. Keine Gegenprobe dafuer: er war nie "das aktuelle
#: Deutsch", den die Gegenprobe gegenpruefen koennte.
_WORT_REGRESSION = "Halten und sprechen"


def test_keine_bekannten_deutschen_textreste_auf_der_en_seite(datenbank, padua):
    pfad, token = datenbank
    zustand = _zustand(pfad, token)
    seite = _sichtbar(web_chat.chat_html(zustand, "n", token, "", 45000))
    skript = _sichtbar(web_chat._js())
    for wort in _WOERTER_AKTUELL + (_WORT_REGRESSION,):
        assert wort not in seite, wort
        assert wort not in skript, wort
    # "Weiter"/"Beenden" auf Wortgrenzen (nicht als blosses Substring):
    # beide JS-Bezeichner wie ``interviewBeendenKnopf``/``brainstormPause
    # Knopf`` tragen diese deutschen Woerter als camelCase-Bestandteil, egal
    # welche Sprache die Seite spricht -- ein Bezeichner wird nie uebersetzt.
    # "Pause" bewusst NICHT mitgeprueft (Abweichung vom urspruenglichen
    # Testvorschlag des Briefs, siehe Bericht) -- es ist ein Lehnwort, das im
    # Englischen unveraendert "Pause" bleibt
    # (_TEXT_INTERVIEW_PAUSE = "⏸ Pause" auf beiden Seiten der Tabelle), ein
    # Treffer waere also kein Hinweis auf einen deutschen Textrest.
    for wort in ("Weiter", "Beenden"):
        assert not _enthaelt_wort(seite, wort), wort
        assert not _enthaelt_wort(skript, wort), wort


def test_die_deutschen_textreste_bleiben_ohne_profil_deutsch(datenbank):
    pfad, token = datenbank
    zustand = _zustand(pfad, token)
    seite = _sichtbar(web_chat.chat_html(zustand, "n", token, "", 45000))
    skript = _sichtbar(web_chat._js())
    for wort in _WOERTER_AKTUELL:
        assert wort in seite or wort in skript, wort
    for wort in ("Pause", "Weiter", "Beenden"):
        assert _enthaelt_wort(seite, wort) or _enthaelt_wort(skript, wort), wort

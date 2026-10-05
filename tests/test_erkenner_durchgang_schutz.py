"""Padua Phase 2: der Erkenner und der laufende Einzeldurchgang
(Feedbackloop P1-2, Runde 3, Befunde H2, H3, M5).

Gemessen im Browserlauf ``2026-10-05-handy-giulia-p12`` (sim.db, chat
7000000000002):

* H2: die Gruppe schreibt "we can go to the interviews" (msg 186). Der
  Gespraechszug liest das als "eigene Fragen fertig" und legt "Question 1/27"
  hin (msg 187/188); sechs Sekunden spaeter setzt der Erkenner aus DERSELBEN
  Nachricht ``phase_setzen 3`` (msg 189 "Noted: We're now at 3 ·
  Interviews") -- der ganze Durchgang lief danach in Phase 3.
* H3: erkenner_lauf 24 "Removed: Questions" -- ``entfernen FRAGEN`` leerte
  mitten im Durchgang alle sieben eigenen Fragen (erkenner_lauf_schritt 28).
* M5: "So geht ein Interview: ..." deutsch in der englischen App
  (``erkenner._interviewmodus_texte`` las ``knoepfe.TEXT_ABLAUF`` am ``T``
  vorbei).

Kein Netz, kein Modell. Erfundenes Material."""

import pytest

from interview_theater import ablauf, erkenner, phasen, repo
from interview_theater.knoepfe import texte as knoepfe_texte

from test_undo_knopf import LLMAttrappe, TelegramAttrappe, padua  # noqa: F401

CHAT = 1

_SIEBEN = "\n".join([
    "Night shift: Can you tell me about one night you still remember?",
    "Home: Where do you sleep best, and why there?",
    "Border: When did someone last make you feel you were on the wrong side?",
    "Noise: Who listens to you when you talk at 3 in the morning?",
    "Home: What is the first thing you do when you come home?",
    "Waiting: What do you wait for most?",
    "Border: Where does Padua end for you?",
])


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _fragen(conn):
    return repo.hole_arbeitsstand(conn, CHAT)["fragen"]


def _im_durchgang(conn):
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Night shift, Home, Border, Noise, Waiting")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", _SIEBEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", _SIEBEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")


# --- H3 -----------------------------------------------------------------------


def test_entfernen_fragen_im_durchgang_laesst_die_fragen_stehen(conn, tg, einst, padua):  # noqa: F811
    """Repro lauf 24: msg 216 ("question 2 ... you lost the thread") ->
    ``entfernen FRAGEN`` -> "Noted: Removed: Questions", ``fragen`` NULL."""
    _im_durchgang(conn)
    repo.merke_nachricht(conn, CHAT, 216, "Gruppe", 0, "text",
                         "No, this is wrong - you lost the thread. Please: question 2",
                         repo._jetzt())
    vorher = len(tg.gesendet)

    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "entfernen", "wert": "FRAGEN"}]}),
                   tg, conn, einst, CHAT)

    assert _fragen(conn) == _SIEBEN
    assert not any("Removed" in t for t in tg.texte[vorher:])
    assert len(tg.gesendet) == vorher


def test_entfernen_fragen_ausserhalb_des_durchgangs_wie_bisher(conn, padua):  # noqa: F811
    repo.setze_arbeitsstand(conn, CHAT, "fragen", _SIEBEN)

    assert erkenner.entferne(conn, CHAT, "FRAGEN") is not None
    assert not _fragen(conn)


def test_befehl_entfernt_fragen_auch_im_durchgang(conn, padua):  # noqa: F811
    """Ein getippter Befehl ist ein ausdruecklicher Wunsch -- der Schutz gilt
    nur dem Erkenner, der dieselbe Nachricht nebenher liest."""
    _im_durchgang(conn)

    assert erkenner.entferne(conn, CHAT, "FRAGEN", quelle="befehl") is not None
    assert not _fragen(conn)


# --- M5 -----------------------------------------------------------------------


def test_ablauf_erklaerung_im_englischen_profil_englisch(conn, tg, einst, padua):  # noqa: F811
    repo.setze_phase(conn, CHAT, 3)
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "text", "then we record", repo._jetzt())

    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "interview_starten", "wert": ""}]}),
                   tg, conn, einst, CHAT)

    texte = [t for t in tg.texte if "interview works" in t or "So geht ein Interview" in t]
    assert texte == [knoepfe_texte.T.TEXT_ABLAUF]
    assert texte[0].startswith("This is how an interview works")


# --- H2 -----------------------------------------------------------------------


def _bereit_zum_vergleich(conn):
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Home, Noise")
    # S2 (B4): der Erkenner hatte die eigenen Fragen schon vorzeitig in
    # ``fragen`` gespeichert -- damit war Phase 3 erlaubt.
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Home: Where do you sleep best?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_ki_vorschlag",
                            "Home: KI question 1.\nNoise: KI question 2.")


def _zug(conn, tg, einst, monkeypatch, message_id, text, antwort):
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "text", text, repo._jetzt())
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: antwort)
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))


_FERTIG = ("Good change.\n\nOwn questions done. Next comes the side-by-side comparison.\n\n"
           "VORSCHLAG EIGENE FRAGEN:\nHome: Where do you sleep best?\n"
           "Noise: Who listens to you at 3 in the morning?")


def test_phasenwunsch_aus_der_nachricht_die_den_vergleich_startet_faellt_weg(
        conn, tg, einst, monkeypatch, padua):  # noqa: F811
    """Repro msg 186-189: der Zug startet den Vergleich, der Erkenner liest
    dieselbe Nachricht als ``phase_setzen 3``."""
    _bereit_zum_vergleich(conn)
    _zug(conn, tg, einst, monkeypatch, 186,
         "Then the list is finished for me and we can go to the interviews", _FERTIG)
    assert repo.hole_arbeitsstand(conn, CHAT)["fragen_aktuell"], "Durchgang laeuft"
    vorher = len(tg.gesendet)

    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "phase_setzen", "wert": "3"}]}),
                   tg, conn, einst, CHAT)

    assert phasen.aktuelle(conn, CHAT) == 2
    assert not any("We're now at" in t for t in tg.texte[vorher:]), tg.texte[vorher:]


def test_phasenwunsch_einer_spaeteren_nachricht_gilt(
        conn, tg, einst, monkeypatch, padua):  # noqa: F811
    """Die Phase setzt die Gruppe: sagt sie es in einer SPAETEREN Nachricht,
    wechselt die Phase."""
    _bereit_zum_vergleich(conn)
    _zug(conn, tg, einst, monkeypatch, 186,
         "Then the list is finished for me and we can go to the interviews", _FERTIG)
    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "phase_setzen", "wert": "3"}]}),
                   tg, conn, einst, CHAT)
    assert phasen.aktuelle(conn, CHAT) == 2

    _zug(conn, tg, einst, monkeypatch, 900, "let's go to phase 3", "Sure.")
    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "phase_setzen", "wert": "3"}]}),
                   tg, conn, einst, CHAT)

    assert phasen.aktuelle(conn, CHAT) == 3


def test_ohne_vergleichsstart_gilt_der_phasenwunsch_derselben_nachricht(
        conn, tg, einst, monkeypatch, padua):  # noqa: F811
    """Gegenprobe: startet der Zug keinen Vergleich, wechselt die Phase wie
    bisher."""
    _bereit_zum_vergleich(conn)
    _zug(conn, tg, einst, monkeypatch, 186, "we can go to the interviews", "Sure.")

    erkenner.laufe(LLMAttrappe({"aenderungen": [{"art": "phase_setzen", "wert": "3"}]}),
                   tg, conn, einst, CHAT)

    assert phasen.aktuelle(conn, CHAT) == 3

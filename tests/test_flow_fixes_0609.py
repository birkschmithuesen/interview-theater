"""Die Flow-Fixes vom 06.09.2026 nachmittags.

Jeder Test haengt an einer Stelle, die in einem der drei Simulationslaeufe
vom selben Tag gemessen wurde (`simulation/laeufe/2026-09-06-*.md`) -- kein
Test hier ist geraten.
"""

from __future__ import annotations

import pytest

from interview_theater import (
    bot, db, einstellungen, erkenner, phasen, phasentexte, repo, workshop,
)

from simulation.attrappe import TelegramAttrappe

CHAT = -4242


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "testbot", "Testgruppe")
    yield verbindung
    verbindung.close()


@pytest.fixture
def einst(tmp_path, monkeypatch):
    monkeypatch.setenv("IT_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("IT_BOT_TOKEN", "x")
    monkeypatch.setenv("IT_BOT_NAME", "testbot")
    monkeypatch.setenv("IT_LLM_URL", "http://x/chat/completions")
    monkeypatch.setenv("IT_LLM_TOKEN", "x")
    monkeypatch.setenv("IT_LLM_KEY", "x")
    monkeypatch.setenv("IT_LLM_MODELL", "kimi")
    monkeypatch.setenv("IT_STT_PRODUKT", "PRODUKT-ID")
    monkeypatch.setenv("IT_CHAT_ID", str(CHAT))
    monkeypatch.delenv("IT_WEB_URL", raising=False)
    return einstellungen.laden()


# --- Fix 1: die Begruessung fordert nicht, was gerade kam -------------------


def test_begruessung_fordert_die_liste_nicht_wenn_die_gruppe_schon_schrieb(
    conn, einst, monkeypatch
):
    """Gemessen in beiden tag1-Laeufen: die Gruppe schickt als erste
    Nachricht ihre Begriffe, der Bot antwortet mit 'Schickt mir die Liste'."""
    tg = TelegramAttrappe()
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe A", 0, "text",
                         "unsere begriffe: trauma, macht", repo._jetzt())

    bot.erstkontakt(conn, tg, einst, CHAT)

    text = tg.gesendet[0]["text"]
    assert "Schickt mir die Liste" not in text
    assert "Eure Begriffe habe ich schon" in text


def test_ohne_gruppennachricht_bleibt_die_alte_begruessung(conn, einst):
    tg = TelegramAttrappe()

    bot.erstkontakt(conn, tg, einst, CHAT)

    assert "Als Erstes schickt ihr mir eure Begriffe" in tg.gesendet[0]["text"]


def test_transkript_echo_zaehlt_nicht_als_gruppennachricht(conn):
    """Ein Transkript-Echo ist Interviewinhalt, kein Beitrag der Gruppe."""
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "transkript",
                         "und dann bin ich gegangen", repo._jetzt())

    assert not repo.hat_gruppennachricht(conn, CHAT)


def test_start_befehl_zaehlt_nicht_als_gruppennachricht(conn, einst):
    """Abnahme P1-2, 04.10.2026 (echter Browserlauf): der versteckte
    ``/start``-Eingang beim ersten Seitenaufruf einer frischen Web-Gruppe
    wurde vor diesem Fix als Gruppennachricht gezaehlt -- ``bot.erstkontakt``
    waehlte dann faelschlich "Eure Begriffe habe ich schon" statt "Schickt
    mir eure Begriffe", und das Modell erfand im naechsten Zug eine
    Begriffsliste."""
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "text", "/start", repo._jetzt())

    assert not repo.hat_gruppennachricht(conn, CHAT)

    tg = TelegramAttrappe()
    bot.erstkontakt(conn, tg, einst, CHAT)
    assert "Als Erstes schickt ihr mir eure Begriffe" in tg.gesendet[0]["text"]


def test_erstkontakt_mit_diskussion_aktiv_erzaehlt_kein_plenum(
    conn, einst, monkeypatch
):
    """Echter Browserlauf (handy/giulia, 04.10.2026): mit aktivem
    Hintergrund-Zuhoeren (``workshop.diskussion_aktiv``) erzaehlte
    ``bot.erstkontakt`` weiter die alte Dortmunder Abgabe ("aus dem Plenum",
    "an der Wand") -- die Gruppe erfand daraufhin eine zwanzig Woerter lange
    Wandliste, die mit ihrer echten Diskussion nichts zu tun hatte. Diese
    Begruessung ist der Rueckfallweg (``kontext.ERSTKONTAKT_DISKUSSION``
    traegt den Normalfall), muss aber trotzdem zum aktiven Profil passen."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)

    tg = TelegramAttrappe()
    bot.erstkontakt(conn, tg, einst, CHAT)

    text = tg.gesendet[0]["text"]
    assert "Plenum" not in text and "Wand" not in text
    assert "Handy" in text and "Diskussion fertig" in text


# --- Fix 2: die Form wird vorgeschlagen, nicht gesetzt ----------------------


def test_erkenner_schreibt_die_form_als_vorschlag(conn, einst):
    """Gemessen im Lauf tag1-gruppe2: vier Szenen bekamen ihre Form ueber
    ``szene_planen`` gesetzt, keine einzige wurde per Knopf bestaetigt."""
    erkenner.wende_an(conn, einst, CHAT, [{
        "art": "szene_planen",
        "wert": "Szene 1 | form: Monolog | ort: Schulhof",
    }])

    zeile = repo.hole_szenen(conn, CHAT)[0]
    assert zeile["form"] is None, "form gehoert dem Bestaetigungsknopf"
    assert zeile["form_vorschlag"] == "Monolog"


def test_ein_zweiter_planungssatz_aendert_nur_den_vorschlag(conn, einst):
    for form in ("Dialog", "Chor"):
        erkenner.wende_an(conn, einst, CHAT, [{
            "art": "szene_planen", "wert": f"Szene 1 | form: {form}",
        }])

    zeile = repo.hole_szenen(conn, CHAT)[0]
    assert zeile["form"] is None
    assert zeile["form_vorschlag"] == "Chor"


# --- Fix 3: die letzte Phase behauptet nichts ueber Szenen, die nicht stehen ---------


def test_die_letzte_phase_behauptet_nicht_dass_alle_szenen_stehen(conn):
    """Gemessen im Lauf tag1-gruppe2: der Bot sprang in die letzte Phase und sagte
    'Alle Szenen stehen', waehrend keine geschrieben war."""
    repo.stelle_szene_sicher(conn, CHAT, 1)

    text = phasentexte.eintritt(conn, CHAT, phasen.LETZTE)

    assert "Alle Szenen stehen" not in text
    assert "noch ungeschrieben" in text


def test_die_letzte_phase_sagt_es_wenn_wirklich_alle_stehen(conn):
    szene_id = repo.stelle_szene_sicher(conn, CHAT, 1)
    repo.aktualisiere_szene(conn, szene_id, "Szene 1", None, "MIRA: Hallo.")

    text = phasentexte.eintritt(conn, CHAT, phasen.LETZTE)

    assert "Alle Szenen stehen" in text


def test_ohne_jede_szene_wird_nichts_behauptet(conn):
    """``all()`` ueber eine leere Liste ist True -- ohne die
    Zusatzbedingung stuende 'Alle Szenen stehen' bei null Szenen."""
    text = phasentexte.eintritt(conn, CHAT, phasen.LETZTE)

    assert "Alle Szenen stehen" not in text


# --- Fix 5: die Fragenwahl lief ueber Nummern -- seit 02.10.2026 ersetzt --
#
# Siehe tests/test_phase2_einzeln.py fuer die heutige Fragenauswahl (Vorschlag
# mit Sensibilitaetspruefung im selben Zug, Ueberblick mit Richtungsfrage,
# Frage fuer Frage).

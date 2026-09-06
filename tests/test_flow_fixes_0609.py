"""Die Flow-Fixes vom 06.09.2026 nachmittags.

Jeder Test haengt an einer Stelle, die in einem der drei Simulationslaeufe
vom selben Tag gemessen wurde (`simulation/laeufe/2026-09-06-*.md`) -- kein
Test hier ist geraten.
"""

from __future__ import annotations

import pytest

from interview_theater import (
    bot, db, einstellungen, erkenner, phasen, phasentexte, repo,
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
    monkeypatch.setenv("IT_LLM_URL", "http://x/chat/completions")
    monkeypatch.setenv("IT_LLM_TOKEN", "x")
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


# --- Fix 5: die Fragenwahl laeuft ueber Nummern, nicht ueber Knoepfe ------


def test_die_wahl_per_nummer_nimmt_die_alten_leisten_ab(conn, einst):
    """Gemessen im Regie-Lauf: vier Beschwerden ueber haengende Knoepfe,
    einmal die falsche Behauptung, sie seien weg. Seit dem 06.09.2026 (10:05)
    gibt es die zehn Toggle-Knoepfe gar nicht mehr -- gewaehlt wird per
    Nummer --, aber die Leiste unter dem Vorschlag muss trotzdem weg."""
    from interview_theater import knoepfe

    from interview_theater import phasen

    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 2, "test")
    fragen = "\n".join(f"Frage {n}" for n in range(1, 11))
    knoepfe.biete_fragenauswahl(conn, tg, CHAT, fragen)

    assert knoepfe.nimm_fragennummern(conn, tg, None, einst, CHAT, "1, 2 und 3")

    assert repo.hole_arbeitsstand(conn, CHAT)["fragen"] == "Frage 1\nFrage 2\nFrage 3"
    for art in (knoepfe.ART_FRAGE_WAHL, knoepfe.ART_FRAGEN_ANDERE,
                knoepfe.ART_FRAGEN_EIGENE):
        assert repo.offene_knoepfe(conn, CHAT, art) == [], art
    assert tg.knoepfe_entfernt, "und ihre Tastatur ist abgenommen"


def test_der_vorschlag_zeigt_alle_zehn_fragen_ausgeschrieben(conn):
    """Kein Menue mehr (Birk, 10:05: "sobald ich auf eine Frage klicke,
    verschwindet das Menue"). Die Fragen stehen im Text -- ganz, nicht auf
    Knopflaenge gekuerzt: eine Frage, die eine Sechzehnjaehrige einer fremden
    Person stellen soll, muss sie vorher lesen koennen."""
    from interview_theater import knoepfe

    tg = TelegramAttrappe()
    fragen = "\n".join(
        f"Frage {n}, und zwar eine ziemlich lange, damit das Kuerzen auffiele?"
        for n in range(1, 11)
    )
    knoepfe.biete_fragenauswahl(conn, tg, CHAT, fragen, text="Hier sind zehn.")

    text = tg.knoepfe[-1]["text"]
    leiste = tg.knoepfe[-1]["knoepfe"]
    for n in range(1, 11):
        assert f"{n}. Frage {n}, und zwar eine ziemlich lange" in text, n
    assert "…" not in text, "nichts gekuerzt"
    assert [b for b, _ in leiste] == ["Eigene Idee", "Andere 10"]

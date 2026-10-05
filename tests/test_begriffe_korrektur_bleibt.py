"""Padua Phase 1: nach einer Korrektur bleibt die Gruppe in Phase 1 (Birk
05.10.2026 ~10:50, Brief "p1-bleiben").

Live seit dem Morgen: nach "Discussion done" speichert das Board die Top 5
und fragt "These are your five terms – saved. Shall we move on?" mit
[Yes, on to the questions] · [Change something] · [Undo]. Korrigierte die
Gruppe danach im Chat, sprang das Auto-Speichern der Phase 1 SOFORT in
Phase 2 (``knoepfe.basis._autospeichere`` -> ``uebergang_nach_speichern``).

Birks Entscheidung: eine gespeicherte Begriffs-Korrektur wechselt nie die
Phase. Nach JEDER Korrektur (beliebig oft) kommt proaktiv die kurze Frage
mit der aktualisierten Liste und denselben zwei Knoepfen (+ Undo der
Korrektur). Weiter geht es nur, wenn die Gruppe es ausdruecklich will:
Knopf "Yes, on to the questions" oder Freitext in diese Richtung. Das gilt
fuer alle drei Speicherwege der Phase 1 -- Vorschlagsblock im
Gespraechszug, Erkenner (``begriffe_setzen``) und "Take these".

Kein Netz, kein Modell: Telegram ist eine Attrappe, der Erkenner liefert
vorbereitete Antworten. Erfundenes Material."""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo
from interview_theater.knoepfe import basis, texte

from test_undo_knopf import LLMAttrappe, TelegramAttrappe, _druck, padua  # noqa: F401

CHAT = 1
BOARD = ["Home", "Border", "Courage", "School"]

AKTUALISIERT = "Updated – saved:\n\n{liste}\n\nMove on?"
KNOEPFE = ["Yes, on to the questions", "Change something", "Undo"]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def nach_dem_board(conn, tg, einst, padua):  # noqa: F811
    """Der Stand direkt nach "Discussion done": das Board hat die Top 5 in
    ``begriffe`` gespeichert, die Abschlussnachricht steht da, die Gruppe
    hat "Change something" gedrueckt."""
    wert = ", ".join(BOARD)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", wert)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe_board_wert", wert)
    basis.biete_board_gespeichert(conn, tg, CHAT, BOARD, None)
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten(tg, "Change something")))
    assert tg.texte[-1] == knoepfe.T._TEXT_BOARD_WAS_AENDERN
    return tg


def _daten(tg, beschriftung):
    for _, _, leiste, _ in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r} in {tg.knoepfe!r}")


def _liste(*begriffe):
    return "\n".join(f"{nr}. {b}" for nr, b in enumerate(begriffe, 1))


def _begriffe(conn):
    return repo.hole_arbeitsstand(conn, CHAT)["begriffe"]


def _korrigiere_im_chat(conn, tg, einst, wert):
    """Der Gespraechszug nach der Korrektur: das Modell gibt die ganze,
    korrigierte Liste als Vorschlagsblock aus (Phasenprompt 1)."""
    knoepfe.sende_mit_speicherleiste(
        conn, tg, CHAT, f"Done.\n\nVORSCHLAG BEGRIFFE:\n{wert}", e=einst,
    )


def _erkenner(conn, tg, einst, aenderungen, text, message_id=1):
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "text", text, repo._jetzt())
    erkenner.laufe(LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, CHAT)


def _alle_beschriftungen(tg):
    return [b for _, _, leiste, _ in tg.knoepfe for b, _ in leiste]


# --- Korrektur im Chat (Vorschlagsblock im Gespraechszug) -------------------


def test_korrektur_im_chat_bleibt_in_phase_1_und_fragt_mit_neuer_liste(
        conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    assert phasen.aktuelle(conn, CHAT) == 1
    assert _begriffe(conn) == "Home, Border, Fear, School"
    # EINE Nachricht: der Satz des Modells, darunter die Frage -- die Liste
    # steht nur einmal da (nummeriert), der Block nicht noch als Fliesstext.
    _, text, leiste, _ = tg.knoepfe[-1]
    assert text == "Done.\n\n" + AKTUALISIERT.format(
        liste=_liste("Home", "Border", "Fear", "School"))
    assert tg.texte[-1] == text
    assert [b for b, _ in leiste] == KNOEPFE
    arten = [repo.hole_knopf(conn, int(d[2:]))["art"] for _, d in leiste]
    assert arten == [texte.ART_PHASE, texte.ART_BOARD_AENDERN, texte.ART_UNDO]
    # Kein zweites, allgemeines Phasenangebot und keine 📌-Zeile daneben.
    assert not any(b.startswith("Continue to") for b in _alle_beschriftungen(tg))
    assert not any("📌" in t for t in tg.texte)


def test_zweite_korrektur_fragt_wieder_und_nimmt_die_alte_leiste_ab(
        conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")
    erste = tg.knoepfe[-1]
    knoepfe.behandle(conn, tg, None, einst,
                     _druck(_daten(tg, "Change something"), message_id=erste[3]))
    _korrigiere_im_chat(conn, tg, einst, "Fear, Home, Border, School, Train")

    assert phasen.aktuelle(conn, CHAT) == 1
    assert _begriffe(conn) == "Fear, Home, Border, School, Train"
    _, text, leiste, _ = tg.knoepfe[-1]
    assert text == "Done.\n\n" + AKTUALISIERT.format(
        liste=_liste("Fear", "Home", "Border", "School", "Train"))
    assert [b for b, _ in leiste] == KNOEPFE
    # Nur EINE Leiste ist bedienbar: die erste Frage behaelt allein ihr Undo.
    reduziert = [a for a in tg.aktualisiert if a[1] == erste[3]]
    assert reduziert and [b for b, _ in reduziert[-1][2]] == ["Undo"]


def test_korrektur_ohne_change_something_bleibt_ebenfalls(conn, tg, einst, padua):  # noqa: F811
    """Die Gruppe hat selbst Begriffe gesetzt (kein Board): gleiches Verhalten."""
    _korrigiere_im_chat(conn, tg, einst, "Harbour, Night")

    assert phasen.aktuelle(conn, CHAT) == 1
    _, text, leiste, _ = tg.knoepfe[-1]
    assert text == "Done.\n\n" + AKTUALISIERT.format(liste=_liste("Harbour", "Night"))
    assert [b for b, _ in leiste] == KNOEPFE


def test_derselbe_block_nochmal_schickt_keine_zweite_frage(conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")
    vorher, anzahl_leisten = len(tg.gesendet), len(tg.knoepfe)

    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    assert tg.texte[vorher:] == ["Done.\n\nHome, Border, Fear, School"]
    assert len(tg.knoepfe) == anzahl_leisten
    assert phasen.aktuelle(conn, CHAT) == 1


def test_undo_der_korrektur_holt_die_board_liste_zurueck(conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten(tg, "Undo"), message_id=900))

    assert _begriffe(conn) == ", ".join(BOARD)
    assert phasen.aktuelle(conn, CHAT) == 1


# --- weiter nur auf ausdruecklichen Wunsch ---------------------------------


def test_yes_on_to_the_questions_nach_korrektur_geht_in_phase_2(conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    knoepfe.behandle(conn, tg, None, einst,
                     _druck(_daten(tg, "Yes, on to the questions"), message_id=900))

    assert phasen.aktuelle(conn, CHAT) == 2
    assert _begriffe(conn) == "Home, Border, Fear, School"


def test_freitext_lets_move_on_geht_in_phase_2(conn, einst, nach_dem_board):
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    _erkenner(conn, tg, einst, [{"art": "phase_setzen", "wert": "2"}], "let's move on")

    assert phasen.aktuelle(conn, CHAT) == 2


def test_freitext_ohne_phasennummer_geht_aus_phase_1_ebenfalls_weiter(
        conn, einst, nach_dem_board):
    """Liest der Erkenner "let's move on" als ``phase_setzen`` ohne wirksame
    Nummer ("next", oder die jetzige 1), gab es bisher nur das Angebot
    erneut. In Phase 1 ist das Ziel eindeutig (die Fragen) und die Gruppe hat
    die Frage schon vor sich -- der Wunsch IST das Weiter."""
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")

    _erkenner(conn, tg, einst, [{"art": "phase_setzen", "wert": "next"}], "let's move on")

    assert phasen.aktuelle(conn, CHAT) == 2


def test_freitext_weiter_ohne_begriffe_bleibt_in_phase_1(conn, tg, einst, padua):  # noqa: F811
    """Gegenprobe: ohne gespeicherte Begriffe gibt es kein Weiter."""
    _erkenner(conn, tg, einst, [{"art": "phase_setzen", "wert": "next"}], "let's move on")

    assert phasen.aktuelle(conn, CHAT) == 1


# --- die anderen zwei Speicherwege der Phase 1 -----------------------------


def test_erkenner_begriffe_setzen_bleibt_und_fragt(conn, einst, nach_dem_board):
    tg = nach_dem_board
    vorher = len(tg.gesendet)

    _erkenner(conn, tg, einst,
              [{"art": "begriffe_setzen", "wert": "Home, Fear, School"}],
              "replace border and courage with fear")

    assert phasen.aktuelle(conn, CHAT) == 1
    assert _begriffe(conn) == "Home, Fear, School"
    assert len(tg.gesendet) - vorher == 1, tg.texte[vorher:]
    _, text, leiste, _ = tg.knoepfe[-1]
    assert text == AKTUALISIERT.format(liste=_liste("Home", "Fear", "School"))
    assert [b for b, _ in leiste] == KNOEPFE
    assert not any(b.startswith("Continue to") for b in _alle_beschriftungen(tg))


def test_erkenner_nach_dem_gespraechszug_schickt_nichts_doppelt(conn, einst, nach_dem_board):
    """Gespraechszug und Erkenner laufen auf derselben Nachricht: hat der
    Vorschlagsblock schon gespeichert, findet der Erkenner denselben Wert vor
    -- keine zweite Frage, kein allgemeines "Continue to phase 2"."""
    tg = nach_dem_board
    _korrigiere_im_chat(conn, tg, einst, "Home, Border, Fear, School")
    vorher = len(tg.gesendet)

    _erkenner(conn, tg, einst,
              [{"art": "begriffe_setzen", "wert": "Home, Border, Fear, School"}],
              "courage should be fear")

    assert tg.texte[vorher:] == []
    assert phasen.aktuelle(conn, CHAT) == 1


def test_take_these_bleibt_und_fragt(conn, tg, einst, padua):  # noqa: F811
    """"Take these" speichert die Top 5 des Boards (hier ins leere Feld, etwa
    nach einem Undo) -- auch das ist kein Wunsch weiterzugehen. Ein schon
    gesetzter Wert der Gruppe bleibt wie bisher stehen (``nur_bestaetigen``,
    ``knoepfe.wirkung._wirkung_board_uebernehmen``)."""
    basis.biete_begriffsvorschlag(conn, tg, CHAT, BOARD, BOARD)

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten(tg, "Take these")))

    assert phasen.aktuelle(conn, CHAT) == 1
    assert _begriffe(conn) == ", ".join(BOARD)
    _, text, leiste, _ = tg.knoepfe[-1]
    assert text == AKTUALISIERT.format(liste=_liste(*BOARD))
    assert [b for b, _ in leiste] == KNOEPFE


# --- Gegenproben: andere Phasen, anderes Profil -----------------------------


def test_ohne_padua_bleibt_der_ja_nein_weg(conn, tg, einst):
    """Vorgabeprofil (wie Dortmund): kein Autosave, also auch keine Frage --
    die Ja/Nein-Leiste wie bisher."""
    _korrigiere_im_chat(conn, tg, einst, "Heimat, Arbeit")

    assert not (repo.hole_arbeitsstand(conn, CHAT) or {"begriffe": None})["begriffe"]
    assert _alle_beschriftungen(tg) == ["Ja, speichern", "Nein, nochmal aendern"]


def test_deutscher_wortlaut_hat_dieselben_platzhalter():
    from interview_theater.knoepfe import texte as de

    assert "{liste}" in de._TEXT_BOARD_AKTUALISIERT

"""Szenenauftraege wirken nur in den Szenenphasen (Feedbackloop P1-2, Runde 4,
Befund H4).

Gemessen im Browserlauf ``2026-10-05-handy-giulia-p12`` (sim.db, Padua,
Phase 2 mitten im Einzeldurchgang der Fragen): die Gruppe schreibt "write me
the opening and the closing now" (msg 334) -- gemeint sind Eroeffnung und
Abschluss des INTERVIEWS. Der Erkenner liest ``szene_schreiben``,
``szene.starte`` findet die Pflichtfelder leer und schickt den Sperrtext "For
Scene 1 we still need: Place, Who, ... (phase 4)." (msg 335). Die naechste
Nachricht der Gruppe ("No, the scene can wait ... just write them", msg 337)
liest der Erkenner WIEDER als ``szene_schreiben`` -> derselbe Sperrtext ein
zweites Mal (msg 339). Zweimal, weil es zwei Erkennerlaeufe auf zwei
Nachrichten waren -- nicht eine doppelte Zustellung.

Die Regel jetzt: ``szene_schreiben`` und ``szene_kuerzen`` gelten erst ab der
Phase, in der es Szenen gibt (Setting/Frame, Phase 4, in beiden Profilen);
davor fallen sie still weg -- keine Meldung, kein Lauf.

Kein Netz, kein Modell. Erfundenes Material."""

import pytest

from interview_theater import erkenner, phasen, repo

from test_undo_knopf import LLMAttrappe, TelegramAttrappe, padua  # noqa: F401

CHAT = 1


def _nachricht(conn, message_id, text):
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "text", text, repo._jetzt())


def _laufe(conn, tg, einst, aenderungen):
    erkenner.laufe(LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, CHAT)


@pytest.mark.parametrize("phase", [1, 2, 3])
def test_szene_schreiben_vor_den_szenenphasen_still(conn, einst, padua, phase,  # noqa: F811
                                                     monkeypatch):
    from interview_theater import szene

    monkeypatch.setattr(szene, "starte",
                        lambda *a: pytest.fail("kein Szenenlauf vor Phase 4"))
    phasen.setze(conn, CHAT, phase, "test")
    tg = TelegramAttrappe()
    _nachricht(conn, 334, "write me the opening and the closing now")

    _laufe(conn, tg, einst, [{"art": "szene_schreiben", "wert": "opening and closing"}])

    assert tg.texte == []


def test_repro_msg_334_337_kein_sperrtext_auch_nicht_zweimal(conn, einst, padua):  # noqa: F811
    """Ohne Attrappe fuer ``szene.starte``: in Phase 2 fehlen die
    Pflichtfelder, der echte Weg schickte den Sperrtext -- zweimal."""
    phasen.setze(conn, CHAT, 2, "test")
    tg = TelegramAttrappe()

    _nachricht(conn, 334, "please don't push it to later again: write me the "
                          "opening and the closing now")
    _laufe(conn, tg, einst, [
        {"art": "szene_schreiben", "wert": "opening and closing"},
        {"art": "festlegung_setzen",
         "wert": "stil: ask for the city or the neighbourhood, not the street"},
    ])
    _nachricht(conn, 337, "No, the scene can wait. I don't need Scene 1, I need "
                          "the words. Please just write them")
    _laufe(conn, tg, einst, [{"art": "szene_schreiben", "wert": "opening and closing"}])

    assert not any("Scene 1" in t for t in tg.texte), tg.texte
    # Die Festlegung aus derselben Nachricht wird weiter notiert (msg 336).
    assert len(tg.texte) == 1, tg.texte
    assert "city or the neighbourhood" in tg.texte[0]
    assert phasen.aktuelle(conn, CHAT) == 2


def test_szene_kuerzen_vor_den_szenenphasen_still(conn, einst, padua, monkeypatch):  # noqa: F811
    from interview_theater import kuerzung

    monkeypatch.setattr(kuerzung, "starte",
                        lambda *a: pytest.fail("keine Kuerzung vor Phase 4"))
    phasen.setze(conn, CHAT, 2, "test")
    tg = TelegramAttrappe()
    _nachricht(conn, 50, "make it shorter")

    _laufe(conn, tg, einst, [{"art": "szene_kuerzen", "wert": ""}])

    assert tg.texte == []


@pytest.mark.parametrize("phase", [4, 5, 6, 7])
def test_szene_schreiben_in_den_szenenphasen_wie_bisher(conn, einst, padua, phase,  # noqa: F811
                                                        monkeypatch):
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(szene, "starte",
                        lambda conn, tg, klm, e, chat_id, auftrag: gesehen.append(auftrag))
    phasen.setze(conn, CHAT, phase, "test")
    _nachricht(conn, 50, "write scene 1")

    _laufe(conn, TelegramAttrappe(), einst,
           [{"art": "szene_schreiben", "wert": "Scene 1: at the station"}])

    assert gesehen == ["Scene 1: at the station"]


def test_szene_kuerzen_in_einer_szenenphase_wie_bisher(conn, einst, padua, monkeypatch):  # noqa: F811
    from interview_theater import kuerzung

    gesehen = []
    monkeypatch.setattr(kuerzung, "starte",
                        lambda conn, tg, klm, e, chat_id, nummer: gesehen.append(nummer))
    phasen.setze(conn, CHAT, 4, "test")
    _nachricht(conn, 50, "make scene 2 shorter")

    _laufe(conn, TelegramAttrappe(), einst, [{"art": "szene_kuerzen", "wert": "2"}])

    assert gesehen == [2]


def test_vorgabeprofil_gleiche_szenenphasen(conn):
    """Geteilter Code: das Vorgabe-/Dortmund-Profil hat dieselbe Nummerierung
    -- Phase 1-3 vor den Szenen, ab 4 Szenen."""
    phasen.setze(conn, CHAT, 2, "test")
    assert not erkenner._ist_phasenpassend(conn, CHAT, "szene_schreiben")
    phasen.setze(conn, CHAT, 4, "test")
    assert erkenner._ist_phasenpassend(conn, CHAT, "szene_schreiben")
    assert erkenner._ist_phasenpassend(conn, CHAT, "szene_kuerzen")
    phasen.setze(conn, CHAT, phasen.LETZTE, "test")
    assert erkenner._ist_phasenpassend(conn, CHAT, "szene_schreiben")

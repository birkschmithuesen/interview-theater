"""Padua, Phase-5-Gate (07.10.2026, Birk 08:55): vor jedem Sprung auf Phase 5
(Prose Draft) zeigt der Bot einmal die ganze Werkbank zur Bestaetigung,
solange das Profil ``p5_check.aktiv`` setzt (``workshop/padua-2026/profil.toml``)
-- falsche Eintraege praegen alles, was danach kommt (Prosa, Dramaturgie,
Textbuch), und muessen vorher korrigiert werden koennen.

Vier Wege setzen die Phase: ``befehle.wechsle_phase`` (``/phase``,
``/phaseklick``), der Knopf "Weiter zu Phase N"
(``knoepfe.wirkung._wirkung_phase``), "Ja, speichern"
(``knoepfe.stationen.uebergang_nach_speichern``) und der Absichtserkenner
(``erkenner._wende_phase_an`` ueber ``erkenner._ohne_phase_5_ohne_p5_check``)
-- alle vier laufen durch denselben EINEN Check, ``befehle.p5_gate``.

Ohne den Profilschalter (Dortmund, Vorgabe false) bleibt jeder
Phasenwechsel unveraendert -- ``test_dortmund_ohne_schalter_bleibt_unveraendert``.
"""

import pytest

from interview_theater import web, befehle, erkenner, knoepfe, kontext, phasen, repo, workshop
from interview_theater.knoepfe import stationen, texte

from tests.test_erkenner import LLMAttrappe, TelegramAttrappe as ErkennerTg, _nachricht
from tests.test_knoepfe import TelegramAttrappe, _druck

CHAT = 1


@pytest.fixture(autouse=True)
def p5_check_an(monkeypatch):
    """Alle Tests dieser Datei laufen mit aktivem Profilschalter -- wie unter
    Padua. Die Gegenprobe (Dortmund, Schalter aus) hebt ihn in ihrem eigenen
    Test ausdruecklich wieder auf."""
    monkeypatch.setattr(workshop, "p5_check_aktiv", lambda *a, **kw: True)


def _bereit(conn, chat_id: int = CHAT) -> None:
    """Materiallage, die Phase 5 hergibt (``phasen.voraussetzungen``)."""
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A market square in Padua, today")
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte", "Two families fall out and reconcile")
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", "3")
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, chat_id, "Mira", "the elder daughter")


def _bestaetigt(conn, chat_id: int = CHAT) -> bool:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    return bool(stand and (stand["p5_check_bestaetigt_am"] or "").strip())


# --- Die Werkbank-Uebersicht, deterministisch aus der Datenbank -----------


def test_uebersicht_zeigt_rahmen_figuren_geschichte_szenen_und_festlegungen(conn):
    _bereit(conn)
    szene_id = repo.stelle_szene_sicher(conn, CHAT, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Arrival")
    repo.schreibe_festlegung(
        conn, CHAT, "ort", "The market stalls face east", quelle="befehl")

    text = befehle._baue_p5_uebersicht(conn, CHAT)

    assert "A market square in Padua, today" in text
    assert "Mira" in text and "the elder daughter" in text
    assert "Two families fall out and reconcile" in text
    assert "1. Arrival" in text
    assert "The market stalls face east" in text
    assert text.strip().endswith(befehle.T._TEXT_P5_UEBERSICHT_SCHLUSS)


def test_festlegungen_stehen_unter_eigener_ueberschrift_wie_in_der_werkbank(conn):
    """Birk 07.10.2026: keine Sammelueberschrift, keine deutschen Rohbereiche
    ("struktur", "gruppe") -- je Bereich/Bezug eine eigene, gleichrangige
    Ueberschrift mit der Werkbank-Beschriftung."""
    _bereit(conn)
    repo.schreibe_festlegung(conn, CHAT, "struktur", "Random order", quelle="befehl")
    repo.schreibe_festlegung(conn, CHAT, "gruppe", "3 performers", bezug="Performers", quelle="befehl")

    text = befehle._baue_p5_uebersicht(conn, CHAT)

    assert "Weitere Festlegungen" not in text and "Other fixed items" not in text
    assert "[struktur]" not in text and "[gruppe" not in text
    kopf = web.T.FESTLEGUNG_BEREICH_BESCHRIFTUNG["struktur"]
    assert f"**{kopf[:1].upper() + kopf[1:]}**\nRandom order" in text
    assert "**Performers**\n3 performers" in text


def test_uebersicht_zeigt_leerstellen_statt_zu_schweigen(conn):
    """Ohne jede Festlegung bleibt die Uebersicht trotzdem vollstaendig --
    jeder Block zeigt, dass er offen ist, statt zu fehlen."""
    text = befehle._baue_p5_uebersicht(conn, CHAT)

    assert text.count(befehle.T._TEXT_P5_UEBERSICHT_LEER) >= 3


def test_uebersicht_ohne_szenentitel_zeigt_die_geplante_anzahl(conn):
    repo.setze_arbeitsstand(conn, CHAT, "szenen_anzahl", "4")

    text = befehle._baue_p5_uebersicht(conn, CHAT)

    assert befehle.T._TEXT_P5_UEBERSICHT_SZENENANZAHL.format(anzahl="4") in text


# --- Das Gate blockiert, solange nicht bestaetigt --------------------------


def test_wechsle_phase_blockiert_ohne_bestaetigung(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)

    befehle.wechsle_phase(conn, tg, None, einst, CHAT, 5)

    assert phasen.aktuelle(conn, CHAT) == 4
    assert not _bestaetigt(conn)
    assert tg.knoepfe, "die Uebersicht muss mit Knoepfen kommen"
    beschriftungen = [b for b, _d in tg.knoepfe[-1][2]]
    assert texte._TEXT_P5_CHECK_OK_KNOPF in beschriftungen
    assert texte._TEXT_P5_CHECK_AENDERN_KNOPF in beschriftungen


def test_befehl_phase_5_blockiert_genauso(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")

    befehle.behandle(conn, tg, einst, CHAT, "/phase 5", None, klm=None)

    assert phasen.aktuelle(conn, CHAT) == 4


def test_phaseklick_5_blockiert_genauso(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")

    befehle.behandle(conn, tg, einst, CHAT, "/phaseklick 5", None, klm=None)

    assert phasen.aktuelle(conn, CHAT) == 4


def test_knopf_weiter_zu_phase_5_blockiert(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    knopf_id = repo.lege_knopf_an(conn, CHAT, texte.ART_PHASE, "5")

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}", chat_id=CHAT))

    assert phasen.aktuelle(conn, CHAT) == 4


def test_ja_speichern_uebergang_blockiert(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)

    ergebnis = stationen.uebergang_nach_speichern(conn, tg, None, einst, CHAT)

    assert ergebnis is True  # behandelt (zeigt die Uebersicht), kein No-Op
    assert phasen.aktuelle(conn, CHAT) == 4


def test_erkenner_phase_setzen_5_blockiert(conn, einst):
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)
    _nachricht(conn, CHAT, 1, "lets move on to the prose draft")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "phase_setzen", "wert": "5"}]})
    tg = ErkennerTg()

    erkenner.laufe(klm, tg, conn, einst, CHAT)

    assert phasen.aktuelle(conn, CHAT) == 4


# --- "Alles richtig" bestaetigt und schaltet, "Etwas aendern" bleibt ------


def test_knopf_ok_bestaetigt_und_schaltet_nach_5(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    knopf_id = repo.lege_knopf_an(conn, CHAT, texte.ART_P5_CHECK_OK, None)

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}", chat_id=CHAT))

    assert phasen.aktuelle(conn, CHAT) == 5
    assert _bestaetigt(conn)


def test_knopf_aendern_bleibt_in_phase_4(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    knopf_id = repo.lege_knopf_an(conn, CHAT, texte.ART_P5_CHECK_AENDERN, None)

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}", chat_id=CHAT))

    assert phasen.aktuelle(conn, CHAT) == 4
    assert not _bestaetigt(conn)
    assert any(texte._TEXT_P5_CHECK_AENDERN_FRAGE == t for _c, t in tg.gesendet)


# --- Einmal bestaetigt, geht ein neuer Sprung glatt durch ------------------


def test_bestaetigt_laesst_spaeteren_sprung_glatt_durch(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")
    repo.setze_arbeitsstand(conn, CHAT, "p5_check_bestaetigt_am", repo._jetzt())

    befehle.wechsle_phase(conn, tg, None, einst, CHAT, 5)

    assert phasen.aktuelle(conn, CHAT) == 5
    # Phase 5 selbst bietet beim Eintritt eigene Knoepfe an (Schaerfung) --
    # nur die Werkbank-Uebersicht dieses Gates darf nicht noch einmal
    # dazwischenkommen.
    beschriftungen = [b for _c, _t, leiste in tg.knoepfe for b, _d in leiste]
    assert texte._TEXT_P5_CHECK_OK_KNOPF not in beschriftungen


# --- Zurueck unter 5 verbraucht die Bestaetigung, ein neuer Versuch zeigt
# die Uebersicht wieder --------------------------------------------------


def test_ruecksprung_unter_5_setzt_bestaetigung_zurueck(conn):
    phasen.setze(conn, CHAT, 5, "befehl")
    repo.setze_arbeitsstand(conn, CHAT, "p5_check_bestaetigt_am", repo._jetzt())

    phasen.setze(conn, CHAT, 4, "befehl")

    assert not _bestaetigt(conn)


def test_nach_ruecksprung_zeigt_ein_neuer_versuch_die_uebersicht_wieder(conn, einst):
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 5, "befehl")
    repo.setze_arbeitsstand(conn, CHAT, "p5_check_bestaetigt_am", repo._jetzt())
    phasen.setze(conn, CHAT, 4, "befehl")

    befehle.wechsle_phase(conn, tg, None, einst, CHAT, 5)

    assert phasen.aktuelle(conn, CHAT) == 4
    assert tg.knoepfe


# --- Der Gespraechshinweis, solange der Check ansteht ----------------------


def test_kontext_hinweis_sagt_korrigieren_statt_weiterzufragen(conn):
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)

    hinweis = kontext._baue_phasenhinweis(conn, CHAT)

    assert hinweis == kontext.T._P5_CHECK_GESPRAECHSHINWEIS


def test_kontext_hinweis_leer_ohne_fertige_materiallage(conn):
    phasen.setze(conn, CHAT, 4, "befehl")

    assert kontext._baue_phasenhinweis(conn, CHAT) == ""


def test_kontext_hinweis_verschwindet_nach_bestaetigung(conn):
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)
    repo.setze_arbeitsstand(conn, CHAT, "p5_check_bestaetigt_am", repo._jetzt())

    assert kontext._baue_phasenhinweis(conn, CHAT) != kontext.T._P5_CHECK_GESPRAECHSHINWEIS


# --- Dortmund (Schalter aus) bleibt vollstaendig unveraendert --------------


def test_dortmund_ohne_schalter_bleibt_unveraendert(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "p5_check_aktiv", lambda *a, **kw: False)
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 4, "befehl")

    befehle.wechsle_phase(conn, tg, None, einst, CHAT, 5)

    assert phasen.aktuelle(conn, CHAT) == 5
    beschriftungen = [b for _c, _t, leiste in tg.knoepfe for b, _d in leiste]
    assert texte._TEXT_P5_CHECK_OK_KNOPF not in beschriftungen


def test_dortmund_kontext_hinweis_bleibt_leer(conn, monkeypatch):
    monkeypatch.setattr(workshop, "p5_check_aktiv", lambda *a, **kw: False)
    phasen.setze(conn, CHAT, 4, "befehl")
    _bereit(conn)

    assert kontext._baue_phasenhinweis(conn, CHAT) != kontext.T._P5_CHECK_GESPRAECHSHINWEIS


def test_knopf_ok_ist_voller_eintritt_auch_wenn_phase_5_schon_besucht(conn, einst, monkeypatch):
    """Birk 07.10.2026: "All correct - start Prose Draft" springt direkt in
    Phase 5 MIT Onboarding/Zuordnung -- auch wenn die Gruppe schon einmal in
    Phase 5 war (sonst greift die Wiederherstellung und es kommt nur
    "We're now at 5")."""
    tg = TelegramAttrappe()
    phasen.setze(conn, CHAT, 5, "befehl")
    phasen.setze(conn, CHAT, 4, "befehl")
    eintritte = []
    monkeypatch.setattr(knoepfe, "eintritt_in_phase",
                        lambda c, t, k, e, ch, n: eintritte.append(n))
    knopf_id = repo.lege_knopf_an(conn, CHAT, texte.ART_P5_CHECK_OK, None)

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}", chat_id=CHAT))

    assert phasen.aktuelle(conn, CHAT) == 5
    assert eintritte == [5]

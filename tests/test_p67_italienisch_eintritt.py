"""Morgen-Auftrag 4, Padua Quickfix (Birk 08.10.2026 ~08:52 UTC, G3 live,
web_post 2337-2341): beim Eintritt in Phase 7 kam fuer die italienischen
Gruppen (G1-G3) alles Englisch -- Phasenrahmen, die Telefon-Organisations-
karte mit dem (fuer Padua sinnlosen) Rollenlink-Satz, und das "Noted:/
Agreed:"-Echo des Erkenners.

Drei Punkte, ein Mechanismus (``workshop.italienisch_ab_phase6_chats()``
plus ``sprache.Texte(..., sprachcode="it")``, wie schon in
``szenenkarte.py``/``stagescript.py`` -- eine Chat-Liste, kein globaler
Schalter, Nachtrag 2):

1. Phaseneintritt 6/7 (Kopfzeile, Angebotszeile, Einleitung, Checkliste)
   italienisch fuer gelistete Chats, Phasenname bleibt englisch.
2. Die Telefon-Organisationskarte faellt in Padua-Phase 6/7 ganz weg --
   sie zeigt noch das alte Rollenlink-Layout, das es im Karten-/Stage-
   Script-Ablauf nicht mehr gibt.
3. "Noted:"/"Agreed:" im Erkenner-Echo werden zu "Annotato:"/"Deciso:" --
   nur die Rahmenwoerter, der Inhalt bleibt unuebersetzt.

Der Tester-Chat (7000000000099, nicht in
``workshop.italienisch_ab_phase6_chats()``) bleibt englisch; Dortmund
(kein ``[karten] aktiv``) ist unberuehrt."""

import pytest

from interview_theater import erkenner, knoepfe, phasen, phasentexte, repo, workshop

from tests.test_knoepfe import TelegramAttrappe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    # Morgen-Auftrag 4, Nachtrag 2: eine Chat-Liste statt eines globalen
    # Schalters -- dieser Testfall prueft ausdruecklich das italienische
    # Verhalten, chat_id 1 steht deshalb hier (nur hier) auf der Liste.
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset({1}))
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


class TelegramAttrappeMitBild(TelegramAttrappe):
    def __init__(self):
        super().__init__()
        self.bilder = []

    def sende_bild(self, chat_id, dateiname, inhalt, beschreibung=""):
        self.bilder.append((chat_id, dateiname, inhalt, beschreibung))
        self.naechste_message_id += 1
        return self.naechste_message_id


# --- Punkt 1: Phaseneintritt 6/7 italienisch ------------------------------


def test_eintritt_phase_6_italienisch_fuer_echte_gruppe(conn, padua):
    text = phasentexte.eintritt(conn, 1, 6)

    assert "Fase 6 di 7 · Scene Cards" in text
    assert "La mia proposta per questa fase" in text
    assert "Ora ogni scena diventa una scheda" in text
    assert "Serve: " in text
    assert "Phase 6 of 7" not in text
    assert "My suggestion for this phase" not in text
    assert "What it takes" not in text


def test_eintritt_phase_7_italienisch_mit_willkommenssatz(conn, padua):
    text = phasentexte.eintritt(conn, 1, 7)

    assert "Fase 7 di 7 · Stage Script" in text
    assert "Benvenuti nello Stage Script" in text
    assert "Now every card becomes the stage script" not in text
    assert "Everyone opens their own part via the role link" not in text


def test_eintritt_tester_chat_bleibt_englisch(conn, padua, monkeypatch):
    # Der Tester-Chat steht NICHT in italienisch_ab_phase6_chats() (anders
    # als chat_id 1, das der ``padua``-Fixture oben extra dafuer eintraegt).
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset())

    text = phasentexte.eintritt(conn, 1, 7)

    assert "Phase 7 of 7 · Stage Script" in text
    assert "My suggestion for this phase" in text
    assert "Now every card becomes the stage script" in text


def test_eintritt_phase_5_bleibt_englisch(conn, padua):
    """Nur Phase 6/7 (Birks Regel), Phase 5 (Interviewauswahl) ist aussen vor."""
    text = phasentexte.eintritt(conn, 1, 5)

    assert "Phase 5 of 7" in text
    assert "My suggestion for this phase" in text


def test_eintritt_phase_6_dortmund_bytegleich(conn):
    """Ohne Padua-Profil ist ``szenenkarten_aktiv`` aus -- die alte Phase-6-
    Einleitung (Prosa) bleibt deutsch, unberuehrt vom neuen Schalter."""
    text = phasentexte.eintritt(conn, 1, 6)

    assert "Annotato" not in text
    assert "Ora ogni scena diventa" not in text


# --- Punkt 2: die Telefon-Organisationskarte faellt in P6/7 weg ----------


def test_phase_6_und_7_schicken_keine_handykarte(conn, padua):
    tg = TelegramAttrappeMitBild()

    knoepfe.eintritt_in_phase(conn, tg, None, None, 1, 6)
    knoepfe.eintritt_in_phase(conn, tg, None, None, 1, 7)

    assert tg.bilder == []


def test_phase_5_schickt_weiterhin_die_handykarte(conn, padua):
    tg = TelegramAttrappeMitBild()

    knoepfe.eintritt_in_phase(conn, tg, None, None, 1, 5)

    assert len(tg.bilder) == 1


def test_handykarte_phase_6_7_dortmund_bytegleich(conn):
    tg = TelegramAttrappeMitBild()

    knoepfe.eintritt_in_phase(conn, tg, None, None, 1, 6)

    assert len(tg.bilder) == 1


# --- Punkt 3: "Noted:"/"Agreed:" -> "Annotato:"/"Deciso:" ----------------


def test_phase_setzen_meldung_italienisch_in_phase_7(conn, einst, padua):
    phasen.setze(conn, 1, 6, "test")

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "7"}])
    meldung = erkenner.baue_meldung(wirkliche, conn, 1)

    assert "Siamo ora a 7 · Stage Script." in meldung
    assert meldung.startswith("Annotato:")
    assert "We're now at" not in meldung
    assert "Noted:" not in meldung


def test_festgehalten_zeile_italienisch_in_phase_6(conn, einst, padua):
    phasen.setze(conn, 1, 6, "test")

    wirkliche = erkenner.wende_an(
        conn, einst, 1,
        [{"art": "festlegung_setzen", "wert": "ort: A semicircle of chairs."}],
    )
    meldung = erkenner.baue_meldung(wirkliche, conn, 1)

    assert "Deciso: A semicircle of chairs." in meldung
    assert "Agreed:" not in meldung


def test_erkenner_meldung_tester_chat_bleibt_englisch(conn, einst, padua, monkeypatch):
    # Der Tester-Chat steht NICHT in italienisch_ab_phase6_chats() (anders
    # als chat_id 1, das der ``padua``-Fixture oben extra dafuer eintraegt).
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset())
    phasen.setze(conn, 1, 6, "test")

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "7"}])
    meldung = erkenner.baue_meldung(wirkliche, conn, 1)

    assert "We're now at 7 · Stage Script." in meldung
    assert meldung.startswith("Noted:")


def test_erkenner_meldung_phase_ausserhalb_6_7_bleibt_englisch(conn, einst, padua):
    """Ausserhalb von Phase 6/7 entscheidet allein die Profilsprache --
    ``workshop.italienisch_ab_phase6_chats`` kennt keine Phase, die
    Eingrenzung sitzt in ``erkenner._texte_fuer_phase``."""
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "3"}])
    meldung = erkenner.baue_meldung(wirkliche, conn, 1)

    assert "We're now at 3 ·" in meldung
    assert meldung.startswith("Noted:")


def test_erkenner_meldung_phase_6_7_dortmund_bytegleich(conn, einst):
    phasen.setze(conn, 1, 6, "test")

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "7"}])
    meldung = erkenner.baue_meldung(wirkliche, conn, 1)

    assert "Wir sind jetzt bei 7 ·" in meldung
    assert meldung.startswith("Notiert:")

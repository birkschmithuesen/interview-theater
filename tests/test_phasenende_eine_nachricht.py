"""Padua Hotfix B5 (Birk 02.10.2026): EINE Nachricht am Phasenende, nicht zwei.

Live (Web-Kanal, web_post 11+12): nach dem Speichern der Begriffsliste kam
erst "Noted ... Yes, save / No, change it again / Undo" und sofort danach
"Phase 1 complete ... On to Questions?" mit eigenen Knoepfen. Macht ein
Speichern die Phase abschliessbar, steht jetzt nur noch die
Abschlussnachricht da -- mit "Weiter zu Phase N · Titel", dem Korrekturknopf
und (Erkenner-Weg) dem Undo-Knopf.

Kein Netz, kein Modell: Telegram ist eine Attrappe, das Sprachmodell liefert
vorbereitete Antworten. Erfundenes Material.
"""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo

from test_undo_knopf import LLMAttrappe, TelegramAttrappe, _druck, padua  # noqa: F401


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _laufe(conn, tg, einst, aenderungen, message_id=1):
    repo.merke_nachricht(
        conn, 1, message_id, "Mert", 0, "text", "unsere Begriffe", repo._jetzt())
    erkenner.laufe(LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, 1)


def _daten(tg, beschriftung):
    for _, _, leiste, _ in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r} in {tg.knoepfe!r}")


def _knopf(conn, daten):
    return repo.hole_knopf(conn, int(daten[len(knoepfe.PRAEFIX):]))


def test_erkenner_phase1_abnahme_ist_genau_eine_nachricht(conn, tg, einst):
    _laufe(conn, tg, einst, [{"art": "begriffe_setzen", "wert": "Geld, Bleiben, Gehen"}])

    assert len(tg.gesendet) == 1, tg.texte
    assert len(tg.knoepfe) == 1
    _, text, leiste, _ = tg.knoepfe[0]
    assert [b for b, _ in leiste] == [
        "Weiter zu Phase 2 · Fragen", "Begriffe aendern", "Rueckgaengig",
    ]
    # Die Abschlussnachricht traegt den Inhalt -- die Notiert-Zeile entfaellt.
    assert "Geld, Bleiben, Gehen" in text
    assert not text.startswith("Notiert:")
    assert text.endswith("Weiter zu Phase 2 · Fragen?")
    # Die Knopfarten: Weiter = ART_PHASE, Korrektur = ART_NOCH_NICHT, Undo.
    arten = [_knopf(conn, d)["art"] for _, d in leiste]
    assert arten == [knoepfe.ART_PHASE, knoepfe.ART_NOCH_NICHT, knoepfe.ART_UNDO]
    assert all(len(d.encode("utf-8")) < 64 for _, d in leiste)


def test_erkenner_phase1_abnahme_padua_englisch(conn, tg, einst, padua):  # noqa: F811
    _laufe(conn, tg, einst, [{"art": "begriffe_setzen", "wert": "money, staying"}])

    assert len(tg.gesendet) == 1, tg.texte
    _, text, leiste, _ = tg.knoepfe[0]
    assert [b for b, _ in leiste] == [
        "Continue to phase 2 · Questions", "Change terms", "Undo",
    ]
    assert "money, staying" in text
    assert not text.startswith("Noted")


def test_korrekturknopf_holt_die_eine_nachricht_nach_der_aenderung_zurueck(
        conn, tg, einst):
    _laufe(conn, tg, einst, [{"art": "begriffe_setzen", "wert": "Geld, Bleiben"}])
    knoepfe.behandle(conn, tg, None, einst,
                     _druck(_daten(tg, "Begriffe aendern"), message_id=501))

    # Wirkung von "Noch etwas aendern": Angebot abgelehnt, nicht fuer immer.
    assert repo.hole_phase_angeboten(conn, 1) == -2
    assert tg.texte[-1] == knoepfe.T._TEXT_NOCH_NICHT

    vorher = len(tg.gesendet)
    _laufe(conn, tg, einst,
           [{"art": "begriffe_setzen", "wert": "Geld, Bleiben, Heimat"}], message_id=2)

    neu = tg.gesendet[vorher:]
    assert len(neu) == 1, neu
    _, text, leiste, _ = tg.knoepfe[-1]
    assert "Geld, Bleiben, Heimat" in text
    assert [b for b, _ in leiste][:2] == ["Weiter zu Phase 2 · Fragen", "Begriffe aendern"]
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Geld, Bleiben, Heimat"


def test_undo_in_der_einen_nachricht_nimmt_zurueck_und_der_weiterknopf_verfaellt(
        conn, tg, einst):
    _laufe(conn, tg, einst, [{"art": "begriffe_setzen", "wert": "Geld, Bleiben"}])
    weiter = _daten(tg, "Weiter zu Phase 2 · Fragen")

    knoepfe.behandle(conn, tg, None, einst,
                     _druck(_daten(tg, "Rueckgaengig"), message_id=501))

    assert not (repo.hole_arbeitsstand(conn, 1)["begriffe"] or "")
    assert _knopf(conn, weiter)["benutzt_am"], "Weiter darf nach Undo nicht wirken"
    assert phasen.aktuelle(conn, 1) == 1


def test_knopfweg_phase1_abnahme_geht_direkt_automatisch_weiter(conn, tg, einst):
    """KORREKTUR Birk 18:20 (Kommentar 807, ersetzt B5 fuer den Knopfweg):
    "Ja, speichern" fixiert UND geht DIREKT AUTOMATISCH in die naechste
    Phase -- keine Abschlussnachricht mit "Weiter zu ..."-Angebot an dieser
    Stelle (B5 bleibt allein am Erkenner-Pfad, siehe
    test_erkenner_phase1_abnahme_ist_genau_eine_nachricht oben)."""
    leiste = knoepfe.speicherleiste(conn, 1, "begriffe", "Geld, Bleiben")
    knoepfe.behandle(conn, tg, None, einst, _druck(leiste[0][1], message_id=400))

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Geld, Bleiben"
    assert phasen.aktuelle(conn, 1) == 2
    assert not any(
        b.startswith("Weiter zu") for _, _, leiste, _ in tg.knoepfe for b, _ in leiste
    )


def test_ohne_faelliges_angebot_bleibt_es_bei_notiert_und_leiste(conn, tg, einst):
    """Gegenprobe: macht das Speichern die Phase NICHT abschliessbar (Phase 4,
    Setting allein), bleibt der bisherige Weg -- Notiert + Ja/Nein + Undo."""
    phasen.setze(conn, 1, 4, "test")
    _laufe(conn, tg, einst, [{"art": "rahmen_setzen", "wert": "Bahnhof, abends"}])

    _, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF, knoepfe.T._TEXT_ANDERS_KNOPF,
        knoepfe.T._TEXT_UNDO_KNOPF,
    ]

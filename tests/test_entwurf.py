"""Tests fuer die Stufe A des Phase-5-Entwurfs (Padua Phasen TEIL 1,
03.10.2026): die Geschichts-Uebersicht.

Gemessen werden hier nur die reinen Funktionen -- Nutzertextbau und
Anzeige-Zusammenbau, kein Modellaufruf und kein Thread. ``entwurf.py``
spiegelt ``schaerfung.py``s Bauart (ein Schema-Aufruf, eigener Thread,
eigene Textbau-Funktionen); die Fixture-Konventionen (``conn``, kein
Netzzugriff) sind dieselben wie in ``tests/test_schaerfung.py``.
"""

from interview_theater import entwurf, repo


def test_baue_anzeige_enthaelt_alle_abschnitte():
    ergebnis = {
        "logline": "Two sisters meet again after years apart.",
        "setting": "A station cafe, late evening.",
        "figuren_zeilen": ["Mira -- wants closeness", "Nora -- wants distance"],
        "spannungsbogen": "Neither says what they want.",
        "szenen_was_passiert": ["They arrive.", "A photo surfaces.", "A confession."],
    }

    anzeige = entwurf.baue_anzeige(ergebnis)

    assert "Logline: Two sisters meet again after years apart." in anzeige
    assert "Setting: A station cafe, late evening." in anzeige
    assert "Characters:" in anzeige
    assert "- Mira -- wants closeness" in anzeige
    assert "- Nora -- wants distance" in anzeige
    assert "Tension arc: Neither says what they want." in anzeige
    assert "Scenes:" in anzeige
    assert "1. They arrive." in anzeige
    assert "2. A photo surfaces." in anzeige
    assert "3. A confession." in anzeige


def test_baue_nutzertext_uebersicht_traegt_vorige_fassung_und_notiz(conn):
    chat_id = 1
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte", "Two neighbours drift apart.\nEnding: open"
    )
    repo.setze_figur(conn, chat_id, "Mira", "wants to be heard")
    repo.setze_arbeitsstand(conn, chat_id, "geschichte_uebersicht", "Logline: old one")

    text = entwurf.baue_nutzertext_uebersicht(conn, chat_id, notiz="make it sadder")

    assert "Setting: A hallway, moving boxes." in text
    assert "Two neighbours drift apart." in text
    assert "- Mira -- wants to be heard" in text
    assert "Logline: old one" in text
    assert "make it sadder" in text


def test_baue_nutzertext_uebersicht_traegt_die_szenenanzahl(conn):
    chat_id = 1
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", "5")

    text = entwurf.baue_nutzertext_uebersicht(conn, chat_id)

    assert "Number of scenes: 5" in text


def test_baue_nutzertext_uebersicht_ist_leer_ohne_stand(conn):
    """Ohne jede Festlegung bleibt der Nutzertext leer -- kein erfundener
    Platzhaltertext, der das Modell in die Irre fuehrt."""
    assert entwurf.baue_nutzertext_uebersicht(conn, 1) == ""


def test_generiere_uebersicht_ruft_modellwahl_mit_dem_schema(conn, einst, monkeypatch):
    aufrufe = []

    def _fake_aufruf_schema(conn_, klm, e, chat_id, system, nutzer, schema, art,
                             *, ueber_claude, modell=None):
        aufrufe.append({
            "system": system, "nutzer": nutzer, "schema": schema, "art": art,
        })
        return {
            "logline": "L", "setting": "S", "figuren_zeilen": [],
            "spannungsbogen": "B", "szenen_was_passiert": ["Eins."],
        }

    monkeypatch.setattr(entwurf.modellwahl, "aufruf_schema", _fake_aufruf_schema)
    monkeypatch.setattr(entwurf.szene_claude, "ist_aktiv", lambda e, conn_, chat_id: False)

    ergebnis = entwurf.generiere_uebersicht(object(), conn, einst, 1)

    assert aufrufe[0]["art"] == entwurf.ART_UEBERSICHT
    assert aufrufe[0]["schema"] == entwurf.SCHEMA_UEBERSICHT
    assert ergebnis["logline"] == "L"


def test_starte_uebersicht_ohne_modell_liefert_none(conn, einst):
    assert entwurf.starte_uebersicht(conn, None, None, einst, 1) is None


def test_starte_uebersicht_gibt_none_wenn_die_sperre_schon_haelt(conn, einst):
    sperre = entwurf._sperre_fuer(1)
    sperre.acquire()
    try:
        assert entwurf.starte_uebersicht(conn, None, object(), einst, 1) is None
    finally:
        sperre.release()

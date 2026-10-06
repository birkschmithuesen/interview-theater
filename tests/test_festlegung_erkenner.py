"""Die Erkenner-Art ``festlegung_setzen`` (06.09.2026).

Der Regelweg in die Auffangtabelle. Sie ist die Antwort auf den Befund aus
``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 3: fuer jede relevante
Angabe ausserhalb des festen Slot-Rasters gab es kein Feld -- nur einen
``journal``-Eintrag, der aus dem Prompt faellt.

Fixtures synthetisch.
"""

import pytest

from interview_theater import db, erkenner, repo, sprache


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class Umgebung:
    bot_name = "gruppe1"


def _wende(conn, wert):
    return erkenner.wende_an(
        conn, Umgebung(), 1, [{"art": "festlegung_setzen", "wert": wert}]
    )


def test_art_ist_bekannt():
    assert "festlegung_setzen" in erkenner.ARTEN
    assert "festlegung_setzen" in erkenner.SCHEMA["properties"]["aenderungen"][
        "items"]["properties"]["art"]["enum"]


def test_gilt_nicht_aus_einer_aufnahme():
    """Was eine interviewte Person erzaehlt, ist Material und nie eine
    Absicht der Gruppe (docs/agents/entscheidungen.md, Korpusfaelle n12/n26)."""
    assert "festlegung_setzen" not in erkenner.ARTEN_IN_AUFNAHME


def test_bereich_bezug_und_text(conn):
    wirklich = _wende(conn, "figur/Kassandra: 19 Jahre, Schauspielerin")
    assert wirklich == [
        {
            "art": "festlegung_setzen",
            "wert": "[figur/Kassandra] 19 Jahre, Schauspielerin",
            "bereich": "figur",
            "bezug": "Kassandra",
            "text": "19 Jahre, Schauspielerin",
        }
    ]
    zeile = repo.festlegungen(conn, 1)[0]
    assert (zeile["bereich"], zeile["bezug"], zeile["quelle"]) == (
        "figur", "Kassandra", "erkenner"
    )


def test_ohne_bezug(conn):
    _wende(conn, "struktur: Nur eine Szene, die erste Folge einer Serie")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "struktur"
    assert zeile["bezug"] is None


def test_ohne_bereich_landet_es_in_sonstiges(conn):
    """Ein Wert ohne Doppelpunkt ist kein Fehler, sondern der haeufigste
    Fall von "passt in kein Fach": lieber in ``sonstiges`` als verloren."""
    _wende(conn, "Die Szenentexte sollen kurz sein, hoechstens eine Seite")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "sonstiges"
    assert zeile["text"] == "Die Szenentexte sollen kurz sein, hoechstens eine Seite"


def test_unbekannter_bereich_bleibt_als_freier_titel_erhalten(conn):
    """Padua-Brainstorming-Umbau (02.10.2026): "unlimited, free titles" --
    ein unbekannter Bereich wird nicht mehr nach "sonstiges" kollabiert."""
    _wende(conn, "dramaturgie: Das Ende bleibt offen")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "dramaturgie"
    assert zeile["text"] == "Das Ende bleibt offen"


def test_leerer_wert_wirkt_nicht(conn):
    assert _wende(conn, "   ") == []
    assert repo.festlegungen(conn, 1) == []


def test_bereich_ohne_text_wirkt_nicht(conn):
    assert _wende(conn, "struktur:") == []
    assert repo.festlegungen(conn, 1) == []


def test_dieselbe_festlegung_zweimal_meldet_nur_einmal(conn):
    _wende(conn, "gruppe/die Coolen: definieren sich ueber Herkunft und Geld")
    zweite = _wende(conn, "gruppe/die Coolen: definieren sich ueber Herkunft und Geld")
    assert zweite == []
    assert len(repo.festlegungen(conn, 1)) == 1


def test_was_schon_im_arbeitsstand_steht_wird_verworfen(conn):
    """Risiko 2 der Analyse (\"Doppelte Wahrheit\"): steht das Setting
    sowohl in ``arbeitsstand.rahmen`` als auch als Festlegung, widersprechen
    sich beide irgendwann. Abgefangen wird das hier in der Auswertung --
    genauso wie ``_ist_geschichte`` den Fehler in umgekehrter Richtung
    abfaengt."""
    repo.setze_arbeitsstand(
        conn, 1, "rahmen", "Am Kanal im Sommer, nachmittags nach der Schule"
    )
    assert _wende(conn, "ort: Am Kanal im Sommer") == []
    assert repo.festlegungen(conn, 1) == []
    vorfaelle = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "festlegung_stand_schon_im_feld" in vorfaelle


def test_eine_echte_ergaenzung_zum_setting_bleibt(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal im Sommer")
    assert _wende(conn, "ort: dazu der Skatepark an der Bruecke")
    assert len(repo.festlegungen(conn, 1)) == 1


def test_reine_mitgliedschaft_ohne_eigenen_fakt_wirkt_nicht(conn):
    """02.10.2026, Fall fl03: 'eine der beiden Gruppen' wiederholt nur die
    Zugehoerigkeit, die schon im Bezug steckt -- kein eigener Fakt."""
    assert _wende(conn, "gruppe/die Stillen: eine der beiden Gruppen") == []
    assert repo.festlegungen(conn, 1) == []
    vorfaelle = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "festlegung_ohne_inhalt" in vorfaelle


def test_platzhalter_ohne_beschreibung_wirkt_nicht(conn):
    assert _wende(conn, "gruppe/die Stillen: (no description)") == []
    assert repo.festlegungen(conn, 1) == []


def test_eine_kurze_aber_echte_angabe_bleibt_trotz_bezug(conn):
    """Die Gegenprobe zu beiden Faellen oben: eine knappe Angabe mit echtem
    Inhalt darf die Pruefung nicht mitreissen."""
    assert _wende(conn, "gruppe/die Lauten: erkennt man an den Markenklamotten")
    assert len(repo.festlegungen(conn, 1)) == 1


def test_figur_festlegung_faellt_weg_wenn_dieselbe_figur_gesetzt_wird(conn):
    """02.10.2026, Fall z04: 'figur: die Zuordnung der Figuren ist nur fuer
    die Gruppe' neben drei figur_setzen ist Metakommentar zum Festhalten
    selbst, kein Fakt UEBER eine Figur."""
    wirklich = erkenner.wende_an(
        conn, Umgebung(), 1,
        [
            {"art": "figur_setzen", "wert": "Nour: traegt ein Gericht in fremde Raeume"},
            {"art": "figur_setzen", "wert": "Selin: baute aus einem Satz ein Haus"},
            {"art": "figur_setzen", "wert": "Asmin: trug zehn Jahre Schwarz"},
            {
                "art": "festlegung_setzen",
                "wert": "figur: die Zuordnung der Figuren ist nur fuer die Gruppe",
            },
        ],
    )
    arten = [a["art"] for a in wirklich]
    assert arten == ["figur_setzen", "figur_setzen", "figur_setzen"]
    assert repo.festlegungen(conn, 1) == []


def test_figur_festlegung_mit_bezug_auf_gesetzte_figur_faellt_weg(conn):
    wirklich = erkenner.wende_an(
        conn, Umgebung(), 1,
        [
            {"art": "figur_setzen", "wert": "Nour: traegt ein Gericht in fremde Raeume"},
            {"art": "festlegung_setzen", "wert": "figur/Nour: ist eine Hauptfigur"},
        ],
    )
    assert [a["art"] for a in wirklich] == ["figur_setzen"]
    assert repo.festlegungen(conn, 1) == []


def test_figur_festlegung_ohne_figur_setzen_bleibt(conn):
    """Ohne gleichzeitiges figur_setzen ist dieselbe Zeile ein eigener Fakt
    (fl01: Herkunft einer Figur, fuer die niemand gerade figur_setzen schreibt)."""
    wirklich = erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "festlegung_setzen", "wert": "figur/Sevda: 19, kommt aus Bulgarien"}],
    )
    assert [a["art"] for a in wirklich] == ["festlegung_setzen"]
    assert len(repo.festlegungen(conn, 1)) == 1


def test_meldung_nennt_die_festlegung_mit_bezug():
    meldung = erkenner.baue_meldung(
        [
            {
                "art": "festlegung_setzen",
                "wert": "[figur/Kassandra] 19 Jahre",
                "bereich": "figur",
                "bezug": "Kassandra",
                "text": "19 Jahre",
            }
        ]
    )
    assert meldung == "Notiert:\nFestgehalten (Kassandra): 19 Jahre"


def test_meldung_ohne_bezug():
    meldung = erkenner.baue_meldung(
        [
            {
                "art": "festlegung_setzen",
                "wert": "[struktur] Nur eine Szene",
                "bereich": "struktur",
                "bezug": None,
                "text": "Nur eine Szene",
            }
        ]
    )
    assert meldung == "Notiert:\nFestgehalten: Nur eine Szene"


# --- Abnahme-Befund A13/laptop-A1 (06.10.2026): Bereichs-Titel der 📌-Zeile
# in Phase 4 -- "RAHMEN" (deutsches Protokollwort, oft GROSSBUCHSTABEN) blieb
# unuebersetzt/GROSSBUCHSTABEN stehen, auch in einer englischen Gruppe.
# Root Cause: ``_meldungszeilen`` grossschrieb nur den ersten Buchstaben des
# rohen Bereichswerts, ohne jeden Nachschlag ueber T (DE/EN). ------------

def test_jeder_bereich_den_der_erkenner_kennt_hat_eine_beschriftung():
    """Die sieben kanonischen Bereiche (``repo.FESTLEGUNG_BEREICHE``) plus
    ``rahmen`` -- das Wort leckt aus der GROSSBUCHSTABEN-Protokollliste von
    art=entfernen (sprachen/en/prompts/erkenner.md Punkt 20) in
    festlegung_setzen, wenn ein Modell "If none fits, use a short word of
    your own" zu woertlich damit einloest (gemessen:
    festlegung.bereich='RAHMEN')."""
    assert set(erkenner._FESTLEGUNG_BEREICH_BESCHRIFTUNG) == (
        set(repo.FESTLEGUNG_BEREICHE) | {"rahmen"}
    )


def test_bereich_titel_bekannter_bereich_grossgeschrieben():
    assert erkenner._bereich_titel("figur") == "Figur"
    assert erkenner._bereich_titel("rahmen") == "Rahmen"
    # Case-insensitiv: repo.normiere_bereich laesst einen unbekannten
    # Bereich wie "RAHMEN" unveraendert (nicht kleingeschrieben) stehen.
    assert erkenner._bereich_titel("RAHMEN") == "Rahmen"


def test_bereich_titel_freier_titel_wird_nur_lesbar_nicht_uebersetzt():
    """Ein echter freier Bereichstitel (den die Gruppe spaeter wiederfinden
    soll, repo.normiere_bereich-Docstring) bekommt keine erfundene
    Uebersetzung, aber auch keine stehenbleibenden GROSSBUCHSTABEN mehr --
    vorher liess ``titel[:1].upper() + titel[1:]`` ein komplett
    grossgeschriebenes Protokollwort unveraendert."""
    assert erkenner._bereich_titel("COSTUMES") == "Costumes"
    assert erkenner._bereich_titel("kostueme") == "Kostueme"


def test_bereich_titel_leer_wird_sonstiges():
    assert erkenner._bereich_titel(None) == erkenner._bereich_titel("sonstiges")


def test_festlegung_bereich_rahmen_in_der_notiert_zeile_englisch(conn, monkeypatch):
    """End-to-end-Reproduktion des Befunds: Gruppe spricht englisch, der
    Erkenner liefert den Bereich als rohes Protokollwort "RAHMEN", Phase 4
    ist aktiv -- die 📌-Zeile darf das deutsche Wort nicht zeigen."""
    monkeypatch.setattr(sprache, "code", lambda: "en")
    repo.setze_phase(conn, 1, 4)
    wirklich = _wende(
        conn, "RAHMEN: the departure board still shows her bus every night"
    )
    meldung = erkenner.baue_meldung(wirklich, conn, 1)
    assert "📌 Frame:" in meldung
    assert "RAHMEN" not in meldung


def test_entfernen_nimmt_eine_festlegung_zurueck(conn):
    """Weiches Loeschen ueber dieselbe art wie alles andere (N3) -- ohne
    diesen Weg erbt die neue Tabelle den alten Fehler: ein Eintrag ueber
    einen laengst zurueckgenommenen zweiten Spielort, den nie jemand
    abraeumt."""
    _wende(conn, "ort: Zweiter Ort ist die Schule")
    wirklich = erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "entfernen", "wert": "Festlegung: Schule"}],
    )
    assert wirklich == [
        {"art": "entfernen", "wert": "Festlegung: Zweiter Ort ist die Schule"}
    ]
    assert repo.festlegungen(conn, 1) == []


def test_entfernen_ohne_treffer_wirkt_nicht(conn):
    assert erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "entfernen", "wert": "Festlegung: Bahnhof"}],
    ) == []


def test_figur_festlegung_faellt_weg_neben_figur_quelle_setzen():
    # Fall en-e15 (02.10.2026): Zuordnung zu einem Interview plus dieselbe
    # Figur noch einmal als Festlegung -- doppelt erfasst.
    aenderungen = [
        {"art": "figur_quelle_setzen", "wert": "Karim: Interview 3"},
        {"art": "festlegung_setzen", "wert": "FIGUR/Karim: the kid with the headphones"},
    ]
    assert erkenner.waechter_filter(aenderungen) == aenderungen[:1]


def test_waechter_filter_verwirft_inhaltslose_festlegung():
    aenderungen = [
        {"art": "festlegung_setzen", "wert": "gruppe/die Lauten: erkennt man an den Markenklamotten"},
        {"art": "festlegung_setzen", "wert": "gruppe/die Stillen: eine der beiden Gruppen"},
    ]
    assert erkenner.waechter_filter(aenderungen) == aenderungen[:1]


def test_waechter_filter_laesst_andere_arten_unveraendert():
    # Der Korpus misst nach diesem Filter -- er darf an Arten ohne Waechter
    # nichts aendern, sonst faellt die Trefferquote ohne Modellaenderung
    # (Fehlversuch 02.10.: Vergleich auf der Rueckgabe von wende_an, 90/122).
    aenderungen = [
        {"art": "szene_planen", "wert": "SZENE 1 | ORT: Kueche"},
        {"art": "entfernen", "wert": "FIGUR Tomas"},
        {"art": "interview_beenden", "wert": ""},
        {"art": "szene_usa", "wert": "ja"},
    ]
    assert erkenner.waechter_filter(aenderungen) == aenderungen


def test_korpusvergleich_nutzt_den_waechter_filter():
    from scripts import pruefe_prompts
    roh = [
        {"art": "figur_setzen", "wert": "Mira: macht Pfannkuchen"},
        {"art": "festlegung_setzen", "wert": "figur: die Zuordnung ist nur fuer die Gruppe"},
    ]
    assert pruefe_prompts._wende_fuer_vergleich(None, 1, roh) == roh[:1]


def test_interview_starten_faellt_weg_beim_ruecksprung_in_die_interviews():
    # Korpusfall p05 (02.10.2026): "zurueck zu den Interviews, wir fragen
    # Hatice nochmal" ist ein Plan -- der Phaseneintritt bietet den Knopf an.
    roh = [
        {"art": "phase_setzen", "wert": "3"},
        {"art": "interview_starten", "wert": ""},
    ]
    assert erkenner.waechter_filter(roh) == roh[:1]


def test_interview_starten_bleibt_ohne_phasenwechsel():
    roh = [{"art": "interview_starten", "wert": ""}]
    assert erkenner.waechter_filter(roh) == roh


def test_interview_starten_bleibt_bei_sprung_in_andere_phase():
    roh = [
        {"art": "phase_setzen", "wert": "5"},
        {"art": "interview_starten", "wert": ""},
    ]
    assert erkenner.waechter_filter(roh) == roh

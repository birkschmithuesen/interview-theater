"""Tests fuer den Absichtserkenner (SPEC-kontext-architektur.md § 4.3,
teil-b.md Aufgabe 2).

Wie in test_verdichter.py: das Sprachmodell wird durch eine Attrappe mit
einer .schema()-Methode ersetzt, die eine vorbereitete Antwort liefert (oder
einen vorbereiteten Fehler wirft) und ihre Aufrufe samt Parametern
aufzeichnet. Kein Netzzugriff.
"""

import pytest

from theatersoap import erkenner, repo


class LLMAttrappe:
    """Ersetzt theatersoap.llm.LLM in Tests: liefert eine vorbereitete Antwort
    (oder wirft einen vorbereiteten Fehler), zaehlt die Aufrufe und
    zeichnet die zuletzt gesehenen Parameter auf -- insbesondere modell und
    temperature, damit sich pruefen laesst, dass der Erkenner NICHT das
    Gespraechsmodell verwendet."""

    def __init__(self, antwort=None, fehler=None):
        self._antwort = antwort
        self._fehler = fehler
        self.aufrufe = 0
        self.gesehen = {}

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        self.aufrufe += 1
        self.gesehen = {
            "chat_id": chat_id,
            "system": system,
            "nutzer": nutzer,
            "schema": schema,
            "art": art,
            "modell": modell,
            "temperature": temperature,
        }
        if self._fehler is not None:
            raise self._fehler
        return self._antwort


def _nachricht(conn, chat_id, message_id, text, absender="Mert", ist_bot=0):
    repo.merke_nachricht(conn, chat_id, message_id, absender, ist_bot, "text", text, repo._jetzt())


def test_ohne_neue_nachrichten_wird_das_modell_nicht_gerufen(conn, einst):
    klm = LLMAttrappe(antwort={"aenderungen": []})
    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 0


def test_leere_aenderungsliste_ist_kein_fehler(conn, einst):
    _nachricht(conn, 1, 1, "guten Morgen zusammen")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 1


def test_interview_starten_erkannt_und_wasserzeichen_vorgerueckt(conn, einst):
    _nachricht(conn, 1, 5, "wir machen jetzt ein Interview")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_starten", "wert": ""}]})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == [{"art": "interview_starten", "wert": ""}]
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 5


def test_mehr_als_fuenf_aenderungen_werden_auf_fuenf_gekappt(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    sechs = [{"art": "verworfen", "wert": f"Sache {i}"} for i in range(6)]
    klm = LLMAttrappe(antwort={"aenderungen": sechs})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert len(ergebnis) == erkenner.MAX_AENDERUNGEN == 5


def test_unbekannte_art_wird_verworfen_statt_zu_krachen(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "irgendwas_erfundenes", "wert": "?"},
        {"art": "kernthema_setzen", "wert": "Ankommen"},
    ]})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == [{"art": "kernthema_setzen", "wert": "Ankommen"}]


def test_fehlschlag_laesst_wasserzeichen_stehen_und_schreibt_vorfall(conn, einst):
    _nachricht(conn, 1, 3, "diverses")
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell nicht erreichbar"))

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 0
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "extraktor_fehler"


def test_deckel_ueber_4000_token_rueckt_wasserzeichen_vor_und_schreibt_vorfall(conn, einst):
    # kontext.schaetze() ist Zeichen // 3 -- 15.000 Zeichen sind 5.000
    # geschaetzte Token, klar ueber dem Deckel.
    _nachricht(conn, 1, 7, "x" * 15_000)
    klm = LLMAttrappe(antwort={"aenderungen": []})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 0, "das Modell wird beim Deckel gar nicht erst gerufen"
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 7
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "fenster_verworfen"


def test_ruft_erkennermodell_mit_temperature_0_2_auf_nicht_das_gespraechsmodell(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    erkenner.erkenne(klm, conn, einst, 1)

    assert klm.gesehen["modell"] == einst.erkenner_modell
    assert klm.gesehen["modell"] != einst.llm_modell
    assert klm.gesehen["temperature"] == 0.2
    assert klm.gesehen["art"] == "erkenner"


def test_schema_hat_additional_properties_false_und_vollstaendiges_required():
    def pruefe_objekt(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, node
                eigenschaften = set(node.get("properties", {}).keys())
                assert set(node.get("required", [])) == eigenschaften, node
            for wert in node.values():
                pruefe_objekt(wert)
        elif isinstance(node, list):
            for element in node:
                pruefe_objekt(element)

    pruefe_objekt(erkenner.SCHEMA)


def test_schema_kennt_kein_maxitems():
    """global-constraints.md § Schema: die Fuenf-Obergrenze steht im
    Prompttext und wird im Code durchgesetzt, nicht im Schema (von strikten
    Modi oft nicht unterstuetzt)."""
    assert "maxItems" not in str(erkenner.SCHEMA)


def test_arten_enthaelt_alle_elf_werte():
    erwartet = {
        "interview_starten", "interview_beenden", "interview_benennen",
        "begriffe_setzen", "kernthema_setzen", "hauptkonflikt_setzen",
        "figur_setzen", "wortlaut_an", "wortlaut_aus", "verworfen", "entschieden",
    }
    assert set(erkenner.ARTEN) == erwartet


def test_prompt_enthaelt_fuenf_beispiele_davon_zwei_leer():
    """Grober Regressionsschutz gegen einen versehentlich verkuerzten Prompt
    (SPEC/Rechercheempfehlung: 5 Few-Shot-Beispiele, davon 2 leer)."""
    anzahl_beispiele = erkenner.PROMPT.count("<beispiel>")
    anzahl_leer = erkenner.PROMPT.count('"aenderungen": []')
    assert anzahl_beispiele == 5
    assert anzahl_leer == 2


# ---------------------------------------------------------------------------
# Aufgabe 3: Schreibpfad (erkenner.wende_an)
# ---------------------------------------------------------------------------


def test_kernthema_ueberschreiben_aendert_feld_und_gilt_als_aenderung(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    )

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"
    assert wirkliche == [{"art": "kernthema_setzen", "wert": "Ankommen"}]


def test_kernthema_ueberschreiben_ersetzt_alten_wert(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Abschied"}])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Abschied"


def test_derselbe_wert_nochmal_gilt_nicht_als_aenderung(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    )

    assert wirkliche == []


def test_hauptkonflikt_und_begriffe_werden_ueberschrieben(conn, einst):
    wirkliche = erkenner.wende_an(
        conn,
        einst,
        1,
        [
            {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"},
            {"art": "begriffe_setzen", "wert": "Migration, Ankommen"},
        ],
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["hauptkonflikt"] == "Bleiben oder Gehen"
    assert stand["begriffe"] == "Migration, Ankommen"
    assert len(wirkliche) == 2


def test_figur_mit_bekanntem_namen_wird_ueberschrieben_nicht_verdoppelt(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_setzen", "wert": " maria : kam 1998"}]
    )

    figuren = repo.figuren(conn, 1)
    assert len(figuren) == 1
    assert figuren[0]["beschreibung"] == "kam 1998"
    assert wirkliche == [{"art": "figur_setzen", "wert": "maria"}]


def test_figur_ohne_doppelpunkt_bekommt_leere_beschreibung(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Peter"}])

    figuren = repo.figuren(conn, 1)
    assert len(figuren) == 1
    assert figuren[0]["name"] == "Peter"
    assert figuren[0]["beschreibung"] == ""
    assert wirkliche == [{"art": "figur_setzen", "wert": "Peter"}]


def test_figur_gleicher_name_und_gleiche_beschreibung_gilt_nicht_als_aenderung(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}]
    )

    assert wirkliche == []


def test_verworfen_landet_im_journal_nicht_im_arbeitsstand(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]
    )

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "verworfen"
    assert eintraege[0]["text"] == "Zeitreise-Idee — zu teuer"
    assert eintraege[0]["quelle"] == "erkenner"
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert wirkliche == [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]


def test_entschieden_landet_im_journal(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "entschieden", "wert": "6 Interviewfragen"}])

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "entschieden"
    assert eintraege[0]["quelle"] == "erkenner"


def test_leerer_wert_wird_uebersprungen(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "   "}]
    )

    assert wirkliche == []
    assert repo.hole_arbeitsstand(conn, 1) is None


def test_wortlaut_an_setzt_modus_auf_namen(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "wortlaut_an", "wert": "Maria"}]
    )

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "Maria"
    assert wirkliche == [{"art": "wortlaut_an", "wert": "Maria"}]


def test_wortlaut_an_leerer_wert_setzt_stern(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_an", "wert": ""}])

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "*"
    assert wirkliche == [{"art": "wortlaut_an", "wert": "*"}]


def test_wortlaut_aus_setzt_modus_auf_none(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_an", "wert": "Maria"}])

    erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_aus", "wert": ""}])

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_interview_benennen_benennt_letzte_aufnahme(conn, einst):
    repo.lege_aufnahme_an(conn, 1, 1, "kurz", "sprache")
    zweite_id = repo.lege_aufnahme_an(conn, 1, 2, "kurz", "sprache")

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "interview_benennen", "wert": "Maria"}]
    )

    umbenannt = repo.hole_aufnahme(conn, zweite_id)
    assert umbenannt["name"] == "Maria"
    assert wirkliche == [{"art": "interview_benennen", "wert": "Maria"}]


def test_interview_starten_und_beenden_werden_uebersprungen(conn, einst):
    wirkliche = erkenner.wende_an(
        conn,
        einst,
        1,
        [
            {"art": "interview_starten", "wert": ""},
            {"art": "interview_beenden", "wert": ""},
        ],
    )

    assert wirkliche == []


def test_eine_fehlerhafte_aenderung_reisst_die_anderen_nicht_mit(conn, einst):
    wirkliche = erkenner.wende_an(
        conn,
        einst,
        1,
        [
            {"art": "kernthema_setzen", "wert": "Ankommen"},
            {"art": "figur_setzen", "wert": 12345},  # kein String -> .strip() kracht
            {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"},
        ],
    )

    assert {"art": "kernthema_setzen", "wert": "Ankommen"} in wirkliche
    assert {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"} in wirkliche
    assert len(wirkliche) == 2
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None

"""Der Richter: Anforderungstext, Parsing, Klemmen, Fehlerhaltung -- ohne Netz."""

import pytest

from simulation import claude, richter


class SimAttrappe:
    """Liefert, was ihr vorgegeben wird, und merkt sich den Aufruf."""

    modell = "claude-opus-5"

    def __init__(self, antwort):
        self.antwort = antwort
        self.gesehen = []

    def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
        self.gesehen.append({"art": art, "nutzer": nutzer, "system": system,
                             "max_tokens": max_tokens})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


VOLLSTAENDIG = {
    "geht_auf_gesagtes_ein": 2,
    "bietet_an_statt_vorzuschreiben": 1,
    "phase_transparent": 0,
    "korrektur_angenommen": 2,
    "satz": "Der Bot hat den Vorschlag nicht zurueckgenommen.",
    "zustimmungen": ["S3", " S7 ", ""],
    "schlechteste_antwort": "Jetzt formuliert ihr drei Fragen.",
    "begruendung": "Anweisung statt Angebot.",
}


def test_schema_ist_strikt_und_flach():
    """Das Schema erzwingt hier nichts mehr (der Proxy kennt keinen
    Schema-Modus), aber es bleibt die eine Quelle fuer den Anforderungstext --
    und dafuer muss es vollstaendig sein."""
    for schema in (richter.SCHEMA, richter.SZENEN_SCHEMA):
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_anforderung_nennt_jedes_feld_des_schemas():
    """Ein Feld, das im Schema steht und nicht im Anforderungstext, kaeme nie
    zurueck -- und stuende im Bericht als unerklaerlicher Strich."""
    text = richter.anforderung(richter.SCHEMA)
    for name in richter.SCHEMA["required"]:
        assert f'"{name}"' in text
    assert "JSON" in text


def test_prompt_wird_aus_der_prompt_datei_geladen():
    text = richter.prompt()
    assert "geht_auf_gesagtes_ein" in text
    assert "zustimmungen" in text


def test_bewerte_abschnitt_liest_noten_und_zustimmungen():
    sim = SimAttrappe(VOLLSTAENDIG)
    urteil = richter.bewerte_abschnitt(sim, "Fragen", "Ziel", "Bot: ...")
    assert urteil["geht_auf_gesagtes_ein"] == 2
    assert urteil["phase_transparent"] == 0
    assert urteil["zustimmungen"] == ["S3", "S7"]
    assert urteil["fehler"] is None
    assert sim.gesehen[0]["art"] == richter.ART
    assert sim.gesehen[0]["system"] == richter.prompt()


def test_noten_werden_auf_null_bis_zwei_geklemmt():
    sim = SimAttrappe({**VOLLSTAENDIG, "geht_auf_gesagtes_ein": 7,
                       "phase_transparent": -3, "korrektur_angenommen": "zwei"})
    urteil = richter.bewerte_abschnitt(sim, "T", "Z", "A")
    assert urteil["geht_auf_gesagtes_ein"] == 2
    assert urteil["phase_transparent"] == 0
    assert urteil["korrektur_angenommen"] == 0


def test_fehlende_felder_kippen_den_abschnitt_nicht():
    urteil = richter.bewerte_abschnitt(SimAttrappe({}), "T", "Z", "A")
    assert all(urteil[k] == 0 for k in richter.KRITERIEN)
    assert urteil["zustimmungen"] == []


def test_ein_modellfehler_liefert_ein_leeres_urteil():
    sim = SimAttrappe(claude.ClaudeFehler("Antwort ist kein JSON-Objekt"))
    urteil = richter.bewerte_abschnitt(sim, "Fragen", "Ziel", "A")
    assert all(urteil[k] is None for k in richter.KRITERIEN)
    assert "Nicht bewertet" in urteil["satz"]
    assert richter.summe(urteil) is None


def test_nutzertext_stellt_das_ziel_vor_den_wortlaut():
    text = richter.baue_nutzertext("Fragen", "Ihr wollt sechs Fragen.", "Bot: hallo")
    assert text.index("Ihr wollt sechs Fragen.") < text.index("Bot: hallo")


def test_nutzertext_endet_mit_der_json_anforderung():
    """Was am Ende des Prompts steht, wiegt am schwersten -- und die Form der
    Antwort ist das Einzige, was hier ohne Schema-Modus durchgesetzt wird."""
    text = richter.baue_nutzertext("T", "Z", "Bot: hallo")
    assert text.index("Bot: hallo") < text.index("JSON")


def test_leerer_abschnitt_wird_benannt():
    assert "(keine Nachrichten" in richter.baue_nutzertext("T", "Z", "   ")


def test_szene_wird_nur_bei_vorhandenem_text_bewertet():
    sim = SimAttrappe({"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 1,
                       "satz": "geht so"})
    assert richter.bewerte_szene(sim, "Planung", "") == {}
    assert sim.gesehen == []

    urteil = richter.bewerte_szene(sim, "Planung", "MERYEM: Hallo.")
    assert urteil["stimmen_unterscheidbar"] == 1
    assert "szene_stimmt_zur_planung" in sim.gesehen[0]["nutzer"]


def test_summe_und_markierte_zustimmungen():
    a = richter.bewerte_abschnitt(SimAttrappe(VOLLSTAENDIG), "A", "Z", "x")
    b = richter.bewerte_abschnitt(
        SimAttrappe({**VOLLSTAENDIG, "zustimmungen": ["S9"]}), "B", "Z", "x"
    )
    assert richter.summe(a) == 5
    assert richter.markierte_zustimmungen({"a": a, "b": b}) == {"S3", "S7", "S9"}

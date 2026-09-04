"""Der Richter: Schema, Parsing, Klemmen, Fehlerhaltung -- ohne Netz."""

import pytest

from interview_theater import llm
from simulation import richter


class _E:
    erkenner_modell = "google/gemma-4-31B-it"


class KLM:
    """Liefert, was ihr vorgegeben wird, und merkt sich den Aufruf."""

    def __init__(self, antwort):
        self.antwort = antwort
        self.gesehen = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self.gesehen.append({"art": art, "modell": modell, "nutzer": nutzer,
                             "schema": schema})
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
    """Jedes Objekt braucht additionalProperties:false und ein required mit
    allen Eigenschaften, sonst lehnt Infomaniak den erzwungenen Modus ab."""
    for schema in (richter.SCHEMA, richter.SZENEN_SCHEMA):
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_prompt_wird_aus_der_prompt_datei_geladen():
    text = richter.prompt()
    assert "geht_auf_gesagtes_ein" in text
    assert "zustimmungen" in text


def test_bewerte_abschnitt_liest_noten_und_zustimmungen():
    klm = KLM(VOLLSTAENDIG)
    urteil = richter.bewerte_abschnitt(klm, _E(), "Fragen", "Ziel", "Bot: ...")
    assert urteil["geht_auf_gesagtes_ein"] == 2
    assert urteil["phase_transparent"] == 0
    assert urteil["zustimmungen"] == ["S3", "S7"]
    assert urteil["fehler"] is None
    assert klm.gesehen[0]["art"] == richter.ART
    assert klm.gesehen[0]["modell"] == "google/gemma-4-31B-it"


def test_noten_werden_auf_null_bis_zwei_geklemmt():
    klm = KLM({**VOLLSTAENDIG, "geht_auf_gesagtes_ein": 7,
               "phase_transparent": -3, "korrektur_angenommen": "zwei"})
    urteil = richter.bewerte_abschnitt(klm, _E(), "T", "Z", "A")
    assert urteil["geht_auf_gesagtes_ein"] == 2
    assert urteil["phase_transparent"] == 0
    assert urteil["korrektur_angenommen"] == 0


def test_fehlende_felder_kippen_den_abschnitt_nicht():
    urteil = richter.bewerte_abschnitt(KLM({}), _E(), "T", "Z", "A")
    assert all(urteil[k] == 0 for k in richter.KRITERIEN)
    assert urteil["zustimmungen"] == []


def test_ein_modellfehler_liefert_ein_leeres_urteil():
    klm = KLM(llm.LLMFehler("Sprachmodell lehnte den Aufruf ab: HTTP 502"))
    urteil = richter.bewerte_abschnitt(klm, _E(), "Fragen", "Ziel", "A")
    assert all(urteil[k] is None for k in richter.KRITERIEN)
    assert "Nicht bewertet" in urteil["satz"]
    assert richter.summe(urteil) is None


def test_nutzertext_stellt_das_ziel_vor_den_wortlaut():
    text = richter.baue_nutzertext("Fragen", "Ihr wollt sechs Fragen.", "Bot: hallo")
    assert text.index("Ihr wollt sechs Fragen.") < text.index("Bot: hallo")


def test_leerer_abschnitt_wird_benannt():
    assert "(keine Nachrichten" in richter.baue_nutzertext("T", "Z", "   ")


def test_szene_wird_nur_bei_vorhandenem_text_bewertet():
    klm = KLM({"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 1,
               "satz": "geht so"})
    assert richter.bewerte_szene(klm, _E(), "Planung", "") == {}
    assert klm.gesehen == []

    urteil = richter.bewerte_szene(klm, _E(), "Planung", "MERYEM: Hallo.")
    assert urteil["stimmen_unterscheidbar"] == 1
    assert klm.gesehen[0]["schema"] is richter.SZENEN_SCHEMA


def test_summe_und_markierte_zustimmungen():
    a = richter.bewerte_abschnitt(KLM(VOLLSTAENDIG), _E(), "A", "Z", "x")
    b = richter.bewerte_abschnitt(
        KLM({**VOLLSTAENDIG, "zustimmungen": ["S9"]}), _E(), "B", "Z", "x"
    )
    assert richter.summe(a) == 5
    assert richter.markierte_zustimmungen({"a": a, "b": b}) == {"S3", "S7", "S9"}

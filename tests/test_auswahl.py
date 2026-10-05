"""auswahl.fragen_liste: die Fragen der Auswahl je Begriff, mit Herkunft und
Zustand, fuer die Sortierliste im CoThinker (Padua, 05.10.2026)."""

from interview_theater import auswahl


def _stand(**kw):
    basis = {"begriffe": None, "fragen_auswahl": None,
             "fragen_herkunft": None, "fragen_entschieden": None}
    basis.update(kw)
    return basis


def test_leer():
    leer = {"gruppen": [], "zaehler": {"ja": 0, "nein": 0, "schaerfen": 0, "offen": 0}}
    assert auswahl.fragen_liste(_stand()) == leer
    assert auswahl.fragen_liste(_stand(begriffe="Casa", fragen_auswahl="")) == leer


def test_gruppen_in_begriffsreihenfolge_und_ausrichtung():
    stand = _stand(
        begriffe="Casa, Amore",
        fragen_auswahl="Amore: Che cos'è l'amore?\nCasa: Dove ti senti a casa?\n"
                       "**Casa**: Cosa manca?\nUna domanda senza begriff?",
        fragen_herkunft="eigen,ki,eigen,ki",
        fragen_entschieden="ja,schaerfen",
    )
    erg = auswahl.fragen_liste(stand)
    assert [g["titel"] for g in erg["gruppen"]] == ["Casa", "Amore", ""]
    casa = erg["gruppen"][0]["eintraege"]
    assert casa == [
        {"nummer": 2, "text": "Dove ti senti a casa?", "herkunft": "ki", "zustand": "schaerfen"},
        {"nummer": 3, "text": "Cosa manca?", "herkunft": "eigen", "zustand": ""},
    ]
    assert erg["gruppen"][1]["eintraege"] == [
        {"nummer": 1, "text": "Che cos'è l'amore?", "herkunft": "eigen", "zustand": "ja"},
    ]
    assert erg["gruppen"][2]["eintraege"][0]["nummer"] == 4
    assert erg["gruppen"][2]["eintraege"][0]["text"] == "Una domanda senza begriff?"
    assert erg["zaehler"] == {"ja": 1, "nein": 0, "schaerfen": 1, "offen": 2}


def test_begriff_mit_doppelpunkt():
    stand = _stand(
        begriffe="EVENTO: dall'esterno all'interno\nCasa",
        fragen_auswahl="EVENTO: dall'esterno all'interno: Che cosa …?\nCasa: Dove?",
    )
    erg = auswahl.fragen_liste(stand)
    assert erg["gruppen"][0]["titel"] == "EVENTO: dall'esterno all'interno"
    assert erg["gruppen"][0]["eintraege"][0]["text"] == "Che cosa …?"
    assert erg["gruppen"][1]["titel"] == "Casa"


def test_begriff_mit_doppelpunkt_und_typografischem_apostroph():
    # Live G3, 05.10.2026: der Begriff steht mit ’, die Fragen mit '.
    stand = _stand(
        begriffe="EVENTO: dall’esterno all’interno",
        fragen_auswahl="EVENTO: dall'esterno all'interno: Dov'eri l'11 settembre 2001?",
    )
    erg = auswahl.fragen_liste(stand)
    assert erg["gruppen"][0]["titel"] == "EVENTO: dall’esterno all’interno"
    assert erg["gruppen"][0]["eintraege"][0]["text"] == "Dov'eri l'11 settembre 2001?"


def test_fremder_kopf_bekommt_eigene_gruppe():
    # Live G3: KI-Fragen zu einem Begriff, den die Gruppe nicht (mehr) hat.
    stand = _stand(
        begriffe="Casa",
        fragen_auswahl="Casa: Dove?\nricordi personali: Quale notizia ricordi?\nNiente?",
    )
    erg = auswahl.fragen_liste(stand)
    assert [g["titel"] for g in erg["gruppen"]] == ["Casa", "ricordi personali", ""]
    assert erg["gruppen"][1]["eintraege"][0]["text"] == "Quale notizia ricordi?"


def test_zaehler_fehlende_und_leere_sind_offen():
    stand = _stand(begriffe="A", fragen_auswahl="A: x?\nA: y?\nA: z?\nA: w?",
                   fragen_entschieden="nein,,schaerfen")
    assert auswahl.fragen_liste(stand)["zaehler"] == {
        "ja": 0, "nein": 1, "schaerfen": 1, "offen": 2}


def test_unbekannter_zustand_gilt_als_offen():
    stand = _stand(begriffe="A", fragen_auswahl="A: x?", fragen_entschieden="vielleicht")
    erg = auswahl.fragen_liste(stand)
    assert erg["gruppen"][0]["eintraege"][0]["zustand"] == ""
    assert erg["zaehler"]["offen"] == 1


def test_langer_begriff_ueber_60_zeichen():
    # Live G2, 05.10.2026: ein Begriff mit 78 Zeichen fiel in die Gruppe "".
    lang = "impatto della tecnologia sulle relazioni interpersonali e sulla comunicazione"
    stand = _stand(begriffe=f"{lang}, amore",
                   fragen_auswahl=f"{lang}: I social ti avvicinano?\namore: Cos'è?")
    erg = auswahl.fragen_liste(stand)
    assert erg["gruppen"][0]["titel"] == lang
    assert erg["gruppen"][0]["eintraege"][0]["text"] == "I social ti avvicinano?"

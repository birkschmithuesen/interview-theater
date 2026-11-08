from interview_theater import stueck_sicht as sicht


def test_karte_ansicht_ignoriert_struktur_aus_dem_json():
    roh = {"typ": "spoken", "worum": "w", "ort": "GIFT", "wer": "GIFT", "fragen": ["GIFT?"],
           "punkte": ["p", "[OPEN] GIFT"], "zitate": []}
    k = sicht.karte_ansicht(roh, ort="Piazza", besetzung=[("Anna", "(Arlecchino)")],
                            zusatz="tutto il pubblico", fragen_offen=["Wo?"],
                            fragen_vertagt=["Wann?"])
    assert k["ort"] == "Piazza"
    assert k["wer"] == "Anna (Arlecchino), tutto il pubblico"
    assert k["fragen"] == ["Wo?"]
    assert k["punkte"] == ["p", "[OPEN] Wann?"]
    assert "GIFT" not in repr(k)


def test_ohne_karte_keine_ansicht():
    assert sicht.karte_ansicht(None, ort="x", besetzung=[], zusatz=None,
                               fragen_offen=[], fragen_vertagt=[]) is None


def test_ordne_besetzung_rolle_und_rest():
    figuren = {"anna": 1, "pietro": 2, "francesco": 3}
    eintraege, rest = sicht.ordne_besetzung(
        "Anna (Arlecchino), Pietro; Francesco fuori campo e tutto il pubblico", figuren)
    assert eintraege == [(1, "(Arlecchino)"), (2, None), (3, "fuori campo")]
    assert rest == ["tutto il pubblico"]


def test_ordne_besetzung_kein_teiltreffer():
    eintraege, rest = sicht.ordne_besetzung("Annabella", {"anna": 1})
    assert eintraege == [] and rest == ["Annabella"]


def test_offen_punkt():
    assert sicht.OFFEN_PUNKT.match("[OPEN] Wer spielt?").group(1) == "Wer spielt?"
    assert sicht.OFFEN_PUNKT.match("[APERTO]: Chi?").group(1) == "Chi?"
    assert sicht.OFFEN_PUNKT.match("Kein [OPEN] hier") is None

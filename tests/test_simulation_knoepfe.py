"""Der Knopf-Weg der Simulation (06.09.2026).

Der Bot fuehrt seit dem Umbau ueber Inline-Knoepfe. Diese Tests halten fest,
dass der Simulator sie **sieht** (Attrappe), sie einer Stimme **anbietet**
(Prompt), eine Knopfwahl **erkennt** und sie in Kennzahlen **zaehlt**. Kein
Netz, kein Modell.
"""

from __future__ import annotations

from simulation import kennzahlen, skript, stimmen
from simulation.attrappe import TelegramAttrappe
from simulation.kennzahlen import Beitrag, Zug


# --- Attrappe --------------------------------------------------------------


def test_attrappe_merkt_die_leiste_und_gibt_offene_knoepfe():
    tg = TelegramAttrappe()
    tg.sende(1, "ohne Knoepfe")
    mid = tg.sende_mit_knoepfen(1, "Vorschlag", [("Passt", "k:7"), ("Nein", "k:8")])
    offen = tg.offene_knoepfe()
    assert [k["beschriftung"] for k in offen] == ["Passt", "Nein"]
    assert all(k["message_id"] == mid for k in offen)
    assert offen[0]["text"] == "Vorschlag"


def test_entfernte_tastatur_ist_nicht_mehr_antippbar():
    tg = TelegramAttrappe()
    mid = tg.sende_mit_knoepfen(1, "Vorschlag", [("Passt", "k:7")])
    tg.entferne_knoepfe(1, mid)
    assert tg.offene_knoepfe() == []


def test_aktualisierte_tastatur_ersetzt_die_alte():
    """Der Toggle der Fragenauswahl tauscht die Tastatur derselben Nachricht.

    Ohne diese Methode faellt ``knoepfe._toggle_frage`` in seinen
    ``except``-Zweig: die Haken werden nie sichtbar, und die Stimme waehlt
    gegen eine Tastatur, die es so nie gab."""
    tg = TelegramAttrappe()
    mid = tg.sende_mit_knoepfen(1, "Waehlt drei", [("1 Frage", "k:1")])
    tg.aktualisiere_knoepfe(1, mid, [("✓ 1 Frage", "k:1"), ("2 Frage", "k:2")])
    assert [k["beschriftung"] for k in tg.offene_knoepfe()] == \
        ["✓ 1 Frage", "2 Frage"]


def test_juengste_nachricht_zuerst():
    tg = TelegramAttrappe()
    tg.sende_mit_knoepfen(1, "alt", [("Alt", "k:1")])
    tg.sende_mit_knoepfen(1, "neu", [("Neu", "k:2")])
    assert tg.offene_knoepfe()[0]["beschriftung"] == "Neu"


# --- Die Stimme sieht und waehlt -------------------------------------------


def _person():
    return stimmen.aus_steckbrief(stimmen.TAG1[0])


def test_knopftexte_stehen_im_nutzertext_einer_stimme():
    knoepfe = [{"beschriftung": "Gefaellt uns, weiter"},
               {"beschriftung": "Passt, aber anders"}]
    text = stimmen.baue_nutzertext(_person(), [], "Ziel", knoepfe)
    assert "Gefaellt uns, weiter" in text
    assert "Passt, aber anders" in text
    assert stimmen.KNOPF_PRAEFIX in text


def test_ohne_knoepfe_steht_keine_knopfanweisung_im_prompt():
    text = stimmen.baue_nutzertext(_person(), [], "Ziel", [])
    assert stimmen.KNOPF_PRAEFIX not in text


def test_knopfliste_entfernt_dubletten_und_deckelt():
    viele = [{"beschriftung": "Weiter"}] * 3 + [
        {"beschriftung": f"K{n}"} for n in range(50)
    ]
    liste = stimmen.knopfliste(viele)
    assert liste[0] == "Weiter"
    assert len(liste) <= stimmen.MAX_KNOEPFE
    assert len(liste) == len(set(liste))


def test_knopfwahl_wird_exakt_und_unscharf_erkannt():
    knoepfe = [{"beschriftung": "Gefaellt uns, weiter", "daten": "k:3"}]
    assert stimmen.lies_knopfwahl(
        "KNOPF: Gefaellt uns, weiter", knoepfe)["daten"] == "k:3"
    assert stimmen.lies_knopfwahl(
        'KNOPF: "Gefaellt uns, weiter"', knoepfe)["daten"] == "k:3"


def test_freitext_ist_keine_knopfwahl():
    knoepfe = [{"beschriftung": "Weiter", "daten": "k:3"}]
    assert stimmen.lies_knopfwahl("passt so, weiter", knoepfe) is None
    assert stimmen.lies_knopfwahl("KNOPF:", knoepfe) is None


def test_erfundener_knopftext_wird_nicht_geraten():
    """Trifft kein Knopf, ist das kein Druck -- der Aufrufer schickt dann
    Text. Raten waere schlimmer als nichts: die Simulation drueckte einen
    Knopf, den die Stimme nie gemeint hat."""
    knoepfe = [{"beschriftung": "Weiter", "daten": "k:3"}]
    assert stimmen.lies_knopfwahl("KNOPF: Alles loeschen", knoepfe) is None


# --- Die neuen Kennzahlen --------------------------------------------------


def _zug(bot, beitraege=(), marke=""):
    return Zug(
        schritt="s", marke=marke, bot=list(bot),
        beitraege=[Beitrag(f"S{n}", "s", "A", "p", t)
                   for n, t in enumerate(beitraege)],
    )


def test_fragen_je_botnachricht_zaehlt_fragezeichen_nicht_nachrichten():
    zuege = [_zug(["Wer? Wo? Wann?", "Gut."])]
    assert kennzahlen.fragen_je_botnachricht(zuege) == 1.5


def test_nachrichten_je_festlegung_zaehlt_bis_zur_notiert_zeile():
    notiert = kennzahlen.NOTIERT + " Begriffe: X"
    zuege = [
        _zug(["Und?"], beitraege=["hallo"]),
        _zug(["Und?"], beitraege=["noch was"]),
        _zug([notiert], beitraege=["ja"]),
    ]
    lage = kennzahlen.nachrichten_je_festlegung(zuege)
    assert lage["festlegungen"] == 1
    assert lage["nachrichten_je_festlegung"] == [3]


def test_knopfdruck_zaehlt_wie_eine_nachricht():
    notiert = kennzahlen.NOTIERT + " Begriffe: X"
    zuege = [_zug([], marke="knopf"), _zug([notiert])]
    assert kennzahlen.nachrichten_je_festlegung(zuege)[
        "nachrichten_je_festlegung"] == [1]


def test_knopflage_zaehlt_angeboten_gegen_gedrueckt():
    tg = TelegramAttrappe()
    tg.sende_mit_knoepfen(1, "a", [("X", "k:1"), ("Y", "k:2")])
    lage = kennzahlen.knopflage(tg, [{"beschriftung": "X"}])
    assert lage["knoepfe_angeboten"] == 2
    assert lage["knoepfe_gedrueckt"] == 1
    assert lage["knoepfe_quote"] == 0.5


def test_phasenlage_meldet_den_notweg_als_befund():
    lage = kennzahlen.phasenlage([2, 3], [4])
    assert lage["phasenwechsel_selbst"] == [4]
    assert lage["phasenwechsel_proaktiv_anteil"] == 0.67


def test_parallel_zum_auftrag_zaehlt_nur_die_zweite_antwort():
    zuege = [_zug(["Ich schreibe.", "Und was soll rein?"], marke="szene_aufruf")]
    assert kennzahlen.parallel_zum_auftrag(zuege) == ["Und was soll rein?"]


def test_ohne_auftragsmarke_gibt_es_keine_parallelrede():
    zuege = [_zug(["eins", "zwei", "drei"])]
    assert kennzahlen.parallel_zum_auftrag(zuege) == []


# --- Das Skript der sieben Phasen --------------------------------------------


def test_das_tag2_skript_faehrt_alle_sieben_phasen_an():
    """Sechs Phasenschritte fuer sieben Phasen: Phase 1 ist der Anfang, und
    zwischen Figuren und Geschichte gibt es seit dem 06.09.2026 keinen
    Wechsel mehr -- das ist EINE Station."""
    nummern = [s.phase_nummer for s in skript.SCHRITTE_TAG2 if s.art == "phase"]
    assert nummern == [2, 3, 4, 5, 6, 7]


def test_jeder_schritt_hat_eine_bekannte_art():
    for schritt in skript.SCHRITTE_TAG2:
        assert schritt.art in skript.ARTEN, schritt.schluessel


def test_die_alten_skripte_bleiben_unveraendert_lang():
    """``SCHRITTE`` und ``SCHRITTE_BIRK`` sind die Messlatte der Laeufe vom
    05.09. Wer sie umbaut, macht ``verlauf.jsonl`` unvergleichbar."""
    assert len(skript.SCHRITTE) == 10
    assert len(skript.SCHRITTE_BIRK) == 11

"""Validierung des Padua-Testsatzes (``korpus/padua_testsatz.jsonl``) --
ohne Netz, ohne Datenbank (InScribe Messung 1, t_dd94e894).

Der Testsatz zieht 37 echte Chat-Faelle aus den drei Padua-Gruppen, gegen
``p7audit.json`` gespiegelt (Doku im Commit, nicht hier). Diese Tests
pruefen zweierlei: die Form (Datenschutz E8, Mindestbesetzung -- wie
``tests/test_korpus.py`` es fuer ``korpus/erkenner.jsonl`` tut) und -- der
eigentliche Witz eines Testsatzes -- dass seine ``erwartet``-Sollwerte
tatsaechlich etwas pruefen: ein absichtlich verfaelschter Sollwert muss den
Vergleichslauf (``scripts.pruefe_prompts.vergleiche_erkenner``) rot machen.
Ohne diesen Mutationstest koennte der Testsatz voller Platzhalter stehen,
ohne dass es irgendein Lauf je merkt.
"""

import json
import re
from pathlib import Path

import pytest

from interview_theater import erkenner
from scripts import pruefe_prompts as pp

PFAD = Path(__file__).resolve().parent.parent / "korpus" / "padua_testsatz.jsonl"

MIN_FAELLE = 30
MIN_NEGATIV = 8
MIN_GRUPPEN = 3

#: Echte Vornamen aus den Figurentabellen der drei Gruppen (vor der
#: Anonymisierung) -- duerfen in keinem Fall mehr auftauchen (E8). Reale
#: numerische chat_ids (Padua: 13-stellig, Praefix 7000000000) ebenfalls nicht.
KLARNAMEN = ("Samuele", "Giona", "Emma", "Giada", "Anna", "Chicca", "Francesca",
             "Francesco", "Pietro", "Silvio", "Luca", "Maniero")
ECHTE_CHAT_ID_MUSTER = re.compile(r"\b7000000000\d{3}\b")


def lade():
    zeilen = PFAD.read_text(encoding="utf-8").splitlines()
    faelle = []
    for nummer, zeile in enumerate(zeilen, 1):
        assert zeile.strip(), f"padua_testsatz.jsonl:{nummer}: Leerzeile"
        try:
            faelle.append(json.loads(zeile))
        except json.JSONDecodeError as fehler:
            pytest.fail(f"padua_testsatz.jsonl:{nummer}: kein gueltiges JSON ({fehler})")
    return faelle


@pytest.fixture(scope="module")
def faelle():
    return lade()


# --- Form -------------------------------------------------------------

def test_mindestanzahl(faelle):
    assert len(faelle) >= MIN_FAELLE


def test_ids_sind_eindeutig(faelle):
    ids = [f["id"] for f in faelle]
    doppelte = {i for i in ids if ids.count(i) > 1}
    assert not doppelte, f"doppelte ids: {sorted(doppelte)}"


def test_jeder_fall_hat_id_notiz_und_herkunft(faelle):
    for fall in faelle:
        assert fall.get("id"), "Fall ohne id"
        assert fall.get("notiz", "").strip(), f"{fall['id']}: ohne notiz"
        herkunft = fall.get("herkunft")
        assert isinstance(herkunft, dict), f"{fall['id']}: ohne herkunft"
        assert herkunft.get("gruppe") in ("g1", "g2", "g3"), fall["id"]
        assert isinstance(herkunft.get("post_id"), int), fall["id"]


def test_pflichtfelder_wie_im_erkenner_korpus(faelle):
    """Dasselbe Format wie ``korpus/erkenner.jsonl``, damit derselbe Runner
    (``scripts.pruefe_prompts``) beide Dateien fahren kann."""
    for fall in faelle:
        assert isinstance(fall.get("arbeitsstand"), dict), fall["id"]
        assert isinstance(fall.get("erwartet"), list), fall["id"]
        assert isinstance(fall.get("nachrichten"), list) and fall["nachrichten"], fall["id"]
        for nachricht in fall["nachrichten"]:
            assert nachricht.get("absender"), fall["id"]
            assert nachricht.get("text"), fall["id"]


def test_arten_sind_bekannt(faelle):
    for fall in faelle:
        for aenderung in fall["erwartet"]:
            assert aenderung["art"] in erkenner.ARTEN, f"{fall['id']}: {aenderung['art']}"
            assert isinstance(aenderung.get("wert"), str), fall["id"]


def test_genug_negativfaelle(faelle):
    negativ = [f for f in faelle if not f["erwartet"]]
    assert len(negativ) >= MIN_NEGATIV


def test_alle_drei_gruppen_vertreten(faelle):
    gruppen = {f["herkunft"]["gruppe"] for f in faelle}
    assert len(gruppen) >= MIN_GRUPPEN


def test_mindestens_ein_belegtes_falsch_positiv(faelle):
    """Der eigentliche Zweck dieses Testsatzes: die Baseline-Messung braucht
    mindestens einen Fall, in dem die Produktion nachweislich etwas
    geschrieben hat, das die Gruppe nicht wollte."""
    fp = [f for f in faelle if f["herkunft"].get("erkenner_befund") == "fp"]
    assert fp, "kein belegtes Falsch-Positiv im Testsatz"
    for fall in fp:
        assert fall["erwartet"] == [], f"{fall['id']}: FP-Fall erwartet trotzdem etwas"


def test_mindestens_ein_belegter_miss(faelle):
    """Und mindestens einen Fall, in dem die Produktion eine klare Absicht
    NICHT angewendet hat (still verpasst)."""
    miss = [f for f in faelle if f["herkunft"].get("erkenner_befund") == "miss"]
    assert miss, "kein belegter Miss-Fall im Testsatz"
    for fall in miss:
        assert fall["erwartet"], f"{fall['id']}: Miss-Fall ohne Sollwert"


def test_keine_klarnamen(faelle):
    """E8: Figurennamen aus den Padua-Gruppen (vor der Anonymisierung)
    duerfen nirgends mehr im Testsatz stehen -- auch nicht versteckt in
    notiz oder herkunft."""
    for fall in faelle:
        blob = json.dumps(fall, ensure_ascii=False)
        treffer = [n for n in KLARNAMEN if re.search(r"\b" + re.escape(n) + r"\b", blob, re.IGNORECASE)]
        assert not treffer, f"{fall['id']}: Klarname(n) {treffer}"


def test_keine_echten_chat_ids(faelle):
    for fall in faelle:
        blob = json.dumps(fall, ensure_ascii=False)
        assert not ECHTE_CHAT_ID_MUSTER.search(blob), f"{fall['id']}: echte chat_id im Testsatz"


def test_anonymisierte_figuren_sind_platzhalter(faelle):
    """Figurennamen in den anonymisierten Faellen folgen dem Muster
    'Figur-<Buchstabe>' -- kein Wiedereinschleichen eines echten Namens unter
    anderer Schreibweise waere an diesem Muster jedenfalls nicht zu sehen,
    aber die Form selbst muss stimmen."""
    muster = re.compile(r"Figur-[A-Z]\b")
    treffer = [f["id"] for f in faelle if muster.search(json.dumps(f, ensure_ascii=False))]
    assert treffer, "kein Fall nutzt das Figur-Platzhaltermuster -- Anonymisierung ueberhaupt wirksam?"


# --- Mutationstest ------------------------------------------------------
#
# Der eigentliche Nachweis, dass der Testsatz etwas misst: ein Lauf, der
# GENAU das liefert, was ``erwartet`` vorgibt, ist tadellos (FP=FN=0). Wird
# der Sollwert im Testsatz danach absichtlich verfaelscht -- derselbe
# gelieferte Wert bleibt unveraendert -- muss derselbe Vergleich jetzt eine
# Abweichung zeigen. Sonst koennte ``erwartet`` leeres Rauschen sein, ohne
# dass es ein Lauf je merkt.

def test_mutation_an_einem_positivfall_macht_den_vergleich_rot(faelle):
    positiv = next(f for f in faelle if f["erwartet"])
    geliefert = [dict(e) for e in positiv["erwartet"]]

    sauber = pp.vergleiche_erkenner(positiv["erwartet"], geliefert)
    assert not sauber["fehlend"] and not sauber["ueberzaehlig"], (
        "Ausgangslage muss sauber sein, bevor mutiert wird"
    )

    # Nicht anhaengen: ``wert_passt`` prueft Teilstring in beide Richtungen
    # (korpus/erkenner.jsonl-Konvention), ein blosses Suffix bliebe also ein
    # Treffer. Der Sollwert muss durch etwas OHNE Teilstring-Beziehung
    # ersetzt werden, um wirklich etwas anderes zu behaupten.
    mutiert = [dict(e, wert="UNZUSAMMENHAENGENDE-MUTATION-9f3a") for e in positiv["erwartet"]]
    ergebnis = pp.vergleiche_erkenner(mutiert, geliefert)
    assert ergebnis["fehlend"] or ergebnis["ueberzaehlig"], (
        f"{positiv['id']}: ein verfaelschter Sollwert haette den Vergleich "
        "rot machen muessen, tat es aber nicht"
    )


def test_mutation_an_einem_negativfall_macht_den_vergleich_rot(faelle):
    negativ = next(f for f in faelle if not f["erwartet"])
    geliefert = []

    sauber = pp.vergleiche_erkenner(negativ["erwartet"], geliefert)
    assert not sauber["fehlend"] and not sauber["ueberzaehlig"]

    mutiert = [{"art": "kernthema_setzen", "wert": "erfundene Mutation"}]
    ergebnis = pp.vergleiche_erkenner(mutiert, geliefert)
    assert ergebnis["fehlend"], (
        f"{negativ['id']}: ein untergeschobener Sollwert haette als "
        "fehlend auffallen muessen"
    )


def test_mutation_an_der_art_macht_den_vergleich_rot(faelle):
    """Nicht nur der ``wert`` ist load-bearing -- auch eine vertauschte
    ``art`` muss auffallen (der Nemotron-Fehler aus dem Haupt-Korpus: FP und
    FN zugleich)."""
    positiv = next(f for f in faelle if f["erwartet"] and f["erwartet"][0]["art"] != "kernthema_setzen")
    geliefert = [dict(e) for e in positiv["erwartet"]]
    mutiert = [dict(e, art="kernthema_setzen") for e in positiv["erwartet"]]
    ergebnis = pp.vergleiche_erkenner(mutiert, geliefert)
    assert ergebnis["fehlend"] and ergebnis["ueberzaehlig"], positiv["id"]

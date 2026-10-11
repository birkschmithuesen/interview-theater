"""Validierung des Padua-Testsatzes (``betrieb/korpus/en/padua_testsatz.jsonl``)
-- ohne Netz, ohne Datenbank (InScribe Messung 1, t_dd94e894/t_941bfc86).

Der Testsatz zieht 37 echte Chat-Faelle aus den drei Padua-Gruppen, gegen
``p7audit.json`` gespiegelt (Doku im Commit, nicht hier). Diese Tests
pruefen zweierlei: die Form (Datenschutz E8, Mindestbesetzung -- wie
``tests/test_korpus.py`` es fuer ``korpus/erkenner.jsonl`` tut) und -- der
eigentliche Witz eines Testsatzes -- dass seine ``erwartet``-Sollwerte
tatsaechlich etwas pruefen: ein absichtlich verfaelschter Sollwert muss den
Vergleichslauf (``scripts.pruefe_prompts.vergleiche_erkenner``) rot machen.
Ohne diesen Mutationstest koennte der Testsatz voller Platzhalter stehen,
ohne dass es irgendein Lauf je merkt.

Die Datei enthaelt echte Chat-Zitate (vor der Anonymisierung Teil davon
Klarnamen) und darf deshalb nicht im oeffentlichen Repo liegen (E8) -- sie
liegt unter ``IT_PRIVAT_KORPUS``/``betrieb/korpus/`` (``scripts.pruefe_prompts
.PRIVATE_KORPUS_DATEIEN``) und fehlt in einem frischen Checkout bewusst. Die
Tests hier, die die echte Datei brauchen, ueberspringen sich dann selbst;
``test_synthetische_mini_fixture_*`` deckt dieselbe Pruefungslogik mit frei
erfundenen Faellen ab, damit sie nicht ungetestet bleibt.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from interview_theater import erkenner
from scripts import pruefe_prompts as pp

#: Unter betrieb/korpus/en/, nicht im Repo (E8): die Faelle sind Padua-
#: Realitaet (Englisch-Profil, Gruppennachrichten italienisch/englisch) und
#: muessen ueber ``--sprache en`` denselben Pfad nehmen wie
#: ``korpus/en/erkenner.jsonl`` -- sonst lehnt ``scripts.pruefe_prompts.main``
#: den Lauf unter IT_WORKSHOP=padua-2026 als Sprachmismatch ab (D8-Pruefung).
PFAD = pp.privat_korpus_wurzel() / "en" / "padua_testsatz.jsonl"

MIN_FAELLE = 30
MIN_NEGATIV = 8
MIN_GRUPPEN = 3

#: Echte Vornamen aus den Figurentabellen der drei Gruppen (vor der
#: Anonymisierung) duerfen in keinem Fall mehr auftauchen (E8) -- auch nicht
#: im Testcode selbst. Statt der Klarnamen stehen hier ihre SHA-256-Hashes
#: (kleingeschrieben vor dem Hashen); ``test_keine_klarnamen`` hasht jedes
#: Wort aus dem Testsatz und vergleicht nur die Hashes.
KLARNAMEN_HASHES = frozenset({
    "6c1bdfb0f1ec46ffd6ddb972d02049c9d2168515bd9fd23c7eda144607891b5f",  # Name 1
    "1ed2f6a8a38962318ae4c1ecd27fc1492e92bace368f4bbb12cdd8a2f64b9222",  # Name 2
    "f4aa0655cdb8d4fcf6f719c7a786de10556783c70bfb8ef1d78923482fe6ebbc",  # Name 3
    "e7356c5332a3dc172307d7d27b86c3b852b08334cbf292d93965c4566ffacf99",  # Name 4
    "55579b557896d0ce1764c47fed644f9b35f58bad620674af23f356d80ed0c503",  # Name 5
    "c8b503c9f7396e8154f8205e43b5b481bfcd8123325035ef315f13317b4266e1",  # Name 6
    "5dfd46e27a5e3e8e06fcb92817b0955f7fd28048f5003bfd4e5be8e67bf417db",  # Name 7
    "a2cab1deca58c8353168310f520c3bb7e45466e6722d771bed19126077b58703",  # Name 8
    "09c12d01508bb6b857cf2f84199fb3134b58985806b40d6440a1acf453b2e106",  # Name 9
    "c5099a6000c2be06c62bd9ca2dd25526efb177e0d7193746a2a163f7f4f48947",  # Name 10
    "d70f47790f689414789eeff231703429c7f88a10210775906460edbf38589d90",  # Name 11
    "28d976388f223162eece5bd9dff2745b5d3e0c4f4e7374ec964a0527d596f462",  # Name 12
})
ECHTE_CHAT_ID_MUSTER = re.compile(r"\b7000000000\d{3}\b")

#: Jede Hex-Kette oben muss 64 Zeichen lang sein (sha256.hexdigest()) --
#: eine versehentlich verstuemmelte Konstante waere sonst ein stiller
#: Nie-Treffer statt eines Fehlers.
assert all(len(h) == 64 for h in KLARNAMEN_HASHES)


def _woerter(blob: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", blob)


def _klarnamen_treffer(fall: dict, hashes: frozenset = KLARNAMEN_HASHES) -> list[str]:
    """Worthashes aus ``fall`` gegen ``hashes`` (Vorgabe ``KLARNAMEN_HASHES``)
    -- liefert die (noch gehashten) Treffer, nicht die Klarnamen selbst."""
    blob = json.dumps(fall, ensure_ascii=False)
    return [
        w for w in _woerter(blob)
        if hashlib.sha256(w.lower().encode("utf-8")).hexdigest() in hashes
    ]


def lade():
    if not PFAD.exists():
        pytest.skip(f"private Datei fehlt: {PFAD}")
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
    notiz oder herkunft. Der Vergleich laeuft ueber SHA-256-Hashes, nicht
    ueber die Klarnamen selbst (die stehen nicht im Testcode)."""
    for fall in faelle:
        treffer = _klarnamen_treffer(fall)
        assert not treffer, f"{fall['id']}: Klarname(n) (Hash-Treffer) {treffer}"


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


# --- Synthetische Mini-Fixture ------------------------------------------
#
# Deckt dieselbe Pruefungslogik (Klarnamen-Hash-Abgleich, Mutationstest) mit
# frei erfundenen Faellen ab -- laeuft IMMER, auch ohne die private Datei,
# damit die Logik selbst nicht ungetestet bleibt.

_SYNTH_POSITIV = {
    "id": "synth-leuchtturm-rahmen", "arbeitsstand": {}, "nachrichten": [
        {"absender": "Gruppe", "text": "Der Leuchtturm soll gelb werden."},
    ], "erwartet": [{"art": "rahmen_setzen", "wert": "gelber Leuchtturm"}],
    "notiz": "frei erfunden", "herkunft": {"gruppe": "g1", "post_id": 1},
}
_SYNTH_NEGATIV = {
    "id": "synth-wal-frage", "arbeitsstand": {}, "nachrichten": [
        {"absender": "Gruppe", "text": "Wie lange dauert die Pause?"},
    ], "erwartet": [],
    "notiz": "frei erfunden", "herkunft": {"gruppe": "g2", "post_id": 2},
}
#: Nur fuer diesen Test: ein frei erfundener Testname, kein echter Name aus
#: der Projektumgebung -- separate Hash-Menge, NICHT Teil von
#: ``KLARNAMEN_HASHES``, damit dieser Testfall nicht versehentlich einen der
#: 12 echten Namen reproduziert.
_TEST_NUR_HASHES = frozenset({
    hashlib.sha256(b"testperson").hexdigest(),
})
_SYNTH_MIT_KLARNAME = {
    "id": "synth-mit-klarname", "arbeitsstand": {}, "nachrichten": [
        {"absender": "Gruppe", "text": "Testperson soll die Szene eroeffnen."},
    ], "erwartet": [],
    "notiz": "frei erfunden, ABSICHTLICH ein erkennbarer Name fuer den Test",
    "herkunft": {"gruppe": "g3", "post_id": 3},
}


def test_synthetische_mini_fixture_erkennt_klarnamen_ueber_hash():
    assert not _klarnamen_treffer(_SYNTH_POSITIV)
    assert not _klarnamen_treffer(_SYNTH_NEGATIV)
    # gegen die echten KLARNAMEN_HASHES ist der frei erfundene Testname kein
    # Treffer -- die Erkennung wird hier mit der test-eigenen Hash-Menge
    # geprueft, nicht mit KLARNAMEN_HASHES.
    assert not _klarnamen_treffer(_SYNTH_MIT_KLARNAME)
    assert _klarnamen_treffer(_SYNTH_MIT_KLARNAME, hashes=_TEST_NUR_HASHES) == ["Testperson"]


def test_synthetische_mini_fixture_mutationstest_positiv():
    geliefert = [dict(e) for e in _SYNTH_POSITIV["erwartet"]]
    sauber = pp.vergleiche_erkenner(_SYNTH_POSITIV["erwartet"], geliefert)
    assert not sauber["fehlend"] and not sauber["ueberzaehlig"]

    mutiert = [dict(e, wert="UNZUSAMMENHAENGENDE-MUTATION") for e in _SYNTH_POSITIV["erwartet"]]
    ergebnis = pp.vergleiche_erkenner(mutiert, geliefert)
    assert ergebnis["fehlend"] or ergebnis["ueberzaehlig"]


def test_synthetische_mini_fixture_mutationstest_negativ():
    geliefert = []
    sauber = pp.vergleiche_erkenner(_SYNTH_NEGATIV["erwartet"], geliefert)
    assert not sauber["fehlend"] and not sauber["ueberzaehlig"]

    mutiert = [{"art": "kernthema_setzen", "wert": "erfundene Mutation"}]
    ergebnis = pp.vergleiche_erkenner(mutiert, geliefert)
    assert ergebnis["fehlend"]

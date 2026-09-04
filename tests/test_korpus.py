"""Validierung des Regressionskorpus unter ``korpus/`` -- ohne Netz.

Der Korpus ist Material, kein Code: er wird waehrend eines Workshops von Hand
erweitert, oft in Eile. Diese Tests fangen genau die Fehler ab, die dabei
passieren und die man sonst erst merkt, wenn der Pruefdurchlauf schon bezahlt
ist -- eine kaputte JSONL-Zeile, ein Tippfehler in einer ``art``, eine doppelt
vergebene id.

Sie pruefen ausserdem die Mindestbesetzung: der Korpus taugt nur etwas, wenn
jede Aenderungsart mehrfach vorkommt und die Negativfaelle die Mehrheit der
schwierigen Faelle stellen. Ein Korpus, der nur Treffer enthaelt, misst genau
die Zahl nicht, an der der Erkenner haengt (0 Falsch-Positive).
"""

import json
from pathlib import Path

import pytest

from theatersoap import erkenner, journal

KORPUS = Path(__file__).resolve().parent.parent / "korpus"

#: Mindestbesetzung, wie im Auftrag festgelegt. Als Konstanten hier, damit ein
#: Unterschreiten im Testnamen sichtbar wird und nicht in einer Zahl im Code.
MIN_ERKENNER = 60
MIN_ERKENNER_JE_ART = 2
MIN_ERKENNER_NEGATIV = 25

#: Zwei Arten sind teurer als der Rest und deshalb eigens abgesichert:
#: ``phase_setzen`` verschiebt den Fokus des ganzen Gespraechs (und muss
#: Rueckspruenge genauso treffen wie Schritte nach vorn), ``entfernen`` nimmt
#: Arbeitsergebnisse weg. Beide sind am 04.09.2026 dazugekommen und noch
#: nirgends gegen das echte Modell gemessen -- umso wichtiger, dass der
#: Korpus sie tragfaehig belegt (Brief A6, B4).
MIN_JE_NEUER_ART = 6
MIN_JOURNAL = 20
MIN_JOURNAL_LEER = 8
MIN_VERDICHTER = 6


def lade(name):
    zeilen = (KORPUS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    faelle = []
    for nummer, zeile in enumerate(zeilen, 1):
        assert zeile.strip(), f"{name}.jsonl:{nummer}: Leerzeile"
        try:
            faelle.append(json.loads(zeile))
        except json.JSONDecodeError as fehler:
            pytest.fail(f"{name}.jsonl:{nummer}: kein gueltiges JSON ({fehler})")
    return faelle


@pytest.fixture(scope="module")
def erkenner_faelle():
    return lade("erkenner")


@pytest.fixture(scope="module")
def journal_faelle():
    return lade("journal")


@pytest.fixture(scope="module")
def verdichter_faelle():
    return lade("verdichter")


# --- gemeinsame Form ------------------------------------------------------

@pytest.mark.parametrize("name", ["erkenner", "journal", "verdichter"])
def test_ids_sind_eindeutig(name):
    ids = [f["id"] for f in lade(name)]
    doppelte = {i for i in ids if ids.count(i) > 1}
    assert not doppelte, f"doppelte ids in {name}.jsonl: {sorted(doppelte)}"


@pytest.mark.parametrize("name", ["erkenner", "journal", "verdichter"])
def test_jeder_fall_hat_id_und_notiz(name):
    """Die ``notiz`` ist keine Zierde: sie sagt, warum ein Fall im Korpus ist.
    Ohne sie weiss in zwei Wochen niemand mehr, ob ein Fehlschlag schlimm ist."""
    for fall in lade(name):
        assert fall.get("id"), f"{name}.jsonl: Fall ohne id"
        assert fall.get("notiz", "").strip(), f"{name}.jsonl: {fall['id']} ohne notiz"


# --- Erkenner -------------------------------------------------------------

def test_erkenner_pflichtfelder(erkenner_faelle):
    for fall in erkenner_faelle:
        assert isinstance(fall.get("arbeitsstand"), dict), fall["id"]
        assert isinstance(fall.get("nachrichten"), list) and fall["nachrichten"], fall["id"]
        assert isinstance(fall.get("erwartet"), list), fall["id"]
        for nachricht in fall["nachrichten"]:
            assert nachricht.get("absender"), fall["id"]
            assert nachricht.get("text"), fall["id"]


def test_erkenner_arten_sind_bekannt(erkenner_faelle):
    """``art`` muss im Enum des Erkenners liegen -- sonst kann das Modell den
    Wert gar nicht liefern (das Schema erzwingt ihn) und der Fall waere ein
    garantierter Fehlschlag."""
    for fall in erkenner_faelle:
        for aenderung in fall["erwartet"]:
            assert aenderung["art"] in erkenner.ARTEN, f"{fall['id']}: {aenderung['art']}"
            assert isinstance(aenderung.get("wert"), str), fall["id"]


def test_erkenner_arbeitsstand_kennt_nur_bekannte_felder(erkenner_faelle):
    erlaubt = {"begriffe", "kernthema", "hauptkonflikt", "figuren"}
    for fall in erkenner_faelle:
        unbekannt = set(fall["arbeitsstand"]) - erlaubt
        assert not unbekannt, f"{fall['id']}: {unbekannt}"
        for figur in fall["arbeitsstand"].get("figuren", []):
            assert figur.get("name"), fall["id"]


def test_erkenner_mindestanzahl(erkenner_faelle):
    assert len(erkenner_faelle) >= MIN_ERKENNER


def test_erkenner_jede_art_mindestens_zweimal(erkenner_faelle):
    gezaehlt = {art: 0 for art in erkenner.ARTEN}
    for fall in erkenner_faelle:
        for aenderung in fall["erwartet"]:
            gezaehlt[aenderung["art"]] += 1
    zu_duenn = {a: n for a, n in gezaehlt.items() if n < MIN_ERKENNER_JE_ART}
    assert not zu_duenn, f"zu selten belegte Arten: {zu_duenn}"


@pytest.mark.parametrize("art", ["phase_setzen", "entfernen"])
def test_erkenner_traegt_die_neuen_arten_dicht_genug(erkenner_faelle, art):
    """Brief A6/B4: sechs Faelle je neuer art. Die Mindestbesetzung von zwei
    (oben) reicht dafuer nicht -- beide Arten sind noch nirgends gegen das
    echte Modell gemessen, und beide koennen etwas kaputtmachen, das die
    Gruppe erarbeitet hat."""
    gezaehlt = sum(
        1 for f in erkenner_faelle for a in f["erwartet"] if a["art"] == art
    )
    assert gezaehlt >= MIN_JE_NEUER_ART, f"{art}: nur {gezaehlt} Faelle"


def test_erkenner_hat_den_material_fall(erkenner_faelle):
    """Material ist nie entfernbar (NACHTRAG N3). Der Fall, der das belegt,
    ist ein Negativfall mitten unter den Entfernungen -- er darf nicht
    verschwinden, wenn jemand den Korpus aufraeumt."""
    faelle = [
        f for f in erkenner_faelle
        if not f["erwartet"]
        and any(
            wort in n["text"].lower()
            for n in f["nachrichten"]
            for wort in ("lösch", "loesch")
        )
        and any("interview" in n["text"].lower() for n in f["nachrichten"])
    ]
    assert faelle, "der Fall 'Interview loeschen -> gar nichts' fehlt"


def test_erkenner_genug_negativfaelle(erkenner_faelle):
    """Falsch-Positive sind der teure Fehler (SPEC § 4.3a) -- entsprechend
    viele Faelle muessen eine leere Erwartung haben."""
    negativ = [f for f in erkenner_faelle if not f["erwartet"]]
    assert len(negativ) >= MIN_ERKENNER_NEGATIV


def test_erkenner_hat_die_gemessenen_faelle(erkenner_faelle):
    """Die vier Faelle aus der Endpruefung vom 04.09.2026 (HANDOFF (d)) muessen
    drin sein -- sie sind die einzigen, fuer die ein Sollwert am echten Modell
    belegt ist."""
    nach_art = {a["art"] for f in erkenner_faelle for a in f["erwartet"]}
    for art in ("interview_starten", "interview_beenden", "kernthema_setzen", "verworfen"):
        assert art in nach_art

    texte = " ".join(n["text"] for f in erkenner_faelle for n in f["nachrichten"]).lower()
    assert "kindheit" in texte, "der Nemotron-Fall (Kindheitsfragen) fehlt"


# --- Journal --------------------------------------------------------------

def test_journal_pflichtfelder(journal_faelle):
    for fall in journal_faelle:
        assert isinstance(fall.get("abschnitt"), list) and fall["abschnitt"], fall["id"]
        assert isinstance(fall.get("bisherige_eintraege"), list), fall["id"]
        assert isinstance(fall.get("erwartet"), list), fall["id"]
        for nachricht in fall["abschnitt"]:
            assert nachricht.get("absender"), fall["id"]
            assert nachricht.get("text"), fall["id"]
        for eintrag in fall["bisherige_eintraege"]:
            assert eintrag.get("art") and eintrag.get("text"), fall["id"]


def test_journal_kategorien_sind_bekannt(journal_faelle):
    for fall in journal_faelle:
        for eintrag in fall["erwartet"]:
            assert eintrag["kategorie"] in journal.KATEGORIEN, fall["id"]
            assert eintrag["text"].strip(), fall["id"]


def test_journal_mindestanzahl_und_leerfaelle(journal_faelle):
    assert len(journal_faelle) >= MIN_JOURNAL
    leer = [f for f in journal_faelle if not f["erwartet"]]
    assert len(leer) >= MIN_JOURNAL_LEER


def test_journal_erwartungen_sind_stichwoerter_kein_wortlaut(journal_faelle):
    """``erwartet[].text`` ist ein Muss-Stichwort-Set, kein Satz. Ein ganzer
    Satz darin waere ein stiller Fehler: er wuerde als ein einziges, sehr
    langes Stichwort geprueft und praktisch nie treffen."""
    for fall in journal_faelle:
        for eintrag in fall["erwartet"]:
            for stichwort in eintrag["text"].split("|"):
                assert stichwort.strip(), fall["id"]
                assert len(stichwort.split()) <= 3, (
                    f"{fall['id']}: '{stichwort}' sieht nach Wortlaut aus, "
                    "nicht nach Stichwort"
                )


# --- Verdichter -----------------------------------------------------------

def test_verdichter_pflichtfelder(verdichter_faelle):
    for fall in verdichter_faelle:
        assert fall.get("transkript", "").strip(), fall["id"]
        erwartet = fall.get("erwartet")
        assert isinstance(erwartet, dict), fall["id"]
        assert isinstance(erwartet.get("stichwoerter"), list), fall["id"]
        assert erwartet["stichwoerter"], fall["id"]
        assert 1 <= erwartet["themen_min"] <= erwartet["themen_max"], fall["id"]


def test_verdichter_mindestanzahl(verdichter_faelle):
    assert len(verdichter_faelle) >= MIN_VERDICHTER


def test_verdichter_transkripte_haben_die_richtige_laenge(verdichter_faelle):
    """200-600 Woerter: kuerzer traegt keine zwei belegbaren Kernthemen,
    laenger misst eher die Kuerzung als den Prompt."""
    for fall in verdichter_faelle:
        woerter = len(fall["transkript"].split())
        assert 200 <= woerter <= 600, f"{fall['id']}: {woerter} Woerter"


def test_verdichter_transkripte_haben_sprechermarker(verdichter_faelle):
    """Ohne Sprechermarker ist es kein Interviewtranskript, sondern ein
    Aufsatz -- und der Verdichter saehe im Betrieb etwas anderes."""
    for fall in verdichter_faelle:
        zeilen = [z for z in fall["transkript"].splitlines() if z.strip()]
        mit_marker = [z for z in zeilen if ":" in z.split(" ")[0]]
        assert len(mit_marker) >= 4, fall["id"]

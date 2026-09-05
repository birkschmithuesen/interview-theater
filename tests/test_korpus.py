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

from interview_theater import erkenner, journal

KORPUS = Path(__file__).resolve().parent.parent / "korpus"

#: Mindestbesetzung, wie im Auftrag festgelegt. Als Konstanten hier, damit ein
#: Unterschreiten im Testnamen sichtbar wird und nicht in einer Zahl im Code.
MIN_ERKENNER = 70
MIN_ERKENNER_JE_ART = 2
MIN_ERKENNER_NEGATIV = 28

#: Zwei Arten sind teurer als der Rest und deshalb eigens abgesichert:
#: ``phase_setzen`` verschiebt den Fokus des ganzen Gespraechs (und muss
#: Rueckspruenge genauso treffen wie Schritte nach vorn), ``entfernen`` nimmt
#: Arbeitsergebnisse weg. Beide sind am 04.09.2026 dazugekommen und noch
#: nirgends gegen das echte Modell gemessen -- umso wichtiger, dass der
#: Korpus sie tragfaehig belegt (Brief A6, B4).
MIN_JE_NEUER_ART = 6

#: ``fragen_setzen`` ist am selben Abend dazugekommen und schreibt ein Feld,
#: das die Gruppe im Interview vor sich hat. Vier Faelle plus zwei
#: Negativfaelle -- weniger als bei den beiden oben, weil die Abgrenzung
#: einfacher ist (Fragen stehen da oder werden erst ueberlegt), aber mehr als
#: die zwei aus der allgemeinen Mindestbesetzung.
MIN_FRAGEN_SETZEN = 4
MIN_JOURNAL = 20
MIN_JOURNAL_LEER = 8
MIN_VERDICHTER = 6

#: Der Sprachprofil-Korpus (05.09.2026). Vier Faelle waren gefordert, fuenf
#: sind es geworden -- einer je Sprechweise, die sich im Material
#: unterscheidet: kurze Saetze mit Selbstkorrektur, Code-Switching,
#: 'man'-Distanz, Reihungen, Rueckfragen. Die Transkripte sind dieselben wie
#: im Verdichter-Korpus: sie sind erfunden, gepflegt und lang genug -- ein
#: zweiter Satz erfundener Interviews waere doppelte Arbeit an derselben
#: Sache.
MIN_SPRACHPROFIL = 4


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


@pytest.fixture(scope="module")
def sprachprofil_faelle():
    return lade("sprachprofil")


# --- gemeinsame Form ------------------------------------------------------

@pytest.mark.parametrize("name", ["erkenner", "journal", "verdichter", "sprachprofil"])
def test_ids_sind_eindeutig(name):
    ids = [f["id"] for f in lade(name)]
    doppelte = {i for i in ids if ids.count(i) > 1}
    assert not doppelte, f"doppelte ids in {name}.jsonl: {sorted(doppelte)}"


@pytest.mark.parametrize("name", ["erkenner", "journal", "verdichter", "sprachprofil"])
def test_jeder_fall_hat_id_und_notiz(name):
    """Die ``notiz`` ist keine Zierde: sie sagt, warum ein Fall im Korpus ist.
    Ohne sie weiss in zwei Wochen niemand mehr, ob ein Fehlschlag schlimm ist."""
    for fall in lade(name):
        assert fall.get("id"), f"{name}.jsonl: Fall ohne id"
        assert fall.get("notiz", "").strip(), f"{name}.jsonl: {fall['id']} ohne notiz"


# --- Erkenner -------------------------------------------------------------

def ist_aufnahmefall(fall) -> bool:
    """Ein Fall, der nicht einen Gespraechsabschnitt zeigt, sondern das
    Transkript EINER Sprachnachricht aus einem laufenden Interview (N1).

    Er hat ``aufnahme`` statt ``nachrichten`` -- so wie der Betrieb dort
    einen anderen Nutzertext baut (``erkenner.baue_aufnahme_nutzertext``) und
    das Ergebnis auf ``erkenner.ARTEN_IN_AUFNAHME`` einschraenkt."""
    return bool(fall.get("aufnahme"))


def texte_von(fall) -> list[str]:
    """Alle Texte eines Erkennerfalls, kleingeschrieben -- egal ob er aus
    Nachrichten besteht oder aus dem Transkript einer Aufnahme."""
    if ist_aufnahmefall(fall):
        return [fall["aufnahme"].lower()]
    return [n["text"].lower() for n in fall["nachrichten"]]


def test_erkenner_pflichtfelder(erkenner_faelle):
    for fall in erkenner_faelle:
        assert isinstance(fall.get("arbeitsstand"), dict), fall["id"]
        assert isinstance(fall.get("erwartet"), list), fall["id"]
        if ist_aufnahmefall(fall):
            assert fall["aufnahme"].strip(), fall["id"]
            assert "nachrichten" not in fall, (
                f"{fall['id']}: entweder aufnahme oder nachrichten, nicht beides"
            )
            continue
        assert isinstance(fall.get("nachrichten"), list) and fall["nachrichten"], fall["id"]
        for nachricht in fall["nachrichten"]:
            assert nachricht.get("absender"), fall["id"]
            assert nachricht.get("text"), fall["id"]


def test_erkenner_aufnahmefaelle_erwarten_nur_erlaubte_arten(erkenner_faelle):
    """Aus einer Aufnahme gelten genau die Arten aus ARTEN_IN_AUFNAHME -- alles
    andere filtert der Code weg (n12/n26). Ein Korpusfall, der etwas anderes
    erwartet, waere ein garantierter Fehlschlag."""
    aufnahmefaelle = [f for f in erkenner_faelle if ist_aufnahmefall(f)]
    assert aufnahmefaelle, "kein Erkenner-Fall aus einer Aufnahme (N1)"
    for fall in aufnahmefaelle:
        for aenderung in fall["erwartet"]:
            assert aenderung["art"] in erkenner.ARTEN_IN_AUFNAHME, (
                f"{fall['id']}: {aenderung['art']} gilt aus einer Aufnahme nicht"
            )


def test_erkenner_aufnahmefaelle_haben_negativfaelle(erkenner_faelle):
    """Der teuerste Fehler dieses Laufs ist ein Treffer auf Interviewinhalt:
    eine Lebensgeschichte im Arbeitsstand, der Gruppe als 'Notiert' gemeldet.
    Also muessen auch hier Negativfaelle dabei sein."""
    leer = [f for f in erkenner_faelle if ist_aufnahmefall(f) and not f["erwartet"]]
    assert len(leer) >= 2


def test_erkenner_traegt_an_den_bot_dicht_genug(erkenner_faelle):
    """N4: die Abgrenzung 'an mich gerichtet' gegen 'Interviewmaterial' laesst
    sich in Regeln kaum fassen -- sie haengt am Adressaten, nicht an einer
    Formulierung ("zeig mir mal" steht in beiden). Drei Positive und drei
    Negative sind das Minimum, und die Negativen sind die wichtigeren: ein
    falsch abgezweigter Teil nimmt dem Interview seinen Inhalt."""
    aufnahmefaelle = [f for f in erkenner_faelle if ist_aufnahmefall(f)]
    positiv = [
        f for f in aufnahmefaelle
        if any(a["art"] == "an_den_bot" for a in f["erwartet"])
    ]
    negativ = [f for f in aufnahmefaelle if not f["erwartet"]]
    assert len(positiv) >= 3, f"an_den_bot: nur {len(positiv)} Positivfaelle"
    assert len(negativ) >= 3, f"Aufnahmefaelle: nur {len(negativ)} Negativfaelle"


def test_erkenner_hat_die_interviewfrage_als_negativfall(erkenner_faelle):
    """Der teuerste Fehler von N4 in einem Fall: eine Frage AN die
    interviewte Person, die aussieht wie eine an den Bot."""
    treffer = [
        f for f in erkenner_faelle
        if ist_aufnahmefall(f) and not f["erwartet"]
        and any("zeig mir" in t for t in texte_von(f))
    ]
    assert treffer, "der Fall 'Interviewfrage im Imperativ -> gar nichts' fehlt"


def test_erkenner_arten_sind_bekannt(erkenner_faelle):
    """``art`` muss im Enum des Erkenners liegen -- sonst kann das Modell den
    Wert gar nicht liefern (das Schema erzwingt ihn) und der Fall waere ein
    garantierter Fehlschlag."""
    for fall in erkenner_faelle:
        for aenderung in fall["erwartet"]:
            assert aenderung["art"] in erkenner.ARTEN, f"{fall['id']}: {aenderung['art']}"
            assert isinstance(aenderung.get("wert"), str), fall["id"]


def test_erkenner_arbeitsstand_kennt_nur_bekannte_felder(erkenner_faelle):
    erlaubt = {
        "begriffe", "fragen", "kernthema", "format", "rahmen", "hauptkonflikt",
        "figuren",
    }
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


#: Die vier Arten vom 05.09.2026 (Phase 5, Szenenplanung, Sprachprofil).
#: Je drei Positiv- und zwei Negativfaelle, wie im Auftrag festgelegt --
#: dieselbe Ueberlegung wie bei ``MIN_JE_NEUER_ART``: keine von ihnen ist
#: gegen das echte Modell gemessen, und jede schreibt etwas, das die Gruppe
#: erarbeitet hat.
NEUE_ARTEN_0509 = ("format_setzen", "rahmen_setzen", "szene_planen",
                   "figur_quelle_setzen")
MIN_POSITIV_0509 = 3
MIN_NEGATIV_0509 = 2

#: Die Kennung, an der die Negativfaelle einer neuen art haengen: sie stehen
#: als Block direkt bei ihren Positivfaellen und teilen deren Praefix
#: (``f01``…``f05`` fuer format_setzen). Das ist Konvention, keine Mechanik --
#: der Test macht sie sichtbar, damit beim Aufraeumen nicht die Negativfaelle
#: als erste verschwinden.
PRAEFIX_0509 = {
    "format_setzen": "f0", "rahmen_setzen": "r0", "szene_planen": "sp0",
    "figur_quelle_setzen": "q0",
}


@pytest.mark.parametrize("art", NEUE_ARTEN_0509)
def test_erkenner_traegt_die_arten_vom_05_09(erkenner_faelle, art):
    positiv = [
        f for f in erkenner_faelle
        if any(a["art"] == art for a in f["erwartet"])
    ]
    negativ = [
        f for f in erkenner_faelle
        if not f["erwartet"] and f["id"].startswith(PRAEFIX_0509[art])
    ]
    assert len(positiv) >= MIN_POSITIV_0509, f"{art}: nur {len(positiv)} Positivfaelle"
    assert len(negativ) >= MIN_NEGATIV_0509, f"{art}: nur {len(negativ)} Negativfaelle"


def test_erkenner_hat_die_live_stellen_aus_dem_probelauf(erkenner_faelle):
    """Die vier Nachrichten aus dem Probelauf vom 05.09.2026, an denen der
    Umbau haengt: 76 (Rahmen), 86 (Szenenplanung mit Ort und Figuren), 97
    ("Go" nach einer Planung) und 115 (ein Kernsatz wird nachgetragen).

    Sie sind die einzigen Faelle mit einem Sollwert aus einem echten Chat --
    wer den Korpus aufraeumt, darf sie nicht mit den erfundenen verwechseln."""
    texte = " ".join(t for f in erkenner_faelle for t in texte_von(f))
    for stelle in ("demonstration", "polizeikessel", "riviera", "go!"):
        assert stelle in texte, f"die Live-Stelle '{stelle}' fehlt"


def test_erkenner_traegt_fragen_setzen(erkenner_faelle):
    gezaehlt = sum(
        1 for f in erkenner_faelle for a in f["erwartet"] if a["art"] == "fragen_setzen"
    )
    assert gezaehlt >= MIN_FRAGEN_SETZEN, f"fragen_setzen: nur {gezaehlt} Faelle"


def test_erkenner_hat_den_negativfall_fragen_nur_ueberlegt(erkenner_faelle):
    """'Welche Fragen koennten wir stellen?' ist KEIN Setzen. Der Fall muss
    im Korpus bleiben: ein Falsch-Positiv wuerde hier die Frageliste mit
    einer Ueberlegung ueberschreiben, und die Gruppe geht damit ins
    Interview."""
    negativ = [f for f in erkenner_faelle if not f["erwartet"]]
    assert any(
        "welche fragen" in t for f in negativ for t in texte_von(f)
    ), "der Fall 'ueber Fragen reden -> gar nichts' fehlt"


def test_erkenner_trennt_konflikt_von_kernthema_und_figuren(erkenner_faelle):
    """Der Fall belegt, dass ein Abschnitt, in dem BEIDE Phasen vorkommen --
    Figuren (4) und Konflikt (5) --, auf die gemeinte gesetzt wird und nicht
    auf die zuerst genannte."""
    treffer = [
        f for f in erkenner_faelle
        if any(a["art"] == "phase_setzen" for a in f["erwartet"])
        and any("konflikt" in t for t in texte_von(f))
        and any("figuren" in t for t in texte_von(f))
    ]
    assert treffer, "der Fall 'erst der Konflikt, Figuren danach' fehlt"


def test_erkenner_hat_den_fall_kernthema_und_figuren_zusammen(erkenner_faelle):
    """Der Satz, aus dem das siebenstufige Modell entstanden ist ("Kernthema
    und Figuren in einem Schritt", Birk 04.09.2026 abends). Er muss im Korpus
    bleiben: er ist der einzige Fall, der belegt, dass beides EINE Phase
    setzt und nicht zwei."""
    treffer = [
        f for f in erkenner_faelle
        if any(a["art"] == "phase_setzen" for a in f["erwartet"])
        and any("kernthema" in t and "figuren" in t for t in texte_von(f))
    ]
    assert treffer, "der Fall 'Kernthema und Figuren zusammen' fehlt"


def test_erkenner_hat_den_material_fall(erkenner_faelle):
    """Material ist nie entfernbar (NACHTRAG N3). Der Fall, der das belegt,
    ist ein Negativfall mitten unter den Entfernungen -- er darf nicht
    verschwinden, wenn jemand den Korpus aufraeumt."""
    faelle = [
        f for f in erkenner_faelle
        if not f["erwartet"]
        and any(wort in t for t in texte_von(f) for wort in ("lösch", "loesch"))
        and any("interview" in t for t in texte_von(f))
    ]
    assert faelle, "der Fall 'Interview loeschen -> gar nichts' fehlt"


def test_erkenner_traegt_die_zustimmungsfaelle(erkenner_faelle):
    """N7: der Fall, den diese Umkalibrierung abstellen soll -- die Gruppe
    stimmt einem konkreten Vorschlag zu, und nichts wird eingetragen. Er ist
    im Probelauf dreimal aufgetreten (Fragen, Kernthema, drei Figuren), also
    muessen mindestens so viele Faelle ihn belegen.

    ``zustimmung: true`` ist kein Sollwert, sondern eine Markierung: aus ihr
    baut ``pruefe_prompts.zustimmungszeilen`` die Kennzahl 'Falsch-Negative in
    Zustimmungsfaellen'."""
    markiert = [f for f in erkenner_faelle if f.get("zustimmung")]
    assert len(markiert) >= 5
    for fall in markiert:
        assert fall["erwartet"], (
            f"{fall['id']}: ein Zustimmungsfall ohne Sollwert misst nichts"
        )


def test_erkenner_hat_den_gegenfall_zur_zustimmung(erkenner_faelle):
    """Die Umkalibrierung braucht ihre Grenze, sonst wird aus 'im Zweifel
    eintragen' ein Freibrief: ein Bot-Vorschlag, dem die Gruppe NICHT
    zustimmt, bleibt leer."""
    treffer = [
        f for f in erkenner_faelle
        if not f["erwartet"]
        and any(n.get("ist_bot") for n in f.get("nachrichten", []))
    ]
    assert treffer, "der Fall 'Bot-Vorschlag ohne Zustimmung -> gar nichts' fehlt"


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

    texte = " ".join(t for f in erkenner_faelle for t in texte_von(f))
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

def ist_ablehnungsfall(fall) -> bool:
    """Ein Fall, dessen Sollwert NULL Themen ist (``themen_max == 0``, N2).

    Er misst das Gegenteil der uebrigen Faelle: nicht, ob der Verdichter zwei
    bis vier belegte Themen findet, sondern ob er bei zu duennem Material
    **nichts** erfindet. Die Formvorgaben der anderen Faelle (200-600 Woerter,
    vier Sprechermarker) gelten fuer ihn deshalb ausdruecklich nicht -- ein
    Ablehnungsfall mit 200 Woertern waere gar keiner."""
    return fall["erwartet"].get("themen_max") == 0


def test_verdichter_pflichtfelder(verdichter_faelle):
    for fall in verdichter_faelle:
        assert fall.get("transkript", "").strip(), fall["id"]
        erwartet = fall.get("erwartet")
        assert isinstance(erwartet, dict), fall["id"]
        assert isinstance(erwartet.get("stichwoerter"), list), fall["id"]
        if ist_ablehnungsfall(fall):
            assert erwartet["themen_min"] == 0, fall["id"]
            assert erwartet["stichwoerter"] == [], (
                f"{fall['id']}: ein Ablehnungsfall erwartet keine Stichwoerter"
            )
            continue
        assert erwartet["stichwoerter"], fall["id"]
        assert 1 <= erwartet["themen_min"] <= erwartet["themen_max"], fall["id"]


def test_verdichter_mindestanzahl(verdichter_faelle):
    assert len(verdichter_faelle) >= MIN_VERDICHTER


def test_verdichter_hat_den_ablehnungsfall(verdichter_faelle):
    """N2: der Fall aus dem Probelauf ("Zeigt mir mal die Verdichtungen ...")
    muss im Korpus bleiben. Er ist der einzige, der die teuerste Eigenschaft
    des Verdichters misst -- dass er aus einem Satz kein Interview erfindet."""
    assert [f["id"] for f in verdichter_faelle if ist_ablehnungsfall(f)]


def test_verdichter_hat_einen_fall_mit_frageliste(verdichter_faelle):
    """N3: der Verdichter geht die Fragen der Gruppe der Reihe nach durch.
    Mindestens ein Korpusfall muss deshalb eine Frageliste tragen -- sonst
    misst der Lauf genau den Weg nicht, den ein Interview im Workshop nimmt.

    Format wie in ``arbeitsstand.fragen``: eine Frage je Zeile, "Thema:
    Frage"."""
    mit_fragen = [f for f in verdichter_faelle if f.get("fragen")]
    assert mit_fragen, "kein Verdichter-Fall mit Frageliste"
    for fall in mit_fragen:
        zeilen = [z for z in fall["fragen"].splitlines() if z.strip()]
        assert len(zeilen) >= 2, fall["id"]
        for zeile in zeilen:
            assert ":" in zeile, f"{fall['id']}: '{zeile}' ohne Thema"


def test_verdichter_transkripte_haben_die_richtige_laenge(verdichter_faelle):
    """200-600 Woerter: kuerzer traegt keine zwei belegbaren Kernthemen,
    laenger misst eher die Kuerzung als den Prompt. Ablehnungsfaelle sind
    ausgenommen -- sie sind absichtlich zu kurz."""
    for fall in verdichter_faelle:
        if ist_ablehnungsfall(fall):
            continue
        woerter = len(fall["transkript"].split())
        assert 200 <= woerter <= 600, f"{fall['id']}: {woerter} Woerter"


def test_verdichter_transkripte_haben_sprechermarker(verdichter_faelle):
    """Ohne Sprechermarker ist es kein Interviewtranskript, sondern ein
    Aufsatz -- und der Verdichter saehe im Betrieb etwas anderes."""
    for fall in verdichter_faelle:
        if ist_ablehnungsfall(fall):
            continue
        zeilen = [z for z in fall["transkript"].splitlines() if z.strip()]
        mit_marker = [z for z in zeilen if ":" in z.split(" ")[0]]
        assert len(mit_marker) >= 4, fall["id"]


# --- Sprachprofil ---------------------------------------------------------

def test_sprachprofil_pflichtfelder(sprachprofil_faelle):
    for fall in sprachprofil_faelle:
        assert fall.get("transkript", "").strip(), fall["id"]
        erwartet = fall.get("erwartet")
        assert isinstance(erwartet, dict), fall["id"]
        assert erwartet.get("stichwoerter"), fall["id"]
        assert erwartet.get("zitate_min", 0) >= 1, fall["id"]


def test_sprachprofil_mindestanzahl(sprachprofil_faelle):
    assert len(sprachprofil_faelle) >= MIN_SPRACHPROFIL


def test_sprachprofil_stichwoerter_sind_alternativen_kein_wortlaut(sprachprofil_faelle):
    """``stichwoerter`` sind Alternativenmengen ("kurz|knapp|abgehackt"), von
    denen eine im Profil vorkommen muss -- kein Wortlaut.

    Fuer eine Beobachtung ueber Sprechweise gibt es ein Dutzend Woerter; ein
    Wortlautvergleich wuerde bei jeder harmlosen Synonymwahl Alarm schlagen
    und die Kennzahl entwerten, an der wirklich etwas haengt (erfundene
    Zitate)."""
    for fall in sprachprofil_faelle:
        for eintrag in fall["erwartet"]["stichwoerter"]:
            alternativen = [a.strip() for a in eintrag.split("|")]
            assert all(alternativen), fall["id"]
            for alternative in alternativen:
                assert len(alternative.split()) == 1, (
                    f"{fall['id']}: '{alternative}' sieht nach Wortlaut aus"
                )


def test_sprachprofil_nutzt_die_verdichter_transkripte(
    sprachprofil_faelle, verdichter_faelle
):
    """Dieselben erfundenen Interviews wie im Verdichter-Korpus. Ein zweiter
    Satz waere doppelte Arbeit an derselben Sache -- und die Transkripte
    muessen dieselben bleiben, damit ein Unterschied zwischen den beiden
    Laeufen wirklich am Prompt liegt und nicht am Material."""
    bekannt = {f["transkript"] for f in verdichter_faelle}
    for fall in sprachprofil_faelle:
        assert fall["transkript"] in bekannt, fall["id"]

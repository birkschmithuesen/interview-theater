"""Tests fuer die Schaerfung am Material (Phase 6, Umbau 05.09.2026 nachts).

Gemessen wird die eine Entscheidung, um die es geht: **erst erfinden, dann
schaerfen**. Die Gruppe hat Setting, Figuren und Geschichte selbst gemacht;
dieses Modul legt das Material daneben und ordnet zu -- es schreibt die
Geschichte nicht um.

Konkret: dass das Mapping nur aus der nummerierten Liste waehlt, dass ein
Wortlaut gegen das Original geprueft wird, dass die Zuordnungen in
``schaerfung`` landen (additiv, mit Runde), dass es je Szene und je Figur
eine Vorschlagsnachricht mit Grundleiste gibt, dass die Uebernahme wirklich
Felder schreibt -- und dass eine zweite Runde die Rundennummer erhoeht.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, schaerfung

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


class KLMAttrappe:
    """Liefert die vorgegebene Schema-Antwort und merkt sich den Nutzertext."""

    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


ZITAT_A = "Ich habe zwanzig Jahre genaeht und keiner hat gefragt."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt."


def _interview(conn, transkript, themen, name="Interview"):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, name)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Eine Zusammenfassung.", themen)
    return kopf_id


@pytest.fixture
def lage(conn):
    """Der Stand beim Eintritt in Phase 6: Setting, zwei Figuren, eine
    Geschichte mit zwei Szenen -- und zwei ausgewertete Interviews."""
    _interview(conn, ZITAT_A, [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": ZITAT_A,
         "zitat_geprueft": 1},
    ], name="A")
    _interview(conn, ZITAT_B, [
        {"thema": "Leere Stadt am Wochenende", "beleg_zitat": ZITAT_B,
         "zitat_geprueft": 1},
    ], name="B")

    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_arbeitsstand(
        conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen"
    )
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Pal", "haelt an seiner Route fest")
    for nummer, titel in ((1, "Im Treppenhaus"), (2, "Am Kiosk")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
        repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    phasen.setze(conn, 1, 6, "test")
    return conn


def _antwort(**felder):
    grund = {
        "eintrag_nummern": [], "szenen_nummern": [], "figuren_namen": [],
        "begruendungen": [],
    }
    grund.update(felder)
    return grund


# --- der Mapping-Lauf -----------------------------------------------------


def test_der_nutzertext_traegt_das_erfundene_und_das_nummerierte_material(
    lage, einst
):
    """Erst das Erfundene (Setting, Figuren, Geschichte, Szenen mit Nummer),
    dann das Material mit Nummern -- die Nummer ist der einzige Weg, auf eine
    Stelle zu zeigen."""
    klm = KLMAttrappe(_antwort())

    schaerfung.mappe(klm, lage, einst, 1)

    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Setting: Ein Treppenhaus, nachts" in nutzer
    assert "Zwei verlieren sich." in nutzer
    assert "Mira" in nutzer and "Pal" in nutzer
    assert "[1] — Im Treppenhaus" in nutzer
    assert "[2] — Am Kiosk" in nutzer
    assert f'[1] Interview 1 | Thema: Arbeit ohne Anerkennung' in nutzer
    assert ZITAT_A in nutzer


def test_das_mapping_speichert_je_szene_und_je_figur(lage, einst):
    klm = KLMAttrappe(_antwort(
        eintrag_nummern=[1, 2],
        szenen_nummern=[1, 0],
        figuren_namen=["Mira", "Pal"],
        begruendungen=["Mira kommt daher", "Pal bleibt dabei"],
    ))

    anzahl, runde = schaerfung.mappe(klm, lage, einst, 1)

    assert (anzahl, runde) == (2, 1)
    szene_id = repo.hole_szenen(lage, 1)[0]["id"]
    zu_szene = repo.schaerfungen(lage, 1, szene_id=szene_id)
    assert [z["zitat"] for z in zu_szene] == [ZITAT_A]
    assert zu_szene[0]["begruendung"] == "Mira kommt daher"
    pal = repo.hole_figur(lage, 1, "Pal")
    assert [z["zitat"] for z in repo.schaerfungen(lage, 1, figur_id=pal["id"])] == [
        ZITAT_B
    ]


def test_eine_nummer_die_es_nicht_gibt_wird_verworfen(lage, einst):
    """Der Schutz der Nummerierung: erfinden kann das Modell nichts, weil
    nichts Erfundenes eine Nummer hat."""
    klm = KLMAttrappe(_antwort(
        eintrag_nummern=[99], szenen_nummern=[1], figuren_namen=[""],
        begruendungen=["frei erfunden"],
    ))

    anzahl, _ = schaerfung.mappe(klm, lage, einst, 1)

    assert anzahl == 0
    assert repo.schaerfungen(lage, 1) == []


def test_ein_falscher_wortlaut_verwirft_die_zuordnung(lage, einst):
    """Dieselbe Regel wie beim Verdichter und beim Sprachprofil (N2, T3):
    schreibt das Modell etwas anderes hin als das Zitat, auf dessen Nummer es
    zeigt, meint es nicht diese Stelle."""
    klm = KLMAttrappe(_antwort(
        eintrag_nummern=[1], szenen_nummern=[1], figuren_namen=[""],
        begruendungen=["passt"], zitate=["Das habe ich nie gesagt."],
    ))

    anzahl, _ = schaerfung.mappe(klm, lage, einst, 1)

    assert anzahl == 0


def test_eine_zuordnung_ohne_szene_und_ohne_figur_faellt_weg(lage, einst):
    klm = KLMAttrappe(_antwort(
        eintrag_nummern=[1], szenen_nummern=[0], figuren_namen=[""],
        begruendungen=["irgendwie schon"],
    ))

    assert schaerfung.mappe(klm, lage, einst, 1)[0] == 0


def test_ohne_material_gibt_es_keinen_aufruf(conn, einst):
    klm = KLMAttrappe(_antwort())

    assert schaerfung.mappe(klm, conn, einst, 1) == (0, 0)
    assert klm.aufrufe == []


def test_eine_zweite_runde_zaehlt_hoch_und_laesst_die_erste_stehen(lage, einst):
    """Additiv, nicht ersetzend: eine Schaerfung, die die Gruppe schon
    uebernommen hat, ist eine Entscheidung -- ein zweiter Lauf darf sie nicht
    wegraeumen."""
    klm = KLMAttrappe(_antwort(
        eintrag_nummern=[1], szenen_nummern=[1], figuren_namen=[""],
        begruendungen=["erste Runde"],
    ))
    schaerfung.mappe(klm, lage, einst, 1)

    klm.antwort = _antwort(
        eintrag_nummern=[2], szenen_nummern=[2], figuren_namen=[""],
        begruendungen=["zweite Runde"],
    )
    _, runde = schaerfung.mappe(klm, lage, einst, 1)

    assert runde == 2
    alle = repo.schaerfungen(lage, 1)
    assert [z["runde"] for z in alle] == [1, 2]


# --- was im Chat steht ----------------------------------------------------


def _mappe(lage, einst, **felder):
    schaerfung.mappe(KLMAttrappe(_antwort(**felder)), lage, einst, 1)


def test_je_szene_eine_vorschlagsnachricht_mit_grundleiste(lage, tg, einst):
    _mappe(lage, einst, eintrag_nummern=[1], szenen_nummern=[1],
           figuren_namen=[""], begruendungen=["Mira erzaehlt davon"])

    assert knoepfe.biete_schaerfung(lage, tg, 1) is True

    text = tg.knoepfe[-1][1]
    assert "Szene 1" in text
    assert "Interview 1" in text
    assert ZITAT_A in text
    assert "Mira erzaehlt davon" in text
    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
    ]


def test_je_figur_eine_vorschlagsnachricht(lage, tg, einst):
    _mappe(lage, einst, eintrag_nummern=[2], szenen_nummern=[0],
           figuren_namen=["Pal"], begruendungen=["so redet er"])

    knoepfe.biete_schaerfung(lage, tg, 1)

    assert "Pal" in tg.knoepfe[-1][1]
    assert ZITAT_B in tg.knoepfe[-1][1]


def test_ohne_offene_schaerfung_kommt_die_frage_nach_einer_runde(lage, tg):
    assert knoepfe.biete_schaerfung(lage, tg, 1) is False

    assert knoepfe.TEXT_SCHAERFUNG_RUNDE_KNOPF in [
        b for b, _ in tg.knoepfe[-1][2]
    ]


# --- die Uebernahme -------------------------------------------------------


def test_uebernehmen_schreibt_die_szenenfelder(lage, einst):
    _mappe(lage, einst, eintrag_nummern=[1], szenen_nummern=[1],
           figuren_namen=[""], begruendungen=["Mira zaehlt die Jahre auf"])
    szene = repo.hole_szenen(lage, 1)[0]

    assert schaerfung.uebernimm_szene(lage, 1, szene) == 1

    frisch = repo.hole_szene(lage, szene["id"])
    assert "Mira zaehlt die Jahre auf" in frisch["was_passiert"]
    assert ZITAT_A in frisch["kernsaetze"]


def test_uebernehmen_ergaenzt_und_ersetzt_nicht(lage, einst):
    """Die Gruppe hat das Feld erfunden, das Material schaerft es -- es
    ueberschreibt es nicht."""
    szene = repo.hole_szenen(lage, 1)[0]
    repo.setze_szenenfeld(lage, szene["id"], "was_passiert", "Sie warten.")
    _mappe(lage, einst, eintrag_nummern=[1], szenen_nummern=[1],
           figuren_namen=[""], begruendungen=["und zaehlen die Jahre"])

    schaerfung.uebernimm_szene(lage, 1, repo.hole_szenen(lage, 1)[0])

    frisch = repo.hole_szene(lage, szene["id"])
    assert frisch["was_passiert"].startswith("Sie warten.")
    assert "und zaehlen die Jahre" in frisch["was_passiert"]


def test_uebernehmen_setzt_das_interview_der_figur(lage, einst):
    """Hier steckt die frueher eigenstaendige Figuren-Ebene 2: aus der
    Zuordnung wird ``figur.quelle_aufnahme_id`` -- und daraus danach der
    Sprachduktus."""
    _mappe(lage, einst, eintrag_nummern=[2], szenen_nummern=[0],
           figuren_namen=["Pal"], begruendungen=["seine Route"])
    figur = repo.hole_figur(lage, 1, "Pal")
    assert figur["quelle_aufnahme_id"] is None

    assert schaerfung.uebernimm_figur(lage, 1, figur) == 1

    frisch = repo.hole_figur(lage, 1, "Pal")
    assert frisch["quelle_aufnahme_id"] is not None
    assert "seine Route" in frisch["beschreibung"]


def test_eine_uebernommene_schaerfung_wird_nicht_zweimal_vorgeschlagen(
    lage, tg, einst
):
    _mappe(lage, einst, eintrag_nummern=[1], szenen_nummern=[1],
           figuren_namen=[""], begruendungen=["einmal"])
    schaerfung.uebernimm_szene(lage, 1, repo.hole_szenen(lage, 1)[0])

    assert schaerfung.szenenvorschlag(
        lage, 1, repo.hole_szenen(lage, 1)[0]
    ) is None


# --- der Knopfweg ---------------------------------------------------------


def _druck(daten):
    return {
        "callback_query_id": "q1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }


def _knopf(tg, beschriftung):
    for _, _, leiste in tg.knoepfe:
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}")


def test_gefaellt_uns_weiter_uebernimmt_und_geht_weiter(lage, tg, einst):
    _mappe(lage, einst, eintrag_nummern=[1, 2], szenen_nummern=[1, 0],
           figuren_namen=["", "Pal"], begruendungen=["zur Szene", "zur Figur"])
    knoepfe.biete_schaerfung(lage, tg, 1)

    knoepfe.behandle(lage, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter")))

    frisch = repo.hole_szene(lage, repo.hole_szenen(lage, 1)[0]["id"])
    assert "zur Szene" in frisch["was_passiert"]
    # Und die naechste offene Schaerfung steht schon da: die Figur.
    assert "Pal" in tg.knoepfe[-1][1]


def test_noch_eine_runde_startet_das_mapping_erneut(lage, tg, einst, monkeypatch):
    """Zusage 2: der Knopf ruft kein Modell -- er gibt an einen Thread ab."""
    gestartet = []

    def _fake_starte(conn, tg_, klm, e, chat_id, nachbereitung=None):
        gestartet.append(chat_id)
        return None

    monkeypatch.setattr(schaerfung, "starte", _fake_starte)
    knoepfe.biete_schaerfung(lage, tg, 1)

    knoepfe.behandle(
        lage, tg, object(), einst,
        _druck(_knopf(tg, knoepfe.TEXT_SCHAERFUNG_RUNDE_KNOPF)),
    )

    assert gestartet == [1]


def test_der_phaseneintritt_stoesst_das_mapping_an(lage, tg, einst, monkeypatch):
    """Die Schaerfung fragt nicht nach Ideen: sie legt die Geschichte neben
    die Interviews -- automatisch beim Eintritt, im Thread."""
    gestartet = []
    monkeypatch.setattr(
        schaerfung, "starte",
        lambda *a, **k: gestartet.append(True) or None,
    )
    phasen.setze(lage, 1, 4, "test")
    knoepfe.biete_phase(lage, tg, 1, "Weiter?", 5)

    knoepfe.behandle(
        lage, tg, object(), einst, _druck(_knopf(tg, "Weiter zu Schaerfung"))
    )

    assert gestartet == [True]
    assert knoepfe._TEXT_PROAKTIV not in [t for _, t in tg.gesendet]

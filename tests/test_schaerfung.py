"""Tests fuer die Schaerfung am Material (Phase 6, Umbau 05.09.2026 nachts,
Umbau auf Je-Ziel-Aufrufe 07.10.2026).

Gemessen wird die eine Entscheidung, um die es geht: **erst erfinden, dann
schaerfen**. Die Gruppe hat Setting, Figuren und Geschichte selbst gemacht;
dieses Modul legt das Material daneben und ordnet zu -- es schreibt die
Geschichte nicht um.

Seit dem Umbau 07.10.2026 (Analyse ``zuordnung-pruefung.md``) fragt
``schaerfung.mappe`` nicht mehr EINMAL ueber alle Szenen/Figuren gleichzeitig,
sondern JE SZENE UND JE FIGUR einen eigenen, engen Aufruf -- parallel. Konkret
gemessen: dass der Nutzertext je Ziel das Erfundene, den Hintergrund und das
EINE Ziel traegt, dass eine Nummer, die es nicht gibt, verworfen wird, dass
ein Wortlaut gegen das Original geprueft wird, dass eine Staerke unter
``STAERKE_MIN`` nicht gespeichert wird, dass die Zuordnungen in
``schaerfung`` landen (additiv, mit Runde), dass es je Szene und je Figur
eine seitenweise Vorschlagsnachricht mit Grundleiste gibt (ohne
Gesamtgrenze, mit "Mehr zeigen"), dass "Diese uebernehmen"/"Keine davon" nur
die gezeigte Seite treffen, dass die Uebernahme wirklich Felder schreibt --
und dass eine zweite Runde die Rundennummer erhoeht.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, schaerfung, vorschlagssperre

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_vorschlagssperre():
    """Kein Zustand aus einem frueheren Test -- die Sperre lebt im Modul und
    alle Tests hier verwenden ``chat_id=1``. Die meisten Tests patchen
    ``schaerfung.starte`` weg und beruehren sie ohnehin nicht, aber
    defensiv wie ``tests/test_szenenfolge.py``."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


def _antwort(**felder):
    grund = {"eintrag_nummern": [], "staerke": [], "begruendungen": []}
    grund.update(felder)
    return grund


class KLMAttrappe:
    """Liefert je Ziel-Aufruf eine eigene Antwort -- ``antworten`` bildet
    einen eindeutigen Substring des Nutzertexts (die Ziel-Zeile nennt ihn,
    z. B. "Szene 1" oder "Figur Mira") auf die Schema-Antwort fuer GENAU
    dieses Ziel ab. Kein Treffer: die leere Vorgabe (kein Fund fuer dieses
    Ziel) -- derselbe Fall wie ein Ziel, das der Test nicht erwaehnt."""

    def __init__(self, antworten: dict[str, dict] | None = None):
        self.antworten = antworten or {}
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        for schluessel, antwort in self.antworten.items():
            if schluessel in nutzer:
                return antwort
        return _antwort()


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


# --- der Mapping-Lauf -------------------------------------------------------


def test_der_nutzertext_traegt_das_erfundene_den_hintergrund_und_das_ziel(
    lage, einst
):
    """Erst das Erfundene (Setting, Figuren, Geschichte, Szenen mit Nummer),
    dann das eine Ziel, dann das Material mit Nummern -- die Nummer ist der
    einzige Weg, auf eine Stelle zu zeigen."""
    klm = KLMAttrappe()

    schaerfung.mappe(klm, lage, einst, 1)

    # Vier Ziele (zwei Szenen, zwei Figuren) -- ein Aufruf je Ziel.
    assert len(klm.aufrufe) == 4
    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Setting: Ein Treppenhaus, nachts" in nutzer
    assert "Zwei verlieren sich." in nutzer
    assert "Mira" in nutzer and "Pal" in nutzer
    assert "[1] — Im Treppenhaus" in nutzer
    assert "[2] — Am Kiosk" in nutzer
    assert "Ziel -- ordne NUR fuer dieses eine Ziel zu:" in nutzer
    assert f'[1] Interview 1 | Thema: Arbeit ohne Anerkennung' in nutzer
    assert ZITAT_A in nutzer


def test_jeder_aufruf_nennt_genau_ein_ziel(lage, einst):
    """Jeder der vier Aufrufe zeigt genau EIN Ziel -- nicht alle vier."""
    klm = KLMAttrappe()

    schaerfung.mappe(klm, lage, einst, 1)

    ziel_zeilen = [
        a["nutzer"].split("Ziel -- ordne NUR fuer dieses eine Ziel zu: ")[1]
        .splitlines()[0]
        for a in klm.aufrufe
    ]
    assert sorted(z.split(" — ")[0] for z in ziel_zeilen) == [
        "Figur Mira", "Figur Pal", "Szene 1", "Szene 2",
    ]


def test_das_mapping_speichert_je_szene_und_je_figur(lage, einst):
    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["Mira kommt daher"]),
        "Figur Pal": _antwort(eintrag_nummern=[2], staerke=[2],
                              begruendungen=["Pal bleibt dabei"]),
    })

    anzahl, runde = schaerfung.mappe(klm, lage, einst, 1)

    assert (anzahl, runde) == (2, 1)
    szene_id = repo.hole_szenen(lage, 1)[0]["id"]
    zu_szene = repo.schaerfungen(lage, 1, szene_id=szene_id)
    assert [z["zitat"] for z in zu_szene] == [ZITAT_A]
    assert zu_szene[0]["begruendung"] == "Mira kommt daher"
    assert zu_szene[0]["staerke"] == 3
    pal = repo.hole_figur(lage, 1, "Pal")
    zu_pal = repo.schaerfungen(lage, 1, figur_id=pal["id"])
    assert [z["zitat"] for z in zu_pal] == [ZITAT_B]
    assert zu_pal[0]["staerke"] == 2


def test_eine_nummer_die_es_nicht_gibt_wird_verworfen(lage, einst):
    """Der Schutz der Nummerierung: erfinden kann das Modell nichts, weil
    nichts Erfundenes eine Nummer hat."""
    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[99], staerke=[3],
                            begruendungen=["frei erfunden"]),
    })

    anzahl, _ = schaerfung.mappe(klm, lage, einst, 1)

    assert anzahl == 0
    assert repo.schaerfungen(lage, 1) == []


def test_ein_falscher_wortlaut_verwirft_die_zuordnung(lage, einst):
    """Dieselbe Regel wie beim Verdichter und beim Sprachprofil (N2, T3):
    schreibt das Modell etwas anderes hin als das Zitat, auf dessen Nummer es
    zeigt, meint es nicht diese Stelle."""
    klm = KLMAttrappe({
        "Szene 1": _antwort(
            eintrag_nummern=[1], staerke=[3], begruendungen=["passt"],
            zitate=["Das habe ich nie gesagt."],
        ),
    })

    anzahl, _ = schaerfung.mappe(klm, lage, einst, 1)

    assert anzahl == 0


def test_eine_staerke_unter_der_schwelle_faellt_weg(lage, einst):
    """Birk 07.10.2026: keine feste Prozentzahl, sondern eine Schwelle je
    Zuordnung -- Staerke 1 (passt am Rand) wird NICHT gespeichert."""
    assert schaerfung.STAERKE_MIN == 2
    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[1],
                            begruendungen=["passt nur am Rand"]),
    })

    anzahl, _ = schaerfung.mappe(klm, lage, einst, 1)

    assert anzahl == 0


def test_ohne_material_gibt_es_keinen_aufruf(conn, einst):
    klm = KLMAttrappe()

    assert schaerfung.mappe(klm, conn, einst, 1) == (0, 0)
    assert klm.aufrufe == []


def test_ohne_ziele_gibt_es_keinen_aufruf(conn, einst):
    """Material ja, aber noch keine Szene/Figur erfunden -- ein Modell, das
    ohne Ziel zuordnen soll, erfindet eins."""
    _interview(conn, ZITAT_A, [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": ZITAT_A,
         "zitat_geprueft": 1},
    ])
    klm = KLMAttrappe()

    assert schaerfung.mappe(klm, conn, einst, 1) == (0, 0)
    assert klm.aufrufe == []


def test_eine_zweite_runde_zaehlt_hoch_und_laesst_die_erste_stehen(lage, einst):
    """Additiv, nicht ersetzend: eine Schaerfung, die die Gruppe schon
    uebernommen hat, ist eine Entscheidung -- ein zweiter Lauf darf sie nicht
    wegraeumen."""
    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["erste Runde"]),
    })
    schaerfung.mappe(klm, lage, einst, 1)

    klm2 = KLMAttrappe({
        "Szene 2": _antwort(eintrag_nummern=[2], staerke=[3],
                            begruendungen=["zweite Runde"]),
    })
    _, runde = schaerfung.mappe(klm2, lage, einst, 1)

    assert runde == 2
    alle = repo.schaerfungen(lage, 1)
    assert sorted(z["runde"] for z in alle) == [1, 2]


def test_fortschrittsmeldung_wird_aktualisiert_und_am_ende_geloescht(lage, tg, einst):
    """Anforderung 4 (Birk 07.10.2026): die Gruppe wartet nicht stumm."""
    klm = KLMAttrappe()

    schaerfung._lauf(lage, tg, klm, einst, 1)

    # Erste Zeile: die Fortschrittsmeldung, schon mit der echten Zielzahl
    # (0/4, nie "0/?" -- Birk 07.10.2026). Danach vier Aktualisierungen
    # (eine je Ziel), am Ende geloescht -- nicht mehr im Chat.
    assert tg.gesendet[0][1].startswith("🔍")
    assert "0/4" in tg.gesendet[0][1] and "?" not in tg.gesendet[0][1]
    assert len(tg.geaendert) == 4
    assert tg.geloescht and tg.geloescht[0][0] == 1


# --- was im Chat steht ------------------------------------------------------


def _mappe(lage, einst, antworten):
    """``antworten``: dict Substring-im-Nutzertext -> Schema-Antwort fuer
    GENAU dieses Ziel (siehe ``KLMAttrappe``)."""
    return schaerfung.mappe(KLMAttrappe(antworten), lage, einst, 1)


def test_je_szene_ein_menue_mit_einem_knopf_je_stelle(lage, tg, einst):
    """Seit dem 06.09.2026 ist das ein Menue wie jedes andere: Ueberschrift,
    nummerierte Kurzoption, ein Knopf je Stelle -- statt eines Fliessblocks
    mit einer globalen Ja/Nein-Frage (Analyse Abschnitt 2)."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["Mira erzaehlt davon"]),
    })

    assert knoepfe.biete_schaerfung(lage, tg, 1) is True

    text = tg.knoepfe[-1][1]
    assert "Szene 1" in text
    assert "Interview 1" in text
    assert "Mira erzaehlt davon" in text
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    # Ein Knopf je Stelle, dann die beiden Sammelknoepfe (kein "Mehr zeigen"
    # noetig -- nur eine Stelle insgesamt).
    assert beschriftungen[0].startswith("1 · ")
    assert beschriftungen[-2:] == [
        knoepfe._TEXT_SCHAERFUNG_ALLE_KNOPF, knoepfe._TEXT_SCHAERFUNG_KEINE_KNOPF,
    ]
    # Das Zitat steht als Kurzform da (hier passt es in die 12 Woerter).
    assert f"„{ZITAT_A}“" in text
    assert "Vorschlag:" not in text


def test_ein_langes_zitat_wird_im_menue_gekuerzt(lage, einst):
    assert schaerfung.ZITAT_WOERTER == 12
    lang = " ".join(f"wort{n}" for n in range(1, 30))
    _, beschreibung = schaerfung.option(
        lage, 1,
        {
            "aufnahme_id": None, "thema": "Ein Thema", "zitat": lang,
            "begruendung": "",
        },
    )
    assert "wort12" in beschreibung
    assert "wort13" not in beschreibung
    assert "…" in beschreibung


def test_je_figur_eine_vorschlagsnachricht(lage, tg, einst):
    _mappe(lage, einst, {
        "Figur Pal": _antwort(eintrag_nummern=[2], staerke=[3],
                              begruendungen=["so redet er"]),
    })

    knoepfe.biete_schaerfung(lage, tg, 1)

    assert "Pal" in tg.knoepfe[-1][1]
    assert ZITAT_B in tg.knoepfe[-1][1]


def test_ohne_offene_schaerfung_kommt_die_frage_nach_einer_runde(lage, tg):
    assert knoepfe.biete_schaerfung(lage, tg, 1) is False

    assert knoepfe.TEXT_SCHAERFUNG_RUNDE_KNOPF in [
        b for b, _ in tg.knoepfe[-1][2]
    ]


# --- Seiten: mehr als eine Seite offener Stellen ----------------------------


def test_offene_stellen_sind_nicht_mehr_gedeckelt_sortiert_nach_staerke(
    lage, einst
):
    """Birk 07.10.2026: ``MAX_STELLEN`` war nur die Anzeige -- die Zuordnung
    selbst hat keine Gesamtgrenze mehr. Sortiert staerkste zuerst."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(
            eintrag_nummern=[1, 2, 1, 2], staerke=[2, 3, 2, 3],
            begruendungen=["a", "b", "c", "d"],
        ),
    })
    szene_id = repo.hole_szenen(lage, 1)[0]["id"]

    alle = schaerfung.offene_stellen(lage, 1, szene_id=szene_id)

    assert len(alle) == 4
    assert [z["staerke"] for z in alle] == [3, 3, 2, 2]


def test_mehr_zeigen_knopf_erscheint_erst_ab_der_vierten_stelle(lage, tg, einst):
    """``MAX_STELLEN`` ist jetzt eine Seitengroesse, keine Gesamtgrenze --
    "Mehr zeigen" erscheint nur, wenn ueber die Seite hinaus noch etwas
    offen ist."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(
            eintrag_nummern=[1, 2, 1, 2], staerke=[2, 3, 2, 3],
            begruendungen=["a", "b", "c", "d"],
        ),
    })

    knoepfe.biete_schaerfung(lage, tg, 1)

    optionsknoepfe = [b for b, _ in tg.knoepfe[-1][2] if b[0].isdigit()]
    assert len(optionsknoepfe) == 3
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert knoepfe._TEXT_SCHAERFUNG_MEHR_KNOPF in beschriftungen
    assert "(1–3 von 4)" in tg.knoepfe[-1][1]


def test_mehr_zeigen_blaettert_dieselbe_szene_weiter(lage, tg, einst):
    _mappe(lage, einst, {
        "Szene 1": _antwort(
            eintrag_nummern=[1, 2, 1, 2], staerke=[2, 3, 2, 3],
            begruendungen=["erste", "zweite", "dritte", "vierte"],
        ),
    })
    knoepfe.biete_schaerfung(lage, tg, 1)
    mehr_daten = _knopf(tg, knoepfe._TEXT_SCHAERFUNG_MEHR_KNOPF)

    knoepfe.behandle(lage, tg, None, einst, _druck(mehr_daten))

    text = tg.knoepfe[-1][1]
    optionsknoepfe = [b for b, _ in tg.knoepfe[-1][2] if b[0].isdigit()]
    assert len(optionsknoepfe) == 1
    assert "(4–4 von 4)" in text


def test_diese_uebernehmen_trifft_nur_die_gezeigte_seite(lage, tg, einst):
    """Der gemessene Fehler von vorher (Analyse Abschnitt 4): ein Klick auf
    die sichtbaren drei Stellen uebernahm heimlich auch die vierte,
    unsichtbare. Seit 07.10.2026 traegt der Knopf nur die ``id``s der Seite."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(
            eintrag_nummern=[1, 2, 1, 2], staerke=[2, 3, 2, 3],
            begruendungen=["erste", "zweite", "dritte", "vierte"],
        ),
    })
    knoepfe.biete_schaerfung(lage, tg, 1)

    knoepfe.behandle(
        lage, tg, None, einst,
        _druck(_knopf(tg, knoepfe._TEXT_SCHAERFUNG_ALLE_KNOPF)),
    )

    offen = [z for z in repo.schaerfungen(lage, 1) if not z["uebernommen_am"]]
    uebernommen = [z for z in repo.schaerfungen(lage, 1) if z["uebernommen_am"]]
    assert len(uebernommen) == 3
    assert len(offen) == 1


# --- die Uebernahme --------------------------------------------------------


def test_uebernehmen_schreibt_die_szenenfelder(lage, einst):
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["Mira zaehlt die Jahre auf"]),
    })
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
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["und zaehlen die Jahre"]),
    })

    schaerfung.uebernimm_szene(lage, 1, repo.hole_szenen(lage, 1)[0])

    frisch = repo.hole_szene(lage, szene["id"])
    assert frisch["was_passiert"].startswith("Sie warten.")
    assert "und zaehlen die Jahre" in frisch["was_passiert"]


def test_uebernehmen_setzt_das_interview_der_figur(lage, einst):
    """Hier steckt die frueher eigenstaendige Figuren-Ebene 2: aus der
    Zuordnung wird ``figur.quelle_aufnahme_id`` -- und daraus danach der
    Sprachduktus."""
    _mappe(lage, einst, {
        "Figur Pal": _antwort(eintrag_nummern=[2], staerke=[3],
                              begruendungen=["seine Route"]),
    })
    figur = repo.hole_figur(lage, 1, "Pal")
    assert figur["quelle_aufnahme_id"] is None

    assert schaerfung.uebernimm_figur(lage, 1, figur) == 1

    frisch = repo.hole_figur(lage, 1, "Pal")
    assert frisch["quelle_aufnahme_id"] is not None
    assert "seine Route" in frisch["beschreibung"]


def test_eine_uebernommene_schaerfung_wird_nicht_zweimal_vorgeschlagen(
    lage, tg, einst
):
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["einmal"]),
    })
    schaerfung.uebernimm_szene(lage, 1, repo.hole_szenen(lage, 1)[0])

    assert schaerfung.szenenvorschlag(
        lage, 1, repo.hole_szenen(lage, 1)[0]
    ) is None


# --- der Knopfweg -----------------------------------------------------------


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


def test_diese_uebernehmen_uebernimmt_und_geht_weiter(lage, tg, einst):
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["zur Szene"]),
        "Figur Pal": _antwort(eintrag_nummern=[2], staerke=[3],
                              begruendungen=["zur Figur"]),
    })
    knoepfe.biete_schaerfung(lage, tg, 1)

    knoepfe.behandle(
        lage, tg, None, einst,
        _druck(_knopf(tg, knoepfe._TEXT_SCHAERFUNG_ALLE_KNOPF)),
    )

    frisch = repo.hole_szene(lage, repo.hole_szenen(lage, 1)[0]["id"])
    assert "zur Szene" in frisch["was_passiert"]
    # Und die naechste offene Schaerfung steht schon da: die Figur.
    assert "Pal" in tg.knoepfe[-1][1]


def test_ein_knopf_uebernimmt_genau_eine_stelle(lage, tg, einst):
    """Der Kern von Massnahme 4: Knopf N wirkt auf Punkt N -- und nur auf
    ihn."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(
            eintrag_nummern=[1, 2], staerke=[3, 3],
            begruendungen=["erste Stelle", "zweite Stelle"],
        ),
    })
    knoepfe.biete_schaerfung(lage, tg, 1)
    erster = [b for b, _ in tg.knoepfe[-1][2] if b.startswith("1 · ")][0]

    knoepfe.behandle(lage, tg, None, einst, _druck(_knopf(tg, erster)))

    frisch = repo.hole_szene(lage, repo.hole_szenen(lage, 1)[0]["id"])
    assert "erste Stelle" in frisch["was_passiert"]
    assert "zweite Stelle" not in frisch["was_passiert"]
    offen = [z for z in repo.schaerfungen(lage, 1) if not z["uebernommen_am"]]
    assert len(offen) == 1


def test_keine_davon_verwirft_die_gezeigten_stellen(lage, tg, einst):
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                            begruendungen=["passt nicht"]),
    })
    knoepfe.biete_schaerfung(lage, tg, 1)

    knoepfe.behandle(
        lage, tg, None, einst,
        _druck(_knopf(tg, knoepfe._TEXT_SCHAERFUNG_KEINE_KNOPF)),
    )

    assert repo.schaerfungen(lage, 1) == []
    frisch = repo.hole_szene(lage, repo.hole_szenen(lage, 1)[0]["id"])
    assert "passt nicht" not in (frisch["was_passiert"] or "")


def test_callback_data_des_menues_bleibt_unter_der_grenze(lage, tg, einst):
    """Zusage 1: auch mit mehreren ids im ``wert`` traegt der Knopf nur
    ``k:<id>``."""
    _mappe(lage, einst, {
        "Szene 1": _antwort(eintrag_nummern=[1, 2], staerke=[3, 3],
                            begruendungen=["a", "b"]),
    })

    knoepfe.biete_schaerfung(lage, tg, 1)

    for _, daten in tg.knoepfe[-1][2]:
        assert len(daten.encode("utf-8")) <= 64


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
        lage, tg, object(), einst, _druck(_knopf(tg, "Weiter zu Phase 5 · Schaerfung"))
    )

    assert gestartet == [True]
    assert knoepfe._TEXT_PROAKTIV not in [t for _, t in tg.gesendet]


def test_entwurf_startet_nur_mit_aktivem_profilschalter(lage, tg, einst, monkeypatch):
    """Padua Phasen TEIL 1 (03.10.2026): die Stufe-A-Uebersicht laeuft nach
    dem automatischen Mapping NUR unter dem Profilschalter
    ``[prosa_entwurf] aktiv`` an -- Dortmund (Schalter aus) bleibt beim
    bisherigen Weg unberuehrt.

    ``schaerfung.starte`` wird wie im Nachbartest durch eine Attrappe
    ersetzt, die hier aber die uebergebene ``nachbereitung`` sofort ausfuehrt
    -- genau das, was der echte Thread nach dem Mapping tut (``_lauf``
    ruft ``nachbereitung`` nach Freigabe der Sperre)."""
    from interview_theater import entwurf, workshop

    def _fake_starte(conn, tg_, klm, e, chat_id, nachbereitung=None):
        # Realistisch: der echte Thread (``schaerfung._lauf``) ruft
        # ``nachbereitung`` EINMAL nach dem Mapping und liefert kein
        # ``None`` zurueck -- ``starte_schaerfung`` haengt die
        # Schaerfung-Vorstellung sonst ein zweites Mal an (``if ... is
        # None: _danach()``, fuer den Fall ohne Sprachmodell).
        if nachbereitung is not None:
            nachbereitung()
        return "thread"

    monkeypatch.setattr(schaerfung, "starte", _fake_starte)
    aufgerufen = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht", lambda *a, **k: aufgerufen.append(True)
    )

    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: False)
    phasen.setze(lage, 1, 4, "test")
    knoepfe.biete_phase(lage, tg, 1, "Weiter?", 5)
    knoepfe.behandle(
        lage, tg, object(), einst, _druck(_knopf(tg, "Weiter zu Phase 5 · Schaerfung"))
    )

    assert aufgerufen == []

    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    tg.knoepfe.clear()
    phasen.setze(lage, 1, 4, "test")
    knoepfe.biete_phase(lage, tg, 1, "Weiter?", 5)
    knoepfe.behandle(
        lage, tg, object(), einst, _druck(_knopf(tg, "Weiter zu Phase 5 · Schaerfung"))
    )

    assert aufgerufen == [True]


def test_matcher_hintergrund_voll_nur_mit_profilschalter(monkeypatch):
    """Birk 07.10.2026 14:45: unter ``vollmaterial_phase5`` bekommt jeder
    Je-Ziel-Aufruf Festlegungen, Uebersicht und den vollen Mitgehoert-Block;
    ohne Schalter nichts davon. Mutant: Schalter ignoriert -> zweiter Teil rot."""
    from interview_theater import kontext, repo, schaerfung, workshop
    monkeypatch.setattr(repo, "festlegungen", lambda conn, chat_id: [
        {"bereich": "struktur", "bezug": None, "text": "three parts"}])
    monkeypatch.setattr(repo, "festlegungszeile", lambda b, z, t: f"[{b}] {t}")
    monkeypatch.setattr(kontext, "_baue_mitgehoert", lambda conn, chat_id, voll=False: "BRAINSTORM WORTLAUT")
    stand = _Stand({"geschichte_uebersicht": "Logline: X", "figuren_entwurf": ""})
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)
    text = "\n".join(schaerfung._hintergrund_voll_zeilen(None, 1, stand))
    assert "three parts" in text and "Logline: X" in text and "BRAINSTORM WORTLAUT" in text
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: False)
    assert schaerfung._hintergrund_voll_zeilen(None, 1, stand) == []


class _Stand(dict):
    pass


def test_ziele_ohne_figuren_fuer_selbstspielende_gruppe(monkeypatch):
    """Birk 07.10.2026 15:10: Gruppen im Profilschalter bekommen nur Szenen
    als Ziele; ohne Szenen bleiben die Figuren (sonst gaebe es gar kein Ziel).
    Mutant: Schalter ignoriert -> Figur taucht auf."""
    from interview_theater import repo, schaerfung, workshop
    szene = {"id": 1, "nummer": 1, "titel": "A", "was_passiert": "x", "form": None}
    figur = {"id": 9, "name": "F", "beschreibung": "y"}
    monkeypatch.setattr(repo, "figuren", lambda conn, chat_id: [figur])
    monkeypatch.setattr(workshop, "schaerfung_ohne_figuren_chats", lambda *a, **k: frozenset({5}))
    monkeypatch.setattr(repo, "hole_szenen", lambda conn, chat_id: [szene])
    assert [z["art"] for z in schaerfung._ziele(None, 5)] == ["szene"]
    assert [z["art"] for z in schaerfung._ziele(None, 6)] == ["szene", "figur"]
    monkeypatch.setattr(repo, "hole_szenen", lambda conn, chat_id: [])
    assert [z["art"] for z in schaerfung._ziele(None, 5)] == ["figur"]

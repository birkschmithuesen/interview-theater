"""Die Roadmap: welche Aufgabe der sieben Phasen steht, welche fehlt.

**Keine zweite Wunschliste** (AGENTS.md, ``fehlstellen``). Was eine Phase
setzt, steht in ``phasentexte.PARAMETER`` -- und ein Test nagelt Namen und
Reihenfolge daran fest. Eigen sind nur die **Pruefer**, und das aus einem
harten Grund: die Leser in ``PARAMETER`` rufen ``repo``, und der Webserver
bekommt keinen ``repo``-Pfad.

**Nichts hier setzt eine Phase.** Die Uebersicht zeigt den Datenstand; der
Datenstand schaltet nie (AGENTS.md, "Der automatische Phasensprung").
"""

import pytest

from interview_theater import db, fehlstellen, phasen, phasentexte, repo, roadmap, web_daten

CHAT = 7_000_000_000_001


def _lage(**abweichung) -> dict:
    grund = {
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 1,
        "interviewmodus": False, "tippt": False, "strom": None,
    }
    grund.update(abweichung)
    return grund


# -- die Liste ist genagelt --------------------------------------------------


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_jede_phase_nennt_dieselben_parameter_wie_phasentexte(nummer):
    """Eine Liste, zwei Leser. Wer eine Phase um ein Feld erweitert, aendert
    ``phasentexte.PARAMETER`` -- und merkt HIER, dass die Roadmap nachzieht."""
    aus_texten = [name for name, _, _ in phasentexte.PARAMETER.get(nummer, ())]
    aus_roadmap = [a.parameter for a in roadmap.AUFGABEN.get(nummer, ())]
    assert aus_roadmap == aus_texten


def test_jede_phase_kommt_vor():
    assert [p["nummer"] for p in roadmap.aus_daten(_lage())] == \
        [n for n, _, _ in phasen.PHASEN]


def test_die_namen_kommen_aus_dem_profil():
    erste = roadmap.aus_daten(_lage())[0]
    assert erste["bezeichnung"] == phasen.bezeichnung(erste["nummer"])
    assert erste["name"] == phasen.kurzname(erste["nummer"])


def test_die_aufgabentexte_laufen_ueber_die_beschriftungstabelle():
    """Damit Padua sie auf Englisch liest (Karte A1) und niemand eine zweite
    Uebersetzung pflegen muss."""
    erste = roadmap.aus_daten(_lage())[0]["aufgaben"][0]
    assert erste["text"] == phasentexte.beschriftung(
        roadmap.AUFGABEN[1][0].parameter)


# -- erledigt / offen --------------------------------------------------------


def _zustand(phasen_liste, nummer, kennung):
    for p in phasen_liste:
        if p["nummer"] != nummer:
            continue
        for a in p["aufgaben"]:
            if a["kennung"] == kennung:
                return a["zustand"]
    raise AssertionError(f"{nummer}/{kennung} nicht gefunden")


def test_am_anfang_ist_alles_offen():
    ergebnis = roadmap.aus_daten(_lage())
    assert all(a["zustand"] == "offen" for p in ergebnis for a in p["aufgaben"])
    assert ergebnis[0]["erledigt"] == 0


def test_begriffe_erledigt():
    ergebnis = roadmap.aus_daten(_lage(stand={"begriffe": "Heimat, Arbeit"}))
    assert _zustand(ergebnis, 1, "begriffe") == "erledigt"
    assert ergebnis[0]["erledigt"] == 1


def test_leere_einleitungen_zaehlen_als_geprueft():
    """"Keine noetig" ist ein Ergebnis der Sensibilitaetspruefung, kein
    fehlender Wert -- dieselbe Unterscheidung wie in
    ``phasen.voraussetzungen`` und ``fehlstellen``."""
    ergebnis = roadmap.aus_daten(_lage(stand={"fragen": "drei", "fragen_weich": ""}))
    assert _zustand(ergebnis, 2, "einleitungen") == "erledigt"


def test_szenentexte_erst_erledigt_wenn_alle_stehen():
    halb = [{"nummer": 1, "volltext": "Text"}, {"nummer": 2, "volltext": ""}]
    ganz = [{"nummer": 1, "volltext": "Text"}, {"nummer": 2, "volltext": "Auch"}]
    assert _zustand(roadmap.aus_daten(_lage(szenen=halb)), 6, "szenentexte") == "laeuft"
    assert _zustand(roadmap.aus_daten(_lage(szenen=ganz)), 6, "szenentexte") == "erledigt"


def test_prosa_zaehlt_wie_volltext():
    """Wie ``phasen._prosa_oder_volltext``: Phase 6 schreibt Geschichte, der
    Feinschliff Theatertext -- beides ist 'die Szene steht'."""
    szenen = [{"nummer": 1, "prosa": "Geschichte", "volltext": ""}]
    assert _zustand(roadmap.aus_daten(_lage(szenen=szenen)), 6, "szenentexte") == "erledigt"


def test_auswertungen_erledigt_erst_mit_einer_verdichtung():
    ohne = [{"zusammenfassung": None}]
    mit = [{"zusammenfassung": "Maria erzaehlt vom ersten Winter"}]
    assert _zustand(roadmap.aus_daten(_lage(interviews=ohne)), 3, "auswertungen") == "offen"
    assert _zustand(roadmap.aus_daten(_lage(interviews=mit)), 3, "auswertungen") == "erledigt"


# -- laeuft ------------------------------------------------------------------


def test_eine_laufende_aufnahme_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=3, interviewmodus=True))
    assert _zustand(ergebnis, 3, "interviews") == "laeuft"


def test_ein_laufender_szenenlauf_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=6, strom="szene"))
    assert _zustand(ergebnis, 6, "szenentexte") == "laeuft"


def test_ein_laufender_prosalauf_zeigt_laeuft():
    ergebnis = roadmap.aus_daten(_lage(phase=6, strom="prosa"))
    assert _zustand(ergebnis, 6, "szenentexte") == "laeuft"


def test_was_schon_steht_bleibt_erledigt_auch_wenn_etwas_laeuft():
    ergebnis = roadmap.aus_daten(
        _lage(phase=3, interviewmodus=True,
              interviews=[{"zusammenfassung": "steht"}]))
    assert _zustand(ergebnis, 3, "auswertungen") == "erledigt"


# -- die aktive Phase --------------------------------------------------------


def test_genau_eine_phase_ist_aktiv():
    ergebnis = roadmap.aus_daten(_lage(phase=4))
    assert [p["nummer"] for p in ergebnis if p["aktiv"]] == [4]


# -- die Sprungziele ---------------------------------------------------------


@pytest.mark.parametrize("nummer,kennung,tab", [
    (1, "begriffe", "stand"),
    (4, "setting", "stand"),
    (4, "szenenfolge", "stand"),
    (3, "interviews", "chat"),
    (6, "szenentexte", "textbuch"),
])
def test_jede_aufgabe_zeigt_auf_einen_tab(nummer, kennung, tab):
    for p in roadmap.aus_daten(_lage()):
        for a in p["aufgaben"]:
            if p["nummer"] == nummer and a["kennung"] == kennung:
                assert a["ziel"]["tab"] == tab
                return
    raise AssertionError("nicht gefunden")


def test_jedes_ziel_nennt_einen_bekannten_tab():
    erlaubt = {"chat", "stand", "textbuch"}
    for phase in roadmap.AUFGABEN.values():
        for aufgabe in phase:
            assert aufgabe.ziel["tab"] in erlaubt, aufgabe.kennung


# -- nichts setzt eine Phase -------------------------------------------------


def test_das_lesen_setzt_nie_eine_phase(tmp_path):
    """AGENTS.md: 'Datenstand ist nicht Absicht.' Die Uebersicht zeigt, sie
    schaltet nicht."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Drei Fragen")
    vorher = phasen.aktuelle(conn, CHAT)

    roadmap.register(conn, CHAT)
    conn.commit()
    assert phasen.aktuelle(conn, CHAT) == vorher
    assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_kein_sql_und_kein_repo_in_roadmap():
    """Dasselbe Muster wie ``fehlstellen``: ``aus_daten`` ist rein, ``register``
    holt ueber ``repo``, ``web_daten.roadmap`` read-only -- der Webserver
    bekommt dadurch keinen ``repo``-Pfad."""
    import pathlib

    quelle = pathlib.Path(roadmap.__file__).read_text(encoding="utf-8")
    for verboten in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert verboten not in quelle
    # ``repo`` nur im lokalen Import von ``register``, nie im Modulkopf.
    kopf = quelle.split("def aus_daten")[0]
    assert "import repo" not in kopf


# -- der Weg des Webservers --------------------------------------------------


def test_web_daten_liefert_dieselbe_liste_wie_der_bot(tmp_path):
    """Ein Zusammenbau, zwei Aufrufer -- wie beim Leitfaden und bei den
    Fehlstellen. Auf der Seite darf nichts anderes stehen als im Chat."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    repo.setze_phase(conn, CHAT, 4)
    conn.commit()

    vom_bot = roadmap.register(conn, CHAT)
    lesend = web_daten.oeffne_lesend(pfad)
    vom_web = web_daten.roadmap(lesend, CHAT)
    lesend.close()

    def kurz(liste):
        return [(p["nummer"], p["aktiv"],
                 [(a["kennung"], a["zustand"]) for a in p["aufgaben"]])
                for p in liste]

    assert kurz(vom_web) == kurz(vom_bot)


def test_web_daten_schreibt_nichts(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)      # mode=ro: jeder Schreibversuch wirft
    assert isinstance(web_daten.roadmap(lesend, CHAT), list)
    lesend.close()


# -- die Demo-Gruppe: erfundenes Material, drei Staende ----------------------


def _demo(conn, stand: str) -> None:
    """Baut eine Gruppe in einem von drei Staenden auf -- **nur erfundenes
    Material** (``simulation/interviews/``), nie ``betrieb/`` (Datenschutz)."""
    import pathlib

    from interview_theater import aufnahme

    class Einstellungen:
        bot_name = "gruppe1"
        audio_verz = "/tmp"

    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit, Streit")
    if stand == "begriffe":
        return
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war im Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    quelle = pathlib.Path("simulation/interviews/set1/1-meryem-koffer.md")
    aufnahme_id = aufnahme.importiere_text(
        conn, Einstellungen(), CHAT, 11,
        quelle.read_text(encoding="utf-8"), name="Interview 1",
    )
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Erzaehlt vom ersten Winter",
        [{"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
          "zitat_geprueft": 1}],
    )
    if stand == "interviews":
        return
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte", "Zwei treffen sich und bleiben.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    repo.lege_szene_an(conn, CHAT, 1, "Ankunft", "Meryem kommt an", None)


@pytest.fixture
def demo(tmp_path, request):
    pfad = str(tmp_path / "demo.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    _demo(conn, request.param)
    conn.commit()
    return conn


@pytest.mark.parametrize("demo,erwartet", [
    ("begriffe", {(1, "begriffe"): "erledigt", (2, "fragen"): "offen",
                  (3, "interviews"): "offen", (4, "setting"): "offen"}),
    ("interviews", {(1, "begriffe"): "erledigt", (2, "fragen"): "erledigt",
                    (2, "einleitungen"): "erledigt", (3, "interviews"): "erledigt",
                    (3, "auswertungen"): "erledigt", (4, "setting"): "offen"}),
    ("phase4", {(4, "setting"): "erledigt", (4, "figuren"): "erledigt",
                (4, "geschichte"): "erledigt", (4, "szenenfolge"): "erledigt",
                (5, "zuordnungen"): "offen", (6, "szenentexte"): "offen",
                (7, "stueckpruefung"): "offen"}),
], indirect=["demo"])
def test_die_demo_gruppe_zeigt_den_richtigen_stand(demo, erwartet):
    """Die Abnahme der Karte: erledigt/offen stimmt an einer echten Datenbank
    -- und das Lesen setzt keine Phase."""
    vorher = phasen.aktuelle(demo, CHAT)
    ergebnis = roadmap.register(demo, CHAT)
    for (nummer, kennung), soll in erwartet.items():
        assert _zustand(ergebnis, nummer, kennung) == soll, (nummer, kennung)
    assert phasen.aktuelle(demo, CHAT) == vorher


# -- Voraussetzung je Phase (UX-Knoepfe-Karte, Abschnitt 4) ------------------


def _phase(ergebnis, nummer):
    return next(p for p in ergebnis if p["nummer"] == nummer)


def test_phase_eins_hat_keine_voraussetzung():
    """Dorthin kommt man immer zurueck -- wie ``phasen.voraussetzungen``, die
    fuer 1 gar keinen Eintrag traegt."""
    assert roadmap.bereit(1, _lage()) is True
    assert roadmap.fehlt(1, _lage()) == []


def test_ohne_begriffe_ist_phase_zwei_nicht_bereit():
    assert roadmap.bereit(2, _lage()) is False
    assert roadmap.fehlt(2, _lage()) == ["Begriffe"]


def test_mit_begriffen_ist_phase_zwei_bereit():
    lage = _lage(stand={"begriffe": "Heimat, Arbeit"})
    assert roadmap.bereit(2, lage) is True
    assert roadmap.fehlt(2, lage) == []


def test_phase_vier_braucht_verdichtung_und_keine_offene():
    """Zwei Bedingungen, jede einzeln noetig -- wie
    ``phasen.voraussetzungen[4]``: eine Verdichtung reicht nicht, solange ein
    anderes Interview noch offen ist."""
    ohne_verdichtung = _lage()
    assert roadmap.bereit(4, ohne_verdichtung) is False
    assert roadmap.fehlt(4, ohne_verdichtung) == ["Auswertungen"]

    mit_offener = _lage(hat_verdichtung=True, offene_interviews=True)
    assert roadmap.bereit(4, mit_offener) is False
    assert roadmap.fehlt(4, mit_offener) == ["Offene Auswertungen"]

    fertig = _lage(hat_verdichtung=True, offene_interviews=False)
    assert roadmap.bereit(4, fertig) is True
    assert roadmap.fehlt(4, fertig) == []


def test_phase_fuenf_braucht_abgenommene_figurenliste():
    """``phasen.voraussetzungen[5]``: Figuren alleine reichen nicht, die
    Liste muss abgenommen sein (``figuren_fixiert_am``) -- anders als die
    Aufgabe ``AUFGABEN[4]["figuren"]``, die nur "gibt es welche" prueft."""
    lage = _lage(
        stand={"rahmen": "Bahnhof", "geschichte": "Zwei treffen sich"},
        figuren=[{"name": "Meryem"}], szenen=[{"nummer": 1, "volltext": "x"}],
    )
    assert roadmap.bereit(5, lage) is False
    assert roadmap.fehlt(5, lage) == ["Figuren"]

    lage["stand"]["figuren_fixiert_am"] = "2026-09-05T00:00:00"
    assert roadmap.bereit(5, lage) is True
    assert roadmap.fehlt(5, lage) == []


def test_aus_daten_traegt_bereit_und_fehlt_je_phase():
    ergebnis = roadmap.aus_daten(_lage())
    for phase in ergebnis:
        assert "bereit" in phase
        assert "fehlt" in phase
    assert _phase(ergebnis, 1)["bereit"] is True
    assert _phase(ergebnis, 2)["bereit"] is False
    assert _phase(ergebnis, 2)["fehlt"] == ["Begriffe"]


def test_web_daten_liefert_dieselbe_bereitschaft_wie_der_bot(tmp_path):
    """Dieselbe Quelle, zwei Aufrufer -- auch fuer die neuen Felder, sonst
    zeigt die Leiste im Web etwas anderes als der Bot beim Klick ausfuehrt."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war im Koffer?")
    repo.setze_phase(conn, CHAT, 2)
    conn.commit()

    vom_bot = roadmap.register(conn, CHAT)
    lesend = web_daten.oeffne_lesend(pfad)
    vom_web = web_daten.roadmap(lesend, CHAT)
    lesend.close()

    def kurz(liste):
        return [(p["nummer"], p["bereit"], p["fehlt"]) for p in liste]

    assert kurz(vom_web) == kurz(vom_bot)

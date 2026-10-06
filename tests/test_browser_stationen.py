import re

from simulation import browser_stationen as s
from simulation import browser_invarianten as inv
from simulation.diskussionen import DISKUSSIONEN

REZEPT = re.compile(r"\b(with the button|undo button|press the|click the|tap the|save them)\b", re.I)


def _b(von, text, typ="text"):
    return {"von": von, "typ": typ, "text": text}


def test_bot_fragt_zuletzt_also_antworten():
    assert s.muss_antworten([_b("gruppe", "hi"), _b("bot", "Which terms matter most?")], 0)


def test_systemzeilen_zaehlen_nicht():
    blasen = [_b("bot", "Which one?"), _b("bot", "📌 Saved.", "system"),
              _b("bot", "Interview 1", "transkript")]
    assert s.muss_antworten(blasen, 0)


def test_ohne_fragezeichen_oder_gruppe_zuletzt_nicht():
    assert not s.muss_antworten([_b("bot", "Saved your terms.")], 0)
    assert not s.muss_antworten([_b("bot", "Which?"), _b("gruppe", "home")], 0)
    assert not s.muss_antworten([], 0)


def test_hoechstens_drei_nachfragen():
    assert s.muss_antworten([_b("bot", "And?")], 2)
    assert not s.muss_antworten([_b("bot", "And?")], 3)


def test_notweg_nie_rueckwaerts_nie_doppelt():
    assert s.notweg_ziel(1, 1) == 2
    assert s.notweg_ziel(1, 2) is None      # schon da: kein zweiter Phasentext
    assert s.notweg_ziel(1, 3) is None      # nie zurueck
    assert s.notweg_ziel(1, None) is None   # unbekannt: nichts anfassen


def test_stationen_p12_vollstaendig_und_geordnet():
    schluessel = [st.schluessel for st in s.STATIONEN["p12"]]
    assert schluessel == [
        "p1-start", "p1-eintritt", "p1-kalibrierung", "p1-zuhoeren", "p1-begriffe",
        "p1-uebergang", "p2-eigene-fragen", "p2-ab-vergleich",
        "p2-einzeldurchgang", "p2-eroeffnung", "p2-uebergang"]
    phasen = [st.phase for st in s.STATIONEN_P12]
    assert phasen == sorted(phasen) and set(phasen) == {1, 2}
    zuhoeren = next(st for st in s.STATIONEN_P12 if st.schluessel == "p1-zuhoeren")
    assert zuhoeren.zuhoeren_s >= 120          # brainstorm: 1200 Zeichen / 90 s
    assert "Start listening" in zuhoeren.ziel and "do not type" in zuhoeren.ziel


def test_praedikate_ueber_datenstand():
    st = {x.schluessel: x for x in s.STATIONEN_P12}
    leer = {"arbeitsstand": {}, "kalibrierung_aufnahmen": 0, "diskussion_aufnahmen": 0}
    voll = {"arbeitsstand": {"begriffe": "home, border", "begriffe_detail": "[...]",
                             "phase": 2, "phase_angeboten": 3, "fragen": "x",
                             "fragen_eigene_vorschlag": "x", "fragen_ki_vorschlag": "x",
                             "interview_eroeffnung": "x", "interview_abschluss": "x"},
            "kalibrierung_aufnahmen": 1, "diskussion_aufnahmen": 4}
    for x in s.STATIONEN_P12:
        if x.fertig:
            assert not x.fertig(leer), x.schluessel
            assert x.fertig(voll), x.schluessel


def test_p1_start_ist_die_erste_station_und_ruft_keine_persona():
    schluessel = [st.schluessel for st in s.STATIONEN_P12]
    assert schluessel[0] == "p1-start"
    start = s.STATIONEN_P12[0]
    assert start.phase == 1
    assert start.ohne_persona is True
    assert start.warte_s == 60

    # Contract check: a harness respecting `ohne_persona` must never call
    # the persona client for this station. Simulate that contract here with
    # an attrappen (fake) persona client that counts calls.
    aufrufe = {"n": 0}

    class _AttrappenPersonaClient:
        def erzeuge(self, *a, **k):
            aufrufe["n"] += 1
            return {}

    client = _AttrappenPersonaClient()
    if not start.ohne_persona:
        client.erzeuge()  # a real engine would call the persona here
    assert aufrufe["n"] == 0


def test_ziele_statt_rezepte_in_beiden_listen():
    for liste in (s.STATIONEN_P12, s.STATIONEN_INVARIANTEN, s.STATIONEN_P34):
        for st in liste:
            if st.schluessel in {"p1-zuhoeren", "p1-zuhoeren-2", "p1-zuhoeren-3"}:
                continue  # 'Start listening' ist hier die Aufgabe selbst
            assert not REZEPT.search(st.ziel), (st.schluessel, st.ziel)


def test_p1_begriffe_ist_ein_ziel():
    st = next(x for x in s.STATIONEN_P12 if x.schluessel == "p1-begriffe")
    assert "workbench" in st.ziel.casefold()
    assert "button" not in st.ziel.casefold()


def test_invarianten_liste_deckt_die_abnahme():
    liste = s.STATIONEN_INVARIANTEN
    pruefungen = {p for st in liste for p in st.pruefung}
    assert {"nach_ende", "wissen", "raumcheck", "zweite_gruppe", "verhoerer"} <= pruefungen
    diskussionen = [st.diskussion for st in liste if st.diskussion]
    assert diskussionen[0] == "knapp"
    assert len(diskussionen) >= 3  # erste, zweite, dritte Diskussion in derselben Gruppe
    assert all(d in DISKUSSIONEN for d in diskussionen)
    assert any(st.gruppe == 2 for st in liste)
    wissen = next(st for st in liste if "wissen" in st.pruefung)
    assert wissen.sage == inv.WISSENSFRAGE
    assert all(p in s.PRUEFUNGEN for p in pruefungen)


def test_kalibrierung_hat_budget_fuer_einen_ganzen_raumcheck():
    """Abnahmelauf 05.10.2026: 6 Schritte reichten fuer einen vollstaendigen
    Raumcheck mit verstuemmeltem Testsatz nicht."""
    for liste in (s.STATIONEN_P12, s.STATIONEN_INVARIANTEN):
        kal = next(st for st in liste if st.schluessel == "p1-kalibrierung")
        assert kal.budget == 10
    kal = next(st for st in s.STATIONEN_INVARIANTEN if st.schluessel == "p1-kalibrierung")
    assert "raumcheck" in kal.pruefung
    # Merge-Nachtrag 06.10.2026: Phase 4 teilt sich das Diskussions-Gate mit
    # Phase 1 (siehe Kommentar vor STATIONEN_P34) -- derselbe Budget-Bedarf.
    p4_kal = next(st for st in s.STATIONEN_P34 if st.schluessel == "p4-kalibrierung")
    assert p4_kal.budget == 10
    assert p4_kal.zuhoeren_s == 0  # Default: der blockierende Zuhoer-Takt greift hier nie


def test_p12_prueft_nach_ende_und_p2_werkbank():
    p12 = {st.schluessel: st for st in s.STATIONEN_P12}
    assert "nach_ende" in p12["p1-zuhoeren"].pruefung
    assert "p2_werkbank" in p12["p2-einzeldurchgang"].pruefung


# --- Task 2: Stationen p34 (Interviews, Übergang 3→4, Brainstorm, Rahmen, Angebot 5) ---

from interview_theater import aufnahme, brainstorm


def test_stationen_p34_vollstaendig_und_geordnet():
    schluessel = [st.schluessel for st in s.STATIONEN["p34"]]
    assert schluessel == [
        "p3-eintritt", "p3-interview-kurz", "p3-interview-gemischt", "p3-uebergang",
        "p4-eintritt", "p4-kalibrierung", "p4-brainstorm", "p4-setting-figuren",
        "p4-geschichte", "p4-uebergang"]
    phasen = [st.phase for st in s.STATIONEN_P34]
    assert phasen == sorted(phasen) and set(phasen) == {3, 4}
    assert s.STARTPHASE["p12"] == 1
    assert s.STARTPHASE["invarianten"] == 1
    assert s.STARTPHASE["p34"] == 3


def test_p34_aufnahmestationen_haben_skript_und_pruefung():
    st = {x.schluessel: x for x in s.STATIONEN_P34}
    for name in ("p3-interview-kurz", "p3-interview-gemischt"):
        assert st[name].aufnahme == "interview" and st[name].diskussion in DISKUSSIONEN
        assert "nach_interview" in st[name].pruefung
    assert st["p4-brainstorm"].aufnahme == "brainstorm"
    assert "nach_brainstorm" in st["p4-brainstorm"].pruefung
    assert "modellwahl" in st["p3-uebergang"].pruefung
    assert "p5_angebot" in st["p4-uebergang"].pruefung
    # I4 (Review 05.10.2026, Fix round 1): ``modellwahl`` lief bisher NUR an
    # p3-uebergang -- zu diesem Zeitpunkt ist noch keine Phase-4-Station
    # gelaufen, der Phase-4-Bereich also immer leer, P4_GESPRAECH_NICHT_OPUS
    # konnte nie feuern. Jetzt auch am Ende von Phase 4.
    assert "modellwahl" in st["p4-uebergang"].pruefung
    assert all(p in s.PRUEFUNGEN for x in s.STATIONEN_P34 for p in x.pruefung)


def test_p34_skripte_treffen_die_schwellen():
    # kurz: unter der Mindestlaenge (darf Phase 4 nicht sperren),
    # gemischt: darueber (wird verdichtet), Bogen: ueber der Abschlussschwelle.
    assert len(DISKUSSIONEN["interview-kurz"].text().split()) < aufnahme.MINDEST_WOERTER
    assert len(DISKUSSIONEN["interview-gemischt"].text().split()) >= aufnahme.MINDEST_WOERTER
    assert DISKUSSIONEN["brainstorm-bogen"].zeichen() >= brainstorm.VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS


def test_selektoren_je_aufnahmeart():
    # Birk 05.10.2026 22:00: kein Toggle mehr -- Brainstorm (Phase 4) bedient
    # sich ueber denselben Knopf wie Diskussion (Phase 1), ``#diskussion``/
    # ``#diskussion-beenden``, mit eigenem Stationstyp "brainstorm" (fuer
    # ``Station.aufnahme``/die Pruef-Haken) aber denselben Selektoren.
    assert set(s.LAEUFT) == set(s.ENDE) == {"diskussion", "interview", "brainstorm"}
    assert s.LAEUFT["interview"] == '#interview[data-laeuft="1"]'
    assert s.ENDE["diskussion"] == "#diskussion-beenden"
    assert s.ENDE["interview"] == "#interview-beenden"
    assert s.LAEUFT["brainstorm"] == s.LAEUFT["diskussion"] == '#diskussion[data-laeuft="1"]'
    assert s.ENDE["brainstorm"] == s.ENDE["diskussion"] == "#diskussion-beenden"


def test_p4_brainstorm_ziel_nennt_denselben_knopf_wie_phase1():
    """Der Zieltext darf nicht mehr von einem einzelnen Gedanken/Tipp
    sprechen (das alte Toggle-Bild), sondern von "Start listening"/
    "Discussion done" wie Phase 1. Der moegliche Raumcheck hat seit dem
    Merge mit main (06.10.2026, Kill-Switch-Umbau) eine eigene Station davor
    (``p4-kalibrierung``, mirrors ``p1-kalibrierung``) -- genau wie
    "p1-zuhoeren" ihn seit "p1-kalibrierung" existiert auch nicht mehr selbst
    erwaehnt, erwaehnt "p4-brainstorm" ihn jetzt auch nicht mehr."""
    st = {x.schluessel: x for x in s.STATIONEN_P34}
    ziel = st["p4-brainstorm"].ziel.casefold()
    assert "start listening" in ziel
    assert "discussion done" in ziel
    assert "tap" not in ziel and "thought is complete" not in ziel


# --- Task 2 (BRIEF p57): Stationen p57 (Phase 5-7, Prose Draft/Rewrite/Stage) ---


def test_stationen_p57_vollstaendig_und_geordnet():
    schluessel = [st.schluessel for st in s.STATIONEN["p57"]]
    assert schluessel == [
        "p5-eintritt", "p5-schaerfung", "p5-uebersicht", "p5-szenen",
        "p6-gesamt", "p6-szenen", "p7-formen", "p7-sprechweisen",
        "p7-szenen", "p7-schluss"]
    phasen = [st.phase for st in s.STATIONEN_P57]
    assert phasen == sorted(phasen) and set(phasen) == {5, 6, 7}
    assert s.STARTPHASE["p57"] == 5


def test_stationen_p57_gesamtbudget_unter_der_grenze():
    """Risiko-Vorgabe im Plan: Gesamtbudget <= 80 Schritte, sonst verlaengert
    sich der Lauf (> 30 min, muss in den Hintergrund)."""
    assert sum(st.budget for st in s.STATIONEN_P57) <= 80


def test_stationen_p57_geduld_600_ausser_eintritt():
    for st in s.STATIONEN_P57:
        if st.schluessel == "p5-eintritt":
            assert st.geduld_s == 90.0
        else:
            assert st.geduld_s == 600


def test_stationen_p57_pruefungen_bekannt():
    pruefungen = {p for st in s.STATIONEN_P57 for p in st.pruefung}
    assert pruefungen <= set(s.PRUEFUNGEN)
    assert "p5_schaerfung" in pruefungen and "p5_uebersicht" in pruefungen
    assert "prueflauf" in pruefungen and "chat_volltext" in pruefungen
    assert "sprung" in pruefungen and "kuerzung" in pruefungen
    assert "formen" in pruefungen and "stueckpruefung" in pruefungen
    assert "textbuch" in pruefungen


def test_stationen_p57_ziele_statt_rezepte():
    for st in s.STATIONEN_P57:
        assert not REZEPT.search(st.ziel), (st.schluessel, st.ziel)


def test_p5_eintritt_wartet_auf_schaerfung_oder_uebersicht():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-eintritt")
    assert st.warte_bis({"schaerfung_zeilen": 1}) is True
    assert st.warte_bis({"arbeitsstand": {"geschichte_uebersicht": "x"}}) is True
    assert st.warte_bis({"schaerfung_zeilen": 0, "arbeitsstand": {}}) is False


def test_p5_schaerfung_fertig_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-schaerfung")
    assert not st.fertig({"schaerfung_uebernommen": 0, "arbeitsstand": {}})
    assert st.fertig({"schaerfung_uebernommen": 1, "arbeitsstand": {}})
    assert st.fertig({"schaerfung_uebernommen": 0,
                      "arbeitsstand": {"geschichte_uebersicht_fixiert_am": "x"}})


def test_p5_uebersicht_fertig_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-uebersicht")
    assert not st.fertig({"arbeitsstand": {}})
    assert st.fertig({"arbeitsstand": {"geschichte_uebersicht_fixiert_am": "2026-10-06"}})


def test_p5_szenen_fertig_praedikat_phasensprung():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-szenen")
    assert not st.fertig({"arbeitsstand": {"phase": 5}})
    assert st.fertig({"arbeitsstand": {"phase": 6}})
    assert st.endet_bei_phasenwechsel is True


def test_p6_gesamt_fertig_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p6-gesamt")
    assert not st.fertig({"arbeitsstand": {}})
    assert st.fertig({"arbeitsstand": {"gesamttext_fixiert_am": "2026-10-06"}})


def test_p6_szenen_fertig_praedikat_phasensprung():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p6-szenen")
    assert not st.fertig({"arbeitsstand": {"phase": 6}})
    assert st.fertig({"arbeitsstand": {"phase": 7}})
    assert st.endet_bei_phasenwechsel is True


def test_p7_formen_fertig_praedikat_zaehlt_inhalt_nicht_nur_laenge():
    """Lehre B-neu-2: 'alle Szenen haben eine Form' muss an der tatsaechlichen
    Szenenzahl gemessen werden, nicht an einer festen Zahl -- sonst meldet
    das Praedikat bei EINER fehlenden Form trotzdem faelschlich fertig."""
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-formen")
    assert not st.fertig({"szenen_mit_form": 2, "szenen_anzahl": 3})
    assert st.fertig({"szenen_mit_form": 3, "szenen_anzahl": 3})
    assert not st.fertig({"szenen_mit_form": 0, "szenen_anzahl": 0})  # keine Szenen = nicht fertig


def test_p7_sprechweisen_fertig_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-sprechweisen")
    assert not st.fertig({"arbeitsstand": {}})
    assert st.fertig({"arbeitsstand": {"sprechweisen_fixiert_am": "2026-10-06"}})


def test_p7_szenen_fertig_praedikat_zaehlt_inhalt_nicht_nur_laenge():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-szenen")
    assert not st.fertig({"szenen_fertig": 2, "szenen_anzahl": 3})
    assert st.fertig({"szenen_fertig": 3, "szenen_anzahl": 3})
    assert not st.fertig({"szenen_fertig": 0, "szenen_anzahl": 0})


def test_p7_schluss_fertig_praedikat_und_leitbild_tab():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-schluss")
    assert not st.fertig({"stueckpruefung_zeilen": 0})
    assert st.fertig({"stueckpruefung_zeilen": 1})
    assert st.leitbild_tab == "textbuch"


# --- Review-Fix (06.10.2026, P57-Harness): warte_bis fuer alle zehn --------


def test_alle_p57_stationen_haben_warte_bis():
    """Vorher hatte nur ``p5-eintritt`` ein ``warte_bis`` -- die anderen neun
    lasen den Nachher-Stand sofort nach ``_ANLAUF_S`` (3s), obwohl keines der
    Hintergrund-Module dieser Phasen ``tg.tippt()`` ruft (Begruendung am
    Feld ``Station.geduld_s``)."""
    for st in s.STATIONEN_P57:
        assert st.warte_bis is not None, st.schluessel


def test_p5_schaerfung_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-schaerfung")
    assert not st.warte_bis({"schaerfung_uebernommen": 0, "arbeitsstand": {}})
    assert st.warte_bis({"schaerfung_uebernommen": 1, "arbeitsstand": {}})
    assert st.warte_bis({"schaerfung_uebernommen": 0,
                         "arbeitsstand": {"geschichte_uebersicht_fixiert_am": "x"}})


def test_p5_uebersicht_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-uebersicht")
    assert not st.warte_bis({"arbeitsstand": {}})
    assert st.warte_bis({"arbeitsstand": {"geschichte_uebersicht_fixiert_am": "2026-10-06"}})


def test_p5_szenen_warte_bis_erkennt_jede_einzelne_szene():
    """Der Clou gegenueber ``fertig`` (das erst beim Phasensprung wahr wird):
    ``warte_bis`` muss schon JEDEN Zwischenschritt erkennen -- sonst wuerde
    der Harness bei einer 14-Schritte-Schleife auf jedem Schritt bis
    ``geduld_s`` (600s) warten, statt sofort weiterzulesen, sobald die
    naechste Szene entworfen ist."""
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p5-szenen")
    # Weder entworfen noch abgenommen: noch nichts zu lesen.
    assert not st.warte_bis({"szenen_mit_prosa": 0, "szenen_entwurf_ok": 0, "szenen_anzahl": 3,
                             "arbeitsstand": {"phase": 5}})
    # Szene 1 ist entworfen (mehr Prosa als Abnahmen) -- bereit zum Lesen.
    assert st.warte_bis({"szenen_mit_prosa": 1, "szenen_entwurf_ok": 0, "szenen_anzahl": 3,
                         "arbeitsstand": {"phase": 5}})
    # Szene 1 abgenommen, Szene 2 noch nicht entworfen: wieder warten.
    assert not st.warte_bis({"szenen_mit_prosa": 1, "szenen_entwurf_ok": 1, "szenen_anzahl": 3,
                             "arbeitsstand": {"phase": 5}})
    # Alle abgenommen (Phasensprung schon gesetzt oder Zaehler voll): fertig.
    assert st.warte_bis({"szenen_mit_prosa": 3, "szenen_entwurf_ok": 3, "szenen_anzahl": 3,
                         "arbeitsstand": {"phase": 6}})


def test_p6_gesamt_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p6-gesamt")
    assert not st.warte_bis({"arbeitsstand": {}})
    assert st.warte_bis({"arbeitsstand": {"gesamttext_fixiert_am": "2026-10-06"}})


def test_p6_szenen_warte_bis_praedikat_phasensprung():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p6-szenen")
    assert not st.warte_bis({"szenen_ueberarbeitung_ok": 1, "szenen_anzahl": 3,
                             "arbeitsstand": {"phase": 6}})
    assert st.warte_bis({"szenen_ueberarbeitung_ok": 3, "szenen_anzahl": 3,
                         "arbeitsstand": {"phase": 6}})
    assert st.warte_bis({"szenen_ueberarbeitung_ok": 0, "szenen_anzahl": 3,
                         "arbeitsstand": {"phase": 7}})


def test_p7_formen_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-formen")
    assert not st.warte_bis({"szenen_mit_form": 2, "szenen_anzahl": 3})
    assert st.warte_bis({"szenen_mit_form": 3, "szenen_anzahl": 3})
    assert not st.warte_bis({"szenen_mit_form": 0, "szenen_anzahl": 0})


def test_p7_sprechweisen_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-sprechweisen")
    assert not st.warte_bis({"arbeitsstand": {}})
    assert st.warte_bis({"arbeitsstand": {"sprechweisen_fixiert_am": "2026-10-06"}})


def test_p7_szenen_warte_bis_erkennt_jede_einzelne_szene():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-szenen")
    assert not st.warte_bis({"szenen_mit_volltext": 0, "szenen_fertig": 0, "szenen_anzahl": 3})
    # Szene 1 uebertragen (mehr Buehnentext als Abnahmen) -- bereit zum Lesen.
    assert st.warte_bis({"szenen_mit_volltext": 1, "szenen_fertig": 0, "szenen_anzahl": 3})
    # Szene 1 abgenommen, Szene 2 noch nicht uebertragen: wieder warten.
    assert not st.warte_bis({"szenen_mit_volltext": 1, "szenen_fertig": 1, "szenen_anzahl": 3})
    assert st.warte_bis({"szenen_mit_volltext": 3, "szenen_fertig": 3, "szenen_anzahl": 3})


def test_p7_schluss_warte_bis_praedikat():
    st = next(x for x in s.STATIONEN_P57 if x.schluessel == "p7-schluss")
    assert not st.warte_bis({"stueckpruefung_zeilen": 0})
    assert st.warte_bis({"stueckpruefung_zeilen": 1})


def test_p4_kalibrierung_station_mirrors_p1_kalibrierung():
    """Merge-Nachtrag 06.10.2026: mit dem Kill-Switch per Vorgabe AN und
    einem Lauf, der in Phase 3 startet (kein Cache aus einer vorherigen
    Phase-1-Diskussion), kann der Raumcheck-Dialog beim ersten
    ``#diskussion``-Start in Phase 4 tatsaechlich erscheinen -- derselbe
    Dialog, dasselbe Gate wie in Phase 1 (``beginneAufnahme``,
    ``sitzung.art === 'diskussion'``)."""
    st = {x.schluessel: x for x in s.STATIONEN_P34}
    kal = st["p4-kalibrierung"]
    assert kal.phase == 4
    assert "room" in kal.ziel.casefold()
    assert kal.fertig is not None
    assert not kal.fertig({"kalibrierung_aufnahmen": 0, "kalibrierung_modus": None})
    assert kal.fertig({"kalibrierung_aufnahmen": 1, "kalibrierung_modus": None})
    assert kal.fertig({"kalibrierung_aufnahmen": 0, "kalibrierung_modus": "herumreichen"})
    # Station liegt zwischen p4-eintritt und p4-brainstorm.
    schluessel = [x.schluessel for x in s.STATIONEN_P34]
    assert schluessel.index("p4-eintritt") < schluessel.index("p4-kalibrierung") \
        < schluessel.index("p4-brainstorm")

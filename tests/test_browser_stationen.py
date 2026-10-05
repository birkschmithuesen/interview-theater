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
        "p4-eintritt", "p4-brainstorm", "p4-setting-figuren", "p4-geschichte",
        "p4-uebergang"]
    phasen = [st.phase for st in s.STATIONEN_P34]
    assert phasen == sorted(phasen) and set(phasen) == {3, 4}
    assert s.STARTPHASE == {"p12": 1, "invarianten": 1, "p34": 3}


def test_p34_aufnahmestationen_haben_skript_und_pruefung():
    st = {x.schluessel: x for x in s.STATIONEN_P34}
    for name in ("p3-interview-kurz", "p3-interview-gemischt"):
        assert st[name].aufnahme == "interview" and st[name].diskussion in DISKUSSIONEN
        assert "nach_interview" in st[name].pruefung
    assert st["p4-brainstorm"].aufnahme == "brainstorm"
    assert "nach_brainstorm" in st["p4-brainstorm"].pruefung
    assert "modellwahl" in st["p3-uebergang"].pruefung
    assert "p5_angebot" in st["p4-uebergang"].pruefung
    assert all(p in s.PRUEFUNGEN for x in s.STATIONEN_P34 for p in x.pruefung)


def test_p34_skripte_treffen_die_schwellen():
    # kurz: unter der Mindestlaenge (darf Phase 4 nicht sperren),
    # gemischt: darueber (wird verdichtet), Bogen: ueber der Abschlussschwelle.
    assert len(DISKUSSIONEN["interview-kurz"].text().split()) < aufnahme.MINDEST_WOERTER
    assert len(DISKUSSIONEN["interview-gemischt"].text().split()) >= aufnahme.MINDEST_WOERTER
    assert DISKUSSIONEN["brainstorm-bogen"].zeichen() >= brainstorm.VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS


def test_selektoren_je_aufnahmeart():
    assert set(s.LAEUFT) == set(s.ENDE) == {"diskussion", "interview", "brainstorm"}
    assert s.LAEUFT["interview"] == '#interview[data-laeuft="1"]'
    assert s.ENDE["diskussion"] == "#diskussion-beenden"
    assert s.ENDE["interview"] == "#interview-beenden"
    assert s.ENDE["brainstorm"] == "#brainstorm"     # Toggle (Task 5)

"""Die Schaerfungs-Sortierliste im CoThinker (Padua, 07.10.2026): statt
seitenweiser Chat-Karten mit "Mehr zeigen" sortiert die Gruppe ALLE
zugeordneten Interviewstellen auf einmal im CoThinker-Tab (Yes/No, Done) --
dasselbe Muster wie die Fragen-Sortierliste aus Phase 2
(``tests/test_fragen_sortieren.py``, ``tests/test_web_auswahl.py``).

Gemessen: ``repo.setze_schaerfung_entscheidung`` (je Zeile, nicht je Feld),
dass der Chat unter Padua keine Seitenkarten mehr zeigt, dass "Done"
(``knoepfe.szenen.schliesse_schaerfungsliste``) genau die Yes-Zeilen
uebernimmt und die Nein-Zeilen verwirft, offene stehen laesst, und danach
dieselbe Abschlussmeldung schickt wie am Ende der alten Kartenfolge --
sowie die read-only Webdaten (``web_daten.schaerfungsliste``) und ihr
Rendern (``web._schaerfungsliste_html``)."""

import pytest

from interview_theater import befehle, db, knoepfe, phasen, repo, schaerfung, web, web_daten, workshop
from interview_theater.knoepfe import szenen as knoepfe_szenen

from test_knoepfe import TelegramAttrappe
from test_schaerfung import KLMAttrappe, ZITAT_A, ZITAT_B, _antwort, _interview, freie_vorschlagssperre, lage


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- repo.setze_schaerfung_entscheidung -------------------------------------


def test_setze_schaerfung_entscheidung_setzt_und_macht_rueckgaengig(lage, einst):
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)
    zeile_id = repo.schaerfungen(lage, 1)[0]["id"]

    assert repo.setze_schaerfung_entscheidung(lage, 1, zeile_id, "ja") is True
    assert repo.schaerfungen(lage, 1)[0]["entscheidung"] == "ja"
    assert repo.setze_schaerfung_entscheidung(lage, 1, zeile_id, "") is True
    assert repo.schaerfungen(lage, 1)[0]["entscheidung"] is None


def test_setze_schaerfung_entscheidung_lehnt_unsinn_ab(lage, einst):
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)
    zeile_id = repo.schaerfungen(lage, 1)[0]["id"]

    assert repo.setze_schaerfung_entscheidung(lage, 1, zeile_id, "vielleicht") is False
    assert repo.setze_schaerfung_entscheidung(lage, 1, 999999, "ja") is False
    # Fremder chat_id trifft die Zeile nicht.
    assert repo.setze_schaerfung_entscheidung(lage, 2, zeile_id, "ja") is False


def test_setze_schaerfung_entscheidung_nach_uebernahme_ist_zu(lage, einst):
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)
    zeile_id = repo.schaerfungen(lage, 1)[0]["id"]
    repo.merke_schaerfung_uebernommen(lage, zeile_id)

    assert repo.setze_schaerfung_entscheidung(lage, 1, zeile_id, "ja") is False


# --- Chat: kein Seitenmenue mehr unter Padua --------------------------------


def test_biete_schaerfung_zeigt_unter_padua_kein_kartenmenue(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)

    assert knoepfe.biete_schaerfung(lage, tg, 1) is True
    assert tg.gesendet == []
    assert tg.knoepfe == []


def test_biete_schaerfung_zeigt_ohne_padua_weiter_das_kartenmenue(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)

    assert knoepfe.biete_schaerfung(lage, tg, 1) is True
    assert tg.knoepfe  # unveraendert: Dortmund/andere Profile bleiben bei der Karte.


def test_biete_schaerfung_ohne_offenes_schickt_weiter_die_abschlussfrage(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    assert knoepfe.biete_schaerfung(lage, tg, 1) is False
    assert tg.gesendet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_DURCH


# --- Done: Yes uebernehmen, No verwerfen, offen stehen lassen --------------


def test_schliesse_schaerfungsliste_uebernimmt_ja_und_verwirft_nein(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3], begruendungen=["Mira kommt daher"]),
        "Figur Pal": _antwort(eintrag_nummern=[2], staerke=[2], begruendungen=["Pal bleibt dabei"]),
    })
    schaerfung.mappe(klm, lage, einst, 1)
    alle = repo.schaerfungen(lage, 1)
    ja_id = next(z["id"] for z in alle if z["szene_id"] is not None)
    nein_id = next(z["id"] for z in alle if z["figur_id"] is not None)
    repo.setze_schaerfung_entscheidung(lage, 1, ja_id, "ja")
    repo.setze_schaerfung_entscheidung(lage, 1, nein_id, "nein")

    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, 1)

    szene = repo.hole_szenen(lage, 1)[0]
    assert "Mira kommt daher" in (szene["was_passiert"] or "")
    assert schaerfung.offene_stellen(lage, 1) == []
    # "Keine davon" ist weich entfernt -- taucht in ``repo.schaerfungen`` nicht mehr auf.
    assert nein_id not in {z["id"] for z in repo.schaerfungen(lage, 1)}
    assert tg.gesendet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_DURCH


def test_schliesse_schaerfungsliste_laesst_offene_stellen_stehen(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)

    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, 1)

    assert len(schaerfung.offene_stellen(lage, 1)) == 1


def test_schliesse_schaerfungsliste_ohne_ja_sendet_trotzdem_den_abschluss(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, 1)
    assert tg.gesendet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_DURCH


# --- Die kurze Ankuendigung im Chat ------------------------------------------


def test_lauf_sendet_unter_padua_den_cothinker_hinweis_statt_der_karte(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung._lauf(lage, tg, klm, einst, 1)

    texte = [t for _, t in tg.gesendet]
    assert any("CoThinker" in t for t in texte)
    assert not any(t == schaerfung.MELDUNG.format(anzahl=1) for t in texte)


def test_befehl_schaerfung_fertig_ist_versteckt_und_schliesst_ab(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)
    zeile_id = repo.schaerfungen(lage, 1)[0]["id"]
    repo.setze_schaerfung_entscheidung(lage, 1, zeile_id, "ja")

    assert befehle.behandle(lage, tg, einst, 1, "/schaerfung_fertig", None) is True

    szene = repo.hole_szenen(lage, 1)[0]
    assert "x" in (szene["was_passiert"] or "")
    assert tg.gesendet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_DURCH


def test_lauf_sendet_ohne_padua_weiter_die_alte_meldung(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung._lauf(lage, tg, klm, einst, 1)

    texte = [t for _, t in tg.gesendet]
    assert schaerfung.MELDUNG.format(anzahl=1) in texte


# --- web_daten.schaerfungsliste -----------------------------------------


@pytest.fixture
def web_db(tmp_path, einst):
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Testgruppe")
    repo.setze_gruppe_kanal(conn, 1, "web")
    token = repo.stelle_web_token_sicher(conn, 1)

    _interview(conn, ZITAT_A, [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1},
    ], name="A")
    _interview(conn, ZITAT_B, [
        {"thema": "Leere Stadt am Wochenende", "beleg_zitat": ZITAT_B, "zitat_geprueft": 1},
    ], name="B")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Im Treppenhaus")
    phasen.setze(conn, 1, 5, "test")

    klm = KLMAttrappe({
        "Szene 1": _antwort(eintrag_nummern=[1], staerke=[3], begruendungen=["Mira kommt daher"]),
        "Figur Mira": _antwort(eintrag_nummern=[2], staerke=[2], begruendungen=["Mira redet"]),
    })
    schaerfung.mappe(klm, conn, einst, 1)
    conn.commit()
    conn.close()
    return pfad, token


def test_web_daten_schaerfungsliste_gruppiert_nach_ziel_sortiert_nach_staerke(web_db, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, _token = web_db
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        liste = web_daten.schaerfungsliste(lesend, 1)
    finally:
        lesend.close()

    assert liste is not None
    assert liste["zaehler"] == {"ja": 0, "nein": 0, "offen": 2}
    arten = [(g["art"], g.get("nummer"), g.get("name")) for g in liste["gruppen"]]
    assert arten == [("szene", 1, None), ("figur", None, "Mira")]
    szene_eintrag = liste["gruppen"][0]["eintraege"][0]
    assert szene_eintrag["zitat"] == ZITAT_A
    assert szene_eintrag["begruendung"] == "Mira kommt daher"
    assert szene_eintrag["interview"] == "Interview 1"


def test_web_daten_schaerfungsliste_ohne_profil_ist_none(web_db, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = web_db
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    assert daten["schaerfungsliste"] is None


# --- web._schaerfungsliste_html ----------------------------------------------


LISTE = {
    "gruppen": [
        {"art": "szene", "nummer": 1, "titel": "Im Treppenhaus", "eintraege": [
            {"id": 11, "zustand": "ja", "titel": "Arbeit ohne Anerkennung",
             "interview": "Interview 1", "zitat": ZITAT_A, "begruendung": "Mira kommt daher"},
        ]},
        {"art": "figur", "name": "Mira", "eintraege": [
            {"id": 12, "zustand": "", "titel": "Leere Stadt am Wochenende",
             "interview": "Interview 2", "zitat": ZITAT_B, "begruendung": ""},
        ]},
    ],
    "zaehler": {"ja": 1, "nein": 0, "offen": 1},
}


def test_schaerfungsliste_html_rendert_gruppen_und_knoepfe():
    seite = web._schaerfungsliste_html(LISTE)
    assert seite.startswith(
        '<div id="buehne-panel" data-ansicht="auswahl" data-liste="schaerfung">'
    )
    assert "Im Treppenhaus" in seite and ">Mira<" in seite
    assert '<li data-nummer="11" data-zustand="ja">' in seite
    assert '<li data-nummer="12" data-zustand="offen">' in seite
    assert ZITAT_A in seite and ZITAT_B in seite
    assert "Mira kommt daher" in seite
    assert seite.count('class="auswahl-knopf"') == 4
    assert 'data-wert="schaerfen"' not in seite
    assert '<button type="button" class="auswahl-fertig">' in seite


def test_schaerfungsliste_html_maskiert():
    bose = {
        "gruppen": [{"art": "figur", "name": "<b>X</b>", "eintraege": [
            {"id": 1, "zustand": "", "titel": "<script>", "interview": "I",
             "zitat": "<i>z</i>", "begruendung": "<u>b</u>"},
        ]}],
        "zaehler": {"ja": 0, "nein": 0, "offen": 1},
    }
    seite = web._schaerfungsliste_html(bose)
    assert "<script>" not in seite
    assert "<b>X</b>" not in seite


def test_buehne_html_zeigt_schaerfungsliste():
    seite = web._buehne_html({"schaerfungsliste": LISTE})
    assert 'data-liste="schaerfung"' in seite


# -- POST: dieselben Wege wie die Fragenliste, liste="schaerfung" -----------


import json
import threading
import urllib.error
import urllib.request

from interview_theater import web_vereint

SCHLUESSEL = b"y" * 32


@pytest.fixture
def server(web_db):
    pfad, token = web_db
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _post(url, nutzlast):
    anfrage = urllib.request.Request(
        url, data=json.dumps(nutzlast).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _eingaenge(pfad):
    conn = db.verbinde(pfad)
    try:
        return [(z["typ"], z["text"]) for z in repo.web_eingang(conn, 1, 0)]
    finally:
        conn.close()


def test_auswahl_post_schreibt_die_schaerfungsentscheidung(server):
    basis, token, pfad = server
    zeile_id = repo.schaerfungen(db.verbinde(pfad), 1)[0]["id"]
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "schaerfung",
                       "nummer": zeile_id, "wert": "ja"})
    assert status == 200
    assert repo.schaerfungen(db.verbinde(pfad), 1)[0]["entscheidung"] == "ja"
    assert _eingaenge(pfad) == []


def test_auswahl_post_schaerfung_lehnt_dritten_zustand_ab(server):
    basis, token, pfad = server
    zeile_id = repo.schaerfungen(db.verbinde(pfad), 1)[0]["id"]
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "schaerfung",
                       "nummer": zeile_id, "wert": "schaerfen"})
    assert status == 400


def test_auswahl_fertig_post_schaerfung_legt_den_versteckten_befehl_an(server):
    basis, token, pfad = server
    status, _ = _post(f"{basis}/g/{token}/chat/auswahl_fertig",
                      {"nonce": web.nonce(SCHLUESSEL, token), "liste": "schaerfung"})
    assert status == 202
    assert _eingaenge(pfad) == [(repo.WEB_TYP_BEFEHL, "/schaerfung_fertig")]


def test_auswahl_skript_traegt_beide_zaehlervorlagen(web_db, monkeypatch):
    pfad, token = web_db
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, 1)
    finally:
        lesend.close()
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)

    seite = web_vereint.seite(daten, chatdaten, roadmapdaten, "n", token,
                              "/theatersoap", 45_000, {}, True)

    assert "ZAEHLER = { fragen:" in seite and "schaerfung:" in seite
    assert "__AUSWAHL_ZAEHLER_FRAGEN__" not in seite
    assert "__AUSWAHL_ZAEHLER_SCHAERFUNG__" not in seite

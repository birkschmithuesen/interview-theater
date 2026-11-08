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

    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)

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

    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)

    assert len(schaerfung.offene_stellen(lage, 1)) == 1


def test_schliesse_schaerfungsliste_ohne_ja_sendet_trotzdem_den_abschluss(lage, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
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


# --- Padua Entry-Umbau (07.10.2026, "Entry zu voll"): zwei Knoepfe statt --
# Text, die Geschichts-Uebersicht erst nach "Done" --------------------------


def test_lauf_unter_padua_bietet_zwei_knoepfe_statt_nur_text(lage, tg, einst, monkeypatch):
    """Birk Live-Test 07.10.2026: die automatische Zuordnung beim Eintritt
    soll NICHT mehr nur eine Textzeile schicken, sondern die Wahl zwischen
    Sortieren und Reden -- derselbe Text wie vorher, jetzt mit Leiste."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung._lauf(lage, tg, klm, einst, 1)

    assert tg.knoepfe, "keine Leiste unter der Zuordnungs-Meldung"
    text, leiste = tg.knoepfe[-1][1], tg.knoepfe[-1][2]
    assert text == schaerfung.MELDUNG_COTHINKER.format(anzahl=1)
    beschriftungen = [b for b, _ in leiste]
    assert beschriftungen == [
        knoepfe_szenen.T.TEXT_SCHAERFUNG_SORTIEREN_KNOPF,
        knoepfe_szenen.T.TEXT_SCHAERFUNG_CHAT_KNOPF,
    ]


def test_lauf_ohne_zuordnung_zeigt_weiterhin_nur_text(lage, tg, einst, monkeypatch):
    """Ohne eine einzige Zuordnung (``anzahl == 0``) gibt es nichts zu
    sortieren -- die Leiste bleibt weg, ``MELDUNG_LEER`` bleibt Text."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe()
    schaerfung._lauf(lage, tg, klm, einst, 1)

    assert tg.knoepfe == []
    assert any(t == schaerfung.MELDUNG_LEER for _, t in tg.gesendet)


def test_wirkung_schaerfung_sortieren_ist_reine_bestaetigung(lage, tg, einst, monkeypatch):
    from interview_theater.knoepfe import wirkung
    from test_knoepfe import _druck

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    knopf_id = repo.lege_knopf_an(lage, 1, knoepfe_szenen.ART_SCHAERFUNG_SORTIEREN, None)
    druck = _druck(wirkung._daten(knopf_id), chat_id=1, message_id=42)

    assert wirkung.behandle(lage, tg, None, einst, druck) is True
    assert tg.beantwortet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_SORTIEREN_NOTIERT
    # Reine Bestaetigung: kein zusaetzlicher Chat-Text, keine Datenaenderung.
    assert tg.gesendet == []


def test_wirkung_schaerfung_chat_stoesst_zusammenfassung_an(lage, tg, einst, monkeypatch):
    from interview_theater.knoepfe import wirkung
    from test_knoepfe import _druck

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe()
    knopf_id = repo.lege_knopf_an(lage, 1, knoepfe_szenen.ART_SCHAERFUNG_CHAT, None)
    druck = _druck(wirkung._daten(knopf_id), chat_id=1, message_id=42)

    assert wirkung.behandle(lage, tg, klm, einst, druck) is True
    assert tg.beantwortet[-1][1] == knoepfe_szenen.T._TEXT_SCHAERFUNG_CHAT_NOTIERT


def test_schliesse_schaerfungsliste_stoesst_uebersicht_nur_einmal_an(lage, tg, einst, monkeypatch):
    """Done -> Stufe-A-Uebersicht (``entwurf.starte_uebersicht``), aber nur
    solange sie noch nicht fixiert ist -- ein spaeteres Done (nach "Noch
    eine Runde") darf eine schon abgenommene Uebersicht nicht ueberschreiben
    und damit eine laufende Stufe B nicht gefaehrden."""
    from interview_theater import entwurf

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    aufrufe = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht",
        lambda *a, **k: aufrufe.append(1),
    )
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)

    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert len(aufrufe) == 1

    # Die Gruppe hat die Uebersicht inzwischen abgenommen ("Yes, save").
    repo.setze_arbeitsstand(lage, 1, "geschichte_uebersicht_fixiert_am", repo._jetzt())
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert len(aufrufe) == 1, "Done nach Fixierung darf die Uebersicht nicht neu anstossen"


class _ZusammenfassungKLM:
    """Traegt nur ``.schema()`` -- genug fuer
    ``schaerfung.starte_zusammenfassung``/``modellwahl.aufruf_schema``."""

    def __init__(self, text: str):
        self.text = text
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return {"zusammenfassung": self.text}


def test_lauf_zusammenfassung_schickt_den_text_in_den_chat(lage, tg, einst):
    klm = _ZusammenfassungKLM("Acht Interviews, Thema Arbeit ohne Anerkennung.")

    schaerfung._lauf_zusammenfassung(lage, tg, klm, einst, 1)

    assert tg.gesendet[-1][1] == "Acht Interviews, Thema Arbeit ohne Anerkennung."
    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Interview 1" in nutzer
    assert "Arbeit ohne Anerkennung" in nutzer


def test_lauf_zusammenfassung_ohne_material_meldet_das_statt_zu_rufen(tg, einst, conn):
    klm = _ZusammenfassungKLM("sollte nie ankommen")

    schaerfung._lauf_zusammenfassung(conn, tg, klm, einst, 1)

    assert klm.aufrufe == []
    assert tg.gesendet[-1][1] == schaerfung.T.MELDUNG_OHNE_MATERIAL


def test_eintritt_phase_5_unter_padua_stoesst_uebersicht_nicht_automatisch_an(
    lage, tg, einst, monkeypatch,
):
    """Birk Live-Test 07.10.2026 ("Entry zu voll"): Eintrittskarte, CoThinker-
    Hinweis mit Knoepfen -- aber NICHT mehr automatisch die Logline-
    Uebersicht mit Yes/No. Die kommt jetzt erst nach "Done" (siehe oben)."""
    from interview_theater import entwurf, knoepfe, vorschlagssperre

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    aufrufe = []
    monkeypatch.setattr(entwurf, "starte_uebersicht", lambda *a, **k: aufrufe.append(1))
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3],
                                           begruendungen=["x"])})

    knoepfe.eintritt_in_phase(lage, tg, klm, einst, 1, 5)

    # Das Mapping laeuft im Thread (``schaerfung.starte``) -- derselbe
    # Wartepfad wie ``tests/test_entwurf_ablauf.py``s ``_warte``, nur ueber
    # die gemeinsame Vorschlagssperre statt ``entwurf._sperre_fuer``.
    sperre = vorschlagssperre.sperre_fuer(1)
    assert sperre.acquire(timeout=5), "Mapping-Thread nicht rechtzeitig fertig"
    sperre.release()

    assert aufrufe == [], "die Uebersicht darf beim Eintritt nicht automatisch starten"
    beschriftungen = [b for _, _, leiste in tg.knoepfe for b, _ in leiste]
    assert knoepfe_szenen.T.TEXT_SCHAERFUNG_SORTIEREN_KNOPF in beschriftungen


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
    assert "Im Treppenhaus" in seite and ">Mira <" in seite
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


def test_schaerfungsliste_html_erklaert_und_zeigt_verbindung_zuerst():
    """Birk 07.10.2026 14:30: Erklaerzeile oben, je Gruppe die Anzahl, und
    die Verbindung (→ Begruendung) steht VOR dem Zitat."""
    seite = web._schaerfungsliste_html(LISTE)
    assert 'class="schaerfung-erklaerung"' in seite
    assert "→ Mira kommt daher" in seite
    assert seite.index("→ Mira kommt daher") < seite.index(ZITAT_A)


def test_schaerfungsliste_begrenzt_je_ziel_und_zeigt_jede_stelle_nur_einmal(monkeypatch):
    """Birk 07.10.2026 14:30 ("266 viel zu viel"): hoechstens N offene je
    Ziel, eine Interviewstelle nur beim staerksten Ziel. Mutant: Grenze
    entfernt -> 8 offene statt 3."""
    import sqlite3
    from interview_theater import web_daten
    monkeypatch.setattr(web_daten, "SCHAERFUNGSLISTE_JE_ZIEL", 3)
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript("""
    create table schaerfung(id integer primary key, chat_id, verdichtung_thema_id, szene_id, figur_id,
      begruendung, runde, uebernommen_am, erstellt_am, entfernt_am, staerke, entscheidung);
    create table verdichtung_thema(id integer primary key, verdichtung_id, thema, beleg_zitat);
    create table verdichtung(id integer primary key, aufnahme_id, entfernt_am);
    create table szene(id integer primary key, chat_id, nummer, titel, entfernt_am);
    create table figur(id integer primary key, chat_id, name, entfernt_am);
    insert into verdichtung values(1, 1, null);
    insert into figur values(1, 1, 'A', null); insert into figur values(2, 1, 'B', null);
    """)
    for t in range(1, 7):
        c.execute("insert into verdichtung_thema values(?,1,?,?)", (t, f"T{t}", f"Z{t}"))
        c.execute("insert into schaerfung(chat_id,verdichtung_thema_id,figur_id,begruendung,runde,staerke)"
                  " values(1,?,1,'b',1,3)", (t,))
        c.execute("insert into schaerfung(chat_id,verdichtung_thema_id,figur_id,begruendung,runde,staerke)"
                  " values(1,?,2,'b',1,2)", (t,))
    monkeypatch.setattr(web_daten, "_interviewbezeichnungen", lambda conn, chat_id: {})
    daten = web_daten.schaerfungsliste(c, 1)
    je = {g["name"]: [e["titel"] for e in g["eintraege"]] for g in daten["gruppen"]}
    assert je["A"] == ["T1", "T2", "T3"]
    assert je["B"] == ["T4", "T5", "T6"]
    assert daten["zaehler"]["offen"] == 6


@pytest.fixture(autouse=True)
def _done_sperre_frei():
    knoepfe_szenen._letztes_done.clear()
    yield
    knoepfe_szenen._letztes_done.clear()


def _p5_done_lage(lage, einst, monkeypatch):
    from interview_theater import entwurf, szene as szene_modul
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    aufrufe = {"uebersicht": 0, "szene": []}
    monkeypatch.setattr(entwurf, "starte_uebersicht",
                        lambda *a, **k: aufrufe.__setitem__("uebersicht", aufrufe["uebersicht"] + 1))
    monkeypatch.setattr(szene_modul, "starte", lambda conn, tg, klm, e, chat_id, auftrag, *a, **k: aufrufe["szene"].append(auftrag))
    klm = KLMAttrappe({"Szene 1": _antwort(eintrag_nummern=[1], staerke=[3], begruendungen=["x"])})
    schaerfung.mappe(klm, lage, einst, 1)
    return aufrufe


def test_done_p5_ohne_uebersicht_startet_uebersicht_ohne_rundenfrage(lage, tg, einst, monkeypatch):
    """Birk 07.10.2026 ~16:35: Done fuehrt in Phase 5 gerade weiter, keine
    Frage 'noch eine Runde?'."""
    aufrufe = _p5_done_lage(lage, einst, monkeypatch)
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert aufrufe["uebersicht"] == 1 and aufrufe["szene"] == []
    texte = " ".join(str(n) for n in tg.gesendet)
    assert "another round" not in texte and "noch eine Runde" not in texte.lower()


def test_done_p5_szene_schon_geschrieben_wird_nicht_doppelt_geschrieben(lage, tg, einst, monkeypatch):
    """G1-Fall: Uebersicht (still) fixiert, Szene 1 hat schon Text -> Done
    bietet Szene 1 zur Abnahme an, schreibt sie nicht neu. Mutant: Prosa-
    Pruefung weg -> szene.starte wird gerufen -> rot."""
    aufrufe = _p5_done_lage(lage, einst, monkeypatch)
    repo.setze_arbeitsstand(lage, 1, "geschichte_uebersicht_fixiert_am", repo._jetzt())
    sid = repo.stelle_szene_sicher(lage, 1, 1)
    lage.execute("UPDATE szene SET prosa = 'Text' WHERE id = ?", (sid,)); lage.commit()
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert aufrufe["szene"] == [] and aufrufe["uebersicht"] == 0


def test_done_p5_szene_ohne_text_wird_geschrieben(lage, tg, einst, monkeypatch):
    aufrufe = _p5_done_lage(lage, einst, monkeypatch)
    repo.setze_arbeitsstand(lage, 1, "geschichte_uebersicht_fixiert_am", repo._jetzt())
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert len(aufrufe["szene"]) == 1 and "SZENE 1" in aufrufe["szene"][0]


def test_done_doppelklick_wirkt_einmal(lage, tg, einst, monkeypatch):
    """G1 tippte Done dreimal in 4 s. Mutant: Sperre weg -> 3 Uebersichten."""
    aufrufe = _p5_done_lage(lage, einst, monkeypatch)
    for _ in range(3):
        knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert aufrufe["uebersicht"] == 1


def test_done_p5_schliesst_liste_keine_nachruecker(lage, tg, einst, monkeypatch):
    """Birk 07.10.2026 ~18:00 (G2): nach Done kamen neue Interviewstellen in
    die Liste. Done: sichtbare offene = Keep, ausgeblendete fallen heraus,
    die Liste ist danach leer. Mutant: Block weg -> offene bleiben -> rot."""
    from interview_theater import web_daten
    _p5_done_lage(lage, einst, monkeypatch)
    monkeypatch.setattr(web_daten, "_interviewbezeichnungen", lambda conn, chat_id: {})
    monkeypatch.setattr(web_daten, "SCHAERFUNGSLISTE_JE_ZIEL", 0)
    assert schaerfung.offene_stellen(lage, 1)
    knoepfe_szenen.schliesse_schaerfungsliste(lage, tg, None, None, 1)
    assert schaerfung.offene_stellen(lage, 1) == []
    assert web_daten.schaerfungsliste(lage, 1) is None

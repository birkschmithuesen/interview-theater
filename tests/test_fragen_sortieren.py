"""Phase 2, Padua 05.10.2026: die Fragen auf einmal sortieren (CoThinker-
Liste) statt nur Karte fuer Karte -- ``repo.setze_fragen_entscheidung``,
"schaerfen" als offener Zustand, ``knoepfe.fragen.sortierung_abschliessen``
und der versteckte Befehl ``/sortiert``."""

import pytest

from interview_theater import repo, roadmap, workshop
from interview_theater.knoepfe import fragen
from interview_theater.knoepfe.texte import T

from test_knoepfe import TelegramAttrappe

CHAT = 1
FUENF = "A: eins?\nA: zwei?\nA: drei?\nA: vier?\nA: fuenf?"


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    from interview_theater import ablauf

    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def _feld(conn, feld):
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    return zeile[feld] if zeile is not None else None


def _auswahl(conn, wert=FUENF, begriffe="A"):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", begriffe)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", wert)


# --- repo.setze_fragen_entscheidung -----------------------------------------


def test_setze_fragen_entscheidung_fuellt_auf(conn):
    _auswahl(conn)
    assert repo.setze_fragen_entscheidung(conn, CHAT, 3, "nein") is True
    assert _feld(conn, "fragen_entschieden") == ",,nein"
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "schaerfen") is True
    assert _feld(conn, "fragen_entschieden") == "schaerfen,,nein"
    assert repo.setze_fragen_entscheidung(conn, CHAT, 3, "") is True
    assert _feld(conn, "fragen_entschieden") == "schaerfen,,"


@pytest.mark.parametrize("nummer,wert", [
    (0, "ja"), (6, "ja"), (-1, "ja"), (2, "vielleicht"), (2, "Ja"), (2, None),
])
def test_setze_fragen_entscheidung_lehnt_ab(conn, nummer, wert):
    _auswahl(conn)
    repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja")
    assert repo.setze_fragen_entscheidung(conn, CHAT, nummer, wert) is False
    assert _feld(conn, "fragen_entschieden") == "ja"


def test_setze_fragen_entscheidung_ohne_arbeitsstand(conn):
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja") is False
    assert repo.hole_arbeitsstand(conn, CHAT) is None


# --- "schaerfen" ist offen ---------------------------------------------------


def test_schaerfen_gilt_als_offen(conn):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,schaerfen,nein")
    assert fragen._naechste_offene(conn, CHAT, 5) == 2
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")
    assert fragen._aktuelle_offene_nummer(conn, CHAT) == 2
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "3")
    assert fragen._aktuelle_offene_nummer(conn, CHAT) is None


# --- sortierung_abschliessen -------------------------------------------------


def test_sortierung_mit_schaerfen_zeigt_die_karte(conn, tg, auftraege):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,,nein,schaerfen,")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen_entschieden") == "ja,ja,nein,schaerfen,ja"
    assert _feld(conn, "fragen_aktuell") == "4"
    texte = [g[1] for g in tg.gesendet]
    assert any("vier?" in t for t in texte)
    assert texte[-1] == T._TEXT_FRAGE_WAS_AENDERN
    assert _feld(conn, "fragen") is None

    fragen.entscheide(conn, tg, None, None, CHAT, 4, "ja")
    fertig = _feld(conn, "fragen")
    assert "eins?" in fertig and "zwei?" in fertig and "vier?" in fertig
    assert "fuenf?" in fertig and "drei?" not in fertig


def test_sortierung_ohne_schaerfen_schliesst_direkt_ab(conn, tg, auftraege):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    fertig = _feld(conn, "fragen")
    assert fertig and "eins?" in fertig and "zwei?" not in fertig and "fuenf?" in fertig


def test_sortierung_ohne_auswahl(conn, tg):
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert [g[1] for g in tg.gesendet] == [T._TEXT_FRAGEN_KEINE_AUSWAHL]


def test_befehl_sortiert(conn, tg, einst, auftraege):
    from interview_theater import befehle

    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "nein")
    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)
    fertig = _feld(conn, "fragen")
    assert fertig and "drei?" in fertig and "eins?" not in fertig


# --- roadmap.fragenuebersicht: Begriff mit Doppelpunkt ------------------------


def test_fragenuebersicht_begriff_mit_doppelpunkt():
    stand = {"begriffe": "EVENTO: dall’esterno all’interno",
             "fragen": None,
             "fragen_eigene_vorschlag":
                 "EVENTO: dall'esterno all'interno: Dov'eri l'11 settembre 2001?",
             "fragen_herkunft_final": None}
    erg = roadmap.fragenuebersicht(stand)
    assert erg == [{"begriff": "EVENTO: dall’esterno all’interno",
                    "fragen": ["Dov'eri l'11 settembre 2001?"]}]


def test_fragenuebersicht_trennt_zusammengeklebte_fragen():
    # Live G1, 05.10.2026: eine Zeile in ``fragen`` trug vier Fragen.
    stand = {"begriffe": "casa",
             "fragen": "casa: Cosa significa sentirsi a casa? Cosa rende casa "
                       "effettivamente casa? Ti piacerebbe cambiare casa? Perché?",
             "fragen_eigene_vorschlag": None,
             "fragen_herkunft_final": None}
    erg = roadmap.fragenuebersicht(stand)
    assert erg[0]["fragen"] == [
        "Cosa significa sentirsi a casa?",
        "Cosa rende casa effettivamente casa?",
        "Ti piacerebbe cambiare casa? Perché?",
    ]


def test_karte_begriff_mit_doppelpunkt(conn, tg):
    # Live G3: die Karte zeigte "EVENTO" als Kopf und den Rest des Begriffs
    # vor der Frage.
    _auswahl(conn, "EVENTO: dall'esterno all'interno: Dov'eri?",
             begriffe="EVENTO: dall’esterno all’interno")
    fragen._zeige_frage(conn, tg, CHAT, 1)
    text = tg.gesendet[-1][1]
    assert T._TEXT_FRAGE_KOPF.format(
        nummer=1, gesamt=1, begriff="EVENTO: dall’esterno all’interno") in text
    assert text.endswith("\n\nDov'eri?")


# --- Task 3: "show all", Frage bei offener Karte, Hinweis auf den CoThinker ---


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert workshop.diskussion_aktiv() is True
    yield
    workshop.vergiss()


@pytest.fixture
def dortmund(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    assert workshop.diskussion_aktiv() is False
    yield
    workshop.vergiss()


def _karte_offen(conn, entschieden="ja"):
    _auswahl(conn, "A: eins?\nA: zwei?\nB: drei?", begriffe="A, B")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki,ki")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", entschieden)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")


@pytest.mark.parametrize("wunsch", ["show all", "Mostra tutte!", "show all questions",
                                     "mostra tutte le domande", "Zeig alle Fragen."])
def test_show_all_zeigt_die_uebersicht(conn, tg, auftraege, padua, wunsch):
    _karte_offen(conn, "ja,,nein")
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, wunsch) is True
    assert auftraege == []
    text = tg.gesendet[-1][1]
    assert "— A —" in text and "— B —" in text
    assert f"1. ✓ eins?{T._TEXT_HERKUNFT_EIGEN}" in text
    assert f"2. · zwei?{T._TEXT_HERKUNFT_KI}" in text
    assert f"3. ✗ drei?{T._TEXT_HERKUNFT_KI}" in text
    assert T._TEXT_AUSWAHL_ZAEHLER.format(ja=1, nein=1, schaerfen=0, offen=1) in text
    assert text.endswith(T._TEXT_FRAGEN_COTHINKER_HINWEIS)


def test_uebersicht_markiert_schaerfen(conn, padua):
    _karte_offen(conn, "schaerfen")
    assert "1. ✎ eins?" in fragen.uebersicht_text(conn, CHAT)


def test_show_all_ohne_auswahl_bleibt_im_gespraech(conn, tg, auftraege, padua):
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "show all") is False


def test_frage_bei_offener_karte_geht_ins_gespraech(conn, tg, auftraege, padua):
    _karte_offen(conn)
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Can we see all questions?") is False
    assert auftraege == []


def test_nach_schaerfen_druck_ist_eine_frage_der_wunsch(conn, tg, auftraege, padua):
    _karte_offen(conn)
    fragen.frage_waehlt_schaerfen(conn, tg, CHAT, 2)
    assert _feld(conn, "fragen_warte_auf") == "schaerfen"
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Could you make it shorter?") is True
    assert len(auftraege) == 1 and "make it shorter" in auftraege[0]
    assert not _feld(conn, "fragen_warte_auf")


def test_aussage_bei_offener_karte_bleibt_schaerfungswunsch(conn, tg, auftraege, padua):
    _karte_offen(conn)
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "make it shorter") is True
    assert len(auftraege) == 1


def test_sortierung_mit_schaerfen_wartet_auf_den_wunsch(conn, tg, auftraege, padua):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,schaerfen")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen_warte_auf") == "schaerfen"
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Shorter, please?") is True
    assert len(auftraege) == 1


def test_annehmen_nach_schaerfen_druck_raeumt_das_warten_ab(conn, tg, auftraege, padua):
    _karte_offen(conn)
    fragen.frage_waehlt_schaerfen(conn, tg, CHAT, 2)
    fragen.entscheide(conn, tg, None, None, CHAT, 2, "ja")
    assert not _feld(conn, "fragen_warte_auf")
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Is this one good?") is False


def test_dortmund_unveraendert(conn, tg, auftraege, dortmund):
    _karte_offen(conn)
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "show all") is True
    assert len(auftraege) == 1  # wie bisher: Schaerfungswunsch
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Can we see all questions?") is True
    fragen.frage_waehlt_schaerfen(conn, tg, CHAT, 2)
    assert not _feld(conn, "fragen_warte_auf")
    vorher = len(tg.gesendet)
    fragen.starte_durchgehen(conn, tg, CHAT)
    assert all(T._TEXT_FRAGEN_COTHINKER_HINWEIS not in t for _, t in tg.gesendet[vorher:])


def test_padua_durchgehen_nennt_den_cothinker(conn, tg, padua):
    _karte_offen(conn)
    fragen.starte_durchgehen(conn, tg, CHAT)
    texte = [t for _, t in tg.gesendet]
    assert sum(T._TEXT_FRAGEN_COTHINKER_HINWEIS in t for t in texte) == 1


def test_padua_gegenueberstellung_nennt_den_cothinker_einmal(conn, tg, padua, monkeypatch):
    from interview_theater import fragen_ki

    monkeypatch.setattr(fragen_ki, "passt_zu_begriffen", lambda *a, **k: True)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "A")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", "A: eins?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_ki_vorschlag", "A: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", "2026-10-05")
    assert fragen.versuche_gegenueberstellung(conn, tg, CHAT) is not None
    texte = [t for _, t in tg.gesendet]
    assert sum(T._TEXT_FRAGEN_COTHINKER_HINWEIS in t for t in texte) == 1
    assert T._TEXT_GEGENUEBERSTELLUNG_BEREIT in texte[0]


def test_hinweis_deutsch_wortlaut():
    from interview_theater.knoepfe import texte

    assert texte._TEXT_FRAGEN_COTHINKER_HINWEIS == (
        "Ihr könnt alle Fragen auch im CoThinker auf einmal sortieren: "
        "✓ behalten · ✗ weg · ✎ umformulieren, dann „Fertig sortiert“.")


def test_fragenuebersicht_langer_begriff():
    lang = "impatto della tecnologia sulle relazioni interpersonali e sulla comunicazione"
    stand = {"begriffe": lang, "fragen": f"{lang}: I social ti avvicinano?",
             "fragen_eigene_vorschlag": None, "fragen_herkunft_final": None}
    assert roadmap.fragenuebersicht(stand)[0]["fragen"] == ["I social ti avvicinano?"]


# --- Review-Fix 05.10.2026: alte Karten, mehrere ✎, Wunsch nach Schaerfung ---


def test_fertig_sortiert_nimmt_die_offene_karte_ab(conn, tg, auftraege, padua):
    _auswahl(conn)
    fragen.starte_durchgehen(conn, tg, CHAT, hinweis=False)
    assert repo.offene_knoepfe(conn, CHAT, fragen.ART_FRAGE_ANNEHMEN)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert not repo.offene_knoepfe(conn, CHAT, fragen.ART_FRAGE_ANNEHMEN)


def test_alte_karte_nach_abschluss_startet_nichts_neu(conn, tg, auftraege, padua):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    fertig = _feld(conn, "fragen")
    vorher = len(tg.gesendet)
    for wert in ("ja", "nein"):
        assert fragen.entscheide(conn, tg, None, None, CHAT, 1, wert) \
            == T._TEXT_FRAGEN_KEINE_AUSWAHL
    assert fragen.frage_waehlt_schaerfen(conn, tg, CHAT, 1) == T._TEXT_FRAGEN_KEINE_AUSWAHL
    assert _feld(conn, "fragen") == fertig
    assert _feld(conn, "fragen_entschieden") is None
    assert _feld(conn, "fragen_aktuell") is None
    assert not _feld(conn, "fragen_warte_auf")
    assert len(tg.gesendet) == vorher


def test_druck_auf_nicht_aktuelle_karte_wird_ignoriert(conn, tg, auftraege, padua):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "3")
    assert fragen.entscheide(conn, tg, None, None, CHAT, 1, "nein") \
        == T._TEXT_FRAGEN_KEINE_AUSWAHL
    assert _feld(conn, "fragen_entschieden") == "ja,ja"
    assert _feld(conn, "fragen_aktuell") == "3"


def test_zwei_schaerfen_fragen_beide_mit_rueckfrage(conn, tg, auftraege, padua):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,schaerfen,nein,schaerfen,")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen_aktuell") == "2"
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "kuerzer") is True
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "A: zwei kurz?", None)

    fragen.entscheide(conn, tg, None, None, CHAT, 2, "ja")
    assert _feld(conn, "fragen_aktuell") == "4"
    texte = [t for _, t in tg.gesendet]
    assert "vier?" in texte[-2] and texte[-1] == T._TEXT_FRAGE_WAS_AENDERN
    assert _feld(conn, "fragen_warte_auf") == "schaerfen"
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Could it be shorter?") is True
    assert len(auftraege) == 2
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "A: vier kurz?", None)

    fragen.entscheide(conn, tg, None, None, CHAT, 4, "ja")
    assert _feld(conn, "fragen") == "A: eins?\nA: zwei kurz?\nA: vier kurz?\nA: fuenf?"


def test_nach_schaerfung_ist_eine_frage_wieder_der_wunsch(conn, tg, auftraege, padua):
    _karte_offen(conn)
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "make it shorter") is True
    assert not _feld(conn, "fragen_warte_auf")
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "A: zwei kurz?", None)
    assert _feld(conn, "fragen_warte_auf") == "schaerfen"
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "Could it be shorter?") is True
    assert len(auftraege) == 2


def test_dortmund_schaerfung_wartet_nicht(conn, tg, auftraege, dortmund):
    _karte_offen(conn)
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "A: zwei kurz?", None)
    assert not _feld(conn, "fragen_warte_auf")


# --- Fix 05.10.2026: "Sortierung offen" ist EINE Regel -----------------------


@pytest.mark.parametrize("stand, offen", [
    (None, True),
    ({"fragen": None, "fragen_entschieden": None}, True),
    ({"fragen": "", "fragen_entschieden": None}, True),
    ({"fragen": "A: eins?", "fragen_entschieden": None}, False),
    ({"fragen": "A: eins?", "fragen_entschieden": ""}, True),
    ({"fragen": "A: eins?", "fragen_entschieden": ",,"}, True),
])
def test_sortierung_offen(stand, offen):
    from interview_theater import auswahl

    assert auswahl.sortierung_offen(stand) is offen


def test_zweites_sortiert_nach_abschluss_aendert_nichts(conn, tg, auftraege):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein,nein")
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    fertig = _feld(conn, "fragen")
    assert fertig and "eins?" in fertig and "zwei?" not in fertig
    vorher = dict(repo.hole_arbeitsstand(conn, CHAT))
    gesendet = len(tg.gesendet)
    auftraege_vorher = len(auftraege)
    fragen.sortierung_abschliessen(conn, tg, None, None, CHAT)
    nachher = dict(repo.hole_arbeitsstand(conn, CHAT))
    vorher.pop("geaendert_am", None)
    nachher.pop("geaendert_am", None)
    assert nachher == vorher
    assert len(tg.gesendet) == gesendet
    assert len(auftraege) == auftraege_vorher


def test_setze_fragen_entscheidung_nach_abschluss_false(conn):
    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "A: eins?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", None)
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja") is False
    assert _feld(conn, "fragen_entschieden") is None


def test_setze_fragen_entscheidung_in_fremder_transaktion(conn):
    _auswahl(conn)
    conn.execute("UPDATE arbeitsstand SET begriffe = 'A' WHERE chat_id = ?", (CHAT,))
    assert conn.in_transaction
    assert repo.setze_fragen_entscheidung(conn, CHAT, 2, "ja") is True
    assert _feld(conn, "fragen_entschieden") == ",ja"



def test_setze_fragen_entscheidung_nimmt_den_schreib_lock_vor_dem_lesen(conn, monkeypatch):
    """Zwei Prozesse (Webserver, Bot) teilen sich ``_LOCK`` nicht -- das
    Lesen muss deshalb schon unter BEGIN IMMEDIATE laufen."""
    _auswahl(conn)
    gesehen = []
    ursprung = repo.hole_arbeitsstand

    def spion(c, chat_id):
        gesehen.append(c.in_transaction)
        return ursprung(c, chat_id)

    monkeypatch.setattr(repo, "hole_arbeitsstand", spion)
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja") is True
    assert gesehen and all(gesehen)
    assert not conn.in_transaction


def test_padua_neue_runde_nach_abschluss_ist_offen(conn, tg, padua):
    from interview_theater import auswahl

    _auswahl(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "A: eins?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", None)
    fragen.biete_fragenauswahl(conn, tg, CHAT, "A: neu?\nA: auch neu?")
    assert auswahl.sortierung_offen(repo.hole_arbeitsstand(conn, CHAT))
    assert repo.setze_fragen_entscheidung(conn, CHAT, 1, "ja") is True

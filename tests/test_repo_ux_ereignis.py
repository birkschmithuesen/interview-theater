"""UX-Ereignis-Logging (Karte t_10a31406): die repo-Schicht speichert eine
Charge Ereignisse und verwirft dabei, was kein deklariertes Nutzungssignal
ist -- insbesondere jeden Versuch, Freitext/Transkriptinhalt durch
``extra`` zu schmuggeln. Kein Modellaufruf, kein Knopf: reine Validierung
und ein INSERT je gueltigem Ereignis."""

import json

import pytest

from interview_theater import db, repo

CHAT = 7_000_000_000_051


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _zeilen(conn):
    return [dict(z) for z in conn.execute(
        "SELECT * FROM ux_ereignis WHERE chat_id = ? ORDER BY id", (CHAT,)
    )]


# -- Normalfall ---------------------------------------------------------------


def test_gueltiges_ereignis_wird_gespeichert(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "phase": 4, "t": 1000},
    ])
    assert n == 1
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["geraet"] == "g-abc123"
    assert zeilen[0]["typ"] == "tab_wechsel"
    assert zeilen[0]["ziel"] == "tab:buehne"
    assert zeilen[0]["phase"] == 4
    assert zeilen[0]["client_t"] == 1000
    assert zeilen[0]["server_t"]
    assert zeilen[0]["extra_json"] is None


def test_mehrere_gueltige_ereignisse_in_einer_charge(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1},
        {"typ": "klick", "ziel": "knopf:groesse", "t": 2},
        {"typ": "abbruch", "ziel": "aufnahme:slide", "t": 3},
    ])
    assert n == 3
    assert [z["typ"] for z in _zeilen(conn)] == ["klick", "klick", "abbruch"]


def test_optionale_dauer_wird_gespeichert(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "sichtbarkeit", "ziel": "hintergrund", "t": 5, "dauer_ms": 1500},
    ])
    assert _zeilen(conn)[0]["dauer_ms"] == 1500


# -- typ: nur die feste Liste -------------------------------------------------


def test_unbekannter_typ_wird_verworfen(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "irgendwas_neues", "ziel": "tab:buehne", "t": 1},
    ])
    assert n == 0
    assert _zeilen(conn) == []


def test_fehlender_typ_wird_verworfen(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"ziel": "tab:buehne", "t": 1},
    ])
    assert n == 0


# -- ziel: kurzes Schluesselwort, kein Freitext -------------------------------


@pytest.mark.parametrize("ziel", [
    "Das war eine ganze Transkriptzeile mit vielen Woertern drin",
    "tab buehne",            # Leerzeichen
    "tab:büh ne",            # Leerzeichen + Umlaut
    "a" * 41,                # zu lang
    "",                      # leer
    None,
    42,
])
def test_ziel_ausserhalb_des_schluesselwort_musters_wird_verworfen(conn, ziel):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": ziel, "t": 1},
    ])
    assert n == 0
    assert _zeilen(conn) == []


def test_ziel_am_laengenlimit_wird_noch_angenommen(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "a" * 40, "t": 1},
    ])
    assert n == 1


# -- extra: nur Zahlen unter festen Schluesseln, keine Freitextfelder --------


def test_extra_mit_erlaubten_zahlenfeldern_wird_gespeichert(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1,
         "extra": {"von": 1, "nach": 4}},
    ])
    extra = json.loads(_zeilen(conn)[0]["extra_json"])
    assert extra == {"von": 1, "nach": 4}


@pytest.mark.parametrize("schmuggel", [
    {"text": "Das Interview sagte, ihre Mutter heisst Carla"},
    {"transkript": "wörtlicher Chatinhalt"},
    {"nachricht": "freier Text"},
    {"zitat": "ein Belegzitat"},
])
def test_unbekannte_extra_schluessel_werden_gestrichen_nicht_gespeichert(conn, schmuggel):
    """Das ist der Kern der Abnahme: kein Freitext- oder Transkriptfeld darf
    durch ``extra`` ins Logging gelangen -- das Ereignis bleibt gueltig,
    aber ohne den Schmuggelversuch."""
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1, "extra": schmuggel},
    ])
    zeilen = _zeilen(conn)
    assert len(zeilen) == 1
    assert zeilen[0]["extra_json"] is None


def test_extra_mit_erlaubtem_und_unerlaubtem_schluessel_behaelt_nur_erlaubten(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1,
         "extra": {"von": 1, "transkript": "geheim"}},
    ])
    extra = json.loads(_zeilen(conn)[0]["extra_json"])
    assert extra == {"von": 1}


def test_extra_string_wert_unter_erlaubtem_zahlenfeld_wird_gestrichen(conn):
    """Ein String unter einem eigentlich numerischen Schluessel ist der
    naheliegendste Schmuggelweg -- 'von' ist fuer eine Zahl gedacht, nicht
    fuer einen Satz."""
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1,
         "extra": {"von": "ein ganzer Satz statt einer Zahl"}},
    ])
    assert _zeilen(conn)[0]["extra_json"] is None


def test_extra_msg_feld_ist_eine_kurze_diagnosezeile_fuer_js_fehler(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "js_fehler", "ziel": "fenster", "t": 1,
         "extra": {"msg": "TypeError: x is undefined", "zeile": 42}},
    ])
    extra = json.loads(_zeilen(conn)[0]["extra_json"])
    assert extra == {"msg": "TypeError: x is undefined", "zeile": 42}


def test_extra_msg_wird_auf_eine_laenge_begrenzt(conn):
    lang = "x" * 500
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "js_fehler", "ziel": "fenster", "t": 1, "extra": {"msg": lang}},
    ])
    extra = json.loads(_zeilen(conn)[0]["extra_json"])
    assert len(extra["msg"]) == repo.UX_MSG_ZEICHEN_MAX


def test_extra_bool_wert_unter_zahlenfeld_wird_gestrichen(conn):
    """bool ist in Python eine int-Unterklasse -- ohne expliziten Ausschluss
    wuerde True/False als 1/0 durchschluepfen."""
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1, "extra": {"von": True}},
    ])
    assert _zeilen(conn)[0]["extra_json"] is None


def test_extra_nicht_endliche_zahl_wird_gestrichen(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "tab_wechsel", "ziel": "tab:buehne", "t": 1,
         "extra": {"von": float("inf")}},
    ])
    assert _zeilen(conn)[0]["extra_json"] is None


def test_extra_das_kein_dict_ist_wird_ignoriert(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1, "extra": "kein dict"},
    ])
    assert n == 1
    assert _zeilen(conn)[0]["extra_json"] is None


# -- geraet: zufaellige ID, kein Fingerprint, aber ein Pflichtformat ---------


@pytest.mark.parametrize("geraet", ["", "mit leerzeichen", "a" * 65, None, 123])
def test_ungueltiges_geraet_verwirft_die_ganze_charge(conn, geraet):
    n = repo.speichere_ux_ereignisse(conn, CHAT, geraet, [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1},
    ])
    assert n == 0
    assert _zeilen(conn) == []


# -- t/phase/dauer_ms: Typpruefung --------------------------------------------


@pytest.mark.parametrize("t", [None, "1000", True, [1]])
def test_ungueltiger_client_zeitstempel_wird_verworfen(conn, t):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": t},
    ])
    assert n == 0


@pytest.mark.parametrize("phase", ["4", True, 4.5, [4]])
def test_ungueltige_phase_wird_verworfen(conn, phase):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1, "phase": phase},
    ])
    assert n == 0


def test_phase_none_ist_erlaubt(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1, "phase": None},
    ])
    assert n == 1
    assert _zeilen(conn)[0]["phase"] is None


@pytest.mark.parametrize("dauer", [-1, "500", True])
def test_ungueltige_dauer_wird_verworfen(conn, dauer):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1, "dauer_ms": dauer},
    ])
    assert n == 0


# -- eine kaputte Zeile reisst nicht die ganze Charge mit --------------------


def test_eine_ungueltige_zeile_in_der_charge_verwirft_nur_sich_selbst(conn):
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1},
        {"typ": "nicht_erlaubt", "ziel": "x", "t": 2},
        {"typ": "abbruch", "ziel": "aufnahme:slide", "t": 3},
    ])
    assert n == 2
    assert [z["typ"] for z in _zeilen(conn)] == ["klick", "abbruch"]


# -- Charge-Obergrenze als letzte Verteidigungslinie -------------------------


def test_charge_ueber_der_hoechstzahl_wird_auf_das_limit_gekappt(conn):
    viele = [{"typ": "klick", "ziel": "knopf:stift", "t": i} for i in range(80)]
    n = repo.speichere_ux_ereignisse(conn, CHAT, "g-abc123", viele)
    assert n == repo.MAX_UX_EVENTS_JE_BATCH == 50


# -- hole_ux_ereignisse --------------------------------------------------------


def test_hole_ux_ereignisse_liefert_chronologisch_mit_geparstem_extra(conn):
    repo.speichere_ux_ereignisse(conn, CHAT, "g-1", [
        {"typ": "tab_wechsel", "ziel": "tab:chat", "t": 1, "extra": {"von": 1, "nach": 2}},
    ])
    repo.speichere_ux_ereignisse(conn, CHAT, "g-1", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 2},
    ])
    ereignisse = repo.hole_ux_ereignisse(conn, CHAT)
    assert [e["typ"] for e in ereignisse] == ["tab_wechsel", "klick"]
    assert ereignisse[0]["extra"] == {"von": 1, "nach": 2}
    assert ereignisse[1]["extra"] == {}


def test_hole_ux_ereignisse_ist_je_gruppe_getrennt(conn):
    andere = CHAT + 1
    repo.sichere_gruppe(conn, andere, "gruppe2", "Andere Gruppe")
    repo.speichere_ux_ereignisse(conn, CHAT, "g-1", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1},
    ])
    repo.speichere_ux_ereignisse(conn, andere, "g-2", [
        {"typ": "klick", "ziel": "knopf:stift", "t": 1},
    ])
    assert len(repo.hole_ux_ereignisse(conn, CHAT)) == 1
    assert len(repo.hole_ux_ereignisse(conn, andere)) == 1


# -- web_post_fuer_auswertung -------------------------------------------------


def test_web_post_fuer_auswertung_liefert_richtung_typ_und_zeit_chronologisch(conn):
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, "text", text="Hallo")
    repo.lege_web_post_an(conn, CHAT, "aus", "text", text="Antwort vom Bot")
    zeilen = repo.web_post_fuer_auswertung(conn, CHAT)
    assert [(z["richtung"], z["typ"]) for z in zeilen] == [("ein", "text"), ("aus", "text")]
    assert all("text" not in z for z in zeilen)  # nie der Nachrichtentext


def test_web_post_fuer_auswertung_laesst_geloeschte_zeilen_weg(conn):
    message_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, "text", text="Hallo")
    conn.execute("UPDATE web_post SET geloescht_am = ? WHERE id = ?",
                 (repo._jetzt(), message_id))
    conn.commit()
    assert repo.web_post_fuer_auswertung(conn, CHAT) == []

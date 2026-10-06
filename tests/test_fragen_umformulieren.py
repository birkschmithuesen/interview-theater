"""Padua Phase 2, Testkarte t_266e7485 (06.10.2026): die Umformulier-Runde --
nach "Fertig sortiert" schickt die Gruppe EINE freie Anweisung, EIN
gebuendelter Modellaufruf schlaegt neue Formulierungen fuer ALLE behaltenen
Fragen vor, die Gruppe uebernimmt oder verwirft einzeln (Vorgabe: alte
behalten), wiederholbar in beliebig vielen Runden. Nur Padua; Dortmund bleibt
unberuehrt, weil der Hidden-Befehl und die neuen Wartezustaende dort nie
vorkommen."""

import pytest

from interview_theater import repo, workshop
from interview_theater.knoepfe import fragen
from interview_theater.knoepfe.texte import T

from test_knoepfe import TelegramAttrappe

CHAT = 1


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


def _feld(conn, feld):
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    return zeile[feld] if zeile is not None else None


def _setze_fragen(conn, fragen_wert, herkunft=None):
    repo.setze_arbeitsstand(conn, CHAT, "fragen", fragen_wert)
    if herkunft is not None:
        repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft_final", herkunft)


# --- Die reine Mischfunktion -------------------------------------------------


def test_wende_umformulierung_an_uebernimmt_nur_angenommene():
    alte = ["A: eins?", "A: zwei?", "A: drei?"]
    neue = ["A: EINS NEU?", "A: ZWEI NEU?", "A: DREI NEU?"]
    ergebnis = fragen._wende_umformulierung_an(alte, neue, {1, 3})
    assert ergebnis == ["A: EINS NEU?", "A: zwei?", "A: DREI NEU?"]


def test_wende_umformulierung_an_ohne_annahme_bleibt_unveraendert():
    alte = ["A: eins?", "A: zwei?"]
    neue = ["A: EINS NEU?", "A: ZWEI NEU?"]
    assert fragen._wende_umformulierung_an(alte, neue, set()) == alte


def test_wende_umformulierung_an_leere_neue_zeile_behaelt_alte():
    """Mutationsbefund (Review t_b371c0f1): ohne die Pruefung
    ``neue[n - 1].strip()`` ueberschriebe eine akzeptierte Position mit
    einer leeren/whitespace-only neuen Zeile die alte Formulierung mit
    einem Leerstring, statt sie zu behalten."""
    alte = ["A: eins?", "A: zwei?"]
    neue = ["A: EINS NEU?", "   "]
    ergebnis = fragen._wende_umformulierung_an(alte, neue, {1, 2})
    assert ergebnis == ["A: EINS NEU?", "A: zwei?"]


def test_parse_annahme_liest_zahlen():
    assert fragen._parse_annahme("1, 3", 3) == {1, 3}
    assert fragen._parse_annahme("take all", 3) == {1, 2, 3}
    assert fragen._parse_annahme("ALLE", 3) == {1, 2, 3}
    assert fragen._parse_annahme("nothing here", 3) == set()
    assert fragen._parse_annahme("7", 3) == set()


# --- starte_umformulierung: die Anweisung ------------------------------------


def test_starte_umformulierung_baut_eine_gebuendelte_anweisung(conn, tg, auftraege, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    assert fragen.starte_umformulierung(
        conn, tg, None, None, CHAT, "macht sie konkreter") is True
    assert len(auftraege) == 1
    anweisung = auftraege[0]
    assert "macht sie konkreter" in anweisung
    assert "A: eins?" in anweisung and "A: zwei?" in anweisung
    assert "VORSCHLAG FRAGEN UMFORMULIERUNG" not in "".join(tg.gesendet)


def test_starte_umformulierung_ohne_fragen_tut_nichts(conn, tg, auftraege, padua):
    assert fragen.starte_umformulierung(conn, tg, None, None, CHAT, "egal") is False
    assert auftraege == []


def test_sprache_wird_in_die_anweisung_uebernommen(conn, tg, auftraege, padua, monkeypatch):
    from interview_theater import sprache

    monkeypatch.setattr(sprache, "code", lambda: "it")
    _setze_fragen(conn, "A: eins?")
    fragen.starte_umformulierung(conn, tg, None, None, CHAT, "piu concrete")
    assert len(auftraege) == 1
    assert "Italiano" in auftraege[0]


def test_englische_sprache_wird_in_die_anweisung_uebernommen(conn, tg, auftraege, padua, monkeypatch):
    from interview_theater import sprache

    monkeypatch.setattr(sprache, "code", lambda: "en")
    _setze_fragen(conn, "A: eins?")
    fragen.starte_umformulierung(conn, tg, None, None, CHAT, "make them shorter")
    assert "English" in auftraege[0]


# --- biete_umformulierung: die Vorschau alt->neu -----------------------------


def test_biete_umformulierung_zeigt_nur_geaenderte_fragen(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?\nA: drei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: eins?\nA: ZWEI NEU?\nA: drei?")
    text = tg.gesendet[-1][1]
    assert "zwei?" in text and "ZWEI NEU?" in text
    assert "eins?" not in text
    assert _feld(conn, "fragen_warte_auf") == "umformulieren_auswahl"


def test_biete_umformulierung_ohne_aenderung(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: eins?\nA: zwei?")
    assert tg.gesendet[-1][1] == T._TEXT_UMFORMULIEREN_UNVERAENDERT
    assert _feld(conn, "fragen_warte_auf") is None


# --- Annahme: nur angenommene Zeilen aendern sich, Rest bleibt stehen -------


def test_umformulierung_uebernimmt_nur_angenommene_rest_bleibt_stehen(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?\nA: drei?", herkunft="eigen,ki,ki")
    fragen.biete_umformulierung(
        conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?\nA: DREI NEU?")
    fragen._wende_umformulierung_durch(conn, tg, None, None, CHAT, {1, 3})
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: zwei?\nA: DREI NEU?"


def test_umformulierung_markiert_ki_frage_bearbeitet_wenn_uebernommen(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?", herkunft="eigen,ki")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: eins?\nA: ZWEI NEU?")
    fragen._wende_umformulierung_durch(conn, tg, None, None, CHAT, {1, 2})
    assert _feld(conn, "fragen_bearbeitet_final") == ",1"


def test_umformulierung_markiert_eigene_frage_nicht(conn, tg, padua):
    _setze_fragen(conn, "A: eins?", herkunft="eigen")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?")
    fragen._wende_umformulierung_durch(conn, tg, None, None, CHAT, {1})
    assert _feld(conn, "fragen") == "A: EINS NEU?"
    assert not _feld(conn, "fragen_bearbeitet_final")


def test_umformulierung_alle_annehmen_knopf(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    fragen.fragen_umformulierung_alle_annehmen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: ZWEI NEU?"
    assert _feld(conn, "fragen_warte_auf") is None
    assert _feld(conn, "fragen_umformuliert_vorschlag") is None


def test_umformulierung_alte_behalten_knopf(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    fragen.fragen_umformulierung_alle_verwerfen(conn, tg, None, None, CHAT)
    assert _feld(conn, "fragen") == "A: eins?\nA: zwei?"


# --- Zweite Runde arbeitet auf dem Ergebnis der ersten -----------------------


def test_zweite_runde_arbeitet_auf_ergebnis_der_ersten(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    fragen._wende_umformulierung_durch(conn, tg, None, None, CHAT, {1})
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: zwei?"

    assert fragen._aktuelle_fragen(conn, CHAT) == ["A: EINS NEU?", "A: zwei?"]
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NOCHMAL?\nA: ZWEI NEU2?")
    fragen._wende_umformulierung_durch(conn, tg, None, None, CHAT, {2})
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: ZWEI NEU2?"


# --- Verdrahtung: Hidden-Befehl, Wartezustaende, Marker-Dispatch -------------


def test_befehl_umformulieren_fragt_nach_der_anweisung(conn, tg, einst, padua):
    from interview_theater import befehle

    _setze_fragen(conn, "A: eins?")
    befehle.behandle(conn, tg, einst, CHAT, "/umformulieren", None)
    assert _feld(conn, "fragen_warte_auf") == "umformulieren"
    assert tg.gesendet[-1][1] == T._TEXT_UMFORMULIEREN_WUNSCH_FRAGE


def test_befehl_umformulieren_ohne_fragen(conn, tg, einst, padua):
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, CHAT, "/umformulieren", None)
    assert _feld(conn, "fragen_warte_auf") != "umformulieren"


def test_befehl_umformulieren_in_dortmund_tut_nichts(conn, tg, einst, dortmund):
    from interview_theater import befehle

    _setze_fragen(conn, "A: eins?")
    befehle.behandle(conn, tg, einst, CHAT, "/umformulieren", None)
    assert _feld(conn, "fragen_warte_auf") != "umformulieren"


def test_wunsch_nach_umformulieren_startet_auftrag(conn, tg, auftraege, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", "umformulieren")
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "macht sie kuerzer") is True
    assert len(auftraege) == 1 and "kuerzer" in auftraege[0]
    assert _feld(conn, "fragen_warte_auf") is None


def test_auswahl_text_wendet_zahlen_an(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "1") is True
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: zwei?"


def test_auswahl_text_alle_uebernimmt_alles(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    assert fragen.nimm_offene_frage_text(conn, tg, None, None, CHAT, "all") is True
    assert _feld(conn, "fragen") == "A: EINS NEU?\nA: ZWEI NEU?"


def test_auswahl_text_ohne_zahlen_behaelt_alte(conn, tg, padua):
    _setze_fragen(conn, "A: eins?\nA: zwei?")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "lieber nicht") is True
    assert _feld(conn, "fragen") == "A: eins?\nA: zwei?"


def test_marker_wird_an_biete_umformulierung_weitergeleitet(conn, tg, padua, einst):
    from interview_theater import knoepfe

    _setze_fragen(conn, "A: eins?\nA: zwei?")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, CHAT,
        "VORSCHLAG FRAGEN UMFORMULIERUNG:\nA: EINS NEU?\nA: ZWEI NEU?",
        e=einst,
    )
    assert _feld(conn, "fragen_umformuliert_vorschlag") == "A: EINS NEU?\nA: ZWEI NEU?"
    assert _feld(conn, "fragen_warte_auf") == "umformulieren_auswahl"


# --- Verdrahtung: ein ECHTER Ausloeser nach "Fertig sortiert" --------------


def test_sortiert_bietet_umformulierung_an_und_knopf_loest_sie_aus(
    conn, tg, einst, auftraege, padua,
):
    """Befund 1 (Review t_b371c0f1): der versteckte Befehl
    ``/umformulieren`` hatte keinen Ausloeser -- dieser Test faehrt den
    ECHTEN Pfad nach: ``/sortiert`` (wie ``web_vereint.auswahl_fertig_post``
    ihn fuer die Gruppe ausloest) schliesst die Fragen ab und bietet jetzt
    einen Knopf an; ERST der Druck auf diesen Knopf (ueber
    ``knoepfe.wirkung.behandle``, nicht der direkte Funktionsaufruf) setzt
    ``fragen_warte_auf`` auf "umformulieren"."""
    from interview_theater import befehle
    from interview_theater.knoepfe import wirkung

    from test_knoepfe import _druck

    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")

    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)

    assert _feld(conn, "fragen") == "A: eins?\nA: zwei?"
    assert _feld(conn, "fragen_warte_auf") != "umformulieren"
    assert tg.knoepfe, "kein Knopf angeboten -- Umformulier-Runde unerreichbar"
    chat_id, text, leiste = tg.knoepfe[-1]
    assert text == T._TEXT_UMFORMULIEREN_ANBIETEN
    assert leiste[0][0] == T._TEXT_UMFORMULIEREN_ANBIETEN_KNOPF
    daten = leiste[0][1]

    behandelt = wirkung.behandle(conn, tg, None, einst, _druck(daten, chat_id=CHAT))

    assert behandelt is True
    assert _feld(conn, "fragen_warte_auf") == "umformulieren"
    assert tg.gesendet[-1][1] == T._TEXT_UMFORMULIEREN_WUNSCH_FRAGE


def test_dortmund_wartezustand_kommt_nie_vor(conn, tg, auftraege, dortmund):
    """Die neuen Wartezustaende existieren nur, wenn der Hidden-Befehl sie
    setzt -- Dortmund hat weder den Befehl noch einen Weg dorthin, also
    bleibt ``nimm_offene_frage_text`` fuer sie taub."""
    _setze_fragen(conn, "A: eins?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", "umformulieren")
    # Ohne Padua greift die Weiche fuer "umformulieren" nicht -- der Text
    # faellt durch (hier: kein offenes Einzelkarten-Fenster, also False).
    assert fragen.nimm_offene_frage_text(
        conn, tg, None, None, CHAT, "macht sie kuerzer") is False
    assert auftraege == []


# --- Karte t_1f13a707: eine ECHTE Weiche statt einer sofortigen Eroeffnung --


def test_sortiert_startet_eroeffnung_nicht_mehr_sofort(
    conn, tg, einst, auftraege, padua,
):
    """Bisher lief die Eroeffnung im selben Schritt wie das Angebot -- der
    Knopf war erreichbar, aber wirkungslos begraben. Jetzt wartet die Kette
    auf die Entscheidung der Gruppe."""
    from interview_theater import befehle

    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")

    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)

    assert auftraege == []
    assert _feld(conn, "fragen_fortsetzung_offen") == "1"


def test_biete_umformulierung_an_zeigt_beide_knoepfe(conn, tg, padua):
    fragen._biete_umformulierung_an(conn, tg, CHAT)
    chat_id, text, leiste = tg.knoepfe[-1]
    beschriftungen = [b for b, _ in leiste]
    assert beschriftungen == [
        T._TEXT_UMFORMULIEREN_ANBIETEN_KNOPF, T._TEXT_UMFORMULIEREN_WEITER_KNOPF,
    ]


def test_weiter_knopf_setzt_die_kette_sofort_fort(conn, tg, einst, auftraege, padua):
    from interview_theater import befehle
    from interview_theater.knoepfe import wirkung

    from test_knoepfe import _druck

    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")
    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)
    assert auftraege == []

    chat_id, text, leiste = tg.knoepfe[-1]
    assert leiste[1][0] == T._TEXT_UMFORMULIEREN_WEITER_KNOPF
    daten = leiste[1][1]

    behandelt = wirkung.behandle(conn, tg, None, einst, _druck(daten, chat_id=CHAT))

    assert behandelt is True
    assert len(auftraege) == 1
    assert _feld(conn, "fragen_fortsetzung_offen") is None


def test_rephrase_runde_fertig_setzt_die_kette_auch_fort(
    conn, tg, einst, auftraege, padua,
):
    """'Alle uebernehmen' direkt aus der Weiche heraus setzt die Kette
    genauso fort wie "Weiter zur Eroeffnung" -- die Eroeffnung startet jetzt
    erst hier, nicht schon beim Abschluss der Sortierung."""
    from interview_theater import befehle

    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")
    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)
    assert auftraege == []

    fragen.frage_nach_umformulierung(conn, tg, CHAT)
    fragen.starte_umformulierung(conn, tg, None, None, CHAT, "macht sie kuerzer")
    # Der Auftrag oben ist die Umformulier-Runde, nicht die Eroeffnung.
    assert len(auftraege) == 1
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NEU?\nA: ZWEI NEU?")

    fragen.fragen_umformulierung_alle_annehmen(conn, tg, None, None, CHAT)

    assert len(auftraege) == 2  # Umformulier-Auftrag + Eroeffnung
    assert _feld(conn, "fragen_fortsetzung_offen") is None


def test_spaetere_rephrase_runde_stoesst_eroeffnung_nicht_erneut_an(
    conn, tg, einst, auftraege, padua,
):
    """Der Dauerknopf im CoThinker/der Werkbank bleibt bis zum ersten
    Interview erreichbar -- eine Runde NACH der schon gelaufenen Eroeffnung
    darf diese nicht ein zweites Mal anstossen."""
    from interview_theater import befehle
    from interview_theater.knoepfe import wirkung

    from test_knoepfe import _druck

    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "A: eins?\nA: zwei?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,ja")
    befehle.behandle(conn, tg, einst, CHAT, "/sortiert", None)

    chat_id, text, leiste = tg.knoepfe[-1]
    behandelt = wirkung.behandle(
        conn, tg, None, einst, _druck(leiste[1][1], chat_id=CHAT),
    )
    assert behandelt is True
    assert len(auftraege) == 1  # die Eroeffnung ist schon gestartet

    fragen.frage_nach_umformulierung(conn, tg, CHAT)
    fragen.starte_umformulierung(conn, tg, None, None, CHAT, "noch kuerzer")
    fragen.biete_umformulierung(conn, tg, CHAT, "A: EINS NOCHMAL?\nA: ZWEI NEU2?")
    fragen.fragen_umformulierung_alle_annehmen(conn, tg, None, None, CHAT)

    # Der Umformulier-Auftrag kommt dazu, aber KEIN zweiter Eroeffnungslauf.
    assert len(auftraege) == 2

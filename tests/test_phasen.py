"""Die Arbeitsphasen als gespeicherter Zustand (theatersoap/phasen.py).

Zwei Dinge werden hier geprueft, und beide sind Entscheidungen, keine
Implementierungsdetails: dass ``nummer_fuer`` tolerant genug ist, um zu
verstehen, was eine Gruppe im Chat sagt, und dass ``naechste_moegliche``
ausschliesslich aus der Materiallage folgt -- ohne Modell, ohne
Zustandsmaschine, und niemals rueckwaerts.
"""

import pytest

from theatersoap import db, phasen, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def _szene(conn, nummer, volltext):
    repo.lege_szene_an(conn, 1, nummer, f"Szene {nummer}", "eine Zeile", volltext)


# --- die Liste selbst -----------------------------------------------------


def test_acht_phasen_mit_nummer_kurzname_und_satz():
    assert [nummer for nummer, _, _ in phasen.PHASEN] == [1, 2, 3, 4, 5, 6, 7, 8]
    for nummer, name, satz in phasen.PHASEN:
        assert name.strip() and satz.strip(), nummer


def test_bezeichnung_ist_ueberall_dieselbe_schreibweise():
    assert phasen.bezeichnung(5) == "5 · Figuren entwickeln"


# --- nummer_fuer: was die Gruppe sagt -------------------------------------


@pytest.mark.parametrize(
    "gesagt, erwartet",
    [
        ("5", 5),
        (5, 5),
        ("Figuren entwickeln", 5),   # voller Kurzname
        ("figuren", 5),              # Teilstring, kleingeschrieben
        ("Kernthema", 3),
        ("interview", 2),            # Singular trifft 'Interviews'
        ("Durchlauf.", 8),           # Satzzeichen stoert nicht
        ("wir sind noch beim Kernthema", 3),  # Kurzname im Satz
    ],
)
def test_nummer_fuer_versteht_nummer_name_und_teilstring(gesagt, erwartet):
    assert phasen.nummer_fuer(gesagt) == erwartet


@pytest.mark.parametrize("gesagt", ["", "   ", "0", "9", "42", "Kaffeepause", None])
def test_nummer_fuer_raet_nicht(gesagt):
    """Was sich keiner Phase zuordnen laesst, ist None -- der Aufrufer
    aendert dann nichts. Eine falsch gesetzte Phase kostet mehr als eine
    nicht gesetzte."""
    assert phasen.nummer_fuer(gesagt) is None


# --- aktuelle -------------------------------------------------------------


def test_ohne_gespeicherte_phase_gilt_die_erste(conn):
    assert repo.hole_phase(conn, 1) is None
    assert phasen.aktuelle(conn, 1) == 1


def test_setze_schreibt_phase_und_journalzeile(conn):
    assert phasen.setze(conn, 1, 5, "erkenner") is True

    assert repo.hole_phase(conn, 1) == 5
    eintrag = repo.journal(conn, 1)[-1]
    assert eintrag["art"] == "entschieden"
    assert eintrag["text"] == "Phase 5 · Figuren entwickeln"
    assert eintrag["quelle"] == "erkenner"


def test_setze_auf_denselben_wert_ist_keine_aenderung(conn):
    phasen.setze(conn, 1, 5, "erkenner")

    assert phasen.setze(conn, 1, 5, "befehl") is False
    assert len(repo.journal(conn, 1)) == 1


def test_ruecksprung_ist_erlaubt(conn):
    phasen.setze(conn, 1, 8, "erkenner")

    assert phasen.setze(conn, 1, 5, "erkenner") is True
    assert repo.hole_phase(conn, 1) == 5


# --- naechste_moegliche: jede Stufe ---------------------------------------


def test_ohne_material_gibt_es_keine_naechste_phase(conn):
    assert phasen.naechste_moegliche(conn, 1) is None


def test_begriffe_erlauben_zwei(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    assert phasen.naechste_moegliche(conn, 1) == 2


def test_eine_verdichtung_erlaubt_drei(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "hallo", repo._jetzt())
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 60)
    repo.speichere_verdichtung(conn, 1, aufnahme_id, "Maria erzaehlt", [])
    assert phasen.naechste_moegliche(conn, 1) == 3


def test_kernthema_erlaubt_vier(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    assert phasen.naechste_moegliche(conn, 1) == 4


def test_hauptkonflikt_erlaubt_fuenf(conn):
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    assert phasen.naechste_moegliche(conn, 1) == 5


def test_zwei_figuren_erlauben_sechs_eine_nicht(conn):
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    assert phasen.naechste_moegliche(conn, 1) is None

    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    assert phasen.naechste_moegliche(conn, 1) == 6


def test_eine_szene_erlaubt_sieben_und_volltext_ueberall_acht(conn):
    _szene(conn, 1, None)
    assert phasen.naechste_moegliche(conn, 1) == 7

    repo.aktualisiere_szene(
        conn, repo.hole_szenen(conn, 1)[0]["id"], "Szene 1", "eine Zeile", "MARIA: Hier."
    )
    assert phasen.naechste_moegliche(conn, 1) == 8


def test_eine_szene_ohne_volltext_haelt_acht_zurueck(conn):
    _szene(conn, 1, "MARIA: Hier.")
    _szene(conn, 2, None)
    assert phasen.naechste_moegliche(conn, 1) == 7


def test_die_hoechste_erfuellte_stufe_gewinnt(conn):
    """Die Bedingungen sind nicht kumulativ: eine Gruppe, die ohne Interviews
    Kernthema und Konflikt gesetzt hat, darf nach 5."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    assert phasen.naechste_moegliche(conn, 1) == 5


def test_nie_rueckwaerts_und_nie_die_aktuelle(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 8, "erkenner")

    assert phasen.naechste_moegliche(conn, 1) is None


def test_erfuellte_stufe_gleich_der_aktuellen_ist_kein_vorschlag(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 4, "erkenner")

    assert phasen.naechste_moegliche(conn, 1) is None


# --- sprung_nach: der automatische Sprung ---------------------------------


def test_sprung_nur_wenn_die_aenderung_genau_die_naechste_phase_traegt(conn):
    phasen.setze(conn, 1, 3, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    ) == 4


def test_kein_sprung_ueber_eine_phase_hinweg(conn):
    """Phase 1, ein Kernthema gesetzt: Phase 4 waere moeglich, aber drei
    Stufen auf einmal ist ein Angebot, kein Sprung."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    ) is None


def test_kein_sprung_ohne_belegende_aenderung(conn):
    phasen.setze(conn, 1, 3, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "entschieden", "wert": "wir treffen uns um zehn"}]
    ) is None


def test_kein_sprung_wenn_die_gruppe_selbst_eine_phase_genannt_hat(conn):
    phasen.setze(conn, 1, 3, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    aenderungen = [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "phase_setzen", "wert": "3"},
    ]
    assert phasen.sprung_nach(conn, 1, aenderungen) is None


def test_kein_sprung_ueber_die_letzte_phase_hinaus(conn):
    phasen.setze(conn, 1, 8, "befehl")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_figur(conn, 1, "Elif", "Nachbarin")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "figur_setzen", "wert": "Elif"}]
    ) is None


def test_entfernte_figuren_zaehlen_fuer_die_materiallage_nicht(conn):
    """Weiches Loeschen wirkt auch hier: zwei Figuren erlauben Phase 6, eine
    entfernte Figur nimmt die Voraussetzung wieder weg (N3)."""
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    assert phasen.naechste_moegliche(conn, 1) == 6

    repo.entferne_figur(conn, 1, "Elif")
    assert phasen.naechste_moegliche(conn, 1) is None

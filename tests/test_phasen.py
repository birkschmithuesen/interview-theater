"""Die Arbeitsphasen als gespeicherter Zustand (interview_theater/phasen.py).

Drei Dinge werden hier geprueft, und alle drei sind Entscheidungen, keine
Implementierungsdetails: dass ``nummer_fuer`` tolerant genug ist, um zu
verstehen, was eine Gruppe im Chat sagt; dass die Voraussetzungen
ausschliesslich aus der Materiallage folgen -- ohne Modell, ohne
Zustandsmaschine, und niemals rueckwaerts; und dass der Code die freie Stelle
zwischen Figuren (5) und Hauptkonflikt (6) in Ruhe laesst.
"""

import pytest

from interview_theater import db, phasen, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def _szene(conn, nummer, volltext):
    repo.lege_szene_an(conn, 1, nummer, f"Szene {nummer}", "eine Zeile", volltext)


def _zwei_figuren(conn):
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_figur(conn, 1, "Elif", "Nachbarin")


# --- die Liste selbst -----------------------------------------------------


def test_acht_phasen_mit_nummer_kurzname_und_satz():
    assert [nummer for nummer, _, _ in phasen.PHASEN] == [1, 2, 3, 4, 5, 6, 7, 8]
    for nummer, name, satz in phasen.PHASEN:
        assert name.strip() and satz.strip(), nummer


def test_die_korrigierte_reihenfolge_der_kurznamen():
    """Das Modell vom 04.09.2026 abends: Begriffe kommen aus dem Plenum,
    Fragen sind eine eigene Phase, Figuren stehen vor dem Hauptkonflikt (aber
    nicht ueber ihm), Szenenfolge und Szenentexte sind eine Phase."""
    assert [name for _, name, _ in phasen.PHASEN] == [
        "Begriffe", "Fragen", "Interviews", "Kernthema",
        "Figuren", "Hauptkonflikt", "Szenen", "Durchlauf",
    ]


def test_bezeichnung_ist_ueberall_dieselbe_schreibweise():
    assert phasen.bezeichnung(5) == "5 · Figuren"


# --- nummer_fuer: was die Gruppe sagt -------------------------------------


@pytest.mark.parametrize(
    "gesagt, erwartet",
    [
        ("5", 5),
        (5, 5),
        ("Begriffe", 1),
        ("Fragen", 2),
        ("fragen", 2),
        ("Interviews", 3),
        ("interview", 3),            # Singular trifft 'Interviews'
        ("Kernthema", 4),
        ("figuren", 5),              # Teilstring, kleingeschrieben
        ("Hauptkonflikt", 6),
        ("konflikt", 6),             # Teilstring in die andere Richtung
        ("Szenen", 7),
        ("szenentexte", 7),          # Szenenfolge und Texte sind eine Phase
        ("Durchlauf.", 8),           # Satzzeichen stoert nicht
        ("wir sind noch beim Kernthema", 4),  # Kurzname im Satz
    ],
)
def test_nummer_fuer_versteht_nummer_name_und_teilstring(gesagt, erwartet):
    assert phasen.nummer_fuer(gesagt) == erwartet


def test_kurzname_schlaegt_einen_treffer_im_erklaerenden_satz():
    """'interview' steht auch im Satz von Phase 2 ('Interviewfragen
    entwickeln'). Erst wenn kein Kurzname passt, wird in den Saetzen gesucht
    -- sonst landete die Gruppe beim Formulieren statt beim Aufnehmen."""
    assert phasen.nummer_fuer("interview") == 3
    assert phasen.nummer_fuer("verdichten") == 3  # nur im Satz, nirgends im Namen


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
    assert eintrag["text"] == "Phase 5 · Figuren"
    assert eintrag["quelle"] == "erkenner"


def test_setze_auf_denselben_wert_ist_keine_aenderung(conn):
    phasen.setze(conn, 1, 5, "erkenner")

    assert phasen.setze(conn, 1, 5, "befehl") is False
    assert len(repo.journal(conn, 1)) == 1


def test_ruecksprung_ist_erlaubt(conn):
    phasen.setze(conn, 1, 8, "erkenner")

    assert phasen.setze(conn, 1, 5, "erkenner") is True
    assert repo.hole_phase(conn, 1) == 5


# --- voraussetzungen: jede Stufe einzeln ----------------------------------


def test_ohne_material_gibt_es_keine_naechste_phase(conn):
    assert phasen.moegliche_naechste(conn, 1) == []
    assert phasen.naechste_moegliche(conn, 1) is None


def test_begriffe_erlauben_zwei(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    assert phasen.moegliche_naechste(conn, 1) == [2]


def test_fragen_erlauben_drei(conn):
    """Die neue Stufe: erst die Frageliste macht die Interviews moeglich."""
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    assert phasen.moegliche_naechste(conn, 1) == [3]


def test_eine_verdichtung_erlaubt_vier(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "hallo", repo._jetzt())
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 60)
    repo.speichere_verdichtung(conn, 1, aufnahme_id, "Maria erzaehlt", [])
    assert phasen.moegliche_naechste(conn, 1) == [4]


def test_kernthema_erlaubt_fuenf_und_sechs_zugleich(conn):
    """Die freie Stelle in den Voraussetzungen: Figuren und Hauptkonflikt
    haben dieselbe Bedingung, also sind beide gleichzeitig moeglich."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    assert phasen.moegliche_naechste(conn, 1) == [5, 6]


def test_sieben_braucht_konflikt_und_zwei_figuren(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    assert 7 not in phasen.moegliche_naechste(conn, 1)

    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    assert 7 not in phasen.moegliche_naechste(conn, 1)

    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    assert 7 in phasen.moegliche_naechste(conn, 1)


def test_sieben_zaehlt_die_reihenfolge_nicht(conn):
    """Egal, ob erst die Figuren oder erst der Konflikt entstanden sind --
    beides zusammen macht die Szenen moeglich."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    _zwei_figuren(conn)
    assert 7 not in phasen.moegliche_naechste(conn, 1)

    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    assert 7 in phasen.moegliche_naechste(conn, 1)


def test_erst_ein_szenentext_erlaubt_acht(conn):
    _szene(conn, 1, None)
    assert 8 not in phasen.moegliche_naechste(conn, 1)

    repo.aktualisiere_szene(
        conn, repo.hole_szenen(conn, 1)[0]["id"], "Szene 1", "eine Zeile", "MARIA: Hier."
    )
    assert 8 in phasen.moegliche_naechste(conn, 1)


def test_eine_zweite_szene_ohne_text_haelt_acht_nicht_zurueck(conn):
    """Der Durchlauf beginnt, sobald der erste Text steht -- nicht erst, wenn
    jede Szene ausgeschrieben ist. Eine Gruppe, die eine Szene bewusst
    improvisiert laesst, kaeme sonst nie in Phase 8."""
    _szene(conn, 1, "MARIA: Hier.")
    _szene(conn, 2, None)
    assert 8 in phasen.moegliche_naechste(conn, 1)


def test_die_bedingungen_sind_nicht_kumulativ(conn):
    """Eine Gruppe, die ohne Interviews direkt ein Kernthema setzt, darf
    trotzdem nach 5 -- die Reihenfolge ist eine Landkarte, kein Zwang."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    assert phasen.voraussetzungen(conn, 1)[4] is False
    assert 5 in phasen.moegliche_naechste(conn, 1)


def test_nie_rueckwaerts_und_nie_die_aktuelle(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 8, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_erfuellte_stufe_gleich_der_aktuellen_ist_kein_vorschlag(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 6, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_naechste_moegliche_ist_die_hoechste(conn):
    """Der Merkposten fuer ``phase_angeboten`` braucht eine Zahl, keine
    Liste -- das ist der einzige Grund, warum es beide Funktionen gibt."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    assert phasen.naechste_moegliche(conn, 1) == 6


def test_entfernte_figuren_zaehlen_fuer_die_materiallage_nicht(conn):
    """Weiches Loeschen wirkt auch hier: zwei Figuren und ein Konflikt
    erlauben Phase 7, eine entfernte Figur nimmt die Voraussetzung wieder
    weg (N3)."""
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    _zwei_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[7] is True

    repo.entferne_figur(conn, 1, "Elif")
    assert phasen.voraussetzungen(conn, 1)[7] is False


# --- ermoeglichte_phase: wohin eine Aenderung zeigt -----------------------


@pytest.mark.parametrize(
    "art, erwartet",
    [("begriffe_setzen", 2), ("fragen_setzen", 3), ("kernthema_setzen", 5)],
)
def test_die_drei_festen_arten(conn, art, erwartet):
    assert phasen.ermoeglichte_phase(conn, 1, art) == erwartet


@pytest.mark.parametrize("art", ["entschieden", "verworfen", "phase_setzen", None])
def test_arten_ohne_phasenwirkung(conn, art):
    assert phasen.ermoeglichte_phase(conn, 1, art) is None


def test_figur_setzen_zaehlt_erst_ab_der_zweiten_figur(conn):
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    assert phasen.ermoeglichte_phase(conn, 1, "figur_setzen") is None

    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    assert phasen.ermoeglichte_phase(conn, 1, "figur_setzen") == 6


def test_figur_setzen_zeigt_mit_konflikt_auf_die_szenen(conn):
    _zwei_figuren(conn)
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert phasen.ermoeglichte_phase(conn, 1, "figur_setzen") == 7


def test_hauptkonflikt_setzen_zeigt_ohne_figuren_auf_die_figuren(conn):
    assert phasen.ermoeglichte_phase(conn, 1, "hauptkonflikt_setzen") == 5


def test_hauptkonflikt_setzen_zeigt_mit_zwei_figuren_auf_die_szenen(conn):
    _zwei_figuren(conn)
    assert phasen.ermoeglichte_phase(conn, 1, "hauptkonflikt_setzen") == 7


# --- sprung_nach: der automatische Sprung ---------------------------------


def test_sprung_nur_wenn_die_aenderung_genau_die_naechste_phase_traegt(conn):
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    ) == 5


def test_begriffe_springen_von_eins_nach_zwei(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "begriffe_setzen", "wert": "Koffer, Bahnhof"}]
    ) == 2


def test_fragen_springen_von_zwei_nach_drei(conn):
    phasen.setze(conn, 1, 2, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "fragen_setzen", "wert": "Was war in deinem Koffer?"}]
    ) == 3


def test_hauptkonflikt_ohne_figuren_springt_von_vier_nach_fuenf(conn):
    """Die Gruppe hat den Konflikt vor den Figuren benannt -- dann ist die
    naechste Arbeit die an den Figuren, nicht die an den Szenen."""
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "hauptkonflikt_setzen", "wert": "bleiben gegen gehen"}]
    ) == 5


def test_kein_automatischer_sprung_von_fuenf_nach_sechs(conn):
    """Die freie Stelle: die zweite Figur macht den Hauptkonflikt zwar zur
    naechsten Arbeit, aber welche der beiden Phasen zuerst drankommt,
    entscheidet die Gruppe -- nicht der Code."""
    phasen.setze(conn, 1, 5, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    _zwei_figuren(conn)
    assert phasen.ermoeglichte_phase(conn, 1, "figur_setzen") == 6

    assert phasen.sprung_nach(
        conn, 1, [{"art": "figur_setzen", "wert": "Elif"}]
    ) is None


def test_kein_automatischer_sprung_von_sechs_nach_fuenf(conn):
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "hauptkonflikt_setzen", "wert": "bleiben gegen gehen"}]
    ) is None


def test_figur_setzen_springt_von_sechs_nach_sieben(conn):
    """Steht der Konflikt schon, ist die zweite Figur das letzte fehlende
    Stueck fuer die Szenen."""
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    _zwei_figuren(conn)

    assert phasen.sprung_nach(
        conn, 1, [{"art": "figur_setzen", "wert": "Elif"}]
    ) == 7


def test_hauptkonflikt_setzen_springt_von_sechs_nach_sieben(conn):
    phasen.setze(conn, 1, 6, "befehl")
    _zwei_figuren(conn)
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "hauptkonflikt_setzen", "wert": "bleiben gegen gehen"}]
    ) == 7


def test_kein_sprung_ueber_eine_phase_hinweg(conn):
    """Phase 1, ein Kernthema gesetzt: Phase 5 waere moeglich, aber vier
    Stufen auf einmal ist ein Angebot, kein Sprung."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    ) is None


def test_kein_sprung_ohne_belegende_aenderung(conn):
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "entschieden", "wert": "wir treffen uns um zehn"}]
    ) is None


def test_kein_sprung_ohne_materiallage(conn):
    """Die belegende art allein genuegt nicht: steht der Wert nicht wirklich
    im Arbeitsstand, bleibt die Phase, wo sie ist."""
    phasen.setze(conn, 1, 2, "befehl")

    assert phasen.sprung_nach(
        conn, 1, [{"art": "fragen_setzen", "wert": "irgendwas"}]
    ) is None


def test_kein_sprung_wenn_die_gruppe_selbst_eine_phase_genannt_hat(conn):
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    aenderungen = [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "phase_setzen", "wert": "4"},
    ]
    assert phasen.sprung_nach(conn, 1, aenderungen) is None


def test_kein_sprung_ueber_die_letzte_phase_hinaus(conn):
    phasen.setze(conn, 1, 8, "befehl")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    _zwei_figuren(conn)

    assert phasen.sprung_nach(
        conn, 1, [{"art": "figur_setzen", "wert": "Elif"}]
    ) is None

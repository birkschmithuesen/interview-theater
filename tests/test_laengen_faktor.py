"""Die Uebersteuerung: "Kuerzer/Instagram" als dauerhafter Faktor
(30.09.2026, Karte R).

Der Faktor ist ein ZUSTAND: die Gruppe sagt einmal "kuerzer", und danach
werden alle kommenden Szenen kuerzer geplant. Deshalb eine Spalte im
Arbeitsstand und keine Festlegung -- eine Festlegung ist Freitext fuer den
Prompt, und derselbe Wert zweimal zu fuehren waere die doppelte Wahrheit,
gegen die ``repo.FESTLEGUNG_BEREICHE`` gebaut ist.
"""

import pytest

from interview_theater import (
    db, kuerzung, kurzgeschichte, laengen, phasen, repo, szene, workshop,
)

from test_knoepfe import TelegramAttrappe
from test_laengen_prosa import ProsaAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Die Spalte -----------------------------------------------------------


def test_die_spalte_steht_im_schema(conn):
    spalten = {z["name"] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    assert laengen.FELD_FAKTOR in spalten


def test_eine_alte_datenbank_bekommt_die_spalte_nachgeruestet(tmp_path):
    """Additiv ueber ``_migriere_fehlende_spalten``: im Betrieb laufen vier
    Bots auf denselben Dateien, ein Schema-Neubau kostet den Workshop."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    c.execute(f"ALTER TABLE arbeitsstand DROP COLUMN {laengen.FELD_FAKTOR}")
    c.commit()
    c.close()
    c2 = db.verbinde(pfad)
    db.initialisiere(c2)
    spalten = {z["name"] for z in c2.execute("PRAGMA table_info(arbeitsstand)")}
    assert laengen.FELD_FAKTOR in spalten


def test_der_schreibweg_ist_der_vorhandene(conn):
    """``repo.setze_arbeitsstand`` und kein eigenes SQL -- sonst waere es ein
    zweiter Schreibweg fuer denselben Wert."""
    laengen.setze_faktor(conn, 1, 0.25)
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand[laengen.FELD_FAKTOR] == "0.25"


# --- Der gelesene Faktor --------------------------------------------------


def test_ohne_faktor_gilt_eins(conn):
    assert laengen.faktor_aus_stand(None) == 1.0
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


def test_ein_gesetzter_faktor_wird_gelesen(conn):
    laengen.setze_faktor(conn, 1, 0.25)
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 0.25


def test_ein_unsinniger_faktor_gilt_als_keiner(conn):
    """Nachsichtig wie alle Leser dieses Moduls: ein kaputter Wert darf keinen
    Lauf mitnehmen. 0 oder negativ waere eine Szene ohne Woerter, ueber 1 waere
    eine Verlaengerung -- beides ist keine Uebersteuerung."""
    for wert in ("0", "-1", "2", "keine Ahnung", ""):
        repo.setze_arbeitsstand(conn, 1, laengen.FELD_FAKTOR, wert)
        assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


# --- Der Anschluss an den Kuerzen-Weg ------------------------------------


@pytest.fixture
def prosa6(conn, padua):
    """Phase 6, zwei Abschnitte mit Prosa -- der Stand nach einem Prosalauf."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Streit")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.aktualisiere_szene(conn, szene_id, titel, "kurz", None,
                                "passiert", prosa="Ein langer Text. " * 50)
    phasen.setze(conn, 1, 6, "test")
    return conn


def test_kuerzen_der_ganzen_geschichte_setzt_den_faktor(prosa6, tg, einst):
    """"Kuerzer (25 %)" unter der ganzen Geschichte ist die
    Instagram-Entscheidung: sie gilt fuer alles, was danach kommt."""
    klm = ProsaAttrappe()
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == 1.0
    _meldung, gestartet = kuerzung.starte(prosa6, tg, klm, einst, 1)
    assert gestartet is True
    assert kurzgeschichte._sperre_fuer(1).acquire(timeout=20)
    kurzgeschichte._sperre_fuer(1).release()
    # P57 Lauf 3: "25 % kuerzer" heisst Faktor 0,75, nicht 0,25.
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == 0.75


def test_kuerzen_EINER_szene_setzt_den_faktor_nicht(prosa6, tg, einst):
    """OFFENE FRAGE 3 im Plan, geplante Variante: eine Entscheidung ueber eine
    Szene ist keine ueber alle."""
    klm = ProsaAttrappe()
    _meldung, gestartet = kuerzung.starte(prosa6, tg, klm, einst, 1, nummer=1)
    # Abweichung vom Plan: der Szenenweg laeuft unter der SZENEN-Sperre. Der
    # Plan wartete auf die Kurzgeschichte-Sperre und gab sie nie frei -- der
    # naechste Test blockierte daran.
    assert szene._sperre_fuer(1).acquire(timeout=20)
    szene._sperre_fuer(1).release()
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)) == 1.0


def test_ohne_lauf_kein_faktor(conn, padua, tg, einst):
    """Gibt es nichts zu kuerzen, gibt es keinen Lauf -- und dann auch keine
    Entscheidung. ``kuerzung.starte`` liefert ``gestartet = False``."""
    klm = ProsaAttrappe()
    meldung, gestartet = kuerzung.starte(conn, tg, klm, einst, 1)
    assert gestartet is False
    assert meldung == kuerzung.T.TEXT_NICHTS_ZU_KUERZEN   # Padua: englisch
    assert laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)) == 1.0


def test_ohne_aktives_profil_wird_kein_faktor_gesetzt(prosa6, tg, einst, monkeypatch):
    """Dortmund: der Kuerzen-Weg bleibt genau, was er war."""
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    klm = ProsaAttrappe()
    kuerzung.starte(prosa6, tg, klm, einst, 1)
    assert kurzgeschichte._sperre_fuer(1).acquire(timeout=20)
    kurzgeschichte._sperre_fuer(1).release()
    stand = repo.hole_arbeitsstand(prosa6, 1)
    assert (stand[laengen.FELD_FAKTOR] or "") == ""


def test_der_faktor_wirkt_auf_das_naechste_budget(prosa6, padua):
    ziel_vorher = kurzgeschichte.budget_eintraege(prosa6, 1)
    laengen.setze_faktor(prosa6, 1, 0.25)
    ziel_nachher = kurzgeschichte.budget_eintraege(
        prosa6, 1, faktor=laengen.faktor_aus_stand(repo.hole_arbeitsstand(prosa6, 1)),
    )
    assert [b for _n, _f, b in ziel_nachher] != [b for _n, _f, b in ziel_vorher]

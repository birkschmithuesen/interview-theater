"""Tests fuer das Kalibrierungsskript (``scripts/kalibriere_kontext.py``).

Das Skript ist die Grundlage von ``docs/kontext-3-5-kalibrierung.md``. Es
muss ohne Netz, ohne Modell und ohne Betriebsdatenbank laufen -- und es darf
keine Zahl behaupten, die ``kontext.baue`` nicht auch sehen wuerde. Die
Tests pinnen bewusst **keine** Messwerte: die Grenzen werden nach dieser
Messung verschoben (Task 3), und ein Test, der die alten Zahlen festhielte,
waere genau der, der dabei im Weg steht.
"""

from interview_theater import kontext, repo
from scripts import kalibriere_kontext as k


def test_laeuft_ohne_netz_und_liefert_alle_abschnitte(capsys):
    assert k.main(["kalibriere_kontext"]) == 0
    aus = capsys.readouterr().out
    for kopf in (
        "## Systemanweisung je Phase",
        "## Gespraechs-Prompt, Fixture Spaetstand",
        "## Gespraechs-Prompt, Vollast phasengerecht",
        "## Bloecke gegen BUDGETS",
        "## Szenenlauf, Vollast",
    ):
        assert kopf in aus


def test_messung_deckt_sich_mit_kontext_baue():
    """Die Messung nach der Kuerzung ist dieselbe Zahl, die ``baue`` liefert
    -- sonst misst das Skript einen Prompt, den es nicht gibt."""
    conn, _ = k.vollast()
    m = k.miss_phase(conn, 7)
    ausloeser = k._ausloeser(conn)
    koerper = kontext.baue(conn, 1, ausloeser, k._E())
    assert m["nach"] == len(koerper)
    assert m["system"] == len(kontext.system(k.BOT, 7))
    assert m["roh"] >= m["nach"]


def test_vollast_fuellt_das_fenster():
    """Die Vollast ist nur dann eine, wenn das Fenster vor der Kuerzung voll
    ist -- sonst misst sie den ruhigen Fall zweimal."""
    conn, _ = k.vollast()
    m = k.miss_phase(conn, 1, phasengerecht=True)
    # Voll heisst: eine der beiden Obergrenzen des Fensters ist erreicht.
    assert (m["fenster_zeichen_vorher"] > 0.9 * kontext.FENSTER_ZEICHEN
            or m["fenster_vorher"] >= kontext.FENSTER_NACHRICHTEN - 1)
    assert len(repo.festlegungen(conn, 1)) == 20

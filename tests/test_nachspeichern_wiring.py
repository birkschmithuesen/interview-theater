"""Die Verdrahtung des optionalen Nachspeichern-Zusatzes (Karte t_c5d68218)
an den beiden Speicher-Flows, die ihn tragen: der Grundleiste
(``knoepfe.basis._speichere``) und der Geschichte-mit-Szenen-Quittung
(``knoepfe.szenen._nach_szenen_gespeichert``).

Gemessen wird end-to-end ueber ``knoepfe.behandle`` -- derselbe Weg wie ein
echter Knopfdruck -- mit einer Modell-Attrappe statt eines Netzzugriffs:

(a) Sentinel-Pfad ohne Zusatz = nur die Bestaetigung kommt an.
(b) Ein echter Zusatz erscheint als eigene, zweite Nachricht.
(c) Ein scheiternder Modellaufruf bleibt stumm -- die Bestaetigung stand
    schon vorher, die Gruppe bleibt nie unbeantwortet.

Der dritte, bereits bestehende Pfad (``knoepfe.zeige_kurzgeschichte``) ist
bewusst aussen vor: ``tests/test_vorspann_orte.py::
test_der_vorspann_kostet_keinen_modellaufruf`` haelt fest, dass diese
Ansicht KEIN Modellobjekt annimmt (strukturelle Garantie, Zusage aus einem
frueheren Auftrag) -- dort bleibt die Bestaetigungsfrage ohne Modell-Zusatz.
"""

import threading

import pytest

from interview_theater import db, knoepfe, phasen, repo, szene_claude

from tests.test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class _FakeKlm:
    def __init__(self, antwort):
        self._antwort = antwort
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append((chat_id, system, nutzer, art))
        return self._antwort


class _KaputterKlm:
    def prosa(self, *a, **k):
        raise RuntimeError("kaputt")


def _warte_auf_hintergrund_threads(vorher: set, timeout: float = 5.0) -> None:
    for faden in set(threading.enumerate()) - vorher:
        faden.join(timeout)


RAHMEN_ALT = "Ein Hinterhof, Juli, abends"
RAHMEN_NEU = "Eine Kueche, Winter, frueh am Morgen"


def _stelle_offene_aenderung_her(conn):
    """Phase 6, ``rahmen`` schon gesetzt, eine Aenderung ist offen -- die
    Materiallage gibt die naechste Phase nicht her (keine Szenen, kein
    Prosa-Entwurf), ``uebergang_nach_speichern`` bleibt also aus und der
    Code erreicht den Zweig mit der Bestaetigungsfrage."""
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", RAHMEN_ALT)
    repo.setze_arbeitsstand(conn, 1, "aenderung_offen", "rahmen")


def _druecke_speichern(conn, tg, klm, einst):
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN,
        f"rahmen{knoepfe.TRENNER}{RAHMEN_NEU}",
    )
    vorher = set(threading.enumerate())
    knoepfe.behandle(conn, tg, klm, einst, _druck(f"k:{knopf_id}"))
    _warte_auf_hintergrund_threads(vorher)


def test_bestaetigung_ersetzt_die_alte_statische_frage(conn, tg, einst, monkeypatch):
    """Kriterium 1: statt der alten "wollt ihr noch etwas hinzufuegen"-Frage
    steht jetzt eine Bestaetigung."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_offene_aenderung_her(conn)

    _druecke_speichern(conn, tg, _FakeKlm("NICHTS"), einst)

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == RAHMEN_NEU
    assert phasen.aktuelle(conn, 1) == 6, "die Materiallage darf hier nicht weiterspringen"
    assert not any("hinzufuegen" in t for _, t in tg.gesendet)
    assert any("Passt das so" in t for _, t in tg.gesendet)


def test_sentinel_antwort_ergibt_keine_zweite_nachricht(conn, tg, einst, monkeypatch):
    """Kriterium (a): NICHTS vom Modell -- nur die Bestaetigung, kein Zusatz."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_offene_aenderung_her(conn)

    _druecke_speichern(conn, tg, _FakeKlm("NICHTS"), einst)

    texte = [t for _, t in tg.gesendet]
    bestaetigungen = [t for t in texte if "Passt das so" in t]
    assert len(bestaetigungen) == 1
    # Die Notiert-Zeile und die Bestaetigung -- aber kein Zusatz danach.
    assert len(texte) == 2, texte


def test_echter_zusatz_kommt_als_eigene_nachricht_danach(conn, tg, einst, monkeypatch):
    """Kriterium (b): findet das Modell einen Grund, kommt der Zusatz --
    als zweite, eigene Nachricht nach der Bestaetigung."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_offene_aenderung_her(conn)
    zusatz = "Eine Rueckfrage: bleibt die Kueche das ganze Stueck ueber der einzige Ort?"

    _druecke_speichern(conn, tg, _FakeKlm(zusatz), einst)

    texte = [t for _, t in tg.gesendet]
    assert any("Passt das so" in t for t in texte)
    assert zusatz in texte
    # Die Bestaetigung zuerst, der Zusatz danach -- nie umgekehrt.
    assert texte.index([t for t in texte if "Passt das so" in t][0]) < texte.index(zusatz)


def test_scheiternder_modellaufruf_bleibt_stumm(conn, tg, einst, monkeypatch):
    """Kriterium (c): ein Fehlschlag im optionalen Zusatz darf die Gruppe
    nie unbeantwortet lassen -- die Bestaetigung ging schon vorher raus,
    und danach kommt schlicht nichts mehr, kein Absturz, keine Fehlermeldung
    im Chat."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_offene_aenderung_her(conn)

    _druecke_speichern(conn, tg, _KaputterKlm(), einst)

    texte = [t for _, t in tg.gesendet]
    assert len(texte) == 2, texte
    assert any("Passt das so" in t for t in texte)
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (1,),
    ).fetchone()
    assert zeile["art"] == "nachspeichern_fehlgeschlagen"


def test_ohne_sprachmodell_bleibt_es_bei_der_reinen_bestaetigung(conn, tg, monkeypatch):
    """Der Regelfall bestehender Tests: ``klm=None`` (kein Modell übergeben)
    darf nicht brechen -- die weit verbreitete Form in ``knoepfe.behandle``-
    Aufrufen ohne Modell-Attrappe."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_offene_aenderung_her(conn)

    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN, f"rahmen{knoepfe.TRENNER}{RAHMEN_NEU}",
    )
    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))

    texte = [t for _, t in tg.gesendet]
    assert len(texte) == 2, texte
    assert any("Passt das so" in t for t in texte)


# --- Geschichte mit Szenen (knoepfe.szenen._nach_szenen_gespeichert) --------


def _stelle_geschichte_mit_szenen_her(conn):
    """Phase 6, ``geschichte`` schon mal irgendwas (keine Rolle), eine
    Aenderung ist offen, die Richtung traegt zwei Szenenzeilen -- das ist
    der Pfad, der ``_nach_szenen_gespeichert`` erreicht."""
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "aenderung_offen", "geschichte")


RICHTUNG_MIT_SZENEN = (
    "Die Flucht — beginnt am Bahnhof, endet im Zug, Konflikt: wer bleibt zurueck. "
    "Szene 1: Am Bahnhof. Szene 2: Im Zug."
)


def test_geschichte_bestaetigung_und_zusatz(conn, tg, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    _stelle_geschichte_mit_szenen_her(conn)
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_GESCHICHTE_SPEICHERN,
        f"weiter{knoepfe.TRENNER}{RICHTUNG_MIT_SZENEN}",
    )
    zusatz = "Ein Vorschlag: zeigt auch, wer am Bahnsteig zurueckbleibt."
    vorher = set(threading.enumerate())

    knoepfe.behandle(conn, tg, _FakeKlm(zusatz), einst, _druck(f"k:{knopf_id}"))
    _warte_auf_hintergrund_threads(vorher)

    texte = [t for _, t in tg.gesendet]
    assert any("Passt das so" in t for t in texte)
    assert zusatz in texte

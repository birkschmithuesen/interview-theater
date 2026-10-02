"""Der Stromschicht-Kern: aus einem halben JSON den bisherigen Text lesen.

Warum das noetig ist (Praemissenkorrektur im Plan-Kopf): der Gespraechszug
laeuft ueber ``LLM.schema`` mit ``{"antwort": string}``. Was beim Streamen
ankommt, ist also nicht der Text, sondern ein waschsender JSON-Praefix --
und der endet mitten in einem Escape, mitten in einem ``\\uXXXX`` und
mitten in einem Surrogatpaar.

Nichts hier fasst eine Datenbank an: reine Funktionen, Tabellentests.
"""

import pytest

from interview_theater import strom


# -- der Dekoder ------------------------------------------------------------


@pytest.mark.parametrize("praefix,erwartet", [
    ("", ""),
    ("{", ""),
    ('{"antw', ""),
    ('{"antwort"', ""),
    ('{"antwort":', ""),
    ('{"antwort": ', ""),
    ('{"antwort": "', ""),
    ('{"antwort": "Hallo', "Hallo"),
    ('{"antwort": "Hallo"', "Hallo"),
    ('{"antwort": "Hallo"}', "Hallo"),
    ('{"antwort":"Hallo ihr"}', "Hallo ihr"),
    # Der Schluessel darf Leerraum um den Doppelpunkt haben.
    ('{"antwort"  :\n  "Hi', "Hi"),
])
def test_wachsender_praefix(praefix, erwartet):
    assert strom.wert_aus_praefix(praefix) == erwartet


@pytest.mark.parametrize("praefix,erwartet", [
    (r'{"antwort": "Zeile\n', "Zeile\n"),
    (r'{"antwort": "Zeile\\', "Zeile\\"),
    (r'{"antwort": "sie sagte \"ja\"', 'sie sagte "ja"'),
    (r'{"antwort": "Tab\there', "Tab\there"),
    # Halber Escape am Praefixende: der Backslash faellt weg, nicht der Satz.
    ('{"antwort": "Zeile\\', "Zeile"),
    (r'{"antwort": "Gruß', "Gruß"),
    # Halbe \u-Folge: weg, der Rest bleibt.
    (r'{"antwort": "Gru\u00', "Gru"),
    (r'{"antwort": "Gru\u', "Gru"),
])
def test_escapes(praefix, erwartet):
    assert strom.wert_aus_praefix(praefix) == erwartet


def test_surrogatpaar_wird_zusammengesetzt():
    assert strom.wert_aus_praefix(r'{"antwort": "ok 😀"}') == "ok \U0001F600"


def test_halbes_surrogatpaar_faellt_weg_statt_zu_sprengen():
    """Ein einzeln stehendes High-Surrogate laesst sich nicht nach UTF-8
    kodieren -- es wuerde den ``json.dumps`` der SSE-Nutzlast sprengen."""
    ergebnis = strom.wert_aus_praefix(r'{"antwort": "ok \ud83d')
    assert ergebnis == "ok "
    ergebnis.encode("utf-8")   # wirft nicht


def test_ein_anderes_feld_stoert_nicht():
    assert strom.wert_aus_praefix('{"denken": "egal", "antwort": "Text') == "Text"


def test_feldname_ist_waehlbar():
    assert strom.wert_aus_praefix('{"x": "abc', feld="x") == "abc"


# -- was sichtbar wird ------------------------------------------------------


def test_eine_fertige_markerzeile_erscheint_nie():
    """Entscheidung D: VORSCHLAG-Marker sieht die Gruppe nie -- auch nicht
    fuer einen Augenblick."""
    text = "Wie waere es damit?\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit"
    assert "VORSCHLAG" not in strom.sichtbar(text)
    assert "Heimat, Arbeit" in strom.sichtbar(text)


@pytest.mark.parametrize("angefangen", ["V", "VOR", "VORSCHLA", "VORSCHLAG",
                                        "VORSCHLAG BEGR"])
def test_eine_angefangene_markerzeile_erscheint_auch_nicht(angefangen):
    """Der Fall, den ``vorschlag.ohne_marker`` nicht kennt: die Markerzeile
    ist noch nicht fertig getippt."""
    assert strom.sichtbar(f"Wie waere es damit?\n{angefangen}") == "Wie waere es damit?"


def test_ein_gewoehnliches_wort_mit_v_bleibt_stehen():
    assert strom.sichtbar("Wir nehmen\nVier Figuren") == "Wir nehmen\nVier Figuren"


# -- die Drosselung ---------------------------------------------------------


class Uhr:
    """Eine Uhr, die nur weitergeht, wenn der Test es sagt."""

    def __init__(self) -> None:
        self.jetzt = 1000.0

    def __call__(self) -> float:
        return self.jetzt


@pytest.fixture
def aufbau():
    uhr = Uhr()
    geschrieben: list[tuple[int, str]] = []
    beendet: list[tuple[int, str, int | None]] = []
    zaehler = {"n": 0}

    def beginne() -> int:
        zaehler["n"] += 1
        return zaehler["n"]

    senke = strom.Senke(
        beginne,
        lambda sid, text: geschrieben.append((sid, text)),
        lambda sid, zustand, post_id: beendet.append((sid, zustand, post_id)),
        uhr=uhr,
    )
    return senke, uhr, geschrieben, beendet


def test_die_erste_zeile_geht_sofort_raus(aufbau):
    senke, _uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    assert geschrieben == [(1, "Hallo")]


def test_innerhalb_des_takts_wird_nichts_geschrieben(aufbau):
    senke, uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    uhr.jetzt += 0.05
    senke("Hallo ihr")
    assert geschrieben == [(1, "Hallo")]


def test_nach_dem_takt_wird_wieder_geschrieben(aufbau):
    senke, uhr, geschrieben, _beendet = aufbau
    senke("Hallo")
    uhr.jetzt += strom.INTERVALL_S
    senke("Hallo ihr")
    assert geschrieben == [(1, "Hallo"), (1, "Hallo ihr")]


def test_der_letzte_stand_geht_beim_abschluss_immer_raus(aufbau):
    """Sonst fehlte der Gruppe genau der Satz, auf den sie gewartet hat."""
    senke, _uhr, geschrieben, beendet = aufbau
    senke("Hallo")
    senke("Hallo ihr alle")          # innerhalb des Takts -- nicht geschrieben
    senke.fertig(post_id=42)
    assert geschrieben[-1] == (1, "Hallo ihr alle")
    assert beendet == [(1, "fertig", 42)]


def test_abbruch_beendet_ohne_nachricht(aufbau):
    senke, _uhr, _geschrieben, beendet = aufbau
    senke("halb")
    senke.abbruch()
    assert beendet == [(1, "abgebrochen", None)]


def test_neu_faengt_eine_zweite_zeile_an_statt_anzuhaengen(aufbau):
    """Entscheidung D: loest ``_ohne_echo`` einen zweiten Aufruf aus, beginnt
    der Strom neu -- sonst klebte die verworfene Antwort davor."""
    senke, uhr, geschrieben, beendet = aufbau
    senke("erster Versuch")
    senke.neu()
    uhr.jetzt += strom.INTERVALL_S
    senke("zweiter Versuch")
    assert beendet[0][1] == "abgebrochen"
    assert geschrieben[-1] == (2, "zweiter Versuch")


def test_zweimal_fertig_beendet_nur_einmal(aufbau):
    senke, _uhr, _geschrieben, beendet = aufbau
    senke("x")
    senke.fertig(1)
    senke.fertig(2)
    assert beendet == [(1, "fertig", 1)]


def test_ohne_ein_einziges_stueck_passiert_gar_nichts(aufbau):
    """Ein Aufruf, der sofort scheitert, soll keine leere Blase hinterlassen."""
    senke, _uhr, geschrieben, beendet = aufbau
    senke.abbruch()
    assert geschrieben == [] and beendet == []


# -- Fix-Runde Abschluss, Befund 2: ein werfender Abschluss kostet nicht --
# die bezahlte Antwort ---------------------------------------------------


@pytest.fixture
def aufbau_werfend():
    """Wie ``aufbau``, nur dass ``beende`` immer wirft -- so wie
    ``repo.beende_strom`` es bei "database is locked" tut."""
    uhr = Uhr()
    geschrieben: list[tuple[int, str]] = []
    zaehler = {"n": 0}

    def beginne() -> int:
        zaehler["n"] += 1
        return zaehler["n"]

    def beende(sid, zustand, post_id):
        raise RuntimeError("database is locked")

    senke = strom.Senke(
        beginne, lambda sid, text: geschrieben.append((sid, text)), beende, uhr=uhr,
    )
    return senke, geschrieben


def test_fertig_wirft_nicht_wenn_der_abschluss_scheitert(aufbau_werfend):
    senke, _geschrieben = aufbau_werfend
    senke("Hallo")
    senke.fertig(post_id=42)          # wirft NICHT -- das ist die Zusage


def test_abbruch_wirft_nicht_wenn_der_abschluss_scheitert(aufbau_werfend):
    senke, _geschrieben = aufbau_werfend
    senke("Hallo")
    senke.abbruch()                   # wirft NICHT


def test_neu_wirft_nicht_wenn_der_abschluss_scheitert(aufbau_werfend):
    senke, _geschrieben = aufbau_werfend
    senke("Hallo")
    senke.neu()                       # wirft NICHT -- delegiert an abbruch()


def test_nach_einem_werfenden_fertig_ist_die_zeile_trotzdem_zu(aufbau_werfend):
    """Sonst versuchte der naechste Aufruf (z. B. ein zweites ``fertig``)
    erneut, dieselbe schon kaputte Zeile abzuschliessen."""
    senke, geschrieben = aufbau_werfend
    senke("Hallo")
    senke.fertig(post_id=1)
    assert senke.strom_id is None
    senke("Neuer Zug")                # legt eine NEUE Zeile an, keine alte
    assert geschrieben[-1] == (2, "Neuer Zug")


def test_ein_werfender_abschluss_wird_geloggt(aufbau_werfend, caplog):
    import logging

    senke, _geschrieben = aufbau_werfend
    senke("Hallo")
    with caplog.at_level(logging.ERROR, logger="interview_theater.strom"):
        senke.fertig(post_id=1)
    assert "database is locked" in caplog.text


# -- die drei Kanal-Helfer --------------------------------------------------


class OhneStrom:
    """So sieht ``telegram.Telegram`` aus: kein ``strom``."""


class MitStrom:
    def __init__(self) -> None:
        self.gerufen: list = []

    def strom(self, chat_id, art):
        self.gerufen.append(("strom", chat_id, art))
        return "senke"

    def strom_abschluss(self, chat_id, post_id=None, abgebrochen=False):
        self.gerufen.append(("ab", chat_id, post_id, abgebrochen))


def test_ein_kanal_ohne_strom_liefert_none_und_faellt_nicht_um():
    """E1: ``telegram.Telegram`` bekommt nichts dazu."""
    tg = OhneStrom()
    assert strom.senke(tg, 1, "gespraech") is None
    strom.schliesse(tg, 1, 5)     # wirft nicht
    strom.verwirf(tg, 1)          # wirft nicht


def test_ein_kanal_mit_strom_wird_gerufen():
    tg = MitStrom()
    assert strom.senke(tg, 7, "gespraech") == "senke"
    strom.schliesse(tg, 7, 5)
    strom.verwirf(tg, 7)
    assert tg.gerufen == [
        ("strom", 7, "gespraech"), ("ab", 7, 5, False), ("ab", 7, None, True),
    ]

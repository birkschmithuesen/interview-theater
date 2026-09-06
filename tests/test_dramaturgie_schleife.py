"""Schicht 4b: die Rueckkopplungsschleife.

Alle Modellaufrufe laufen gegen Attrappen -- den ``Rundenrichter`` (ein
Richter, dessen Scores je Runde feststehen) und die ``Schreibattrappe`` (ein
Schreibpfad, der keinen Text erfindet, sondern den vorhandenen markiert).
Geprueft wird die Schleife selbst: die drei Abbruchbedingungen, die Bilanz
zwischen den Runden, der zur Phase passende Schreibweg -- und die drei
Grenzen, die bleiben muessen (Parameterbefund, verifiziertes Belegzitat,
keine automatische Uebernahme).
"""

import re
import sys
import types

import pytest
from interview_theater import repo, szene
from interview_theater.dramaturgie import bilanz, fanout, schleife

from test_dramaturgie_fanout import SZENE_1, SZENE_2, einst, stueck  # noqa: F401
from test_knoepfe import TelegramAttrappe

# --- Attrappen ------------------------------------------------------------

#: Das Wort, an dem die Richter-Attrappe eine ueberarbeitete Szene erkennt.
#: Es steht im Szenentext und ist damit genau das, was der Judge sieht.
MARKE = "UEBERARBEITET"

_SZENE_IM_KOPF = re.compile(r"(?:Das ist Szene|Repliken von Szene) (\d+)")


def _material(nutzer: str, marke: str) -> str:
    auf, zu = fanout.MARKEN[marke]
    return nutzer.split(auf, 1)[-1].split(zu, 1)[0]


def _zitat(nutzer: str, marke: str = "szene") -> str:
    """Ein Belegzitat, das die Verifikation besteht: eine Zeile aus genau dem
    Material, das im Prompt stand. Hier wird die Schleife geprueft und nicht
    noch einmal die Belegschleife."""
    for zeile in _material(nutzer, marke).splitlines():
        kern = zeile.strip()
        if len(kern) >= fanout.beleg_modul.MINDESTLAENGE + 5:
            return kern
    return ""


class Rundenrichter(fanout.Richter):
    """Ein Richter, dessen Scores je Frage, Szene und Runde feststehen.

    ``plan`` ist ``{(schluessel, szene): [score_runde_1, score_runde_2, ...]}``.
    Eine Frage ohne Eintrag bekommt eine leere Antwort und erzeugt damit
    weder Befund noch Bewertung."""

    def __init__(self, plan, modell="attrappe"):
        super().__init__("attrappe", modell)
        self.plan = plan
        self.gezaehlt: dict = {}
        self.gesehen: list = []

    def frage(self, conn, e, klm, chat_id, system, nutzer, art):
        self.aufrufe += 1
        self.gesehen.append((art, nutzer))
        schluessel = next(
            (k for k, wert in fanout.ARTEN.items() if wert == art), art
        )
        treffer = _SZENE_IM_KOPF.search(nutzer.split(fanout.MARKEN["szene"][0])[0])
        adresse = (schluessel, int(treffer.group(1)) if treffer else None)
        scores = self.plan.get(adresse)
        if not scores:
            return ""
        n = self.gezaehlt.get(adresse, 0)
        self.gezaehlt[adresse] = n + 1
        score = scores[min(n, len(scores) - 1)]
        nummer = adresse[1] or 1
        marke = "synopsen" if adresse[0] in ("a2", "a11") else "szene"
        return (
            f"SCORE: {score}\n"
            "BEFUND: Die Szene endet, wie sie anfaengt.\n"
            f"BELEG: {_zitat(nutzer, marke)}\n"
            "SCHWERE: hoch\n"
            "RICHTUNG: text\n"
            f"VORSCHLAG: Szene {nummer}: Lass Mira den Koffer oeffnen, "
            "damit Jonas sieht, was darin ist.\n"
            "UNSICHER: nein\n"
        )


class Schreibattrappe:
    """Der Schreibpfad ohne Modell: sie markiert den Szenentext, statt einen
    neuen zu erfinden. Sie zeichnet auf, welche Auftraege sie bekommen hat --
    daran haengen die Tests zu den Grenzen."""

    def __init__(self, conn):
        self.conn = conn
        self.auftraege: list = []

    def __call__(self, conn, tg, klm, e, chat_id, auftraege):
        self.auftraege.extend(auftraege)
        nummern = []
        for auftrag in auftraege:
            nummer = auftrag["szene"]
            zeile = next(
                s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == nummer
            )
            conn.execute(
                "UPDATE szene SET volltext = ? WHERE id = ?",
                (f"{zeile['volltext']}\nMIRA: {MARKE}, jetzt steht es anders.",
                 zeile["id"]),
            )
            nummern.append(nummer)
        conn.commit()
        return nummern


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _besser(plan_score_vorher=0, plan_score_nachher=2):
    """Ein Plan, in dem Szene 1 in Runde 2 besser dasteht."""
    return {("b1", 1): [plan_score_vorher, plan_score_nachher]}


# --- Der Regelfall --------------------------------------------------------


def test_die_schleife_prueft_ueberarbeitet_und_prueft_erneut(stueck, einst, tg):
    schreiber = Schreibattrappe(stueck)
    richter = Rundenrichter(_besser())

    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1, richter=richter, schreiber=schreiber,
    )

    assert [r.nummer for r in ergebnis.runden] == [1, 2]
    assert [a["szene"] for a in schreiber.auftraege] == [1]
    assert ergebnis.grund == schleife.GRUND_KEINE_AUFTRAEGE


def test_die_bilanz_vergleicht_die_scores_der_beiden_runden(stueck, einst, tg):
    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter(_besser()), schreiber=Schreibattrappe(stueck),
    )

    (vergleich,) = ergebnis.bilanzen[0].vergleiche
    assert (vergleich.pruefung, vergleich.szene) == ("b1", 1)
    assert (vergleich.vorher, vergleich.nachher) == (0, 2)
    assert vergleich.richtung == bilanz.BESSER
    assert not ergebnis.geschadet


def test_jede_runde_hat_ihre_nummer_und_ihre_befunde(stueck, einst, tg):
    schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter(_besser()), schreiber=Schreibattrappe(stueck),
    )

    assert repo.dramaturgie_befunde(stueck, 1, runde=1)
    assert {z["runde"] for z in repo.dramaturgie_bewertungen(stueck, 1)} == {1, 2}


def test_derselbe_richter_prueft_beide_runden(stueck, einst, tg):
    """Zwei Runden mit verschiedenen Modellen liefern keine vergleichbaren
    Scores -- die Bilanz waere dann eine Aussage ueber den Modellwechsel."""
    richter = Rundenrichter(_besser())

    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1, richter=richter,
        schreiber=Schreibattrappe(stueck),
    )

    assert all(r.ergebnis.richter is richter for r in ergebnis.runden)


# --- Die drei Abbruchbedingungen ------------------------------------------


def test_ohne_auftraege_wird_gar_nicht_erst_geschrieben(stueck, einst, tg):
    """Ein Text, der keinen harten Befund traegt, wird nicht angefasst."""
    schreiber = Schreibattrappe(stueck)

    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter({("b1", 1): [2]}), schreiber=schreiber,
    )

    assert schreiber.auftraege == []
    assert len(ergebnis.runden) == 1
    assert ergebnis.grund == schleife.GRUND_KEINE_AUFTRAEGE


def test_nach_hoechstens_zwei_runden_ist_schluss(stueck, einst, tg):
    """Ein Stueck, das in jeder Runde denselben Befund traegt, laeuft nicht
    ewig: das Rundenlimit ist der Auffangfall."""
    schreiber = Schreibattrappe(stueck)

    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter({("b1", 1): [0]}), schreiber=schreiber,
    )

    assert schleife.RUNDEN_MAX == 2
    assert len(schreiber.auftraege) == schleife.RUNDEN_MAX
    assert [r.nummer for r in ergebnis.runden] == [1, 2, 3]
    assert ergebnis.grund == schleife.GRUND_RUNDENLIMIT


def test_das_rundenlimit_laesst_sich_fuer_einen_lauf_senken(stueck, einst, tg):
    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1, runden_max=1,
        richter=Rundenrichter({("b1", 1): [0]}), schreiber=Schreibattrappe(stueck),
    )

    assert [r.nummer for r in ergebnis.runden] == [1, 2]
    assert ergebnis.grund == schleife.GRUND_RUNDENLIMIT


def test_ein_gefallener_score_bricht_die_schleife_ab(stueck, einst, tg):
    """Der Fall, wegen dem die Bilanz Scores und nicht Befunde vergleicht:
    die Ueberarbeitung von Szene 1 hat Szene 2 kaputt gemacht."""
    plan = {("b1", 1): [0, 2], ("b1", 2): [2, 0]}

    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter(plan), schreiber=Schreibattrappe(stueck),
    )

    assert ergebnis.grund == schleife.GRUND_GESCHADET
    assert ergebnis.geschadet
    assert len(ergebnis.runden) == 2
    schaden = ergebnis.bilanzen[0].schlechter
    assert [(v.pruefung, v.szene, v.vorher, v.nachher) for v in schaden] == [
        ("b1", 2, 2, 0)
    ]


def test_die_verschlechterung_wird_sichtbar_vermerkt(stueck, einst, tg):
    """Sichtbar heisst nicht "steht irgendwo in einer Bilanz": das Dashboard
    soll sie zeigen, ohne dass jemand den Bericht liest."""
    plan = {("b1", 1): [0, 2], ("b1", 2): [2, 0]}

    schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter(plan), schreiber=Schreibattrappe(stueck),
    )

    schaden = stueck.execute(
        "SELECT detail FROM vorfall WHERE chat_id = 1 AND art = ?",
        (schleife.VORFALL_GESCHADET,),
    ).fetchall()
    assert len(schaden) == 1
    assert "Szene 2: 2 -> 0" in schaden[0]["detail"]


def test_der_grund_steht_als_satz_im_ergebnis(stueck, einst, tg):
    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=Rundenrichter({("b1", 1): [2]}), schreiber=Schreibattrappe(stueck),
    )

    assert ergebnis.meldung == schleife.GRUENDE[schleife.GRUND_KEINE_AUFTRAEGE]
    assert "Runde 1:" in ergebnis.als_text()
    assert "Schluss:" in ergebnis.als_text()


# --- Die Grenzen, die bleiben muessen -------------------------------------


def test_ein_parameterbefund_erzeugt_nie_einen_schreibauftrag(stueck, einst, tg):
    """``richtung=parameter`` heisst: der TEXT hat recht, die Festlegung ist
    veraltet. Das an den Schreiber zu geben hiesse, den Text auf eine
    ueberholte Planung zurueckzubiegen -- das Gegenteil des Befunds."""
    szene_id = repo.hole_letzte_szene(stueck, 1)["id"]
    repo.setze_szenenfeld(stueck, szene_id, "ort", "Eine Kueche")
    stueck.commit()

    class NurParameter(Rundenrichter):
        def frage(self, conn, e, klm, chat_id, system, nutzer, art):
            antwort = super().frage(conn, e, klm, chat_id, system, nutzer, art)
            return antwort.replace("RICHTUNG: text", "RICHTUNG: parameter")

    schreiber = Schreibattrappe(stueck)
    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=NurParameter({("a10", 2): [0]}), schreiber=schreiber,
    )

    assert schreiber.auftraege == []
    assert ergebnis.grund == schleife.GRUND_KEINE_AUFTRAEGE
    # Der Befund selbst bleibt stehen -- er geht als Vorschlag an die Gruppe,
    # und seine Richtung ueberlebt den Weg durch die Datenbank.
    a10 = [z for z in repo.dramaturgie_befunde(stueck, 1) if z["pruefung"] == "a10"]
    assert [z["richtung"] for z in a10] == ["parameter"]


def test_ein_befund_ohne_geprueften_beleg_steuert_den_schreiber_nicht(
    stueck, einst, tg
):
    class MitErfundenemBeleg(Rundenrichter):
        def frage(self, conn, e, klm, chat_id, system, nutzer, art):
            antwort = super().frage(conn, e, klm, chat_id, system, nutzer, art)
            return re.sub(r"BELEG: .*", "BELEG: Das steht so nirgends im Text.",
                          antwort)

    schreiber = Schreibattrappe(stueck)
    schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=MitErfundenemBeleg({("b1", 1): [0]}), schreiber=schreiber,
    )

    assert schreiber.auftraege == []


def test_ein_verworfener_score_kommt_nicht_in_die_bilanz(stueck, einst, tg):
    class MitErfundenemBeleg(Rundenrichter):
        def frage(self, conn, e, klm, chat_id, system, nutzer, art):
            antwort = super().frage(conn, e, klm, chat_id, system, nutzer, art)
            return re.sub(r"BELEG: .*", "BELEG: Das steht so nirgends im Text.",
                          antwort)

    schleife.schliesse(
        stueck, tg, None, einst, 1,
        richter=MitErfundenemBeleg({("b1", 1): [0]}), schreiber=Schreibattrappe(stueck),
    )

    assert repo.dramaturgie_bewertungen(stueck, 1) == []


def test_die_schleife_haengt_an_keinem_knopf():
    """Keine automatische Uebernahme in die Live-Daten: die Schleife wird
    nicht aus einem Knopf-Handler gestartet und nicht aus ``fanout.starte``.
    Sie schlaegt vor, die Gruppe bestaetigt."""
    from interview_theater import knoepfe

    for modul in (knoepfe, fanout):
        with open(modul.__file__, encoding="utf-8") as datei:
            quelle = datei.read()
        assert "import schleife" not in quelle
        assert "schleife.schliesse" not in quelle


# --- Der Schreibweg, der zur Phase passt ----------------------------------


def test_im_feinschliff_wird_je_szene_geschrieben(stueck, einst):
    repo.setze_phase(stueck, 1, 7)

    assert schleife.schreibweg(stueck, 1) is schleife._schreibe_je_szene


def test_in_der_prosaphase_geht_ein_lauf_ueber_die_ganze_geschichte(stueck, einst):
    repo.setze_phase(stueck, 1, 6)

    assert schleife.schreibweg(stueck, 1) is schleife._schreibe_die_geschichte


def test_ohne_geschichtenweg_gibt_es_keinen_modellaufruf(stueck, einst, tg):
    """Kein stiller Rueckfall auf den phasenfremden Pfad: der laeuft ohne
    Fehler durch und liefert gemessen schwaechere Texte."""
    repo.setze_phase(stueck, 1, 6)

    with pytest.raises(schleife.SchreibwegFehlt):
        schleife._schreibe_die_geschichte(
            stueck, tg, None, einst, 1, [{"szene": 1, "anweisung": "x"}]
        )


def test_die_prosaphase_nimmt_einen_lauf_fuer_alle_auftraege(
    stueck, einst, tg, monkeypatch
):
    """Ein Lauf, EINE Regie-Notiz mit allen Auftraegen -- nicht ein Lauf je
    Szene."""
    laeufe = []
    attrappe = types.ModuleType(schleife.GESCHICHTE_MODUL)
    attrappe.schreibe = (
        lambda conn, tg_, klm, e_, chat_id, regie: laeufe.append(regie)
    )
    monkeypatch.setitem(sys.modules, schleife.GESCHICHTE_MODUL, attrappe)
    repo.setze_phase(stueck, 1, 6)

    auftraege = [
        {"szene": 1, "anweisung": "Lass Mira den Koffer oeffnen."},
        {"szene": 2, "anweisung": "Gib Jonas ein eigenes Fuellwort."},
    ]
    nummern = schleife._schreibe_die_geschichte(
        stueck, tg, None, einst, 1, auftraege
    )

    assert len(laeufe) == 1
    assert "Szene 1: Lass Mira den Koffer oeffnen." in laeufe[0]
    assert "Szene 2: Gib Jonas ein eigenes Fuellwort." in laeufe[0]
    assert nummern == [1, 2]


def test_der_auftragstext_ist_derselbe_wie_am_knopf():
    """Zwei Wortlaute waeren zwei Prompts -- und ein Unterschied, den niemand
    bemerkt, weil beide funktionieren."""
    befund = {"szene": 3, "pruefung": "b1", "vorschlag": "Szene 3: Mira geht."}
    auftrag = {"szene": 3, "pruefung": "b1", "anweisung": "Szene 3: Mira geht."}

    assert fanout.szenenauftrag(befund) == fanout.szenenauftrag(auftrag)
    assert fanout.szenenauftrag(auftrag).startswith("Schreib Szene 3 neu.")


def test_eine_szene_mit_fehlendem_pflichtfeld_wird_uebersprungen(
    stueck, einst, tg, monkeypatch
):
    """``szene.schreibe`` prueft die Sperre nicht selbst -- ein Lauf ohne Ort
    und Besetzung erfindet welche. Die Schleife prueft sie deshalb."""
    monkeypatch.setattr(szene, "sperrtext", lambda conn, ziel: "Mir fehlt der Ort.")
    gerufen = []
    monkeypatch.setattr(
        szene, "schreibe",
        lambda *a, **k: gerufen.append(a) or 1,
    )

    nummern = schleife._schreibe_je_szene(
        stueck, tg, None, einst, 1,
        [{"szene": 1, "pruefung": "b1", "anweisung": "Szene 1: Mira geht."}],
    )

    assert gerufen == []
    assert nummern == []

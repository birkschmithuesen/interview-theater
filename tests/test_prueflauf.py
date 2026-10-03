"""Der Prueflauf vor jeder Anzeige (Padua Phasen TEIL 2, Task 6).

Alle Modellaufrufe laufen gegen Attrappen: der ``Rundenrichter`` aus
``test_dramaturgie_schleife`` (Scores je Frage, Szene und Runde stehen fest)
und eine Schreibattrappe, die der Reihe nach vorgegebene Prosa liefert.
Geprueft wird der Ablauf: Teilmenge der Fragen, hoechstens zwei
Ueberarbeitungen, die bessere Fassung bei einem gefallenen Score, die
Zitatwache, die Erstfassung, hoechstens drei Zeilen und die Protokollzeile.
"""

import re

import pytest

import test_dramaturgie_schleife as schleifentest
from interview_theater import phasen, prueflauf, repo, szene, workshop
from interview_theater.dramaturgie import fanout, schleife
from test_dramaturgie_schleife import Rundenrichter
from test_knoepfe import TelegramAttrappe

ZITAT = "also ich, ja, ich weiss nicht"

VORHER = (
    f"Mira steht am Steg und sagt: {ZITAT}. Jonas schaut auf das Wasser "
    "und antwortet lange nicht.\n"
    "Dann geht er, und Mira bleibt allein am Steg zurueck, bis es dunkel wird.\n"
)


def _antwort(koerper: str) -> str:
    return (
        "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
        "ZUSAMMENFASSUNG: Mira und Jonas treffen sich.\nANDERS GEMACHT: nichts\n\n"
        + koerper
    )


#: Die Ueberarbeitung behaelt das Zitat.
MIT_ZITAT = _antwort(
    f"Mira steht am Steg und sagt: {ZITAT}. Jonas oeffnet den Koffer, "
    "und Mira sieht, was darin liegt.\n"
    "Danach bleibt keiner von beiden derselbe, und der Steg ist leer.\n"
)

#: Die Ueberarbeitung glaettet das Zitat weg (theater-tells Nr. 21).
OHNE_ZITAT = _antwort(
    "Mira steht am Steg und sagt, dass es eine schwierige Zeit war. Jonas "
    "oeffnet den Koffer, und Mira sieht, was darin liegt.\n"
    "Danach bleibt keiner von beiden derselbe, und der Steg ist leer.\n"
)


class Schreiber:
    """Die Sprachmodell-Attrappe des Szenenlaufs: liefert der Reihe nach die
    vorgegebenen Antworten und merkt jeden Aufruf samt ``art``."""

    def __init__(self, *antworten):
        self.antworten = list(antworten) or [MIT_ZITAT]
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe.append(art)
        i = min(len(self.aufrufe) - 1, len(self.antworten) - 1)
        return self.antworten[i]

    def ueberarbeitungen(self) -> int:
        return sum(1 for a in self.aufrufe if a == prueflauf.ART_UEBERARBEITUNG)


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    # Der Rundenrichter erkennt die Szene am deutschen Kopf; Padua spricht
    # Englisch ("This is scene N of the play.").
    monkeypatch.setattr(schleifentest, "_SZENE_IM_KOPF", re.compile(
        r"(?:Das ist Szene|Repliken von Szene|This is scene) (\d+)"))
    yield
    workshop.vergiss()


@pytest.fixture
def szene6(conn, padua):
    """Phase 6, Szene 1 als Geschichte, mit einem geprueften Zitat."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jonas", "schweigt lieber")
    ids = [repo.hole_figur(conn, 1, n)["id"] for n in ("Mira", "Jonas")]
    repo.setze_sprachprofil(conn, ids[0], "kurze Saetze", [ZITAT])
    repo.setze_sprachprofil(conn, ids[1], "wenige Worte", [])
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("ort", "Steg"), ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, ids)
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", "kurz", None,
                            "Mira und Jonas treffen sich.", prosa=VORHER.strip())
    phasen.setze(conn, 1, 6, "test")
    return conn


def _richter(monkeypatch, plan):
    richter = Rundenrichter(plan)
    monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)
    return richter


def _prosa(conn) -> str:
    return repo.hole_szenen(conn, 1)[0]["prosa"]


# --- Die Schleife ---------------------------------------------------------


def test_pruefe_szene_hoechstens_zwei_ueberarbeitungen_und_protokoll(
        szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [0]})
    klm = Schreiber(MIT_ZITAT)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert bericht.ueberarbeitungen <= 2
    assert klm.ueberarbeitungen() == bericht.ueberarbeitungen == 2
    (zeile,) = repo.prueflaeufe(szene6, 1)
    assert zeile["ziel"] == "szene"
    assert zeile["szene_nummer"] == 1
    assert zeile["fragen"] == "b1,a10"
    assert zeile["zweite_runde_mit_auftraegen"] == 1
    assert zeile["grund"] == schleife.GRUND_RUNDENLIMIT
    assert zeile["ueberarbeitungen"] == 2
    assert zeile["runden"] == 3
    assert bericht.auftraege_je_runde == [1, 1, 1]
    # Der Prueflauf zeigt nichts -- das macht der Aufrufer (Task 7).
    assert tg.gesendet == [] and tg.knoepfe == []


def test_pruefe_szene_ohne_auftraege_schreibt_nicht(szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [2]})
    klm = Schreiber(MIT_ZITAT)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert klm.ueberarbeitungen() == 0
    assert bericht.grund == schleife.GRUND_KEINE_AUFTRAEGE
    assert bericht.ueberarbeitungen == 0
    assert _prosa(szene6) == VORHER.strip()
    assert repo.prueflaeufe(szene6, 1)[0]["zweite_runde_mit_auftraegen"] == 0


def test_verschlechterung_laesst_die_bessere_fassung_und_sagt_es(
        szene6, tg, einst, monkeypatch):
    # B1 traegt den Auftrag, A10 faellt nach der Ueberarbeitung von 2 auf 0.
    _richter(monkeypatch, {("b1", 1): [0], ("a10", 1): [2, 0]})
    klm = Schreiber(MIT_ZITAT)
    vorher = _prosa(szene6)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert klm.ueberarbeitungen() == 1
    assert _prosa(szene6) == vorher
    assert prueflauf.T._ZEILE_VERSCHLECHTERT in bericht.zeilen
    assert bericht.zeilen[0].startswith("The revision was weaker")
    assert bericht.verworfen == "verschlechterung"
    assert repo.prueflaeufe(szene6, 1)[0]["verworfen"] == "verschlechterung"


def test_verlorenes_zitat_wird_verworfen(szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [0, 2]})
    klm = Schreiber(OHNE_ZITAT)
    vorher = _prosa(szene6)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert klm.ueberarbeitungen() == 1
    assert _prosa(szene6) == vorher
    assert ZITAT in _prosa(szene6)
    assert bericht.verworfen == "zitat"
    assert prueflauf.T._ZEILE_ZITAT_VERWORFEN in bericht.zeilen
    assert repo.prueflaeufe(szene6, 1)[0]["verworfen"] == "zitat"


def test_erstentwurf_zeigt_auf_die_fassung_vor_der_pruefung(
        szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [0, 2]})
    klm = Schreiber(MIT_ZITAT)
    vorher = _prosa(szene6)
    szene_id = repo.hole_szenen(szene6, 1)[0]["id"]

    prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert klm.ueberarbeitungen() == 1
    assert repo.erstentwurf_text(szene6, szene_id) == vorher
    assert _prosa(szene6) != vorher


def test_hoechstens_drei_zeilen(szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [0], ("a10", 1): [0]})
    klm = Schreiber(MIT_ZITAT)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert bericht.auftraege_je_runde[0] == 2
    assert bericht.ueberarbeitungen == 2
    assert 0 < len(bericht.zeilen) <= 3
    assert bericht.zeilen[0].startswith("Check (")


def test_richterfehler_zeigt_trotzdem_und_protokolliert(szene6, tg, einst, monkeypatch):
    def _fehler(*a, **k):
        raise fanout.RichterFehler("x")

    monkeypatch.setattr(fanout, "waehle_richter", _fehler)
    klm = Schreiber(MIT_ZITAT)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert bericht.zeilen == ["x"]
    assert klm.ueberarbeitungen() == 0
    (zeile,) = repo.prueflaeufe(szene6, 1)
    assert zeile["grund"] == "ohne_pruefung"
    assert zeile["runden"] == 0
    arten = [z["art"] for z in szene6.execute("SELECT art FROM vorfall")]
    assert "prueflauf_ohne_richter" in arten


def test_ohne_text_kein_lauf(conn, padua, tg, einst, monkeypatch):
    repo.stelle_szene_sicher(conn, 1, 1)
    phasen.setze(conn, 1, 6, "test")
    _richter(monkeypatch, {("b1", 1): [0]})

    bericht = prueflauf.pruefe_szene(conn, tg, Schreiber(), einst, 1, 1)

    assert bericht.grund == "ohne_text"
    assert repo.prueflaeufe(conn, 1) == []


class Parameterrichter(Rundenrichter):
    """A10 sagt: der Text hat recht, die Planung (``ort``) ist veraltet."""

    def frage(self, conn, e, klm, chat_id, system, nutzer, art):
        if art != fanout.ARTEN["a10"]:
            return super().frage(conn, e, klm, chat_id, system, nutzer, art)
        self.aufrufe += 1
        return (
            "SCORE: 0\nBEFUND: Die Szene spielt am Steg, geplant war anderes.\n"
            f"BELEG: {schleifentest._zitat(nutzer)}\nSCHWERE: hoch\n"
            "RICHTUNG: parameter\nVORSCHLAG: ort: Am Steg im Regen\nUNSICHER: nein\n"
        )


def test_a10_parameterbefund_laesst_die_planung_dem_text_folgen(
        szene6, tg, einst, monkeypatch):
    richter = Parameterrichter({})
    monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)
    klm = Schreiber(MIT_ZITAT)

    bericht = prueflauf.pruefe_szene(szene6, tg, klm, einst, 1, 1)

    assert klm.ueberarbeitungen() == 0          # ein Parameterbefund schreibt nie
    assert repo.hole_szenen(szene6, 1)[0]["ort"] == "Am Steg im Regen"
    assert bericht.zeilen == [prueflauf.T._ZEILE_PARAMETER.format(nummer=1, feld="ort")]
    journal = [z for z in repo.journal(szene6, 1) if z["quelle"] == "prueflauf"]
    assert len(journal) == 1 and journal[0]["art"] == "entschieden"


# --- Die Fragen je Lage ---------------------------------------------------


def _spion(monkeypatch):
    gesehen: list = []
    echt = fanout.pruefe

    def spion(*a, **k):
        gesehen.append(k)
        return echt(*a, **k)

    monkeypatch.setattr(fanout, "pruefe", spion)
    return gesehen


def test_pruefe_geschichte_nutzt_die_ganzstueck_fragen(szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {})
    gesehen = _spion(monkeypatch)

    bericht = prueflauf.pruefe_geschichte(szene6, tg, Schreiber(), einst, 1)

    assert gesehen[0]["fragen"] == prueflauf.FRAGEN_GESCHICHTE
    assert gesehen[0]["szenen"] is None
    assert gesehen[0]["mechanik"] is False
    (zeile,) = repo.prueflaeufe(szene6, 1)
    assert zeile["ziel"] == "geschichte"
    assert zeile["szene_nummer"] is None
    assert bericht.grund == schleife.GRUND_KEINE_AUFTRAEGE


def test_buehnenszene_fragt_a10_und_c1(szene6, tg, einst, monkeypatch):
    szene_id = repo.hole_szenen(szene6, 1)[0]["id"]
    repo.setze_szenenfeld(szene6, szene_id, "form", "dialog")
    repo.aktualisiere_szene(
        szene6, szene_id, "Am Steg", "kurz",
        f"MIRA: {ZITAT}.\nJONAS: Und?\nMIRA: Nichts.\n", "Sie treffen sich.")
    phasen.setze(szene6, 1, 7, "test")
    _richter(monkeypatch, {})
    gesehen = _spion(monkeypatch)

    prueflauf.pruefe_szene(szene6, tg, Schreiber(), einst, 1, 1)

    assert gesehen[0]["fragen"] == ("a10", "c1")
    assert gesehen[0]["szenen"] == (1,)
    assert repo.prueflaeufe(szene6, 1)[0]["fragen"] == "a10,c1"


# --- Die Threads ----------------------------------------------------------


def test_starte_szene_ruft_danach_mit_dem_bericht(szene6, tg, einst, monkeypatch):
    _richter(monkeypatch, {("b1", 1): [2]})
    gesehen = []

    faden = prueflauf.starte_szene(szene6, tg, Schreiber(), einst, 1, 1, gesehen.append)
    faden.join(10)

    assert len(gesehen) == 1 and isinstance(gesehen[0], prueflauf.Bericht)
    assert not szene._sperre_fuer(1).locked()


def test_starte_szene_bei_belegter_sperre_nichts(szene6, tg, einst):
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        assert prueflauf.starte_szene(szene6, tg, Schreiber(), einst, 1, 1,
                                      lambda b: None) is None
    finally:
        sperre.release()


def test_starte_geschichte_nimmt_in_der_prosaphase_die_kurzgeschichtensperre(
        szene6, tg, einst):
    from interview_theater import kurzgeschichte

    sperre = kurzgeschichte._sperre_fuer(1)
    sperre.acquire()
    try:
        assert prueflauf.starte_geschichte(szene6, tg, Schreiber(), einst, 1,
                                           lambda b: None) is None
    finally:
        sperre.release()


def test_ohne_profil_aus(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    assert prueflauf.aktiv() is False

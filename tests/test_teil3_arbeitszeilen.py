"""Teil 3 der Live-Zusaetze vom 06.09.2026 (Birk, 10:45/11:15/12:05-12:10):
Arbeitszeilen, Knopfnachrichten im Gespraechsfenster, Phase-3-Angebot und
Auftrags-Schweigen.
"""

import time

import pytest

from interview_theater import ablauf, arbeitszeilen, knoepfe, phasen, repo

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- Arbeitszeilen (Birk, 11:15/12:08/12:10) ------------------------------


def test_jede_auftragsart_hat_eigene_zeilen():
    for art in ("geschichte", "prosa", "schaerfung", "stueckpruefung",
                "feinschliff", "sensibilitaet", "eroeffnung"):
        assert len(arbeitszeilen.liste(art)) >= 1, art
    assert arbeitszeilen.liste("gibt-es-nicht") == arbeitszeilen.VORGABE


def test_die_zeilen_kommen_aus_der_welt_des_stuecks():
    """Urban Dance Theater, kein Kino (Birk, 12:08): Probeflaeche, Beat,
    Chor, Platz -- kein Vorhang, keine Kamera."""
    alle = [z.lower() for liste in arbeitszeilen.ZEILEN.values() for z in liste]
    alle += [z.lower() for z in arbeitszeilen.VORGABE]
    for zeile in alle:
        for wort in arbeitszeilen.VERBOTEN:
            assert wort not in zeile, f"{wort!r} in {zeile!r}"


class _Tg:
    def __init__(self):
        self.gesendet = []
        self.geaendert = []
        self.geloescht = []
        self.tipps = 0

    def tippt(self, chat_id):
        self.tipps += 1

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def aendere_text(self, chat_id, message_id, text):
        self.geaendert.append(text)

    def loesche_nachrichten(self, chat_id, ids):
        self.geloescht += ids
        return len(ids)


def test_die_erste_zeile_steht_sofort_da():
    """Sofort heisst: aus dem Handler, ohne auf einen Thread zu warten."""
    tg = _Tg()

    lauf = arbeitszeilen.sichtbar(tg, 1, "geschichte")
    try:
        assert len(tg.gesendet) == 1
        assert tg.gesendet[0] in arbeitszeilen.liste("geschichte")
    finally:
        lauf.stoppe()
    assert tg.geloescht


def test_die_zeilen_wiederholen_sich_im_lauf_nicht():
    tg = _Tg()
    alt_takt, alt_tipp = arbeitszeilen.TAKT_S, arbeitszeilen.TIPP_S
    arbeitszeilen.TAKT_S, arbeitszeilen.TIPP_S = 0.1, 0.05
    try:
        lauf = arbeitszeilen.sichtbar(tg, 1, "prosa")
        time.sleep(0.45)
        lauf.stoppe()
    finally:
        arbeitszeilen.TAKT_S, arbeitszeilen.TIPP_S = alt_takt, alt_tipp

    gesehen = tg.gesendet + tg.geaendert
    vier = gesehen[:len(arbeitszeilen.liste("prosa"))]
    assert len(set(vier)) == len(vier), gesehen


# --- Knopfnachrichten im Gespraechsfenster (Birk, 12:05) ------------------


def test_ein_vorschlagsmenue_steht_im_gespraechsfenster(conn, tg):
    """Bis heute fehlten alle Menues im Fenster: nur ``tg.sende`` schrieb
    mit, ``sende_mit_knoepfen`` nicht."""
    phasen.setze(conn, 1, 4, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG RAHMEN:\nEin Treppenhaus\nEin Kiosk\nEin Hof",
    )

    texte = [n["text"] for n in repo.letzte_nachrichten(conn, 1) if n["ist_bot"]]
    assert any("Treppenhaus" in t for t in texte), texte


def test_eine_ja_nein_rueckspiegelung_steht_ebenfalls_im_fenster(conn, tg):
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    texte = [n["text"] for n in repo.letzte_nachrichten(conn, 1) if n["ist_bot"]]
    assert any("Heimat" in t for t in texte), texte


def test_ein_400_auf_answercallbackquery_wirft_nicht(conn, tg, einst):
    """Telegram lehnt alte Knopfdruecke mit 400 ab -- das ist kein Fehler
    des Bots und darf keinen Traceback erzeugen."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    daten = [d for b, d in tg.knoepfe[-1][2] if b == "Ja, speichern"][0]

    def _wirft(*_a, **_k):
        raise RuntimeError("query is too old (400)")

    tg.beantworte_knopf = _wirft

    assert knoepfe.behandle(conn, tg, None, einst, _druck(daten)) is True
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat"


# --- Phase 3: Angebot nach jeder Auswertung, Auftrags-Schweigen -----------


def _interview(conn, mit_verdichtung=True):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, "Wir haben lange geredet, ueber alles.")
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    if mit_verdichtung:
        repo.speichere_verdichtung(conn, 1, kopf_id, "Es ging um Arbeit", [])
    return kopf_id


def test_das_angebot_kommt_nach_jeder_auswertung_erneut(conn, tg):
    """Der Merkposten ``phase_angeboten`` darf es nicht einmalig machen
    (Birk, 10:45)."""
    phasen.setze(conn, 1, 3, "befehl")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war?")
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Hallo")
    erstes = _interview(conn)

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", erstes)
    assert any(b.startswith("Weiter zu") for b, _ in tg.knoepfe[-1][2])

    zweites = _interview(conn)
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 2 ausgewertet.", zweites)

    assert any(b.startswith("Weiter zu") for b, _ in tg.knoepfe[-1][2]), (
        tg.knoepfe[-1][2]
    )


@pytest.mark.parametrize("text", [
    "interview starten",
    "wir wollen jetzt ein interview machen",
    "interview anfangen",
    "los, interview",
    "interview beenden",
])
def test_ein_interview_auftrag_bringt_den_gespraechsbot_zum_schweigen(text):
    assert ablauf.ist_auftrag(text) is True


@pytest.mark.parametrize("text", [
    "was war nochmal im interview 2?",
    "wir haben das interview gut gefunden",
])
def test_eine_frage_ueber_ein_interview_ist_kein_auftrag(text):
    assert ablauf.ist_auftrag(text) is False

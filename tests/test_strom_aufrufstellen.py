"""Strom an den Aufrufstellen, Fix-Runde 1 (Karte W, Aufgabe 7).

Gegen einen echten ``WebKanal`` auf einer Wegwerf-Datenbank:

* Szenenlauf und Gespraechszug ueberlappen -- jeder Strom endet mit seinem
  eigenen Zustand und seiner eigenen ``post_id`` (Befund 1);
* der Nachpass streamt gar nicht, und ein scheiternder Szenenlauf laesst
  keine halbe Blase stehen (Befund 2, 4);
* scheitert der Echo-Nachversuch, traegt die Zeile den gesendeten Text
  (Befund 3);
* scheitert der Versand im Auftragszug, wird der Strom abgebrochen
  (Befund 5).
"""

import threading

import pytest

from interview_theater import ablauf, knoepfe, nachpass, repo, strom, szene, web_kanal
from tests.test_szene import ANTWORT, _bereit_machen


@pytest.fixture(autouse=True)
def ohne_takt(monkeypatch):
    monkeypatch.setattr(strom, "INTERVALL_S", 0.0)
    szene._sperren.clear()
    yield
    szene._sperren.clear()


@pytest.fixture
def web(conn, tmp_path):
    repo.setze_gruppe_kanal(conn, 1, "web")
    return web_kanal.WebKanal(conn, 1, str(tmp_path / "audio"))


def _stroeme(conn):
    return conn.execute(
        "SELECT * FROM web_strom WHERE chat_id = 1 ORDER BY id").fetchall()


def _stueckweise(text, bei_teil):
    if bei_teil is None:
        return
    gesehen = ""
    for zeichen in text:
        gesehen += zeichen
        bei_teil(gesehen)


class Klm:
    """Prosa fuer die Szene, Schema fuer den Gespraechszug."""

    def __init__(self, prosa=ANTWORT, fehler=None, vor_ende=None,
                 antworten=("Hallo zurueck.",)):
        self._prosa = prosa
        self._fehler = fehler
        self._vor_ende = vor_ende
        self._antworten = list(antworten)
        self.schema_aufrufe = 0

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        _stueckweise(self._prosa[: len(self._prosa) // 2], bei_teil)
        if self._vor_ende is not None:
            self._vor_ende()
        if self._fehler is not None:
            raise self._fehler
        _stueckweise(self._prosa, bei_teil)
        return self._prosa

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort"):
        eintrag = self._antworten[min(self.schema_aufrufe, len(self._antworten) - 1)]
        self.schema_aufrufe += 1
        if isinstance(eintrag, Exception):
            _stueckweise("halb kaputt", bei_teil)
            raise eintrag
        _stueckweise(eintrag, bei_teil)
        return {"antwort": eintrag}


def _warte(faden):
    assert faden is not None
    faden.join(timeout=15)
    assert not faden.is_alive()


def _eingang(conn, text):
    message_id = repo.lege_web_post_an(conn, 1, repo.RICHTUNG_EIN,
                                       repo.WEB_TYP_TEXT, text=text)
    repo.merke_nachricht(conn, 1, message_id, web_kanal.ABSENDER, 0, "text",
                         text, repo._jetzt())
    return repo.unbeantwortete(conn, 1)


# --- Befund 1 ---------------------------------------------------------------


def test_zwei_gleichzeitige_stroeme_im_kanal_bestehen_nebeneinander(conn, web):
    """Vorher hielt der Kanal EINE Senke je chat_id: der zweite Strom brach den
    ersten ab, und dessen ``schliesse`` beendete die Zeile des zweiten -- ohne
    post_id. Jetzt endet jeder Strom mit seinem eigenen Zustand."""
    angefangen = threading.Event()
    weiter = threading.Event()
    ids = {}

    def szenenlauf():
        senke = strom.senke(web, 1, "szene")
        senke("MARIA: Da.")
        ids["szene"] = senke.strom_id
        angefangen.set()
        weiter.wait(5)
        senke("MARIA: Da.\nELIF: Ja.")
        strom.schliesse(web, 1, senke=senke)

    faden = threading.Thread(target=szenenlauf)
    faden.start()
    assert angefangen.wait(5)
    gespraech = strom.senke(web, 1, "gespraech")
    gespraech("Hallo ihr")
    ids["gespraech"] = gespraech.strom_id
    weiter.set()
    _warte(faden)
    strom.schliesse(web, 1, 77)

    szene_zeile = repo.hole_strom(conn, ids["szene"])
    gespraech_zeile = repo.hole_strom(conn, ids["gespraech"])
    assert szene_zeile["zustand"] == repo.STROM_FERTIG
    assert szene_zeile["post_id"] is None
    assert szene_zeile["text"] == "MARIA: Da.\nELIF: Ja."
    assert gespraech_zeile["zustand"] == repo.STROM_FERTIG
    assert gespraech_zeile["post_id"] == 77
    assert repo.laufende_stroeme(conn, 1) == []
    assert len(_stroeme(conn)) == 2


def test_verwirf_mit_senke_trifft_nur_diese(conn, web):
    erste = strom.senke(web, 1, "gespraech")
    erste("a")
    erste_id = erste.strom_id
    zweite = {}

    def anderer():
        s = strom.senke(web, 1, "szene")
        s("b")
        zweite["s"] = s
        zweite["id"] = s.strom_id

    faden = threading.Thread(target=anderer)
    faden.start()
    _warte(faden)
    strom.verwirf(web, 1, senke=zweite["s"])
    assert repo.hole_strom(conn, zweite["id"])["zustand"] == repo.STROM_ABGEBROCHEN
    assert repo.hole_strom(conn, erste_id)["zustand"] == repo.STROM_LAEUFT
    strom.schliesse(web, 1, 3)
    assert repo.hole_strom(conn, erste_id)["post_id"] == 3


def test_auftragszug_waehrend_des_szenenlaufs(conn, einst, web):
    _bereit_machen(conn)
    mitten = threading.Event()
    weiter = threading.Event()

    def halt():
        mitten.set()
        weiter.wait(10)

    klm = Klm(vor_ende=halt)
    faden = szene.starte(conn, web, klm, einst, 1, "Szene 1: Ankunft")
    assert mitten.wait(10)

    # ``antworte`` faellt waehrend eines Szenenlaufs aus (``szene.laeuft``),
    # ein Knopf-Auftrag nicht -- er ist der Gespraechszug, der im Betrieb
    # neben dem Szenenstrom laeuft (wie jeder Zug neben einem Prosalauf).
    ablauf.auftragszug(conn, web, klm, einst, 1, "Sag kurz Hallo.")
    weiter.set()
    _warte(faden)

    zeilen = _stroeme(conn)
    nach_art = {z["art"]: z for z in zeilen}
    assert len(zeilen) == 2, [dict(z) for z in zeilen]
    assert nach_art["szene"]["zustand"] == repo.STROM_FERTIG
    assert nach_art["szene"]["post_id"] is None
    assert nach_art["gespraech"]["zustand"] == repo.STROM_FERTIG
    post = repo.hole_web_post(conn, nach_art["gespraech"]["post_id"])
    assert post["text"] == "Hallo zurueck."
    assert repo.laufende_stroeme(conn, 1) == []


# --- Befund 2 und 4 ---------------------------------------------------------


def test_der_nachpass_streamt_nicht(conn, einst, web):
    """``schreibe`` ohne ``bei_teil`` -- so ruft es ``nachpass.nach_szene`` --
    legt keine Stromzeile an: die Gruppe erfaehrt vom Nachpass nichts."""
    _bereit_machen(conn)
    szene.schreibe(conn, web, Klm(), einst, 1, "Szene 1: Ankunft",
                   art=nachpass.ART_SZENE)
    assert _stroeme(conn) == []


def test_der_szenenlauf_selbst_streamt(conn, einst, web):
    _bereit_machen(conn)
    _warte(szene.starte(conn, web, Klm(), einst, 1, "Szene 1: Ankunft"))
    zeilen = _stroeme(conn)
    assert [z["zustand"] for z in zeilen] == [repo.STROM_FERTIG]
    assert zeilen[0]["art"] == "szene"


def test_ein_szenenlauf_der_mitten_im_strom_scheitert_bricht_ab(conn, einst, web):
    _bereit_machen(conn)
    _warte(szene.starte(conn, web, Klm(fehler=RuntimeError("weg")), einst, 1,
                        "Szene 1: Ankunft"))
    zeilen = _stroeme(conn)
    assert [z["zustand"] for z in zeilen] == [repo.STROM_ABGEBROCHEN]
    assert zeilen[0]["post_id"] is None
    assert repo.hole_szenen(conn, 1)[0]["volltext"] is None


def test_eine_antwort_ohne_szenentext_bricht_den_strom_ab(conn, einst, web):
    """Befund 4: ``SzeneFehler`` ist kein 'fertig'."""
    _bereit_machen(conn)
    _warte(szene.starte(conn, web, Klm(prosa="TITEL: Am Bahnhof\nKURZ: Eine Zeile\n"),
                        einst, 1, "Szene 1: Ankunft"))
    zeilen = _stroeme(conn)
    assert [z["zustand"] for z in zeilen] == [repo.STROM_ABGEBROCHEN]


# --- Befund 3 ---------------------------------------------------------------


def test_scheitert_der_echo_nachversuch_traegt_die_zeile_den_gesendeten_text(
        conn, einst, web, monkeypatch):
    rufe = {"n": 0}

    def echo(antwort, offen):
        rufe["n"] += 1
        return rufe["n"] == 1

    monkeypatch.setattr(ablauf, "ist_echo", echo)
    offen = _eingang(conn, "Womit fangen wir an?")
    klm = Klm(antworten=["Womit fangen wir an?", RuntimeError("weg")])
    ablauf.antworte(conn, web, klm, einst, 1, offen)

    fertig = [z for z in _stroeme(conn) if z["zustand"] == repo.STROM_FERTIG]
    assert len(fertig) == 1
    post = repo.hole_web_post(conn, fertig[0]["post_id"])
    assert post["text"] == "Womit fangen wir an?"
    assert fertig[0]["text"] == post["text"]
    assert repo.laufende_stroeme(conn, 1) == []


# --- Befund 5 ---------------------------------------------------------------


def test_scheitert_der_versand_im_auftragszug_wird_der_strom_abgebrochen(
        conn, einst, web, monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("Versand weg")

    monkeypatch.setattr(knoepfe, "sende_mit_speicherleiste", kaputt)
    monkeypatch.setattr(web, "sende", kaputt)
    with pytest.raises(RuntimeError):
        ablauf.auftragszug(conn, web, Klm(antworten=["Ein Vorschlag."]), einst, 1,
                           "Schlag etwas vor.")
    zeilen = _stroeme(conn)
    assert [z["zustand"] for z in zeilen] == [repo.STROM_ABGEBROCHEN]


# --- R2-1: eine spaet verworfene Schaerfung schickt nichts an die Gruppe ---


def test_spaet_verworfene_schaerfung_im_auftragszug_schickt_nichts(
        conn, einst, web):
    """Live-Beschwerde "I don't know this selection any more": eine Frage
    1 ist laengst entschieden, als die Antwort der Schaerfung ankommt.
    ``fragen.uebernimm_schaerfung`` verwirft sie jetzt stumm (liefert
    ``None``) -- vorher schickte sie trotzdem die Fehlzeile
    ``T._TEXT_FRAGEN_KEINE_AUSWAHL``, weil ``auftragszug`` eine echte
    ``message_id`` brauchte. Kein ``web_post``, kein ``nachricht``-Eintrag,
    der Strom endet ohne ``post_id`` -- fuer den Browser (``web_vereint.
    scope_css``) wie ein abgebrochener Strom: ersatzlos weg."""
    vorher_posts = conn.execute(
        "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = 1").fetchone()["n"]
    vorher_nachrichten = conn.execute(
        "SELECT COUNT(*) AS n FROM nachricht WHERE chat_id = 1").fetchone()["n"]

    klm = Klm(antworten=["VORSCHLAG FRAGE:\nHeimat: Wann warst du zuletzt fremd?"])
    ablauf.auftragszug(conn, web, klm, einst, 1, "Mach die Frage persoenlicher.")

    zeilen = _stroeme(conn)
    assert [z["zustand"] for z in zeilen] == [repo.STROM_FERTIG]
    assert zeilen[0]["post_id"] is None
    nachher_posts = conn.execute(
        "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = 1").fetchone()["n"]
    nachher_nachrichten = conn.execute(
        "SELECT COUNT(*) AS n FROM nachricht WHERE chat_id = 1").fetchone()["n"]
    assert nachher_posts == vorher_posts, "kein neuer Post an die Gruppe"
    assert nachher_nachrichten == vorher_nachrichten, "nichts mitgeschrieben"

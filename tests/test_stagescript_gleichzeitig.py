"""Abschlussreview t_fd88600b I1: eine Aenderung, die WAEHREND des
Schreibens einer Szene passiert, geht nicht still verloren -- der
Veraltet-Vermerk ueberlebt das Speichern, und der Nachzug aus dem (alten)
Text ueberschreibt den neuen Ort nicht."""

from interview_theater import karten_nachzug, repo, stagescript, stueck, workshop

from test_szenenkarte import TG, _lage, padua  # noqa: F401
from test_stagescript import _karten
from tests.stueck_hilfe import lege_karte_an


class LLMMitAenderung:
    """Der Schreibaufruf aendert mittendrin den Ort der Szene (wie der Erkenner
    ``szene_planen`` oder die Gruppenseite es koennten)."""

    def __init__(self, conn, nummer, ort):
        self.conn, self.nummer, self.ort = conn, nummer, ort

    def schema(self, chat_id, system, nutzer, schema, art):
        if art == stagescript.ART:
            stueck.setze_ort(self.conn, chat_id, szene=self.nummer, ort=self.ort,
                             quelle=stueck.QUELLE_PLANUNG)
            return {"text": "EMMA: Home.", "kopf": ""}
        return {}


def test_vermerk_aus_dem_schreibfenster_ueberlebt_das_speichern(conn, padua):
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[1], "ALTER TEXT", None)
    assert stagescript.schreibe(conn, LLMMitAenderung(conn, 2, "Station"), None, 1, 2) is True
    offen = [v for v in repo.offene_veraltet(conn, 1)
             if v["szene_id"] == ids[1] and v["ansicht"] == "script"]
    assert len(offen) == 1
    assert repo.hole_szene(conn, ids[1])["ort"] == "Station"


def test_vermerk_vor_dem_schreibstart_wird_erledigt(conn, padua):
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[1], "ALTER TEXT", None)
    stueck.setze_ort(conn, 1, szene=2, ort="Station")
    assert [v for v in repo.offene_veraltet(conn, 1) if v["szene_id"] == ids[1]]

    class Still:
        def schema(self, chat_id, system, nutzer, schema, art):
            return {"text": "EMMA: Home.", "kopf": ""} if art == stagescript.ART else {}

    assert stagescript.schreibe(conn, Still(), None, 1, 2) is True
    assert [v for v in repo.offene_veraltet(conn, 1) if v["szene_id"] == ids[1]] == []


def test_weiterer_grund_in_offenem_vermerk_zaehlt_als_neu(conn, padua):
    """Ein Vermerk, der schon offen war, bekommt waehrend des Schreibens einen
    weiteren Grund: er darf nicht mit dem Speichern verschwinden."""
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[1], "ALTER TEXT", None)
    stueck.setze_ort(conn, 1, szene=2, ort="Station")
    assert stagescript.schreibe(conn, LLMMitAenderung(conn, 2, "Bahnhof"), None, 1, 2) is True
    assert [v for v in repo.offene_veraltet(conn, 1)
            if v["szene_id"] == ids[1] and v["ansicht"] == "script"]


class LLMNachzug:
    def __init__(self, ort):
        self.ort = ort

    def schema(self, chat_id, system, nutzer, schema, art):
        return {"ort": self.ort, "wer": "", "modus": "none"}


def test_nachzug_ueberschreibt_keinen_ort_der_waehrend_des_schreibens_kam(conn, einst):
    sid = lege_karte_an(conn, ort="Bar", bestaetigt=True)
    repo.setze_stagescript(conn, sid, "TEXT", None)
    start = repo.hoechste_stueck_aenderung_id(conn, 1)
    stueck.setze_ort(conn, 1, szene=1, ort="Station", quelle=stueck.QUELLE_PLANUNG)
    karten_nachzug.ziehe_nach(conn, LLMNachzug("Bar"), einst, 1, sid, "TEXT",
                              ueber_claude=False, seit_aenderung=start)
    assert repo.hole_szene(conn, sid)["ort"] == "Station"


def test_nachzug_ohne_aenderung_im_fenster_zieht_nach(conn, einst):
    sid = lege_karte_an(conn, ort="Bar", bestaetigt=True)
    repo.setze_stagescript(conn, sid, "TEXT", None)
    start = repo.hoechste_stueck_aenderung_id(conn, 1)
    karten_nachzug.ziehe_nach(conn, LLMNachzug("Piazza"), einst, 1, sid, "TEXT",
                              ueber_claude=False, seit_aenderung=start)
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza"

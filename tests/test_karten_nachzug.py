"""Phase 7: Ort/Figuren aus dem neu geschriebenen Stage Script auf die
Szenenkarte nachziehen (Padua, Birk 08.10.2026 ~12:50, Profilschalter
``[karten] p7_meta_nachziehen``). Deterministischer Vergleich -- der
Modellaufruf selbst ist ein Testdouble."""

import json

import pytest

from interview_theater import karten_nachzug, repo, szenenkarte


class LLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "system": system, "nutzer": nutzer})
        return self.antwort


def _karte(conn, chat_id=1, **felder):
    sid = repo.stelle_szene_sicher(conn, chat_id, 1)
    karte = {"typ": "spoken", "modus": "none", "worum": "x", "ort": "Bar",
             "wer": "Anna", "punkte": ["p"], "zitate": [], "fragen": []}
    karte.update(felder)
    repo.setze_szenenkarte(conn, sid, json.dumps(karte))
    repo.setze_szenenkarte_bestaetigt(conn, sid)
    return sid


def test_neuer_ort_aktualisiert_karte_und_haengt_verlauf_an(conn, einst):
    sid = _karte(conn)
    klm = LLM({"ort": "Piazza", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "EMMA: ... in piazza ...",
                              ueber_claude=False)

    karte = szenenkarte.karte_von(repo.hole_szene(conn, sid))
    assert karte["ort"] == "Piazza"
    verlauf = repo.karte_verlauf(conn, 1, sid)
    assert verlauf[-1]["ausloeser"] == szenenkarte.AUSLOESER_AENDERUNG
    assert json.loads(verlauf[-1]["karte_json"])["ort"] == "Piazza"


def test_neuer_ort_laesst_abnahme_stehen(conn, einst):
    """Anders als ``repo.setze_szenenkarte``: die Phase-6-Abnahme der Karte
    bleibt stehen -- Phase 7 zieht nur nach, nimmt nicht neu ab."""
    sid = _karte(conn)
    klm = LLM({"ort": "Piazza", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert repo.hole_szene(conn, sid)["karte_bestaetigt_am"]


def test_neue_figur_aktualisiert_wer(conn, einst):
    sid = _karte(conn)
    klm = LLM({"ort": "Bar", "wer": "Anna, an audience member", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    karte = szenenkarte.karte_von(repo.hole_szene(conn, sid))
    assert karte["wer"] == "Anna, an audience member"


def test_gleicher_ort_schreibt_nichts(conn, einst):
    sid = _karte(conn)
    klm = LLM({"ort": "Bar", "wer": "Anna", "modus": "none"})
    vorher = len(repo.karte_verlauf(conn, 1, sid))

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert len(repo.karte_verlauf(conn, 1, sid)) == vorher
    assert szenenkarte.karte_von(repo.hole_szene(conn, sid))["ort"] == "Bar"


def test_vergleich_ist_normalisiert_gross_klein_leerzeichen(conn, einst):
    """Mutationsprobe: ein bloss andersgroesser/-geleerzeichter Ort ist
    KEINE Aenderung -- ohne Normalisierung waere das ein falscher Treffer."""
    sid = _karte(conn)
    klm = LLM({"ort": "  bar  ", "wer": "anna", "modus": "none"})
    vorher = len(repo.karte_verlauf(conn, 1, sid))

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert len(repo.karte_verlauf(conn, 1, sid)) == vorher


def test_modus_aendert_sich_nur_bei_typ_moment(conn, einst):
    sid = _karte(conn, typ="spoken", modus="none")
    klm = LLM({"ort": "Bar", "wer": "Anna", "modus": "collective"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    karte = szenenkarte.karte_von(repo.hole_szene(conn, sid))
    assert karte["modus"] == "none"


def test_modus_aendert_sich_bei_typ_moment(conn, einst):
    sid = _karte(conn, typ="moment", modus="microphone")
    klm = LLM({"ort": "Bar", "wer": "Anna", "modus": "collective"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    karte = szenenkarte.karte_von(repo.hole_szene(conn, sid))
    assert karte["modus"] == "collective"


def test_fehlerhafter_modellaufruf_laesst_karte_unveraendert(conn, einst):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("boom")

    sid = _karte(conn)
    karten_nachzug.ziehe_nach(conn, Kaputt(), einst, 1, sid, "text", ueber_claude=False)

    karte = szenenkarte.karte_von(repo.hole_szene(conn, sid))
    assert karte["ort"] == "Bar"


def test_ohne_karte_tut_nichts(conn, einst):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    klm = LLM({"ort": "Piazza", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert klm.aufrufe == []

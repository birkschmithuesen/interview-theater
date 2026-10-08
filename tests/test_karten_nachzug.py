"""Phase 7: Ort/Figuren aus dem neu geschriebenen Stage Script auf die
Szenenkarte UND die Werkbank (``szene.ort``/``szene_figur``) nachziehen
(Padua, Birk 08.10.2026 ~12:50 + Nachtrag ~13:00, Profilschalter
``[karten] p7_meta_nachziehen``). Deterministischer Vergleich -- der
Modellaufruf selbst ist ein Testdouble."""

import json

import pytest

from interview_theater import karten_nachzug, repo, szenenkarte, web


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


def test_neuer_ort_zieht_auch_die_werkbank_nach(conn, einst):
    """Live-Befund G1 S1 (Nachtrag Birk 08.10.2026 ~13:00): die Werkbank
    (web._szene_html) liest ``szene.ort``, nicht die Karte -- ohne Nachzug
    blieb sie bei der alten Planung stehen, waehrend die Karte schon den
    neuen Ort trug."""
    sid = _karte(conn)
    repo.setze_szenenfeld(conn, sid, "ort", "Bar")
    klm = LLM({"ort": "Piazza", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert repo.hole_szene(conn, sid)["ort"] == "Piazza"


def test_neue_figur_zieht_nur_vorhandene_in_die_werkbank(conn, einst):
    """Eine neue Figur ("an audience member") bekommt KEINE eigene
    ``figur``-Zeile -- nur das Kartenfeld ``wer``; die Werkbank-Besetzung
    uebernimmt nur Namen, die schon eine Figur haben."""
    repo.setze_figur(conn, 1, "Anna", "")
    vorher = len(repo.figuren(conn, 1))
    sid = _karte(conn)
    klm = LLM({"ort": "Bar", "wer": "Anna, an audience member", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert len(repo.figuren(conn, 1)) == vorher
    namen = {f["name"] for f in repo.szene_figuren(conn, sid)}
    assert namen == {"Anna"}


def test_werkbank_html_zeigt_den_neuen_ort(conn, einst):
    """Die Werkbank (``web._szene_html``, read-only wie in Padua) liest
    ``szene.ort`` -- nach dem Nachzug steht dort der neue Ort, nicht mehr
    die alte Planung."""
    sid = _karte(conn)
    repo.setze_szenenfeld(conn, sid, "ort", "Bar")
    klm = LLM({"ort": "Piazza", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    szene = repo.hole_szene(conn, sid)
    s = {"nummer": szene["nummer"], "id": szene["id"], "ort": szene["ort"],
         "figuren": [f["name"] for f in repo.szene_figuren(conn, sid)]}
    html = web._szene_html(s)
    assert "Piazza" in html
    assert "Bar" not in html


def test_ohne_aenderung_bleibt_die_werkbank_unberuehrt(conn, einst):
    repo.setze_figur(conn, 1, "Anna", "")
    [anna] = repo.figuren(conn, 1)
    sid = _karte(conn)
    repo.setze_szenenfeld(conn, sid, "ort", "Bar")
    repo.setze_szene_figuren(conn, 1, sid, [anna["id"]])
    klm = LLM({"ort": "Bar", "wer": "Anna", "modus": "none"})

    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "text", ueber_claude=False)

    assert repo.hole_szene(conn, sid)["ort"] == "Bar"
    assert [f["name"] for f in repo.szene_figuren(conn, sid)] == ["Anna"]


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

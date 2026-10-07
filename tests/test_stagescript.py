"""Phase 7 = Stage Script aus den Szenenkarten (Padua-Phasenumbau, Birk
07.10.2026 ~18:12, ``[karten] aktiv``): Szene fuer Szene aus der Karte, das
Format nach dem Kartentyp, einmal ein Kopf bei Handlungsanweisungen, EN/IT-
Spiegel, Abnahme ueber die vorhandenen Wege."""

import json

import pytest

from interview_theater import phasen, repo, stagescript, ueberarbeitung, workshop

from test_szenenkarte import TG, _lage, padua  # noqa: F401


class LLM:
    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == stagescript.ART:
            return {"text": "**Theme**\nEMMA: Casa.", "kopf": "Setup: a bar table."}
        if art == "skript_spiegel":
            return {"prosa_en": "**Theme**\nEMMA: Home.", "prosa_it": "**Tema**\nEMMA: Casa."}
        return {}


def _karten(conn, typ="instructions"):
    ids = _lage(conn)
    for n, sid in enumerate(ids, start=1):
        repo.setze_szenenkarte(conn, sid, json.dumps({
            "typ": typ, "worum": f"Worum {n}", "ort": "Bar", "wer": "Anna",
            "punkte": [f"Punkt {n}"], "zitate": [], "fragen": []}))
        repo.setze_szenenkarte_bestaetigt(conn, sid)
    phasen.setze(conn, 1, 7, "befehl")
    return ids


def _warte():
    stagescript._sperre_fuer(1).acquire(timeout=5)
    stagescript._sperre_fuer(1).release()


def test_ohne_schalter_bleibt_phase_7_die_formwahl(conn, einst, monkeypatch):
    ids = _karten(conn)
    tg = TG()
    monkeypatch.setattr(ueberarbeitung, "aktiv", lambda: True)
    ueberarbeitung.weiter_7(conn, tg, LLM(), einst, 1)
    assert stagescript.T._TEXT_SCHREIBE.format(nummer=1) not in tg.texte
    assert repo.hole_szene(conn, ids[0])["volltext"] is None


def test_phase_7_szene_fuer_szene_aus_der_karte(conn, einst, padua):
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    zeile = repo.hole_szene(conn, ids[0])
    assert zeile["volltext"] == "**Theme**\nEMMA: Home."
    assert zeile["volltext_it"] == "**Tema**\nEMMA: Casa."
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["stage_kopf"] == "Setup: a bar table."
    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Worum 1" in nutzer and "CAMERA" in nutzer and "\"kopf\"" in nutzer
    assert any("Script tab" in t for t in tg.texte)

    # "No, change" -> neu mit Notiz und bisherigem Text, ohne zweiten Kopf.
    ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "Anna speaks Italian", nummer=1).join(5)
    nutzer = [a for a in klm.aufrufe if a["art"] == stagescript.ART][-1]["nutzer"]
    assert "Anna speaks Italian" in nutzer and "EMMA: Home." in nutzer
    assert "\"kopf\"" not in nutzer

    # "Yes, save" -> fertig_am, naechste Szene.
    ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 1)
    _warte()
    assert repo.hole_szene(conn, ids[0])["fertig_am"]
    assert repo.hole_szene(conn, ids[1])["volltext"]
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2
    assert ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 1) == \
        stagescript.T._TEXT_NICHT_DRAN
    ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 2)
    assert tg.texte[-1] == stagescript.T._TEXT_ALLES_FERTIG


def test_format_nach_kartentyp(conn, padua):
    ids = _karten(conn, typ="moment")
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "microphone" in text and "CAMERA" not in text
    assert stagescript.braucht_kopf(conn, 1) is False


def test_kopf_nur_bei_ueberwiegend_anweisungen(conn, padua):
    ids = _karten(conn, typ="instructions")
    assert stagescript.braucht_kopf(conn, 1) is True
    repo.setze_szenenkarte(conn, ids[0], json.dumps({"typ": "description", "worum": "x",
                                                     "punkte": ["y"]}))
    assert stagescript.braucht_kopf(conn, 1) is False


def test_anschluss_an_das_ende_der_vorigen_szene(conn, padua):
    """Nachtrag Birk 08.10.2026 (Vollskript G3): Szene 5 endete mit der
    projizierten Schlussfrage, Szene 6 liess sie noch einmal erscheinen. Der
    Prompt einer Szene bekommt deshalb das geschriebene Ende der vorigen.
    Mutant: Block weg -> rot; ganzer Text statt Ende -> rot."""
    ids = _karten(conn)
    anfang = "ANFANG-DER-SZENE-1 " + "x " * 800
    repo.setze_stagescript(conn, ids[0], anfang + "ENDE: die Frage erscheint auf der Wand.", None)
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[1]))
    assert stagescript.T._KOPF_VORHER in text
    assert "ENDE: die Frage erscheint auf der Wand." in text
    assert "ANFANG-DER-SZENE-1" not in text
    erste = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert stagescript.T._KOPF_VORHER not in erste

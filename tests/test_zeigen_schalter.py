"""Padua Phasen TEIL 2: ein Lauf kann schreiben, ohne zu zeigen -- der
Prueflauf zeigt erst die gepruefte Fassung."""

from test_knoepfe import TelegramAttrappe

from interview_theater import kurzgeschichte, phasen, repo, szene


class ProsaKLM:
    def __init__(self, text):
        self.text = text
        self.aufrufe = 0

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None, bei_teil=None):
        self.aufrufe += 1
        return self.text


def _vorbereiten(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Flur.")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei Freunde.")
    repo.setze_figur(conn, 1, "Alex", "leise")
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, sid, "was_passiert", "Alex packt.")
    repo.setze_szenenfeld(conn, sid, "ort", "Flur")
    repo.setze_szene_figuren(conn, 1, sid, [f["id"] for f in repo.figuren(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    return sid


def test_schreibe_ohne_zeigen_speichert_aber_sendet_nichts(conn, einst):
    sid = _vorbereiten(conn)
    tg = TelegramAttrappe()
    szene.schreibe(conn, tg, ProsaKLM("TITEL: Eins\n\nPROSA-KOERPER-XYZ"), einst, 1,
                   "SZENE 1: schreib", zeigen=False)
    assert "PROSA-KOERPER-XYZ" in (repo.hole_szene(conn, sid)["prosa"] or "")
    assert not any("PROSA-KOERPER-XYZ" in t for _c, t, *_ in tg.gesendet)
    assert not tg.knoepfe


def test_ueberarbeitungsauftrag_haengt_im_prosalauf_bisher_an(conn):
    _vorbereiten(conn)  # Phase 6 -> Prosa
    auftrag = szene.ueberarbeitungsauftrag(conn, 1, 1, "wuetender")
    assert szene.BISHER_MARKER in auftrag and "wuetender" in auftrag
    phasen.setze(conn, 1, 7, "befehl")
    assert szene.BISHER_MARKER not in szene.ueberarbeitungsauftrag(conn, 1, 1, "x")


def _kurzgeschichte_vorbereiten(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ort: Treppenhaus, Zeit: nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Sie geht, er bleibt.")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")


def test_kurzgeschichte_schreibe_ohne_zeigen_speichert_aber_sendet_nichts(conn, einst):
    _kurzgeschichte_vorbereiten(conn)
    tg = TelegramAttrappe()
    antwort = (
        "1. Abschnitt Eins\n"
        "Zusammenfassung: Im ersten Abschnitt passiert etwas Bestimmtes.\n\n"
        "PROSA-ABSCHNITT-XYZ"
    )
    nummern = kurzgeschichte.schreibe(conn, tg, ProsaKLM(antwort), einst, 1, zeigen=False)
    assert nummern
    szenen = repo.hole_szenen(conn, 1)
    assert any("PROSA-ABSCHNITT-XYZ" in (s["prosa"] or "") for s in szenen)
    assert not any("PROSA-ABSCHNITT-XYZ" in t for _c, t, *_ in tg.gesendet)
    assert not tg.knoepfe

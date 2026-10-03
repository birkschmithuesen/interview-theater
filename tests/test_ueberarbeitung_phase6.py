"""Phase 6 (Rewrite) in Padua (Padua Phasen TEIL 2, Task 8).

Zuerst das Ganze, dann Szene fuer Szene: beim Eintritt wird die schon
vorhandene Prosa aus Phase 5 GEPRUEFT (nicht neu geschrieben), "Yes, save"
fixiert den Gesamttext, danach je Szene ein Prueflauf mit Hinweis, und nach
der letzten abgenommenen Szene genau eine Abschlussnachricht und der
automatische Sprung nach Phase 7.

Richter ohne Befunde (``Rundenrichter({})``) -- keine Auftraege, also keine
Ueberarbeitung und kein Modellaufruf des Schreibers.
"""

import re
import time

import pytest

import test_dramaturgie_schleife as schleifentest
from interview_theater import (
    knoepfe, kurzgeschichte, phasen, repo, szene, ueberarbeitung, workshop,
)
from interview_theater.dramaturgie import fanout
from test_dramaturgie_schleife import Rundenrichter
from test_knoepfe import TelegramAttrappe, _druck


class Schreiber:
    """Szenen- und Geschichtenlauf ohne Netz; merkt jeden Prosa-Aufruf."""

    def __init__(self):
        self.prosa_aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.prosa_aufrufe.append((art, nutzer))
        if art == kurzgeschichte.ART:
            return "".join(
                f"## {n}. Teil {n}\nZusammenfassung: Teil {n}.\n\n"
                f"Mira geht weiter, Abschnitt {n}.\n\n"
                for n in (1, 2, 3)
            )
        return (
            "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
            "ZUSAMMENFASSUNG: Mira und Jonas treffen sich am Steg.\n"
            "ANDERS GEMACHT: nichts\n\n"
            "Mira steht am Steg. Jonas schaut auf das Wasser.\n"
        )

    def schema(self, *a, **k):
        raise AssertionError("kein Schema-Aufruf erwartet")


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    monkeypatch.setattr(schleifentest, "_SZENE_IM_KOPF", re.compile(
        r"(?:Das ist Szene|Repliken von Szene|This is scene) (\d+)"))
    richter = Rundenrichter({})
    monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)
    # Phase 7 startet beim Eintritt die Stueckpruefung -- nicht Gegenstand
    # dieser Datei.
    monkeypatch.setattr(knoepfe.stationen, "starte_stueckpruefung",
                        lambda *a, **k: None)
    yield
    workshop.vergiss()


@pytest.fixture
def ohne_profil(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def _stueck(conn, szenen=(1, 2, 3)):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jonas", "schweigt lieber")
    ids = [repo.hole_figur(conn, 1, n)["id"] for n in ("Mira", "Jonas")]
    for nummer in szenen:
        sid = repo.stelle_szene_sicher(conn, 1, nummer)
        for feld, wert in (("ort", "Steg"), ("was_passiert", "Sie treffen sich.")):
            repo.setze_szenenfeld(conn, sid, feld, wert)
        repo.setze_szene_figuren(conn, 1, sid, ids)
        repo.aktualisiere_szene(
            conn, sid, f"Teil {nummer}", None, None, f"Teil {nummer}.",
            prosa=f"Mira steht am Steg, Teil {nummer}. Jonas schaut aufs Wasser.",
        )
        repo.setze_szene_entwurf_bestaetigt(conn, sid)
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 6, "test")
    return conn


def _warte_auf(bedingung, timeout=20.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.02)
    raise AssertionError("Bedingung nicht rechtzeitig erfuellt")


def _laeufe(conn):
    return repo.prueflaeufe(conn, 1)


def _letzte_leiste_hat(tg, art, conn):
    if not tg.knoepfe:
        return False
    arten = [repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"]
             for _b, d in tg.knoepfe[-1][2]]
    return art in arten


def _daten_fuer(tg, conn, art):
    for _b, d in tg.knoepfe[-1][2]:
        if repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"] == art:
            return d
    raise AssertionError(f"kein Knopf {art} in der letzten Leiste")


def _eintritt(conn, tg, klm, einst):
    knoepfe.eintritt_in_phase(conn, tg, klm, einst, 1, 6)
    _warte_auf(lambda: len(_laeufe(conn)) == 1
               and _letzte_leiste_hat(tg, knoepfe.ART_GESCHICHTE_PASST, conn))


def _alles(tg):
    return "\n".join(t for _, t in tg.gesendet)


def test_eintritt_prueft_die_vorhandene_geschichte(conn, padua, tg, einst):
    _stueck(conn)
    klm = Schreiber()

    _eintritt(conn, tg, klm, einst)

    (zeile,) = _laeufe(conn)
    assert zeile["ziel"] == "geschichte"
    assert "Yes, save" in [b for b, _d in tg.knoepfe[-1][2]]
    assert klm.prosa_aufrufe == [], "die Geschichte wird nicht neu geschrieben"
    assert "First you read the whole story in the Script tab" in _alles(tg)
    assert "Before I suggest anything" not in _alles(tg)


def test_gesamt_ja_fixiert_und_startet_szene_1(conn, padua, tg, einst):
    _stueck(conn)
    klm = Schreiber()
    _eintritt(conn, tg, klm, einst)

    assert knoepfe.behandle(conn, tg, klm, einst, _druck(
        _daten_fuer(tg, conn, knoepfe.ART_GESCHICHTE_PASST))) is True

    assert (repo.hole_arbeitsstand(conn, 1)["gesamttext_fixiert_am"] or "").strip()
    assert "scene 1 of 3" in _alles(tg)
    _warte_auf(lambda: len(_laeufe(conn)) == 2
               and _letzte_leiste_hat(tg, knoepfe.ART_SZENE_PASST, conn))
    neu = _laeufe(conn)[-1] if _laeufe(conn)[-1]["ziel"] == "szene" else _laeufe(conn)[0]
    assert neu["ziel"] == "szene"
    assert neu["szene_nummer"] == 1
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1


def test_ueberarbeite_vor_dem_fixieren_laeuft_ueber_die_ganze_geschichte(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn)
    klm = Schreiber()
    _eintritt(conn, tg, klm, einst)
    aufrufe = []
    echt = kurzgeschichte.starte

    def spion(*a, **k):
        aufrufe.append((a, k))
        return echt(*a, **k)

    monkeypatch.setattr(kurzgeschichte, "starte", spion)
    vorher = len(tg.knoepfe)

    faden = ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "make it sadder")

    assert faden is not None
    faden.join(20)
    assert len(aufrufe) == 1
    assert aufrufe[0][1].get("vorlage") is True
    assert "make it sadder" in aufrufe[0][0]
    assert len(klm.prosa_aufrufe) >= 1
    _warte_auf(lambda: len(tg.knoepfe) > vorher
               and _letzte_leiste_hat(tg, knoepfe.ART_GESCHICHTE_PASST, conn))


def test_ueberarbeite_nach_dem_fixieren_trifft_die_aktuelle_szene(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn)
    repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", repo._jetzt())
    klm = Schreiber()
    auftraege = []
    monkeypatch.setattr(szene, "starte",
                        lambda c, t, k, e, cid, auftrag, *a, **kw:
                        auftraege.append(auftrag) or "faden")

    assert ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "angrier") == "faden"

    (auftrag,) = auftraege
    assert szene.BISHER_MARKER in auftrag
    assert "angrier" in auftrag
    assert re.search(r"\b1\b", auftrag)


def test_drei_mal_ja_springt_nach_phase_7(conn, padua, tg, einst):
    _stueck(conn)
    klm = Schreiber()
    _eintritt(conn, tg, klm, einst)
    knoepfe.behandle(conn, tg, klm, einst, _druck(
        _daten_fuer(tg, conn, knoepfe.ART_GESCHICHTE_PASST), query_id="g"))

    for nummer in (1, 2, 3):
        _warte_auf(lambda n=nummer: any(
            z["ziel"] == "szene" and z["szene_nummer"] == n for z in _laeufe(conn))
            and _letzte_leiste_hat(tg, knoepfe.ART_SZENE_PASST, conn)
            and repo.hole_knopf(conn, knoepfe._id_aus_daten(
                _daten_fuer(tg, conn, knoepfe.ART_SZENE_PASST)))["wert"] == str(n))
        knoepfe.behandle(conn, tg, klm, einst, _druck(
            _daten_fuer(tg, conn, knoepfe.ART_SZENE_PASST), query_id=f"s{nummer}"))

    fertig = ueberarbeitung.T._TEXT_6_FERTIG.format(gesamt=3)
    assert [t for _, t in tg.gesendet].count(fertig) == 1
    assert phasen.aktuelle(conn, 1) == 7
    for s in repo.hole_szenen(conn, 1):
        assert (s["ueberarbeitung_bestaetigt_am"] or "").strip()
    assert ueberarbeitung.aktuelle_szene(conn, 1) is None


def test_ohne_prosa_bleibt_der_knopf_geschichte_schreiben(conn, padua, tg, einst):
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 6, "test")

    knoepfe.eintritt_in_phase(conn, tg, Schreiber(), einst, 1, 6)

    assert _letzte_leiste_hat(tg, knoepfe.ART_GESCHICHTE_SCHREIBEN, conn)
    assert _laeufe(conn) == []


def test_aktuelle_szene_phase_7(conn, padua):
    _stueck(conn)
    phasen.setze(conn, 1, 7, "test")
    assert ueberarbeitung.aktuelle_szene(conn, 1) is None
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    assert ueberarbeitung.aktuelle_szene(conn, 1) is None  # Formen fehlen
    for s in repo.hole_szenen(conn, 1):
        repo.setze_szenenfeld(conn, s["id"], "form", "dialog")
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1
    repo.setze_szene_fertig(conn, repo.hole_szenen(conn, 1)[0]["id"], True)
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2


def test_regienotiz_nach_anders_geht_in_padua_ueber_ueberarbeite(
        conn, padua, tg, einst, monkeypatch):
    from interview_theater import ablauf, szenenfolge

    _stueck(conn)
    repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", repo._jetzt())
    gerufen = []
    monkeypatch.setattr(ueberarbeitung, "ueberarbeite",
                        lambda c, t, k, e, cid, notiz, nummer=None:
                        gerufen.append((notiz, nummer)))
    monkeypatch.setattr(szene, "starte", lambda *a, **k: pytest.fail("direkt"))
    monkeypatch.setattr(kurzgeschichte, "starte",
                        lambda *a, **k: pytest.fail("direkt"))
    szenenfolge.erwarte_regienotiz(1, 2)

    assert ablauf._szene_hat_vorfahrt(
        conn, tg, Schreiber(), einst, 1, {"text": "the mother angrier"}) is True
    assert gerufen == [("the mother angrier", 2)]

    knoepfe.erwarte_geschichte_notiz(1)
    assert ablauf._szene_hat_vorfahrt(
        conn, tg, Schreiber(), einst, 1, {"text": "a sadder ending"}) is True
    assert gerufen[-1] == ("a sadder ending", None)


def test_dortmund_bietet_weiter_geschichte_schreiben(conn, ohne_profil, tg, einst):
    assert not ueberarbeitung.aktiv()
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 6, "test")

    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 6)

    assert _letzte_leiste_hat(tg, knoepfe.ART_GESCHICHTE_SCHREIBEN, conn)
    assert repo.prueflaeufe(conn, 1) == []

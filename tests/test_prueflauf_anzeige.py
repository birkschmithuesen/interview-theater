"""Die Anzeige nach dem Prueflauf (Padua Phasen TEIL 2, Task 7).

In Padua geht jeder Szenen- und Geschichtenlauf: still schreiben ->
``prueflauf`` -> ein kurzer Hinweis im Chat (nie der Volltext) mit Knoepfen.
Dortmund und das Vorgabeprofil bleiben, wie sie sind: der Volltext steht im
Chat, und es gibt keine Zeile in ``prueflauf``.

Alle Modellaufrufe gehen gegen Attrappen: ein Schreiber, dessen Text die
Marke ``KOERPER-MARKER-`` traegt, und ein Richter ohne Befunde (leerer Plan
des ``Rundenrichter``) -- keine Auftraege, also keine Ueberarbeitung.
"""

import dataclasses
import re

import pytest

import test_dramaturgie_schleife as schleifentest
from interview_theater import (
    knoepfe, kurzgeschichte, phasen, prueflauf, repo, szene, workshop,
)
from interview_theater.dramaturgie import fanout
from test_dramaturgie_schleife import Rundenrichter
from test_knoepfe import TelegramAttrappe, _druck

MARKE = "KOERPER-MARKER-"


class Schreiber:
    """Szenen- und Geschichtenlauf ohne Modell. Jeder Text traegt die Marke."""

    def __init__(self):
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe.append(art)
        n = len(self.aufrufe)
        if art == kurzgeschichte.ART:
            return (
                "## 1. Am Steg\nZusammenfassung: Sie treffen sich.\n\n"
                f"{MARKE}A{n} Mira wartet am Steg auf Jonas.\n\n"
                "## 2. Der Koffer\nZusammenfassung: Er oeffnet ihn.\n\n"
                f"{MARKE}B{n} Jonas oeffnet den Koffer.\n"
            )
        return (
            "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
            "ZUSAMMENFASSUNG: Mira und Jonas treffen sich am Steg.\n"
            "ANDERS GEMACHT: nichts\n\n"
            f"{MARKE}{n} Mira steht am Steg. Jonas schaut auf das Wasser.\n"
        )


class KaputtesModell:
    """Jeder Modellaufruf ist ein Fehler -- Zusage 2."""

    def __getattr__(self, name):
        def _kaputt(*a, **k):
            raise AssertionError(f"Modellaufruf im Knopf-Handler: {name}")
        return _kaputt


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
    yield
    workshop.vergiss()


@pytest.fixture
def ohne_profil(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def _stueck(conn, phase: int, szenen=(1,)):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jonas", "schweigt lieber")
    ids = [repo.hole_figur(conn, 1, n)["id"] for n in ("Mira", "Jonas")]
    for nummer in szenen:
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        for feld, wert in (("ort", "Steg"), ("was_passiert", "Sie treffen sich.")):
            repo.setze_szenenfeld(conn, szene_id, feld, wert)
        repo.setze_szene_figuren(conn, 1, szene_id, ids)
    phasen.setze(conn, 1, phase, "test")
    return conn


def _warte(sperre, timeout=20) -> None:
    assert sperre.acquire(timeout=timeout), "Hintergrundlauf nicht rechtzeitig fertig"
    sperre.release()


def _alles(tg) -> str:
    return "\n".join(t for _, t in tg.gesendet) + "\n".join(
        t for _, t, _l in tg.knoepfe)


def _starte_szene_1(conn, tg, klm, einst):
    faden = szene.starte(
        conn, tg, klm, einst, 1,
        "SZENE 1: write this scene as prose, following the overview.")
    assert faden is not None, "kein Szenenlauf angestossen"
    faden.join(20)
    _warte(szene._sperre_fuer(1))


def test_phase5_stufe_b_zeigt_nur_hinweis(conn, padua, tg, einst):
    _stueck(conn, 5)

    _starte_szene_1(conn, tg, Schreiber(), einst)

    assert MARKE not in _alles(tg)
    beschriftungen = [b for b, _d in tg.knoepfe[-1][2]]
    assert "Show first draft" in beschriftungen
    # TEIL 1 drueckt den ersten Knopf: er bleibt "Passt" (ART_SZENE_PASST).
    knopf = repo.hole_knopf(conn, knoepfe._id_aus_daten(tg.knoepfe[-1][2][0][1]))
    assert knopf["art"] == knoepfe.ART_SZENE_PASST
    (zeile,) = repo.prueflaeufe(conn, 1)
    assert zeile["phase"] == 5
    assert zeile["fragen"] == "b1,a10"
    hinweis = tg.knoepfe[-1][1]
    assert hinweis.startswith("Scene 1 of 1 is ready")
    assert "Mira und Jonas treffen sich am Steg." in hinweis
    assert "Read it in the Script tab." in hinweis


def test_telegram_bekommt_einen_link(conn, padua, tg, einst):
    _stueck(conn, 5)
    e = dataclasses.replace(einst, web_url="https://x/theatersoap")

    _starte_szene_1(conn, tg, Schreiber(), e)

    hinweis = tg.knoepfe[-1][1]
    assert "/g/" in hinweis and "#textbuch" in hinweis
    assert MARKE not in _alles(tg)


def test_web_gruppe_bekommt_den_tab_statt_link(conn, padua, einst):
    _stueck(conn, 5)
    e = dataclasses.replace(einst, web_url="https://x/theatersoap")
    conn.execute("UPDATE gruppe SET kanal = 'web' WHERE chat_id = 1")
    conn.commit()

    assert knoepfe.skript_verweis(conn, e, 1) == "Read it in the Script tab."


def test_phase6_szene_hat_die_ueberarbeitungsleiste(conn, padua, tg, einst):
    _stueck(conn, 6)

    _starte_szene_1(conn, tg, Schreiber(), einst)

    assert MARKE not in _alles(tg)
    arten = [repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"]
             for _b, d in tg.knoepfe[-1][2]]
    assert arten == [knoepfe.ART_SZENE_PASST, knoepfe.ART_SZENE_ANDERS,
                     knoepfe.ART_SZENE_KUERZEN, knoepfe.ART_ERSTENTWURF]


def test_ohne_schalter_wie_bisher(conn, ohne_profil, tg, einst):
    _stueck(conn, 5)

    _starte_szene_1(conn, tg, Schreiber(), einst)

    assert MARKE in _alles(tg)
    assert repo.prueflaeufe(conn, 1) == []
    assert all(b != "Show first draft" and b != "Erste Fassung zeigen"
               for _c, _t, leiste in tg.knoepfe for b, _d in leiste)


def test_erstentwurf_knopf_ohne_modellaufruf(conn, padua, tg, einst):
    _stueck(conn, 6)
    _starte_szene_1(conn, tg, Schreiber(), einst)
    daten = next(d for b, d in tg.knoepfe[-1][2] if b == "Show first draft")

    assert knoepfe.behandle(conn, tg, KaputtesModell(), einst, _druck(daten)) is True

    antwort = tg.gesendet[-1][1]
    assert "First draft" in antwort
    assert "Script tab" in antwort


def test_erstentwurf_ohne_fassung(conn, padua, tg, einst):
    _stueck(conn, 6)
    knopf = repo.lege_knopf_an(conn, 1, knoepfe.ART_ERSTENTWURF, "1")

    knoepfe.behandle(conn, tg, KaputtesModell(), einst,
                     _druck(knoepfe._daten(knopf)))

    assert tg.gesendet[-1][1] == "There is no earlier draft for this yet."


def test_geschichte_zeigt_nur_hinweis(conn, padua, tg, einst):
    _stueck(conn, 6, szenen=(1, 2))

    faden = kurzgeschichte.starte(conn, tg, Schreiber(), einst, 1, None)
    assert faden is not None
    faden.join(20)
    _warte(kurzgeschichte._sperre_fuer(1))

    assert MARKE not in _alles(tg)
    (zeile,) = repo.prueflaeufe(conn, 1)
    assert zeile["ziel"] == "geschichte"
    hinweis = tg.knoepfe[-1][1]
    assert hinweis.startswith("The whole story is there (2 scenes).")
    arten = [repo.hole_knopf(conn, knoepfe._id_aus_daten(d))["art"]
             for _b, d in tg.knoepfe[-1][2]]
    assert arten == [knoepfe.ART_GESCHICHTE_PASST, knoepfe.ART_GESCHICHTE_ANDERS,
                     knoepfe.ART_GESCHICHTE_KUERZEN, knoepfe.ART_ERSTENTWURF]


def test_geschichte_ohne_schalter_wie_bisher(conn, ohne_profil, tg, einst):
    _stueck(conn, 6, szenen=(1, 2))

    faden = kurzgeschichte.starte(conn, tg, Schreiber(), einst, 1, None)
    faden.join(20)
    _warte(kurzgeschichte._sperre_fuer(1))

    assert MARKE in _alles(tg)
    assert repo.prueflaeufe(conn, 1) == []


def test_pruefung_ohne_ueberarbeitung_zeigt_volltext_und_zeilen(
        conn, padua, tg, einst, monkeypatch):
    """Die Kombination ohne Profil: Prueflauf an, Ueberarbeitung aus ->
    der Volltext wie bisher, die Zeilen als eigene Nachricht."""
    monkeypatch.setattr(workshop, "ueberarbeitung_aktiv", lambda *a, **k: False)
    _stueck(conn, 6)
    _starte_szene_1(conn, tg, Schreiber(), einst)
    tg.gesendet.clear()
    bericht = prueflauf.Bericht(zeilen=["Zeile eins."])

    knoepfe.zeige_geprueft_szene(conn, tg, einst, 1, 1, bericht)

    texte = [t for _, t in tg.gesendet]
    assert any(MARKE in t for t in texte)
    assert texte[-1] == "Zeile eins."

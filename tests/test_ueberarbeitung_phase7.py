"""Phase 7 (Stage Version) in Padua (Padua Phasen TEIL 2, Task 9).

Erst waehlt die Gruppe die Form je Szene (EINE Nachricht mit der ganzen
Szenenliste, keine Knoepfe, kein Vorschlag), dann bekommen alle Figuren eine
Sprechweise (EINE Nachricht, "Yes, save"), dann wird Szene fuer Szene
uebertragen und geprueft, und am Ende laeuft die Pruefung ueber das ganze
Textbuch und danach die Stueckpruefung -- mit der Zeile "The script is
complete" ganz am Schluss.

Richter ohne Befunde (``Rundenrichter({})``): keine Auftraege, also keine
Ueberarbeitung.
"""

import re
import time

import pytest

import test_dramaturgie_schleife as schleifentest
from interview_theater import (
    knoepfe, phasen, prueflauf, repo, sprechweise, stueckpruefung, szene,
    ueberarbeitung, workshop,
)
from interview_theater.dramaturgie import fanout
from test_dramaturgie_schleife import Rundenrichter
from test_knoepfe import TelegramAttrappe, _druck


class Schreiber:
    """Szenenlauf und Sprechweisen ohne Netz."""

    def __init__(self):
        self.prosa_aufrufe = []
        self.schema_aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.prosa_aufrufe.append((art, nutzer))
        return (
            "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
            "ZUSAMMENFASSUNG: Mira und Jonas treffen sich am Steg.\n"
            "ANDERS GEMACHT: nichts\n\n"
            "MIRA: Du bist spaet.\nJONAS: Ich weiss.\n"
        )

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               bei_teil=None):
        self.schema_aufrufe.append(art)
        return {"sprechweisen": ["Jonas: slow, long pauses"]}


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def stueckpruefung_spion(monkeypatch):
    gerufen = []

    def spion(conn, tg, klm, e, chat_id, nachbereitung=None):
        gerufen.append(chat_id)
        tg.sende(chat_id, "STUECKPRUEFUNG")
        if nachbereitung is not None:
            nachbereitung()
        return None

    monkeypatch.setattr(stueckpruefung, "starte", spion)
    monkeypatch.setattr(knoepfe.stationen, "starte_stueckpruefung",
                        lambda *a, **k: gerufen.append("stationen"))
    return gerufen


@pytest.fixture
def padua(monkeypatch, stueckpruefung_spion):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    monkeypatch.setattr(schleifentest, "_SZENE_IM_KOPF", re.compile(
        r"(?:Das ist Szene|Repliken von Szene|This is scene) (\d+)"))
    richter = Rundenrichter({})
    monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)
    yield stueckpruefung_spion
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
    repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", repo._jetzt())
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Jonas", "schweigt lieber")
    repo.setze_figur_sprachstil(conn, repo.hole_figur(conn, 1, "Mira")["id"],
                                "short sentences")
    ids = [repo.hole_figur(conn, 1, n)["id"] for n in ("Mira", "Jonas")]
    for nummer in szenen:
        sid = repo.stelle_szene_sicher(conn, 1, nummer)
        for feld, wert in (("ort", "Steg"), ("was_passiert", "Sie treffen sich.")):
            repo.setze_szenenfeld(conn, sid, feld, wert)
        repo.setze_szene_figuren(conn, 1, sid, ids)
        repo.aktualisiere_szene(
            conn, sid, f"Teil {nummer}", None, None,
            f"Teil {nummer} beginnt. Danach mehr.",
            prosa=f"Mira steht am Steg, Teil {nummer}. Jonas schaut aufs Wasser.",
        )
        repo.setze_szene_entwurf_bestaetigt(conn, sid)
        repo.setze_szene_ueberarbeitung_bestaetigt(conn, sid)
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 7, "test")
    return conn


def _formen(conn, formen=("chor", "dialog", "rap")):
    for s, form in zip(sorted(repo.hole_szenen(conn, 1), key=lambda s: s["nummer"]),
                       formen):
        repo.setze_szenenfeld(conn, s["id"], "form", form)


def _warte_auf(bedingung, timeout=20.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.02)
    raise AssertionError("Bedingung nicht rechtzeitig erfuellt")


def _knopf(conn, daten):
    return repo.hole_knopf(conn, knoepfe._id_aus_daten(daten))


def _letzte_leiste(conn, tg, art):
    if not tg.knoepfe:
        return None
    for _b, d in tg.knoepfe[-1][2]:
        if _knopf(conn, d)["art"] == art:
            return d
    return None


def _texte(tg):
    return [t for _, t in tg.gesendet]


def test_eintritt_zeigt_die_formwahl_ohne_knoepfe(conn, padua, tg, einst):
    _stueck(conn)

    knoepfe.eintritt_in_phase(conn, tg, Schreiber(), einst, 1, 7)

    formwahl = [t for t in _texte(tg) if "Which form for each number?" in t]
    assert len(formwahl) == 1
    (text,) = formwahl
    assert text.startswith("Here are your scenes:")
    for n in (1, 2, 3):
        assert f"\n{n}. Teil {n} -- Teil {n} beginnt." in text
    assert "Danach mehr" not in text, "nur der erste Satz"
    assert "Chorus" in text and "Dialogue" in text
    assert tg.knoepfe == []
    assert padua == [], "keine Stueckpruefung beim Eintritt"
    assert "Now the story becomes a play" in _texte(tg)[0]
    # Der Gespraechs-Bot sieht die Formwahl (Task 10 liest die Antwort).
    zeilen = conn.execute(
        "SELECT text FROM nachricht WHERE chat_id = 1").fetchall()
    assert any("Which form for each number?" in (z["text"] or "") for z in zeilen)


def test_mit_formen_kommen_die_sprechweisen(conn, padua, tg, einst):
    _stueck(conn)
    _formen(conn)
    klm = Schreiber()

    faden = ueberarbeitung.weiter_7(conn, tg, klm, einst, 1)
    faden.join(10)

    assert klm.schema_aufrufe == [sprechweise.ART]
    (_cid, text, leiste) = tg.knoepfe[-1]
    assert "- Mira: short sentences" in text
    assert "- Jonas: slow, long pauses" in text
    assert [b for b, _d in leiste] == ["Yes, save", "No, change it again"]


def test_ja_auf_sprechweisen_fixiert_und_startet_szene_1(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn)
    _formen(conn)
    klm = Schreiber()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1).join(10)
    auftraege = []
    monkeypatch.setattr(szene, "starte",
                        lambda c, t, k, e, cid, auftrag, *a, **kw:
                        auftraege.append(auftrag) or "faden")

    daten = _letzte_leiste(conn, tg, knoepfe.ART_SPRECHWEISEN_PASST)
    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten)) is True

    assert (repo.hole_arbeitsstand(conn, 1)["sprechweisen_fixiert_am"] or "").strip()
    assert "scene 1 of 3" in "\n".join(_texte(tg))
    assert auftraege == [ueberarbeitung.T._AUFTRAG_BUEHNE.format(nummer=1)]
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1


def test_szene_fuer_szene_und_am_ende_die_stueckpruefung(conn, padua, tg, einst):
    _stueck(conn)
    _formen(conn)
    klm = Schreiber()
    repo.setze_figur_sprachstil(conn, repo.hole_figur(conn, 1, "Jonas")["id"], "slow")
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())

    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1)
    for nummer in (1, 2, 3):
        _warte_auf(lambda n=nummer: (d := _letzte_leiste(
            conn, tg, knoepfe.ART_SZENE_PASST)) is not None
            and _knopf(conn, d)["wert"] == str(n)
            and not szene._sperre_fuer(1).locked())
        ziel = next(s for s in repo.hole_szenen(conn, 1) if s["nummer"] == nummer)
        assert "MIRA:" in (ziel["volltext"] or "")
        knoepfe.behandle(conn, tg, klm, einst, _druck(
            _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST), query_id=f"s{nummer}"))

    fertig = ueberarbeitung.T._TEXT_TEXTBUCH_FERTIG
    _warte_auf(lambda: any(t.startswith(fertig) for t in _texte(tg)))
    assert padua == [1]
    texte = _texte(tg)
    assert texte.index("STUECKPRUEFUNG") < max(
        i for i, t in enumerate(texte) if t.startswith(fertig))
    assert all((s["fertig_am"] or "").strip() for s in repo.hole_szenen(conn, 1))
    geschichte = [z for z in repo.prueflaeufe(conn, 1) if z["ziel"] == "geschichte"]
    assert len(geschichte) == 1
    assert geschichte[0]["phase"] == 7
    szenenlaeufe = sorted(z["szene_nummer"] for z in repo.prueflaeufe(conn, 1)
                          if z["ziel"] == "szene")
    assert szenenlaeufe == [1, 2, 3]
    assert not szene._sperre_fuer(1).locked()


def test_ja_auf_szene_waehrend_ein_lauf_geht_speichert_nichts(conn, padua, tg, einst):
    _stueck(conn)
    _formen(conn)
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    sperre = szene._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        antwort = ueberarbeitung.bestaetige_szene_7(conn, tg, Schreiber(), einst, 1, 1)
    finally:
        sperre.release()
    assert antwort == ueberarbeitung.T._TEXT_LAEUFT_NOCH
    assert _texte(tg) == [antwort]
    assert all(not (s["fertig_am"] or "").strip() for s in repo.hole_szenen(conn, 1))


def test_ja_auf_sprechweisen_waehrend_sie_laufen_speichert_nichts(
        conn, padua, tg, einst):
    _stueck(conn)
    _formen(conn)
    sperre = sprechweise._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        antwort = ueberarbeitung.bestaetige_sprechweisen(conn, tg, Schreiber(), einst, 1)
    finally:
        sperre.release()
    assert antwort == ueberarbeitung.T._TEXT_LAEUFT_NOCH
    assert not (repo.hole_arbeitsstand(conn, 1)["sprechweisen_fixiert_am"] or "").strip()


def test_wiedereintritt_mit_text_prueft_statt_neu_zu_schreiben(
        conn, padua, tg, einst, monkeypatch):
    _stueck(conn)
    _formen(conn)
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    sid = next(s["id"] for s in repo.hole_szenen(conn, 1) if s["nummer"] == 1)
    repo.aktualisiere_szene(conn, sid, "Teil 1", None, "MIRA: Da.\nJONAS: Ja.",
                            "Teil 1 beginnt.")
    monkeypatch.setattr(szene, "starte", lambda *a, **k: pytest.fail("neu"))

    faden = ueberarbeitung.weiter_7(conn, tg, Schreiber(), einst, 1)
    faden.join(20)
    _warte_auf(lambda: _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST) is not None)

    (lauf,) = repo.prueflaeufe(conn, 1)
    assert (lauf["ziel"], lauf["szene_nummer"]) == ("szene", 1)


def _alles_fertig(conn):
    _stueck(conn)
    _formen(conn)
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", repo._jetzt())
    for s in repo.hole_szenen(conn, 1):
        repo.aktualisiere_szene(conn, s["id"], s["titel"], None, "MIRA: Da.",
                                s["zusammenfassung"])
        repo.setze_szene_fertig(conn, s["id"], True)


def _schluss_protokoll(conn):
    repo.lege_prueflauf_an(
        conn, 1, phase=7, ziel="geschichte", szene_nummer=None,
        fragen=",".join(prueflauf.FRAGEN_GESCHICHTE), runden=1,
        ueberarbeitungen=0, auftraege_je_runde="0",
        zweite_runde_mit_auftraegen=False, grund="keine_auftraege",
        verworfen=None, dauer_ms=1,
    )


def test_wiedereintritt_ohne_schlusspruefung_holt_sie_nach(
        conn, padua, tg, einst, monkeypatch):
    """Neustart mitten im Schluss: alle Szenen fertig, aber keine
    Protokollzeile der Schlusspruefung -> der Eintritt holt sie nach."""
    _alles_fertig(conn)
    gestartet = []
    echt = ueberarbeitung.starte_schluss

    def spion(*a, **k):
        gestartet.append(a)
        return echt(*a, **k)

    monkeypatch.setattr(ueberarbeitung, "starte_schluss", spion)

    knoepfe.eintritt_in_phase(conn, tg, Schreiber(), einst, 1, 7)

    assert len(gestartet) == 1
    fertig = ueberarbeitung.T._TEXT_TEXTBUCH_FERTIG
    _warte_auf(lambda: any(t.startswith(fertig) for t in _texte(tg)))
    assert not any(t.startswith(ueberarbeitung.T._TEXT_7_SCHON_FERTIG)
                   for t in _texte(tg))
    assert padua == [1]
    assert ueberarbeitung.schluss_gelaufen(conn, 1)


def test_wiedereintritt_nach_der_schlusspruefung_keine_neue(
        conn, padua, tg, einst, monkeypatch):
    _alles_fertig(conn)
    _schluss_protokoll(conn)
    monkeypatch.setattr(ueberarbeitung, "starte_schluss",
                        lambda *a, **k: pytest.fail("neuer Schlusslauf"))

    knoepfe.eintritt_in_phase(conn, tg, Schreiber(), einst, 1, 7)

    assert padua == []
    assert len(repo.prueflaeufe(conn, 1)) == 1
    assert any(t.startswith(ueberarbeitung.T._TEXT_7_SCHON_FERTIG) for t in _texte(tg))


def test_belegter_naechster_schritt_gibt_eine_zeile(conn, padua, tg, einst, monkeypatch):
    _stueck(conn)
    _formen(conn)
    monkeypatch.setattr(sprechweise, "starte", lambda *a, **k: None)

    assert ueberarbeitung.weiter_7(conn, tg, Schreiber(), einst, 1) is None
    assert _texte(tg) == [ueberarbeitung.T._TEXT_LAEUFT_NOCH]


def test_dortmund_eintritt_7_bleibt_durchlauf_und_stueckpruefung(
        conn, ohne_profil, tg, einst, monkeypatch):
    assert not ueberarbeitung.aktiv()
    gerufen = []
    monkeypatch.setattr(knoepfe.stationen, "starte_stueckpruefung",
                        lambda *a, **k: gerufen.append("stueck"))
    monkeypatch.setattr(knoepfe.stationen, "biete_durchlauf",
                        lambda *a, **k: gerufen.append("durchlauf"))
    monkeypatch.setattr(ueberarbeitung, "weiter_7",
                        lambda *a, **k: pytest.fail("Padua-Weg in Dortmund"))
    phasen.setze(conn, 1, 7, "test")

    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 7)

    assert gerufen == ["durchlauf", "stueck"]

"""Die Zusage an Dortmund: der ganze Pfad ist ein No-Op (30.09.2026, Karte R).

Ohne aktives Profil darf kein zusaetzlicher Modellaufruf entstehen, kein
zusaetzlicher Vorfall, keine zusaetzliche Journalzeile und kein Zeichen mehr
im Prompt. Geprueft wird nicht der Schalter, sondern die WIRKUNG.
"""

import pytest

from interview_theater import (
    kurzgeschichte, laengen, nachpass, phasen, repo, szene, workshop,
)

from test_knoepfe import TelegramAttrappe
from test_nachpass import (  # noqa: F401  (Fixtures: szene7 braucht padua)
    LLMAttrappe, LANG, KURZ, _vorfallarten, padua, szene7,
)


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def ohne_profil(monkeypatch):
    from interview_theater import anweisungen
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture
def szene7_dortmund(conn, ohne_profil):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


# --- Dortmund: genau EIN Modellaufruf je Szene --------------------------


def test_ein_szenenlauf_bleibt_ein_aufruf(szene7_dortmund, tg, einst):
    """Der Kern der Zusage: kein Nachpass, keine Zusatzkosten."""
    klm = LLMAttrappe(LANG)          # bewusst zu lang -- ohne Profil egal
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["art"] == szene.ART


def test_kein_nachpass_vorfall(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(LANG)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    arten = set(_vorfallarten(szene7_dortmund))
    assert not (arten & {nachpass.VORFALL_GELAUFEN, nachpass.VORFALL_VERWORFEN,
                         nachpass.VORFALL_IMMER_NOCH,
                         nachpass.VORFALL_ABSCHNITTSZAHL,
                         nachpass.VORFALL_FEHLER})


def test_keine_laengen_journalzeile(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(KURZ)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    texte = [j["text"] for j in repo.journal(szene7_dortmund, 1)]
    assert not any("Seed" in t or "gewuerfelt" in t for t in texte)


def test_kein_laengenblock_im_prompt(szene7_dortmund, tg, einst):
    klm = LLMAttrappe(KURZ)
    thread = szene.starte(szene7_dortmund, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert laengen.BLOCK_KOPF_SZENE not in klm.aufrufe[0]["nutzer"]


def test_die_drei_funktionen_liefern_nichts_zu_tun(szene7_dortmund):
    """Nicht der Schalter wird geprueft, sondern die Wirkung: ohne Profil
    liefern Budget, Nachzaehlen und Sprachpass "nichts"."""
    ziel = szene.ziel_fuer(szene7_dortmund, 1, "Schreib Szene 1")
    assert szene.budget_fuer_szene(szene7_dortmund, 1, ziel) == 0
    stand = nachpass.befund(szene7_dortmund, 1, 1)
    assert stand["zu_lang"] is False and stand["gemeldet"] == []
    assert nachpass.befund_prosa(szene7_dortmund, 1)["eintraege"] == []


# --- Padua: der Nachpass laeuft wirklich ------------------------------


def test_padua_haengt_genau_einen_lauf_an(szene7, tg, einst):  # noqa: F811
    """Die Gegenprobe: mit Profil sind es zwei Aufrufe -- der Szenenlauf und
    genau ein Nachpass."""
    klm = LLMAttrappe(LANG, KURZ)
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=30)
    assert [a["art"] for a in klm.aufrufe] == [szene.ART, nachpass.ART_SZENE]


def test_der_nachpass_laeuft_unter_derselben_sperre(szene7, tg, einst):  # noqa: F811
    """Waehrend er laeuft, darf kein zweiter Szenenlauf derselben Gruppe
    dazwischenkommen -- die Sperre haelt das schon, man darf sie nur nicht
    vorher loslassen."""
    klm = LLMAttrappe(LANG, KURZ)
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    assert szene._sperre_fuer(1).locked() is True
    thread.join(timeout=30)
    assert szene._sperre_fuer(1).locked() is False
    assert len(klm.aufrufe) == 2


def test_ein_gescheiterter_szenenlauf_loest_keinen_nachpass_aus(szene7, tg, einst):  # noqa: F811
    """Der Aufruf steht im ``try``, nicht im ``finally``: nach einem
    gescheiterten Lauf gibt es keinen Text, ueber den nachzuzaehlen waere."""
    class Kaputt:
        def __init__(self):
            self.aufrufe = []

        def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                  timeout=None):
            self.aufrufe.append(art)
            raise RuntimeError("Modell weg")

    klm = Kaputt()
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)
    assert klm.aufrufe == [szene.ART]

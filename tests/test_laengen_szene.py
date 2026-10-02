"""Phase 7: das Budget im Szenen-Prompt (30.09.2026, Karte R).

Der Block steht im **nie gekuerzten** Teil des Nutzertexts: eine Laenge, die
die Kuerzungsleiter wegwerfen darf, ist keine Vorgabe. Ohne aktives Profil
bleibt der Nutzertext zeichengleich.
"""

import pytest

from interview_theater import laengen, phasen, repo, szene, workshop

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


class SzeneAttrappe:
    ANTWORT = (
        "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
        "ZUSAMMENFASSUNG: Mira und Pal treffen sich.\nANDERS GEMACHT: nichts\n\n"
        "MIRA: Du bist zu spaet.\nPAL: Ich war da.\n"
    )

    def __init__(self, antwort=None):
        self.antwort = antwort or self.ANTWORT
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


@pytest.fixture
def szene7(conn):
    """Phase 7, eine planungsvollstaendige Szene 1 mit bestaetigter Form."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    # ``setze_figur`` liefert **kein** id zurueck (repo.py:1827, Rueckgabe
    # ``None``) -- die id wird danach gelesen, so wie es auch
    # ``tests/test_kuerzung.py`` tut.
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Der Block ------------------------------------------------------------


def test_der_laengenblock_steht_direkt_hinter_der_aufgabe():
    """Reihenfolge ist Wirkung: die Laenge gehoert zu dem, was die Gruppe
    entschieden hat, und steht deshalb im nie gekuerzten Teil."""
    i = list(szene._REIHENFOLGE).index("aufgabe")
    assert szene._REIHENFOLGE[i + 1] == "laenge"


def test_der_laengenblock_wird_nie_gekuerzt():
    """``_kuerze_szenenprompt`` kuerzt Vorszenen, Chat, Kernpaket und
    Sprachprofil-Zitate -- die Laenge darf in keiner dieser Stufen
    verschwinden."""
    import inspect
    quelle = inspect.getsource(szene._kuerze_szenenprompt)
    assert "laenge" not in quelle


def test_ohne_profil_bleibt_der_nutzertext_zeichengleich(szene7):
    ziel = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    assert szene.budget_fuer_szene(szene7, 1, ziel) == 0
    text = szene.baue_nutzertext(szene7, 1, "Schreib Szene 1", ziel)
    assert laengen.BLOCK_KOPF_SZENE not in text


def test_mit_profil_steht_das_budget_im_nutzertext(szene7, padua):
    ziel = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    budget = szene.budget_fuer_szene(szene7, 1, ziel)
    assert 200 <= budget <= 450, budget          # Dialog-Rahmen
    text = szene.baue_nutzertext(szene7, 1, "Schreib Szene 1", ziel)
    # Padua spricht Englisch: Kopf und Vorrang kommen ueber ``T``.
    assert laengen.T.BLOCK_KOPF_SZENE in text
    assert str(budget) in text
    assert laengen.T.SATZ_VORRANG in text


def test_das_budget_folgt_der_bestaetigten_form(szene7, padua):
    """Chor ist kuerzer als Dialog -- dieselbe Szene, andere Form, anderes
    Budget."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    ziel_dialog = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    dialog = szene.budget_fuer_szene(szene7, 1, ziel_dialog)
    repo.setze_szenenfeld(szene7, szene_id, "form", "chor")
    ziel_chor = szene.ziel_fuer(szene7, 1, "Schreib Szene 1")
    chor = szene.budget_fuer_szene(szene7, 1, ziel_chor)
    assert chor < dialog, (chor, dialog)


def test_ohne_ziel_gibt_es_kein_budget(szene7, padua):
    assert szene.budget_fuer_szene(szene7, 1, None) == 0


# --- ``art`` als Parameter ------------------------------------------------


def test_schreibe_nimmt_eine_eigene_art(szene7, tg, einst):
    klm = SzeneAttrappe()
    szene.schreibe(szene7, tg, klm, einst, 1, "Schreib Szene 1",
                   art="szene_nachpass")
    assert klm.aufrufe[0]["art"] == "szene_nachpass"


def test_ohne_art_bleibt_es_bei_der_bisherigen(szene7, tg, einst):
    klm = SzeneAttrappe()
    szene.schreibe(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    assert klm.aufrufe[0]["art"] == szene.ART


def test_starte_gibt_die_art_durch(szene7, tg, einst):
    klm = SzeneAttrappe()
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1",
                          art="szene_nachpass")
    assert thread is not None
    thread.join(timeout=20)
    assert klm.aufrufe and klm.aufrufe[0]["art"] == "szene_nachpass"

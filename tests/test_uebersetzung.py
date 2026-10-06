"""Die englische Uebersetzung der Dashboard-Felder (Padua, t_f7770dc4):
Segmentbau, Hash-Cache und der eine Schreiber-Aufruf je Aenderung."""

import json

import pytest

from interview_theater import repo, uebersetzung, workshop


class _FakeKlm:
    """Steht fuer llm.LLM: zaehlt Aufrufe, uebersetzt durch einen festen
    Praefix statt eines echten Modells."""

    def __init__(self, antwort=None):
        self.aufrufe = []
        self._antwort = antwort

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort"):
        self.aufrufe.append(
            {"chat_id": chat_id, "nutzer": nutzer, "schema": schema,
             "art": art, "modell": modell})
        if self._antwort is not None:
            return self._antwort
        seg = json.loads(nutzer)
        return {k: f"EN:{v}" for k, v in seg.items()}


# --- segmente() --------------------------------------------------------------


def test_segmente_sammelt_alle_felder():
    stand = {
        "rahmen": "a bridge", "geschichte": "two friends", "kernthema": "belonging",
        "hauptkonflikt": "stay or leave", "begriffe": "bridge, market, rain",
        "fragen": "Home: Where?",
    }
    figuren = [{"name": "Mira"}, {"name": "Luca"}]
    kurzformen = [
        {"name": "Interview 1", "kurzformen": ["fishing at dawn", "a lost key"]},
        {"name": "Interview 2", "kurzformen": ["the old bakery"]},
    ]
    seg = uebersetzung.segmente(stand, figuren, kurzformen)
    assert seg == {
        "rahmen": "a bridge", "geschichte": "two friends", "kernthema": "belonging",
        "hauptkonflikt": "stay or leave", "begriffe": "bridge, market, rain",
        "fragen": "Home: Where?",
        "figur_0": "Mira", "figur_1": "Luca",
        "interview_0_0": "fishing at dawn", "interview_0_1": "a lost key",
        "interview_1_0": "the old bakery",
        "hauptthema": "belonging",
        "b_2fa1981b4a9a": "bridge", "b_5c9f73af7333": "market", "b_fbec17cb2fcb": "rain",
        "b_70f8bb9a8a53": "Home",  # fremder Kopf in "fragen", kein Begriff der Gruppe
        "q_92b8d23bee56": "Where?",
    }


# --- segmente(): q_/b_ Schluessel je Fragenzeile/Begriff -----------------------


def test_segmente_q_schluessel_je_zeile_aus_fragen_und_fragen_auswahl():
    """Beide Felder tragen bei, nicht nur ``fragen`` -- waehrend eine Gruppe
    noch sortiert, steht die Uebersetzung in ``fragen_auswahl``."""
    stand = {"begriffe": "Home, Work",
              "fragen": "Home: Q1",
              "fragen_auswahl": "Home: Q1\nWork: Q2"}
    seg = uebersetzung.segmente(stand, [], [])
    assert seg[uebersetzung.zeile_schluessel("Home: Q1")] == "Q1"
    assert seg[uebersetzung.zeile_schluessel("Work: Q2")] == "Q2"


def test_segmente_q_schluessel_dedupliziert_gleiche_zeile():
    """Dieselbe Zeile in ``fragen`` UND ``fragen_auswahl`` (nach dem
    Abschluss der Sortierung) erzeugt nur EINEN Schluessel."""
    stand = {"begriffe": "Home", "fragen": "Home: Q1", "fragen_auswahl": "Home: Q1"}
    seg = uebersetzung.segmente(stand, [], [])
    treffer = [k for k in seg if k == uebersetzung.zeile_schluessel("Home: Q1")]
    assert len(treffer) == 1


def test_segmente_b_schluessel_je_begriff():
    stand = {"begriffe": "Home, Work"}
    seg = uebersetzung.segmente(stand, [], [])
    assert seg[uebersetzung.begriff_schluessel("Home")] == "Home"
    assert seg[uebersetzung.begriff_schluessel("Work")] == "Work"


def test_segmente_fremder_kopf_bekommt_eigenen_b_schluessel():
    """Ein Kopf, der KEIN Begriff der Gruppe ist (ein Ad-hoc-Thema der
    Fragengenerierung, Padua G3: 'ricordi personali' o.ae.) braucht selbst
    eine Uebersetzung -- derselbe Schluesselraum wie fuer echte Begriffe."""
    stand = {"begriffe": "EVENTO", "fragen_auswahl": "ricordi personali: Q1"}
    seg = uebersetzung.segmente(stand, [], [])
    assert seg[uebersetzung.begriff_schluessel("ricordi personali")] == "ricordi personali"
    assert seg[uebersetzung.zeile_schluessel("ricordi personali: Q1")] == "Q1"


def test_segmente_zeile_ohne_kopf_bleibt_unveraendert():
    """Eine Zeile ohne erkennbaren Kopf (keine Fortsetzung, kein Begriff)
    bleibt als Ganzes der Wert -- dieselbe Zeile, die das Dashboard dann
    unveraendert zeigt."""
    stand = {"begriffe": "Home", "fragen_auswahl": "just a loose line"}
    seg = uebersetzung.segmente(stand, [], [])
    assert seg[uebersetzung.zeile_schluessel("just a loose line")] == "just a loose line"


def test_segmente_leer_ohne_inhalt():
    assert uebersetzung.segmente({}, [], []) == {}
    assert uebersetzung.segmente(None, None, None) == {}


def test_segmente_ueberspringt_leere_felder():
    stand = {"rahmen": "", "geschichte": None, "kernthema": "belonging"}
    seg = uebersetzung.segmente(stand, [], [])
    assert "rahmen" not in seg
    assert "geschichte" not in seg
    assert seg["kernthema"] == "belonging"


def test_hauptthema_aus_kernthema_wenn_gesetzt():
    assert uebersetzung.hauptthema_quelle({"kernthema": "belonging", "begriffe": "x"}) == "belonging"


def test_hauptthema_aus_begriffen_ohne_kernthema():
    stand = {"kernthema": None, "begriffe": "bridge, market, rain, extra"}
    assert uebersetzung.hauptthema_quelle(stand) == "bridge, market, rain"


def test_hauptthema_none_ohne_kernthema_und_begriffe():
    assert uebersetzung.hauptthema_quelle({}) is None
    assert uebersetzung.hauptthema_quelle({"kernthema": None, "begriffe": None}) is None


# --- quelle_hash() -------------------------------------------------------------


def test_quelle_hash_stabil_bei_gleicher_quelle():
    stand = {"kernthema": "belonging"}
    a = uebersetzung.quelle_hash(stand, [], [])
    b = uebersetzung.quelle_hash(dict(stand), [], [])
    assert a == b
    assert a != ""


def test_quelle_hash_aendert_sich_bei_aenderung():
    a = uebersetzung.quelle_hash({"kernthema": "belonging"}, [], [])
    b = uebersetzung.quelle_hash({"kernthema": "something else"}, [], [])
    assert a != b


def test_quelle_hash_leer_ohne_segmente():
    assert uebersetzung.quelle_hash({}, [], []) == ""


# --- englisch() ----------------------------------------------------------------


def _gruppe(**zusatz) -> dict:
    basis = {
        "arbeitsstand": {"kernthema": "belonging"},
        "figuren": [],
        "interview_kurzformen": [],
    }
    basis.update(zusatz)
    return basis


def test_englisch_leer_ohne_cache():
    assert uebersetzung.englisch(_gruppe()) == {}


def test_englisch_leer_bei_hash_mismatch():
    g = _gruppe(uebersetzung={"quelle_hash": "veraltet", "felder": {"kernthema": "EN:belonging"}})
    assert uebersetzung.englisch(g) == {}


def test_englisch_liefert_felder_bei_passendem_hash():
    stand = {"kernthema": "belonging"}
    hash_ = uebersetzung.quelle_hash(stand, [], [])
    g = _gruppe(arbeitsstand=stand,
                uebersetzung={"quelle_hash": hash_, "felder": {"kernthema": "EN:belonging",
                                                                "hauptthema": "EN:belonging"}})
    assert uebersetzung.englisch(g) == {"kernthema": "EN:belonging", "hauptthema": "EN:belonging"}


# --- aktualisiere() (Schreiber-Seite, mit echter DB) ---------------------------


CHAT = 1  # von conftest.conn als "gruppe1" angelegt


def test_aktualisiere_ohne_inhalt_ist_no_op(conn, einst):
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is False
    assert klm.aufrufe == []
    assert repo.hole_uebersetzung(conn, CHAT) is None


def test_aktualisiere_erster_lauf_ruft_modell_einmal_und_speichert(conn, einst):
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["modell"] == einst.erkenner_modell
    zeile = repo.hole_uebersetzung(conn, CHAT)
    assert zeile is not None
    felder = json.loads(zeile["felder"])
    assert felder["kernthema"] == "EN:belonging"


def test_aktualisiere_cache_hit_kein_weiterer_modellaufruf(conn, einst):
    """Kernkriterium der Karte: ein unveraenderter Quelltext ruft das
    Modell nicht noch einmal."""
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is False
    assert len(klm.aufrufe) == 1   # Mutation Check: ohne den Hash-Vergleich waere es 2.


def test_aktualisiere_bei_aenderung_genau_ein_weiterer_aufruf(conn, einst):
    """Kernkriterium der Karte: eine geaenderte Quelle loest genau EINE
    Neu-Uebersetzung aus -- nicht keine, nicht mehrere."""
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    uebersetzung.aktualisiere(conn, klm, einst, CHAT)
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "something else")
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    assert len(klm.aufrufe) == 2
    zeile = repo.hole_uebersetzung(conn, CHAT)
    felder = json.loads(zeile["felder"])
    assert felder["kernthema"] == "EN:something else"
    # Nochmal ohne Aenderung: wieder ein Cache-Hit, kein dritter Aufruf.
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is False
    assert len(klm.aufrufe) == 2


def test_aktualisiere_verwendet_figuren_und_interviews(conn, einst):
    repo.setze_figur(conn, CHAT, "Mira", "a student")
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, 1, "lang", "sprache", brainstorm=False, schnittgrund=None,
    )
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "summary",
        [{"thema": "fishing", "kurz": "fishing at dawn",
          "beleg_zitat": None, "zitat_geprueft": 0}],
    )
    klm = _FakeKlm()
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    uebersetzung.aktualisiere(conn, klm, einst, CHAT)
    felder = json.loads(repo.hole_uebersetzung(conn, CHAT)["felder"])
    assert felder["figur_0"] == "EN:Mira"
    assert felder["interview_0_0"] == "EN:fishing at dawn"


# --- aktualisiere_fuer_bot() (der Profilschalter) ------------------------------


@pytest.fixture(autouse=True)
def _frisch_profil():
    yield
    workshop.vergiss()


def test_aktualisiere_fuer_bot_ohne_schalter_ist_no_op(conn, einst, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere_fuer_bot(conn, klm, einst) == 0
    assert klm.aufrufe == []


def test_aktualisiere_fuer_bot_mit_padua_profil_uebersetzt(conn, einst, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere_fuer_bot(conn, klm, einst) == 1
    assert len(klm.aufrufe) == 1

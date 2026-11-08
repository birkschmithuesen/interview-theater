"""Die englische Uebersetzung der Dashboard-Felder (Padua, t_f7770dc4):
Segmentbau, Hash-Cache und der eine Schreiber-Aufruf je Aenderung."""

import json

import pytest

from interview_theater import repo, uebersetzung, workshop


class _Ausfall(Exception):
    """Steht fuer den LLMFehler, den ``klm.schema`` nach den eigenen
    Wiederholungen wirft -- hier genuegt eine beliebige Ausnahme, da
    ``uebersetzung.aktualisiere`` nichts Spezifisches faengt, sondern sie
    durchreicht."""


class _FakeKlm:
    """Steht fuer llm.LLM: zaehlt Aufrufe, uebersetzt durch einen festen
    Praefix statt eines echten Modells.

    ``fehler_bei_aufruf`` simuliert ein Haeppchen, das endgueltig scheitert
    (nach den eigenen Wiederholungen von ``klm.schema``) -- die Aufrufe
    sind nullbasiert durchnummeriert, unabhaengig davon, wie viele
    Schluessel je Aufruf uebersetzt werden."""

    def __init__(self, antwort=None, fehler_bei_aufruf=()):
        self.aufrufe = []
        self._antwort = antwort
        self._fehler_bei_aufruf = set(fehler_bei_aufruf)

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort"):
        index = len(self.aufrufe)
        self.aufrufe.append(
            {"chat_id": chat_id, "nutzer": nutzer, "schema": schema,
             "art": art, "modell": modell})
        if index in self._fehler_bei_aufruf:
            raise _Ausfall(f"simulierter Ausfall bei Aufruf {index}")
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


# --- aktualisiere(): Haeppchen statt EIN Riesenaufruf (Sofort-Fix 06.10.2026) --


def _begriffe(anzahl: int) -> str:
    return ", ".join(f"term{i}" for i in range(anzahl))


def test_aktualisiere_teilt_viele_schluessel_in_haeppchen(conn, einst):
    """40 Begriffe (plus die Felder ``begriffe`` und ``hauptthema`` selbst,
    42 Schluessel insgesamt) -> 3 Aufrufe von hoechstens
    ``HAEPPCHEN_GROESSE`` (15) statt EINEM Aufruf mit allen 42 (der nach
    dem Zusammenfuehren vieler Interviews regelmaessig mit ReadTimeout
    scheiterte)."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", _begriffe(40))
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    groessen = [len(json.loads(a["nutzer"])) for a in klm.aufrufe]
    # Mutation Check: ohne das Haeppchen-Limit waere es EIN Aufruf mit 42.
    assert len(klm.aufrufe) == 3
    assert groessen == [15, 15, 12]
    felder = json.loads(repo.hole_uebersetzung(conn, CHAT)["felder"])
    assert len(felder) == 42


def test_aktualisiere_sendet_unveraenderte_schluessel_nicht_erneut(conn, einst):
    """Kernkriterium der Karte: nur Schluessel, deren Quelltext sich
    geaendert hat, werden neu uebersetzt -- ein neuer Begriff bei sonst
    gleicher Quelle sendet nur den geaenderten ``begriffe``-Rohtext und den
    neuen Begriff, nicht ``kernthema``/``hauptthema`` oder die schon
    bekannten Begriffe."""
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "fixed")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Home, Work")
    klm = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    assert len(klm.aufrufe) == 1
    erster_aufruf = json.loads(klm.aufrufe[0]["nutzer"])
    assert set(erster_aufruf) == {
        "begriffe", "kernthema", "hauptthema",
        uebersetzung.begriff_schluessel("Home"), uebersetzung.begriff_schluessel("Work"),
    }

    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Home, Work, Market")
    assert uebersetzung.aktualisiere(conn, klm, einst, CHAT) is True
    assert len(klm.aufrufe) == 2
    zweiter_aufruf = json.loads(klm.aufrufe[1]["nutzer"])
    # Mutation Check: ohne Wiederverwendung staende hier zusaetzlich
    # "kernthema", "hauptthema", "Home" und "Work" -- hier nur, was sich
    # wirklich geaendert hat.
    assert zweiter_aufruf == {
        "begriffe": "Home, Work, Market",
        uebersetzung.begriff_schluessel("Market"): "Market",
    }

    felder = json.loads(repo.hole_uebersetzung(conn, CHAT)["felder"])
    assert felder["kernthema"] == "EN:fixed"  # wiederverwendet, nicht neu gesendet
    assert felder[uebersetzung.begriff_schluessel("Home")] == "EN:Home"
    assert felder[uebersetzung.begriff_schluessel("Work")] == "EN:Work"
    assert felder[uebersetzung.begriff_schluessel("Market")] == "EN:Market"


def test_aktualisiere_haeppchen_schlaegt_fehl_cache_bleibt_alt(conn, einst):
    """Scheitert ein Haeppchen endgueltig (alle Wiederholungen von
    ``klm.schema`` aufgebraucht), wird der Cache NICHT geschrieben -- alt
    bleibt alt stehen, kein teilweise uebersetzter Zwischenstand. Der
    naechste Lauf setzt mit demselben offenen Schluessel an, weil der Cache
    unveraendert ist."""
    repo.setze_arbeitsstand(conn, CHAT, "kernthema", "belonging")
    klm = _FakeKlm()
    uebersetzung.aktualisiere(conn, klm, einst, CHAT)
    alte_zeile = dict(repo.hole_uebersetzung(conn, CHAT))

    repo.setze_figur(conn, CHAT, "Mira", "a student")
    klm_ausfall = _FakeKlm(fehler_bei_aufruf=[0])
    with pytest.raises(_Ausfall):
        uebersetzung.aktualisiere(conn, klm_ausfall, einst, CHAT)
    assert len(klm_ausfall.aufrufe) == 1
    assert json.loads(klm_ausfall.aufrufe[0]["nutzer"]) == {"figur_0": "Mira"}

    # Mutation Check: ohne "alles oder nichts" stuende hier bereits die neue
    # (unvollstaendige) Zeile oder ein geaenderter quelle_hash.
    nach_ausfall = dict(repo.hole_uebersetzung(conn, CHAT))
    assert nach_ausfall == alte_zeile

    klm_erfolg = _FakeKlm()
    assert uebersetzung.aktualisiere(conn, klm_erfolg, einst, CHAT) is True
    assert len(klm_erfolg.aufrufe) == 1
    assert json.loads(klm_erfolg.aufrufe[0]["nutzer"]) == {"figur_0": "Mira"}
    felder = json.loads(repo.hole_uebersetzung(conn, CHAT)["felder"])
    assert felder["kernthema"] == "EN:belonging"  # wiederverwendet
    assert felder["figur_0"] == "EN:Mira"


def test_aktualisiere_hash_bleibt_ueber_alle_schluessel_trotz_haeppchen(conn, einst):
    """``quelle_hash`` bleibt ein Hash ueber ALLE Segmente (``alles oder
    nichts beim Lesen``, s. Moduldocstring) -- das Haeppchen-Schreiben
    darf diese Semantik nicht veraendern, sonst erkennt ``englisch()``
    eine teilweise uebersetzte Quelle faelschlich als passend."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", _begriffe(20))
    klm = _FakeKlm()
    uebersetzung.aktualisiere(conn, klm, einst, CHAT)
    stand = dict(repo.hole_arbeitsstand(conn, CHAT) or {})
    erwartet = uebersetzung.quelle_hash(stand, [], [])
    zeile = repo.hole_uebersetzung(conn, CHAT)
    assert zeile["quelle_hash"] == erwartet
    assert uebersetzung.englisch({
        "arbeitsstand": stand, "figuren": [], "interview_kurzformen": [],
        "uebersetzung": {"quelle_hash": zeile["quelle_hash"],
                          "felder": json.loads(zeile["felder"])},
    }) == json.loads(zeile["felder"])


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

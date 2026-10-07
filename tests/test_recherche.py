"""Internet-Recherche (Karte t_c5117c91): Fragenvorschlag, Suchanfragen,
Kartenbau mit Zitat-Verifikation -- Fachlogik, kein echtes Netz.

Jeder Test nennt den Mutanten, gegen den er faellt, im Docstring/Kommentar."""

import pytest

from interview_theater import db, recherche, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class LLMAttrappe:
    """Ersetzt interview_theater.llm.LLM: zaehlt Aufrufe, liefert ein
    vorbereitetes Ergebnis je ``art``."""

    def __init__(self, ergebnisse: dict):
        self.ergebnisse = ergebnisse
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        self.aufrufe.append((art, nutzer))
        return self.ergebnisse[art]


# --- Suchanfragen: nie aus dem Transkript -----------------------------------


def test_suchanfragen_kommen_nur_aus_der_frage():
    anfragen = recherche.baue_suchanfragen("When was the city founded?")
    assert anfragen
    assert all("When was the city founded?" in a or a for a in anfragen)
    assert len(anfragen) <= 3


def test_suchanfragen_sind_leer_ohne_frage():
    assert recherche.baue_suchanfragen("") == []


def test_themen_tragen_nie_das_belegzitat(conn):
    """Mutant: _themen() liest 'beleg_zitat' statt 'thema' -- faellt hier,
    weil das einzigartige Token NUR im Zitat steht, nie im Thema."""
    aufnahme_id = repo.lege_interview_an(conn, CHAT)
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Zusammenfassung.",
        [{"thema": "Family", "kurz": "Family", "beleg_zitat": "XYZZY77 said the family moved.", "zitat_geprueft": 1}],
    )
    themen = recherche._themen(conn, CHAT)
    assert themen == ["Family"]
    assert "XYZZY77" not in " ".join(themen)


def test_nutzertext_fragen_enthaelt_kein_token_aus_dem_transkript(conn):
    """Der Produkt-Test der Karte: ein Transkript mit einzigartigem Token
    darf in keiner generierten Suchanfrage auftauchen. Mutant: der
    Nutzertext fuer den Fragenvorschlag haengt das Rohtranskript an."""
    aufnahme_id = repo.lege_interview_an(conn, CHAT)
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE id = ?",
        ("My unique token is QWERTY42 and I never told anyone.", aufnahme_id),
    )
    conn.commit()
    repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Summary without the token.",
        [{"thema": "Migration", "kurz": "Migration", "beleg_zitat": "QWERTY42 never told anyone", "zitat_geprueft": 1}],
    )
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "A small town, today.")

    nutzertext = recherche.baue_nutzertext_fragen(conn, CHAT)

    assert "QWERTY42" not in nutzertext
    assert "Migration" in nutzertext


def test_schlage_fragen_vor_liefert_hoechstens_drei_fragen(conn):
    klm = LLMAttrappe({
        "recherche": {"fragen": ["Q1?", "Q2?", "Q3?", "Q4?"]},
    })
    fragen = recherche.schlage_fragen_vor(klm, conn, None, CHAT)
    assert fragen == ["Q1?", "Q2?", "Q3?"]


# --- Kartenbau: nur verifizierte Aussagen -----------------------------------


SEITEN = [
    {"url": "https://example.org/a", "title": "Example A",
     "content": "The city was founded in 1850 by settlers.",
     "raw_content": "The city was founded in 1850 by settlers."},
    {"url": "https://example.org/b", "title": "Example B",
     "content": "Totally unrelated content about weather.",
     "raw_content": "Totally unrelated content about weather."},
]


def _suche_fn(treffer):
    def _suche(query, anzahl):
        return treffer
    return _suche


def _hole_fn(seiten_nach_url):
    def _hole(url):
        return seiten_nach_url.get(url)
    return _hole


def test_starte_speichert_nur_verifizierte_aussagen(conn):
    """Mutant: zitat.pruefe() wird nicht aufgerufen -- die unbelegte Aussage
    (Snippet aus Seite B kommt gar nicht in raw_content vor) landete dann
    trotzdem in der Karte."""
    klm = LLMAttrappe({
        "recherche": {"aussagen": [
            {"text": "The city was founded in 1850.",
             "beleg": "founded in 1850 by settlers", "quelle_index": 0},
            {"text": "It rains a lot.",
             "beleg": "this snippet does not appear anywhere", "quelle_index": 1},
        ]},
    })
    treffer = [{"title": "Example A", "url": "https://example.org/a", "description": ""},
               {"title": "Example B", "url": "https://example.org/b", "description": ""}]
    seiten_nach_url = {s["url"]: s for s in SEITEN}

    recherche_id = recherche.starte(
        klm, conn, None, CHAT, "When was the city founded?",
        suche_fn=_suche_fn(treffer), hole_fn=_hole_fn(seiten_nach_url),
    )

    gespeichert = repo.hole_recherche(conn, CHAT, recherche_id)
    assert "1850" in gespeichert["ergebnis_text"]
    assert "rains" not in gespeichert["ergebnis_text"]
    assert len(gespeichert["quellen"]) == 1
    assert gespeichert["quellen"][0]["url"] == "https://example.org/a"


def test_starte_liefert_none_ohne_jeden_verifizierten_claim(conn):
    klm = LLMAttrappe({
        "recherche": {"aussagen": [
            {"text": "It rains a lot.",
             "beleg": "this snippet does not appear anywhere", "quelle_index": 0},
        ]},
    })
    treffer = [{"title": "Example A", "url": "https://example.org/a", "description": ""}]
    seiten_nach_url = {s["url"]: s for s in SEITEN}

    recherche_id = recherche.starte(
        klm, conn, None, CHAT, "Irrelevant question?",
        suche_fn=_suche_fn(treffer), hole_fn=_hole_fn(seiten_nach_url),
    )

    assert recherche_id is None
    assert repo.hole_recherchen(conn, CHAT) == []


def test_starte_liefert_none_ohne_treffer(conn):
    recherche_id = recherche.starte(
        LLMAttrappe({}), conn, None, CHAT, "Question?",
        suche_fn=_suche_fn([]), hole_fn=_hole_fn({}),
    )
    assert recherche_id is None

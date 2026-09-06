"""Die Massnahmen 1 und 3 aus ``docs/analyse-phase5-chaos-2026-09-06.md``.

**1 -- USA-Handler prueft die Phase, bevor ein gemerkter Auftrag laeuft.**
Gemessener Live-Fall: nach der USA-Einwilligung startete in Phase 6 der
gemerkte Einzelszenen-Auftrag ("Schreib Szene 1."), und der Zweig darunter,
der die durchgehende Kurzgeschichte anbietet, war damit unerreichbar.

**3 -- Knopf "Zufaellig zuordnen".** Die Zuordnung Interview -> Figur
entstand bis dahin nur als Nebenprodukt der Stilwahl: ein Modellaufruf je
Figur (gemessen 12 Laeufe, 718 s) -- und trotzdem blieben Figuren ohne
Quelle. Der Knopf erledigt sie in einem Druck, ohne Modell.

Alle Daten sind erfunden. Kein Interviewinhalt, keine Klarnamen.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, szene


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.naechste_message_id = 400

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    @property
    def texte(self):
        return [t for _, t in self.gesendet]

    @property
    def knopftexte(self):
        return [b for _, _, leiste in self.knoepfe for b, _ in leiste]


class LLMWaechter:
    """Ein Sprachmodell, das nie gerufen werden darf (Zusage 2)."""

    def __init__(self):
        self.aufrufe = 0

    def prosa(self, *_a, **_kw):
        self.aufrufe += 1
        raise AssertionError("Modellaufruf im Knopf-Handler")

    def schema(self, *_a, **_kw):
        self.aufrufe += 1
        raise AssertionError("Modellaufruf im Knopf-Handler")


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    szene._sperren.clear()
    yield
    szene._sperren.clear()


def _druecke(conn, tg, einst, beschriftung, klm=None, chat_id=1, message_id=777):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                knoepfe.behandle(
                    conn, tg, klm, einst,
                    {
                        "callback_query_id": "q",
                        "data": daten,
                        "chat_id": chat_id,
                        "chat_titel": "Testgruppe",
                        "message_id": message_id,
                    },
                )
                return daten
    raise AssertionError(
        f"Knopf {beschriftung!r} steht nicht im Chat: {tg.knopftexte}"
    )


# --- Massnahme 1: USA-Handler ---------------------------------------------


def _vorbereitet_fuer_usa(conn, phase: int, chat_id=1):
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ort: Steg, Zeit: abends")
    repo.setze_arbeitsstand(conn, chat_id, "geschichte", "Sie geht, er bleibt.")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    phasen.setze(conn, chat_id, phase, "test")
    repo.merke_szene_usa_angeboten(conn, chat_id, "Schreib Szene 1.")


def test_usa_ja_in_phase_6_bietet_die_kurzgeschichte_statt_der_einzelszene(
    conn, einst, tg
):
    """Der Kern des Ablauffehlers: in Phase 6 gehoert an diese Stelle der
    Knopf, aus dem der Prosa-Lauf startet -- nicht der gemerkte
    Einzelszenen-Auftrag."""
    _vorbereitet_fuer_usa(conn, knoepfe.PHASE_SZENEN)
    knoepfe.biete_szene_usa(conn, tg, 1)
    waechter = LLMWaechter()

    _druecke(conn, tg, einst, knoepfe._TEXT_USA_JA_KNOPF, klm=waechter)

    assert waechter.aufrufe == 0
    assert knoepfe._TEXT_KURZGESCHICHTE_BEREIT in tg.texte
    # Der gemerkte Einzelauftrag ist verbraucht, nicht liegengeblieben.
    assert repo.hole_und_loesche_offenen_szenenauftrag(conn, 1) in (None, "")


def test_usa_ja_vor_phase_6_startet_den_gemerkten_auftrag(conn, einst, tg):
    """Der bisherige Weg bleibt: in Phase 5 laeuft der gemerkte Auftrag, wie
    seit dem 05.09.2026 zugesagt."""
    _vorbereitet_fuer_usa(conn, knoepfe.PHASE_SCHAERFUNG)
    knoepfe.biete_szene_usa(conn, tg, 1)
    gestartet = []

    from interview_theater import szene as szene_modul

    echt = szene_modul.starte
    szene_modul.starte = lambda *a, **kw: gestartet.append(a[-1])
    try:
        _druecke(conn, tg, einst, knoepfe._TEXT_USA_JA_KNOPF)
    finally:
        szene_modul.starte = echt

    assert gestartet == ["Schreib Szene 1."]
    assert knoepfe._TEXT_KURZGESCHICHTE_BEREIT not in tg.texte


def test_usa_nein_setzt_false_und_bleibt_beim_phasenweg(conn, einst, tg):
    """Der Fallstrick aus AGENTS.md bleibt geprueft: ein "nein" ist keine
    Zustimmung zur Datenuebermittlung."""
    _vorbereitet_fuer_usa(conn, knoepfe.PHASE_SZENEN)
    knoepfe.biete_szene_usa(conn, tg, 1)

    _druecke(conn, tg, einst, knoepfe._TEXT_USA_NEIN_KNOPF)

    gruppe = repo.hole_gruppe(conn, 1)
    assert str(gruppe["szene_usa_bestaetigt_am"] or "").startswith("nein")


# --- Massnahme 3: Knopf "Zufaellig zuordnen" ------------------------------


def _figuren_und_interviews(conn, figuren=4, interviews=2, chat_id=1):
    for n in range(1, figuren + 1):
        repo.setze_figur(conn, chat_id, f"Figur {n}", f"Beschreibung {n}")
    ids = []
    for n in range(1, interviews + 1):
        ids.append(repo.lege_aufnahme_an(conn, chat_id, 100 + n, "lang", "sprache"))
    return ids


def test_zufallszuordnung_belegt_jede_offene_figur_ohne_modell(conn):
    aufnahmen = _figuren_und_interviews(conn, figuren=5, interviews=2)

    anzahl, interviews = knoepfe.ordne_figuren_zufaellig_zu(conn, 1)

    assert anzahl == 5
    assert interviews == 2
    for figur in repo.figuren(conn, 1):
        assert figur["quelle_aufnahme_id"] in aufnahmen


def test_ein_interview_darf_mehrere_figuren_speisen(conn):
    _figuren_und_interviews(conn, figuren=4, interviews=1)

    anzahl, interviews = knoepfe.ordne_figuren_zufaellig_zu(conn, 1)

    assert (anzahl, interviews) == (4, 1)
    quellen = {f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)}
    assert len(quellen) == 1


def test_bestehende_zuordnung_bleibt_unangetastet(conn):
    aufnahmen = _figuren_und_interviews(conn, figuren=3, interviews=2)
    fest = repo.figuren(conn, 1)[0]
    repo.setze_figur_quelle(conn, fest["id"], aufnahmen[0])

    anzahl, _ = knoepfe.ordne_figuren_zufaellig_zu(conn, 1)

    assert anzahl == 2
    frisch = {f["name"]: f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)}
    assert frisch[fest["name"]] == aufnahmen[0]


def test_zuordnung_ist_idempotent(conn):
    _figuren_und_interviews(conn, figuren=4, interviews=2)
    knoepfe.ordne_figuren_zufaellig_zu(conn, 1)
    vorher = {f["id"]: f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)}

    assert knoepfe.ordne_figuren_zufaellig_zu(conn, 1) == (0, 0)

    assert {f["id"]: f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)} == vorher


def test_ohne_interview_passiert_nichts(conn):
    _figuren_und_interviews(conn, figuren=3, interviews=0)

    assert knoepfe.ordne_figuren_zufaellig_zu(conn, 1) == (0, 0)
    assert all(not f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1))


def test_knopf_steht_in_der_leiste_beim_abschluss_der_figuren(conn, tg):
    _figuren_und_interviews(conn, figuren=3, interviews=2)

    knoepfe._schliesse_figuren_ab(conn, tg, 1)

    assert knoepfe._TEXT_FIGUREN_ZUFALL_KNOPF in tg.knopftexte


def test_knopf_fehlt_wenn_es_nichts_zuzuordnen_gibt(conn, tg):
    _figuren_und_interviews(conn, figuren=2, interviews=1)
    knoepfe.ordne_figuren_zufaellig_zu(conn, 1)

    knoepfe._schliesse_figuren_ab(conn, tg, 1)

    assert knoepfe._TEXT_FIGUREN_ZUFALL_KNOPF not in tg.knopftexte


def test_knopfdruck_ordnet_zu_ruft_kein_modell_und_journalisiert(conn, einst, tg):
    _figuren_und_interviews(conn, figuren=4, interviews=2)
    knoepfe._schliesse_figuren_ab(conn, tg, 1)
    waechter = LLMWaechter()

    _druecke(conn, tg, einst, knoepfe._TEXT_FIGUREN_ZUFALL_KNOPF, klm=waechter)

    assert waechter.aufrufe == 0
    assert all(f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1))
    assert any("zufaellig zugeordnet" in z["text"] for z in repo.journal(conn, 1))
    # Sprachstile entstehen dabei ausdruecklich NICHT.
    assert all(not (f["sprachstil"] or "").strip() for f in repo.figuren(conn, 1))


def test_zweiter_druck_wirkt_nicht_noch_einmal(conn, einst, tg):
    """Zusage 3: ``repo.beanspruche_knopf`` klemmt den zweiten Druck ab."""
    _figuren_und_interviews(conn, figuren=4, interviews=2)
    knoepfe._schliesse_figuren_ab(conn, tg, 1)

    daten = _druecke(conn, tg, einst, knoepfe._TEXT_FIGUREN_ZUFALL_KNOPF)
    vorher = {f["id"]: f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)}
    knoepfe.behandle(
        conn, tg, None, einst,
        {
            "callback_query_id": "q2", "data": daten, "chat_id": 1,
            "chat_titel": "Testgruppe", "message_id": 777,
        },
    )

    assert tg.beantwortet[-1][1] == knoepfe._TEXT_SCHON_BENUTZT
    assert {f["id"]: f["quelle_aufnahme_id"] for f in repo.figuren(conn, 1)} == vorher
    journale = [z for z in repo.journal(conn, 1) if "zufaellig zugeordnet" in z["text"]]
    assert len(journale) == 1


def test_callback_data_bleibt_unter_der_grenze(conn, tg):
    """Zusage 1: der Knopf traegt nur ``k:<id>``."""
    _figuren_und_interviews(conn, figuren=3, interviews=2)

    knoepfe._schliesse_figuren_ab(conn, tg, 1)

    for _, _, leiste in tg.knoepfe:
        for _, daten in leiste:
            assert len(daten.encode("utf-8")) <= 64

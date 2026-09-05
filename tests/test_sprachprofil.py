"""Das Sprachprofil je Figur (interview_theater/sprachprofil.py).

Birk, 05.09.2026: *"Zitate als Few-Shots fuer die Sprechweise je Figur, das
ist das Wichtigste."* Geprueft wird hier vor allem eines: dass **nichts
gespeichert wird, was nicht woertlich im Transkript steht** -- ein erfundenes
Zitat ginge als Few-Shot in jeden weiteren Szenenlauf ein.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe mit einer
``.schema()``-Methode, die eine vorbereitete Antwort liefert.
"""

import pytest

from interview_theater import repo, sprachprofil

TRANSKRIPT = (
    "Sara: Erzaehl doch mal.\n"
    "Pola: Wir haben zusammen gepogt, getanzt. Halt so, ne? Und dann, weiss "
    "nicht, dann war das vorbei.\n"
    "Sara: Und danach?\n"
    "Pola: Danach halt nichts mehr."
)

ANTWORT = {
    "profil": (
        "Kurze Saetze, oft nur ein Halbsatz.\n"
        "Fuellwoerter: 'halt', 'so', 'ne?'.\n"
        "Bricht ab und faengt neu an."
    ),
    "zitate": [
        "Wir haben zusammen gepogt, getanzt.",
        "Halt so, ne?",
        "Danach halt nichts mehr.",
    ],
}


class LLMAttrappe:
    def __init__(self, antwort=None, fehler=None):
        self._antwort = antwort if antwort is not None else ANTWORT
        self._fehler = fehler
        self.aufrufe = 0
        self.gesehen = {}

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        self.aufrufe += 1
        self.gesehen = {
            "chat_id": chat_id, "system": system, "nutzer": nutzer, "art": art,
            "modell": modell, "temperature": temperature,
        }
        if self._fehler is not None:
            raise self._fehler
        return self._antwort


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self._naechste = 7000

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        self._naechste += 1
        return self._naechste

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def figur(conn):
    """Eine Figur mit zugeordnetem Interview -- der Zustand, in dem der
    Sprachprofil-Aufruf startet."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 100, "lang", "text")
    repo.setze_aufnahme_name(conn, aufnahme_id, "Interview 2")
    repo.setze_transkript(conn, aufnahme_id, TRANSKRIPT)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    zeile = repo.hole_figur(conn, 1, "Pola")
    repo.setze_figur_quelle(conn, zeile["id"], aufnahme_id)
    return zeile["id"]


def test_profil_und_geprueftes_zitat_landen_an_der_figur(conn, einst, figur):
    meldung = sprachprofil.erstelle(LLMAttrappe(), conn, einst, figur)

    zeile = repo.hole_figur(conn, 1, "Pola")
    assert "Fuellwoerter" in zeile["sprachprofil"]
    assert zeile["zitate"].split(repo.ZITAT_TRENNER) == ANTWORT["zitate"]
    assert meldung.startswith("Sprachprofil fuer Pola aus Interview 1:")
    assert "Kurze Saetze" in meldung


def test_erfundene_zitate_fliegen_raus(conn, einst, figur):
    """Dieselbe Pruefung wie beim Verdichter (SPEC § 5, N2): was nicht
    woertlich im Transkript steht, wird nicht gespeichert."""
    klm = LLMAttrappe(antwort={
        "profil": "Kurze Saetze.",
        "zitate": ["Halt so, ne?", "Das habe ich nie gesagt."],
    })

    sprachprofil.erstelle(klm, conn, einst, figur)

    assert repo.hole_figur(conn, 1, "Pola")["zitate"] == "Halt so, ne?"


def test_ohne_ein_einziges_belegtes_zitat_wird_nichts_gespeichert(conn, einst, figur):
    """Ein Profil ohne Zitate waere die Behauptung, so spreche ein Mensch, den
    die Gruppe kennt -- und im Szenen-Prompt haengt die Stimme der Figur genau
    an diesen Saetzen."""
    klm = LLMAttrappe(antwort={"profil": "Redet viel.", "zitate": ["frei erfunden"]})

    meldung = sprachprofil.erstelle(klm, conn, einst, figur)

    zeile = repo.hole_figur(conn, 1, "Pola")
    assert zeile["sprachprofil"] is None and zeile["zitate"] is None
    assert "keinen Satz woertlich belegen" in meldung
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert "zitat_ungeprueft" in arten


def test_hoechstens_fuenf_zitate(conn, einst, figur):
    klm = LLMAttrappe(antwort={
        "profil": "Kurz.",
        "zitate": ["Halt so, ne?"] * 3 + ["Danach halt nichts mehr."],
    })

    sprachprofil.erstelle(klm, conn, einst, figur)

    # Dubletten zaehlen nicht doppelt: derselbe Satz waere derselbe Few-Shot.
    zitate = repo.hole_figur(conn, 1, "Pola")["zitate"].split(repo.ZITAT_TRENNER)
    assert zitate == ["Halt so, ne?", "Danach halt nichts mehr."]
    assert len(zitate) <= sprachprofil.MAX_ZITATE


def test_ohne_transkript_sagt_der_bot_das(conn, einst):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 101, "lang", "text")
    repo.setze_aufnahme_name(conn, aufnahme_id, "Interview 3")
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    repo.setze_figur_quelle(conn, figur_id, aufnahme_id)
    klm = LLMAttrappe()

    meldung = sprachprofil.erstelle(klm, conn, einst, figur_id)

    assert klm.aufrufe == 0, "ohne Transkript wird das Modell gar nicht gefragt"
    assert "kein Transkript" in meldung


def test_ohne_zugeordnetes_interview_passiert_nichts(conn, einst):
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    klm = LLMAttrappe()

    assert sprachprofil.erstelle(klm, conn, einst, figur_id) is None
    assert klm.aufrufe == 0


def test_laeuft_mit_dem_erkennermodell_ohne_reasoning(conn, einst, figur):
    """Extraktion, kein Abwaegen: gemma und ``LLM.schema`` (reasoning_effort
    'none' ist dessen Vorgabe) -- nicht das Gespraechsmodell."""
    klm = LLMAttrappe()

    sprachprofil.erstelle(klm, conn, einst, figur)

    assert klm.gesehen["modell"] == einst.erkenner_modell
    assert klm.gesehen["modell"] != einst.llm_modell
    assert klm.gesehen["art"] == "sprachprofil"


def test_der_nutzertext_ist_das_transkript_und_sonst_nichts(conn, einst, figur):
    klm = LLMAttrappe()

    sprachprofil.erstelle(klm, conn, einst, figur)

    assert klm.gesehen["nutzer"] == TRANSKRIPT
    assert "Pola" not in klm.gesehen["system"]


def test_das_journal_haelt_die_zuordnung_fest(conn, einst, figur):
    sprachprofil.erstelle(LLMAttrappe(), conn, einst, figur)

    eintraege = [(e["art"], e["text"]) for e in repo.journal(conn, 1)]
    assert ("entschieden", "Sprachprofil fuer Pola aus Interview 1") in eintraege


def test_starte_laeuft_im_thread_und_meldet_sich(conn, einst, tg, figur):
    thread = sprachprofil.starte(conn, tg, LLMAttrappe(), einst, 1, [figur])
    assert thread is not None
    thread.join(timeout=10)

    assert not thread.is_alive()
    assert tg.texte[0].startswith("Sprachprofil fuer Pola aus Interview 1:")
    # Wie jede Bot-Zeile: sie steht im Verlaufsfenster des naechsten Zugs.
    texte = [n["text"] for n in repo.letzte_nachrichten(conn, 1) if n["ist_bot"]]
    assert any(t.startswith("Sprachprofil fuer Pola") for t in texte)


def test_starte_ohne_figuren_stoesst_nichts_an(conn, einst, tg):
    assert sprachprofil.starte(conn, tg, LLMAttrappe(), einst, 1, []) is None
    assert tg.gesendet == []


def test_ein_fehlschlag_bleibt_still_und_reisst_die_andere_figur_nicht_mit(
    conn, einst, tg, figur
):
    """Die Gruppe kann einen Modellfehler nicht beheben und wartet nicht
    darauf -- also erfaehrt sie nichts davon (SPEC § 11.1). Der Vorfall haelt
    ihn fuers Dashboard fest."""
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell weg"))

    thread = sprachprofil.starte(conn, tg, klm, einst, 1, [figur])
    thread.join(timeout=10)

    assert tg.gesendet == []
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert "sprachprofil_fehlgeschlagen" in arten

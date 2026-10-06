"""Aufgabe 7 (Padua Phase 1+2 Umbau): ``interview_theater.diskussion`` -- die
EINE Verdichtung der Hintergrund-Diskussion am Ende von Phase 1.

Gebaut auf demselben Sperren-Muster wie ``brainstorm.py``
(``tests/test_brainstorm.py``) und demselben Zitatschutz wie ``verdichter.py``
(``tests/test_zitat.py``)."""

import threading
import time

import pytest

from interview_theater import db, diskussion, repo, workshop

CHAT = 1


@pytest.fixture(autouse=True)
def diskussion_aktiv_vorgabe(monkeypatch):
    """Ohne Profil ist ``workshop.diskussion_aktiv()`` False (Dortmund-
    Vorgabe) -- die meisten Tests hier wollen den aktiven Fall pruefen und
    schalten ihn deshalb an; der eine Test, der die Abschaltung selbst
    prueft, ueberschreibt das wieder."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)


def _segment_an(conn, message_id: int, transkript: str, chat_id: int = CHAT) -> None:
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", diskussion=True,
    )
    conn.execute(
        "UPDATE aufnahme SET transkript = ?, status = 'fertig' WHERE id = ?",
        (transkript, aufnahme_id),
    )
    conn.commit()


def _warte_bis(bedingung, timeout=5.0) -> None:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


class _KLM:
    """Dieselbe Form wie ``tests/test_modellwahl.py::_KLM`` -- zaehlt Aufrufe
    und beantwortet jeden mit einer festen Antwort."""

    def __init__(self, antwort: str = "NICHTS"):
        self.aufrufe = 0
        self._antwort = antwort

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"antwort": self._antwort}


# ---------------------------------------------------------------------------
# Der Zitatfilter (_gefiltert)
# ---------------------------------------------------------------------------


def test_gefiltert_behaelt_nur_die_zeile_mit_echtem_zitat():
    transkript = 'Jemand sagte: "Das echte Zitat aus dem Transkript".'
    antwort = (
        'Thema A: "Das echte Zitat aus dem Transkript" kam vor.\n'
        'Thema B: "Ein frei erfundenes Zitat" kam nicht vor.'
    )
    gefiltert = diskussion._gefiltert(antwort, transkript)
    assert "Das echte Zitat aus dem Transkript" in gefiltert
    assert "frei erfundenes Zitat" not in gefiltert


def test_gefiltert_behaelt_zeilen_ohne_zitat():
    transkript = "Irgendein Transkripttext."
    antwort = "Eine Zeile ganz ohne Anfuehrungszeichen."
    assert diskussion._gefiltert(antwort, transkript) == antwort


@pytest.mark.parametrize("wort", ["NICHTS", "nichts", "  Nichts  ", "NOTHING", "none"])
def test_gefiltert_erkennt_die_leer_antworten_case_und_whitespace_unabhaengig(wort):
    assert diskussion._gefiltert(wort, "irgendein Transkript") == ""


def test_gefiltert_wirft_nur_zeilen_mit_schlechtem_zitat_weg_nicht_die_ganze_antwort():
    transkript = 'Erstens steht hier: "Guter Satz". Zweitens auch.'
    antwort = (
        '- "Guter Satz" ist echt.\n'
        '- "Ein zweiter, komplett erfundener Satz" ist es nicht.\n'
        '- Noch eine Zeile ohne jedes Zitat.'
    )
    gefiltert = diskussion._gefiltert(antwort, transkript)
    zeilen = gefiltert.splitlines()
    assert any("Guter Satz" in z for z in zeilen)
    assert not any("komplett erfundener" in z for z in zeilen)
    assert any("ohne jedes Zitat" in z for z in zeilen)


# ---------------------------------------------------------------------------
# _nutzertext ist isoliert: nur das Transkript, sonst nichts
# ---------------------------------------------------------------------------


def test_nutzertext_nimmt_nur_das_transkript_entgegen():
    text = diskussion._nutzertext("Genau dieser Satz und sonst nichts.")
    assert "Genau dieser Satz und sonst nichts." in text


def test_nutzertext_kopf_ist_deutsch_ohne_profil():
    text = diskussion._nutzertext("Beispielsatz.")
    assert text.startswith("Das Transkript der Diskussion:")


def test_nutzertext_kopf_ist_englisch_in_padua(monkeypatch):
    """P1-L8/P2-N2 (Prompt-Check Padua P1/P2, Abschnitt 9): der Nutzerteil
    trug den deutschen Kopf auch in Padua (englisches Profil) -- jetzt ueber
    die Sprachschicht wie ``begriffsboard._TRANSKRIPT_KOPF``."""
    from interview_theater import sprache

    monkeypatch.setattr(sprache, "code", lambda: "en")
    text = diskussion._nutzertext("Example sentence.")
    assert text.startswith("The transcript of the discussion:")
    assert "Das Transkript" not in text


# ---------------------------------------------------------------------------
# starte(): die Weichen
# ---------------------------------------------------------------------------


def test_starte_tut_nichts_ohne_klm(conn, einst):
    _segment_an(conn, 1, "Ein Gedanke.")
    diskussion.starte(conn, None, None, einst, CHAT)
    assert repo.diskussion_verdichtung_text(conn, CHAT) is None
    # Keine Sperre haengen geblieben.
    assert diskussion.versuche_start(CHAT) is True
    diskussion.beende(CHAT)


def test_starte_tut_nichts_wenn_diskussion_nicht_aktiv(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    _segment_an(conn, 1, "Ein Gedanke.")
    klm = _KLM()
    diskussion.starte(conn, None, klm, einst, CHAT)
    assert klm.aufrufe == 0
    assert repo.diskussion_verdichtung_text(conn, CHAT) is None
    assert diskussion.versuche_start(CHAT) is True
    diskussion.beende(CHAT)


def test_starte_bei_leerem_transkript_ruft_kein_modell_und_gibt_die_sperre_frei(conn, einst):
    """Die Sperre muss auch auf diesem fruehen Rueckweg zurueckgegeben werden
    -- sonst bliebe diese Gruppe fuer immer 'laeuft gerade'."""
    klm = _KLM()
    diskussion.starte(conn, None, klm, einst, CHAT)
    assert klm.aufrufe == 0
    assert repo.diskussion_verdichtung_text(conn, CHAT) is None
    # Die entscheidende Probe: ein zweiter Aufruf muss die Sperre bekommen.
    assert diskussion.versuche_start(CHAT) is True
    diskussion.beende(CHAT)


def test_doppelter_start_ruft_das_modell_nur_einmal_auf(conn, einst):
    """Schwarzkasten-Pruefung des Kartenversprechens "genau einmal": zwei
    unmittelbar aufeinanderfolgende ``starte``-Aufrufe duerfen nur einen
    Modellaufruf ausloesen -- die Sperre wird synchron in ``starte`` selbst
    gesetzt (vor dem Thread-Start), ein zweiter Aufruf kurz danach sieht sie
    deshalb deterministisch schon belegt."""
    _segment_an(conn, 1, "Ein Gedanke im Hintergrund.")
    klm = _KLM()
    diskussion.starte(conn, None, klm, einst, CHAT)
    diskussion.starte(conn, None, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe >= 1)
    time.sleep(0.05)  # Zeit fuer einen etwaigen zweiten, unerwuenschten Lauf
    assert klm.aufrufe == 1


def test_starte_speichert_die_gefilterte_antwort(conn, einst):
    transkript = 'Jemand sagte: "Ein belegbarer Gedanke zur Diskussion".'
    _segment_an(conn, 1, transkript)
    klm = _KLM(antwort='Thema: "Ein belegbarer Gedanke zur Diskussion" kam vor.')
    diskussion.starte(conn, None, klm, einst, CHAT)
    _warte_bis(lambda: repo.diskussion_verdichtung_text(conn, CHAT) is not None)
    text = repo.diskussion_verdichtung_text(conn, CHAT)
    assert "Ein belegbarer Gedanke zur Diskussion" in text


def test_starte_speichert_nichts_bei_leerer_gefilterter_antwort(conn, einst):
    _segment_an(conn, 1, "Ein Transkript ohne jedes brauchbare Zitat.")
    klm = _KLM(antwort="NICHTS")
    diskussion.starte(conn, None, klm, einst, CHAT)
    _warte_bis(lambda: diskussion.versuche_start(CHAT) is True)
    diskussion.beende(CHAT)
    assert repo.diskussion_verdichtung_text(conn, CHAT) is None


def test_starte_merkt_sovereign_als_modell_ohne_claude(conn, einst):
    transkript = 'Hier steht: "Ein woertlich belegtes Statement".'
    _segment_an(conn, 1, transkript)
    klm = _KLM(antwort='"Ein woertlich belegtes Statement" wurde gesagt.')
    diskussion.starte(conn, None, klm, einst, CHAT)
    _warte_bis(lambda: repo.diskussion_verdichtung_text(conn, CHAT) is not None)
    zeile = conn.execute(
        "SELECT modell FROM diskussion_verdichtung WHERE chat_id = ?", (CHAT,),
    ).fetchone()
    assert zeile["modell"] == "sovereign"


def test_ein_gescheiterter_lauf_gibt_die_sperre_frei_und_schreibt_einen_vorfall(
    conn, einst,
):
    _segment_an(conn, 1, "Ein Gedanke.")

    class _KaputtesKLM:
        def schema(self, *a, **k):
            raise RuntimeError("simulierter Ausfall")

    diskussion.starte(conn, None, _KaputtesKLM(), einst, CHAT)
    _warte_bis(lambda: diskussion.versuche_start(CHAT) is True)
    diskussion.beende(CHAT)
    vorfall = conn.execute(
        "SELECT art FROM vorfall WHERE art = 'diskussion_verdichtung_fehler'",
    ).fetchone()
    assert vorfall is not None

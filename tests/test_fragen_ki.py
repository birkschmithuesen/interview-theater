"""Aufgabe 12 (Padua Phase 1+2 Umbau): ``interview_theater.fragen_ki`` -- der
isolierte Hintergrundlauf, der beim Eintritt in Phase 2 DREI KI-Fragen je
Begriff erzeugt, BEVOR die Gruppe eigene Fragen eingibt.

Gebaut auf demselben Sperren-/Thread-Muster wie ``diskussion.py``
(``tests/test_diskussion.py``) -- der strukturbildende Unterschied ist die
Isolation: ``_nutzertext`` darf ``conn``/``chat_id`` in der Signatur gar
nicht erst kennen, siehe AB-AENDERUNG-PHASE2.md Punkt 2/7 und die
Korrektur in KORREKTUR-PHASE2-KEIN-KNOPF.md (kein "fertig"-Knopf -- dieser
Lauf selbst bleibt rein code-/thread-getrieben)."""

import inspect
import time
from datetime import datetime

import pytest

from interview_theater import fragen_ki, repo, workshop
from interview_theater.knoepfe import fragen

CHAT = 1

#: Steht fuer "eine eigene Frage der Gruppe" -- darf unter keinen Umstaenden
#: im Nutzertext des isolierten KI-Laufs auftauchen.
PLANTED_OWN_QUESTION = "PLANTED_OWN_QUESTION_MARKER: Did you ever own a suitcase?"


@pytest.fixture(autouse=True)
def fragen_ab_aktiv_vorgabe(monkeypatch):
    """Ohne Profil ist ``workshop.fragen_ab_aktiv()`` False (Dortmund-
    Vorgabe) -- die meisten Tests hier wollen den aktiven Fall pruefen und
    schalten ihn deshalb an; der eine Test, der die Abschaltung selbst
    prueft, ueberschreibt das wieder."""
    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: True)


def _warte_bis(bedingung, timeout=5.0) -> None:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


class _KLM:
    """Dieselbe Form wie ``tests/test_diskussion.py::_KLM`` -- zaehlt
    Aufrufe, merkt sich den gesendeten ``nutzer``-Text und beantwortet jeden
    Aufruf mit einer festen Antwort."""

    def __init__(self, antwort: str = "Heimat: Frage eins.\nHeimat: Frage zwei.\nHeimat: Frage drei."):
        self.aufrufe = 0
        self.letzter_nutzer = None
        self._antwort = antwort

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        self.letzter_nutzer = nutzer
        return {"antwort": self._antwort}


class _TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append((chat_id, text))
        return 1

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        # Seit 05.10.2026 traegt der Eintritt in Padua Phase 2 den Knopf
        # "Suggest questions".
        return self.sende(chat_id, text, **kw)


def _setze_begriffe(conn, begriffe: str = "Heimat, Streit", chat_id: int = CHAT) -> None:
    repo.setze_arbeitsstand(conn, chat_id, "begriffe", begriffe)


def _feld(conn, chat_id, feld):
    """``sqlite3.Row`` kennt kein ``.get`` -- dieser Helfer liefert ``None``
    sowohl fuer eine fehlende Zeile als auch fuer ein leeres Feld."""
    zeile = repo.hole_arbeitsstand(conn, chat_id)
    return zeile[feld] if zeile is not None else None


# ---------------------------------------------------------------------------
# _nutzertext ist isoliert: Signatur kennt nur Begriffe + Diskussionstext
# ---------------------------------------------------------------------------


def test_nutzertext_signatur_kennt_weder_conn_noch_chat_id():
    """Strukturelle Isolationsprobe: die Signatur selbst macht es unmoeglich,
    aus dieser Funktion heraus die Datenbank oder den Phase-2-Chat zu
    lesen."""
    parameter = list(inspect.signature(fragen_ki._nutzertext).parameters)
    assert parameter == ["begriffe", "diskussion_text", "begriffe_detail"]
    assert "conn" not in parameter
    assert "chat_id" not in parameter


def test_nutzertext_enthaelt_die_begriffe():
    text = fragen_ki._nutzertext("Heimat, Streit", None)
    assert "Heimat" in text
    assert "Streit" in text


def test_nutzertext_degradiert_graceful_ohne_diskussionstext():
    # Darf nicht crashen, und das Fehlen soll auch nicht als Fehlertext
    # auftauchen.
    text = fragen_ki._nutzertext("Heimat", None)
    assert "Heimat" in text


def test_nutzertext_nimmt_diskussionstext_als_zusatz_auf():
    text = fragen_ki._nutzertext("Heimat", "In der Diskussion kam Umzug auf.")
    assert "Umzug" in text


# ---------------------------------------------------------------------------
# Isolation (a): der gesendete Nutzertext enthaelt nie eine eigene Frage
# ---------------------------------------------------------------------------


def test_starte_sendet_nie_eine_eigene_frage_der_gruppe(conn, einst):
    """Staerkste Isolationsprobe: selbst wenn ``fragen_eigene_vorschlag``
    bereits eine markante eigene Frage traegt (zeitlich kaeme das beim
    echten Ablauf erst NACH diesem Lauf vor -- hier bewusst schon vorab
    gesetzt), darf der gesendete Nutzertext sie nicht enthalten, weil
    ``starte``/``_nutzertext`` sie strukturell gar nicht lesen koennen."""
    _setze_begriffe(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", PLANTED_OWN_QUESTION)

    klm = _KLM()
    tg = _TG()
    fragen_ki.starte(conn, tg, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe >= 1)

    assert klm.letzter_nutzer is not None
    assert PLANTED_OWN_QUESTION not in klm.letzter_nutzer


# ---------------------------------------------------------------------------
# starte(): die Weichen
# ---------------------------------------------------------------------------


def test_starte_tut_nichts_ohne_klm(conn, einst):
    _setze_begriffe(conn)
    fragen_ki.starte(conn, _TG(), None, einst, CHAT)
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert not (zeile and zeile["fragen_ki_vorschlag"])


def test_starte_tut_nichts_wenn_fragen_ab_nicht_aktiv(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: False)
    _setze_begriffe(conn)
    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    assert klm.aufrufe == 0
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert not (zeile and zeile["fragen_ki_vorschlag"])


def test_eintritt_in_phase_ruft_fragen_ki_bei_aktivem_profil(conn, einst, monkeypatch):
    from interview_theater import knoepfe

    aufrufe = []
    monkeypatch.setattr(
        fragen_ki, "starte",
        lambda conn, tg, klm, e, chat_id: aufrufe.append(chat_id),
    )
    knoepfe.eintritt_in_phase(conn, _TG(), object(), einst, CHAT, 2)
    assert aufrufe == [CHAT]


def test_eintritt_in_phase_laesst_fragen_ki_aus_wenn_profil_aus(conn, einst, monkeypatch):
    from interview_theater import knoepfe

    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: False)
    aufrufe = []
    monkeypatch.setattr(
        fragen_ki, "starte",
        lambda conn, tg, klm, e, chat_id: aufrufe.append(chat_id),
    )
    knoepfe.eintritt_in_phase(conn, _TG(), object(), einst, CHAT, 2)
    assert aufrufe == []


def test_eintritt_in_phase_2_feuert_weiterhin_biete_proaktiv(conn, einst, monkeypatch):
    """Regressionswache: die bestehende proaktive Phase-2-Meldung
    (``biete_proaktiv``, der generische ``else``-Zweig) darf durch die neue
    Weiche nicht verschwinden -- weder mit noch ohne das Profil."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import stationen

    aufrufe = []
    monkeypatch.setattr(
        stationen, "biete_proaktiv",
        lambda *a, **k: aufrufe.append(a),
    )
    monkeypatch.setattr(fragen_ki, "starte", lambda *a, **k: None)
    knoepfe.eintritt_in_phase(conn, _TG(), None, einst, CHAT, 2)
    assert len(aufrufe) == 1

    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: False)
    knoepfe.eintritt_in_phase(conn, _TG(), None, einst, CHAT, 2)
    assert len(aufrufe) == 2


def test_doppelter_start_ruft_das_modell_nur_einmal_auf(conn, einst):
    _setze_begriffe(conn)
    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe >= 1)
    time.sleep(0.05)  # Zeit fuer einen etwaigen zweiten, unerwuenschten Lauf
    assert klm.aufrufe == 1


def test_erfolgreicher_lauf_schreibt_vorschlag_und_zeitstempel(conn, einst):
    _setze_begriffe(conn)
    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    _warte_bis(
        lambda: _feld(conn, CHAT, "fragen_ki_vorschlag")
    )
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert "Heimat" in zeile["fragen_ki_vorschlag"]
    assert zeile["fragen_ki_erzeugt_am"]


def test_no_amend_zweiter_lauf_aendert_den_gespeicherten_wert_nicht(conn, einst):
    _setze_begriffe(conn)
    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    _warte_bis(
        lambda: _feld(conn, CHAT, "fragen_ki_vorschlag")
    )
    erster_wert = repo.hole_arbeitsstand(conn, CHAT)["fragen_ki_vorschlag"]
    erste_zeit = repo.hole_arbeitsstand(conn, CHAT)["fragen_ki_erzeugt_am"]

    klm2 = _KLM(antwort="Heimat: Eine ganz andere Frage.")
    fragen_ki.starte(conn, _TG(), klm2, einst, CHAT)
    time.sleep(0.1)

    assert klm2.aufrufe == 0
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert zeile["fragen_ki_vorschlag"] == erster_wert
    assert zeile["fragen_ki_erzeugt_am"] == erste_zeit


# ---------------------------------------------------------------------------
# Ordering (b): KI-Zeitstempel liegt vor einem spaeteren eigenen Zeitstempel
# ---------------------------------------------------------------------------


def test_ki_erzeugt_am_liegt_vor_einem_spaeter_gesetzten_eigenen_zeitstempel(conn, einst):
    """Reale Chronologie, nicht ein Zeichenkettenartefakt (Review-Befund 2,
    Task 12): die urspruengliche Fassung verglich ``repo._jetzt()``
    (Sekundengenauigkeit, endet auf ``+00:00``) gegen ``repo._jetzt_fein()``
    (Mikrosekundengenauigkeit, ``...NNNNNN+00:00``) -- ``'+' < '.'`` in ASCII
    macht den String-Vergleich UNABHAENGIG von der echten Reihenfolge wahr,
    das ``time.sleep(0.01)`` davor war wirkungslos. Jetzt: beide Seiten
    dieselbe Praezision (``repo._jetzt()``), eine echte, gemessene Pause von
    ueber einer Sekunde (garantiert einen anderen Sekundenwert), und der
    Vergleich laeuft ueber geparste ``datetime``-Objekte statt ueber rohe
    Strings -- das waere auch bei ungleicher Praezision noch korrekt. Probe:
    vertauschte man die Schreibreihenfolge der beiden Zeilen unten, wuerde
    die Assertion rot (manuell nachvollzogen, siehe Taskbericht)."""
    _setze_begriffe(conn)
    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    _warte_bis(lambda: _feld(conn, CHAT, "fragen_ki_erzeugt_am"))
    ki_erzeugt_am = repo.hole_arbeitsstand(conn, CHAT)["fragen_ki_erzeugt_am"]

    # Simuliert: die Gruppe schliesst ihre eigenen Fragen spaeter ab -- eine
    # echte, messbare Pause (keine Praezisionsdifferenz im Format).
    time.sleep(1.05)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", repo._jetzt())

    eigene_erstellt_am = repo.hole_arbeitsstand(conn, CHAT)["fragen_eigene_erstellt_am"]
    assert (
        datetime.fromisoformat(ki_erzeugt_am)
        < datetime.fromisoformat(eigene_erstellt_am)
    )


# ---------------------------------------------------------------------------
# Reveal-Aufruf: fragen_modul.versuche_gegenueberstellung (Aufgabe 13,
# noch nicht gebaut -- per monkeypatch mit raising=False antizipiert)
# ---------------------------------------------------------------------------


def test_erfolgreicher_lauf_ruft_versuche_gegenueberstellung_genau_einmal(conn, einst, monkeypatch):
    aufrufe = []

    def fake(conn_arg, tg_arg, chat_id_arg):
        aufrufe.append((conn_arg, tg_arg, chat_id_arg))

    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", fake, raising=False)

    _setze_begriffe(conn)
    klm = _KLM()
    tg = _TG()
    fragen_ki.starte(conn, tg, klm, einst, CHAT)
    _warte_bis(lambda: len(aufrufe) >= 1)

    assert len(aufrufe) == 1
    gesehen_conn, gesehen_tg, gesehen_chat = aufrufe[0]
    assert gesehen_conn is conn
    assert gesehen_tg is tg
    assert gesehen_chat == CHAT


def test_gescheiterter_lauf_ruft_versuche_gegenueberstellung_nicht(conn, einst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(
        fragen, "versuche_gegenueberstellung",
        lambda *a, **k: aufrufe.append(a), raising=False,
    )

    class _KaputtesKLM:
        def schema(self, *a, **k):
            raise RuntimeError("simulierter Ausfall")

    _setze_begriffe(conn)
    fragen_ki.starte(conn, _TG(), _KaputtesKLM(), einst, CHAT)
    _warte_bis(lambda: fragen_ki.versuche_start(CHAT) is True)
    fragen_ki.beende(CHAT)
    assert aufrufe == []


def test_ein_gescheiterter_lauf_gibt_die_sperre_frei_und_schreibt_einen_vorfall(conn, einst):
    _setze_begriffe(conn)

    class _KaputtesKLM:
        def schema(self, *a, **k):
            raise RuntimeError("simulierter Ausfall")

    fragen_ki.starte(conn, _TG(), _KaputtesKLM(), einst, CHAT)
    _warte_bis(lambda: fragen_ki.versuche_start(CHAT) is True)
    fragen_ki.beende(CHAT)
    vorfall = conn.execute(
        "SELECT art FROM vorfall WHERE art = 'fragen_ki_fehler'",
    ).fetchone()
    assert vorfall is not None

    # Ein gescheiterter Lauf laesst das Feld leer -- ein spaeterer Aufruf
    # (z.B. ein erneuter Phase-2-Eintritt) ist damit ein zulaessiger Retry.
    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert not (zeile and zeile["fragen_ki_vorschlag"])


# ---------------------------------------------------------------------------
# Review-Befund 1 (Task 12): eine "erfolgreiche", aber leere Modellantwort
# ist derselbe Fall wie eine Ausnahme -- Vorfall, kein Reveal-Aufruf, Feld
# bleibt leer.
# ---------------------------------------------------------------------------


def test_leere_antwort_schreibt_ebenfalls_einen_vorfall_und_ruft_den_reveal_nicht(
    conn, einst, monkeypatch,
):
    """Unterscheidet sich von ``_KaputtesKLM``: der Modellaufruf selbst
    gelingt (kein Exception-Pfad), liefert aber eine leere, unbrauchbare
    Antwort -- das darf nicht stillschweigend durchgehen."""
    aufrufe = []
    monkeypatch.setattr(
        fragen, "versuche_gegenueberstellung",
        lambda *a, **k: aufrufe.append(a), raising=False,
    )

    _setze_begriffe(conn)
    klm_leer = _KLM(antwort="")
    fragen_ki.starte(conn, _TG(), klm_leer, einst, CHAT)
    _warte_bis(lambda: fragen_ki.versuche_start(CHAT) is True)
    fragen_ki.beende(CHAT)

    vorfall = conn.execute(
        "SELECT art FROM vorfall WHERE art = 'fragen_ki_fehler'",
    ).fetchone()
    assert vorfall is not None

    zeile = repo.hole_arbeitsstand(conn, CHAT)
    assert not (zeile and zeile["fragen_ki_vorschlag"])
    assert aufrufe == []


def test_ein_gescheiterter_lauf_erlaubt_einen_retry(conn, einst):
    _setze_begriffe(conn)

    class _KaputtesKLM:
        def schema(self, *a, **k):
            raise RuntimeError("simulierter Ausfall")

    fragen_ki.starte(conn, _TG(), _KaputtesKLM(), einst, CHAT)
    _warte_bis(lambda: fragen_ki.versuche_start(CHAT) is True)
    fragen_ki.beende(CHAT)

    klm = _KLM()
    fragen_ki.starte(conn, _TG(), klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe >= 1)
    _warte_bis(
        lambda: _feld(conn, CHAT, "fragen_ki_vorschlag")
    )
    assert klm.aufrufe == 1

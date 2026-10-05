"""Aufgabe 13 (Padua Phase 1+2 Umbau, 03.10.2026, KORREKTUR-PHASE2-KEIN-KNOPF.md):
``knoepfe.fragen.uebernimm_eigene``/``versuche_gegenueberstellung`` -- der
A/B-Vergleich eigene-vs-KI-Fragen in Phase 2, OHNE "Fertig"-Knopf.

Der Code speichert nach jedem Zug die eigenen Fragen (``VORSCHLAG EIGENE
FRAGEN:``) und startet die Gegenueberstellung mit den isoliert im
Hintergrund erzeugten KI-Fragen (``fragen_ki.py``, Aufgabe 12), sobald die
Gruppe fertig ist -- erkannt von ``_fruehzeitig_fertig`` an einem
woertlichen Satz, den das Padua-Profil-Prompt das Modell sagen laesst
(keine neue, bezahlte Erkenner-Art). Seit 05.10.2026 ohne Mindestzahl je
Begriff (Birk: die Anzahl entscheidet die Gruppe)."""

import re
import threading
import time

import pytest

from interview_theater import db, phasen, repo, vorschlag, workshop
from interview_theater import knoepfe
from interview_theater.knoepfe import fragen
from interview_theater.knoepfe.texte import T

from test_knoepfe import TelegramAttrappe, _druck

CHAT = 1


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    """Dieselbe Attrappe wie ``tests/test_undo_fragen_abschluss.py``: ein
    Auftragszug wird aufgezeichnet statt ausgefuehrt -- kein Netz, kein
    Modell."""
    from interview_theater import ablauf

    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


class _TG:
    """Threadsicher (fuer den Race-Test): ``sende``/``sende_mit_knoepfen``
    haengen unter einem Lock an, damit zwei gleichzeitige Aufrufer sich
    nicht die Liste zerschiessen -- die Faehigkeit, die mit einem einfachen
    ``list.append`` aus zwei Threads fehlen wuerde."""

    def __init__(self):
        self._lock = threading.Lock()
        self.gesendet = []
        self.naechste_message_id = 100

    def sende(self, chat_id, text, **_kw):
        with self._lock:
            self.naechste_message_id += 1
            self.gesendet.append((chat_id, text))
            return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        with self._lock:
            self.naechste_message_id += 1
            self.gesendet.append((chat_id, text))
            return self.naechste_message_id

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


def _setze_begriffe(conn, begriffe: str = "Heimat, Streit", chat_id: int = CHAT) -> None:
    repo.setze_arbeitsstand(conn, chat_id, "begriffe", begriffe)


def _feld(conn, chat_id, feld):
    zeile = repo.hole_arbeitsstand(conn, chat_id)
    return zeile[feld] if zeile is not None else None


# ---------------------------------------------------------------------------
# vorschlag.py: der neue Marker
# ---------------------------------------------------------------------------


def test_marker_eigene_fragen():
    assert vorschlag.marker("eigene_fragen") == "VORSCHLAG EIGENE FRAGEN:"


def test_eigene_fragen_block_wird_gelesen():
    text = "Danke!\n\nVORSCHLAG EIGENE FRAGEN:\nHeimat: Wo warst du zuhause?"
    bloecke = vorschlag.alle(text)
    assert bloecke["eigene_fragen"] == "Heimat: Wo warst du zuhause?"


def test_eigene_fragen_wird_nicht_von_fragen_verschluckt_und_verschluckt_fragen_nicht():
    """Zwei getrennte Bloecke in einem Text duerfen sich nicht
    gegenseitig uebernehmen -- die urspruengliche Sorge der Karte (``EIGENE
    FRAGEN`` koennte wie ``FRAGEN`` gelesen werden oder umgekehrt)."""
    text = (
        "VORSCHLAG FRAGEN:\nHeimat: Alte Frage.\n\n"
        "VORSCHLAG EIGENE FRAGEN:\nHeimat: Neue eigene Frage."
    )
    bloecke = vorschlag.alle(text)
    assert bloecke["fragen"] == "Heimat: Alte Frage."
    assert bloecke["eigene_fragen"] == "Heimat: Neue eigene Frage."


def test_padua_tallystufe_fordert_kein_fragen_weich_mehr(monkeypatch):
    """Review-Fund (Fix-Runde nach der ersten Abnahme von Aufgabe 13): die
    Padua-Phase-2-Vorlage bat das Modell urspruenglich, WAEHREND der
    laufenden Zusammenfassung (``VORSCHLAG EIGENE FRAGEN:``) zusaetzlich auf
    sensible Themen zu pruefen und ``VORSCHLAG FRAGEN WEICH:`` anzuhaengen.
    ``{"eigene_fragen", "fragen_weich"}`` steht aber NICHT in
    ``basis._ERLAUBTE_BLOCKPAARE`` -- der weiche Block waere von
    ``_ein_feld_je_nachricht`` als zweites, unerwartetes Thema verworfen
    worden (Vorfall ``vorschlag_mehrere_arten``), ohne dass ``fragen_weich``
    je gesetzt wird. Fix (8acd2b8): die Vorlage fordert das waehrend der
    Tally-Stufe nicht mehr an, sondern nur noch in der spaeteren
    Einzeldurchgang-Stufe (``VORSCHLAG FRAGE:`` + ``VORSCHLAG FRAGEN
    WEICH:``, ein Paar, das ``_ERLAUBTE_BLOCKPAARE`` erlaubt).

    Update (Prompt-Hygiene-Karte, T1-Review-Fund, 05.10.2026, P2-N3): kurz
    danach (7cd6096, 03.10.2026) hat Birk die weiche Fassung fuer Padua
    komplett per Profilschalter abgeschaltet (``fragen_weich.aktiv = false``
    in ``workshop/padua-2026/profil.toml``, ``workshop.fragen_weich_aktiv()``
    == False) -- seitdem verwirft der Code jeden ``fragen_weich``-Wert fuer
    Padua ohnehin (``knoepfe/fragen.py:_setze_weich``: "Abgeschaltet
    (Padua): nichts speichern, auch wenn ein Modell den Block doch
    liefert"), unabhaengig vom Prompttext. Die Einzeldurchgang-Stufe nannte
    den Marker seitdem nur noch, um ihn ausdruecklich zu VERBIETEN ("No
    softer versions, ... not here and not anywhere else in this phase
    (switched off for this workshop)") -- ein toter Verweis, den keine
    Pruefung mehr braucht, weil der Profilschalter die Wirkung schon
    abschliessend regelt. Die Karte hat diesen Satz entfernt (nur die
    positive Regel "The group words its questions itself." bleibt). Diese
    Erwartung aendert sich deshalb mit: fuer Padua darf der Marker jetzt
    NIRGENDS mehr im geladenen Phase-2-Prompt vorkommen, nicht einmal als
    Verbotsklausel -- die urspruengliche Absicht des Tests (Tally-Stufe
    ohne den Marker) ist weiter erfuellt, nur strenger (ueberall ohne)."""
    from interview_theater import anweisungen

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    try:
        assert workshop.fragen_weich_aktiv() is False
        text = " ".join(anweisungen.hole("phasen/2").split())
        tally_beginn = text.index("Keep a running tally")
        vergleich_beginn = text.index("Once the comparison is running")
        tally_abschnitt = text[tally_beginn:vergleich_beginn]
        assert "FRAGEN WEICH" not in tally_abschnitt.upper()
        # Seit dem Profilschalter (7cd6096) und der Entfernung des toten
        # Verbots-Verweises (P2-N3): der Marker kommt fuer Padua gar nicht
        # mehr vor, auch nicht in der spaeteren Einzeldurchgang-Stufe.
        assert "FRAGEN WEICH" not in text.upper()
    finally:
        workshop.vergiss()
        anweisungen._CACHE.clear()


def test_regex_eigene_fragen_hat_kein_gemeinsames_praefix_mit_den_anderen_fragen_varianten():
    """Unabhaengige Bestaetigung (die Karte verlangt sie ausdruecklich):
    ``EIGENE FRAGEN`` beginnt mit einem eigenen Wort direkt nach
    'VORSCHLAG ' und kann deshalb nie von ``FRAGEN``/``FRAGE``/
    ``FRAGENAUSWAHL``/``FRAGEN WEICH`` schon vorher abgefangen werden --
    unabhaengig von der Reihenfolge in der Alternation."""
    for zeile in (
        "VORSCHLAG FRAGEN:", "VORSCHLAG FRAGE:", "VORSCHLAG FRAGENAUSWAHL:",
        "VORSCHLAG FRAGEN WEICH:",
    ):
        treffer = vorschlag._ZEILE.match(zeile + " x")
        assert treffer is not None
        art = treffer.group(1).strip().upper()
        assert not art.startswith("EIGENE")
    treffer = vorschlag._ZEILE.match("VORSCHLAG EIGENE FRAGEN: x")
    assert treffer is not None
    assert treffer.group(1).strip().upper() == "EIGENE FRAGEN"


# ---------------------------------------------------------------------------
# uebernimm_eigene: Overwrite-Semantik
# ---------------------------------------------------------------------------


def test_uebernimm_eigene_ueberschreibt_statt_anzuhaengen(conn, einst, monkeypatch):
    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    _setze_begriffe(conn, "Heimat")
    tg = _TG()

    fragen.uebernimm_eigene(conn, tg, CHAT, "Heimat: Erste Fassung.")
    erster = _feld(conn, CHAT, "fragen_eigene_vorschlag")
    assert erster == "Heimat: Erste Fassung."

    fragen.uebernimm_eigene(conn, tg, CHAT, "Heimat: Ganz andere Fassung.")
    zweiter = _feld(conn, CHAT, "fragen_eigene_vorschlag")
    assert zweiter == "Heimat: Ganz andere Fassung."
    assert "Erste Fassung" not in zweiter


# ---------------------------------------------------------------------------
# Die Mindestzahl je Begriff: Stand-Zeile vs. automatischer Start
# ---------------------------------------------------------------------------


def test_ohne_fertig_satz_geht_die_antwort_des_modells_raus_keine_stand_zeile(
    conn, einst, monkeypatch,
):
    """Live-Test 05.10.2026 (Birk): statt "Still missing: Begriff (x/3)"
    nach jeder Bestaetigung geht die eigene Antwort des Modells in den Chat
    -- ohne Soll-Zahl. Der Stand je Begriff steht im CoThinker."""
    aufrufe = []
    monkeypatch.setattr(
        fragen, "versuche_gegenueberstellung",
        lambda *a, **k: aufrufe.append(a) or None,
    )
    _setze_begriffe(conn, "Heimat, Streit")
    tg = _TG()

    wert = "Heimat: Frage eins.\nStreit: Frage A."
    fragen.uebernimm_eigene(conn, tg, CHAT, wert, text="Gute Frage zu Heimat!")

    assert aufrufe == []
    assert _feld(conn, CHAT, "fragen_eigene_erstellt_am") is None
    assert [t for _, t in tg.gesendet] == ["Gute Frage zu Heimat!"]
    assert not any(re.search(r"\(\d+/\d+\)", t) for _, t in tg.gesendet)


def test_ohne_antworttext_nur_der_verweis_auf_den_cothinker(conn, einst, monkeypatch):
    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    _setze_begriffe(conn, "Heimat")
    tg = _TG()

    fragen.uebernimm_eigene(conn, tg, CHAT, "Heimat: Frage eins.", text="  ")

    assert [t for _, t in tg.gesendet] == [T._TEXT_FRAGEN_EIGENE_IM_COTHINKER]


def test_keine_mindestzahl_drei_fragen_je_begriff_loesen_nichts_automatisch_aus(
    conn, einst, monkeypatch,
):
    """Birk, 05.10.2026: die Anzahl entscheidet die Gruppe. Auch drei (oder
    mehr) Fragen je Begriff starten die Gegenueberstellung NICHT von selbst
    -- nur der Satz, mit dem das Modell meldet, dass die Gruppe fertig ist."""
    aufrufe = []
    monkeypatch.setattr(
        fragen, "versuche_gegenueberstellung",
        lambda *a, **k: aufrufe.append(a) or None,
    )
    _setze_begriffe(conn, "Heimat")
    tg = _TG()
    wert = "Heimat: Frage eins.\nHeimat: Frage zwei.\nHeimat: Frage drei."

    fragen.uebernimm_eigene(conn, tg, CHAT, wert, text="Noch eine?")
    assert aufrufe == []
    assert _feld(conn, CHAT, "fragen_eigene_erstellt_am") is None

    fragen.uebernimm_eigene(
        conn, tg, CHAT, wert, text="Alles klar. Eigene Fragen fertig.",
    )
    assert len(aufrufe) == 1
    assert _feld(conn, CHAT, "fragen_eigene_erstellt_am")


def test_erstellt_am_wird_nur_einmal_gesetzt(conn, einst, monkeypatch):
    """Idempotenz (Punkt 2 des Controller-Designs): ein spaeterer, erneut
    'bereiter' Aufruf darf den einmal gesetzten Zeitstempel nicht
    ueberschreiben."""
    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    _setze_begriffe(conn, "Heimat")
    tg = _TG()
    wert = "Heimat: Frage eins.\nHeimat: Frage zwei.\nHeimat: Frage drei."
    fertig = "Eigene Fragen fertig."

    fragen.uebernimm_eigene(conn, tg, CHAT, wert, text=fertig)
    erster_zeitstempel = _feld(conn, CHAT, "fragen_eigene_erstellt_am")
    assert erster_zeitstempel

    time.sleep(0.01)
    fragen.uebernimm_eigene(conn, tg, CHAT, wert, text=fertig)
    zweiter_zeitstempel = _feld(conn, CHAT, "fragen_eigene_erstellt_am")
    assert zweiter_zeitstempel == erster_zeitstempel


def test_bereit_ohne_ki_schickt_warte_hinweis(conn, einst, monkeypatch):
    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    _setze_begriffe(conn, "Heimat")
    tg = _TG()

    fragen.uebernimm_eigene(
        conn, tg, CHAT,
        "Heimat: Frage eins.\nHeimat: Frage zwei.\nHeimat: Frage drei.",
        text="Eigene Fragen fertig.",
    )
    assert tg.gesendet[-1][1] == T._TEXT_FRAGEN_EIGENE_WARTET_AUF_KI


# ---------------------------------------------------------------------------
# Frueher Schluss ohne Knopf und ohne Erkenner-Art
# ---------------------------------------------------------------------------


def test_fruehzeitig_fertig_erkennt_den_satz_case_und_whitespace_unabhaengig():
    assert fragen._fruehzeitig_fertig("Alles klar. eigene fragen   fertig.  ") is True
    assert fragen._fruehzeitig_fertig("Gut so. EIGENE FRAGEN FERTIG.") is True


def test_fruehzeitig_fertig_ist_false_fuer_none_leer_und_unverwandtes():
    assert fragen._fruehzeitig_fertig(None) is False
    assert fragen._fruehzeitig_fertig("") is False
    assert fragen._fruehzeitig_fertig("   ") is False
    assert fragen._fruehzeitig_fertig("Wir machen gleich weiter.") is False


def test_fruehzeitig_fertig_loest_den_reveal_auch_unter_der_mindestzahl_aus(conn, einst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(
        fragen, "versuche_gegenueberstellung",
        lambda *a, **k: aufrufe.append(a) or None,
    )
    _setze_begriffe(conn, "Heimat, Streit")
    tg = _TG()

    # Nur je eine Frage -- unter der Mindestzahl, aber die Gruppe sagt den
    # Satz aus dem Padua-Profil-Prompt woertlich im Fliesstext.
    fragen.uebernimm_eigene(
        conn, tg, CHAT, "Heimat: Frage eins.\nStreit: Frage A.",
        text="Gut, das reicht uns. Eigene Fragen fertig.",
    )
    assert len(aufrufe) == 1
    assert _feld(conn, CHAT, "fragen_eigene_erstellt_am")


# ---------------------------------------------------------------------------
# versuche_gegenueberstellung: Reveal nur mit beiden Seiten
# ---------------------------------------------------------------------------


def test_kein_reveal_ohne_ki_seite(conn):
    _setze_begriffe(conn, "Heimat")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", "Heimat: Eigene Frage.")
    tg = _TG()

    ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert ergebnis is None
    assert not _feld(conn, CHAT, "fragen_auswahl")
    assert tg.gesendet == []


def test_kein_reveal_ohne_eigene_seite(conn):
    _setze_begriffe(conn, "Heimat")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_ki_vorschlag", "Heimat: KI Frage.")
    tg = _TG()

    ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert ergebnis is None
    assert not _feld(conn, CHAT, "fragen_auswahl")


def _bereite_gegenueberstellung_vor(conn) -> None:
    _setze_begriffe(conn, "Heimat, Streit")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_eigene_vorschlag",
        "Heimat: Eigene Frage 1.\nStreit: Eigene Frage A.",
    )
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_ki_vorschlag",
        "Heimat: KI Frage 1.\nHeimat: KI Frage 2.\nHeimat: KI Frage 3.\n"
        "Streit: KI Frage 1.\nStreit: KI Frage 2.\nStreit: KI Frage 3.",
    )
    # Die Gruppe hat gesagt, dass sie fertig ist (``uebernimm_eigene``).
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", repo._jetzt())


def test_kein_reveal_solange_die_gruppe_nicht_fertig_ist(conn):
    """05.10.2026: ein KI-Lauf, der fertig wird, waehrend die Gruppe noch
    sammelt, offenbart nicht mitten hinein -- die eigene Seite steht erst
    mit ``fragen_eigene_erstellt_am``."""
    _bereite_gegenueberstellung_vor(conn)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", None)
    tg = _TG()

    assert fragen.versuche_gegenueberstellung(conn, tg, CHAT) is None
    assert not _feld(conn, CHAT, "fragen_auswahl")
    assert tg.gesendet == []


def test_reveal_interleaved_eigene_vor_ki_je_begriff_mit_ausgerichteter_herkunft(conn):
    _bereite_gegenueberstellung_vor(conn)
    # Beweis, dass der Reset wirklich etwas zurueckzusetzen hat.
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "7")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,nein")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_warte_auf", "richtung")
    tg = _TG()

    ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert ergebnis is not None

    zeilen = repo.hole_arbeitsstand(conn, CHAT)["fragen_auswahl"].splitlines()
    herkunft = repo.hole_arbeitsstand(conn, CHAT)["fragen_herkunft"].split(",")
    assert zeilen == [
        "Heimat: Eigene Frage 1.",
        "Heimat: KI Frage 1.",
        "Heimat: KI Frage 2.",
        "Heimat: KI Frage 3.",
        "Streit: Eigene Frage A.",
        "Streit: KI Frage 1.",
        "Streit: KI Frage 2.",
        "Streit: KI Frage 3.",
    ]
    assert herkunft == ["eigen", "ki", "ki", "ki", "eigen", "ki", "ki", "ki"]
    assert len(zeilen) == len(herkunft)

    stand = repo.hole_arbeitsstand(conn, CHAT)
    # Der Reset raeumt den ALTEN Stand weg (Frage 7, "ja,nein", "richtung");
    # ``starte_durchgehen`` zeigt danach Frage 1 und setzt ``fragen_aktuell``
    # folgerichtig auf "1" -- das ist die neue, gueltige Frage, nicht Reststand.
    assert stand["fragen_aktuell"] == "1"
    assert not stand["fragen_entschieden"]
    assert not stand["fragen_warte_auf"]

    # Die Ueberleitungszeile UND die erste Frage (``starte_durchgehen``
    # wiederverwendet, nicht nachgebaut) sind raus.
    assert T._TEXT_GEGENUEBERSTELLUNG_BEREIT in tg.texte
    assert any("Eigene Frage 1" in t for t in tg.texte)


def test_reveal_ist_danach_ein_dauerhaftes_no_op(conn):
    _bereite_gegenueberstellung_vor(conn)
    tg = _TG()
    erstes_ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert erstes_ergebnis is not None
    gesendet_nach_erstem_lauf = len(tg.gesendet)

    zweites_ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert zweites_ergebnis is None
    assert len(tg.gesendet) == gesendet_nach_erstem_lauf


# ---------------------------------------------------------------------------
# Race/Doppel-Trigger: zwei Aufrufer gleichzeitig -- Reveal GENAU EINMAL
# ---------------------------------------------------------------------------


def _zweite_verbindung(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    return c


def test_zwei_gleichzeitige_aufrufer_offenbaren_genau_einmal(tmp_path):
    """Schwarzkasten-Probe der Karte ("Gegenueberstellung laeuft genau
    einmal"): zwei ECHTE Threads mit je einer EIGENEN Datenbankverbindung
    auf dieselbe Datei (das unterstuetzte Produktionsmuster, WAL +
    busy_timeout -- NICHT eine Verbindung ueber mehrere Threads, das waere
    Falle 6 aus AGENTS.md) rufen ``versuche_gegenueberstellung`` mit einem
    ``threading.Barrier`` moeglichst gleichzeitig auf. Ohne den
    Modul-Lock in ``versuche_gegenueberstellung`` koennten beide den noch
    leeren ``fragen_auswahl``-Stand sehen und zweimal offenbaren."""
    conn1 = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn1)
    repo.sichere_gruppe(conn1, CHAT, "gruppe1", "Testgruppe")
    _bereite_gegenueberstellung_vor(conn1)
    conn2 = _zweite_verbindung(tmp_path)

    tg = _TG()
    start = threading.Barrier(2)
    ergebnisse: list[int | None] = [None, None]

    def _lauf(index: int, conn) -> None:
        start.wait(timeout=5)
        ergebnisse[index] = fragen.versuche_gegenueberstellung(conn, tg, CHAT)

    t1 = threading.Thread(target=_lauf, args=(0, conn1))
    t2 = threading.Thread(target=_lauf, args=(1, conn2))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    treffer = [e for e in ergebnisse if e is not None]
    assert len(treffer) == 1, f"erwartet genau ein Reveal, bekommen: {ergebnisse}"

    # Die Ueberleitungszeile darf nur EINMAL im Chat stehen.
    ueberleitungen = [t for t in tg.texte if t == T._TEXT_GEGENUEBERSTELLUNG_BEREIT]
    assert len(ueberleitungen) == 1

    zeilen = repo.hole_arbeitsstand(conn1, CHAT)["fragen_auswahl"].splitlines()
    assert len(zeilen) == 8  # 2 eigene + 6 KI, nicht verdoppelt

    conn1.close()
    conn2.close()


# ---------------------------------------------------------------------------
# _zeige_frage: Herkunfts-Kennzeichnung, byte-identisch ohne Herkunftsdaten
# ---------------------------------------------------------------------------


def test_zeige_frage_zeigt_herkunft_wenn_daten_vorhanden(conn):
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: Eigene Frage.\nHeimat: KI Frage.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki")
    tg = _TG()

    fragen._zeige_frage(conn, tg, CHAT, 1)
    assert tg.gesendet[-1][1].endswith(T._TEXT_HERKUNFT_EIGEN)

    fragen._zeige_frage(conn, tg, CHAT, 2)
    assert tg.gesendet[-1][1].endswith(T._TEXT_HERKUNFT_KI)


def test_zeige_frage_bleibt_byte_identisch_ohne_herkunftsdaten(conn):
    """Regressionswache (Task-Vorgabe): der klassische Ablauf
    (``fragen_ab_aktiv()`` aus, oder jeder Lauf vor Aufgabe 13) kennt
    ``fragen_herkunft`` nicht -- die Darstellung muss zeichengleich zu
    vorher bleiben."""
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "Heimat: Eine Frage.")
    tg = _TG()

    fragen._zeige_frage(conn, tg, CHAT, 1)
    erwartet = (
        T._TEXT_FRAGE_KOPF.format(nummer=1, gesamt=1, begriff="Heimat")
        + "\n\n" + "Eine Frage."
    )
    assert tg.gesendet[-1][1] == erwartet


# ---------------------------------------------------------------------------
# fragen_bearbeitet: nur fuer editierte KI-Fragen, nie fuer eigene
# ---------------------------------------------------------------------------


def test_schaerfung_markiert_bearbeitet_nur_fuer_ki_herkunft(conn):
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: KI Frage.\nHeimat: Eigene Frage.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "ki,eigen")
    tg = _TG()

    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "1")
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "Heimat: Ueberarbeitete KI-Frage.", None)
    assert _feld(conn, CHAT, "fragen_bearbeitet") == "1"

    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "2")
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "Heimat: Ueberarbeitete eigene Frage.", None)
    # Nummer 2 ist "eigen" -- das Flag darf dadurch NICHT gesetzt werden,
    # der bestehende Wert (nur Index 1) bleibt unangetastet.
    assert _feld(conn, CHAT, "fragen_bearbeitet") == "1"


def test_schaerfung_ohne_herkunftsdaten_bleibt_ein_no_op_fuer_bearbeitet(conn):
    """Klassischer Ablauf: ``fragen_herkunft`` existiert nicht, also darf
    ``fragen_bearbeitet`` auch nicht entstehen."""
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "Heimat: Eine Frage.")
    tg = _TG()
    repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", "1")
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "Heimat: Andere Frage.", None)
    assert not _feld(conn, CHAT, "fragen_bearbeitet")


# ---------------------------------------------------------------------------
# fragen_herkunft_final: Laenge und Indexreihenfolge wie ``fragen``
# ---------------------------------------------------------------------------


def test_herkunft_final_passt_zu_fragen_nach_abschluss(conn, tg, einst, auftraege):
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl",
        "Heimat: Q1 eigen.\nHeimat: Q2 ki.\nStreit: Q3 ki.\nStreit: Q4 eigen.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki,ki,eigen")
    phasen.setze(conn, CHAT, 2, "befehl")

    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")   # eigen, angenommen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "nein")  # ki, verworfen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 3, "ja")   # ki, angenommen
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 4, "ja")   # eigen, angenommen

    stand = repo.hole_arbeitsstand(conn, CHAT)
    fragen_liste = stand["fragen"].splitlines()
    herkunft_final = stand["fragen_herkunft_final"].split(",")
    assert fragen_liste == ["Heimat: Q1 eigen.", "Streit: Q3 ki.", "Streit: Q4 eigen."]
    assert herkunft_final == ["eigen", "ki", "eigen"]
    assert len(fragen_liste) == len(herkunft_final)


def test_herkunft_final_ist_leer_ohne_herkunftsdaten(conn, tg, einst, auftraege):
    """Klassischer Ablauf: jede Position bleibt ein leerer String, aber die
    Laenge passt trotzdem zu ``fragen`` (Lockstep-Garantie fuer Aufgabe 14)."""
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: Q1.\nStreit: Q2.",
    )
    phasen.setze(conn, CHAT, 2, "befehl")

    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "ja")

    stand = repo.hole_arbeitsstand(conn, CHAT)
    fragen_liste = stand["fragen"].splitlines()
    herkunft_final = stand["fragen_herkunft_final"].split(",")
    assert herkunft_final == ["", ""]
    assert len(fragen_liste) == len(herkunft_final)


# ---------------------------------------------------------------------------
# Scope-Grenze: der klassische Ablauf bleibt byte-identisch
# ---------------------------------------------------------------------------


def test_klassischer_abschlusstext_bleibt_byte_identisch(conn, tg, einst, auftraege):
    """Regressionswache (Task-Vorgabe, 'same spirit as Task 8's Dortmund
    guard'): ohne ``fragen_herkunft`` darf die Notiert-Meldung am Ende von
    Phase 2 kein Zeichen anders aussehen als vor Aufgabe 13."""
    wert = (
        "Heimat: Wann hast du dich zuletzt fremd gefuehlt?\n"
        "Streit: Wann habt ihr zuletzt richtig gestritten?"
    )
    phasen.setze(conn, CHAT, 2, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, CHAT, "Hier ein paar Fragen.\n\nVORSCHLAG FRAGENAUSWAHL:\n" + wert,
    )
    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "ja")

    erwartet = (
        "Notiert, eure 2 Fragen:\n"
        "1. Heimat: Wann hast du dich zuletzt fremd gefuehlt?\n"
        "2. Streit: Wann habt ihr zuletzt richtig gestritten?"
    )
    assert tg.gesendet[-1][1] == erwartet


# ---------------------------------------------------------------------------
# Review-Fund: ein unerwarteter FRAGEN-WEICH-Block neben EIGENE FRAGEN
# bricht nichts -- bestehendes, generisches Verhalten, NICHT neu verdrahtet
# ---------------------------------------------------------------------------


def test_eigene_fragen_mit_unerwartetem_fragen_weich_bricht_nicht_sondern_verwirft_ihn(
    conn, monkeypatch,
):
    """Sollte trotz der Vorlagenkorrektur doch einmal ein ``VORSCHLAG FRAGEN
    WEICH:`` neben ``VORSCHLAG EIGENE FRAGEN:`` in einer Antwort stehen
    (ein aelterer Modellstand, ein anderes Profil, ein Ausreisser): nichts
    stuerzt ab. Das ist das bestehende, korrekte generische Verhalten fuer
    zwei Vorschlagsbloecke verschiedener Art in einer Nachricht
    (``basis._ein_feld_je_nachricht``) -- der erste im Text gewinnt, der
    zweite wird verworfen und als Vorfall vermerkt. Dieser Test bestaetigt
    ausdruecklich NICHT, dass die Verdrahtung ``eigene_fragen`` jetzt doch
    einen ``fragen_weich``-Block entgegennimmt (das soll sie laut Review
    gerade nicht) -- nur, dass die Vorlagenkorrektur die einzig noetige
    Aenderung war und der generische Pfad weiterhin sicher ist."""
    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    _setze_begriffe(conn, "Heimat")
    tg = _TG()

    text = (
        "Danke!\n\nVORSCHLAG EIGENE FRAGEN:\nHeimat: Frage eins.\n\n"
        "VORSCHLAG FRAGEN WEICH:\n1 — Weicher gefragt."
    )
    message_id, hat_leiste = knoepfe.sende_mit_speicherleiste(conn, tg, CHAT, text)

    assert message_id is not None
    assert hat_leiste is True
    # Der erste Block im Text ("eigene_fragen") gewinnt und wird gespeichert.
    assert _feld(conn, CHAT, "fragen_eigene_vorschlag") == "Heimat: Frage eins."
    # Der zweite ("fragen_weich") wird verworfen, nicht gespeichert.
    assert not _feld(conn, CHAT, "fragen_weich")

    vorfall = conn.execute(
        "SELECT art FROM vorfall WHERE art = 'vorschlag_mehrere_arten'",
    ).fetchone()
    assert vorfall is not None


# ---------------------------------------------------------------------------
# Abschluss-Review des gesamten Branches, Finding 1: stale fragen_herkunft/
# fragen_bearbeitet duerfen eine klassische Fragenrunde nach einem
# abgelehnten A/B-Reveal nicht ueberleben
# ---------------------------------------------------------------------------


def test_reset_fragenrunde_entfernt_stale_herkunft_nach_abgelehnter_gegenueberstellung(
    conn, tg, einst, auftraege,
):
    """Szenario aus dem Abschluss-Review: eine Gruppe faehrt den A/B-Reveal
    (``versuche_gegenueberstellung`` setzt ``fragen_herkunft``), lehnt dann
    IN DER EINZELDURCHSICHT JEDE Frage ab. ``_schliesse_fragen_ab``s
    bestehender ``if not angenommen:``-Zweig ruft
    ``frage_fuer_andere_richtung`` -> ``_starte_auftrag``, der einen frischen,
    KLASSISCHEN ``VORSCHLAG FRAGENAUSWAHL:``-Block erzeugt -- der kommt ueber
    ``biete_fragenauswahl`` zurueck, NICHT ueber ``uebernimm_eigene``/
    ``versuche_gegenueberstellung``. Ohne den Fix in ``_reset_fragenrunde``
    ueberlebt das alte ``fragen_herkunft`` der verworfenen Gegenueberstellung
    diesen Uebergang: ``_zeige_frage`` haengt die alten, index-falschen
    " (eure)"/" (KI)"-Marken an voellig unabhaengige neue Fragen, und eine
    spaetere ``_schliesse_fragen_ab`` baut ``fragen_herkunft_final`` aus
    Indizes, die nicht mehr zu denselben Fragen gehoeren -- das korrumpiert
    Aufgabe 14s Dashboard-/Chat-Auswertung fuer diese Gruppe."""
    _bereite_gegenueberstellung_vor(conn)
    ergebnis = fragen.versuche_gegenueberstellung(conn, tg, CHAT)
    assert ergebnis is not None

    vor_ablehnung = repo.hole_arbeitsstand(conn, CHAT)
    gesamt = len(vor_ablehnung["fragen_auswahl"].splitlines())
    assert gesamt == 8
    # Beweis, dass es wirklich etwas Stale-s zu vererben gibt.
    assert vor_ablehnung["fragen_herkunft"]

    for nummer in range(1, gesamt + 1):
        knoepfe.entscheide(conn, tg, None, einst, CHAT, nummer, "nein")

    # Der Fallback-Pfad der Karte lief: "nichts angenommen" hat ueber
    # _starte_auftrag (hier aufgezeichnet statt ausgefuehrt, Fixture
    # ``auftraege``) einen neuen Vorschlag angestossen.
    assert auftraege
    assert T._TEXT_FRAGEN_KEINE_ANGENOMMEN in tg.texte

    # Die Antwort auf diesen Auftrag kommt -- wie jede allererste Runde --
    # ueber biete_fragenauswahl zurueck, mit voellig neuen, unabhaengigen
    # Fragen (anderer Wortlaut, andere Zaehlung).
    fragen.biete_fragenauswahl(
        conn, tg, CHAT,
        "Neu: Ganz andere Frage eins.\nNeu: Ganz andere Frage zwei.",
    )

    stand = repo.hole_arbeitsstand(conn, CHAT)
    # Der eigentliche Fix: keine stale Herkunft/Bearbeitet-Markierung mehr.
    assert not stand["fragen_herkunft"]
    assert not stand["fragen_bearbeitet"]

    # Ohne den Fix haette Frage 1 hier noch " (eure)" getragen (Index 1 der
    # alten Herkunftsliste war "eigen") -- eine Kennzeichnung, die zu einer
    # voellig anderen, unabhaengigen Frage gehoert.
    fragen._zeige_frage(conn, tg, CHAT, 1)
    assert not tg.texte[-1].endswith(T._TEXT_HERKUNFT_EIGEN)
    assert not tg.texte[-1].endswith(T._TEXT_HERKUNFT_KI)

    knoepfe.starte_durchgehen(conn, tg, CHAT)
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, CHAT, 2, "ja")

    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["fragen"].splitlines() == [
        "Neu: Ganz andere Frage eins.", "Neu: Ganz andere Frage zwei.",
    ]
    # fragen_herkunft_final muss fuer diese Runde entweder leer/abwesend sein
    # oder konsequent "kein A/B-Vergleich" anzeigen -- NIE Reste der alten
    # Gegenueberstellung (die sich an den gleichen Indizes befunden haetten).
    herkunft_final = (stand["fragen_herkunft_final"] or "").split(",")
    assert all(not h for h in herkunft_final)


def test_fragen_ab_inaktiv_populiert_nie_die_neuen_felder(conn, einst, monkeypatch):
    """Solange ``workshop.fragen_ab_aktiv()`` False ist (Dortmund-Vorgabe,
    jedes bestehende Profil): der neue Marker kommt im Prompt gar nicht vor
    (er steht nur im Padua-Profil), also laeuft dieser Pfad fuer eine echte
    Gruppe nie an. Hier wird nur bestaetigt, dass ``fragen_ab_aktiv()``
    tatsaechlich False ist, solange niemand das Profil umschaltet -- die
    Marker-Abwesenheit selbst ist in ``tests/test_sprache_prompts.py``/
    ``tests/test_anweisungen.py`` abgedeckt (kein Marker im Repo-Prompt)."""
    assert workshop.fragen_ab_aktiv() is False


# ---------------------------------------------------------------------------
# P2-H2 (Feedbackloop P1-2, 05.10.2026): der A/B-Vergleich verlor KI-Fragen,
# weil ``_zeilen_je_begriff`` einen exakten "<Begriff>: "-Praefix verlangte.
# Echte Modellausgaben schreiben den Begriff fett, in Anfuehrungszeichen, im
# Singular, mit Gedankenstrich statt Doppelpunkt oder als Zwischenueberschrift.
# ---------------------------------------------------------------------------

BEGRIFFE_REAL = ["Living on mars", "robots", "Home"]


@pytest.mark.parametrize("zeile, begriff, frage", [
    ("**Home**: Tell me about a place.", "Home", "Tell me about a place."),
    ("**Home:** Tell me about a place.", "Home", "Tell me about a place."),
    ('"Home": Tell me about a place.', "Home", "Tell me about a place."),
    ("“Home”: Tell me about a place.", "Home", "Tell me about a place."),
    ("HOME: Tell me about a place.", "Home", "Tell me about a place."),
    ("  home :  Tell me about a place.", "Home", "Tell me about a place."),
    ("Home – Tell me about a place.", "Home", "Tell me about a place."),
    ("Home — Tell me about a place.", "Home", "Tell me about a place."),
    ("Home - Tell me about a place.", "Home", "Tell me about a place."),
    ("Robot: Who repairs a robot?", "robots", "Who repairs a robot?"),
    ("The robots: Who repairs a robot?", "robots", "Who repairs a robot?"),
    ("Living on Mars: What would you miss on Mars?", "Living on mars",
     "What would you miss on Mars?"),
    ("Home (term 3): Tell me about a place.", "Home", "Tell me about a place."),
    ("Home – Tell me: where was it?", "Home", "Tell me: where was it?"),
])
def test_zeilen_je_begriff_toleriert_echte_modellausgabe(zeile, begriff, frage):
    je_begriff = fragen._zeilen_je_begriff(BEGRIFFE_REAL, [zeile])
    assert je_begriff[begriff] == [f"{begriff}: {frage}"]


def test_zeilen_je_begriff_liest_zwischenueberschriften():
    zeilen = vorschlag.zeilen(
        "**Home**\n- Tell me about a place.\n- Who cooked there?\n\n"
        "Robots:\n1. Who repairs a robot?"
    )
    je_begriff = fragen._zeilen_je_begriff(BEGRIFFE_REAL, zeilen)
    assert je_begriff["Home"] == [
        "Home: Tell me about a place.", "Home: Who cooked there?",
    ]
    assert je_begriff["robots"] == ["robots: Who repairs a robot?"]


def test_zeilen_je_begriff_haengt_umbrochene_fortsetzung_an():
    """Das Beispiel im Prompt selbst ist umbrochen -- ein Modell, das es
    nachahmt, schreibt eine Frage ueber zwei Zeilen."""
    zeilen = vorschlag.zeilen(
        "Home: What did you take with you the last time you moved -- and why exactly\n"
        "that?\nHome: Who cooked there?"
    )
    je_begriff = fragen._zeilen_je_begriff(BEGRIFFE_REAL, zeilen)
    assert je_begriff["Home"] == [
        "Home: What did you take with you the last time you moved -- and why "
        "exactly that?",
        "Home: Who cooked there?",
    ]


def test_zeilen_je_begriff_schlaegt_keinen_satzanfang_einem_begriff_zu():
    """'Tell me about home: ...' ist eine Frage, kein Begriffskopf -- sie
    wird nicht verstuemmelt und keinem Begriff zugeschlagen."""
    zeilen, rest = fragen._ordne_zeilen(
        BEGRIFFE_REAL, ["Tell me about home: what did it smell like?"],
    )
    assert all(not z for z in zeilen.values())
    assert rest == ["Tell me about home: what did it smell like?"]


def test_reveal_verliert_keine_ki_frage_bei_echter_modellausgabe(conn):
    """Live-Fall: alle KI-Zeilen fielen durch, die Gegenueberstellung
    zeigte nur die eigenen Fragen (oder gar nichts)."""
    _setze_begriffe(conn, "Living on mars, robots")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_eigene_vorschlag",
        "Living on mars: Would you like to live on Mars?",
    )
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_ki_vorschlag",
        "**Living on Mars**: What would you miss on Mars?\n"
        "Robot – Who repairs a robot?\n"
        "Something else entirely: A question without a term?",
    )
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", repo._jetzt())
    tg = _TG()

    assert fragen.versuche_gegenueberstellung(conn, tg, CHAT) is not None
    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["fragen_auswahl"].splitlines() == [
        "Living on mars: Would you like to live on Mars?",
        "Living on mars: What would you miss on Mars?",
        "robots: Who repairs a robot?",
        # Kein Begriff erfunden, aber auch keine Frage verloren: am Ende.
        "Something else entirely: A question without a term?",
    ]
    assert stand["fragen_herkunft"].split(",") == ["eigen", "ki", "ki", "ki"]
    assert T._TEXT_FRAGEN_KEINE_AUSWAHL not in tg.texte


def test_leerer_vergleich_laeuft_nicht_in_keine_auswahl(conn):
    """Ergibt sich keine einzige Zeile, wird nichts offenbart -- keine leere
    ``fragen_auswahl`` und kein "I don't know this selection any more"
    (das danach bei jedem Versuch wieder kam)."""
    _setze_begriffe(conn, "Heimat")
    # Nicht leer, aber ohne eine einzige Fragezeile (nur Aufzaehlungszeichen).
    repo.setze_arbeitsstand(conn, CHAT, "fragen_ki_vorschlag", "-\n*")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_erstellt_am", repo._jetzt())
    tg = _TG()

    assert fragen.versuche_gegenueberstellung(conn, tg, CHAT) is None
    assert not _feld(conn, CHAT, "fragen_auswahl")
    assert T._TEXT_FRAGEN_KEINE_AUSWAHL not in tg.texte


# ---------------------------------------------------------------------------
# P2-H3 (Karte): dieselbe Frage dreimal als Karte. Jede freie Nachricht
# waehrend einer offenen Frage ist ein Schaerfungswunsch; kam die Frage
# unveraendert zurueck, stand dieselbe Karte erneut da -- mit einer zweiten
# lebenden Annehmen-Leiste darueber.
# ---------------------------------------------------------------------------


def test_unveraenderte_schaerfung_zeigt_keine_zweite_karte(conn, tg, einst):
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: Eine Frage?\nStreit: Zweite?",
    )
    knoepfe.starte_durchgehen(conn, tg, CHAT)
    karten_vorher = len(tg.knoepfe)

    fragen.uebernimm_schaerfung(conn, tg, CHAT, "Heimat:  eine frage?", None)
    fragen.uebernimm_schaerfung(conn, tg, CHAT, "Heimat: Eine Frage?", None)

    assert len(tg.knoepfe) == karten_vorher
    assert tg.texte[-1] == T._TEXT_FRAGE_WAS_AENDERN
    # Die erste Karte bleibt bedienbar.
    assert repo.offene_knoepfe(conn, CHAT, knoepfe.ART_FRAGE_ANNEHMEN)


def test_geschaerfte_karte_nimmt_der_alten_die_leiste_ab(conn, tg, einst):
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen_auswahl", "Heimat: Eine Frage?\nStreit: Zweite?",
    )
    knoepfe.starte_durchgehen(conn, tg, CHAT)
    (alt,) = repo.offene_knoepfe(conn, CHAT, knoepfe.ART_FRAGE_ANNEHMEN)

    neue_id = fragen.uebernimm_schaerfung(
        conn, tg, CHAT, "Heimat: Eine bessere Frage?", None,
    )

    assert tg.knoepfe[-1][1].endswith("Eine bessere Frage?")
    offen = repo.offene_knoepfe(conn, CHAT, knoepfe.ART_FRAGE_ANNEHMEN)
    assert [k["message_id"] for k in offen] == [neue_id]
    assert (CHAT, alt["message_id"]) in tg.entfernt


# ---------------------------------------------------------------------------
# P2-N1: "What do you want to change?" stand doppelt (Blase + Quittung)
# ---------------------------------------------------------------------------


def test_schaerfen_knopf_quittiert_nicht_mit_derselben_frage(conn, tg, einst):
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "Heimat: Eine Frage?")
    knoepfe.starte_durchgehen(conn, tg, CHAT)
    daten = next(d for b, d in tg.knoepfe[-1][2] if b == T._TEXT_FRAGE_SCHAERFEN_KNOPF)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert tg.texte.count(T._TEXT_FRAGE_WAS_AENDERN) == 1
    assert T._TEXT_FRAGE_WAS_AENDERN not in [t for _, t in tg.beantwortet]

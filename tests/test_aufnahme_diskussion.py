"""Aufgabe 3 (Padua Phase 1+2 Umbau): ``aufnahme._diskussion_abschliessen`` --
das Hintergrund-Mithoeren von Phase 1 ("nur zuhoeren"). Ein Diskussions-Segment
ist reines Material: es wird als Sprechblase im Web-Chat abgetippt, loest aber
nie einen Gespraechszug, nie den Absichtserkenner und nie die
CoThinker-Vorschlagskarte (``brainstorm.soll_reagieren``/``_starte_buehnenkarte``)
aus -- im Unterschied zum strukturell aehnlichen Brainstorm-Weg (Phase 4,
``_brainstorm_abschliessen``), der genau das am Ende pruefen darf.

Gebaut direkt auf dem Muster der Brainstorm-Dispatch-Tests in
``tests/test_aufnahme.py`` (``_brainstorm_zeile``, lokale ``conn``/``tg``/
``einst``-Fixtures)."""

import pytest

from interview_theater import aufnahme, db, einstellungen, repo, workshop


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def _diskussion_zeile(conn, chat_id, message_id, transkript, schnittgrund=None):
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.merke_nachricht(
        conn, chat_id, message_id, "Gruppe", 0, "sprache", None,
        repo._jetzt(), 1,
    )
    return repo.hole_aufnahme(conn, aufnahme_id)


class _TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        return 1


def _kurz_zeile(conn, chat_id, message_id, transkript):
    """Eine gewoehnliche kurze Sprachnachricht -- weder ``brainstorm`` noch
    ``diskussion`` gesetzt. Dient der Regressionspruefung: dieser Weg muss
    unveraendert ``zug`` ausloesen."""
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.merke_nachricht(
        conn, chat_id, message_id, "Gruppe", 0, "sprache", None,
        repo._jetzt(), 1,
    )
    return repo.hole_aufnahme(conn, aufnahme_id)


def test_diskussion_segment_setzt_status_fertig(conn, einst):
    row = _diskussion_zeile(conn, 1, 700, "Ein Gedanke im Hintergrund.")
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    neu = repo.hole_aufnahme(conn, row["id"])
    assert neu["status"] == "fertig"


def test_diskussion_segment_ruft_zug_nicht_auf(conn, einst):
    row = _diskussion_zeile(conn, 1, 701, "Noch ein Gedanke.")
    aufgerufen = []
    aufnahme._kurz_abschliessen(
        conn, None, None, einst, row,
        lambda *a, **k: aufgerufen.append(1), False,
    )
    assert not aufgerufen


def test_diskussion_segment_schreibt_transkript_in_die_sprachblase(conn, einst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(
        aufnahme, "_web_sprachblase",
        lambda conn_, chat_id, message_id, text: aufrufe.append((chat_id, message_id, text)),
    )
    row = _diskussion_zeile(conn, 1, 702, "Das steht im Hintergrund.")
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    assert aufrufe == [(1, 702, "Das steht im Hintergrund.")]


def test_diskussion_segment_startet_nie_eine_buehnenkarte(conn, einst, monkeypatch):
    """Ein Diskussions-Segment startet nie einen Buehnenkarten-Lauf (Phase
    4). Seit Karte t_4517d4ad prueft es aber ``soll_reagieren`` -- fuer das
    Begriffsboard (``begriffsboard.nach_segment``), siehe
    ``tests/test_begriffsboard_mithoeren.py``."""
    buehnenkarte_aufgerufen = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda *a, **k: buehnenkarte_aufgerufen.append(1),
    )
    row = _diskussion_zeile(conn, 1, 703, "x" * 200)
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    assert not buehnenkarte_aufgerufen


def test_diskussion_segment_wird_nicht_typ_text(conn, einst):
    """Wie beim Brainstorm-Weg bleibt die ``nachricht``-Zeile unveraendert --
    das Transkript ist Material, kein Gespraechsbeitrag im Fenster."""
    row = _diskussion_zeile(conn, 1, 704, "Ein kurzer Gedanke im Hintergrund.")
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    zeile = conn.execute(
        "SELECT typ, unterdrueckt FROM nachricht WHERE chat_id = 1 AND message_id = 704",
    ).fetchone()
    assert zeile["typ"] == "sprache"
    assert zeile["unterdrueckt"] == 1


# -- Regression: der bestehende Weg bleibt unveraendert ---------------------


def test_brainstorm_segment_bleibt_unveraendert_von_der_diskussionspruefung(
    conn, einst, monkeypatch,
):
    """``row["diskussion"]`` ist bei einem Brainstorm-Segment 0 -- die neue
    Weiche darf den bestehenden Brainstorm-Dispatch nicht umgehen oder
    doppelt ausloesen."""
    aufgerufen = []
    monkeypatch.setattr(
        aufnahme, "_brainstorm_abschliessen",
        lambda *a, **k: aufgerufen.append(1),
    )
    aufnahme_id = repo.lege_aufnahme_an(
        conn, 1, 705, "kurz", "sprache", status="transkribiert", brainstorm=True,
    )
    repo.setze_transkript(conn, aufnahme_id, "Ein Brainstorm-Gedanke.")
    repo.merke_nachricht(
        conn, 1, 705, "Gruppe", 0, "sprache", None, repo._jetzt(), 1,
    )
    row = repo.hole_aufnahme(conn, aufnahme_id)
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    assert aufgerufen == [1]


def test_plain_kurz_zeile_loest_weiterhin_zug_aus(conn, einst):
    """Eine gewoehnliche kurze Sprachnachricht (weder brainstorm noch
    diskussion) muss unveraendert einen Gespraechszug ausloesen -- die neue
    Weiche darf diesen Weg nicht blockieren."""
    row = _kurz_zeile(conn, 1, 706, "Ein ganz normaler Gespraechsbeitrag.")
    aufgerufen = []
    aufnahme._kurz_abschliessen(
        conn, None, None, einst, row,
        lambda conn_, tg_, klm_, e_, chat_id, hinweis=None: aufgerufen.append(chat_id),
        False,
    )
    assert aufgerufen == [1]


# -- Aufgabe 7: der Abschlusspfad (schnittgrund == 'ende') ------------------


@pytest.fixture(autouse=True)
def _diskussion_aktiv(monkeypatch):
    """Dieselbe Vorgabe wie in ``tests/test_diskussion.py`` -- ohne Profil
    ist ``workshop.diskussion_aktiv()`` False (Dortmund-Vorgabe)."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)


def test_ende_segment_sendet_die_begriffe_aufforderung_und_startet_die_verdichtung(
    conn, einst, monkeypatch,
):
    from interview_theater import diskussion

    gestartet = []
    monkeypatch.setattr(
        diskussion, "starte",
        lambda conn_, tg_, klm_, e_, chat_id: gestartet.append(chat_id),
    )
    tg = _TelegramAttrappe()
    row = _diskussion_zeile(conn, 1, 710, "Der letzte Gedanke.", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, None, einst, row, aufnahme._kein_zug, False)
    assert tg.gesendet == [(1, aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE)]
    assert gestartet == [1]


def test_nicht_ende_segment_sendet_nichts_und_startet_keine_verdichtung(
    conn, einst, monkeypatch,
):
    from interview_theater import diskussion

    gestartet = []
    monkeypatch.setattr(
        diskussion, "starte",
        lambda conn_, tg_, klm_, e_, chat_id: gestartet.append(chat_id),
    )
    tg = _TelegramAttrappe()
    row = _diskussion_zeile(conn, 1, 711, "Ein Gedanke mittendrin.", schnittgrund="pause")
    aufnahme._kurz_abschliessen(conn, tg, None, einst, row, aufnahme._kein_zug, False)
    assert tg.gesendet == []
    assert gestartet == []


def test_segment_ohne_schnittgrund_sendet_nichts_und_startet_keine_verdichtung(
    conn, einst, monkeypatch,
):
    """``schnittgrund`` ist NULL, solange kein VAD-Schnitt vorlag (Rueckfall
    ohne AnalyserNode) -- auch dann bleibt der Abschlusspfad aus."""
    from interview_theater import diskussion

    gestartet = []
    monkeypatch.setattr(
        diskussion, "starte",
        lambda conn_, tg_, klm_, e_, chat_id: gestartet.append(chat_id),
    )
    tg = _TelegramAttrappe()
    row = _diskussion_zeile(conn, 1, 712, "Ein Gedanke ohne Schnittgrund.")
    aufnahme._kurz_abschliessen(conn, tg, None, einst, row, aufnahme._kein_zug, False)
    assert tg.gesendet == []
    assert gestartet == []

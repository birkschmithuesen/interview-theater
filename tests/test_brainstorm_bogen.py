"""Brainstorm der Phase 4 als Gedankenbogen (Karte t_cf87ee0a, Birk
03.10.2026): EIN Toggle = EIN Bogen. Waehrend der Toggle an ist, entsteht
keine Karte; erst das Bogenende (``schnittgrund='ende'``) wartet auf alle
Segmente des Bogens und entscheidet genau einmal -- Karte oder sichtbares
Schweigen. Fixtures aus ``tests/test_aufnahme.py`` kopiert, damit die Datei
allein laeuft."""

import threading
import time

import pytest

from interview_theater import aufnahme, brainstorm, db, einstellungen, repo


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


class TelegramAttrappe:
    """Kein Netzzugriff, zeichnet auf (Kopie aus ``tests/test_aufnahme.py``)."""

    def __init__(self):
        self.gesendet = []
        self._letzte_message_id = 9000

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._letzte_message_id += 1
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _brainstorm_zeile(conn, chat_id, message_id, transkript, schnittgrund="pause"):
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
        schnittgrund=schnittgrund, brainstorm=True,
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.merke_nachricht(
        conn, chat_id, message_id, "Gruppe", 0, "sprache", None,
        "2026-10-02T10:00:00", 1,
    )
    return repo.hole_aufnahme(conn, aufnahme_id)


def test_ende_wartet_auf_offene_segmente_des_bogens(conn, tg, einst, monkeypatch):
    """Reihenfolge sichern: die Karte laeuft erst, wenn das letzte
    Zwischensegment (cap) transkribiert ist -- heute Race zwischen Upload/STT
    und _starte_buehnenkarte."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    gesehen = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda c, t, k, e, chat_id, **kw: gesehen.append(
            repo.brainstorm_stand(c, chat_id, bis_id=kw.get("bis_id"))["unreagierte_zeichen"]))
    offen = repo.lege_aufnahme_an(conn, 1, 600, "kurz", "sprache", status="empfangen",
                                  brainstorm=True, schnittgrund="cap")
    ende = _brainstorm_zeile(conn, 1, 601, "x" * 20, schnittgrund="ende")

    def spaeter():
        time.sleep(0.2)
        repo.setze_transkript(conn, offen, "y" * 30)
        repo.setze_status(conn, offen, "fertig")

    threading.Thread(target=spaeter).start()
    aufnahme._kurz_abschliessen(conn, tg, None, einst, ende, aufnahme._kein_zug, False)
    assert gesehen == [50]


def test_ende_unter_der_schwelle_ist_sichtbares_schweigen(conn, tg, einst):
    """Nach dem Stopp kommt GENAU eine Reaktion: Karte oder 'nothing to add'
    (cothinker_status.ZUSTAND_SCHWEIGT) -- auch wenn der Bogen kurz war."""
    row = _brainstorm_zeile(conn, 1, 610, "zu kurz", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    karten = repo.buehnenkarten(conn, 1)
    assert len(karten) == 1 and karten[0]["schweigen"] == 1 and karten[0]["text"] == ""


# Birk 05.10.2026 22:00: kein Toggle, Phase-1-Bedienung -- ein Kappenschnitt
# zaehlt im Zwischenlauf jetzt wie ein Pausenschnitt (D1, dasselbe Muster wie
# begriffsboard.soll_laufen). Die alte "cap loest nie aus"-Erwartung ist
# damit ueberholt; die neue Erwartung (Kappenschnitt mit genug Text loest
# eine Zwischenkarte aus) steht in tests/test_aufnahme.py als
# test_kappenschnitt_mit_genug_text_loest_eine_karte_aus.


def test_pausenschnitt_unter_schwelle_schreibt_kein_schweigen(conn, tg, einst, monkeypatch):
    """Birk 05.10.2026 22:00: der Zwischenlauf waehrend des Zuhoerens ist
    STILL unter der Schwelle -- anders als das Bogenende ('ende') legt er nie
    eine sichtbare Schweigen-Zeile an, auch nicht wenn ``soll_reagieren``
    verneint. Die unreagierten Zeichen bleiben einfach stehen und zaehlen
    beim naechsten Schnitt weiter mit."""
    aufgerufen = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: aufgerufen.append(1))
    row = _brainstorm_zeile(conn, 1, 620, "x" * 5, schnittgrund="pause")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert not aufgerufen and repo.buehnenkarten(conn, 1) == []


def test_pausenschnitt_wartet_nie(conn, tg, einst, monkeypatch):
    """Birk 05.10.2026 22:00: der Zwischenauslöser entscheidet SOFORT -- er
    wartet nie auf offene Segmente oder einen freien Kartenlauf (das bleibt
    dem Bogenende vorbehalten). Die beiden Wartefunktionen wuerden hier
    werfen, wenn sie aufgerufen wuerden."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "0")

    def _wirft(*a, **k):
        raise AssertionError("der Zwischenlauf darf nie warten")

    monkeypatch.setattr(aufnahme, "_warte_auf_offene_segmente", _wirft)
    monkeypatch.setattr(aufnahme, "_warte_auf_freien_kartenlauf", _wirft)
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: True)
    row = _brainstorm_zeile(conn, 1, 621, "x" * 20, schnittgrund="pause")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)


def test_zwischenkarte_markiert_nur_bis_vor_das_erste_offene_segment(conn, tg, einst, monkeypatch):
    """Birk 05.10.2026 22:00: die Zwischenmarkierung bleibt -- wie der
    Boardlauf der Phase 1 (``repo.diskussion_gelesen_bis``) -- vor dem ersten
    noch offenen (nicht fertigen) Segment stehen, auch wenn ein spaeteres
    Segment schon fertig ist und den Lauf ausloest."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "0")
    gesehen = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda c, t, k, e, chat_id, **kw: gesehen.append(kw.get("bis_id")))

    def _segment(message_id, status, schnittgrund, text=None):
        aufnahme_id = repo.lege_aufnahme_an(
            conn, 1, message_id, "kurz", "sprache", status=status,
            schnittgrund=schnittgrund, brainstorm=True,
        )
        if text is not None:
            repo.setze_transkript(conn, aufnahme_id, text)
        return aufnahme_id

    erste = _segment(700, "fertig", "pause", "x" * 20)
    _segment(701, "empfangen", "cap")  # noch offen -- kein Transkript
    dritte_id = _segment(702, "fertig", "pause", "y" * 20)

    aufnahme._kurz_abschliessen(
        conn, tg, None, einst, repo.hole_aufnahme(conn, dritte_id),
        aufnahme._kein_zug, False,
    )
    assert gesehen == [erste]


def test_ende_nach_zwischenkarte_zaehlt_nur_den_rest(conn, tg, einst, monkeypatch):
    """Birk 05.10.2026 22:00: nach einer Zwischenkarte (``brainstorm_
    markierung_id`` gesetzt) zaehlt das Bogenende nur noch den REST seit
    dieser Markierung -- unter der Abschlussschwelle (150) sichtbares
    Schweigen, darueber eine Karte."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "150")
    repo.sichere_gruppe(conn, 2, "gruppe2", "Testgruppe2")

    def _segment(chat_id, message_id, schnittgrund, text):
        aufnahme_id = repo.lege_aufnahme_an(
            conn, chat_id, message_id, "kurz", "sprache", status="fertig",
            schnittgrund=schnittgrund, brainstorm=True,
        )
        repo.setze_transkript(conn, aufnahme_id, text)
        return aufnahme_id

    # Chat 1: unter der Schwelle (100 Zeichen Rest) -> sichtbares Schweigen.
    markiert_bei = _segment(1, 720, "pause", "x" * 50)
    repo.markiere_brainstorm_reaktion(conn, 1, markiert_bei)
    ende_unter = _segment(1, 721, "ende", "y" * 100)
    aufnahme._kurz_abschliessen(
        conn, tg, object(), einst, repo.hole_aufnahme(conn, ende_unter),
        aufnahme._kein_zug, False,
    )
    karten1 = repo.buehnenkarten(conn, 1)
    assert [(k["schweigen"], k["modell"]) for k in karten1] == [(1, "schwelle")]

    # Chat 2: ueber der Schwelle (150 Zeichen Rest) -> Karte.
    aufgerufen = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: aufgerufen.append(1) or True)
    markiert_bei_2 = _segment(2, 722, "pause", "x" * 50)
    repo.markiere_brainstorm_reaktion(conn, 2, markiert_bei_2)
    ende_ueber = _segment(2, 723, "ende", "z" * 150)
    aufnahme._kurz_abschliessen(
        conn, tg, object(), einst, repo.hole_aufnahme(conn, ende_ueber),
        aufnahme._kein_zug, False,
    )
    assert aufgerufen


def test_pausensegment_waehrend_ende_wartet_startet_keine_zwischenkarte(conn, tg, einst, monkeypatch):
    """Birk 05.10.2026 22:00: ein 'pause'-Segment, das erst NACH dem
    Bogenende ('ende', hoehere id) fertig wird (langsame Transkription),
    sieht als juengsten Schnittgrund insgesamt 'ende' -- der Zwischenlauf
    greift dann nicht, denn die Gruppe hat ja schon aufgehoert."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "0")
    aufgerufen = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: aufgerufen.append(1) or True)

    pause_row = _brainstorm_zeile(conn, 1, 740, "x" * 20, schnittgrund="pause")
    # Das Bogenende ist schon da -- schneller verarbeitet, hoehere id.
    _brainstorm_zeile(conn, 1, 741, "y" * 20, schnittgrund="ende")

    aufnahme._kurz_abschliessen(conn, tg, None, einst, pause_row, aufnahme._kein_zug, False)
    assert not aufgerufen


def test_offene_brainstorm_segmente_zaehlt_nur_diese_sitzung(conn):
    alt = repo.lege_aufnahme_an(conn, 1, 700, "kurz", "sprache", status="empfangen",
                                brainstorm=True, schnittgrund="cap")
    repo.lege_aufnahme_an(conn, 1, 701, "kurz", "sprache", status="fertig",
                          brainstorm=True, schnittgrund="ende")
    offen = repo.lege_aufnahme_an(conn, 1, 702, "kurz", "sprache", status="empfangen",
                                  brainstorm=True, schnittgrund="cap")
    ende = repo.lege_aufnahme_an(conn, 1, 703, "kurz", "sprache", status="fertig",
                                 brainstorm=True, schnittgrund="ende")
    assert repo.offene_brainstorm_segmente(conn, 1, ende) == 1
    assert alt < offen


def test_ende_wartet_auf_laufende_karte_des_vorigen_bogens(conn, tg, einst, monkeypatch):
    """Genau eine Reaktion je Bogen: laeuft beim Stopp noch die Karte des
    VORIGEN Bogens (``brainstorm.versuche_start`` waere belegt), darf dieser
    Bogen nicht still leer ausgehen -- das Ende wartet, bis der Lauf frei ist,
    und entscheidet dann."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    beim_start_belegt = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda c, t, k, e, chat_id, **kw: beim_start_belegt.append(brainstorm.laeuft(chat_id))
        or True)
    assert brainstorm.versuche_start(1)
    try:
        threading.Timer(0.2, brainstorm.beende, args=(1,)).start()
        row = _brainstorm_zeile(conn, 1, 630, "x" * 20, schnittgrund="ende")
        aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    finally:
        brainstorm.beende(1)
    assert beim_start_belegt == [False]


def _warte_auf_karten(conn, anzahl=1):
    for _ in range(100):
        if len(repo.buehnenkarten(conn, 1)) >= anzahl:
            break
        time.sleep(0.02)
    return repo.buehnenkarten(conn, 1)


def test_ende_schweigt_sichtbar_wenn_voriger_lauf_ueber_die_frist_belegt(
    conn, tg, einst, monkeypatch,
):
    """Review I1: laeuft die Karte des vorigen Bogens laenger als das Ende
    wartet, darf der neue Bogen nicht still leer ausgehen -- genau eine
    sichtbare Schweigen-Zeile (modell 'belegt')."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_TAKT_S", 0.01)
    monkeypatch.setattr(aufnahme, "ENDE_WARTEN_S", 0.05)
    monkeypatch.setattr(aufnahme, "ENDE_LAUF_WARTEN_S", 0.05, raising=False)
    assert brainstorm.versuche_start(1)
    try:
        row = _brainstorm_zeile(conn, 1, 640, "x" * 20, schnittgrund="ende")
        aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    finally:
        brainstorm.beende(1)
    karten = repo.buehnenkarten(conn, 1)
    assert [(k["schweigen"], k["text"], k["modell"]) for k in karten] == [(1, "", "belegt")]


def test_ende_wartet_auf_den_vorigen_lauf_laenger_als_die_segmentfrist():
    """Review I1: ein Kartenlauf darf ``buehnenkarte.TIMEOUT_S`` dauern --
    das Ende wartet mindestens so lange auf ihn."""
    from interview_theater import buehnenkarte
    assert aufnahme.ENDE_LAUF_WARTEN_S > buehnenkarte.TIMEOUT_S


def test_segment_des_naechsten_bogens_zaehlt_nicht_zur_schwelle(conn, tg, einst, monkeypatch):
    """Review I2: wird der Toggle waehrend des Ende-Wartens neu gestartet,
    zaehlt ein Segment des NAECHSTEN Bogens nicht zur Schwelle dieses Bogens."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "100")
    gestartet = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte",
                        lambda *a, **k: gestartet.append(1) or True)
    row = _brainstorm_zeile(conn, 1, 650, "x" * 20, schnittgrund="ende")
    _brainstorm_zeile(conn, 1, 651, "y" * 500, schnittgrund="pause")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert gestartet == []
    karten = repo.buehnenkarten(conn, 1)
    assert [(k["schweigen"], k["modell"]) for k in karten] == [(1, "schwelle")]


def test_segment_des_naechsten_bogens_wird_nicht_als_reagiert_markiert(
    conn, tg, einst, monkeypatch,
):
    """Review I2: die Markierung der Karte endet am Ende-Segment ihres Bogens."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    monkeypatch.setattr(aufnahme.buehnenkarte, "erzeuge",
                        lambda *a, **k: ("Karte.", "infomaniak"))
    row = _brainstorm_zeile(conn, 1, 660, "x" * 20, schnittgrund="ende")
    _brainstorm_zeile(conn, 1, 661, "y" * 500, schnittgrund="pause")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert len(_warte_auf_karten(conn)) == 1
    for _ in range(100):
        if not brainstorm.laeuft(1):
            break
        time.sleep(0.02)
    assert repo.brainstorm_stand(conn, 1)["unreagierte_zeichen"] == 500


def test_brainstorm_stand_mit_bis_id_zaehlt_nur_bis_dorthin(conn):
    erste = _brainstorm_zeile(conn, 1, 670, "x" * 20, schnittgrund="ende")
    _brainstorm_zeile(conn, 1, 671, "y" * 500, schnittgrund="pause")
    assert repo.brainstorm_stand(conn, 1, bis_id=erste["id"])["unreagierte_zeichen"] == 20
    assert repo.brainstorm_stand(conn, 1)["unreagierte_zeichen"] == 520


def test_kartenlauf_mit_ausnahme_hinterlaesst_eine_schweigen_zeile(conn, tg, einst, monkeypatch):
    """Review M2: wirft der Lauf (z. B. ``_nutzertext`` oder
    ``anweisungen.hole`` ausserhalb des try in ``erzeuge``), sieht die Gruppe
    trotzdem eine Reaktion -- eine Schweigen-Zeile (modell 'fehler')."""
    def _wirft(*a, **k):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(aufnahme.buehnenkarte, "erzeuge", _wirft)
    assert aufnahme._starte_buehnenkarte(conn, tg, object(), einst, 1) is True
    karten = _warte_auf_karten(conn)
    assert [(k["schweigen"], k["text"], k["modell"]) for k in karten] == [(1, "", "fehler")]
    for _ in range(100):
        if not brainstorm.laeuft(1):
            break
        time.sleep(0.02)
    assert not brainstorm.laeuft(1)


def test_spaet_verarbeitetes_ende_eines_schon_gedeckten_bogens_schweigt_still(
    conn, tg, einst, monkeypatch,
):
    """P34 Final-Review: wurde das Ende eines SPAETEREN Bogens zuerst
    verarbeitet und hat dessen Karte diesen Bogen mit abgedeckt
    (Markierung >= Ende-id), legt das spaet verarbeitete Ende keine
    'schwelle'-Schweigen-Zeile ueber die echte Karte."""
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    gestartet = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte",
                        lambda *a, **k: gestartet.append(1) or True)
    frueh = _brainstorm_zeile(conn, 1, 680, "x" * 20, schnittgrund="ende")
    spaet = _brainstorm_zeile(conn, 1, 681, "y" * 30, schnittgrund="ende")
    repo.markiere_brainstorm_reaktion(conn, 1, spaet["id"])
    repo.lege_buehnenkarte_an(conn, 1, "Karte.", "infomaniak")

    aufnahme._kurz_abschliessen(conn, tg, object(), einst, frueh, aufnahme._kein_zug, False)

    assert gestartet == []
    karten = repo.buehnenkarten(conn, 1)
    assert [(k["schweigen"], k["text"]) for k in karten] == [(0, "Karte.")]


def test_sperre_bleibt_nicht_haengen_wenn_die_laufmarkierung_wirft(
    conn, tg, einst, monkeypatch,
):
    """P34 Final-Review: wirft ``repo.markiere_buehnenkarten_lauf`` nach
    ``brainstorm.versuche_start`` (noch vor dem Thread), muss die Sperre
    trotzdem frei werden -- sonst wartet jedes spaetere Bogenende
    ``ENDE_LAUF_WARTEN_S`` und schweigt dann 'belegt'."""
    def _wirft(*a, **k):
        raise RuntimeError("db kaputt")

    monkeypatch.setattr(aufnahme.repo, "markiere_buehnenkarten_lauf", _wirft)
    try:
        with pytest.raises(RuntimeError):
            aufnahme._starte_buehnenkarte(conn, tg, object(), einst, 1)
        assert not brainstorm.laeuft(1)
        assert brainstorm.versuche_start(1)
    finally:
        brainstorm.beende(1)

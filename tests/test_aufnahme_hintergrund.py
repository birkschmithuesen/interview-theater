"""Warnung 'Aufnahme im Hintergrund unterbrochen' (Karte t_1423ca89).

Evidence: Clone "G3 Interview 1" (padua-test1.db, Aufnahme #113) meldete
178 s, der Mitschnitt hielt real nur ~26 s Audio (412 KB bei den fuer dieses
Telefon ueblichen ~16 KB/s) -- die Seite war waehrend des Interviews im
Hintergrund, MediaRecorder und Timer dort angehalten (Wake Lock, 3a83071,
haelt nur den Bildschirm an, nicht Seitenwechsel/Sperrbildschirm).

Serverseitige Erkennung (kein JS-Vertrauen noetig): dauer_sekunden gegen die
Byte-Rate vorheriger Teile DESSELBEN Interviews -- dieselbe Rechnung wie in
der Evidence (412 000 / 16 000 ≈ 25,75 s, unter 50 % von 178 s)."""

from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import aufnahme, db, repo
from tests.test_aufnahme import TelegramAttrappe, interview_an, sprachnachricht

#: ~16 KB/s -- die "fuer dieses Telefon ueblichen" Rate aus der Evidence.
RATE_BYTES_S = 16_000


class TgGroesse(TelegramAttrappe):
    """Wie ``TelegramAttrappe``, nur schreibt ``lade_datei()`` so viele Bytes,
    wie ``groessen[file_id]`` sagt -- die fest verdrahteten 25 Byte der
    Attrappe waeren fuer eine Bytes/Sekunde-Schaetzung witzlos."""

    def __init__(self, groessen: dict):
        super().__init__()
        self._groessen = groessen

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"\x00" * self._groessen[file_id])
        self.heruntergeladen.append((file_id, ziel))


# -- die reinen Funktionen ---------------------------------------------------


def test_erkennt_die_evidence_aus_der_karte():
    """412 KB gemeldet als 178 s, Basisrate 16 KB/s -> geschaetzt ~25,75 s,
    weit unter 50 % von 178 s. Verlust ~152 s (178 - 25,75), wie im Brief
    beschrieben ("die letzten ~2,5 min des Interviews wurden nie
    aufgenommen")."""
    verlust = aufnahme.erkenne_hintergrund_unterbrechung(412_000, 178, RATE_BYTES_S)
    assert verlust == 152


def test_normale_rate_gibt_keinen_befund():
    """45 s bei 16 KB/s ergeben genau 720 000 Byte -- die Schaetzung trifft
    die gemeldete Dauer, kein Hintergrund-Vorfall."""
    assert aufnahme.erkenne_hintergrund_unterbrechung(
        45 * RATE_BYTES_S, 45, RATE_BYTES_S) is None


def test_knapp_ueber_der_haelfte_gibt_keinen_befund():
    """Genau an der Schwelle (50 % der gemeldeten Dauer): HINTERGRUND_ANTEIL
    ist ein ">=", nicht ein ">" -- die Grenze selbst zaehlt noch als
    unauffaellig, sonst waere eine Rate-Schwankung ohne jeden Hintergrund-
    Wechsel schon ein falscher Treffer."""
    dauer = 40
    genau_haelfte_bytes = int(dauer * aufnahme.HINTERGRUND_ANTEIL * RATE_BYTES_S)
    assert aufnahme.erkenne_hintergrund_unterbrechung(
        genau_haelfte_bytes, dauer, RATE_BYTES_S) is None


def test_kurze_nachricht_unter_der_mindestdauer_wird_nie_geprueft():
    """Unter HINTERGRUND_MIN_DAUER_S (20 s) nie ein Befund, egal wie
    verdaechtig die Rate aussieht -- eine kurze Nachricht schwankt zu stark."""
    assert aufnahme.erkenne_hintergrund_unterbrechung(
        10, 19, RATE_BYTES_S) is None


def test_ohne_basisrate_gibt_es_nie_einen_befund():
    """Der erste Teil eines Interviews hat keine Vorgaenger -- ohne
    Basisrate laesst sich nichts schaetzen, auch bei einer winzigen Datei."""
    assert aufnahme.erkenne_hintergrund_unterbrechung(100, 178, None) is None
    assert aufnahme.erkenne_hintergrund_unterbrechung(100, 178, 0) is None


def test_hintergrund_ms_bestimmt_die_ausgewiesene_dauer_wenn_vorhanden():
    """Spezifikation Punkt 3: exakt (vom Client gemessen) schlaegt geschaetzt
    fuer die ANGEZEIGTE Zahl -- die Ausloesung (Punkt 2) bleibt trotzdem die
    Bytes/Dauer-Pruefung."""
    verlust = aufnahme.erkenne_hintergrund_unterbrechung(
        412_000, 178, RATE_BYTES_S, hintergrund_ms=161_000)
    assert verlust == 161


def test_hintergrund_ms_ohne_ausloesenden_befund_bleibt_wirkungslos():
    """hintergrund_ms allein macht keinen Vorfall -- ohne die Bytes/Dauer-
    Ausloesung (hier: normale Rate) bleibt es None."""
    assert aufnahme.erkenne_hintergrund_unterbrechung(
        45 * RATE_BYTES_S, 45, RATE_BYTES_S, hintergrund_ms=5000) is None


def test_median_ungerade_laenge():
    assert aufnahme._median([3.0, 1.0, 2.0]) == 2.0


def test_median_gerade_laenge():
    assert aufnahme._median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_leer_ist_none():
    assert aufnahme._median([]) is None


def test_bytes_je_sekunde_ohne_datei_ist_none(tmp_path):
    zeile = {"audio_pfad": str(tmp_path / "fehlt.webm"), "dauer_sekunden": 10}
    assert aufnahme._bytes_je_sekunde(zeile) is None


def test_bytes_je_sekunde_ohne_dauer_ist_none(tmp_path):
    datei = tmp_path / "a.webm"
    datei.write_bytes(b"\x00" * 1000)
    zeile = {"audio_pfad": str(datei), "dauer_sekunden": None}
    assert aufnahme._bytes_je_sekunde(zeile) is None


def test_bytes_je_sekunde_rechnet_groesse_durch_dauer(tmp_path):
    datei = tmp_path / "a.webm"
    datei.write_bytes(b"\x00" * 32_000)
    zeile = {"audio_pfad": str(datei), "dauer_sekunden": 2}
    assert aufnahme._bytes_je_sekunde(zeile) == 16_000.0


# -- durch empfange() --------------------------------------------------------


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def einst(tmp_path):
    from interview_theater import einstellungen
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


def test_normaler_teil_loest_nichts_aus(conn, einst):
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 45 * RATE_BYTES_S})
    nachricht = sprachnachricht(dauer=45, message_id=10, file_id="F1")
    aid = aufnahme.empfange(conn, tg, einst, nachricht)

    assert repo.hole_aufnahme(conn, aid)["status"] == "empfangen"
    assert tg.gesendet == []
    assert conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE art = 'aufnahme_hintergrund'"
    ).fetchone()[0] == 0


def test_erster_teil_hat_keine_basis_und_loest_nie_aus(conn, einst):
    """Der erste Teil eines Interviews hat keine Vorgaenger -- selbst eine
    verdaechtig kleine Datei bei langer gemeldeter Dauer bleibt unauffaellig,
    weil es nichts zum Vergleichen gibt."""
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 412_000})
    nachricht = sprachnachricht(dauer=178, message_id=10, file_id="F1")
    aufnahme.empfange(conn, tg, einst, nachricht)

    assert tg.gesendet == []
    assert conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE art = 'aufnahme_hintergrund'"
    ).fetchone()[0] == 0


def test_truncated_teil_loest_vorfall_und_chatzeile_aus(conn, einst):
    """Die Evidence der Karte, Schritt fuer Schritt nachgebaut: ein normaler
    erster Teil setzt die Basisrate, ein zweiter Teil kommt mit 412 KB bei
    gemeldeten 178 s -- Vorfall UND genau eine Chatzeile."""
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 45 * RATE_BYTES_S, "F2": 412_000})
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=45, message_id=10, file_id="F1"))
    aid2 = aufnahme.empfange(
        conn, tg, einst, sprachnachricht(dauer=178, message_id=11, file_id="F2"))

    vorfall = conn.execute(
        "SELECT * FROM vorfall WHERE art = 'aufnahme_hintergrund'"
    ).fetchone()
    assert vorfall is not None
    assert str(aid2) in vorfall["detail"]

    chatzeilen = [t for _cid, t in tg.gesendet if "nicht vollstaendig aufgenommen" in t]
    assert len(chatzeilen) == 1
    assert "Interview 1" in chatzeilen[0]
    assert "2:32" in chatzeilen[0]   # 152 s = 2:32


def test_zweiter_truncated_teil_binnen_2_minuten_bekommt_keine_zweite_zeile(conn, einst):
    """"Do not repeat for the same interview within 2 min": der Vorfall wird
    bei JEDEM betroffenen Teil vermerkt (Dashboard), die Chatzeile aber nur
    einmal im Deckelfenster."""
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 45 * RATE_BYTES_S, "F2": 412_000, "F3": 412_000})
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=45, message_id=10, file_id="F1"))
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=178, message_id=11, file_id="F2"))
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=178, message_id=12, file_id="F3"))

    anzahl_vorfaelle = conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE art = 'aufnahme_hintergrund'"
    ).fetchone()[0]
    assert anzahl_vorfaelle == 2, "jeder betroffene Teil bekommt seinen Vorfall"

    chatzeilen = [t for _cid, t in tg.gesendet if "nicht vollstaendig aufgenommen" in t]
    assert len(chatzeilen) == 1, "nur eine Chatzeile binnen des Deckelfensters"


def test_ein_vorfall_ausserhalb_des_deckelfensters_bekommt_wieder_eine_zeile(conn, einst):
    """Nach Ablauf von HINTERGRUND_DECKEL_S darf wieder eine Chatzeile
    kommen -- der Deckel ist ein Zeitfenster, keine Einmal-Sperre."""
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 45 * RATE_BYTES_S, "F2": 412_000})
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=45, message_id=10, file_id="F1"))
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=178, message_id=11, file_id="F2"))
    assert len(tg.gesendet) == 1

    # Den schon gemeldeten Vorfall in die Vergangenheit verschieben, statt
    # den Deckel selbst zu verkuerzen (keine zweite Konfigurationsgroesse
    # nur fuer den Test).
    alt = (datetime.now(timezone.utc) - timedelta(seconds=aufnahme.HINTERGRUND_DECKEL_S + 5)
           ).isoformat(timespec="seconds")
    conn.execute("UPDATE vorfall SET erstellt_am = ? WHERE art = 'aufnahme_hintergrund'", (alt,))
    conn.commit()

    tg._groessen["F3"] = 412_000
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=178, message_id=12, file_id="F3"))
    chatzeilen = [t for _cid, t in tg.gesendet if "nicht vollstaendig aufgenommen" in t]
    assert len(chatzeilen) == 2


def test_hintergrund_ms_wird_gespeichert_und_bevorzugt_angezeigt(conn, einst):
    """Punkt 3 der Spezifikation: das vom Client gemessene ``hintergrund_ms``
    landet auf dem Teil UND bestimmt die in der Chatzeile genannte Dauer
    (exakt statt geschaetzt)."""
    interview_an(conn, einst=einst)
    tg = TgGroesse({"F1": 45 * RATE_BYTES_S, "F2": 412_000})
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=45, message_id=10, file_id="F1"))
    nachricht = sprachnachricht(dauer=178, message_id=11, file_id="F2")
    nachricht["hintergrund_ms"] = 161_000
    aid2 = aufnahme.empfange(conn, tg, einst, nachricht)

    assert repo.hole_aufnahme(conn, aid2)["hintergrund_ms"] == 161_000
    chatzeilen = [t for _cid, t in tg.gesendet if "nicht vollstaendig aufgenommen" in t]
    assert "2:41" in chatzeilen[0]   # 161 s = 2:41, nicht die geschaetzten 2:32


def test_kurzer_beitrag_ausserhalb_des_interviewmodus_loest_nichts_aus(conn, einst):
    """klasse='kurz' hat kein teil_von -- die Pruefung greift nur fuer
    Interview-Teile (siehe Docstring von _pruefe_hintergrund_unterbrechung)."""
    tg = TgGroesse({"F1": 100})
    nachricht = sprachnachricht(dauer=178, message_id=10, file_id="F1")
    aufnahme.empfange(conn, tg, einst, nachricht)
    assert conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE art = 'aufnahme_hintergrund'"
    ).fetchone()[0] == 0

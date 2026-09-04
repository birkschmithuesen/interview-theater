import pytest
from theatersoap import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_nachricht_wird_nicht_doppelt_eingefuegt(conn):
    assert repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    assert not repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 1


def test_unbeantwortete_beachtet_wasserzeichen_und_unterdrueckung(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "alt", "2026-09-05T10:00:00")
    repo.merke_nachricht(conn, 1, 11, "Bo", 0, "text", "nacht", "2026-09-05T22:00:00",
                         unterdrueckt=1)
    repo.merke_nachricht(conn, 1, 12, "Cem", 0, "text", "neu", "2026-09-06T12:00:00")
    repo.setze_beantwortet_bis(conn, 1, 10)
    assert [r["message_id"] for r in repo.unbeantwortete(conn, 1)] == [12]


def test_unbeantwortete_ignoriert_bot_nachrichten(conn):
    repo.merke_nachricht(conn, 1, 20, "Bot", 1, "text", "Antwort", "2026-09-05T10:00:00")
    assert repo.unbeantwortete(conn, 1) == []


def test_update_id_ueberlebt_eine_neue_verbindung(conn, tmp_path):
    repo.setze_update_id(conn, "gruppe1", 4711)
    conn.close()
    assert repo.hole_update_id(db.verbinde(str(tmp_path / "t.db")), "gruppe1") == 4711


def test_update_id_ist_null_wenn_unbekannt(conn):
    assert repo.hole_update_id(conn, "nochniegesehen") == 0


def test_wasserzeichen_geht_nie_rueckwaerts(conn):
    repo.setze_beantwortet_bis(conn, 1, 12)
    repo.setze_beantwortet_bis(conn, 1, 5)
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 12


def test_merke_aufruf_schreibt_die_richtigen_spalten(conn):
    repo.merke_aufruf(
        conn,
        chat_id=1,
        art="gespraech",
        modus="A",
        geschaetzte_token=100,
        tatsaechliche_token=110,
        antwort_token=42,
        finish_reason="stop",
        dauer_ms=987,
        erfolg=1,
    )
    row = conn.execute("SELECT * FROM aufruf").fetchone()
    assert row["chat_id"] == 1
    assert row["art"] == "gespraech"
    assert row["modus"] == "A"
    assert row["geschaetzte_token"] == 100
    assert row["tatsaechliche_token"] == 110
    assert row["antwort_token"] == 42
    assert row["finish_reason"] == "stop"
    assert row["dauer_ms"] == 987
    assert row["erfolg"] == 1
    assert row["erstellt_am"] is not None


def test_letzte_nachrichten_liefert_die_letzten_in_chronologischer_reihenfolge(conn):
    for message_id in range(1, 6):
        repo.merke_nachricht(conn, 1, message_id, "Ada", 0, "text", f"n{message_id}",
                              f"2026-09-05T10:0{message_id}:00")
    ergebnis = repo.letzte_nachrichten(conn, 1, anzahl=3)
    assert [r["message_id"] for r in ergebnis] == [3, 4, 5]


def test_szenen_kommen_in_szenenreihenfolge_zurueck(conn):
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt aus", "ELIF: Zu.")
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Da.")
    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 2]


def test_letzte_szene_ist_die_zuletzt_geaenderte_nicht_die_hoechste_nummer(conn):
    """SPEC § 6.2 Block 5. Der Fall, an dem eine sekundengenaue Zeitangabe
    scheitern wuerde: eine AELTERE Szene wird ueberarbeitet und hat dabei die
    kleinere id -- die Sortierung nach geaendert_am muss trotzdem sie
    liefern (repo._jetzt_genau)."""
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Alt.")
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt aus", "ELIF: Zu.")
    erste = repo.hole_szenen(conn, 1)[0]

    repo.aktualisiere_szene(conn, erste["id"], "Ankunft", "Maria kommt an", "MARIA: Neu.")

    letzte = repo.hole_letzte_szene(conn, 1)
    assert letzte["nummer"] == 1
    assert letzte["volltext"] == "MARIA: Neu."


def test_ohne_szene_gibt_es_keine_letzte(conn):
    assert repo.hole_letzte_szene(conn, 1) is None
    assert repo.hole_szenen(conn, 1) == []


def test_szenen_einer_anderen_gruppe_bleiben_draussen(conn):
    repo.sichere_gruppe(conn, 2, "gruppe1", "Zweite Gruppe")
    repo.lege_szene_an(conn, 2, 1, "Fremd", "andere Gruppe", "X: Y.")
    assert repo.hole_szenen(conn, 1) == []
    assert repo.hole_letzte_szene(conn, 1) is None


def test_sichere_gruppe_erzeugt_ein_web_token(conn):
    """Der Webserver liest read-only, also muss der Schreibpfad des Bots das
    Token anlegen -- sonst haette eine Gruppe nie eine erreichbare Seite."""
    token = repo.hole_gruppe(conn, 1)["web_token"]
    assert token
    assert len(token) >= 20, "muss lang genug sein, um nicht ratbar zu sein"


def test_web_token_bleibt_ueber_weitere_nachrichten_stabil(conn):
    """Die URL wird am Workshoptag herumgereicht: sie darf sich nicht bei
    jeder eingehenden Nachricht aendern."""
    erstes = repo.stelle_web_token_sicher(conn, 1)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Testgruppe umbenannt")
    assert repo.stelle_web_token_sicher(conn, 1) == erstes


def test_web_token_ist_je_gruppe_verschieden(conn):
    """Der ganze Zweck des Tokens: Gruppe 2 soll Gruppe 1 nicht lesen."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Zweite Gruppe")
    assert repo.stelle_web_token_sicher(conn, 1) != repo.stelle_web_token_sicher(conn, 2)


def test_web_token_fuer_unbekannte_gruppe_ist_none(conn):
    assert repo.stelle_web_token_sicher(conn, 999) is None


def test_web_token_wird_fuer_altbestand_nachgereicht(conn):
    """Gruppen, die vor der Weboberflaeche entstanden sind, haben NULL stehen
    -- der naechste Bot-Lauf muss das fuellen, ohne dass jemand eingreift."""
    conn.execute("UPDATE gruppe SET web_token = NULL WHERE chat_id = 1")
    conn.commit()
    assert repo.stelle_web_token_sicher(conn, 1)


def test_alle_gruppen_sieht_auch_fremde_bots(conn):
    """scripts/web_links.py laeuft neben den Bot-Prozessen und braucht alle
    Gruppen, nicht nur die eines Bots."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Zweite Gruppe")
    assert [z["chat_id"] for z in repo.alle_gruppen(conn)] == [1, 2]

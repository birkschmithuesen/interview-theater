"""Nachbesserung nach Aufgabe 10 (Code-Review-Befund 'Kritisch'): repo.py
serialisiert seit dieser Nachbesserung alle Zugriffe auf die geteilte
sqlite3.Connection ueber einen modulweiten ``threading.RLock``
(``repo._LOCK``/``repo._gesperrt``, siehe Moduldocstring in
``interview_theater/repo.py``).

Hintergrund: ``db.verbinde()`` oeffnet mit ``check_same_thread=False`` und
reicht EINE Connection an alle Threads eines Prozesses durch (Poll-Schleife,
8er-Pool, Nachhol-Thread, seit Aufgabe 10 auch jeder Gespraechszug). Ohne
Serialisierung fuehrt das unter echter Nebenlaeufigkeit sporadisch zu
``sqlite3.OperationalError: cannot commit - no transaction is active`` bzw.
``SystemError`` -- WAL und ``busy_timeout`` loesen nur die Dateisperre
ZWISCHEN Prozessen, nicht diese Racebedingung INNERHALB eines Prozesses.

Dieser Test belegt die Behebung unter mehreren Threads, die gleichzeitig
verschiedene Repo-Funktionen (lesend und schreibend) auf derselben
Verbindung aufrufen.
"""

import sqlite3
import threading

import pytest

from interview_theater import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_setze_uebersetzung_blockiert_keine_zweite_verbindung(conn, tmp_path):
    """Regression (Nacht-Lockfix, 07.10.2026): ``repo.setze_uebersetzung``
    schrieb (INSERT ... ON CONFLICT) ohne ``conn.commit()`` -- eine beim
    Zusammenfuehren der Internet-Recherche (Karte t_c5117c91) verschobene
    ``conn.commit()``-Zeile landete als totes Statement nach dem ``return``
    von ``entferne_recherche`` weiter unten in der Datei.

    Die offene Transaktion hielt den sqlite-Schreiblock auf der Datei, bis
    irgendein anderer Schreibvorgang im selben Prozess zufaellig mitcommittete
    -- oder, blieb der Prozess eine Weile ruhig, bis zum naechsten Neustart.
    Eine ZWEITE Verbindung (der Webserver-Prozess: eigene Verbindung je
    Anfrage, ``web_chat.schreibend``) erreichte in der Zwischenzeit nicht
    einmal ``BEGIN IMMEDIATE`` -- das Symptom war "database is locked" auf
    ``POST /g/<token>/chat/phase``.

    Dieser Test spiegelt genau das wider: nach ``setze_uebersetzung`` muss
    eine zweite, frische Verbindung auf dieselbe Datei sofort schreiben
    koennen, ohne auf ``busy_timeout`` zu warten."""
    repo.setze_uebersetzung(
        conn, 1, "hash1", {"rahmen": "a bridge"}, {"rahmen": "a bridge"},
    )

    zweite = sqlite3.connect(str(tmp_path / "t.db"), timeout=0.2)
    try:
        zweite.execute("BEGIN IMMEDIATE")
        zweite.execute(
            "INSERT INTO vorfall (chat_id, bot_name, art, detail, erstellt_am) "
            "VALUES (1, 'gruppe1', 'test', 'zweite-verbindung', '2026-01-01T00:00:00')"
        )
        zweite.commit()
    except sqlite3.OperationalError as fehler:
        pytest.fail(
            f"zweite Verbindung kam nicht ans Schreiben -- "
            f"setze_uebersetzung liess eine Transaktion offen: {fehler}"
        )
    finally:
        zweite.close()


def test_gleichzeitige_repo_aufrufe_verschiedener_funktionen_sind_sicher(conn):
    """Sechs Threads (Schreiben von Nachrichten/Vorfaellen/Aufnahmen, Lesen
    von unbeantwortete()/letzte_nachrichten()) laufen gleichzeitig auf
    derselben Connection. Keine Ausnahme darf auftreten, jeder Thread muss
    innerhalb des Timeouts fertig werden, und am Ende muss die erwartete
    Zeilenzahl stimmen -- eine verlorene oder doppelt gezaehlte Zeile waere
    das Zeichen einer Race."""
    anzahl_je_art = 20
    ausnahmen = []
    ausnahmen_lock = threading.Lock()

    def _bewache(fn):
        try:
            fn()
        except Exception as fehler:  # sammeln statt den Test still zu verschlucken
            with ausnahmen_lock:
                ausnahmen.append(fehler)

    def schreibe_nachrichten(start_id):
        def _tun():
            for i in range(anzahl_je_art):
                repo.merke_nachricht(
                    conn, 1, start_id + i, "Ada", 0, "text", f"Text {i}", repo._jetzt(),
                )
        _bewache(_tun)

    def schreibe_vorfaelle():
        def _tun():
            for i in range(anzahl_je_art):
                repo.merke_vorfall(conn, 1, "gruppe1", "test", f"Vorfall {i}")
        _bewache(_tun)

    def schreibe_aufnahmen():
        def _tun():
            for i in range(anzahl_je_art):
                # lege_aufnahme_an ruft intern zaehle_aufnahmen auf (derselbe
                # Thread, derselbe Lock) -- genau der Fall, der RLock statt
                # Lock erzwingt.
                repo.lege_aufnahme_an(conn, 1, 3000 + i, "kurz", "sprache")
        _bewache(_tun)

    def lies_waehrenddessen():
        def _tun():
            for _ in range(anzahl_je_art):
                repo.unbeantwortete(conn, 1)
                repo.letzte_nachrichten(conn, 1)
        _bewache(_tun)

    threads = [
        threading.Thread(target=schreibe_nachrichten, args=(1000,)),
        threading.Thread(target=schreibe_nachrichten, args=(2000,)),
        threading.Thread(target=schreibe_vorfaelle),
        threading.Thread(target=schreibe_aufnahmen),
        threading.Thread(target=lies_waehrenddessen),
        threading.Thread(target=lies_waehrenddessen),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    for t in threads:
        assert not t.is_alive(), "Thread nicht innerhalb des Timeouts fertig geworden"

    assert ausnahmen == [], f"Repo-Aufrufe duerfen unter Nebenlaeufigkeit nie werfen: {ausnahmen!r}"

    nachrichten = conn.execute(
        "SELECT count(*) FROM nachricht WHERE chat_id = 1 AND message_id >= 1000"
    ).fetchone()[0]
    assert nachrichten == 2 * anzahl_je_art, "zwei Schreiber, keine Zeile verloren oder doppelt"

    vorfaelle = conn.execute(
        "SELECT count(*) FROM vorfall WHERE chat_id = 1 AND art = 'test'"
    ).fetchone()[0]
    assert vorfaelle == anzahl_je_art

    aufnahmen = conn.execute("SELECT count(*) FROM aufnahme WHERE chat_id = 1").fetchone()[0]
    assert aufnahmen == anzahl_je_art


def test_lock_ist_reentrant_lege_aufnahme_an_ruft_zaehle_aufnahmen_auf(conn):
    """Ohne RLock (ein einfacher threading.Lock) wuerde dieser Aufruf den
    Thread beim zweiten acquire() selbst blockieren: lege_aufnahme_an haelt
    den Lock schon, wenn es intern zaehle_aufnahmen aufruft. Dieser Test
    schlaegt bei einem Lock-Typ-Regress als Timeout fehl, nicht als
    Assertion -- deshalb der explizite join-Timeout."""
    fertig = threading.Event()

    def _tun():
        repo.lege_aufnahme_an(conn, 1, 4000, "kurz", "sprache")
        fertig.set()

    t = threading.Thread(target=_tun)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), "Selbst-Deadlock: lege_aufnahme_an -> zaehle_aufnahmen braucht RLock"
    assert fertig.is_set()

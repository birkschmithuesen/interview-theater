"""QUICKFIX Birk, 07.10.2026 (Testgruppe Padua, chat_id 7000000000099, 07:16
UTC): zwei schnelle Phasenklicks (``/phaseklick 3`` dann ``/phaseklick 4``,
2 Sekunden auseinander) liefen als zwei asynchrone Erkennerlaeufe -- der
Lauf fuer den ERSTEN Klick kam erst NACH dem zweiten Klick zum Abschluss
und las dabei die eigene Bestaetigungszeile des ersten Klicks
("We're now at 3 ... ") als ``phase_setzen`` "3" zurueck, warf die Gruppe
von der inzwischen manuell gesetzten Phase 4 zurueck auf 3. journal belegt
das Ping-Pong: quelle='web' Phase 3, Phase 4, dann quelle='erkenner' Phase
3, Phase 4 -- alle vier Eintraege binnen 6 Sekunden.

Regel jetzt: ein ``phase_setzen``, das der Erkenner anwenden will, faellt
still weg, wenn die Phase kurz zuvor schon manuell (Klick oder Befehl)
gesetzt wurde -- der manuelle Weg ist die Gruppe selbst (AGENTS.md: "Die
Phase setzt allein die Gruppe"), ein nachlaufender Erkennerlauf auf
veraltetem Text darf das nicht wieder aufrollen.

Kein Netz, kein Modell."""

from datetime import datetime, timedelta, timezone

from interview_theater import erkenner, phasen, repo

from test_undo_knopf import LLMAttrappe, TelegramAttrappe  # noqa: F401

CHAT = 1


def _nachricht(conn, message_id, text, gesendet_am=None):
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "text", text,
                         gesendet_am or repo._jetzt())


def _laufe(conn, tg, einst, aenderungen):
    erkenner.laufe(LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, CHAT)


def test_ein_nachlaufender_erkennerlauf_ueberschreibt_keinen_frischen_klick(conn, einst):
    """Die Nachricht hinter dem ERSTEN Klick ist zehn Sekunden alt (sein
    Erkennerlauf haengt); die Gruppe hat in der Zwischenzeit manuell auf
    Phase 3 UND weiter auf 4 geklickt (quelle='web', beide ``jetzt``). Der
    nachlaufende Erkennerlauf liest auf dieser alten Nachricht
    ``phase_setzen`` "3" -- das darf die inzwischen manuell gesetzte Phase 4
    nicht mehr zuruecknehmen."""
    alt = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="seconds")
    _nachricht(conn, 1, "/phaseklick 3", gesendet_am=alt)
    phasen.setze(conn, CHAT, 3, "web")
    phasen.setze(conn, CHAT, 4, "web")
    tg = TelegramAttrappe()

    _laufe(conn, tg, einst, [{"art": "phase_setzen", "wert": "3"}])

    assert phasen.aktuelle(conn, CHAT) == 4


def test_ohne_frischen_manuellen_wechsel_wirkt_der_erkenner_normal(conn, einst):
    """Gegenprobe: ganz ohne vorherigen manuellen Klick darf der Erkenner
    die Phase weiterhin setzen -- das ist sein Alltagsgeschaeft."""
    phasen.setze(conn, CHAT, 2, "erkenner")
    tg = TelegramAttrappe()
    _nachricht(conn, 1, "let's move to phase 3 now")

    _laufe(conn, tg, einst, [{"art": "phase_setzen", "wert": "3"}])

    assert phasen.aktuelle(conn, CHAT) == 3

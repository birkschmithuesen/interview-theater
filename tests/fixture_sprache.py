"""Eine erfundene, englischsprachige Gruppe fuer die Sprachtests (Karte A1).

Alle Namen sind erfunden und stammen nicht aus dem Projektumfeld. Die
Absendernamen sind absichtlich ungewoehnlich genug, dass ein Teilstring-Test
sie in keinem Prompttext zufaellig findet.
"""

from datetime import datetime, timedelta, timezone

from interview_theater import repo

ABSENDER = ("Giulia", "Tomasz", "Amara")
AUFNAHMENAME = "Rosa"
_BASIS = datetime(2026, 10, 5, 9, 0, 0, tzinfo=timezone.utc)


def _zeit(minuten: int) -> str:
    return (_BASIS + timedelta(minutes=minuten)).isoformat(timespec="seconds")


def baue_englische_gruppe(conn, chat_id: int = 1) -> str:
    repo.sichere_gruppe(conn, chat_id, "gruppe1", "Test group")
    stand = {
        "begriffe": "belonging, family, noise, courage",
        "fragen": "1. Where do you feel at home?\n2. Who do you argue with?\n3. What gives you courage?",
        "interview_eroeffnung": "Hi, we are a youth theatre group making a play about this city.",
        "interview_abschluss": "Thank you - your story will become part of a scene.",
        "rahmen": "A bus stop at night, two sisters wait for the last bus.",
        "geschichte": "Nadia wants to leave, Tomas wants her to stay. In the end she stays one more night.",
    }
    for feld, wert in stand.items():
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    repo.setze_figur(conn, chat_id, "Nadia", "the older sister, restless")
    repo.setze_figur(conn, chat_id, "Tomas", "the younger brother, stubborn")
    repo.setze_phase(conn, chat_id, 6)
    for nummer, (titel, text) in enumerate([
        ("Last bus", "NADIA: I'm going.\nTOMAS: You always say that."),
        ("One more night", "TOMAS: Stay.\nNADIA: One night. Then we'll see."),
    ], start=1):
        repo.lege_szene_an(conn, chat_id, nummer, titel, None, text)
    # Wie tests/fixture_spaetstand.py: quelle "sprache", status gleich "fertig".
    aufnahme_id = repo.lege_aufnahme_an(conn, chat_id, 10, "lang", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "Allora, I grew up above a bakery. Home is the smell of bread.")
    repo.setze_aufnahme_name(conn, aufnahme_id, AUFNAHMENAME)
    repo.speichere_verdichtung(conn, chat_id, aufnahme_id, "She talks about home and the bakery.", [
        {"thema": "home", "beleg_zitat": "Home is the smell of bread.", "zitat_geprueft": 1, "kurz": "home"},
    ])
    message_id = 100
    for runde in range(6):
        for absender in ABSENDER:
            message_id += 1
            repo.merke_nachricht(conn, chat_id, message_id, absender, 0, "text",
                                 f"Idea number {runde}: the bus is late again.",
                                 _zeit(message_id))
        message_id += 1
        repo.merke_nachricht(conn, chat_id, message_id, "gruppe1", 1, "text",
                             "Noted. What happens when the bus finally comes?", _zeit(message_id))
    return repo.stelle_web_token_sicher(conn, chat_id)

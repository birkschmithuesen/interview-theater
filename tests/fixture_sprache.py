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


#: Die Formwerte, die ``baue_volle_englische_gruppe`` auf die Szenen legt --
#: genau die drei, deren Datenbankwert ein deutsches Wort ist (Nachbesserung
#: zu Aufgabe 30): in einer Anzeige muessen sie als englischer Name stehen.
FORMEN_DEUTSCHES_WORT = ("chor", "lied", "monolog")


def baue_volle_englische_gruppe(conn, chat_id: int = 1) -> str:
    """``baue_englische_gruppe`` plus alles, was die Gruppenseite nur mit
    Daten zeigt: Formen (``chor``/``lied``/``monolog``) samt Formvorschlag
    und Stil, Besetzung, Festlegungen, Journaleintraege jeder Art, zwei
    Fassungen einer Szene, Sprecherzeilen (Sprechanteile), Befunde der
    Stueck- und der Dramaturgie-Pruefung, eine Schaerfung. Alles erfunden
    und englisch -- ein deutsches Wort im gerenderten Text kommt aus dem
    Code, nicht aus der Fixture."""
    token = baue_englische_gruppe(conn, chat_id)
    dritte = repo.lege_szene_an(conn, chat_id, 3, "Morning", None,
                                "NADIA: (alone) The bus never came.")
    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, chat_id)}
    for nummer, form in zip((1, 2, 3), FORMEN_DEUTSCHES_WORT):
        repo.setze_szenenfeld(conn, szenen[nummer]["id"], "form", form)
    repo.setze_szenenfeld(conn, szenen[2]["id"], "stil", "litanei")
    repo.setze_szenenfeld(conn, szenen[1]["id"], "ort", "the bus stop")
    repo.setze_szenenfeld(conn, szenen[1]["id"], "was_passiert", "Nadia says she is leaving.")
    vierte = repo.lege_szene_an(conn, chat_id, 4, "Dawn", None, None)
    repo.setze_szenenfeld(conn, vierte, "form_vorschlag", "lied")
    repo.setze_szenenfeld(conn, vierte, "form_vorschlag_grund", "The ending needs a song.")
    figuren = {f["name"]: f["id"] for f in repo.figuren(conn, chat_id)}
    for nummer in (1, 2):
        repo.setze_szene_figuren(conn, chat_id, szenen[nummer]["id"], list(figuren.values()))
    repo.setze_szene_figuren(conn, chat_id, dritte, [figuren["Nadia"]])
    # Zwei Fassungen von Szene 1: die Fassungsleiste steht erst ab zwei.
    repo.haenge_szenenfassung_an(conn, chat_id, szenen[1]["id"], "NADIA: I'm leaving.\nTOMAS: Sure.")
    repo.haenge_szenenfassung_an(conn, chat_id, szenen[1]["id"], szenen[1]["volltext"])
    for bereich, text in (("figur", "Nadia is nineteen."), ("struktur", "Only one scene per location."),
                          ("form", "At most one song."), ("sonstiges", "Nobody dies.")):
        repo.schreibe_festlegung(conn, chat_id, bereich, text, quelle="befehl")
    for art in ("vorgeschlagen", "verworfen", "entschieden", "offen", "notiert"):
        repo.schreibe_journal(conn, chat_id, art, f"The group talked about the bus, round {len(art)}.",
                              quelle="befehl")
    repo.lege_stueckpruefung_an(conn, chat_id, [
        {"frage": "Spannungsbogen", "bewertung": 3, "begruendung": "The middle sags.",
         "vorschlag": "Cut scene 2 short.", "szene_nummer": 2},
    ])
    repo.lege_dramaturgie_befunde_an(conn, chat_id, [
        {"pruefung": "b1", "szene": 1, "schwere": "hoch", "text": "Scene 1 does not turn.",
         "beleg": "NADIA: I'm going.", "beleg_geprueft": 1,
         "vorschlag": "Scene 1: Nadia should say why she is going.", "quelle": "judge"},
        {"pruefung": "sprechanteil", "figur": "Tomas", "schwere": "mittel",
         "text": "Tomas speaks very little.", "quelle": "mechanik"},
        {"pruefung": "a10", "szene": 1, "schwere": "mittel", "text": "The place changed.",
         "vorschlag": "ort: the old station", "richtung": "parameter", "quelle": "judge",
         "beleg": "NADIA: I'm going.", "beleg_geprueft": 1},
    ])
    thema = conn.execute("SELECT id FROM verdichtung_thema WHERE chat_id = ?", (chat_id,)).fetchone()
    repo.lege_schaerfung_an(conn, chat_id, [
        {"verdichtung_thema_id": thema["id"], "szene_id": szenen[1]["id"],
         "figur_id": figuren["Nadia"], "begruendung": "Home is what she leaves."},
    ])
    return token

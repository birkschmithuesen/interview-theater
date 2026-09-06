"""Die Spaetstand-Fixture: eine Gruppe im Zustand, in dem die Fehler sichtbar sind.

Herausgeloest aus ``tests/test_prompt_audit.py`` (06.09.2026, Auftrag 5), damit
``scripts/kontext_recall.py`` gegen **dieselbe** Gruppe messen kann wie die
Prompt-Audit-Tests. Eine zweite, handgeschriebene Fixture waere eine zweite
Wahrheit -- und genau das ist der Fehlertyp, den der Audit ueberall gefunden hat.
"""

from datetime import datetime, timedelta, timezone

from interview_theater import repo

BASIS = datetime(2026, 9, 6, 0, 33, 0, tzinfo=timezone.utc)


def _iso(versatz_minuten: int) -> str:
    return (BASIS + timedelta(minutes=versatz_minuten)).isoformat(timespec="seconds")


def baue_spaetstand(conn):
    """Eine Gruppe im Spaetstand: Phase 7, vier Figuren, vier Szenen, ein
    gewuchertes Journal, ein langer Verlauf und ein Interview mit vielen
    markierten Themen.

    Das ist der Stand, an dem die Fehler sichtbar werden. Eine frische
    Datenbank zeigt keinen davon -- deshalb hat der Audit-Befund so lange
    ueberlebt: die Tests liefen alle gegen den Vormittag."""
    repo.sichere_gruppe(conn, 1, "gruppe4", "Testgruppe")

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe, Spass, Streit")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "ungluecklich verliebt sein und Rassismus")
    repo.setze_arbeitsstand(conn, 1, "kernfrage", "Was haelt uns bei jemandem, der uns kleinmacht?")
    repo.setze_arbeitsstand(
        conn, 1, "rahmen",
        "Vier Freundinnen leben im Nordkiez in Dortmund. Eine ist ungluecklich "
        "verliebt in einen rassistischen Typen; die anderen wollen sie ueberzeugen.",
    )
    repo.setze_arbeitsstand(
        conn, 1, "geschichte",
        "Leyla haelt an einem Jungen fest, der sie kleinmacht. Die drei Freundinnen "
        "versuchen erst zu reden, dann zu draengen, dann zu schweigen. Am Ende "
        "bleibt Leyla stehen und entscheidet zum ersten Mal selbst.",
    )
    repo.setze_phase(conn, 1, 7)

    # Ein Interview mit einer langen Zusammenfassung und vielen Themen: genau
    # die Lage, in der die Zusammenfassung elfmal in den Prompt geriet.
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "T" * 400)
    zusammenfassung = (
        "Die befragte Person erzaehlt von ihrer Freundin, der in der Bahn das "
        "Kopftuch abgezogen wurde, und raet Betroffenen, sich keine Gedanken zu "
        "machen. Sie streitet regelmaessig mit ihrem Bruder, der ihre Sachen "
        "ohne Fragen nimmt. Liebe hat sie noch nie bewusst erlebt."
    )
    themen = [
        {"thema": thema, "beleg_zitat": f"Beleg {i}", "zitat_geprueft": 1,
         "kurz": f"kurz {i}"}
        for i, thema in enumerate(
            ["Rassismus", "Rassismus", "Rassismus", "Streit", "Streit", "Streit",
             "Liebe", "Liebe", "Spass", "Spass", "Spass"]
        )
    ]
    verdichtung_id = repo.speichere_verdichtung(conn, 1, aufnahme_id, zusammenfassung, themen)
    repo.markiere_themen_zum_kernthema(
        conn, 1, [t["id"] for t in repo.themen_zu(conn, verdichtung_id)]
    )

    for name, beschreibung, profil in (
        ("Leyla", "will, dass die Liebe reicht", "Kurze Saetze, bricht ab."),
        ("Cemre", "will ihre Freundin retten", "Direkt, laesst nicht locker."),
        ("Aylin", "will den Frieden halten", "Lange Schachtelsaetze, weicht aus."),
        ("Zeynep", "will Fairness in der Familie", "Nennt Zahlen und Uhrzeiten."),
    ):
        repo.setze_figur(conn, 1, name, beschreibung)
        repo.setze_sprachprofil(
            conn, repo.hole_figur(conn, 1, name)["id"], profil, zitate=[]
        )

    szene_id = repo.lege_szene_an(
        conn, 1, 1, "Einundfuenfzig Stunden",
        "Leyla wartet auf dem Schulhof auf eine Antwort.",
        "LEYLA: Gelesen.\n\nCEMRE: Sie geht nicht.\n",
    )
    for feld, wert in (("form", "dialog"), ("ort", "Schulhof"),
                       ("zeit", "Freitagnachmittag")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    for nummer in (2, 3, 4):
        repo.lege_szene_an(conn, 1, nummer, None, None, None)

    # Ein Journal wie am 06.09.: mit vierfacher Dublette.
    for art, text in (
        ("entschieden", "Begriffe: Rassismus, Liebe, Spass, Streit"),
        ("entschieden", "Phase 4 · Setting & Figuren"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("vorgeschlagen", "Leyla will, dass die Liebe reicht, basierend auf Interview 1."),
        ("vorgeschlagen", "Cemre will ihre Freundin retten, basierend auf Interview 1."),
        ("vorgeschlagen", "Aylin will den Frieden halten, basierend auf Interview 1."),
        ("vorgeschlagen", "Zeynep will Fairness, basierend auf Interview 1."),
        ("entschieden", "Szene 1 neu geplant: Dialog am Kiosk, Exposition der vier."),
    ):
        repo.schreibe_journal(conn, 1, art, text, quelle="befehl")

    # Ein langer Verlauf: 400 Nachrichten, wie er ueber zwei Workshoptage
    # entsteht. Ohne ihn greift keine Kuerzung.
    for i in range(400):
        repo.merke_nachricht(
            conn, 1, 100 + i, "Bot" if i % 2 else "Birk", i % 2, "text",
            f"Ein laengerer Gespraechsbeitrag ueber Szene 1 und die Figuren, Nummer {i}.",
            _iso(i),
        )
    return conn

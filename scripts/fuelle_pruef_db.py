"""Bringt eine KOPIE der Test-DB auf den Stand, den Birk am 06.09. 00:33 gemessen hat.

Die ausgelieferte ``betrieb/test.db`` ist ein fruehes Abbild (Phase 3, keine
Figuren, keine Szenen, zwei Journalzeilen). Die gravierenden Befunde des
Prompt-Audits -- Dubletten, Journal-Wucherung, Phasen-Widerspruch, Laenge --
zeigen sich erst an einem spaeten Stand. Dieses Skript stellt ihn her:
Arbeitsstand, vier Figuren, vier Szenen, ein Journal mit den gemessenen
Dubletten, ein langer Gespraechsverlauf.

**Nur gegen eine Kopie laufen lassen** (``cp betrieb/test.db /tmp/...``).
Es schreibt. Aufruf::

    IT_DB=/tmp/prompt-audit.db python -m scripts.fuelle_pruef_db
"""

import os

from interview_theater import db

#: Der Journalstand vom 06.09. 00:33 -- mit den Dubletten, die er hatte.
JOURNAL = [
    ("entschieden", "Begriffe: Rassismus, Liebe, Spass, Streit"),
    ("entschieden", "Phase 3 · Interviews (nachgetragen: Gruppe interviewte am 05.09., Feld war nie gesetzt)"),
    ("entschieden", "Phase 4 · Setting & Figuren"),
    ("entschieden", "Phase 7 · Szenentexte"),
    ("entschieden", "Setting: Leyla checkt ihr Handy auf dem Schulhof, die anderen beobachten sie von weitem"),
    ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
    ("entschieden", "Setting zurueckgesetzt auf die Fassung von 21:37 (Vier Freundinnen im Nordkiez ...) - ein Knopfdruck um 21:50 hatte es mit einem Szenenbild ueberschrieben"),
    ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
    ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
    ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
    ("vorgeschlagen", "Leyla will, dass die Liebe reicht, auch wenn es wehtut, basierend auf Interview 1."),
    ("vorgeschlagen", "Cemre will ihre Freundin retten, bevor es zu spaet ist, basierend auf Interview 1."),
    ("vorgeschlagen", "Aylin will den Frieden in der Gruppe halten, basierend auf Interview 1."),
    ("vorgeschlagen", "Zeynep will, dass Fairness auch in der eigenen Familie gilt, basierend auf Interview 1."),
    ("entschieden", "Szene 1 neu geplant (Regie, Birk 06.09. 00:32): Dialog am Kiosk, Exposition der vier Freundinnen und des Konflikts"),
]

FIGUREN = [
    ("Leyla", "will, dass die Liebe reicht, auch wenn es wehtut",
     "Kurze Saetze, bricht mitten im Satz ab, wiederholt sich, wenn sie unsicher ist."),
    ("Cemre", "will ihre Freundin retten, bevor es zu spaet ist",
     "Direkt, fragt nach, laesst nicht locker; wenig Fuellwoerter."),
    ("Aylin", "will den Frieden in der Gruppe halten",
     "Lange Schachtelsaetze, viele 'wir koennen ja auch', weicht aus."),
    ("Zeynep", "will, dass Fairness auch in der eigenen Familie gilt",
     "Nennt Zahlen und Uhrzeiten, argumentiert mit Beispielen aus der Familie."),
]

SZENEN = [
    (1, "Einundfuenfzig Stunden",
     "Leyla wartet auf dem Schulhof auf eine Antwort, die nicht kommt, waehrend ihre drei Freundinnen hinter ihr stehen.",
     "Schulhof", "Freitagnachmittag", "dialog"),
    (2, None, None, None, None, None),
    (3, None, None, None, None, None),
    (4, None, None, None, None, None),
]

RAHMEN = (
    "Vier Freundinnen leben im Nordkiez in Dortmund. Eine ist unglaeubig verliebt "
    "in einen rassistischen Typen; die anderen Freundinnen spueren das und wollen "
    "sie ueberzeugen, dass er nicht cool ist. Es gibt viel Streit, aber auch Spass "
    "und humorvolle Szenen unter den Freundinnen."
)

GESCHICHTE = (
    "Leyla haelt an einem Jungen fest, der sie kleinmacht. Die drei Freundinnen "
    "versuchen erst zu reden, dann zu draengen, dann zu schweigen. Am Ende geht "
    "Leyla nicht mit ihm mit - aber auch nicht mit ihnen: sie bleibt stehen und "
    "entscheidet zum ersten Mal selbst."
)

SZENENTEXT = """(Schulhof, Nachmittag. Leyla vorn, das Handy in beiden Haenden.)

LEYLA: (zum Handy) Gelesen. Steht klein drunter, grau. Gelesen.

AYLIN: Leyla. Der Bus ist weg, der Naechste kommt in zwoelf Minuten.

CEMRE: Sie geht nicht.

ZEYNEP: Mein Bruder ist gestern um halb zwoelf reingekommen. Keiner fragt ihn was.

LEYLA: Er hat viel um die Ohren.

ZEYNEP: Einundfuenfzig Stunden.

(Die drei bleiben stehen.)
"""

VERLAUF = [
    ("Izan", "Kannst du die ganzen Fragen anders formulieren?"),
    ("Du", "Izan, bist du bei der Formulierung oder bei der Struktur unzufrieden?"),
    ("Izan", "Also ich bin unzufrieden damit"),
    ("Du", "Izan, klar. Was stoert dich genau? Die Wortwahl oder die Reihenfolge?"),
    ("Izan", "Wir machen ein Interview"),
    ("Du", "Gut, dann los. Drueckt unten auf 'Aufnahme starten' und legt los."),
    ("Du", "Aufnahme laeuft. Sprecht eure Sprachnachrichten ein."),
    ("JAYJAY", None),
    ("Du", "Interview 3 ist sehr kurz (1 s, 4 Woerter). Ich werte es nicht von selbst aus."),
    ("JAYJAY", None),
    ("Du", "Interview 4 ist aufgenommen und ausgewertet."),
    ("Du", "Bin wieder da. Wir sind bei 1 · Begriffe. Wenn ihr weitermachen wollt, sagt mir Bescheid."),
    ("Du", "Bin wieder da. Wir sind bei 1 · Begriffe. Wenn ihr weitermachen wollt, sagt mir Bescheid."),
    ("Birk", "Warum soll sie ausweichen zur Bushaltestelle oder zum Kiosk?"),
    ("Du", "Birk, dann schlag ich vor: Leyla wartet am Schulhof-Tor auf den Typen."),
    ("Birk", "Du hast nicht auf meine Frage geantwortet und das doppelt sich ueberall."),
    ("Du", "Birk, sorry - du hast recht. Ich wiederhole mich. Das war ein Fehler auf meiner Seite."),
    ("Birk", "neu schreiben"),
    ("Du", "Birk, klar - Szene 1 neu. Soll der Typ wirklich kommen?"),
    ("Birk", "wo bist du? es muesste jetzt szenen geschrieben werden. wir haben gerade die reihenfolge festgelegt"),
]


def fuelle(conn, chat_id: int) -> None:
    jetzt = "2026-09-06T00:33:00+00:00"
    conn.execute(
        "UPDATE arbeitsstand SET phase = 7, phase_angeboten = 7, kernthema = ?, "
        "kernfrage = ?, rahmen = ?, geschichte = ?, hauptkonflikt = ? WHERE chat_id = ?",
        (
            "unglaeubig verliebt sein und Rassismus",
            "Was haelt uns bei jemandem, der uns kleinmacht?",
            RAHMEN, GESCHICHTE,
            "Leyla gegen ihre drei Freundinnen: Liebe gegen Loyalitaet",
            chat_id,
        ),
    )
    conn.execute("DELETE FROM figur WHERE chat_id = ?", (chat_id,))
    for i, (name, beschreibung, profil) in enumerate(FIGUREN, start=1):
        conn.execute(
            "INSERT INTO figur (id, chat_id, name, beschreibung, sprachprofil, "
            "quelle_aufnahme_id, geaendert_am) VALUES (?, ?, ?, ?, ?, NULL, ?)",
            (i, chat_id, name, beschreibung, profil, jetzt),
        )
    conn.execute("DELETE FROM szene WHERE chat_id = ?", (chat_id,))
    for i, (nummer, titel, kurz, ort, zeit, form) in enumerate(SZENEN, start=1):
        conn.execute(
            "INSERT INTO szene (id, chat_id, nummer, titel, kurzbeschreibung, "
            "volltext, ort, zeit, form, geaendert_am) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, chat_id, nummer, titel, kurz,
             SZENENTEXT if nummer == 1 else None, ort, zeit, form, jetzt),
        )
    conn.execute("DELETE FROM journal WHERE chat_id = ?", (chat_id,))
    for i, (art, text) in enumerate(JOURNAL, start=1):
        conn.execute(
            "INSERT INTO journal (id, chat_id, art, text, quelle, erstellt_am) "
            "VALUES (?, ?, ?, ?, 'knopf', ?)",
            (i, chat_id, art, text, jetzt),
        )
    # Themen ans Kernthema haengen, damit das Kernpaket traegt.
    conn.execute("UPDATE verdichtung_thema SET zum_kernthema_am = ? WHERE chat_id = ?",
                 (jetzt, chat_id))
    # Ein langer Verlauf: die 20 Zeilen zwanzigmal, damit die Kuerzung greift.
    hoechste = conn.execute(
        "SELECT COALESCE(MAX(message_id), 0) FROM nachricht WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    mid = hoechste + 1
    minute = 0
    for runde in range(20):
        for absender, text in VERLAUF:
            stunde, rest = divmod(minute, 60)
            conn.execute(
                "INSERT INTO nachricht (chat_id, message_id, absender, telegram_user, "
                "text, typ, ist_bot, gesendet_am) VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (chat_id, mid, "Bot" if absender == "Du" else absender,
                 text, "text" if text else "sprache", 1 if absender == "Du" else 0,
                 f"2026-09-05T{6 + stunde // 60:02d}:{stunde % 60:02d}:{rest:02d}+00:00"),
            )
            mid += 1
            minute += 1
    conn.execute(
        "UPDATE gruppe SET letzte_beantwortete_message_id = ?, "
        "letzte_extrahierte_message_id = ?, letzte_journalisierte_message_id = ? "
        "WHERE chat_id = ?", (mid - 2, mid - 2, mid - 2, chat_id),
    )
    conn.commit()


def main() -> None:
    pfad = os.environ["IT_DB"]
    assert "test.db" not in pfad, "nie gegen betrieb/test.db selbst laufen lassen"
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    chat_id = conn.execute(
        "SELECT chat_id FROM nachricht GROUP BY chat_id ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()[0]
    fuelle(conn, chat_id)
    print(f"Pruef-DB gefuellt: {pfad}, chat_id={chat_id}")


if __name__ == "__main__":
    main()

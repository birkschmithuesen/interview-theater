"""Zusammenbau des Gespraechs-Prompts (SPEC-kontext-architektur.md § 6, § 7).

**Datengetrieben statt aufgabengetrieben.** Es gibt keine
Phasen-Zustandsmaschine: jeder Block unten wird schlicht weggelassen, solange
die zugrundeliegenden Daten leer sind. Am Samstagvormittag gibt es Begriffe
und sonst nichts -- also enthaelt der Prompt Begriffe und sonst nichts.
Biegt die Gruppe ab, aendert sich die Materiallage und der Prompt folgt
automatisch; es gibt keinen Zustand, der ihr widersprechen koennte.

**Reihenfolge: stabil nach vorn, fluechtig nach hinten** --
``verdichtungen, transkripte, arbeitsstand, journal, fenster, ausloeser``.
Begruendet einzig mit der Aufmerksamkeitsverteilung des Modells: was am Ende
des Prompts steht, wiegt am schwersten und soll deshalb das Aktuellste sein.
Kein Caching-Argument: in den Messlaeufen gegen Infomaniak steht in jeder
Antwort ``prompt_tokens_details: null`` -- unbelegt und deshalb nirgends als
Begruendung verwendet (§ 6.1).

Szenen bleiben im Durchstich aussen vor: der Block "aktuelle Szene im
Volltext" und der Befehl ``/szene`` gehoeren zu einer spaeteren
Workshop-Phase und sind hier bewusst nicht eingebaut.
"""

from datetime import datetime
from pathlib import Path

from theatersoap import repo

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: theatersoap/prompts/system.md). Wird der Sprachmodell-Anfrage getrennt vom
#: Rueckgabewert von baue() als ``system``-Feld mitgegeben (vgl.
#: theatersoap.llm.LLM.schema/.prosa).
SYSTEM = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

#: Kein Tokenizer -- zwei Tage vor dem Workshop keine Abhaengigkeit, die sich
#: fuer Kimi nicht sauber verifizieren laesst. Zeichen ÷ 3 ueberschaetzt bei
#: deutschen Komposita leicht die Tokenzahl -- die richtige Fehlerrichtung:
#: lieber zu frueh kuerzen als zu spaet (§ 7.1).
_ZEICHEN_JE_TOKEN = 3

#: Budgets in Token je Block (SPEC § 6.2). Nur informativ/als Fuellgrenze fuer
#: das Fenster verwendet -- die Kuerzung selbst kennt nur zwei Schritte
#: (§ 7.2), keine fuenfstufige Leiter. Szene fehlt bewusst: sie bleibt im
#: Durchstich aussen vor.
BUDGETS = {
    "system": 900,
    "verdichtungen": 3000,
    "transkripte": 5000,
    "arbeitsstand": 1200,
    "journal": 1500,
    "fenster": 2500,
    "ausloeser": 300,
}

#: Zielgroesse Normalfall und Reissleine, in Token (§ 6.2, § 7.2).
ZIEL = 10_000
REISSLEINE = 20_000

#: Ab dieser Zeitspanne zwischen zwei Nachrichten im Fenster wird eine
#: Pausenzeile eingeschoben (§ 6.2 "Pausenmarkierung").
PAUSE_AB_MINUTEN = 60

#: Feste Reihenfolge des Prompt-Koerpers (ohne SYSTEM, das separat verschickt
#: wird): stabil nach vorn, fluechtig nach hinten.
_REIHENFOLGE = ("verdichtungen", "transkripte", "arbeitsstand", "journal", "fenster", "ausloeser")


def schaetze(text: str) -> int:
    """Schaetzt die Tokenzahl eines Textes: Zeichen ÷ 3, kein Tokenizer (§ 7.1)."""
    return len(text) // _ZEICHEN_JE_TOKEN


def sprecherzeile(n) -> str:
    """Formatiert eine ``nachricht``-Zeile als ``"Sprecher: Text"``.

    Bot-Nachrichten erscheinen als Sprecher ``Du``: das Sprachmodell bekommt
    den Verlauf als einen zusammenhaengenden Text, nicht als mehrteiligen
    Chat mit eigener Rolle je Zug, und liest darin seine eigenen frueheren
    Aeusserungen in der zweiten Person. Menschliche Nachrichten tragen den
    Vornamen aus ``nachricht.absender``.

    Nachrichten ohne Text (Sprache ohne Transkript, Foto, Sticker, ...)
    erscheinen als ``"Name: (typ)"`` statt als leere Zeile -- die Gruppe hat
    etwas geschickt, und das Modell soll das wissen.
    """
    sprecher = "Du" if n["ist_bot"] else n["absender"]
    text = n["text"]
    if text:
        return f"{sprecher}: {text}"
    return f"{sprecher}: ({n['typ']})"


def _pausenzeile(vorher_iso: str, nachher_iso: str) -> str | None:
    """Baut ``"[Pause: N Stunden]"``, wenn zwischen zwei Zeitstempeln mehr als
    PAUSE_AB_MINUTEN liegen -- sonst None. Die Zeitstempel sind ISO-8601 mit
    Zeitzone (repo._jetzt()); datetime.fromisoformat vergleicht sie ueber
    Zeitzonen hinweg korrekt, ohne dass wir selbst normalisieren muessten."""
    vorher = datetime.fromisoformat(vorher_iso)
    nachher = datetime.fromisoformat(nachher_iso)
    minuten = (nachher - vorher).total_seconds() / 60
    if minuten <= PAUSE_AB_MINUTEN:
        return None
    stunden = max(1, round(minuten / 60))
    einheit = "Stunde" if stunden == 1 else "Stunden"
    return f"[Pause: {stunden} {einheit}]"


def _baue_verdichtungen(conn, chat_id: int) -> str:
    bloecke = []
    for v in repo.verdichtungen(conn, chat_id):
        aufnahme = repo.hole_aufnahme(conn, v["aufnahme_id"])
        name = aufnahme["name"] if aufnahme else f"Aufnahme {v['aufnahme_id']}"
        zeilen = [f"{name}: {v['zusammenfassung']}"]
        for thema in repo.themen_zu(conn, v["id"]):
            if thema["beleg_zitat"]:
                zeilen.append(f'  - {thema["thema"]}: "{thema["beleg_zitat"]}"')
            else:
                zeilen.append(f'  - {thema["thema"]}')
        bloecke.append("\n".join(zeilen))
    if not bloecke:
        return ""
    return "Verdichtungen:\n" + "\n\n".join(bloecke)


def _baue_transkripte(conn, chat_id: int) -> str:
    """Volltranskripte, sofern welche existieren.

    Kein ``/wortlaut``-Schalter: der Befehl kommt erst in einer spaeteren
    Aufgabe (Auftragshinweis). Solange es ihn nicht gibt, entscheidet allein
    die Materiallage -- ein vorhandenes Transkript geht mit, ein fehlendes
    nicht. Das gilt es zu ueberpruefen, sobald ``/wortlaut`` eingefuehrt wird.
    """
    zeilen = []
    for a in repo.transkripte(conn, chat_id):
        if a["transkript"]:
            zeilen.append(f"--- {a['name']} (Volltranskript) ---\n{a['transkript']}")
    if not zeilen:
        return ""
    return "Volltranskripte:\n" + "\n\n".join(zeilen)


def _baue_arbeitsstand(conn, chat_id: int) -> str:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)

    zeilen = []
    if stand:
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
        if stand["kernthema"]:
            zeile = f"Kernthema: {stand['kernthema']}"
            if stand["kernthema_begruendung"]:
                zeile += f" (Begruendung: {stand['kernthema_begruendung']})"
            zeilen.append(zeile)
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(f"Figur {figur['name']}{beschreibung}")

    if not zeilen:
        return ""
    return "Arbeitsstand:\n" + "\n".join(zeilen)


def _baue_journal(conn, chat_id: int) -> str:
    eintraege = repo.journal(conn, chat_id)
    if not eintraege:
        return ""
    zeilen = [f"- [{e['art']}] {e['text']}" for e in eintraege]
    return "Journal:\n" + "\n".join(zeilen)


def _baue_fenster(conn, chat_id: int, ausloeser) -> str:
    """Die letzten Nachrichten vor der ausloesenden, von hinten gefuellt bis
    zum Budget aus BUDGETS["fenster"] (in Token, hier in Zeichen umgerechnet).
    Mit Pausenmarkierung, sofern zwischen zwei aufeinanderfolgenden
    Nachrichten mehr als PAUSE_AB_MINUTEN liegen (§ 6.2)."""
    ausloeser_ids = {n["message_id"] for n in ausloeser}
    kandidaten = [
        n for n in repo.letzte_nachrichten(conn, chat_id, anzahl=1000)
        if n["message_id"] not in ausloeser_ids
    ]

    zeichen_budget = BUDGETS["fenster"] * _ZEICHEN_JE_TOKEN
    gewaehlt = []
    laenge = 0
    for n in reversed(kandidaten):
        zeile = sprecherzeile(n)
        zusatz = len(zeile) + 1
        if gewaehlt and laenge + zusatz > zeichen_budget:
            break
        gewaehlt.append(n)
        laenge += zusatz
    gewaehlt.reverse()

    zeilen = []
    vorherige_zeit = None
    for n in gewaehlt:
        if vorherige_zeit is not None:
            pause = _pausenzeile(vorherige_zeit, n["gesendet_am"])
            if pause:
                zeilen.append(pause)
        zeilen.append(sprecherzeile(n))
        vorherige_zeit = n["gesendet_am"]
    return "\n".join(zeilen)


def _baue_ausloeser(ausloeser) -> str:
    """Die ausloesende(n) Nachricht(en) -- ueberlebt jede Kuerzung (§ 7.2),
    darum von der Kuerzungslogik in baue() nie angefasst."""
    if not ausloeser:
        return ""
    zeilen = [sprecherzeile(n) for n in ausloeser]
    return "Aktuell:\n" + "\n".join(zeilen)


def _zusammen(bloecke: dict) -> str:
    """Fuegt die nichtleeren Bloecke in der festen Reihenfolge zusammen."""
    return "\n\n".join(bloecke[k] for k in _REIHENFOLGE if bloecke.get(k))


def _fenster_beschneiden(fenster: str) -> str:
    """Schneidet die aelteste Zeile des Fensters ab (§ 7.2: von vorn
    beschneiden). Leeres Ergebnis, wenn nichts mehr uebrig ist -- das ist der
    Abbruch fuer die while-Schleife in baue()."""
    zeilen = fenster.split("\n")
    return "\n".join(zeilen[1:])


def baue(conn, chat_id: int, ausloeser, e) -> str:
    """Baut den Koerper des Gespraechs-Prompts (ohne SYSTEM, das getrennt
    verschickt wird).

    ``ausloeser`` ist die Liste der Nachrichten, die diesen Zug ausgeloest
    haben (alles seit ``letzte_beantwortete_message_id``, § 1.3) -- vom
    Aufrufer ermittelt, hier nur formatiert.

    Passt der Koerper nicht ins Zielbudget ZIEL, greift die zweistufige
    Kuerzung aus § 7.2: erst fliegen die Volltranskripte ganz raus, dann wird
    das Fenster von vorn beschnitten, bis es passt oder leer ist. Die
    Notbremse -- Systemanweisung, Arbeitsstand, Fenster, ausloesende
    Nachricht -- wird dabei nie angetastet: Arbeitsstand und Ausloeser sind
    von der Kuerzung grundsaetzlich ausgenommen, es gibt keinen Zustand, in
    dem der Bot wegen des Budgets nicht antworten koennte."""
    bloecke = {
        "verdichtungen": _baue_verdichtungen(conn, chat_id),
        "transkripte": _baue_transkripte(conn, chat_id),
        "arbeitsstand": _baue_arbeitsstand(conn, chat_id),
        "journal": _baue_journal(conn, chat_id),
        "fenster": _baue_fenster(conn, chat_id, ausloeser),
        "ausloeser": _baue_ausloeser(ausloeser),
    }

    if schaetze(_zusammen(bloecke)) > ZIEL:
        bloecke["transkripte"] = ""
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "kuerzung", "Transkripte entfernt"
        )
        while schaetze(_zusammen(bloecke)) > ZIEL and bloecke["fenster"]:
            bloecke["fenster"] = _fenster_beschneiden(bloecke["fenster"])

    return _zusammen(bloecke)

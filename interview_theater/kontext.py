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

Szenen sind seit dem 04.09.2026 eingebaut (siehe ``interview_theater/szene.py``,
das sie schreibt): die Szenenliste als Teil des Arbeitsstands (Block 4) und
die zuletzt geaenderte Szene im Volltext als eigener Block 5 -- beide
datengetrieben wie alles andere, also weg, solange es keine Szene gibt.
"""

import logging
import os
from datetime import datetime, timedelta

from interview_theater import phasen, repo

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: interview_theater/prompts/system.md). Wird der Sprachmodell-Anfrage getrennt vom
#: Rueckgabewert von baue() als ``system``-Feld mitgegeben (vgl.
#: interview_theater.llm.LLM.schema/.prosa).
from interview_theater import anweisungen


def system(bot_name: str | None = None, phase: int | None = None) -> str:
    """Systemanweisung, heiss nachgeladen (siehe interview_theater.anweisungen).

    ``phase`` haengt die Anweisung fuer die aktuelle Arbeitsphase an
    (``prompts/phasen/N.md``). Sie steuert den Fokus, nicht den
    Informationszugang: die datengetriebenen Bloecke unten bleiben davon
    unberuehrt."""
    return anweisungen.system(bot_name, phase)

#: Kein Tokenizer -- zwei Tage vor dem Workshop keine Abhaengigkeit, die sich
#: fuer Kimi nicht sauber verifizieren laesst. Zeichen ÷ 3 ueberschaetzt bei
#: deutschen Komposita leicht die Tokenzahl -- die richtige Fehlerrichtung:
#: lieber zu frueh kuerzen als zu spaet (§ 7.1).
_ZEICHEN_JE_TOKEN = 3

#: Budgets in Token je Block (SPEC § 6.2) -- rein dokumentarisch, wie in
#: keinem der Bloecke einzeln durchgesetzt. Die tatsaechliche Begrenzung des
#: Gesamtprompts leistet ausschliesslich die zweistufige Kuerzung (§ 7.2):
#: erst Transkripte raus, dann das Fenster von vorn beschnitten, bis das
#: Ziel erreicht ist oder nichts mehr uebrig ist. Ein Block, der schon beim
#: Bauen auf sein eigenes Budget zusammengestutzt wuerde, wuerde genau die
#: Faelle verstecken, die die Kuerzung eigentlich zeigen soll (ein sehr
#: langer Gespraechsverlauf allein kann das Ziel reissen, auch ganz ohne
#: Transkripte). ``arbeitsstand`` enthaelt laut § 6.2 Block 4 auch die
#: Szenenliste (Titel plus je eine Zeile), ``szene`` ist Block 5: die eine
#: zuletzt geaenderte Szene im Volltext.
BUDGETS = {
    "system": 900,
    "verdichtungen": 3000,
    "transkripte": 5000,
    "kernpaket": 2000,
    "arbeitsstand": 1200,
    "phasenhinweis": 50,
    "figurenhinweis": 100,
    "szene": 1500,
    "journal": 1500,
    "fenster": 8000,
    "ausloeser": 300,
}

#: Zielgroesse Normalfall und Reissleine, in Token (§ 6.2, § 7.2).
ZIEL = 20_000
REISSLEINE = 40_000

#: **Harte Obergrenze des Nutzertextes in ZEICHEN** (Audit 06.09.2026,
#: Befund G4). Bis hierher war ZIEL = 20.000 Token die einzige Bremse -- und
#: sie hat am 06.09. nicht gegriffen: gemessen gingen 52.361 Zeichen raus,
#: nach ``schaetze`` (Zeichen ÷ 3) rund 17.400 Token, also *unter* ZIEL. Der
#: Prompt war damit formal in Ordnung und praktisch unbrauchbar: ein Fenster
#: von 700 Zeilen bis in den Vormittag zurueck, in dem das Modell die
#: Gegenwart nicht mehr fand. § 7.2 der SPEC nennt fuer das Fenster 8.000
#: Token; 24.000 Zeichen (~7.000 Token nach unserer Schaetzung, ~8.000 real
#: bei deutschen Komposita) ist diese Zahl, in der Einheit gemessen, in der
#: wir sie ohne Tokenizer sicher pruefen koennen.
#:
#: Ueber ``IT_PROMPT_ZEICHEN`` konfigurierbar: am Workshoptag muss sich das
#: ohne Codeaenderung nachziehen lassen.
ZEICHEN_GRENZE_VORGABE = 24_000


def zeichengrenze() -> int:
    """Die geltende harte Obergrenze in Zeichen (``IT_PROMPT_ZEICHEN``).

    Bei jedem Aufruf gelesen, nicht beim Import: dieselbe Ueberlegung wie beim
    Hot-Reload der Prompts (``anweisungen.py``) -- eine Aenderung soll ohne
    Neustart wirken. Ein unlesbarer oder unsinniger Wert faellt still auf die
    Vorgabe zurueck; am Workshoptag darf ein Tippfehler in einer Umgebung den
    Bot nicht stumm schalten."""
    roh = os.environ.get("IT_PROMPT_ZEICHEN")
    if not roh:
        return ZEICHEN_GRENZE_VORGABE
    try:
        wert = int(roh)
    except ValueError:
        log.warning("IT_PROMPT_ZEICHEN unlesbar (%r), nehme %d", roh, ZEICHEN_GRENZE_VORGABE)
        return ZEICHEN_GRENZE_VORGABE
    if wert < 2_000:
        log.warning("IT_PROMPT_ZEICHEN zu klein (%d), nehme %d", wert, ZEICHEN_GRENZE_VORGABE)
        return ZEICHEN_GRENZE_VORGABE
    return wert

#: Ab dieser Zeitspanne zwischen zwei Nachrichten im Fenster wird eine
#: Pausenzeile eingeschoben (§ 6.2 "Pausenmarkierung").
PAUSE_AB_MINUTEN = 60

#: Feste Reihenfolge des Prompt-Koerpers (ohne SYSTEM, das separat verschickt
#: wird): stabil nach vorn, fluechtig nach hinten.
_REIHENFOLGE = (
    "verdichtungen", "transkripte", "kernpaket", "arbeitsstand", "phasenhinweis",
    "figurenhinweis", "szene", "journal", "fenster", "ausloeser", "erstkontakt",
)


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


def interviewbezeichnung(conn, chat_id: int, aufnahme_id: int | None) -> str:
    """'Interview 2' -- die Nummer in der Reihenfolge der langen Aufnahmen
    der Gruppe. NIE der Aufnahmename (Birk 05.09.): der ist oft ein
    Klarname oder nur der Telegram-Name dessen, der das Handy hielt, und er
    gehoert weder ins Modell (das ihn als 'spricht wie Birk' nachplappert)
    noch aufs Dashboard. Ohne Treffer: 'Interview' plus id."""
    if aufnahme_id is None:
        return ""
    lange = [a for a in repo.transkripte(conn, chat_id) if a["klasse"] == "lang"]
    for n, a in enumerate(lange, start=1):
        if a["id"] == aufnahme_id:
            return f"Interview {n}"
    return f"Interview {aufnahme_id}"


def _baue_verdichtungen(conn, chat_id: int) -> str:
    bloecke = []
    for v in repo.verdichtungen(conn, chat_id):
        name = interviewbezeichnung(conn, chat_id, v["aufnahme_id"]) or f"Aufnahme {v['aufnahme_id']}"
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
    """Volltranskripte -- nur wenn der Schalter ``gruppe.wortlaut_modus``
    gesetzt ist (SPEC § 6.2 Block 3). Ohne ihn waeren Transkripte ab
    Samstagmittag 5.000 Token Dauerlast, die jede Antwort unschaerfer macht;
    die Kuerzung (§ 7.2) faengt das nicht zuverlaessig ab, weil sie erst ab
    ZIEL greift und ein Nachmittag mit drei bis fuenf Interviews oft darunter
    bleibt. NULL/leer heisst kein Block, ``'*'`` heisst alle, jeder andere
    Wert ist ein Name und filtert grosszuegig wie ``repo.transkripte``.

    Der Slash-Befehl ``/wortlaut`` selbst (der dieses Feld setzt) wird erst
    in einer spaeteren Aufgabe gebaut (``befehle.py``); das Datenbankfeld
    existiert aber bereits seit Aufgabe 1 und wird hier rein lesend
    ausgewertet.

    Nur Aufnahmen der Klasse ``'lang'`` zaehlen als Material im Sinne von
    § 10.1 -- kurze Gespraechsbeitraege (Zurufe, Regieanweisungen) stehen
    ohnehin schon im Fenster; sie hier zusaetzlich als Volltranskript
    aufzufuehren wuerde denselben Inhalt verdoppeln und einen Zuruf
    faelschlich zu Interview-Material erklaeren.

    Je Interview EIN Transkript (§ 10.6, ``repo.zusammengefuegtes_transkript``):
    die Teile werden zusammengefuegt, in Reihenfolge, durch eine Leerzeile
    getrennt. Ein Interview aus fuenf Sprachnachrichten ist ein Gespraech, und
    als fuenf Bloecke gelesen zerfiele es genau dort, wo es interessant wird.
    Das gilt auch fuer ein noch laufendes Interview -- die Gruppe soll den
    Wortlaut mitlesen koennen, waehrend er entsteht.
    """
    gruppe = repo.hole_gruppe(conn, chat_id)
    modus = gruppe["wortlaut_modus"] if gruppe else None
    if not modus:
        return ""
    name = None if modus == "*" else modus

    zeilen = []
    for a in repo.transkripte(conn, chat_id, name=name):
        if a["klasse"] != "lang":
            continue
        transkript = repo.zusammengefuegtes_transkript(conn, a["id"])
        if transkript:
            zeilen.append(f"--- {a['name']} (Volltranskript) ---\n{transkript}")
    if not zeilen:
        return ""
    return "Volltranskripte:\n" + "\n\n".join(zeilen)


# --- Das Kernpaket (05.09.2026 abends) ------------------------------------
#
# **Warum es das gibt.** Bis zu diesem Abend bekam der Figuren-Prompt alle
# Verdichtungen und alle Transkripte, und ``prompts/phasen/4.md`` verlangte
# Figuren, "die sich auf Interviewstellen stuetzen". Die Figuren kamen damit
# aus den Interviews statt aus dem Kernthema, und die Gruppe konnte den Weg
# Kernthema -> Figuren nicht nachvollziehen (Birk, nach dem Regie-Test).
#
# Ab den Figuren steht deshalb an der Stelle von Verdichtungen und
# Transkripten EIN Block: das Kernpaket. Es enthaelt Kernthema, Kernfrage, die
# ausgewaehlten Kernzitate, die **am Kernthema gefilterten** Verdichtungen
# (nur die markierten Themen, mit Interview-Nummer), die Figuren mit ihrem
# Sprachprofil und den Rahmen. Die Verdichtungen fliegen also nicht raus --
# sie werden gefiltert, genau wie die Zitate.

KERNPAKET_KOPF = (
    "Das Kernpaket - hieraus arbeitest du. Figuren und Szenen kommen aus dem "
    "Kernthema und dieser Auswahl, nicht aus den Interviews (die stehen dir "
    "hier bewusst nicht mehr im Wortlaut zur Verfuegung):"
)


def _baue_kernpaket(conn, chat_id: int) -> str:
    """Der Block, der ab den Figuren an die Stelle von Verdichtungen und
    Transkripten tritt.

    Datengetrieben wie alles: jeder Teil faellt weg, solange seine Daten leer
    sind, und ohne Kernthema gibt es gar keinen Block."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen: list[str] = []
    # Die Geschichte steht vorn: sie hat die Rolle uebernommen, die bis zum
    # Umbau vom 05.09.2026 nachts das Kernthema hatte -- der Bogen, an dem
    # alles haengt. Das Kernthema bleibt darunter stehen, solange eine alte
    # Gruppe eines gesetzt hat (rueckwaertskompatibel).
    if "geschichte" in stand.keys() and stand["geschichte"]:
        zeilen.append("Geschichte:\n" + stand["geschichte"].strip())
    if stand["kernthema"]:
        zeile = f"Kernthema: {stand['kernthema']}"
        if stand["kernthema_begruendung"]:
            zeile += f" (Begruendung: {stand['kernthema_begruendung']})"
        zeilen.append(zeile)
    if stand["kernfrage"]:
        zeilen.append("Kernfrage:\n" + stand["kernfrage"].strip())
    if stand["rahmen"]:
        zeilen.append(f"Setting (Rahmen): {stand['rahmen']}")

    themen = repo.kernthemen_themen(conn, chat_id)
    if themen:
        block = ["Passende Stellen aus den Interviews (die Ausarbeitungsgrundlage):"]
        # Die Zusammenfassung gehoert der VERDICHTUNG, nicht dem Thema:
        # ``kernthemen_themen`` liefert sie je Zeile mit, und ein Interview mit
        # elf markierten Themen schrieb sie deshalb elfmal in den Prompt --
        # gemessen am 06.09.2026: derselbe 700-Zeichen-Absatz 11x, allein
        # 7.700 Zeichen Dublette (Audit-Befund G1). Jetzt einmal je Interview,
        # danach nur noch die Themenzeilen.
        gesehen: set[str] = set()
        for thema in themen:
            name = interviewbezeichnung(conn, chat_id, thema["aufnahme_id"])
            block.append(f"- {name}: {thema['thema']}")
            zusammenfassung = (thema["zusammenfassung"] or "").strip()
            if zusammenfassung and zusammenfassung not in gesehen:
                gesehen.add(zusammenfassung)
                block.append(f"    {zusammenfassung}")
        zeilen.append("\n".join(block))

    zitate = repo.kernzitate(conn, chat_id)
    if zitate:
        block = ["Kernzitate (woertlich, geprueft):"]
        for eintrag in zitate:
            name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
            zeile = f'- {name}: "{eintrag["zitat"]}"'
            if eintrag["begruendung"]:
                zeile += f" ({eintrag['begruendung']})"
            block.append(zeile)
        zeilen.append("\n".join(block))

    figuren = repo.figuren(conn, chat_id)
    if figuren:
        block = ["Figuren:"]
        for figur in figuren:
            kopf = figur["name"]
            if figur["beschreibung"]:
                kopf += f" -- {figur['beschreibung']}"
            block.append(f"- {kopf}")
            if figur["sprachprofil"]:
                block.append(f"    Sprachduktus: {figur['sprachprofil'].strip()}")
            for eintrag in repo.schaerfungen(conn, chat_id, figur_id=figur["id"]):
                name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
                block.append(
                    f'    Aus {name}: {eintrag["thema"]} -- "{eintrag["zitat"]}"'
                )
        zeilen.append("\n".join(block))

    # Die Schaerfungen je Szene (Phase 6): jede Szene mit den Stellen, die
    # ihr zugeordnet wurden. Datengetrieben wie alles -- ohne Zuordnung kein
    # Block.
    szenenbloecke: list[str] = []
    for szene in repo.hole_szenen(conn, chat_id):
        eintraege = repo.schaerfungen(conn, chat_id, szene_id=szene["id"])
        if not eintraege:
            continue
        block = [szenenzeile(szene)]
        for eintrag in eintraege:
            name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
            zeile = f'  - {name}: {eintrag["thema"]} -- "{eintrag["zitat"]}"'
            if eintrag["begruendung"]:
                zeile += f" ({eintrag['begruendung']})"
            block.append(zeile)
        szenenbloecke.append("\n".join(block))
    if szenenbloecke:
        zeilen.append(
            "Geschaerft am Material, je Szene:\n" + "\n".join(szenenbloecke)
        )

    if not zeilen:
        return ""
    return KERNPAKET_KOPF + "\n" + "\n".join(zeilen)


#: Die beiden Erfindungsphasen (Umbau 05.09.2026 nachts): 4 Setting & Figuren
#: und 5 Geschichte. Dort sieht der Bot **kein** Material -- keine
#: Verdichtungen, keine Transkripte, kein Kernpaket. Vorschlaege kommen
#: ausschliesslich aus Begriffen, Fragen und dem, was die Gruppe schon
#: festgelegt hat.
PHASEN_ERFINDEN = (4, 5)

#: Ab dieser Phase arbeitet der Bot aus dem Kernpaket (mit den Schaerfungen).
PHASE_KERNPAKET = 6


def material_erlaubt(conn, chat_id: int) -> bool:
    """Duerfen Verdichtungen und Transkripte in den Prompt?

    Ja bis einschliesslich Phase 3: dort wird aufgenommen und ausgewertet,
    und die Verdichtung gehoert in den Chat. **Nein in 4 und 5** -- das ist
    der Kern des Umbaus vom 05.09.2026 nachts: Setting, Figuren und
    Geschichte erfindet die Gruppe frei, und ein Bot, der dabei alle
    Interviews vor sich hat, schlaegt nichts anderes vor als die Interviews.
    Nein auch ab 6, aber aus dem alten Grund: dort traegt das Kernpaket.

    Eine reine Leseabfrage aus einem Feld, kein gespeicherter Zustand --
    geht die Gruppe zurueck nach 3, ist das Material wieder da."""
    return phasen.aktuelle(conn, chat_id) < min(PHASEN_ERFINDEN)


def kernpaket_erlaubt(conn, chat_id: int) -> bool:
    """Darf das Kernpaket in den Prompt? Erst ab der Schaerfung (Phase 6).

    In 4 und 5 waere es dasselbe Leck wie die Verdichtungen: das Kernpaket
    traegt Zitate und gefilterte Verdichtungen, und genau die sollen dort
    nicht auf dem Tisch liegen."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_KERNPAKET


def szenenzeile(s) -> str:
    """Eine Szene als eine Zeile: Nummer, Titel, Kurzbeschreibung (SPEC § 6.2
    Block 4). Fehlt eines der Felder, faellt nur dieser Teil weg -- die Zeile
    bleibt lesbar, auch wenn das Sprachmodell einmal keinen Titel geliefert
    hat und ``interview_theater.szene`` auf 'Szene N' zurueckgefallen ist."""
    kopf = f"Szene {s['nummer']}" if s["nummer"] is not None else "Szene"
    if s["titel"]:
        kopf += f": {s['titel']}"
    if s["kurzbeschreibung"]:
        return f"{kopf} - {s['kurzbeschreibung']}"
    return kopf


def _baue_arbeitsstand(conn, chat_id: int, ohne_kernpaket_felder: bool = False) -> str:
    """Der Arbeitsstand -- was die Gruppe festgelegt hat.

    ``ohne_kernpaket_felder`` laesst die Felder weg, die im selben Prompt
    schon im Kernpaket stehen (Audit-Befund G2, 06.09.2026): Geschichte,
    Kernthema, Kernfrage, Rahmen und die Figurenzeilen standen an beiden
    Stellen wortgleich -- Kernthema und Rahmen sogar dreimal, weil das
    Kernpaket den Rahmen als "Setting (Rahmen)" fuehrt. Ein Fakt, der zweimal
    dasteht, ist kein Fakt mehr, sondern eine Betonung, und das Modell hat sie
    am 05.09. um 21:50 als solche gelesen. **Eine Quelle je Fakt**: steht das
    Kernpaket im Prompt, gehoeren diese Felder ihm; sonst dem Arbeitsstand.

    Begriffe, Fragen, Hauptkonflikt und die Szenenliste bleiben immer hier --
    sie stehen im Kernpaket nicht."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)
    szenen = repo.hole_szenen(conn, chat_id)

    zeilen = []
    # Die Phase steht ganz vorn im Arbeitsstand -- aber nur, wenn sie
    # tatsaechlich gesetzt wurde. Ein NULL-Feld ist kein Wissen: solange
    # niemand eine Phase genannt hat, gibt es nichts zu berichten, und der
    # Block bleibt weg wie jeder andere leere Block (SPEC § 6.1). Den Fokus
    # bekommt der Bot in diesem Fall trotzdem, ueber prompts/phasen/1.md
    # (anweisungen.system).
    gespeicherte_phase = repo.hole_phase(conn, chat_id)
    if gespeicherte_phase is not None:
        zeilen.append(f"Aktuelle Phase: {phasen.bezeichnung(gespeicherte_phase)}")
    if stand:
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
        if stand["fragen"]:
            zeilen.append(f"Fragen: {stand['fragen']}")
        if stand["kernthema"] and not ohne_kernpaket_felder:
            zeile = f"Kernthema: {stand['kernthema']}"
            if stand["kernthema_begruendung"]:
                zeile += f" (Begruendung: {stand['kernthema_begruendung']})"
            zeilen.append(zeile)
        if stand["kernfrage"] and not ohne_kernpaket_felder:
            zeilen.append("Kernfrage:\n" + stand["kernfrage"].strip())
        # Die Geschichte im Groben (Phase 5): Bogen und Ende.
        if ("geschichte" in stand.keys() and stand["geschichte"]
                and not ohne_kernpaket_felder):
            zeilen.append("Geschichte:\n" + stand["geschichte"].strip())
        # Der Rahmen (Phase 5, seit 05.09.2026). Datengetrieben wie alles
        # andere: der Hauptkonflikt steht nur da, wenn die Gruppe einen wollte
        # -- er ist eine Rahmen-Entscheidung, keine Pflicht. Ein "Format" des
        # Stuecks steht hier seit dem Abend des 05.09.2026 nicht mehr: es
        # wird nicht mehr gefragt, also wird es auch nicht mehr vorgehalten.
        if stand["rahmen"] and not ohne_kernpaket_felder:
            zeilen.append(f"Rahmen: {stand['rahmen']}")
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    if not ohne_kernpaket_felder:
        for figur in figuren:
            beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
            zeilen.append(f"Figur {figur['name']}{beschreibung}")
    # Szenenliste: Teil des Arbeitsstands, nicht ein eigener Block -- SPEC
    # § 6.2 fuehrt sie woertlich in Block 4 auf ("Begriffe, Fragen, Kernthema +
    # Begruendung, Figuren, Konflikt, Szenenliste"). Nur Titel und die eine
    # Kurzbeschreibungszeile; die Volltexte waeren bei sechs Szenen rund 6.000
    # Token Dauerlast, deshalb geht davon nur die zuletzt geaenderte mit
    # (Block 5, _baue_szene).
    for szene in szenen:
        zeilen.append(szenenzeile(szene))

    if not zeilen:
        return ""
    return "Arbeitsstand:\n" + "\n".join(zeilen)


#: Der Hinweisblock, mit dem der Bot einen Phasenwechsel zur Sprache bringt.
#:
#: Seit dem 05.09.2026 ist das ausdruecklich eine **Frage**, kein Angebot und
#: erst recht kein Wechsel (Birk, nach dem Probelauf): Datenstand ist nicht
#: Absicht -- eine fertige Verdichtung sagt nicht, ob noch drei Interviews
#: kommen. Der Bot fragt im Fluss, die Gruppe antwortet in einem Satz, und
#: der Erkenner liest daraus ``phase_setzen``. Der Bot selbst schaltet nie um.
_PHASENHINWEIS = (
    "Die Materiallage wuerde Phase {bezeichnung} hergeben. Frag im Fluss "
    "nach, ob die Gruppe schon dorthin will -- ein Satz, keine Ankuendigung "
    '("Kommen noch Interviews, oder gehen wir ans Kernthema?"). Du schaltest '
    "nicht selbst um; das tut die Antwort der Gruppe."
)


def _baue_phasenhinweis(conn, chat_id: int) -> str:
    """Der Hinweis auf eine moegliche naechste Phase -- hoechstens einmal je
    Stufe (interview_theater/phasen.py).

    Die einzige Stelle im Kontextaufbau, die schreibt: ``phase_angeboten``
    merkt sich, welcher Wechsel schon im Prompt stand. Ohne dieses Feld
    stuende der Block in jedem Zug erneut da, und der Bot fragte alle zwei
    Minuten dasselbe -- aus einer Frage wuerde Draengeln. Antwortet die
    Gruppe, aendert sich die Phase, und beim naechsten erreichbaren Schritt
    gibt es eine neue Frage; antwortet sie nicht, bleibt es still."""
    stufe = phasen.offenes_angebot(conn, chat_id)
    if stufe is None:
        return ""
    phasen.merke_angebot(conn, chat_id, stufe)
    return _PHASENHINWEIS.format(bezeichnung=phasen.bezeichnung(stufe))


#: Der Hinweisblock, mit dem der Bot die Interview-Zuordnung einer Figur zur
#: Sprache bringt (05.09.2026, Birk: "Zitate als Few-Shots fuer die
#: Sprechweise je Figur, das ist das Wichtigste").
#:
#: Eine **Frage im Fluss**, kein Formular -- dieselbe Form wie der
#: Phasenhinweis: der Bot schlaegt vor, die Gruppe entscheidet, und erst ihre
#: Antwort loest den Sprachprofil-Aufruf aus (Erkenner-art
#: ``figur_quelle_setzen``). Der Code raet die Zuordnung nie selbst: welche
#: Figur aus wessen Erzaehlung spricht, kann kein Namensvergleich
#: beantworten.
_FIGURENHINWEIS = (
    "Diesen Figuren fehlt noch das Interview, aus dem sie spricht: {namen}. "
    "Wenn es passt, EIN Satz dazu, hoechstens: '<Figurenname> koennte wie "
    "<Interviewname> sprechen -- passt das?' Kein Zitat, keine Begruendung, "
    "keine Erklaerung, wozu die Zuordnung gut ist, und nichts wiederholen, "
    "was schon gesagt oder notiert wurde (Birk, 05.09. abends: die Zuordnung "
    "war zu langatmig). Nur Figurennamen aus der Liste oben und Interviewnamen "
    "aus den Verdichtungen. Sagt die Gruppe, eine Figur sei frei erfunden, "
    "frag fuer sie nicht mehr. Ein Interview darf mehrere Figuren speisen."
)


def _baue_figurenhinweis(conn, chat_id: int) -> str:
    """Der Hinweis auf Figuren ohne Quelle-Interview -- datengetrieben wie
    alles andere: weg, sobald jede Figur eine hat.

    Anders als der Phasenhinweis **ohne Merkposten**: hier verschwindet die
    Frage von selbst, sobald die Gruppe geantwortet hat, weil dann die Quelle
    gesetzt ist. Ein zweites Feld waere ein Merkposten fuer etwas, das die
    Daten schon sagen -- und wuerde die Frage fuer eine spaeter angelegte
    Figur mitverschlucken.

    Nur, wenn es ueberhaupt ein Interview gibt: ohne Material ist die Frage
    unbeantwortbar, und der Bot soll nicht nach etwas fragen, das die Gruppe
    noch gar nicht aufgenommen hat."""
    # Und erst ab der Schaerfung (Phase 6): in 4 und 5 wird erfunden, die
    # Frage nach dem Interview einer Figur waere dort genau die Ruecklenkung
    # aufs Material, die der Umbau vermeiden soll.
    if not kernpaket_erlaubt(conn, chat_id):
        return ""
    ohne = [f["name"] for f in repo.figuren(conn, chat_id) if f["quelle_aufnahme_id"] is None]
    if not ohne:
        return ""
    if not any(a["klasse"] == "lang" for a in repo.transkripte(conn, chat_id)):
        return ""
    return _FIGURENHINWEIS.format(namen=", ".join(ohne))


def _baue_szene(conn, chat_id: int) -> str:
    """Block 5: die EINE zuletzt geaenderte Szene im Volltext (SPEC § 6.2).

    Datengetrieben wie alle Bloecke, ohne gespeicherten Zustand: woran die
    Gruppe zuletzt gearbeitet hat, ist die Szene, um die es gerade geht --
    springt sie zu einer frueheren zurueck und ueberarbeitet sie, wandert
    diese automatisch hierher (repo.aktualisiere_szene setzt geaendert_am
    neu)."""
    szene = repo.hole_letzte_szene(conn, chat_id)
    if szene is None or not szene["volltext"]:
        return ""
    return f"Aktuelle Szene ({szenenzeile(szene)}):\n{szene['volltext']}"


#: Wie viele Journaleintraege in den Prompt gehen -- die letzten N nach
#: Dedupe (Audit-Befund G3, 06.09.2026). Das Journal ist nur-anhaengend und
#: waechst ueber zwei Workshoptage auf Dutzende Zeilen; gemessen standen am
#: 06.09. 15 Zeilen im Prompt, davon "Szene 1 geschrieben: ..." VIERMAL und
#: vier Figurenzeilen mit demselben "basierend auf Interview 1"-Anhang. Ein
#: Modell liest vierfache Wiederholung als Betonung -- es hielt die eine
#: geschriebene Szene fuer vier.
JOURNAL_EINTRAEGE = 8


def _baue_journal(conn, chat_id: int) -> str:
    """Die letzten JOURNAL_EINTRAEGE Journalzeilen, ohne Dubletten.

    **Dedupe vor Kuerzung**: erst fliegen textgleiche Eintraege raus (der
    juengste bleibt, weil er den aktuellen Stand traegt), dann werden die
    letzten N genommen. Andersherum wuerden acht Dubletten acht Plaetze
    besetzen und alles Aeltere verdraengen.

    Das Journal in der Datenbank bleibt unangetastet -- dort steht die volle
    Geschichte, und ein Journal wird nur angehaengt, nie umgeschrieben
    (AGENTS.md). Gekuerzt wird nur die Sicht des Modells."""
    eintraege = repo.journal(conn, chat_id)
    if not eintraege:
        return ""
    # Von hinten durchgehen: der juengste Eintrag eines Textes gewinnt.
    gesehen: set[tuple[str, str]] = set()
    behalten = []
    for e in reversed(eintraege):
        schluessel = (e["art"], (e["text"] or "").strip())
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        behalten.append(e)
    behalten = list(reversed(behalten))[-JOURNAL_EINTRAEGE:]
    zeilen = [f"- [{e['art']}] {e['text']}" for e in behalten]
    return "Journal:\n" + "\n".join(zeilen)


#: Obergrenze fuer den Nachrichtenpool, aus dem das Fenster gebaut wird --
#: eine reine Performance-Vorkehrung (niemand soll fuer jeden Zug den
#: gesamten Zweitagesverlauf aus der DB laden), kein Budget im Sinne von
#: BUDGETS["fenster"].
_FENSTER_POOL = 1000

#: Wie viele Nachrichten hoechstens ins Fenster kommen (06.09.2026, Birk,
#: gemessen an der Testgruppe um 00:33: der Nutzertext hatte **52 000
#: Zeichen**, und darin standen 700 Zeilen bis in den Vormittag zurueck).
#:
#: Zwanzig ist die Zahl, die eine laufende Arbeitsphase abdeckt, ohne den
#: Vormittag mitzuschleppen. Alles Aeltere, das wirklich zaehlt, steht
#: ohnehin strukturiert im Prompt: Arbeitsstand, Journal, Figuren,
#: Verdichtungen. Das Fenster ist fuer den Ton und den letzten Faden da,
#: nicht als Archiv.
FENSTER_NACHRICHTEN = 20

#: Und zeitlich: was laenger als das her ist, gehoert nicht mehr zur
#: laufenden Unterhaltung. Es gilt die KLEINERE der beiden Grenzen.
#:
#: Der Anlass ist gemessen (05.09.2026, 21:50): weil der Vormittag mit im
#: Fenster stand -- und wegen der falschen Sortierung sogar OBEN --, hielt
#: das Modell ihn fuer die Gegenwart und antwortete in Phase 6 mit "Das ist
#: Tag 1 und wir stehen erst am Anfang. Also: Rassismus, Liebe, Spaß,
#: Streit."
FENSTER_MINUTEN = 30

#: Systemzeilen, die nicht ins Fenster gehoeren (06.09.2026). Sie sind
#: Ereignisse, keine Gespraechsbeitraege: was sie festhalten, steht im
#: Journal und im Arbeitsstand, und im Fenster stiften sie nur Verwirrung --
#: am Testabend stand "Bin wieder da" zweimal darin, und das Modell erzaehlte
#: die Notiert-Zeilen nach, statt weiterzuarbeiten.
_SYSTEMANFAENGE = (
    "Bin wieder da.",
    "Notiert:",
    "Aufnahme laeuft.",
    "Aufnahme beendet.",
    "Bereit -",
    "Hinweis: Den Szenentext",
    "Ich schreibe die Szene aus",
    "Ich schreibe gerade noch",
    "Ich werte die offenen Interviews aus",
    "Entfernt:",
)


def _ist_systemzeile(n) -> bool:
    """Ist diese Bot-Nachricht eine Systemmeldung und kein Gespraechsbeitrag?

    Nur Bot-Nachrichten: eine Gruppe, die zufaellig "Notiert:" tippt, sagt
    damit etwas -- und was die Gruppe sagt, faellt hier nie weg."""
    if not n["ist_bot"]:
        return False
    text = (n["text"] or "").lstrip()
    return any(text.startswith(anfang) for anfang in _SYSTEMANFAENGE)


def _baue_fenster_eintraege(conn, chat_id: int, ausloeser) -> list[str]:
    """Liefert die Eintraege des kurzen Fensters (Nachrichtenzeilen und
    Pausenmarkierungen), **aeltester zuerst** -- die letzten
    ``FENSTER_NACHRICHTEN`` Nachrichten oder die letzten ``FENSTER_MINUTEN``,
    was weniger ist, ohne Systemzeilen.

    **Warum das am 06.09.2026 umgebaut wurde.** Gemessen an der Testgruppe:
    der Nutzertext eines Zuges war 52 000 Zeichen lang, das Fenster reichte
    700 Zeilen bis in den Vormittag zurueck -- und es stand **rueckwaerts**
    darin. Der Grund fuer die Reihenfolge war eine falsche
    Sortierannahme: ``repo.letzte_nachrichten`` ordnet nach ``message_id``,
    und eine uebernommene Gruppenhistorie traegt **negative, absteigend
    vergebene** ids. Aufsteigend sortiert stehen die aeltesten dieser
    Nachrichten damit zuletzt und die juengsten zuerst. Sortiert wird deshalb
    hier nach ``gesendet_am``: die Uhrzeit luegt nicht.

    Die Folge des alten Verhaltens ist belegt (05.09.2026, 21:50): das Modell
    hielt den Vormittag fuer die Gegenwart und bot in Phase 6 an, aus den
    Begriffen Interviewfragen zu entwickeln.

    Jeder Listeneintrag bleibt eine atomare Einheit (eine Pausenzeile oder
    eine einzelne Nachricht) -- Grundlage dafuer, dass die Kuerzung in
    ``baue()`` ganze Nachrichten abschneiden kann."""
    ausloeser_ids = {n["message_id"] for n in ausloeser}
    roh = [
        n for n in repo.letzte_nachrichten(conn, chat_id, anzahl=_FENSTER_POOL)
        if n["message_id"] not in ausloeser_ids and not _ist_systemzeile(n)
    ]
    # Nach der Uhrzeit, nicht nach der id (siehe Docstring).
    roh.sort(key=lambda n: n["gesendet_am"])

    kandidaten = roh[-FENSTER_NACHRICHTEN:]
    juengste = _juengste_zeit(ausloeser, kandidaten)
    if juengste is not None:
        grenze = juengste - timedelta(minutes=FENSTER_MINUTEN)
        kandidaten = [
            n for n in kandidaten
            if datetime.fromisoformat(n["gesendet_am"]) >= grenze
        ]

    eintraege = []
    vorherige_zeit = None
    for n in kandidaten:
        if vorherige_zeit is not None:
            pause = _pausenzeile(vorherige_zeit, n["gesendet_am"])
            if pause:
                eintraege.append(pause)
        eintraege.append(sprecherzeile(n))
        vorherige_zeit = n["gesendet_am"]
    return eintraege


def _juengste_zeit(ausloeser, kandidaten):
    """Der Bezugspunkt der 30-Minuten-Grenze: die ausloesende Nachricht, oder
    -- wenn es keine gibt -- die juengste im Fenster. Nicht ``jetzt``: ein
    Test und ein Nachlauf sollen dieselbe Antwort bekommen wie der Livezug."""
    zeiten = [n["gesendet_am"] for n in ausloeser] or [
        n["gesendet_am"] for n in kandidaten
    ]
    if not zeiten:
        return None
    return datetime.fromisoformat(max(zeiten))


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


#: Beim allerersten Zug einer Gruppe bekommt das Modell diese Anweisung an
#: den Anfang des Koerpers -- statt eines fest verdrahteten Begruessungstexts
#: (Birk 04.09. abends: "der Einstieg reagiert gar nicht auf das, was die
#: Leute als Allererstes sagen"). Der Inhalt (Mitlesen, Interviews, /hilfe,
#: Link) bleibt Pflicht, die Form entsteht aus der ersten Nachricht.
ERSTKONTAKT = (
    "Dies ist eure allererste Nachricht in dieser Gruppe -- deine Antwort ist "
    "zugleich die Begruessung. Geh zuerst auf das ein, was gerade gesagt "
    "wurde, und nimm dir dann Raum: das ist der Moment, in dem die Gruppe "
    "versteht, wie hier gearbeitet wird. Bring unter, in dieser Reihenfolge "
    "und in ganzen Saetzen, nicht als Liste: wer du bist und was ihr "
    "zusammen macht (aus den Begriffen der Gruppe entstehen Fragen, mit den "
    "Fragen zieht die Gruppe los und macht Interviews, aus den Interviews "
    "wird spaeter das Stueck); dass du alles mitliest und auf alles "
    "antwortest, getippt wie gesprochen; **dass ein Interview mit dem Knopf "
    "\"Interview starten\" beginnt und dass nach jeder Sprachnachricht ein "
    "Knopf fragt, ob es weitergeht oder fertig ist** -- die "
    "Knoepfe unter deiner Nachricht zeigen den Weg, **nenne keinen "
    "Schraegstrich-Befehl**{link}. "
    "**Schliesse mit der Frage nach den Begriffen**: die Gruppe hat im Raum "
    "Begriffe gesammelt -- bitte sie, dir diese Liste zu schicken, getippt, "
    "als Foto abgetippt oder als Sprachnachricht. Das ist der erste "
    "Arbeitsschritt, und die Begruessung endet damit. "
    "Kein Formular, keine Aufzaehlung mit Spiegelstrichen -- ein warmer, "
    "ausfuehrlicher Einstieg, der mit dem Gesagten anfaengt und mit der "
    "Bitte um die Begriffe aufhoert."
)

#: Der Satz zum Link, wenn eine Weboberflaeche konfiguriert ist.
ERSTKONTAKT_LINK = (
    "; und dass die Gruppe alles Festgehaltene unter {url} mitlesen kann "
    "(nur fuer diese Gruppe, den Link genau so nennen)"
)


def _baue_erstkontakt(conn, chat_id: int, e) -> str:
    # ueber bot.stelle_link_sicher, nicht ueber repo.gruppenseite_url direkt:
    # der Link muss in der Begruessung stehen, auch wenn die Gruppenzeile
    # gerade erst entsteht (05.09.2026).
    from interview_theater import bot

    url = bot.stelle_link_sicher(conn, e, chat_id)
    link = ERSTKONTAKT_LINK.format(url=url) if url else ""
    return ERSTKONTAKT.format(link=link)


def umriss(bloecke: dict, gekuerzt: bool = False) -> dict:
    """Welcher Block mit wie vielen geschaetzten Token im Prompt stand.

    Reine Buchhaltung ueber dem fertigen Ergebnis, ohne Einfluss darauf.
    Gebraucht wird sie vom Simulator: die Frage "was wird wann injiziert" --
    lag die Verdichtung ueberhaupt im Prompt, als der Bot danebengeantwortet
    hat? -- laesst sich sonst nur beantworten, indem man den ganzen Prompt
    mitschreibt, und der ist bei 20.000 Token keine Berichtszeile mehr.

    Leere Bloecke stehen mit 0 drin und fallen nicht weg: dass die
    Verdichtungen fehlten, ist die interessantere Zeile als dass sie da
    waren."""
    return {
        "bloecke": {name: schaetze(bloecke.get(name, "")) for name in _REIHENFOLGE},
        "gesamt": schaetze(_zusammen(bloecke)),
        "gekuerzt": bool(gekuerzt),
    }


def baue(conn, chat_id: int, ausloeser, e, erstkontakt: bool = False,
         protokoll: list | None = None) -> str:
    """Baut den Koerper des Gespraechs-Prompts (ohne SYSTEM, das getrennt
    verschickt wird).

    ``ausloeser`` ist die Liste der Nachrichten, die diesen Zug ausgeloest
    haben (alles seit ``letzte_beantwortete_message_id``, § 1.3) -- vom
    Aufrufer ermittelt, hier nur formatiert.

    ``protokoll`` ist rein additiv und im Betrieb nie gesetzt: ist es eine
    Liste, wird ein ``umriss()`` des fertigen Prompts angehaengt. Der
    Simulator misst damit, was wann im Prompt stand; der Bot selbst merkt von
    diesem Argument nichts.

    Passt der Koerper nicht ins Zielbudget ZIEL, greift die zweistufige
    Kuerzung aus § 7.2: erst fliegen die Volltranskripte ganz raus, dann wird
    das Fenster von vorn beschnitten -- eine ganze Nachricht (oder Pausenzeile)
    je Schritt, nie nur eine physische Zeile eines mehrzeiligen Beitrags --
    bis es passt oder leer ist. Die Notbremse -- Systemanweisung,
    Arbeitsstand, Fenster, ausloesende Nachricht -- wird dabei nie
    angetastet: Arbeitsstand und Ausloeser sind von der Kuerzung
    grundsaetzlich ausgenommen, es gibt keinen Zustand, in dem der Bot wegen
    des Budgets nicht antworten koennte."""
    fenster_eintraege = _baue_fenster_eintraege(conn, chat_id, ausloeser)
    # Der Kontext-Filter je Phase (05.09.2026 abends): bis zur Kernfrage
    # arbeitet der Bot AM Material (Verdichtungen; Transkripte, wenn der
    # Wortlaut-Schalter steht), danach AUS dem Kernpaket. Datengetrieben wie
    # alles andere -- es gibt keinen gespeicherten Zustand, nur zwei Felder,
    # die die Lage beschreiben.
    material = material_erlaubt(conn, chat_id)
    kernpaket = (
        _baue_kernpaket(conn, chat_id) if kernpaket_erlaubt(conn, chat_id) else ""
    )
    bloecke = {
        "erstkontakt": _baue_erstkontakt(conn, chat_id, e) if erstkontakt else "",
        "verdichtungen": _baue_verdichtungen(conn, chat_id) if material else "",
        "transkripte": _baue_transkripte(conn, chat_id) if material else "",
        # In 4 und 5 gibt es WEDER Material NOCH Kernpaket: dort wird
        # erfunden (``PHASEN_ERFINDEN``).
        "kernpaket": kernpaket,
        # Kernpaket ODER Arbeitsstand, nie beides fuer denselben Fakt
        # (Audit-Befund G2).
        "arbeitsstand": _baue_arbeitsstand(
            conn, chat_id, ohne_kernpaket_felder=bool(kernpaket)
        ),
        "phasenhinweis": _baue_phasenhinweis(conn, chat_id),
        "figurenhinweis": _baue_figurenhinweis(conn, chat_id),
        "szene": _baue_szene(conn, chat_id),
        "journal": _baue_journal(conn, chat_id),
        "fenster": "\n".join(fenster_eintraege),
        "ausloeser": _baue_ausloeser(ausloeser),
    }

    gekuerzt = False
    grenze = zeichengrenze()

    def _zu_lang() -> bool:
        """Ueber Zeichengrenze ODER ueber Token-Ziel -- beides bremst.

        Zwei Masse, weil sie verschiedene Fehler fangen: ZIEL faengt den
        Prompt, der insgesamt zu gross wird, die Zeichengrenze den, der es in
        Token knapp nicht wird und trotzdem unlesbar ist (der Fall vom
        06.09.2026)."""
        text = _zusammen(bloecke)
        return len(text) > grenze or schaetze(text) > ZIEL

    if _zu_lang():
        gekuerzt = True
        vorher = len(_zusammen(bloecke))
        # Kuerzungsreihenfolge (§ 7.2, praezisiert im Audit 06.09.2026):
        # 1. Volltranskripte -- der groesste einzelne Brocken, und ihr Inhalt
        #    steht verdichtet ohnehin da.
        # 2. Der Verlauf von vorn -- das Aelteste zuerst, eine ganze Nachricht
        #    je Schritt.
        # 3. Das Journal von vorn -- die aeltesten Notizen.
        # 4. Die Verdichtungen -- zuletzt, weil sie das Material selbst sind.
        # Nie angetastet: Kernpaket, Arbeitsstand, Hinweise, aktuelle Szene und
        # die ausloesende Nachricht. Es gibt keinen Zustand, in dem der Bot
        # wegen des Budgets nicht antworten koennte.
        bloecke["transkripte"] = ""
        while _zu_lang() and fenster_eintraege:
            fenster_eintraege = fenster_eintraege[1:]
            bloecke["fenster"] = "\n".join(fenster_eintraege)
        if _zu_lang() and bloecke["journal"]:
            journalzeilen = bloecke["journal"].split("\n")
            # Zeile 0 ist die Ueberschrift "Journal:" -- sie bleibt, solange
            # noch eine Notiz darunter steht.
            while _zu_lang() and len(journalzeilen) > 2:
                journalzeilen = [journalzeilen[0]] + journalzeilen[2:]
                bloecke["journal"] = "\n".join(journalzeilen)
            if _zu_lang():
                bloecke["journal"] = ""
        if _zu_lang():
            bloecke["verdichtungen"] = ""
        nachher = len(_zusammen(bloecke))
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "kontext_gekuerzt",
            f"Nutzertext von {vorher} auf {nachher} Zeichen gekuerzt "
            f"(Grenze {grenze}, Ziel {ZIEL} Token)",
        )

    if protokoll is not None:
        protokoll.append(umriss(bloecke, gekuerzt))
    return _zusammen(bloecke)

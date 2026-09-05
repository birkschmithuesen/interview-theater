"""Die mechanischen Kennzahlen eines Laufs -- aus Datenbank und Attrappe.

Kein Modellaufruf. Alles hier ist nachzaehlbar, und genau darin liegt der
Wert: die Noten des Richters (``richter.py``) schwanken zwischen zwei Laeufen,
diese Zahlen nicht. Wer eine Prompt-Aenderung bewerten will, schaut zuerst
hierhin.

Gemessen wird gegen die Sollwerte aus dem Auftrag:

===============================  ====================================
``phase_erreicht``               Soll: die Szenen-Phase
``arbeitsstand_vollstaendig``    je Feld 0/1
``zustimmungen_gespeichert``     Anteil der Zustimmungen, nach denen eine
                                 Notiert-Zeile kam (Soll 1,0)
``verdichtungen``                Soll: eine je Interview
``zitate_geprueft``              Anteil der Kernthemen mit geprueftem Zitat
``zitate_soll``                  Anteil der Soll-Zitate, die als Belegzitat
                                 auftauchen
``echo``                         Bot-Antworten, die eine Stimm-Nachricht
                                 zurueckspiegeln (Soll 0)
``rueckfragen_vor_szene``        Soll <= 1
``behauptete_schreibvorgaenge``  Soll 0
``namensanrede``                 Soll 0
``laenge_bot``                   Median Zeichen je Bot-Antwort, Soll < 700
===============================  ====================================
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field

from interview_theater import ablauf, erkenner, kontext, phasen, repo, zitat

from simulation import skript

#: Sollwerte, an denen der Bericht die Zahlen misst. An einer Stelle, damit
#: Bericht und Test dieselbe Zahl meinen.
SOLL_LAENGE_BOT = 700
SOLL_RUECKFRAGEN_VOR_SZENE = 1

#: Median-Zeichenzahl, unter der eine Bot-Antwort auf dem Handy noch als eine
#: Nachricht gelesen wird (N5.2). Strenger als ``SOLL_LAENGE_BOT``, das aus
#: dem urspruenglichen Auftrag stammt -- beide stehen im Bericht, damit
#: sichtbar bleibt, gegen welche Latte gerade gemessen wird.
SOLL_LAENGE_BOT_KNAPP = 500

#: Ab so vielen Aufzaehlungspunkten am Ende einer Antwort ist es eine
#: Optionenliste und kein Vorschlag mehr (N5.2).
OPTIONEN_AB = 3

#: Sollwert fuer das 90. Perzentil der Gespraechslatenz, in Sekunden (N5.1).
SOLL_P90_GESPRAECH_S = 12.0


def _notiert_praefix() -> str:
    """Die erste Zeile der Aenderungsmeldung des Erkenners -- **erzeugt**,
    nicht abgeschrieben.

    Damit erkennt diese Datei die Notiert-Zeile auch dann noch, wenn jemand
    ``erkenner.baue_meldung`` umformuliert; ein hart eingetragenes 'Notiert:'
    wuerde nach so einer Aenderung stillschweigend null Zustimmungen
    finden."""
    beispiel = erkenner.baue_meldung([{"art": "kernthema_setzen", "wert": "Probe"}])
    return beispiel.splitlines()[0] if beispiel else "Notiert:"


NOTIERT = _notiert_praefix()

#: Woerter, mit denen der Bot einen Schreibvorgang behauptet. Ohne Umlaute
#: verglichen (``_falte``), weil der Bot mal 'geloescht' und mal 'gelöscht'
#: schreibt.
SCHREIB_BEHAUPTUNGEN = ("notiert", "korrigiert", "geloescht", "im arbeitsstand")

#: Wie eine Namensanrede aussieht, die der Bot nicht fuehren soll.
_ANREDE_MUSTER = ("{name}:", "{name} hat recht")

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _falte(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().translate(_UMSCHRIFT)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Das Protokoll eines Laufs
# ---------------------------------------------------------------------------


@dataclass
class Beitrag:
    """Eine Nachricht einer simulierten Teilnehmerin."""

    kennung: str      # "S7" -- die Kennung, unter der der Richter sie markiert
    schritt: str
    absender: str
    profil: str
    text: str


@dataclass
class Zug:
    """Ein Gespraechszug: ein oder zwei Stimm-Nachrichten und alles, was der
    Bot daraufhin geschickt hat.

    ``marke`` haelt Sonderereignisse fest, die keine Stimme sind -- der
    Textimport eines Interviews (``import``) und der Moment, in dem die Szene
    beauftragt wurde (``szene_aufruf``). Die Kennzahl
    ``rueckfragen_vor_szene`` haengt an der zweiten."""

    schritt: str
    beitraege: list[Beitrag] = field(default_factory=list)
    bot: list[str] = field(default_factory=list)
    marke: str = ""
    notiz: str = ""
    #: Die Umrisse der Gespraechs-Prompts dieses Zuges (``kontext.umriss``):
    #: welcher Block mit wie vielen geschaetzten Token drinstand. Ein Zug kann
    #: mehrere haben, wenn der Bot mehrfach gefragt wurde (Echo-Wiederholung).
    kontext: list[dict] = field(default_factory=list)
    #: Was zum Zeitpunkt dieses Zuges in der Datenbank stand (``datenlage``).
    #: Zusammen mit ``kontext`` beantwortet es die Frage aus N4b: lag die
    #: Verdichtung vor, als der Bot danebengeantwortet hat -- und stand sie
    #: auch im Prompt?
    datenlage: dict = field(default_factory=dict)
    #: Sekunden von "Update rein" bis zur ersten Bot-Nachricht in der
    #: Attrappe -- die Wartezeit aus Sicht der Gruppe.
    latenz_s: float | None = None
    #: Wofuer der Zug Zeit gebraucht hat: 'gespraech', 'verdichtung',
    #: 'szene'. Trennt die Latenzen im Bericht.
    art: str = "gespraech"

    @property
    def hat_notiert(self) -> bool:
        return any(t.strip().startswith(NOTIERT) for t in self.bot)


# ---------------------------------------------------------------------------
# Zahlen aus dem Protokoll
# ---------------------------------------------------------------------------


def bot_antworten(zuege: list[Zug]) -> list[str]:
    return [t for z in zuege for t in z.bot]


def laenge_bot(zuege: list[Zug]) -> int:
    """Median der Zeichenzahl je Bot-Antwort. Median, nicht Mittelwert: eine
    einzige Szenenvorschau von 2.000 Zeichen wuerde den Mittelwert reissen
    und ueber die uebrigen dreissig Antworten nichts mehr aussagen."""
    laengen = [len(t) for t in bot_antworten(zuege)]
    return int(statistics.median(laengen)) if laengen else 0


def echos(zuege: list[Zug]) -> list[str]:
    """Bot-Antworten, die eine Stimm-Nachricht desselben Zuges
    zurueckspiegeln.

    Geprueft mit **derselben Funktion, die im Betrieb entscheidet**
    (``ablauf.ist_echo``, 80 % woertlich) -- etwas Eigenes hier waere eine
    zweite Wahrheit ueber dieselbe Frage, und die Zahl im Bericht liesse sich
    nicht mehr mit dem Vorfall ``echo_verworfen`` vergleichen."""
    treffer = []
    for zug in zuege:
        ausloeser = [{"ist_bot": 0, "text": b.text} for b in zug.beitraege]
        treffer.extend(t for t in zug.bot if ablauf.ist_echo(t, ausloeser))
    return treffer


def namensanreden(zuege: list[Zug], namen: list[str]) -> list[str]:
    """Bot-Antworten, die mit '<Name>:' oder '<Name> hat recht' beginnen.

    Der gemessene Live-Fall vom 04.09.2026: der Bot schickte eine Nachricht
    mit 'Birk:' davor. Anders als bei ``ist_echo`` zaehlt hier nicht, ob
    danach etwas Eigenes kommt -- die Gruppe soll gar nicht erst angesprochen
    werden wie eine Figur im Stueck."""
    muster = [_falte(form.format(name=name)) for name in namen for form in _ANREDE_MUSTER]
    return [
        t for t in bot_antworten(zuege)
        if any(_falte(t).startswith(m) for m in muster)
    ]


def behauptete_schreibvorgaenge(zuege: list[Zug]) -> list[str]:
    """Bot-Antworten, die einen Schreibvorgang behaupten, ohne dass im selben
    Zug eine Notiert-Zeile des Erkenners kam.

    Der Fehler dahinter ist der teuerste, den der Bot machen kann: die Gruppe
    glaubt, etwas sei festgehalten, arbeitet weiter, und am Abend ist die
    Gruppenseite leer. Die Notiert-Zeile selbst zaehlt nicht mit -- sie ist
    der Beleg, nicht die Behauptung."""
    treffer = []
    for zug in zuege:
        if zug.hat_notiert:
            continue
        for text in zug.bot:
            if text.strip().startswith(NOTIERT):
                continue
            gefaltet = _falte(text)
            if any(wort in gefaltet for wort in SCHREIB_BEHAUPTUNGEN):
                treffer.append(text)
    return treffer


def bot_rueckfragen(zuege: list[Zug]) -> list[str]:
    """Bot-Antworten, die auf ein Fragezeichen **enden** -- also nicht
    liefern, sondern zurueckfragen.

    Nicht "Fragezeichen irgendwo im Text": der Bot darf mitten in einer
    Antwort eine Frage stellen, das ist ein Gespraech. Endet die Nachricht
    damit, hat er den Ball zurueckgespielt. Dieselbe Definition benutzt
    ``birk.referenz`` fuer den echten Chat, sonst waeren die beiden Spalten
    des Referenzvergleichs mit verschiedenen Ellen gemessen."""
    return [t for t in bot_antworten(zuege) if t.strip().endswith("?")]


def rueckfragen_vor_szene(zuege: list[Zug]) -> list[str]:
    """Bot-Nachrichten mit '?' zwischen dem Beginn der Szenenplanung und dem
    Szenen-Auftrag (Soll <= 1).

    Eine Rueckfrage ist in Ordnung -- 'wo spielt sie?' ist eine gute Frage.
    Drei sind ein Verhoer: die Gruppe hat gesagt, was sie will, und wartet
    darauf, dass etwas entsteht."""
    treffer = []
    for zug in zuege:
        if zug.schritt != "szene":
            continue
        if zug.marke == "szene_aufruf":
            break
        treffer.extend(t for t in zug.bot if "?" in t)
    return treffer


def mechanische_treffer(zuege: list[Zug], namen: list[str]) -> dict[str, str]:
    """Bot-Antworten, an denen ohne Modell etwas nachweisbar falsch ist --
    Text -> Grund.

    Sie sind die Grundlage dafuer, dass der Abschnitt "Die schlechtesten
    Bot-Antworten" im Bericht **nie leer** ist. Im ersten echten Lauf war er
    es: der Richter hatte in sechs von acht Abschnitten nichts zu bemaengeln
    und liess das Feld leer, waehrend ``behauptete_schreibvorgaenge`` bei 1
    stand. Der Prompt-Pfleger sah also eine 1 in der Tabelle und nirgends den
    Satz dazu."""
    treffer: dict[str, str] = {}
    for text in behauptete_schreibvorgaenge(zuege):
        treffer.setdefault(text, "behauptet einen Schreibvorgang ohne Notiert-Zeile")
    for text in echos(zuege):
        treffer.setdefault(text, "spiegelt die Gruppe zurueck (Echo)")
    for text in namensanreden(zuege, namen):
        treffer.setdefault(text, "redet eine Teilnehmerin mit Namen an")
    return treffer


def zustimmungen(zuege: list[Zug], markiert: set[str]) -> tuple[int, int]:
    """``(gespeichert, insgesamt)`` fuer die vom Richter als Zustimmung
    markierten Stimm-Nachrichten.

    'Gespeichert' heisst: im selben Zug kam eine Notiert-Zeile. Das ist die
    Kennzahl aus N7 in ihrer strengsten Form -- im Probelauf stimmte die
    Gruppe dreimal zu, und dreimal blieb der Arbeitsstand leer."""
    gesamt = gespeichert = 0
    for zug in zuege:
        for beitrag in zug.beitraege:
            if beitrag.kennung not in markiert:
                continue
            gesamt += 1
            if zug.hat_notiert:
                gespeichert += 1
    return gespeichert, gesamt


# ---------------------------------------------------------------------------
# Zahlen aus der Datenbank
# ---------------------------------------------------------------------------


def _stand_wert(conn, chat_id: int, feld: str) -> str:
    """Ein Arbeitsstandfeld im Wortlaut, oder ein leerer String."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return ""
    try:
        return str(stand[feld] or "")
    except (IndexError, KeyError):
        return ""


# ---------------------------------------------------------------------------
# Latenz, Laenge, Optionenlisten (N5.1, N5.2)
# ---------------------------------------------------------------------------


def _perzentil(werte: list[float], anteil: float) -> float:
    """Das Perzentil einer kleinen Stichprobe -- naechster Rang, nicht
    interpoliert.

    ``statistics.quantiles`` braucht mindestens zwei Werte und interpoliert;
    bei acht gemessenen Zuegen ist das eine Genauigkeit, die es nicht gibt.
    Der naechste Rang sagt "so lange hat der zweitlangsame Zug gedauert" --
    eine Aussage, die man nachzaehlen kann."""
    if not werte:
        return 0.0
    sortiert = sorted(werte)
    rang = min(len(sortiert) - 1, int(round(anteil * (len(sortiert) - 1))))
    return round(sortiert[rang], 2)


def latenzen(zuege: list[Zug]) -> dict:
    """Wartezeit aus Nutzersicht -- Median und p90, getrennt nach Gespraech,
    Verdichtung und Szene.

    Getrennt, weil die Erwartung eine andere ist: auf eine Gespraechsantwort
    wartet die Gruppe im Chat (Soll p90 unter zwoelf Sekunden), auf eine
    Verdichtung wartet sie nach dem Interview, auf eine Szene wartet sie gar
    nicht -- der Bot sagt an, dass es dauert. Ein gemeinsamer Median ueber
    alle drei waere eine Zahl ohne Erwartung daneben."""
    ergebnis = {}
    for art in ("gespraech", "verdichtung", "szene"):
        werte = [z.latenz_s for z in zuege if z.art == art and z.latenz_s is not None]
        ergebnis[art] = {
            "n": len(werte),
            "median": round(statistics.median(werte), 2) if werte else 0.0,
            "p90": _perzentil(werte, 0.9),
        }
    return ergebnis


#: Zeilen, die als Aufzaehlungspunkt zaehlen: Spiegelstrich, Bullet, Stern,
#: oder eine Ziffer mit Punkt.
_PUNKT = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+\S")


def optionenlisten(zuege: list[Zug], ab: int = OPTIONEN_AB) -> list[str]:
    """Bot-Antworten, die mit ``ab`` oder mehr Aufzaehlungspunkten **enden**.

    Am Ende, nicht irgendwo: eine Aufzaehlung mitten in einer Antwort ist eine
    Aufstellung ("das habt ihr bisher"), eine am Schluss ist ein Menue. Der
    Bot soll EINE Sache vorschlagen, ueber die die Gruppe entscheidet -- drei
    gleichrangige Optionen schieben die Arbeit zurueck."""
    treffer = []
    for text in bot_antworten(zuege):
        zeilen = [z for z in text.splitlines() if z.strip()]
        punkte = 0
        for zeile in reversed(zeilen):
            if _PUNKT.match(zeile):
                punkte += 1
            else:
                break
        if punkte >= ab:
            treffer.append(text)
    return treffer


# ---------------------------------------------------------------------------
# Erfundene Zitate (N4c)
# ---------------------------------------------------------------------------

#: Was als Zitat gilt: ein laengerer Text zwischen Anfuehrungszeichen. Kurze
#: Anfuehrungen ("fertig", "Kueche") sind keine Behauptung ueber das
#: Transkript, sondern Erwaehnungen -- sie zaehlen nicht.
#: Eine Anfuehrung zaehlt nur, wenn sie an einer Stelle beginnt, an der ein
#: Zitat steht: Zeilenanfang, nach Doppelpunkt, nach Gedankenstrich oder
#: Klammer. Sonst faengt der Ausdruck bei ``Bei "Spiegel" denkt Sevil ...``
#: das Wort "Spiegel" als Anfang und liest bis zum naechsten Zeichen -- die
#: Thema-Zeile der Verdichtung wird zum "erfundenen Zitat" (gemessen 05.09.,
#: set3: 6 Treffer, alle falsch).
_IN_ANFUEHRUNG = re.compile(r'(?:^|[:\-–(\s])\s*[„"»“]([^„"»«“”]{20,400})[”“"«]', re.MULTILINE)

#: So viele Woerter muss eine Anfuehrung haben, damit sie als Zitat aus einem
#: Interview gemeint sein kann.
ZITAT_MINDEST_WOERTER = 4


def erfundene_zitate(zuege: list[Zug], transkripte: list[str],
                     marke: str = "zitatabfrage") -> list[str]:
    """Anfuehrungen in Bot-Antworten, die in **keinem** Transkript stehen.

    Gemessen wird nur in den Zuegen der Zitatabfragen (``marke``): dort
    behauptet der Bot, aus dem Material zu zitieren, und nur dort ist eine
    Anfuehrung eine ueberpruefbare Aussage darueber. Ueber den ganzen Lauf
    gemessen wuerde die Zahl unbrauchbar -- der Bot setzt auch eigene
    Vorschlaege in Anfuehrungszeichen ("waere 'Ankommen' ein Kernthema fuer
    euch?"), und die stehen naturgemaess in keinem Transkript.

    Verglichen wird mit ``zitat.normalisiere``, derselben Normalisierung, mit
    der im Betrieb ueber ein Belegzitat entschieden wird."""
    material_text = " ".join(zitat.normalisiere(t) for t in transkripte)
    treffer = []
    for zug in zuege:
        if zug.marke != marke:
            continue
        for text in zug.bot:
            for gefunden in _IN_ANFUEHRUNG.findall(text):
                if len(gefunden.split()) < ZITAT_MINDEST_WOERTER:
                    continue
                if zitat.normalisiere(gefunden) not in material_text:
                    treffer.append(gefunden.strip())
    return treffer


# ---------------------------------------------------------------------------
# Journal und Kontextaufbau (N4a, N4b)
# ---------------------------------------------------------------------------


def _kern(text: str) -> frozenset:
    """Die bedeutungstragenden Woerter eines Journaleintrags -- fuer die
    Dublettenpruefung. Grob mit Absicht: zwei Eintraege ueber dieselbe Sache
    sind selten wortgleich, aber fast immer wortgleich in den Substantiven."""
    worte = {w for w in _falte(text).split() if len(w) > 4}
    return frozenset(worte)


#: Ab welchem Anteil gemeinsamer Kernwoerter zwei Journaleintraege als
#: Dublette gelten. 0,7 ist hoch angesetzt: ein falscher Treffer waere hier
#: ein Vorwurf gegen den Extraktor, den niemand nachvollziehen koennte.
DUBLETTE_AB = 0.7


def journallage(conn, chat_id: int) -> dict:
    """Was am Ende im Journal steht -- je Art gezaehlt, plus Dubletten.

    ``ausgeloest`` sagt, ob der Journal-Extraktor ueberhaupt gelaufen ist. Er
    laeuft nur bei Verdraengung (``journal.berechne_verdraengten_abschnitt``),
    und ein kurzer Lauf verdraengt nie etwas. Im Bericht steht dann "Journal
    nicht ausgeloest" statt einer Null-Note: eine Null waere die Behauptung,
    der Extraktor habe nichts gefunden -- er ist gar nicht gefragt worden."""
    eintraege = repo.journal(conn, chat_id)
    je_art: dict[str, int] = {}
    je_quelle: dict[str, int] = {}
    for e in eintraege:
        je_art[e["art"]] = je_art.get(e["art"], 0) + 1
        quelle = e["quelle"] or "?"
        je_quelle[quelle] = je_quelle.get(quelle, 0) + 1

    vorgeschlagen = [e["text"] for e in eintraege if e["art"] == "vorgeschlagen"]
    dubletten = []
    kerne = [(t, _kern(t)) for t in [e["text"] for e in eintraege]]
    for i, (text_a, kern_a) in enumerate(kerne):
        for text_b, kern_b in kerne[i + 1:]:
            if not kern_a or not kern_b:
                continue
            gemeinsam = len(kern_a & kern_b) / max(len(kern_a), len(kern_b))
            if gemeinsam >= DUBLETTE_AB:
                dubletten.append((text_a, text_b))

    return {
        "journal_eintraege": len(eintraege),
        "journal_je_art": dict(sorted(je_art.items())),
        "journal_je_quelle": dict(sorted(je_quelle.items())),
        "journal_vorgeschlagen": vorgeschlagen,
        "journal_dubletten": dubletten,
        "journal_ausgeloest": je_quelle.get("extraktor", 0) > 0,
    }


#: Die Arbeitsstandfelder, deren Vorhandensein in der Datenlage vermerkt
#: wird. Aus dem Schema gelesen, nicht aufgezaehlt -- nach einem Umbau der
#: Phase 5 taucht das neue Feld von selbst auf.
def datenlage(conn, chat_id: int) -> dict:
    """Was zu diesem Zeitpunkt in der Datenbank steht -- gezaehlt, nicht im
    Wortlaut.

    Wird je Zug festgehalten, weil der Richter bei den schwaechsten Antworten
    beurteilen soll, ob dem Bot **Information gefehlt** hat, die dagewesen
    waere (N4b). Ohne diese Momentaufnahme liesse sich das nur gegen den
    Endstand pruefen -- und der sagt ueber den dritten Zug nichts."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    gesetzt = []
    if stand is not None:
        for spalte in skript.arbeitsstand_spalten(conn):
            if spalte in skript._KEINE_FELDER:
                continue
            try:
                if stand[spalte]:
                    gesetzt.append(spalte)
            except (IndexError, KeyError):
                continue
    gruppe = repo.hole_gruppe(conn, chat_id)
    return {
        "verdichtungen": len(repo.verdichtungen(conn, chat_id)),
        "transkripte": len(repo.transkripte(conn, chat_id)),
        "figuren": len(repo.figuren(conn, chat_id)),
        "journal": len(repo.journal(conn, chat_id)),
        "szenen": len(repo.hole_szenen(conn, chat_id)),
        "arbeitsstand": gesetzt,
        "wortlaut_modus": (gruppe["wortlaut_modus"] if gruppe else None) or "aus",
    }


def datenlage_text(lage: dict) -> str:
    """Die Datenlage als lesbare Zeilen fuer den Richter."""
    if not lage:
        return ""
    return "\n".join([
        f"- Verdichtungen: {lage['verdichtungen']}",
        f"- Transkripte: {lage['transkripte']} (Wortlaut-Modus: {lage['wortlaut_modus']})",
        f"- Figuren: {lage['figuren']}, Szenen: {lage['szenen']}, "
        f"Journaleintraege: {lage['journal']}",
        "- gesetzte Arbeitsstandfelder: "
        + (", ".join(lage["arbeitsstand"]) or "keine"),
    ])


def kontextlage(zuege: list[Zug]) -> dict:
    """Was wann im Gespraechs-Prompt stand -- die Frage aus N4b.

    Je Block der Median und das Maximum der geschaetzten Token ueber alle
    Zuege, dazu die Zahl der Prompts ueber ``kontext.ZIEL`` und die mit
    Kuerzung. Der Median, nicht der Mittelwert: ein einzelner Prompt mit
    Volltranskripten wuerde den Mittelwert reissen und ueber die uebrigen
    dreissig nichts mehr sagen."""
    umrisse = [u for z in zuege for u in z.kontext]
    if not umrisse:
        return {
            "kontext_zuege": 0, "kontext_bloecke": {},
            "kontext_ueber_ziel": 0, "kontext_gekuerzt": 0,
            "kontext_gesamt_median": 0, "kontext_gesamt_max": 0,
        }

    namen = sorted({name for u in umrisse for name in u["bloecke"]})
    bloecke = {}
    for name in namen:
        werte = [u["bloecke"].get(name, 0) for u in umrisse]
        bloecke[name] = {
            "median": int(statistics.median(werte)),
            "max": max(werte),
            "leer": sum(1 for w in werte if w == 0),
        }
    gesamt = [u["gesamt"] for u in umrisse]
    return {
        "kontext_zuege": len(umrisse),
        "kontext_bloecke": bloecke,
        "kontext_ueber_ziel": sum(1 for g in gesamt if g > kontext.ZIEL),
        "kontext_gekuerzt": sum(1 for u in umrisse if u["gekuerzt"]),
        "kontext_gesamt_median": int(statistics.median(gesamt)),
        "kontext_gesamt_max": max(gesamt),
    }


def _figuren_inkl_entfernt(conn, chat_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM figur WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]


def arbeitsstand_vollstaendig(conn, chat_id: int) -> dict[str, int]:
    """Je Feld 0/1: Begriffe, Fragen, Kernthema, drei Figuren, das
    Pflichtfeld der Phase 5 (heute ``format``).

    Das letzte kommt aus ``skript.pflichtfeld_fuer_phase`` und damit aus dem
    Schema -- nach einem Umbau der Phase 5 misst diese Funktion das neue Feld,
    ohne dass jemand sie nachzieht. Nur das Pflichtfeld: ``rahmen`` darf leer
    bleiben, und eine Kennzahl, die es mitzaehlt, meldete einen Lauf als
    unvollstaendig, dem nichts fehlt."""
    ergebnis = {
        "begriffe": int(skript._stand_gesetzt(conn, chat_id, "begriffe")),
        "fragen": int(skript._stand_gesetzt(conn, chat_id, "fragen")),
        "kernthema": int(skript._stand_gesetzt(conn, chat_id, "kernthema")),
        # Figuren INKLUSIVE der weich geloeschten: Skript-Schritt 8 entfernt
        # absichtlich eine, und die Kennzahl soll messen, ob der Bot drei
        # ANGELEGT hat -- nicht, ob am Ende noch drei stehen (gemessen 05.09.,
        # set1 seed1 nachher: drei angelegt, eine entfernt, Kennzahl 0).
        f"figuren_{skript.FIGUREN_SOLL}": int(
            _figuren_inkl_entfernt(conn, chat_id) >= skript.FIGUREN_SOLL
        ),
    }
    feld = skript.pflichtfeld_fuer_phase(conn, skript.PHASE_MITTE)
    if feld:
        ergebnis[feld] = int(skript._stand_gesetzt(conn, chat_id, feld))
    else:
        ergebnis[f"phase_{skript.PHASE_MITTE}_erreicht"] = int(
            phasen.aktuelle(conn, chat_id) >= skript.PHASE_MITTE
        )
    return ergebnis


def zitatlage(conn, chat_id: int, gezogene) -> dict:
    """Verdichtungen, geprueftes Belegzitat, gefundene Soll-Zitate.

    ``zitate_soll`` ist die einzige Zahl im Bericht, die etwas ueber die
    **inhaltliche** Qualitaet der Verdichtung sagt, ohne ein Modell zu
    fragen: die drei Saetze je Interviewdatei sind mit der Hand ausgesucht,
    und ein Verdichter, der keinen davon findet, hat am Material vorbei
    gelesen. Verglichen wird als Teilstring nach ``zitat.normalisiere`` --
    dieselbe Normalisierung, mit der im Betrieb entschieden wird, ob ein
    Zitat stehen bleibt."""
    verdichtungen = repo.verdichtungen(conn, chat_id)
    themen = [t for v in verdichtungen for t in repo.themen_zu(conn, v["id"])]
    geprueft = [t for t in themen if t["zitat_geprueft"] == 1]

    belege = " ".join(
        zitat.normalisiere(t["beleg_zitat"] or "") for t in themen
    )
    soll = [s for interview in gezogene for s in interview.zitate_soll]
    gefunden = [s for s in soll if zitat.normalisiere(s) in belege]

    return {
        "verdichtungen": len(verdichtungen),
        "themen": len(themen),
        "zitate_geprueft": len(geprueft),
        "zitate_soll": len(soll),
        "zitate_soll_gefunden": len(gefunden),
        "zitate_soll_vermisst": [s for s in soll if s not in gefunden],
    }


#: Woran erkannt wird, dass der Bot nach der Nacht wieder von vorn anfaengt,
#: die Bedienung zu erklaeren. Die Wiederkehr-Zeile soll sagen, wo man steht,
#: und sonst nichts -- wer den Interviewmodus zum zweiten Mal erklaert
#: bekommt, liest ihn nicht.
_BEFEHLSERKLAERUNG = ("/hilfe", "wir machen jetzt ein interview", "fertig beendet",
                      "ich lese alles mit")


def wiederkehr(zeilen: list[str], phase_bezeichnung: str) -> dict:
    """Was der Bot nach der simulierten Nacht geschickt hat (``--pause``).

    Zwei Fragen: nennt er die richtige Phase, und faengt er wieder an, die
    Befehle zu erklaeren? Beides mechanisch -- die Wiederkehr-Zeile ist ein
    fester Text (``bot._TEXT_WIEDERKEHR``), da gibt es nichts zu deuten."""
    text = "\n".join(zeilen)
    gefaltet = _falte(text)
    return {
        "wiederkehr_zeilen": list(zeilen),
        "wiederkehr_phase_richtig": _falte(phase_bezeichnung) in gefaltet,
        "wiederkehr_erklaert_befehle": any(
            _falte(w) in gefaltet for w in _BEFEHLSERKLAERUNG
        ),
    }


def vorfaelle(conn, chat_id: int) -> dict[str, int]:
    """Die Vorfaelle dieses Laufs, je Art gezaehlt.

    ``http_5xx`` ist die Zahl, die ``--parallel`` interessant macht: zwei
    Gruppen gegen denselben Anbieter, und die Frage ist, wie oft er dabei
    drosselt."""
    zeilen = conn.execute(
        "SELECT art, count(*) AS n FROM vorfall WHERE chat_id = ? GROUP BY art",
        (chat_id,),
    ).fetchall()
    return {z["art"]: z["n"] for z in zeilen}


#: Wie viele Laeufe ein Workshop mit drei Gruppen an zwei Tagen ausmacht --
#: und wie viele in Padua (drei Gruppen, fuenfzehn Tage). Ein Lauf entspricht
#: dabei EINEM Workshoptag EINER Gruppe: er faehrt alle Phasen durch, aber
#: mit fuenf Interviews und rund vierzig Nachrichten, und das ist die
#: Groessenordnung eines Tages, nicht die eines ganzen Workshops.
HOCHRECHNUNG = (
    ("eine Gruppe, ein Tag", 1),
    ("3 Gruppen x 2 Tage", 6),
    ("3 Gruppen x 15 Tage (Padua)", 45),
)


def hochrechnung(chf_lauf: float) -> list[tuple[str, float]]:
    """Die Kosten eines Laufs auf die geplanten Workshops hochgerechnet."""
    return [(name, round(chf_lauf * faktor, 2)) for name, faktor in HOCHRECHNUNG]


def kosten(conn, e, preise: dict) -> dict:
    """Kosten in CHF -- **nur der Bot**.

    Die Tabelle ``aufruf`` haelt kein Modell fest, nur die ``art`` -- die
    Zuordnung art -> Modell ist deshalb dieselbe wie im Betrieb
    (``scripts.pruefe_prompts.modell_fuer``): Gespraech, Verdichter und Szene
    laufen mit dem Gespraechsmodell, Erkenner und Journal mit gemma.

    Die Simulationsseite (Stimmen, Richter) steht seit dem Modellwechsel gar
    nicht mehr in dieser Tabelle: sie laeuft ueber Claude am lokalen Proxy und
    kostet je Aufruf nichts (``simulation/claude.py``). Ihre Aufrufzahlen
    kommen aus ``claude.Statistik`` und werden im Bericht getrennt
    ausgewiesen -- was hier steht, ist damit genau das, was ein echter
    Workshoptag an Infomaniak zahlen wuerde."""
    modelle = {
        "gespraech": e.llm_modell,
        "verdichter": e.llm_modell,
        "szene": e.llm_modell,
        "erkenner": e.erkenner_modell,
        "journal": e.erkenner_modell,
    }

    summe = 0.0
    token = {"ein": 0, "aus": 0}
    aufrufe = 0
    je_art: dict[str, float] = {}
    for zeile in conn.execute(
        "SELECT art, sum(tatsaechliche_token) AS ein, sum(antwort_token) AS aus, "
        "count(*) AS n FROM aufruf GROUP BY art"
    ):
        art = zeile["art"]
        ein, aus = zeile["ein"] or 0, zeile["aus"] or 0
        token["ein"] += ein
        token["aus"] += aus
        aufrufe += zeile["n"]
        preis = preise.get(modelle.get(art, ""))
        if preis is None:
            continue
        chf = (ein * preis[0] + aus * preis[1]) / 1_000_000
        summe += chf
        je_art[art] = round(je_art.get(art, 0.0) + chf, 4)
    return {
        "chf_bot": round(summe, 4),
        "chf_je_art": dict(sorted(je_art.items())),
        "token_ein": token["ein"],
        "token_aus": token["aus"],
        "aufrufe": aufrufe,
    }


def sammle(conn, chat_id: int, zuege: list[Zug], gezogene, namen, markiert,
           schritte, e, preise, dauer_s: float, notausgaenge: int = 0,
           sim_statistik: dict | None = None, journal_urteil: dict | None = None,
           stoerung: dict | None = None, wiederkehr_zeilen: list | None = None,
           tg=None, knopfdruecke=None, phasen_proaktiv=None,
           phasen_selbst=None) -> dict:
    """Alle mechanischen Kennzahlen eines Laufs in einem Dict -- die Form, in
    der sie in den Bericht und nach ``verlauf.jsonl`` gehen.

    ``tg``, ``knopfdruecke``, ``phasen_proaktiv`` und ``phasen_selbst`` kamen
    am 06.09.2026 dazu (Knopf-Umbau) und sind optional: eine alte
    Verlaufszeile ohne diese Felder bleibt lesbar, und ein Aufrufer, der sie
    nicht hat, bekommt Nullen statt eines TypeError."""
    gespeichert, zustimmung_gesamt = zustimmungen(zuege, markiert)
    zahlen = {
        "interviews_soll": len(gezogene),
        "notausgaenge": notausgaenge,
        "phase_erreicht": phasen.aktuelle(conn, chat_id),
        "phase_erreicht_name": phasen.bezeichnung(phasen.aktuelle(conn, chat_id)),
        "phase_soll": skript.phase_szenen(),
        "arbeitsstand_vollstaendig": arbeitsstand_vollstaendig(conn, chat_id),
        "zustimmungen": zustimmung_gesamt,
        "zustimmungen_gespeichert": gespeichert,
        "echo": len(echos(zuege)),
        "bot_rueckfragen": len(bot_rueckfragen(zuege)),
        "optionenlisten": len(optionenlisten(zuege)),
        "rueckfragen_vor_szene": len(rueckfragen_vor_szene(zuege)),
        "behauptete_schreibvorgaenge": len(behauptete_schreibvorgaenge(zuege)),
        "namensanrede": len(namensanreden(zuege, namen)),
        "laenge_bot": laenge_bot(zuege),
        "bot_antworten": len(bot_antworten(zuege)),
        "stimm_nachrichten": sum(len(z.beitraege) for z in zuege),
        "schritte_gescheitert": [s for s, ok in schritte.items() if not ok],
        "dauer_s": round(dauer_s, 1),
        # Der Wortlaut, nicht nur die 0/1 aus ``arbeitsstand_vollstaendig``:
        # der Referenzvergleich von ``--set birk`` stellt das Kernthema von
        # heute neben das von damals, und dafuer braucht er den Satz.
        "kernthema": _stand_wert(conn, chat_id, "kernthema"),
        "figuren": [f["name"] for f in repo.figuren(conn, chat_id)],
        "latenzen": latenzen(zuege),
        "vorfaelle": vorfaelle(conn, chat_id),
        "zitat_erfunden": len(
            erfundene_zitate(zuege, [i.transkript for i in gezogene])
        ),
        "zitat_erfunden_liste": erfundene_zitate(
            zuege, [i.transkript for i in gezogene]
        ),
    }
    zahlen.update(journallage(conn, chat_id))
    zahlen.update(kontextlage(zuege))
    zahlen.update(journal_urteil or {})
    zahlen.update(stoerung or {"stoerung": "", "stoerung_geworfen": 0,
                               "stoerung_zuege": []})
    zahlen.update(wiederkehr(
        wiederkehr_zeilen or [],
        phasen.bezeichnung(phasen.aktuelle(conn, chat_id)),
    ) if wiederkehr_zeilen is not None else {})
    zahlen.update(zitatlage(conn, chat_id, gezogene))
    zahlen.update(sammle_knopfzahlen(
        conn, chat_id, zuege, tg, knopfdruecke or [],
        phasen_proaktiv or [], phasen_selbst or [],
    ))
    zahlen.update(kosten(conn, e, preise))
    zahlen["hochrechnung"] = hochrechnung(zahlen["chf_bot"])
    zahlen.update(sim_statistik or {
        "sim_aufrufe": 0, "sim_aufrufe_je_art": {},
        "sim_token_ein": 0, "sim_token_aus": 0, "sim_fehler": 0,
    })
    return zahlen


# ---------------------------------------------------------------------------
# Die Kennzahlen des Knopf-Umbaus (06.09.2026)
# ---------------------------------------------------------------------------
#
# Alle mechanisch, keine mit Modell. Sie messen genau das, was am Testabend
# schiefging: zwanzig Nachrichten je Festlegung, 64 % Fragen, 23 angebotene
# Knoepfe und null Druecke.

#: Sollwert: so viele Nachrichten der Gruppe darf eine Festlegung hoechstens
#: kosten. Zwei, weil eine Festlegung im Regelfall aus einem Vorschlag und
#: einem Druck besteht.
SOLL_NACHRICHTEN_JE_FESTLEGUNG = 2

#: Sollwert: so viele Fragezeichen darf eine Bot-Nachricht im Schnitt tragen.
SOLL_FRAGEN_JE_NACHRICHT = 1.0

#: Ab welcher Deckung zwei Bot-Nachrichten als Wiederholung zaehlen -- dieselbe
#: Schwelle, mit der ``ablauf.ist_wiederholung`` im Betrieb verwirft.
WIEDERHOLUNG_AB = 0.6


def nachrichten_je_festlegung(zuege: list[Zug]) -> dict:
    """Wie viele Stimm-Nachrichten zwischen zwei Notiert-Zeilen lagen.

    Dieselbe Definition wie ``birk.referenz``: die Notiert-Zeilen sind die
    Trennmarken zwischen den Arbeitsschritten, was dazwischen liegt, hat die
    Gruppe gebraucht, um eine Festlegung durchzubekommen. Median statt
    Mittelwert -- ein einzelner Abschnitt, in dem der Erkenner taub war,
    verschoebe den Mittelwert um mehr, als die uebrigen aussagen.

    Knopfdruecke zaehlen **mit**: sie sind Aufwand fuer die Gruppe, auch wenn
    sie keine Nachricht sind. Ein Ablauf, der eine Festlegung auf fuenf
    Knopfdruecke verteilt, ist nicht besser als einer mit fuenf Nachrichten."""
    abschnitte: list[int] = []
    laufend = 0
    for zug in zuege:
        laufend += len(zug.beitraege)
        if zug.marke == "knopf":
            laufend += 1
        if zug.hat_notiert:
            abschnitte.append(laufend)
            laufend = 0
    return {
        "festlegungen": len(abschnitte),
        "nachrichten_je_festlegung": abschnitte,
        "nachrichten_je_festlegung_median": (
            round(statistics.median(abschnitte), 1) if abschnitte else 0
        ),
    }


def fragen_je_botnachricht(zuege: list[Zug]) -> float:
    """Fragezeichen je Bot-Nachricht (Soll <= 1).

    Gezaehlt werden Fragezeichen, nicht Nachrichten mit Fragezeichen: der
    gemessene Fall vom Testabend war eine Nachricht mit vier Fragen darin, und
    die zaehlt hier vierfach. Genau darum geht es -- "Stell immer nur eine
    Frage auf einmal" (Birk, 06.09.)."""
    antworten = bot_antworten(zuege)
    if not antworten:
        return 0.0
    return round(sum(t.count("?") for t in antworten) / len(antworten), 2)


def _deckung(a: str, b: str) -> float:
    """Wortdeckung zweier Texte -- der Rueckfall, wenn
    ``ablauf.ist_wiederholung`` eine andere Signatur hat als erwartet."""
    worte_a = set(_falte(a).split())
    worte_b = set(_falte(b).split())
    if not worte_a or not worte_b:
        return 0.0
    gemeinsam = len(worte_a.intersection(worte_b))
    return gemeinsam / max(len(worte_a), len(worte_b))


def wiederholungsquote(zuege: list[Zug], ab: float = WIEDERHOLUNG_AB) -> dict:
    """Anteil der Bot-Nachrichten, die die vorherige Bot-Nachricht
    wiederholen.

    Geprueft wird mit ``ablauf.ist_wiederholung``, derselben Funktion, mit der
    der Betrieb seit dem 06.09. verwirft -- eine zweite Wahrheit ueber
    dieselbe Frage waere im Bericht nicht mit dem Vorfall
    ``wiederholung_verworfen`` vergleichbar. Verworfene Antworten stehen
    naturgemaess nicht in dieser Liste; was hier auftaucht, ist durch die
    Sperre GEKOMMEN."""
    antworten = bot_antworten(zuege)
    pruefe = getattr(ablauf, "ist_wiederholung", None)
    treffer = []
    for vorher, nachher in zip(antworten, antworten[1:]):
        ist_wdh = False
        if pruefe is not None:
            try:
                ist_wdh = bool(pruefe(nachher, vorher))
            except Exception:  # noqa: BLE001 -- andere Signatur im Betrieb
                ist_wdh = _deckung(nachher, vorher) >= ab
        else:
            ist_wdh = _deckung(nachher, vorher) >= ab
        if ist_wdh:
            treffer.append(nachher)
    nenner = max(1, len(antworten) - 1)
    return {
        "wiederholungen": len(treffer),
        "wiederholungsquote": round(len(treffer) / nenner, 2) if antworten else 0.0,
        "wiederholungen_liste": treffer[:5],
    }


#: Woran erkannt wird, dass der Bot parallel zu einem laufenden Auftrag
#: weiterredet: der Gespraechs-Bot soll schweigen, solange ein Auftrag laeuft
#: (``ablauf.ist_auftrag``). Gemessen wird an der Marke des Zuges.
AUFTRAGSMARKEN = ("szene_aufruf",)


def parallel_zum_auftrag(zuege: list[Zug]) -> list[str]:
    """Bot-Nachrichten, die im selben Zug wie ein Auftrag stehen und nicht
    zum Auftrag gehoeren (Soll 0).

    Der gemessene Fall: die Gruppe sagt "schreib Szene 1", der Szenen-Thread
    laeuft an -- und der Gespraechs-Bot antwortet daneben noch einmal auf
    dieselbe Nachricht. Die Gruppe liest zwei Antworten auf eine Frage und
    weiss nicht, welche gilt."""
    treffer = []
    for zug in zuege:
        if zug.marke not in AUFTRAGSMARKEN:
            continue
        # Die erste Nachricht ist die Ansage bzw. der Szenentext selbst; was
        # danach in DEMSELBEN Zug kommt, ist Parallelrede.
        treffer.extend(zug.bot[1:])
    return treffer


def knopflage(tg, knopfdruecke: list) -> dict:
    """Angeboten gegen gedrueckt -- die Zahl aus dem Testabend (23 zu 0).

    ``angeboten`` zaehlt Knoepfe, nicht Leisten: eine Leiste mit drei
    Knoepfen ist drei Angebote, und die Frage ist, wie viele davon je
    benutzt werden."""
    angeboten = sum(len(a.get("knoepfe") or []) for a in getattr(tg, "knoepfe", []))
    gedrueckt = len(knopfdruecke)
    je_beschriftung: dict[str, int] = {}
    for druck in knopfdruecke:
        name = druck.get("beschriftung") or "?"
        je_beschriftung[name] = je_beschriftung.get(name, 0) + 1
    return {
        "knoepfe_angeboten": angeboten,
        "knoepfe_gedrueckt": gedrueckt,
        "knoepfe_quote": round(gedrueckt / angeboten, 2) if angeboten else 0.0,
        "knoepfe_je_beschriftung": dict(sorted(je_beschriftung.items())),
    }


def phasenlage(proaktiv: list, selbst: list) -> dict:
    """Wie die Gruppe durch die Phasen kam: ueber das proaktive Angebot des
    Bots oder ueber den versteckten ``/phase``-Befehl.

    Der zweite Weg ist der Befund. Eine echte Gruppe kennt ``/phase`` nicht
    (Slash-Befehle werden nicht mehr beworben, AGENTS.md) -- wo der Simulator
    ihn braucht, waere eine echte Gruppe steckengeblieben."""
    gesamt = len(proaktiv) + len(selbst)
    return {
        "phasenwechsel_proaktiv": list(proaktiv),
        "phasenwechsel_selbst": list(selbst),
        "phasenwechsel_proaktiv_anteil": (
            round(len(proaktiv) / gesamt, 2) if gesamt else 0.0
        ),
    }


def formlage(conn, chat_id: int) -> dict:
    """Je Szene: gab es einen Formvorschlag, und wurde er BESTAETIGT?

    ``szene.form`` bleibt seit dem 06.09.2026 leer, bis die Gruppe die Form
    per Knopf bestaetigt (``form_vorschlag`` traegt den Vorschlag). Eine Szene
    mit gesetzter ``form`` und ohne ``form_vorschlag`` ist deshalb ein
    Befund: dort hat jemand die Form gesetzt statt bestaetigen zu lassen."""
    szenen = repo.hole_szenen(conn, chat_id)
    vorgeschlagen = bestaetigt = gesetzt_ohne_vorschlag = 0
    for zeile in szenen:
        try:
            vorschlag = (zeile["form_vorschlag"] or "").strip()
        except (IndexError, KeyError):
            vorschlag = ""
        form = (zeile["form"] or "").strip()
        if vorschlag:
            vorgeschlagen += 1
        if form and vorschlag:
            bestaetigt += 1
        if form and not vorschlag:
            gesetzt_ohne_vorschlag += 1
    return {
        "szenen_gesamt": len(szenen),
        "form_vorgeschlagen": vorgeschlagen,
        "form_bestaetigt": bestaetigt,
        "form_gesetzt_ohne_vorschlag": gesetzt_ohne_vorschlag,
    }


def rahmen_ueberschrieben(conn, chat_id: int) -> int:
    """Wie oft ein gesetzter Rahmen bzw. eine gesetzte Geschichte ersetzt
    wurde -- aus dem Journal gezaehlt.

    "Still ueberschrieben" laesst sich hier nicht sauber von "die Gruppe hat
    es geaendert" trennen; gezaehlt wird deshalb die schwaechere, aber
    nachpruefbare Groesse -- **mehr als ein** Eintrag je Feld. Im Bericht
    steht sie mit dieser Einschraenkung daneben."""
    zeilen = repo.journal(conn, chat_id)
    je_feld: dict[str, int] = {}
    for eintrag in zeilen:
        text = _falte(eintrag["text"] or "")
        for feld in ("rahmen", "setting", "geschichte"):
            if text.startswith(feld):
                je_feld[feld] = je_feld.get(feld, 0) + 1
    return sum(max(0, n - 1) for n in je_feld.values())


def sammle_knopfzahlen(conn, chat_id: int, zuege: list[Zug], tg,
                       knopfdruecke: list, proaktiv: list, selbst: list) -> dict:
    """Alle Kennzahlen des Knopf-Umbaus in einem Dict -- die Form, in der sie
    ``sammle`` beigemischt werden."""
    zahlen = {
        "fragen_je_botnachricht": fragen_je_botnachricht(zuege),
        "parallel_zum_auftrag": len(parallel_zum_auftrag(zuege)),
        "rahmen_ueberschrieben": rahmen_ueberschrieben(conn, chat_id),
    }
    zahlen.update(nachrichten_je_festlegung(zuege))
    zahlen.update(wiederholungsquote(zuege))
    zahlen.update(knopflage(tg, knopfdruecke))
    zahlen.update(phasenlage(proaktiv, selbst))
    zahlen.update(formlage(conn, chat_id))
    return zahlen

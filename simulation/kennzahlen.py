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
_IN_ANFUEHRUNG = re.compile(r'[„"»“]([^„"»«“”]{20,400})[”“"«]')

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


def arbeitsstand_vollstaendig(conn, chat_id: int) -> dict[str, int]:
    """Je Feld 0/1: Begriffe, Fragen, Kernthema, drei Figuren, die Felder der
    Phase 5.

    Die letzten kommen aus ``skript.felder_fuer_phase`` und damit aus dem
    Schema -- nach einem Umbau der Phase 5 misst diese Funktion die neuen
    Felder, ohne dass jemand sie nachzieht."""
    ergebnis = {
        "begriffe": int(skript._stand_gesetzt(conn, chat_id, "begriffe")),
        "fragen": int(skript._stand_gesetzt(conn, chat_id, "fragen")),
        "kernthema": int(skript._stand_gesetzt(conn, chat_id, "kernthema")),
        f"figuren_{skript.FIGUREN_SOLL}": int(
            len(repo.figuren(conn, chat_id)) >= skript.FIGUREN_SOLL
        ),
    }
    felder = skript.felder_fuer_phase(conn, skript.PHASE_MITTE)
    if felder:
        for feld in felder:
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
           stoerung: dict | None = None, wiederkehr_zeilen: list | None = None) -> dict:
    """Alle mechanischen Kennzahlen eines Laufs in einem Dict -- die Form, in
    der sie in den Bericht und nach ``verlauf.jsonl`` gehen."""
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
    zahlen.update(kosten(conn, e, preise))
    zahlen["hochrechnung"] = hochrechnung(zahlen["chf_bot"])
    zahlen.update(sim_statistik or {
        "sim_aufrufe": 0, "sim_aufrufe_je_art": {},
        "sim_token_ein": 0, "sim_token_aus": 0, "sim_fehler": 0,
    })
    return zahlen

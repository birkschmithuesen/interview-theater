"""Der Ablauf, den die simulierten Teilnehmerinnen *wollen*.

Neun Schritte, jeder mit einem **Ziel** (was die Stimmen anstreben, nicht
was sie woertlich sagen) und einem **Zielzustand in der Datenbank** (woran
der Lauf merkt, dass der Schritt durch ist). Ist der Zielzustand nach
``MAX_NACHRICHTEN`` Stimm-Nachrichten nicht erreicht, gilt der Schritt als
**gescheitert**, wird so vermerkt, und der Lauf geht trotzdem weiter -- ein
Workshop bleibt auch nicht stehen, weil der Bot etwas nicht mitbekommen hat.

**Datengetrieben, nicht hart codiert.** Die Phasen kommen aus
``phasen.PHASEN``, die Arbeitsstandfelder aus ``PRAGMA
table_info(arbeitsstand)``. Welches Feld zu Phase 5 gehoert, wird aus ihrem
Kurznamen abgeleitet (``felder_fuer_phase``): heisst sie seit dem 05.09.2026
'Rahmen', ist es ``rahmen``; hiesse sie wieder
'Hauptkonflikt', waere es die Spalte ``hauptkonflikt``. Findet sich gar keine
Spalte, faellt die Pruefung auf 'die Gruppe steht in dieser Phase' zurueck --
lieber eine schwaechere Aussage als eine falsche.

**Pflicht ist das erste Feld** (``pflichtfeld_fuer_phase``). Ein Kurzname
nennt zuerst die Entscheidung, die die naechste Phase traegt: ohne
``format`` weiss niemand, ob die naechste Szene ein Dialog oder ein Rap wird,
``rahmen`` darf leer bleiben -- genau so haelt es ``phasen.voraussetzungen``
fuer den Schritt von 5 nach 6.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Callable

from interview_theater import phasen, repo

#: Hoechstzahl an Stimm-Nachrichten je Schritt, bevor er als gescheitert
#: gilt. Sechs ist die Vorgabe aus dem Auftrag: genug fuer Vorschlag,
#: Korrektur und Zustimmung, wenig genug, dass ein Lauf mit einem tauben Bot
#: nicht ewig dauert.
MAX_NACHRICHTEN = 6

#: Wie viele Figuren die Gruppe anlegen will (Skript-Schritt 5) -- dieselbe
#: Zahl steht in der Kennzahl ``arbeitsstand_vollstaendig``.
FIGUREN_SOLL = 3

#: Die Phase, deren Feld(er) Schritt 6 fuellt. Bewusst die **Nummer** und
#: nicht der Name: wie sie heisst, liest der Schritt zur Laufzeit aus
#: ``phasen.PHASEN``.
PHASE_MITTE = 5

#: Die Phase, in der ein Lauf enden soll (Kennzahl ``phase_erreicht``).
#: Ueber den Kurznamen gesucht, nicht als Zahl hingeschrieben: nach einem
#: Umbau der Phasenliste soll der Simulator dieselbe Station meinen, auch
#: wenn sie eine andere Nummer traegt.
PHASE_SZENEN_NAME = "Szenen"


def phase_szenen() -> int:
    """Die Nummer der Szenen-Phase, aus ``phasen.PHASEN`` gesucht.

    Faellt auf die letzte Phase zurueck, wenn keine so heisst -- dann ist die
    Aussage 'so weit ist die Gruppe gekommen' zwar strenger als gemeint, aber
    nie falsch."""
    nummer = phasen.nummer_fuer(PHASE_SZENEN_NAME)
    return nummer if nummer is not None else phasens_letzte()


def phasens_letzte() -> int:
    return phasen.PHASEN[-1][0]


# ---------------------------------------------------------------------------
# Arbeitsstandfelder einer Phase -- aus dem Schema, nicht aus einer Liste
# ---------------------------------------------------------------------------

#: Spalten der Tabelle ``arbeitsstand``, die zu keiner Phase gehoeren koennen
#: -- Schluessel und Buchhaltung. Ohne sie wuerde eine Phase namens 'Phase'
#: sich selbst als Feld finden.
_KEINE_FELDER = {"chat_id", "geaendert_am", "phase", "phase_angeboten"}


def _falte(text: str) -> str:
    """Kleinschreibung ohne Umlaute und ohne Sonderzeichen -- damit
    'Format', 'format' und 'Rahmen/Format' dieselben Spalten finden."""
    ohne = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return "".join(z for z in ohne.lower() if z.isalnum())


def arbeitsstand_spalten(conn) -> list[str]:
    """Die Spalten der Tabelle ``arbeitsstand``, wie sie gerade wirklich
    aussieht (``PRAGMA table_info``) -- nicht wie sie in ``db.SCHEMA``
    stand, als dieser Simulator geschrieben wurde."""
    return [z["name"] for z in conn.execute("PRAGMA table_info(arbeitsstand)")]


def felder_fuer_phase(conn, nummer: int) -> list[str]:
    """Die Arbeitsstandspalten, die zum Kurznamen einer Phase passen.

    'Rahmen' -> ``["rahmen"]``, 'Kernthema & Figuren' ->
    ``["kernthema"]`` (Figuren sind eine eigene Tabelle), 'Hauptkonflikt' ->
    ``["hauptkonflikt"]``, falls es diese Spalten gibt. Leere Liste, wenn
    keine passt -- der Aufrufer weicht dann auf die Phase selbst aus.

    Die Reihenfolge ist die des Kurznamens, nicht die der Tabelle: davon
    haengt ab, welches Feld ``pflichtfeld_fuer_phase`` nimmt."""
    spalten = {_falte(s): s for s in arbeitsstand_spalten(conn) if s not in _KEINE_FELDER}
    worte = [w for w in phasen.kurzname(nummer).replace("&", " ").split() if w]
    treffer = []
    for wort in worte:
        spalte = spalten.get(_falte(wort))
        if spalte and spalte not in treffer:
            treffer.append(spalte)
    return treffer


def pflichtfeld_fuer_phase(conn, nummer: int) -> str:
    """Das eine Feld, ohne das die Phase nicht durch ist -- das erste aus
    ``felder_fuer_phase``, oder ein leerer String.

    Ein Kurzname nennt zuerst die Entscheidung, die die naechste Phase traegt:
    bei 'Rahmen' ist das ``rahmen`` (ohne Rahmen weiss niemand, worin die
    naechste Szene ein Dialog oder ein Rap wird), waehrend ``rahmen`` leer
    bleiben darf -- dieselbe Gewichtung wie in ``phasen.voraussetzungen`` fuer
    den Schritt von 5 nach 6. Bei einem einwortigen Kurznamen
    ('Hauptkonflikt') ist es das einzige Feld, und die Unterscheidung faellt
    nicht auf."""
    felder = felder_fuer_phase(conn, nummer)
    return felder[0] if felder else ""


def _stand_gesetzt(conn, chat_id: int, feld: str) -> bool:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return False
    try:
        return bool(stand[feld])
    except (IndexError, KeyError):
        return False


# ---------------------------------------------------------------------------
# Die Schritte
# ---------------------------------------------------------------------------

#: Die Arten, wie ein Schritt gefahren wird. ``stimmen`` ist der Normalfall
#: (Stimme -> Zug -> Erkenner, bis der Zielzustand steht); die anderen haben
#: einen eigenen Ablauf in ``lauf.py``, weil sie mehr tun als reden.
ARTEN = ("stimmen", "interviews", "szene", "befehl", "zitate")


@dataclass(frozen=True)
class Schritt:
    """Ein Schritt des Skripts."""

    schluessel: str
    titel: str
    #: Was die Stimmen wollen. ``{...}``-Platzhalter werden in
    #: ``ziel_text`` aus dem Laufkontext gefuellt.
    ziel: str
    #: Woran der Lauf merkt, dass der Schritt durch ist.
    fertig: Callable[..., bool]
    art: str = "stimmen"
    max_nachrichten: int = MAX_NACHRICHTEN
    #: Nur fuer ``art='befehl'``: der Befehl, den die Gruppe tippt.
    befehl: str = ""
    #: Nur fuer ``art='szene'``: welche Szene dieser Schritt schreiben laesst,
    #: und in welcher Form. Die Form geht in den Auftrag an den Bot und in die
    #: Frage an den Richter ("Form eingehalten?").
    szene_nummer: int = 1
    form: str = ""
    #: Nur fuer ``art='interviews'``: in wie viele Textimporte jedes Interview
    #: zerlegt wird. 0 heisst "wie bisher": eines zufaellig gewaehlte in zwei,
    #: der Rest in einem.
    teile: int = 0
    #: Nur fuer ``art='interviews'``: ob mittendrin eine Frage an den Bot
    #: gestellt wird ("was war nochmal die zweite Frage").
    mit_frage: bool = True

    def ziel_text(self, merker: dict) -> str:
        return self.ziel.format(**merker)


def _fertig_begriffe(conn, chat_id, merker):
    return _stand_gesetzt(conn, chat_id, "begriffe")


def _fertig_fragen(conn, chat_id, merker):
    return _stand_gesetzt(conn, chat_id, "fragen")


def _fertig_interviews(conn, chat_id, merker):
    return len(repo.verdichtungen(conn, chat_id)) >= merker["interviews_soll"]


def _fertig_kernthema(conn, chat_id, merker):
    return _stand_gesetzt(conn, chat_id, "kernthema")


def _fertig_figuren(conn, chat_id, merker):
    return len(repo.figuren(conn, chat_id)) >= FIGUREN_SOLL


def _fertig_phase_mitte(conn, chat_id, merker):
    """Das Pflichtfeld der Phase 5 -- heute ``format`` -- oder, wenn das
    Schema keines hergibt, dass die Gruppe ueberhaupt dort angekommen ist.

    Nicht **alle** Felder der Phase: ``rahmen`` darf leer bleiben, und ein
    Schritt, der daran scheitert, wuerde einen Bot als taub melden, der genau
    das getan hat, was die Phase verlangt."""
    feld = pflichtfeld_fuer_phase(conn, PHASE_MITTE)
    if not feld:
        return phasen.aktuelle(conn, chat_id) >= PHASE_MITTE
    return _stand_gesetzt(conn, chat_id, feld)


def _fertig_szene(conn, chat_id, merker):
    return any(s["volltext"] for s in repo.hole_szenen(conn, chat_id))


def _fertig_szene_nummer(nummer: int):
    """Zielzustand fuer einen Szenen-Schritt, der eine **bestimmte** Szene
    schreiben laesst.

    Bei drei Szenen hintereinander (``--set birk``) genuegt "irgendeine Szene
    hat einen Volltext" nicht: nach Szene 1 waere jeder weitere Schritt sofort
    fertig, und die Szenen 2 und 3 entstuenden nie."""
    def fertig(conn, chat_id, merker):
        return any(
            s["nummer"] == nummer and s["volltext"]
            for s in repo.hole_szenen(conn, chat_id)
        )
    return fertig


def _fertig_korrektur(conn, chat_id, merker):
    """Eine Figur weniger als beim Betreten des Schritts.

    Die Transkriptkorrektur ('X heisst Y') laesst sich nicht so pruefen: ob
    es dafuer ueberhaupt eine Aenderungsart gibt, entscheidet der Erkenner
    und nicht der Simulator. Sie steht deshalb im Ziel der Stimmen, aber
    nicht im Zielzustand -- gemessen wird sie ueber den Richter."""
    return len(repo.figuren(conn, chat_id)) < merker.get("figuren_vorher", 0)


def _fertig_stand(conn, chat_id, merker):
    """``/stand`` ist durch, sobald der Bot geantwortet hat -- das prueft
    ``lauf.py`` an der Attrappe, nicht an der Datenbank."""
    return True


def _fertig_zitate(conn, chat_id, merker):
    """Die Zitatabfragen haben keinen Zielzustand in der Datenbank: sie
    aendern nichts, sie fragen ab. Ob der Bot richtig geantwortet hat, sagen
    der Richter und die Kennzahl ``zitat_erfunden`` -- nicht ein Feld."""
    return True


#: Die drei Fragen des Abfrage-Schritts, je eine Stimme. Sie sind bewusst
#: verschieden schwer: die erste laesst sich aus den Verdichtungen beantworten
#: (die stehen immer im Prompt), die zweite verlangt eine bestimmte Stelle,
#: die dritte den Volltext -- und der steht nur mit ``/wortlaut`` im Kontext.
#: Der Bericht sagt hinterher, was davon gereicht hat.
ZITAT_ZIELE = (
    "Du willst sehen, was der Bot sich aus einem Interview gemerkt hat: "
    "frag ihn, ob er dir alle Zitate aus dem zweiten Interview zeigt.",
    "Dich interessiert eine bestimmte Stelle: frag den Bot, was genau zu "
    "einem der Begriffe gesagt wurde -- woertlich, nicht zusammengefasst.",
    "Du willst den ganzen Text: bitte den Bot um das vollstaendige "
    "Transkript des ersten Interviews.",
)


#: Die neun Schritte in der Reihenfolge, in der sie gefahren werden.
SCHRITTE: tuple[Schritt, ...] = (
    Schritt(
        "begriffe",
        "Begriffe einwerfen",
        "Ihr habt im Plenum an der Wand Begriffe gesammelt und gebt sie dem "
        "Bot jetzt durch: {begriffe}. Sagt sie ihm, damit er sie sich merkt. "
        "Ihr wollt, dass er sie als eure Begriffsliste festhaelt.",
        _fertig_begriffe,
    ),
    Schritt(
        "fragen",
        "Fragen entwickeln",
        "Aus den Begriffen sollen Interviewfragen werden. Lasst den Bot "
        "welche vorschlagen, korrigiert eine davon (zu privat, zu allgemein, "
        "falsch verstanden) und stimmt dann ausdruecklich zu, damit er die "
        "Liste festhaelt. Ungefaehr in diese Richtung: {fragen}",
        _fertig_fragen,
    ),
    Schritt(
        "interviews",
        "Fuenf Interviews",
        "Ihr fuehrt jetzt die Interviews. Sagt dem Bot, dass ein Interview "
        "anfaengt, gebt ihm danach das Transkript und sagt am Ende, dass es "
        "fertig ist. Interview: {interview_name}.",
        _fertig_interviews,
        art="interviews",
    ),
    Schritt(
        "kernthema",
        "Kernthema",
        "Aus den Interviews soll ein Kernthema werden. Lasst den Bot eines "
        "vorschlagen, nehmt es an -- aber korrigiert es einmal, bevor ihr "
        "endgueltig zustimmt. Ihr wollt, dass am Ende genau ein Kernthema "
        "festgehalten ist.",
        _fertig_kernthema,
    ),
    Schritt(
        "figuren",
        "Figuren",
        "Ihr wollt drei Figuren fuer das Stueck, jede mit einem Namen und "
        "einem Satz dazu, wer sie ist. Nehmt Vorschlaege des Bots an oder "
        "macht eigene. Wenn der Bot anbietet, die Figuren den Interviews "
        "zuzuordnen, bestaetigt das.",
        _fertig_figuren,
    ),
    Schritt(
        "phase_mitte",
        "Phase 5",
        "Ihr seid jetzt bei '{phase_mitte}' und wollt festlegen, WORIN das "
        "Stueck spielt. Lasst euch vom Bot Rahmen vorschlagen (Ort, Zeit, "
        "Anlass) und stimmt einem davon zu, damit er ihn festhaelt.",
        _fertig_phase_mitte,
    ),
    Schritt(
        "szene",
        "Szene 1 planen und schreiben lassen",
        "Ihr plant die erste Szene: sagt, wo sie spielt (Ort), wer darin "
        "vorkommt und was darin passiert. Wenn das steht, lasst den Bot die "
        "Szene ausschreiben.",
        _fertig_szene,
        art="szene",
        max_nachrichten=4,
    ),
    Schritt(
        "zitate",
        "Zitatabfragen",
        "Ihr wollt wissen, was der Bot aus den Interviews woertlich hat.",
        _fertig_zitate,
        art="zitate",
        max_nachrichten=len(ZITAT_ZIELE),
    ),
    Schritt(
        "korrektur",
        "Korrektur und Entfernen",
        "Zwei Sachen: erstens stimmt ein Name im Interviewmaterial nicht -- "
        "sagt dem Bot, dass '{falscher_name}' in Wahrheit '{richtiger_name}' "
        "heisst. Zweitens soll eine der Figuren wieder weg: sagt ihm, dass "
        "die Figur '{figur_weg}' rausfliegt.",
        _fertig_korrektur,
    ),
    Schritt(
        "stand",
        "/stand",
        "Ihr wollt sehen, was der Bot sich gemerkt hat.",
        _fertig_stand,
        art="befehl",
        befehl="/stand",
        max_nachrichten=1,
    ),
)


def schritt_fuer(schluessel: str, schritte=SCHRITTE) -> Schritt:
    """Ein Schritt anhand seines Schluessels. Fehlt er, ist das ein
    Programmierfehler."""
    for schritt in schritte:
        if schritt.schluessel == schluessel:
            return schritt
    raise KeyError(schluessel)


def ohne_szene(schritte=SCHRITTE) -> tuple[Schritt, ...]:
    """Das Skript ohne die Szenen-Schritte (``--ohne-szene``).

    Ein Szenen-Schritt ist der einzige, der einen Reasoning-Lauf ausloest --
    zwei bis vier Minuten und ein Vielfaches der Kosten aller anderen
    Schritte zusammen. Wer nur den Gespraechsteil misst, laesst ihn weg."""
    return tuple(s for s in schritte if s.art != "szene")


# ---------------------------------------------------------------------------
# Das Skript von ``--set birk``
# ---------------------------------------------------------------------------

#: Die drei Formen, in denen die Szenen von ``--set birk`` geschrieben werden
#: sollen. Sie sind erfunden (Birk: "erfinde die fehlenden Angaben wie Form"),
#: aber sie sind das eigentliche Experiment dieses Sets: haelt der Bot eine
#: Formvorgabe durch, wenn sie nicht Dialog heisst?
FORMEN_BIRK = ("Dialog", "Lied", "Rap")

#: Das Format, auf das sich die Gruppe in Phase 5 festlegt.
RAHMEN_BIRK = "Ein Polizeikessel auf einer Demo, ein Abend"


def _fertig_ein_interview(conn, chat_id, merker):
    """Ein Interview, EINE Verdichtung -- auch wenn es in drei Textimporten
    hereinkam (§ 10.6). Genau das ist hier die Kennzahl."""
    return len(repo.verdichtungen(conn, chat_id)) >= 1


#: Das Skript von ``--set birk``: dasselbe Geruest, aber auf echten Daten und
#: mit einer einzigen Stimme. Gemessen wird die **Navigation**, nicht der
#: Text -- das Interview ist duenn (drei kurze Antworten), und ein Szenentext
#: daraus ist keine Aussage ueber Sprachqualitaet. Die Frage ist, wie
#: natuerlich der Bot durch die Phasen fuehrt, wenn eine echte Person so
#: knapp schreibt wie Birk am 04.09.
SCHRITTE_BIRK: tuple[Schritt, ...] = (
    Schritt(
        "begriffe",
        "Begriffe einwerfen",
        "Du gibst dem Bot die drei Begriffe durch, die im Plenum an der Wand "
        "stehen: {begriffe}. Du willst, dass er sie als Begriffsliste "
        "festhaelt.",
        _fertig_begriffe,
    ),
    Schritt(
        "fragen",
        "Fragen entwickeln",
        "Aus den Begriffen sollen Interviewfragen werden. Lass den Bot "
        "welche vorschlagen und korrigier eine davon, wenn sie nicht passt "
        "-- dann stimm zu, damit er die Liste festhaelt. Ungefaehr diese drei "
        "willst du am Ende haben:\n{fragen}",
        _fertig_fragen,
    ),
    Schritt(
        "interviews",
        "Ein Interview in drei Teilen",
        "Du fuehrst jetzt das Interview: sag dem Bot, dass eins anfaengt, gib "
        "ihm danach die Antworten und sag am Ende, dass du fertig bist. Es "
        "ist EIN Interview mit drei Antworten, kein drittes und viertes.",
        _fertig_ein_interview,
        art="interviews",
        teile=3,
        mit_frage=False,
    ),
    Schritt(
        "kernthema",
        "Kernthema",
        "Aus dem Interview soll ein Kernthema werden. Lass den Bot eines "
        "vorschlagen und nimm es an -- praezisier es einmal, wenn es dir zu "
        "eng ist. Am Ende soll genau ein Kernthema festgehalten sein.",
        _fertig_kernthema,
    ),
    Schritt(
        "figuren",
        "Drei Figuren mit Namen",
        "Du willst drei Figuren, jede mit einem Namen und einem Satz dazu, "
        "wer sie ist. Lass den Bot Namen vorschlagen und nimm sie an. Wenn "
        "er selbst keine anbietet, nenn ihm Mira, Pola und Pal.",
        _fertig_figuren,
    ),
    Schritt(
        "phase_mitte",
        "Phase 5: Rahmen",
        "Ihr seid jetzt bei '{phase_mitte}'. Du hast dich fuer einen Rahmen "
        f"entschieden: {RAHMEN_BIRK}. Sag es dem Bot und stimm zu, damit er "
        "ihn festhaelt.",
        _fertig_phase_mitte,
    ),
    Schritt(
        "zitate",
        "Zitatabfragen",
        "Du willst wissen, was der Bot aus dem Interview woertlich hat.",
        _fertig_zitate,
        art="zitate",
        max_nachrichten=len(ZITAT_ZIELE),
    ),
    Schritt(
        "szene1",
        "Szene 1: der Kessel (Dialog)",
        "Du planst Szene 1: Polizeikessel auf einer Palaestina-Demo, alle "
        "drei Figuren sind darin. Eine wirft Trumps 'Riviera fuer Gaza' ein, "
        "'nur halt ohne Vertreibung'; eine andere zerreisst das, daraus wird "
        "ein Streit. Form: Dialog. Wenn das steht, lass den Bot die Szene "
        "ausschreiben.",
        _fertig_szene_nummer(1),
        art="szene",
        szene_nummer=1,
        form="Dialog",
        max_nachrichten=4,
    ),
    Schritt(
        "szene2",
        "Szene 2: die Kueche (Lied)",
        "Du planst Szene 2: die Kueche der dritten Figur, direkt nach der "
        "Demo. Es gibt Pfannkuchen mit Schokolade und Banane. Die erste Figur "
        "legt sich mit den Pfannkuchen an, die zweite beobachtet nur. Form: "
        "Lied -- die Figur singt beim Backen, die anderen fallen ein. Wenn "
        "das steht, lass den Bot die Szene ausschreiben.",
        _fertig_szene_nummer(2),
        art="szene",
        szene_nummer=2,
        form="Lied",
        max_nachrichten=4,
    ),
    Schritt(
        "szene3",
        "Szene 3: das Zentrum (Rap)",
        "Du planst Szene 3: nachts, das autonome Zentrum. Eine Figur allein "
        "oder zu zweit, es wird gepogt und getanzt. Hawaii kommt vor -- als "
        "Bild, das nicht ihres ist. Form: Rap. Wenn das steht, lass den Bot "
        "die Szene ausschreiben.",
        _fertig_szene_nummer(3),
        art="szene",
        szene_nummer=3,
        form="Rap",
        max_nachrichten=4,
    ),
    Schritt(
        "stand",
        "/stand",
        "Du willst sehen, was der Bot sich gemerkt hat.",
        _fertig_stand,
        art="befehl",
        befehl="/stand",
        max_nachrichten=1,
    ),
)

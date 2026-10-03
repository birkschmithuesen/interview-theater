"""Der Ablauf, den die simulierten Teilnehmerinnen *wollen*.

Je Schritt ein **Ziel** (was die Stimmen anstreben, nicht was sie woertlich
sagen) und ein **Zielzustand in der Datenbank** (woran der Lauf merkt, dass
der Schritt durch ist). Ist der Zielzustand nach ``MAX_NACHRICHTEN``
Stimm-Nachrichten nicht erreicht, gilt der Schritt als **gescheitert**, wird
so vermerkt, und der Lauf geht trotzdem weiter -- ein Workshop bleibt auch
nicht stehen, weil der Bot etwas nicht mitbekommen hat.

**Drei Skriptlisten, keine ist die eine.** ``SCHRITTE`` ist die Messlatte der
Laeufe vom 05.09.2026 und bleibt deshalb unveraendert -- sie steuert die
Phasen NICHT an (kein ``art='phase'``-Schritt) und kennt eine Station
'Kernthema', die es seit dem 06.09. nicht mehr gibt. ``SCHRITTE_TAG2`` ist
das Skript der heutigen **sieben** Phasen aus ``phasen.PHASEN``.
``SCHRITTE_BIRK`` faehrt echtes Material. ``SCHRITTE_PADUA`` faehrt die
Phasen 5 bis 7 im neuen Padua-Ablauf (Erstentwurf, Ueberarbeitung,
Buehnenfassung). Welche gefahren wird, entscheidet
``scripts.simulation._schritte`` (Schalter ``--skript``).

**Datengetrieben, nicht hart codiert.** Die Phasen kommen aus
``phasen.PHASEN``, die Arbeitsstandfelder aus ``PRAGMA
table_info(arbeitsstand)``. Welches Feld zu einer Phase gehoert, wird aus
ihrem Kurznamen abgeleitet (``felder_fuer_phase``): heisst Phase 4 seit dem
06.09.2026 'Setting, Figuren & Geschichte', ist es ``geschichte``; hiesse sie
wieder 'Hauptkonflikt', waere es die Spalte ``hauptkonflikt``. Findet sich gar
keine Spalte, faellt die Pruefung auf 'die Gruppe steht in dieser Phase'
zurueck -- lieber eine schwaechere Aussage als eine falsche.

**Pflicht ist das erste Feld** (``pflichtfeld_fuer_phase``). Ein Kurzname
nennt zuerst die Entscheidung, die die naechste Phase traegt: bei 'Setting,
Figuren & Geschichte' ist das ``geschichte`` -- ohne sie gibt es keine
Szenenfolge --, waehrend ``rahmen`` fuer sich genommen leer bleiben darf.
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

#: Drei sachliche Festlegungen, die in **kein** Arbeitsstandfeld passen -- die
#: drei schwersten Verluste der Gruppe 1 vom 06.09.2026 als Pruefsaetze
#: (``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 0: die vierteilige
#: Handlungsstruktur, die Gruppenzuordnung, die Laengen-/Strukturvorgabe).
#:
#: Je Probe ``(bereich, stichwort, satz)``. Der ``satz`` geht ins Ziel des
#: Schritts ``festlegungen`` -- die Stimmen sollen ihn sagen; das
#: ``stichwort`` ist, wonach ``kennzahlen.festlegungslage`` danach in allen
#: dauerhaften Feldern sucht. Der ``bereich`` muss ein
#: ``repo.FESTLEGUNG_BEREICHE`` sein, sonst wandert die Zeile auf
#: 'sonstiges' und die Bereichsspalte im Bericht sagt nichts.
#:
#: Bewusst drei und nicht zehn: jede Probe kostet die Gruppe Nachrichten, und
#: ein Schritt, der zehn Saetze verlangt, misst die Geduld des Simulators und
#: nicht das Gedaechtnis des Bots.
FESTLEGUNGSPROBEN: tuple[tuple[str, str, str], ...] = (
    ("struktur", "erste Folge einer Serie",
     "Das Stueck ist nur eine Szene -- die erste Folge einer Serie."),
    ("gruppe", "Outsider",
     "Die Figuren gehoeren zu zwei Gruppen: den Coolen und den Outsider."),
    ("stil", "hoechstens eine Seite",
     "Jeder Szenentext soll hoechstens eine Seite lang sein."),
)


def festlegungsproben_text(proben=None) -> str:
    """Die Pruefsaetze als Aufzaehlung fuer das Ziel eines Schritts.

    Eine Funktion und keine Konstante, damit ein Aufrufer eigene Proben
    einsetzen kann (die Tests tun das) und die Formatierung trotzdem an einer
    Stelle steht."""
    return "\n".join(f"- {satz}" for _b, _s, satz in
                     (FESTLEGUNGSPROBEN if proben is None else proben))

#: Die Phase, deren Feld(er) Schritt 6 fuellt. Bewusst die **Nummer** und
#: nicht der Name: wie sie heisst, liest der Schritt zur Laufzeit aus
#: ``phasen.PHASEN``.
PHASE_MITTE = 4

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
    bei 'Setting, Figuren & Geschichte' ist das ``geschichte`` (ohne
    Geschichte gibt es keine Szenenfolge), waehrend ``rahmen`` fuer sich
    genommen leer bleiben darf -- dieselbe Gewichtung wie in
    ``phasen.voraussetzungen`` fuer den Schritt von 4 nach 5. Bei einem
    einwortigen Kurznamen
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
ARTEN = ("stimmen", "interviews", "szene", "befehl", "zitate", "phase")


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
    #: Nur fuer ``art='phase'``: in welche Phase gewechselt werden soll. Der
    #: Lauf drueckt dafuer zuerst den proaktiv angebotenen Knopf \"Weiter zu
    #: ...\" und faellt nur zurueck auf ``/phase N``, wenn keiner dasteht --
    #: die Kennzahl ``phasenwechsel_proaktiv`` haengt genau an diesem
    #: Unterschied.
    phase_nummer: int = 0
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
    """Das Pflichtfeld der Phase 4 -- heute ``geschichte`` -- oder, wenn das
    Schema keines hergibt, dass die Gruppe ueberhaupt dort angekommen ist.

    Nicht **alle** Felder der Phase: ``rahmen`` darf leer bleiben, und ein
    Schritt, der daran scheitert, wuerde einen Bot als taub melden, der genau
    das getan hat, was die Phase verlangt."""
    feld = pflichtfeld_fuer_phase(conn, PHASE_MITTE)
    if not feld:
        return phasen.aktuelle(conn, chat_id) >= PHASE_MITTE
    return _stand_gesetzt(conn, chat_id, feld)


def _geschrieben(szene) -> bool:
    """Steht diese Szene? In Phase 6 als Geschichte (``prosa``), ab Phase 7
    als Theatertext (``volltext``) -- 06.09.2026, 10:30."""
    try:
        if szene["prosa"]:
            return True
    except (IndexError, KeyError):
        pass
    return bool(szene["volltext"])


def _fertig_szene(conn, chat_id, merker):
    return any(_geschrieben(s) for s in repo.hole_szenen(conn, chat_id))


def _fertig_szene_nummer(nummer: int):
    """Zielzustand fuer einen Szenen-Schritt, der eine **bestimmte** Szene
    schreiben laesst.

    Bei drei Szenen hintereinander (``--set birk``) genuegt "irgendeine Szene
    hat einen Volltext" nicht: nach Szene 1 waere jeder weitere Schritt sofort
    fertig, und die Szenen 2 und 3 entstuenden nie."""
    def fertig(conn, chat_id, merker):
        return any(
            s["nummer"] == nummer and _geschrieben(s)
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


#: Die Schritte in der Reihenfolge, in der sie gefahren werden. **Nicht
#: anfassen** -- diese Liste ist die Messlatte der Laeufe vom 05.09.2026, und
#: der Vergleich ueber ``verlauf.jsonl`` ist der einzige Grund, aus dem die
#: Datei im Repository liegt. Fuer die heutigen Phasen: ``SCHRITTE_TAG2``.
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
        f"Phase {PHASE_MITTE}",
        "Ihr seid jetzt bei '{phase_mitte}' und wollt die Geschichte im "
        "Groben festlegen: was passiert, wie es endet, in welchen Szenen. "
        "Lasst euch vom Bot einen Vorschlag machen und stimmt ihm zu, damit "
        "er ihn festhaelt.",
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
        "Phase 4: Geschichte",
        "Ihr seid jetzt bei '{phase_mitte}'. Du weisst, worin es spielt "
        f"({RAHMEN_BIRK}) -- jetzt sag dem Bot, was passieren und wie es "
        "enden soll, und stimm seinem Vorschlag zu, damit er ihn festhaelt.",
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


# ---------------------------------------------------------------------------
# Das Skript der sieben Phasen -- ``--skript tag2`` und alle ``--set tag1-*``
# ---------------------------------------------------------------------------
#
# Warum ein zweites Skript und nicht ein umgebautes erstes: ``SCHRITTE`` und
# ``SCHRITTE_BIRK`` sind die Messlatte der vier Laeufe vom 05.09. Ein Umbau an
# ihnen macht die alten Verlaufszeilen unvergleichbar -- und der Vergleich
# ueber die Laeufe hinweg ist der einzige Grund, aus dem ``verlauf.jsonl``
# ueberhaupt im Repository liegt. Das neue Skript steht daneben.
#
# Der Ablauf folgt den Phasen aus ``phasen.PHASEN``. Die Phasennummern stehen
# als Konstanten, nicht als Zahlen im Text: eine achte Phase soll dieses
# Skript nicht mitreissen.

PHASE_BEGRIFFE = 1
PHASE_FRAGEN = 2
PHASE_INTERVIEWS = 3
#: Setting, Figuren UND Geschichte sind seit dem 06.09.2026 eine Station.
PHASE_SETTING = 4
PHASE_GESCHICHTE = PHASE_SETTING
PHASE_SCHAERFUNG = 5
#: Phase 6 heisst seit dem 06.09.2026 abends "Szenen als Geschichte" (Prosa),
#: Phase 7 "Feinschliff" (Form je Szene, Uebersetzung, Stueckpruefung). Die
#: alten Namen nach den Stationen "Szenentexte" und "Durchlauf" (Stand
#: 05.09.) sind weg, damit niemand aus dem Namen auf die falsche Station
#: schliesst.
PHASE_PROSA = 6
PHASE_FEINSCHLIFF = 7


def _fertig_eroeffnung(conn, chat_id, merker):
    """Phase 2 ist erst durch, wenn NEBEN den Fragen auch der
    Eroeffnungstext steht.

    Dieselbe Bedingung wie ``phasen.voraussetzungen[3]`` (06.09.2026): ohne
    Eroeffnung geht keine Sechzehnjaehrige auf eine fremde Person zu, und ein
    Schritt, der schon bei gesetzten ``fragen`` fertig waere, uebersaehe
    genau den Teil, der neu ist."""
    return (
        _stand_gesetzt(conn, chat_id, "fragen")
        and _stand_gesetzt(conn, chat_id, "interview_eroeffnung")
    )


def _fertig_setting(conn, chat_id, merker):
    """Phase 4: Setting (``rahmen``) UND eine fixierte Figurenliste --
    zwei der Dinge, die ``phasen.voraussetzungen[5]`` verlangt (die
    Geschichte kommt im naechsten Schritt derselben Station dazu)."""
    return (
        _stand_gesetzt(conn, chat_id, "rahmen")
        and _stand_gesetzt(conn, chat_id, "figuren_fixiert_am")
        and bool(repo.figuren(conn, chat_id))
    )


def _fertig_festlegungen(conn, chat_id, merker):
    """Alle Pruefsaetze liegen **dauerhaft** -- in einem Arbeitsstandfeld, an
    einer Figur, an einer Szene oder in der Auffangtabelle ``festlegung``.

    Das Journal zaehlt nicht mit: es wird in ``kontext._baue_journal`` auf acht
    Zeilen gekappt, und ein verdraengter Eintrag kommt nie zurueck -- genau der
    Verlust aus ``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 2.7.

    Der Import steht in der Funktion, weil ``kennzahlen`` dieses Modul auf
    Modulebene importiert; oben waere das ein Zyklus. Dieselbe Bauart wie
    ueberall im Repo."""
    from simulation import kennzahlen

    lage = kennzahlen.festlegungslage(conn, chat_id)
    return lage["festlegungsproben_erhalten"] == lage["festlegungsproben"]


def _fertig_geschichte(conn, chat_id, merker):
    """Phase 4, zweiter Teil: die Geschichte steht und mindestens eine Szene
    ist geplant. Kein eigener Phasenschritt mehr davor -- der Bot leitet nach
    der Figurenliste innerhalb derselben Station weiter (06.09.2026)."""
    return (
        _stand_gesetzt(conn, chat_id, "geschichte")
        and bool(repo.hole_szenen(conn, chat_id))
    )


def _fertig_schaerfung(conn, chat_id, merker):
    """Die Schaerfung ist ein **Angebot**, keine Pflicht
    (``phasen.voraussetzungen`` sperrt die Szenentexte nicht daran). Fertig ist der Schritt deshalb, sobald die Gruppe
    in Phase 6 war -- ob sie eine Runde uebernommen hat, misst die Kennzahl
    ``schaerfungen``, nicht der Zielzustand."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_SCHAERFUNG


def _in_phase(nummer: int):
    """Zielzustand eines ``art='phase'``-Schritts: die Gruppe steht dort."""
    def fertig(conn, chat_id, merker):
        return phasen.aktuelle(conn, chat_id) >= nummer
    return fertig


def _phasenschritt(nummer: int) -> Schritt:
    """Ein Schritt, der nur die Phase wechselt.

    Eigene Schritte und nicht ein Satz im Ziel des naechsten: der Wechsel ist
    seit dem 06.09.2026 der Moment, an dem der Bot **von sich aus** fragt
    (``knoepfe.biete_phase_proaktiv``), und ob er das tut, ist eine der
    Kennzahlen dieses Umbaus. Ein Schritt, der im Vorbeigehen mitwechselt,
    haette sie verschluckt."""
    return Schritt(
        f"phase{nummer}",
        f"Weiter zu Phase {nummer}: {phasen.kurzname(nummer)}",
        f"Ihr seid mit dem Vorigen durch und wollt weiter zu "
        f"'{phasen.kurzname(nummer)}'.",
        _in_phase(nummer),
        art="phase",
        phase_nummer=nummer,
        max_nachrichten=2,
    )


#: Das Skript der sieben Phasen. Die Interviews kommen aus den erfundenen Sets
#: (``simulation/interviews/``), nie aus echtem Material -- die Stimmen sind
#: aus Tag 1 abgeleitet, die Transkripte bleiben erfunden.
SCHRITTE_TAG2: tuple[Schritt, ...] = (
    Schritt(
        "begriffe",
        "Phase 1: Begriffe uebergeben",
        "Ihr habt im Plenum an der Wand Begriffe gesammelt und gebt sie dem "
        "Bot jetzt durch: {begriffe}. Ihr wollt, dass er sie als eure "
        "Begriffsliste festhaelt -- beim ERSTEN Mal, ohne Rueckfrage.",
        _fertig_begriffe,
    ),
    _phasenschritt(PHASE_FRAGEN),
    Schritt(
        "fragen",
        "Phase 2: aus zehn Fragen drei waehlen",
        "Ihr wollt Interviewfragen. Lasst euch zehn vorschlagen, tippt genau "
        "drei davon an und uebernehmt sie. Danach kommen Einleitungen zu "
        "heiklen Fragen und eine Eroeffnung fuer das Gespraech -- nehmt beides "
        "an oder aendert eine Kleinigkeit. Ihr wollt am Ende einen Leitfaden "
        "haben. Ungefaehr in diese Richtung: {fragen}",
        _fertig_eroeffnung,
        max_nachrichten=10,
    ),
    _phasenschritt(PHASE_INTERVIEWS),
    Schritt(
        "interviews",
        "Phase 3: Interviews fuehren und auswerten",
        "Ihr fuehrt jetzt die Interviews. Startet das Interview, gebt dem Bot "
        "danach die Aufnahme und beendet es, wenn ihr durch seid. "
        "Interview: {interview_name}.",
        _fertig_interviews,
        art="interviews",
    ),
    _phasenschritt(PHASE_SETTING),
    Schritt(
        "setting",
        "Phase 4: Setting und Figuren frei erfinden",
        "Jetzt wird ERFUNDEN, nicht aus den Interviews abgeleitet. Legt fest, "
        "worin das Stueck spielt (Ort, Zeit, Anlass) und welche Figuren es "
        "gibt -- sagt zuerst, wie viele, dann die Namen. Nehmt Vorschlaege an "
        "oder macht eigene, und bestaetigt die Liste am Ende.",
        _fertig_setting,
        max_nachrichten=10,
    ),
    Schritt(
        "festlegungen",
        "Phase 4: was in kein Feld passt (dieselbe Station)",
        "Ihr legt jetzt drei Sachen fest, die in keinen der Bot-Kaesten "
        "passen. Sagt sie ihm in eigenen Worten, eine nach der anderen, und "
        "vergewissert euch, dass er sie festgehalten hat:\n"
        "{festlegungsproben}",
        _fertig_festlegungen,
        max_nachrichten=6,
    ),
    Schritt(
        "geschichte",
        "Phase 4: die Geschichte im Groben (dieselbe Station)",
        "Was passiert, wie endet es, in welchen Szenen? Lasst euch einen "
        "Vorschlag machen, aendert eine Sache daran und nehmt ihn dann an. "
        "Ihr wollt am Ende eine Geschichte und eine Szenenfolge haben.",
        _fertig_geschichte,
        max_nachrichten=8,
    ),
    _phasenschritt(PHASE_SCHAERFUNG),
    Schritt(
        "schaerfung",
        "Phase 5: am Material schaerfen",
        "Jetzt kommt das Interviewmaterial dazu und legt sich NEBEN das "
        "Erfundene. Schaut euch an, was der Bot je Szene und je Figur "
        "vorschlaegt, und uebernehmt, was passt.",
        _fertig_schaerfung,
        max_nachrichten=6,
    ),
    _phasenschritt(PHASE_PROSA),
    Schritt(
        "szene1",
        "Phase 6: Szene 1 -- Form bestaetigen, dann schreiben",
        "Ihr wollt Szene 1 geschrieben haben. Der Bot fragt euch zuerst nach "
        "der FORM -- bestaetigt sie (oder waehlt eine andere) -- und danach, "
        "ob er schreiben soll. Sagt ja. Wenn der Text da ist, sagt, ob er "
        "passt oder neu geschrieben werden soll.",
        _fertig_szene_nummer(1),
        art="szene",
        szene_nummer=1,
        max_nachrichten=6,
    ),
    Schritt(
        "zitate",
        "Zitatabfragen",
        "Ihr wollt wissen, was der Bot aus den Interviews woertlich hat.",
        _fertig_zitate,
        art="zitate",
        max_nachrichten=len(ZITAT_ZIELE),
    ),
    _phasenschritt(PHASE_FEINSCHLIFF),
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


# ---------------------------------------------------------------------------
# Das Padua-Skript -- ``--skript padua`` (Padua Phasen TEIL 2, Task 14)
# ---------------------------------------------------------------------------
#
# Bis zur Geschichte (Phase 4) dasselbe wie ``SCHRITTE_TAG2``; danach der
# neue Ablauf: Phase 5 ist der Erstentwurf (Uebersicht, dann Szene fuer
# Szene im Script-Tab), Phase 6 die Ueberarbeitung (erst das Ganze, dann je
# Szene), Phase 7 die Buehnenfassung (Formen, Sprechweisen, je Szene, die
# Stueckpruefung). Der Ablauf greift nur mit ``IT_WORKSHOP=padua-2026``
# (``workshop.ueberarbeitung_aktiv``) -- das Profil kommt aus der Umgebung,
# nicht aus diesem Schalter.
#
# Die Phasenschritte 6 und 7 stehen als Marken da: im neuen Ablauf wechselt
# die Phase von selbst (das Abnehmen der letzten Szene schaltet weiter), ihr
# Zielzustand ist also meist schon erreicht und sie kosten keine Nachricht.
# Ohne sie ordnete der Abdeckungszensus (``phase_je_schritt``) alles ab dem
# Entwurf der Phase 5 zu; und bleibt ein Wechsel aus, greift derselbe
# Notweg wie in ``SCHRITTE_TAG2`` -- als Befund ``phasenwechsel_selbst``.


def _fertig_entwurf(conn, chat_id, merker):
    """Phase 5 ist durch, wenn die Gruppe in Phase 6 steht -- das Abnehmen
    der letzten Entwurfsszene schaltet selbst weiter."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_PROSA


def _fertig_gesamt6(conn, chat_id, merker):
    """Phase 6, erster Teil: der Gesamttext ist fixiert."""
    from interview_theater import ueberarbeitung

    return ueberarbeitung.gesamttext_fixiert(conn, chat_id)


def _fertig_szenen6(conn, chat_id, merker):
    """Phase 6, zweiter Teil: jede Szene abgenommen -- die letzte schaltet
    in Phase 7 weiter."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_FEINSCHLIFF


def _fertig_formen7(conn, chat_id, merker):
    """Jede Szene hat eine bestaetigte ``form``. Ohne Szenen nie fertig --
    sonst waere der Schritt bei einem leeren Stueck still durch."""
    from interview_theater import ueberarbeitung

    return (bool(ueberarbeitung.szenennummern(conn, chat_id))
            and not ueberarbeitung.formen_offen(conn, chat_id))


def _fertig_sprechweisen7(conn, chat_id, merker):
    """Die Sprechweisen der Figuren sind fixiert."""
    from interview_theater import ueberarbeitung

    return ueberarbeitung.sprechweisen_fixiert(conn, chat_id)


def _fertig_buehne7(conn, chat_id, merker):
    """Jede Szene traegt ``fertig_am`` (Buehnenfassung abgenommen)."""
    szenen = [s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] is not None]
    return bool(szenen) and all(s["fertig_am"] for s in szenen)


def _fertig_pruefung7(conn, chat_id, merker):
    """Die Stueckpruefung hat mindestens eine Runde geschrieben."""
    return repo.letzte_pruefrunde(conn, chat_id) >= 1


def _bis_zur_geschichte() -> tuple[Schritt, ...]:
    schluessel = [s.schluessel for s in SCHRITTE_TAG2]
    return SCHRITTE_TAG2[: schluessel.index("geschichte") + 1]


#: Das Skript des Padua-Ablaufs: Phasen 1-4 wie ``SCHRITTE_TAG2``, danach
#: Erstentwurf, Ueberarbeitung und Buehnenfassung. Kein bezahlter Lauf in
#: der Testsuite -- der Befehl dafuer steht in ``simulation/README.md``.
SCHRITTE_PADUA: tuple[Schritt, ...] = _bis_zur_geschichte() + (
    _phasenschritt(PHASE_SCHAERFUNG),
    Schritt(
        "entwurf",
        "Phase 5: Uebersicht und Erstentwurf Szene fuer Szene",
        "Lest die Uebersicht und sagt 'Yes, save'. Danach kommt Szene fuer "
        "Szene -- lest sie im Script-Tab und drueckt jeweils 'Yes, save'.",
        _fertig_entwurf,
        max_nachrichten=12,
    ),
    _phasenschritt(PHASE_PROSA),
    Schritt(
        "gesamt6",
        "Phase 6: die ganze Geschichte ueberarbeiten",
        "Die ganze Geschichte steht im Script-Tab. Sagt in einem Satz, wohin "
        "sie gehen soll (z. B. 'make it darker'), dann 'Yes, save'.",
        _fertig_gesamt6,
    ),
    Schritt(
        "szenen6",
        "Phase 6: Szene fuer Szene ueberarbeiten",
        "Geht Szene fuer Szene durch: bei Szene 1 sagt ihr eine Aenderung, "
        "danach jeweils 'Yes, save'.",
        _fertig_szenen6,
        max_nachrichten=12,
    ),
    _phasenschritt(PHASE_FEINSCHLIFF),
    Schritt(
        "formen7",
        "Phase 7: eine Form je Szene",
        "Antwortet auf 'Which form for each number?' in einer Nachricht, "
        "z. B. '1 chorus, 2 dialogue'.",
        _fertig_formen7,
    ),
    Schritt(
        "sprechweisen7",
        "Phase 7: wie jede Figur spricht",
        "Ihr seht, wie jede Figur spricht. Aendert eine Figur per Chat, dann "
        "'Yes, save'.",
        _fertig_sprechweisen7,
    ),
    Schritt(
        "buehne7",
        "Phase 7: Buehnenfassung Szene fuer Szene",
        "Szene fuer Szene: bei Szene 1 sagt 'make the mother angrier' (oder "
        "eine passende Figur), danach jeweils 'Yes, save'.",
        _fertig_buehne7,
        max_nachrichten=14,
    ),
    Schritt(
        "pruefung7",
        "Phase 7: Stueckpruefung abwarten",
        "Wartet die Stueckpruefung ab.",
        _fertig_pruefung7,
    ),
    SCHRITTE_TAG2[-1],
)

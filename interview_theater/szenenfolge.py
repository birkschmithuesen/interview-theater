"""Die Szenenfolge und die Szenenplanung als Knopf-Navigation (Phase 6 Szenentexte).

**Warum es dieses Modul gibt.** Die Szenentexte-Phase ist die laengste Strecke des
Workshops: erst eine Folge von vier bis sechs Szenen, dann Szene fuer Szene
die Planung, dann je Szene ein Text. Bis zum 05.09.2026 lief das ganz im
Gespraech -- und genau dort verlor der Bot die Entscheidungen, die die Gruppe
schon getroffen hatte: eine zugestimmte Szenenfolge stand als Fliesstext im
Chat und nie in der Tabelle ``szene``, und die naechste Antwort schlug eine
andere Folge vor.

Der Weg ist derselbe wie bei den uebrigen Auswahl-Momenten (``knoepfe.py``):
der Bot legt einen **Vorschlag als Text** hin, mit einem Marker, den der Code
lesen kann (``vorschlag.py``), und darunter haengen Knoepfe, die den Vorschlag
**deterministisch** speichern. Was hier dazukommt, ist der Weg, einen neuen
Vorschlag anzustossen, ohne dass jemand etwas tippen muss -- \"Anzahl
aendern\" und \"Reihenfolge aendern\" brauchen eine neue Antwort des Modells.

**Kein Modellaufruf im Knopf-Handler** (AGENTS.md, Zusage 2 in
``knoepfe.py``): jede Funktion hier, die ein Modell fragt, gibt den Aufruf
sofort an einen eigenen Thread ab -- dasselbe Muster wie ``szene.starte``.
Die Sperre je ``chat_id`` liegt aus demselben Grund vor dem Thread und wird
im Thread freigegeben.
"""

from __future__ import annotations

import logging
import re
import threading

from interview_theater import anweisungen, repo

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "szenenfolge"

#: Art des zweiten, kleineren Aufrufs: die fehlenden Felder EINER Szene.
ART_FELDER = "szenenfelder"

#: Art des Geschichte-Aufrufs (Phase 4, Umbau 05.09.2026 nachts): Bogen, Ende
#: und Szenenfolge in EINEM Vorschlag -- und **ohne Material**.
ART_GESCHICHTE = "geschichte"

#: Ausgabebudget. Ein Vorschlag sind sechs Zeilen -- das Budget ist eine
#: Obergrenze gegen Durchdrehen, kein Zielwert (wie ``szene.MAX_TOKENS``).
#: ACHTUNG, AGENTS.md Falle 4: dieser Aufruf laeuft ueber ``klm.prosa`` und
#: damit mit AKTIVEM Reasoning. Reasoning verbraucht das Ausgabebudget VOR
#: dem eigentlichen Inhalt -- bei zu knappem Budget kommt HTTP 200 mit
#: leerem Inhalt und ``finish_reason: "length"`` zurueck, ein stiller
#: Durchfall. Live gemessen am 05.09.2026 abends (Test-Gruppe): mit 4000
#: Token endete jeder Lauf im Denken, die Gruppe sah nur "Die Szenenfolge
#: ist mir nicht gelungen". Deshalb wie in ``szene.py`` weit ueber der
#: Messung; was das Modell nicht braucht, kostet nichts.
MAX_TOKENS = 60_000

#: Zeitbudget des Aufrufs. Ebenfalls angehoben (vorher 120 s): ein
#: Reasoning-Lauf braucht laut ``reasoning-stufen-entscheidungshilfe.md``
#: § 4.4 mindestens 60 s, und ein Timeout spart hier nichts -- der Lauf
#: haengt in einem eigenen Thread, ein Abbruch ist trotzdem bezahlt.
TIMEOUT_S = 300.0

#: Wie viele Szenen vorgeschlagen werden, wenn niemand etwas anderes sagt.
ANZAHL_VORGABE = 5
#: Die Auswahl hinter \"Anzahl aendern\". Drei ist die Untergrenze, unter der
#: kein Abend entsteht; sechs die Obergrenze, die eine Workshopgruppe an einem
#: Wochenende ausschreiben kann.
ANZAHL_MOEGLICH = (3, 4, 5, 6)

#: Die Form, mit der eine Szene startet, wenn die Vorschlagszeile keine
#: nennt. Vorgabe, keine Festlegung: \"Form aendern\" haengt unter jeder
#: Szenenvorstellung. Seit dem 05.09.2026 abends nennt der Prompt die Form
#: je Zeile ausdruecklich (``ANWEISUNG_FOLGE``) -- der Rueckfall greift nur,
#: wenn das Modell die vierte Spalte weglaesst.
FORM_VORGABE = "dialog"

#: Trennt zwei Fassungen im Feld ``szene.fruehere_fassungen``.
FASSUNGSTRENNER = "\n\n----- fruehere Fassung -----\n\n"

#: Die Anweisung fuer den Vorschlags-Aufruf. Bewusst kurz und ausdruecklich
#: auf das Format bezogen: der Marker ist die einzige Stelle, an der der Code
#: den Vorschlag wiederfindet (``vorschlag.lies``), und ein Vorschlag ohne
#: Marker bekommt keine Knoepfe -- geraten wird nichts.
ANWEISUNG_FOLGE = """Du planst mit einer Theatergruppe die Szenenfolge ihres Stuecks.

Schlage genau {anzahl} Szenen vor. Antworte in GENAU dieser Form, ohne
Einleitung und ohne Nachwort:

VORSCHLAG SZENENFOLGE:
Titel — ein Satz, was passiert — Figur, Figur — Form
Titel — ein Satz, was passiert — Figur, Figur — Form

Eine Zeile je Szene, {anzahl} Zeilen. Nimm nur Figuren, die unten im
Arbeitsstand stehen. Denk in Situationen: Ort, Beteiligte, was sich aendert.
Eine Szene ohne Veraenderung ist ein Gespraech, kein Theater -- eine Szene
ohne Konflikt dagegen schon.

**Die Form ist Pflicht** und steht als vierte Spalte jeder Zeile. Es gibt
genau fuenf: Dialog, Monolog, Chor, Lied, Rap. Waehl sie nach dem Material,
nicht nach Gewohnheit -- **nicht jede Szene ist ein Dialog**. Wo ein Zitat
singt, steht ein Lied; wo eine Reihung klopft, ein Rap; wo eine allein
bleibt, ein Monolog; wo viele dasselbe sagen, ein Chor. Eine Folge aus lauter
Dialogen ist ein Fehler.

Danach ein Satz und eine offene Frage an die Gruppe, hoechstens zwei Zeilen."""

#: Die Anweisung fuer den Geschichte-Aufruf (Phase 4). Der Unterschied zur
#: Szenenfolge ist nicht die Form, sondern die Quelle: hier wird **erfunden**,
#: aus den Begriffen und Fragen der Gruppe und dem, was sie in Phase 4
#: festgelegt hat -- keine Interviews, keine Verdichtungen, keine Zitate. Das
#: Material kommt erst in Phase 5 dazu und schaerft, was hier entsteht.
ANWEISUNG_GESCHICHTE = """Du entwickelst mit einer Theatergruppe die Geschichte ihres Stuecks im Groben.

Die Gruppe hat Setting und Figuren selbst erfunden. Jetzt geht es um den
Bogen: was passiert, wie es endet, worum gestritten wird.

**Du schlaegst GENAU DREI RICHTUNGEN vor** (Birk, 06.09.2026 11:42) -- drei
verschiedene Moeglichkeiten, wie dieselbe Welt zu einer Geschichte wird. Je
Richtung ein kurzer, fetter Titel und danach zwei bis drei Saetze: der Bogen,
das Ende und der Kernkonflikt.

**KEINE Szenenfolge in diesem Schritt.** Keine Szenentitel, keine Formen,
keine Nummern -- die Szenen kommen erst, wenn die Gruppe sich fuer eine
Richtung entschieden hat und das Ende feststeht.

**Du erfindest hier frei** -- aus den Begriffen und Fragen der Gruppe, aus
dem Setting und den Figuren. Interviews, Verdichtungen und Zitate stehen dir
bewusst nicht zur Verfuegung; sie kommen erst in der naechsten Station dazu
und schaerfen, was ihr jetzt erfindet.

Antworte in GENAU dieser Form, ohne Einleitung und ohne Nachwort:

VORSCHLAG GESCHICHTE:
Titel der ersten Richtung — Bogen, Ende und Kernkonflikt in zwei bis drei Saetzen
Titel der zweiten Richtung — Bogen, Ende und Kernkonflikt in zwei bis drei Saetzen
Titel der dritten Richtung — Bogen, Ende und Kernkonflikt in zwei bis drei Saetzen

Genau drei Zeilen, je eine Richtung, Titel unter 25 Zeichen. Nimm nur
Figuren, die unten stehen.

Danach ein Satz und eine offene Frage an die Gruppe, hoechstens zwei Zeilen."""

#: Die Szenenfolge NACH der gewaehlten Richtung (06.09.2026, Birk 11:42):
#: erst wenn Bogen und Ende feststehen, wird daraus eine Folge von Szenen.
#: Ein eigener Vorschlag mit Ja/Nein, kein Anhaengsel der Richtungswahl.
ANWEISUNG_GESCHICHTE_SZENEN = """Du entwickelst mit einer Theatergruppe die Szenenfolge ihres Stuecks.

Die Gruppe hat sich fuer eine Richtung entschieden; Bogen und Ende stehen
unten. Daraus schlaegst du jetzt die Szenen vor.

Antworte in GENAU dieser Form, ohne Einleitung und ohne Nachwort:

VORSCHLAG SZENENFOLGE:
Titel — ein Satz, was passiert — Figur, Figur — Form — warum diese Form
Titel — ein Satz, was passiert — Figur, Figur — Form — warum diese Form

Nimm nur Figuren, die unten stehen.

**Die Form schlaegst du VOR, du entscheidest sie nicht.** Sie steht als
vierte Spalte, ihre Begruendung als fuenfte, und beide sind Pflicht -- die
Gruppe bestaetigt die Form spaeter Szene fuer Szene per Knopf.

Es gibt genau fuenf: Dialog, Monolog, Chor, Lied, Rap. **Dialog ist der
Normalfall.** Monolog, Lied und Rap nur, wenn die Szene es verlangt: eine
Figur allein mit sich, ein Gefuehl, das gesungen groesser wird, Wut, die
Rhythmus braucht. Hoechstens EINE Nicht-Dialog-Szene je drei Szenen, und
Szene 1 ist nie Monolog oder Lied -- die Exposition braucht Begegnung.

Danach ein Satz und eine offene Frage an die Gruppe, hoechstens zwei Zeilen."""

#: Dasselbe fuer die fehlenden Felder EINER Szene. Der Anlass (Birk,
#: 05.09.2026): \"Passt, schreiben\" lief bis dahin in den Sperrtext
#: (``szene.sperrtext``) -- eine Liste dessen, was fehlt, und die Gruppe
#: musste es abtippen. Vorschlagen statt abfragen: der Bot legt hin, was er
#: aus dem Material weiss, die Gruppe tippt einen Knopf.
ANWEISUNG_FELDER = """Du planst mit einer Theatergruppe eine einzelne Szene.

Fuer die Szene unten fehlen noch Angaben: {felder}.

Schlage sie vor -- aus dem Material, das unten steht, nicht frei erfunden.
Antworte in GENAU dieser Form, ohne Einleitung und ohne Nachwort:

VORSCHLAG SZENE:
feld: Wert
feld: Wert

Eine Zeile je Feld, nur die fehlenden Felder, die Feldnamen genau so wie in
der Aufzaehlung oben. Danach ein Satz und eine offene Frage an die Gruppe,
hoechstens zwei Zeilen."""


class SzenenfolgeFehler(Exception):
    """Der Vorschlags-Aufruf lieferte nichts Verwertbares."""


# Eine Sperre je chat_id, wie in ``szene.py`` und ``ablauf.py``: zwei
# gleichzeitige Vorschlaege derselben Gruppe waeren zwei Listen im Chat, und
# die Gruppe wuesste nicht, welche gilt.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


# ---------------------------------------------------------------------------
# Vorschlag lesen
# ---------------------------------------------------------------------------

#: Trennzeichen einer Szenenzeile: \"Titel — was passiert — Mira, Pal\".
#: Derselbe Satz Trenner wie ``vorschlag._FIGUR_TRENNER`` -- Modelle liefern
#: Gedankenstrich und einfachen Bindestrich gemischt.
_TRENNER = re.compile(r"\s+[—–]\s+|\s+-\s+")


def zerlege(wert: str) -> list[tuple[str, str, list[str], str, str]]:
    """Zerlegt den Szenenfolge-Block in ``(Titel, was_passiert, Figuren,
    Formvorschlag, Begruendung)``.

    Eine Zeile je Szene. Fuehrende Aufzaehlungszeichen (\"- \", \"1. \",
    \"Szene 1: \") fallen weg -- ein Modell nummeriert gern mit, und die
    Nummer vergibt der Code selbst. Zeilen ohne Titel fallen raus.

    Fehlt die dritte Spalte, bleibt die Figurenliste leer: eine Szene ohne
    Besetzung ist ein normaler Planungszustand (``szene.sperrtext`` sagt es
    spaeter), kein Grund, die ganze Zeile wegzuwerfen.

    Die **vierte Spalte ist der Formvorschlag** (05.09.2026 abends, Birk),
    die **fuenfte seine Begruendung** (06.09.2026, Birk: "Die Form Monolog
    habe ich niemals eingegeben und aktiv bestaetigt. Die Form muss mit mehr
    Bedacht gewaehlt werden und vom User bestaetigt werden."). Beides ist ein
    **Vorschlag**: gesetzt wird ``szene.form`` allein durch einen Knopfdruck
    der Gruppe, Szene fuer Szene (``knoepfe.biete_szenenform``). Fehlt die
    vierte Spalte, gilt ``FORM_VORGABE`` als Vorschlag -- Dialog ist der
    Normalfall. Uebersetzt wird ueber ``szene.formdatei``: was das Modell
    schreibt ("gesungen"), landet bei der Form, die es meint."""

    from interview_theater import szene as szene_modul

    ergebnis: list[tuple[str, str, list[str], str, str]] = []
    for zeile in (wert or "").splitlines():
        roh = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", zeile).strip()
        roh = re.sub(r"^\s*szene\s*\d{0,3}\s*[:.]\s*", "", roh, flags=re.IGNORECASE)
        if not roh:
            continue
        teile = [t.strip() for t in _TRENNER.split(roh)]
        titel = teile[0].strip(" .;:")
        if not titel:
            continue
        was = teile[1].strip() if len(teile) > 1 else ""
        figuren = []
        if len(teile) > 2:
            figuren = [f.strip(" .;:") for f in teile[2].split(",") if f.strip()]
        roh_form = teile[3].strip(" .;:") if len(teile) > 3 else ""
        form = szene_modul.formdatei(roh_form) if roh_form else FORM_VORGABE
        grund = teile[4].strip() if len(teile) > 4 else ""
        ergebnis.append((titel, was, figuren, form, grund))
    return ergebnis


def lege_an(
    conn, chat_id: int, zeilen: list[tuple[str, str, list[str], str, str]]
) -> list[int]:
    """Gleicht einen Szenenfolge-Vorschlag mit der bestehenden Folge ab und
    liefert die Nummern.

    **Abgleichend, nicht ersetzend** (06.09.2026, Analyse
    ``docs/analyse-phase5-chaos-2026-09-06.md`` Abschnitt B). Bis dahin stand
    hier das Gegenteil -- "eine neue Folge ist eine neue Folge" --, und genau
    das hat im Live-Fall Gruppe 1 drei geplante Szenen samt ihrer
    Formfestlegung weich entfernt, ohne dass jemand darum gebeten hatte. Seit
    diesem Umbau laeuft alles ueber ``repo.gleiche_szenenfolge_ab``: Szenen
    mit derselben Nummer werden **aktualisiert**, fehlende **ergaenzt**,
    ueberzaehlige **bleiben stehen**. Eine Szene verschwindet nur noch auf
    ausdruecklichen Wunsch (``repo.entferne_szene``, N3).

    Was dabei geschuetzt ist, steht in ``repo.GESCHUETZTE_SZENENFELDER``:
    ``form``/``form_vorschlag``/``stil`` (Entscheidungen der Gruppe) und
    ``volltext``/``prosa`` (geschriebene Texte) bleiben erhalten, solange sie
    gefuellt sind.

    Die Besetzung wird nur gesetzt, soweit die Namen im Arbeitsstand stehen --
    eine Figur wird hier NIE angelegt. Figuren entstehen in Phase 4 mit
    Beschreibung und Interview; sie aus einer Szenenzeile zu raten waere genau
    der Fehler, den ``vorschlag.py`` vermeidet. Eine bestehende Besetzung
    wird nicht geleert: nennt der Vorschlag keine bekannten Namen, bleibt sie
    stehen.

    **Die Form wird NICHT gesetzt** (Birk, 06.09.2026 00:30): sie landet als
    ``form_vorschlag`` samt Begruendung in der Szene, ``form`` bleibt leer,
    bis die Gruppe sie Szene fuer Szene per Knopf bestaetigt. Anlass: in einer
    fertigen Szene stand "Monolog", ohne dass es je jemand gewaehlt hatte."""
    from interview_theater import szene as szene_modul

    nach_name = {f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)}
    abgleich: list[dict] = []
    for zeile in zeilen:
        titel, was = zeile[0], zeile[1]
        # Der Formvorschlag kommt aus der vierten Spalte, seine Begruendung
        # aus der fuenften; aeltere Aufrufer mit kuerzeren Tupeln bekommen die
        # Vorgabe (Dialog).
        form = zeile[3] if len(zeile) > 3 and zeile[3] else FORM_VORGABE
        grund = zeile[4] if len(zeile) > 4 else ""
        abgleich.append(
            {
                "titel": titel,
                "was_passiert": was,
                "form_vorschlag": form,
                "form_vorschlag_grund": grund,
            }
        )
    bericht = repo.gleiche_szenenfolge_ab(conn, chat_id, abgleich)
    for nummer, zeile in enumerate(zeilen, start=1):
        szene_id = bericht["ids"][nummer]
        # Das Setting ist die Vorgabe fuer ort/zeit/anlass (06.09.2026, Birk
        # 12:00): jede Szene bekommt sie beim Anlegen, statt spaeter danach
        # gefragt zu werden. ``uebernimm_rahmen`` schreibt nur in leere
        # Felder.
        szene_modul.uebernimm_rahmen(conn, chat_id, szene_id)
        figuren = zeile[2]
        ids = [nach_name[n.lower()] for n in figuren if n.lower() in nach_name]
        if ids:
            repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
    return list(bericht["nummern"])


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------


#: Wie die Ende-Zeile eines Geschichte-Vorschlags anfaengt.
_ENDE_PRAEFIX = re.compile(r"^\s*ende\s*[:\-–—]\s*", re.IGNORECASE)


def zerlege_geschichte(wert: str) -> tuple[str, list[tuple[str, str, list[str], str]]]:
    """Zerlegt einen ``VORSCHLAG GESCHICHTE:``-Block in ``(geschichte,
    Szenenzeilen)``.

    Zeile 1 ist der Bogen, Zeile 2 das Ende (mit oder ohne \"Ende:\" davor),
    ab Zeile 3 die Szenen in der Form der Szenenfolge -- deshalb geht der
    Rest durch ``zerlege()`` und nicht durch einen zweiten Zerleger.

    ``geschichte`` ist der Text, der in ``arbeitsstand.geschichte`` landet:
    zwei Zeilen, Bogen und Ende. Fehlt die Ende-Zeile (das Modell hat sie
    weggelassen), bleibt es bei einer -- geraten wird nichts.
    """
    roh = [z.strip() for z in (wert or "").splitlines() if z.strip()]
    if not roh:
        return "", []
    bogen = roh[0]
    rest = roh[1:]
    ende = ""
    if rest and _ENDE_PRAEFIX.match(rest[0]):
        ende = _ENDE_PRAEFIX.sub("", rest[0]).strip()
        rest = rest[1:]
    geschichte = bogen if not ende else f"{bogen}\nEnde: {ende}"
    return geschichte, zerlege("\n".join(rest))


def vorstellung(conn, zeile, chat_id: int | None = None) -> str:
    """Eine Szene, wie sie der Gruppe vorgestellt wird: alle Felder
    untereinander, fehlende Pflichtfelder als \"noch offen\" markiert.

    Deterministisch aus der Datenbank, kein Modellaufruf -- die Vorstellung
    ist eine Ansicht, keine Erfindung. Sie ist ausfuehrlicher als
    ``szene.planungszeile`` (eine Zeile, fuer Bestaetigungen): hier
    entscheidet die Gruppe, ob geschrieben werden darf."""
    from interview_theater import szene as szene_modul

    nummer = zeile["nummer"]
    kopf = f"Szene {nummer}" if nummer is not None else "Szene"
    if zeile["titel"]:
        kopf += f": {zeile['titel']}"
    fehlende, _ = szene_modul.fehlendes(conn, zeile)
    zeilen = [kopf]
    # Die FORM steht in Zeile 2, direkt unter dem Titel (05.09.2026 abends,
    # Birk): sie ist seit dem Wegfall der Formatfrage die eine Entscheidung,
    # die je Szene faellt -- ob Dialog, Monolog, Chor, Lied oder Rap. Unter
    # den uebrigen Feldern waere sie eine Angabe unter acht.
    form = (zeile["form"] or "").strip()
    zeilen.append(
        f"{szene_modul.FELDNAMEN['form']}: {form or 'noch offen'}"
    )
    # Der Pruef-Vermerk steht direkt darunter: er ist der Grund, aus dem diese
    # Szene ueberhaupt wieder vorgestellt wird (05.09.2026, Aenderung an einer
    # frueheren Szene).
    if chat_id is not None and zu_pruefen(conn, chat_id, nummer):
        zeilen.append(TEXT_ZU_PRUEFEN)
    for feld in ("ort", "zeit", "anlass", "figuren", "was_passiert",
                 "was_anders", "ton"):
        name = szene_modul.FELDNAMEN[feld]
        if feld == "figuren":
            namen = [f["name"] for f in repo.szene_figuren(conn, zeile["id"])]
            wert = ", ".join(namen)
        else:
            wert = (zeile[feld] or "").strip()
        if wert:
            zeilen.append(f"{name}: {wert}")
        elif feld in fehlende:
            zeilen.append(f"{name}: noch offen")
    ausserdem = [f for f in fehlende if f in szene_modul.ARBEITSSTAND_PFLICHTFELDER]
    if ausserdem:
        zeilen.append(
            "Es fehlt ausserdem: "
            + ", ".join(szene_modul.FELDNAMEN[f] for f in ausserdem)
        )
    # Die Frage steht ausdrücklich da (Birk, 05.09. abends): die Gruppe soll
    # nicht raten, was der Knopf "Passt, schreiben" tut, und nie einen
    # Slash-Befehl brauchen. Fehlt noch etwas, sagt der Knopf trotzdem zu --
    # er schlaegt die Luecken dann zuerst vor (szenenfolge, Feldvorschlag).
    if fehlende:
        zeilen.append(
            f"\nSoll ich Szene {nummer} jetzt schreiben? Was noch offen ist, "
            "schlage ich vorher vor."
        )
    else:
        zeilen.append(f"\nSoll ich Szene {nummer} jetzt schreiben?")
    return "\n".join(zeilen)


def ist_fertig(zeile) -> bool:
    """Hat die Gruppe diese Szene mit "Passt" abgenommen?

    Ueber eine eigene Spalte und nicht ueber "hat Volltext": ein
    geschriebener Text ist ein Entwurf, kein Ergebnis -- genau darum gibt es
    unter ihm die vier Knoepfe."""
    return bool("fertig_am" in zeile.keys() and zeile["fertig_am"])


#: Wie ein Pruef-Vermerk im Journal anfaengt. Der Vermerk ist die einzige
#: Stelle, an der \"Szene 3 muss nach der Aenderung an Szene 1 nochmal
#: angesehen werden\" ueberhaupt festgehalten ist -- eine eigene Spalte waere
#: eine Schemaaenderung fuer einen Zustand, den das Journal ohnehin traegt
#: (SPEC § 2). Der Code findet ihn ueber dieses Praefix wieder.
PRUEFVERMERK = "Szene {nummer} muss nach Aenderung an Szene {geaendert} geprueft werden"
_PRUEFVERMERK_ANFANG = "Szene {nummer} muss nach Aenderung an Szene "

#: Was ueber der Vorstellung einer so markierten Szene steht.
TEXT_ZU_PRUEFEN = "Vorherige Szene wurde geaendert - neu schreiben?"


def markiere_spaetere(conn, chat_id: int, nummer: int) -> list[int]:
    """Nach einer Aenderung an Szene ``nummer``: alle spaeteren Szenen MIT
    Volltext verlieren ihren Fertig-Stempel und bekommen einen Vermerk im
    Journal. Liefert die betroffenen Nummern.

    **Kein automatisches Neuschreiben** (Birk, 05.09.2026): eine Szene 3, die
    sich von selbst aendert, weil jemand an Szene 1 gearbeitet hat, waere ein
    Bot, der der Gruppe die Arbeit aus der Hand nimmt -- und drei bezahlte
    Laeufe fuer eine Notiz. Der Vermerk sagt, dass hinzusehen ist; entschieden
    wird an der Vorstellung der Szene ("Neu schreiben" · "So lassen").

    Nur Szenen MIT Volltext: eine noch leere spaetere Szene ist ohnehin
    ungeschrieben, ein Vermerk an ihr waere Laerm."""
    betroffen = []
    for szene in repo.hole_szenen(conn, chat_id):
        if szene["nummer"] is None or szene["nummer"] <= nummer:
            continue
        if not (szene["volltext"] or "").strip():
            continue
        repo.setze_szene_fertig(conn, szene["id"], False)
        repo.schreibe_journal(
            conn, chat_id, "offen",
            PRUEFVERMERK.format(nummer=szene["nummer"], geaendert=nummer),
            quelle="knopf",
        )
        betroffen.append(szene["nummer"])
    return betroffen


def zu_pruefen(conn, chat_id: int, nummer: int | None) -> bool:
    """Steht fuer diese Szene ein offener Pruef-Vermerk im Journal?

    Aus dem Journal und nicht aus einer Spalte: dort steht ohnehin, was gilt,
    und ein zurueckgenommener Eintrag (``repo.entferne_journal``, N3) faellt
    damit automatisch heraus -- \"So lassen\" muss nichts weiter tun, als den
    Vermerk zurueckzunehmen."""
    if nummer is None:
        return False
    anfang = _PRUEFVERMERK_ANFANG.format(nummer=nummer)
    return any(
        (e["text"] or "").startswith(anfang) for e in repo.journal(conn, chat_id)
    )


def nimm_pruefvermerk(conn, chat_id: int, nummer: int) -> None:
    """Nimmt die Pruef-Vermerke zu dieser Szene zurueck ("So lassen" oder eine
    neue Fassung). Weich wie alles hier (N3): der Eintrag bleibt in der
    Datenbank, er zaehlt nur nicht mehr."""
    anfang = _PRUEFVERMERK_ANFANG.format(nummer=nummer)
    while repo.entferne_journal(conn, chat_id, anfang) is not None:
        pass


def uebersicht(conn, chat_id: int) -> str:
    """Die Szenenfolge mit Status, wie sie Phase 7 (Schaerfung des Stuecks) zeigt.

    Drei Zustaende, in der Sprache der Gruppe: **fertig** (abgenommen),
    **geschrieben** (Text da, noch nicht abgenommen), **offen** (nur geplant).
    """
    zeilen = []
    for s in repo.hole_szenen(conn, chat_id):
        kopf = f"Szene {s['nummer']}" if s["nummer"] is not None else "Szene"
        if s["titel"]:
            kopf += f": {s['titel']}"
        if ist_fertig(s):
            stand = "fertig"
        elif (s["volltext"] or "").strip():
            stand = "geschrieben"
        else:
            stand = "offen"
        zeilen.append(f"{kopf} — {stand}")
        # Die Zusammenfassung als eine eingerueckte Zeile darunter
        # (06.09.2026): die Uebersicht sagte bis dahin nur, DASS eine Szene
        # geschrieben ist, nicht was in ihr passiert.
        try:
            fassung = (s["zusammenfassung"] or "").strip()
        except (IndexError, KeyError):
            fassung = ""
        if fassung:
            zeilen.append(f"  {' '.join(fassung.split())}")
    if not zeilen:
        return "Es gibt noch keine Szenen."
    return "Euer Durchlauf:\n" + "\n".join(zeilen)


def textbuch(conn, chat_id: int) -> str:
    """Alle Szenen als ein Textbuch (Markdown) -- der Datei-Export in Phase 7.

    Szenen ohne Volltext stehen mit ihrer Planung drin und nicht als Luecke:
    ein Textbuch, in dem Szene 4 fehlt, sieht aus wie ein Fehler; eines, in
    dem Szene 4 als \"noch nicht geschrieben\" steht, sagt die Wahrheit."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    teile = ["# Textbuch"]
    if stand and (stand["kernthema"] or "").strip():
        teile.append(f"Kernthema: {stand['kernthema'].strip()}")
    for s in repo.hole_szenen(conn, chat_id):
        kopf = f"## Szene {s['nummer']}" if s["nummer"] is not None else "## Szene"
        if s["titel"]:
            kopf += f": {s['titel']}"
        teile.append(kopf)
        teile.append(vorstellung(conn, s))
        volltext = (s["volltext"] or "").strip()
        teile.append(volltext if volltext else "(noch nicht geschrieben)")
    return "\n\n".join(teile)


def dateiname(chat_id: int) -> str:
    """Der Name der Textbuch-Datei. Ohne chat_id im Namen: der Dateiname
    steht in der Gruppe und soll nichts ueber die Gruppe verraten."""
    return "textbuch.md"


# ---------------------------------------------------------------------------
# Die erwartete Regie-Notiz ("Passt, aber anders" unter einem Szenentext)
# ---------------------------------------------------------------------------
#
# Bewusst im Prozess und nicht in der Datenbank: es ist ein Zustand von
# Sekunden ("der Bot hat gerade gefragt, was anders werden soll"), kein Stand
# des Workshops. Nach einem Neustart ist er weg -- und das ist richtig, dann
# ist auch die Frage im Chat laengst nach oben gescrollt. Derselbe Gedanke wie
# bei ``szene._usa_erinnerungen``.
_regienotiz_erwartet: dict[int, int] = {}


def erwarte_regienotiz(chat_id: int, nummer: int) -> None:
    """Merkt: die naechste freie Nachricht dieser Gruppe ist die Regie-Notiz
    fuer Szene ``nummer``."""
    _regienotiz_erwartet[chat_id] = nummer


def nimm_regienotiz(chat_id: int) -> int | None:
    """Liefert die erwartete Szenennummer und vergisst sie -- einmalig, damit
    nicht jede weitere Nachricht die Szene neu schreiben laesst."""
    return _regienotiz_erwartet.pop(chat_id, None)


# ---------------------------------------------------------------------------
# Der Aufruf
# ---------------------------------------------------------------------------


def _material(conn, chat_id: int) -> str:
    """Was das Modell fuer einen Szenenfolge-Vorschlag braucht: den Rahmen,
    das Kernthema, die Figuren, die bestehende Folge und das Verworfene.

    Aus ``szene.py`` geholt statt hier zweitgepflegt -- laeuft der Szenen-
    Prompt auseinander, laeuft auch dieser mit."""
    from interview_theater import szene as szene_modul

    bloecke = [
        szene_modul._format_rahmen_text(conn, chat_id),
        szene_modul._thema_text(conn, chat_id),
        szene_modul._figuren_text(conn, chat_id),
        szene_modul._continuity_text(conn, chat_id, None),
        szene_modul._verworfen_text(conn, chat_id),
    ]
    return "\n\n".join(b for b in bloecke if b)


def _erfundenes(conn, chat_id: int) -> str:
    """Was in Phase 4 (Geschichte) im Prompt stehen darf: Begriffe, Fragen,
    Setting, Figuren -- und die bestehende Folge.

    **Kein Material.** Keine Verdichtungen, keine Zitate, keine Sprachprofile
    (die haengen an Interviews). Das ist der Kontext-Filter dieser Phase, im
    Code und nicht nur im Prompt: ein Modell, das die Interviews sieht,
    erfindet nichts mehr, es referiert."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen: list[str] = []
    if stand:
        if (stand["begriffe"] or "").strip():
            zeilen.append(f"Begriffe der Gruppe: {stand['begriffe'].strip()}")
        if (stand["fragen"] or "").strip():
            zeilen.append("Fragen der Gruppe:\n" + stand["fragen"].strip())
        if (stand["rahmen"] or "").strip():
            zeilen.append(f"Setting: {stand['rahmen'].strip()}")
        if "geschichte" in stand.keys() and (stand["geschichte"] or "").strip():
            zeilen.append("Bisherige Geschichte:\n" + stand["geschichte"].strip())
    figuren = repo.figuren(conn, chat_id)
    if figuren:
        block = ["Figuren:"]
        for figur in figuren:
            kopf = f"- {figur['name']}"
            if figur["beschreibung"]:
                kopf += f" -- {figur['beschreibung']}"
            block.append(kopf)
        zeilen.append("\n".join(block))
    szenen = repo.hole_szenen(conn, chat_id)
    if szenen:
        block = ["Bisherige Szenenfolge:"]
        for s in szenen:
            teile = [f"Szene {s['nummer']}"]
            if s["titel"]:
                teile.append(s["titel"])
            if s["was_passiert"]:
                teile.append(s["was_passiert"])
            block.append(" — ".join(teile))
        zeilen.append("\n".join(block))
    return "\n\n".join(zeilen)


def systemanweisung(anzahl: int) -> str:
    """Anweisung fuer den Folge-Aufruf: die Form (Marker!) plus der
    Phasenfokus aus ``prompts/phasen/6.md``, heiss nachgeladen.

    Die Phasendatei ist optional (``hole_optional``): fehlt sie am
    Workshoptag, entsteht trotzdem eine Szenenfolge."""
    teile = [ANWEISUNG_FOLGE.format(anzahl=anzahl)]
    phase = anweisungen.hole_optional("phasen/6")
    if phase and phase.strip():
        teile.append(phase.strip())
    return "\n\n".join(teile)


def systemanweisung_geschichte(anzahl: int | None = None) -> str:
    """Anweisung fuer den Geschichte-Aufruf plus der Phasenfokus aus
    ``prompts/phasen/4.md``.

    ``anzahl`` ist eine Bitte, keine Vorgabe: wie viele Szenen es werden,
    ergibt sich aus der Geschichte -- \"Anzahl aendern\" reicht sie herein,
    wenn die Gruppe eine nennt."""
    teile = [ANWEISUNG_GESCHICHTE]
    if anzahl:
        teile.append(f"Die Gruppe moechte {anzahl} Szenen.")
    phase = anweisungen.hole_optional("phasen/4")
    if phase and phase.strip():
        teile.append(phase.strip())
    return "\n\n".join(teile)


def baue_nutzertext_geschichte(conn, chat_id: int, wunsch: str | None = None) -> str:
    """Das Erfundene, dann der Auftrag -- **ohne Material** (``_erfundenes``)."""
    teile = [_erfundenes(conn, chat_id)]
    auftrag = (
        "Euer Auftrag:\nSchlag die Geschichte im Groben vor: was passiert, "
        "wie es endet, welche Szenen."
    )
    if wunsch and wunsch.strip():
        auftrag += f"\n{wunsch.strip()}"
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)


def baue_nutzertext(conn, chat_id: int, anzahl: int, wunsch: str | None = None) -> str:
    """Material, dann der Auftrag -- was am Ende steht, wiegt am schwersten
    (SPEC § 6.1), deshalb der Wunsch der Gruppe zuletzt."""
    teile = [_material(conn, chat_id)]
    auftrag = f"Euer Auftrag:\nSchlag {anzahl} Szenen vor."
    if wunsch and wunsch.strip():
        auftrag += f"\n{wunsch.strip()}"
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)


_TEXT_LAEUFT = "Ich schlage euch eine Szenenfolge vor, einen Moment."
_TEXT_BESETZT = "Ich denke gerade schon ueber die Szenenfolge nach, gleich."
_TEXT_FEHLER = (
    "Die Szenenfolge ist mir nicht gelungen. Sagt es nochmal, dann versuche "
    "ich es neu."
)
_TEXT_FELDER_LAEUFT = "Ich schlage die fehlenden Angaben vor, einen Moment."
_TEXT_GESCHICHTE_LAEUFT = "Ich schlage euch eine Geschichte vor, einen Moment."


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    """Wie ``szene._sende_und_merke``: die Zeile geht in die Gruppe UND ins
    Verlaufsfenster des naechsten Gespraechszugs."""
    from interview_theater import szene as szene_modul

    szene_modul._sende_und_merke(conn, tg, e, chat_id, text)


def _lauf(conn, tg, klm, e, chat_id: int, system: str, nutzer: str, art: str,
          sperre: threading.Lock, nachbereitung) -> None:
    """Der Thread-Rumpf: Modell fragen, Antwort mit Leiste ausspielen, Sperre
    in JEDEM Fall freigeben -- bliebe sie liegen, koennte die Gruppe fuer den
    Rest des Workshops keinen Vorschlag mehr bekommen (wie ``szene._lauf``).

    Waehrenddessen laufen die Arbeitszeilen (06.09.2026, Birk 11:15): je
    Auftragsart eine eigene Liste, alle 15 s eine neue Zeile, am Ende
    geloescht (``arbeitszeilen.Lauf``)."""
    from interview_theater import arbeitszeilen

    zeilen = arbeitszeilen.sichtbar(tg, chat_id, art)
    try:
        antwort = klm.prosa(
            chat_id, system, nutzer, art, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
        )
        if not (antwort or "").strip():
            raise SzenenfolgeFehler("Antwort des Sprachmodells war leer")
        nachbereitung(antwort)
    except Exception:
        log.exception("Szenenfolge-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "szenenfolge_fehlgeschlagen", "Szenenfolge-Aufruf fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall nicht schreibbar, chat_id=%s", chat_id)
        _sende(conn, tg, e, chat_id, _TEXT_FEHLER)
    finally:
        zeilen.stoppe()
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, anzahl: int | None = None,
           wunsch: str | None = None) -> threading.Thread | None:
    """Kuendigt an und gibt den Vorschlags-Aufruf an einen eigenen Thread ab.

    Liefert den Thread (fuer Tests) oder None, wenn nichts angestossen wurde.
    **Kein Modellaufruf im aufrufenden Thread** -- das ist die Bedingung
    dafuer, dass ein Knopf ihn ueberhaupt ausloesen darf (``knoepfe.py``,
    Zusage 2)."""
    if klm is None:
        log.error("Szenenfolge ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    anzahl = int(anzahl or ANZAHL_VORGABE)
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_LAEUFT)

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_szenenfolge(conn, tg, chat_id, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, systemanweisung(anzahl),
              baue_nutzertext(conn, chat_id, anzahl, wunsch), ART, sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread


def starte_geschichte(conn, tg, klm, e, chat_id: int, anzahl: int | None = None,
                      wunsch: str | None = None) -> threading.Thread | None:
    """Der Geschichte-Vorschlag (Phase 4) -- derselbe Weg wie ``starte``, nur
    mit anderer Anweisung und **ohne Material** im Nutzertext.

    Kein Modellaufruf im aufrufenden Thread (Zusage 2): ein Knopf darf ihn
    ausloesen, weil er sofort abgibt."""
    if klm is None:
        log.error("Geschichte ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_GESCHICHTE_LAEUFT)

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_geschichte(conn, tg, chat_id, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, systemanweisung_geschichte(anzahl),
              baue_nutzertext_geschichte(conn, chat_id, wunsch),
              ART_GESCHICHTE, sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread



def systemanweisung_geschichte_szenen() -> str:
    """Anweisung fuer die Szenenfolge NACH der gewaehlten Richtung
    (06.09.2026, Birk 11:42) plus der Phasenfokus aus ``prompts/phasen/4.md``."""
    teile = [ANWEISUNG_GESCHICHTE_SZENEN]
    phase = anweisungen.hole_optional("phasen/4")
    if phase and phase.strip():
        teile.append(phase.strip())
    return "\n\n".join(teile)


def starte_geschichte_szenen(conn, tg, klm, e, chat_id: int,
                             anzahl: int | None = None,
                             wunsch: str | None = None):
    """Die Szenenfolge, nachdem die Gruppe eine Richtung gewaehlt hat.

    Derselbe Weg wie ``starte``, aber **ohne Material** im Nutzertext: in
    Phase 4 wird erfunden (``baue_nutzertext_geschichte``). Kein Modellaufruf
    im aufrufenden Thread (Zusage 2)."""
    if klm is None:
        log.error("Szenenfolge ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_LAEUFT)

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_szenenfolge(conn, tg, chat_id, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, systemanweisung_geschichte_szenen(),
              baue_nutzertext_geschichte(conn, chat_id, wunsch), ART,
              sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread


def starte_feldvorschlag(conn, tg, klm, e, chat_id: int, ziel) -> threading.Thread | None:
    """Schlaegt die fehlenden Pflichtfelder EINER Szene vor -- der Ersatz fuer
    den Sperrtext an der Stelle \"Passt, schreiben\" (Birk, 05.09.2026).

    Der Sperrtext (``szene.sperrtext``) bleibt, wo er hingehoert: beim
    direkten Schreibauftrag. Wer dagegen gerade eine Szene vor Augen hat und
    \"Passt, schreiben\" tippt, soll nicht eine Liste von Luecken bekommen,
    sondern Vorschlaege mit Knoepfen darunter."""
    from interview_theater import szene as szene_modul

    if klm is None:
        log.error("Feldvorschlag ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    fehlende, _ = szene_modul.fehlendes(conn, ziel)
    # Die Arbeitsstand-Felder (Format, Rahmen) gehoeren in Phase 4 und werden
    # hier NICHT vorgeschlagen: sie haengen am Stueck, nicht an der Szene.
    fehlende = [f for f in fehlende if f not in szene_modul.ARBEITSSTAND_PFLICHTFELDER]
    if not fehlende:
        return None
    nummer = ziel["nummer"]
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_FELDER_LAEUFT)
    system = ANWEISUNG_FELDER.format(felder=", ".join(fehlende))
    nutzer = "\n\n".join(
        t for t in (
            _material(conn, chat_id),
            szene_modul._diese_szene_text(conn, ziel),
            f"Euer Auftrag:\nSchlag die fehlenden Angaben fuer Szene {nummer} vor.",
        ) if t
    )

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_szenenfelder(conn, tg, chat_id, nummer, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, system, nutzer, ART_FELDER, sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread

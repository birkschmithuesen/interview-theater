"""Die Stimmen-Sets aus dem echten Tag 1 -- **PII-frei abgeleitet**.

Am 05./06.09.2026 haben drei echte Gruppen (Sechzehnjaehrige) und eine
Testgruppe (die Regie) mit dem Bot gearbeitet. Was dabei entstanden ist,
laesst sich nicht einfach in eine Simulation kippen: in ``aufnahme.transkript``
stehen Lebensgeschichten Minderjaehriger, in ``nachricht`` stehen ihre
Klarnamen und ihr Wortlaut.

**Was hier drin ist und warum es drin sein darf**

* ``BEGRIFFE`` -- die Begriffslisten aus ``arbeitsstand.begriffe``. Die
  Gruppen haben sie selbst im Plenum an die Wand geschrieben und dem Bot als
  **Stueckthema** uebergeben; sie sind eine kuenstlerische Setzung, keine
  personenbezogene Angabe.
* ``THEMENSTICHWORTE`` -- die Themenzeilen aus ``verdichtung_thema``, auf ihr
  **Stichwort** verkuerzt. Kein Belegzitat, keine Zusammenfassung, kein Satz
  aus einem Transkript. Sie sagen, worum es in der Gruppe ging, nicht was
  jemand erzaehlt hat.
* ``VERHALTEN`` -- Verhaltensmuster als **Aggregat**: Anzahl Nachrichten,
  Medianlaenge, wie oft ein Knopf angeboten und wie oft er gedrueckt wurde,
  wie viele Interviews gefuehrt wurden. Zahlen ueber eine Gruppe, keine
  Aussage ueber eine Person.
* Der Steckbrief der **Regie** ist aus Birks eigenen Nachrichten abgeleitet
  -- er ist ihr Autor und hat sie ausdruecklich dafuer freigegeben.

**Was hier ausdruecklich NICHT drin ist**

Kein Wortlaut aus ``aufnahme.transkript``, keine Telegram-Usernamen, keine
Klarnamen, kein Nachrichtentext einer Teilnehmerin. ``tests/
test_simulation_tag1.py`` prueft das gegen die echte Datenbank, wenn sie da
ist -- keine Achtwortfolge aus einem echten Transkript darf in dieser Datei
oder in den Steckbriefen stehen.

**Die Interviews bleiben erfunden.** Ein Lauf mit einem ``tag1``-Set zieht
seine Transkripte aus ``simulation/interviews/set{1,2,3}`` wie jeder andere.
Was aus Tag 1 kommt, ist die **Art zu schreiben** und der **Themenkreis** --
nie das Material.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulation import stimmen

#: Die Begriffslisten, wie die drei Gruppen sie selbst gesetzt haben
#: (``arbeitsstand.begriffe``, Stand 06.09.2026 frueh).
BEGRIFFE = {
    "tag1-gruppe1": ["Trauma", "Macht", "Stereotype", "Massenkontrolle"],
    "tag1-gruppe2": ["Liebe", "Freundschaft", "Mord", "Depression"],
    "tag1-gruppe3": ["Rassismus", "Liebe", "Spass", "Streit"],
}

#: Die Themen aus ``verdichtung_thema``, auf ihr Stichwort verkuerzt. Sie
#: gehen NICHT in den Prompt des Bots -- sie stehen hier, damit die
#: Fragenrichtung eines Sets nachvollziehbar aus dem echten Tag kommt und
#: nicht aus einem Einfall.
THEMENSTICHWORTE = {
    "tag1-gruppe1": ["Stereotyp-Erfahrung", "Ueberwachung", "Trauma",
                     "Interviewabbruch"],
    "tag1-gruppe2": ["Liebe trotz Gewalt", "Freundschaft und Depression"],
    "tag1-gruppe3": ["Rassismus", "Streit", "Liebe", "Spass"],
}

#: Die Fragenrichtung je Set -- aus den echten ``arbeitsstand.fragen``
#: **umformuliert**, nicht kopiert: eine Frageliste ist die Arbeit einer
#: Gruppe. Sie dient dem Simulator nur als Ziel ("ungefaehr in diese
#: Richtung"), der Bot schlaegt seine eigenen zehn vor.
FRAGENRICHTUNG = {
    "tag1-gruppe1": [
        "Wann hast du gemerkt, dass etwas dich veraendert hat?",
        "Wer hatte Macht ueber dich -- und wolltest du sie selbst?",
        "Wann hat jemand ein Bild von dir gehabt, das nicht stimmte?",
    ],
    "tag1-gruppe2": [
        "Was bedeutet Liebe, wenn um dich herum Gewalt passiert?",
        "Wie geht Freundschaft weiter, wenn es einem schlecht geht?",
        "Wann hat dich Liebe das letzte Mal wirklich getroffen?",
    ],
    "tag1-gruppe3": [
        "Wann hast du Rassismus zum ersten Mal bewusst erlebt?",
        "Was hat dir in dem Moment geholfen -- oder wer?",
        "Wann hast du das letzte Mal richtig gestritten, und worum ging es?",
    ],
}


@dataclass(frozen=True)
class Aggregat:
    """Was eine Gruppe an Tag 1 **getan** hat, in Zahlen.

    Kein Text, keine Namen. Die Zahlen begruenden den Steckbrief: eine
    Gruppe mit Medianlaenge 27 Zeichen und null Phasenknopf-Druecken bekommt
    einen anderen Steckbrief als eine, die alles bestaetigt."""

    nachrichten: int
    median_zeichen: int
    kurznachrichten: int          # <= 6 Zeichen
    mit_rueckfrage: int
    interviews: int
    verdichtungen: int
    knoepfe_angeboten: int
    knoepfe_gedrueckt: int
    phasenknoepfe_angeboten: int
    phasenknoepfe_gedrueckt: int


#: Die Aggregate, am 06.09.2026 aus ``betrieb/soap.db`` gelesen (read-only,
#: ``mode=ro``) und hier als Zahlen festgehalten. Als Konstante und nicht als
#: Abfrage, damit ein Lauf reproduzierbar bleibt: die Betriebsdatenbank
#: aendert sich weiter, ein Steckbrief soll das nicht.
VERHALTEN = {
    "tag1-gruppe1": Aggregat(25, 27, 3, 2, 4, 1, 24, 6, 6, 0),
    "tag1-gruppe2": Aggregat(17, 28, 5, 0, 10, 1, 38, 14, 11, 0),
    "tag1-gruppe3": Aggregat(17, 34, 4, 1, 6, 1, 28, 8, 8, 0),
}

#: Die Regie: Birks eigene Testgruppe. Die Zahlen stammen aus
#: ``betrieb/test.db``; sein Wortlaut darf hier verwendet werden, weil er sein
#: Autor ist -- Beispielsaetze stehen im Steckbrief ``stimmen/regie.md``.
VERHALTEN_REGIE = Aggregat(49, 30, 2, 6, 1, 1, 0, 0, 0, 0)

#: Die Sets, die ``--set`` annimmt. Reihenfolge ist die Reihenfolge im
#: Bericht.
SETS = ("tag1-gruppe1", "tag1-gruppe2", "tag1-gruppe3", "regie")

#: Welches erfundene Interview-Set thematisch am naechsten liegt. Die
#: Transkripte bleiben erfunden -- diese Zuordnung sorgt nur dafuer, dass
#: Begriffe, Fragen und Material nicht in drei Richtungen zeigen.
INTERVIEWSET = {
    "tag1-gruppe1": 1,
    "tag1-gruppe2": 2,
    "tag1-gruppe3": 3,
    "regie": 3,
}

#: Wie viele Interviews ein tag1-Lauf fuehrt. Zwei statt fuenf: die echten
#: Gruppen haben an Tag 1 je EINE Verdichtung zustande gebracht, und ein
#: Lauf mit fuenf sauberen Interviews misst einen Nachmittag, den es nicht
#: gab. Zwei, damit der Fall "zweites Interview an ein bestehendes" noch
#: vorkommt.
INTERVIEWS_JE_LAUF = 2

#: Die Gewichte: in einer echten Gruppe schreibt nicht jede gleich viel. Hier
#: spielt aber je Set nur EINE Stimme -- die Gruppen haben an Tag 1
#: tatsaechlich ueber ein Geraet geschrieben (ein Chat, eine Person tippt).
GEWICHT = 1


def steckbrief(name: str) -> stimmen.Steckbrief:
    """Der Steckbrief eines tag1-Sets -- dieselbe Form wie ``stimmen.BESETZUNG``.

    Der ``schluessel`` ist zugleich der Dateiname unter
    ``simulation/stimmen/``; ``lade_profil`` prueft ihn gegen ``stimmen.ALLE``,
    deshalb sind die vier dort registriert."""
    if name not in SETS:
        raise ValueError(f"unbekanntes tag1-Set: {name!r}")
    return next(b for b in stimmen.ALLE if b.schluessel == name)


def begriffe(name: str) -> list[str]:
    """Die Begriffsliste, mit der ein tag1-Lauf startet."""
    return list(BEGRIFFE.get(name, BEGRIFFE["tag1-gruppe3"]))


def fragen(name: str) -> list[str]:
    """Die Fragenrichtung -- Ziel der Stimmen, nicht Vorgabe an den Bot."""
    return list(FRAGENRICHTUNG.get(name, FRAGENRICHTUNG["tag1-gruppe3"]))


def interviewset(name: str) -> int:
    return INTERVIEWSET.get(name, 1)


def person(name: str) -> stimmen.Person:
    """Die eine Stimme eines tag1-Laufs."""
    return stimmen.aus_steckbrief(steckbrief(name))


def aggregat(name: str) -> Aggregat:
    return VERHALTEN_REGIE if name == "regie" else VERHALTEN[name]


def referenz(name: str) -> dict:
    """Die Messlatte aus Tag 1 -- die Zahlen, gegen die der Bericht die
    Simulation stellt.

    Bewusst nur Aggregate: was eine Gruppe geschrieben hat, steht nirgends in
    diesem Repository und soll es auch nicht."""
    zahl = aggregat(name)
    return {
        "quelle": "Tag 1 (aggregiert, PII-frei)",
        "nachrichten_gesamt": zahl.nachrichten,
        "median_zeichen": zahl.median_zeichen,
        "kurznachrichten": zahl.kurznachrichten,
        "interviews": zahl.interviews,
        "verdichtungen": zahl.verdichtungen,
        "knoepfe_angeboten": zahl.knoepfe_angeboten,
        "knoepfe_gedrueckt": zahl.knoepfe_gedrueckt,
        "phasenknoepfe_angeboten": zahl.phasenknoepfe_angeboten,
        "phasenknoepfe_gedrueckt": zahl.phasenknoepfe_gedrueckt,
        "begriffe": begriffe(name) if name != "regie" else BEGRIFFE["tag1-gruppe3"],
        "themen": THEMENSTICHWORTE.get(name, []),
    }

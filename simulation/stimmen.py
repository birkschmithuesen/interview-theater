"""Die simulierten Teilnehmerinnen: drei **Personen**, gespielt von Claude.

**Personen, nicht Sprachstile.** Bis zum 05.09.2026 standen hier drei
Schreibweisen -- knapp, ausschweifend, skeptisch. Das war die falsche
Abstraktion: eine Schreibweise hat keinen Grund, und ohne Grund wird jede
Stimme in jedem Schritt gleich kooperativ. Jetzt stehen hier drei Menschen
mit Alter, Bildungsweg, Technikvertrautheit und einem eigenen Ziel im
Workshop (``simulation/stimmen/*.md``). Die Sprache folgt daraus: Guelten
tippt kurz, weil sie mit einem Finger tippt; Halyna schreibt ganze Saetze,
weil sie Ingenieurin ist und Genauigkeit ihr Beruf war.

Daraus folgt auch, **wie oft** jemand schreibt: wer dem Computer am wenigsten
traut, schreibt am seltensten (``gewicht``, ``waehle_sprecher``). Eine
Gruppe, in der alle drei gleich viel schreiben, gibt es nicht -- und der Bot
soll gemessen werden an einer, die es wirklich gibt.

Jede Stimme bekommt drei Dinge: den **Chatverlauf** (die letzten
``VERLAUF_NACHRICHTEN`` Nachrichten), das **Ziel des aktuellen Schritts**
(``skript.py``) und die Anweisung, EINE Nachricht zu schreiben. Sie bekommt
ausdruecklich **nicht** den Arbeitsstand aus der Datenbank: eine
Teilnehmerin sieht nur, was im Chat steht -- und ob der Bot ihr sagt, was er
sich gemerkt hat, ist genau die Frage, die der Lauf misst.

**Nicht das Modell des Bots.** Die Stimmen laufen ueber ``simulation/claude.py``
(Opus am lokalen Proxy), nicht ueber Infomaniak: der Bot ist der Prueflung,
und ein Prueflung, der zugleich seine eigenen Teilnehmerinnen spielt, misst
vor allem sich selbst. Nebeneffekt, aber kein unwichtiger: die Stimmen kosten
damit nichts, und ein Lauf darf so viele Nachrichten haben, wie er braucht.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

#: Wo die Steckbriefe liegen. Gleichnamiges Verzeichnis neben diesem
#: Modul: Python findet erst dieses Modul und dann erst das Verzeichnis, ein
#: Namenskonflikt entsteht nicht (``simulation/stimmen/`` hat kein
#: ``__init__.py`` und ist deshalb keine Paketkonkurrenz).
VERZEICHNIS = Path(__file__).resolve().parent / "stimmen"

#: So viele Nachrichten des Chatverlaufs bekommt eine Stimme zu sehen.
VERLAUF_NACHRICHTEN = 30


@dataclass(frozen=True)
class Steckbrief:
    """Eine Person: Dateiname des Steckbriefs, Name im Chat, wie oft sie
    schreibt, und ihr Ziel im Workshop.

    ``gewicht`` ist die relative Haeufigkeit, mit der sie gezogen wird -- die
    Umsetzung des Satzes "die Person mit dem geringsten Technikvertrauen
    schreibt am seltensten". Es ist ein Verhaeltnis, keine
    Wahrscheinlichkeit: 3 zu 5 zu 4 heisst, dass Guelten auf fuenf Nachrichten
    von Dilan drei schreibt."""

    schluessel: str
    name: str
    gewicht: int
    ziel: str


#: Die feste Besetzung der Sets 1-3. Reihenfolge = Anlegereihenfolge, damit
#: derselbe Seed dieselbe Besetzung ergibt.
BESETZUNG: tuple[Steckbrief, ...] = (
    Steckbrief(
        "guelten", "Guelten", 3,
        "Ihre eigene Geschichte soll im Stueck vorkommen -- aber nicht ihr Name.",
    ),
    Steckbrief(
        "dilan", "Dilan", 5,
        "Das Stueck soll politisch sein, keine ruehrende Migrantinnengeschichte.",
    ),
    Steckbrief(
        "halyna", "Halyna", 4,
        "Es soll handwerklich stimmen -- Figuren, Konflikt, Aufbau muessen tragen.",
    ),
)

#: Der Steckbrief fuer ``--set birk``: EINE Person, kalibriert auf den echten
#: Probelauf vom 04.09.2026 (``simulation/birk.py``). Steht ausserhalb von
#: ``BESETZUNG``, weil dieser Lauf keine Gruppe simuliert, sondern genau die
#: eine Person, deren Chatverlauf als Messlatte danebenliegt.
BIRK = Steckbrief(
    "birk", "Birk", 1,
    "Durch die Phasen kommen, bis Szenentexte dastehen. Wenig Zeit.",
)

#: Die Steckbriefe aus dem echten Tag 1 (06.09.2026, ``simulation/tag1.py``).
#: Je Set EINE Stimme: die drei Gruppen haben tatsaechlich ueber ein Geraet
#: geschrieben, und eine simulierte Gruppe mit drei Handys waere eine
#: Erfindung, die den Bot leichter macht als er es hatte.
#:
#: Die Steckbriefe selbst sind PII-frei aus Aggregaten abgeleitet -- Begriffe,
#: Antwortlaengen, Knopfverhalten. Kein Wortlaut, keine Namen. Die einzige
#: Ausnahme ist ``regie``: dort sind Beispielsaetze Birks eigene, und er ist
#: ihr Autor.
TAG1: tuple[Steckbrief, ...] = (
    Steckbrief(
        "tag1-gruppe1", "Gruppe A", 1,
        "Schnell durchkommen -- reden ist die Arbeit, tippen kostet Zeit.",
    ),
    Steckbrief(
        "tag1-gruppe2", "Gruppe B", 1,
        "Nichts uebernehmen, was nicht von uns kommt.",
    ),
    Steckbrief(
        "tag1-gruppe3", "Gruppe C", 1,
        "Es soll fertig werden -- gestritten wird im Raum, nicht im Chat.",
    ),
    Steckbrief(
        "regie", "Regie", 1,
        "Den Bot pruefen: speichert er, wiederholt er sich, baut er Menues?",
    ),
)

#: Alle Steckbriefe, die es gibt -- fuer ``lade_profil`` und die Tests.
ALLE = BESETZUNG + (BIRK,) + TAG1

#: Wahrscheinlichkeit, dass nach der ersten Stimme sofort eine zweite
#: nachlegt -- der haeufigste Fall in einer echten Gruppe, und derjenige, der
#: das Sammeln in ``ablauf.bearbeite`` ueberhaupt erst auf die Probe stellt.
P_ZWEITE_STIMME = 0.3

#: Art dieses Aufrufs in der Statistik des Simulationsklienten
#: (``claude.Statistik``) -- damit der Bericht Stimmen und Richter getrennt
#: ausweisen kann.
ART = "stimme"

#: Ausgabebudget einer Stimme. Eine Telegram-Nachricht, auch eine
#: ausschweifende, bleibt deutlich darunter; der Deckel faengt nur den Fall
#: ab, dass das Modell ins Erzaehlen kommt.
MAX_TOKENS = 600

_RAHMEN = (
    "Ihr entwickelt in einem Workshop ein Theaterstueck aus Interviews mit "
    "Frauen mit Migrationsgeschichte. Der Bot in der Gruppe hilft euch dabei: "
    "er merkt sich, was ihr festlegt, wertet die Interviews aus und schreibt "
    "spaeter Szenentexte. Ihr sprecht im Raum miteinander -- in den Chat "
    "schreibt ihr nur, was an den Bot geht."
)

_ANWEISUNG = (
    "Schreibe jetzt GENAU EINE Nachricht in die Gruppe, als {name}. Nur den "
    "Nachrichtentext, ohne deinen Namen davor, ohne Anfuehrungszeichen, ohne "
    "Erklaerung dazu. Wiederhole nicht, was schon im Verlauf steht."
)

_ZIEL_KOPF = "Worauf du gerade hinauswillst (nicht woertlich abschreiben):"


_ZIEL_PERSON = "Dein eigenes Ziel im Workshop:"


#: Praefix, mit dem eine Stimme sagt, dass sie einen Knopf drueckt statt zu
#: schreiben. Ein Praefix und kein eigener Aufruf: eine Person entscheidet
#: das in einem Moment, nicht in zwei.
KNOPF_PRAEFIX = "KNOPF:"

#: So viele Knopftexte bekommt eine Stimme hoechstens zu sehen. Die
#: Fragenauswahl haengt dreizehn Knoepfe unter eine Nachricht; alle
#: aufzuzaehlen ist richtig, aber ein Deckel gegen den Fall, dass eine
#: Nachricht versehentlich hundert traegt.
MAX_KNOEPFE = 20

_KNOPF_KOPF = (
    "Unter der letzten Bot-Nachricht haengen Knoepfe zum Antippen. Das ist "
    "der normale Weg -- eine echte Gruppe tippt, statt zu tippen:"
)

_KNOPF_ANWEISUNG = (
    "Entscheide selbst: Wenn einer der Knoepfe das trifft, was du gerade "
    "willst, antworte mit genau einer Zeile\n"
    "{praefix} <Knopftext genau so wie oben>\n"
    "und sonst nichts. Trifft keiner, schreib stattdessen deine Nachricht "
    "als Text. Erfinde keinen Knopftext, der oben nicht steht."
)


def knopfliste(knoepfe: list[dict]) -> list[str]:
    """Die sichtbaren Knopftexte, ohne Dubletten, hoechstens ``MAX_KNOEPFE``.

    Ohne Dubletten, weil dieselbe Grundleiste unter mehreren Vorschlaegen
    haengen kann: die Stimme soll \"Gefaellt uns, weiter\" einmal lesen und
    nicht dreimal, sonst liest sie es als drei verschiedene Angebote."""
    gesehen: list[str] = []
    for knopf in knoepfe:
        text = (knopf.get("beschriftung") or "").strip()
        if text and text not in gesehen:
            gesehen.append(text)
        if len(gesehen) >= MAX_KNOEPFE:
            break
    return gesehen


@dataclass(frozen=True)
class Person:
    """Eine simulierte Teilnehmerin an einem Lauf.

    ``zusatz`` haengt hinten an den Steckbrief -- die Stelle, an der
    ``--set birk`` seiner Stimme den echten Chatverlauf als Stil-Referenz
    mitgibt (``birk.stil_referenz``)."""

    name: str
    profil: str            # Dateiname des Steckbriefs, zugleich Schluessel
    gewicht: int = 1
    ziel: str = ""
    zusatz: str = ""

    @property
    def system(self) -> str:
        teile = [lade_profil(self.profil)]
        if self.zusatz:
            teile.append(self.zusatz.strip())
        return "\n\n".join(teile)


def aus_steckbrief(brief: Steckbrief, zusatz: str = "") -> Person:
    return Person(brief.name, brief.schluessel, brief.gewicht, brief.ziel, zusatz)


def lade_profil(name: str) -> str:
    """Der Steckbrief einer Person. Fehlt die Datei, ist das ein
    Programmierfehler -- anders als bei den Bot-Prompts gibt es hier keinen
    sinnvollen Rueckfallweg: eine Stimme ohne Steckbrief waere eine weitere,
    unbeschriebene Person."""
    if name not in {b.schluessel for b in ALLE}:
        raise ValueError(f"unbekannter Steckbrief: {name!r}")
    return (VERZEICHNIS / f"{name}.md").read_text(encoding="utf-8").strip()


def personen(zufall: random.Random) -> list[Person]:
    """Die drei Personen eines Laufs -- feste Besetzung.

    ``zufall`` wird nicht mehr gebraucht, um Namen zu ziehen: die drei sind
    dieselben in jedem Lauf, weil sie Personen sind und nicht Wuerfe aus
    einem Pool. Der Seed variiert nur noch, **wer wann spricht**
    (``waehle_sprecher``). Der Parameter bleibt in der Signatur, damit
    Aufrufer sich nicht merken muessen, welche der beiden Funktionen ihn
    braucht."""
    return [aus_steckbrief(b) for b in BESETZUNG]


def waehle_sprecher(zufall: random.Random, alle: list[Person]) -> list[Person]:
    """Wer in diesem Zug schreibt: eine Person, mit
    ``P_ZWEITE_STIMME`` eine zweite (andere) direkt hinterher.

    Gezogen wird **gewichtet** (``Person.gewicht``): wer dem Computer am
    wenigsten traut, schreibt am seltensten. Eine Gruppe, in der alle drei
    gleich viel schreiben, gibt es nicht -- und ein Bot, der nur an einer
    solchen gemessen wird, sieht nie den Fall, dass eine Teilnehmerin seit
    zwanzig Nachrichten nichts gesagt hat.

    Zwei Nachrichten hintereinander sind kein Zierrat: sie sind der Fall, in
    dem ``ablauf.bearbeite`` sammelt statt zweimal zu antworten (SPEC § 1.3),
    und ohne sie bliebe genau dieser Pfad im Simulator unbetreten."""
    if not alle:
        return []
    erste = _ziehe(zufall, alle)
    if zufall.random() >= P_ZWEITE_STIMME:
        return [erste]
    uebrige = [p for p in alle if p.name != erste.name]
    return [erste, _ziehe(zufall, uebrige)] if uebrige else [erste]


def _ziehe(zufall: random.Random, kandidaten: list[Person]) -> Person:
    """Eine Person, gewichtet nach ``gewicht``. ``random.choices`` waere
    kuerzer, zieht aber aus einem anderen Teil des Zufallsstroms als
    ``random()`` und ``choice()`` -- eine handgeschriebene Ziehung haelt den
    Strom an einer Stelle und damit den Seed vergleichbar."""
    summe = sum(max(1, p.gewicht) for p in kandidaten)
    wurf = zufall.randrange(summe)
    laufend = 0
    for person in kandidaten:
        laufend += max(1, person.gewicht)
        if wurf < laufend:
            return person
    return kandidaten[-1]  # pragma: no cover -- nur bei Rundungsfehlern


def _verlaufszeile(eintrag: dict) -> str:
    """Eine Zeile des Chatverlaufs, wie eine Teilnehmerin sie auf dem Handy
    saehe: Absender und Text, mehr nicht."""
    return f"{eintrag['absender']}: {eintrag['text']}"


def baue_nutzertext(person: Person, verlauf: list[dict], ziel: str,
                    knoepfe: list[dict] | None = None) -> str:
    """Der Nutzertext einer Stimme: Rahmen, Chatverlauf, Schrittziel,
    Anweisung -- in dieser Reihenfolge.

    Das Ziel steht **nach** dem Verlauf und vor der Anweisung: was am Ende
    des Prompts steht, wiegt am schwersten (SPEC § 6.1), und das Ziel ist
    das einzige, was diesen Aufruf von jedem anderen unterscheidet.

    ``knoepfe`` sind die gerade antippbaren Knopftexte
    (``attrappe.offene_knoepfe``). Sie stehen **zwischen** Verlauf und Ziel:
    sie sind Teil dessen, was die Person auf dem Handy sieht, nicht Teil
    ihrer Absicht. Ohne sie misst die Simulation seit dem 06.09.2026 einen
    Weg, den eine echte Gruppe nicht mehr geht -- der Bot fuehrt ueber
    Inline-Knoepfe."""
    zeilen = [_RAHMEN, ""]
    letzte = verlauf[-VERLAUF_NACHRICHTEN:]
    if letzte:
        zeilen.append("Bisher im Chat:")
        zeilen.extend(_verlaufszeile(e) for e in letzte)
    else:
        zeilen.append("Der Chat ist noch leer, ihr fangt gerade an.")
    sichtbar = knopfliste(knoepfe or [])
    if sichtbar:
        zeilen += ["", _KNOPF_KOPF]
        zeilen += [f"- {t}" for t in sichtbar]
    if person.ziel:
        # Das eigene Ziel steht VOR dem Schrittziel: die Gruppe will das eine,
        # sie will daneben noch etwas anderes -- und genau an der Reibung
        # zwischen beidem zeigt sich, ob der Bot zuhoert oder abarbeitet.
        zeilen += ["", _ZIEL_PERSON, person.ziel]
    zeilen += ["", _ZIEL_KOPF, ziel.strip(), "", _ANWEISUNG.format(name=person.name)]
    if sichtbar:
        zeilen += ["", _KNOPF_ANWEISUNG.format(praefix=KNOPF_PRAEFIX)]
    return "\n".join(zeilen)


def saeubere(text: str, name: str) -> str:
    """Raeumt weg, was das Modell trotz Anweisung gern voranstellt: den
    eigenen Namen als Sprecherpraefix und Anfuehrungszeichen um die ganze
    Nachricht.

    Ohne das ginge beides in den Chat -- und die Kennzahl ``namensanrede``
    zaehlte anschliessend den Bot dafuer ab, dass er zurueckspiegelt, was die
    Simulation selbst hineingeschrieben hat."""
    nackt = (text or "").strip()
    praefix = f"{name}:"
    if nackt.lower().startswith(praefix.lower()):
        nackt = nackt[len(praefix):].lstrip()
    if len(nackt) >= 2 and nackt[0] in "\"'„»" and nackt[-1] in "\"'“«":
        nackt = nackt[1:-1].strip()
    return nackt


def lies_knopfwahl(text: str, knoepfe: list[dict]) -> dict | None:
    """Der Knopf, den die Stimme mit ``KNOPF: <Text>`` gemeint hat -- oder
    ``None``, wenn sie geschrieben statt gedrueckt hat.

    Verglichen wird der **Beschriftungstext**, klein geschrieben und
    getrimmt, erst exakt und dann als Teilstring: das Modell setzt gern einen
    Haken oder ein Anfuehrungszeichen dazu. Kein Treffer bedeutet
    ausdruecklich \"kein Knopf\" -- der Aufrufer schickt den Text dann als
    Nachricht, statt zu raten, welcher gemeint war."""
    zeile = (text or "").strip()
    if not zeile.upper().startswith(KNOPF_PRAEFIX):
        return None
    gesucht = zeile[len(KNOPF_PRAEFIX):].strip().strip('"\'„“»«').lower()
    if not gesucht:
        return None
    for knopf in knoepfe:
        if (knopf.get("beschriftung") or "").strip().lower() == gesucht:
            return knopf
    for knopf in knoepfe:
        beschriftung = (knopf.get("beschriftung") or "").strip().lower()
        if beschriftung and (beschriftung in gesucht or gesucht in beschriftung):
            return knopf
    return None


def sprich(sim, person: Person, verlauf: list[dict], ziel: str,
           knoepfe: list[dict] | None = None) -> str:
    """Laesst eine Stimme eine Nachricht schreiben und liefert deren Text.

    ``sim`` ist der Simulationsklient (``simulation/claude.py``), nicht der
    Bot-Klient: eine Teilnehmerin wird nicht von dem Modell gespielt, das
    gerade geprueft wird. Ein leeres Ergebnis liefert einen leeren String; der
    Aufrufer entscheidet, ob er den Schritt damit als gescheitert vermerkt
    (``lauf.py``).

    Beginnt das Ergebnis mit ``KNOPF:``, hat die Stimme einen Knopf gemeint --
    der Aufrufer loest ihn mit ``lies_knopfwahl`` auf. Diese Funktion gibt die
    Zeile unveraendert zurueck, damit die Entscheidung an genau einer Stelle
    faellt (``lauf._stimmen_zug``)."""
    text = sim.text(
        person.system, baue_nutzertext(person, verlauf, ziel, knoepfe), ART,
        max_tokens=MAX_TOKENS,
    )
    return saeubere(text, person.name)

"""Die simulierten Teilnehmerinnen: drei Sprachprofile, gespielt von Claude.

Drei Profile als System-Prompts (``simulation/stimmen/*.md``) --
**knapp**, **ausschweifend**, **skeptisch**. Ein Lauf hat drei Personen, eine
je Profil; je Schritt spricht eine, gelegentlich zwei hintereinander
(``waehle_sprecher``, aus dem Seed).

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

#: Wo die drei Profildateien liegen. Gleichnamiges Verzeichnis neben diesem
#: Modul: Python findet erst dieses Modul und dann erst das Verzeichnis, ein
#: Namenskonflikt entsteht nicht (``simulation/stimmen/`` hat kein
#: ``__init__.py`` und ist deshalb keine Paketkonkurrenz).
VERZEICHNIS = Path(__file__).resolve().parent / "stimmen"

#: Die drei Profile in fester Reihenfolge -- sie ist die Reihenfolge, in der
#: die Personen eines Laufs angelegt werden, und damit reproduzierbar.
PROFILE = ("knapp", "ausschweifend", "skeptisch")

#: So viele Nachrichten des Chatverlaufs bekommt eine Stimme zu sehen.
VERLAUF_NACHRICHTEN = 30

#: Namenspool je Profil. Drei Namen je Profil, damit zwei Laeufe mit
#: verschiedenen Seeds verschieden klingen, ohne dass die Zuordnung
#: Person -> Profil je Lauf raten muesste.
NAMEN = {
    "knapp": ("Jo", "Sanja", "Merle"),
    "ausschweifend": ("Marlen", "Doro", "Bettina"),
    "skeptisch": ("Ines", "Hatice", "Ruth"),
}

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


@dataclass(frozen=True)
class Person:
    """Eine simulierte Teilnehmerin: Name und Sprachprofil."""

    name: str
    profil: str

    @property
    def system(self) -> str:
        return lade_profil(self.profil)


def lade_profil(name: str) -> str:
    """Der System-Prompt eines Sprachprofils. Fehlt die Datei, ist das ein
    Programmierfehler -- anders als bei den Bot-Prompts gibt es hier keinen
    sinnvollen Rueckfallweg: eine Stimme ohne Profil waere ein viertes,
    unbeschriebenes Verhalten."""
    if name not in PROFILE:
        raise ValueError(f"unbekanntes Sprachprofil: {name!r}")
    return (VERZEICHNIS / f"{name}.md").read_text(encoding="utf-8").strip()


def personen(zufall: random.Random) -> list[Person]:
    """Die drei Personen eines Laufs, eine je Profil, mit Namen aus dem Pool.

    Reihenfolge und Namenswahl haengen allein am uebergebenen ``Random`` --
    derselbe Seed ergibt dieselbe Besetzung."""
    return [Person(zufall.choice(NAMEN[profil]), profil) for profil in PROFILE]


def waehle_sprecher(zufall: random.Random, alle: list[Person]) -> list[Person]:
    """Wer in diesem Zug schreibt: eine Person, mit
    ``P_ZWEITE_STIMME`` eine zweite (andere) direkt hinterher.

    Zwei Nachrichten hintereinander sind kein Zierrat: sie sind der Fall, in
    dem ``ablauf.bearbeite`` sammelt statt zweimal zu antworten (SPEC § 1.3),
    und ohne sie bliebe genau dieser Pfad im Simulator unbetreten."""
    erste = zufall.choice(alle)
    if zufall.random() >= P_ZWEITE_STIMME:
        return [erste]
    uebrige = [p for p in alle if p.name != erste.name]
    return [erste, zufall.choice(uebrige)] if uebrige else [erste]


def _verlaufszeile(eintrag: dict) -> str:
    """Eine Zeile des Chatverlaufs, wie eine Teilnehmerin sie auf dem Handy
    saehe: Absender und Text, mehr nicht."""
    return f"{eintrag['absender']}: {eintrag['text']}"


def baue_nutzertext(person: Person, verlauf: list[dict], ziel: str) -> str:
    """Der Nutzertext einer Stimme: Rahmen, Chatverlauf, Schrittziel,
    Anweisung -- in dieser Reihenfolge.

    Das Ziel steht **nach** dem Verlauf und vor der Anweisung: was am Ende
    des Prompts steht, wiegt am schwersten (SPEC § 6.1), und das Ziel ist
    das einzige, was diesen Aufruf von jedem anderen unterscheidet."""
    zeilen = [_RAHMEN, ""]
    letzte = verlauf[-VERLAUF_NACHRICHTEN:]
    if letzte:
        zeilen.append("Bisher im Chat:")
        zeilen.extend(_verlaufszeile(e) for e in letzte)
    else:
        zeilen.append("Der Chat ist noch leer, ihr fangt gerade an.")
    zeilen += ["", _ZIEL_KOPF, ziel.strip(), "", _ANWEISUNG.format(name=person.name)]
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


def sprich(sim, person: Person, verlauf: list[dict], ziel: str) -> str:
    """Laesst eine Stimme eine Nachricht schreiben und liefert deren Text.

    ``sim`` ist der Simulationsklient (``simulation/claude.py``), nicht der
    Bot-Klient: eine Teilnehmerin wird nicht von dem Modell gespielt, das
    gerade geprueft wird. Ein leeres Ergebnis liefert einen leeren String; der
    Aufrufer entscheidet, ob er den Schritt damit als gescheitert vermerkt
    (``lauf.py``)."""
    text = sim.text(
        person.system, baue_nutzertext(person, verlauf, ziel), ART,
        max_tokens=MAX_TOKENS,
    )
    return saeubere(text, person.name)

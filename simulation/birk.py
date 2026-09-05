"""``--set birk``: der Probelauf vom 04.09.2026 als Messlatte.

**Das einzige Set auf echten Daten.** Die drei erfundenen Sets messen den Bot
an Material, das eigens dafuer geschrieben wurde -- fuenf saubere Interviews,
drei Teilnehmerinnen, die kooperieren, weil sie dafuer gebaut sind. Dieses Set
misst ihn an dem, was am 04.09. wirklich passiert ist: ein duennes Interview
(drei kurze Antworten), eine einzelne Person, die knapp und ungeduldig
schreibt, und ein Chatverlauf, an dem sich ablesen laesst, wie viele
Nachrichten der Bot damals gebraucht hat.

**Gemessen wird die Navigation, nicht der Text.** Das Interview gibt nicht
genug her, als dass ein Szenentext daraus eine Aussage waere. Was zaehlt: Wie
natuerlich fuehrt der Bot durch die Phasen, wenn eine echte Person so
schreibt wie Birk? Deshalb steht im Bericht neben jeder Zahl der Simulation
die Zahl aus dem echten Chat (``referenz``): so viele Nachrichten hat der Bot
damals gebraucht, so viele Rueckfragen gestellt, so oft "notiert" gesagt,
ohne dass etwas notiert wurde. Soll: nicht mehr als damals.

**Das Material liegt ausserhalb des Repositories.** Es sind echte Daten einer
echten Person -- sie gehoeren nicht in ein Git, das spaeter jemand anders
liest. Der Pfad steht in ``VERZEICHNIS`` und laesst sich mit ``IT_SIM_BIRK``
umbiegen; fehlt er, liefern die Funktionen hier ``None`` bzw. leere Werte und
``--set birk`` bricht mit einer verstaendlichen Meldung ab, statt auf halbem
Weg umzufallen.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from interview_theater import ablauf, zitat

from simulation import material, stimmen

#: Wo das Material des Probelaufs liegt. Ueberschreibbar mit ``IT_SIM_BIRK``.
VERZEICHNIS_VORGABE = Path(
    "/mnt/HC_Volume_106183673/projekte/interview-theater-material/birk-test"
)

#: Kennung des Interviews -- zugleich der Name, unter dem es im Bericht und
#: in den Dateinamen der Laeufe auftaucht.
KENNUNG = "interview-birk"

#: Wie das Interview im Workshop heisst. Kurz, nicht der Titel aus dem Kopf
#: ("Birk-Testinterview 04.09.2026"): der Name geht als ``aufnahme.name`` in
#: die Datenbank und steht danach in jeder Verdichtungszeile im Prompt.
INTERVIEW_NAME = "Birk"

#: Wie der Lauf heisst (``--set birk``, ``mischungsname``).
NAME = "birk"

#: In wie vielen Textimporten das eine Interview hereinkommt. Drei, weil es im
#: Original drei Antworten auf drei Fragen sind -- und weil genau daran
#: gemessen wird, ob der Bot aus drei Importen EINE Verdichtung macht
#: (§ 10.6) statt drei.
TEILE = 3

#: Die drei Saetze, die ein guter Verdichter aus diesem Interview finden muss.
#: Von Hand ausgesucht und beim Laden gegen den Text geprueft
#: (``_pruefe_zitate``): sie stehen woertlich darin, und wenn jemand das
#: Material austauscht, faellt das sofort auf statt erst im Bericht als Null.
ZITATE_SOLL = (
    "Also am liebsten mache ich Pfannkuchen, Palatschinken, so mit Schokolade und Banane.",
    "Das war so eine Punkerin, die ich im autonomen Zentrum kennengelernt hab, mit Piercings.",
    "Naja, also da denke ich an Strand und Palmen und Pinacolada.",
)

#: Woran man die Sprechweise erkennt -- fuer den Kopf des Interviews, damit es
#: dieselbe Form hat wie die fuenfzehn erfundenen.
SPRACHMERKMALE = ("Abbrueche", "Fuellwoerter", "weicht der Frage zuerst aus")

#: Das Kernthema, auf das die Gruppe im Probelauf gekommen ist. **Sollwert
#: zum Vergleich, keine Vorgabe**: es steht im Bericht neben dem, was der Bot
#: diesmal vorgeschlagen hat, und geht nirgends in den Prompt.
KERNTHEMA_DAMALS = (
    "Woher kommen die Bilder in uns – und merken wir noch, dass sie nicht von "
    "uns sind?"
)

#: Die drei Figurennamen aus dem Probelauf -- ebenfalls nur Vergleichswert.
FIGUREN_DAMALS = ("Mira", "Pola", "Pal")


def verzeichnis() -> Path:
    wert = os.environ.get("IT_SIM_BIRK")
    return Path(wert) if wert else VERZEICHNIS_VORGABE


def interviewdatei() -> Path:
    return verzeichnis() / "interview-birk.md"


def chatdatei() -> Path:
    return verzeichnis() / "chat-04-09.json"


def vorhanden() -> bool:
    """Ob das Material da ist. Der Chatverlauf ist optional -- ohne ihn laeuft
    ``--set birk`` weiter, nur ohne Referenzspalte und mit einer Stimme, die
    sich allein auf ihren Steckbrief stuetzt."""
    return interviewdatei().is_file()


# ---------------------------------------------------------------------------
# Das Interview
# ---------------------------------------------------------------------------


def _lies_kopf(roh: str) -> tuple[dict, str]:
    """Der Frontmatter-Kopf dieser einen Datei.

    Ein eigener Parser statt ``material._lies_kopf``: dieser Kopf traegt
    andere Felder (``fragen``, ``begriffe``, ``quelle``) und eine andere
    Listenform (``- "..."``-Zeilen mit Anfuehrungszeichen), weil er nicht aus
    dem Generator kommt, sondern aus dem Betrieb."""
    zeilen = roh.splitlines()
    if not zeilen or zeilen[0].strip() != "---":
        raise ValueError(f"{interviewdatei()}: kein Kopf")
    ende = next(i for i, z in enumerate(zeilen[1:], 1) if z.strip() == "---")

    kopf: dict = {}
    offen = None
    for zeile in zeilen[1:ende]:
        if not zeile.strip():
            continue
        if zeile.lstrip().startswith("- ") and offen:
            kopf[offen].append(zeile.lstrip()[2:].strip().strip('"\''))
            continue
        schluessel, _, wert = zeile.partition(":")
        schluessel = schluessel.strip()
        if wert.strip():
            kopf[schluessel] = wert.strip().strip('"\'')
            offen = None
        else:
            kopf[schluessel] = []
            offen = schluessel
    return kopf, "\n".join(zeilen[ende + 1:]).strip()


def _begriffsliste(kopf: dict) -> list[str]:
    return [b.strip() for b in str(kopf.get("begriffe", "")).split(",") if b.strip()]


def _pruefe_zitate(transkript: str) -> None:
    """Die drei Soll-Zitate gegen den Text -- mit ``zitat.pruefe``, derselben
    Funktion, die im Betrieb ueber ein Belegzitat entscheidet. Ein Zitat, das
    hier nicht steht, waere im Bericht eine Null, die niemand erklaeren
    kann."""
    fehlend = [z for z in ZITATE_SOLL if not zitat.pruefe(z, transkript)]
    if fehlend:
        raise ValueError(
            f"{interviewdatei()}: diese Soll-Zitate stehen nicht mehr im "
            f"Transkript: {fehlend}"
        )


def lade() -> material.Interview:
    """Das Testinterview als ``material.Interview`` -- dieselbe Form wie die
    fuenfzehn erfundenen, damit der ganze Lauf nichts von diesem Sonderfall
    wissen muss.

    ``nummer=0``: es gehoert zu keinem der drei Sets. Die Zahl wird nur fuer
    die Kopfzeile des Berichts gebraucht, nirgends fuer eine Auswahl."""
    kopf, transkript = _lies_kopf(interviewdatei().read_text(encoding="utf-8"))
    _pruefe_zitate(transkript)
    return material.Interview(
        kennung=KENNUNG,
        name=INTERVIEW_NAME,
        nummer=0,
        themen=tuple(_begriffsliste(kopf)),
        sprachmerkmale=SPRACHMERKMALE,
        zitate_soll=ZITATE_SOLL,
        transkript=transkript,
    )


def fragen() -> list[str]:
    """Die drei Interviewfragen aus dem Kopf -- sie sind das Ziel des
    Fragen-Schritts, nicht eine Erfindung des Simulators."""
    kopf, _ = _lies_kopf(interviewdatei().read_text(encoding="utf-8"))
    return list(kopf.get("fragen") or [])


def begriffe() -> list[str]:
    kopf, _ = _lies_kopf(interviewdatei().read_text(encoding="utf-8"))
    return _begriffsliste(kopf)


# ---------------------------------------------------------------------------
# Der echte Chatverlauf: Stil-Referenz und Messlatte
# ---------------------------------------------------------------------------


def chat() -> list[dict]:
    """Die 100 Nachrichten des Probelaufs, aelteste zuerst. Leere Liste, wenn
    die Datei fehlt."""
    if not chatdatei().is_file():
        return []
    daten = json.loads(chatdatei().read_text(encoding="utf-8"))
    return list(daten.get("nachrichten") or [])


#: So viele echte Nachrichten gehen als Stil-Referenz in den System-Prompt.
#: Alle, die von Birk stammen -- die Bot-Antworten braucht die Stimme nicht,
#: sie stuenden ihr nur im Weg.
STIL_KOPF = (
    "Zur Kalibrierung: so hast du im echten Probelauf am 04.09. geschrieben. "
    "Nicht abschreiben -- so klingen."
)


def stil_referenz() -> str:
    """Birks eigene Nachrichten aus dem echten Chat, als Block fuer den
    System-Prompt seiner Stimme.

    Nur seine, nicht die des Bots: die Stimme soll lernen, wie **er**
    schreibt. Leerer String, wenn der Chat fehlt -- dann traegt der Steckbrief
    allein, und der Lauf sagt im Bericht, dass die Kalibrierung fehlte."""
    meine = [
        (n.get("text") or "").strip() for n in chat()
        if not n.get("ist_bot") and (n.get("text") or "").strip()
    ]
    if not meine:
        return ""
    return STIL_KOPF + "\n" + "\n".join(f"- {t}" for t in meine)


def person() -> stimmen.Person:
    """Die eine Stimme dieses Laufs: Steckbrief plus Stil-Referenz."""
    return stimmen.aus_steckbrief(stimmen.BIRK, zusatz=stil_referenz())


# ---------------------------------------------------------------------------
# Die Referenzzahlen aus dem echten Chat -- mechanisch, kein Modell
# ---------------------------------------------------------------------------

#: Woran eine Notiert-Zeile im echten Chat erkennbar ist. Die Zeilen des
#: Erkenners sind die Trennmarken zwischen den Arbeitsschritten: was zwischen
#: zwei von ihnen liegt, hat die Gruppe gebraucht, um eine Festlegung
#: durchzubekommen.
_NOTIERT = "Notiert:"

def _ist_notiert(text: str) -> bool:
    return text.strip().startswith(_NOTIERT)


#: Die Zahlen, die **Birk selbst** am 05.09. aus dem Chat gelesen hat: vier
#: Rueckfragen, ein Echo, fuenf unbelegte "notiert"-Behauptungen.
#:
#: Sie stehen hier als Konstante und nicht als Rechenergebnis, weil sie eine
#: Handzaehlung sind: was er als "Rueckfrage" gezaehlt hat, ist ein Urteil
#: ("hier haette der Bot einfach machen sollen"), und keine mechanische Regel
#: trifft es. ``referenz()`` rechnet daneben mit einer nachlesbaren Definition
#: -- der Bericht zeigt beide Spalten und sagt, welche woher kommt. Eine Zahl
#: hinzubiegen, bis sie 4 ergibt, waere das Gegenteil einer Messung.
HANDZAEHLUNG = {"rueckfragen": 4, "echo": 1, "behauptete_schreibvorgaenge": 5}


def referenz() -> dict:
    """Die Messlatte aus dem echten Chat -- rein mechanisch, kein Modell.

    * ``nachrichten_je_abschnitt``: wie viele Nachrichten Birk zwischen zwei
      Notiert-Zeilen gebraucht hat. Die Notiert-Zeilen sind die Trennmarken
      zwischen den Arbeitsschritten: was dazwischen liegt, hat die Gruppe
      gebraucht, um eine Festlegung durchzubekommen. Das ist die Zahl, gegen
      die im Bericht steht, was der Simulator gebraucht hat.
    * ``rueckfragen``: Bot-Nachrichten, die auf ein Fragezeichen enden --
      also nicht liefern, sondern zurueckfragen. Fragezeichen irgendwo im
      Text zaehlt nicht: der Bot darf mitten in einer Antwort eine Frage
      stellen, das ist ein Gespraech.
    * ``echo``: geprueft mit ``ablauf.ist_echo``, genau der Funktion, die im
      Betrieb entscheidet -- sonst waere die Spalte "echt" mit einer anderen
      Elle gemessen als die Spalte "Simulation".
    * ``behauptete_schreibvorgaenge``: Bot sagt "notiert"/"korrigiert"/"im
      Arbeitsstand", ohne dass es eine Notiert-Zeile des Erkenners war.

    Leeres Dict, wenn der Chat fehlt -- der Bericht schreibt dann "keine
    Referenz" statt einer erfundenen Null."""
    from simulation import kennzahlen  # spaet: kennzahlen importiert skript

    nachrichten = chat()
    if not nachrichten:
        return {}

    abschnitte: list[int] = []
    laufend = 0
    rueckfragen = echo = behauptet = 0
    vorherige: list[dict] = []

    for n in nachrichten:
        text = (n.get("text") or "").strip()
        if not n.get("ist_bot"):
            laufend += 1
            vorherige.append({"ist_bot": 0, "text": text})
            continue

        if _ist_notiert(text):
            abschnitte.append(laufend)
            laufend = 0
            vorherige = []
            continue

        if text.endswith("?"):
            rueckfragen += 1
        if ablauf.ist_echo(text, vorherige):
            echo += 1
        gefaltet = kennzahlen._falte(text)
        if any(w in gefaltet for w in kennzahlen.SCHREIB_BEHAUPTUNGEN):
            behauptet += 1

    if laufend:
        abschnitte.append(laufend)

    return {
        "nachrichten_je_abschnitt": abschnitte,
        "nachrichten_gesamt": sum(1 for n in nachrichten if not n.get("ist_bot")),
        "abschnitte": len(abschnitte),
        "rueckfragen": rueckfragen,
        "echo": echo,
        "behauptete_schreibvorgaenge": behauptet,
        "kernthema": KERNTHEMA_DAMALS,
        "figuren": list(FIGUREN_DAMALS),
        "handzaehlung": dict(HANDZAEHLUNG),
    }

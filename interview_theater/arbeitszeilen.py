"""Die Arbeitszeilen: was im Chat steht, waehrend der Bot arbeitet
(06.09.2026, Birk 11:15/12:05/12:08/12:10).

**Warum es das gibt.** Ein Modellaufruf dauert zwischen zehn Sekunden und
vier Minuten. Bis zum 06.09.2026 gab es dafuer zwei verschiedene Loesungen:
eine einmalige Zeile im Handler (``ablauf.arbeitet_sichtbar``) und eine
wechselnde Emoji-Zeile im Szenenlauf (``szene._arbeitet_sichtbar``). Beide
sind hier zu EINER Funktion zusammengefasst -- ``sichtbar()`` --, und beide
Anlaesse gelten jetzt ueberall: **sofort** (unter einer Sekunde, aus dem
Handler heraus) die erste Zeile, danach alle ``TAKT_S`` eine neue, am Ende
alles wieder geloescht.

**Die Texte kommen aus der Welt des Stuecks**, nicht aus dem Kino: Urban
Dance Theater -- Probeflaeche, Bewegung, Beat, Chor, Platz. Kein Vorhang,
keine Kamera, kein Film: die Gruppe baut ein Stueck fuer einen oeffentlichen
Platz, und eine Zeile, die von Leinwand spricht, verschiebt das Bild.

Zufaellig, aber **ohne Wiederholung im Lauf**: dieselbe Zeile zweimal
hintereinander sieht aus wie ein haengender Prozess -- genau das, was die
Zeile verhindern soll.
"""

from __future__ import annotations

import logging
import random
import threading

log = logging.getLogger(__name__)

#: Wie lange eine Zeile stehen bleibt, bevor die naechste sie ersetzt.
TAKT_S = 15.0
#: Wie oft die Tippanzeige nachgeschickt wird (Telegram loescht sie nach
#: rund fuenf Sekunden von selbst).
TIPP_S = 4.0

#: Je Auftragsart eine Liste. Der Name ist der, unter dem der Aufruf im
#: ``aufruf``-Protokoll steht, damit niemand ein zweites Vokabular pflegen
#: muss.
ZEILEN: dict[str, tuple[str, ...]] = {
    "geschichte": (
        "🎭 lege drei Boegen auf die Probeflaeche …",
        "🔁 lasse die Geschichte einmal im Kopf durchlaufen …",
        "🔚 suche ein Ende, das noch nachhallt …",
    ),
    "prosa": (
        "✍️ schreibe, streiche, schreibe nochmal …",
        "👟 schaue den Figuren bei der Probe zu …",
        "☕ kurze Pause am Rand der Probeflaeche …",
        "📐 messe, ob der erste Auftritt schon zieht …",
    ),
    "schaerfung": (
        "🔍 suche in euren Interviews nach Saetzen, die auf die Buehne wollen …",
        "🧩 lege Zitate an die Figuren …",
    ),
    "stueckpruefung": (
        "🎭 stelle mich an den Rand des Platzes und schaue zu …",
        "📊 zaehle, wo die Spannung haengt …",
        "🔦 leuchte die Uebergaenge zwischen den Szenen aus …",
    ),
    "feinschliff": (
        "🎶 hoere, ob das nach Rap, Lied oder Chor klingt …",
        "🥁 suche den Beat unter den Repliken …",
        "🗣️ spreche die Repliken einmal laut …",
    ),
    "sensibilitaet": (
        "🤔 lese die Fragen nochmal mit fremden Augen …",
        "🫶 pruefe, wo jemand vorsichtig gefragt werden will …",
    ),
    "eroeffnung": (
        "🎤 uebe den ersten Satz vor dem Spiegel …",
    ),
    "sprachstil": (
        "🗣️ hoere, wie sie klingt, wenn sie loslegt …",
        "👂 vergleiche zwei Sprechweisen nebeneinander …",
    ),
}

#: Wenn eine Art keine eigene Liste hat. Bewusst kurz: eine allgemeine Zeile
#: soll nicht so tun, als wuesste sie, was gerade laeuft.
VORGABE = (
    "🎭 arbeite an eurem Stueck …",
    "👟 gehe die Szene einmal auf der Probeflaeche durch …",
)

#: Woerter, die in keiner Arbeitszeile vorkommen duerfen (Birk, 12:08): das
#: Stueck ist Theater auf einem Platz, kein Film. Der Test liest diese Liste.
VERBOTEN = ("kino", "film", "vorhang", "kamera", "leinwand", "dreh")


def liste(art: str | None) -> tuple[str, ...]:
    """Die Zeilen zu einer Auftragsart -- oder die allgemeinen."""
    return ZEILEN.get((art or "").strip().lower(), VORGABE)


def _reihenfolge(art: str | None) -> list[str]:
    """Die Zeilen dieser Art in zufaelliger Reihenfolge, jede genau einmal.

    Erst wenn alle durch sind, wird neu gemischt: **keine Wiederholung im
    Lauf**, solange es noch ungenutzte Zeilen gibt."""
    zeilen = list(liste(art))
    random.shuffle(zeilen)
    return zeilen


class Lauf:
    """Eine laufende Arbeitszeile. ``starte()`` schickt SOFORT die erste
    Zeile (im Handler, ohne Thread-Wartezeit) und laesst danach einen
    Daemon-Thread wechseln; ``stoppe()`` raeumt auf.

    Alle Fehler sind still und werden nur geloggt: das ist Schmuck, kein
    Betriebspfad -- eine gescheiterte Zeile darf nie einen Auftrag
    mitreissen."""

    def __init__(self, tg, chat_id: int, art: str | None = None):
        self._tg = tg
        self._chat_id = chat_id
        self._art = art
        self._stopp = threading.Event()
        self._thread: threading.Thread | None = None
        self._message_id: int | None = None
        self._offen: list[str] = []

    def _naechste(self) -> str:
        if not self._offen:
            self._offen = _reihenfolge(self._art)
        return self._offen.pop(0)

    def starte(self) -> None:
        try:
            self._tg.tippt(self._chat_id)
        except Exception:
            log.debug("Tippanzeige fehlgeschlagen, chat_id=%s", self._chat_id)
        try:
            self._message_id = self._tg.sende(self._chat_id, self._naechste())
        except Exception:
            log.exception("Arbeitszeile fehlgeschlagen, chat_id=%s", self._chat_id)
            self._message_id = None
        self._thread = threading.Thread(target=self._lauf, daemon=True)
        self._thread.start()

    def _lauf(self) -> None:
        seit = 0.0
        while not self._stopp.wait(TIPP_S):
            try:
                self._tg.tippt(self._chat_id)
            except Exception:
                pass
            seit += TIPP_S
            if seit < TAKT_S:
                continue
            seit = 0.0
            text = self._naechste()
            try:
                if self._message_id is not None:
                    # Ersetzen statt neu schicken (Birk, 12:05): sonst
                    # waechst der Chat waehrend eines Szenenlaufs um zehn
                    # Zeilen, die niemand lesen will.
                    self._tg.aendere_text(self._chat_id, self._message_id, text)
                else:
                    self._message_id = self._tg.sende(self._chat_id, text)
            except Exception:
                log.debug("Arbeitszeile nicht gewechselt, chat_id=%s", self._chat_id)

    def stoppe(self) -> None:
        self._stopp.set()
        if self._thread is not None:
            self._thread.join(timeout=TIPP_S + 1.0)
        if self._message_id is None:
            return
        try:
            self._tg.loesche_nachrichten(self._chat_id, [self._message_id])
        except Exception:
            log.debug("Arbeitszeile nicht geloescht, chat_id=%s", self._chat_id)
        self._message_id = None


def sichtbar(tg, chat_id: int, art: str | None = None) -> Lauf:
    """Startet einen ``Lauf`` und gibt ihn zurueck -- der Aufrufer ruft
    ``stoppe()``, ueblicherweise in einem ``finally``.

    Fuer ``with``-Bloecke gibt es ``ablauf.arbeitet_sichtbar``, das dieselbe
    Klasse benutzt."""
    lauf = Lauf(tg, chat_id, art)
    lauf.starte()
    return lauf

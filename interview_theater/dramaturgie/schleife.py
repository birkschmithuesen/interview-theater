"""Schicht 4b: die Rueckkopplung -- pruefen, ueberarbeiten, wieder pruefen.

``fanout.pruefe`` findet Befunde, ``fanout.auftraege`` macht daraus
Ueberarbeitungsauftraege -- und dann hoerte es auf. Dieses Modul ist das
Verbindungsstueck: es fuehrt die Auftraege ueber den **bestehenden**
Schreibpfad aus, prueft danach noch einmal und misst mit
``bilanz``, ob die Ueberarbeitung wirklich geholfen hat.

## Drei Abbruchbedingungen, und jede hat einen eigenen Grund

* **Keine Auftraege mehr** (``GRUND_KEINE_AUFTRAEGE``) -- der Regelfall. Der
  Text traegt keinen harten Befund mehr, an dem sich eine Anweisung
  formulieren liesse.
* **Die Ueberarbeitung hat geschadet** (``GRUND_GESCHADET``) -- ein Score ist
  gefallen. Dann wird nicht weitergedreht: die naechste Runde bekaeme einen
  Text als Ausgangslage, der an einer Stelle schon schlechter ist, und der
  Schaden waere nach zwei weiteren Laeufen nicht mehr zuzuordnen.
* **Das Rundenlimit** (``RUNDEN_MAX``) -- der Auffangfall, wenn die beiden
  anderen nicht greifen.

## Was diese Schicht NICHT tut

**Sie uebernimmt nichts.** Der Bot schlaegt vor, die Gruppe bestaetigt --
dieselbe Haltung wie ueberall (``knoepfe.zeige_dramaturgie``: *"erst der
Knopfdruck loest einen Szenenlauf aus"*). Die Schleife laeuft deshalb nicht
von selbst und haengt an keinem Knopf; sie wird vom Betreiber gegen eine
**Kopie**-Datenbank gefahren (``scripts/dramaturgie_pruefen.py --schleife``),
und was dabei herauskommt, ist ein Vorschlag samt Bilanz. Der Weg endet hier.

**Sie umgeht keine der drei Grenzen aus Schicht 1-3:**

* Ein Parameterbefund (``richtung=parameter``) erzeugt nie einen
  Schreibauftrag. Die Sperre sitzt in ``fanout.auftraege``, und diese Schicht
  ruft genau diese Funktion -- sie baut keine eigene Auftragsliste.
* Ein Befund ohne verifiziertes Belegzitat steuert keinen Schreiber; auch das
  entscheidet ``fanout.auftraege`` ueber ``beleg.darf_an_den_schreiber``.
* Ein verworfener Score geht nicht in die Bilanz (``fanout._merke``).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field

from interview_theater import repo
from interview_theater.dramaturgie import bilanz as bilanz_modul
from interview_theater.dramaturgie import fanout

log = logging.getLogger(__name__)

#: Hoechstens so viele **Ueberarbeitungsrunden** je Lauf -- also hoechstens
#: drei Pruefungen (pruefen, ueberarbeiten, pruefen, ueberarbeiten, pruefen).
#:
#: **Warum zwei.** Nicht, weil zwei Runden reichen wuerden, sondern weil die
#: dritte mehr riskiert, als sie einbringt:
#:
#: 1. Jede Runde kostet einen vollen Fan-out (bei acht Szenen rund achtzehn
#:    Modellaufrufe, Recherche § 3) **plus** einen Schreiblauf je Auftrag --
#:    und der Schreiblauf ist der teuerste Aufruf des ganzen Systems
#:    (``szene.MAX_TOKENS``). Die Gruppe steht dabei im Raum und wartet.
#: 2. Jede Ueberarbeitung ist ein neuer Modelllauf, der auch etwas kaputt
#:    machen kann -- genau dafuer gibt es ``bilanz``. Mehr Runden heisst mehr
#:    Gelegenheiten dazu, und der Schaden aus Runde 4 laesst sich Runde 1
#:    nicht mehr zuordnen.
#: 3. Eine Schleife, die lange genug laeuft, konvergiert auf den Richter und
#:    nicht auf das Stueck der Gruppe. Zwei Runden sind ein Vorschlag; fuenf
#:    waeren ein automatisches Umschreiben, und das ist genau das, was dieses
#:    Repo an jeder anderen Stelle nicht tut.
#:
#: Die beiden anderen Abbruchbedingungen greifen im Regelfall frueher. Diese
#: hier ist der Auffangfall, nicht der Normalweg.
RUNDEN_MAX = 2

GRUND_KEINE_AUFTRAEGE = "keine_auftraege"
GRUND_GESCHADET = "geschadet"
GRUND_RUNDENLIMIT = "rundenlimit"
GRUND_OHNE_SCHREIBWEG = "ohne_schreibweg"

#: Was zu jedem Abbruchgrund im Bericht steht -- ein Satz, kein Kuerzel.
GRUENDE = {
    GRUND_KEINE_AUFTRAEGE: "Keine Ueberarbeitungsauftraege mehr.",
    GRUND_GESCHADET: (
        "Ein Score ist gefallen - die Ueberarbeitung hat geschadet, "
        "die Schleife bricht ab."
    ),
    GRUND_RUNDENLIMIT: f"Rundenlimit erreicht ({RUNDEN_MAX}).",
    GRUND_OHNE_SCHREIBWEG: "Kein Schreibweg fuer diese Phase.",
}

#: Vorfall, wenn eine Ueberarbeitung einen Score gesenkt hat. Er steht neben
#: der Bilanz und nicht statt ihrer: "gekuerzt" und "reicht nicht" sind zwei
#: verschiedene Meldungen (AGENTS.md, ``kontext_kuerzung_erfolglos``).
VORFALL_GESCHADET = "dramaturgie_verschlechterung"


class SchreibwegFehlt(Exception):
    """Fuer diese Phase gibt es hier keinen Schreibweg -- mit einem Satz, was
    fehlt. **Kein Rueckfall auf den anderen Weg**: gemessen am 06.09.2026
    liefert der phasenfremde Pfad deutlich schwaechere Texte, und ein still
    genommener falscher Weg waere schlimmer als eine Meldung (dieselbe Haltung
    wie ``szene.sperrtext``)."""


# ---------------------------------------------------------------------------
# Der Schreibweg: der, der zur Phase passt
# ---------------------------------------------------------------------------

#: Das Modul, das in der Prosa-Phase EINEN Lauf ueber die ganze Geschichte
#: macht, und die **synchrone** Funktion darin, die diese Schleife braucht.
#: Als Name und nicht als Import: es haengt an einem anderen Zweig als dieser
#: hier, und ein harter Import wuerde das ganze Paket unimportierbar machen.
GESCHICHTE_MODUL = "interview_theater.kurzgeschichte"
GESCHICHTE_FUNKTION = "schreibe"

MELDUNG_OHNE_GESCHICHTENWEG = (
    "In dieser Phase entsteht die Geschichte in EINEM Lauf ueber das ganze "
    f"Stueck; dafuer braucht die Schleife {GESCHICHTE_MODUL}."
    f"{GESCHICHTE_FUNKTION}() als synchronen Aufruf. Den gibt es hier nicht - "
    "je Szene zu schreiben waere der Weg der naechsten Phase und liefert "
    "gemessen schwaechere Texte. Deshalb kein Modellaufruf."
)


def prosa_phase(conn, chat_id: int) -> bool:
    """Schreibt diese Phase eine Geschichte oder einen Theatertext?

    Gelesen wird ``szene.schreibt_prosa`` -- **die** eine Stelle, an der die
    Verzweigung haengt (Systemanweisung, Zielspalte und Vorlage lesen sie
    ebenfalls dort ab). Eine zweite Phasenabfrage hier waere ein zweiter Ort
    fuer dieselbe Entscheidung."""
    from interview_theater import szene

    return szene.schreibt_prosa(conn, chat_id)


def _schreibe_je_szene(conn, tg, klm, e, chat_id: int, auftraege) -> list[int]:
    """Der Weg des Feinschliffs: ein Szenenlauf je Auftrag.

    ``szene.schreibe`` ist synchron und dafuer vorgesehen ("wer sie direkt
    aufruft (Tests, ein kuenftiger Stapellauf), bekommt sie synchron und muss
    sich selbst um die Sperre kuemmern"). Die Sperre je ``chat_id`` wird
    deshalb hier genommen -- ohne sie liefe ein Knopfdruck der Gruppe mitten
    in die Schleife hinein.

    **Die Sperre aus ``szene.sperrtext`` gilt auch hier.** ``schreibe()``
    selbst prueft sie nicht (das tut sonst ``starte()``), und ein Szenenlauf
    ohne Ort und Besetzung erfindet welche -- genau der Probelauf, wegen dem
    es die Sperre gibt. Ein Auftrag, dem etwas fehlt, wird uebersprungen und
    geloggt, nicht blind gefahren."""
    from interview_theater import szene

    geschrieben: list[int] = []
    sperre = szene._sperre_fuer(chat_id)
    with sperre:
        for auftrag in auftraege:
            text = fanout.szenenauftrag(auftrag)
            ziel = szene.ziel_fuer(conn, chat_id, text)
            fehlt = szene.sperrtext(conn, ziel)
            if fehlt:
                log.info(
                    "Schleife ueberspringt Szene %s, chat_id=%s: %s",
                    auftrag.get("szene"), chat_id, fehlt,
                )
                continue
            geschrieben.append(szene.schreibe(conn, tg, klm, e, chat_id, text))
    return geschrieben


def _regie_fuer_die_geschichte(auftraege) -> str:
    """Alle Auftraege als EINE Regie-Notiz.

    In der Prosa-Phase gibt es einen Lauf ueber das ganze Stueck und also auch
    nur eine Notiz. Sie behaelt die Reihenfolge aus ``fanout.auftraege``
    (Schwere, dann Ebene) -- was oben steht, liest ein Modell zuerst."""
    return "\n".join(
        f"- Szene {a.get('szene')}: {a.get('anweisung')}" for a in auftraege
    )


def _schreibe_die_geschichte(conn, tg, klm, e, chat_id: int, auftraege) -> list[int]:
    """Der Weg der Prosa-Phase: EIN Lauf ueber die ganze Geschichte.

    Fehlt das Modul oder die synchrone Funktion darin, gibt es **keinen
    Modellaufruf**, sondern einen ``SchreibwegFehlt`` mit einem Satz, was
    fehlt."""
    try:
        modul = importlib.import_module(GESCHICHTE_MODUL)
    except ImportError:
        raise SchreibwegFehlt(MELDUNG_OHNE_GESCHICHTENWEG) from None
    funktion = getattr(modul, GESCHICHTE_FUNKTION, None)
    if not callable(funktion):
        raise SchreibwegFehlt(MELDUNG_OHNE_GESCHICHTENWEG)
    funktion(conn, tg, klm, e, chat_id, _regie_fuer_die_geschichte(auftraege))
    return sorted({a["szene"] for a in auftraege if a.get("szene") is not None})


def schreibweg(conn, chat_id: int):
    """Die Schreibfunktion, die zu dieser Phase gehoert.

    Die Verzweigung ist der Punkt, an dem diese Schleife am leichtesten
    falsch wird: der phasenfremde Pfad laeuft ohne Fehler durch und liefert
    trotzdem einen schwaecheren Text (gemessen 06.09.2026). Deshalb steht sie
    hier als eigene Funktion und nicht als ``if`` mitten in der Schleife."""
    return _schreibe_die_geschichte if prosa_phase(conn, chat_id) else _schreibe_je_szene


# ---------------------------------------------------------------------------
# Was ein Lauf zurueckgibt
# ---------------------------------------------------------------------------


@dataclass
class Runde:
    """Eine Runde: eine Pruefung, ihre Auftraege, und -- ab der zweiten -- die
    Bilanz gegen die vorige."""

    nummer: int
    ergebnis: fanout.Ergebnis
    auftraege: list = field(default_factory=list)
    ueberarbeitet: list = field(default_factory=list)
    bilanz: bilanz_modul.Bilanz | None = None


@dataclass
class Schleifenergebnis:
    """Der ganze Lauf: die Runden, warum Schluss war, und die Bilanzen."""

    runden: list = field(default_factory=list)
    grund: str = GRUND_KEINE_AUFTRAEGE
    meldung: str = ""

    @property
    def bilanzen(self) -> list:
        return [r.bilanz for r in self.runden if r.bilanz is not None]

    @property
    def geschadet(self) -> bool:
        return any(b.geschadet for b in self.bilanzen)

    @property
    def aufrufe(self) -> int:
        """Die Modellaufrufe des Richters ueber alle Runden -- die Zahl, die
        auf der Rechnung steht. Der Richter bleibt derselbe (siehe
        ``schliesse``), sein Zaehler laeuft also durch."""
        letzte = self.runden[-1].ergebnis if self.runden else None
        return letzte.aufrufe if letzte is not None else 0

    def zeilen(self) -> list[str]:
        """Der Lauf in wenigen Zeilen: je Runde eine Kopfzeile, dazu die
        Bilanz, am Ende der Grund."""
        zeilen: list[str] = []
        for runde in self.runden:
            zeilen.append(
                f"Runde {runde.nummer}: {len(runde.ergebnis.befunde)} Befunde, "
                f"{len(runde.ergebnis.bewertungen)} Bewertungen, "
                f"{len(runde.auftraege)} Auftraege, "
                f"{len(runde.ueberarbeitet)} Szenen ueberarbeitet"
            )
            if runde.bilanz is not None:
                zeilen.extend(runde.bilanz.zeilen())
        zeilen.append(f"Schluss: {self.meldung or GRUENDE.get(self.grund, self.grund)}")
        return zeilen

    def als_text(self) -> str:
        return "\n".join(self.zeilen())


# ---------------------------------------------------------------------------
# Die Schleife
# ---------------------------------------------------------------------------


def schliesse(conn, tg, klm, e, chat_id: int, *, richter=None,
              runden_max: int = RUNDEN_MAX, schreiber=None) -> Schleifenergebnis:
    """pruefen -> auftraege -> umschreiben -> pruefen -> vergleichen.

    **Derselbe Richter ueber alle Runden.** Er wird in Runde 1 gewaehlt und
    danach weitergereicht: zwei Runden, die verschiedene Modelle gefragt
    haben, liefern keine vergleichbaren Scores, und die Bilanz waere dann eine
    Aussage ueber den Modellwechsel statt ueber den Text.

    ``schreiber`` ueberschreibt die Wahl aus ``schreibweg`` -- fuer Tests und
    fuer einen Aufrufer, der genau weiss, welchen Weg er will. Ohne ihn
    entscheidet die Phase.

    Die Runden zaehlen ausdruecklich hoch (``runde=`` an ``fanout.pruefe``)
    und nicht ueber ``repo.letzte_dramaturgie_runde``: das liest die
    Befundtabelle, und eine Runde ganz ohne Befund wuerde dort keine Spur
    hinterlassen und die naechste dieselbe Nummer bekommen."""
    ergebnis = Schleifenergebnis()
    lauf = fanout.pruefe(conn, e, klm, chat_id, richter=richter)
    richter = lauf.richter
    ergebnis.runden.append(Runde(nummer=lauf.runde, ergebnis=lauf))
    if schreiber is None:
        schreiber = schreibweg(conn, chat_id)

    ueberarbeitungen = 0
    while True:
        aktuell = ergebnis.runden[-1]
        # **Aus der Datenbank, nicht aus ``lauf.befunde``**: die Auftraege
        # tragen die ``befund_id``, und die gibt es erst nach dem INSERT --
        # ohne sie koennte die Gruppe den Vorschlag hinterher keinem Befund
        # mehr zuordnen.
        aktuell.auftraege = fanout.auftraege(
            repo.dramaturgie_befunde(conn, chat_id, runde=aktuell.nummer),
            [f["name"] for f in repo.figuren(conn, chat_id)],
        )
        if not aktuell.auftraege:
            ergebnis.grund = GRUND_KEINE_AUFTRAEGE
            break
        if ueberarbeitungen >= runden_max:
            ergebnis.grund = GRUND_RUNDENLIMIT
            break

        try:
            aktuell.ueberarbeitet = schreiber(
                conn, tg, klm, e, chat_id, aktuell.auftraege
            )
        except SchreibwegFehlt as fehler:
            ergebnis.grund = GRUND_OHNE_SCHREIBWEG
            ergebnis.meldung = str(fehler)
            break
        ueberarbeitungen += 1
        if not aktuell.ueberarbeitet:
            # Alle Auftraege sind an einer Sperre haengengeblieben. Ohne
            # geaenderten Text braucht niemand eine zweite Pruefung zu
            # bezahlen.
            ergebnis.grund = GRUND_KEINE_AUFTRAEGE
            break

        naechste = fanout.pruefe(
            conn, e, klm, chat_id, richter=richter, runde=aktuell.nummer + 1
        )
        vergleich = bilanz_modul.baue(
            aktuell.ergebnis.bewertungen, naechste.bewertungen,
            von=aktuell.nummer, nach=naechste.runde,
        )
        ergebnis.runden.append(
            Runde(nummer=naechste.runde, ergebnis=naechste, bilanz=vergleich)
        )
        if vergleich.geschadet:
            _merke_schaden(conn, e, chat_id, vergleich)
            ergebnis.grund = GRUND_GESCHADET
            break
    ergebnis.meldung = ergebnis.meldung or GRUENDE.get(ergebnis.grund, "")
    return ergebnis


def _merke_schaden(conn, e, chat_id: int, vergleich) -> None:
    """Ein gefallener Score wird eigens vermerkt.

    Sichtbar heisst nicht "steht irgendwo in einer Bilanz": eine
    Ueberarbeitung, die etwas kaputt gemacht hat, ist ein Vorfall wie ein
    gescheiterter Aufruf, und das Dashboard soll sie zeigen, ohne dass jemand
    den Bericht liest."""
    text = "; ".join(v.zeile() for v in vergleich.schlechter)
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), VORFALL_GESCHADET,
            f"Runde {vergleich.von} -> {vergleich.nach}: {text}",
        )
    except Exception:
        log.exception("Vorfall zur Verschlechterung nicht schreibbar, chat_id=%s",
                      chat_id)

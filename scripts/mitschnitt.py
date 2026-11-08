"""Ein mitschreibendes Double an der Transportgrenze zum Sprachmodell.

**Warum an der Grenze und nicht per Nachbau** (Architekt-Entscheidung D1,
05.10.2026): einen Prompt nachzubauen hiesse, eine zweite Wahrheit zu pflegen.
Was hier aufgezeichnet wird, ist per Konstruktion genau das, was der Bot
verschickt haette -- dieselbe Ueberlegung, aus der ``ruecknahme.py`` einen
Erkennerlauf per Diff erfasst statt je Art nachzubauen.

Kein Byte geht ins Netz: ``Mitschnitt`` ersetzt ``klm``, und ``fange_alles``
ersetzt zusaetzlich ``szene_claude.schema``/``prosa`` sowie die Klasse
``interview_theater.llm.LLM`` -- letztere, weil ``dramaturgie.fanout.Richter.frage``
sich fuer den Infomaniak-Richter selbst ein ``LLM`` baut.

Das Double gibt eine **minimal gueltige** Antwort zurueck (``minimale_antwort``)
statt eine Ausnahme zu werfen: Pfade mit mehreren Aufrufen hintereinander
(``verdichter`` zweiter Versuch, ``ablauf._ohne_echo``) sollen weiterlaufen und
auch ihren zweiten Prompt hinterlassen.
"""

from __future__ import annotations

import contextlib
import dataclasses

from interview_theater import llm as llm_modul
from interview_theater import szene_claude

#: Der Platzhalter, den das Double als String-Antwort liefert. Nicht leer:
#: ``ablauf._antworttext`` wirft bei leerer Antwort einen ``LLMFehler``, und
#: ``szene.schreibe`` prueft auf Inhalt.
PROSA_MARKE = "[MITSCHNITT]"

_VORGABE = {
    "string": PROSA_MARKE,
    "array": [],
    "object": {},
    "integer": 0,
    "number": 0,
    "boolean": False,
}


@dataclasses.dataclass(frozen=True)
class Aufruf:
    """Ein aufgezeichneter Modellaufruf -- genau die fuenf Angaben, die der
    Dump braucht: ``art`` fuer die Zuordnung, ``weg``/``modell`` fuer die
    Kopfzeile, ``system``/``nutzer`` fuer den Inhalt."""
    art: str
    weg: str
    modell: str
    system: str
    nutzer: str


def minimale_antwort(schema: dict) -> dict:
    """Das kleinste Objekt, das ``schema`` erfuellt.

    Nur die Pflichtfelder bekommen Werte, der Rest bleibt weg: ein Double, das
    mehr liefert als verlangt, verdeckt einen Aufrufer, der auf ein optionales
    Feld baut."""
    eigenschaften = (schema or {}).get("properties") or {}
    pflicht = (schema or {}).get("required") or list(eigenschaften)
    antwort = {}
    for name in pflicht:
        typ = (eigenschaften.get(name) or {}).get("type", "string")
        antwort[name] = _VORGABE.get(typ, PROSA_MARKE)
    return antwort


class _Klient:
    """Platzhalter fuer ``klm._klient``.

    ``modellwahl.aufruf_schema`` und die vier ``szene_claude``-Aufrufer holen
    sich ``getattr(klm, "_klient", None) or httpx.Client(...)``. Ohne dieses
    Attribut entstuende je Aufruf ein echter Klient -- harmlos, aber er wird
    nie geschlossen, und ein Audit soll keine Sockets hinterlassen."""


class Mitschnitt:
    """Ersetzt ``interview_theater.llm.LLM`` als ``klm``."""

    def __init__(self, e) -> None:
        self._e = e
        self.aufrufe: list[Aufruf] = []
        self._klient = _Klient()

    # -- die zwei Methoden der echten LLM ----------------------------------

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort") -> dict:
        self._merke(art, modell or getattr(self._e, "llm_modell", ""),
                    system, nutzer)
        return minimale_antwort(schema)

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
              timeout=None, bei_teil=None) -> str:
        self._merke(art, getattr(self._e, "llm_modell", ""), system, nutzer)
        return PROSA_MARKE

    # -- Lesen --------------------------------------------------------------

    def letzter(self, art: str) -> Aufruf | None:
        for aufruf in reversed(self.aufrufe):
            if aufruf.art == art:
                return aufruf
        return None

    # -- innen --------------------------------------------------------------

    def _merke(self, art, modell, system, nutzer, weg="infomaniak") -> None:
        self.aufrufe.append(
            Aufruf(art=art, weg=weg, modell=modell or "",
                   system=system or "", nutzer=nutzer or "")
        )


@contextlib.contextmanager
def fange_alles(schnitt: Mitschnitt):
    """Leitet den Claude-Weg und die selbstgebaute ``LLM`` auf ``schnitt`` um.

    Drei Patches, alle am Modul und nicht am Objekt -- die Aufrufer greifen
    ``szene_claude.prosa`` beim Namen (``interview_theater/szene.py:2366``,
    ``kurzgeschichte.py:448``, ``szenenfolge.py:1176``,
    ``stueckpruefung.py:293``, ``buehnenkarte.py:119``,
    ``dramaturgie/fanout.py:213``) und ``llm.LLM`` ebenfalls
    (``fanout.py:219``, lokaler Import in der Funktion)."""
    echte_prosa = szene_claude.prosa
    echtes_schema = szene_claude.schema
    echte_klasse = llm_modul.LLM

    def claude_prosa(conn, e, klient, chat_id, system, nutzer, art, timeout,
                     bei_teil=None, wartezeiten=None, modell=None):
        schnitt._merke(
            art, modell or getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE,
            system, nutzer, weg="claude",
        )
        return PROSA_MARKE

    def claude_schema(conn, e, klient, chat_id, system, nutzer, schema_, art,
                      timeout, bei_teil=None, teil_feld=None, wartezeiten=None,
                      modell=None):
        schnitt._merke(
            art, modell or getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE,
            system, nutzer, weg="claude",
        )
        return minimale_antwort(schema_)

    def fabrik(e, klient=None, conn=None, *rest, **schluessel):
        """Ersatz fuer ``LLM(e, klient, conn)``.

        Liefert ein Double, das in **dieselbe** Liste schreibt und das
        ``llm_modell`` des durchgereichten ``e`` traegt -- bei der
        Dramaturgie-Pruefung ist das das Richtermodell
        (``fanout.Richter.frage``: ``dataclasses.replace(e, llm_modell=...)``)."""
        doppel = Mitschnitt(e)
        doppel.aufrufe = schnitt.aufrufe
        return doppel

    szene_claude.prosa = claude_prosa
    szene_claude.schema = claude_schema
    llm_modul.LLM = fabrik
    try:
        yield schnitt
    finally:
        szene_claude.prosa = echte_prosa
        szene_claude.schema = echtes_schema
        llm_modul.LLM = echte_klasse

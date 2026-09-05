"""Ausfall-Simulation: was liest die Gruppe, wenn das Sprachmodell wegbleibt?

**Die Frage.** SPEC § 11.1 beschreibt, was der Bot tun soll, wenn Infomaniak
nicht antwortet. Was dabei in der Gruppe **ankommt**, hat noch niemand
gelesen: eine Fehlerzeile? Stille? Und laeuft der Bot danach weiter, oder
bleibt der Workshop stehen? Genau das misst ``--stoerung``.

**Wie.** Eine Huelle um den Bot-Klienten wirft ab Zug ``ab_zug`` dreimal in
Folge denselben Fehler -- und zwar nur bei Aufrufen der Art ``gespraech``:
das ist der eine Aufruf, auf den die Gruppe im Chat wartet. Ein Erkenner, der
ausfaellt, ist ein anderer Befund (er laeuft nachgelagert, niemand wartet)
und wuerde die Messung nur vermischen.

**Dreimal in Folge, nicht dauerhaft.** Ein dauerhafter Ausfall misst nur, dass
nichts mehr geht. Interessant ist die Erholung: sagt der Bot etwas, faengt
sich die Gruppe, und geht es danach weiter?

**Kein Netz noetig.** Die Fehler entstehen hier, nicht am Draht -- ``--stoerung``
laesst sich in einem Lauf mit attrappiertem Modell fahren.
"""

from __future__ import annotations

from interview_theater.llm import LLMFehler

#: Die Ausfallarten. Die Meldungen sind wortgleich die, die ``llm.LLM``
#: erzeugt -- ein Fehlertext, den es im Betrieb so nie gibt, wuerde eine
#: Fehlerbehandlung messen, die nur in dieser Datei existiert.
MELDUNGEN = {
    "429": "Sprachmodell lehnte den Aufruf ab: HTTP 429",
    "5xx": "Sprachmodell nach 4 Versuchen nicht erreichbar "
           "(zuletzt: HTTPStatusError)",
    "timeout": "Sprachmodell nach 4 Versuchen nicht erreichbar "
               "(zuletzt: ReadTimeout)",
}

ARTEN = tuple(MELDUNGEN)

#: So oft in Folge wird geworfen.
WIE_OFT = 3

#: Ab welchem Zug, wenn nichts anderes gesagt wird. Frueh genug, dass danach
#: noch Schritte kommen (die Erholung ist der eigentliche Befund), spaet
#: genug, dass die Gruppe schon etwas festgelegt hat.
AB_ZUG_VORGABE = 6

#: Die Aufrufart, die gestoert wird: die eine, auf die die Gruppe wartet.
GESTOERTE_ART = "gespraech"


class StoerungsLLM:
    """Huelle um den Bot-Klienten. Reicht alles durch, ausser den drei
    Aufrufen, die sie schluckt."""

    def __init__(self, klm, art: str, ab_zug: int = AB_ZUG_VORGABE,
                 wie_oft: int = WIE_OFT):
        if art not in MELDUNGEN:
            raise ValueError(f"unbekannte Stoerungsart: {art!r}")
        self._klm = klm
        self.art = art
        self.ab_zug = ab_zug
        self.wie_oft = wie_oft
        self.zug = 0
        self.geworfen = 0
        #: In welchen Zuegen geworfen wurde -- der Bericht zeigt genau diese
        #: Zuege im Wortlaut.
        self.zuege_betroffen: list[int] = []

    def neuer_zug(self) -> None:
        self.zug += 1

    def _faellig(self, art) -> bool:
        return (
            art == GESTOERTE_ART
            and self.zug >= self.ab_zug
            and self.geworfen < self.wie_oft
        )

    def _wirf(self) -> None:
        self.geworfen += 1
        self.zuege_betroffen.append(self.zug)
        raise LLMFehler(MELDUNGEN[self.art])

    def schema(self, *args, **kwargs):
        # ``art`` ist das fuenfte Argument von ``LLM.schema`` -- die Huelle
        # liest es an derselben Stelle, an der der echte Klient es liest,
        # statt eine eigene Signatur zu erfinden, die beim naechsten
        # Parameter auseinanderliefe.
        art = args[4] if len(args) > 4 else kwargs.get("art", "")
        if self._faellig(art):
            self._wirf()
        return self._klm.schema(*args, **kwargs)

    def prosa(self, *args, **kwargs):
        art = args[3] if len(args) > 3 else kwargs.get("art", "")
        if self._faellig(art):
            self._wirf()
        return self._klm.prosa(*args, **kwargs)

    def bericht(self) -> dict:
        return {
            "stoerung": self.art,
            "stoerung_ab_zug": self.ab_zug,
            "stoerung_geworfen": self.geworfen,
            "stoerung_zuege": list(self.zuege_betroffen),
        }

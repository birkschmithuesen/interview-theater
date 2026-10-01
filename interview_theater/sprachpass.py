"""Der letzte Sprachpass: vier mechanisch gezaehlte Muster (30.09.2026, Karte R).

**Warum es das gibt.** ``interview_theater/prompts/theater-tells.md`` steht
**praeventiv** im Schreib-Prompt und nennt drei dieser Muster schon (Nr. 13
rhetorische Dreierfigur, Nr. 19 Themensatz, Nr. 3/4 Fazit und Moral).
Gemessen hat das nicht genuegt: am 06.09.2026 hat Birk den Gruppentext vor dem
Versand von Hand nachbearbeitet -- Gedankenstrich-Inflation, "nicht X, sondern
Y", Adjektiv-Trippel, Geruestsprache. Eine Negativliste im Prompt ist die
halbe Massnahme; die andere Haelfte ist ein Zaehler **nach** dem Lauf.

**Kein Modell.** Vier Regex-Zaehler. Ein Judge, der Sprache beurteilt,
begruendet jede Note -- auch eine falsche -- und kostet je Szene einen Aufruf;
eine Zaehlung ist nachrechenbar und kostet nichts. Ueberschreitet ein Zaehler
seinen Grenzwert, entsteht daraus eine Regie-Notiz, und **erst die** kostet
einen Lauf (``nachpass.py``).

**Die Negativfaelle sind die Arbeit.** Ein falscher Befund kostet einen
bezahlten Lauf und Vertrauen, ein fehlender nur eine Gelegenheit -- dieselbe
Kalibrierung wie beim Sprecherzeilen-Parser in ``dramaturgie/mechanik.py``
("erkennt er keine Sprecherzeile, liefert er gar keinen Befund"). Deshalb
raeumt ``entkleide`` erst Sprecherkoepfe und Regieanweisungen weg, und deshalb
sind die Muster eng: ein Bindestrich-Kompositum ist kein Gedankenstrich, eine
Requisitenliste keine Adjektivkette, ein "but" nach einer Verneinung nicht
automatisch "not X but Y".

**Einheiten.** Drei Zaehler rechnen **je 1.000 Woerter** -- ein Strich in
2.230 Woertern (Dortmund v2, gemessen) ist kein Befund, sechs in 1.000 sind
einer. Der Fazitsatz zaehlt **je Text**, weil er positionell gezaehlt wird:
nur in den letzten ``FAZIT_FENSTER_SAETZE`` Saetzen. Die Einheit steht im
Namen des Grenzwerts (``gedankenstriche_je_1000``, ``fazitsatz_je_text``).

**Zwei Sprachen, eine Auswahl.** Die deutschen Muster existieren und sind
getestet; ob der Pass laeuft, entscheidet ``[sprachpass] aktiv`` im Profil --
fuer Dortmund steht er aus.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Sequence

log = logging.getLogger(__name__)

#: Ein Sprecherkopf bzw. eine Protokoll-Kopfzeile am Zeilenanfang: bis zu 40
#: Zeichen ohne Doppelpunkt, dann ein Doppelpunkt. Deckt ``MIRA:``, ``CHOR:``,
#: ``TITEL:``, ``ZUSAMMENFASSUNG:`` und ``ANDERS GEMACHT:`` ab -- alles, was
#: nicht gesprochener Text ist.
_SPRECHERKOPF = re.compile(r"(?m)^[^\n:]{1,40}:")

#: Eine Regieanweisung. Nicht geschachtelt -- wie ``sprecher._KLAMMER``.
_KLAMMER = re.compile(r"\([^()]*\)")

#: Satzgrenzen fuer das Fazit-Fenster. Schlicht und dokumentiert: Punkt,
#: Ausrufe- oder Fragezeichen, dann Leerraum.
_SATZENDE = re.compile(r"(?<=[.!?])\s+")

#: In so vielen Saetzen am Schluss wird der Fazitsatz gesucht. Zwei, weil ein
#: Fazit gern hinter einem letzten Bild steht.
FAZIT_FENSTER_SAETZE = 2

#: Die Namen der vier Zaehler -- EINE Reihenfolge fuer Zaehlung, Grenzwerte,
#: Notiz und Befund.
NAMEN = ("gedankenstriche", "nicht_sondern", "adjektiv_dreier", "fazitsatz")

# --- 1. Gedankenstrich-Inflation ------------------------------------------
#
# Em- und En-Dash zwischen Wortzeichen (``word—word``, die Maschinenform) und
# der ASCII-Doppelstrich mit Leerzeichen (``wort -- wort``, die Schreibweise
# dieses Repos). Ein einzelner Bindestrich ist NICHT dabei: ``well-known``
# waere sonst ein Befund. Und ein Strich am Zeilenanfang auch nicht -- davor
# steht kein Wortzeichen, dort ist es ein Listenpunkt.
MUSTER_GEDANKENSTRICH = re.compile(r"(?<=\w)\s*(?:[—–]|--)\s*(?=\w)")

# --- 2. "not X but Y" / "nicht X, sondern Y" ------------------------------
#
# Eng: zwischen den Haelften steht kein Satzzeichen ausser einem Komma (sonst
# waeren zwei Saetze ein Muster), die erste Haelfte ist kurz, und nach ``but``
# darf kein Subjektpronomen stehen -- "not ready but I tried" ist ein
# gewoehnlicher Nebensatz. ``\bnot\s`` trifft "nothing but" nicht, weil dort
# kein Leerzeichen hinter "not" steht.
MUSTER_NICHT_SONDERN_EN = re.compile(
    r"\bnot\s+(?:just\s+|only\s+|merely\s+|simply\s+)?"
    r"[^,.;:!?()]{2,40},?\s+but\s+(?:also\s+|rather\s+|instead\s+)?"
    r"(?!(?:i|you|he|she|it|we|they|there)\b)\w",
    re.IGNORECASE,
)
MUSTER_NICHT_SONDERN_DE = re.compile(
    r"\bnicht\s+[^,.;:!?()]{2,40},\s*sondern\s+\w", re.IGNORECASE,
)

# --- 3. Adjektiv-Dreierkette ---------------------------------------------
#
# Kopula plus drei kleingeschriebene Woerter ab drei Buchstaben. **Bewusst
# case-sensitiv**: "was John, Mary, and Sue" ist eine Namensliste, und Namen
# sind gross. Ein Artikel faellt an ``{3,}`` heraus ("a cup, a plate" -- "a"
# hat einen Buchstaben), und Requisitenlisten in Regieanweisungen sind von
# ``entkleide`` ohnehin schon weg.
MUSTER_DREIER_EN = re.compile(
    r"\b(?:is|was|are|were|felt|feels|seemed|seems|looked|looks|becomes|became)"
    r"\s+(?:so\s+|very\s+|too\s+|much\s+)?"
    r"[a-z]{3,},\s+[a-z]{3,},\s+(?:and\s+|or\s+)?[a-z]{3,}\b"
)
MUSTER_DREIER_DE = re.compile(
    r"\b(?:ist|war|sind|waren|wirkt|wirkte|klingt|klang|bleibt|blieb|wurde)"
    r"\s+(?:so\s+|sehr\s+|zu\s+)?"
    r"[a-zäöüß]{3,},\s+[a-zäöüß]{3,}\s*,?\s+(?:und\s+|oder\s+)?[a-zäöüß]{3,}\b"
)

# --- 4. Fazit- und Themensatz --------------------------------------------
#
# Nur in den letzten Saetzen gezaehlt: dieselben Worte mitten im Text sind
# eine Floskel, am Schluss sind sie eine Moral (theater-tells 3, 4, 19).
MUSTER_FAZIT_EN = (
    re.compile(r"\b(?:we all|everyone|everybody|people)\s+"
               r"(?:should|must|need to|have to|ought to)\b", re.IGNORECASE),
    re.compile(r"\b(?:maybe|perhaps)\b[^.!?]{0,60}?\b(?:is|are)\s+"
               r"(?:just\s+|simply\s+|really\s+)?(?:about|where|what)\b",
               re.IGNORECASE),
    re.compile(r"\bthat(?:'s|’s| is)\s+(?:just\s+|simply\s+)?(?:how|what)\s+"
               r"(?:it|life|things|we|they)\b", re.IGNORECASE),
)
MUSTER_FAZIT_DE = (
    re.compile(r"\b(?:wir alle|jeder|man)\s+"
               r"(?:sollte|sollten|muss|muessen|müssen)\b", re.IGNORECASE),
    # Zwei Wortstellungen in EINEM Muster (die Fazit-Zaehlung summiert je
    # Muster -- zwei getrennte zaehlten denselben Satz doppelt):
    # "Vielleicht ... ist (einfach) da/wo/was" und die deutsche Stellung
    # "Vielleicht ist Heimat einfach da, wo ...", bei der das Subjekt
    # zwischen "ist" und dem Ort steht. Die zweite eng: hoechstens zwei
    # Woerter dazwischen, und ein Signalwort muss stehen.
    re.compile(r"\bvielleicht\b(?:[^.!?]{0,60}?\bist\s+"
               r"(?:einfach\s+|eben\s+|wirklich\s+)?(?:da|dort|wo|was|das)\b"
               r"|\s+ist\s+(?:[\wäöüß]+\s+){1,2}?"
               r"(?:einfach|eben|wirklich|nur)\s+(?:da|dort|wo|was|das)\b)",
               re.IGNORECASE),
    re.compile(r"\bso\s+ist\s+(?:das|es|das leben)\b", re.IGNORECASE),
)


def entkleide(text: str | None) -> str:
    """Sprecherkoepfe und Regieanweisungen weg -- gezaehlt wird, was
    gesprochen wird.

    Dieselbe Abgrenzung wie in ``sprecher.py`` (Kopf am Zeilenanfang bis zum
    Doppelpunkt, Regie in runden Klammern), aber bewusst eine **eigene**
    Funktion: ``sprecher`` bestimmt einen Sprecher und verlangt dafuer einen
    Namen aus der Figurenliste; hier wird nur Text entfernt.

    Das ist die Wache gegen den teuersten Falsch-Positiv: eine
    Requisitenliste in einer Regieanweisung (``(a cup, a plate, and a
    knife)``) ist keine Adjektiv-Dreierkette. Prosa ohne Sprecherkoepfe (Phase
    6) bleibt unveraendert."""
    return _SPRECHERKOPF.sub(" ", _KLAMMER.sub(" ", text or ""))


def _je_sprache(code: str | None, werte: dict[str, Any]) -> Any:
    """``sprache.je_sprache`` mit einem Ueberschreibweg fuer Tests und den
    Befund. Ohne ``code`` entscheidet das aktive Profil."""
    if code:
        return werte.get(code, werte["de"])
    return sprache.je_sprache(werte)


def _saetze(text: str) -> list[str]:
    return [s for s in _SATZENDE.split((text or "").strip()) if s.strip()]


def rohzahlen(text: str | None, code: str | None = None) -> dict[str, int]:
    """Die **unskalierten** Treffer je Muster -- die Zahl, die im Befund
    steht.

    Gezaehlt wird auf dem entkleideten Text. Der Fazitsatz nur in den letzten
    ``FAZIT_FENSTER_SAETZE`` Saetzen: die Stelle ist der ganze Unterschied
    zwischen einer Floskel und einer Moral."""
    nackt = entkleide(text)
    nicht_sondern = _je_sprache(
        code, {"de": MUSTER_NICHT_SONDERN_DE, "en": MUSTER_NICHT_SONDERN_EN})
    dreier = _je_sprache(code, {"de": MUSTER_DREIER_DE, "en": MUSTER_DREIER_EN})
    fazit = _je_sprache(code, {"de": MUSTER_FAZIT_DE, "en": MUSTER_FAZIT_EN})
    schluss = " ".join(_saetze(nackt)[-FAZIT_FENSTER_SAETZE:])
    return {
        "gedankenstriche": len(MUSTER_GEDANKENSTRICH.findall(nackt)),
        "nicht_sondern": len(nicht_sondern.findall(nackt)),
        "adjektiv_dreier": len(dreier.findall(nackt)),
        "fazitsatz": sum(1 for m in fazit if m.search(schluss)),
    }


def zaehle(text: str | None, code: str | None = None) -> dict[str, float]:
    """Die Zahlen, gegen die die Grenzwerte gerechnet werden.

    Die ersten drei **je 1.000 Woerter**, der Fazitsatz als absolute Zahl --
    genau wie die Grenzwerte im Profil heissen
    (``gedankenstriche_je_1000`` / ``fazitsatz_je_text``). Gezaehlt werden die
    Woerter mit ``laengen.zaehle_woerter``: EIN Zaehler fuer Eichung, Budget
    und Sprachpass."""
    from interview_theater import laengen

    roh = rohzahlen(text, code)
    woerter = laengen.zaehle_woerter(entkleide(text))
    je_tausend = (woerter / 1000.0) if woerter else 0.0
    ergebnis: dict[str, float] = {"fazitsatz": float(roh["fazitsatz"])}
    for name in ("gedankenstriche", "nicht_sondern", "adjektiv_dreier"):
        ergebnis[name] = (roh[name] / je_tausend) if je_tausend else 0.0
    return {name: ergebnis[name] for name in NAMEN}


# Der Sprachzugriff steht am Modulende (A1-Konvention K1). Hier wird nur
# ``je_sprache`` gebraucht -- die Nutzertexte dieses Pfads stehen in
# ``nachpass.py``.
from interview_theater import sprache  # noqa: E402

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


#: Die Vorgabe-Grenzwerte, falls ein Profil einen nicht nennt. Gleichlautend
#: mit ``workshop.VORGABE_WERTE["sprachpass"]`` -- die Wiederholung ist hier
#: Absicht: der Leser dieses Moduls soll die Zahl sehen, ohne die TOML zu
#: oeffnen, und ein Test haelt beide Seiten aneinander.
GRENZEN_VORGABE: dict[str, float] = {
    "gedankenstriche": 6.0,
    "nicht_sondern": 2.0,
    "adjektiv_dreier": 2.0,
    "fazitsatz": 1,
}

#: Der Profil-Schluessel je Zaehler. Die Einheit steht im Namen, damit
#: niemand sie raten muss.
SCHLUESSEL: dict[str, str] = {
    "gedankenstriche": "gedankenstriche_je_1000",
    "nicht_sondern": "nicht_sondern_je_1000",
    "adjektiv_dreier": "adjektiv_dreier_je_1000",
    "fazitsatz": "fazitsatz_je_text",
}

#: Der Kopf der Regie-Notiz. **Eine Ueberarbeitung, kein Neuschrieb** -- wie
#: "Passt, aber anders": derselbe Text, dieselben Ereignisse, dieselbe
#: Reihenfolge.
NOTIZ_KOPF = ("Ueberarbeite den Text sprachlich. Dieselben Ereignisse, "
              "dieselbe Reihenfolge, dieselben Figuren, dasselbe Ende -- "
              "geaendert wird nur, wie es dasteht:")

#: Der Satz, der die Zitate schuetzt. Er steht **immer** in der Notiz, egal
#: welches Muster gemeldet wurde: das Modell soll es sagen bekommen, und der
#: Code prueft es danach nach (``verlorene``). Der Satz allein waere eine
#: Bitte, die Pruefung allein eine Ueberraschung.
NOTIZ_ZITATE = ("Woertliche Zitate aus den Interviews bleiben Wort fuer Wort "
                "stehen -- auch die Brueche, Wiederholungen und Fuellwoerter "
                "darin. Sie sind die Information, nicht der Fehler.")

#: Je Zaehler ein Satz, der sagt, was zu tun ist. Keine Zahl darin: das
#: Modell soll nicht zaehlen, sondern schreiben.
NOTIZ: dict[str, str] = {
    "gedankenstriche": ("Weniger Gedankenstriche. Wo einer steht, geht meist "
                        "ein Punkt, ein Komma oder gar kein Zeichen."),
    "nicht_sondern": ("Keine Saetze der Form \"nicht X, sondern Y\". Sag "
                      "gleich Y."),
    "adjektiv_dreier": ("Keine Dreierketten aus Eigenschaftswoertern. Eines "
                        "genuegt, oder ein Bild statt aller drei."),
    "fazitsatz": ("Kein Fazit und keine Moral am Schluss. Der letzte Satz "
                  "sagt nicht, worum es ging."),
}


def grenzwerte(profil: Any = None) -> dict[str, float]:
    """Die Grenzwerte dieses Profils, je Zaehler.

    Nachsichtig wie alle Leser dieses Pfades: was keine Zahl ist, wird die
    Vorgabe. ``scripts/pruefe_profil.py`` hat es vorher beanstandet."""
    from interview_theater import workshop

    p = profil or workshop.aktiv()
    ergebnis: dict[str, float] = {}
    for name in NAMEN:
        wert = p.wert(f"sprachpass.{SCHLUESSEL[name]}", GRENZEN_VORGABE[name])
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            log.warning("sprachpass.%s ist keine Zahl (%r)", SCHLUESSEL[name], wert)
            wert = GRENZEN_VORGABE[name]
        ergebnis[name] = wert
    return ergebnis


def ueberschreitungen(zahlen: dict[str, float],
                      grenzen: dict[str, float]) -> list[str]:
    """Welche Zaehler ihren Grenzwert erreichen -- **in der Reihenfolge von
    ``NAMEN``**.

    Erreichen, nicht ueberschreiten: der Grenzwert ist die Zahl, ab der es
    auffaellt. Die feste Reihenfolge ist keine Kosmetik -- eine Notiz mit
    wechselnder Reihenfolge waere im Prompt zwei verschiedene Auftraege fuer
    denselben Befund.

    **Ein Grenzwert 0 schaltet den Zaehler ab.** Sonst erreichte jeder Text
    ihn, und jede Szene kostete einen Nachpass-Lauf."""
    return [name for name in NAMEN
            if float(zahlen.get(name, 0)) >= float(grenzen.get(name, 0))
            and float(grenzen.get(name, 0)) > 0]


def notiz(namen: Sequence[str]) -> str:
    """Die Regie-Notiz aus den gemeldeten Zaehlern, oder "".

    Sie geht ueber denselben Weg wie "Passt, aber anders" in den Auftrag: der
    Text wird **ueberarbeitet**, nicht neu geschrieben. Deshalb kommt hier
    kein ``szene.NEU_MARKER`` vor -- der wuerde die alte Fassung aus dem
    Prompt nehmen und einen zweiten Text erzeugen statt denselben besser."""
    gemeldet = [n for n in NAMEN if n in set(namen)]
    if not gemeldet:
        return ""
    zeilen = [T.NOTIZ_KOPF]
    zeilen += [f"- {T.NOTIZ[n]}" for n in gemeldet]
    zeilen.append(T.NOTIZ_ZITATE)
    return "\n".join(zeilen)


def gepruefte_zitate(conn, chat_id: int) -> list[str]:
    """Alle woertlichen Zitate dieser Gruppe, die eine Pruefung bestanden
    haben.

    Zwei Quellen, und nur zwei: die Verdichtungsthemen mit
    ``zitat_geprueft = 1`` (``repo.gepruefte_themen``) und die
    Sprachprofil-Zitate der Figuren (``figur.zitate`` -- ohne ein einziges
    belegtes Zitat wird dort gar nichts gespeichert). Die Schaerfungen
    (``repo.schaerfungen``) liefern denselben ``beleg_zitat`` und sind damit
    eine Teilmenge der ersten Quelle, kein dritter Ort.

    ``figur.zitate`` ist EIN Feld, die Zitate darin stehen mit
    ``repo.ZITAT_TRENNER`` dazwischen (``repo.setze_sprachprofil``) --
    getrennt wird hier so wie an jeder anderen Lesestelle (``szene``,
    ``knoepfe``, ``web_daten``).

    **Ungeprueftes zaehlt nicht.** Ein unbelegtes Zitat zu schuetzen hiesse,
    eine Erfindung festzuschreiben -- genau das, was ``zitat.py`` seit N2
    verhindert.

    Reine Leseabfrage; die einzige Funktion dieses Moduls, die die Datenbank
    anfasst."""
    from interview_theater import repo

    zitate: list[str] = []
    for thema in repo.gepruefte_themen(conn, chat_id):
        text = (thema["beleg_zitat"] or "").strip()
        if text:
            zitate.append(text)
    for figur in repo.figuren(conn, chat_id):
        for teil in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
            text = teil.strip()
            if text:
                zitate.append(text)
    # Reihenfolge erhalten, Dubletten weg -- dasselbe Zitat zweimal zu
    # pruefen kostet nichts, aber es stuende zweimal im Vorfall.
    gesehen: set[str] = set()
    eindeutig = []
    for text in zitate:
        if text not in gesehen:
            gesehen.add(text)
            eindeutig.append(text)
    return eindeutig


def enthaltene(text: str | None, zitate: Iterable[str]) -> list[str]:
    """Welche dieser Zitate im Text stehen -- geprueft mit ``zitat.pruefe``.

    **Keine zweite Normalisierung.** ``zitat.pruefe`` glaettet
    Whitespace-Folgen und typografische Anfuehrungszeichen und sonst nichts;
    es ist dieselbe Funktion, an der jedes Belegzitat in Verdichter,
    Kernzitaten, Sprachprofil, Schaerfung und Dramaturgie haengt. Eine
    strengere Vergleichsform hier waere ein zweiter Massstab fuer denselben
    Begriff."""
    from interview_theater import zitat as zitat_modul

    return [z for z in zitate if zitat_modul.pruefe(z, text or "")]


def verlorene(alt: str | None, neu: str | None,
              zitate: Iterable[str]) -> list[str]:
    """Welche Zitate **vorher** im Text standen und **nachher** nicht mehr.

    Nur was vorher dastand: ein Zitat, das die Szene nie enthielt, kann sie
    nicht verlieren, und es einzufordern hiesse, dem Modell einen Satz
    aufzuzwingen, den die Gruppe hier nicht wollte."""
    liste = list(zitate)
    vorher = set(enthaltene(alt, liste))
    nachher = set(enthaltene(neu, liste))
    return [z for z in liste if z in vorher and z not in nachher]


# Der Textzugriff (A1-Konvention K1) -- **am Modulende**, nach allen
# Konstanten.
T = sprache.Texte(__name__)

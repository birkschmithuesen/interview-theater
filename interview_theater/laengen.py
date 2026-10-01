"""Laengen-Rhythmus je Szene (30.09.2026, Karte R).

**Warum es das gibt.** Am 06.09.2026 hat Birk den Gruppentext vor dem
Versand an die Auftraggeberin von Hand nachbearbeitet, und zwei der
Eingriffe sind Maschinenarbeit: die Gruppe hatte "Instagram-Kuerze"
beschlossen (etwa ein Viertel der vorgesehenen Laenge), und alle Abschnitte
waren gleich lang. Gemessen am Textbuch v2 dieses Tages: 825, 802, 603
Woerter -- drei Abschnitte, praktisch eine Laenge. Das Modell glaettet auf
Mittelmass, weil der Prompt eine Gesamtlaenge nennt und sonst nichts
(``kurzgeschichte.ANWEISUNG``: "Insgesamt 1.500 bis 3.500 Woerter").

**Was hier passiert.** Der Code -- nicht das Modell -- waehlt je Szene ein
Wortbudget. Er tut es aus einem **Rhythmus-Muster** (kurz-lang-kurz,
lang-kurz-Schlag, ...), das er je Gruppe wuerfelt und zyklisch ueber die
Szenennummern liest. Damit ist "nie alle gleich" keine Bitte an ein Modell,
sondern eine Eigenschaft der Zahlen.

**Was hier NICHT passiert.** Kein Modellaufruf, keine Datenbank, keine
Entscheidung ueber die **Form** einer Szene. Dieses Modul liest die Form und
leitet daraus eine Laenge ab; gesetzt wird ``szene.form`` allein durch einen
Knopfdruck der Gruppe, wie bisher.

**Alles Konfigurierbare liegt im Profil** (``[laengen]`` in
``workshop/<name>/profil.toml``), und der Hauptschalter ``aktiv`` steht im
eingebauten Vorgabeprofil auf ``False``: ohne ``IT_WORKSHOP`` und mit
``IT_WORKSHOP=dortmund-2026`` wird hier nichts gelesen und kein Prompt
geaendert.

**Die Leser sind nachsichtig, der Profil-Pruefer ist streng.** Ein kaputter
Wert in der TOML faellt hier auf die Vorgabe zurueck und schreibt eine
Logzeile; beanstandet wird er in ``scripts/pruefe_profil.py``, das in
``scripts/betrieb-start.sh`` **vor** dem Bot laeuft. Ein Absturz mitten im
Workshop wegen eines Tippfehlers waere der teurere Fehler.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Mapping, Sequence

from interview_theater import workshop

log = logging.getLogger(__name__)

#: Markdown-Zeichen, die keine Woerter sind. Sie fallen weg, bevor gezaehlt
#: wird -- ein Modell setzt Ueberschriften und Betonungen auch dann, wenn der
#: Prompt es nicht verlangt.
_MARKDOWN = re.compile(r"[*_`#>\[\]]")

#: Ein Wort: Wortzeichen, optional mit einem Apostroph-Anhang ("don't").
#: Genau die Tokenisierung der Eichung vom 30.09.2026.
_WORT = re.compile(r"\w+(?:['’]\w+)?", re.UNICODE)

#: Unter so viele Woerter geht kein Budget. ``kurz_faktor`` = 0,25 auf den
#: kleinsten Rahmen (Chor 80) ergaebe 20 -- weniger waere keine Szene mehr.
MINDEST_WOERTER = 20

#: Auf so viel wird jedes Budget gerundet. Eine Zahl wie "247 Woerter" gibt
#: eine Genauigkeit vor, die es nicht gibt.
RUNDUNG = 10

#: Die Stufen des Rhythmus und ihr Gewicht im Rahmen einer Form: 0,0 ist das
#: Minimum, 1,0 das Maximum. "schlag" ist die ganz kurze Szene, die einen
#: Rhythmus erst hoerbar macht.
STUFEN: dict[str, float] = {
    "schlag": 0.0,
    "kurz": 0.2,
    "mittel": 0.5,
    "lang": 1.0,
}


def zaehle_woerter(text: str | None) -> int:
    """Wie viele Woerter ein Text hat -- **die eine Zaehlung** fuer Eichung,
    Budget, Nachzaehlen und Befund.

    Gemessen wie die Eichung vom 30.09.2026: Markdown-Zeichen weg, dann
    Tokens ``\\w+('\\w+)?``. Bewusst **nicht** ``len(text.split())`` (dort
    zaehlen Satzzeichen als Wortteil mit) und bewusst **nicht**
    ``sprecher._worte`` (das entfernt Regieanweisungen, weil es Sprechanteile
    zaehlt -- fuer ein Laengenbudget zaehlt aber alles, was auf dem Blatt
    steht). Die bestehenden Zaehlungen bleiben, wo sie sind; sie messen
    etwas anderes."""
    return len(_WORT.findall(_MARKDOWN.sub(" ", text or "")))


def _werte(profil: workshop.Profil | None = None) -> Mapping[str, Any]:
    """Der Abschnitt ``[laengen]`` des aktiven Profils, oder ein leeres Dict.

    Bei **jedem** Aufruf frisch geholt (``workshop.aktiv()``), nicht einmal
    beim Import: derselbe Grund wie beim Modul-``__getattr__`` in
    ``phasen.py`` -- ein Prozess koennte spaeter mehr als ein Profil sehen."""
    p = profil or workshop.aktiv()
    wert = p.wert("laengen", {})
    return wert if isinstance(wert, Mapping) else {}


def _zahl(quelle: Mapping[str, Any], name: str, vorgabe: float) -> float:
    """Eine Zahl aus dem Profil, nachsichtig: was keine ist, wird die
    Vorgabe, und der Fall steht im Log."""
    wert = quelle.get(name, vorgabe)
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        log.warning("laengen.%s ist keine Zahl (%r) -- nehme %r", name, wert, vorgabe)
        return vorgabe
    return float(wert)


def aktiv(profil: workshop.Profil | None = None) -> bool:
    """Waehlt dieses Profil die Budgets? Vorgabe: nein."""
    return bool(_werte(profil).get("aktiv", False))


def sprachpass_aktiv(profil: workshop.Profil | None = None) -> bool:
    """Laeuft der letzte Sprachpass? Vorgabe: nein.

    Steht hier und nicht in ``sprachpass.py``, damit es **einen** Ort fuer
    beide Schalter gibt: wer die Konfiguration sucht, sucht sie einmal."""
    p = profil or workshop.aktiv()
    wert = p.wert("sprachpass", {})
    return bool(wert.get("aktiv", False)) if isinstance(wert, Mapping) else False


def kurz_faktor(profil: workshop.Profil | None = None) -> float:
    """Was "Kuerzer/Instagram" auf alle Budgets legt. Vorgabe 0,25."""
    faktor = _zahl(_werte(profil), "kurz_faktor", 0.25)
    return faktor if 0 < faktor <= 1 else 0.25


def nachzaehl_schwelle(profil: workshop.Profil | None = None) -> float:
    """Ab welchem Anteil des Budgets EIN Kuerzungslauf angehaengt wird.
    Vorgabe 1,3 -- also ab 130 %."""
    schwelle = _zahl(_werte(profil), "nachzaehl_schwelle", 1.3)
    return schwelle if schwelle >= 1.0 else 1.3


def rahmen_fuer(form: str | None,
                profil: workshop.Profil | None = None) -> tuple[int, int]:
    """Der Wortrahmen ``(min, max)`` dieser Form.

    Die Form wird getrimmt und kleingeschrieben verglichen -- ``szene.form``
    ist ein freies Textfeld, und "CHOR" ist dieselbe Form wie "chor". Eine
    Form, die im Profil keinen Rahmen hat (auch eine frei erfundene
    "Bewegungsszene"), bekommt ``vorgabe_min``/``vorgabe_max``: ein
    unbekannter Formname darf kein Absturz und keine fehlende Laenge sein."""
    werte = _werte(profil)
    unten = int(_zahl(werte, "vorgabe_min", 200))
    oben = int(_zahl(werte, "vorgabe_max", 450))
    if not 0 < unten < oben:
        unten, oben = 200, 450
    rahmen = werte.get("rahmen") or {}
    schluessel = (form or "").strip().lower()
    paar = rahmen.get(schluessel) if isinstance(rahmen, Mapping) else None
    if paar is None:
        return unten, oben
    try:
        a, b = int(paar[0]), int(paar[1])
    except (TypeError, ValueError, IndexError):
        log.warning("laengen.rahmen[%r] ist kein [min, max] (%r)", schluessel, paar)
        return unten, oben
    if not 0 < a < b:
        log.warning("laengen.rahmen[%r] ist kein 0 < min < max (%r)", schluessel, paar)
        return unten, oben
    return a, b


def form_der_szene(szene: Any) -> str:
    """Die Form, an der die Laenge dieser Szene haengt: **bestaetigt vor
    vorgeschlagen vor Vorgabe**.

    In Phase 6 ist ``form`` oft leer, weil die Gruppe sie erst im Feinschliff
    bestaetigt -- ``form_vorschlag`` steht dort aber schon (die vierte Spalte
    der Szenenzeile). Das Budget **liest** hier, es **schreibt** nichts: eine
    Laenge ist keine Formentscheidung, und ``szene.form`` bleibt
    unberuehrt."""
    def feld(name: str) -> str:
        try:
            return (szene[name] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""

    return feld("form") or feld("form_vorschlag") or workshop.form_vorgabe()


#: Die Mindestspreizung innerhalb einer Form: das groesste Budget geteilt
#: durch das kleinste. Je Form gerechnet, weil die Form die Laenge dominiert
#: -- eine lange Chorszene (200) darf kuerzer sein als eine kurze
#: Dialogszene (250), ohne dass der Rhythmus verlorengegangen waere.
SPREIZUNG_MIN = 1.5

#: Das Muster, das gilt, wenn das Profil keines nennt. Gleichlautend mit dem
#: ersten Eintrag der Vorgabe, damit ein Profil ohne ``muster`` nicht flach
#: wird.
MUSTER_RUECKFALL: tuple[str, ...] = ("kurz", "lang", "kurz")


def muster_liste(profil: workshop.Profil | None = None) -> tuple[tuple[str, ...], ...]:
    """Die brauchbaren Muster des Profils.

    Nachsichtig wie ``rahmen_fuer``: ein Eintrag mit einer unbekannten Stufe
    oder mit weniger als zwei verschiedenen Stufen fliegt hier heraus statt
    einen Lauf mitzunehmen -- ``scripts/pruefe_profil.py`` hat ihn vorher
    beanstandet. Bleibt nichts uebrig, gilt ``MUSTER_RUECKFALL``: ein Profil
    ohne brauchbares Muster soll kurze und lange Szenen bekommen und nicht
    lauter mittlere."""
    roh = _werte(profil).get("muster") or ()
    gut: list[tuple[str, ...]] = []
    for eintrag in roh:
        try:
            stufen = tuple(str(s).strip().lower() for s in eintrag)
        except TypeError:
            log.warning("laengen.muster: %r ist keine Liste", eintrag)
            continue
        if len(stufen) < 2 or any(s not in STUFEN for s in stufen):
            log.warning("laengen.muster: %r unbrauchbar -- uebersprungen", eintrag)
            continue
        if len(set(stufen)) < 2:
            log.warning("laengen.muster: %r ist flach -- uebersprungen", eintrag)
            continue
        gut.append(stufen)
    return tuple(gut) or (MUSTER_RUECKFALL,)


def muster_fuer(seed: int,
                profil: workshop.Profil | None = None) -> tuple[str, ...]:
    """Das Rhythmus-Muster dieser Gruppe.

    ``seed`` ist die ``chat_id``. Kein ``random``, kein gespeicherter Wert:
    derselbe Chat bekommt immer dasselbe Muster, und niemand muss es
    aufbewahren. Telegram-Gruppen haben **negative** ids -- ``abs()`` steht
    hier, damit der Index unabhaengig von der Vorzeichen-Konvention von ``%``
    lesbar bleibt."""
    liste = muster_liste(profil)
    return liste[abs(int(seed)) % len(liste)]


def stufe_fuer(nummer: int | None, muster: Sequence[str]) -> str:
    """Die Stufe der Szene ``nummer`` in diesem Muster -- **zyklisch**.

    Zyklisch und nicht ueber die Gesamtzahl verteilt: sonst verschoebe eine
    nachtraeglich eingefuegte Szene 6 das Budget von Szene 1, und das
    Nachzaehlen rechnete gegen eine andere Zahl als der Lauf. ``nummer``
    ``None`` oder 0 gilt als erste Szene -- ``szene.nummer`` darf NULL sein,
    und eine Ausnahme waere ein Lauf ohne Budget."""
    if not muster:
        muster = MUSTER_RUECKFALL
    n = int(nummer or 1)
    if n < 1:
        n = 1
    return muster[(n - 1) % len(muster)]


def stufen(nummern: Sequence[int | None], seed: int,
           profil: workshop.Profil | None = None) -> list[str]:
    """Die Stufen einer ganzen Szenenfolge, in deren Reihenfolge."""
    muster = muster_fuer(seed, profil)
    return [stufe_fuer(n, muster) for n in nummern]


def ist_flach(werte: Sequence[str]) -> bool:
    """Bekommen alle Szenen dieselbe Stufe?

    Eine einzelne Szene ist immer flach -- ein Rhythmus braucht zwei. Das ist
    keine Beanstandung, sondern die Wahrheit: bei einer Szene gibt es keinen
    Rhythmus, und der Test dazu verlangt ihn nicht."""
    return len(set(werte)) <= 1


def spreizung(werte: Sequence[int]) -> float:
    """Groesstes durch kleinstes Budget -- 1,0, wenn es nichts zu vergleichen
    gibt oder ein Wert 0 ist (keine Division durch Null)."""
    zahlen = [int(w) for w in werte if int(w) > 0]
    if len(zahlen) < 2:
        return 1.0
    return max(zahlen) / min(zahlen)


def _aus_stufe(stufe: str, unten: int, oben: int, faktor: float) -> int:
    """Eine Stufe im Rahmen ``(unten, oben)`` zu einer Wortzahl.

    Linear zwischen Minimum (Gewicht 0,0) und Maximum (1,0), dann mit
    ``faktor`` skaliert, auf ``RUNDUNG`` gerundet und nie unter
    ``MINDEST_WOERTER``. Die Rundung steht **nach** dem Faktor: sonst waere
    "ein Viertel von einer runden Zahl" wieder keine runde Zahl."""
    gewicht = STUFEN.get(stufe, STUFEN["mittel"])
    roh = (unten + gewicht * (oben - unten)) * float(faktor)
    gerundet = int(round(roh / RUNDUNG) * RUNDUNG)
    return max(gerundet, MINDEST_WOERTER)


def budget_fuer(nummer: int | None, form: str | None, seed: int,
                faktor: float = 1.0,
                profil: workshop.Profil | None = None) -> int:
    """Das Wortbudget EINER Szene.

    ``form`` ist die Form, die ``form_der_szene`` geliefert hat; ``seed`` die
    ``chat_id``; ``faktor`` die Uebersteuerung (1,0 = keine). Deckungsgleich
    mit dem entsprechenden Eintrag aus ``budgets`` -- ein Test haelt das fest,
    denn zwei Wege zu einer Zahl, die auseinanderlaufen, planen gegen ein
    anderes Budget als sie pruefen."""
    unten, oben = rahmen_fuer(form, profil)
    return _aus_stufe(stufe_fuer(nummer, muster_fuer(seed, profil)),
                      unten, oben, faktor)


def budgets(formen: Sequence[str | None], nummern: Sequence[int | None],
            seed: int, faktor: float = 1.0,
            profil: workshop.Profil | None = None) -> list[int]:
    """Die Budgets einer ganzen Szenenfolge, in der Reihenfolge von
    ``formen``/``nummern``.

    Die beiden Listen gehoeren paarweise zusammen; ist ``nummern`` kuerzer,
    wird ab dort durchgezaehlt (eine Szene ohne Nummer ist die naechste)."""
    ergebnis: list[int] = []
    for i, form in enumerate(formen):
        nummer = nummern[i] if i < len(nummern) else i + 1
        ergebnis.append(budget_fuer(nummer, form, seed, faktor, profil))
    return ergebnis


def zu_lang(woerter: int, budget: int,
            profil: workshop.Profil | None = None) -> bool:
    """Ist dieser Text ueber der Nachzaehl-Schwelle?

    Kein Budget (0 oder negativ) heisst **keine** Beanstandung: wo nichts
    geplant war, ist nichts ueberschritten."""
    if int(budget) <= 0:
        return False
    return int(woerter) >= int(budget) * nachzaehl_schwelle(profil)

"""Schicht 3: der Fan-out -- vier Judge-Fragen, je ein Aufruf, je eine Frage.

**Nicht alle vierzehn Fragen des Katalogs** (Recherche § 2), sondern die vier
mit dem hoechsten Ertrag pro Aufruf, in der Reihenfolge aus § 6:

* **B1 Value Flip** (Materialklasse M1, je Szene) -- findet die Plauderszene,
  den haeufigsten Fehlermodus einer LLM-geschriebenen Szene.
* **A2 Kausale Verkettung** (M5, Synopsen-Kette, EIN Aufruf fuers ganze
  Stueck) -- findet strukturelles Auseinanderfallen, solange Umbau billig ist.
* **A6 Tschechow** (EIN Aufruf am Ende, **nur ueber die Kandidatenliste aus
  Schicht 1**) -- nicht ueber das ganze Stueck: das waere derselbe Aufruf
  noch einmal, nur teurer.
* **C1 Blind-Attribution** (M2, anonymisiert, je Szene) -- **der Judge vergibt
  hier keinen Score.** Er ordnet Repliken zu; die Trefferquote und damit der
  Score wird im Code aus dem Abgleich mit der Ground Truth berechnet. Das ist
  der Kern der Bias-Freiheit dieser Frage: das Modell weiss nicht, wie gut es
  war, und kann sich deshalb nicht selbst benoten (Recherche § 4).

## Sechs bindende Regeln, alle im Code und nicht im Prompt

1. **Ein Aufruf = eine Frage.** Kein Feld "Gesamtnote" im Antwortschema --
   auch nicht optional, sonst fuellt das Modell es (Recherche § 4,
   Halo-Effekt).
2. **Jeder Prompt ist eine eigene Datei** unter ``prompts/dramaturgie/`` und
   laeuft ueber ``anweisungen.hole`` -- heiss nachgeladen wie jeder andere
   Prompt. Die ``prompt_version`` steht in der Datei und kommt aus dem
   Dateikopf ins Ergebnis, **nicht** aus der Modellantwort: eine Version, die
   das Modell selbst nennt, sagt nichts darueber, welche Datei gelaufen ist.
3. **Antwortformat sind Markerbloecke**, wie in ``stueckpruefung.py`` -- kein
   erzwungenes JSON-Schema. Grund: die Szenen-Anbieter liefern Prosa
   (``llm.prosa`` / ``szene_claude.prosa``), und der Claude-Weg kennt
   ``response_format`` gar nicht. Ein zweiter Anbieterpfad nur fuer diese
   Pruefung waere ein zweiter Ort fuer dieselbe Entscheidung. Der Parser ist
   dafuer streng und getestet.
4. **Getrennter Richter.** Der Judge darf nicht dasselbe Modell sein wie der
   Schreiber (Recherche § 4, Self-Enhancement Bias). Erzwungen in
   ``waehle_richter``: sind beide gleich, gibt es einen ``RichterFehler`` mit
   klarer Meldung und **keinen Lauf** -- keine stille Abwertung.
5. **Seriell.** Die Recherche empfiehlt Nebenlaeufigkeit 8-12. Das ist fuer
   unseren Betrieb falsch: Infomaniak drosselt Parallelitaet mit 429/5xx
   statt mit einer Warteschlange (AGENTS.md, Falle 8), und
   ``scripts/pruefe_prompts.py`` ruft aus demselben Grund sequenziell auf.
   Ein voller Lauf ueber acht Szenen sind ohnehin nur rund achtzehn Aufrufe.
   Backoff steckt in den beiden Anbieterwegen (``llm.WARTEZEITEN``,
   ``szene_claude.WARTEZEITEN``).
6. **Kein Modellaufruf im Knopf-Handler** (bindende Zusage 2): ``starte()``
   gibt an einen eigenen Thread ab, wie ``stueckpruefung.starte``.

## Was der Judge sieht

Kein Klarname, kein Transkript, kein Chat, kein Arbeitsstand ausser der
Geschichte: **B1 und C1 sehen nur den Szenentext**, A2 nur die Synopsen,
A6 nur die Kandidatenliste. Der Prueftext steht zwischen Markierungen, und
jeder Prompt sagt ausdruecklich, dass dazwischen niemals eine Anweisung
steht (Recherche § 4, Prompt Injection).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import re
import threading
from dataclasses import dataclass, field

import httpx

from interview_theater import anweisungen, phasen, repo, szene_claude
from interview_theater.dramaturgie import beleg as beleg_modul
from interview_theater.dramaturgie import mechanik

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

#: Prompt-Namen unter ``interview_theater/prompts/``.
PROMPTS = {
    "b1": "dramaturgie/b1_wendung",
    "a2": "dramaturgie/a2_kausalkette",
    "a6": "dramaturgie/a6_tschechow",
    "a9": "dramaturgie/a9_fokus",
    "a10": "dramaturgie/a10_materialtreue",
    "a11": "dramaturgie/a11_stueckvorgaben",
    "c1": "dramaturgie/c1_stimme",
}

#: ``art`` in der Tabelle ``aufruf`` -- je Frage eine eigene, damit Dashboard
#: und Kostenzeile den Weg getrennt sehen (und nicht mit ``szene`` oder
#: ``stueckpruefung`` verrechnen).
ARTEN = {schluessel: f"dramaturgie_{schluessel}" for schluessel in PROMPTS}

#: Zeitbudget und Ausgabedeckel je Aufruf. Der Deckel ist eine Obergrenze
#: gegen ein durchdrehendes Modell, kein Zielwert (Birk, 04.09.2026) -- eine
#: Judge-Antwort sind acht Zeilen, aber der Infomaniak-Weg laeuft ueber
#: ``llm.prosa`` mit aktivem Reasoning, und das verbraucht das Budget vor dem
#: eigentlichen Inhalt (AGENTS.md, Falle 4).
TIMEOUT_S = 300.0
MAX_TOKENS = 16_000

#: **Seriell.** Der Wert steht hier, damit er benannt ist und nicht als
#: stillschweigende Eigenschaft einer for-Schleife existiert. Wer ihn
#: heraufsetzt, liest vorher AGENTS.md Falle 8; die Obergrenze aus dem
#: Auftrag ist 3, nicht die 12 aus der Recherche.
GLEICHZEITIG = 1

#: Ab so vielen Repliken lohnt sich C1. Darunter ist die Trefferquote
#: Zufall -- bei drei Repliken und zwei Figuren raet man 50 % richtig, ohne
#: irgendetwas gehoert zu haben.
C1_REPLIKEN_MIN = 6
C1_FIGUREN_MIN = 2

#: Die Schwellen aus Recherche § 2, C1. Sie werden **im Code** angewandt, weil
#: der Judge seinen eigenen Score nicht kennt.
C1_SCHWELLE_GUT = 0.8
C1_SCHWELLE_MITTEL = 0.5

#: Hoechstens so viele Ueberarbeitungsauftraege je Szene und Runde
#: (Recherche § 3): sonst ueberschreibt der Schreib-LLM sich selbst.
AUFTRAEGE_JE_SZENE = 3

#: Rang der Schweregrade, ueber beide Quellen hinweg. ``hart`` (Mechanik) und
#: ``blocker`` (Judge) sind derselbe Rang -- beides heisst "im Text
#: nachweisbar falsch".
SCHWERE_RANG = {
    "blocker": 0, "hart": 0, "hoch": 1, "mittel": 2, "verdacht": 2,
    "niedrig": 3, "hinweis": 3,
}
SCHWEREN_JUDGE = ("blocker", "hoch", "mittel", "niedrig")

#: Die Ebene je Pruefung -- Geschichte vor Szene vor Stimme (Recherche § 3).
#: Eine Prueung, die hier fehlt, sortiert ans Ende.
EBENEN = {
    "a2": 0, "a6": 0, "a11": 0, "namensstabilitaet": 0, "geisterfigur": 0,
    "erstauftritt": 0, "figur_ohne_auftritt": 0,
    "a9": 1, "fokus": 1, "a10": 1,
    "b1": 1, "besetzung_stumm": 1, "besetzung_fremd": 1,
    "formverteilung": 1, "form_regel": 1, "tschechow": 1,
    "c1": 2, "sprechanteil": 2,
}

#: Was in den Chat geht, wenn der Lauf nicht laufen konnte.
MELDUNG_OHNE_SZENEN = (
    "Ich kann die Dramaturgie noch nicht pruefen - es ist noch keine Szene "
    "geschrieben."
)
MELDUNG_GLEICHES_MODELL = (
    "Ich pruefe nicht mit demselben Modell, das die Szenen geschrieben hat "
    "({modell}) - ein Modell, das seinen eigenen Text benotet, findet ihn gut. "
    "Setzt IT_JUDGE_MODELL auf ein anderes Modell, dann laeuft die Pruefung."
)
MELDUNG_OHNE_USA = (
    "Fuer die Pruefung muesste ich eure Szenen an das US-Modell schicken "
    "({modell}), und dem habt ihr nicht zugestimmt. Entweder ihr stimmt der "
    "Uebermittlung zu, oder der Betreiber setzt IT_JUDGE_MODELL auf ein "
    "Schweizer Modell, das nicht eure Szenen geschrieben hat."
)
MELDUNG_FEHLGESCHLAGEN = (
    "Die Dramaturgie-Pruefung hat nicht geklappt. Ihr koennt es gleich noch "
    "einmal versuchen."
)
MELDUNG_KOPF = "Ich habe eure Szenen einzeln durchgesehen - Runde {runde}:"
MELDUNG_OHNE_BEFUND = (
    "Ich habe eure Szenen einzeln durchgesehen und nichts gefunden, was ich "
    "euch melden muesste."
)


class RichterFehler(Exception):
    """Der Richter steht nicht -- mit einem Text fuer die Gruppe."""


class DramaturgieFehler(Exception):
    """Der Lauf konnte nicht laufen -- mit einem Text fuer die Gruppe."""


# ---------------------------------------------------------------------------
# Der Richter: ein anderes Modell als der Schreiber
# ---------------------------------------------------------------------------

#: Umgebungsvariable, mit der der Betreiber das Richtermodell setzt. Ohne sie
#: wird der jeweils ANDERE Weg genommen: schreiben die Szenen ueber Claude,
#: richtet Infomaniak -- und umgekehrt.
ENV_MODELL = "IT_JUDGE_MODELL"


@dataclass
class Richter:
    """Wer prueft: ein Anbieterweg und ein Modellname.

    ``weg`` ist ``"claude"`` (lokaler Proxy, Anthropic-Format) oder
    ``"infomaniak"`` (chat/completions). Welcher, entscheidet der Modellname:
    alles, was mit ``claude`` beginnt, geht ueber den Proxy.

    ``aufrufe`` zaehlt die **Modellaufrufe**, nicht die Fragen: ein Retry nach
    einem nicht gefundenen Beleg ist ein zweiter Aufruf und kostet zweimal.
    Der Bericht soll die Zahl nennen, die auf der Rechnung steht."""

    weg: str
    modell: str
    aufrufe: int = 0

    def frage(self, conn, e, klm, chat_id: int, system: str, nutzer: str,
              art: str) -> str:
        """Ein Aufruf, ein Text. Bucht in ``aufruf`` mit der ``art`` dieser
        Frage -- der Weg selbst ist der vorhandene, hier kommt kein dritter
        Anbieterpfad dazu."""
        self.aufrufe += 1
        if self.weg == "claude":
            klient = getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S)
            return szene_claude.prosa(
                conn, dataclasses.replace(e, szene_modell=self.modell), klient,
                chat_id, system, nutzer, art, timeout=TIMEOUT_S,
            )
        from interview_theater.llm import LLM

        klient = getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S)
        richter_klm = LLM(
            dataclasses.replace(e, llm_modell=self.modell), klient, conn
        )
        return richter_klm.prosa(
            chat_id, system, nutzer, art, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
        )


def schreibermodell(e, conn=None, chat_id: int | None = None) -> str:
    """Welches Modell die Szenen dieser Gruppe schreibt.

    Nicht aus einer Konstante, sondern aus derselben Bedingung, die
    ``szene.py`` benutzt: der Betreiber muss den Claude-Weg erlaubt haben UND
    die Gruppe zugestimmt haben. Sonst ist es das Infomaniak-Modell."""
    if szene_claude.ist_aktiv(e, conn, chat_id):
        return getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE
    return getattr(e, "llm_modell", "") or ""


def waehle_richter(e, conn=None, chat_id: int | None = None) -> Richter:
    """Der Richter fuer diese Gruppe -- oder ein ``RichterFehler``.

    **Weigert sich zu laufen, wenn Schreiber == Richter.** Das ist die
    Gegenmassnahme gegen den Self-Enhancement Bias (Recherche § 4, Q17/Q19):
    ein Judge bevorzugt Texte des eigenen Modells, gemessen und
    reproduzierbar. Der Fehler ist laut und traegt eine Meldung fuer die
    Gruppe; eine stille Abwertung ("wir ziehen einen Punkt ab") waere eine
    Zahl, die niemand nachrechnen kann.

    Ohne ``IT_JUDGE_MODELL`` gilt die Vorgabe: schreiben die Szenen ueber
    Claude, richtet das Infomaniak-Modell -- und umgekehrt."""
    schreiber = schreibermodell(e, conn, chat_id)
    gewuenscht = (os.environ.get(ENV_MODELL) or "").strip()
    if not gewuenscht:
        gewuenscht = (
            (getattr(e, "llm_modell", "") or "")
            if szene_claude.ist_aktiv(e, conn, chat_id)
            else szene_claude.MODELL_VORGABE
        )
    if not gewuenscht:
        raise RichterFehler(T.MELDUNG_GLEICHES_MODELL.format(modell=schreiber or "?"))
    if gewuenscht.strip().casefold() == (schreiber or "").strip().casefold():
        raise RichterFehler(T.MELDUNG_GLEICHES_MODELL.format(modell=schreiber))
    weg = "claude" if gewuenscht.lower().startswith("claude") else "infomaniak"
    if weg == "claude" and not usa_erlaubt(conn, chat_id):
        # **Der Judge liest den Szenentext**, und der Claude-Weg geht ueber
        # eine amerikanische API. Dieselbe Zustimmung, die der Szenenlauf
        # braucht (``szene_claude.ist_aktiv``), braucht deshalb auch die
        # Pruefung -- sonst ginge auf dem Umweg ueber den Richter in die USA,
        # was die Gruppe fuer das Schreiben ausdruecklich abgelehnt hat.
        raise RichterFehler(T.MELDUNG_OHNE_USA.format(modell=gewuenscht))
    return Richter(weg, gewuenscht)


def usa_erlaubt(conn=None, chat_id: int | None = None) -> bool:
    """Hat die Gruppe der Uebermittlung in die USA zugestimmt?

    Ohne Gruppenbezug (Skript, Test) True: dort entscheidet der Betreiber, wen
    er fragt, und es gibt keine Gruppe, die widersprechen koennte."""
    if conn is None or chat_id is None:
        return True
    return repo.szene_usa_stand(conn, chat_id) == "ja"


# ---------------------------------------------------------------------------
# Prompt und Version
# ---------------------------------------------------------------------------

_VERSION = re.compile(r"^\s*prompt_version:\s*(\S+)\s*$", re.MULTILINE)


def prompt(schluessel: str) -> str:
    """Der Prompt einer Frage, heiss nachgeladen (``anweisungen.hole``)."""
    return anweisungen.hole(PROMPTS[schluessel])


def version(schluessel: str) -> str:
    """Die ``prompt_version`` aus der Prompt-Datei.

    Aus der **Datei**, nicht aus der Antwort: welche Fassung gelaufen ist,
    weiss der Code und nicht das Modell. Fehlt die Zeile, ist das ``"?"`` --
    ein Ergebnis ohne Versionsangabe ist besser als kein Ergebnis, aber es
    soll auffallen."""
    treffer = _VERSION.search(prompt(schluessel))
    return treffer.group(1) if treffer else "?"


# ---------------------------------------------------------------------------
# Der Parser: Markerbloecke
# ---------------------------------------------------------------------------

_MARKERZEILE = re.compile(r"^([A-ZÄÖÜ][A-ZÄÖÜ_ ]{1,28}?)\s*:\s*(.*)$")

#: Die Marker, die es gibt -- und **nur** die eroeffnen einen Block.
#:
#: Der Grund ist ein Fehler, der ohne Liste passiert waere: ein Belegzitat aus
#: einer Dialogszene beginnt regelmaessig mit einem Sprechernamen in Versalien
#: und einem Doppelpunkt (``BELEG: MIRA: Gib mir den Schluessel.``). Geht das
#: Zitat ueber zwei Zeilen, saehe die zweite (``JONAS: Nein.``) wie ein neuer
#: Marker aus, und der Beleg waere abgeschnitten. Mit der Liste ist jede Zeile,
#: die keinen bekannten Marker traegt, eine Fortsetzung.
_SCHLUESSEL = frozenset({
    "SCORE", "BEFUND", "BELEG", "SCHWERE", "VORSCHLAG", "UNSICHER", "SZENE",
    "WERT", "LADUNG", "ADDITIVE_SZENEN", "UNEINGELOEST", "ZUORDNUNG",
    "FRAGE", "PROMPT_VERSION",
    # A9 Fokus
    "THEMA", "KLASSEN", "DANEBEN",
    # A10 Materialtreue -- RICHTUNG entscheidet, ob der Text oder die
    # Festlegung nachzieht, und muss deshalb sicher ankommen.
    "GEPRUEFT", "ABWEICHUNG", "GEWINN", "RICHTUNG",
})


def _bloecke(antwort: str) -> dict[str, list[str]]:
    """Zerlegt eine Markerantwort in Schluessel -> Werte, in Reihenfolge.

    Fortsetzungszeilen (eine Zeile ohne bekannten Marker) gehoeren zum zuletzt
    geoeffneten Marker: ein Beleg oder ein Vorschlag darf ueber zwei Zeilen
    gehen. Markdown-Beiwerk (``**BELEG:** ...``) wird abgeraeumt, wie in
    ``szene._kopfwert`` -- das Modell setzt seine Marker gern fett."""
    ergebnis: dict[str, list[str]] = {}
    letzter: str | None = None
    for roh in (antwort or "").splitlines():
        zeile = roh.strip().lstrip("*#`> -").strip()
        if not zeile:
            letzter = None
            continue
        treffer = _MARKERZEILE.match(zeile)
        schluessel = (
            "_".join(treffer.group(1).split()).upper() if treffer else ""
        )
        if schluessel in _SCHLUESSEL:
            wert = treffer.group(2).strip().strip("*` ").strip()
            ergebnis.setdefault(schluessel, []).append(wert)
            letzter = schluessel
            continue
        if letzter and ergebnis[letzter]:
            ergebnis[letzter][-1] = (ergebnis[letzter][-1] + " " + zeile).strip()
    return ergebnis


def _erster(bloecke: dict, schluessel: str) -> str:
    werte = bloecke.get(schluessel) or []
    return werte[0] if werte else ""


def _score(wert: str):
    treffer = re.search(r"[0-2]", wert or "")
    return int(treffer.group()) if treffer else None


#: Die englischen Schwere-Woerter (Karte A1, K5) -> die deutschen
#: Protokollwerte aus ``SCHWEREN_JUDGE``. Erst nach den deutschen probiert,
#: mit Wortgrenzen ("low" soll nicht in "below"/"follow" treffen).
_SCHWEREN_EN = (("high", "hoch"), ("medium", "mittel"), ("low", "niedrig"))


def _schwere(wert: str) -> str:
    gefaltet = (wert or "").lower()
    for name in SCHWEREN_JUDGE:
        if name in gefaltet:
            return name
    for wort, name in _SCHWEREN_EN:
        if re.search(r"\b" + wort + r"\b", gefaltet):
            return name
    return "mittel"


def _ja(wert: str) -> bool:
    gefaltet = (wert or "").strip().lower()
    return gefaltet.startswith(("ja", "true", "yes", "y"))


def _nummer(wert: str):
    treffer = re.search(r"\d+", wert or "")
    return int(treffer.group()) if treffer else None


def zerlege(antwort: str) -> dict:
    """Die Markerantwort einer Frage mit Score als Dict.

    **Kein Feld "Gesamtnote"** -- es gibt keins im Schema und deshalb auch
    keins hier. Was nicht dasteht, ist None; ein fehlender Score macht den
    Befund unbrauchbar, aber nicht den Lauf kaputt."""
    bloecke = _bloecke(antwort)
    return {
        "score": _score(_erster(bloecke, "SCORE")),
        "befund": _erster(bloecke, "BEFUND") or None,
        "beleg": _erster(bloecke, "BELEG") or None,
        "schwere": _schwere(_erster(bloecke, "SCHWERE")),
        "vorschlag": _erster(bloecke, "VORSCHLAG") or None,
        "szene": _nummer(_erster(bloecke, "SZENE")),
        "unsicher": _ja(_erster(bloecke, "UNSICHER")),
        "wert": _erster(bloecke, "WERT") or None,
        "ladung": _erster(bloecke, "LADUNG") or None,
        "additive_szenen": _erster(bloecke, "ADDITIVE_SZENEN") or None,
        "uneingeloest": _erster(bloecke, "UNEINGELOEST") or None,
        # A10: in welche Richtung korrigiert wird. "parameter" heisst, dass
        # der Text recht hat und die Festlegung veraltet ist -- der Vorschlag
        # geht dann NICHT an den Schreiber (siehe ``parameterkorrektur``).
        "richtung": _richtung(_erster(bloecke, "RICHTUNG")),
        "abweichung": _erster(bloecke, "ABWEICHUNG") or None,
        "gewinn": _erster(bloecke, "GEWINN") or None,
    }


#: Die beiden Richtungen einer A10-Korrektur. Alles andere ist keine.
RICHTUNGEN = ("text", "parameter")


def _richtung(wert: str) -> str | None:
    """``text`` oder ``parameter`` -- oder None, wenn das Modell etwas
    anderes geschrieben hat. Kein Rueckfall auf einen der beiden Werte: eine
    geratene Richtung wuerde entweder den Text umschreiben oder eine
    Festlegung der Gruppe ueberschreiben, und beides auf Verdacht."""
    kern = (wert or "").strip().lower().rstrip(".")
    for richtung in RICHTUNGEN:
        if kern.startswith(richtung):
            return richtung
    return None


#: ``1 = MIRA``, aber auch ``1: MIRA`` und mehrere Paare in einer Zeile
#: (``1 = MIRA, 2 = JONAS``). Der Prompt bittet um eine Zeile je Replik; ein
#: Modell, das sie in einer Zeile zusammenfasst, soll deswegen nicht als
#: "hat nichts zugeordnet" gelten -- das waere ein Befund ueber den Parser,
#: der als Befund ueber das Stueck in den Chat ginge.
_ZUORDNUNG = re.compile(r"(\d{1,3})\s*[=:]\s*([^,;\n]+)")


def zerlege_zuordnung(antwort: str) -> tuple[dict[int, str], dict]:
    """Die C1-Antwort: Replik-Nummer -> vermutete Figur, plus Beleg.

    **Kein Score.** Der Prompt fragt keinen ab, und dieser Parser liest
    keinen -- selbst wenn das Modell einen mitschickt, ist er hier nicht
    abholbar. Genau das ist die Massnahme."""
    bloecke = _bloecke(antwort)
    zuordnung: dict[int, str] = {}
    for wert in bloecke.get("ZUORDNUNG") or []:
        for nummer, name in _ZUORDNUNG.findall(wert):
            gesaeubert = name.strip().strip("„“\"'*` ").strip()
            if gesaeubert:
                zuordnung.setdefault(int(nummer), gesaeubert)
    rest = {
        "befund": _erster(bloecke, "BEFUND") or None,
        "beleg": _erster(bloecke, "BELEG") or None,
        "unsicher": _ja(_erster(bloecke, "UNSICHER")),
    }
    return zuordnung, rest


# ---------------------------------------------------------------------------
# Das Material: was der Judge sieht
# ---------------------------------------------------------------------------

#: Die Markierungen um den Prueftext. Sie stehen im Prompt und hier -- eine
#: Aenderung braucht beide Stellen, und ein Test haelt sie zusammen.
MARKEN = {
    "szene": ("<<<SZENE", "SZENE>>>"),
    "synopsen": ("<<<SYNOPSEN", "SYNOPSEN>>>"),
    "kandidaten": ("<<<KANDIDATEN", "KANDIDATEN>>>"),
    "repliken": ("<<<REPLIKEN", "REPLIKEN>>>"),
}


def umschliesse(marke: str, material: str, kopf: str = "") -> str:
    """Der Nutzertext: eine Kopfzeile ausserhalb, der Prueftext innerhalb der
    Markierungen. Der Beleg wird gegen ``material`` geprueft und nie gegen
    diesen ganzen String -- was ausserhalb steht, hat der Judge nicht als
    Stueck gelesen."""
    auf, zu = MARKEN[marke]
    teile = [kopf.strip()] if kopf.strip() else []
    teile.append(f"{auf}\n{material.strip()}\n{zu}")
    return "\n\n".join(teile)


def material_szene(zeile) -> str:
    """Nur der Szenentext -- kein Klarname, kein Transkript, kein Chat."""
    for feld in ("volltext", "prosa"):
        try:
            wert = (zeile[feld] or "").strip()
        except (IndexError, KeyError):
            continue
        if wert:
            return wert
    return ""


def material_synopsen(conn, chat_id: int) -> str:
    """Die Synopsen-Kette (Materialklasse M5): je Szene Nummer, Titel, Form
    und die Kurzfassung -- nie der Volltext.

    Quelle der Kurzfassung ist ``szene.zusammenfassung`` (die schreibt das
    Szenen-Modell selbst mit, kostet also keinen Aufruf), sonst
    ``kurzbeschreibung``, sonst der Anfang der Prosafassung. Fehlt alles,
    steht die Szene mit ihrer Planung da und nicht als Luecke."""
    teile: list[str] = []
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None:
            continue
        kopf = T._SZENE_MIT_NUMMER.format(nummer=s["nummer"])
        if (s["titel"] or "").strip():
            kopf += f": {s['titel'].strip()}"
        if (s["form"] or "").strip():
            kopf += f" ({s['form'].strip()})"
        teile.append(kopf)
        teile.append(_synopse(s))
    return "\n".join(teile)


#: So viele Zeichen der Prosafassung stehen im Rueckfall in der Synopse. Drei
#: Zeilen, wie es die Materialklasse M5 vorsieht -- nicht der halbe Volltext,
#: sonst ist die Kette so teuer wie das Fenster.
SYNOPSE_ZEICHEN = 400


def _synopse(s) -> str:
    for feld in ("zusammenfassung", "kurzbeschreibung"):
        try:
            wert = (s[feld] or "").strip()
        except (IndexError, KeyError):
            continue
        if wert:
            return wert
    for feld in ("prosa", "was_passiert"):
        try:
            wert = " ".join((s[feld] or "").split())
        except (IndexError, KeyError):
            continue
        if wert:
            return wert[:SYNOPSE_ZEICHEN]
    return T.OHNE_SYNOPSE


def material_kandidaten(kandidaten) -> str:
    """Die Tschechow-Kandidaten mit ihrem Satz als Kontext.

    Der Satz ist da, damit der Judge ueberhaupt etwas **zitieren** kann: eine
    reine Wortliste liesse ihn zwischen "kein Beleg moeglich" und einem
    erfundenen Zitat waehlen."""
    zeilen = []
    for k in kandidaten:
        zeile = T._ZEILE_KANDIDAT.format(szene=k.szene, wort=k.wort, anzahl=k.anzahl)
        if k.satz:
            zeile += f": {k.satz}"
        zeilen.append(zeile)
    return "\n".join(zeilen)


def material_repliken(repliken) -> str:
    """Die Repliken einer Szene **ohne Namen**, durchnummeriert (M2)."""
    return "\n".join(f"{i}. {r.text}" for i, r in enumerate(repliken, start=1))


# ---------------------------------------------------------------------------
# Die vier Fragen
# ---------------------------------------------------------------------------


def _stelle(conn, e, klm, chat_id, richter, schluessel, nutzer, material, marke):
    """Ein Aufruf mit Belegpflicht: fragen, Beleg pruefen, hoechstens einmal
    nachfragen (``beleg.hole_mit_beleg``)."""
    system = prompt(schluessel)

    def aufruf(hinweis):
        text = nutzer if not hinweis else f"{nutzer}\n\n{hinweis}"
        return zerlege(
            richter.frage(conn, e, klm, chat_id, system, text, ARTEN[schluessel])
        )

    return beleg_modul.hole_mit_beleg(aufruf, material, marke)


def frage_b1(conn, e, klm, chat_id: int, richter: Richter, szene,
             bewertungen=None) -> dict | None:
    """B1 Value Flip fuer EINE Szene (M1). None, wenn die Szene keinen Text
    hat."""
    material = material_szene(szene)
    if not material:
        return None
    nummer = szene["nummer"]
    nutzer = umschliesse(
        "szene", material, T._KOPF_SZENE.format(nummer=nummer)
    )
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "b1", nutzer, material, f"b1 Szene {nummer}",
    )
    _merke(bewertungen, "b1", nummer, antwort, stand)
    return _befund_aus("b1", antwort, stand, szene=nummer)


def frage_a9(conn, e, klm, chat_id: int, richter: Richter, szene,
             hauptkonflikt: str = "", bewertungen=None) -> dict | None:
    """A9 Fokus fuer EINE Szene: wieviel Text spielt neben dem Hauptkonflikt?

    **Warum es diese Frage gibt** (Birk, 06.09.2026, zum fertigen Text von
    Gruppe 1): *"zu wenig Fokus auf die wesentliche Handlung, zu viele
    belanglose Nebenschauplaetze, die vom Wesentlichen ablenken"*. Keine der
    vier bestehenden Fragen konnte das melden: B1 prueft, ob die Wertladung
    kippt (sie kippte), A2 die Verkettung der Szenen, A6 aufgeladene
    Gegenstaende, C1 die Stimmen. Ein Text kann alle vier bestehen und
    trotzdem zur Haelfte woanders spielen -- gemessen an Gruppe 1: Szene 1 zu
    53 %, Szene 3 zu 52 %, waehrend Szene 2 mit 2 % die Szene ist, die alle
    als die staerkste lesen.

    **Der Hauptkonflikt geht in den Nutzertext, nicht in die
    Systemanweisung** -- dort steht die Frage, hier das Material dieser
    Gruppe. Ohne Hauptkonflikt gibt es keine Frage: dann ist unbestimmt,
    wovon ein Nebenschauplatz abweichen wuerde.
    """
    material = material_szene(szene)
    if not material or not (hauptkonflikt or "").strip():
        return None
    nummer = szene["nummer"]
    kopf = T._KOPF_SZENE.format(nummer=nummer) + T._KOPF_HAUPTKONFLIKT.format(
        hauptkonflikt=hauptkonflikt.strip()
    )
    nutzer = umschliesse("szene", material, kopf)
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "a9", nutzer, material, f"a9 Szene {nummer}",
    )
    _merke(bewertungen, "a9", nummer, antwort, stand)
    return _befund_aus("a9", antwort, stand, szene=nummer)


#: Die Szenenfelder, die A10 als Festlegung vorlegt -- und die einzigen, die
#: eine Parameterkorrektur setzen darf. ``ort`` steht dabei, weil es eine
#: Entscheidung der Gruppe ist; ``titel`` nicht, der ist eine Beschriftung
#: und keine Festlegung ueber den Inhalt.
#:
#: **``form`` steht NICHT hier.** Sie wird erst im Feinschliff (Phase 7)
#: eingeloest; in Phase 6 schreibt das Modell ausdruecklich Prosa
#: (``szene.py``: *"In Phase 6 geht IMMER prosa.md in die Systemanweisung --
#: die Form der Szene ist dort noch gar nicht entschieden"*). Ein Judge, der
#: eine Prosafassung an ihrer kuenftigen Form misst, meldet einen Fehler, der
#: keiner ist -- gemessen 06.09.2026: A10 verlangte fuer Szene 3 gesprochenen
#: Rap in einem Text, der ihn planmaessig noch nicht haben konnte.
#: ``form`` wird stattdessen von ``FORM_JE_PHASE`` zugeschaltet, sobald das
#: Stueck im Feinschliff ist.
A10_FELDER = ("ort", "zeit", "anlass", "was_passiert", "kernsaetze", "ton")

#: Ab dieser Phase ist die Form eingeloest und darf geprueft werden. Davor
#: ist sie eine Notiz fuer spaeter (``szene.form_vorschlag``).
A10_FORM_AB_PHASE = 7

#: Wie die Felder im Nutzertext heissen. Der Judge soll den Feldnamen
#: zurueckschreiben koennen (``anlass: <neuer Wert>``), deshalb steht der
#: technische Name daneben.
A10_BESCHRIFTUNG = {
    "form": "Form", "ort": "Ort", "zeit": "Zeit", "anlass": "Anlass",
    "was_passiert": "Was passiert", "kernsaetze": "Kernsaetze", "ton": "Ton",
}


def a10_felder(conn=None, chat_id: int | None = None) -> tuple[str, ...]:
    """Die Felder, die A10 in dieser Phase prueft.

    Im Feinschliff kommt ``form`` dazu: dort ist sie eingeloest und eine
    Szene, die ihre Form verfehlt, ist ein echter Befund. In Phase 6 bleibt
    sie draussen (siehe ``A10_FELDER``).
    """
    if conn is None or chat_id is None:
        return A10_FELDER
    try:
        phase = phasen.aktuelle(conn, chat_id)
    except Exception:  # noqa: BLE001 -- ohne Phase gilt die engere Liste
        return A10_FELDER
    if phase is not None and phase >= A10_FORM_AB_PHASE:
        return ("form",) + A10_FELDER
    return A10_FELDER


def material_festlegungen(szene, felder=None) -> str:
    """Die Festlegungen der Gruppe zu dieser Szene, als Liste.

    Leere Felder werden weggelassen, nicht als "—" gezeigt: eine Festlegung,
    die es nicht gibt, kann weder eingeloest noch verfehlt werden, und eine
    Zeile "Ton: —" laedt den Judge ein, ueber ihr Fehlen zu urteilen.
    """
    zeilen = []
    for feld in (felder if felder is not None else A10_FELDER):
        try:
            wert = (szene[feld] or "").strip()
        except (IndexError, KeyError):
            continue
        if wert:
            zeilen.append(f"- {T.A10_BESCHRIFTUNG[feld]} ({feld}): {wert}")
    return "\n".join(zeilen)


def frage_a10(conn, e, klm, chat_id: int, richter: Richter, szene,
              bewertungen=None) -> dict | None:
    """A10 Materialtreue: haelt die Szene, was die Gruppe festgelegt hat?

    **Und wenn nicht -- wer zieht nach?** (Birk, 06.09.2026: *"die Szene kann
    und darf sich in der Entwicklung auch von den Ursprungsparametern
    aendern, wenn es die Szene oder die Handlung verbessert... wenn die
    Aenderung gut begruendet wird, sollte der Parameter angepasst werden"*).

    Eine reine Treuepruefung wuerde ein Stueck starr machen: der Schreiblauf
    findet regelmaessig etwas Besseres als die Planung, und ein Judge, der
    das als Fehler meldet, biegt den Text auf eine ueberholte Festlegung
    zurueck. Deshalb liefert A10 eine **Richtung**: ``text`` (der Schreiber
    zieht nach) oder ``parameter`` (die Festlegung ist veraltet und wird auf
    den Stand des Textes gebracht).

    Ohne Festlegungen gibt es nichts zu pruefen -- dann kein Aufruf.
    """
    material = material_szene(szene)
    felder = a10_felder(conn, chat_id)
    festlegungen = material_festlegungen(szene, felder)
    if not material or not festlegungen:
        return None
    nummer = szene["nummer"]
    kopf = T._KOPF_SZENE.format(nummer=nummer) + T._KOPF_FESTLEGUNGEN.format(
        festlegungen=festlegungen
    )
    nutzer = umschliesse("szene", material, kopf)
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "a10", nutzer, material,
        f"a10 Szene {nummer}",
    )
    _merke(bewertungen, "a10", nummer, antwort, stand)
    return _befund_aus("a10", antwort, stand, szene=nummer)


#: ``anlass: Michael geht ins Wasser`` -- Feldname, Doppelpunkt, neuer Wert.
#: ``form`` ist hier erlaubt, obwohl es nicht in ``A10_FELDER`` steht: im
#: Feinschliff legt ``a10_felder`` es vor, und dann muss der Judge es auch
#: zurueckschreiben duerfen. Vorgelegt wird es trotzdem nur phasenabhaengig --
#: was nicht im Prompt stand, schlaegt ein Modell praktisch nie vor.
_PARAMETER_ZEILE = re.compile(
    r"^\s*(form|" + "|".join(A10_FELDER) + r")\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def parameterkorrektur(befund) -> tuple[str, str] | None:
    """Aus einem A10-Befund mit ``richtung=parameter``: (Feld, neuer Wert).

    **Der einzige Weg, auf dem ein Judge eine Festlegung der Gruppe aendern
    kann** -- und er fuehrt nicht an ihr vorbei: was hier herauskommt, ist
    ein *Vorschlag*, den die Gruppe im Chat bestaetigt. Ein Modell, das eine
    Szenenplanung still ueberschreibt, waere genau die Sorte unsichtbarer
    Aenderung, wegen der die Analyse vom 06.09. geschrieben wurde.

    Liefert None, wenn die Richtung nicht ``parameter`` ist, der Beleg nicht
    geprueft wurde oder der Vorschlag nicht als ``feld: wert`` lesbar ist.
    """
    if _feld(befund, "pruefung") != "a10":
        return None
    if _feld(befund, "richtung") != "parameter":
        return None
    if not _feld(befund, "beleg_geprueft"):
        # Dieselbe Grenze wie beim Schreiber: ohne verifiziertes Zitat
        # aendert sich nichts (Recherche § 4).
        return None
    treffer = _PARAMETER_ZEILE.search(_feld(befund, "vorschlag") or "")
    if treffer is None:
        return None
    feld = treffer.group(1).lower()
    wert = treffer.group(2).strip().strip("\"'")
    return (feld, wert) if wert else None


#: Die Felder des Arbeitsstands, die A11 als Vorgabe vorlegt -- und die
#: einzigen, die eine Parameterkorrektur auf Stueckebene setzen darf.
A11_FELDER = ("format", "rahmen", "figuren_anzahl", "geschichte")

A11_BESCHRIFTUNG = {
    "format": "Format", "rahmen": "Rahmen (Ort und Zeit)",
    "figuren_anzahl": "Figurenzahl", "geschichte": "Geplante Szenenfolge",
}


def material_vorgaben(conn, chat_id: int) -> str:
    """Die Vorgaben der Gruppe fuer das ganze Stueck, als Liste.

    Leere Felder werden weggelassen -- was nie festgelegt wurde, kann nicht
    verfehlt werden (dieselbe Regel wie bei ``material_festlegungen``).
    """
    zeile = repo.hole_arbeitsstand(conn, chat_id)
    if zeile is None:
        return ""
    zeilen = []
    for feld in A11_FELDER:
        try:
            wert = (zeile[feld] or "").strip()
        except (IndexError, KeyError):
            continue
        if wert:
            zeilen.append(f"- {T.A11_BESCHRIFTUNG[feld]} ({feld}): {wert}")
    return "\n".join(zeilen)


def frage_a11(conn, e, klm, chat_id: int, richter: Richter,
              bewertungen=None) -> dict | None:
    """A11 Stueckvorgaben: haelt das Stueck, was fuer das Ganze galt?

    **EIN Aufruf ueber die Synopsen-Kette**, nicht einer je Szene: Format,
    Rahmen und Figurenzahl sind Eigenschaften des Stuecks, und eine Frage je
    Szene wuerde dieselbe Antwort n-mal bezahlen.

    Dieselbe Zwei-Richtungs-Logik wie A10 (siehe dort): ``text`` oder
    ``parameter``. Beim Format ist der Prompt bewusst strenger -- "eine Folge,
    Ende offen" ist eine Zusage darueber, was am Ende auf der Buehne steht,
    keine Stilfrage.

    Ohne Vorgaben oder mit lueckenhaften Synopsen: kein Aufruf. Die
    Synopsen-Sperre ist dieselbe wie bei A2 (``synopsen_fehlen``) -- eine
    Kette aus Platzhaltern beantwortet keine Frage ueber den Bogen.
    """
    vorgaben = material_vorgaben(conn, chat_id)
    if not vorgaben:
        return None
    material = material_synopsen(conn, chat_id)
    if not material.strip():
        return None
    luecken = synopsen_fehlen(material)
    if len(luecken) > SYNOPSEN_LUECKEN_MAX:
        log.info(
            "a11 uebersprungen, chat_id=%s: keine Kurzfassung fuer Szene %s",
            chat_id, ", ".join(str(n) for n in luecken),
        )
        return None
    kopf = T._KOPF_SYNOPSEN + T._KOPF_VORGABEN.format(vorgaben=vorgaben)
    nutzer = umschliesse("synopsen", material, kopf)
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "a11", nutzer, material, "a11",
    )
    # Adresse ``None``: A11 gilt dem Stueck, nicht einer Szene.
    _merke(bewertungen, "a11", None, antwort, stand)
    return _befund_aus("a11", antwort, stand)


#: ``format: eine Folge, Ende offen`` -- Feldname, Doppelpunkt, neuer Wert.
_STUECKPARAMETER_ZEILE = re.compile(
    r"^\s*(" + "|".join(A11_FELDER) + r")\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def stueckparameterkorrektur(befund) -> tuple[str, str] | None:
    """Aus einem A11-Befund mit ``richtung=parameter``: (Feld, neuer Wert).

    Gegenstueck zu ``parameterkorrektur`` fuer die Stueckebene, mit denselben
    drei Sperren: richtige Pruefung, Richtung ``parameter``, geprueftes
    Belegzitat. Und wie dort gilt: das Ergebnis ist ein **Vorschlag** an die
    Gruppe, keine Aenderung.
    """
    if _feld(befund, "pruefung") != "a11":
        return None
    if _feld(befund, "richtung") != "parameter":
        return None
    if not _feld(befund, "beleg_geprueft"):
        return None
    treffer = _STUECKPARAMETER_ZEILE.search(_feld(befund, "vorschlag") or "")
    if treffer is None:
        return None
    feld = treffer.group(1).lower()
    wert = treffer.group(2).strip().strip("\"'")
    return (feld, wert) if wert else None


#: Was ``_synopse`` liefert, wenn eine Szene keinerlei Kurzfassung hat.
#: Steht als Konstante hier, weil ``synopsen_fehlen`` daran erkennt, dass eine
#: Zeile leer ist -- ein Vergleich gegen einen wiederholten Literalstring waere
#: genau die Stelle, an der die Sperre beim naechsten Umformulieren aufhoert
#: zu greifen.
OHNE_SYNOPSE = "(noch nichts geschrieben)"

#: Die Kopfzeilen und Materialzeilen der Judge-Nutzertexte (W3: in der
#: Sprache des Profils, damit der Richter in ihr antwortet).
_SZENE_MIT_NUMMER = "Szene {nummer}"
_ZEILE_KANDIDAT = 'Szene {szene} - "{wort}" ({anzahl}-mal)'
_KOPF_SZENE = "Das ist Szene {nummer} des Stuecks."
_KOPF_HAUPTKONFLIKT = "\n\nDer Hauptkonflikt des Stuecks: {hauptkonflikt}"
_KOPF_FESTLEGUNGEN = "\n\nDie Gruppe hat fuer diese Szene festgelegt:\n{festlegungen}"
_KOPF_SYNOPSEN = "Das ist die Szenenfolge des Stuecks als Kurzfassungen."
_KOPF_VORGABEN = "\n\nDie Gruppe hat fuer das ganze Stueck vorgegeben:\n{vorgaben}"
_KOPF_GESCHICHTE = "\nDie Gruppe hat sich die Geschichte so vorgenommen:\n{geschichte}"
_KOPF_KANDIDATEN = "Das ist die maschinelle Kandidatenliste zu diesem Stueck."
_KOPF_REPLIKEN = (
    "Das sind die Repliken von Szene {nummer}, ohne Namen. "
    "In dieser Szene sprechen: {figuren}."
)

#: Der Kopf einer Szene in der Synopsen-Kette, in beiden Sprachen -- die
#: Kette kann vor einem Profilwechsel gebaut sein (Rundreise, Karte A1).
_SYNOPSE_KOPF = re.compile(r"^Szene (\d+)")
_SYNOPSE_KOPF_EN = re.compile(r"^Scene (\d+)")

#: Wie viele Szenen hoechstens ohne Kurzfassung dastehen duerfen, damit A2
#: noch laeuft. Null: die Frage lautet, ob Szene n kausal an eine fruehere
#: anschliesst -- fehlt auch nur eine Kurzfassung, ist die Kette an dieser
#: Stelle nicht pruefbar, und der Judge beantwortet in Wahrheit eine Frage
#: ueber unsere Datenlage.
SYNOPSEN_LUECKEN_MAX = 0


#: Ab wie vielen Woertern eine Kurzfassung als Kurzfassung gilt. Gemessen am
#: 06.09.2026: eine Kurzbeschreibung wie "szene" oder "Szene 2" ist formal
#: gefuellt und inhaltlich leer -- der Judge liest daraus dieselbe Luecke wie
#: aus einem fehlenden Feld, nur merkt es niemand, weil das Feld belegt ist.
#:
#: **Woerter, nicht Zeichen.** Der erste Versuch nahm 25 Zeichen und verwarf
#: damit "Sie streiten." und "Mira und Jonas streiten." -- gueltige, nur kurze
#: Synopsen. Zwei Woerter trennen den Satz vom Etikett, ohne knappe Saetze zu
#: bestrafen: "Sie streiten." bleibt drin, "szene" und "Szene 2" fallen raus.
SYNOPSE_MINDEST_WOERTER = 2


def synopsen_fehlen(material: str) -> list[int]:
    """Die Szenennummern ohne brauchbare Kurzfassung in der Synopsen-Kette.

    **Warum das eine eigene Sperre braucht** (gemessen 06.09.2026 in den
    ersten beiden echten Judge-Laeufen gegen Opus): ``material_synopsen``
    liefert *immer* einen nicht-leeren Text -- eine Szene ohne jede
    Kurzfassung steht mit ``OHNE_SYNOPSE`` da. Die alte Pruefung
    ``if not material.strip()`` konnte deshalb nie greifen. Der Judge bekam
    eine Kette aus Titeln und Platzhaltern und meldete pflichtgemaess, es gebe
    *"weder in Szene 2 noch in Szene 3 einen erkennbaren kausalen Anschluss"*
    -- ein wahrer Satz ueber unsere Datenlage und ein falscher ueber das
    Stueck. Ein bezahlter Aufruf fuer einen Befund, der eine Gruppe zu einem
    Umbau verleitet haette, den ihr Stueck nicht braucht.

    **Zwei Faelle, nicht einer** (der zweite kam erst im Gegenprobelauf ans
    Licht): das Feld fehlt ganz (``OHNE_SYNOPSE``) -- oder es ist gefuellt und
    trotzdem leer ("szene", "Szene 2"). Der zweite Fall ist der gefaehrlichere,
    weil er wie Inhalt aussieht. Geprueft wird deshalb auf Satzcharakter
    (``SYNOPSE_MINDEST_WOERTER``), nicht auf Existenz.

    Dieselbe Haltung wie ``szene.sperrtext``: fehlt eine Voraussetzung, gibt
    es **keinen Modellaufruf**, sondern eine Nachricht in einem Satz, was
    fehlt.
    """
    luecken: list[int] = []
    nummer: int | None = None
    leer = {OHNE_SYNOPSE, T.OHNE_SYNOPSE}
    for zeile in (material or "").splitlines():
        treffer = (_SYNOPSE_KOPF.match(zeile.strip())
                   or _SYNOPSE_KOPF_EN.match(zeile.strip()))
        if treffer is not None:
            nummer = int(treffer.group(1))
            continue
        if nummer is None:
            continue
        text = zeile.strip()
        if text in leer or len(text.split()) < SYNOPSE_MINDEST_WOERTER:
            luecken.append(nummer)
        nummer = None
    return luecken


def frage_a2(conn, e, klm, chat_id: int, richter: Richter,
             bewertungen=None) -> dict | None:
    """A2 Kausale Verkettung -- EIN Aufruf ueber die Synopsen-Kette (M5)."""
    material = material_synopsen(conn, chat_id)
    if not material.strip():
        return None
    # Sperre VOR dem Aufruf, nicht Bewertung danach (siehe ``synopsen_fehlen``).
    luecken = synopsen_fehlen(material)
    if len(luecken) > SYNOPSEN_LUECKEN_MAX:
        log.info(
            "a2 uebersprungen, chat_id=%s: keine Kurzfassung fuer Szene %s",
            chat_id, ", ".join(str(n) for n in luecken),
        )
        return None
    stand_zeile = repo.hole_arbeitsstand(conn, chat_id)
    kopf = T._KOPF_SYNOPSEN
    geschichte = ""
    if stand_zeile is not None:
        try:
            geschichte = (stand_zeile["geschichte"] or "").strip()
        except (IndexError, KeyError):
            geschichte = ""
    if geschichte:
        kopf += T._KOPF_GESCHICHTE.format(geschichte=geschichte)
    nutzer = umschliesse("synopsen", material, kopf)
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "a2", nutzer, material, "a2 Kausalkette",
    )
    # Adresse ``None``: gefragt wurde ueber die ganze Kette. Die Szenennummer
    # in der Antwort ist die Fundstelle und geht in den Befund, nicht in die
    # Bilanz (siehe ``_merke``).
    _merke(bewertungen, "a2", None, antwort, stand)
    return _befund_aus("a2", antwort, stand, szene=antwort.get("szene"))


def frage_a6(conn, e, klm, chat_id: int, richter: Richter, kandidaten,
             bewertungen=None) -> dict | None:
    """A6 Tschechow -- EIN Aufruf am Ende, **nur** ueber die Kandidatenliste
    aus Schicht 1. None, wenn es keine Kandidaten gibt: dann gibt es nichts
    zu fragen, und ein Aufruf "prueft doch mal das ganze Stueck" waere genau
    der teure Aufruf, den die Vorfilterung spart."""
    if not kandidaten:
        return None
    material = material_kandidaten(kandidaten)
    nutzer = umschliesse("kandidaten", material, T._KOPF_KANDIDATEN)
    antwort, stand = _stelle(
        conn, e, klm, chat_id, richter, "a6", nutzer, material, "a6 Tschechow",
    )
    _merke(bewertungen, "a6", None, antwort, stand)
    return _befund_aus("a6", antwort, stand, szene=antwort.get("szene"))


def frage_c1(conn, e, klm, chat_id: int, richter: Richter, nummer: int,
             repliken, bewertungen=None) -> dict | None:
    """C1 Blind-Attribution fuer EINE Szene (M2).

    **Der Judge vergibt keinen Score** -- er ordnet zu, und die Trefferquote
    rechnet diese Funktion aus. Sie kennt die Ground Truth (die Labels, die
    ``mechanik.repliken`` gelesen hat) und gibt sie nie in den Prompt."""
    echte = [r for r in repliken
             if mechanik._schluessel(r.label) not in mechanik.KOLLEKTIVE]
    figuren = list(dict.fromkeys(r.label for r in echte))
    if len(echte) < C1_REPLIKEN_MIN or len(figuren) < C1_FIGUREN_MIN:
        return None

    material = material_repliken(echte)
    kopf = T._KOPF_REPLIKEN.format(nummer=nummer, figuren=", ".join(figuren))
    nutzer = umschliesse("repliken", material, kopf)
    system = prompt("c1")
    zuordnung: dict[int, str] = {}

    def aufruf(hinweis):
        nonlocal zuordnung
        text = nutzer if not hinweis else f"{nutzer}\n\n{hinweis}"
        zuordnung, rest = zerlege_zuordnung(
            richter.frage(conn, e, klm, chat_id, system, text, ARTEN["c1"])
        )
        return rest

    antwort, stand = beleg_modul.hole_mit_beleg(
        aufruf, material, f"c1 Szene {nummer}"
    )
    if not zuordnung:
        # **Keine Zuordnung ist kein Score 0.** Ohne Zuordnung waere die
        # Trefferquote null und der Befund "die Figuren klingen alle gleich" --
        # ein Urteil ueber den Parser oder einen abgebrochenen Aufruf, das als
        # Urteil ueber das Stueck in den Chat ginge.
        log.warning(
            "C1 Szene %s: keine Zuordnung in der Antwort, kein Befund", nummer
        )
        return None
    richtig = sum(
        1 for i, r in enumerate(echte, start=1)
        if mechanik._schluessel(zuordnung.get(i, "")) == mechanik._schluessel(r.label)
    )
    quote = richtig / len(echte)
    score = (
        2 if quote >= C1_SCHWELLE_GUT
        else 1 if quote >= C1_SCHWELLE_MITTEL
        else 0
    )
    if score == 2:
        # Erfuellt: kein Befund -- aber sehr wohl eine Bewertung. Genau diese
        # Zwei ist es, deren Absturz in der naechsten Runde zeigt, dass eine
        # Ueberarbeitung geschadet hat.
        _merke(bewertungen, "c1", nummer, {"score": score}, stand)
        return None

    paar = _verwechseltes_paar(echte, zuordnung) or figuren[:2]
    antwort = dict(antwort)
    antwort["score"] = None if stand.unsicher else score
    _merke(bewertungen, "c1", nummer, antwort, stand)
    # Score 0 heisst "die Figuren sind nicht auseinanderzuhalten" -- fuer eine
    # Laiengruppe ein Befund, an dem eine ganze Szene haengt. Score 1 wird in
    # ``_befund_aus`` ohnehin zum ``verdacht``.
    antwort["schwere"] = "hoch"
    antwort["befund"] = T._C1_BEFUND.format(
        repliken=len(echte), nummer=nummer, richtig=richtig,
    )
    antwort["vorschlag"] = T._C1_VORSCHLAG.format(
        nummer=nummer, erste=paar[0], zweite=paar[1],
    )
    return _befund_aus("c1", antwort, stand, szene=nummer, figur=paar[0])


#: Befund und Umbauvorschlag der Blind-Attribution -- im Code gebaut, nicht
#: vom Modell (siehe ``frage_c1``).
_C1_BEFUND = (
    "Von {repliken} Repliken in Szene {nummer} liessen sich {richtig} "
    "der richtigen Figur zuordnen, als die Namen weg waren."
)
_C1_VORSCHLAG = (
    "Szene {nummer}: {erste} und {zweite} klingen austauschbar. Gib "
    "{erste} ein eigenes Sprachmerkmal - kuerzere Saetze, ein "
    "Fuellwort, ein Abbruch - und schreib ihre Repliken in Szene "
    "{nummer} damit neu."
)


def _verwechseltes_paar(repliken, zuordnung) -> tuple[str, str] | None:
    """Das Figurenpaar, das am haeufigsten verwechselt wurde -- die Adresse
    des Umbauvorschlags. Deterministisch aus der Zuordnung, nicht vom
    Modell."""
    zaehler: dict[tuple[str, str], int] = {}
    for i, r in enumerate(repliken, start=1):
        geraten = (zuordnung.get(i) or "").strip()
        if not geraten:
            continue
        if mechanik._schluessel(geraten) == mechanik._schluessel(r.label):
            continue
        paar = tuple(sorted((r.label, geraten), key=mechanik._schluessel))
        zaehler[paar] = zaehler.get(paar, 0) + 1
    if not zaehler:
        return None
    return max(zaehler.items(), key=lambda p: (p[1], p[0]))[0]


def _merke(bewertungen, pruefung: str, szene, antwort: dict, stand) -> None:
    """Legt den Score dieser Frage fuer die Bilanz ab (Schicht 4).

    **Auch die Zwei.** ``_befund_aus`` gibt fuer einen erfuellten Score
    bewusst keinen Befund zurueck -- fuer die Frage, ob eine Ueberarbeitung
    geholfen hat, ist er aber die wichtigste Zahl: faellt eine Zwei auf eine
    Null, hat die Ueberarbeitung geschadet, und ohne die Zwei der Vorrunde
    saehe man nur einen neuen Befund und wuesste nicht, ob er neu ist.

    **Die Adresse ist die, unter der gefragt wurde**, nicht die, die der Judge
    nennt: A2 und A6 tragen in ihrer Antwort eine Szenennummer, laufen aber als
    EIN Aufruf ueber das ganze Stueck. Wuerde die Bilanz diese Nummer als
    Schluessel nehmen, verglichen zwei Runden verschiedene Dinge, sobald der
    Judge auf eine andere Szene zeigt.

    **Kein Score ohne bestaetigtes Belegzitat.** Ein verworfener Score
    (Recherche § 4) ist keine Note und geht deshalb auch nicht in die Bilanz;
    dieselbe Grenze wie beim Schreibauftrag."""
    if bewertungen is None:
        return
    if not stand.geprueft or antwort.get("unsicher"):
        return
    score = antwort.get("score")
    if score is None:
        return
    bewertungen.append(
        {"pruefung": pruefung, "szene": szene, "score": int(score)}
    )


def _befund_aus(schluessel: str, antwort: dict, stand, szene=None,
                figur=None) -> dict | None:
    """Aus einer geprueften Judge-Antwort ein Befund -- oder None.

    **Score 2 ist kein Befund.** Das Kriterium ist erfuellt; es gibt nichts
    zu melden, und eine Zeile "alles gut" in einer Befundliste ist Rauschen.
    Score 1 wird zum ``verdacht``, Score 0 traegt die Schwere des Judges.

    Ein unsicherer Befund (Beleg auch nach dem Retry nicht gefunden) bleibt
    erhalten, aber als ``hinweis`` mit ``beleg_geprueft = 0`` und ohne
    Vorschlag: er geht in die Liste und ins Log, nie an den Schreib-LLM."""
    score = antwort.get("score")
    if not stand.geprueft or antwort.get("unsicher"):
        text = antwort.get("befund") or T._KEIN_BELEG
        return {
            "pruefung": schluessel, "quelle": "judge", "schwere": "hinweis",
            "text": T._ZUSATZ_UNSICHER.format(text=text),
            "szene": szene, "figur": figur, "beleg": None, "beleg_geprueft": 0,
            "vorschlag": None, "prompt_version": version(schluessel),
        }
    if score is None or score >= 2:
        return None
    # Score 0 traegt die Schwere, die der Judge genannt hat; Score 1 ("teilweise
    # erfuellt") ist immer ein ``verdacht`` -- ein halb erfuelltes Kriterium ist
    # kein Blocker, egal wie dringlich das Modell klingt.
    schwere = (antwort.get("schwere") or "mittel") if score == 0 else "verdacht"
    return {
        "pruefung": schluessel, "quelle": "judge",
        "schwere": schwere,
        "text": antwort.get("befund") or T._KEIN_BEFUNDTEXT,
        "szene": szene, "figur": figur,
        "beleg": stand.beleg, "beleg_geprueft": 1,
        "vorschlag": antwort.get("vorschlag"),
        "richtung": antwort.get("richtung"),
        "prompt_version": version(schluessel),
    }


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


@dataclass
class Ergebnis:
    """Was ein Lauf zurueckgibt: Runde, Befunde, Bewertungen, Modellaufrufe.

    ``befunde`` sagt, was schieflaeuft; ``bewertungen`` sagt, wie **jede**
    Frage ausgegangen ist -- auch die erfuellte. Die Bilanz zwischen zwei
    Runden (``dramaturgie.schleife``) rechnet mit den Bewertungen und nie mit
    der Zahl der Befunde: ein guter Text erzeugt zu Recht keine Befunde."""

    runde: int = 0
    befunde: list = field(default_factory=list)
    bewertungen: list = field(default_factory=list)
    aufrufe: int = 0
    richter: Richter | None = None


def pruefe(conn, e, klm, chat_id: int, richter: Richter | None = None,
           runde: int | None = None) -> Ergebnis:
    """Der ganze Lauf: Mechanik, dann vier Judge-Fragen, dann speichern.

    **Seriell** (siehe ``GLEICHZEITIG``). Ein einzelner gescheiterter Aufruf
    reisst den Lauf nicht mit: er wird geloggt, bekommt einen Vorfall, und
    die uebrigen Fragen laufen weiter -- die Mechanik-Befunde und die Haelfte
    der Judge-Befunde sind mehr wert als gar nichts."""
    lage = mechanik.lies(conn, chat_id)
    if not lage.nummern:
        raise DramaturgieFehler(T.MELDUNG_OHNE_SZENEN)

    ergebnis = Ergebnis(richter=richter or waehle_richter(e, conn, chat_id))
    ergebnis.befunde = [b.als_dict() for b in mechanik.pruefe_alles(conn, chat_id, lage)]

    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, chat_id)
              if s["nummer"] is not None}

    for nummer in lage.nummern:
        _sammle(ergebnis, _versuch(
            conn, e, chat_id, f"b1 Szene {nummer}",
            lambda n=nummer: frage_b1(conn, e, klm, chat_id, ergebnis.richter,
                                      szenen[n], ergebnis.bewertungen),
        ))

    # A9 Fokus: dieselbe Adressierung wie B1 (eine Frage je Szene), aber mit
    # dem Hauptkonflikt als Massstab. Einmal gelesen, nicht je Szene.
    konflikt = mechanik.hauptkonflikt(conn, chat_id)
    for nummer in lage.nummern:
        _sammle(ergebnis, _versuch(
            conn, e, chat_id, f"a9 Szene {nummer}",
            lambda n=nummer: frage_a9(conn, e, klm, chat_id, ergebnis.richter,
                                      szenen[n], konflikt, ergebnis.bewertungen),
        ))

    # A10 Materialtreue: haelt die Szene ihre eigenen Festlegungen -- und
    # wenn nicht, zieht der Text nach oder der Parameter? Szenen ohne
    # Festlegungen fragt ``frage_a10`` selbst nicht.
    for nummer in lage.nummern:
        _sammle(ergebnis, _versuch(
            conn, e, chat_id, f"a10 Szene {nummer}",
            lambda n=nummer: frage_a10(conn, e, klm, chat_id, ergebnis.richter,
                                       szenen[n], ergebnis.bewertungen),
        ))

    _sammle(ergebnis, _versuch(
        conn, e, chat_id, "a2",
        lambda: frage_a2(conn, e, klm, chat_id, ergebnis.richter,
                         ergebnis.bewertungen),
    ))

    # A11 Stueckvorgaben: EIN Aufruf ueber dieselbe Synopsen-Kette wie A2 --
    # Format, Rahmen und Figurenzahl gelten fuer das Stueck, nicht je Szene.
    _sammle(ergebnis, _versuch(
        conn, e, chat_id, "a11",
        lambda: frage_a11(conn, e, klm, chat_id, ergebnis.richter,
                          ergebnis.bewertungen),
    ))

    for nummer in lage.mit_sprechern():
        _sammle(ergebnis, _versuch(
            conn, e, chat_id, f"c1 Szene {nummer}",
            lambda n=nummer: frage_c1(conn, e, klm, chat_id, ergebnis.richter,
                                      n, lage.repliken[n], ergebnis.bewertungen),
        ))

    _sammle(ergebnis, _versuch(
        conn, e, chat_id, "a6",
        lambda: frage_a6(conn, e, klm, chat_id, ergebnis.richter,
                         mechanik.tschechow_kandidaten(lage),
                         ergebnis.bewertungen),
    ))

    ergebnis.aufrufe = ergebnis.richter.aufrufe
    ergebnis.runde = runde or repo.letzte_dramaturgie_runde(conn, chat_id) + 1
    repo.lege_dramaturgie_befunde_an(
        conn, chat_id, ergebnis.befunde, runde=ergebnis.runde
    )
    # Die Scores derselben Runde -- getrennte Tabelle, gleiche Rundennummer.
    # Sie sind die Datenbankform der Bilanz (``dramaturgie.schleife``): aus
    # zwei Runden Scores laesst sich der Vergleich jederzeit neu rechnen, aus
    # einem abgelegten Vergleich nie wieder die Messung.
    repo.lege_dramaturgie_bewertungen_an(
        conn, chat_id, ergebnis.bewertungen, runde=ergebnis.runde
    )
    return ergebnis


#: Die Texte eines Judge-Befunds, wenn das Modell selbst keinen lieferte
#: oder der Beleg nicht bestaetigt ist.
_KEIN_BELEG = "Der Judge fand keinen Beleg im Text."
_ZUSATZ_UNSICHER = "{text} (Belegzitat nicht bestaetigt - Bewertung verworfen.)"
_KEIN_BEFUNDTEXT = "(kein Befundtext)"


def _versuch(conn, e, chat_id, marke, funktion):
    """Ein Aufruf, dessen Scheitern nur diesen einen Befund kostet."""
    try:
        return funktion()
    except Exception:  # noqa: BLE001 -- ein Aufruf reisst den Lauf nicht mit
        log.exception("Dramaturgie-Aufruf %s gescheitert, chat_id=%s", marke, chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "dramaturgie_aufruf_fehlgeschlagen", f"{marke} gescheitert",
            )
        except Exception:
            log.exception("Vorfall zur Dramaturgie nicht geschrieben")
        return None


def _sammle(ergebnis: Ergebnis, befund) -> None:
    if befund is not None:
        ergebnis.befunde.append(befund)


# ---------------------------------------------------------------------------
# Aggregation: aus Befunden werden Auftraege
# ---------------------------------------------------------------------------


def auftraege(befunde, figuren=()) -> list[dict]:
    """Aus Befunden werden Ueberarbeitungsauftraege -- **nicht gemittelt**.

    Recherche § 3: jeder harte Befund und jeder Judge-Score 0 mit hoher
    Schwere ergibt **genau einen** Auftrag, adressiert an eine Szene, mit dem
    konkreten Umbauvorschlag als Anweisung. Ein Mittelwert ueber Befunde
    verschiedener Ebenen sagt nichts: "1,4" ist keine Anweisung an eine Szene.

    **Hoechstens drei je Szene und Runde**, priorisiert nach Schwere, dann
    Ebene (Geschichte vor Szene vor Stimme) -- sonst ueberschreibt der
    Schreib-LLM sich selbst.

    Ein Befund ohne Szene (Sprechanteil, Formverteilung ueber das ganze
    Stueck) erzeugt keinen Auftrag: es gibt keine Adresse. Er steht trotzdem
    in der Liste und im Chat -- die Gruppe entscheidet, was daraus folgt."""
    kandidaten = []
    for b in befunde:
        szene = b.get("szene") if isinstance(b, dict) else b["szene"]
        if szene is None:
            continue
        quelle = _feld(b, "quelle")
        schwere = (_feld(b, "schwere") or "").lower()
        vorschlag = (_feld(b, "vorschlag") or "").strip()
        text = (_feld(b, "text") or "").strip()
        if quelle == "mechanik":
            if schwere != "hart":
                continue
            anweisung = vorschlag or text
        else:
            if schwere not in ("blocker", "hoch"):
                continue
            # **Eine Parameterkorrektur ist kein Auftrag an den Schreiber.**
            # Bei ``richtung=parameter`` sagt der Judge, dass der TEXT recht
            # hat und die Festlegung veraltet ist (A10). Wer das an den
            # Schreib-LLM gaebe, liesse ihn den Text auf eine ueberholte
            # Planung zurueckbiegen -- also genau das Gegenteil dessen, was
            # der Befund meint. Der Weg dafuer ist ``parameterkorrektur``,
            # und der endet bei der Gruppe, nicht beim Modell.
            if _feld(b, "richtung") == "parameter":
                continue
            if not beleg_modul.darf_an_den_schreiber(dict(
                beleg_geprueft=_feld(b, "beleg_geprueft"),
                unsicher=False, szene=szene, vorschlag=vorschlag,
            ), figuren):
                continue
            anweisung = vorschlag
        if not anweisung:
            continue
        kandidaten.append({
            "szene": int(szene),
            "pruefung": _feld(b, "pruefung"),
            "schwere": schwere,
            "anweisung": anweisung,
            "befund_id": _feld(b, "id"),
        })

    kandidaten.sort(key=lambda a: (
        SCHWERE_RANG.get(a["schwere"], 9),
        EBENEN.get(a["pruefung"], 9),
        a["szene"],
    ))
    je_szene: dict[int, int] = {}
    ergebnis = []
    for auftrag in kandidaten:
        zahl = je_szene.get(auftrag["szene"], 0)
        if zahl >= AUFTRAEGE_JE_SZENE:
            continue
        je_szene[auftrag["szene"]] = zahl + 1
        ergebnis.append(auftrag)
    ergebnis.sort(key=lambda a: (a["szene"], SCHWERE_RANG.get(a["schwere"], 9)))
    return ergebnis


def _feld(zeile, name):
    """Ein Feld aus einem Dict oder einer ``sqlite3.Row`` -- der Aufrufer soll
    beides uebergeben duerfen (frischer Lauf bzw. Datenbank)."""
    if isinstance(zeile, dict):
        return zeile.get(name)
    try:
        return zeile[name]
    except (IndexError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------

TEXT_BEFUND = "Szene {szene}: {text}"
TEXT_BEFUND_OHNE_SZENE = "{text}"
TEXT_AUFTRAG_KNOPF = "Szene {nummer} so ueberarbeiten"
#: Was vor der Regie-Notiz steht, wenn der Befund keine Pruefung nennt.
_DRAMATURGIE = "Dramaturgie"


def befundzeile(zeile) -> str:
    """Eine Zeile je Befund, mit Szenennummer davor.

    **Ohne Belegzitat.** Das Zitat ist der Nachweis fuer den Code, nicht der
    Text fuer die Gruppe -- und ein Zitat, dessen Pruefung nicht bestanden
    hat, darf nirgends stehen, wo Belegzitate stehen (dieselbe Grenze wie bei
    den Verdichtungen)."""
    text = (_feld(zeile, "text") or "").strip()
    szene = _feld(zeile, "szene")
    if szene is None:
        return T.TEXT_BEFUND_OHNE_SZENE.format(text=text)
    return T.TEXT_BEFUND.format(szene=szene, text=text)


def regienotiz(zeile) -> str:
    """Was als Regie-Notiz in den Szenenauftrag geht, wenn die Gruppe "Szene N
    so ueberarbeiten" drueckt -- mit der Pruefung davor, damit im Auftrag
    steht, WORAUF sie zielt (wie ``stueckpruefung.regienotiz``).

    Nimmt einen **Befund** (Feld ``vorschlag``, so kommt er aus der Datenbank)
    oder einen **Auftrag** aus ``auftraege()`` (Feld ``anweisung``, so kommt er
    aus der Schleife). Beides ist derselbe Satz unter zwei Namen; ihn zweimal
    zu formulieren waere ein zweiter Wortlaut fuer denselben Weg."""
    vorschlag = (
        (_feld(zeile, "vorschlag") or _feld(zeile, "anweisung") or "").strip()
    )
    pruefung = _feld(zeile, "pruefung") or T._DRAMATURGIE
    return f"{pruefung}: {vorschlag}" if vorschlag else str(
        (_feld(zeile, "text") or "").strip() or pruefung
    )


def szenenauftrag(zeile) -> str:
    """Der fertige Auftragstext fuer ``szene.schreibe`` -- aus einem Befund
    (Knopfweg) oder einem Auftrag (Schleifenweg).

    Bis zur Nachbesserung von Aufgabe 23 (Review-Befund 3) stand hier eine
    eigene Konstante ``TEXT_SZENENAUFTRAG``, wortgleich zu
    ``szene.TEXT_AUFTRAG_NEU`` -- zwei Stellen mit demselben Wortlaut, von
    denen eine irgendwann die andere nicht mehr mitbekommen haette. Jetzt
    wird an die eine Quelle delegiert (lokaler Import, wie ueberall im Repo
    gegen den Zyklus -- ``szene`` heisst hier ueberall sonst die einzelne
    Szenenzeile, nicht das Modul)."""
    from interview_theater import szene

    return szene.T.TEXT_AUFTRAG_NEU.format(
        nummer=_feld(zeile, "szene"), notiz=regienotiz(zeile)
    )


# ---------------------------------------------------------------------------
# Der Thread
# ---------------------------------------------------------------------------


def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: pruefen, die Befunde in den Chat legen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still (SPEC § 11.1) --
    sie wartet gerade darauf."""
    from interview_theater import knoepfe

    runde = 0
    try:
        ergebnis = pruefe(conn, e, klm, chat_id)
        runde = ergebnis.runde
    except (RichterFehler, DramaturgieFehler) as fehler:
        _sende(conn, tg, e, chat_id, str(fehler))
    except Exception:
        log.exception("Dramaturgie-Pruefung fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "dramaturgie_fehlgeschlagen", "Dramaturgie-Pruefung fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zur Dramaturgie nicht schreibbar")
        _sende(conn, tg, e, chat_id, T.MELDUNG_FEHLGESCHLAGEN)
    else:
        try:
            knoepfe.zeige_dramaturgie(conn, tg, chat_id, runde)
        except Exception:
            log.exception("Befunde nicht zustellbar, chat_id=%s", chat_id)
    if nachbereitung is not None:
        try:
            nachbereitung()
        except Exception:
            log.exception("Nachbereitung der Dramaturgie gescheitert, chat_id=%s",
                          chat_id)


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Meldung der Dramaturgie fehlgeschlagen, chat_id=%s", chat_id)


def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt die Pruefung an einen eigenen Thread ab -- dasselbe Muster wie
    ``stueckpruefung.starte`` (Zusage 2: kein Modellaufruf in einem
    Knopf-Handler). Liefert den Thread (fuer Tests) oder None."""
    if klm is None:
        log.error("Dramaturgie-Pruefung ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
    )
    thread.start()
    return thread


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

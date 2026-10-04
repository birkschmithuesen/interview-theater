"""Die Zaehler der Begriffsboard-Inhaltsmessung (Karte t_2b9d2cbe) -- rein,
offline getestet (``tests/test_begriffsboard_inhalt_zaehler.py``). Kein Netz,
keine Datenbank, kein Modell. Der Messlauf steht in
``scripts/rauchtest_begriffsboard_inhalt.py``."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from interview_theater import begriffsboard

FAELLE_VERZ = Path(__file__).resolve().parent.parent / "simulation" / "begriffsboard_faelle"
ERFUNDEN = ("ansage_en", "deutsch_stt", "schaerfung_stt_en")

ZAEHLER = ("fuell_begruendungen", "begruendung_ohne_beleg", "meta_begriffe",
           "dubletten", "sprache_ungleich_profil", "begriffe_fehlend")
INFO = ("eintraege", "begruendungen_belegt")

#: Merge-/STT-Spuren in einer Begruendung (D3) -- casefold.
_SPUR = re.compile(r"\b(aufgegangen|zusammengeführt|zusammengefuehrt|verhört|verhoert"
                   r"|verhörer|verhoerer|merged|misheard|mishearing|stt)\b")

#: Deterministische Sprachheuristik: Funktionswoerter, die nur in einer der
#: beiden Sprachen vorkommen ("was", "die", "an" stehen deshalb in keiner).
_DE = frozenset("der das und ist nicht wird mit für fuer ein eine sich auch als von zu "
                "den dem sie er es im auf weil dass wie wo oder aber noch nur sehr hat "
                "haben werden wurde ihr ihre gruppe will".split())
_EN = frozenset("the and is of to it with for as that this are be by not they their "
                "because when what where or but only very has have group wants".split())
_UMLAUT = re.compile(r"[äöüß]")


@dataclass(frozen=True)
class Fall:
    name: str
    beschreibung: str
    sprache_gesprochen: str
    segmente: tuple[str, ...]
    soll: tuple[tuple[str, ...], ...]
    varianten: tuple[str, ...]
    meta: tuple[str, ...]
    mit_grund: tuple[str, ...]


def lade_fall(pfad: Path) -> Fall:
    with open(pfad, "rb") as f:
        d = tomllib.load(f)
    return Fall(
        name=d["name"], beschreibung=d["beschreibung"],
        sprache_gesprochen=d["sprache_gesprochen"],
        segmente=tuple(d["segmente"]),
        soll=tuple(tuple(g["alternativen"]) for g in d["soll"]),
        varianten=tuple(d.get("varianten", ())), meta=tuple(d.get("meta", ())),
        mit_grund=tuple(d.get("mit_grund", ())),
    )


def lade_erfundene() -> list[Fall]:
    return [lade_fall(FAELLE_VERZ / f"{name}.toml") for name in ERFUNDEN]


def sprache_von(text: str | None) -> str:
    k = begriffsboard.schluessel(text)
    woerter = re.findall(r"\w+", k)
    de = sum(w in _DE for w in woerter) + 2 * len(_UMLAUT.findall(k))
    en = sum(w in _EN for w in woerter)
    if de > en:
        return "de"
    if en > de:
        return "en"
    return ""


def _trifft(begriff: str, alternativen) -> bool:
    k = begriffsboard.schluessel(begriff)
    return any(k == begriffsboard.schluessel(a) for a in alternativen)


def zaehle(board: list[dict], transkript: str, fall: Fall, profilsprache: str) -> dict[str, int]:
    meta = {begriffsboard.schluessel(m) for m in fall.meta}
    zahl = dict.fromkeys(ZAEHLER + INFO, 0)
    zahl["eintraege"] = len(board)
    for e in board:
        grund = (e.get("begruendung") or "").strip()
        if grund and begriffsboard.ist_fuellsatz(grund):
            zahl["fuell_begruendungen"] += 1
        if grund and not begriffsboard.traegt_beleg(e, transkript):
            zahl["begruendung_ohne_beleg"] += 1
        if grund and begriffsboard.traegt_beleg(e, transkript):
            zahl["begruendungen_belegt"] += 1
        if (begriffsboard.ist_metabegriff(e.get("begriff"))
                or begriffsboard.schluessel(e.get("begriff")) in meta):
            zahl["meta_begriffe"] += 1
        if _trifft(e.get("begriff", ""), fall.varianten):
            zahl["dubletten"] += 1
        if _SPUR.search(begriffsboard.schluessel(grund)):
            zahl["dubletten"] += 1
        for feld in ("begruendung", "doppelbedeutung"):
            s = sprache_von(e.get(feld))
            if (e.get(feld) or "").strip() and s and s != profilsprache:
                zahl["sprache_ungleich_profil"] += 1
    for gruppe in fall.soll:
        treffer = sum(_trifft(e.get("begriff", ""), gruppe) for e in board)
        if treffer == 0:
            zahl["begriffe_fehlend"] += 1
        else:
            zahl["dubletten"] += treffer - 1
    return zahl


def summe(zaehlungen: list[dict[str, int]]) -> dict[str, int]:
    gesamt: dict[str, int] = {}
    for z in zaehlungen:
        for k, v in z.items():
            gesamt[k] = gesamt.get(k, 0) + v
    return gesamt


def tabelle(messungen: list[dict]) -> str:
    """Eine Markdown-Tabelle: je Fall eine Zeile je (Arm, Modell, Runde,
    Stufe), Spalten = Zaehler + Info. Summen ueber die Laeufe."""
    spalten = ZAEHLER + INFO
    zeilen = ["| Fall | Arm | Modell | Runde | Stufe | Läufe/Fehler | " + " | ".join(spalten) + " |",
              "|" + "---|" * (6 + len(spalten))]
    for m in messungen:
        for fall, d in m["faelle"].items():
            for stufe in ("roh", "validiert"):
                werte = " | ".join(str(d[stufe].get(s, 0)) for s in spalten)
                zeilen.append(f"| {fall} | {m['arm']} | {m['modell']} | {m['runde']} | {stufe} | "
                              f"{d['laeufe']}/{d['fehler']} | {werte} |")
    return "\n".join(zeilen)

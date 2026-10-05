"""Rauchtest der Resonanz- und Analyse-Schicht des Begriffsboards (Karte
t_9258d2e9, Plan docs/superpowers/plans/2026-10-04-padua-begriffsboard-resonanz.md).

**Kein Test, laeuft nie automatisch, kostet Geld.** Braucht echte
Zugangsdaten (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL, ...) in der Umgebung und
Netzzugriff. Seine ``aufruf``-Zeilen landen in einer Wegwerf-Datenbank, nie
in ``IT_DB``.

Sieben erfundene Faelle (EN, Profil padua-2026), vier Aufrufarten:

- ``board``: der echte Board-Prompt -- ausgewertet als Arm A (nur Modell,
  ``sortiert`` ohne Resonanz) UND, ohne weiteren Aufruf, als Arm B (Modell +
  Resonanz), sobald ``interview_theater/begriffsboard_resonanz.py`` existiert.
- ``prompt_nur`` (Arm D): derselbe Prompt, die Mehrheitsregel fuer Verhoerer
  durch "Sinn zuerst" ersetzt -- NUR hier, nie in den Prompt-Dateien.
- ``analyse`` (Arm C): ``begriffsboard_analyse`` mit beiden Fragen.
- ``verhoerer`` (Arm E): ``begriffsboard_analyse`` nur mit der Verhoerer-Frage.

Jeder Aufruf wird eine Zeile in ``--roh`` (JSONL unter korpus/berichte/,
gitignored: dort stehen vollstaendige Modellantworten). ``--auswerten``
rechnet alles daraus, ohne einen Aufruf. Das Kartenbudget ``--deckel``
(Vorgabe 200) zaehlt die Zeilen dort mit: das Skript bricht VOR dem ersten
Aufruf ab, wenn bisher + geplant darueber laegen.

Aufruf:
    python -m scripts.rauchtest_begriffsboard_resonanz --arme board --modell gespraech --trocken
    python -m scripts.rauchtest_begriffsboard_resonanz --arme board,prompt_nur,analyse,verhoerer --modell gespraech
    python -m scripts.rauchtest_begriffsboard_resonanz --arme analyse,verhoerer --modell erkenner
    python -m scripts.rauchtest_begriffsboard_resonanz --auswerten --bericht docs/begriffsboard-resonanz/rauchtest-tabellen.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import begriffsboard, brainstorm, kosten  # noqa: E402
from interview_theater import begriffsboard_analyse as analyse  # noqa: E402
from scripts.rauchtest_begriffsboard import FAELLE as _FAELLE_ALT  # noqa: E402

ROH_VORGABE = "korpus/berichte/begriffsboard_resonanz_roh.jsonl"
DECKEL_VORGABE = 200
WIEDERHOLUNGEN_VORGABE = 5
#: 4 von 5 (D6): ab diesem Anteil gilt ein Fall als bestanden.
SCHWELLE = 0.8
ARME = ("board", "prompt_nur", "analyse", "verhoerer")
#: Nur die zwei Modelle, die die Umgebung schon konfiguriert (Plan, D7).
MODELL_ALIAS = {"gespraech": "llm_modell", "erkenner": "erkenner_modell"}

TEXT_PRAEMISSE_WIDERLEGT = "Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle"
TEXT_PRAEMISSE_BESTAETIGT = "Praemisse bestaetigt: Arm A scheitert an (b) oder (c) -- D4 (Resonanz) wird gebaut"
TEXT_VERHOERER_REICHT = "Verhoerer: Mehrheitsregel scheitert in diesem Fall nicht, kein Zusatzaufruf noetig"
TEXT_VERHOERER_SCHEITERT = "Verhoerer: Mehrheitsregel scheitert in (e) -- Arme D/C/E entscheiden, Zahlen an Birk"

#: Wortlisten fuer die Pruefung -- englisch UND die deutsche Antwort, die
#: das Modell trotz EN-Prompt manchmal gibt (Sprachfund, NICHT Teil dieser
#: Karte; wie ``_finde`` im bestehenden Rauchtest).
OZEAN, GARTEN = ("ocean", "ozean"), ("garden", "garten")
LEUCHTTURM, MOTORRAD = ("lighthouse", "leuchtturm"), ("motorbike", "motorrad")
BAHNHOF = ("station", "bahnhof")
WETTER, OB = ("weather", "wetter"), ("whether",)
BLUME = ("flower", "blume")
RITTER, NACHT = ("knight", "ritter"), ("night", "nacht")

FAELLE = {
    "a_rezenz": {
        "segmente": [_FAELLE_ALT["rezenz_statt_haeufigkeit"]["transkript"]],
        "arme": {"board", "analyse"},
        "board_analyse": ["garden", "ocean"],
    },
    "b_konsens": {
        "segmente": [
            "What about a lighthouse? A lighthouse at the edge of town, like the one "
            "from the school trip.",
            "Yes, exactly, the lighthouse. I agree, the lighthouse feels like us. "
            "Let's go with the lighthouse.",
            "I still think the motorbike. The motorbike is cool. A motorbike, a loud "
            "motorbike racing down the street. The motorbike again, the motorbike.",
        ],
        "arme": {"board", "analyse"},
        "board_analyse": ["lighthouse", "motorbike"],
    },
    "c_abgelehnt": {
        "segmente": [
            "Maybe the garden. A garden behind the house, with old trees.",
            "The garden could work. And what about the station, the old train "
            "station at night?",
            "Yes, the station. I like that.",
            "No, not the garden. I don't think the garden works for us, it is too quiet.",
        ],
        "arme": {"board", "analyse"},
        "board_analyse": ["garden", "station"],
    },
    "d_kontrolle": {
        "segmente": [
            "We talked about the river and the bridge. The river runs through the old "
            "part of town.",
            "The bridge is where people meet in the evening. The river is loud in spring.",
            "The bridge and the river, both from our neighbourhood.",
        ],
        "arme": {"board"},
        "board_analyse": ["river", "bridge"],
    },
    "e_verhoerer": {
        "segmente": [
            "The whether in our story should change all the time. First sun, then "
            "heavy rain.",
            "And a storm at the end. The whether gets worse and worse, wind and thunder.",
            "The weather is like the mood of the family. When the whether turns, they fight.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        # Was die Mehrheitsregel (3:1) heute auf dem Board liesse.
        "board_analyse": ["whether", "rain", "storm"],
    },
    "f_kontrolle_mehrheit": {
        "segmente": [
            "Flowers everywhere on stage. The flower stall of the grandmother is the "
            "centre of it.",
            "She sells one flower to every customer, a red flower for each person.",
            "At the end she gives her last flour to the boy, the last flower she has.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        "board_analyse": ["flower", "flour", "grandmother"],
    },
    "g_zwei_begriffe": {
        "segmente": [
            "I want a knight in the story, a knight in old armour who is lost in our city.",
            "And everything happens at night. The night is when the city feels different.",
            "So the knight walks through the city at night, and nobody believes him.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        "board_analyse": ["knight", "night", "city"],
    },
}
RANGFAELLE = ("a_rezenz", "b_konsens", "c_abgelehnt")
VERHOERFAELLE = ("e_verhoerer", "f_kontrolle_mehrheit", "g_zwei_begriffe")
OBEN_UNTEN = {"a_rezenz": (OZEAN, GARTEN), "b_konsens": (LEUCHTTURM, MOTORRAD)}

#: Die Mehrheitsregel im EN-Board-Prompt, Anfang und Ende woertlich
#: (``interview_theater/sprachen/en/prompts/begriffsboard.md``, Stand nach
#: 9113cb7 -- "Decide by majority AND context plausibility together").
#: Der Block endet seit 9113cb7 (t_2b9d2cbe, Aufgabe 6: Belegpflicht der
#: Begruendung) wieder mit "deletes a real term." statt mit dem
#: nachgestellten Beispielsatz "heard correctly three times." -- die
#: Korrektur-Notiz im Absatz danach wurde ersatzlos gestrichen (keine
#: Korrektur mehr in begruendung).
_MEHRHEIT_ANFANG = "Decide by majority AND context plausibility together, not by majority\nalone:"
_MEHRHEIT_ENDE = "deletes a real term."
VARIANTE_SINN_ZUERST = (
    "Decide by meaning first: look at what the group is talking about around "
    "each of the two spellings. Keep as ``begriff`` the reading that makes "
    "sense in that conversation, even if the other spelling occurs more often "
    "in the transcript -- a mishearing that repeats is still a mishearing. "
    "Drop the other reading entirely, add both mention counts into the "
    "remaining entry and note the correction briefly in ``begruendung``. Only "
    "when both readings make equal sense, keep the spelling with the higher "
    "count; if the count is tied as well, keep both separate for now rather "
    "than guessing -- a wrong call here deletes a real\nterm."
)

#: Hochrechnung (Plan, Abschnitt "Kosten und Latenz"). ANNAHME: ~130
#: gesprochene Woerter je Minute x ~6 Zeichen.
REFERENZ_MINUTEN = 45
ZEICHEN_JE_MINUTE = 780


def transkript(fall: str) -> str:
    """Wie ``repo.diskussion_transkript``: Segmente mit Leerzeile verbunden."""
    return "\n\n".join(FAELLE[fall]["segmente"])


def auftraege(arme, faelle, wiederholungen: int) -> list[tuple[str, str, int]]:
    for arm in arme:
        if arm not in ARME:
            raise SystemExit(f"Unbekannter Arm: {arm} (erlaubt: {', '.join(ARME)})")
    return [(arm, fall, w) for arm in arme for fall in FAELLE
            if (not faelle or fall in faelle) and arm in FAELLE[fall]["arme"]
            for w in range(1, wiederholungen + 1)]


def prompt_nur(system: str) -> str:
    """Arm D: den (seit 41d96c6 hybriden Mehrheit+Kontext-)Verhoererblock durch
    "Sinn zuerst" ersetzt, sonst Zeichen fuer Zeichen der echte Prompt. Bleibt
    als Vergleich sinnvoll: die Variante entscheidet NUR nach Sinn (Mehrheit
    zaehlt nur beim echten Gleichstand), waehrend der echte Prompt Mehrheit UND
    Kontext zusammen gewichtet -- ob der Hybrid den reinen Sinn-Ansatz noch
    braucht, ist genau die Frage dieses Arms. Fehlt der Anker, ist der Prompt
    geaendert worden -- dann lieber kein Aufruf als ein Vergleich gegen etwas
    anderes."""
    anfang = system.find(_MEHRHEIT_ANFANG)
    ende = system.find(_MEHRHEIT_ENDE, anfang if anfang >= 0 else 0)
    if anfang < 0 or ende < 0:
        raise ValueError("Mehrheitsregel im Board-Prompt nicht gefunden -- Prompt geaendert?")
    return system[:anfang] + VARIANTE_SINN_ZUERST + system[ende + len(_MEHRHEIT_ENDE):]


def eingabe(arm: str, fall: str, board_prompt: str) -> tuple[str, str, dict, str]:
    """(system, nutzer, schema, art) eines Aufrufs."""
    tr = transkript(fall)
    if arm == "board":
        return board_prompt, begriffsboard._nutzertext(tr, []), begriffsboard.SCHEMA, "rauchtest_resonanz_board"
    if arm == "prompt_nur":
        return (prompt_nur(board_prompt), begriffsboard._nutzertext(tr, []), begriffsboard.SCHEMA,
                "rauchtest_resonanz_prompt_nur")
    teile = analyse.TEILE if arm == "analyse" else ("verhoerer",)
    board = [{"begriff": b} for b in FAELLE[fall]["board_analyse"]]
    return analyse.anweisung(teile), analyse.nutzertext(tr, board), analyse.schema_fuer(teile), analyse.art_fuer(teile)


# -- Pruefung (rein) ----------------------------------------------------------

def _wort(namen, text) -> bool:
    t = str(text or "").casefold()
    return any(re.search(r"(?<!\w)" + re.escape(n.casefold()) + r"(?!\w)", t) for n in namen)


def _indizes(eintraege: list[dict], namen) -> set[int]:
    return {i for i, e in enumerate(eintraege) if _wort(namen, e.get("begriff"))}


def _rang(reihe: list[dict], namen) -> int | None:
    treffer = _indizes(reihe, namen)
    return min(treffer) if treffer else None


def pruefe_reihe(fall: str, reihe: list[dict]) -> bool | None:
    """Rangfaelle (a, b, c) an einer ``sortiert``-Reihe."""
    if fall in OBEN_UNTEN:
        oben, unten = OBEN_UNTEN[fall]
        ro, ru = _rang(reihe, oben), _rang(reihe, unten)
        return ro is not None and ru is not None and ro < ru
    if fall == "c_abgelehnt":
        return bool(reihe) and not _wort(GARTEN, reihe[0].get("begriff"))
    return None


def pruefe_board_verhoerer(fall: str, eintraege: list[dict]) -> bool | None:
    """Verhoerer-Faelle (e, f, g) an einer Boardantwort (Arme A und D)."""
    if fall == "e_verhoerer":
        return bool(_indizes(eintraege, WETTER)) and not _indizes(eintraege, OB)
    if fall == "f_kontrolle_mehrheit":
        return bool(_indizes(eintraege, BLUME))
    if fall == "g_zwei_begriffe":
        return any(i != j for i in _indizes(eintraege, RITTER) for j in _indizes(eintraege, NACHT))
    return None


def pruefe_verhoerer(fall: str, paare: list[dict]) -> bool | None:
    """Verhoerer-Faelle an der ``verhoerer``-Liste (Arme C und E)."""
    if fall == "e_verhoerer":
        return (any(_wort(OB, p["lesart_falsch"]) and _wort(WETTER, p["lesart_richtig"]) for p in paare)
                and not any(_wort(WETTER, p["lesart_falsch"]) for p in paare))
    if fall == "f_kontrolle_mehrheit":
        return not any(_wort(BLUME, p["lesart_falsch"]) for p in paare)
    if fall == "g_zwei_begriffe":
        return not any((_wort(RITTER, p["lesart_falsch"]) and _wort(NACHT, p["lesart_richtig"]))
                       or (_wort(NACHT, p["lesart_falsch"]) and _wort(RITTER, p["lesart_richtig"]))
                       for p in paare)
    return None


def pruefe_analyse(fall: str, ergebnis: dict) -> bool | None:
    """Arm C: Rangfaelle am ``wunsch``, Verhoerer-Faelle an ``verhoerer``."""
    w = ergebnis["wunsch"]
    if fall in OBEN_UNTEN:
        oben, unten = OBEN_UNTEN[fall][0][0], OBEN_UNTEN[fall][1][0]
        return oben in w and unten in w and w[oben] > w[unten]
    if fall == "c_abgelehnt":
        return "garden" in w and "station" in w and w["garden"] < w["station"]
    return pruefe_verhoerer(fall, ergebnis["verhoerer"])


def _ohne_resonanz(eintraege: list[dict]) -> list[dict]:
    return [{k: v for k, v in e.items() if k != "resonanz"} for e in eintraege]


def bewerte(zeile: dict, resonanz_modul=None) -> dict[str, bool | None]:
    """Eine Rohzeile -> {Arm-Kuerzel: bestanden}. ``None`` heisst "ohne
    Aussage" (Kontrolle d fuer Arm A, Arm B ohne Resonanzmodul oder auf den
    Verhoerer-Faellen) und zaehlt nicht in die Quote."""
    fall, arm, antwort = zeile["fall"], zeile["arm"], zeile.get("antwort")
    tr = transkript(fall)
    if arm in ("analyse", "verhoerer"):
        kuerzel = "C" if arm == "analyse" else "E"
        if not isinstance(antwort, dict):
            return {kuerzel: False}
        board = [{"begriff": b} for b in FAELLE[fall]["board_analyse"]]
        ergebnis = analyse.validiere(antwort, tr, board)
        urteil = pruefe_analyse(fall, ergebnis) if arm == "analyse" else pruefe_verhoerer(fall, ergebnis["verhoerer"])
        return {kuerzel: bool(urteil)}
    roh = antwort.get("board") if isinstance(antwort, dict) else None
    eintraege = begriffsboard.lies(json.dumps(roh if isinstance(roh, list) else []))
    if arm == "prompt_nur":
        return {"D": bool(pruefe_board_verhoerer(fall, eintraege)) if antwort is not None else False}
    reihe_a = begriffsboard.sortiert(_ohne_resonanz(eintraege))
    if fall in RANGFAELLE:
        a = bool(pruefe_reihe(fall, reihe_a)) if antwort is not None else False
    elif fall in VERHOERFAELLE:
        a = bool(pruefe_board_verhoerer(fall, eintraege)) if antwort is not None else False
    else:
        a = None
    if resonanz_modul is None or fall in VERHOERFAELLE:
        return {"A": a, "B": None}
    if antwort is None:
        return {"A": a, "B": False}
    mit = _ohne_resonanz(eintraege)
    resonanz_modul.trage_ein(mit, tr, code="en")
    reihe_b = begriffsboard.sortiert(mit)
    if fall in RANGFAELLE:
        b = bool(pruefe_reihe(fall, reihe_b))
    else:  # d_kontrolle: ohne Resonanzphrasen muss die Reihenfolge gleich bleiben
        werte = resonanz_modul.resonanz_je_begriff([e["begriff"] for e in eintraege], tr, code="en")
        b = ([begriffsboard.schluessel(e["begriff"]) for e in reihe_b]
             == [begriffsboard.schluessel(e["begriff"]) for e in reihe_a]
             and all(v == 0 for v in werte.values()))
    return {"A": a, "B": b}


def tabelle(zeilen: list[dict], resonanz_modul=None) -> dict[tuple[str, str, str], list[bool]]:
    t: dict[tuple[str, str, str], list[bool]] = {}
    for zeile in zeilen:
        for kuerzel, urteil in bewerte(zeile, resonanz_modul).items():
            if urteil is not None:
                t.setdefault((kuerzel, zeile["fall"], zeile["modell"]), []).append(bool(urteil))
    return t


def bestanden(t, kuerzel: str, fall: str, modell: str) -> bool:
    liste = t.get((kuerzel, fall, modell), [])
    return len(liste) >= WIEDERHOLUNGEN_VORGABE and sum(liste) >= SCHWELLE * len(liste)


def gate_ranking(t, modell: str) -> str:
    """D6: besteht Arm A (b) UND (c) in >= 4/5, wird D4 nicht gebaut."""
    if bestanden(t, "A", "b_konsens", modell) and bestanden(t, "A", "c_abgelehnt", modell):
        return TEXT_PRAEMISSE_WIDERLEGT
    return TEXT_PRAEMISSE_BESTAETIGT


def gate_verhoerer(t, modell: str) -> str:
    return TEXT_VERHOERER_REICHT if bestanden(t, "A", "e_verhoerer", modell) else TEXT_VERHOERER_SCHEITERT


# -- Messwerte und Hochrechnung -----------------------------------------------

def _mittel(werte) -> float:
    werte = list(werte)
    return statistics.mean(werte) if werte else 0.0


def messwerte(zeilen: list[dict]) -> dict[tuple[str, str], dict]:
    gruppen: dict[tuple[str, str], list[dict]] = {}
    for zeile in zeilen:
        gruppen.setdefault((zeile["arm"], zeile["modell"]), []).append(zeile)
    ergebnis = {}
    for schluessel, zs in gruppen.items():
        mit_token = [z for z in zs if z.get("eingabe_token")]
        ergebnis[schluessel] = {
            "aufrufe": len(zs),
            "fehler": sum(1 for z in zs if z.get("fehler")),
            "eingabe_token": _mittel(z["eingabe_token"] for z in mit_token),
            "ausgabe_token": _mittel(z.get("ausgabe_token") or 0 for z in mit_token),
            "dauer_ms_mittel": _mittel(z.get("dauer_ms") or 0 for z in zs),
            "dauer_ms_max": max((z.get("dauer_ms") or 0 for z in zs), default=0),
            "kosten_chf": sum(z.get("kosten_chf") or 0.0 for z in zs),
            "system_zeichen": _mittel(z.get("system_zeichen") or 0 for z in zs),
            "token_je_zeichen": _mittel(
                z["eingabe_token"] / max(1, (z.get("system_zeichen") or 0) + (z.get("nutzer_zeichen") or 0))
                for z in mit_token),
        }
    return ergebnis


def hochrechnung(*, system_zeichen: float, token_je_zeichen: float, ausgabe_token: float,
                 preis: tuple[float, float] | None, minuten: int = REFERENZ_MINUTEN,
                 zeichen_je_minute: int = ZEICHEN_JE_MINUTE) -> dict:
    """Ein Aufruf je Boardlauf, eine Diskussion von ``minuten``: Laeufe =
    min(Zeichen / 600, Sekunden / 90) (``begriffsboard.VORGABE_MIN_ZEICHEN``,
    ``brainstorm.VORGABE_MIN_ABSTAND_S``), jeder mit dem Transkript bis dahin
    (gedeckelt auf ``VORGABE_TRANSKRIPT_ZEICHEN``). ``preis`` je Mio Token
    (ein/aus) aus ``kosten.PREISE_CHF_JE_MIO_TOKEN``; ohne Preis kein Betrag."""
    zeichen = minuten * zeichen_je_minute
    aufrufe = max(1, min(zeichen // begriffsboard.VORGABE_MIN_ZEICHEN,
                         (minuten * 60) // brainstorm.VORGABE_MIN_ABSTAND_S))
    schritt = zeichen / aufrufe
    eingabe_zeichen = sum(system_zeichen + min(begriffsboard.VORGABE_TRANSKRIPT_ZEICHEN, schritt * k)
                          for k in range(1, aufrufe + 1))
    eingabe_token = eingabe_zeichen * token_je_zeichen
    gesamt_aus = aufrufe * ausgabe_token
    chf = None if preis is None else (eingabe_token * preis[0] + gesamt_aus * preis[1]) / 1_000_000
    return {"aufrufe": int(aufrufe), "eingabe_token": round(eingabe_token),
            "ausgabe_token": round(gesamt_aus), "chf": None if chf is None else round(chf, 4)}


def bericht(zeilen: list[dict], resonanz_modul=None) -> str:
    """Nur Zahlen -- kein Transkript, keine Modellantwort."""
    t = tabelle(zeilen, resonanz_modul)
    m = messwerte(zeilen)
    aus = [
        "# Rauchtest Begriffsboard-Resonanz (Karte t_9258d2e9)", "",
        f"Aufrufe in der Rohdatei: {len(zeilen)} · Resonanzmodul: "
        f"{'vorhanden' if resonanz_modul is not None else 'nicht gebaut'}", "",
        "## Trefferquote je Fall x Arm x Modell", "",
        "Arme: A nur Modell (heutiges sortiert) · B Modell + Resonanz (offline aus denselben "
        "Antworten) · C Analyse beide Fragen · D Board-Prompt 'Sinn zuerst' · E Analyse nur Verhoerer", "",
        "| Fall | Arm | Modell | bestanden |", "|---|---|---|---|",
    ]
    for kuerzel, fall, modell in sorted(t, key=lambda k: (k[1], k[0], k[2])):
        liste = t[(kuerzel, fall, modell)]
        aus.append(f"| {fall} | {kuerzel} | {modell} | {sum(liste)}/{len(liste)} |")
    aus += ["", "## Messwerte je Aufrufart x Modell", "",
            "| Aufruf | Modell | Aufrufe | Fehler | Eingabe-Token Mittel | Ausgabe-Token Mittel "
            "| Latenz ms Mittel / Max | Kosten CHF Summe |",
            "|---|---|---|---|---|---|---|---|"]
    for (arm, modell), w in sorted(m.items()):
        aus.append(f"| {arm} | {modell} | {w['aufrufe']} | {w['fehler']} | {w['eingabe_token']:.0f} "
                   f"| {w['ausgabe_token']:.0f} | {w['dauer_ms_mittel']:.0f} / {w['dauer_ms_max']} "
                   f"| {w['kosten_chf']:.4f} |")
    aus += ["", f"## Hochrechnung: ein Aufruf je Boardlauf, Diskussion von {REFERENZ_MINUTEN} min", "",
            f"ANNAHME {ZEICHEN_JE_MINUTE} Zeichen/min; Token je Zeichen gemessen; Preise "
            f"kosten.PREISE_CHF_JE_MIO_TOKEN (Stand {kosten.PREISE_STAND}).", "",
            "| Aufruf | Modell | Laeufe | Eingabe-Token | Ausgabe-Token | CHF |", "|---|---|---|---|---|---|"]
    for (arm, modell), w in sorted(m.items()):
        h = hochrechnung(system_zeichen=w["system_zeichen"], token_je_zeichen=w["token_je_zeichen"],
                         ausgabe_token=w["ausgabe_token"], preis=kosten.PREISE_CHF_JE_MIO_TOKEN.get(modell))
        chf = "kein Preis" if h["chf"] is None else f"{h['chf']:.4f}"
        aus.append(f"| {arm} | {modell} | {h['aufrufe']} | {h['eingabe_token']} | {h['ausgabe_token']} | {chf} |")
    aus += ["", "## Gates", ""]
    for modell in sorted({k[2] for k in t if k[0] == "A"}):
        aus.append(f"- Ranking ({modell}): {gate_ranking(t, modell)}")
        aus.append(f"- Verhoerer ({modell}): {gate_verhoerer(t, modell)}")
    return "\n".join(aus) + "\n"


# -- Rohdatei, Lauf, Aufruf ----------------------------------------------------

def lies_roh(pfad: str) -> list[dict]:
    p = Path(pfad)
    if not p.is_file():
        return []
    return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


def zaehle_roh(pfad: str) -> int:
    p = Path(pfad)
    return sum(1 for z in p.read_text(encoding="utf-8").splitlines() if z.strip()) if p.is_file() else 0


def _resonanz_modul():
    try:
        from interview_theater import begriffsboard_resonanz
    except ImportError:
        return None
    return begriffsboard_resonanz


def _git_kopf() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def modellname(alias: str, einst) -> str:
    return getattr(einst, MODELL_ALIAS[alias]) if alias in MODELL_ALIAS else alias


def _ein_aufruf(conn, klm, board_prompt: str, arm: str, fall: str, modell: str,
                wiederholung: int, kopf: str) -> dict:
    system, nutzer, schema, art = eingabe(arm, fall, board_prompt)
    vorher = conn.execute("SELECT max(id) AS m FROM aufruf").fetchone()["m"] or 0
    antwort = fehler = None
    start = time.monotonic()
    try:
        antwort = klm.schema(None, system, nutzer, schema, art, modell=modell)
    except Exception as ausnahme:  # noqa: BLE001 -- ein Fehlschlag ist ein Messwert
        fehler = f"{type(ausnahme).__name__}: {ausnahme}"[:300]
    wand_ms = int((time.monotonic() - start) * 1000)
    # Wie scripts/pruefe_prompts._aufruf_nach: llm.LLM._anfrage bucht im
    # ``finally``, also auch bei Fehlschlag.
    gebucht = conn.execute(
        "SELECT tatsaechliche_token, antwort_token, dauer_ms, kosten_chf FROM aufruf "
        "WHERE id > ? ORDER BY id DESC LIMIT 1", (vorher,),
    ).fetchone()
    return {
        "zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kopf": kopf,
        "arm": arm, "fall": fall, "modell": modell, "wiederholung": wiederholung,
        "system_zeichen": len(system), "nutzer_zeichen": len(nutzer),
        "antwort": antwort, "fehler": fehler,
        "eingabe_token": (gebucht["tatsaechliche_token"] or 0) if gebucht else 0,
        "ausgabe_token": (gebucht["antwort_token"] or 0) if gebucht else 0,
        "dauer_ms": (gebucht["dauer_ms"] or wand_ms) if gebucht else wand_ms,
        "kosten_chf": (gebucht["kosten_chf"] or 0.0) if gebucht else 0.0,
    }


def _laufe(plan, modelle, roh_pfad: str) -> int:
    import httpx

    from interview_theater import anweisungen, db, einstellungen, llm, sprache, workshop

    os.environ["IT_WORKSHOP"] = "padua-2026"
    workshop.vergiss()
    sprache.vergiss()
    einst = einstellungen.laden()
    board_prompt = anweisungen.hole("begriffsboard")
    kopf = _git_kopf()
    Path(roh_pfad).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rauchtest-resonanz-") as verzeichnis:
        conn = db.verbinde(str(Path(verzeichnis) / "wegwerf.db"))
        db.initialisiere(conn)
        try:
            with httpx.Client(timeout=120.0) as klient:
                klm = llm.LLM(einst, klient, conn)
                for alias in modelle:
                    modell = modellname(alias, einst)
                    for arm, fall, w in plan:
                        zeile = _ein_aufruf(conn, klm, board_prompt, arm, fall, modell, w, kopf)
                        with open(roh_pfad, "a", encoding="utf-8") as datei:
                            datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                        zustand = f"FEHLER {zeile['fehler']}" if zeile["fehler"] else "ok"
                        print(f"{arm} {fall} {modell} #{w}: {zustand} ({zeile['dauer_ms']} ms)", flush=True)
        finally:
            conn.close()
    print(bericht(lies_roh(roh_pfad), _resonanz_modul()))
    return 0


def _argumente(argv):
    p = argparse.ArgumentParser(description="Rauchtest Begriffsboard-Resonanz (kostet Geld)")
    p.add_argument("--arme", default="board", help=f"Komma-Liste aus {', '.join(ARME)}")
    p.add_argument("--modell", default="gespraech", help="Komma-Liste: gespraech, erkenner")
    p.add_argument("--faelle", default="", help="Komma-Liste aus FAELLE, leer = alle")
    p.add_argument("--wiederholungen", type=int, default=WIEDERHOLUNGEN_VORGABE)
    p.add_argument("--roh", default=ROH_VORGABE)
    p.add_argument("--deckel", type=int, default=DECKEL_VORGABE)
    p.add_argument("--trocken", action="store_true", help="nur planen, kein Aufruf")
    p.add_argument("--auswerten", action="store_true", help="nur die Rohdatei auswerten, kein Aufruf")
    p.add_argument("--bericht", default="", help="Tabellen zusaetzlich in diese Datei schreiben")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _argumente(argv)
    if args.auswerten:
        text = bericht(lies_roh(args.roh), _resonanz_modul())
        print(text)
        if args.bericht:
            Path(args.bericht).parent.mkdir(parents=True, exist_ok=True)
            Path(args.bericht).write_text(text, encoding="utf-8")
        return 0
    arme = [a for a in args.arme.split(",") if a]
    modelle = [m for m in args.modell.split(",") if m]
    faelle = {f for f in args.faelle.split(",") if f}
    plan = auftraege(arme, faelle, args.wiederholungen)
    geplant = len(plan) * len(modelle)
    bisher = zaehle_roh(args.roh)
    print(f"Geplant: {geplant} bezahlte Aufrufe ({len(plan)} je Modell x {len(modelle)} Modell(e)); "
          f"bisher in {args.roh}: {bisher}; Deckel: {args.deckel}")
    if bisher + geplant > args.deckel:
        print("ABBRUCH: das Kartenbudget wuerde ueberschritten -- kein Aufruf.")
        return 3
    if args.trocken:
        return 0
    return _laufe(plan, modelle, args.roh)


if __name__ == "__main__":
    sys.exit(main())

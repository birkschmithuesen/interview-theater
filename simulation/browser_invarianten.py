"""Deterministische Invarianten der Browser-Simulation — kein Richter, kein Modell.

Karte t_fc2c1bfa (05.10.2026): ein Symptom ist ein App-Fehler bis zum
Gegenbeweis. Jede verletzte Invariante wird ein Befund "hoch" mit der Ursache
"App oder Werkzeug – ungeklaert" und wird nie still als Werkzeugmangel
abgehakt (der Abnahmebericht vom 04.10. zeigte 165-mal "0 Begriffe" und
erklaerte es weg).

Liest die Simulations-DB nur lesend und mit eigenem SQL statt ueber `repo`:
die Simulation prueft auch aeltere App-Staende (Abnahme gegen cb200e4), deren
Funktionen vom Harness-Stand abweichen. "Phase 2 moeglich" ist hier
gleichbedeutend mit "arbeitsstand.begriffe gesetzt" (phasen.voraussetzungen,
``2: bool(stand and stand["begriffe"])`` -- identisch an cb200e4 und HEAD).

Schema-Abgleich (Step 1, `git show cb200e4:interview_theater/db.py` gegen
den aktuellen Stand -- an beiden Staenden byte-gleich in den hier
gebrauchten Spalten):

- `aufnahme`: Transkript-Spalte heisst `transkript` (nicht `text`),
  Status-Spalte `status` mit den Werten
  `laeuft|empfangen|transkribiert|fertig|fehlgeschlagen`. Ein Ende-Segment,
  das noch nicht fertig transkribiert ist, hat (wie ein echtes Leer-Segment)
  einen leeren `transkript`-Wert -- ohne den Statusfilter waere das ein
  falscher `stille_nach_leerem_ende`-Befund mitten in einer Rennlage.
  Deshalb zaehlt `lese_p1_stand` nur `status = 'fertig'`-Zeilen -- fuer
  `ende_leer` zusaetzlich `fehlgeschlagen` (endgueltig, so endet ein leeres
  Ende-Segment an cb200e4, siehe `_STATUS_ENDGUELTIG`).
- Bot-Blasen im Browser: `web_kanal.WebKanal.sende` (die Padua-Weboberflaeche,
  um die es in dieser Simulation geht) schreibt ausschliesslich nach
  `web_post` (`repo.lege_web_post_an`, `richtung = 'aus'`); die Tabelle
  `nachricht` (mit `ist_bot`) ist die Mitschrift fuer das Gespraechsfenster
  und Erkenner, nicht das, was der Browser als Blase zeigt -- bei
  Hintergrund-Boardlaeufen/-Vorschlaegen bleibt sie sogar unberuehrt. Darum
  kommen `P1Stand.bot_ids` aus `web_post` (`richtung = 'aus'`,
  `geloescht_am IS NULL`), identisch an beiden Staenden (dasselbe Schema,
  dieselbe `WebKanal.sende`-Bauart).
- `begriffsboard.json`: an beiden Staenden eine reine JSON-**Liste** von
  Eintraegen (`json.dumps(neu, ...)` in `begriffsboard._lauf_einmal`), kein
  umschliessendes Objekt. `board_begriffe_aus_json` akzeptiert zusaetzlich
  ein Objekt mit Schluessel `begriffe` (robuster gegen ein kuenftiges
  Format), ohne dass das am realen Fall etwas aendert.
- `arbeitsstand.fragen`: laut `fragen_auswertung.py` "die final angenommenen
  Fragezeilen, eine je Zeile" -- **keine** JSON-Liste, sondern Zeilen.
  `zaehle_fragen` zaehlt deshalb primaer nicht-leere Zeilen; eine JSON-Liste
  wird zusaetzlich erkannt (defensiv, falls ein kuenftiger Stand doch JSON
  schreibt), ist im echten Betrieb aber nicht der Normalfall.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

URSACHE_UNGEKLAERT = "App oder Werkzeug – ungeklaert"
FRIST_NACH_ENDE_S = 60.0
GRUPPENSCHLUESSEL_PRAEFIXE = ("vad_",)

BOARD_LEER = "board_leer_nach_ende"
BOARD_NICHT_NACHGEZOGEN = "board_nicht_nachgezogen"
STILLE_LEERES_ENDE = "stille_nach_leerem_ende"
STILLE_NACH_ENDE = "stille_nach_ende"
WERKBANK_LEER = "werkbank_leer_phase2_gesperrt"
RAUMCHECK_DOMAINWEIT = "raumcheck_domainweit"
VERHOERER = "verhoerer_nicht_korrigiert"
P2_FRAGEN_FEHLEN = "p2_fragen_fehlen"
P2_ZAEHLER = "p2_zaehler_inkonsistent"
BOARD_BEOBACHTER_LEER = "board_beobachter_leer"
STATION_NICHT_ERREICHT = "station_nicht_erreicht"

#: Status, ab dem eine `aufnahme`-Zeile als abgeschlossen gilt (siehe
#: Docstring oben) -- nur solche Zeilen zaehlen fuer die Zeichenzahl.
_STATUS_FERTIG = "fertig"
#: Fuer `ende_leer` zaehlt zusaetzlich `fehlgeschlagen`: ein leeres
#: Ende-Segment endet dort ("leeres Transkript -- Stille ist kein gueltiges
#: Ergebnis", Abnahmelauf cb200e4 05.10.2026, Aufnahme 7 -- Birks Live-Fall).
#: Beide Status sind endgueltig; nur noch laufende bleiben aussen vor.
_STATUS_ENDGUELTIG = ("fertig", "fehlgeschlagen")
#: Bot-Zeilen, die NICHT auf "Discussion done" antworten: die
#: Zwischenmeldung beim langsamen Abtippen eines frueheren Segments
#: (``aufnahme._TEXT_ZWISCHENMELDUNG``, an cb200e4 und HEAD gleich, EN und
#: DE). Im Lauf gegen cb200e4 verdeckte sie die Stille nach dem Ende.
KEINE_ANTWORT_AUF_ENDE = (
    "I'm still typing up the voice message, one moment.",
    "Ich tippe die Sprachnachricht noch ab, einen Moment.",
)


@dataclass(frozen=True)
class Befund:
    schluessel: str
    station: str
    text: str
    schwere: str = "hoch"
    ursache: str = URSACHE_UNGEKLAERT

    def als_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class P1Stand:
    board_begriffe: tuple[str, ...]
    board_zeilen: int
    transkript_zeichen: int
    ende_leer: bool
    arbeitsstand_begriffe: str
    max_bot_id: int
    bot_ids: tuple[int, ...]
    #: Fertige Diskussionszeichen hinter ``bis_aufnahme_id`` des letzten
    #: Boardlaufs (ohne Boardlauf: alle) -- 0, wenn die Spalte fehlt.
    ungelesen_zeichen: int = 0


def oeffne_lesend(db_pfad) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_pfad)}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def board_begriffe_aus_json(roh: str | None) -> tuple[str, ...]:
    try:
        daten = json.loads(roh or "[]")
    except ValueError:
        return ()
    if isinstance(daten, dict):
        daten = daten.get("begriffe", [])
    if not isinstance(daten, list):
        return ()
    return tuple(
        str(e["begriff"]).strip()
        for e in daten
        if isinstance(e, dict)
        and e.get("status") != "verworfen"
        and str(e.get("begriff") or "").strip()
    )


def lese_p1_stand(conn: sqlite3.Connection, chat_id: int) -> P1Stand:
    letzte = conn.execute(
        "SELECT * FROM begriffsboard WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,)
    ).fetchone()
    board_zeilen = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    platzhalter = ", ".join("?" for _ in _STATUS_ENDGUELTIG)
    alle = conn.execute(
        "SELECT id, transkript, schnittgrund, status FROM aufnahme "
        f"WHERE chat_id = ? AND diskussion = 1 AND status IN ({platzhalter}) ORDER BY id",
        (chat_id, *_STATUS_ENDGUELTIG),
    ).fetchall()
    aufnahmen = [a for a in alle if a["status"] == _STATUS_FERTIG]
    stand = conn.execute("SELECT begriffe FROM arbeitsstand WHERE chat_id = ?", (chat_id,)).fetchone()
    ausnahmen = ", ".join("?" for _ in KEINE_ANTWORT_AUF_ENDE)
    bot_ids = tuple(
        z[0]
        for z in conn.execute(
            "SELECT id FROM web_post WHERE chat_id = ? AND richtung = 'aus' "
            f"AND geloescht_am IS NULL AND COALESCE(text, '') NOT IN ({ausnahmen}) ORDER BY id",
            (chat_id, *KEINE_ANTWORT_AUF_ENDE),
        )
    )
    ende = [a for a in alle if a["schnittgrund"] == "ende"]
    return P1Stand(
        board_begriffe=board_begriffe_aus_json(letzte["json"] if letzte else None),
        board_zeilen=board_zeilen,
        transkript_zeichen=sum(len((a["transkript"] or "").strip()) for a in aufnahmen),
        ende_leer=bool(ende) and not (ende[-1]["transkript"] or "").strip(),
        arbeitsstand_begriffe=(stand["begriffe"] or "") if stand else "",
        max_bot_id=max(bot_ids, default=0),
        bot_ids=bot_ids,
        ungelesen_zeichen=_ungelesen(letzte, aufnahmen),
    )


def _ungelesen(letzte, aufnahmen) -> int:
    """Zeichen der fertigen Diskussionssegmente hinter dem letzten Boardlauf
    (``begriffsboard.bis_aufnahme_id``, an cb200e4 und HEAD vorhanden). Ohne
    Boardlauf ist alles ungelesen; fehlt die Spalte, 0 (nicht beurteilbar)."""
    if letzte is None:
        bis = 0
    elif "bis_aufnahme_id" in letzte.keys():
        bis = letzte["bis_aufnahme_id"] or 0
    else:
        return 0
    return sum(len((a["transkript"] or "").strip()) for a in aufnahmen if a["id"] > bis)


def pruefe_nach_diskussion(vorher: P1Stand, nachher: P1Stand, station: str) -> list[Befund]:
    befunde: list[Befund] = []
    if nachher.transkript_zeichen > 0 and not nachher.board_begriffe:
        befunde.append(Befund(
            BOARD_LEER, station,
            f"Nach 'Discussion done' ist das Board leer, obwohl {nachher.transkript_zeichen} Zeichen "
            f"transkribiert sind ({nachher.board_zeilen} Board-Laeufe).",
        ))
    elif nachher.ungelesen_zeichen > 0:
        # Dasselbe Symptom mit Vorgeschichte (Abnahmelauf cb200e4): das
        # Board ist aus einer frueheren Runde gefuellt, die knappe Nennung
        # danach liest es auch nach dem Ende nie.
        befunde.append(Befund(
            BOARD_NICHT_NACHGEZOGEN, station,
            f"Nach 'Discussion done' hat das Board {nachher.ungelesen_zeichen} Zeichen Transkript "
            f"nie gelesen ({nachher.board_zeilen} Board-Laeufe).",
        ))
    if not any(i > vorher.max_bot_id for i in nachher.bot_ids):
        if nachher.ende_leer:
            befunde.append(Befund(
                STILLE_LEERES_ENDE, station,
                "Nach 'Discussion done' kam keine Bot-Nachricht; das Ende-Segment war leer.",
            ))
        else:
            befunde.append(Befund(STILLE_NACH_ENDE, station, "Nach 'Discussion done' kam keine Bot-Nachricht."))
    if not nachher.arbeitsstand_begriffe.strip():
        befunde.append(Befund(
            WERKBANK_LEER, station,
            "arbeitsstand.begriffe ist leer: die Werkbank zeigt keine Begriffe, Phase 2 ist gesperrt.",
        ))
    return befunde


def warte_nach_diskussion(
    db_pfad, chat_id: int, vorher: P1Stand, station: str, *,
    frist_s: float = FRIST_NACH_ENDE_S, takt_s: float = 2.0,
    schlafe: Callable[[float], None] = time.sleep, uhr: Callable[[], float] = time.monotonic,
) -> tuple[list[Befund], P1Stand]:
    ende = uhr() + frist_s
    while True:
        with oeffne_lesend(db_pfad) as conn:
            stand = lese_p1_stand(conn, chat_id)
        befunde = pruefe_nach_diskussion(vorher, stand, station)
        if not befunde or uhr() >= ende:
            return befunde, stand
        schlafe(takt_s)


def pruefe_station_erreicht(station: str, fertig: bool) -> list[Befund]:
    if fertig:
        return []
    return [Befund(f"{STATION_NICHT_ERREICHT}:{station}", station,
                   f"Station {station} nicht erreicht (Ziel nicht erfuellt).")]


def pruefe_beobachter(verlauf: list[int], station: str) -> list[Befund]:
    if verlauf and max(verlauf) > 0:
        return []
    return [Befund(BOARD_BEOBACHTER_LEER, station,
                   f"Das zweite Geraet sah nie einen Begriff im CoThinker (Verlauf {verlauf or '[]'}).")]


def pruefe_raumcheck_schluessel(schluessel: list[str], token: str, station: str,
                                alle_tokens: tuple[str, ...] = ()) -> list[Befund]:
    """Meldet ``vad_*``-Schluessel ohne Gruppenbezug. ``alle_tokens``: die
    Tokens ALLER Gruppen des Laufs -- ein Schluessel, der irgendeinen davon
    traegt, ist korrekt gruppengebunden (z. B. die Messung von Gruppe 1,
    gesehen auf der Seite von Gruppe 2) und kein Befund."""
    tokens = (token, *alle_tokens)
    offen = sorted(
        k for k in schluessel
        if k.startswith(GRUPPENSCHLUESSEL_PRAEFIXE) and not any(t and t in k for t in tokens)
    )
    if not offen:
        return []
    return [Befund(RAUMCHECK_DOMAINWEIT, station,
                   "Raumcheck-Messung liegt ohne Gruppenbezug im localStorage (gilt fuer die ganze Domain, "
                   f"also auch fuer andere Gruppen): {', '.join(offen)}.")]


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def pruefe_verhoerer(board_begriffe, verhoerer: dict[str, str], station: str) -> list[Befund]:
    board = [_norm(b) for b in board_begriffe]
    befunde = []
    for falsch, richtig in verhoerer.items():
        hat_falsch = any(_norm(falsch) in b for b in board)
        hat_richtig = any(_norm(richtig) in b for b in board)
        if hat_falsch and not hat_richtig:
            befunde.append(Befund(VERHOERER, station,
                                  f"Verhoerer '{falsch}' steht im Board, '{richtig}' nicht (Kontextsatz nicht genutzt).",
                                  schwere="mittel"))
    return befunde


def zaehle_fragen(text: str | None) -> int:
    if not text or not text.strip():
        return 0
    try:
        daten = json.loads(text)
    except ValueError:
        daten = None
    if isinstance(daten, list):
        return len(daten)
    return sum(1 for z in text.splitlines() if z.strip())


def pruefe_p2_werkbank(fragen_text: str | None, sichtbare_fragen: int | None, station: str) -> list[Befund]:
    zahl = zaehle_fragen(fragen_text)
    if zahl == 0:
        return [Befund(P2_FRAGEN_FEHLEN, station, "arbeitsstand.fragen ist leer: keine Fragen in der Werkbank.")]
    if sichtbare_fragen is not None and sichtbare_fragen != zahl:
        return [Befund(P2_ZAEHLER, station,
                       f"Werkbank zeigt {sichtbare_fragen} Fragen, gespeichert sind {zahl}.")]
    return []


# --- Der Chat weiss, was der Bildschirm zeigt --------------------------------
#
# Der Gespraechsprompt des naechsten Zugs (``simulation/prompt_abzug.py``, mit
# dem ``kontext`` des App-Checkouts gegen eine DB-Kopie gebaut) wird mechanisch
# mit dem verglichen, was die Gruppe im Browser sieht. Was sichtbar ist und im
# Prompt fehlt, kann der Bot nicht wissen -- ein Befund, kein Geschmack.

CHAT_KENNT_BOARD_NICHT = "chat_kennt_board_nicht"
CHAT_KENNT_TRANSKRIPT_NICHT = "chat_kennt_transkript_nicht"
CHAT_KENNT_WERKBANK_NICHT = "chat_kennt_werkbank_nicht"
CHAT_NENNT_BOARD_NICHT = "chat_nennt_board_nicht"
WISSENSFRAGE = "Which terms are on the CoThinker right now?"
#: Laenge der Probe je Transkript-Blase (normalisiert, vom Anfang) -- lang
#: genug, um nicht zufaellig zu treffen, kurz genug, um eine Kuerzung des
#: Blasenendes zu ueberstehen.
TRANSKRIPT_PROBE_ZEICHEN = 30


@dataclass(frozen=True)
class Sichtbar:
    board: tuple[str, ...] = ()
    transkripte: tuple[str, ...] = ()
    werkbank: tuple[str, ...] = ()


def _norm_satz(text: str) -> str:
    """Kleinbuchstaben, Satzzeichen zu Leerraum, Leerraum zusammengefasst --
    damit "border." im Prompt "border" auf dem Board trifft."""
    erlaubt = "".join(c if c.isalnum() or c.isspace() else " " for c in text.casefold())
    return " ".join(erlaubt.split())


def _fehlend(begriffe, prompt_n: str) -> list[str]:
    return [b for b in begriffe if _norm_satz(b) and _norm_satz(b) not in prompt_n]


def pruefe_kontext(prompt: str, sichtbar: Sichtbar, station: str) -> list[Befund]:
    p = _norm_satz(prompt)
    befunde = []
    fehlt = _fehlend(sichtbar.board, p)
    if fehlt:
        befunde.append(Befund(CHAT_KENNT_BOARD_NICHT, station,
                              f"CoThinker zeigt {len(sichtbar.board)} Begriffe, im Gespraechsprompt fehlen: "
                              f"{', '.join(fehlt)}."))
    proben = [_norm_satz(t)[:TRANSKRIPT_PROBE_ZEICHEN] for t in sichtbar.transkripte if _norm_satz(t)]
    if proben:
        gefunden = sum(1 for pr in proben if pr in p)
        if gefunden * 2 < len(proben):
            befunde.append(Befund(CHAT_KENNT_TRANSKRIPT_NICHT, station,
                                  f"Von {len(proben)} sichtbaren Transkript-Blasen stehen nur {gefunden} "
                                  "im Gespraechsprompt."))
    fehlt = _fehlend(sichtbar.werkbank, p)
    if fehlt:
        befunde.append(Befund(CHAT_KENNT_WERKBANK_NICHT, station,
                              f"Werkbank zeigt Begriffe, die im Gespraechsprompt fehlen: {', '.join(fehlt)}."))
    return befunde


def pruefe_wissensantwort(antwort: str, board: tuple[str, ...], station: str) -> list[Befund]:
    """Antwort auf ``WISSENSFRAGE``: sie muss mindestens drei Board-Begriffe
    nennen (bei kleinerem Board alle)."""
    if not board:
        return []
    a = _norm_satz(antwort)
    genannt = [b for b in board if _norm_satz(b) in a]
    noetig = min(3, len(board))
    if len(genannt) >= noetig:
        return []
    return [Befund(CHAT_NENNT_BOARD_NICHT, station,
                   f"Auf '{WISSENSFRAGE}' nennt der Bot {len(genannt)} von {len(board)} Board-Begriffen "
                   f"(noetig {noetig}): {antwort[:160]!r}")]

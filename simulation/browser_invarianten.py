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
  Deshalb zaehlt `lese_p1_stand` nur `status = 'fertig'`-Zeilen.
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
#: Docstring oben) -- nur solche Zeilen zaehlen fuer `ende_leer` und die
#: Zeichenzahl.
_STATUS_FERTIG = "fertig"


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
        "SELECT json FROM begriffsboard WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,)
    ).fetchone()
    board_zeilen = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    aufnahmen = conn.execute(
        "SELECT transkript, schnittgrund FROM aufnahme "
        "WHERE chat_id = ? AND diskussion = 1 AND status = ? ORDER BY id",
        (chat_id, _STATUS_FERTIG),
    ).fetchall()
    stand = conn.execute("SELECT begriffe FROM arbeitsstand WHERE chat_id = ?", (chat_id,)).fetchone()
    bot_ids = tuple(
        z[0]
        for z in conn.execute(
            "SELECT id FROM web_post WHERE chat_id = ? AND richtung = 'aus' "
            "AND geloescht_am IS NULL ORDER BY id",
            (chat_id,),
        )
    )
    ende = [a for a in aufnahmen if a["schnittgrund"] == "ende"]
    return P1Stand(
        board_begriffe=board_begriffe_aus_json(letzte["json"] if letzte else None),
        board_zeilen=board_zeilen,
        transkript_zeichen=sum(len((a["transkript"] or "").strip()) for a in aufnahmen),
        ende_leer=bool(ende) and not (ende[-1]["transkript"] or "").strip(),
        arbeitsstand_begriffe=(stand["begriffe"] or "") if stand else "",
        max_bot_id=max(bot_ids, default=0),
        bot_ids=bot_ids,
    )


def pruefe_nach_diskussion(vorher: P1Stand, nachher: P1Stand, station: str) -> list[Befund]:
    befunde: list[Befund] = []
    if nachher.transkript_zeichen > 0 and not nachher.board_begriffe:
        befunde.append(Befund(
            BOARD_LEER, station,
            f"Nach 'Discussion done' ist das Board leer, obwohl {nachher.transkript_zeichen} Zeichen "
            f"transkribiert sind ({nachher.board_zeilen} Board-Laeufe).",
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


def pruefe_raumcheck_schluessel(schluessel: list[str], token: str, station: str) -> list[Befund]:
    offen = sorted(
        k for k in schluessel
        if k.startswith(GRUPPENSCHLUESSEL_PRAEFIXE) and token not in k
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

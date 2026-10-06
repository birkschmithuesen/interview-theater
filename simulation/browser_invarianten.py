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
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from interview_theater import aufnahme

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
ENDE_NICHT_ANGEKOMMEN = "ende_nicht_angekommen"
RAUMCHECK_NICHT_BESTAETIGT = "raumcheck_nicht_bestaetigt"
#: Praefix fuer eine Pruefung, die nicht laufen konnte (keine Messung, leeres
#: Board): ``nicht_pruefbar:<zielschluessel>``. Abnahmelauf 05.10.2026 --
#: bis dahin lieferten solche Pruefungen ``[]`` und erschienen in der
#: Vorher/Nachher-Tabelle als "–", also wie behoben.
NICHT_PRUEFBAR = "nicht_pruefbar"


def nicht_pruefbar(ziel: str, station: str, grund: str) -> "Befund":
    return Befund(f"{NICHT_PRUEFBAR}:{ziel}", station,
                  f"Pruefung {ziel} konnte nicht laufen: {grund}")

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
    #: Hoechste ``aufnahme.id`` der Gruppe (jeder Status) -- im Vorher-Stand
    #: die Grenze, hinter der die jetzige Diskussion beginnt.
    max_aufnahme_id: int = 0
    #: Id der Ende-Zeile, deren Leere ``ende_leer`` beschreibt (0: keine).
    ende_id: int = 0
    #: Hoechste Id einer Diskussions-Ende-Zeile in JEDEM Status (auch noch
    #: laufend) -- fuer ``ende_nicht_angekommen``.
    max_ende_id: int = 0


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
    max_aufnahme_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM aufnahme WHERE chat_id = ?", (chat_id,)).fetchone()[0]
    max_ende_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM aufnahme WHERE chat_id = ? AND diskussion = 1 "
        "AND schnittgrund = 'ende'", (chat_id,)).fetchone()[0]
    return P1Stand(
        board_begriffe=board_begriffe_aus_json(letzte["json"] if letzte else None),
        board_zeilen=board_zeilen,
        transkript_zeichen=sum(len((a["transkript"] or "").strip()) for a in aufnahmen),
        ende_leer=bool(ende) and not (ende[-1]["transkript"] or "").strip(),
        arbeitsstand_begriffe=(stand["begriffe"] or "") if stand else "",
        max_bot_id=max(bot_ids, default=0),
        bot_ids=bot_ids,
        ungelesen_zeichen=_ungelesen(letzte, aufnahmen),
        max_aufnahme_id=max_aufnahme_id,
        ende_id=ende[-1]["id"] if ende else 0,
        max_ende_id=max_ende_id,
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
    # Nur Ende-Zeilen der JETZIGEN Diskussion zaehlen (hinter dem
    # Vorher-Stand) -- das leere Ende einer frueheren Runde ist erledigt.
    ende_leer = nachher.ende_leer and nachher.ende_id > vorher.max_aufnahme_id
    if nachher.max_ende_id <= vorher.max_aufnahme_id:
        # Abnahmelauf 05.10.2026: ohne aktiven VAD haengt
        # ``web_chat.beendeDiskussion`` kein 'ende' an -- der Server schliesst
        # die Diskussion nie ab (kein Board, keine Antwort).
        befunde.append(Befund(
            ENDE_NICHT_ANGEKOMMEN, station,
            "Nach 'Discussion done' kam keine Aufnahme mit schnittgrund='ende' an (keine neue "
            f"Ende-Zeile hinter Aufnahme {vorher.max_aufnahme_id}); die Diskussion ist nie abgeschlossen.",
        ))
    if not any(i > vorher.max_bot_id for i in nachher.bot_ids):
        if ende_leer:
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
    gesehen auf der Seite von Gruppe 2) und kein Befund.

    Liegt gar kein ``vad_*``-Schluessel im Speicher, ist die Pruefung nicht
    gelaufen (``nicht_pruefbar:raumcheck_domainweit``), nicht bestanden."""
    tokens = (token, *alle_tokens)
    vad = [k for k in schluessel if k.startswith(GRUPPENSCHLUESSEL_PRAEFIXE)]
    if not vad:
        return [nicht_pruefbar(RAUMCHECK_DOMAINWEIT, station,
                               "keine Messung gespeichert (kein vad_*-Schluessel im localStorage).")]
    offen = sorted(k for k in vad if not any(t and t in k for t in tokens))
    if not offen:
        return []
    return [Befund(RAUMCHECK_DOMAINWEIT, station,
                   "Raumcheck-Messung liegt ohne Gruppenbezug im localStorage (gilt fuer die ganze Domain, "
                   f"also auch fuer andere Gruppen): {', '.join(offen)}.")]


def pruefe_raumcheck_bestaetigt(schluessel: list[str], kalibrierung_modus: str | None,
                                station: str) -> list[Befund]:
    """Nach ``p1-kalibrierung``: weder eine Messung (``vad_*`` im
    localStorage) noch ein gewaehlter Ausweg (``gruppe.kalibrierung_modus``)
    -- der Raumcheck ist nicht bestaetigt, auch wenn das Fertig-Praedikat
    der Station (eine Kalibrier-Aufnahme) erfuellt ist. Abnahmelauf
    05.10.2026: so startete jede neue Zuhoer-Sitzung den Raumcheck neu."""
    if any(k.startswith(GRUPPENSCHLUESSEL_PRAEFIXE) for k in schluessel) or kalibrierung_modus:
        return []
    return [Befund(RAUMCHECK_NICHT_BESTAETIGT, station,
                   "Raumcheck nicht bestaetigt: kein vad_*-Schluessel im localStorage und kein "
                   "gruppe.kalibrierung_modus.")]


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def pruefe_verhoerer(board_begriffe, verhoerer: dict[str, str], station: str) -> list[Befund]:
    board = [_norm(b) for b in board_begriffe]
    if verhoerer and not board:
        return [nicht_pruefbar(VERHOERER, station,
                               f"Board leer, Verhoerer {', '.join(repr(f) for f in verhoerer)} nicht auswertbar.")]
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
    if not sichtbar.board:
        befunde.append(nicht_pruefbar(CHAT_KENNT_BOARD_NICHT, station,
                                      "Board leer, kein sichtbarer Begriff zum Abgleich."))
    elif fehlt:
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


# --- Padua live-reif, Phase 3+4 (Karte t_92f99911, Task 2, 05.10.2026) ------
#
# Dieselbe Haltung wie oben: ein Symptom ist ein App-Fehler bis zum
# Gegenbeweis, und eine Pruefung ohne Material ist "nicht_pruefbar", nie
# stilles []. ``P34Stand`` liest nur lesend, eigenes SQL wie ``lese_p1_stand``.

INTERVIEW_OHNE_BLASE = "interview_ohne_transkriptblase"
INTERVIEW_OHNE_STATUS = "interview_ohne_statuszeile"
INTERVIEW_STATUS_DOPPELT = "interview_status_doppelt"          # mittel
INTERVIEW_STATUS_DEUTSCH = "interview_status_nicht_englisch"   # mittel
P4_GESPERRT_OHNE_VERDICHTUNG = "p4_gesperrt_ohne_laufende_verdichtung"
BRAINSTORM_OHNE_REAKTION = "brainstorm_ohne_karte_oder_schweigen"
#: Birk 05.10.2026 22:00 (kein Toggle mehr, Phase-1-Steuerung): Zwischenkarten
#: WAEHREND des Zuhoerens sind jetzt erwartetes Verhalten (``aufnahme.
#: _brainstorm_entscheide``'s Zwischenlauf) -- dieser Schluessel zaehlt
#: deshalb nur noch mehr als EINE Reaktion NACH "Discussion done"; die frueher
#: eigene Pruefung ``BRAINSTORM_KARTE_WAEHREND_BOGEN`` (eine Karte vor dem
#: Ende war beim alten Ein-Toggle-Bogen unmoeglich und damit immer ein
#: Befund) ist ersatzlos entfallen.
BRAINSTORM_MEHRERE_KARTEN = "brainstorm_mehrere_karten_je_bogen"
BRAINSTORM_ENDE_NICHT_ANGEKOMMEN = "brainstorm_ende_nicht_angekommen"
COTHINKER_UNGEERDET = "cothinker_karte_ungeerdet"               # mittel (t_c5cc5a62)
P3_GESPRAECH_OPUS = "p3_gespraech_ueber_opus"                   # hoch: Datenschutz
P4_GESPRAECH_NICHT_OPUS = "p4_gespraech_nicht_opus"             # mittel
EINWILLIGUNG_GEFRAGT = "einwilligung_gefragt"                   # hoch: Padua fragt nicht
P5_NICHT_ANGEBOTEN = "p5_nicht_angeboten"
FRIST_NACH_INTERVIEW_S = 120.0
FRIST_NACH_BRAINSTORM_S = 60.0
#: Woerter, an denen eine deutsche Statuszeile in einer EN-Gruppe auffaellt.
DE_MARKEN = (" ist ", " und ", " nicht ", "Wörter", "gespeichert", "zu kurz")
#: I3 (Review 05.10.2026, Fix round 1): mit ``{4,}`` zaehlten auch generische
#: englische Funktionswoerter als "Inhaltswort" -- ein Satz wie "What if that
#: is the whole story?" traf dann zufaellig zwei Transkriptwoerter, ohne dass
#: die Karte irgendetwas Konkretes aus dem Gehoerten aufgriff. Erweitert um
#: gaengige 4-Buchstaben-Funktionswoerter (Pronomen, Hilfsverben, Adverbien);
#: gegen die Original-Testfaelle UND den echten ``brainstorm-bogen``-Text
#: geprueft (``test_karte_geerdet_gegen_bogen_lehnt_generische_saetze_ab``).
#: I1 (Review 05.10.2026, Fix round 2): die erste Liste war gegen den echten
#: Transkript-Text (``simulation/diskussion/p4-brainstorm-bogen.txt``) noch
#: NICHT geprueft -- Woerter wie "whole", "never", "always", "same", "every",
#: "single", "right", "actually" stehen WORTGLEICH im Transkript (als
#: generische Fuellwoerter des erfundenen Dialogs, nicht als konkreter
#: Inhalt), trafen also auch nach dem Wortgrenzen-Fix (siehe
#: ``karte_geerdet`` unten) noch zufaellig. Deutlich erweitert (~150+
#: Woerter) auf eine umfassende Liste generischer/Funktionswoerter; die drei
#: Beispielsaetze aus dem Taskbrief laufen jetzt mit gegen den echten
#: Bogen-Text (``test_karte_geerdet_gegen_bogen_lehnt_generische_saetze_ab``).
#: Die Brainstorm-Skripte (``simulation/diskussion/*.txt``) sind durchgehend
#: Englisch -- keine italienischen/deutschen Funktionswoerter noetig.
_STOPP = frozenset({
    "about", "there", "their", "which", "would", "could", "because", "really",
    "that", "what", "with", "have", "they", "this", "when", "from", "then", "them",
    "were", "will", "into", "more", "some", "like", "just", "been", "here", "only",
    "also", "does", "very", "well", "much", "time", "maybe",
    # Fix round 2 (I1): Woerter aus dem Taskbrief, direkt gegen den echten
    # Bogen-Text getroffen.
    "whole", "might", "never", "always", "same", "every", "single", "right",
    "where", "such", "actually", "until", "gets", "thing", "things",
    "something", "everyone", "away", "story",
    # Fix round 2 (I1): weitere generische/Funktionswoerter (Pronomen,
    # Hilfsverben, Quantoren, Adverbien, Konjunktionen, haeufige vage Verben
    # und Fuellnomen), unabhaengig davon, ob sie im aktuellen Bogen-Text
    # vorkommen -- dieselbe Vorsicht wie bei jeder Pruefung ohne Material:
    # ein kuenftiger Bogen-Text soll nicht erneut dieselbe Lueckenklasse treffen.
    "after", "again", "against", "almost", "along", "already", "although",
    "among", "another", "anyone", "anything", "anywhere", "around", "aside",
    "back", "before", "behind", "below", "beside", "besides", "between",
    "beyond", "both", "cannot", "cause", "certain", "certainly", "come",
    "comes", "coming", "done", "doing", "down", "during", "each", "either",
    "else", "enough", "ever", "every", "everybody", "everything",
    "everywhere", "except", "fairly", "feel", "feels", "felt", "find",
    "finds", "found", "further", "getting", "give", "gives", "given",
    "giving", "goes", "going", "gone", "good", "great", "happen",
    "happened", "happens", "hardly", "having", "hence", "herself",
    "himself", "however", "indeed", "inside", "instead", "itself", "keep",
    "keeps", "kept", "kind", "kinds", "knew", "know", "known", "knows",
    "last", "least", "less", "little", "long", "look", "looked", "looking",
    "looks", "made", "make", "makes", "making", "many", "matter",
    "matters", "mean", "means", "meant", "mere", "merely", "might",
    "moment", "moments", "most", "mostly", "much", "must", "myself",
    "nearly", "need", "needs", "needed", "neither", "next", "nobody",
    "none", "nothing", "nowhere", "often", "once", "onto", "other",
    "others", "ourselves", "outside", "over", "overall", "own", "part",
    "parts", "perhaps", "place", "places", "plenty", "quite", "rather",
    "sees", "seem", "seemed", "seems", "several", "shall", "should",
    "simply", "since", "someone", "somehow", "someplace", "somewhat",
    "somewhere", "soon", "sort", "start", "started", "starts", "still",
    "stuff", "such", "sure", "take", "takes", "taken", "taking", "than",
    "themselves", "these", "think", "thinks", "those", "though",
    "through", "thus", "times", "together", "took", "toward", "towards",
    "truly", "turn", "turned", "turns", "under", "unless", "upon", "used",
    "uses", "using", "usual", "usually", "want", "wanted", "wants", "went",
    "whatever", "whenever", "wherever", "whether", "whom", "whose",
    "within", "without", "wonder", "wondered", "wonders", "year", "years",
    "yours", "yourself", "yourselves",
})
#: Deutsche und englische Konstanten der USA-Einwilligungsfrage
#: (``interview_theater/knoepfe/texte.py`` bzw. ``sprachen/en/texte.toml``) --
#: Padua fragt nicht, ein Treffer ist also immer ein Befund.
_USA_FRAGE_TEXTE = ("Tippt an, was gelten soll:", "Tap what should apply:")
_USA_JA_KNOPF_TEXTE = ("Ja, US-Modell", "Yes, US model")
#: Die reine Bestaetigung des Beenden-Knopfs (``befehle._befehl_fertig``,
#: ``T._TEXT_INTERVIEW_AUS``) -- im Web-Kanal IMMER als ``typ='system'``
#: verschickt (``system=True``), bei JEDEM ``/fertig``, unabhaengig davon, ob
#: die eigentliche Auswertungszeile ("zu kurz"/"gespeichert",
#: ``aufnahme._TEXT_ZU_KURZ``/``_TEXT_AUSGEWERTET``/``_text_interview_gespeichert_web``)
#: je ankommt. Ohne diesen Ausschluss kann INTERVIEW_OHNE_STATUS nie feuern --
#: jeder Klick auf "End interview" erzeugt diese Zeile zuerst (I1, Review
#: 05.10.2026, Fix round 1).
_INTERVIEW_AUS_TEXTE = ("Aufnahme beendet.", "Recording stopped.")
#: Mindestlaenge eines Inhaltsworts fuer ``karte_geerdet`` -- bewusst 4 statt
#: der ersten Annahme 5: ein echtes Transkript wie "the bench and the cafe"
#: traegt mit "cafe" ein viertes, fuer die Pruefung zentrales Wort, das bei
#: {5,} nie mitgezaehlt wuerde (siehe Taskbericht, Abweichung von der
#: Brief-Prosa "[a-zà-ü]{5,}" -- gegen den woertlichen Testfall geprueft).
_WORT_MINDESTLAENGE = 4
_WORT = re.compile(rf"[a-zà-ü]{{{_WORT_MINDESTLAENGE},}}")


@dataclass(frozen=True)
class P34Stand:
    max_post_id: int = 0
    #: (id, text) aus ``web_post`` ``richtung='aus' AND typ='transkript'``.
    transkript_posts: tuple = ()
    #: (id, text) aus ``web_post`` ``richtung='aus' AND typ='system'``.
    system_posts: tuple = ()
    #: Je Interview-Kopf (``klasse='lang'``): id, status, beendet_am (roh),
    #: beendet (bool, Nachbau von ``aufnahme.unausgewertete_interviews``:
    #: ``beendet_am`` gesetzt ODER Status in (fertig, transkribiert)),
    #: zu_kurz (bool), hat_verdichtung (bool), hat_transkript (bool, faellt
    #: wie ``repo.zusammengefuegtes_transkript`` auf die Teile zurueck).
    koepfe: tuple = ()
    #: (id, schweigen, text) aus ``buehnenkarte``.
    karten: tuple = ()
    max_aufnahme_id: int = 0
    #: Hoechste ``aufnahme.id`` mit ``brainstorm=1 AND schnittgrund='ende'``.
    brainstorm_ende_id: int = 0
    #: Alle ``brainstorm=1``-Transkripte mit Status ``fertig``, verbunden.
    brainstorm_text: str = ""
    #: (id, art, modus) aus ``aufruf``.
    aufrufe: tuple = ()
    #: Ob eine USA-Einwilligungsfrage je gestellt wurde (Padua fragt nicht).
    usa_gefragt: bool = False
    phase: int | None = None
    phase_angeboten: int | None = None
    #: SQL-Nachbau von ``phasen.voraussetzungen()[5]``.
    p5_moeglich: bool = False


def _hat_spalte(conn: sqlite3.Connection, tabelle: str, spalte: str) -> bool:
    try:
        return any(r[1] == spalte for r in conn.execute(f"PRAGMA table_info({tabelle})"))
    except sqlite3.OperationalError:
        return False


def lese_p34_stand(conn: sqlite3.Connection, chat_id: int) -> P34Stand:
    max_post_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM web_post WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    transkript_posts = tuple(
        (z["id"], z["text"]) for z in conn.execute(
            "SELECT id, text FROM web_post WHERE chat_id = ? AND richtung = 'aus' "
            "AND typ = 'transkript' ORDER BY id", (chat_id,)))
    system_posts = tuple(
        (z["id"], z["text"]) for z in conn.execute(
            "SELECT id, text FROM web_post WHERE chat_id = ? AND richtung = 'aus' "
            "AND typ = 'system' ORDER BY id", (chat_id,)))
    zu_kurz_ausdruck = "zu_kurz_uebersprungen" if _hat_spalte(conn, "aufnahme", "zu_kurz_uebersprungen") else "0"
    koepfe = tuple(
        {"id": z["id"], "status": z["status"], "beendet_am": z["beendet_am"],
         "beendet": bool(z["beendet_am"]) or z["status"] in ("fertig", "transkribiert"),
         "zu_kurz": bool(z["zu_kurz"]),
         "hat_transkript": bool((z["transkript"] or "").strip() or (z["teile_transkript"] or "").strip()),
         "hat_verdichtung": bool(z["verdichtungen"])}
        for z in conn.execute(
            f"""
            SELECT a.id, a.status, a.beendet_am, a.transkript, {zu_kurz_ausdruck} AS zu_kurz,
                   (SELECT COUNT(*) FROM verdichtung v WHERE v.aufnahme_id = a.id) AS verdichtungen,
                   (SELECT GROUP_CONCAT(t.transkript, '') FROM aufnahme t
                    WHERE t.teil_von = a.id AND t.transkript IS NOT NULL AND t.transkript != '')
                   AS teile_transkript
            FROM aufnahme a WHERE a.chat_id = ? AND a.klasse = 'lang' ORDER BY a.id
            """, (chat_id,)))
    karten = tuple(
        (z["id"], z["schweigen"], z["text"]) for z in conn.execute(
            "SELECT id, schweigen, text FROM buehnenkarte WHERE chat_id = ? ORDER BY id", (chat_id,)))
    max_aufnahme_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM aufnahme WHERE chat_id = ?", (chat_id,)).fetchone()[0]
    brainstorm_ende_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM aufnahme WHERE chat_id = ? AND brainstorm = 1 "
        "AND schnittgrund = 'ende'", (chat_id,)).fetchone()[0]
    brainstorm_text = " ".join(
        (z["transkript"] or "").strip() for z in conn.execute(
            "SELECT transkript FROM aufnahme WHERE chat_id = ? AND brainstorm = 1 "
            "AND status = 'fertig' ORDER BY id", (chat_id,))).strip()
    aufrufe = tuple(
        (z["id"], z["art"], z["modus"]) for z in conn.execute(
            "SELECT id, art, modus FROM aufruf WHERE chat_id = ? ORDER BY id", (chat_id,)))
    usa_gefragt = bool(conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND richtung = 'aus' AND ("
        "text IN (?, ?) OR knoepfe LIKE ? OR knoepfe LIKE ?)",
        (chat_id, *_USA_FRAGE_TEXTE, f"%{_USA_JA_KNOPF_TEXTE[0]}%", f"%{_USA_JA_KNOPF_TEXTE[1]}%"),
    ).fetchone()[0])
    arbeitsstand = conn.execute(
        "SELECT phase, phase_angeboten, rahmen, geschichte, szenen_anzahl, figuren_fixiert_am "
        "FROM arbeitsstand WHERE chat_id = ?", (chat_id,)).fetchone()
    # M2 (Review 05.10.2026, Fix round 1): weich entfernte Figuren/Szenen
    # (``repo.entferne_figur``/``figur.entfernt_am``) zaehlten bisher mit --
    # ``repo.figuren``/``repo.hole_szenen`` filtern sie aus jeder Ansicht,
    # hier taeten sie ``p5_moeglich`` faelschlich wahr machen. ``_hat_spalte``
    # wie beim bestehenden ``zu_kurz_uebersprungen``-Muster: die Testfixtur
    # (``db34``) traegt die Spalte nicht auf jedem Stand.
    figur_filter = " AND entfernt_am IS NULL" if _hat_spalte(conn, "figur", "entfernt_am") else ""
    szene_filter = " AND entfernt_am IS NULL" if _hat_spalte(conn, "szene", "entfernt_am") else ""
    figuren = conn.execute(
        f"SELECT COUNT(*) FROM figur WHERE chat_id = ?{figur_filter}", (chat_id,)).fetchone()[0]
    szenen = conn.execute(
        f"SELECT COUNT(*) FROM szene WHERE chat_id = ?{szene_filter}", (chat_id,)).fetchone()[0]
    p5_moeglich = bool(
        arbeitsstand and (arbeitsstand["rahmen"] or "").strip()
        and (arbeitsstand["figuren_fixiert_am"] or "").strip()
        and (arbeitsstand["geschichte"] or "").strip()
        and figuren >= 1
        and (bool((arbeitsstand["szenen_anzahl"] or "").strip()) or szenen >= 1)
    )
    return P34Stand(
        max_post_id=max_post_id, transkript_posts=transkript_posts, system_posts=system_posts,
        koepfe=koepfe, karten=karten, max_aufnahme_id=max_aufnahme_id,
        brainstorm_ende_id=brainstorm_ende_id, brainstorm_text=brainstorm_text, aufrufe=aufrufe,
        usa_gefragt=usa_gefragt,
        phase=(arbeitsstand["phase"] if arbeitsstand else None),
        phase_angeboten=(arbeitsstand["phase_angeboten"] if arbeitsstand else None),
        p5_moeglich=p5_moeglich,
    )


def _sekunden_seit(iso: str | None, jetzt_iso: str) -> float | None:
    """Sekunden zwischen ``iso`` und ``jetzt_iso`` (beide ``repo._jetzt()``-
    Format), oder ``None`` wenn ``iso`` fehlt oder nicht parsbar ist (z. B.
    ein Platzhalterwert in einer Testfixtur) -- dann gilt die Zeile als noch
    nicht ueber die Frist, dieselbe Vorsicht wie bei jeder Pruefung ohne
    Material."""
    if not iso:
        return None
    try:
        dann = datetime.fromisoformat(iso)
        jetzt = datetime.fromisoformat(jetzt_iso)
    except ValueError:
        return None
    if dann.tzinfo is None:
        dann = dann.replace(tzinfo=timezone.utc)
    if jetzt.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=timezone.utc)
    return (jetzt - dann).total_seconds()


def pruefe_p4_sperre(stand: P34Stand, station: str, *, jetzt_iso: str | None = None) -> list[Befund]:
    """Jeder beendete Interview-Kopf (``beendet`` -- Nachbau von
    ``aufnahme.unausgewertete_interviews``, siehe ``P34Stand.koepfe``) mit
    Transkript, nicht zu-kurz-uebersprungen und ohne Verdichtung -- Phase 4
    bleibt gesperrt, ohne dass ein Verdichtungslauf sichtbar laeuft (Padua
    Phasen TEIL 2, Befund 4a).

    Status ``laeuft``/``empfangen`` bekommt, solange ``beendet_am`` juenger
    als ``FRIST_NACH_INTERVIEW_S`` ist, noch Zeit (eine normal laufende
    Verdichtung): ein haengender Kopf -- ``beendet_am`` gesetzt, Status aber
    weiter ``laeuft``, laenger als die Frist -- zaehlt dagegen (I5, Review
    05.10.2026, Fix round 1: vorher war jeder Status in (laeuft, empfangen)
    BLIND ausgenommen, egal wie lange er schon so stand)."""
    jetzt_iso = jetzt_iso or datetime.now(timezone.utc).isoformat(timespec="seconds")
    befunde = []
    for kopf in stand.koepfe:
        if not (kopf["beendet"] and kopf["hat_transkript"] and not kopf["zu_kurz"]
                and not kopf["hat_verdichtung"]):
            continue
        if kopf["status"] in ("laeuft", "empfangen"):
            sekunden = _sekunden_seit(kopf.get("beendet_am"), jetzt_iso)
            if sekunden is None or sekunden < FRIST_NACH_INTERVIEW_S:
                continue  # normale Verarbeitung hat noch Zeit
        befunde.append(Befund(
            P4_GESPERRT_OHNE_VERDICHTUNG, station,
            f"Interview {kopf['id']} (Status {kopf['status']!r}) ist beendet, hat ein "
            "Transkript und keine Verdichtung -- Phase 4 bleibt gesperrt, ohne dass ein "
            "Verdichtungslauf sichtbar laeuft.",
        ))
    return befunde


def hat_neue_statuszeile(vorher: P34Stand, stand: P34Stand) -> bool:
    """Positiv-Signal fuer ``warte_auf`` (I2): mindestens eine neue
    Systemzeile ist da, die NICHT die reine Beenden-Bestaetigung ist -- die
    eigentliche Statuszeile (zu kurz/gespeichert) kann trotzdem noch ein
    zweites Mal kommen; das prueft ``pruefe_nach_interview``, nicht dieses
    Signal."""
    return any(i > vorher.max_post_id and (t or "") not in _INTERVIEW_AUS_TEXTE
               for i, t in stand.system_posts)


def pruefe_nach_interview(vorher: P34Stand, nachher: P34Stand, station: str) -> list[Befund]:
    befunde: list[Befund] = []
    neue_transkripte = [t for i, t in nachher.transkript_posts if i > vorher.max_post_id]
    # I1 (Review 05.10.2026, Fix round 1): die reine Beenden-Bestaetigung
    # (``_INTERVIEW_AUS_TEXTE``) laeuft bei JEDEM "End interview"-Klick,
    # unabhaengig davon, ob die eigentliche Auswertungszeile je ankommt --
    # ohne den Ausschluss hier konnte INTERVIEW_OHNE_STATUS nie feuern.
    neue_system = [(i, t) for i, t in nachher.system_posts
                   if i > vorher.max_post_id and (t or "") not in _INTERVIEW_AUS_TEXTE]
    if not neue_transkripte:
        befunde.append(Befund(
            INTERVIEW_OHNE_BLASE, station,
            "Nach dem Interview-Ende kam keine Transkript-Blase ('🎙 ...') im Chat an."))
    elif any(not (t or "").startswith("🎙") for t in neue_transkripte):
        befunde.append(Befund(
            INTERVIEW_OHNE_BLASE, station,
            "Eine neue Transkript-Zeile beginnt nicht mit dem Mikrofon-Emoji '🎙'."))
    if not neue_system:
        befunde.append(Befund(
            INTERVIEW_OHNE_STATUS, station,
            "Nach dem Interview-Ende kam keine Statuszeile (zu kurz/gespeichert) im Chat an."))
    else:
        texte = [t for _, t in neue_system]
        for text in dict.fromkeys(texte):
            if texte.count(text) >= 2:
                befunde.append(Befund(
                    INTERVIEW_STATUS_DOPPELT, station,
                    f"Die Statuszeile {text!r} kam {texte.count(text)}-mal an.", schwere="mittel"))
            if any(marke in (text or "") for marke in DE_MARKEN):
                befunde.append(Befund(
                    INTERVIEW_STATUS_DEUTSCH, station,
                    f"Statuszeile auf Deutsch in einer englischsprachigen Gruppe: {text!r}.",
                    schwere="mittel"))
    befunde += pruefe_p4_sperre(nachher, station)
    return befunde


def _inhaltswoerter(text: str) -> set[str]:
    return {w for w in _WORT.findall((text or "").casefold()) if w not in _STOPP}


def karte_geerdet(karte: str, transkript: str) -> bool:
    """Mindestens zwei verschiedene Inhaltswoerter aus ``transkript`` stehen
    in ``karte`` -- der CoThinker hat wirklich zugehoert, statt etwas
    Generisches zu schreiben.

    I1 (Review 05.10.2026, Fix round 2): vorher wurde jedes Transkriptwort
    per ``in karte_cf`` als TEILSTRING in der Karte gesucht -- ein kurzes
    Wort wie "cat" traf dann auch mitten in "indicate" oder "location",
    ohne dass die Karte das Wort wirklich enthielt. Jetzt werden ganze
    Woerter verglichen: ``_WORT.findall`` auf der Karte liefert dieselbe
    Tokenisierung wie auf dem Transkript, der Treffer ist eine
    Mengenschnittmenge."""
    kandidaten = _inhaltswoerter(transkript)
    karte_woerter = set(_WORT.findall((karte or "").casefold()))
    treffer = kandidaten & karte_woerter
    return len(treffer) >= 2


def hat_neue_karte(vor_ende: P34Stand, stand: P34Stand) -> bool:
    """Positiv-Signal fuer ``warte_auf`` (I2): mindestens eine neue
    Buehnenkarte (echt oder vermerktes Schweigen) ist da -- ob es zu VIELE
    sind (``BRAINSTORM_MEHRERE_KARTEN``, eine spaet eintreffende zweite),
    prueft erst die finale Pruefung nach der Gnadenfrist."""
    vorher_ids = {k[0] for k in vor_ende.karten}
    return any(k[0] not in vorher_ids for k in stand.karten)


def pruefe_nach_brainstorm(vorher: P34Stand, vor_ende: P34Stand, nachher: P34Stand,
                           station: str) -> list[Befund]:
    """Birk 05.10.2026 22:00: kein Toggle mehr -- Phase 4 hoert kontinuierlich
    zu wie Phase 1, CoThinker-Karten koennen also schon WAEHREND des
    Zuhoerens entstehen (``vorher`` -> ``vor_ende``), nicht erst danach. Eine
    solche Zwischenkarte ist deshalb kein eigener Befund mehr -- sie muss nur
    weiterhin geerdet sein (``karte_geerdet``), genau wie jede Karte NACH dem
    Ende. ``BRAINSTORM_MEHRERE_KARTEN`` zaehlt dagegen ausschliesslich, was
    NACH ``vor_ende`` (also nach "Discussion done") entstand -- eine
    Zwischenkarte zaehlt dafuer nicht mit, der Abschluss bleibt "genau eine
    Reaktion auf das Ende"."""
    befunde: list[Befund] = []
    if nachher.brainstorm_ende_id <= vorher.max_aufnahme_id:
        befunde.append(Befund(
            BRAINSTORM_ENDE_NICHT_ANGEKOMMEN, station,
            "Nach dem Beenden des Mithoerens kam keine Aufnahme mit brainstorm=1 und "
            f"schnittgrund='ende' an (keine neue Ende-Zeile hinter Aufnahme {vorher.max_aufnahme_id})."))
    vorher_ids = {k[0] for k in vorher.karten}
    vor_ende_ids = {k[0] for k in vor_ende.karten}
    waehrend = [k for k in vor_ende.karten if k[0] not in vorher_ids]
    neue_karten = [k for k in nachher.karten if k[0] not in vor_ende_ids]
    if not neue_karten:
        befunde.append(Befund(
            BRAINSTORM_OHNE_REAKTION, station,
            "Nach dem Ende des Bogens kam keine Buehnenkarte und kein vermerktes Schweigen an."))
    elif len(neue_karten) > 1:
        befunde.append(Befund(
            BRAINSTORM_MEHRERE_KARTEN, station,
            f"{len(neue_karten)} Buehnenkarten nach 'Discussion done' -- erwartet war genau eine."))
    for _id, schweigen, text in (*waehrend, *neue_karten):
        if schweigen:
            continue
        if not karte_geerdet(text, nachher.brainstorm_text):
            befunde.append(Befund(
                COTHINKER_UNGEERDET, station,
                f"Buehnenkarte {text!r} nimmt kein erkennbares Wort aus dem Brainstorm-Transkript auf.",
                schwere="mittel"))
    return befunde


def pruefe_modellwahl(stand: P34Stand, phase3: tuple[int, int], phase4: tuple[int, int],
                      station: str, *, nur_phase: int | None = None) -> list[Befund]:
    """``phase3``/``phase4`` sind (von, bis)-Grenzen der ``aufruf.id`` dieser
    Phase (siehe ``_aufruf_bereiche``/``_teile_bereich_am_phasenwechsel`` in
    Task 2c/Fix round 1): ``von < id <= bis``.

    I4 (Review 05.10.2026, Fix round 1): hat ``phase4`` im geprueften
    Bereich gar keinen ``gespraech``-Aufruf (leerer Bereich, oder die
    Stationen dieser Phase sind noch nicht gelaufen), ist
    ``P4_GESPRAECH_NICHT_OPUS`` nicht pruefbar -- vorher lieferte das still
    ``[]``, als waere alles in Ordnung.

    ``nur_phase`` (M2, Review 05.10.2026, Fix round 2): der ``modellwahl``-
    Haken laeuft an ZWEI Stationen (``p3-uebergang``, ``p4-uebergang``) mit
    DEMSELBEN Phase-3-Bereich -- ohne Einschraenkung lieferte das an
    ``p3-uebergang`` IMMER ``nicht_pruefbar:p4_gespraech_nicht_opus`` (der
    Phase-4-Bereich ist dort naturgemaess noch leer, keine Phase-4-Station
    ist gelaufen), und ein echter ``P3_GESPRAECH_OPUS``-Befund kaeme an
    ``p4-uebergang`` ein zweites Mal. ``None`` (Vorgabe) prueft weiterhin
    beide Teile -- fuer direkte Aufrufe/Tests dieser Funktion unveraendert;
    der Produktionsaufruf (``browser_pruefhaken._modellwahl``) reicht die
    Stationsphase durch und bekommt so nur noch den passenden Teil."""
    def _im_bereich(bereich: tuple[int, int], i: int) -> bool:
        von, bis = bereich
        return von < i <= bis

    befunde: list[Befund] = []
    if nur_phase in (None, 3):
        gespraeche3 = [a for a in stand.aufrufe if a[1] == "gespraech" and _im_bereich(phase3, a[0])]
        if any(a[2] == "C" for a in gespraeche3):
            befunde.append(Befund(
                P3_GESPRAECH_OPUS, station,
                "Ein Gespraechsaufruf in Phase 3 lief ueber Opus (modus 'C') -- Datenschutz, "
                "die Interviews gehen in Phase 3 nicht an die USA."))
    if nur_phase in (None, 4):
        gespraeche4 = [a for a in stand.aufrufe if a[1] == "gespraech" and _im_bereich(phase4, a[0])]
        if not gespraeche4:
            befunde.append(nicht_pruefbar(
                P4_GESPRAECH_NICHT_OPUS, station,
                f"keine Gespraechsaufrufe im geprueften Phase-4-Bereich {phase4}."))
        elif any(a[2] != "C" for a in gespraeche4):
            befunde.append(Befund(
                P4_GESPRAECH_NICHT_OPUS, station,
                "Ein Gespraechsaufruf in Phase 4 lief NICHT ueber Opus (modus != 'C').",
                schwere="mittel"))
    if stand.usa_gefragt:
        befunde.append(Befund(
            EINWILLIGUNG_GEFRAGT, station,
            "Die USA-Einwilligungsfrage wurde gestellt -- Padua fragt nicht danach."))
    return befunde


def pruefe_p5_angebot(stand: P34Stand, station: str) -> list[Befund]:
    if stand.p5_moeglich and (stand.phase_angeboten or 0) < 5 and (stand.phase or 0) < 5:
        return [Befund(
            P5_NICHT_ANGEBOTEN, station,
            "Setting, fixierte Figuren, Geschichte und Szenenzahl stehen, aber Phase 5 wurde "
            "nicht angeboten (arbeitsstand.phase_angeboten < 5).")]
    return []


#: Nach dem Positiv-Signal (oder der Frist) wird noch diese Zeit abgewartet,
#: bevor ``warte_auf`` EIN letztes Mal prueft -- sonst sieht eine fruehe
#: "saubere" Zwischenmessung eine zweite, verspaetete Statuszeile oder
#: Buehnenkarte nie (I2, Review 05.10.2026, Fix round 1). Bleibt die Vorgabe
#: fuer den Brainstorm-Pfad (M3, Fix round 2): die CoThinker-Karte entsteht
#: ``_brainstorm_abschliessen``/``_brainstorm_entscheide`` direkt im selben
#: Transkriptions-Durchlauf (kein periodischer Arbeiter dazwischen) -- 10 s
#: Verarbeitungs-Spielraum reichen hier aus.
GRACE_NACH_SIGNAL_S = 10.0
#: M3 (Review 05.10.2026, Fix round 2): fuer den Interview-Pfad war
#: ``GRACE_NACH_SIGNAL_S`` (10 s) KUERZER als der Takt des Nachhol-Arbeiters
#: (``aufnahme.NACHHOL_INTERVALL_S`` = 60 s, der Arbeiter, der eine
#: gescheiterte Verdichtung erneut versucht) -- eine zweite, erst durch
#: einen Nachhol-Lauf entstandene Statuszeile kam dann oft NACH der finalen
#: Pruefung an und wurde nie geprueft. 5 s Sicherheitsabstand ueber einen
#: vollen Nachhol-Takt hinaus.
GRACE_NACH_INTERVIEW_S = aufnahme.NACHHOL_INTERVALL_S + 5.0


def warte_auf(lese: Callable[[], object], pruefe: Callable[[object], list[Befund]], *,
             frist_s: float, ende: Callable[[object], bool] | None = None,
             grace_s: float = GRACE_NACH_SIGNAL_S, takt_s: float = 2.0,
             schlafe: Callable[[float], None] = time.sleep,
             uhr: Callable[[], float] = time.monotonic) -> tuple[list[Befund], object]:
    """Generische Fassung von ``warte_nach_diskussion``: pollt ``lese()``,
    bis ``ende(stand)`` wahr wird (ohne ``ende``: bis ``pruefe(stand)`` leer
    ist -- das alte Verhalten) oder die Frist ``frist_s`` ablaeuft; wartet
    DANACH zusaetzlich ``grace_s`` und liefert GENAU das Ergebnis dieser
    letzten, finalen Pruefung. ``warte_nach_diskussion`` bleibt unveraendert
    stehen -- diese Funktion ist der Einhaengepunkt fuer ``nach_interview``/
    ``nach_brainstorm`` (Task 2c).

    I2 (Review 05.10.2026, Fix round 1): der fruehere Entwurf gab beim
    ersten befundfreien Zwischenstand sofort zurueck -- eine zweite,
    verspaetete Statuszeile (``INTERVIEW_STATUS_DOPPELT``), eine zweite
    Buehnenkarte (``BRAINSTORM_MEHRERE_KARTEN``) oder eine deutsche
    Statuszeile, die erst nach der ersten (englischen) ankam
    (``INTERVIEW_STATUS_DEUTSCH``), kam dann NIE zur Pruefung. Jetzt zaehlt
    nur noch die Pruefung NACH der Gnadenfrist."""
    ende_zeit = uhr() + frist_s
    stand = lese()
    weiter = (lambda s: not ende(s)) if ende is not None else (lambda s: bool(pruefe(s)))
    while weiter(stand) and uhr() < ende_zeit:
        schlafe(takt_s)
        stand = lese()
    schlafe(grace_s)
    stand = lese()
    return pruefe(stand), stand


def pruefe_wissensantwort(antwort: str, board: tuple[str, ...], station: str) -> list[Befund]:
    """Antwort auf ``WISSENSFRAGE``: sie muss mindestens drei Board-Begriffe
    nennen (bei kleinerem Board alle). Leeres Board: nicht pruefbar."""
    if not board:
        return [nicht_pruefbar(CHAT_NENNT_BOARD_NICHT, station,
                               "Board leer, keine Begriffe, die die Antwort nennen koennte.")]
    a = _norm_satz(antwort)
    genannt = [b for b in board if _norm_satz(b) in a]
    noetig = min(3, len(board))
    if len(genannt) >= noetig:
        return []
    return [Befund(CHAT_NENNT_BOARD_NICHT, station,
                   f"Auf '{WISSENSFRAGE}' nennt der Bot {len(genannt)} von {len(board)} Board-Begriffen "
                   f"(noetig {noetig}): {antwort[:160]!r}")]

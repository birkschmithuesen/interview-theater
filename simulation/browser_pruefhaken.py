"""Die Pruef-Haken des Stationsmotors (Karte t_fc2c1bfa, Task 6): nach jeder
Station laufen die in ``Station.pruefung`` genannten deterministischen
Pruefungen aus ``browser_invarianten`` -- ohne Richter, ohne Modell.

Jede Abhaengigkeit kommt ueber ``PruefKontext`` herein (Seite, Beobachter,
DB-Pfad, ``warte``, ``hole_prompt``, ``sende``), damit die Haken ohne Browser
und ohne echten Stack testbar sind. Eigenes Modul statt weiterer hundert
Zeilen in ``browser_lauf.py``; ``browser_lauf`` reicht die Namen weiter.

Selektoren (an HEAD und an cb200e4 gleich, ``git show cb200e4:...``):

- Transkript-Blasen der Gruppe: ``.blase.gruppe.sprache`` -- eine abgetippte
  Sprachnachricht steht als ``"🎤 <m:ss> · <text>"`` darin
  (``web_chat._TEXT_SPRACHE_ABGETIPPT``, JS ``textVon``); der Platzhalter
  waehrend des Abtippens hat kein Mikrofon und zaehlt nicht. Dazu
  ``.blase.transkript`` (die eine Interview-Transkriptblase).
- Werkbank-Fragen: ``ul.fragen > li`` im Rumpf von ``/g/<token>/teil/stand``
  (``web._fragen_html``) -- per ``fetch`` aus der Beobachter-Seite gelesen,
  ohne Tabwechsel: das Stand-Panel laedt sich nur nach, solange es sichtbar
  ist, ein Tabwechsel im Beobachter wuerde dessen Board-Messung stoeren.
- Werkbank-Begriffe: kein eindeutiger Selektor (ein blosses ``<p>`` in
  ``web._wb_inhalt_html``) -- deshalb aus ``arbeitsstand.begriffe`` in der
  DB, im Befundtext als "(Werkbank aus DB)" vermerkt.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from simulation import browser_invarianten as inv
from simulation.diskussionen import DISKUSSIONEN

log = logging.getLogger(__name__)

#: Abgetippte Sprachnachricht: "🎤 0:45 · <text>".
_SPRACHE_PRAEFIX = re.compile(r"^\s*🎤\s*\d+:\d{2}\s*·\s*")
_TRANSKRIPT_JS = (
    "els => els.map(e => ({typ: e.classList.contains('transkript') ? 'transkript' : 'sprache', "
    "text: (e.innerText || '').trim()}))"
)
_FRAGEN_JS = """async () => {
  const weg = location.pathname.replace(/\\/$/, '') + '/teil/stand';
  const r = await fetch(weg, {cache: 'no-store'});
  if (!r.ok) { return null; }
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  const listen = Array.from(doc.querySelectorAll('ul.fragen'));
  if (!listen.length) { return 0; }
  return Math.max(...listen.map(u => u.querySelectorAll(':scope > li').length));
}"""
_HINWEIS_WERKBANK_DB = " (Werkbank aus DB)"
#: Wie lange der Beobachter nach einem gefuellten DB-Board noch auf die
#: Anzeige warten darf (das Board laedt per Takt nach, nicht sofort).
BEOBACHTER_NACHLAUF_S = 10


@dataclass
class PruefKontext:
    db_pfad: str
    gruppen: list                        # Objekte mit .token/.chat_id (browser_umgebung.Gruppe)
    page: object
    beobachter: object | None = None
    vorher: inv.P1Stand | None = None    # P1-Stand direkt vor "Discussion done"
    antwort: str | None = None           # Bot-Antwort auf ``station.sage`` (von ``sende``)
    hole_prompt: Callable[[int, str], str] | None = None
    warte: Callable = inv.warte_nach_diskussion
    sende: Callable[[str], str] | None = None   # schickt Text als Gruppe, liefert die Bot-Antwort
    lauf_verzeichnis: Path | None = None
    beobachter_start: int = 0            # Index in beobachter.verlauf zu Stationsbeginn
    stand: inv.P1Stand | None = None     # Ergebnis von nach_ende, fuer verhoerer
    notizen: list = field(default_factory=list)
    #: (befunde, stand) aus ``warte``, gelaufen DIREKT nach dem Klick auf
    #: "Discussion done" -- spaetere Persona-Nachrichten koennen Stille
    #: dann nicht mehr verdecken, und die 60 s beginnen beim Klick.
    ergebnis_nach_ende: tuple | None = None
    # --- Padua live-reif Phase 3+4 (Task 2c) --------------------------------
    vorher_p34: inv.P34Stand | None = None     # P34-Stand zu Stationsbeginn
    vor_ende_p34: inv.P34Stand | None = None   # P34-Stand direkt vor dem Ende-Klick
    stand_p34: inv.P34Stand | None = None      # Ergebnis von nach_interview/nach_brainstorm
    #: (befunde, stand) aus ``warte_p34``, gelaufen DIREKT nach dem
    #: Harness-Klick auf "End interview"/"Discussion done" (Brainstorm hat
    #: seit 05.10.2026 22:00 keinen eigenen Toggle mehr).
    ergebnis_p34: tuple | None = None
    warte_p34: Callable = inv.warte_auf
    #: Station.schluessel -> (von, bis) der ``aufruf.id``, die waehrend
    #: dieser Station entstanden -- Grundlage des ``modellwahl``-Hakens.
    aufruf_bereiche: dict = field(default_factory=dict)
    #: Station.schluessel -> Phase, fuer die Bereichs-Vereinigung im
    #: ``modellwahl``-Haken (Phase-3- bzw. Phase-4-Bereich ueber alle
    #: Stationen dieser Phase).
    stationen_phase: dict = field(default_factory=dict)
    #: M2 (Review 05.10.2026, Fix round 2): welche Phasenteile
    #: (3 und/oder 4) ``_modellwahl`` in DIESEM Lauf schon geprueft hat --
    #: dasselbe ``set``-Objekt wandert per Referenz in JEDE ``PruefKontext``
    #: dieses Laufs (wie ``aufruf_bereiche``/``stationen_phase``), damit eine
    #: spaetere Station nicht denselben Teil ein zweites Mal meldet, ein
    #: FEHLENDER frueherer Check (z. B. eine gescheiterte Phase-3-Station
    #: ohne eigenen ``modellwahl``-Haken) aber weiter vollstaendig nachgeholt
    #: wird (``_modellwahl`` faellt dann auf ``nur_phase=None`` zurueck).
    modellwahl_phasen_geprueft: set = field(default_factory=set)
    #: Coverage-Luecke Pause/Resume (p34-abnahme-verfahren.md §3): die
    #: Rueckgabe von ``browser_lauf._fuehre_station_aus`` dieser Station
    #: (u. a. ``pause_resume_ok``) -- von ``fuehre_stationen`` gesetzt, BEVOR
    #: ``fuehre_pruefungen`` laeuft.
    lauf: dict | None = None


def speicher_schluessel(page) -> list[str]:
    return list(page.evaluate("Object.keys(localStorage)"))


def _transkripte(page) -> tuple[str, ...]:
    roh = page.eval_on_selector_all(".blase.gruppe.sprache, .blase.transkript", _TRANSKRIPT_JS)
    texte = []
    for z in roh:
        text = z["text"]
        if z["typ"] == "sprache":
            if not _SPRACHE_PRAEFIX.match(text):
                continue          # Platzhalter "wird abgetippt" / nur Dauer
            text = _SPRACHE_PRAEFIX.sub("", text)
        if text.strip():
            texte.append(text.strip())
    return tuple(texte)


def begriffe_aus_text(text: str | None) -> tuple[str, ...]:
    """``arbeitsstand.begriffe`` ist ein freier String ("home, border, ...")
    -- getrennt an Komma, Semikolon, Zeilenumbruch und " | "."""
    teile = re.split(r"[,;\n]| \| ", text or "")
    return tuple(t.strip(" -•.") for t in teile if t.strip(" -•."))


def sichtbares(page, beobachter, *, werkbank: tuple[str, ...] = ()) -> inv.Sichtbar:
    """Was die Gruppe gerade sieht: Board vom zweiten Geraet (CoThinker),
    Transkript-Blasen aus dem Chat der Persona, Werkbank-Begriffe vom
    Aufrufer (siehe Moduldoc: aus der DB)."""
    board = tuple(beobachter.begriffe()) if beobachter is not None else ()
    return inv.Sichtbar(board=board, transkripte=_transkripte(page), werkbank=tuple(werkbank))


def _sichtbare_fragen(beobachter) -> int | None:
    if beobachter is None:
        return None
    try:
        wert = beobachter.page.evaluate(_FRAGEN_JS)
    except Exception:
        log.exception("Werkbank-Fragen im Beobachter nicht lesbar")
        return None
    return None if wert is None else int(wert)


def _lies_p1(kontext: PruefKontext, chat_id: int) -> inv.P1Stand:
    with inv.oeffne_lesend(kontext.db_pfad) as conn:
        return inv.lese_p1_stand(conn, chat_id)


def _lies_fragen(kontext: PruefKontext, chat_id: int) -> str:
    """Ungekappt aus der DB -- ``browser_mitschnitt.datenstand`` kappt Werte
    auf 120 Zeichen und wuerde Fragen verschlucken."""
    with inv.oeffne_lesend(kontext.db_pfad) as conn:
        zeile = conn.execute("SELECT fragen FROM arbeitsstand WHERE chat_id = ?", (chat_id,)).fetchone()
    return (zeile["fragen"] or "") if zeile else ""


def _beobachter_nachmessen(kontext: PruefKontext, board_gefuellt: bool) -> None:
    b = kontext.beobachter
    if b is None:
        return
    b.messe()
    if not board_gefuellt:
        return
    for _ in range(BEOBACHTER_NACHLAUF_S // 2):
        if b.verlauf and b.verlauf[-1] > 0:
            return
        b.page.wait_for_timeout(2000)
        b.messe()


def warte_nach_klick(station, kontext: PruefKontext, chat_id: int) -> None:
    """Rueckruf direkt nach dem Harness-Klick auf "Discussion done"."""
    kontext.ergebnis_nach_ende = kontext.warte(
        kontext.db_pfad, chat_id, kontext.vorher, station.schluessel)


def _nach_ende(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    if kontext.ergebnis_nach_ende is not None:
        befunde, stand = kontext.ergebnis_nach_ende
    else:
        # Der Harness hat "Discussion done" nicht selbst gedrueckt (die
        # Persona war schneller oder die Diskussion lief nie): Vorher-Stand
        # ist der Stationsbeginn, gewartet wird erst jetzt -- vermerkt, weil
        # Bot-Zeilen der Station dann Stille verdecken koennen.
        vorher = kontext.vorher
        if vorher is None:
            vorher = _lies_p1(kontext, chat_id)
        kontext.notizen.append(
            f"{station.schluessel}: kein Harness-Klick auf 'Discussion done' -- Vorher-Stand vom "
            "Stationsbeginn, Wartezeit ab Stationsende")
        befunde, stand = kontext.warte(kontext.db_pfad, chat_id, vorher, station.schluessel)
    kontext.stand = stand
    befunde = list(befunde)
    if kontext.beobachter is not None:
        _beobachter_nachmessen(kontext, bool(stand.board_begriffe))
        verlauf = list(kontext.beobachter.verlauf[kontext.beobachter_start:])
        befunde += inv.pruefe_beobachter(verlauf, station.schluessel)
    return befunde


def _verhoerer(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    stand = kontext.stand or _lies_p1(kontext, chat_id)
    verhoerer = DISKUSSIONEN[station.diskussion].verhoerer if station.diskussion else {}
    return inv.pruefe_verhoerer(stand.board_begriffe, verhoerer, station.schluessel)


def _wissen(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    text = station.sage or inv.WISSENSFRAGE
    # ZUERST der Prompt: der Abzug haengt den Text selbst als neue Nachricht
    # an eine DB-Kopie -- genau der Zug, den der Bot nach dem Senden baut.
    prompt = kontext.hole_prompt(chat_id, text) if kontext.hole_prompt else ""
    if kontext.lauf_verzeichnis is not None:
        (Path(kontext.lauf_verzeichnis) / f"prompt-{station.schluessel}.txt").write_text(
            prompt, encoding="utf-8")
    werkbank = begriffe_aus_text(_lies_p1(kontext, chat_id).arbeitsstand_begriffe)
    sichtbar = sichtbares(kontext.page, kontext.beobachter, werkbank=werkbank)
    befunde = [
        dataclasses.replace(b, text=b.text + _HINWEIS_WERKBANK_DB)
        if b.schluessel == inv.CHAT_KENNT_WERKBANK_NICHT else b
        for b in inv.pruefe_kontext(prompt, sichtbar, station.schluessel)
    ]
    if kontext.sende is not None:
        kontext.antwort = kontext.sende(text)
    befunde += inv.pruefe_wissensantwort(kontext.antwort or "", sichtbar.board, station.schluessel)
    return befunde


def _alle_tokens(kontext: PruefKontext) -> tuple[str, ...]:
    return tuple(g.token for g in kontext.gruppen)


def _lies_kalibrierung_modus(kontext: PruefKontext, chat_id: int) -> str | None:
    with inv.oeffne_lesend(kontext.db_pfad) as conn:
        zeile = conn.execute("SELECT kalibrierung_modus FROM gruppe WHERE chat_id = ?",
                             (chat_id,)).fetchone()
    return zeile["kalibrierung_modus"] if zeile else None


def _raumcheck(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    """Nach ``p1-kalibrierung``: domainweite Schluessel (oder nicht pruefbar
    ohne Messung) und ob der Raumcheck ueberhaupt bestaetigt ist. Die DB
    wird nur gelesen, wenn kein ``vad_*``-Schluessel da ist."""
    token = kontext.gruppen[station.gruppe - 1].token
    schluessel = speicher_schluessel(kontext.page)
    befunde = inv.pruefe_raumcheck_schluessel(schluessel, token, station.schluessel,
                                              alle_tokens=_alle_tokens(kontext))
    if not any(k.startswith(inv.GRUPPENSCHLUESSEL_PRAEFIXE) for k in schluessel):
        befunde += inv.pruefe_raumcheck_bestaetigt(
            schluessel, _lies_kalibrierung_modus(kontext, chat_id), station.schluessel)
    return befunde


def _zweite_gruppe(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    """Gemeldet werden nur ``vad_*``-Schluessel, die KEINEN Gruppentoken
    tragen: die korrekt gebundene Messung von Gruppe 1 (``vad_*:<tok1>:…``)
    liegt auf demselben Geraet legitim im Speicher und ist kein Befund."""
    gruppe = kontext.gruppen[max(station.gruppe, 2) - 1]
    befunde = inv.pruefe_raumcheck_schluessel(
        speicher_schluessel(kontext.page), gruppe.token, station.schluessel,
        alle_tokens=_alle_tokens(kontext))
    if befunde and kontext.page.locator("#kalibrierung-neu:visible").count():
        befunde = [dataclasses.replace(
            b, text=b.text + " DOM: 'Measure again' ist in der zweiten Gruppe sichtbar, "
                             "ohne dass dort gemessen wurde.") for b in befunde]
    return befunde


def _p2_werkbank(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    return inv.pruefe_p2_werkbank(_lies_fragen(kontext, chat_id),
                                  _sichtbare_fragen(kontext.beobachter), station.schluessel)


# --- Padua live-reif Phase 3+4 (Task 2c) -------------------------------------


def _lies_p34(kontext: PruefKontext, chat_id: int) -> inv.P34Stand:
    with inv.oeffne_lesend(kontext.db_pfad) as conn:
        return inv.lese_p34_stand(conn, chat_id)


def _nach_aufnahme_p34(station, kontext: PruefKontext, chat_id: int, *, pruefe, ende, frist_s: float,
                       knopf_text: str, grace_s: float = inv.GRACE_NACH_SIGNAL_S) -> list[inv.Befund]:
    """Gemeinsamer Kern von ``_nach_interview``/``_nach_brainstorm``: wie
    ``_nach_ende``, aber ueber ``P34Stand`` und ``kontext.warte_p34``
    (andere Signatur als ``kontext.warte``: ``(lese, pruefe, *, frist_s,
    ende, grace_s)``, siehe ``browser_invarianten.warte_auf``).

    ``ende`` (I2, Fix round 1): das Positiv-Signal, das ``warte_auf`` von der
    reinen "keine Befunde"-Zwischenmessung unterscheidet -- ohne ``ende``
    wuerde eine zweite, verspaetete Statuszeile/Karte nie geprueft.

    ``grace_s`` (M3, Fix round 2): ``_nach_interview`` reicht
    ``inv.GRACE_NACH_INTERVIEW_S`` durch (laenger als der Nachhol-Takt),
    ``_nach_brainstorm`` laesst die kuerzere Vorgabe stehen."""
    if kontext.ergebnis_p34 is not None:
        befunde, stand = kontext.ergebnis_p34
    else:
        vorher = kontext.vorher_p34
        if vorher is None:
            vorher = _lies_p34(kontext, chat_id)
        kontext.notizen.append(
            f"{station.schluessel}: kein Harness-Klick auf {knopf_text!r} -- Vorher-Stand vom "
            "Stationsbeginn, Wartezeit ab Stationsende")
        befunde, stand = kontext.warte_p34(
            lambda: _lies_p34(kontext, chat_id), lambda s: pruefe(vorher, s), frist_s=frist_s,
            ende=lambda s: ende(vorher, s), grace_s=grace_s)
    kontext.stand_p34 = stand
    return list(befunde)


def _nach_interview(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    return _nach_aufnahme_p34(
        station, kontext, chat_id,
        pruefe=lambda vorher, stand: inv.pruefe_nach_interview(vorher, stand, station.schluessel),
        ende=inv.hat_neue_statuszeile,
        frist_s=inv.FRIST_NACH_INTERVIEW_S, knopf_text="End interview",
        grace_s=inv.GRACE_NACH_INTERVIEW_S)


def _nach_brainstorm(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    return _nach_aufnahme_p34(
        station, kontext, chat_id,
        pruefe=lambda vorher, stand: inv.pruefe_nach_brainstorm(
            vorher, kontext.vor_ende_p34 or vorher, stand, station.schluessel),
        ende=lambda vorher, stand: inv.hat_neue_karte(kontext.vor_ende_p34 or vorher, stand),
        frist_s=inv.FRIST_NACH_BRAINSTORM_S, knopf_text="Discussion done")


def _bereich_je_phase(kontext: PruefKontext, phase: int) -> tuple[int, int]:
    """Vereinigung der ``aufruf_bereiche`` aller bisher gelaufenen Stationen
    dieser Phase -- min(``von``) bis max(``bis``), ``(0, 0)`` ohne eine
    einzige Station dieser Phase (dann gibt es nichts zu pruefen)."""
    grenzen = [g for schluessel, p in kontext.stationen_phase.items() if p == phase
               for g in kontext.aufruf_bereiche.get(schluessel, ())]
    return (min(grenzen), max(grenzen)) if grenzen else (0, 0)


def _modellwahl(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    """M2 (Review 05.10.2026, Fix round 2): an einer Phase-3-Station
    (``p3-uebergang``) ist der Phase-4-Bereich naturgemaess noch leer (keine
    Phase-4-Station ist gelaufen) -- das lieferte dort IMMER
    ``nicht_pruefbar:p4_gespraech_nicht_opus`` als Rauschen, deshalb wird an
    einer Phase-3-Station NUR der Phase-3-Teil geprueft.

    An einer Phase-4-Station wird der Phase-3-Teil NUR dann uebersprungen,
    wenn er schon an einer frueheren Station dieses Laufs geprueft wurde
    (``kontext.modellwahl_phasen_geprueft``, dasselbe ``set``-Objekt wandert
    per Referenz durch den ganzen Lauf) -- sonst kaeme ein echter
    ``P3_GESPRAECH_OPUS``-Befund dort ein zweites Mal. Lief NIE eine eigene
    Phase-3-Station mit diesem Haken (z. B. weil sie vorher scheiterte), ist
    der Phase-3-Teil noch UNGEPRUEFT -- dann prueft die Phase-4-Station ihn
    vollstaendig nach (``nur_phase=None``), damit ein Phase-3-Befund nicht
    spurlos verschwindet (siehe M1, Fix round 1:
    ``test_aufruf_waehrend_gescheiterter_station_bleibt_fuer_modellwahl_sichtbar``)."""
    stand = _lies_p34(kontext, chat_id)
    bereich3 = _bereich_je_phase(kontext, 3)
    bereich4 = _bereich_je_phase(kontext, 4)
    geprueft = kontext.modellwahl_phasen_geprueft
    if station.phase == 3:
        nur_phase = 3
    elif 3 in geprueft:
        nur_phase = 4
    else:
        nur_phase = None
    befunde = inv.pruefe_modellwahl(
        stand, bereich3, bereich4, station.schluessel, nur_phase=nur_phase)
    geprueft.update({3, 4} if nur_phase is None else {nur_phase})
    return befunde


def _p5_angebot(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    return inv.pruefe_p5_angebot(_lies_p34(kontext, chat_id), station.schluessel)


def _pause_resume(station, kontext: PruefKontext, chat_id: int) -> list[inv.Befund]:
    """Coverage-Luecke Pause/Resume (p34-abnahme-verfahren.md §3): liest
    ``kontext.lauf['pause_resume_ok']`` (von ``browser_lauf.
    _fuehre_station_aus``, ueber ``Station.pause_resume`` deterministisch
    ausgeloest -- ``_pausiere_und_fortsetze_aufnahme``). ``versucht`` ist die
    Stationsabsicht selbst (``station.pause_resume``), nicht nur ob es
    geklappt hat: eine Station, die es anfordert, aber bei der die Aufnahme
    nie lief (z. B. H1), soll einen echten Befund zeigen, nicht
    ``nicht_pruefbar``."""
    lauf = kontext.lauf or {}
    return inv.pruefe_pause_resume(
        bool(lauf.get("pause_resume_ok")), station.pause_resume, station.schluessel)


HAKEN: dict[str, Callable] = {
    "nach_ende": _nach_ende,
    "verhoerer": _verhoerer,
    "wissen": _wissen,
    "raumcheck": _raumcheck,
    "zweite_gruppe": _zweite_gruppe,
    "p2_werkbank": _p2_werkbank,
    "nach_interview": _nach_interview,
    "nach_brainstorm": _nach_brainstorm,
    "modellwahl": _modellwahl,
    "p5_angebot": _p5_angebot,
    "pause_resume": _pause_resume,
}


def fuehre_pruefungen(station, kontext: PruefKontext) -> list[inv.Befund]:
    """Alle Pruefungen aus ``station.pruefung`` in ihrer Reihenfolge
    (``nach_ende`` vor ``verhoerer``: der zweite liest den Stand des
    ersten). Eine Ausnahme in einem Haken wird selbst ein Befund "hoch" --
    nie still verschluckt (Symptomregel)."""
    chat_id = kontext.gruppen[station.gruppe - 1].chat_id
    befunde: list[inv.Befund] = []
    for name in station.pruefung:
        haken = HAKEN.get(name)
        if haken is None:
            befunde.append(inv.Befund(f"pruefung_unbekannt:{name}", station.schluessel,
                                      f"Unbekannte Pruefung {name!r} an Station {station.schluessel}."))
            continue
        try:
            befunde += haken(station, kontext, chat_id)
        except Exception as fehler:
            log.exception("Pruefung %s an Station %s gescheitert", name, station.schluessel)
            befunde.append(inv.Befund(
                f"pruefung_gescheitert:{name}", station.schluessel,
                f"Pruefung {name} an Station {station.schluessel} warf "
                f"{type(fehler).__name__}: {fehler}"))
    return befunde


def befund_ausnahme(station, fehler: BaseException) -> inv.Befund:
    """Symptomregel: eine Station, die mit einer Ausnahme endet, ist nicht
    erreicht -- mit dem Ausnahmetext im Befund."""
    return inv.Befund(
        f"{inv.STATION_NICHT_ERREICHT}:{station.schluessel}", station.schluessel,
        f"Station {station.schluessel} nicht erreicht (Ausnahme {type(fehler).__name__}: {fehler}).")

"""Mess-/Pruefskript fuer Karte t_97f605c7: Treue, Kumulation, Platz im
Prompt, Nutzung -- gegen die aggregierte Fixture aus Task 1
(``scripts/fixture_padua_aggregiert.py``).

Diese Datei schreibt NICHT den BEFUND (das macht der Orchestrator danach
aus den Zahlen hier) -- sie liefert die harten Zahlen und
bestandenen/durchgefallenen Pruefungen, auf denen der Bericht aufbaut:

1. ``treue_wortueberlappung`` -- mechanische Vorfilterung, ob ein freier Text
   (Verdichtung, Zusammenfassung, Buehnenkarte) einen Eigennamen oder ein
   Zitat enthaelt, das im zugehoerigen Transkript NICHT vorkommt.
2. ``kumulation_tabelle`` -- Wachstum und Dubletten ueber mehrere Sessions
   eines Strangs.
3. ``ersetzt_oder_haengt_an`` -- Zeilenzahl einer Tabelle (ersetzt eine
   Zeile bei jedem Lauf, oder haengt an).
4. ``platz_im_prompt`` / ``pruefe_phasen_asymmetrie`` -- was ``kontext.baue``
   tatsaechlich in den Prompt legt, und ob die in AGENTS.md behauptete
   Phasen-Gating-Asymmetrie (Diskussion ohne Phasenfilter, begriffe_detail
   nur bei Phase 2 oder >= 4) am lebenden Code stimmt.
5. ``provoziere_kuerzung`` -- ob und in welcher Reihenfolge die
   Kuerzungsleiter (``kontext._kuerze_auf_budget``) die beiden P1-Bloecke vor
   den P3-Verdichtungen wegwirft, wenn das Budget nicht reicht.
6. ``nutzung_befund`` -- welche der fuenf Suchbegriffe in welcher
   Prompt-Datei tatsaechlich stehen (reine Fundstellen, keine Interpretation).

``main()`` baut dafuer eine Wegwerf-SQLite-Datenbank, fuellt sie ueber
``fixture_padua_aggregiert.baue_alle`` und druckt einen Klartextbericht mit
echten Zahlen auf stdout -- die Vorlage fuer BEFUND.md.
"""

from __future__ import annotations

import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from interview_theater import db, einstellungen, kontext, repo, zitat
from scripts import fixture_padua_aggregiert as fix

# ---------------------------------------------------------------------------
# 1. Treue: mechanische Wortueberlappung + Zitatpruefung
# ---------------------------------------------------------------------------

#: Dieselbe einfache Form wie ``interview_theater.diskussion._ZITAT_MUSTER``
#: -- hier neu definiert statt importiert, damit dieses Skript von keinem
#: internen Modulnamen abhaengt, der sich unabhaengig von dieser Karte
#: aendern kann.
_ZITAT_MUSTER = re.compile(r'"([^"]+)"')

#: Woerter aus Buchstaben inkl. der deutschen Sonderzeichen -- wie vom Brief
#: vorgeschlagen, auch wenn der aktuelle Freitext durchgehend englisch ist:
#: ein kuenftiger deutscher Freitext soll denselben Code treffen.
_WORT_MUSTER = re.compile(r"[A-Za-zÄÖÜäöüß]+")

#: Grossgeschriebene Fuellwoerter, die KEINE Eigennamen sind -- empirisch aus
#: den 15 Freitexten der drei Straenge zusammengestellt (nicht aus einer
#: generischen Stopwortliste kopiert): jedes Wort hier wurde beim ersten
#: Testlauf als Fehlalarm beobachtet, dann hier eingetragen, bis KEINE der
#: nicht-fabrizierten Sessions mehr falsch alarmiert (siehe Testdatei und der
#: Docstring von ``treue_wortueberlappung`` fuer die Begruendung, warum eine
#: Satzanfang-Position-Regel hier NICHT funktioniert).
_FUELLWOERTER = frozenset({
    "the", "a", "an", "one", "someone", "something", "somewhere", "anything",
    "she", "he", "it", "they", "we", "i", "you", "her", "his", "its", "their",
    "our", "your", "my", "this", "that", "these", "those", "who", "what",
    "which", "where", "when", "while", "if", "so", "and", "but", "or",
    "because", "although", "though", "however", "then", "now", "there",
    "here", "later", "finally", "overall", "give", "keep", "for", "by",
    "after", "before", "until", "since", "during", "meanwhile", "yes", "no",
    "ok", "okay", "also", "still", "just", "only", "even", "well", "right",
    "true", "false", "not",
})


def treue_wortueberlappung(freitext: str, transkript: str) -> dict:
    """Mechanische Vorfilterung: welche Kandidatenwoerter in ``freitext``
    stehen NIRGENDS (case-insensitiv) in ``transkript`` -- kein NLP, kein
    LLM-Aufruf, nur ``re``/``str``.

    **Kandidat ist, wer grossgeschrieben, mindestens 3 Zeichen lang, NICHT
    durchgehend GROSS (das waere eine Kopfzeile/ein Label wie "STAGE NOTE:",
    kein Eigenname) und NICHT in ``_FUELLWOERTER`` steht.**

    Bewusst OHNE die vom Brief vorgeschlagene dritte Bedingung "nicht das
    erste Wort eines Satzes": die Honeypot-Fabrikation der Diskussion
    ("Dorotea") steht im echten Fixture-Text direkt nach einem Satzende
    ("... one participant said. Dorotea, who joined ...") und waere mit
    einer reinen Satzanfang-Ausschlussregel selbst aus den Kandidaten
    gefallen -- der Test, den diese Funktion bestehen MUSS, waere nie grün
    geworden. Die Fuellwortliste uebernimmt die Aufgabe stattdessen direkt an
    den WOERTERN, die tatsaechlich als Fehlalarm auftraten ("The", "One",
    "Someone", "Give", "Keep", "For", ...), und trifft damit praeziser als
    eine Positionsregel, die jedes Wort nach einem Punkt gleich behandelt.

    **Bekannte, bewusst belassene Grenzen** (siehe Testdatei und Bericht):
    diese Vorfilterung ist mechanisch, nicht semantisch. Zwei echte,
    nicht-fabrizierte Faelle aus der Fixture werden trotzdem alarmiert, weil
    das Kandidatenwort zwar legitim, aber nicht WOERTLICH im uebergebenen
    ``transkript`` steht:
    - Interview-Session 1: "Quran" (englische Zusammenfassung) vs. "Koran"
      im deutschen Original -- eine Uebersetzung ist nie ein woertliches
      Zitat, egal wie treu sie ist.
    - Brainstorm-Session 2: "Tommaso" steht in der Buehnenkarte ("... lands
      in the interview material ...") als Verweis auf eine Figur, die im
      selben ``chat_id`` nirgends benannt ist (nicht im Brainstorm-Transkript,
      nicht in Setting/Geschichte) -- ihr Name lebt nur im ANDEREN Strang
      (den Interviews), den eine chat-lokale Pruefung strukturell nicht
      sehen kann.
    Beides sind echte, erklaerbare Befunde einer mechanischen Vorfilterung
    (keine Heuristik-Bugs) -- ein Mensch muesste sie einordnen, genau wie
    jeden anderen Kandidaten. Deshalb bleibt die Funktion bewusst eine
    VORfilterung: sie liefert Kandidaten zur Pruefung, kein Urteil.

    Liefert ``{"kandidaten": [...], "verdaechtig": [...], "quote_pruefungen":
    [{"zitat": str, "bestanden": bool}, ...]}``."""
    kandidaten: list[str] = []
    for wort in _WORT_MUSTER.findall(freitext or ""):
        if len(wort) < 3:
            continue
        if not wort[0].isupper():
            continue
        if wort.isupper():  # ALL CAPS: Kopfzeile/Label, kein Eigenname
            continue
        if wort.lower() in _FUELLWOERTER:
            continue
        kandidaten.append(wort)

    transkript_lower = (transkript or "").lower()
    verdaechtig = [w for w in kandidaten if w.lower() not in transkript_lower]

    quote_pruefungen = [
        {"zitat": z, "bestanden": zitat.pruefe(z, transkript or "")}
        for z in _ZITAT_MUSTER.findall(freitext or "")
    ]
    return {
        "kandidaten": kandidaten,
        "verdaechtig": verdaechtig,
        "quote_pruefungen": quote_pruefungen,
    }


# ---------------------------------------------------------------------------
# 2. Kumulation
# ---------------------------------------------------------------------------


def kumulation_tabelle(sessions: list[dict], schluessel_zeichen: str) -> list[dict]:
    """Wachstum und Dubletten ueber eine Session-Liste (die Rueckgabe einer
    der drei ``baue_*_sessions``-Funktionen aus Task 1).

    Pure Funktion, kein ``conn`` noetig: der Freitext-Vergleich fuer
    ``ist_dublette`` laeuft generisch ueber den GANZEN Session-Dict (ohne das
    Feld ``"session"``, das sich naturgemaess je Session unterscheidet) --
    nicht ueber einen fest benannten Freitext-Schluessel, weil die drei
    Straenge unterschiedliche Schluessel fuehren (``verdichtung_text``,
    ``zusammenfassung`` -- Brainstorm-Sessions haben ueberhaupt kein
    Freitextfeld im Rueckgabedict, nur Zahlen/Flags). Zwei Sessions sind
    WORTWOeRTLICH gleich, wenn ihre uebrigen Felder uebereinstimmen -- und
    das setzt insbesondere voraus, dass der tatsaechliche Freitext (wo
    vorhanden) identisch ist."""
    ergebnis: list[dict] = []
    gesehen: list[dict] = []
    vorheriger_wert = None
    for i, session in enumerate(sessions):
        wert = session[schluessel_zeichen]
        vergleichbar = {k: v for k, v in session.items() if k != "session"}
        ist_dublette = vergleichbar in gesehen
        gesehen.append(vergleichbar)
        wachstum = 0 if i == 0 else wert - vorheriger_wert
        ergebnis.append({
            "session": session.get("session", i + 1),
            schluessel_zeichen: wert,
            "wachstum_seit_vorher": wachstum,
            "ist_dublette": ist_dublette,
        })
        vorheriger_wert = wert
    return ergebnis


# ---------------------------------------------------------------------------
# 3. Ersetzen vs. Anhaengen
# ---------------------------------------------------------------------------


def ersetzt_oder_haengt_an(conn, chat_id: int, tabellenname: str) -> dict:
    """Zeilenzahl einer Tabelle fuer eine Gruppe -- direktes SQL wie in
    ``fixture_padua_voll.fensterbefund``: dies ist ein Pruefskript, keine
    Fachlogik, und die Stelle, an der ``repo.py``/``db.py`` sonst alles SQL
    buendeln, gilt hier nicht."""
    n = conn.execute(
        f"SELECT COUNT(*) FROM {tabellenname} WHERE chat_id=?", (chat_id,),
    ).fetchone()[0]
    return {"tabelle": tabellenname, "zeilen": n}


# ---------------------------------------------------------------------------
# Hilfsfunktion: ein minimaler, gueltiger Ausloeser (Nachtrag zum Brief)
# ---------------------------------------------------------------------------

#: Ein fester Zeitpunkt (statt "jetzt") -- die aggregierte Fixture schreibt
#: selbst keine Zeilen in ``nachricht``, ein neuer Ausloeser darf also nicht
#: mit irgendetwas kollidieren, das schon da ist. Ein naiver (tz-loser)
#: Zeitstempel, weil jede andere Nachricht, die dieses Skript selbst anlegt,
#: ebenfalls naiv ist -- ``datetime.fromisoformat``-Vergleiche in
#: ``kontext.waehle_fenster`` brechen sonst mit
#: "can't compare offset-naive and offset-aware datetimes".
_AUSLOESER_ZEITPUNKT = datetime(2026, 10, 1, 11, 0, 0)


def _ausloeser(conn, chat_id: int, message_id: int, text: str = "ok, weiter") -> list:
    """Eine einzelne, gueltige Ausloeser-Nachricht fuer ``kontext.baue`` --
    genau das Muster aus dem Nachtrag des Briefs. Idempotent: ein zweiter
    Aufruf mit derselben ``message_id`` legt dieselbe Zeile nicht doppelt an
    (``repo.merke_nachricht`` ist ``INSERT OR IGNORE``), liefert aber
    weiterhin die vorhandene Zeile zurueck."""
    repo.merke_nachricht(
        conn, chat_id, message_id, "Giulia", 0, "text", text,
        _AUSLOESER_ZEITPUNKT.isoformat(),
    )
    zeile = repo.hole_nachricht(conn, chat_id, message_id)
    return [zeile]


# ---------------------------------------------------------------------------
# 4. Platz im Prompt
# ---------------------------------------------------------------------------

_PLATZ_AUSLOESER_MESSAGE_ID = 996_001


def platz_im_prompt(conn, chat_id: int, e) -> dict:
    """Baut einen minimalen Ausloeser, ruft ``kontext.baue`` EINMAL mit
    ``protokoll`` auf und liefert ``protokoll[-1]`` angereichert um drei
    Anteils-Zeilen (0.0 bei ``gesamt == 0``, nicht ``ZeroDivisionError``)."""
    ausloeser = _ausloeser(conn, chat_id, _PLATZ_AUSLOESER_MESSAGE_ID)
    protokoll: list = []
    kontext.baue(conn, chat_id, ausloeser, e, protokoll=protokoll)
    stand = dict(protokoll[-1])
    stand["bloecke"] = dict(stand["bloecke"])
    gesamt = stand["gesamt"]

    def anteil(name: str) -> float:
        return (stand["bloecke"].get(name, 0) / gesamt * 100) if gesamt else 0.0

    stand["anteil_diskussion_prozent"] = anteil("diskussion")
    stand["anteil_begriffe_detail_prozent"] = anteil("begriffe_detail")
    stand["anteil_verdichtungen_prozent"] = anteil("verdichtungen")
    return stand


# ---------------------------------------------------------------------------
# 4b. Phasen-Gating-Asymmetrie (verifizierte Tatsache, selbst nachgerechnet)
# ---------------------------------------------------------------------------

_ASYMMETRIE_AUSLOESER_MESSAGE_ID = 995_001


def pruefe_phasen_asymmetrie(conn, chat_id: int, e) -> dict:
    """Verifiziert AM LAUFENDEN ``kontext.baue`` (nicht nur durch Lesen) die
    in AGENTS.md behauptete Phase-Gating-Asymmetrie: ``_baue_diskussion_block``
    hat KEINEN Phasenfilter (erscheint in jeder Phase, sobald
    ``diskussion_verdichtung_text`` nicht leer ist), waehrend
    ``_baue_begriffe_detail`` nur bei Phase 2 oder >= 4 erscheint (Code:
    ``if phase != 2 and phase < 4: return ""``).

    Derselbe ``chat_id``, derselbe Datenstand -- nur die Phase wechselt
    zwischen den beiden ``kontext.baue``-Aufrufen (Phase 1, dann Phase 7, wie
    im Brief vorgeschlagen). Am Ende wird die Phase auf ihren urspruenglichen
    Wert zurueckgesetzt (ersatzweise 1, wenn sie nie gesetzt war -- das ist
    fuer ``phasen.aktuelle`` ohnehin aequivalent zu NULL), damit dieser
    Aufruf keine bleibende Nebenwirkung fuer andere Pruefungen auf demselben
    ``chat_id`` hinterlaesst."""
    ausloeser = _ausloeser(conn, chat_id, _ASYMMETRIE_AUSLOESER_MESSAGE_ID)
    urspruenglich = repo.hole_phase(conn, chat_id)

    ergebnis: dict = {}
    for phase, schluessel in ((1, "phase_1"), (7, "phase_7")):
        repo.setze_phase(conn, chat_id, phase)
        protokoll: list = []
        kontext.baue(conn, chat_id, ausloeser, e, protokoll=protokoll)
        bloecke = protokoll[-1]["bloecke"]
        ergebnis[schluessel] = {
            "diskussion": bloecke["diskussion"],
            "begriffe_detail": bloecke["begriffe_detail"],
        }

    repo.setze_phase(conn, chat_id, urspruenglich if urspruenglich is not None else 1)
    return ergebnis


# ---------------------------------------------------------------------------
# 5. Kuerzung provozieren
# ---------------------------------------------------------------------------

_KUERZUNG_AUSLOESER_MESSAGE_ID = 997_001
_KUERZUNG_FESTLEGUNGEN = 30
_KUERZUNG_FENSTER_NACHRICHTEN = 25
_KUERZUNG_SCHRITT_ZEICHEN = 1000
#: Sicherheitsdeckel gegen eine Endlosschleife. Empirisch gemessen (siehe
#: Bericht) faellt die Kuerzung bei diesem Aufbau spaetestens in Runde 24
#: vollstaendig durch alle Stufen -- 30 Runden lassen Luft, ohne den Lauf
#: spuerbar zu verlangsamen (kein Netz, kein LLM, nur SQLite + reines Python).
_KUERZUNG_MAX_RUNDEN = 30


def provoziere_kuerzung(conn, chat_id: int, e) -> dict:
    """Legt auf ``chat_id`` zusaetzliches Material an -- lange Festlegungen,
    einen dichten, langen Verlauf (fuellt das Fenster nahe an sein Maximum)
    und eine wachsende Zahl zusaetzlicher Verdichtungen --, bis
    ``kontext.baue(..., protokoll=protokoll)`` wirklich
    ``protokoll[-1]["gekuerzt"] is True`` liefert, und beobachtet dabei JE
    RUNDE, welche Bloecke (``fenster``, ``festlegungen``, ``diskussion``,
    ``begriffe_detail``, ``verdichtungen``) zuerst auf 0 fallen.

    **Nebenwirkung, bewusst:** diese Funktion ist destruktiv -- sie schreibt
    dauerhaft grosse Mengen Testmaterial auf ``chat_id`` und ist nur fuer
    eine Wegwerf-Datenbank gedacht (wie hier, ``main()``s temporaeres
    Verzeichnis). Sie setzt NICHT selbst die Phase: wer begriffe_detail
    gleichzeitig mit Diskussion und Verdichtungen beobachten will (wie in
    ``main()``), ruft vorher ``repo.setze_phase(conn, chat_id, 2)`` --
    Phase 2 ist die einzige, in der ``material_erlaubt`` (Verdichtungen,
    < Phase 4) UND die ``begriffe_detail``-Gating-Bedingung (``phase == 2``)
    gleichzeitig wahr sind."""
    ausloeser = _ausloeser(conn, chat_id, _KUERZUNG_AUSLOESER_MESSAGE_ID)

    for i in range(_KUERZUNG_FESTLEGUNGEN):
        repo.schreibe_festlegung(conn, chat_id, "stil", "x" * 180 + f" Zeile {i}")

    basis = datetime(2026, 10, 1, 9, 0, 0)
    for i in range(_KUERZUNG_FENSTER_NACHRICHTEN):
        ts = (basis + timedelta(minutes=i)).isoformat()
        repo.merke_nachricht(
            conn, chat_id, 997_100 + i, "Marco", 0, "text",
            "lorem " * 80 + f"Zeile {i}", ts,
        )

    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, 997_900, "lang", "text", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "Fuellmaterial. " * 100)

    verlauf: list[tuple[int, dict]] = []
    letzter_stand: dict | None = None
    beobachtete = ("fenster", "festlegungen", "diskussion", "begriffe_detail",
                   "verdichtungen")
    for runde in range(1, _KUERZUNG_MAX_RUNDEN + 1):
        repo.speichere_verdichtung(
            conn, chat_id, aufnahme_id,
            "z" * _KUERZUNG_SCHRITT_ZEICHEN + f" Runde {runde}", [],
        )
        protokoll: list = []
        kontext.baue(conn, chat_id, ausloeser, e, protokoll=protokoll)
        letzter_stand = protokoll[-1]
        verlauf.append((runde, dict(letzter_stand["bloecke"])))
        if all(letzter_stand["bloecke"].get(n) == 0 for n in
               ("diskussion", "begriffe_detail", "verdichtungen")):
            break

    assert letzter_stand is not None  # mindestens eine Runde laeuft immer
    bloecke_am_ende = dict(letzter_stand["bloecke"])
    gekuerzt = bool(letzter_stand["gekuerzt"])

    # Reihenfolge, in der je ein Block ZUERST auf 0 fiel, ueber alle Runden.
    reihenfolge: list[tuple[str, int]] = []
    gesehen_null: set[str] = set()
    for runde, bloecke in verlauf:
        for name in beobachtete:
            if bloecke.get(name) == 0 and name not in gesehen_null:
                gesehen_null.add(name)
                reihenfolge.append((name, runde))

    if not gekuerzt:
        beobachtung = (
            f"KEINE Kuerzung ausgeloest nach {len(verlauf)} Runden "
            f"wachsenden Materials (letzter Gesamtwert {bloecke_am_ende} "
            "Token) -- ehrlich gemeldet, keine Kuerzung erfunden."
        )
    else:
        beobachtung = (
            f"Kuerzung ausgeloest nach {len(verlauf)} Runden wachsenden "
            f"Materials (je +{_KUERZUNG_SCHRITT_ZEICHEN} Zeichen Verdichtung "
            f"je Runde, zusaetzlich {_KUERZUNG_FESTLEGUNGEN} lange "
            f"Festlegungen und {_KUERZUNG_FENSTER_NACHRICHTEN} dichte "
            "Verlaufsnachrichten vorab). Reihenfolge, in der Bloecke auf 0 "
            f"fielen (Block, erste Runde): {reihenfolge or 'keiner fiel auf 0'}."
        )

    return {
        "gekuerzt": gekuerzt,
        "bloecke_am_ende": bloecke_am_ende,
        "beobachtung": beobachtung,
        "runden": len(verlauf),
        "reihenfolge_null": reihenfolge,
    }


# ---------------------------------------------------------------------------
# 6. Nutzung im Prompt
# ---------------------------------------------------------------------------

#: Die fuenf Suchbegriffe aus dem Brief -- wortwoertlich, case-sensitiv.
NUTZUNG_SUCHBEGRIFFE = (
    "Kernpaket", "Verdichtung", "Begriffs-Diskussion", "begriffe_detail",
    "Begriffsboard",
)


def _projekt_root() -> Path:
    """``interview_theater/`` liegt ein Verzeichnis ueber ``scripts/`` --
    robust gegen den Aufrufort (``python -m scripts.pruefe_padua_aggregiert``
    aus einem beliebigen cwd)."""
    return Path(__file__).resolve().parents[1]


def nutzung_befund() -> dict:
    """Liest ``interview_theater/prompts/system.md`` und jede Datei unter
    ``interview_theater/prompts/phasen/*.md`` und sucht wortwoertlich
    (case-sensitiv) nach ``NUTZUNG_SUCHBEGRIFFE``.

    Liefert ``{suchbegriff: [dateiname, ...]}`` -- rohe Fundstellen, keine
    Interpretation (die schreibt der Orchestrator in BEFUND.md)."""
    root = _projekt_root()
    dateien = [root / "interview_theater" / "prompts" / "system.md"]
    dateien += sorted((root / "interview_theater" / "prompts" / "phasen").glob("*.md"))

    treffer: dict[str, list[str]] = {b: [] for b in NUTZUNG_SUCHBEGRIFFE}
    for datei in dateien:
        text = datei.read_text(encoding="utf-8")
        for begriff in NUTZUNG_SUCHBEGRIFFE:
            if begriff in text:
                treffer[begriff].append(datei.name)
    return treffer


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _drucke_kumulation(titel: str, sessions: list[dict], schluessel: str) -> None:
    print(f"\n-- Kumulation: {titel} ({schluessel}) --")
    for zeile in kumulation_tabelle(sessions, schluessel):
        print(f"  {zeile}")


def _drucke_treue(titel: str, faelle: list[tuple[int, str, str, str | None]]) -> None:
    """``faelle``: Liste von (session_nr, freitext, transkript, erwartetes
    Fabrikationswort_oder_None)."""
    print(f"\n-- Treue: {titel} --")
    for session, freitext, transkript, erwartet in faelle:
        befund = treue_wortueberlappung(freitext, transkript)
        status = "OK"
        if erwartet:
            status = "HONEYPOT GEFUNDEN" if erwartet in befund["verdaechtig"] else "HONEYPOT VERFEHLT!"
        print(f"  Session {session}: kandidaten={befund['kandidaten']} "
              f"verdaechtig={befund['verdaechtig']} ({status}) "
              f"zitate={befund['quote_pruefungen']}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_pfad = str(Path(tmp) / "pruefe_padua_aggregiert.db")
        conn = db.verbinde(db_pfad)
        try:
            db.initialisiere(conn)
            ergebnis = fix.baue_alle(conn)

            e = einstellungen.Einstellungen(
                bot_token="T", bot_name="pruefskript", db_pfad=db_pfad,
                audio_verz=str(Path(tmp) / "audio"),
                llm_url="https://llm.test/v1/chat/completions", llm_key="K",
                llm_modell="kimi", stt_basis="https://stt.test",
                stt_produkt="PRODUKT-ID",
            )

            diskussion_chat = fix.chat_id_fuer("diskussion")
            interviews_chat = fix.chat_id_fuer("interviews")
            brainstorm_chat = fix.chat_id_fuer("brainstorm")

            print("=" * 78)
            print("KARTE t_97f605c7 -- Padua aggregiert: Treue / Kumulation / "
                  "Platz im Prompt / Nutzung")
            print("=" * 78)

            # --- 1) Treue -------------------------------------------------
            print("\n" + "#" * 78)
            print("# 1. TREUE (mechanische Wortueberlappung + Zitatpruefung)")
            print("#" * 78)

            diskussion_sessions = ergebnis["diskussion"]["sessions"]
            _drucke_treue(
                "Diskussion (verdichtung_text vs. transkript_bisher)",
                [
                    (s["session"], s["verdichtung_text"], s["transkript_bisher"],
                     s["fabrikationswort"])
                    for s in diskussion_sessions
                ],
            )

            interview_sessions = ergebnis["interviews"]["sessions"]
            _drucke_treue(
                "Interviews (zusammenfassung vs. transkript)",
                [
                    (s["session"], s["zusammenfassung"], s["transkript"],
                     s["fabrikationswort"])
                    for s in interview_sessions
                ],
            )

            # Brainstorm: die Buehnenkarte steht nicht im Session-Dict (Task 1
            # gibt dort nur Zahlen/Flags zurueck), sondern in der Tabelle
            # ``buehnenkarte`` -- wie test_genau_eine_brainstormsession_ist_
            # die_fabrikation es bereits vormacht.
            stand = repo.hole_arbeitsstand(conn, brainstorm_chat)
            grundlage = "\n".join([
                repo.brainstorm_transkript(conn, brainstorm_chat),
                stand["rahmen"] or "",
                stand["geschichte"] or "",
            ])
            karten = conn.execute(
                "SELECT text FROM buehnenkarte WHERE chat_id=? ORDER BY id ASC",
                (brainstorm_chat,),
            ).fetchall()
            brainstorm_faelle = []
            for i, (session, karte) in enumerate(zip(ergebnis["brainstorm"]["sessions"], karten)):
                brainstorm_faelle.append(
                    (session["session"], karte["text"], grundlage, session["fabrikationswort"])
                )
            print("\n-- Treue: Brainstorm (Buehnenkarte vs. Transkript+Setting+Geschichte) --")
            print("   (Grundlage = brainstorm_transkript + rahmen + geschichte, siehe Docstring")
            print("    von treue_wortueberlappung fuer den 'Tommaso'-Befund unten)")
            for session, freitext, transkript, erwartet in brainstorm_faelle:
                befund = treue_wortueberlappung(freitext, transkript)
                status = "OK"
                if erwartet:
                    status = "HONEYPOT GEFUNDEN" if erwartet in befund["verdaechtig"] else "HONEYPOT VERFEHLT!"
                print(f"  Session {session}: kandidaten={befund['kandidaten']} "
                      f"verdaechtig={befund['verdaechtig']} ({status})")

            # --- 2) Kumulation ---------------------------------------------
            print("\n" + "#" * 78)
            print("# 2. KUMULATION (Wachstum und Dubletten ueber mehrere Sessions)")
            print("#" * 78)
            _drucke_kumulation("Diskussion", diskussion_sessions, "zeichen")
            _drucke_kumulation("Interviews", interview_sessions, "zeichen")
            _drucke_kumulation(
                "Brainstorm", ergebnis["brainstorm"]["sessions"],
                "brainstorm_transkript_zeichen",
            )

            # --- 3) Ersetzen vs. Anhaengen ---------------------------------
            print("\n" + "#" * 78)
            print("# 3. ERSETZT ODER HAENGT AN (Zeilenzahl je Tabelle)")
            print("#" * 78)
            for chat_id, tabelle, strang in (
                (diskussion_chat, "diskussion_verdichtung", "Diskussion"),
                (diskussion_chat, "begriffsboard", "Diskussion"),
                (interviews_chat, "verdichtung", "Interviews"),
                (brainstorm_chat, "buehnenkarte", "Brainstorm"),
            ):
                befund = ersetzt_oder_haengt_an(conn, chat_id, tabelle)
                print(f"  [{strang}] {befund}")

            # --- 4) Platz im Prompt + Phasen-Asymmetrie --------------------
            print("\n" + "#" * 78)
            print("# 4. PLATZ IM PROMPT (kontext.baue, protokoll=...)")
            print("#" * 78)
            for chat_id, name in (
                (diskussion_chat, "Diskussion (Phase 1, Vorgabe)"),
                (brainstorm_chat, "Brainstorm (Phase 4)"),
            ):
                stand = platz_im_prompt(conn, chat_id, e)
                print(f"\n  -- {name}, chat_id={chat_id} --")
                print(f"    bloecke={stand['bloecke']}")
                print(f"    gesamt={stand['gesamt']} token, "
                      f"system={stand['system']} token, gekuerzt={stand['gekuerzt']}")
                print(f"    anteil_diskussion_prozent="
                      f"{stand['anteil_diskussion_prozent']:.1f}")
                print(f"    anteil_begriffe_detail_prozent="
                      f"{stand['anteil_begriffe_detail_prozent']:.1f}")
                print(f"    anteil_verdichtungen_prozent="
                      f"{stand['anteil_verdichtungen_prozent']:.1f}")

            print("\n  -- Phasen-Gating-Asymmetrie (derselbe chat_id, Phase 1 vs. 7) --")
            asymmetrie = pruefe_phasen_asymmetrie(conn, diskussion_chat, e)
            print(f"    {asymmetrie}")
            diskussion_konstant = (
                asymmetrie["phase_1"]["diskussion"] > 0
                and asymmetrie["phase_7"]["diskussion"] > 0
            )
            begriffe_detail_asymmetrisch = (
                asymmetrie["phase_1"]["begriffe_detail"] == 0
                and asymmetrie["phase_7"]["begriffe_detail"] > 0
            )
            print(f"    diskussion bei beiden Phasen > 0: {diskussion_konstant}")
            print(f"    begriffe_detail nur bei Phase 7 > 0 (Phase 1 == 0): "
                  f"{begriffe_detail_asymmetrisch}")

            # --- 5) Kuerzung provozieren ------------------------------------
            print("\n" + "#" * 78)
            print("# 5. KUERZUNG PROVOZIEREN (kontext._kuerze_auf_budget)")
            print("#" * 78)
            # Phase 2: einzige Phase, in der Verdichtungen (< Phase 4) UND
            # begriffe_detail (phase == 2) gleichzeitig gezeigt werden --
            # siehe Docstring von provoziere_kuerzung.
            repo.setze_phase(conn, diskussion_chat, 2)
            kuerzung = provoziere_kuerzung(conn, diskussion_chat, e)
            print(f"  gekuerzt={kuerzung['gekuerzt']} nach {kuerzung['runden']} Runden")
            print(f"  beobachtung: {kuerzung['beobachtung']}")
            print(f"  bloecke_am_ende={kuerzung['bloecke_am_ende']}")

            # --- 6) Nutzung im Prompt ---------------------------------------
            print("\n" + "#" * 78)
            print("# 6. NUTZUNG (wo im Prompt-Text stehen die Suchbegriffe wirklich?)")
            print("#" * 78)
            befund = nutzung_befund()
            for begriff, dateien in befund.items():
                print(f"  {begriff!r}: {dateien}")

            print("\n" + "=" * 78)
            print("Ende des Berichts.")
            print("=" * 78)
        finally:
            conn.close()


if __name__ == "__main__":
    main()

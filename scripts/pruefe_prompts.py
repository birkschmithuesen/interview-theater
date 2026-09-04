"""Regressionskorpus gegen das echte Sprachmodell laufen lassen.

**Kein Test, laeuft nie automatisch, kostet Geld.** Die Testsuite unter
``tests/`` prueft nur den Korpus und die Bewertungsfunktionen hier -- ohne
Netz. Dieses Skript ist das Gegenstueck: es schickt jeden Korpusfall an das
echte Modell, mit denselben Einstellungen wie der Bot.

**Wozu.** Seit ``interview_theater/anweisungen.py`` die Prompts heiss nachlaedt,
wird jemand sie waehrend des Workshops aendern. Ohne Korpus ist jede solche
Aenderung ein Blindflug: die Prompts waren an je 4-7 Faellen gemessen, aber
es lag nichts herum, was man danach nochmal laufen lassen koennte
(gedaechtnis-extraktion-agenten.md § 9 Punkt 3, "Regressionsschutz").

Aufruf::

    set -a; . ./betrieb/gruppe1.env; set +a
    PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
    $PY -m scripts.pruefe_prompts erkenner
    $PY -m scripts.pruefe_prompts alle --bericht
    $PY -m scripts.pruefe_prompts erkenner --nur e18-verworfen-kindheitsfragen,n04-zitat-eines-vorschlags
    $PY -m scripts.pruefe_prompts erkenner --modell nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8

Die ``betrieb/<gruppe>.env`` muss vorher geladen sein -- ``einstellungen.laden()``
liest ausschliesslich Umgebungsvariablen und braucht IT_LLM_URL, IT_LLM_KEY,
IT_LLM_MODELL (und die uebrigen Pflichtvariablen). **``IT_DB`` wird bewusst
ueberschrieben:** der Lauf schreibt seine ``aufruf``- und ``vorfall``-Zeilen in
eine Wegwerf-Datenbank in einem Temporaerverzeichnis, nie in die
Betriebsdatenbank.

**Exit-Code.** ``1``, sobald der Erkenner auch nur ein Falsch-Positiv liefert.
Das ist die Kennzahl, die den Erkenner qualifiziert hat (0 FP bei 25
Negativfaellen, SPEC § 4.3a) -- eine Prompt-Aenderung, die sie kaputt macht,
gehoert zurueckgenommen, egal wie gut die Trefferquote sonst aussieht.

**Sequenziell, nie parallel.** Infomaniak liefert bei parallelen Aufrufen
429/5xx. Ein voller Lauf ueber alle drei Korpora sind rund 70 Aufrufe.

Die Nutzertexte baut dieses Skript **nicht selbst**, sondern ueber
``erkenner._baue_nutzertext`` / ``journal._baue_nutzertext``. Die brauchen
eine Datenbankverbindung fuer Arbeitsstand, Figuren und bisheriges Journal --
deshalb die Wegwerf-Datenbank, und deshalb je Fall eine eigene ``chat_id``:
so sieht das Modell exakt den Text, den es im Betrieb saehe, ohne dass hier
die Formatierungslogik ein zweites Mal nachgebaut waere (und beim naechsten
Umbau auseinanderliefe).
"""

import argparse
import json
import re
import statistics
import os
import sys
import tempfile
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, erkenner, journal, llm, repo, verdichter, zitat

#: Wo die Korpusdateien liegen.
KORPUS = Path(__file__).resolve().parent.parent / "korpus"

#: Wo --bericht ohne Pfadangabe hinschreibt (gitignored bis auf .gitkeep --
#: die Berichte enthalten vollstaendige Modellantworten).
BERICHTE = KORPUS / "berichte"

#: Die drei pruefbaren Prompts, in der Reihenfolge, in der "alle" sie laeuft.
PROMPTS = ("erkenner", "journal", "verdichter")

#: CHF je 1 Mio. Token (Eingabe, Ausgabe), Stand 04.09.2026 aus
#: ~/hermes-shared/hermes-knowledge/infomaniak-modelle.md § 1.1. Bewusst hart
#: im Skript und mit Datum: die Datei liegt ausserhalb des Repositories, und
#: Infomaniak aendert die Preise in Monaten -- eine Kostenschaetzung ohne
#: sichtbares Datum waere schlimmer als keine.
PREISE_STAND = "04.09.2026"
PREISE_CHF_JE_MIO_TOKEN = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8": (0.05, 0.20),
    "google/gemma-4-31B-it": (0.20, 0.40),
    "mistralai/Mistral-Small-4-119B-2603": (0.20, 0.75),
    "mistralai/Ministral-3-14B-Instruct-2512": (0.30, 0.40),
    "Qwen/Qwen3.5-122B-A10B-FP8": (0.40, 3.20),
    "moonshotai/Kimi-K2.6": (0.60, 3.00),
    "swiss-ai/Apertus-v1.5-70B": (0.70, 2.50),
    "Qwen/Qwen3.5-397B-A17B-FP8": (0.80, 3.60),
}

#: Trennzeichen zwischen den Muss-Stichwoertern eines erwarteten
#: Journaleintrags (korpus/journal.jsonl, Feld erwartet[].text). Der Korpus
#: legt bewusst KEINEN Wortlaut fest: derselbe Vorschlag laesst sich auf zehn
#: Arten formulieren, und ein Wortlautvergleich wuerde bei jeder harmlosen
#: Umformulierung Alarm schlagen.
STICHWORT_TRENNER = "|"

#: Wortformen, mit denen ein Journaleintrag nicht beginnen darf (Prompt-Regel
#: 2: "Jeder Eintrag muss allein verstaendlich sein ... Keine Woerter wie
#: 'das', 'es', 'die Idee'"). Wird getrennt gezaehlt und geht NICHT in
#: FP/FN ein -- ein Eintrag, der mit einem Artikel beginnt, kann trotzdem
#: inhaltlich richtig sein, und der Exit-Code haengt allein am Erkenner.
PRONOMEN_ANFAENGE = ("er", "sie", "es", "das", "die", "der")


# ---------------------------------------------------------------------------
# Normalisierung und Bewertung -- ohne Netz, ohne Datenbank, einzeln testbar
# ---------------------------------------------------------------------------

#: Umlaute und Eszett werden auf ae/oe/ue/ss abgebildet, bevor verglichen
#: wird. Grund: die Prompts selbst sind in Umschrift geschrieben
#: ("Aenderungen", "woertlich"), die Gruppe schreibt mit Umlauten -- das
#: Modell mischt beides. Ohne diese Faltung waere "ohne Buehnenbild" gegen
#: "ohne Bühnenbild" ein Falsch-Negativ, das nur an der Tastatur liegt.
_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalisiere(text: str) -> str:
    """Kleinschreibung, Umlaute in Umschrift, Satzzeichen weg,
    Whitespace-Folgen zu einem Leerzeichen.

    Bewusst nicht ``interview_theater.zitat.normalisiere``: die dortige Funktion
    darf **nichts** wegwerfen ausser Whitespace und typografischen
    Anfuehrungszeichen, weil sie eine Zitattreue-Aussage traegt (SPEC § 5).
    Hier ist das Gegenteil richtig -- verglichen werden Formulierungen, nicht
    Zitate."""
    text = (text or "").lower().translate(_UMSCHRIFT)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def wert_passt(erwartet: str, geliefert: str) -> bool:
    """Teilstring-Treffer in beide Richtungen nach ``normalisiere``.

    Ein **leerer erwarteter Wert** heisst: allein die ``art`` zaehlt. Das ist
    kein Nachlassen, sondern die Sachlage -- bei ``interview_starten``,
    ``interview_beenden`` und ``wortlaut_aus`` schreibt der Prompt einen leeren
    String vor und ``erkenner._wende_eine_an`` sieht sich den Wert nie an.

    In beide Richtungen, weil der Korpus kurze Kernwerte festhaelt ("Meryem",
    "Mutter gegen Tochter") und das Modell laengere liefert ("Interview mit
    Meryem"). Was hier zaehlt, ist die Sache, nicht die Formulierung."""
    e = normalisiere(erwartet)
    if not e:
        return True
    g = normalisiere(geliefert)
    return bool(g) and (e in g or g in e)


def vergleiche_erkenner(erwartet: list[dict], geliefert: list[dict]) -> dict:
    """Vergleicht zwei Mengen von ``{"art", "wert"}``.

    ``art`` muss exakt stimmen, ``wert`` nach ``wert_passt``. Jede gelieferte
    Aenderung kann hoechstens eine erwartete bedienen (sonst wuerden zwei
    Figuren durch einen einzigen Treffer abgedeckt).

    Liefert ``{"treffer", "fehlend", "ueberzaehlig"}`` -- Falsch-Negative und
    Falsch-Positive getrennt, weil sie unterschiedlich schwer wiegen: ein FN
    ist eine verpasste Notiz, ein FP schreibt etwas Falsches in den
    Arbeitsstand und meldet es der Gruppe auch noch."""
    offen = list(geliefert)
    treffer, fehlend = [], []
    for erwartung in erwartet:
        index = None
        for i, kandidat in enumerate(offen):
            if kandidat.get("art") == erwartung.get("art") and wert_passt(
                erwartung.get("wert", ""), kandidat.get("wert", "")
            ):
                index = i
                break
        if index is None:
            fehlend.append(erwartung)
        else:
            treffer.append(offen.pop(index))
    return {"treffer": treffer, "fehlend": fehlend, "ueberzaehlig": offen}


def fragen_ohne_thema(aenderungen: list[dict]) -> list[str]:
    """Prompt-Punkt 5, mechanisch geprueft: steht in jeder Zeile eines
    ``fragen_setzen``-Werts ein Thema vor der Frage ("Koffer: Was war in
    deinem Koffer?")?

    Das Format ist keine Kosmetik: die Gruppenseite rendert daraus eine Liste
    mit fett gesetztem Thema (``web._fragen_html``), und ohne Doppelpunkt
    steht dort die nackte Frage. Sollwert ist deshalb schlicht **mindestens
    ein ':' je Zeile**; welches Thema das Modell waehlt, ist seine Sache.

    Bewusst grob und bewusst getrennt gezaehlt, wie ``beginnt_mit_pronomen``:
    eine Frage ohne Thema ist inhaltlich richtig, nur schlecht dargestellt.
    Das geht **nicht** in FP/FN und nicht in den Exit-Code ein -- der haengt
    allein an den Falsch-Positiven (AGENTS.md)."""
    verletzungen = []
    for aenderung in aenderungen:
        if aenderung.get("art") != "fragen_setzen":
            continue
        for zeile in (aenderung.get("wert") or "").splitlines():
            zeile = zeile.strip(" -•\t")
            if zeile and ":" not in zeile:
                verletzungen.append(zeile)
    return verletzungen


def stichwoerter_aus(text: str) -> list[str]:
    """Zerlegt ein Muss-Stichwort-Set (``"sechs|fragen"``) in seine Teile."""
    return [t.strip() for t in text.split(STICHWORT_TRENNER) if t.strip()]


def beginnt_mit_pronomen(text: str) -> bool:
    """Prompt-Regel 2, mechanisch geprueft: faengt der Eintrag mit einem
    alleinstehenden ``er/sie/es/das/die/der`` an?

    Bewusst grob. Ein Eintrag, der mit "Die" beginnt, kann voellig in Ordnung
    sein -- deshalb ist das ein eigener, gezaehlter Hinweis und kein Fehler,
    der in FP/FN einginge oder den Exit-Code beeinflusste. Er zeigt an, wo
    man in die Spalte "geliefert" schauen sollte."""
    worte = normalisiere(text).split()
    return bool(worte) and worte[0] in PRONOMEN_ANFAENGE


def vergleiche_journal(erwartet: list[dict], geliefert: list[dict]) -> dict:
    """Bewertet einen Journalfall.

    Leer gegen nicht-leer ist die wichtigste Unterscheidung und wird exakt
    genommen: erwartet der Korpus nichts und das Modell liefert etwas, ist
    jeder gelieferte Eintrag ein Falsch-Positiv (und umgekehrt jedes erwartete
    Stichwortset ein Falsch-Negativ). Das faellt hier ohne Sonderfall heraus,
    weil die Zuordnung unten dann schlicht nichts findet.

    Bei nicht-leer muss jedes erwartete Stichwortset in **genau einem**
    gelieferten Eintrag vorkommen. "Genau einem" ist Absicht: passt ein Set auf
    zwei Eintraege, hat das Modell eine Sache doppelt notiert oder zwei Sachen
    zu unscharf formuliert -- beides zaehlt als Fehlschlag, nicht als Treffer.
    """
    verbraucht: set[int] = set()
    treffer, fehlend, mehrdeutig = [], [], []
    for erwartung in erwartet:
        muss = [normalisiere(s) for s in stichwoerter_aus(erwartung.get("text", ""))]
        passende = [
            i
            for i, eintrag in enumerate(geliefert)
            if i not in verbraucht
            and all(s in normalisiere(eintrag.get("text", "")) for s in muss)
        ]
        if len(passende) == 1:
            verbraucht.add(passende[0])
            treffer.append(geliefert[passende[0]])
        else:
            fehlend.append(erwartung)
            if len(passende) > 1:
                mehrdeutig.append(erwartung)
    ueberzaehlig = [e for i, e in enumerate(geliefert) if i not in verbraucht]
    return {
        "treffer": treffer,
        "fehlend": fehlend,
        "ueberzaehlig": ueberzaehlig,
        "mehrdeutig": mehrdeutig,
        "pronomen": [e for e in geliefert if beginnt_mit_pronomen(e.get("text", ""))],
    }


def bewerte_verdichter(erwartet: dict, ergebnis: dict, transkript: str) -> dict:
    """Bewertet eine Verdichtung: Belegzitate, Themenanzahl, Stichwoerter.

    Die Zitatpruefung laeuft ueber ``interview_theater.zitat.pruefe`` -- exakt die
    Funktion, die auch im Betrieb entscheidet, ob ein Zitat stehen bleibt oder
    aus dem Thema entfernt wird. Etwas Eigenes hier waere eine zweite Wahrheit
    ueber dieselbe Frage.

    Die Stichwoerter werden gegen Zusammenfassung UND Themen zusammen
    geprueft: ob ein Motiv als Thema oder in der Zusammenfassung auftaucht, ist
    dem Korpus egal -- fehlen darf es nicht."""
    themen = ergebnis.get("kernthemen") or []
    zusammenfassung = ergebnis.get("zusammenfassung") or ""

    zitate_ok, zitate_fehlerhaft = [], []
    for thema in themen:
        beleg = thema.get("beleg_zitat") or ""
        (zitate_ok if zitat.pruefe(beleg, transkript) else zitate_fehlerhaft).append(thema)

    heuhaufen = normalisiere(
        zusammenfassung + " " + " ".join(t.get("thema", "") for t in themen)
    )
    gesucht = erwartet.get("stichwoerter") or []
    gefunden = [s for s in gesucht if normalisiere(s) in heuhaufen]
    vermisst = [s for s in gesucht if normalisiere(s) not in heuhaufen]

    anzahl = len(themen)
    anzahl_ok = erwartet.get("themen_min", 0) <= anzahl <= erwartet.get("themen_max", 99)
    return {
        "anzahl": anzahl,
        "anzahl_ok": anzahl_ok,
        "zitate_ok": zitate_ok,
        "zitate_fehlerhaft": zitate_fehlerhaft,
        "stichwoerter_gefunden": gefunden,
        "stichwoerter_vermisst": vermisst,
    }


def zaehle_verdichter(bewertung: dict) -> tuple[int, int, int]:
    """Bildet die Verdichter-Bewertung auf dieselben drei Zahlen ab wie die
    beiden anderen Prompts, damit die Tabelle eine Tabelle bleibt:

    * **Treffer** = geprueftes Belegzitat + gefundenes Stichwort
    * **FP** = Thema mit einem Zitat, das so nicht im Transkript steht (die
      direkte Halluzinationsmessung, HANDOFF (g))
    * **FN** = vermisstes Stichwort, plus eins, wenn die Themenanzahl ausserhalb
      des erlaubten Bereichs liegt
    """
    treffer = len(bewertung["zitate_ok"]) + len(bewertung["stichwoerter_gefunden"])
    fp = len(bewertung["zitate_fehlerhaft"])
    fn = len(bewertung["stichwoerter_vermisst"]) + (0 if bewertung["anzahl_ok"] else 1)
    return treffer, fp, fn


# ---------------------------------------------------------------------------
# Korpus laden
# ---------------------------------------------------------------------------

def lade_korpus(name: str, nur: list[str] | None = None) -> list[dict]:
    """Liest ``korpus/<name>.jsonl``. ``nur`` filtert auf ids, in der
    Reihenfolge der Datei (nicht in der Reihenfolge der Angabe).

    Unbekannte ids meldet hier bewusst niemand: bei ``alle`` liegt jede id nur
    in genau einem der drei Korpora, ein Filter auf die anderen beiden waere
    also immer 'unbekannt'. Die Kontrolle macht ``main`` einmal ueber alle
    geladenen Korpora zusammen."""
    pfad = KORPUS / f"{name}.jsonl"
    faelle = []
    for zeilennummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
        if not zeile.strip():
            continue
        try:
            faelle.append(json.loads(zeile))
        except json.JSONDecodeError as fehler:
            raise SystemExit(f"{pfad}:{zeilennummer}: kein gueltiges JSON ({fehler})")
    if nur:
        gewuenscht = set(nur)
        faelle = [f for f in faelle if f["id"] in gewuenscht]
    return faelle


# ---------------------------------------------------------------------------
# Wegwerf-Datenbank: Arbeitsstand, Figuren und Journal fuer den Nutzertext
# ---------------------------------------------------------------------------

def _nachrichtenzeilen(nachrichten: list[dict]) -> list[dict]:
    """Ergaenzt die Korpusnachrichten (``absender``, ``text``) um die Felder,
    die ``kontext.sprecherzeile`` liest. ``sqlite3.Row`` und ``dict`` werden
    beide per Schluessel gelesen -- die Zeilen muessen also nicht durch die
    Datenbank, nur die Stammdaten muessen es."""
    return [
        {"absender": n["absender"], "text": n["text"], "ist_bot": 0, "typ": "text",
         "message_id": i + 1}
        for i, n in enumerate(nachrichten)
    ]


def _fuelle_arbeitsstand(conn, chat_id: int, stand: dict) -> None:
    for feld in ("begriffe", "fragen", "kernthema", "hauptkonflikt"):
        wert = (stand or {}).get(feld)
        if wert:
            repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    for figur in (stand or {}).get("figuren", []):
        repo.setze_figur(conn, chat_id, figur["name"], figur.get("beschreibung", ""))


def _fuelle_journal(conn, chat_id: int, eintraege: list[dict]) -> None:
    for eintrag in eintraege or []:
        repo.schreibe_journal(
            conn, chat_id, eintrag["art"], eintrag["text"], quelle="korpus"
        )


# ---------------------------------------------------------------------------
# Ein Fall = ein Modellaufruf
# ---------------------------------------------------------------------------

def _hoechste_aufruf_id(conn) -> int:
    zeile = conn.execute("SELECT max(id) AS m FROM aufruf").fetchone()
    return (zeile["m"] if zeile else None) or 0


def _aufruf_nach(conn, vorher_id: int) -> dict:
    """Token und Dauer des Aufrufs, den dieser Fall ausgeloest hat.

    ``llm.LLM._anfrage`` schreibt die ``aufruf``-Zeile im ``finally``, also
    auch bei Fehlschlag. Scheitert ein Fall dagegen **vor** dem Modellaufruf
    (etwa beim Bauen des Nutzertextes), gibt es gar keine neue Zeile -- dann
    duerfen hier nicht die Zahlen des vorherigen Falls stehen, sondern
    Nullen."""
    zeile = conn.execute(
        "SELECT tatsaechliche_token, antwort_token, dauer_ms FROM aufruf "
        "WHERE id > ? ORDER BY id DESC LIMIT 1",
        (vorher_id,),
    ).fetchone()
    if zeile is None:
        return {"eingabe_token": 0, "ausgabe_token": 0, "dauer_ms": 0}
    return {
        "eingabe_token": zeile["tatsaechliche_token"] or 0,
        "ausgabe_token": zeile["antwort_token"] or 0,
        "dauer_ms": zeile["dauer_ms"] or 0,
    }


def _laufe_erkenner(klm, conn, chat_id, fall, modell):
    _fuelle_arbeitsstand(conn, chat_id, fall.get("arbeitsstand"))
    nutzer = erkenner._baue_nutzertext(
        conn, chat_id, _nachrichtenzeilen(fall["nachrichten"])
    )
    ergebnis = klm.schema(
        chat_id, erkenner.prompt(), nutzer, erkenner.SCHEMA, "erkenner",
        modell=modell, temperature=erkenner.TEMPERATURE,
    )
    # Dieselbe Obergrenze wie erkenner.erkenne(): was das Modell darueber
    # hinaus liefert, kaeme im Betrieb nie an und darf hier weder als
    # Treffer noch als Falsch-Positiv zaehlen.
    geliefert = ergebnis.get("aenderungen", [])[: erkenner.MAX_AENDERUNGEN]
    bewertung = vergleiche_erkenner(fall["erwartet"], geliefert)
    bewertung["fragen_ohne_thema"] = fragen_ohne_thema(geliefert)
    return geliefert, bewertung, (
        len(bewertung["treffer"]),
        len(bewertung["ueberzaehlig"]),
        len(bewertung["fehlend"]),
    )


def _laufe_journal(klm, conn, chat_id, fall, modell):
    _fuelle_journal(conn, chat_id, fall.get("bisherige_eintraege"))
    nutzer = journal._baue_nutzertext(
        conn, chat_id, _nachrichtenzeilen(fall["abschnitt"])
    )
    ergebnis = klm.schema(
        chat_id, journal.prompt(), nutzer, journal.SCHEMA, "journal",
        modell=modell, temperature=journal.TEMPERATURE,
    )
    geliefert = ergebnis.get("eintraege", [])[: journal.MAX_EINTRAEGE]
    bewertung = vergleiche_journal(fall["erwartet"], geliefert)
    return geliefert, bewertung, (
        len(bewertung["treffer"]),
        len(bewertung["ueberzaehlig"]),
        len(bewertung["fehlend"]),
    )


def _laufe_verdichter(klm, conn, chat_id, fall, modell):
    transkript = fall["transkript"]
    ergebnis = klm.schema(
        chat_id, verdichter.prompt(), transkript, verdichter.SCHEMA, "verdichter",
        modell=modell,
    )
    bewertung = bewerte_verdichter(fall["erwartet"], ergebnis, transkript)
    return ergebnis, bewertung, zaehle_verdichter(bewertung)


#: Wartezeit nach HTTP 429, bevor derselbe Fall wiederholt wird.
PAUSE_429_S = float(os.environ.get("IT_PRUEFE_PAUSE_429_S", "45"))

LAEUFE = {
    "erkenner": _laufe_erkenner,
    "journal": _laufe_journal,
    "verdichter": _laufe_verdichter,
}


# ---------------------------------------------------------------------------
# Darstellung
# ---------------------------------------------------------------------------

def _kurz(wert, laenge: int = 70) -> str:
    """Einzeilige, gekuerzte Darstellung fuer eine Tabellenzelle. Pipes werden
    ersetzt, sonst zerfaellt die Markdown-Tabelle an einem Modelltext."""
    if isinstance(wert, list):
        text = "; ".join(
            f"{e.get('art') or e.get('kategorie', '')}={e.get('wert', e.get('text', ''))}"
            for e in wert
        ) or "—"
    elif isinstance(wert, dict):
        text = json.dumps(wert, ensure_ascii=False)
    else:
        text = str(wert)
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= laenge else text[: laenge - 1] + "…"


def _erwartet_spalte(prompt: str, fall: dict) -> str:
    if prompt == "verdichter":
        e = fall["erwartet"]
        return _kurz(
            f"{e['themen_min']}-{e['themen_max']} Themen, "
            f"Stichwoerter: {', '.join(e.get('stichwoerter', []))}"
        )
    return _kurz(fall["erwartet"])


def _geliefert_spalte(prompt: str, ergebnis, bewertung) -> str:
    if prompt == "verdichter":
        return _kurz(
            f"{bewertung['anzahl']} Themen, Zitate "
            f"{len(bewertung['zitate_ok'])}/{bewertung['anzahl']} geprueft"
        )
    return _kurz(ergebnis)


def baue_tabelle(prompt: str, zeilen: list[dict]) -> list[str]:
    """Eine Markdown-Tabelle je Fall."""
    aus = [
        "| id | erwartet | geliefert | Treffer | FP | FN | ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for z in zeilen:
        if z.get("fehler"):
            aus.append(
                f"| {z['id']} | {z['erwartet']} | **FEHLER: {_kurz(z['fehler'])}** "
                f"| – | – | – | {z['dauer_ms']} |"
            )
            continue
        aus.append(
            f"| {z['id']} | {z['erwartet']} | {z['geliefert']} "
            f"| {z['treffer']} | {z['fp']} | {z['fn']} | {z['dauer_ms']} |"
        )
    return aus


def baue_auffaellige(zeilen: list[dict]) -> list[str]:
    """Zu jedem Fall mit FP, FN oder Fehler die ``notiz`` aus dem Korpus samt
    voller Modellantwort.

    Wer den Bericht liest, muss entscheiden koennen, ob ein Fehlschlag
    schlimm ist. Die Tabelle sagt nur *dass* etwas danebenging; die Notiz sagt,
    warum der Fall ueberhaupt im Korpus steht ("Nemotron las das als
    kernthema_setzen") -- ohne sie muesste man jedes Mal die JSONL-Zeile
    nachschlagen."""
    auffaellig = [z for z in zeilen if z.get("fehler") or z["fp"] or z["fn"]]
    if not auffaellig:
        return ["", "Keine Auffaelligkeiten."]
    aus = ["", "<details><summary>Auffaellige Faelle im Einzelnen</summary>", ""]
    for z in auffaellig:
        aus.append(f"**{z['id']}** — FP {z['fp']}, FN {z['fn']}"
                   + (f", FEHLER: {z['fehler']}" if z.get("fehler") else ""))
        if z["notiz"]:
            aus.append(f"> {z['notiz']}")
        aus.append("")
        aus.append("```json")
        aus.append(json.dumps(z["roh"], ensure_ascii=False, indent=2))
        aus.append("```")
        aus.append("")
    aus.append("</details>")
    return aus


def kosten_chf(modell: str, eingabe_token: int, ausgabe_token: int) -> float | None:
    """Kostenschaetzung nach den hart eingetragenen Preisen. ``None`` fuer ein
    Modell, das nicht in der Liste steht -- lieber keine Zahl als eine
    erfundene."""
    preise = PREISE_CHF_JE_MIO_TOKEN.get(modell)
    if preise is None:
        return None
    eingabe, ausgabe = preise
    return (eingabe_token * eingabe + ausgabe_token * ausgabe) / 1_000_000


def baue_summe(prompt: str, modell: str, zeilen: list[dict]) -> list[str]:
    """Summenzeile je Prompt: Trefferquote, FP, FN, Median-Dauer, Kosten."""
    gelaufen = [z for z in zeilen if not z.get("fehler")]
    fehlgeschlagen = len(zeilen) - len(gelaufen)
    treffer = sum(z["treffer"] for z in gelaufen)
    fp = sum(z["fp"] for z in gelaufen)
    fn = sum(z["fn"] for z in gelaufen)
    erwartet_gesamt = treffer + fn
    quote = f"{treffer}/{erwartet_gesamt}" if erwartet_gesamt else "– (nur Negativfaelle)"
    median = int(statistics.median([z["dauer_ms"] for z in zeilen])) if zeilen else 0
    eingabe = sum(z["eingabe_token"] for z in zeilen)
    ausgabe = sum(z["ausgabe_token"] for z in zeilen)
    kosten = kosten_chf(modell, eingabe, ausgabe)
    kostentext = (
        f"{kosten:.4f} CHF (Preise Stand {PREISE_STAND})"
        if kosten is not None
        else f"nicht schaetzbar, Preis fuer {modell} nicht hinterlegt"
    )
    zeilentext = [
        "",
        f"**{prompt}** ({modell}), {len(zeilen)} Laeufe"
        + (f", davon {fehlgeschlagen} mit Fehler" if fehlgeschlagen else ""),
        "",
        f"- Trefferquote: {quote}",
        f"- Falsch-Positive: **{fp}**",
        f"- Falsch-Negative: {fn}",
        f"- Median-Dauer: {median} ms",
        f"- Token: {eingabe} ein, {ausgabe} aus — {kostentext}",
    ]
    pronomen = sum(z.get("pronomen", 0) for z in zeilen)
    if prompt == "journal":
        zeilentext.append(f"- Eintraege mit Pronomen-Anfang: {pronomen}")
    if prompt == "erkenner":
        # Kein Fehler, ein Hinweis: die Zeile steht im Arbeitsstand richtig,
        # nur die Gruppenseite kann daraus kein Thema fett setzen.
        zeilentext.append(
            "- Fragen ohne Thema vor dem Doppelpunkt: "
            f"{sum(z.get('fragen_ohne_thema', 0) for z in zeilen)}"
        )
    return zeilentext


# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------

def pruefe(prompt: str, klm, conn, faelle: list[dict], modell: str,
           wiederholungen: int, chat_id_basis: int = 0) -> list[dict]:
    """Laeuft die Faelle **sequenziell** durch. Kein Thread-Pool, keine
    Nebenlaeufigkeit: Infomaniak antwortet auf parallele Aufrufe mit 429/5xx
    (AGENTS.md 'Die Fallen'), und ein Korpuslauf hat es nicht eilig.

    ``chat_id_basis`` haelt die chat_ids ueber mehrere Prompts hinweg
    auseinander -- sonst saehe bei ``alle`` der dritte Journalfall den
    Arbeitsstand des dritten Erkennerfalls."""
    laufe = LAEUFE[prompt]
    zeilen = []
    for durchgang in range(1, wiederholungen + 1):
        for fall in faelle:
            # Eigene chat_id je Lauf: der Arbeitsstand des einen Falls darf
            # den naechsten nicht sehen.
            chat_id = chat_id_basis + len(zeilen) + 1
            repo.sichere_gruppe(conn, chat_id, "korpus", fall["id"])
            kennung = fall["id"] if wiederholungen == 1 else f"{fall['id']}#{durchgang}"

            vorher_id = _hoechste_aufruf_id(conn)
            start = time.monotonic()
            fehler = None
            ergebnis = bewertung = None
            zahlen = (0, 0, 0)
            # Gemessen 04.09.2026: nach rund 50 Aufrufen in Folge antwortet
            # Infomaniak mit HTTP 429 (Drosselung), und zwar fuer alle
            # weiteren -- bis eine Pause die Quote freigibt. Deshalb bei 429
            # warten und denselben Fall noch einmal, bis zu dreimal.
            for versuch in range(3):
                try:
                    ergebnis, bewertung, zahlen = laufe(klm, conn, chat_id, fall, modell)
                    fehler = None
                    break
                except Exception as ausnahme:  # noqa: BLE001 -- ein Fall soll den Lauf nie abbrechen
                    fehler = f"{type(ausnahme).__name__}: {ausnahme}"
                    if "429" in fehler and versuch < 2:
                        print(f"  429 -- warte {PAUSE_429_S} s", file=sys.stderr)
                        time.sleep(PAUSE_429_S)
                        continue
                    break
            dauer_ms = int((time.monotonic() - start) * 1000)
            gemessen = _aufruf_nach(conn, vorher_id)

            zeilen.append({
                "id": kennung,
                "erwartet": _erwartet_spalte(prompt, fall),
                "geliefert": "" if fehler else _geliefert_spalte(prompt, ergebnis, bewertung),
                "roh": ergebnis,
                "treffer": zahlen[0],
                "fp": zahlen[1],
                "fn": zahlen[2],
                "pronomen": len((bewertung or {}).get("pronomen", [])),
                "fragen_ohne_thema": len((bewertung or {}).get("fragen_ohne_thema", [])),
                "dauer_ms": gemessen["dauer_ms"] or dauer_ms,
                "eingabe_token": gemessen["eingabe_token"],
                "ausgabe_token": gemessen["ausgabe_token"],
                "fehler": fehler,
                "notiz": fall.get("notiz", ""),
            })
            print(f"  [{len(zeilen)}] {kennung}: "
                  + (f"FEHLER {fehler}" if fehler
                     else f"Treffer {zahlen[0]}, FP {zahlen[1]}, FN {zahlen[2]}"),
                  flush=True)
    return zeilen


def modell_fuer(prompt: str, e, ueberschreibung: str | None) -> str:
    """Dieselbe Modellwahl wie im Betrieb (SPEC § 4.3a): Erkenner und Journal
    laufen mit ``e.erkenner_modell``, der Verdichter mit dem
    Gespraechsmodell."""
    if ueberschreibung:
        return ueberschreibung
    return e.llm_modell if prompt == "verdichter" else e.erkenner_modell


def berichtspfad(angabe: str | None, prompts: list[str]) -> Path:
    """``--bericht`` ohne Pfad schreibt nach
    ``korpus/berichte/<datum>-<prompt>.md``."""
    if angabe:
        return Path(angabe)
    name = prompts[0] if len(prompts) == 1 else "alle"
    return BERICHTE / f"{date.today().isoformat()}-{name}.md"


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m scripts.pruefe_prompts",
        description="Regressionskorpus gegen das echte Sprachmodell laufen lassen. "
                    "Kostet Geld, laeuft nie automatisch.",
    )
    p.add_argument("prompt", choices=(*PROMPTS, "alle"))
    p.add_argument("--nur", help="Kommaliste von Fall-ids")
    p.add_argument("--modell", help="Modell statt der Vorgabe aus den Einstellungen")
    p.add_argument("--wiederholungen", type=int, default=1,
                   help="jeden Fall N-mal laufen lassen (Streuung sichtbar machen)")
    p.add_argument("--bericht", nargs="?", const="", default=None,
                   help="Markdown-Bericht schreiben; ohne Pfad nach "
                        "korpus/berichte/<datum>-<prompt>.md")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    prompts = list(PROMPTS) if args.prompt == "alle" else [args.prompt]
    nur = [t.strip() for t in args.nur.split(",") if t.strip()] if args.nur else None
    if args.wiederholungen < 1:
        raise SystemExit("--wiederholungen muss mindestens 1 sein")

    e = einstellungen.laden()
    with tempfile.TemporaryDirectory(prefix="interview_theater-korpus-") as verzeichnis:
        # IT_DB wird ausdruecklich verworfen: aufruf- und vorfall-Zeilen
        # dieses Laufs gehoeren nicht in die Betriebsdatenbank.
        db_pfad = str(Path(verzeichnis) / "korpus.db")
        e = replace(e, db_pfad=db_pfad)
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)

        korpora = {p: lade_korpus(p, nur) for p in prompts}
        if nur:
            gefunden = {f["id"] for faelle in korpora.values() for f in faelle}
            unbekannt = set(nur) - gefunden
            if unbekannt:
                raise SystemExit(
                    f"unbekannte id(s) in --nur: {', '.join(sorted(unbekannt))}")

        abschnitte: list[str] = []
        erkenner_fp = 0
        chat_id_basis = 0
        with httpx.Client(timeout=120.0) as klient:
            klm = llm.LLM(e, klient, conn)
            for prompt in prompts:
                faelle = korpora[prompt]
                if not faelle:
                    continue
                modell = modell_fuer(prompt, e, args.modell)
                print(f"\n=== {prompt} ({modell}), {len(faelle)} Faelle "
                      f"x {args.wiederholungen} ===", flush=True)
                zeilen = pruefe(prompt, klm, conn, faelle, modell,
                                args.wiederholungen, chat_id_basis)
                chat_id_basis += len(zeilen)
                if prompt == "erkenner":
                    erkenner_fp += sum(z["fp"] for z in zeilen)
                abschnitte += [f"## {prompt}", ""]
                abschnitte += baue_tabelle(prompt, zeilen)
                abschnitte += baue_summe(prompt, modell, zeilen)
                abschnitte += baue_auffaellige(zeilen)
                abschnitte += [""]

        kopf = [
            f"# Korpuslauf {date.today().isoformat()}",
            "",
            "Erzeugt von `scripts/pruefe_prompts.py` gegen das echte Modell.",
            "",
        ]
        text = "\n".join(kopf + abschnitte)
        print()
        print(text)

        if args.bericht is not None:
            pfad = berichtspfad(args.bericht, prompts)
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_text(text + "\n", encoding="utf-8")
            print(f"\nBericht: {pfad}")

        conn.close()

    if erkenner_fp:
        print(f"\nFEHLGESCHLAGEN: {erkenner_fp} Falsch-Positive beim Erkenner. "
              "Die Prompt-Aenderung gehoert zurueckgenommen (SPEC § 4.3a: 0 FP "
              "ist die Kennzahl, die den Erkenner qualifiziert hat).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

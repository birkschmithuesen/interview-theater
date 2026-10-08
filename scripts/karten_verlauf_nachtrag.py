"""Nachtrag: Karten-Verlauf aus dem Chat rekonstruieren (Birk 08.10.2026
~10:35/~10:48, NACHTRAG Robo 10:48).

``karte_verlauf`` (b3ddefa, ``szenenkarte.erzeuge``/``ueberspringe_fragen``)
speichert jede Fassung einer Szenenkarte erst seit heute. Die drei
Padua-Gruppen waren beim Deploy schon in Phase 6/7 -- ihr Karten-Verlauf ist
leer, obwohl sie Karten mehrfach ueberarbeitet haben. Dieses Skript holt
NUR den einen klar erkennbaren Fall nach: den formalen Dialog "Was soll an
Karte N anders werden?" -- EINE Notiz der Gruppe -- Neubau, erkennbar an der
immer gleichen Bestaetigungszeile vor dem Neubau (``szenenkarte._TEXT_AENDERE``,
IT "Ok. Ricostruisco la scheda N ...", EN "Got it. I'm rebuilding card N ...").
Die anschliessende Kartenanzeige im Chat (``szenenkarte.karte_text``, nur
IT/EN-Vorlage, deterministisch) liefert die Felder der neuen Fassung;
fehlt sie oder laesst sie sich nicht lesen, fallen wir auf den aktuellen,
gespeicherten Kartenstand zurueck (besser ein etwas zu spaeter Stand als
keiner).

**Bewusst NICHT nachgetragen** (siehe Bericht):

* G1 und Teile von G3 fuehren die Ueberarbeitung als freie
  CoThinker-Konversation ohne den formalen Notiz-Dialog -- mehrere
  Nachrichten hin und her, keine einzelne "das ist die Notiz"-Zeile, kein
  Neubau-Anker im Chat. Eine Heuristik, die hier IRGENDEINE Nachricht als
  "die" Entscheidung der Gruppe markiert, waere erfunden, nicht
  rekonstruiert -- und ginge direkt in den P7-Prompt als bindende
  Entscheidung ein. Lieber eine Luecke melden als eine falsche Vorgabe.
* Fragen-Klaerung ("Clear the questions"): die gespeicherte Notiz ist im
  Code eine Zusammenfassung ALLER Fragen+Antworten
  (``szenenkarte._klaerungsnotiz``), im Chat steht aber nur die letzte
  Antwort als eigene Nachricht -- zu unsicher, aus dem Chat wortgleich
  nachzubauen.
* "Skip questions" fand in den geprueften Gruppen nicht statt (keine
  passende Bestaetigungszeile im Chat) -- fuer den Fall ist die Erkennung
  vorbereitet (``_SKIP_ACK_RE``), aber ungetestet an echten Daten.

Kein Modellaufruf, kostet nichts.

Aufruf (aus dem Hauptcheckout):

    uv run --extra dev python -m scripts.karten_verlauf_nachtrag --db betrieb/padua.db                   # Trockenlauf, alle Gruppen
    uv run --extra dev python -m scripts.karten_verlauf_nachtrag --db betrieb/padua.db --chat <chat_id>   # Trockenlauf, eine Gruppe
    uv run --extra dev python -m scripts.karten_verlauf_nachtrag --db betrieb/padua.db --ja                # wirklich schreiben

Nur Szenen ohne jeden vorhandenen Karten-Verlauf werden angefasst --
wiederholbar, keine Dubletten.

Sicherung: ``--ja`` schreibt zuerst per ``VACUUM INTO`` eine Kopie der
gesamten Datenbank nach ``<db-Verzeichnis>/backup/padua-karten-verlauf-
<Zeit>.db`` (dieselbe Begruendung wie ``scripts/stage_kopf_it_nachtrag.py``:
``VACUUM INTO`` statt ``shutil.copy``, die Betriebsdatenbank laeuft im
WAL-Modus).

Journal: ein Eintrag Art ``entschieden``, Quelle ``regie`` je Szene
(Birks Vorgabe -- ein Operator-Nachtrag, kein Erkenner- oder Befehlslauf)."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo, szenenkarte

JOURNAL_TEXT = "Karten-Verlauf nachgetragen (Robo, Chat-Rekonstruktion)."

#: Die Kopfzeile einer Kartenanzeige -- ausschliesslich die deterministische
#: Vorlage aus ``szenenkarte.karte_text`` (IT ``_KARTE_KOPF``/EN
#: ``_KARTE_KOPF``), NIE ein frei formuliertes Modell-Echo (das kommt mit
#: anderem Trennzeichen vor, siehe Bericht -- bewusst nicht erkannt).
_KOPF_RE = re.compile(r"^\*\*(?:Scheda scena|Scene card) \d+(?: — .*)?\*\* · \*([^*]+)\*\s*$")

_TYP_LABEL = {
    "descrizione": "description", "testo parlato": "spoken",
    "istruzioni": "instructions", "momento": "moment",
    "description": "description", "spoken text": "spoken",
    "instructions": "instructions", "moment": "moment",
}

#: Feldlabel -> Kartenfeld, IT und EN (woertlich aus den Vorlagen in
#: ``szenenkarte.py``/``sprachen/it/texte.toml``/``sprachen/en/texte.toml`,
#: Stand der historischen Nachrichten -- bewusst fest verdrahtet: wir lesen
#: Text, der schon geschrieben steht, kein heutiges Profil).
_FELD_LABEL = {
    "Dove:": "ort", "Where:": "ort",
    "Chi:": "wer", "Who:": "wer",
    "Cosa succede:": "punkte", "What happens:": "punkte",
    "Citazioni dall'intervista:": "zitate", "Interview quotes:": "zitate",
    "Domande aperte:": "fragen", "Open questions:": "fragen",
}
_LABEL_ZEILE_RE = re.compile(r"^\*\*([^*]+)\*\*\s*(.*)$")
_ZITAT_ZEILE_RE = re.compile(r"^-\s*\*[“\"](.+?)[”\"]\*(?:\s*\((.*?)\))?\s*$")

#: Die Bestaetigungszeile unmittelbar VOR jedem Neubau mit Notiz
#: (``szenenkarte._TEXT_AENDERE`` bzw. die englische Fassung in
#: ``sprachen/en/texte.toml``) -- der verlaesslichste Anker: er steht
#: IMMER mit der Kartennummer da, unabhaengig davon, welche Frage ihn
#: ausgeloest hat (Kommandozeile, Knopf, CoThinker).
_AENDERE_ACK_RE = re.compile(
    r"^(?:Ok\. Ricostruisco la scheda (\d+) con la vostra modifica"
    r"|Got it\. I'm rebuilding card (\d+) with your change)"
)
#: Vorbereitet, an echten Daten noch ungetestet (siehe Modul-Docstring).
_SKIP_ACK_RE = re.compile(
    r"^(?:Domande della scheda (\d+) saltate|Questions on card (\d+) skipped)"
)

_TEXT_TYPEN = ("text", "sprache")


def _parse_karte_text(text: str) -> dict | None:
    """Liest eine im Chat geschriebene Kartenanzeige (``szenenkarte.
    karte_text``, plus ggf. eine Statuszeile danach) wieder in ein Karten-
    Dict zurueck. ``None``, wenn die erste Zeile nicht die bekannte Vorlage
    ist -- lieber nichts erkennen als etwas Falsches."""
    zeilen = (text or "").split("\n")
    if not zeilen:
        return None
    kopf = _KOPF_RE.match(zeilen[0])
    if kopf is None:
        return None
    karte: dict = {"typ": _TYP_LABEL.get(kopf.group(1).strip())}
    i = 1
    if i < len(zeilen) and zeilen[i].strip() and not zeilen[i].strip().startswith("**"):
        karte["worum"] = zeilen[i].strip()
        i += 1
    aktuelles_feld = None
    punkte: list[str] = []
    zitate: list[dict] = []
    fragen: list[str] = []
    while i < len(zeilen):
        stripped = zeilen[i].strip()
        i += 1
        if not stripped:
            continue
        label = _LABEL_ZEILE_RE.match(stripped)
        if label is not None:
            feld = _FELD_LABEL.get(label.group(1))
            rest = label.group(2).strip()
            if feld in ("ort", "wer") and rest:
                karte[feld] = rest
            aktuelles_feld = feld if feld in ("punkte", "zitate", "fragen") else None
            continue
        if not stripped.startswith("- "):
            break  # Statuszeile am Ende -- hier ist die Karte zu Ende.
        eintrag = stripped[2:].strip()
        if aktuelles_feld == "punkte":
            punkte.append(eintrag)
        elif aktuelles_feld == "zitate":
            m = _ZITAT_ZEILE_RE.match(stripped)
            if m is not None:
                zitate.append({"zitat": m.group(1), "interview": m.group(2) or ""})
        elif aktuelles_feld == "fragen":
            fragen.append(eintrag)
    karte["punkte"] = punkte
    karte["zitate"] = zitate
    karte["fragen"] = fragen
    return karte


def _notiz_vor(rows: list, index: int) -> str | None:
    """Die naechste eingehende Text-/Sprachnachricht VOR ``rows[index]`` --
    die Notiz, die den Neubau an dieser Stelle ausgeloest hat."""
    for j in range(index - 1, -1, -1):
        r = rows[j]
        if r["richtung"] == repo.RICHTUNG_AUS or r["typ"] not in _TEXT_TYPEN:
            continue
        if (r["text"] or "").strip():
            return r["text"].strip()
    return None


def _karte_nach(rows: list, index: int, nummer: int, grenze: int) -> dict | None:
    """Die naechste erkennbare Kartenanzeige fuer ``nummer`` zwischen
    ``rows[index]`` (exklusiv) und ``grenze`` (exklusiv, der naechste
    Neubau-Anker) -- die Fassung, die dieser Neubau erzeugt hat."""
    for j in range(index + 1, min(grenze, len(rows))):
        r = rows[j]
        if r["richtung"] != repo.RICHTUNG_AUS:
            continue
        geparst = _parse_karte_text(r["text"] or "")
        if geparst is not None and (r["text"] or "").startswith(
            ("**Scheda scena " + str(nummer), "**Scene card " + str(nummer))
        ):
            return geparst
    return None


def plane(conn, chat_id: int) -> list[dict]:
    """Was ein Lauf taete -- reine Leseabfrage, kein Schreibzugriff.
    Grundlage von Trockenlauf UND Ernstfall. Nur Szenen ohne jeden
    vorhandenen Karten-Verlauf (Idempotenz: ein zweiter Lauf, oder eine
    Szene, deren Verlauf der laufende Code schon selbst fuehrt, bleibt
    unangetastet)."""
    rows = conn.execute(
        "SELECT id, richtung, typ, text FROM web_post WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,),
    ).fetchall()
    anker = []  # (zeilen_index, nummer)
    for idx, r in enumerate(rows):
        if r["richtung"] != repo.RICHTUNG_AUS:
            continue
        m = _AENDERE_ACK_RE.match(r["text"] or "")
        if m is not None:
            anker.append((idx, int(m.group(1) or m.group(2))))

    plan = []
    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, chat_id)
              if s["nummer"] is not None and not s["entfernt_am"]}
    for pos, (idx, nummer) in enumerate(anker):
        szene = szenen.get(nummer)
        if szene is None:
            continue
        if repo.karte_verlauf(conn, chat_id, szene["id"]):
            continue  # schon ein Verlauf da -- nichts anfassen (Idempotenz).
        naechste_grenze = anker[pos + 1][0] if pos + 1 < len(anker) else len(rows)
        notiz = _notiz_vor(rows, idx)
        karte = _karte_nach(rows, idx, nummer, naechste_grenze)
        if karte is None:
            aktuell = szenenkarte.karte_von(szene)
            if aktuell is None:
                continue
            karte = aktuell
        plan.append({
            "chat_id": chat_id, "szene_id": szene["id"], "nummer": nummer,
            "notiz": notiz, "ausloeser": szenenkarte.AUSLOESER_AENDERUNG, "karte": karte,
        })
    return plan


def berichtstext(chat_id: int, plan: list[dict], trocken: bool) -> str:
    if not plan:
        return f"chat_id {chat_id}: nichts rekonstruierbar (kein formaler Notiz-Dialog)."
    kopf = "Trockenlauf" if trocken else "Nachgetragen"
    zeilen = [f"{kopf}: chat_id {chat_id}, {len(plan)} Aenderung(en)."]
    for eintrag in plan:
        notiz = (eintrag["notiz"] or "(keine Notiz gefunden)")[:80]
        zeilen.append(f"  Szene {eintrag['nummer']}: {notiz!r}")
    if trocken:
        zeilen.append("Nichts geschrieben. Mit --ja ausfuehren.")
    return "\n".join(zeilen)


def fuehre_aus(conn, chat_id: int, eintrag: dict) -> None:
    repo.merke_karte_verlauf(
        conn, chat_id, eintrag["szene_id"], json.dumps(eintrag["karte"], ensure_ascii=False),
        eintrag["ausloeser"], eintrag["notiz"],
    )
    repo.schreibe_journal(conn, chat_id, "entschieden", JOURNAL_TEXT, quelle="regie")


def _sicherungspfad(db_pfad: str, jetzt: datetime) -> Path:
    ordner = Path(db_pfad).resolve().parent / "backup"
    return ordner / f"padua-karten-verlauf-{jetzt:%Y%m%d-%H%M%S}.db"


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.karten_verlauf_nachtrag",
        description="Traegt den Karten-Verlauf aus dem Chat nach (NACHTRAG Robo 08.10.2026).",
    )
    zerleger.add_argument("--db", required=True, dest="db_pfad")
    zerleger.add_argument("--chat", type=int, dest="chat_id", default=None,
                          help="nur diese Gruppe -- ohne diese Option alle")
    zerleger.add_argument("--ja", action="store_true", help="wirklich schreiben")
    a = zerleger.parse_args(argv)

    conn = db.verbinde(a.db_pfad)
    try:
        db.initialisiere(conn)
        chat_ids = [a.chat_id] if a.chat_id is not None else [
            g["chat_id"] for g in repo.alle_gruppen(conn)
        ]
        plaene = {chat_id: plane(conn, chat_id) for chat_id in chat_ids}
        for chat_id in chat_ids:
            print(berichtstext(chat_id, plaene[chat_id], trocken=not a.ja))
        gesamt = sum(len(p) for p in plaene.values())
        if not a.ja or gesamt == 0:
            return 0

        jetzt = datetime.now(timezone.utc)
        sicherung = _sicherungspfad(a.db_pfad, jetzt)
        sicherung.parent.mkdir(parents=True, exist_ok=True)
        conn.execute("VACUUM INTO ?", (str(sicherung),))
        print(f"Backup: {sicherung}")

        for chat_id in chat_ids:
            for eintrag in plaene[chat_id]:
                fuehre_aus(conn, chat_id, eintrag)
            if plaene[chat_id]:
                print(f"  geschrieben: chat_id {chat_id}, {len(plaene[chat_id])} Aenderung(en).")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

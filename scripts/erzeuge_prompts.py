"""Erzeugt je Prompt-Pfad einen echten Prompt gegen eine Kopie der Test-DB.

Aufruf::

    IT_DB=/tmp/prompt-audit.db python -m scripts.erzeuge_prompts <zielverzeichnis>

Schreibt je Pfad eine Datei ``<pfad>.txt`` mit ``=== SYSTEM ===`` und
``=== NUTZER ===``, plus ``uebersicht.tsv`` mit den Laengen. Transkript-Inhalte
werden ersetzt (``[Transkript N, 1234 Zeichen]``) -- die Test-DB enthaelt
Kopien echter Gruppen, und die Dumps werden committet.

Rein lesend gegen die DB, mit einer Ausnahme: ``kontext.baue`` merkt sich das
Phasenangebot und kann einen Vorfall schreiben. Deshalb ausdruecklich nur
gegen eine KOPIE der Test-DB laufen lassen.
"""

import os
import re
import sys
from pathlib import Path

from interview_theater import (
    ablauf, db, erkenner, journal, kernzitate, kontext, phasen, repo,
    schaerfung, sprachprofil, szene, szenenfolge, verdichter,
)


class _E:
    """Minimale Umgebung, wie sie die Bausteine erwarten."""
    bot_name = "gruppe4"
    erkenner_modell = None
    weboberflaeche_url = None


#: Die Transkripte, die aus der Test-DB gelesen wurden. Die Test-DB enthaelt
#: Kopien echter Gruppen, und die Dumps werden committet -- also darf kein
#: Wortlaut darin stehen. Wird in ``main()`` gefuellt, bevor irgendein Dump
#: geschrieben wird.
_TRANSKRIPTE: list[str] = []

#: Die woertlichen Belegzitate aus den Verdichtungen. Sie sind kein
#: Transkriptblock, aber genauso echte Rede einer interviewten Person --
#: und sie stehen im Kernzitate- und Schaerfungs-Prompt im Wortlaut.
_ZITATE: list[str] = []

#: Die Verdichtungs-Zusammenfassungen. Kein Wortlaut, sondern vom Modell
#: geschriebene indirekte Rede -- sie erzaehlen aber die Erlebnisse einer
#: realen Person nach ("ihrer Freundin wurde in der Bahn das Kopftuch
#: abgezogen") und gehoeren damit nicht in ein oeffentliches Repository.
_ZUSAMMENFASSUNGEN: list[str] = []


def _entschaerfe(text: str) -> str:
    """Ersetzt jeden Transkript-Wortlaut durch eine Laengenangabe.

    Zwei Wege, weil Transkripte auf zwei Arten in einen Prompt kommen:
    als markierter Block (``--- Name (Volltranskript) ---``) im
    Gespraechs-Prompt und als **nackter Text** im Verdichter-, Sprachprofil-
    und Erkenner-Nutzertext. Der zweite Weg war beim ersten Lauf uebersehen
    worden -- der Verdichter-Dump trug das Interview im Wortlaut.
    """
    def block(m):
        return (f"--- {m.group(1)} (Volltranskript) ---\n"
                f"[Transkript, {len(m.group(2))} Zeichen]")
    text = re.sub(
        r"--- (.+?) \(Volltranskript\) ---\n(.*?)(?=\n\n--- |\Z)",
        block, text, flags=re.S,
    )
    # Der nackte Wortlaut: jedes bekannte Transkript, auch in Teilen. Von den
    # laengsten zuerst, damit ein Teiltranskript nicht ein Volltranskript
    # zerschneidet.
    for n, transkript in enumerate(
        sorted(_TRANSKRIPTE, key=len, reverse=True), start=1
    ):
        if transkript and transkript in text:
            text = text.replace(
                transkript, f"[Transkript {n}, {len(transkript)} Zeichen]"
            )
    # Die einzelnen Belegzitate: dieselbe Ueberlegung, nur kleiner. Kurze
    # Zitate (unter 25 Zeichen) bleiben stehen -- sie sind zu allgemein, um
    # jemanden zu identifizieren, und ein zu gieriges Ersetzen wuerde den
    # Dump unlesbar machen.
    for n, zitat in enumerate(sorted(_ZITATE, key=len, reverse=True), start=1):
        if len(zitat) >= 25 and zitat in text:
            text = text.replace(zitat, f"[Zitat {n}, {len(zitat)} Zeichen]")
    for n, fassung in enumerate(
        sorted(_ZUSAMMENFASSUNGEN, key=len, reverse=True), start=1
    ):
        if fassung and fassung in text:
            text = text.replace(
                fassung, f"[Zusammenfassung {n}, {len(fassung)} Zeichen]"
            )
    return text


def _schreibe(ziel: Path, name: str, system: str, nutzer: str, notiz: str = "") -> tuple:
    system = _entschaerfe(system or "")
    nutzer = _entschaerfe(nutzer or "")
    kopf = f"# {name}\n# {notiz}\n" if notiz else f"# {name}\n"
    (ziel / f"{name}.txt").write_text(
        f"{kopf}=== SYSTEM ({len(system)} Zeichen, ~{kontext.schaetze(system)} Token) ===\n"
        f"{system}\n\n"
        f"=== NUTZER ({len(nutzer)} Zeichen, ~{kontext.schaetze(nutzer)} Token) ===\n"
        f"{nutzer}\n",
        encoding="utf-8",
    )
    return name, len(system), len(nutzer), kontext.schaetze(system) + kontext.schaetze(nutzer)


def main() -> None:
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/prompt-audit/2026-09-06")
    ziel.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(os.environ["IT_DB"])
    e = _E()

    chat_id = conn.execute(
        "SELECT chat_id FROM nachricht GROUP BY chat_id ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()[0]
    # **Zuerst** alle Transkripte einsammeln: sie sind die Liste, gegen die
    # ``_entschaerfe`` ersetzt, und kein Dump darf geschrieben werden, bevor
    # sie vollstaendig ist.
    transkript = ""
    for a in repo.transkripte(conn, chat_id):
        text = repo.zusammengefuegtes_transkript(conn, a["id"]) or ""
        if text.strip():
            _TRANSKRIPTE.append(text)
            if not transkript and a["klasse"] == "lang":
                transkript = text
    for v in repo.verdichtungen(conn, chat_id):
        if v["zusammenfassung"]:
            _ZUSAMMENFASSUNGEN.append(v["zusammenfassung"])
        for thema in repo.themen_zu(conn, v["id"]):
            if thema["beleg_zitat"]:
                _ZITATE.append(thema["beleg_zitat"])

    zeilen = []

    # --- 1. Gespraechszug -------------------------------------------------
    nachrichten = repo.letzte_nachrichten(conn, chat_id, anzahl=5)
    ausloeser = [nachrichten[-1]] if nachrichten else []
    phase = phasen.aktuelle(conn, chat_id)
    zeilen.append(_schreibe(
        ziel, "01-gespraech",
        kontext.system(e.bot_name, phase),
        kontext.baue(conn, chat_id, ausloeser, e),
        f"kontext.baue + anweisungen.system(bot, phase={phase})",
    ))

    # --- 2. Erstkontakt ---------------------------------------------------
    zeilen.append(_schreibe(
        ziel, "02-gespraech-erstkontakt",
        kontext.system(e.bot_name, 1),
        kontext.baue(conn, chat_id, ausloeser, e, erstkontakt=True),
        "erster Zug einer Gruppe",
    ))

    # --- 3. Auftragszug ---------------------------------------------------
    for kurz, anweisung in (
        ("schlag-vor", "Schlag du vor."),
        ("namen", "Schlag drei andere Namen fuer diese Figur vor."),
        ("duktus", "Schlag drei andere Sprachduktus-Beschreibungen fuer diese Figur vor."),
        ("richtungen", "Schlag drei grobe Richtungen fuer das Kernthema vor."),
    ):
        koerper = kontext.baue(conn, chat_id, [], e)
        koerper = f"{koerper}\n\n{ablauf._AUFTRAG_KOPF}\n{anweisung}"
        zeilen.append(_schreibe(
            ziel, f"03-auftragszug-{kurz}", kontext.system(e.bot_name, phase), koerper,
            f"ablauf.auftragszug, Anweisung: {anweisung!r}",
        ))

    # --- 4. Erkenner ------------------------------------------------------
    neue = repo.letzte_nachrichten(conn, chat_id, anzahl=8)
    vorlauf = repo.letzte_bot_nachricht_vor(conn, chat_id, neue[0]["message_id"]) if neue else None
    zeilen.append(_schreibe(
        ziel, "04-erkenner", erkenner.prompt(),
        erkenner._baue_nutzertext(conn, chat_id, neue, vorlauf),
        "erkenner.md + Arbeitsstand + Fenster",
    ))
    if transkript:
        zeilen.append(_schreibe(
            ziel, "05-erkenner-aufnahme", erkenner.prompt(),
            erkenner.baue_aufnahme_nutzertext(transkript),
            "erkenner auf ein Aufnahme-Transkript",
        ))

    # --- 5. Verdichter ----------------------------------------------------
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = stand["fragen"] if stand else None
    zeilen.append(_schreibe(
        ziel, "06-verdichter", verdichter.prompt(),
        verdichter.baue_nutzertext(transkript or "(kein Transkript in der Test-DB)", fragen),
        "verdichter.md + Fragen + Transkript",
    ))

    # --- 6. Journal-Extraktor --------------------------------------------
    verdraengt = repo.letzte_nachrichten(conn, chat_id, anzahl=6)
    zeilen.append(_schreibe(
        ziel, "07-journal", journal.prompt(),
        journal._baue_nutzertext(conn, chat_id, verdraengt),
        "journal.md + bisheriges Journal + verdraengter Abschnitt",
    ))

    # --- 7. Sprachprofil --------------------------------------------------
    zeilen.append(_schreibe(
        ziel, "08-sprachprofil", sprachprofil.prompt(),
        sprachprofil.baue_nutzertext(transkript or "(kein Transkript)"),
        "sprachprofil.md + Transkript",
    ))

    # --- 8. Kernzitate ----------------------------------------------------
    eintraege = kernzitate._eintraege(conn, chat_id)
    zeilen.append(_schreibe(
        ziel, "09-kernzitate", kernzitate.prompt(),
        kernzitate.baue_nutzertext(
            (stand["kernthema"] if stand else "") or "",
            (stand["kernfrage"] if stand else "") or "", eintraege),
        "kernzitate.md + Material",
    ))

    # --- 9. Schaerfung ----------------------------------------------------
    s_eintraege = schaerfung._eintraege(conn, chat_id)
    zeilen.append(_schreibe(
        ziel, "10-schaerfung", schaerfung.prompt(),
        schaerfung.baue_nutzertext(conn, chat_id, s_eintraege),
        "schaerfung.md + Erfundenes + Material",
    ))

    # --- 10. Szenenfolge / Geschichte -------------------------------------
    zeilen.append(_schreibe(
        ziel, "11-szenenfolge", szenenfolge.systemanweisung(4),
        szenenfolge.baue_nutzertext(conn, chat_id, 4),
        "szenenfolge.systemanweisung(4) + baue_nutzertext",
    ))
    zeilen.append(_schreibe(
        ziel, "12-geschichte", szenenfolge.systemanweisung_geschichte(4),
        szenenfolge.baue_nutzertext_geschichte(conn, chat_id),
        "szenenfolge.systemanweisung_geschichte + baue_nutzertext_geschichte",
    ))

    # --- 11. Szene, je Form -----------------------------------------------
    szenen = repo.hole_szenen(conn, chat_id)
    ziel_szene = szenen[0] if szenen else None
    for form in ("dialog", "monolog", "chor", "lied", "rap"):
        zeilen.append(_schreibe(
            ziel, f"13-szene-{form}", szene.systemanweisung(form),
            szene.baue_nutzertext(conn, chat_id, "Schreib Szene 1.", ziel_szene),
            f"szene.systemanweisung({form!r}) + baue_nutzertext",
        ))

    # --- 12. Feldvorschlag ------------------------------------------------
    if ziel_szene is not None:
        fehlend, _ = szene.fehlendes(conn, ziel_szene)
        anweisung = (
            "Schlag fuer diese Szene die fehlenden Felder vor: "
            + ", ".join(fehlend or ["ort", "zeit", "figuren"])
        )
        koerper = kontext.baue(conn, chat_id, [], e)
        koerper = f"{koerper}\n\n{ablauf._AUFTRAG_KOPF}\n{anweisung}"
        zeilen.append(_schreibe(
            ziel, "14-feldvorschlag", kontext.system(e.bot_name, phase), koerper,
            "Auftragszug 'Feld vorschlagen' (knoepfe -> ablauf.starte_auftrag)",
        ))

    # --- Uebersicht -------------------------------------------------------
    tsv = ["pfad\tsystem_zeichen\tnutzer_zeichen\ttoken_gesamt"]
    for name, s, n, t in zeilen:
        tsv.append(f"{name}\t{s}\t{n}\t{t}")
    (ziel / "uebersicht.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    print("\n".join(tsv))


if __name__ == "__main__":
    main()

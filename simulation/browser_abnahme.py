"""Der Abnahmebericht Phase 1-2 (04.10.2026): Urteil, Stationen mit
Erklaerspalte (Pflichtpunkt 1) und dem p1-start-Beobachtungsblock
(Pflichtpunkt 2), Begriffsboard-Verlauf, Richterbefunde, Modellbeleg samt
Kostensumme, Entwickler-Meta-Zaehler, B-Befunde und Leitbilder.

Reine Textzusammenstellung plus ein read-only SQL-Zugriff
(``modellbeleg``) -- kein Modellaufruf, kein Schreibzugriff. Konsumiert
das ``ergebnis.json`` der Stationsmotor-Engine aus
``simulation/browser_lauf.py`` (``fuehre_stationen``)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

MAX_B_BEFUNDE = 5

_STATIONEN_HEADER = (
    "| Station | Persona | Schritte | Nachfragen | fertig | Note | "
    "offene Fragen | Erklaerung | schwaechstes Zitat | Vorschlag |"
)
_STATIONEN_TRENNER = "|---|---|---|---|---|---|---|---|---|---|"


def _ja_nein(wert) -> str:
    return "ja" if wert else "nein"


def urteil(laeufe: list[dict]) -> tuple[bool, str]:
    """ja genau dann, wenn in JEDEM Lauf jede Station ``fertig`` ist,
    ``board_bestanden`` haelt und ``entwickler_meta`` leer ist. Der Grund
    nennt bei ``nein`` den ERSTEN Fehlschlag."""
    for lauf in laeufe:
        geraet = lauf.get("geraet", "?")
        for station in lauf.get("stationen_ergebnisse", []):
            if not station.get("fertig"):
                return False, f"{geraet}: Station {station['schluessel']} nicht erreicht"
        if not lauf.get("board_bestanden"):
            return False, f"{geraet}: Begriffsboard nicht bestanden"
        meta = lauf.get("entwickler_meta") or []
        if meta:
            return False, f"{geraet}: Entwickler-Meta im Chat ({meta[0]!r})"
    return True, "alle 11 Stationen auf beiden Geraeten erreicht, Board ohne Reload gewachsen"


def modellbeleg(db_pfad: str) -> list[tuple[str, str, int, float]]:
    """``(art, modell, anzahl, chf)`` je Kombination, read-only. Fehlt die
    Tabelle oder die Datei, ist das Ergebnis leer statt ein Fehler --
    ein Lauf ohne ``aufruf``-Zeilen (z. B. ``p1-start``) ist kein Fehler."""
    try:
        conn = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return []
    try:
        zeilen = conn.execute(
            "SELECT art, modell, COUNT(*), COALESCE(SUM(kosten_chf), 0) "
            "FROM aufruf GROUP BY art, modell ORDER BY art, modell"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [(art, modell, anzahl, round(chf, 4)) for art, modell, anzahl, chf in zeilen]


def kosten_summe(db_pfade: list[str]) -> float:
    return round(sum(zeile[3] for pfad in db_pfade for zeile in modellbeleg(pfad)), 4)


def _belegtabelle(zeilen: list[tuple]) -> str:
    kopf = "| Art | Modell | Anzahl | CHF |\n|---|---|---|---|"
    rumpf = "\n".join(
        f"| {art} | {modell} | {anzahl} | {chf:.4f} |" for art, modell, anzahl, chf in zeilen
    )
    return f"{kopf}\n{rumpf}" if rumpf else f"{kopf}\n| — | — | — | — |"


def _wert_oder(wert, leer="—") -> str:
    if wert in (None, ""):
        return leer
    return str(wert)


def _station_zeile(station: dict, persona: str) -> str:
    offene = "; ".join(station.get("offene_fragen") or []) or "—"
    note = _wert_oder(station.get("note"))
    erklaerung = _wert_oder(station.get("note_erklaerung"))
    zitat = _wert_oder(station.get("schwaechstes_zitat"))
    if station.get("zitat_unbelegt"):
        zitat = f"{zitat} (unbelegt)"
    vorschlag = _wert_oder(station.get("vorschlag"))
    return (
        f"| {station['schluessel']} | {persona} | {station.get('schritte', 0)} | "
        f"{station.get('nachfragen_beantwortet', 0)} | {_ja_nein(station.get('fertig'))} | "
        f"{note} | {offene} | {erklaerung} | {zitat} | {vorschlag} |"
    )


def _p1_start_block(station: dict, geraet: str) -> str:
    def _flag(schluessel: str) -> str:
        if schluessel not in station:
            return "unbekannt"
        return _ja_nein(station[schluessel])

    return (
        f"**p1-start ({geraet}) — Seite neu oeffnen, nichts tippen: Was passiert?**\n\n"
        f"- Bot-Nachricht da: {_flag('bot_nachricht')}\n"
        f"- Kalibrierung sichtbar: {_flag('kalibrierung_sichtbar')}\n"
        f"- Mithoeren laeuft: {_flag('zuhoeren_laeuft')}\n"
        f"- Leertext sichtbar: {_flag('leertext_sichtbar')}"
    )


def _stationen_abschnitt(laeufe: list[dict]) -> str:
    teile = []
    for lauf in laeufe:
        stationen = lauf.get("stationen_ergebnisse", [])
        if stationen and stationen[0].get("schluessel") == "p1-start":
            teile.append(_p1_start_block(stationen[0], lauf.get("geraet", "?")))
        zeilen = [_station_zeile(s, lauf.get("persona", "?")) for s in stationen]
        tabelle = "\n".join([_STATIONEN_HEADER, _STATIONEN_TRENNER, *zeilen])
        teile.append(f"### {lauf.get('geraet', '?')}\n\n{tabelle}")
    return "\n\n".join(teile)


def _begriffsboard_abschnitt(laeufe: list[dict]) -> str:
    zeilen = []
    for lauf in laeufe:
        verlauf = " → ".join(str(x) for x in lauf.get("board_verlauf", []))
        zeilen.append(
            f"- {lauf.get('geraet', '?')}: {verlauf} -- "
            f"neu geladen: {_ja_nein(lauf.get('beobachter_neu_geladen'))}, "
            f"bestanden: {_ja_nein(lauf.get('board_bestanden'))}"
        )
    return "\n".join(zeilen)


def _richter_abschnitt(laeufe: list[dict]) -> str:
    zeilen = []
    for lauf in laeufe:
        for station in lauf.get("stationen_ergebnisse", []):
            for befund in station.get("befunde") or []:
                zeilen.append(
                    f"- **{befund.get('schwere', '?')}** "
                    f"{lauf.get('geraet', '?')}/{station['schluessel']}: {befund.get('text', '')}"
                )
    return "\n".join(zeilen) if zeilen else "Keine Befunde."


def _modellbeleg_abschnitt(belege: dict[str, list[tuple]], modellwahl_satz: str) -> str:
    teile = []
    for geraet, zeilen in belege.items():
        teile.append(f"### {geraet}\n\n{_belegtabelle(zeilen)}")
    teile.append(modellwahl_satz or "—")
    summe = round(sum(zeile[3] for zeilen in belege.values() for zeile in zeilen), 4)
    teile.append(f"Summe: {summe:.4f} CHF")
    return "\n\n".join(teile)


def _meta_abschnitt(laeufe: list[dict]) -> str:
    treffer = [m for lauf in laeufe for m in (lauf.get("entwickler_meta") or [])]
    if not treffer:
        return "0 (Ziel 0)"
    return "\n".join(f"- {t}" for t in treffer)


def _b_befunde_abschnitt(b_befunde: list[dict]) -> str:
    if not b_befunde:
        return "Keine B-Befunde."
    zeilen = []
    for i, befund in enumerate(b_befunde, start=1):
        zeilen.append(
            f"{i}. **{befund['titel']}.** {befund['text']} "
            f"Vorschlag: {befund['vorschlag']} Frage: Soll ich?"
        )
    return "\n\n".join(zeilen)


def _leitbilder_abschnitt(leitbilder: list[dict]) -> str:
    if not leitbilder:
        return "Keine Leitbilder (noch kein Schlusslauf)."
    return "\n".join(
        f"- docs/guide/bilder/{e['datei']} — {e['unterschrift_en']}" for e in leitbilder
    )


def _harness_notizen_abschnitt(harness_notizen: list[str]) -> str:
    if not harness_notizen:
        return "Keine Notizen."
    return "\n".join(f"- {n}" for n in harness_notizen)


_TESTANLEITUNG = """\
Zwei Geraete, ein Gruppenlink: Geraet A oeffnet den Gruppenlink zuerst.
Geraet B oeffnet denselben Link und tippt auf "CoThinker" -- danach wird
auf Geraet B NICHT neu geladen, das Begriffsboard soll von selbst
wachsen. Geraet A macht den Mikrofon-Check und drueckt dann
"Start listening"; das Telefon liegt dafuer mit dem Bildschirm nach oben
in der Mitte des Tischs, rund drei Minuten lang, waehrend die Gruppe ueber
Begriffe spricht. In dieser Zeit auf Geraet B zusehen, wie das Board
waechst -- ohne Klick, ohne Reload. Danach auf Geraet A "Discussion done"
druecken, den Vorschlag lesen, "Take these" druecken, die
Speicherbestaetigung abwarten, dann "Undo" druecken und anschliessend
"Take these" noch einmal druecken. Weiter zu Phase 2: eigene Fragen als
Gruppe eintippen, beim Abgleich mit den KI-Fragen auf einen Wartehinweis
achten (laeuft da sichtbar etwas im Hintergrund?), die Fragen einzeln
durchgehen, dabei Zeilen auf- und wieder zuklappen, und am Ende pruefen,
dass das Angebot fuer Phase 3 (Interviews) erscheint.\
"""


def baue_abnahme(laeufe: list[dict], *, belege: dict[str, list[tuple]],
                  b_befunde: list[dict], leitbilder: list[dict],
                  harness_notizen: list[str], modellwahl_satz: str) -> str:
    if len(b_befunde) > MAX_B_BEFUNDE:
        raise ValueError(f"hoechstens {MAX_B_BEFUNDE} B-Befunde, nicht {len(b_befunde)}")
    ok, grund = urteil(laeufe)
    teile = [
        f"Phase 1-2 abnahmebereit: {'ja' if ok else 'nein'} — {grund}",
        "## Testanleitung fuer Birk",
        _TESTANLEITUNG,
        "## Stationen",
        _stationen_abschnitt(laeufe),
        "## Begriffsboard (zweites Geraet)",
        _begriffsboard_abschnitt(laeufe),
        "## Richter",
        _richter_abschnitt(laeufe),
        "## Modellbeleg",
        _modellbeleg_abschnitt(belege, modellwahl_satz),
        "## Entwickler-Meta im Chat",
        _meta_abschnitt(laeufe),
        "## B-Befunde (hoechstens 5)",
        _b_befunde_abschnitt(b_befunde),
        "## Leitbilder",
        _leitbilder_abschnitt(leitbilder),
        "## Harness-Notizen",
        _harness_notizen_abschnitt(harness_notizen),
    ]
    return "\n\n".join(teile) + "\n"


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(prog="python -m simulation.browser_abnahme")
    unter = zerleger.add_subparsers(dest="befehl", required=True)

    bericht = unter.add_parser("bericht")
    bericht.add_argument("--lauf", action="append", required=True, dest="laeufe")
    bericht.add_argument("--b-befunde")
    bericht.add_argument("--notizen")
    bericht.add_argument("--modellwahl", default="")
    bericht.add_argument("--ausgabe", required=True)

    kosten = unter.add_parser("kosten")
    kosten.add_argument("datenbanken", nargs="+")

    argumente = zerleger.parse_args()

    if argumente.befehl == "kosten":
        print(f"Summe CHF: {kosten_summe(argumente.datenbanken):.4f}")
        return

    laeufe = []
    belege: dict[str, list[tuple]] = {}
    for verzeichnis in argumente.laeufe:
        pfad = Path(verzeichnis) / "ergebnis.json"
        ergebnis = json.loads(pfad.read_text(encoding="utf-8"))
        laeufe.append(ergebnis)
        db_pfad = ergebnis.get("db_pfad")
        if db_pfad:
            belege[ergebnis.get("geraet", verzeichnis)] = modellbeleg(db_pfad)

    leitbilder_index = Path("docs/guide/bilder/index.json")
    leitbilder = (
        json.loads(leitbilder_index.read_text(encoding="utf-8"))
        if leitbilder_index.exists() else []
    )

    b_befunde = (
        json.loads(Path(argumente.b_befunde).read_text(encoding="utf-8"))
        if argumente.b_befunde else []
    )

    harness_notizen = (
        [z for z in Path(argumente.notizen).read_text(encoding="utf-8").splitlines() if z.strip()]
        if argumente.notizen else []
    )

    markdown = baue_abnahme(
        laeufe, belege=belege, b_befunde=b_befunde, leitbilder=leitbilder,
        harness_notizen=harness_notizen, modellwahl_satz=argumente.modellwahl,
    )
    ausgabe = Path(argumente.ausgabe)
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    ausgabe.write_text(markdown, encoding="utf-8")
    print(f"Bericht geschrieben: {ausgabe}")


if __name__ == "__main__":
    main()

"""Kalibrierung: die Budget- und Grenzkonstanten gegen die heutigen Prompts.

Grundlage von ``docs/kontext-3-5-kalibrierung.md`` (30.09.2026, Padua K,
Task 2). Misst je Phase 1-7 die Systemanweisung, den Koerper des
Gespraechs-Prompts **vor** und **nach** der Kuerzung und den Szenenlauf-Prompt
-- und stellt jede Zahl neben die Konstante, gegen die sie laeuft.

Aufruf::

    python3.11 -m scripts.kalibriere_kontext
    python3.11 -m scripts.kalibriere_kontext --nur-system --profil dortmund-2026

**Ohne Netz, ohne Modellaufruf, ohne Betriebsdaten.** Gemessen wird gegen zwei
Wegwerf-Datenbanken im Speicher:

* ``spaetstand`` -- die geteilte Fixture aus ``tests/fixture_spaetstand.py``
  (dieselbe Gruppe wie ``tests/test_prompt_audit.py`` und
  ``scripts/kontext_recall.py``). Klein: kurze Nachrichten, eine kurze Szene.
* ``vollast`` -- dieselbe Fixture, aufgefuellt bis an die Deckel, die der
  Code selbst setzt: Fenster bis ``FENSTER_ZEICHEN`` (gemessen am 06.09.
  trugen 20 echte Nachrichten ~19.400 Zeichen, das Fenster ist im Spaetstand
  also voll), Festlegungen bis ``BUDGETS["festlegungen"]``, eine Szene ueber
  ``SZENE_ZEICHEN_MAX``, ein volles Journal, fuenf Verdichtungen, acht Szenen.
  Der realistische schlechteste Fall -- kein kuenstlicher Ausreisser.

Die Kuerzung wird genau so gerufen wie in ``kontext.baue`` (``_bloecke`` ->
``_systemgroesse`` -> ``_kuerze_auf_budget``), nur dass vorher eine Kopie der
Bloecke die Rohgroesse festhaelt. Gibt nur Zahlen aus, keine Texte.
"""

import os
import sys

from interview_theater import db, journal, kontext, kurzgeschichte, phasen, repo, szene
from interview_theater import stile, szene_claude

BOT = "gruppe4"


class _E:
    """Minimale Umgebung, wie sie kontext.baue erwartet."""
    bot_name = BOT
    erkenner_modell = None
    weboberflaeche_url = None
    szene_anbieter = None


# ---------------------------------------------------------------------------
# Die zwei Datenlagen
# ---------------------------------------------------------------------------


def _satz(n: int, zeichen: int) -> str:
    """Ein neutraler Fuelltext genau dieser Laenge -- keine echten Inhalte."""
    grund = (f"Beitrag {n}: Wir ueberlegen, wie die Szene weitergeht und was "
             "die Figuren einander noch nicht gesagt haben. ")
    return (grund * (zeichen // len(grund) + 1))[:zeichen]


def _szenentext(zeilen: int, praefix: str = "LEYLA") -> str:
    return "\n".join(
        f"{praefix if i % 2 else 'CEMRE'}: Eine ausgeschriebene Replik mitten "
        f"in der Szene, mit etwas Regie (steht auf), Zeile {i}."
        for i in range(zeilen)
    )


def spaetstand():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tests.fixture_spaetstand import baue_spaetstand, _iso

    conn = db.verbinde(":memory:")
    db.initialisiere(conn)
    baue_spaetstand(conn)
    return conn, _iso


#: Groesse der Vollast-Nachrichten. Mensch kurz, Bot lang -- im Mittel so,
#: dass 20 Nachrichten (``FENSTER_NACHRICHTEN``) knapp ueber
#: ``FENSTER_ZEICHEN`` liegen, wie am 06.09. gemessen (20 Nachrichten =
#: 6.454 Token ~ 19.400 Zeichen, ``docs/kontext-audit-2026-09-06.md`` C.3).
VOLLAST_MENSCH = 200
VOLLAST_BOT = 1_000


def vollast():
    """Die Spaetstand-Fixture, aufgefuellt bis an die Deckel des Codes."""
    conn, iso = spaetstand()

    # Fenster: 30 frische Nachrichten, eine je Minute, die letzte von einem
    # Menschen (sie ist der Ausloeser).
    for j in range(30):
        mensch = j % 2 == 1
        repo.merke_nachricht(
            conn, 1, 1000 + j, "Birk" if mensch else "Bot", 0 if mensch else 1,
            "text", _satz(j, VOLLAST_MENSCH if mensch else VOLLAST_BOT),
            iso(500 + j),
        )

    # Festlegungen: 20 Zeilen a ~110 Zeichen -- mehr, als der Deckel zulaesst.
    for i in range(20):
        bereich = repo.FESTLEGUNG_BEREICHE[i % len(repo.FESTLEGUNG_BEREICHE)]
        repo.schreibe_festlegung(conn, 1, bereich, _satz(i, 110), quelle="befehl")

    # Journal: 12 weitere, verschiedene Eintraege a ~180 Zeichen.
    for i in range(12):
        repo.schreibe_journal(conn, 1, "entschieden", _satz(100 + i, 180), quelle="befehl")

    # Vier weitere Interviews mit Verdichtung (zusammen fuenf).
    for k in range(4):
        aid = repo.lege_aufnahme_an(conn, 1, 20 + k, "lang", "sprache", status="fertig")
        repo.setze_transkript(conn, aid, "T" * 400)
        themen = [
            {"thema": f"Thema {k}-{i}", "beleg_zitat": _satz(i, 80),
             "zitat_geprueft": 1, "kurz": _satz(i, 60)}
            for i in range(8)
        ]
        repo.speichere_verdichtung(conn, 1, aid, _satz(k, 700), themen)

    # Figuren mit fuenf Zitaten (Few-Shots im Szenen-Prompt).
    for f in repo.figuren(conn, 1):
        repo.setze_sprachprofil(
            conn, f["id"], "Kurze Saetze, bricht ab, wiederholt sich.",
            zitate=[_satz(i, 100) for i in range(5)],
        )

    # Szenen 2-7 mit der laengsten gemessenen Szenengroesse (5.349 Zeichen,
    # Kommentar an ``kontext.SZENE_ZEICHEN_MAX``), Szene 8 geplant ohne Text.
    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, 1)}
    for nummer in range(2, 9):
        if nummer not in szenen:
            repo.lege_szene_an(conn, 1, nummer, None, None, None)
    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, 1)}
    for nummer in range(2, 8):
        s = szenen[nummer]
        text = _szenentext(80)[:5_349]
        repo.aktualisiere_szene(conn, s["id"], f"Szene {nummer}", "Kurz.", text,
                                zusammenfassung=_satz(nummer, 300))
    ziel = szenen[8]
    for feld, wert in (("form", "dialog"), ("ort", "Schulhof"),
                       ("was_passiert", _satz(8, 300))):
        repo.setze_szenenfeld(conn, ziel["id"], feld, wert)
    # Szene 1 zuletzt und ueber dem Deckel: sie ist "die aktuelle".
    s1 = szenen[1]
    repo.aktualisiere_szene(conn, s1["id"], s1["titel"], s1["kurzbeschreibung"],
                            _szenentext(120), zusammenfassung=_satz(1, 300))
    return conn, iso


# ---------------------------------------------------------------------------
# Gespraechs-Prompt je Phase
# ---------------------------------------------------------------------------


def _ausloeser(conn):
    alle = repo.letzte_nachrichten(conn, 1, anzahl=1000)
    menschen = [n for n in alle if not n["ist_bot"]]
    return menschen[-1:]


#: Welche Bloecke im **regulaeren** Ablauf in einer Phase ueberhaupt Daten
#: haben. Die Vollast-Datenbank traegt alles auf einmal (acht Szenen schon in
#: Phase 1) -- das ist die Obergrenze, aber nicht der typische Zug. Fuer die
#: phasengerechte Vollast werden die uebrigen Bloecke VOR der Kuerzung
#: geleert; die Kuerzung selbst laeuft unveraendert. Begruendung je Zeile:
#: 1-2 kein Material, keine Szene; 3 dazu die Verdichtungen; 4 kein Material
#: (``PHASEN_ERFINDEN``), dafuer Festlegungen; 5-6 Kernpaket, noch kein
#: Theatertext (Phase 6 schreibt ``prosa``, der Szenenblock liest
#: ``volltext``); 7 der Szenenblock.
PHASENGERECHT = {
    1: {"arbeitsstand", "phasenhinweis", "journal", "fenster", "ausloeser"},
    2: {"arbeitsstand", "phasenhinweis", "journal", "fenster", "ausloeser"},
    3: {"verdichtungen", "arbeitsstand", "phasenhinweis", "journal", "fenster",
        "ausloeser"},
    4: {"arbeitsstand", "festlegungen", "phasenhinweis", "journal", "fenster",
        "ausloeser"},
    5: {"kernpaket", "arbeitsstand", "festlegungen", "phasenhinweis",
        "figurenhinweis", "journal", "fenster", "ausloeser"},
    6: {"kernpaket", "arbeitsstand", "festlegungen", "phasenhinweis",
        "figurenhinweis", "journal", "fenster", "ausloeser"},
    7: {"kernpaket", "arbeitsstand", "festlegungen", "phasenhinweis",
        "figurenhinweis", "szene", "journal", "fenster", "ausloeser"},
}


def miss_phase(conn, phase: int, phasengerecht: bool = False) -> dict:
    """Ein Gespraechszug in ``phase``: Rohbedarf, Ergebnis der Kuerzung, Fenster."""
    phasen.setze(conn, 1, phase, "befehl")
    e = _E()
    ausloeser = _ausloeser(conn)
    fenster = kontext._baue_fenster_eintraege(conn, 1, ausloeser)
    bloecke = kontext._bloecke(conn, 1, ausloeser, e, False, fenster)
    if phasengerecht:
        for name in bloecke:
            if name not in PHASENGERECHT[phase]:
                bloecke[name] = ""
        # Die Kuerzung baut den Szenenblock nur neu, wenn er nicht leer ist
        # (``if _zu_lang() and bloecke["szene"]``) -- geleert bleibt geleert.
    roh = dict(bloecke)
    system_zeichen = kontext._systemgroesse(conn, 1, e)
    gekuerzt = kontext._kuerze_auf_budget(conn, 1, e, bloecke, list(fenster),
                                          system_zeichen)
    # Wie viele Fenster-Eintraege sind geblieben? Die Kuerzung nimmt von vorn.
    bleibt = len(fenster)
    while bleibt and "\n".join(fenster[len(fenster) - bleibt:]) != bloecke["fenster"]:
        bleibt -= 1
    weg = fenster[: len(fenster) - bleibt]

    # Die Kopplung zum Journal-Extraktor: was die Kuerzung aus dem Fenster
    # nimmt, liegt INNERHALB von ``waehle_fenster`` -- der Extraktor haelt es
    # fuer "noch im Fenster" und journalisiert es nicht.
    verdraengt = journal.berechne_verdraengten_abschnitt(repo.unjournalisierte(conn, 1))
    verdraengt_zeilen = {kontext.sprecherzeile(n) for n in verdraengt}
    weg_im_extraktor = sum(1 for x in weg if x in verdraengt_zeilen)
    return {
        "phase": phase,
        "system": system_zeichen,
        "roh": len(kontext._zusammen(roh)),
        "nach": len(kontext._zusammen(bloecke)),
        "gekuerzt": gekuerzt,
        "bloecke_roh": {k: len(v) for k, v in roh.items() if v},
        "bloecke_nach": {k: len(v) for k, v in bloecke.items() if v},
        "fenster_vorher": len(fenster),
        "fenster_nachher": bleibt,
        "fenster_zeichen_vorher": len(roh["fenster"]),
        "fenster_zeichen_nachher": len(bloecke["fenster"]),
        "weg_zeichen": sum(len(x) + 1 for x in weg),
        "weg_token": kontext.schaetze("\n".join(weg)),
        "weg_im_extraktor": weg_im_extraktor,
    }


def _r(budget: int, gemessen: int) -> str:
    return f"{budget - gemessen:+,}".replace(",", ".")


def _z(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def tabelle_system(messungen: list[dict]) -> str:
    gesamt = kontext.gesamtgrenze()
    zeilen = [
        "| Phase | System (Z.) | ~Token ÷3 | SYSTEM_ZEICHEN_MAX | Reserve | "
        "Koerperraum unter gesamtgrenze() | Anteil an ZEICHEN_GRENZE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m in messungen:
        raum = gesamt - m["system"]
        zeilen.append(
            f"| {m['phase']} | {_z(m['system'])} | {_z(m['system'] // 3)} "
            f"| {_z(kontext.SYSTEM_ZEICHEN_MAX)} "
            f"| {_r(kontext.SYSTEM_ZEICHEN_MAX, m['system'])} "
            f"| {_z(raum)} | {round(100 * raum / kontext.zeichengrenze())} % |"
        )
    return "\n".join(zeilen)


def tabelle_koerper(messungen: list[dict]) -> str:
    grenze, gesamt, ziel = kontext.zeichengrenze(), kontext.gesamtgrenze(), kontext.ZIEL
    zeilen = [
        "| Phase | Koerper roh | Reserve Koerper (24.000) | Gesamt roh (Sys+Koerper) "
        "| Reserve gesamt (40.000) | Reserve ZIEL (Token) | Koerper nach Kuerzung "
        "| gekuerzt | Fenster Eintraege vor→nach (Min " + str(kontext.FENSTER_MIN_NACHRICHTEN) + ") "
        "| Fenster Zeichen vor→nach | aus Fenster gekuerzt, nie journalisiert |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for m in messungen:
        weg = (f"{m['fenster_vorher'] - m['fenster_nachher']} Eintr. / "
               f"{_z(m['weg_zeichen'])} Z. (~{_z(m['weg_token'])} Tok.), "
               f"davon im Extraktor-Abschnitt: {m['weg_im_extraktor']}"
               if m["weg_zeichen"] else "–")
        unter = " **unter Min**" if m["fenster_nachher"] < kontext.FENSTER_MIN_NACHRICHTEN else ""
        zeilen.append(
            f"| {m['phase']} | {_z(m['roh'])} | {_r(grenze, m['roh'])} "
            f"| {_z(m['system'] + m['roh'])} | {_r(gesamt, m['system'] + m['roh'])} "
            f"| {_r(ziel, kontext.schaetze('x' * m['roh']))} "
            f"| {_z(m['nach'])} | {'ja' if m['gekuerzt'] else 'nein'} "
            f"| {m['fenster_vorher']}→{m['fenster_nachher']}{unter} "
            f"| {_z(m['fenster_zeichen_vorher'])}→{_z(m['fenster_zeichen_nachher'])} "
            f"| {weg} |"
        )
    return "\n".join(zeilen)


def tabelle_bloecke(messungen: list[dict]) -> str:
    """Groesster Rohwert je Block ueber alle Phasen, gegen BUDGETS (Token)."""
    namen = [n for n in kontext._REIHENFOLGE if n != "erstkontakt"]
    zeilen = [
        "| Block | BUDGETS (Token) | ~Zeichen (×3) | max. roh gemessen (Z.) | in Phase "
        "| Reserve (Z.) | durchgesetzt von |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    durch = {
        "fenster": f"`FENSTER_ZEICHEN` = {_z(kontext.FENSTER_ZEICHEN)} (Budget historisch)",
        "festlegungen": f"`_baue_festlegungen` ({kontext.FESTLEGUNGEN_ZEILEN} Zeilen, Budget)",
        "szene": f"`SZENE_ZEICHEN_MAX` = {_z(kontext.SZENE_ZEICHEN_MAX)} (+ Kopfzeile)",
        "journal": f"`JOURNAL_EINTRAEGE` = {kontext.JOURNAL_EINTRAEGE} Zeilen",
        "system": f"`SYSTEM_ZEICHEN_MAX` (Test) / `gesamtgrenze()`",
    }
    for name in ["system"] + namen:
        budget = kontext.BUDGETS.get(name)
        if name == "system":
            best = max(messungen, key=lambda m: m["system"])
            wert = best["system"]
        else:
            best = max(messungen, key=lambda m: m["bloecke_roh"].get(name, 0))
            wert = best["bloecke_roh"].get(name, 0)
        zeilen.append(
            f"| {name} | {_z(budget) if budget else '–'} "
            f"| {_z(budget * 3) if budget else '–'} | {_z(wert)} "
            f"| {best['phase'] if wert else '–'} "
            f"| {_r(budget * 3, wert) if budget else '–'} "
            f"| {durch.get(name, 'nur Kuerzungsleiter')} |"
        )
    return "\n".join(zeilen)


# ---------------------------------------------------------------------------
# Szenenlauf
# ---------------------------------------------------------------------------


def miss_szene(conn, nummer: int) -> list[dict]:
    """Der Szenen-Prompt fuer Szene ``nummer`` je Form, plus Prosa (Phase 6).

    Gemessen wird der UNGEKUERZTE Rohbedarf: ``IT_SZENE_TOKEN_MAX`` wird
    dafuer weit gesetzt, damit die Kuerzungsleiter nicht greift.

    Die Systemanweisung haengt seit dem Stil-Umbau (06.09.2026) auch vom
    Stil ab (``szene.systemanweisung(form, stil)``, ``stil.py``) -- ein
    Stilblock haengt bis zu 5.760 Zeichen an (``schlagabtausch.md``). Die
    Gruppe waehlt den Stil frei, unabhaengig vom Vorschlag
    (``stile.VORSCHLAG``); gemessen wird deshalb je Form das GROESSTE System
    ueber ALLE Stile inklusive ``stil=None`` (kein Stil gewaehlt), aus der
    echten Liste ``stile.STILE`` -- nicht nur der Vorschlag. Bei ``prosa``
    wirkt kein Stil (``systemanweisung`` haengt ihn nur bei ``form !=
    prosa`` an), deshalb bleibt die Prosa-Zeile unveraendert."""
    alt = os.environ.get("IT_SZENE_TOKEN_MAX")
    os.environ["IT_SZENE_TOKEN_MAX"] = str(10_000_000)
    try:
        phasen.setze(conn, 1, 7, "befehl")
        ziel = {s["nummer"]: s for s in repo.hole_szenen(conn, 1)}[nummer]
        nutzer = szene.baue_nutzertext(conn, 1, f"Schreib Szene {nummer}.", ziel)
        stile_slugs = [None] + [s["slug"] for s in stile.STILE]
        ergebnis = []
        for form in szene.FORMEN:
            bester_stil, beste_laenge = None, -1
            for stil_slug in stile_slugs:
                laenge = len(szene.systemanweisung(form, stil_slug))
                if laenge > beste_laenge:
                    bester_stil, beste_laenge = stil_slug, laenge
            ergebnis.append({"form": form, "stil": bester_stil or "(kein Stil)",
                             "system": beste_laenge, "nutzer": len(nutzer)})
        ergebnis.append({"form": "prosa (Phase 6)", "stil": "-",
                         "system": len(kurzgeschichte.systemanweisung()),
                         "nutzer": len(kurzgeschichte.baue_nutzertext(conn, 1))})
        return ergebnis
    finally:
        if alt is None:
            os.environ.pop("IT_SZENE_TOKEN_MAX", None)
        else:
            os.environ["IT_SZENE_TOKEN_MAX"] = alt


def tabelle_szene(messungen: list[dict]) -> str:
    j = szene.SZENE_ZEICHEN_JE_TOKEN
    b_claude, b_info = szene.token_budget(True), szene.token_budget(False)
    fenster_claude = szene.CLAUDE_FENSTER_TOKEN - szene_claude.MAX_TOKENS
    fenster_info = szene.INFOMANIAK_GESAMT_TOKEN - szene.MAX_TOKENS
    zeilen = [
        f"| Form | Stil (groesstes System) | System (Z.) | Nutzer (Z.) | Nutzer Tok. (÷{j}) "
        f"| System+Nutzer Tok. "
        f"| Reserve Budget Claude ({_z(b_claude)}, nur Nutzer) "
        f"| Reserve Budget Infomaniak ({_z(b_info)}, nur Nutzer) "
        f"| Reserve Eingaberaum Claude ({_z(fenster_claude)}, Sys+Nutzer) "
        f"| Reserve Eingaberaum Infomaniak ({_z(fenster_info)}, Sys+Nutzer) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in messungen:
        nt = int(m["nutzer"] / j)
        gt = int((m["system"] + m["nutzer"]) / j)
        zeilen.append(
            f"| {m['form']} | {m.get('stil', '-')} | {_z(m['system'])} | {_z(m['nutzer'])} "
            f"| {_z(nt)} | {_z(gt)} "
            f"| {_r(b_claude, nt)} | {_r(b_info, nt)} "
            f"| {_r(fenster_claude, gt)} | {_r(fenster_info, gt)} |"
        )
    return "\n".join(zeilen)


# ---------------------------------------------------------------------------


def konstanten() -> str:
    return (
        f"ZEICHEN_GRENZE={kontext.zeichengrenze()} GESAMT={kontext.gesamtgrenze()} "
        f"ZIEL={kontext.ZIEL} SYSTEM_ZEICHEN_MAX={kontext.SYSTEM_ZEICHEN_MAX} "
        f"FENSTER_ZEICHEN={kontext.FENSTER_ZEICHEN} "
        f"FENSTER_NACHRICHTEN={kontext.FENSTER_NACHRICHTEN} "
        f"FENSTER_MIN_NACHRICHTEN={kontext.FENSTER_MIN_NACHRICHTEN} "
        f"SZENE_ZEICHEN_MAX={kontext.SZENE_ZEICHEN_MAX} "
        f"SZENE_ZEICHEN_NOTFALL={kontext.SZENE_ZEICHEN_NOTFALL} "
        f"SCHWELLE_VERDRAENGUNG={journal.SCHWELLE_VERDRAENGUNG} "
        f"SZENE_TOKEN_MAX claude={szene.token_budget(True)} "
        f"infomaniak={szene.token_budget(False)} "
        f"IT_WORKSHOP={os.environ.get('IT_WORKSHOP') or '(Vorgabeprofil)'}"
    )


def main(argv: list[str]) -> int:
    # Kein Regie-Zettel aus einer Betriebsumgebung: ``zusatz.md`` liegt neben
    # ``IT_DB`` -- ohne IT_DB wird keiner gelesen. Beide Variablen werden am
    # Ende wiederhergestellt (try/finally) -- sonst liesse ein Aufruf aus dem
    # selben Prozess (z.B. der Test) ``IT_DB``/``IT_WORKSHOP`` fuer alles
    # Nachfolgende geloescht bzw. veraendert stehen.
    alt_db = os.environ.pop("IT_DB", None)
    alt_workshop = os.environ.get("IT_WORKSHOP")
    hatte_workshop = "IT_WORKSHOP" in os.environ
    try:
        if "--profil" in argv:
            # Statt ``IT_WORKSHOP=... python -m ...``: ``workshop.aktiv()``
            # liest die Variable bei jedem Aufruf, also genuegt es, sie hier
            # zu setzen.
            os.environ["IT_WORKSHOP"] = argv[argv.index("--profil") + 1]
        print(konstanten())
        phasenliste = range(phasen.ERSTE, phasen.LETZTE + 1)

        conn, _ = spaetstand()
        fixture = [miss_phase(conn, p) for p in phasenliste]
        print("\n## Systemanweisung je Phase\n")
        print(tabelle_system(fixture))
        if "--nur-system" in argv:
            return 0
        print("\n## Gespraechs-Prompt, Fixture Spaetstand\n")
        print(tabelle_koerper(fixture))
        szene_fixture = miss_szene(conn, 4)

        conn, _ = vollast()
        last = [miss_phase(conn, p) for p in phasenliste]
        print("\n## Gespraechs-Prompt, Vollast (alle Bloecke in jeder Phase)\n")
        print(tabelle_koerper(last))
        print("\n## Gespraechs-Prompt, Vollast phasengerecht\n")
        print(tabelle_koerper([miss_phase(conn, p, phasengerecht=True) for p in phasenliste]))
        print("\n## Bloecke gegen BUDGETS (Vollast, groesster Rohwert ueber alle Phasen)\n")
        print(tabelle_bloecke(last))
        print("\n## Szenenlauf, Fixture Spaetstand (Ziel Szene 4, ungekuerzt)\n")
        print(tabelle_szene(szene_fixture))
        print("\n## Szenenlauf, Vollast (Ziel Szene 8, sieben Vorszenen, ungekuerzt)\n")
        print(tabelle_szene(miss_szene(conn, 8)))
        return 0
    finally:
        if alt_db is None:
            os.environ.pop("IT_DB", None)
        else:
            os.environ["IT_DB"] = alt_db
        if hatte_workshop:
            os.environ["IT_WORKSHOP"] = alt_workshop
        else:
            os.environ.pop("IT_WORKSHOP", None)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

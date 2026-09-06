"""Misst den Ist-Stand des Kontext-Aufbaus gegen eine KOPIE einer Datenbank.

Grundlage des Berichts ``docs/kontext-audit-2026-09-06.md``. Rein messend,
ohne Betriebswirkung -- aber ``kontext.baue`` merkt sich das Phasenangebot und
kann einen Vorfall schreiben, deshalb **nur gegen eine Kopie** laufen lassen::

    cp betrieb/test.db /tmp/messung.db
    python -m scripts.miss_kontext /tmp/messung.db

Gibt aus: Prompt-Groessen je Block, Fensterinhalt, ob die Kuerzung greift und
-- der eigentliche Zweck -- ob der Journal-Extraktor mit dem aktuellen Fenster
ueberhaupt je anspringt (Befund C.3 des Audits: seine Verdraengungsrechnung
haengt an ``kontext.BUDGETS["fenster"]``, waehrend das reale Fenster seit dem
06.09.2026 nach Nachrichten und Minuten bemessen wird).

Gibt **keine** Nachrichtentexte, Transkripte oder Namen aus -- nur Zahlen.
"""

import sys

from interview_theater import db, journal, kontext, phasen, repo


class _E:
    """Minimale Umgebung, wie sie kontext.baue erwartet."""
    bot_name = "messung"
    erkenner_modell = None
    weboberflaeche_url = None


def _gruppen(conn) -> list[int]:
    return [r["chat_id"] for r in conn.execute("SELECT chat_id FROM gruppe")]


def miss(conn, chat_id: int) -> None:
    alle = repo.letzte_nachrichten(conn, chat_id, anzahl=1000)
    if not alle:
        print(f"  (keine Nachrichten)")
        return

    menschen = [n for n in alle if not n["ist_bot"]]
    ausloeser = menschen[-1:] or alle[-1:]

    protokoll: list = []
    koerper = kontext.baue(conn, chat_id, ausloeser, _E(), protokoll=protokoll)
    stufe = phasen.aktuelle(conn, chat_id)
    system = kontext.system("messung", stufe)
    umriss = protokoll[0]

    print(f"  Phase {stufe} | {len(alle)} Nachrichten")
    print(f"  SYSTEM  {len(system):>7} Zeichen / {kontext.schaetze(system):>6} Token")
    print(f"  KOERPER {len(koerper):>7} Zeichen / {kontext.schaetze(koerper):>6} Token"
          f"  (gekuerzt: {umriss['gekuerzt']})")
    print(f"  GESAMT  {len(system) + len(koerper):>7} Zeichen"
          f" -- Zeichengrenze {kontext.zeichengrenze()} prueft NUR den Koerper")
    belegt = {k: v for k, v in umriss["bloecke"].items() if v}
    print(f"  Bloecke (Token): {belegt}")

    eintraege = kontext._baue_fenster_eintraege(conn, chat_id, ausloeser)
    print(f"  FENSTER {len(eintraege)} Eintraege / "
          f"{sum(len(x) for x in eintraege)} Zeichen"
          + ("   <-- LEER" if not eintraege else ""))

    # Die Kopplung: rechnet der Extraktor gegen dasselbe Fenster wie der Prompt?
    unjournalisiert = repo.unjournalisierte(conn, chat_id)
    verdraengt = journal.berechne_verdraengten_abschnitt(unjournalisiert)
    verlauf_token = kontext.schaetze(
        "\n".join(kontext.sprecherzeile(n) for n in alle)
    )
    print(f"  unjournalisiert: {len(unjournalisiert)} Nachrichten"
          f" -> verdraengt {len(verdraengt)}"
          f" -> Extraktor laeuft: {bool(verdraengt)}")
    print(f"  Verlauf gesamt {verlauf_token} Token"
          f" vs. Verdraengungsbudget {kontext.BUDGETS['fenster']} Token"
          + ("   <-- kann nie verdraengen"
             if verlauf_token < kontext.BUDGETS["fenster"] else ""))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    pfad = argv[1]
    if "betrieb/" in pfad:
        print("Nur gegen eine KOPIE laufen lassen, nicht gegen betrieb/*.db")
        return 2
    conn = db.verbinde(pfad)
    print(f"Konstanten: FENSTER_NACHRICHTEN={kontext.FENSTER_NACHRICHTEN}"
          f" FENSTER_MINUTEN={kontext.FENSTER_MINUTEN}"
          f" BUDGETS[fenster]={kontext.BUDGETS['fenster']}"
          f" SCHWELLE_VERDRAENGUNG={journal.SCHWELLE_VERDRAENGUNG}"
          f" ZEICHEN_GRENZE={kontext.zeichengrenze()} ZIEL={kontext.ZIEL}")
    for chat_id in _gruppen(conn):
        print(f"\nGruppe {chat_id}:")
        miss(conn, chat_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

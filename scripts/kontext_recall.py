"""Recall-Messung: was weiss das Modell nach der Kuerzung noch?

Auftrag 5 des Kontext-Audits (``docs/kontext-audit-2026-09-06.md``, Abschnitt
D). Unsere 20+ Prompt-Audit-Tests messen **Form** -- Groesse, Dubletten,
Reihenfolge. Keiner misst, **was nach der Kuerzung noch beantwortbar ist**.
hermes-agents ``evals/compaction/`` stellt genau diese Frage: Faktenfragen aus
der wegkomprimierten Region, Recall gegen behaltene Token. Ihre Kernaussage --
*miss, was die Kuerzung an Erinnerung kostet, nicht was sie an Token spart* --
ist die groesste konzeptionelle Luecke, die der Audit gefunden hat.

**Ohne Sprachmodell.** Die Pruefung ist eine reine Textsuche: steht die
Antwort noch woertlich im Prompt? Das findet nach Einschaetzung des Audits
rund 80 % der Faelle und kostet nichts -- kein Aufruf, kein Geld, keine
Nichtdeterminiertheit, und damit als Test tauglich. Ein Modell im Kreis waere
die zweite Fassung, nicht die erste.

**Die zehn Fragen** sind mechanisch aus der Datenbank abgeleitet, nicht
erfunden: Kernthema, Kernfrage, Rahmen, Geschichte, Begriffe, die erste und
die letzte Figur, das Sprachprofil einer Figur, der Titel der aktuellen Szene
und ihr Schluss. Alles Dinge, die im Arbeitsstand oder im Szenenblock stehen
und die Kuerzung deshalb **ueberleben muessten**. Wo sie es nicht tun, ist das
der Befund.

Aufruf::

    cp betrieb/test.db /tmp/recall.db
    python -m scripts.kontext_recall /tmp/recall.db
    python -m scripts.kontext_recall --fixture      # Spaetstand-Fixture
    python -m scripts.kontext_recall --fixture 20   # mit 20-facher Szene (C.4)

Gibt **keine** Nachrichtentexte, Transkripte, Namen oder Antworttexte aus --
nur die Frage, ihre Kategorie und ja/nein je Spalte. Die Antworten selbst
bleiben im Prozess.

``kontext.baue`` merkt sich das Phasenangebot und kann einen Vorfall
schreiben: nur gegen eine **Kopie** laufen lassen.
"""

import os
import sys

from interview_theater import db, kontext, phasen, repo


class _E:
    """Minimale Umgebung, wie sie kontext.baue erwartet."""
    bot_name = "messung"
    erkenner_modell = None
    weboberflaeche_url = None


#: Wie gross die Grenzen im "vorher"-Lauf gesetzt werden: so weit, dass die
#: Kuerzung sicher nicht greift. Der Vergleich braucht denselben Prompt,
#: einmal ungekuerzt und einmal gekuerzt -- nicht zwei verschiedene.
_WEIT = 10_000_000


def _erste_zeile(text: str) -> str:
    for zeile in (text or "").splitlines():
        if zeile.strip():
            return zeile.strip()
    return ""


def _letzte_zeile(text: str) -> str:
    for zeile in reversed((text or "").splitlines()):
        if zeile.strip():
            return zeile.strip()
    return ""


def fragen(conn, chat_id: int) -> list[dict]:
    """Die zehn mechanischen Faktenfragen zu einer Gruppe.

    Jede Frage traegt ``antwort``: die Zeichenkette, die im Prompt stehen
    muss, damit sie beantwortbar ist. Fragen ohne Datengrundlage fallen weg
    (eine Gruppe ohne Szene hat keine Szenenfrage) -- lieber acht ehrliche
    Fragen als zehn, von denen zwei immer 'nein' sagen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)
    # Die zuletzt geaenderte Szene ist oft eine leere Huelle (angelegt, noch
    # nicht geschrieben). Gefragt wird nach der letzten, die einen Text hat --
    # das ist die, die im Szenenblock stehen kann.
    szene = repo.hole_letzte_szene(conn, chat_id)
    if szene is None or not (szene["volltext"] or "").strip():
        mit_text = [s for s in repo.hole_szenen(conn, chat_id)
                    if (s["volltext"] or "").strip()]
        szene = mit_text[-1] if mit_text else None
    journaleintraege = repo.journal(conn, chat_id)

    roh: list[tuple[str, str, str]] = []

    def feld(name: str) -> str:
        if stand is None:
            return ""
        try:
            return (stand[name] or "").strip()
        except (IndexError, KeyError):
            return ""

    roh.append(("arbeitsstand", "Welches Kernthema hat die Gruppe gesetzt?",
                feld("kernthema")))
    roh.append(("arbeitsstand", "Wie lautet die Kernfrage?", feld("kernfrage")))
    roh.append(("arbeitsstand", "In welchem Rahmen spielt das Stueck?",
                _erste_zeile(feld("rahmen"))))
    roh.append(("arbeitsstand", "Wie lautet die Geschichte?",
                _erste_zeile(feld("geschichte"))))
    roh.append(("arbeitsstand", "Welche Begriffe hat die Gruppe gesammelt?",
                feld("begriffe")))

    if figuren:
        roh.append(("figuren", "Welche Figuren hat die Gruppe?",
                    ", ".join(f["name"] for f in figuren)))
        mit_wunsch = [f for f in figuren if (f["beschreibung"] or "").strip()]
        if mit_wunsch:
            roh.append(("figuren", "Was will die erste Figur?",
                        (mit_wunsch[0]["beschreibung"] or "").strip()))
            roh.append(("figuren", "Was will die letzte Figur?",
                        (mit_wunsch[-1]["beschreibung"] or "").strip()))

    if szene is not None:
        roh.append(("szene", "Wie heisst die aktuelle Szene?",
                    (szene["titel"] or "").strip()))
        roh.append(("szene", "Worum geht es in der aktuellen Szene?",
                    (szene["kurzbeschreibung"] or "").strip()))
        volltext = szene["volltext"] or ""
        roh.append(("szene", "Wie faengt die aktuelle Szene an?",
                    _erste_zeile(volltext)))
        roh.append(("szene", "Wie endet die aktuelle Szene?",
                    _letzte_zeile(volltext)))

    if journaleintraege:
        roh.append(("journal", "Was steht im aeltesten Journaleintrag?",
                    (journaleintraege[0]["text"] or "").strip()))
        roh.append(("journal", "Was steht im juengsten Journaleintrag?",
                    (journaleintraege[-1]["text"] or "").strip()))

    # Der **weggefallene** Teil: was heute schon nicht mehr im Prompt steht
    # oder als erstes fliegt. Ohne diese Zeilen misst die Tabelle nur, dass
    # das Geschuetzte geschuetzt ist -- und das ist keine Recall-Messung,
    # sondern eine Tautologie (der Fehler, den hermes-agents evals/compaction
    # ausdruecklich vermeidet: Fragen aus der wegkomprimierten Region).
    verlauf = repo.letzte_nachrichten(conn, chat_id, anzahl=1000)
    gespraech = [n for n in verlauf if (n["text"] or "").strip()]
    if len(gespraech) > kontext.FENSTER_NACHRICHTEN:
        alt = gespraech[0]
        mitte = gespraech[len(gespraech) // 2]
        roh.append(("verdraengt", "Was wurde ganz am Anfang gesagt?",
                    (alt["text"] or "").strip()))
        roh.append(("verdraengt", "Was wurde in der Mitte des Verlaufs gesagt?",
                    (mitte["text"] or "").strip()))
    if len(journaleintraege) > kontext.JOURNAL_EINTRAEGE:
        raus = journaleintraege[: len(journaleintraege) - kontext.JOURNAL_EINTRAEGE]
        roh.append(("verdraengt", "Was stand in einem aelteren Journaleintrag?",
                    (raus[0]["text"] or "").strip()))
    if szene is not None:
        volltext = szene["volltext"] or ""
        zeilen_szene = [z for z in volltext.splitlines() if z.strip()]
        if len(zeilen_szene) > 40:
            roh.append(("verdraengt", "Was steht in der Mitte der aktuellen Szene?",
                        zeilen_szene[len(zeilen_szene) // 2].strip()))

    # Kurze Antworten taugen nicht als Textprobe: "Ja" steht in jedem Prompt.
    tauglich = [
        {"kategorie": k, "frage": f, "antwort": a}
        for k, f, a in roh
        if len(a) >= 12
    ]
    # Zehn Fragen, aber die aus dem weggefallenen Teil **zuerst**: sie sind
    # der Zweck der Messung, die geschuetzten Felder die Kontrollgruppe.
    verdraengt = [z for z in tauglich if z["kategorie"] == "verdraengt"]
    rest = [z for z in tauglich if z["kategorie"] != "verdraengt"]
    return (verdraengt + rest)[:10]


def _prompt(conn, chat_id: int, ausloeser, weit: bool) -> str:
    """Der Koerper einmal ungekuerzt (``weit``) und einmal wie im Betrieb."""
    alt = (os.environ.get("IT_PROMPT_ZEICHEN"),
           os.environ.get("IT_PROMPT_ZEICHEN_GESAMT"))
    try:
        if weit:
            os.environ["IT_PROMPT_ZEICHEN"] = str(_WEIT)
            os.environ["IT_PROMPT_ZEICHEN_GESAMT"] = str(_WEIT)
        else:
            os.environ.pop("IT_PROMPT_ZEICHEN", None)
            os.environ.pop("IT_PROMPT_ZEICHEN_GESAMT", None)
        return kontext.baue(conn, chat_id, ausloeser, _E())
    finally:
        for name, wert in zip(
            ("IT_PROMPT_ZEICHEN", "IT_PROMPT_ZEICHEN_GESAMT"), alt
        ):
            if wert is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = wert


def messe(conn, chat_id: int) -> dict:
    """Recall vorher/nachher fuer eine Gruppe. Reine Zahlen und ja/nein."""
    alle = repo.letzte_nachrichten(conn, chat_id, anzahl=1000)
    menschen = [n for n in alle if not n["ist_bot"]]
    ausloeser = menschen[-1:] or alle[-1:]

    vorher = _prompt(conn, chat_id, ausloeser, weit=True)
    nachher = _prompt(conn, chat_id, ausloeser, weit=False)
    stufe = phasen.aktuelle(conn, chat_id)
    system = kontext.system(_E.bot_name, stufe)

    zeilen = []
    for f in fragen(conn, chat_id):
        zeilen.append({
            "kategorie": f["kategorie"],
            "frage": f["frage"],
            "vorher": f["antwort"] in vorher,
            "nachher": f["antwort"] in nachher,
        })
    return {
        "chat_id": chat_id,
        "phase": stufe,
        "system_zeichen": len(system),
        "vorher_zeichen": len(vorher),
        "nachher_zeichen": len(nachher),
        "gesamt_nachher": len(system) + len(nachher),
        "zeilen": zeilen,
        "recall_vorher": sum(1 for z in zeilen if z["vorher"]),
        "recall_nachher": sum(1 for z in zeilen if z["nachher"]),
    }


def _tabelle(ergebnis: dict) -> str:
    breite = max([len(z["frage"]) for z in ergebnis["zeilen"]] + [5])
    kopf = f"| {'Frage'.ljust(breite)} | Bereich      | vorher | nachher |"
    strich = f"|{'-' * (breite + 2)}|--------------|--------|---------|"
    zeilen = [kopf, strich]
    for z in ergebnis["zeilen"]:
        zeilen.append(
            f"| {z['frage'].ljust(breite)} | {z['kategorie'].ljust(12)} "
            f"| {'ja' if z['vorher'] else 'NEIN':<6} "
            f"| {'ja' if z['nachher'] else 'NEIN':<7} |"
        )
    n = len(ergebnis["zeilen"])
    zeilen.append(
        f"\nRecall {ergebnis['recall_nachher']}/{n} nach Kuerzung "
        f"(vorher {ergebnis['recall_vorher']}/{n})"
    )
    return "\n".join(zeilen)


def bericht(ergebnis: dict) -> str:
    kopf = (
        f"Gruppe {ergebnis['chat_id']} | Phase {ergebnis['phase']}\n"
        f"  System  {ergebnis['system_zeichen']:>7} Zeichen"
        f"  (Testgrenze {kontext.SYSTEM_ZEICHEN_MAX})\n"
        f"  Koerper {ergebnis['vorher_zeichen']:>7} -> "
        f"{ergebnis['nachher_zeichen']} Zeichen"
        f"  (Grenze {kontext.zeichengrenze()})\n"
        f"  Gesamt  {ergebnis['gesamt_nachher']:>7} Zeichen"
        f"  (Gesamtgrenze {kontext.gesamtgrenze()})\n"
    )
    return kopf + "\n" + _tabelle(ergebnis)


def _fixture_conn(szene_faktor: int = 1):
    """Die Spaetstand-Fixture aus dem Prompt-Audit, ohne pytest.

    Dieselbe Gruppe, gegen die ``tests/test_prompt_audit.py`` misst -- so
    laeuft das Skript auch dort, wo keine Betriebs-DB liegt, und die Zahlen
    im Bericht sind reproduzierbar.

    ``szene_faktor`` blaeht den Szenentext auf: der Fall aus Befund C.4, in
    dem der Szenenblock alles andere aus dem Prompt draengte. Genau dort
    unterscheiden sich die Recall-Zahlen vor und nach Auftrag 3."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tests.fixture_spaetstand import baue_spaetstand

    conn = db.verbinde(":memory:")
    db.initialisiere(conn)
    baue_spaetstand(conn)
    if szene_faktor > 1:
        s = repo.hole_szenen(conn, 1)[0]
        text = "\n".join(
            f"LEYLA: Ein ausgeschriebener Satz mitten in der Szene, Zeile {i}."
            for i in range(szene_faktor * 200)
        )
        repo.aktualisiere_szene(conn, s["id"], s["titel"], s["kurzbeschreibung"], text)
    return conn


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--fixture":
        faktor = int(argv[2]) if len(argv) == 3 else 1
        conn = _fixture_conn(faktor)
        chat_ids = [1]
    elif len(argv) == 2:
        pfad = argv[1]
        if "betrieb/" in pfad:
            print("Nur gegen eine KOPIE laufen lassen, nicht gegen betrieb/*.db")
            return 2
        conn = db.verbinde(pfad)
        chat_ids = [r["chat_id"] for r in conn.execute("SELECT chat_id FROM gruppe")]
    else:
        print(__doc__)
        return 2

    schlecht = 0
    for chat_id in chat_ids:
        ergebnis = messe(conn, chat_id)
        if not ergebnis["zeilen"]:
            print(f"Gruppe {chat_id}: keine Faktenfragen ableitbar (leere Gruppe)")
            continue
        print(bericht(ergebnis))
        print()
        schlecht += ergebnis["recall_vorher"] - ergebnis["recall_nachher"]
    if schlecht:
        print(f"Insgesamt {schlecht} Faktenfrage(n) durch die Kuerzung verloren.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

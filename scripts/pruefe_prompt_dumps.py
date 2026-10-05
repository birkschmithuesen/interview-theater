"""Misst die erzeugten Prompt-Dumps: Dubletten, Bloecke, verbotene Reste.

Aufruf::

    python -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-09-06
"""

import re
from collections import Counter
from pathlib import Path

#: Saetze/Zeilen ab dieser Laenge zaehlen als Dublette, wenn sie zweimal
#: vorkommen -- kuerzere Zeilen ("Ja.", "Szene 2") wiederholen sich legitim.
DUBLETTE_AB = 80

#: Was in keinem Prompt mehr stehen darf.
VERBOTEN = (
    "Kessel", "Mira", "Pola", "Pal ",
    "Kernthema & Figuren",
    "sieben Stationen",
    "Phase 7 · Durchlauf",
    "6. Szenen ",
)


def zeilen(text: str) -> list[str]:
    return [z.strip() for z in text.splitlines() if z.strip()]


#: Die Kopfzeilen, die ``erzeuge_prompts._schreibe`` selbst schreibt. Sie sind
#: deutsch ("=== SYSTEM (26943 Zeichen, ~9112 Token) ===") und waeren in jedem
#: englischen Dump ein Falsch-Positiv -- gemessen am 05.10.2026 genau zwei
#: Treffer je Datei, beide aus dieser Zeile.
KOPFZEILEN = ("=== ", "# ")


def teile(text: str) -> tuple[str, str]:
    """(Systemteil, Nutzerteil). Der Trenner ist ``=== NUTZER``, wie in
    ``erzeuge_prompts._schreibe``."""
    stuecke = text.split("=== NUTZER")
    return stuecke[0], (stuecke[1] if len(stuecke) > 1 else "")


def inhaltszeilen(text: str) -> list[tuple[int, str]]:
    """Nummerierte, nicht-leere Zeilen ohne die Kopfzeilen des Dumps.

    Die Nummer ist **1-basiert und auf die Datei bezogen** -- genau die Zahl,
    die die Opus-Lesung spaeter in ihrem Befund nennt, damit das Zitat
    mechanisch geprueft werden kann."""
    ergebnis = []
    for nummer, zeile in enumerate(text.splitlines(), start=1):
        knapp = zeile.strip()
        if not knapp or knapp.startswith(KOPFZEILEN):
            continue
        ergebnis.append((nummer, knapp))
    return ergebnis


#: Deutsche Funktionswoerter, die **kein** englisches Wort sind. Jedes Wort
#: hier ist am 05.10.2026 gegen die vier Dumps von 2026-10-02-padua-p2
#: gemessen worden: null Treffer. Bewusst NICHT in der Liste, weil auch
#: englisch und damit Falsch-Positive: also, was, wie, hier, war, an, in, so,
#: die, hat, man, bei.
DE_STOPWOERTER = frozenset({
    "und", "oder", "nicht", "eine", "einen", "einem", "dass", "sich", "der",
    "das", "den", "dem", "ist", "sind", "wird", "werden", "aber", "auch",
    "noch", "schon", "wenn", "weil", "ihre", "wir", "fuer", "für", "von",
    "zum", "zur", "aus", "ueber", "über", "durch", "ohne", "kann", "soll",
    "muss", "nur", "sehr", "immer", "jede", "jeder", "etwas", "nichts",
    "mehr", "weniger", "zwei", "drei", "vier", "fuenf", "fünf", "steht",
    "gibt", "wurde", "seine", "diese", "dieser", "damit", "dafuer", "dafür",
    "dabei", "dann", "dort", "woerter", "wörter", "zeichen", "deine", "euer",
    "eure", "bitte", "keine", "kein", "vielleicht", "natuerlich", "natürlich",
    "trotzdem", "deshalb", "ausserdem", "außerdem", "korrigiere", "schreibe",
})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")

#: Was Birks UX-Regeln in einem Prompt verbieten -- je Eintrag Muster und der
#: Satz, der im Bericht daneben steht. Ein Muster ohne Erklaerung ist eine
#: Zahl, die niemand nachrechnen kann.
#:
#: ACHTUNG: "Yes, save"/"No, change it again" sind zugleich die ECHTEN
#: Knopfbeschriftungen (sprachen/en/texte.toml: _TEXT_SPEICHERN_KNOPF /
#: _TEXT_ANDERS_KNOPF). Ein Treffer ist deshalb kein automatischer Fix, sondern
#: eine Frage an Birk -- siehe Task 10.
VERBOTENE_UX = (
    ("Yes, save",
     "Bestaetigungs-Zeremonie: Entscheidungen werden automatisch gespeichert "
     "und mit EINER Systemzeile plus Undo quittiert (UX-Regel 3). Zugleich die "
     "echte Knopfbeschriftung -- vor einem Fix pruefen, siehe BEFUND."),
    ("No, change it again",
     "Wie 'Yes, save': dieselbe Zeremonie, dieselbe Doppelrolle."),
    ("please fix it in the work status",
     "Schiebt die Arbeit zur Gruppe zurueck, statt einen Weg anzubieten "
     "(UX-Regel 3: jedes Speichern hat ein Undo)."),
    ("ask whether",
     "Rueckfrage vor dem Speichern: 'speichern beim ersten Mal, keine "
     "Rueckfrage davor' (AGENTS.md, Haltung 06.09.2026)."),
    ("how many scenes",
     "Zahl und Umfang entscheidet die Gruppe; der Bot schlaegt keine Anzahl "
     "vor (UX-Regel 1)."),
    ("wake word",
     "Kein Weckwort fuer einen Bot, der in der Sitzung ohnehin zuhoert "
     "(UX-Regel 4)."),
)

#: Zeilen, die eine Frageregel aufstellen UND eine Position nennen. Sie werden
#: nebeneinander gedruckt, damit ein Mensch den Widerspruch sieht -- gemessen in
#: sprachen/en/prompts/system.md: Z146 "ends with an open question", Z148
#: "BEFORE the suggestion block", Z151 "that one at the end".
FRAGEREGEL = re.compile(
    r"question.{0,80}?\b(ends?|before|after|first|last)\b"
    r"|\b(ends?|before|after|first|last)\b.{0,80}?question",
    re.IGNORECASE | re.DOTALL,
)


def deutsche_reste(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Zeile, getroffenes Wort) je deutschem Funktionswort."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for wort in _WORT.findall(zeile.lower()):
            if wort in DE_STOPWOERTER:
                treffer.append((nummer, zeile, wort))
    return treffer


def verbotene_muster(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Muster, Erklaerung). **Nur auf den Systemteil anwenden**
    -- im Nutzerteil sind diese Wortlaute Geschichte und kein Promptfehler."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for muster, erklaerung in VERBOTENE_UX:
            if muster.lower() in zeile.lower():
                treffer.append((nummer, muster, erklaerung))
    return treffer


def frageregel_zeilen(text: str) -> list[tuple[int, str]]:
    return [(n, z) for n, z in inhaltszeilen(text) if FRAGEREGEL.search(z)]


#: Ein Quotenzaehler: "(0/3)", "(2 / 5)". Birk 00:40: steht er als Quote da
#: ("du hast erst 0 von 3") oder neutral? Der Pruefer entscheidet das nicht --
#: er stellt die Zeilen hin, damit die Lesung sie beurteilen kann.
QUOTE = re.compile(r"\(\s*\d+\s*/\s*\d+\s*\)")

#: Eine Sprecherzeile im Verlaufsblock. Deutsch UND englisch, weil der
#: Nutzertext in Padua englisch ist (``kontext._SPRECHER_BOT`` -> "You",
#: ``_PSEUDONYM`` -> "Member {nummer}"), der Dump aber auch gegen ein deutsches
#: Profil gefahren werden kann. Die letzte Alternative faengt einen Klarnamen
#: (Dortmund ohne Pseudonyme) und ist bewusst eng: hoechstens 28 Zeichen und
#: Grossbuchstabe am Anfang, sonst waere "Note: see above" eine Sprecherzeile.
SPRECHER = re.compile(r"^(Du|You|Mitglied \d+|Member \d+|[A-Z][\w .'-]{0,27}):")

#: Die Systemzeilen, die als Bot-Zeile im Verlauf mitgehen. Gemessen:
#: ``repo.merke_bot_zeile`` legt sie als typ='text', ist_bot=1 ab -- sie sind
#: also Teil des Fensters, und genau das ist Birks Frage ("Gehen Bot-Zeilen,
#: Systemzeilen und Transkript-Echos mit?").
SYSTEMMARKEN = ("📌", "Noted:", "Changed since")

#: Das Mikrofon vor einem Transkript-Echo. Es soll im Verlauf NICHT stehen
#: (``repo.TYP_TRANSKRIPT`` faellt aus allen drei Fenstern) -- steht es da, ist
#: das ein Befund und keine Kleinigkeit: der Erkenner las am 06.09.2026
#: Interviewinhalt als Gruppenabsicht.
ECHO_MARKE = "🎙"


def verlaufsbefund(nutzer: str) -> dict:
    """Was im Nutzerteil an Verlauf steckt (Birk, 05.10.2026 00:40).

    Keine Bewertung, nur Zaehlung: ob fuenf Bot-Zeilen auf vier Gruppenzeilen
    richtig sind, entscheidet die Lesung -- hier entsteht die Zahl, an der sie
    sich festhalten kann."""
    zuege = []
    for nummer, zeile in inhaltszeilen(nutzer):
        treffer = SPRECHER.match(zeile)
        if treffer:
            zuege.append((nummer, treffer.group(1), zeile))
    return {
        "zuege": len(zuege),
        "sprecher": sorted({name for _, name, _ in zuege}),
        "bot_zeilen": sum(1 for _, name, _ in zuege if name in ("Du", "You")),
        "systemzeilen": sum(
            1 for _, _, zeile in zuege
            if any(marke in zeile for marke in SYSTEMMARKEN)
        ),
        "transkript_echos": sum(
            1 for _, zeile in inhaltszeilen(nutzer) if ECHO_MARKE in zeile
        ),
        "quoten": [(n, z) for n, z in inhaltszeilen(nutzer) if QUOTE.search(z)],
    }


#: Die Koepfe der zwei Bloecke vom 05.10.2026 (Birk, Nachtrag 5: "Der Chat
#: muss immer ueber alles Bescheid wissen") und der Verlaufsmarker fuer
#: mitgehoerte Segmente -- deutsch UND englisch, wie ``SPRECHER``.
BOARD_KOEPFE = ("Das CoThinker-Board", "The CoThinker board")
MITGEHOERT_KOEPFE = ("Was die Gruppe gesagt hat, waehrend du mitgehoert hast",
                     "What the group said while you listened in")
MITGEHOERT_MARKEN = ("mitgehoerte Sprachaufnahme", "voice recording(s) listened in")


def kontextluecken(nutzer: str) -> list[str]:
    """Board/Diskussion fehlt im Kontext (05.10.2026, Birk: live sagte der
    Bot "I can't see what's on the cothinker page" und "only the marker for
    a voice recording, not the words themselves").

    Drei Befunde, alle aus dem Nutzerteil allein: (1) eine Sprachaufnahme
    steht nur als Marker "(sprache)" ohne Wortlaut im Verlauf; (2) der
    Verlauf verweist auf mitgehoerte Aufnahmen, aber der Block mit ihrem
    Wortlaut fehlt (weggekuerzt); (3) im Verlauf ist vom CoThinker die
    Rede, aber der Board-Block fehlt."""
    befunde = []
    zeilen = [z for _, z in inhaltszeilen(nutzer)]
    if any(z.rstrip().endswith(": (sprache)") for z in zeilen):
        befunde.append("Sprachaufnahme nur als Marker '(sprache)', ohne Wortlaut")
    if (any(m in nutzer for m in MITGEHOERT_MARKEN)
            and not any(k in nutzer for k in MITGEHOERT_KOEPFE)):
        befunde.append("Mitgehoertes im Verlauf markiert, Wortlaut-Block fehlt")
    if ("cothinker" in "\n".join(z for z in zeilen if SPRECHER.match(z)).lower()
            and not any(k in nutzer for k in BOARD_KOEPFE)):
        befunde.append("CoThinker im Verlauf erwaehnt, Board-Block fehlt")
    return befunde


def dubletten_quer(nutzer: str) -> list[tuple[str, int]]:
    """Wortgleiche Zeilen im Nutzerteil, ab 20 Zeichen.

    Kuerzer als ``DUBLETTE_AB``, weil hier Verlauf und Zusammenfassungsbloecke
    aneinanderstossen: die Dublette, die am 06.09.2026 wehgetan hat ("dieselbe
    Interview-Zusammenfassung 11x"), war eine Zeile und kein Satz."""
    gezaehlt = Counter(z for _, z in inhaltszeilen(nutzer) if len(z) >= 20)
    return sorted(((z, n) for z, n in gezaehlt.items() if n > 1),
                  key=lambda paar: (-paar[1], paar[0]))


def groessen(tsv) -> dict[str, int]:
    """``pfad -> system_zeichen + nutzer_zeichen`` aus einer ``uebersicht.tsv``.

    Gelesen wird nach **Spaltenname**, nicht nach Position: die neue Uebersicht
    (Task 7) hat mehr Spalten in anderer Ordnung, und ein Vergleich, der an
    Spalte 2 haengt, vergliche dann Phasennummern mit Zeichenzahlen.

    Ohne Pfad oder ohne Datei ein leeres Dict -- dann gilt jeder Dump als neu."""
    if tsv is None:
        return {}
    pfad = Path(tsv)
    if not pfad.exists():
        return {}
    reihen = pfad.read_text(encoding="utf-8").splitlines()
    if not reihen:
        return {}
    kopf = reihen[0].split("\t")
    try:
        i_pfad = kopf.index("pfad")
        i_sys = kopf.index("system_zeichen")
        i_nutz = kopf.index("nutzer_zeichen")
    except ValueError:
        return {}
    ergebnis = {}
    for zeile in reihen[1:]:
        felder = zeile.split("\t")
        if len(felder) <= max(i_pfad, i_sys, i_nutz):
            continue
        try:
            ergebnis[felder[i_pfad]] = int(felder[i_sys]) + int(felder[i_nutz])
        except ValueError:
            continue
    return ergebnis


def bericht(pfad, basis: dict | None = None) -> dict:
    pfad = Path(pfad)
    roh = pfad.read_text(encoding="utf-8")
    system, nutzer = teile(roh)
    lang = [z for z in zeilen(roh) if len(z) >= DUBLETTE_AB]
    vorher = (basis or {}).get(pfad.stem)
    jetzt = len(system) + len(nutzer)
    return {
        "datei": pfad.name,
        "name": pfad.stem,
        "system_zeichen": len(system),
        "nutzer_zeichen": len(nutzer),
        "dubletten": {z: n for z, n in Counter(lang).items() if n > 1},
        "verboten": [w for w in VERBOTEN if w in roh],
        "deutsche_reste": deutsche_reste(roh),
        "ux_muster": verbotene_muster(system),
        "frageregeln": frageregel_zeilen(system),
        "verlauf": verlaufsbefund(nutzer),
        "dubletten_quer": dubletten_quer(nutzer),
        "kontextluecken": kontextluecken(nutzer),
        "delta_zeichen": None if vorher is None else jetzt - vorher,
    }


def mechanik_markdown(berichte: list[dict]) -> str:
    """Ein Abschnitt je Dump. Geht so in ``mechanik.md`` wie nach stdout --
    zwei Formate waeren zwei Wahrheiten."""
    aus = ["# Mechanischer Prompt-Check", ""]
    for b in berichte:
        v = b["verlauf"]
        delta = "neu" if b["delta_zeichen"] is None else f"{b['delta_zeichen']:+d}"
        aus.append(f"## {b['datei']}")
        aus.append(
            f"- Groesse: system={b['system_zeichen']} "
            f"nutzer={b['nutzer_zeichen']} (gegen Basis: {delta})"
        )
        aus.append(
            f"- Verlauf: Zuege={v['zuege']} Bot-Zeilen={v['bot_zeilen']} "
            f"Systemzeilen={v['systemzeilen']} "
            f"Transkript-Echos={v['transkript_echos']} "
            f"Sprecher={', '.join(v['sprecher']) or '-'}"
        )
        for titel, eintraege in (
            ("Deutsche Reste",
             [f"Z{n}: {w} -- {z[:100]}" for n, z, w in b["deutsche_reste"]]),
            ("UX-Muster",
             [f"Z{n}: {m} -- {e}" for n, m, e in b["ux_muster"]]),
            ("Frageregeln (nebeneinander lesen)",
             [f"Z{n}: {z[:110]}" for n, z in b["frageregeln"]]),
            ("Quotenzaehler",
             [f"Z{n}: {z[:110]}" for n, z in v["quoten"]]),
            ("Dubletten im Nutzertext",
             [f"{n}x {z[:110]}" for z, n in b["dubletten_quer"]]),
            ("Dubletten ueber 80 Zeichen",
             [f"{n}x {z[:110]}" for z, n in sorted(
                 b["dubletten"].items(), key=lambda paar: -paar[1])]),
            ("Verbotene Reste", list(b["verboten"])),
            ("Board/Diskussion fehlt im Kontext", list(b.get("kontextluecken", []))),
        ):
            if eintraege:
                aus.append(f"- **{titel}:**")
                aus.extend(f"  - {e}" for e in eintraege)
        aus.append("")
    return "\n".join(aus)


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Prompt-Dumps messen")
    zerleger.add_argument("ordner")
    zerleger.add_argument(
        "--basis",
        default="docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv",
        help="uebersicht.tsv des Vergleichsstands; '-' schaltet den Vergleich aus",
    )
    zerleger.add_argument(
        "--nach", default=None,
        help="Zieldatei des Markdown-Berichts (Vorgabe: <ordner>/mechanik.md)",
    )
    argumente = zerleger.parse_args()

    ordner = Path(argumente.ordner)
    basis = groessen(None if argumente.basis == "-" else argumente.basis)
    berichte = [bericht(p, basis) for p in sorted(ordner.glob("*.txt"))]
    text = mechanik_markdown(berichte)
    ziel = Path(argumente.nach) if argumente.nach else ordner / "mechanik.md"
    ziel.write_text(text + "\n", encoding="utf-8")
    print(text)
    # **Exit 0, immer.** Der Pruefer ist ein Bericht, kein Gate: das Gate ist
    # tests/test_modellaufrufe_inventar.py in der Suite plus die Pass-Regel im
    # END-Template (docs/flow-audit/vorlagen.md, Task 11). Ein Exit-Code, der
    # an einer Zaehlung haengt, macht aus jeder neuen Prompt-Zeile einen roten
    # Lauf -- und dann schaltet ihn jemand ab.


if __name__ == "__main__":
    main()

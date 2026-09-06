"""Phase 2: die Fragenauswahl, die Sensibilitaetspruefung, der Leitfaden.

Der Bot schlaegt zehn Fragen vor, die Gruppe nimmt genau drei; darauf folgen
die weichen Fassungen der heiklen Fragen und Eroeffnung samt Abschluss.
Daraus baut ``leitfaden.py`` deterministisch den Gespraechsleitfaden.

Die Toggle-Auswahl per Knopf (``ART_FRAGE_WAHL``) ist seit dem 06.09.2026
stillgelegt -- sie funktionierte am Telefon nicht; genommen wird jetzt ueber
Nummern im Text (``lies_fragennummern``).
"""

import re

from interview_theater import repo

from interview_theater.knoepfe.texte import (
    ANWEISUNG_EINLEITUNGEN, ANWEISUNG_EROEFFNUNG, ART_FRAGEN_ANDERE,
    ART_FRAGEN_EIGENE, ART_FRAGEN_UEBERNEHMEN, ART_FRAGE_WAHL, ART_LEITFADEN,
    FRAGEN_ANZAHL, FRAGEN_ZUR_WAHL, KNOPF_LAENGE, TEXT_ARBEIT_EROEFFNUNG,
    TEXT_ARBEIT_SENSIBILITAET, TEXT_PRUEFUNG_LAEUFT, _HAKEN,
    _TEXT_FRAGEN_ANDERE_KNOPF, _TEXT_FRAGEN_EIGENE_KNOPF,
    _TEXT_FRAGEN_KEINE_AUSWAHL, _TEXT_FRAGEN_NOTIERT,
    _TEXT_FRAGEN_NUMMERN_FALSCH, _TEXT_FRAGEN_UEBERNOMMEN, _TEXT_FRAGEN_WAHL,
    _TEXT_LEITFADEN_KNOPF,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _nimm_alte_leiste_ab, _starte_auftrag, offene_art,
)


# --- Phase 2: die Fragen als Mehrfachauswahl ------------------------------


def _gewaehlte(conn, chat_id: int) -> list[int]:
    """Die angetippten Fragennummern, aufsteigend."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_gewaehlt"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    return sorted(int(t) for t in roh.split(",") if t.strip().isdigit())


def _auswahlfragen(conn, chat_id: int) -> list[str]:
    """Die zur Wahl stehenden Fragen, eine je Zeile."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_auswahl"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    from interview_theater import vorschlag

    return vorschlag.zeilen(roh)


def _knopftext(nummer: int, frage: str, gewaehlt: bool) -> str:
    """Die Beschriftung einer Fragenzeile: Haken, Nummer, gekuerzte Frage.

    Gekuerzt wird sichtbar (mit '…'), nicht still: eine Beschriftung, die
    Telegram selbst abschneidet, sieht auf dem Telefon aus wie ein Fehler
    des Bots."""
    kurz = frage if len(frage) <= KNOPF_LAENGE else frage[: KNOPF_LAENGE - 1].rstrip() + "…"
    return f"{_HAKEN if gewaehlt else ''}{nummer}. {kurz}"


def _fragenleiste(conn, chat_id: int) -> list[tuple[str, str]]:
    """Die Leiste unter dem Zehnervorschlag -- seit dem 06.09.2026 (10:05,
    Birk) nur noch **zwei** Knoepfe: "Eigene Idee" und "Andere zehn".

    **Die zehn Toggle-Knoepfe sind weg.** Sie funktionierten am Telefon
    nicht: "sobald ich auf eine Frage klicke, verschwindet das Menue" -- im
    Log ein ``editMessageReplyMarkup``, das die Nachricht auf dem Geraet der
    Gruppe ersetzte statt sie zu ergaenzen. Ein Bedienelement, das auf dem
    Geraet der Gruppe verschwindet, ist schlechter als gar keins. Gewaehlt
    wird jetzt per Nummer im Text oder in der Sprachnachricht
    (``nimm_fragennummern``).

    ``ART_FRAGE_WAHL`` und ``ART_FRAGEN_UEBERNEHMEN`` bleiben im Code, damit
    ein Knopf aus einer alten Nachricht nicht ins Leere laeuft -- angeboten
    werden sie nicht mehr."""
    return [
        (
            _TEXT_FRAGEN_EIGENE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_EIGENE, None)),
        ),
        (
            _TEXT_FRAGEN_ANDERE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_ANDERE, None)),
        ),
    ]


def fragenliste(conn, chat_id: int) -> str:
    """Die zehn Fragen ausgeschrieben und nummeriert, eine je Zeile.

    Ausgeschrieben und nicht gekuerzt (``_knopftext`` kuerzte auf 40
    Zeichen): eine Frage, die eine Sechzehnjaehrige einer fremden Person
    stellen soll, muss sie ganz lesen koennen, bevor sie sie waehlt."""
    return "\n".join(
        f"{nummer}. {frage}"
        for nummer, frage in enumerate(_auswahlfragen(conn, chat_id), start=1)
    )


def biete_fragenauswahl(conn, tg, chat_id: int, wert: str, text: str | None = None) -> int:
    """Stellt die zehn vorgeschlagenen Fragen hin -- **ausgeschrieben, als
    EINE Nachricht** (06.09.2026, 10:05, Birk).

    ``wert`` ist der Inhalt des Blocks ``VORSCHLAG FRAGENAUSWAHL:`` -- eine
    Frage je Zeile. Er wird als ``arbeitsstand.fragen_auswahl`` abgelegt,
    **bevor** die Nachricht rausgeht: die Gruppe antwortet mit Nummern, und
    eine Nummer ohne Liste waere nichts wert.

    Darunter nur zwei Knoepfe ("Eigene Idee", "Andere zehn"). Gewaehlt wird
    per Nummer im Chat -- der Weg ist ``nimm_fragennummern``, aufgerufen aus
    ``ablauf.antworte``.

    Liefert die ``message_id``."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGE_WAHL)
    for art in (ART_FRAGEN_UEBERNEHMEN, ART_FRAGEN_ANDERE, ART_FRAGEN_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", wert)
    leiste = _fragenleiste(conn, chat_id)
    vorspann = (text or "").strip()
    nachricht = "\n\n".join(
        teil for teil in (vorspann, fragenliste(conn, chat_id), _TEXT_FRAGEN_WAHL)
        if teil
    )
    message_id = tg.sende_mit_knoepfen(chat_id, nachricht, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id
    )
    return message_id


#: Ordinalwoerter, mit denen eine Gruppe eine Frage benennt ("die zweite,
#: fuenfte und neunte"). Sie stehen als Daten und nicht als Sonderfall im
#: Code -- eine elfte Frage braucht nichts als eine Zeile hier.
_ORDINALWOERTER = {
    "erste": 1, "zweite": 2, "dritte": 3, "vierte": 4, "fuenfte": 5,
    "sechste": 6, "siebte": 7, "siebente": 7, "achte": 8, "neunte": 9,
    "zehnte": 10,
}


def lies_fragennummern(text: str) -> list[int]:
    """Die genannten Fragennummern aus einem Satz, in der Reihenfolge des
    ersten Auftretens und ohne Dubletten.

    Versteht Ziffern ("2, 5 und 9", "1 3 7", "2,5,9") und Ordinalwoerter
    ("die zweite, fuenfte und neunte" -- mit und ohne Umlaut, weil Whisper
    beides liefert). Zahlen ausserhalb 1..``FRAGEN_ZUR_WAHL`` fallen weg:
    eine 47 ist keine Frage, sondern eine Jahreszahl.

    Rein deterministisch, kein Modellaufruf -- der Aufrufer entscheidet, ob
    die Zahl der Nummern stimmt."""
    gefaltet = (
        (text or "").lower()
        .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        .replace("ß", "ss")
    )
    gefunden: list[int] = []

    def merke(nummer: int) -> None:
        if 1 <= nummer <= FRAGEN_ZUR_WAHL and nummer not in gefunden:
            gefunden.append(nummer)

    for treffer in re.finditer(r"\d+|[a-z]+", gefaltet):
        stueck = treffer.group()
        if stueck.isdigit():
            merke(int(stueck))
        elif stueck in _ORDINALWOERTER:
            merke(_ORDINALWOERTER[stueck])
    return gefunden


def nimm_fragennummern(conn, tg, klm, e, chat_id: int, text: str) -> bool:
    """Die Gruppe hat Nummern gesagt: die drei Fragen werden zur Frageliste.

    Liefert ``True``, wenn die Nachricht als Auswahl verstanden wurde -- dann
    geht sie NICHT zusaetzlich in den Gespraechszug. ``False`` heisst
    "war keine Auswahl", und der normale Weg laeuft weiter (der Erkenner
    liest freie Fragen weiterhin als ``fragen_setzen``).

    **Greift nur, solange der Zehnervorschlag offen ist** (``offene_art`` ==
    "fragen" und eine Auswahlliste steht): sonst wuerde jede Nachricht mit
    einer Zahl darin eine Frageliste ueberschreiben.

    Kein Modellaufruf hier; die Sensibilitaetspruefung laeuft danach im
    eigenen Thread (dieselbe Kette wie nach dem alten Knopf)."""
    if offene_art(conn, chat_id) != "fragen":
        return False
    fragen = _auswahlfragen(conn, chat_id)
    if not fragen:
        return False
    nummern = lies_fragennummern(text)
    if not nummern:
        return False
    if len(nummern) != FRAGEN_ANZAHL:
        tg.sende(chat_id, _TEXT_FRAGEN_NUMMERN_FALSCH)
        return True
    ausgewaehlt = [fragen[n - 1] for n in nummern if n <= len(fragen)]
    if len(ausgewaehlt) != FRAGEN_ANZAHL:
        tg.sende(chat_id, _TEXT_FRAGEN_KEINE_AUSWAHL)
        return True
    return _uebernimm_fragen(
        conn, tg, klm, e, chat_id, ausgewaehlt, nummern=nummern,
    ) is not None


def _uebernimm_fragen(conn, tg, klm, e, chat_id: int, ausgewaehlt: list[str],
                      nummern: list[int] | None = None) -> str:
    """Die gewaehlten Fragen werden zur Frageliste, und danach laeuft die
    Sensibilitaetspruefung an.

    Ein Weg fuer beide Quellen -- die gesagten Nummern (der Regelweg seit
    dem 06.09.2026) und den alten Knopf aus einer bereits verschickten
    Nachricht."""
    wert = "\n".join(ausgewaehlt)
    repo.setze_arbeitsstand(conn, chat_id, "fragen", wert)
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    # Die Auswahl ist getroffen -- alte Leisten kommen weg (06.09.2026, im
    # Regie-Lauf gemessen). Vorher blieben sie haengen: die Regie beschwerte
    # sich VIERMAL ("die knoepfe mit den zehn fragen sind immer noch da").
    for art in (ART_FRAGE_WAHL, ART_FRAGEN_UEBERNEHMEN, ART_FRAGEN_ANDERE,
                ART_FRAGEN_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Fragen: {wert}", quelle="knopf",
    )
    kopf = (
        _TEXT_FRAGEN_NOTIERT.format(nummern=", ".join(str(n) for n in nummern))
        if nummern
        else _TEXT_FRAGEN_UEBERNOMMEN.format(anzahl=len(ausgewaehlt))
    )
    tg.sende(
        chat_id,
        kopf + "\n" + "\n".join(
            f"{n}. {f}" for n, f in enumerate(ausgewaehlt, start=1)
        ),
    )
    starte_sensibilitaetspruefung(conn, tg, klm, e, chat_id)
    return "Fragen uebernommen"


def starte_sensibilitaetspruefung(conn, tg, klm, e, chat_id: int) -> bool:
    """Die Pruefung nach dem Festlegen der Fragen (06.09.2026, Birk).

    **Warum sie automatisch laeuft.** Die Interviews fuehren 15- bis
    18-Jaehrige mit FREMDEN Personen auf der Strasse und im Verein. Eine
    Frage nach Familie, Herkunft, Religion, Gewalt, Liebe, Geld, Krankheit,
    Flucht oder Diskriminierung ist dabei kein Problem -- sie ohne einen Satz
    davor zu stellen, schon. Wer erst danach merkt, dass ein Satz gefehlt
    haette, kann ihn nicht mehr nachreichen.

    Ein Gespraechszug mit Anweisung in einem eigenen Thread
    (``ablauf.starte_auftrag``) -- **kein Modellaufruf in diesem Handler**
    (AGENTS.md, Zusage 2). Die Antwort traegt den Block
    ``VORSCHLAG EINLEITUNGEN:`` und darunter die Grundleiste; das Ping-Pong
    laeuft wie bei jedem anderen Vorschlag, bis die Gruppe
    \"Gefaellt uns, weiter\" drueckt.
    """
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = (stand["fragen"] if stand else "") or ""
    if not fragen.strip():
        return False
    tg.sende(chat_id, TEXT_PRUEFUNG_LAEUFT)
    return _starte_auftrag(
        conn, tg, klm, e, chat_id, ANWEISUNG_EINLEITUNGEN.format(fragen=fragen),
        arbeitszeile=TEXT_ARBEIT_SENSIBILITAET,
    )


def starte_eroeffnung(conn, tg, klm, e, chat_id: int) -> bool:
    """Der zweite Schritt der Verfeinerung: Eroeffnungs- und Abschlusstext.

    Laeuft automatisch, sobald die Einleitungen abgenommen sind -- die
    Gruppe soll nicht wissen muessen, dass es diesen Schritt gibt. Wieder
    ein Auftragszug im eigenen Thread, wieder die Grundleiste darunter."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = (stand["fragen"] if stand else "") or ""
    return _starte_auftrag(
        conn, tg, klm, e, chat_id, ANWEISUNG_EROEFFNUNG.format(fragen=fragen),
        arbeitszeile=TEXT_ARBEIT_EROEFFNUNG,
    )


def _speichere_eroeffnung(conn, tg, chat_id: int, wert: str) -> str:
    """Zerlegt den Block ``VORSCHLAG EROEFFNUNG:`` in Eroeffnung und
    Abschluss und legt beides ab.

    Der Block traegt beides, weil es EINE Entscheidung ist (\"womit fangen
    wir an, womit hoeren wir auf\") -- gespeichert wird es getrennt, weil der
    Leitfaden die beiden Texte an verschiedene Stellen setzt. Die Trennung
    laeuft ueber eine Zeile, die mit \"Abschluss\" beginnt; fehlt sie, ist
    alles Eroeffnung und der Abschluss bleibt leer (der Leitfaden laesst ihn
    dann weg, statt etwas zu erfinden).
    """
    eroeffnung: list[str] = []
    abschluss: list[str] = []
    ziel = eroeffnung
    for zeile in (wert or "").splitlines():
        roh = zeile.strip()
        if not roh:
            continue
        ohne = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", roh)
        kopf, sep, rest = ohne.partition(":")
        if sep and kopf.strip().lower().startswith("abschluss"):
            ziel = abschluss
            if rest.strip():
                ziel.append(rest.strip())
            continue
        if sep and kopf.strip().lower().startswith("eroeffnung"):
            ziel = eroeffnung
            if rest.strip():
                ziel.append(rest.strip())
            continue
        ziel.append(ohne)
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung", "\n".join(eroeffnung).strip() or None
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", "\n".join(abschluss).strip() or None
    )
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", "Eroeffnung und Abschluss festgelegt",
        quelle="knopf",
    )
    # Und jetzt steht der Leitfaden -- die Gruppe soll ihn sehen, ohne
    # danach fragen zu muessen.
    from interview_theater import leitfaden

    # ``sende_einmal`` und nicht ``sende``: derselbe Merkposten wie beim
    # Schritt in die Interviews (``_eintrittstext``, ``befehle`` beim ersten
    # Interviewstart). Vorher stand er zweimal wortgleich im Chat -- einmal
    # hier, wenige Nachrichten spaeter noch einmal beim Phasenwechsel
    # (gemessen 06.09., Lauf tag1-gruppe1). Der Leitfaden ist lang; zweimal
    # hintereinander schiebt er alles andere aus dem Bild.
    leitfaden.sende_einmal(conn, tg, chat_id)
    # **Die Kette bricht hier nicht ab** (06.09.2026, 10:25, Birk): mit
    # Eroeffnung und Abschluss ist Phase 2 fertig, also kommt sofort die
    # Abschlussnachricht mit "Weiter zu Interviews". Vorher stand nach dem
    # letzten "Gefaellt uns, weiter" nichts mehr da, und die Gruppe wartete
    # auf einen Schritt, den niemand mehr machte.
    from interview_theater.knoepfe.stationen import biete_phase_proaktiv

    biete_phase_proaktiv(conn, tg, chat_id)
    return "Eroeffnung uebernommen"


def _leitfaden_knopf(conn, chat_id: int) -> tuple[str, str] | None:
    """\"Leitfaden zeigen\", sobald es einen gibt -- sonst None."""
    from interview_theater import leitfaden

    if not leitfaden.steht(conn, chat_id):
        return None
    return (
        _TEXT_LEITFADEN_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_LEITFADEN, None)),
    )


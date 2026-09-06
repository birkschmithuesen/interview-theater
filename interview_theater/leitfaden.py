"""Der Interview-Gespraechsleitfaden -- deterministisch aus dem Arbeitsstand
zusammengebaut (06.09.2026, Birk).

**Warum es das gibt.** Zwischen "die Fragen stehen" und "geht raus und
befragt fremde Menschen" fehlte ein Schritt. Die Gruppe sind junge Frauen
zwischen 15 und 18; sie sprechen auf der Strasse oder im Verein Personen an,
die sie nicht kennen. Eine Frageliste allein ist dafuer zu wenig: es fehlt,
womit man anfaengt (wer wir sind, wofuer das ist, dass man jederzeit aufhoeren
kann), was man vor einer heiklen Frage sagt, und womit man aufhoert.

Deshalb drei Schritte am Ende der Phase 2 -- Sensibilitaetspruefung mit
Einleitungsvorschlaegen, dann Eroeffnung und Abschluss -- und daraus **ein**
Text, den die Gruppe mitnimmt.

**Kein Modellaufruf.** ``baue`` setzt nur zusammen, was die Gruppe schon
abgenommen hat (``arbeitsstand.fragen``, ``frage_einleitungen``,
``interview_eroeffnung``, ``interview_abschluss``). Der Leitfaden ist damit
jederzeit und beliebig oft abrufbar -- per Knopf, per ``/leitfaden``, auf der
Gruppenseite --, ohne dass ein Aufruf bezahlt oder gewartet wird. Er darf sich
zwischen zwei Abrufen auch nicht unterscheiden: was auf dem Telefon steht,
waehrend die Gruppe im Raum steht, ist der Text, mit dem sie losgeht.

**Die Zuordnung Einleitung -> Frage laeuft ueber die Nummer**, nicht ueber
Textaehnlichkeit: der Vorschlagsblock schreibt ``2 — <Einleitung>``, und 2
ist die zweite Zeile der Frageliste. Raten waere hier derselbe Fehler wie in
``vorschlag.py``: lieber eine Frage ohne Einleitung als eine Einleitung vor
der falschen Frage.
"""

import re

from interview_theater import repo

#: Was ueber dem Leitfaden steht, wenn der Bot ihn von sich aus schickt --
#: einmal beim Interviewstart, danach nur auf Nachfrage.
TEXT_KOPF = "Euer Leitfaden fuers Interview:"

#: Die Ueberschriften im Text. Als Konstanten, damit Test und Web denselben
#: Wortlaut pruefen koennen, ohne ihn abzuschreiben.
UEBERSCHRIFT_EROEFFNUNG = "So fangt ihr an:"
UEBERSCHRIFT_FRAGEN = "Eure Fragen:"
UEBERSCHRIFT_ABSCHLUSS = "So hoert ihr auf:"

#: Solange nichts dasteht. Kein Platzhalter-Leitfaden: ein halber Leitfaden
#: waere schlimmer als gar keiner, weil die Gruppe mit ihm losginge.
TEXT_LEER = (
    "Einen Leitfaden habe ich noch nicht - dafuer brauche ich zuerst eure "
    "Fragen."
)

#: Die Zeile vor einer Frage, wenn es eine Einleitung dazu gibt. Der Pfeil
#: sagt der Interviewerin: das sagst du VOR der Frage.
_EINLEITUNG_ZEILE = "   ↳ vorher sagen: {text}"

#: Die Kern-Zeile unter einer weich gefassten Frage (06.09.2026, 10:18,
#: Birk). Im Leitfaden steht oben, was die Interviewerin SAGT -- ein
#: Gespraechsstueck, kein Behoerdensatz --, und darunter in Klammern, worum
#: es dabei geht. Ohne die Kern-Zeile wuesste eine Interviewerin, die im
#: Gespraech abkommt, nicht mehr, was sie eigentlich fragen wollte.
_KERN_ZEILE = "   (Kern: {text})"

#: Wie eine Einleitungszeile im Vorschlagsblock aussieht: ``2 — <Text>``.
#: Gedankenstrich wie ueberall, der einfache Bindestrich mit Leerzeichen und
#: der Doppelpunkt zusaetzlich -- Modelle liefern alle drei.
_EINLEITUNG = re.compile(r"^\s*(\d{1,2})\s*(?:[—–-]|:)\s*(.+)$")

#: Fuehrende Aufzaehlungszeichen und Nummern einer Fragezeile ("1. ", "- ").
_AUFZAEHLUNG = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


def fragen(wert: str | None) -> list[str]:
    """Die Frageliste als Zeilen -- dieselbe Zerlegung wie auf der
    Weboberflaeche (``web._fragen_html``): Zeilenumbruch oder ``" | "``.

    Der Erkenner speichert die Fragen als EINEN String, und wie er ihn
    trennt, haengt daran, was das Modell geliefert hat. Beide Formen hier
    zu kennen ist billiger, als sie beim Speichern zu normalisieren -- der
    gespeicherte Wert ist der, den die Gruppe im Chat gelesen hat.
    """
    if not (wert or "").strip():
        return []
    teile = [_AUFZAEHLUNG.sub("", t).strip() for t in re.split(r"\n+| \| ", wert or "")]
    return [t for t in teile if t]


def einleitungen(wert: str | None) -> dict[int, str]:
    """Die Einleitungen als ``{Fragennummer: Text}``.

    Zeilen ohne fuehrende Nummer fallen raus -- dazu gehoert ausdruecklich
    auch die Leerfall-Zeile ("Keine der Fragen braucht eine besondere
    Einleitung."): sie ist eine Antwort an die Gruppe, kein Eintrag.
    """
    ergebnis: dict[int, str] = {}
    for zeile in (wert or "").splitlines():
        treffer = _EINLEITUNG.match(zeile)
        if treffer is None:
            continue
        text = treffer.group(2).strip()
        if text:
            ergebnis[int(treffer.group(1))] = text
    return ergebnis


def bausteine(felder: dict) -> dict | None:
    """Die Bestandteile des Leitfadens -- oder None, wenn es keinen gibt.

    ``{"eroeffnung": str, "fragen": [{"nummer", "text", "kern",
    "einleitung"}], "abschluss": str}``. ``text`` ist das, was die
    Interviewerin **sagt**; ``kern`` steht nur bei einer weich gefassten
    Frage darunter (worum es dabei geht), ``einleitung`` nur bei einer
    Frage ohne weiche Fassung (was sie vorher sagt) -- die beiden schliessen
    sich aus, so wie im Chattext.

    **Ein Zusammenbau, drei Aufrufer** (06.09.2026): ``aus_feldern`` setzt
    daraus den Chattext, die Gruppenseite zeigt denselben Text, und die
    Leitfaden-Route ``/g/<token>/leitfaden`` setzt daraus die grosse
    Handy-Ansicht. Die Route baut damit **nicht** ihre eigene Wahrheit -- sie
    setzt dieselben Stuecke nur anders."""
    def feld(name: str) -> str:
        return ((felder.get(name) or "") if felder else "").strip()

    liste = fragen(feld("fragen"))
    if not liste:
        return None

    vorher = einleitungen(feld("frage_einleitungen"))
    # Die weichen Fassungen liegen in derselben Form wie die Einleitungen vor
    # (``<Nummer> — <Text>``) und werden mit demselben Leser gelesen: es gibt
    # einen nummerierten Zeilenblock in diesem Projekt, nicht zwei.
    weich = einleitungen(feld("fragen_weich"))
    eintraege = []
    for nummer, frage in enumerate(liste, start=1):
        # **Die weiche Fassung ist der Text, den die Gruppe spricht**
        # (06.09.2026, 10:18): sie ersetzt die Aneinanderreihung von
        # Einleitung und Frage, ist also KEINE zusaetzliche Zeile. Gibt es
        # keine, steht die Frage selbst da -- eine nicht-sensible Frage
        # braucht keine Umformulierung.
        if nummer in weich:
            eintraege.append(
                {"nummer": nummer, "text": weich[nummer], "kern": frage,
                 "einleitung": ""}
            )
            continue
        eintraege.append(
            {"nummer": nummer, "text": frage, "kern": "",
             "einleitung": vorher.get(nummer, "")}
        )
    return {
        "eroeffnung": feld("interview_eroeffnung"),
        "fragen": eintraege,
        "abschluss": feld("interview_abschluss"),
    }


def aus_feldern(felder: dict) -> str:
    """Der Leitfaden aus einem Dict statt aus der Datenbank -- die reine
    Funktion hinter ``baue``.

    Gebraucht von der Weboberflaeche (``web_daten._arbeitsstand`` liefert
    ein Dict aus einer read-only geoeffneten Verbindung): sie darf ``repo``
    nicht anfassen, weil das dessen modulweiten Schreib-Lock in den
    Webprozess zoege (AGENTS.md). Ein Text, zwei Aufrufer, eine
    Zusammenbau-Regel.
    """
    teil = bausteine(felder)
    if teil is None:
        return TEXT_LEER

    teile: list[str] = []
    if teil["eroeffnung"]:
        teile.append(f"{UEBERSCHRIFT_EROEFFNUNG}\n{teil['eroeffnung']}")

    zeilen = [UEBERSCHRIFT_FRAGEN]
    for frage in teil["fragen"]:
        zeilen.append(f"{frage['nummer']}. {frage['text']}")
        if frage["kern"]:
            zeilen.append(_KERN_ZEILE.format(text=frage["kern"]))
        elif frage["einleitung"]:
            zeilen.append(_EINLEITUNG_ZEILE.format(text=frage["einleitung"]))
    teile.append("\n".join(zeilen))

    if teil["abschluss"]:
        teile.append(f"{UEBERSCHRIFT_ABSCHLUSS}\n{teil['abschluss']}")
    return "\n\n".join(teile)


def baue(conn, chat_id: int) -> str:
    """Der vollstaendige Leitfaden als Text: Eroeffnung, Fragen mit ihren
    Einleitungen, Abschluss.

    Ohne Fragen gibt es keinen Leitfaden (``TEXT_LEER``) -- die Fragen sind
    sein Skelett. Eroeffnung, Einleitungen und Abschluss sind einzeln
    optional: eine Gruppe, die keine sensible Frage hat, bekommt trotzdem
    einen Leitfaden, und eine, die noch keine Eroeffnung abgenommen hat,
    sieht schon einmal ihre Fragen.
    """
    stand = repo.hole_arbeitsstand(conn, chat_id)

    def feld(name: str) -> str:
        try:
            return (stand[name] or "").strip() if stand else ""
        except (IndexError, KeyError):  # Spalte fehlt noch (alte Datenbank)
            return ""

    return aus_feldern(
        {
            name: feld(name)
            for name in (
                "fragen", "frage_einleitungen", "fragen_weich",
                "interview_eroeffnung", "interview_abschluss",
            )
        }
    )


def steht(conn, chat_id: int) -> bool:
    """Gibt es ueberhaupt einen Leitfaden? Rein aus den Daten, ohne den Text
    zu bauen -- fuer Knopfleisten, die nur wissen muessen, ob sie ihn
    anbieten duerfen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        return bool(stand and (stand["fragen"] or "").strip())
    except (IndexError, KeyError):
        return False


#: Der Pfad der Leitfaden-Ansicht unter der Gruppenseite -- eine Stelle,
#: gelesen vom Webserver (Routing) und vom Bot (Link im Chat).
WEB_PFAD = "leitfaden"

#: Die Zeile unter dem Leitfaden im Chat (06.09.2026). Sie kommt
#: **zusaetzlich** zum bestehenden Text: der bleibt, weil eine Gruppe ohne
#: Netz im Probenraum sonst nichts mehr haette. Sie steht da, weil genau
#: dieses Dokument eine Sechzehnjaehrige in der Hand haelt, wenn sie eine
#: fremde Person anspricht -- und im Chat versinkt es nach zehn Nachrichten.
TEXT_WEBLINK = "Gross und zum Ausdrucken: {url}"


def weblink(conn, chat_id: int, e=None) -> str | None:
    """Die URL der Leitfaden-Ansicht dieser Gruppe, oder None ohne Basis-URL
    bzw. ohne Web-Token -- dieselbe Regel wie ``repo.gruppenseite_url``."""
    from interview_theater import repo

    basis = repo.gruppenseite_url(conn, chat_id, getattr(e, "web_url", "") or "")
    return f"{basis}/{WEB_PFAD}" if basis else None


def sende(conn, tg, chat_id: int, mit_kopf: bool = True, e=None) -> int | None:
    """Schickt den Leitfaden in den Chat. Liefert die ``message_id`` oder
    None, wenn es nichts zu schicken gab.

    Eine Nachricht, nicht zwei: der Kopf steht im selben Text wie der
    Leitfaden, damit die Gruppe ihn als EINE Nachricht weiterleiten oder
    anheften kann. Unter dem Text steht seit dem 06.09.2026 der Link auf die
    grosse Handy-Ansicht (``TEXT_WEBLINK``) -- **zusaetzlich**, der Chattext
    bleibt unveraendert.
    """
    text = baue(conn, chat_id)
    if text == TEXT_LEER:
        return tg.sende(chat_id, TEXT_LEER)
    if mit_kopf:
        text = f"{TEXT_KOPF}\n\n{text}"
    url = weblink(conn, chat_id, e)
    if url:
        text = f"{text}\n\n{TEXT_WEBLINK.format(url=url)}"
    return tg.sende(chat_id, text)


def sende_einmal(conn, tg, chat_id: int, e=None) -> int | None:
    """Schickt den Leitfaden **einmal je Gruppe** -- beim Schritt in die
    Interviews und beim Interviewstart, danach nie wieder von selbst
    (06.09.2026, Birk).

    Der Merkposten sitzt im Journal (``leitfaden_gezeigt``) und nicht in
    einer neuen Spalte: es ist ein Ereignis, kein Zustand, und das Journal
    wird ohnehin nur angehaengt. Danach bleibt der Leitfaden ueber den Knopf,
    ``/leitfaden`` und die Gruppenseite erreichbar -- gezeigt wird er nur
    nicht mehr ungefragt, sonst staende er vor jedem Interview noch einmal
    im Chat und schoebe das Transkript weg.
    """
    if not steht(conn, chat_id):
        return None
    if _schon_gezeigt(conn, chat_id):
        return None
    message_id = sende(conn, tg, chat_id, e=e)
    repo.schreibe_journal(
        conn, chat_id, "notiert", JOURNAL_GEZEIGT, quelle="leitfaden",
    )
    return message_id


#: Der Journaltext, an dem "schon einmal gezeigt" haengt.
JOURNAL_GEZEIGT = "Leitfaden gezeigt"


def _schon_gezeigt(conn, chat_id: int) -> bool:
    return any(
        (eintrag["text"] or "") == JOURNAL_GEZEIGT
        for eintrag in repo.journal(conn, chat_id)
    )

"""Neun Slash-Befehle als Notausgang (teil-b.md Aufgabe 6, plus ``/szene``,
``/phase`` und ``/figur``).

Der Absichtserkenner (``erkenner.py``) ist der Hauptweg: gemessen 0
Falsch-Positive bei 25 Negativfaellen, 30/30 Treffer. Diese Befehle sind der
Notausgang, wenn er trotzdem danebenliegt oder die Gruppe es lieber explizit
macht -- **neun, nicht fuenfzehn** (SPEC-Reduktion nach dem ersten
Workshoptag; ``/szene`` kam mit den Szenentexten dazu, ``/phase`` und
``/figur`` mit den Arbeitsphasen und dem weichen Loeschen).

``behandle()`` wird in ``ablauf.antworte`` VOR dem Kontextaufbau aufgerufen:
ein erkannter Befehl loest KEINEN Gespraechszug aus (kann also nicht am
Gespraechsmodell scheitern) und wird direkt beantwortet. Ein unbekannter
Befehl bekommt eine freundliche Zeile statt zu krachen -- ``behandle()``
liefert in beiden Faellen ``True``.

**Die Ausnahme, benannt:** ``/szene`` braucht ein Sprachmodell, deshalb nimmt
``behandle()`` seit heute ein optionales ``klm`` entgegen. Die urspruengliche
strukturelle Garantie ("behandle nimmt kein LLM-Objekt, also kann /stand
nicht am Modell scheitern") ist damit eine Zusage geworden, die der Code
weiterhin einhaelt: kein Befehl ruft synchron ein Modell: ``/szene`` gibt den
Aufruf sofort an einen eigenen Thread ab (``szene.starte``) und kehrt zurueck.
Wer hier einen weiteren Befehl anhaengt, halte sich daran.

Telegram haengt in Gruppen mit mehreren Bots oft den Benutzernamen an einen
Befehl an (``/stand@interview_theaterbot``) -- ``_zerlege`` trennt das
grosszuegig ab, unabhaengig davon, welcher Name genau dahintersteht."""

import logging
import re

from interview_theater import erkenner, phasen, repo, szene

#: Woerter, die einen Befehl zu einer Entfernung machen (NACHTRAG N3).
#: Grosszuegig, weil die Gruppe tippt, was ihr einfaellt -- aber eine feste
#: Liste, kein Freitext: "/szene 2 kuerzer" ist ein Schreibauftrag.
_ENTFERNEN_WOERTER = {"entfernen", "entferne", "loeschen", "löschen", "weg", "raus"}

#: "/szene 2 entfernen" -- Nummer, dann ein Entfernungswort, sonst nichts.
_SZENE_ENTFERNEN = re.compile(
    r"^(?:szene\s*)?(\d{1,3})\s+(?:" + "|".join(_ENTFERNEN_WOERTER) + r")\.?$",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)

_TEXT_INTERVIEW_AN = "Ich zeichne jetzt auf."
_TEXT_INTERVIEW_AUS = "Aufnahme beendet."
_TEXT_KERNTHEMA_LEER = "Schreibt das Kernthema hinter den Befehl, zum Beispiel: /kernthema Ankommen"
_TEXT_UNBEKANNT = "Diesen Befehl kenne ich nicht. /hilfe zeigt, was ich verstehe."
_TEXT_WORTLAUT_AUS = "Wortlaut aus."
_TEXT_PHASE_UMSCHALTEN = "Umschalten mit /phase 5 oder /phase Figuren - auch zurueck."
_TEXT_FIGUR_HILFE = (
    "So nehme ich eine Figur weg: /figur Peter entfernen. "
    "Anlegen koennt ihr Figuren einfach im Gespraech."
)
_TEXT_PHASE_UNBEKANNT = "Diese Phase kenne ich nicht. Ich habe diese acht:"
_TEXT_KEINE_AUFNAHMEN = "Es gibt noch keine Aufnahmen."
_TEXT_SZENE_LEER = (
    "Schreibt den Auftrag hinter den Befehl, zum Beispiel: "
    "/szene Szene 2: Maria kommt am Bahnhof an und trifft Elif"
)
#: Nur erreichbar, wenn ein Aufrufer ``behandle()`` ohne ``klm`` benutzt --
#: ein Programmierfehler, aber einer, der die Gruppe nicht ratlos lassen soll.
_TEXT_SZENE_UNMOEGLICH = "Ich kann gerade keine Szene schreiben."

#: Wortidentisch mit der Begruessung aus bot.erstkontakt (teil-b.md Aufgabe
#: 7) in den ersten beiden Absaetzen -- /hilfe ist das jederzeit abrufbare
#: Gegenstueck zur einmaligen Begruessung, beide erklaeren dasselbe (dass
#: der Bot auf alles antwortet, wie Interviews laufen) in derselben
#: Reihenfolge und mit denselben Worten, damit sich niemand an zwei
#: widerspruechliche Erklaerungen erinnern muss.
_TEXT_HILFE = (
    "Schreibt oder sprecht einfach - ich lese alles mit und antworte.\n\n"
    "So laufen Interviews: sagt \"wir machen jetzt ein Interview\", dann "
    "zeichne ich auf. \"Fertig\" beendet es.\n\n"
    "Befehle, falls ich mal danebenliege:\n"
    "/interview - Aufnahme starten\n"
    "/fertig - Aufnahme beenden\n"
    "/phase [nummer|name] - zeigt die Phase oder schaltet um\n"
    "/kernthema <text|aus> - Kernthema setzen, korrigieren oder wegnehmen\n"
    "/figur <name> entfernen - eine Figur wegnehmen\n"
    "/szene <auftrag> - eine Szene ausschreiben lassen\n"
    "/szene <nummer> entfernen - eine Szene wegnehmen\n"
    "/stand - zeigt, was ich mir bisher gemerkt habe\n"
    "/wortlaut [name|aus] - Originaltranskripte mitlesen\n"
    "/hilfe - diese Uebersicht"
)

#: Telegram-Nutzlast fuer setMyCommands (teil-b.md Aufgabe 6) -- ohne
#: fuehrenden Schraegstrich, Telegram haengt ihn selbst an. Dieselben neun
#: Befehle wie in behandle(), in derselben Reihenfolge wie in _TEXT_HILFE.
BEFEHLE_LISTE = [
    {"command": "interview", "description": "Aufnahme starten"},
    {"command": "fertig", "description": "Aufnahme beenden"},
    {"command": "phase", "description": "Arbeitsphase zeigen oder umschalten"},
    {"command": "kernthema", "description": "Kernthema setzen, korrigieren oder wegnehmen"},
    {"command": "figur", "description": "Eine Figur entfernen"},
    {"command": "szene", "description": "Eine Szene ausschreiben lassen oder entfernen"},
    {"command": "stand", "description": "Arbeitsstand anzeigen"},
    {"command": "wortlaut", "description": "Originaltranskripte mitlesen"},
    {"command": "hilfe", "description": "Wie der Bot funktioniert"},
]


def _zerlege(text: str) -> tuple[str, str]:
    """Trennt den ersten Token (den Befehl, ggf. mit '@botname') vom Rest
    des Textes. Liefert ``(befehl_ohne_at_und_kleingeschrieben, rest_getrimmt)``."""
    erster, _, rest = text.partition(" ")
    befehl = erster.split("@", 1)[0].lower()
    return befehl, rest.strip()


def _namen_der_aufnahmen(conn, chat_id: int) -> list[str]:
    return [a["name"] for a in repo.transkripte(conn, chat_id) if a["name"]]


def _wortlaut_liste(conn, chat_id: int) -> str:
    namen = _namen_der_aufnahmen(conn, chat_id)
    if not namen:
        return _TEXT_KEINE_AUFNAHMEN
    return "Ich kenne diesen Namen nicht. Vorhandene Aufnahmen: " + ", ".join(namen)


def _befehl_interview(conn, tg, chat_id: int) -> None:
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    tg.sende(chat_id, _TEXT_INTERVIEW_AN)


def _befehl_fertig(conn, tg, chat_id: int) -> None:
    repo.setze_interviewmodus(conn, chat_id, None)
    tg.sende(chat_id, _TEXT_INTERVIEW_AUS)


def _befehl_kernthema(conn, tg, chat_id: int, rest: str) -> None:
    """Setzt das Kernthema -- oder nimmt es mit ``/kernthema aus`` wieder
    weg (NACHTRAG N3, der deterministische Weg neben der Erkenner-art
    ``entfernen``)."""
    if not rest:
        tg.sende(chat_id, _TEXT_KERNTHEMA_LEER)
        return
    if rest.lower() == "aus":
        entfernt = erkenner.entferne(conn, chat_id, "kernthema", quelle="befehl")
        tg.sende(chat_id, _melde_entfernt(entfernt, "Ein Kernthema war nicht gesetzt."))
        return
    repo.setze_arbeitsstand(conn, chat_id, "kernthema", rest)
    tg.sende(chat_id, f"Kernthema notiert: {rest}")


def _melde_entfernt(entfernt: dict | None, wenn_nichts: str) -> str:
    """Die Antwort auf einen Entfernen-Befehl: was weg ist, oder warum
    nichts passiert ist.

    Anders als beim Erkenner (der still bleibt, wenn er nichts findet) sagt
    ein Befehl immer etwas: wer ``/figur Peter entfernen`` tippt, wartet auf
    eine Antwort, und Schweigen sieht aus wie ein kaputter Bot."""
    if entfernt is None:
        return wenn_nichts
    return f"Entfernt: {entfernt['wert']}. Falls das nicht stimmt, sagt es mir."


def _befehl_figur(conn, tg, chat_id: int, rest: str) -> None:
    """``/figur <Name> entfernen`` -- der deterministische Weg, eine Figur
    wegzunehmen (NACHTRAG N3 letzter Absatz).

    Bewusst nur der Entfernungsweg: Figuren ANlegen erledigt der Erkenner im
    Gespraech (art ``figur_setzen``), und ein zweiter Schreibweg fuer
    dasselbe waere genau die Doppelung, die die Befehlsliste am ersten
    Workshoptag von fuenfzehn auf sechs gebracht hat."""
    name, _, schlusswort = rest.rpartition(" ")
    if schlusswort.lower().strip(".") not in _ENTFERNEN_WOERTER or not name.strip():
        tg.sende(chat_id, _TEXT_FIGUR_HILFE)
        return
    entfernt = erkenner.entferne(
        conn, chat_id, f"figur {name.strip()}", quelle="befehl"
    )
    tg.sende(
        chat_id,
        _melde_entfernt(entfernt, f"Eine Figur {name.strip()} kenne ich nicht."),
    )


def _befehl_phase(conn, tg, chat_id: int, rest: str) -> None:
    """Der Notausgang fuer die Arbeitsphase (interview_theater/phasen.py) -- neben
    dem Erkenner (art ``phase_setzen``) der zweite, deterministische Weg.

    Ohne Argument zeigt er die aktuelle Phase und alle acht; mit Argument
    (Nummer oder Name) schaltet er um, auch rueckwaerts. Ein Argument, das
    sich keiner Phase zuordnen laesst, aendert nichts und bekommt die Liste
    zu sehen -- raten waere hier der teuerste Ausgang.

    Geantwortet wird immer, auch wenn die Phase schon stimmte: auf einen
    getippten Befehl zu schweigen sieht aus wie ein kaputter Bot. Ins
    Journal geht der Eintrag trotzdem nur bei einer echten Aenderung
    (``phasen.setze``)."""
    if not rest:
        tg.sende(
            chat_id,
            f"Wir sind bei {phasen.bezeichnung(phasen.aktuelle(conn, chat_id))}.\n\n"
            f"{phasen.liste()}\n\n{_TEXT_PHASE_UMSCHALTEN}",
        )
        return
    nummer = phasen.nummer_fuer(rest)
    if nummer is None:
        tg.sende(chat_id, f"{_TEXT_PHASE_UNBEKANNT}\n\n{phasen.liste()}")
        return
    phasen.setze(conn, chat_id, nummer, "befehl")
    tg.sende(chat_id, phasen.meldung(nummer))


def _befehl_stand(conn, tg, chat_id: int, e=None) -> None:
    """Baut die Stand-Antwort ausschliesslich aus der Datenbank -- ohne
    Sprachmodell, kann also nicht am LLM scheitern (teil-b.md Aufgabe 6).

    Die Phase steht zuerst: sie ordnet alles darunter ein."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)
    aufnahmen_namen = _namen_der_aufnahmen(conn, chat_id)
    gruppe = repo.hole_gruppe(conn, chat_id)
    interviewmodus_an = gruppe is not None and gruppe["interviewmodus_seit"] is not None

    zeilen = ["Stand:"]
    zeilen.append(f"Phase: {phasen.bezeichnung(phasen.aktuelle(conn, chat_id))}")
    zeilen.append(
        f"Begriffe: {stand['begriffe']}" if stand and stand["begriffe"] else "Begriffe: noch keine"
    )
    zeilen.append(
        f"Fragen: {stand['fragen']}" if stand and stand["fragen"] else "Fragen: noch keine"
    )
    zeilen.append(
        f"Kernthema: {stand['kernthema']}" if stand and stand["kernthema"] else "Kernthema: noch offen"
    )
    zeilen.append(
        f"Hauptkonflikt: {stand['hauptkonflikt']}" if stand and stand["hauptkonflikt"]
        else "Hauptkonflikt: noch offen"
    )
    zeilen.append(
        "Figuren: " + ", ".join(f["name"] for f in figuren) if figuren else "Figuren: noch keine"
    )
    zeilen.append(
        "Interviews: " + ", ".join(aufnahmen_namen) if aufnahmen_namen else "Interviews: noch keine"
    )
    zeilen.append("Interviewmodus: an" if interviewmodus_an else "Interviewmodus: aus")
    url = repo.gruppenseite_url(conn, chat_id, getattr(e, "web_url", ""))
    if url:
        zeilen.append(f"Zum Mitlesen: {url}")

    tg.sende(chat_id, "\n".join(zeilen))


def _befehl_wortlaut(conn, tg, chat_id: int, rest: str) -> None:
    if rest.lower() == "aus":
        repo.setze_wortlaut_modus(conn, chat_id, None)
        tg.sende(chat_id, _TEXT_WORTLAUT_AUS)
        return
    if not rest:
        repo.setze_wortlaut_modus(conn, chat_id, "*")
        tg.sende(chat_id, "Wortlaut an: alle Aufnahmen.")
        return
    vorhanden = _namen_der_aufnahmen(conn, chat_id)
    treffer = next((n for n in vorhanden if n.lower() == rest.lower()), None)
    if treffer is None:
        # Unbekannter Name: die vorhandenen aufzaehlen statt zu raten
        # (teil-b.md Aufgabe 6).
        tg.sende(chat_id, _wortlaut_liste(conn, chat_id))
        return
    repo.setze_wortlaut_modus(conn, chat_id, treffer)
    tg.sende(chat_id, f"Wortlaut an: {treffer}")


def _befehl_hilfe(tg, e, chat_id: int) -> None:
    tg.sende(chat_id, _TEXT_HILFE.format(bot_name=e.bot_name))


def _befehl_szene(conn, tg, klm, e, chat_id: int, rest: str) -> None:
    """Der deterministische Weg zum Szenentext -- dasselbe Ziel wie die art
    ``szene_schreiben`` des Absichtserkenners, nur ohne Erkennungsrisiko.

    ``/szene <n> entfernen`` nimmt stattdessen eine Szene weg (NACHTRAG N3).
    Die Abgrenzung ist eng gefasst -- Nummer, dann ein Entfernungswort, sonst
    nichts: alles andere ist ein Schreibauftrag, und einen Auftrag als
    Loeschung misszuverstehen waere der teurere Fehler.

    Schickt selbst keine Ankuendigung: das macht ``szene.starte``, samt der
    Abfuhr, wenn schon eine Szene fuer diese Gruppe laeuft."""
    if not rest:
        tg.sende(chat_id, _TEXT_SZENE_LEER)
        return
    entfernung = _SZENE_ENTFERNEN.match(rest)
    if entfernung:
        nummer = entfernung.group(1)
        entfernt = erkenner.entferne(conn, chat_id, f"szene {nummer}", quelle="befehl")
        tg.sende(
            chat_id, _melde_entfernt(entfernt, f"Eine Szene {nummer} kenne ich nicht.")
        )
        return
    if klm is None:
        log.error("/szene ohne Sprachmodell aufgerufen, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_SZENE_UNMOEGLICH)
        return
    szene.starte(conn, tg, klm, e, chat_id, rest)


#: Die neun erkannten Befehle -- Grundlage dafuer, dass ein unbekannter
#: Slash-Text (z. B. "/irgendwas") freundlich beantwortet statt zu krachen.
_BEKANNTE_BEFEHLE = {
    "/interview", "/fertig", "/phase", "/kernthema", "/figur", "/szene",
    "/stand", "/wortlaut", "/hilfe",
}


def behandle(
    conn, tg, e, chat_id: int, text: str, absender: str | None, klm=None
) -> bool:
    """Faengt Slash-Befehle ab, BEVOR ein Kontext gebaut oder das
    Gespraechsmodell gerufen wird (teil-b.md Aufgabe 6).

    Liefert ``True``, wenn ``text`` mit '/' beginnt (unabhaengig davon, ob
    der Befehl bekannt ist) -- der Aufrufer (``ablauf.antworte``) darf dann
    KEINEN Gespraechszug mehr anstossen. Liefert ``False`` bei jedem anderen
    Text, damit normale Nachrichten unveraendert beim Sprachmodell landen.

    ``klm`` braucht nur ``/szene``, und auch der ruft damit nichts synchron
    auf (siehe Moduldocstring); alle anderen Befehle beantworten sich
    weiterhin allein aus der Datenbank. Der Vorgabewert ``None`` haelt
    bestehende Aufrufe gueltig."""
    if not text or not text.startswith("/"):
        return False

    befehl, rest = _zerlege(text)
    if befehl not in _BEKANNTE_BEFEHLE:
        tg.sende(chat_id, _TEXT_UNBEKANNT)
        return True

    if befehl == "/interview":
        _befehl_interview(conn, tg, chat_id)
    elif befehl == "/fertig":
        _befehl_fertig(conn, tg, chat_id)
    elif befehl == "/phase":
        _befehl_phase(conn, tg, chat_id, rest)
    elif befehl == "/kernthema":
        _befehl_kernthema(conn, tg, chat_id, rest)
    elif befehl == "/figur":
        _befehl_figur(conn, tg, chat_id, rest)
    elif befehl == "/szene":
        _befehl_szene(conn, tg, klm, e, chat_id, rest)
    elif befehl == "/stand":
        _befehl_stand(conn, tg, chat_id, e)
    elif befehl == "/wortlaut":
        _befehl_wortlaut(conn, tg, chat_id, rest)
    elif befehl == "/hilfe":
        _befehl_hilfe(tg, e, chat_id)
    return True

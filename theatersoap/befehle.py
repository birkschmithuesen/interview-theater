"""Sechs Slash-Befehle als Notausgang (teil-b.md Aufgabe 6).

Der Absichtserkenner (``erkenner.py``) ist der Hauptweg: gemessen 0
Falsch-Positive bei 25 Negativfaellen, 30/30 Treffer. Diese sechs Befehle
sind der Notausgang, wenn er trotzdem danebenliegt oder die Gruppe es lieber
explizit macht -- **sechs, nicht fuenfzehn** (SPEC-Reduktion nach dem ersten
Workshoptag).

``behandle()`` wird in ``ablauf.antworte`` VOR dem Kontextaufbau aufgerufen:
ein erkannter Befehl loest KEINEN Sprachmodell-Aufruf aus (kann also nicht am
LLM scheitern) und wird direkt beantwortet. Ein unbekannter Befehl bekommt
eine freundliche Zeile statt zu krachen -- ``behandle()`` liefert in beiden
Faellen ``True``.

Telegram haengt in Gruppen mit mehreren Bots oft den Benutzernamen an einen
Befehl an (``/stand@theatersoapbot``) -- ``_zerlege`` trennt das
grosszuegig ab, unabhaengig davon, welcher Name genau dahintersteht."""

import logging

from theatersoap import repo

log = logging.getLogger(__name__)

_TEXT_INTERVIEW_AN = "Ich zeichne jetzt auf."
_TEXT_INTERVIEW_AUS = "Aufnahme beendet."
_TEXT_KERNTHEMA_LEER = "Schreibt das Kernthema hinter den Befehl, zum Beispiel: /kernthema Ankommen"
_TEXT_UNBEKANNT = "Diesen Befehl kenne ich nicht. /hilfe zeigt, was ich verstehe."
_TEXT_WORTLAUT_AUS = "Wortlaut aus."
_TEXT_KEINE_AUFNAHMEN = "Es gibt noch keine Aufnahmen."

#: Wortidentisch mit der Begruessung aus bot.erstkontakt (teil-b.md Aufgabe
#: 7) in den ersten beiden Absaetzen -- /hilfe ist das jederzeit abrufbare
#: Gegenstueck zur einmaligen Begruessung, beide erklaeren Ansprache und
#: Interviewmodus in derselben Reihenfolge und mit denselben Worten, damit
#: sich niemand an zwei widerspruechliche Erklaerungen erinnern muss.
_TEXT_HILFE = (
    "So sprecht ihr mich an: antwortet auf eine meiner Nachrichten, schreibt "
    "@{bot_name} davor, oder schickt mir eine Sprachnachricht. Untereinander "
    "koennt ihr reden, ohne dass ich dazwischenrede.\n\n"
    "So laufen Interviews: sagt \"wir machen jetzt ein Interview\", dann "
    "zeichne ich auf. \"Fertig\" beendet es.\n\n"
    "Befehle, falls ich mal danebenliege:\n"
    "/interview - Aufnahme starten\n"
    "/fertig - Aufnahme beenden\n"
    "/kernthema <text> - Kernthema setzen oder korrigieren\n"
    "/stand - zeigt, was ich mir bisher gemerkt habe\n"
    "/wortlaut [name|aus] - Originaltranskripte mitlesen\n"
    "/hilfe - diese Uebersicht"
)

#: Telegram-Nutzlast fuer setMyCommands (teil-b.md Aufgabe 6) -- ohne
#: fuehrenden Schraegstrich, Telegram haengt ihn selbst an. Dieselben sechs
#: Befehle wie in behandle(), in derselben Reihenfolge wie in _TEXT_HILFE.
BEFEHLE_LISTE = [
    {"command": "interview", "description": "Aufnahme starten"},
    {"command": "fertig", "description": "Aufnahme beenden"},
    {"command": "kernthema", "description": "Kernthema setzen oder korrigieren"},
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
    if not rest:
        tg.sende(chat_id, _TEXT_KERNTHEMA_LEER)
        return
    repo.setze_arbeitsstand(conn, chat_id, "kernthema", rest)
    tg.sende(chat_id, f"Kernthema notiert: {rest}")


def _befehl_stand(conn, tg, chat_id: int) -> None:
    """Baut die Stand-Antwort ausschliesslich aus der Datenbank -- ohne
    Sprachmodell, kann also nicht am LLM scheitern (teil-b.md Aufgabe 6)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)
    aufnahmen_namen = _namen_der_aufnahmen(conn, chat_id)
    gruppe = repo.hole_gruppe(conn, chat_id)
    interviewmodus_an = gruppe is not None and gruppe["interviewmodus_seit"] is not None

    zeilen = ["Stand:"]
    zeilen.append(
        f"Begriffe: {stand['begriffe']}" if stand and stand["begriffe"] else "Begriffe: noch keine"
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


#: Die sechs erkannten Befehle -- Grundlage dafuer, dass ein unbekannter
#: Slash-Text (z. B. "/irgendwas") freundlich beantwortet statt zu krachen.
_BEKANNTE_BEFEHLE = {"/interview", "/fertig", "/kernthema", "/stand", "/wortlaut", "/hilfe"}


def behandle(conn, tg, e, chat_id: int, text: str, absender: str | None) -> bool:
    """Faengt Slash-Befehle ab, BEVOR ein Kontext gebaut oder das
    Sprachmodell gerufen wird (teil-b.md Aufgabe 6).

    Liefert ``True``, wenn ``text`` mit '/' beginnt (unabhaengig davon, ob
    der Befehl bekannt ist) -- der Aufrufer (``ablauf.antworte``) darf dann
    KEINEN Gespraechszug mehr anstossen. Liefert ``False`` bei jedem anderen
    Text, damit normale Nachrichten unveraendert beim Sprachmodell landen."""
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
    elif befehl == "/kernthema":
        _befehl_kernthema(conn, tg, chat_id, rest)
    elif befehl == "/stand":
        _befehl_stand(conn, tg, chat_id)
    elif befehl == "/wortlaut":
        _befehl_wortlaut(conn, tg, chat_id, rest)
    elif befehl == "/hilfe":
        _befehl_hilfe(tg, e, chat_id)
    return True

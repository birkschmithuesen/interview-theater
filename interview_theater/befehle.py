"""Zehn Slash-Befehle als Notausgang (teil-b.md Aufgabe 6, plus ``/szene``,
``/phase``, ``/figur`` und ``/auswerten``).

Der Absichtserkenner (``erkenner.py``) ist der Hauptweg: gemessen 0
Falsch-Positive bei 25 Negativfaellen, 30/30 Treffer. Diese Befehle sind der
Notausgang, wenn er trotzdem danebenliegt oder die Gruppe es lieber explizit
macht -- **zehn, nicht fuenfzehn** (SPEC-Reduktion nach dem ersten
Workshoptag; ``/szene`` kam mit den Szenentexten dazu, ``/phase`` und
``/figur`` mit den Arbeitsphasen und dem weichen Loeschen, ``/auswerten`` mit
der Mindestlaenge aus N2).

``behandle()`` wird in ``ablauf.antworte`` VOR dem Kontextaufbau aufgerufen:
ein erkannter Befehl loest KEINEN Gespraechszug aus (kann also nicht am
Gespraechsmodell scheitern) und wird direkt beantwortet. Ein unbekannter
Befehl bekommt eine freundliche Zeile statt zu krachen -- ``behandle()``
liefert in beiden Faellen ``True``.

**Die Ausnahmen, benannt:** ``/szene``, ``/fertig`` und ``/auswerten``
brauchen ein Sprachmodell, deshalb nimmt ``behandle()`` ein optionales
``klm`` entgegen.
Die urspruengliche strukturelle Garantie ("behandle nimmt kein LLM-Objekt,
also kann /stand nicht am Modell scheitern") ist damit eine Zusage geworden,
die der Code weiterhin einhaelt: kein Befehl ruft synchron ein Modell.
``/szene`` gibt den Aufruf sofort an einen eigenen Thread ab
(``szene.starte``), ``/fertig`` ebenso (``aufnahme.starte_abschluss`` fuer die
eine Verdichtung des beendeten Interviews, § 10.6) und ``/auswerten``
(``aufnahme.starte_auswertung``). Wer hier einen weiteren Befehl anhaengt,
halte sich daran.

Telegram haengt in Gruppen mit mehreren Bots oft den Benutzernamen an einen
Befehl an (``/stand@interview_theaterbot``) -- ``_zerlege`` trennt das
grosszuegig ab, unabhaengig davon, welcher Name genau dahintersteht."""

import logging
import re

from interview_theater import aufnahme, erkenner, knoepfe, phasen, repo, szene

#: Woerter, die einen Befehl zu einer Entfernung machen (NACHTRAG N3).
#: Grosszuegig, weil die Gruppe tippt, was ihr einfaellt -- aber eine feste
#: Liste, kein Freitext: "/szene 2 kuerzer" ist ein Schreibauftrag.
_ENTFERNEN_WOERTER = {"entfernen", "entferne", "loeschen", "löschen", "weg", "raus"}

#: "/szene 2 entfernen" -- Nummer, dann ein Entfernungswort, sonst nichts.
_SZENE_ENTFERNEN = re.compile(
    r"^(?:szene\s*)?(\d{1,3})\s+(?:" + "|".join(_ENTFERNEN_WOERTER) + r")\.?$",
    re.IGNORECASE,
)

#: "/szene usa ja" bzw. "/szene usa nein" -- die Antwort auf das
#: Einwilligungs-Angebot fuer das US-Modell, deterministisch statt ueber den
#: Erkenner. Eng gefasst: nur genau dieses eine Wortpaar, damit ein
#: Szenenauftrag, in dem zufaellig "usa" vorkommt, nicht als Einwilligung
#: gelesen wird.
_SZENE_USA = re.compile(r"^usa\s+(ja|j|yes|nein|n|no)\.?$", re.IGNORECASE)

#: "/szene usa" ohne Antwort -- dann kommen die beiden Knoepfe, statt einer
#: Zeile, die die Syntax erklaert (05.09.2026). Dieselbe Ueberlegung wie bei
#: "/kernthema" ohne Argument: an einem Auswahl-Moment ist ein Knopf die
#: bessere Antwort als eine Bedienungsanleitung.
_SZENE_USA_LEER = re.compile(r"^usa\.?$", re.IGNORECASE)

#: "/szene 2 form" ohne Wert -- dann kommen die Formknoepfe. Ohne diese
#: Sonderform faengt ``_SZENE_FELD`` den Text nicht (es verlangt einen Wert),
#: und der Rest liefe als Szenen-SCHREIBauftrag ins Sprachmodell.
_SZENE_FORM_LEER = re.compile(r"^(?:szene\s*)?(\d{1,3})\s+form\.?$", re.IGNORECASE)

#: "/szene 2 ort Polizeikessel" -- Nummer, ein bekannter Feldname, der Wert.
#: Der Korrekturweg zu den Szenenfeldern (05.09.2026), neben der Erkenner-art
#: ``szene_planen``. Eng gefasst wie ``_SZENE_ENTFERNEN``: der zweite Token
#: muss ein Feldname sein, sonst ist es ein Schreibauftrag ("/szene 2 nochmal,
#: aber kuerzer").
_SZENE_FELD = re.compile(
    r"^(?:szene\s*)?(\d{1,3})\s+(\w+)\s+(.+)$", re.IGNORECASE | re.DOTALL
)

log = logging.getLogger(__name__)

#: Start und Stopp sagen seit 05.09.2026 (Birk) die Bedienung dazu: die
#: Gruppe steht im Raum mit einer interviewten Person vor sich und soll nicht
#: raten muessen, wie sie die Aufnahme wieder anhaelt.
_TEXT_INTERVIEW_AN = (
    "Aufnahme laeuft. Sprecht eure Sprachnachrichten ein - so viele, wie ihr "
    "wollt, sie gehoeren alle zu diesem einen Interview. Nach jeder schicke "
    "ich euch den abgetippten Text zum Mitlesen. Zum Beenden nochmal "
    "/aufnahme."
)
_TEXT_INTERVIEW_AUS = (
    "Aufnahme beendet. Fuer das naechste Interview wieder /aufnahme."
)
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
#: ``/szene 2 figuren ...`` mit lauter unbekannten Namen. Anders als beim
#: Erkenner (der still bleibt) bekommt ein getippter Befehl immer eine
#: Antwort -- und der Grund ist hier eine Entscheidung, keine Panne: eine
#: Szene wird nur mit Figuren aus dem Arbeitsstand besetzt.
_TEXT_SZENE_FIGUR_UNBEKANNT = (
    "Diese Figuren kenne ich nicht: {namen}. In einer Szene stehen nur "
    "Figuren aus dem Arbeitsstand - legt sie zuerst im Gespraech an."
)
#: Nur erreichbar, wenn ein Aufrufer ``behandle()`` ohne ``klm`` benutzt --
#: ein Programmierfehler, aber einer, der die Gruppe nicht ratlos lassen soll.
_TEXT_SZENE_UNMOEGLICH = "Ich kann gerade keine Szene schreiben."
_TEXT_AUSWERTEN_UNMOEGLICH = "Ich kann gerade nicht auswerten."

#: Wortidentisch mit der Begruessung aus bot.erstkontakt (teil-b.md Aufgabe
#: 7) in den ersten beiden Absaetzen -- /hilfe ist das jederzeit abrufbare
#: Gegenstueck zur einmaligen Begruessung, beide erklaeren dasselbe (dass
#: der Bot auf alles antwortet, wie Interviews laufen) in derselben
#: Reihenfolge und mit denselben Worten, damit sich niemand an zwei
#: widerspruechliche Erklaerungen erinnern muss.
_TEXT_HILFE = (
    "Schreibt oder sprecht einfach - ich lese alles mit und antworte.\n\n"
    "SO MACHT IHR EIN INTERVIEW:\n"
    "1. /aufnahme - die Aufnahme laeuft\n"
    "2. Sprachnachrichten einsprechen, so viele ihr wollt - sie gehoeren "
    "alle zu diesem einen Interview\n"
    "3. Nach jeder schicke ich euch den abgetippten Text zum Mitlesen. "
    "Steht da ein Wort falsch, sagt es mir einfach.\n"
    "4. /aufnahme - beendet das Interview\n"
    "Fuer das naechste Interview wieder mit /aufnahme anfangen.\n\n"
    "Weitere Befehle:\n"
    "/stand - zeigt, was ich mir bisher gemerkt habe\n"
    "/auswerten [nummer] - was in den Interviews steckt\n"
    "/kernthema <text> - das Kernthema festlegen\n"
    "/stueck format <text> - Sprechtheater, Musical, Mischform ...\n"
    "/stueck rahmen <text> - Ort, Zeit, Anlass des Abends\n"
    "/szene <nummer> form <dialog|monolog|lied|rap|chor|stumm>\n"
    "/szene <nummer> ort <text> - dasselbe fuer ort, zeit, anlass, figuren\n"
    "/szene <auftrag> - eine Szene schreiben lassen\n"
    "/phase [nummer|name] - zeigt die Phase oder schaltet um\n"
    "/hilfe - diese Uebersicht\n\n"
    "Alles andere sagt ihr mir einfach: Figuren, Szenen, Entscheidungen - "
    "ich halte es fest, ohne dass ihr einen Befehl braucht."
)

#: Telegram-Nutzlast fuer setMyCommands (teil-b.md Aufgabe 6) -- ohne
#: fuehrenden Schraegstrich, Telegram haengt ihn selbst an.
#: Was im Telegram-Menue steht, wenn jemand '/' tippt. Seit 05.09.2026 stark
#: gekuerzt (Birk: "es gibt zu viele / commands im chat, da muessen wir uns
#: reduzieren"): fuenf statt zehn. Massstab ist, was eine Gruppe im Workshop
#: WIRKLICH selbst braucht -- alles andere kann sie dem Bot einfach sagen, er
#: versteht es im Gespraech (der Erkenner schreibt Kernthema, Figuren, Phase
#: und Szenen ohnehin mit).
#:
#: Draussen, aber weiter gueltig (nur nicht mehr beworben): /interview und
#: /fertig (Synonyme von /aufnahme, fuer das Muskelgedaechtnis), /kernthema,
#: /figur, /szene, /auswerten, /wortlaut, /phase.
BEFEHLE_LISTE = [
    {"command": "aufnahme", "description": "Interview starten - und nochmal, um zu beenden"},
    {"command": "stand", "description": "Arbeitsstand anzeigen"},
    {"command": "auswerten", "description": "Interviews auswerten und anzeigen"},
    {"command": "kernthema", "description": "Kernthema festlegen oder korrigieren"},
    {"command": "stueck", "description": "Format und Rahmen des Stuecks (Phase 5)"},
    {"command": "szene", "description": "Szene planen, Form setzen, schreiben lassen"},
    {"command": "phase", "description": "Arbeitsphase zeigen oder umschalten"},
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


def _befehl_aufnahme(conn, tg, klm, e, chat_id: int) -> None:
    """``/aufnahme`` -- EIN mechanischer Umschalter fuer Start und Stopp
    (Birk 05.09.2026: "das Interview starten und stoppen ist sehr
    problematisch, ich denke die sicherste Loesung ist das mechanisch mit
    /aufnahme zu machen").

    Vorher brauchte es zwei Wege: gesprochenes "wir machen jetzt ein
    Interview" (der Erkenner musste es treffen) oder ``/interview`` und
    ``/fertig`` als zwei getrennte Befehle. Beides ging im Testlauf schief --
    Start und Ende fielen in denselben Erkennerlauf und der Kopf blieb leer.

    Ein Umschalter kann das nicht: laeuft nichts, startet er; laeuft etwas,
    beendet er. Die Gruppe muss sich nur EIN Wort merken, und der Zustand
    steht sichtbar in der Antwort."""
    if repo.ist_interviewmodus_an(conn, chat_id):
        kopf_id = aufnahme.beende_interview(conn, chat_id)
        knoepfe.biete_aufnahme(conn, tg, chat_id, _TEXT_INTERVIEW_AUS)
        if kopf_id is not None and klm is not None:
            aufnahme.starte_abschluss(conn, tg, klm, e, kopf_id)
        return
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, chat_id)
    knoepfe.biete_aufnahme(conn, tg, chat_id, _TEXT_INTERVIEW_AN)


def _befehl_interview(conn, tg, chat_id: int) -> None:
    """Modus an -- und damit entsteht EIN Interview (§ 10.6), zu dem alle
    folgenden Sprachnachrichten als Teile gehoeren."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, chat_id)
    tg.sende(chat_id, _TEXT_INTERVIEW_AN)


def _befehl_fertig(conn, tg, klm, e, chat_id: int) -> None:
    """Modus aus, Interview zusammenfuegen und einmal verdichten (§ 10.6).

    Die Verdichtung laeuft in einem eigenen Thread (``aufnahme.starte_abschluss``)
    -- die Zusage 'kein Befehl ruft synchron ein Modell' gilt weiter. Ohne
    ``klm`` (ein Aufrufer ohne Sprachmodell) bleibt das Interview auf
    'transkribiert' stehen und der Nachhol-Arbeiter verdichtet es."""
    kopf_id = aufnahme.beende_interview(conn, chat_id)
    tg.sende(chat_id, _TEXT_INTERVIEW_AUS)
    if kopf_id is not None and klm is not None:
        aufnahme.starte_abschluss(conn, tg, klm, e, kopf_id)


def _befehl_auswerten(conn, tg, klm, e, chat_id: int, rest: str) -> None:
    """``/auswerten [N]`` -- verdichtet ein Interview, das der Bot von sich
    aus nicht ausgewertet hat (Nachtrag N2: unter ``aufnahme.MINDEST_WOERTER``
    Woertern fragt er das Sprachmodell gar nicht erst).

    Der Widerspruchsweg zu genau dieser Ablehnung: die Gruppe kennt ihr
    Material besser als eine Wortzahl. Ohne Argument trifft es das letzte
    Interview, mit Nummer oder Namensteil ein bestimmtes.

    Laeuft wie ``/fertig`` in einem eigenen Thread (``aufnahme.
    starte_auswertung``) -- kein Befehl ruft synchron ein Modell."""
    kopf = aufnahme.finde_interview(conn, chat_id, rest)
    if kopf is None:
        namen = [a["name"] for a in aufnahme.interviews(conn, chat_id) if a["name"]]
        tg.sende(
            chat_id,
            _TEXT_KEINE_AUFNAHMEN if not namen
            else "Dieses Interview kenne ich nicht. Vorhandene: " + ", ".join(namen),
        )
        return
    name = kopf["name"] or "Das Interview"
    if repo.verdichtung_zu_aufnahme(conn, kopf["id"]) is not None:
        tg.sende(chat_id, f"{name} ist schon ausgewertet.")
        return
    if klm is None:
        log.error("/auswerten ohne Sprachmodell aufgerufen, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
        return
    tg.sende(chat_id, f"Ich werte {name} aus.")
    aufnahme.starte_auswertung(conn, tg, klm, e, kopf["id"])


def _befehl_stueck(conn, tg, chat_id: int, rest: str) -> None:
    """``/stueck format <text>`` und ``/stueck rahmen <text>`` -- die beiden
    Ergebnisse von Phase 5 unter EINEM Befehl.

    Vorher waren es zwei (``/format``, ``/rahmen``). Zusammengelegt am
    05.09.2026 (Birk: "fass zusammen, was Sinn macht"), weil beide dieselbe
    Frage beantworten -- was fuer ein Stueck entsteht -- und die Station im
    Bot auch "Format & Rahmen" heisst. Ein Befehl weniger im Menue, und das
    Muster ist dasselbe wie bei ``/szene 2 ort Kessel``: Befehl, Feld, Wert.

    Ohne Feld zeigt er beide Werte -- so ist ``/stueck`` zugleich die Antwort
    auf "was haben wir da nochmal festgelegt", ohne den ganzen ``/stand``.

    ``aus`` als Wert nimmt das Feld wieder weg, wie bei ``/kernthema aus``."""
    felder = {"format": "Format", "rahmen": "Rahmen"}
    feld, _, wert = rest.partition(" ")
    feld = feld.strip().lower()
    wert = wert.strip()

    if not feld:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        zeilen = []
        for schluessel, name in felder.items():
            gesetzt = (stand[schluessel] if stand else None) or ""
            zeilen.append(f"{name}: {gesetzt}" if gesetzt else f"{name}: noch offen")
        zeilen.append("Setzen: /stueck format Sprechtheater: Dialog und Chor")
        tg.sende(chat_id, "\n".join(zeilen))
        return

    if feld not in felder:
        tg.sende(
            chat_id,
            "Das kenne ich nicht. Es gibt /stueck format <text> und "
            "/stueck rahmen <text>.",
        )
        return

    bezeichnung = felder[feld]
    if not wert:
        # Beim Format kommen seit dem 05.09.2026 Knoepfe statt einer
        # Syntaxzeile: Phase 5 stellt das Format als nummerierte Auswahl, und
        # auf "das erste" kann der Erkenner nicht zuverlaessig schliessen
        # (knoepfe.biete_format). Der Rahmen bleibt Freitext -- dort gibt es
        # keine Liste, aus der sich waehlen liesse.
        if feld == "format":
            knoepfe.biete_format(conn, tg, chat_id)
            return
        beispiel = _BEISPIEL_ARBEITSSTAND[feld]
        tg.sende(
            chat_id,
            f"Schreibt den {bezeichnung} dahinter, zum Beispiel: "
            f"/stueck {feld} {beispiel}",
        )
        return
    if wert.lower() == "aus":
        entfernt = erkenner.entferne(conn, chat_id, feld, quelle="befehl")
        tg.sende(chat_id, _melde_entfernt(entfernt, f"Ein {bezeichnung} war nicht gesetzt."))
        return
    repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    tg.sende(chat_id, f"{bezeichnung} notiert: {wert}")


#: Beispiele fuer die Hilfezeilen von /stueck -- konkret, damit
#: sichtbar ist, wie lang die Angabe sein soll (eine Zeile, kein Aufsatz).
_BEISPIEL_ARBEITSSTAND = {
    "format": "Sprechtheater: Dialog und Chor",
    "rahmen": "Ein Wartezimmer, an einem Nachmittag",
}


def _befehl_kernthema(conn, tg, chat_id: int, rest: str) -> None:
    """Setzt das Kernthema -- oder nimmt es mit ``/kernthema aus`` wieder
    weg (NACHTRAG N3, der deterministische Weg neben der Erkenner-art
    ``entfernen``).

    Ohne Argument bietet der Befehl seit dem 05.09.2026 die Kernthema-
    Vorschlaege als Knoepfe an (``knoepfe.biete_kernthema``), statt nur zu
    erklaeren, wie man ihn benutzt: an genau diesem Auswahl-Moment ist die
    Spracherkennung unzuverlaessig (siehe knoepfe.py), und die Vorschlaege
    liegen schon fertig in den Verdichtungen -- ein Knopf spart der Gruppe
    das Abtippen und dem Bot das Raten. Kein Modellaufruf: die Vorschlaege
    kommen aus der Datenbank."""
    if not rest:
        if not knoepfe.biete_kernthema(conn, tg, chat_id):
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

    Ohne Argument zeigt er die aktuelle Phase und alle sieben; mit Argument
    (Nummer oder Name) schaltet er um, auch rueckwaerts. Ein Argument, das
    sich keiner Phase zuordnen laesst, aendert nichts und bekommt die Liste
    zu sehen -- raten waere hier der teuerste Ausgang.

    Gibt die Materiallage einen Schritt nach oben her, haengt seit dem
    05.09.2026 ein Knopf "Weiter zu Phase N" darunter
    (``knoepfe.biete_phase``, reine Leseabfrage ueber
    ``phasen.naechste_moegliche``). Genau EIN Ziel und nicht die ganze
    Liste: der Knopf ist eine Frage, keine Navigation -- zurueck geht
    weiterhin ueber ``/phase 4``.

    Geantwortet wird immer, auch wenn die Phase schon stimmte: auf einen
    getippten Befehl zu schweigen sieht aus wie ein kaputter Bot. Ins
    Journal geht der Eintrag trotzdem nur bei einer echten Aenderung
    (``phasen.setze``)."""
    if not rest:
        text = (
            f"Wir sind bei {phasen.bezeichnung(phasen.aktuelle(conn, chat_id))}.\n\n"
            f"{phasen.liste()}\n\n{_TEXT_PHASE_UMSCHALTEN}"
        )
        naechste = phasen.naechste_moegliche(conn, chat_id)
        if naechste is None:
            tg.sende(chat_id, text)
        else:
            knoepfe.biete_phase(conn, tg, chat_id, text, naechste)
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
        f"Format: {stand['format']}" if stand and stand["format"] else "Format: noch offen"
    )
    zeilen.append(
        f"Rahmen: {stand['rahmen']}" if stand and stand["rahmen"] else "Rahmen: noch offen"
    )
    # Der Hauptkonflikt steht nur da, wenn es einen gibt (05.09.2026): er ist
    # eine moegliche Rahmen-Entscheidung, keine Pflicht -- und eine Zeile
    # "Hauptkonflikt: noch offen" liest sich wie eine Luecke, die zu fuellen
    # waere.
    if stand and stand["hauptkonflikt"]:
        zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
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


def _setze_szenenfeld(conn, tg, chat_id: int, rest: str) -> bool:
    """``/szene <n> <feld> <wert>`` -- der deterministische Korrekturweg zu
    den Szenenfeldern (05.09.2026), neben der Erkenner-art ``szene_planen``.

    Liefert True, wenn der Text als Feldkorrektur gelesen wurde -- dann ist
    der Befehl erledigt. Sonst False, und ``_befehl_szene`` macht mit dem
    Entfernungs- und dem Schreibweg weiter.

    Die Abgrenzung ist eng: der zweite Token muss ein bekannter Feldname sein
    (``szene.FELD_ALIASE``). Alles andere ist ein Schreibauftrag -- "/szene 2
    nochmal, aber kuerzer" darf nicht als Feld 'nochmal' enden."""
    treffer = _SZENE_FELD.match(rest)
    if treffer is None:
        return False
    feld = szene.feldname(treffer.group(2))
    if feld is None:
        return False
    nummer, wert = int(treffer.group(1)), treffer.group(3).strip()
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    if feld == "figuren":
        ids = erkenner._figuren_aus_namen(conn, chat_id, wert)
        if not ids:
            tg.sende(chat_id, _TEXT_SZENE_FIGUR_UNBEKANNT.format(namen=wert))
            return True
        repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
    else:
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    tg.sende(chat_id, szene.planungszeile(conn, repo.hole_szene(conn, szene_id)))
    return True


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
    # /szene usa ja|nein -- die Antwort auf das Einwilligungs-Angebot, ohne
    # dass sie der Erkenner treffen muss. In der Simulation am 05.09. las er
    # "ja stimmt alles" als Zustimmung zu den Figuren, nicht zur USA-Frage;
    # der Bot wiederholte daraufhin siebenmal dieselbe Erinnerung.
    usa = _SZENE_USA.match(rest)
    if usa:
        ja = usa.group(1).lower() in ("ja", "j", "yes")
        repo.setze_szene_usa(conn, chat_id, ja)
        tg.sende(
            chat_id,
            "Gut, Szenen kommen ab jetzt vom US-Modell. Ich sage es vor jeder "
            "Szene nochmal." if ja else
            "Verstanden, alles bleibt in der Schweiz. Ich frage nicht wieder.",
        )
        return
    # "/szene usa" ohne Antwort: die beiden Knoepfe statt einer Syntaxzeile.
    # Genau hier ist die Sprachnavigation am 05.09.2026 gescheitert -- die
    # Gruppe bejahte siebenmal, der Erkenner las es als Zustimmung zu den
    # Figuren (siehe knoepfe.biete_szene_usa).
    if _SZENE_USA_LEER.match(rest):
        knoepfe.biete_szene_usa(conn, tg, chat_id)
        return
    # "/szene 2 form" ohne Wert: die sechs Formknoepfe. Muss VOR
    # _setze_szenenfeld stehen, sonst faellt der Text durch bis zum
    # Schreibauftrag.
    form_leer = _SZENE_FORM_LEER.match(rest)
    if form_leer:
        knoepfe.biete_szenenform(conn, tg, chat_id, int(form_leer.group(1)))
        return
    if _setze_szenenfeld(conn, tg, chat_id, rest):
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


#: Die erkannten Befehle -- Grundlage dafuer, dass ein unbekannter
#: Slash-Text (z. B. "/irgendwas") freundlich beantwortet statt zu krachen.
#: ``/aufnahme`` ist seit 05.09.2026 der beworbene Weg; ``/interview`` und
#: ``/fertig`` bleiben als stille Synonyme gueltig (Muskelgedaechtnis), stehen
#: aber nicht mehr im Menue.
_BEKANNTE_BEFEHLE = {
    "/aufnahme", "/interview", "/fertig", "/auswerten", "/phase", "/kernthema",
    "/stueck", "/figur", "/szene", "/stand", "/wortlaut", "/hilfe",
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

    if befehl == "/aufnahme":
        _befehl_aufnahme(conn, tg, klm, e, chat_id)
    elif befehl == "/interview":
        _befehl_interview(conn, tg, chat_id)
    elif befehl == "/fertig":
        _befehl_fertig(conn, tg, klm, e, chat_id)
    elif befehl == "/auswerten":
        _befehl_auswerten(conn, tg, klm, e, chat_id, rest)
    elif befehl == "/phase":
        _befehl_phase(conn, tg, chat_id, rest)
    elif befehl == "/kernthema":
        _befehl_kernthema(conn, tg, chat_id, rest)
    elif befehl == "/stueck":
        _befehl_stueck(conn, tg, chat_id, rest)
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

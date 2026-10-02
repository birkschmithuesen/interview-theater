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

from interview_theater import (
    aufnahme, erkenner, knoepfe, leitfaden, phasen, repo, sprache, szene,
)

#: Woerter, die einen Befehl zu einer Entfernung machen (NACHTRAG N3).
#: Grosszuegig, weil die Gruppe tippt, was ihr einfaellt -- aber eine feste
#: Liste, kein Freitext: "/szene 2 kuerzer" ist ein Schreibauftrag.
_ENTFERNEN_WOERTER = {"entfernen", "entferne", "loeschen", "löschen", "weg", "raus"}

#: "/szene 2 entfernen" -- Nummer, dann ein Entfernungswort, sonst nichts.
_SZENE_ENTFERNEN = re.compile(
    r"^(?:szene\s*)?(\d{1,3})\s+(?:" + "|".join(_ENTFERNEN_WOERTER) + r")\.?$",
    re.IGNORECASE,
)

#: Die Befehlsargumente einer englischsprachigen Gruppe (Karte A1,
#: Aufgabe 22). Gewaehlt wird je Sprache; die englische Wahl nimmt die
#: deutschen Argumentwoerter **mit**, weil sie nach Annahme A4 Teil der
#: Befehlssyntax bleiben und die englische Hilfe sie nennt
#: ("/figur <name> entfernen", "/festlegung weg <search word>").
_ENTFERNEN_WOERTER_EN = {"remove", "delete", "drop", "out"}
_ENTFERNEN_JE_SPRACHE = {
    "de": _ENTFERNEN_WOERTER,
    "en": _ENTFERNEN_WOERTER | _ENTFERNEN_WOERTER_EN,
}
#: Nachbesserung (Review Commit 15d70a8, Befund 4, mit dem Interpreter
#: gemessen): der Praefix kannte nur "scene", der Slash-Befehl heisst aber
#: weiter "/szene" (Annahme A4) -- "/szene szene 2 remove" fiel bis zum
#: Schreibauftrag durch, weil das Praefixwort "szene" nicht erkannt wurde.
#: Jetzt akzeptiert der Praefix beide Schreibweisen.
_SZENE_PRAEFIX_EN = r"(?:s(?:z|c)ene\s*)?"
_SZENE_ENTFERNEN_EN = re.compile(
    r"^" + _SZENE_PRAEFIX_EN + r"(\d{1,3})\s+(?:"
    + "|".join(sorted(_ENTFERNEN_JE_SPRACHE["en"])) + r")\.?$",
    re.IGNORECASE,
)

#: Das Argument, das ein Feld wieder leert ("/kernthema aus").
_AUS = {"de": ("aus",), "en": ("off", "aus")}

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
#: Nachbesserung (Review Commit 15d70a8, Befund 4, derselbe Praefix-Fund wie
#: bei ``_SZENE_ENTFERNEN_EN``): "szene" war hier ebenso wenig erkannt wie
#: dort, mit dem Interpreter nachgemessen.
_SZENE_FORM_LEER_EN = re.compile(
    r"^" + _SZENE_PRAEFIX_EN + r"(\d{1,3})\s+form\.?$", re.IGNORECASE
)

#: "/szene 2 ort Polizeikessel" -- Nummer, ein bekannter Feldname, der Wert.
#: Der Korrekturweg zu den Szenenfeldern (05.09.2026), neben der Erkenner-art
#: ``szene_planen``. Eng gefasst wie ``_SZENE_ENTFERNEN``: der zweite Token
#: muss ein Feldname sein, sonst ist es ein Schreibauftrag ("/szene 2 nochmal,
#: aber kuerzer").
_SZENE_FELD = re.compile(
    r"^(?:szene\s*)?(\d{1,3})\s+(\w+)\s+(.+)$", re.IGNORECASE | re.DOTALL
)
#: Dieselben zwei Muster fuer eine englischsprachige Gruppe ("/szene scene 2
#: ort ..."). Der Feldname selbst laeuft weiter ueber ``szene.feldname``.
#: Nachbesserung (Review Commit 15d70a8, Befund 4): Praefix akzeptiert jetzt
#: "szene" oder "scene", siehe ``_SZENE_PRAEFIX_EN``.
_SZENE_FELD_EN = re.compile(
    r"^" + _SZENE_PRAEFIX_EN + r"(\d{1,3})\s+(\w+)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _ist_aus(wert: str) -> bool:
    """Ist ``wert`` das Leer-Argument der Sprache ("aus", englisch "off")?"""
    return wert.lower() in sprache.je_sprache(_AUS)

log = logging.getLogger(__name__)

#: Start und Stopp sagen seit 05.09.2026 (Birk) die Bedienung dazu: die
#: Gruppe steht im Raum mit einer interviewten Person vor sich und soll nicht
#: raten muessen, wie sie die Aufnahme wieder anhaelt.
#: Der Wortlaut ist Birks, mit einer Aenderung aus (E): unter dieser
#: Bestaetigung haengt seit 05.09.2026 KEIN Knopf mehr (Live-Fall Gruppe 1,
#: 14:21 -- Start, sieben Sekunden spaeter versehentlich Beenden).
#: Deshalb sagt der Text jetzt ausdruecklich, WO der Beenden-Knopf erscheint:
#: unter dem abgetippten Text der ersten Sprachnachricht
#: (``knoepfe.biete_nach_teil``).
_TEXT_INTERVIEW_AN = (
    "Bereit - schickt eure Sprachnachrichten. Nach jeder kommt der abgetippte "
    "Text."
)
_TEXT_INTERVIEW_AUS = "Aufnahme beendet."
_TEXT_KERNTHEMA_LEER = "Schreibt das Kernthema hinter den Befehl, zum Beispiel: /kernthema Ankommen"
#: Ein unbekannter Slash-Text. Statt auf ``/hilfe`` zu verweisen, haengen die
#: Einstiegsknoepfe darunter (05.09.2026) -- wer sich schon in einem Befehl
#: vertippt hat, soll nicht einen zweiten richtig treffen muessen.
_TEXT_UNBEKANNT = "Diesen Befehl kenne ich nicht."
_TEXT_WORTLAUT_AUS = "Wortlaut aus."
_TEXT_PHASE_UMSCHALTEN = "Umschalten mit /phase 4 oder /phase Figuren - auch zurueck."
_TEXT_FIGUR_HILFE = (
    "So nehme ich eine Figur weg: /figur Peter entfernen. "
    "Anlegen koennt ihr Figuren einfach im Gespraech."
)
_TEXT_PHASE_UNBEKANNT = "Diese Phase kenne ich nicht. Ich habe diese sieben:"
_TEXT_KEINE_AUFNAHMEN = "Es gibt noch keine Aufnahmen."
#: /sprache (Karte A1, D2) -- versteckt, wie /leitfaden: der Weg ist der
#: Knopf in Phase 3, der Befehl der Notausgang und die Anzeige.
_TEXT_SPRACHE_STAND = "Interviewsprache: {sprache}."
_TEXT_SPRACHE_GESETZT = "Interviewsprache ab jetzt: {sprache}."
_TEXT_SPRACHE_UNBEKANNT = (
    "Das kenne ich nicht. Moeglich sind auto oder ein Sprachkuerzel wie "
    "it, en, de."
)
_TEXT_SPRACHE_AUTO = "automatisch (ich erkenne sie selbst)"
_JOURNAL_SPRACHE = "Interviewsprache fuer Whisper: {sprache}"
_SPRACHWERT = re.compile(r"^(auto|[a-z]{2})$")
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

#: Die frueheren Inline-Saetze der Befehle (Karte A1): als Konstanten, damit
#: sie ueber ``T`` laufen. Zeichengleich mit dem, was vorher am
#: Verwendungsort stand.
_TEXT_NAME_UNBEKANNT = "Ich kenne diesen Namen nicht. Vorhandene Aufnahmen: {namen}"
_TEXT_INTERVIEW_UNBEKANNT = "Dieses Interview kenne ich nicht. Vorhandene: {namen}"
#: /stueck: Feldname -> sichtbare Bezeichnung. Die Schluessel sind Protokoll
#: (Spaltennamen und Befehlsargument), nur die Werte sind Anzeige.
_STUECK_FELDER = {"rahmen": "Rahmen", "format": "Format"}
_TEXT_RAHMEN_ZEILE = "Rahmen: {rahmen}"
_TEXT_RAHMEN_OFFEN = "Rahmen: noch offen"
_TEXT_RAHMEN_SETZEN = "Setzen: /stueck rahmen Ein Wartezimmer, an einem Nachmittag"
_TEXT_STUECK_UNBEKANNT = "Das kenne ich nicht. Es gibt /stueck rahmen <text>."
_TEXT_STUECK_WERT_LEER = (
    "Schreibt den {bezeichnung} dahinter, zum Beispiel: /stueck {feld} {beispiel}"
)
_TEXT_STUECK_NICHT_GESETZT = "Ein {bezeichnung} war nicht gesetzt."
_TEXT_STUECK_NOTIERT = "{bezeichnung} notiert: {wert}"
_TEXT_KERNTHEMA_NICHT_GESETZT = "Ein Kernthema war nicht gesetzt."
_TEXT_ENTFERNT = "Entfernt: {wert}."
_TEXT_FIGUR_UNBEKANNT = "Eine Figur {name} kenne ich nicht."
_TEXT_SZENE_UNBEKANNT = "Eine Szene {nummer} kenne ich nicht."
_TEXT_FESTGEHALTEN = "Festgehalten: {zeile}"
_TEXT_WIR_SIND_BEI = "Wir sind bei {phase}."
_TEXT_STAND_KOPF = "Stand:"
_TEXT_STAND_PHASE = "Phase: {phase}"
_TEXT_WAS_BISHER = "Was bisher passiert:"
_TEXT_STAND_KERNTHEMA = "Kernthema: {wert}"
_TEXT_STAND_HAUPTKONFLIKT = "Hauptkonflikt: {wert}"
_TEXT_INTERVIEWMODUS_AN = "Interviewmodus: an"
_TEXT_INTERVIEWMODUS_AUS = "Interviewmodus: aus"
_TEXT_ZUM_MITLESEN = "Zum Mitlesen: {url}"
_TEXT_WORTLAUT_ALLE = "Wortlaut an: alle Aufnahmen."
_TEXT_WORTLAUT_AN = "Wortlaut an: {name}"

#: Wortidentisch mit der Begruessung aus bot.erstkontakt (teil-b.md Aufgabe
#: 7) in den ersten beiden Absaetzen -- /hilfe ist das jederzeit abrufbare
#: Gegenstueck zur einmaligen Begruessung, beide erklaeren dasselbe (dass
#: der Bot auf alles antwortet, wie Interviews laufen) in derselben
#: Reihenfolge und mit denselben Worten, damit sich niemand an zwei
#: widerspruechliche Erklaerungen erinnern muss.
_TEXT_HILFE = (
    "Schreibt oder sprecht einfach - ich lese alles mit und antworte.\n\n"
    "SO MACHT IHR EIN INTERVIEW:\n"
    "1. \"Interview starten\" antippen\n"
    "2. Die Sprachnachrichten eurer Interviewpartnerin schicken, so viele "
    "ihr wollt - sie gehoeren alle zu diesem einen Interview\n"
    "3. Nach jeder schicke ich euch den abgetippten Text zum Mitlesen, und "
    "darunter fragt ein Knopf, ob das Interview weitergeht oder fertig ist. "
    "Steht da ein Wort falsch, sagt es mir einfach.\n"
    "4. Nach \"Interview ist fertig\" stehen die naechsten Schritte als "
    "Knoepfe da: Auswerten, Naechstes Interview, Weiter zur naechsten "
    "Station.\n\n"
    "Die Knoepfe sind der Weg. Wer lieber tippt, kann auch diese Befehle "
    "benutzen:\n"
    "/aufnahme - Interview starten und beenden\n"
    "/stand - zeigt, was ich mir bisher gemerkt habe\n"
    "/auswerten [nummer] - was in den Interviews steckt\n"
    "/kernthema <text> - das Kernthema festlegen\n"
    "/stueck rahmen <text> - Ort, Zeit, Anlass des Abends\n"
    "/szene <nummer> form <dialog|monolog|chor|lied|rap>\n"
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


def _aufnahmen_mit_anzeige(conn, chat_id: int) -> list[tuple[str, str]]:
    """(gespeicherter Name, Anzeigename) je benannter Aufnahme. Ohne
    Pseudonyme sind beide gleich; mit Pseudonymen (E8) zeigt der Bot
    "Interview N" und nimmt beides an -- was er zeigt, muss die Gruppe auch
    tippen koennen."""
    return [(a["name"], aufnahme.anzeigename(conn, a, a["name"]))
            for a in repo.transkripte(conn, chat_id) if a["name"]]


def _wortlaut_liste(conn, chat_id: int) -> str:
    namen = [anzeige for _, anzeige in _aufnahmen_mit_anzeige(conn, chat_id)]
    if not namen:
        return T._TEXT_KEINE_AUFNAHMEN
    return T._TEXT_NAME_UNBEKANNT.format(namen=", ".join(namen))


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
    steht sichtbar in der Antwort.

    Zwei Aenderungen vom 05.09.2026 (Live-Lauf Gruppe 1):

    * Der Start setzt die Phase auf 3, wenn die Gruppe noch in 1 oder 2 steht
      (``aufnahme.stelle_phase_interviews_sicher``) -- sonst stuende im
      Einstieg "Weiter zu Phase 3" neben "Aufnahme starten".
    * Unter der Startbestaetigung haengt **kein** Knopf mehr
      (``knopf=False``): "Aufnahme beenden" direkt unter "Aufnahme laeuft"
      war eine Fehldruck-Falle (14:21:32 gestartet, 14:21:39 beendet). Die
      Beenden-Moeglichkeit kommt mit dem ersten Teil-Transkript
      (``knoepfe.biete_nach_teil``), der Text sagt das."""
    if repo.ist_interviewmodus_an(conn, chat_id):
        kopf_id = aufnahme.beende_interview(conn, chat_id)
        knoepfe.biete_aufnahme(conn, tg, chat_id, T._TEXT_INTERVIEW_AUS)
        if kopf_id is not None and klm is not None:
            aufnahme.starte_abschluss(conn, tg, klm, e, kopf_id)
        return
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, chat_id)
    aufnahme.stelle_phase_interviews_sicher(conn, tg, chat_id, quelle="befehl")
    knoepfe.biete_aufnahme(conn, tg, chat_id, T._TEXT_INTERVIEW_AN, knopf=False)
    # Beim ersten Interviewstart geht der Leitfaden EINMAL mit raus
    # (06.09.2026): die Gruppe steht in dem Moment vor einer fremden Person
    # und braucht Eroeffnung, Einleitungen und Fragen an einer Stelle. Danach
    # nur noch auf Nachfrage (``leitfaden.sende_einmal``) -- sonst schoebe er
    # vor jedem Interview das Transkript aus dem Bild.
    leitfaden.sende_einmal(conn, tg, chat_id, e=e)


def _befehl_leitfaden(conn, tg, chat_id: int, e=None) -> None:
    """``/leitfaden`` -- der Gespraechsleitfaden auf Zuruf.

    Nicht beworben (er steht in keiner ``BEFEHLE_LISTE``, in keinem
    ``_TEXT_*`` und in keinem Prompt): der Weg ist der Knopf
    (``knoepfe._leitfaden_knopf``). Der Befehl ist der Notausgang fuer den
    Fall, dass der Knopf gerade nicht dasteht -- dieselbe Rolle wie bei den
    anderen zehn.

    Kein Modellaufruf: ``leitfaden.baue`` setzt nur zusammen, was schon in
    der Datenbank steht."""
    leitfaden.sende(conn, tg, chat_id, e=e)


def _befehl_interview(conn, tg, chat_id: int) -> None:
    """Modus an -- und damit entsteht EIN Interview (§ 10.6), zu dem alle
    folgenden Sprachnachrichten als Teile gehoeren."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, chat_id)
    aufnahme.stelle_phase_interviews_sicher(conn, tg, chat_id, quelle="befehl")
    tg.sende(chat_id, T._TEXT_INTERVIEW_AN)


def _befehl_fertig(conn, tg, klm, e, chat_id: int) -> None:
    """Modus aus, Interview zusammenfuegen und einmal verdichten (§ 10.6).

    Die Verdichtung laeuft in einem eigenen Thread (``aufnahme.starte_abschluss``)
    -- die Zusage 'kein Befehl ruft synchron ein Modell' gilt weiter. Ohne
    ``klm`` (ein Aufrufer ohne Sprachmodell) bleibt das Interview auf
    'transkribiert' stehen und der Nachhol-Arbeiter verdichtet es."""
    kopf_id = aufnahme.beende_interview(conn, chat_id)
    tg.sende(chat_id, T._TEXT_INTERVIEW_AUS)
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
        namen = [aufnahme.anzeigename(conn, a, a["name"])
                 for a in aufnahme.interviews(conn, chat_id) if a["name"]]
        tg.sende(
            chat_id,
            T._TEXT_KEINE_AUFNAHMEN if not namen
            else T._TEXT_INTERVIEW_UNBEKANNT.format(namen=", ".join(namen)),
        )
        return
    name = aufnahme.anzeigename(conn, kopf, knoepfe.T._TEXT_DAS_INTERVIEW_ANFANG)
    if aufnahme.zeige_verdichtung(conn, tg, e, kopf["id"]):
        # Schon verdichtet: die vorhandene Auswertung wird ausgespielt, nicht
        # ein zweites Mal erzeugt (05.09.2026). Vorher stand hier nur "ist
        # schon ausgewertet." -- und die Gruppe bekam den Inhalt nie zu sehen,
        # obwohl er in der Datenbank lag.
        return
    if klm is None:
        log.error("/auswerten ohne Sprachmodell aufgerufen, chat_id=%s", chat_id)
        tg.sende(chat_id, T._TEXT_AUSWERTEN_UNMOEGLICH)
        return
    tg.sende(chat_id, knoepfe.T._TEXT_ICH_WERTE_AUS.format(name=name))
    aufnahme.starte_auswertung(conn, tg, klm, e, kopf["id"])


def _befehl_stueck(conn, tg, chat_id: int, rest: str) -> None:
    """``/stueck rahmen <text>`` -- das Ergebnis von Phase 5.

    Ohne Feld zeigt er den Rahmen -- so ist ``/stueck`` zugleich die Antwort
    auf "was haben wir da nochmal festgelegt", ohne den ganzen ``/stand``.

    ``format`` bleibt seit dem 05.09.2026 abends als **stilles Synonym**
    erhalten: die Spalte ``arbeitsstand.format`` gibt es weiter, und ein
    Bot-Neustart soll einen alten Befehl nicht mit einem Fehler beantworten.
    Beworben wird sie nicht mehr -- das Format des Stuecks ist keine Frage
    mehr, die der Bot stellt (Birk: "wir wollen immer zuerst ein Textbuch;
    wie wir inszenieren, ist unser Ding").

    ``aus`` als Wert nimmt das Feld wieder weg, wie bei ``/kernthema aus``."""
    felder = T._STUECK_FELDER
    feld, _, wert = rest.partition(" ")
    feld = feld.strip().lower()
    feld = sprache.je_sprache({"de": {}, "en": _STUECK_SYNONYME_EN}).get(feld, feld)
    wert = wert.strip()

    if not feld:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        gesetzt = (stand["rahmen"] if stand else None) or ""
        zeilen = [T._TEXT_RAHMEN_ZEILE.format(rahmen=gesetzt) if gesetzt
                  else T._TEXT_RAHMEN_OFFEN]
        zeilen.append(T._TEXT_RAHMEN_SETZEN)
        tg.sende(chat_id, "\n".join(zeilen))
        return

    if feld not in felder:
        tg.sende(chat_id, T._TEXT_STUECK_UNBEKANNT)
        return

    bezeichnung = felder[feld]
    if not wert:
        beispiel = T._BEISPIEL_ARBEITSSTAND[feld]
        tg.sende(
            chat_id,
            T._TEXT_STUECK_WERT_LEER.format(
                bezeichnung=bezeichnung, feld=feld, beispiel=beispiel),
        )
        return
    if _ist_aus(wert):
        entfernt = erkenner.entferne(conn, chat_id, feld, quelle="befehl")
        tg.sende(chat_id, _melde_entfernt(
            entfernt, T._TEXT_STUECK_NICHT_GESETZT.format(bezeichnung=bezeichnung)))
        return
    repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    tg.sende(chat_id, T._TEXT_STUECK_NOTIERT.format(bezeichnung=bezeichnung, wert=wert))


#: Beispiele fuer die Hilfezeilen von /stueck -- konkret, damit
#: sichtbar ist, wie lang die Angabe sein soll (eine Zeile, kein Aufsatz).
_BEISPIEL_ARBEITSSTAND = {
    "format": "Sprechtheater: Dialog und Chor",
    "rahmen": "Ein Wartezimmer, an einem Nachmittag",
}

#: "/stueck setting <text>" -- das englische Wort fuer das Feld ``rahmen``
#: (Aufgabe 22). Nach aussen heisst ``rahmen`` ohnehin "Setting".
_STUECK_SYNONYME_EN = {"setting": "rahmen"}


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
            tg.sende(chat_id, T._TEXT_KERNTHEMA_LEER)
        return
    if _ist_aus(rest):
        entfernt = erkenner.entferne(conn, chat_id, "kernthema", quelle="befehl")
        tg.sende(chat_id, _melde_entfernt(entfernt, T._TEXT_KERNTHEMA_NICHT_GESETZT))
        return
    repo.setze_arbeitsstand(conn, chat_id, "kernthema", rest)
    tg.sende(chat_id, knoepfe.T._TEXT_KERNTHEMA_NOTIERT.format(kernthema=rest))


def _melde_entfernt(entfernt: dict | None, wenn_nichts: str) -> str:
    """Die Antwort auf einen Entfernen-Befehl: was weg ist, oder warum
    nichts passiert ist.

    Anders als beim Erkenner (der still bleibt, wenn er nichts findet) sagt
    ein Befehl immer etwas: wer ``/figur Peter entfernen`` tippt, wartet auf
    eine Antwort, und Schweigen sieht aus wie ein kaputter Bot."""
    if entfernt is None:
        return wenn_nichts
    return T._TEXT_ENTFERNT.format(wert=entfernt["wert"])


def _befehl_figur(conn, tg, chat_id: int, rest: str) -> None:
    """``/figur <Name> entfernen`` -- der deterministische Weg, eine Figur
    wegzunehmen (NACHTRAG N3 letzter Absatz).

    Bewusst nur der Entfernungsweg: Figuren ANlegen erledigt der Erkenner im
    Gespraech (art ``figur_setzen``), und ein zweiter Schreibweg fuer
    dasselbe waere genau die Doppelung, die die Befehlsliste am ersten
    Workshoptag von fuenfzehn auf sechs gebracht hat."""
    name, _, schlusswort = rest.rpartition(" ")
    woerter = sprache.je_sprache(_ENTFERNEN_JE_SPRACHE)
    if schlusswort.lower().strip(".") not in woerter or not name.strip():
        tg.sende(chat_id, T._TEXT_FIGUR_HILFE)
        return
    entfernt = erkenner.entferne(
        conn, chat_id, f"figur {name.strip()}", quelle="befehl"
    )
    tg.sende(
        chat_id,
        _melde_entfernt(entfernt, T._TEXT_FIGUR_UNBEKANNT.format(name=name.strip())),
    )


#: Der Kopf der Liste, die ``/festlegung`` ohne Argument zeigt.
_TEXT_FESTLEGUNG_KOPF = "Festgehalten, ausserhalb der Felder:"
_TEXT_FESTLEGUNG_LEER = "Ausserhalb der Felder ist noch nichts festgehalten."
#: Eine Zeile Syntax, nach dem Muster von ``_TEXT_PHASE_UMSCHALTEN``.
_TEXT_FESTLEGUNG_HILFE = (
    "Neu: /festlegung struktur: nur eine Szene - "
    "zurueck: /festlegung weg <suchwort>. "
    "Bereiche: figur, gruppe, ort, struktur, form, stil, sonstiges."
)
_TEXT_FESTLEGUNG_SCHON_DA = "Das steht schon so da."
_TEXT_FESTLEGUNG_UNBEKANNT = "Dazu habe ich nichts festgehalten."

#: "weg" als erstes Wort nimmt zurueck. Eng gefasst und nur dieses eine Wort:
#: "/festlegung wegstrecke: ..." soll eine Festlegung SETZEN.
_FESTLEGUNG_WEG = re.compile(r"^weg\s+(.+)$", re.IGNORECASE | re.DOTALL)
#: Englisch "remove"; "weg" gilt dort weiter (A4, die englische Hilfe nennt
#: "/festlegung weg <search word>").
_FESTLEGUNG_WEG_EN = re.compile(r"^remove\s+(.+)$", re.IGNORECASE | re.DOTALL)


def _befehl_festlegung(conn, tg, chat_id: int, rest: str) -> None:
    """``/festlegung <bereich>[/<bezug>]: <text>`` und ``/festlegung weg
    <suchwort>`` -- der deterministische Weg in die Auffangtabelle
    (docs/analyse-phase4-datenverlust-2026-09-06.md § 4.1).

    **Die Rueckfallebene, nicht der Komfortweg** (Analyse § 4.4 Risiko 4).
    Der Regelweg ist die Erkenner-art ``festlegung_setzen``; die laeuft ueber
    ein Modell, und das ist am 06.09. mitten in Phase 4 mit HTTP 5xx
    ausgefallen (``vorfall`` id 19). Ohne diesen Befehl gaebe es in so einem
    Moment keinen Weg, eine Festlegung abzulegen.

    Nirgends beworben, wie ``/leitfaden``: die Gruppe soll keine Befehle
    lernen muessen, sie sagt es einfach. Wer ihn kennt, ist das
    Workshop-Team.

    Geantwortet wird immer -- auch wenn nichts passiert ist. Anders als der
    Erkenner (der still bleibt, wenn er nichts findet) wartet hier jemand auf
    eine Antwort, und Schweigen sieht aus wie ein kaputter Bot."""
    rest = (rest or "").strip()
    if not rest:
        zeilen = [
            repo.festlegungszeile(z["bereich"], z["bezug"], z["text"])
            for z in repo.festlegungen(conn, chat_id)
        ]
        kopf = (
            T._TEXT_FESTLEGUNG_KOPF + "\n" + "\n".join(zeilen)
            if zeilen
            else T._TEXT_FESTLEGUNG_LEER
        )
        tg.sende(chat_id, f"{kopf}\n\n{T._TEXT_FESTLEGUNG_HILFE}")
        return

    weg = next(filter(None, (
        muster.match(rest) for muster in sprache.je_sprache(
            {"de": (_FESTLEGUNG_WEG,), "en": (_FESTLEGUNG_WEG_EN, _FESTLEGUNG_WEG)})
    )), None)
    if weg:
        # Ueber ``erkenner.entferne`` und nicht direkt ueber ``repo``: es gibt
        # fuer beide Wege -- gesprochen und getippt -- nur eine Wahrheit, und
        # die Journalzeile faellt dabei mit ab.
        entfernt = erkenner.entferne(
            conn, chat_id, f"festlegung {weg.group(1).strip()}", quelle="befehl"
        )
        tg.sende(chat_id, _melde_entfernt(entfernt, T._TEXT_FESTLEGUNG_UNBEKANNT))
        return

    # Dieselbe Zerlegung wie beim Erkenner: ein Format, nicht zwei.
    bereich, bezug, text = erkenner._zerlege_festlegung(rest)
    if not text.strip():
        tg.sende(chat_id, T._TEXT_FESTLEGUNG_HILFE)
        return
    if repo.schreibe_festlegung(
        conn, chat_id, bereich, text, bezug=bezug, quelle="befehl"
    ) is None:
        tg.sende(chat_id, T._TEXT_FESTLEGUNG_SCHON_DA)
        return
    tg.sende(
        chat_id,
        T._TEXT_FESTGEHALTEN.format(
            zeile=repo.festlegungszeile(bereich, bezug, text.strip())),
    )


def wechsle_phase(conn, tg, klm, e, chat_id: int, nummer: int,
                  quelle: str = "befehl") -> None:
    """Die Phase umschalten -- der EINE Weg fuer Befehl und Klick
    (30.09.2026, Karte W).

    Birk, 30.09.2026: die Phase soll per Klick in der Phasenuebersicht
    umschaltbar sein, "weg von reiner chat navigation". Das ist kein
    Widerspruch zu "Die Phase setzt allein die Gruppe" -- ein Klick IST die
    Gruppe; verworfen bleibt allein der automatische Sprung aus dem
    Datenstand.

    Damit ein Klick nie in einer anderen Phase landet als ein Befehl, laufen
    beide hier durch: ``quelle`` ist der einzige Unterschied ('befehl' gegen
    'web') und steht im Journal.

    Geantwortet wird immer, auch wenn die Phase schon stimmte; ins Journal
    geht der Eintrag nur bei einer echten Aenderung (``phasen.setze``)."""
    phasen.setze(conn, chat_id, nummer, quelle)
    tg.sende(chat_id, phasen.meldung(nummer))
    # Derselbe Rahmen wie ueber den Knopf (06.09.2026): Kopfzeile,
    # Einleitung, Checkliste und die Einstiegsknoepfe dieser Phase.
    try:
        knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, nummer)
    except Exception:
        log.exception("Phaseneintritt fehlgeschlagen, chat_id=%s", chat_id)


def _befehl_phase(conn, tg, chat_id: int, rest: str, klm=None, e=None) -> None:
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

    Das Umschalten selbst steht seit Karte W in ``wechsle_phase`` -- derselbe
    Weg, den auch ein Klick in der Web-Uebersicht nimmt (``/phaseklick``)."""
    if not rest:
        text = (
            T._TEXT_WIR_SIND_BEI.format(
                phase=phasen.bezeichnung(phasen.aktuelle(conn, chat_id)))
            + f"\n\n{phasen.liste()}\n\n{T._TEXT_PHASE_UMSCHALTEN}"
        )
        naechste = phasen.naechste_moegliche(conn, chat_id)
        if naechste is None:
            tg.sende(chat_id, text)
        else:
            knoepfe.biete_phase(conn, tg, chat_id, text, naechste)
        return
    nummer = phasen.nummer_fuer(rest, jetzige=phasen.aktuelle(conn, chat_id))
    if nummer is None:
        tg.sende(chat_id, f"{T._TEXT_PHASE_UNBEKANNT}\n\n{phasen.liste()}")
        return
    wechsle_phase(conn, tg, klm, e, chat_id, nummer, quelle="befehl")


def _befehl_phaseklick(conn, tg, klm, e, chat_id: int, rest: str) -> None:
    """Der Klick auf eine Phase in der Web-Uebersicht (30.09.2026, Karte W).

    **Versteckt**: nirgends beworben, nicht im Menue -- er ist kein Befehl
    zum Tippen, sondern der Weg des Knopfes durch die Naht von Karte A2. Der
    Webserver kann die Phase nicht selbst setzen (kein ``klm``, und
    ``eintritt_in_phase`` stoesst Modellarbeit in Threads an); er legt
    stattdessen einen gewoehnlichen Eingang ab, und der Bot fuehrt ihn aus.

    Genau derselbe Weg wie ``/phase N`` -- nur die Journalquelle ist 'web'."""
    nummer = phasen.nummer_fuer(rest, jetzige=phasen.aktuelle(conn, chat_id))
    if nummer is None:
        log.warning("Phasenklick ohne gueltige Nummer: %r (chat_id=%s)", rest, chat_id)
        return
    wechsle_phase(conn, tg, klm, e, chat_id, nummer, quelle="web")


def _befehl_stand(conn, tg, chat_id: int, e=None) -> None:
    """Baut die Stand-Antwort ausschliesslich aus der Datenbank -- ohne
    Sprachmodell, kann also nicht am LLM scheitern (teil-b.md Aufgabe 6).

    Die Phase steht zuerst: sie ordnet alles darunter ein. Danach je Phase
    bis zur aktuellen ein Block mit **denselben** Parameterzeilen, die auch
    die Eintritts- und die Abschlussnachricht zeigen
    (``phasentexte.standzeilen``, 06.09.2026). Eine Liste, drei Leser -- ein
    zweiter Ort waere ein zweiter Stand.

    Kernthema und Hauptkonflikt stehen weiter am Ende: sie sind seit dem
    Umbau vom 05.09.2026 keiner Phase mehr zugeordnet, bleiben aber
    rueckwaertskompatibel im Code und in bestehenden Gruppen."""
    from interview_theater import fehlstellen, phasentexte

    stand = repo.hole_arbeitsstand(conn, chat_id)
    gruppe = repo.hole_gruppe(conn, chat_id)
    interviewmodus_an = gruppe is not None and gruppe["interviewmodus_seit"] is not None
    jetzige = phasen.aktuelle(conn, chat_id)

    zeilen = [T._TEXT_STAND_KOPF]
    zeilen.append(T._TEXT_STAND_PHASE.format(phase=phasen.bezeichnung(jetzige)))
    # Alle acht Bloecke, nicht nur die bis zur aktuellen Phase: der Stand ist
    # die Uebersicht ueber das ganze Stueck, und eine Gruppe, die aus Phase 7
    # nach 2 zurueckgesprungen ist, soll ihre Szenen darin nicht verlieren.
    # Was noch nicht dasteht, steht als "noch keine"/"noch offen" da -- das
    # ist die Information, nicht ihre Abwesenheit.
    for nummer, _, _ in phasen.PHASEN:
        block = phasentexte.standzeilen(conn, chat_id, nummer)
        if not block:
            continue
        zeilen.append("")
        zeilen.append(f"{phasen.bezeichnung(nummer)}")
        zeilen.extend(block)
    zeilen.append("")
    # Je geschriebener Szene eine Zeile, was in ihr passiert (06.09.2026).
    # Sie steht nach den Phasenbloecken und vor dem Kernthema: das ist der
    # Inhalt des Stuecks, und eine Gruppe, die ``/stand`` aufruft, sucht
    # genau ihn -- die Phasenbloecke nennen nur Nummer, Titel und Form.
    fassungen = phasentexte.zusammenfassungszeilen(conn, chat_id)
    if fassungen:
        zeilen.append(T._TEXT_WAS_BISHER)
        zeilen.extend(fassungen)
        zeilen.append("")
    # Und was noch fehlt (06.09.2026): dieselbe Datenlage, andere Richtung.
    # Die Phasenbloecke oben sagen, was **dasteht**; diese Liste macht daraus
    # eine Arbeitsliste. Sie erscheint **nur, wenn es Fehlstellen gibt** --
    # eine Zeile "nichts fehlt" waere Laerm. Reine Leseabfrage
    # (``fehlstellen.zeilen``), kein Modellaufruf.
    offen = fehlstellen.zeilen(conn, chat_id)
    if offen:
        zeilen.append(f"{fehlstellen.T.UEBERSCHRIFT}:")
        zeilen.extend(offen)
        zeilen.append("")
    if stand and stand["kernthema"]:
        zeilen.append(T._TEXT_STAND_KERNTHEMA.format(wert=stand["kernthema"]))
    # Der Hauptkonflikt steht nur da, wenn es einen gibt (05.09.2026): er ist
    # eine moegliche Rahmen-Entscheidung, keine Pflicht -- und eine Zeile
    # "Hauptkonflikt: noch offen" liest sich wie eine Luecke, die zu fuellen
    # waere.
    if stand and stand["hauptkonflikt"]:
        zeilen.append(T._TEXT_STAND_HAUPTKONFLIKT.format(wert=stand["hauptkonflikt"]))
    zeilen.append(T._TEXT_INTERVIEWMODUS_AN if interviewmodus_an
                  else T._TEXT_INTERVIEWMODUS_AUS)
    url = repo.gruppenseite_url(conn, chat_id, getattr(e, "web_url", ""))
    if url:
        zeilen.append(T._TEXT_ZUM_MITLESEN.format(url=url))

    # Steht die naechste Phase offen, haengt der Knopf "Weiter zu <Phase>"
    # unter dem Stand (06.09.2026, Nacht-Simulation Punkt 6). ``/stand`` ist
    # der Griff, zu dem eine Gruppe greift, wenn sie die Orientierung sucht
    # -- und genau dann soll der naechste Schritt ein Druck sein und nicht
    # der versteckte Befehl ``/phase``. Reine Leseabfrage, kein Modellaufruf;
    # der Merkposten bleibt unberuehrt, weil dieser Knopf keine eigene
    # Angebotsnachricht ist.
    text = "\n".join(zeilen)
    naechste = phasen.naechste_moegliche(conn, chat_id)
    if naechste is None or naechste <= jetzige:
        tg.sende(chat_id, text)
        return
    try:
        knoepfe.biete_phase(conn, tg, chat_id, text, naechste)
    except Exception:
        log.exception("Phasenknopf unter /stand fehlgeschlagen, chat_id=%s", chat_id)
        tg.sende(chat_id, text)


def _befehl_wortlaut(conn, tg, chat_id: int, rest: str) -> None:
    if _ist_aus(rest):
        repo.setze_wortlaut_modus(conn, chat_id, None)
        tg.sende(chat_id, T._TEXT_WORTLAUT_AUS)
        return
    if not rest:
        repo.setze_wortlaut_modus(conn, chat_id, "*")
        tg.sende(chat_id, T._TEXT_WORTLAUT_ALLE)
        return
    # Nur gegen das, was der Bot zeigt: ohne Pseudonyme ist das der
    # gespeicherte Name; mit Pseudonymen (E8) "Interview N" -- ein
    # gespeicherter Name "Interview 3" traefe sonst nach einem entfernten
    # Interview eine andere Aufnahme als die gezeigte.
    treffer = next(
        ((name, anzeige) for name, anzeige in _aufnahmen_mit_anzeige(conn, chat_id)
         if rest.lower() == anzeige.lower()),
        None,
    )
    if treffer is None:
        # Unbekannter Name: die vorhandenen aufzaehlen statt zu raten
        # (teil-b.md Aufgabe 6).
        tg.sende(chat_id, _wortlaut_liste(conn, chat_id))
        return
    repo.setze_wortlaut_modus(conn, chat_id, treffer[0])
    tg.sende(chat_id, T._TEXT_WORTLAUT_AN.format(name=treffer[1]))


def _befehl_hilfe(tg, e, chat_id: int) -> None:
    tg.sende(chat_id, T._TEXT_HILFE.format(bot_name=e.bot_name))


def _setze_szenenfeld(conn, tg, chat_id: int, rest: str) -> bool:
    """``/szene <n> <feld> <wert>`` -- der deterministische Korrekturweg zu
    den Szenenfeldern (05.09.2026), neben der Erkenner-art ``szene_planen``.

    Liefert True, wenn der Text als Feldkorrektur gelesen wurde -- dann ist
    der Befehl erledigt. Sonst False, und ``_befehl_szene`` macht mit dem
    Entfernungs- und dem Schreibweg weiter.

    Die Abgrenzung ist eng: der zweite Token muss ein bekannter Feldname sein
    (``szene.FELD_ALIASE``). Alles andere ist ein Schreibauftrag -- "/szene 2
    nochmal, aber kuerzer" darf nicht als Feld 'nochmal' enden."""
    treffer = sprache.je_sprache({"de": _SZENE_FELD, "en": _SZENE_FELD_EN}).match(rest)
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
            tg.sende(chat_id, T._TEXT_SZENE_FIGUR_UNBEKANNT.format(namen=wert))
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
        tg.sende(chat_id, T._TEXT_SZENE_LEER)
        return
    # /szene usa ja|nein -- die Antwort auf das Einwilligungs-Angebot, ohne
    # dass sie der Erkenner treffen muss. In der Simulation am 05.09. las er
    # "ja stimmt alles" als Zustimmung zu den Figuren, nicht zur USA-Frage;
    # der Bot wiederholte daraufhin siebenmal dieselbe Erinnerung.
    usa = _SZENE_USA.match(rest)
    if usa:
        ja = usa.group(1).lower() in ("ja", "j", "yes")
        repo.setze_szene_usa(conn, chat_id, ja)
        # Wortgleich mit knoepfe._TEXT_USA_JA/_NEIN (und szene._TEXT_USA_*):
        # auf die Knopftexte verweisen statt eine weitere Kopie anzulegen.
        tg.sende(chat_id, szene.T._TEXT_USA_JA if ja else szene.T._TEXT_USA_NEIN)
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
    form_leer = sprache.je_sprache(
        {"de": _SZENE_FORM_LEER, "en": _SZENE_FORM_LEER_EN}).match(rest)
    if form_leer:
        knoepfe.biete_szenenform(conn, tg, chat_id, int(form_leer.group(1)))
        return
    if _setze_szenenfeld(conn, tg, chat_id, rest):
        return
    entfernung = sprache.je_sprache(
        {"de": _SZENE_ENTFERNEN, "en": _SZENE_ENTFERNEN_EN}).match(rest)
    if entfernung:
        nummer = entfernung.group(1)
        entfernt = erkenner.entferne(conn, chat_id, f"szene {nummer}", quelle="befehl")
        tg.sende(
            chat_id, _melde_entfernt(entfernt, T._TEXT_SZENE_UNBEKANNT.format(nummer=nummer))
        )
        return
    if klm is None:
        log.error("/szene ohne Sprachmodell aufgerufen, chat_id=%s", chat_id)
        tg.sende(chat_id, T._TEXT_SZENE_UNMOEGLICH)
        return
    szene.starte(conn, tg, klm, e, chat_id, rest)


def _befehl_sprache(conn, tg, chat_id: int, rest: str) -> None:
    """``/sprache`` zeigt, ``/sprache auto|it|en|…`` setzt die Whisper-Sprache
    dieser Gruppe (Karte A1). Kein Modellaufruf."""

    def anzeige(wert: str) -> str:
        return (T._TEXT_SPRACHE_AUTO if wert == sprache.AUTO
                else sprache.SPRACHNAMEN.get(wert, wert))

    wert = rest.strip().lower()
    if not wert:
        tg.sende(chat_id, T._TEXT_SPRACHE_STAND.format(
            sprache=anzeige(aufnahme.whisper_sprache(conn, chat_id))))
        return
    if not _SPRACHWERT.match(wert):
        tg.sende(chat_id, T._TEXT_SPRACHE_UNBEKANNT)
        return
    repo.setze_stt_sprache(conn, chat_id, wert)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          T._JOURNAL_SPRACHE.format(sprache=wert), quelle="befehl")
    tg.sende(chat_id, T._TEXT_SPRACHE_GESETZT.format(sprache=anzeige(wert)))


#: Die erkannten Befehle -- Grundlage dafuer, dass ein unbekannter
#: Slash-Text (z. B. "/irgendwas") freundlich beantwortet statt zu krachen.
#: ``/aufnahme`` ist seit 05.09.2026 der beworbene Weg; ``/interview`` und
#: ``/fertig`` bleiben als stille Synonyme gueltig (Muskelgedaechtnis), stehen
#: aber nicht mehr im Menue.
_BEKANNTE_BEFEHLE = {
    "/aufnahme", "/interview", "/fertig", "/auswerten", "/phase", "/kernthema",
    "/stueck", "/figur", "/szene", "/stand", "/wortlaut", "/hilfe",
    # Versteckt: nirgends beworben, aber gueltig (06.09.2026). Der Weg zum
    # Leitfaden ist der Knopf; dieser Befehl ist der Notausgang.
    "/leitfaden",
    # Ebenfalls versteckt: der Regelweg in die Auffangtabelle ist die
    # Erkenner-art ``festlegung_setzen``, dieser Befehl die Rueckfallebene
    # fuer den Fall, dass das Erkenner-Modell ausfaellt.
    "/festlegung",
    # Versteckt (Karte A1): die Whisper-Sprache dieser Gruppe zeigen oder
    # umstellen. Der Weg ist der Knopf in Phase 3.
    "/sprache",
    # Versteckt (Karte W, 30.09.2026): der Klick auf eine Phase in der
    # Web-Uebersicht. Kein Befehl zum Tippen -- der Weg des Knopfes durch
    # die Naht, siehe ``_befehl_phaseklick``.
    "/phaseklick",
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
        # Knoepfe statt einer Zeile, die einen weiteren Befehl empfiehlt
        # (05.09.2026): der naechste Schritt ist ein Druck, kein zweiter
        # Tippversuch.
        try:
            knoepfe.biete_einstieg(conn, tg, chat_id, T._TEXT_UNBEKANNT)
        except Exception:
            log.exception("Einstiegsknoepfe fehlgeschlagen, chat_id=%s", chat_id)
            tg.sende(chat_id, T._TEXT_UNBEKANNT)
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
        _befehl_phase(conn, tg, chat_id, rest, klm=klm, e=e)
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
    elif befehl == "/leitfaden":
        _befehl_leitfaden(conn, tg, chat_id, e)
    elif befehl == "/festlegung":
        _befehl_festlegung(conn, tg, chat_id, rest)
    elif befehl == "/sprache":
        _befehl_sprache(conn, tg, chat_id, rest)
    elif befehl == "/phaseklick":
        _befehl_phaseklick(conn, tg, klm, e, chat_id, rest)
    return True


T = sprache.Texte(__name__)

"""Aufnahme-Pipeline: der Weg einer Sprachnachricht von der Ankunft bis zum
fertigen Material (Aufgabe 8, SPEC-kontext-architektur.md § 10).

Sprache ist hier nicht nur Interview-Material: die Gruppe spricht auch normale
Arbeitskommunikation und Regieanweisungen ein. Die Dauer einer Sprachnachricht
sagt darueber nichts aus (§ 10.1, teil-b.md Aufgabe 5) -- ein Interview kann
aus fuenf kurzen Sprachnachrichten bestehen, eine Regieanweisung laenger als
eine Minute dauern. Stattdessen entscheidet ``gruppe.interviewmodus_seit``,
den die Gruppe ausdruecklich schaltet (durch Saetze wie "wir machen jetzt ein
Interview" ueber den Absichtserkenner, oder durch /interview und /fertig).

**Ein Interview ist eine Einheit** (Nachtrag 05.09.2026, § 10.6). Das ist die
Korrektur aus dem Probelauf vom 04.09. abends: ein Interview bestand aus fuenf
Sprachnachrichten, der Code machte daraus fuenf Aufnahmen und fuenf
Verdichtungen, zwei davon leer ("Material extrem kurz"), und die Gruppe hoerte
fuenfmal "Ich hoere durch" und danach nichts. Seitdem gilt:

* **lang** = der Interview-KOPF. Entsteht beim Einschalten des Modus, traegt
  Name ("Interview 3"), zusammengefuegtes Transkript und Verdichtung, hat
  selbst kein Audio und wartet auf ``status='laeuft'``.
* **teil** (Modus an) = eine einzelne Sprachnachricht dieses Interviews. Wird
  transkribiert und das Transkript **sofort woertlich in den Chat gestellt**
  ("Interview 3, Teil 2: ..."): zur Kontrolle, solange die interviewte Person
  noch im Raum ist. Kein Modellaufruf, kein Kommentar, keine Zusammenfassung
  -- und keine Empfangsbestaetigung mehr, das Transkript IST sie.
* **kurz** (Modus aus): ein Gespraechsbeitrag. Latenz zerstoert den Fluss,
  darum ein knappes Zeitbudget; das Transkript wandert in dieselbe
  Nachrichtenzeile und loest einen Gespraechszug aus.

Verdichtet wird **einmal je Interview**, wenn die Gruppe "fertig" sagt
(``beende_interview`` → ``schliesse_ab``), ueber das zusammengefuegte
Transkript aller Teile -- und die Verdichtung geht als inhaltliche Rueckmeldung
in den Chat ("Interview 3 ist durch. Was ich darin hoere: ..."). Genau die
fehlte im Probelauf.

Wird der Modus zu starten vergessen, ist die Sprachnachricht trotzdem als
Klasse *kurz* gespeichert (§ 10.2) und kann nachtraeglich zugeordnet werden --
nichts geht verloren. Eine besonders lange Sprachnachricht ausserhalb des
Modus bekommt stattdessen einen beilaeufigen Hinweis an der ohnehin faelligen
Antwort (HINWEIS_AB_S), keine Rueckfrage (SPEC § 1.4, § 10.1: eine Rueckfrage
braucht wartenden Zustand, genau das Konstrukt, das ersatzlos gestrichen wurde).

**Die eigentliche Absicherung (§ 10.2):** ``empfange()`` laedt die Datei herunter
und legt ``status='empfangen'`` an, OHNE jemals Whisper zu fragen -- es gibt in
dieser Funktion keinen STT-Klienten. Faellt Whisper aus, liegt das Material
trotzdem da; der Nachhol-Arbeiter (``nachholen()``) holt es spaeter nach.

Alle Klassen durchlaufen dieselbe Statusmaschine in der Tabelle ``aufnahme``:
``empfangen`` → ``transkribiert`` → ``fertig`` (oder ``fehlgeschlagen`` nach
MAX_VERSUCHE erfolglosen Anlaeufen); der Kopf beginnt bei ``laeuft``. Der
Zwischenstand ``transkribiert`` ist ein echter Wiederaufnahmepunkt: schlaegt
bei einem Interview nur die Verdichtung fehl (Transkript schon da), fragt ein
erneuter Anlauf nicht noch einmal Whisper, sondern verdichtet nur weiter.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from interview_theater import brainstorm, buehnenkarte, phasen, repo, sprache, stt, verdichter, workshop

log = logging.getLogger(__name__)

# Alle Schwellwerte an genau dieser Stelle (Auftragshinweis 5), Werte aus der
# Messung vom 03.09.2026 (76 Laeufe, Median 2,9 s, einziger Ausreisser 8,88 s,
# kein Lauf ueber 10 s). Nirgends im Code als Zahl wiederholt.
TIPPANZEIGE_AB_S = 5
MELDUNG_AB_S = 12
BUDGET_LANG_S = 90
#: War 45 (eigener, kuerzerer Wert) bis zum Pausen-Schnitt (VAD, 02.10.2026):
#: ein 'kurz'-Segment (Web, ausserhalb des Interviewmodus) kann seitdem
#: genauso bis zu IT_WEB_VAD_MAX_MS lang sein wie ein Interview-Teil --
#: BUDGET_KURZ_S ist ein Transkriptions-ZEITBUDGET (Upload + Whisper + ein
#: Retry, siehe stt.transkribiere), kein Laengen-Deckel, und 45 s waeren fuer
#: ein 90-Sekunden-Segment zu knapp bemessen.
BUDGET_KURZ_S = BUDGET_LANG_S
NACHHOL_INTERVALL_S = 60
MAX_VERSUCHE = 5

#: Ein Ende-Segment (Diskussion/Brainstorm, ``schnittgrund='ende'``) unter
#: dieser Dateigroesse geht gar nicht erst an Whisper, sondern wird sofort
#: verworfen und der Abschluss laeuft (Robo, Simulationslauf 05.10.2026
#: 14:26: 110 Bytes / 1 s, nur der WebM-Kopf -- Whisper meldete 'failed',
#: und der Nachhol-Arbeiter brauchte MAX_VERSUCHE x NACHHOL_INTERVALL_S, gut
#: fuenf Minuten). Die Grenze: der Client schneidet erst ab MIN_SPEECH_MS =
#: 500 ms Rede (``web_chat.py``); 500 ms Opus brauchen selbst bei sparsamen
#: 16 kbit/s 1000 Bytes, Kopf nicht mitgezaehlt. Darunter ist keine
#: Aeusserung moeglich.
LEERES_ENDE_MAX_BYTES = 1000

#: Unter dieser Wortzahl (ueber das ganze zusammengefuegte Interview) wird
#: **nicht verdichtet** (Nachtrag N2, 05.09.2026). Aus dem Probelauf: eine
#: Aufnahme von einer Sekunde ("Das Interview ist fertig.") und eine von vier
#: Sekunden ("Zeigt mir die Verdichtungen von den Interviews an.") wurden
#: beide als Interview verdichtet -- aus der zweiten erfand das Modell ein
#: komplettes Interview mit drei Themen. Ein Sprachmodell, dem man zu wenig
#: gibt, liefert trotzdem etwas; die einzige verlaessliche Abwehr ist, es
#: gar nicht erst zu fragen. Die Gruppe kann es mit ``/auswerten``
#: ueberstimmen -- ihr Urteil steht ueber der Zahl.
MINDEST_WOERTER = 40

#: Kein Klassifikations-Schwellwert (den gibt es seit Aufgabe 5 nicht mehr) --
#: nur der Ausloeser fuer den beilaeufigen Materialhinweis (§ 10.1): eine
#: Sprachnachricht ueber dieser Dauer, waehrend der Interviewmodus AUS ist,
#: bekommt eine angehaengte Zeile an der ohnehin faelligen Antwort, keine
#: eigene Nachricht und keine Rueckfrage.
HINWEIS_AB_S = 60

#: Endung des Zielpfads einer heruntergeladenen Aufnahme, wenn die Quelle
#: keine nennt. Telegram nennt keine -- der Web-Kanal nennt sie, weil
#: ``stt.mime_typ()`` den MIME-Typ aus der Endung ableitet (Falle 3).
ENDUNG_VORGABE = ".ogg"

#: Wortlaut aus SPEC § 10.4/§ 11.1, ohne Umlaute wie der uebrige Quelltext.
#: 05.09.2026 praezisiert (Birk: "worauf bezieht sich das? macht kein sinn in
#: dem kontext gerade"): "Ich hoer noch zu" klang wie eine Antwort auf das
#: Gespraech und passte nur, solange eine Aufnahme lief -- gemeint ist aber
#: immer dasselbe technische Warten, naemlich dass Whisper die Sprachnachricht
#: noch abtippt. Das steht jetzt da.
_TEXT_ZWISCHENMELDUNG = "Ich tippe die Sprachnachricht noch ab, einen Moment."
_TEXT_AUSFALL = (
    "Ich kann gerade nicht hoeren. Schreibt mir solange, ich sammle die "
    "Aufnahmen und hole sie nach."
)
_TEXT_RUECKKEHR = "Ich kann wieder hoeren."

#: Historisch (bis 06.09.2026): der beilaeufige Hinweis, der an einer
#: Gespraechsantwort hing, wenn eine lange Sprachnachricht ausserhalb des
#: Interviewmodus ankam. Ersetzt durch die deterministische Rueckfrage mit
#: zwei Knoepfen (``_TEXT_INTERVIEW_OHNE_KNOPF``) -- der Hinweis half nicht,
#: weil der Zug, an dem er hing, genau der Zug war, den es nicht geben durfte.
_TEXT_MATERIAL_HINWEIS = "Das klingt nach Material fuer ein Interview."

#: Die Rueckfrage nach einer langen Sprachnachricht ohne Interviewmodus
#: (06.09.2026, Live-Fall Gruppe 1). Die Dauer steht als M:SS darin, damit
#: die Gruppe erkennt, welche Aufnahme gemeint ist -- sie hat gerade drei
#: Minuten gesprochen und sieht sonst nur eine Frage ohne Bezug.
_TEXT_INTERVIEW_OHNE_KNOPF = (
    "Das klingt nach einem Interview ({dauer}). Soll ich es als Interview "
    "speichern?"
)

#: Die Folgefrage nach \"Ja, als Interview\": das Interview steht, aber es
#: koennen noch Sprachnachrichten dazukommen. Ohne diese Frage waere die
#: Gruppe im Interviewmodus, ohne es zu wissen.
_TEXT_INTERVIEW_OHNE_KNOPF_WEITER = (
    "Ist das Interview fertig, oder kommen noch Sprachnachrichten dazu?"
)

#: \"Nein, war ein Beitrag\": das Transkript wird sichtbar und der normale
#: Weg einmal nachgeholt.
_TEXT_INTERVIEW_OHNE_KNOPF_NEIN = "Gut, dann nehme ich es als Beitrag."

#: Brainstorm-Modus (Phase 4, nur Web, 02.10.2026): hoechstens EINE Zeile je
#: Karte, OHNE Inhalt (brief: "the chat must not become a long sausage").
#: Erscheint nicht zweimal hintereinander (repo.neueste_nachricht_text).
_TEXT_BUEHNE_NEUE_KARTE = "Neue Karte im Tab Bühne"

#: Die deterministische Aufforderung am Ende der Hintergrund-Diskussion
#: (Phase 1, Padua Phase 1+2 Umbau, 03.10.2026): sobald das letzte Segment
#: mit ``schnittgrund='ende'`` eintrifft, geht diese Zeile raus, BEVOR der
#: (nicht blockierende) Verdichtungslauf startet -- siehe
#: ``_diskussion_abschliessen`` und ``interview_theater.diskussion.starte``.
_TEXT_DISKUSSION_FERTIG_BEGRIFFE = (
    "Die Diskussion ist zu Ende. Schickt mir jetzt eure fuenf Begriffe dazu "
    "- getippt oder als Sprachnachricht."
)

#: Seit 05.10.2026 (Birk, Live-Test Gruppe 2) der Rueckfall nach "Discussion
#: done" an Stelle von ``_TEXT_DISKUSSION_FERTIG_BEGRIFFE`` (der alte Ablauf,
#: bleibt als Konstante stehen): das Board laeuft am Ende jetzt IMMER, sobald
#: es Transkript gibt (``begriffsboard.soll_laufen``). Dieser Satz kommt nur
#: noch, wenn nichts transkribiert wurde -- oder das Modell trotz Transkript
#: keinen Begriff lieferte. Keine Aufforderung "schickt mir fuenf".
_TEXT_DISKUSSION_KEINE_BEGRIFFE = (
    "Aus der Diskussion konnte ich keine Begriffe heraushoeren - tippt auf "
    "\"Zuhoeren starten\" und sprecht noch einmal, oder schreibt die Begriffe hier."
)

#: Wie lange der Ende-Schnitt der Diskussion auf noch offene Segmente
#: derselben Sitzung wartet (05.10.2026): sie werden im Pool parallel
#: transkribiert, und das kurze Ende-Segment ist oft vor dem vorigen fertig.
#: Ohne Warten liefe der Schlusslauf (und die Verdichtung) ueber ein
#: unvollstaendiges Transkript. Danach geht es trotzdem weiter (Vorfall
#: ``diskussion_ende_segmente_offen``) -- ein haengendes Segment darf den
#: Vorschlag nicht ewig aufhalten.
ENDE_WARTEN_S = 90.0
ENDE_WARTEN_TAKT_S = 0.5

#: Wie lange das Brainstorm-Ende auf den Kartenlauf des VORIGEN Bogens
#: wartet (t_cf87ee0a, Review I1): ein Lauf darf ``buehnenkarte.TIMEOUT_S``
#: dauern, plus Spielraum. Reicht auch das nicht, gibt es eine sichtbare
#: Schweigen-Zeile (``modell='belegt'``) statt gar keiner Reaktion.
ENDE_LAUF_WARTEN_S = buehnenkarte.TIMEOUT_S + 30.0

#: Das Transkript-Echo eines Teils (§ 10.6): woertlich, ohne Kommentar, ohne
#: Zusammenfassung. Der Kopf sagt, wozu es gehoert -- das ist der ganze
#: Unterschied zu "Ich hoere durch", das nichts zu kontrollieren gab.
_TEXT_TEIL_ECHO = "{name}, Teil {nummer}:\n{transkript}"

#: Padua (04.10.2026, Karte t_ea994c7f, ``[interview] fliesstext``): die
#: erste Zeile der EINEN Transkriptblase eines Interviews im Web-Chat.
#: Darunter, je durch eine Leerzeile getrennt, alle Teil-Transkripte als
#: Fliesstext -- ohne "Teil K:" (``transkript_blasentext``).
_TEXT_TRANSKRIPT_KOPF = "🎙 {name}"

#: Die inhaltliche Rueckmeldung, wenn ein Interview durch ist. Sie ist der
#: eigentliche Ertrag dieses Nachtrags -- bisher endete ein Interview ohne ein
#: Wort darueber, was darin steckt.
#: Kurze Bestaetigung statt der ausgespielten Verdichtung (Birk 05.09.2026):
#: nach einem Interview wird NICHT zurueckgemeldet und NICHT nachgefragt --
#: "zuerst nur Interviews machen, eins nach dem anderen, und wenn alle fertig
#: sind, dann die Verdichtungen ausspielen". Verdichtet wird trotzdem sofort
#: (das Material ist gesichert und steht auf der Gruppenseite), nur der Chat
#: bleibt ruhig. Ausgespielt wird auf Druck des Knopfes "Auswerten"
#: (``knoepfe.biete_nach_aufnahme``) -- der Slash-Befehl ``/auswerten``
#: existiert weiter, wird aber nicht mehr im Text beworben.
_TEXT_INTERVIEW_ABGELEGT = (
    "{name} ist aufgenommen und ausgewertet - ich halte mich damit zurueck, "
    "bis ihr alle Interviews zusammen habt."
)

#: Die EINE knappe Zeile, sobald die Verdichtung steht (Birk, 06.09.2026
#: 09:55). Bis dahin sagte der Bot "ich halte mich damit zurueck" und die
#: Gruppe erfuhr nie, ob ueberhaupt etwas herausgekommen war. Jetzt steht
#: die Zaehlung da -- Themen und Zitate --, und die Verdichtung selbst bleibt
#: hinter dem Knopf: **kein** Volltext ohne Knopfdruck, das bleibt die
#: Entscheidung vom 05.09.2026.
_TEXT_AUSGEWERTET = "{name} ausgewertet: {themen} Themen, {zitate} Zitate."

#: Die Zeile nach einem Interview im Web-Kanal (02.10.2026), Bausteine fuer
#: ``_text_interview_gespeichert_web``. Bis 04.10.2026 standen sie als
#: Literale in der Funktion und gingen an der Sprachschicht vorbei -- Padua
#: (englisch) sah deutschen Text. Wortlaut unveraendert.
_TEXT_GESPEICHERT_WEB = "{name} gespeichert · {uhrzeit} Uhr · {minuten} Min"
_TEXT_THEMEN_WEB = "Themen: "
_TEXT_AUSWERTUNG_IM_TAB = "Ganze Auswertung im Tab Arbeitsstand."

_TEXT_VERDICHTUNG_KOPF = "{name} ist durch. Was ich darin hoere:"
_TEXT_VERDICHTUNG_THEMEN = "Kernthemen:"
_TEXT_VERDICHTUNG_FRAGE = "Stimmt das so? Sonst sagt es mir."

#: Die Phasenfrage unter der ersten Verdichtung (05.09.2026, Birk nach dem
#: Probelauf). Sie haengt genau hier, weil hier der Moment ist, in dem die
#: Frage aufkommt -- und weil der Bot sie sonst erst im naechsten
#: Gespraechszug stellen wuerde, also nach der naechsten Nachricht der Gruppe.
#: Eine **Frage**, kein Wechsel: der Datenstand sagt nur, dass Phase 4
#: moeglich WAERE, nicht dass die Gruppe fertig ist mit den Interviews.
_TEXT_PHASENFRAGE = "Kommen noch Interviews, oder gehen wir ans Kernthema?"

#: Steht statt der Kernthemen, wenn keines von ihnen ein woertliches Zitat
#: hatte (N2): lieber die ehrliche Leerstelle als drei Themen, die sich auf
#: nichts stuetzen.
_TEXT_OHNE_BELEG = "Ich konnte kein Thema mit einem woertlichen Zitat belegen."

#: Ein Interview unter MINDEST_WOERTER Woertern wird nicht ausgewertet (N2) --
#: mit Zahlen, damit die Gruppe erkennt, welche Aufnahme gemeint ist. Der
#: Widerspruch dagegen ist seit 05.09.2026 der Knopf "Auswerten" darunter
#: (``knoepfe.biete_nach_aufnahme``) und nicht mehr ein Hinweis auf einen
#: Slash-Befehl: im Live-Lauf (Gruppe 2, 13:59) fragte die Gruppe nach diesem
#: Text zweimal nach, und ausgewertet wurde nie.
_TEXT_ZU_KURZ = (
    "{name} war sehr kurz ({woerter} Woerter) - ich habe es nicht "
    "ausgewertet."
)

#: "fertig" ohne eine einzige Sprachnachricht: eine Zeile, kein Modellaufruf.
_TEXT_OHNE_AUFNAHME = "{name} hatte keine Aufnahme - ich habe nichts verdichtet."

#: Ein Interview, in dem NIE eine Sprachnachricht ankam, wird beim Beenden
#: weich entfernt (05.09.2026, Live-Fall Gruppe 1, 14:21): "Aufnahme starten",
#: sieben Sekunden spaeter versehentlich "Aufnahme beenden", zweimal
#: hintereinander -- es blieben zwei leere Interviews stehen, die als
#: unausgewertet die Phase-4-Sperre ausloesten. Statt "Interview N beendet"
#: steht seitdem diese Zeile da, mit dem Knopf "Aufnahme starten" darunter:
#: ein Fehlgriff soll nichts hinterlassen ausser der Moeglichkeit, es
#: nochmal zu versuchen.
_TEXT_LEER_VERWORFEN = "Keine Aufnahme dabei - nichts gespeichert."

#: Wie ein Interview ohne gespeicherten Namen im Satz heisst.
_TEXT_DAS_INTERVIEW = "Das Interview"

#: Die Fehlerzeilen rund um eine Sprachnachricht und die Bausteine, mit denen
#: ``_aufnahme_beschreibung`` sagt, welche Aufnahme gemeint ist.
_TEXT_DOWNLOAD_FEHLER = (
    "Die Aufnahme ist bei mir nicht angekommen - schickt sie bitte nochmal."
)
_TEXT_BITTE_NOCHMAL = (
    "{beschreibung} konnte ich nicht verstehen - schickt sie bitte nochmal."
)
_TEXT_VERDICHTUNG_GESCHEITERT = (
    "Ich konnte {beschreibung} nicht auswerten. Das Transkript bleibt "
    "gespeichert, nur die Zusammenfassung fehlt."
)
_ARTIKEL_GROSS = "Die"
_ARTIKEL_KLEIN = "die"
_BESCHREIBUNG_TEIL = "{artikel} Aufnahme von {name}, Teil {nummer}"
_BESCHREIBUNG_NAME = "{artikel} Aufnahme von {name}"
_BESCHREIBUNG_LETZTE = "{artikel} letzte {art}"
_ART_LANG = "lange Aufnahme"
_ART_KURZ = "kurze Aufnahme"


def klasse_fuer(conn, chat_id: int) -> str:
    """Ordnet eine eingehende Sprachnachricht ihrer Klasse zu (§ 10.1, § 10.6)
    -- ausschliesslich anhand von ``gruppe.interviewmodus_seit``, NICHT anhand
    der Dauer: die sagt nichts ueber die Art aus (ein Interview kann aus fuenf
    kurzen Sprachnachrichten bestehen, eine Regieanweisung laenger als eine
    Minute dauern).

    Bei aktivem Modus ist die Sprachnachricht seit dem Nachtrag ein *teil*
    eines Interviews, keine eigenstaendige lange Aufnahme mehr: ``lang``
    bezeichnet nur noch den Kopf, den ``stelle_interview_sicher`` anlegt."""
    return "teil" if repo.ist_interviewmodus_an(conn, chat_id) else "kurz"


#: Wie weit zurueck eine Sprachnachricht beim Einschalten des Interviewmodus
#: noch als Interviewmaterial eingesammelt wird (``NACHZUEGLER``, 05.09.2026).
#: Gesetzt, nicht gemessen: 10 Minuten decken den Fall ab, dass eine Gruppe
#: erst spricht und danach "wir machen jetzt ein Interview ... fertig" sagt,
#: ohne Zurufe aus einer ganz anderen Arbeitsphase mitzunehmen. Fehlerrichtung
#: bewusst: lieber ein Zuruf zu viel im Transkript (die Gruppe sieht ihn im
#: zurueckgespielten Text und kann widersprechen) als das ganze Interview
#: verloren.
NACHZUEGLER_FENSTER_S = 600


def ist_web_gruppe(conn, chat_id: int) -> bool:
    """Arbeitet diese Gruppe im Browser (``gruppe.kanal = 'web'``)? Ohne
    Gruppenzeile: nein -- dann gilt der Telegram-Weg wie bisher.

    Oeffentlich (06.10.2026, Phase 3 Web-UX): der eine geteilte
    Kanal-Check, den ausser ``stelle_interview_sicher`` hier auch
    ``knoepfe.interviews`` und ``_kurz_abschliessen``/``_sende_teil_echo``
    brauchen, um alte Telegram-Knoepfe auf dem Web-Kanal nicht mehr
    anzubieten (Handler bleiben unveraendert, nur das Angebot aendert sich)."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    return gruppe is not None and "kanal" in gruppe.keys() and gruppe["kanal"] == "web"


def _web_sprachblase(conn, chat_id: int, message_id: int, text: str | None) -> None:
    """Padua Hotfix B7 (02.10.2026): die Sprachblase im Web-Chat bekommt ihr
    Transkript -- oder mit ``text=None`` nur das Zeichen, dass nicht mehr
    abgetippt wird (Interview-Teil mit eigenem Echo, versteckte lange
    Nachricht, endgueltiger Fehlschlag). Nur im Web-Kanal; Telegram zeigt die
    Sprachnachricht selbst.

    Aufzurufen NACH dem Status ``fertig``/``fehlgeschlagen``: die Blase zeigt
    "wird abgetippt", solange die Aufnahme keinen dieser Status hat
    (``web_daten``), und ein Poll zwischen beiden Schritten saehe sonst die
    Aenderung, aber noch den alten Status. Ein Fehler hier kostet nur die
    Anzeige, nie die Aufnahme."""
    try:
        if ist_web_gruppe(conn, chat_id):
            repo.setze_web_sprachtext(conn, chat_id, message_id, text)
    except Exception:
        log.exception("Sprachblase im Web-Chat nicht aktualisiert, chat_id=%s", chat_id)


def stelle_interview_sicher(conn, chat_id: int) -> int:
    """Liefert den laufenden Interview-Kopf dieser Gruppe und legt ihn beim
    ersten Bedarf an (§ 10.6). Liefert dessen ``aufnahme_id``.

    Aufgerufen beim Einschalten des Modus (``/interview``, Erkenner-art
    ``interview_starten``) -- und zusaetzlich in ``empfange()``, falls dort
    trotz aktivem Modus keiner existiert: der Modus steht in der Datenbank und
    kann aus einer aelteren Fassung, einem Fehlschlag beim Anlegen oder einem
    Handeingriff stammen. Eine Sprachnachricht ohne Kopf waere sonst
    heimatloses Material.

    Beim ANLEGEN eines Kopfes werden ausserdem die Sprachnachrichten der
    letzten ``NACHZUEGLER_FENSTER_S`` Sekunden eingesammelt, die noch an
    keinem Interview haengen (``repo.ziehe_in_interview``, 05.09.2026): sagt
    eine Gruppe erst nach dem Sprechen "wir machen jetzt ein Interview", waere
    ihr Material sonst verloren."""
    kopf = repo.laufendes_interview(conn, chat_id)
    if kopf is not None:
        return kopf["id"]
    kopf_id = repo.lege_interview_an(conn, chat_id)
    if ist_web_gruppe(conn, chat_id):
        # Im Web gibt es keine Nachzuegler (Abschlussreview I4): eine
        # PTT-Nachricht ist dort ausdruecklich "an den Bot", und der Browser
        # schickt Interview-Segmente erst, wenn der Modus gemeldet ist
        # (web_chat, Warteschlange "bereit"). Einsammeln hiesse, Zurufe an den
        # Bot ins Transkript zu ziehen. Telegram bleibt unveraendert (E1).
        return kopf_id
    try:
        grenze = datetime.now(timezone.utc) - timedelta(seconds=NACHZUEGLER_FENSTER_S)
        eingesammelt = repo.ziehe_in_interview(
            conn, chat_id, kopf_id, grenze.isoformat()
        )
        if eingesammelt:
            log.info(
                "Interview %s: %s Nachzuegler-Aufnahme(n) eingesammelt, chat_id=%s",
                kopf_id, len(eingesammelt), chat_id,
            )
    except Exception:
        # Ein Fehlschlag hier darf den Interviewstart nicht mitreissen: der
        # Kopf steht, ab jetzt laufen neue Sprachnachrichten ohnehin korrekt
        # als Teile hinein.
        log.exception("Nachzuegler konnten nicht eingesammelt werden, chat_id=%s", chat_id)
    return kopf_id


#: Die Phase, in der Interviews gefuehrt werden (``phasen.PHASEN``, dieselbe
#: Zahl wie ``knoepfe.PHASE_INTERVIEWS``).
PHASE_INTERVIEWS = 3

#: Der Klammerzusatz im Journal, wenn der Aufnahmestart die Phase mitzieht.
_JOURNAL_PHASE_DURCH_AUFNAHME = "durch Aufnahmestart"


def stelle_phase_interviews_sicher(conn, tg, chat_id: int, quelle: str = "knopf") -> bool:
    """Setzt die Phase auf 3, wenn die Gruppe ausdruecklich eine Aufnahme
    startet und noch in Phase 1 oder 2 steht (05.09.2026, Live-Fall
    Gruppe 1). Liefert True, wenn dabei etwas geaendert wurde.

    Das ist **kein Raten** und damit kein Bruch mit "Die Phase setzt allein
    die Gruppe" (AGENTS.md): der Aufnahmestart ist eine Handlung der Gruppe
    -- Knopf, ``/aufnahme`` oder ein erkanntes ``interview_starten``. Wer
    aufnimmt, fuehrt Interviews; die Phase hinterherhinken zu lassen hatte
    genau eine sichtbare Folge, und die war falsch: die Einstiegsleiste bot
    "Weiter zu Phase 3" NEBEN "Aufnahme starten" an, zwei Knoepfe fuer
    dieselbe Sache.

    Aus Phase 4 und hoeher wird **nicht** zurueckgeschaltet: eine Gruppe,
    die im Kernthema noch ein Interview nachschiebt, ist deshalb nicht
    wieder in Phase 3 (``_aufnahme_anbieten`` erlaubt das ausdruecklich).

    Der Wechsel wird gemeldet wie jeder andere (``phasen.meldung``) -- er
    ist hoerbar, nicht still."""
    if phasen.aktuelle(conn, chat_id) >= PHASE_INTERVIEWS:
        return False
    if not phasen.setze(
        conn, chat_id, PHASE_INTERVIEWS, quelle,
        notiz=T._JOURNAL_PHASE_DURCH_AUFNAHME,
    ):
        return False
    try:
        tg.sende(chat_id, phasen.meldung(PHASE_INTERVIEWS))
    except Exception:
        log.exception("Phasenmeldung nach Aufnahmestart fehlgeschlagen, chat_id=%s", chat_id)
    return True


def _kein_zug(conn, tg, klm, e, chat_id, hinweis=None) -> None:
    """Vorgabewert fuer den zug-Parameter: absichtlich ohne Wirkung.

    Seit Aufgabe 10 existiert der echte Gespraechszug in ``interview_theater.ablauf``
    -- aufnahme.py importiert dieses Modul bewusst nicht selbst, um jeden
    Importzyklus von vornherein auszuschliessen. Die echte Funktion
    (``ablauf.bearbeite``) reicht ausschliesslich ``bot.py`` explizit herein,
    an beiden Stellen, an denen die Pipeline aufgerufen wird
    (``_bearbeite_sprachnachricht`` fuer den Live-Weg, ``_nachhol_schleife``
    fuer den Nachhol-Arbeiter). Direkte Aufrufe von ``verarbeite()``/
    ``nachholen()`` ohne explizites ``zug`` (Tests, ein spaeterer Textimport)
    bleiben mit diesem Vorgabewert unveraendert wirkungslos.

    ``hinweis`` (Aufgabe 5): eine optionale Zeile, die ``ablauf.bearbeite``
    an die ohnehin faellige Antwort anhaengt (siehe _kurz_abschliessen) --
    hier ohne jede Wirkung, wie der Rest dieser Attrappe."""
    return None


def _lade_mit_wiederholung(tg, file_id: str, ziel: Path) -> Exception | None:
    """Laedt die Datei herunter, wiederholt bei Fehlschlag mit denselben
    Wartezeiten wie ``stt.absenden`` (``stt.WARTEZEITEN``). Liefert ``None``
    bei Erfolg, sonst die zuletzt aufgetretene Ausnahme.

    Kritischer Nachbesserungspunkt: ohne diese Wiederholung wuerde ein
    einzelner Telegram-Aussetzer beim Download dieselbe Aufnahme unrettbar
    verlieren, die die ganze Aufgabe eigentlich absichern soll -- nur eine
    Etage frueher als Whisper."""
    letzter_fehler: Exception | None = None
    gesamtversuche = len(stt.WARTEZEITEN) + 1
    for versuch in range(gesamtversuche):
        try:
            tg.lade_datei(file_id, ziel)
            return None
        except Exception as fehler:
            letzter_fehler = fehler
        if versuch < len(stt.WARTEZEITEN):
            time.sleep(stt.WARTEZEITEN[versuch])
    return letzter_fehler


def empfange(conn, tg, e, n: dict) -> int | None:
    """Laedt die Sprachnachricht herunter und legt die Aufnahme mit
    ``status='empfangen'`` an -- ohne jeden Whisper-Kontakt (§ 10.2, die
    eigentliche Absicherung dieser Aufgabe).

    ``n`` ist das normalisierte Nachrichten-Dictionary aus
    ``interview_theater.telegram.lies_nachricht()``. Die zugehoerige Zeile in
    ``nachricht`` existiert im Normalbetrieb schon (die Polling-Schleife legt
    sie mit ``typ='sprache'``, ``text=NULL``, ``unterdrueckt=1`` an); der
    ``INSERT OR IGNORE`` hier stellt sicher, dass sie auch existiert, wenn
    ``empfange()`` direkt aufgerufen wird (Tests, spaeterer Nachhol-Anlauf).

    Bei aktivem Interviewmodus haengt die neue Zeile als *Teil* am laufenden
    Interview (``teil_von``, § 10.6). Eine Empfangsbestaetigung gibt es seit
    dem Nachtrag nicht mehr: das Transkript kommt gleich hinterher und ist die
    Bestaetigung -- "Ich hoere durch" gefolgt von Schweigen war genau das, was
    im Probelauf nicht getragen hat.

    Liefert die neue ``aufnahme_id``, oder ``None``, wenn der Download nach
    Wiederholung endgueltig scheiterte. In diesem Fall entsteht bewusst
    **keine** ``aufnahme``-Zeile (es gibt kein Audio, das der Nachhol-Arbeiter
    je nachholen koennte) -- dafuer aber ein Vorfall und eine Bitte an die
    Gruppe, es nochmal zu schicken, damit nichts spurlos verschwindet.

    ``n["endung"]`` (optional) bestimmt die Endung des Zielpfads. Sie ist der
    einzige Weg, auf dem ``stt.mime_typ()`` den richtigen MIME-Typ bekommt
    (Falle 3); ohne sie bleibt es bei ``ENDUNG_VORGABE``, wie im
    Telegram-Betrieb."""
    chat_id = n["chat_id"]
    message_id = n["message_id"]
    kalibrierung = bool(n.get("kalibrierung"))
    # Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026): ein
    # Kalibrierungs-Testsatz ist UNABHAENGIG vom gerade geltenden Modus
    # strukturell nie Teil eines Interviews -- die Gruppe kann /interview
    # laengst gedrueckt haben, bevor der Clip hochlaedt
    # (``starteInterview`` schickt den Befehl vor dem ersten Segment).
    # Deshalb hier VOR jedem Blick auf den Modus entschieden, nicht ueber
    # ``klasse_fuer``/``stelle_interview_sicher``.
    if kalibrierung:
        klasse = "kurz"
        teil_von = None
    else:
        klasse = klasse_fuer(conn, chat_id)
        teil_von = stelle_interview_sicher(conn, chat_id) if klasse == "teil" else None

    # Dieselbe Entscheidung wie oben: KEINE ``nachricht``-Zeile fuer einen
    # Kalibrierungs-Testsatz. Ohne sie kann der Clip strukturell nie in
    # ``kontext.baue``s Fenster, dem Absichtserkenner oder dem Journal
    # auftauchen -- alle drei lesen ueber Funktionen, die aus ``nachricht``
    # selektieren (``letzte_nachrichten``/``unextrahierte``/
    # ``unjournalisierte``). Empfangen und In-den-Prompt-legen sind zwei
    # Entscheidungen (docs/agents/entscheidungen.md) -- hier wird bewusst auch das Empfangen in
    # dieser Tabelle ausgelassen, weil ein Kalibrierungs-Testsatz kein
    # Gruppenbeitrag ist, den es je zu zeigen gaebe.
    if not kalibrierung:
        repo.merke_nachricht(
            conn, chat_id, message_id, n.get("absender"), 0, "sprache", None,
            n.get("gesendet_am") or repo._jetzt(), 1,
        )

    ziel = (
        Path(e.audio_verz) / str(chat_id)
        / f"{message_id}{n.get('endung') or ENDUNG_VORGABE}"
    )
    fehler = _lade_mit_wiederholung(tg, n["file_id"], ziel)
    if fehler is not None:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "download_fehlgeschlagen",
            f"Sprachnachricht message_id={message_id}: {type(fehler).__name__}",
        )
        try:
            tg.sende(chat_id, T._TEXT_DOWNLOAD_FEHLER)
        except Exception:
            log.exception("Download-Fehlermeldung fehlgeschlagen, chat_id=%s", chat_id)
        # Review-Fund zu B7: ohne aufnahme-Zeile hinge die Blase sonst fuer
        # immer auf "wird abgetippt" -- das Zeichen kommt hier ueber
        # ``aenderung`` (``web_daten._ABGETIPPT``), nicht ueber einen Status.
        _web_sprachblase(conn, chat_id, message_id, None)
        return None

    return repo.lege_aufnahme_an(
        conn, chat_id, message_id, klasse, "sprache",
        audio_pfad=str(ziel), dauer=n.get("dauer"), teil_von=teil_von,
        schnittgrund=n.get("schnittgrund"), brainstorm=bool(n.get("brainstorm")),
        diskussion=bool(n.get("diskussion")),
        rede_ms=n.get("rede_ms"), kalibrierung=kalibrierung,
        weich_ms=n.get("weich_ms"),
    )


# Schuetzt gegen doppelte Bearbeitung derselben Aufnahme INNERHALB eines
# Prozesses: der Nachhol-Thread laeuft alle NACHHOL_INTERVALL_S Sekunden,
# unabhaengig vom ThreadPoolExecutor der laufenden Uploads. Dauert eine live
# eingehende lange Aufnahme laenger als ein Nachhol-Intervall, koennten sonst
# beide Wege dieselbe (noch 'empfangen'e) Aufnahme gleichzeitig aufgreifen.
# Die Absicherung ueber Prozessgrenzen hinweg leistet
# repo.offene_aufnahmen_fuer_bot() (siehe nachholen()).
_in_bearbeitung: set[int] = set()
_in_bearbeitung_lock = threading.Lock()


def verarbeite(conn, tg, klm, e, klient, aufnahme_id, *, zug=_kein_zug, nachgeholt=False) -> None:
    """Transkribiert eine Aufnahme und verarbeitet sie klassenabhaengig weiter.

    ``klient`` wird unveraendert an ``stt.transkribiere`` durchgereicht (ein
    echter ``httpx.Client`` in Produktion, ein per MockTransport gebauter in
    Tests). ``zug`` ist der Gespraechszug fuer Klasse *kurz* -- als Parameter
    hereingereicht statt hier importiert, damit aufnahme.py nie von
    ``interview_theater.ablauf`` abhaengt (siehe ``_kein_zug``); Voreinstellung:
    nichts tun. ``bot.py`` reicht die echte Funktion (``ablauf.bearbeite``)
    explizit herein.

    ``nachgeholt=True`` (gesetzt von ``nachholen()``) unterdrueckt den
    Gespraechszug unabhaengig vom Alter der urspruenglichen Nachricht (§ 10.3:
    'Nachgeholtes loest nie eine Antwort aus') -- die Gruppe ist inzwischen
    weiter, eine verspaetete Antwort auf einen laengst vergangenen Moment
    stiftet mehr Verwirrung, als sie nuetzt. Die Alters-Pruefung allein reicht
    nicht: ein Whisper-Ausfall, der binnen weniger Minuten wieder abklingt,
    waere sonst 'jung genug', obwohl der Anlauf im Hintergrund lief."""
    with _in_bearbeitung_lock:
        if aufnahme_id in _in_bearbeitung:
            return
        _in_bearbeitung.add(aufnahme_id)
    try:
        _verarbeite(conn, tg, klm, e, klient, aufnahme_id, zug, nachgeholt)
    finally:
        with _in_bearbeitung_lock:
            _in_bearbeitung.discard(aufnahme_id)


def _verarbeite(conn, tg, klm, e, klient, aufnahme_id, zug, nachgeholt) -> None:
    row = repo.hole_aufnahme(conn, aufnahme_id)
    # 'laeuft' heisst: ein Interview-Kopf sammelt gerade noch Teile ein. Er
    # wird nicht hier abgeschlossen, sondern in schliesse_ab(), wenn die
    # Gruppe "fertig" gesagt hat -- sonst verdichtete ein Nachhol-Lauf ein
    # Interview mitten im Satz.
    if row is None or row["status"] in ("fertig", "fehlgeschlagen", "laeuft"):
        return  # nichts (mehr) zu tun

    if row["status"] == "empfangen":
        # Der Tagesdeckel (Karte Padua S). Hier und NICHT als Ausnahme aus
        # stt.transkribiere: die liefe durch ``_melde_transkriptionsfehler``,
        # und das zaehlt ``repo.zaehle_versuch_hoch`` hoch. Der
        # Nachhol-Arbeiter laeuft alle 60 s -- MAX_VERSUCHE waeren in fuenf
        # Minuten verbraucht, und jedes Interview des Abends stuende am
        # naechsten Morgen auf 'fehlgeschlagen'.
        #
        # Stattdessen: nichts tun. Datei und Zeile bleiben, der Status bleibt
        # 'empfangen', und ``nachholen()`` greift sie nach Mitternacht von
        # selbst auf (repo.offene_aufnahmen_fuer_bot liefert alles ausserhalb
        # von fertig/fehlgeschlagen/laeuft). Kein neuer Mechanismus.
        from interview_theater import kosten

        if kosten.deckel_erreicht(conn, row["chat_id"], e):
            if not nachgeholt:
                # Nur im Live-Pfad melden: "Nachgeholtes loest nie eine
                # Antwort aus" (SPEC § 10.3), und der Nachhol-Arbeiter kaeme
                # sonst alle 60 s wieder.
                kosten.melde_pause_wenn_deckel(conn, tg, e, row["chat_id"])
            return
        if _ist_leeres_ende(row):
            _verwirf_ende_segment(conn, e, row, "leeres_segment_verworfen",
                                  f"Ende-Segment unter {LEERES_ENDE_MAX_BYTES} Bytes")
            _abschluss_trotz_verworfenem_ende(conn, tg, klm, e, aufnahme_id)
            return
        text = _transkribiere_mit_meldung(conn, tg, e, klient, row)
        if text is None:
            # Fehler wurde schon gemeldet/aufgezeichnet. Ist es endgueltig
            # (leer oder aufgegeben) und war es der Ende-Schnitt einer
            # Diskussion/eines Brainstorms, laeuft der Abschluss trotzdem.
            _abschluss_trotz_verworfenem_ende(conn, tg, klm, e, aufnahme_id)
            return
        melde_rueckkehr(conn, tg, e, row["chat_id"])
        repo.setze_transkript(conn, aufnahme_id, text)
        repo.setze_status(conn, aufnahme_id, "transkribiert")
        row = repo.hole_aufnahme(conn, aufnahme_id)

    # status ist jetzt 'transkribiert' -- frisch oder schon vorher (Textimport,
    # oder ein frueherer Anlauf, bei dem nur die Verdichtung scheiterte).
    if row["klasse"] == "teil":
        _teil_abschliessen(conn, tg, klm, e, row, zug, nachgeholt)
    elif row["klasse"] == "kurz":
        _kurz_abschliessen(conn, tg, klm, e, row, zug, nachgeholt)
    else:
        _interview_abschliessen(conn, tg, klm, e, row, nachgeholt=nachgeholt)


def whisper_sprache(conn, chat_id: int) -> str:
    """Welche Sprache Whisper fuer diese Gruppe hoeren soll (Karte A1, D2):
    der Gruppenwert (``gruppe.stt_sprache``, per Knopf oder /sprache
    gesetzt) vor dem Profilwert (``sprache.whisper``). ``"auto"`` heisst:
    Whisper erkennt selbst."""
    return repo.stt_sprache(conn, chat_id) or sprache.whisper_vorgabe()


def _transkribiere_mit_meldung(conn, tg, e, klient, row) -> str | None:
    """Ruft stt.transkribiere auf, waehrenddessen die Tippanzeige laeuft (ab
    TIPPANZEIGE_AB_S, fuer jede Klasse). Die Zwischenmeldung ("Ich hoer noch
    zu...", ab MELDUNG_AB_S) geht seit dem Nachtrag auch an einen Interview-
    *Teil*: die Empfangsbestaetigung, die frueher fuer ihn sprach, gibt es
    nicht mehr, und wer gerade eine Sprachnachricht geschickt hat, wartet auf
    ihr Transkript. Sie feuert erst deutlich ueber der Tippanzeige
    (MELDUNG_AB_S > TIPPANZEIGE_AB_S, beide gemessen 03.09.2026) -- im
    Normalfall von unter drei Sekunden also nie."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]
    budget = BUDGET_KURZ_S if row["klasse"] == "kurz" else BUDGET_LANG_S
    pfad = Path(row["audio_pfad"])

    def _tippen():
        try:
            tg.tippt(chat_id)
        except Exception:
            log.exception("Tippanzeige fehlgeschlagen, chat_id=%s", chat_id)

    def _zwischenmeldung():
        try:
            tg.sende(chat_id, T._TEXT_ZWISCHENMELDUNG)
        except Exception:
            log.exception("Zwischenmeldung fehlgeschlagen, chat_id=%s", chat_id)

    timer_tipp = threading.Timer(TIPPANZEIGE_AB_S, _tippen)
    timer_tipp.daemon = True
    timer_tipp.start()

    timer_meldung = threading.Timer(MELDUNG_AB_S, _zwischenmeldung)
    timer_meldung.daemon = True
    timer_meldung.start()

    start = time.monotonic()
    erfolg = 0
    try:
        text = stt.transkribiere(e, klient, pfad, budget,
                                 sprache=whisper_sprache(conn, chat_id))
        erfolg = 1
        return text
    except Exception as fehler:
        _melde_transkriptionsfehler(conn, tg, e, row, fehler)
        return None
    finally:
        timer_tipp.cancel()
        timer_meldung.cancel()
        _buche_stt(conn, e, row, time.monotonic() - start, erfolg)


#: Was in ``aufruf.modell`` steht, wenn Whisper lief. Ein fester Name und
#: kein Modell-Bezeichner: der Aufruf geht ueber ``e.stt_produkt`` an einen
#: Produkt-Endpunkt, nicht an ein benanntes Modell.
STT_MODELL = "whisper-v3"


def _buche_stt(conn, e, row, dauer_s: float, erfolg: int) -> None:
    """Der Whisper-Aufruf in ``aufruf`` -- seit dem 30.09.2026 (Karte Padua S).

    **Warum hier und nicht in ``stt.py``:** ``stt.transkribiere`` bekommt
    weder ``conn`` noch ``chat_id`` (``stt.py``), und das soll so bleiben --
    ``llm.py`` traegt diese Kopplung schon, ``stt.py`` bewusst nicht. Der
    einzige Aufrufer steht hier.

    **Die Dauer kommt aus ``aufnahme.dauer_sekunden``**, nicht aus der
    Whisper-Antwort: ``stt.abholen`` liefert nur den Text, und ob die Antwort
    ein Dauerfeld traegt, waere ein bezahlter Aufruf. Fehlt die Dauer, werden
    **0 CHF gebucht und nichts geraten** -- die eine Stelle, an der der
    Tagesdeckel weniger sieht, als anfaellt.

    **Gebucht wird auch bei Misserfolg**: ein Auftrag, der ins Zeitbudget
    laeuft, wurde abgesendet und ist bezahlt (dieselbe Regel wie das
    ``finally`` in ``llm._anfrage``)."""
    from interview_theater import kosten

    try:
        repo.merke_aufruf(
            conn, row["chat_id"], "stt", modus=None,
            dauer_ms=int(dauer_s * 1000), erfolg=erfolg,
            modell=STT_MODELL,
            kosten_chf=kosten.stt_kosten_chf(row["dauer_sekunden"]),
        )
    except Exception:  # noqa: BLE001 -- die Buchung darf die Aufnahme nie mitreissen
        log.exception("Aufruf-Buchung (Whisper) fehlgeschlagen, aufnahme=%s", row["id"])


def _ist_ersatzname(name: str | None) -> bool:
    """Erkennt den automatisch vergebenen Namen 'Interview n' (repo.lege_
    aufnahme_an), im Unterschied zu einem von der Gruppe echt vergebenen
    Namen."""
    return bool(name) and re.fullmatch(r"Interview \d+", name) is not None


def anzeigename(conn, row, ersatz: str) -> str:
    """Wie eine Aufnahme in einem Bot-Text heisst (E8, Karte A1): in einem
    Profil mit Pseudonymen immer "Interview N" -- ein Aufnahmename ist oft
    ein Klarname ("das war Marias Interview") oder der Telegram-Name dessen,
    der das Handy hielt, und Bot-Texte kommen als "Du:"-Zeilen zurueck in
    jedes Fenster. Sonst wie bisher: der Name oder ``ersatz``."""
    if sprache.pseudonyme():
        from interview_theater import kontext

        return kontext.interviewbezeichnung(conn, row["chat_id"], row["id"]) or ersatz
    return row["name"] or ersatz


def _aufnahme_beschreibung(conn, row, gross: bool) -> str:
    """Beschreibt eine Aufnahme in einer Nutzernachricht. Ein automatisch
    vergebener Ersatzname wie 'Interview 1' wirkt in einer Chatnachricht
    unfreiwillig komisch ('Die Aufnahme von Interview 1...') -- ohne einen
    von der Gruppe vergebenen echten Namen wird stattdessen die Klasse
    genannt.

    Bei einem Teil ist das anders: 'Interview 1, Teil 3' ist keine Verlegenheit,
    sondern die einzige Angabe, mit der die Gruppe weiss, WELCHE der fuenf
    Sprachnachrichten sie noch einmal schicken soll."""
    artikel = T._ARTIKEL_GROSS if gross else T._ARTIKEL_KLEIN
    if row["teil_von"]:
        kopf = repo.hole_aufnahme(conn, row["teil_von"])
        name = anzeigename(conn, kopf, "Interview") if kopf else "Interview"
        return T._BESCHREIBUNG_TEIL.format(
            artikel=artikel, name=name, nummer=repo.teil_nummer(conn, row["id"]),
        )
    # E8: mit Pseudonymen ist das immer "Interview N" -- ein Ersatzname, also
    # die Klassenbeschreibung wie ohne echten Namen.
    name = anzeigename(conn, row, "")
    if name and not _ist_ersatzname(name):
        return T._BESCHREIBUNG_NAME.format(artikel=artikel, name=name)
    art = T._ART_LANG if row["klasse"] == "lang" else T._ART_KURZ
    return T._BESCHREIBUNG_LETZTE.format(artikel=artikel, art=art)


def _sende_bitte_nochmal(conn, tg, chat_id, row) -> None:
    text = T._TEXT_BITTE_NOCHMAL.format(
        beschreibung=_aufnahme_beschreibung(conn, row, gross=True),
    )
    try:
        tg.sende(chat_id, text)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _sende_verdichtung_gescheitert(conn, tg, chat_id, row) -> None:
    text = T._TEXT_VERDICHTUNG_GESCHEITERT.format(
        beschreibung=_aufnahme_beschreibung(conn, row, gross=False),
    )
    try:
        tg.sende(chat_id, text)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _ist_ende_segment(row) -> bool:
    """Der Ende-Schnitt einer Diskussion (Phase 1) oder eines Brainstorms
    (Phase 4) -- das Segment, auf dessen Abschluss die Gruppe wartet."""
    return row["schnittgrund"] == "ende" and bool(row["diskussion"] or row["brainstorm"])


def _ist_leeres_ende(row) -> bool:
    """Ein Ende-Segment, das zu klein fuer Rede ist (``LEERES_ENDE_MAX_BYTES``)."""
    if not _ist_ende_segment(row) or not row["audio_pfad"]:
        return False
    try:
        return Path(row["audio_pfad"]).stat().st_size < LEERES_ENDE_MAX_BYTES
    except OSError:
        return False  # fehlende Datei: der gewoehnliche Fehlerweg entscheidet


def _verwirf_ende_segment(conn, e, row, art: str, grund: str, fehlertext: str | None = None) -> None:
    """Still verwerfen (``status='fehlgeschlagen'``): keine Chatzeile, kein
    Ausfall-Alarm, kein Nachhol-Anlauf -- siehe ``_melde_transkriptionsfehler``."""
    repo.merke_vorfall(
        conn, row["chat_id"], getattr(e, "bot_name", None), art,
        f"Aufnahme {row['id']}: {grund}, still verworfen",
    )
    repo.setze_status(conn, row["id"], "fehlgeschlagen", fehlertext=fehlertext or grund)
    _web_sprachblase(conn, row["chat_id"], row["message_id"], None)


def _melde_transkriptionsfehler(conn, tg, e, row, fehler: Exception) -> None:
    """Bei jedem Fehlschlag: Versuch zaehlen, den einmaligen Whisper-Ausfall-
    Hinweis pruefen (melde_ausfall), und ab MAX_VERSUCHE endgueltig aufgeben.

    Die "...schickt sie bitte nochmal"-Bitte (§ 11.1) geht bei Material
    (Interview-Teil, Textimport) nur beim **ersten** Fehlschlag dieser
    Aufnahme raus --
    nicht bei jedem der bis zu MAX_VERSUCHE Nachhol-Anlaeufe, sonst waeren das
    bei einem laengeren Ausfall mit mehreren Interviews schnell Dutzende
    Nachrichten, und sie widerspraeche der Ausfallmeldung, die gerade
    zugesagt hat, alles nachzuholen. Ein Gespraechsbeitrag (Klasse *kurz*)
    bekommt dagegen gar keine Meldung bei Zwischenversuchen -- ein einzelner
    Zuruf ist niedrigschwellig genug, dass die pauschale Ausfallmeldung
    reicht -- aber beim endgueltigen Aufgeben (Wichtig 3) muss die Gruppe
    trotzdem erfahren, dass der Beitrag verloren ist, statt dass er
    kommentarlos als 'typ=sprache, text=NULL' im Verlauf haengen bleibt.

    **Ein Segment mit leerem Whisper-Ergebnis ist ein dritter, eigener
    Fall** (Karte Padua Brainstorm, 03.10.2026, Live-Fall: aufnahme 16, 4s,
    5 Versuche, dann eine unpassende "verstehe ich nicht"-Meldung im Chat;
    ausgeweitet auf JEDE Aufnahmeklasse mit der Karte "Mithoeren SICHER",
    03.10.2026, weil der Client seitdem jedes Segment hochlaedt statt
    VAD-Rauschen client-seitig zu verwerfen -- vorher traf dieser Fall fast
    nur Brainstorm, jetzt routinemaessig auch Interview-Teile und
    Gespraechsbeitraege): niemand wartet auf dieses eine Segment und niemand
    kann es "noch einmal sagen" -- es war nur ein paar Sekunden Rauschen
    beim Loslassen des Knopfes. Still verwerfen statt der normalen
    Fehlerkette: kein Wiederholungsversuch (``repo._NICHTS_ZU_TUN`` haelt
    den Nachhol-Arbeiter ab einem ``status='fehlgeschlagen'`` ohnehin fern),
    keine Chatzeile, und KEIN Ausfall-Alarm (``melde_ausfall``) -- Stille
    ist kein Dienstausfall."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]

    if isinstance(fehler, stt.LeeresTranskript):
        _verwirf_ende_segment(conn, e, row, "leeres_segment_verworfen",
                              "leeres Transkript", fehlertext=str(fehler))
        return
    # Ein Ende-Segment, dessen Auftrag Whisper endgueltig abbrach ('failed'),
    # wartet niemand fuenf Nachhol-Anlaeufe ab: verwerfen, der Aufrufer
    # schliesst ab. 5xx/Netz bleibt bei der Wiederholung unten.
    if isinstance(fehler, stt.AuftragAbgebrochen) and _ist_ende_segment(row):
        _verwirf_ende_segment(conn, e, row, "ende_segment_abgebrochen",
                              "Whisper-Auftrag abgebrochen", fehlertext=str(fehler))
        return

    versuche = repo.zaehle_versuch_hoch(conn, aufnahme_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "transkription_fehlgeschlagen",
        f"Aufnahme {aufnahme_id} (Versuch {versuche}/{MAX_VERSUCHE}): "
        f"{type(fehler).__name__}",
    )

    melde_ausfall(conn, tg, e, chat_id)

    endgueltig = versuche >= MAX_VERSUCHE
    if (row["klasse"] != "kurz" and versuche == 1) or (row["klasse"] == "kurz" and endgueltig):
        _sende_bitte_nochmal(conn, tg, chat_id, row)

    if endgueltig:
        repo.setze_status(conn, aufnahme_id, "fehlgeschlagen", fehlertext=str(fehler))
        _web_sprachblase(conn, chat_id, row["message_id"], None)
    else:
        # Status bleibt (wieder) 'empfangen': der Nachhol-Arbeiter greift die
        # Aufnahme beim naechsten Anlauf erneut auf, sobald Whisper zurueck ist.
        repo.setze_status(conn, aufnahme_id, "empfangen", fehlertext=str(fehler))


def _kalibrierung_abschliessen(conn, row) -> None:
    """Der Testsatz einer Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren
    SICHER/Kalibrierung, 03.10.2026): nur ``status='fertig'`` setzen, nichts
    sonst. Das Transkript liegt schon auf der Zeile (``_verarbeite`` setzt es
    vor der Weiche auf ``row["klasse"]``) -- ``web_daten.kalibrierung_zustand``
    liest genau diese Zeile fuer den Browser zurueck. Kein Gespraechszug, kein
    Erkenner, kein Journal, keine Interview-Rueckfrage, keine Sprachblase (es
    gibt keine sichtbare Blase, die Zeile faellt ja aus dem Chatverlauf
    heraus)."""
    repo.setze_status(conn, row["id"], "fertig")


def _kurz_abschliessen(conn, tg, klm, e, row, zug, nachgeholt) -> None:
    """Schreibt das Transkript als Aktualisierung der vorhandenen
    Nachrichtenzeile (§ 10.2) und loest den Gespraechszug nur aus, wenn die
    urspruengliche Nachricht noch jung genug ist (Auftragshinweis 1) UND es
    kein Nachhol-Anlauf war -- damit weder Nachtstau noch Nachgeholtes je eine
    Antwort ausloesen.

    Diese Funktion laeuft ausschliesslich fuer Klasse *kurz* -- und damit,
    seit Aufgabe 5, ausschliesslich fuer Sprachnachrichten, die bei
    interviewmodus AUS eintrafen (klasse_fuer).

    **Die lange Sprachnachricht ohne Interviewmodus ist seit dem 06.09.2026
    ein eigener, deterministischer Weg** (Live-Fall Gruppe 1, 13:32): sie
    bekommt keinen beilaeufigen Hinweis mehr an einer Gespraechsantwort,
    sondern gar keine Gespraechsantwort -- stattdessen die Frage, ob es ein
    Interview war, mit zwei Knoepfen. Siehe ``_frage_interview_ohne_knopf``.

    **Ein Brainstorm-Segment (``row['brainstorm']``, 02.10.2026) geht einen
    dritten, ganz eigenen Weg** -- siehe ``_brainstorm_abschliessen``: kein
    Gespraechsbeitrag, kein Zug, kein Erkenner, keine Interview-Rueckfrage.

    **Ein Diskussions-Segment (``row['diskussion']``, Phase 1, Padua
    03.10.2026) geht einen vierten, noch einfacheren Weg** -- siehe
    ``_diskussion_abschliessen``: reines Mithoeren, nie ein Gespraechsbeitrag,
    kein Zug, kein Erkenner, keine Buehnenkarte; laufend wird nur das
    Begriffsboard fortgeschrieben (``begriffsboard.nach_segment``). Diese Pruefung
    steht VOR der Brainstorm-Pruefung, weil beide Flags sich ausschliessen
    (verschiedene Phasen) -- die Reihenfolge entscheidet hier nichts, macht
    die Absicht aber am Quelltext sichtbar: Phase 1 vor Phase 4.

    **Ein Kalibrierungs-Testsatz (``row['kalibrierung']``, Task 2, Kanban-
    Karte Mithoeren SICHER/Kalibrierung, 03.10.2026) geht einen FUENFTEN,
    noch kuerzeren Weg** -- siehe ``_kalibrierung_abschliessen``: er setzt
    nur Status und behaelt das Transkript auf der ``aufnahme``-Zeile (die
    einzige Stelle, an der der Browser es ueber
    ``web_daten.kalibrierung_zustand`` wieder abholt). Er ist **nicht**
    implizit ueber ``jung``/``urspruengliche_nachricht`` abgesichert, obwohl
    das zufaellig auch funktionieren wuerde (``empfange()`` schreibt fuer
    ihn nie eine ``nachricht``-Zeile) -- der explizite Zweig bleibt richtig,
    auch wenn sich das einmal aendert."""
    if row["diskussion"]:
        _diskussion_abschliessen(conn, tg, klm, e, row)
        return

    if row["kalibrierung"]:
        _kalibrierung_abschliessen(conn, row)
        return

    if row["brainstorm"]:
        _brainstorm_abschliessen(conn, tg, klm, e, row)
        return

    from interview_theater import bot  # spaeter Import: vermeidet einen Ladezyklus mit bot.py

    aufnahme_id = row["id"]
    chat_id = row["chat_id"]
    message_id = row["message_id"]
    text = row["transkript"]

    urspruengliche_nachricht = repo.hole_nachricht(conn, chat_id, message_id)
    jetzt = datetime.now(timezone.utc)
    jung = (
        not nachgeholt
        and urspruengliche_nachricht is not None
        and not bot.ist_nachtstau(urspruengliche_nachricht["gesendet_am"], jetzt)
    )

    dauer = row["dauer_sekunden"] or 0
    interview_frage = (
        jung
        and dauer > HINWEIS_AB_S
        and not repo.ist_interviewmodus_an(conn, chat_id)
        # Auf dem Web-Kanal sind PTT und der Aufnahme-Regler zwei getrennte
        # Bedienelemente (06.10.2026, Phase 3 Web-UX) -- eine lange
        # PTT-Aufnahme ausserhalb des Interviewmodus ist dort unzweideutig
        # ein Gespraechsbeitrag und darf nie die "Ja, als Interview"/"Nein,
        # war ein Beitrag"-Frage ausloesen.
        and not ist_web_gruppe(conn, chat_id)
    )

    repo.aktualisiere_transkribierte_nachricht(
        conn, chat_id, message_id, text, 1 if (interview_frage or not jung) else 0,
        versteckt=interview_frage,
    )
    repo.setze_status(conn, aufnahme_id, "fertig")
    # B7: sichtbar abgetippt nur, was auch im Gespraech steht -- ein
    # verstecktes Transkript bleibt auch in der Blase verborgen.
    _web_sprachblase(conn, chat_id, message_id, None if interview_frage else text)

    if interview_frage:
        _frage_interview_ohne_knopf(conn, tg, e, chat_id, aufnahme_id, dauer)
        return

    if jung:
        try:
            zug(conn, tg, klm, e, chat_id, hinweis=None)
        except Exception:
            log.exception("Gespraechszug nach kurzer Aufnahme fehlgeschlagen, chat_id=%s", chat_id)


def _diskussion_abschliessen(conn, tg, klm, e, row) -> None:
    """Ein Segment des Hintergrund-Mithoerens (Phase 1, Padua 03.10.2026):
    die Gruppe diskutiert im Raum, das Mikrofon laeuft mit -- reines
    Material, nie ein Gespraechsbeitrag an den Bot. Die ``nachricht``-Zeile
    bleibt, wie ``empfange()`` sie anlegte (``unterdrueckt=1``); das
    Transkript in ``aufnahme.transkript`` ist das Material.

    Auf JEDEM Segment: Status ``fertig``, das Transkript als Sprechblase
    (B7) -- und seit Karte t_4517d4ad (04.10.2026, Birk: Phase 1 und 4
    laufen EINHEITLICH automatisch) die Code-Entscheidung, ob das
    Begriffsboard fortgeschrieben wird: ``begriffsboard.nach_segment`` ruft
    ``brainstorm.soll_reagieren`` mit den eigenen Zahlen der Phase 1 und
    stoesst den Lauf im eigenen Thread an. Kein Gespraechszug, kein
    Absichtserkenner, keine Buehnenkarte und KEINE Chatzeile -- das Board
    steht nur im CoThinker-Tab.

    Beim Abschluss-Segment (``schnittgrund == 'ende'``, allein aus
    "Discussion done" -- Phase 1 hat seit 04.10.2026 keinen Pause-Knopf
    mehr) kommt danach der Vorschlag der Top 5 (oder, bei leerem Board, die
    bisherige Aufforderung) -- nach einem Lauf, den dieser Schnitt unter der
    gewoehnlichen Regel ausloest, oder nach einem gerade laufenden -- und,
    unabhaengig davon, der EINE Verdichtungslauf (``diskussion.starte``)."""
    repo.setze_status(conn, row["id"], "fertig")
    _web_sprachblase(conn, row["chat_id"], row["message_id"], row["transkript"] or None)
    _diskussion_entscheide(conn, tg, klm, e, row)


def _diskussion_entscheide(conn, tg, klm, e, row) -> None:
    """Die Entscheidung nach einem Diskussionssegment: Boardlauf, und beim
    Ende-Schnitt Abschluss (Vorschlag/Rueckfall) und Verdichtung. Getrennt
    von ``_diskussion_abschliessen``, weil sie seit 05.10.2026 auch nach
    einem VERWORFENEN Ende-Segment laeuft
    (``_abschluss_trotz_verworfenem_ende``)."""
    from interview_theater import begriffsboard  # lokaler Import, wie diskussion unten

    ende = row["schnittgrund"] == "ende"
    if ende:
        _warte_auf_offene_segmente(conn, e, row)
    begriffsboard.nach_segment(
        conn, tg, klm, e, row["chat_id"], ist_abschluss=ende,
        rueckfall_text=T._TEXT_DISKUSSION_KEINE_BEGRIFFE,
    )
    if ende:
        from interview_theater import diskussion  # lokaler Import, wie an anderen Cross-Modul-Stellen dieser Datei (z. B. bot)

        diskussion.starte(conn, tg, klm, e, row["chat_id"])


def _warte_auf_offene_segmente(conn, e, row, *, zaehle=None,
                               vorfall="diskussion_ende_segmente_offen") -> None:
    """Der Ende-Schnitt wartet, bis alle Segmente seiner Sitzung fertig sind
    (``ENDE_WARTEN_S``, 05.10.2026) -- erst dann sieht der Schlusslauf das
    komplette Transkript. Ein Segment, das in der Zwischenzeit fertig wird,
    geht seinen gewoehnlichen Weg (``begriffsboard.nach_segment`` ohne
    Abschluss; ``soll_laufen`` sieht dort schon den Ende-Schnitt als
    juengsten); laeuft dadurch gerade ein Lauf, entscheidet ``nach_segment``
    nach ihm neu. Laeuft im Pool-Thread, nie in einem Knopf-Handler.

    ``zaehle``/``vorfall``: dieselbe Wartebauart fuer den Brainstorm der
    Phase 4 (t_cf87ee0a) -- dort mit ``repo.offene_brainstorm_segmente``."""
    zaehle = zaehle or repo.offene_diskussion_segmente
    frist = time.monotonic() + ENDE_WARTEN_S
    while zaehle(conn, row["chat_id"], row["id"]):
        if time.monotonic() >= frist:
            log.warning("Ende ohne alle Segmente (%s), chat_id=%s", vorfall, row["chat_id"])
            try:
                repo.merke_vorfall(
                    conn, row["chat_id"], getattr(e, "bot_name", None),
                    vorfall,
                    f"ende_id={row['id']} warten_s={ENDE_WARTEN_S:.0f}",
                )
            except Exception:
                log.exception("Vorfall nicht geschrieben, chat_id=%s", row["chat_id"])
            return
        time.sleep(ENDE_WARTEN_TAKT_S)


def _abschluss_trotz_verworfenem_ende(conn, tg, klm, e, aufnahme_id: int) -> None:
    """Birk, Live-Test 05.10.2026 (Gruppe 2, Aufnahme 36): das Segment von
    "Discussion done" war leer (nur Stille nach dem Druck), wurde still
    verworfen -- und weil nur ein fertig transkribiertes Segment je bei
    ``_diskussion_abschliessen`` ankam, gab es keinen Schlusslauf, keine
    Verdichtung, keinen Vorschlag: der Bot schwieg, der letzte Begriff kam
    nie aufs Board. Seitdem: ist ein Ende-Segment endgueltig verworfen
    (``status='fehlgeschlagen'`` -- leer oder nach ``MAX_VERSUCHE``), laeuft
    derselbe Abschluss wie nach einem Ende-Segment mit Text; verworfen ist
    nur das Segment selbst. Ein Zwischensegment bleibt still wie bisher, und
    ein Segment, das noch einmal versucht wird (``empfangen``), wartet auf
    seinen naechsten Anlauf. Dasselbe fuer den Brainstorm der Phase 4."""
    row = repo.hole_aufnahme(conn, aufnahme_id)
    if row is None or row["status"] != "fehlgeschlagen" or row["schnittgrund"] != "ende":
        return
    try:
        if row["diskussion"]:
            _diskussion_entscheide(conn, tg, klm, e, row)
        elif row["brainstorm"]:
            _brainstorm_entscheide(conn, tg, klm, e, row)
    except Exception:
        log.exception("Abschluss nach verworfenem Ende-Segment fehlgeschlagen, chat_id=%s",
                      row["chat_id"])


def _brainstorm_abschliessen(conn, tg, klm, e, row) -> None:
    """Ein Segment des Knopfs "Brainstorm mithören" (Phase 4, nur Web,
    02.10.2026): bleibt ein stiller Gespraechsbeitrag der Gruppe -- die
    ``nachricht``-Zeile steht unveraendert, wie ``empfange()`` sie anlegte
    (``typ='sprache'``, ``text=NULL``, ``unterdrueckt=1``); nur das
    Transkript in ``aufnahme.transkript`` (schon gesetzt, siehe
    ``_verarbeite``) ist das Material. **Kein Gespraechszug, kein
    Absichtserkenner, kein Journal-Extraktor** -- was eine interviewte
    Person erzaehlt, ist kein Fall dafuer (docs/agents/entscheidungen.md), und ein stiller
    Brainstorm-Gedanke erst recht nicht.

    Danach die EINE Code-Entscheidung (kein Modellaufruf, Zusage 2):
    reicht es fuer eine Buehnenkarte? ``brainstorm.soll_reagieren`` prueft
    das rein anhand von Zahlen aus ``repo.brainstorm_stand``.

    ``schnittgrund == 'ende'`` heisst: dieses Segment ist der Flush beim
    Stopp des Toggles (t_cf87ee0a, Birk 03.10.2026: ein Toggle = ein
    Gedankenbogen; der Browser setzt ``'ende'`` vor ``alt.stop()``) -- das
    einzige Signal, das eine Karte (oder ein sichtbares Schweigen) ausloest.
    Es gibt dafuer keinen eigenen Serveraufruf: die Brainstorm-Sitzung kennt
    keinen Modus-Befehl, das LETZTE hochgeladene Segment TRAEGT das Ende."""
    repo.setze_status(conn, row["id"], "fertig")
    # Birk 02.10.2026: "das Transcript im Chat anzeigen als Feedback ist
    # wichtig. Nach jeder Pause-Detection [...] soll es sich auch im Chat
    # updaten." Die Blase bekommt ihr Transkript wie jede Sprachnachricht
    # (B7) -- NUR die Anzeige: die ``nachricht``-Zeile bleibt
    # ``unterdrueckt``, kein Gespraechszug, kein Erkenner (siehe oben).
    _web_sprachblase(conn, row["chat_id"], row["message_id"], row["transkript"] or None)
    _brainstorm_entscheide(conn, tg, klm, e, row)


def _brainstorm_entscheide(conn, tg, klm, e, row) -> None:
    """Die Code-Entscheidung nach einem Brainstorm-Segment (Buehnenkarte ja
    oder nein) -- getrennt von ``_brainstorm_abschliessen`` aus demselben
    Grund wie ``_diskussion_entscheide``.

    Seit t_cf87ee0a (Birk 03.10.2026): EIN Toggle = EIN Gedankenbogen.
    Waehrend der Toggle an ist, entsteht keine Karte (``pause``/``cap`` sind
    stille technische Schnitte); erst das Bogenende (``ende``) wartet auf alle
    Segmente des Bogens und entscheidet dann genau einmal: Karte (ueber
    ``_starte_buehnenkarte``) oder -- unter der Abschlussschwelle -- eine
    sichtbare Schweigen-Zeile. ``IT_BRAINSTORM_MIN_ZEICHEN``/``_MIN_ABSTAND_S``
    sind damit im Brainstorm ohne Wirkung (``soll_reagieren`` bleibt
    unveraendert, das Begriffsboard der Phase 1 nutzt es weiter).

    Laeuft beim Ende noch die Karte des VORIGEN Bogens, wartet das Ende auf
    sie (``_warte_auf_freien_kartenlauf``, hoechstens ``ENDE_LAUF_WARTEN_S``)
    -- sonst ginge dieser Bogen still leer aus, weil
    ``brainstorm.versuche_start`` belegt ist. Bleibt der Lauf trotzdem belegt
    (Frist abgelaufen, oder zwei Enden im selben Augenblick), kommt eine
    sichtbare Schweigen-Zeile (``modell='belegt'``) -- nie gar nichts.

    Der Bogen endet an ``row['id']`` (Review I2): Schwelle und Markierung
    zaehlen nur Segmente bis zum Ende-Segment; ein Segment des naechsten
    Bogens (Toggle waehrend des Wartens neu gestartet) bleibt unreagiert.

    Die Wartezeiten laufen im Pool- oder im Nachhol-Thread (``nachholen``
    kann dadurch bis zu ``ENDE_WARTEN_S + ENDE_LAUF_WARTEN_S`` blockieren),
    nie in einem Knopf-Handler."""
    if row["schnittgrund"] != "ende":
        return
    _warte_auf_offene_segmente(conn, e, row, zaehle=repo.offene_brainstorm_segmente,
                               vorfall="brainstorm_ende_segmente_offen")
    if klm is not None:
        _warte_auf_freien_kartenlauf(conn, e, row)
    # P34 Final-Review: hat die Karte eines SPAETER verarbeiteten Bogenendes
    # diesen Bogen schon abgedeckt, still auslassen -- keine 'schwelle'-Zeile
    # ueber der echten Karte.
    arbeitsstand = repo.hole_arbeitsstand(conn, row["chat_id"])
    if arbeitsstand and (arbeitsstand["brainstorm_markierung_id"] or 0) >= row["id"]:
        return
    stand = repo.brainstorm_stand(conn, row["chat_id"], bis_id=row["id"])
    sekunden = stand["sekunden_seit_letzter_reaktion"]
    soll = brainstorm.soll_reagieren(
        unreagierte_zeichen=stand["unreagierte_zeichen"],
        sekunden_seit_letzter_reaktion=sekunden if sekunden is not None else float("inf"),
        letzter_schnittgrund=stand["letzter_schnittgrund"],
        ist_abschluss=True,
    )
    if klm is None:
        if soll:
            _starte_buehnenkarte(conn, tg, klm, e, row["chat_id"], bis_id=row["id"])
        return
    if not soll:
        repo.lege_buehnenkarte_an(conn, row["chat_id"], "", "schwelle", schweigen=True)
    elif not _starte_buehnenkarte(conn, tg, klm, e, row["chat_id"], bis_id=row["id"]):
        repo.lege_buehnenkarte_an(conn, row["chat_id"], "", "belegt", schweigen=True)


def _warte_auf_freien_kartenlauf(conn, e, row) -> None:
    """Wartet (hoechstens ``ENDE_LAUF_WARTEN_S``, laenger als ein Kartenlauf
    nach ``buehnenkarte.TIMEOUT_S`` dauern darf), bis kein Buehnenkarten-Lauf
    dieser Gruppe mehr laeuft (t_cf87ee0a: genau eine Reaktion je Bogen).
    Erst danach liest ``brainstorm_stand`` -- die Markierung des vorigen
    Laufs steht dann, die Zeichen DIESES Bogens zaehlen als unreagiert.
    Laeuft im Pool- oder Nachhol-Thread, nie in einem Knopf-Handler."""
    frist = time.monotonic() + ENDE_LAUF_WARTEN_S
    while brainstorm.laeuft(row["chat_id"]):
        if time.monotonic() >= frist:
            log.warning("Brainstorm-Ende: Kartenlauf noch belegt, chat_id=%s", row["chat_id"])
            try:
                repo.merke_vorfall(
                    conn, row["chat_id"], getattr(e, "bot_name", None),
                    "brainstorm_ende_lauf_belegt",
                    f"ende_id={row['id']} warten_s={ENDE_LAUF_WARTEN_S:.0f}",
                )
            except Exception:
                log.exception("Vorfall nicht geschrieben, chat_id=%s", row["chat_id"])
            return
        time.sleep(ENDE_WARTEN_TAKT_S)


def _starte_buehnenkarte(conn, tg, klm, e, chat_id: int, *,
                         bis_id: int | None = None) -> bool:
    """Stoesst einen Buehnenkarten-Lauf in einem eigenen Thread an (Zusage 2:
    kein Modellaufruf hier selbst). Hoechstens ein Lauf je Gruppe gleichzeitig
    (``brainstorm.versuche_start``) -- wer die Sperre nicht bekommt, verliert
    nichts: die unreagierten Zeichen bleiben stehen und zaehlen beim naechsten
    qualifizierenden Segment einfach weiter mit ("pending text accumulates
    into the next turn").

    Liefert, ob der Lauf gestartet wurde -- das Bogenende schreibt sonst eine
    sichtbare Schweigen-Zeile (Review I1). ``bis_id``: die Markierung endet
    am Ende-Segment des Bogens statt an der juengsten Brainstorm-id (Review
    I2). Wirft der Lauf, haengt er ebenfalls eine Schweigen-Zeile an
    (``modell='fehler'``, Review M2) -- einziger Aufrufer ist der Brainstorm
    der Phase 4."""
    if klm is None:
        return False
    if not brainstorm.versuche_start(chat_id):
        return False
    try:
        repo.markiere_buehnenkarten_lauf(conn, chat_id, repo._jetzt())
        # VOR dem Lauf gelesen: die Markierung soll genau die Segmente
        # abdecken, die die Karte tatsaechlich gesehen hat -- ein waehrend des
        # Laufs neu eingetroffenes Segment bleibt UNREAGIERT und zaehlt beim
        # naechsten Mal.
        markierung_id = (bis_id if bis_id is not None
                         else repo.hoechste_brainstorm_aufnahme_id(conn, chat_id))
    except BaseException:
        # P34 Final-Review: ohne Thread kein ``finally`` in ``_lauf`` -- die
        # Sperre wuerde haengen, und jedes spaetere Bogenende wartete
        # ``ENDE_LAUF_WARTEN_S`` und schwiege dann 'belegt'.
        brainstorm.beende(chat_id)
        raise

    def _lauf() -> None:
        angelegt = False
        try:
            text, modell = buehnenkarte.erzeuge(conn, e, klm, chat_id)
            if text:
                repo.markiere_brainstorm_reaktion(conn, chat_id, markierung_id)
                repo.lege_buehnenkarte_an(conn, chat_id, text, modell)
                angelegt = True
                # Birk, 02.10.2026 (Padua-Feedback b): KEINE Chat-Zeile mehr --
                # der Bot "antwortet" im Brainstorm-Modus nirgends sonst als
                # ueber den unaufdringlichen Marker am CoThinker-Tab (den
                # setzt ``web_vereint``/``web_chat`` allein aus einer neuen
                # Karte in ``buehnenkarten``, kein Schreibzugriff hier noetig)
                # und das Panel selbst, das sich waehrend es offen ist im
                # selben Poll-Takt aktualisiert (``_VEREINT_JS.ladeBuehne``).
            else:
                # NICHTS oder ein Fehlschlag: "nothing changes" -- keine
                # Markierung, kein Chateintrag. Das naechste qualifizierende
                # Segment sieht denselben (oder einen groesseren) Stand
                # erneut. Eine Zeile kommt trotzdem in die Tabelle (Karte
                # Padua Brainstorm, 03.10.2026): sonst ist "zugehoert,
                # geschwiegen" von "nie gelaufen" nicht zu unterscheiden --
                # weder im Dashboard noch im Buehne-Panel.
                repo.lege_buehnenkarte_an(conn, chat_id, "", modell, schweigen=True)
                angelegt = True
        except Exception:
            log.exception("Buehnenkarten-Lauf fehlgeschlagen, chat_id=%s", chat_id)
            if not angelegt:
                # Review M2: auch ein geworfener Lauf ist fuer die Gruppe
                # eine sichtbare Reaktion ("nothing to add"), kein Nichts.
                try:
                    repo.lege_buehnenkarte_an(conn, chat_id, "", "fehler", schweigen=True)
                except Exception:
                    log.exception("Schweigen-Zeile nicht geschrieben, chat_id=%s", chat_id)
        finally:
            brainstorm.beende(chat_id)
            repo.markiere_buehnenkarten_lauf(conn, chat_id, None)

    threading.Thread(target=_lauf, daemon=True).start()
    return True


def dauer_mmss(sekunden: int) -> str:
    """``186`` -> ``\"3:06\"``. Die Gruppe erkennt ihre Aufnahme an der Laenge,
    nicht an einer Sekundenzahl."""
    sekunden = max(0, int(sekunden or 0))
    return f"{sekunden // 60}:{sekunden % 60:02d}"


def _frage_interview_ohne_knopf(conn, tg, e, chat_id: int, aufnahme_id: int, dauer: int) -> None:
    """Die deterministische Frage nach einer langen Sprachnachricht OHNE
    laufenden Interviewmodus (06.09.2026, Live-Fall Gruppe 1, 13:32-13:37).

    Was an dem Tag passierte: die Gruppe schickte 186 Sekunden Interview,
    ohne vorher \"Interview starten\" zu druecken. Das Transkript ging als
    **Gespraechsbeitrag** in den Kontext, das Gespraechsmodell antwortete mit
    einem Denkspur-Rest, der **Absichtserkenner** las die Aufzaehlung der
    interviewten Person als Begriffsliste der Gruppe und ueberschrieb
    ``arbeitsstand.begriffe``, und der Journal-Extraktor schrieb einen
    Vorschlag aus dem Interviewinhalt. Drei Modellaufrufe auf Material, das
    keine Absicht der Gruppe war -- genau der Fall, gegen den
    ``repo.TYP_TRANSKRIPT`` seit § 10.6 schuetzt, nur hier ungeschuetzt, weil
    ohne Modus niemand ein Interview vermutete.

    Deshalb jetzt: **kein Gespraechszug, kein Erkenner, kein Journal** auf
    dieser Nachricht. Das Transkript ist gespeichert (Empfangen und
    In-den-Prompt-legen sind zwei Entscheidungen), steht aber versteckt
    (``versteckt=True``) und damit in keinem Fenster, bis die Gruppe geklaert
    hat, was es war. Der Knopf traegt die Auswahl selbst -- es gibt etwas
    Fixes zu speichern, also ist die Knopfregel erfuellt (docs/agents/entscheidungen.md).

    Kommt keine Antwort, passiert **nichts**: kein Auto-Ja, kein Zeitgeber.
    Das Material liegt da und kann jederzeit ueber \"Interview starten\" als
    Nachzuegler eingesammelt werden -- der Weg, der am Live-Tag fuenf Minuten
    spaeter tatsaechlich funktioniert hat. Fuers Dashboard bleibt ein
    Vorfall ``interview_ohne_knopf_offen`` stehen."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    text = T._TEXT_INTERVIEW_OHNE_KNOPF.format(dauer=dauer_mmss(dauer))
    try:
        knoepfe.biete_interview_ohne_knopf(conn, tg, chat_id, text, aufnahme_id)
    except Exception:
        log.exception("Interview-Rueckfrage fehlgeschlagen, chat_id=%s", chat_id)
        return
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "interview_ohne_knopf_offen",
            f"Aufnahme {aufnahme_id} ({dauer_mmss(dauer)}) wartet auf Ja/Nein",
        )
    except Exception:
        log.exception("Vorfall interview_ohne_knopf_offen fehlgeschlagen, chat_id=%s", chat_id)


def nimm_als_interview(conn, tg, chat_id: int, aufnahme_id: int) -> int | None:
    """\"Ja, als Interview\": legt den Kopf an, sammelt GENAU diese Aufnahme
    ein und sichert Phase 3. Liefert die Kopf-id.

    Kein Modellaufruf (Zusage 2) -- alles hier ist Datenbank und eine feste
    Meldung. ``stelle_interview_sicher`` sammelt zwar seine Nachzuegler
    ohnehin ein, aber nur die der letzten ``NACHZUEGLER_FENSTER_S`` Sekunden:
    zwischen Aufnahme und Knopfdruck koennen mehr liegen (die Gruppe steht im
    Raum). Deshalb danach ausdruecklich ``repo.ziehe_eine_in_interview`` mit
    der bekannten id -- die eine Aufnahme, um die es geht, haengt danach in
    jedem Fall am Kopf.

    Der Interviewmodus bleibt dabei AN: es koennen noch Sprachnachrichten
    kommen, und erst \"Fertig, auswerten\" beendet das Interview."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    kopf_id = stelle_interview_sicher(conn, chat_id)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    if row is not None and row["teil_von"] != kopf_id:
        repo.ziehe_eine_in_interview(conn, aufnahme_id, kopf_id)
    stelle_phase_interviews_sicher(conn, tg, chat_id, quelle="knopf")
    return kopf_id


def nimm_als_beitrag(conn, tg, klm, e, chat_id: int, aufnahme_id: int) -> bool:
    """\"Nein, war ein Beitrag\": macht das versteckte Transkript sichtbar und
    holt Gespraechszug samt Erkenner GENAU EINMAL nach (06.09.2026).

    Bis zum Knopfdruck stand die Zeile als ``TYP_TRANSKRIPT`` in der
    Datenbank und damit in keinem Fenster. Jetzt ist geklaert, dass es ein
    Beitrag der Gruppe war -- also gehoert sie in Verlauf, Erkenner und
    Journal, und die Gruppe bekommt die Antwort, die sie vorhin bekommen
    haette.

    Der Zug laeuft in einem eigenen Thread: ein Knopf-Handler macht keinen
    Modellaufruf (Zusage 2, AGENTS.md). Liefert True, wenn die Aufnahme
    bekannt war."""
    row = repo.hole_aufnahme(conn, aufnahme_id)
    if row is None:
        return False
    repo.zeige_transkript_nachricht(conn, chat_id, row["message_id"])
    _web_sprachblase(conn, chat_id, row["message_id"], row["transkript"])
    starte_nachgeholten_zug(conn, tg, klm, e, chat_id)
    return True


def starte_nachgeholten_zug(conn, tg, klm, e, chat_id: int):
    """Stoesst ``bot._zug_und_erkenner`` in einem eigenen Thread an -- der
    normale Weg nach einer Textnachricht, hier einmal nachgeholt.

    Der spaete Import haelt ``aufnahme.py`` frei von ``bot.py`` im Modulkopf
    (derselbe Grund wie bei ``_kein_zug``). ``klm is None`` (Tests ohne
    Modell) laeuft ins Leere statt in eine Ausnahme."""
    if klm is None:
        return None

    def _lauf() -> None:
        from interview_theater import bot

        try:
            bot._zug_und_erkenner(conn, tg, klm, e, chat_id)
        except Exception:
            log.exception("Nachgeholter Gespraechszug fehlgeschlagen, chat_id=%s", chat_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    return thread


def _sende_und_merke(conn, tg, e, chat_id: int, text: str, typ: str = "text",
                     system: bool = False) -> None:
    """Schickt eine Bot-Nachricht und schreibt sie in ``nachricht`` mit --
    wie ``ablauf.antworte`` und ``erkenner.laufe`` es tun.

    ``typ='transkript'`` ist der Sonderfall dieses Moduls (§ 10.6): die Zeile
    wird gespeichert (Empfangen und In-den-Prompt-legen sind zwei
    Entscheidungen), taucht aber in keinem Fenster auf -- siehe
    ``repo.TYP_TRANSKRIPT``. Ein Fehlschlag beim Senden wird nur geloggt: der
    Inhalt selbst steht laengst in der Datenbank.

    ``system=True`` nur aus ``_sende_nach_interview`` (Karte t_ea994c7f)."""
    try:
        message_id = tg.sende(chat_id, text, system=True) if system else tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, typ,
            text, repo._jetzt(), 1 if typ == repo.TYP_TRANSKRIPT else 0,
        )
    except Exception:
        log.exception("Nachricht an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _text_interview_gespeichert_web(conn, row, verdichtung_id: int, e) -> str:
    """Die Zeile nach einem Interview im Web-Kanal (02.10.2026): ersetzt
    ``_TEXT_AUSGEWERTET`` dort -- Name, Uhrzeit, Dauer, bis zu drei Themen,
    ein fester Hinweis auf den (noch nicht zusammengefuehrten) Arbeitsstand-
    Tab. Keine Gesamtauswertung ueber alle Interviews -- das ist Sache von
    ``knoepfe.stationen.schliesse_interviews_ab``."""
    name = anzeigename(conn, row, T._TEXT_DAS_INTERVIEW)
    zone = getattr(e, "zeitzone", None) or "Europe/Rome"
    try:
        ort = ZoneInfo(zone)
    except Exception:
        ort = ZoneInfo("Europe/Rome")
    uhrzeit = datetime.now(ort).strftime("%H:%M")
    sekunden = sum((teil["dauer_sekunden"] or 0) for teil in repo.hole_teile(conn, row["id"]))
    minuten = max(1, round(sekunden / 60))
    zeilen = [T._TEXT_GESPEICHERT_WEB.format(name=name, uhrzeit=uhrzeit, minuten=minuten)]
    themen = [
        (t["kurz"] or "").strip()
        for t in repo.themen_zu(conn, verdichtung_id)
        if (t["kurz"] or "").strip()
    ][:3]
    if themen:
        zeilen.append(T._TEXT_THEMEN_WEB + " · ".join(themen))
    zeilen.append(T._TEXT_AUSWERTUNG_IM_TAB)
    return "\n".join(zeilen)


def _sende_nach_interview(conn, tg, e, chat_id: int, text: str, kopf_id: int | None,
                          system: bool = False) -> None:
    """Schickt die Abschlussnachricht eines Interviews MIT der Knopfleiste
    darunter (05.09.2026) und schreibt sie wie jede Bot-Nachricht mit.

    Die eine Stelle, an der der Weg nach einem Interview angeboten wird --
    ``/aufnahme`` und der Erkenner-Pfad enden beide hier, ueber
    ``schliesse_ab``. Der Text ist die Zeile darueber (Dauer/Wortzahl,
    "ist abgelegt", "hatte keine Aufnahme"), die Knoepfe sind der Weg:
    Auswerten, Naechste Aufnahme, und -- wenn die Materiallage es hergibt --
    Weiter zu Phase N.

    Faellt die Tastatur aus (Telegram-Fehler), geht der Text trotzdem raus:
    ``_sende_und_merke`` als Rueckfall. Die Gruppe soll wegen einer
    misslungenen Tastatur nicht ohne Rueckmeldung dastehen."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    try:
        message_id = knoepfe.biete_nach_aufnahme(conn, tg, chat_id, text, kopf_id, system=system)
    except Exception:
        log.exception("Knopfleiste nach Interview fehlgeschlagen, chat_id=%s", chat_id)
        _sende_und_merke(conn, tg, e, chat_id, text, system=system)
        return
    try:
        repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    except Exception:
        log.exception("Abschlussnachricht mitzuschreiben fehlgeschlagen, chat_id=%s", chat_id)


def _an_den_bot_abzweigen(conn, tg, klm, e, row, zug, nachgeholt) -> None:
    """Nimmt eine Sprachnachricht aus dem Interview heraus und gibt sie in den
    Gespraechszug (N4, 05.09.2026).

    Der Fall: mitten im Interviewmodus spricht jemand den BOT an ("zeig mir
    die Verdichtungen von den Interviews", "was war nochmal die zweite
    Frage") -- nicht die Person, die gerade erzaehlt. Bis heute wurde daraus
    ein Interview-Teil: er stand im Transkript, ging in die Verdichtung ein
    und wurde nie beantwortet. Genau so ist im Probelauf aus "Zeigt mir die
    Verdichtungen von den Interviews an." ein erfundenes Interview geworden.

    Der Weg ist dann derselbe wie fuer jede Sprachnachricht ausserhalb des
    Modus: Klasse ``kurz``, das Transkript wandert in die Nachrichtenzeile und
    loest einen Gespraechszug aus (``_kurz_abschliessen``). Kein
    Transkript-Echo -- das gehoert zur Kontrolle von Interviewmaterial, und
    Material ist das hier gerade nicht."""
    repo.loese_aus_interview(conn, row["id"])
    _kurz_abschliessen(
        conn, tg, klm, e, repo.hole_aufnahme(conn, row["id"]), zug, nachgeholt
    )


#: Eine Sperre je Interview-Kopf fuer "Teile lesen + Blase anlegen oder
#: aendern + echo_message_id merken" (Karte t_ea994c7f, Entscheidung C).
#: Teile laufen im Pool (``bot.POOL_GROESSE``): ohne die Sperre laegen zwei
#: gleichzeitig fertige Teile beide "noch keine Blase" und legten zwei an,
#: oder der spaetere Text ueberschriebe den vollstaendigeren. Je Kopf statt
#: je Gruppe, wie die Register in ``ablauf``/``szene`` -- gemeinsam haette
#: es nichts zu schuetzen.
_blasen_sperren: dict[int, threading.Lock] = {}
_blasen_sperren_schutz = threading.Lock()


def _blasen_sperre(kopf_id: int) -> threading.Lock:
    """Liefert die (ggf. neu angelegte) Sperre fuer einen Interview-Kopf."""
    with _blasen_sperren_schutz:
        sperre = _blasen_sperren.get(kopf_id)
        if sperre is None:
            sperre = threading.Lock()
            _blasen_sperren[kopf_id] = sperre
        return sperre


def fliesstext_aktiv(conn, chat_id: int) -> bool:
    """Gilt fuer diese Gruppe die EINE Transkriptblase je Interview samt der
    Systemzeilen rund ums Interview (Karte t_ea994c7f)? Nur mit
    ``[interview] fliesstext`` UND nur im Web-Kanal -- Telegram behaelt das
    Echo je Teil mit seiner Leiste, auch mit dem Schalter."""
    return workshop.interview_fliesstext() and ist_web_gruppe(conn, chat_id)


def transkript_blasentext(conn, kopf) -> str:
    """Der ganze Text der Transkriptblase, bei JEDEM Teil neu gebaut statt
    angehaengt (Entscheidung B): Kopfzeile, Leerzeile, alle Teile mit
    Transkript in Eingangsreihenfolge, je durch eine Leerzeile getrennt.

    Ausgewaehlt wird nach ``transkript``, nicht nach ``status``: der Teil,
    der gerade abgeschlossen wird, steht noch auf 'transkribiert'. Ein per
    ``an_den_bot`` abgezweigter Teil faellt heraus, weil
    ``repo.loese_aus_interview`` sein ``teil_von`` leert."""
    teile = [
        (teil["transkript"] or "").strip()
        for teil in repo.hole_teile(conn, kopf["id"])
        if (teil["transkript"] or "").strip()
    ]
    kopfzeile = T._TEXT_TRANSKRIPT_KOPF.format(name=anzeigename(conn, kopf, "Interview"))
    return "\n\n".join([kopfzeile, *teile])


def _sende_transkript_blase(conn, tg, e, chat_id: int, kopf_id: int, nur_aendern: bool = False) -> None:
    """Legt die EINE Transkriptblase eines Interviews an oder schreibt sie
    weiter (Karte t_ea994c7f).

    Gibt es noch keine (``aufnahme.echo_message_id`` leer), geht sie mit
    ``transkript=True`` raus, wird am Kopf gemerkt und -- wie jedes
    Teil-Echo -- einmal versteckt in ``nachricht`` mitgeschrieben.
    Spaetere Teile tauschen nur ihren Text (``tg.aendere_text``); die
    Mitschrift wird dabei NICHT nachgezogen: sie steht in keinem Fenster,
    die Wahrheit ist ``aufnahme.transkript`` (Entscheidung F).

    ``nur_aendern=True`` schreibt nur eine schon vorhandene Blase neu und
    legt nie eine an (Nachlauf nach ``an_den_bot``).

    Ein Fehlschlag kostet nur die Anzeige, nie das Transkript.
    Unter ``_blasen_sperre(kopf_id)``."""
    with _blasen_sperre(kopf_id):
        kopf = repo.hole_aufnahme(conn, kopf_id)
        if kopf is None:
            return
        text = transkript_blasentext(conn, kopf)
        message_id = repo.echo_message_id(conn, kopf_id)
        if message_id is not None:
            try:
                tg.aendere_text(chat_id, message_id, text)
            except Exception:
                log.exception("Transkriptblase nicht aktualisiert, kopf_id=%s", kopf_id)
            return
        if nur_aendern:
            return
        try:
            message_id = tg.sende(chat_id, text, transkript=True)
        except Exception:
            log.exception("Transkriptblase nicht gesendet, kopf_id=%s", kopf_id)
            return
        repo.setze_echo_message_id(conn, kopf_id, message_id)
        try:
            repo.merke_nachricht(
                conn, chat_id, message_id, getattr(e, "bot_name", None), 1,
                repo.TYP_TRANSKRIPT, text, repo._jetzt(), 1,
            )
        except Exception:
            log.exception("Transkriptblase mitzuschreiben fehlgeschlagen, chat_id=%s", chat_id)


def _teil_abschliessen(conn, tg, klm, e, row, zug=_kein_zug, nachgeholt=False) -> None:
    """Stellt das Transkript eines Interview-Teils sofort und woertlich in den
    Chat (§ 10.6, Birk 04.09. abends: "Transkript Stueck fuer Stueck").

    Mit ``fliesstext_aktiv`` (Padua, Web) geht statt des Echos je Teil die
    EINE Transkriptblase raus (``_sende_transkript_blase``).

    Kein Kommentar, keine Zusammenfassung -- die Gruppe soll waehrend das
    Gegenueber noch im Raum sitzt kontrollieren koennen, ob angekommen ist,
    was gesagt wurde. Verdichtet wird erst bei "fertig", ueber das ganze
    Interview (``schliesse_ab``).

    **Ein Modellaufruf ist seit N1 doch dabei**, und zwar der billige: der
    Absichtserkenner (gemma, unter einer Sekunde nach dem Warmlauf) laeuft
    ueber das Transkript und sucht darin drei Dinge --
    ``interview_beenden``, ``interview_benennen`` und seit N4 ``an_den_bot``
    (``erkenner.ARTEN_IN_AUFNAHME``). Die Gruppe sagt "so, das Interview ist
    fertig" naemlich meistens in die Aufnahme hinein, nicht in den Chat, und
    das Transkript-Echo steht in keinem Erkenner-Fenster. Der Teil selbst
    bleibt trotzdem Teil des Interviews: der Satz ist mit aufgenommen worden
    und steht harmlos am Ende des Transkripts.

    ``an_den_bot`` ist der eine Fall, in dem er das NICHT tut: dann war die
    Sprachnachricht gar kein Material, sondern eine Frage an den Bot, und sie
    geht denselben Weg wie jede Sprachnachricht ausserhalb des Modus
    (``_an_den_bot_abzweigen``).

    Reihenfolge: erst erkennen (schreibt nichts), dann Echo und 'fertig',
    dann anwenden. Andersherum faende ``schliesse_ab`` genau diesen Teil noch
    offen und verschoebe den Abschluss um ein Nachhol-Intervall.

    Der Status wird auch dann auf 'fertig' gesetzt, wenn das Senden
    misslingt: das Transkript ist gespeichert, und ein zweiter Anlauf wuerde
    Whisper erneut bezahlen, um dieselbe Zeile noch einmal zu schicken."""
    from interview_theater import erkenner  # spaeter Import, haelt den Modulkopf frei

    chat_id = row["chat_id"]
    aenderungen = (
        erkenner.erkenne_in_aufnahme(klm, conn, e, chat_id, row["transkript"])
        if klm is not None
        else []
    )

    if any(a.get("art") == "an_den_bot" for a in aenderungen):
        kopf_id = row["teil_von"]
        _an_den_bot_abzweigen(conn, tg, klm, e, row, zug, nachgeholt)
        # Karte t_ea994c7f: ein paralleler Teil kann die Blase schon MIT
        # diesem Transkript gebaut haben -- jetzt, wo es aus dem Interview
        # geloest ist, einmal ohne es neu schreiben. Nie neu anlegen.
        if kopf_id is not None and fliesstext_aktiv(conn, chat_id):
            _sende_transkript_blase(conn, tg, e, chat_id, kopf_id, nur_aendern=True)
        # Die uebrigen Arten gelten weiter: "fertig, und zeig mir die
        # Verdichtungen" ist beides. Erst abzweigen (die Aufnahme steht danach
        # auf 'fertig'), dann anwenden -- sonst faende schliesse_ab sie noch
        # offen.
        _wende_aus_aufnahme_an(conn, tg, klm, e, chat_id, row, aenderungen)
        return

    if fliesstext_aktiv(conn, chat_id):
        # Padua (04.10.2026, Karte t_ea994c7f): EINE Blase je Interview, aus
        # allen Teilen mit Transkript neu gebaut -- ohne Leiste, die deckt
        # im Web der eigene Aufnahme-Regler ab.
        _sende_transkript_blase(conn, tg, e, chat_id, row["teil_von"])
    else:
        kopf = repo.hole_aufnahme(conn, row["teil_von"])
        text = T._TEXT_TEIL_ECHO.format(
            name=anzeigename(conn, kopf, "Interview") if kopf else "Interview",
            nummer=repo.teil_nummer(conn, row["id"]),
            transkript=row["transkript"],
        )
        _sende_teil_echo(conn, tg, e, chat_id, text)
    repo.setze_status(conn, row["id"], "fertig")
    # B7: das Echo traegt das Transkript schon -- die Blase nicht noch einmal.
    _web_sprachblase(conn, chat_id, row["message_id"], None)
    angestossen = _wende_aus_aufnahme_an(conn, tg, klm, e, chat_id, row, aenderungen)

    # Race (Padua A2, gemessen): "fertig" kann eintreffen, waehrend dieser
    # Teil noch bei Whisper haengt -- schliesse_ab() fand den Kopf dann noch
    # offen (hat_offene_teile) und gab auf, ohne sich selbst zu wiederholen.
    # Bis zum naechsten Nachhol-Lauf (NACHHOL_INTERVALL_S = 60 s) blieb die
    # Verdichtung aus. Dieser Teil ist jetzt der letzte, der fertig werden
    # konnte -- ist der Kopf bereits beendet ("fertig" wurde schon gesagt),
    # wird der Abschluss hier sofort erneut versucht statt auf den
    # Nachhol-Arbeiter zu warten.
    #
    # Der Kopf wird HIER frisch gelesen, nicht der Schnappschuss von oben
    # wiederverwendet: zwischen beiden liegen Echo, Status und Erkenner, und
    # genau in diesem Fenster trifft "fertig" ein. Weil der Status dieses
    # Teils schon VOR diesem Lesen committet ist, bleibt kein Fenster: setzt
    # "fertig" beendet_am vor diesem Lesen, sehen wir es hier; setzt es
    # danach, sieht schliesse_ab() auf seinem eigenen Weg diesen Teil bereits
    # als 'fertig'. None (Kopf hart geloescht, scripts/loeschen.py) heisst:
    # nichts mehr abzuschliessen.
    #
    # Hat der Erkenner "fertig" in DIESEM Teil gehoert, hat er den Abschluss
    # gerade selbst angestossen (``starte_abschluss``, eigener Thread) und
    # dabei beendet_am gesetzt -- die Nachpruefung saehe genau das und riefe
    # schliesse_ab ein zweites Mal. Der Thread startet erst NACH dem 'fertig'
    # dieses Teils, er findet also keinen offenen Teil von hier mehr; ein
    # zweiter Aufruf haette nichts zu retten. Gilt nur fuer denselben Kopf
    # und nur, wenn der Thread wirklich gestartet ist (sonst None).
    kopf = repo.hole_aufnahme(conn, row["teil_von"])
    if (
        kopf is not None
        and kopf["id"] != angestossen
        and kopf["beendet_am"]
        and kopf["status"] == "laeuft"
    ):
        try:
            schliesse_ab(conn, tg, klm, e, kopf["id"])
        except Exception:
            log.exception(
                "Interviewabschluss nach letztem Teil fehlgeschlagen, kopf_id=%s",
                kopf["id"],
            )


def _sende_teil_echo(conn, tg, e, chat_id: int, text: str) -> None:
    """Schickt das Teil-Transkript MIT der Leiste "Interview geht weiter" ·
    "Interview ist fertig" darunter (05.09.2026, ``knoepfe.biete_nach_teil``).

    Der Anlass (Live-Lauf Gruppe 1): das Echo stand da, und die Gruppe wusste
    nicht, ob das Interview weitergeht oder fertig ist. Die naechste Antwort
    wird jetzt aktiv angeboten statt vorausgesetzt.

    Die Nachricht bleibt ``typ='transkript'`` und damit in KEINEM
    Erkenner-Fenster (§ 10.6): eine Tastatur darunter aendert nichts daran,
    dass Interviewinhalt keine Gruppenabsicht ist.

    Faellt die Tastatur aus (Telegram-Fehler), geht das Echo trotzdem raus --
    das Transkript ist wichtiger als die Knoepfe.

    Auf dem Web-Kanal (06.10.2026, Phase 3 Web-UX) entfaellt die Leiste ganz:
    Pause/Weiter/Beenden des eigenen Aufnahme-Reglers deckt ab, was Telegram
    hier mit zwei Knoepfen anbietet. Das Echo geht unveraendert raus -- derselbe
    Weg wie der bestehende Fehlerrueckfall unten, nur ohne Fehler."""
    if ist_web_gruppe(conn, chat_id):
        _sende_und_merke(conn, tg, e, chat_id, text, typ=repo.TYP_TRANSKRIPT)
        return

    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    try:
        message_id = knoepfe.biete_nach_teil(conn, tg, chat_id, text)
    except Exception:
        log.exception("Leiste unter dem Teil-Echo fehlgeschlagen, chat_id=%s", chat_id)
        _sende_und_merke(conn, tg, e, chat_id, text, typ=repo.TYP_TRANSKRIPT)
        return
    try:
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1,
            repo.TYP_TRANSKRIPT, text, repo._jetzt(), 1,
        )
    except Exception:
        log.exception("Teil-Echo mitzuschreiben fehlgeschlagen, chat_id=%s", chat_id)


def _wende_aus_aufnahme_an(conn, tg, klm, e, chat_id, row, aenderungen) -> int | None:
    """Ruft ``erkenner.wende_aus_aufnahme_an`` und faengt jeden Fehler ab.

    Ein Fehlschlag hier darf den Teil nicht mitreissen: sein Transkript steht
    laengst in der Datenbank und im Chat, und der Nachhol-Arbeiter greift ein
    liegengebliebenes Interview beim naechsten Durchlauf ohnehin auf.

    Liefert die id des Interviews, dessen Abschluss dabei angestossen wurde,
    sonst None (auch bei einem Fehler)."""
    from interview_theater import erkenner  # spaeter Import, haelt den Modulkopf frei

    try:
        return erkenner.wende_aus_aufnahme_an(klm, tg, conn, e, chat_id, aenderungen)
    except Exception:
        log.exception(
            "Anwenden einer Absicht aus einem Teil fehlgeschlagen, id=%s", row["id"]
        )
        return None


def _verdichtungstext(conn, name: str, verdichtung_id: int) -> str:
    """Baut die Rueckmeldung zu einem verdichteten Interview (§ 10.6).

    Seit N2 traegt jedes gespeicherte Thema ein geprueftes Zitat (siehe
    ``verdichter.verdichte``) -- die Zeile ohne Anfuehrungszeichen bleibt
    trotzdem stehen, fuer Verdichtungen aus der Zeit davor. Bleibt gar kein
    Thema uebrig, sagt der Bot genau das, statt die Kernthemen-Ueberschrift
    ueber eine leere Liste zu setzen.

    Am Ende eine echte Rueckfrage -- keine, auf die etwas wartet: der Bot
    laeuft weiter, ob die Gruppe antwortet oder nicht (SPEC § 1.4)."""
    verdichtung = repo.hole_verdichtung(conn, verdichtung_id)
    zeilen = [
        T._TEXT_VERDICHTUNG_KOPF.format(name=name),
        verdichtung["zusammenfassung"] if verdichtung else "",
        "",
    ]
    themen = repo.themen_zu(conn, verdichtung_id)
    if themen:
        zeilen.append(T._TEXT_VERDICHTUNG_THEMEN)
        for thema in themen:
            if thema["zitat_geprueft"] == 1 and thema["beleg_zitat"]:
                zeilen.append(f'- {thema["thema"]}: "{thema["beleg_zitat"]}"')
            else:
                zeilen.append(f'- {thema["thema"]}')
    else:
        zeilen.append(T._TEXT_OHNE_BELEG)
    zeilen.append("")
    return "\n".join(zeilen)


def _phasenfrage(conn, chat_id: int) -> str:
    """Die Zeile "Kommen noch Interviews, oder gehen wir ans Kernthema?" --
    oder leer.

    Nur aus Phase 3 heraus und nur, solange der Schritt nach 4 noch nicht
    angeboten wurde (``phasen.offenes_angebot``). Beides ist noetig: aus
    Phase 4 heraus ist die Frage schon beantwortet, und ohne den Merkposten
    stuende sie unter jeder einzelnen Verdichtung -- bei fuenf Interviews
    fuenfmal dieselbe Frage.

    Gemerkt wird nur, wenn die Zeile auch wirklich mitgeht: sonst
    verschluckte diese Stelle das Angebot, das der Gespraechs-Prompt
    (``kontext._baue_phasenhinweis``) sonst gemacht haette."""
    if phasen.aktuelle(conn, chat_id) != 3:
        return ""
    if phasen.offenes_angebot(conn, chat_id) != 4:
        return ""
    phasen.merke_angebot(conn, chat_id, 4)
    return T._TEXT_PHASENFRAGE


def _zu_kurz_gemeldet(conn, tg, e, row) -> bool:
    """Prueft die Mindestlaenge (N2) und meldet, wenn sie unterschritten ist.

    Liefert True, wenn dieses Interview NICHT verdichtet wird: dann ist es
    fertig, die Gruppe hat eine Zeile mit Dauer und Wortzahl bekommen und kann
    mit ``/auswerten`` widersprechen. Kein Sprachmodell-Aufruf -- genau das
    ist der Punkt (siehe MINDEST_WOERTER)."""
    woerter = len((row["transkript"] or "").split())
    if woerter >= MINDEST_WOERTER:
        return False
    repo.setze_status(conn, row["id"], "fertig")
    # Padua Phasen TEIL 2, Task 1/5 (Befund 4a): ohne dieses Flag blieb ein
    # zu-kurz uebersprungenes Interview in unausgewertete_interviews() stehen
    # (status='fertig', aber keine Verdichtung) und sperrte Phase 4 auf
    # unbestimmte Zeit -- genau der Fall der Padua-Gruppe.
    repo.setze_zu_kurz_uebersprungen(conn, row["id"])
    _sende_nach_interview(
        conn, tg, e, row["chat_id"],
        T._TEXT_ZU_KURZ.format(
            name=anzeigename(conn, row, T._TEXT_DAS_INTERVIEW),
            woerter=woerter,
        ),
        row["id"],
        system=fliesstext_aktiv(conn, row["chat_id"]),
    )
    return True


def zeige_verdichtung(conn, tg, e, kopf_id: int) -> bool:
    """Stellt eine schon vorhandene Verdichtung in den Chat. Liefert False,
    wenn es zu diesem Interview noch keine gibt.

    Der Grund, warum es diese Funktion gibt (05.09.2026): seit dem
    Nachmittag wird zwar sofort verdichtet, aber NICHT mehr von selbst
    ausgespielt (siehe ``_TEXT_INTERVIEW_ABGELEGT``). Wer die Auswertung
    sehen will -- ueber den Knopf "Auswerten" oder ``/auswerten`` --, muss
    sie also aus der Datenbank bekommen und nicht ein zweites Mal verdichten
    lassen: eine Verdichtung wird nie nachtraeglich geaendert (docs/agents/entscheidungen.md),
    und ein zweiter Lauf waere ein zweiter bezahlter Modellaufruf mit einem
    anderen Ergebnis.

    Kein Modellaufruf, reine Leseabfrage -- deshalb darf ein Knopf-Handler
    sie direkt aufrufen."""
    verdichtung = repo.verdichtung_zu_aufnahme(conn, kopf_id)
    if verdichtung is None:
        return False
    kopf = repo.hole_aufnahme(conn, kopf_id)
    name = anzeigename(conn, kopf, T._TEXT_DAS_INTERVIEW) if kopf else T._TEXT_DAS_INTERVIEW
    _sende_und_merke(
        conn, tg, e, verdichtung["chat_id"],
        _verdichtungstext(conn, name, verdichtung["id"]),
    )
    return True


def _interview_abschliessen(conn, tg, klm, e, row, erzwungen: bool = False,
                            nachgeholt: bool = False) -> None:
    """Verdichtet ein Interview (oder einen Textimport) und meldet das
    Ergebnis in den Chat.

    ``erzwungen=True`` (aus ``/auswerten``) uebergeht die Mindestlaenge aus
    N2: die Gruppe hat ausdruecklich darum gebeten, und ihr Urteil ueber ihr
    eigenes Material steht ueber einer Wortzahl.

    Schlaegt die Verdichtung fehl, bleibt status='transkribiert' stehen und
    der Versuchszaehler steigt -- derselbe Zaehler und dieselbe
    MAX_VERSUCHE-Grenze wie bei einem Transkriptionsfehlschlag (kritische
    Nachbesserung: eine misslingende Verdichtung ist ein bezahlter
    Sprachmodell-Aufruf und darf nicht unbegrenzt oft alle
    NACHHOL_INTERVALL_S Sekunden wiederholt werden). Ab MAX_VERSUCHE wird
    endgueltig aufgegeben, das Transkript bleibt aber erhalten -- nur die
    Zusammenfassung fehlt.

    **Der Tagesdeckel (Karte Padua S) ist kein Fehlschlag** und zaehlt
    deshalb keinen Versuch: der Nachhol-Arbeiter laeuft alle 60 s, und
    MAX_VERSUCHE waeren in fuenf Minuten verbraucht -- ein Interview vom
    Abend stuende am Morgen auf 'fehlgeschlagen'. Es bleibt
    'transkribiert', und ``nachholen()`` verdichtet es nach Mitternacht.
    Gemeldet wird nur im Live-Pfad (``nachgeholt`` falsch), SPEC § 10.3."""
    from interview_theater import kosten

    aufnahme_id = row["id"]
    chat_id = row["chat_id"]
    if not erzwungen and _zu_kurz_gemeldet(conn, tg, e, row):
        return
    try:
        verdichtung_id = verdichter.verdichte(klm, conn, e, aufnahme_id)
    except kosten.KostendeckelErreicht:
        if not nachgeholt:
            kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
        return
    except Exception as fehler:
        log.exception("Verdichtung fehlgeschlagen, aufnahme_id=%s", aufnahme_id)
        versuche = repo.zaehle_versuch_hoch(conn, aufnahme_id)
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "verdichtung_fehlgeschlagen",
            f"Aufnahme {aufnahme_id} (Versuch {versuche}/{MAX_VERSUCHE}): "
            f"{type(fehler).__name__}",
        )
        if versuche >= MAX_VERSUCHE:
            repo.setze_status(conn, aufnahme_id, "fehlgeschlagen", fehlertext=str(fehler))
            _sende_verdichtung_gescheitert(conn, tg, chat_id, row)
        return
    repo.setze_status(conn, aufnahme_id, "fertig")
    # Der Auto-Uebergang nach dem Web-Knopf "Interviews fertig" (02.10.2026):
    # lief er auf einem noch offenen Interview auf, steht der Wunsch hier
    # (``arbeitsstand.interviews_fertig_wunsch_seit``) -- jede weitere
    # erfolgreiche Verdichtung prueft, ob jetzt die letzte war. Laeuft fuer
    # BEIDE Pfade (erzwungen und normal): ein erzwungenes ``/auswerten`` auf
    # dem letzten offenen kurzen Interview ist genau der Fall, der ebenfalls
    # weiterschalten soll.
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is not None and stand["interviews_fertig_wunsch_seit"] and not unausgewertete_interviews(conn, chat_id):
        from interview_theater.knoepfe.stationen import schliesse_interviews_ab

        if schliesse_interviews_ab(conn, tg, klm, e, chat_id):
            repo.setze_arbeitsstand(conn, chat_id, "interviews_fertig_wunsch_seit", None)
    # Seit 05.09.2026 (Birk, Testlauf vor dem Workshop) geht die Verdichtung
    # NICHT mehr von selbst in den Chat: nach einem Interview kommt keine
    # Rueckmeldung und keine Rueckfrage, weil das eine eigene Phase ist --
    # erst werden alle Interviews gemacht, eins nach dem anderen, danach
    # werden die Verdichtungen ausgespielt. Verdichtet wird trotzdem sofort:
    # das Material ist gesichert, steht auf der Gruppenseite und ist ueber
    # ``/auswerten`` jederzeit abrufbar. ``erzwungen`` kommt genau von dort --
    # dann WILL die Gruppe den Text sehen und bekommt ihn.
    name = anzeigename(conn, row, T._TEXT_DAS_INTERVIEW)
    if not erzwungen:
        # Seit dem 06.09.2026 (Birk 09:55) sagt der Bot, WAS herausgekommen
        # ist -- eine Zeile mit der Zaehlung, nicht die Verdichtung selbst.
        # Der Volltext bleibt hinter "Zusammenfassung zeigen" (Entscheidung
        # vom 05.09.2026: kein ungefragter Verdichtungstext im Chat), das
        # Transkript hinter "Transkript zeigen" -- zum Gegenpruefen.
        #
        # Seit dem 02.10.2026 (Aufgabe 4) bekommt der Web-Kanal eine eigene
        # Zeile (Uhrzeit, Dauer, bis zu drei Themen) statt der
        # Telegram-Zaehlung -- Telegram bleibt bitgleich.
        if ist_web_gruppe(conn, chat_id):
            text = _text_interview_gespeichert_web(conn, row, verdichtung_id, e)
        else:
            themen = repo.themen_zu(conn, verdichtung_id)
            text = T._TEXT_AUSGEWERTET.format(
                name=name,
                themen=len(themen),
                zitate=sum(
                    1 for t in themen
                    if t["zitat_geprueft"] == 1 and t["beleg_zitat"]
                ),
            )
        _sende_nach_interview(
            conn, tg, e, chat_id, text, aufnahme_id,
            system=fliesstext_aktiv(conn, chat_id),
        )
        return
    # Die Verdichtung geht als normale Bot-Nachricht in den Chat: anders als
    # das Transkript-Echo GEHOERT sie ins Gespraechsfenster -- sie ist eine
    # Aussage des Bots ueber die Arbeit, und ein Widerspruch der Gruppe
    # ("nee, darum ging es nicht") soll im naechsten Zug seinen Bezug haben.
    # Ganz unten hing bis 05.09.2026 die Phasenfrage ("Kommen noch Interviews,
    # oder gehen wir ans Kernthema?"). Sie ist raus: nach einem Interview
    # stellt der Bot keine Rueckfragen, die Gruppe macht ein Interview nach
    # dem anderen und entscheidet selbst, wann sie weitergeht (Birk 05.09.).
    text = _verdichtungstext(conn, name, verdichtung_id)
    _sende_und_merke(conn, tg, e, chat_id, text)


def beende_interview(conn, chat_id: int) -> int | None:
    """Schaltet den Interviewmodus aus und stempelt das laufende Interview als
    beendet (§ 10.6). Liefert dessen ``aufnahme_id``, oder None, wenn gar
    keines lief.

    Beruehrt weder Telegram noch ein Sprachmodell -- das ist die Bedingung
    dafuer, dass sowohl ``/fertig`` (befehle.py) als auch der Absichtserkenner
    (``interview_beenden``, der nur in die Datenbank schreiben darf) dieselbe
    Funktion benutzen koennen. Das Zusammenfuegen und Verdichten schliesst
    ``schliesse_ab`` an, die Aufrufer stossen es ueber ``starte_abschluss``
    an."""
    repo.setze_interviewmodus(conn, chat_id, None)
    kopf = repo.laufendes_interview(conn, chat_id)
    if kopf is None:
        return None
    repo.setze_interview_beendet(conn, kopf["id"])
    return kopf["id"]


def schliesse_ab(conn, tg, klm, e, kopf_id: int) -> bool:
    """Fuegt die Teile eines beendeten Interviews zu einem Transkript zusammen
    und verdichtet es -- **einmal**, ueber das ganze Interview (§ 10.6).

    Liefert False, solange noch ein Teil in Arbeit ist: dann passiert nichts,
    und der Nachhol-Arbeiter kommt in NACHHOL_INTERVALL_S Sekunden wieder.
    Lieber eine Minute spaeter verdichten als ohne den Teil, an dem Whisper
    gerade haengt.

    Ohne eine einzige Sprachnachricht gibt es eine Zeile und **keinen
    Modellaufruf**: eine Verdichtung von nichts hat im Probelauf zwei leere
    Zusammenfassungen erzeugt ("Material extrem kurz").

    Laeuft je Kopf hoechstens einmal gleichzeitig (``_abschluss_sperre``):
    zwei Wege -- der Abschluss-Thread von "fertig" und die Nachpruefung des
    letzten Teils in ``_teil_abschliessen`` -- koennen sonst beide hinter der
    Statuspruefung stehen und doppelt verdichten. Die Sperre **wartet** statt
    abzuweisen: wer als zweiter kommt, liest danach frisch und findet den Kopf
    entweder abgeschlossen (nichts zu tun) oder -- hat der erste wegen eines
    offenen Teils aufgegeben -- ohne offenen Teil und schliesst selbst ab.
    Ein Abweisen verloere genau diesen zweiten Fall an den Nachhol-Arbeiter."""
    with _abschluss_sperre(kopf_id):
        return _schliesse_ab(conn, tg, klm, e, kopf_id)


#: Eine Sperre je Interview-Kopf fuer ``schliesse_ab``. Nicht
#: ``_in_bearbeitung``: das weist ab, statt zu warten, und ``schliesse_ab``
#: ruft darunter selbst ``verarbeite`` fuer denselben Kopf. Ueber
#: Prozessgrenzen braucht es keine: ein Interview gehoert einer Gruppe, und
#: eine Gruppe hat genau einen Bot-Prozess (Falle 7). Die Eintraege bleiben
#: stehen -- einer je Interview, eine Handvoll je Workshop. ``RLock``, damit
#: ein Aufruf aus demselben Thread heraus nicht an sich selbst haengt.
_abschluss_sperren: dict[int, threading.RLock] = {}
_abschluss_sperren_lock = threading.Lock()


def _abschluss_sperre(kopf_id: int):
    with _abschluss_sperren_lock:
        return _abschluss_sperren.setdefault(kopf_id, threading.RLock())


def _schliesse_ab(conn, tg, klm, e, kopf_id: int) -> bool:
    kopf = repo.hole_aufnahme(conn, kopf_id)
    if kopf is None or kopf["status"] != "laeuft":
        return True  # schon abgeschlossen (oder nie ein Kopf) -- nichts zu tun
    if repo.hat_offene_teile(conn, kopf_id):
        return False

    name = anzeigename(conn, kopf, T._TEXT_DAS_INTERVIEW)
    transkript = repo.zusammengefuegtes_transkript(conn, kopf_id)
    if not transkript.strip():
        if not repo.hole_teile(conn, kopf_id):
            # Kein einziger Teil: das Interview ist nie entstanden, es war
            # ein Fehlgriff auf dem Knopf (Live-Fall Gruppe 1, 14:21). Weich
            # entfernen statt als leere Huelle stehen lassen -- sonst zaehlt
            # es als unausgewertetes Interview und sperrt Phase 4.
            _verwirf_leeres_interview(conn, tg, e, kopf["chat_id"], kopf_id)
            return True
        repo.setze_status(conn, kopf_id, "fertig")
        _sende_nach_interview(
            conn, tg, e, kopf["chat_id"], T._TEXT_OHNE_AUFNAHME.format(name=name),
            None,
        )
        return True

    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "transkribiert")
    if klm is None:
        # Kein Sprachmodell zur Hand (ein Aufrufer ohne klm): der Kopf steht
        # jetzt auf 'transkribiert' und wird vom Nachhol-Arbeiter verdichtet.
        return True
    verarbeite(conn, tg, klm, e, None, kopf_id)
    return True


def _verwirf_leeres_interview(conn, tg, e, chat_id: int, kopf_id: int) -> None:
    """Entfernt ein Interview ohne einen einzigen Teil weich und meldet es
    in einer Zeile mit dem Knopf "Aufnahme starten" darunter (05.09.2026).

    Weich (``repo.entferne_aufnahme``) und nicht hart: die Audiodateien
    bleiben liegen, der vollstaendige Loeschweg ist weiterhin
    ``scripts/loeschen.py``. Hier gibt es ohnehin nichts zu loeschen -- es
    ist nie eine Sprachnachricht angekommen.

    Die **Interviewnummern verschieben sich dadurch nicht**:
    ``repo.zaehle_interviews`` zaehlt entfernte Koepfe ausdruecklich mit
    (siehe dort), das naechste Interview heisst also "Interview 3", auch
    wenn 1 und 2 verworfen wurden. Zwei Aufnahmen mit demselben Namen waeren
    im Journal nicht mehr auseinanderzuhalten."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    # Erst den Status, dann das Entfernen: ein Kopf, der auf 'laeuft' stehen
    # bliebe, waere fuer den Nachhol-Arbeiter und ``schliesse_ab`` weiter ein
    # offenes Interview -- auch als entfernte Zeile.
    repo.setze_status(conn, kopf_id, "fertig")
    try:
        repo.entferne_aufnahme(conn, chat_id, kopf_id)
    except Exception:
        log.exception("Leeres Interview entfernen fehlgeschlagen, id=%s", kopf_id)
    try:
        message_id = knoepfe.biete_aufnahme(conn, tg, chat_id, T._TEXT_LEER_VERWORFEN)
        repo.merke_bot_zeile(
            conn, chat_id, message_id, e, T._TEXT_LEER_VERWORFEN
        )
    except Exception:
        log.exception("Meldung zum leeren Interview fehlgeschlagen, chat_id=%s", chat_id)


def starte_abschluss(conn, tg, klm, e, kopf_id: int) -> threading.Thread:
    """Stoesst ``schliesse_ab`` in einem eigenen Thread an und kehrt sofort
    zurueck -- dasselbe Muster wie ``szene.starte``.

    Grund: ``/fertig`` laeuft in ``befehle.behandle``, und **kein Befehl ruft
    synchron ein Modell** (docs/agents/spec-abweichungen.md). Der Gespraechszug der Gruppe haelt sonst
    fuer die Dauer der Verdichtung die Sperre je chat_id. Die Gruppe bekommt
    sofort "Aufnahme beendet." und wenige Sekunden spaeter die Verdichtung.

    Liefert den Thread zurueck, damit Tests auf ihn warten koennen."""
    def _lauf() -> None:
        try:
            schliesse_ab(conn, tg, klm, e, kopf_id)
        except Exception:
            log.exception("Interviewabschluss fehlgeschlagen, aufnahme_id=%s", kopf_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    return thread


def interviews(conn, chat_id: int) -> list:
    """Die Interviews einer Gruppe (die Koepfe, in Entstehungsreihenfolge) --
    ohne Gespraechsbeitraege und ohne die einzelnen Teile."""
    return [a for a in repo.transkripte(conn, chat_id) if a["klasse"] == "lang"]


def unausgewertete_interviews(conn, chat_id: int) -> list:
    """Beendete Interviews mit Material, aber ohne Verdichtung (05.09.2026).

    Die Grundlage der **Phase-4-Sperre**: erst wenn diese Liste leer ist,
    gibt es \"Weiter zu Phase 4\" -- ins Kernthema geht es mit dem ganzen
    Material, nicht mit dem halben (Live-Fall 05.09.: die Gruppe schaltete
    weiter, waehrend zwei Interviews unausgewertet danebenlagen, und der
    Bot schlug Kernthemen aus einem Drittel des Materials vor).

    Drei Bedingungen, jede einzeln noetig:

    * **beendet** (``beendet_am`` gesetzt oder Status ``fertig``/
      ``transkribiert``) -- ein laufendes Interview ist keine offene
      Auswertung, sondern eine laufende Aufnahme.
    * **hat ein Transkript** -- ein Interview ohne eine einzige
      Sprachnachricht (\"hatte keine Aufnahme\") kann nie verdichtet werden
      und wuerde die Gruppe sonst dauerhaft aussperren.
    * **keine Verdichtung** (``repo.verdichtung_zu_aufnahme``).

    Reine Leseabfrage, kein Modellaufruf -- sie laeuft in jedem
    Gespraechszug (``phasen.voraussetzungen``)."""
    offen = []
    for kopf in interviews(conn, chat_id):
        beendet = kopf["beendet_am"] or kopf["status"] in ("fertig", "transkribiert")
        if not beendet:
            continue
        if not (kopf["transkript"] or "").strip():
            if not repo.zusammengefuegtes_transkript(conn, kopf["id"]).strip():
                continue
        # Ein zu-kurz uebersprungenes Interview (``_zu_kurz_gemeldet``, N2)
        # wird NIE automatisch verdichtet -- und darf die Phase-4-Sperre
        # deshalb nicht auf unbestimmte Zeit offenhalten (Padua Phasen TEIL
        # 2, Befund 4a). ``/auswerten`` (das die Verdichtung erzwingt) nimmt
        # es trotzdem ueber den BESTEHENDEN ``verdichtung_zu_aufnahme is
        # None``-Zweig unten aus der Liste, sobald die Verdichtung existiert
        # -- das Flag muss dafuer nicht zurueckgesetzt werden.
        if kopf["zu_kurz_uebersprungen"]:
            continue
        if repo.verdichtung_zu_aufnahme(conn, kopf["id"]) is None:
            offen.append(kopf)
    return offen


def migriere_zu_kurz_altdaten(conn, chat_id: int | None = None) -> int:
    """Einmaliger Nachtrag fuer Gruppen, die den Fehler aus Befund 4a schon
    LIVE erlebt haben (Padua Phasen TEIL 2, Task 5) -- z.B. die echte
    Padua-Gruppe aus dem Kartentext: vor diesem Fix wurden zu kurze
    Interviews mit ``status='fertig'`` abgeschlossen, OHNE
    ``zu_kurz_uebersprungen`` zu setzen, und blieben deshalb in
    ``unausgewertete_interviews()`` stehen -- die Phase-4-Sperre ging nie
    wieder auf.

    Findet alle Interview-Koepfe (``klasse='lang'``) mit ``status='fertig'``,
    ``zu_kurz_uebersprungen = 0``, OHNE Verdichtung und mit einer
    Transkript-Wortzahl unter ``MINDEST_WOERTER``, optional eingeschraenkt
    auf eine ``chat_id``, und setzt das Flag nach. Liefert die Anzahl der
    migrierten Zeilen.

    **Kein automatischer Aufruf beim Start** -- das waere eine versteckte
    Nebenwirkung auf jede Datenbank. Wird explizit aus einem Skript oder
    einem Test heraus gerufen (hier: dem Replay-Test gegen die Padua-Kopie)."""
    if chat_id is not None:
        chat_ids = [chat_id]
    else:
        chat_ids = [
            z["chat_id"]
            for z in conn.execute("SELECT DISTINCT chat_id FROM aufnahme").fetchall()
        ]
    migriert = 0
    for cid in chat_ids:
        for kopf in interviews(conn, cid):
            if kopf["status"] != "fertig" or kopf["zu_kurz_uebersprungen"]:
                continue
            if repo.verdichtung_zu_aufnahme(conn, kopf["id"]) is not None:
                continue
            text = (kopf["transkript"] or "").strip()
            if not text:
                text = repo.zusammengefuegtes_transkript(conn, kopf["id"]).strip()
            if not text or len(text.split()) >= MINDEST_WOERTER:
                continue
            repo.setze_zu_kurz_uebersprungen(conn, kopf["id"])
            migriert += 1
    return migriert


def finde_interview(conn, chat_id: int, bezeichnung: str = ""):
    """Sucht das Interview, das ``bezeichnung`` meint -- eine Nummer ("3",
    "Interview 3"), ein Namensteil ("Meryem") oder nichts (dann das letzte).

    Liefert die ``aufnahme``-Zeile oder None. Grundlage von ``/auswerten``
    (N2); grosszuegig wie ``repo.transkripte``, weil die Gruppe Namen nicht
    immer gleich tippt -- eine Nummer wird aber genau genommen, damit
    "/auswerten 1" nicht Interview 11 trifft."""
    vorhandene = interviews(conn, chat_id)
    if not vorhandene:
        return None
    bezeichnung = (bezeichnung or "").strip()
    if not bezeichnung:
        return vorhandene[-1]
    treffer = re.search(r"\d{1,4}", bezeichnung)
    if treffer:
        gesucht = f"Interview {int(treffer.group(0))}"
        if sprache.pseudonyme():
            # E8: gezeigt (und im Prompt genannt) wird "Interview N" nach
            # Position -- genau das meint die Gruppe und der Erkenner, nicht
            # ein gespeicherter Name, der nach einem Entfernen verrutscht ist.
            return next((a for a in vorhandene
                         if anzeigename(conn, a, "") == gesucht), None)
        return next((a for a in vorhandene if (a["name"] or "") == gesucht), None)
    gesucht = bezeichnung.lower()
    return next((a for a in vorhandene if gesucht in (a["name"] or "").lower()), None)


def _auswerten(conn, tg, klm, e, kopf_id: int) -> None:
    """Verdichtet ein Interview auf ausdrueckliche Bitte der Gruppe
    (``/auswerten``, N2) -- auch wenn es unter MINDEST_WOERTER liegt.

    Holt das zusammengefuegte Transkript nach, falls am Kopf noch keines
    steht: bei einem Interview, das nie ueber ``schliesse_ab`` gelaufen ist,
    gibt es sonst nichts zu verdichten."""
    row = repo.hole_aufnahme(conn, kopf_id)
    if row is None:
        return
    if not (row["transkript"] or "").strip():
        transkript = repo.zusammengefuegtes_transkript(conn, kopf_id)
        if not transkript.strip():
            _sende_und_merke(
                conn, tg, e, row["chat_id"],
                T._TEXT_OHNE_AUFNAHME.format(name=anzeigename(conn, row, T._TEXT_DAS_INTERVIEW)),
            )
            return
        repo.setze_transkript(conn, kopf_id, transkript)
        row = repo.hole_aufnahme(conn, kopf_id)
    _interview_abschliessen(conn, tg, klm, e, row, erzwungen=True)


def starte_auswertung(conn, tg, klm, e, kopf_id: int) -> threading.Thread:
    """Stoesst ``_auswerten`` in einem eigenen Thread an -- dasselbe Muster
    wie ``starte_abschluss``, aus demselben Grund: ``/auswerten`` ist ein
    Befehl, und **kein Befehl ruft synchron ein Modell** (docs/agents/spec-abweichungen.md)."""
    def _lauf() -> None:
        try:
            _auswerten(conn, tg, klm, e, kopf_id)
        except Exception:
            log.exception("Auswertung fehlgeschlagen, aufnahme_id=%s", kopf_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    return thread


def melde_ausfall(conn, tg, e, chat_id) -> None:
    """Meldet einen Whisper-Ausfall genau einmal pro Gruppe (§ 10.4).

    Nachbesserung 'Wichtig 1': **erst atomar setzen, dann senden.** Der
    ThreadPoolExecutor bearbeitet mehrere Sprachnachrichten gleichzeitig --
    genau im Auslösefall (Whisper weg) koennten sonst zwei Threads beide noch
    ``whisper_stumm_seit IS NULL`` lesen und beide senden. Das atomare
    ``UPDATE ... WHERE whisper_stumm_seit IS NULL`` (repo.
    setze_whisper_stumm_seit_falls_leer) garantiert, dass nur der Thread, der
    das Feld tatsaechlich gesetzt hat (``rowcount == 1``), ueberhaupt sendet."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None:
        return
    if not repo.setze_whisper_stumm_seit_falls_leer(conn, chat_id, repo._jetzt()):
        return  # ein anderer Thread war schneller, oder das Feld war schon gesetzt
    try:
        tg.sende(chat_id, T._TEXT_AUSFALL)
    except Exception:
        log.exception("Ausfall-Hinweis fehlgeschlagen, chat_id=%s", chat_id)


def melde_rueckkehr(conn, tg, e, chat_id) -> None:
    """Meldet die Rueckkehr, wenn zuvor ein Ausfall gemeldet wurde (§ 10.4).
    Spiegelbildlich zu melde_ausfall: erst atomar leeren, dann senden."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None:
        return
    if not repo.leere_whisper_stumm_seit_falls_gesetzt(conn, chat_id):
        return
    try:
        tg.sende(chat_id, T._TEXT_RUECKKEHR)
    except Exception:
        log.exception("Rueckkehr-Hinweis fehlgeschlagen, chat_id=%s", chat_id)


def nachholen(conn, tg, klm, e, klient, *, zug=_kein_zug) -> None:
    """Greift beim Start und danach alle NACHHOL_INTERVALL_S Sekunden alles
    auf, was nicht in einem Endzustand steht (§ 10.3) -- derselbe Weg, der
    auch die Nacht zwischen zwei Workshoptagen ueberbrueckt (§ 9.1 Schritt 3).

    Nur die Aufnahmen der Gruppen, die dieser Bot-Prozess bedient
    (``gruppe.bot_name == e.bot_name``, siehe
    ``repo.offene_aufnahmen_fuer_bot``): es laeuft ein Prozess je Gruppe auf
    derselben SQLite-Datei, und ohne diese Einschraenkung wuerden zwei
    Prozesse dieselbe Aufnahme gleichzeitig zu Whisper hochladen.

    ``zug`` (Aufgabe 10, ``ablauf.bearbeite``) wird unveraendert an
    ``verarbeite()`` durchgereicht -- auch hier, mit ``nachgeholt=True``.
    Das ist sicher: ``_kurz_abschliessen`` ruft ``zug`` bei ``nachgeholt=True``
    strukturell nie auf, unabhaengig davon, welche Funktion hereingereicht
    wurde (SPEC § 10.3: 'Nachgeholtes loest nie eine Antwort aus').

    Zwei Durchgaenge, in dieser Reihenfolge (§ 10.6):

    1. Alles, woran noch Arbeit offen ist -- darunter Interview-Teile, deren
       Transkription live gescheitert ist (ihr Echo geht dann eben verspaetet
       in den Chat: nachgeholt heisst nicht stumm, das Transkript ist der
       einzige Weg, auf dem die Gruppe es je zu sehen bekommt) und Koepfe, bei
       denen nur die Verdichtung fehlschlug.
    2. Interviews, die die Gruppe fuer beendet erklaert hat, deren Teile aber
       noch nicht alle durch waren. Erst jetzt, nach Durchgang 1, ist die
       Antwort auf 'sind alle Teile durch?' die aktuelle."""
    for row in repo.offene_aufnahmen_fuer_bot(conn, e.bot_name):
        try:
            verarbeite(conn, tg, klm, e, klient, row["id"], zug=zug, nachgeholt=True)
        except Exception:
            log.exception("Nachholen einer Aufnahme fehlgeschlagen, id=%s", row["id"])

    for kopf in repo.beendete_offene_interviews(conn, e.bot_name):
        try:
            schliesse_ab(conn, tg, klm, e, kopf["id"])
        except Exception:
            log.exception("Nachholen eines Interviewabschlusses fehlgeschlagen, id=%s", kopf["id"])


def importiere_text(conn, e, chat_id: int, message_id: int, text: str, name: str | None = None) -> int:
    """Legt Text als gleichwertiges Material an (§ 10.5): deckt sowohl den
    Rueckfallweg ab (Whisper streikt) als auch das Einspeisen vorhandenen
    Recherchematerials, das nie gesprochen wurde. Legt die Aufnahme nur bis
    'transkribiert' an -- die eigentliche Verdichtung geschieht ausschliesslich
    in ``verarbeite()`` (Aufruf durch den Aufrufer selbst oder durch den
    Nachhol-Arbeiter, falls der erste Anlauf nicht sofort verdichtet).

    Ein Textimport ist ein Interview mit einem einzigen Teil, und dieser eine
    Teil ist der Text selbst: der Kopf traegt ihn direkt (§ 10.6, dieselbe
    Form wie bei allen Aufnahmen aus der Zeit vor dem Nachtrag, siehe
    ``repo.zusammengefuegtes_transkript``). Eine eigene Teil-Zeile brauchte es
    nur, um denselben Text ein zweites Mal zu speichern -- und sie wuerde ihn
    obendrein als Echo in den Chat stellen, obwohl niemand ihn gerade
    eingesprochen hat.

    Wichtig (Nachbesserung 'Kritisch 2'): ``verdichter.verdichte()`` darf nach
    ``importiere_text()`` NIE direkt aufgerufen werden, ohne anschliessend
    auch den Status auf 'fertig' zu setzen -- sonst bleibt die Aufnahme bei
    'transkribiert' stehen, und der periodische Nachhol-Arbeiter
    (``nachholen()``) verdichtet sie beim naechsten Durchlauf ein zweites Mal
    (zwei ``verdichtung``-Zeilen, zwei bezahlte Sprachmodell-Aufrufe). Der
    einzig sichere Weg zur Verdichtung ist ``verarbeite(conn, tg, klm, e,
    klient, aufnahme_id)`` -- die kuemmert sich sowohl um die Verdichtung als
    auch um den Statuswechsel und die MAX_VERSUCHE-Grenze."""
    aufnahme_id = repo.lege_aufnahme_an(conn, chat_id, message_id, "lang", "text")
    repo.setze_transkript(conn, aufnahme_id, text)
    repo.setze_status(conn, aufnahme_id, "transkribiert")
    if name:
        repo.setze_aufnahme_name(conn, aufnahme_id, name)
    return aufnahme_id


T = sprache.Texte(__name__)

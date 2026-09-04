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
from datetime import datetime, timezone
from pathlib import Path

from interview_theater import phasen, repo, stt, verdichter

log = logging.getLogger(__name__)

# Alle Schwellwerte an genau dieser Stelle (Auftragshinweis 5), Werte aus der
# Messung vom 03.09.2026 (76 Laeufe, Median 2,9 s, einziger Ausreisser 8,88 s,
# kein Lauf ueber 10 s). Nirgends im Code als Zahl wiederholt.
TIPPANZEIGE_AB_S = 5
MELDUNG_AB_S = 12
BUDGET_KURZ_S = 45
BUDGET_LANG_S = 90
NACHHOL_INTERVALL_S = 60
MAX_VERSUCHE = 5

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

#: Wortlaut aus SPEC § 10.4/§ 11.1, ohne Umlaute wie der uebrige Quelltext.
_TEXT_ZWISCHENMELDUNG = "Ich hoer noch zu, einen Moment."
_TEXT_AUSFALL = (
    "Ich kann gerade nicht hoeren. Schreibt mir solange, ich sammle die "
    "Aufnahmen und hole sie nach."
)
_TEXT_RUECKKEHR = "Ich kann wieder hoeren."
_TEXT_MATERIAL_HINWEIS = (
    "Das klingt nach Material - wenn ihr es als Interview festhalten wollt, "
    "sagt mir Bescheid."
)

#: Das Transkript-Echo eines Teils (§ 10.6): woertlich, ohne Kommentar, ohne
#: Zusammenfassung. Der Kopf sagt, wozu es gehoert -- das ist der ganze
#: Unterschied zu "Ich hoere durch", das nichts zu kontrollieren gab.
_TEXT_TEIL_ECHO = "{name}, Teil {nummer}:\n{transkript}"

#: Die inhaltliche Rueckmeldung, wenn ein Interview durch ist. Sie ist der
#: eigentliche Ertrag dieses Nachtrags -- bisher endete ein Interview ohne ein
#: Wort darueber, was darin steckt.
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
#: mit Zahlen, damit die Gruppe erkennt, welche Aufnahme gemeint ist, und mit
#: dem ausdruecklichen Angebot, es trotzdem zu tun.
_TEXT_ZU_KURZ = (
    "{name} ist sehr kurz ({dauer} s, {woerter} Woerter). Ich werte es nicht "
    "aus - sagt Bescheid, wenn ich es trotzdem soll."
)

#: "fertig" ohne eine einzige Sprachnachricht: eine Zeile, kein Modellaufruf.
_TEXT_OHNE_AUFNAHME = "{name} hatte keine Aufnahme - ich habe nichts verdichtet."


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


def stelle_interview_sicher(conn, chat_id: int) -> int:
    """Liefert den laufenden Interview-Kopf dieser Gruppe und legt ihn beim
    ersten Bedarf an (§ 10.6). Liefert dessen ``aufnahme_id``.

    Aufgerufen beim Einschalten des Modus (``/interview``, Erkenner-art
    ``interview_starten``) -- und zusaetzlich in ``empfange()``, falls dort
    trotz aktivem Modus keiner existiert: der Modus steht in der Datenbank und
    kann aus einer aelteren Fassung, einem Fehlschlag beim Anlegen oder einem
    Handeingriff stammen. Eine Sprachnachricht ohne Kopf waere sonst
    heimatloses Material."""
    kopf = repo.laufendes_interview(conn, chat_id)
    if kopf is not None:
        return kopf["id"]
    return repo.lege_interview_an(conn, chat_id)


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
    Gruppe, es nochmal zu schicken, damit nichts spurlos verschwindet."""
    chat_id = n["chat_id"]
    message_id = n["message_id"]
    klasse = klasse_fuer(conn, chat_id)
    teil_von = stelle_interview_sicher(conn, chat_id) if klasse == "teil" else None

    repo.merke_nachricht(
        conn, chat_id, message_id, n.get("absender"), 0, "sprache", None,
        n.get("gesendet_am") or repo._jetzt(), 1,
    )

    ziel = Path(e.audio_verz) / str(chat_id) / f"{message_id}.ogg"
    fehler = _lade_mit_wiederholung(tg, n["file_id"], ziel)
    if fehler is not None:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "download_fehlgeschlagen",
            f"Sprachnachricht message_id={message_id}: {type(fehler).__name__}",
        )
        try:
            tg.sende(
                chat_id,
                "Die Aufnahme ist bei mir nicht angekommen - schickt sie bitte nochmal.",
            )
        except Exception:
            log.exception("Download-Fehlermeldung fehlgeschlagen, chat_id=%s", chat_id)
        return None

    return repo.lege_aufnahme_an(
        conn, chat_id, message_id, klasse, "sprache",
        audio_pfad=str(ziel), dauer=n.get("dauer"), teil_von=teil_von,
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
        text = _transkribiere_mit_meldung(conn, tg, e, klient, row)
        if text is None:
            return  # Fehler wurde schon gemeldet/aufgezeichnet
        melde_rueckkehr(conn, tg, e, row["chat_id"])
        repo.setze_transkript(conn, aufnahme_id, text)
        repo.setze_status(conn, aufnahme_id, "transkribiert")
        row = repo.hole_aufnahme(conn, aufnahme_id)

    # status ist jetzt 'transkribiert' -- frisch oder schon vorher (Textimport,
    # oder ein frueherer Anlauf, bei dem nur die Verdichtung scheiterte).
    if row["klasse"] == "teil":
        _teil_abschliessen(conn, tg, klm, e, row)
    elif row["klasse"] == "kurz":
        _kurz_abschliessen(conn, tg, klm, e, row, zug, nachgeholt)
    else:
        _interview_abschliessen(conn, tg, klm, e, row)


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
            tg.sende(chat_id, _TEXT_ZWISCHENMELDUNG)
        except Exception:
            log.exception("Zwischenmeldung fehlgeschlagen, chat_id=%s", chat_id)

    timer_tipp = threading.Timer(TIPPANZEIGE_AB_S, _tippen)
    timer_tipp.daemon = True
    timer_tipp.start()

    timer_meldung = threading.Timer(MELDUNG_AB_S, _zwischenmeldung)
    timer_meldung.daemon = True
    timer_meldung.start()

    try:
        return stt.transkribiere(e, klient, pfad, budget)
    except Exception as fehler:
        _melde_transkriptionsfehler(conn, tg, e, row, fehler)
        return None
    finally:
        timer_tipp.cancel()
        timer_meldung.cancel()


def _ist_ersatzname(name: str | None) -> bool:
    """Erkennt den automatisch vergebenen Namen 'Interview n' (repo.lege_
    aufnahme_an), im Unterschied zu einem von der Gruppe echt vergebenen
    Namen."""
    return bool(name) and re.fullmatch(r"Interview \d+", name) is not None


def _aufnahme_beschreibung(conn, row, gross: bool) -> str:
    """Beschreibt eine Aufnahme in einer Nutzernachricht. Ein automatisch
    vergebener Ersatzname wie 'Interview 1' wirkt in einer Chatnachricht
    unfreiwillig komisch ('Die Aufnahme von Interview 1...') -- ohne einen
    von der Gruppe vergebenen echten Namen wird stattdessen die Klasse
    genannt.

    Bei einem Teil ist das anders: 'Interview 1, Teil 3' ist keine Verlegenheit,
    sondern die einzige Angabe, mit der die Gruppe weiss, WELCHE der fuenf
    Sprachnachrichten sie noch einmal schicken soll."""
    artikel = "Die" if gross else "die"
    if row["teil_von"]:
        kopf = repo.hole_aufnahme(conn, row["teil_von"])
        name = (kopf["name"] if kopf else None) or "Interview"
        return f"{artikel} Aufnahme von {name}, Teil {repo.teil_nummer(conn, row['id'])}"
    name = row["name"]
    if name and not _ist_ersatzname(name):
        return f"{artikel} Aufnahme von {name}"
    art = "lange Aufnahme" if row["klasse"] == "lang" else "kurze Aufnahme"
    return f"{artikel} letzte {art}"


def _sende_bitte_nochmal(conn, tg, chat_id, row) -> None:
    text = (
        f"{_aufnahme_beschreibung(conn, row, gross=True)} konnte ich nicht "
        "verstehen - schickt sie bitte nochmal."
    )
    try:
        tg.sende(chat_id, text)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _sende_verdichtung_gescheitert(conn, tg, chat_id, row) -> None:
    text = (
        f"Ich konnte {_aufnahme_beschreibung(conn, row, gross=False)} nicht auswerten. "
        "Das Transkript bleibt gespeichert, nur die Zusammenfassung fehlt."
    )
    try:
        tg.sende(chat_id, text)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


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
    kommentarlos als 'typ=sprache, text=NULL' im Verlauf haengen bleibt."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]

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
    else:
        # Status bleibt (wieder) 'empfangen': der Nachhol-Arbeiter greift die
        # Aufnahme beim naechsten Anlauf erneut auf, sobald Whisper zurueck ist.
        repo.setze_status(conn, aufnahme_id, "empfangen", fehlertext=str(fehler))


def _kurz_abschliessen(conn, tg, klm, e, row, zug, nachgeholt) -> None:
    """Schreibt das Transkript als Aktualisierung der vorhandenen
    Nachrichtenzeile (§ 10.2) und loest den Gespraechszug nur aus, wenn die
    urspruengliche Nachricht noch jung genug ist (Auftragshinweis 1) UND es
    kein Nachhol-Anlauf war -- damit weder Nachtstau noch Nachgeholtes je eine
    Antwort ausloesen.

    Diese Funktion laeuft ausschliesslich fuer Klasse *kurz* -- und damit,
    seit Aufgabe 5, ausschliesslich fuer Sprachnachrichten, die bei
    interviewmodus AUS eintrafen (klasse_fuer). War die Nachricht dabei
    laenger als HINWEIS_AB_S, haengt sie dem Gespraechszug einen beilaeufigen
    Hinweis an -- keine Rueckfrage, kein eigener Zustand (§ 10.1)."""
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

    repo.aktualisiere_transkribierte_nachricht(
        conn, chat_id, message_id, text, 0 if jung else 1
    )
    repo.setze_status(conn, aufnahme_id, "fertig")

    if jung:
        dauer = row["dauer_sekunden"] or 0
        hinweis = _TEXT_MATERIAL_HINWEIS if dauer > HINWEIS_AB_S else None
        try:
            zug(conn, tg, klm, e, chat_id, hinweis=hinweis)
        except Exception:
            log.exception("Gespraechszug nach kurzer Aufnahme fehlgeschlagen, chat_id=%s", chat_id)


def _sende_und_merke(conn, tg, e, chat_id: int, text: str, typ: str = "text") -> None:
    """Schickt eine Bot-Nachricht und schreibt sie in ``nachricht`` mit --
    wie ``ablauf.antworte`` und ``erkenner.laufe`` es tun.

    ``typ='transkript'`` ist der Sonderfall dieses Moduls (§ 10.6): die Zeile
    wird gespeichert (Empfangen und In-den-Prompt-legen sind zwei
    Entscheidungen), taucht aber in keinem Fenster auf -- siehe
    ``repo.TYP_TRANSKRIPT``. Ein Fehlschlag beim Senden wird nur geloggt: der
    Inhalt selbst steht laengst in der Datenbank."""
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, typ,
            text, repo._jetzt(), 1 if typ == repo.TYP_TRANSKRIPT else 0,
        )
    except Exception:
        log.exception("Nachricht an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _teil_abschliessen(conn, tg, klm, e, row) -> None:
    """Stellt das Transkript eines Interview-Teils sofort und woertlich in den
    Chat (§ 10.6, Birk 04.09. abends: "Transkript Stueck fuer Stueck").

    Kein Kommentar, keine Zusammenfassung -- die Gruppe soll waehrend das
    Gegenueber noch im Raum sitzt kontrollieren koennen, ob angekommen ist,
    was gesagt wurde. Verdichtet wird erst bei "fertig", ueber das ganze
    Interview (``schliesse_ab``).

    **Ein Modellaufruf ist seit N1 doch dabei**, und zwar der billige: der
    Absichtserkenner (gemma, unter einer Sekunde nach dem Warmlauf) laeuft
    ueber das Transkript und sucht darin genau zwei Dinge --
    ``interview_beenden`` und ``interview_benennen`` (``erkenner.
    ARTEN_IN_AUFNAHME``). Die Gruppe sagt "so, das Interview ist fertig"
    naemlich meistens in die Aufnahme hinein, nicht in den Chat, und das
    Transkript-Echo steht in keinem Erkenner-Fenster. Der Teil selbst bleibt
    trotzdem Teil des Interviews: der Satz ist mit aufgenommen worden und
    steht harmlos am Ende des Transkripts.

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

    kopf = repo.hole_aufnahme(conn, row["teil_von"])
    text = _TEXT_TEIL_ECHO.format(
        name=(kopf["name"] if kopf else None) or "Interview",
        nummer=repo.teil_nummer(conn, row["id"]),
        transkript=row["transkript"],
    )
    _sende_und_merke(conn, tg, e, chat_id, text, typ=repo.TYP_TRANSKRIPT)
    repo.setze_status(conn, row["id"], "fertig")

    try:
        erkenner.wende_aus_aufnahme_an(klm, tg, conn, e, chat_id, aenderungen)
    except Exception:
        log.exception(
            "Anwenden einer Absicht aus einem Teil fehlgeschlagen, id=%s", row["id"]
        )


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
        _TEXT_VERDICHTUNG_KOPF.format(name=name),
        verdichtung["zusammenfassung"] if verdichtung else "",
        "",
    ]
    themen = repo.themen_zu(conn, verdichtung_id)
    if themen:
        zeilen.append(_TEXT_VERDICHTUNG_THEMEN)
        for thema in themen:
            if thema["zitat_geprueft"] == 1 and thema["beleg_zitat"]:
                zeilen.append(f'- {thema["thema"]}: "{thema["beleg_zitat"]}"')
            else:
                zeilen.append(f'- {thema["thema"]}')
    else:
        zeilen.append(_TEXT_OHNE_BELEG)
    zeilen.append("")
    zeilen.append(_TEXT_VERDICHTUNG_FRAGE)
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
    return _TEXT_PHASENFRAGE


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
    _sende_und_merke(
        conn, tg, e, row["chat_id"],
        _TEXT_ZU_KURZ.format(
            name=row["name"] or "Das Interview",
            dauer=repo.dauer_gesamt(conn, row["id"]) or 0,
            woerter=woerter,
        ),
    )
    return True


def _interview_abschliessen(conn, tg, klm, e, row, erzwungen: bool = False) -> None:
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
    Zusammenfassung fehlt."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]
    if not erzwungen and _zu_kurz_gemeldet(conn, tg, e, row):
        return
    try:
        verdichtung_id = verdichter.verdichte(klm, conn, e, aufnahme_id)
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
    # Die Verdichtung geht als normale Bot-Nachricht in den Chat: anders als
    # das Transkript-Echo GEHOERT sie ins Gespraechsfenster -- sie ist eine
    # Aussage des Bots ueber die Arbeit, und ein Widerspruch der Gruppe
    # ("nee, darum ging es nicht") soll im naechsten Zug seinen Bezug haben.
    # Ganz unten haengt, einmal je Workshop, die Phasenfrage (_phasenfrage).
    text = _verdichtungstext(conn, row["name"] or "Das Interview", verdichtung_id)
    frage = _phasenfrage(conn, chat_id)
    if frage:
        text = f"{text}\n{frage}"
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
    Zusammenfassungen erzeugt ("Material extrem kurz")."""
    kopf = repo.hole_aufnahme(conn, kopf_id)
    if kopf is None or kopf["status"] != "laeuft":
        return True  # schon abgeschlossen (oder nie ein Kopf) -- nichts zu tun
    if repo.hat_offene_teile(conn, kopf_id):
        return False

    name = kopf["name"] or "Das Interview"
    transkript = repo.zusammengefuegtes_transkript(conn, kopf_id)
    if not transkript.strip():
        repo.setze_status(conn, kopf_id, "fertig")
        _sende_und_merke(
            conn, tg, e, kopf["chat_id"], _TEXT_OHNE_AUFNAHME.format(name=name)
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


def starte_abschluss(conn, tg, klm, e, kopf_id: int) -> threading.Thread:
    """Stoesst ``schliesse_ab`` in einem eigenen Thread an und kehrt sofort
    zurueck -- dasselbe Muster wie ``szene.starte``.

    Grund: ``/fertig`` laeuft in ``befehle.behandle``, und **kein Befehl ruft
    synchron ein Modell** (AGENTS.md). Der Gespraechszug der Gruppe haelt sonst
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
                _TEXT_OHNE_AUFNAHME.format(name=row["name"] or "Das Interview"),
            )
            return
        repo.setze_transkript(conn, kopf_id, transkript)
        row = repo.hole_aufnahme(conn, kopf_id)
    _interview_abschliessen(conn, tg, klm, e, row, erzwungen=True)


def starte_auswertung(conn, tg, klm, e, kopf_id: int) -> threading.Thread:
    """Stoesst ``_auswerten`` in einem eigenen Thread an -- dasselbe Muster
    wie ``starte_abschluss``, aus demselben Grund: ``/auswerten`` ist ein
    Befehl, und **kein Befehl ruft synchron ein Modell** (AGENTS.md)."""
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
        tg.sende(chat_id, _TEXT_AUSFALL)
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
        tg.sende(chat_id, _TEXT_RUECKKEHR)
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

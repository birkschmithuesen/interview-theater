"""Aufnahme-Pipeline: der Weg einer Sprachnachricht von der Ankunft bis zum
fertigen Material (Aufgabe 8, SPEC-kontext-architektur.md § 10).

Sprache ist hier nicht nur Interview-Material: die Gruppe spricht auch normale
Arbeitskommunikation und Regieanweisungen ein. Die Dauer einer Sprachnachricht
sagt darueber nichts aus (§ 10.1, teil-b.md Aufgabe 5) -- ein Interview kann
aus fuenf kurzen Sprachnachrichten bestehen, eine Regieanweisung laenger als
eine Minute dauern. Stattdessen entscheidet ``gruppe.interviewmodus_seit``,
den die Gruppe ausdruecklich schaltet (durch Saetze wie "wir machen jetzt ein
Interview" ueber den Absichtserkenner, oder durch /interview und /fertig):

* **kurz** (Modus aus): ein Gespraechsbeitrag. Latenz zerstoert den Fluss,
  darum keine Empfangsbestaetigung und ein knappes Zeitbudget.
* **lang** (Modus an): Material (ein Interview). Darf dauern; bekommt eine
  sofortige Empfangsbestaetigung und laeuft zusaetzlich durch den Verdichter
  (§ 4.2).

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

Beide Klassen durchlaufen dieselbe Statusmaschine in der Tabelle ``aufnahme``:
``empfangen`` → ``transkribiert`` → ``fertig`` (oder ``fehlgeschlagen`` nach
MAX_VERSUCHE erfolglosen Anlaeufen). Der Zwischenstand ``transkribiert`` ist ein
echter Wiederaufnahmepunkt: schlaegt bei einer langen Aufnahme nur die
Verdichtung fehl (Transkript schon da), fragt ein erneuter Anlauf nicht noch
einmal Whisper, sondern verdichtet nur weiter.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from interview_theater import repo, stt, verdichter

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

#: Kein Klassifikations-Schwellwert (den gibt es seit Aufgabe 5 nicht mehr) --
#: nur der Ausloeser fuer den beilaeufigen Materialhinweis (§ 10.1): eine
#: Sprachnachricht ueber dieser Dauer, waehrend der Interviewmodus AUS ist,
#: bekommt eine angehaengte Zeile an der ohnehin faelligen Antwort, keine
#: eigene Nachricht und keine Rueckfrage.
HINWEIS_AB_S = 60

#: Wortlaut aus SPEC § 10.4/§ 11.1, ohne Umlaute wie der uebrige Quelltext.
_TEXT_EMPFANGSBESTAETIGUNG = "Ich hoere durch - das kann einen Moment dauern."
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


def klasse_fuer(conn, chat_id: int) -> str:
    """Ordnet eine Sprachnachricht einer der zwei Klassen zu (§ 10.1,
    teil-b.md Aufgabe 5) -- ausschliesslich anhand von
    ``gruppe.interviewmodus_seit``, NICHT anhand der Dauer: die sagt nichts
    ueber die Art aus (ein Interview kann aus fuenf kurzen Sprachnachrichten
    bestehen, eine Regieanweisung laenger als eine Minute dauern)."""
    return "lang" if repo.ist_interviewmodus_an(conn, chat_id) else "kurz"


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

    Liefert die neue ``aufnahme_id``, oder ``None``, wenn der Download nach
    Wiederholung endgueltig scheiterte. In diesem Fall entsteht bewusst
    **keine** ``aufnahme``-Zeile (es gibt kein Audio, das der Nachhol-Arbeiter
    je nachholen koennte) -- dafuer aber ein Vorfall und eine Bitte an die
    Gruppe, es nochmal zu schicken, damit nichts spurlos verschwindet."""
    chat_id = n["chat_id"]
    message_id = n["message_id"]
    klasse = klasse_fuer(conn, chat_id)

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

    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, klasse, "sprache",
        audio_pfad=str(ziel), dauer=n.get("dauer"),
    )

    if klasse == "lang":
        try:
            tg.sende(chat_id, _TEXT_EMPFANGSBESTAETIGUNG)
        except Exception:
            log.exception("Empfangsbestaetigung fehlgeschlagen, chat_id=%s", chat_id)

    return aufnahme_id


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
    if row is None or row["status"] in ("fertig", "fehlgeschlagen"):
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
    if row["klasse"] == "kurz":
        _kurz_abschliessen(conn, tg, klm, e, row, zug, nachgeholt)
    else:
        _lang_abschliessen(conn, tg, klm, e, row)


def _transkribiere_mit_meldung(conn, tg, e, klient, row) -> str | None:
    """Ruft stt.transkribiere auf, waehrenddessen die Tippanzeige laeuft (ab
    TIPPANZEIGE_AB_S, fuer beide Klassen). Die Zwischenmeldung ("Ich hoer
    noch zu...", ab MELDUNG_AB_S) gibt es dagegen nur fuer Klasse *kurz* --
    eine lange Aufnahme hat schon die Empfangsbestaetigung aus ``empfange()``
    bekommen, eine zweite Nachricht fuer dieselbe Sache waere Rauschen."""
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

    timer_meldung = None
    if row["klasse"] == "kurz":
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
        if timer_meldung is not None:
            timer_meldung.cancel()


def _ist_ersatzname(name: str | None) -> bool:
    """Erkennt den automatisch vergebenen Namen 'Interview n' (repo.lege_
    aufnahme_an), im Unterschied zu einem von der Gruppe echt vergebenen
    Namen."""
    return bool(name) and re.fullmatch(r"Interview \d+", name) is not None


def _aufnahme_beschreibung(row, gross: bool) -> str:
    """Beschreibt eine Aufnahme in einer Nutzernachricht. Ein automatisch
    vergebener Ersatzname wie 'Interview 1' wirkt in einer Chatnachricht
    unfreiwillig komisch ('Die Aufnahme von Interview 1...') -- ohne einen
    von der Gruppe vergebenen echten Namen wird stattdessen die Klasse
    genannt."""
    artikel = "Die" if gross else "die"
    name = row["name"]
    if name and not _ist_ersatzname(name):
        return f"{artikel} Aufnahme von {name}"
    art = "lange Aufnahme" if row["klasse"] == "lang" else "kurze Aufnahme"
    return f"{artikel} letzte {art}"


def _sende_bitte_nochmal(tg, chat_id, row) -> None:
    text = f"{_aufnahme_beschreibung(row, gross=True)} konnte ich nicht verstehen - schickt sie bitte nochmal."
    try:
        tg.sende(chat_id, text)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _sende_verdichtung_gescheitert(tg, chat_id, row) -> None:
    text = (
        f"Ich konnte {_aufnahme_beschreibung(row, gross=False)} nicht auswerten. "
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
    (Klasse *lang*) nur beim **ersten** Fehlschlag dieser Aufnahme raus --
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
    if (row["klasse"] == "lang" and versuche == 1) or (row["klasse"] == "kurz" and endgueltig):
        _sende_bitte_nochmal(tg, chat_id, row)

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


def _lang_abschliessen(conn, tg, klm, e, row) -> None:
    """Verdichtet eine lange Aufnahme (Material). Schlaegt die Verdichtung
    fehl, bleibt status='transkribiert' stehen und der Versuchszaehler steigt
    -- derselbe Zaehler und dieselbe MAX_VERSUCHE-Grenze wie bei einem
    Transkriptionsfehlschlag (kritische Nachbesserung: eine misslingende
    Verdichtung ist ein bezahlter Sprachmodell-Aufruf und darf nicht
    unbegrenzt oft alle NACHHOL_INTERVALL_S Sekunden wiederholt werden). Ab
    MAX_VERSUCHE wird endgueltig aufgegeben, das Transkript bleibt aber
    erhalten -- nur die Zusammenfassung fehlt."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]
    try:
        verdichter.verdichte(klm, conn, e, aufnahme_id)
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
            _sende_verdichtung_gescheitert(tg, chat_id, row)
        return
    repo.setze_status(conn, aufnahme_id, "fertig")


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
    wurde (SPEC § 10.3: 'Nachgeholtes loest nie eine Antwort aus')."""
    for row in repo.offene_aufnahmen_fuer_bot(conn, e.bot_name):
        try:
            verarbeite(conn, tg, klm, e, klient, row["id"], zug=zug, nachgeholt=True)
        except Exception:
            log.exception("Nachholen einer Aufnahme fehlgeschlagen, id=%s", row["id"])


def importiere_text(conn, e, chat_id: int, message_id: int, text: str, name: str | None = None) -> int:
    """Legt Text als gleichwertiges Material an (§ 10.5): deckt sowohl den
    Rueckfallweg ab (Whisper streikt) als auch das Einspeisen vorhandenen
    Recherchematerials, das nie gesprochen wurde. Legt die Aufnahme nur bis
    'transkribiert' an -- die eigentliche Verdichtung geschieht ausschliesslich
    in ``verarbeite()`` (Aufruf durch den Aufrufer selbst oder durch den
    Nachhol-Arbeiter, falls der erste Anlauf nicht sofort verdichtet).

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

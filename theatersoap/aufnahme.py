"""Aufnahme-Pipeline: der Weg einer Sprachnachricht von der Ankunft bis zum
fertigen Material (Aufgabe 8, SPEC-kontext-architektur.md § 10).

Sprache ist hier nicht nur Interview-Material: die Gruppe spricht auch normale
Arbeitskommunikation und Regieanweisungen ein. Telegram liefert `voice.duration`
in den Metadaten, bevor irgendetwas heruntergeladen wird -- das genuegt fuer die
einzige Unterscheidung, die zaehlt (§ 10.1):

* **kurz** (bis KURZ_GRENZE_S): ein Gespraechsbeitrag. Latenz zerstoert den
  Fluss, darum keine Empfangsbestaetigung und ein knappes Zeitbudget.
* **lang**: Material (ein Interview). Darf dauern; bekommt eine sofortige
  Empfangsbestaetigung und laeuft zusaetzlich durch den Verdichter (§ 4.2).

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
import threading
from datetime import datetime, timezone
from pathlib import Path

from theatersoap import repo, stt, verdichter

log = logging.getLogger(__name__)

# Alle Schwellwerte an genau dieser Stelle (Auftragshinweis 5), Werte aus der
# Messung vom 03.09.2026 (76 Laeufe, Median 2,9 s, einziger Ausreisser 8,88 s,
# kein Lauf ueber 10 s). Nirgends im Code als Zahl wiederholt.
KURZ_GRENZE_S = 45
TIPPANZEIGE_AB_S = 5
MELDUNG_AB_S = 12
BUDGET_KURZ_S = 45
BUDGET_LANG_S = 90
NACHHOL_INTERVALL_S = 60
MAX_VERSUCHE = 5

#: Wortlaut aus SPEC § 10.4/§ 11.1, ohne Umlaute wie der uebrige Quelltext.
_TEXT_EMPFANGSBESTAETIGUNG = "Ich hoere durch - das kann einen Moment dauern."
_TEXT_ZWISCHENMELDUNG = "Ich hoer noch zu, einen Moment."
_TEXT_AUSFALL = (
    "Ich kann gerade nicht hoeren. Schreibt mir solange, ich sammle die "
    "Aufnahmen und hole sie nach."
)
_TEXT_RUECKKEHR = "Ich kann wieder hoeren."


def klasse_fuer(dauer: int | None) -> str:
    """Ordnet eine Dauer (Sekunden) einer der zwei Klassen zu (§ 10.1).

    ``None`` liefert 'lang': im Zweifel Material, weil ein faelschlich als
    Material behandelter Zuruf harmlos ist, ein faelschlich als Zuruf
    behandeltes Interview aber nicht verdichtet wuerde."""
    if dauer is None:
        return "lang"
    return "kurz" if dauer <= KURZ_GRENZE_S else "lang"


def _kein_zug(conn, tg, klm, e, chat_id) -> None:
    """Platzhalter fuer den Gespraechszug: ablauf.py existiert erst ab
    Aufgabe 10. Absichtlich ohne Wirkung, damit aufnahme.py keinen Import auf
    ein noch nicht existierendes Modul braucht."""
    return None


def empfange(conn, tg, e, n: dict) -> int:
    """Laedt die Sprachnachricht herunter und legt die Aufnahme mit
    ``status='empfangen'`` an -- ohne jeden Whisper-Kontakt (§ 10.2, die
    eigentliche Absicherung dieser Aufgabe).

    ``n`` ist das normalisierte Nachrichten-Dictionary aus
    ``theatersoap.telegram.lies_nachricht()``. Die zugehoerige Zeile in
    ``nachricht`` existiert im Normalbetrieb schon (die Polling-Schleife legt
    sie mit ``typ='sprache'``, ``text=NULL``, ``unterdrueckt=1`` an); der
    ``INSERT OR IGNORE`` hier stellt sicher, dass sie auch existiert, wenn
    ``empfange()`` direkt aufgerufen wird (Tests, spaeterer Nachhol-Anlauf)."""
    chat_id = n["chat_id"]
    message_id = n["message_id"]
    klasse = klasse_fuer(n.get("dauer"))

    ziel = Path(e.audio_verz) / str(chat_id) / f"{message_id}.ogg"
    tg.lade_datei(n["file_id"], ziel)

    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, klasse, "sprache",
        audio_pfad=str(ziel), dauer=n.get("dauer"),
    )

    repo.merke_nachricht(
        conn, chat_id, message_id, n.get("absender"), 0, "sprache", None,
        n.get("gesendet_am") or repo._jetzt(), 1,
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
    hereingereicht, weil ``ablauf.py`` (Aufgabe 10) noch nicht existiert;
    Voreinstellung: nichts tun.

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
        _lang_abschliessen(conn, klm, e, row)


def _transkribiere_mit_meldung(conn, tg, e, klient, row) -> str | None:
    """Ruft stt.transkribiere auf, waehrenddessen Tippanzeige (ab
    TIPPANZEIGE_AB_S) und Zwischenmeldung (ab MELDUNG_AB_S) laufen. Liefert
    das Transkript oder None nach einem gemeldeten Fehler."""
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
    timer_meldung = threading.Timer(MELDUNG_AB_S, _zwischenmeldung)
    timer_tipp.daemon = True
    timer_meldung.daemon = True
    timer_tipp.start()
    timer_meldung.start()
    try:
        return stt.transkribiere(e, klient, pfad, budget)
    except Exception as fehler:
        _melde_transkriptionsfehler(conn, tg, e, row, fehler)
        return None
    finally:
        timer_tipp.cancel()
        timer_meldung.cancel()


def _melde_transkriptionsfehler(conn, tg, e, row, fehler: Exception) -> None:
    """Bei jedem Fehlschlag: Versuch zaehlen, den einmaligen Whisper-Ausfall-
    Hinweis pruefen (melde_ausfall), bei Material zusaetzlich um erneutes
    Schicken bitten (§ 11.1), und ab MAX_VERSUCHE endgueltig aufgeben."""
    aufnahme_id = row["id"]
    chat_id = row["chat_id"]

    versuche = repo.zaehle_versuch_hoch(conn, aufnahme_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "transkription_fehlgeschlagen",
        f"Aufnahme {aufnahme_id} (Versuch {versuche}/{MAX_VERSUCHE}): "
        f"{type(fehler).__name__}",
    )

    melde_ausfall(conn, tg, e, chat_id)

    if row["klasse"] == "lang":
        name = row["name"] or f"Aufnahme {aufnahme_id}"
        try:
            tg.sende(
                chat_id,
                f"Die Aufnahme von {name} konnte ich nicht verstehen - "
                "schickt sie bitte nochmal.",
            )
        except Exception:
            log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)

    if versuche >= MAX_VERSUCHE:
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
    Antwort ausloesen."""
    from theatersoap import bot  # spaeter Import: vermeidet einen Ladezyklus mit bot.py

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
        try:
            zug(conn, tg, klm, e, chat_id)
        except Exception:
            log.exception("Gespraechszug nach kurzer Aufnahme fehlgeschlagen, chat_id=%s", chat_id)


def _lang_abschliessen(conn, klm, e, row) -> None:
    """Verdichtet eine lange Aufnahme (Material). Schlaegt die Verdichtung
    fehl, bleibt status='transkribiert' stehen: der Nachhol-Arbeiter fragt
    beim naechsten Anlauf nicht erneut Whisper, sondern verdichtet nur weiter."""
    aufnahme_id = row["id"]
    try:
        verdichter.verdichte(klm, conn, e, aufnahme_id)
    except Exception:
        log.exception("Verdichtung fehlgeschlagen, aufnahme_id=%s", aufnahme_id)
        repo.merke_vorfall(
            conn, row["chat_id"], getattr(e, "bot_name", None),
            "verdichtung_fehlgeschlagen", f"Aufnahme {aufnahme_id}",
        )
        return
    repo.setze_status(conn, aufnahme_id, "fertig")


def melde_ausfall(conn, tg, e, chat_id) -> None:
    """Meldet einen Whisper-Ausfall genau einmal pro Gruppe (§ 10.4):
    ``gruppe.whisper_stumm_seit`` leer → eine Zeile schicken und Feld setzen,
    sonst still bleiben."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None or gruppe["whisper_stumm_seit"]:
        return
    try:
        tg.sende(chat_id, _TEXT_AUSFALL)
    except Exception:
        log.exception("Ausfall-Hinweis fehlgeschlagen, chat_id=%s", chat_id)
        return
    repo.setze_whisper_stumm_seit(conn, chat_id, repo._jetzt())


def melde_rueckkehr(conn, tg, e, chat_id) -> None:
    """Meldet die Rueckkehr, wenn zuvor ein Ausfall gemeldet wurde (§ 10.4),
    und leert das Feld wieder."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None or not gruppe["whisper_stumm_seit"]:
        return
    try:
        tg.sende(chat_id, _TEXT_RUECKKEHR)
    except Exception:
        log.exception("Rueckkehr-Hinweis fehlgeschlagen, chat_id=%s", chat_id)
        return
    repo.setze_whisper_stumm_seit(conn, chat_id, None)


def nachholen(conn, tg, klm, e, klient) -> None:
    """Greift beim Start und danach alle NACHHOL_INTERVALL_S Sekunden alles
    auf, was nicht in einem Endzustand steht (§ 10.3) -- derselbe Weg, der
    auch die Nacht zwischen zwei Workshoptagen ueberbrueckt (§ 9.1 Schritt 3).

    Nur die Aufnahmen der Gruppen, die dieser Bot-Prozess bedient
    (``gruppe.bot_name == e.bot_name``, siehe
    ``repo.offene_aufnahmen_fuer_bot``): es laeuft ein Prozess je Gruppe auf
    derselben SQLite-Datei, und ohne diese Einschraenkung wuerden zwei
    Prozesse dieselbe Aufnahme gleichzeitig zu Whisper hochladen."""
    for row in repo.offene_aufnahmen_fuer_bot(conn, e.bot_name):
        try:
            verarbeite(conn, tg, klm, e, klient, row["id"], nachgeholt=True)
        except Exception:
            log.exception("Nachholen einer Aufnahme fehlgeschlagen, id=%s", row["id"])


def importiere_text(conn, e, chat_id: int, message_id: int, text: str, name: str | None = None) -> int:
    """Legt Text als gleichwertiges Material an (§ 10.5): deckt sowohl den
    Rueckfallweg ab (Whisper streikt) als auch das Einspeisen vorhandenen
    Recherchematerials, das nie gesprochen wurde. Laeuft durch denselben
    Verdichter wie eine Sprachaufnahme -- hier nur bis 'transkribiert', den
    Verdichtungsschritt macht der Aufrufer (wie eine per Whisper transkribierte
    Aufnahme auch erst in verarbeite() verdichtet wird)."""
    aufnahme_id = repo.lege_aufnahme_an(conn, chat_id, message_id, "lang", "text")
    repo.setze_transkript(conn, aufnahme_id, text)
    repo.setze_status(conn, aufnahme_id, "transkribiert")
    if name:
        repo.setze_aufnahme_name(conn, aufnahme_id, name)
    return aufnahme_id

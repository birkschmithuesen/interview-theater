"""Whisper V3 ueber Infomaniak, zweistufig und asynchron (SPEC-kontext-architektur.md
§ 11.3 Punkt 5, global-constraints.md).

Vorlage: /home/birk/projekte/kollektivgedaechtnis/stt_backends/infomaniak_whisper_backend.py
(Funktionen ``submit_transcription`` und ``fetch_transcript``), nur Leserecht, dort
nichts geaendert. Uebernommen: der Pfad ``/1/ai/{produkt}/...`` (nicht ``/2/.../openai/v1/``
-- der Server antwortet dort 404, das ist laut Vorlage „die Sorte Detail, die man genau
einmal herausfindet"), dass ``data`` in der Ergebnisantwort ein JSON-STRING ist und ein
zweites Mal geparst werden muss, die 25-MB-Grenze vor dem Upload und dass jeder unbekannte
Status als „weiterwarten" gilt statt als Fehler.

Abweichungen von der Vorlage:

* Die Vorlage kennt pro Chunk keinen Retry ("eine Wiederholung landet nach dem
  naechsten Satz und verwirrt mehr, als sie rettet") -- dort haengt ein
  Live-Mikrofon dahinter. Hier haengt eine Sprachnachricht dahinter, die als
  Ganzes im Verlauf landen soll; darum gibt es genau einen sofortigen
  Wiederholungsversuch mit neuem Upload (nicht nur erneutes Pollen derselben
  batch_id), bevor die Aufnahme auf ``status='empfangen'`` liegen bleibt und
  der Nachhol-Arbeiter (Aufgabe 8) uebernimmt.
* Fuer 5xx beim Absenden gilt dieselbe Wiederholungslogik wie in
  ``interview_theater.llm`` (WARTEZEITEN, Basisklasse ``httpx.TransportError``),
  unabhaengig vom einen Gesamt-Wiederholungsversuch oben.
* Kein separater STT-Schluessel: Infomaniak nimmt fuer Whisper denselben
  Produktschluessel wie fuer das Sprachmodell (``e.llm_key``) -- die
  Einstellungen kennen keine zehnte Umgebungsvariable dafuer.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import threading
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

#: ElevenLabs als zweiter STT-Weg (Nacht 07.10.2026, Padua-Ausfall Infomaniak
#: Whisper ab 10:48). Nur aktiv, wenn ``e.stt_ersatz_schluessel`` gesetzt ist
#: -- ohne Schluessel bleibt ``transkribiere`` bitgleich zum bisherigen Weg.
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/speech-to-text"

#: Welcher Anbieter das letzte ``transkribiere()``-Ergebnis in diesem Thread
#: lieferte -- ``aufnahme._buche_stt`` liest das fuer die Modellbuchung.
#: Thread-lokal statt ein Rueckgabewert zweiter Ordnung: der einzige Aufrufer
#: (``aufnahme._transkribiere_mit_meldung``) braucht es nur im Erfolgsfall,
#: und eine neue Signatur fuer alle bestehenden Aufrufer waere invasiver.
_zuletzt = threading.local()


def letzter_anbieter() -> str:
    return getattr(_zuletzt, "wert", "infomaniak")

#: Whisper erkennt die Sprache selbst (Karte A1, Birk E5): das Feld
#: ``language`` wird dann gar nicht gesendet.
AUTO = "auto"

#: Sekunden zwischen zwei Nachfragen beim Pollen. Gemessen (03.09.2026): der
#: Overhead liegt bei wenigen Sekunden, haeufiger fragen bringt nichts.
POLL_INTERVALL_S = 0.5

#: Grenze des Anbieters, vor dem Upload geprueft -- ein zu grosser Upload
#: kostet sonst die volle Wartezeit und scheitert dann doch.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: Wartezeiten zwischen Wiederholungen bei 5xx/Transportfehler beim Absenden,
#: wie in interview_theater.llm.WARTEZEITEN.
WARTEZEITEN = (0.7, 1.5, 3.0)

#: "success" beendet das Warten erfolgreich, diese hier beenden es als Fehler.
#: Alles andere heisst weiterwarten, begrenzt vom Zeitbudget: die Namen der
#: Zwischenzustaende sind nicht abschliessend bekannt, und ein unbekannter
#: Status darf nicht als Fehler durchgehen.
_ABBRUCHSTATUS = ("error", "failed", "aborted", "canceled", "cancelled")


#: MIME-Typen, auf die wir uns nicht auf ``mimetypes`` verlassen wollen.
#: ``.oga`` und ``.m4a`` kennt die Standardbibliothek je nach Plattform nicht,
#: und ``.ogg`` liefert dort teils ``application/ogg``.
_MIME_TYPEN = {
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def mime_typ(pfad: Path) -> str:
    """Leitet den MIME-Typ aus der Dateiendung ab.

    Gemessen am 04.09.2026: Ein fest verdrahtetes ``audio/ogg`` fuer eine
    WAV-Datei wird vom Anbieter zwar mit einer ``batch_id`` quittiert, der
    Auftrag bleibt danach aber dauerhaft auf ``pending`` und laeuft in die
    Zeitfrist (89,7 s statt 2,0 s). Das ist die schlimmste Sorte Fehler --
    im Betrieb nur als "haengt" sichtbar. Telegram liefert Audio nicht nur
    als ``voice`` (ogg/opus), sondern auch als ``audio`` (m4a, mp3) und als
    Dokument, deshalb reicht ein fester Wert hier nicht.
    """
    endung = pfad.suffix.lower()
    if endung in _MIME_TYPEN:
        return _MIME_TYPEN[endung]
    geraten, _ = mimetypes.guess_type(pfad.name)
    return geraten or "application/octet-stream"


class STTFehler(Exception):
    """Fehler bei der Spracherkennung.

    Der API-Schluessel steht ausschliesslich im Authorization-Header und darf
    in keiner Ausnahme und keinem Log auftauchen (wie interview_theater.llm.LLMFehler).
    """


class LeeresTranskript(STTFehler):
    """Whisper hat geantwortet, aber ohne Wortlaut -- Stille oder Rauschen,
    kein Dienstausfall (Karte Padua Brainstorm, 03.10.2026). Eine eigene
    Klasse statt eines Vergleichs gegen den Fehlertext: ``aufnahme.py``
    unterscheidet danach, ob ein Brainstorm-Segment still verworfen werden
    darf (nichts wurde gesagt) oder ob es sich um einen echten technischen
    Fehlschlag handelt, der einen Wiederholungsversuch verdient."""


class AuftragAbgebrochen(STTFehler):
    """Whisper hat den Auftrag angenommen und endgueltig abgebrochen
    (``_ABBRUCHSTATUS``, z. B. ``'failed'``) -- anders als ein 5xx oder
    Transportfehler kein voruebergehender Ausfall. ``aufnahme.py`` verwirft
    danach ein Ende-Segment sofort, statt es MAX_VERSUCHE-mal nachzuholen
    (Robo, Simulationslauf 05.10.2026: ein 110-Byte-Segment, fuenf Minuten)."""


def absenden(e, klient: httpx.Client, pfad: Path, budget_s: float,
             *, sprache: str | None = "de") -> str:
    """Laedt die Datei hoch und liefert die batch_id. Wiederholt bei 5xx/
    Transportfehler (WARTEZEITEN), analog interview_theater.llm.

    ``budget_s`` ist eine harte Frist ueber ALLE Versuche zusammen, nicht ein
    Zeitbudget pro Versuch: ohne diese Frist wuerde ein Server, der nie
    antwortet, bis zu ``gesamtversuche * budget_s`` plus die Wartezeiten
    dazwischen verbrauchen -- ein Vielfaches der Zusage an den Aufrufer.

    ``sprache`` ist die Sprache der Aufnahme (ISO 639-1) oder ``AUTO``/None --
    dann fehlt das Feld ``language``, und Whisper erkennt selbst. Der
    Aufrufer ermittelt sie (``aufnahme.whisper_sprache``); dieses Modul liest
    keine Datenbank.
    """
    if pfad.stat().st_size > MAX_UPLOAD_BYTES:
        raise STTFehler(f"{pfad.name} ist groesser als 25 MB")

    url = f"{e.stt_basis.rstrip('/')}/1/ai/{e.stt_produkt}/openai/audio/transcriptions"
    headers = {"Authorization": f"Bearer {e.llm_key}"}
    frist = time.monotonic() + budget_s

    letzter_fehler: Exception | None = None
    gesamtversuche = len(WARTEZEITEN) + 1
    # Reihenfolge wie vor A1 (model, language, response_format), damit der
    # Upload fuer Deutsch byte-gleich bleibt.
    daten = {"model": "whisper"}
    if sprache and sprache != AUTO:
        daten["language"] = sprache
    daten["response_format"] = "verbose_json"
    for versuch in range(gesamtversuche):
        rest = frist - time.monotonic()
        if rest <= 0:
            break  # Frist bereits erreicht -- kein weiterer Versuch mehr
        try:
            with open(pfad, "rb") as datei:
                antwort = klient.post(
                    url,
                    headers=headers,
                    files={"file": (pfad.name, datei, mime_typ(pfad))},
                    data=daten,
                    timeout=max(1.0, rest),
                )
            antwort.raise_for_status()
            koerper = antwort.json() or {}
            batch_id = koerper.get("batch_id")
            if not batch_id:
                raise STTFehler("keine batch_id in der Antwort")
            return str(batch_id)
        except httpx.HTTPStatusError as fehler:
            if fehler.response.status_code < 500:
                raise STTFehler(
                    f"Whisper lehnte den Upload ab: HTTP {fehler.response.status_code}"
                ) from fehler
            letzter_fehler = fehler
        except httpx.TransportError as fehler:
            letzter_fehler = fehler

        rest_vor_wartezeit = frist - time.monotonic()
        if versuch < len(WARTEZEITEN) and rest_vor_wartezeit > 0:
            time.sleep(min(WARTEZEITEN[versuch], rest_vor_wartezeit))

    if letzter_fehler is None:
        raise STTFehler(
            f"Whisper-Upload: Zeitbudget von {budget_s}s aufgebraucht, "
            "bevor ueberhaupt ein Versuch stattfinden konnte"
        )
    raise STTFehler(
        f"Whisper-Upload nicht erreichbar (zuletzt: {type(letzter_fehler).__name__}), "
        f"Zeitbudget von {budget_s}s ausgeschoepft"
    ) from letzter_fehler


def abholen(e, klient: httpx.Client, batch_id: str, budget_s: float) -> str:
    """Pollt das Ergebnis, bis ``status == 'success'``, ein Abbruchstatus
    eintritt, oder das Zeitbudget aufgebraucht ist. ``data`` in der
    Ergebnisantwort ist ein JSON-STRING und wird ein zweites Mal geparst.

    Ein 5xx beim Pollen ist kein Abbruch, sondern heisst weiterwarten,
    solange die Frist reicht -- der Auftrag laeuft serverseitig weiter. Ein
    4xx (z.B. eine unbekannte batch_id) ist dagegen ein sofortiger Fehler:
    weiterpollen wuerde dort nie zu einem Ergebnis fuehren.
    """
    url = f"{e.stt_basis.rstrip('/')}/1/ai/{e.stt_produkt}/results/{batch_id}"
    headers = {"Authorization": f"Bearer {e.llm_key}"}
    frist = time.monotonic() + budget_s

    while True:
        rest = frist - time.monotonic()
        if rest <= 0:
            raise STTFehler(f"Auftrag {batch_id} war nach {budget_s}s noch nicht fertig")

        antwort = klient.get(url, headers=headers, timeout=max(1.0, rest))
        try:
            antwort.raise_for_status()
        except httpx.HTTPStatusError as fehler:
            if antwort.status_code < 500:
                raise STTFehler(
                    f"Whisper lehnte die Ergebnisabfrage ab: HTTP {antwort.status_code}"
                ) from fehler
            # 5xx: der Auftrag laeuft serverseitig weiter, kein Abbruch.
            if time.monotonic() >= frist:
                raise STTFehler(
                    f"Auftrag {batch_id} war nach {budget_s}s noch nicht abrufbar "
                    f"(zuletzt HTTP {antwort.status_code} bei der Ergebnisabfrage)"
                ) from fehler
            time.sleep(POLL_INTERVALL_S)
            continue

        koerper = antwort.json() or {}
        status = str(koerper.get("status", "")).lower()

        if status == "success":
            break
        if status in _ABBRUCHSTATUS:
            raise AuftragAbgebrochen(f"Auftrag {batch_id} endete als {status!r}")
        if time.monotonic() >= frist:
            raise STTFehler(
                f"Auftrag {batch_id} war nach {budget_s}s noch {status!r}"
            )
        time.sleep(POLL_INTERVALL_S)

    daten = koerper.get("data")
    if isinstance(daten, str):
        try:
            daten = json.loads(daten)
        except json.JSONDecodeError as fehler:
            raise STTFehler(f"Ergebnis von {batch_id} ist kein gueltiges JSON: {fehler}") from fehler

    ergebnis = daten or {}
    if ergebnis.get("language"):
        log.info("Whisper erkannte Sprache %s (Auftrag %s)", ergebnis["language"], batch_id)
    return str(ergebnis.get("text") or "").strip()


def _transkribiere_infomaniak(e, klient: httpx.Client, pfad: Path, budget_s: float,
                               *, sprache: str | None = "de") -> str:
    """Absenden und Abholen verbunden, mit hartem Gesamtbudget ueber beides.

    Genau ein sofortiger Wiederholungsversuch mit neuem Upload, wenn der
    erste Anlauf scheitert -- kein Schleifen im heissen Pfad. Ein leeres
    Transkript ist ein Fehler, kein gueltiges Ergebnis: Stille darf nicht als
    Aeusserung im Verlauf landen.

    ``sprache`` wird unveraendert an ``absenden`` durchgereicht (ISO 639-1
    oder ``AUTO``/None fuer Spracherkennung durch Whisper selbst).
    """
    frist = time.monotonic() + budget_s
    letzter_fehler: STTFehler | None = None

    for versuch in range(2):
        rest = frist - time.monotonic()
        if rest <= 0:
            letzter_fehler = letzter_fehler or STTFehler(
                f"kein Zeitbudget von {budget_s}s mehr uebrig"
            )
            break
        try:
            batch_id = absenden(e, klient, pfad, rest, sprache=sprache)
            rest_abholen = frist - time.monotonic()
            if rest_abholen <= 0:
                raise STTFehler("kein Zeitbudget mehr fuer das Abholen")
            text = abholen(e, klient, batch_id, rest_abholen)
            if not text:
                raise LeeresTranskript("leeres Transkript -- Stille ist kein gueltiges Ergebnis")
            return text
        except STTFehler as fehler:
            letzter_fehler = fehler
            continue

    raise letzter_fehler


def _infomaniak_einmal(e, klient: httpx.Client, pfad: Path, budget_s: float,
                        *, sprache: str | None) -> str:
    """Wie ``_transkribiere_infomaniak``, aber genau EIN Anlauf (kein zweiter
    Upload bei Fehlschlag) -- wenn ein Ersatzweg bereitsteht, soll die Zeit
    fuer dessen Versuch reichen statt im zweiten Infomaniak-Upload zu verbrennen."""
    frist = time.monotonic() + budget_s
    batch_id = absenden(e, klient, pfad, budget_s, sprache=sprache)
    rest = frist - time.monotonic()
    if rest <= 0:
        raise STTFehler("kein Zeitbudget mehr fuer das Abholen")
    text = abholen(e, klient, batch_id, rest)
    if not text:
        raise LeeresTranskript("leeres Transkript -- Stille ist kein gueltiges Ergebnis")
    return text


def transkribiere_elevenlabs(klient: httpx.Client, pfad: Path, budget_s: float,
                              *, sprache: str | None, schluessel: str) -> str:
    """ElevenLabs Scribe v2 als zweiter STT-Weg, synchron (keine batch_id,
    keine Zwischenabfrage -- anders als Infomaniak liefert die Antwort den
    Text direkt). ``sprache`` nur gesendet, wenn bekannt (sonst erkennt
    ElevenLabs selbst, wie Whisper bei ``AUTO``)."""
    headers = {"xi-api-key": schluessel}
    daten = {"model_id": "scribe_v2", "tag_audio_events": "false"}
    if sprache and sprache != AUTO:
        daten["language_code"] = sprache

    frist_s = max(1.0, budget_s)
    try:
        with open(pfad, "rb") as datei:
            antwort = klient.post(
                ELEVENLABS_URL,
                headers=headers,
                files={"file": (pfad.name, datei, mime_typ(pfad))},
                data=daten,
                timeout=frist_s,
            )
        antwort.raise_for_status()
    except httpx.HTTPStatusError as fehler:
        raise STTFehler(
            f"ElevenLabs lehnte den Upload ab: HTTP {fehler.response.status_code}"
        ) from fehler
    except httpx.TransportError as fehler:
        raise STTFehler(
            f"ElevenLabs nicht erreichbar ({type(fehler).__name__}), "
            f"Zeitbudget von {budget_s}s ausgeschoepft"
        ) from fehler

    koerper = antwort.json() or {}
    text = str(koerper.get("text") or "").strip()
    if not text:
        raise LeeresTranskript("ElevenLabs: leeres Transkript -- Stille ist kein gueltiges Ergebnis")
    return text


def transkribiere(e, klient: httpx.Client, pfad: Path, budget_s: float,
                   *, sprache: str | None = "de") -> str:
    """Infomaniak bleibt der Hauptweg. Nur wenn ``e.stt_ersatz_schluessel``
    gesetzt ist (Nacht 07.10.2026, Padua-Ausfall), bekommt Infomaniak
    hoechstens ``min(budget_s, e.stt_infomaniak_budget_s)`` fuer GENAU EINEN
    Anlauf (kein zweiter Upload); jeder STTFehler ausser einem echten leeren
    Transkript (Stille ist kein Dienstausfall) loest danach ElevenLabs mit
    dem verbleibenden Budget aus. Ohne Schluessel: bitgleich zum bisherigen
    Weg. ``IT_STT_NUR_ERSATZ`` ueberspringt Infomaniak ganz (Schalter fuer
    einen Totalausfall)."""
    ersatz_schluessel = getattr(e, "stt_ersatz_schluessel", "") or ""
    _zuletzt.wert = "infomaniak"

    if not ersatz_schluessel:
        return _transkribiere_infomaniak(e, klient, pfad, budget_s, sprache=sprache)

    frist = time.monotonic() + budget_s
    nur_ersatz = bool(getattr(e, "stt_nur_ersatz", False))

    if not nur_ersatz:
        primaer_budget_s = min(budget_s, getattr(e, "stt_infomaniak_budget_s", 25.0) or 25.0)
        try:
            text = _infomaniak_einmal(e, klient, pfad, primaer_budget_s, sprache=sprache)
            log.info("STT via infomaniak")
            return text
        except LeeresTranskript:
            raise
        except STTFehler:
            pass  # echter Fehlschlag (nicht Stille) -- weiter zu ElevenLabs

    rest_s = frist - time.monotonic()
    text = transkribiere_elevenlabs(
        klient, pfad, max(1.0, rest_s), sprache=sprache, schluessel=ersatz_schluessel)
    _zuletzt.wert = "elevenlabs"
    log.info("STT via elevenlabs")
    return text

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
  ``theatersoap.llm`` (WARTEZEITEN, Basisklasse ``httpx.TransportError``),
  unabhaengig vom einen Gesamt-Wiederholungsversuch oben.
* Kein separater STT-Schluessel: Infomaniak nimmt fuer Whisper denselben
  Produktschluessel wie fuer das Sprachmodell (``e.llm_key``) -- die
  Einstellungen kennen keine zehnte Umgebungsvariable dafuer.
"""

from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path

import httpx

#: Sekunden zwischen zwei Nachfragen beim Pollen. Gemessen (03.09.2026): der
#: Overhead liegt bei wenigen Sekunden, haeufiger fragen bringt nichts.
POLL_INTERVALL_S = 0.5

#: Grenze des Anbieters, vor dem Upload geprueft -- ein zu grosser Upload
#: kostet sonst die volle Wartezeit und scheitert dann doch.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: Wartezeiten zwischen Wiederholungen bei 5xx/Transportfehler beim Absenden,
#: wie in theatersoap.llm.WARTEZEITEN.
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
    in keiner Ausnahme und keinem Log auftauchen (wie theatersoap.llm.LLMFehler).
    """


def absenden(e, klient: httpx.Client, pfad: Path, budget_s: float) -> str:
    """Laedt die Datei hoch und liefert die batch_id. Wiederholt bei 5xx/
    Transportfehler (WARTEZEITEN), analog theatersoap.llm.

    ``budget_s`` ist eine harte Frist ueber ALLE Versuche zusammen, nicht ein
    Zeitbudget pro Versuch: ohne diese Frist wuerde ein Server, der nie
    antwortet, bis zu ``gesamtversuche * budget_s`` plus die Wartezeiten
    dazwischen verbrauchen -- ein Vielfaches der Zusage an den Aufrufer.
    """
    if pfad.stat().st_size > MAX_UPLOAD_BYTES:
        raise STTFehler(f"{pfad.name} ist groesser als 25 MB")

    url = f"{e.stt_basis.rstrip('/')}/1/ai/{e.stt_produkt}/openai/audio/transcriptions"
    headers = {"Authorization": f"Bearer {e.llm_key}"}
    frist = time.monotonic() + budget_s

    letzter_fehler: Exception | None = None
    gesamtversuche = len(WARTEZEITEN) + 1
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
                    data={
                        "model": "whisper",
                        "language": "de",
                        "response_format": "verbose_json",
                    },
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
            raise STTFehler(f"Auftrag {batch_id} endete als {status!r}")
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

    return str((daten or {}).get("text") or "").strip()


def transkribiere(e, klient: httpx.Client, pfad: Path, budget_s: float) -> str:
    """Absenden und Abholen verbunden, mit hartem Gesamtbudget ueber beides.

    Genau ein sofortiger Wiederholungsversuch mit neuem Upload, wenn der
    erste Anlauf scheitert -- kein Schleifen im heissen Pfad. Ein leeres
    Transkript ist ein Fehler, kein gueltiges Ergebnis: Stille darf nicht als
    Aeusserung im Verlauf landen.
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
            batch_id = absenden(e, klient, pfad, rest)
            rest_abholen = frist - time.monotonic()
            if rest_abholen <= 0:
                raise STTFehler("kein Zeitbudget mehr fuer das Abholen")
            text = abholen(e, klient, batch_id, rest_abholen)
            if not text:
                raise STTFehler("leeres Transkript -- Stille ist kein gueltiges Ergebnis")
            return text
        except STTFehler as fehler:
            letzter_fehler = fehler
            continue

    raise letzter_fehler

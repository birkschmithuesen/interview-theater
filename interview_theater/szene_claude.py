"""Der zweite Weg fuer den Szenen-Aufruf: Claude ueber den lokalen Proxy
(``hermes-anthropic-proxy.service``, 127.0.0.1:28764, Anthropic-Messages-Format).

**Warum es diesen Weg gibt (Birk, 05.09.2026 frueh).** Vier Modelle, ein
Prompt, dieselbe Szene: Opus war "mit Abstand besser" -- der einzige, der die
Dramaturgie-Regeln tat statt sie zu zitieren (Gegenstand, an dem sich die
Szene entscheidet; woertlich wiederholte Uhrzeit; Schweigen im Kippmoment;
"Okay. -- Okay."). Kimi klebte Interviewzitate als Repliken hinein.

**Warum es NUR fuer die Szene gilt.** Alles andere -- Gespraech, Erkenner,
Verdichter, Journal, Sprachprofil, Whisper -- bleibt bei Infomaniak
(Schweiz). Die Szene ist der eine Aufruf, bei dem Textqualitaet den
Ausschlag gibt, und der einzige, der ueber eine amerikanische API laeuft.
Deshalb bekommt die Gruppe VOR jedem Szenen-Aufruf die Warnung (szene.py
``_TEXT_WARNUNG_USA``), dass ab jetzt Daten in die USA gehen: Arbeitsstand,
Figuren mit ihren Zitaten, Szenenfelder, Journal -- keine Transkripte, keine
Audio, keine Telegram-Namen (die stehen nicht im Szenen-Prompt).

**Schalter.** ``IT_SZENE_ANBIETER=claude`` in der Env der Gruppe; Vorgabe ist
``infomaniak`` (dann passiert hier gar nichts). ``IT_SZENE_URL`` und
``IT_SZENE_MODELL`` ueberschreiben Proxy und Modell.

**Kein Import aus ``simulation/``.** Dort liegt ein aehnlicher Klient
(``simulation/claude.py``) -- der ist Messinstrument und darf nie mit dem
Betrieb zusammenfallen. Dieser hier ist absichtlich ein Zwilling, kein
Alias.
"""
from __future__ import annotations

import logging
import time

import httpx

from interview_theater import repo

log = logging.getLogger(__name__)

URL_VORGABE = "http://127.0.0.1:28764/v1/messages"
MODELL_VORGABE = "claude-opus-5"
API_VERSION = "2023-06-01"
#: Deckel, kein Ziel (Birk). Opus schrieb die Vergleichsszene mit ~3k
#: Zeichen; 32k laesst Luft fuer laengere Formen (Lied, Chor).
MAX_TOKENS = 32_000
WARTEZEITEN = (3.0, 10.0, 30.0)


class ClaudeFehler(Exception):
    pass


def ist_aktiv(e) -> bool:
    return (getattr(e, "szene_anbieter", None) or "infomaniak").lower() == "claude"


def prosa(conn, e, klient: httpx.Client, chat_id: int | None, system: str,
          nutzer: str, art: str, timeout: float) -> str:
    """Ein Aufruf, ein Text. Bucht in ``aufruf`` mit modus 'C' (Claude), damit
    Dashboard und Kostenrechnung den Weg sehen -- mit 0 CHF, weil Abo."""
    url = getattr(e, "szene_url", None) or URL_VORGABE
    modell = getattr(e, "szene_modell", None) or MODELL_VORGABE
    koerper = {
        "model": modell,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": nutzer}],
    }
    headers = {"content-type": "application/json", "anthropic-version": API_VERSION}
    start = time.monotonic()
    letzter: Exception | None = None
    for versuch in range(len(WARTEZEITEN) + 1):
        try:
            antwort = klient.post(url, headers=headers, json=koerper, timeout=timeout)
            antwort.raise_for_status()
            daten = antwort.json()
            teile = [b.get("text") or "" for b in (daten.get("content") or [])
                     if isinstance(b, dict) and b.get("type") == "text"]
            text = "\n".join(teile).strip()
            nutzung = daten.get("usage") or {}
            _buche(conn, chat_id, e, art, modell, nutzung, daten.get("stop_reason"),
                   time.monotonic() - start, erfolg=bool(text))
            if not text:
                raise ClaudeFehler(
                    f"keine Textbloecke (stop_reason={daten.get('stop_reason')})"
                )
            return text
        except httpx.HTTPStatusError as fehler:
            code = fehler.response.status_code
            if code != 429 and code < 500:
                _buche(conn, chat_id, e, art, modell, {}, f"http_{code}",
                       time.monotonic() - start, erfolg=False)
                raise ClaudeFehler(f"Claude-Proxy lehnte ab: HTTP {code}") from fehler
            letzter = fehler
        except httpx.TransportError as fehler:
            letzter = fehler
        if versuch < len(WARTEZEITEN):
            time.sleep(WARTEZEITEN[versuch])
    _buche(conn, chat_id, e, art, modell, {}, "abgebrochen", time.monotonic() - start, erfolg=False)
    raise ClaudeFehler(f"Claude-Proxy nach {len(WARTEZEITEN) + 1} Versuchen: {letzter}")


def _buche(conn, chat_id, e, art, modell, nutzung, finish, dauer_s, erfolg):
    try:
        ein = int(nutzung.get("input_tokens") or 0)
        repo.merke_aufruf(
            conn, chat_id, art, modus="C", geschaetzte_token=ein,
            tatsaechliche_token=ein, antwort_token=int(nutzung.get("output_tokens") or 0),
            finish_reason=finish, dauer_ms=int(dauer_s * 1000), erfolg=1 if erfolg else 0,
        )
    except Exception:  # noqa: BLE001 -- Buchung darf den Aufruf nie mitreissen
        log.exception("Aufruf-Buchung (Claude) fehlgeschlagen")

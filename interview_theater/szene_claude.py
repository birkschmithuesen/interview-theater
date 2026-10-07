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

import json
import logging
import time

import httpx

from interview_theater import kosten, repo

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


#: Wie in ``llm.py``: eine Prozessflagge, kein Dauerversuch.
_STROM_AUS = False


class _StromNichtVerfuegbar(Exception):
    """Der Proxy/Anbieter kann oder will ueberhaupt nicht streamen -- BEVOR
    ein Stueck kam. Setzt die Prozessflagge ``_STROM_AUS`` dauerhaft."""


class _StromVoruebergehend(Exception):
    """Ein VORUEBERGEHENDER Fehler (408, 429, 5xx, 529 "overloaded",
    Transport-/Dekodierfehler) -- BEVOR ein Stueck kam (wie in ``llm.py``,
    Fix Runde 1, Punkt 3). Infomaniak UND der Claude-Proxy koennen mit
    429/5xx drosseln; ein einzelner Drosselimpuls darf nicht jede weitere
    Szene dieses Prozesses auf Nichtstreaming umschalten. Setzt die
    Prozessflagge NICHT."""


class _StromAbbruch(Exception):
    """Der Stream ist mitten drin abgerissen -- NACH dem ersten Stueck. Setzt
    die Prozessflagge nie: ein Abbruch sagt nichts darueber, ob der naechste
    Stream gelingt."""


def _abgeschaltet() -> bool:
    return _STROM_AUS


def vergiss_strom() -> None:
    """Nur fuer Tests."""
    global _STROM_AUS
    _STROM_AUS = False


def _melde_strom_aus(conn, e, chat_id, grund: str) -> None:
    global _STROM_AUS
    if _STROM_AUS:
        return
    _STROM_AUS = True
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "strom_nicht_verfuegbar",
            f"Claude-Proxy ohne Stream ({grund})",
        )
    except Exception:  # noqa: BLE001
        log.exception("Vorfall strom_nicht_verfuegbar nicht geschrieben")


def _blockierend(klient, url, headers, koerper, timeout) -> dict:
    antwort = klient.post(url, headers=headers, json=koerper, timeout=timeout)
    antwort.raise_for_status()
    return antwort.json()


#: HTTP-Stati, die als vorruebergehend gelten (Drosselung/Ueberlast) --
#: 529 ist Anthropics eigener "overloaded"-Code, zusaetzlich zu den
#: ueblichen 408/429/5xx aus ``llm.py``.
_HTTP_VORUEBERGEHEND = (408, 429, 529)

#: Anthropic schickt Ueberlast/Drosselung nicht nur als HTTP-Status, sondern
#: auch als eigenes SSE-Ereignis INNERHALB einer HTTP-200-Antwort
#: (``{"type": "error", "error": {"type": "overloaded_error"}}``, Review-Fund
#: Aufgabe 6). Diese drei Fehlertypen gelten als voruebergehend; alles andere
#: (z. B. ``invalid_request_error``) ist ein echtes "das geht so nicht".
_FEHLERTYPEN_VORUEBERGEHEND = ("overloaded_error", "rate_limit_error", "api_error")


def _stream(klient, url, headers, koerper, timeout, bei_teil) -> dict:
    """Ein Aufruf mit ``stream: true`` im Anthropic-Messages-Format; baut aus
    den Ereignissen denselben Koerper, den der blockierende Weg liefert.

    Gelesen werden ``message_start`` (input_tokens), ``content_block_delta``
    mit ``delta.type == "text_delta"``, ``message_delta`` (stop_reason,
    output_tokens), ``message_stop`` und das SSE-eigene ``error``-Ereignis
    (Ueberlast/Drosselung INNERHALB einer HTTP-200-Antwort). Ein
    ``thinking_delta`` wird **nicht** weitergegeben -- die Denkspur ist nie
    fuer die Gruppe. Mehrere Textbloecke (``index`` im Ereignis) werden
    getrennt gesammelt und am Ende wie im blockierenden Weg mit ``\\n``
    verbunden, nicht roh aneinandergeklebt.

    Review-Lehren aus Aufgabe 5 (``llm.py``), hier von Anfang an eingebaut:
    ein sauberes Verbindungsende OHNE ``message_stop``/``stop_reason`` nach
    dem ersten Stueck ist ein Abbruch, kein Erfolg (sonst kaeme ein
    abgeschnittener Satz als vollstaendige Szene durch); eine werfende
    ``bei_teil``-Senke stoppt nur die Anzeige, nicht das Sammeln; ein
    voruebergehender Fehler (408/429/5xx/529, Transport-/Dekodierfehler) VOR
    dem ersten Stueck schaltet die Prozessflagge nicht ab -- nur ein
    Fehler, der zeigt, dass der Proxy ueberhaupt nicht streamen kann oder
    will, tut das.

    Review-Lehren aus der Pruefung von Aufgabe 6: ein ``message_stop``, das
    ohne jeden ``text_delta`` ankommt (Ablehnung, leere Antwort), ist KEIN
    "kann nicht streamen" -- der Stream hat sauber geantwortet, nur eben mit
    leerem Text, und das meldet ``prosa`` ueber seinen gewohnten
    "keine Textbloecke"-Fehler, nicht ueber die Prozessflagge."""
    import json as _json

    strom_koerper = dict(koerper)
    strom_koerper["stream"] = True
    bloecke: dict[int, list[str]] = {}
    nutzung: dict = {}
    stop = None
    erstes_stueck = False
    fertig_gesehen = False
    sende_an_senke = True
    try:
        with klient.stream("POST", url, headers=headers, json=strom_koerper,
                           timeout=timeout) as antwort:
            if antwort.status_code >= 400:
                if antwort.status_code in _HTTP_VORUEBERGEHEND or antwort.status_code >= 500:
                    raise _StromVoruebergehend(f"HTTP {antwort.status_code}")
                raise _StromNichtVerfuegbar(f"HTTP {antwort.status_code}")
            for zeile in antwort.iter_lines():
                zeile = zeile.strip()
                if not zeile.startswith("data:"):
                    continue
                try:
                    ereignis = _json.loads(zeile[len("data:"):].strip())
                except ValueError as fehler:
                    if erstes_stueck:
                        raise _StromAbbruch("unlesbares Ereignis") from fehler
                    raise _StromNichtVerfuegbar("unlesbare Antwort") from fehler
                typ = ereignis.get("type")
                if typ == "message_start":
                    nutzung.update(
                        (ereignis.get("message") or {}).get("usage") or {})
                elif typ == "content_block_delta":
                    delta = ereignis.get("delta") or {}
                    if delta.get("type") != "text_delta":
                        # thinking_delta und andere Deltatypen gehen nie an
                        # die Gruppe (Denkspur) -- nur text_delta zaehlt.
                        continue
                    erstes_stueck = True
                    index = ereignis.get("index", 0)
                    bloecke.setdefault(index, []).append(delta.get("text") or "")
                    if sende_an_senke:
                        try:
                            bei_teil("\n".join(
                                "".join(stuecke)
                                for _, stuecke in sorted(bloecke.items())
                            ))
                        except Exception:  # noqa: BLE001 -- eine werfende
                            # Anzeige (z. B. gesperrte DB) darf die Antwort
                            # nicht kosten. Nur die Anzeige stoppt, das
                            # Sammeln laeuft weiter.
                            log.exception(
                                "bei_teil-Senke (Claude) fehlgeschlagen -- "
                                "Anzeige gestoppt, der Text wird trotzdem "
                                "weiter gesammelt"
                            )
                            sende_an_senke = False
                elif typ == "message_delta":
                    delta_stop = (ereignis.get("delta") or {}).get("stop_reason")
                    if delta_stop:
                        stop = delta_stop
                        fertig_gesehen = True
                    nutzung.update(ereignis.get("usage") or {})
                elif typ == "message_stop":
                    fertig_gesehen = True
                elif typ == "error":
                    # Anthropics eigenes Ueberlast-/Drosselsignal INNERHALB
                    # einer HTTP-200-Antwort (Review-Fund Aufgabe 6). Nach
                    # dem ersten Stueck ist es immer ein Abbruch -- davor
                    # entscheidet der Fehlertyp zwischen "voruebergehend"
                    # (Drosselung) und "geht grundsaetzlich nicht".
                    fehlertyp = (ereignis.get("error") or {}).get("type")
                    if erstes_stueck:
                        raise _StromAbbruch(
                            f"error-Ereignis nach dem ersten Stueck: {fehlertyp}"
                        )
                    if fehlertyp in _FEHLERTYPEN_VORUEBERGEHEND:
                        raise _StromVoruebergehend(f"error-Ereignis: {fehlertyp}")
                    raise _StromNichtVerfuegbar(f"error-Ereignis: {fehlertyp}")
    except (_StromNichtVerfuegbar, _StromVoruebergehend, _StromAbbruch):
        raise
    except httpx.HTTPStatusError as fehler:
        status = fehler.response.status_code
        if status in _HTTP_VORUEBERGEHEND or status >= 500:
            raise _StromVoruebergehend(f"HTTP {status}") from fehler
        raise _StromNichtVerfuegbar(f"HTTP {status}") from fehler
    except (httpx.TransportError, httpx.DecodingError, httpx.StreamError) as fehler:
        # httpx.DecodingError und httpx.StreamError sind keine
        # httpx.TransportError (eigene Hierarchien), muessen aber genauso
        # behandelt werden -- vor dem ersten Stueck ein voruebergehender
        # Rueckfall, danach ein Abbruch (wie in llm.py, Fix Runde 1, Punkt 5).
        if erstes_stueck:
            raise _StromAbbruch(type(fehler).__name__) from fehler
        raise _StromVoruebergehend(type(fehler).__name__) from fehler
    if fertig_gesehen:
        # Ein ordentliches Abschlusssignal (message_delta mit stop_reason
        # oder message_stop) ist ein Erfolg -- AUCH wenn nie ein einziger
        # text_delta kam (Ablehnung, max_tokens waehrend des Denkens, leere
        # Antwort). Der Proxy HAT gestreamt; dass der Text leer ist, meldet
        # ``prosa`` ueber seinen gewohnten "keine Textbloecke"-Fehler, nicht
        # ueber ein "kann nicht streamen" mit Dauerabschaltung.
        return {
            "content": [
                {"type": "text", "text": "".join(stuecke)}
                for _, stuecke in sorted(bloecke.items())
            ],
            "usage": nutzung,
            "stop_reason": stop,
        }
    if erstes_stueck:
        # Die Verbindung endete sauber, aber ohne Abschlusssignal -- das ist
        # ein Abbruch, kein Erfolg (sonst kaeme ein abgeschnittener Satz als
        # vollstaendige Szene durch).
        raise _StromAbbruch("Verbindung endete ohne message_stop/stop_reason")
    raise _StromNichtVerfuegbar("kein einziges Stueck")


def ist_aktiv(e, conn=None, chat_id: int | None = None) -> bool:
    """True, wenn diese Szene ueber Claude laufen soll: der Betreiber hat es
    erlaubt (IT_SZENE_ANBIETER=claude) UND die Gruppe hat zugestimmt
    (gruppe.szene_usa_bestaetigt_am = 'ja:...'). Ohne conn/chat_id nur die
    Betreiber-Seite -- fuer Tests und Skripte.

    Ist ``workshop.modellwahl_einwilligung_aktiv()`` aus (Padua), entfaellt
    die Einwilligungspruefung komplett: Betreiber-Erlaubnis reicht."""
    erlaubt = (getattr(e, "szene_anbieter", None) or "infomaniak").lower() == "claude"
    if not erlaubt:
        return False
    from interview_theater import workshop

    if not workshop.modellwahl_einwilligung_aktiv():
        return True
    if conn is None or chat_id is None:
        return True
    return repo.szene_usa_stand(conn, chat_id) == "ja"


def angebot_faellig(e, conn, chat_id: int) -> bool:
    """True, wenn der Bot der Gruppe den Wechsel VORSCHLAGEN soll: Betreiber
    erlaubt es, die Gruppe wurde noch nicht gefragt -- und das Angebot steht
    noch nicht im Chat (gemessen 05.09.: es kam zweimal, weil nur der Stand
    'offen' geprueft wurde, nicht ob schon gefragt war).

    Ist ``workshop.modellwahl_einwilligung_aktiv()`` aus (Padua), gibt es
    nichts anzubieten -- die Frage faellt ganz weg."""
    from interview_theater import workshop

    if not workshop.modellwahl_einwilligung_aktiv():
        return False
    erlaubt = (getattr(e, "szene_anbieter", None) or "infomaniak").lower() == "claude"
    if not erlaubt or repo.szene_usa_stand(conn, chat_id) != "offen":
        return False
    g = repo.hole_gruppe(conn, chat_id)
    schon_gefragt = bool(g and "szene_usa_angeboten_am" in g.keys() and g["szene_usa_angeboten_am"])
    return not schon_gefragt


def wartet_auf_antwort(e, conn, chat_id: int) -> bool:
    """True, wenn gefragt wurde und die Gruppe noch nicht geantwortet hat.
    Dann wird keine Szene geschrieben und nicht nochmal gefragt -- nur kurz
    erinnert.

    Ist ``workshop.modellwahl_einwilligung_aktiv()`` aus (Padua), wurde nie
    gefragt -- also wird auch nie gewartet."""
    from interview_theater import workshop

    if not workshop.modellwahl_einwilligung_aktiv():
        return False
    erlaubt = (getattr(e, "szene_anbieter", None) or "infomaniak").lower() == "claude"
    if not erlaubt or repo.szene_usa_stand(conn, chat_id) != "offen":
        return False
    g = repo.hole_gruppe(conn, chat_id)
    return bool(g and "szene_usa_angeboten_am" in g.keys() and g["szene_usa_angeboten_am"])


def warnung_angebracht(e, conn, chat_id: int) -> bool:
    """True, wenn vor einem Claude-Szenenlauf die US-Warnung
    (``szene._TEXT_WARNUNG_USA``) gezeigt werden soll: Claude ist aktiv
    UND die Einwilligungsfrage ist der Grund dafuer. Laeuft Claude ohne
    Einwilligungsfrage (Padua-Profilschalter aus), waere die Warnung eine
    Antwort auf eine Frage, die nie gestellt wurde."""
    from interview_theater import workshop

    if not ist_aktiv(e, conn, chat_id):
        return False
    return workshop.modellwahl_einwilligung_aktiv()


def prosa(conn, e, klient: httpx.Client, chat_id: int | None, system: str,
          nutzer: str, art: str, timeout: float, bei_teil=None,
          wartezeiten: tuple[float, ...] | None = None,
          modell: str | None = None) -> str:
    """Ein Aufruf, ein Text. Bucht in ``aufruf`` mit modus 'C' (Claude), damit
    Dashboard und Kostenrechnung den Weg sehen -- mit 0 CHF, weil Abo.

    ``wartezeiten``/``modell`` (Birk/Robo 07.10.2026, Schaerfung-Karte):
    ohne Angabe gilt wie bisher das Modul-``WARTEZEITEN`` und
    ``e.szene_modell``/``MODELL_VORGABE`` -- ein Aufrufer, der beides nicht
    anfasst, bekommt zeichengleiches Verhalten (E1). Mit Angabe kann EIN
    Aufrufer (z. B. ``schaerfung.py``) eigene Wiederholungen und ein eigenes
    Modell erzwingen, unabhaengig vom Gespraechs-Modell derselben Gruppe.

    ``bei_teil`` (Karte W, Aufgabe 6): eine Senke, die den bisherigen Text
    bekommt, waehrend er entsteht -- Anthropic-SSE statt dem
    chat/completions-Format aus ``llm.py``, aber dieselbe Zusage: ohne
    ``bei_teil`` ist der Anfragekoerper zeichengleich wie vor dieser Karte
    (E1), und mit ihr hinterlaesst ein gestreamter Lauf dieselbe
    ``aufruf``-Zeile wie ein blockierender."""
    # Auch hier, obwohl der Claude-Weg 0 CHF bucht (Abo): ist das Tagesbudget
    # der Gruppe erreicht, antwortet der Bot im Chat nicht mehr -- eine Szene,
    # die trotzdem geschrieben wird, koennte sie gar nicht abnehmen.
    kosten.pruefe(conn, chat_id, e)
    url = getattr(e, "szene_url", None) or URL_VORGABE
    modell = modell or getattr(e, "szene_modell", None) or MODELL_VORGABE
    wartezeiten = WARTEZEITEN if wartezeiten is None else wartezeiten
    koerper = {
        "model": modell,
        "max_tokens": MAX_TOKENS,
        # Modellwahl-Karte (02.10.2026): der Systemprompt aendert sich
        # zwischen zwei Zuegen derselben Gruppe kaum (Basis + Phase +
        # Profil), nur der Nutzertext waechst. ``cache_control`` auf dem
        # System-Block laesst wiederholte Zuege den Infomaniak-Fall nicht
        # mehr wiederholen muessen -- der Proxy (Anthropic) liest den
        # System-Teil aus dem Cache. Ohne Senke (Szene, Buehnenkarte, ...)
        # ist das ein reiner Kostenvorteil; fuer das Gespraech zusaetzlich
        # Latenz. Der Nutzertext-Block (z. B. das Brainstorming-Protokoll)
        # bekommt bewusst KEIN eigenes ``cache_control`` -- er aendert sich
        # jeden Zug (die ausloesende Nachricht steht am Ende), ein zweiter
        # Cache-Block dort haette keinen Treffer und nur Kosten verursacht.
        "system": [
            {"type": "text", "text": system,
             "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [{"role": "user", "content": nutzer}],
    }
    headers = {"content-type": "application/json", "anthropic-version": API_VERSION}
    start = time.monotonic()
    letzter: Exception | None = None
    for versuch in range(len(wartezeiten) + 1):
        try:
            if bei_teil is not None and not _abgeschaltet():
                try:
                    daten = _stream(klient, url, headers, koerper, timeout, bei_teil)
                except _StromNichtVerfuegbar as fehler:
                    _melde_strom_aus(conn, e, chat_id, str(fehler))
                    daten = _blockierend(klient, url, headers, koerper, timeout)
                except _StromVoruebergehend as fehler:
                    log.info(
                        "Claude-Stream voruebergehend nicht verfuegbar "
                        "(art=%s): %s -- dieser Zug laeuft blockierend, "
                        "Flagge bleibt an", art, fehler,
                    )
                    daten = _blockierend(klient, url, headers, koerper, timeout)
                except _StromAbbruch:
                    abbruch = getattr(bei_teil, "abbruch", None)
                    if callable(abbruch):
                        try:
                            abbruch()
                        except Exception:  # noqa: BLE001 -- ein scheiternder
                            # Abbruch-Hook (z. B. ein DB-Schreibfehler beim
                            # Entfernen der vorlaeufigen Blase) darf den
                            # blockierenden Nachversuch nicht verhindern.
                            log.exception(
                                "bei_teil.abbruch() (Claude) fehlgeschlagen"
                            )
                    daten = _blockierend(klient, url, headers, koerper, timeout)
            else:
                daten = _blockierend(klient, url, headers, koerper, timeout)
            teile = [b.get("text") or "" for b in (daten.get("content") or [])
                     if isinstance(b, dict) and b.get("type") == "text"]
            text = "\n".join(teile).strip()
            nutzung = daten.get("usage") or {}
            stop = daten.get("stop_reason")
            _buche(conn, chat_id, e, art, modell, nutzung, stop,
                   time.monotonic() - start, erfolg=bool(text))
            if not text:
                raise ClaudeFehler(
                    f"keine Textbloecke (stop_reason={stop})"
                )
            # **Ein abgeschnittener Text ist ein Fehler, kein Ergebnis**
            # (Birk, 06.09.2026: "Nichts darf stillschweigend abgeschnitten
            # werden."). ``stop_reason=max_tokens`` heisst, dass die Antwort
            # am Ausgabedeckel endete -- mitten im Satz, ohne die
            # Pflichtzeilen, ohne Schluss. Bis dahin wanderte so ein Halbtext
            # als fertige Szene in die Datenbank und in den Chat.
            if stop and stop != "end_turn":
                try:
                    repo.merke_vorfall(
                        conn, chat_id, getattr(e, "bot_name", None),
                        "szene_abgeschnitten",
                        f"stop_reason={stop}, {len(text)} Zeichen, "
                        f"{nutzung.get('output_tokens')} von {MAX_TOKENS} "
                        f"Ausgabe-Token",
                    )
                except Exception:
                    log.exception("Vorfall szene_abgeschnitten nicht geschrieben")
                raise ClaudeFehler(
                    f"Antwort abgeschnitten (stop_reason={stop}) -- "
                    f"kein halber Szenentext"
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
        if versuch < len(wartezeiten):
            time.sleep(wartezeiten[versuch])
    _buche(conn, chat_id, e, art, modell, {}, "abgebrochen", time.monotonic() - start, erfolg=False)
    raise ClaudeFehler(f"Claude-Proxy nach {len(wartezeiten) + 1} Versuchen: {letzter}")


#: Haengt sich an den System-Prompt eines ``schema``-Aufrufs (Modellwahl-
#: Karte, 02.10.2026): das Anthropic-Messages-Format kennt kein natives
#: ``response_format: json_schema`` wie Infomaniak -- die Form steht
#: stattdessen als Anweisung im Prompt, geparst wird mit derselben robusten
#: ``llm.lies_json`` wie beim Kimi-Pfad (erlaubt Praefix-/Suffix-Rauschen,
#: lehnt einen zweiten JSON-Wert als mehrdeutig ab).
_SCHEMA_ANHANG = (
    "\n\nAntworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt, das genau "
    "diesem JSON-Schema entspricht -- kein Text davor oder danach, kein "
    "Markdown-Codeblock, keine Erklaerung:\n{schema}"
)


class _TeilSenke:
    """Entpackt beim Streamen eines Schema-Aufrufs das Feld ``teil_feld`` aus
    dem wachsenden JSON-Praefix (``strom.wert_aus_praefix``) -- dieselbe
    Umpackung wie ``llm.LLM.schema`` fuer den Kimi-Pfad, hier fuer Claude.
    Ohne ``teil_feld`` bekommt die aeussere Senke den rohen Text.

    ``__getattr__`` reicht ``abbruch``/``neu`` an die aeussere Senke durch --
    ``prosa()``/``_stream`` rufen sie per ``getattr(bei_teil, ..., None)``."""

    def __init__(self, aussen, teil_feld: str | None):
        self._aussen = aussen
        self._teil_feld = teil_feld

    def __call__(self, ganz: str) -> None:
        from interview_theater import strom as strom_modul

        wert = (strom_modul.wert_aus_praefix(ganz, self._teil_feld)
                if self._teil_feld else ganz)
        self._aussen(wert)

    def __getattr__(self, name):
        return getattr(self._aussen, name)


def schema(conn, e, klient: httpx.Client, chat_id: int | None, system: str,
          nutzer: str, schema_: dict, art: str, timeout: float,
          bei_teil=None, teil_feld: str | None = None,
          wartezeiten: tuple[float, ...] | None = None,
          modell: str | None = None) -> dict:
    """Ein Schema-Aufruf ueber den Claude-Proxy -- dasselbe Versprechen wie
    ``llm.LLM.schema`` (ein JSON-Objekt nach festem Schema), aber ohne
    natives ``response_format``: die Form geht als Anweisung in den
    System-Prompt (``_SCHEMA_ANHANG``), geparst wird mit ``llm.lies_json``.

    Bucht wie ``prosa`` (``art``, modus 'C', 0 CHF) -- ``prosa`` traegt die
    ganze Mechanik (Retry, Stream, Tagesdeckel, Abschneide-Pruefung); dieses
    hier baut nur den Prompt um und entpackt die Antwort."""
    from interview_theater import llm as llm_modul

    system_mit_schema = system + _SCHEMA_ANHANG.format(
        schema=json.dumps(schema_, ensure_ascii=False)
    )
    innere = _TeilSenke(bei_teil, teil_feld) if bei_teil is not None else None
    text = prosa(conn, e, klient, chat_id, system_mit_schema, nutzer, art,
                timeout, bei_teil=innere, wartezeiten=wartezeiten, modell=modell)
    return llm_modul.lies_json(text)


def _buche(conn, chat_id, e, art, modell, nutzung, finish, dauer_s, erfolg):
    try:
        ein = int(nutzung.get("input_tokens") or 0)
        repo.merke_aufruf(
            conn, chat_id, art, modus="C", geschaetzte_token=ein,
            tatsaechliche_token=ein, antwort_token=int(nutzung.get("output_tokens") or 0),
            finish_reason=finish, dauer_ms=int(dauer_s * 1000), erfolg=1 if erfolg else 0,
            modell=modell,
            # 0 CHF, weil Abonnement -- der Wert steht in kosten.py an genau
            # einer Stelle, damit aus dem Abo eine Abrechnung werden kann,
            # ohne dass jemand suchen muss. ``modell`` steht trotzdem in der
            # Zeile: das Dashboard soll den Weg sehen.
            kosten_chf=kosten.CLAUDE_CHF_JE_AUFRUF,
            # Modellwahl-Karte: die Cache-Zahlen aus der Anthropic-``usage``,
            # falls der Proxy sie liefert (ANNAHME, siehe Report -- nicht
            # gegen den echten Proxy gemessen). ``None`` bei einem blockierenden
            # Aufruf ohne Cache-Treffer ist keine Null, sondern "unbekannt".
            cache_read_token=nutzung.get("cache_read_input_tokens"),
            cache_creation_token=nutzung.get("cache_creation_input_tokens"),
        )
    except Exception:  # noqa: BLE001 -- Buchung darf den Aufruf nie mitreissen
        log.exception("Aufruf-Buchung (Claude) fehlgeschlagen")

"""Der optionale Zusatz nach "Ja, speichern" (Karte t_c5d68218, 06.10.2026).

Nach einem Speichern bekommt die Gruppe sofort, deterministisch, die
Bestaetigungsfrage (``knoepfe.texte.T._TEXT_NACH_SPEICHERN_FRAGE`` --
gesendet von ``knoepfe.basis``/``knoepfe.szenen``, nicht hier). Dieses Modul
liefert NUR den optionalen Zusatz dazu -- einen Verbesserungsvorschlag oder
eine kritische Rueckfrage, und auch den nur, wenn das Modell im
vorliegenden Material wirklich einen Grund findet (Sentinel ``NICHTS``, wie
``buehnenkarte.py``). Kein Zwang: ein leeres oder ``NICHTS``-Ergebnis heisst,
es kommt gar keine zweite Nachricht -- nie ein halluzinierter Zusatz.

Derselbe Modellpfad wie ``buehnenkarte.erzeuge`` (Claude mit Einwilligung,
sonst Infomaniak ueber ``llm.LLM.prosa``), derselbe stille Fehlschlag mit
Vorfall fuers Dashboard. ``starte()`` laeuft im eigenen Thread, nie im
Knopf-Handler (Zusage 2) -- die Bestaetigung ist zu diesem Zeitpunkt schon
raus, ein Fehlschlag hier bleibt deshalb fuer die Gruppe folgenlos."""

import logging
import threading

import httpx

from interview_theater import anweisungen, repo, sprache, szene_claude

log = logging.getLogger(__name__)

#: Die Sentinel-Antwort fuer "kein Zusatz jetzt" -- derselbe Code-Vergleich
#: wie ``buehnenkarte.NICHTS``, kein Text, den die Gruppe je sieht.
NICHTS = "NICHTS"

#: Knapp: ein Zusatz ist hoechstens ein paar Saetze, kein Szenenlauf.
TIMEOUT_S = 60.0
MAX_TOKENS = 1000

_UEBERSCHRIFT_GESPEICHERT = "Gerade gespeichert:"
_ZEILE_FELD = "{feld}: {wert}"
_UEBERSCHRIFT_STUECKKARTE = "Stueckkarte:"
_TEXT_NOCH_OFFEN = "(noch offen)"
_ZEILE_BEGRIFFE = "Begriffe: {wert}"

#: Beschriftung der drei Felder aus ``repo.stueckkarte_felder`` -- dieselben
#: deutschen Schluessel wie in ``buehnenkarte.FELD_BESCHRIFTUNG``.
FELD_BESCHRIFTUNG = {
    "Setting": "Setting",
    "Figuren": "Figuren",
    "Geschichte": "Geschichte",
}

T = sprache.Texte(__name__)

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Die Sperre des Zusatz-Laufs dieser Gruppe -- Get-or-create unter
    einem Meta-Lock (``sprechweise._sperre_fuer`` ist dasselbe Muster)."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def _stueckkarte_text(conn, chat_id: int) -> str:
    zeilen = []
    beschriftung = T.FELD_BESCHRIFTUNG
    for name, wert in repo.stueckkarte_felder(conn, chat_id):
        name = beschriftung.get(name, name)
        zeilen.append(f"{name}: {wert or T._TEXT_NOCH_OFFEN}")
    return "\n".join(zeilen)


def _nutzertext(conn, chat_id: int, feld_bezeichnung: str, wert: str) -> str:
    teile = [
        f"{T._UEBERSCHRIFT_GESPEICHERT}\n"
        + T._ZEILE_FELD.format(feld=feld_bezeichnung, wert=wert)
    ]
    stueckkarte = _stueckkarte_text(conn, chat_id)
    if stueckkarte:
        teile.append(f"{T._UEBERSCHRIFT_STUECKKARTE}\n{stueckkarte}")
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is not None and stand["begriffe"]:
        teile.append(T._ZEILE_BEGRIFFE.format(wert=stand["begriffe"]))
    return "\n\n".join(teile)


def erzeuge(conn, e, klm, chat_id: int, feld_bezeichnung: str,
           wert: str) -> tuple[str | None, str]:
    """Erzeugt den optionalen Zusatz. Liefert ``(text, modell)``, oder
    ``(None, modell)``, wenn das Modell ``NICHTS`` antwortete oder der
    Aufruf scheiterte.

    Ein Scheitern bleibt fuer die Gruppe unsichtbar (wie bei
    ``buehnenkarte.erzeuge``): die Bestaetigung steht schon, ein Zusatz ist
    eine Zugabe -- dafuer ein Vorfall fuers Dashboard."""
    system = anweisungen.hole("nachspeichern")
    nutzer = _nutzertext(conn, chat_id, feld_bezeichnung, wert)
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    modell = "claude" if ueber_claude else "infomaniak"
    try:
        if ueber_claude:
            klient = getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S)
            antwort = szene_claude.prosa(
                conn, e, klient, chat_id, system, nutzer, "nachspeichern",
                timeout=TIMEOUT_S,
            )
        else:
            antwort = klm.prosa(
                chat_id, system, nutzer, "nachspeichern",
                max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
            )
    except Exception:
        log.exception("Nachspeichern-Zusatz fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "nachspeichern_fehlgeschlagen", f"modell={modell}",
            )
        except Exception:
            log.exception("Vorfall nachspeichern_fehlgeschlagen nicht geschrieben")
        return None, modell

    text = (antwort or "").strip()
    if not text or text.upper() == NICHTS:
        return None, modell
    return text, modell


def _lauf(conn, tg, klm, e, chat_id: int, feld_bezeichnung: str, wert: str,
          sperre: threading.Lock) -> None:
    try:
        text, _modell = erzeuge(conn, e, klm, chat_id, feld_bezeichnung, wert)
        if text:
            tg.sende(chat_id, text)
    except Exception:
        log.exception("Nachspeichern-Zusatz-Anzeige gescheitert, chat_id=%s", chat_id)
    finally:
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, feld_bezeichnung: str,
          wert: str) -> threading.Thread | None:
    """Eigener Thread fuer den optionalen Zusatz -- die Bestaetigung selbst
    ist zu diesem Zeitpunkt schon raus (Zusage 2: kein Modellaufruf im
    Knopf-Handler). ``None`` ohne Sprachmodell, oder wenn fuer diese Gruppe
    schon ein Lauf geht."""
    if klm is None:
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    try:
        faden = threading.Thread(
            target=_lauf,
            args=(conn, tg, klm, e, chat_id, feld_bezeichnung, wert, sperre),
            daemon=True,
        )
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden

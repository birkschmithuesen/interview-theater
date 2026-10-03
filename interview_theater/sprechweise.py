"""Die Sprechweise je Figur vor der Buehnenfassung (Padua Phasen TEIL 2,
Task 9, Phase 7 Schritt 2).

Birk: "Vor der ersten Uebertragung bekommen alle Figuren automatisch eine
Sprechweise (aus figur.sprachstil/Interviews, sonst abgeleitet). Alle in
EINER Nachricht, je Figur eine Zeile, abnicken mit 'Yes, save' / 'No, change
it again', Aenderungen per Chat wirken. Erst dann weiter."

**Ein Schema-Aufruf** (gemma, wie ``entwurf.generiere_uebersicht``), flach
wie ueberall: eine Liste von Strings ``"Name: eine Zeile"``. Er bekommt jede
Figur mit Beschreibung, gewaehltem Stil, Sprachprofil und gepruefte Zitate;
antworten muss er nur fuer die Figuren OHNE ``sprachstil``. Geschrieben wird
auch nur dort -- ein Stil, den die Gruppe gewaehlt hat, ueberschreibt kein
Modell (``repo.setze_figur_sprachstil``, geprueft zur Schreibzeit).

**Die Anweisung ist eine Modul-Konstante**, keine neue Prompt-Datei: eine
neue deutsche ``.md`` braucht einen Abschnitt im Dortmund-Schnappschuss. Die
englische Fassung steht in ``sprachen/en/texte.toml``.

**Eigenes Sperren-Register mit Meta-Lock** wie ``entwurf._sperre_fuer``
("Ein Sperren-Register je Nebenlaeufigkeit", AGENTS.md). Kein SQL hier, kein
Modellaufruf ausserhalb des Threads (Zusage 2: ``starte`` wird aus einem
Knopf-Handler gerufen).
"""

from __future__ import annotations

import logging
import threading

from interview_theater import modellwahl, repo, szene_claude

log = logging.getLogger(__name__)

ART = "sprechweise"
VORFALL_FEHLGESCHLAGEN = "sprechweise_fehlgeschlagen"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sprechweisen"],
    "properties": {
        "sprechweisen": {"type": "array", "items": {"type": "string"}},
    },
}

#: Die Systemanweisung des Aufrufs (deutsch; englisch in ``texte.toml``).
ANWEISUNG = (
    "Du bereitest die Buehnenfassung eines Stuecks vor. Gib jeder Figur, "
    "die unten als \"braucht eine Sprechweise\" markiert ist, genau EINE "
    "Zeile, wie sie spricht: Satzlaenge, Tempo, Wortwahl, Eigenheiten -- "
    "so konkret, dass ein Schauspieler es spielen kann. Stuetze dich auf "
    "Sprachprofil und Zitate, wenn es sie gibt, sonst auf die Beschreibung. "
    "Figuren mit vorhandener Sprechweise sind nur zur Abgrenzung genannt: "
    "jede Figur soll anders klingen als die anderen. Antworte als Liste von "
    "Zeilen der Form \"Name: Sprechweise\", eine je Figur, die eine braucht, "
    "mit dem Namen genau wie unten."
)
_ZEILE_FIGUR = "- {name}"
_ZEILE_BESCHREIBUNG = "  Beschreibung: {text}"
_ZEILE_STIL = "  Sprechweise (steht schon): {text}"
_ZEILE_PROFIL = "  Sprachprofil aus dem Interview: {text}"
_ZEILE_ZITAT = "  Zitat: \"{text}\""
_ZEILE_BRAUCHT = "  braucht eine Sprechweise"
_KOPF_FIGUREN = "Figuren:"

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Die Sperre des Sprechweisen-Laufs dieser Gruppe -- Get-or-create
    unter einem Meta-Lock (sonst TOCTOU, siehe ``entwurf._sperre_fuer``)."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def fehlende(conn, chat_id: int) -> list:
    """Die Figuren der Gruppe ohne ``sprachstil``, in Entstehungsreihenfolge."""
    return [f for f in repo.figuren(conn, chat_id) if not _gesetzt(f["sprachstil"])]


def baue_nutzertext(conn, chat_id: int) -> str:
    """Je Figur Name, Beschreibung, vorhandener Stil, Sprachprofil und
    gepruefte Zitate; die ohne Stil sind als "braucht eine Sprechweise"
    markiert."""
    zeilen = [T._KOPF_FIGUREN]
    for figur in repo.figuren(conn, chat_id):
        zeilen.append(T._ZEILE_FIGUR.format(name=figur["name"]))
        if _gesetzt(figur["beschreibung"]):
            zeilen.append(T._ZEILE_BESCHREIBUNG.format(text=figur["beschreibung"].strip()))
        if _gesetzt(figur["sprachstil"]):
            zeilen.append(T._ZEILE_STIL.format(text=figur["sprachstil"].strip()))
        else:
            zeilen.append(T._ZEILE_BRAUCHT)
        if _gesetzt(figur["sprachprofil"]):
            zeilen.append(T._ZEILE_PROFIL.format(text=figur["sprachprofil"].strip()))
        for satz in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
            if satz.strip():
                zeilen.append(T._ZEILE_ZITAT.format(text=satz.strip()))
    return "\n".join(zeilen)


def zerlege(antwort: dict) -> dict[str, str]:
    """``{"sprechweisen": ["Mira: kurz", ...]}`` -> ``{"mira": "kurz"}``
    (Schluessel kleingeschrieben). Zeilen ohne Doppelpunkt oder ohne Text
    fallen heraus; ein fuehrender Spiegelstrich ist erlaubt."""
    ergebnis: dict[str, str] = {}
    for zeile in (antwort or {}).get("sprechweisen") or []:
        name, trenner, text = str(zeile).strip().lstrip("-*• ").partition(":")
        if trenner and name.strip() and text.strip():
            ergebnis.setdefault(name.strip().lower(), text.strip())
    return ergebnis


def _schreibe(conn, chat_id: int, sprechweisen: dict[str, str]) -> int:
    """Nur fuer Figuren, die JETZT noch keinen Stil haben -- die Gruppe kann
    waehrend des Laufs im Chat einen gesetzt haben."""
    geschrieben = 0
    for figur in fehlende(conn, chat_id):
        text = sprechweisen.get(figur["name"].strip().lower())
        if text:
            repo.setze_figur_sprachstil(conn, figur["id"], text)
            geschrieben += 1
    return geschrieben


#: Eine Zeile der Notiert-Meldung je gesetzter Sprechweise
#: (Erkenner-Art ``sprechweise_setzen``, Task 10).
_ZEILE_GESETZT = "Sprechweise {name}: {text}"


def wende_an(conn, chat_id: int, wert: str) -> list[str]:
    """Der Schreibpfad der Erkenner-Art ``sprechweise_setzen`` (Padua Phasen
    TEIL 2, Task 10): ``"Name: text"``, mehrere mit ``|`` getrennt. Schreibt
    ``figur.sprachstil`` fuer jede Figur, die es gibt -- die Gruppe hat sie
    genannt, also ueberschreibt sie auch einen schon gesetzten Stil (anders
    als ``_schreibe``, das nur fuer Figuren ohne Stil schreibt: dort spricht
    ein Modell). Liefert je wirklich geaenderter Figur eine Zeile."""
    zeilen: list[str] = []
    for teil in (wert or "").split("|"):
        name, trenner, text = teil.strip().lstrip("-*• ").partition(":")
        text = " ".join(text.split())
        if not trenner or not name.strip() or not text:
            continue
        figur = repo.hole_figur(conn, chat_id, name.strip())
        if figur is None or (figur["sprachstil"] or "").strip() == text:
            continue
        repo.setze_figur_sprachstil(conn, figur["id"], text)
        zeilen.append(T._ZEILE_GESETZT.format(name=figur["name"], text=text))
    return zeilen


def _lauf(conn, tg, klm, e, chat_id: int, sperre: threading.Lock) -> None:
    from interview_theater import arbeitszeilen, knoepfe

    try:
        if fehlende(conn, chat_id):
            zeilen = arbeitszeilen.sichtbar(tg, chat_id, ART)
            try:
                antwort = modellwahl.aufruf_schema(
                    conn, klm, e, chat_id, T.ANWEISUNG,
                    baue_nutzertext(conn, chat_id), SCHEMA, ART,
                    ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
                    modell=e.erkenner_modell,
                )
                _schreibe(conn, chat_id, zerlege(antwort))
            except Exception:
                log.exception("Sprechweisen fehlgeschlagen, chat_id=%s", chat_id)
                try:
                    repo.merke_vorfall(
                        conn, chat_id, getattr(e, "bot_name", None),
                        VORFALL_FEHLGESCHLAGEN, "Sprechweisen fehlgeschlagen",
                    )
                except Exception:
                    log.exception("Vorfall nicht schreibbar, chat_id=%s", chat_id)
                from interview_theater import kosten

                try:
                    kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
                except Exception:
                    log.exception("Pausenmeldung gescheitert, chat_id=%s", chat_id)
            finally:
                zeilen.stoppe()
        # Auch nach einem Fehlschlag: die Liste steht, die offenen Figuren
        # sind markiert, und die Gruppe kann sie im Chat setzen -- Stille
        # waere die schlechtere Antwort.
        knoepfe.biete_sprechweisen(conn, tg, e, chat_id)
    except Exception:
        log.exception("Sprechweisen-Anzeige gescheitert, chat_id=%s", chat_id)
    finally:
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int) -> threading.Thread | None:
    """Eigener Thread unter der Sperre dieser Gruppe; ``None``, wenn schon
    ein Lauf geht -- oder wenn eine Figur einen Modellaufruf braucht und es
    kein Sprachmodell gibt."""
    if klm is None and fehlende(conn, chat_id):
        log.error("Sprechweisen ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    try:
        faden = threading.Thread(
            target=_lauf, args=(conn, tg, klm, e, chat_id, sperre), daemon=True,
        )
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

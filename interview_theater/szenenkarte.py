"""Die Szenenkarten von Phase 6 (Padua-Phasenumbau, Birk, Live-Workshop
07.10.2026 ~18:12, Profilschalter ``[karten] aktiv``,
``workshop.szenenkarten_aktiv``).

Phase 5 waehlt nur noch Interviews aus; Phase 6 macht daraus EINE Karte je
Szene bzw. Moment -- auf einen Blick, statt Prosa:

* ``typ``: ``description`` (Ablauf beschrieben) · ``spoken`` (Sprechtext) ·
  ``instructions`` (Handlungsanweisungen) · ``moment`` (Moment im Raum);
* ``worum`` (1 Satz) · ``ort`` · ``wer`` · ``punkte`` (3-6, was passiert);
* ``zitate`` -- hoechstens 5 der von der Gruppe uebernommenen Stellen, IMMER im
  Originalwortlaut aus der Datenbank (das Modell waehlt nur Nummern) mit
  Interviewnummer;
* ``fragen`` -- offene Fragen an die Gruppe.

Eine Karte nach der anderen ("one scene at a time"): die erste Szene ohne
``karte_bestaetigt_am`` ist dran. "Yes, save" nimmt sie ab, "No, change" +
Textnachricht schreibt sie mit der Notiz neu. Nach der letzten Karte laeuft
die Gesamtpruefung einmal ueber alle Karten (``gesamtpruefung``), danach das
Angebot "Weiter zu Phase 7".

Die Knopf- und Chatwege bleiben die von ``ueberarbeitung`` (``weiter_6``,
``bestaetige_szene_6``, ``ueberarbeite``, ``nimm_ab``) -- sie verzweigen
unter dem Schalter hierher. Material aus Phase 5 geht vollstaendig ein und
wird nie geloescht: uebernommene Stellen, Kurzform (``szenenkern``),
Phase-5-Gespraech, Logline/Uebersicht, eine schon geschriebene Prosa.

Kein Modellaufruf im Aufrufer-Thread (Zusage 2): ``starte`` gibt an einen
eigenen Thread ab."""

from __future__ import annotations

import json
import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, szene_claude, workshop

log = logging.getLogger(__name__)

ART = "szenenkarte"
PHASE = 6
TYPEN = ("description", "spoken", "instructions", "moment")
#: Der Modus eines Moments (G3: Orts-Partitur im Script-Tab).
MODI = ("microphone", "one_to_one", "collective", "none")
PUNKTE_MAX = 6
ZITATE_MAX = 5
FRAGEN_MAX = 3
ZEICHEN = 120
#: So viel Prosa (G1 Szene 1) geht hoechstens als Material mit.
PROSA_ZEICHEN = 6000

SCHEMA = {
    "type": "object",
    "properties": {
        "typ": {"type": "string", "enum": list(TYPEN),
                "description": "description = the course of action is described; "
                               "spoken = a spoken text will be written; instructions = "
                               "instructions for the performers (social experiment, "
                               "film); moment = a moment in the room (immersive)."},
        "modus": {"type": "string", "enum": list(MODI),
                  "description": "Only for typ moment: where the attention is -- "
                                 "microphone, one_to_one (whispered 1:1) or collective "
                                 "(everyone together); otherwise none."},
        "worum": {"type": "string", "description": "One sentence: what this scene is about."},
        "ort": {"type": "string", "description": "Where it happens (place / spot in the room), short."},
        "wer": {"type": "string", "description": "Who is in it, short."},
        "punkte": {"type": "array", "items": {"type": "string"},
                   "description": "3 to 6 short points: what happens, in order. "
                                  "Each point about one line, at most 120 characters."},
        "zitate": {"type": "array", "items": {"type": "integer"},
                   "description": "Numbers of at most 5 interview passages from the "
                                  "list that this scene uses, strongest first."},
        "questions": {"type": "array", "items": {"type": "string"},
                   "description": "0 to 3 open questions the group still has to decide."},
    },
    "required": ["typ", "modus", "worum", "ort", "wer", "punkte", "zitate", "questions"],
    "additionalProperties": False,
}


def aktiv() -> bool:
    return workshop.szenenkarten_aktiv()


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _szenen(conn, chat_id: int) -> list:
    return sorted(
        (s for s in repo.hole_szenen(conn, chat_id)
         if s["nummer"] is not None and not s["entfernt_am"]),
        key=lambda s: s["nummer"],
    )


def karte_von(szene) -> dict | None:
    """Die gespeicherte Karte als Dict, oder ``None``."""
    try:
        roh = szene["karte"]
    except (IndexError, KeyError):
        return None
    if not _gesetzt(roh):
        return None
    try:
        karte = json.loads(roh)
    except ValueError:
        return None
    return karte if isinstance(karte, dict) else None


def aktuelle_nummer(conn, chat_id: int) -> int | None:
    """Die erste Szene ohne abgenommene Karte."""
    for s in _szenen(conn, chat_id):
        if not _gesetzt(s["karte_bestaetigt_am"]):
            return s["nummer"]
    return None


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    return next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)


# ---------------------------------------------------------------------------
# Der Modellaufruf
# ---------------------------------------------------------------------------


def baue_nutzertext(conn, chat_id: int, szene, notiz: str | None = None) -> str:
    """Alles, was die Gruppe bis Phase 5 fuer diese Szene entschieden hat --
    und die nummerierte Liste der uebernommenen Stellen zur Wahl."""
    from interview_theater import hintergrund, szenenkern

    # Der Hintergrund kommt aus EINER Funktion (Andockstelle der
    # Phasen-Summary, Birk 07.10.2026 ~19:40).
    zeilen: list[str] = []
    hinten = hintergrund.hintergrund_fuer_prompt(conn, chat_id)
    if hinten:
        zeilen.append(hinten)
    alle = [f"{s['nummer']}. {s['titel'] or ''}".strip() for s in _szenen(conn, chat_id)]
    zeilen.append(T._KOPF_ALLE_SZENEN + "\n" + "\n".join(alle))

    teile = [T._KOPF_DIESE.format(nummer=szene["nummer"], titel=szene["titel"] or "")]
    beschreibung = szenenkern.gruppenbeschreibung(conn, chat_id, szene)
    if beschreibung:
        teile.append(T._KOPF_BESCHREIBUNG + " " + beschreibung)
    if _gesetzt(szene["ort"]):
        teile.append(T._KOPF_ORT + " " + szene["ort"].strip())
    namen = [f["name"] for f in repo.szene_figuren(conn, szene["id"])]
    if namen:
        teile.append(T._KOPF_WER + " " + ", ".join(namen))
    for p in szenenkern.kern_punkte(szene):
        teile.append(f"- {p}")
    zeilen.append("\n".join(teile))
    prosa = (szene["prosa"] or "").strip()
    if prosa:
        zeilen.append(T._KOPF_PROSA + "\n" + prosa[:PROSA_ZEICHEN])
    alte = karte_von(szene)
    if alte and notiz:
        zeilen.append(T._KOPF_ALTE_KARTE + "\n" + karte_text(alte, szene))
    if notiz:
        zeilen.append(T._KOPF_NOTIZ + "\n" + notiz.strip())
    liste = [T._KOPF_LISTE]
    for n, (zitat, interview) in enumerate(szenenkern._kandidaten(conn, chat_id, szene), start=1):
        liste.append(f"[{n}] {szenenkern.zitatzeile(zitat[:szenenkern.ZITAT_ZEICHEN_PROMPT], interview)}")
    if len(liste) == 1:
        liste.append(T._KEINE_STELLEN)
    zeilen.append("\n".join(liste))
    return "\n\n".join(zeilen)


def _kappe(text, grenze: int = ZEICHEN) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= grenze:
        return text
    anhang = " …"
    return text[:grenze - len(anhang)].rsplit(" ", 1)[0].rstrip(" ,;:-") + anhang


def erzeuge(conn, klm, e, chat_id: int, nummer: int, notiz: str | None = None) -> dict | None:
    """Der EINE Schema-Aufruf je Karte. Speichert und liefert die Karte,
    oder ``None`` bei jedem Fehler (Vorfall ``szenenkarte_fehler``)."""
    from interview_theater import szenenkern

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return None
    kandidaten = szenenkern._kandidaten(conn, chat_id, szene)
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id,
            system=anweisungen.hole(ART),
            nutzer=baue_nutzertext(conn, chat_id, szene, notiz),
            schema=SCHEMA, art=ART,
            ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
        )
        punkte = [_kappe(p) for p in (ergebnis.get("punkte") or []) if str(p).strip()]
        if not punkte or not str(ergebnis.get("worum") or "").strip():
            raise ValueError("Karte ohne Worum oder ohne Punkte")
        gewaehlt: list[int] = []
        for n in ergebnis.get("zitate") or []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(kandidaten) and n not in gewaehlt:
                gewaehlt.append(n)
        typ = str(ergebnis.get("typ") or "").strip().lower()
        modus = str(ergebnis.get("modus") or "").strip().lower()
        karte = {
            "typ": typ if typ in TYPEN else "description",
            "modus": modus if modus in MODI and typ == "moment" else "none",
            "worum": _kappe(ergebnis.get("worum")),
            "ort": _kappe(ergebnis.get("ort"), 160),
            "wer": _kappe(ergebnis.get("wer"), 160),
            "punkte": punkte[:PUNKTE_MAX],
            "zitate": [
                {"zitat": kandidaten[n - 1][0], "interview": kandidaten[n - 1][1]}
                for n in gewaehlt[:ZITATE_MAX]
            ],
            "fragen": [_kappe(f) for f in (ergebnis.get("questions") or [])
                       if str(f).strip()][:FRAGEN_MAX],
        }
    except Exception:
        log.exception("Szenenkarte fehlgeschlagen, chat_id=%s, nummer=%s", chat_id, nummer)
        try:
            repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                               "szenenkarte_fehler", f"Szene {nummer}: Karte nicht erzeugt")
        except Exception:
            log.exception("Vorfall szenenkarte_fehler nicht geschrieben")
        return None
    repo.setze_szenenkarte(conn, szene["id"], json.dumps(karte, ensure_ascii=False))
    return karte


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------


def karte_text(karte: dict, szene) -> str:
    """Die Karte als Chatnachricht (Markdown wie im Web-Chat)."""
    titel = (szene["titel"] or "").strip()
    kopf = T_IT._KARTE_KOPF.format(nummer=szene["nummer"], titel=titel).rstrip(" —")
    zeilen = [f"**{kopf}** · *{T.TYP_BESCHRIFTUNG.get(karte.get('typ'), karte.get('typ') or '')}*"]
    if karte.get("worum"):
        zeilen.append(karte["worum"])
    if karte.get("ort"):
        zeilen.append(f"**{T_IT._ZEILE_ORT}** {karte['ort']}")
    if karte.get("wer"):
        zeilen.append(f"**{T_IT._ZEILE_WER}** {karte['wer']}")
    if karte.get("punkte"):
        zeilen.append(f"**{T_IT._ZEILE_PUNKTE}**")
        zeilen += [f"- {p}" for p in karte["punkte"]]
    if karte.get("zitate"):
        zeilen.append(f"**{T_IT._ZEILE_ZITATE}**")
        for z in karte["zitate"]:
            quelle = f" ({z['interview']})" if z.get("interview") else ""
            zeilen.append(f"- *“{z['zitat']}”*{quelle}")
    if karte.get("fragen"):
        zeilen.append(f"**{T_IT._ZEILE_FRAGEN}**")
        zeilen += [f"- {f}" for f in karte["fragen"]]
    return "\n".join(zeilen)


def im_cothinker(conn, chat_id: int) -> bool:
    """Leben die Karten im CoThinker-Tab (Birk 07.10.2026 ~19:25)? Nur fuer
    Web-Gruppen mit CoThinker (``diskussion_aktiv``); Telegram behaelt die
    Karte im Chat."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    kanal = (gruppe["kanal"] if gruppe is not None and "kanal" in gruppe.keys() else None)
    return kanal == "web" and workshop.diskussion_aktiv()


def frage_nach_aenderung(conn, tg, e, chat_id: int, nummer: int) -> None:
    """"No, change" auf der Karte im CoThinker: die naechste Nachricht im
    Chat ist das Feedback (``szenenfolge.erwarte_regienotiz`` -- derselbe
    Weg wie "No, change" unter einem Text, ``ablauf`` gibt sie an
    ``ueberarbeitung.ueberarbeite`` -> ``aendere``)."""
    from interview_theater import szenenfolge

    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_NICHT_DRAN)
        return
    szenenfolge.erwarte_regienotiz(chat_id, nummer)
    _sende(conn, tg, e, chat_id, T_IT._TEXT_FEEDBACK_FRAGE.format(nummer=nummer))


def zeige(conn, tg, e, chat_id: int, nummer: int, *, im_chat: bool = False) -> int | None:
    """Die Karte mit "Yes, save" / "No, change" -- dieselben Knopfarten wie
    unter einem Szenentext, damit Knopf- und Chatweg gleich wirken.

    Im CoThinker-Modus (``im_cothinker``) steht die Karte selbst im
    CoThinker-Tab; der Chat bekommt nur eine Zeile -- AUSSER die Karte ist
    das Ergebnis einer Klaerung im Chat (``im_chat``): dann steht sie dort
    ganz, zur Bestaetigung mit "Yes, save card" / "No, change again" (Birk:
    was im Chat geklaert wurde, wird bestaetigt, nie still gespeichert)."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import basis, szenen as ks

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    if karte is None:
        return None
    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_SZENE_PASST)
    gesamt = len(_szenen(conn, chat_id))
    cothinker = im_cothinker(conn, chat_id)
    if cothinker and not im_chat:
        return _sende(conn, tg, e, chat_id, T_IT._TEXT_IM_COTHINKER.format(
            nummer=nummer, gesamt=gesamt))
    text = karte_text(karte, szene) + "\n\n" + T_IT._TEXT_FRAGE.format(
        nummer=nummer, gesamt=gesamt)
    # Knopf-Beschriftungen bleiben IMMER auf der gewoehnlichen ``T``, nicht
    # ``T_IT`` (Morgen-Auftrag 4: "Knoepfe bleiben EN").
    ja = T._TEXT_KARTE_JA_KNOPF if cothinker else knoepfe.T.TEXT_WEITER_KNOPF
    nein = T._TEXT_KARTE_NOCHMAL_KNOPF if cothinker else knoepfe.T.TEXT_NEIN_AENDERN_KNOPF
    leiste = [
        ks._knopf(conn, chat_id, ja, ks.ART_SZENE_PASST, str(nummer)),
        ks._knopf(conn, chat_id, nein, ks.ART_SZENE_ANDERS, str(nummer)),
    ]
    message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


def _sende(conn, tg, e, chat_id: int, text: str):
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


# ---------------------------------------------------------------------------
# Der Schrittweg
# ---------------------------------------------------------------------------

_SPERREN: dict[int, threading.Lock] = {}
_SPERREN_LOCK = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _SPERREN_LOCK:
        return _SPERREN.setdefault(chat_id, threading.Lock())


def laeuft(chat_id: int) -> bool:
    return _sperre_fuer(chat_id).locked()


def starte(conn, tg, klm, e, chat_id: int, nummer: int,
           notiz: str | None = None) -> threading.Thread | None:
    """Erzeugt (oder ueberarbeitet mit ``notiz``) die Karte ``nummer`` im
    eigenen Thread und zeigt sie danach. ``None``, wenn schon eine Karte
    dieser Gruppe entsteht (dann eine Zeile statt Stille)."""
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_LAEUFT)
        return None
    _sende(conn, tg, e, chat_id, (T_IT._TEXT_AENDERE if notiz else T_IT._TEXT_SCHREIBE).format(
        nummer=nummer))

    def _lauf() -> None:
        karte = None
        try:
            karte = erzeuge(conn, klm, e, chat_id, nummer, notiz)
        finally:
            sperre.release()
        if karte is None:
            _sende(conn, tg, e, chat_id, T_IT._TEXT_FEHLER.format(nummer=nummer))
            return
        zeige(conn, tg, e, chat_id, nummer, im_chat=bool(notiz))

    faden = threading.Thread(target=_lauf, daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


def weiter(conn, tg, klm, e, chat_id: int, *, aus_eintritt: bool = False):
    """Was in Phase 6 als naechstes dran ist: die aktuelle Karte zeigen
    (vorhanden) oder erzeugen (fehlt); sind alle abgenommen, die
    Gesamtpruefung einmal und danach das Angebot Phase 7."""
    from interview_theater import knoepfe

    nummer = aktuelle_nummer(conn, chat_id)
    if nummer is not None:
        szene = _szene_mit_nummer(conn, chat_id, nummer)
        if karte_von(szene) is not None:
            zeige(conn, tg, e, chat_id, nummer)
            return None
        return starte(conn, tg, klm, e, chat_id, nummer)
    if not _szenen(conn, chat_id):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_KEINE_SZENEN)
        return None
    stand = repo.hole_arbeitsstand(conn, chat_id)
    geprueft = bool(stand is not None and _gesetzt(stand["karten_geprueft_am"]))
    if geprueft:
        knoepfe.biete_phase(conn, tg, chat_id, T_IT._TEXT_ALLE_GESPEICHERT, 7)
        return None
    return starte_gesamtpruefung(conn, tg, klm, e, chat_id)


def bestaetige(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" auf einer Karte (Knopf oder Chat)."""
    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_LAEUFT)
        return T_IT._TEXT_LAEUFT
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_NICHT_DRAN)
        return T_IT._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None or karte_von(szene) is None:
        _sende(conn, tg, e, chat_id, T_IT._TEXT_NICHT_DRAN)
        return T_IT._TEXT_NICHT_DRAN
    repo.setze_szenenkarte_bestaetigt(conn, szene["id"])
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          T_IT._JOURNAL_GESPEICHERT.format(nummer=nummer,
                                                        titel=szene["titel"] or "").strip(),
                          quelle="knopf")
    antwort = T_IT._ANTWORT_GESPEICHERT.format(nummer=nummer)
    weiter(conn, tg, klm, e, chat_id)
    return antwort


def aendere(conn, tg, klm, e, chat_id: int, notiz: str, nummer: int | None = None):
    """"No, change" + Textnachricht, oder Rueckmeldung im Chat: die Karte
    (genannte oder aktuelle) neu, mit der Notiz und der alten Karte."""
    n = nummer if nummer is not None else aktuelle_nummer(conn, chat_id)
    if n is None:
        _sende(conn, tg, e, chat_id, T_IT._TEXT_KEIN_ZIEL)
        return None
    return starte(conn, tg, klm, e, chat_id, n, notiz)


# ---------------------------------------------------------------------------
# Gesamtpruefung ueber alle Karten (a2/a6/a9/a11)
# ---------------------------------------------------------------------------


def karten_am_stueck(conn, chat_id: int) -> str:
    teile = []
    for s in _szenen(conn, chat_id):
        karte = karte_von(s)
        if karte is not None:
            teile.append(karte_text(karte, s))
    return "\n\n".join(teile)


def _gesamt(conn, tg, klm, e, chat_id: int, sperre: threading.Lock) -> None:
    from interview_theater import knoepfe

    zeilen: list[str] = []
    try:
        zeilen = pruefe_karten(conn, klm, e, chat_id)
    except Exception:
        log.exception("Gesamtpruefung der Karten gescheitert, chat_id=%s", chat_id)
    finally:
        repo.setze_arbeitsstand(conn, chat_id, "karten_geprueft_am", repo._jetzt())
        sperre.release()
    text = T_IT._TEXT_GESAMT_KOPF
    if zeilen:
        text += "\n" + "\n".join(f"- {z}" for z in zeilen)
    else:
        text += "\n" + T_IT._TEXT_GESAMT_OHNE
    _sende(conn, tg, e, chat_id, text)
    knoepfe.biete_phase(conn, tg, chat_id, T_IT._TEXT_ALLE_GESPEICHERT, 7)


def starte_gesamtpruefung(conn, tg, klm, e, chat_id: int):
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        if klm is None:
            from interview_theater import knoepfe

            knoepfe.biete_phase(conn, tg, chat_id, T_IT._TEXT_ALLE_GESPEICHERT, 7)
        return None
    _sende(conn, tg, e, chat_id, T_IT._TEXT_GESAMT_LAEUFT)
    faden = threading.Thread(target=_gesamt, args=(conn, tg, klm, e, chat_id, sperre),
                             daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


GESAMT_SCHEMA = {
    "type": "object",
    "properties": {
        "befunde": {
            "type": "array", "items": {"type": "string"},
            "description": "At most 5 short findings, each one sentence, each naming "
                           "the scene number it concerns.",
        },
    },
    "required": ["befunde"],
    "additionalProperties": False,
}


def pruefe_karten(conn, klm, e, chat_id: int) -> list[str]:
    """EIN Aufruf ueber alle Karten mit den vier Fragen der Gesamtpruefung
    (a2 Bogen, a6 Material, a9 Ende, a11 Format -- ``prompts/szenenkarte_pruefung.md``).
    Nur Befunde, kein Umschreiben: die Karten bleiben, wie die Gruppe sie
    abgenommen hat."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    format_ = ((stand["format"] if stand is not None else "") or "").strip()
    nutzer = (T._KOPF_FORMAT + "\n" + format_ + "\n\n" if format_ else "") + karten_am_stueck(conn, chat_id)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id,
        system=anweisungen.hole("szenenkarte_pruefung"), nutzer=nutzer,
        schema=GESAMT_SCHEMA, art=ART_PRUEFUNG,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
    )
    return [_kappe(b) for b in (ergebnis.get("befunde") or []) if str(b).strip()][:5]


ART_PRUEFUNG = "szenenkarte_pruefung"

# ---------------------------------------------------------------------------
# Texte (W3: Sprache des Profils; Padua ueberschreibt in sprachen/en)
# ---------------------------------------------------------------------------

_KOPF_FORMAT = "Format:"
_KOPF_ALLE_SZENEN = "Alle Szenen:"
_KOPF_DIESE = "DIESE Karte: Szene {nummer} -- {titel}"
_KOPF_BESCHREIBUNG = "Was die Gruppe beschrieben hat:"
_KOPF_ORT = "Ort:"
_KOPF_WER = "Wer:"
_KOPF_PROSA = "Schon geschriebener Text dieser Szene (nur Material, kein Massstab):"
_KOPF_ALTE_KARTE = "Bisherige Karte:"
_KOPF_NOTIZ = "Was die Gruppe an der Karte geaendert haben will (gilt vor allem anderen):"
_KOPF_LISTE = "Von der Gruppe uebernommene Interviewstellen (nach Nummer waehlen):"
_KEINE_STELLEN = "(keine)"

_KARTE_KOPF = "Szenenkarte {nummer} — {titel}"
TYP_BESCHRIFTUNG = {"description": "Beschreibung", "spoken": "Sprechtext",
                    "instructions": "Handlungsanweisungen", "moment": "Moment"}
_ZEILE_ORT = "Wo:"
_ZEILE_WER = "Wer:"
_ZEILE_PUNKTE = "Was passiert:"
_ZEILE_ZITATE = "Interviewstellen:"
_ZEILE_FRAGEN = "Offene Fragen:"
_TEXT_FRAGE = "Karte {nummer} von {gesamt}. Passt sie so? Sonst sagt mir, was anders sein soll."
_TEXT_SCHREIBE = "Ich baue die Karte fuer Szene {nummer}."
_TEXT_AENDERE = "Ich baue die Karte fuer Szene {nummer} neu."
_TEXT_LAEUFT = "Ich baue gerade noch an einer Karte -- gleich."
_TEXT_FEHLER = "Die Karte fuer Szene {nummer} hat nicht geklappt. Sagt einfach nochmal Bescheid."
_TEXT_NICHT_DRAN = "Diese Karte ist gerade nicht dran -- gespeichert habe ich nichts."
_TEXT_KEIN_ZIEL = "Alle Karten sind gespeichert. Welche Szene wollt ihr aendern?"
_TEXT_KEINE_SZENEN = "Es gibt noch keine Szenen -- legt sie zuerst in der Workbench fest."
_TEXT_ALLE_GESPEICHERT = "Alle Karten sind gespeichert. Weiter zum Stage Script?"
_TEXT_GESAMT_LAEUFT = "Alle Karten stehen. Ich schaue einmal uebers Ganze."
_TEXT_GESAMT_KOPF = "Blick aufs Ganze:"
_TEXT_GESAMT_OHNE = "- Nichts Auffaelliges."
_ANTWORT_GESPEICHERT = "Karte {nummer} gespeichert"
_TEXT_IM_COTHINKER = "Karte {nummer} von {gesamt} steht im CoThinker-Tab."
_TEXT_FEEDBACK_FRAGE = "Was soll an Karte {nummer} anders werden?"
_TEXT_KARTE_JA_KNOPF = "Yes, save card"
_TEXT_KARTE_NOCHMAL_KNOPF = "No, change again"
_JOURNAL_GESPEICHERT = "Szenenkarte {nummer} gespeichert: {titel}"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
#: Morgen-Auftrag 4 (08.10.2026): Kartentexte und Statuszeilen ab Phase 6
#: italienisch (``workshop.p67_italienisch_aktiv``), NIE die beiden
#: Knopf-Beschriftungen oben -- die bleiben auf ``T``.
T_IT = sprache.Texte(__name__, ab_phase67_italienisch=True)

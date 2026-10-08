"""Phase 7 = das Stage Script aus den Szenenkarten (Padua-Phasenumbau, Birk,
Live-Workshop 07.10.2026 ~18:12, Profilschalter ``[karten] aktiv``).

Keine Formwahl, keine Sprechweisen mehr: jede Szene wird -- eine nach der
anderen -- aus ihrer abgenommenen Karte (``szenenkarte.py``) in das Format
der Gruppe geschrieben. Das Format folgt dem Kartentyp:

* ``description`` -- der Ablauf in 5-8 Zeilen (G1 Szene 1 und 3);
* ``spoken`` -- Sprechtext in Abschnitten, ``SPRECHER:``-Zeilen, Interview
  quotes markiert, [Musik-Cues] (G1 Szene 2);
* ``instructions`` -- Thema, Handlungsanweisung je Person, Einstiegssaetze,
  KAMERA, ABBRUCH (G2); dazu EINMAL je Stueck ein Kopf (Versuchsanordnung +
  Rollen mit Charakter, ``arbeitsstand.stage_kopf``);
* ``moment`` -- Ort/Modus (🎤 Mikrofon · 👂 1:1 · 👥 Kollektiv), Wer,
  Wand/Klang, Zitate, Uebergang (G3).

Interview quotes stehen IMMER im Original (``> *Interview quote (N):* "…"``).
Der Text geht nach ``szene.volltext``; mit ``[skript] zweisprachig`` danach
der EN/IT-Spiegel (``skript_uebersetzung.spiegle_text``) nach ``volltext``/
``volltext_it``. Abnahme ueber die vorhandenen Wege (``ueberarbeitung.
weiter_7``/``bestaetige_szene_7``/``ueberarbeite``/``nimm_ab`` verzweigen
hierher); "Yes, save" setzt ``fertig_am``."""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, szene_claude, workshop

log = logging.getLogger(__name__)

ART = "stagescript"
PHASE = 7
#: So viel vom Ende der vorigen Szene geht in den Prompt.
VORHER_ZEICHEN = 900

SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string",
                 "description": "The stage script of this one scene, in the format "
                                "given for its type."},
        "kopf": {"type": "string",
                 "description": "Only when asked for: the head of the whole script "
                                "(setup and roles). Otherwise an empty string."},
    },
    "required": ["text", "kopf"],
    "additionalProperties": False,
}


def aktiv() -> bool:
    return workshop.szenenkarten_aktiv()


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _szenen(conn, chat_id: int) -> list:
    from interview_theater import szenenkarte

    return szenenkarte._szenen(conn, chat_id)


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    return next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)


def aktuelle_nummer(conn, chat_id: int) -> int | None:
    """Die erste Szene ohne abgenommenes Stage Script (``fertig_am``)."""
    for s in _szenen(conn, chat_id):
        if not _gesetzt(s["fertig_am"]):
            return s["nummer"]
    return None


def braucht_kopf(conn, chat_id: int) -> bool:
    """Ein Kopf (Versuchsanordnung + Rollen) gehoert vor ein Skript, das
    UEBERWIEGEND aus Handlungsanweisungen besteht (G2) -- einmal je Stueck.
    Eine einzelne Anweisungsszene (G1: das Ritual) braucht keinen."""
    from interview_theater import szenenkarte

    typen = [(szenenkarte.karte_von(s) or {}).get("typ") for s in _szenen(conn, chat_id)]
    return bool(typen) and sum(t == "instructions" for t in typen) * 2 > len(typen)


def baue_nutzertext(conn, chat_id: int, szene, notiz: str | None = None,
                    mit_kopf: bool = False, ueber_claude: bool = False) -> str:
    from interview_theater import hintergrund, szenenkarte

    stand = repo.hole_arbeitsstand(conn, chat_id)

    def feld(name: str) -> str:
        return ((stand[name] if stand is not None and name in stand.keys() else "") or "").strip()

    # Der Hintergrund kommt aus EINER Funktion -- derselben wie bei den
    # Karten (Andockstelle der Phasen-Summary, Birk 07.10.2026 ~19:40).
    # ``ueber_claude`` geht unveraendert durch (Datenschutz: der
    # Verdichtungen-Block bleibt dem Kimi-Weg vorbehalten, ``hintergrund.py``).
    teile = []
    hinten = hintergrund.hintergrund_fuer_prompt(conn, chat_id, ueber_claude=ueber_claude)
    if hinten:
        teile.append(hinten)
    if feld("stage_kopf") and not mit_kopf:
        teile.append(T._KOPF_STUECKKOPF + "\n" + feld("stage_kopf"))
    alle = []
    for s in _szenen(conn, chat_id):
        karte = szenenkarte.karte_von(s)
        if karte is None or s["nummer"] == szene["nummer"]:
            continue
        alle.append(f"{s['nummer']}. {s['titel'] or ''} -- {karte.get('worum', '')}")
    if alle:
        teile.append(T._KOPF_ANDERE + "\n" + "\n".join(alle))
    vorige = next((s for s in _szenen(conn, chat_id) if s["nummer"] == szene["nummer"] - 1), None)
    vorher = ((vorige["volltext"] if vorige is not None else "") or "").strip()
    if vorher:
        # Das geschriebene Ende der vorigen Szene (Nachtrag Birk 08.10.2026,
        # G3: Szene 5 und 6 projizierten beide die Schlussfrage).
        if len(vorher) > VORHER_ZEICHEN:
            vorher = "… " + vorher[-VORHER_ZEICHEN:].split(" ", 1)[-1]
        teile.append(T._KOPF_VORHER + "\n" + vorher)
    karte = szenenkarte.karte_von(szene) or {}
    teile.append(T._KOPF_KARTE + "\n" + szenenkarte.karte_text(karte, szene))
    typ = karte.get("typ") or "description"
    teile.append(T._KOPF_FORMAT_TYP + "\n" + T.FORMAT_JE_TYP.get(typ, T.FORMAT_JE_TYP["description"]))
    if chat_id in workshop.skript_ohne_zitate_chats():
        teile.append(T._AUFTRAG_OHNE_ZITATE)
    if mit_kopf:
        teile.append(T._AUFTRAG_KOPF)
    alt = (szene["volltext"] or "").strip()
    if notiz and alt:
        teile.append(T._KOPF_BISHER + "\n" + alt)
    if notiz:
        teile.append(T._KOPF_NOTIZ + "\n" + notiz.strip())
    teile.append(T._AUFTRAG.format(nummer=szene["nummer"]))
    return "\n\n".join(teile)


def schreibe(conn, klm, e, chat_id: int, nummer: int, notiz: str | None = None) -> bool:
    """Der Modellaufruf (plus ggf. der Spiegelpass). ``True`` bei Erfolg."""
    from interview_theater import skript_uebersetzung

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    mit_kopf = (braucht_kopf(conn, chat_id)
                and not _gesetzt(stand["stage_kopf"] if stand is not None else None))
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=anweisungen.hole(ART),
            nutzer=baue_nutzertext(conn, chat_id, szene, notiz, mit_kopf, ueber_claude),
            schema=SCHEMA, art=ART, ueber_claude=ueber_claude, timeout=240.0,
        )
        text = (ergebnis.get("text") or "").strip()
        if not text:
            raise ValueError("Stage Script ohne Text")
        kopf = (ergebnis.get("kopf") or "").strip()
    except Exception:
        log.exception("Stage Script fehlgeschlagen, chat_id=%s, nummer=%s", chat_id, nummer)
        try:
            repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                               "stagescript_fehler", f"Szene {nummer}: Stage Script nicht erzeugt")
        except Exception:
            log.exception("Vorfall stagescript_fehler nicht geschrieben")
        return False
    if mit_kopf and kopf:
        kopf_it = None
        if workshop.skript_zweisprachig_aktiv():
            gespiegelt_kopf = skript_uebersetzung.spiegle_text(
                conn, klm, e, chat_id, kopf, ueber_claude=ueber_claude)
            if gespiegelt_kopf is not None:
                kopf, kopf_it = gespiegelt_kopf
        repo.setze_arbeitsstand(conn, chat_id, "stage_kopf", kopf)
        repo.setze_arbeitsstand(conn, chat_id, "stage_kopf_it", kopf_it)
    text_it = None
    if workshop.skript_zweisprachig_aktiv():
        gespiegelt = skript_uebersetzung.spiegle_text(
            conn, klm, e, chat_id, text, ueber_claude=ueber_claude)
        if gespiegelt is not None:
            text, text_it = gespiegelt
    repo.setze_stagescript(conn, szene["id"], text, text_it)
    return True


def _sende(conn, tg, e, chat_id: int, text: str) -> int:
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


def zeige(conn, tg, e, chat_id: int, nummer: int) -> int:
    """Kein Volltext im Chat: der Hinweis aufs Script, "Yes, save" / "No, change"."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import basis, szenen as ks

    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_SZENE_PASST)
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    text = T_IT._TEXT_FERTIG.format(nummer=nummer, titel=(szene["titel"] or "").strip(),
                                 gesamt=len(_szenen(conn, chat_id)))
    leiste = [
        ks._knopf(conn, chat_id, knoepfe.T.TEXT_WEITER_KNOPF, ks.ART_SZENE_PASST, str(nummer)),
        ks._knopf(conn, chat_id, knoepfe.T.TEXT_NEIN_AENDERN_KNOPF, ks.ART_SZENE_ANDERS, str(nummer)),
    ]
    message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


_SPERREN: dict[int, threading.Lock] = {}
_SPERREN_LOCK = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _SPERREN_LOCK:
        return _SPERREN.setdefault(chat_id, threading.Lock())


def laeuft(chat_id: int) -> bool:
    return _sperre_fuer(chat_id).locked()


def starte(conn, tg, klm, e, chat_id: int, nummer: int, notiz: str | None = None):
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_LAEUFT)
        return None
    _sende(conn, tg, e, chat_id, (T_IT._TEXT_AENDERE if notiz else T_IT._TEXT_SCHREIBE).format(
        nummer=nummer))

    def _lauf() -> None:
        ok = False
        try:
            ok = schreibe(conn, klm, e, chat_id, nummer, notiz)
        finally:
            sperre.release()
        if not ok:
            _sende(conn, tg, e, chat_id, T_IT._TEXT_FEHLER.format(nummer=nummer))
            return
        zeige(conn, tg, e, chat_id, nummer)

    faden = threading.Thread(target=_lauf, daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


def weiter(conn, tg, klm, e, chat_id: int, *, aus_eintritt: bool = False):
    """Die aktuelle Szene: Text da -> zeigen, sonst schreiben; alle
    abgenommen -> die Fertig-Zeile."""
    nummer = aktuelle_nummer(conn, chat_id)
    if nummer is None:
        _sende(conn, tg, e, chat_id, T_IT._TEXT_ALLES_FERTIG)
        return None
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if _gesetzt(szene["volltext"]):
        zeige(conn, tg, e, chat_id, nummer)
        return None
    return starte(conn, tg, klm, e, chat_id, nummer)


def bestaetige(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_LAEUFT)
        return T_IT._TEXT_LAEUFT
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if (nummer != aktuelle_nummer(conn, chat_id) or szene is None
            or not _gesetzt(szene["volltext"])):
        _sende(conn, tg, e, chat_id, T_IT._TEXT_NICHT_DRAN)
        return T_IT._TEXT_NICHT_DRAN
    repo.setze_szene_fertig(conn, szene["id"], True)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          T_IT._JOURNAL_GESPEICHERT.format(nummer=nummer,
                                                        titel=szene["titel"] or "").strip(),
                          quelle="knopf")
    antwort = T_IT._ANTWORT_GESPEICHERT.format(nummer=nummer)
    weiter(conn, tg, klm, e, chat_id)
    return antwort


def aendere(conn, tg, klm, e, chat_id: int, notiz: str, nummer: int | None = None):
    n = nummer if nummer is not None else aktuelle_nummer(conn, chat_id)
    if n is None:
        _sende(conn, tg, e, chat_id, T_IT._TEXT_KEIN_ZIEL)
        return None
    return starte(conn, tg, klm, e, chat_id, n, notiz)


# ---------------------------------------------------------------------------
# Texte (W3)
# ---------------------------------------------------------------------------

_KOPF_STUECKKOPF = "Kopf des Skripts (steht schon fest):"
_KOPF_ANDERE = "Die anderen Szenen (nur zur Orientierung):"
_KOPF_VORHER = "So endet die vorige Szene (steht schon -- hier anschliessen, nichts davon wiederholen):"
_KOPF_KARTE = "Die abgenommene Karte DIESER Szene -- sie ist bindend:"
_KOPF_FORMAT_TYP = "So sieht das Skript dieser Szene aus:"
_KOPF_BISHER = "Bisheriges Skript dieser Szene, es soll ueberarbeitet werden:"
_KOPF_NOTIZ = "Was die Gruppe geaendert haben will (gilt vor allem anderen):"
_AUFTRAG_KOPF = (
    "Schreib zusaetzlich in \"kopf\" EINMAL den Kopf des ganzen Skripts: die "
    "Versuchsanordnung (Ziel, Ort, Regeln, Abbruch) und je beteiligter Person "
    "ihre Rolle -- was sie tut, was nie, wann sie eingreift. Rollen und "
    "Eigenschaften NUR aus Uebersicht und Festlegungen der Gruppe; wo die "
    "Gruppe keine genannt hat, keine."
)
_AUFTRAG_OHNE_ZITATE = (
    "Diese Gruppe will KEINE Interviewzitate im Skript (Morgen-Auftrag 1): "
    "keine Zeile \"> *Interview quote (N):* ...\" und kein Zitat mitten im "
    "Absatz -- trag den Inhalt in eigenen Worten."
)
_AUFTRAG = "Schreib jetzt das Stage Script von Szene {nummer}."
FORMAT_JE_TYP = {
    "description": (
        "Der Ablauf in 5 bis 8 kurzen Zeilen: Positionen, Musik/Klang, was "
        "gesagt oder gezeigt wird, der Uebergang zur naechsten Szene. Kein "
        "Sprechtext ausser hoechstens 2-3 Kernsaetzen."
    ),
    "spoken": (
        "Sprechtext in Abschnitten: je Abschnitt eine Ueberschrift (**...**), "
        "dann Zeilen \"NAME: ...\". Interviewstellen woertlich im Original als "
        "eigene Zeile: > *Interview quote (N):* \"...\". Kurze Bruecken der "
        "Performer zwischen den Stimmen, Musik-Cues in [eckigen Klammern]."
    ),
    "instructions": (
        "Fuer diesen Moment: **Thema** (mit Interview quote im Original), "
        "**Handlungsanweisung** je Person (WER TUT WAS), **Einstiegssaetze** "
        "der Eingeweihten (2-4, in der Sprache, in der gespielt wird), "
        "**KAMERA** (Position/Einstellung), **ABBRUCH** (wann und wie)."
    ),
    "moment": (
        "Fuer diesen Moment: **Ort / Modus** (🎤 Mikrofon · 👂 1:1 geflüstert, "
        "Ich-Form · 👥 Kollektiv), **Wer** (Voce 1-5), **Wand/Klang** in einer "
        "Zeile ([VIDEO: ...] als Platzhalter), die Interview quotes im Original "
        "als > *Interview quote (N):* \"...\", **Uebergang** (wohin wandert die "
        "Aufmerksamkeit)."
    ),
}
_TEXT_SCHREIBE = "Ich schreibe das Stage Script fuer Szene {nummer}."
_TEXT_AENDERE = "Ich schreibe das Stage Script fuer Szene {nummer} neu."
_TEXT_LAEUFT = "Ich schreibe gerade noch -- gleich."
_TEXT_FEHLER = "Das Stage Script fuer Szene {nummer} hat nicht geklappt. Sagt einfach nochmal Bescheid."
_TEXT_FERTIG = (
    "Szene {nummer} von {gesamt} ({titel}) steht im Script-Tab. Lest sie dort -- "
    "passt sie so? Sonst sagt mir, was anders sein soll."
)
_TEXT_NICHT_DRAN = "Diese Szene ist gerade nicht dran -- gespeichert habe ich nichts."
_TEXT_KEIN_ZIEL = "Alle Szenen sind gespeichert. Welche wollt ihr aendern?"
_TEXT_ALLES_FERTIG = "Das Stage Script ist fertig. Lest es im Script-Tab."
_ANTWORT_GESPEICHERT = "Szene {nummer} gespeichert"
_JOURNAL_GESPEICHERT = "Stage Script Szene {nummer} gespeichert: {titel}"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
#: Morgen-Auftrag 4 (08.10.2026): die an die Gruppe gesendeten Statuszeilen
#: ab Phase 7 italienisch (``workshop.p67_italienisch_aktiv``) -- der
#: Prompt-Aufbau (``baue_nutzertext``, oben) bleibt auf ``T``: er geht ans
#: Modell, nicht an die Gruppe, und braucht die Umstellung nicht.
T_IT = sprache.Texte(__name__, ab_phase67_italienisch=True)

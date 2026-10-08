"""Phasen-Summary (Karte t_1bc96848, Padua): je Phase ein knappes,
automatisiert erzeugtes Summary nur des BESCHLOSSENEN -- ersetzt in den
Prompts der Folgephasen die Rohdumps aus Chat/Journal/Workbench einer
ABGESCHLOSSENEN Phase (Birk, woertlich sinngemaess: "Nicht den kompletten
Verlauf reindumpen, das verwirrt. Ein ordentliches, automatisiertes Summary
nach jeder Phase.").

**Nur Padua** (``workshop.phasen_summary_aktiv``); Dortmund und das
eingebaute Vorgabeprofil bleiben byte-gleich -- ohne den Schalter ruft
niemand dieses Modul auf.

**Wann es laeuft.** Beim Phasenwechsel -- jeder Aufrufer, der nach einem
erfolgreichen ``phasen.setze`` Zugriff auf ein Sprachmodell hat, ruft
``starte_wenn_aktiv`` mit der gerade VERLASSENEN Phase. Der Lauf selbst geht
in einen eigenen Thread (Zusage 2, AGENTS.md: kein Modellaufruf im
Knopf-/Erkenner-Handler) und ein Fehlschlag bleibt still: kein Summary ist
ein akzeptabler Fehlerfall, kein Absturz, und der Phasenwechsel selbst ist
zu diesem Zeitpunkt schon durch.

**Woraus es entsteht** (``baue_nutzertext``): der Chat (ohne Klarnamen, wie
``szene._chat_text``) und die Journalzeilen ``entschieden``/``verworfen``
seit dem letzten Eintritt in die abgeschlossene Phase, dazu die geltenden
Festlegungen und ein Schnappschuss der Werkbank (Setting, Figuren,
Geschichte, Szenen) -- derselbe Materialkreis wie
``schaerfung._hintergrund_voll_zeilen``, nur fuer GENAU EINE Phase statt des
ganzen bisherigen Verlaufs.

**Was herauskommt** (``erzeuge``/``baue_text``). Ein Schema-Aufruf (Modus A,
Reasoning aus) liefert drei flache Listen -- Entscheidungen, Verworfenes,
offene Punkte --, die zu hoechstens ``MAX_ZEICHEN`` Zeichen zusammengesetzt
werden: 1.500 Zeichen sind rund ein Zehntel des gemessenen Phase-5-Rohdumps
einer Gruppe (16.710 Zeichen woertlicher Chat, ``docs/handoffs/`` zur Karte)
-- genug fuer anderthalb Dutzend kurze Zeilen, wenig genug, um neben dem
laufenden Gespraech nicht selbst wieder zur Wall of Text zu werden.

**Modellwahl wie ``entwurf``/``schaerfung``**: ``modellwahl.aufruf_schema``
mit ``szene_claude.ist_aktiv`` -- Opus nur mit US-Einwilligung UND
Betreiberschalter, sonst der bestehende Kimi-Weg.
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, modellwahl, phasen, repo, szene_claude, workshop

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "phasen_summary"

#: Obergrenze des fertigen Summary-Texts in Zeichen -- Begruendung im
#: Moduldocstring. Harter Deckel (``_kuerze``), kein Zielwert: der Prompt
#: nennt dieselbe Zahl, ein Modell, das sie trotzdem reisst, wird hier
#: gekappt statt verworfen.
MAX_ZEICHEN = 1500

#: Flach wie ueberall (global-constraints.md 'Schema'): drei Listen von
#: Strings statt einer verschachtelten Struktur.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entscheidungen", "discarded", "offene_punkte"],
    "properties": {
        "entscheidungen": {"type": "array", "items": {"type": "string"}},
        "discarded": {"type": "array", "items": {"type": "string"}},
        "offene_punkte": {"type": "array", "items": {"type": "string"}},
    },
}

#: Ein Sperren-Register je (chat_id, phase) -- zwei Laeufe fuer dieselbe
#: Phase derselben Gruppe sollen sich nicht ueberholen; zwei verschiedene
#: Phasen (oder Gruppen) duerfen parallel laufen ("Ein Sperren-Register je
#: Nebenlaeufigkeit", docs/agents/aufbau.md).
_sperren: dict[tuple[int, int], threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int, phase: int) -> threading.Lock:
    schluessel = (chat_id, phase)
    with _sperren_schutz:
        sperre = _sperren.get(schluessel)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[schluessel] = sperre
        return sperre


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("phasen_summary")


#: Wer im Chat-Block spricht -- ohne Klarnamen (wie ``szene._chat_text``).
_SPRECHER_DU = "Du"
_SPRECHER_GRUPPE = "Gruppe"

#: Journalzeilen, die eine reine Phasen-Navigation sind ("Phase 5 ·
#: Prose Draft"), tragen keine Entscheidung ueber den INHALT und bleiben
#: deshalb aussen vor -- sie wuerden das Summary nur mit sich selbst fuellen.
_PHASENZEILE_PRAEFIX = "Phase "


def _feld(stand, name: str) -> str:
    if stand is None or name not in stand.keys():
        return ""
    return (stand[name] or "").strip()


def _chat_zeilen(conn, chat_id: int, seit: str) -> list[str]:
    """Der Chat-Wortlaut seit ``seit`` -- Systemzeilen und Echo faellt heraus
    (``repo.letzte_nachrichten``/``kontext._ist_systemzeile``), wie beim
    Phase-5-Gespraechsblock in ``szene.py``."""
    from interview_theater import kontext

    zeilen = []
    for n in repo.letzte_nachrichten(conn, chat_id, anzahl=kontext._FENSTER_POOL):
        if kontext._ist_systemzeile(n) or (n["gesendet_am"] or "") < seit:
            continue
        text = (n["text"] or "").strip()
        if text:
            zeilen.append(
                f"{_SPRECHER_DU if n['ist_bot'] else _SPRECHER_GRUPPE}: {text}"
            )
    return zeilen


def _journal_zeilen(conn, chat_id: int, seit: str) -> list[str]:
    """Entscheidungen und Verworfenes seit ``seit`` -- ohne die reinen
    Phasen-Navigationszeilen (siehe ``_PHASENZEILE_PRAEFIX``)."""
    return [
        f"- [{e['art']}] {e['text']}"
        for e in repo.journal(conn, chat_id)
        if e["art"] in ("entschieden", "verworfen")
        and (e["erstellt_am"] or "") >= seit
        and not (e["text"] or "").startswith(_PHASENZEILE_PRAEFIX)
    ]


def _workbench_zeilen(conn, chat_id: int) -> list[str]:
    """Ein Schnappschuss der Werkbank: Setting, Geschichte, Figuren, Szenen,
    geltende Festlegungen -- derselbe Materialkreis wie
    ``schaerfung._erfundenes_zeilen``/``entwurf._voll_bloecke``, hier ohne
    Modellaufruf, nur als Eingabe fuer das Summary dieses Moduls."""
    zeilen: list[str] = []
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is not None:
        if (stand["rahmen"] or "").strip():
            zeilen.append(f"Setting: {stand['rahmen'].strip()}")
        if "geschichte" in stand.keys() and (stand["geschichte"] or "").strip():
            zeilen.append(f"Story: {stand['geschichte'].strip()}")
    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append("Characters: " + ", ".join(f["name"] for f in figuren))
    szenen = repo.hole_szenen(conn, chat_id)
    if szenen:
        teile = []
        for z in sorted(szenen, key=lambda z: z["nummer"] or 0):
            was = (z["was_passiert"] or z["kurzbeschreibung"] or "").strip()
            kopf = f"{z['nummer']}. {z['titel'] or ''}".strip()
            teile.append(f"{kopf} -- {was}" if was else kopf)
        zeilen.append("Scenes:\n" + "\n".join(teile))
    fest = [
        repo.festlegungszeile(f["bereich"], f["bezug"], f["text"])
        for f in repo.festlegungen(conn, chat_id)
    ]
    if fest:
        zeilen.append("Agreed by the group:\n" + "\n".join(f"- {t}" for t in fest))
    return zeilen


#: Phasen 1-3 haben anderes Material als der Rest (Birk 08.10.2026: "das
#: Material der P1-3 ist anders -- Begriffe, Fragen/Leitfaden, Interviews").
#: Statt Chat+Werkbank (die fuer diese Phasen vor allem Rohchat waeren, bis
#: zu 142.000 Zeichen gemessen an den Live-Gruppen) liefert jede ein eigenes,
#: schon kuratiertes Material -- das Journal bleibt in jeder Phase gleich.
_PHASE_BEGRIFFE = 1
_PHASE_FRAGEN = 2
_PHASE_INTERVIEWS = 3

_KOPF_BEGRIFFE_FINAL = "Terms the group settled on:"
_KOPF_BEGRIFFE_DETAIL = "Reasoning behind individual terms:"
_KOPF_FRAGEN = "Interview questions the group chose:"
_KOPF_INTERVIEWS_ANZAHL = "Interviews conducted: {n}"
_KOPF_INTERVIEWS_THEMEN = "Themes across the interviews (no names, no quotes):"


def _begriffe_zeilen(conn, chat_id: int) -> list[str]:
    """Phase 1: die entschiedenen Begriffe plus ihre Begruendung aus dem
    Begriffsboard -- nie das Zitat dahinter (dieselbe Regel wie
    ``roadmap.begriffe_detail``)."""
    from interview_theater import begriffsboard
    from interview_theater import begriffe as begriffe_modul

    stand = repo.hole_arbeitsstand(conn, chat_id)
    begriffe_text = _feld(stand, "begriffe")
    teile: list[str] = []
    begriffe = begriffe_modul.zerlege(begriffe_text)
    if begriffe:
        teile.append(_KOPF_BEGRIFFE_FINAL + " " + ", ".join(begriffe))
    roh = stand["begriffe_detail"] if stand is not None and "begriffe_detail" in stand.keys() else None
    detail = begriffsboard.lies(roh)
    zeilen = begriffsboard.detail_zeilen(detail)
    if zeilen:
        teile.append(_KOPF_BEGRIFFE_DETAIL + "\n" + "\n".join(zeilen))
    return teile


def _fragen_zeilen(conn, chat_id: int) -> list[str]:
    """Phase 2: die Fragen, auf die sich die Gruppe festgelegt hat --
    dieselbe Zerlegung wie der Leitfaden (``leitfaden.fragen``)."""
    from interview_theater import leitfaden

    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = leitfaden.fragen(_feld(stand, "fragen"))
    if not fragen:
        return []
    return [_KOPF_FRAGEN + "\n" + "\n".join(f"- {f}" for f in fragen)]


def _interviews_zeilen(conn, chat_id: int) -> list[str]:
    """Phase 3: wie viele Interviews gefuehrt wurden und welche Themen sie
    insgesamt trugen -- nie Namen, nie ein Zitat, nie das Transkript."""
    anzahl = repo.zaehle_interviews(conn, chat_id)
    if not anzahl:
        return []
    zeilen = [_KOPF_INTERVIEWS_ANZAHL.format(n=anzahl)]
    themen: list[str] = []
    gesehen: set[str] = set()
    for v in repo.verdichtungen(conn, chat_id):
        for thema in repo.themen_zu(conn, v["id"]):
            text = (thema["thema"] or "").strip()
            if text and text not in gesehen:
                gesehen.add(text)
                themen.append(text)
    if themen:
        zeilen.append(_KOPF_INTERVIEWS_THEMEN + "\n" + "\n".join(f"- {t}" for t in themen))
    return zeilen


_KURATOR_JE_PHASE = {
    _PHASE_BEGRIFFE: _begriffe_zeilen,
    _PHASE_FRAGEN: _fragen_zeilen,
    _PHASE_INTERVIEWS: _interviews_zeilen,
}


def baue_nutzertext(conn, chat_id: int, phase: int) -> str:
    """Der Nutzertext des Summary-Aufrufs der Phase ``phase``: in den
    Phasen 1-3 ihr eigenes kuratiertes Material (``_KURATOR_JE_PHASE``),
    sonst Chat und Werkbank seit dem letzten Eintritt -- das Journal
    (Entscheidungen/Verworfenes) traegt jede Phase gleich."""
    praefix = f"{_PHASENZEILE_PRAEFIX}{phasen.bezeichnung(phase)}"
    seit = repo.phase_eintritt_zeitpunkt(conn, chat_id, praefix) or ""
    teile = [f"Phase: {praefix}"]
    kurator = _KURATOR_JE_PHASE.get(phase)
    if kurator is not None:
        teile.extend(kurator(conn, chat_id))
    else:
        chat = _chat_zeilen(conn, chat_id, seit)
        if chat:
            teile.append("Conversation during this phase:\n" + "\n".join(chat))
        workbench = _workbench_zeilen(conn, chat_id)
        if workbench:
            teile.append("Current state of the workbench:\n\n" + "\n\n".join(workbench))
    journal = _journal_zeilen(conn, chat_id, seit)
    if journal:
        teile.append(
            "Decisions and discards logged during this phase:\n" + "\n".join(journal)
        )
    return "\n\n".join(teile)


_KOPF_ENTSCHEIDUNGEN = "Decided:"
_KOPF_DISCARDED = "Discarded:"
_KOPF_OFFEN = "Open:"


def _abschnitt(kopf: str, eintraege) -> str:
    zeilen = [str(e).strip() for e in (eintraege or []) if str(e).strip()]
    if not zeilen:
        return ""
    return kopf + "\n" + "\n".join(f"- {z}" for z in zeilen)


def _kuerze(text: str) -> str:
    """Kuerzt hart auf ``MAX_ZEICHEN``, am letzten Zeilenumbruch davor --
    nie mitten im Wort. Erste und einzige Verteidigung gegen ein Modell, das
    trotz Prompt-Vorgabe zu viel liefert."""
    if len(text) <= MAX_ZEICHEN:
        return text
    gekuerzt = text[:MAX_ZEICHEN]
    umbruch = gekuerzt.rfind("\n")
    if umbruch > MAX_ZEICHEN // 2:
        gekuerzt = gekuerzt[:umbruch]
    return gekuerzt.rstrip() + "\n…"


def baue_text(ergebnis: dict, phase: int) -> str:
    """Setzt die Schema-Antwort zum fertigen Summary-Text zusammen --
    deterministisch, kein zweiter Modellaufruf (wie ``entwurf.baue_anzeige``)."""
    abschnitte = [
        _abschnitt(_KOPF_ENTSCHEIDUNGEN, ergebnis.get("entscheidungen")),
        _abschnitt(_KOPF_DISCARDED, ergebnis.get("discarded")),
        _abschnitt(_KOPF_OFFEN, ergebnis.get("offene_punkte")),
    ]
    kopf = f"Phase {phasen.bezeichnung(phase)} summary:"
    text = "\n\n".join([kopf] + [a for a in abschnitte if a])
    return _kuerze(text)


def erzeuge(klm, conn, e, chat_id: int, phase: int) -> dict:
    """Der eigentliche Modellaufruf -- schreibt noch NICHTS in die
    Datenbank (das macht ``_lauf``)."""
    return modellwahl.aufruf_schema(
        conn, klm, e, chat_id, prompt(), baue_nutzertext(conn, chat_id, phase),
        SCHEMA, ART,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
        modell=getattr(e, "erkenner_modell", None),
    )


def _lauf(conn, klm, e, chat_id: int, phase: int, sperre: threading.Lock) -> None:
    try:
        ergebnis = erzeuge(klm, conn, e, chat_id, phase)
        text = baue_text(ergebnis, phase)
        repo.speichere_phasen_summary(conn, chat_id, phase, text)
    except Exception:
        log.exception(
            "Phasen-Summary fehlgeschlagen, chat_id=%s, phase=%s", chat_id, phase
        )
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "phasen_summary_fehlgeschlagen",
                f"Phasen-Summary fuer Phase {phase} fehlgeschlagen",
            )
        except Exception:
            log.exception(
                "Vorfall zur Phasen-Summary nicht schreibbar, chat_id=%s", chat_id
            )
    finally:
        sperre.release()


def starte_wenn_aktiv(conn, klm, e, chat_id: int, phase: int | None):
    """Stoesst die Summary-Erzeugung der gerade VERLASSENEN Phase ``phase``
    in einem eigenen Thread an.

    Tut nichts (liefert ``None``) ohne Profilschalter
    (``workshop.phasen_summary_aktiv``), ohne Sprachmodell oder ohne
    ``phase`` (eine Gruppe, die gerade zum ersten Mal ueberhaupt eine Phase
    setzt, verlaesst keine) -- und damit unveraendert fuer Dortmund und das
    eingebaute Vorgabeprofil (E1)."""
    if phase is None or klm is None or not workshop.phasen_summary_aktiv():
        return None
    sperre = _sperre_fuer(chat_id, phase)
    if not sperre.acquire(blocking=False):
        return None
    try:
        thread = threading.Thread(
            target=_lauf, args=(conn, klm, e, chat_id, phase, sperre), daemon=True,
        )
        thread.start()
    except BaseException:
        sperre.release()
        raise
    return thread


def hole_text(conn, chat_id: int, phase: int) -> str | None:
    """Das gespeicherte Summary dieser Phase, oder ``None``, wenn noch
    keins erzeugt wurde."""
    zeile = repo.hole_phasen_summary(conn, chat_id, phase)
    return zeile["text"] if zeile else None


def bloecke_bis(conn, chat_id: int, vor_phase: int) -> list[str]:
    """Die gespeicherten Summaries aller Phasen VOR ``vor_phase`` --
    aufsteigend. Die generische Injektionsgrundlage fuer Prompt-Bloecke, die
    bisher den Rohdump abgeschlossener Phasen trugen."""
    return [
        z["text"] for z in repo.phasen_summaries(conn, chat_id) if z["phase"] < vor_phase
    ]

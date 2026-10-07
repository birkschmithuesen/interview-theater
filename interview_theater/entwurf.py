"""Phase 5 (Prose Draft), zweistufig: erst eine Geschichts-Uebersicht
abnehmen, dann Szene fuer Szene Prosa schreiben (Padua Phasen TEIL 1,
03.10.2026).

**Nur aktiv mit** ``workshop.prosa_entwurf_aktiv()`` (Dortmund und das
eingebaute Vorgabeprofil lassen das Feld unangetastet -- Phase 5 bleibt dort
die automatische Schaerfung allein, wie vor diesem Umbau).

**Stufe A -- Uebersicht.** Nach der automatischen Schaerfung
(``schaerfung.mappe``, unveraendert) laeuft EIN Schema-Aufruf, der aus
Setting, Figuren, Geschichte und der Szenenanzahl eine strukturierte
Uebersicht baut: Logline, Setting, Figuren (je eine Zeile), Spannungsbogen,
und je Szene ein bis zwei Saetze. Flach wie ueberall
(global-constraints.md 'Schema'): ``szenen_was_passiert`` ist eine Liste von
Strings, eine je Szene -- keine verschachtelte Struktur. Die Gruppe sieht die
zusammengesetzte Anzeige (``baue_anzeige``) mit zwei Knoepfen, "Yes, save"
und "No, change it again"; Freitext-Rueckmeldung laeuft ueber die
Erkenner-art ``uebersicht_aendern`` (phasengebunden, siehe erkenner.py).

**Stufe B -- Szene fuer Szene.** Sobald die Uebersicht fixiert ist
(``geschichte_uebersicht_fixiert_am``), bekommt jede Szene ihre Pflichtfelder
aus der Uebersicht (``was_passiert`` aus ``szenen_was_passiert[i]``, ``ort``
aus ``arbeitsstand.rahmen`` als Vorgabe, die volle Besetzung als Vorgabe-Cast)
und wird ueber das BESTEHENDE ``szene.starte()`` geschrieben -- das schreibt
bei Phase <= ``szene.PHASE_PROSA`` (6) ohnehin schon in ``szene.prosa`` statt
``volltext`` und verlangt dort kein ``form``. Jede Szene bekommt dabei
GARANTIERT den vollen Text jeder vorigen Szene (nicht nur eine
Zusammenfassung) -- das ist bereits ``szene.py``s Normalfall
(``_continuity_bloecke``, voller Wortlaut, solange das Tokenbudget reicht);
dieses Modul erzwingt keine zusaetzliche Kuerzung.

Ist eine Szene abgenommen (Knopf "Yes, save",
``repo.setze_szene_entwurf_bestaetigt``), geht es automatisch zur naechsten
offenen Szene weiter (wiederverwendet: ``knoepfe.szenen._naechste_offene``).
Ist keine mehr offen, springt die Phase automatisch auf 6 -- die EINE,
ausdruecklich von Birk gewuenschte Ausnahme vom sonst geltenden
"Datenstand ist nicht Absicht" (AGENTS.md); sie bleibt lokal auf diesen
Abschluss begrenzt und aendert nichts an ``phasen.moegliche_naechste``/
``offenes_angebot`` fuer jeden anderen Phasenuebergang.

**Eigenes Sperren-Register**, nicht ``vorschlagssperre`` (die koppelt
ausschliesslich Schaerfung und Szenenfolge) und nicht ``szene._sperren``
(das ist je Szene, dieses hier ist je Gruppe fuer den ganzen
Uebersicht-Lauf) -- "Ein Sperren-Register je Nebenlaeufigkeit" (docs/agents/aufbau.md).
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, szene_claude

log = logging.getLogger(__name__)

ART_UEBERSICHT = "entwurf_uebersicht"

#: Ein Sperren-Register je Gruppe -- eigenes Register, siehe Modul-Docstring.
#: Das Get-or-create unten ist sonst eine TOCTOU-Luecke (zwei Threads sehen
#: beide ``None`` fuer dieselbe neue ``chat_id`` und installieren je ein
#: eigenes ``Lock`` -- beide ``acquire`` gelingen dann gleichzeitig). Deshalb
#: ein eigener Meta-Lock, wie bei ``kurzgeschichte._sperren_schutz``.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


#: Flach (global-constraints.md 'Schema'): keine verschachtelte Struktur,
#: eine Liste von Strings je Szene -- dieselbe Bauart wie schaerfung.SCHEMA.
SCHEMA_UEBERSICHT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["logline", "setting", "figuren_zeilen", "spannungsbogen",
                 "szenen_was_passiert"],
    "properties": {
        "logline": {"type": "string"},
        "setting": {"type": "string"},
        "figuren_zeilen": {"type": "array", "items": {"type": "string"}},
        "spannungsbogen": {"type": "string"},
        "szenen_was_passiert": {"type": "array", "items": {"type": "string"}},
    },
}


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("entwurf")


def baue_nutzertext_uebersicht(conn, chat_id: int, notiz: str | None = None) -> str:
    """Setting, Figuren, Geschichte, Szenenanzahl -- und bei einer
    Neugenerierung die vorige Uebersicht plus die Rueckmeldung der Gruppe,
    damit ``uebersicht_aendern`` wirklich etwas AENDERT statt zufaellig neu
    zu wuerfeln."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen: list[str] = []
    if stand and (stand["rahmen"] or "").strip():
        zeilen.append(f"Setting: {stand['rahmen'].strip()}")
    if stand and (stand["geschichte"] or "").strip():
        zeilen.append(f"Story (arc and ending):\n{stand['geschichte'].strip()}")
    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append("Characters:")
        for figur in figuren:
            beschreibung = (figur["beschreibung"] or "").strip()
            zeilen.append(f"- {figur['name']}" + (f" -- {beschreibung}" if beschreibung else ""))
    anzahl = (stand["szenen_anzahl"] or "").strip() if stand else ""
    if anzahl:
        zeilen.append(f"Number of scenes: {anzahl}")
    zeilen.extend(_voll_bloecke(conn, chat_id))
    bisherige = (stand["geschichte_uebersicht"] or "").strip() if stand else ""
    if bisherige:
        zeilen.append("Previous overview (for reference, to be replaced):")
        zeilen.append(bisherige)
    if notiz:
        zeilen.append(f"Feedback from the group on the previous overview: {notiz}")
    return "\n\n".join(zeilen)


def baue_anzeige(ergebnis: dict) -> str:
    """Setzt die Schema-Antwort zur Chat-Anzeige zusammen -- deterministisch,
    kein zweiter Modellaufruf."""
    zeilen = [f"Logline: {ergebnis.get('logline', '').strip()}",
              "", f"Setting: {ergebnis.get('setting', '').strip()}",
              "", "Characters:"]
    for zeile in ergebnis.get("figuren_zeilen") or []:
        zeilen.append(f"- {zeile}")
    zeilen.append("")
    zeilen.append(f"Tension arc: {ergebnis.get('spannungsbogen', '').strip()}")
    zeilen.append("")
    zeilen.append("Scenes:")
    for i, satz in enumerate(ergebnis.get("szenen_was_passiert") or [], start=1):
        zeilen.append(f"{i}. {satz.strip()}")
    return "\n".join(zeilen)


def _voll_bloecke(conn, chat_id: int) -> list[str]:
    """Padua (Birk 07.10.2026 ~16:10): die Uebersicht/Logline soll auch dann
    sinnvoll werden, wenn die Gruppe im CoThinker NICHT alles durchklickt,
    sondern im Chat ueber die Interviews redet -- "der Chat ist das Wertvolle
    fuer die Logline". Zusaetzlich: Szenen mit Titel und was passiert, die
    Festlegungen, die uebernommenen Interviewstellen und das ganze
    Phase-5-Gespraech (``szene._p5_gespraech_text``, Claude-Grenze). Nur unter
    ``workshop.vollmaterial_phase5_aktiv`` (Padua); sonst leer, Dortmund
    byte-gleich."""
    from interview_theater import kontext, szene, workshop

    if not workshop.vollmaterial_phase5_aktiv():
        return []
    bloecke: list[str] = []
    szenen = sorted(repo.hole_szenen(conn, chat_id), key=lambda z: z["nummer"] or 0)
    if szenen:
        teile = ["Scenes the group has laid out (keep their number, titles and order):"]
        for z in szenen:
            was = (z["was_passiert"] or z["kurzbeschreibung"] or "").strip()
            teile.append(f"{z['nummer']}. {z['titel'] or ''}" + (f" -- {was}" if was else ""))
        bloecke.append("\n".join(teile))
    fest = [repo.festlegungszeile(f["bereich"], f["bezug"], f["text"])
            for f in repo.festlegungen(conn, chat_id)]
    if fest:
        bloecke.append("Agreed by the group:\n" + "\n".join(f"- {f}" for f in fest))
    stellen = [z for z in repo.schaerfungen(conn, chat_id) if z["uebernommen_am"]]
    if stellen:
        teile = ["Interview passages the group accepted (with interview number):"]
        for z in stellen[:80]:
            name = kontext.interviewbezeichnung(conn, chat_id, z["aufnahme_id"])
            teile.append(f'- {name}: {z["thema"]} -- "{z["zitat"]}"')
        bloecke.append("\n".join(teile))
    gespraech = szene._p5_gespraech_text(conn, chat_id, ueber_claude=True)
    if gespraech:
        bloecke.append(gespraech + "\n(This conversation is the most valuable source for the "
                       "logline and the scene lines: what the group said about the interviews, "
                       "which voices and themes they chose. Condense it -- don't invent.)")
    return bloecke


def generiere_uebersicht(klm, conn, e, chat_id: int, notiz: str | None = None) -> dict:
    """Der eigentliche Modellaufruf: Nutzertext bauen, Schema-Aufruf, Ergebnis
    zurueckgeben (schreibt noch NICHTS in die Datenbank -- das macht der
    Aufrufer, der auch die Chat-Anzeige verschickt)."""
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id, prompt(), baue_nutzertext_uebersicht(conn, chat_id, notiz),
        SCHEMA_UEBERSICHT, ART_UEBERSICHT,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id), modell=e.erkenner_modell,
    )
    return ergebnis


def _lauf(conn, tg, klm, e, chat_id: int, notiz: str | None,
          sperre: threading.Lock) -> None:
    from interview_theater import arbeitszeilen, knoepfe

    try:
        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "entwurf_uebersicht")
        try:
            ergebnis = generiere_uebersicht(klm, conn, e, chat_id, notiz)
            anzeige = baue_anzeige(ergebnis)
            repo.setze_arbeitsstand(conn, chat_id, "geschichte_uebersicht", anzeige)
            # Einzeln, newline-getrennt -- Stufe B liest das hieraus zurueck
            # (entwurf.uebernimm_szenenfelder), statt die zusammengesetzte
            # Anzeige wieder zu zerlegen.
            repo.setze_arbeitsstand(
                conn, chat_id, "geschichte_uebersicht_szenen",
                "\n".join(ergebnis.get("szenen_was_passiert") or []),
            )
            repo.schreibe_journal(
                conn, chat_id, "entschieden",
                f"Geschichts-Uebersicht erzeugt ({len(anzeige)} Zeichen)",
                quelle="entwurf",
            )
        except Exception:
            log.exception("Uebersicht-Erzeugung fehlgeschlagen, chat_id=%s", chat_id)
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "entwurf_uebersicht_fehlgeschlagen", "Uebersicht-Erzeugung fehlgeschlagen",
            )
            from interview_theater import kosten
            kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
            anzeige = None
        finally:
            zeilen.stoppe()
        if anzeige:
            knoepfe.biete_uebersicht(conn, tg, chat_id, anzeige)
    finally:
        sperre.release()


def uebernimm_szenenfelder(conn, chat_id: int) -> None:
    """Stufe A -> B: jede Szene bekommt ihre Pflichtfelder aus der
    Uebersicht, sofern sie noch leer sind. ``form`` bleibt aussen vor -- das
    ist in Phase 5 kein Pflichtfeld (``szene.schreibt_prosa``).

    ``was_passiert`` kommt zeilenweise aus
    ``arbeitsstand.geschichte_uebersicht_szenen`` (die EINZELNEN
    Szenensaetze, getrennt von der zusammengesetzten Anzeige, die ``_lauf``
    dort ablegt). Ort faellt auf das Setting zurueck (docs/agents/entscheidungen.md: das Setting
    ist die Vorgabe fuer Ort, Zeit und Anlass jeder Szene); die Besetzung
    faellt auf die volle Figurenliste zurueck (dokumentierte Vereinfachung,
    Padua Phasen TEIL 1 -- das Schema liefert keine Besetzung je Szene, um
    flach zu bleiben). Alle drei sind ueber die Gruppenseite danach
    aenderbar."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return
    rahmen = (stand["rahmen"] or "").strip()
    anzahl_text = (stand["szenen_anzahl"] or "").strip()
    anzahl = int(anzahl_text) if anzahl_text.isdigit() else 0
    was_passiert_zeilen = (stand["geschichte_uebersicht_szenen"] or "").splitlines()
    figuren_ids = [f["id"] for f in repo.figuren(conn, chat_id)]
    for nummer in range(1, anzahl + 1):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        zeile = repo.hole_szene(conn, szene_id)
        if not (zeile["was_passiert"] or "").strip() and nummer - 1 < len(was_passiert_zeilen):
            satz = was_passiert_zeilen[nummer - 1].strip()
            if satz:
                repo.setze_szenenfeld(conn, szene_id, "was_passiert", satz)
        if not (zeile["ort"] or "").strip() and rahmen:
            repo.setze_szenenfeld(conn, szene_id, "ort", rahmen)
        if not repo.szene_figuren(conn, szene_id) and figuren_ids:
            repo.setze_szene_figuren(conn, chat_id, szene_id, figuren_ids)


def erste_offene_szene(conn, chat_id: int) -> int | None:
    """Die niedrigste Szenennummer, deren Prosa-Entwurf noch nicht
    abgenommen ist (``szene.entwurf_bestaetigt_am``). Pflichtfelder
    (``was_passiert``, Besetzung) muessen schon dastehen --
    ``uebernimm_szenenfelder`` laeuft vorher."""
    for s in sorted(repo.hole_szenen(conn, chat_id), key=lambda z: z["nummer"] or 0):
        if s["nummer"] is not None and not (s["entwurf_bestaetigt_am"] or "").strip():
            return s["nummer"]
    return None


#: Der Auftrag an den Szenenlauf in Stufe B (unveraendert der Wortlaut, der
#: bis TEIL 2 zweimal in ``knoepfe/wirkung.py`` stand).
_AUFTRAG_PROSA = "SZENE {nummer}: write this scene as prose, following the overview."


def fixiere_uebersicht(conn, tg, klm, e, chat_id: int) -> str:
    """"Yes, save" auf der Uebersicht (Stufe A -> B) -- der EINE Rumpf fuer
    den Knopf (``knoepfe.wirkung._wirkung_uebersicht_passt``) und den
    Erkenner (``fassung_abnehmen``, Padua Phasen TEIL 2).

    Kein Modellaufruf hier (Zusage 2): die Pflichtfelder kommen aus dem
    schon erzeugten Uebersicht-Text, und die erste offene Szene geht ueber
    ``szene.starte`` in einen eigenen Thread."""
    from interview_theater import knoepfe, szene

    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte_uebersicht_fixiert_am", repo._jetzt(),
    )
    uebernimm_szenenfelder(conn, chat_id)
    erste = erste_offene_szene(conn, chat_id)
    if erste is not None:
        szene.starte(conn, tg, klm, e, chat_id, _AUFTRAG_PROSA.format(nummer=erste))
    return knoepfe.T._TEXT_UEBERSICHT_FIXIERT


def bestaetige_szene(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" auf einem Prosa-Entwurf in Stufe B -- der EINE Rumpf fuer
    Knopf und Erkenner. Szene abnehmen, automatisch weiter -- zur naechsten
    offenen Szene oder, wenn keine mehr offen ist, automatisch nach Phase 6
    (die EINE, ausdruecklich von Birk gewuenschte Ausnahme vom sonst
    geltenden "Datenstand ist nicht Absicht", AGENTS.md)."""
    from interview_theater import knoepfe, phasen, szene

    ziel = knoepfe._szene_mit_nummer(conn, chat_id, nummer)
    if ziel is None:
        tg.sende(chat_id, knoepfe.T._TEXT_SZENE_UNBEKANNT)
        return knoepfe.T._TEXT_SZENE_UNBEKANNT
    repo.setze_szene_entwurf_bestaetigt(conn, ziel["id"])
    naechste = erste_offene_szene(conn, chat_id)
    if naechste is not None:
        szene.starte(conn, tg, klm, e, chat_id, _AUFTRAG_PROSA.format(nummer=naechste))
        return knoepfe.T._TEXT_NAECHSTE_SZENE_WIRD_GESCHRIEBEN
    phasen.setze(conn, chat_id, 6, "entwurf", notiz="alle Szenen entworfen")
    knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, 6)
    return knoepfe.T._TEXT_ALLE_SZENEN_ENTWORFEN


def starte_uebersicht(conn, tg, klm, e, chat_id: int, notiz: str | None = None):
    """Gibt die Uebersicht-Erzeugung an einen eigenen Thread ab -- dasselbe
    Muster wie ``schaerfung.starte``/``kernzitate.starte`` (Zusage 2: kein
    Modellaufruf im Knopf-/Erkenner-Handler)."""
    if klm is None:
        log.error("Entwurf-Uebersicht ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    try:
        thread = threading.Thread(
            target=_lauf, args=(conn, tg, klm, e, chat_id, notiz, sperre), daemon=True,
        )
        thread.start()
    except BaseException:
        sperre.release()
        raise
    return thread

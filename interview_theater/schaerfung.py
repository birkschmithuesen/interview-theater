"""Die Schaerfung am Material: Verdichtungen auf Szenen und Figuren mappen.

**Warum es das gibt** (Birk, 05.09.2026 nachts): bis zu diesem Umbau
entstanden Figuren und Szenen AUS den Interviews -- und die Gruppe erkannte
ihren eigenen kreativen Anteil nicht wieder. Der Weg ist jetzt umgekehrt:
**zuerst erfindet die Gruppe** (Phase 4 Setting & Figuren, Phase 5
Geschichte), **dann schaerft das Material** (Phase 6, dieses Modul).

Der Lauf, in einem Satz: ein Schema-Aufruf bekommt Setting, Figuren und die
Geschichte mit ihren Szenen plus ALLE geprueften ``verdichtung_thema``-
Eintraege und **mappt jeden passenden Eintrag auf eine Szene und/oder eine
Figur**; was nicht passt, bleibt weg. Das Ergebnis steht in der Tabelle
``schaerfung`` (additiv, mit Rundennummer), und der Bot legt der Gruppe je
Szene und je Figur eine Vorschlagsnachricht hin -- \"Gefaellt uns, weiter\"
uebernimmt sie ins Szenenfeld bzw. in die Figur.

**Die Eingabe ist geschlossen** (wie in ``kernzitate.py``, auf dem dieses
Modul aufbaut): das Modell sieht ausschliesslich die schon geprueften
Verdichtungsthemen (``repo.gepruefte_themen``) -- Interview-Nummer, Thema,
Zusammenfassung, Zitat, **keine Transkripte**. Es zeigt per Nummer darauf;
erfinden kann es nichts, weil nichts Erfundenes eine Nummer hat. Nennt es
zusaetzlich einen Wortlaut, wird dieser gegen das Original geprueft
(``zitat.pruefe``) und der Eintrag sonst verworfen (N2, T3).

**Reasoning aus, gemma, eigener Thread** -- die Aufgabe ist Zuordnung, kein
Abwaegen, und niemand wartet im Chat darauf (AGENTS.md, Zusage 2: kein
Modellaufruf in einem Knopf-Handler).
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, repo, zitat

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "schaerfung"

#: Flach wie ueberall (global-constraints.md 'Schema'): vier gleich lange
#: Listen statt einer Liste aus Objekten. Die Zuordnung laeuft ueber die
#: Nummern der Eingabeliste und ueber Szenennummer bzw. Figurenname -- beides
#: steht im Nutzertext, beides ist nachpruefbar.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eintrag_nummern", "szenen_nummern", "figuren_namen", "begruendungen"],
    "properties": {
        "eintrag_nummern": {"type": "array", "items": {"type": "integer"}},
        # 0 heisst \"keine Szene\" -- ein null in einem flachen Schema ist
        # bei mehreren Modellen ein Formatfehler, eine 0 nicht.
        "szenen_nummern": {"type": "array", "items": {"type": "integer"}},
        # Leerer String heisst \"keine Figur\".
        "figuren_namen": {"type": "array", "items": {"type": "string"}},
        "begruendungen": {"type": "array", "items": {"type": "string"}},
        "zitate": {"type": "array", "items": {"type": "string"}},
    },
}

#: Die Zeile, die nach einem Lauf in den Chat geht.
MELDUNG = (
    "Ich habe {anzahl} Stellen aus euren Interviews euren Szenen und Figuren "
    "zugeordnet. Ich gehe sie mit euch durch."
)
MELDUNG_LEER = (
    "Keine Stelle aus den Interviews passt zu eurer Geschichte - sie bleibt, "
    "wie ihr sie erfunden habt."
)
MELDUNG_OHNE_MATERIAL = (
    "Es gibt noch keine ausgewerteten Interviews, an denen ich schaerfen "
    "koennte."
)


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("schaerfung")


def _eintraege(conn, chat_id: int) -> list[dict]:
    """Die Materialliste: je geprueftem Thema eine Zeile mit Nummer."""
    from interview_theater import kontext

    eintraege = []
    for nummer, zeile in enumerate(repo.gepruefte_themen(conn, chat_id), start=1):
        eintraege.append(
            {
                "nummer": nummer,
                "thema_id": zeile["id"],
                "aufnahme_id": zeile["aufnahme_id"],
                "interview": kontext.interviewbezeichnung(
                    conn, chat_id, zeile["aufnahme_id"]
                ) or f"Interview {zeile['aufnahme_id']}",
                "thema": zeile["thema"] or "",
                "zusammenfassung": zeile["zusammenfassung"] or "",
                "zitat": zeile["beleg_zitat"] or "",
            }
        )
    return eintraege


def baue_nutzertext(conn, chat_id: int, eintraege: list[dict]) -> str:
    """Erst das Erfundene (Setting, Figuren, Geschichte, Szenen), dann das
    Material mit Nummern.

    Oeffentlich wie ``verdichter.baue_nutzertext``, damit ein Pruefskript
    denselben Text bauen kann wie der Betrieb."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen: list[str] = []
    if stand and (stand["rahmen"] or "").strip():
        zeilen.append(f"Setting: {stand['rahmen'].strip()}")
    if stand and "geschichte" in stand.keys() and (stand["geschichte"] or "").strip():
        zeilen.append("Geschichte:\n" + stand["geschichte"].strip())

    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append("Figuren (Namen genau so schreiben):")
        for figur in figuren:
            beschreibung = (figur["beschreibung"] or "").strip()
            zeilen.append(f"- {figur['name']}" + (f" -- {beschreibung}" if beschreibung else ""))

    szenen = repo.hole_szenen(conn, chat_id)
    if szenen:
        zeilen.append("Szenen (Nummer verwenden):")
        for szene in szenen:
            teile = [f"[{szene['nummer']}]"]
            if szene["titel"]:
                teile.append(szene["titel"])
            if szene["was_passiert"]:
                teile.append(szene["was_passiert"])
            if szene["form"]:
                teile.append(f"Form: {szene['form']}")
            zeilen.append(" — ".join(teile))

    zeilen.append("")
    zeilen.append("Material (nur hieraus waehlen, nach Nummer):")
    # Die Zusammenfassung gehoert dem Interview, nicht der Zeile: elf geprueft
    # Themen desselben Interviews schrieben sie elfmal (Audit-Befund M1,
    # 06.09.2026 -- 7.700 Zeichen Dublette in einem 9.000-Zeichen-Prompt).
    # Jetzt einmal je Interview, als eigene Zeile darueber.
    letztes_interview = None
    for eintrag in eintraege:
        if eintrag["interview"] != letztes_interview:
            letztes_interview = eintrag["interview"]
            if eintrag["zusammenfassung"]:
                zeilen.append(
                    f"\n{eintrag['interview']} -- worum es darin geht: "
                    f"{eintrag['zusammenfassung']}"
                )
        zeilen.append(
            f"[{eintrag['nummer']}] {eintrag['interview']} | "
            f"Thema: {eintrag['thema']} | "
            f'Zitat: "{eintrag["zitat"]}"'
        )
    return "\n".join(zeilen)


def _liste(ergebnis: dict, name: str) -> list:
    wert = ergebnis.get(name)
    return list(wert) if isinstance(wert, list) else []


def mappe(klm, conn, e, chat_id: int) -> tuple[int, int]:
    """Der eigentliche Lauf: Material holen, Modell fragen, pruefen,
    speichern. Liefert ``(Anzahl Zuordnungen, Runde)``.

    Ohne Material (noch keine geprueften Themen) gibt es keinen Aufruf --
    ein Modell, das aus nichts zuordnen soll, erfindet."""
    eintraege = _eintraege(conn, chat_id)
    if not eintraege:
        return 0, 0

    runde = repo.letzte_schaerfungsrunde(conn, chat_id) + 1
    ergebnis = klm.schema(
        chat_id, prompt(), baue_nutzertext(conn, chat_id, eintraege),
        SCHEMA, ART, modell=e.erkenner_modell,
    )

    nach_nummer = {eintrag["nummer"]: eintrag for eintrag in eintraege}
    szenen_nach_nummer = {
        s["nummer"]: s["id"] for s in repo.hole_szenen(conn, chat_id)
        if s["nummer"] is not None
    }
    figuren_nach_name = {
        f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)
    }

    nummern = _liste(ergebnis, "eintrag_nummern")
    szenen = _liste(ergebnis, "szenen_nummern")
    namen = _liste(ergebnis, "figuren_namen")
    begruendungen = _liste(ergebnis, "begruendungen")
    wortlaute = _liste(ergebnis, "zitate")

    zuordnungen: list[dict] = []
    for lauf, roh in enumerate(nummern):
        try:
            eintrag = nach_nummer.get(int(roh))
        except (TypeError, ValueError):
            continue
        if eintrag is None:
            # Eine Nummer, die es nicht gibt, ist genau der Fall, gegen den
            # die Nummerierung schuetzt: verworfen, nicht geraten.
            continue
        # Der mitgeschriebene Wortlaut wird gegen das Original gehalten:
        # schreibt das Modell etwas anderes hin als das Zitat, auf dessen
        # Nummer es zeigt, meint es nicht diese Stelle.
        wortlaut = str(wortlaute[lauf] or "").strip() if lauf < len(wortlaute) else ""
        if wortlaut and not zitat.pruefe(wortlaut, eintrag["zitat"]):
            log.info("Schaerfung verworfen: Wortlaut passt nicht zu Nummer %s", roh)
            continue
        szene_id = None
        if lauf < len(szenen):
            try:
                szene_id = szenen_nach_nummer.get(int(szenen[lauf]))
            except (TypeError, ValueError):
                szene_id = None
        figur_id = None
        if lauf < len(namen):
            figur_id = figuren_nach_name.get(str(namen[lauf] or "").strip().lower())
        if szene_id is None and figur_id is None:
            continue
        zuordnungen.append(
            {
                "verdichtung_thema_id": eintrag["thema_id"],
                "szene_id": szene_id,
                "figur_id": figur_id,
                "begruendung": (
                    str(begruendungen[lauf] or "").strip()
                    if lauf < len(begruendungen) else None
                ),
            }
        )

    anzahl = repo.lege_schaerfung_an(conn, chat_id, zuordnungen, runde=runde)
    if anzahl:
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            f"Schaerfung Runde {runde}: {anzahl} Stellen zugeordnet",
            quelle="schaerfung",
        )
    return anzahl, runde


def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: mappen, die eine Zeile schicken, weitergehen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still: sie wartet gerade
    darauf (SPEC § 11.1). Die Nachbereitung laeuft in jedem Fall -- der Weg
    durch die Phase darf an einem Mapping-Lauf nicht haengenbleiben."""
    anzahl = 0
    from interview_theater import arbeitszeilen

    zeilen = arbeitszeilen.sichtbar(tg, chat_id, "schaerfung")
    try:
        anzahl, _ = mappe(klm, conn, e, chat_id)
        meldung = MELDUNG.format(anzahl=anzahl) if anzahl else MELDUNG_LEER
    except Exception:
        log.exception("Schaerfung fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "schaerfung_fehlgeschlagen", "Schaerfung fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zur Schaerfung nicht schreibbar")
        meldung = None
    finally:
        zeilen.stoppe()
    if meldung:
        try:
            message_id = tg.sende(chat_id, meldung)
            repo.merke_nachricht(
                conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
                meldung, repo._jetzt(),
            )
        except Exception:
            log.exception("Schaerfungs-Meldung fehlgeschlagen, chat_id=%s", chat_id)
    if nachbereitung is not None:
        try:
            nachbereitung()
        except Exception:
            log.exception("Nachbereitung der Schaerfung gescheitert, chat_id=%s", chat_id)


def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt das Mapping an einen eigenen Thread ab -- dasselbe Muster wie
    ``kernzitate.starte`` und ``sprachprofil.starte`` (Zusage 2).

    Liefert den Thread (fuer Tests) oder None, wenn es nichts anzustossen
    gab."""
    if klm is None:
        log.error("Schaerfung ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------


def _stelle(conn, chat_id: int, eintrag) -> str:
    from interview_theater import kontext

    name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
    zeile = f'{name} "{eintrag["thema"]}": "{eintrag["zitat"]}"'
    if eintrag["begruendung"]:
        zeile += f"\n  Vorschlag: {eintrag['begruendung']}"
    return zeile


#: Wie viele Stellen hoechstens in EINER Vorschlagsnachricht stehen
#: (06.09.2026, Analyse Abschnitt 2). Der gemessene Fall waren Bloecke von
#: 712 und 1280 Zeichen mit vollstaendigen Zitaten und **einer** globalen
#: Ja/Nein-Frage -- die Wall of Text. Drei ist die Zahl, die auch die
#: Fragenauswahl und die Geschichte-Richtungen benutzen.
MAX_STELLEN = 3

#: Wie viele Woerter eines Zitats in die Kurzoption gehen. Der Volltext des
#: Zitats steht in der Datenbank und geht bei der Uebernahme in
#: ``szene.kernsaetze`` -- im Menue braucht es nur so viel, dass die Gruppe
#: die Stelle wiedererkennt.
ZITAT_WOERTER = 12


def _gekuerzt(text: str, woerter: int = ZITAT_WOERTER) -> str:
    teile = (text or "").split()
    if len(teile) <= woerter:
        return " ".join(teile)
    return " ".join(teile[:woerter]) + " …"


def offene_stellen(conn, chat_id: int, szene_id=None, figur_id=None) -> list:
    """Die noch offenen Schaerfungen zu einer Szene oder Figur, gedeckelt auf
    ``MAX_STELLEN``.

    Deterministisch aus der Datenbank, kein Modellaufruf: das Mapping ist
    schon gelaufen. Der Deckel ist bewusst hier und nicht beim Anzeigen --
    die Reihenfolge (Runde, dann id) entscheidet, was zuerst drankommt, und
    was heute nicht mehr passt, steht beim naechsten Durchgang oben."""
    eintraege = [
        z for z in repo.schaerfungen(conn, chat_id, szene_id=szene_id, figur_id=figur_id)
        if not z["uebernommen_am"]
    ]
    return eintraege[:MAX_STELLEN]


def option(conn, chat_id: int, eintrag) -> tuple[str, str]:
    """Eine Stelle als Menue-Option: ``(Titel, Beschreibung)``.

    Der Titel ist zugleich die Knopfbeschriftung (``vorschlag.menuetext`` +
    ``knoepfe.MENUE_KNOPF_LAENGE``) -- Knopf N und Punkt N meinen dadurch
    dasselbe, wie bei ``stile.reihenfolge_mit_vorschlag``. Die Beschreibung
    traegt das gekuerzte Zitat und, wenn es eine gibt, die Begruendung."""
    from interview_theater import kontext

    name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
    titel = str(eintrag["thema"] or name or "Stelle").strip()
    stuecke = []
    zitat_kurz = _gekuerzt(str(eintrag["zitat"] or ""))
    if zitat_kurz:
        stuecke.append(f'{name}: „{zitat_kurz}“')
    elif name:
        stuecke.append(name)
    if eintrag["begruendung"]:
        stuecke.append(str(eintrag["begruendung"]).strip())
    return (titel, " — ".join(stuecke))


def szenenueberschrift(conn, chat_id: int, szene) -> str:
    kopf = f"Szene {szene['nummer']}"
    if szene["titel"]:
        kopf += f": {szene['titel']}"
    return f"{kopf} — was aus den Interviews dazupasst"


def figurueberschrift(figur) -> str:
    return f"{figur['name']} — was aus den Interviews dazupasst"


def uebernimm_stelle(conn, chat_id: int, schaerfung_id: int) -> str | None:
    """Uebernimmt GENAU EINE Stelle -- der Knopf je Option (06.09.2026).

    Liefert einen kurzen Bezeichner ("Szene 2", "<Figurname>") oder None,
    wenn es die Stelle nicht mehr gibt. Die Wirkung ist dieselbe wie bei
    ``uebernimm_szene``/``uebernimm_figur``, nur auf einen Eintrag begrenzt:
    ``was_passiert`` bzw. die Figurenbeschreibung werden **ergaenzt**, das
    Zitat wandert in ``kernsaetze``."""
    eintrag = next(
        (z for z in repo.schaerfungen(conn, chat_id) if z["id"] == schaerfung_id),
        None,
    )
    if eintrag is None or eintrag["uebernommen_am"]:
        return None
    if eintrag["szene_id"]:
        szene = repo.hole_szene(conn, eintrag["szene_id"])
        if szene is None:
            return None
        _ergaenze_szene(conn, szene, [eintrag])
        repo.merke_schaerfung_uebernommen(conn, eintrag["id"])
        return f"Szene {szene['nummer']}"
    if eintrag["figur_id"]:
        figur = repo.hole_figur_nach_id(conn, eintrag["figur_id"])
        if figur is None:
            return None
        _ergaenze_figur(conn, chat_id, figur, [eintrag])
        repo.merke_schaerfung_uebernommen(conn, eintrag["id"])
        return str(figur["name"])
    return None


def verwirf_stellen(conn, ids: list[int]) -> int:
    """"Keine davon": die gezeigten Stellen fallen weich heraus (N3), damit
    die naechste Runde sie nicht erneut vorlegt."""
    anzahl = 0
    for schaerfung_id in ids:
        repo.entferne_schaerfung(conn, schaerfung_id)
        anzahl += 1
    return anzahl


def szenenvorschlag(conn, chat_id: int, szene) -> str | None:
    """Die Schaerfungs-Vorschlagsnachricht zu EINER Szene, oder None, wenn
    ihr nichts zugeordnet wurde.

    Deterministisch aus der Datenbank, kein Modellaufruf: das Mapping ist
    schon gelaufen, hier wird nur vorgestellt.

    Seit dem 06.09.2026 baut ``knoepfe.biete_schaerfung`` daraus ein Menue
    (``option``); diese Fliesstextfassung bleibt als Rueckfall und fuer
    Protokolle stehen."""
    eintraege = offene_stellen(conn, chat_id, szene_id=szene["id"])
    if not eintraege:
        return None
    zeilen = [szenenueberschrift(conn, chat_id, szene) + ":"]
    zeilen.extend(f"- {_stelle(conn, chat_id, z)}" for z in eintraege)
    zeilen.append("\nSoll das in die Szene?")
    return "\n".join(zeilen)


def figurvorschlag(conn, chat_id: int, figur) -> str | None:
    """Dasselbe je Figur: die Stellen, aus denen sie sprechen koennte."""
    eintraege = offene_stellen(conn, chat_id, figur_id=figur["id"])
    if not eintraege:
        return None
    zeilen = [figurueberschrift(figur) + ":"]
    zeilen.extend(f"- {_stelle(conn, chat_id, z)}" for z in eintraege)
    zeilen.append("\nSoll das zu dieser Figur?")
    return "\n".join(zeilen)


def _ergaenze_szene(conn, szene, eintraege) -> None:
    """Die Schreibwirkung einer Szenen-Schaerfung -- geteilt von
    ``uebernimm_szene`` (alle offenen) und ``uebernimm_stelle`` (eine)."""
    frisch = repo.hole_szene(conn, szene["id"])
    ergaenzung = "; ".join(
        (z["begruendung"] or z["thema"] or "").strip() for z in eintraege
        if (z["begruendung"] or z["thema"] or "").strip()
    )
    if ergaenzung:
        alt = (frisch["was_passiert"] or "").strip()
        repo.setze_szenenfeld(
            conn, szene["id"], "was_passiert",
            f"{alt} {ergaenzung}".strip() if alt else ergaenzung,
        )
    saetze = [str(z["zitat"] or "").strip() for z in eintraege if (z["zitat"] or "").strip()]
    if saetze:
        alt = (frisch["kernsaetze"] or "").strip()
        neu = " | ".join(saetze)
        repo.setze_szenenfeld(
            conn, szene["id"], "kernsaetze", f"{alt} | {neu}" if alt else neu,
        )


def _ergaenze_figur(conn, chat_id: int, figur, eintraege) -> None:
    """Dasselbe je Figur: Beschreibung ergaenzen, Quelle nachtragen."""
    frisch = repo.hole_figur_nach_id(conn, figur["id"])
    ergaenzung = "; ".join(
        (z["begruendung"] or z["thema"] or "").strip() for z in eintraege
        if (z["begruendung"] or z["thema"] or "").strip()
    )
    if ergaenzung:
        alt = (frisch["beschreibung"] or "").strip()
        repo.setze_figur(
            conn, chat_id, frisch["name"],
            f"{alt} {ergaenzung}".strip() if alt else ergaenzung,
        )
    if frisch["quelle_aufnahme_id"] is None:
        quelle = next((z["aufnahme_id"] for z in eintraege if z["aufnahme_id"]), None)
        if quelle is not None:
            repo.setze_figur_quelle(conn, frisch["id"], quelle)


def uebernimm_szene(conn, chat_id: int, szene) -> int:
    """\"Gefaellt uns, weiter\" auf einer Szenen-Schaerfung: die zugeordneten
    Stellen wandern in die Szenenfelder. Liefert die Zahl der Uebernahmen.

    ``was_passiert`` und ``ton`` werden **ergaenzt**, nicht ersetzt: die
    Gruppe hat sie erfunden, das Material schaerft sie. Die Zitate landen in
    ``kernsaetze`` -- das ist das Feld, das der Szenen-Prompt als \"soll
    woertlich vorkommen\" liest."""
    eintraege = [
        z for z in repo.schaerfungen(conn, chat_id, szene_id=szene["id"])
        if not z["uebernommen_am"]
    ]
    if not eintraege:
        return 0
    _ergaenze_szene(conn, szene, eintraege)
    for z in eintraege:
        repo.merke_schaerfung_uebernommen(conn, z["id"])
    return len(eintraege)


def uebernimm_figur(conn, chat_id: int, figur) -> int:
    """Dasselbe je Figur: die Beschreibung wird ergaenzt, und wenn die Figur
    noch kein Interview hat, bekommt sie das der ersten Zuordnung
    (``figur.quelle_aufnahme_id``) -- genau die Zuordnung, aus der bis zu
    diesem Umbau die Figuren-Ebene 2 in Phase 4 bestand. Der Sprachduktus
    entsteht danach daraus."""
    eintraege = [
        z for z in repo.schaerfungen(conn, chat_id, figur_id=figur["id"])
        if not z["uebernommen_am"]
    ]
    if not eintraege:
        return 0
    _ergaenze_figur(conn, chat_id, figur, eintraege)
    for z in eintraege:
        repo.merke_schaerfung_uebernommen(conn, z["id"])
    return len(eintraege)

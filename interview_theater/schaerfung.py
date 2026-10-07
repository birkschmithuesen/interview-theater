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

**Modellwahl-Karte (02.10.2026):** ab Phase 4 mit Einwilligung UND
Betreiberschalter (``szene_claude.ist_aktiv``) laeuft der Lauf stattdessen
ueber den Claude-Proxy -- die Schaerfung steht in der Betreiber-Entscheidung
ausdruecklich auf der Opus-Seite ("viel Leistung gefragt"), trotz des
gemma-Arguments oben (Zuordnung statt Abwaegen). ``modellwahl.aufruf_schema``
faellt bei einem Proxy-Fehler auf genau diesen einen Lauf zurueck auf gemma
(Vorfall ``opus_fallback``) -- die Gruppe wartet nicht im Chat, trotzdem soll
eine Schaerfungsrunde nicht an einem einzelnen Proxy-Ausfall scheitern.

**Umbau 07.10.2026 (Birk, Analyse ``zuordnung-pruefung.md``):** ein einzelner
Pauschal-Lauf ueber alle Szenen und Figuren gleichzeitig sammelte statt zu
verteilen (gemessen: 16 von 21 Zuordnungen einer Gruppe liefen auf EINE
Figur) und war zwischen zwei identischen Laeufen nur zu 27-56 % reproduzierbar.
``mappe`` fragt deshalb jetzt JE SZENE UND JE FIGUR einen eigenen, engen
Aufruf (``_mappe_ziel``) -- gemessen +560-780 % Ertrag und +42-72
Prozentpunkte Reproduzierbarkeit auf den geprueften Kategorien. Die Aufrufe
laufen parallel (``ThreadPoolExecutor``, ``PARALLEL_AUFRUFE``), weil sonst
sechs bis zehn serielle Aufrufe die Gruppe zu lange warten liessen.

**Timeout/Modell (Robo 07.10.2026, gemessen):** der alte Vorgabe-Timeout von
60 s reichte fuer Opus bei der vollen Materialliste oft nicht -- vier
Wiederholungen mit Wartezeiten liessen EINEN gescheiterten Aufruf bis zu
283 s dauern, bevor gemma uebernahm. Ein gemessener echter Aufruf brauchte
37 s; ``CLAUDE_TIMEOUT_S`` (120 s, mindestens das Doppelte) und
``CLAUDE_WARTEZEITEN`` (hoechstens eine Wiederholung) halten das gebuendelt.
``IT_SCHAERFUNG_MODELL`` (Vorgabe ``claude-opus-5``) ist UNABHAENGIG von
``IT_SZENE_MODELL`` (das eine Gruppe fuer das Gespraech z. B. auf
``claude-sonnet-5`` stellen kann) -- die Schaerfung soll immer auf Opus
laufen, egal was die Gruppe fuer ihr Gespraech eingestellt hat.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from interview_theater import anweisungen, modellwahl, repo, szene_claude, vorschlagssperre, zitat

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf`` (Vorsilbe -- der tatsaechliche
#: Aufruf traegt zusaetzlich Ziel-Art und -id, siehe ``_mappe_ziel``).
ART = "schaerfung"

#: Wie viele Ziel-Aufrufe (Szenen + Figuren) hoechstens gleichzeitig laufen.
#: Sechs war die von Robo gemessene Zahl, bei der eine Gruppe mit 6 Szenen +
#: 4 Figuren in unter 90 s fertig wird.
PARALLEL_AUFRUFE = 6

#: Timeout je Ziel-Aufruf ueber den Claude-Proxy und hoechstens eine
#: Wiederholung (Robo 07.10.2026, gemessen: ein echter Opus-Aufruf ueber die
#: volle Materialliste brauchte 37 s -- 120 s ist mindestens das Doppelte,
#: nie weniger). Ohne diese Grenze griff ``szene_claude.WARTEZEITEN`` (3
#: Wiederholungen) mit dem alten 60-s-Vorgabewert und liess einen
#: gescheiterten Aufruf bis zu 283 s dauern.
CLAUDE_TIMEOUT_S = 120.0
CLAUDE_WARTEZEITEN = (10.0,)

#: Wie viele Woerter eines Zitats in die Materialzeile EINES Ziel-Aufrufs
#: gehen (Robo Punkt 3: Eingabe verkleinern). Der volle Wortlaut bleibt in
#: der Datenbank und in ``baue_nutzertext`` (Pruefskript-Schnappschuss) --
#: hier zaehlt nur, dass das Modell die Stelle wiedererkennt.
PROMPT_ZITAT_WOERTER = 25

#: Staerke, ab der eine Zuordnung gespeichert wird (Birk 07.10.2026: keine
#: feste Prozentzahl, sondern eine Schwelle je Zuordnung). 1 = passt am
#: Rand, 3 = passt sehr genau -- 1 bleibt weg, 2 und 3 werden gespeichert.
STAERKE_MIN = 2

#: Flach wie ueberall (global-constraints.md 'Schema'): drei gleich lange
#: Listen statt einer Liste aus Objekten. EIN Aufruf gilt fuer EIN Ziel
#: (eine Szene oder eine Figur, siehe ``_ziele``) -- die Zuordnung braucht
#: deshalb keine Szenennummer/Figurenname mehr, nur noch die Nummer der
#: Materialstelle, eine Staerke und eine Begruendung.
ZIEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eintrag_nummern", "staerke", "begruendungen"],
    "properties": {
        "eintrag_nummern": {"type": "array", "items": {"type": "integer"}},
        "staerke": {"type": "array", "items": {"type": "integer"}},
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

#: Was ``starte`` liefert, wenn ein anderer Vorschlagslauf die gemeinsame
#: Sperre haelt (30.09.2026, C7). Bewusst NICHT ``None``: ``None`` heisst
#: "es gab nichts anzustossen", und ``knoepfe.starte_schaerfung`` spielt
#: darauf die vorhandene Lage aus. Gemerkt heisst "kommt noch".
GEMERKT = "gemerkt"

#: Die Wartemeldung. Sie sagt, was passiert -- nicht, dass nichts passiert.
TEXT_GEMERKT = (
    "Ich denke noch ueber etwas anderes nach. Sobald ich damit fertig bin, "
    "lege ich euer Material neben eure Geschichte."
)

#: Die Fortschrittsmeldung waehrend des Laufs (Birk 07.10.2026, Anforderung
#: 4: "die Gruppe wartet nicht stumm"). Wird aktualisiert, sobald ein
#: Ziel-Aufruf (Szene oder Figur) fertig ist, und am Ende geloescht.
_TEXT_SCHAERFUNG_FORTSCHRITT = "🔍 Ich ordne euer Material zu: {erledigt}/{gesamt} …"


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


def _erfundenes_zeilen(conn, chat_id: int) -> list[str]:
    """Das Erfundene: Setting, Figuren, Geschichte, Szenen -- geteilt von
    ``baue_nutzertext`` (der volle Schnappschuss) und
    ``_baue_nutzertext_ziel`` (der enge Je-Ziel-Aufruf)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen: list[str] = []
    if stand and (stand["rahmen"] or "").strip():
        zeilen.append(T._ZEILE_SETTING.format(rahmen=stand["rahmen"].strip()))
    if stand and "geschichte" in stand.keys() and (stand["geschichte"] or "").strip():
        zeilen.append(T._GESCHICHTE_KOPF + stand["geschichte"].strip())

    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append(T._FIGUREN_KOPF)
        for figur in figuren:
            beschreibung = (figur["beschreibung"] or "").strip()
            zeilen.append(f"- {figur['name']}" + (f" -- {beschreibung}" if beschreibung else ""))

    szenen = repo.hole_szenen(conn, chat_id)
    if szenen:
        zeilen.append(T._SZENEN_KOPF)
        for szene in szenen:
            teile = [f"[{szene['nummer']}]"]
            if szene["titel"]:
                teile.append(szene["titel"])
            if szene["was_passiert"]:
                teile.append(szene["was_passiert"])
            if szene["form"]:
                teile.append(T._ZEILE_FORM.format(form=szene["form"]))
            zeilen.append(" — ".join(teile))
    return zeilen


def _material_zeilen(eintraege: list[dict], *, woerter: int | None = None) -> list[str]:
    """Die Materialliste mit Kopf -- geteilt von ``baue_nutzertext`` (volles
    Zitat) und ``_baue_nutzertext_ziel`` (``woerter`` kuerzt es, Robo Punkt 3:
    Eingabe je Ziel-Aufruf verkleinern)."""
    zeilen = [T._MATERIAL_KOPF]
    # Die Zusammenfassung gehoert dem Interview, nicht der Zeile: elf geprueft
    # Themen desselben Interviews schrieben sie elfmal (Audit-Befund M1,
    # 06.09.2026 -- 7.700 Zeichen Dublette in einem 9.000-Zeichen-Prompt).
    # Jetzt einmal je Interview, als eigene Zeile darueber.
    letztes_interview = None
    for eintrag in eintraege:
        if eintrag["interview"] != letztes_interview:
            letztes_interview = eintrag["interview"]
            if eintrag["zusammenfassung"]:
                zeilen.append(T._ZEILE_WORUM.format(
                    interview=eintrag["interview"],
                    zusammenfassung=eintrag["zusammenfassung"],
                ))
        zitat_text = _gekuerzt(eintrag["zitat"], woerter) if woerter else eintrag["zitat"]
        zeilen.append(T._ZEILE_EINTRAG.format(
            nummer=eintrag["nummer"], interview=eintrag["interview"],
            thema=eintrag["thema"], zitat=zitat_text,
        ))
    return zeilen


def baue_nutzertext(conn, chat_id: int, eintraege: list[dict]) -> str:
    """Erst das Erfundene (Setting, Figuren, Geschichte, Szenen), dann das
    Material mit Nummern, volles Zitat.

    Oeffentlich wie ``verdichter.baue_nutzertext``, damit ein Pruefskript
    (``scripts/erzeuge_prompts.py``) denselben Text bauen kann wie der
    Betrieb -- unveraendert seit vor dem Umbau 07.10.2026 auf Je-Ziel-
    Aufrufe (``_baue_nutzertext_ziel``), die dieselben Bausteine nutzen."""
    zeilen = _erfundenes_zeilen(conn, chat_id)
    zeilen.append("")
    zeilen.extend(_material_zeilen(eintraege))
    return "\n".join(zeilen)


def _hintergrund_zeilen(conn, chat_id: int) -> list[str]:
    """Zusaetzlicher Kontext NUR fuer den Je-Ziel-Aufruf (Birk 07.10.2026,
    Anforderung 3): die Verdichtung der Phase-1-Diskussion und Kernthema/
    Begriffe aus dem Arbeitsstand -- NIE Transkripte, NIE Interviews. Leer,
    wenn noch nichts davon existiert (z. B. eine Gruppe ohne Diskussionsphase)."""
    zeilen: list[str] = []
    diskussion = repo.diskussion_verdichtung_text(conn, chat_id)
    if diskussion and diskussion.strip():
        zeilen.append(T._HINTERGRUND_DISKUSSION.format(text=diskussion.strip()))
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand:
        if "kernthema" in stand.keys() and (stand["kernthema"] or "").strip():
            zeilen.append(T._HINTERGRUND_KERNTHEMA.format(text=stand["kernthema"].strip()))
        if "begriffe" in stand.keys() and (stand["begriffe"] or "").strip():
            zeilen.append(T._HINTERGRUND_BEGRIFFE.format(text=stand["begriffe"].strip()))
    return zeilen


def _ziel_beschreibung(ziel: dict) -> str:
    """Sprachschicht T (AGENTS.md): die Bezeichnung geht in den Modell-Prompt
    und muss deshalb lokalisiert sein, nicht hart Deutsch -- Fund
    ``test_padua_ist_frei_von_deutsch`` (07.10.2026): "Szene"/"Figur" roh im
    englischen Nutzertext."""
    from interview_theater import szene as szene_modul

    if ziel["art"] == "szene":
        teile = [szene_modul.T._SZENE_MIT_NUMMER.format(nummer=ziel["nummer"])]
        if ziel["titel"]:
            teile.append(ziel["titel"])
        if ziel["was_passiert"]:
            teile.append(ziel["was_passiert"])
        if ziel["form"]:
            teile.append(T._ZEILE_FORM.format(form=ziel["form"]))
        return " — ".join(teile)
    teile = [T._ZIEL_FIGUR_LABEL.format(name=ziel["name"])]
    if ziel["beschreibung"]:
        teile.append(ziel["beschreibung"])
    return " — ".join(teile)


def _ziele(conn, chat_id: int) -> list[dict]:
    """Je eine Zeile pro Szene und pro Figur -- das sind die Ziele, fuer die
    ``mappe`` je einen eigenen, engen Aufruf macht (Umbau 07.10.2026)."""
    ziele: list[dict] = []
    for szene in repo.hole_szenen(conn, chat_id):
        if szene["nummer"] is None:
            continue
        ziele.append({
            "art": "szene", "id": szene["id"], "nummer": szene["nummer"],
            "titel": szene["titel"] or "", "was_passiert": szene["was_passiert"] or "",
            "form": szene["form"] or "",
        })
    for figur in repo.figuren(conn, chat_id):
        ziele.append({
            "art": "figur", "id": figur["id"], "name": figur["name"],
            "beschreibung": (figur["beschreibung"] or "").strip(),
        })
    for ziel in ziele:
        ziel["beschreibung_text"] = _ziel_beschreibung(ziel)
    return ziele


def _baue_nutzertext_ziel(conn, chat_id: int, eintraege: list[dict], ziel: dict) -> str:
    """Der enge Nutzertext EINES Ziel-Aufrufs: Erfundenes, Hintergrund
    (Anforderung 3), das EINE Ziel, dann das Material mit gekuerztem Zitat
    (Robo Punkt 3: Eingabe verkleinern)."""
    zeilen = _erfundenes_zeilen(conn, chat_id)
    hintergrund = _hintergrund_zeilen(conn, chat_id)
    if hintergrund:
        zeilen.append("")
        zeilen.extend(hintergrund)
    zeilen.append("")
    zeilen.append(T._ZIEL_ZEILE.format(beschreibung=ziel["beschreibung_text"]))
    zeilen.append("")
    zeilen.extend(_material_zeilen(eintraege, woerter=PROMPT_ZITAT_WOERTER))
    return "\n".join(zeilen)


#: Die Koepfe und Zeilen des Nutzertexts (W3). ``_ZEILE_WORUM`` und
#: ``_ZEILE_EINTRAG`` teilt sich ``kernzitate`` -- dieselbe Materialliste.
_ZEILE_SETTING = "Setting: {rahmen}"
_GESCHICHTE_KOPF = "Geschichte:\n"
_FIGUREN_KOPF = "Figuren (Namen genau so schreiben):"
_SZENEN_KOPF = "Szenen (Nummer verwenden):"
_ZEILE_FORM = "Form: {form}"
_MATERIAL_KOPF = "Material (nur hieraus waehlen, nach Nummer):"
_ZEILE_WORUM = "\n{interview} -- worum es darin geht: {zusammenfassung}"
_ZEILE_EINTRAG = '[{nummer}] {interview} | Thema: {thema} | Zitat: "{zitat}"'
#: Anforderung 3 (Birk 07.10.2026): zusaetzlicher Hintergrund je Ziel-Aufruf.
_HINTERGRUND_DISKUSSION = "\nHintergrund -- Verdichtung der Diskussion aus Phase 1:\n{text}"
_HINTERGRUND_KERNTHEMA = "\nHintergrund -- Kernthema der Gruppe:\n{text}"
_HINTERGRUND_BEGRIFFE = "\nHintergrund -- Begriffe aus Phase 1:\n{text}"
_ZIEL_ZEILE = "Ziel -- ordne NUR fuer dieses eine Ziel zu: {beschreibung}"
_ZIEL_FIGUR_LABEL = "Figur {name}"


def _liste(ergebnis: dict, name: str) -> list:
    wert = ergebnis.get(name)
    return list(wert) if isinstance(wert, list) else []


def _mappe_ziel(klm, conn, e, chat_id: int, ziel: dict, eintraege: list[dict],
                nach_nummer: dict) -> list[dict]:
    """EIN enger Aufruf fuer EIN Ziel (Szene oder Figur) -- liefert die
    Zuordnungen, die diesem Ziel zugeschrieben wurden (Staerke >= ``STAERKE_MIN``).

    Eigener Timeout/Wartezeiten/Modell (``CLAUDE_TIMEOUT_S``,
    ``CLAUDE_WARTEZEITEN``, ``IT_SCHAERFUNG_MODELL``) -- unabhaengig vom
    Gespraechsmodell derselben Gruppe (Robo 07.10.2026, BINDEND)."""
    art = f"{ART}_{ziel['art']}_{ziel['id']}"
    nutzer = _baue_nutzertext_ziel(conn, chat_id, eintraege, ziel)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id, prompt(), nutzer, ZIEL_SCHEMA, art,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
        modell=e.erkenner_modell,
        claude_modell=getattr(e, "schaerfung_modell", None) or szene_claude.MODELL_VORGABE,
        timeout=CLAUDE_TIMEOUT_S, wartezeiten=CLAUDE_WARTEZEITEN,
    )

    nummern = _liste(ergebnis, "eintrag_nummern")
    staerken = _liste(ergebnis, "staerke")
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
        try:
            staerke = int(staerken[lauf]) if lauf < len(staerken) else 0
        except (TypeError, ValueError):
            staerke = 0
        if staerke < STAERKE_MIN:
            continue
        zuordnung = {
            "verdichtung_thema_id": eintrag["thema_id"],
            "staerke": staerke,
            "begruendung": (
                str(begruendungen[lauf] or "").strip()
                if lauf < len(begruendungen) else None
            ),
        }
        if ziel["art"] == "szene":
            zuordnung["szene_id"] = ziel["id"]
        else:
            zuordnung["figur_id"] = ziel["id"]
        zuordnungen.append(zuordnung)
    return zuordnungen


def _aktualisiere_fortschritt(tg, chat_id: int, message_id, erledigt: int, gesamt: int) -> None:
    try:
        tg.aendere_text(
            chat_id, message_id,
            T._TEXT_SCHAERFUNG_FORTSCHRITT.format(erledigt=erledigt, gesamt=gesamt),
        )
    except Exception:
        log.exception("Fortschrittsmeldung der Schaerfung fehlgeschlagen, chat_id=%s", chat_id)


def mappe(klm, conn, e, chat_id: int, *, tg=None, fortschritt_message_id=None) -> tuple[int, int]:
    """Der eigentliche Lauf: je Szene und je Figur ein eigener, enger Aufruf
    (parallel, ``PARALLEL_AUFRUFE``), dann speichern. Liefert
    ``(Anzahl Zuordnungen, Runde)``.

    Ohne Material (noch keine geprueften Themen) oder ohne Ziele (noch keine
    Szene/Figur) gibt es keinen Aufruf -- ein Modell, das aus nichts
    zuordnen soll, erfindet.

    ``tg``/``fortschritt_message_id`` (Birk Anforderung 4, "Gruppe wartet
    nicht stumm"): wenn gesetzt, wird nach jedem fertigen Ziel-Aufruf die
    Fortschrittsmeldung aktualisiert -- optional, damit bestehende direkte
    Aufrufer (Tests, Messskripte) unveraendert funktionieren."""
    eintraege = _eintraege(conn, chat_id)
    if not eintraege:
        return 0, 0
    # Der Tagesdeckel gilt, sobald es ueberhaupt Material gibt -- VOR der
    # Ziel-Suche, sonst bliebe eine Gruppe ohne Szene/Figur (noch) beim
    # Deckel still statt die Pausenmeldung zu bekommen (gemessen:
    # tests/test_kostendeckel.py::test_schaerfung_meldet_die_pause_statt_zu_schweigen,
    # Verhalten von vor dem Umbau 07.10.2026 auf Je-Ziel-Aufrufe).
    from interview_theater import kosten

    kosten.pruefe(conn, chat_id, e)
    ziele = _ziele(conn, chat_id)
    if not ziele:
        return 0, 0

    runde = repo.letzte_schaerfungsrunde(conn, chat_id) + 1
    nach_nummer = {eintrag["nummer"]: eintrag for eintrag in eintraege}
    alle_zuordnungen: list[dict] = []
    fortschritt_sperre = threading.Lock()
    erledigt = 0

    def _lauf_eines_ziels(ziel):
        nonlocal erledigt
        from interview_theater import kosten

        try:
            ergebnis = _mappe_ziel(klm, conn, e, chat_id, ziel, eintraege, nach_nummer)
        except kosten.KostendeckelErreicht:
            # Nicht pro Ziel abfangen: der Tagesdeckel betrifft die ganze
            # Gruppe, nicht nur dieses eine Ziel. Durchreichen, damit
            # ``_lauf`` wie vor dem Umbau die Pausenmeldung schickt
            # (``kosten.melde_pause_wenn_deckel``), statt stillschweigend
            # "nichts passt" zu melden.
            raise
        except Exception:
            log.exception(
                "Schaerfung je Ziel fehlgeschlagen, chat_id=%s, ziel=%s",
                chat_id, ziel.get("beschreibung_text"),
            )
            ergebnis = []
        with fortschritt_sperre:
            erledigt += 1
            alle_zuordnungen.extend(ergebnis)
            if tg is not None and fortschritt_message_id is not None:
                _aktualisiere_fortschritt(tg, chat_id, fortschritt_message_id, erledigt, len(ziele))
        return ergebnis

    with ThreadPoolExecutor(max_workers=min(PARALLEL_AUFRUFE, len(ziele))) as pool:
        list(pool.map(_lauf_eines_ziels, ziele))

    anzahl = repo.lege_schaerfung_an(conn, chat_id, alle_zuordnungen, runde=runde)
    if anzahl:
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            T._JOURNAL_RUNDE.format(runde=runde, anzahl=anzahl),
            quelle="schaerfung",
        )
    return anzahl, runde


def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: mappen, die eine Zeile schicken, weitergehen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still: sie wartet gerade
    darauf (SPEC § 11.1). Die Nachbereitung laeuft in jedem Fall -- der Weg
    durch die Phase darf an einem Mapping-Lauf nicht haengenbleiben.

    **Die gemeinsame Vorschlagssperre wird zuletzt freigegeben** (30.09.2026,
    C7): erst wenn auch die Nachbereitung durch ist, steht die Gruppe nicht
    mehr mitten in einer Frage -- ein Szenenfolge-Vorschlag, der sich
    dazwischen legt, war der gemessene Fehler."""
    anzahl = 0
    fortschritt_id = None
    try:
        fortschritt_id = tg.sende(
            chat_id, T._TEXT_SCHAERFUNG_FORTSCHRITT.format(erledigt=0, gesamt="?"),
        )
    except Exception:
        log.exception("Fortschrittsmeldung der Schaerfung fehlgeschlagen, chat_id=%s", chat_id)

    try:
        try:
            anzahl, _ = mappe(klm, conn, e, chat_id, tg=tg, fortschritt_message_id=fortschritt_id)
            meldung = T.MELDUNG.format(anzahl=anzahl) if anzahl else T.MELDUNG_LEER
        except Exception:
            log.exception("Schaerfung fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "schaerfung_fehlgeschlagen", "Schaerfung fehlgeschlagen",
                )
            except Exception:
                log.exception("Vorfall zur Schaerfung nicht schreibbar")
            # Tagesdeckel (Karte Padua S): die Gruppe wartet schon auf
            # "Schaerfung laeuft, einen Moment" -- bei Deckel bekommt sie
            # wenigstens die Pausenmeldung statt gar nichts. Ohne Deckel
            # bleibt es beim bisherigen stillen Fehlschlag.
            from interview_theater import kosten

            kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
            meldung = None
        finally:
            if fortschritt_id is not None:
                try:
                    tg.loesche_nachrichten(chat_id, [fortschritt_id])
                except Exception:
                    log.exception(
                        "Fortschrittsmeldung der Schaerfung nicht loeschbar, chat_id=%s",
                        chat_id,
                    )
        if meldung:
            try:
                message_id = tg.sende(chat_id, meldung)
                repo.merke_bot_zeile(conn, chat_id, message_id, e, meldung)
            except Exception:
                log.exception(
                    "Schaerfungs-Meldung fehlgeschlagen, chat_id=%s", chat_id
                )
        if nachbereitung is not None:
            try:
                nachbereitung()
            except Exception:
                log.exception(
                    "Nachbereitung der Schaerfung gescheitert, chat_id=%s", chat_id
                )
    finally:
        vorschlagssperre.gib_frei(chat_id)


def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt das Mapping an einen eigenen Thread ab -- dasselbe Muster wie
    ``kernzitate.starte`` und ``sprachprofil.starte`` (Zusage 2).

    Liefert den Thread, ``GEMERKT``, wenn ein anderer Vorschlagslauf gerade
    die gemeinsame Sperre haelt (der Auftrag laeuft dann automatisch nach),
    oder ``None``, wenn es nichts anzustossen gab.

    **Die Sperre ist dieselbe wie die der Szenenfolge** (30.09.2026, C7,
    ``vorschlagssperre.py``). Bis dahin hatte dieser Lauf gar keine, und der
    Phaseneintritt legte seine Vorschlaege zeitgleich ueber einen laufenden
    Szenenfolge-Vorschlag."""
    if klm is None:
        log.error("Schaerfung ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    if not vorschlagssperre.nimm_oder_merke(
        chat_id, ART, lambda: starte(conn, tg, klm, e, chat_id, nachbereitung),
    ):
        try:
            gemerkt = T.TEXT_GEMERKT
            message_id = tg.sende(chat_id, gemerkt)
            repo.merke_bot_zeile(conn, chat_id, message_id, e, gemerkt)
        except Exception:
            log.exception("Wartemeldung der Schaerfung fehlgeschlagen, chat_id=%s",
                          chat_id)
        return GEMERKT
    # Sperr-Leck-Fund (30.09.2026): auch der Thread-Aufbau selbst steht unter
    # der Wache -- eine Ausnahme beim Anlegen des ``Thread``-Objekts darf die
    # Sperre nicht fuer die Prozesslaufzeit belegt lassen.
    try:
        thread = threading.Thread(
            target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
        )
        thread.start()
    except BaseException:
        vorschlagssperre.gib_frei(chat_id)
        raise
    return thread


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------


def _stelle(conn, chat_id: int, eintrag) -> str:
    from interview_theater import kontext

    name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
    zeile = f'{name} "{eintrag["thema"]}": "{eintrag["zitat"]}"'
    if eintrag["begruendung"]:
        zeile += T._ZEILE_VORSCHLAG.format(begruendung=eintrag["begruendung"])
    return zeile


#: Die Bausteine der Vorschlagsnachrichten im Chat.
_JOURNAL_RUNDE = "Schaerfung Runde {runde}: {anzahl} Stellen zugeordnet"
_ZEILE_VORSCHLAG = "\n  Vorschlag: {begruendung}"
_STELLE = "Stelle"
_UEBERSCHRIFT = "{kopf} — was aus den Interviews dazupasst"
_FRAGE_SZENE = "\nSoll das in die Szene?"
_FRAGE_FIGUR = "\nSoll das zu dieser Figur?"


#: Wie viele Stellen hoechstens in EINER Vorschlagsnachricht/Seite stehen
#: (06.09.2026, Analyse Abschnitt 2; seit 07.10.2026 eine Seitengroesse,
#: keine Gesamtgrenze mehr -- siehe ``offene_stellen``/``offene_stellen_seite``).
#: Der gemessene Fall waren Bloecke von 712 und 1280 Zeichen mit
#: vollstaendigen Zitaten und **einer** globalen Ja/Nein-Frage -- die Wall of
#: Text. Drei ist die Zahl, die auch die Fragenauswahl und die
#: Geschichte-Richtungen benutzen.
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
    """ALLE noch offenen Schaerfungen zu einer Szene oder Figur, staerkste
    zuerst (Birk 07.10.2026: ``MAX_STELLEN`` war nur die Anzeige -- die
    Zuordnung und Speicherung liefen schon vorher darueber hinaus; eine
    Gruppe mit 16 zugeordneten Stellen sah nur 3 und die restlichen 13
    blieben unsichtbar, bis die ersten drei abgearbeitet waren).

    Deterministisch aus der Datenbank, kein Modellaufruf: das Mapping ist
    schon gelaufen. Sortiert nach Staerke absteigend (eine alte Zeile ohne
    Staerke -- vor diesem Umbau -- gilt als 0 und steht hinten), dann Runde,
    dann id. Anzeige-Seiten baut ``offene_stellen_seite``."""
    eintraege = [
        z for z in repo.schaerfungen(conn, chat_id, szene_id=szene_id, figur_id=figur_id)
        if not z["uebernommen_am"]
    ]
    return sorted(eintraege, key=lambda z: (-(z["staerke"] or 0), z["runde"], z["id"]))


def offene_stellen_seite(
    conn, chat_id: int, szene_id=None, figur_id=None, versatz: int = 0,
) -> tuple[list, int]:
    """Eine Anzeige-Seite der offenen Stellen: ``(stellen, gesamt)`` --
    hoechstens ``MAX_STELLEN`` Eintraege ab ``versatz``, plus die Gesamtzahl
    fuer den "Mehr zeigen"-Knopf (Birk 07.10.2026, Anforderung 1: alle
    zugeordneten Stellen muessen sichtbar werden, ohne Wall of Text)."""
    alle = offene_stellen(conn, chat_id, szene_id=szene_id, figur_id=figur_id)
    return alle[versatz:versatz + MAX_STELLEN], len(alle)


def option(conn, chat_id: int, eintrag) -> tuple[str, str]:
    """Eine Stelle als Menue-Option: ``(Titel, Beschreibung)``.

    Der Titel ist zugleich die Knopfbeschriftung (``vorschlag.menuetext`` +
    ``knoepfe.MENUE_KNOPF_LAENGE``) -- Knopf N und Punkt N meinen dadurch
    dasselbe, wie bei ``stile.reihenfolge_mit_vorschlag``. Die Beschreibung
    traegt das gekuerzte Zitat und, wenn es eine gibt, die Begruendung."""
    from interview_theater import kontext

    name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
    titel = str(eintrag["thema"] or name or T._STELLE).strip()
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
    from interview_theater import szene as szene_modul

    kopf = szene_modul.T._SZENE_MIT_NUMMER.format(nummer=szene["nummer"])
    if szene["titel"]:
        kopf += f": {szene['titel']}"
    return T._UEBERSCHRIFT.format(kopf=kopf)


def figurueberschrift(figur) -> str:
    return T._UEBERSCHRIFT.format(kopf=figur["name"])


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
        from interview_theater import szene as szene_modul

        return szene_modul.T._SZENE_MIT_NUMMER.format(nummer=szene["nummer"])
    if eintrag["figur_id"]:
        figur = repo.hole_figur_nach_id(conn, eintrag["figur_id"])
        if figur is None:
            return None
        _ergaenze_figur(conn, chat_id, figur, [eintrag])
        repo.merke_schaerfung_uebernommen(conn, eintrag["id"])
        return str(figur["name"])
    return None


def uebernimm_stellen(conn, chat_id: int, ids: list[int]) -> int:
    """"Diese uebernehmen", seitengebunden (Birk 07.10.2026, Anforderung 1):
    uebernimmt GENAU die Stellen aus ``ids`` -- die einer Anzeige-Seite,
    nicht alle, die je fuer dieses Ziel zugeordnet wurden (das waere der
    gemessene Fehler von vorher: ein Klick auf 3 sichtbare Stellen uebernahm
    heimlich auch 13 unsichtbare). Eine Stelle, die zu Szene UND Figur
    gehoert, ergaenzt beide -- wie ``uebernimm_szene``/``uebernimm_figur``."""
    alle = {z["id"]: z for z in repo.schaerfungen(conn, chat_id)}
    eintraege = [alle[i] for i in ids if i in alle and not alle[i]["uebernommen_am"]]
    if not eintraege:
        return 0
    szenen_gruppen: dict[int, list] = {}
    figuren_gruppen: dict[int, list] = {}
    for z in eintraege:
        if z["szene_id"]:
            szenen_gruppen.setdefault(z["szene_id"], []).append(z)
        if z["figur_id"]:
            figuren_gruppen.setdefault(z["figur_id"], []).append(z)
    for szene_id, gruppe in szenen_gruppen.items():
        szene = repo.hole_szene(conn, szene_id)
        if szene is not None:
            _ergaenze_szene(conn, szene, gruppe)
    for figur_id, gruppe in figuren_gruppen.items():
        figur = repo.hole_figur_nach_id(conn, figur_id)
        if figur is not None:
            _ergaenze_figur(conn, chat_id, figur, gruppe)
    for z in eintraege:
        repo.merke_schaerfung_uebernommen(conn, z["id"])
    return len(eintraege)


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
    zeilen.append(T._FRAGE_SZENE)
    return "\n".join(zeilen)


def figurvorschlag(conn, chat_id: int, figur) -> str | None:
    """Dasselbe je Figur: die Stellen, aus denen sie sprechen koennte."""
    eintraege = offene_stellen(conn, chat_id, figur_id=figur["id"])
    if not eintraege:
        return None
    zeilen = [figurueberschrift(figur) + ":"]
    zeilen.extend(f"- {_stelle(conn, chat_id, z)}" for z in eintraege)
    zeilen.append(T._FRAGE_FIGUR)
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


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

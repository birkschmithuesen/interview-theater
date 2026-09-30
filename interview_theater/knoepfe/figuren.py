"""Phase 4: die Figuren, in zwei Ebenen.

**Ebene 1** ist die Liste: wie viele Figuren, wie heissen sie
(``biete_figurenanzahl``, ``biete_figurenliste``). **Ebene 2** geht Figur fuer
Figur -- aus welchem Interview spricht sie, wie klingt sie
(``stelle_figur_vor``, ``stelle_stil_vor``) -- und laeuft erst ab Phase 6
(``ebene2_erlaubt``): in Phase 4 danach zu fragen waere die Ruecklenkung aufs
Material, die der Phasen-Umbau vermeidet.

Dazu die Kette durch Phase 4 (``_kette_weiter``): Kernthema -> Kernfrage ->
Filter am Kernthema -> Figurenanzahl -> Figurenliste, und die zufaellige
Zuordnung von Interviews auf Figuren (``ordne_figuren_zufaellig_zu``) als der
eine Druck statt zwoelf Modellaufrufen.
"""

import random
import re

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ART_ANDERS, ART_EIGENE, ART_FIGUREN_ANZAHL, ART_FIGUREN_ANZAHL_FREI,
    ART_FIGUREN_ANZAHL_MENU, ART_FIGUREN_NAMEN_MENU, ART_FIGUREN_ZUFALL,
    ART_FIGUR_DUKTUS_MENU, ART_FIGUR_ENTFERNEN, ART_FIGUR_INTERVIEW,
    ART_FIGUR_INTERVIEW_MENU, ART_FIGUR_PASST, ART_FIGUR_STIL,
    ART_FIGUR_STIL_FREI, ART_SCHLAG_VOR, ART_SPEICHERN, ART_WIR_ZUERST,
    FIGURENZAHLEN, FIGURENZAHL_MAX, FIGURENZAHL_MIN, MENUE_KNOPF_LAENGE,
    PHASE_SCHAERFUNG, PHASE_SETTING, T, TRENNER, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _nimm_alte_leiste_ab, _sende_knoepfe,
    _starte_auftrag, speicherleiste,
)


def _ersetze_namen(conn, tg, chat_id: int, neuer_name: str) -> str:
    """Ersetzt den Namen EINER Zeile im Figuren-Entwurf und stellt Ebene 1
    neu hin (05.09.2026 abends).

    Welche Zeile gemeint ist, steht im Merkposten
    ``arbeitsstand.figur_aktuell`` (ihr Index) -- der Knopf traegt nur den
    Namen, damit auch ein langer Name die 64 Bytes nie beruehrt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    roh_index = (stand["figur_aktuell"] if stand else "") or ""
    zeilen = _entwurfszeilen(conn, chat_id)
    if not roh_index.isdigit() or int(roh_index) >= len(zeilen) or not neuer_name:
        log.error("Namensknopf ohne Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    index = int(roh_index)
    alt_zeile = zeilen[index]
    # Nur der Namensteil wird getauscht -- Satz und Interview bleiben, sie
    # sind die Arbeit der Gruppe, der Name war nur ihre Beschriftung.
    rest = alt_zeile.split("—", 1)
    if len(rest) == 1:
        rest = alt_zeile.split(" - ", 1)
        zeilen[index] = (
            f"{neuer_name} - {rest[1].lstrip()}" if len(rest) > 1 else neuer_name
        )
    else:
        zeilen[index] = f"{neuer_name} — {rest[1].lstrip()}"
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", None)
    biete_figurenliste(conn, tg, chat_id, "\n".join(zeilen))
    return T._TEXT_NAME_GEAENDERT_QUITTUNG


def _figurenzeile(namen: list[str]) -> str:
    """Dieselbe Zeile, die der Erkenner baut (``erkenner._figuren_zeile``) --
    von dort geholt statt hier zweitgepflegt: die Gruppe soll nicht zwei
    Formulierungen fuer dasselbe Ereignis sehen."""
    from interview_theater import erkenner

    return erkenner._figuren_zeile(namen)

#: Merkposten je Gruppe: die naechste freie Nachricht ist die Figurenanzahl
#: (nach "Andere Zahl"). Wie ``szenenfolge._regienotiz_erwartet`` bewusst im
#: Prozess und nicht in der Datenbank: er gilt fuer genau die naechste
#: Nachricht, ein Neustart dazwischen macht daraus wieder einen normalen
#: Gespraechsbeitrag -- und das ist die richtige Fehlerrichtung.
_anzahl_erwartet: set[int] = set()


def erwarte_figurenanzahl(chat_id: int) -> None:
    """Merkt: die naechste Nachricht dieser Gruppe ist die Figurenanzahl."""
    _anzahl_erwartet.add(chat_id)


def nimm_figurenanzahl_erwartung(chat_id: int) -> bool:
    """Liefert True, wenn eine Zahl erwartet wird -- und vergisst es dabei.

    Einmalig wie ``szenenfolge.nimm_regienotiz``: sonst wuerde jede weitere
    Nachricht der Gruppe als Figurenanzahl gelesen."""
    if chat_id not in _anzahl_erwartet:
        return False
    _anzahl_erwartet.discard(chat_id)
    return True


def _zahl_aus(text: str) -> int | None:
    """Die erste Zahl in einer Nachricht, wenn sie im erlaubten Bereich liegt.

    Toleriert \"wir haetten gern 4\" und \"4 Figuren bitte\" -- die Gruppe
    tippt keine blanken Ziffern. Ausgeschrieben zaehlt auch: \"vier\" ist eine
    Zahl, und wer eine Zahl sagt, meint eine."""
    treffer = re.search(r"\d{1,2}", text or "")
    if treffer is not None:
        zahl = int(treffer.group(0))
    else:
        worte = {
            "eine": 1, "einer": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4,
            "fuenf": 5, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
            "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12, "zwölf": 12,
        }
        gefunden = [
            wert for wort, wert in worte.items()
            if re.search(rf"\b{wort}\b", (text or "").lower())
        ]
        if not gefunden:
            return None
        zahl = gefunden[0]
    if FIGURENZAHL_MIN <= zahl <= FIGURENZAHL_MAX:
        return zahl
    return None


def biete_figurenanzahl(conn, tg, chat_id: int, text: str | None = None) -> int:
    """Die eigene Frage vor der Figurenliste: 1-6 und \"Andere Zahl\".

    Deterministisch, kein Modellaufruf (Zusage 2). Sie steht bewusst VOR dem
    Listenvorschlag: solange die Zahl aus einem Prompt kam, war sie eine
    Vorgabe des Bots -- jetzt ist sie eine Entscheidung der Gruppe, und der
    Vorschlag richtet sich danach (``ANWEISUNG_FIGURENZAHL``)."""
    for art in (ART_FIGUREN_ANZAHL, ART_FIGUREN_ANZAHL_FREI):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    leiste = [
        (zahl, _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL, zahl)))
        for zahl in FIGURENZAHLEN
    ]
    leiste.append(
        (
            T._TEXT_FIGUREN_ANZAHL_FREI_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_FREI, None)),
        )
    )
    message_id = _sende_knoepfe(conn, tg, chat_id, text or T._TEXT_FIGUREN_ANZAHL_ERSTFRAGE, leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id


def uebernimm_figurenanzahl(conn, tg, klm, e, chat_id: int, anzahl: int) -> None:
    """Speichert die Anzahl und laesst im Thread eine Liste mit genau so
    vielen Figuren vorschlagen -- der eine Weg, auf dem eine Zahl wirkt,
    egal ob sie aus einem Knopf oder aus einer Nachricht kam."""
    repo.setze_arbeitsstand(conn, chat_id, "figuren_anzahl", str(anzahl))
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_FIGURENANZAHL.format(anzahl=anzahl),
        quelle="knopf",
    )
    _starte_auftrag(
        conn, tg, klm, e, chat_id, T.ANWEISUNG_FIGURENZAHL.format(anzahl=anzahl),
    )


def _kette_weiter(conn, tg, klm, e, chat_id: int, art: str) -> None:
    """Was nach dem Speichern einer Kettenart passiert."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if art == "rahmen":
        # Das Setting steht -- jetzt die Figuren, und wie viele es sein
        # sollen, sagt die Gruppe (deterministisch, kein Modellaufruf).
        biete_figurenanzahl(conn, tg, chat_id)
        return
    if art == "kernthema":
        _starte_auftrag(
            conn, tg, klm, e, chat_id,
            T.ANWEISUNG_KERNFRAGE.format(
                kernthema=(stand["kernthema"] if stand else "") or ""
            ),
        )
        return
    # Die Kernfrage steht: jetzt wird am Kernthema gefiltert -- still, im
    # Thread, ohne Liste im Chat. Danach kommt die Frage nach der
    # Figurenanzahl aus der Nachbereitung heraus, damit sie NACH der einen
    # Auswahl-Zeile steht und nicht davor.
    from interview_theater import kernzitate

    def _danach() -> None:
        biete_figurenanzahl(conn, tg, chat_id)

    thread = kernzitate.starte(conn, tg, klm, e, chat_id, nachbereitung=_danach)
    if thread is None:
        # Ohne Sprachmodell (Tests, ein Programmierfehler) bleibt der Weg
        # trotzdem offen: die Frage nach der Anzahl kommt sofort.
        biete_figurenanzahl(conn, tg, chat_id)


def _entwurfszeilen(conn, chat_id: int) -> list[str]:
    """Die Zeilen des aktuellen Figuren-Entwurfs
    (``arbeitsstand.figuren_entwurf``), eine je Figur."""
    from interview_theater import vorschlag

    stand = repo.hole_arbeitsstand(conn, chat_id)
    return vorschlag.zeilen(stand["figuren_entwurf"] if stand else "")


def biete_figurenliste(conn, tg, chat_id: int, wert: str, text: str | None = None) -> int:
    """Ebene 1: die Figurenliste mit "Anzahl aendern" · "Namen aendern" und
    der Grundleiste darunter (05.09.2026 abends, Birk).

    Der Entwurf wird dabei im Arbeitsstand festgehalten
    (``figuren_entwurf``) -- nicht als Figuren: erst "Gefaellt uns, weiter"
    legt sie an. Sonst staenden nach drei Runden Namensaenderung neun Figuren
    in der Datenbank, von denen die Gruppe sechs nie gewollt hat."""
    repo.setze_arbeitsstand(conn, chat_id, "figuren_entwurf", wert)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FIGUREN_ANZAHL_MENU)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FIGUREN_NAMEN_MENU)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_EIGENE)
    leiste = [
        (
            T._TEXT_FIGUREN_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_MENU, None)),
        ),
        (
            T._TEXT_FIGUREN_NAMEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_NAMEN_MENU, None)),
        ),
    ] + speicherleiste(conn, chat_id, "figuren", wert)
    message_id = _sende_knoepfe(conn, tg, chat_id, text or wert, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id
    )
    return message_id


def _uebernimm_figurenliste(conn, tg, chat_id: int, wert: str) -> str:
    """"Gefaellt uns, weiter" (oder "Passt, aber anders") auf der
    Figurenliste: ALLE Figuren des Entwurfs anlegen und Ebene 2 starten.

    Die Zuordnung Figur -> Interview kommt aus der dritten Spalte der
    Entwurfszeile ("Interview 2"), sofern es dieses Interview gibt --
    dieselbe Nummerierung wie ``kontext.interviewbezeichnung``. Fehlt sie
    oder passt sie auf kein Interview, bleibt die Quelle leer; Ebene 2 fragt
    dann danach ("Anderes Interview")."""
    from interview_theater import vorschlag

    angelegt: list[str] = []
    for zeile in vorschlag.zeilen(wert):
        zerlegt = vorschlag.figuren(zeile)
        if not zerlegt:
            continue
        name, beschreibung = zerlegt[0]
        # Derselbe Schreibweg wie erkenner._wende_figur_an.
        repo.setze_figur(conn, chat_id, name, beschreibung)
        aufnahme_id = _interview_aus_zeile(conn, chat_id, zeile)
        if aufnahme_id is not None:
            figur = repo.hole_figur(conn, chat_id, name)
            if figur is not None and figur["quelle_aufnahme_id"] is None:
                repo.setze_figur_quelle(conn, figur["id"], aufnahme_id)
        angelegt.append(name)
    if not angelegt:
        log.error("Figuren-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        return T._TEXT_UNBEKANNT
    repo.setze_arbeitsstand(conn, chat_id, "figuren_entwurf", wert)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_FIGUREN.format(namen=", ".join(angelegt)),
        quelle="knopf",
    )
    tg.sende(chat_id, T._TEXT_NOTIERT_KOPF + _figurenzeile(angelegt))
    return T._TEXT_FIGUREN_QUITTUNG


#: "Interview 2" am Ende einer Entwurfszeile.
_INTERVIEWNUMMER = re.compile(r"interview\s*(\d{1,3})", re.IGNORECASE)


def _interview_aus_zeile(conn, chat_id: int, zeile: str) -> int | None:
    """Die ``aufnahme_id`` hinter "Interview N" in einer Entwurfszeile, oder
    None. Gezaehlt wird wie in ``kontext.interviewbezeichnung``: die langen
    Aufnahmen in Entstehungsreihenfolge, ab 1."""
    treffer = _INTERVIEWNUMMER.search(zeile or "")
    if treffer is None:
        return None
    from interview_theater import aufnahme as aufnahme_modul

    koepfe = aufnahme_modul.interviews(conn, chat_id)
    nummer = int(treffer.group(1))
    if 1 <= nummer <= len(koepfe):
        return koepfe[nummer - 1]["id"]
    return None


def _figurenvorstellung(conn, chat_id: int, figur, ohne_beleg: bool = False) -> str:
    """Der Text, mit dem eine Figur in Ebene 2 vorgestellt wird: Name, Satz,
    Interview, Sprachduktus und die belegten Zitate.

    Rein aus der Datenbank, kein Modellaufruf (Zusage 2). Die Zitate stehen
    dabei, weil genau sie zeigen, was der Duktus behauptet -- die Gruppe
    nimmt eine Figur an ihrer Sprache ab, nicht an einer Beschreibung."""
    from interview_theater import kontext

    zeilen = [figur["name"]]
    if (figur["beschreibung"] or "").strip():
        zeilen.append(figur["beschreibung"].strip())
    if figur["quelle_aufnahme_id"] is not None:
        zeilen.append(
            kontext.interviewbezeichnung(conn, chat_id, figur["quelle_aufnahme_id"])
        )
        profil = (figur["sprachprofil"] or "").strip()
        if profil:
            zeilen.append(T._TEXT_SPRACHDUKTUS_ZEILE.format(profil=profil))
        elif ohne_beleg:
            from interview_theater import sprachprofil

            zeilen.append(
                sprachprofil._TEXT_KEIN_ZITAT.format(name=figur["name"])
            )
        else:
            zeilen.append(T._TEXT_DUKTUS_FEHLT)
        zitate = [
            z.strip()
            for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER)
            if z.strip()
        ]
        if zitate:
            zeilen.append("")
            zeilen.append(T._TEXT_ZITATE_VORSPANN)
            zeilen.extend(f"– {z}" for z in zitate)
    else:
        zeilen.append(T._TEXT_DUKTUS_OHNE_QUELLE)
    return "\n".join(zeilen)


def naechste_offene_figur(conn, chat_id: int):
    """Die naechste Figur, die in Ebene 2 noch nicht abgenommen wurde -- oder
    None, wenn alle durch sind.

    "Abgenommen" heisst: ``geprueft_am`` ist gesetzt (ein Druck auf "Passt").
    Der Merkposten sitzt an der Figur und nicht in einer Warteschlange:
    entfernt die Gruppe eine Figur oder kommt spaeter eine dazu, stimmt die
    Liste ohne Zutun."""
    return next(
        (f for f in repo.figuren(conn, chat_id) if not f["geprueft_am"]), None
    )


def ebene2_erlaubt(conn, chat_id: int) -> bool:
    """Darf die Figurenarbeit Figur fuer Figur laufen (Interview-Zuordnung,
    Sprachduktus)?

    Erst ab der Schaerfung (Phase 5). In Phase 4 wird **erfunden**: die
    Figuren entstehen aus Begriffen, Fragen und Setting, und die Frage
    \"aus welchem Interview spricht sie?\" waere dort genau die Ruecklenkung
    aufs Material, die der Umbau vom 05.09.2026 nachts vermeidet. Die Liste
    ist damit nach Ebene 1 fixiert; das Interview kommt in Phase 5 aus der
    Zuordnung (``schaerfung.uebernimm_figur``)."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_SCHAERFUNG


def stelle_stil_vor(conn, tg, klm, e, chat_id: int) -> bool:
    """Fragt fuer die naechste Figur ohne Sprachstil: "Wie spricht <Figur>?"

    Liefert True, wenn ein Stil-Lauf angestossen wurde. Kein Modellaufruf
    hier (Zusage 2) -- ``sprachstil.starte`` gibt an einen Thread ab. Ohne
    geprueftes Material aus den Interviews passiert nichts, und der Aufrufer
    schliesst die Figurenliste wie bisher ab."""
    from interview_theater import sprachstil

    if klm is None:
        return False
    offen = next(
        (
            f for f in repo.figuren(conn, chat_id)
            if not (f["sprachstil"] or "").strip() and not f["geprueft_am"]
        ),
        None,
    )
    if offen is None:
        return False
    if not sprachstil.stilmaterial(conn, chat_id):
        return False
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", offen["name"])
    return sprachstil.starte(conn, tg, klm, e, chat_id, offen["name"]) is not None


def sende_stil(conn, tg, chat_id: int, name: str, antwort: str) -> int:
    """Das Stil-Menue EINER Figur: je Option Titel, gepruefte Zitatzeile und
    der Beispielsatz -- darunter die Knoepfe und "Eigener Stil".

    Die Zitate werden hier **gegen die Transkripte geprueft**
    (``zitat.pruefe``, dieselbe Pruefung wie beim Verdichter): ein erfundenes
    Zitat ginge sonst als Few-Shot in jeden weiteren Szenenlauf ein. Faellt
    eine Option dabei weg, bleiben die anderen."""
    from interview_theater import sprachstil, vorschlag, zitat as zitat_modul

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "stil")
    if not wert:
        log.error("Stil-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    optionen = sprachstil.zerlege(wert)
    quellen = {
        i + 1: kopf["id"]
        for i, kopf in enumerate(_interviewkoepfe(conn, chat_id))
    }
    zeilen_text: list[str] = []
    leiste: list[tuple[str, str]] = []
    nummer = 0
    for titel, zitat, beispiel, interview in optionen:
        aufnahme_id = quellen.get(interview) if interview else None
        if zitat and aufnahme_id is not None and not _zitat_belegt(
            conn, chat_id, aufnahme_id, zitat, zitat_modul
        ):
            log.info("Stil-Zitat nicht belegt, chat_id=%s, %r", chat_id, zitat)
            zitat = ""
        nummer += 1
        beschreibung = " ".join(
            t for t in (f'"{zitat}"' if zitat else "", beispiel) if t
        )
        zeilen_text.append(f"{titel} — {beschreibung}".strip(" —"))
        leiste.append(
            (
                f"{nummer} · {titel}"[:MENUE_KNOPF_LAENGE],
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_FIGUR_STIL,
                        f"{name}{TRENNER}{aufnahme_id or ''}{TRENNER}"
                        f"{titel}: {beispiel or zitat}",
                    )
                ),
            )
        )
    if not leiste:
        return tg.sende(chat_id, sauber)
    leiste.append(
        (
            T._TEXT_STIL_EIGENER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_STIL_FREI, name)),
        )
    )
    # Der Ausweg aus der Figur-fuer-Figur-Schleife (06.09.2026): wer die
    # zwoelf Minuten Modellzeit nicht abwarten will, ordnet in einem Druck
    # zu und kommt weiter.
    zufall = _zufallsknopf(conn, chat_id)
    if zufall is not None:
        leiste.append(zufall)
    html, klar = vorschlag.menuetext(
        T._TEXT_STIL_FRAGE.format(name=name), "\n".join(zeilen_text)
    )
    message_id = _sende_knoepfe(conn, tg, chat_id, html, leiste, parse_mode="HTML", klartext=klar
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id


def _interviewkoepfe(conn, chat_id: int) -> list:
    from interview_theater import aufnahme as aufnahme_modul

    return aufnahme_modul.interviews(conn, chat_id)


def _figuren_ohne_quelle(conn, chat_id: int) -> list:
    """Die Figuren, denen noch kein Interview zugeordnet ist."""
    return [f for f in repo.figuren(conn, chat_id) if not f["quelle_aufnahme_id"]]


def _zufallsknopf(conn, chat_id: int) -> tuple[str, str] | None:
    """Der Knopf "Zufaellig zuordnen" -- oder None, wenn es nichts zuzuordnen
    gibt (keine offene Figur oder kein Interview).

    Ein Knopf, der nichts tut, ist schlimmer als keiner: die Leiste steht
    dann nur da, wo sie auch wirkt."""
    if not _figuren_ohne_quelle(conn, chat_id):
        return None
    if not _interviewkoepfe(conn, chat_id):
        return None
    return (
        T._TEXT_FIGUREN_ZUFALL_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ZUFALL, None)),
    )


def ordne_figuren_zufaellig_zu(conn, chat_id: int) -> tuple[int, int]:
    """Ordnet allen Figuren OHNE Quelle reihum zufaellig ein vorhandenes
    Interview zu. Liefert ``(Figuren, benutzte Interviews)``.

    **Kein Modellaufruf** (Zusage 2): das ist eine reine Datenbankoperation
    ueber ``repo.figuren`` und ``repo.setze_figur_quelle``. Sprachstile
    entstehen dabei ausdruecklich **nicht** -- wer sie will, geht weiter
    Figur fuer Figur ueber ``stelle_stil_vor``.

    **Idempotent** (Zusage 3): bestehende Zuordnungen bleiben unangetastet,
    ein zweiter Aufruf findet nichts Offenes mehr und schreibt nichts. Die
    Knopf-Sperre in ``behandle`` kommt zusaetzlich davor.

    Ein Interview darf mehrere Figuren speisen (ausdruecklich erlaubt): bei
    mehr Figuren als Interviews wird die Interviewliste durchgereicht
    (Round-Robin), damit keines leer ausgeht, bevor sich eines wiederholt."""
    offen = _figuren_ohne_quelle(conn, chat_id)
    koepfe = _interviewkoepfe(conn, chat_id)
    if not offen or not koepfe:
        return (0, 0)
    reihenfolge = list(offen)
    random.shuffle(reihenfolge)
    quellen = [k["id"] for k in koepfe]
    random.shuffle(quellen)
    benutzt: set[int] = set()
    for stelle, figur in enumerate(reihenfolge):
        aufnahme_id = quellen[stelle % len(quellen)]
        repo.setze_figur_quelle(conn, figur["id"], aufnahme_id)
        benutzt.add(aufnahme_id)
    return (len(reihenfolge), len(benutzt))


def _zitat_belegt(conn, chat_id: int, aufnahme_id: int, text: str,
                  zitat_modul) -> bool:
    """Steht dieses Zitat woertlich im Transkript dieses Interviews?"""
    kopf = repo.hole_aufnahme(conn, aufnahme_id)
    if kopf is None:
        return False
    return zitat_modul.pruefe(text, kopf["transkript"] or "")


def stelle_figur_vor(conn, tg, klm, e, chat_id: int, figur=None) -> bool:
    """Stellt die naechste offene Figur mit ihren vier Knoepfen vor -- oder
    schliesst Ebene 2 ab, wenn keine mehr offen ist. Liefert True, solange
    noch eine Figur vorgestellt wurde.

    Fehlt das Sprachprofil, wird es **im Thread** erzeugt
    (``sprachprofil.starte``) -- ein Knopf-Handler ruft kein Modell
    (Zusage 2). Die Vorstellung geht dann NICHT sofort raus, sondern erst
    nach dem Lauf, aus dessen Nachbereitung heraus: vorher fehlen genau die
    Belegzitate, an denen die Gruppe die Figur abnimmt. Bis dahin liest sie
    eine Zeile, die sagt, was gerade passiert (gemessen 05.09.2026: die
    sofort gesendete Fassung mit "Sprachduktus: entsteht gerade." blieb fuer
    immer stehen)."""
    if not ebene2_erlaubt(conn, chat_id):
        # Phase 4: keine Interview-Frage und kein Sprachprofil-Lauf -- aber
        # seit dem 06.09.2026 (Birk, 12:20) der **Sprachstil je Figur**: nach
        # Name und "wer sie ist" EINE Nachricht "Wie spricht <Figur>?" mit
        # zwei bis drei Optionen aus den Interviews. Steht kein Material
        # bereit, ist die Liste wie bisher mit Ebene 1 fertig.
        if stelle_stil_vor(conn, tg, klm, e, chat_id):
            return True
        return _schliesse_figuren_ab(conn, tg, chat_id)
    figur = figur if figur is not None else naechste_offene_figur(conn, chat_id)
    if figur is None:
        return _schliesse_figuren_ab(conn, tg, chat_id)

    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", figur["name"])
    if (klm is not None and figur["quelle_aufnahme_id"] is not None
            and not (figur["sprachprofil"] or "").strip()):
        from interview_theater import kontext, sprachprofil

        figur_id = figur["id"]

        def _nachher() -> None:
            """Laeuft im Sprachprofil-Thread, nachdem das Profil steht (oder
            endgueltig gescheitert ist). Die Figur wird frisch geladen --
            das Profil ist gerade erst geschrieben worden."""
            frisch = repo.hole_figur_nach_id(conn, figur_id)
            if frisch is not None:
                _sende_figurenvorstellung(
                    conn, tg, chat_id, frisch, ohne_beleg=True,
                )

        try:
            thread = sprachprofil.starte(
                conn, tg, klm, e, chat_id, [figur_id], nachbereitung=_nachher,
            )
        except Exception:
            log.exception("Sprachprofil-Start fehlgeschlagen, figur_id=%s", figur_id)
            thread = None
        if thread is not None:
            quelle = kontext.interviewbezeichnung(
                conn, chat_id, figur["quelle_aufnahme_id"]
            ) or T._TEXT_DAS_INTERVIEW
            tg.sende(
                chat_id,
                T._TEXT_DUKTUS_LAEUFT.format(quelle=quelle, name=figur["name"]),
            )
            return True

    _sende_figurenvorstellung(conn, tg, chat_id, figur)
    return True


def _sende_figurenvorstellung(conn, tg, chat_id: int, figur,
                              ohne_beleg: bool = False) -> None:
    """Vorstellungstext plus die fuenf Knoepfe. Eigene Funktion, weil sie
    aus zwei Richtungen kommt: direkt (Profil steht schon) und aus der
    Nachbereitung des Sprachprofil-Threads. ``ohne_beleg`` heisst: der Lauf
    ist durch und hat trotzdem kein Profil geliefert -- dann steht statt
    "entsteht gerade" der Hinweis aus ``sprachprofil._TEXT_KEIN_ZITAT``,
    denn die Gruppe kann das beheben (ein anderes Interview nennen)."""
    name = figur["name"]
    for art in (ART_FIGUR_PASST, ART_FIGUR_INTERVIEW_MENU,
                ART_FIGUR_DUKTUS_MENU, ART_FIGUR_ENTFERNEN):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    leiste = [
        (T._TEXT_FIGUR_PASST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_PASST, name))),
        (T._TEXT_FIGUR_INTERVIEW_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_INTERVIEW_MENU, name))),
        (T._TEXT_FIGUR_DUKTUS_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_DUKTUS_MENU, name))),
        (T._TEXT_FIGUR_ENTFERNEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_ENTFERNEN, name))),
        (T._TEXT_EIGENE_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, "figur"))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, _figurenvorstellung(conn, chat_id, figur, ohne_beleg), leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)


def _schliesse_figuren_ab(conn, tg, chat_id: int) -> bool:
    """Ebene 2 ist durch: Merkposten setzen und **innerhalb derselben Phase**
    zur Geschichte ueberleiten. Liefert immer False (es wurde keine Figur
    mehr vorgestellt).

    Bis zum 06.09.2026 stand hier der Knopf "Weiter zu Geschichte" -- eine
    eigene Station mit eigener Phasenmeldung. Birk hat beides
    zusammengelegt: Setting, Figuren und Geschichte sind eine Arbeit, und
    eine Zaesur mittendrin unterbricht sie, statt sie zu ordnen. Jetzt eine
    kurze Zeile und die offene Frage, darunter dieselben zwei Knoepfe wie bei
    jedem Eintritt ("Ja, wir zuerst" · "Schlag du vor")."""
    if not repo.figuren(conn, chat_id):
        tg.sende(chat_id, T._TEXT_FIGUREN_KEINE)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_FIGURENLISTE_STEHT, quelle="knopf",
    )
    leiste = [
        (T._TEXT_WIR_ZUERST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_WIR_ZUERST, str(PHASE_SETTING)))),
        (T._TEXT_SCHLAG_VOR_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHLAG_VOR, str(PHASE_SETTING)))),
    ]
    # Genau hier startete bisher die Figur-fuer-Figur-Schleife mit einem
    # Modellaufruf je Figur (06.09.2026, gemessen: 12 Laeufe, 718 s, und
    # trotzdem fuenf Figuren ohne Quelle). Der Knopf daneben erledigt die
    # Zuordnung in einem Druck, ohne Modell.
    zufall = _zufallsknopf(conn, chat_id)
    if zufall is not None:
        leiste.append(zufall)
    message_id = _sende_knoepfe(conn, tg, chat_id, T._TEXT_ZUR_GESCHICHTE, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return False


def _biete_interviews(conn, tg, chat_id: int, name: str) -> str:
    """Ein Knopf je vorhandenem Interview -- die Auswahl fuer "Anderes
    Interview". Ohne Interviews gibt es nichts zu waehlen."""
    from interview_theater import aufnahme as aufnahme_modul
    from interview_theater import kontext

    koepfe = aufnahme_modul.interviews(conn, chat_id)
    if not koepfe:
        tg.sende(chat_id, T._TEXT_KEIN_INTERVIEW)
        return T._TEXT_KEIN_INTERVIEW
    leiste = [
        (
            kontext.interviewbezeichnung(conn, chat_id, kopf["id"]),
            _daten(repo.lege_knopf_an(
                conn, chat_id, ART_FIGUR_INTERVIEW, f"{name}{TRENNER}{kopf['id']}"
            )),
        )
        for kopf in koepfe
    ]
    frage = T._TEXT_FIGUR_INTERVIEW_FRAGE.format(name=name)
    message_id = _sende_knoepfe(conn, tg, chat_id, frage, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return T._TEXT_INTERVIEW_WAEHLEN_QUITTUNG
